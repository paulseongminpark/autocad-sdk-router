#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M02 TEST -- validator's NEW patch/diff gates fire + skip cleanly.

Intent (WHY):
  * M02 adds patch/diff awareness to the validator: diff_expected_changes,
    patch_policy, staged_copy_used, original_dwg_unchanged, journal_present (plus
    no_unrelated_changes, cad_diff_schema). Each must FIRE when its input is given
    and SKIP BENIGNLY (status skipped + skip_benign, not downgrading the verdict)
    when its input is absent. A gate that silently no-ops on bad input, or one
    that downgrades a clean plain-IR run, would make the verdict untrustworthy.
  * The "a patch that produced NO diff is NOT a success" gate (diff_expected_
    changes) is the heart of patch verification -- it must FAIL on an empty diff
    and drive the overall verdict to fail. (Rule 9: a test that can't fail when
    business logic changes is worthless.)
  * patch_policy must FAIL on a write_original / staged==original patch (a hard
    safety failure), not merely warn.
  * EVERY gate record must carry a stable NAME field ``gate`` (mirrors ``id``) and
    a ``detail`` field, so downstream consumers can key on them. M02 contract.
  * Existing IR-only gates must be PRESERVED: a plain-IR validation with no
    run/patch/diff still rolls up to ``pass`` (benign skips don't downgrade).

Built from ir_builder.make_fixture_ir() + a synthetic cad_diff + a synthetic
patch run folder (staged_*.dwg + journal.json) so the patch/diff gates are
exercised deterministically WITHOUT AutoCAD.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CAD_DIFF_SCHEMA_ID = "ariadne.cad_diff.v1"
CAD_PATCH_SCHEMA_ID = "ariadne.cad_patch.v1"

# The M02 patch/diff gates that must exist + behave.
_PATCH_DIFF_GATES = (
    "cad_diff_schema", "diff_expected_changes", "no_unrelated_changes",
    "patch_policy", "staged_copy_used", "journal_present",
    "original_dwg_unchanged",
)


def _gate(report, gid):
    return next((g for g in report["gates"]
                 if g.get("gate") == gid or g.get("id") == gid), None)


def _good_ir():
    import ir_builder
    ir = ir_builder.make_fixture_ir()
    ir["source"]["dwg_path"] = os.path.join("staging", "golden", "fix", "input.dwg")
    ir["source"]["original_path"] = os.path.join("samples", "input.dwg")
    return ir


def _write_ir(ir, tmp):
    path = os.path.join(tmp, "dwg_graph_ir.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ir, fh, indent=2)
    return path


def _diff_with_one_added():
    return {
        "schema": CAD_DIFF_SCHEMA_ID,
        "diff_id": "diff-gatetest-0001",
        "before_ref": {"kind": "ir", "ref": "before.json", "entity_count": 2},
        "after_ref": {"kind": "ir", "ref": "after.json", "entity_count": 3},
        "changed_handles": [
            {"handle": "3C", "change": "added", "dxf_name": "LINE", "layer": "DIM"},
        ],
        "summary": {"added": 1, "removed": 0, "modified": 0, "unchanged": 2,
                    "by_type": {"LINE": {"added": 1, "removed": 0, "modified": 0}}},
        "diagnostics": {"comparison_basis": "handle", "warnings": [], "errors": []},
    }


def _empty_diff():
    d = _diff_with_one_added()
    d["changed_handles"] = []
    d["summary"].update({"added": 0, "removed": 0, "modified": 0})
    return d


def _good_patch(staged, original):
    return {
        "schema": CAD_PATCH_SCHEMA_ID, "patch_id": "p-gate-good",
        "target_dwg": {"staged_path": staged, "original_path": original},
        "operations": [{"operation": "create_line", "args": {}}],
        "policy": {"staged_copy": True, "write_mode": "write_copy"},
    }


class TestEveryGateHasNameAndDetail(unittest.TestCase):
    def setUp(self):
        import validator
        self.validator = validator

    def test_all_gates_carry_gate_id_and_detail(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = _write_ir(_good_ir(), tmp)
            report = self.validator.validate_target(ir_path=ir_path)
        self.assertTrue(report["gates"], "no gates emitted")
        for g in report["gates"]:
            self.assertIsInstance(g.get("gate"), str, "gate record missing 'gate' id")
            self.assertTrue(g["gate"])
            self.assertIn("detail", g, "gate %r missing 'detail'" % g.get("id"))


class TestPatchDiffGatesSkipBenignlyOnPlainIr(unittest.TestCase):
    """With only an IR, the patch/diff gates SKIP benignly and don't downgrade."""

    def setUp(self):
        import validator
        self.validator = validator

    def test_plain_ir_still_passes_overall(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = _write_ir(_good_ir(), tmp)
            report = self.validator.validate_target(ir_path=ir_path, run_dir=None)
        self.assertEqual(report["status"], "pass",
                         "benign skips downgraded a clean plain-IR verdict")

    def test_each_patch_diff_gate_present_and_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = _write_ir(_good_ir(), tmp)
            report = self.validator.validate_target(ir_path=ir_path)
        for gid in _PATCH_DIFF_GATES:
            g = _gate(report, gid)
            self.assertIsNotNone(g, "gate %s not emitted" % gid)
            self.assertEqual(g["status"], "skipped",
                             "gate %s should skip with no input, got %r"
                             % (gid, g["status"]))
            # an absent-input skip must be BENIGN (explicit, not silent).
            self.assertTrue(g.get("skip_benign"),
                            "gate %s skipped but not marked skip_benign" % gid)
            self.assertTrue(g.get("message") or g.get("detail"),
                            "gate %s skipped without an explicit reason" % gid)


class TestDiffGatesFire(unittest.TestCase):
    def setUp(self):
        import validator
        self.validator = validator

    def test_diff_expected_changes_passes_on_real_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = _write_ir(_good_ir(), tmp)
            report = self.validator.validate_target(
                ir_path=ir_path, diff_path=_diff_with_one_added())
        g = _gate(report, "diff_expected_changes")
        self.assertEqual(g["status"], "pass")
        cad_schema = _gate(report, "cad_diff_schema")
        self.assertEqual(cad_schema["status"], "pass")

    def test_empty_diff_fails_and_forces_overall_fail(self):
        # A no-effect patch is a HARD failure, not partial.
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = _write_ir(_good_ir(), tmp)
            report = self.validator.validate_target(
                ir_path=ir_path, diff_path=_empty_diff())
        g = _gate(report, "diff_expected_changes")
        self.assertEqual(g["status"], "fail",
                         "empty diff did not fail diff_expected_changes")
        self.assertEqual(report["status"], "fail",
                         "overall verdict not fail despite a no-effect diff")


class TestPatchPolicyGateFires(unittest.TestCase):
    def setUp(self):
        import validator
        self.validator = validator

    def test_good_patch_policy_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = _write_ir(_good_ir(), tmp)
            report = self.validator.validate_target(
                ir_path=ir_path,
                patch_path=_good_patch(os.path.join(tmp, "staged.dwg"),
                                       os.path.join(tmp, "orig.dwg")))
        g = _gate(report, "patch_policy")
        self.assertEqual(g["status"], "pass")

    def test_write_original_patch_fails_overall(self):
        bad = _good_patch(os.path.join("x", "staged.dwg"), os.path.join("x", "orig.dwg"))
        bad["policy"]["write_mode"] = "write_original"
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = _write_ir(_good_ir(), tmp)
            report = self.validator.validate_target(ir_path=ir_path, patch_path=bad)
        g = _gate(report, "patch_policy")
        self.assertEqual(g["status"], "fail")
        self.assertEqual(report["status"], "fail",
                         "an original-write policy must be a HARD safety failure")


class TestPatchRunFolderGates(unittest.TestCase):
    """staged_copy_used / journal_present / original_dwg_unchanged on a run dir."""

    def setUp(self):
        import validator
        self.validator = validator

    def _make_patch_run(self, tmp, *, journal_unchanged=True,
                        with_staged_output=True):
        """Synthesize a patch run folder: staged_input/output.dwg + cad_diff.json
        + cad_patch.json + journal.json (recording original sha before/after)."""
        run = os.path.join(tmp, "patchrun")
        os.makedirs(run, exist_ok=True)
        with open(os.path.join(run, "staged_input.dwg"), "wb") as fh:
            fh.write(b"STAGED-IN")
        if with_staged_output:
            with open(os.path.join(run, "staged_output.dwg"), "wb") as fh:
                fh.write(b"STAGED-OUT")
        with open(os.path.join(run, "cad_diff.json"), "w", encoding="utf-8") as fh:
            json.dump(_diff_with_one_added(), fh)
        with open(os.path.join(run, "cad_patch.json"), "w", encoding="utf-8") as fh:
            json.dump(_good_patch(os.path.join(run, "staged_input.dwg"),
                                  os.path.join(tmp, "orig.dwg")), fh)
        sha_a = "a" * 64
        sha_b = sha_a if journal_unchanged else ("b" * 64)
        journal = {
            "schema": "ariadne.cad_patch.journal.v1",
            "patch_id": "p-gate-good",
            "original_sha256_before": sha_a,
            "original_sha256_after": sha_b,
            "steps": [{"step": "create_staged_copy", "status": "pass"}],
        }
        with open(os.path.join(run, "journal.json"), "w", encoding="utf-8") as fh:
            json.dump(journal, fh)
        return run

    def test_patch_run_gates_fire_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._make_patch_run(tmp)
            report = self.validator.validate_target(run_dir=run)
        self.assertTrue(report["summary"].get("is_patch_run"),
                        "run with staged_*.dwg + journal not recognized as a patch run")
        for gid in ("staged_copy_used", "journal_present", "original_dwg_unchanged"):
            g = _gate(report, gid)
            self.assertIsNotNone(g, "gate %s missing" % gid)
            self.assertEqual(g["status"], "pass",
                             "patch-run gate %s did not pass: %r" % (gid, g))

    def test_original_changed_in_journal_fails_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._make_patch_run(tmp, journal_unchanged=False)
            report = self.validator.validate_target(run_dir=run)
        g = _gate(report, "original_dwg_unchanged")
        self.assertEqual(g["status"], "fail",
                         "journal sha mismatch did not fail original_dwg_unchanged")
        self.assertEqual(report["status"], "fail")

    def test_missing_staged_output_fails_staged_copy_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._make_patch_run(tmp, with_staged_output=False)
            report = self.validator.validate_target(run_dir=run)
        g = _gate(report, "staged_copy_used")
        self.assertEqual(g["status"], "fail",
                         "missing staged_output.dwg did not fail staged_copy_used")


class TestIrOnlyGatesPreserved(unittest.TestCase):
    """The frozen M01 IR gates still fire on a good IR (no regression)."""

    def setUp(self):
        import validator
        self.validator = validator

    def test_core_ir_gates_still_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = _write_ir(_good_ir(), tmp)
            report = self.validator.validate_target(ir_path=ir_path)
        for gid in ("ir_schema_present", "entity_count_consistency",
                    "no_original_write_evidence"):
            g = _gate(report, gid)
            self.assertIsNotNone(g, "core IR gate %s vanished" % gid)
            self.assertEqual(g["status"], "pass",
                             "core IR gate %s regressed: %r" % (gid, g))


if __name__ == "__main__":
    unittest.main()
