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
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import patch_ops  # per-family op-case dispatch (PLAN F9)

# *D<n> anonymous defs are per-dimension rendered caches (LEX-0001): the
# rebuilt drawing's dimensions mint their own fresh *D records, so census
# caches are never re-emitted -- including by the orphan-def sweep below.
_DIM_CACHE_NAME = re.compile(r"^\*D\d+$")
from patch_ops.xdata import build_xdata_ops


def _op_for(ent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map one IR entity to a cad_patch operation, or None if not regenerable.

    Dispatches to the entity's family module under tools/patch_ops/ (PLAN F9).
    """
    return patch_ops.ir_op_for(ent)


def _is_anonymous_block_name(block_name: Any, block_def: Optional[Dict[str, Any]] = None) -> bool:
    return bool((block_def or {}).get("anonymous")) or (
        isinstance(block_name, str) and block_name.startswith("*"))


def _anon_clone_base_name(block_name: str) -> str:
    sanitized = "".join(
        ch if ch.isalnum() else "_"
        for ch in block_name
        if ch != "*"
    )
    return "ARIADNE_ANON_" + sanitized


def _build_anon_remap(ir: Dict[str, Any],
                      block_defs_by_name: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    # Reserve every known BTR name so clone synthesis never collides with the
    # source drawing's existing records.
    reserved_names = set(block_defs_by_name)
    for record in (ir.get("block_table_records") or []):
        if not isinstance(record, dict):
            continue
        name = record.get("name")
        if isinstance(name, str):
            reserved_names.add(name)

    remap: Dict[str, str] = {}
    anon_names = sorted(
        name for name, block_def in block_defs_by_name.items()
        if _is_anonymous_block_name(name, block_def)
    )
    for name in anon_names:
        base_name = _anon_clone_base_name(name)
        clone_name = base_name
        suffix = 2
        while clone_name in reserved_names:
            clone_name = "%s_%d" % (base_name, suffix)
            suffix += 1
        remap[name] = clone_name
        reserved_names.add(clone_name)
    return remap


def build_patch_from_ir(ir: Dict[str, Any], target_dwg: Dict[str, Any], patch_id: str,
                        kinds: Optional[set] = None,
                        include_xdata: bool = False) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
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
    anon_remap = _build_anon_remap(ir, block_defs_by_name)
    emitted_block_defs: set = set()
    handle_map: Dict[Any, Any] = {}
    active_block_defs: List[str] = []
    block_def_step_counts: Dict[int, int] = {}
    cycle_notes_seen: set = set()

    def _emit_block_name(block_name: Any) -> Any:
        return anon_remap.get(block_name, block_name)

    def _block_def_for_emit(block_name: str) -> Dict[str, Any]:
        block_def = block_defs_by_name[block_name]
        emitted_name = _emit_block_name(block_name)
        emitted_def = dict(block_def)
        emitted_def["name"] = emitted_name
        emitted_entities: List[Dict[str, Any]] = []
        for def_ent in (block_def.get("def_entities") or []):
            g = def_ent.get("geometry") or {}
            if g.get("kind") != "block_reference":
                emitted_entities.append(def_ent)
                continue
            nested_name = g.get("block_name")
            emitted_nested_name = _emit_block_name(nested_name)
            if emitted_nested_name == nested_name:
                emitted_entities.append(def_ent)
                continue
            emitted_ent = dict(def_ent)
            emitted_g = dict(g)
            emitted_g["block_name"] = emitted_nested_name
            emitted_ent["geometry"] = emitted_g
            emitted_entities.append(emitted_ent)
        emitted_def["def_entities"] = emitted_entities
        return emitted_def

    def _entity_for_emit(ent: Dict[str, Any]) -> Dict[str, Any]:
        g = ent.get("geometry") or {}
        if g.get("kind") != "block_reference":
            return ent
        emitted_name = _emit_block_name(g.get("block_name"))
        if emitted_name == g.get("block_name"):
            return ent
        emitted_ent = dict(ent)
        emitted_g = dict(g)
        emitted_g["block_name"] = emitted_name
        emitted_ent["geometry"] = emitted_g
        return emitted_ent

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
            bd_ops, bd_deferred = patch_ops.blocks.block_def_ops(_block_def_for_emit(block_name))
            next_step = block_def_step_counts.get(root_entity_index, 0)
            for bd_op in bd_ops:
                # Nested block_reference appends are only sound when their
                # target definition was actually synthesized (dependency
                # order guarantees it is already in emitted_block_defs).
                # Anonymous/missing/cycle targets never got emitted -- the
                # native append would fail-loud on a missing block table
                # record and abort the whole batch, so defer honestly here.
                bd_ent = ((bd_op.get("args") or {}).get("entity") or {})
                if (bd_op.get("operation") == "append_block_entity"
                        and bd_ent.get("kind") == "block_reference"
                        and bd_ent.get("block_name") not in emitted_block_defs):
                    deferred.append({
                        "block_name": block_name,
                        "kind": "block_reference",
                        "reason": "nested block_reference append skipped: target %r "
                                  "not synthesized (anonymous/missing/cycle)"
                                  % (bd_ent.get("block_name"),),
                    })
                    continue
                bd_op["step_id"] = "bd%d_%d" % (root_entity_index, next_step)
                ops.append(bd_op)
                next_step += 1
            block_def_step_counts[root_entity_index] = next_step
            deferred.extend(bd_deferred)
            emitted_block_defs.add(block_name)
            remapped_name = anon_remap.get(block_name)
            if remapped_name:
                emitted_block_defs.add(remapped_name)
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
            if block_name not in emitted_block_defs:
                # _emit_block_def declined (cycle): a
                # create_blockref would target a name the seed cannot
                # resolve -- defer the INSERT honestly.
                deferred.append({
                    "index": i, "handle": ent.get("handle"), "kind": kind,
                    "reason": "block definition %r not synthesizable "
                              "(cycle) - INSERT deferred" % (block_name,),
                })
                continue
        op = _op_for(_entity_for_emit(ent))
        if op is None:
            deferred.append({"index": i, "handle": ent.get("handle"), "kind": kind})
            continue
        op["step_id"] = "e%d" % i
        ops.append(op)
        if ent.get("handle"):
            handle_map[ent.get("handle")] = op["step_id"]
    if kinds is None:
        # Orphan-def sweep (R4s removed-28 finding): reference-reachability
        # alone misses defs that are authored content but never INSERTed --
        # measured on 1.dwg: DIMDOT + _ArchTick (referenced only from *D
        # dimension caches, which the rebuild intentionally never emits,
        # LEX-0001) and two unreferenced defs (...$0$ins-l, ...$0$ng), 4 defs
        # / 28 entities scored removed on every R4 run. Emit every remaining
        # non-*D-cache definition after the entity stream so the rebuilt
        # drawing carries the full authored block table. Skipped for
        # kind-filtered (tiered) runs, which are deliberately partial.
        sweep_root = len(ir.get("entities") or [])
        for block_name in sorted(block_defs_by_name):
            if block_name in emitted_block_defs:
                continue
            if _DIM_CACHE_NAME.match(block_name or ""):
                continue
            _emit_block_def(block_name, sweep_root)
    if include_xdata:
        xdata_ops, xdata_deferred = build_xdata_ops(ir, handle_map)
        for j, xdata_op in enumerate(xdata_ops):
            xdata_op["step_id"] = "xd%d" % j
            ops.append(xdata_op)
        deferred.extend(xdata_deferred)
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
    if anon_remap:
        patch["anon_remap"] = {
            name: anon_remap[name] for name in sorted(anon_remap)
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
