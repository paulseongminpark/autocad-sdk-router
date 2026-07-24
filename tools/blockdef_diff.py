#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Per-block-definition geometry diff over DWG graph IRs."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

import cad_diff

_JSON_ENCODING = "utf-8-sig"
SCHEMA_ID = "ariadne.blockdef_diff.v1"

_TWO_PI = 2.0 * math.pi
_TWO_PI_6DP = round(_TWO_PI, 6)

# *D<n> anonymous blocks are DIMENSION-DERIVED CACHES: every AcDbDimension
# mints its own *D block holding that dimension's rendered representation, and
# a rebuilt drawing's dimensions mint FRESH *D names. Comparing them by name
# is a category error, measured on R4l: 2,183 of 2,534 residual mismatches
# (86.1%) were exactly 113 a-side *D orphans + 113 freshly-minted b-side *D
# defs -- a perfect pairing with the drawing's 113 dimensions, whose semantic
# content the L5 dim_semantic_gate verifies directly (113/113 = 1.0 on the
# same run). The caches are excluded from the name-matched comparison and
# accounted honestly in totals.derived_cache_excluded.
_DIM_CACHE_NAME = re.compile(r"^\*D\d+$")


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _canonical_hatch_geometry(g: Dict[str, Any]) -> Dict[str, Any]:
    """Unit-normalize hatch pattern definitions before comparison.

    Two legislated notational equivalences, both measured on 1.dwg:

    1. Scale baking (R4l, def X-...$0$111a, pattern H3, scale 300): the
       ORIGINAL hatch extracts pattern_type=1 (kPreDefined) with
       getPatternDefinitionAt values scale-BAKED (base [14135, -7335], offset
       [-300, ~0]); the .pat replay rebuild extracts pattern_type=2
       (kCustomDefined) with UNIT values (base [47.1167, -24.45], offset
       [-1, ~0]) -- exactly a = b * scale, the same line families rendered
       identically. Canonical form: divide type-1 base/offset/dashes by
       pattern_scale (type-2 rows are already unit) and drop pattern_type
       (provenance, not geometry).

    2. Phase carrier (R4n census probe, runs/e2e_1dwg_R4n_origin_20260709):
       the per-hatch pattern phase may live EITHER baked into the row base
       points (originals: 233/233 residual pairs = one common per-hatch base
       vector, census pattern_origin [0,0]) OR in the HPORIGIN field with
       zero-phase rows (the rebased-.pat replay: blocks.py emits
       pattern_origin = rows[0].base + census origin). Same rendered lattice,
       different carrier. Canonical form: rows carry INTRA-pattern structure
       only (base rebased against rows[0].base) and the effective phase is
       folded into one provenance-free field
           pattern_phase = rows[0].base/divisor + pattern_origin/scale
       (both terms in unit pattern space); pattern_origin is then dropped.
       A REAL phase difference still differs after folding -- only the
       carrier choice is quotiented out. Substitute verifier for the folded
       representation: the visual gate lane.

    Same measurement-contract precedent as spline fit_points below.
    """
    try:
        ptype = float(g.get("pattern_type"))
        scale = float(g.get("pattern_scale"))
    except (TypeError, ValueError):
        return g
    rows = g.get("pattern_definitions")
    if not isinstance(rows, list):
        return g
    canon_g = dict(g)
    canon_g.pop("pattern_type", None)
    # Baked-vs-unit detection must NOT trust pattern_type: originals store
    # type-1 rows scale-BAKED, but a type-1 PREDEFINED-name replay (DASH x66,
    # R4p runs/e2e_1dwg_R4p_phase_20260709) stores UNIT rows -- same type,
    # different baking. The scale signal lives in the row magnitudes
    # themselves: baked offsets/dashes are O(scale), unit ones are O(1), so
    # sqrt(scale) separates the two whenever scale > 1 (measured populations:
    # 43.75..350 baked vs 0.125..1 unit at scales 300/350). Degenerate
    # scales (<=1) or all-zero rows keep the legacy type-1 rule.
    row_mag = 0.0
    for _row in rows:
        if not isinstance(_row, dict):
            continue
        for _key in ("offset", "dashes"):
            _val = _row.get(_key)
            if isinstance(_val, list):
                for _v in (_val[:2] if _key == "offset" else _val):
                    if isinstance(_v, (int, float)):
                        row_mag = max(row_mag, abs(_v))
    if scale and scale > 1.0 and row_mag > 0.0:
        baked = row_mag > math.sqrt(scale)
    else:
        baked = (ptype == 1.0 and bool(scale))
    divisor = scale if (baked and scale) else 1.0

    def _q(v: Any) -> Any:
        # Quantize AFTER unit-normalization: the .pat replay serializes at
        # %.10g (measured residue ~3e-11 on base, ~1e-16 on near-zero
        # offsets) while the census carries full doubles; cad_diff compares
        # this nested field exactly, so equality needs a shared grid. 1e-6 in
        # unit pattern space is far coarser than the serialization noise and
        # far finer than any real pattern difference.
        return round(v / divisor, 6) if isinstance(v, (int, float)) else v

    def _num_pair(val: Any) -> Optional[List[float]]:
        if (isinstance(val, list) and len(val) >= 2
                and all(isinstance(v, (int, float)) for v in val[:2])):
            return [float(val[0]), float(val[1])]
        return None

    base1 = None
    if rows and isinstance(rows[0], dict):
        base1 = _num_pair(rows[0].get("base"))
    origin = _num_pair(canon_g.pop("pattern_origin", None)) or [0.0, 0.0]
    origin_div = scale if scale else divisor
    phase_src = base1 or [0.0, 0.0]
    canon_g["pattern_phase"] = [
        round(phase_src[0] / divisor + origin[0] / origin_div, 6),
        round(phase_src[1] / divisor + origin[1] / origin_div, 6),
    ]

    norm_rows: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            norm_rows.append(row)
            continue
        nrow = dict(row)
        if isinstance(row.get("angle"), (int, float)):
            # Angle is never scaled; it IS circle-valued (LEX-0009): the
            # census carries a 2*pi-branch DASH vintage (4/66 hatches at row
            # angle 6.28318..., R4s dissection reports/interior100/
            # loops_residue_analysis_R4s.json) that the predefined-name
            # replay re-reports at 0.0 -- the same line family. Fold to the
            # principal branch [0, 2*pi) on the shared 6dp grid.
            ang = round(float(row["angle"]) % _TWO_PI, 6)
            if ang >= _TWO_PI_6DP:
                ang = 0.0
            nrow["angle"] = ang
        for key in ("base", "offset", "dashes"):
            val = row.get(key)
            if isinstance(val, list):
                if key == "base" and base1 is not None:
                    pair = _num_pair(val)
                    if pair is not None:
                        rebased = [pair[0] - base1[0], pair[1] - base1[1]]
                        rebased.extend(val[2:])
                        nrow[key] = [_q(v) for v in rebased]
                        continue
                nrow[key] = [_q(v) for v in val]
        norm_rows.append(nrow)
    canon_g["pattern_definitions"] = norm_rows
    return canon_g


