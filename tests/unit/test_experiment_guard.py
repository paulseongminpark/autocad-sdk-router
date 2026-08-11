#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_E2 = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "tools", "e2"))
if _TOOLS_E2 not in sys.path:
    sys.path.insert(0, _TOOLS_E2)

import experiment_guard as guard
import run_guarded_experiment as guarded_runner


OBSERVATION_COMMAND = [
    sys.executable,
    str(Path(_TOOLS_E2) / "experiment_guard.py"),
    "--require",
    "vendor_custom_wall_semantics",
]


def _minimal_dwg_bytes(payload: bytes = b"test fixture") -> bytes:
    """A header-only DWG fixture; the guard intentionally does not parse DWGs."""

    return b"AC1027" + payload


_TARGET_SOURCE_BYTES = _minimal_dwg_bytes(b"target population fixture")
_TARGET_SOURCE_SHA256 = hashlib.sha256(_TARGET_SOURCE_BYTES).hexdigest()


class _Completed:
    def __init__(self, returncode: object = 0) -> None:
        self.returncode = returncode


def _assert_authoritative_receipt(result: dict, receipt_path: Path) -> dict:
    saved = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert saved == result
    assert saved["receipt_phase"] == "TERMINAL"
    return saved


def _assert_nonterminal_preflight(receipt_path: Path) -> dict:
    preflight = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert preflight["receipt_phase"] == "PREFLIGHT"
    assert preflight["terminal_state"] == "NON_TERMINAL"
    assert preflight["execution_outcome"] == "PREFLIGHT_NON_TERMINAL"
    assert preflight["guard"]["status"] == guard.BLOCKED
    assert preflight["qualification"]["status"] == guard.READY
    assert preflight["command_succeeded"] is False
    assert preflight["terminal_authorized"] is False
    assert preflight["terminal_success"] is False
    return preflight


def _rich_ir(*, include_hatch=True, entity_count=3, proxy_status="partial"):
    sections = [
        "entities",
        "database",
        "symbol_tables",
        "block_table_records",
        "block_definitions",
        "layouts",
        "xrefs",
        "dictionaries",
        "xrecords",
        "xdata",
    ]
    if include_hatch:
        sections.append("hatch_loops")
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "coverage_level": "native_full",
        "database": {},
        "symbol_tables": {"layers": [{"name": "0"}]},
        "block_definitions": [{"name": "WALL"}],
        "block_references": [{"block_name": "WALL"}],
        "layouts": [],
        "xrefs": [],
        "dictionaries": [],
        "xrecords": [],
        "entities": [{"dxf_name": "LINE", "layer": "0"}] * entity_count,
        "diagnostics": {
            "entity_count": entity_count,
            "realized_entity_count": entity_count,
            "warnings": [],
            "errors": [],
            "coverage": {
                "modelspace_count_from_native": entity_count,
                "realized_entity_count": entity_count,
                "match": True,
                "sections_present": sections,
                "sections_skipped": ["groups"],
                "section_status": {
                    **{name: "implemented" for name in sections},
                    "layers": "implemented",
                    "proxy_objects": proxy_status,
                },
                "counts": {"hatch_loops": 2 if include_hatch else 0},
                "proxy_or_undecoded_count": 0,
            },
        },
    }


def test_counts_only_claim_selects_summary_and_needs_live_probe():
    result = guard.qualify(
        required_observables=["database_counts", "drawing_units"],
        candidate="auto",
    )
    assert result["status"] == guard.NEEDS_PROBE
    assert result["selected_pipeline"] == "database_summary"


def test_rich_claim_rejects_summary_and_selects_native_graph():
    result = guard.qualify(
        required_observables=[
            "modelspace_geometry",
            "block_definitions",
            "nested_insert_graph",
            "hatch_boundary_loops",
            "layer_provenance",
        ],
        candidate="database_summary",
    )
    assert result["status"] == guard.NEEDS_PROBE
    assert result["selected_pipeline"] == "native_graph"
    assert result["candidate_accepted"] is False
    assert "database_summary" in result["rejected_candidates"]


def test_unknown_observable_never_degrades_to_a_weaker_tool():
    result = guard.qualify(
        required_observables=["vendor_custom_wall_semantics"],
        candidate="auto",
    )
    assert result["status"] == guard.NEEDS_TOOL
    assert result["selected_pipeline"] is None


def test_missing_rich_graph_to_worldir_bridge_is_needs_build():
    result = guard.qualify(
        required_observables=["nested_insert_world_geometry"],
        candidate="auto",
    )
    assert result["status"] == guard.NEEDS_BUILD
    assert result["selected_pipeline"] is None
    assert "rich_graph_to_worldir" in result["missing_builds"]


def _worldir_probe(*, adapter_balance=True, conservation=True, inserts=1):
    return {
        "oracle": "worldir.oracle.v1",
        "status": "PASS",
        "drawing_id": "probe",
        "input_mode": "definition_graph",
        "segments": [{"lineage_id": "L1", "p0_world": [0, 0], "p1_world": [1, 0]}],
        "adapter_ledger": {
            "scope": "LINE_POLYLINE_ARC_INSERT",
            "source_entity_templates": 3,
            "adapted_entity_templates": 3 if adapter_balance else 2,
            "explicitly_excluded_entity_templates": 0,
            "excluded_by_dxf_name": {},
            "balance_ok": adapter_balance,
        },
        "conservation_ledger": {
            "reachable_insert_placements": inserts,
            "expected_segment_instances": 1,
            "visible_source_segment_instances": 1 if conservation else 0,
            "clipped_away_segment_instances": 0,
            "clip_generated_fragment_instances": 0,
            "emitted_segment_instances": 1 if conservation else 0,
            "conservation_delta": 0 if conservation else 1,
            "conservation_ok": conservation,
        },
        "failure_ledger": [],
    }


def _bind_authoritative_target_oracle(tmp_path: Path, oracle: dict) -> dict:
    source_path = tmp_path / "target_source.dwg"
    source_path.write_bytes(_TARGET_SOURCE_BYTES)
    drawing_id = hashlib.sha256(source_path.read_bytes()).hexdigest()
    oracle["drawing_id"] = drawing_id
    receipt_path = tmp_path / "display_membership_receipt.json"
    oracle_path = tmp_path / "target_population_oracle.json"
    geometry_scope = oracle.get("geometry_scope") or "strict_layer_entities_v1"
    staged_path = tmp_path / "target_staged.dwg"
    staged_path.write_bytes(source_path.read_bytes())
    raw_path = tmp_path / "native_job_out.json"
    raw_path.write_text('{"native":true}', encoding="utf-8")
    attended_path = tmp_path / "attended_final_receipt.json"
    attended_path.write_text('{"receipt":true}', encoding="utf-8")
    manifest_path = tmp_path / "native_build_manifest.json"
    manifest_path.write_text('{"manifest":true}', encoding="utf-8")

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    oracle.update(
        {
            "status": "OBSERVED",
            "claim_scope": "instrument_observation_only",
            "producer_receipt_required": True,
            "producer_receipt_path": str(receipt_path.resolve()),
            "downstream_experiment_guard_required": True,
            "geometry_scope": geometry_scope,
        }
    )
    for target in oracle["targets"]:
        visible = target["native_visible_source_segments"]
        target.update(
            {
                "native_source_entity_templates": target.get(
                    "native_source_entity_templates", visible
                ),
                "expected_source_segments": target.get("expected_source_segments", visible),
                "clipped_away_source_segments": target.get("clipped_away_source_segments", 0),
                "excluded_curved_source_segments": target.get("excluded_curved_source_segments", 0),
                "excluded_degenerate_source_segments": target.get("excluded_degenerate_source_segments", 0),
                "excluded_unsupported_entity_templates": target.get(
                    "excluded_unsupported_entity_templates", 0
                ),
            }
        )
    binding_path = tmp_path / "display_membership_binding.json"
    binding = {
        "schema": "ariadne.e2.native_display_binding.v1",
        "source_path": str(source_path.resolve()),
        "source_sha256": drawing_id,
        "staged_path": str(staged_path.resolve()),
        "staged_sha256_before": digest(staged_path),
        "geometry_scope": geometry_scope,
        "native_job_out_path": str(raw_path.resolve()),
        "native_job_out_sha256": digest(raw_path),
        "attended_final_receipt": {
            "path": str(attended_path.resolve()),
            "sha256": digest(attended_path),
        },
        "native_build_manifest": {
            "path": str(manifest_path.resolve()),
            "sha256": digest(manifest_path),
        },
    }
    binding_path.write_text(json.dumps(binding), encoding="utf-8")
    oracle["evidence"] = [
        {"path": str(path.resolve()), "sha256": digest(path)}
        for path in (raw_path, attended_path, binding_path, manifest_path)
    ]
    oracle_path.write_text(json.dumps(oracle), encoding="utf-8")
    oracle_sha256 = digest(oracle_path)
    receipt = {
        "schema": "ariadne.cadctl.display_membership.v1",
        "status": "PASS",
        "operation": "e2.inspect.xclip_membership",
        "geometry_scope": geometry_scope,
        "claim_scope": "instrument_observation_only",
        "downstream_experiment_guard_required": True,
        "authoritative_completion_marker": str(receipt_path.resolve()),
        "target_population_oracle": str(oracle_path.resolve()),
        "target_population_oracle_sha256": oracle_sha256,
        "final_evidence_sha256": {
            "source": drawing_id,
            "staged_dwg": digest(staged_path),
            "native_job_out": digest(raw_path),
            "attended_final_receipt": digest(attended_path),
            "binding": digest(binding_path),
            "observation_oracle": oracle_sha256,
            "native_build_manifest": digest(manifest_path),
        },
    }
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return oracle


