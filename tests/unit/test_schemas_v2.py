#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lane E TEST -- new v2/v1 JSON schemas parse, self-validate, and accept fixtures.

Intent (WHY each gate matters, not just WHAT it does):
  * Every new ``schemas/*.v*.json`` must be syntactically loadable with the BOM
    decoder this box requires (``utf-8-sig``). A schema that cannot even parse
    silently disables every downstream contract that references it.
  * When ``jsonschema`` is importable, each schema must pass ``check_schema`` --
    i.e. it must be a *valid Draft-07 schema*, not merely valid JSON. A schema
    that is malformed (bad ``$ref``, wrong meta-schema) would accept garbage.
  * ``dwg_graph_ir.v1`` is the engine-neutral truth IR. It MUST accept the
    canonical fixture the producer emits (``ir_builder.make_fixture_ir()``);
    if the schema and the producer drift apart, the whole IR contract is a lie.

Discoverable by BOTH pytest and ``python -m unittest discover -s tests``.
Standard library only (plus optional ``jsonschema``); BOM-tolerant JSON reads.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

# --- repo-root bootstrap (so tools/* import under unittest discovery) ---------
_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))  # tests/unit -> tests -> repo
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SCHEMAS_DIR = os.path.join(_REPO, "schemas")
_JSON_ENCODING = "utf-8-sig"  # config/schema JSON on this box carries a UTF-8 BOM

# The NEW v2/v1 schemas this packet adds (additive to the frozen v1 schemas).
_NEW_SCHEMA_FILES = (
    "cad_job.v2.schema.json",
    "cad_result.v2.schema.json",
    "operation_registry.v2.schema.json",
    "dwg_graph_ir.v1.schema.json",
    "cad_patch.v1.schema.json",
    "cad_diff.v1.schema.json",
    "validation_report.v1.schema.json",
    "visual_artifact.v1.schema.json",
)


def _load_json(path: str):
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _try_import_jsonschema():
    try:
        import jsonschema  # type: ignore
        return jsonschema
    except Exception:  # pragma: no cover - environment without jsonschema
        return None


class TestNewSchemasParse(unittest.TestCase):
    """Every new schema file exists and parses with the BOM decoder."""

    def test_all_new_schema_files_present_and_parse(self):
        for name in _NEW_SCHEMA_FILES:
            path = os.path.join(_SCHEMAS_DIR, name)
            with self.subTest(schema=name):
                self.assertTrue(os.path.isfile(path), "missing schema file: %s" % path)
                doc = _load_json(path)
                self.assertIsInstance(doc, dict, "%s is not a JSON object" % name)
                # A schema must declare its identity ($id) and a type/defs; we do
                # not over-constrain, but an empty {} would be a useless schema.
                self.assertTrue(
                    doc.get("$id") or doc.get("$schema") or doc.get("type") or doc.get("$defs"),
                    "%s has no $id/$schema/type/$defs -- likely not a real schema" % name,
                )


class TestNewSchemasCheckSchema(unittest.TestCase):
    """When jsonschema is importable, each schema is a valid Draft-07 schema."""

    def setUp(self):
        self.jsonschema = _try_import_jsonschema()
        if self.jsonschema is None:
            self.skipTest("SKIPPED_DEP: jsonschema not importable")

    def test_each_schema_passes_check_schema(self):
        # Prefer the validator class the schema's own $schema implies; default to
        # Draft7 (every new schema declares draft-07).
        Draft7Validator = getattr(self.jsonschema, "Draft7Validator")
        for name in _NEW_SCHEMA_FILES:
            path = os.path.join(_SCHEMAS_DIR, name)
            with self.subTest(schema=name):
                doc = _load_json(path)
                # check_schema raises SchemaError on a malformed schema; a clean
                # return is the pass condition.
                try:
                    Draft7Validator.check_schema(doc)
                except self.jsonschema.exceptions.SchemaError as exc:  # type: ignore[attr-defined]
                    self.fail("%s failed check_schema: %s" % (name, exc))


class TestDwgGraphIrAcceptsFixture(unittest.TestCase):
    """dwg_graph_ir.v1 must accept the producer's canonical fixture IR."""

    def test_make_fixture_ir_validates_against_schema(self):
        import ir_builder  # built by Lane B3; on sys.path via bootstrap

        ir = ir_builder.make_fixture_ir()
        # Structural truths that hold regardless of jsonschema availability: the
        # fixture IS the IR the schema is supposed to describe.
        self.assertEqual(ir.get("schema"), "ariadne.dwg_graph_ir.v1")
        self.assertIsInstance(ir.get("entities"), list)
        self.assertEqual(
            ir["diagnostics"]["entity_count"], len(ir["entities"]),
            "fixture IR violates its own truth gate (entity_count != len(entities))",
        )

        jsonschema = _try_import_jsonschema()
        if jsonschema is None:
            self.skipTest("SKIPPED_DEP: jsonschema not importable (structural checks ran)")

        schema = _load_json(os.path.join(_SCHEMAS_DIR, "dwg_graph_ir.v1.schema.json"))
        jsonschema.Draft7Validator.check_schema(schema)
        validator = jsonschema.Draft7Validator(schema)
        errors = sorted(validator.iter_errors(ir), key=lambda e: list(e.path))
        self.assertEqual(
            errors, [],
            "make_fixture_ir() does not conform to dwg_graph_ir.v1: "
            + "; ".join("%s: %s" % ("/".join(str(p) for p in e.path), e.message)
                       for e in errors[:10]),
        )

    def test_truth_gate_violation_is_caught_by_the_count_authority(self):
        """A corrupted IR (entity_count != len(entities)) must be CAUGHT.

        Subtlety this test encodes honestly: JSON Schema CANNOT express
        "entity_count == len(entities)" (no cross-field/length comparison in
        Draft-07), so a stale count does NOT fail jsonschema validation and
        ir_builder._validate_ir (which prefers jsonschema when available) is
        therefore NOT the truth-gate authority. The authority is the deterministic
        validator gate ``entity_count_consistency``. We prove the gate can
        actually fail (Rule 9: a gate that can't fail is worthless), and we also
        confirm the structural fallback in _validate_ir catches it when
        jsonschema is unavailable."""
        import ir_builder
        import validator

        ir = ir_builder.make_fixture_ir()
        ir["entities"] = ir["entities"][:-1]  # drop one; entity_count now stale
        self.assertNotEqual(
            ir["diagnostics"]["entity_count"], len(ir["entities"]),
            "setup error: corruption did not actually desync the count",
        )

        # The real authority: the deterministic validator gate must FAIL.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = os.path.join(tmp, "bad_ir.json")
            with open(ir_path, "w", encoding="utf-8") as fh:
                json.dump(ir, fh)
            report = validator.validate_target(ir_path=ir_path)
        gate = next(g for g in report["gates"] if g["id"] == "entity_count_consistency")
        self.assertEqual(gate["status"], "fail",
                         "the count-consistency gate did NOT fail on a desynced IR")
        self.assertEqual(report["status"], "fail",
                         "overall verdict not 'fail' despite the required gate failing")

    def test_structural_fallback_catches_count_desync_without_jsonschema(self):
        """When jsonschema is NOT importable, ir_builder._validate_ir falls back to
        structural checks that DO assert the truth gate -- prove that branch
        catches a desync. (Guards the no-dependency environment.)"""
        import ir_builder

        ir = ir_builder.make_fixture_ir()
        ir["entities"] = ir["entities"][:-1]  # stale count

        if _try_import_jsonschema() is not None:
            # Force the structural branch by hiding jsonschema for this call.
            import builtins
            real_import = builtins.__import__

            def _no_jsonschema(name, *a, **k):
                if name == "jsonschema":
                    raise ImportError("hidden for structural-fallback test")
                return real_import(name, *a, **k)

            builtins.__import__ = _no_jsonschema
            try:
                ok, method, errs = ir_builder._validate_ir(ir)
            finally:
                builtins.__import__ = real_import
        else:
            ok, method, errs = ir_builder._validate_ir(ir)

        self.assertEqual(method, "structural",
                         "expected the structural fallback path")
        self.assertFalse(ok, "structural fallback accepted a desynced IR")
        self.assertTrue(
            any("truth gate" in e.lower() or "entity_count" in e for e in errs),
            "structural fallback did not surface the count desync; errors=%r" % errs,
        )


if __name__ == "__main__":
    unittest.main()
