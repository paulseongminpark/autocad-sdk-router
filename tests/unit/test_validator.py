#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lane E TEST -- validator deterministic gates + validation_report.v1 conformance.

Intent (WHY):
  * validator.validate_target is the deterministic verdict engine. On a GOOD
    fixture IR the REQUIRED IR gates (schema present, entity-count consistency,
    staged-copy evidence) must PASS.
  * The entity-count truth gate is the whole point of validation: when
    diagnostics.entity_count != len(entities), that gate MUST FAIL and the
    overall verdict MUST become 'fail'. A validator that can't fail this is
    worthless (Rule 9). We prove it can.
  * The emitted report must CONFORM to validation_report.v1 -- otherwise the
    verdict can't be consumed/validated downstream. We assert conformance both
    structurally and (when jsonschema is present) against the schema.
  * Determinism: the same IR yields the same gate verdicts on repeat runs (no
    sampling / no LLM).

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only
(plus optional jsonschema for the schema-conformance assertion).
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

_SCHEMAS = os.path.join(_REPO, "schemas")
_JSON_ENCODING = "utf-8-sig"


def _try_import_jsonschema():
    try:
        import jsonschema  # type: ignore
        return jsonschema
    except Exception:  # pragma: no cover
        return None


def _good_ir():
    """A staged, internally-consistent IR that should PASS the IR-only gates.

    Built from the real producer (ir_builder) so the validator is tested against
    genuine producer output, then given an original_path so the staged-copy gate
    has the evidence it needs.
    """
    import ir_builder
    ir = ir_builder.make_fixture_ir()
    # Ensure staged-copy evidence: dwg_path under staging/ + a distinct original.
    ir["source"]["dwg_path"] = os.path.join("staging", "golden", "fix", "input.dwg")
    ir["source"]["original_path"] = os.path.join("samples", "input.dwg")
    return ir