def _target_oracle(tmp_path: Path, *, w1_visible=1, w2_visible=1):
    def visible_ids(prefix: str, count: int) -> list[str]:
        return [prefix, *(f"{prefix}-{index}" for index in range(2, count + 1))] if count else []

    oracle = {
        "schema": "ariadne.e2.target_population_oracle.v1",
        "oracle": "autocad.native_display_membership.v1",
        "targets": [
            {
                "target_id": "wall-w1",
                "layer": "X-PLAN$0$W1",
                "native_visible_source_segments": w1_visible,
                "native_visible_segment_ids": visible_ids("P-W1", w1_visible),
            },
            {
                "target_id": "wall-w2",
                "layer": "X-PLAN$0$W2",
                "native_visible_source_segments": w2_visible,
                "native_visible_segment_ids": visible_ids("P-W2", w2_visible),
            },
        ],
    }
    return _bind_authoritative_target_oracle(tmp_path, oracle)


def _authoritative_target_oracle(tmp_path: Path):
    return _target_oracle(tmp_path)


def _target_worldir_probe():
    probe = _worldir_probe()
    probe["drawing_id"] = _TARGET_SOURCE_SHA256
    probe["segments"] = [
        {
            "placed_uid": "P-W1",
            "lineage_id": "P-W1",
            "source_layer": "X-PLAN$0$W1",
            "p0_world": [0, 0],
            "p1_world": [1, 0],
        },
        {
            "placed_uid": "P-W2",
            "lineage_id": "P-W2",
            "source_layer": "X-PLAN$0$W2",
            "p0_world": [0, 1],
            "p1_world": [1, 1],
        },
    ]
    probe["conservation_ledger"].update(
        {
            "expected_segment_instances": 2,
            "visible_source_segment_instances": 2,
            "emitted_segment_instances": 2,
            "entity_entries": [
                {
                    "source_layer": "X-PLAN$0$W1",
                    "visible_source_segments": 1,
                    "emitted_segments": 1,
                    "clipped_away_segments": 0,
                    "status": "PRESERVED",
                },
                {
                    "source_layer": "X-PLAN$0$W2",
                    "visible_source_segments": 1,
                    "emitted_segments": 1,
                    "clipped_away_segments": 0,
                    "status": "PRESERVED",
                },
            ],
        }
    )
    return probe


def _model_input(*placed_uids: str):
    return {
        "ir": "seg.v1",
        "drawing_id": _TARGET_SOURCE_SHA256,
        "segments": [
            {
                "handle": uid,
                "layer": "X-PLAN$0$W1" if uid.startswith("P-W1") else "X-PLAN$0$W2",
            }
            for uid in placed_uids
        ],
    }


def test_supported_nested_world_segments_selects_adapter_oracle_pipeline():
    result = guard.qualify(
        required_observables=["nested_insert_world_segments", "world_lineage"],
        candidate="auto",
    )
    assert result["status"] == guard.NEEDS_PROBE
    assert result["selected_pipeline"] == "native_graph_worldir_segments"


def test_target_population_observables_select_worldir_pipeline_and_need_probe():
    result = guard.qualify(
        required_observables=[
            "nested_insert_world_segments",
            "world_lineage",
            "native_display_membership",
            "model_input_membership",
        ],
        candidate="auto",
    )

    assert result["status"] == guard.NEEDS_PROBE
    assert result["selected_pipeline"] == "native_graph_worldir_segments"


def test_target_population_gate_opens_only_when_oracle_world_and_model_input_agree(tmp_path: Path):
    decision = guard.qualify(
        required_observables=[
            "nested_insert_world_segments",
            "world_lineage",
            "native_display_membership",
            "model_input_membership",
        ],
        candidate="auto",
    )

    result = guard.verify_probe(
        decision,
        _target_worldir_probe(),
        target_population_oracle=_target_oracle(tmp_path),
        model_input_output=_model_input("P-W1", "P-W2"),
    )

    assert result["status"] == guard.READY
    assert result["reason_code"] == "INSTRUMENT_QUALIFIED"
    assert result["target_population"]["wall-w1"]["model_input_segments"] == 1
    assert result["target_population"]["wall-w2"]["model_input_segments"] == 1
    assert set(result["evidence_payload_sha256"]) == {
        "world_ir",
        "target_population_oracle",
        "model_input_ir",
    }
    assert all(len(value) == 64 for value in result["evidence_payload_sha256"].values())


def test_target_population_gate_accepts_only_the_pr66_authoritative_receipt_contract(
    tmp_path: Path,
):
    decision = guard.qualify(
        required_observables=[
            "nested_insert_world_segments",
            "world_lineage",
            "native_display_membership",
            "model_input_membership",
        ],
        candidate="auto",
    )

    result = guard.verify_probe(
        decision,
        _target_worldir_probe(),
        target_population_oracle=_authoritative_target_oracle(tmp_path),
        model_input_output=_model_input("P-W1", "P-W2"),
    )

    assert result["status"] == guard.READY
    assert result["reason_code"] == "INSTRUMENT_QUALIFIED"


def test_guarded_runner_does_not_start_without_the_pr66_authoritative_receipt(
    tmp_path: Path,
):
    oracle = _target_oracle(tmp_path)
    Path(oracle["producer_receipt_path"]).unlink()
    calls = []

    def should_not_run(command, check=False):
        calls.append(command)
        raise AssertionError("model command must not run without the final display receipt")

    result = guarded_runner.run_guarded(
        required_observables=[
            "nested_insert_world_segments",
            "world_lineage",
            "native_display_membership",
            "model_input_membership",
        ],
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_output=_target_worldir_probe(),
        target_population_oracle=oracle,
        model_input_output=_model_input("P-W1", "P-W2"),
        runner=should_not_run,
    )

    assert result["guard"]["status"] == guard.NEEDS_PROBE
    assert result["guard"]["reason_code"] == "TARGET_POPULATION_ORACLE_INVALID"
    assert result["executed"] is False
    assert calls == []


