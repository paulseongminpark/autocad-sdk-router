#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dissect the HATCH ``loops`` residue: notation-vs-geometry classification.

After LEX-0008 (R4r remeasure, reports/interior100/R4r_remeasure_lex0008.json)
the interior diff sits at 26,893/27,130 with 237 residual entities. Recon on
def X-...$0$111a showed the nearest residual pairs differ in exactly ONE
canonical geometry key: ``loops`` -- the hatch boundary. A boundary loop is a
closed CYCLE of edges, and the same geometric cycle admits many notations:

  * rotation  -- which edge the serialization starts at
  * direction -- traversal order (line start/end swapped, arc angles swapped
                 + ccw flipped, spline control/knots reversed)
  * loop order -- the loops[] list order inside one hatch (plus the per-loop
                 ``index`` field, which is pure ordering provenance)

This tool measures, pair by pair, whether the residue is notation (same point
set, different cycle notation) or geometry (different point set):

  1. reproduce the R4r pairing EXACTLY (monkey-patch cad_diff.classify_change
     to capture tier-2 modified pairs while blockdef_diff runs unchanged) and
     assert per-def counts match the R4r report -- population control
     (LEX-0006);
  2. classify each modified pair by its changed canonical fields
     (loops-only / loops+other / non-loops);
  3. for loops-only pairs, measure point-cloud equivalence (dense edge
     sampling, symmetric max nearest-neighbour distance) -- the substitute
     verifier that separates notation from geometry;
  4. apply the CANDIDATE canonical form (rotation x direction minimal
     serialization per loop, loops sorted, index dropped) and count which
     pairs fold;
  5. collision test: canonicalize EVERY census-side hatch loop and verify no
     two point-cloud-distinct loops share a canonical form (the quotient must
     not make the measurer blind);
  6. optional --dryrun: run the FULL blockdef_diff with the candidate
     canonicalization patched in -- the exact preregistration number for the
     legislated remeasure (same code path, deterministic).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import blockdef_diff
import cad_diff

SCHEMA_ID = "ariadne.loops_residue_analysis.v1"
_INPUT_ENCODING = "utf-8-sig"

_R4R_RUN = r"D:\dev\99_tools\autocad-sdk-router\runs\e2e_1dwg_R4r_assoc_20260710"
DEFAULT_CENSUS_IR = _R4R_RUN + r"\census\dwg_graph_ir.json"
DEFAULT_POST_IR = _R4R_RUN + r"\regen\post\dwg_graph_ir.json"
DEFAULT_INTERIOR_DIFF = (
    r"D:\dev\99_tools\autocad-sdk-router\reports\interior100"
    r"\R4r_remeasure_lex0008.json"
)
DEFAULT_OUT_JSON = r"reports\interior100\loops_residue_analysis_R4s.json"
DEFAULT_OUT_MD = r"reports\interior100\loops_residue_analysis_R4s.md"
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)

_ROUND = 6   # value grid of the emitted canonical form (house convention:
             # same 6dp as _canonical_hatch_geometry's _q / pattern_phase)
_COARSE = 3  # rotation/direction/order SELECTION grid: the representative
             # choice must be stable under sub-tolerance (1e-6) jitter, so it
             # is made on a 1e-3 grid first (1e-6 straddle needs a value
             # within 1e-6 of a 1e-3 boundary at the decisive position) and
             # only tie-broken on the fine grid.
_GEOM_EQ_TOL = 1e-3   # mm; point-cloud equality threshold (far above the
                      # measured serialization noise ~1e-9, far below any
                      # real boundary difference)
_SAMPLES_PER_EDGE = 24


# --------------------------------------------------------------------------- #
# small utils
# --------------------------------------------------------------------------- #

def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding=_INPUT_ENCODING) as fh:
        return json.load(fh)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _round_tree(value: Any, nd: int) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        r = round(float(value), nd)
        return 0.0 if r == 0 else r
    if isinstance(value, list):
        return [_round_tree(v, nd) for v in value]
    if isinstance(value, tuple):
        return [_round_tree(v, nd) for v in value]
    if isinstance(value, dict):
        return {k: _round_tree(v, nd) for k, v in value.items()}
    return value


