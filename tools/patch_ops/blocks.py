#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_ops.blocks -- block / insert / BTR write ops (CAD OS Layer, Lane E
family split).

No patch op in this family has a live native write handler yet; insert_block
(the block_reference IR-op-case) degrades to not_implemented / deferred
(no-fake-success) until a family ticket wires a native write.block.* op.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# patch op id -> native ObjectARX write op. Empty until a block/insert/BTR op
# lands (mirrors patch_ops.entities.WRITE_OP_MAP's shape for the next family).
WRITE_OP_MAP: Dict[str, str] = {}


def build_job_args(native_op: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """No block-family native op is wired yet; always None (not our native_op)."""
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
