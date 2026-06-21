#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M02 TEST -- ir_builder.build_ir_from_database_graph -> native_full IR.

Intent (WHY):
  * build_ir_from_database_graph is the seam that turns a NATIVE ObjectARX
    database-graph result (native class names, inline geometry) into the
    engine-neutral ariadne.dwg_graph_ir.v1 at coverage_level=native_full. If that
    mapping drifts, every downstream consumer (sqlite store, diff, validation,
    lineage) silently reads a wrong shape. We pin it against the REAL live result.
  * The whole point of the IR is the cross-engine TRUTH GATE: the golden DWG has
    21747 modelspace entities, asserted three ways -- the native result's
    modelspace_entities, the IR's diagnostics.entity_count, and len(entities) --
    all must equal 21747. A builder that can't hold that line is worthless (Rule 9).
  * The class->(dxf_name, kind) crosswalk is load-bearing: native emits dxf_name =
    the runtime class (AcDbLine, AcDb2dPolyline, AcDbBlockReference, ...) and the
    IR must surface the DXF type (LINE, POLYLINE, INSERT, ...). We assert the
    by-type histogram matches the cross-engine ground truth exactly.
  * The emitted IR must CONFORM to dwg_graph_ir.v1 (structurally always; against
    the JSON schema when jsonschema is importable) -- else it can't be validated
    downstream.

Two layers of evidence:
  * a tiny SYNTHETIC native result (deterministic, always runs) proving the
    mapping, truth gate, and required-field shape;
  * the LIVE golden native result (runs/dwg_truth_autocad_cad_job_*/...): when
    present, asserts the full 21747 truth gate + the by-type histogram. When the
    artifact is absent the live test SKIPS with an explicit reason (never fails).

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only
(plus optional jsonschema for the schema-conformance assertion).
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SCHEMAS = os.path.join(_REPO, "schemas")
_GOLDEN = os.path.join(_REPO, "tests", "golden")
_JSON_ENCODING = "utf-8-sig"

# The live native graph result the M02 contract pins (the ``.result`` object is
# what build_ir_from_database_graph consumes).
_LIVE_NATIVE_RESULT = os.path.join(
    _REPO, "runs", "dwg_truth_autocad_cad_job_20260622_012807",
    "native_cad_job_result.json")

# Cross-engine ground truth for the golden DWG.
_GOLDEN_TOTAL = 21747
_GOLDEN_BY_TYPE = {
    "LINE": 16276, "INSERT": 2027, "POLYLINE": 1874, "ARC": 753,
    "HATCH": 669, "MTEXT": 106, "CIRCLE": 33, "TEXT": 9,
}


def _load_json(path):
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _try_import_jsonschema():
    try:
        import jsonschema  # type: ignore
        return jsonschema
    except Exception:  # pragma: no cover
        return None


def _synthetic_native_result():
    """A tiny native ``inspect.database.graph`` result object (the shape of the
    ``.result`` key), with native class names + inline geometry. Mirrors the live
    artifact's structure so the mapping is exercised without the 15MB file.
    """
    return {
        "modelspace_entities": 4,
        "database": {"header_vars": {"ACADVER": "AC1032"}},
        "symbol_tables": {
            "layers": [
                {"name": "0", "handle": "10", "color_index": 7},
                {"name": "WALLS", "handle": "11", "color_index": 1},
            ],
            "linetypes": [{"name": "Continuous", "handle": "14"}],
            "text_styles": [{"name": "Standard", "handle": "15"}],
        },
        "block_table_records": [
            {"name": "*Model_Space", "handle": "1F", "is_layout": True},
            {"name": "DOOR", "handle": "A0", "entity_count": 1},
        ],
        "block_definitions": [
            {"name": "DOOR", "handle": "A0", "entity_count": 1},
        ],
        "layouts": [{"name": "Model", "handle": "22", "tab_order": 0}],
        "dictionaries": [{"handle": "C", "name": "ROOT", "entries": []}],
        "xrecords": [],
        "xrefs": [],
        "entities": [
            {"handle": "2A7", "dxf_name": "AcDbLine", "owner_handle": "1F",
             "space": "model", "layer": "0",
             "start": {"x": 0.0, "y": 0.0, "z": 0.0},
             "end": {"x": 10.0, "y": 0.0, "z": 0.0}},
            {"handle": "2A8", "dxf_name": "AcDbCircle", "owner_handle": "1F",
             "space": "model", "layer": "WALLS",
             "center": {"x": 5.0, "y": 5.0, "z": 0.0}, "radius": 2.5},
            {"handle": "2A9", "dxf_name": "AcDb2dPolyline", "owner_handle": "1F",
             "space": "model", "layer": "WALLS",
             "vertices": [{"x": 0, "y": 0, "z": 0}, {"x": 1, "y": 1, "z": 0}]},
            {"handle": "2AA", "dxf_name": "AcDbBlockReference", "owner_handle": "1F",
             "space": "model", "layer": "0", "block_name": "DOOR",
             "block_record_handle": "A0",
             "position": {"x": 1.0, "y": 2.0, "z": 0.0},
             "scale": {"x": 1.0, "y": 1.0, "z": 1.0}, "rotation": 0.0},
        ],
        "coverage": {
            "sections_present": ["entities", "layers", "block_definitions"],
            "sections_skipped": [],
            "layers": "implemented",
            "entities": "implemented",
            "counts": {"layers": 2, "block_definitions": 1},
        },
    }