def test_target_population_gate_needs_build_when_native_display_oracle_is_absent():
    decision = guard.qualify(
        required_observables=[
            "nested_insert_world_segments",
            "world_lineage",
            "native_display_membership",
            "model_input_membership",
        ],
        candidate="auto",
    )

    result = guard.verify_probe(
        decision,
        _target_worldir_probe(),
        model_input_output=_model_input("P-W1", "P-W2"),
    )

    assert result["status"] == guard.NEEDS_BUILD
    assert result["reason_code"] == "NATIVE_DISPLAY_ORACLE_REQUIRED"
    assert result["missing_builds"] == ["autocad.native_display_membership.v1"]


def test_target_population_oracle_fixture_matches_published_schema(tmp_path: Path):
    repo = Path(__file__).resolve().parents[2]
    schema = json.loads(
        (repo / "schemas" / "e2_target_population_oracle.v1.schema.json").read_text(
            encoding="utf-8"
        )
    )

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(_target_oracle(tmp_path))


def test_target_population_gate_rejects_legacy_pass_status_even_with_receipt(tmp_path: Path):
    oracle = _target_oracle(tmp_path)
    oracle["status"] = "PASS"
    decision = guard.qualify(
        required_observables=["native_display_membership"], candidate="auto"
    )

    result = guard.verify_probe(
        decision,
        _target_worldir_probe(),
        target_population_oracle=oracle,
        model_input_output=_model_input("P-W1", "P-W2"),
    )

    assert result["status"] == guard.NEEDS_PROBE
    assert result["reason_code"] == "TARGET_POPULATION_ORACLE_INVALID"


def test_target_population_gate_rejects_final_evidence_hash_drift(tmp_path: Path):
    oracle = _target_oracle(tmp_path)
    receipt_path = Path(oracle["producer_receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["final_evidence_sha256"]["binding"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    decision = guard.qualify(
        required_observables=["native_display_membership"], candidate="auto"
    )

    result = guard.verify_probe(
        decision,
        _target_worldir_probe(),
        target_population_oracle=oracle,
        model_input_output=_model_input("P-W1", "P-W2"),
    )

    assert result["status"] == guard.NEEDS_PROBE
    assert result["reason_code"] == "TARGET_POPULATION_ORACLE_INVALID"


def test_target_population_gate_blocks_when_visible_w1_is_missing_from_model_input(tmp_path: Path):
    calls = []

    def fake_runner(command, check=False):
        calls.append(command)
        raise AssertionError("model command must not run after target population loss")

    result = guarded_runner.run_guarded(
        required_observables=[
            "nested_insert_world_segments",
            "world_lineage",
            "native_display_membership",
            "model_input_membership",
        ],
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_output=_target_worldir_probe(),
        target_population_oracle=_target_oracle(tmp_path),
        model_input_output=_model_input("P-W2"),
        runner=fake_runner,
    )

    assert result["guard"]["status"] == guard.BLOCKED
    assert result["guard"]["reason_code"] == "TARGET_POPULATION_LOST"
    assert result["guard"]["target_population"]["wall-w1"]["missing_model_input_segments"] == 1
    assert result["executed"] is False
    assert calls == []


def test_target_population_gate_blocks_when_native_visible_w1_was_all_clipped(tmp_path: Path):
    probe = _target_worldir_probe()
    probe["segments"] = [probe["segments"][1]]
    probe["conservation_ledger"].update(
        {
            "visible_source_segment_instances": 1,
            "clipped_away_segment_instances": 1,
            "emitted_segment_instances": 1,
            "entity_entries": [
                {
                    "source_layer": "X-PLAN$0$W1",
                    "visible_source_segments": 0,
                    "emitted_segments": 0,
                    "clipped_away_segments": 1,
                    "status": "CLIPPED",
                },
                probe["conservation_ledger"]["entity_entries"][1],
            ],
        }
    )
    decision = guard.qualify(
        required_observables=[
            "nested_insert_world_segments",
            "native_display_membership",
            "model_input_membership",
        ],
        candidate="auto",
    )

    result = guard.verify_probe(
        decision,
        probe,
        target_population_oracle=_target_oracle(tmp_path),
        model_input_output=_model_input("P-W2"),
    )

    assert result["status"] == guard.BLOCKED
    assert result["reason_code"] == "TARGET_POPULATION_LOST"
    assert result["target_population"]["wall-w1"] == {
        "layer": "X-PLAN$0$W1",
        "native_visible_source_segments": 1,
        "world_visible_source_segments": 0,
        "world_emitted_segments": 0,
        "model_input_segments": 0,
        "native_missing_from_worldir_segments": 1,
        "worldir_missing_from_native_segments": 0,
        "missing_model_input_segments": 1,
        "extra_model_input_segments": 0,
    }


def test_target_population_gate_blocks_native_world_visibility_disagreement(tmp_path: Path):
    decision = guard.qualify(
        required_observables=[
            "nested_insert_world_segments",
            "native_display_membership",
            "model_input_membership",
        ],
        candidate="auto",
    )

    result = guard.verify_probe(
        decision,
        _target_worldir_probe(),
        target_population_oracle=_target_oracle(tmp_path, w1_visible=2),
        model_input_output=_model_input("P-W1", "P-W1-2", "P-W2"),
    )

    assert result["status"] == guard.BLOCKED
    assert result["reason_code"] == "XCLIP_ORACLE_DISAGREEMENT"


def test_target_population_gate_rejects_same_count_with_different_object_ids(tmp_path: Path):
    oracle = _target_oracle(tmp_path)
    oracle["targets"][0]["native_visible_segment_ids"] = ["P-W1-OTHER"]
    _bind_authoritative_target_oracle(tmp_path, oracle)
    decision = guard.qualify(
        required_observables=["native_display_membership", "model_input_membership"],
        candidate="auto",
    )

    result = guard.verify_probe(
        decision,
        _target_worldir_probe(),
        target_population_oracle=oracle,
        model_input_output=_model_input("P-W1", "P-W2"),
    )

    assert result["status"] == guard.BLOCKED
    assert result["reason_code"] == "TARGET_POPULATION_LOST"
    assert result["target_population"]["wall-w1"]["missing_model_input_segments"] == 1
    assert result["target_population"]["wall-w1"]["extra_model_input_segments"] == 1


def test_target_population_gate_rejects_unbound_native_oracle(tmp_path: Path):
    oracle = _target_oracle(tmp_path)
    Path(oracle["evidence"][0]["path"]).write_text("tampered", encoding="utf-8")
    decision = guard.qualify(
        required_observables=["native_display_membership"],
        candidate="auto",
    )

    result = guard.verify_probe(
        decision,
        _target_worldir_probe(),
        target_population_oracle=oracle,
        model_input_output=_model_input("P-W1", "P-W2"),
    )

    assert result["status"] == guard.NEEDS_PROBE
    assert result["reason_code"] == "TARGET_POPULATION_ORACLE_INVALID"


def test_worldir_probe_with_both_ledgers_opens_supported_segment_experiment():
    decision = guard.qualify(
        required_observables=[
            "nested_insert_world_segments",
            "world_lineage",
            "silent_drop_detection",
        ],
        candidate="auto",
    )
    result = guard.verify_probe(decision, _worldir_probe())
    assert result["status"] == guard.READY
    assert result["coverage_level"] == "world_segments_verified"


def test_source_document_identity_requires_an_exact_expected_sha256():
    requirements = [
        "nested_insert_world_segments",
        "world_lineage",
        "silent_drop_detection",
        "source_document_identity",
    ]
    decision = guard.qualify(required_observables=requirements, candidate="auto")
    expected = "a" * 64
    matching = _worldir_probe()
    matching["drawing_id"] = expected

    assert guard.verify_probe(
        decision, matching, expected_source_sha256=expected
    )["status"] == guard.READY
    missing = guard.verify_probe(decision, matching)
    malformed = guard.verify_probe(
        decision, matching, expected_source_sha256="not-a-sha256"
    )
    wrong = _worldir_probe()
    wrong["drawing_id"] = "b" * 64
    mismatched = guard.verify_probe(
        decision, wrong, expected_source_sha256=expected
    )

    assert missing["status"] != guard.READY
    assert missing["reason_code"] == "SOURCE_DOCUMENT_BINDING_REQUIRED"
    assert malformed["status"] != guard.READY
    assert malformed["reason_code"] == "SOURCE_DOCUMENT_BINDING_REQUIRED"
    assert mismatched["status"] != guard.READY
    assert mismatched["reason_code"] == "SOURCE_DOCUMENT_IDENTITY_MISMATCH"


def test_guarded_runner_hash_binds_real_source_and_exact_probe_file(tmp_path: Path):
    requirements = [
        "nested_insert_world_segments",
        "world_lineage",
        "silent_drop_detection",
        "source_document_identity",
    ]
    staged = tmp_path / "l0_gold.dwg"
    staged.write_bytes(_minimal_dwg_bytes(b"matching staged DWG"))
    staged_sha256 = hashlib.sha256(staged.read_bytes()).hexdigest()
    matching_path = tmp_path / "matching-probe.json"
    matching_probe = _worldir_probe()
    matching_probe["drawing_id"] = staged_sha256
    matching_path.write_text(json.dumps(matching_probe), encoding="utf-8")
    receipt_path = tmp_path / "matching-receipt.json"
    calls = []

    class Completed:
        returncode = 0

    def fake_runner(command, check=False):
        calls.append(command)
        return Completed()

    matching = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=matching_path,
        source_drawing=staged,
        receipt_path=receipt_path,
        runner=fake_runner,
    )

    saved = json.loads(receipt_path.read_text(encoding="utf-8"))
    binding = saved["evidence_binding"]
    assert matching["guard"]["status"] == guard.READY
    assert matching["executed"] is True
    assert matching["receipt_phase"] == "TERMINAL"
    assert matching["terminal_state"] == "AUTHORIZED_SUCCESS"
    assert matching["command_succeeded"] is True
    assert matching["evidence_authorized"] is True
    assert matching["terminal_authorized"] is True
    assert binding["source_path"] == str(staged.resolve())
    assert binding["source_requested_path"] == str(staged.absolute())
    assert binding["source_canonical_target"] == str(staged.resolve())
    assert binding["source_file_identity"]["size"] == len(staged.read_bytes())
    assert binding["source_format_validation"]["valid"] is True
    assert binding["source_format_validation"]["observed_signature"] == "AC1027"
    assert binding["source_sha256"] == staged_sha256
    assert binding["probe_path"] == str(matching_path.resolve())
    assert binding["probe_requested_path"] == str(matching_path.absolute())
    assert binding["probe_canonical_target"] == str(matching_path.resolve())
    assert binding["probe_file_identity"]["size"] == len(matching_path.read_bytes())
    assert binding["probe_sha256"] == hashlib.sha256(matching_path.read_bytes()).hexdigest()
    assert binding["verified_probe_drawing_id"] == staged_sha256
    assert binding["pre_spawn_validation"]["status"] == "VALID"
    assert binding["post_execution_validation"]["status"] == "VALID"
    assert binding["terminal_evidence_valid"] is True
    assert binding["terminal_evidence_validity"] == "VALID"
    assert saved["terminal_authorized"] is True
    assert saved["execution_outcome"] == "COMMAND_SUCCEEDED"
    assert saved == matching
    assert calls == [OBSERVATION_COMMAND]

    wrong_identity_path = tmp_path / "wrong-identity-probe.json"
    wrong_identity_probe = _worldir_probe()
    wrong_identity_probe["drawing_id"] = "b" * 64
    wrong_identity_path.write_text(json.dumps(wrong_identity_probe), encoding="utf-8")
    wrong_identity = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=wrong_identity_path,
        source_drawing=staged,
        runner=fake_runner,
    )

    wrong_source = tmp_path / "other.dwg"
    wrong_source.write_bytes(_minimal_dwg_bytes(b"different staged DWG"))
    wrong_source_result = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=matching_path,
        source_drawing=wrong_source,
        runner=fake_runner,
    )

    stale_in_memory_probe = dict(matching_probe)
    mutated_path = tmp_path / "mutated-probe.json"
    mutated_probe = _worldir_probe()
    mutated_probe["drawing_id"] = "c" * 64
    mutated_path.write_text(json.dumps(mutated_probe), encoding="utf-8")
    mutated = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_output=stale_in_memory_probe,
        probe_path=mutated_path,
        source_drawing=staged,
        runner=fake_runner,
    )

    omitted_source = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=matching_path,
        runner=fake_runner,
    )

    assert wrong_identity["guard"]["status"] != guard.READY
    assert wrong_identity["guard"]["reason_code"] == "SOURCE_DOCUMENT_IDENTITY_MISMATCH"
    assert wrong_source_result["guard"]["status"] != guard.READY
    assert wrong_source_result["guard"]["reason_code"] == "SOURCE_DOCUMENT_IDENTITY_MISMATCH"
    assert mutated["guard"]["status"] != guard.READY
    assert mutated["guard"]["reason_code"] == "SOURCE_DOCUMENT_IDENTITY_MISMATCH"
    assert mutated["evidence_binding"]["probe_sha256"] == hashlib.sha256(mutated_path.read_bytes()).hexdigest()
    assert omitted_source["guard"]["status"] != guard.READY
    assert omitted_source["guard"]["reason_code"] == "SOURCE_DOCUMENT_BINDING_REQUIRED"
    assert calls == [OBSERVATION_COMMAND]


