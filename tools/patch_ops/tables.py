#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_ops.tables -- symbol-table write ops (CAD OS Layer, Lane E family
split).

Symbol-table ops (layer/linetype/dimstyle/textstyle). create_layer (->
write.layer.create), create_dimstyle (-> write.dimstyle.create), and
create_linetype (-> write.linetype.create) have live native handlers here
today; textstyle record writes await a family ticket (only the reference BY
NAME from a layer record -- see "linetype" below -- is wired).

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

w3-ltts (D-class TABLES tier): write.linetype.create is the SAME upsert
shape for the LINETYPE table -- name + description (comments) + a simple
dash pattern (``dash_lengths``, a plain list of numbers: positive=dash,
negative=gap, 0=dot, per DXF/AutoCAD LINETYPE semantics). Complex-linetype
shape/text embedding is out of scope (see AriadneNativeJob.cpp's
linetypesRichJson docstring) -- an honest gap, not a fake write. Supplying
``dash_lengths`` always replaces the whole pattern; there is no partial
per-index update (AutoCAD's own setNumDashes/setDashLengthAt pair has no
concept of one). Live-verified quirk (see AriadneNativeJob.cpp's
applyLinetypeProperties): AutoCAD's core LTYPE persistence ties the comments
field to the dash-pattern recompute trigger, so a description-only update on
an EXISTING linetype silently reverted until the native handler was made to
re-apply the record's own current dash pattern alongside it -- this is
handled natively; callers do not need to work around it themselves.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# patch op id -> native ObjectARX write op (operations.v2.json, status
# "implemented"). Only these have a live native handler today.
WRITE_OP_MAP: Dict[str, str] = {
    "create_layer": "write.layer.create",
    "create_dimstyle": "write.dimstyle.create",
    "create_linetype": "write.linetype.create",
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

# The representative field subset write.linetype.create's native handler
# actually reads (LinetypePropertyArgs in AriadneNativeJob.cpp). dash_lengths
# is a plain list of numbers -- no bool coercion needed, it travels as a JSON
# array verbatim (see module docstring's "replaces the whole pattern" note).
_LINETYPE_PASSTHROUGH_FIELDS = ("description", "dash_lengths")


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
    if native_op == "write.linetype.create":
        # create_linetype -> create-or-update (upsert) the target linetype
        # record. Mirrors write.layer.create's arg-forwarding exactly.
        out: Dict[str, Any] = {}
        name = args.get("name")
        if name is not None:
            out["name"] = name
        for key in _LINETYPE_PASSTHROUGH_FIELDS:
            if key in args:
                out[key] = args[key]
        return out
    return None


def ir_op_for(ent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """No IR entity kind regenerates a symbol-table op yet; always None."""
    return None
