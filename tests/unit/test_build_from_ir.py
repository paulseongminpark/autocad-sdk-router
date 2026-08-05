#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEST -- tools/build_from_ir.py: the IR -> DXF regenerator's defect regressions.

Intent (WHY):
  Every test in the "issue regression" classes below pins ONE defect the HDC 267
  / Okpo 16 round-trip campaign found and fixed (GitHub issues #49, #51, #53,
  #54, #55, #56, #58, #59, #60). The campaign's fixes live on a collaborator's
  machine; these tests are what stops the SAME defect from being reintroduced
  here. Each test therefore asserts the OBSERVABLE end state (reload the written
  DXF and read it back), not the code path taken -- a fix that only works
  in-memory is not a fix, because the pipeline's next step is DXF -> DWG.

  Field names come from the IR schema of record (tools/ir_builder.py,
  schemas/dwg_graph_ir.v1.schema.json), not from the issue snippets.

Discoverable by pytest and ``python -m unittest discover -s tests``.
Requires ezdxf (declared in requirements-full.txt, used across tools/e2).
"""
from __future__ import annotations

import io
import math
import os
import sys
import tempfile
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ezdxf  # noqa: E402

from tools.build_from_ir import (  # noqa: E402
    SUPPORTED_KINDS, BuildReport, build_dxf_from_ir,
)
from tools.ir_builder import make_fixture_ir  # noqa: E402


# --- helpers ------------------------------------------------------------------

def _reload(doc):
    """Write the drawing to DXF text and read it back -- the trip that matters."""
    stream = io.StringIO()
    doc.write(stream)
    stream.seek(0)
    return ezdxf.read(stream)


def _ir(entities=None, *, symbol_tables=None, block_definitions=None):
    """A minimal dwg_graph_ir.v1-shaped document (only the keys the builder reads)."""
    tables = {"layers": [{"name": "0"}]}
    if symbol_tables:
        tables.update(symbol_tables)
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "ir_version": "test",
        "coverage_level": "native_full",
        "source": {"dwg_name": "synthetic.dwg"},
        "database": {"header_vars": {}},
        "symbol_tables": tables,
        "block_definitions": block_definitions or [],
        "block_references": [],
        "entities": entities or [],
        "diagnostics": {"entity_count": len(entities or [])},
    }


def _ent(kind, geometry, *, handle="1A", layer="0", space="model", **top_level):
    ent = {
        "handle": handle,
        "class": "AcDbEntity",
        "dxf_name": kind.upper(),
        "owner_handle": "1F",
        "space": space,
        "layer": layer,
        "bbox": None,
        "geometry": dict(geometry, kind=kind),
        "source": {"extractor": "test", "engine_tier": "test", "route": "test",
                   "decoded": True},
    }
    ent.update(top_level)
    return ent


class PublicApiTest(unittest.TestCase):
    """The contract the rest of the pipeline codes against."""

    def test_returns_drawing_and_report(self):
        doc, report = build_dxf_from_ir(make_fixture_ir())
        self.assertIsInstance(report, BuildReport)
        self.assertEqual(report.added["line"], 1)
        self.assertEqual(report.added["circle"], 1)
        self.assertEqual(report.added["block_reference"], 1)
        self.assertEqual(report.total_added, 3)
        self.assertEqual(dict(report.errors), {})
        self.assertIn("0", doc.layers)

    def test_out_path_writes_a_readable_dxf(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "sub", "rebuilt.dxf")
            _, report = build_dxf_from_ir(make_fixture_ir(), out)
            self.assertTrue(os.path.isfile(out))
            again = ezdxf.readfile(out)
            self.assertEqual(len(list(again.modelspace())), report.total_added)

    def test_roundtrip_kind_counts_match_the_ir(self):
        """BUNDLE 5: build -> reload -> per-kind counts equal the IR's own."""
        ir = make_fixture_ir()
        doc, report = build_dxf_from_ir(ir)
        want = {}
        for ent in ir["entities"]:
            want[ent["dxf_name"]] = want.get(ent["dxf_name"], 0) + 1
        got = {}
        for entity in _reload(doc).modelspace():
            got[entity.dxftype()] = got.get(entity.dxftype(), 0) + 1
        self.assertEqual(got, want)
        self.assertEqual(report.total_skipped, 0)

    def test_unrebuildable_kind_is_counted_with_a_reason(self):
        """ACIS-backed geometry cannot come back from IR -- it must still be counted."""
        _, report = build_dxf_from_ir(_ir([_ent("region", {})]))
        self.assertEqual(report.total_added, 0)
        self.assertEqual(report.skipped["region:acis_binary_not_in_ir"], 1)

    def test_supported_kinds_cover_the_defect_issues(self):
        """The kinds the campaign's issues are about must all be rebuildable."""
        for kind in ("wipeout", "spline", "hatch", "face3d", "leader",
                     "lwpolyline", "dimension"):
            self.assertIn(kind, SUPPORTED_KINDS)

    def test_unknown_kind_is_counted_not_dropped(self):
        """#55's lesson: an unrecognized type string must never vanish silently."""
        _, report = build_dxf_from_ir(_ir([_ent("some_future_kind", {})]))
        self.assertEqual(report.skipped["some_future_kind:unrecognized_kind"], 1)

    def test_symbol_tables_are_rebuilt(self):
        ir = _ir(symbol_tables={
            "layers": [{"name": "0"}, {"name": "WALLS", "color_index": 3,
                                       "linetype": "DASHED", "lineweight": 25}],
            "linetypes": [{"name": "DASHED", "pattern_length": 0.6,
                           "dash_lengths": [0.4, -0.2], "description": "dashed"}],
            "text_styles": [{"name": "NOTES", "font_file": "romans.shx",
                             "width_factor": 0.8}],
        })
        doc, report = build_dxf_from_ir(ir)
        reloaded = _reload(doc)
        self.assertIn("WALLS", reloaded.layers)
        self.assertEqual(reloaded.layers.get("WALLS").dxf.color, 3)
        self.assertEqual(reloaded.layers.get("WALLS").dxf.linetype, "DASHED")
        self.assertIn("DASHED", reloaded.linetypes)
        self.assertEqual(reloaded.styles.get("NOTES").dxf.font, "romans.shx")
        self.assertEqual(report.added["table:layer"], 2)


class Issue60DefpointsCasingTest(unittest.TestCase):
    """#60: ezdxf pre-creates 'Defpoints'; the original's 'DEFPOINTS' must win."""

    def _uppercase_defpoints_ir(self):
        return _ir(
            [_ent("point", {"position": [1.0, 2.0, 0.0]}, layer="DEFPOINTS")],
            symbol_tables={"layers": [{"name": "0"},
                                      {"name": "DEFPOINTS", "color_index": 3}]},
        )

    def test_layer_table_keeps_the_original_casing(self):
        doc, report = build_dxf_from_ir(self._uppercase_defpoints_ir())
        reloaded = _reload(doc)
        names = [layer.dxf.name for layer in reloaded.layers]
        self.assertIn("DEFPOINTS", names)
        self.assertNotIn("Defpoints", names)
        # The record must be the IR's own, not an attribute-less stand-in: a
        # discarded-then-implicitly-recreated layer loses its color.
        self.assertEqual(reloaded.layers.get("DEFPOINTS").dxf.color, 3)
        self.assertEqual(report.added["table:layer_recased"], 1)

    def test_entity_lands_on_the_original_layer_name(self):
        doc, _ = build_dxf_from_ir(self._uppercase_defpoints_ir())
        points = list(_reload(doc).modelspace().query("POINT"))
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].dxf.layer, "DEFPOINTS")


