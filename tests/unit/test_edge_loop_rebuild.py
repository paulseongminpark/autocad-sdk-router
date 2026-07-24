#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from patch_ops import blocks as patch_ops_blocks  # noqa: E402


def _polyline_loop() -> dict:
    return {
        "index": 0,
        "loop_type": 7,
        "closed": True,
        "status": "ok",
        "vertices": [
            {"point": [0.0, 0.0], "bulge": 0.0},
            {"point": [2.0, 0.0], "bulge": 0.0},
            {"point": [2.0, 1.0], "bulge": 0.0},
        ],
    }


def _edge_loop(*edges: dict) -> dict:
    return {
        "index": 0,
        "loop_type": 5,
        "closed": True,
        "status": "ok",
        "edges": list(edges),
    }


def _base_hatch(*, pattern_name: str = "DASH", loops: list[dict], pattern_definitions=None) -> dict:
    geometry = {
        "kind": "hatch",
        "normal": [0.0, 0.0, 1.0],
        "elevation": 0.0,
        "pattern_angle": 0.0,
        "pattern_scale": 1.0,
        "pattern_type": 1.0,
        "hatch_style": 1.0,
        "loop_count": float(len(loops)),
        "pattern_name": pattern_name,
        "pattern_double": False,
        "is_solid_fill": False,
        "is_associative": False,
        "is_gradient": False,
        "loops": loops,
    }
    if pattern_definitions is not None:
        geometry["pattern_definitions"] = pattern_definitions
    return {"handle": "H1", "layer": "0", "geometry": geometry}


def test_hatch_serializer_emits_supported_edge_loops_verbatim():
    loop = _edge_loop(
        {"type": "line", "start": [0.0, 0.0], "end": [1.0, 0.0]},
        {
            "type": "arc",
            "center": [1.0, 1.0],
            "radius": 1.0,
            "start_angle": -math.pi / 2.0,
            "end_angle": 0.0,
            "ccw": True,
        },
        {
            "type": "ellipse",
            "center": [3.0, 2.0],
            "major": [2.0, 0.0],
            "ratio": 0.5,
            "start_angle": 0.0,
            "end_angle": math.pi / 2.0,
            "ccw": True,
        },
        {
            "type": "spline",
            "degree": 2,
            "control": [[0.0, 0.0], [0.5, 0.25], [1.0, 1.0]],
            "knots": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
            "rational": False,
            "weights": [],
        },
    )
    ent = _base_hatch(loops=[loop])

    op = patch_ops_blocks._def_entity_append_op("BLK", ent)

    assert op is not None
    assert op["args"]["entity"]["kind"] == "hatch"
    assert op["args"]["entity"]["loops"] == ent["geometry"]["loops"]


def test_hatch_with_unsupported_edge_type_defers_with_distinct_reason():
    ent = _base_hatch(loops=[_edge_loop({"type": "unsupported_77"})])

    ops, deferred = patch_ops_blocks.block_def_ops({"name": "BLK", "handle": "B1", "def_entities": [ent]})

    assert [op["operation"] for op in ops] == ["create_block"]
    assert deferred == [{
        "block_name": "BLK",
        "def_entity_index": 0,
        "handle": ent["handle"],
        "kind": "hatch",
        "reason": ("def_entity kind unsupported by write.block.append_entity"
                   " (unsupported edge type in loop)"),
    }]


def test_hatch_serializer_polyline_only_behavior_unchanged():
    ent = _base_hatch(loops=[_polyline_loop()])

    op = patch_ops_blocks._def_entity_append_op("BLK", ent)

    assert op is not None
    assert op["args"]["entity"]["loops"] == ent["geometry"]["loops"]
    assert "pattern_definitions" not in op["args"]["entity"]


def test_custom_pattern_edge_loop_with_pattern_definitions_emits():
    definitions = [{
        "angle": math.pi / 6.0,
        "base": [2.0, -3.0],
        "offset": [0.0, 4.7625],
        "dashes": [-1.25, 0.625],
    }]
    loop = _edge_loop({
        "type": "spline",
        "degree": 2,
        "control": [[0.0, 0.0], [0.5, 0.25], [1.0, 1.0]],
        "knots": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
        "rational": False,
        "weights": [],
    })
    ent = _base_hatch(pattern_name="H3", loops=[loop], pattern_definitions=definitions)

    op = patch_ops_blocks._def_entity_append_op("BLK", ent)

    assert op is not None
    assert op["args"]["entity"]["loops"] == ent["geometry"]["loops"]
    assert op["args"]["entity"]["pattern_definitions"] == definitions
