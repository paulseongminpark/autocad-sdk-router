#!/usr/bin/env python3
"""evidence_grid.py -- multi-evidence wall scoring over SEGMENT-IR v1 (CARD S4-D).

Consumes a SEG-IR dict (see contract below) and scores every segment on FOUR
independent evidence channels, each reported SEPARATELY (never collapsed silently):

  - parallel  : a near-parallel partner segment exists (angle tol `angle_tol_deg`,
                default 2 deg) whose lateral offset falls inside the thickness band
                AND whose longitudinal overlap ratio is >= `overlap_min` (default 0.5).
                The channel value is that best partner's overlap ratio (0..1).
  - thickness : the lateral offset to the best near-parallel neighbour falls inside a
                plausible wall band.  Default band 50..400 in DRAWING UNITS when scale
                is unknown; when `scale_mm_per_unit` is known the band is interpreted
                in mm (50..400 mm) and converted to units.  Graded membership 0..1.
  - junction  : segment endpoints meet other wall-candidate segments at L / T / X
                within `snap_tol` (default 6.0 units).  Saturating count -> 0..1.
  - layer     : layer name contains a wall-ish token (WALL, WA, BEARING, 벽).
                Kept SEPARATE so name-blind scoring is possible: params={"use_layer":False}
                zeroes this channel AND drops it from the weighted mean.

Aggregate score = weighted mean of the four channels.  Default weights:
    parallel 0.35, thickness 0.25, junction 0.20, layer 0.20
(override via params={"weights":{...}}).  When use_layer is False the layer weight is
removed and the remaining weights are renormalised, so the aggregate stays comparable.

SEGMENT-IR v1 (shared contract -- exact keys, version field required):
  {"ir":"seg.v1","drawing_id":"str","units":"mm|unknown","scale_mm_per_unit":null,
   "segments":[{"sid":"s0001","handle":"8B52 or null","pts":[[x1,y1],[x2,y2]],
                "layer":"str","kind":"line|poly-edge|arc-chord",
                "label":"wall|opening|other|unknown",
                "source":"native|synth|floorplancad|cubicasa"}]}

Public API (S4 wiring contract -- modules must NOT import each other):
  score(seg_ir, params=None) -> {
    "per_handle": {key: {"score": 0..1,
                         "evidence": {"parallel":x,"thickness":x,"junction":x,"layer":x}}},
    "walls": [{"handles":[...], "axis":[[x,y],[x,y]], "thickness":t}]
  }
`key` is the segment handle when present, otherwise the sid (documented fallback so
null-handle segments are never silently dropped).

Pure Python stdlib.  Run `python evidence_grid.py --selftest` for the self-test.
"""
from __future__ import annotations

import argparse
import json
import math
import sys

# ---------------------------------------------------------------------------
# Defaults (documented; all overridable via params)
# ---------------------------------------------------------------------------
DEFAULTS = {
    "angle_tol_deg": 2.0,        # near-parallel angular tolerance
    "overlap_min": 0.5,          # min longitudinal overlap ratio for a parallel partner
    "thickness_band_mm": (50.0, 400.0),  # plausible wall thickness in mm
    "snap_tol": 6.0,             # junction snap tolerance in drawing units
    "use_layer": True,
    "weights": {"parallel": 0.35, "thickness": 0.25, "junction": 0.20, "layer": 0.20},
}
WALL_LAYER_TOKENS = ("WALL", "WA", "BEARING", "벽")  # 벽 == 벽


# ---------------------------------------------------------------------------
# Geometry helpers (2D)
# ---------------------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _length(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def _unit(p1, p2):
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    n = math.hypot(dx, dy)
    if n == 0.0:
        return (0.0, 0.0), 0.0
    return (dx / n, dy / n), n


def _seg_angle_deg(p1, p2):
    """Undirected angle in [0,180)."""
    ang = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0])) % 180.0
    return ang