class Issue54DimstylePruneTest(unittest.TestCase):
    """#54: case-sensitive prune deleted the dimstyle 213 dimensions referenced."""

    def _uppercase_standard_ir(self):
        return _ir(
            [_ent("dimension", {"xline1_point": [0.0, 0.0, 0.0],
                                "xline2_point": [10.0, 0.0, 0.0],
                                "dim_line_point": [5.0, 5.0, 0.0],
                                "measurement": 10.0, "rotation": 0.0},
                  layer="DIMS")],
            symbol_tables={"dim_styles": [{"name": "STANDARD",
                                           "dim_vars": {"DIMTXT": 3.75}}]},
        )

    def test_referenced_uppercase_standard_survives(self):
        doc, report = build_dxf_from_ir(self._uppercase_standard_ir())
        reloaded = _reload(doc)
        self.assertIn("STANDARD", reloaded.dimstyles)
        # ezdxf recreates a missing "Standard" on load, so table membership
        # alone cannot detect the wrongful prune -- the IR's own dim_vars can.
        self.assertEqual(reloaded.dimstyles.get("STANDARD").dxf.dimtxt, 3.75)
        self.assertEqual(report.added["table:prune_dimstyle_std"], 0)

    def test_dimension_reference_resolves_after_reload(self):
        doc, _ = build_dxf_from_ir(self._uppercase_standard_ir())
        reloaded = _reload(doc)
        dims = list(reloaded.modelspace().query("DIMENSION"))
        self.assertEqual(len(dims), 1)
        self.assertIn(dims[0].dxf.dimstyle, reloaded.dimstyles)


