#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for the N5 dimension-geometry semantic gate."""

from __future__ import annotations

import copy
import math
import os
import sys
from pathlib import Path

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools.semantic_gates.dim_geometry import (  # noqa: E402
    compare_dim_relations,
    extract_dim_relations,
    load_ir,
    self_test_mutations,
)

_FIXTURE_PATH = Path(_REPO) / "tests" / "fixtures" / "dim_gate_samples.json"


def _fixture_doc():
    return load_ir(_FIXTURE_PATH)


def test_real_fixture_all_113_dimensions_are_coherent():
    rows = extract_dim_relations(_fixture_doc())

    assert len(rows) == 113
    assert all(row["coherent"] for row in rows)
    assert max(abs(row["residual"]) for row in rows) <= 1e-6 * max(1.0, max(row["span"] for row in rows))


def test_identical_ir_compare_is_fully_preserved():
    ir_a = _fixture_doc()
    ir_b = copy.deepcopy(ir_a)

    report = compare_dim_relations(extract_dim_relations(ir_a), extract_dim_relations(ir_b))

    assert report["schema"] == "ariadne.dim_semantic_gate.v1"
    assert report["total_a"] == 113
    assert report["total_b"] == 113
    assert report["preserved"] == 113
    assert report["missing"] == 0
    assert report["mutated"] == 0
    assert report["fraction"] == 1.0
    assert report["status"] == "ok"
    assert report["rows_mutated"] == []


def test_self_test_mutations_convicts_the_three_seeded_violations():
    report = self_test_mutations()

    assert report["status"] == "blocked"
    assert report["mutated"] == 1
    assert report["missing"] == 2
    assert len(report["rows_mutated"]) == 1


def test_missing_dimension_is_reported():
    ir_a = _fixture_doc()
    ir_b = copy.deepcopy(ir_a)
    ir_b["dimensions"].pop()

    report = compare_dim_relations(extract_dim_relations(ir_a), extract_dim_relations(ir_b))

    assert report["total_a"] == 113
    assert report["total_b"] == 112
    assert report["preserved"] == 112
    assert report["missing"] == 1
    assert report["mutated"] == 0
    assert report["status"] == "blocked"
    assert math.isclose(report["fraction"], 112.0 / 113.0, rel_tol=0.0, abs_tol=1e-12)
