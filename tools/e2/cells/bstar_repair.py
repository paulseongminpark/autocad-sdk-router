#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Repair B* geometry-family leakage by excluding cross-family val drawings.

The runner is deliberately limited to the frozen train/val feature universe.
It imports the baseline implementation for its metric, fitting, aggregation,
family-audit, seed, and model-selection behavior.  It has no path for the test
split and writes only beside this file.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import math
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


# Match the frozen cell's CPU pool bounds before importing numerical packages.
for _thread_env in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_thread_env, "8")

# Importing the read-only baseline must not create or refresh a .pyc beside it.
sys.dont_write_bytecode = True

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier


CELL_DIR = Path(__file__).resolve().parent
BASELINE_DIR = Path(r"D:\runs\e2_program\cells\baseline_freeze")
BASELINE_PY = BASELINE_DIR / "baseline_freeze.py"
V1_RESULTS_PATH = BASELINE_DIR / "results.json"
V1_MANIFEST_PATH = BASELINE_DIR / "bstar_manifest.json"
V1_MODEL_PATH = BASELINE_DIR / "bstar_model.joblib"
PACKET_PATH = Path(r"D:\runs\e2_program\build\PACKET_bstar_repair.md")

RESULTS_V2_PATH = CELL_DIR / "results_v2.json"
MANIFEST_V2_PATH = CELL_DIR / "bstar_manifest_v2.json"
MODEL_V2_PATH = CELL_DIR / "bstar_model_v2.joblib"
REPORT_PATH = CELL_DIR / "REPORT.md"

EXPECTED_MODEL_SEEDS = (17, 29, 43)
EXPECTED_ORIGINAL_VAL_DRAWINGS = 400
EXPECTED_REPAIRED_VAL_DRAWINGS = 396
EXPECTED_GEOMETRY_FAMILY_COLLISIONS = 4
RAM_LIMIT_BYTES = 48 * 1024**3

PRIMARY_ORDER = (
    "fast_score_p1",
    "logistic_local6",
    "hist_gbdt_local6_p2a",
    "hist_gbdt_context12_p2b",
)
DIAGNOSTIC_ARM = "hist_gbdt_context_layer_name_diagnostic"
ALL_ARMS = PRIMARY_ORDER + (DIAGNOSTIC_ARM,)
METRIC_KEYS = (
    "auprc",
    "f1",
    "precision",
    "recall",
    "threshold",
    "tp",
    "fp",
    "fn",
    "tn",
    "n",
)
FLOAT_METRIC_KEYS = {"auprc", "f1", "precision", "recall", "threshold"}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _assert_output(path: Path) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(CELL_DIR.resolve())
    except ValueError as exc:
        raise RuntimeError(f"refusing output outside cell directory: {resolved}") from exc