def _matching_source_bound_inputs(tmp_path: Path, *, receipt_name: str):
    requirements = [
        "nested_insert_world_segments",
        "world_lineage",
        "silent_drop_detection",
        "source_document_identity",
    ]
    source = tmp_path / "l0_gold.dwg"
    source.write_bytes(_minimal_dwg_bytes(b"matching staged DWG"))
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    probe_path = tmp_path / "scoped_worldir_probe.json"
    probe = _worldir_probe()
    probe["drawing_id"] = source_sha256
    probe_path.write_text(json.dumps(probe), encoding="utf-8")
    return requirements, source, probe_path, tmp_path / receipt_name


def test_guarded_runner_invalidates_terminal_receipt_when_runner_mutates_probe(tmp_path: Path):
    requirements, source, probe_path, receipt_path = _matching_source_bound_inputs(
        tmp_path, receipt_name="probe-mutated-receipt.json"
    )
    mutated_probe = _worldir_probe()
    mutated_probe["drawing_id"] = "b" * 64
    def mutating_runner(command, check=False):
        probe_path.write_text(json.dumps(mutated_probe), encoding="utf-8")
        return _Completed(0)

    result = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=probe_path,
        source_drawing=source,
        receipt_path=receipt_path,
        runner=mutating_runner,
    )

    final = _assert_authoritative_receipt(result, receipt_path)
    binding = final["evidence_binding"]
    assert final["guard"]["status"] == guard.BLOCKED
    assert final["guard"]["reason_code"] == "EVIDENCE_BINDING_INVALIDATED_AFTER_EXECUTION"
    assert final["executed"] is True
    assert final["command_exit_code"] == 0
    assert final["command_succeeded"] is True
    assert final["evidence_authorized"] is False
    assert final["execution_outcome"] == "COMMAND_COMPLETED_EVIDENCE_INVALIDATED"
    assert final["terminal_authorized"] is False
    assert binding["post_execution_validation"]["valid"] is False
    assert binding["post_execution_validation"]["probe_matches_preflight"] is False
    assert binding["post_execution_validation"]["probe_sha256"] == hashlib.sha256(
        probe_path.read_bytes()
    ).hexdigest()
    assert binding["terminal_evidence_valid"] is False
    assert binding["terminal_evidence_validity"] == "INVALIDATED_AFTER_EXECUTION"


