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
    # The real 1.dwg sample carries a DRAWING-CUSTOM pattern name (H1) which
    # now defers until .pat synthesis lands - assert that first, then run the
    # verbatim-emission check on a standard-pattern variant of the same data.
    assert patch_ops_blocks._def_entity_append_op("BLK", ent) is None
    ent["geometry"]["pattern_name"] = "DASH"
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


def test_custom_pattern_hatch_defers_until_pat_synthesis():
    # H3 x181 on 1.dwg: not in headless acad.pat -> setPattern errorstatus 3
    # aborted batch b157 on R4f. Custom names defer; standard names emit.
    base = {
        "kind": "hatch", "normal": [0.0, 0.0, 1.0], "elevation": 0.0,
        "pattern_angle": 0.0, "pattern_scale": 1.0, "pattern_type": 1.0,
        "hatch_style": 1.0, "loop_count": 1.0, "pattern_double": False,
        "is_solid_fill": False, "is_associative": False, "is_gradient": False,
        "loops": [{"index": 0, "loop_type": 7, "closed": True, "status": "ok",
                   "vertices": [{"point": [0.0, 0.0]}, {"point": [1.0, 0.0]},
                                 {"point": [1.0, 1.0]}]}],
    }
    custom = {"handle": "H", "layer": "0", "geometry": dict(base, pattern_name="H3")}
    assert patch_ops_blocks._def_entity_append_op("B", custom) is None
    assert "custom hatch pattern replay pending" in patch_ops_blocks._def_entity_append_reason(custom)
    standard = {"handle": "H", "layer": "0", "geometry": dict(base, pattern_name="DASH")}
    assert patch_ops_blocks._def_entity_append_op("B", standard) is not None
    solid = {"handle": "H", "layer": "0",
             "geometry": dict(base, pattern_name="SOLID", is_solid_fill=True)}
    assert patch_ops_blocks._def_entity_append_op("B", solid) is not None


def test_hatch_pattern_origin_passes_through_when_present():
    # Live cert 2026-07-09 (runs/hatch_origin_cert3_20260709): originPoint()
    # round-trips setOriginPoint exactly, and the original 1.dwg census reads
    # 27/265 hatches with nonzero per-hatch origins (HPORIGIN). The serializer
    # replays whatever the census recorded.
    ent = _sample("hatch", require_vertices=True)
    ent["geometry"]["pattern_origin"] = [-356718.6693916272, 148665.00000000006]

    op = patch_ops_blocks._def_entity_append_op("BLK", ent)

    if op is None:
        # Drawing-custom pattern without definitions defers -- make the
        # sample emittable the same way the custom-pat tests do.
        ent["geometry"]["pattern_definitions"] = [
            {"angle": 1.5707963267948966, "base": [0.0, 0.0],
             "offset": [-1.0, 0.0], "dashes": []}]
        op = patch_ops_blocks._def_entity_append_op("BLK", ent)
    assert op is not None
    assert op["args"]["entity"]["pattern_origin"] == [-356718.6693916272, 148665.00000000006]


def test_hatch_with_pattern_definitions_derives_origin_from_row_base():
    # R4n census (runs/e2e_1dwg_R4n_origin_20260709): custom-pattern hatches
    # carry their per-hatch phase BAKED into the row base points while the
    # census pattern_origin field is [0,0] (233/233 residual pairs, one
    # common per-hatch base vector). The name-shared .pat is rebased to zero
    # phase, so the serializer must put the phase on HPORIGIN:
    # effective origin = rows[0].base + census origin.
    ent = _sample("hatch", require_vertices=True)
    ent["geometry"].pop("pattern_origin", None)
    ent["geometry"]["pattern_definitions"] = [
        {"angle": 0.0, "base": [250000.00000000023, -234000.0],
         "offset": [43.75, 43.75], "dashes": [43.75, -43.75]}]

    op = patch_ops_blocks._def_entity_append_op("BLK", ent)

    assert op is not None
    assert op["args"]["entity"]["pattern_origin"] == [250000.00000000023, -234000.0]


def test_hatch_pattern_definitions_origin_adds_census_origin():
    # Additivity of baked base + HPORIGIN: evidenced by the 27 nonzero-origin
    # census hatches that were already diff0 under the shared-base replay.
    ent = _sample("hatch", require_vertices=True)
    ent["geometry"]["pattern_origin"] = [123.5, -77.25]
    ent["geometry"]["pattern_definitions"] = [
        {"angle": 0.0, "base": [100.0, 200.0],
         "offset": [43.75, 43.75], "dashes": []}]

    op = patch_ops_blocks._def_entity_append_op("BLK", ent)

    assert op is not None
    assert op["args"]["entity"]["pattern_origin"] == [223.5, 122.75]


def test_hatch_without_origin_and_without_defs_emits_no_origin_key():
    ent = _sample("hatch", require_vertices=True)
    ent["geometry"].pop("pattern_origin", None)
    ent["geometry"].pop("pattern_definitions", None)

    op = patch_ops_blocks._def_entity_append_op("BLK", ent)

    if op is None:
        # Drawing-custom pattern without definitions defers by design; the
        # no-key contract is only observable on an emittable hatch.
        ent["geometry"]["pattern_name"] = "DASH"
        op = patch_ops_blocks._def_entity_append_op("BLK", ent)
    assert op is not None
    assert "pattern_origin" not in op["args"]["entity"]
