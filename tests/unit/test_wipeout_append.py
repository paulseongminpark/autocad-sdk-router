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
_EXTERNAL = _UNSUPPORTED + " (external raster image wipeout)"
_MISSING_CLIP = _UNSUPPORTED + " (missing clip_boundary)"


def _samples() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))["samples"]


def _sample(kind: str = "wipeout") -> dict:
    for ent in _samples()[kind]:
        return copy.deepcopy(ent)
    raise AssertionError("fixture sample not found for %s" % kind)


def test_wipeout_serializer_emits_real_fixture_fields_verbatim():
    ent = _sample()
    geom = ent["geometry"]

    op = patch_ops_blocks._def_entity_append_op("BLK", ent)

    assert op == {
        "operation": "append_block_entity",
        "args": {
            "block_name": "BLK",
            "layer": ent["layer"],
            "entity": {
                "kind": "wipeout",
                "origin": geom["origin"],
                "u_vector": geom["u_vector"],
                "v_vector": geom["v_vector"],
                "image_size": geom["image_size"],
                "clip_boundary_type": geom["clip_boundary_type"],
                "clip_boundary": geom["clip_boundary"],
                "source_file_name": geom["source_file_name"],
                "frame_on": geom["frame_on"],
            },
        },
    }


def test_wipeout_block_def_ops_emits_append_for_representable_fixture():
    ent = _sample()

    ops, deferred = patch_ops_blocks.block_def_ops(
        {"name": "BLK", "handle": "B1", "def_entities": [ent]})

    assert [op["operation"] for op in ops] == ["create_block", "append_block_entity"]
    assert deferred == []
    assert ops[1]["args"]["entity"]["kind"] == "wipeout"
    assert ops[1]["args"]["entity"]["clip_boundary"] == ent["geometry"]["clip_boundary"]


def test_external_source_file_name_defers_with_explicit_reason():
    ent = _sample()
    ent["geometry"]["source_file_name"] = r"C:\images\mask.tif"

    ops, deferred = patch_ops_blocks.block_def_ops(
        {"name": "BLK", "handle": "B2", "def_entities": [ent]})

    assert [op["operation"] for op in ops] == ["create_block"]
    assert deferred == [{
        "block_name": "BLK",
        "def_entity_index": 0,
        "handle": ent["handle"],
        "kind": "wipeout",
        "reason": _EXTERNAL,
    }]


def test_missing_clip_boundary_defers_with_explicit_reason():
    ent = _sample()
    ent["geometry"]["clip_boundary"] = []

    ops, deferred = patch_ops_blocks.block_def_ops(
        {"name": "BLK", "handle": "B3", "def_entities": [ent]})

    assert [op["operation"] for op in ops] == ["create_block"]
    assert deferred == [{
        "block_name": "BLK",
        "def_entity_index": 0,
        "handle": ent["handle"],
        "kind": "wipeout",
        "reason": _MISSING_CLIP,
    }]


def test_incomplete_wipeout_geometry_keeps_generic_reason():
    ent = _sample()
    del ent["geometry"]["u_vector"]

    ops, deferred = patch_ops_blocks.block_def_ops(
        {"name": "BLK", "handle": "B4", "def_entities": [ent]})

    assert [op["operation"] for op in ops] == ["create_block"]
    assert deferred == [{
        "block_name": "BLK",
        "def_entity_index": 0,
        "handle": ent["handle"],
        "kind": "wipeout",
        "reason": _UNSUPPORTED,
    }]