def _canonical_ellipse_geometry(g: Dict[str, Any]) -> Dict[str, Any]:
    """Principal-branch ellipse arc angles (LEX-0009).

    The census reports start/end params on the [-pi, pi) branch while the
    rebuild engine re-reports [0, 2*pi) (R4s dissection: all 16 residual
    ellipse pairs are the SAME arc in two branches, e.g. start -pi/2 -> end
    ~0 vs start 3*pi/2 -> end 2*pi). Angles on a circle are equivalence
    classes mod 2*pi; the arc itself is (start, sweep). Canonical form:
    start folded to [0, 2*pi) on the 6dp grid, end = start + sweep with
    sweep in (0, 2*pi] so a full ellipse stays full instead of collapsing
    to empty. A REAL sweep or placement difference still differs after
    folding. Substitute verifier: dense point sampling of both
    parameterizations (tools/loops_residue_analysis.py, R4s)."""
    try:
        start = float(g.get("start_angle"))
        end = float(g.get("end_angle"))
    except (TypeError, ValueError):
        return g
    sweep = (end - start) % _TWO_PI
    # Robust full-ellipse detection (LEX-0009, extended on the GEN2d idempotence
    # residual hd1050/853). A full ellipse has |end-start| ~ k*2pi, and a
    # re-extraction lands the %2pi residual on EITHER side of 0/2pi by float
    # noise: measured gen1 end-start = 2pi + 1.8e-15 -> sweep ~ 0; gen2 =
    # 2pi - 2e-15 -> sweep ~ 2pi. The old exact `sweep == 0.0` guard folded one
    # generation to an EMPTY arc (sweep rounds to 0) and the other to FULL -- a
    # 1-entity gen1->gen2 break (and a latent forward mis-fold: 1.dwg's own
    # 1CDF full ellipse canonicalized to empty, harmless only because forward
    # was symmetric). Treat the arc as full when it spans at least ~one turn AND
    # the residual sits within the shared 6dp grid of a full turn. A genuine
    # partial arc (sweep not near 0/2pi) and a genuine empty arc
    # (|end-start| < grid) are untouched; a 1.5-turn arc (sweep ~ pi) is not
    # folded because its residual is not near 0/2pi.
    if abs(end - start) >= _TWO_PI - 1e-6 and (sweep <= 1e-6 or sweep >= _TWO_PI - 1e-6):
        sweep = _TWO_PI
    start_c = round(start % _TWO_PI, 6)
    if start_c >= _TWO_PI_6DP:
        start_c = 0.0
    canon_g = dict(g)
    canon_g["start_angle"] = start_c
    canon_g["end_angle"] = round(start_c + round(sweep, 6), 6)
    return canon_g


