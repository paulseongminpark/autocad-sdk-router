#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Match DWG graph IR entity lineage by additive stable identity."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import ir_builder

REPORT_SCHEMA = "ariadne.ir_identity_report.v1"


def load_ir(path) -> dict:
    """Load an IR JSON document (BOM-tolerant)."""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _prepare_ir(ir: dict) -> dict:
    """Clone an IR doc and ensure stable identity fields exist."""
    prepared = copy.deepcopy(ir or {})
    ir_builder.apply_stable_entity_identity(prepared)
    return prepared


def _entity_key(entity: dict):
    return (
        str(entity.get("stable_id", "") or ""),
        int(entity.get("stable_id_ordinal", 0) or 0),
    )


def _index_entities(ir: dict) -> dict:
    return {_entity_key(entity): entity for entity in (ir.get("entities") or [])}


def match_ir_documents(pre_ir: dict, post_ir: dict) -> dict:
    """Match two IR docs by stable_id + stable_id_ordinal and return a lineage report."""
    pre = _prepare_ir(pre_ir)
    post = _prepare_ir(post_ir)
    pre_by_key = _index_entities(pre)
    post_by_key = _index_entities(post)
    keys = sorted(set(pre_by_key) | set(post_by_key))

    lineage = []
    matched = 0
    moved = 0
    added = 0
    removed = 0

    for key in keys:
        before = pre_by_key.get(key)
        after = post_by_key.get(key)
        exemplar = after or before or {}
        if before and after:
            matched += 1
            status = "matched"
            if (before.get("handle") or "") != (after.get("handle") or ""):
                moved += 1
                status = "moved"
        elif before:
            removed += 1
            status = "removed"
        else:
            added += 1
            status = "added"
        lineage.append({
            "stable_id": key[0],
            "stable_id_ordinal": key[1],
            "status": status,
            "dxf_name": exemplar.get("dxf_name", ""),
            "layer": exemplar.get("layer", ""),
            "pre_handle": (before or {}).get("handle"),
            "post_handle": (after or {}).get("handle"),
        })

    return {
        "schema": REPORT_SCHEMA,
        "summary": {
            "matched": matched,
            "added": added,
            "removed": removed,
            "moved": moved,
            "unchanged_handle": matched - moved,
            "entity_count_pre": len(pre.get("entities") or []),
            "entity_count_post": len(post.get("entities") or []),
        },
        "diagnostics": {
            "comparison_basis": "stable_id_plus_ordinal",
            "stable_id_float_epsilon": ir_builder.STABLE_ID_FLOAT_EPSILON,
            "pre_ir_version": pre.get("ir_version"),
            "post_ir_version": post.get("ir_version"),
        },
        "lineage": lineage,
    }


def match_ir_paths(pre_path: str, post_path: str) -> dict:
    """Load two IR paths and return a stable-identity lineage report."""
    report = match_ir_documents(load_ir(pre_path), load_ir(post_path))
    report["pre_ref"] = str(Path(pre_path))
    report["post_ref"] = str(Path(post_path))
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Match two IR JSON files by stable identity.")
    parser.add_argument("--pre", required=True, help="Path to the BEFORE IR JSON.")
    parser.add_argument("--post", required=True, help="Path to the AFTER IR JSON.")
    parser.add_argument("--out", required=True, help="Path to write the lineage report JSON.")
    args = parser.parse_args(argv)

    report = match_ir_paths(args.pre, args.post)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
