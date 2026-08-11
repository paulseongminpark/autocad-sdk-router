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
    _build_instrument_snapshot,
    _runtime_wall_guard_qualified,
    build_first_report,
    validate_downstream_qualification_receipt,
)
from tools.e2.qualification import cli as qualification_cli  # noqa: E402
from tools.e2.qualification import engine as qualification_engine  # noqa: E402
import run_guarded_experiment as guarded_runner  # noqa: E402


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


QUALIFIED_OBSERVABLES = [
    "nested_insert_world_segments",
    "world_lineage",
    "silent_drop_detection",
    "xclip_preservation",
    "source_document_identity",
    "native_display_membership",
    "model_input_membership",
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


def test_public_phase_two_wrapper_blocks_before_optional_model_runtime(
    tmp_path: Path,
) -> None:
    script = r"""
import builtins
import json
import sys
from pathlib import Path

real_import = builtins.__import__

def reject_model_runtime(name, globals=None, locals=None, fromlist=(), level=0):
    if name.endswith("._phase2_models") or name.endswith("._phase2_review"):
        raise AssertionError(f"model runtime imported before sealed execution: {name}")
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = reject_model_runtime
from tools.e2 import qualification

result = qualification.build_model_assisted_report(
    {"schema": "e2.model_assisted_spec.v1", "experiment_id": "blocked-fixture"},
    Path(sys.argv[1]),
)
assert result["status"] == "BLOCKED", json.dumps(result)
assert result["reason_code"] == "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"
assert result["executed"] is False
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "phase2")],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("experiment_id", [None, "", "   "])
def test_phase_two_refuses_an_empty_experiment_identity(
    tmp_path: Path,
    experiment_id: object,
) -> None:
    from tools.e2.qualification.phase2 import build_model_assisted_report

    with pytest.raises(ValueError, match="experiment_id"):
        build_model_assisted_report(
            {"experiment_id": experiment_id},
            tmp_path / "phase2",
        )

    assert not (tmp_path / "phase2" / "phase2_receipt.json").exists()


def test_phase_two_cli_returns_blocked_receipt_without_model_execution(
    tmp_path: Path, capsys
) -> None:
    from tools.e2.qualification import phase2_cli

    first_run = tmp_path / "first"
    first_run.mkdir()
    _write_json(
        first_run / "experiment_spec.json",
        {
            "source": {
                "path": str(tmp_path / "source.dwg"),
                "sha256": "0" * 64,
                "read_only": True,
            }
        },
    )

    exit_code = phase2_cli.main(
        [
            "--first-run",
            str(first_run),
            "--run-dir",
            str(tmp_path / "phase2-cli"),
            "--experiment-id",
            "blocked-cli-fixture",
        ]
    )

    result = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"
    assert result["executed"] is False

    receipt = json.loads(Path(result["receipt"]).read_text(encoding="utf-8"))
    schema = json.loads(
        (REPO / "schemas" / "e2_phase2_receipt.v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    errors = sorted(
        Draft202012Validator(schema).iter_errors(receipt),
        key=lambda error: tuple(error.absolute_path),
    )
    assert errors == [], [error.message for error in errors]


def test_phase_two_cli_describes_only_the_fail_closed_boundary(capsys) -> None:
    from tools.e2.qualification import phase2_cli

    with pytest.raises(SystemExit) as exit_info:
        phase2_cli.main(["--help"])

    help_text = capsys.readouterr().out
    assert exit_info.value.code == 0
    assert "sealed executor" in help_text.lower()
    assert "--frozen-transfer-harness" not in help_text
    assert "--public-limit" not in help_text
    assert "--audit-count" not in help_text
    assert "--sealed-holdout-count" not in help_text


def test_phase_two_cli_does_not_claim_the_retired_model_spec_schema(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.e2.qualification import phase2_cli

    first_run = tmp_path / "first"
    first_run.mkdir()
    _write_json(
        first_run / "experiment_spec.json",
        {
            "source": {
                "path": str(tmp_path / "source.dwg"),
                "sha256": "0" * 64,
                "read_only": True,
            }
        },
    )
    captured: dict[str, object] = {}

    def refuse(spec: dict[str, object], run_dir: Path) -> dict[str, object]:
        captured.update(spec)
        return {
            "status": "BLOCKED",
            "reason_code": "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED",
            "executed": False,
        }

    monkeypatch.setattr(phase2_cli, "build_model_assisted_report", refuse)
    exit_code = phase2_cli.main(
        [
            "--first-run",
            str(first_run),
            "--run-dir",
            str(tmp_path / "phase2-cli"),
            "--experiment-id",
            "blocked-cli-fixture",
        ]
    )
    capsys.readouterr()

    assert exit_code == 2
    assert "schema" not in captured


def _record(run_root: Path, relative_path: str, role: str) -> dict[str, object]:
    path = run_root / relative_path
    raw = path.read_bytes()
    return {
        "role": role,
        "path": relative_path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _payload_sha256(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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

    native = {
        "schema": "ariadne.dwg_graph_ir.v1",
        "coverage_level": "native_full",
        "source": {"sha256": source_sha256},
        "entities": [],
        "block_definitions": [],
        "diagnostics": {"errors": [], "warnings": []},
    }
    adapter_ledger = {
        "source_entity_templates": 2,
        "adapted_entity_templates": 2,
        "explicitly_excluded_entity_templates": 0,
        "balance_ok": True,
    }
    adapter = {
        "ir": "worldir.input.v1",
        "status": "PASS",
        "drawing_id": source_sha256,
        "adapter_ledger": adapter_ledger,
        "definitions": {},
    }
    layers = {"P1": "W1", "P2": "W2"}
    world = {
        "oracle": "worldir.oracle.v1",
        "status": "PASS",
        "drawing_id": source_sha256,
        "segments": [
            {
                "placed_uid": segment_id,
                "lineage_id": segment_id,
                "source_layer": layer,
                "p0_world": [0.0, float(index)],
                "p1_world": [1.0, float(index)],
            }
            for index, (segment_id, layer) in enumerate(layers.items())
        ],
        "adapter_ledger": adapter_ledger,
        "conservation_ledger": {
            "conservation_ok": True,
            "reachable_insert_placements": 1,
            "expected_segment_instances": 2,
            "visible_source_segment_instances": 2,
            "clipped_away_segment_instances": 0,
            "clip_generated_fragment_instances": 0,
            "emitted_segment_instances": 2,
            "conservation_delta": 0,
            "entity_entries": [
                {
                    "source_layer": layer,
                    "visible_source_segments": 1,
                    "emitted_segments": 1,
                    "clipped_away_segments": 0,
                    "status": "PRESERVED",
                }
                for layer in layers.values()
            ],
        },
        "failure_ledger": [],
    }
    staged = evidence_root / "target_staged.dwg"
    staged.write_bytes(source.read_bytes())
    native_job = evidence_root / "target_native_job.json"
    attended = evidence_root / "target_attended_receipt.json"
    manifest = evidence_root / "target_native_manifest.json"
    _write_json(native_job, {"native": True})
    _write_json(attended, {"receipt": True})
    _write_json(manifest, {"manifest": True})
    binding_path = evidence_root / "target_binding.json"
    binding = {
        "schema": "ariadne.e2.native_display_binding.v1",
        "source_path": str(source.resolve()),
        "source_sha256": source_sha256,
        "staged_path": str(staged.resolve()),
        "staged_sha256_before": hashlib.sha256(staged.read_bytes()).hexdigest(),
        "geometry_scope": "linear_segments_v1",
        "native_job_out_path": str(native_job.resolve()),
        "native_job_out_sha256": hashlib.sha256(native_job.read_bytes()).hexdigest(),
        "attended_final_receipt": {
            "path": str(attended.resolve()),
            "sha256": hashlib.sha256(attended.read_bytes()).hexdigest(),
        },
        "native_build_manifest": {
            "path": str(manifest.resolve()),
            "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        },
    }
    _write_json(binding_path, binding)
    target_oracle_path = evidence_root / "target_population_oracle.json"
    target_receipt_path = evidence_root / "target_population_receipt.json"
    target_oracle = {
        "schema": "ariadne.e2.target_population_oracle.v1",
        "oracle": "autocad.native_display_membership.v1",
        "status": "OBSERVED",
        "claim_scope": "instrument_observation_only",
        "producer_receipt_required": True,
        "producer_receipt_path": str(target_receipt_path.resolve()),
        "downstream_experiment_guard_required": True,
        "geometry_scope": "linear_segments_v1",
        "drawing_id": source_sha256,
        "evidence": [
            {
                "path": str(path.resolve()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in (native_job, attended, binding_path, manifest)
        ],
        "targets": [
            {
                "target_id": f"wall-{layer.lower()}",
                "layer": layer,
                "native_source_entity_templates": 1,
                "expected_source_segments": 1,
                "native_visible_source_segments": 1,
                "clipped_away_source_segments": 0,
                "excluded_curved_source_segments": 0,
                "excluded_degenerate_source_segments": 0,
                "excluded_unsupported_entity_templates": 0,
                "native_visible_segment_ids": [segment_id],
            }
            for segment_id, layer in layers.items()
        ],
    }
    _write_json(target_oracle_path, target_oracle)
    target_oracle_sha256 = hashlib.sha256(target_oracle_path.read_bytes()).hexdigest()
    target_receipt = {
        "schema": "ariadne.cadctl.display_membership.v1",
        "status": "PASS",
        "operation": "e2.inspect.xclip_membership",
        "geometry_scope": "linear_segments_v1",
        "claim_scope": "instrument_observation_only",
        "downstream_experiment_guard_required": True,
        "authoritative_completion_marker": str(target_receipt_path.resolve()),
        "target_population_oracle": str(target_oracle_path.resolve()),
        "target_population_oracle_sha256": target_oracle_sha256,
        "final_evidence_sha256": {
            "source": source_sha256,
            "staged_dwg": hashlib.sha256(staged.read_bytes()).hexdigest(),
            "native_job_out": hashlib.sha256(native_job.read_bytes()).hexdigest(),
            "attended_final_receipt": hashlib.sha256(attended.read_bytes()).hexdigest(),
            "binding": hashlib.sha256(binding_path.read_bytes()).hexdigest(),
            "observation_oracle": target_oracle_sha256,
            "native_build_manifest": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        },
    }
    _write_json(target_receipt_path, target_receipt)
    model_input = {
        "ir": "seg.v1",
        "drawing_id": source_sha256,
        "segments": [
            {"handle": segment_id, "layer": layer}
            for segment_id, layer in layers.items()
        ],
    }
    evidence_payloads = {
        "native_ir": native,
        "adapter_ir": adapter,
        "world_ir": world,
        "target_population_oracle": target_oracle,
        "model_input_ir": model_input,
    }
    for role, payload in evidence_payloads.items():
        if role != "target_population_oracle":
            _write_json(evidence_root / f"{role}.json", payload)

    candidates = {
        "schema": "e2.wall_candidates_rules.v1",
        "experiment_id": experiment_id,
        "source_sha256": source_sha256,
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
        "experiment_id": experiment_id,
        "source_sha256": source_sha256,
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
        "experiment_id": experiment_id,
        "source_sha256": source_sha256,
        "baseline": {
            "segments": 2,
            "handles_scored": 2,
            "positive_handles_at_threshold_0_5": 1,
            "parallel_pair_handles": 2,
            "wall_pair_records": 1,
        },
        "interventions": invariant_records,
    }
    object_truth = {
        "schema": "ariadne.e2.l0.object_truth.v1",
        "experiment_id": experiment_id,
        "drawing_id": source_sha256,
        "candidate_scope": "xclip_visible_linear_segments_v1",
        "label_authority": "independent_complete_object_truth",
        "object_truth_completeness": "COMPLETE",
        "records": [
            {"placed_uid": "P1", "label": "wall"},
            {"placed_uid": "P2", "label": "non_wall"},
        ],
    }
    predictions = {
        "schema": "ariadne.e2.l0.baseline_predictions.v1",
        "experiment_id": experiment_id,
        "drawing_id": source_sha256,
        "model_sha256": "1" * 64,
        "checkpoint_sha256": "2" * 64,
        "threshold": 0.5,
        "rows": [
            {"placed_uid": "P1", "score": 0.8},
            {"placed_uid": "P2", "score": 0.2},
        ],
    }
    guard_decision = {
        "schema": "ariadne.e2.guard_decision.v1",
        "status": "READY",
        "reason_code": "INSTRUMENT_QUALIFIED",
        "experiment_id": experiment_id,
        "drawing_id": source_sha256,
        "required_observables": sorted(QUALIFIED_OBSERVABLES),
        "target_population": {
            f"wall-{layer.lower()}": {
                "native_visible_source_segments": 1,
                "world_visible_source_segments": 1,
                "model_input_segments": 1,
                "missing_model_input_segments": 0,
                "extra_model_input_segments": 0,
            }
            for layer in layers.values()
        },
        "evidence_payload_sha256": {
            "world_ir": _payload_sha256(world),
            "target_population_oracle": _payload_sha256(target_oracle),
            "model_input_ir": _payload_sha256(model_input),
        },
    }
    outputs = {
        "wall_candidates_rules.json": candidates,
        "model_diagnostics.json": models,
        "intervention_results.json": interventions,
        "object_truth.json": object_truth,
        "baseline_predictions.json": predictions,
        "guard_decision.json": guard_decision,
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
            for role in evidence_payloads
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
        "target_population_oracle": target_oracle,
        "model_input_output": model_input,
        "world_ir": world,
    }
    return receipt_path, source, context


def _refresh_output_record(receipt_path: Path, role: str) -> None:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    record = next(row for row in receipt["outputs"] if row["role"] == role)
    raw = (receipt_path.parent / record["path"]).read_bytes()
    record["sha256"] = hashlib.sha256(raw).hexdigest()
    record["bytes"] = len(raw)
    _write_json(receipt_path, receipt)


def _refresh_evidence_record(receipt_path: Path, role: str) -> None:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    record = next(row for row in receipt["evidence"] if row["role"] == role)
    raw = (receipt_path.parent / record["path"]).read_bytes()
    record["sha256"] = hashlib.sha256(raw).hexdigest()
    record["bytes"] = len(raw)
    _write_json(receipt_path, receipt)


def test_downstream_receipt_rejects_reduced_wall_observable_scope(tmp_path: Path):
    receipt_path, _, context = _write_authorizing_bundle(tmp_path)
    reduced = QUALIFIED_OBSERVABLES[:4]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["authorization_scope"]["required_observables"] = sorted(reduced)
    _write_json(receipt_path, receipt)
    context["required_observables"] = sorted(reduced)

    result = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=context,
    )

    assert result["status"] == "BLOCKED"
    assert "QUALIFICATION_OBSERVABLE_SCOPE_INCOMPLETE" in result["reason_codes"]


def test_downstream_receipt_rejects_unvalidated_evidence_payloads(tmp_path: Path):
    receipt_path, _, context = _write_authorizing_bundle(tmp_path)
    native_path = receipt_path.parent / "evidence" / "native_ir.json"
    _write_json(native_path, {"schema": "fixture.native_ir.v1"})
    _refresh_evidence_record(receipt_path, "native_ir")

    result = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=context,
    )

    assert result["status"] == "BLOCKED"
    assert "QUALIFICATION_EVIDENCE_INVALID" in result["reason_codes"]


def test_downstream_receipt_rejects_target_oracle_without_producer_authority(
    tmp_path: Path,
):
    receipt_path, _, context = _write_authorizing_bundle(tmp_path)
    oracle_path = receipt_path.parent / "evidence" / "target_population_oracle.json"
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    producer_receipt_path = Path(oracle["producer_receipt_path"])
    producer_receipt = json.loads(producer_receipt_path.read_text(encoding="utf-8"))
    producer_receipt["status"] = "PARTIAL_PASS"
    _write_json(producer_receipt_path, producer_receipt)

    result = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=context,
    )

    assert result["status"] == "BLOCKED"
    assert "QUALIFICATION_EVIDENCE_INVALID" in result["reason_codes"]
    assert any("producer authority" in error for error in result["evidence_errors"])


def test_downstream_receipt_rejects_population_replay(tmp_path: Path):
    receipt_path, _, context = _write_authorizing_bundle(tmp_path)
    model_path = receipt_path.parent / "evidence" / "model_input_ir.json"
    model_input = json.loads(model_path.read_text(encoding="utf-8"))
    model_input["drawing_id"] = "a" * 64
    _write_json(model_path, model_input)
    _refresh_evidence_record(receipt_path, "model_input_ir")
    guard_path = receipt_path.parent / "guard_decision.json"
    guard = json.loads(guard_path.read_text(encoding="utf-8"))
    guard["evidence_payload_sha256"]["model_input_ir"] = _payload_sha256(model_input)
    _write_json(guard_path, guard)
    _refresh_output_record(receipt_path, "guard_decision")

    result = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=context,
    )

    assert result["status"] == "BLOCKED"
    assert "QUALIFICATION_POPULATION_BINDING_MISMATCH" in result["reason_codes"]


def test_downstream_receipt_rejects_cross_run_output_replay(tmp_path: Path):
    receipt_path, _, context = _write_authorizing_bundle(tmp_path)
    for filename, role in (
        ("wall_candidates_rules.json", "wall_candidates_rules"),
        ("model_diagnostics.json", "model_diagnostics"),
        ("intervention_results.json", "intervention_results"),
    ):
        path = receipt_path.parent / filename
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["experiment_id"] = "other-run"
        _write_json(path, payload)
        _refresh_output_record(receipt_path, role)

    result = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=context,
    )

    assert result["status"] == "BLOCKED"
    assert "QUALIFICATION_OUTPUT_INVALID" in result["reason_codes"]


def test_downstream_receipt_recomputes_f1_from_raw_truth_predictions(tmp_path: Path):
    receipt_path, _, context = _write_authorizing_bundle(tmp_path)
    models_path = receipt_path.parent / "model_diagnostics.json"
    models = json.loads(models_path.read_text(encoding="utf-8"))
    models["rules"]["accuracy_metrics"] = {
        "true_positive": 1,
        "false_positive": 1,
        "false_negative": 1,
        "f1": 0.5,
    }
    _write_json(models_path, models)
    _refresh_output_record(receipt_path, "model_diagnostics")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["downstream_experiment_gate"]["rules_f1"] = 0.5
    _write_json(receipt_path, receipt)

    result = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=context,
    )

    assert result["status"] == "BLOCKED"
    assert "QUALIFICATION_EVALUATION_EVIDENCE_INVALID" in result["reason_codes"]
    assert any("raw truth and predictions" in error for error in result["output_errors"])


def test_downstream_receipt_rejects_truth_predictions_outside_qualified_population(
    tmp_path: Path,
):
    receipt_path, _, context = _write_authorizing_bundle(tmp_path)
    synthetic_ids = ["SYNTHETIC-WALL-NOT-IN-WORLD", "SYNTHETIC-NONWALL-NOT-IN-WORLD"]
    truth_path = receipt_path.parent / "object_truth.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    for record, segment_id in zip(truth["records"], synthetic_ids):
        record["placed_uid"] = segment_id
    _write_json(truth_path, truth)
    _refresh_output_record(receipt_path, "object_truth")
    predictions_path = receipt_path.parent / "baseline_predictions.json"
    predictions = json.loads(predictions_path.read_text(encoding="utf-8"))
    for row, segment_id in zip(predictions["rows"], synthetic_ids):
        row["placed_uid"] = segment_id
    _write_json(predictions_path, predictions)
    _refresh_output_record(receipt_path, "baseline_predictions")

    result = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=context,
    )

    assert result["status"] == "BLOCKED"
    assert "QUALIFICATION_POPULATION_BINDING_MISMATCH" in result["reason_codes"]


def test_downstream_receipt_rejects_explicitly_incomplete_object_truth(tmp_path: Path):
    receipt_path, _, context = _write_authorizing_bundle(tmp_path)
    truth_path = receipt_path.parent / "object_truth.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    truth["object_truth_completeness"] = "UNKNOWN"
    _write_json(truth_path, truth)
    _refresh_output_record(receipt_path, "object_truth")

    result = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=context,
    )

    assert result["status"] == "BLOCKED"
    assert "QUALIFICATION_EVALUATION_EVIDENCE_INVALID" in result["reason_codes"]


def test_downstream_receipt_applies_schema_and_current_execution_context(tmp_path: Path):
    receipt_path, source, context = _write_authorizing_bundle(tmp_path)

    valid = validate_downstream_qualification_receipt(
        receipt_path,
        authorization_context=context,
    )
    assert valid["status"] == "BLOCKED"
    assert valid["integrity_status"] == "PASS"
    assert valid["execution_authorized"] is False
    assert valid["reason_codes"] == ["SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"]
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


def test_guarded_downstream_run_requires_sealed_executor_before_spawn(
    tmp_path: Path,
):
    receipt_path, source, context = _write_authorizing_bundle(tmp_path)
    probe = context["world_ir"]
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
        target_population_oracle=context["target_population_oracle"],
        model_input_output=context["model_input_output"],
        qualification_receipt_path=receipt_path,
        receipt_path=terminal_receipt,
        runner=fake_runner,
    )

    assert result["terminal_state"] == "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED", json.dumps(
        result, indent=2, ensure_ascii=False
    )
    assert result["guard"]["reason_code"] == "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"
    assert result["terminal_authorized"] is False
    assert result["executed"] is False
    assert calls == []
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


def test_unsealed_downstream_block_precedes_receipt_revalidation_and_spawn(
    tmp_path: Path, monkeypatch
):
    receipt_path, source, context = _write_authorizing_bundle(tmp_path)
    probe = context["world_ir"]
    probe_path = tmp_path / "toctou-probe.json"
    _write_json(probe_path, probe)
    real_validator = guarded_runner.validate_downstream_qualification_receipt
    events = []

    def pass_then_block(*args, **kwargs):
        if not events:
            result = real_validator(*args, **kwargs)
            assert result["status"] == "BLOCKED"
            assert result["integrity_status"] == "PASS"
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
        target_population_oracle=context["target_population_oracle"],
        model_input_output=context["model_input_output"],
        qualification_receipt_path=receipt_path,
        runner=should_not_spawn,
    )

    assert events == ["validate_PASS"]
    assert result["guard"]["status"] == "BLOCKED"
    assert result["guard"]["reason_code"] == "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"
    assert result["executed"] is False


def test_unsealed_downstream_runner_cannot_attempt_output_replacement(
    tmp_path: Path,
):
    receipt_path, source, context = _write_authorizing_bundle(tmp_path)
    probe = context["world_ir"]
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
        target_population_oracle=context["target_population_oracle"],
        model_input_output=context["model_input_output"],
        qualification_receipt_path=receipt_path,
        runner=replacing_runner,
    )

    assert replacement_observation == []
    assert result["terminal_state"] == "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"
    assert result["executed"] is False


def test_unsealed_downstream_runner_cannot_attempt_source_or_probe_replacement(
    tmp_path: Path,
):
    receipt_path, source, context = _write_authorizing_bundle(tmp_path)
    probe_path = tmp_path / "locked-source-probe.json"
    _write_json(probe_path, context["world_ir"])
    source_replacement = tmp_path / "source-replacement.dwg"
    source_replacement.write_bytes(source.read_bytes())
    probe_replacement = tmp_path / "probe-replacement.json"
    probe_replacement.write_bytes(probe_path.read_bytes())
    observations = []

    class Completed:
        returncode = 0

    def replacing_runner(command, check=False):
        for replacement, target, name in (
            (source_replacement, source, "SOURCE"),
            (probe_replacement, probe_path, "PROBE"),
        ):
            try:
                os.replace(replacement, target)
            except PermissionError:
                observations.append(f"{name}_LOCKED")
            else:
                observations.append(f"{name}_REPLACED")
        return Completed()

    result = guarded_runner.run_guarded(
        execution_purpose="downstream_learning_or_scoring",
        experiment_id=str(context["experiment_id"]),
        required_observables=QUALIFIED_OBSERVABLES,
        command=list(context["command"]),
        command_config=dict(context["command_config"]),
        probe_path=probe_path,
        source_drawing=source,
        target_population_oracle=context["target_population_oracle"],
        model_input_output=context["model_input_output"],
        qualification_receipt_path=receipt_path,
        runner=replacing_runner,
    )

    assert observations == []
    assert result["terminal_state"] == "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"
    assert result["executed"] is False


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
    assert result["integrity_status"] == "BLOCKED"
    assert result["execution_authorized"] is False
    assert result["reason_codes"] == ["QUALIFICATION_RECEIPT_UNREADABLE"]
    assert "reparse" in result["reason"]


def test_downstream_receipt_missing_file_is_explicitly_unauthorized(
    tmp_path: Path,
) -> None:
    result = validate_downstream_qualification_receipt(
        tmp_path / "qualification_receipt.json"
    )

    assert result["status"] == "BLOCKED"
    assert result["integrity_status"] == "BLOCKED"
    assert result["execution_authorized"] is False
    assert result["reason_codes"] == ["QUALIFICATION_RECEIPT_UNREADABLE"]


def test_internal_instrument_snapshot_is_evidence_bound_and_schema_valid(tmp_path: Path):
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

    result = _build_instrument_snapshot(spec, tmp_path / "run")

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

    forged_receipt = json.loads(json.dumps(receipt))
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
    forged_receipt_path = tmp_path / "run" / "qualification_receipt.json"
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
        experiment_id="fixture",
        required_observables=["modelspace_geometry"],
        command=["python", "model.py"],
        probe_output=native,
        qualification_receipt_path=forged_receipt_path,
        runner=should_not_run,
    )

    assert guarded["guard"]["status"] == "BLOCKED"
    assert guarded["guard"]["reason_code"] == "QUALIFICATION_RECEIPT_REJECTED"
    assert guarded["terminal_state"] == "QUALIFICATION_RECEIPT_REJECTED"
    assert guarded["executed"] is False
    assert guarded["terminal_authorized"] is False
    assert calls == []


def test_public_first_report_and_cli_stop_before_rule_scoring(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scorer_calls: list[bool] = []

    def forbidden_scorer():
        scorer_calls.append(True)
        raise AssertionError("unsealed rule scorer reached")

    monkeypatch.setattr(qualification_engine, "_load_evidence_grid", forbidden_scorer)
    run_dir = tmp_path / "direct-run"
    result = build_first_report({"experiment_id": "blocked-first-report"}, run_dir)

    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"
    assert result["executed"] is False
    assert scorer_calls == []
    assert not run_dir.exists()

    exit_code = qualification_cli.main(
        [
            "--experiment-id",
            "blocked-first-report-cli",
            "--source",
            str(tmp_path / "missing-source.dwg"),
            "--source-sha256",
            "0" * 64,
            "--native-ir",
            str(tmp_path / "missing-native.json"),
            "--adapter-ir",
            str(tmp_path / "missing-adapter.json"),
            "--world-ir",
            str(tmp_path / "missing-world.json"),
            "--run-dir",
            str(tmp_path / "cli-run"),
        ]
    )
    cli_result = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert cli_result["status"] == "BLOCKED"
    assert cli_result["reason_code"] == "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"
    assert cli_result["executed"] is False
    assert scorer_calls == []
    assert not (tmp_path / "cli-run").exists()


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
    assert _runtime_wall_guard_qualified(
        {
            **target_qualified,
            "required_observables": [
                *target_qualified["required_observables"],
                "database_counts",
            ],
        }
    ) is False
