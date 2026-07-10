#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prototype batch planner for staged patch execution.

Design contract for the future `tools.patch_engine.apply_staged` consumer:
`plan_batches()` would be called over the patch's ordered operations, then the
engine would launch one native CAD job plus one generated script per batch
instead of one `accoreconsole` process per operation. Per-op status would still
be reported individually from inside that batch job, so the staged-write
journal remains operation-granular even when execution is process-batched.

This does not change the staged-only lifecycle or the original-immutability
invariants already enforced by `apply_staged`: batches would still mutate only
the staged copy, and the source DWG would remain untouched.

This module is NOT wired into `patch_engine` yet. It is a pure planning and
validation prototype only.
"""
from __future__ import annotations

import collections
from typing import Any, Dict, List

SCHEMA = "ariadne.patch_batch_plan.v1"


def _require_max_ops_per_batch(max_ops_per_batch: int) -> None:
    if not isinstance(max_ops_per_batch, int) or max_ops_per_batch <= 0:
        raise ValueError("max_ops_per_batch must be a positive integer")


def _block_group_name(op: Dict[str, Any]) -> str | None:
    if op.get("operation") != "create_block":
        return None
    args = op.get("args")
    if not isinstance(args, dict):
        return None
    name = args.get("name")
    return name if isinstance(name, str) and name else None


def _is_matching_block_append(op: Dict[str, Any], block_name: str) -> bool:
    if op.get("operation") != "append_block_entity":
        return False
    args = op.get("args")
    if not isinstance(args, dict):
        return False
    return args.get("block_name") == block_name


def _detect_atomic_groups(operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []
    index = 0
    while index < len(operations):
        block_name = _block_group_name(operations[index])
        if block_name is None:
            index += 1
            continue
        op_indices = [index]
        index += 1
        while index < len(operations) and _is_matching_block_append(operations[index], block_name):
            op_indices.append(index)
            index += 1
        groups.append({
            "group_id": "g%03d" % len(groups),
            "group_type": "block_definition",
            "block_name": block_name,
            "start_index": op_indices[0],
            "end_index": op_indices[-1],
            "op_indices": op_indices,
            "op_count": len(op_indices),
        })
    return groups


def _batch_units(
    operations: List[Dict[str, Any]],
    atomic_groups: List[Dict[str, Any]],
) -> List[List[int]]:
    groups_by_start = {group["start_index"]: group for group in atomic_groups}
    units: List[List[int]] = []
    index = 0
    while index < len(operations):
        group = groups_by_start.get(index)
        if group is None:
            units.append([index])
            index += 1
            continue
        units.append(list(group["op_indices"]))
        index = group["end_index"] + 1
    return units


def _is_relink_barrier_op(op: Dict[str, Any]) -> bool:
    """Relink ops translate CENSUS handles through the engine's handle ledger
    at batch-PREP time, so every append whose new_handle they need must be in
    a STRICTLY EARLIER batch (the ledger is parsed from a batch's results only
    after that whole batch ran). A batch mixing appends with relinks would
    translate against a ledger that cannot contain those appends yet."""
    return op.get("operation") == "relink_hatch_assoc"


def _make_batch(batch_number: int, op_indices: List[int], *, oversized: bool = False) -> Dict[str, Any]:
    batch = {
        "batch_id": "b%03d" % batch_number,
        "op_indices": list(op_indices),
        "op_count": len(op_indices),
    }
    if oversized:
        batch["oversized"] = True
    return batch


def plan_batches(
    operations: List[Dict[str, Any]],
    *,
    max_ops_per_batch: int = 100,
) -> Dict[str, Any]:
    _require_max_ops_per_batch(max_ops_per_batch)
    atomic_groups = _detect_atomic_groups(operations)
    units = _batch_units(operations, atomic_groups)
    batches: List[Dict[str, Any]] = []
    current: List[int] = []
    current_is_relink = False
    for unit in units:
        unit_size = len(unit)
        unit_is_relink = _is_relink_barrier_op(operations[unit[0]])
        if current and unit_is_relink != current_is_relink:
            # relink barrier: never share a batch across the append/relink
            # boundary (see _is_relink_barrier_op).
            batches.append(_make_batch(len(batches), current))
            current = []
        current_is_relink = unit_is_relink
        if unit_size > max_ops_per_batch:
            if current:
                batches.append(_make_batch(len(batches), current))
                current = []
            batches.append(_make_batch(len(batches), unit, oversized=True))
            continue
        if current and len(current) + unit_size > max_ops_per_batch:
            batches.append(_make_batch(len(batches), current))
            current = []
        current.extend(unit)
    if current:
        batches.append(_make_batch(len(batches), current))
    return {
        "schema": SCHEMA,
        "max_ops_per_batch": max_ops_per_batch,
        "batches": batches,
        "atomic_groups": atomic_groups,
        "totals": {
            "op_count": len(operations),
            "batch_count": len(batches),
        },
    }


def validate_plan(plan: Dict[str, Any], operations: List[Dict[str, Any]]) -> List[str]:
    violations: List[str] = []
    if plan.get("schema") != SCHEMA:
        violations.append("schema mismatch")
    batches = plan.get("batches")
    if not isinstance(batches, list):
        return violations + ["batches must be a list"]

    flattened: List[int] = []
    batch_for_index: Dict[int, str] = {}
    for batch_number, batch in enumerate(batches):
        op_indices = batch.get("op_indices")
        if not isinstance(op_indices, list):
            violations.append("batch %d op_indices must be a list" % batch_number)
            continue
        if batch.get("op_count") != len(op_indices):
            violations.append("batch %d op_count mismatch" % batch_number)
        batch_id = batch.get("batch_id", "b%03d" % batch_number)
        for op_index in op_indices:
            if not isinstance(op_index, int):
                violations.append("batch %s has non-integer op index %r" % (batch_id, op_index))
                continue
            flattened.append(op_index)
            batch_for_index[op_index] = str(batch_id)

    expected = list(range(len(operations)))
    counts = collections.Counter(flattened)
    missing = [op_index for op_index in expected if counts[op_index] == 0]
    extras = sorted(op_index for op_index in counts if op_index not in expected)
    duplicates = sorted(op_index for op_index, count in counts.items() if count > 1)
    if missing:
        violations.append("missing op indices: %s" % missing)
    if extras:
        violations.append("out-of-range op indices: %s" % extras)
    if duplicates:
        violations.append("duplicate op indices: %s" % duplicates)
    if flattened != expected:
        violations.append("op indices are not in original order")

    expected_groups = _detect_atomic_groups(operations)
    atomic_groups = plan.get("atomic_groups")
    if not isinstance(atomic_groups, list):
        violations.append("atomic_groups must be a list")
    else:
        expected_group_indices = [group["op_indices"] for group in expected_groups]
        actual_group_indices = [group.get("op_indices") for group in atomic_groups]
        if actual_group_indices != expected_group_indices:
            violations.append("atomic_groups metadata does not match operations")
    for group in expected_groups:
        memberships = {batch_for_index.get(op_index) for op_index in group["op_indices"]}
        memberships.discard(None)
        if len(memberships) > 1:
            violations.append(
                "atomic group split across batches for block %r: %s"
                % (group["block_name"], group["op_indices"])
            )

    for batch_number, batch in enumerate(batches):
        op_indices = batch.get("op_indices")
        if not isinstance(op_indices, list):
            continue
        kinds_in_batch = {
            _is_relink_barrier_op(operations[i])
            for i in op_indices
            if isinstance(i, int) and 0 <= i < len(operations)
        }
        if len(kinds_in_batch) > 1:
            violations.append(
                "batch %s mixes relink ops with non-relink ops (handle ledger "
                "cannot cover same-batch appends)" % batch.get("batch_id", batch_number))

    totals = plan.get("totals")
    if not isinstance(totals, dict):
        violations.append("totals must be a dict")
    else:
        if totals.get("op_count") != len(operations):
            violations.append("totals.op_count mismatch")
        if totals.get("batch_count") != len(batches):
            violations.append("totals.batch_count mismatch")
    if plan.get("max_ops_per_batch") != plan.get("max_ops_per_batch"):
        violations.append("max_ops_per_batch mismatch")
    return violations


__all__ = ["SCHEMA", "plan_batches", "validate_plan"]
