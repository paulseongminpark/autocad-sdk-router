#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for the centerline-topology semantic gate."""

from __future__ import annotations

import copy
import json
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools.semantic_gates.centerline_topology import (  # noqa: E402
    CENTERLINE_TOPOLOGY_GATE_SCHEMA_ID,
    centerline_topology_gate_report,
)


def _line(handle, start, end):
    return {
        "handle": handle,
        "dxf_name": "LINE",
        "geometry": {"kind": "line", "start": start, "end": end},
    }


def _block_ir(lines, name="WALLS"):
    return {"block_definitions": [{"name": name, "def_entities": list(lines)}]}


def _report(ir_a, ir_b, **kwargs):
    return centerline_topology_gate_report(
        ir_a,
        ir_b,
        thickness_min=10.0,
        thickness_max=400.0,
        overlap_min_ratio=0.5,
        **kwargs,
    )


def test_block_definition_lines_produce_non_vacuous_passing_centerlines():
    ir = _block_ir([
        _line("A", [0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]),
        _line("B", [0.0, 100.0, 0.0], [1000.0, 100.0, 0.0]),
    ])

    report = _report(ir, copy.deepcopy(ir))

    assert report["schema"] == CENTERLINE_TOPOLOGY_GATE_SCHEMA_ID
    assert report["verdict"] == "PASS"
    assert report["totals"]["census_segments"] > 0
    assert report["per_block"]["WALLS"]["census"]["segments"] == 1


def test_vertical_wall_pair_is_covered_and_translation_fails():
    census = _block_ir([
        _line("A", [0.0, 0.0, 0.0], [0.0, 1000.0, 0.0]),
        _line("B", [100.0, 0.0, 0.0], [100.0, 1000.0, 0.0]),
    ])
    post = _block_ir([
        _line("A", [0.0, 0.0, 0.0], [0.0, 1000.0, 0.0]),
        _line("B", [150.0, 0.0, 0.0], [150.0, 1000.0, 0.0]),
    ])

    identical = _report(census, copy.deepcopy(census))
    mutated = _report(census, post)

    assert identical["per_block"]["WALLS"]["census"]["segments"] == 1
    assert mutated["verdict"] == "FAIL"
    assert mutated["per_block"]["WALLS"]["diff"]["missing_total"] == 1
    assert mutated["per_block"]["WALLS"]["diff"]["added_total"] == 1


def test_half_integer_midline_survives_sub_unit_noise():
    census = _block_ir([
        _line("A", [0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]),
        _line("B", [0.0, 101.0, 0.0], [1000.0, 101.0, 0.0]),
    ])
    post = _block_ir([
        _line("A", [0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]),
        _line("B", [0.0, 101.00000000001, 0.0], [1000.0, 101.00000000001, 0.0]),
    ])

    report = _report(census, post)

    assert report["verdict"] == "PASS"
    assert report["totals"]["missing_total"] == 0
    assert report["totals"]["added_total"] == 0


def test_three_collinear_parallel_faces_emit_only_adjacent_centerlines():
    ir = _block_ir([
        _line("A", [0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]),
        _line("B", [0.0, 100.0, 0.0], [1000.0, 100.0, 0.0]),
        _line("C", [0.0, 200.0, 0.0], [1000.0, 200.0, 0.0]),
    ])

    report = _report(ir, copy.deepcopy(ir))

    assert report["verdict"] == "PASS"
    assert report["per_block"]["WALLS"]["census"]["segments"] == 2


def test_room_width_gap_does_not_create_spanning_phantom_centerline():
    ir = _block_ir([
        _line("A", [0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]),
        _line("B", [0.0, 100.0, 0.0], [1000.0, 100.0, 0.0]),
        _line("C", [0.0, 1000.0, 0.0], [1000.0, 1000.0, 0.0]),
        _line("D", [0.0, 1100.0, 0.0], [1000.0, 1100.0, 0.0]),
    ])

    report = _report(ir, copy.deepcopy(ir))

    assert report["verdict"] == "PASS"
    assert report["per_block"]["WALLS"]["census"]["segments"] == 2


def test_report_is_deterministic():
    ir = _block_ir([
        _line("A", [0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]),
        _line("B", [0.0, 100.0, 0.0], [1000.0, 100.0, 0.0]),
        _line("C", [0.0, 250.0, 0.0], [1000.0, 250.0, 0.0]),
    ])

    first = json.dumps(_report(ir, copy.deepcopy(ir)), sort_keys=True)
    second = json.dumps(_report(ir, copy.deepcopy(ir)), sort_keys=True)

    assert first == second


def test_degenerate_and_malformed_entities_are_ignored():
    ir = _block_ir([
        _line("A", [0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]),
        _line("B", [0.0, 100.0, 0.0], [1000.0, 100.0, 0.0]),
        _line("MISSING_START", None, [0.0, 0.0, 0.0]),
        _line("ZERO", [1.0, 1.0, 0.0], [1.0, 1.0, 0.0]),
        _line("BAD", [0.0, "x", 0.0], [1.0, 1.0, 0.0]),
        {"geometry": {"kind": "circle", "center": [0.0, 0.0, 0.0]}},
    ])

    report = _report(ir, copy.deepcopy(ir))

    assert report["verdict"] == "PASS"
    assert report["per_block"]["WALLS"]["census"]["segments"] == 1


def test_name_map_pairs_renamed_anonymous_blocks():
    # census keeps AutoCAD's anonymous name; the rebuild renames it (as the
    # roundtrip pipeline does: *U132 -> ARIADNE_ANON_U132). Same geometry.
    lines = [
        _line("A", [0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]),
        _line("B", [0.0, 100.0, 0.0], [1000.0, 100.0, 0.0]),
    ]
    census = _block_ir(list(lines), name="*U132")
    post = _block_ir(list(lines), name="ARIADNE_ANON_U132")

    # Without the map the rename reads as a full block of missing+added.
    unmapped = _report(census, post)
    assert unmapped["verdict"] == "FAIL"
    assert unmapped["totals"]["missing_total"] == 1
    assert unmapped["totals"]["added_total"] == 1

    # With the census->post map the two blocks pair and the verdict is clean.
    mapped = _report(census, post, name_map={"*U132": "ARIADNE_ANON_U132"})
    assert mapped["verdict"] == "PASS"
    assert mapped["totals"]["missing_total"] == 0
    assert mapped["totals"]["added_total"] == 0
    assert "ARIADNE_ANON_U132" in mapped["per_block"]
    assert "*U132" not in mapped["per_block"]
