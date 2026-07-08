#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from patch_ops import blocks as patch_ops_blocks  # noqa: E402

_FIXTURE = Path(_REPO) / "tests" / "fixtures" / "unsupported_kind_samples.json"
_UNSUPPORTED = "def_entity kind unsupported by write.block.append_entity"
_GRADIENT = _UNSUPPORTED + " (no gradient replay)"


def _samples() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))["samples"]


def _sample(kind: str, *, require_vertices: bool | None = None) -> dict:
    for ent in _samples()[kind]:
        loops = (ent.get("geometry") or {}).get("loops") or []
        has_vertices = bool(loops) and all(isinstance(loop, dict) and "vertices" in loop for loop in loops)
        if require_vertices is None or has_vertices == require_vertices:
            return copy.deepcopy(ent)
    raise AssertionError("fixture sample not found for %s require_vertices=%r" % (kind, require_vertices))


def test_hatch_serializer_emits_real_pattern_fields_and_loops_verbatim():
    ent = _sample("hatch", require_vertices=True)
    geom = ent["geometry"]

    op = patch_ops_blocks._def_entity_append_op("BLK", ent)

    assert op == {
        "operation": "append_block_entity",
        "args": {
            "block_name": "BLK",
            "layer": ent["layer"],
            "entity": {
                "kind": "hatch",
                "normal": geom["normal"],
                "elevation": geom["elevation"],
                "pattern_angle": geom["pattern_angle"],
                "pattern_scale": geom["pattern_scale"],
                "pattern_type": geom["pattern_type"],
                "hatch_style": geom["hatch_style"],
                "loop_count": geom["loop_count"],
                "pattern_name": geom["pattern_name"],
                "pattern_double": geom["pattern_double"],
                "is_solid_fill": geom["is_solid_fill"],
                "is_associative": geom["is_associative"],
                "is_gradient": geom["is_gradient"],
                "loops": geom["loops"],
            },
        },
    }


def test_gradient_hatch_defers_with_explicit_reason():
    ent = _sample("hatch", require_vertices=True)
    ent["geometry"]["is_gradient"] = True

    ops, deferred = patch_ops_blocks.block_def_ops({"name": "BLK", "handle": "B1", "def_entities": [ent]})

    assert [op["operation"] for op in ops] == ["create_block"]
    assert deferred == [{
        "block_name": "BLK",
        "def_entity_index": 0,
        "handle": ent["handle"],
        "kind": "hatch",
        "reason": _GRADIENT,
    }]


def test_face3d_serializer_emits_four_corners_and_visibility():
    ent = _sample("face3d")
    geom = ent["geometry"]

    op = patch_ops_blocks._def_entity_append_op("BLK", ent)

    assert op == {
        "operation": "append_block_entity",
        "args": {
            "block_name": "BLK",
            "layer": ent["layer"],
            "entity": {
                "kind": "face3d",
                "p0": geom["p0"],
                "p1": geom["p1"],
                "p2": geom["p2"],
                "p3": geom["p3"],
                "edge_visibility": geom["edge_visibility"],
            },
        },
    }


def test_wipeout_stays_deferred_with_generic_reason():
    ent = _sample("wipeout")

    ops, deferred = patch_ops_blocks.block_def_ops({"name": "BLK", "handle": "B2", "def_entities": [ent]})

    assert [op["operation"] for op in ops] == ["create_block"]
    assert deferred == [{
        "block_name": "BLK",
        "def_entity_index": 0,
        "handle": ent["handle"],
        "kind": "wipeout",
        "reason": _UNSUPPORTED,
    }]


def test_non_gradient_hatch_without_polyline_vertices_keeps_generic_reason():
    ent = _sample("hatch", require_vertices=False)

    ops, deferred = patch_ops_blocks.block_def_ops({"name": "BLK", "handle": "B3", "def_entities": [ent]})

    assert [op["operation"] for op in ops] == ["create_block"]
    assert deferred == [{
        "block_name": "BLK",
        "def_entity_index": 0,
        "handle": ent["handle"],
        "kind": "hatch",
        "reason": _UNSUPPORTED,
    }]
