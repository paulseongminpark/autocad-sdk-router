#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""op_roundtrip_probe.py -- CAD OS Layer WAVE-0 F3: the op_id -> P-gate driver.

``cad_op_gate.py`` is pure judge logic (dict-in, dict-out; fully unit-testable
without a live CAD runtime). THIS module is the thin, op-aware DRIVER that
feeds it real staged-write results:

  1. ``resolve_native_op`` -- a patch op_name (e.g. ``"create_line"``) maps to
     its native ObjectARX op_id via ``tools/patch_ops`` (F9's split registry,
     already merged). An op_name with NO live handler fails HERE, before any
     disk/process activity -- this is the "exit 3 on not-wired" acceptance
     case, checked first and unconditionally.
  2. ``expected_ir_for_op`` -- builds the single-entity "ground truth" IR
     directly from the op's OWN args (the geometry we ASKED to be written --
     never a live read). This is the P-gate's ``expected_ir``.
  3. ``probe_roundtrip`` -- drives ``patch_engine.apply_staged`` (already
     merged: staging, the real ObjectARX write, pre/post-inspect, cad_diff,
     validate, and the original-unchanged proof) to mutate a STAGED COPY and
     extract the REAL pre/post IR. Injectable as ``apply_staged=`` purely for
     testability (mirrors ``cross_oracle.py``'s own ``router_extract``
     injection pattern) -- unit tests inject a fake envelope; LIVE callers get
     the real ``patch_engine.apply_staged`` by default.
  4. ``added_entities_ir`` -- resolves the diff's added-handle set back into
     FULL post-IR entity records (``cad_diff``'s ``changed_handles`` only
     carries handle/dxf_name/layer, not geometry) -- this is the P-gate's
     ``actual_ir``.
  5. hands ``(expected_ir, actual_ir)`` to ``cad_op_gate.check_roundtrip`` and
     folds in the original-unchanged proof ``apply_staged`` already computed.

Live-runtime status (Rule 12, no-fake-success)
------------------------------------------------
The LIVE leg genuinely shells out to accoreconsole via
``patch_engine.apply_staged -> run_job.run_router_cad_job`` (already-merged,
real router integration) -- it is NOT re-implemented here. This module's OWN
logic (op resolution / expected-entity construction / added-entity extraction
/ gate wiring) is fully exercised by
``tests/unit/test_op_roundtrip_probe.py`` against an INJECTED fake
``apply_staged`` (no accoreconsole invoked in CI/unit tests). A genuine
end-to-end run against a live, disposable staging DWG is DONE_NEEDS_RUNTIME:

    Deferred live command (run from this worktree root; AutoCAD 2027 present
    on this box, but a real staged write was not exercised in this build --
    provisioning a disposable scratch DWG + verifying the real ObjectARX
    write path is out of scope for a pure-logic unit-test gate):

        python tools/op_roundtrip_probe.py --op create_line \\
            --dwg <a real, disposable staging DWG path> \\
            --start 0 0 0 --end 100 0 0 --layer DIM \\
            --out-dir runs/f3_probe_live

Public API:
    resolve_native_op(op_name, patch_ops_mod=None) -> str | None
    expected_ir_for_op(op_name, args) -> dict
    added_entities_ir(pre_ir, post_ir, cad_diff_mod=None) -> dict
    probe_roundtrip(op_name, args, dwg_path, out_dir, apply_staged=None, ...) -> dict
    load_ir(path) -> dict                                        # BOM-tolerant

