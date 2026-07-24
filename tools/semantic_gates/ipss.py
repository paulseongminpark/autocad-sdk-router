#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Insidious planted-defect semantic suite for L5 gate sanity.

This suite exists because count-parity verification was measured blind to
semantic damage: the interior-100 program's naive fraction could not see
swapped dimension measurements. IPSS keeps every mutation count-preserving,
then requires the semantic gates to convict the planted defect.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
from collections import Counter
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple

try:
    from .block_topology import block_topology_gate_report
    from .dim_geometry import compare_dim_relations, extract_dim_relations
    from .synthetic_truth import make_dim_ir
except ImportError:  # pragma: no cover - script execution path
    _REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _REPO not in sys.path:
        sys.path.insert(0, _REPO)
    from tools.semantic_gates.block_topology import block_topology_gate_report
    from tools.semantic_gates.dim_geometry import compare_dim_relations, extract_dim_relations
    from tools.semantic_gates.synthetic_truth import make_dim_ir


IPSS_SCHEMA_ID = "ariadne.ipss.v1"
NAIVE_GATE_SCHEMA_ID = "ariadne.ipss.naive_gate.v1"

Mutation = Callable[[Dict[str, Any]], Dict[str, Any]]


def _block_ref(handle: str, block_name: str, position: Sequence[float]) -> Dict[str, Any]:
    return {
        "handle": handle,
        "dxf_name": "INSERT",
        "layer": "0",
        "space": "model",
        "geometry": {
            "kind": "block_reference",
            "block_name": block_name,
            "position": list(position),
        },
    }


def _line(handle: str, start: Sequence[float], end: Sequence[float]) -> Dict[str, Any]:
    return {
        "handle": handle,
        "dxf_name": "LINE",
        "layer": "0",
        "space": "model",
        "geometry": {
            "kind": "line",
            "start": list(start),
            "end": list(end),
        },
    }


def make_ipss_base_ir(n_dims: int = 8) -> Dict[str, Any]:
    """Build a deterministic IR with dimensions plus reachable block topology."""
    dim_doc = make_dim_ir(n_dims)
    entities: List[Dict[str, Any]] = []

    for anchor in dim_doc["anchor_geometry"]:
        entities.append(
            {
                "handle": anchor["handle"],
                "dxf_name": "LINE",
                "layer": anchor.get("layer", "0"),
                "space": "model",
                "geometry": copy.deepcopy(anchor["geometry"]),
            }
        )
    for dimension in dim_doc["dimensions"]:
        entities.append(
            {
                "handle": dimension["handle"],
                "dxf_name": "DIMENSION",
                "layer": dimension.get("layer", "DIM"),
                "space": "model",
                "geometry": copy.deepcopy(dimension["geometry"]),
            }
        )

    entities.extend(
        [
            _block_ref("MS_INSERT_A", "A", [0.0, 20000.0, 0.0]),
            _block_ref("MS_INSERT_B", "B", [1000.0, 20000.0, 0.0]),
        ]
    )

    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "entities": entities,
        "block_definitions": [
            {
                "name": "A",
                "handle": "DEF_A",
                "def_entities": [
                    _block_ref("A_TO_C", "C", [0.0, 0.0, 0.0]),
                    _line("A_FILLER", [0.0, 0.0, 0.0], [10.0, 0.0, 0.0]),
                ],
            },
            {
                "name": "B",
                "handle": "DEF_B",
                "def_entities": [
                    _block_ref("B_TO_D", "D", [0.0, 0.0, 0.0]),
                    _line("B_FILLER", [0.0, 1.0, 0.0], [10.0, 1.0, 0.0]),
                ],
            },
            {"name": "C", "handle": "DEF_C", "def_entities": []},
            {"name": "D", "handle": "DEF_D", "def_entities": []},
        ],
    }


def _dxf_histogram(ir_doc: Mapping[str, Any]) -> Counter:
    return Counter(
        entity.get("dxf_name")
        for entity in (ir_doc.get("entities") or [])
        if isinstance(entity, Mapping)
    )


