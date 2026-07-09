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
_INCOMPLETE = _UNSUPPORTED + " (incomplete wipeout geometry)"


def _samples() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))["samples"]


def _sample(kind: str = "wipeout") -> dict:
    for ent in _samples()[kind]:
        return copy.deepcopy(ent)
    raise AssertionError("fixture sample not found for %s" % kind)


def test_representable_wipeout_emits_cert_proven_payload():
    # Live-certified 2026-07-09 (runs/wipeout_cert_census_20260709): this
    # exact field set appended handle 290 into WIPEOUT_CERT_BLK and the census
    # re-extraction matched the fixture geometry bit-for-bit. Emission mirrors
    # that cert payload -- nothing more (image_size/frame_on are not builder
    # inputs; frame_on has no public AcDbWipeout setter).
    ent = _sample()
    g = ent["geometry"]

    op = patch_ops_blocks._def_entity_append_op("BLK", ent)

    assert op == {
        "operation": "append_block_entity",
        "args": {
            "block_name": "BLK",
            "entity": {
                "kind": "wipeout",
                "origin": list(g["origin"]),
                "u_vector": list(g["u_vector"]),
                "v_vector": list(g["v_vector"]),
                "clip_boundary_type": g["clip_boundary_type"],
                "clip_boundary": g["clip_boundary"],
            },
            "layer": ent["layer"],
        },
    }

    ops, deferred = patch_ops_blocks.block_def_ops(
        {"name": "BLK", "handle": "B1", "def_entities": [ent]})
    assert [o["operation"] for o in ops] == ["create_block", "append_block_entity"]
    assert deferred == []


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


def test_incomplete_wipeout_geometry_defers_with_incomplete_reason():
    # Missing u_vector but clip present: the builder is live, but this input
    # cannot fill the cert-proven payload -- defer honestly as incomplete
    # geometry (external-source and missing-clip keep their finer reasons).
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
        "reason": _INCOMPLETE,
    }]