def _source_meta():
    return {
        "dwg_path": os.path.join("staging", "dwg_xyz", "input.dwg"),
        "original_path": os.path.join("staging", "dwg_20260617_191504", "input.dwg"),
        "dwg_name": "input.dwg",
        "format": "dwg",
        "byte_size": 2524981,
        "sha256": "0" * 64,
        "extractor": "native_objectarx",
        "engine_tier": "native_arx",
        "route": "dwg_truth_autocad",
    }


class TestSyntheticNativeMapping(unittest.TestCase):
    """The native-class -> (class, dxf_name, kind) mapping and required shape."""

    def setUp(self):
        import ir_builder
        self.ir_builder = ir_builder
        self.ir = ir_builder.build_ir_from_database_graph(
            _synthetic_native_result(), _source_meta())

    def test_coverage_level_is_native_full(self):
        self.assertEqual(self.ir["schema"], "ariadne.dwg_graph_ir.v1")
        self.assertEqual(self.ir["coverage_level"], "native_full")

    def test_truth_gate_holds_by_construction(self):
        diag = self.ir["diagnostics"]
        self.assertEqual(diag["entity_count"], len(self.ir["entities"]))
        self.assertEqual(diag["entity_count"], 4)
        self.assertEqual(diag.get("realized_entity_count"), 4)

    def test_native_class_maps_to_dxf_and_kind(self):
        # native dxf_name is the runtime class; the IR must surface BOTH the
        # runtime class (entity.class) and the DXF type (entity.dxf_name).
        by_handle = {e["handle"]: e for e in self.ir["entities"]}
        line = by_handle["2A7"]
        self.assertEqual(line["class"], "AcDbLine")
        self.assertEqual(line["dxf_name"], "LINE")
        self.assertEqual(line["geometry"]["kind"], "line")

        circle = by_handle["2A8"]
        self.assertEqual(circle["dxf_name"], "CIRCLE")
        self.assertEqual(circle["geometry"]["kind"], "circle")
        # circle bbox is grown by the radius around the center.
        self.assertEqual(circle["bbox"], [2.5, 2.5, 0.0, 7.5, 7.5, 0.0])

        poly = by_handle["2A9"]
        self.assertEqual(poly["dxf_name"], "POLYLINE")
        self.assertEqual(poly["geometry"]["kind"], "polyline")

        ins = by_handle["2AA"]
        self.assertEqual(ins["class"], "AcDbBlockReference")
        self.assertEqual(ins["dxf_name"], "INSERT")
        self.assertEqual(ins["geometry"]["kind"], "block_reference")

    def test_every_entity_carries_required_ir_fields(self):
        required = ("handle", "class", "dxf_name", "owner_handle", "space",
                    "layer", "bbox", "geometry", "source")
        for ent in self.ir["entities"]:
            for rk in required:
                self.assertIn(rk, ent,
                              "entity %r missing required IR field %s"
                              % (ent.get("handle"), rk))
            # per-entity provenance decoded flag must be present and truthful.
            self.assertIn("decoded", ent["source"])
            self.assertTrue(ent["source"]["decoded"],
                            "a recognized native class was marked undecoded")

    def test_entities_by_type_histogram(self):
        ebt = self.ir["diagnostics"]["entities_by_type"]
        self.assertEqual(ebt, {"LINE": 1, "CIRCLE": 1, "POLYLINE": 1, "INSERT": 1})
        self.assertEqual(sum(ebt.values()), len(self.ir["entities"]))

    def test_rich_sections_carried_through(self):
        # native_full carries symbol tables + block defs + layouts + dictionaries.
        self.assertIn("block_table_records", self.ir["symbol_tables"])
        self.assertEqual(len(self.ir["block_definitions"]), 1)
        self.assertEqual(len(self.ir["layouts"]), 1)
        self.assertEqual(len(self.ir["dictionaries"]), 1)
        # INSERT entities are projected into the block_references convenience index.
        self.assertEqual(len(self.ir["block_references"]), 1)
        self.assertEqual(self.ir["block_references"][0]["block_name"], "DOOR")

    def test_unknown_native_class_degrades_truthfully(self):
        # No-fake-success: an unrecognized class must NOT claim a decoded kind.
        result = _synthetic_native_result()
        result["entities"].append({
            "handle": "2AB", "dxf_name": "AcDbWeirdProxyThing",
            "owner_handle": "1F", "space": "model", "layer": "0"})
        result["modelspace_entities"] = 5
        ir = self.ir_builder.build_ir_from_database_graph(result, _source_meta())
        weird = next(e for e in ir["entities"] if e["handle"] == "2AB")
        self.assertEqual(weird["geometry"]["kind"], "unsupported")
        self.assertFalse(weird["source"]["decoded"])
        # and it still counts toward the truth gate.
        self.assertEqual(ir["diagnostics"]["entity_count"], len(ir["entities"]))
        self.assertEqual(ir["diagnostics"]["entity_count"], 5)


