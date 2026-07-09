#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic L5 semantic gate for block-topology preservation."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Tuple


BLOCK_TOPOLOGY_SEMANTIC_GATE_SCHEMA_ID = "ariadne.block_topology_gate.v1"
MODELSPACE_OWNER = "__modelspace__"

# Same *D measurement contract as blockdef_diff: dimension-derived cache
# blocks (and their arrow-block edges) are per-dimension rendered artifacts;
# a rebuild's dimensions mint fresh *D names. Filtering must happen BEFORE
# extraction -- anon_remap renames census *D defs (e.g. to ARIADNE_ANON_D*),
# measured on R4l, so a post-extraction name filter misses the a-side.
_DIM_CACHE_NAME = re.compile(r"^\*D\d+$")


def _normalize_name(name: Any, name_map: Dict[str, str]) -> str:
    if not isinstance(name, str):
        return ""
    return name_map.get(name, name)


def extract_block_topology(ir_doc: Dict[str, Any], *, name_map: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Extract a deterministic block-reference topology from an IR document."""
    mapping = name_map or {}
    block_defs = []
    edge_counts: Counter[Tuple[str, str]] = Counter()

    for block_def in ir_doc.get("block_definitions") or []:
        if not isinstance(block_def, dict):
            continue
        name = block_def.get("name")
        owner = _normalize_name(name, mapping)
        if not owner:
            continue
        block_defs.append(owner)

        for entity in block_def.get("def_entities") or []:
            if not isinstance(entity, dict):
                continue
            geometry = entity.get("geometry") or {}
            if not isinstance(geometry, dict):
                continue
            if geometry.get("kind") != "block_reference":
                continue
            block_name = geometry.get("block_name")
            target = _normalize_name(block_name, mapping)
            if not target:
                continue
            edge_counts[(owner, target)] += 1

    for entity in ir_doc.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        geometry = entity.get("geometry") or {}
        if not isinstance(geometry, dict):
            continue
        if geometry.get("kind") != "block_reference":
            continue
        block_name = geometry.get("block_name")
        target = _normalize_name(block_name, mapping)
        if not target:
            continue
        edge_counts[(MODELSPACE_OWNER, target)] += 1

    edges = [
        [owner, referenced, count]
        for (owner, referenced), count in sorted(edge_counts.items())
    ]
    return {
        "defs": sorted(set(block_defs)),
        "edges": edges,
    }


def compare_block_topology(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two extracted topologies and report deterministic deltas."""
    defs_a = sorted({name for name in (a.get("defs") or []) if isinstance(name, str)})
    defs_b = sorted({name for name in (b.get("defs") or []) if isinstance(name, str)})
    set_a = set(defs_a)
    set_b = set(defs_b)

    defs_missing = sorted(set_a - set_b)
    defs_extra = sorted(set_b - set_a)

    edges_a = {
        (edge[0], edge[1]): int(edge[2])
        for edge in (a.get("edges") or [])
        if isinstance(edge, (list, tuple))
        and len(edge) >= 3
        and isinstance(edge[0], str)
        and isinstance(edge[1], str)
    }
    edges_b = {
        (edge[0], edge[1]): int(edge[2])
        for edge in (b.get("edges") or [])
        if isinstance(edge, (list, tuple))
        and len(edge) >= 3
        and isinstance(edge[0], str)
        and isinstance(edge[1], str)
    }

    edges_missing: List[Sequence[Any]] = []
    edges_extra: List[Sequence[Any]] = []
    edge_count_mutations: List[Sequence[Any]] = []

    all_edges = set(edges_a) | set(edges_b)
    for owner, referenced in sorted(all_edges):
        count_a = edges_a.get((owner, referenced), 0)
        count_b = edges_b.get((owner, referenced), 0)

        if count_a and not count_b:
            edges_missing.append([owner, referenced, count_a])
        elif count_b and not count_a:
            edges_extra.append([owner, referenced, count_b])
        elif count_a != count_b:
            edge_count_mutations.append([owner, referenced, count_a, count_b])

    status = "ok"
    if any([defs_missing, defs_extra, edges_missing, edges_extra, edge_count_mutations]):
        status = "blocked"

    totals = {
        "defs_a": len(defs_a),
        "defs_b": len(defs_b),
        "edges_a": len(edges_a),
        "edges_b": len(edges_b),
        "defs_missing": len(defs_missing),
        "defs_extra": len(defs_extra),
        "edges_missing": len(edges_missing),
        "edges_extra": len(edges_extra),
        "edge_count_mutations": len(edge_count_mutations),
        "total_defs": len(defs_a) + len(defs_b),
        "total_edges": len(edges_a) + len(edges_b),
    }

    return {
        "schema": BLOCK_TOPOLOGY_SEMANTIC_GATE_SCHEMA_ID,
        "defs_missing": defs_missing,
        "defs_extra": defs_extra,
        "edges_missing": edges_missing,
        "edges_extra": edges_extra,
        "edge_count_mutations": edge_count_mutations,
        "status": status,
        "totals": totals,
    }


def _strip_derived_caches(ir_doc: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    """Drop ^\\*D\\d+$ block definitions from an IR doc (pre-extraction)."""
    block_defs = ir_doc.get("block_definitions") or []
    kept = [b for b in block_defs
            if not (isinstance(b, dict) and _DIM_CACHE_NAME.match(b.get("name") or ""))]
    dropped = len(block_defs) - len(kept)
    if not dropped:
        return ir_doc, 0
    out = dict(ir_doc)
    out["block_definitions"] = kept
    return out, dropped


def reachable_subgraph(topology: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Split a topology into (modelspace-reachable subgraph, unreachable defs).

    The regen replays the def graph reachable from the modelspace INSERTs;
    census defs referenced by nothing (orphan definitions, or defs referenced
    only by excluded *D caches -- e.g. DIMDOT/_ArchTick arrow blocks, measured
    on R4l) are outside that authored-reachable scope. They are returned
    separately for honest reporting, never silently dropped.
    """
    adjacency: Dict[str, set] = {}
    for edge in topology.get("edges") or []:
        if isinstance(edge, (list, tuple)) and len(edge) >= 3:
            adjacency.setdefault(edge[0], set()).add(edge[1])
    seen: set = set()
    stack = [MODELSPACE_OWNER]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency.get(node, ()))
    defs = [d for d in (topology.get("defs") or []) if isinstance(d, str)]
    reachable = {
        "defs": sorted(d for d in defs if d in seen),
        "edges": [e for e in (topology.get("edges") or [])
                  if isinstance(e, (list, tuple)) and len(e) >= 3
                  and (e[0] == MODELSPACE_OWNER or e[0] in seen)],
    }
    unreachable = sorted(d for d in defs if d not in seen)
    return reachable, unreachable


def block_topology_gate_report(census_ir: Dict[str, Any], post_ir: Dict[str, Any], *,
                               name_map: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """L5 semantic gate: the modelspace-reachable block-reference graph of the
    census must be preserved by the rebuild (insert topology, not counts).

    Contract (verified on R4l before wiring): *D derived caches excluded
    pre-extraction on both sides; the gate verdict compares the
    modelspace-REACHABLE subgraph (census defs unreachable from modelspace are
    outside the regen's replay scope and are reported, not folded into the
    verdict). R4l measured: 290/290 reachable defs, 711/711 edges preserved;
    4 census defs unreachable (DIMDOT/_ArchTick arrow blocks referenced only
    by excluded caches + 2 orphan definitions).
    """
    census_stripped, caches_a = _strip_derived_caches(census_ir or {})
    post_stripped, caches_b = _strip_derived_caches(post_ir or {})
    topo_a = extract_block_topology(census_stripped, name_map=name_map)
    topo_b = extract_block_topology(post_stripped)
    reachable_a, unreachable_a = reachable_subgraph(topo_a)
    report = compare_block_topology(reachable_a, topo_b)
    report["derived_cache_defs_excluded"] = {"a": caches_a, "b": caches_b,
                                             "name_pattern": _DIM_CACHE_NAME.pattern}
    report["census_defs_unreachable_from_modelspace"] = unreachable_a
    if not reachable_a["defs"] and not reachable_a["edges"]:
        report["status"] = "ok"
        report["note"] = "no reachable census block topology (vacuously ok)"
    return report


def _synthetic_topology() -> Dict[str, Any]:
    return {
        "block_definitions": [
            {
                "name": "A",
                "def_entities": [
                    {
                        "geometry": {
                            "kind": "block_reference",
                            "block_name": "B",
                            "position": [0.0, 0.0, 0.0],
                        },
                    },
                    {
                        "geometry": {
                            "kind": "block_reference",
                            "block_name": "B",
                            "position": [1.0, 0.0, 0.0],
                        },
                    },
                ],
            },
            {
                "name": "B",
                "def_entities": [
                    {
                        "geometry": {
                            "kind": "block_reference",
                            "block_name": "C",
                            "position": [0.0, 0.0, 0.0],
                        },
                    },
                ],
            },
            {
                "name": "C",
                "def_entities": [],
            },
        ],
        "entities": [
            {"geometry": {"kind": "block_reference", "block_name": "A", "position": [0.0, 0.0, 0.0]}},
            {"geometry": {"kind": "block_reference", "block_name": "B", "position": [1.0, 1.0, 0.0]}},
        ],
    }


def _mutate_block_topology(ir_doc: Dict[str, Any], kind: str) -> Dict[str, Any]:
    mutated = {
        "block_definitions": [dict(defn) for defn in ir_doc.get("block_definitions", [])],
        "entities": [dict(entity) for entity in ir_doc.get("entities", [])],
    }

    if kind == "drop_def":
        mutated["block_definitions"] = [defn for defn in mutated["block_definitions"] if defn.get("name") != "C"]

    elif kind == "drop_edge":
        mutated["entities"] = [entity for entity in mutated["entities"] if entity != mutated["entities"][0]]

    elif kind == "count_change":
        mutated["block_definitions"][0]["def_entities"].append(
            {
                "geometry": {
                    "kind": "block_reference",
                    "block_name": "B",
                    "position": [2.0, 0.0, 0.0],
                },
            }
        )

    elif kind == "rename":
        mutated["block_definitions"][0]["name"] = "A_RENAMED"

    else:
        raise ValueError(f"unknown mutation {kind!r}")

    return mutated


def self_test_mutations() -> Dict[str, Any]:
    """Author a tiny synthetic topology, then confirm each mutation is blocked."""
    ir_a = _synthetic_topology()
    topology_a = extract_block_topology(ir_a)
    report_identical = compare_block_topology(topology_a, topology_a)
    assert report_identical["status"] == "ok"

    report_drop_def = compare_block_topology(topology_a, extract_block_topology(_mutate_block_topology(ir_a, "drop_def")))
    assert report_drop_def["status"] == "blocked"
    assert report_drop_def["defs_missing"] == ["C"]

    report_drop_edge = compare_block_topology(topology_a, extract_block_topology(_mutate_block_topology(ir_a, "drop_edge")))
    assert report_drop_edge["status"] == "blocked"
    assert report_drop_edge["edges_missing"] == [["__modelspace__", "A", 1]]

    report_count_change = compare_block_topology(topology_a, extract_block_topology(_mutate_block_topology(ir_a, "count_change")))
    assert report_count_change["status"] == "blocked"
    assert report_count_change["edge_count_mutations"] == [["A", "B", 2, 3]]

    report_rename = compare_block_topology(topology_a, extract_block_topology(_mutate_block_topology(ir_a, "rename")))
    assert report_rename["status"] == "blocked"
    assert report_rename["defs_missing"] == ["A"]
    assert report_rename["defs_extra"] == ["A_RENAMED"]

    return {
        "identical": report_identical,
        "drop_def": report_drop_def,
        "drop_edge": report_drop_edge,
        "count_change": report_count_change,
        "rename": report_rename,
    }

