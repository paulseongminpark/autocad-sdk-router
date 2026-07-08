#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit coverage for deferred accounting in per_kind_verdict."""
from __future__ import annotations

import importlib
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.join(os.path.dirname(_THIS_DIR), "..", "tools")
_TOOLS_DIR = os.path.normpath(_TOOLS_DIR)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

frc = importlib.import_module("full_roundtrip_capstone")


def _entity(dxf_name, kind):
    return {"dxf_name": dxf_name, "geometry": {"kind": kind}}


def _row(verdict, dxf_name):
    return next(row for row in verdict["rows"] if row["dxf_name"] == dxf_name)


def test_per_kind_verdict_deferred_insert_counts_are_additive():
    pre_ir = {
        "entities": [
            _entity("INSERT", "block_reference"),
            _entity("INSERT", "block_reference"),
            _entity("INSERT", "block_reference"),
            _entity("LINE", "line"),
            _entity("LINE", "line"),
        ]
    }
    diff = {
        "diagnostics": {"comparison_basis": "geometry"},
        "summary": {"by_type": {"INSERT": {"added": 0, "removed": 2, "modified": 0}}},
        "changed_handles": [],
    }
    deferred = [
        {"index": 0, "handle": "8468", "kind": "block_reference", "reason": "missing def A"},
        {"index": 2, "handle": "846D", "kind": "block_reference", "reason": "missing def B"},
    ]

    verdict = frc.per_kind_verdict(pre_ir, diff, deferred=deferred)

    insert_row = _row(verdict, "INSERT")
    assert insert_row["regen_attempted_count"] == 3
    assert insert_row["removed_count"] == 2
    assert insert_row["diff0_count"] == 1
    assert insert_row["deferred_count"] == 2
    assert insert_row["attempted_live_count"] == 1

    assert verdict["totals"]["regen_attempted_count"] == 5
    assert verdict["totals"]["diff0_count"] == 3
    assert verdict["totals"]["removed_count"] == 2
    assert verdict["totals"]["deferred_count"] == 2
    assert verdict["totals"]["attempted_live_count"] == 3


def test_per_kind_verdict_deferred_none_keeps_zero_deferred_counts():
    pre_ir = {"entities": [_entity("CIRCLE", "circle") for _ in range(4)]}
    diff = {"diagnostics": {"comparison_basis": "geometry"}, "summary": {"by_type": {}}, "changed_handles": []}

    verdict = frc.per_kind_verdict(pre_ir, diff, deferred=None)

    row = _row(verdict, "CIRCLE")
    assert row["regen_attempted_count"] == 4
    assert row["deferred_count"] == 0
    assert row["attempted_live_count"] == 4
    assert verdict["totals"]["deferred_count"] == 0
    assert verdict["totals"]["attempted_live_count"] == 4


def test_per_kind_verdict_kind_without_deferred_is_unaffected():
    pre_ir = {
        "entities": [
            _entity("INSERT", "block_reference"),
            _entity("INSERT", "block_reference"),
            _entity("LINE", "line"),
            _entity("LINE", "line"),
            _entity("LINE", "line"),
            _entity("LINE", "line"),
        ]
    }
    diff = {
        "diagnostics": {"comparison_basis": "geometry"},
        "summary": {
            "by_type": {
                "INSERT": {"added": 0, "removed": 1, "modified": 0},
                "LINE": {"added": 0, "removed": 1, "modified": 1},
            }
        },
        "changed_handles": [],
    }
    deferred = [{"index": 0, "handle": "8468", "kind": "block_reference", "reason": "missing def"}]

    verdict = frc.per_kind_verdict(pre_ir, diff, deferred=deferred)

    line_row = _row(verdict, "LINE")
    assert line_row["regen_attempted_count"] == 4
    assert line_row["deferred_count"] == 0
    assert line_row["attempted_live_count"] == 4
    assert line_row["removed_count"] == 1
    assert line_row["modified_count"] == 1
    assert line_row["diff0_count"] == 2


def test_per_kind_verdict_ignores_unmappable_deferred_kinds():
    pre_ir = {"entities": [_entity("CIRCLE", "circle"), _entity("CIRCLE", "circle")]}
    diff = {"diagnostics": {"comparison_basis": "geometry"}, "summary": {"by_type": {}}, "changed_handles": []}
    deferred = [
        {"index": 0, "handle": "100", "kind": "circle", "reason": "deferred"},
        {"index": 1, "handle": "101", "kind": "not_a_real_kind", "reason": "ignored"},
    ]

    verdict = frc.per_kind_verdict(pre_ir, diff, deferred=deferred)

    row = _row(verdict, "CIRCLE")
    assert row["deferred_count"] == 1
    assert row["attempted_live_count"] == 1
    assert verdict["totals"]["deferred_count"] == 1
    assert verdict["totals"]["attempted_live_count"] == 1
