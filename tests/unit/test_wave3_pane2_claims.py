#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wave3 Pane2 claim closure tests.

Pins the ticket contract: every operation assigned in
reports/tickets/WAVE3_PANE2_CLAIMS.json must close as implemented / blocked /
deprecated, never remain catalogued/stub/unknown/deferred. Implemented native ops
must carry handler/test/evidence metadata.
"""
from __future__ import annotations

import json
import os
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_CLAIMS = os.path.join(_REPO, "reports", "tickets", "WAVE3_PANE2_CLAIMS.json")
_REG = os.path.join(_REPO, "config", "operations.v2.json")

_ALLOWED_FINAL = {"implemented", "blocked", "deprecated"}
_FORBIDDEN_FINAL = {"catalogued", "stub", "unknown", "deferred", "future_version", "v1_target_false_escape"}


class TestWave3Pane2Claims(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(_CLAIMS, "r", encoding="utf-8") as f:
            cls.claim_doc = json.load(f)
        with open(_REG, "r", encoding="utf-8-sig") as f:
            cls.reg = json.load(f)
        cls.by_id = {o["id"]: o for o in cls.reg["operations"]}
        cls.claims = [c["operation"] for c in cls.claim_doc["claims"]]

    def test_claim_file_shape(self):
        self.assertEqual(self.claim_doc["pane"], 2)
        self.assertEqual(self.claim_doc["claim_count"], len(self.claims))
        self.assertEqual(len(self.claims), 21)
        self.assertEqual(len(set(self.claims)), 21)

    def test_all_claims_exist_in_registry(self):
        missing = [op for op in self.claims if op not in self.by_id]
        self.assertEqual(missing, [])

    def test_no_claim_left_catalogued_stub_unknown_or_deferred(self):
        bad = {op: self.by_id[op]["status"] for op in self.claims
               if self.by_id[op].get("status") in _FORBIDDEN_FINAL}
        self.assertEqual(bad, {})
        not_final = {op: self.by_id[op]["status"] for op in self.claims
                     if self.by_id[op].get("status") not in _ALLOWED_FINAL}
        self.assertEqual(not_final, {})

    def test_all_claims_implemented_this_ticket(self):
        not_impl = {op: self.by_id[op]["status"] for op in self.claims
                    if self.by_id[op].get("status") != "implemented"}
        self.assertEqual(not_impl, {})

    def test_implemented_claims_have_handler_tests_evidence(self):
        missing = []
        for op in self.claims:
            rec = self.by_id[op]
            handler = rec.get("handler") or {}
            tests = rec.get("tests") or []
            evidence = rec.get("evidence_refs") or []
            if not handler.get("dispatcher_symbol"):
                missing.append((op, "dispatcher_symbol"))
            if not tests:
                missing.append((op, "tests"))
            if not evidence:
                missing.append((op, "evidence_refs"))
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
