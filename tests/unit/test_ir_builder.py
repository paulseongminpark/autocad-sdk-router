#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lane E TEST -- ir_builder.build_ir_from_extract: mapping, counts, coverage warning.

Intent (WHY):
  * build_ir_from_extract normalizes a router ``dwg_geometry_extract.v1`` payload
    into the engine-neutral IR. The two facts the rest of the pipeline trusts are
    diagnostics.entity_count and entities_by_type. This test feeds a KNOWN fake
    extract and asserts those come out exactly right -- if the mapping miscounts
    or mistypes, every downstream count/diff is poisoned.
  * The truth gate (entity_count == len(entities)) must hold BY CONSTRUCTION for
    any extract, including one whose summary disagrees.
  * No-fake-success on coverage: when summary.modelspace_count != realized count,
    the builder must WARN and set coverage.match=False -- it must NOT silently
    smooth the mismatch into a green IR. We assert the warning actually fires.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
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


def _fake_extract(summary_count):
    """A small extract with 3 entities (LINE, LINE, CIRCLE) across 2 layers.

    ``summary_count`` lets a test deliberately set modelspace_count to agree
    (3) or disagree (e.g. 4) with the realized entity count.
    """
    return {
        "schema": "ariadne.dwg_geometry_extract.v1",
        "route": "dwg_truth_autocad",
        "extractor": "test_synthetic",
        "status": "ok",
        "source": {"dwg_name": "fake.dwg", "format": "dwg"},
        "summary": {
            "modelspace_count": summary_count,
            "entities_by_type": {"LINE": 2, "CIRCLE": 1},
        },
        "entities": [
            {"handle": "100", "object_id": "o1", "type": "LINE", "layer": "0",
             "geometry": {"kind": "line",
                          "start": {"x": 0, "y": 0, "z": 0},
                          "end": {"x": 10, "y": 0, "z": 0}}},
            {"handle": "101", "object_id": "o2", "type": "LINE", "layer": "WALLS",
             "geometry": {"kind": "line",
                          "start": {"x": 0, "y": 0, "z": 0},
                          "end": {"x": 0, "y": 7, "z": 0}}},
            {"handle": "102", "object_id": "o3", "type": "CIRCLE", "layer": "WALLS",
             "geometry": {"kind": "circle",
                          "center": {"x": 5, "y": 5, "z": 0}, "radius": 2.5}},
        ],
    }


_SOURCE_META = {
    "extractor": "test_synthetic",
    "engine_tier": "accoreconsole_lisp",
    "route": "dwg_truth_autocad",
    "dwg_path": "staging/golden/test/fake.dwg",
    "original_path": "samples/fake.dwg",
    "byte_size": 0,
}


