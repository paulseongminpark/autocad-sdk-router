#!/usr/bin/env python3
"""Validate L0 inputs and refuse the retired unsealed baseline runner.

This is a frozen transfer measurement, not training.  The model-facing SEG-IR
must contain the same stable IDs as the separate truth table while carrying no
layer name or label cue.  Metrics are segment-level on one owner-labeled drawing;
wall-object PQ and population-generalization claims remain deferred.  A known
wall layer is not complete object truth, and even complete truth cannot start a
host jury until a registered OS-confined sealed executor owns the run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


PASS = "PASS"
PASS_WITH_DEFERRAL = "PASS_WITH_DEFERRAL"
BLOCKED = "BLOCKED"
EXPECTED_SEGMENT_KEYS = frozenset(
    {"sid", "handle", "pts", "layer", "kind", "label", "source"}
)


class LabelCompletenessUnknownError(ValueError):
    """The supplied labels are layer anchors, not complete binary object truth."""


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
            "LABEL_COMPLETENESS_UNKNOWN",
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
    model_layer_by_id: dict[str, str] = {}
    for index, segment in enumerate(segments):
        if not isinstance(segment, Mapping) or set(segment) != EXPECTED_SEGMENT_KEYS:
            raise ValueError(f"model segment[{index}] violates the exact SEG-IR key contract")
        handle = str(segment.get("handle") or "")
        if (
            not handle
            or segment.get("sid") != handle
            or not isinstance(segment.get("layer"), str)
            or re.fullmatch(r"L\d{6}", str(segment.get("layer"))) is None
            or segment.get("label") != "unknown"
        ):
            raise ValueError(f"model segment[{index}] contains a label cue or invalid stable ID")
        if handle in model_ids:
            raise ValueError("model input contains duplicate stable IDs")
        model_ids.add(handle)
        model_layer_by_id[handle] = str(segment["layer"])

    if truth.get("drawing_id") != model.get("drawing_id"):
        raise ValueError("truth table does not match the qualified owner-label contract")
    if (
        truth.get("schema") == "ariadne.e2.l0.detector_label_anchors.v1"
        and truth.get("label_authority") == "owner_layer_positive_only"
        and truth.get("object_truth_completeness") == "UNKNOWN"
    ):
        records = truth.get("records")
        if not isinstance(records, list) or not records:
            raise ValueError("positive layer anchor table has no records")
        anchor_ids: set[str] = set()
        for index, record in enumerate(records):
            if not isinstance(record, Mapping):
                raise ValueError(f"layer anchor record[{index}] is not an object")
            segment_id = str(record.get("placed_uid") or "")
            if (
                not segment_id
                or segment_id in anchor_ids
                or record.get("object_label") != "UNKNOWN"
                or record.get("layer_anchor") not in {"POSITIVE_UNLABELED", "UNKNOWN"}
            ):
                raise ValueError(f"layer anchor record[{index}] is invalid")
            anchor_ids.add(segment_id)
        if model_ids != anchor_ids:
            raise ValueError("model/layer-anchor stable-ID population mismatch")
        raise LabelCompletenessUnknownError(
            "W1/W2 are positive layer anchors only; object negatives, layer purity and wall "
            "completeness are unknown, so AP/PR-AUC/confusion metrics are forbidden"
        )
    if (
        truth.get("schema") != "ariadne.e2.l0.object_truth.v1"
        or truth.get("label_authority") != "independent_complete_object_truth"
    ):
        raise ValueError("truth table is not independently complete object truth")
    if (
        truth.get("object_truth_completeness") != "COMPLETE"
        or truth.get("candidate_scope") != "xclip_visible_linear_segments_v1"
    ):
        raise LabelCompletenessUnknownError(
            "object truth is not explicitly complete for the qualified linear candidate scope"
        )
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
    if {str(record.get("label") or "") for record in truth_by_id.values()} != {
        "wall",
        "non_wall",
    }:
        raise LabelCompletenessUnknownError(
            "complete object metrics require both wall and non-wall gold labels"
        )
    pseudonym_by_source_layer: dict[str, str] = {}
    source_layer_by_pseudonym: dict[str, str] = {}
    for segment_id, record in truth_by_id.items():
        source_layer = str(record.get("source_layer") or "")
        pseudonym = model_layer_by_id[segment_id]
        if not source_layer:
            raise ValueError("complete object truth has no source layer for partition validation")
        previous_pseudonym = pseudonym_by_source_layer.setdefault(source_layer, pseudonym)
        previous_source_layer = source_layer_by_pseudonym.setdefault(pseudonym, source_layer)
        if previous_pseudonym != pseudonym or previous_source_layer != source_layer:
            raise ValueError("model pseudonyms do not preserve the source-layer partition")
    return receipt, model, truth_by_id


def run(
    *,
    population_receipt_path: Path,
    model_input_path: Path,
    truth_path: Path,
    transfer_harness: Path,
    out_dir: Path,
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
        population_receipt, _, truth_by_id = _load_contract(
            population_receipt_path, model_input_path, truth_path
        )
        return finish(
            BLOCKED,
            "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED",
            (
                "Complete object truth passed the local data-contract checks, but this "
                "standalone host runner cannot prove independent gold authority, exact "
                "model/checkpoint bytes, or confined input consumption. No jury was loaded."
            ),
            metrics_not_computed={
                "average_precision": "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED",
                "pr_auc": "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED",
                "confusion_matrix": "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED",
            },
            inputs={
                "population_receipt": _file_record(population_receipt_path),
                "model_input": _file_record(model_input_path),
                "truth": _file_record(truth_path),
                "transfer_harness": _file_record(transfer_harness),
            },
            validated_population_ids=len(truth_by_id),
            population_reason_code=population_receipt.get("reason_code"),
        )
    except LabelCompletenessUnknownError as exc:
        return finish(
            BLOCKED,
            "LABEL_COMPLETENESS_UNKNOWN",
            str(exc),
            metrics_not_computed={
                "average_precision": "LABEL_COMPLETENESS_UNKNOWN",
                "pr_auc": "LABEL_COMPLETENESS_UNKNOWN",
                "confusion_matrix": "LABEL_COMPLETENESS_UNKNOWN",
            },
            inputs={
                "population_receipt": str(population_receipt_path),
                "model_input": str(model_input_path),
                "truth": str(truth_path),
                "transfer_harness": str(transfer_harness),
            },
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
    return 0 if result.get("status") == PASS else 2


if __name__ == "__main__":
    raise SystemExit(main())