def _write_ir(ir, tmp):
    path = os.path.join(tmp, "dwg_graph_ir.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ir, fh, indent=2)
    return path


def _gate(report, gid):
    return next((g for g in report["gates"] if g["id"] == gid), None)


class TestGatesPassOnGoodIr(unittest.TestCase):
    def setUp(self):
        import validator
        self.validator = validator

    def test_required_ir_gates_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = _write_ir(_good_ir(), tmp)
            report = self.validator.validate_target(ir_path=ir_path, run_dir=None)
        schema_gate = _gate(report, "ir_schema_present")
        count_gate = _gate(report, "entity_count_consistency")
        staged_gate = _gate(report, "no_original_write_evidence")
        self.assertEqual(schema_gate["status"], "pass")
        self.assertEqual(count_gate["status"], "pass",
                         "entity-count gate did not pass on a good IR: %r" % count_gate)
        self.assertEqual(staged_gate["status"], "pass")

    def test_count_gate_is_required(self):
        # The truth gate must be REQUIRED; if it were optional, a count failure
        # would only downgrade to partial instead of failing the build.
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = _write_ir(_good_ir(), tmp)
            report = self.validator.validate_target(ir_path=ir_path)
        count_gate = _gate(report, "entity_count_consistency")
        self.assertTrue(count_gate.get("required", True),
                        "entity_count_consistency must be a REQUIRED gate")

    def test_validation_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = _write_ir(_good_ir(), tmp)
            r1 = self.validator.validate_target(ir_path=ir_path)
            r2 = self.validator.validate_target(ir_path=ir_path)
        # Same inputs -> identical gate id/status sequence (ids aside from the
        # random validation_id, which we ignore).
        self.assertEqual(
            [(g["id"], g["status"]) for g in r1["gates"]],
            [(g["id"], g["status"]) for g in r2["gates"]],
            "validator is not deterministic across runs",
        )


class TestEntityCountMismatchFails(unittest.TestCase):
    """A desynced entity_count must FAIL the gate and the overall verdict."""

    def setUp(self):
        import validator
        self.validator = validator

    def test_stale_entity_count_fails_gate_and_overall(self):
        ir = _good_ir()
        # Corrupt: assert one MORE entity than actually present.
        ir["diagnostics"]["entity_count"] = len(ir["entities"]) + 1
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = _write_ir(ir, tmp)
            report = self.validator.validate_target(ir_path=ir_path)
        count_gate = _gate(report, "entity_count_consistency")
        self.assertEqual(count_gate["status"], "fail",
                         "stale entity_count did NOT fail the truth gate")
        # A required-gate failure must drive the overall verdict to 'fail'.
        self.assertEqual(report["status"], "fail",
                         "overall verdict was not 'fail' despite a required gate failing")
        # The failure must be surfaced in errors[] (fail loud, not silent).
        self.assertTrue(any("entity_count_consistency" in e for e in report["errors"]))

    def test_summary_disagreement_fails_gate(self):
        # The validator recovers an INDEPENDENT count to cross-check against the
        # asserted entity_count. Its highest-priority independent source is
        # diagnostics.realized_entity_count (see _summary_count_from_ir). Desync
        # THAT while keeping entity_count == len(entities): the primary check
        # passes but the independent cross-check must catch the disagreement.
        ir = _good_ir()
        self.assertEqual(ir["diagnostics"]["entity_count"], len(ir["entities"]))
        ir["diagnostics"]["realized_entity_count"] = len(ir["entities"]) + 5
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = _write_ir(ir, tmp)
            report = self.validator.validate_target(ir_path=ir_path)
        count_gate = _gate(report, "entity_count_consistency")
        self.assertEqual(count_gate["status"], "fail",
                         "independent summary disagreement did not fail the gate")
        # And it must be reported as the reason (fail loud).
        self.assertIn("realized_entity_count",
                      (count_gate.get("message") or ""),
                      "gate failed but did not name the disagreeing source")


class TestReportConformsToSchema(unittest.TestCase):
    """The emitted report conforms to validation_report.v1."""

    def setUp(self):
        import validator
        self.validator = validator

    def test_report_has_required_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = _write_ir(_good_ir(), tmp)
            report = self.validator.validate_target(ir_path=ir_path)
        for req in ("schema", "validation_id", "status", "gates", "errors",
                    "warnings", "artifacts"):
            self.assertIn(req, report, "report missing required field %s" % req)
        self.assertEqual(report["schema"], "ariadne.validation_report.v1")
        self.assertIn(report["status"], ("pass", "fail", "partial", "blocked"))
        for g in report["gates"]:
            self.assertIn("id", g)
            self.assertIn("status", g)
            self.assertIn(g["status"], ("pass", "fail", "skipped", "blocked"))

    def test_report_validates_against_schema(self):
        jsonschema = _try_import_jsonschema()
        if jsonschema is None:
            self.skipTest("SKIPPED_DEP: jsonschema not importable")
        with open(os.path.join(_SCHEMAS, "validation_report.v1.schema.json"),
                  "r", encoding=_JSON_ENCODING) as fh:
            schema = json.load(fh)
        jsonschema.Draft7Validator.check_schema(schema)
        validator_obj = jsonschema.Draft7Validator(schema)
        # Validate a passing report AND a failing report -- both must conform.
        with tempfile.TemporaryDirectory() as tmp:
            good_path = _write_ir(_good_ir(), tmp)
            good_report = self.validator.validate_target(ir_path=good_path)
            bad_ir = _good_ir()
            bad_ir["diagnostics"]["entity_count"] = 999
            bad_path = os.path.join(tmp, "bad_ir.json")
            with open(bad_path, "w", encoding="utf-8") as fh:
                json.dump(bad_ir, fh)
            bad_report = self.validator.validate_target(ir_path=bad_path)
        for label, report in (("pass", good_report), ("fail", bad_report)):
            errors = sorted(validator_obj.iter_errors(report), key=lambda e: list(e.path))
            self.assertEqual(
                errors, [],
                "%s report does not conform to validation_report.v1: " % label
                + "; ".join("%s: %s" % ("/".join(str(p) for p in e.path), e.message)
                           for e in errors[:8]),
            )

    def test_no_ir_supplied_blocks_required_gates_not_pass(self):
        # No-fake-success: with no IR and no run_dir, required gates must be
        # 'blocked', and the overall verdict must NOT be 'pass'.
        report = self.validator.validate_target(ir_path=None, run_dir=None)
        self.assertNotEqual(report["status"], "pass",
                            "validator returned 'pass' with no inputs (fake success)")
        count_gate = _gate(report, "entity_count_consistency")
        self.assertEqual(count_gate["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