def _ser(value: Any, nd: int) -> str:
    return json.dumps(_round_tree(value, nd), sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False)


# --------------------------------------------------------------------------- #
# candidate canonical form (rotation x direction x order quotient)
# --------------------------------------------------------------------------- #

def _seg_from_edge(edge: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    t = str(edge.get("type") or "?")
    if t == "line":
        return ("line", {"start": edge.get("start"), "end": edge.get("end")})
    if t == "arc":
        return ("arc", {k: edge.get(k) for k in
                        ("center", "radius", "start_angle", "end_angle", "ccw")})
    if t == "spline":
        return ("spline", {k: edge.get(k) for k in
                           ("degree", "rational", "control", "knots", "weights")})
    return (t, {k: v for k, v in edge.items() if k != "type"})


def _rev_seg(seg: Tuple[str, Dict[str, Any]]) -> Optional[Tuple[str, Dict[str, Any]]]:
    t, d = seg
    if t == "line":
        return ("line", {"start": d.get("end"), "end": d.get("start")})
    if t == "arc":
        e = dict(d)
        e["start_angle"], e["end_angle"] = d.get("end_angle"), d.get("start_angle")
        ccw = d.get("ccw")
        e["ccw"] = (not ccw) if isinstance(ccw, bool) else ccw
        return ("arc", e)
    if t == "spline":
        e = dict(d)
        ctrl = d.get("control")
        wts = d.get("weights")
        knots = d.get("knots")
        if isinstance(ctrl, list):
            e["control"] = list(reversed(ctrl))
        if isinstance(wts, list):
            e["weights"] = list(reversed(wts))
        if (isinstance(knots, list) and knots
                and all(isinstance(k, (int, float)) for k in knots)):
            lo, hi = float(knots[0]), float(knots[-1])
            e["knots"] = [lo + hi - float(k) for k in reversed(knots)]
        return ("spline", e)
    return None  # unknown edge type: not reversible


def _poly_reversed(verts: List[Any]) -> List[Any]:
    """Reverse a polyline vertex loop, keeping bulges on their segments.

    Vertices are [x, y] or [x, y, bulge]; bulge at index i belongs to the
    segment v[i] -> v[(i+1) % n]. In the reversed traversal that segment is
    walked backwards, so its bulge lands negated on the reversed segment's
    start vertex: bulge'[k] = -bulge[(n-2-k) % n].
    """
    n = len(verts)
    rev = [list(v) if isinstance(v, list) else v for v in reversed(verts)]
    if n and all(isinstance(v, list) and len(v) >= 3 for v in verts):
        bulges = [float(v[2]) for v in verts]
        for k in range(n):
            src = (n - 2 - k) % n
            rev[k][2] = -bulges[src] if bulges[src] != 0 else 0.0
    return rev


def _rotations(seq: List[Any], closed: bool) -> List[List[Any]]:
    if not closed or len(seq) <= 1:
        return [list(seq)]
    return [seq[i:] + seq[:i] for i in range(len(seq))]


def _min_by_ser(cands: List[Any]) -> Any:
    return min(cands, key=lambda c: (_ser(c, _COARSE), _ser(c, _ROUND)))


def canonical_loop(loop: Dict[str, Any]) -> Dict[str, Any]:
    """Rotation/direction/order-invariant representative of one loop.

    Emits the loop with ``edges``/``vertices`` replaced by the minimal
    (coarse-grid-first) serialization among all valid rotations x directions,
    values rounded to the 6dp house grid, and drops ``index`` (list-order
    provenance, meaningless once loops[] is sorted).
    """
    keep = {k: loop[k] for k in loop if k not in ("edges", "vertices", "index")}
    closed = bool(loop.get("closed"))
    edges = loop.get("edges")
    verts = loop.get("vertices")
    if isinstance(edges, list) and edges:
        segs = [_seg_from_edge(e) for e in edges if isinstance(e, dict)]
        cands: List[List[Any]] = list(_rotations(segs, closed))
        rev = [_rev_seg(s) for s in reversed(segs)]
        if all(r is not None for r in rev):
            cands.extend(_rotations(rev, closed))
        keep["segments"] = _round_tree(_min_by_ser(cands), _ROUND)
    elif isinstance(verts, list) and verts:
        cands = list(_rotations(list(verts), closed))
        cands.extend(_rotations(_poly_reversed(verts), closed))
        keep["poly_vertices"] = _round_tree(_min_by_ser(cands), _ROUND)
    return keep


def canonical_loops_field(loops: List[Any]) -> List[Any]:
    canon = [canonical_loop(lp) if isinstance(lp, dict) else lp for lp in loops]
    canon.sort(key=lambda c: (_ser(c, _COARSE), _ser(c, _ROUND)))
    return canon


def apply_loop_canon_to_geometry(g: Dict[str, Any]) -> Dict[str, Any]:
    loops = g.get("loops")
    if not (isinstance(loops, list) and loops):
        return g
    g2 = dict(g)
    g2["loops"] = canonical_loops_field(loops)
    return g2


# --------------------------------------------------------------------------- #
# point-cloud equivalence (substitute verifier)
# --------------------------------------------------------------------------- #

def _sample_edge(edge: Dict[str, Any], out: List[Tuple[float, float]]) -> Optional[str]:
    """Append dense samples of one edge; returns a note for unsampleable ones."""
    t = edge.get("type")
    if t == "line":
        s, e = edge.get("start"), edge.get("end")
        if not (isinstance(s, list) and isinstance(e, list)):
            return "line-missing-endpoint"
        for i in range(_SAMPLES_PER_EDGE + 1):
            u = i / _SAMPLES_PER_EDGE
            out.append((s[0] + (e[0] - s[0]) * u, s[1] + (e[1] - s[1]) * u))
        return None
    if t == "arc":
        c = edge.get("center")
        try:
            r = float(edge.get("radius"))
            a0 = float(edge.get("start_angle"))
            a1 = float(edge.get("end_angle"))
        except (TypeError, ValueError):
            return "arc-missing-params"
        if not isinstance(c, list):
            return "arc-missing-center"
        ccw = edge.get("ccw", True)
        sweep = a1 - a0
        if ccw and sweep < 0:
            sweep += 2 * math.pi
        if (not ccw) and sweep > 0:
            sweep -= 2 * math.pi
        for i in range(_SAMPLES_PER_EDGE + 1):
            a = a0 + sweep * i / _SAMPLES_PER_EDGE
            out.append((c[0] + r * math.cos(a), c[1] + r * math.sin(a)))
        return None
    if t == "spline":
        # control polygon as identity proxy: same degree/knots/weights and
        # same (or reversed) control net define the same curve; the canonical
        # fold compares those exactly, so sampling the control net is enough
        # to catch a REAL geometry difference here.
        for p in edge.get("control") or []:
            if isinstance(p, list) and len(p) >= 2:
                out.append((float(p[0]), float(p[1])))
        return "spline-control-proxy"
    return "unknown-edge-%s" % t


def _bulge_arc_points(p0: List[float], p1: List[float], bulge: float,
                      out: List[Tuple[float, float]]) -> None:
    theta = 4.0 * math.atan(bulge)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    chord = math.hypot(dx, dy)
    if chord == 0 or theta == 0:
        out.append((p0[0], p0[1]))
        out.append((p1[0], p1[1]))
        return
    mx, my = (p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0
    h = (chord / 2.0) / math.tan(theta / 2.0)
    nx, ny = -dy / chord, dx / chord  # left normal
    cx, cy = mx + nx * h, my + ny * h
    a0 = math.atan2(p0[1] - cy, p0[0] - cx)
    for i in range(_SAMPLES_PER_EDGE + 1):
        a = a0 + theta * i / _SAMPLES_PER_EDGE
        rr = math.hypot(p0[0] - cx, p0[1] - cy)
        out.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))


