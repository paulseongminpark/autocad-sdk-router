#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_ops.tables -- symbol-table write ops (CAD OS Layer, Lane E family
split).

Symbol-table ops (layer/linetype/dimstyle/textstyle). Only set_layer and
create_layer (both -> write.layer.create, ensuring the target layer exists)
have a live native handler today; linetype/dimstyle/textstyle await a family
ticket.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# patch op id -> native ObjectARX write op (operations.v2.json, status
# "implemented"). Only these have a live native handler today.
WRITE_OP_MAP: Dict[str, str] = {
    "set_layer": "write.layer.create",
    "create_layer": "write.layer.create",
}


def build_job_args(native_op: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Native job "args" for a symbol-table write op, or None if native_op
    isn't ours."""
    if native_op == "write.layer.create":
        # set_layer/create_layer -> ensure the target layer exists.
        out: Dict[str, Any] = {}
        name = args.get("name") or args.get("layer")
        if name is not None:
            out["name"] = name
        if "color_index" in args:
            out["color_index"] = args["color_index"]
        return out
    return None


def ir_op_for(ent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """No IR entity kind regenerates a symbol-table op yet; always None."""
    return None
