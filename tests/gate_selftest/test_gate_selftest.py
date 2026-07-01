#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F3-self TEST -- the 5 hand-built adversarial gate fixtures (adversarial_fixtures.py)
return the CORRECT exit code on every one (Rule 9: a test that cannot fail
when the gate logic changes is worthless).

Dual-runnable: discoverable by both pytest and
``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools"), _THIS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import adversarial_fixtures as af  # noqa: E402
import cad_op_gate  # noqa: E402


class TestF3SelfAdversarialFixtures(unittest.TestCase):
    """Every one of the 5 hand-built adversarial (pre_ir, post_ir) pairs must
    make the gate return its pinned exit code -- mostly exit 4 HOLLOW, except
    the wrong-entity-modified identity failure, which is exit 8
    IRRECONSTRUCTIBLE (see adversarial_fixtures.CASES)."""

    def test_manifest_is_exactly_five_cases(self):
        self.assertEqual(len(af.CASES), 5)

    def test_case_a_field_absent_is_hollow(self):
        result = af.case_a_field_absent()
        self.assertEqual(result["status"], cad_op_gate.STATUS_HOLLOW)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_HOLLOW)

    def test_case_b_bucket_collapse_is_hollow(self):
        result = af.case_b_bucket_collapse()
        self.assertEqual(result["status"], cad_op_gate.STATUS_HOLLOW)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_HOLLOW)
        self.assertIn("degenerate dim", result["reason"])

    def test_case_c_key_injected_is_hollow(self):
        result = af.case_c_key_injected()
        self.assertEqual(result["status"], cad_op_gate.STATUS_HOLLOW)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_HOLLOW)

    def test_case_d_coarse_quantized_invisible_is_hollow(self):
        result = af.case_d_coarse_quantized_invisible()
        self.assertEqual(result["status"], cad_op_gate.STATUS_HOLLOW)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_HOLLOW)

    def test_case_e_wrong_entity_modified_is_irreconstructible(self):
        result = af.case_e_wrong_entity_modified()
        self.assertEqual(result["status"], cad_op_gate.STATUS_IRRECONSTRUCTIBLE)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_IRRECONSTRUCTIBLE)

    def test_four_of_five_are_exit_4_one_is_exit_8(self):
        """Pin the "(mostly exit 4)" shape of the manifest itself -- a future
        edit that quietly changes a case's expectation must fail loudly here."""
        counts = {}
        for _name, runner, _exit, _status in af.CASES:
            result = runner()
            counts[result["exit_code"]] = counts.get(result["exit_code"], 0) + 1
        self.assertEqual(counts, {cad_op_gate.EXIT_HOLLOW: 4, cad_op_gate.EXIT_IRRECONSTRUCTIBLE: 1})

    def test_all_cases_match_their_pinned_manifest_expectation(self):
        for name, runner, expected_exit, expected_status in af.CASES:
            with self.subTest(case=name):
                result = runner()
                self.assertEqual(result["exit_code"], expected_exit)
                self.assertEqual(result["status"], expected_status)

    def test_run_all_returns_every_case_by_name(self):
        results = af.run_all()
        self.assertEqual(set(results), {name for name, *_ in af.CASES})


if __name__ == "__main__":
    unittest.main(verbosity=2)
