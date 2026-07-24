#!/usr/bin/env python3
"""tools/e2/synth/grammar.py -- E2 CARD S2-B.

Synthetic rectilinear wall grammar + DXF emitter core.

This module GENERATES synthetic drawings (it does not read or modify any
original CAD file). Two public functions:

  plan_random(seed, spec) -> WallPlan
      A deterministic (per-seed) rectilinear wall network: one outer loop plus
      binary-space-partition (BSP) interior partitions. Junctions that emerge
      are L (outer corners) and T (partition stems meeting a through-wall).

  emit(plan, dxf_path, opening_renderer=None) -> TRUTH-LEDGER v1
      Each wall centerline becomes two parallel LINEs offset by +/- thickness/2,
      with a simple mitred junction trim (extend at L corners, trim at T stems).
      A few 'MISC' clutter LINEs are added and recorded as non-wall. If an
      opening_renderer callback is supplied it is called per wall with a
      line-adding function and its returned opening-truth entries are merged.
      Handles in the ledger are the REAL handles read back from the saved doc.

Contracts (inline, shared across S2 cards)
------------------------------------------
WallPlan dict (plan == "wp.v1"):
  {"plan":"wp.v1","seed":int,"units":"mm",
   "walls":[{"id":"w1","axis":[[x,y],[x,y]],"thickness":240.0,"layer":"WALL"}],
   "openings":[{"id":"o1","wall_id":"w1","span_along_axis":[t0,t1],
                "type":"door|window"}]}     # span t in 0..1 along axis

TRUTH-LEDGER v1 (truth == "wall.v1"):
  {"truth":"wall.v1","drawing_id":"str",
   "walls":[{"id":"w1","axis":[[x,y],[x,y]],"thickness":240.0,"layer":"WALL",
             "handles":["h1","h2"]}],
   "openings":[{"id":"o1","wall_id":"w1","span_along_axis":[t0,t1],
                "type":"door|window"}],
   "wall_handles_flat":["h1","h2"]}
  (additive, non-contract key: "non_wall_handles" -- records the MISC clutter)

DXF: R2018 ASCII (ezdxf default write format). ezdxf is explicitly allowed.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import tempfile

import ezdxf

WP_VERSION = "wp.v1"
TRUTH_VERSION = "wall.v1"

DEFAULT_SPEC = {
    "thickness_choices": [100, 150, 200, 240, 300],
    "n_rooms": [2, 6],          # int -> fixed; [lo, hi] -> sampled inclusive
    "extent": [8000, 6000],     # [w, h] in mm
}

# Appids used to tag entities so handles can be read back and grouped by wall.
_APPID_WALL = "E2WALL"
_APPID_MISC = "E2MISC"
_APPID_OPEN = "E2OPEN"

_EPS = 1e-6


# --------------------------------------------------------------------------- #
# small 2D geometry helpers
# --------------------------------------------------------------------------- #
def _pt_eq(a, b, eps=_EPS):
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps


def _unit(ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    n = math.hypot(dx, dy)
    if n == 0.0:
        return 0.0, 0.0, 0.0
    return dx / n, dy / n, n


def _on_seg_interior(p, a, b, eps=_EPS):
    """True if p lies on segment a-b, strictly between the endpoints."""
    if _pt_eq(p, a, eps) or _pt_eq(p, b, eps):
        return False
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0.0:
        return False
    t = ((px - ax) * dx + (py - ay) * dy) / l2
    if t <= eps or t >= 1.0 - eps:
        return False
    projx, projy = ax + t * dx, ay + t * dy
    return math.hypot(px - projx, py - projy) <= eps


def _endpoint_delta(endpoint, wall, walls):
    """Mitre adjustment for one wall endpoint (signed distance along axis).

    +delta => EXTEND outward past the endpoint (L corner: fill the corner).
    -delta => TRIM inward from the endpoint (T stem: butt against a through-wall).
     0.0   => free end / no junction: leave as a plain butt.

    All classification uses centerline axis coordinates (exact) not offsets.
    """
    # L corner: another wall shares this endpoint -> extend by its half-thickness.
    extend = 0.0
    for other in walls:
        if other is wall:
            continue
        a2, b2 = other["axis"][0], other["axis"][1]
        if _pt_eq(endpoint, a2) or _pt_eq(endpoint, b2):
            extend = max(extend, other["thickness"] / 2.0)
    if extend > 0.0:
        return extend
    # T stem: this endpoint lands on the interior of another wall -> trim.
    for other in walls:
        if other is wall:
            continue
        a2, b2 = other["axis"][0], other["axis"][1]
        if _on_seg_interior(endpoint, a2, b2):
            return -(other["thickness"] / 2.0)
    return 0.0


def _wall_offset_segments(wall, walls):
    """Return ((p0,p1),(m0,m1)) two parallel offset segments for a wall.

    plus segment is offset by +thickness/2 along the left normal,
    minus segment by -thickness/2, both with endpoint mitre extend/trim applied.
    """
    (ax, ay), (bx, by) = wall["axis"]
    ux, uy, length = _unit(ax, ay, bx, by)
    ht = wall["thickness"] / 2.0
    nx, ny = -uy, ux  # left normal

    da = _endpoint_delta((ax, ay), wall, walls)  # at A
    db = _endpoint_delta((bx, by), wall, walls)  # at B

    # Guard against over-trim collapsing/inverting a short wall.
    trim_a = -da if da < 0 else 0.0
    trim_b = -db if db < 0 else 0.0
    if length > 0 and (trim_a + trim_b) >= length:
        room = max(0.0, length - _EPS) / 2.0
        if trim_a > room:
            da = -room
        if trim_b > room:
            db = -room

    # Outward direction at A is -u, at B is +u. Positive delta pushes outward.
    a2x, a2y = ax - ux * da, ay - uy * da
    b2x, b2y = bx + ux * db, by + uy * db

    plus = ((a2x + nx * ht, a2y + ny * ht), (b2x + nx * ht, b2y + ny * ht))
    minus = ((a2x - nx * ht, a2y - ny * ht), (b2x - nx * ht, b2y - ny * ht))
    return plus, minus


# --------------------------------------------------------------------------- #
# plan_random
# --------------------------------------------------------------------------- #
def _resolve_spec(spec):
    merged = dict(DEFAULT_SPEC)
    if spec:
        merged.update(spec)
    return merged


def _resolve_n_rooms(rng, n_rooms):
    if isinstance(n_rooms, (list, tuple)):
        lo, hi = int(n_rooms[0]), int(n_rooms[1])
        return rng.randint(lo, hi)
    return int(n_rooms)


def plan_random(seed, spec=None):
    """Deterministic rectilinear wall network for a given seed.

    Outer rectangle (4 walls) + BSP interior partitions. n_rooms rooms require
    n_rooms-1 partition walls, so len(walls) == n_rooms + 3.
    """
    rng = random.Random(seed)
    spec = _resolve_spec(spec)
    w, h = int(spec["extent"][0]), int(spec["extent"][1])
    thickness_choices = list(spec["thickness_choices"])
    layer = spec.get("layer", "WALL")
    n_rooms = _resolve_n_rooms(rng, spec["n_rooms"])
    n_rooms = max(1, n_rooms)

    walls = []
    counter = [0]

    def add_wall(p0, p1):
        counter[0] += 1
        t = float(rng.choice(thickness_choices))
        walls.append({
            "id": f"w{counter[0]}",
            "axis": [[float(p0[0]), float(p0[1])], [float(p1[0]), float(p1[1])]],
            "thickness": t,
            "layer": layer,
        })

    # Outer loop (4 walls, closed rectangle).
    add_wall((0, 0), (w, 0))
    add_wall((w, 0), (w, h))
    add_wall((w, h), (0, h))
    add_wall((0, h), (0, 0))

    # BSP interior partitions: split the largest region until n_rooms reached.
    regions = [(0, 0, w, h)]  # x0, y0, x1, y1
    guard = 0
    while len(regions) < n_rooms and guard < 500:
        guard += 1
        # Pick the largest-area region (deterministic; ties by first index).
        idx = max(range(len(regions)),
                  key=lambda i: (regions[i][2] - regions[i][0]) *
                                (regions[i][3] - regions[i][1]))
        x0, y0, x1, y1 = regions.pop(idx)
        rw, rh = x1 - x0, y1 - y0
        # Split the longer dimension; jittered but bounded away from edges.
        split_vertical = rw >= rh
        frac = rng.uniform(0.35, 0.65)
        if split_vertical:
            xs = int(round(x0 + rw * frac))
            xs = min(max(xs, x0 + 1), x1 - 1)
            add_wall((xs, y0), (xs, y1))
            regions.append((x0, y0, xs, y1))
            regions.append((xs, y0, x1, y1))
        else:
            ys = int(round(y0 + rh * frac))
            ys = min(max(ys, y0 + 1), y1 - 1)
            add_wall((x0, ys), (x1, ys))
            regions.append((x0, y0, x1, ys))
            regions.append((x0, ys, x1, y1))

    return {
        "plan": WP_VERSION,
        "seed": int(seed),
        "units": "mm",
        "walls": walls,
        "openings": [],  # opening specs are produced by the opening_renderer (emit)
    }


# --------------------------------------------------------------------------- #
# emit
# --------------------------------------------------------------------------- #
def _ensure_appid(doc, name):
    if name not in doc.appids:
        try:
            doc.appids.add(name)
        except Exception:  # pragma: no cover - older ezdxf API fallback
            doc.appids.new(name)


def _ensure_layer(doc, name):
    if name not in doc.layers:
        doc.layers.add(name)


def emit(plan, dxf_path, opening_renderer=None):
    """Emit the plan as an R2018 DXF and return a TRUTH-LEDGER v1 dict.

    opening_renderer(wall_dict, add_line_fn) -> list[opening_entry] (optional).
      add_line_fn(start, end, layer="OPENING", meta="") -> handle draws a line
      and returns its real handle. Returned opening entries are merged into the
      ledger's "openings".
    """
    walls = plan["walls"]

    doc = ezdxf.new("R2018")
    for appid in (_APPID_WALL, _APPID_MISC, _APPID_OPEN):
        _ensure_appid(doc, appid)
    for ly in {w["layer"] for w in walls} | {"MISC"}:
        _ensure_layer(doc, ly)
    msp = doc.modelspace()

    # --- wall geometry: two parallel offset LINEs per wall ------------------ #
    for wall in walls:
        plus, minus = _wall_offset_segments(wall, walls)
        for kind, (s, e) in (("plus", plus), ("minus", minus)):
            line = msp.add_line(s, e, dxfattribs={"layer": wall["layer"]})
            line.set_xdata(_APPID_WALL, [(1000, wall["id"]), (1000, kind)])

    # --- optional opening renderer ------------------------------------------ #
    openings = []
    if opening_renderer is not None:
        def add_line_fn(start, end, layer="OPENING", meta=""):
            _ensure_layer(doc, layer)
            ln = msp.add_line(start, end, dxfattribs={"layer": layer})
            ln.set_xdata(_APPID_OPEN, [(1000, str(meta))])
            return ln.dxf.handle
        for wall in walls:
            entries = opening_renderer(wall, add_line_fn)
            if entries:
                openings.extend(entries)

    # --- non-wall clutter on layer MISC ------------------------------------- #
    crng = random.Random((plan.get("seed", 0) * 2654435761) & 0xFFFFFFFF)
    ext_w = max((abs(w["axis"][1][0] - w["axis"][0][0]) for w in walls), default=1000)
    ext_h = max((abs(w["axis"][1][1] - w["axis"][0][1]) for w in walls), default=1000)
    span = max(ext_w, ext_h, 1000)
    for _ in range(3):
        x0 = crng.uniform(0, span)
        y0 = crng.uniform(0, span)
        x1 = x0 + crng.uniform(-span * 0.15, span * 0.15)
        y1 = y0 + crng.uniform(-span * 0.15, span * 0.15)
        ln = msp.add_line((x0, y0), (x1, y1), dxfattribs={"layer": "MISC"})
        ln.set_xdata(_APPID_MISC, [(1000, "clutter")])

    # --- save, then read handles BACK from the saved document --------------- #
    doc.saveas(dxf_path)
    doc2 = ezdxf.readfile(dxf_path)
    msp2 = doc2.modelspace()

    wall_handles = {}          # wall_id -> [handle, ...]
    non_wall_handles = []
    for e in msp2.query("LINE"):
        if e.has_xdata(_APPID_WALL):
            xd = e.get_xdata(_APPID_WALL)
            wid = xd[0][1]
            wall_handles.setdefault(wid, []).append(e.dxf.handle)
        elif e.has_xdata(_APPID_MISC):
            non_wall_handles.append(e.dxf.handle)

    drawing_id = os.path.splitext(os.path.basename(dxf_path))[0]
    ledger_walls = []
    flat = []
    for wall in walls:
        hs = wall_handles.get(wall["id"], [])
        flat.extend(hs)
        ledger_walls.append({
            "id": wall["id"],
            "axis": wall["axis"],
            "thickness": wall["thickness"],
            "layer": wall["layer"],
            "handles": hs,
        })

    return {
        "truth": TRUTH_VERSION,
        "drawing_id": drawing_id,
        "walls": ledger_walls,
        "openings": openings,
        "wall_handles_flat": flat,
        "non_wall_handles": non_wall_handles,
    }


# --------------------------------------------------------------------------- #
# selftest
# --------------------------------------------------------------------------- #
def _demo_opening_renderer(wall, add_line_fn):
    """Tiny smoke renderer: put one door mid-span on horizontal walls.

    Draws two jamb lines and returns one opening-truth entry. Used only to
    exercise the callback merge path in the selftest.
    """
    (ax, ay), (bx, by) = wall["axis"]
    if abs(by - ay) > _EPS:        # only horizontal walls, keep it trivial
        return []
    ux, uy, length = _unit(ax, ay, bx, by)
    if length < 2000:
        return []
    t0, t1 = 0.45, 0.55
    j0 = (ax + ux * length * t0, ay + uy * length * t0)
    j1 = (ax + ux * length * t1, ay + uy * length * t1)
    add_line_fn(j0, (j0[0], j0[1] + 1), layer="OPENING", meta=wall["id"])
    add_line_fn(j1, (j1[0], j1[1] + 1), layer="OPENING", meta=wall["id"])
    return [{
        "id": f"o_{wall['id']}",
        "wall_id": wall["id"],
        "span_along_axis": [t0, t1],
        "type": "door",
    }]


def _selftest():
    print("== E2 S2-B grammar selftest ==")
    print(f"ezdxf {ezdxf.__version__}")

    spec = {
        "thickness_choices": [100, 150, 200, 240, 300],
        "n_rooms": 3,
        "extent": [8000, 6000],
    }
    plan = plan_random(7, spec)
    n_walls = len(plan["walls"])
    print(f"plan: seed={plan['seed']} units={plan['units']} walls={n_walls}")
    assert plan["plan"] == WP_VERSION, "plan version key"
    assert plan["seed"] == 7
    assert n_walls == 6, f"expected 4 outer + 2 partitions == 6, got {n_walls}"

    # Determinism: same seed -> byte-identical plan.
    plan_again = plan_random(7, spec)
    assert plan_again == plan, "plan_random must be deterministic per seed"
    print("determinism: plan_random(7) reproducible -> OK")

    tmpdir = tempfile.mkdtemp(prefix="e2_s2b_")
    dxf_path = os.path.join(tmpdir, "e2_s2b_seed7.dxf")
    print(f"tmp dxf: {dxf_path}")

    ledger = emit(plan, dxf_path)

    assert ledger["truth"] == TRUTH_VERSION, "ledger truth key"
    assert ledger["drawing_id"] == "e2_s2b_seed7"
    # CARD assertion: ledger wall handle count == 2 * len(walls) minimum.
    assert len(ledger["wall_handles_flat"]) >= 2 * n_walls, (
        f"wall handle count {len(ledger['wall_handles_flat'])} < {2 * n_walls}")
    assert len(ledger["wall_handles_flat"]) == 2 * n_walls, (
        "expected exactly 2 offset lines per wall")
    for w in ledger["walls"]:
        assert len(w["handles"]) >= 2, f"wall {w['id']} has <2 handles"
    # Handles are unique.
    flat = ledger["wall_handles_flat"]
    assert len(set(flat)) == len(flat), "duplicate wall handles"
    print(f"ledger: walls={len(ledger['walls'])} "
          f"wall_handles_flat={len(flat)} (==2*{n_walls}) "
          f"non_wall={len(ledger['non_wall_handles'])} "
          f"openings={len(ledger['openings'])}")

    # Re-open the saved DXF independently and verify every handle is REAL.
    doc = ezdxf.readfile(dxf_path)
    saved = {e.dxf.handle: e for e in doc.modelspace().query("LINE")}
    for h in flat:
        assert h in saved, f"wall handle {h} absent from saved DXF"
    for h in ledger["non_wall_handles"]:
        assert h in saved, f"misc handle {h} absent from saved DXF"
        assert saved[h].dxf.layer == "MISC", "clutter must be on MISC layer"
    total_lines = len(saved)
    print(f"reopen: {total_lines} LINEs in saved doc; "
          f"all {len(flat)} wall + {len(ledger['non_wall_handles'])} misc "
          f"handles present -> OK")
    assert doc.dxfversion == ezdxf.const.acad_release_to_dxf_version["R2018"], \
        f"expected R2018, got {doc.dxfversion}"
    print(f"dxf version: {doc.dxfversion} (R2018) -> OK")

    # Exercise the opening_renderer merge path (separate file).
    dxf_path2 = os.path.join(tmpdir, "e2_s2b_seed7_openings.dxf")
    ledger2 = emit(plan, dxf_path2, opening_renderer=_demo_opening_renderer)
    assert len(ledger2["openings"]) >= 1, "opening_renderer entries not merged"
    for o in ledger2["openings"]:
        assert {"id", "wall_id", "span_along_axis", "type"} <= set(o), \
            "opening entry missing contract keys"
        assert any(w["id"] == o["wall_id"] for w in ledger2["walls"]), \
            "opening wall_id must reference a wall"
    print(f"opening_renderer path: merged {len(ledger2['openings'])} "
          f"opening entrie(s) -> OK")

    # Show a compact slice of the ledger so output carries real evidence.
    sample = {
        "truth": ledger["truth"],
        "drawing_id": ledger["drawing_id"],
        "wall0": ledger["walls"][0],
        "wall_handles_flat": flat,
        "non_wall_handles": ledger["non_wall_handles"],
    }
    print("ledger sample:")
    print(json.dumps(sample, indent=2))
    print("SELFTEST PASS")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="E2 S2-B synthetic wall grammar")
    parser.add_argument("--selftest", action="store_true",
                        help="build a fixture in the OS temp dir and verify")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
