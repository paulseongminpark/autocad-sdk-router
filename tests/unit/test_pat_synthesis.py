#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import patch_engine as pe  # noqa: E402
from patch_ops import blocks as patch_ops_blocks  # noqa: E402


def _pattern_definitions() -> list[dict]:
    return [
        {
            "angle": math.pi / 2.0,
            "base": [0.0, 1.25],
            "offset": [-2.5, 0.0],
            "dashes": [0.5, -0.25, 0.0],
        },
        {
            "angle": math.pi / 6.0,
            "base": [2.0, -3.0],
            "offset": [0.0, 4.7625],
            "dashes": [-1.25, 0.625],
        },
    ]


def _custom_hatch(*, pattern_name: str = "H3", pattern_definitions=None) -> dict:
    geometry = {
        "kind": "hatch",
        "normal": [0.0, 0.0, 1.0],
        "elevation": 0.0,
        "pattern_angle": 0.0,
        "pattern_scale": 1.0,
        "pattern_type": 1.0,
        "hatch_style": 1.0,
        "loop_count": 1.0,
        "pattern_name": pattern_name,
        "pattern_double": False,
        "is_solid_fill": False,
        "is_associative": False,
        "is_gradient": False,
        "loops": [{
            "index": 0,
            "loop_type": 7,
            "closed": True,
            "status": "ok",
            "vertices": [
                {"point": [0.0, 0.0], "bulge": 0.0},
                {"point": [1.0, 0.0], "bulge": 0.0},
                {"point": [1.0, 1.0], "bulge": 0.0},
            ],
        }],
    }
    if pattern_definitions is not None:
        geometry["pattern_definitions"] = pattern_definitions
    return {"handle": "H1", "layer": "0", "geometry": geometry}


def _batch_record(index: int, pattern_name: str, pattern_definitions: list[dict]) -> dict:
    return {
        "index": index,
        "step_id": "s%d" % index,
        "native_op": "write.block.append_entity",
        "args": {
            "block_name": "BLK",
            "layer": "0",
            "entity": patch_ops_blocks._def_entity_append_op(
                "BLK",
                _custom_hatch(pattern_name=pattern_name, pattern_definitions=pattern_definitions),
            )["args"]["entity"],
        },
        "batch_marker_id": "s%d" % index,
    }


def test_custom_hatch_with_pattern_definitions_emits_and_without_still_defers():
    definitions = _pattern_definitions()
    emitted = patch_ops_blocks._def_entity_append_op(
        "BLK",
        _custom_hatch(pattern_name="H3", pattern_definitions=definitions),
    )
    assert emitted is not None
    assert emitted["args"]["entity"]["pattern_definitions"] == definitions

    missing = _custom_hatch(pattern_name="H3")
    assert patch_ops_blocks._def_entity_append_op("BLK", missing) is None
    assert "custom hatch pattern replay pending .pat synthesis" in (
        patch_ops_blocks._def_entity_append_reason(missing)
    )

    empty = _custom_hatch(pattern_name="H3", pattern_definitions=[])
    assert patch_ops_blocks._def_entity_append_op("BLK", empty) is None


def test_batch_pat_synthesis_writes_exact_content_and_dedupes_names(monkeypatch, tmp_path):
    native_bin = tmp_path / "native"
    native_bin.mkdir()
    for leaf in ("Ariadne.AcadNativeDbx.dbx", "Ariadne.AcadNative.crx"):
        (native_bin / leaf).write_text("", encoding="utf-8")
    monkeypatch.setattr(pe, "_resolve_native_acad_module", lambda leaf: str(native_bin / leaf))

    definitions = _pattern_definitions()
    batch_dir = tmp_path / "batch"
    records = [
        _batch_record(0, "h3", definitions),
        _batch_record(1, "H3", definitions),
    ]

    pe._build_native_batch_script(str(batch_dir), "b001", records)

    pat_path = (batch_dir / "H3.pat").resolve()
    assert pat_path.read_text(encoding="utf-8") == (
        "*H3\n"
        "90, 0, 1.25, -2.5, 0, 0.5, -0.25, 0\n"
        "30, 2, -3, 0, 4.7625, -1.25, 0.625\n"
    )
    assert [path.name for path in batch_dir.glob("*.pat")] == ["H3.pat"]

    job_paths = sorted((batch_dir / "jobs").glob("*.json"))
    assert len(job_paths) == 2
    for job_path in job_paths:
        job = json.loads(job_path.read_text(encoding="utf-8"))
        entity = job["args"]["entity"]
        assert entity["pattern_pat_path"] == pat_path.as_posix()
        assert os.path.isabs(entity["pattern_pat_path"])
        assert "\\" not in entity["pattern_pat_path"]