def _angle_diff_deg(a, b):
    """Smallest undirected difference between two [0,180) angles."""
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def _foot_on_line(pt, a, u):
    """Foot of perpendicular from pt onto the line through `a` with unit dir `u`."""
    ap = _sub(pt, a)
    t = ap[0] * u[0] + ap[1] * u[1]
    return (a[0] + t * u[0], a[1] + t * u[1])


def _perp_distance(pt, a, u):
    f = _foot_on_line(pt, a, u)
    return _length(pt, f)


def _project_scalar(pt, origin, u):
    ap = _sub(pt, origin)
    return ap[0] * u[0] + ap[1] * u[1]


def _longitudinal_overlap_ratio(s, t):
    """Overlap of t projected onto s's direction, as a fraction of the SHORTER segment."""
    u, ls = _unit(s[0], s[1])
    _, lt = _unit(t[0], t[1])
    if ls == 0.0 or lt == 0.0:
        return 0.0
    origin = s[0]
    ts = sorted((_project_scalar(s[0], origin, u), _project_scalar(s[1], origin, u)))
    tt = sorted((_project_scalar(t[0], origin, u), _project_scalar(t[1], origin, u)))
    overlap = max(0.0, min(ts[1], tt[1]) - max(ts[0], tt[0]))
    denom = min(ls, lt)
    return overlap / denom if denom > 0 else 0.0


def _lateral_offset(s, t):
    """Perpendicular distance from t's midpoint to s's infinite line."""
    u, ls = _unit(s[0], s[1])
    if ls == 0.0:
        return float("inf")
    mid_t = ((t[0][0] + t[1][0]) / 2.0, (t[0][1] + t[1][1]) / 2.0)
    return _perp_distance(mid_t, s[0], u)


def _proper_intersection(s, t, eps=1e-9):
    """True if segments s and t cross in their strict interiors (an X junction)."""
    p, r = s[0], _sub(s[1], s[0])
    q, w = t[0], _sub(t[1], t[0])
    rxs = r[0] * w[1] - r[1] * w[0]
    if abs(rxs) < eps:
        return False  # parallel or collinear -> not a proper X crossing
    qp = _sub(q, p)
    a = (qp[0] * w[1] - qp[1] * w[0]) / rxs   # param along s
    b = (qp[0] * r[1] - qp[1] * r[0]) / rxs   # param along t
    return eps < a < 1.0 - eps and eps < b < 1.0 - eps


# ---------------------------------------------------------------------------
# Channel scoring
# ---------------------------------------------------------------------------
def _band_membership(d, lo, hi):
    """1.0 inside [lo,hi]; linear falloff to 0 over a margin of half the band width."""
    if lo <= d <= hi:
        return 1.0
    margin = max(1e-9, 0.5 * (hi - lo))
    if d < lo:
        return max(0.0, 1.0 - (lo - d) / margin)
    return max(0.0, 1.0 - (d - hi) / margin)


def _layer_is_wallish(layer):
    if not layer:
        return False
    up = layer.upper()
    for tok in WALL_LAYER_TOKENS:
        t = tok.upper()
        if t in up:
            return True
    return False


def _resolve_params(seg_ir, params):
    p = dict(DEFAULTS)
    if params:
        p.update({k: v for k, v in params.items() if k != "weights"})
        if "weights" in params and params["weights"]:
            w = dict(DEFAULTS["weights"])
            w.update(params["weights"])
            p["weights"] = w
    # Resolve thickness band into DRAWING UNITS.
    scale = None
    if params and params.get("scale_mm_per_unit") is not None:
        scale = params.get("scale_mm_per_unit")
    elif seg_ir.get("scale_mm_per_unit") is not None:
        scale = seg_ir.get("scale_mm_per_unit")
    if params and params.get("thickness_band_units") is not None:
        lo, hi = params["thickness_band_units"]
    else:
        lo_mm, hi_mm = p["thickness_band_mm"]
        if scale:  # mm per unit -> units = mm / (mm/unit)
            lo, hi = lo_mm / scale, hi_mm / scale
        else:
            lo, hi = lo_mm, hi_mm  # scale unknown: band is in drawing units directly
    p["_band_units"] = (float(lo), float(hi))
    p["_scale"] = scale
    return p


