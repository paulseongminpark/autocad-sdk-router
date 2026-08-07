#!/usr/bin/env python3
"""Run sealed rules/GBDT/GNN on one qualified, leakage-free L0 population.

This is a frozen transfer measurement, not training.  The model-facing SEG-IR
must contain the same stable IDs as the separate truth table while carrying no
layer name or label cue.  Metrics are segment-level on one owner-labeled drawing;
wall-object PQ and population-generalization claims remain deferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import numpy as np
from sklearn.metrics import auc, average_precision_score, precision_recall_curve


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


PASS = "PASS"
PASS_WITH_DEFERRAL = "PASS_WITH_DEFERRAL"
PARTIAL_PASS = "PARTIAL_PASS"
BLOCKED = "BLOCKED"
THRESHOLD = 0.5
MODEL_ARMS = ("rules", "gbdt", "gnn")
EXPECTED_SEGMENT_KEYS = frozenset(
    {"sid", "handle", "pts", "layer", "kind", "label", "source"}
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def _file_record(path: Path) -> dict[str, Any]:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": _sha256(path)}


def _load_contract(
    population_receipt_path: Path,
    model_input_path: Path,
    truth_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    receipt = _read_json(population_receipt_path)
    model = _read_json(model_input_path)
    truth = _read_json(truth_path)
    if (
        receipt.get("schema") != "ariadne.e2.l0.detector_population_receipt.v1"
        or receipt.get("status") not in {PASS, PASS_WITH_DEFERRAL}
        or receipt.get("reason_code")
        not in {
            "DETECTOR_POPULATION_QUALIFIED",
            "DUAL_ORACLE_CONSENSUS_WITH_DISPUTED_SEGMENTS",
        }
    ):
        raise ValueError("detector population receipt is not PASS-qualified")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ValueError("detector population receipt has no artifact bindings")
    expected_artifacts = {"model_input": model_input_path, "truth": truth_path}
    for role, path in expected_artifacts.items():
        record = artifacts.get(role)
        if (
            not isinstance(record, Mapping)
            or Path(str(record.get("path") or "")).resolve() != path.resolve()
            or str(record.get("sha256") or "").lower() != _sha256(path)
        ):
            raise ValueError(f"detector population artifact binding drifted: {role}")

    expected_top = {"ir", "drawing_id", "units", "scale_mm_per_unit", "segments"}
    if set(model) != expected_top or model.get("ir") != "seg.v1":
        raise ValueError("model input is not exact SEG-IR v1")
    segments = model.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("model input has no segment population")
    model_ids: set[str] = set()
    for index, segment in enumerate(segments):
        if not isinstance(segment, Mapping) or set(segment) != EXPECTED_SEGMENT_KEYS:
            raise ValueError(f"model segment[{index}] violates the exact SEG-IR key contract")
        handle = str(segment.get("handle") or "")
        if (
            not handle
            or segment.get("sid") != handle
            or segment.get("layer") != ""
            or segment.get("label") != "unknown"
        ):
            raise ValueError(f"model segment[{index}] contains a label cue or invalid stable ID")
        if handle in model_ids:
            raise ValueError("model input contains duplicate stable IDs")
        model_ids.add(handle)

    if (
        truth.get("schema") != "ariadne.e2.l0.detector_truth.v1"
        or truth.get("drawing_id") != model.get("drawing_id")
        or truth.get("label_authority") != "owner_complete_binary_layer_contract"
    ):
        raise ValueError("truth table does not match the qualified owner-label contract")
    truth_records = truth.get("records")
    if not isinstance(truth_records, list):
        raise ValueError("truth table has no records")
    truth_by_id: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(truth_records):
        if not isinstance(record, Mapping):
            raise ValueError(f"truth record[{index}] is not an object")
        segment_id = str(record.get("placed_uid") or "")
        if not segment_id or segment_id in truth_by_id or record.get("label") not in {"wall", "non_wall"}:
            raise ValueError(f"truth record[{index}] has invalid identity or label")
        truth_by_id[segment_id] = dict(record)
    truth_ids = set(truth_by_id)
    if model_ids != truth_ids:
        raise ValueError(
            f"model/truth stable-ID mismatch: missing={len(truth_ids-model_ids)} extra={len(model_ids-truth_ids)}"
        )
    return receipt, model, truth_by_id


def _confusion(y_true: np.ndarray, scores: np.ndarray, threshold: float = THRESHOLD) -> dict[str, Any]:
    predicted = scores >= threshold
    positive = y_true == 1
    tp = int(np.sum(predicted & positive))
    fp = int(np.sum(predicted & ~positive))
    fn = int(np.sum(~predicted & positive))
    tn = int(np.sum(~predicted & ~positive))
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall > 0
        else None
    )
    return {
        "threshold": threshold,
        "threshold_policy": "fixed_0.5_diagnostic_not_tuned_on_this_drawing",
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "predicted_positive_count": tp + fp,
        "predicted_negative_count": fn + tn,
    }


def _metrics(y_true: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
    if y_true.ndim != 1 or scores.ndim != 1 or len(y_true) != len(scores) or not len(y_true):
        raise ValueError("metric arrays must be non-empty, finite one-dimensional peers")
    if not np.all(np.isfinite(scores)) or not {0, 1} <= set(np.unique(y_true).tolist()):
        raise ValueError("metric labels or scores are invalid")
    precision_curve, recall_curve, _ = precision_recall_curve(y_true, scores)
    return {
        "segment_count": int(len(y_true)),
        "positive_count": int(np.sum(y_true == 1)),
        "negative_count": int(np.sum(y_true == 0)),
        "prevalence": float(np.mean(y_true)),
        "average_precision": float(average_precision_score(y_true, scores)),
        "pr_auc_trapezoid": float(auc(recall_curve, precision_curve)),
        "score_min": float(np.min(scores)),
        "score_mean": float(np.mean(scores)),
        "score_median": float(np.median(scores)),
        "score_max": float(np.max(scores)),
        "operating_point": _confusion(y_true, scores),
    }


def _layer_diagnostics(
    ids: list[str],
    truth_by_id: Mapping[str, Mapping[str, Any]],
    scores: np.ndarray,
) -> dict[str, Any]:
    rows: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for segment_id, score in zip(ids, scores):
        truth = truth_by_id[segment_id]
        rows[str(truth.get("source_layer") or "")].append(
            (1 if truth.get("label") == "wall" else 0, float(score))
        )
    output = []
    for layer, values in rows.items():
        labels = np.asarray([value[0] for value in values], dtype=np.int8)
        layer_scores = np.asarray([value[1] for value in values], dtype=np.float64)
        predicted = layer_scores >= THRESHOLD
        output.append(
            {
                "source_layer": layer,
                "segment_count": len(values),
                "positive_count": int(np.sum(labels)),
                "predicted_positive_count": int(np.sum(predicted)),
                "mean_score": float(np.mean(layer_scores)),
            }
        )
    output.sort(key=lambda row: (-row["predicted_positive_count"], -row["segment_count"], row["source_layer"]))
    return {"layers": output, "top_false_positive_layers": [row for row in output if row["positive_count"] == 0][:20]}


def _external_arm_status() -> dict[str, Any]:
    model_root = Path(r"D:\runs\e2_program\w5\refs\models")
    sympoint_code = model_root / "SymPointV2"
    sympoint_weights = sympoint_code / "weights.pth"
    vecformer_code = model_root / "VecFormer"
    return {
        "sympointv2": {
            "status": BLOCKED,
            "reason_code": "SEMANTIC35_ADAPTER_AND_RUNTIME_UNQUALIFIED",
            "code_present": sympoint_code.is_dir(),
            "task_weights_present": sympoint_weights.is_file(),
            "reason": "The local archive is a 35-class semantic/instance checkpoint (wall class 33), but its SEG-IR adapter, nested checkpoint extraction and legacy CUDA runtime are not qualified.",
        },
        "vecformer": {
            "status": BLOCKED,
            "reason_code": "TASK_CHECKPOINT_ABSENT",
            "code_present": vecformer_code.is_dir(),
            "task_weights_present": False,
            "reason": "Training code is local, but no released/frozen VecFormer task checkpoint or prepared FloorPlanCAD input is available.",
        },
        "graph_transformer": {
            "status": BLOCKED,
            "reason_code": "NO_E2_TASK_CHECKPOINT_OR_INPUT_CONTRACT",
            "code_present": False,
            "task_weights_present": False,
            "reason": "GraphGPS/graph-transformer is a later relation-model candidate, not a qualified L0 wall checkpoint.",
        },
    }


def run(
    *,
    population_receipt_path: Path,
    model_input_path: Path,
    truth_path: Path,
    transfer_harness: Path,
    out_dir: Path,
    jury_factory: Callable[[Path], Any] | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = out_dir / "model_arm_receipt.json"
    metrics_path = out_dir / "segment_metrics.json"
    predictions_path = out_dir / "baseline_predictions.json"
    existing = [path for path in (receipt_path, metrics_path, predictions_path) if path.exists()]
    if existing:
        return {
            "schema": "ariadne.e2.l0.model_arm_receipt.v1",
            "status": BLOCKED,
            "reason_code": "OUTPUT_ALREADY_EXISTS",
            "reason": "Refusing to overwrite evidence: " + ", ".join(map(str, existing)),
        }

    def finish(status: str, reason_code: str, reason: str, **extra: Any) -> dict[str, Any]:
        receipt = {
            "schema": "ariadne.e2.l0.model_arm_receipt.v1",
            "status": status,
            "reason_code": reason_code,
            "reason": reason,
            **extra,
        }
        _write_json(receipt_path, receipt)
        receipt["receipt"] = str(receipt_path)
        return receipt

    try:
        for path in (population_receipt_path, model_input_path, truth_path, transfer_harness):
            if not path.is_file():
                raise FileNotFoundError(path)
        population_receipt, model_input, truth_by_id = _load_contract(
            population_receipt_path, model_input_path, truth_path
        )
        if jury_factory is None:
            from tools.e2.qualification._phase2_models import FrozenJury

            jury_factory = FrozenJury
        jury = jury_factory(transfer_harness)
        artifact_receipt = jury.artifact_receipt()
        if artifact_receipt.get("status") != PASS:
            raise ValueError("frozen rules/GBDT/GNN artifact integrity failed")
        result = jury.score_baseline(model_input)
        diagnostics = result.get("diagnostics")
        if not isinstance(diagnostics, Mapping):
            raise ValueError("frozen jury returned no input diagnostics")
        ids = [str(segment["handle"]) for segment in model_input["segments"]]
        expected_ids = set(ids)
        y_true = np.asarray(
            [1 if truth_by_id[segment_id]["label"] == "wall" else 0 for segment_id in ids],
            dtype=np.int8,
        )
        metrics_by_arm: dict[str, Any] = {}
        scores_by_arm: dict[str, dict[str, float]] = {}
        executed_arms: dict[str, Any] = {}
        for arm in MODEL_ARMS:
            raw = result.get(arm)
            if not isinstance(raw, Mapping):
                raise ValueError(f"frozen jury returned no {arm} score map")
            score_map = {str(key): float(value) for key, value in raw.items()}
            observed_ids = set(score_map)
            if observed_ids != expected_ids:
                raise ValueError(
                    f"{arm} stable-ID coverage mismatch: missing={len(expected_ids-observed_ids)} "
                    f"extra={len(observed_ids-expected_ids)}"
                )
            scores = np.asarray([score_map[segment_id] for segment_id in ids], dtype=np.float64)
            if not np.all(np.isfinite(scores)):
                raise ValueError(f"{arm} emitted non-finite scores")
            scores_by_arm[arm] = score_map
            metrics_by_arm[arm] = {
                **_metrics(y_true, scores),
                "layer_diagnostics": _layer_diagnostics(ids, truth_by_id, scores),
                "score_interpretation": (
                    "hand-coded geometry evidence score" if arm == "rules" else "frozen CubiCasa-supervised transfer score"
                ),
            }
            executed_arms[arm] = {
                "status": PASS,
                "input_segment_ids": len(observed_ids),
                "missing_input_ids": 0,
                "extra_input_ids": 0,
                "dependence_group": "deterministic_geometry" if arm == "rules" else "cubicasa_supervised",
            }

        prediction_rows = []
        for segment_id in ids:
            truth = truth_by_id[segment_id]
            prediction_rows.append(
                {
                    "placed_uid": segment_id,
                    "label": truth["label"],
                    "wall_subtype": truth.get("wall_subtype"),
                    "source_layer": truth.get("source_layer"),
                    **{f"{arm}_score": scores_by_arm[arm][segment_id] for arm in MODEL_ARMS},
                }
            )
        predictions = {
            "schema": "ariadne.e2.l0.baseline_predictions.v1",
            "drawing_id": model_input["drawing_id"],
            "threshold": THRESHOLD,
            "rows": prediction_rows,
        }
        metrics_payload = {
            "schema": "ariadne.e2.l0.segment_metrics.v1",
            "drawing_id": model_input["drawing_id"],
            "evaluation_unit": "xclip_visible_linear_segment_instance",
            "drawing_count": 1,
            "segment_count": len(ids),
            "positive_count": int(np.sum(y_true)),
            "negative_count": int(len(y_true) - np.sum(y_true)),
            "arms": metrics_by_arm,
            "independence_warning": "GBDT and GNN share CubiCasa supervision and are one learned evidence family.",
            "not_computed": {
                "wall_pq": "wall-chain ontology and independent chain assembler are not sealed yet",
                "junction_f1": "wall-object evaluator is not sealed yet",
                "room_cycle_f1": "downstream wall-to-room pipeline is not sealed yet",
                "cross_drawing_confidence_interval": "one owner-labeled drawing cannot estimate drawing/domain variation",
            },
        }
        _write_json(predictions_path, predictions)
        _write_json(metrics_path, metrics_payload)
        external = _external_arm_status()
        return finish(
            PARTIAL_PASS,
            "THREE_FROZEN_ARMS_RAN_EXTENDED_ARMS_BLOCKED",
            "Rules, GBDT and GNN scored every qualified ID; transformer-family arms remain unqualified.",
            inputs={
                "population_receipt": _file_record(population_receipt_path),
                "model_input": _file_record(model_input_path),
                "truth": _file_record(truth_path),
                "transfer_harness": _file_record(transfer_harness),
            },
            implementation={
                "baseline_runner": _file_record(Path(__file__)),
                "frozen_jury_adapter": _file_record(
                    REPO_ROOT / "tools" / "e2" / "qualification" / "_phase2_models.py"
                ),
            },
            population_reason_code=population_receipt.get("reason_code"),
            artifact_integrity=artifact_receipt,
            model_input_diagnostics=dict(diagnostics),
            executed_arms=executed_arms,
            blocked_arms=external,
            metrics={"path": str(metrics_path), "sha256": _sha256(metrics_path)},
            predictions={"path": str(predictions_path), "sha256": _sha256(predictions_path)},
            claim_boundary=(
                "segment-level frozen transfer on one owner-labeled drawing; no wall-object, "
                "cross-drawing, cross-company, or generalization claim"
            ),
        )
    except Exception as exc:
        return finish(
            BLOCKED,
            "MODEL_ARM_EXECUTION_FAILED",
            f"{type(exc).__name__}: {exc}",
            inputs={
                "population_receipt": str(population_receipt_path),
                "model_input": str(model_input_path),
                "truth": str(truth_path),
                "transfer_harness": str(transfer_harness),
            },
        )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--population-receipt", type=Path, required=True)
    parser.add_argument("--model-input", type=Path, required=True)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--transfer-harness", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run(
        population_receipt_path=args.population_receipt,
        model_input_path=args.model_input,
        truth_path=args.truth,
        transfer_harness=args.transfer_harness,
        out_dir=args.out_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {PASS, PARTIAL_PASS} else 2


if __name__ == "__main__":
    raise SystemExit(main())
