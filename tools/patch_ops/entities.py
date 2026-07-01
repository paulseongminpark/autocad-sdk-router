#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_ops.entities -- entity write ops (CAD OS Layer, Lane E family split).

Owns the entity family's slice of patch_engine.NATIVE_WRITE_OP_MAP /
_native_job_doc and ir_to_patch's entity IR-op-cases (line/circle/arc/text/
polyline/dimension/...). create_line, create_circle, set_layer, and (WAVE-1
TIER-1 T1, via tools/promote_op.py F2 promotion) create_arc/create_ellipse/
create_mpolygon/create_mtext/create_text/create_polyline/create_dimension/
set_entity_xdata have a live native handler today; the rest degrade to
not_implemented / deferred (no-fake-success) until a family ticket wires them.

CADOS F8 / H-5: set_layer is wired here (not patch_ops.tables) because its
real native handler is modify.entity.common -- an ENTITY mutation
(AcDbEntity::setLayer on a resolved 'handle'), not a symbol-table op. The
former mapping (write.layer.create) only ensured a layer existed and silently
ignored 'handle', so it never actually reassigned anything -- an active
fake-success. See src/Ariadne.AcadNative/families/m08g_handlers.inc's
"modify.entity.common" branch and the live Lane-A probe
tools/probe_modify.py::run_probe_common (R1) for the ground truth this
mapping is repointed at.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# patch op id -> native ObjectARX write op (operations.v2.json, status
# "implemented"). Only these have a live native handler today.
WRITE_OP_MAP: Dict[str, str] = {
    "create_line": "write.entity.line",
    "create_circle": "write.entity.circle",
    "set_layer": "modify.entity.common",
    "create_arc": "write.entity.arc",
    "create_ellipse": "write.entity.ellipse",
    "create_mpolygon": "write.entity.mpolygon",
    "create_mtext": "write.entity.mtext",
    "create_text": "write.entity.text",
    "create_polyline": "write.entity.polyline",
    "create_dimension": "write.entity.dim.rotated",
    "set_entity_xdata": "write.entity.set_xdata",
    "create_spline": "write.entity.spline",
    "create_dimension_aligned": "write.entity.dim.aligned",
    "create_dimension_radial": "write.entity.dim.radial",
    "create_dimension_diametric": "write.entity.dim.diametric",
    "create_dimension_ordinate": "write.entity.dim.ordinate",
    "create_leader": "write.entity.leader",
    "create_mline": "write.entity.mline",
    "create_dimension_arc": "write.entity.dim.arc",
    "create_dimension_angular2line": "write.entity.dim.angular2line",
    "create_dimension_angular3pt": "write.entity.dim.angular3pt",
}


