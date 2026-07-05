#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_ops.blocks -- block / insert / BTR write ops (CAD OS Layer, Lane E
family split).

p3-insattr adds the first live entry: create_block_simple (write.block.
simple_create) -- creates a NAMED block table record if it doesn't already
exist (idempotent: re-running with the same name is a no-op, not an error),
used as the setup step for an ATTDEF-in-block-definition + INSERT-with-
attributes multi-op patch (see op_roundtrip_probe.py's
probe_insert_attributes_roundtrip). create_blockref (write.entity.blockref,
the INSERT itself) is registered in patch_ops.entities instead -- a pre-
existing placement from the w3-insert wave, not moved here to avoid an
unrelated refactor.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# patch op id -> native ObjectARX write op (mirrors patch_ops.entities.
# WRITE_OP_MAP's shape).
WRITE_OP_MAP: Dict[str, str] = {
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
