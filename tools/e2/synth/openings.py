#!/usr/bin/env python3
"""tools/e2/synth/openings.py -- E2 CARD S2-C.

Openings module: deterministically ASSIGN doors/windows onto a synthetic
WallPlan, and RENDER an opening by splitting a wall's two parallel face lines
at the gap (plus jamb ticks and, for doors, a quarter-circle swing arc).

Two public functions:

  assign(plan, seed, spec) -> plan
      Copy of `plan` with `openings` populated. Each wall is (deterministically,
      per seed) given a door (0.9 m default), a window (1.2 m default), or
      nothing, according to `spec` probabilities {"door_p":0.6,"window_p":0.4}.
      Each span is clamped away from the wall's two junction zones (the corner
      regions near each endpoint where walls meet) by one wall-thickness at each
      end. A wall too short to fit the opening plus its clearances gets nothing.

  opening_renderer(wall_dict, add_line_fn) -> list[entry]
      Rendering callback with the signature grammar.emit injects (see the
      grammar module's `emit` docstring; this module does NOT import grammar).
      For every opening carried on `wall_dict["openings"]` it:
        * SPLITS each of the wall's two parallel face lines at the span so a
          real gap is left in the middle (add_line_fn draws the solid pieces);
        * draws a jamb tick line across the thickness at each side of the gap;
        * for doors, emits a quarter-circle swing arc on layer 'DOOR'.
      Returns a list mixing opening-truth entries
        {"id","wall_id","span_along_axis":[t0,t1],"type"}
      and, for doors, arc entries the caller renders
        {"arc":{"center":[x,y],"r":r,"start":a0,"end":a1,"layer":"DOOR"}}
      (arcs cannot go through add_line_fn, which draws LINEs only).

The two functions compose through a tiny bridge (`_walls_with_openings`): run
`assign` to fill `plan["openings"]`, then hand each wall its own openings before
calling `opening_renderer`. That is exactly what an emit that supports
per-wall openings does; the selftest performs the bridge explicitly with a
recording stub add_line_fn instead of importing grammar.

Contracts (inline, shared across S2 cards)
------------------------------------------
WallPlan dict (plan == "wp.v1"):
  {"plan":"wp.v1","seed":int,"units":"mm",
   "walls":[{"id":"w1","axis":[[x,y],[x,y]],"thickness":240.0,"layer":"WALL"}],
   "openings":[{"id":"o1","wall_id":"w1","span_along_axis":[t0,t1],
                "type":"door|window"}]}     # span t in 0..1 along axis

TRUTH-LEDGER v1 (truth == "wall.v1") openings entries share the exact keys
{"id","wall_id","span_along_axis","type"}.

DXF: R2018 ASCII (ezdxf). ezdxf is explicitly allowed for this card.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import random
import sys
import tempfile

import ezdxf

WP_VERSION = "wp.v1"

# Default opening widths in millimetres (WallPlan units == "mm").
DOOR_WIDTH_MM = 900.0
WINDOW_WIDTH_MM = 1200.0

# Default assignment probabilities. door_p + window_p may be < 1.0; the
# remainder is the probability a wall gets no opening.
DEFAULT_SPEC = {"door_p": 0.6, "window_p": 0.4}

_EPS = 1e-9


# --------------------------------------------------------------------------- #
# small 2D geometry helpers (inlined; grammar is NOT imported)
# --------------------------------------------------------------------------- #
def _unit(ax, ay, bx, by):
    """Unit direction A->B and the segment length."""
    dx, dy = bx - ax, by - ay
    n = math.hypot(dx, dy)
    if n == 0.0:
        return 0.0, 0.0, 0.0
    return dx / n, dy / n, n


def _solid_segments(spans, lo=0.0, hi=1.0):
    """Complement of the union of `spans` inside [lo, hi].

    `spans` is a list of (t0, t1) sorted by t0 and assumed non-overlapping and
    inside (lo, hi). Returns the solid (drawn) pieces of the axis parameter --
    e.g. one opening [0.4, 0.55] yields [(0.0, 0.4), (0.55, 1.0)].
    """
    segs = []
    cur = lo
    for a, b in spans:
        a = max(lo, a)
        b = min(hi, b)
        if a > cur + _EPS:
            segs.append((cur, a))
        cur = max(cur, b)
    if cur < hi - _EPS:
        segs.append((cur, hi))
    return segs


# --------------------------------------------------------------------------- #
# assign
# --------------------------------------------------------------------------- #
def _resolve_spec(spec):
    merged = dict(DEFAULT_SPEC)
    if spec:
        merged.update(spec)
    return merged


def assign(plan, seed, spec=None):
    """Return a copy of `plan` with `openings` populated deterministically.

    For each wall, in order, one RNG draw decides door / window / nothing using
    `spec` ("door_p", "window_p"); a second draw (only when an opening is
    placed) positions the span. The span is clamped so it stays clear of both
    junction zones -- a margin of one wall-thickness at each end -- and centred
    randomly within the remaining room. Walls too short to fit the opening plus
    clearances receive nothing. Input `plan` is not mutated.
    """
    spec = _resolve_spec(spec)
    door_p = float(spec.get("door_p", DEFAULT_SPEC["door_p"]))
    window_p = float(spec.get("window_p", DEFAULT_SPEC["window_p"]))

    rng = random.Random(seed)
    out = copy.deepcopy(plan)
    openings = []
    counter = 0

    for wall in out.get("walls", []):
        (ax, ay), (bx, by) = wall["axis"]
        length = math.hypot(bx - ax, by - ay)
        if length <= 0.0:
            continue

        roll = rng.random()
        if roll < door_p:
            otype, width = "door", DOOR_WIDTH_MM
        elif roll < door_p + window_p:
            otype, width = "window", WINDOW_WIDTH_MM
        else:
            continue  # no opening on this wall

        thickness = float(wall.get("thickness", 240.0))
        # Junction zone: keep clear of each corner by one wall-thickness.
        margin_frac = thickness / length
        width_frac = width / length
        lo = margin_frac + width_frac / 2.0
        hi = 1.0 - margin_frac - width_frac / 2.0
        if hi <= lo:
            continue  # wall too short for this opening + clearances

        center = rng.uniform(lo, hi)
        t0 = center - width_frac / 2.0
        t1 = center + width_frac / 2.0
        counter += 1
        openings.append({
            "id": f"o{counter}",
            "wall_id": wall["id"],
            "span_along_axis": [t0, t1],
            "type": otype,
        })

    out["openings"] = openings
    return out


def _walls_with_openings(plan):
    """Bridge assign -> opening_renderer.

    Yield each wall dict enriched with its own openings (grouped from the flat
    `plan["openings"]` list by wall_id). This is what an emit that supports
    per-wall openings passes as `wall_dict` to `opening_renderer`.
    """
    by_wall = {}
    for op in plan.get("openings", []):
        by_wall.setdefault(op["wall_id"], []).append(op)
    for wall in plan.get("walls", []):
        enriched = dict(wall)
        enriched["openings"] = by_wall.get(wall["id"], [])
        yield enriched


# --------------------------------------------------------------------------- #
# opening_renderer  (callback injected into grammar.emit)
# --------------------------------------------------------------------------- #
def opening_renderer(wall_dict, add_line_fn):
    """Render every opening on `wall_dict` and return opening-truth + arc entries.

    Geometry per opening span [t0, t1] (t measured along the wall axis A->B):
      * the two parallel face lines (axis +/- thickness/2 along the normal) are
        SPLIT at the span, so add_line_fn draws only the solid pieces and the
        gap is genuinely empty;
      * a jamb tick line spans the thickness at t0 and at t1;
      * doors additionally get a quarter-circle swing arc (returned, not drawn
        through add_line_fn, which handles LINEs only).

    `add_line_fn(start, end, layer=..., meta=...)` matches the callback
    grammar.emit injects; only (start, end, layer) are used here.
    """
    axis = wall_dict.get("axis")
    ops = list(wall_dict.get("openings", []))
    if not axis or not ops:
        return []

    (ax, ay), (bx, by) = axis
    ux, uy, length = _unit(ax, ay, bx, by)
    if length <= 0.0:
        return []
    ht = float(wall_dict.get("thickness", 240.0)) / 2.0
    nx, ny = -uy, ux  # left normal (unit)
    layer = wall_dict.get("layer", "WALL")
    wall_id = wall_dict.get("id", "")

    # Sorted, in-range spans define the gaps.
    spans = sorted(
        (tuple(o["span_along_axis"]) for o in ops), key=lambda s: s[0]
    )

    def _axis_point(t):
        return ax + ux * length * t, ay + uy * length * t

    # --- split each face line into its solid pieces around the gaps --------- #
    for sign in (1.0, -1.0):
        ox, oy = nx * ht * sign, ny * ht * sign
        for a, b in _solid_segments(spans):
            sax, say = _axis_point(a)
            ebx, eby = _axis_point(b)
            add_line_fn((sax + ox, say + oy), (ebx + ox, eby + oy), layer)

    # --- per-opening jamb ticks, truth entries, and door swing arcs --------- #
    entries = []
    ops_sorted = sorted(ops, key=lambda o: o["span_along_axis"][0])
    for op in ops_sorted:
        t0, t1 = op["span_along_axis"]
        # Jamb tick across the thickness at each side of the gap.
        for t in (t0, t1):
            px, py = _axis_point(t)
            add_line_fn((px + nx * ht, py + ny * ht),
                        (px - nx * ht, py - ny * ht), layer)

        entries.append({
            "id": op.get("id"),
            "wall_id": wall_id,
            "span_along_axis": [t0, t1],
            "type": op["type"],
        })

        if op["type"] == "door":
            # Hinge at the t0 jamb on the +normal face; leaf sweeps 90deg from
            # the wall direction (closed) to the normal direction (open).
            hx, hy = _axis_point(t0)
            hx, hy = hx + nx * ht, hy + ny * ht
            radius = (t1 - t0) * length
            a0 = math.degrees(math.atan2(uy, ux))
            a1 = math.degrees(math.atan2(ny, nx))
            entries.append({
                "arc": {
                    "center": [hx, hy],
                    "r": radius,
                    "start": a0,
                    "end": a1,
                    "layer": "DOOR",
                }
            })

    return entries


# --------------------------------------------------------------------------- #
# selftest -- self-contained; fabricates a WallPlan literal, builds to OS temp
# --------------------------------------------------------------------------- #
def _proj_t(pt, a, ux, uy, length):
    """Project a point onto the axis and return its parameter t (0..1)."""
    return ((pt[0] - a[0]) * ux + (pt[1] - a[1]) * uy) / length


def _fixture_plan():
    """A hand-written WallPlan: outer 6000x4000 rectangle + one partition."""
    return {
        "plan": WP_VERSION,
        "seed": 0,
        "units": "mm",
        "walls": [
            {"id": "w1", "axis": [[0.0, 0.0], [6000.0, 0.0]],
             "thickness": 240.0, "layer": "WALL"},
            {"id": "w2", "axis": [[6000.0, 0.0], [6000.0, 4000.0]],
             "thickness": 240.0, "layer": "WALL"},
            {"id": "w3", "axis": [[6000.0, 4000.0], [0.0, 4000.0]],
             "thickness": 240.0, "layer": "WALL"},
            {"id": "w4", "axis": [[0.0, 4000.0], [0.0, 0.0]],
             "thickness": 240.0, "layer": "WALL"},
            {"id": "w5", "axis": [[3000.0, 0.0], [3000.0, 4000.0]],
             "thickness": 150.0, "layer": "WALL"},
        ],
        "openings": [],
    }


def _assert_no_line_crosses_gaps(recorded, wall):
    """CARD assertion: no recorded line's axis projection overlaps any gap."""
    (ax, ay), (bx, by) = wall["axis"]
    ux, uy, length = _unit(ax, ay, bx, by)
    spans = [o["span_along_axis"] for o in wall["openings"]]
    a = (ax, ay)
    for start, end, _layer in recorded:
        ts = _proj_t(start, a, ux, uy, length)
        te = _proj_t(end, a, ux, uy, length)
        tlo, thi = min(ts, te), max(ts, te)
        for t0, t1 in spans:
            overlap = min(thi, t1) - max(tlo, t0)
            assert overlap <= 1e-6, (
                f"line proj [{tlo:.4f},{thi:.4f}] crosses gap "
                f"[{t0:.4f},{t1:.4f}] on {wall['id']}")


