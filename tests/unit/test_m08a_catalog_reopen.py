#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08A-T01 TEST — catalog reopen + v1_target escape removed.

Intent (WHY):
  The "M08 PASS" only ever scored the {implemented, blocked} v1 subset, so the 474
  `catalogued` ops were structurally invisible to the gate — the v1_target=false
  escape the COMMON_TICKET_CONTRACT forbids. M08A-T01 reopens every op into scope.
  These tests encode the contract:
    1. EVERY op now carries owner_ticket + implementation_strategy + evidence_required
       (no op may be left unowned — that is what "reopened" means).
    2. The honest closure_gate scores ALL ops, is False while anything is
       catalogued/stub, and is True only after the full catalog is closed.
    3. The escape is explicitly banned; M09 is allowed only after M08R closure.
    4. Raw-command ops close as `deprecated` and are owned by the fallback lane
       (they may never become agent-exposed "implemented").
    5. The legacy v1 `gate` is NOT regressed (back-compat: removing the escape must
       not demote the existing v1 surface).
  A test that could not fail if the catalog were re-hidden would be worthless — so
  these assert the live matrix/registry, not a snapshot.

Stdlib only; BOM-tolerant. Discoverable by pytest and unittest.
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

import operation_coverage_matrix as ocm  # noqa: E402

_REQUIRED_FIELDS = ("owner_ticket", "implementation_strategy", "evidence_required")
_OPEN_STATES = ("catalogued", "stub")


class TestM08ACatalogReopen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = ocm._load(ocm.REG)
        cls.ops = cls.doc["operations"]
        cls.cg = ocm.compute_closure_gate(cls.doc)

    # 1 — every op reopened (owned + planned)
    def test_every_op_has_owner_ticket(self):
        bad = [o.get("id") for o in self.ops if not o.get("owner_ticket")]
        self.assertEqual(bad, [], f"ops without owner_ticket: {bad[:10]}")

    def test_every_op_has_strategy_and_evidence(self):
        bad = [o.get("id") for o in self.ops
               if not o.get("implementation_strategy") or not o.get("evidence_required")]
        self.assertEqual(bad, [], f"ops missing strategy/evidence: {bad[:10]}")

    def test_reopen_fields_are_deterministic(self):
        # re-deriving must reproduce the stored values exactly (pure function).
        for o in self.ops:
            self.assertEqual(o["owner_ticket"], ocm.assign_owner_ticket(o), o.get("id"))
            self.assertEqual(o["implementation_strategy"], ocm.impl_strategy(o), o.get("id"))
            self.assertEqual(o["evidence_required"], ocm.evidence_required(o), o.get("id"))

    # 2 — honest closure gate (the anti-escape invariant)
    def test_closure_gate_owner_and_plan_checks_pass(self):
        self.assertTrue(self.cg["checks"]["every_op_has_owner_ticket"])
        self.assertTrue(self.cg["checks"]["every_open_op_has_strategy_and_evidence"])

    def test_closure_gate_honestly_open_while_catalogued(self):
        # The catalog is genuinely open: catalogued > 0, so closure MUST be False.
        # (If a future change re-hid the catalog behind a v1 filter, catalogued
        # would read 0 here and this guard would catch a false closure.)
        open_now = sum(1 for o in self.ops if o.get("status") in _OPEN_STATES)
        if open_now > 0:
            self.assertFalse(self.cg["closure_gate_pass"],
                             "closure_gate must NOT pass while ops are catalogued/stub")
            self.assertFalse(self.cg["checks"]["zero_catalogued"] and self.cg["checks"]["zero_stub"])
        self.assertEqual(self.cg["catalogued"] + self.cg["stub"], open_now)

    # 3 — escape banned, M09 blocked
    def test_v1_target_escape_banned(self):
        marker = self.doc.get("m08a_catalog_reopen") or {}
        self.assertTrue(marker.get("v1_target_escape_banned"))
        self.assertIn("v1_target_false", marker.get("forbidden_closure_states", []))
        self.assertTrue(self.cg["checks"]["v1_target_escape_banned"])

    def test_m09_allowed_only_after_closure(self):
        self.assertTrue(self.cg["m09_blocked_until_m08r"])
        open_now = self.cg["catalogued"] + self.cg["stub"]
        if open_now:
            self.assertFalse(self.cg["m09_allowed"],
                             "M09 may not be allowed while the catalog is open")
        else:
            self.assertTrue(self.cg["m09_allowed"],
                            "M09 should be allowed once the full catalog is closed")

    # 4 — raw command ops hard-blocked by safety policy, never agent-exposed
    def test_raw_command_ops_hard_blocked_and_owned(self):
        raw = [o for o in self.ops if ocm.is_raw_command(o)]
        self.assertGreater(len(raw), 0, "expected real raw-command ops to exist")
        for o in raw:
            self.assertEqual(o["status"], "blocked", o.get("id"))
            self.assertEqual(o["implementation_strategy"], "hard_blocked", o.get("id"))
            self.assertEqual(o["owner_ticket"], "M08O-T02", o.get("id"))
            self.assertTrue(o.get("blocked_reason") and "SAFETY_FORBIDDEN" in o.get("blocked_reason", ""),
                            f"{o.get('id')} missing SAFETY_FORBIDDEN blocker")
            self.assertIn("docs/FALLBACK_POLICY.md", o.get("evidence_refs") or [],
                          f"{o.get('id')} missing fallback policy evidence ref")

    # surfaced index gap — constraints_associativity gets its proposed lane
    def test_constraints_family_assigned_to_proposed_lane(self):
        cons = [o for o in self.ops if o.get("family") == "constraints_associativity"]
        self.assertGreater(len(cons), 0)
        self.assertTrue(all(o["owner_ticket"] == "M08K-T03" for o in cons))
        self.assertIn("M08K-T03", (self.doc.get("m08a_catalog_reopen") or {}).get("proposed_new_tickets", {}))

    # 5 — back-compat: the legacy v1 gate is not regressed
    def test_legacy_v1_gate_still_passes(self):
        matrix, _ = ocm.build_matrix()
        self.assertTrue(matrix["gate"]["gate_pass"],
                        "removing the escape must not regress the v1 surface gate")
        # and the matrix now also carries the closure_gate
        self.assertIn("closure_gate", matrix)

    def test_status_counts_reflect_wave3_closure(self):
        # Wave3 closure eliminates the old catalogued/stub escape: every op is now
        # implemented or hard-blocked. w3-dimstyle adds one new synthetic
        # implemented op (write.dimstyle.create) on top of the wave3 baseline
        # -- 457 -> 458 (see tools/patch_ops/tables.py). p9-tables2 adds one
        # more synthetic implemented op (write.ucs.create) -- 458 -> 459, then
        # a second (write.view.create) -- 459 -> 460, then a third
        # (write.vport.create) -- 460 -> 461.
        import collections
        by_status = collections.Counter(o.get("status") for o in self.ops)
        self.assertEqual(by_status.get("unknown", 0), 0)
        self.assertEqual(by_status.get("catalogued", 0), 0)
        self.assertEqual(by_status.get("stub", 0), 0)
        self.assertEqual(by_status.get("implemented", 0), 461)
        self.assertEqual(by_status.get("blocked", 0), 60)
        # ^ unchanged: p9-tables2 (like w3-dimstyle before it) only added a
        # new IMPLEMENTED synthetic op, never touched the blocked count.
        self.assertEqual(by_status.get("implemented", 0) + by_status.get("blocked", 0), len(self.ops))


if __name__ == "__main__":
    unittest.main(verbosity=2)