Run ``python tools/op_roundtrip_probe.py`` (no args) for a synthetic self-demo
against an injected fake ``apply_staged`` (no live runtime touched).
"""
from __future__ import annotations

import json
import math
import os
import sys
from typing import Any, Callable, Dict, Optional

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)

SCHEMA_ID = "ariadne.op_roundtrip_probe.v1"
IR_SCHEMA_ID = "ariadne.dwg_graph_ir.v1"
_JSON_ENCODING = "utf-8-sig"


def _import_optional(module_name: str):
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
    try:
        return __import__(module_name)
    except Exception:  # pragma: no cover - defensive; sibling truly absent
        return None


def load_ir(path) -> Dict[str, Any]:
    """Load an IR JSON document (BOM-tolerant)."""
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _load_ir_maybe(value: Any) -> Dict[str, Any]:
    """``value`` is either an already-loaded IR dict (unit tests) or a path
    string (the real patch_engine.apply_staged envelope's extra.pre_ir/
    post_ir, which are on-disk JSON paths)."""
    if isinstance(value, dict):
        return value
    return load_ir(value)


# --------------------------------------------------------------------------- #
# 1. op resolution -- "exit 3 on not-wired" fires here
# --------------------------------------------------------------------------- #

def resolve_native_op(op_name: str, *, patch_ops_mod=None) -> Optional[str]:
    """patch op_name (e.g. ``"create_line"``) -> native op_id, or ``None`` if
    this patch op has no LIVE native write handler wired today
    (``patch_ops.NATIVE_WRITE_OP_MAP``, F9's split registry)."""
    mod = patch_ops_mod if patch_ops_mod is not None else _import_optional("patch_ops")
    if mod is None:
        return None
    return (getattr(mod, "NATIVE_WRITE_OP_MAP", None) or {}).get(op_name)


# --------------------------------------------------------------------------- #
# 2. expected-entity construction (ground truth = the op's own args, never a
#    live read)
# --------------------------------------------------------------------------- #

def _point_to_list(coords: Any) -> list:
    """The IR's OWN geometry representation is a plain ``[x, y, z]`` list (see
    ``added_entities_ir`` / the native extractor's ``actual_ir``) -- distinct
    from the job-args point-OBJECT shape schemas/cad_job.v2.schema.json
    requires (``{"x":.., "y":.., "z":..}``, confirmed by test_native/
    job_line_create.json). Accepts either shape so this stays correct for
    both CLI-built args (point-object, see ``_as_point_arg``) and any
    programmatic caller still passing a bare ``[x, y, z]``."""
    if isinstance(coords, dict):
        return [coords.get("x", 0.0), coords.get("y", 0.0), coords.get("z", 0.0)]
    return list(coords)


def _expect_create_line(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "dxf_name": "LINE", "layer": args.get("layer") or "0",
        "geometry": {"kind": "line", "start": _point_to_list(args["start"]),
                    "end": _point_to_list(args["end"])},
    }


def _expect_create_circle(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "dxf_name": "CIRCLE", "layer": args.get("layer") or "0",
        "geometry": {"kind": "circle", "center": _point_to_list(args["center"]),
                    "radius": args["radius"]},
    }


def _expect_create_arc(args: Dict[str, Any]) -> Dict[str, Any]:
    # AriadneNativeJob.cpp's collectModelSpaceGraph (the inspect.database.graph
    # reader every apply_staged pre/post-inspect uses) casts AcDbArc BEFORE
    # AcDbCircle and emits exactly center/radius/start_angle/end_angle -- no
    # "normal" -- so that is the full, honest ground truth for a roundtrip.
    return {
        "dxf_name": "ARC", "layer": args.get("layer") or "0",
        "geometry": {"kind": "arc", "center": _point_to_list(args["center"]),
                    "radius": args["radius"], "start_angle": args["start_angle"],
                    "end_angle": args["end_angle"]},
    }


def _expect_create_text(args: Dict[str, Any]) -> Dict[str, Any]:
    # collectModelSpaceGraph's AcDbText branch (T3a) now also surfaces height
    # (AcDbText::height()) -- write.entity.text (m08h_handlers.inc) always
    # calls setHeight(height) for a positive height (default 2.5 when the arg
    # is absent), so ground truth requires an explicit "height" arg, exactly
    # like create_arc requires explicit start_angle/end_angle.
    return {
        "dxf_name": "TEXT", "layer": args.get("layer") or "0",
        "geometry": {"kind": "text", "position": _point_to_list(args["position"]),
                    "text": args.get("text", ""), "height": args["height"]},
    }


def _expect_create_mtext(args: Dict[str, Any]) -> Dict[str, Any]:
    # Same T3a fix as create_text: AcDbMText's branch now surfaces height
    # (AcDbMText::textHeight()), a direct echo of setTextHeight(height).
    return {
        "dxf_name": "MTEXT", "layer": args.get("layer") or "0",
        "geometry": {"kind": "mtext", "position": _point_to_list(args["position"]),
                    "text": args.get("text", ""), "height": args["height"]},
    }


def _expect_create_polyline(args: Dict[str, Any]) -> Dict[str, Any]:
    # write.entity.polyline (m08g_handlers.inc) builds a real AcDbPolyline
    # (LWPOLYLINE) via addVertexAt(AcGePoint2d(x, y), bulge) and setClosed()
    # when "closed" is a truthy NUMBER (m08g's own check is `cf != 0.0` via
    # jsonFindNumber -- a JSON bool literal would not parse as a number, so
    # callers must pass 0/1, never true/false). collectModelSpaceGraph's
    # AcDbPolyline branch (T3a) now calls getBulgeAt()/isClosed() too, so
    # both are direct echoes of the write args.
    vertices = [{"point": [pt.get("x", 0.0), pt.get("y", 0.0), 0.0],
                "bulge": pt.get("bulge", 0.0)}
                for pt in (args.get("points") or [])]
    closed = bool(args.get("closed", 0))
    return {
        "dxf_name": "LWPOLYLINE", "layer": args.get("layer") or "0",
        "geometry": {"kind": "lwpolyline", "vertices": vertices, "closed": closed},
    }


def _expect_create_ellipse(args: Dict[str, Any]) -> Dict[str, Any]:
    # collectModelSpaceGraph's AcDbEllipse branch (T3a) emits center/
    # major_axis/radius_ratio/start_angle/end_angle/normal -- every ctor arg
    # write.entity.ellipse passes to AcDbEllipse(center, normal, major, ratio,
    # sa, ea) verbatim (m08g_handlers.inc), so ground truth is a direct
    # pass-through, exactly like create_arc's.
    return {
        "dxf_name": "ELLIPSE", "layer": args.get("layer") or "0",
        "geometry": {"kind": "ellipse", "center": _point_to_list(args["center"]),
                    "normal": _point_to_list(args["normal"]),
                    "major_axis": _point_to_list(args["major_axis"]),
                    "radius_ratio": args["radius_ratio"],
                    "start_angle": args["start_angle"], "end_angle": args["end_angle"]},
    }


def _rotated_dimension_measurement(p1: list, p2: list, rotation: float) -> float:
    """AcDbRotatedDimension's measurement: the xLine1Point->xLine2Point vector
    projected onto the dimension line's direction (angle ``rotation`` from the
    X axis) -- the same projection AutoCAD uses to derive the linear distance
    a rotated dimension displays. Independently computed (not an arg) so
    create_dimension's ground truth can assert it without a live read.
    """
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return abs(dx * math.cos(rotation) + dy * math.sin(rotation))


def _rotated_dimension_line_point(p1: list, p2: list, rotation: float, dim_line_arg: list) -> list:
    """AcDbRotatedDimension does NOT store the raw ``dim_line`` ctor arg back
    verbatim -- live-verified (2026-07-02 T3a re-cert, 2 real accoreconsole
    roundtrips: rotation=0 and rotation=pi/4) against
    ``tests/fixtures/native_sample.dwg``: AutoCAD keeps only the PERPENDICULAR
    offset of the input point relative to xLine1Point (the distance the
    dimension line sits off the measured baseline) along
    ``v = (-sin(rotation), cos(rotation))`` -- the along-axis component is
    discarded and the stored point is re-anchored at xLine2Point instead:
    ``stored = xLine2Point + offset * v``. Confirmed exactly (to float
    precision) on both live cases, e.g. xline1=(0,0) xline2=(100,0) rotation=0
    dim_line=(50,20) -> stored (100.0, 20.0, 0.0), NOT (50, 20, 0).

    Both verification cases used an xLine1Point->xLine2Point baseline
    PARALLEL to the rotation direction (the common "measure along this axis"
    case a rotated dimension is normally used for) -- this ground truth is
    only asserted for that case; a non-parallel baseline is unverified.
    """
    ux, uy = math.cos(rotation), math.sin(rotation)
    vx, vy = -uy, ux
    dx = dim_line_arg[0] - p1[0]
    dy = dim_line_arg[1] - p1[1]
    offset = dx * vx + dy * vy
    return [p2[0] + offset * vx, p2[1] + offset * vy, p2[2]]


def _expect_create_dimension(args: Dict[str, Any]) -> Dict[str, Any]:
    # collectModelSpaceGraph's AcDbRotatedDimension branch (T3a) emits the 3
    # defining points + rotation + measurement. xline1_point/xline2_point/
    # rotation are direct ctor-arg echoes; "measurement" and "dim_line_point"
    # are NOT -- AutoCAD derives/canonicalizes both internally -- so this
    # ground truth independently computes the same values
    # (_rotated_dimension_measurement / _rotated_dimension_line_point) rather
    # than echoing args.
    #
    # dim_block_handle/dim_block_name (the dimension's anonymous defining-
    # block id/name) are DELIBERATELY absent here even though the reader now
    # surfaces them: that value is AutoCAD's own incrementing anonymous-block
    # counter (*D1, *D2, ...), a function of the live drawing's PRE-EXISTING
    # block count, not of this op's own args -- asserting it here would
    # violate expected_ir_for_op's "ground truth from args alone, never a
    # live read" contract. ir_builder.py's _entity_from_native surfaces it as
    # a top-level field OUTSIDE "geometry" for exactly this reason: it must
    # never enter this P-gate's geometry-basis fingerprint (cad_diff.py's
    # comparison_basis="geometry" only ever looks at entity["geometry"]).
    xline1 = _point_to_list(args["xline1"])
    xline2 = _point_to_list(args["xline2"])
    rotation = args["rotation"]
    dim_line_arg = _point_to_list(args["dim_line"])
    return {
        "dxf_name": "DIMENSION", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "dimension",
            "xline1_point": xline1, "xline2_point": xline2,
            "dim_line_point": _rotated_dimension_line_point(xline1, xline2, rotation, dim_line_arg),
            "rotation": rotation,
            "measurement": _rotated_dimension_measurement(xline1, xline2, rotation),
        },
    }


