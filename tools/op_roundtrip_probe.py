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
from typing import Any, Callable, Dict, List, Optional

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


def _expect_create_polyline2d(args: Dict[str, Any]) -> Dict[str, Any]:
    # w3-poly2d: write.entity.polyline2d is an ALIAS for write.entity.
    # polyline in m08g_handlers.inc ("if (op == "write.entity.polyline" ||
    # op == "write.entity.polyline2d")") -- it does NOT build a true legacy
    # AcDb2dPolyline; it builds the exact same AcDbPolyline (LWPOLYLINE) via
    # addVertexAt(AcGePoint2d(x, y), bulge) + setClosed(), byte-for-byte the
    # same code path create_polyline already exercises (identical args,
    # identical ground truth -- see _expect_create_polyline above, which
    # this mirrors verbatim). dxf_name is therefore "LWPOLYLINE" (the REAL
    # entity class written/read back), not "POLYLINE" (the class name
    # AcDb2dPolyline itself reads back as -- see _expect_create_polyline3d
    # for a case that DOES read back "POLYLINE").
    vertices = [{"point": [pt.get("x", 0.0), pt.get("y", 0.0), 0.0],
                "bulge": pt.get("bulge", 0.0)}
                for pt in (args.get("points") or [])]
    closed = bool(args.get("closed", 0))
    return {
        "dxf_name": "LWPOLYLINE", "layer": args.get("layer") or "0",
        "geometry": {"kind": "lwpolyline", "vertices": vertices, "closed": closed},
    }


def _expect_create_polyline3d(args: Dict[str, Any]) -> Dict[str, Any]:
    # w3-poly3d: write.entity.polyline3d (m08g_handlers.inc) builds a
    # genuine AcDb3dPolyline: appendAcDbEntity then appendVertex(new
    # AcDb3dPolylineVertex(point)) per point, no transform -- vertices are
    # direct, args-derivable echoes, the SAME plain [x,y,z]-array shape
    # AcDbLeader/AcDbMline/AcDbMLeader already use (NOT LWPOLYLINE's
    # {point,bulge} shape -- a 3D polyline vertex has no bulge concept).
    # "closed" is NEVER read from args at all (no setClosed() call anywhere
    # in this branch, unlike write.entity.polyline/polyline2d's own "closed"
    # handling) -- a deterministic constant, always False for this op
    # regardless of any "closed" arg a caller might pass (live-verified
    # 2026-07-02 w3-poly3d re-cert: passed closed=1 anyway, still read back
    # False).
    vertices = [{"point": _point_to_list(p)} for p in (args.get("points") or [])]
    return {
        "dxf_name": "POLYLINE", "layer": args.get("layer") or "0",
        "geometry": {"kind": "polyline", "vertices": vertices, "closed": False},
    }


def _expect_create_polygonmesh(args: Dict[str, Any]) -> Dict[str, Any]:
    # w3-pmesh: write.entity.polygonmesh (m08g_handlers.inc) builds a genuine
    # AcDbPolygonMesh via its one-shot ctor: AcDbPolygonMesh(kSimpleMesh,
    # mSize, nSize, verts, Adesk::kFalse, Adesk::kFalse) -- m_size/n_size and
    # the flattened "points" array are direct, args-derivable echoes (no
    # transform, no reordering). Vertices use the SAME plain [x,y,z]-array
    # shape create_polyline3d/create_mleader already use (a mesh vertex has no
    # bulge concept either) -- collectModelSpaceGraph's AcDbPolygonMesh branch
    # walks them via vertexIterator(), the identical owned-sub-entity idiom
    # AcDb2dPolyline/AcDb3dPolyline already use, so iteration order matches
    # construction order (live-verified 2026-07-02 w3-pmesh re-cert on an
    # asymmetric 2x3 grid -- a row/column transposition would have been
    # visible as a geometry-diff mismatch, and was not).
    #
    # m_closed/n_closed are NEVER read from args at all -- the ctor call
    # hardcodes Adesk::kFalse for both (unlike the ctor's OWN default of
    # kTrue/kTrue) -- a deterministic constant, always False for this op
    # regardless of any m_closed/n_closed a caller might (futilely) pass, the
    # same "handler ignores an arg it never reads" shape create_polyline3d's
    # "closed" already documented.
    vertices = [{"point": _point_to_list(p)} for p in (args.get("points") or [])]
    return {
        "dxf_name": "POLYLINE", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "polygon_mesh",
            "m_size": args["m_size"], "n_size": args["n_size"],
            "m_closed": False, "n_closed": False,
            "vertices": vertices,
        },
    }


def _expect_create_polyfacemesh(args: Dict[str, Any]) -> Dict[str, Any]:
    # w3-pfmesh: write.entity.polyfacemesh (m08g_handlers.inc) builds a
    # genuine AcDbPolyFaceMesh: appendVertex() once per "points"/"vertices"
    # arg entry (plain [x,y,z] position, no bulge -- same vertex shape
    # create_polygonmesh/create_polyline3d/create_mleader already use) THEN
    # appendFaceRecord() exactly ONCE, with vertex indices HARDCODED to
    # {1, 2, 3, len>=4?4:3} -- a deterministic FUNCTION of vertex count, not
    # an independent "faces" arg (the handler never reads one at all, the
    # same "handler ignores an arg it never reads" shape create_polygonmesh's
    # m_closed/n_closed already documented).
    #
    # collectModelSpaceGraph's AcDbPolyFaceMesh branch discriminates the SAME
    # vertexIterator()'s mixed AcDbPolyFaceMeshVertex/AcDbFaceRecord
    # sub-entities by cast(), so iteration order matches append order
    # (live-verified 2026-07-02 w3-pfmesh re-cert on a 4-vertex quad -- an
    # index/order mismatch would have been visible as a geometry-diff
    # mismatch, and was not).
    raw_points = args.get("points") or args.get("vertices") or []
    vertices = [{"point": _point_to_list(p)} for p in raw_points]
    n = len(vertices)
    face = [1, 2, 3, 4 if n >= 4 else 3]
    return {
        "dxf_name": "POLYLINE", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "poly_face_mesh",
            "vertices": vertices,
            "faces": [face],
        },
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


def _expect_create_face3d(args: Dict[str, Any]) -> Dict[str, Any]:
    # p8-simple2: write.entity.face (m08g_handlers.inc) builds AcDbFace(p0,
    # p1, p2, p3) with all 4 edges visible (the ctor's e0vis..e3vis args
    # default to Adesk::kTrue; the handler never overrides them or reads an
    # "edge_visibility" job field). collectModelSpaceGraph's AcDbFace branch
    # reads getVertexAt(0..3) back verbatim -- no reordering in the reader --
    # so ground truth is a direct pass-through of all 4 points plus the
    # all-true edge_visibility default.
    return {
        "dxf_name": "3DFACE", "layer": args.get("layer") or "0",
        "geometry": {"kind": "face3d",
                    "p0": _point_to_list(args["p0"]), "p1": _point_to_list(args["p1"]),
                    "p2": _point_to_list(args["p2"]), "p3": _point_to_list(args["p3"]),
                    "edge_visibility": [True, True, True, True]},
    }


def _expect_create_solid2d(args: Dict[str, Any]) -> Dict[str, Any]:
    # p8-simple2: write.entity.solid2d (m08g_handlers.inc) builds AcDbSolid
    # (p0, p1, p2, p3); collectModelSpaceGraph's AcDbSolid branch reads
    # getPointAt(0..3) back verbatim (no reordering in the READER). Live-
    # verified 2026-07-05 (p8-simple2 re-cert, staged tests/fixtures/
    # native_sample.dwg, 4 distinct corners p0=(0,0,0) p1=(10,0,0)
    # p2=(10,10,0) p3=(0,10,0), boundary order -- chosen so any 2/3 swap
    # would be immediately visible): getPointAt(0..3) returned p0..p3 in
    # the EXACT SAME order they were constructed with -- no "bow-tie"
    # storage-order swap measured. (AutoCAD's own SOLID/TRACE bow-tie
    # convention, where a boundary-ordered quad renders as two crossed
    # triangles unless points 3/4 are supplied pre-swapped, is a DRAWING/
    # tessellation detail of how the two triangles (0,1,2)+(1,3,2) are
    # filled -- not a storage transform ObjectARX applies to what you
    # pass the ctor.) Also live-verified: the triangular case (job p2==p3)
    # round-trips as a plain duplicate, no special-casing needed. Ground
    # truth is therefore a direct args pass-through.
    return {
        "dxf_name": "SOLID", "layer": args.get("layer") or "0",
        "geometry": {"kind": "solid",
                    "p0": _point_to_list(args["p0"]), "p1": _point_to_list(args["p1"]),
                    "p2": _point_to_list(args["p2"]), "p3": _point_to_list(args["p3"])},
    }


