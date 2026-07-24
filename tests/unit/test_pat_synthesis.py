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

    # R4t vintage contract: .pat files live under pats/<digest>/<NAME>.pat
    # (leaf name stays <NAME>.pat for cwd resolution; vintages separate by
    # DIRECTORY). Identical zero-phase content -- here the same definitions
    # under case-variant names -- dedupes to ONE file.
    pat_paths = sorted(batch_dir.glob("pats/*/H3.pat"))
    assert len(pat_paths) == 1
    pat_path = pat_paths[0].resolve()
    # The .pat is zero-phase: every row is rebased against the seed row's
    # base (row1 [0, 1.25] -> [0, 0]; row2 [2, -3] -> [2, -4.25]) so the
    # per-hatch phase rides HPORIGIN instead of the name-shared .pat (R4n
    # census: 233/233 residual pairs were one shared-seed phase forced onto
    # per-hatch bases; runs/e2e_1dwg_R4n_origin_20260709).
    assert pat_path.read_text(encoding="utf-8") == (
        "*H3\n"
        "90, 0, 0, 0, 2.5, 0.5, -0.25, 0\n"
        "30, 2, -4.25, 2.38125, 4.1244459855, -1.25, 0.625\n"
    )

    job_paths = sorted((batch_dir / "jobs").glob("*.json"))
    assert len(job_paths) == 2
    for job_path in job_paths:
        job = json.loads(job_path.read_text(encoding="utf-8"))
        entity = job["args"]["entity"]
        assert entity["pattern_pat_path"] == pat_path.as_posix()
        assert os.path.isabs(entity["pattern_pat_path"])
        assert "\\" not in entity["pattern_pat_path"]


def test_batch_pat_synthesis_separates_vintages_by_digest_dir(tmp_path):
    # The H3 clobber defect (R4s, 154 X-grid hatches rendered as plus-grid):
    # same NAME + DIFFERENT row geometry must produce TWO files in different
    # digest dirs, each job pointing at its own vintage.
    defs_a = _pattern_definitions()
    defs_b = [{"angle": 0.25, "base": [0.0, 0.0], "offset": [0.0, 3.0],
               "dashes": [1.0, -0.5]}]
    op_a = {"operation": "append_block_entity",
            "args": {"block_name": "B", "layer": "0",
                     "entity": patch_ops_blocks._def_entity_append_op(
                         "B", _custom_hatch(pattern_name="H3",
                                            pattern_definitions=defs_a),
                     )["args"]["entity"]}}
    op_b = {"operation": "append_block_entity",
            "args": {"block_name": "B", "layer": "0",
                     "entity": patch_ops_blocks._def_entity_append_op(
                         "B", _custom_hatch(pattern_name="H3",
                                            pattern_definitions=defs_b),
                     )["args"]["entity"]}}

    out = pe._synthesize_batch_pat_files(str(tmp_path), [op_a, op_b])

    assert len(out) == 2
    paths = sorted(Path(p) for p in out.values())
    assert [p.name for p in paths] == ["H3.pat", "H3.pat"]
    assert paths[0].parent != paths[1].parent
    assert (op_a["args"]["entity"]["pattern_pat_path"]
            != op_b["args"]["entity"]["pattern_pat_path"])


def test_pat_lines_divide_out_baked_scale_and_never_emit_scientific_notation(tmp_path):
    # Regression for the R4i b037 evaluateHatch bomb: getPatternDefinitionAt
    # values carry the entity pattern_scale baked in, and %.10g wrote tiny
    # residues as "8.5e-14" which AutoCAD's .pat parser cannot read.
    geometry = _custom_hatch()["geometry"] if isinstance(_custom_hatch(), dict) and "geometry" in _custom_hatch() else None
    entity = _custom_hatch()
    geom = entity.get("geometry", entity)
    geom["pattern_scale"] = 300.0
    geom["pattern_definitions"] = [
        {"angle": 0.0, "base": [7429.999999999884, -5869.999999999971],
         "offset": [8.526512829121202e-14, 300.0], "dashes": []},
        {"angle": 1.5707963267948966, "base": [7429.999999999884, -5869.999999999971],
         "offset": [-300.0, 8.526512829121202e-14], "dashes": []},
    ]
    op = {"operation": "append_block_entity",
          "args": {"block_name": "B", "layer": "0", "entity": geom}}
    out = pe._synthesize_batch_pat_files(str(tmp_path), [op])
    assert len(out) == 1
    text = Path(next(iter(out.values()))).read_text(encoding="utf-8")
    assert "e-" not in text and "E-" not in text
    line = text.splitlines()[1]
    fields = [f.strip() for f in line.split(",")]
    # angle 0 / base and offset divided by 300 / near-zero clamped to literal 0
    assert fields[0] == "0"
    assert fields[3] == "0"
    assert abs(float(fields[4]) - 1.0) < 1e-9
    # Base is rebased against the seed row (zero-phase .pat): both rows share
    # the same base here, so both land at literal 0 after rebase + clamp.
    assert fields[1] == "0" and fields[2] == "0"

    # 90-degree row: world offset (-300, ~0) must land line-local as (0, 1) --
    # perpendicular spacing 1, never the "-1, 0" zero-spacing family that made
    # evaluateHatch refuse the whole hatch (Grok advisory #2 verdict).
    line90 = [f.strip() for f in text.splitlines()[2].split(",")]
    assert line90[0] == "90"
    assert line90[3] == "0"
    assert abs(float(line90[4]) - 1.0) < 1e-9