def _expect_create_dimension_aligned(args: Dict[str, Any]) -> Dict[str, Any]:
    # An ALIGNED dimension is a rotated dimension whose "rotation" is not an
    # independent arg -- it is implicitly the xLine1->xLine2 baseline's own
    # angle (that is the definition of "aligned": the dimension line is always
    # parallel to the measured baseline). Live-verified (2026-07-02 T3a-batch2
    # re-cert) against tests/fixtures/native_sample.dwg: AcDbAlignedDimension
    # re-anchors dim_line_point EXACTLY like AcDbRotatedDimension does (T3a),
    # so this reuses _rotated_dimension_line_point/_measurement verbatim with
    # the baseline angle standing in for "rotation" -- projecting the baseline
    # vector onto its own direction is just its own length, so measurement
    # reduces to the straight-line xLine1->xLine2 distance, as expected for an
    # aligned dimension.
    xline1 = _point_to_list(args["xline1"])
    xline2 = _point_to_list(args["xline2"])
    baseline_rotation = math.atan2(xline2[1] - xline1[1], xline2[0] - xline1[0])
    dim_line_arg = _point_to_list(args["dim_line"])
    return {
        "dxf_name": "DIMENSION", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "dimension",
            "xline1_point": xline1, "xline2_point": xline2,
            "dim_line_point": _rotated_dimension_line_point(
                xline1, xline2, baseline_rotation, dim_line_arg),
            "measurement": _rotated_dimension_measurement(xline1, xline2, baseline_rotation),
        },
    }