def _expect_create_trace(args: Dict[str, Any]) -> Dict[str, Any]:
    # p8-simple2: write.entity.trace (m08g_handlers.inc) builds AcDbTrace(p0,
    # p1, p2, p3); collectModelSpaceGraph's AcDbTrace branch reads
    # getPointAt(0..3) back verbatim. Same live-verified (2026-07-05,
    # p8-simple2 re-cert) plain pass-through convention as create_solid2d
    # above -- see that function's comment; AcDbTrace's getPointAt showed
    # the identical no-swap, no-reordering behavior on the same fixture.
    return {
        "dxf_name": "TRACE", "layer": args.get("layer") or "0",
        "geometry": {"kind": "trace",
                    "p0": _point_to_list(args["p0"]), "p1": _point_to_list(args["p1"]),
                    "p2": _point_to_list(args["p2"]), "p3": _point_to_list(args["p3"])},
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


def _expect_create_dimension_radiallarge(args: Dict[str, Any]) -> Dict[str, Any]:
    # AcDbRadialDimensionLarge(center, chordPoint, overrideCenter, jogPoint,
    # jogAngle, dimText, dimStyle) -- write.entity.dim.radiallarge
    # (m08h_handlers.inc) passes all 5 geometry args straight to the ctor.
    # center/chord_point carry the SAME "true center of the dimensioned arc" /
    # "point on that arc" semantic AcDbRadialDimension already has, so
    # measurement (the dimensioned radius) is computed identically:
    # independently, as the center<->chord_point distance (never a live
    # read), exactly like _expect_create_dimension_radial above.
    # override_center/jog_point/jog_angle are asserted as direct, verbatim
    # ctor-arg echoes (live-verified 2026-07-02 w3-radl re-cert) -- UNLIKE
    # AcDbArcDimension/AcDb2LineAngularDimension/AcDb3PointAngularDimension's
    # own placement-only arc_point, AutoCAD does NOT re-anchor any of this
    # class's 3 jog-symbol args: they are independent stored fields (each has
    # its own plain setCenter/setChordPoint/setOverrideCenter/setJogPoint/
    # setJogAngle -- the ObjectARX header's cross-updating "PP" variants
    # (setOverrideCenterPP/setJogPointPP) are documented as "used exclusively
    # by property palette", i.e. NOT invoked by the plain ctor this handler
    # calls).
    center = _point_to_list(args["center"])
    chord = _point_to_list(args["chord_point"])
    override_center = _point_to_list(args["override_center"])
    jog_point = _point_to_list(args["jog_point"])
    jog_angle = args.get("jog_angle", 0.785398163397448)  # handler default: 45deg
    dx, dy, dz = chord[0] - center[0], chord[1] - center[1], chord[2] - center[2]
    measurement = math.sqrt(dx * dx + dy * dy + dz * dz)
    return {
        "dxf_name": "DIMENSION", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "dimension",
            "center": center, "chord_point": chord,
            "override_center": override_center, "jog_point": jog_point,
            "jog_angle": jog_angle,
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


def _arc_dimension_signed_span(center: list, p1: list, p2: list, arc_point: list):
    """Shared geometry for AcDbArcDimension's two derived fields: the radius
    (center<->xLine1Point distance), xLine1Point's own angle ``a1``, and the
    SIGNED angular span from ``a1`` to xLine2Point's angle, resolved to
    whichever rotational direction (CCW, positive, or CW, negative) the input
    ``arc_point`` arg actually lies in. Returns ``(radius, a1, signed_span)``.
    """
    radius = math.hypot(p1[0] - center[0], p1[1] - center[1])
    a1 = math.atan2(p1[1] - center[1], p1[0] - center[0])
    a2 = math.atan2(p2[1] - center[1], p2[0] - center[0])
    a_arc = math.atan2(arc_point[1] - center[1], arc_point[0] - center[0])
    span_ccw = (a2 - a1) % (2 * math.pi)
    arc_ccw = (a_arc - a1) % (2 * math.pi)
    signed_span = span_ccw if arc_ccw <= span_ccw else -(2 * math.pi - span_ccw)
    return radius, a1, signed_span


def _arc_dimension_measurement(center: list, p1: list, p2: list, arc_point: list) -> float:
    """AcDbArcDimension's measurement: an ARC LENGTH -- radius times the
    absolute angular span from xLine1Point to xLine2Point (see
    _arc_dimension_signed_span). Independently computed (not an arg) so
    ``_expect_create_dimension_arc`` can assert it without a live read.
    """
    radius, _a1, signed_span = _arc_dimension_signed_span(center, p1, p2, arc_point)
    return radius * abs(signed_span)


def _arc_dimension_arc_point(center: list, p1: list, p2: list, arc_point: list) -> list:
    """AcDbArcDimension does NOT store the raw ``arc_point`` ctor arg back
    verbatim -- live-verified (2026-07-02 w3-dimarc re-cert, 3 real
    accoreconsole roundtrips against tests/fixtures/native_sample.dwg, each
    with a DIFFERENT center/radius/span AND a different input arc_point
    position within the span -- one at the angular midpoint, one at the
    midpoint again on a rotated/differently-sized arc, one at 90% of the way
    to xLine2Point): AutoCAD discards the input arcPoint's own position
    entirely and re-places it at EXACTLY 1/3 of the xLine1Point->xLine2Point
    angular span (same radius as xLine1Point from centerPoint), measured from
    xLine1Point in whichever rotational direction the input arc_point arg
    resolves the span to (see _arc_dimension_signed_span) -- confirmed exact
    to float precision in all 3 cases (e.g. center=(0,0,0),
    xline1=(50,0,0) [0 deg], xline2=(0,50,0) [90 deg], input arc_point at 45
    deg -> stored arc_point at EXACTLY 30 deg = 0 + 90/3, not 45).

    All 3 verification cases had the input arc_point on the SAME (CCW-from-
    xLine1) side as the resolved short span, with that span < 180 degrees --
    this ground truth is only asserted for that case; an input arc_point on
    the opposite (reflex/major-arc) side, or a span >= 180 degrees, is
    unverified, out of scope (same caveat T3a's rotated-dimension
    dim_line_point formula carries for a non-parallel baseline).
    """
    radius, a1, signed_span = _arc_dimension_signed_span(center, p1, p2, arc_point)
    third_angle = a1 + signed_span / 3.0
    cz = center[2] if len(center) > 2 else 0.0
    return [center[0] + radius * math.cos(third_angle),
            center[1] + radius * math.sin(third_angle), cz]


def _expect_create_dimension_arc(args: Dict[str, Any]) -> Dict[str, Any]:
    # AcDbArcDimension(centerPoint, xLine1Point, xLine2Point, arcPoint,
    # dimText, dimStyle) -- write.entity.dim.arc (m08h_handlers.inc) passes
    # center/xline1/xline2/arc_point straight to the ctor. center/xline1_point/
    # xline2_point are direct, args-derivable ground truth (live-verified
    # 2026-07-02 w3-dimarc re-cert). arc_point and measurement are NOT verbatim
    # ctor-arg echoes -- both independently computed via
    # _arc_dimension_arc_point / _arc_dimension_measurement (see their
    # docstrings for the live-discovered formulas and verified scope).
    center = _point_to_list(args["center"])
    xline1 = _point_to_list(args["xline1"])
    xline2 = _point_to_list(args["xline2"])
    arc_point_arg = _point_to_list(args["arc_point"])
    return {
        "dxf_name": "DIMENSION", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "dimension",
            "center": center, "xline1_point": xline1, "xline2_point": xline2,
            "arc_point": _arc_dimension_arc_point(center, xline1, xline2, arc_point_arg),
            "measurement": _arc_dimension_measurement(center, xline1, xline2, arc_point_arg),
        },
    }


def _angular2line_line_intersect(l1s: list, l1e: list, l2s: list, l2e: list):
    """2D intersection of the INFINITE lines through (l1s,l1e) and (l2s,l2e)
    -- the implicit "apex" AcDb2LineAngularDimension's arc is drawn around.
    Neither line's own start/end points are that apex in general (this
    batch's own valid-arg fixture deliberately keeps both segments OFFSET
    from it, exactly like a real "dimension the corner between two walls"
    usage where neither wall's endpoint sits at the corner). Undefined for
    parallel lines (d==0) -- out of scope, same class of caveat every prior
    T3a/w3 dimension formula carries for its own degenerate case.
    """
    x1, y1 = l1s[0], l1s[1]; x2, y2 = l1e[0], l1e[1]
    x3, y3 = l2s[0], l2s[1]; x4, y4 = l2e[0], l2e[1]
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / d
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / d
    return [px, py]


def _angular2line_sector(l1s: list, l1e: list, l2s: list, l2e: list, arc_point: list):
    """Shared geometry for AcDb2LineAngularDimension's two derived fields.

    Two (infinite) lines through a common apex split the plane into 4
    sectors, bounded by the 4 rays {a1, a2, a1+pi, a2+pi} where a1/a2 are
    xLine1's/xLine2's OWN direction angles (end-start, i.e. which way each
    input segment points AWAY from the apex -- verified only for that
    direction convention, see module-level caveat below). Sorting those 4
    rays CCW gives 4 sectors of widths (span, pi-span, span, pi-span) for
    some 0 < span <= pi. The input ``arc_point`` arg's OWN angle (relative to
    the apex) selects exactly one of those 4 sectors -- LIVE-VERIFIED
    (2026-07-02 w3-ang2 cert, 4 real accoreconsole roundtrips against
    tests/fixtures/native_sample.dwg: 2 different apex points, 2 different
    xLine1/xLine2 angle pairs (0/50deg and 170/310deg -- the second
    deliberately chosen so the 4 sorted sector boundaries are NOT already
    ray-a1-first, unlike the first pair), arc_point tried at 3 different
    within-sector angles and 2 different radii at the same angle) that:
      - "measurement" is EXACTLY that selected sector's angular width, and
      - the stored "arc_point" (see _angular2line_arc_point) sits at EXACTLY
        1/3 of that sector's span from its start boundary, at a radius
        EXACTLY equal to the input arc_point's own distance from the apex --
        the same 1/3-of-selected-span rule w3-dimarc discovered for
        AcDbArcDimension.arcPoint(), now confirmed on a structurally
        different class (2 independent lines, not one arc's 2 xLine points
        sharing a literal centerPoint arg). All 4 cases matched to float
        precision (max observed error ~1e-14).

    Returns ``(apex, sector_start, sector_span)`` (angles in radians).
    """
    apex = _angular2line_line_intersect(l1s, l1e, l2s, l2e)
    a1 = math.atan2(l1e[1] - l1s[1], l1e[0] - l1s[0]) % (2 * math.pi)
    a2 = math.atan2(l2e[1] - l2s[1], l2e[0] - l2s[0]) % (2 * math.pi)
    bounds = sorted([a1, a2, (a1 + math.pi) % (2 * math.pi), (a2 + math.pi) % (2 * math.pi)])
    # Unwrap into [bounds[0], bounds[0]+2*pi) so the 4 sector widths are all
    # positive without any modular wraparound arithmetic.
    unwrapped = [bounds[0]] + [b + (2 * math.pi if b < bounds[0] else 0.0) for b in bounds[1:]]
    unwrapped.append(bounds[0] + 2 * math.pi)
    a_in = math.atan2(arc_point[1] - apex[1], arc_point[0] - apex[0]) % (2 * math.pi)
    a_in_unwrapped = a_in + (2 * math.pi if a_in < unwrapped[0] else 0.0)
    for i in range(4):
        if unwrapped[i] <= a_in_unwrapped <= unwrapped[i + 1]:
            return apex, unwrapped[i], unwrapped[i + 1] - unwrapped[i]
    # arc_point exactly on a boundary ray (measure-zero input) -- unreached
    # by this batch's fixture; not asserted for that edge case.
    raise ValueError("arc_point angle did not resolve to any of the 4 sectors")


def _angular2line_measurement(l1s: list, l1e: list, l2s: list, l2e: list, arc_point: list) -> float:
    """AcDb2LineAngularDimension's measurement: the angular width (radians)
    of whichever of the 4 apex sectors the input arc_point arg selects (see
    _angular2line_sector). Independently computed (not an arg) so
    ``_expect_create_dimension_angular2line`` can assert it without a live
    read.
    """
    _apex, _start, span = _angular2line_sector(l1s, l1e, l2s, l2e, arc_point)
    return span


def _angular2line_arc_point(l1s: list, l1e: list, l2s: list, l2e: list, arc_point: list) -> list:
    """AcDb2LineAngularDimension does NOT store the raw ``arc_point`` ctor
    arg back verbatim -- see _angular2line_sector's docstring for the
    live-verified 1/3-of-selected-sector-span rule (radius preserved from
    the input arc_point's own distance to the apex; angle re-anchored).
    """
    apex, start, span = _angular2line_sector(l1s, l1e, l2s, l2e, arc_point)
    third_angle = start + span / 3.0
    radius = math.hypot(arc_point[0] - apex[0], arc_point[1] - apex[1])
    az = arc_point[2] if len(arc_point) > 2 else 0.0
    return [apex[0] + radius * math.cos(third_angle), apex[1] + radius * math.sin(third_angle), az]


def _expect_create_dimension_angular2line(args: Dict[str, Any]) -> Dict[str, Any]:
    # AcDb2LineAngularDimension(xLine1Start, xLine1End, xLine2Start,
    # xLine2End, arcPoint, dimText, dimStyle) -- write.entity.dim.angular2line
    # (m08h_handlers.inc) passes xline1_start/xline1_end/xline2_start/
    # xline2_end/arc_point straight to the ctor. The 4 line-endpoint args are
    # direct, args-derivable ground truth (live-verified 2026-07-02 w3-ang2
    # re-cert, identical across all 4 cases regardless of arc_point). arc_point
    # and measurement are NOT verbatim ctor-arg echoes -- both independently
    # computed via _angular2line_arc_point / _angular2line_measurement (see
    # _angular2line_sector's docstring for the live-discovered formula and its
    # verified scope: non-parallel xLine1/xLine2 only, and only for the
    # "segment direction points away from the apex" convention this batch's
    # own fixture used).
    l1s = _point_to_list(args["xline1_start"])
    l1e = _point_to_list(args["xline1_end"])
    l2s = _point_to_list(args["xline2_start"])
    l2e = _point_to_list(args["xline2_end"])
    arc_point_arg = _point_to_list(args["arc_point"])
    return {
        "dxf_name": "DIMENSION", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "dimension",
            "xline1_start": l1s, "xline1_end": l1e,
            "xline2_start": l2s, "xline2_end": l2e,
            "arc_point": _angular2line_arc_point(l1s, l1e, l2s, l2e, arc_point_arg),
            "measurement": _angular2line_measurement(l1s, l1e, l2s, l2e, arc_point_arg),
        },
    }


