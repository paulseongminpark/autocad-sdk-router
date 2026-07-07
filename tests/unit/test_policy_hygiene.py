#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CADOS registry policy hygiene tests.

Intent (WHY):
  Embedded ``operations[].policy`` blocks are a second, easy-to-stale copy of
  the write-safety contract in ``config/policy.v2.json``. When an op's
  top-level ``status`` or ``write_level`` moves forward but its nested policy
  block does not, cadctl/MCP gates read contradictory signals (the classic
  ``status==implemented`` + ``policy.status_policy==catalogued_not_runnable``
  hole). ``tools/policy_hygiene.py`` is the deterministic reconciler: it
  recomputes the expected policy block from the policy source + row facts and
  either reports drift (check mode) or rewrites only drifted rows (``--fix``).

These tests pin that contract at two levels:
  1. After ``--fix`` on the live registry, the checker must report zero drift
     (the committed registry is self-consistent).
  2. A hand-built synthetic row with an intentional legacy policy shape must be
     caught and repaired by the same pure functions the CLI uses.

Stdlib only; BOM-tolerant reads (utf-8-sig). Discoverable by pytest and
``python -m unittest discover -s tests``.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from collections import Counter

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import policy_hygiene as ph  # noqa: E402

_POLICY = os.path.join(_REPO, "config", "policy.v2.json")
_OPERATIONS_V2 = os.path.join(_REPO, "config", "operations.v2.json")
_JSON_ENCODING = "utf-8-sig"


def _load(path: str):
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


class TestPolicyHygieneLiveRegistry(unittest.TestCase):
    """The committed registry must be drift-free after hygiene reconciliation."""

    @classmethod
    def setUpClass(cls):
        cls.policy_doc = _load(_POLICY)
        cls.registry = _load(_OPERATIONS_V2)

    def test_live_registry_has_expected_status_histogram(self):
        by_status = Counter(op.get("status") for op in self.registry["operations"])
        self.assertEqual(dict(by_status), {"implemented": 488, "blocked": 62})
        self.assertEqual(len(self.registry["operations"]), 550)

    def test_zero_drift_after_fix_on_live_registry(self):
        report = ph.check_registry(self.registry, self.policy_doc)
        self.assertEqual(
            report["drift_count"],
            0,
            "live registry still carries stale policy blocks: %s"
            % [row["op_id"] for row in report.get("drift_rows", [])[:10]],
        )


class TestPolicyHygieneSyntheticDrift(unittest.TestCase):
    def test_legacy_policy_shape_is_detected_and_repaired(self):
        policy_doc = _load(_POLICY)
        op = {
            "id": "synthetic.hygiene.legacy",
            "status": "implemented",
            "mapping_type": "synthetic",
            "write_level": {
                "default_write_mode": "read",
                "allowed_write_modes": ["read"],
                "dwg_persisted": False,
                "original_write_default": False,
            },
            "policy": {
                "write_mode_default": "read",
                "staged_copy_required": False,
                "write_original_requires_approval": True,
                "raw_command_dispatch": "forbidden",
                "secrets": "never_read_or_printed",
            },
        }

        drift = ph.policy_drift(op, policy_doc)
        self.assertTrue(drift, "legacy v1 policy shape must be reported as drift")
        self.assertEqual(drift[0].get("reason"), "legacy_v1_policy_shape")

        expected = ph.expected_policy(op, policy_doc, actual_policy=op["policy"])
        self.assertEqual(expected["source"], ph.POLICY_SOURCE)
        self.assertEqual(expected["status_policy"], "implemented")
        self.assertEqual(expected["default_write_mode"], "read")
        self.assertNotIn("write_mode_default", expected)

        op["policy"] = expected
        self.assertEqual(ph.policy_drift(op, policy_doc), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