def _expect_create_dimension_radial(args: Dict[str, Any]) -> Dict[str, Any]:
    # AcDbRadialDimension has no rotation-style re-anchoring degree of freedom
    # (unlike aligned/rotated, there is no "dimension line" point independent
    # of center/chord_point) -- center/chord_point are direct ctor-arg echoes
    # (live-verified 2026-07-02 T3a-batch2 re-cert). measurement is the
    # dimensioned radius: the center->chord_point distance, independently
    # computed (not an arg) so ground truth never needs a live read.
    #
    # leader_length is NOT asserted: LIVE-DISCOVERED (2026-07-02 T3a-batch2
    # re-cert) that it does not survive as a ctor-arg echo -- AutoCAD reset a
    # requested leader_length=5.0 to 0.0 for a chord_point 10 units from
    # center (no leader actually needed at default text/arrow size), i.e. it
    # is AutoCAD's own internal leader-needed recompute, not derivable from
    # this op's own args alone -- same treatment as dim_block_handle/name.
    # ir_builder.py surfaces it as a TOP-LEVEL entity field instead.
    center = _point_to_list(args["center"])
    chord = _point_to_list(args["chord_point"])
    dx, dy, dz = chord[0] - center[0], chord[1] - center[1], chord[2] - center[2]
    measurement = math.sqrt(dx * dx + dy * dy + dz * dz)
    return {
        "dxf_name": "DIMENSION", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "dimension",
            "center": center, "chord_point": chord,
            "measurement": measurement,
        },
    }


def _expect_create_dimension_diametric(args: Dict[str, Any]) -> Dict[str, Any]:
    # AcDbDiametricDimension, same reasoning as radial: chord_point/
    # far_chord_point are direct ctor-arg echoes (live-verified 2026-07-02
    # T3a-batch2 re-cert); measurement is the dimensioned diameter, the
    # chord_point<->far_chord_point distance. leader_length is NOT asserted,
    # for the identical live-discovered reason documented on
    # _expect_create_dimension_radial above.
    chord = _point_to_list(args["chord_point"])
    far_chord = _point_to_list(args["far_chord_point"])
    dx, dy, dz = far_chord[0] - chord[0], far_chord[1] - chord[1], far_chord[2] - chord[2]
    measurement = math.sqrt(dx * dx + dy * dy + dz * dz)
    return {
        "dxf_name": "DIMENSION", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "dimension",
            "chord_point": chord, "far_chord_point": far_chord,
            "measurement": measurement,
        },
    }


def _expect_create_dimension_ordinate(args: Dict[str, Any]) -> Dict[str, Any]:
    # AcDbOrdinateDimension(useXAxis, definingPoint, leaderEndPoint, dimText,
    # dimStyle) -- write.entity.dim.ordinate (m08h_handlers.inc) passes
    # defining_point/leader_end_point/use_x_axis straight to the ctor with no
    # re-anchoring degree of freedom (unlike aligned/rotated dim_line_point),
    # so all three are direct, args-derivable ground truth. use_x_axis
    # defaults to True when the arg is absent, mirroring the handler's own
    # "useXAxis = true unless use_x_axis is an explicit falsy number" default.
    #
    # measurement IS asserted (unlike leader_length/dim_block_handle): LIVE-
    # VERIFIED (2026-07-02 T3a-batch3 re-cert, 2 real accoreconsole roundtrips
    # -- one per axis) that an ordinate dimension's measurement is simply the
    # defining_point's own X (useXAxis) or Y (not useXAxis) coordinate relative
    # to origin() -- and origin() is always (0,0,0) here since this op never
    # calls setOrigin. Case 1: use_x_axis=True, defining_point=(10,5,0) ->
    # measurement=10.0 (the X coordinate). Case 2: use_x_axis=False,
    # defining_point=(7,12,0) -> measurement=12.0 (the Y coordinate). This is
    # args-derivable (never a live read) and independently computed here,
    # exactly like _rotated_dimension_measurement.
    #
    # origin is NOT asserted: not a write.entity.dim.ordinate ctor arg at all
    # (see ir_builder.py/_entity_from_native's top-level "origin" field and
    # AriadneNativeJob.cpp's AcDbOrdinateDimension branch) -- extracted by the
    # reader for completeness but kept outside this op's own-args contract.
    defining_point = _point_to_list(args["defining_point"])
    leader_end_point = _point_to_list(args["leader_end_point"])
    use_x_axis = bool(args.get("use_x_axis", True))
    measurement = defining_point[0] if use_x_axis else defining_point[1]
    return {
        "dxf_name": "DIMENSION", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "dimension",
            "defining_point": defining_point, "leader_end_point": leader_end_point,
            "use_x_axis": use_x_axis, "measurement": measurement,
        },
    }


