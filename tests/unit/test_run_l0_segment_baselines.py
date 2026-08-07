from __future__ import annotations

import hashlib
import inspect
import json
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
                "layer": "",
                "kind": "line",
                "label": "unknown",
                "source": "native",
            }
            for index, segment_id in enumerate(ids)
        ],
    }
    truth = {
        "schema": "ariadne.e2.l0.detector_truth.v1",
        "drawing_id": model["drawing_id"],
        "candidate_scope": "xclip_visible_linear_segments_v1",
        "label_authority": "owner_complete_binary_layer_contract",
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


class _FakeJury:
    def __init__(self, _: Path) -> None:
        pass

    def artifact_receipt(self) -> dict:
        return {"schema": "fixture", "status": "PASS", "checks": {}}

    def score_baseline(self, model: dict) -> dict:
        ids = [segment["handle"] for segment in model["segments"]]
        scores = {
            "rules": [0.9, 0.8, 0.4, 0.1],
            "gbdt": [0.7, 0.6, 0.3, 0.2],
            "gnn": [0.95, 0.55, 0.45, 0.05],
        }
        return {
            "schema": "e2.segment_juror_baseline.v1",
            "status": "FROZEN_TRANSFER_SCORES",
            **{arm: dict(zip(ids, values)) for arm, values in scores.items()},
            "diagnostics": {
                "input_segments": len(ids),
                "rule_scored_handles": len(ids),
                "gbdt_scored_handles": len(ids),
                "gnn_scored_handles": len(ids),
                "graph_edge_count": 3,
                "graph_feature_count": 17,
                "gbdt_feature_count": 12,
            },
        }


def test_run_scores_every_id_and_keeps_extended_arms_blocked(tmp_path: Path):
    population, model, truth, transfer = _inputs(tmp_path)
    result = runner.run(
        population_receipt_path=population,
        model_input_path=model,
        truth_path=truth,
        transfer_harness=transfer,
        out_dir=tmp_path / "out",
        jury_factory=_FakeJury,
    )

    assert result["status"] == "PARTIAL_PASS"
    assert set(result["executed_arms"]) == {"rules", "gbdt", "gnn"}
    assert all(row["status"] == "PASS" for row in result["executed_arms"].values())
    assert set(result["blocked_arms"]) == {"sympointv2", "vecformer", "graph_transformer"}
    metrics = json.loads((tmp_path / "out" / "segment_metrics.json").read_text(encoding="utf-8"))
    assert metrics["segment_count"] == 4
    assert metrics["positive_count"] == 2
    assert metrics["arms"]["rules"]["average_precision"] == 1.0
    assert metrics["arms"]["rules"]["operating_point"] == {
        "threshold": 0.5,
        "threshold_policy": "fixed_0.5_diagnostic_not_tuned_on_this_drawing",
        "tp": 2,
        "fp": 0,
        "fn": 0,
        "tn": 2,
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
        "predicted_positive_count": 2,
        "predicted_negative_count": 2,
    }
    predictions = json.loads((tmp_path / "out" / "baseline_predictions.json").read_text(encoding="utf-8"))
    assert len(predictions["rows"]) == 4


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
        jury_factory=_FakeJury,
    )

    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "MODEL_ARM_EXECUTION_FAILED"
    assert "label cue" in result["reason"]
    assert not (tmp_path / "out" / "segment_metrics.json").exists()


def test_frozen_jury_uses_the_sealed_a4_rule_library():
    source = inspect.getsource(_phase2_models.FrozenJury._score_one)

    assert 'self.components["rules_lib"].evaluate' in source
    assert "rule_scorer" not in source
    assert "/ 16.0" in source