def _loop_vertex_key(v: Any) -> Optional[Tuple[float, float, float]]:
    """(x, y, bulge) on the 6dp grid, for LEX-0012 rotation ordering.

    Accepts the IR dict form {"point": [x, y(, z)], "bulge": b} and the bare
    list form [x, y(, bulge)]. Returns None when unparseable (the loop is
    then left in its original notation -- never guessed)."""
    if isinstance(v, dict):
        p = v.get("point")
        b = v.get("bulge") or 0.0
    elif isinstance(v, list) and len(v) >= 2:
        p, b = v[:2], (v[2] if len(v) >= 3 else 0.0)
    else:
        return None
    if not (isinstance(p, list) and len(p) >= 2):
        return None
    try:
        return (round(float(p[0]), 6), round(float(p[1]), 6),
                round(float(b), 6))
    except (TypeError, ValueError):
        return None


def _canonical_poly_loop(loop: Any) -> Any:
    """Closed polyline-loop cycle quotient (LEX-0012, R4v).

    The id-derived boundary replay (relink + evaluateHatch, R4v) re-serializes
    a closed vertex loop starting at a DIFFERENT vertex: the same cycle,
    rotated (5/5 measured pairs at point-cloud distance exactly 0.0,
    reports/interior100/loops_residue_analysis_R4v.json). A closed cycle has
    no distinguished first vertex, so the serialization start is notation.
    Canonical form, applied ONLY when the loop is closed by its own flag AND
    carries an exact explicit duplicate closing vertex (trailing bulge 0 --
    the R4v population is 16/16 loops per side in exactly that shape):
    drop the duplicate, rotate the cycle to its lexicographically minimal
    (x, y, bulge)@6dp serialization, and EMIT the vertices on that same 6dp
    grid (the replayed boundary re-derives coordinates from the relinked
    sources with sub-grid float noise -- measured 2e-12 on the 2465/6D12
    pairs -- and the ladder's shared 6dp grid is exactly the instrument
    resolution, LEX-0009). Direction is NOT quotiented and open paths are
    NEVER touched (a distinguished start is real there) -- the quotient
    stays minimal per the LEX-0010 blind-spot rationale."""
    if not isinstance(loop, dict) or not loop.get("closed"):
        return loop
    verts = loop.get("vertices")
    if not (isinstance(verts, list) and len(verts) >= 3):
        return loop
    keys = [_loop_vertex_key(v) for v in verts]
    if any(k is None for k in keys):
        return loop
    if not (keys[0][:2] == keys[-1][:2] and keys[-1][2] == 0.0):
        return loop
    body, body_keys = verts[:-1], keys[:-1]
    n = len(body)
    if n < 2:
        return loop
    best = min(range(n), key=lambda s: [body_keys[(s + j) % n] for j in range(n)])
    cverts: List[Dict[str, Any]] = []
    for j in range(n):
        v = body[(best + j) % n]
        x, y, b = body_keys[(best + j) % n]
        p = v.get("point") if isinstance(v, dict) else v[:2]
        pt = [x, y]
        if isinstance(p, list) and len(p) >= 3:
            try:
                pt.extend(round(float(z), 6) for z in p[2:])
            except (TypeError, ValueError):
                pt = [x, y]
        cverts.append({"point": pt, "bulge": b})
    new_loop = dict(loop)
    new_loop["vertices"] = cverts
    return new_loop


def _parse_spline_edge(edge: Any) -> Optional[Tuple[int, List[Tuple[float, ...]],
                                                      List[float],
                                                      Optional[List[float]]]]:
    """Validate one hatch-loop spline edge; None => leave the loop untouched.

    Requires type=='spline', integer degree>=1, control list of >=degree+1
    numeric [x,y] points, and a non-decreasing knots list of length
    len(control)+degree+1. Rational edges (rational truthy or non-empty
    weights) further require len(weights)==len(control) with every weight>0.
    Same never-guess discipline as _loop_vertex_key."""
    if not isinstance(edge, dict) or edge.get("type") != "spline":
        return None
    degree = edge.get("degree")
    if isinstance(degree, bool) or not isinstance(degree, int) or degree < 1:
        return None
    control_raw = edge.get("control")
    knots_raw = edge.get("knots")
    if not (isinstance(control_raw, list) and isinstance(knots_raw, list)):
        return None
    if len(control_raw) < degree + 1:
        return None
    if len(knots_raw) != len(control_raw) + degree + 1:
        return None
    try:
        control: List[Tuple[float, ...]] = []
        for pt in control_raw:
            if not (isinstance(pt, list) and len(pt) >= 2):
                return None
            control.append((float(pt[0]), float(pt[1])))
        knots = [float(t) for t in knots_raw]
    except (TypeError, ValueError):
        return None
    for i in range(1, len(knots)):
        if knots[i] < knots[i - 1]:
            return None
    weights_raw = edge.get("weights")
    rational = bool(edge.get("rational")) or (
        isinstance(weights_raw, list) and len(weights_raw) > 0
    )
    weights: Optional[List[float]] = None
    if rational:
        if not isinstance(weights_raw, list) or len(weights_raw) != len(control):
            return None
        try:
            weights = [float(w) for w in weights_raw]
        except (TypeError, ValueError):
            return None
        if any(w <= 0.0 for w in weights):
            return None
    return degree, control, knots, weights


