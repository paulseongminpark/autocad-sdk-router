#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Block-definition append payload coverage for newly admitted kinds."""
from __future__ import annotations

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from patch_ops import blocks as patch_ops_blocks  # noqa: E402
from patch_ops import entities as patch_ops_entities  # noqa: E402


def _ent(kind: str, *, layer: str = "0", native_class: str | None = None, **geometry) -> dict:
    ent = {"handle": "H1", "layer": layer, "geometry": {"kind": kind, **geometry}}
    if native_class is not None:
        ent["class"] = native_class
    return ent


def _expected_entity_from_create_serializer(ent: dict) -> dict:
    op = patch_ops_entities.ir_op_for(ent)
    assert op is not None
    return {
        "kind": ent["geometry"]["kind"],
        **{k: v for k, v in op["args"].items() if k != "layer"},
    }


def test_existing_four_kinds_are_unchanged():
    cases = [
        (
            _ent("line", start=[0.0, 0.0, 0.0], end=[1.0, 2.0, 0.0]),
            {"kind": "line",
             "start": {"x": 0.0, "y": 0.0, "z": 0.0},
             "end": {"x": 1.0, "y": 2.0, "z": 0.0}},
        ),
        (
            _ent("circle", center=[3.0, 4.0, 0.0], radius=5.0),
            {"kind": "circle",
             "center": {"x": 3.0, "y": 4.0, "z": 0.0},
             "radius": 5.0},
        ),
        (
            _ent("arc", center=[6.0, 7.0, 0.0], radius=8.0, start_angle=0.1, end_angle=0.9),
            {"kind": "arc",
             "center": {"x": 6.0, "y": 7.0, "z": 0.0},
             "radius": 8.0, "start_angle": 0.1, "end_angle": 0.9},
        ),
        (
            _ent("text", position=[9.0, 10.0, 0.0], text="door", height=2.5),
            {"kind": "text",
             "position": {"x": 9.0, "y": 10.0, "z": 0.0},
             "text": "door", "height": 2.5},
        ),
    ]

    for ent, expected in cases:
        op = patch_ops_blocks._def_entity_append_op("BLK", ent)
        assert op == {
            "operation": "append_block_entity",
            "args": {"block_name": "BLK", "entity": expected, "layer": ent["layer"]},
        }


def test_ellipse_point_lwpolyline_and_block_reference_match_create_serializers():
    cases = [
        _ent("ellipse", center=[1.0, 2.0, 0.0], normal=[0.0, 0.0, 1.0],
             major_axis=[3.0, 0.0, 0.0], radius_ratio=0.5,
             start_angle=0.0, end_angle=6.283185307179586),
        _ent("point", position=[5.0, 6.0, 0.0]),
        _ent("lwpolyline", closed=True,
             vertices=[{"point": [0.0, 0.0, 0.0], "bulge": 0.5},
                       {"point": [10.0, 0.0, 0.0], "bulge": 0.0}],
             const_width=0.25),
        _ent("block_reference", native_class="AcDbBlockReference",
             block_name="NESTED", position=[7.0, 8.0, 0.0],
             scale=[2.0, 3.0, 1.0], rotation=0.5),
    ]

    for ent in cases:
        op = patch_ops_blocks._def_entity_append_op("BLK", ent)
        assert op is not None
        expected = _expected_entity_from_create_serializer(ent)
        if ent["geometry"]["kind"] == "lwpolyline":
            expected["const_width"] = 0.25
        assert op["args"]["entity"] == expected
        assert op["args"]["layer"] == ent["layer"]


def test_spline_carries_fit_control_points_degree_and_closed():
    ent = _ent(
        "spline",
        degree=3,
        closed=False,
        fit_points=[[0.0, 0.0, 0.0], [10.0, 5.0, 0.0], [20.0, 0.0, 0.0]],
    )
    ent["spline_control_points"] = [[0.0, 0.0, 0.0], [6.0, 8.0, 0.0], [20.0, 0.0, 0.0]]

    op = patch_ops_blocks._def_entity_append_op("BLK", ent)

    assert op is not None
    assert op["args"]["entity"] == {
        "kind": "spline",
        "fit_points": [[0.0, 0.0, 0.0], [10.0, 5.0, 0.0], [20.0, 0.0, 0.0]],
        "control_points": [[0.0, 0.0, 0.0], [6.0, 8.0, 0.0], [20.0, 0.0, 0.0]],
        "degree": 3,
        "closed": False,
    }


