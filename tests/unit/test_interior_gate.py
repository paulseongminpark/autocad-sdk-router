#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import full_roundtrip_capstone as cap


def _ir(defs):
    return {"schema": "ariadne.dwg_graph_ir.v1", "entities": [], "block_definitions": defs}


def _line_def(name, n):
    ents = [{"handle": "%s%d" % (name, i), "layer": "0",
             "geometry": {"kind": "line", "start": [float(i), 0.0, 0.0], "end": [float(i), 1.0, 0.0]}}
            for i in range(n)]
    return {"name": name, "handle": "H" + name, "def_entities": ents}


def test_interior_gate_ok_at_or_above_baseline():
    a = _ir([_line_def("D", 4)])
    diff, gate = cap.interior_gate_report(a, a, baseline=1.0, baseline_source="test")
    assert gate["status"] == "ok"
    assert gate["fraction"] == 1.0
    assert diff["totals"]["diff0_total"] == 4


def test_interior_gate_blocks_on_regression():
    a = _ir([_line_def("D", 4)])
    b = _ir([_line_def("D", 2)])
    _diff, gate = cap.interior_gate_report(a, b, baseline=0.9, baseline_source="test")
    assert gate["status"] == "blocked"
    assert "regressed below ratchet baseline" in gate["reason"]


def test_interior_gate_vacuous_ok_without_block_definitions():
    a = _ir([])
    _diff, gate = cap.interior_gate_report(a, a, baseline=0.9, baseline_source="test")
    assert gate["status"] == "ok"
    assert "vacuously ok" in gate["note"]


def test_interior_gate_blocks_without_baseline():
    a = _ir([_line_def("D", 1)])
    _diff, gate = cap.interior_gate_report(a, a, baseline=None)
    assert gate["status"] == "blocked"
    assert "no ratchet baseline" in gate["reason"]


def test_committed_baseline_config_loads():
    baseline, source = cap._load_interior_baseline()
    assert isinstance(baseline, float) and 0.0 < baseline <= 1.0
    assert "R4e" in source