def test_guarded_runner_invalidates_terminal_receipt_when_runner_mutates_source(tmp_path: Path):
    requirements, source, probe_path, receipt_path = _matching_source_bound_inputs(
        tmp_path, receipt_name="source-mutated-receipt.json"
    )

    class Completed:
        returncode = 0

    def mutating_runner(command, check=False):
        source.write_bytes(b"source bytes changed during command")
        return Completed()

    result = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=probe_path,
        source_drawing=source,
        receipt_path=receipt_path,
        runner=mutating_runner,
    )

    final = _assert_authoritative_receipt(result, receipt_path)
    binding = final["evidence_binding"]
    assert final["guard"]["status"] == guard.BLOCKED
    assert final["guard"]["reason_code"] == "EVIDENCE_BINDING_INVALIDATED_AFTER_EXECUTION"
    assert final["executed"] is True
    assert final["command_succeeded"] is True
    assert final["evidence_authorized"] is False
    assert final["terminal_authorized"] is False
    assert binding["post_execution_validation"]["valid"] is False
    assert binding["post_execution_validation"]["source_matches_preflight"] is False
    assert binding["post_execution_validation"]["source_sha256"] == hashlib.sha256(
        source.read_bytes()
    ).hexdigest()
    assert binding["terminal_evidence_validity"] == "INVALIDATED_AFTER_EXECUTION"


def test_guarded_runner_blocks_pre_spawn_probe_mutation_and_does_not_execute(tmp_path: Path, monkeypatch):
    requirements, source, probe_path, receipt_path = _matching_source_bound_inputs(
        tmp_path, receipt_name="pre-spawn-mutated-receipt.json"
    )
    original_verify_probe = guarded_runner.experiment_guard.verify_probe
    mutated_probe = _worldir_probe()
    mutated_probe["drawing_id"] = "c" * 64

    def mutate_after_preflight(*args, **kwargs):
        decision = original_verify_probe(*args, **kwargs)
        probe_path.write_text(json.dumps(mutated_probe), encoding="utf-8")
        return decision

    monkeypatch.setattr(guarded_runner.experiment_guard, "verify_probe", mutate_after_preflight)

    def should_not_run(command, check=False):
        raise AssertionError("pre-spawn binding change must prevent execution")

    result = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=probe_path,
        source_drawing=source,
        receipt_path=receipt_path,
        runner=should_not_run,
    )

    final = _assert_authoritative_receipt(result, receipt_path)
    binding = final["evidence_binding"]
    assert final["guard"]["status"] == guard.BLOCKED
    assert final["guard"]["reason_code"] == "EVIDENCE_BINDING_INVALIDATED_BEFORE_SPAWN"
    assert final["executed"] is False
    assert final["command_exit_code"] is None
    assert final["command_succeeded"] is False
    assert final["evidence_authorized"] is False
    assert final["execution_outcome"] == "NOT_EXECUTED_EVIDENCE_INVALIDATED_BEFORE_SPAWN"
    assert final["terminal_authorized"] is False
    assert binding["pre_spawn_validation"]["valid"] is False
    assert binding["post_execution_validation"] == {"status": "NOT_RUN", "valid": False}
    assert binding["terminal_evidence_validity"] == "INVALIDATED_BEFORE_SPAWN"


def test_guarded_runner_terminalizes_runner_exception_receipt(tmp_path: Path):
    requirements, source, probe_path, receipt_path = _matching_source_bound_inputs(
        tmp_path, receipt_name="runner-exception-receipt.json"
    )

    def failing_runner(command, check=False):
        raise OSError("simulated runner failure")

    result = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=probe_path,
        source_drawing=source,
        receipt_path=receipt_path,
        runner=failing_runner,
    )

    final = _assert_authoritative_receipt(result, receipt_path)
    binding = final["evidence_binding"]
    assert final["guard"]["status"] == guard.BLOCKED
    assert final["guard"]["reason_code"] == "RUNNER_INVOCATION_FAILED"
    assert final["executed"] is False
    assert final["command_exit_code"] is None
    assert final["execution_outcome"] == "RUNNER_EXCEPTION"
    assert final["runner_error_type"] == "OSError"
    assert final["command_succeeded"] is False
    assert final["terminal_authorized"] is False
    assert binding["post_execution_validation"]["valid"] is True
    assert binding["terminal_evidence_valid"] is False
    assert binding["terminal_evidence_validity"] == "RUNNER_EXCEPTION"


def test_worldir_probe_with_adapter_imbalance_stays_closed():
    decision = guard.qualify(
        required_observables=["nested_insert_world_segments"], candidate="auto")
    result = guard.verify_probe(decision, _worldir_probe(adapter_balance=False))
    assert result["status"] == guard.NEEDS_BUILD
    assert result["reason_code"] == "ADAPTER_LEDGER_FAILED"


def test_worldir_probe_accepts_explicit_xclip_balance():
    decision = guard.qualify(
        required_observables=["nested_insert_world_segments", "xclip_preservation"],
        candidate="auto",
    )
    probe = _worldir_probe()
    probe["conservation_ledger"].update({
        "expected_segment_instances": 9,
        "visible_source_segment_instances": 1,
        "clipped_away_segment_instances": 8,
        "emitted_segment_instances": 1,
        "clip_generated_fragment_instances": 0,
    })

    result = guard.verify_probe(decision, probe)

    assert result["status"] == guard.READY


def test_worldir_probe_rejects_missing_clip_accounting():
    decision = guard.qualify(
        required_observables=["nested_insert_world_segments"], candidate="auto"
    )
    probe = _worldir_probe()
    del probe["conservation_ledger"]["visible_source_segment_instances"]

    result = guard.verify_probe(decision, probe)

    assert result["status"] == guard.NEEDS_PROBE
    assert result["reason_code"] == "WORLDIR_CONSERVATION_FAILED"


def test_native_full_probe_opens_rich_experiment():
    requirements = [
        "modelspace_geometry",
        "block_definitions",
        "nested_insert_graph",
        "hatch_boundary_loops",
        "layer_provenance",
    ]
    decision = guard.qualify(required_observables=requirements, candidate="auto")
    result = guard.verify_probe(decision, _rich_ir())
    assert result["status"] == guard.READY
    assert result["selected_pipeline"] == "native_graph"
    assert result["coverage_level"] == "native_full"


def test_claimed_hatch_observation_fails_when_probe_omits_hatch_loops():
    decision = guard.qualify(
        required_observables=["hatch_boundary_loops"], candidate="auto")
    result = guard.verify_probe(decision, _rich_ir(include_hatch=False))
    assert result["status"] == guard.NEEDS_BUILD
    assert "hatch_boundary_loops" in result["unverified_observables"]


def test_empty_probe_cannot_be_called_ready_by_default():
    decision = guard.qualify(
        required_observables=["modelspace_geometry"], candidate="auto")
    result = guard.verify_probe(decision, _rich_ir(entity_count=0))
    assert result["status"] == guard.NEEDS_PROBE
    assert result["reason_code"] == "VACUOUS_PROBE"


def test_impossibility_claim_requires_an_independent_oracle():
    decision = guard.qualify(
        required_observables=["modelspace_geometry"],
        candidate="auto",
        conclusion="impossibility",
    )
    result = guard.verify_probe(decision, _rich_ir())
    assert result["status"] == guard.NEEDS_PROBE
    assert result["reason_code"] == "INDEPENDENT_ORACLE_REQUIRED"