def _boehm_insert_once(controls: List[Tuple[float, ...]], knots: List[float],
                       degree: int, u: float
                       ) -> Tuple[List[Tuple[float, ...]], List[float]]:
    """Insert knot u once (Boehm / de Boor-style); stdlib only."""
    d = degree
    n = len(controls) - 1
    k: Optional[int] = None
    for i in range(len(knots) - 1):
        if knots[i] <= u < knots[i + 1]:
            k = i
            break
    if k is None:
        return controls, knots
    dim = len(controls[0])
    new_c: List[Optional[Tuple[float, ...]]] = [None] * (n + 2)
    for i in range(0, k - d + 1):
        new_c[i] = controls[i]
    for i in range(k - d + 1, k + 1):
        denom = knots[i + d] - knots[i]
        alpha = 0.0 if denom == 0.0 else (u - knots[i]) / denom
        new_c[i] = tuple(
            (1.0 - alpha) * controls[i - 1][j] + alpha * controls[i][j]
            for j in range(dim)
        )
    for i in range(k + 1, n + 2):
        new_c[i] = controls[i - 1]
    out: List[Tuple[float, ...]] = []
    for c in new_c:
        if c is None:  # pragma: no cover - Boehm fills every slot
            raise RuntimeError("boehm slot left empty")
        out.append(c)
    return out, knots[: k + 1] + [u] + knots[k + 1 :]


def _spline_edge_to_bezier_segments(
        degree: int,
        control: List[Tuple[float, ...]],
        knots: List[float],
        weights: Optional[List[float]],
) -> List[Dict[str, Any]]:
    """Raise interior knots to multiplicity==degree, emit per-span Beziers.

    Quantization (round(_, 6)) happens ONLY at emission. Zero-width spans are
    skipped; segments whose d+1 controls are identical @6dp are dropped.
    Knot values themselves are notation and do not appear in the output."""
    d = degree
    if weights is None:
        pts: List[Tuple[float, ...]] = list(control)
    else:
        pts = [(c[0] * w, c[1] * w, w) for c, w in zip(control, weights)]
    U = list(knots)
    domain_start, domain_end = U[d], U[len(pts)]
    interiors: List[float] = []
    seen = set()
    for t in U:
        if t not in seen and domain_start < t < domain_end:
            interiors.append(t)
            seen.add(t)
    for u in interiors:
        while sum(1 for t in U if t == u) < d:
            pts, U = _boehm_insert_once(pts, U, d, u)
    n = len(pts) - 1
    segs: List[Dict[str, Any]] = []
    for i in range(d, n + 1):
        if not (U[i] < U[i + 1]):
            continue
        raw = pts[i - d: i + 1]
        if weights is None:
            q_ctrl = [[round(p[0], 6), round(p[1], 6)] for p in raw]
            if all(pt == q_ctrl[0] for pt in q_ctrl):
                continue
            segs.append({"type": "spline_bezier", "degree": d, "control": q_ctrl})
        else:
            dehom: List[Tuple[float, float, float]] = []
            ok = True
            for hx, hy, hw in raw:
                if hw == 0.0:
                    ok = False
                    break
                dehom.append((hx / hw, hy / hw, hw))
            if not ok:
                continue
            q_ctrl = [[round(p[0], 6), round(p[1], 6)] for p in dehom]
            q_w = [round(p[2], 6) for p in dehom]
            if all(pt == q_ctrl[0] for pt in q_ctrl) and all(w == q_w[0] for w in q_w):
                continue
            segs.append({"type": "spline_bezier", "degree": d,
                         "control": q_ctrl, "weights": q_w})
    return segs


def _bezier_seg_key(seg: Dict[str, Any]) -> Tuple[Any, ...]:
    """JSON-stable tuple form of one spline_bezier segment (sorted keys)."""
    parts: List[Tuple[str, Any]] = []
    for k in sorted(seg.keys()):
        v = seg[k]
        if k == "control":
            parts.append((k, tuple(tuple(p) for p in v)))
        elif k == "weights":
            parts.append((k, tuple(v)))
        else:
            parts.append((k, v))
    return tuple(parts)


