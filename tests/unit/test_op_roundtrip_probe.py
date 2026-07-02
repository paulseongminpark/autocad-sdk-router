#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer F3 TEST -- op_roundtrip_probe.py, the op_id -> P-gate driver.

Intent (WHY):
  * "exit 3 on not-wired" is THIS module's own responsibility (resolved
    BEFORE any disk/process activity): an op_name outside
    ``patch_ops.NATIVE_WRITE_OP_MAP`` must never even attempt a staged write.
    Pinned against the REAL ``patch_ops`` module (already merged, F9) so this
    test cannot silently pass against a stale/fake registry.
  * ``expected_ir_for_op`` is the P-gate's ground truth -- it must be built
    from the op's OWN args, never from a live read (an op_name this module
    cannot honestly build ground truth for is NOT_IMPLEMENTED, not guessed).
  * ``probe_roundtrip`` is fully driven through an INJECTED fake
    ``apply_staged`` (mirrors cross_oracle.py's own established injection
    pattern for its LIVE leg) -- no accoreconsole is ever invoked by this
    suite; every degraded ``apply_staged`` envelope status (not_implemented /
    unavailable / blocked / a missing original-unchanged proof) must degrade
    truthfully rather than fake a PASS.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib
only.
"""
from __future__ import annotations

import math
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cad_op_gate  # noqa: E402
import op_roundtrip_probe as probe  # noqa: E402

IR_SCHEMA_ID = probe.IR_SCHEMA_ID


# --------------------------------------------------------------------------- #
# resolve_native_op -- exit 3 on not-wired
# --------------------------------------------------------------------------- #

class TestResolveNativeOp(unittest.TestCase):
    def test_create_line_resolves_against_real_patch_ops(self):
        import patch_ops
        self.assertEqual(probe.resolve_native_op("create_line", patch_ops_mod=patch_ops),
                        "write.entity.line")

    def test_create_circle_resolves_against_real_patch_ops(self):
        import patch_ops
        self.assertEqual(probe.resolve_native_op("create_circle", patch_ops_mod=patch_ops),
                        "write.entity.circle")

    def test_unwired_op_resolves_to_none(self):
        # create_arc was the fixture here pre-WAVE-1 TIER-1 T1; promote_op.py
        # has since wired it for real -- create_hatch remains genuinely
        # unwired at the patch_ops layer today.
        import patch_ops
        self.assertIsNone(probe.resolve_native_op("create_hatch", patch_ops_mod=patch_ops))
        self.assertNotIn("create_hatch", patch_ops.NATIVE_WRITE_OP_MAP,
                         "fixture premise: create_hatch must genuinely be unwired today")

    def test_missing_patch_ops_sibling_resolves_to_none(self):
        self.assertIsNone(probe.resolve_native_op("create_line", patch_ops_mod=object()))


# --------------------------------------------------------------------------- #
# expected_ir_for_op -- ground truth from the op's own args
# --------------------------------------------------------------------------- #

class TestExpectedIrForOp(unittest.TestCase):
    def test_create_line_builds_line_geometry(self):
        ir = probe.expected_ir_for_op("create_line", {"start": [0, 0, 0], "end": [10, 0, 0], "layer": "DIM"})
        self.assertEqual(ir["schema"], IR_SCHEMA_ID)
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "LINE")
        self.assertEqual(ent["layer"], "DIM")
        self.assertEqual(ent["geometry"], {"kind": "line", "start": [0, 0, 0], "end": [10, 0, 0]})

    def test_create_circle_builds_circle_geometry(self):
        ir = probe.expected_ir_for_op("create_circle", {"center": [1, 2, 0], "radius": 3.0, "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "CIRCLE")
        self.assertEqual(ent["geometry"], {"kind": "circle", "center": [1, 2, 0], "radius": 3.0})

    def test_default_layer_is_zero(self):
        ir = probe.expected_ir_for_op("create_line", {"start": [0, 0, 0], "end": [10, 0, 0]})
        self.assertEqual(ir["entities"][0]["layer"], "0")

    def test_create_arc_builds_arc_geometry(self):
        ir = probe.expected_ir_for_op(
            "create_arc", {"center": [1, 2, 0], "radius": 5.0,
                          "start_angle": 0.0, "end_angle": 1.5707963267948966, "layer": "DIM"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "ARC")
        self.assertEqual(ent["layer"], "DIM")
        self.assertEqual(ent["geometry"],
                         {"kind": "arc", "center": [1, 2, 0], "radius": 5.0,
                          "start_angle": 0.0, "end_angle": 1.5707963267948966})
        # no "normal" key -- collectModelSpaceGraph's AcDbArc branch never
        # emits one; including it would make a real read-back mismatch.
        self.assertNotIn("normal", ent["geometry"])

    def test_create_text_builds_text_geometry_with_height(self):
        # T3a: collectModelSpaceGraph's AcDbText branch now surfaces height
        # (AcDbText::height()), so ground truth includes it too.
        ir = probe.expected_ir_for_op(
            "create_text", {"position": [0, 0, 0], "text": "hello", "height": 2.5, "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "TEXT")
        self.assertEqual(ent["geometry"],
                         {"kind": "text", "position": [0, 0, 0], "text": "hello", "height": 2.5})

    def test_create_mtext_builds_mtext_geometry_with_height(self):
        # T3a: collectModelSpaceGraph's AcDbMText branch now surfaces height
        # (AcDbMText::textHeight()), so ground truth includes it too.
        ir = probe.expected_ir_for_op(
            "create_mtext", {"position": [1, 1, 0], "text": "note", "height": 3.0, "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "MTEXT")
        self.assertEqual(ent["geometry"],
                         {"kind": "mtext", "position": [1, 1, 0], "text": "note", "height": 3.0})

    def test_create_polyline_builds_vertices_with_bulge_and_closed(self):
        # T3a: collectModelSpaceGraph's AcDbPolyline branch now calls
        # getBulgeAt()/isClosed() too, so ground truth includes both.
        ir = probe.expected_ir_for_op(
            "create_polyline",
            {"points": [{"x": 0, "y": 0, "bulge": 0.5}, {"x": 10, "y": 0, "bulge": 0.0}],
             "closed": 1, "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "LWPOLYLINE")
        self.assertEqual(ent["geometry"],
                         {"kind": "lwpolyline",
                          "vertices": [{"point": [0, 0, 0.0], "bulge": 0.5},
                                      {"point": [10, 0, 0.0], "bulge": 0.0}],
                          "closed": True})

    def test_create_ellipse_builds_ellipse_geometry(self):
        # T3a: collectModelSpaceGraph grew an AcDbEllipse branch, so
        # create_ellipse is now certifiable -- ground truth is a direct
        # pass-through of every ctor arg, same pattern as create_arc.
        ir = probe.expected_ir_for_op(
            "create_ellipse",
            {"center": [1, 2, 0], "normal": [0, 0, 1], "major_axis": [3, 0, 0],
             "radius_ratio": 0.5, "start_angle": 0.0, "end_angle": 6.283185307179586,
             "layer": "DIM"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "ELLIPSE")
        self.assertEqual(ent["layer"], "DIM")
        self.assertEqual(ent["geometry"],
                         {"kind": "ellipse", "center": [1, 2, 0], "normal": [0, 0, 1],
                          "major_axis": [3, 0, 0], "radius_ratio": 0.5,
                          "start_angle": 0.0, "end_angle": 6.283185307179586})

    def test_create_dimension_builds_dimension_geometry(self):
        # T3a: collectModelSpaceGraph grew an AcDbRotatedDimension branch, so
        # create_dimension is now certifiable. "measurement" is independently
        # computed (projection of xline1->xline2 onto the rotation direction),
        # not echoed from args -- rotation=0 makes this a pure X-distance so
        # the expected value is unambiguous (100.0). "dim_line_point" is ALSO
        # not echoed: live-verified (2026-07-02 T3a re-cert) that AutoCAD
        # keeps only the perpendicular offset of the input point (here 20,
        # the Y delta) and re-anchors it at xLine2Point -- (50, 20, 0) in ->
        # (100, 20, 0) stored, not (50, 20, 0) (see
        # _rotated_dimension_line_point's docstring for the live evidence).
        ir = probe.expected_ir_for_op(
            "create_dimension",
            {"xline1": [0, 0, 0], "xline2": [100, 0, 0], "dim_line": [50, 20, 0],
             "rotation": 0.0, "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "DIMENSION")
        self.assertEqual(ent["geometry"],
                         {"kind": "dimension", "xline1_point": [0, 0, 0],
                          "xline2_point": [100, 0, 0], "dim_line_point": [100.0, 20.0, 0],
                          "rotation": 0.0, "measurement": 100.0})
        # dim_block_handle/dim_block_name are NEVER asserted here (see
        # _expect_create_dimension's docstring comment): a live AutoCAD
        # anonymous-block counter, not derivable from args alone.
        self.assertNotIn("dim_block_handle", ent["geometry"])
        self.assertNotIn("dim_block_name", ent["geometry"])

    def test_create_dimension_aligned_builds_dimension_geometry(self):
        # T3a-batch2: collectModelSpaceGraph grew an AcDbAlignedDimension
        # branch. dim_line_point/measurement are NOT ctor-arg echoes -- an
        # aligned dimension re-anchors dim_line_point exactly like a rotated
        # dimension does (T3a), with the xLine1->xLine2 baseline's own angle
        # standing in for "rotation" (live-verified 2026-07-02 T3a-batch2
        # re-cert). xline1=(0,0,0) xline2=(60,80,0) (baseline angle
        # atan2(80,60), length 100 -- a scaled 3-4-5 triangle) dim_line=
        # (20,60,0) -> stored dim_line_point (44.0, 92.0, 0.0), measurement
        # 100.0 (the straight-line xline1->xline2 distance).
        ir = probe.expected_ir_for_op(
            "create_dimension_aligned",
            {"xline1": [0, 0, 0], "xline2": [60, 80, 0], "dim_line": [20, 60, 0], "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "DIMENSION")
        geom = ent["geometry"]
        self.assertEqual(geom["kind"], "dimension")
        self.assertEqual(geom["xline1_point"], [0, 0, 0])
        self.assertEqual(geom["xline2_point"], [60, 80, 0])
        self.assertAlmostEqual(geom["dim_line_point"][0], 44.0)
        self.assertAlmostEqual(geom["dim_line_point"][1], 92.0)
        self.assertAlmostEqual(geom["dim_line_point"][2], 0.0)
        self.assertAlmostEqual(geom["measurement"], 100.0)
        self.assertNotIn("rotation", geom)
        self.assertNotIn("dim_block_handle", geom)
        self.assertNotIn("dim_block_name", geom)

    def test_create_dimension_radial_builds_dimension_geometry(self):
        # T3a-batch2: collectModelSpaceGraph grew an AcDbRadialDimension
        # branch. center/chord_point are direct ctor-arg echoes (no
        # rotation-style re-anchoring degree of freedom applies here,
        # live-verified 2026-07-02 T3a-batch2 re-cert); measurement is the
        # independently-computed center->chord_point distance (the radius).
        # leader_length is deliberately NOT asserted -- live-discovered to be
        # AutoCAD's own recomputed value (see the function's docstring).
        ir = probe.expected_ir_for_op(
            "create_dimension_radial",
            {"center": [0, 0, 0], "chord_point": [10, 0, 0], "leader_length": 5.0, "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "DIMENSION")
        self.assertEqual(ent["geometry"], {
            "kind": "dimension", "center": [0, 0, 0], "chord_point": [10, 0, 0],
            "measurement": 10.0,
        })
        self.assertNotIn("leader_length", ent["geometry"])

    def test_create_dimension_diametric_builds_dimension_geometry(self):
        # T3a-batch2: collectModelSpaceGraph grew an AcDbDiametricDimension
        # branch. chord_point/far_chord_point are direct ctor-arg echoes
        # (live-verified 2026-07-02 T3a-batch2 re-cert); measurement is the
        # independently-computed chord_point<->far_chord_point distance (the
        # diameter). leader_length is deliberately NOT asserted, same reason
        # as the radial case above.
        ir = probe.expected_ir_for_op(
            "create_dimension_diametric",
            {"chord_point": [-10, 0, 0], "far_chord_point": [10, 0, 0],
             "leader_length": 5.0, "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "DIMENSION")
        self.assertEqual(ent["geometry"], {
            "kind": "dimension", "chord_point": [-10, 0, 0], "far_chord_point": [10, 0, 0],
            "measurement": 20.0,
        })
        self.assertNotIn("leader_length", ent["geometry"])

    def test_create_dimension_radiallarge_builds_dimension_geometry(self):
        # w3-radl: collectModelSpaceGraph grew an AcDbRadialDimensionLarge
        # branch. center/chord_point carry the SAME semantic AcDbRadialDimension
        # already uses, so measurement is the identical independently-computed
        # center->chord_point distance (the radius). UNLIKE AcDbArcDimension/
        # AcDb2LineAngularDimension/AcDb3PointAngularDimension's own
        # placement-only arc_point, override_center/jog_point/jog_angle are
        # asserted as direct, verbatim ctor-arg echoes -- live-verified
        # (2026-07-02 w3-radl re-cert, 3 real accoreconsole roundtrips against
        # tests/fixtures/native_sample.dwg, one with a non-zero Z) that
        # AutoCAD does not re-anchor any of them.
        ir = probe.expected_ir_for_op(
            "create_dimension_radiallarge",
            {"center": [0, 0, 0], "chord_point": [50, 0, 0],
             "override_center": [0, -80, 0], "jog_point": [25, -40, 0],
             "jog_angle": 0.785398163397448, "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "DIMENSION")
        self.assertEqual(ent["geometry"], {
            "kind": "dimension", "center": [0, 0, 0], "chord_point": [50, 0, 0],
            "override_center": [0, -80, 0], "jog_point": [25, -40, 0],
            "jog_angle": 0.785398163397448, "measurement": 50.0,
        })

    def test_create_dimension_radiallarge_jog_angle_defaults_to_45deg(self):
        # write.entity.dim.radiallarge's own handler default (m08h_handlers.inc:
        # "double jogAngle = 0.785398163397448; jsonFindNumber(job, "jog_angle",
        # jogAngle);") -- mirrored here so an omitted jog_angle arg still
        # asserts the SAME value the native ctor actually receives.
        ir = probe.expected_ir_for_op(
            "create_dimension_radiallarge",
            {"center": [0, 0, 0], "chord_point": [50, 0, 0],
             "override_center": [0, -80, 0], "jog_point": [25, -40, 0], "layer": "0"})
        geom = ir["entities"][0]["geometry"]
        self.assertAlmostEqual(geom["jog_angle"], 0.785398163397448, places=12)

    def test_create_spline_builds_spline_geometry(self):
        # T3a-batch2: collectModelSpaceGraph grew an AcDbSpline branch.
        # write.entity.spline (m08g_handlers.inc) always builds a fit-point
        # spline (order defaults to 4.0, never periodic/closed), so degree
        # (=order-1) / closed (=False) / fit_points (the literal "points" arg)
        # are direct, args-derivable ground truth -- live-verified
        # (2026-07-02 T3a-batch2 re-cert) diff=0 for exactly these three.
        ir = probe.expected_ir_for_op(
            "create_spline",
            {"points": [[0, 0, 0], [10, 5, 0], [20, 0, 0], [30, 8, 0]], "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "SPLINE")
        self.assertEqual(ent["geometry"], {
            "kind": "spline", "degree": 3, "closed": False,
            "fit_points": [[0, 0, 0], [10, 5, 0], [20, 0, 0], [30, 8, 0]],
        })
        # spline_control_points/spline_knots are NEVER asserted here (see
        # _expect_create_spline's docstring): AutoCAD's own fit-to-NURBS
        # conversion result, not derivable from args alone.
        self.assertNotIn("spline_control_points", ent["geometry"])
        self.assertNotIn("spline_knots", ent["geometry"])

    def test_create_spline_honors_explicit_order(self):
        ir = probe.expected_ir_for_op(
            "create_spline", {"points": [[0, 0, 0], [10, 0, 0]], "order": 2, "layer": "0"})
        self.assertEqual(ir["entities"][0]["geometry"]["degree"], 1)

    def test_create_dimension_ordinate_builds_dimension_geometry(self):
        # T3a-batch3: collectModelSpaceGraph grew an AcDbOrdinateDimension
        # branch. defining_point/leader_end_point/use_x_axis are direct
        # ctor-arg echoes (no re-anchoring degree of freedom applies here,
        # unlike aligned/rotated's dim_line_point); measurement is the
        # independently-computed defining_point.x (use_x_axis=True) -- all
        # live-verified (2026-07-02 T3a-batch3 re-cert). origin is
        # deliberately NOT asserted -- see _expect_create_dimension_ordinate's
        # docstring.
        ir = probe.expected_ir_for_op(
            "create_dimension_ordinate",
            {"defining_point": [10, 5, 0], "leader_end_point": [10, 15, 0], "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "DIMENSION")
        self.assertEqual(ent["geometry"], {
            "kind": "dimension", "defining_point": [10, 5, 0],
            "leader_end_point": [10, 15, 0], "use_x_axis": True, "measurement": 10,
        })
        self.assertNotIn("origin", ent["geometry"])

    def test_create_dimension_ordinate_honors_explicit_use_x_axis(self):
        # use_x_axis=False (live-verified 2026-07-02 T3a-batch3 re-cert):
        # measurement becomes defining_point.y instead of .x.
        ir = probe.expected_ir_for_op(
            "create_dimension_ordinate",
            {"defining_point": [10, 5, 0], "leader_end_point": [0, 15, 0],
             "use_x_axis": 0, "layer": "0"})
        geom = ir["entities"][0]["geometry"]
        self.assertEqual(geom["use_x_axis"], False)
        self.assertEqual(geom["measurement"], 5)

    def test_create_dimension_arc_builds_dimension_geometry(self):
        # w3-dimarc: collectModelSpaceGraph grew an AcDbArcDimension branch.
        # center/xline1_point/xline2_point are direct ctor-arg echoes.
        # arc_point is NOT a verbatim echo -- live-verified (2026-07-02
        # w3-dimarc re-cert, 3 real accoreconsole roundtrips) that AutoCAD
        # discards the input arcPoint's own position and re-places it at
        # exactly 1/3 of the xline1->xline2 angular span (same radius as
        # xline1 from center); measurement is the independently-computed arc
        # length (radius * angular span). Here center=(0,0,0),
        # xline1=(50,0,0) (angle 0), xline2=(0,50,0) (angle 90 deg), input
        # arc_point at 45 deg (irrelevant to the result beyond picking the
        # CCW side) -> stored arc_point at 90/3=30 deg, measurement=50*pi/2.
        ir = probe.expected_ir_for_op(
            "create_dimension_arc",
            {"center": [0, 0, 0], "xline1": [50, 0, 0], "xline2": [0, 50, 0],
             "arc_point": [35.35533905932738, 35.35533905932738, 0], "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "DIMENSION")
        self.assertEqual(ent["geometry"], {
            "kind": "dimension", "center": [0, 0, 0],
            "xline1_point": [50, 0, 0], "xline2_point": [0, 50, 0],
            "arc_point": [50 * math.cos(math.pi / 6), 50 * math.sin(math.pi / 6), 0.0],
            "measurement": 50 * math.pi / 2,
        })

    def test_create_dimension_angular2line_builds_dimension_geometry(self):
        # w3-ang2: collectModelSpaceGraph grew an AcDb2LineAngularDimension
        # branch. xline1_start/xline1_end/xline2_start/xline2_end are direct
        # ctor-arg echoes. arc_point is NOT a verbatim echo -- live-verified
        # (2026-07-02 w3-ang2 re-cert, 4 real accoreconsole roundtrips, 2
        # different apex points) that AutoCAD re-anchors it to exactly 1/3 of
        # whichever of the 2 lines' 4 apex-sectors the input arc_point's own
        # angle selects (same radius as the input arc_point's own distance
        # from the apex); measurement is the independently-computed selected
        # sector's angular width. Here xline1=(10,0,0)->(30,0,0) (angle 0
        # from the implicit apex at (0,0,0)), xline2=(0,10,0)->(0,30,0)
        # (angle 90 deg), input arc_point at 60 deg / radius 40 (irrelevant
        # to the result beyond picking the [0,90] sector) -> stored arc_point
        # at 90/3=30 deg / radius 40, measurement=pi/2.
        ir = probe.expected_ir_for_op(
            "create_dimension_angular2line",
            {"xline1_start": [10, 0, 0], "xline1_end": [30, 0, 0],
             "xline2_start": [0, 10, 0], "xline2_end": [0, 30, 0],
             "arc_point": [40 * math.cos(math.pi / 3), 40 * math.sin(math.pi / 3), 0], "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "DIMENSION")
        self.assertEqual(ent["geometry"], {
            "kind": "dimension",
            "xline1_start": [10, 0, 0], "xline1_end": [30, 0, 0],
            "xline2_start": [0, 10, 0], "xline2_end": [0, 30, 0],
            "arc_point": [40 * math.cos(math.pi / 6), 40 * math.sin(math.pi / 6), 0.0],
            "measurement": math.pi / 2,
        })

    def test_create_dimension_angular3pt_builds_dimension_geometry(self):
        # w3-ang3: collectModelSpaceGraph grew an AcDb3PointAngularDimension
        # branch. center/xline1_point/xline2_point are direct ctor-arg echoes
        # (identical ctor shape to create_dimension_arc). arc_point is NOT a
        # verbatim echo -- live-verified (2026-07-02 w3-ang3 re-cert, 3 real
        # accoreconsole roundtrips) that AutoCAD re-anchors its ANGLE the same
        # way create_dimension_arc's arc_point does (1/3 of the xline1->
        # xline2 span) but preserves its RADIUS from the INPUT arc_point's
        # own distance to center -- NOT xline1's distance (see the next test,
        # which uses a different xline-radius vs arc_point-radius to actually
        # distinguish the two rules; this case alone can't, since the input
        # arc_point sits at radius 50, same as xline1). measurement is the
        # plain ANGLE (pi/2), NOT an arc length (unlike create_dimension_arc's
        # 50*pi/2 for these identical points).
        ir = probe.expected_ir_for_op(
            "create_dimension_angular3pt",
            {"center": [0, 0, 0], "xline1": [50, 0, 0], "xline2": [0, 50, 0],
             "arc_point": [35.35533905932738, 35.35533905932738, 0], "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "DIMENSION")
        self.assertEqual(ent["geometry"], {
            "kind": "dimension", "center": [0, 0, 0],
            "xline1_point": [50, 0, 0], "xline2_point": [0, 50, 0],
            "arc_point": [50 * math.cos(math.pi / 6), 50 * math.sin(math.pi / 6), 0.0],
            "measurement": math.pi / 2,
        })

    def test_create_dimension_angular3pt_arc_point_radius_is_input_not_xline1(self):
        # w3-ang3 LIVE DISCOVERY: a first attempt assumed arc_point's
        # re-anchoring was IDENTICAL to create_dimension_arc's (same radius as
        # xLine1Point) since the two ops share an identical ctor-arg shape --
        # that passed the test above (input arc_point radius == xline1
        # radius there, 50 both, by construction) but FAILED live once the
        # input arc_point was given a DIFFERENT radius than xline1/xline2
        # (2 of 3 2026-07-02 w3-ang3 re-cert roundtrips): the stored arc_point
        # keeps the INPUT arc_point's OWN radius from center, the same rule
        # create_dimension_angular2line uses for its own apex, NOT xline1's
        # radius. Here xline1/xline2 sit at radius 30 from center=(10,-5,0)
        # (angles 20/140 deg), the input arc_point sits at radius 18 (angle 80
        # deg, inside the [20,140] span) -- live-verified the stored
        # arc_point comes back at radius 18 (NOT 30), angle 20+120/3=60 deg.
        cx, cy, r, arc_r = 10.0, -5.0, 30.0, 18.0
        a1, a2, ain = math.radians(20), math.radians(140), math.radians(80)
        xline1 = [cx + r * math.cos(a1), cy + r * math.sin(a1), 0.0]
        xline2 = [cx + r * math.cos(a2), cy + r * math.sin(a2), 0.0]
        arc_point_arg = [cx + arc_r * math.cos(ain), cy + arc_r * math.sin(ain), 0.0]
        ir = probe.expected_ir_for_op(
            "create_dimension_angular3pt",
            {"center": [cx, cy, 0.0], "xline1": xline1, "xline2": xline2,
             "arc_point": arc_point_arg, "layer": "0"})
        geom = ir["entities"][0]["geometry"]
        third_angle = math.radians(20 + 120 / 3.0)
        self.assertEqual(geom["arc_point"],
                          [cx + arc_r * math.cos(third_angle), cy + arc_r * math.sin(third_angle), 0.0])
        self.assertAlmostEqual(geom["measurement"], math.radians(120), places=12)

    def test_create_leader_builds_leader_geometry(self):
        # T3a-batch3: collectModelSpaceGraph grew an AcDbLeader branch.
        # vertices are direct, args-derivable echoes (appendVertex per point,
        # no transform); has_arrow_head/splined are deterministic constants
        # for this op (enableArrowHead()/setToStraightLeader() are always
        # called) -- live-verified (2026-07-02 T3a-batch3 re-cert) diff=0.
        ir = probe.expected_ir_for_op(
            "create_leader",
            {"vertices": [[0, 0, 0], [10, 10, 0], [20, 10, 0]], "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "LEADER")
        self.assertEqual(ent["geometry"], {
            "kind": "leader",
            "vertices": [{"point": [0, 0, 0]}, {"point": [10, 10, 0]}, {"point": [20, 10, 0]}],
            "has_arrow_head": True, "splined": False,
        })

    def test_create_leader_falls_back_to_points_key(self):
        # write.entity.leader reads "vertices" first, falling back to "points"
        # only when "vertices" yields <2 points -- mirror that fallback here.
        ir = probe.expected_ir_for_op(
            "create_leader", {"points": [[1, 1, 0], [5, 5, 0]], "layer": "0"})
        self.assertEqual(ir["entities"][0]["geometry"]["vertices"],
                         [{"point": [1, 1, 0]}, {"point": [5, 5, 0]}])

    def test_create_mleader_builds_leader_geometry(self):
        # w3-mleader: collectModelSpaceGraph grew an AcDbMLeader branch.
        # vertices are direct, args-derivable echoes (addFirstVertex once +
        # addLastVertex per remaining point, no transform -- same shape as
        # create_leader's appendVertex loop); text/height are direct ctor-arg
        # echoes too (setMText/setTextHeight) -- live-verified (2026-07-02
        # w3-mleader re-cert, 3 real accoreconsole roundtrips, 2/3/4-vertex
        # cases) diff=0 for all four fields, no write bug (unlike create_
        # mline's own appendSeg bug -- create_mleader's addLeaderLine/
        # addFirstVertex/addLastVertex chain DOES check ErrorStatus at every
        # step).
        ir = probe.expected_ir_for_op(
            "create_mleader",
            {"vertices": [[0, 0, 0], [15, 10, 0], [30, 0, 0]],
             "text": "Multi Vertex", "height": 3.0, "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "MULTILEADER")
        self.assertEqual(ent["geometry"], {
            "kind": "leader",
            "vertices": [{"point": [0, 0, 0]}, {"point": [15, 10, 0]}, {"point": [30, 0, 0]}],
            "text": "Multi Vertex", "height": 3.0,
        })

    def test_create_mleader_falls_back_to_points_key(self):
        # write.entity.mleader reads "vertices" first, falling back to
        # "points" only when "vertices" yields <2 points -- same fallback
        # create_leader uses.
        ir = probe.expected_ir_for_op(
            "create_mleader",
            {"points": [[1, 1, 0], [5, 5, 0]], "text": "Via points", "height": 2.5, "layer": "0"})
        self.assertEqual(ir["entities"][0]["geometry"]["vertices"],
                         [{"point": [1, 1, 0]}, {"point": [5, 5, 0]}])

    def test_create_blockref_builds_block_reference_geometry(self):
        # w3-insert: collectModelSpaceGraph's AcDbBlockReference branch
        # pre-dates this op's patch_ops wiring (unlike every op above); the
        # write handler's own gap was scale/rotation never being applied --
        # fixed alongside this wiring (m08g_handlers.inc), so all four fields
        # are direct, args-derivable echoes: position (ctor arg), block_name
        # (a block-table NAME LOOKUP the write handler resolves, then the
        # read branch resolves back via blockTableRecord()->getName() -- so
        # it round-trips as long as the name is real), scale (setScaleFactors)
        # and rotation (setRotation) both live-verified 2026-07-02 w3-insert
        # cert against a real accoreconsole roundtrip.
        ir = probe.expected_ir_for_op(
            "create_blockref",
            {"block_name": "AGENT_TEST_BLOCK",
             "position": {"x": 10.0, "y": 20.0, "z": 0.0},
             "scale": {"x": 2.0, "y": 3.0, "z": 1.0},
             "rotation": 0.5, "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "INSERT")
        self.assertEqual(ent["geometry"], {
            "kind": "block_reference",
            "position": [10.0, 20.0, 0.0],
            "scale": [2.0, 3.0, 1.0],
            "rotation": 0.5,
            "block_name": "AGENT_TEST_BLOCK",
        })

    def test_create_blockref_scale_and_rotation_default_when_omitted(self):
        # write.entity.blockref's own handler defaults (m08g_handlers.inc:
        # "m08gPoint(job, "scale", 1.0, 1.0, 1.0, scalePt)" / "double rotation
        # = 0.0") -- mirrored here so an omitted scale/rotation still asserts
        # the SAME AcDbBlockReference ctor default the native handler applies.
        ir = probe.expected_ir_for_op(
            "create_blockref",
            {"block_name": "AGENT_TEST_BLOCK",
             "position": {"x": 0.0, "y": 0.0, "z": 0.0}, "layer": "0"})
        geom = ir["entities"][0]["geometry"]
        self.assertEqual(geom["scale"], [1.0, 1.0, 1.0])
        self.assertEqual(geom["rotation"], 0.0)

    def test_create_polyline2d_builds_lwpolyline_geometry(self):
        # w3-poly2d: write.entity.polyline2d is an ALIAS for write.entity.
        # polyline (m08g_handlers.inc) -- it builds a real AcDbPolyline
        # (LWPOLYLINE), NOT a true legacy AcDb2dPolyline, despite the op's
        # own name. Ground truth is therefore IDENTICAL to
        # _expect_create_polyline's own (vertices/bulge/closed all direct,
        # args-derivable echoes) -- live-verified (2026-07-02 w3-poly2d
        # re-cert) diff=0, dxf_name reads back "LWPOLYLINE".
        ir = probe.expected_ir_for_op(
            "create_polyline2d",
            {"points": [{"x": 0, "y": 0, "bulge": 0}, {"x": 10, "y": 0, "bulge": 0.5},
                        {"x": 10, "y": 10, "bulge": 0}],
             "closed": 1, "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "LWPOLYLINE")
        self.assertEqual(ent["geometry"], {
            "kind": "lwpolyline",
            "vertices": [{"point": [0, 0, 0.0], "bulge": 0},
                        {"point": [10, 0, 0.0], "bulge": 0.5},
                        {"point": [10, 10, 0.0], "bulge": 0}],
            "closed": True,
        })

    def test_create_polyline3d_builds_polyline_geometry(self):
        # w3-poly3d: write.entity.polyline3d builds a genuine AcDb3dPolyline
        # (appendVertex per point, no transform) -- vertices are direct,
        # args-derivable echoes, plain [x,y,z] shape (no bulge, unlike
        # LWPOLYLINE). "closed" is a deterministic constant, always False --
        # the handler has no setClosed() call at all, so even though this
        # fixture passes closed=1, ground truth (and the live re-cert) both
        # show it discarded.
        ir = probe.expected_ir_for_op(
            "create_polyline3d",
            {"points": [{"x": 0, "y": 0, "z": 0}, {"x": 10, "y": 0, "z": 5},
                        {"x": 10, "y": 10, "z": 8}],
             "closed": 1, "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "POLYLINE")
        self.assertEqual(ent["geometry"], {
            "kind": "polyline",
            "vertices": [{"point": [0, 0, 0]}, {"point": [10, 0, 5]}, {"point": [10, 10, 8]}],
            "closed": False,
        })

    def test_create_polygonmesh_builds_polygon_mesh_geometry(self):
        # w3-pmesh: write.entity.polygonmesh builds a genuine AcDbPolygonMesh
        # via its one-shot ctor (mSize/nSize/verts, mClosed/nClosed HARDCODED
        # to Adesk::kFalse) -- m_size/n_size and the flattened points array are
        # direct, args-derivable echoes, plain [x,y,z] vertex shape (no bulge,
        # same shape create_polyline3d/create_mleader already use).
        # m_closed/n_closed are deterministic constants, always False -- the
        # handler never reads either field from args at all (live-verified
        # 2026-07-02 w3-pmesh re-cert).
        ir = probe.expected_ir_for_op(
            "create_polygonmesh",
            {"m_size": 2, "n_size": 3,
             "points": [{"x": 0, "y": 0, "z": 0}, {"x": 1, "y": 0, "z": 0}, {"x": 2, "y": 0, "z": 0},
                        {"x": 0, "y": 1, "z": 5}, {"x": 1, "y": 1, "z": 5}, {"x": 2, "y": 1, "z": 5}],
             "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "POLYLINE")
        self.assertEqual(ent["geometry"], {
            "kind": "polygon_mesh",
            "m_size": 2, "n_size": 3,
            "m_closed": False, "n_closed": False,
            "vertices": [{"point": [0, 0, 0]}, {"point": [1, 0, 0]}, {"point": [2, 0, 0]},
                        {"point": [0, 1, 5]}, {"point": [1, 1, 5]}, {"point": [2, 1, 5]}],
        })

    def test_create_polyfacemesh_builds_poly_face_mesh_geometry(self):
        # w3-pfmesh: write.entity.polyfacemesh builds a genuine AcDbPolyFace
        # Mesh: appendVertex() once per "points" entry (plain [x,y,z], no
        # bulge, same vertex shape create_polygonmesh already uses) THEN
        # appendFaceRecord() exactly ONCE with vertex indices HARDCODED to
        # {1,2,3,4} for this 4-vertex quad (n>=4 branch) -- the handler never
        # reads a "faces" field from args at all (live-verified 2026-07-02
        # w3-pfmesh re-cert).
        ir = probe.expected_ir_for_op(
            "create_polyfacemesh",
            {"points": [{"x": 0, "y": 0, "z": 0}, {"x": 10, "y": 0, "z": 0},
                        {"x": 10, "y": 10, "z": 0}, {"x": 0, "y": 10, "z": 0}],
             "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "POLYLINE")
        self.assertEqual(ent["geometry"], {
            "kind": "poly_face_mesh",
            "vertices": [{"point": [0, 0, 0]}, {"point": [10, 0, 0]},
                        {"point": [10, 10, 0]}, {"point": [0, 10, 0]}],
            "faces": [[1, 2, 3, 4]],
        })

    def test_create_mline_builds_mline_geometry(self):
        # w3-wbug: collectModelSpaceGraph grew an AcDbMline branch alongside the
        # write.entity.mline native bugfix (appendSeg's ErrorStatus was never
        # checked before; a silently-failing build reported success with a
        # geometrically-empty MLINE -- see m08g_handlers.inc). vertices are
        # direct, args-derivable echoes (appendSeg per point, no transform);
        # "closed" defaults False when absent -- live-verified (2026-07-02
        # w3-wbug re-cert) diff=0.
        ir = probe.expected_ir_for_op(
            "create_mline",
            {"points": [[0, 0, 0], [10, 0, 0], [10, 10, 0]], "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "MLINE")
        self.assertEqual(ent["geometry"], {
            "kind": "mline",
            "vertices": [{"point": [0, 0, 0]}, {"point": [10, 0, 0]}, {"point": [10, 10, 0]}],
            "closed": False,
        })

    def test_create_mline_falls_back_to_vertices_key(self):
        # write.entity.mline reads "points" first, falling back to "vertices"
        # only when "points" yields <2 points -- the OPPOSITE precedence from
        # write.entity.leader's vertices-first order; mirror that here.
        ir = probe.expected_ir_for_op(
            "create_mline", {"vertices": [[1, 1, 0], [5, 5, 0]], "layer": "0"})
        self.assertEqual(ir["entities"][0]["geometry"]["vertices"],
                         [{"point": [1, 1, 0]}, {"point": [5, 5, 0]}])

    def test_create_mline_honors_explicit_closed(self):
        ir = probe.expected_ir_for_op(
            "create_mline",
            {"points": [[0, 0, 0], [10, 0, 0], [10, 10, 0]], "closed": 1, "layer": "0"})
        self.assertEqual(ir["entities"][0]["geometry"]["closed"], True)

    def test_unbuildable_op_raises_not_implemented_error(self):
        # create_arc/create_ellipse were the fixtures here pre-T3a; this
        # module has since grown ground-truth builders for both.
        # create_mpolygon remains genuinely unbuildable (its live create
        # itself fails, errorstatus=409 -- not a reader gap at all).
        with self.assertRaises(NotImplementedError):
            probe.expected_ir_for_op("create_mpolygon", {})

    def test_mpolygon_xdata_remain_unbuildable(self):
        # create_mpolygon: live create fails (errorstatus=409). set_entity_
        # xdata: not a geometry op at all. Both are wired natively
        # (patch_ops.NATIVE_WRITE_OP_MAP) but neither has a ground-truth
        # builder here.
        for op_name in ("create_mpolygon", "set_entity_xdata"):
            with self.assertRaises(NotImplementedError):
                probe.expected_ir_for_op(op_name, {})


# --------------------------------------------------------------------------- #
# added_entities_ir -- resolves the diff's added-handle set back to FULL records
# --------------------------------------------------------------------------- #

class TestAddedEntitiesIr(unittest.TestCase):
    def test_resolves_full_entity_not_just_summary_fields(self):
        pre_ir = {"schema": IR_SCHEMA_ID, "entities": []}
        new_entity = {"handle": "9F1", "dxf_name": "LINE", "layer": "DIM",
                     "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [10.0, 0.0, 0.0]}}
        post_ir = {"schema": IR_SCHEMA_ID, "entities": [new_entity]}
        actual = probe.added_entities_ir(pre_ir, post_ir)
        self.assertEqual(actual["entities"], [new_entity])

    def test_unchanged_entities_are_excluded(self):
        shared = {"handle": "1A", "dxf_name": "LINE", "layer": "0",
                 "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [1.0, 0.0, 0.0]}}
        new_entity = {"handle": "1B", "dxf_name": "CIRCLE", "layer": "0",
                     "geometry": {"kind": "circle", "center": [0.0, 0.0, 0.0], "radius": 1.0}}
        pre_ir = {"schema": IR_SCHEMA_ID, "entities": [dict(shared)]}
        post_ir = {"schema": IR_SCHEMA_ID, "entities": [dict(shared), new_entity]}
        actual = probe.added_entities_ir(pre_ir, post_ir)
        self.assertEqual([e["handle"] for e in actual["entities"]], ["1B"])


# --------------------------------------------------------------------------- #
# probe_roundtrip -- the full driver, apply_staged injected (no live runtime)
# --------------------------------------------------------------------------- #

def _fake_apply_staged(post_entity, *, status="ok", reason=None, original_unchanged=True,
                      pre_entities=None):
    def _fn(patch, dwg_path, out_dir):
        pre_ir = {"schema": IR_SCHEMA_ID, "entities": list(pre_entities or [])}
        post_ir = {"schema": IR_SCHEMA_ID, "entities": list(pre_entities or []) + [dict(post_entity)]}
        envelope = {"status": status}
        if reason is not None:
            envelope["reason"] = reason
        if status == "ok":
            envelope["original_unchanged"] = {"unchanged": original_unchanged}
            # top-level, mirroring the REAL patch_engine.apply_staged envelope
            # (_result_envelope(..., extra=...) does env.update(extra) -- there
            # is no nested "extra" key in the real contract).
            envelope["pre_ir"] = pre_ir
            envelope["post_ir"] = post_ir
        return envelope
    return _fn


class TestProbeRoundtrip(unittest.TestCase):
    def test_not_wired_op_is_exit_3_before_any_apply_staged_call(self):
        # create_arc was the fixture here pre-wfix-allowlist; it is natively
        # wired AND has a ground-truth builder now. create_hatch remains
        # genuinely unwired at the patch_ops layer (see TestResolveNativeOp).
        def _must_not_be_called(patch, dwg_path, out_dir):
            raise AssertionError("apply_staged must never be called for an unwired op_name")
        result = probe.probe_roundtrip("create_hatch", {}, "fake.dwg", "fake_out",
                                       apply_staged=_must_not_be_called)
        self.assertEqual(result["status"], cad_op_gate.STATUS_NOT_IMPLEMENTED)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_NOT_IMPLEMENTED)

    def test_matching_roundtrip_is_exit_0(self):
        entity = {"handle": "9F1", "dxf_name": "LINE", "layer": "DIM",
                  "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [100.0, 0.0, 0.0]}}
        result = probe.probe_roundtrip(
            "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"},
            "fake.dwg", "fake_out", apply_staged=_fake_apply_staged(entity))
        self.assertEqual(result["status"], cad_op_gate.STATUS_OK)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)
        self.assertEqual(result["native_op"], "write.entity.line")

    def test_matching_arc_roundtrip_is_exit_0(self):
        # end-to-end wiring for one of the newly-added T1 ground-truth
        # builders (create_arc), mirroring test_matching_roundtrip_is_exit_0.
        entity = {"handle": "9F2", "dxf_name": "ARC", "layer": "0",
                  "geometry": {"kind": "arc", "center": [5.0, 5.0, 0.0], "radius": 2.5,
                              "start_angle": 0.0, "end_angle": 3.14159265358979}}
        result = probe.probe_roundtrip(
            "create_arc",
            {"center": [5, 5, 0], "radius": 2.5, "start_angle": 0.0,
             "end_angle": 3.14159265358979, "layer": "0"},
            "fake.dwg", "fake_out", apply_staged=_fake_apply_staged(entity))
        self.assertEqual(result["status"], cad_op_gate.STATUS_OK)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)
        self.assertEqual(result["native_op"], "write.entity.arc")

    def test_shifted_roundtrip_is_exit_1(self):
        entity = {"handle": "9F1", "dxf_name": "LINE", "layer": "DIM",
                  "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [100.0, 5.0, 0.0]}}
        result = probe.probe_roundtrip(
            "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"},
            "fake.dwg", "fake_out", apply_staged=_fake_apply_staged(entity))
        self.assertEqual(result["status"], cad_op_gate.STATUS_FAIL)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_FAIL)

    def test_apply_staged_not_implemented_degrades_truthfully(self):
        result = probe.probe_roundtrip(
            "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"},
            "fake.dwg", "fake_out",
            apply_staged=_fake_apply_staged(
                {}, status="not_implemented", reason="run_job.run_router_cad_job unavailable"))
        self.assertEqual(result["status"], cad_op_gate.STATUS_NOT_IMPLEMENTED)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_NOT_IMPLEMENTED)

    def test_apply_staged_blocked_is_error_not_fake_pass(self):
        result = probe.probe_roundtrip(
            "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"},
            "fake.dwg", "fake_out",
            apply_staged=_fake_apply_staged({}, status="blocked", reason="guards failed"))
        self.assertEqual(result["status"], cad_op_gate.STATUS_ERROR)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_ERROR)

    def test_original_mutated_during_apply_is_exit_5(self):
        entity = {"handle": "9F1", "dxf_name": "LINE", "layer": "DIM",
                  "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [100.0, 0.0, 0.0]}}
        result = probe.probe_roundtrip(
            "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"},
            "fake.dwg", "fake_out",
            apply_staged=_fake_apply_staged(entity, original_unchanged=False))
        self.assertEqual(result["status"], cad_op_gate.STATUS_ORIGINAL_MUTATED)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_ORIGINAL_MUTATED)

    def test_matching_ellipse_roundtrip_is_exit_0(self):
        # end-to-end wiring for the T3a ellipse ground-truth builder,
        # mirroring test_matching_arc_roundtrip_is_exit_0.
        entity = {"handle": "9F3", "dxf_name": "ELLIPSE", "layer": "0",
                  "geometry": {"kind": "ellipse", "center": [1.0, 2.0, 0.0],
                              "normal": [0.0, 0.0, 1.0], "major_axis": [3.0, 0.0, 0.0],
                              "radius_ratio": 0.5, "start_angle": 0.0,
                              "end_angle": 6.283185307179586}}
        result = probe.probe_roundtrip(
            "create_ellipse",
            {"center": [1, 2, 0], "normal": [0, 0, 1], "major_axis": [3, 0, 0],
             "radius_ratio": 0.5, "start_angle": 0.0, "end_angle": 6.283185307179586,
             "layer": "0"},
            "fake.dwg", "fake_out", apply_staged=_fake_apply_staged(entity))
        self.assertEqual(result["status"], cad_op_gate.STATUS_OK)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)
        self.assertEqual(result["native_op"], "write.entity.ellipse")

    def test_matching_dimension_roundtrip_is_exit_0(self):
        # end-to-end wiring for the T3a dimension ground-truth builder. The
        # actual read-back may ALSO carry dim_block_handle/dim_block_name
        # (top-level, per ir_builder.py's _entity_from_native) -- those must
        # never affect the geometry-basis roundtrip diff.
        # dim_line_point is the CANONICALIZED value (re-anchored at
        # xLine2Point, see _rotated_dimension_line_point), not a raw echo of
        # the (50, 20, 0) arg below -- this fake stands in for a real
        # read-back, which never contains the raw arg either.
        entity = {"handle": "9F4", "dxf_name": "DIMENSION", "layer": "0",
                  "dim_block_handle": "7A1", "dim_block_name": "*D1",
                  "geometry": {"kind": "dimension", "xline1_point": [0.0, 0.0, 0.0],
                              "xline2_point": [100.0, 0.0, 0.0],
                              "dim_line_point": [100.0, 20.0, 0.0],
                              "rotation": 0.0, "measurement": 100.0}}
        result = probe.probe_roundtrip(
            "create_dimension",
            {"xline1": [0, 0, 0], "xline2": [100, 0, 0], "dim_line": [50, 20, 0],
             "rotation": 0.0, "layer": "0"},
            "fake.dwg", "fake_out", apply_staged=_fake_apply_staged(entity))
        self.assertEqual(result["status"], cad_op_gate.STATUS_OK)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)
        self.assertEqual(result["native_op"], "write.entity.dim.rotated")

    def test_unbuildable_expected_ir_is_exit_3_even_if_natively_wired(self):
        # a defensive case: an op_name that IS wired natively but this module
        # has no ground-truth builder for must still be NOT_IMPLEMENTED
        # (never silently guessed). create_ellipse/create_dimension were this
        # fixture pre-T3a; create_mpolygon is a REAL, permanent instance of
        # this today (patch_ops.NATIVE_WRITE_OP_MAP really does map it to
        # write.entity.mpolygon -- no fake override needed): its live create
        # itself fails (errorstatus=409), a genuinely different kind of gap
        # than a missing reader branch, but still correctly NOT_IMPLEMENTED
        # here since this module has no ground-truth builder for it either.
        import patch_ops
        self.assertIn("create_mpolygon", patch_ops.NATIVE_WRITE_OP_MAP,
                     "fixture premise: create_mpolygon must genuinely be natively wired today")

        def _must_not_be_called(patch, dwg_path, out_dir):
            raise AssertionError("apply_staged must never be called without expected-entity ground truth")

        result = probe.probe_roundtrip(
            "create_mpolygon", {}, "fake.dwg", "fake_out",
            apply_staged=_must_not_be_called)
        self.assertEqual(result["status"], cad_op_gate.STATUS_NOT_IMPLEMENTED)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_NOT_IMPLEMENTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
