#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M08O fallback lane evidence tests.

These are lane-local guardrails for Pane 4 (COM/bootstrap + raw-command hard-block):
- raw-command ops are hard-blocked with explicit safety blockers and evidence
- COM fallback remains constrained to known loader commands (ARXLOAD / NETLOAD), not
  raw command dispatch
- `automate.com.send_command` is never agent-exposed while no managed implementation is
  wired.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import operation_coverage_matrix as ocm  # noqa: E402


class TestM08OFallback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix, cls.doc = ocm.build_matrix()
        cls.ops = cls.doc["operations"]
        cls.rows = {r["operation"]: r for r in cls.matrix["operations"]}

    def test_raw_command_ops_hard_blocked_with_fallback_evidence(self):
        raw_ids = {
            "command.invoke.coroutine",
            "command.invoke.sync",
            "command.invoke.sync.resbuf",
            "command.queue.post",
        }
        raw_ops = [o for o in self.ops if o["id"] in raw_ids]
        self.assertEqual(len(raw_ops), len(raw_ids), "expected all raw-command fallback ops to be present")
        for o in raw_ops:
            self.assertEqual(o["status"], "blocked", o["id"])
            self.assertEqual(o["owner_ticket"], "M08O-T02", o["id"])
            self.assertIn("SAFETY_FORBIDDEN", o["blocked_reason"], o["id"])
            self.assertIn("docs/FALLBACK_POLICY.md", o.get("evidence_refs", []), o["id"])
            self.assertFalse(self.rows[o["id"]]["agent_exposed"], o["id"])

    def test_com_send_command_is_not_agent_exposed(self):
        op = next(o for o in self.ops if o["id"] == "automate.com.send_command")
        self.assertNotIn(op["status"], ("implemented", "wired"),
                         "COM send_command must not become surfaced")
        self.assertIn(op["id"], self.rows)
        self.assertFalse(self.rows[op["id"]]["agent_exposed"], "automate.com.send_command must remain non-exposed")

    def test_doc_sendstring_is_safety_blocked_not_agent_exposed(self):
        op = next(o for o in self.ops if o["id"] == "doc.sendstring")
        self.assertEqual(op["status"], "blocked", "doc.sendstring must not remain open or runnable")
        self.assertIn("SAFETY_FORBIDDEN", op.get("blocked_reason", ""))
        self.assertIn("raw command", op.get("blocked_reason", "").lower())
        self.assertFalse(self.rows["doc.sendstring"]["agent_exposed"])
        self.assertEqual(self.rows["doc.sendstring"]["risk_class"], "raw_command")

    def test_fallback_loaders_documented(self):
        policy = Path(_REPO) / "docs" / "FALLBACK_POLICY.md"
        self.assertTrue(policy.exists())
        text = policy.read_text(encoding="utf-8")
        for token in ("ARXLOAD", "NETLOAD", "AutoLISP", ".NET"):
            self.assertIn(token, text, f"fallback policy must document {token}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
