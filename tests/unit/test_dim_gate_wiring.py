#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import full_roundtrip_capstone as cap  # noqa: E402


def _dimension_entity(handle: str, measurement: float):
    return {
        "handle": handle,
        "geometry": {
            "kind": "dimension",
            "xline1_point": [0.0, 0.0],
            "xline2_point": [1.0, 0.0],
            "rotation": 0.0,
            "measurement": measurement,
        },
    }


def _ir_for_gate(dimensions):
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "dimensions": copy.deepcopy(dimensions),
        "entities": [],
    }


def test_dim_semantic_gate_report_identical_ir_is_ok():
    census = _ir_for_gate([_dimension_entity("A", 10.0)])
    report = cap.dim_semantic_gate_report(census, copy.deepcopy(census))

    assert report["schema"] == "ariadne.dim_semantic_gate.v1"
    assert report["status"] == "ok"
    assert report["mutated"] == 0
    assert report["missing"] == 0
    assert report["fraction"] == 1.0


def test_dim_semantic_gate_report_mutation_is_blocked():
    census = _ir_for_gate([_dimension_entity("A", 10.0)])
    mutated = _ir_for_gate([_dimension_entity("A", 11.0)])

    report = cap.dim_semantic_gate_report(census, mutated)

    assert report["status"] == "blocked"
    assert report["mutated"] == 1
    assert report["preserved"] == 0


def test_dim_semantic_gate_report_vacuous_ok_without_dimensions():
    census = _ir_for_gate([])
    report = cap.dim_semantic_gate_report(census, _ir_for_gate([]))

    assert report["status"] == "ok"
    assert "vacuously ok" in report["note"]
