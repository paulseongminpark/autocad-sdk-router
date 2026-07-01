#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_ops.entities -- entity write ops (CAD OS Layer, Lane E family split).

Owns the entity family's slice of patch_engine.NATIVE_WRITE_OP_MAP /
_native_job_doc and ir_to_patch's entity IR-op-cases (line/circle/arc/text/
polyline/dimension/...). create_line, create_circle, and set_layer have a live
native handler today; the rest degrade to not_implemented / deferred
(no-fake-success) until a family ticket wires them.

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
    # --- Tier 2 (require family-op promotion to be runnable) ---
    if kind == "text":
        return {"operation": "create_text",
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