def score(seg_ir, params=None):
    """Score every segment on the four evidence channels.  See module docstring."""
    p = _resolve_params(seg_ir, params)
    lo, hi = p["_band_units"]
    angle_tol = p["angle_tol_deg"]
    overlap_min = p["overlap_min"]
    snap = p["snap_tol"]
    use_layer = bool(p["use_layer"])
    weights = dict(p["weights"])
    if not use_layer:
        weights["layer"] = 0.0

    segs = seg_ir.get("segments", []) or []
    # Normalise into a working list of records.
    recs = []
    for s in segs:
        pts = s.get("pts") or []
        if len(pts) < 2:
            continue
        p1 = (float(pts[0][0]), float(pts[0][1]))
        p2 = (float(pts[-1][0]), float(pts[-1][1]))
        if _length(p1, p2) == 0.0:
            continue
        key = s.get("handle") or s.get("sid")
        recs.append({
            "key": key,
            "sid": s.get("sid"),
            "handle": s.get("handle"),
            "p1": p1, "p2": p2,
            "layer": s.get("layer") or "",
            "kind": s.get("kind"),
            "geom": (p1, p2),
            "angle": _seg_angle_deg(p1, p2),
        })

    n = len(recs)
    per_handle = {}
    walls = []
    seen_pairs = set()

    for i in range(n):
        a = recs[i]
        best_parallel = None       # (overlap, offset, j) valid wall partner
        best_thick_off = None      # offset of nearest near-parallel neighbour (for thickness)
        junction_partners = set()

        for j in range(n):
            if i == j:
                continue
            b = recs[j]
            near_parallel = _angle_diff_deg(a["angle"], b["angle"]) <= angle_tol
            if near_parallel:
                ov = _longitudinal_overlap_ratio(a["geom"], b["geom"])
                if ov > 0.0:
                    off = _lateral_offset(a["geom"], b["geom"])
                    # thickness: track the plausible-wall-gap neighbour (prefer overlap>=min,
                    # then smallest offset) so the channel is independent of parallel's gate.
                    cand = (0 if ov >= overlap_min else 1, off)
                    if best_thick_off is None or cand < best_thick_off[0]:
                        best_thick_off = (cand, off)
                    # parallel: requires offset in band AND overlap >= min.
                    if ov >= overlap_min and lo <= off <= hi:
                        if best_parallel is None or ov > best_parallel[0]:
                            best_parallel = (ov, off, j)
            # junction: L/T (endpoint contacts) or X (interior crossing).
            if _segments_junction(a["geom"], b["geom"], snap):
                junction_partners.add(j)

        parallel_score = best_parallel[0] if best_parallel else 0.0
        thickness_score = _band_membership(best_thick_off[1], lo, hi) if best_thick_off else 0.0
        junction_score = min(1.0, len(junction_partners) / 2.0)
        layer_score = 1.0 if (use_layer and _layer_is_wallish(a["layer"])) else 0.0

        channels = {
            "parallel": round(parallel_score, 6),
            "thickness": round(thickness_score, 6),
            "junction": round(junction_score, 6),
            "layer": round(layer_score, 6),
        }
        wsum = sum(w for w in weights.values() if w > 0)
        if wsum <= 0:
            agg = 0.0
        else:
            agg = sum(weights[c] * channels[c] for c in channels) / wsum
        per_handle[a["key"]] = {"score": round(agg, 6), "evidence": channels}

        # Emit a wall record for each unique valid parallel pair.
        if best_parallel is not None:
            j = best_parallel[2]
            pair = frozenset((a["key"], recs[j]["key"]))
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                walls.append(_wall_record(a, recs[j], best_parallel[1]))

    return {"per_handle": per_handle, "walls": walls}


