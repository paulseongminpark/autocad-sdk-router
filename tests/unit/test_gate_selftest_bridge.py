#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bridge test -- wires tests/gate_selftest/ (F3-self, the 5 hand-built
adversarial gate fixtures) into the tests/unit pytest run.

WHY this file exists: tests/gate_selftest/ is its own directory (a sibling of
tests/unit, matching this repo's existing tests/integration, tests/smoke,
tests/fixtures, tests/golden convention), so a bare ``pytest tests/unit -q``
invocation would never import it and its 5-case meta-guard would silently go
unexercised by the project's standard verification command. This bridge makes
that impossible: it fails LOUD (not skips) if tests/gate_selftest/ or its
manifest ever goes missing or its case count drifts.

Dual-runnable: discoverable by both pytest and
``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_GATE_SELFTEST_DIR = os.path.join(_REPO, "tests", "gate_selftest")
for _p in (_REPO, os.path.join(_REPO, "tools"), _GATE_SELFTEST_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import adversarial_fixtures as af  # noqa: E402
import cad_op_gate  # noqa: E402


class TestGateSelftestIsWiredIntoUnitRun(unittest.TestCase):
    """The 5 F3-self adversarial cases, re-run here so ``pytest tests/unit -q``
    alone (this repo's standard gate command) genuinely exercises them --
    not merely tests/gate_selftest/ in isolation."""

    def test_gate_selftest_directory_exists(self):
        self.assertTrue(os.path.isdir(_GATE_SELFTEST_DIR),
                        "tests/gate_selftest/ (F3-self) is missing")

    def test_exactly_five_adversarial_cases(self):
        self.assertEqual(len(af.CASES), 5)

    def test_every_case_matches_its_pinned_exit_code(self):
        for name, runner, expected_exit, expected_status in af.CASES:
            with self.subTest(case=name):
                result = runner()
                self.assertEqual(result["exit_code"], expected_exit,
                                 "%s: expected exit %d, got %r" % (name, expected_exit, result))
                self.assertEqual(result["status"], expected_status)

    def test_mostly_exit_4_shape(self):
        counts = {}
        for _name, runner, _exit, _status in af.CASES:
            result = runner()
            counts[result["exit_code"]] = counts.get(result["exit_code"], 0) + 1
        self.assertEqual(counts, {cad_op_gate.EXIT_HOLLOW: 4, cad_op_gate.EXIT_IRRECONSTRUCTIBLE: 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