def test_absence_claim_accepts_only_hash_bound_independent_receipt(tmp_path: Path):
    evidence = tmp_path / "oracle.json"
    evidence.write_text('{"count": 3}', encoding="utf-8")
    receipt = {
        "status": "PASS",
        "evidence": [
            {
                "path": str(evidence),
                "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            }
        ],
    }
    decision = guard.qualify(
        required_observables=["modelspace_geometry"],
        candidate="auto",
        conclusion="absence",
    )

    accepted = guard.verify_probe(
        decision,
        _rich_ir(),
        independent_oracle_receipt=receipt,
    )
    evidence.write_text('{"count": 4}', encoding="utf-8")
    rejected = guard.verify_probe(
        decision,
        _rich_ir(),
        independent_oracle_receipt=receipt,
    )

    assert accepted["status"] == guard.READY
    assert rejected["status"] == guard.NEEDS_PROBE
    assert rejected["reason_code"] == "INDEPENDENT_ORACLE_REQUIRED"


def test_proxy_geometry_is_not_promoted_from_partial_identity_coverage():
    result = guard.qualify(
        required_observables=["proxy_object_geometry"], candidate="auto")
    assert result["status"] == guard.NEEDS_TOOL
    assert "object_enabler_or_vendor_sdk" in result["missing_tools"]


def test_guarded_runner_does_not_execute_without_probe():
    calls = []

    def fake_runner(command, check=False):
        calls.append(command)
        raise AssertionError("experiment command must not run")

    result = guarded_runner.run_guarded(
        required_observables=["modelspace_geometry"],
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        runner=fake_runner,
    )
    assert result["guard"]["status"] == guard.NEEDS_PROBE
    assert result["executed"] is False
    assert calls == []


def test_guarded_runner_requires_an_explicit_execution_purpose():
    calls = []

    def should_not_run(command, check=False):
        calls.append(command)
        raise AssertionError("an omitted execution purpose must fail before spawn")

    with pytest.raises(TypeError):
        guarded_runner.run_guarded(
            required_observables=["modelspace_geometry"],
            command=OBSERVATION_COMMAND,
            probe_output=_rich_ir(),
            runner=should_not_run,
        )

    assert calls == []


def test_downstream_execution_without_a_receipt_is_blocked_before_spawn():
    calls = []

    def should_not_run(command, check=False):
        calls.append(command)
        raise AssertionError("downstream execution must not run without a receipt")

    result = guarded_runner.run_guarded(
        execution_purpose="downstream_learning_or_scoring",
        experiment_id="missing-receipt",
        required_observables=["modelspace_geometry"],
        command=["python", "model.py"],
        probe_output=_rich_ir(),
        runner=should_not_run,
    )

    assert result["guard"]["status"] == guard.BLOCKED
    assert result["guard"]["reason_code"] == "QUALIFICATION_RECEIPT_REQUIRED"
    assert result["executed"] is False
    assert result["terminal_authorized"] is False
    assert calls == []


def test_observation_mode_rejects_an_arbitrary_subprocess_before_spawn():
    calls = []

    def should_not_run(command, check=False):
        calls.append(command)
        raise AssertionError("observation mode must use the closed repository allowlist")

    result = guarded_runner.run_guarded(
        execution_purpose="observation_only",
        required_observables=["modelspace_geometry"],
        command=["python", "model.py"],
        probe_output=_rich_ir(),
        runner=should_not_run,
    )

    assert result["guard"]["status"] == guard.BLOCKED
    assert result["guard"]["reason_code"] == "OBSERVATION_COMMAND_NOT_ALLOWED"
    assert result["executed"] is False
    assert calls == []


def test_guarded_runner_executes_only_after_ready_probe():
    calls = []

    class Completed:
        returncode = 7

    def fake_runner(command, check=False):
        calls.append(command)
        return Completed()

    result = guarded_runner.run_guarded(
        required_observables=["modelspace_geometry", "block_definitions"],
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_output=_rich_ir(),
        runner=fake_runner,
    )
    assert result["guard"]["status"] == guard.READY
    assert result["executed"] is True
    assert result["command_exit_code"] == 7
    assert result["execution_outcome"] == "COMMAND_FAILED"
    assert result["command_succeeded"] is False
    assert result["terminal_authorized"] is False
    assert calls == [OBSERVATION_COMMAND]


def test_guarded_runner_writes_preflight_and_final_receipt(tmp_path: Path):
    receipt_path = tmp_path / "guard.json"

    class Completed:
        returncode = 0

    def fake_runner(command, check=False):
        preflight = _assert_nonterminal_preflight(receipt_path)
        assert preflight["executed"] is False
        return Completed()

    result = guarded_runner.run_guarded(
        required_observables=["modelspace_geometry", "block_definitions"],
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_output=_rich_ir(),
        receipt_path=receipt_path,
        runner=fake_runner,
    )

    final = _assert_authoritative_receipt(result, receipt_path)
    assert result["executed"] is True
    assert final["executed"] is True
    assert final["command_exit_code"] == 0
    assert final["command_succeeded"] is True
    assert final["evidence_authorized"] is None
    assert final["terminal_authorized"] is True
    assert final["evidence_binding"]["pre_spawn_validation"]["status"] == "NOT_REQUIRED"
    assert final["evidence_binding"]["post_execution_validation"]["status"] == "NOT_REQUIRED"
    assert final["evidence_binding"]["terminal_evidence_valid"] is None
    assert final["evidence_binding"]["terminal_evidence_validity"] == "NOT_REQUIRED"
    assert final["execution_outcome"] == "COMMAND_SUCCEEDED"


def test_guarded_runner_never_executes_known_build_gap():
    calls = []

    def fake_runner(command, check=False):
        calls.append(command)
        raise AssertionError("experiment command must not run")

    result = guarded_runner.run_guarded(
        required_observables=["nested_insert_world_geometry"],
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_output=_rich_ir(),
        runner=fake_runner,
    )
    assert result["guard"]["status"] == guard.NEEDS_BUILD
    assert result["executed"] is False
    assert calls == []


def _make_directory_alias(alias: Path, target: Path) -> bool:
    """Create a retargetable directory alias on Windows without requiring CAD."""

    try:
        os.symlink(target, alias, target_is_directory=True)
        return True
    except (NotImplementedError, OSError):
        environment = os.environ.copy()
        environment["CODEX_E2_ALIAS_PATH"] = str(alias)
        environment["CODEX_E2_ALIAS_TARGET"] = str(target)
        completed = subprocess.run(
            [
                "pwsh",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                (
                    "New-Item -ItemType Junction -Path $env:CODEX_E2_ALIAS_PATH "
                    "-Target $env:CODEX_E2_ALIAS_TARGET -ErrorAction Stop | Out-Null"
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        return completed.returncode == 0 and alias.exists()


def _remove_directory_alias(alias: Path) -> None:
    if not alias.exists() and not alias.is_symlink():
        return
    if alias.is_symlink():
        alias.unlink()
    else:
        os.rmdir(alias)


@pytest.mark.parametrize("bound_kind", ["source", "probe"])
def test_guarded_runner_invalidates_byte_identical_directory_alias_retarget(
    tmp_path: Path, bound_kind: str
):
    requirements = [
        "nested_insert_world_segments",
        "world_lineage",
        "silent_drop_detection",
        "source_document_identity",
    ]
    target_a = tmp_path / "target-a"
    target_b = tmp_path / "target-b"
    target_a.mkdir()
    target_b.mkdir()
    alias = tmp_path / "retargetable-alias"
    source_bytes = _minimal_dwg_bytes(b"byte-identical source")
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    probe = _worldir_probe()
    probe["drawing_id"] = source_sha256
    probe_bytes = json.dumps(probe).encode("utf-8")

    if bound_kind == "source":
        (target_a / "source.dwg").write_bytes(source_bytes)
        (target_b / "source.dwg").write_bytes(source_bytes)
        source = alias / "source.dwg"
        probe_path = tmp_path / "probe.json"
        probe_path.write_bytes(probe_bytes)
        expected_a = target_a / "source.dwg"
    else:
        source = tmp_path / "source.dwg"
        source.write_bytes(source_bytes)
        (target_a / "probe.json").write_bytes(probe_bytes)
        (target_b / "probe.json").write_bytes(probe_bytes)
        probe_path = alias / "probe.json"
        expected_a = target_a / "probe.json"

    if not _make_directory_alias(alias, target_a):
        pytest.skip("Windows denied both directory symlink and junction creation")
    receipt_path = tmp_path / f"{bound_kind}-retarget-receipt.json"

    def retargeting_runner(command, check=False):
        _remove_directory_alias(alias)
        assert _make_directory_alias(alias, target_b)
        return _Completed(0)

    try:
        result = guarded_runner.run_guarded(
            required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
            probe_path=probe_path,
            source_drawing=source,
            receipt_path=receipt_path,
            runner=retargeting_runner,
        )
    finally:
        _remove_directory_alias(alias)

    final = _assert_authoritative_receipt(result, receipt_path)
    binding = final["evidence_binding"]
    prefix = "SOURCE_DRAWING" if bound_kind == "source" else "PROBE_FILE"
    assert final["guard"]["status"] == guard.BLOCKED
    assert final["guard"]["reason_code"] == "EVIDENCE_BINDING_INVALIDATED_AFTER_EXECUTION"
    assert final["executed"] is True
    assert final["command_succeeded"] is True
    assert final["evidence_authorized"] is False
    assert final["terminal_authorized"] is False
    assert binding[f"{bound_kind}_requested_path"] == str(
        (source if bound_kind == "source" else probe_path).absolute()
    )
    assert binding[f"{bound_kind}_canonical_target"] == str(expected_a.resolve())
    validation = binding["post_execution_validation"]
    assert validation[f"{bound_kind}_canonical_target_matches_preflight"] is False
    assert f"{prefix}_CANONICAL_TARGET_CHANGED" in validation["reasons"]
    assert f"{prefix}_FILE_IDENTITY_CHANGED" in validation["reasons"]


@pytest.mark.parametrize("bound_kind", ["source", "probe"])
def test_guarded_runner_invalidates_byte_identical_replacement_when_observable(
    tmp_path: Path, bound_kind: str
):
    requirements, source, probe_path, receipt_path = _matching_source_bound_inputs(
        tmp_path, receipt_name=f"{bound_kind}-replacement-receipt.json"
    )
    target = source if bound_kind == "source" else probe_path
    replacement = tmp_path / f"replacement-{target.name}"
    replacement.write_bytes(target.read_bytes())

    def replacing_runner(command, check=False):
        os.replace(replacement, target)
        return _Completed(0)

    result = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=probe_path,
        source_drawing=source,
        receipt_path=receipt_path,
        runner=replacing_runner,
    )

    final = _assert_authoritative_receipt(result, receipt_path)
    validation = final["evidence_binding"]["post_execution_validation"]
    if validation[f"{bound_kind}_file_identity_matches_preflight"] is True:
        pytest.skip("the platform did not expose a changed identity/stat fingerprint")
    prefix = "SOURCE_DRAWING" if bound_kind == "source" else "PROBE_FILE"
    assert final["guard"]["status"] == guard.BLOCKED
    assert final["guard"]["reason_code"] == "EVIDENCE_BINDING_INVALIDATED_AFTER_EXECUTION"
    assert final["command_succeeded"] is True
    assert final["terminal_authorized"] is False
    assert any(
        reason in validation["reasons"]
        for reason in (f"{prefix}_FILE_IDENTITY_CHANGED", f"{prefix}_FILE_STAT_CHANGED")
    )


@pytest.mark.parametrize("bound_kind", ["source", "probe"])
def test_guarded_runner_invalidates_source_or_probe_deletion(tmp_path: Path, bound_kind: str):
    requirements, source, probe_path, receipt_path = _matching_source_bound_inputs(
        tmp_path, receipt_name=f"{bound_kind}-deleted-receipt.json"
    )
    target = source if bound_kind == "source" else probe_path

    def deleting_runner(command, check=False):
        target.unlink()
        return _Completed(0)

    result = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=probe_path,
        source_drawing=source,
        receipt_path=receipt_path,
        runner=deleting_runner,
    )

    final = _assert_authoritative_receipt(result, receipt_path)
    prefix = "SOURCE_DRAWING" if bound_kind == "source" else "PROBE_FILE"
    assert final["guard"]["status"] == guard.BLOCKED
    assert final["guard"]["reason_code"] == "EVIDENCE_BINDING_INVALIDATED_AFTER_EXECUTION"
    assert final["command_succeeded"] is True
    assert final["evidence_authorized"] is False
    assert final["terminal_authorized"] is False
    assert any(
        reason.startswith(f"{prefix}_UNAVAILABLE")
        for reason in final["evidence_binding"]["post_execution_validation"]["reasons"]
    )


def test_guarded_runner_blocks_malformed_probe_with_a_terminal_receipt(tmp_path: Path):
    requirements, source, probe_path, receipt_path = _matching_source_bound_inputs(
        tmp_path, receipt_name="malformed-probe-receipt.json"
    )
    probe_path.write_text("{not valid JSON", encoding="utf-8")
    calls = []

    def should_not_run(command, check=False):
        calls.append(command)
        raise AssertionError("malformed probe must never run")

    result = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=probe_path,
        source_drawing=source,
        receipt_path=receipt_path,
        runner=should_not_run,
    )

    final = _assert_authoritative_receipt(result, receipt_path)
    assert final["guard"]["status"] == guard.NEEDS_PROBE
    assert final["executed"] is False
    assert final["command_succeeded"] is False
    assert final["terminal_authorized"] is False
    assert calls == []
    assert any(
        error.startswith("PROBE_FILE_UNAVAILABLE_OR_INVALID")
        for error in final["evidence_binding"]["binding_errors"]
    )


def test_guarded_runner_rejects_non_dwg_source_even_when_probe_hash_matches(tmp_path: Path):
    requirements, source, probe_path, receipt_path = _matching_source_bound_inputs(
        tmp_path, receipt_name="malformed-source-receipt.json"
    )
    source.write_bytes(b"not a DWG")
    probe = _worldir_probe()
    probe["drawing_id"] = hashlib.sha256(source.read_bytes()).hexdigest()
    probe_path.write_text(json.dumps(probe), encoding="utf-8")
    calls = []

    def should_not_run(command, check=False):
        calls.append(command)
        raise AssertionError("non-DWG source must never run")

    result = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=probe_path,
        source_drawing=source,
        receipt_path=receipt_path,
        runner=should_not_run,
    )

    final = _assert_authoritative_receipt(result, receipt_path)
    format_validation = final["evidence_binding"]["source_format_validation"]
    assert final["guard"]["status"] == guard.BLOCKED
    assert final["guard"]["reason_code"] == "SOURCE_DRAWING_FORMAT_INVALID"
    assert final["executed"] is False
    assert final["command_succeeded"] is False
    assert final["terminal_authorized"] is False
    assert format_validation["valid"] is False
    assert format_validation["observed_signature_hex"] == b"not a ".hex()
    assert calls == []


