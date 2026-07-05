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

w3-dimstyle + p1-dimvars (D-class TABLES tier): write.dimstyle.create is the
SAME upsert shape for the DIMSTYLE table -- AcDbDimStyleTableRecord exposes
~78 dimension variables (dbdimvar.h). p1-dimvars extended the native side
(AriadneNativeJob.cpp's DimStylePropertyArgs) from the original
representative 10-field subset to the full honestly-settable surface, and
the passthrough allow-lists below now cover every wired field -- any DIMVAR
NOT in one of these tuples is a measured, documented exclusion (see
D:/dev/.build/cados_plan/runs/waveP/dimvars/build_log.md), not a silent gap.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# patch op id -> native ObjectARX write op (operations.v2.json, status
# "implemented"). Only these have a live native handler today.
WRITE_OP_MAP: Dict[str, str] = {
    "create_layer": "write.layer.create",
    "create_dimstyle": "write.dimstyle.create",
}

# Passthrough fields whose native job encoding is identical to the patch-op
# arg (string/number, no coercion needed).
_LAYER_PASSTHROUGH_FIELDS = ("color_index", "linetype", "lineweight")
# Boolean-shaped fields: the native side parses job args via jsonFindNumber
# (strtod) for its "closed"/"is_write"-style 0/1 convention, which does NOT
# understand JSON true/false tokens -- coerce here so a caller can pass an
# idiomatic Python bool without silently becoming "false" on the wire.
_LAYER_FLAG_FIELDS = ("plottable", "frozen", "off", "locked")

# Every DIMVAR write.dimstyle.create's native handler reads (DimStyle
# PropertyArgs in AriadneNativeJob.cpp) -- p1-dimvars extended both tuples
# from the original representative 10-field subset to the full
# honestly-settable ~78-DIMVAR surface (dbdimvar.h); any name still not
# forwarded here is a measured, documented exclusion (build_log.md).
_DIMSTYLE_PASSTHROUGH_FIELDS = (
    "dimtxt", "dimasz", "dimexe", "dimexo", "dimdec", "dimscale",
    "dimclrd", "dimclre", "dimclrt",
    # p1-dimvars: doubles
    "dimaltf", "dimaltrnd", "dimcen", "dimdle", "dimdli", "dimgap",
    "dimjogang", "dimlfac", "dimrnd", "dimtfac", "dimtm", "dimtp",
    "dimtsz", "dimtvp", "dimfxlen", "dimmzf", "dimaltmzf",
    # p1-dimvars: ints
    "dimadec", "dimaltd", "dimalttd", "dimalttz", "dimaltu", "dimaltz",
    "dimarcsym", "dimatfit", "dimaunit", "dimazin", "dimfrac", "dimjust",
    "dimlunit", "dimtad", "dimtdec", "dimtfill", "dimtmove", "dimtolj",
    "dimtzin", "dimzin",
    # p1-dimvars: AcCmColor index + AcDb::LineWeight (plain ints, same
    # convention as dimclrd/e/t and LAYER's "lineweight" above)
    "dimtfillclr", "dimlwd", "dimlwe",
    # p1-dimvars: content strings (empty is a legitimate "clear" value) +
    # the 1-character decimal separator
    "dimapost", "dimpost", "dimmzs", "dimaltmzs", "dimdsep",
    # p1-dimvars: ObjectId-typed fields resolved by NAME on the native side
    # (block/linetype/textstyle lookup) -- plain string passthrough here,
    # same as LAYER's "linetype" above.
    "dimblk", "dimblk1", "dimblk2", "dimldrblk",
    "dimltype", "dimltex1", "dimltex2", "dimtxsty",
)
_DIMSTYLE_FLAG_FIELDS = (
    "dimse1",
    # p1-dimvars: bools
    "dimalt", "dimlim", "dimsah", "dimsd1", "dimsd2", "dimse2", "dimsoxd",
    "dimtih", "dimtix", "dimtofl", "dimtoh", "dimtol", "dimupt",
    "dimfxlenon", "dimtxtdirection",
)


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
    return None


def ir_op_for(ent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """No IR entity kind regenerates a symbol-table op yet; always None."""
    return None