def _segments_junction(s, t, snap):
    """L/T/X junction test between two segments within snap tolerance."""
    # X: proper interior crossing.
    if _proper_intersection(s, t):
        return True
    # L: endpoint-to-endpoint contact.
    for pa in s:
        for pb in t:
            if _length(pa, pb) <= snap:
                return True
    # T: an endpoint of one lies on the body (interior) of the other.
    for endpoints, body in ((s, t), (t, s)):
        u, ln = _unit(body[0], body[1])
        if ln == 0.0:
            continue
        for pt in endpoints:
            proj = _project_scalar(pt, body[0], u)
            if snap < proj < ln - snap and _perp_distance(pt, body[0], u) <= snap:
                return True
    return False


def _wall_record(a, b, offset):
    """Centre-line axis between segment a and its partner b, plus thickness=offset."""
    u, _ = _unit(a["p1"], a["p2"])
    fa = _foot_on_line(a["p1"], b["p1"], _unit(b["p1"], b["p2"])[0])
    fb = _foot_on_line(a["p2"], b["p1"], _unit(b["p1"], b["p2"])[0])
    axis = [
        [round((a["p1"][0] + fa[0]) / 2.0, 6), round((a["p1"][1] + fa[1]) / 2.0, 6)],
        [round((a["p2"][0] + fb[0]) / 2.0, 6), round((a["p2"][1] + fb[1]) / 2.0, 6)],
    ]
    return {"handles": sorted([a["key"], b["key"]]), "axis": axis, "thickness": round(offset, 6)}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
def _build_fixture():
    """Hand-built SEG-IR: 2 parallel wall pairs + 1 lone line + 1 door arc-chord."""
    segments = [
        # Wall pair A (horizontal, offset 200 units, in band). Layer "WALL".
        {"sid": "s0001", "handle": "A1", "pts": [[0, 0], [1200, 0]],
         "layer": "WALL", "kind": "line", "label": "wall", "source": "synth"},
        {"sid": "s0002", "handle": "A2", "pts": [[0, 200], [1200, 200]],
         "layer": "WALL", "kind": "line", "label": "wall", "source": "synth"},
        # Wall pair B (vertical, offset 150 units, in band). Layer "A-WALL".
        {"sid": "s0003", "handle": "B1", "pts": [[1000, 0], [1000, 800]],
         "layer": "A-WALL", "kind": "poly-edge", "label": "wall", "source": "synth"},
        {"sid": "s0004", "handle": "B2", "pts": [[1150, 0], [1150, 800]],
         "layer": "A-WALL", "kind": "poly-edge", "label": "wall", "source": "synth"},
        # Lone diagonal line, isolated, non-wall layer.
        {"sid": "s0005", "handle": "L1", "pts": [[0, -800], [400, -500]],
         "layer": "DIMENSIONS", "kind": "line", "label": "other", "source": "synth"},
        # Door arc-chord, isolated diagonal, non-wall layer.
        {"sid": "s0006", "handle": "D1", "pts": [[600, -400], [800, -200]],
         "layer": "A-DOOR", "kind": "arc-chord", "label": "opening", "source": "synth"},
    ]
    return {"ir": "seg.v1", "drawing_id": "selftest-fixture", "units": "unknown",
            "scale_mm_per_unit": None, "segments": segments}


