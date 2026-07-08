from __future__ import annotations

import copy
import os
import sys

import pytest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import blockdef_diff


def _entity(handle: str, dxf_name: str, kind: str, *, layer: str = "0", **geometry):
    payload = {"kind": kind}
    payload.update(geometry)
    return {
        "handle": handle,
        "dxf_name": dxf_name,
        "layer": layer,
        "space": "block",
        "geometry": payload,
    }


def _ir(*block_defs):
    return {"schema": "ariadne.dwg_graph_ir.v1", "block_definitions": list(block_defs)}


def _block(name: str, *entities):
    return {"name": name, "handle": f"H_{name}", "def_entities": list(entities)}


def _per_def(report, name: str):
    return next(row for row in report["per_def"] if row["name"] == name)


def test_identical_defs_yield_full_diff0_and_fraction_one():
    ir = _ir(
        _block("DOOR", _entity("A1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])),
        _block("*U172", _entity("A2", "CIRCLE", "circle", center=[2, 2, 0], radius=1.0)),
    )

    report = blockdef_diff.diff_block_definitions(ir, copy.deepcopy(ir))

    assert report["schema"] == "ariadne.blockdef_diff.v1"
    assert report["totals"]["diff0_total"] == 2
    assert report["totals"]["interior_diff0_fraction"] == 1.0
    assert _per_def(report, "*U172")["diff0"] == 1
    assert _per_def(report, "DOOR")["diff0"] == 1


def test_missing_definition_in_b_is_reported_and_counted():
    ir_a = _ir(
        _block("A", _entity("A1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])),
        _block("B", _entity("B1", "ARC", "arc", center=[0, 0, 0], radius=2.0, start_angle=0.0, end_angle=1.0)),
    )
    ir_b = _ir(
        _block("A", _entity("A9", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])),
    )

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)
    missing = _per_def(report, "B")

    assert missing["missing_side"] == "b"
    assert missing["a_total"] == 1
    assert missing["b_total"] == 0
    assert missing["removed"] == 1
    assert report["totals"]["a_def_count"] == 2
    assert report["totals"]["b_def_count"] == 1
    assert report["totals"]["a_entity_total"] == 2
    assert report["totals"]["b_entity_total"] == 1


def test_removed_entity_inside_definition_counts_as_removed():
    ir_a = _ir(
        _block(
            "DOOR",
            _entity("D1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0]),
            _entity("D2", "CIRCLE", "circle", center=[2, 0, 0], radius=1.0),
        )
    )
    ir_b = _ir(
        _block(
            "DOOR",
            _entity("D1X", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0]),
        )
    )

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)
    per_def = _per_def(report, "DOOR")

    assert per_def["diff0"] == 1
    assert per_def["removed"] == 1
    assert per_def["added"] == 0
    assert per_def["modified"] == 0


def test_kind_gap_aggregates_counts_across_all_definitions():
    ir_a = _ir(
        _block("A", _entity("A1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])),
        _block("B", _entity("B1", "CIRCLE", "circle", center=[1, 1, 0], radius=1.0)),
    )
    ir_b = _ir(
        _block("A", _entity("A9", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])),
        _block("C", _entity("C1", "LINE", "line", start=[2, 0, 0], end=[3, 0, 0])),
    )

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)

    assert report["by_kind_gap"] == {
        "circle": {"a_count": 1, "b_count": 0},
        "line": {"a_count": 1, "b_count": 2},
    }


def test_empty_a_entity_total_yields_none_fraction():
    ir_a = _ir(_block("EMPTY"))
    ir_b = _ir(_block("FULL", _entity("F1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])))

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)

    assert report["totals"]["a_entity_total"] == 0
    assert report["totals"]["interior_diff0_fraction"] is None