class TestBuildIrMapping(unittest.TestCase):
    """A known extract maps to a valid IR with correct counts and types."""

    def setUp(self):
        import ir_builder
        self.ir_builder = ir_builder
        self.ir = ir_builder.build_ir_from_extract(
            _fake_extract(summary_count=3), summary=None, source_meta=_SOURCE_META,
        )

    def test_ir_is_well_formed_and_schema_tagged(self):
        self.assertEqual(self.ir.get("schema"), "ariadne.dwg_graph_ir.v1")
        self.assertEqual(self.ir.get("coverage_level"), "geometry_only")
        self.assertIsInstance(self.ir.get("entities"), list)
        # Producer's own validator must accept its output.
        ok, method, errs = self.ir_builder._validate_ir(self.ir)
        self.assertTrue(ok, "ir_builder produced an IR its own validator rejects "
                            "(method=%s): %r" % (method, errs))

    def test_entity_count_correct_and_truth_gate_holds(self):
        diag = self.ir["diagnostics"]
        self.assertEqual(diag["entity_count"], 3)
        self.assertEqual(diag["entity_count"], len(self.ir["entities"]),
                         "truth gate violated: entity_count != len(entities)")

    def test_entities_by_type_correct(self):
        self.assertEqual(
            self.ir["diagnostics"]["entities_by_type"],
            {"LINE": 2, "CIRCLE": 1},
        )

    def test_layers_derived_from_entities(self):
        names = {l["name"] for l in self.ir["symbol_tables"]["layers"]}
        self.assertEqual(names, {"0", "WALLS"})

    def test_required_entity_fields_and_class_mapping(self):
        # Every entity carries the IR-required fields; DXF->runtime class mapping
        # populated 'class' even though the extract had no runtime_type.
        by_handle = {e["handle"]: e for e in self.ir["entities"]}
        for h in ("100", "101", "102"):
            e = by_handle[h]
            for rk in ("handle", "class", "dxf_name", "owner_handle", "space",
                       "layer", "bbox", "geometry", "source"):
                self.assertIn(rk, e, "entity %s missing %s" % (h, rk))
        self.assertEqual(by_handle["100"]["class"], "AcDbLine")
        self.assertEqual(by_handle["102"]["class"], "AcDbCircle")
        self.assertEqual(by_handle["100"]["geometry"]["kind"], "line")

    def test_bbox_computed_for_line_and_circle(self):
        by_handle = {e["handle"]: e for e in self.ir["entities"]}
        # LINE (0,0)->(10,0): AABB = [0,0,0,10,0,0]
        self.assertEqual(by_handle["100"]["bbox"], [0.0, 0.0, 0.0, 10.0, 0.0, 0.0])
        # CIRCLE center (5,5) r=2.5: AABB = [2.5,2.5,0,7.5,7.5,0]
        self.assertEqual(by_handle["102"]["bbox"], [2.5, 2.5, 0.0, 7.5, 7.5, 0.0])

    def test_coverage_match_true_when_summary_agrees(self):
        cov = self.ir["diagnostics"]["coverage"]
        self.assertTrue(cov["match"])
        self.assertEqual(cov["modelspace_count_from_summary"], 3)
        self.assertEqual(cov["realized_entity_count"], 3)


class TestCoverageMismatchWarns(unittest.TestCase):
    """A summary/realized count mismatch WARNS and sets coverage.match=False."""

    def test_mismatch_produces_warning_not_silent_pass(self):
        import ir_builder
        # summary claims 4 entities but only 3 are present -> must warn.
        ir = ir_builder.build_ir_from_extract(
            _fake_extract(summary_count=4), summary=None, source_meta=_SOURCE_META,
        )
        diag = ir["diagnostics"]
        # Truth gate STILL holds (entity_count is the realized length).
        self.assertEqual(diag["entity_count"], 3)
        self.assertEqual(diag["entity_count"], len(ir["entities"]))
        # But coverage cross-check must record the disagreement.
        self.assertFalse(diag["coverage"]["match"],
                         "coverage.match should be False when summary disagrees")
        self.assertEqual(diag["coverage"]["modelspace_count_from_summary"], 4)
        warnings = diag.get("warnings") or []
        self.assertTrue(
            any("mismatch" in w.lower() for w in warnings),
            "expected an entity-count mismatch warning, got: %r" % warnings,
        )

    def test_absent_summary_count_warns(self):
        import ir_builder
        extract = _fake_extract(summary_count=3)
        extract["summary"].pop("modelspace_count")  # no cross-check available
        ir = ir_builder.build_ir_from_extract(extract, summary=None, source_meta=_SOURCE_META)
        diag = ir["diagnostics"]
        self.assertEqual(diag["entity_count"], 3)  # still correct
        self.assertFalse(diag["coverage"]["match"])  # can't claim a match
        self.assertTrue(
            any("cannot cross-check" in w.lower() or "absent" in w.lower()
                for w in (diag.get("warnings") or [])),
            "expected a 'cannot cross-check' warning when summary count is absent",
        )


class TestRoundTripThroughDisk(unittest.TestCase):
    """write_ir + load_ir round-trips the IR byte-for-structure."""

    def test_write_then_load_is_identical(self):
        import ir_builder
        import tempfile
        ir = ir_builder.make_fixture_ir()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ir.json")
            written = ir_builder.write_ir(ir, path)
            self.assertEqual(written, path)
            self.assertTrue(os.path.isfile(path))
            reloaded = ir_builder.load_ir(path)
            self.assertEqual(reloaded, ir, "IR did not round-trip through disk")


if __name__ == "__main__":
    unittest.main()