def _expect_create_leader(args: Dict[str, Any]) -> Dict[str, Any]:
    # write.entity.leader (m08h_handlers.inc) reads "vertices" first, falling
    # back to "points" only when "vertices" yields <2 points -- this batch's
    # own fixture always supplies "vertices" directly, so this mirrors that
    # same order. Each vertex is a direct, args-derivable echo (appendVertex
    # per point, no transform); has_arrow_head/splined are deterministic
    # constants for THIS op (enableArrowHead()/setToStraightLeader() are
    # unconditionally called, never gated on any arg) -- live-verified
    # (2026-07-02 T3a-batch3 re-cert) diff=0 for exactly these three fields.
    #
    # annotation_handle is NOT exercised/asserted here: this batch's fixture
    # never supplies "text", so no annotation AcDbMText is ever created -- an
    # annotated leader appends a SECOND, separate entity, which is out of
    # scope for this single-entity geometry P-gate (see AriadneNativeJob.cpp's
    # AcDbLeader branch).
    vertices_arg = args.get("vertices") or args.get("points") or []
    vertices = [{"point": _point_to_list(p)} for p in vertices_arg]
    return {
        "dxf_name": "LEADER", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "leader",
            "vertices": vertices, "has_arrow_head": True, "splined": False,
        },
    }


def _expect_create_spline(args: Dict[str, Any]) -> Dict[str, Any]:
    # write.entity.spline (m08g_handlers.inc) always builds a FIT-POINT
    # AcDbSpline: AcDbSpline(fitPts, order, 0.0) -- order defaults to 4.0 (same
    # default, same "order<2 -> 4" clamp, reproduced here) and is never
    # periodic/closed. degree/closed/fit_points are therefore direct,
    # args-derivable ground truth (degree = order-1, closed always False, fit_
    # points the literal "points" arg) -- live-verified (2026-07-02 T3a-batch2
    # re-cert) diff=0 for exactly these three fields.
    #
    # spline_control_points/spline_knots are NOT asserted here even though the
    # reader now extracts them: they are AutoCAD's OWN fit-to-NURBS conversion
    # result (its internal global curve interpolation from the fit points),
    # not derivable from this op's own args alone without reproducing that
    # proprietary algorithm -- asserting them would violate expected_ir_for_
    # op's "ground truth from args alone, never a live read" contract, exactly
    # like dim_block_handle/dim_block_name. ir_builder.py surfaces both as
    # TOP-LEVEL entity fields (never inside "geometry") for the same reason.
    order = args.get("order", 4)
    if order < 2:
        order = 4
    degree = int(order) - 1
    fit_points = [_point_to_list(p) for p in (args.get("points") or [])]
    return {
        "dxf_name": "SPLINE", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "spline",
            "degree": degree, "closed": False, "fit_points": fit_points,
        },
    }


def _expect_create_mline(args: Dict[str, Any]) -> Dict[str, Any]:
    # write.entity.mline (m08g_handlers.inc) reads "points" first, falling back
    # to "vertices" only when "points" yields <2 points (the OPPOSITE
    # precedence from write.entity.leader's vertices-first order -- mirrored
    # exactly here, not just copy-pasted). Each vertex is a direct, args-
    # derivable echo (appendSeg per point, no transform, same plain-array shape
    # as create_leader's -- an mline vertex has no bulge concept either).
    # "closed" is a direct echo of the op's own "closed" arg: setClosedMline is
    # only called when closed is a truthy NUMBER (m08g's own check is
    # `closed != 0.0` via jsonFindNumber, same convention create_polyline
    # documents -- a JSON bool literal would not parse as a number). Live-
    # verified (2026-07-02 w3-wbug re-cert, real accoreconsole roundtrip
    # against tests/fixtures/native_sample.dwg) diff=0 for exactly these two
    # fields. style/scale/justification are NOT asserted: none of the three is
    # an independently-observable geometry field collectModelSpaceGraph
    # extracts (AcDbMline exposes them via style()/scale()/justification(),
    # none of which this P-gate's geometry-basis compare reads today) -- out of
    # scope for this single-entity geometry cert, same treatment
    # dim_block_handle/spline_control_points got.
    points_arg = args.get("points") or []
    if len(points_arg) < 2:
        points_arg = args.get("vertices") or []
    vertices = [{"point": _point_to_list(p)} for p in points_arg]
    closed = bool(args.get("closed", 0))
    return {
        "dxf_name": "MLINE", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "mline",
            "vertices": vertices, "closed": closed,
        },
    }


