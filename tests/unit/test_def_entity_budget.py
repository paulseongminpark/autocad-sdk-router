#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/unit/test_def_entity_budget.py -- unit coverage for
tools/full_roundtrip_capstone.apply_def_entity_budget: a pure (no-CAD-engine)
function that drops oversized block_definitions entries whole and reports
them, so ir_to_patch can defer create_blockref ops against dropped
definitions with an honest reason instead of attempting a synthesis whose
per-op cost is out of wall-clock budget."""
from __future__ import annotations

import copy
import importlib
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.join(os.path.dirname(_THIS_DIR), "..", "tools")
_TOOLS_DIR = os.path.normpath(_TOOLS_DIR)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

frc = importlib.import_module("full_roundtrip_capstone")


def _bd(name, handle, n_entities):
    return {
        "name": name,
        "handle": handle,
        "def_entities": ["e%d" % i for i in range(n_entities)],
    }


def test_oversized_def_dropped_whole_with_reason():
    ir = {"block_definitions": [_bd("BIGDEF", "h1", 5)]}
    out, dropped = frc.apply_def_entity_budget(ir, 3)
    assert out["block_definitions"] == []
    assert len(dropped) == 1
    entry = dropped[0]
    assert set(("name", "handle", "def_entity_count", "reason")) <= set(entry.keys())
    assert entry["name"] == "BIGDEF"
    assert entry["handle"] == "h1"
    assert entry["def_entity_count"] == 5
    assert "5" in entry["reason"]
    assert "3" in entry["reason"]


def test_def_at_exact_budget_is_kept_boundary():
    ir = {"block_definitions": [_bd("EXACT", "h2", 3)]}
    out, dropped = frc.apply_def_entity_budget(ir, 3)
    assert dropped == []
    assert len(out["block_definitions"]) == 1
    assert out["block_definitions"][0]["name"] == "EXACT"


def test_smaller_defs_kept_in_order():
    defs = [_bd("A", "ha", 1), _bd("B", "hb", 2), _bd("C", "hc", 3)]
    ir = {"block_definitions": defs}
    out, dropped = frc.apply_def_entity_budget(ir, 100)
    assert dropped == []
    assert [d["name"] for d in out["block_definitions"]] == ["A", "B", "C"]


def test_input_ir_not_mutated():
    defs = [_bd("KEEP", "hk", 1), _bd("DROP", "hd", 10)]
    ir = {"block_definitions": defs}
    ir_snapshot = copy.deepcopy(ir)
    out, dropped = frc.apply_def_entity_budget(ir, 5)
    assert ir == ir_snapshot
    assert len(ir["block_definitions"]) == 2
    assert len(dropped) == 1
    assert out is not ir


def test_missing_block_definitions_key_returns_empty_list_no_exception():
    ir = {"some_other_key": True}
    out, dropped = frc.apply_def_entity_budget(ir, 10)
    assert out["block_definitions"] == []
    assert dropped == []


def test_def_entities_missing_or_none_treated_as_zero_and_kept():
    ir = {
        "block_definitions": [
            {"name": "NOKEY", "handle": "h1"},
            {"name": "NONEVAL", "handle": "h2", "def_entities": None},
        ]
    }
    out, dropped = frc.apply_def_entity_budget(ir, 0)
    assert dropped == []
    assert [d["name"] for d in out["block_definitions"]] == ["NOKEY", "NONEVAL"]


def test_multiple_oversized_defs_all_reported():
    # Shape mirrors the measured real case on 1.dwg: budget 100 dropped
    # X-FORM_쳍주 (196 def entities) and X-평면도(기본형) (4723 def entities).
    ir = {
        "block_definitions": [
            _bd("X-FORM_쳍주", "hA", 196),
            _bd("X-평면도(기본형)", "hB", 4723),
            _bd("SMALLDEF", "hC", 10),
        ]
    }
    out, dropped = frc.apply_def_entity_budget(ir, 100)
    assert [d["name"] for d in out["block_definitions"]] == ["SMALLDEF"]
    assert len(dropped) == 2
    by_name = {d["name"]: d for d in dropped}
    assert by_name["X-FORM_쳍주"]["def_entity_count"] == 196
    assert by_name["X-평면도(기본형)"]["def_entity_count"] == 4723
    for entry in dropped:
        assert "100" in entry["reason"]
        assert str(entry["def_entity_count"]) in entry["reason"]