def sample_loop_points(loop: Dict[str, Any]) -> Tuple[List[Tuple[float, float]], List[str]]:
    pts: List[Tuple[float, float]] = []
    notes: List[str] = []
    edges = loop.get("edges")
    if isinstance(edges, list) and edges:
        for ed in edges:
            if isinstance(ed, dict):
                note = _sample_edge(ed, pts)
                if note:
                    notes.append(note)
    verts = loop.get("vertices")
    if isinstance(verts, list) and verts:
        n = len(verts)
        seg_count = n if loop.get("closed") else n - 1
        for i in range(max(seg_count, 0)):
            v0 = verts[i]
            v1 = verts[(i + 1) % n]
            if not (isinstance(v0, list) and isinstance(v1, list)):
                notes.append("poly-nonlist-vertex")
                continue
            b = float(v0[2]) if len(v0) >= 3 else 0.0
            if b:
                _bulge_arc_points(v0, v1, b, pts)
            else:
                for j in range(_SAMPLES_PER_EDGE + 1):
                    u = j / _SAMPLES_PER_EDGE
                    pts.append((v0[0] + (v1[0] - v0[0]) * u,
                                v0[1] + (v1[1] - v0[1]) * u))
    return pts, notes


def _max_nn_distance(a: List[Tuple[float, float]], b: List[Tuple[float, float]]) -> float:
    worst = 0.0
    for (ax, ay) in a:
        best = math.inf
        for (bx, by) in b:
            d = (ax - bx) * (ax - bx) + (ay - by) * (ay - by)
            if d < best:
                best = d
                if best == 0.0:
                    break
        worst = max(worst, best)
    return math.sqrt(worst)


