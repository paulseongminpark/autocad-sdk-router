#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for the IPSS planted-defect semantic suite."""

from __future__ import annotations

import copy
import os
import sys

import pytest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools.semantic_gates import ipss  # noqa: E402
from tools.semantic_gates.block_topology import block_topology_gate_report  # noqa: E402
from tools.semantic_gates.dim_geometry import compare_dim_relations, extract_dim_relations  # noqa: E402


@pytest.mark.parametrize("mutation_name,mutation", list(ipss.MUTATIONS.items()))
def test_each_registered_mutation_is_naive_pass_and_semantically_convicted(mutation_name, mutation):
    base = ipss.make_ipss_base_ir()
    mutated = mutation(base)

    naive_report = ipss.naive_gate(base, mutated)
    dim_report = compare_dim_relations(extract_dim_relations(base), extract_dim_relations(mutated))
    topology_report = block_topology_gate_report(base, mutated)

    assert naive_report["status"] == "ok", mutation_name
    assert dim_report["status"] == "blocked" or topology_report["status"] == "blocked", mutation_name


def test_run_ipss_overall_status_ok():
    report = ipss.run_ipss()

    assert report["schema"] == "ariadne.ipss.v1"
    assert report["status"] == "ok"
    assert [case["mutation"] for case in report["cases"]] == list(ipss.MUTATIONS)
    assert all(case["naive_status"] == "ok" and case["guilty"] for case in report["cases"])


def test_run_ipss_reports_blocked_when_a_mutation_escapes(monkeypatch):
    mutations = dict(ipss.MUTATIONS)
    mutations["noop_escape"] = lambda ir_doc: copy.deepcopy(ir_doc)
    monkeypatch.setattr(ipss, "MUTATIONS", mutations)

    report = ipss.run_ipss()

    escape = [case for case in report["cases"] if case["mutation"] == "noop_escape"][0]
    assert report["status"] == "blocked"
    assert escape["naive_status"] == "ok"
    assert escape["dim_gate_status"] == "ok"
    assert escape["topology_gate_status"] == "ok"
    assert escape["guilty"] is False


def test_naive_gate_passes_identical_irs_and_blocks_entity_count_change():
    base = ipss.make_ipss_base_ir()

    assert ipss.naive_gate(base, copy.deepcopy(base))["status"] == "ok"

    changed = copy.deepcopy(base)
    changed["entities"].pop()

    assert ipss.naive_gate(base, changed)["status"] == "blocked"
