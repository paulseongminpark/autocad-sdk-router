#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_ops.blocks -- block / insert / BTR write ops (CAD OS Layer, Lane E
family split).

p2-blockapp wave: two ops gain their first-ever patch_ops wiring.
  create_block         -> write.block.simple_create (createSimpleBlock,
                          AriadneNativeJob.cpp) -- creates a NEW named block
                          table record (idempotent: a no-op if the name
                          already exists) seeded with one hardcoded line;
                          already real/certified, just never exposed here.
  append_block_entity  -> write.block.append_entity (m08eHandleBlockAppend,
                          families/m08e_handlers.inc) -- graduated from an
                          always-rollback probe to a REAL, persisting write in
                          this same wave (see that file's header comment).
                          Appends one of {line,circle,arc,text} into a NAMED
                          block-table record (or model space if 'block_name'
                          is omitted).
insert_block (the block_reference IR-op-case) still degrades to
not_implemented / deferred (no-fake-success): INSERT itself is
create_blockref, wired in patch_ops.entities, not this family.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# patch op id -> native ObjectARX write op (operations.v2.json, status
# "implemented"). Only entries with a live native handler belong here.
WRITE_OP_MAP: Dict[str, str] = {
    "create_block": "write.block.simple_create",
    "append_block_entity": "write.block.append_entity",
}


def build_job_args(native_op: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Native job "args" for a block-family write op, or None if native_op
    isn't ours."""
    if native_op == "write.block.simple_create":
        out: Dict[str, Any] = {}
        if "name" in args:
            out["name"] = args["name"]
        return out
    if native_op == "write.block.append_entity":
        # Flat passthrough is correct here even though "entity" is itself a
        # nested {kind,...} object: m08eHandleBlockAppend/m08eBuildEntityForAppend
        # (m08e_handlers.inc) do their OWN nested jsonFindString/jsonFindObject
        # parsing of the "entity" sub-object out of the native job JSON, so no
        # per-field flattening belongs on the Python side.
        out = {}
        for k in ("block_name", "entity", "layer"):
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
    """Map one IR entity to a cad_patch operation, or None if not a block kind."""
    g = ent.get("geometry") or {}
    kind = g.get("kind")
    if kind == "block_reference":
        return {"operation": "insert_block",
                "args": {"name": g.get("block_name"), "position": _pt(g.get("position"))}}
    return None