def _angular3pt_measurement(center: list, p1: list, p2: list, arc_point: list) -> float:
    """AcDb3PointAngularDimension's measurement: the plain ANGULAR width
    (radians) of the xLine1Point->xLine2Point span as seen from centerPoint --
    UNLIKE AcDbArcDimension (an ARC-LENGTH dimension: measurement = radius *
    angular span), this is a plain angle, the SAME semantic
    AcDb2LineAngularDimension.measurement() has. Independently computed (not
    an arg) so ``_expect_create_dimension_angular3pt`` can assert it without a
    live read. Reuses _arc_dimension_signed_span's direction-resolution logic
    (the input arc_point's own angle picks which of the two complementary
    spans is "the" span) -- see that function's docstring for the shared
    caveat (only verified for an input arc_point on the same CCW-from-xLine1
    side as the resolved short span, with that span < 180 degrees).
    """
    _radius, _a1, signed_span = _arc_dimension_signed_span(center, p1, p2, arc_point)
    return abs(signed_span)


def _angular3pt_arc_point(center: list, p1: list, p2: list, arc_point: list) -> list:
    """AcDb3PointAngularDimension does NOT store the raw ``arc_point`` ctor
    arg back verbatim -- LIVE-VERIFIED (2026-07-02 w3-ang3 re-cert, 3 real
    accoreconsole roundtrips against tests/fixtures/native_sample.dwg, 3
    different center/xLine-radius/span combinations, the 2nd and 3rd
    DELIBERATELY giving the input arc_point a DIFFERENT distance from center
    than xLine1Point/xLine2Point have) that AutoCAD re-places arcPoint's ANGLE
    at exactly 1/3 of the xLine1Point->xLine2Point angular span (same
    direction-resolution as _arc_dimension_signed_span/_arc_dimension_
    arc_point), but preserves the RADIUS as the INPUT arc_point's OWN distance
    from centerPoint -- NOT xLine1Point's distance from centerPoint, which is
    what AcDbArcDimension.arcPoint() uses (_arc_dimension_arc_point). This is
    the SAME radius rule AcDb2LineAngularDimension.arcPoint() uses
    (_angular2line_arc_point preserves the input arc_point's own distance from
    the apex) -- i.e. angular3pt's arc_point re-anchoring is a hybrid: angle
    rule shared with AcDbArcDimension, radius rule shared with
    AcDb2LineAngularDimension. (case 1 of the 3 live cases used an input
    arc_point at the SAME radius as xLine1Point by construction -- 50 both --
    so it could not by itself distinguish the two radius rules; cases 2/3
    deliberately used a different radius (18 and 25 respectively, vs xLine1's
    30/40) and matched ONLY the "input arc_point's own radius" rule, to float
    precision, max observed error ~2e-15.)
    """
    _radius, a1, signed_span = _arc_dimension_signed_span(center, p1, p2, arc_point)
    third_angle = a1 + signed_span / 3.0
    own_radius = math.hypot(arc_point[0] - center[0], arc_point[1] - center[1])
    cz = center[2] if len(center) > 2 else 0.0
    return [center[0] + own_radius * math.cos(third_angle),
            center[1] + own_radius * math.sin(third_angle), cz]