def build_job_args(native_op: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Native job "args" for an entity write op, or None if native_op isn't ours."""
    if native_op == "write.entity.line":
        out: Dict[str, Any] = {}
        for k in ("start", "end", "layer"):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.circle":
        out = {}
        for k in ("center", "radius", "layer"):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "modify.entity.common":
        # set_layer -> resolve 'handle' and REASSIGN its layer (the m08g
        # native dispatcher reads 'handle' from the job root or job.args, and
        # 'set_layer' as a plain string field anywhere in the job JSON -- see
        # m08gFindHandle / the "modify.entity.common" branch in
        # m08g_handlers.inc). Patch-op args use 'layer' (matching
        # create_line/create_circle's key); the native field name is
        # 'set_layer', so the two are NOT the same key here on purpose.
        out = {}
        if "handle" in args:
            out["handle"] = args["handle"]
        if "layer" in args:
            out["set_layer"] = args["layer"]
        return out
    if native_op == "write.entity.arc":
        out: Dict[str, Any] = {}
        for k in ('center', 'radius', 'start_angle', 'end_angle', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.ellipse":
        out: Dict[str, Any] = {}
        for k in ('center', 'normal', 'major_axis', 'radius_ratio', 'start_angle', 'end_angle', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.mpolygon":
        out: Dict[str, Any] = {}
        for k in ('points', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.mtext":
        out: Dict[str, Any] = {}
        for k in ('position', 'text', 'height', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.text":
        out: Dict[str, Any] = {}
        for k in ('position', 'text', 'height', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.polyline":
        out: Dict[str, Any] = {}
        for k in ('points', 'closed', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.dim.rotated":
        out: Dict[str, Any] = {}
        for k in ('xline1', 'xline2', 'dim_line', 'dim_text', 'rotation', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.spline":
        out: Dict[str, Any] = {}
        for k in ('points', 'order', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.dim.aligned":
        out: Dict[str, Any] = {}
        for k in ('xline1', 'xline2', 'dim_line', 'dim_text', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.dim.radial":
        out: Dict[str, Any] = {}
        for k in ('center', 'chord_point', 'leader_length', 'dim_text', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.dim.diametric":
        out: Dict[str, Any] = {}
        for k in ('chord_point', 'far_chord_point', 'leader_length', 'dim_text', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.dim.ordinate":
        out: Dict[str, Any] = {}
        for k in ('defining_point', 'leader_end_point', 'use_x_axis', 'dim_text', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.leader":
        out: Dict[str, Any] = {}
        for k in ('vertices', 'points', 'text', 'height', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.mline":
        out: Dict[str, Any] = {}
        for k in ('points', 'vertices', 'closed', 'scale', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.dim.arc":
        out: Dict[str, Any] = {}
        for k in ('center', 'xline1', 'xline2', 'arc_point', 'dim_text', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.dim.angular2line":
        out: Dict[str, Any] = {}
        for k in ('xline1_start', 'xline1_end', 'xline2_start', 'xline2_end', 'arc_point', 'dim_text', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.dim.angular3pt":
        out: Dict[str, Any] = {}
        for k in ('center', 'xline1', 'xline2', 'arc_point', 'dim_text', 'layer'):
            if k in args:
                out[k] = args[k]
        return out
    if native_op == "write.entity.set_xdata":
        out: Dict[str, Any] = {}
        for k in ('app', 'value'):
            if k in args:
                out[k] = args[k]
        return out
    return None


def _pt(arr: Any) -> Optional[Dict[str, float]]:
    """IR coordinate array [x,y,z] -> native job object {x,y,z}."""
    if not arr:
        return None
    return {"x": arr[0], "y": arr[1], "z": arr[2] if len(arr) > 2 else 0.0}


def ir_op_for(ent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map one IR entity to a cad_patch operation, or None if not an entity
    kind this family regenerates."""
    g = ent.get("geometry") or {}
    kind = g.get("kind")
    layer = ent.get("layer")

    if kind == "line":
        return {"operation": "create_line",
                "args": {"start": _pt(g.get("start")), "end": _pt(g.get("end")), "layer": layer}}
    if kind == "circle":
        return {"operation": "create_circle",
                "args": {"center": _pt(g.get("center")), "radius": g.get("radius"), "layer": layer}}
    if kind == "arc":
        return {"operation": "create_arc",
                "args": {"center": _pt(g.get("center")), "radius": g.get("radius"),
                         "start_angle": g.get("start_angle"), "end_angle": g.get("end_angle"),
                         "layer": layer}}
    if kind == "ellipse":
        return {"operation": "create_ellipse",
                "args": {"center": _pt(g.get("center")), "normal": _pt(g.get("normal")),
                         "major_axis": _pt(g.get("major_axis")), "radius_ratio": g.get("radius_ratio"),
                         "start_angle": g.get("start_angle"), "end_angle": g.get("end_angle"),
                         "layer": layer}}
    # --- Tier 2 (WAVE-1 TIER-1 T1 promoted create_text/create_polyline to a
    # live native handler; the gate below is now just "is this IR kind ever
    # produced", not "is the op runnable") ---
    if kind == "text":
        return {"operation": "create_text",
                "args": {"position": _pt(g.get("position")), "text": g.get("text"),
                         "height": g.get("height", 2.5), "layer": layer}}
    if kind == "mtext":
        return {"operation": "create_mtext",
                "args": {"position": _pt(g.get("position")), "text": g.get("text"),
                         "height": g.get("height", 2.5), "layer": layer}}
    if kind in ("lwpolyline", "polyline"):
        points: List[Dict[str, float]] = []
        for v in (g.get("vertices") or []):
            p = v.get("point") if isinstance(v, dict) else v
            if not p:
                continue
            points.append({"x": p[0], "y": p[1],
                           "bulge": (v.get("bulge", 0.0) if isinstance(v, dict) else 0.0)})
        return {"operation": "create_polyline",
                "args": {"points": points, "closed": int(bool(g.get("closed"))), "layer": layer}}
    # --- Tier 3 (requires dimension extraction to populate geometry) ---
    if kind == "dimension":
        need = ("xline1_point", "xline2_point", "dim_line_point")
        if all(g.get(x) for x in need):
            return {"operation": "create_dimension",
                    "args": {"layer": layer, "dim_text": g.get("dim_text", ""),
                             "rotation": g.get("rotation", 0.0),
                             "xline1": _pt(g["xline1_point"]), "xline2": _pt(g["xline2_point"]),
                             "dim_line": _pt(g["dim_line_point"])}}
        return None  # extraction not landed yet -> deferred
    return None
