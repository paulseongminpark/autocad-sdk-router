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
_BUILDER_PENDING = _UNSUPPORTED + " (native wipeout builder pending)"


def _samples() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))["samples"]


def _sample(kind: str = "wipeout") -> dict:
    for ent in _samples()[kind]:
        return copy.deepcopy(ent)
    raise AssertionError("fixture sample not found for %s" % kind)


def test_wipeout_defers_until_native_builder_lands():
    # Serializer readiness is NOT emission: R4k b017 measured the CRX
    # rejecting kind=wipeout (UNSUPPORTED_KIND - m08e has no AcDbWipeout
    # builder). Representable fixtures defer with the pending-builder reason
    # until the native side actually exists.
    ent = _sample()

    assert patch_ops_blocks._def_entity_append_op("BLK", ent) is None

    ops, deferred = patch_ops_blocks.block_def_ops(
        {"name": "BLK", "handle": "B1", "def_entities": [ent]})
    assert [op["operation"] for op in ops] == ["create_block"]
    assert deferred == [{
        "block_name": "BLK",
        "def_entity_index": 0,
        "handle": ent["handle"],
        "kind": "wipeout",
        "reason": _BUILDER_PENDING,
    }]


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


def test_incomplete_wipeout_geometry_defers_with_pending_reason():
    # Missing u_vector but clip present: still a wipeout the FUTURE native
    # builder owns, so it shares the pending-builder reason (external-source
    # and missing-clip keep their finer reasons above).
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
        "reason": _BUILDER_PENDING,
    }]