class Issue58ShapeFileStyleTest(unittest.TestCase):
    """#58: a shape-file STYLE record named STANDARD overwrote text style Standard."""

    def _shape_record_ir(self):
        return _ir(symbol_tables={"text_styles": [
            {"name": "Standard", "font_file": "arial.ttf", "is_shape_file": False},
            {"name": "STANDARD", "font_file": "SYMBOL", "is_shape_file": True},
            {"name": "", "font_file": "ltypeshp.shx", "is_shape_file": True},
        ]})

    def test_text_style_font_is_not_corrupted_by_a_shape_record(self):
        doc, _ = build_dxf_from_ir(self._shape_record_ir())
        self.assertEqual(_reload(doc).styles.get("Standard").dxf.font, "arial.ttf")

    def test_shape_records_are_restored_as_shx_entries(self):
        doc, report = build_dxf_from_ir(self._shape_record_ir())
        reloaded = _reload(doc)
        self.assertIsNotNone(reloaded.styles.find_shx("SYMBOL"))
        self.assertIsNotNone(reloaded.styles.find_shx("ltypeshp.shx"))
        self.assertEqual(report.added["table:shape_file"], 2)


class Issue51BlockDimensionInlineTest(unittest.TestCase):
    """#51: inlining block-internal dimensions orphans *D -> purge kills INSERTs.

    Adopted design: inline OFF by default (the *D definition is preserved and
    the DIMENSION entity points at it), with inline available as an option for
    the drawings whose DWG conversion fails with rc53.
    """

    def _ir_with_block_dimension(self):
        dim = _ent("dimension", {"xline1_point": [0.0, 0.0, 0.0],
                                 "xline2_point": [10.0, 0.0, 0.0],
                                 "dim_line_point": [5.0, 5.0, 0.0],
                                 "measurement": 10.0, "rotation": 0.0},
                   handle="D1", layer="DIMS", space="block",
                   dim_block_name="*D1")
        return _ir(
            [_ent("block_reference", {"position": [0.0, 0.0, 0.0],
                                      "block_name": "FRAME"}, handle="I1")],
            symbol_tables={"layers": [{"name": "0"}, {"name": "DIMS"}]},
            block_definitions=[
                {"name": "*D1", "def_entities": [
                    _ent("line", {"start": [0.0, 5.0, 0.0], "end": [10.0, 5.0, 0.0]},
                         handle="L1", layer="DIMS", space="block"),
                    _ent("line", {"start": [0.0, 0.0, 0.0], "end": [0.0, 5.0, 0.0]},
                         handle="L2", layer="DIMS", space="block"),
                ]},
                {"name": "FRAME", "def_entities": [dim]},
            ],
        )

    def test_default_keeps_the_dimension_and_its_anonymous_block(self):
        doc, report = build_dxf_from_ir(self._ir_with_block_dimension())
        reloaded = _reload(doc)
        self.assertIn("*D1", reloaded.blocks)
        frame = reloaded.blocks.get("FRAME")
        self.assertEqual([e.dxftype() for e in frame], ["DIMENSION"])
        self.assertEqual(frame[0].dxf.geometry, "*D1")
        self.assertEqual(report.added["dim_inlined"], 0)
        self.assertEqual(len(list(reloaded.modelspace().query("INSERT"))), 1)

    def test_inline_option_expands_the_anonymous_block_contents(self):
        doc, report = build_dxf_from_ir(self._ir_with_block_dimension(),
                                        inline_block_dims=True)
        reloaded = _reload(doc)
        frame = reloaded.blocks.get("FRAME")
        self.assertEqual([e.dxftype() for e in frame], ["LINE", "LINE"])
        self.assertEqual(report.added["dim_inlined"], 1)
        self.assertIn("*D1", reloaded.blocks)


