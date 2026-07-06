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
create_blockref (write.entity.blockref, the INSERT itself) is registered in
patch_ops.entities (its kind=="block_reference" IR-op-case), not this
family -- w3-insert wired the WRITE_OP_MAP/build_job_args side there, but
(cb2-irmap/#129b) the ir_op_for side was never added, so this module's own
ir_op_for used to fill the gap with an "insert_block" op id no registry
entry declares (regen/journal.json's "insert_block is not declared"
warning -- an active fake-success this module's own docstring already
called out as merely "degrading to deferred", which the code did not
actually do). Fixed by adding the missing case to entities.py and deleting
it here; this family's ir_op_for now returns None for every kind (it maps
no IR kind of its own).

p3-insattr (same wave, concurrent lane) independently wired the SAME native
op under a second patch-op id: create_block_simple (write.block.
simple_create), used as the setup step for an ATTDEF-in-block-definition +
INSERT-with-attributes multi-op patch (see op_roundtrip_probe.py's
probe_insert_attributes_roundtrip). Both aliases are kept -- each lane's
oracle/probe references its own id, and two patch-op ids mapping to one
native op is an established pattern (create_polyline2d).

cb2-irmap/#129b block-def dependency: create_blockref only succeeds against
a target whose block table already has the referenced name (m08g_handlers.
inc's write.entity.blockref branch returns BLOCK_NOT_FOUND otherwise) --
true for a fresh/blank regen seed, which starts with none of the source
DWG's custom blocks. block_def_ops() below synthesizes that block-def (a
create_block plus one append_block_entity per def_entity write.block.
append_entity's native handler can represent) from the source IR's own
block_definitions[] entry, so ir_to_patch.build_patch_from_ir can emit it
ahead of the first create_blockref referencing that name.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# patch op id -> native ObjectARX write op (operations.v2.json, status
# "implemented"). Only entries with a live native handler belong here.
WRITE_OP_MAP: Dict[str, str] = {
    "create_block": "write.block.simple_create",
    "append_block_entity": "write.block.append_entity",
    "create_block_simple": "write.block.simple_create",
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
    """Block family maps no IR entity ``kind`` of its own -- create_blockref
    (kind=="block_reference") is entities.py's case; see module docstring."""
    return None


def _def_entity_append_op(block_name: str, def_ent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One block_definitions[].def_entities[] item -> an append_block_entity
    op targeting ``block_name``, or None if this def_entity's kind is not one
    of the 4 kinds write.block.append_entity's native handler
    (m08eBuildEntityForAppend) can build: line/circle/arc/text."""
    g = def_ent.get("geometry") or {}
    kind = g.get("kind")
    layer = def_ent.get("layer")
    entity: Optional[Dict[str, Any]] = None
    if kind == "line":
        entity = {"kind": "line", "start": _pt(g.get("start")), "end": _pt(g.get("end"))}
    elif kind == "circle":
        entity = {"kind": "circle", "center": _pt(g.get("center")), "radius": g.get("radius")}
    elif kind == "arc":
        entity = {"kind": "arc", "center": _pt(g.get("center")), "radius": g.get("radius"),
                  "start_angle": g.get("start_angle"), "end_angle": g.get("end_angle")}
    elif kind == "text":
        entity = {"kind": "text", "position": _pt(g.get("position")), "text": g.get("text"),
                  "height": g.get("height", 2.5)}
    if entity is None:
        return None
    return {"operation": "append_block_entity",
            "args": {"block_name": block_name, "entity": entity, "layer": layer}}


def block_def_ops(block_def: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """One IR block_definitions[] entry -> (ops, deferred) that synthesize
    that block definition in a fresh/seed target: a create_block (idempotent
    BTR creation, see WRITE_OP_MAP's comment) followed by one
    append_block_entity per def_entity write.block.append_entity's native
    handler can represent. A def_entity of an unsupported kind, or a
    block_definitions entry with no inlined def_entities at all (schema
    allows content to live via owner_handle instead -- not followed here),
    is reported in ``deferred``, never silently dropped (no-fake-success).
    """
    name = block_def.get("name")
    ops: List[Dict[str, Any]] = [{"operation": "create_block", "args": {"name": name}}]
    deferred: List[Dict[str, Any]] = []
    def_entities = block_def.get("def_entities") or []
    if not def_entities:
        deferred.append({
            "block_name": name, "def_entity_index": None, "handle": block_def.get("handle"),
            "kind": None,
            "reason": "block_definitions entry has no inlined def_entities "
                      "(content may live via owner_handle, not lifted here)",
        })
    for i, def_ent in enumerate(def_entities):
        op = _def_entity_append_op(name, def_ent)
        if op is None:
            deferred.append({
                "block_name": name, "def_entity_index": i, "handle": def_ent.get("handle"),
                "kind": (def_ent.get("geometry") or {}).get("kind"),
                "reason": "def_entity kind unsupported by write.block.append_entity",
            })
            continue
        ops.append(op)
    return ops, deferred