def _expect_create_dimension_angular3pt(args: Dict[str, Any]) -> Dict[str, Any]:
    # AcDb3PointAngularDimension(centerPoint, xLine1Point, xLine2Point,
    # arcPoint, dimText, dimStyle) -- write.entity.dim.angular3pt
    # (m08h_handlers.inc) passes center/xline1/xline2/arc_point straight to the
    # ctor -- an IDENTICAL ctor-arg shape to write.entity.dim.arc.
    # center/xline1_point/xline2_point are direct, args-derivable ground truth
    # (live-verified 2026-07-02 w3-ang3 re-cert). arc_point is NOT a verbatim
    # ctor-arg echo -- see _angular3pt_arc_point's docstring for the
    # live-discovered hybrid formula (angle rule shared with
    # AcDbArcDimension, radius rule shared with AcDb2LineAngularDimension) and
    # its verified scope. measurement, unlike AcDbArcDimension's arc-length,
    # is the plain angular span -- see _angular3pt_measurement.
    center = _point_to_list(args["center"])
    xline1 = _point_to_list(args["xline1"])
    xline2 = _point_to_list(args["xline2"])
    arc_point_arg = _point_to_list(args["arc_point"])
    return {
        "dxf_name": "DIMENSION", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "dimension",
            "center": center, "xline1_point": xline1, "xline2_point": xline2,
            "arc_point": _angular3pt_arc_point(center, xline1, xline2, arc_point_arg),
            "measurement": _angular3pt_measurement(center, xline1, xline2, arc_point_arg),
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


def _expect_create_mleader(args: Dict[str, Any]) -> Dict[str, Any]:
    # write.entity.mleader (m08h_handlers.inc) reads "vertices" first, falling
    # back to "points" only when "vertices" yields <2 points -- mirrors
    # create_leader's own arg-reading order exactly. Each vertex is a direct,
    # args-derivable echo (addFirstVertex once + addLastVertex per remaining
    # point, no transform -- same shape as create_leader's appendVertex loop).
    # text/height are both required explicit args here, same convention
    # create_text/create_mtext use (ground truth requires them explicitly
    # rather than modeling m08h's own "MLeader"/2.5 defaults for the
    # absent-arg case).
    #
    # Emitted vertices reuse the SAME plain-[x,y,z]-array shape create_leader/
    # create_mline already use (AriadneNativeJob.cpp's AcDbMLeader branch), so
    # ir_builder.py's existing generic "vertices" lift needed zero changes;
    # its _NATIVE_CLASS_TO_DXF_KIND already had an AcDbMLeader entry from an
    # earlier batch.
    vertices_arg = args.get("vertices") or args.get("points") or []
    vertices = [{"point": _point_to_list(p)} for p in vertices_arg]
    return {
        "dxf_name": "MULTILEADER", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "leader",
            "vertices": vertices, "text": args["text"], "height": args["height"],
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


def _expect_create_blockref(args: Dict[str, Any]) -> Dict[str, Any]:
    # w3-insert: write.entity.blockref (m08g_handlers.inc) builds a real
    # AcDbBlockReference(position, blockId) then -- as of this batch's fix --
    # also calls setScaleFactors/setRotation from "scale"/"rotation" args
    # (previously silently dropped; see test_patch_ops_split.py's module
    # docstring). block_name is NOT an independent ctor-arg echo: it is a
    # block-table LOOKUP BY NAME (blockTableRecord()->getName() on read), so
    # this ground truth only holds when "block_name" resolves to a real
    # pre-existing block definition in the target DWG -- callers are
    # responsible for that precondition, this builder does not create one.
    # scale/rotation default to the AcDbBlockReference ctor defaults (1,1,1
    # / 0.0) when
    # omitted, matching m08gPoint/jsonFindNumber's own defaults in the
    # handler -- live-verified 2026-07-02 w3-insert cert (diff=0 for all
    # four fields against a real accoreconsole roundtrip).
    scale_arg = args.get("scale")
    scale = _point_to_list(scale_arg) if scale_arg is not None else [1.0, 1.0, 1.0]
    return {
        "dxf_name": "INSERT", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "block_reference",
            "position": _point_to_list(args["position"]),
            "scale": scale,
            "rotation": args.get("rotation", 0.0),
            "block_name": args["block_name"],
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
#
# w3-dimarc adds create_dimension_arc: same two-part gap as every T3a-batch
# dimension subtype (already native-REACHABLE per measure/reachable_matrix.
# jsonl, but no patch_ops wiring and no collectModelSpaceGraph read branch
# until this batch).
#
# w3-ang2 adds create_dimension_angular2line: same two-part gap as every
# T3a-batch/w3-dimarc dimension subtype (already native-REACHABLE per
# measure/reachable_matrix.jsonl, but no patch_ops wiring and no
# collectModelSpaceGraph read branch until this batch).
#
# w3-ang3 adds create_dimension_angular3pt: same two-part gap as every
# T3a-batch/w3-dimarc/w3-ang2 dimension subtype (already native-REACHABLE per
# measure/reachable_matrix.jsonl, but no patch_ops wiring and no
# collectModelSpaceGraph read branch until this batch).
#
# w3-mleader adds create_mleader: same two-part gap as create_leader before
# it (already native-REACHABLE per measure/reachable_matrix.jsonl, but no
# patch_ops wiring and no collectModelSpaceGraph read branch until this
# batch).
#
# w3-poly2d adds create_polyline2d: already native-REACHABLE per measure/
# reachable_matrix.jsonl, but no patch_ops wiring -- UNLIKE every op above,
# it needed NO NEW collectModelSpaceGraph read branch at all (polyline2d
# aliases the already-read AcDbPolyline path).
#
# w3-poly3d adds create_polyline3d: already native-REACHABLE per measure/
# reachable_matrix.jsonl, but no patch_ops wiring -- like w3-poly2d, needed
# NO NEW collectModelSpaceGraph read branch (AcDb3dPolyline's own branch
# pre-dates any wired create op for it).
#
# w3-pmesh adds create_polygonmesh: already native-REACHABLE (measure/
# reachable_matrix.jsonl: registry_status=implemented, class=REACHABLE from
# its empty-arg probe) but had NEITHER patch_ops wiring NOR a
# collectModelSpaceGraph read branch at all (unlike every polyline/dimension/
# leader kind above, AcDbPolygonMesh had never been read before this batch).
# A live create-only probe (direct patch_engine.apply_staged call, no
# expected-ir builder yet) confirmed a real, non-attended-only entity first
# (net modelspace +1, class=AcDbPolygonMesh, original DWG byte-identical)
# BEFORE the read branch + rebuild were invested in -- ruling out the
# raster/wipeout/mpolygon demand-loaded-module failure mode this ticket
# flagged as the risk to check for.
#
# w3-pfmesh adds create_polyfacemesh: already native-REACHABLE (measure/
# reachable_matrix.jsonl: registry_status=implemented, class=REACHABLE from
# its empty-arg probe) but had NEITHER patch_ops wiring NOR a
# collectModelSpaceGraph read branch at all (same two-part gap as w3-pmesh
# just above -- AcDbPolyFaceMesh had never been read before this batch,
# unlike AcDbPolygonMesh/AcDb3dPolyline's read branches, which pre-date any
# wired create op for them). The SAME de-risking discipline was applied
# first: a live create-only probe (direct patch_engine.apply_staged call, no
# expected-ir builder yet) confirmed a real, non-attended-only entity (net
# modelspace +1, class=AcDbPolyFaceMesh, original DWG byte-identical) BEFORE
# the read branch + rebuild were invested in.
#
# w3-radl adds create_dimension_radiallarge: the m08h_handlers.inc write
# handler already existed (core dbdim.h, same acdb import lib as every other
# dimension subtype -- no demand-loaded engine), but had NEITHER patch_ops
# wiring NOR a collectModelSpaceGraph read branch at all (same two-part gap
# as w3-pmesh/w3-pfmesh). The SAME de-risking discipline was applied first: a
# live create-only probe (direct patch_engine.apply_staged call, no
# expected-ir builder yet) confirmed a real, non-attended-only entity (net
# modelspace +1, class=AcDbRadialDimensionLarge, original DWG byte-identical)
# BEFORE the read branch + rebuild were invested in.
#
# w3-insert adds create_blockref (AcDbBlockReference/INSERT -- the BLOCK/
# INSERT tier's foundation, and the single most common entity in production
# DWGs): UNLIKE every op above, this one already had a real m08g_handlers.inc
# write handler AND a collectModelSpaceGraph read branch (position/scale/
# rotation/block_name/block_record_handle) BEFORE this batch -- no two-part
# gap. The real gap was that the write handler read "name"/"position" but
# never applied "scale"/"rotation" (silently dropped -- a live create-only
# probe against a real block definition confirmed net modelspace +1,
# class=AcDbBlockReference, original DWG byte-identical, but scale/rotation
# read back as the ctor default 1/1/1 and 0.0 regardless of the arg, even
# though the operation_registry's own native_api note already listed
# setScaleFactors/setRotation as intended). Fixed in the same handler (see
# m08g_handlers.inc) before this builder was written, so all four fields
# below are asserted as REAL, live-verified ctor-arg echoes, not aspirational
# ones. Also unlike every op above: native_sample.dwg's 245 real block
# definitions are ALL non-ASCII (Korean) names, and at the time of this batch
# the write handler resolved "name" via asciiToWide (naive byte-widening, not
# UTF-8 decode), so none of them resolved correctly through this op. The cert
# below uses a fresh ASCII block definition created via the already-
# implemented write.block.simple_create op instead (see runs/w3_insert_probe)
# -- the non-ASCII block_name lookup gap was a real, separate, pre-existing
# limitation this batch did NOT fix (asciiToWide was shared by other
# symbol-table name lookups outside this op's scope -- see m08c_handlers.inc).
#
# w3-utf8 FIXES the non-ASCII block_name lookup gap noted just above:
# asciiToWide (AriadneNativeJob.cpp) was a naive per-byte widen, not a UTF-8
# decode, so a Korean block/layer/dict-key/regapp/layout name from the JSON
# job never matched the real UTF-16 symbol-table record. It now delegates to
# the already-existing utf8ToWide helper (same file, previously only used for
# the ARIADNE_NATIVE_JOB_ARGS path channel) -- ASCII input is a strict subset
# of UTF-8 so every existing ASCII call site is byte-identical, no call site
# needed to change. Live-verified (staged copies of this fixture, original
# READ-ONLY, codepoint-exact comparisons, never console glyphs):
#   - a freshly created Korean block-def ("테스트블록") round-trips through
#     write.block.simple_create -> create_blockref (INSERT) diff=0;
#   - a freshly created Korean layer ("테스트레이어") round-trips through
#     create_layer -> create_line -> re-extraction diff=0;
#   - a REAL pre-existing Korean block from this fixture's block table (one
#     of the 245 -- all 245 are Korean-named) now resolves via
#     write.entity.blockref, where it previously could not;
#   - the ASCII cert below (and create_line/create_circle) are unchanged,
#     diff=0.
_EXPECTED_ENTITY_BUILDERS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "create_line": _expect_create_line,
    "create_circle": _expect_create_circle,
    "create_arc": _expect_create_arc,
    "create_ellipse": _expect_create_ellipse,
    "create_text": _expect_create_text,
    "create_mtext": _expect_create_mtext,
    "create_polyline": _expect_create_polyline,
    "create_polyline2d": _expect_create_polyline2d,
    "create_polyline3d": _expect_create_polyline3d,
    "create_polygonmesh": _expect_create_polygonmesh,
    "create_polyfacemesh": _expect_create_polyfacemesh,
    "create_dimension": _expect_create_dimension,
    "create_spline": _expect_create_spline,
    "create_dimension_aligned": _expect_create_dimension_aligned,
    "create_dimension_radial": _expect_create_dimension_radial,
    "create_dimension_diametric": _expect_create_dimension_diametric,
    "create_dimension_radiallarge": _expect_create_dimension_radiallarge,
    "create_dimension_ordinate": _expect_create_dimension_ordinate,
    "create_leader": _expect_create_leader,
    "create_mline": _expect_create_mline,
    "create_dimension_arc": _expect_create_dimension_arc,
    "create_dimension_angular2line": _expect_create_dimension_angular2line,
    "create_dimension_angular3pt": _expect_create_dimension_angular3pt,
    "create_mleader": _expect_create_mleader,
    "create_blockref": _expect_create_blockref,
    "create_face3d": _expect_create_face3d,
    "create_solid2d": _expect_create_solid2d,
    "create_trace": _expect_create_trace,
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

def _build_patch(op_name: str, args: Dict[str, Any], dwg_path: str, out_dir: str, *,
                 postconditions: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    # target_dwg is REQUIRED by schemas/cad_patch.v1.schema.json (staged_path
    # distinct from original_path). apply_staged's own create_staged_copy(dwg_path,
    # out_dir) always writes to <out_dir>/staged_input.dwg regardless of this
    # declared value (it does not read target_dwg to decide where to stage) --
    # so this is the TRUE path, not a placeholder, kept honest with what
    # create_staged_copy actually produces moments later.
    #
    # postconditions defaults to the entity P-gate's "one new entity" shape;
    # callers whose op doesn't add an entity (e.g. the TABLES-tier
    # create_layer probe below, which adds a symbol_tables.layers[] record,
    # not an entities[] one) pass an accurate override instead of inheriting
    # a postcondition that would silently assert the wrong thing.
    return {
        "schema": "ariadne.cad_patch.v1",
        "patch_id": "op_roundtrip_probe/%s" % op_name,
        "target_dwg": {
            "original_path": os.path.abspath(dwg_path),
            "staged_path": os.path.join(out_dir, "staged_input.dwg"),
        },
        "operations": [{"step_id": "s1", "operation": op_name, "args": args}],
        "postconditions": (postconditions if postconditions is not None
                           else [{"subject": "entity_count", "op": "delta_eq", "value": 1}]),
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
# TABLES tier (w3-tables, D-class): layer table RECORD-diff driver.
#
# symbol_tables.layers[] is not an entity: no handle join through cad_diff, no
# geometry/bbox, joined by NAME instead (a layer's name is its own unique
# key). cad_op_gate.check_roundtrip/check_mutation_pair are entity-shaped
# (cad_diff.compute_diff's join is entities[]-by-handle) so they don't apply
# here -- this is a sibling, record-level P-/D-gate reusing apply_staged (the
# real staged write + re-extract) but judging with a flat per-field compare
# instead of cad_diff's geometry-aware one. Status/exit-code vocabulary is
# still cad_op_gate's (STATUS_OK/STATUS_FAIL/... EXIT_OK/EXIT_FAIL/...) so a
# caller of both drivers sees one consistent PASS/FAIL shape.
# --------------------------------------------------------------------------- #

#: fields write.layer.create can set (AriadneNativeJob.cpp's
#: LayerPropertyArgs/applyLayerProperties) AND layersRichJson extracts back --
#: the record-diff's comparable field set. true_color/is_xref_dependent/handle/
#: name are read-only or not yet write-wired, so they're out of scope here.
LAYER_RECORD_FIELDS = ("color_index", "linetype", "lineweight",
                       "plottable", "frozen", "off", "locked")


def _layer_by_name(ir: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    """Find a symbol_tables.layers[] record by name -- the layer table's own
    join key (unique within a database), unlike an entity handle which is
    assigned by the engine rather than asserted by the caller."""
    for rec in ((ir.get("symbol_tables") or {}).get("layers") or []):
        if isinstance(rec, dict) and rec.get("name") == name:
            return rec
    return None


def expected_layer_record(args: Dict[str, Any]) -> Dict[str, Any]:
    """Ground truth = the op's OWN args (never a live read): every
    LAYER_RECORD_FIELDS key present in ``args`` is asserted verbatim."""
    return {k: args[k] for k in LAYER_RECORD_FIELDS if k in args}


def layer_record_diff(expected: Dict[str, Any],
                      actual: Optional[Dict[str, Any]]) -> List[str]:
    """Sorted field names in ``expected`` whose value ``actual`` disagrees
    with (every expected field, if the record was not found at all). An empty
    list is "record-diff=0" -- the PASS shape for both create and update."""
    if actual is None:
        return sorted(expected)
    return sorted(k for k, v in expected.items() if actual.get(k) != v)


def probe_layer_roundtrip(args: Dict[str, Any], dwg_path: str, out_dir: str, *,
                          apply_staged: Optional[Callable[[Dict[str, Any], str, str], Dict[str, Any]]] = None,
                          patch_ops_mod=None, cad_op_gate_mod=None) -> Dict[str, Any]:
    """create_layer -> re-extract -> record-diff against the op's own args.

    Mirrors probe_roundtrip's pipeline and result shape (status/exit_code
    drawn from cad_op_gate) but joins/compares a symbol_tables.layers[]
    record by NAME instead of an entities[] record by handle.
    """
    gate = cad_op_gate_mod if cad_op_gate_mod is not None else _import_optional("cad_op_gate")
    if gate is None:
        return {"schema": SCHEMA_ID, "op_name": "create_layer", "status": "error",
                "exit_code": 2, "reason": "cad_op_gate sibling module unavailable"}

    native_op = resolve_native_op("create_layer", patch_ops_mod=patch_ops_mod)
    if native_op is None:
        return {
            "schema": SCHEMA_ID, "op_name": "create_layer", "status": gate.STATUS_NOT_IMPLEMENTED,
            "exit_code": gate.EXIT_NOT_IMPLEMENTED,
            "reason": "create_layer has no live native write handler wired "
                      "(patch_ops.NATIVE_WRITE_OP_MAP)",
        }

    name = args.get("name")
    if not name:
        return {"schema": SCHEMA_ID, "op_name": "create_layer", "native_op": native_op,
                "status": gate.STATUS_ERROR, "exit_code": gate.EXIT_ERROR,
                "reason": "args['name'] is required"}

    apply_fn = apply_staged
    if apply_fn is None:
        patch_engine = _import_optional("patch_engine")
        apply_fn = getattr(patch_engine, "apply_staged", None) if patch_engine else None
    if apply_fn is None:
        return {
            "schema": SCHEMA_ID, "op_name": "create_layer", "native_op": native_op,
            "status": gate.STATUS_NOT_IMPLEMENTED, "exit_code": gate.EXIT_NOT_IMPLEMENTED,
            "reason": "patch_engine.apply_staged unavailable",
        }

    patch = _build_patch("create_layer", args, dwg_path, out_dir,
                         postconditions=[{"subject": "layer_exists", "op": "exists", "value": name}])
    envelope = apply_fn(patch, dwg_path, out_dir)
    env_status = envelope.get("status")
    if env_status != "ok":
        deferred_reasons = {"not_implemented", "unavailable"}
        exit_code = gate.EXIT_NOT_IMPLEMENTED if env_status in deferred_reasons else gate.EXIT_ERROR
        status = gate.STATUS_NOT_IMPLEMENTED if env_status in deferred_reasons else gate.STATUS_ERROR
        return {
            "schema": SCHEMA_ID, "op_name": "create_layer", "native_op": native_op,
            "status": status, "exit_code": exit_code,
            "reason": envelope.get("reason"), "envelope_status": env_status,
        }

    orig = envelope.get("original_unchanged") or {}
    if orig and orig.get("unchanged") is False:
        return {
            "schema": SCHEMA_ID, "op_name": "create_layer", "native_op": native_op,
            "status": gate.STATUS_ORIGINAL_MUTATED, "exit_code": gate.EXIT_ORIGINAL_MUTATED,
            "reason": "original DWG changed during the live apply -- READ-ONLY invariant violated",
            "original_unchanged": orig,
        }

    post_ir_ref = envelope.get("post_ir")
    if not post_ir_ref:
        return {
            "schema": SCHEMA_ID, "op_name": "create_layer", "native_op": native_op,
            "status": gate.STATUS_ERROR, "exit_code": gate.EXIT_ERROR,
            "reason": "apply_staged envelope reported ok but is missing post_ir",
        }
    post_ir = _load_ir_maybe(post_ir_ref)
    actual = _layer_by_name(post_ir, name)
    expected = expected_layer_record(args)
    diff = layer_record_diff(expected, actual)

    result: Dict[str, Any] = {
        "schema": SCHEMA_ID, "op_name": "create_layer", "native_op": native_op,
        "layer_name": name, "expected": expected, "actual": actual, "record_diff": diff,
        "original_unchanged": orig, "run_dir": out_dir,
        "staged_output": envelope.get("staged_output"),
    }
    if actual is None:
        result.update(status=gate.STATUS_HOLLOW, exit_code=gate.EXIT_HOLLOW,
                      reason="layer %r not found in symbol_tables.layers[] after the write" % name)
    elif diff:
        result.update(status=gate.STATUS_FAIL, exit_code=gate.EXIT_FAIL,
                      reason="record-diff is non-zero: field(s) %s do not match what was written"
                             % diff)
    else:
        result.update(status=gate.STATUS_OK, exit_code=gate.EXIT_OK)
    return result


def probe_layer_mutation(name: str, baseline_args: Dict[str, Any], change_args: Dict[str, Any],
                         dwg_path: str, out_dir: str, *,
                         apply_staged: Optional[Callable[[Dict[str, Any], str, str], Dict[str, Any]]] = None,
                         patch_ops_mod=None, cad_op_gate_mod=None) -> Dict[str, Any]:
    """The D-gate's 'changing color_index -> 1 modified' contract, at the
    layer-record level: two sequential create_layer writes chained through
    the SAME staged-copy lineage -- step 1 creates ``name`` with
    baseline_args, step 2 re-applies create_layer with ONLY change_args onto
    step 1's own staged_output (never the original dwg_path again). The
    resulting (pre=after-step-1, post=after-step-2) pair must show exactly
    change_args' keys as changed -- nothing else moved (replace-not-inject at
    the field level, mirrors cad_op_gate.check_mutation_pair's identity/
    exactly-one-field checks, just without an entity handle to key on).
    """
    gate = cad_op_gate_mod if cad_op_gate_mod is not None else _import_optional("cad_op_gate")
    if gate is None:
        return {"schema": SCHEMA_ID, "op_name": "create_layer", "status": "error",
                "exit_code": 2, "reason": "cad_op_gate sibling module unavailable"}

    out_dir1 = os.path.join(out_dir, "step1_baseline")
    step1 = probe_layer_roundtrip(dict(baseline_args, name=name), dwg_path, out_dir1,
                                  apply_staged=apply_staged, patch_ops_mod=patch_ops_mod,
                                  cad_op_gate_mod=gate)
    if step1["status"] != gate.STATUS_OK:
        step1["reason"] = "baseline step failed: %s" % step1.get("reason")
        return step1
    staged_after_1 = step1.get("staged_output")
    if not staged_after_1:
        return {"schema": SCHEMA_ID, "op_name": "create_layer", "status": gate.STATUS_ERROR,
                "exit_code": gate.EXIT_ERROR, "reason": "baseline step produced no staged_output"}

    apply_fn = apply_staged
    if apply_fn is None:
        patch_engine = _import_optional("patch_engine")
        apply_fn = getattr(patch_engine, "apply_staged", None) if patch_engine else None
    if apply_fn is None:
        return {"schema": SCHEMA_ID, "op_name": "create_layer", "status": gate.STATUS_NOT_IMPLEMENTED,
                "exit_code": gate.EXIT_NOT_IMPLEMENTED, "reason": "patch_engine.apply_staged unavailable"}
    native_op = resolve_native_op("create_layer", patch_ops_mod=patch_ops_mod)

    out_dir2 = os.path.join(out_dir, "step2_change")
    change_full_args = dict(change_args, name=name)
    patch2 = _build_patch("create_layer", change_full_args, staged_after_1, out_dir2,
                          postconditions=[{"subject": "layer_exists", "op": "exists", "value": name}])
    envelope2 = apply_fn(patch2, staged_after_1, out_dir2)
    if envelope2.get("status") != "ok":
        return {
            "schema": SCHEMA_ID, "op_name": "create_layer", "native_op": native_op,
            "status": gate.STATUS_ERROR, "exit_code": gate.EXIT_ERROR,
            "reason": "mutation step failed: %s" % envelope2.get("reason"),
            "envelope_status": envelope2.get("status"),
        }
    orig2 = envelope2.get("original_unchanged") or {}
    if orig2 and orig2.get("unchanged") is False:
        return {
            "schema": SCHEMA_ID, "op_name": "create_layer", "native_op": native_op,
            "status": gate.STATUS_ORIGINAL_MUTATED, "exit_code": gate.EXIT_ORIGINAL_MUTATED,
            "reason": "step 1's staged_output changed during step 2's apply -- "
                      "READ-ONLY invariant violated at the chain link",
            "original_unchanged": orig2,
        }

    pre_ir_ref = envelope2.get("pre_ir")
    post_ir_ref = envelope2.get("post_ir")
    if not pre_ir_ref or not post_ir_ref:
        return {
            "schema": SCHEMA_ID, "op_name": "create_layer", "native_op": native_op,
            "status": gate.STATUS_ERROR, "exit_code": gate.EXIT_ERROR,
            "reason": "mutation step envelope missing pre_ir/post_ir",
        }
    pre_ir = _load_ir_maybe(pre_ir_ref)
    post_ir = _load_ir_maybe(post_ir_ref)
    pre_rec = _layer_by_name(pre_ir, name)
    post_rec = _layer_by_name(post_ir, name)

    result: Dict[str, Any] = {
        "schema": SCHEMA_ID, "op_name": "create_layer", "native_op": native_op,
        "layer_name": name, "pre_record": pre_rec, "post_record": post_rec, "run_dir": out_dir,
    }
    if pre_rec is None or post_rec is None:
        result.update(status=gate.STATUS_HOLLOW, exit_code=gate.EXIT_HOLLOW,
                      reason="layer %r missing from pre_ir and/or post_ir" % name)
        return result

    requested = layer_record_diff({k: change_args[k] for k in LAYER_RECORD_FIELDS if k in change_args},
                                  post_rec)
    all_changed = sorted(k for k in LAYER_RECORD_FIELDS if pre_rec.get(k) != post_rec.get(k))
    expected_changed = sorted(change_args.keys())
    result["changed_fields"] = all_changed
    if requested:
        result.update(status=gate.STATUS_HOLLOW, exit_code=gate.EXIT_HOLLOW,
                      reason="the requested change to %s was not detected on re-extraction "
                             "(invisible data)" % requested)
    elif all_changed != expected_changed:
        result.update(status=gate.STATUS_IRRECONSTRUCTIBLE, exit_code=gate.EXIT_IRRECONSTRUCTIBLE,
                      reason="expected exactly the changed field set %s, observed %s"
                             % (expected_changed, all_changed))
    else:
        result.update(status=gate.STATUS_OK, exit_code=gate.EXIT_OK)
    return result


# --------------------------------------------------------------------------- #
# TABLES tier (w3-dimstyle, D-class): dimstyle table RECORD-diff driver.
#
# symbol_tables.dim_styles[] is, like symbol_tables.layers[], not an entity:
# no handle join through cad_diff, no geometry/bbox, joined by NAME instead.
# This is the DIMSTYLE sibling of the LAYER record-diff driver directly
# above (LAYER_RECORD_FIELDS / layer_record_diff / probe_layer_roundtrip /
# probe_layer_mutation) -- same apply_staged plumbing, same cad_op_gate
# status/exit-code vocabulary, same flat per-field compare, just a different
# op_name / symbol-table section / field set.
# --------------------------------------------------------------------------- #

#: the representative DIMVAR subset write.dimstyle.create actually writes
#: (AriadneNativeJob.cpp's DimStylePropertyArgs/applyDimStyleProperties) AND
#: dimStylesRichJson extracts back -- the record-diff's comparable field set.
#: AcDbDimStyleTableRecord exposes ~70 DIMVARs total (dbdimvar.h); the other
#: ~60 are an honest gap (see tools/patch_ops/tables.py's module docstring),
#: not yet write-wired, so they're out of scope here.
DIMSTYLE_RECORD_FIELDS = ("dimtxt", "dimasz", "dimexe", "dimexo", "dimdec",
                          "dimscale", "dimclrd", "dimclre", "dimclrt", "dimse1")


def _dimstyle_by_name(ir: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    """Find a symbol_tables.dim_styles[] record by name -- the dimstyle
    table's own join key (unique within a database), mirroring
    _layer_by_name."""
    for rec in ((ir.get("symbol_tables") or {}).get("dim_styles") or []):
        if isinstance(rec, dict) and rec.get("name") == name:
            return rec
    return None


def expected_dimstyle_record(args: Dict[str, Any]) -> Dict[str, Any]:
    """Ground truth = the op's OWN args (never a live read): every
    DIMSTYLE_RECORD_FIELDS key present in ``args`` is asserted verbatim.
    Mirrors expected_layer_record."""
    return {k: args[k] for k in DIMSTYLE_RECORD_FIELDS if k in args}


#: dimstyle_record_diff is IDENTICAL in shape to layer_record_diff (same
#: "sorted mismatching keys, or every expected key if actual is None"
#: contract) -- reused directly rather than redefined.
dimstyle_record_diff = layer_record_diff


def probe_dimstyle_roundtrip(args: Dict[str, Any], dwg_path: str, out_dir: str, *,
                             apply_staged: Optional[Callable[[Dict[str, Any], str, str], Dict[str, Any]]] = None,
                             patch_ops_mod=None, cad_op_gate_mod=None) -> Dict[str, Any]:
    """create_dimstyle -> re-extract -> record-diff against the op's own
    args. Mirrors probe_layer_roundtrip's pipeline and result shape exactly,
    joining/comparing a symbol_tables.dim_styles[] record by NAME."""
    gate = cad_op_gate_mod if cad_op_gate_mod is not None else _import_optional("cad_op_gate")
    if gate is None:
        return {"schema": SCHEMA_ID, "op_name": "create_dimstyle", "status": "error",
                "exit_code": 2, "reason": "cad_op_gate sibling module unavailable"}

    native_op = resolve_native_op("create_dimstyle", patch_ops_mod=patch_ops_mod)
    if native_op is None:
        return {
            "schema": SCHEMA_ID, "op_name": "create_dimstyle", "status": gate.STATUS_NOT_IMPLEMENTED,
            "exit_code": gate.EXIT_NOT_IMPLEMENTED,
            "reason": "create_dimstyle has no live native write handler wired "
                      "(patch_ops.NATIVE_WRITE_OP_MAP)",
        }

    name = args.get("name")
    if not name:
        return {"schema": SCHEMA_ID, "op_name": "create_dimstyle", "native_op": native_op,
                "status": gate.STATUS_ERROR, "exit_code": gate.EXIT_ERROR,
                "reason": "args['name'] is required"}

    apply_fn = apply_staged
    if apply_fn is None:
        patch_engine = _import_optional("patch_engine")
        apply_fn = getattr(patch_engine, "apply_staged", None) if patch_engine else None
    if apply_fn is None:
        return {
            "schema": SCHEMA_ID, "op_name": "create_dimstyle", "native_op": native_op,
            "status": gate.STATUS_NOT_IMPLEMENTED, "exit_code": gate.EXIT_NOT_IMPLEMENTED,
            "reason": "patch_engine.apply_staged unavailable",
        }

    patch = _build_patch("create_dimstyle", args, dwg_path, out_dir,
                         postconditions=[{"subject": "dimstyle_exists", "op": "exists", "value": name}])
    envelope = apply_fn(patch, dwg_path, out_dir)
    env_status = envelope.get("status")
    if env_status != "ok":
        deferred_reasons = {"not_implemented", "unavailable"}
        exit_code = gate.EXIT_NOT_IMPLEMENTED if env_status in deferred_reasons else gate.EXIT_ERROR
        status = gate.STATUS_NOT_IMPLEMENTED if env_status in deferred_reasons else gate.STATUS_ERROR
        return {
            "schema": SCHEMA_ID, "op_name": "create_dimstyle", "native_op": native_op,
            "status": status, "exit_code": exit_code,
            "reason": envelope.get("reason"), "envelope_status": env_status,
        }

    orig = envelope.get("original_unchanged") or {}
    if orig and orig.get("unchanged") is False:
        return {
            "schema": SCHEMA_ID, "op_name": "create_dimstyle", "native_op": native_op,
            "status": gate.STATUS_ORIGINAL_MUTATED, "exit_code": gate.EXIT_ORIGINAL_MUTATED,
            "reason": "original DWG changed during the live apply -- READ-ONLY invariant violated",
            "original_unchanged": orig,
        }

    post_ir_ref = envelope.get("post_ir")
    if not post_ir_ref:
        return {
            "schema": SCHEMA_ID, "op_name": "create_dimstyle", "native_op": native_op,
            "status": gate.STATUS_ERROR, "exit_code": gate.EXIT_ERROR,
            "reason": "apply_staged envelope reported ok but is missing post_ir",
        }
    post_ir = _load_ir_maybe(post_ir_ref)
    actual = _dimstyle_by_name(post_ir, name)
    expected = expected_dimstyle_record(args)
    diff = dimstyle_record_diff(expected, actual)

    result: Dict[str, Any] = {
        "schema": SCHEMA_ID, "op_name": "create_dimstyle", "native_op": native_op,
        "dimstyle_name": name, "expected": expected, "actual": actual, "record_diff": diff,
        "original_unchanged": orig, "run_dir": out_dir,
        "staged_output": envelope.get("staged_output"),
    }
    if actual is None:
        result.update(status=gate.STATUS_HOLLOW, exit_code=gate.EXIT_HOLLOW,
                      reason="dimstyle %r not found in symbol_tables.dim_styles[] after the write" % name)
    elif diff:
        result.update(status=gate.STATUS_FAIL, exit_code=gate.EXIT_FAIL,
                      reason="record-diff is non-zero: field(s) %s do not match what was written"
                             % diff)
    else:
        result.update(status=gate.STATUS_OK, exit_code=gate.EXIT_OK)
    return result


def probe_dimstyle_mutation(name: str, baseline_args: Dict[str, Any], change_args: Dict[str, Any],
                            dwg_path: str, out_dir: str, *,
                            apply_staged: Optional[Callable[[Dict[str, Any], str, str], Dict[str, Any]]] = None,
                            patch_ops_mod=None, cad_op_gate_mod=None) -> Dict[str, Any]:
    """The D-gate's 'changing one DIMVAR -> 1 modified' contract, at the
    dimstyle-record level. Mirrors probe_layer_mutation's two-step chained-
    staged-copy pipeline exactly (see its own docstring for the full
    rationale) -- step 1 creates ``name`` with baseline_args, step 2
    re-applies create_dimstyle with ONLY change_args onto step 1's own
    staged_output."""
    gate = cad_op_gate_mod if cad_op_gate_mod is not None else _import_optional("cad_op_gate")
    if gate is None:
        return {"schema": SCHEMA_ID, "op_name": "create_dimstyle", "status": "error",
                "exit_code": 2, "reason": "cad_op_gate sibling module unavailable"}

    out_dir1 = os.path.join(out_dir, "step1_baseline")
    step1 = probe_dimstyle_roundtrip(dict(baseline_args, name=name), dwg_path, out_dir1,
                                     apply_staged=apply_staged, patch_ops_mod=patch_ops_mod,
                                     cad_op_gate_mod=gate)
    if step1["status"] != gate.STATUS_OK:
        step1["reason"] = "baseline step failed: %s" % step1.get("reason")
        return step1
    staged_after_1 = step1.get("staged_output")
    if not staged_after_1:
        return {"schema": SCHEMA_ID, "op_name": "create_dimstyle", "status": gate.STATUS_ERROR,
                "exit_code": gate.EXIT_ERROR, "reason": "baseline step produced no staged_output"}

    apply_fn = apply_staged
    if apply_fn is None:
        patch_engine = _import_optional("patch_engine")
        apply_fn = getattr(patch_engine, "apply_staged", None) if patch_engine else None
    if apply_fn is None:
        return {"schema": SCHEMA_ID, "op_name": "create_dimstyle", "status": gate.STATUS_NOT_IMPLEMENTED,
                "exit_code": gate.EXIT_NOT_IMPLEMENTED, "reason": "patch_engine.apply_staged unavailable"}
    native_op = resolve_native_op("create_dimstyle", patch_ops_mod=patch_ops_mod)

    out_dir2 = os.path.join(out_dir, "step2_change")
    change_full_args = dict(change_args, name=name)
    patch2 = _build_patch("create_dimstyle", change_full_args, staged_after_1, out_dir2,
                          postconditions=[{"subject": "dimstyle_exists", "op": "exists", "value": name}])
    envelope2 = apply_fn(patch2, staged_after_1, out_dir2)
    if envelope2.get("status") != "ok":
        return {
            "schema": SCHEMA_ID, "op_name": "create_dimstyle", "native_op": native_op,
            "status": gate.STATUS_ERROR, "exit_code": gate.EXIT_ERROR,
            "reason": "mutation step failed: %s" % envelope2.get("reason"),
            "envelope_status": envelope2.get("status"),
        }
    orig2 = envelope2.get("original_unchanged") or {}
    if orig2 and orig2.get("unchanged") is False:
        return {
            "schema": SCHEMA_ID, "op_name": "create_dimstyle", "native_op": native_op,
            "status": gate.STATUS_ORIGINAL_MUTATED, "exit_code": gate.EXIT_ORIGINAL_MUTATED,
            "reason": "step 1's staged_output changed during step 2's apply -- "
                      "READ-ONLY invariant violated at the chain link",
            "original_unchanged": orig2,
        }

    pre_ir_ref = envelope2.get("pre_ir")
    post_ir_ref = envelope2.get("post_ir")
    if not pre_ir_ref or not post_ir_ref:
        return {
            "schema": SCHEMA_ID, "op_name": "create_dimstyle", "native_op": native_op,
            "status": gate.STATUS_ERROR, "exit_code": gate.EXIT_ERROR,
            "reason": "mutation step envelope missing pre_ir/post_ir",
        }
    pre_ir = _load_ir_maybe(pre_ir_ref)
    post_ir = _load_ir_maybe(post_ir_ref)
    pre_rec = _dimstyle_by_name(pre_ir, name)
    post_rec = _dimstyle_by_name(post_ir, name)

    result: Dict[str, Any] = {
        "schema": SCHEMA_ID, "op_name": "create_dimstyle", "native_op": native_op,
        "dimstyle_name": name, "pre_record": pre_rec, "post_record": post_rec, "run_dir": out_dir,
    }
    if pre_rec is None or post_rec is None:
        result.update(status=gate.STATUS_HOLLOW, exit_code=gate.EXIT_HOLLOW,
                      reason="dimstyle %r missing from pre_ir and/or post_ir" % name)
        return result

    requested = dimstyle_record_diff(
        {k: change_args[k] for k in DIMSTYLE_RECORD_FIELDS if k in change_args}, post_rec)
    all_changed = sorted(k for k in DIMSTYLE_RECORD_FIELDS if pre_rec.get(k) != post_rec.get(k))
    expected_changed = sorted(change_args.keys())
    result["changed_fields"] = all_changed
    if requested:
        result.update(status=gate.STATUS_HOLLOW, exit_code=gate.EXIT_HOLLOW,
                      reason="the requested change to %s was not detected on re-extraction "
                             "(invisible data)" % requested)
    elif all_changed != expected_changed:
        result.update(status=gate.STATUS_IRRECONSTRUCTIBLE, exit_code=gate.EXIT_IRRECONSTRUCTIBLE,
                      reason="expected exactly the changed field set %s, observed %s"
                             % (expected_changed, all_changed))
    else:
        result.update(status=gate.STATUS_OK, exit_code=gate.EXIT_OK)
    return result


# --------------------------------------------------------------------------- #
# TABLES tier (w3-ltts, D-class): linetype table RECORD-diff driver.
#
# symbol_tables.linetypes[] is, like symbol_tables.layers[]/dim_styles[], not
# an entity: no handle join through cad_diff, no geometry/bbox, joined by
# NAME instead. This is the LINETYPE sibling of the LAYER/DIMSTYLE
# record-diff drivers above -- same apply_staged plumbing, same cad_op_gate
# status/exit-code vocabulary, same flat per-field compare (dash_lengths
# compares as a whole list, which Python's != already does element-wise), just
# a different op_name / symbol-table section / field set.
# --------------------------------------------------------------------------- #

#: the representative field subset write.linetype.create actually writes
#: (AriadneNativeJob.cpp's LinetypePropertyArgs/applyLinetypeProperties) AND
#: linetypesRichJson extracts back -- the record-diff's comparable field set.
#: Complex-linetype shape/text embedding is an honest gap (see
#: tools/patch_ops/tables.py's module docstring), out of scope here.
LINETYPE_RECORD_FIELDS = ("description", "dash_lengths")


def _linetype_by_name(ir: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    """Find a symbol_tables.linetypes[] record by name -- the linetype
    table's own join key (unique within a database), mirroring
    _layer_by_name."""
    for rec in ((ir.get("symbol_tables") or {}).get("linetypes") or []):
        if isinstance(rec, dict) and rec.get("name") == name:
            return rec
    return None


def expected_linetype_record(args: Dict[str, Any]) -> Dict[str, Any]:
    """Ground truth = the op's OWN args (never a live read): every
    LINETYPE_RECORD_FIELDS key present in ``args`` is asserted verbatim.
    Mirrors expected_layer_record."""
    return {k: args[k] for k in LINETYPE_RECORD_FIELDS if k in args}


#: linetype_record_diff is IDENTICAL in shape to layer_record_diff (same
#: "sorted mismatching keys, or every expected key if actual is None"
#: contract) -- reused directly rather than redefined.
linetype_record_diff = layer_record_diff


def probe_linetype_roundtrip(args: Dict[str, Any], dwg_path: str, out_dir: str, *,
                             apply_staged: Optional[Callable[[Dict[str, Any], str, str], Dict[str, Any]]] = None,
                             patch_ops_mod=None, cad_op_gate_mod=None) -> Dict[str, Any]:
    """create_linetype -> re-extract -> record-diff against the op's own
    args. Mirrors probe_layer_roundtrip's pipeline and result shape exactly,
    joining/comparing a symbol_tables.linetypes[] record by NAME."""
    gate = cad_op_gate_mod if cad_op_gate_mod is not None else _import_optional("cad_op_gate")
    if gate is None:
        return {"schema": SCHEMA_ID, "op_name": "create_linetype", "status": "error",
                "exit_code": 2, "reason": "cad_op_gate sibling module unavailable"}

    native_op = resolve_native_op("create_linetype", patch_ops_mod=patch_ops_mod)
    if native_op is None:
        return {
            "schema": SCHEMA_ID, "op_name": "create_linetype", "status": gate.STATUS_NOT_IMPLEMENTED,
            "exit_code": gate.EXIT_NOT_IMPLEMENTED,
            "reason": "create_linetype has no live native write handler wired "
                      "(patch_ops.NATIVE_WRITE_OP_MAP)",
        }

    name = args.get("name")
    if not name:
        return {"schema": SCHEMA_ID, "op_name": "create_linetype", "native_op": native_op,
                "status": gate.STATUS_ERROR, "exit_code": gate.EXIT_ERROR,
                "reason": "args['name'] is required"}

    apply_fn = apply_staged
    if apply_fn is None:
        patch_engine = _import_optional("patch_engine")
        apply_fn = getattr(patch_engine, "apply_staged", None) if patch_engine else None
    if apply_fn is None:
        return {
            "schema": SCHEMA_ID, "op_name": "create_linetype", "native_op": native_op,
            "status": gate.STATUS_NOT_IMPLEMENTED, "exit_code": gate.EXIT_NOT_IMPLEMENTED,
            "reason": "patch_engine.apply_staged unavailable",
        }

    patch = _build_patch("create_linetype", args, dwg_path, out_dir,
                         postconditions=[{"subject": "linetype_exists", "op": "exists", "value": name}])
    envelope = apply_fn(patch, dwg_path, out_dir)
    env_status = envelope.get("status")
    if env_status != "ok":
        deferred_reasons = {"not_implemented", "unavailable"}
        exit_code = gate.EXIT_NOT_IMPLEMENTED if env_status in deferred_reasons else gate.EXIT_ERROR
        status = gate.STATUS_NOT_IMPLEMENTED if env_status in deferred_reasons else gate.STATUS_ERROR
        return {
            "schema": SCHEMA_ID, "op_name": "create_linetype", "native_op": native_op,
            "status": status, "exit_code": exit_code,
            "reason": envelope.get("reason"), "envelope_status": env_status,
        }

    orig = envelope.get("original_unchanged") or {}
    if orig and orig.get("unchanged") is False:
        return {
            "schema": SCHEMA_ID, "op_name": "create_linetype", "native_op": native_op,
            "status": gate.STATUS_ORIGINAL_MUTATED, "exit_code": gate.EXIT_ORIGINAL_MUTATED,
            "reason": "original DWG changed during the live apply -- READ-ONLY invariant violated",
            "original_unchanged": orig,
        }

    post_ir_ref = envelope.get("post_ir")
    if not post_ir_ref:
        return {
            "schema": SCHEMA_ID, "op_name": "create_linetype", "native_op": native_op,
            "status": gate.STATUS_ERROR, "exit_code": gate.EXIT_ERROR,
            "reason": "apply_staged envelope reported ok but is missing post_ir",
        }
    post_ir = _load_ir_maybe(post_ir_ref)
    actual = _linetype_by_name(post_ir, name)
    expected = expected_linetype_record(args)
    diff = linetype_record_diff(expected, actual)

    result: Dict[str, Any] = {
        "schema": SCHEMA_ID, "op_name": "create_linetype", "native_op": native_op,
        "linetype_name": name, "expected": expected, "actual": actual, "record_diff": diff,
        "original_unchanged": orig, "run_dir": out_dir,
        "staged_output": envelope.get("staged_output"),
    }
    if actual is None:
        result.update(status=gate.STATUS_HOLLOW, exit_code=gate.EXIT_HOLLOW,
                      reason="linetype %r not found in symbol_tables.linetypes[] after the write" % name)
    elif diff:
        result.update(status=gate.STATUS_FAIL, exit_code=gate.EXIT_FAIL,
                      reason="record-diff is non-zero: field(s) %s do not match what was written"
                             % diff)
    else:
        result.update(status=gate.STATUS_OK, exit_code=gate.EXIT_OK)
    return result


def probe_linetype_mutation(name: str, baseline_args: Dict[str, Any], change_args: Dict[str, Any],
                            dwg_path: str, out_dir: str, *,
                            apply_staged: Optional[Callable[[Dict[str, Any], str, str], Dict[str, Any]]] = None,
                            patch_ops_mod=None, cad_op_gate_mod=None) -> Dict[str, Any]:
    """The D-gate's 'changing one field -> 1 modified' contract, at the
    linetype-record level. Mirrors probe_layer_mutation's two-step chained-
    staged-copy pipeline exactly (see its own docstring for the full
    rationale) -- step 1 creates ``name`` with baseline_args, step 2
    re-applies create_linetype with ONLY change_args onto step 1's own
    staged_output."""
    gate = cad_op_gate_mod if cad_op_gate_mod is not None else _import_optional("cad_op_gate")
    if gate is None:
        return {"schema": SCHEMA_ID, "op_name": "create_linetype", "status": "error",
                "exit_code": 2, "reason": "cad_op_gate sibling module unavailable"}

    out_dir1 = os.path.join(out_dir, "step1_baseline")
    step1 = probe_linetype_roundtrip(dict(baseline_args, name=name), dwg_path, out_dir1,
                                     apply_staged=apply_staged, patch_ops_mod=patch_ops_mod,
                                     cad_op_gate_mod=gate)
    if step1["status"] != gate.STATUS_OK:
        step1["reason"] = "baseline step failed: %s" % step1.get("reason")
        return step1
    staged_after_1 = step1.get("staged_output")
    if not staged_after_1:
        return {"schema": SCHEMA_ID, "op_name": "create_linetype", "status": gate.STATUS_ERROR,
                "exit_code": gate.EXIT_ERROR, "reason": "baseline step produced no staged_output"}

    apply_fn = apply_staged
    if apply_fn is None:
        patch_engine = _import_optional("patch_engine")
        apply_fn = getattr(patch_engine, "apply_staged", None) if patch_engine else None
    if apply_fn is None:
        return {"schema": SCHEMA_ID, "op_name": "create_linetype", "status": gate.STATUS_NOT_IMPLEMENTED,
                "exit_code": gate.EXIT_NOT_IMPLEMENTED, "reason": "patch_engine.apply_staged unavailable"}
    native_op = resolve_native_op("create_linetype", patch_ops_mod=patch_ops_mod)

    out_dir2 = os.path.join(out_dir, "step2_change")
    change_full_args = dict(change_args, name=name)
    patch2 = _build_patch("create_linetype", change_full_args, staged_after_1, out_dir2,
                          postconditions=[{"subject": "linetype_exists", "op": "exists", "value": name}])
    envelope2 = apply_fn(patch2, staged_after_1, out_dir2)
    if envelope2.get("status") != "ok":
        return {
            "schema": SCHEMA_ID, "op_name": "create_linetype", "native_op": native_op,
            "status": gate.STATUS_ERROR, "exit_code": gate.EXIT_ERROR,
            "reason": "mutation step failed: %s" % envelope2.get("reason"),
            "envelope_status": envelope2.get("status"),
        }
    orig2 = envelope2.get("original_unchanged") or {}
    if orig2 and orig2.get("unchanged") is False:
        return {
            "schema": SCHEMA_ID, "op_name": "create_linetype", "native_op": native_op,
            "status": gate.STATUS_ORIGINAL_MUTATED, "exit_code": gate.EXIT_ORIGINAL_MUTATED,
            "reason": "step 1's staged_output changed during step 2's apply -- "
                      "READ-ONLY invariant violated at the chain link",
            "original_unchanged": orig2,
        }

    pre_ir_ref = envelope2.get("pre_ir")
    post_ir_ref = envelope2.get("post_ir")
    if not pre_ir_ref or not post_ir_ref:
        return {
            "schema": SCHEMA_ID, "op_name": "create_linetype", "native_op": native_op,
            "status": gate.STATUS_ERROR, "exit_code": gate.EXIT_ERROR,
            "reason": "mutation step envelope missing pre_ir/post_ir",
        }
    pre_ir = _load_ir_maybe(pre_ir_ref)
    post_ir = _load_ir_maybe(post_ir_ref)
    pre_rec = _linetype_by_name(pre_ir, name)
    post_rec = _linetype_by_name(post_ir, name)

    result: Dict[str, Any] = {
        "schema": SCHEMA_ID, "op_name": "create_linetype", "native_op": native_op,
        "linetype_name": name, "pre_record": pre_rec, "post_record": post_rec, "run_dir": out_dir,
    }
    if pre_rec is None or post_rec is None:
        result.update(status=gate.STATUS_HOLLOW, exit_code=gate.EXIT_HOLLOW,
                      reason="linetype %r missing from pre_ir and/or post_ir" % name)
        return result

    requested = linetype_record_diff(
        {k: change_args[k] for k in LINETYPE_RECORD_FIELDS if k in change_args}, post_rec)
    all_changed = sorted(k for k in LINETYPE_RECORD_FIELDS if pre_rec.get(k) != post_rec.get(k))
    expected_changed = sorted(change_args.keys())
    result["changed_fields"] = all_changed
    if requested:
        result.update(status=gate.STATUS_HOLLOW, exit_code=gate.EXIT_HOLLOW,
                      reason="the requested change to %s was not detected on re-extraction "
                             "(invisible data)" % requested)
    elif all_changed != expected_changed:
        result.update(status=gate.STATUS_IRRECONSTRUCTIBLE, exit_code=gate.EXIT_IRRECONSTRUCTIBLE,
                      reason="expected exactly the changed field set %s, observed %s"
                             % (expected_changed, all_changed))
    else:
        result.update(status=gate.STATUS_OK, exit_code=gate.EXIT_OK)
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
