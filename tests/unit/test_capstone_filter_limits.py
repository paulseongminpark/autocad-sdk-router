#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/unit/test_capstone_filter_limits.py -- additive coverage for
full_roundtrip_capstone.filter_ir_to_certified's kinds/limit/per_kind_limit
knobs, on top of tests/unit/test_full_roundtrip_capstone.py. Cases already
covered there and SKIPPED here: kinds={'line'} narrowing (see
test_filter_ir_to_certified_kinds_narrows_further), a single-kind global
limit (test_filter_ir_to_certified_global_limit), per_kind_limit's resulting
per-kind counts (test_filter_ir_to_certified_per_kind_limit), and exclusion
of a non-certified (dxf_name, kind) pair via HATCH/hatch, plus a shallow
never-mutates-input check
(test_filter_ir_to_certified_drops_out_of_class_and_preserves_certified)."""
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


def _entity(dxf, kind, handle="1"):
    return {"handle": handle, "dxf_name": dxf, "layer": "0", "geometry": {"kind": kind}}


def test_per_kind_limit_keeps_first_n_per_kind_in_input_order():
    ir = {"entities": [
        _entity("LINE", "line", handle="L1"),
        _entity("CIRCLE", "circle", handle="C1"),
        _entity("LINE", "line", handle="L2"),
        _entity("LINE", "line", handle="L3"),
        _entity("CIRCLE", "circle", handle="C2"),
    ]}
    filtered = frc.filter_ir_to_certified(ir, per_kind_limit=2)
    handles = [e["handle"] for e in filtered["entities"]]
    # First 2 LINEs (L1, L2) and first 2 CIRCLEs (C1, C2), each in the order
    # they appeared in the input -- L3 dropped as the 3rd LINE.
    assert handles == ["L1", "C1", "L2", "C2"]


def test_limit_caps_globally_across_mixed_kinds():
    ir = {"entities": [
        _entity("LINE", "line", handle="L1"),
        _entity("CIRCLE", "circle", handle="C1"),
        _entity("TEXT", "text", handle="T1"),
        _entity("LINE", "line", handle="L2"),
        _entity("CIRCLE", "circle", handle="C2"),
    ]}
    filtered = frc.filter_ir_to_certified(ir, limit=3)
    handles = [e["handle"] for e in filtered["entities"]]
    # limit=3 stops after the 3rd certified entity overall, not per kind.
    assert handles == ["L1", "C1", "T1"]


def test_kind_certified_elsewhere_but_wrong_dxf_pairing_excluded():
    # "circle" is a certified kind (via (CIRCLE, circle)), but (LINE, circle)
    # is not a real CERTIFIED_BUCKETS pair -- the pair must be checked, not
    # just kind membership.
    assert ("LINE", "circle") not in frc.CERTIFIED_BUCKETS
    assert "circle" in frc.CERTIFIED_KINDS
    ir = {"entities": [_entity("LINE", "circle"), _entity("CIRCLE", "circle")]}
    filtered = frc.filter_ir_to_certified(ir)
    pairs = [(e["dxf_name"], e["geometry"]["kind"]) for e in filtered["entities"]]
    assert pairs == [("CIRCLE", "circle")]


def test_non_dict_entities_skipped_without_exception():
    ir = {"entities": [None, "not-a-dict", 42, _entity("LINE", "line")]}
    filtered = frc.filter_ir_to_certified(ir)
    assert len(filtered["entities"]) == 1
    assert filtered["entities"][0]["dxf_name"] == "LINE"


def test_input_ir_and_its_entities_list_are_not_mutated():
    original_entities = [_entity("LINE", "line"), _entity("HATCH", "hatch")]
    ir = {"entities": original_entities, "schema": "dwg_graph_ir.v1"}
    filtered = frc.filter_ir_to_certified(ir, limit=1)
    assert filtered is not ir
    assert ir["entities"] is original_entities
    assert len(ir["entities"]) == 2
    assert ir["entities"][1]["dxf_name"] == "HATCH"


def test_empty_entities_yields_empty_result_and_preserves_other_keys():
    ir = {"entities": [], "schema": "dwg_graph_ir.v1", "source_path": "x.dwg"}
    filtered = frc.filter_ir_to_certified(ir)
    assert filtered["entities"] == []
    assert filtered["schema"] == "dwg_graph_ir.v1"
    assert filtered["source_path"] == "x.dwg"
