#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wave 3 Pane 8 registry closure test.

Business rule: every claimed Pane 8 op must leave `catalogued` and land in the
registry with a real native dispatcher + evidence refs.
"""
from __future__ import annotations

import json
import os
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_CLAIMS = os.path.join(_REPO, "reports", "tickets", "WAVE3_PANE8_CLAIMS.json")
_REG = os.path.join(_REPO, "config", "operations.v2.json")


def _load(path: str):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


class TestWave3Pane8Registry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.claims = _load(_CLAIMS)
        cls.reg = _load(_REG)
        cls.by_id = {o.get("id"): o for o in cls.reg.get("operations", []) if isinstance(o, dict)}
        cls.claimed_ops = [c["operation"] for c in cls.claims.get("claims", [])]

    def test_claim_file_shape(self):
        self.assertEqual(self.claims.get("pane"), 8)
        self.assertEqual(self.claims.get("claim_count"), 9)
        self.assertEqual(len(self.claimed_ops), 9)

    def test_all_claimed_ops_exist_and_are_implemented(self):
        missing = [op for op in self.claimed_ops if op not in self.by_id]
        self.assertEqual(missing, [], "claimed ops missing from registry: %s" % missing)
        bad = [(op, self.by_id[op].get("status")) for op in self.claimed_ops if self.by_id[op].get("status") != "implemented"]
        self.assertEqual(bad, [], "claimed ops not implemented: %s" % bad)

    def test_all_claimed_ops_point_to_m08m_dispatch(self):
        bad = []
        for op in self.claimed_ops:
            dispatcher = ((self.by_id[op].get("handler") or {}).get("dispatcher_symbol"))
            if dispatcher != "m08mDispatch":
                bad.append((op, dispatcher))
        self.assertEqual(bad, [], "claimed ops not wired to m08mDispatch: %s" % bad)

    def test_all_claimed_ops_have_wave3_evidence_refs(self):
        need = {
            "src/Ariadne.AcadNative/families/m08m_handlers.inc:m08mDispatch",
            "reports/tickets/WAVE3_PANE8_OPM_REACTORS.md",
            "reports/tickets/WAVE3_PANE8_OPM_REACTORS_OPS.json",
        }
        bad = []
        for op in self.claimed_ops:
            refs = set(self.by_id[op].get("evidence_refs") or [])
            if not need.issubset(refs):
                bad.append((op, sorted(need - refs)))
        self.assertEqual(bad, [], "claimed ops missing Pane 8 evidence refs: %s" % bad)

    def test_all_claimed_ops_reference_unit_tests(self):
        bad = []
        for op in self.claimed_ops:
            tests = set(self.by_id[op].get("tests") or [])
            if "tests/unit/test_m08m_handlers.py" not in tests:
                bad.append((op, sorted(tests)))
        self.assertEqual(bad, [], "claimed ops missing m08m unit-test evidence: %s" % bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
