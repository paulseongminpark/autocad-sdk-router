#!/usr/bin/env python3
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).resolve().parent
_E2 = _THIS_DIR.parents[1] / "tools" / "e2"
_INSTRUMENTS = _E2 / "instruments"
for _path in (_E2, _INSTRUMENTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import dwg_graph_to_worldir as adapter
import worldir_oracle


def _line(handle, start, end, *, owner="1F", space="model"):
    return {
        "handle": handle,
        "dxf_name": "LINE",
        "owner_handle": owner,
        "space": space,
        "layer": "WALL",
        "geometry": {"kind": "line", "start": list(start), "end": list(end)},
    }


def _insert(handle, target, position, *, owner="1F", space="model", scale=(1, 1, 1), rotation=0.0):
    return {
        "handle": handle,
        "dxf_name": "INSERT",
        "owner_handle": owner,
        "space": space,
        "layer": "0",
        "block_record_handle": target,
        "geometry": {
            "kind": "block_reference",
            "position": list(position),
            "scale": list(scale),
            "rotation": rotation,
        },
    }


def _rich_ir():
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "coverage_level": "native_full",
        "source": {"sha256": "a" * 64, "dwg_name": "origin_fixture.dwg"},
        "symbol_tables": {
            "block_table_records": [
                {"handle": "1F", "name": "*Model_Space", "is_layout": True, "origin": [0, 0, 0]},
                {"handle": "A", "name": "A", "is_layout": False, "origin": [10, 20, 0]},
                {"handle": "B", "name": "B", "is_layout": False, "origin": [0, 0, 0]},
            ]
        },
        "entities": [
            _line("ROOT_LINE", (0, 0, 0), (1, 0, 0)),
            _insert("ROOT_INS", "A", (100, 200, 0), scale=(2, 3, 1), rotation=math.pi / 2),
        ],
        "block_definitions": [
            {
                "handle": "A",
                "name": "A",
                "origin": [10, 20, 0],
                "entity_count": 2,
                "def_entities": [
                    _line("A_LINE", (10, 20, 0), (11, 20, 0), owner="A", space="block"),
                    _insert("A_INS", "B", (12, 20, 0), owner="A", space="block"),
                ],
            },
            {
                "handle": "B",
                "name": "B",
                "origin": [0, 0, 0],
                "entity_count": 1,
                "def_entities": [
                    _line("B_LINE", (0, 0, 0), (0, 2, 0), owner="B", space="block"),
                ],
            },
        ],
    }


def _point_pairs(world_output):
    pairs = []
    for segment in world_output["segments"]:
        p0 = tuple(round(value, 6) for value in segment["p0_world"])
        p1 = tuple(round(value, 6) for value in segment["p1_world"])
        pairs.append(tuple(sorted((p0, p1))))
    return set(pairs)


def test_adapter_preserves_nonzero_block_origin_and_nested_transforms():
    adapted = adapter.adapt(_rich_ir())
    assert adapted["status"] == "PASS"
    assert adapted["definitions"]["A"]["base_point"] == [10.0, 20.0]
    assert adapted["definitions"]["1F"]["entities"][1]["rotation_deg"] == pytest.approx(90.0)
    assert adapted["adapter_ledger"]["source_entity_templates"] == 5
    assert adapted["adapter_ledger"]["adapted_entity_templates"] == 5
    assert adapted["adapter_ledger"]["explicitly_excluded_entity_templates"] == 0

    world = worldir_oracle.expand_world_ir(adapted)
    assert world["status"] == "PASS"
    assert world["adapter_ledger"]["balance_ok"] is True
    assert world["conservation_ledger"]["conservation_ok"] is True
    pairs = _point_pairs(world)
    assert ((100.0, 200.0), (100.0, 202.0)) in pairs
    assert ((94.0, 204.0), (100.0, 204.0)) in pairs


def test_unsupported_entity_is_explicitly_excluded_not_silently_dropped():
    ir = _rich_ir()
    ir["entities"] = [{
        "handle": "C1",
        "dxf_name": "CIRCLE",
        "owner_handle": "1F",
        "space": "model",
        "geometry": {"kind": "circle", "center": [0, 0, 0], "radius": 1},
    }]
    ir["block_definitions"] = []
    ir["symbol_tables"]["block_table_records"] = [
        {"handle": "1F", "name": "*Model_Space", "is_layout": True, "origin": [0, 0, 0]}
    ]

    adapted = adapter.adapt(ir)
    ledger = adapted["adapter_ledger"]
    assert adapted["status"] == "PARTIAL"
    assert ledger["source_entity_templates"] == 1
    assert ledger["adapted_entity_templates"] == 0
    assert ledger["explicitly_excluded_entity_templates"] == 1
    assert ledger["balance_ok"] is True
    assert ledger["excluded_by_dxf_name"] == {"CIRCLE": 1}


