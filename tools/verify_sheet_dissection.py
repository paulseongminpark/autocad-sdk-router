#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Per-sheet block-dissection verifier over dwg_graph_ir.v1 documents."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

_JSON_ENCODING = "utf-8-sig"
SCHEMA_ID = "ariadne.sheet_dissection_report.v1"


def load_ir(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _def_entity_counts(ir: Dict[str, Any]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for block_def in ir.get("block_definitions") or []:
        if not isinstance(block_def, dict):
            continue
        name = block_def.get("name")
        if not name:
            continue
        out[str(name)] = len(block_def.get("def_entities") or [])
    return out


def _insert_records(ir: Dict[str, Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for entity in ir.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        geometry = entity.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("kind") != "block_reference":
            continue
        block_name = geometry.get("block_name")
        if not block_name:
            continue
        space = entity.get("space") or "model"
        layout = entity.get("layout") if space == "paper" else None
        sheet = layout or ("__model__" if space == "model" else "__%s__" % (space,))
        records.append({
            "block_name": str(block_name),
            "sheet": str(sheet),
        })
    return records


def _insert_counts(ir: Dict[str, Any], def_counts: Dict[str, int]) -> Dict[str, Dict[str, int]]:
    counts: Dict[str, Dict[str, int]] = {}
    for record in _insert_records(ir):
        block_name = record["block_name"]
        entry = counts.setdefault(block_name, {
            "insert_count": 0,
            "def_entities": def_counts.get(block_name, 0),
        })
        entry["insert_count"] += 1
    return counts


def _sheet_counts(ir: Dict[str, Any], def_counts: Dict[str, int]) -> Dict[str, Dict[str, int]]:
    sheets: Dict[str, Dict[str, int]] = {}
    for record in _insert_records(ir):
        sheet = record["sheet"]
        block_name = record["block_name"]
        entry = sheets.setdefault(sheet, {})
        entry[block_name] = entry.get(block_name, 0) + def_counts.get(block_name, 0)
    return sheets


def _bbox_degenerate_warnings(ir: Dict[str, Any], def_counts: Dict[str, int]) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []
    for block_def in ir.get("block_definitions") or []:
        if not isinstance(block_def, dict):
            continue
        block_name = block_def.get("name")
        if not block_name or def_counts.get(str(block_name), 0) <= 0:
            continue
        bbox = block_def.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 6:
            continue
        try:
            width = float(bbox[3]) - float(bbox[0])
            height = float(bbox[4]) - float(bbox[1])
        except (TypeError, ValueError):
            continue
        if width == 0.0 and height == 0.0:
            warnings.append({
                "block_name": str(block_name),
                "def_entities": def_counts[str(block_name)],
                "bbox": bbox,
                "reason": "bbox area is 0 while def_entities > 0",
            })
    return warnings


def analyze(original_ir: Dict[str, Any], replay_ir: Dict[str, Any], threshold: int = 0) -> Dict[str, Any]:
    original_defs = _def_entity_counts(original_ir)
    replay_defs = _def_entity_counts(replay_ir)
    original_inserts = _insert_counts(original_ir, original_defs)
    replay_inserts = _insert_counts(replay_ir, replay_defs)
    original_sheets = _sheet_counts(original_ir, original_defs)
    replay_sheets = _sheet_counts(replay_ir, replay_defs)

    all_blocks = sorted(set(original_inserts) | set(replay_inserts))
    insert_comparison: Dict[str, Any] = {}
    missing_block_count = 0
    new_block_count = 0
    def_entity_delta_total = 0
    for block_name in all_blocks:
        left = original_inserts.get(block_name, {"insert_count": 0, "def_entities": original_defs.get(block_name, 0)})
        right = replay_inserts.get(block_name, {"insert_count": 0, "def_entities": replay_defs.get(block_name, 0)})
        delta = {
            "insert_count": right["insert_count"] - left["insert_count"],
            "def_entities": right["def_entities"] - left["def_entities"],
        }
        if left["insert_count"] > 0 and right["insert_count"] == 0:
            missing_block_count += 1
        if left["insert_count"] == 0 and right["insert_count"] > 0:
            new_block_count += 1
        def_entity_delta_total += abs(delta["def_entities"])
        insert_comparison[block_name] = {
            "original": left,
            "replay": right,
            "delta": delta,
        }

    per_sheet: Dict[str, Any] = {}
    for sheet in sorted(set(original_sheets) | set(replay_sheets)):
        left = original_sheets.get(sheet, {})
        right = replay_sheets.get(sheet, {})
        left_blocks = set(left)
        right_blocks = set(right)
        per_sheet[sheet] = {
            "missing_blocks": sorted(left_blocks - right_blocks),
            "new_blocks": sorted(right_blocks - left_blocks),
            "def_entity_delta": sum(right.get(name, 0) - left.get(name, 0)
                                     for name in set(left) | set(right)),
        }

    degenerate = _bbox_degenerate_warnings(original_ir, original_defs) + _bbox_degenerate_warnings(replay_ir, replay_defs)
    total_issues = missing_block_count + len(degenerate)
    exit_code = 1 if total_issues > threshold else 0

    return {
        "schema": SCHEMA_ID,
        "threshold": threshold,
        "def_entity_counts": {
            "original": original_defs,
            "replay": replay_defs,
        },
        "insert_comparison": insert_comparison,
        "per_sheet": per_sheet,
        "warnings": {
            "bbox_degenerate": degenerate,
        },
        "summary": {
            "missing_block_count": missing_block_count,
            "new_block_count": new_block_count,
            "def_entity_delta_total": def_entity_delta_total,
            "degenerate_bbox_count": len(degenerate),
            "total_issues": total_issues,
            "exit_code": exit_code,
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare original vs replay IR per sheet to catch block-definition loss."
    )
    parser.add_argument("original_ir", help="Path to the original dwg_graph_ir.v1 JSON")
    parser.add_argument("replay_ir", help="Path to the replay/regenerated dwg_graph_ir.v1 JSON")
    parser.add_argument("--report", help="Optional path to write the JSON report")
    parser.add_argument("--threshold", type=int, default=0,
                        help="Allow up to N issues before exiting 1 (default: 0)")
    args = parser.parse_args(argv)

    for path in (args.original_ir, args.replay_ir):
        if not os.path.isfile(path):
            print("error: IR file not found: %s" % path, file=sys.stderr)
            return 3

    report = analyze(load_ir(args.original_ir), load_ir(args.replay_ir), threshold=args.threshold)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    print(
        "sheet_dissection issues=%d missing_blocks=%d degenerate_bbox=%d threshold=%d"
        % (
            report["summary"]["total_issues"],
            report["summary"]["missing_block_count"],
            report["summary"]["degenerate_bbox_count"],
            args.threshold,
        )
    )
    return int(report["summary"]["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
