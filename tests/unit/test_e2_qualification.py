#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import copy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
E2 = REPO / "tools" / "e2"
if str(E2) not in sys.path:
    sys.path.insert(0, str(E2))

from tools.e2.qualification.engine import (  # noqa: E402
    _runtime_wall_guard_qualified,
    build_first_report,
    validate_downstream_qualification_receipt,
)
from tools.e2.qualification import cli as qualification_cli  # noqa: E402
import run_guarded_experiment as guarded_runner  # noqa: E402


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


QUALIFIED_OBSERVABLES = [
    "nested_insert_world_segments",
    "silent_drop_detection",
    "source_document_identity",
    "world_lineage",
]


def test_phase_one_import_does_not_require_optional_model_runtime() -> None:
    script = r"""
import builtins
import sys

real_import = builtins.__import__

def reject_optional_runtime(name, globals=None, locals=None, fromlist=(), level=0):
    if name.split(".", 1)[0] in {"joblib", "numpy", "torch"}:
        raise ModuleNotFoundError(f"blocked optional model dependency: {name}")
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = reject_optional_runtime
from tools.e2 import qualification

assert callable(qualification.qualify)
assert callable(qualification.build_first_report)
assert callable(qualification.build_model_assisted_report)
assert "tools.e2.qualification.phase2" not in sys.modules
assert "tools.e2.qualification._phase2_models" not in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def _record(run_root: Path, relative_path: str, role: str) -> dict[str, object]:
    path = run_root / relative_path
    raw = path.read_bytes()
    return {
        "role": role,
        "path": relative_path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _write_authorizing_bundle(
    tmp_path: Path,
    *,
    experiment_id: str = "qualified-current-run",
) -> tuple[Path, Path, dict[str, object]]:
    run_root = tmp_path / "qualified-run"
    evidence_root = run_root / "evidence"
    evidence_root.mkdir(parents=True)
    source = tmp_path / "current-source.dwg"
    source.write_bytes(b"AC1027qualified source fixture")
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()

    for role in ("native_ir", "adapter_ir", "world_ir"):
        _write_json(evidence_root / f"{role}.json", {"schema": f"fixture.{role}.v1"})

    candidates = {
        "schema": "e2.wall_candidates_rules.v1",
        "status": "LABELED_EVALUATION",
        "threshold": 0.5,
        "candidate_count": 1,
        "candidates": [{"placed_uid": "P1", "score": 0.8}],
        "wall_pair_records": [
            {
                "handles": ["P1", "P2"],
                "axis": [[0.0, 0.0], [10.0, 0.0]],
                "thickness": 0.2,
            }
        ],
    }
    models = {
        "schema": "e2.model_diagnostics.v1",
        "rules": {
            "status": "LABELED_EVALUATION",
            "candidate_count": 1,
            "accuracy_metrics": {
                "true_positive": 1,
                "false_positive": 0,
                "false_negative": 0,
                "f1": 1.0,
            },
        },
    }
    invariant_records = [
        {
            "intervention": name,
            "expected_invariant": True,
            "status": "PASS",
            "segments": 2,
            "positive_handles": 1,
            "positive_membership_changed_handles": [],
            "score_changed_handle_count": 0,
            "positive_handle_jaccard_vs_baseline": 1.0,
            "parallel_pair_handle_jaccard_vs_baseline": 1.0,
            "max_per_handle_score_delta": 0.0,
        }
        for name in sorted(
            {
                "rotate_37_degrees",
                "translate_large_offset",
                "scale_coordinates_x1000_consistent",
                "split_every_segment_at_midpoint",
            }
        )
    ]
    interventions = {
        "schema": "e2.intervention_results.v1",
        "baseline": {
            "segments": 2,
            "handles_scored": 2,
            "positive_handles_at_threshold_0_5": 1,
            "parallel_pair_handles": 2,
            "wall_pair_records": 1,
        },
        "interventions": invariant_records,
    }
    outputs = {
        "wall_candidates_rules.json": candidates,
        "model_diagnostics.json": models,
        "intervention_results.json": interventions,
    }
    for name, payload in outputs.items():
        _write_json(run_root / name, payload)

    expected_statuses = {row["intervention"]: "PASS" for row in invariant_records}
    gate = {
        "status": "PASS",
        "reason_codes": [],
        "qualification_status": "PASS",
        "candidate_count": 1,
        "wall_pair_record_count": 1,
        "rules_f1": 1.0,
        "expected_invariant_statuses": expected_statuses,
        "blocked_expected_invariants": [],
    }
    receipt = {
        "schema": "e2.qualification_receipt.v1",
        "status": "PASS",
        "experiment_id": experiment_id,
        "created_at": "2026-08-11T00:00:00Z",
        "source": {
            "path": str(source.resolve()),
            "sha256": source_sha256,
            "native_payload_sha256": source_sha256,
            "read_only": True,
        },
        "evidence": [
            _record(run_root, f"evidence/{role}.json", role)
            for role in ("native_ir", "adapter_ir", "world_ir")
        ],
        "gates": [{"gate": "source_identity", "status": "PASS", "evidence": "bound"}],
        "scope_verdicts": {"downstream_model_learning_or_scoring": "PASS"},
        "limitations": [],
        "authorization_scope": {
            "execution_purpose": "downstream_learning_or_scoring",
            "required_observables": sorted(QUALIFIED_OBSERVABLES),
        },
        "downstream_experiment_gate": gate,
        "outputs": [
            _record(run_root, name, name.removesuffix(".json"))
            for name in outputs
        ],
    }
    receipt_path = run_root / "qualification_receipt.json"
    _write_json(receipt_path, receipt)
    context: dict[str, object] = {
        "execution_purpose": "downstream_learning_or_scoring",
        "experiment_id": experiment_id,
        "required_observables": sorted(QUALIFIED_OBSERVABLES),
        "source_path": str(source.resolve()),
        "source_sha256": source_sha256,
        "command": ["python", "model.py"],
        "command_config": {"split": "heldout"},
    }
    return receipt_path, source, context


def _refresh_output_record(receipt_path: Path, role: str) -> None:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    record = next(row for row in receipt["outputs"] if row["role"] == role)
    raw = (receipt_path.parent / record["path"]).read_bytes()
    record["sha256"] = hashlib.sha256(raw).hexdigest()
    record["bytes"] = len(raw)
    _write_json(receipt_path, receipt)


def test_downstream_receipt_applies_schema_and_current_execution_context(tmp_path: Path):
    receipt_path, source, context = _write_authorizing_bundle(tmp_path)

    valid = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=context,
    )
    assert valid["status"] == "PASS"
    assert valid["authorization_snapshot_digest"]

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    schema_forgery = copy.deepcopy(receipt)
    for key in (
        "experiment_id",
        "source",
        "evidence",
        "gates",
        "scope_verdicts",
        "limitations",
    ):
        schema_forgery.pop(key)
    _write_json(receipt_path, schema_forgery)
    missing_required = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=context,
    )
    assert missing_required["status"] == "BLOCKED"
    assert "QUALIFICATION_RECEIPT_SCHEMA_INVALID" in missing_required["reason_codes"]

    _write_json(receipt_path, receipt)
    stale_context = dict(context)
    other_source = tmp_path / "other-source.dwg"
    other_source.write_bytes(b"AC1027other source fixture")
    stale_context["source_path"] = str(other_source.resolve())
    stale_context["source_sha256"] = hashlib.sha256(other_source.read_bytes()).hexdigest()
    stale = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=stale_context,
    )
    assert stale["status"] == "BLOCKED"
    assert "QUALIFICATION_SOURCE_BINDING_MISMATCH" in stale["reason_codes"]

    observable_context = dict(context)
    observable_context["required_observables"] = ["modelspace_geometry"]
    observables = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=observable_context,
    )
    assert observables["status"] == "BLOCKED"
    assert "QUALIFICATION_OBSERVABLE_SCOPE_MISMATCH" in observables["reason_codes"]

    assert source.is_file()


def test_guarded_downstream_run_binds_command_config_and_snapshot_to_terminal_receipt(
    tmp_path: Path,
):
    receipt_path, source, context = _write_authorizing_bundle(tmp_path)
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    probe = {
        "oracle": "worldir.oracle.v1",
        "status": "PASS",
        "drawing_id": source_sha256,
        "input_mode": "definition_graph",
        "segments": [
            {"lineage_id": "L1", "p0_world": [0, 0], "p1_world": [1, 0]}
        ],
        "adapter_ledger": {
            "scope": "LINE_POLYLINE_ARC_INSERT",
            "source_entity_templates": 1,
            "adapted_entity_templates": 1,
            "explicitly_excluded_entity_templates": 0,
            "excluded_by_dxf_name": {},
            "balance_ok": True,
        },
        "conservation_ledger": {
            "reachable_insert_placements": 1,
            "expected_segment_instances": 1,
            "visible_source_segment_instances": 1,
            "clipped_away_segment_instances": 0,
            "clip_generated_fragment_instances": 0,
            "emitted_segment_instances": 1,
            "conservation_delta": 0,
            "conservation_ok": True,
        },
        "failure_ledger": [],
    }
    probe_path = tmp_path / "probe.json"
    _write_json(probe_path, probe)
    terminal_receipt = tmp_path / "guarded-terminal.json"
    calls = []

    class Completed:
        returncode = 0

    def fake_runner(command, check=False):
        calls.append(command)
        return Completed()

    result = guarded_runner.run_guarded(
        execution_purpose="downstream_learning_or_scoring",
        experiment_id=str(context["experiment_id"]),
        required_observables=QUALIFIED_OBSERVABLES,
        command=list(context["command"]),
        command_config=dict(context["command_config"]),
        probe_path=probe_path,
        source_drawing=source,
        qualification_receipt_path=receipt_path,
        receipt_path=terminal_receipt,
        runner=fake_runner,
    )

    assert result["terminal_state"] == "AUTHORIZED_SUCCESS", json.dumps(
        result, indent=2, ensure_ascii=False
    )
    assert result["terminal_authorized"] is True
    assert calls == [context["command"]]
    snapshot = result["qualification_authorization_snapshot"]
    assert snapshot["digest"] == result["qualification_receipt_validation"][
        "authorization_snapshot_digest"
    ]
    assert snapshot["command"] == context["command"]
    assert snapshot["command_config"] == context["command_config"]
    persisted = json.loads(terminal_receipt.read_text(encoding="utf-8"))
    assert persisted["qualification_authorization_snapshot"] == snapshot


def test_downstream_gate_recomputes_detailed_candidates_f1_pairs_and_invariants(
    tmp_path: Path,
):
    receipt_path, _, context = _write_authorizing_bundle(tmp_path)
    run_root = receipt_path.parent

    candidates_path = run_root / "wall_candidates_rules.json"
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    candidates["candidates"] = []
    candidates["wall_pair_records"] = [{}]
    _write_json(candidates_path, candidates)
    _refresh_output_record(receipt_path, "wall_candidates_rules")

    models_path = run_root / "model_diagnostics.json"
    models = json.loads(models_path.read_text(encoding="utf-8"))
    models["rules"]["accuracy_metrics"] = {
        "true_positive": 0,
        "false_positive": 1,
        "false_negative": 1,
        "f1": 1.0,
    }
    _write_json(models_path, models)
    _refresh_output_record(receipt_path, "model_diagnostics")

    interventions_path = run_root / "intervention_results.json"
    interventions = json.loads(interventions_path.read_text(encoding="utf-8"))
    interventions["interventions"].append(
        copy.deepcopy(interventions["interventions"][0])
    )
    _write_json(interventions_path, interventions)
    _refresh_output_record(receipt_path, "intervention_results")

    result = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=context,
    )

    assert result["status"] == "BLOCKED"
    assert {
        "CANDIDATE_DETAIL_INVALID",
        "WALL_PAIR_DETAIL_INVALID",
        "RULES_F1_CONFUSION_MISMATCH",
        "EXPECTED_INVARIANCE_DETAIL_INVALID",
    } <= set(result["reason_codes"])


def test_downstream_receipt_rejects_unvalidated_foreign_extra_output(tmp_path: Path):
    receipt_path, _, context = _write_authorizing_bundle(tmp_path)
    foreign = tmp_path / "foreign-run" / "experiment_spec.json"
    foreign.parent.mkdir()
    _write_json(foreign, {"schema": "foreign.run.v1"})
    raw = foreign.read_bytes()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["outputs"].append(
        {
            "role": "experiment_spec",
            "path": str(foreign.resolve()),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
    )
    _write_json(receipt_path, receipt)

    result = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=context,
    )

    assert result["status"] == "BLOCKED"
    assert "QUALIFICATION_OUTPUT_INVALID" in result["reason_codes"]
    assert any("relative" in error for error in result["output_errors"])


def test_downstream_receipt_rejects_bool_summaries_and_nonfinite_json(tmp_path: Path):
    receipt_path, _, context = _write_authorizing_bundle(tmp_path)
    candidates_path = receipt_path.parent / "wall_candidates_rules.json"
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    candidates["candidate_count"] = True
    _write_json(candidates_path, candidates)
    _refresh_output_record(receipt_path, "wall_candidates_rules")

    bool_result = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=context,
    )
    assert bool_result["status"] == "BLOCKED"
    assert "CANDIDATE_DETAIL_INVALID" in bool_result["reason_codes"]

    receipt_path, _, context = _write_authorizing_bundle(
        tmp_path / "nan-case",
        experiment_id="nan-case",
    )
    models_path = receipt_path.parent / "model_diagnostics.json"
    models = json.loads(models_path.read_text(encoding="utf-8"))
    models["rules"]["accuracy_metrics"]["f1"] = float("nan")
    models_path.write_text(json.dumps(models), encoding="utf-8")
    _refresh_output_record(receipt_path, "model_diagnostics")

    nan_result = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=context,
    )
    assert nan_result["status"] == "BLOCKED"
    assert "QUALIFICATION_OUTPUT_INVALID" in nan_result["reason_codes"]
    assert any("non-finite" in error for error in nan_result["output_errors"])


def test_receipt_is_revalidated_immediately_before_spawn(tmp_path: Path, monkeypatch):
    receipt_path, source, context = _write_authorizing_bundle(tmp_path)
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    probe = {
        "oracle": "worldir.oracle.v1",
        "status": "PASS",
        "drawing_id": source_sha256,
        "input_mode": "definition_graph",
        "segments": [
            {"lineage_id": "L1", "p0_world": [0, 0], "p1_world": [1, 0]}
        ],
        "adapter_ledger": {
            "scope": "LINE_POLYLINE_ARC_INSERT",
            "source_entity_templates": 1,
            "adapted_entity_templates": 1,
            "explicitly_excluded_entity_templates": 0,
            "excluded_by_dxf_name": {},
            "balance_ok": True,
        },
        "conservation_ledger": {
            "reachable_insert_placements": 1,
            "expected_segment_instances": 1,
            "visible_source_segment_instances": 1,
            "clipped_away_segment_instances": 0,
            "clip_generated_fragment_instances": 0,
            "emitted_segment_instances": 1,
            "conservation_delta": 0,
            "conservation_ok": True,
        },
        "failure_ledger": [],
    }
    probe_path = tmp_path / "toctou-probe.json"
    _write_json(probe_path, probe)
    real_validator = guarded_runner.validate_downstream_qualification_receipt
    events = []

    def pass_then_block(*args, **kwargs):
        if not events:
            result = real_validator(*args, **kwargs)
            assert result["status"] == "PASS"
            events.append("validate_PASS")
            return result
        events.append("validate_BLOCKED")
        return {
            "status": "BLOCKED",
            "reason_codes": ["SIMULATED_RECEIPT_REPLACEMENT"],
            "authorization_snapshot_digest": None,
        }

    def should_not_spawn(command, check=False):
        events.append("SPAWN")
        raise AssertionError("the second receipt validation must happen before spawn")

    monkeypatch.setattr(
        guarded_runner,
        "validate_downstream_qualification_receipt",
        pass_then_block,
    )
    result = guarded_runner.run_guarded(
        execution_purpose="downstream_learning_or_scoring",
        experiment_id=str(context["experiment_id"]),
        required_observables=QUALIFIED_OBSERVABLES,
        command=list(context["command"]),
        command_config=dict(context["command_config"]),
        probe_path=probe_path,
        source_drawing=source,
        qualification_receipt_path=receipt_path,
        runner=should_not_spawn,
    )

    assert events == ["validate_PASS", "validate_BLOCKED"]
    assert result["guard"]["status"] == "BLOCKED"
    assert result["guard"]["reason_code"] == "QUALIFICATION_RECEIPT_INVALIDATED_BEFORE_SPAWN"
    assert result["executed"] is False


def test_locked_authorization_snapshot_prevents_output_replacement_during_runner(
    tmp_path: Path,
):
    receipt_path, source, context = _write_authorizing_bundle(tmp_path)
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    probe = {
        "oracle": "worldir.oracle.v1",
        "status": "PASS",
        "drawing_id": source_sha256,
        "input_mode": "definition_graph",
        "segments": [
            {"lineage_id": "L1", "p0_world": [0, 0], "p1_world": [1, 0]}
        ],
        "adapter_ledger": {
            "scope": "LINE_POLYLINE_ARC_INSERT",
            "source_entity_templates": 1,
            "adapted_entity_templates": 1,
            "explicitly_excluded_entity_templates": 0,
            "excluded_by_dxf_name": {},
            "balance_ok": True,
        },
        "conservation_ledger": {
            "reachable_insert_placements": 1,
            "expected_segment_instances": 1,
            "visible_source_segment_instances": 1,
            "clipped_away_segment_instances": 0,
            "clip_generated_fragment_instances": 0,
            "emitted_segment_instances": 1,
            "conservation_delta": 0,
            "conservation_ok": True,
        },
        "failure_ledger": [],
    }
    probe_path = tmp_path / "locked-probe.json"
    _write_json(probe_path, probe)
    target = receipt_path.parent / "wall_candidates_rules.json"
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(target.read_bytes())
    replacement_observation = []

    class Completed:
        returncode = 0

    def replacing_runner(command, check=False):
        try:
            os.replace(replacement, target)
        except PermissionError:
            replacement_observation.append("LOCKED")
        else:
            replacement_observation.append("REPLACED")
        return Completed()

    result = guarded_runner.run_guarded(
        execution_purpose="downstream_learning_or_scoring",
        experiment_id=str(context["experiment_id"]),
        required_observables=QUALIFIED_OBSERVABLES,
        command=list(context["command"]),
        command_config=dict(context["command_config"]),
        probe_path=probe_path,
        source_drawing=source,
        qualification_receipt_path=receipt_path,
        runner=replacing_runner,
    )

    assert replacement_observation == ["LOCKED"]
    assert result["terminal_state"] == "AUTHORIZED_SUCCESS"
    assert result["qualification_authorization_snapshot"]["lock_contract"] == (
        "LOCKED_OPEN_HANDLES_HELD_THROUGH_RUNNER"
    )


def test_downstream_receipt_rejects_parent_traversal_output(tmp_path: Path):
    receipt_path, _, context = _write_authorizing_bundle(tmp_path)
    foreign = tmp_path / "foreign.json"
    _write_json(foreign, {"schema": "foreign.v1"})
    raw = foreign.read_bytes()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["outputs"].append(
        {
            "role": "foreign",
            "path": "../foreign.json",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
    )
    _write_json(receipt_path, receipt)

    result = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=context,
    )

    assert result["status"] == "BLOCKED"
    assert "QUALIFICATION_OUTPUT_INVALID" in result["reason_codes"]
    assert any("relative" in error for error in result["output_errors"])


def test_downstream_receipt_rejects_symlinked_output(tmp_path: Path):
    receipt_path, _, context = _write_authorizing_bundle(tmp_path)
    target = receipt_path.parent / "wall_candidates_rules.json"
    real = receipt_path.parent / "wall_candidates_rules.real.json"
    target.replace(real)
    try:
        os.symlink(real, target)
    except OSError as error:
        real.replace(target)
        pytest.skip(f"file symlink creation unavailable: {error}")
    try:
        result = validate_downstream_qualification_receipt(
            receipt_path,
            authorization_context=context,
        )
    finally:
        target.unlink(missing_ok=True)
        real.replace(target)

    assert result["status"] == "BLOCKED"
    assert "QUALIFICATION_OUTPUT_INVALID" in result["reason_codes"]
    assert any("reparse" in error for error in result["output_errors"])


def test_downstream_receipt_rejects_junction_run_root(tmp_path: Path):
    receipt_path, _, context = _write_authorizing_bundle(tmp_path)
    alias = tmp_path / "aliased-run"
    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(alias), str(receipt_path.parent)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        pytest.skip(f"junction creation unavailable: {completed.stderr.strip()}")
    try:
        result = validate_downstream_qualification_receipt(
            alias / "qualification_receipt.json",
            authorization_context=context,
        )
    finally:
        os.rmdir(alias)

    assert result["status"] == "BLOCKED"
    assert result["reason_codes"] == ["QUALIFICATION_RECEIPT_UNREADABLE"]
    assert "reparse" in result["reason"]


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
    assert result["downstream_experiment_gate"]["status"] == "BLOCKED"
    assert result["downstream_experiment_gate"]["candidate_count"] == 0
    assert result["downstream_experiment_gate"]["wall_pair_record_count"] == 0
    assert result["downstream_experiment_gate"]["rules_f1"] is None
    assert "split_every_segment_at_midpoint" in result["downstream_experiment_gate"][
        "blocked_expected_invariants"
    ]
    assert (tmp_path / "run" / "REPORT.md").is_file()
    receipt = json.loads((tmp_path / "run" / "qualification_receipt.json").read_text(encoding="utf-8"))
    assert receipt["source"]["sha256"] == source_hash
    assert receipt["downstream_experiment_gate"] == result["downstream_experiment_gate"]
    assert any(row["gate"] == "world_transform_and_xclip_conservation" and row["status"] == "PASS" for row in receipt["gates"])

    for schema_name, instance in (
        ("e2_experiment_spec.v1.schema.json", spec),
        ("e2_qualification_receipt.v1.schema.json", receipt),
        ("world_geometry_ir.v1.schema.json", world),
    ):
        schema = json.loads((REPO / "schemas" / schema_name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(instance)

    cli_run = tmp_path / "cli-run"
    exit_code = qualification_cli.main(
        [
            "--experiment-id",
            "fixture-cli",
            "--source",
            str(source),
            "--source-sha256",
            source_hash,
            "--native-ir",
            str(native_path),
            "--adapter-ir",
            str(adapter_path),
            "--world-ir",
            str(world_path),
            "--run-dir",
            str(cli_run),
        ]
    )

    assert exit_code == 2
    cli_receipt = json.loads(
        (cli_run / "qualification_receipt.json").read_text(encoding="utf-8")
    )
    assert cli_receipt["status"] == "PARTIAL_PASS"
    assert cli_receipt["downstream_experiment_gate"]["status"] == "BLOCKED"

    forged_receipt = json.loads(json.dumps(cli_receipt))
    forged_receipt["status"] = "PASS"
    forged_receipt["downstream_experiment_gate"].update(
        {
            "status": "PASS",
            "reason_codes": [],
            "qualification_status": "PASS",
            "candidate_count": 1,
            "wall_pair_record_count": 1,
            "rules_f1": 1.0,
            "expected_invariant_statuses": {
                "rotate_37_degrees": "PASS",
                "translate_large_offset": "PASS",
                "scale_coordinates_x1000_consistent": "PASS",
                "split_every_segment_at_midpoint": "PASS",
            },
            "blocked_expected_invariants": [],
        }
    )
    forged_receipt_path = cli_run / "qualification_receipt.json"
    _write_json(forged_receipt_path, forged_receipt)

    forged_validation = validate_downstream_qualification_receipt(
        forged_receipt_path
    )
    assert forged_validation["status"] == "BLOCKED"
    assert "DOWNSTREAM_GATE_EVIDENCE_MISMATCH" in forged_validation["reason_codes"]

    calls = []

    def should_not_run(command, check=False):
        calls.append(command)
        raise AssertionError("downstream command must not run with a blocked receipt")

    guarded = guarded_runner.run_guarded(
        execution_purpose="downstream_learning_or_scoring",
        experiment_id="fixture-cli",
        required_observables=["modelspace_geometry"],
        command=["python", "model.py"],
        probe_output=native,
        qualification_receipt_path=cli_run / "qualification_receipt.json",
        runner=should_not_run,
    )

    assert guarded["guard"]["status"] == "BLOCKED"
    assert guarded["guard"]["reason_code"] == "QUALIFICATION_RECEIPT_REJECTED"
    assert guarded["terminal_state"] == "QUALIFICATION_RECEIPT_REJECTED"
    assert guarded["executed"] is False
    assert guarded["terminal_authorized"] is False
    assert calls == []


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
