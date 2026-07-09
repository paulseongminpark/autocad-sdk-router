#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for the block-topology semantic gate."""

from __future__ import annotations

import copy
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools.semantic_gates.block_topology import (  # noqa: E402
    BLOCK_TOPOLOGY_SEMANTIC_GATE_SCHEMA_ID,
    compare_block_topology,
    extract_block_topology,
    self_test_mutations,
)


def _block_reference(block_name: str, position) -> dict:
    return {
        "geometry": {
            "kind": "block_reference",
            "block_name": block_name,
            "position": position,
        },
    }


def _base_topology_ir() -> dict:
    return {
        "block_definitions": [
            {"name": "A", "def_entities": [
                _block_reference("B", [0.0, 0.0, 0.0]),
                _block_reference("B", [1.0, 0.0, 0.0]),
            ]},
            {"name": "B", "def_entities": [
                _block_reference("C", [0.0, 0.0, 0.0]),
            ]},
            {"name": "C", "def_entities": []},
        ],
        "entities": [
            _block_reference("A", [0.0, 0.0, 0.0]),
            _block_reference("B", [2.0, 0.0, 0.0]),
        ],
    }


def _sorted_edges(edges):
    return sorted(
        [list(edge) for edge in edges],
        key=lambda edge: (edge[0], edge[1], edge[2]),
    )


def test_extract_block_topology_builds_sorted_defs_and_edges():
    topology = extract_block_topology(_base_topology_ir())

    assert topology["defs"] == ["A", "B", "C"]
    assert _sorted_edges(topology["edges"]) == _sorted_edges([
        ["__modelspace__", "A", 1],
        ["__modelspace__", "B", 1],
        ["A", "B", 2],
        ["B", "C", 1],
    ])


def test_compare_identical_topologies_reports_ok():
    topology_a = extract_block_topology(_base_topology_ir())
    topology_b = extract_block_topology(_base_topology_ir())

    report = compare_block_topology(topology_a, topology_b)

    assert report["schema"] == BLOCK_TOPOLOGY_SEMANTIC_GATE_SCHEMA_ID
    assert report["status"] == "ok"
    assert report["defs_missing"] == []
    assert report["defs_extra"] == []
    assert report["edges_missing"] == []
    assert report["edges_extra"] == []
    assert report["edge_count_mutations"] == []
    assert report["totals"]["defs_a"] == 3
    assert report["totals"]["defs_b"] == 3
    assert report["totals"]["edges_a"] == 4
    assert report["totals"]["edges_b"] == 4


def test_compare_mutation_drops_definition():
    topology_a = extract_block_topology(_base_topology_ir())
    mutated = copy.deepcopy(_base_topology_ir())
    mutated["block_definitions"] = [d for d in mutated["block_definitions"] if d["name"] != "C"]

    report = compare_block_topology(topology_a, extract_block_topology(mutated))

    assert report["status"] == "blocked"
    assert report["defs_missing"] == ["C"]
    assert report["defs_extra"] == []


def test_compare_mutation_drops_edge():
    topology_a = extract_block_topology(_base_topology_ir())
    mutated = copy.deepcopy(_base_topology_ir())
    mutated["entities"] = [mutated["entities"][0]]

    report = compare_block_topology(topology_a, extract_block_topology(mutated))

    assert report["status"] == "blocked"
    assert report["edges_missing"] == [["__modelspace__", "B", 1]]
    assert report["edges_extra"] == []


def test_compare_mutation_changes_edge_count():
    topology_a = extract_block_topology(_base_topology_ir())
    mutated = copy.deepcopy(_base_topology_ir())
    mutated["block_definitions"][0]["def_entities"].append(_block_reference("B", [3.0, 0.0, 0.0]))

    report = compare_block_topology(topology_a, extract_block_topology(mutated))

    assert report["status"] == "blocked"
    assert report["edge_count_mutations"] == [["A", "B", 2, 3]]


def test_compare_mutation_rename_without_name_map_blocks():
    topology_a = extract_block_topology(_base_topology_ir())
    mutated = copy.deepcopy(_base_topology_ir())
    mutated["block_definitions"][0]["name"] = "A_RENAMED"

    report = compare_block_topology(topology_a, extract_block_topology(mutated))

    assert report["status"] == "blocked"
    assert report["defs_missing"] == ["A"]
    assert report["defs_extra"] == ["A_RENAMED"]