def _canonical_spline_loop(loop: Any) -> Any:
    """Spline edge-loop re-decomposition quotient (LEX-0013, R4x).

    The two residual 1.dwg hatch pairs in def X-FORM_청주$0$dA로고
    (reports/interior100/loops_residue_analysis_R4x.json: resistant 2,
    pointcloud_max_nn 9.16e-4, spline-control-proxy;
    fixture tests/fixtures/lex0013_dA_pairs.json pairs[2]=1BDF/762B,
    pairs[3]=1BE6/7632) store THE SAME boundary curve under two notations:
    the census side keeps a few MULTI-SPAN cubic B-spline edges (knot counts
    23/8/14 on the outer loop), while the rebuild re-decomposes into
    per-knot-span Bezier edges (degree 3, 4 control points, knots like
    [6,6,6,6,7,7,7,7]). Segmentation and knot parameterization of a spline
    edge chain are notation; the curve is the geometry.

    Canonical form, applied ONLY when every edge of the loop is a well-formed
    spline (see _parse_spline_edge -- any violation returns the loop
    unchanged): Boehm-raise every interior knot to multiplicity == degree,
    split each edge into per-span Bezier segments, concatenate in edge order,
    emit on the ladder's shared 6dp grid (LEX-0009) as
    {type:spline_bezier, degree, control[, weights]}, drop @6dp-degenerate
    segments, and -- when loop.closed -- rotate the segment list to its
    lexicographically minimal JSON-stable serialization (same cycle-quotient
    shape as LEX-0012). Direction is NOT quotiented; open loops are NOT
    rotated. Knot values and per-edge grouping do not appear in the
    canonical form."""
    if not isinstance(loop, dict):
        return loop
    edges = loop.get("edges")
    if not (isinstance(edges, list) and edges):
        return loop
    parsed = [_parse_spline_edge(e) for e in edges]
    if any(p is None for p in parsed):
        return loop
    segs: List[Dict[str, Any]] = []
    for item in parsed:
        assert item is not None
        degree, control, knots, weights = item
        segs.extend(_spline_edge_to_bezier_segments(degree, control, knots, weights))
    if loop.get("closed") and segs:
        n = len(segs)
        keys = [_bezier_seg_key(s) for s in segs]
        best = min(range(n), key=lambda s: [keys[(s + j) % n] for j in range(n)])
        segs = [segs[(best + j) % n] for j in range(n)]
    new_loop = dict(loop)
    new_loop["edges"] = segs
    return new_loop