def hatch_pointcloud_distance(g_a: Dict[str, Any], g_b: Dict[str, Any]
                              ) -> Tuple[float, List[str]]:
    pts_a: List[Tuple[float, float]] = []
    pts_b: List[Tuple[float, float]] = []
    notes: List[str] = []
    for lp in g_a.get("loops") or []:
        if isinstance(lp, dict):
            p, n = sample_loop_points(lp)
            pts_a.extend(p)
            notes.extend(n)
    for lp in g_b.get("loops") or []:
        if isinstance(lp, dict):
            p, n = sample_loop_points(lp)
            pts_b.extend(p)
            notes.extend(n)
    if not pts_a or not pts_b:
        return math.inf, notes + ["empty-side"]
    d = max(_max_nn_distance(pts_a, pts_b), _max_nn_distance(pts_b, pts_a))
    return d, sorted(set(notes))


# --------------------------------------------------------------------------- #
# pairing reproduction (capture tier-2 modified pairs from cad_diff itself)
# --------------------------------------------------------------------------- #

class _PairCapture:
    """Monkey-patch cad_diff.classify_change to record tier-2 pairs.

    classify_change is called exactly once per tier-2 (dxf_name, layer) zip
    pair inside _compute_diff_geometry_basis; wrapping it captures the very
    pairs the measurement classifies, with zero pairing re-implementation.
    """

    def __init__(self) -> None:
        self.pairs: List[Tuple[Dict[str, Any], Dict[str, Any], List[str]]] = []
        self._orig = None

    def __enter__(self) -> "_PairCapture":
        self._orig = cad_diff.classify_change

        def _capture(pre_e: Dict[str, Any], post_e: Dict[str, Any]):
            fields = self._orig(pre_e, post_e)
            if fields:
                self.pairs.append((pre_e, post_e, list(fields)))
            return fields

        cad_diff.classify_change = _capture
        return self

    def __exit__(self, *exc: Any) -> None:
        cad_diff.classify_change = self._orig


def _load_name_map(report: Dict[str, Any]) -> Dict[str, str]:
    name_map: Dict[str, str] = {}
    for row in report.get("per_def") or []:
        if isinstance(row, dict):
            name = row.get("name")
            b_name = row.get("b_name")
            if isinstance(name, str) and isinstance(b_name, str):
                name_map[name] = b_name
    return name_map