def test_polyline_serializes_2d_and_3d_variants():
    poly2d = _ent(
        "polyline",
        native_class="AcDb2dPolyline",
        closed=True,
        elevation=3.0,
        default_start_width=0.1,
        default_end_width=0.2,
        vertices=[{"point": [0.0, 0.0, 3.0], "bulge": 0.5, "start_width": 0.1, "end_width": 0.2},
                  {"point": [5.0, 5.0, 3.0], "bulge": 0.0, "start_width": 0.0, "end_width": 0.0}],
    )
    poly3d = _ent(
        "polyline",
        native_class="AcDb3dPolyline",
        vertices=[{"point": [0.0, 0.0, 0.0]}, {"point": [1.0, 2.0, 3.0]}],
    )

    op2d = patch_ops_blocks._def_entity_append_op("BLK", poly2d)
    op3d = patch_ops_blocks._def_entity_append_op("BLK", poly3d)

    assert op2d is not None
    assert op2d["args"]["entity"] == {
        "kind": "polyline",
        "class": "AcDb2dPolyline",
        "points": [
            {"x": 0.0, "y": 0.0, "bulge": 0.5, "start_width": 0.1, "end_width": 0.2},
            {"x": 5.0, "y": 5.0, "bulge": 0.0, "start_width": 0.0, "end_width": 0.0},
        ],
        "closed": 1,
        "elevation": 3.0,
        "default_start_width": 0.1,
        "default_end_width": 0.2,
    }
    assert op3d is not None
    assert op3d["args"]["entity"] == {
        "kind": "polyline",
        "class": "AcDb3dPolyline",
        "points": [
            {"x": 0.0, "y": 0.0, "z": 0.0},
            {"x": 1.0, "y": 2.0, "z": 3.0},
        ],
    }


def test_unsupported_kinds_still_defer_with_same_reason():
    block_def = {
        "name": "MIX",
        "handle": "B1",
        "def_entities": [
            _ent("line"),
            _ent("hatch"),
            _ent("wipeout"),
            _ent("face3d"),
        ],
    }

    ops, deferred = patch_ops_blocks.block_def_ops(block_def)

    assert [op["operation"] for op in ops] == ["create_block", "append_block_entity"]
    assert [(row["kind"], row["reason"]) for row in deferred] == [
        ("hatch", "def_entity kind unsupported by write.block.append_entity"),
        ("wipeout", "def_entity kind unsupported by write.block.append_entity"),
        ("face3d", "def_entity kind unsupported by write.block.append_entity"),
    ]


def test_block_reference_without_block_name_still_defers_honestly():
    block_def = {
        "name": "MIX",
        "handle": "B2",
        "def_entities": [
            _ent("block_reference", native_class="AcDbBlockReference", position=[0.0, 0.0, 0.0]),
        ],
    }

    ops, deferred = patch_ops_blocks.block_def_ops(block_def)

    assert [op["operation"] for op in ops] == ["create_block"]
    assert deferred == [{
        "block_name": "MIX",
        "def_entity_index": 0,
        "handle": "H1",
        "kind": "block_reference",
        "reason": "def_entity kind unsupported by write.block.append_entity",
    }]


def test_spline_top_level_knots_and_weights_ride_along():
    # Extractor shape on real drawings (R4 census): geometry carries only
    # kind/degree/closed; control points + knots live at def-entity top level.
    def_ent = {
        "handle": "509", "layer": "X-FUR",
        "geometry": {"kind": "spline", "degree": 2.0, "closed": False},
        "spline_control_points": [[0.0, 0.0, 0.0], [1.0, 1.0, 0.0], [2.0, 0.0, 0.0]],
        "spline_knots": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
    }
    op = patch_ops_blocks._def_entity_append_op("B", def_ent)
    assert op is not None
    ent = op["args"]["entity"]
    assert ent["kind"] == "spline"
    assert ent["control_points"] == [[0.0, 0.0, 0.0], [1.0, 1.0, 0.0], [2.0, 0.0, 0.0]]
    assert ent["knots"] == [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
    assert "weights" not in ent


def test_spline_weights_pass_through_when_present():
    def_ent = {
        "handle": "50A", "layer": "0",
        "geometry": {"kind": "spline", "degree": 3.0, "closed": True},
        "spline_control_points": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]],
        "spline_knots": [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0],
        "spline_weights": [1.0, 0.5, 0.5, 1.0],
    }
    op = patch_ops_blocks._def_entity_append_op("B", def_ent)
    ent = op["args"]["entity"]
    assert ent["knots"] == [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0]
    assert ent["weights"] == [1.0, 0.5, 0.5, 1.0]


def test_create_block_synthesis_suppresses_seed_line():
    ops, _deferred = patch_ops_blocks.block_def_ops(
        {"name": "D", "handle": "H", "def_entities": [
            {"handle": "L1", "layer": "0",
             "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [1.0, 0.0, 0.0]}}]})
    create = ops[0]
    assert create["operation"] == "create_block"
    assert create["args"]["seed_line"] == 0
    job = patch_ops_blocks.build_job_args("write.block.simple_create", create["args"])
    assert job["seed_line"] == 0


def test_simple_create_without_seed_key_stays_legacy():
    job = patch_ops_blocks.build_job_args("write.block.simple_create", {"name": "D"})
    assert "seed_line" not in job
