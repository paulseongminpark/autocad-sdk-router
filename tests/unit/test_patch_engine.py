#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lane E TEST -- patch_engine: schema validation, risk, dry-run plan, write-original guard.

Intent (WHY -- this module is a SAFETY shell, so the tests are safety assertions):
  * validate_patch_schema must accept a well-formed cad_patch.v1 and REJECT the
    structural violations that matter for safety: missing staged_path,
    staged_path == original_path, and policy.staged_copy != true. If validation
    let those through, the original-DWG-read-only invariant could be breached.
  * classify_patch_risk must escalate destructive ops (delete) and BLOCK any
    patch whose write_mode targets the original/active doc.
  * dry_run_plan must return a PLAN whose execution is ALWAYS 'not_implemented'
    (no destructive writes in this packet) -- a fake 'executed' would be the
    worst possible failure here.
  * The write_original guard must REJECT a patch that targets the original.
    This is the load-bearing no-fake-success / safety gate and it must be able
    to actually fire (Rule 9: a guard that can't reject is theater).

No DWG is touched; patches are in-memory dicts pointing at staging/ paths.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _good_patch():
    return {
        "schema": "ariadne.cad_patch.v1",
        "patch_id": "test-patch-0001",
        "title": "test patch",
        "target_dwg": {
            "staged_path": os.path.join("staging", "golden", "x", "input.dwg"),
            "original_path": os.path.join("samples", "input.dwg"),
        },
        "operations": [
            {"step_id": "s1", "operation": "create_line",
             "args": {"start": [0, 0, 0], "end": [10, 0, 0], "layer": "DIM"}},
        ],
        "postconditions": [
            {"subject": "entity_count", "op": "delta_eq", "value": 1},
        ],
        "policy": {"staged_copy": True, "write_mode": "write_copy"},
    }


class TestSchemaValidation(unittest.TestCase):
    def setUp(self):
        import patch_engine
        self.pe = patch_engine

    def test_good_patch_is_valid(self):
        res = self.pe.validate_patch_schema(_good_patch())
        self.assertTrue(res["valid"], "well-formed patch rejected: %r" % res["errors"])
        self.assertEqual(res["errors"], [])

    def test_wrong_schema_const_is_invalid(self):
        p = _good_patch()
        p["schema"] = "ariadne.cad_patch.v2"
        res = self.pe.validate_patch_schema(p)
        self.assertFalse(res["valid"])
        self.assertTrue(any("schema" in e for e in res["errors"]))

    def test_missing_staged_path_is_invalid(self):
        p = _good_patch()
        p["target_dwg"].pop("staged_path")
        res = self.pe.validate_patch_schema(p)
        self.assertFalse(res["valid"])
        self.assertTrue(any("staged_path" in e for e in res["errors"]))

    def test_staged_equals_original_is_invalid(self):
        # The safety-critical case: staged path identical to the original.
        p = _good_patch()
        same = os.path.join("samples", "input.dwg")
        p["target_dwg"]["staged_path"] = same
        p["target_dwg"]["original_path"] = same
        res = self.pe.validate_patch_schema(p)
        self.assertFalse(res["valid"])
        self.assertTrue(any("differ from original" in e for e in res["errors"]),
                        "validator did not reject staged_path == original_path")

    def test_staged_copy_false_is_invalid(self):
        p = _good_patch()
        p["policy"]["staged_copy"] = False
        res = self.pe.validate_patch_schema(p)
        self.assertFalse(res["valid"])
        self.assertTrue(any("staged_copy" in e for e in res["errors"]))

    def test_empty_operations_is_invalid(self):
        p = _good_patch()
        p["operations"] = []
        res = self.pe.validate_patch_schema(p)
        self.assertFalse(res["valid"])


class TestRiskClassification(unittest.TestCase):
    def setUp(self):
        import patch_engine
        self.pe = patch_engine

    def test_create_only_is_low_risk(self):
        res = self.pe.classify_patch_risk(_good_patch())
        self.assertEqual(res["risk"], "low")

    def test_delete_entity_is_high_risk(self):
        p = _good_patch()
        p["operations"] = [{"operation": "delete_entity", "args": {"handle": "2A"}}]
        # give it postconditions so the only escalation source is the op itself
        p["postconditions"] = [{"subject": "entity_count", "op": "delta_eq", "value": -1}]
        res = self.pe.classify_patch_risk(p)
        self.assertEqual(res["risk"], "high")

    def test_mutation_without_postconditions_escalates_to_high(self):
        p = _good_patch()
        p["operations"] = [{"operation": "set_layer", "args": {"handle": "2A", "layer": "DIM"}}]
        p.pop("postconditions", None)
        res = self.pe.classify_patch_risk(p)
        self.assertEqual(res["risk"], "high")
        self.assertTrue(any("postcondition" in r.lower() for r in res["reasons"]))

    def test_write_original_is_blocked(self):
        p = _good_patch()
        p["policy"]["write_mode"] = "write_original"
        res = self.pe.classify_patch_risk(p)
        self.assertEqual(res["risk"], "blocked")
        self.assertTrue(any("original" in r.lower() for r in res["reasons"]))

    def test_no_staged_copy_is_blocked(self):
        p = _good_patch()
        p["policy"]["staged_copy"] = False
        res = self.pe.classify_patch_risk(p)
        self.assertEqual(res["risk"], "blocked")


class TestDryRunPlan(unittest.TestCase):
    def setUp(self):
        import patch_engine
        self.pe = patch_engine

    def test_plan_returns_planned_with_not_implemented_execution(self):
        plan = self.pe.dry_run_plan(_good_patch())
        self.assertEqual(plan["schema"], "ariadne.cad_patch.dry_run.v1")
        self.assertEqual(plan["status"], "planned")
        self.assertTrue(plan["guards_ok"])
        self.assertTrue(plan["schema_validation"]["valid"])
        # EXECUTION must be not_implemented at every level.
        self.assertEqual(plan["execution"], "not_implemented")
        self.assertTrue(plan["planned_ops"], "a valid patch produced no planned ops")
        for po in plan["planned_ops"]:
            self.assertEqual(po["execution_status"], "not_implemented")
            # Each op resolves to a registry op id (the dispatch target).
            self.assertIsNotNone(po["registry_op"])

    def test_invalid_patch_plan_is_rejected(self):
        p = _good_patch()
        p["policy"]["staged_copy"] = False  # both a schema and guard failure
        plan = self.pe.dry_run_plan(p)
        self.assertEqual(plan["status"], "rejected")
        self.assertFalse(plan["guards_ok"])

    def test_plan_records_registry_status_for_create(self):
        # create_line maps to the concrete native line writer; the plan surfaces
        # that op's registry status so a reader sees whether the real handler
        # exists.
        plan = self.pe.dry_run_plan(_good_patch())
        po = plan["planned_ops"][0]
        self.assertEqual(po["registry_op"], "write.entity.line")
        # registry_status may be a real status string or None if registry absent;
        # both are truthful. It must be present as a key.
        self.assertIn("registry_status", po)


class TestExecutionGuards(unittest.TestCase):
    """The guards must be able to actually reject -- not just pass."""

    def setUp(self):
        import patch_engine
        self.pe = patch_engine

    def test_write_original_guard_rejects(self):
        p = _good_patch()
        p["policy"]["write_mode"] = "write_original"
        g = self.pe.reject_write_original_by_default(p)
        self.assertFalse(g["ok"], "write_original was NOT rejected by the guard")
        self.assertIn("write_original", g["message"])

    def test_live_edit_guard_rejects(self):
        p = _good_patch()
        p["policy"]["write_mode"] = "live_edit"
        g = self.pe.reject_write_original_by_default(p)
        self.assertFalse(g["ok"])

    def test_write_copy_guard_passes(self):
        g = self.pe.reject_write_original_by_default(_good_patch())
        self.assertTrue(g["ok"])

    def test_require_staged_copy_rejects_identical_paths(self):
        p = _good_patch()
        same = os.path.join("staging", "golden", "x", "input.dwg")
        p["target_dwg"]["staged_path"] = same
        p["target_dwg"]["original_path"] = same
        g = self.pe.require_staged_copy(p)
        self.assertFalse(g["ok"], "guard accepted staged_path == original_path")

    def test_require_validation_rejects_mutation_without_postconditions(self):
        p = _good_patch()
        p.pop("postconditions", None)
        g = self.pe.require_validation(p)
        self.assertFalse(g["ok"])

    def test_write_original_never_produces_executed_status(self):
        # End-to-end: a write_original patch must end 'rejected' and NEVER carry
        # an execution other than not_implemented. (No fake destructive success.)
        p = _good_patch()
        p["policy"]["write_mode"] = "write_original"
        plan = self.pe.dry_run_plan(p)
        self.assertEqual(plan["status"], "rejected")
        self.assertEqual(plan["execution"], "not_implemented")


if __name__ == "__main__":
    unittest.main()