def test_name_map_normalizes_anonymous_block_refs():
    ir_a = {
        "block_definitions": [
            {
                "name": "*U172",
                "def_entities": [
                    _block_reference("*U9", [0.0, 0.0, 0.0]),
                ],
            },
            {"name": "*U9", "def_entities": []},
        ],
        "entities": [_block_reference("*U172", [0.0, 0.0, 0.0])],
    }
    ir_b = {
        "block_definitions": [
            {
                "name": "ARIADNE_ANON_U172",
                "def_entities": [
                    _block_reference("ARIADNE_ANON_U9", [0.0, 0.0, 0.0]),
                ],
            },
            {"name": "ARIADNE_ANON_U9", "def_entities": []},
        ],
        "entities": [_block_reference("ARIADNE_ANON_U172", [0.0, 0.0, 0.0])],
    }
    name_map = {"*U172": "ARIADNE_ANON_U172", "*U9": "ARIADNE_ANON_U9"}

    report = compare_block_topology(
        extract_block_topology(ir_a, name_map=name_map),
        extract_block_topology(ir_b, name_map=name_map),
    )

    assert report["status"] == "ok"


def test_self_test_mutations_runs_without_failing():
    result = self_test_mutations()

    assert result["identical"]["status"] == "ok"
    assert result["drop_def"]["status"] == "blocked"
    assert result["drop_edge"]["status"] == "blocked"
    assert result["count_change"]["status"] == "blocked"
    assert result["rename"]["status"] == "blocked"


# ---- block_topology_gate_report (capstone wiring contract, R4l-verified) ----

from tools.semantic_gates import block_topology  # noqa: E402


def _gate_ir(defs, ms_inserts):
    return {
        "block_definitions": defs,
        "entities": [
            {"geometry": {"kind": "block_reference", "block_name": n,
                          "position": [0.0, 0.0, 0.0]}}
            for n in ms_inserts
        ],
    }


def _gate_def(name, *refs):
    return {
        "name": name,
        "def_entities": [
            {"geometry": {"kind": "block_reference", "block_name": r,
                          "position": [0.0, 0.0, 0.0]}}
            for r in refs
        ],
    }


def test_gate_report_ok_when_reachable_graph_preserved():
    # Census: modelspace->A->B reachable; ORPHAN + arrow block (referenced
    # only by the *D cache) unreachable; *D7 cache excluded pre-extraction.
    census = _gate_ir(
        [_gate_def("A", "B"), _gate_def("B"), _gate_def("ORPHAN"),
         _gate_def("DIMDOT"), _gate_def("*D7", "DIMDOT")],
        ms_inserts=["A"],
    )
    post = _gate_ir(
        [_gate_def("A", "B"), _gate_def("B"), _gate_def("*D9", "SOMETHING")],
        ms_inserts=["A"],
    )

    report = block_topology.block_topology_gate_report(census, post)

    assert report["status"] == "ok"
    assert report["census_defs_unreachable_from_modelspace"] == ["DIMDOT", "ORPHAN"]
    assert report["derived_cache_defs_excluded"]["a"] == 1
    assert report["derived_cache_defs_excluded"]["b"] == 1


def test_gate_report_blocks_on_reachable_edge_loss():
    census = _gate_ir([_gate_def("A", "B"), _gate_def("B")], ms_inserts=["A"])
    post = _gate_ir([_gate_def("A"), _gate_def("B")], ms_inserts=["A"])

    report = block_topology.block_topology_gate_report(census, post)

    assert report["status"] == "blocked"
    assert report["edges_missing"] == [["A", "B", 1]]


def test_gate_report_applies_anon_remap_to_census_side():
    census = _gate_ir([_gate_def("*U5", "B"), _gate_def("B")], ms_inserts=["*U5"])
    post = _gate_ir([_gate_def("ANON_CLONE", "B"), _gate_def("B")],
                    ms_inserts=["ANON_CLONE"])

    report = block_topology.block_topology_gate_report(
        census, post, name_map={"*U5": "ANON_CLONE"})

    assert report["status"] == "ok"


def test_gate_report_vacuous_ok_without_topology():
    census = _gate_ir([], ms_inserts=[])
    post = _gate_ir([], ms_inserts=[])

    report = block_topology.block_topology_gate_report(census, post)

    assert report["status"] == "ok"
    assert "vacuously ok" in report["note"]