class Issue49WipeoutLayerTest(unittest.TestCase):
    """#49: ezdxf's add_wipeout ignores dxfattribs['layer'] -> everything on '0'.

    Dominant cause of 214 of the 216 initial FAILs in the HDC 267 run
    (~140,000 misplaced WIPEOUTs), so the layer is asserted after a full DXF
    round trip: the post-creation assignment has to survive save+reload.
    """

    def _wipeout_ir(self):
        return _ir(
            [_ent("wipeout", {"origin": [10.0, 20.0, 0.0],
                              "u_vector": [30.0, 0.0, 0.0],
                              "v_vector": [0.0, 15.0, 0.0],
                              "image_size": [1.0, 1.0],
                              "clip_boundary_type": 2,
                              "clip_boundary": [[-0.5, 0.5], [0.5, 0.5],
                                                [0.5, -0.5], [-0.5, -0.5]],
                              "frame_on": True}, layer="PV-MASK")],
            symbol_tables={"layers": [{"name": "0"}, {"name": "PV-MASK"}]},
        )

    def test_wipeout_keeps_its_original_layer(self):
        doc, report = build_dxf_from_ir(self._wipeout_ir())
        wipeouts = list(_reload(doc).modelspace().query("WIPEOUT"))
        self.assertEqual(len(wipeouts), 1)
        self.assertEqual(wipeouts[0].dxf.layer, "PV-MASK")
        self.assertEqual(report.added["wipeout"], 1)

    def test_masking_area_returns_to_the_original_wcs_rectangle(self):
        """The clip boundary is image-plane 2D; the WCS mapping must be exact."""
        doc, _ = build_dxf_from_ir(self._wipeout_ir())
        wipeout = list(_reload(doc).modelspace().query("WIPEOUT"))[0]
        corners = {(round(p.x, 6), round(p.y, 6)) for p in wipeout.boundary_path_wcs()}
        self.assertEqual(corners, {(10.0, 20.0), (40.0, 20.0),
                                   (40.0, 35.0), (10.0, 35.0)})