def _def_entity_counts(ir_doc: Mapping[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for block_def in ir_doc.get("block_definitions") or []:
        if not isinstance(block_def, Mapping):
            continue
        name = block_def.get("name")
        counts[str(name)] = len(block_def.get("def_entities") or [])
    return counts


def naive_gate(ir_a: Dict[str, Any], ir_b: Dict[str, Any]) -> Dict[str, Any]:
    """Pass iff the count-only strawman sees no entity or def-count delta."""
    entities_a = ir_a.get("entities") or []
    entities_b = ir_b.get("entities") or []
    total_entity_count_a = len(entities_a)
    total_entity_count_b = len(entities_b)
    dxf_histogram_a = _dxf_histogram(ir_a)
    dxf_histogram_b = _dxf_histogram(ir_b)
    def_entity_counts_a = _def_entity_counts(ir_a)
    def_entity_counts_b = _def_entity_counts(ir_b)

    status = "ok"
    if (
        total_entity_count_a != total_entity_count_b
        or dxf_histogram_a != dxf_histogram_b
        or def_entity_counts_a != def_entity_counts_b
    ):
        status = "blocked"

    return {
        "schema": NAIVE_GATE_SCHEMA_ID,
        "status": status,
        "total_entity_count_a": total_entity_count_a,
        "total_entity_count_b": total_entity_count_b,
        "dxf_histogram_a": dict(sorted(dxf_histogram_a.items())),
        "dxf_histogram_b": dict(sorted(dxf_histogram_b.items())),
        "def_entity_counts_a": dict(sorted(def_entity_counts_a.items())),
        "def_entity_counts_b": dict(sorted(def_entity_counts_b.items())),
    }


def _dimension_entities(ir_doc: MutableMapping[str, Any]) -> List[Dict[str, Any]]:
    return [
        entity
        for entity in (ir_doc.get("entities") or [])
        if isinstance(entity, dict)
        and isinstance(entity.get("geometry"), dict)
        and entity["geometry"].get("kind") == "dimension"
    ]


def _projected_span(geometry: Mapping[str, Any], *, rotation: float | None = None) -> float:
    xline1 = geometry["xline1_point"]
    xline2 = geometry["xline2_point"]
    angle = float(geometry["rotation"] if rotation is None else rotation)
    unit = (math.cos(angle), math.sin(angle))
    delta = (float(xline2[0]) - float(xline1[0]), float(xline2[1]) - float(xline1[1]))
    return abs(delta[0] * unit[0] + delta[1] * unit[1])


def dim_measurement_swap(ir_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Swap measurements on two dimensions whose true spans differ."""
    doc = copy.deepcopy(ir_doc)
    by_handle = {entity.get("handle"): entity for entity in _dimension_entities(doc)}
    rows = extract_dim_relations(doc)
    for left_idx, left in enumerate(rows):
        for right in rows[left_idx + 1:]:
            if abs(float(left["span"]) - float(right["span"])) <= 1e-6:
                continue
            left_entity = by_handle.get(left.get("handle"))
            right_entity = by_handle.get(right.get("handle"))
            if left_entity is None or right_entity is None:
                continue
            left_geom = left_entity["geometry"]
            right_geom = right_entity["geometry"]
            left_geom["measurement"], right_geom["measurement"] = (
                right_geom["measurement"],
                left_geom["measurement"],
            )
            return doc
    raise ValueError("need two dimensions with different true spans")


def dim_xline_shift(ir_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Move one dimension extension point without changing its measurement."""
    doc = copy.deepcopy(ir_doc)
    dimensions = _dimension_entities(doc)
    if not dimensions:
        raise ValueError("ir_doc has no dimension entities")
    dimensions[0]["geometry"]["xline2_point"][0] += 750.0
    return doc


def insert_retarget(ir_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Retarget modelspace inserts to different existing blocks, preserving counts."""
    doc = copy.deepcopy(ir_doc)
    block_names = [
        block_def.get("name")
        for block_def in (doc.get("block_definitions") or [])
        if isinstance(block_def, Mapping) and isinstance(block_def.get("name"), str)
    ]
    inserts = [
        entity
        for entity in (doc.get("entities") or [])
        if isinstance(entity, dict)
        and isinstance(entity.get("geometry"), dict)
        and entity["geometry"].get("kind") == "block_reference"
        and entity["geometry"].get("block_name") in block_names
    ]
    if len(inserts) < 2 or len(block_names) < 4:
        raise ValueError("need two inserts and four existing block definitions")

    inserts[0]["geometry"]["block_name"] = block_names[2]
    inserts[1]["geometry"]["block_name"] = block_names[3]
    return doc


def def_entity_reparent(ir_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Swap geometry-different def entities between equal-sized block defs."""
    doc = copy.deepcopy(ir_doc)
    block_defs = [
        block_def
        for block_def in (doc.get("block_definitions") or [])
        if isinstance(block_def, dict) and isinstance(block_def.get("def_entities"), list)
    ]
    for left_idx, left_def in enumerate(block_defs):
        left_entities = left_def["def_entities"]
        for right_def in block_defs[left_idx + 1:]:
            right_entities = right_def["def_entities"]
            if len(left_entities) != len(right_entities):
                continue
            for left_entity_idx, left_entity in enumerate(left_entities):
                left_geometry = left_entity.get("geometry") if isinstance(left_entity, dict) else None
                if not isinstance(left_geometry, dict) or left_geometry.get("kind") != "block_reference":
                    continue
                for right_entity_idx, right_entity in enumerate(right_entities):
                    right_geometry = right_entity.get("geometry") if isinstance(right_entity, dict) else None
                    if not isinstance(right_geometry, dict) or right_geometry.get("kind") != "block_reference":
                        continue
                    if left_geometry == right_geometry:
                        continue
                    left_entities[left_entity_idx], right_entities[right_entity_idx] = (
                        right_entities[right_entity_idx],
                        left_entities[left_entity_idx],
                    )
                    return doc
    raise ValueError("need equal-sized block defs with geometry-different block references")


def rotation_sign_flip(ir_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Negate one dimension rotation where the projected span changes."""
    doc = copy.deepcopy(ir_doc)
    for dimension in _dimension_entities(doc):
        geometry = dimension["geometry"]
        rotation = float(geometry.get("rotation", 0.0))
        if rotation == 0.0:
            continue
        if abs(_projected_span(geometry) - _projected_span(geometry, rotation=-rotation)) <= 1e-6:
            continue
        geometry["rotation"] = -rotation
        return doc
    raise ValueError("need a dimension whose span changes under rotation sign flip")


MUTATIONS: Dict[str, Mutation] = {
    "dim_measurement_swap": dim_measurement_swap,
    "dim_xline_shift": dim_xline_shift,
    "insert_retarget": insert_retarget,
    "def_entity_reparent": def_entity_reparent,
    "rotation_sign_flip": rotation_sign_flip,
}


def _iter_mutations(registry: Mapping[str, Mutation] | Iterable[Tuple[str, Mutation]]) -> Iterable[Tuple[str, Mutation]]:
    return registry.items() if isinstance(registry, Mapping) else registry


def run_ipss(n_dims: int = 8) -> Dict[str, Any]:
    """Run every registered planted defect against the naive and semantic gates."""
    base = make_ipss_base_ir(n_dims)
    base_dim_rows = extract_dim_relations(base)
    cases: List[Dict[str, Any]] = []

    for name, mutation in _iter_mutations(MUTATIONS):
        mutated = mutation(base)
        naive_report = naive_gate(base, mutated)
        if naive_report["status"] != "ok":
            raise AssertionError(f"mutation {name!r} is not count-preserving")

        dim_report = compare_dim_relations(base_dim_rows, extract_dim_relations(mutated))
        topology_report = block_topology_gate_report(base, mutated)
        dim_status = dim_report["status"]
        topology_status = topology_report["status"]
        guilty = dim_status != "ok" or topology_status != "ok"

        cases.append(
            {
                "mutation": name,
                "naive_status": naive_report["status"],
                "dim_gate_status": dim_status,
                "topology_gate_status": topology_status,
                "guilty": guilty,
            }
        )

    status = "ok" if all(case["naive_status"] == "ok" and case["guilty"] for case in cases) else "blocked"
    return {"schema": IPSS_SCHEMA_ID, "cases": cases, "status": status}


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-dims", type=int, default=8, help="Number of synthetic dimensions to plant")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    report = run_ipss(n_dims=args.n_dims)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