def _selftest():
    print("== E2 S2-C openings selftest ==")
    print(f"ezdxf {ezdxf.__version__}")

    seed = 11
    spec = {"door_p": 0.6, "window_p": 0.4}
    plan = _fixture_plan()
    assigned = assign(plan, seed, spec)

    assert plan["openings"] == [], "assign must not mutate the input plan"
    n_open = len(assigned["openings"])
    print(f"assign(seed={seed}): {n_open} opening(s) over "
          f"{len(assigned['walls'])} walls")
    for op in assigned["openings"]:
        t0, t1 = op["span_along_axis"]
        assert {"id", "wall_id", "span_along_axis", "type"} <= set(op)
        assert op["type"] in ("door", "window")
        assert 0.0 < t0 < t1 < 1.0, f"span out of range: {op}"
        print(f"  {op['id']} {op['type']:6s} on {op['wall_id']} "
              f"span=[{t0:.4f},{t1:.4f}]")

    # Determinism: same seed -> identical assignment.
    assert assign(plan, seed, spec) == assigned, "assign must be deterministic"
    print("determinism: assign(11) reproducible -> OK")

    # --- render every wall via the callback contract, recording each line --- #
    print("-- opening_renderer over assigned plan (recording stub) --")
    total_lines = 0
    total_arcs = 0
    checked_walls = 0
    for wall in _walls_with_openings(assigned):
        recorded = []

        def rec(start, end, layer="OPENING", meta=""):
            recorded.append((tuple(start), tuple(end), layer))
            return f"h{len(recorded)}"

        entries = opening_renderer(wall, rec)
        if not wall["openings"]:
            assert entries == [] and recorded == [], \
                f"{wall['id']} has no openings but rendered geometry"
            continue

        checked_walls += 1
        # CARD assertion: no drawn line crosses the gap span(s).
        _assert_no_line_crosses_gaps(recorded, wall)

        truth = [e for e in entries if "arc" not in e]
        arcs = [e for e in entries if "arc" in e]
        # Each opening -> 2 face pieces/face * 2 faces + 2 jamb ticks == 6 lines.
        expected_lines = 6 * len(wall["openings"])
        assert len(recorded) == expected_lines, (
            f"{wall['id']}: {len(recorded)} lines != expected {expected_lines}")
        assert len(truth) == len(wall["openings"]), "truth entry count"
        for e in truth:
            assert {"id", "wall_id", "span_along_axis", "type"} <= set(e)
            assert e["wall_id"] == wall["id"]
        for arc in arcs:
            assert arc["arc"]["layer"] == "DOOR", "swing arc must be on DOOR"
            assert arc["arc"]["r"] > 0.0
        n_doors = sum(1 for o in wall["openings"] if o["type"] == "door")
        assert len(arcs) == n_doors, "one swing arc per door"
        total_lines += len(recorded)
        total_arcs += len(arcs)
        print(f"  {wall['id']}: lines={len(recorded)} truth={len(truth)} "
              f"arcs={len(arcs)} -> gap-cross check OK")
    print(f"gap-math: {checked_walls} wall(s) rendered, {total_lines} lines, "
          f"{total_arcs} door arc(s), no line crosses a gap -> OK")

    # --- forced door+window on one wall: exercise both types + multi-split -- #
    print("-- forced 2-opening wall (door + window) --")
    forced = {
        "id": "wf", "axis": [[0.0, 0.0], [8000.0, 0.0]],
        "thickness": 200.0, "layer": "WALL",
        "openings": [
            {"id": "d1", "wall_id": "wf", "span_along_axis": [0.20, 0.31],
             "type": "door"},
            {"id": "g1", "wall_id": "wf", "span_along_axis": [0.60, 0.75],
             "type": "window"},
        ],
    }
    frec = []

    def frec_fn(start, end, layer="OPENING", meta=""):
        frec.append((tuple(start), tuple(end), layer))
        return f"fh{len(frec)}"

    fentries = opening_renderer(forced, frec_fn)
    _assert_no_line_crosses_gaps(frec, forced)
    farcs = [e for e in fentries if "arc" in e]
    # 2 openings -> 3 face pieces/face * 2 faces + 4 jamb ticks == 10 lines.
    assert len(frec) == 10, f"forced wall lines {len(frec)} != 10"
    assert len(farcs) == 1, "exactly one door arc expected"
    print(f"  forced wall: lines={len(frec)} arcs={len(farcs)} "
          f"(door+window, gap-cross check OK)")

    # --- build a real R2018 ASCII DXF to the OS temp dir -------------------- #
    tmpdir = tempfile.mkdtemp(prefix="e2_s2c_")
    dxf_path = os.path.join(tmpdir, "e2_s2c_openings.dxf")
    print(f"tmp dxf: {dxf_path}")

    doc = ezdxf.new("R2018")
    for ly in ("WALL", "DOOR"):
        if ly not in doc.layers:
            doc.layers.add(ly)
    msp = doc.modelspace()

    def draw_line(start, end, layer="OPENING", meta=""):
        return msp.add_line(start, end, dxfattribs={"layer": layer}).dxf.handle

    dxf_lines = 0
    dxf_arcs = 0
    for wall in _walls_with_openings(assigned):
        for entry in opening_renderer(wall, draw_line):
            arc = entry.get("arc") if isinstance(entry, dict) else None
            if arc:
                msp.add_arc(arc["center"], arc["r"], arc["start"], arc["end"],
                            dxfattribs={"layer": arc["layer"]})
                dxf_arcs += 1
        # count lines drawn is implicit; recount from modelspace below
    dxf_lines = len(msp.query("LINE"))
    dxf_arcs = len(msp.query("ARC"))
    doc.saveas(dxf_path)

    reopened = ezdxf.readfile(dxf_path)
    r2018 = ezdxf.const.acad_release_to_dxf_version["R2018"]
    assert reopened.dxfversion == r2018, \
        f"expected R2018 ({r2018}), got {reopened.dxfversion}"
    n_line = len(reopened.modelspace().query("LINE"))
    n_arc = len(reopened.modelspace().query("ARC"))
    assert n_line == dxf_lines and n_line > 0, "LINEs missing in saved DXF"
    assert n_arc == dxf_arcs, "ARCs missing in saved DXF"
    print(f"dxf: version={reopened.dxfversion} (R2018) "
          f"lines={n_line} arcs={n_arc} -> OK")

    print("SELFTEST PASS")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="E2 S2-C synthetic openings (assign + renderer)")
    parser.add_argument("--selftest", action="store_true",
                        help="fabricate a WallPlan, assign + render, and verify")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
