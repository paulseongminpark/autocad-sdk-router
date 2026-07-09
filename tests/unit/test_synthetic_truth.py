#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for the synthetic dimension/geometry IR truth authoring helper."""

from __future__ import annotations

import copy
import os
import sys

import pytest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools.semantic_gates.dim_geometry import (  # noqa: E402
    compare_dim_relations,
    extract_dim_relations,
)
from tools.semantic_gates.synthetic_truth import (  # noqa: E402
    MUTATION_KINDS,
    make_dim_ir,
    mutate,
)


def test_authored_doc_has_requested_dimension_count():
    doc = make_dim_ir(20)

    assert len(doc["dimensions"]) == 20
    assert len(doc["anchor_geometry"]) == 20


def test_authored_doc_is_100_percent_coherent():
    doc = make_dim_ir(37, seed_offset=5)

    rows = extract_dim_relations(doc)

    assert len(rows) == 37
    assert all(row["coherent"] for row in rows)
    assert max(abs(row["residual"]) for row in rows) <= 1e-6 * max(1.0, max(row["span"] for row in rows))


def test_authored_doc_compares_ok_against_a_deep_copy_of_itself():
    doc = make_dim_ir(15)

    report = compare_dim_relations(extract_dim_relations(doc), extract_dim_relations(copy.deepcopy(doc)))

    assert report["status"] == "ok"
    assert report["fraction"] == 1.0
    assert report["mutated"] == 0
    assert report["missing"] == 0


def test_seed_offset_produces_disjoint_handles():
    doc_a = make_dim_ir(10, seed_offset=0)
    doc_b = make_dim_ir(10, seed_offset=10)

    handles_a = {entity["handle"] for entity in doc_a["dimensions"]}
    handles_b = {entity["handle"] for entity in doc_b["dimensions"]}

    assert handles_a.isdisjoint(handles_b)


@pytest.mark.parametrize("kind", MUTATION_KINDS)
def test_each_mutation_kind_is_convicted_by_compare_dim_relations(kind):
    truth = make_dim_ir(12)
    mutated = mutate(truth, kind)

    report = compare_dim_relations(extract_dim_relations(truth), extract_dim_relations(mutated))

    assert report["status"] == "blocked" or report["fraction"] < 1.0


def test_dim_deleted_reduces_total_b():
    truth = make_dim_ir(9)

    mutated = mutate(truth, "dim_deleted")

    report = compare_dim_relations(extract_dim_relations(truth), extract_dim_relations(mutated))

    assert report["total_b"] == report["total_a"] - 1


def test_mutate_does_not_modify_the_original_doc():
    truth = make_dim_ir(6)
    baseline = copy.deepcopy(truth)

    mutate(truth, "measurement_drift")

    assert truth == baseline


def test_mutate_rejects_unknown_kind():
    truth = make_dim_ir(4)

    with pytest.raises(ValueError):
        mutate(truth, "not_a_real_kind")
