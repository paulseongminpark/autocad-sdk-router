#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M08O / Wave4X fallback lane evidence tests.

Guardrails:
- safe COM fallback is metadata-only (no raw COM handles)
- AutoLISP fallback is router-authored and bounded
- raw command surfaces stay hard-blocked and never agent-exposed
- OLE mutation/lifecycle routes stay honestly blocked
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
        cls.ops = {o["id"]: o for o in cls.doc["operations"]}
        cls.rows = {r["operation"]: r for r in cls.matrix["operations"]}

    def test_safe_com_metadata_ops_are_implemented(self):
        safe_ids = {
            "automate.com.get_app",
            "automate.com.get_document",
            "automate.com.get_for_command",
            "automate.com.get_winapp",
            "automate.com.wrapper_for_object",
        }
        for op_id in sorted(safe_ids):
            op = self.ops[op_id]
            row = self.rows[op_id]
            self.assertEqual(op["status"], "implemented", op_id)
            self.assertEqual(op["handler"]["router_lane"], "full_autocad", op_id)
            self.assertEqual(op["handler"]["dispatcher_symbol"], "Invoke-SafeFallbackOperation", op_id)
            self.assertEqual(op["handler"]["execution_host_class"], "full_autocad", op_id)
            self.assertIn("docs/FALLBACK_POLICY.md", op.get("evidence_refs", []), op_id)
            self.assertIn("reports/tickets/WAVE4X_FALLBACK.md", op.get("evidence_refs", []), op_id)
            self.assertTrue(row["agent_exposed"], op_id)
            self.assertEqual(row["risk_class"], "read_safe", op_id)
            self.assertFalse(op.get("blocked_reason"), op_id)

    def test_module_load_lisp_is_implemented_as_safe_adapter_only(self):
        op = self.ops["module.load.lisp"]
        row = self.rows["module.load.lisp"]
        self.assertEqual(op["status"], "implemented")
        self.assertEqual(op["handler"]["router_lane"], "ARIADNE_CAD_JOB")
        self.assertEqual(op["handler"]["dispatcher_symbol"], "Invoke-SafeFallbackOperation")
        self.assertEqual(op["handler"]["execution_host_class"], "coreconsole")
        self.assertIn("safe_status", (op.get("notes") or ""))
        self.assertIn("docs/FALLBACK_POLICY.md", op.get("evidence_refs", []))
        self.assertIn("reports/tickets/WAVE4X_FALLBACK.md", op.get("evidence_refs", []))
        self.assertTrue(row["agent_exposed"])
        self.assertEqual(row["risk_class"], "read_safe")

    def test_raw_command_ops_hard_blocked_with_fallback_evidence(self):
        raw_ids = {
            "command.invoke.coroutine",
            "command.invoke.sync",
            "command.invoke.sync.resbuf",
            "command.queue.post",
        }
        for op_id in sorted(raw_ids):
            op = self.ops[op_id]
            self.assertEqual(op["status"], "blocked", op_id)
            self.assertIn("SAFETY_FORBIDDEN", op.get("blocked_reason", ""), op_id)
            self.assertIn("docs/FALLBACK_POLICY.md", op.get("evidence_refs", []), op_id)
            self.assertFalse(self.rows[op_id]["agent_exposed"], op_id)

    def test_send_command_and_menu_macro_stay_blocked(self):
        for op_id in ("automate.com.send_command", "command.menu.invoke"):
            op = self.ops[op_id]
            self.assertEqual(op["status"], "blocked", op_id)
            self.assertIn("SAFETY_FORBIDDEN", op.get("blocked_reason", ""), op_id)
            self.assertFalse(self.rows[op_id]["agent_exposed"], op_id)

    def test_ole_embed_and_unload_remain_honestly_blocked(self):
        expected = {
            "embed.ole.frame": "HOST_UNAVAILABLE",
            "module.lifecycle.on_ole_unload": "HOST_UNAVAILABLE",
        }
        for op_id, code in expected.items():
            op = self.ops[op_id]
            self.assertEqual(op["status"], "blocked", op_id)
            self.assertIn(code, op.get("blocked_reason", ""), op_id)
            self.assertFalse(self.rows[op_id]["agent_exposed"], op_id)

    def test_fallback_policy_documents_safe_surfaces(self):
        policy = Path(_REPO) / "docs" / "FALLBACK_POLICY.md"
        self.assertTrue(policy.exists())
        text = policy.read_text(encoding="utf-8")
        for token in (
            "automate.com.get_app",
            "automate.com.wrapper_for_object",
            "module.load.lisp",
            "safe_status",
            "ARIADNE_CAD_JOB",
            "NETLOAD",
        ):
            self.assertIn(token, text, f"fallback policy must document {token}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
