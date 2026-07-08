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


def _definition_entities(block_def: Dict[str, Any]) -> List[Dict[str, Any]]:
    entities = block_def.get("def_entities")
    if entities is None:
        entities = block_def.get("entities")
    return [e for e in (entities or []) if isinstance(e, dict)]


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
                           tolerance: float = 1e-6) -> Dict[str, Any]:
    defs_a = _definitions_by_name(ir_a or {})
    defs_b = _definitions_by_name(ir_b or {})

    per_def: List[Dict[str, Any]] = []
    diff0_total = 0
    a_entity_total = 0
    b_entity_total = 0

    for name in sorted(set(defs_a) | set(defs_b)):
        def_a = defs_a.get(name)
        def_b = defs_b.get(name)
        ents_a = _definition_entities(def_a) if def_a else []
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
        per_def.append({
            "name": name,
            "a_total": a_total,
            "b_total": b_total,
            "diff0": diff0,
            "removed": int(summary.get("removed", 0) or 0),
            "added": int(summary.get("added", 0) or 0),
            "modified": int(summary.get("modified", 0) or 0),
            "missing_side": missing_side,
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