class TestSyntheticIrSchemaConforms(unittest.TestCase):
    """The native_full IR conforms to dwg_graph_ir.v1."""

    def setUp(self):
        import ir_builder
        self.ir = ir_builder.build_ir_from_database_graph(
            _synthetic_native_result(), _source_meta())

    def test_structural_required_keys(self):
        for k in ("schema", "source", "database", "symbol_tables",
                  "entities", "diagnostics"):
            self.assertIn(k, self.ir, "IR missing top-level key %s" % k)
        self.assertIn("layers", self.ir["symbol_tables"])
        for k in ("entity_count", "warnings", "errors", "coverage"):
            self.assertIn(k, self.ir["diagnostics"])

    def test_validates_against_schema(self):
        jsonschema = _try_import_jsonschema()
        if jsonschema is None:
            self.skipTest("SKIPPED_DEP: jsonschema not importable")
        schema = _load_json(os.path.join(_SCHEMAS, "dwg_graph_ir.v1.schema.json"))
        jsonschema.Draft7Validator.check_schema(schema)
        validator = jsonschema.Draft7Validator(schema)
        errors = sorted(validator.iter_errors(self.ir), key=lambda e: list(e.path))
        self.assertEqual(
            errors, [],
            "native_full IR does not conform to dwg_graph_ir.v1: "
            + "; ".join("%s: %s" % ("/".join(str(p) for p in e.path), e.message)
                       for e in errors[:8]),
        )


class TestLiveNativeResultTruthGate(unittest.TestCase):
    """The LIVE golden native result builds a 21747 native_full IR (truth gate)."""

    def setUp(self):
        if not os.path.isfile(_LIVE_NATIVE_RESULT):
            self.skipTest("SKIPPED_FIXTURE: live native graph result not present: %s"
                          % _LIVE_NATIVE_RESULT)
        import ir_builder
        self.ir_builder = ir_builder
        # load_native_graph_result returns the ``.result`` object (BOM-tolerant).
        self.result = ir_builder.load_native_graph_result(_LIVE_NATIVE_RESULT)

    def test_result_object_is_the_consumable_shape(self):
        self.assertIsInstance(self.result, dict)
        self.assertEqual(self.result.get("modelspace_entities"), _GOLDEN_TOTAL)
        self.assertEqual(len(self.result.get("entities", [])), _GOLDEN_TOTAL)

    def test_build_ir_holds_21747_three_ways(self):
        ir = self.ir_builder.build_ir_from_database_graph(
            self.result, _source_meta())
        self.assertEqual(ir["coverage_level"], "native_full")
        diag = ir["diagnostics"]
        # 21747 == 21747 == 21747 (native asserted == diagnostics == realized len).
        self.assertEqual(self.result["modelspace_entities"], _GOLDEN_TOTAL)
        self.assertEqual(diag["entity_count"], _GOLDEN_TOTAL)
        self.assertEqual(len(ir["entities"]), _GOLDEN_TOTAL)
        # coverage match flag must be honest (native count == realized).
        self.assertTrue(diag["coverage"]["match"])
        self.assertEqual(diag["coverage"]["modelspace_count_from_native"],
                         _GOLDEN_TOTAL)

    def test_by_type_histogram_matches_ground_truth(self):
        ir = self.ir_builder.build_ir_from_database_graph(
            self.result, _source_meta())
        ebt = ir["diagnostics"]["entities_by_type"]
        self.assertEqual(
            ebt, _GOLDEN_BY_TYPE,
            "native_full by-type histogram drifted from the cross-engine truth")
        self.assertEqual(sum(ebt.values()), _GOLDEN_TOTAL)

    def test_live_ir_schema_conforms(self):
        jsonschema = _try_import_jsonschema()
        if jsonschema is None:
            self.skipTest("SKIPPED_DEP: jsonschema not importable")
        ir = self.ir_builder.build_ir_from_database_graph(
            self.result, _source_meta())
        schema = _load_json(os.path.join(_SCHEMAS, "dwg_graph_ir.v1.schema.json"))
        validator = jsonschema.Draft7Validator(schema)
        errors = sorted(validator.iter_errors(ir), key=lambda e: list(e.path))
        self.assertEqual(
            errors, [],
            "live native_full IR does not conform to dwg_graph_ir.v1: "
            + "; ".join("%s: %s" % ("/".join(str(p) for p in e.path), e.message)
                       for e in errors[:8]),
        )


if __name__ == "__main__":
    unittest.main()