def _write_json(path: Path, value: Any) -> None:
    _assert_output(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _write_text(path: Path, value: str) -> None:
    _assert_output(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def _write_joblib(path: Path, value: Any) -> None:
    _assert_output(path)
    temporary = path.with_name(path.name + ".tmp")
    joblib.dump(value, temporary, compress=3)
    os.replace(temporary, path)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_baseline() -> Any:
    if not BASELINE_PY.is_file():
        raise FileNotFoundError(BASELINE_PY)
    spec = importlib.util.spec_from_file_location("bstar_repair_baseline", BASELINE_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import baseline implementation: {BASELINE_PY}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if Path(module.__file__).resolve() != BASELINE_PY.resolve():
        raise RuntimeError("baseline import path mismatch")
    return module


def _required_sources() -> dict[str, str]:
    paths = {
        "packet_bstar_repair": PACKET_PATH,
        "baseline_freeze_py": BASELINE_PY,
        "results_v1": V1_RESULTS_PATH,
        "manifest_v1": V1_MANIFEST_PATH,
        "model_v1": V1_MODEL_PATH,
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing required sources: {missing}")
    return {name: _sha256(path) for name, path in paths.items()}


def _determine_exclusions(v1: dict[str, Any]) -> dict[str, Any]:
    audit = v1["family_audit"]
    if int(audit["drawing_id_collision_count"]) != 0:
        raise RuntimeError("unexpected drawing-id collision in v1 family audit")
    if int(audit["geometry_family_collision_count"]) != EXPECTED_GEOMETRY_FAMILY_COLLISIONS:
        raise RuntimeError("v1 geometry-family collision count drift")
    examples = list(audit["geometry_family_collision_examples"])
    if len(examples) != int(audit["geometry_family_collision_count"]):
        raise RuntimeError("v1 family examples do not fully enumerate collisions")

    mappings: list[dict[str, Any]] = []
    for example in sorted(examples, key=lambda row: row["family_fingerprint"]):
        fingerprint = str(example["family_fingerprint"])
        train_ids = sorted({str(value) for value in example["train_drawing_ids"]})
        val_ids = sorted({str(value) for value in example["val_drawing_ids"]})
        if not train_ids or not val_ids:
            raise RuntimeError(f"incomplete cross-fold family {fingerprint}")
        for drawing_id in val_ids:
            mappings.append(
                {
                    "family_fingerprint": fingerprint,
                    "train_drawing_ids": train_ids,
                    "excluded_val_drawing_id": drawing_id,
                }
            )
    mappings.sort(
        key=lambda row: (row["excluded_val_drawing_id"], row["family_fingerprint"])
    )
    excluded_ids = sorted({row["excluded_val_drawing_id"] for row in mappings})
    if len(mappings) != len(excluded_ids):
        raise RuntimeError("a val drawing belongs to more than one listed collision family")
    if len(excluded_ids) != EXPECTED_GEOMETRY_FAMILY_COLLISIONS:
        raise RuntimeError("deterministic val exclusion count drift")
    payload = {
        "rule": "same geometry family stays in one fold; exclude val-side members",
        "mappings": mappings,
        "excluded_val_drawing_ids": excluded_ids,
    }
    return {**payload, "deterministic_sha256": _canonical_hash(payload)}


def _validate_design_cache(
    baseline: Any,
    split: str,
    base: dict[str, np.ndarray],
    meta: dict[str, Any],
    context_design: np.ndarray,
    leaky_design: np.ndarray,
) -> int:
    context = np.load(meta["splits"][split]["context_path"], mmap_mode="r")
    layer = np.load(meta["splits"][split]["layer_path"], mmap_mode="r")
    expected_context_shape = (len(base["y"]), len(baseline.P2B_FEATURE_NAMES))
    expected_leaky_shape = (len(base["y"]), len(baseline.DIAGNOSTIC_FEATURE_NAMES))
    if context_design.shape != expected_context_shape:
        raise RuntimeError(f"{split}: context design shape mismatch")
    if leaky_design.shape != expected_leaky_shape:
        raise RuntimeError(f"{split}: diagnostic design shape mismatch")
    mismatch_count = 0
    width = len(baseline.BASE_FEATURE_NAMES)
    p2b_width = len(baseline.P2B_FEATURE_NAMES)
    for start in range(0, len(base["y"]), baseline.MATRIX_CHUNK_ROWS):
        end = min(start + baseline.MATRIX_CHUNK_ROWS, len(base["y"]))
        mismatch_count += int(
            not np.array_equal(
                context_design[start:end, :width],
                base["X"][start:end],
                equal_nan=True,
            )
        )
        mismatch_count += int(
            not np.array_equal(
                context_design[start:end, width:], context[start:end], equal_nan=True
            )
        )
        mismatch_count += int(
            not np.array_equal(
                leaky_design[start:end, :p2b_width],
                context_design[start:end],
                equal_nan=True,
            )
        )
        mismatch_count += int(
            not np.array_equal(
                leaky_design[start:end, p2b_width:],
                layer[start:end],
                equal_nan=True,
            )
        )
    if mismatch_count:
        raise RuntimeError(f"{split}: frozen design-cache mismatch count {mismatch_count}")
    return mismatch_count


def _prepare_data(baseline: Any, v1: dict[str, Any], exclusion: dict[str, Any]) -> dict[str, Any]:
    if tuple(v1["run"]["model_seeds"]) != EXPECTED_MODEL_SEEDS:
        raise RuntimeError("v1 model seed drift")
    if tuple(baseline.MODEL_SEEDS) != EXPECTED_MODEL_SEEDS:
        raise RuntimeError("baseline model seed drift")
    if tuple(v1["primary_arm_order"]) != PRIMARY_ORDER:
        raise RuntimeError("v1 primary arm order drift")

    meta = baseline._load_extraction_meta()  # noqa: SLF001
    if _canonical_hash(meta["family_audit"]) != _canonical_hash(v1["family_audit"]):
        raise RuntimeError("v1 results and extraction metadata family audits differ")
    train = baseline._load_base("train")  # noqa: SLF001
    val = baseline._load_base("val")  # noqa: SLF001
    xtr_context = np.load(BASELINE_DIR / "_work" / "p2b_design_train.npy", mmap_mode="r")
    xva_context_full = np.load(BASELINE_DIR / "_work" / "p2b_design_val.npy", mmap_mode="r")
    xtr_leaky = np.load(BASELINE_DIR / "_work" / "leaky_design_train.npy", mmap_mode="r")
    xva_leaky_full = np.load(BASELINE_DIR / "_work" / "leaky_design_val.npy", mmap_mode="r")
    design_cache_mismatch_count = _validate_design_cache(
        baseline, "train", train, meta, xtr_context, xtr_leaky
    )
    design_cache_mismatch_count += _validate_design_cache(
        baseline, "val", val, meta, xva_context_full, xva_leaky_full
    )

    train_records = list(meta["splits"]["train"]["drawing_records"])
    val_records = list(meta["splits"]["val"]["drawing_records"])
    if len(val_records) != EXPECTED_ORIGINAL_VAL_DRAWINGS:
        raise RuntimeError("original val drawing count drift")
    gids = np.asarray(val["gid"], dtype=np.int32)
    if int(gids.min()) != 0 or int(gids.max()) + 1 != len(val_records):
        raise RuntimeError("val gid coverage does not match drawing records")
    counts = np.bincount(gids, minlength=len(val_records))
    for gid, record in enumerate(val_records):
        if int(counts[gid]) != int(record["row_count"]):
            raise RuntimeError(f"val row-count mismatch at gid {gid}")

    excluded_ids = set(exclusion["excluded_val_drawing_ids"])
    excluded_gids = [
        gid for gid, record in enumerate(val_records) if record["drawing_id"] in excluded_ids
    ]
    if len(excluded_gids) != len(excluded_ids):
        raise RuntimeError("not every deterministic exclusion maps to one val gid")
    matched_ids = {val_records[gid]["drawing_id"] for gid in excluded_gids}
    if matched_ids != excluded_ids:
        raise RuntimeError("val gid exclusion set differs from deterministic ids")
    row_keep = ~np.isin(gids, np.asarray(excluded_gids, dtype=np.int32))
    remaining_records = [
        record for gid, record in enumerate(val_records) if gid not in set(excluded_gids)
    ]
    if len(remaining_records) != EXPECTED_REPAIRED_VAL_DRAWINGS:
        raise RuntimeError("repaired val drawing count drift")
    removed_rows = int(np.sum(~row_keep))
    recorded_removed_rows = sum(int(val_records[gid]["row_count"]) for gid in excluded_gids)
    if removed_rows != recorded_removed_rows:
        raise RuntimeError("removed row count differs from drawing-record total")

    repaired_family_audit = baseline._family_audit(  # noqa: SLF001
        train_records, remaining_records
    )
    for key in (
        "drawing_id_collision_count",
        "geometry_family_collision_count",
        "geometry_cross_fold_drawing_pair_count",
        "family_collision_count",
    ):
        if int(repaired_family_audit[key]) != 0:
            raise RuntimeError(f"post-repair {key} is nonzero")

    mapping_by_id = {
        row["excluded_val_drawing_id"]: row for row in exclusion["mappings"]
    }
    excluded_records = []
    for gid in excluded_gids:
        record = val_records[gid]
        mapping = mapping_by_id[record["drawing_id"]]
        if record["family_fingerprint"] != mapping["family_fingerprint"]:
            raise RuntimeError("exclusion fingerprint differs from extraction metadata")
        excluded_records.append({"gid": int(gid), **record})
    excluded_records.sort(key=lambda row: row["drawing_id"])

    repaired_split_payload = {
        "schema": "e2.bstar_repair.split.v2",
        "parent_split_hash": meta["split_hash"],
        "repair_rule": exclusion["rule"],
        "excluded_records": excluded_records,
        "remaining_val_drawings_sha256": _canonical_hash(remaining_records),
        "train_drawings_sha256": _canonical_hash(train_records),
    }
    return {
        "meta": meta,
        "train": train,
        "val": val,
        "row_keep": row_keep,
        "excluded_gids": sorted(int(value) for value in excluded_gids),
        "excluded_records": excluded_records,
        "remaining_records": remaining_records,
        "removed_rows": removed_rows,
        "repaired_family_audit": repaired_family_audit,
        "repaired_split_hash": _canonical_hash(repaired_split_payload),
        "repaired_split_payload": repaired_split_payload,
        "design_cache_mismatch_count": design_cache_mismatch_count,
        "xtr_context": xtr_context,
        "xva_context_full": xva_context_full,
        "xtr_leaky": xtr_leaky,
        "xva_leaky_full": xva_leaky_full,
    }


def _metric_projection(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in METRIC_KEYS}


def _compare_metric_rows(
    scope: str,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    mismatches = []
    maximum_absolute_delta = 0.0
    for key in METRIC_KEYS:
        left = actual[key]
        right = expected[key]
        if key in FLOAT_METRIC_KEYS:
            delta = abs(float(left) - float(right))
            maximum_absolute_delta = max(maximum_absolute_delta, delta)
            if not math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12):
                mismatches.append(key)
        elif int(left) != int(right):
            mismatches.append(key)
    return {
        "scope": scope,
        "mismatch_count": len(mismatches),
        "mismatch_fields": mismatches,
        "maximum_absolute_float_delta": maximum_absolute_delta,
    }


def _permutation_control(
    baseline: Any, rows: list[dict[str, Any]], observed_p2b: float
) -> dict[str, Any]:
    null_auprc = [row["auprc"] for row in rows]
    null_f1 = [row["f1"] for row in rows]
    heldout = rows[0]
    remaining = rows[1:]
    return {
        "seed_list": list(baseline.PERMUTATION_SEEDS),
        "seed_list_sha256": _canonical_hash(list(baseline.PERMUTATION_SEEDS)),
        "rows": rows,
        "auprc": baseline._distribution(null_auprc),  # noqa: SLF001
        "f1": baseline._distribution(null_f1),  # noqa: SLF001
        "observed_p2b_auprc": observed_p2b,
        "observed_p2b_auprc_percentile": baseline._percentile_position(  # noqa: SLF001
            observed_p2b, null_auprc
        ),
        "heldout_shuffle_position": {
            "seed": heldout["seed"],
            "auprc": heldout["auprc"],
            "auprc_percentile": baseline._percentile_position(  # noqa: SLF001
                heldout["auprc"], (row["auprc"] for row in remaining)
            ),
            "reference_auprc": baseline._distribution(  # noqa: SLF001
                row["auprc"] for row in remaining
            ),
            "f1": heldout["f1"],
            "f1_percentile": baseline._percentile_position(  # noqa: SLF001
                heldout["f1"], (row["f1"] for row in remaining)
            ),
            "reference_f1": baseline._distribution(  # noqa: SLF001
                row["f1"] for row in remaining
            ),
        },
    }


def _measure(
    baseline: Any, v1: dict[str, Any], prepared: dict[str, Any]
) -> dict[str, Any]:
    train = prepared["train"]
    val = prepared["val"]
    keep = prepared["row_keep"]
    ytr = train["y"].astype(np.int8, copy=False)
    yva_full = val["y"].astype(np.int8, copy=False)
    yva = yva_full[keep]
    xtr_base = train["X"]
    xva_base_full = val["X"]
    xva_base = xva_base_full[keep]
    xtr_context = prepared["xtr_context"]
    xva_context_full = prepared["xva_context_full"]
    xva_context = xva_context_full[keep]
    xtr_leaky = prepared["xtr_leaky"]
    xva_leaky_full = prepared["xva_leaky_full"]
    xva_leaky = xva_leaky_full[keep]

    arm_seed_metrics_v2: dict[str, list[dict[str, Any]]] = {
        arm: [] for arm in ALL_ARMS
    }
    arm_seed_metrics_v1_recomputed: dict[str, list[dict[str, Any]]] = {
        arm: [] for arm in ALL_ARMS
    }
    reproduction_checks: list[dict[str, Any]] = []
    models_by_arm: dict[str, dict[int, Any]] = {arm: {} for arm in ALL_ARMS}

    p1_probability_full = (
        0.35 * xva_base_full[:, 0]
        + 0.25 * xva_base_full[:, 1]
        + 0.20 * xva_base_full[:, 2]
    ) / 0.80
    p1_v1 = baseline._metric_record(yva_full, p1_probability_full)  # noqa: SLF001
    p1_v2 = baseline._metric_record(yva, p1_probability_full[keep])  # noqa: SLF001
    for position, seed in enumerate(EXPECTED_MODEL_SEEDS):
        full_row = {"seed": seed, **p1_v1}
        repaired_row = {
            "seed": seed,
            **p1_v2,
            "fit_seconds": 0.0,
            "val_inference_seconds": 0.0,
        }
        arm_seed_metrics_v1_recomputed["fast_score_p1"].append(full_row)
        arm_seed_metrics_v2["fast_score_p1"].append(repaired_row)
        check = _compare_metric_rows(
            f"arm=fast_score_p1 seed={seed}",
            full_row,
            v1["arm_seed_metrics"]["fast_score_p1"][position],
        )
        check.update({"arm": "fast_score_p1", "seed": seed})
        reproduction_checks.append(check)
    print(
        f"[fast_score_p1] v1_auprc={p1_v1['auprc']:.8f} "
        f"v2_auprc={p1_v2['auprc']:.8f}",
        flush=True,
    )

    learned_specs = (
        ("logistic_local6", "logistic", xtr_base, xva_base_full, xva_base),
        (
            "hist_gbdt_local6_p2a",
            "hist_gbdt",
            xtr_base,
            xva_base_full,
            xva_base,
        ),
        (
            "hist_gbdt_context12_p2b",
            "hist_gbdt",
            xtr_context,
            xva_context_full,
            xva_context,
        ),
        (DIAGNOSTIC_ARM, "hist_gbdt", xtr_leaky, xva_leaky_full, xva_leaky),
    )
    for arm, kind, x_train, x_val_full, x_val in learned_specs:
        for position, seed in enumerate(EXPECTED_MODEL_SEEDS):
            estimator, full_metrics = baseline._fit_model(  # noqa: SLF001
                kind, seed, x_train, ytr, x_val_full, yva_full
            )
            started = time.perf_counter()
            probability = estimator.predict_proba(x_val)[:, 1]
            inference_seconds = time.perf_counter() - started
            repaired_metrics = baseline._metric_record(yva, probability)  # noqa: SLF001
            repaired_metrics.update(
                {
                    "fit_seconds": full_metrics["fit_seconds"],
                    "val_inference_seconds": inference_seconds,
                    "warning_count": full_metrics["warning_count"],
                    "warnings": full_metrics["warnings"],
                }
            )
            if "n_iter" in full_metrics:
                repaired_metrics["n_iter"] = full_metrics["n_iter"]
            full_row = {"seed": seed, **full_metrics}
            repaired_row = {"seed": seed, **repaired_metrics}
            arm_seed_metrics_v1_recomputed[arm].append(full_row)
            arm_seed_metrics_v2[arm].append(repaired_row)
            models_by_arm[arm][seed] = estimator
            check = _compare_metric_rows(
                f"arm={arm} seed={seed}",
                full_row,
                v1["arm_seed_metrics"][arm][position],
            )
            check.update({"arm": arm, "seed": seed})
            reproduction_checks.append(check)
            print(
                f"[{arm}] seed={seed} v1_auprc={full_metrics['auprc']:.8f} "
                f"v2_auprc={repaired_metrics['auprc']:.8f} "
                f"v1_f1={full_metrics['f1']:.8f} v2_f1={repaired_metrics['f1']:.8f}",
                flush=True,
            )
            del probability
            gc.collect()

    arm_summaries_v2 = {
        arm: baseline._aggregate(rows)  # noqa: SLF001
        for arm, rows in arm_seed_metrics_v2.items()
    }
    arm_summaries_v1_recomputed = {
        arm: baseline._aggregate(rows)  # noqa: SLF001
        for arm, rows in arm_seed_metrics_v1_recomputed.items()
    }
    champion = max(
        PRIMARY_ORDER,
        key=lambda arm: (
            arm_summaries_v2[arm]["auprc"]["mean"],
            arm_summaries_v2[arm]["f1"]["mean"],
            -PRIMARY_ORDER.index(arm),
        ),
    )

    null_rows_v1_recomputed: list[dict[str, Any]] = []
    null_rows_v2: list[dict[str, Any]] = []
    null_checks: list[dict[str, Any]] = []
    v1_null_rows = v1["controls"]["permutation_null"]["rows"]
    if len(v1_null_rows) != len(baseline.PERMUTATION_SEEDS):
        raise RuntimeError("v1 permutation row count differs from baseline seed count")
    for position, seed in enumerate(baseline.PERMUTATION_SEEDS, 1):
        permuted = np.random.default_rng(seed).permutation(ytr)
        estimator = HistGradientBoostingClassifier(random_state=seed)
        started = time.perf_counter()
        estimator.fit(xtr_context, permuted)
        fit_seconds = time.perf_counter() - started
        started = time.perf_counter()
        full_probability = estimator.predict_proba(xva_context_full)[:, 1]
        full_inference_seconds = time.perf_counter() - started
        full_metrics = baseline._metric_record(yva_full, full_probability)  # noqa: SLF001
        started = time.perf_counter()
        repaired_probability = estimator.predict_proba(xva_context)[:, 1]
        repaired_inference_seconds = time.perf_counter() - started
        repaired_metrics = baseline._metric_record(yva, repaired_probability)  # noqa: SLF001
        full_row = {
            "seed": seed,
            **full_metrics,
            "fit_seconds": fit_seconds,
            "val_inference_seconds": full_inference_seconds,
        }
        repaired_row = {
            "seed": seed,
            **repaired_metrics,
            "fit_seconds": fit_seconds,
            "val_inference_seconds": repaired_inference_seconds,
        }
        null_rows_v1_recomputed.append(full_row)
        null_rows_v2.append(repaired_row)
        check = _compare_metric_rows(
            f"shuffle seed={seed}", full_row, v1_null_rows[position - 1]
        )
        check.update({"seed": seed})
        null_checks.append(check)
        del permuted, estimator, full_probability, repaired_probability
        if position % 8 == 0 or position == len(baseline.PERMUTATION_SEEDS):
            print(
                f"[permutation-null] {position}/{len(baseline.PERMUTATION_SEEDS)} "
                f"v1_auprc={full_metrics['auprc']:.8f} "
                f"v2_auprc={repaired_metrics['auprc']:.8f}",
                flush=True,
            )
        gc.collect()

    permutation_v2 = _permutation_control(
        baseline,
        null_rows_v2,
        arm_summaries_v2["hist_gbdt_context12_p2b"]["auprc"]["mean"],
    )
    permutation_v1_recomputed = _permutation_control(
        baseline,
        null_rows_v1_recomputed,
        arm_summaries_v1_recomputed["hist_gbdt_context12_p2b"]["auprc"]["mean"],
    )

    delta_rows = []
    for arm in ALL_ARMS:
        v1_summary = v1["arm_summaries"][arm]
        v2_summary = arm_summaries_v2[arm]
        delta_rows.append(
            {
                "arm": arm,
                "v1_auprc_mean": v1_summary["auprc"]["mean"],
                "v2_auprc_mean": v2_summary["auprc"]["mean"],
                "auprc_mean_delta_v2_minus_v1": (
                    v2_summary["auprc"]["mean"] - v1_summary["auprc"]["mean"]
                ),
                "v1_f1_mean": v1_summary["f1"]["mean"],
                "v2_f1_mean": v2_summary["f1"]["mean"],
                "f1_mean_delta_v2_minus_v1": (
                    v2_summary["f1"]["mean"] - v1_summary["f1"]["mean"]
                ),
            }
        )
    v1_null = v1["controls"]["permutation_null"]
    null_delta = {
        "v1_auprc_mean": v1_null["auprc"]["mean"],
        "v2_auprc_mean": permutation_v2["auprc"]["mean"],
        "auprc_mean_delta_v2_minus_v1": (
            permutation_v2["auprc"]["mean"] - v1_null["auprc"]["mean"]
        ),
        "v1_f1_mean": v1_null["f1"]["mean"],
        "v2_f1_mean": permutation_v2["f1"]["mean"],
        "f1_mean_delta_v2_minus_v1": (
            permutation_v2["f1"]["mean"] - v1_null["f1"]["mean"]
        ),
    }

    masked = arm_summaries_v2["hist_gbdt_context12_p2b"]
    leaky = arm_summaries_v2[DIAGNOSTIC_ARM]
    leaky_delta = {
        "matched_masked_arm": "hist_gbdt_context12_p2b",
        "diagnostic_arm": DIAGNOSTIC_ARM,
        "auprc_mean_delta": leaky["auprc"]["mean"] - masked["auprc"]["mean"],
        "f1_mean_delta": leaky["f1"]["mean"] - masked["f1"]["mean"],
        "per_seed": [
            {
                "seed": seed,
                "auprc_delta": arm_seed_metrics_v2[DIAGNOSTIC_ARM][position]["auprc"]
                - arm_seed_metrics_v2["hist_gbdt_context12_p2b"][position]["auprc"],
                "f1_delta": arm_seed_metrics_v2[DIAGNOSTIC_ARM][position]["f1"]
                - arm_seed_metrics_v2["hist_gbdt_context12_p2b"][position]["f1"],
            }
            for position, seed in enumerate(EXPECTED_MODEL_SEEDS)
        ],
    }

    return {
        "yva": yva,
        "xva_base": xva_base,
        "xva_context": xva_context,
        "xva_leaky": xva_leaky,
        "arm_seed_metrics_v2": arm_seed_metrics_v2,
        "arm_seed_metrics_v1_recomputed": arm_seed_metrics_v1_recomputed,
        "arm_summaries_v2": arm_summaries_v2,
        "arm_summaries_v1_recomputed": arm_summaries_v1_recomputed,
        "champion": champion,
        "models_by_arm": models_by_arm,
        "reproduction_checks": reproduction_checks,
        "null_checks": null_checks,
        "permutation_v2": permutation_v2,
        "permutation_v1_recomputed": permutation_v1_recomputed,
        "delta_rows": delta_rows,
        "null_delta": null_delta,
        "leaky_delta": leaky_delta,
    }


def _resolve_model_artifact(
    baseline: Any,
    v1: dict[str, Any],
    prepared: dict[str, Any],
    measured: dict[str, Any],
    feature_audit: dict[str, Any],
) -> dict[str, Any]:
    old_champion = v1["bstar"]["arm"]
    champion = measured["champion"]
    comparison_rows: list[dict[str, Any]] = []
    model_changed = champion != old_champion
    old_bundle = joblib.load(V1_MODEL_PATH)
    if old_bundle["bstar_arm"] != old_champion:
        raise RuntimeError("v1 result and model bundle champion differ")
    if not model_changed and champion != "fast_score_p1":
        design = {
            "logistic_local6": prepared["val"]["X"],
            "hist_gbdt_local6_p2a": prepared["val"]["X"],
            "hist_gbdt_context12_p2b": prepared["xva_context_full"],
        }[champion]
        for seed in EXPECTED_MODEL_SEEDS:
            old_probability = old_bundle["models_by_seed"][seed].predict_proba(design)[:, 1]
            new_probability = measured["models_by_arm"][champion][seed].predict_proba(design)[:, 1]
            identical = bool(np.array_equal(old_probability, new_probability))
            maximum_absolute_delta = float(np.max(np.abs(old_probability - new_probability)))
            comparison_rows.append(
                {
                    "seed": seed,
                    "probability_array_equal": int(identical),
                    "maximum_absolute_probability_delta": maximum_absolute_delta,
                }
            )
            model_changed = model_changed or not identical
            del old_probability, new_probability
            gc.collect()
    elif not model_changed:
        comparison_rows = [
            {
                "seed": seed,
                "probability_array_equal": 1,
                "maximum_absolute_probability_delta": 0.0,
            }
            for seed in EXPECTED_MODEL_SEEDS
        ]

    champion_features = {
        "fast_score_p1": baseline.BASE_FEATURE_NAMES[:3],
        "logistic_local6": baseline.BASE_FEATURE_NAMES,
        "hist_gbdt_local6_p2a": baseline.BASE_FEATURE_NAMES,
        "hist_gbdt_context12_p2b": baseline.P2B_FEATURE_NAMES,
    }[champion]
    artifact_type = (
        "deterministic_formula" if champion == "fast_score_p1" else "three_seed_sklearn_bundle"
    )
    if model_changed:
        model_bundle: dict[str, Any] = {
            "schema": "e2.bstar_repair.bstar_model_bundle.v2",
            "created_at": _now_iso(),
            "bstar_arm": champion,
            "model_seeds": list(EXPECTED_MODEL_SEEDS),
            "features": list(champion_features),
            "parent_split_hash": prepared["meta"]["split_hash"],
            "repaired_split_hash": prepared["repaired_split_hash"],
            "feature_allowlist_sha256": feature_audit["allowlist_sha256"],
            "baseline_freeze_py_sha256": _sha256(BASELINE_PY),
            "inference_rule": "report each seed; optional bundle probability is arithmetic mean",
            "artifact_type": artifact_type,
        }
        if champion == "fast_score_p1":
            model_bundle["formula"] = {
                "numerator": "0.35*parallel + 0.25*thickness + 0.20*junction",
                "denominator": 0.80,
            }
        else:
            model_bundle["models_by_seed"] = measured["models_by_arm"][champion]
        _write_joblib(MODEL_V2_PATH, model_bundle)
        artifact_path = MODEL_V2_PATH
    else:
        artifact_path = V1_MODEL_PATH
    artifact_hash = _sha256(artifact_path)
    if not model_changed and artifact_hash != _sha256(V1_MODEL_PATH):
        raise RuntimeError("reused v1 model hash drift")
    return {
        "model_changed": int(model_changed),
        "artifact_path": artifact_path,
        "artifact_sha256": artifact_hash,
        "artifact_type": artifact_type,
        "v1_vs_retrained_prediction_comparison": comparison_rows,
    }


def _selftest_text(result: dict[str, Any], manifest: dict[str, Any]) -> str:
    reproduction = result["selftest"]["v1_reproduction"]
    model = result["bstar"]["model"]
    lines = [
        "SELFTEST_BEGIN",
        f"deterministic_exclusion_repeat_count={result['selftest']['deterministic_exclusion_repeat_count']}",
        f"deterministic_exclusion_mismatch_count={result['selftest']['deterministic_exclusion_mismatch_count']}",
        f"excluded_val_drawing_count={result['repair']['excluded_val_drawing_count']}",
        f"excluded_val_drawing_sha256={result['repair']['deterministic_exclusion_sha256']}",
        f"original_val_drawing_count={result['data']['original_val_drawings']}",
        f"repaired_val_drawing_count={result['data']['repaired_val_drawings']}",
        f"removed_val_row_count={result['data']['removed_val_rows']}",
        f"repaired_val_row_count={result['data']['repaired_val_rows']}",
        f"post_repair_family_collision_count={result['family_audit_v2']['family_collision_count']}",
        f"design_cache_mismatch_count={result['selftest']['design_cache_mismatch_count']}",
        f"v1_arm_metric_comparison_count={reproduction['arm_metric_comparison_count']}",
        f"v1_arm_metric_mismatch_count={reproduction['arm_metric_mismatch_count']}",
        f"v1_arm_metric_max_abs_delta={reproduction['arm_metric_maximum_absolute_float_delta']:.17g}",
        f"v1_shuffle_metric_comparison_count={reproduction['shuffle_metric_comparison_count']}",
        f"v1_shuffle_metric_mismatch_count={reproduction['shuffle_metric_mismatch_count']}",
        f"v1_shuffle_metric_max_abs_delta={reproduction['shuffle_metric_maximum_absolute_float_delta']:.17g}",
        f"manifest_content_hash_match={int(manifest['content_hash'] == _canonical_hash(manifest['frozen']))}",
        f"model_artifact_hash_match={int(model['artifact_sha256'] == _sha256(Path(model['artifact_path'])))}",
        f"peak_rss_under_48gib={int(result['run']['peak_rss_bytes_sampled'] < RAM_LIMIT_BYTES)}",
        f"test_split_reads={result['run']['test_split_reads']}",
        f"subagents_used={result['run']['subagents_used']}",
        "SELFTEST_END",
    ]
    return "\n".join(lines)


def _full_selftest_output(
    core_text: str,
    structural_mismatch_count: int,
    recorded_output_mismatch_count: int,
    total_mismatch_count: int,
) -> str:
    return "\n".join(
        (
            core_text,
            f"structural_mismatch_count={structural_mismatch_count}",
            f"recorded_selftest_output_mismatch_count={recorded_output_mismatch_count}",
            f"selftest_mismatch_count={total_mismatch_count}",
        )
    )


def _render_report(
    result: dict[str, Any], manifest: dict[str, Any], artifact_hashes: dict[str, str]
) -> str:
    lines = [
        "# B* Geometry-Family Repair — Numeric Remeasurement",
        "",
        f"- Completed: {result['run']['completed_at']}",
        f"- Rows: train {result['data']['train_rows']:,}; val v1 {result['data']['original_val_rows']:,}; val v2 {result['data']['repaired_val_rows']:,}",
        f"- Drawings: train {result['data']['train_drawings']:,}; val v1 {result['data']['original_val_drawings']}; val v2 {result['data']['repaired_val_drawings']}",
        f"- Removed val rows: {result['data']['removed_val_rows']:,}",
        f"- Test-split reads: {result['run']['test_split_reads']}",
        f"- Peak sampled RSS: {result['run']['peak_rss_gib']:.3f} GiB",
        "",
        "## Family measurements",
        "",
        f"- v1 family collision count: {result['family_audit_v1']['family_collision_count']}",
        f"- v2 family collision count: {result['family_audit_v2']['family_collision_count']}",
        f"- v2 geometry-family collision count: {result['family_audit_v2']['geometry_family_collision_count']}",
        f"- v2 drawing-ID collision count: {result['family_audit_v2']['drawing_id_collision_count']}",
        "",
        "## Arm deltas (three-seed mean)",
        "",
        "| Arm | AUPRC v1 | AUPRC v2 | Δ v2-v1 | F1 v1 | F1 v2 | Δ v2-v1 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["delta_table"]:
        lines.append(
            f"| {row['arm']} | {row['v1_auprc_mean']:.10f} | "
            f"{row['v2_auprc_mean']:.10f} | "
            f"{row['auprc_mean_delta_v2_minus_v1']:+.10f} | "
            f"{row['v1_f1_mean']:.10f} | {row['v2_f1_mean']:.10f} | "
            f"{row['f1_mean_delta_v2_minus_v1']:+.10f} |"
        )
    null = result["controls"]["permutation_null_delta"]
    lines.extend(
        [
            "",
            "## Shuffle null (64 seeds)",
            "",
            "| Measure | v1 | v2 | Δ v2-v1 |",
            "|---|---:|---:|---:|",
            f"| Mean AUPRC | {null['v1_auprc_mean']:.10f} | {null['v2_auprc_mean']:.10f} | {null['auprc_mean_delta_v2_minus_v1']:+.10f} |",
            f"| Mean F1 | {null['v1_f1_mean']:.10f} | {null['v2_f1_mean']:.10f} | {null['f1_mean_delta_v2_minus_v1']:+.10f} |",
            "",
            "## B* reassignment",
            "",
            f"- v1 arm: `{result['bstar']['v1_arm']}`",
            f"- v2 arm: `{result['bstar']['arm']}`",
            f"- v2 mean val AUPRC: {result['bstar']['auprc_mean']:.10f}",
            f"- v2 mean val F1@0.5: {result['bstar']['f1_mean']:.10f}",
            f"- Model changed: {result['bstar']['model']['model_changed']}",
            f"- Model artifact SHA-256: `{result['bstar']['model']['artifact_sha256']}`",
            f"- Repaired split hash: `{result['repaired_split_hash']}`",
            f"- Manifest content hash: `{manifest['content_hash']}`",
            "",
            "## Excluded val drawings",
            "",
        ]
    )
    for record in result["repair"]["excluded_records"]:
        lines.append(
            f"- `{record['drawing_id']}`: gid {record['gid']}; rows {record['row_count']}; family `{record['family_fingerprint']}`"
        )
    lines.extend(["", "## Selftest", "", "```text"])
    lines.extend(result["selftest"]["output"].splitlines())
    lines.extend(["```", "", "## Artifact hashes", ""])
    for name, digest in artifact_hashes.items():
        lines.append(f"- {name}: `{digest}`")
    lines.extend(["", "## Unresolved", "", "- Count: 0", "", "CELL_COMPLETE: bstar_repair"])
    return "\n".join(lines) + "\n"


def _build_result(
    baseline: Any,
    v1: dict[str, Any],
    source_hashes: dict[str, str],
    exclusion: dict[str, Any],
    prepared: dict[str, Any],
    measured: dict[str, Any],
    model_info: dict[str, Any],
    peak_bytes: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    feature_audit = baseline._feature_audit()  # noqa: SLF001
    if feature_audit["primary_identifier_or_name_feature_count"] != 0:
        raise RuntimeError("primary feature allowlist contains identifier/name features")
    arm_mismatches = sum(row["mismatch_count"] for row in measured["reproduction_checks"])
    null_mismatches = sum(row["mismatch_count"] for row in measured["null_checks"])
    arm_max_delta = max(
        (row["maximum_absolute_float_delta"] for row in measured["reproduction_checks"]),
        default=0.0,
    )
    null_max_delta = max(
        (row["maximum_absolute_float_delta"] for row in measured["null_checks"]),
        default=0.0,
    )
    if arm_mismatches or null_mismatches:
        raise RuntimeError(
            f"v1 numeric reproduction mismatch: arms={arm_mismatches} shuffle={null_mismatches}"
        )
    if peak_bytes >= RAM_LIMIT_BYTES:
        raise RuntimeError(f"sampled peak RSS reached packet ceiling: {peak_bytes}")

    champion = measured["champion"]
    champion_summary = measured["arm_summaries_v2"][champion]
    frozen_content = {
        "bstar": {
            "arm": champion,
            "selection_rule": "maximum three-seed mean val AUPRC; tie mean F1; tie preregistered arm order",
            "auprc_mean": champion_summary["auprc"]["mean"],
            "auprc_std_population": champion_summary["auprc"]["std_population"],
            "f1_mean": champion_summary["f1"]["mean"],
            "f1_std_population": champion_summary["f1"]["std_population"],
        },
        "model_artifact": {
            "path": str(model_info["artifact_path"]),
            "sha256": model_info["artifact_sha256"],
            "type": model_info["artifact_type"],
            "model_changed": model_info["model_changed"],
        },
        "repair": {
            "rule": exclusion["rule"],
            "deterministic_exclusion_sha256": exclusion["deterministic_sha256"],
            "excluded_val_drawing_ids": exclusion["excluded_val_drawing_ids"],
            "parent_split_hash": prepared["meta"]["split_hash"],
            "repaired_split_hash": prepared["repaired_split_hash"],
            "post_repair_family_collision_count": prepared["repaired_family_audit"][
                "family_collision_count"
            ],
        },
        "feature_allowlist": feature_audit,
        "model_seeds": list(EXPECTED_MODEL_SEEDS),
        "permutation_seed_list": list(baseline.PERMUTATION_SEEDS),
        "permutation_seed_list_sha256": _canonical_hash(list(baseline.PERMUTATION_SEEDS)),
        "input_hashes": {
            **source_hashes,
            **{
                f"baseline_input_{key}": value
                for key, value in prepared["meta"]["preflight"]["input_hashes"].items()
            },
        },
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scikit_learn": __import__("sklearn").__version__,
            "joblib": joblib.__version__,
        },
    }
    manifest = {
        "schema": "e2.bstar_repair.bstar_manifest.v2",
        "created_at": _now_iso(),
        "frozen": frozen_content,
        "content_hash": _canonical_hash(frozen_content),
    }

    exclusion_repeat = _determine_exclusions(v1)
    result: dict[str, Any] = {
        "schema": "e2.bstar_repair.results.v2",
        "run": {
            "completed_at": _now_iso(),
            "allowed_splits": ["train", "val"],
            "test_split_reads": 0,
            "subagents_used": 0,
            "model_seeds": list(EXPECTED_MODEL_SEEDS),
            "permutation_seed_count": len(baseline.PERMUTATION_SEEDS),
            "peak_rss_bytes_sampled": int(peak_bytes),
            "peak_rss_gib": peak_bytes / (1024**3),
            "ram_limit_gib": 48,
        },
        "data": {
            "truth_namespace": v1["data"]["truth_namespace"],
            "train_rows": int(len(prepared["train"]["y"])),
            "original_val_rows": int(len(prepared["val"]["y"])),
            "repaired_val_rows": int(np.sum(prepared["row_keep"])),
            "removed_val_rows": prepared["removed_rows"],
            "train_drawings": len(prepared["meta"]["splits"]["train"]["drawing_records"]),
            "original_val_drawings": len(prepared["meta"]["splits"]["val"]["drawing_records"]),
            "repaired_val_drawings": len(prepared["remaining_records"]),
            "train_wall_fraction": float(np.mean(prepared["train"]["y"])),
            "original_val_wall_fraction": float(np.mean(prepared["val"]["y"])),
            "repaired_val_wall_fraction": float(np.mean(measured["yva"])),
            "scale_mm_per_px": float(prepared["meta"]["scale_mm_per_px"]),
            "selected_context_radius_px": float(
                prepared["meta"]["selected_context_radius_px"]
            ),
            "shared_exclusion_contract": prepared["meta"]["exclusion_contract"],
        },
        "parent_split_hash": prepared["meta"]["split_hash"],
        "repaired_split_hash": prepared["repaired_split_hash"],
        "repair": {
            "rule": exclusion["rule"],
            "deterministic_exclusion_sha256": exclusion["deterministic_sha256"],
            "excluded_val_drawing_count": len(exclusion["excluded_val_drawing_ids"]),
            "excluded_val_drawing_ids": exclusion["excluded_val_drawing_ids"],
            "excluded_records": prepared["excluded_records"],
            "mappings": exclusion["mappings"],
        },
        "primary_arm_order": list(PRIMARY_ORDER),
        "diagnostic_arm": DIAGNOSTIC_ARM,
        "arm_seed_metrics": measured["arm_seed_metrics_v2"],
        "arm_summaries": measured["arm_summaries_v2"],
        "delta_table": measured["delta_rows"],
        "bstar": {
            "v1_arm": v1["bstar"]["arm"],
            "arm": champion,
            "auprc_mean": champion_summary["auprc"]["mean"],
            "f1_mean": champion_summary["f1"]["mean"],
            "manifest_content_hash": manifest["content_hash"],
            "model": {
                "model_changed": model_info["model_changed"],
                "artifact_path": str(model_info["artifact_path"]),
                "artifact_sha256": model_info["artifact_sha256"],
                "artifact_type": model_info["artifact_type"],
                "v1_vs_retrained_prediction_comparison": model_info[
                    "v1_vs_retrained_prediction_comparison"
                ],
            },
        },
        "feature_audit": feature_audit,
        "family_audit_v1": v1["family_audit"],
        "family_audit_v2": prepared["repaired_family_audit"],
        "controls": {
            "leaky_vs_masked_delta": measured["leaky_delta"],
            "permutation_null": measured["permutation_v2"],
            "permutation_null_delta": measured["null_delta"],
        },
        "input_hashes": frozen_content["input_hashes"],
        "selftest": {
            "deterministic_exclusion_repeat_count": 2,
            "deterministic_exclusion_mismatch_count": int(
                exclusion_repeat != exclusion
            ),
            "design_cache_mismatch_count": prepared["design_cache_mismatch_count"],
            "v1_reproduction": {
                "source_results_sha256": source_hashes["results_v1"],
                "arm_metric_comparison_count": len(measured["reproduction_checks"]),
                "arm_metric_mismatch_count": arm_mismatches,
                "arm_metric_maximum_absolute_float_delta": arm_max_delta,
                "shuffle_metric_comparison_count": len(measured["null_checks"]),
                "shuffle_metric_mismatch_count": null_mismatches,
                "shuffle_metric_maximum_absolute_float_delta": null_max_delta,
                "arm_checks": measured["reproduction_checks"],
                "shuffle_checks": measured["null_checks"],
                "arm_seed_metrics_recomputed": measured[
                    "arm_seed_metrics_v1_recomputed"
                ],
                "arm_summaries_recomputed": measured[
                    "arm_summaries_v1_recomputed"
                ],
                "permutation_null_recomputed": measured[
                    "permutation_v1_recomputed"
                ],
            },
        },
    }
    result["selftest"]["output"] = _full_selftest_output(
        _selftest_text(result, manifest), 0, 0, 0
    )
    return result, manifest


def run_measurement() -> int:
    CELL_DIR.mkdir(parents=True, exist_ok=True)
    baseline = _load_baseline()
    source_hashes = _required_sources()
    v1 = _load_json(V1_RESULTS_PATH)
    exclusion = _determine_exclusions(v1)
    sampler = baseline.PeakMemorySampler()
    sampler.start()
    try:
        prepared = _prepare_data(baseline, v1, exclusion)
        print(
            f"repair rows: val_v1={len(prepared['val']['y'])} "
            f"removed={prepared['removed_rows']} val_v2={int(np.sum(prepared['row_keep']))}",
            flush=True,
        )
        print(
            f"repair drawings: val_v1={len(prepared['meta']['splits']['val']['drawing_records'])} "
            f"val_v2={len(prepared['remaining_records'])} "
            f"family_collisions_v2={prepared['repaired_family_audit']['family_collision_count']}",
            flush=True,
        )
        measured = _measure(baseline, v1, prepared)
        feature_audit = baseline._feature_audit()  # noqa: SLF001
        model_info = _resolve_model_artifact(
            baseline, v1, prepared, measured, feature_audit
        )
    finally:
        peak_bytes = sampler.stop()

    result, manifest = _build_result(
        baseline,
        v1,
        source_hashes,
        exclusion,
        prepared,
        measured,
        model_info,
        peak_bytes,
    )
    _write_json(MANIFEST_V2_PATH, manifest)
    _write_json(RESULTS_V2_PATH, result)
    artifact_hashes = {
        "bstar_repair.py": _sha256(Path(__file__).resolve()),
        "results_v2.json": _sha256(RESULTS_V2_PATH),
        "bstar_manifest_v2.json": _sha256(MANIFEST_V2_PATH),
        Path(model_info["artifact_path"]).name: model_info["artifact_sha256"],
        "results_v1.json": source_hashes["results_v1"],
        "bstar_model_v1.joblib": source_hashes["model_v1"],
    }
    _write_text(REPORT_PATH, _render_report(result, manifest, artifact_hashes))
    print(result["selftest"]["output"], flush=True)
    print(
        f"measurement_complete bstar={result['bstar']['arm']} "
        f"auprc={result['bstar']['auprc_mean']:.10f} "
        f"family_collisions={result['family_audit_v2']['family_collision_count']} "
        f"manifest_content_hash={manifest['content_hash']}",
        flush=True,
    )
    return 0


def _validate_recorded_reproduction(
    result: dict[str, Any], v1: dict[str, Any]
) -> tuple[int, int, float, float]:
    reproduction = result["selftest"]["v1_reproduction"]
    arm_mismatches = 0
    arm_max_delta = 0.0
    for arm in ALL_ARMS:
        actual_rows = reproduction["arm_seed_metrics_recomputed"][arm]
        expected_rows = v1["arm_seed_metrics"][arm]
        if len(actual_rows) != len(expected_rows):
            arm_mismatches += abs(len(actual_rows) - len(expected_rows)) + 1
            continue
        for actual, expected in zip(actual_rows, expected_rows, strict=True):
            check = _compare_metric_rows(f"arm={arm}", actual, expected)
            arm_mismatches += check["mismatch_count"]
            arm_max_delta = max(
                arm_max_delta, check["maximum_absolute_float_delta"]
            )
    null_mismatches = 0
    null_max_delta = 0.0
    actual_null = reproduction["permutation_null_recomputed"]["rows"]
    expected_null = v1["controls"]["permutation_null"]["rows"]
    if len(actual_null) != len(expected_null):
        null_mismatches += abs(len(actual_null) - len(expected_null)) + 1
    else:
        for actual, expected in zip(actual_null, expected_null, strict=True):
            check = _compare_metric_rows("shuffle", actual, expected)
            null_mismatches += check["mismatch_count"]
            null_max_delta = max(
                null_max_delta, check["maximum_absolute_float_delta"]
            )
    return arm_mismatches, null_mismatches, arm_max_delta, null_max_delta


def run_selftest() -> int:
    required = (RESULTS_V2_PATH, MANIFEST_V2_PATH, REPORT_PATH)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing v2 outputs for selftest: {missing}")
    baseline = _load_baseline()
    v1 = _load_json(V1_RESULTS_PATH)
    result = _load_json(RESULTS_V2_PATH)
    manifest = _load_json(MANIFEST_V2_PATH)
    first = _determine_exclusions(v1)
    second = _determine_exclusions(v1)
    prepared = _prepare_data(baseline, v1, first)
    arm_mismatches, null_mismatches, arm_max_delta, null_max_delta = (
        _validate_recorded_reproduction(result, v1)
    )
    result["selftest"]["deterministic_exclusion_repeat_count"] = 2
    result["selftest"]["deterministic_exclusion_mismatch_count"] = int(first != second)
    result["selftest"]["design_cache_mismatch_count"] = prepared[
        "design_cache_mismatch_count"
    ]
    reproduction = result["selftest"]["v1_reproduction"]
    reproduction["arm_metric_mismatch_count"] = arm_mismatches
    reproduction["arm_metric_maximum_absolute_float_delta"] = arm_max_delta
    reproduction["shuffle_metric_mismatch_count"] = null_mismatches
    reproduction["shuffle_metric_maximum_absolute_float_delta"] = null_max_delta

    structural_mismatches = 0
    structural_mismatches += int(first["deterministic_sha256"] != result["repair"]["deterministic_exclusion_sha256"])
    structural_mismatches += int(
        prepared["repaired_split_hash"] != result["repaired_split_hash"]
    )
    structural_mismatches += int(
        _canonical_hash(prepared["repaired_family_audit"])
        != _canonical_hash(result["family_audit_v2"])
    )
    structural_mismatches += int(
        manifest["content_hash"] != _canonical_hash(manifest["frozen"])
    )
    structural_mismatches += int(
        result["bstar"]["manifest_content_hash"] != manifest["content_hash"]
    )
    model_path = Path(result["bstar"]["model"]["artifact_path"])
    structural_mismatches += int(not model_path.is_file())
    if model_path.is_file():
        structural_mismatches += int(
            _sha256(model_path) != result["bstar"]["model"]["artifact_sha256"]
        )
    structural_mismatches += int(
        REPORT_PATH.read_text(encoding="utf-8").splitlines()[-1]
        != "CELL_COMPLETE: bstar_repair"
    )
    core_text = _selftest_text(result, manifest)
    expected_text = result["selftest"]["output"]
    base_total = (
        structural_mismatches
        + arm_mismatches
        + null_mismatches
        + int(first != second)
        + int(prepared["repaired_family_audit"]["family_collision_count"] != 0)
        + int(result["run"]["peak_rss_bytes_sampled"] >= RAM_LIMIT_BYTES)
        + int(result["run"]["test_split_reads"] != 0)
        + int(result["run"]["subagents_used"] != 0)
    )
    provisional_output = _full_selftest_output(
        core_text, structural_mismatches, 0, base_total
    )
    output_mismatch = int(provisional_output != expected_text)
    total = base_total + output_mismatch
    print(
        _full_selftest_output(
            core_text, structural_mismatches, output_mismatch, total
        ),
        flush=True,
    )
    return int(total != 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="validate deterministic repair, zero collisions, and recorded v1 reproduction",
    )
    args = parser.parse_args(argv)
    return run_selftest() if args.selftest else run_measurement()


if __name__ == "__main__":
    raise SystemExit(main())
