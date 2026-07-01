#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_ops -- per-family split of patch_engine's native write-op map (CAD OS
Layer, Lane E; PLAN F9).

NATIVE_WRITE_OP_MAP and the _native_job_doc arg-branch logic used to live in
one file (patch_engine.py) for every op family; ir_to_patch's per-entity-kind
op-case logic did too. Both are split here by family so parallel writers can
add a new op to their own family module without touching a file another lane
is editing.

Family modules (each owns a DISJOINT op_id / native_op / IR-kind slice):
    entities.py -- entity write ops (line/circle/arc/text/polyline/dimension/...)
    blocks.py   -- block / insert / BTR ops
    tables.py   -- symbol-table ops (layer/linetype/dimstyle/textstyle)
    db.py       -- database / transform ops

Each family module exports:
    WRITE_OP_MAP: Dict[str, str]
        patch op id -> native ObjectARX write op (only entries with a live
        native handler; everything else is not_implemented, no-fake-success).
    build_job_args(native_op, args) -> Optional[Dict[str, Any]]
        native job "args" for native_op, or None if native_op isn't this
        family's (patch_engine._native_job_doc's old if/elif branch, per family).
    ir_op_for(ent) -> Optional[Dict[str, Any]]
        one IR entity -> a cad_patch operation, or None if not this family's
        kind (ir_to_patch._op_for's old if-chain, per family).

This package aggregates the four modules into the SAME NATIVE_WRITE_OP_MAP
patch_engine.py has always exposed (patch_engine.py's public API/symbols are
unchanged by the split) and dispatches build_job_args/ir_op_for across all
families for patch_engine.py and ir_to_patch.py respectively.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from . import blocks, db, entities, tables

_FAMILIES = (entities, blocks, tables, db)

# Aggregate of every family's WRITE_OP_MAP; must reproduce the pre-split
# NATIVE_WRITE_OP_MAP exactly (same keys, same values).
NATIVE_WRITE_OP_MAP: Dict[str, str] = {
    **entities.WRITE_OP_MAP,
    **blocks.WRITE_OP_MAP,
    **tables.WRITE_OP_MAP,
    **db.WRITE_OP_MAP,
}


def build_job_args(native_op: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Native job "args" for ``native_op``, trying each family in turn.

    Mirrors the pre-split _native_job_doc if/elif chain: the first family that
    recognizes native_op wins; an unrecognized native_op yields {} (unchanged
    from the original, where no branch matched).
    """
    for fam in _FAMILIES:
        result = fam.build_job_args(native_op, args)
        if result is not None:
            return result
    return {}


def ir_op_for(ent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map one IR entity to a cad_patch operation, trying each family in turn.

    Mirrors the pre-split ir_to_patch._op_for if-chain (line/circle/
    block_reference/text/polyline/dimension), now spread across families.
    """
    for fam in _FAMILIES:
        op = fam.ir_op_for(ent)
        if op is not None:
            return op
    return None