class Issue53PeriodicSplineTest(unittest.TestCase):
    """#53: ObjectARX periodic knots (ncp+1) were dropped -> knot-less SPLINE.

    A SPLINE with control points and NO knots makes AutoCAD reject the entire
    DXF with rc53 (ezdxf's own audit passes it, which is why this went unseen).
    """

    @staticmethod
    def _ring(count=8, radius=10.0):
        import math as _math
        return [[radius * _math.cos(i * 2 * _math.pi / count),
                 radius * _math.sin(i * 2 * _math.pi / count), 0.0]
                for i in range(count)]

    def _periodic_ir(self):
        control = self._ring()
        return _ir([_ent("spline", {"degree": 3, "closed": True},
                         layer="0",
                         spline_control_points=control,
                         spline_knots=[float(i) for i in range(len(control) + 1)])])

    def test_periodic_spline_gets_a_valid_dxf_knot_vector(self):
        doc, report = build_dxf_from_ir(self._periodic_ir())
        splines = list(_reload(doc).modelspace().query("SPLINE"))
        self.assertEqual(len(splines), 1)
        spline = splines[0]
        self.assertGreater(len(spline.knots), 0)
        self.assertEqual(len(spline.knots),
                         len(spline.control_points) + spline.dxf.degree + 1)
        self.assertEqual(report.added["spline_periodic"], 1)

    def test_standard_knot_vector_is_passed_through_unchanged(self):
        control = [[0.0, 0.0, 0.0], [1.0, 2.0, 0.0], [3.0, 2.0, 0.0], [4.0, 0.0, 0.0]]
        knots = [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0]
        doc, report = build_dxf_from_ir(_ir([
            _ent("spline", {"degree": 3, "closed": False},
                 spline_control_points=control, spline_knots=knots)]))
        spline = list(_reload(doc).modelspace().query("SPLINE"))[0]
        self.assertEqual(list(spline.knots), knots)
        self.assertEqual(report.added["spline_periodic"], 0)

    def test_mismatched_knot_count_is_synthesized_never_left_empty(self):
        control = [[0.0, 0.0, 0.0], [1.0, 2.0, 0.0], [3.0, 2.0, 0.0], [4.0, 0.0, 0.0]]
        doc, report = build_dxf_from_ir(_ir([
            _ent("spline", {"degree": 3, "closed": False},
                 spline_control_points=control, spline_knots=[0.0, 1.0, 2.0])]))
        spline = list(_reload(doc).modelspace().query("SPLINE"))[0]
        self.assertEqual(len(spline.knots),
                         len(spline.control_points) + spline.dxf.degree + 1)
        self.assertEqual(report.added["spline_knots_synthesized"], 1)


class Issue56Face3dTest(unittest.TestCase):
    """#56: no face3d dispatch branch -> all 136 3DFACEs in d008 were lost."""

    def _face_ir(self):
        return _ir([_ent("face3d", {"p0": [0.0, 0.0, 30.0], "p1": [10.0, 0.0, 30.0],
                                    "p2": [10.0, 10.0, -0.0002],
                                    "p3": [0.0, 10.0, -0.0002],
                                    "edge_visibility": [True, False, True, False]},
                         layer="ROOF")],
                   symbol_tables={"layers": [{"name": "0"}, {"name": "ROOF"}]})

    def test_face3d_is_created_with_z_preserved(self):
        doc, report = build_dxf_from_ir(self._face_ir())
        faces = list(_reload(doc).modelspace().query("3DFACE"))
        self.assertEqual(len(faces), 1)
        self.assertEqual(report.added["face3d"], 1)
        self.assertAlmostEqual(faces[0].dxf.vtx0.z, 30.0)
        self.assertAlmostEqual(faces[0].dxf.vtx2.z, -0.0002)
        self.assertEqual(faces[0].dxf.layer, "ROOF")

    def test_edge_visibility_bits_survive_the_roundtrip(self):
        """set_edge_visibility writes group 70 (invisible_edges), not group 60."""
        doc, _ = build_dxf_from_ir(self._face_ir())
        face = list(_reload(doc).modelspace().query("3DFACE"))[0]
        self.assertEqual(face.dxf.invisible_edges, 2 | 8)
        self.assertEqual(face.dxf.invisible, 0)


