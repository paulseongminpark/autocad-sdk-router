from __future__ import annotations

import hashlib
import inspect
import json
import re
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
E2 = REPO / "tools" / "e2"
if str(E2) not in sys.path:
    sys.path.insert(0, str(E2))

import run_l0_segment_baselines as runner  # noqa: E402
from tools.e2.qualification import _phase2_models  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    ids = ["a" * 64, "b" * 64, "c" * 64, "d" * 64]
    model = {
        "ir": "seg.v1",
        "drawing_id": "f" * 64,
        "units": "mm",
        "scale_mm_per_unit": 1.0,
        "segments": [
            {
                "sid": segment_id,
                "handle": segment_id,
                "pts": [[float(index), 0.0], [float(index + 1), 0.0]],
                "layer": f"L{(0 if index < 2 else 1) + 1:06d}",
                "kind": "line",
                "label": "unknown",
                "source": "native",
            }
            for index, segment_id in enumerate(ids)
        ],
    }
    truth = {
        "schema": "ariadne.e2.l0.object_truth.v1",
        "drawing_id": model["drawing_id"],
        "candidate_scope": "xclip_visible_linear_segments_v1",
        "label_authority": "independent_complete_object_truth",
        "object_truth_completeness": "COMPLETE",
        "positive_layers": ["W1", "W2"],
        "label_contract": {"path": "SPEC.md", "sha256": "0" * 64},
        "records": [
            {
                "placed_uid": segment_id,
                "label": "wall" if index < 2 else "non_wall",
                "wall_subtype": "W1" if index < 2 else None,
                "source_layer": "W1" if index < 2 else "OTHER",
                "kind": "line",
                "source_entity_handle": str(index),
                "source_def_handle": "A",
                "lineage_id": segment_id,
            }
            for index, segment_id in enumerate(ids)
        ],
    }
    model_path = tmp_path / "detector_input.seg.json"
    truth_path = tmp_path / "detector_truth.json"
    model_path.write_text(json.dumps(model), encoding="utf-8")
    truth_path.write_text(json.dumps(truth), encoding="utf-8")
    population = {
        "schema": "ariadne.e2.l0.detector_population_receipt.v1",
        "status": "PASS",
        "reason_code": "DETECTOR_POPULATION_QUALIFIED",
        "reason": "fixture",
        "artifacts": {
            "model_input": {"path": str(model_path), "sha256": _sha256(model_path)},
            "truth": {"path": str(truth_path), "sha256": _sha256(truth_path)},
        },
    }
    population_path = tmp_path / "detector_population_receipt.json"
    population_path.write_text(json.dumps(population), encoding="utf-8")
    transfer = tmp_path / "a4_transfer.py"
    transfer.write_text("# sealed fixture\n", encoding="utf-8")
    return population_path, model_path, truth_path, transfer


def test_complete_object_truth_still_requires_sealed_executor_before_jury(
    tmp_path: Path,
):
    population, model, truth, transfer = _inputs(tmp_path)

    result = runner.run(
        population_receipt_path=population,
        model_input_path=model,
        truth_path=truth,
        transfer_harness=transfer,
        out_dir=tmp_path / "out",
    )

    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"
    assert not (tmp_path / "out" / "segment_metrics.json").exists()
    assert not (tmp_path / "out" / "baseline_predictions.json").exists()


def test_unsealed_baseline_runner_has_no_model_factory_seam() -> None:
    assert "jury_factory" not in inspect.signature(runner.run).parameters


def test_run_blocks_layer_cue_before_jury_execution(tmp_path: Path):
    population, model, truth, transfer = _inputs(tmp_path)
    model_value = json.loads(model.read_text(encoding="utf-8"))
    model_value["segments"][0]["layer"] = "W1"
    model.write_text(json.dumps(model_value), encoding="utf-8")
    receipt = json.loads(population.read_text(encoding="utf-8"))
    receipt["artifacts"]["model_input"]["sha256"] = _sha256(model)
    population.write_text(json.dumps(receipt), encoding="utf-8")

    result = runner.run(
        population_receipt_path=population,
        model_input_path=model,
        truth_path=truth,
        transfer_harness=transfer,
        out_dir=tmp_path / "out",
    )

    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "MODEL_ARM_EXECUTION_FAILED"
    assert "label cue" in result["reason"]
    assert not (tmp_path / "out" / "segment_metrics.json").exists()


def test_complete_object_truth_accepts_only_drawing_local_layer_pseudonyms(tmp_path: Path):
    population, model, truth, _ = _inputs(tmp_path)
    model_value = json.loads(model.read_text(encoding="utf-8"))
    assert all(re.fullmatch(r"L\d{6}", row["layer"]) for row in model_value["segments"])

    _, loaded_model, truth_by_id = runner._load_contract(population, model, truth)

    assert len(loaded_model["segments"]) == len(truth_by_id) == 4


def test_complete_object_truth_rejects_a_pseudonym_that_merges_source_layers(tmp_path: Path):
    population, model, truth, transfer = _inputs(tmp_path)
    model_value = json.loads(model.read_text(encoding="utf-8"))
    model_value["segments"][2]["layer"] = "L000001"
    model.write_text(json.dumps(model_value), encoding="utf-8")
    receipt = json.loads(population.read_text(encoding="utf-8"))
    receipt["artifacts"]["model_input"]["sha256"] = _sha256(model)
    population.write_text(json.dumps(receipt), encoding="utf-8")

    result = runner.run(
        population_receipt_path=population,
        model_input_path=model,
        truth_path=truth,
        transfer_harness=transfer,
        out_dir=tmp_path / "out",
    )

    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "MODEL_ARM_EXECUTION_FAILED"
    assert "source-layer partition" in result["reason"]
    assert not (tmp_path / "out" / "segment_metrics.json").exists()


