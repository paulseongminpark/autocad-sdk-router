#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_fragments -- deterministic merge of worker op-fragments into config/operations.v2.json.

Orchestrator-facing utility: each worker drops ONE op-entry JSON file into
reports/ops_fragments/. merge_fragments() folds any not-yet-present ids into
operations[], recomputes the registry header count fields, and writes the
result back (unless dry_run=True).
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict


def merge_fragments(registry_path, fragments_dir, dry_run: bool = False) -> Dict[str, Any]:
    registry_path = Path(registry_path)
    fragments_dir = Path(fragments_dir)

    with registry_path.open("r", encoding="utf-8-sig") as f:
        registry = json.load(f)

    operations = registry["operations"]
    existing_ids = {op["id"] for op in operations}

    added = []
    skipped = []

    if fragments_dir.is_dir():
        fragment_paths = sorted(fragments_dir.glob("*.json"))
    else:
        fragment_paths = []

    for fragment_path in fragment_paths:
        with fragment_path.open("r", encoding="utf-8-sig") as f:
            fragment = json.load(f)
        op_id = fragment["id"]
        if op_id in existing_ids:
            skipped.append(op_id)
            continue
        operations.append(fragment)
        existing_ids.add(op_id)
        added.append(op_id)

    by_status = Counter(op.get("status") for op in operations)
    by_family = Counter(op.get("family") for op in operations)
    by_engine_tier = Counter(op.get("engine_tier") for op in operations)

    implemented = by_status.get("implemented", 0)
    blocked = by_status.get("blocked", 0)

    registry["totals"]["operations"] = len(operations)
    registry["totals"]["by_status"]["implemented"] = implemented
    registry["totals"]["by_status"]["blocked"] = blocked
    registry["totals"]["by_family"] = dict(by_family)
    registry["totals"]["by_engine_tier"] = dict(by_engine_tier)

    registry["coverage"]["operation_records"] = len(operations)
    registry["coverage"]["implemented"] = implemented
    registry["coverage"]["blocked"] = blocked

    if not dry_run:
        with registry_path.open("w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return {
        "added": added,
        "skipped": skipped,
        "total_ops": len(operations),
        "by_status": dict(by_status),
    }