# op_name -> args -> a single IR entity (dxf_name/layer/geometry only -- no
# handle; the P-gate's geometry-basis compare is handle-independent by
# design). Only ops this module can honestly build ground truth for; an
# op_name outside this map is NOT_IMPLEMENTED here even if it happens to be
# wired natively (a real gap between "can write" and "can independently
# assert what SHOULD have been written" -- no-fake-success).
#
# create_ellipse / create_dimension were EXCLUDED through T1 -- a genuine
# reader-side gap in collectModelSpaceGraph (no AcDbEllipse or
# AcDbDimension-subclass read branch at all). T3a added both branches (see
# src/Ariadne.AcadNative/AriadneNativeJob.cpp), so both are now certifiable
# and included below.
# create_mpolygon is excluded because its live write itself fails
# (errorstatus=409); set_entity_xdata is excluded because it mutates
# non-geometry entity data (xdata), which this geometry-basis P-gate does
# not cover at all (that is cad_op_gate's separate D-half/gate_field_mutation
# concern).
#
# T3a-batch2 adds create_spline / create_dimension_aligned /
# create_dimension_radial / create_dimension_diametric: all four were already
# native-REACHABLE (measure/reachable_matrix.jsonl) but had (a) no patch_ops
# wiring at all (tools/patch_ops/entities.py, added this batch) and (b) no
# collectModelSpaceGraph read branch (AriadneNativeJob.cpp, added this batch)
# -- the same two-part gap create_ellipse/create_dimension had through T1.
#
# T3a-batch3 adds create_dimension_ordinate / create_leader: same two-part gap
# (already native-REACHABLE per measure/reachable_matrix.jsonl, but no
# patch_ops wiring and no collectModelSpaceGraph read branch until this batch).
#
# w3-wbug adds create_mline: unlike every T3a-batch kind, this one was NOT
# already native-REACHABLE -- write.entity.mline's handler had a real bug
# (appendSeg's ErrorStatus was never checked, so a silently-failing build
# still reported success with a geometrically-empty MLINE; see
# m08g_handlers.inc). Fixing that bug plus the same two-part gap (patch_ops
# wiring + collectModelSpaceGraph read branch) both landed together.
_EXPECTED_ENTITY_BUILDERS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "create_line": _expect_create_line,
    "create_circle": _expect_create_circle,
    "create_arc": _expect_create_arc,
    "create_ellipse": _expect_create_ellipse,
    "create_text": _expect_create_text,
    "create_mtext": _expect_create_mtext,
    "create_polyline": _expect_create_polyline,
    "create_dimension": _expect_create_dimension,
    "create_spline": _expect_create_spline,
    "create_dimension_aligned": _expect_create_dimension_aligned,
    "create_dimension_radial": _expect_create_dimension_radial,
    "create_dimension_diametric": _expect_create_dimension_diametric,
    "create_dimension_ordinate": _expect_create_dimension_ordinate,
    "create_leader": _expect_create_leader,
    "create_mline": _expect_create_mline,
}


