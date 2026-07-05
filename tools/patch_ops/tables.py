#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_ops.tables -- symbol-table write ops (CAD OS Layer, Lane E family
split).

Symbol-table ops (layer/linetype/dimstyle/textstyle). create_layer (->
write.layer.create) and create_dimstyle (-> write.dimstyle.create) have live
native handlers here today; linetype/textstyle record writes await a family
ticket (only the reference BY NAME from a layer record -- see "linetype"
below -- is wired).

CADOS F8 / H-5: set_layer used to live in this module, also mapped to
write.layer.create. That was an active fake-success -- write.layer.create
only ENSURES a layer exists, it ignores 'handle' and never reassigns an
existing entity's layer, so a set_layer op "succeeded" without mutating
anything. set_layer now lives in patch_ops.entities, mapped to the real
relayer modify.entity.common (which takes 'handle' + 'set_layer' and calls
AcDbEntity::setLayer on the resolved entity -- see
src/Ariadne.AcadNative/families/m08g_handlers.inc and the live Lane-A probe
tools/probe_modify.py::run_probe_common).

w3-tables (D-class TABLES tier): write.layer.create is now an upsert -- an
existing layer's properties are updated (never just a has()-check no-op), so
color_index/linetype/lineweight/plottable/frozen/off/locked all round-trip
through re-extraction (symbol_tables.layers[], see AriadneNativeJob.cpp's
upsertLayerRecord). Only fields present in ``args`` are forwarded; an absent
field is left untouched on the native side, never defaulted/injected here.