@pytest.mark.parametrize(
    ("completed", "runner_error_type"),
    [
        (object(), "MISSING_RETURNCODE"),
        (_Completed(None), "INVALID_RETURNCODE"),
        (_Completed("0"), "INVALID_RETURNCODE"),
        (_Completed(1.5), "INVALID_RETURNCODE"),
    ],
)
def test_guarded_runner_terminalizes_malformed_runner_results(
    tmp_path: Path, completed: object, runner_error_type: str
):
    requirements, source, probe_path, receipt_path = _matching_source_bound_inputs(
        tmp_path, receipt_name=f"runner-{runner_error_type}.json"
    )

    def malformed_runner(command, check=False):
        return completed

    result = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=probe_path,
        source_drawing=source,
        receipt_path=receipt_path,
        runner=malformed_runner,
    )

    final = _assert_authoritative_receipt(result, receipt_path)
    assert final["guard"]["status"] == guard.BLOCKED
    assert final["guard"]["reason_code"] == "RUNNER_CONTRACT_INVALID"
    assert final["execution_outcome"] == "RUNNER_CONTRACT_INVALID"
    assert final["terminal_state"] == "RUNNER_CONTRACT_INVALID"
    assert final["runner_error_type"] == runner_error_type
    assert final["executed"] is True
    assert final["command_exit_code"] is None
    assert final["command_succeeded"] is False
    assert final["terminal_authorized"] is False


