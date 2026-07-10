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

    # Orphan-assoc quotient (LEX-0008, R4r runs/e2e_1dwg_R4r_assoc_20260710):
    # is_associative is a DERIVED flag -- it only has semantics when boundary
    # source refs exist. 1.dwg carries 66 hatches with the flag set and NO
    # sources anywhere (3-way probe: getAssocObjIds 0/66, getAssocObjIdsAt
    # 0/66, LibreDWG DXF no group 97/330), and the engine RESETS a sourceless
    # flag on save (R4r measured: job True -> saved False, all 66). A state
    # no engine path can reproduce is notation, not geometry: when a hatch
    # has no assoc_source_handles the flag is dropped from comparison on
    # BOTH sides. Hatches with real sources keep the flag AND compare the
    # handle payload. Substitute verifier: visual gate (associativity has
    # no render effect) + assoc_source_handles round-trip when present.
    if "is_associative" in canon_g and not g.get("assoc_source_handles"):
        canon_g.pop("is_associative")
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
            nrow["angle"] = round(row["angle"], 6)  # angle is never scaled
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
    if g.get("kind") == "hatch" and g.get("pattern_definitions"):
        canon_g = _canonical_hatch_geometry(g)
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
