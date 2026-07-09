#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""N1 perturbation suite -- deterministic IR mutations that PROVE the
block-definition diff gate (tools/blockdef_diff.diff_block_definitions)
actually reacts to real damage.

A gate that never fires on a real perturbation is dead weight: this module
seeds exactly one known, arithmetic (never random) change per call so
``run_suite`` can measure the gate's conviction rate against a known-good IR
instead of trusting that the gate "should" work.

``def_rename`` is the deliberate exception: it renames a block definition AND
rewrites every ``block_reference`` that points at it in the same call, so the
result stays topologically consistent (nothing actually moved or vanished --
only a name changed). That is invisible to an anon-remap-aware diff
(``name_map=`` mapping the rename) by design; a plain diff without the
name_map still sees it, because names alone are not geometry.
"""

from __future__ import annotations

import copy
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

_TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import blockdef_diff  # noqa: E402

PERTURBATION_KINDS = (
    "entity_shift",
    "entity_delete",
    "entity_duplicate",
    "def_rename",
    "layer_swap",
)

_SHIFT_DX = 1.0
_SHIFT_DY = 0.0
_ALT_LAYER = "ARIADNE_PERTURB_LAYER"
_RENAME_SUFFIX = "__RENAMED"

_EntityTarget = Tuple[Dict[str, Any], List[Dict[str, Any]], int]


def catalog() -> List[str]:
    """Return the perturbation kinds this module can apply."""
    return list(PERTURBATION_KINDS)


def _def_entities_list(block_def: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    entities = block_def.get("def_entities")
    if entities is None:
        entities = block_def.get("entities")
    return entities if isinstance(entities, list) else None


def _entity_targets(doc: Dict[str, Any]) -> List[_EntityTarget]:
    """Flatten every (block_def, entities_list, entity_index) in the doc.

    Order is block_definitions order then def_entities order -- fixed by the
    doc's own structure, so picking by ``index`` is deterministic.
    """
    targets: List[_EntityTarget] = []
    for block_def in doc.get("block_definitions") or []:
        if not isinstance(block_def, dict):
            continue
        entities = _def_entities_list(block_def)
        if entities is None:
            continue
        for entity_idx, entity in enumerate(entities):
            if isinstance(entity, dict):
                targets.append((block_def, entities, entity_idx))
    return targets


def _pick_entity_target(doc: Dict[str, Any], index: int) -> _EntityTarget:
    targets = _entity_targets(doc)
    if not targets:
        raise ValueError("ir_doc has no def entities to perturb")
    return targets[index % len(targets)]


def _looks_like_point(value: Any) -> bool:
    return (
        isinstance(value, list)
        and 2 <= len(value) <= 3
        and all(isinstance(v, (int, float)) for v in value)
    )


def _shift_geometry(geometry: Dict[str, Any], dx: float, dy: float) -> None:
    """Translate every point-shaped field of a geometry dict by (dx, dy).

    Point-shaped: a 2-3 element numeric list (start/end/center/position/...),
    or a vertex list of ``{"point": [...]}`` dicts (lwpolyline-style). No
    kind-specific branching -- whichever fields look like a point move.
    """
    for key, value in geometry.items():
        if key == "kind":
            continue
        if _looks_like_point(value):
            value[0] += dx
            if len(value) > 1:
                value[1] += dy
        elif isinstance(value, list):
            for item in value:
                point = item.get("point") if isinstance(item, dict) else None
                if _looks_like_point(point):
                    point[0] += dx
                    if len(point) > 1:
                        point[1] += dy


def _swap_layer(current_layer: Any) -> str:
    return "0" if current_layer == _ALT_LAYER else _ALT_LAYER


def _iter_entity_lists(doc: Dict[str, Any]):
    top_entities = doc.get("entities")
    if isinstance(top_entities, list):
        yield top_entities
    for block_def in doc.get("block_definitions") or []:
        if not isinstance(block_def, dict):
            continue
        entities = _def_entities_list(block_def)
        if entities is not None:
            yield entities


def _rename_references(doc: Dict[str, Any], old_name: str, new_name: str) -> None:
    for entities in _iter_entity_lists(doc):
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            geometry = entity.get("geometry")
            if (
                isinstance(geometry, dict)
                and geometry.get("kind") == "block_reference"
                and geometry.get("block_name") == old_name
            ):
                geometry["block_name"] = new_name


def _rename_one_def(doc: Dict[str, Any], index: int) -> None:
    block_defs = [bd for bd in (doc.get("block_definitions") or []) if isinstance(bd, dict)]
    if not block_defs:
        raise ValueError("ir_doc has no block_definitions to rename")
    block_def = block_defs[index % len(block_defs)]
    old_name = block_def.get("name")
    new_name = "%s%s" % (old_name, _RENAME_SUFFIX)
    block_def["name"] = new_name
    _rename_references(doc, old_name, new_name)


def perturb(ir_doc: Dict[str, Any], kind: str, *, index: int = 0) -> Dict[str, Any]:
    """Return a deep copy of ``ir_doc`` with exactly one seeded perturbation of ``kind``."""
    if kind not in PERTURBATION_KINDS:
        raise ValueError(
            "unknown perturbation kind: %r (expected one of %s)" % (kind, PERTURBATION_KINDS)
        )

    doc = copy.deepcopy(ir_doc)

    if kind == "entity_shift":
        _, entities, entity_idx = _pick_entity_target(doc, index)
        geometry = entities[entity_idx].get("geometry")
        if isinstance(geometry, dict):
            _shift_geometry(geometry, _SHIFT_DX, _SHIFT_DY)

    elif kind == "entity_delete":
        _, entities, entity_idx = _pick_entity_target(doc, index)
        entities.pop(entity_idx)

    elif kind == "entity_duplicate":
        _, entities, entity_idx = _pick_entity_target(doc, index)
        entities.insert(entity_idx + 1, copy.deepcopy(entities[entity_idx]))

    elif kind == "def_rename":
        _rename_one_def(doc, index)

    elif kind == "layer_swap":
        _, entities, entity_idx = _pick_entity_target(doc, index)
        entity = entities[entity_idx]
        entity["layer"] = _swap_layer(entity.get("layer"))

    return doc


def run_suite(ir_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Perturb ``ir_doc`` once per catalog kind and report whether the
    block-definition diff gate reacts.

    ``blockdef_diff_reacts`` is True when ``diff_block_definitions(ir_doc,
    perturbed)`` shows any non-zero removed/added/modified count anywhere.
    ``fraction_delta`` is the drop from a perfect (1.0) interior match.
    """
    results: List[Dict[str, Any]] = []
    for kind in catalog():
        perturbed = perturb(ir_doc, kind)
        report = blockdef_diff.diff_block_definitions(ir_doc, perturbed)
        totals = report.get("totals") or {}
        mismatch = sum(
            int(row.get("removed", 0) or 0)
            + int(row.get("added", 0) or 0)
            + int(row.get("modified", 0) or 0)
            for row in report.get("per_def") or []
        )
        fraction = totals.get("interior_diff0_fraction")
        results.append(
            {
                "kind": kind,
                "blockdef_diff_reacts": mismatch > 0,
                "fraction_delta": (1.0 - fraction) if fraction is not None else None,
            }
        )
    return results