def expected_ir_for_op(op_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """A minimal single-entity ``dwg_graph_ir.v1`` doc: the geometry ground
    truth the op's OWN args assert -- the P-gate's ``expected_ir``.

    Raises ``NotImplementedError`` for an ``op_name`` this module has no
    ground-truth builder for (a real gap, never silently guessed).
    """
    builder = _EXPECTED_ENTITY_BUILDERS.get(op_name)
    if builder is None:
        raise NotImplementedError(
            "no expected-entity builder for op_name %r (wired: %s)"
            % (op_name, sorted(_EXPECTED_ENTITY_BUILDERS)))
    return {"schema": IR_SCHEMA_ID, "entities": [builder(args)]}


# --------------------------------------------------------------------------- #
# 4. added-entity extraction: real post IR -> the single new FULL record
# --------------------------------------------------------------------------- #

def added_entities_ir(pre_ir: Dict[str, Any], post_ir: Dict[str, Any], *,
                      cad_diff_mod=None) -> Dict[str, Any]:
    """The IR-shaped subset of ``post_ir``'s entities whose handle is NEW
    relative to ``pre_ir`` (a handle-basis diff's 'added' set), resolved back
    into FULL entity records -- ``cad_diff``'s ``changed_handles`` only
    carries handle/dxf_name/layer, not the geometry the P-gate needs.
    """
    cd = cad_diff_mod if cad_diff_mod is not None else _import_optional("cad_diff")
    if cd is None or not hasattr(cd, "compute_diff"):
        raise RuntimeError("cad_diff sibling module unavailable")
    diff = cd.compute_diff(pre_ir, post_ir, comparison_basis="handle")
    added_handles = {r["handle"] for r in diff["changed_handles"] if r["change"] == "added"}
    post_by_handle = {e.get("handle"): e for e in (post_ir.get("entities") or []) if isinstance(e, dict)}
    entities = [post_by_handle[h] for h in sorted(added_handles) if h in post_by_handle]
    return {"schema": IR_SCHEMA_ID, "entities": entities}


# --------------------------------------------------------------------------- #
# 3./5. the driver: stage + write + inspect (patch_engine.apply_staged) ->
# P-gate judge (cad_op_gate.check_roundtrip)
# --------------------------------------------------------------------------- #

def _build_patch(op_name: str, args: Dict[str, Any], dwg_path: str, out_dir: str) -> Dict[str, Any]:
    # target_dwg is REQUIRED by schemas/cad_patch.v1.schema.json (staged_path
    # distinct from original_path). apply_staged's own create_staged_copy(dwg_path,
    # out_dir) always writes to <out_dir>/staged_input.dwg regardless of this
    # declared value (it does not read target_dwg to decide where to stage) --
    # so this is the TRUE path, not a placeholder, kept honest with what
    # create_staged_copy actually produces moments later.
    return {
        "schema": "ariadne.cad_patch.v1",
        "patch_id": "op_roundtrip_probe/%s" % op_name,
        "target_dwg": {
            "original_path": os.path.abspath(dwg_path),
            "staged_path": os.path.join(out_dir, "staged_input.dwg"),
        },
        "operations": [{"step_id": "s1", "operation": op_name, "args": args}],
        "postconditions": [{"subject": "entity_count", "op": "delta_eq", "value": 1}],
        "policy": {"staged_copy": True, "write_mode": "write_copy"},
    }


def probe_roundtrip(op_name: str, args: Dict[str, Any], dwg_path: str, out_dir: str, *,
                    apply_staged: Optional[Callable[[Dict[str, Any], str, str], Dict[str, Any]]] = None,
                    geometry_tolerance: Optional[float] = None,
                    patch_ops_mod=None, cad_diff_mod=None, cad_op_gate_mod=None) -> Dict[str, Any]:
    """Run the P-gate roundtrip probe for one ``create_*`` op against
    ``dwg_path``. See module docstring for the 5-step pipeline. Every non-OK
    outcome (not wired / apply_staged degraded / original mutated / geometry
    mismatch) returns a truthful ``cad_op_gate``-shaped result -- never a
    fake PASS.
    """
    gate = cad_op_gate_mod if cad_op_gate_mod is not None else _import_optional("cad_op_gate")
    if gate is None:
        return {"schema": SCHEMA_ID, "op_name": op_name, "status": "error", "exit_code": 2,
               "reason": "cad_op_gate sibling module unavailable"}

    native_op = resolve_native_op(op_name, patch_ops_mod=patch_ops_mod)
    if native_op is None:
        return {
            "schema": SCHEMA_ID, "op_name": op_name, "status": gate.STATUS_NOT_IMPLEMENTED,
            "exit_code": gate.EXIT_NOT_IMPLEMENTED,
            "reason": "op_name %r has no live native write handler wired "
                      "(patch_ops.NATIVE_WRITE_OP_MAP)" % op_name,
        }

    try:
        expected_ir = expected_ir_for_op(op_name, args)
    except NotImplementedError as exc:
        return {
            "schema": SCHEMA_ID, "op_name": op_name, "native_op": native_op,
            "status": gate.STATUS_NOT_IMPLEMENTED, "exit_code": gate.EXIT_NOT_IMPLEMENTED,
            "reason": str(exc),
        }

    apply_fn = apply_staged
    if apply_fn is None:
        patch_engine = _import_optional("patch_engine")
        apply_fn = getattr(patch_engine, "apply_staged", None) if patch_engine else None
    if apply_fn is None:
        return {
            "schema": SCHEMA_ID, "op_name": op_name, "native_op": native_op,
            "status": gate.STATUS_NOT_IMPLEMENTED, "exit_code": gate.EXIT_NOT_IMPLEMENTED,
            "reason": "patch_engine.apply_staged unavailable",
        }

    patch = _build_patch(op_name, args, dwg_path, out_dir)
    envelope = apply_fn(patch, dwg_path, out_dir)
    env_status = envelope.get("status")
    if env_status != "ok":
        deferred_reasons = {"not_implemented", "unavailable"}
        exit_code = gate.EXIT_NOT_IMPLEMENTED if env_status in deferred_reasons else gate.EXIT_ERROR
        status = gate.STATUS_NOT_IMPLEMENTED if env_status in deferred_reasons else gate.STATUS_ERROR
        return {
            "schema": SCHEMA_ID, "op_name": op_name, "native_op": native_op,
            "status": status, "exit_code": exit_code,
            "reason": envelope.get("reason"), "envelope_status": env_status,
        }

    orig = envelope.get("original_unchanged") or {}
    if orig and orig.get("unchanged") is False:
        return {
            "schema": SCHEMA_ID, "op_name": op_name, "native_op": native_op,
            "status": gate.STATUS_ORIGINAL_MUTATED, "exit_code": gate.EXIT_ORIGINAL_MUTATED,
            "reason": "original DWG changed during the live apply -- READ-ONLY invariant violated",
            "original_unchanged": orig,
        }

    # patch_engine.apply_staged's _result_envelope(..., extra=...) does
    # env.update(extra) -- i.e. extra fields land at the envelope's TOP LEVEL
    # (envelope["pre_ir"] / envelope["post_ir"]), there is no nested "extra" key.
    pre_ir_ref = envelope.get("pre_ir")
    post_ir_ref = envelope.get("post_ir")
    if not pre_ir_ref or not post_ir_ref:
        return {
            "schema": SCHEMA_ID, "op_name": op_name, "native_op": native_op,
            "status": gate.STATUS_ERROR, "exit_code": gate.EXIT_ERROR,
            "reason": "apply_staged envelope reported ok but is missing pre_ir/post_ir",
        }
    pre_ir = _load_ir_maybe(pre_ir_ref)
    post_ir = _load_ir_maybe(post_ir_ref)
    actual_ir = added_entities_ir(pre_ir, post_ir, cad_diff_mod=cad_diff_mod)

    tol = geometry_tolerance if geometry_tolerance is not None else gate.DEFAULT_GEOMETRY_TOLERANCE
    gate_result = gate.check_roundtrip(expected_ir, actual_ir, geometry_tolerance=tol,
                                       cad_diff_mod=cad_diff_mod)

    result = dict(gate_result)
    result.update({
        "schema": SCHEMA_ID, "op_name": op_name, "native_op": native_op,
        "expected_ir": expected_ir, "actual_ir": actual_ir,
        "original_unchanged": orig, "run_dir": out_dir,
    })
    return result


# --------------------------------------------------------------------------- #
# Self-demo (__main__ with no args): injected fake apply_staged, no live
# runtime touched -- proves the driver's OWN wiring end to end.
# --------------------------------------------------------------------------- #

def _fake_apply_staged_ok(op_name: str, entity: Dict[str, Any]):
    def _fn(patch, dwg_path, out_dir):
        pre_ir = {"schema": IR_SCHEMA_ID, "entities": []}
        post_entity = dict(entity)
        post_entity.setdefault("handle", "9F1")
        post_ir = {"schema": IR_SCHEMA_ID, "entities": [post_entity]}
        return {
            "status": "ok",
            "original_unchanged": {"unchanged": True},
            # top-level, mirroring the REAL patch_engine.apply_staged envelope
            # (_result_envelope(..., extra=...) does env.update(extra) --
            # there is no nested "extra" key in the real contract).
            "pre_ir": pre_ir, "post_ir": post_ir,
        }
    return _fn


def _selftest() -> int:
    print("== op_roundtrip_probe self-demo (injected apply_staged, no live runtime) ==")

    matching_entity = {
        "handle": "9F1", "dxf_name": "LINE", "layer": "DIM",
        "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [100.0, 0.0, 0.0]},
    }
    r_ok = probe_roundtrip(
        "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"},
        "fake.dwg", "fake_out",
        apply_staged=_fake_apply_staged_ok("create_line", matching_entity))
    print("matching roundtrip  : status=%s exit=%d (expect ok/0)" % (r_ok["status"], r_ok["exit_code"]))

    shifted_entity = {
        "handle": "9F1", "dxf_name": "LINE", "layer": "DIM",
        "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [100.0, 5.0, 0.0]},
    }
    r_shifted = probe_roundtrip(
        "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"},
        "fake.dwg", "fake_out",
        apply_staged=_fake_apply_staged_ok("create_line", shifted_entity))
    print("shifted roundtrip   : status=%s exit=%d (expect fail/1)"
         % (r_shifted["status"], r_shifted["exit_code"]))

    r_not_wired = probe_roundtrip(
        "create_arc", {}, "fake.dwg", "fake_out",
        apply_staged=_fake_apply_staged_ok("create_arc", matching_entity))
    print("not-wired op        : status=%s exit=%d (expect not_implemented/3)"
         % (r_not_wired["status"], r_not_wired["exit_code"]))

    passed = (r_ok["exit_code"] == 0 and r_shifted["exit_code"] == 1 and r_not_wired["exit_code"] == 3)
    print("RESULT              : %s" % ("PASS" if passed else "FAIL"))
    return 0 if passed else 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="op_roundtrip_probe: op_id -> P-gate driver (F3). With no "
                    "arguments, runs an injected-apply_staged self-demo (no live runtime).")
    ap.add_argument("--op", dest="op_name", help="patch op_name, e.g. create_line")
    ap.add_argument("--dwg", dest="dwg_path", help="staging-source DWG path (LIVE leg)")
    ap.add_argument("--out-dir", dest="out_dir", help="run output directory (LIVE leg)")
    ap.add_argument("--start", nargs=3, type=float, metavar=("X", "Y", "Z"))
    ap.add_argument("--end", nargs=3, type=float, metavar=("X", "Y", "Z"))
    ap.add_argument("--center", nargs=3, type=float, metavar=("X", "Y", "Z"))
    ap.add_argument("--radius", type=float)
    ap.add_argument("--layer", default="0")
    args = ap.parse_args(argv)

    if not args.op_name or not args.dwg_path or not args.out_dir:
        return _selftest()

    def _point_arg(xyz):  # CLI [X, Y, Z] -> the {"x","y","z"} point-object
        return {"x": xyz[0], "y": xyz[1], "z": xyz[2]}  # shape write.entity.line/
        # circle actually require (schemas/cad_job.v2.schema.json + test_native/
        # job_line_create.json) -- a bare list is NOT recognized by the native
        # dispatcher and silently degenerates to a unit line/circle instead of
        # erroring, so this must match on the wire, not just satisfy Python.

    op_args: Dict[str, Any] = {"layer": args.layer}
    if args.start is not None:
        op_args["start"] = _point_arg(args.start)
    if args.end is not None:
        op_args["end"] = _point_arg(args.end)
    if args.center is not None:
        op_args["center"] = _point_arg(args.center)
    if args.radius is not None:
        op_args["radius"] = args.radius

    result = probe_roundtrip(args.op_name, op_args, args.dwg_path, args.out_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return int(result.get("exit_code", 2))


if __name__ == "__main__":
    sys.exit(main())