class Issue59LeaderAndElevationTest(unittest.TestCase):
    """#59: LEADER was downgraded to POLYLINE, and LWPOLYLINE lost its Z."""

    def test_leader_stays_a_leader(self):
        doc, report = build_dxf_from_ir(_ir([
            _ent("leader", {"vertices": [[0.0, 0.0, 0.0], [5.0, 5.0, 0.0],
                                         [10.0, 5.0, 0.0]],
                            "has_arrow_head": True, "splined": False},
                 layer="0")]))
        modelspace = _reload(doc).modelspace()
        self.assertEqual(len(list(modelspace.query("LEADER"))), 1)
        self.assertEqual(len(list(modelspace.query("POLYLINE"))), 0)
        leader = list(modelspace.query("LEADER"))[0]
        self.assertEqual(leader.dxf.has_arrowhead, 1)
        self.assertEqual(leader.dxf.path_type, 0)
        self.assertEqual(report.added["leader"], 1)

    def test_splined_leader_keeps_its_spline_path_type(self):
        doc, _ = build_dxf_from_ir(_ir([
            _ent("leader", {"vertices": [[0.0, 0.0, 0.0], [5.0, 5.0, 0.0],
                                         [10.0, 5.0, 0.0]],
                            "has_arrow_head": False, "splined": True})]))
        leader = list(_reload(doc).modelspace().query("LEADER"))[0]
        self.assertEqual(leader.dxf.path_type, 1)
        self.assertEqual(leader.dxf.has_arrowhead, 0)

    def test_lwpolyline_elevation_is_recovered_from_vertex_z(self):
        """The IR leaves ``elevation`` empty and carries the Z on the vertices."""
        z = 2000000.020962
        doc, _ = build_dxf_from_ir(_ir([
            _ent("lwpolyline", {"vertices": [{"point": [0.0, 0.0, z]},
                                             {"point": [10.0, 0.0, z]},
                                             {"point": [10.0, 5.0, z]}],
                                "closed": True})]))
        lwpolyline = list(_reload(doc).modelspace().query("LWPOLYLINE"))[0]
        self.assertAlmostEqual(lwpolyline.dxf.elevation, z, places=6)

    def test_explicit_lwpolyline_elevation_is_used_as_is(self):
        doc, _ = build_dxf_from_ir(_ir([
            _ent("lwpolyline", {"elevation": -0.023448,
                                "vertices": [{"point": [0.0, 0.0, 0.0]},
                                             {"point": [10.0, 0.0, 0.0]}],
                                "closed": False})]))
        lwpolyline = list(_reload(doc).modelspace().query("LWPOLYLINE"))[0]
        self.assertAlmostEqual(lwpolyline.dxf.elevation, -0.023448)


