"""IR -> cad_patch.v1 builder for perfect DWG roundtrip.

Converts a native_full dwg_graph_ir.json into a cad_patch.v1 whose operations
regenerate each model-space entity through the WIRED native write ops
(patch_engine.NATIVE_WRITE_OP_MAP). The per-entity-kind op-case logic (where
the IR's array geometry [x,y,z] is converted to the native job's object form
{x,y,z}, and the IR 'vertices' key is renamed to the native 'points' key) is
split by family under tools/patch_ops/ (PLAN F9); this module drives the
per-entity loop and is the single caller of that dispatch.

no-fake-success: an entity kind without a runnable write op (or, for dimension,
without extracted geometry) is reported in `deferred`, never silently emitted.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import patch_ops  # per-family op-case dispatch (PLAN F9)


def _op_for(ent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map one IR entity to a cad_patch operation, or None if not regenerable.

    Dispatches to the entity's family module under tools/patch_ops/ (PLAN F9).
    """
    return patch_ops.ir_op_for(ent)


def build_patch_from_ir(ir: Dict[str, Any], target_dwg: Dict[str, Any], patch_id: str,
                        kinds: Optional[set] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Build a (cad_patch.v1, deferred[]) pair from a native_full IR.

    kinds: optional set of geometry.kind to include (e.g. {"line","circle"} for a
    Tier-1a roundtrip); None = all kinds.
    """
    ops: List[Dict[str, Any]] = []
    deferred: List[Dict[str, Any]] = []
    # #129b block-def dependency: a fresh/seed regen target starts with none
    # of the source DWG's custom blocks, so a create_blockref for a name the
    # target can't resolve fails (native BLOCK_NOT_FOUND). Synthesize each
    # referenced block's definition (patch_ops.blocks.block_def_ops), once
    # per name, from this IR's own block_definitions[] -- ahead of the first
    # create_blockref that names it.
    block_defs_by_name = {
        bd.get("name"): bd for bd in (ir.get("block_definitions") or []) if bd.get("name")
    }
    emitted_block_defs: set = set()
    active_block_defs: List[str] = []
    block_def_step_counts: Dict[int, int] = {}
    cycle_notes_seen: set = set()

    def _emit_block_def(block_name: str, root_entity_index: int) -> None:
        if block_name in emitted_block_defs:
            return
        if block_name in active_block_defs:
            return
        block_def = block_defs_by_name.get(block_name)
        if block_def is None:
            return
        active_block_defs.append(block_name)
        try:
            for def_entity_index, def_ent in enumerate(block_def.get("def_entities") or []):
                nested_g = def_ent.get("geometry") or {}
                if nested_g.get("kind") != "block_reference":
                    continue
                nested_block_name = nested_g.get("block_name")
                if nested_block_name in emitted_block_defs:
                    continue
                if nested_block_name in active_block_defs:
                    cycle_start = active_block_defs.index(nested_block_name)
                    cycle_path = active_block_defs[cycle_start:] + [nested_block_name]
                    note = {
                        "block_name": block_name,
                        "reason": "definition cycle detected at %r via %s" % (
                            nested_block_name, " -> ".join(cycle_path)),
                    }
                    note_key = (note["block_name"], note["reason"])
                    if note_key not in cycle_notes_seen:
                        deferred.append(note)
                        cycle_notes_seen.add(note_key)
                    continue
                if nested_block_name not in block_defs_by_name:
                    deferred.append({
                        "block_name": block_name,
                        "def_entity_index": def_entity_index,
                        "kind": "block_reference",
                        "reason": "no block_definitions entry for nested block_name %r"
                                  % (nested_block_name,),
                    })
                    continue
                _emit_block_def(nested_block_name, root_entity_index)
            bd_ops, bd_deferred = patch_ops.blocks.block_def_ops(block_def)
            next_step = block_def_step_counts.get(root_entity_index, 0)
            for bd_op in bd_ops:
                bd_op["step_id"] = "bd%d_%d" % (root_entity_index, next_step)
                ops.append(bd_op)
                next_step += 1
            block_def_step_counts[root_entity_index] = next_step
            deferred.extend(bd_deferred)
            emitted_block_defs.add(block_name)
        finally:
            active_block_defs.pop()

    for i, ent in enumerate(ir.get("entities") or []):
        g = ent.get("geometry") or {}
        kind = g.get("kind")
        if kinds is not None and kind not in kinds:
            continue
        if kind == "block_reference":
            block_name = g.get("block_name")
            block_def = block_defs_by_name.get(block_name)
            if block_def is None:
                # No block_definitions source for this name -- emitting
                # create_blockref anyway would target a name the fresh seed
                # cannot resolve. Honest deferral, never the undeclared
                # 'insert_block' fallback this replaces.
                deferred.append({
                    "index": i, "handle": ent.get("handle"), "kind": kind,
                    "reason": "no block_definitions entry for block_name %r" % (block_name,),
                })
                continue
            if block_name not in emitted_block_defs:
                _emit_block_def(block_name, i)
        op = _op_for(ent)
        if op is None:
            deferred.append({"index": i, "handle": ent.get("handle"), "kind": kind})
            continue
        op["step_id"] = "e%d" % i
        ops.append(op)
    patch = {
        "schema": "ariadne.cad_patch.v1",
        "patch_id": patch_id,
        "title": "roundtrip regen from IR (%d ops)" % len(ops),
        "source_agent": "ir_to_patch",
        "target_dwg": target_dwg,
        "operations": ops,
        "postconditions": [{"subject": "entity_count", "op": "delta_ge", "value": 1}],
        "policy": {"staged_copy": True, "write_mode": "write_copy"},
    }
    return patch, deferred


def kind_counts(ir: Dict[str, Any]) -> Dict[str, int]:
    from collections import Counter
    c = Counter((e.get("geometry") or {}).get("kind") for e in ir.get("entities") or [])
    return dict(c)


if __name__ == "__main__":
    from collections import Counter
    ir_path = sys.argv[1]
    out_patch = sys.argv[2] if len(sys.argv) > 2 else None
    kinds = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
    ir = json.load(open(ir_path, encoding="utf-8-sig"))
    patch, deferred = build_patch_from_ir(
        ir, {"staged_path": "", "original_path": ""}, "cli", kinds)
    summary = {
        "ops": len(patch["operations"]),
        "deferred": len(deferred),
        "deferred_by_kind": dict(Counter(d["kind"] for d in deferred)),
        "ir_kinds": kind_counts(ir),
    }
    print(json.dumps(summary, ensure_ascii=False))
    if out_patch:
        with open(out_patch, "w", encoding="utf-8") as fh:
            json.dump(patch, fh, ensure_ascii=False)
        print("wrote", out_patch)
