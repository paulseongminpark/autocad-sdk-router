#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_ops.tables -- symbol-table write ops (CAD OS Layer, Lane E family
split).

Symbol-table ops (layer/linetype/dimstyle/textstyle). Only create_layer
(-> write.layer.create) has a live native handler here today; linetype/
dimstyle/textstyle record writes await a family ticket (only the reference
BY NAME from a layer record -- see "linetype" below -- is wired).

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
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# patch op id -> native ObjectARX write op (operations.v2.json, status
# "implemented"). Only these have a live native handler today.
WRITE_OP_MAP: Dict[str, str] = {
    "create_layer": "write.layer.create",
}

# Passthrough fields whose native job encoding is identical to the patch-op
# arg (string/number, no coercion needed).
_LAYER_PASSTHROUGH_FIELDS = ("color_index", "linetype", "lineweight")
# Boolean-shaped fields: the native side parses job args via jsonFindNumber
# (strtod) for its "closed"/"is_write"-style 0/1 convention, which does NOT
# understand JSON true/false tokens -- coerce here so a caller can pass an
# idiomatic Python bool without silently becoming "false" on the wire.
_LAYER_FLAG_FIELDS = ("plottable", "frozen", "off", "locked")


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
    return None


def ir_op_for(ent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """No IR entity kind regenerates a symbol-table op yet; always None."""
    return None