def test_missing_block_origin_fails_closed():
    ir = _rich_ir()
    del ir["block_definitions"][0]["origin"]
    with pytest.raises(adapter.AdapterFailure) as exc:
        adapter.adapt(ir)
    assert exc.value.code == "MISSING_BLOCK_ORIGIN"


def test_zero_length_line_is_explicitly_excluded():
    ir = _rich_ir()
    ir["entities"].append(_line("ZERO", (4, 4, 0), (4, 4, 0)))

    result = adapter.adapt(ir)

    assert result["status"] == "PARTIAL"
    ledger = result["adapter_ledger"]
    assert ledger["excluded_invalid_geometry_templates"] == 1
    assert ledger["excluded_by_dxf_name"]["DEGENERATE:LINE"] == 1
    assert ledger["balance_ok"] is True


def test_duplicate_polyline_vertex_is_counted_and_removed():
    ir = _rich_ir()
    ir["entities"].append(
        {
            "handle": "P0",
            "dxf_name": "LWPOLYLINE",
            "layer": "WALL",
            "geometry": {
                "vertices": [
                    {"point": [0.0, 0.0, 0.0]},
                    {"point": [1.0, 0.0, 0.0]},
                    {"point": [1.0, 0.0, 0.0]},
                ],
                "closed": False,
            },
        }
    )

    adapted = adapter.adapt(ir)
    world = worldir_oracle.expand_world_ir(adapted)

    assert adapted["adapter_ledger"]["excluded_degenerate_subsegments"] == 1
    assert world["status"] == "PASS"
    assert world["conservation_ledger"]["conservation_ok"] is True


def test_xclip_removes_hidden_block_geometry_with_conservation():
    ir = _rich_ir()
    ir["entities"][1]["xclip"] = {
        "enabled": True,
        "inverted": False,
        "boundary_wcs": [[99.0, 199.0], [101.0, 203.0]],
    }

    adapted = adapter.adapt(ir)
    world = worldir_oracle.expand_world_ir(adapted)

    assert adapted["definitions"]["1F"]["entities"][1]["clip"] == {
        "boundary_owner": [[99.0, 199.0], [101.0, 203.0]],
        "inverted": False,
    }
    assert world["status"] == "PASS"
    assert world["conservation_ledger"]["clipped_away_segment_instances"] == 1
    assert world["conservation_ledger"]["emitted_segment_instances"] == 2
    assert world["conservation_ledger"]["conservation_ok"] is True


def test_inverted_xclip_keeps_geometry_outside_boundary():
    ir = _rich_ir()
    ir["entities"][1]["xclip"] = {
        "enabled": True,
        "inverted": True,
        "boundary_wcs": [[99.0, 199.0], [101.0, 203.0]],
    }

    world = worldir_oracle.expand_world_ir(adapter.adapt(ir))

    assert world["status"] == "PASS"
    assert ((94.0, 204.0), (100.0, 204.0)) in _point_pairs(world)
    assert ((100.0, 200.0), (100.0, 202.0)) not in _point_pairs(world)
    assert world["conservation_ledger"]["clipped_away_segment_instances"] == 1
    assert world["conservation_ledger"]["conservation_ok"] is True


def test_concave_xclip_can_emit_two_visible_fragments():
    graph = {
        "ir": "worldir.input.v1",
        "drawing_id": "concave",
        "root": "R",
        "definitions": {
            "R": {
                "handle": "R",
                "base_point": [0, 0],
                "entities": [
                    {
                        "handle": "I",
                        "kind": "INSERT",
                        "target": "C",
                        "insert": [0, 0],
                        "scale": [1, 1],
                        "rotation_deg": 0,
                        "clip": {
                            "inverted": False,
                            "boundary_owner": [
                                [0, 0], [4, 0], [4, 4], [3, 4],
                                [3, 1], [1, 1], [1, 4], [0, 4],
                            ],
                        },
                    }
                ],
            },
            "C": {
                "handle": "C",
                "base_point": [0, 0],
                "entities": [
                    {"handle": "L", "kind": "LINE", "start": [-1, 2], "end": [5, 2]}
                ],
            },
        },
    }

    world = worldir_oracle.expand_world_ir(graph)

    assert world["status"] == "PASS"
    assert _point_pairs(world) == {
        ((0.0, 2.0), (1.0, 2.0)),
        ((3.0, 2.0), (4.0, 2.0)),
    }
    ledger = world["conservation_ledger"]
    assert ledger["visible_source_segment_instances"] == 1
    assert ledger["emitted_segment_instances"] == 2
    assert ledger["clip_generated_fragment_instances"] == 1
    assert ledger["conservation_ok"] is True


def test_native_extractor_emits_block_origin_contract():
    source = (
        _THIS_DIR.parents[1]
        / "src"
        / "Ariadne.AcadNative"
        / "AriadneNativeJob.cpp"
    ).read_text(encoding="utf-8-sig")
    assert '"origin"' in source
    assert "pBTR->origin()" in source
