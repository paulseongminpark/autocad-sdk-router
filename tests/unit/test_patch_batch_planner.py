#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for the prototype patch batch planner."""
from __future__ import annotations

import copy
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import patch_batch_planner  # noqa: E402


def _op(name: str) -> dict:
    return {"operation": name, "args": {}, "step_id": "s_%s" % name}


def _create_block(name: str) -> dict:
    return {"operation": "create_block", "args": {"name": name}, "step_id": "s_create_%s" % name}


def _append_block(name: str) -> dict:
    return {
        "operation": "append_block_entity",
        "args": {"block_name": name, "entity": {"kind": "line"}},
        "step_id": "s_append_%s" % name,
    }


class TestPlanBatches(unittest.TestCase):
    def test_preserves_global_order_across_batches(self):
        operations = [
            _op("create_line"),
            _op("create_circle"),
            _create_block("DOOR"),
            _append_block("DOOR"),
            _append_block("DOOR"),
            _op("create_text"),
        ]
        plan = patch_batch_planner.plan_batches(operations, max_ops_per_batch=3)
        self.assertEqual(plan["schema"], patch_batch_planner.SCHEMA)
        self.assertEqual(
            [op_index for batch in plan["batches"] for op_index in batch["op_indices"]],
            list(range(len(operations))),
        )
        self.assertEqual([batch["batch_id"] for batch in plan["batches"]], ["b000", "b001", "b002"])
        self.assertEqual(plan["totals"], {"op_count": 6, "batch_count": 3})
        self.assertEqual(patch_batch_planner.validate_plan(plan, operations), [])

    def test_block_definition_group_is_never_split(self):
        operations = [
            _op("create_line"),
            _create_block("DOOR"),
            _append_block("DOOR"),
            _append_block("DOOR"),
            _op("create_text"),
        ]
        plan = patch_batch_planner.plan_batches(operations, max_ops_per_batch=3)
        self.assertEqual([batch["op_indices"] for batch in plan["batches"]], [[0], [1, 2, 3], [4]])
        self.assertEqual(plan["atomic_groups"][0]["block_name"], "DOOR")
        self.assertEqual(plan["atomic_groups"][0]["op_indices"], [1, 2, 3])
        self.assertNotIn("oversized", plan["batches"][1])

    def test_oversized_block_group_gets_its_own_flagged_batch(self):
        operations = [
            _op("create_line"),
            _create_block("DOOR"),
            _append_block("DOOR"),
            _append_block("DOOR"),
            _op("create_text"),
        ]
        plan = patch_batch_planner.plan_batches(operations, max_ops_per_batch=2)
        self.assertEqual([batch["op_indices"] for batch in plan["batches"]], [[0], [1, 2, 3], [4]])
        self.assertTrue(plan["batches"][1]["oversized"])
        self.assertEqual(patch_batch_planner.validate_plan(plan, operations), [])

    def test_exact_max_ops_boundary_stays_in_one_batch(self):
        operations = [
            _create_block("DOOR"),
            _append_block("DOOR"),
            _append_block("DOOR"),
            _op("create_text"),
            _op("create_circle"),
        ]
        plan = patch_batch_planner.plan_batches(operations, max_ops_per_batch=5)
        self.assertEqual(len(plan["batches"]), 1)
        self.assertEqual(plan["batches"][0]["op_count"], 5)
        self.assertEqual(plan["batches"][0]["op_indices"], [0, 1, 2, 3, 4])

    def test_validate_plan_catches_tampering(self):
        operations = [
            _op("create_line"),
            _create_block("DOOR"),
            _append_block("DOOR"),
            _append_block("DOOR"),
            _op("create_text"),
        ]
        plan = patch_batch_planner.plan_batches(operations, max_ops_per_batch=3)

        dropped = copy.deepcopy(plan)
        dropped["batches"][2]["op_indices"] = []
        dropped["batches"][2]["op_count"] = 0
        violations = patch_batch_planner.validate_plan(dropped, operations)
        self.assertTrue(any("missing op indices" in violation for violation in violations))

        reordered = copy.deepcopy(plan)
        reordered["batches"][1]["op_indices"] = [2, 1, 3]
        violations = patch_batch_planner.validate_plan(reordered, operations)
        self.assertTrue(any("original order" in violation for violation in violations))

        split_group = copy.deepcopy(plan)
        split_group["batches"][1]["op_indices"] = [1, 2]
        split_group["batches"][1]["op_count"] = 2
        split_group["batches"][2]["op_indices"] = [3, 4]
        split_group["batches"][2]["op_count"] = 2
        violations = patch_batch_planner.validate_plan(split_group, operations)
        self.assertTrue(any("atomic group split across batches" in violation for violation in violations))

    def test_empty_operations(self):
        plan = patch_batch_planner.plan_batches([], max_ops_per_batch=4)
        self.assertEqual(plan["batches"], [])
        self.assertEqual(plan["atomic_groups"], [])
        self.assertEqual(plan["totals"], {"op_count": 0, "batch_count": 0})
        self.assertEqual(patch_batch_planner.validate_plan(plan, []), [])


if __name__ == "__main__":
    unittest.main()