def test_guarded_runner_records_nonzero_command_as_nonterminal_failure(tmp_path: Path):
    requirements, source, probe_path, receipt_path = _matching_source_bound_inputs(
        tmp_path, receipt_name="nonzero-receipt.json"
    )

    result = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=probe_path,
        source_drawing=source,
        receipt_path=receipt_path,
        runner=lambda command, check=False: _Completed(7),
    )

    final = _assert_authoritative_receipt(result, receipt_path)
    assert final["guard"]["status"] == guard.READY
    assert final["executed"] is True
    assert final["command_exit_code"] == 7
    assert final["execution_outcome"] == "COMMAND_FAILED"
    assert final["terminal_state"] == "COMMAND_FAILED"
    assert final["evidence_authorized"] is True
    assert final["command_succeeded"] is False
    assert final["terminal_authorized"] is False
    assert final["terminal_success"] is False


def test_guarded_runner_cli_returns_nonzero_command_exit(tmp_path: Path):
    requirements, source, probe_path, receipt_path = _matching_source_bound_inputs(
        tmp_path, receipt_name="cli-nonzero-receipt.json"
    )
    argv = [
        "--execution-purpose",
        "observation_only",
        *(item for required in requirements for item in ("--require", required)),
        "--probe-ir",
        str(probe_path),
        "--source-drawing",
        str(source),
        "--receipt-output",
        str(receipt_path),
        "--",
        *OBSERVATION_COMMAND,
    ]

    assert guarded_runner.main(argv) == 21
    final = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert final["guard"]["status"] == guard.READY
    assert final["execution_outcome"] == "COMMAND_FAILED"
    assert final["command_exit_code"] == 21
    assert final["terminal_authorized"] is False


def test_guarded_runner_returns_blocked_when_final_receipt_write_fails(
    tmp_path: Path, monkeypatch
):
    requirements, source, probe_path, receipt_path = _matching_source_bound_inputs(
        tmp_path, receipt_name="final-write-failure.json"
    )
    original_write_receipt = guarded_runner._write_receipt
    calls = 0

    def fail_final_write(path, result):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated final receipt write failure")
        return original_write_receipt(path, result)

    monkeypatch.setattr(guarded_runner, "_write_receipt", fail_final_write)
    result = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=probe_path,
        source_drawing=source,
        receipt_path=receipt_path,
        runner=lambda command, check=False: _Completed(0),
    )

    preflight = _assert_nonterminal_preflight(receipt_path)
    assert calls == 2
    assert result["guard"]["status"] == guard.BLOCKED
    assert result["guard"]["reason_code"] == "RECEIPT_WRITE_FAILED"
    assert result["receipt_phase"] == "TERMINAL"
    assert result["terminal_state"] == "RECEIPT_WRITE_FAILED"
    assert result["execution_outcome"] == "RECEIPT_WRITE_FAILED"
    assert result["command_exit_code"] == 0
    assert result["command_succeeded"] is True
    assert result["terminal_authorized"] is False
    assert preflight["terminal_authorized"] is False


def test_guarded_runner_does_not_execute_when_initial_receipt_write_fails(
    tmp_path: Path, monkeypatch
):
    requirements, source, probe_path, receipt_path = _matching_source_bound_inputs(
        tmp_path, receipt_name="initial-write-failure.json"
    )
    runner_calls = []

    def fail_initial_write(path, result):
        raise OSError("simulated initial receipt write failure")

    def should_not_run(command, check=False):
        runner_calls.append(command)
        raise AssertionError("command must not run without a durable preflight receipt")

    monkeypatch.setattr(guarded_runner, "_write_receipt", fail_initial_write)
    result = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=probe_path,
        source_drawing=source,
        receipt_path=receipt_path,
        runner=should_not_run,
    )

    assert result["guard"]["status"] == guard.BLOCKED
    assert result["guard"]["reason_code"] == "RECEIPT_WRITE_FAILED"
    assert result["receipt_phase"] == "TERMINAL"
    assert result["terminal_state"] == "RECEIPT_WRITE_FAILED"
    assert result["executed"] is False
    assert result["command_succeeded"] is False
    assert result["terminal_authorized"] is False
    assert result["receipt_persisted"] is False
    assert runner_calls == []
    assert not receipt_path.exists()


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
def test_guarded_runner_propagates_base_exceptions_after_safe_preflight(
    tmp_path: Path, interrupt: type[BaseException]
):
    requirements, source, probe_path, receipt_path = _matching_source_bound_inputs(
        tmp_path, receipt_name=f"{interrupt.__name__}-preflight.json"
    )

    def interrupting_runner(command, check=False):
        _assert_nonterminal_preflight(receipt_path)
        raise interrupt()

    with pytest.raises(interrupt):
        guarded_runner.run_guarded(
            required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
            probe_path=probe_path,
            source_drawing=source,
            receipt_path=receipt_path,
            runner=interrupting_runner,
        )

    _assert_nonterminal_preflight(receipt_path)


@pytest.mark.parametrize("aliased_evidence", ["source", "probe"])
def test_guarded_runner_rejects_receipt_path_aliasing_evidence_without_overwrite(
    tmp_path: Path, aliased_evidence: str
):
    requirements, source, probe_path, _ = _matching_source_bound_inputs(
        tmp_path, receipt_name="unused.json"
    )
    receipt_path = source if aliased_evidence == "source" else probe_path
    source_before = source.read_bytes()
    probe_before = probe_path.read_bytes()
    calls = []

    def should_not_run(command, check=False):
        calls.append(command)
        raise AssertionError("receipt/evidence alias must fail before execution")

    result = guarded_runner.run_guarded(
        required_observables=requirements,
        execution_purpose="observation_only",
        command=OBSERVATION_COMMAND,
        probe_path=probe_path,
        source_drawing=source,
        receipt_path=receipt_path,
        runner=should_not_run,
    )

    assert result["guard"]["status"] == guard.BLOCKED
    assert result["guard"]["reason_code"] == "RECEIPT_PATH_ALIASES_EVIDENCE"
    assert result["executed"] is False
    assert result["terminal_authorized"] is False
    assert result["receipt_persisted"] is False
    assert source.read_bytes() == source_before
    assert probe_path.read_bytes() == probe_before
    assert calls == []


def test_atomic_receipt_write_cleans_temporary_file_when_replace_fails(
    tmp_path: Path, monkeypatch
):
    receipt_path = tmp_path / "atomic-receipt.json"

    def fail_replace(source, destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(guarded_runner.os, "replace", fail_replace)
    with pytest.raises(OSError):
        guarded_runner._write_receipt(receipt_path, {"safe": True})

    assert not receipt_path.exists()
    assert list(tmp_path.glob(f".{receipt_path.name}.*.tmp")) == []