def _selftest():
    ok = True

    def check(cond, msg):
        nonlocal ok
        status = "PASS" if cond else "FAIL"
        if not cond:
            ok = False
        print(f"  [{status}] {msg}")
        return cond

    ir = _build_fixture()
    res = score(ir)
    ph = res["per_handle"]

    print("--- per-handle scores (default params) ---")
    for k in ("A1", "A2", "B1", "B2", "L1", "D1"):
        e = ph[k]["evidence"]
        print(f"  {k}: score={ph[k]['score']:.3f}  "
              f"parallel={e['parallel']:.2f} thickness={e['thickness']:.2f} "
              f"junction={e['junction']:.2f} layer={e['layer']:.2f}")

    walls = ["A1", "A2", "B1", "B2"]
    nonwalls = ["L1", "D1"]
    wall_scores = [ph[k]["score"] for k in walls]
    nonwall_scores = [ph[k]["score"] for k in nonwalls]

    print("--- ranking assertions ---")
    check(min(wall_scores) > max(nonwall_scores),
          f"every wall ({min(wall_scores):.3f}) outranks every non-wall ({max(nonwall_scores):.3f})")
    for k in walls:
        check(ph[k]["evidence"]["parallel"] >= 0.5, f"{k} has a parallel partner (parallel>=0.5)")
        check(ph[k]["evidence"]["thickness"] >= 0.9, f"{k} thickness in band (>=0.9)")
    for k in nonwalls:
        check(ph[k]["evidence"]["parallel"] == 0.0, f"{k} has NO parallel partner (parallel==0)")

    print("--- walls output ---")
    for w in res["walls"]:
        print(f"  handles={w['handles']} thickness={w['thickness']} axis={w['axis']}")
    pair_sets = {frozenset(w["handles"]) for w in res["walls"]}
    check(frozenset(["A1", "A2"]) in pair_sets, "wall pair {A1,A2} detected")
    check(frozenset(["B1", "B2"]) in pair_sets, "wall pair {B1,B2} detected")
    check(len(res["walls"]) == 2, f"exactly 2 wall pairs detected (got {len(res['walls'])})")
    # thickness values recovered from geometry.
    tA = next(w["thickness"] for w in res["walls"] if frozenset(w["handles"]) == frozenset(["A1", "A2"]))
    tB = next(w["thickness"] for w in res["walls"] if frozenset(w["handles"]) == frozenset(["B1", "B2"]))
    check(abs(tA - 200.0) < 1e-6, f"pair A thickness == 200 (got {tA})")
    check(abs(tB - 150.0) < 1e-6, f"pair B thickness == 150 (got {tB})")

    print("--- name-blind (use_layer=False) ---")
    res_nb = score(ir, params={"use_layer": False})
    phn = res_nb["per_handle"]
    for k in walls + nonwalls:
        check(phn[k]["evidence"]["layer"] == 0.0, f"{k} layer channel zeroed")
    wall_nb = [phn[k]["score"] for k in walls]
    nonwall_nb = [phn[k]["score"] for k in nonwalls]
    check(min(wall_nb) > max(nonwall_nb),
          f"name-blind: walls ({min(wall_nb):.3f}) still outrank non-walls ({max(nonwall_nb):.3f})")

    print("--- separate channels never collapsed ---")
    for k in walls + nonwalls:
        check(set(ph[k]["evidence"].keys()) == {"parallel", "thickness", "junction", "layer"},
              f"{k} reports all four channels separately")

    print("--- scale awareness ---")
    # units=mm, scale 1.0 mm/unit -> band stays 50..400 units -> identical ranking.
    ir_scaled = dict(ir); ir_scaled["units"] = "mm"; ir_scaled["scale_mm_per_unit"] = 1.0
    res_sc = score(ir_scaled)
    check(res_sc["per_handle"]["A1"]["evidence"]["thickness"] >= 0.9,
          "scale_mm_per_unit=1.0 -> A1 still in band")
    # Tiny band [1,10] units -> wall offsets 200/150 fall out of band -> parallel drops to 0.
    res_tiny = score(ir, params={"thickness_band_units": [1.0, 10.0]})
    check(res_tiny["per_handle"]["A1"]["evidence"]["parallel"] == 0.0,
          "tiny band [1,10] -> A1 parallel drops to 0 (offset out of band)")

    print()
    print("SELFTEST RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Multi-evidence wall scoring over SEG-IR v1.")
    ap.add_argument("--selftest", action="store_true", help="run the built-in self-test")
    ap.add_argument("--in", dest="infile", help="score a SEG-IR json file and print result")
    ap.add_argument("--params", help="JSON string of params overrides", default=None)
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if args.infile:
        with open(args.infile, "r", encoding="utf-8") as fh:
            seg_ir = json.load(fh)
        params = json.loads(args.params) if args.params else None
        print(json.dumps(score(seg_ir, params), ensure_ascii=False, indent=2))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
