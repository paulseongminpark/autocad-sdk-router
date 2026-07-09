#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for deterministic wall-pair candidate proposal."""

from __future__ import annotations

import json
import os
import sys
from collections import Counter

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools.semantic.wall_pairs import propose_for_ir, propose_wall_pairs  # noqa: E402


def _line(handle, start, end, layer="WALL"):
    return {
        "handle": handle,
        "dxf_name": "LINE",
        "layer": layer,
        "geometry": {"kind": "line", "start": start, "end": end},
    }


def _mixed_fixture():
    return [
        _line("A", [0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]),
        _line("B", [100.0, 200.0, 0.0], [1100.0, 200.0, 0.0]),
        _line("PERP", [0.0, 0.0, 0.0], [0.0, 1000.0, 0.0]),
        _line("FAR", [0.0, 5000.0, 0.0], [1000.0, 5000.0, 0.0]),
        _line("LOW", [900.0, 300.0, 0.0], [1900.0, 300.0, 0.0]),
        _line("COL1", [2000.0, 0.0, 0.0], [3000.0, 0.0, 0.0]),
        _line("COL2", [2100.0, 0.0, 0.0], [3100.0, 0.0, 0.0]),
    ]


def test_propose_wall_pairs_accepts_only_clean_parallel_wall_candidate():
    claims = propose_wall_pairs(_mixed_fixture())

    assert len(claims) == 1
    claim = claims[0]
    assert claim["kind"] == "wall_pair_candidate"
    assert claim["pair"] == ["A", "B"]
    assert claim["gap"] == 200.0
    assert claim["overlap_ratio"] == 0.9
    assert claim["conf"] > 0.5
    assert claim["layers"] == ["WALL", "WALL"]
    assert claim["evidence"] == {
        "parallel_within": 0.005,
        "gap": 200.0,
        "overlap_ratio": 0.9,
    }


def test_propose_wall_pairs_is_deterministic():
    first = json.dumps(propose_wall_pairs(_mixed_fixture()), sort_keys=True)
    second = json.dumps(propose_wall_pairs(_mixed_fixture()), sort_keys=True)

    assert first == second


def test_propose_for_ir_reports_per_definition_totals():
    ir = {"block_definitions": [{"name": "D1", "def_entities": _mixed_fixture()}]}

    report = propose_for_ir(ir)

    assert report["schema"] == "ariadne.semantic.wall_pairs.v0"
    assert report["totals"] == {"defs": 1, "claims": 1}
    assert report["per_def"]["D1"][0]["pair"] == ["A", "B"]


def test_propose_for_ir_can_target_modelspace():
    report = propose_for_ir({"entities": _mixed_fixture()}, def_name="__modelspace__")

    assert report["totals"] == {"defs": 1, "claims": 1}
    assert report["per_def"]["__modelspace__"][0]["pair"] == ["A", "B"]


def test_budget_keeps_no_more_than_max_pairs_per_line():
    entities = [
        _line(f"L{i:02d}", [0.0, i * 40.0, 0.0], [1000.0, i * 40.0, 0.0])
        for i in range(10)
    ]

    claims = propose_wall_pairs(entities, max_pairs_per_line=3)
    counts = Counter(handle for claim in claims for handle in claim["pair"])

    assert claims
    assert all(count <= 3 for count in counts.values())
