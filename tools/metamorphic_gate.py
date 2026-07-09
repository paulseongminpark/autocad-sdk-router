#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Metamorphic equivariance gate for the blockdef_diff measure.

A sound geometry measure must be equivariant under a common rigid translation
applied to BOTH sides: verdicts (diff0_total and entity totals) must be
identical across offsets. This module applies a pure IR translation and
reports whether ``diff_block_definitions`` preserves its verdict.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Sequence, Tuple

import blockdef_diff

SCHEMA_ID = "ariadne.metamorphic_gate.v1"

# Geometry field -> coordinate shape. Used by translate_ir; unknown fields are
# left untouched. "base" lives inside pattern_definitions rows (see translator).
COORD_FIELDS: Dict[str, str] = {
    "start": "xyz_point",
    "end": "xyz_point",
    "position": "xyz_point",
    "center": "xyz_point",
    "insertion_point": "xyz_point",
    "vertices": "vertex_list",
    # "base" lives on pattern_definitions rows (world-space when type-1).
    "base": "xy_point",
    "pattern_origin": "xy_point",
    "pattern_definitions": "pattern_rows",
    "loops": "loops",
}

_DEFAULT_OFFSETS: Tuple[Tuple[float, float], ...] = (
    (0.0, 0.0),
    (12345.678, -9876.543),
    (1e6, 1e6),
)


def _translate_xy(pt: Any, dx: float, dy: float) -> Any:
    """Translate x,y of a numeric point list; leave z (and further) intact."""
    if not (isinstance(pt, list) and len(pt) >= 2):
        return pt
    if not all(isinstance(v, (int, float)) for v in pt[:2]):
        return pt
    out = list(pt)
    out[0] = float(out[0]) + dx
    out[1] = float(out[1]) + dy
    return out


def _translate_vertex_list(vertices: Any, dx: float, dy: float) -> Any:
    if not isinstance(vertices, list):
        return vertices
    out: List[Any] = []
    for item in vertices:
        if isinstance(item, dict) and "point" in item:
            row = dict(item)
            row["point"] = _translate_xy(item["point"], dx, dy)
            out.append(row)
        else:
            out.append(item)
    return out


def _translate_loops(loops: Any, dx: float, dy: float) -> Any:
    if not isinstance(loops, list):
        return loops
    out: List[Any] = []
    for loop in loops:
        if not isinstance(loop, dict):
            out.append(loop)
            continue
        nrow = dict(loop)
        if "point" in nrow:
            nrow["point"] = _translate_xy(nrow["point"], dx, dy)
        if "vertices" in nrow:
            nrow["vertices"] = _translate_vertex_list(nrow["vertices"], dx, dy)
        out.append(nrow)
    return out


def _pattern_type_float(geometry: Dict[str, Any]) -> Optional[float]:
    raw = geometry.get("pattern_type")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _translate_pattern_definitions(
    rows: Any, dx: float, dy: float, *, pattern_type: Optional[float]
) -> Any:
    """2d-translate row ``base`` when it is world-space (type-1 scale-baked).

    Type-2 (custom / unit .pat) bases live in unit pattern space; translating
    them by a world vector would break the phase-carrier fold in
    ``blockdef_diff._canonical_hatch_geometry``. Type-2 phase rides on
    ``pattern_origin`` (translated separately).
    """
    if not isinstance(rows, list):
        return rows
    # Unit-space rows (pattern_type == 2.0): leave base alone.
    translate_base = pattern_type != 2.0
    out: List[Any] = []
    for row in rows:
        if not isinstance(row, dict):
            out.append(row)
            continue
        nrow = dict(row)
        if translate_base and "base" in nrow:
            nrow["base"] = _translate_xy(nrow["base"], dx, dy)
        out.append(nrow)
    return out


def _translate_geometry(geometry: Dict[str, Any], dx: float, dy: float) -> Dict[str, Any]:
    g = dict(geometry)
    ptype = _pattern_type_float(g)
    for key, shape in COORD_FIELDS.items():
        if key not in g:
            continue
        if shape == "xyz_point" or shape == "xy_point":
            g[key] = _translate_xy(g[key], dx, dy)
        elif shape == "vertex_list":
            g[key] = _translate_vertex_list(g[key], dx, dy)
        elif shape == "loops":
            g[key] = _translate_loops(g[key], dx, dy)
        elif shape == "pattern_rows":
            g[key] = _translate_pattern_definitions(
                g[key], dx, dy, pattern_type=ptype
            )
    return g


def _translate_entity(entity: Dict[str, Any], dx: float, dy: float) -> Dict[str, Any]:
    out = dict(entity)
    geom = entity.get("geometry")
    if isinstance(geom, dict):
        out["geometry"] = _translate_geometry(geom, dx, dy)
    return out


def _translate_entity_list(entities: Any, dx: float, dy: float) -> Any:
    if not isinstance(entities, list):
        return entities
    return [
        _translate_entity(e, dx, dy) if isinstance(e, dict) else e
        for e in entities
    ]


def translate_ir(ir: dict, dx: float, dy: float) -> dict:
    """Pure deepcopy translation of every def_entity geometry (and modelspace).

    Never mutates ``ir``. Unknown geometry fields are left untouched.
    """
    out = copy.deepcopy(ir if isinstance(ir, dict) else {})
    for block_def in out.get("block_definitions") or []:
        if not isinstance(block_def, dict):
            continue
        if "def_entities" in block_def:
            block_def["def_entities"] = _translate_entity_list(
                block_def["def_entities"], dx, dy
            )
        if "entities" in block_def:
            block_def["entities"] = _translate_entity_list(
                block_def["entities"], dx, dy
            )
    modelspace = out.get("modelspace")
    if isinstance(modelspace, dict) and "entities" in modelspace:
        modelspace["entities"] = _translate_entity_list(
            modelspace["entities"], dx, dy
        )
    if isinstance(out.get("entities"), list):
        out["entities"] = _translate_entity_list(out["entities"], dx, dy)
    return out


def _verdict_key(totals: Dict[str, Any]) -> Tuple[Any, Any, Any]:
    return (
        totals.get("diff0_total"),
        totals.get("a_entity_total"),
        totals.get("b_entity_total"),
    )


def measure_equivariance_report(
    a_ir: dict,
    b_ir: dict,
    *,
    offsets: Sequence[Tuple[float, float]] = _DEFAULT_OFFSETS,
) -> dict:
    """Translate both IRs by each offset and compare blockdef_diff totals."""
    offset_list = [tuple(map(float, pair)) for pair in offsets]
    verdicts: List[Dict[str, Any]] = []
    for dx, dy in offset_list:
        a_t = translate_ir(a_ir, dx, dy)
        b_t = translate_ir(b_ir, dx, dy)
        report = blockdef_diff.diff_block_definitions(a_t, b_t)
        verdicts.append(dict(report.get("totals") or {}))

    baseline = verdicts[0] if verdicts else {}
    keys = [_verdict_key(v) for v in verdicts]
    equivariant = bool(keys) and all(k == keys[0] for k in keys)

    return {
        "schema": SCHEMA_ID,
        "offsets": [[dx, dy] for dx, dy in offset_list],
        "verdicts": verdicts,
        "equivariant": equivariant,
        "baseline": baseline,
    }