class Issue55HatchEllipseArcTest(unittest.TestCase):
    """#55: 'ellipse_arc' boundary edges were ignored (dispatch said 'ell_arc'),
    so 288 edges vanished and took 20 whole hatches with them; and the
    major_axis/ratio convention was wrong, so any edge that DID get through
    would have come out as a unit-radius circle.

    Field names follow the extractor's own edge JSON -- see
    tests/unit/test_ir_builder.py's edge-loop shape contract.
    """

    MAJOR_RADIUS = 5000.0
    MINOR_RADIUS = 2000.0

    def _hatch_ir(self, edges, *, loop_extra=None):
        loop = {"index": 0, "loop_type": 1, "closed": True, "status": "ok",
                "edges": edges}
        loop.update(loop_extra or {})
        return _ir([_ent("hatch", {"pattern_name": "SOLID", "is_solid_fill": True,
                                   "loops": [loop]}, layer="0")])

    def _unit_axis_ellipse_edge(self):
        """The measured IR shape: unit major_axis + separate radii, radians."""
        return {"type": "ellipse_arc", "center": [0.0, 0.0],
                "major_axis": [1.0, 0.0],
                "major_radius": self.MAJOR_RADIUS,
                "minor_radius": self.MINOR_RADIUS,
                "start_angle": 0.0, "end_angle": math.pi,
                "counterclockwise": True}

    @staticmethod
    def _ellipse_edges(hatch):
        return [e for e in hatch.paths[0].edges if type(e).__name__ == "EllipseEdge"]

    def test_ellipse_arc_loop_is_not_dropped(self):
        doc, report = build_dxf_from_ir(self._hatch_ir([self._unit_axis_ellipse_edge()]))
        hatches = list(_reload(doc).modelspace().query("HATCH"))
        self.assertEqual(len(hatches), 1)
        self.assertEqual(report.added["hatch"], 1)
        self.assertEqual(report.skipped["hatch:hatch_no_boundary"], 0)

    def test_ellipse_arc_keeps_its_real_size_and_ratio(self):
        doc, _ = build_dxf_from_ir(self._hatch_ir([self._unit_axis_ellipse_edge()]))
        hatch = list(_reload(doc).modelspace().query("HATCH"))[0]
        edges = self._ellipse_edges(hatch)
        self.assertEqual(len(edges), 1)
        edge = edges[0]
        # ezdxf wants the center->major-endpoint VECTOR, not a unit direction.
        self.assertAlmostEqual(math.hypot(edge.major_axis[0], edge.major_axis[1]),
                               self.MAJOR_RADIUS, places=6)
        self.assertAlmostEqual(edge.ratio, self.MINOR_RADIUS / self.MAJOR_RADIUS,
                               places=9)
        self.assertAlmostEqual(edge.end_angle, 180.0, places=6)

    def test_full_length_major_dialect_gives_the_same_geometry(self):
        """The extractor's other edge dialect: full-length 'major' + 'ratio'."""
        doc, _ = build_dxf_from_ir(self._hatch_ir([{
            "type": "ellipse", "center": [0.0, 0.0],
            "major": [self.MAJOR_RADIUS, 0.0],
            "ratio": self.MINOR_RADIUS / self.MAJOR_RADIUS,
            "start_angle": 0.0, "end_angle": math.pi, "ccw": True}]))
        edge = self._ellipse_edges(list(_reload(doc).modelspace().query("HATCH"))[0])[0]
        self.assertAlmostEqual(math.hypot(edge.major_axis[0], edge.major_axis[1]),
                               self.MAJOR_RADIUS, places=6)
        self.assertAlmostEqual(edge.ratio, self.MINOR_RADIUS / self.MAJOR_RADIUS,
                               places=9)

    def test_unrecognized_edge_type_is_counted(self):
        """The 288-edge loss showed up only as 20 discarded hatches: never again."""
        doc, report = build_dxf_from_ir(self._hatch_ir([
            {"type": "line", "start": [0.0, 0.0], "end": [10.0, 0.0]},
            {"type": "line", "start": [10.0, 0.0], "end": [10.0, 10.0]},
            {"type": "helix_edge_from_the_future", "start": [10.0, 10.0]},
        ]))
        self.assertEqual(report.skipped["hatch_edge:helix_edge_from_the_future"], 1)
        self.assertEqual(report.added["hatch"], 1)
        self.assertEqual(len(list(_reload(doc).modelspace().query("HATCH"))), 1)

    def test_boundaryless_hatch_is_dropped_and_reported(self):
        doc, report = build_dxf_from_ir(self._hatch_ir([
            {"type": "helix_edge_from_the_future", "start": [0.0, 0.0]}]))
        self.assertEqual(len(list(_reload(doc).modelspace().query("HATCH"))), 0)
        self.assertEqual(report.skipped["hatch:hatch_no_boundary"], 1)
        self.assertEqual(report.added["hatch"], 0)

    def test_polyline_boundary_loop_still_works(self):
        doc, report = build_dxf_from_ir(_ir([_ent("hatch", {
            "pattern_name": "SOLID", "is_solid_fill": True,
            "loops": [{"index": 0, "loop_type": 3, "closed": True,
                       "vertices": [{"point": [0.0, 0.0, 0.0]},
                                    {"point": [10.0, 0.0, 0.0]},
                                    {"point": [10.0, 10.0, 0.0]}]}]})]))
        hatch = list(_reload(doc).modelspace().query("HATCH"))[0]
        self.assertEqual(len(hatch.paths[0].vertices), 3)
        self.assertTrue(hatch.paths[0].is_closed)
        self.assertEqual(report.added["hatch"], 1)


if __name__ == "__main__":
    unittest.main()