def _canonical_entity(entity: Dict[str, Any],
                      name_map: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Normalize representation-dependent geometry before comparison.

    Splines: the extractor stores the canonical B-spline definition at the
    def-entity TOP level (spline_control_points / spline_knots) and, only for
    fit-authored splines, an additional geometry.fit_points list. A rebuild
    from control points + knots produces the mathematically identical curve
    but re-extracts WITHOUT fit_points (measured on R4b: 139/139 canonical
    match while geometry-dict compare called all of them modified). Compare
    the canonical definition on both sides; fit authoring data is reported
    separately in totals, not silently dropped.
    """
    canon = entity
    g = entity.get("geometry") or {}
    if name_map and g.get("kind") == "block_reference":
        block_name = g.get("block_name")
        mapped_name = name_map.get(block_name)
        if mapped_name and mapped_name != block_name:
            canon = dict(entity)
            g = dict(g)
            g["block_name"] = mapped_name
            canon["geometry"] = g
    if g.get("kind") == "hatch":
        canon_g = g
        if g.get("pattern_definitions"):
            canon_g = _canonical_hatch_geometry(canon_g)
        # Orphan-assoc quotient (LEX-0008, R4r runs/e2e_1dwg_R4r_assoc_20260710;
        # gate widened on R4s; observation corrected on R4u -- the 0/66 probes
        # had flown a stale binary, docs/ASSOC_ORPHAN_FINDING.md retraction):
        # is_associative is a DERIVED flag -- it only has semantics when
        # boundary source refs exist. A sourceless flag cannot survive save
        # (R4u measured with the LIVE flag replay: job True -> saved False,
        # 258/258), so when a hatch has no assoc_source_handles the flag drops
        # from comparison on BOTH sides -- for EVERY hatch. Hatches with real
        # sources keep the flag AND compare the source payload (below).
        if "is_associative" in canon_g and not canon_g.get("assoc_source_handles"):
            if canon_g is g:
                canon_g = dict(g)
            canon_g.pop("is_associative")
        # Assoc payload quotient (LEX-0011, R4u): handle IDENTITY is not
        # rebuild-stable -- a rebuild mints fresh handles, so raw handle
        # strings can never match across census and rebuild (same category as
        # *D cache names, LEX-0001, and anonymous block names). Canonical
        # form: per-loop source CARDINALITY, order-aligned to loops[]. A
        # relink to wrong-but-same-count sources still fingerprint-matches --
        # that residual risk rides the substitute verifier (post-flight assoc
        # audit: pairing + per-loop source-kind multisets + the
        # source_handle->new_handle ledger), not the fingerprint.
        srcs = canon_g.get("assoc_source_handles")
        if isinstance(srcs, list) and srcs:
            if canon_g is g:
                canon_g = dict(g)
            canon_g.pop("assoc_source_handles")
            canon_g["assoc_loop_source_counts"] = [
                len(loop) if isinstance(loop, list) else -1 for loop in srcs
            ]
        # Closed polyline-loop cycle quotient (LEX-0012, R4v) then spline
        # edge-loop re-decomposition quotient (LEX-0013 part 1, R4x): see
        # _canonical_poly_loop / _canonical_spline_loop.
        loops = canon_g.get("loops")
        if isinstance(loops, list) and loops:
            new_loops = [_canonical_spline_loop(_canonical_poly_loop(lp))
                         for lp in loops]
            # Derived spline-loop cache fold (LEX-0013 part 2, R4x). The two
            # residual dA-logo pairs are ASSOCIATIVE hatches (1 source entity
            # per loop): AcDbHatch::evaluateHatch re-derives the loop payload
            # from the boundary sources and RE-FITS the spline chain -- the
            # rebuilt cache differs from the census cache by 10-vs-9 Bezier
            # spans and up to 9.16e-4 (measured after the part-1 algebraic
            # quotient, fixture tests/fixtures/lex0013_dA_pairs.json; the same
            # number the R4x point-cloud proxy reported). Fit noise in a
            # host-derived cache is notation, same category as the *D
            # dimension caches (LEX-0001) and assoc handle identity
            # (LEX-0011): the authored geometry lives in the SOURCE entities,
            # which this same def diff compares exactly (1.dwg splines:
            # 3973/3973 diff0). Canonical form: a loop whose edges are ALL
            # spline-class AND which has a positive assoc source count folds
            # its edge payload to the structural marker
            # [{"type": "spline_chain_derived"}] (loop_type/closed/... keys
            # stay). Blind spot, documented per LEX-0010: a cache that
            # differs while its sources are identical is host-deterministic
            # re-derivation -- exactly the quotiented notation; a REAL
            # boundary change moves the sources and is caught there.
            # Substitute verifier: source-entity diff0 + the point-cloud gate
            # (tools/loops_residue_analysis.py, <=1e-3 measured).
            counts = canon_g.get("assoc_loop_source_counts")
            if isinstance(counts, list) and counts:
                folded: List[Any] = []
                for i, lp in enumerate(new_loops):
                    cnt = counts[i] if i < len(counts) else 0
                    edges = lp.get("edges") if isinstance(lp, dict) else None
                    if (isinstance(cnt, int) and cnt > 0
                            and isinstance(edges, list) and edges
                            and all(isinstance(e, dict)
                                    and e.get("type") in ("spline", "spline_bezier")
                                    for e in edges)):
                        nl = dict(lp)
                        nl["edges"] = [{"type": "spline_chain_derived"}]
                        folded.append(nl)
                    else:
                        folded.append(lp)
                new_loops = folded
            if any(nl is not ol for nl, ol in zip(new_loops, loops)):
                if canon_g is g:
                    canon_g = dict(g)
                canon_g["loops"] = new_loops
        if canon_g is not g:
            if canon is entity:
                canon = dict(entity)
            canon["geometry"] = canon_g
        return canon
    if g.get("kind") == "ellipse":
        canon_g = _canonical_ellipse_geometry(g)
        if canon_g is not g:
            if canon is entity:
                canon = dict(entity)
            canon["geometry"] = canon_g
        return canon
    if g.get("kind") != "spline":
        return canon
    control_points = entity.get("spline_control_points")
    knots = entity.get("spline_knots")
    if not (control_points and knots):
        return canon
    canon_g = dict(g)
    canon_g["control_points"] = control_points
    canon_g["knots"] = knots
    canon_g.pop("fit_points", None)
    if canon is entity:
        canon = dict(entity)
    canon["geometry"] = canon_g
    return canon


def _spline_fit_authored_count(entities: List[Dict[str, Any]]) -> int:
    return sum(1 for e in entities
               if ((e.get("geometry") or {}).get("kind") == "spline"
                   and (e.get("geometry") or {}).get("fit_points")))


def _definition_entities(block_def: Dict[str, Any],
                         name_map: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    entities = block_def.get("def_entities")
    if entities is None:
        entities = block_def.get("entities")
    return [_canonical_entity(e, name_map=name_map)
            for e in (entities or []) if isinstance(e, dict)]


def _definitions_by_name(ir: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for block_def in ir.get("block_definitions") or []:
        if not isinstance(block_def, dict):
            continue
        name = block_def.get("name")
        if isinstance(name, str):
            out[name] = block_def
    return out


def _synthetic_ir(entities: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "schema": cad_diff.IR_SCHEMA_ID,
        "entities": list(entities),
    }


def _kind_counts(definitions: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for block_def in definitions.values():
        for entity in _definition_entities(block_def):
            kind = ((entity.get("geometry") or {}).get("kind")) or ""
            counts[kind] = counts.get(kind, 0) + 1
    return counts


def _split_dim_caches(defs: Dict[str, Dict[str, Any]],
                      ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    kept: Dict[str, Dict[str, Any]] = {}
    caches: Dict[str, Dict[str, Any]] = {}
    for name, block_def in defs.items():
        (caches if _DIM_CACHE_NAME.match(name) else kept)[name] = block_def
    return kept, caches


def _cache_entity_total(caches: Dict[str, Dict[str, Any]]) -> int:
    return sum(len(_definition_entities(d)) for d in caches.values())


def _diff_definition_row(name: str,
                         def_a: Optional[Dict[str, Any]],
                         def_b: Optional[Dict[str, Any]], *,
                         tolerance: float = 1e-6,
                         name_map: Optional[Dict[str, str]] = None,
                         b_name: Optional[str] = None) -> Dict[str, Any]:
    b_name = name if b_name is None else b_name
    raw_a = [e for e in ((def_a or {}).get("def_entities")
                         or (def_a or {}).get("entities") or []) if isinstance(e, dict)]
    raw_b = [e for e in ((def_b or {}).get("def_entities")
                         or (def_b or {}).get("entities") or []) if isinstance(e, dict)]
    ents_a = _definition_entities(def_a, name_map=name_map) if def_a else []
    ents_b = _definition_entities(def_b) if def_b else []
    a_total = len(ents_a)
    b_total = len(ents_b)

    diff = cad_diff.compute_diff(
        _synthetic_ir(ents_a),
        _synthetic_ir(ents_b),
        comparison_basis="geometry",
        geometry_tolerance=tolerance,
        diff_scope=cad_diff.FULL_DATABASE,
    )
    summary = diff["summary"]
    missing_side: Optional[str] = None
    if def_a is None:
        missing_side = "a"
    elif def_b is None:
        missing_side = "b"

    row = {
        "name": name,
        "a_total": a_total,
        "b_total": b_total,
        "diff0": int(summary.get("unchanged", 0) or 0),
        "removed": int(summary.get("removed", 0) or 0),
        "added": int(summary.get("added", 0) or 0),
        "modified": int(summary.get("modified", 0) or 0),
        "missing_side": missing_side,
    }
    if b_name != name:
        row["b_name"] = b_name
    return {
        "row": row,
        "a_total": a_total,
        "b_total": b_total,
        "diff0": row["diff0"],
        "fit_authored_a": _spline_fit_authored_count(raw_a),
        "fit_authored_b": _spline_fit_authored_count(raw_b),
    }


def diff_block_definitions(ir_a: Dict[str, Any], ir_b: Dict[str, Any], *,
                           tolerance: float = 1e-6,
                           name_map: Optional[Dict[str, str]] = None,
                           exclude_derived_caches: bool = True) -> Dict[str, Any]:
    defs_a = _definitions_by_name(ir_a or {})
    defs_b = _definitions_by_name(ir_b or {})

    derived_cache_excluded: Optional[Dict[str, Any]] = None
    if exclude_derived_caches:
        defs_a, caches_a = _split_dim_caches(defs_a)
        defs_b, caches_b = _split_dim_caches(defs_b)
        derived_cache_excluded = {
            "name_pattern": _DIM_CACHE_NAME.pattern,
            "a_def_count": len(caches_a),
            "b_def_count": len(caches_b),
            "a_entity_total": _cache_entity_total(caches_a),
            "b_entity_total": _cache_entity_total(caches_b),
            "reason": "*D anonymous blocks are per-dimension rendered caches; "
                      "a rebuild's dimensions mint fresh *D names, so a "
                      "name-matched def compare is a category error. The "
                      "dimension entities themselves are verified by the L5 "
                      "dim_semantic_gate.",
        }

    per_def: List[Dict[str, Any]] = []
    diff0_total = 0
    a_entity_total = 0
    b_entity_total = 0
    fit_authored_a = 0
    fit_authored_b = 0
    matched_b_names = set()

    for name in sorted(defs_a):
        b_name = (name_map or {}).get(name, name)
        def_a = defs_a.get(name)
        def_b = defs_b.get(b_name)
        if def_b is not None:
            matched_b_names.add(b_name)
        compared = _diff_definition_row(
            name, def_a, def_b, tolerance=tolerance, name_map=name_map, b_name=b_name)
        fit_authored_a += compared["fit_authored_a"]
        fit_authored_b += compared["fit_authored_b"]
        a_entity_total += compared["a_total"]
        b_entity_total += compared["b_total"]
        diff0_total += compared["diff0"]
        per_def.append(compared["row"])

    for b_name in sorted(name for name in defs_b if name not in matched_b_names):
        def_b = defs_b.get(b_name)
        compared = _diff_definition_row(
            b_name, None, def_b, tolerance=tolerance, b_name=b_name)
        fit_authored_b += compared["fit_authored_b"]
        b_entity_total += compared["b_total"]
        per_def.append(compared["row"])

    by_kind_a = _kind_counts(defs_a)
    by_kind_b = _kind_counts(defs_b)
    by_kind_gap = {
        kind: {"a_count": by_kind_a.get(kind, 0), "b_count": by_kind_b.get(kind, 0)}
        for kind in sorted(set(by_kind_a) | set(by_kind_b))
    }

    return {
        "schema": SCHEMA_ID,
        "per_def": per_def,
        "totals": {
            "a_def_count": len(defs_a),
            "b_def_count": len(defs_b),
            "a_entity_total": a_entity_total,
            "b_entity_total": b_entity_total,
            "diff0_total": diff0_total,
            "interior_diff0_fraction": (
                (float(diff0_total) / float(a_entity_total)) if a_entity_total else None
            ),
            # Fit-authoring parity (honest annotation): splines compare on the
            # canonical control/knot definition; a-side fit authoring data that
            # the rebuild does not restore shows up as fit_authored_a > _b.
            "spline_fit_authored_a": fit_authored_a,
            "spline_fit_authored_b": fit_authored_b,
            # Honest accounting of what the comparison deliberately skipped
            # (None when exclude_derived_caches=False).
            "derived_cache_excluded": derived_cache_excluded,
        },
        "by_kind_gap": by_kind_gap,
    }


def diff_block_definitions_partial(census_ir: Dict[str, Any],
                                   post_ir: Dict[str, Any],
                                   def_names: Iterable[str], *,
                                   name_map: Optional[Dict[str, str]] = None,
                                   exclude_derived_caches: bool = True) -> Dict[str, Any]:
    requested = list(def_names or [])
    defs_a_all = _definitions_by_name(census_ir or {})
    defs_b_all = _definitions_by_name(post_ir or {})
    defs_a = defs_a_all
    defs_b = defs_b_all
    if exclude_derived_caches:
        defs_a, _caches_a = _split_dim_caches(defs_a_all)
        defs_b, _caches_b = _split_dim_caches(defs_b_all)

    missing: List[Dict[str, str]] = []
    per_def: List[Dict[str, Any]] = []
    compared = 0
    a_entity_total = 0
    b_entity_total = 0
    diff0_total = 0
    seen = set()

    for name in requested:
        if name in seen:
            continue
        seen.add(name)
        if exclude_derived_caches and name in defs_a_all and _DIM_CACHE_NAME.match(name):
            missing.append({
                "name": name,
                "reason": "excluded_derived_cache",
            })
            continue
        def_a = defs_a.get(name)
        if def_a is None:
            missing.append({
                "name": name,
                "reason": "not_found",
            })
            continue
        b_name = (name_map or {}).get(name, name)
        compared_row = _diff_definition_row(
            name, def_a, defs_b.get(b_name), name_map=name_map, b_name=b_name)
        per_def.append(compared_row["row"])
        compared += 1
        a_entity_total += compared_row["a_total"]
        b_entity_total += compared_row["b_total"]
        diff0_total += compared_row["diff0"]

    return {
        "schema": "ariadne.blockdef_diff.partial.v1",
        "per_def": per_def,
        "partial": {
            "requested": requested,
            "compared": compared,
            "missing": missing,
        },
        "totals": {
            "a_entity_total": a_entity_total,
            "b_entity_total": b_entity_total,
            "diff0_total": diff0_total,
        },
    }


def _md_table(headers: List[str], rows: List[List[Any]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")
    return "\n".join(out)


def _render_markdown(report: Dict[str, Any]) -> str:
    per_def = sorted(
        report.get("per_def") or [],
        key=lambda row: (-(int(row.get("a_total", 0)) - int(row.get("diff0", 0))), row.get("name", "")),
    )[:40]
    totals = report.get("totals") or {}
    kind_gap = report.get("by_kind_gap") or {}

    excluded = totals.get("derived_cache_excluded") or {}
    parts = [
        "# Block Definition Diff",
        "",
        "## Totals",
        "",
        _md_table(
            ["a_def_count", "b_def_count", "a_entity_total", "b_entity_total", "diff0_total", "interior_diff0_fraction"],
            [[
                totals.get("a_def_count"),
                totals.get("b_def_count"),
                totals.get("a_entity_total"),
                totals.get("b_entity_total"),
                totals.get("diff0_total"),
                totals.get("interior_diff0_fraction"),
            ]],
        ),
        "",
        ("Derived caches excluded (`%s`): a=%s defs/%s ents, b=%s defs/%s ents"
         % (excluded.get("name_pattern"), excluded.get("a_def_count"),
            excluded.get("a_entity_total"), excluded.get("b_def_count"),
            excluded.get("b_entity_total"))) if excluded else
        "Derived caches excluded: (none -- legacy full compare)",
        "",
        "## Per Definition",
        "",
        _md_table(
            ["name", "a_total", "b_total", "diff0", "removed", "added", "modified", "missing_side"],
            [[
                row.get("name"),
                row.get("a_total"),
                row.get("b_total"),
                row.get("diff0"),
                row.get("removed"),
                row.get("added"),
                row.get("modified"),
                row.get("missing_side"),
            ] for row in per_def],
        ),
        "",
        "## By Kind Gap",
        "",
        _md_table(
            ["kind", "a_count", "b_count"],
            [[kind, counts.get("a_count"), counts.get("b_count")] for kind, counts in kind_gap.items()],
        ),
        "",
    ]
    return "\n".join(parts)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Per-block-definition geometry diff over two IR JSON files.")
    parser.add_argument("ir_a")
    parser.add_argument("ir_b")
    parser.add_argument("--out-json", dest="out_json")
    parser.add_argument("--out-md", dest="out_md")
    parser.add_argument("--include-derived-caches", action="store_true",
                        help="legacy full compare: keep *D dimension-cache "
                             "defs in the name-matched comparison")
    args = parser.parse_args(argv)

    if not os.path.exists(args.ir_a) or not os.path.exists(args.ir_b):
        return 3

    report = diff_block_definitions(
        _load_json(args.ir_a), _load_json(args.ir_b),
        exclude_derived_caches=not args.include_derived_caches)

    if args.out_json:
        _write_json(args.out_json, report)
    if args.out_md:
        with open(args.out_md, "w", encoding="utf-8") as fh:
            fh.write(_render_markdown(report))

    if not args.out_json and not args.out_md:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
