#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T1 -- the hard jsonschema CONFORMANCE GATE for dwg_graph_ir.v1 + cad_diff.v1.

Intent (WHY):
  * F-C1-1 proved that schema files without a runtime call site are culture, not
    a gate: the IR builder drifted out of conformance for a full wave window and
    nothing caught it. T1 adds a HARD gate at the write boundary. These tests pin
    that the gate actually FAILS on a non-conformant, schema-tagged document
    (write_ir -> IRConformanceError; write_diff -> DiffConformanceError) and
    PASSES a conformant one -- so the gate can never silently degrade to a no-op.
  * The kind-coverage guard converts the F-C1-1 defect-B class (native reader
    emits a geometry.kind the schema enum does not list) from "caught at runtime
    by luck" into "caught here": every kind _NATIVE_CLASS_TO_DXF_KIND can emit
    MUST be admitted by the schema enum.

Stdlib + jsonschema (the gate degrades to a structural check when jsonschema is
absent; on this box it is importable, so the schema branch is the one exercised).
Discoverable by pytest and ``python -m unittest discover -s tests``.
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


def _load_json(path):
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


class TestIRWriteGate(unittest.TestCase):
    """write_ir hard-fails a non-conformant, schema-tagged IR before writing."""

    def setUp(self):
        import ir_builder
        self.ir_builder = ir_builder

    def test_good_ir_passes_and_writes(self):
        ir = self.ir_builder.make_fixture_ir()
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "good", "dwg_graph_ir.json")
            written = self.ir_builder.write_ir(ir, out)
            self.assertTrue(os.path.isfile(written))
            reloaded = self.ir_builder.load_ir(written)
            self.assertEqual(reloaded["schema"], "ariadne.dwg_graph_ir.v1")

    def test_malformed_schema_tagged_ir_raises_and_writes_nothing(self):
        # PASS 3.2 deliberately-malformed fixture: a point OBJECT where the
        # schema requires a point3 ARRAY -- the exact F-C1-1 failure class.
        ir = self.ir_builder.make_fixture_ir()
        ir["entities"][0]["geometry"]["start"] = {"x": 0, "y": 0, "z": 0}
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "bad", "dwg_graph_ir.json")
            with self.assertRaises(self.ir_builder.IRConformanceError):
                self.ir_builder.write_ir(ir, out)
            # gate fires BEFORE any bytes are written.
            self.assertFalse(os.path.exists(out))

    def test_enforce_schema_false_bypasses_gate(self):
        # An explicit opt-out still writes (used for deliberately partial docs).
        ir = self.ir_builder.make_fixture_ir()
        ir["entities"][0]["geometry"]["start"] = {"x": 0, "y": 0, "z": 0}
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "partial", "dwg_graph_ir.json")
            written = self.ir_builder.write_ir(ir, out, enforce_schema=False)
            self.assertTrue(os.path.isfile(written))

    def test_untagged_dict_is_not_gated(self):
        # A doc that does NOT claim the schema is not held to it (gate is
        # schema-scoped, not universal).
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "untagged.json")
            written = self.ir_builder.write_ir({"schema": "something.else", "x": 1}, out)
            self.assertTrue(os.path.isfile(written))

    def test_assert_ir_conforms_raises_on_bad_and_true_on_good(self):
        good = self.ir_builder.make_fixture_ir()
        self.assertTrue(self.ir_builder.assert_ir_conforms(good))
        bad = self.ir_builder.make_fixture_ir()
        bad["symbol_tables"]["viewports"] = [{"name": "vp", "view_direction": {"x": 0, "y": 0, "z": 1}}]
        with self.assertRaises(self.ir_builder.IRConformanceError):
            self.ir_builder.assert_ir_conforms(bad)


class TestDiffWriteGate(unittest.TestCase):
    """write_diff hard-fails a non-conformant, cad_diff.v1-tagged diff."""

    def setUp(self):
        import ir_builder
        import cad_diff
        self.cad_diff = cad_diff
        self.pre = ir_builder.make_fixture_ir()
        self.post = ir_builder.make_fixture_ir()

    def test_good_diff_passes_and_writes(self):
        diff = self.cad_diff.compute_diff(self.pre, self.post)
        self.assertEqual(diff["schema"], "ariadne.cad_diff.v1")
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "diff", "cad_diff.json")
            written = self.cad_diff.write_diff(diff, out)
            self.assertTrue(os.path.isfile(written))

    def test_malformed_diff_raises_and_writes_nothing(self):
        diff = self.cad_diff.compute_diff(self.pre, self.post)
        del diff["diagnostics"]  # required by cad_diff.v1
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "baddiff", "cad_diff.json")
            with self.assertRaises(self.cad_diff.DiffConformanceError):
                self.cad_diff.write_diff(diff, out)
            self.assertFalse(os.path.exists(out))

    def test_malformed_change_record_raises(self):
        diff = self.cad_diff.compute_diff(self.pre, self.post)
        diff["schema"] = "ariadne.cad_diff.v1"
        diff["changed_handles"] = [{"handle": "X"}]  # missing required "change"
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "badchange", "cad_diff.json")
            with self.assertRaises(self.cad_diff.DiffConformanceError):
                self.cad_diff.write_diff(diff, out)


class TestKindCoverageGuard(unittest.TestCase):
    """Every geometry.kind the native reader can emit is admitted by the schema
    enum (F-C1-1 defect-B recurrence guard)."""

    def test_native_kinds_subset_of_schema_enum(self):
        import ir_builder
        schema = _load_json(os.path.join(_SCHEMAS, "dwg_graph_ir.v1.schema.json"))
        enum = set(schema["$defs"]["geometry"]["properties"]["kind"]["enum"])
        native_kinds = {v[1] for v in ir_builder._NATIVE_CLASS_TO_DXF_KIND.values()}
        extract_kinds = set(ir_builder._EXTRACT_KIND_TO_IR_KIND.values())
        missing = (native_kinds | extract_kinds) - enum
        self.assertEqual(
            missing, set(),
            "geometry.kind(s) emitted by the builder but NOT in the schema enum "
            "(the F-C1-1 defect-B class): %s" % sorted(missing))


if __name__ == "__main__":
    unittest.main()