def test_complete_object_truth_rejects_pseudonyms_that_split_one_source_layer(tmp_path: Path):
    population, model, truth, transfer = _inputs(tmp_path)
    model_value = json.loads(model.read_text(encoding="utf-8"))
    model_value["segments"][1]["layer"] = "L000003"
    model.write_text(json.dumps(model_value), encoding="utf-8")
    receipt = json.loads(population.read_text(encoding="utf-8"))
    receipt["artifacts"]["model_input"]["sha256"] = _sha256(model)
    population.write_text(json.dumps(receipt), encoding="utf-8")

    result = runner.run(
        population_receipt_path=population,
        model_input_path=model,
        truth_path=truth,
        transfer_harness=transfer,
        out_dir=tmp_path / "out",
    )

    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "MODEL_ARM_EXECUTION_FAILED"
    assert "source-layer partition" in result["reason"]
    assert not (tmp_path / "out" / "segment_metrics.json").exists()


def test_run_blocks_positive_layer_anchor_before_jury_execution(tmp_path: Path):
    population, model, truth, transfer = _inputs(tmp_path)
    truth_value = json.loads(truth.read_text(encoding="utf-8"))
    truth_value["schema"] = "ariadne.e2.l0.detector_label_anchors.v1"
    truth_value["label_authority"] = "owner_layer_positive_only"
    truth_value["object_truth_completeness"] = "UNKNOWN"
    for record in truth_value["records"]:
        record["object_label"] = "UNKNOWN"
        record["layer_anchor"] = (
            "POSITIVE_UNLABELED"
            if record["source_layer"] in {"W1", "W2"}
            else "UNKNOWN"
        )
        record.pop("label")
    truth.write_text(json.dumps(truth_value), encoding="utf-8")
    receipt = json.loads(population.read_text(encoding="utf-8"))
    receipt["status"] = "PASS_WITH_DEFERRAL"
    receipt["reason_code"] = "LABEL_COMPLETENESS_UNKNOWN"
    receipt["artifacts"]["truth"]["sha256"] = _sha256(truth)
    population.write_text(json.dumps(receipt), encoding="utf-8")
    result = runner.run(
        population_receipt_path=population,
        model_input_path=model,
        truth_path=truth,
        transfer_harness=transfer,
        out_dir=tmp_path / "out",
    )

    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "LABEL_COMPLETENESS_UNKNOWN"
    assert not (tmp_path / "out" / "segment_metrics.json").exists()
    assert not (tmp_path / "out" / "baseline_predictions.json").exists()


def test_run_blocks_object_metrics_when_complete_truth_is_only_self_declared_unknown(
    tmp_path: Path,
):
    population, model, truth, transfer = _inputs(tmp_path)
    truth_value = json.loads(truth.read_text(encoding="utf-8"))
    truth_value["object_truth_completeness"] = "UNKNOWN"
    truth.write_text(json.dumps(truth_value), encoding="utf-8")
    receipt = json.loads(population.read_text(encoding="utf-8"))
    receipt["artifacts"]["truth"]["sha256"] = _sha256(truth)
    population.write_text(json.dumps(receipt), encoding="utf-8")
    result = runner.run(
        population_receipt_path=population,
        model_input_path=model,
        truth_path=truth,
        transfer_harness=transfer,
        out_dir=tmp_path / "out",
    )

    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "LABEL_COMPLETENESS_UNKNOWN"
    assert not (tmp_path / "out" / "segment_metrics.json").exists()


def test_run_blocks_object_metrics_when_complete_truth_has_only_one_class(
    tmp_path: Path,
):
    population, model, truth, transfer = _inputs(tmp_path)
    truth_value = json.loads(truth.read_text(encoding="utf-8"))
    for record in truth_value["records"]:
        record["label"] = "wall"
    truth.write_text(json.dumps(truth_value), encoding="utf-8")
    receipt = json.loads(population.read_text(encoding="utf-8"))
    receipt["artifacts"]["truth"]["sha256"] = _sha256(truth)
    population.write_text(json.dumps(receipt), encoding="utf-8")
    result = runner.run(
        population_receipt_path=population,
        model_input_path=model,
        truth_path=truth,
        transfer_harness=transfer,
        out_dir=tmp_path / "out",
    )

    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "LABEL_COMPLETENESS_UNKNOWN"
    assert not (tmp_path / "out" / "segment_metrics.json").exists()


def test_frozen_jury_uses_the_sealed_a4_rule_library():
    source = inspect.getsource(_phase2_models.FrozenJury._score_one)

    assert 'self.components["rules_lib"].evaluate' in source
    assert "rule_scorer" not in source
    assert "/ 16.0" in source


def test_report_retracts_layer_only_binary_metrics():
    report = (
        REPO / "reports" / "e2" / "E2_L0_LINEAR_SEGMENT_BASELINES_20260807.md"
    ).read_text(encoding="utf-8")

    assert report.startswith("상태: **RETRACTED**")
    assert "LABEL_COMPLETENESS_UNKNOWN" in report
    assert "7,189개는 음성 정답이 아니다" in report
    assert "AP·PR-AUC·confusion matrix는 모두 철회" in report
