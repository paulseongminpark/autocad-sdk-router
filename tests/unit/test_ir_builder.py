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


class TestNativeGraphGeometryLifting(unittest.TestCase):
    """T3a: build_ir_from_database_graph's field lifting for the new
    collectModelSpaceGraph fields (ellipse/dimension/text/mtext/polyline).

    build_ir_from_database_graph (the ``inspect.database.graph`` -> IR path
    op_roundtrip_probe's pre/post-inspect actually uses) is otherwise only
    exercised by live/integration/smoke tests gated on a real AutoCAD run --
    this feeds it synthetic raw entity dicts shaped exactly like
    collectModelSpaceGraph's JSON, so the lifting itself is covered without
    any live runtime.
    """

    def _one_entity_ir(self, raw_entity):
        import ir_builder
        graph_result = {"entities": [raw_entity], "modelspace_entities": 1}
        ir = ir_builder.build_ir_from_database_graph(graph_result, {"dwg_path": "fake.dwg"})
        return ir["entities"][0]

    def test_ellipse_lifts_major_axis_and_radius_ratio(self):
        ent = self._one_entity_ir({
            "handle": "1A0", "dxf_name": "AcDbEllipse", "layer": "0",
            "owner_handle": "1F", "space": "model",
            "center": [1.0, 2.0, 0.0], "major_axis": [3.0, 0.0, 0.0],
            "radius_ratio": 0.5, "start_angle": 0.0, "end_angle": 6.283185307179586,
            "normal": [0.0, 0.0, 1.0],
        })
        self.assertEqual(ent["dxf_name"], "ELLIPSE")
        self.assertEqual(ent["geometry"], {
            "kind": "ellipse", "center": [1.0, 2.0, 0.0], "normal": [0.0, 0.0, 1.0],
            "major_axis": [3.0, 0.0, 0.0], "radius_ratio": 0.5,
            "start_angle": 0.0, "end_angle": 6.283185307179586,
        })

    def test_dimension_lifts_points_measurement_and_top_level_block_fields(self):
        ent = self._one_entity_ir({
            "handle": "1A1", "dxf_name": "AcDbRotatedDimension", "layer": "0",
            "owner_handle": "1F", "space": "model",
            "xline1_point": [0.0, 0.0, 0.0], "xline2_point": [100.0, 0.0, 0.0],
            "dim_line_point": [100.0, 20.0, 0.0], "rotation": 0.0, "measurement": 100.0,
            "dim_block_handle": "1A2", "dim_block_name": "*D1",
        })
        self.assertEqual(ent["dxf_name"], "DIMENSION")
        self.assertEqual(ent["geometry"], {
            "kind": "dimension", "xline1_point": [0.0, 0.0, 0.0],
            "xline2_point": [100.0, 0.0, 0.0], "dim_line_point": [100.0, 20.0, 0.0],
            "rotation": 0.0, "measurement": 100.0,
        })
        # dim_block_handle/dim_block_name are TOP-LEVEL entity fields, never
        # inside "geometry" -- see op_roundtrip_probe.py's
        # _expect_create_dimension for why this must hold.
        self.assertEqual(ent["dim_block_handle"], "1A2")
        self.assertEqual(ent["dim_block_name"], "*D1")
        self.assertNotIn("dim_block_handle", ent["geometry"])
        self.assertNotIn("dim_block_name", ent["geometry"])

    def test_text_and_mtext_lift_height(self):
        text_ent = self._one_entity_ir({
            "handle": "1A3", "dxf_name": "AcDbText", "layer": "0",
            "owner_handle": "1F", "space": "model",
            "position": [1.0, 1.0, 0.0], "text": "hi", "height": 3.5,
        })
        self.assertEqual(text_ent["geometry"],
                         {"kind": "text", "position": [1.0, 1.0, 0.0], "text": "hi", "height": 3.5})

        mtext_ent = self._one_entity_ir({
            "handle": "1A4", "dxf_name": "AcDbMText", "layer": "0",
            "owner_handle": "1F", "space": "model",
            "position": [2.0, 2.0, 0.0], "text": "note", "height": 4.25,
        })
        self.assertEqual(mtext_ent["geometry"],
                         {"kind": "mtext", "position": [2.0, 2.0, 0.0], "text": "note", "height": 4.25})

    def test_polyline_lifts_bulge_and_closed(self):
        ent = self._one_entity_ir({
            "handle": "1A5", "dxf_name": "AcDbPolyline", "layer": "0",
            "owner_handle": "1F", "space": "model", "vertex_count": 2,
            "closed": True,
            "vertices": [{"point": [0.0, 0.0, 0.0], "bulge": 0.5},
                        {"point": [10.0, 0.0, 0.0], "bulge": 0.0}],
        })
        self.assertEqual(ent["geometry"], {
            "kind": "lwpolyline", "closed": True,
            "vertices": [{"point": [0.0, 0.0, 0.0], "bulge": 0.5},
                        {"point": [10.0, 0.0, 0.0], "bulge": 0.0}],
        })

    def test_spline_lifts_degree_closed_fit_points_and_top_level_nurbs_fields(self):
        ent = self._one_entity_ir({
            "handle": "1A6", "dxf_name": "AcDbSpline", "layer": "0",
            "owner_handle": "1F", "space": "model",
            "degree": 3, "closed": False,
            "fit_points": [[0.0, 0.0, 0.0], [10.0, 5.0, 0.0], [20.0, 0.0, 0.0]],
            "spline_control_points": [[0.0, 0.0, 0.0], [6.0, 8.0, 0.0], [20.0, 0.0, 0.0]],
            "spline_knots": [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0],
        })
        self.assertEqual(ent["dxf_name"], "SPLINE")
        self.assertEqual(ent["geometry"], {
            "kind": "spline", "degree": 3, "closed": False,
            "fit_points": [[0.0, 0.0, 0.0], [10.0, 5.0, 0.0], [20.0, 0.0, 0.0]],
        })
        # spline_control_points/spline_knots are TOP-LEVEL entity fields, never
        # inside "geometry" -- see op_roundtrip_probe.py's _expect_create_spline
        # for why this must hold (AutoCAD's own fit-to-NURBS conversion result,
        # not derivable from write.entity.spline's args alone).
        self.assertEqual(ent["spline_control_points"],
                         [[0.0, 0.0, 0.0], [6.0, 8.0, 0.0], [20.0, 0.0, 0.0]])
        self.assertEqual(ent["spline_knots"], [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0])
        self.assertNotIn("spline_control_points", ent["geometry"])
        self.assertNotIn("spline_knots", ent["geometry"])

    def test_aligned_dimension_lifts_points_and_measurement(self):
        ent = self._one_entity_ir({
            "handle": "1A7", "dxf_name": "AcDbAlignedDimension", "layer": "0",
            "owner_handle": "1F", "space": "model",
            "xline1_point": [0.0, 0.0, 0.0], "xline2_point": [100.0, 0.0, 0.0],
            "dim_line_point": [100.0, 20.0, 0.0], "measurement": 100.0,
            "dim_block_handle": "1A8", "dim_block_name": "*D2",
        })
        self.assertEqual(ent["dxf_name"], "DIMENSION")
        self.assertEqual(ent["geometry"], {
            "kind": "dimension", "xline1_point": [0.0, 0.0, 0.0],
            "xline2_point": [100.0, 0.0, 0.0], "dim_line_point": [100.0, 20.0, 0.0],
            "measurement": 100.0,
        })
        self.assertEqual(ent["dim_block_handle"], "1A8")
        self.assertEqual(ent["dim_block_name"], "*D2")

    def test_radial_dimension_lifts_center_chord_and_top_level_leader_length(self):
        ent = self._one_entity_ir({
            "handle": "1A9", "dxf_name": "AcDbRadialDimension", "layer": "0",
            "owner_handle": "1F", "space": "model",
            "center": [0.0, 0.0, 0.0], "chord_point": [10.0, 0.0, 0.0],
            "leader_length": 5.0, "measurement": 10.0,
        })
        self.assertEqual(ent["dxf_name"], "DIMENSION")
        self.assertEqual(ent["geometry"], {
            "kind": "dimension", "center": [0.0, 0.0, 0.0], "chord_point": [10.0, 0.0, 0.0],
            "measurement": 10.0,
        })
        # leader_length is a TOP-LEVEL entity field, never inside "geometry" --
        # live-discovered (2026-07-02 T3a-batch2 re-cert) to be AutoCAD's own
        # recomputed value, not a ctor-arg echo (see op_roundtrip_probe.py's
        # _expect_create_dimension_radial).
        self.assertEqual(ent["leader_length"], 5.0)
        self.assertNotIn("leader_length", ent["geometry"])

    def test_diametric_dimension_lifts_chord_points_and_top_level_leader_length(self):
        ent = self._one_entity_ir({
            "handle": "1AA", "dxf_name": "AcDbDiametricDimension", "layer": "0",
            "owner_handle": "1F", "space": "model",
            "chord_point": [-10.0, 0.0, 0.0], "far_chord_point": [10.0, 0.0, 0.0],
            "leader_length": 5.0, "measurement": 20.0,
        })
        self.assertEqual(ent["dxf_name"], "DIMENSION")
        self.assertEqual(ent["geometry"], {
            "kind": "dimension", "chord_point": [-10.0, 0.0, 0.0],
            "far_chord_point": [10.0, 0.0, 0.0], "measurement": 20.0,
        })
        self.assertEqual(ent["leader_length"], 5.0)
        self.assertNotIn("leader_length", ent["geometry"])

    def test_ordinate_dimension_lifts_points_and_top_level_origin(self):
        ent = self._one_entity_ir({
            "handle": "1AB", "dxf_name": "AcDbOrdinateDimension", "layer": "0",
            "owner_handle": "1F", "space": "model",
            "defining_point": [10.0, 5.0, 0.0], "leader_end_point": [10.0, 15.0, 0.0],
            "use_x_axis": True, "origin": [0.0, 0.0, 0.0], "measurement": 10.0,
        })
        self.assertEqual(ent["dxf_name"], "DIMENSION")
        self.assertEqual(ent["geometry"], {
            "kind": "dimension", "defining_point": [10.0, 5.0, 0.0],
            "leader_end_point": [10.0, 15.0, 0.0], "use_x_axis": True, "measurement": 10.0,
        })
        # origin is a TOP-LEVEL entity field, never inside "geometry" -- it is
        # not a write.entity.dim.ordinate ctor arg at all (see op_roundtrip_
        # probe.py's _expect_create_dimension_ordinate).
        self.assertEqual(ent["origin"], [0.0, 0.0, 0.0])
        self.assertNotIn("origin", ent["geometry"])

    def test_leader_lifts_vertices_and_arrowhead_splined(self):
        ent = self._one_entity_ir({
            "handle": "1AC", "dxf_name": "AcDbLeader", "layer": "0",
            "owner_handle": "1F", "space": "model",
            "vertices": [[0.0, 0.0, 0.0], [10.0, 10.0, 0.0], [20.0, 10.0, 0.0]],
            "has_arrow_head": True, "splined": False,
        })
        self.assertEqual(ent["dxf_name"], "LEADER")
        self.assertEqual(ent["geometry"], {
            "kind": "leader",
            "vertices": [{"point": [0.0, 0.0, 0.0]}, {"point": [10.0, 10.0, 0.0]},
                        {"point": [20.0, 10.0, 0.0]}],
            "has_arrow_head": True, "splined": False,
        })


if __name__ == "__main__":
    unittest.main()