w3-dimstyle (D-class TABLES tier): write.dimstyle.create is the SAME upsert
shape for the DIMSTYLE table -- AcDbDimStyleTableRecord exposes ~70
dimension variables (dbdimvar.h); only a representative subset is wired on
the native side today (dimtxt/dimasz/dimexe/dimexo/dimdec/dimscale/dimclrd/
dimclre/dimclrt/dimse1 -- see AriadneNativeJob.cpp's DimStylePropertyArgs).
The other ~60 DIMVARs are an honest gap: passing them in ``args`` is a
silent no-op on the wire (never forwarded), not a fake write.

p9-tables2 (D-class TABLES tier, wave-P2): write.ucs.create is the SAME
upsert shape for the UCS table -- AcDbUCSTableRecord (dbsymtb.h) is a small,
COMPLETE class, so origin/x_axis/y_axis is its entire settable surface (not
a partial subset like DIMSTYLE). These are this module's first point/vector-
valued fields: each travels as a nested {"x","y","z"} object (see
AriadneNativeJob.cpp's jsonFindPoint3/UcsPropertyArgs), passed through
verbatim -- no bool->int coercion needed since none of the 3 fields are
flag-shaped.

p9-tables2 (VIEW): write.view.create is the SAME upsert shape for the VIEW
table -- a REPRESENTATIVE subset of AcDbAbstractViewTableRecord's "camera"
properties (center/height/width/target/view_direction/twist/lens_length/
perspective_enabled/front_clip_distance/front_clip_enabled/
back_clip_distance/back_clip_enabled -- see AriadneNativeJob.cpp's
ViewPropertyArgs). center is a nested {"x","y"} 2D point; target/
view_direction are {"x","y","z"}. perspective_enabled/front_clip_enabled/
back_clip_enabled are flag-shaped (bool->int coercion, same as LAYER's
plottable/frozen/off/locked). Excluded (honest gap): isPaperspaceView,
category_name/layer_state (strings), layout/camera/sun/visual_style/
background (object-id refs), thumbnail/preview image, annotation scale,
UCS-per-view association.

p9-tables2 (VPORT): write.vport.create is the SAME upsert shape for the
VPORT table -- the viewport-specific subset VportPropertyArgs
(AriadneNativeJob.cpp) writes: the paperspace/screen rectangle
(lower_left/upper_right) plus the SAME shared AcDbAbstractViewTableRecord
center/height/width/target/view_direction/twist VIEW already certifies,
plus viewport-only interactive-editing toggles (ucs_follow_mode/
circle_sides/grid_enabled/snap_enabled/snap_angle/ucs_per_viewport).
lower_left/upper_right/center are nested {"x","y"} 2D points; target/
view_direction are {"x","y","z"}. ucs_follow_mode/grid_enabled/
snap_enabled/ucs_per_viewport are flag-shaped (bool->int coercion);
circle_sides is a plain int passthrough. Excluded (honest gap): lens_
length/perspective/clip-plane fields (already proven on this shared base
class via VIEW, not re-certified here); number() (read-only); the vestigial
fastZoomsEnabled; icon/gridIncrements/snapBase/snapIncrements/snapPair/
isometricSnapEnabled/GridDisplay sub-group (narrowed to one representative
field per concern); background/visualStyle/sunId/lighting (object-id or
complex nested refs); the richer UCS query/set API. NOTE: AutoCAD may
legitimately store multiple VPORT records named "*Active" (one per active
tiled viewport pane) -- callers of this op must never pass name="*Active".
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# patch op id -> native ObjectARX write op (operations.v2.json, status
# "implemented"). Only these have a live native handler today.
WRITE_OP_MAP: Dict[str, str] = {
    "create_layer": "write.layer.create",
    "create_dimstyle": "write.dimstyle.create",
    "create_ucs": "write.ucs.create",
    "create_view": "write.view.create",
    "create_vport": "write.vport.create",
}

# Passthrough fields whose native job encoding is identical to the patch-op
# arg (string/number, no coercion needed).
_LAYER_PASSTHROUGH_FIELDS = ("color_index", "linetype", "lineweight")
# Boolean-shaped fields: the native side parses job args via jsonFindNumber
# (strtod) for its "closed"/"is_write"-style 0/1 convention, which does NOT
# understand JSON true/false tokens -- coerce here so a caller can pass an
# idiomatic Python bool without silently becoming "false" on the wire.
_LAYER_FLAG_FIELDS = ("plottable", "frozen", "off", "locked")

# The representative DIMVAR subset write.dimstyle.create's native handler
# actually reads (DimStylePropertyArgs in AriadneNativeJob.cpp) -- every
# other DIMVAR name is NOT forwarded (see module docstring's gap note).
_DIMSTYLE_PASSTHROUGH_FIELDS = (
    "dimtxt", "dimasz", "dimexe", "dimexo", "dimdec", "dimscale",
    "dimclrd", "dimclre", "dimclrt",
)
_DIMSTYLE_FLAG_FIELDS = ("dimse1",)

# The full settable surface write.ucs.create's native handler reads
# (UcsPropertyArgs in AriadneNativeJob.cpp) -- all 3 are nested {"x","y","z"}
# point/vector objects, passed through as-is (no bool->int coercion, no
# passthrough/flag split needed since none are scalar or flag-shaped).
_UCS_POINT_FIELDS = ("origin", "x_axis", "y_axis")

# The representative "camera" subset write.view.create's native handler
# reads (ViewPropertyArgs in AriadneNativeJob.cpp).
_VIEW_POINT_FIELDS = ("center", "target", "view_direction")
_VIEW_PASSTHROUGH_FIELDS = ("height", "width", "twist", "lens_length",
                            "front_clip_distance", "back_clip_distance")
_VIEW_FLAG_FIELDS = ("perspective_enabled", "front_clip_enabled", "back_clip_enabled")

# The viewport-specific subset write.vport.create's native handler reads
# (VportPropertyArgs in AriadneNativeJob.cpp).
_VPORT_POINT_FIELDS = ("lower_left", "upper_right", "center", "target", "view_direction")
_VPORT_PASSTHROUGH_FIELDS = ("height", "width", "twist", "circle_sides", "snap_angle")
_VPORT_FLAG_FIELDS = ("ucs_follow_mode", "grid_enabled", "snap_enabled", "ucs_per_viewport")


def build_job_args(native_op: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Native job "args" for a symbol-table write op, or None if native_op
    isn't ours."""
    if native_op == "write.layer.create":
        # create_layer -> create-or-update (upsert) the target layer record.
        out: Dict[str, Any] = {}
        name = args.get("name") or args.get("layer")
        if name is not None:
            out["name"] = name
        for key in _LAYER_PASSTHROUGH_FIELDS:
            if key in args:
                out[key] = args[key]
        for key in _LAYER_FLAG_FIELDS:
            if key in args:
                out[key] = int(bool(args[key]))
        return out
    if native_op == "write.dimstyle.create":
        # create_dimstyle -> create-or-update (upsert) the target dimstyle
        # record. Mirrors write.layer.create's arg-forwarding exactly.
        out: Dict[str, Any] = {}
        name = args.get("name")
        if name is not None:
            out["name"] = name
        for key in _DIMSTYLE_PASSTHROUGH_FIELDS:
            if key in args:
                out[key] = args[key]
        for key in _DIMSTYLE_FLAG_FIELDS:
            if key in args:
                out[key] = int(bool(args[key]))
        return out
    if native_op == "write.ucs.create":
        # create_ucs -> create-or-update (upsert) the target UCS record.
        # Mirrors write.layer.create/write.dimstyle.create's arg-forwarding,
        # just with point/vector-shaped fields instead of scalars.
        out = {}
        name = args.get("name")
        if name is not None:
            out["name"] = name
        for key in _UCS_POINT_FIELDS:
            if key in args:
                out[key] = args[key]
        return out
    if native_op == "write.view.create":
        # create_view -> create-or-update (upsert) the target VIEW record.
        # Mirrors write.layer.create/write.ucs.create's arg-forwarding, with
        # a mix of point fields (verbatim) and flag fields (bool->int, same
        # convention as LAYER's plottable/frozen/off/locked).
        out = {}
        name = args.get("name")
        if name is not None:
            out["name"] = name
        for key in _VIEW_POINT_FIELDS:
            if key in args:
                out[key] = args[key]
        for key in _VIEW_PASSTHROUGH_FIELDS:
            if key in args:
                out[key] = args[key]
        for key in _VIEW_FLAG_FIELDS:
            if key in args:
                out[key] = int(bool(args[key]))
        return out
    if native_op == "write.vport.create":
        # create_vport -> create-or-update (upsert) the target VPORT record.
        # Mirrors write.view.create's arg-forwarding exactly (point fields
        # verbatim, flag fields bool->int, circle_sides/snap_angle plain
        # passthrough). Caller is responsible for never naming a record
        # "*Active" (see module docstring's VPORT quirk note).
        out = {}
        name = args.get("name")
        if name is not None:
            out["name"] = name
        for key in _VPORT_POINT_FIELDS:
            if key in args:
                out[key] = args[key]
        for key in _VPORT_PASSTHROUGH_FIELDS:
            if key in args:
                out[key] = args[key]
        for key in _VPORT_FLAG_FIELDS:
            if key in args:
                out[key] = int(bool(args[key]))
        return out
    return None


def ir_op_for(ent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """No IR entity kind regenerates a symbol-table op yet; always None."""
    return None
