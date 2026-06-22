#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08 TEST -- full operation coverage closure.

Intent (WHY):
  M08 closes the operation catalog: every one of the registry's operations must
  carry the 13-field coverage taxonomy (no unknowns, no missing field), every
  v1-target op must be implemented OR hard-blocked with evidence (never deferred),
  every implemented op must have test+evidence refs, every blocked op a
  blocker_ref, no raw AutoCAD command may be agent-exposed, and the frozen 29 v1
  ops must stay runnable. These tests assert those invariants against the
  DETERMINISTIC matrix built by tools/operation_coverage_matrix.build_matrix from
  config/operations.v2.json -- so a regression (a demoted op, a missing field, a
  newly-exposed raw command, a v1-target slipping to stub) fails CI, not a human.

Stdlib only; BOM-tolerant (utf-8-sig). Discoverable by pytest and unittest.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import operation_coverage_matrix as ocm  # noqa: E402

_M13 = ["operation", "family", "v1_target", "status", "host_support", "handler",
        "test_ref", "evidence_ref", "blocker_ref", "risk_class", "write_level",
        "agent_exposed", "notes"]

_PROMOTED = ["inspect.layers", "inspect.blocks", "inspect.entities", "live.status"]
_NATIVE_SRC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "AriadneNativeJob.cpp")


def _matrix():
    matrix, doc = ocm.build_matrix()
    return matrix, doc


class TestM08Taxonomy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix, cls.doc = _matrix()
        cls.rows = cls.matrix["operations"]
        cls.by_id = {r["operation"]: r for r in cls.rows}

    def test_gate_passes(self):
        gate = self.matrix["gate"]
        failed = [k for k, v in gate.items() if k != "gate_pass" and not v]
        self.assertEqual(failed, [], f"M08 gate checks failed: {failed}")
        self.assertTrue(gate["gate_pass"], "overall M08 gate must pass")

    def test_all_13_fields_present_every_op(self):
        missing = []
        for r in self.rows:
            for f in _M13:
                if f not in r:
                    missing.append((r.get("operation"), f))
        self.assertEqual(missing, [], f"ops missing taxonomy fields: {missing[:10]}")

    def test_zero_unknown_status(self):
        bad = [r["operation"] for r in self.rows if r["status"] in (None, "", "unknown")]
        self.assertEqual(bad, [], f"ops with unknown status: {bad[:10]}")
        self.assertEqual(self.matrix["totals"]["unknown"], 0)

    def test_total_matches_registry(self):
        self.assertEqual(self.matrix["totals"]["total"], len(self.doc["operations"]))

    def test_every_implemented_has_test_and_evidence(self):
        bad = [r["operation"] for r in self.rows
               if r["status"] == "implemented" and (not r["test_ref"] or not r["evidence_ref"])]
        self.assertEqual(bad, [], f"implemented ops missing test/evidence: {bad}")

    def test_every_blocked_has_blocker_ref(self):
        bad = [r["operation"] for r in self.rows
               if r["status"] == "blocked" and not r["blocker_ref"]]
        self.assertEqual(bad, [], f"blocked ops missing blocker_ref: {bad}")

    def test_no_agent_exposed_raw_command(self):
        bad = [r["operation"] for r in self.rows
               if r["agent_exposed"] and r["risk_class"] == "raw_command"]
        self.assertEqual(bad, [], f"raw command ops must NOT be agent-exposed: {bad}")

    def test_raw_command_ops_detected_and_walled_off(self):
        # The guard must be non-vacuous: genuine raw-command ops EXIST and are all
        # non-exposed (catalogued). If zero were detected the guard would be empty.
        raw = [r for r in self.rows if r["risk_class"] == "raw_command"]
        self.assertGreater(len(raw), 0, "expected to detect real raw-command ops")
        self.assertTrue(all(not r["agent_exposed"] for r in raw))

    def test_no_original_write_default(self):
        bad = [o["id"] for o in self.doc["operations"]
               if (o.get("write_level") or {}).get("original_write_default") is True]
        self.assertEqual(bad, [], f"ops defaulting to original write: {bad}")

    def test_v1_target_implemented_or_blocked_no_deferred(self):
        deferred = [r["operation"] for r in self.rows
                    if r["v1_target"] and r["status"] in ("stub", "catalogued", "deprecated")]
        self.assertEqual(deferred, [], f"v1-target ops may not be deferred: {deferred}")

    def test_v1_target_blocked_have_evidence(self):
        for r in self.rows:
            if r["v1_target"] and r["status"] == "blocked":
                self.assertTrue(r["blocker_ref"], f"{r['operation']} blocked w/o blocker_ref")
                self.assertTrue(r["evidence_ref"], f"{r['operation']} blocked w/o evidence_ref")

    def test_existing_29_frozen_runnable(self):
        frozen = [o for o in self.doc["operations"] if o.get("wired_v1") is True]
        self.assertEqual(len(frozen), 29, "the frozen v1 surface must stay 29 ops")
        bad = [o["id"] for o in frozen if o.get("status") not in ("implemented", "wired")]
        self.assertEqual(bad, [], f"frozen v1 ops demoted from runnable: {bad}")


class TestM08Promotions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix, cls.doc = _matrix()
        cls.by_id = {o["id"]: o for o in cls.doc["operations"]}

    def test_inspect_enumeration_ops_implemented(self):
        for op in _PROMOTED:
            rec = self.by_id.get(op)
            self.assertIsNotNone(rec, f"{op} missing from registry")
            self.assertEqual(rec["status"], "implemented", f"{op} must be implemented")
            self.assertTrue((rec.get("handler") or {}).get("dispatcher_symbol"),
                            f"{op} must declare a dispatcher_symbol")
            self.assertTrue(rec.get("tests"), f"{op} must have tests")
            self.assertTrue(rec.get("evidence_refs"), f"{op} must have evidence_refs")

    def test_registry_cadctl_consistent(self):
        import cadctl
        rc = cadctl.registry_coverage()
        self.assertTrue(rc["consistent"], "cadctl registry coverage must be consistent")
        self.assertEqual(rc["unknown_count"], 0)
        self.assertGreaterEqual(rc["computed_by_status"].get("implemented", 0), 41)
        self.assertEqual(rc["computed_by_status"].get("stub", 0), 0,
                         "M08 leaves no stub ops")

    def test_matrix_counts_match_registry(self):
        import cadctl
        rc = cadctl.registry_coverage()
        self.assertEqual(self.matrix["totals"]["by_status"], rc["computed_by_status"])


class TestM08NativeSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(_NATIVE_SRC, "r", encoding="utf-8", errors="replace") as f:
            cls.src = f.read()

    def test_inspect_dispatch_branches_present(self):
        for branch in ('op == "inspect.layers"', 'op == "inspect.blocks"', 'op == "inspect.entities"'):
            self.assertIn(branch, self.src, f"native dispatcher branch missing: {branch}")

    def test_inspect_helpers_present(self):
        for sym in ("listLayerRecords", "listBlockDefinitionsDetailed", "listModelSpaceEntities"):
            self.assertIn(sym, self.src, f"native helper missing: {sym}")

    def test_entities_is_bounded_with_truncated_flag(self):
        # inspect.entities must report a truncated flag (no silent cap) + counts.
        # (identifiers, not quoted JSON: the source escapes quotes as \" in C++.)
        self.assertIn("truncated", self.src)
        self.assertIn("matching_entities", self.src)
        self.assertIn("returned", self.src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
