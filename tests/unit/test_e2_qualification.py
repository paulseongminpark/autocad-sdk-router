#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.e2.qualification.engine import (  # noqa: E402
    _runtime_wall_guard_qualified,
    build_first_report,
)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_first_report_is_evidence_bound_and_schema_valid(tmp_path: Path):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"fixture-dwg")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    native = {
        "schema": "ariadne.dwg_graph_ir.v1",
        "coverage_level": "native_full",
        "source": {"sha256": source_hash},
        "database": {"units": {"insunits": 4}},
        "entities": [
            {
                "handle": "E1",
                "dxf_name": "LINE",
                "source": {"decoded": True},
                "geometry": {"start": [0, 0, 0], "end": [1000, 0, 0]},
            }
        ],
        "block_definitions": [],
        "diagnostics": {
            "errors": [],
            "warnings": [],
            "coverage": {
                "modelspace_count_from_native": 1,
                "realized_entity_count": 1,
                "match": True,
                "sections_present": ["entities"],
                "sections_skipped": ["groups"],
                "section_status": {"proxy_objects": "partial"},
            },
        },
    }
    adapter = {
        "ir": "worldir.input.v1",
        "status": "PASS",
        "drawing_id": source_hash,
        "root": "1F",
        "definitions": {
            "1F": {
                "handle": "1F",
                "base_point": [0, 0],
                "entities": [
                    {"handle": "E1", "kind": "LINE", "layer": "WALL", "start": [0, 0], "end": [1000, 0]}
                ],
            }
        },
        "adapter_ledger": {
            "scope": "LINE_POLYLINE_ARC_INSERT",
            "source_entity_templates": 1,
            "adapted_entity_templates": 1,
            "explicitly_excluded_entity_templates": 0,
            "excluded_invalid_geometry_templates": 0,
            "excluded_degenerate_subsegments": 0,
            "excluded_by_dxf_name": {},
            "balance_ok": True,
        },
    }
    world = {
        "oracle": "worldir.oracle.v1",
        "status": "PASS",
        "drawing_id": source_hash,
        "input_mode": "definition_graph",
        "segments": [
            {
                "placed_uid": "P1",
                "source_entity_handle": "E1",
                "source_def_handle": "1F",
                "p0_world": [0, 0],
                "p1_world": [1000, 0],
            }
        ],
        "conservation_ledger": {
            "expected_segment_instances": 1,
            "visible_source_segment_instances": 1,
            "clipped_away_segment_instances": 0,
            "partially_clipped_segment_instances": 0,
            "clip_generated_fragment_instances": 0,
            "emitted_segment_instances": 1,
            "conservation_delta": 0,
            "conservation_ok": True,
            "entity_entries": [{"status": "PRESERVED"}],
        },
        "failure_ledger": [],
    }
    native_path = tmp_path / "native.json"
    adapter_path = tmp_path / "adapter.json"
    world_path = tmp_path / "world.json"
    _write_json(native_path, native)
    _write_json(adapter_path, adapter)
    _write_json(world_path, world)
    spec = {
        "schema": "e2.experiment_spec.v1",
        "experiment_id": "fixture",
        "created_at": "2026-08-03T00:00:00Z",
        "target": "wall",
        "source": {"path": str(source), "sha256": source_hash, "read_only": True},
        "evidence": {
            "native_ir": str(native_path),
            "adapter_ir": str(adapter_path),
            "world_ir": str(world_path),
        },
        "interventions": ["rotate_37_degrees"],
    }

    result = build_first_report(spec, tmp_path / "run")

    assert result["status"] == "PARTIAL_PASS"
    assert (tmp_path / "run" / "REPORT.md").is_file()
    receipt = json.loads((tmp_path / "run" / "qualification_receipt.json").read_text(encoding="utf-8"))
    assert receipt["source"]["sha256"] == source_hash
    assert any(row["gate"] == "world_transform_and_xclip_conservation" and row["status"] == "PASS" for row in receipt["gates"])

    for schema_name, instance in (
        ("e2_experiment_spec.v1.schema.json", spec),
        ("e2_qualification_receipt.v1.schema.json", receipt),
        ("world_geometry_ir.v1.schema.json", world),
    ):
        schema = json.loads((REPO / "schemas" / schema_name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(instance)


def test_tool_registry_has_unique_ids_and_required_gates():
    with (REPO / "config" / "e2_tool_registry.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    ids = [row["tool_id"] for row in rows]
    assert len(ids) == len(set(ids))
    assert {"native_objectarx_graph", "wall_evidence_grid", "gbdt_wall_arm", "gnn_wall_arm"} <= set(ids)
    assert all(row["qualification_gate"] for row in rows)


def test_wall_report_rejects_legacy_xclip_only_guard():
    legacy = {
        "status": "READY",
        "required_observables": [
            "nested_insert_world_segments",
            "world_lineage",
            "silent_drop_detection",
            "xclip_preservation",
        ],
    }
    target_qualified = {
        **legacy,
        "required_observables": [
            *legacy["required_observables"],
            "source_document_identity",
            "native_display_membership",
            "model_input_membership",
        ],
        "target_population": {
            "wall-w1": {"model_input_segments": 1},
            "wall-w2": {"model_input_segments": 1},
        },
    }

    assert _runtime_wall_guard_qualified(legacy) is False
    assert _runtime_wall_guard_qualified(target_qualified) is True