def _dirty_rows(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for row in report.get("per_def") or []:
        if not isinstance(row, dict):
            continue
        if (int(row.get("modified", 0) or 0) or int(row.get("removed", 0) or 0)
                or int(row.get("added", 0) or 0)):
            rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
# analysis
# --------------------------------------------------------------------------- #

def _geometry_key_delta(g_a: Dict[str, Any], g_b: Dict[str, Any]) -> List[str]:
    profile = {"length": 1e-6}
    keys = sorted(set(g_a) | set(g_b))
    out = []
    for k in keys:
        if not cad_diff._geometry_within_tolerance(
                g_a.get(k), g_b.get(k), profile, cad_diff._quantity_kind(k)):
            out.append(k)
    return out


def _loop_shape(g: Dict[str, Any]) -> List[Dict[str, Any]]:
    shape = []
    for lp in g.get("loops") or []:
        if not isinstance(lp, dict):
            shape.append({"nondict": True})
            continue
        edges = lp.get("edges")
        verts = lp.get("vertices")
        types: Dict[str, int] = {}
        if isinstance(edges, list):
            for ed in edges:
                t = str((ed or {}).get("type"))
                types[t] = types.get(t, 0) + 1
        shape.append({
            "loop_type": lp.get("loop_type"),
            "closed": lp.get("closed"),
            "n_edges": len(edges) if isinstance(edges, list) else None,
            "n_vertices": len(verts) if isinstance(verts, list) else None,
            "edge_types": types,
        })
    return shape


def analyze(census_ir: Dict[str, Any], post_ir: Dict[str, Any],
            interior: Dict[str, Any], *, dryrun: bool) -> Dict[str, Any]:
    name_map = _load_name_map(interior)
    defs_a = blockdef_diff._definitions_by_name(census_ir)
    defs_b = blockdef_diff._definitions_by_name(post_ir)
    baseline_totals = dict(interior.get("totals") or {})

    # ---- part 1+2: reproduce pairing on dirty defs, capture modified pairs
    pair_rows: List[Dict[str, Any]] = []
    reproduce_errors: List[str] = []
    arc_angle_min = math.inf
    arc_angle_max = -math.inf
    for row in _dirty_rows(interior):
        def_name = str(row.get("name") or "")
        b_name = str(row.get("b_name") or def_name)
        def_a = defs_a.get(def_name)
        def_b = defs_b.get(b_name)
        if def_a is None or def_b is None:
            if row.get("missing_side"):
                continue  # e.g. DIMDOT removed-side rows: nothing to pair
            reproduce_errors.append("def not found: %r" % def_name)
            continue
        ents_a = blockdef_diff._definition_entities(def_a, name_map=name_map)
        ents_b = blockdef_diff._definition_entities(def_b)
        with _PairCapture() as cap:
            diff = cad_diff.compute_diff(
                blockdef_diff._synthetic_ir(ents_a),
                blockdef_diff._synthetic_ir(ents_b),
                comparison_basis="geometry",
                geometry_tolerance=1e-6,
                diff_scope=cad_diff.FULL_DATABASE,
            )
        summary = diff["summary"]
        for key in ("modified", "removed", "added"):
            if int(summary.get(key, 0) or 0) != int(row.get(key, 0) or 0):
                reproduce_errors.append(
                    "def %r %s: reproduced %s != report %s"
                    % (def_name, key, summary.get(key), row.get(key)))
        for pre_e, post_e, fields in cap.pairs:
            g_a = pre_e.get("geometry") or {}
            g_b = post_e.get("geometry") or {}
            for g in (g_a, g_b):
                for lp in g.get("loops") or []:
                    for ed in (lp or {}).get("edges") or []:
                        if isinstance(ed, dict) and ed.get("type") == "arc":
                            for k in ("start_angle", "end_angle"):
                                v = ed.get(k)
                                if isinstance(v, (int, float)):
                                    arc_angle_min = min(arc_angle_min, v)
                                    arc_angle_max = max(arc_angle_max, v)
            geom_keys = _geometry_key_delta(g_a, g_b)
            nongeom = [f for f in fields
                       if f != "geometry" and not f.startswith("geometry.")]
            pair_rows.append({
                "def": def_name,
                "kind": (g_a.get("kind") or g_b.get("kind")),
                "dxf_name": post_e.get("dxf_name") or pre_e.get("dxf_name"),
                "a_handle": pre_e.get("handle"),
                "b_handle": post_e.get("handle"),
                "changed_geometry_keys": geom_keys,
                "changed_nongeometry_fields": nongeom,
                "_g_a": g_a,
                "_g_b": g_b,
            })

    # ---- part 3+4: classify; loops-only pairs get verifier + fold test
    loops_only: List[Dict[str, Any]] = []
    loops_plus: List[Dict[str, Any]] = []
    other: List[Dict[str, Any]] = []
    for pr in pair_rows:
        keys = pr["changed_geometry_keys"]
        target = (pr["kind"] == "hatch" and not pr["changed_nongeometry_fields"]
                  and keys == ["loops"])
        if target:
            loops_only.append(pr)
        elif pr["kind"] == "hatch" and "loops" in keys:
            loops_plus.append(pr)
        else:
            other.append(pr)

    fold_yes = 0
    fold_no = 0
    geom_eq = 0
    geom_diff = 0
    resistant: List[Dict[str, Any]] = []
    folded_geomdiff: List[Dict[str, Any]] = []
    dist_max_folded = 0.0
    for pr in loops_only:
        g_a, g_b = pr.pop("_g_a"), pr.pop("_g_b")
        d, notes = hatch_pointcloud_distance(g_a, g_b)
        pr["pointcloud_max_nn"] = None if math.isinf(d) else round(d, 9)
        pr["pointcloud_notes"] = notes
        equal_geom = d < _GEOM_EQ_TOL
        geom_eq += 1 if equal_geom else 0
        geom_diff += 0 if equal_geom else 1
        ca = apply_loop_canon_to_geometry(g_a)
        cb = apply_loop_canon_to_geometry(g_b)
        folds = cad_diff._geometry_within_tolerance(
            ca, cb, {"length": 1e-6}, "length")
        pr["canon_folds"] = bool(folds)
        if folds:
            fold_yes += 1
            dist_max_folded = max(dist_max_folded,
                                  d if not math.isinf(d) else 0.0)
            if not equal_geom:
                folded_geomdiff.append(pr)  # MUST stay empty: fold w/o geometry
        else:
            fold_no += 1
            pr["a_loop_shape"] = _loop_shape(g_a)
            pr["b_loop_shape"] = _loop_shape(g_b)
            resistant.append(pr)
    for pr in loops_plus + other:
        pr.pop("_g_a", None)
        pr.pop("_g_b", None)

    # ---- part 5: collision test over ALL census-side hatch loops
    canon_buckets: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    n_loops_total = 0
    for def_name, block_def in defs_a.items():
        for ent in blockdef_diff._definition_entities(block_def, name_map=name_map):
            g = ent.get("geometry") or {}
            if g.get("kind") != "hatch":
                continue
            for lp in g.get("loops") or []:
                if not isinstance(lp, dict):
                    continue
                n_loops_total += 1
                key = _ser(canonical_loop(lp), _ROUND)
                canon_buckets.setdefault(key, []).append((_ser(lp, _ROUND), lp))
    collisions: List[Dict[str, Any]] = []
    merged_notation = 0
    for key, members in canon_buckets.items():
        distinct_raw: Dict[str, Dict[str, Any]] = {}
        for raw_ser, lp in members:
            distinct_raw.setdefault(raw_ser, lp)
        if len(distinct_raw) <= 1:
            continue
        merged_notation += len(distinct_raw) - 1
        reps = list(distinct_raw.values())
        base_pts, _ = sample_loop_points(reps[0])
        for other_lp in reps[1:]:
            pts, _ = sample_loop_points(other_lp)
            if not base_pts or not pts:
                collisions.append({"canon_key_prefix": key[:120],
                                   "reason": "unsampleable"})
                continue
            d = max(_max_nn_distance(base_pts, pts),
                    _max_nn_distance(pts, base_pts))
            if d >= _GEOM_EQ_TOL:
                collisions.append({
                    "canon_key_prefix": key[:120],
                    "pointcloud_max_nn": round(d, 9),
                })

    # ---- part 6 (optional): full dry-run with candidate canon patched in
    dryrun_result: Optional[Dict[str, Any]] = None
    if dryrun:
        orig_canon_entity = blockdef_diff._canonical_entity

        def _canon_plus_loops(entity: Dict[str, Any],
                              name_map: Optional[Dict[str, str]] = None
                              ) -> Dict[str, Any]:
            canon = orig_canon_entity(entity, name_map=name_map)
            g = canon.get("geometry") or {}
            if g.get("kind") == "hatch":
                g2 = apply_loop_canon_to_geometry(g)
                if g2 is not g:
                    if canon is entity:
                        canon = dict(entity)
                    canon["geometry"] = g2
            return canon

        blockdef_diff._canonical_entity = _canon_plus_loops
        try:
            full = blockdef_diff.diff_block_definitions(
                census_ir, post_ir, name_map=name_map)
        finally:
            blockdef_diff._canonical_entity = orig_canon_entity
        regressions = []
        base_by_name = {str(r.get("name")): r
                        for r in interior.get("per_def") or [] if isinstance(r, dict)}
        for row in full.get("per_def") or []:
            base = base_by_name.get(str(row.get("name")))
            if base and int(row.get("diff0", 0)) < int(base.get("diff0", 0)):
                regressions.append({
                    "name": row.get("name"),
                    "diff0_before": base.get("diff0"),
                    "diff0_after": row.get("diff0"),
                })
        dryrun_result = {
            "totals": full.get("totals"),
            "per_def_regressions": regressions,
            "dirty_defs_after": [
                {"name": r.get("name"),
                 "a_total": r.get("a_total"), "diff0": r.get("diff0"),
                 "modified": r.get("modified"), "removed": r.get("removed"),
                 "added": r.get("added")}
                for r in full.get("per_def") or []
                if int(r.get("a_total", 0) or 0) != int(r.get("diff0", 0) or 0)
            ],
        }

    return {
        "schema": SCHEMA_ID,
        "inputs": {
            "census_ir": None,   # filled by main()
            "post_ir": None,
            "interior_diff": None,
        },
        "baseline": {
            "totals": baseline_totals,
            "reproduce_errors": reproduce_errors,
            "captured_modified_pairs": len(pair_rows),
        },
        "classification": {
            "loops_only": len(loops_only),
            "loops_plus_other_keys": len(loops_plus),
            "non_loops": len(other),
        },
        "loops_only_verdict": {
            "pointcloud_geometry_equal": geom_eq,
            "pointcloud_geometry_diff": geom_diff,
            "geometry_eq_tolerance": _GEOM_EQ_TOL,
            "canon_folds": fold_yes,
            "canon_resistant": fold_no,
            "max_pointcloud_dist_among_folded": round(dist_max_folded, 9),
            "folded_but_geometry_diff": folded_geomdiff,  # MUST be []
        },
        "arc_angle_range_seen": (
            None if math.isinf(arc_angle_min)
            else [arc_angle_min, arc_angle_max]),
        "collision_test": {
            "census_hatch_loops": n_loops_total,
            "distinct_canonical_forms": len(canon_buckets),
            "notation_variants_merged": merged_notation,
            "geometry_collisions": collisions,  # MUST be []
        },
        "pairs_loops_only": [
            {k: v for k, v in pr.items() if not k.startswith("_")}
            for pr in loops_only],
        "pairs_loops_plus": loops_plus,
        "pairs_non_loops": other,
        "resistant_pairs": resistant,
        "dryrun": dryrun_result,
    }


def _render_md(report: Dict[str, Any]) -> str:
    cls = report["classification"]
    lov = report["loops_only_verdict"]
    col = report["collision_test"]
    lines = [
        "# HATCH loops residue analysis (R4s candidate)",
        "",
        "## Baseline reproduce",
        "",
        "- captured modified pairs: %s" % report["baseline"]["captured_modified_pairs"],
        "- reproduce errors: %s" % (report["baseline"]["reproduce_errors"] or "none"),
        "",
        "## Classification",
        "",
        "- loops-only pairs: %s" % cls["loops_only"],
        "- loops+other-key pairs: %s" % cls["loops_plus_other_keys"],
        "- non-loops pairs: %s" % cls["non_loops"],
        "",
        "## Loops-only verdict",
        "",
        "- point-cloud geometry-equal: %s / geometry-diff: %s (tol %s)"
        % (lov["pointcloud_geometry_equal"], lov["pointcloud_geometry_diff"],
           lov["geometry_eq_tolerance"]),
        "- candidate canon folds: %s / resistant: %s"
        % (lov["canon_folds"], lov["canon_resistant"]),
        "- max point-cloud distance among folded: %s"
        % lov["max_pointcloud_dist_among_folded"],
        "- folded-but-geometry-diff (must be empty): %s"
        % len(lov["folded_but_geometry_diff"]),
        "",
        "## Collision test (census side, all hatch loops)",
        "",
        "- loops: %s, distinct canonical forms: %s, notation variants merged: %s"
        % (col["census_hatch_loops"], col["distinct_canonical_forms"],
           col["notation_variants_merged"]),
        "- geometry collisions (must be empty): %s" % len(col["geometry_collisions"]),
        "",
    ]
    dr = report.get("dryrun")
    if dr:
        totals = dr.get("totals") or {}
        lines += [
            "## Dry-run (candidate legislated, full population)",
            "",
            "- diff0_total: %s / %s (fraction %s)"
            % (totals.get("diff0_total"), totals.get("a_entity_total"),
               totals.get("interior_diff0_fraction")),
            "- per-def regressions (must be empty): %s"
            % len(dr.get("per_def_regressions") or []),
            "",
        ]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census-ir", default=DEFAULT_CENSUS_IR)
    parser.add_argument("--post-ir", default=DEFAULT_POST_IR)
    parser.add_argument("--interior-diff", default=DEFAULT_INTERIOR_DIFF)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--no-dryrun", action="store_true",
                        help="skip the full-population dry run (fast recon)")
    args = parser.parse_args(argv)

    report = analyze(
        _load_json(args.census_ir),
        _load_json(args.post_ir),
        _load_json(args.interior_diff),
        dryrun=not args.no_dryrun,
    )
    report["inputs"] = {
        "census_ir": os.path.abspath(args.census_ir),
        "post_ir": os.path.abspath(args.post_ir),
        "interior_diff": os.path.abspath(args.interior_diff),
    }

    out_json = args.out_json if os.path.isabs(args.out_json) else os.path.join(_REPO_ROOT, args.out_json)
    out_md = args.out_md if os.path.isabs(args.out_md) else os.path.join(_REPO_ROOT, args.out_md)
    _write_json(out_json, report)
    parent = os.path.dirname(os.path.abspath(out_md))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write(_render_md(report))

    print("loops_only=%s loops_plus=%s non_loops=%s"
          % (report["classification"]["loops_only"],
             report["classification"]["loops_plus_other_keys"],
             report["classification"]["non_loops"]))
    lov = report["loops_only_verdict"]
    print("geom_eq=%s geom_diff=%s folds=%s resistant=%s"
          % (lov["pointcloud_geometry_equal"], lov["pointcloud_geometry_diff"],
             lov["canon_folds"], lov["canon_resistant"]))
    print("folded_but_geometry_diff=%s (must be 0)"
          % len(lov["folded_but_geometry_diff"]))
    col = report["collision_test"]
    print("collision: loops=%s canon_forms=%s merged=%s geometry_collisions=%s (must be 0)"
          % (col["census_hatch_loops"], col["distinct_canonical_forms"],
             col["notation_variants_merged"], len(col["geometry_collisions"])))
    if report["baseline"]["reproduce_errors"]:
        print("REPRODUCE ERRORS:", len(report["baseline"]["reproduce_errors"]))
        for err in report["baseline"]["reproduce_errors"][:10]:
            print("  -", ascii(err))
    dr = report.get("dryrun")
    if dr:
        totals = dr.get("totals") or {}
        print("dryrun diff0_total=%s / %s fraction=%s regressions=%s"
              % (totals.get("diff0_total"), totals.get("a_entity_total"),
                 totals.get("interior_diff0_fraction"),
                 len(dr.get("per_def_regressions") or [])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
