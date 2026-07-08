#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Per-block-definition geometry diff over DWG graph IRs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Optional

import cad_diff

_JSON_ENCODING = "utf-8-sig"
SCHEMA_ID = "ariadne.blockdef_diff.v1"


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


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


def diff_block_definitions(ir_a: Dict[str, Any], ir_b: Dict[str, Any], *,
                           tolerance: float = 1e-6,
                           name_map: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    defs_a = _definitions_by_name(ir_a or {})
    defs_b = _definitions_by_name(ir_b or {})

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
        raw_a = [e for e in ((def_a or {}).get("def_entities")
                             or (def_a or {}).get("entities") or []) if isinstance(e, dict)]
        raw_b = [e for e in ((def_b or {}).get("def_entities")
                             or (def_b or {}).get("entities") or []) if isinstance(e, dict)]
        fit_authored_a += _spline_fit_authored_count(raw_a)
        fit_authored_b += _spline_fit_authored_count(raw_b)
        ents_a = _definition_entities(def_a, name_map=name_map) if def_a else []
        ents_b = _definition_entities(def_b) if def_b else []
        a_total = len(ents_a)
        b_total = len(ents_b)
        a_entity_total += a_total
        b_entity_total += b_total

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

        diff0 = int(summary.get("unchanged", 0) or 0)
        diff0_total += diff0
        row = {
            "name": name,
            "a_total": a_total,
            "b_total": b_total,
            "diff0": diff0,
            "removed": int(summary.get("removed", 0) or 0),
            "added": int(summary.get("added", 0) or 0),
            "modified": int(summary.get("modified", 0) or 0),
            "missing_side": missing_side,
        }
        if b_name != name:
            row["b_name"] = b_name
        per_def.append(row)

    for b_name in sorted(name for name in defs_b if name not in matched_b_names):
        def_b = defs_b.get(b_name)
        raw_b = [e for e in ((def_b or {}).get("def_entities")
                             or (def_b or {}).get("entities") or []) if isinstance(e, dict)]
        fit_authored_b += _spline_fit_authored_count(raw_b)
        ents_b = _definition_entities(def_b) if def_b else []
        b_total = len(ents_b)
        b_entity_total += b_total

        diff = cad_diff.compute_diff(
            _synthetic_ir([]),
            _synthetic_ir(ents_b),
            comparison_basis="geometry",
            geometry_tolerance=tolerance,
            diff_scope=cad_diff.FULL_DATABASE,
        )
        summary = diff["summary"]
        per_def.append({
            "name": b_name,
            "a_total": 0,
            "b_total": b_total,
            "diff0": int(summary.get("unchanged", 0) or 0),
            "removed": int(summary.get("removed", 0) or 0),
            "added": int(summary.get("added", 0) or 0),
            "modified": int(summary.get("modified", 0) or 0),
            "missing_side": "a",
        })

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
        },
        "by_kind_gap": by_kind_gap,
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
    args = parser.parse_args(argv)

    if not os.path.exists(args.ir_a) or not os.path.exists(args.ir_b):
        return 3

    report = diff_block_definitions(_load_json(args.ir_a), _load_json(args.ir_b))

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
