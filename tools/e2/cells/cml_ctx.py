#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CML context-feature validation cell (CPU only, train -> val, never test).

The six frozen CubiCasa features are reused from the existing train/val NPZ
matrices.  Every added context feature is recomputed directly from drawing IR.
The only accepted split names are the literal strings ``train`` and ``val``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.spatial import cKDTree


CELL_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(r"D:\dev\99_tools\autocad-sdk-router")
IR_ROOT = REPO_ROOT / "runs" / "e2_ext_cubicasa" / "ir"
BASE_FEATURE_DIR = REPO_ROOT / "runs" / "e2_ext_cubicasa" / "features"
WORK_DIR = CELL_DIR / "_work"
RESULTS_PATH = CELL_DIR / "results.json"
REPORT_PATH = CELL_DIR / "REPORT.md"

SEED = 7
SCALE_MM_PER_PX = 12.0
RADII_PX = (20.0, 40.0, 80.0)
ANGLE_BINS = 12
ALLOWED_SPLITS = frozenset(("train", "val"))

BASE_FEATURE_NAMES = (
    "parallel",
    "thickness",
    "junction",
    "log10_len",
    "sin2t",
    "cos2t",
)
COMMON_CONTEXT_FEATURE_NAMES = (
    "parallel_band_neighbor_count",
    "nearest_parallel_gap_px",
    "junction_degree",
    "drawing_length_percentile",
)

sys.path.insert(0, str(REPO_ROOT / "tools" / "e2"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "e2" / "ext"))
import cubicasa_eval as ce  # noqa: E402
import w1_real_defs  # noqa: E402


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _split_files(split: str) -> list[Path]:
    if split not in ALLOWED_SPLITS:
        raise ValueError(f"forbidden split: {split!r}; only train/val are allowed")
    directory = IR_ROOT / split
    if directory.name != split or directory.parent != IR_ROOT:
        raise RuntimeError("split path safety check failed")
    files = sorted(directory.glob("*.segir.json"))
    if not files:
        raise FileNotFoundError(f"no SEG-IR files under allowed split {directory}")
    return files


def _load_base(split: str) -> dict[str, np.ndarray]:
    if split not in ALLOWED_SPLITS:
        raise ValueError(f"forbidden split: {split!r}")
    path = BASE_FEATURE_DIR / f"{split}.npz"
    with np.load(path) as z:
        return {
            "X": np.asarray(z["X"], dtype=np.float32),
            "y": np.asarray(z["y"], dtype=np.int8),
            "gid": np.asarray(z["gid"], dtype=np.int32),
            "scale": np.asarray(z["scale"]),
        }


def _geometry(ir: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, int]:
    """Return first valid segment geometry per handle in insertion order."""
    seen: set[str] = set()
    p1: list[tuple[float, float]] = []
    p2: list[tuple[float, float]] = []
    valid_records = 0
    for seg in ir.get("segments", []) or []:
        pts = seg.get("pts") or []
        if len(pts) < 2:
            continue
        a = (float(pts[0][0]), float(pts[0][1]))
        b = (float(pts[-1][0]), float(pts[-1][1]))
        if math.hypot(b[0] - a[0], b[1] - a[1]) == 0.0:
            continue
        valid_records += 1
        handle = str(seg.get("handle") or seg.get("sid"))
        if handle in seen:
            continue
        seen.add(handle)
        p1.append(a)
        p2.append(b)
    return (
        np.asarray(p1, dtype=np.float64).reshape((-1, 2)),
        np.asarray(p2, dtype=np.float64).reshape((-1, 2)),
        valid_records - len(p1),
    )


def _parallel_context(
    p1: np.ndarray,
    p2: np.ndarray,
    lengths: np.ndarray,
    units: np.ndarray,
    angles: np.ndarray,
    mid: np.ndarray,
    params: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    """Count banded parallel neighbors and find strict nearest parallel gap."""
    n = len(lengths)
    counts = np.zeros(n, dtype=np.float64)
    nearest = np.full(n, np.inf, dtype=np.float64)
    lo, hi = params["_band_units"]
    angle_tol = float(params["angle_tol_deg"])
    overlap_min = float(params["overlap_min"])
    bi, bj = 192, 8192

    for i0 in range(0, n, bi):
        i1 = min(i0 + bi, n)
        iu = units[i0:i1]
        il = lengths[i0:i1]
        ip1 = p1[i0:i1]
        local_count = np.zeros(i1 - i0, dtype=np.float64)
        local_nearest = np.full(i1 - i0, np.inf, dtype=np.float64)
        for j0 in range(0, n, bj):
            j1 = min(j0 + bj, n)
            selfmask = np.arange(i0, i1)[:, None] == np.arange(j0, j1)[None, :]
            adiff = np.abs(angles[i0:i1, None] - angles[None, j0:j1])
            adiff = np.minimum(adiff, 180.0 - adiff)

            dx1 = p1[j0:j1, 0][None, :] - ip1[:, 0][:, None]
            dy1 = p1[j0:j1, 1][None, :] - ip1[:, 1][:, None]
            dx2 = p2[j0:j1, 0][None, :] - ip1[:, 0][:, None]
            dy2 = p2[j0:j1, 1][None, :] - ip1[:, 1][:, None]
            ta = dx1 * iu[:, 0][:, None] + dy1 * iu[:, 1][:, None]
            tb = dx2 * iu[:, 0][:, None] + dy2 * iu[:, 1][:, None]
            tlo = np.minimum(ta, tb)
            thi = np.maximum(ta, tb)
            overlap_len = np.maximum(
                np.minimum(il[:, None], thi) - np.maximum(0.0, tlo), 0.0
            )
            overlap = overlap_len / np.minimum(
                il[:, None], lengths[j0:j1][None, :]
            )
            mx = mid[j0:j1, 0][None, :] - ip1[:, 0][:, None]
            my = mid[j0:j1, 1][None, :] - ip1[:, 1][:, None]
            gap = np.abs(mx * (-iu[:, 1][:, None]) + my * iu[:, 0][:, None])

            valid = (adiff <= angle_tol) & (overlap >= overlap_min) & ~selfmask
            local_count += (valid & (gap >= lo) & (gap <= hi)).sum(axis=1)
            block_min = np.where(valid, gap, np.inf).min(axis=1)
            local_nearest = np.minimum(local_nearest, block_min)
        counts[i0:i1] = local_count
        nearest[i0:i1] = local_nearest

    nearest[~np.isfinite(nearest)] = np.nan
    return counts, nearest


def _radius_context(
    mid: np.ndarray, angles: np.ndarray
) -> dict[float, tuple[np.ndarray, np.ndarray]]:
    """Density and normalized neighbor-angle histogram entropy at each radius."""
    n = len(mid)
    tree = cKDTree(mid)
    pairs = tree.query_pairs(max(RADII_PX), output_type="ndarray")
    if pairs.size:
        pairs = np.asarray(pairs, dtype=np.int64).reshape((-1, 2))
        diffs = mid[pairs[:, 0]] - mid[pairs[:, 1]]
        pair_d2 = np.einsum("ij,ij->i", diffs, diffs)
    else:
        pairs = np.empty((0, 2), dtype=np.int64)
        pair_d2 = np.empty(0, dtype=np.float64)
    angle_bin = np.minimum(
        (angles / (180.0 / ANGLE_BINS)).astype(np.int64), ANGLE_BINS - 1
    )
    out: dict[float, tuple[np.ndarray, np.ndarray]] = {}
    for radius in RADII_PX:
        chosen = pairs[pair_d2 <= radius * radius]
        if len(chosen):
            left, right = chosen[:, 0], chosen[:, 1]
            degree = np.bincount(
                np.concatenate((left, right)), minlength=n
            ).astype(np.float64)
            keys = np.concatenate(
                (
                    left * ANGLE_BINS + angle_bin[right],
                    right * ANGLE_BINS + angle_bin[left],
                )
            )
            hist = np.bincount(keys, minlength=n * ANGLE_BINS).reshape(
                n, ANGLE_BINS
            )
        else:
            degree = np.zeros(n, dtype=np.float64)
            hist = np.zeros((n, ANGLE_BINS), dtype=np.int64)
        density = degree / (math.pi * radius * radius)
        entropy = np.zeros(n, dtype=np.float64)
        nonzero = degree > 0
        if np.any(nonzero):
            probs = hist[nonzero] / degree[nonzero, None]
            with np.errstate(divide="ignore", invalid="ignore"):
                terms = np.where(probs > 0, probs * np.log(probs), 0.0)
            entropy[nonzero] = -terms.sum(axis=1) / math.log(ANGLE_BINS)
        out[radius] = density, entropy
    return out


def drawing_context(ir: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    p1, p2, duplicate_valid_handles = _geometry(ir)
    n = len(p1)
    if n == 0:
        return np.empty((0, 10), dtype=np.float32), {
            "duplicates": duplicate_valid_handles,
            "n": 0,
        }
    delta = p2 - p1
    lengths = np.hypot(delta[:, 0], delta[:, 1])
    units = delta / lengths[:, None]
    angles = np.degrees(np.arctan2(delta[:, 1], delta[:, 0])) % 180.0
    mid = (p1 + p2) / 2.0
    params = w1_real_defs.evidence_grid._resolve_params(
        ir, ce._params(SCALE_MM_PER_PX)
    )

    parallel_count, nearest_gap = _parallel_context(
        p1, p2, lengths, units, angles, mid, params
    )
    # The exact vectorized detector core exposes the uncapped junction count;
    # the frozen base feature stores only min(1, degree/2).
    _best_ov, _tb_flag, _tb_off, junction_degree = w1_real_defs._fast_core(
        p1, p2, delta, lengths, units, angles, mid, params, 0, n
    )
    length_percentile = np.searchsorted(
        np.sort(lengths), lengths, side="right"
    ).astype(np.float64) / n
    radial = _radius_context(mid, angles)

    columns: list[np.ndarray] = [
        parallel_count,
        nearest_gap,
        junction_degree.astype(np.float64),
        length_percentile,
    ]
    for radius in RADII_PX:
        columns.extend(radial[radius])
    matrix = np.column_stack(columns).astype(np.float32, copy=False)
    return matrix, {
        "duplicates": duplicate_valid_handles,
        "n": n,
        "params": {
            "angle_tol_deg": float(params["angle_tol_deg"]),
            "overlap_min": float(params["overlap_min"]),
            "parallel_band_px": [float(x) for x in params["_band_units"]],
            "snap_tol_px": float(params["snap_tol"]),
        },
    }


def _context_names_all() -> list[str]:
    names = list(COMMON_CONTEXT_FEATURE_NAMES)
    for radius in RADII_PX:
        tag = int(radius)
        names.extend((f"radius_density_r{tag}_per_px2", f"neighbor_angle_entropy_r{tag}"))
    return names


def benchmark(base_train: dict[str, np.ndarray], n_drawings: int = 24) -> dict[str, Any]:
    files = _split_files("train")
    gids = base_train["gid"]
    expected_by_gid = np.bincount(gids, minlength=len(files))
    take = min(n_drawings, len(files))
    indices = np.unique(np.linspace(0, len(files) - 1, take, dtype=int))
    rows = 0
    started = time.perf_counter()
    counts = []
    for gi in indices:
        ir = json.loads(files[int(gi)].read_text(encoding="utf-8"))
        matrix, _meta = drawing_context(ir)
        expected = int(expected_by_gid[int(gi)])
        if len(matrix) != expected:
            raise RuntimeError(
                f"benchmark alignment mismatch gid={gi}: IR {len(matrix)} != base {expected}"
            )
        rows += len(matrix)
        counts.append(len(matrix))
    seconds = time.perf_counter() - started
    rate = rows / seconds if seconds else float("inf")
    projected = len(base_train["y"]) / rate
    return {
        "split": "train",
        "sample_drawings": int(len(indices)),
        "sample_rows": int(rows),
        "seconds": round(seconds, 6),
        "rows_per_second": round(rate, 2),
        "sample_rows_per_drawing": {
            "min": int(min(counts)),
            "median": float(np.median(counts)),
            "max": int(max(counts)),
        },
        "projected_train_seconds": round(projected, 2),
        "projected_train_hours": round(projected / 3600.0, 4),
        "projection_basis": "linear extrapolation from drawing-spread train sample",
    }


def extract_split(split: str, base: dict[str, np.ndarray]) -> tuple[np.memmap, dict[str, Any]]:
    files = _split_files(split)
    gid = base["gid"]
    if len(gid) != len(base["y"]):
        raise RuntimeError(f"{split}: gid/y length mismatch")
    if int(gid.min()) != 0 or int(gid.max()) + 1 != len(files):
        raise RuntimeError(f"{split}: drawing gid coverage does not match allowed IR files")
    expected_by_gid = np.bincount(gid, minlength=len(files))
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = WORK_DIR / f"context_{split}.npy"
    target = np.lib.format.open_memmap(
        cache_path,
        mode="w+",
        dtype=np.float32,
        shape=(len(base["y"]), len(_context_names_all())),
    )
    offset = 0
    duplicate_count = 0
    drawing_counts: list[int] = []
    params_seen: dict[str, Any] | None = None
    started = time.perf_counter()
    for gi, path in enumerate(files):
        ir = json.loads(path.read_text(encoding="utf-8"))
        matrix, meta = drawing_context(ir)
        expected = int(expected_by_gid[gi])
        if len(matrix) != expected:
            raise RuntimeError(
                f"{split}: row alignment mismatch {path.name}: IR {len(matrix)} != base {expected}"
            )
        target[offset : offset + expected] = matrix
        offset += expected
        duplicate_count += int(meta["duplicates"])
        drawing_counts.append(expected)
        if params_seen is None and meta.get("params"):
            params_seen = meta["params"]
        if (gi + 1) % 200 == 0 or gi + 1 == len(files):
            elapsed = time.perf_counter() - started
            print(
                f"[{split}] {gi + 1}/{len(files)} drawings, "
                f"{offset:,} rows, {offset / max(elapsed, 1e-9):,.0f} rows/s",
                flush=True,
            )
    target.flush()
    seconds = time.perf_counter() - started
    if offset != len(base["y"]):
        raise RuntimeError(f"{split}: final context/base row count mismatch")
    stats = {
        "split": split,
        "drawings": len(files),
        "rows": int(offset),
        "seconds": round(seconds, 6),
        "rows_per_second": round(offset / seconds, 2),
        "duplicate_valid_handle_records": int(duplicate_count),
        "rows_per_drawing": {
            "min": int(np.min(drawing_counts)),
            "p50": float(np.percentile(drawing_counts, 50)),
            "p95": float(np.percentile(drawing_counts, 95)),
            "max": int(np.max(drawing_counts)),
        },
        "resolved_geometry_params": params_seen,
        "alignment_check": "PASS",
    }
    return target, stats


def _prf_auc(y: np.ndarray, probability: np.ndarray) -> dict[str, Any]:
    from sklearn.metrics import roc_auc_score

    prediction = probability >= 0.5
    positive = y == 1
    tp = int(np.sum(prediction & positive))
    fp = int(np.sum(prediction & ~positive))
    fn = int(np.sum(~prediction & positive))
    tn = int(np.sum(~prediction & ~positive))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "threshold": 0.5,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": round(float(precision), 6),
        "recall": round(float(recall), 6),
        "f1": round(float(f1), 6),
        "roc_auc": round(float(roc_auc_score(y, probability)), 6),
    }


def _selected_context_indices(radius: float) -> list[int]:
    radius_position = RADII_PX.index(radius)
    start = len(COMMON_CONTEXT_FEATURE_NAMES) + radius_position * 2
    return [0, 1, 2, 3, start, start + 1]


def _assemble(
    base_x: np.ndarray, context_x: np.ndarray, radius: float
) -> tuple[np.ndarray, list[str]]:
    indices = _selected_context_indices(radius)
    out = np.empty(
        (len(base_x), len(BASE_FEATURE_NAMES) + len(indices)), dtype=np.float32
    )
    out[:, : len(BASE_FEATURE_NAMES)] = base_x
    out[:, len(BASE_FEATURE_NAMES) :] = context_x[:, indices]
    names = list(BASE_FEATURE_NAMES) + [_context_names_all()[i] for i in indices]
    return out, names


def _fit_and_score(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    *,
    shuffled: bool = False,
) -> tuple[Any, dict[str, Any]]:
    from sklearn.ensemble import HistGradientBoostingClassifier

    labels = y_train
    if shuffled:
        labels = np.random.default_rng(SEED).permutation(y_train)
    model = HistGradientBoostingClassifier(random_state=SEED)
    t0 = time.perf_counter()
    model.fit(x_train, labels)
    fit_seconds = time.perf_counter() - t0
    t1 = time.perf_counter()
    probability = model.predict_proba(x_val)[:, 1]
    inference_seconds = time.perf_counter() - t1
    metrics = _prf_auc(y_val, probability)
    metrics.update(
        {
            "fit_seconds": round(fit_seconds, 6),
            "val_inference_seconds": round(inference_seconds, 6),
            "n_iter": int(model.n_iter_),
        }
    )
    return model, metrics


def _permutation_importance(
    model: Any,
    x_val: np.ndarray,
    y_val: np.ndarray,
    names: list[str],
    *,
    sample_size: int = 100_000,
    repeats: int = 3,
) -> list[dict[str, Any]]:
    from sklearn.metrics import roc_auc_score

    rng = np.random.default_rng(SEED + 991)
    if len(y_val) > sample_size:
        chosen = np.sort(rng.choice(len(y_val), size=sample_size, replace=False))
        x = np.asarray(x_val[chosen], dtype=np.float32)
        y = y_val[chosen]
    else:
        x = np.asarray(x_val, dtype=np.float32).copy()
        y = y_val
    base_auc = float(roc_auc_score(y, model.predict_proba(x)[:, 1]))
    rows: list[dict[str, Any]] = []
    for col, name in enumerate(names):
        original = x[:, col].copy()
        drops = []
        for _ in range(repeats):
            x[:, col] = original[rng.permutation(len(original))]
            auc = float(roc_auc_score(y, model.predict_proba(x)[:, 1]))
            drops.append(base_auc - auc)
        x[:, col] = original
        rows.append(
            {
                "rank": 0,
                "feature": name,
                "mean_auc_drop": round(float(np.mean(drops)), 8),
                "std_auc_drop": round(float(np.std(drops)), 8),
                "sample_rows": int(len(y)),
                "repeats": repeats,
            }
        )
    rows.sort(key=lambda row: row["mean_auc_drop"], reverse=True)
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return rows


def run_models(
    train: dict[str, np.ndarray],
    val: dict[str, np.ndarray],
    ctx_train: np.ndarray,
    ctx_val: np.ndarray,
) -> dict[str, Any]:
    xtr_base, ytr, gtr = train["X"], train["y"].astype(int), train["gid"]
    xva_base, yva, gva = val["X"], val["y"].astype(int), val["gid"]

    tune_train_idx = np.flatnonzero((gtr % 7) == 0)
    tune_val_idx = np.flatnonzero((gva % 4) == 0)
    tuning = []
    for radius in RADII_PX:
        xtr_tune, tune_names = _assemble(
            xtr_base[tune_train_idx], ctx_train[tune_train_idx], radius
        )
        xva_tune, _ = _assemble(xva_base[tune_val_idx], ctx_val[tune_val_idx], radius)
        _model, metrics = _fit_and_score(
            xtr_tune, ytr[tune_train_idx], xva_tune, yva[tune_val_idx]
        )
        tuning.append(
            {
                "radius_px": radius,
                "radius_mm": radius * SCALE_MM_PER_PX,
                "n_train_rows": int(len(tune_train_idx)),
                "n_val_rows": int(len(tune_val_idx)),
                "features": tune_names,
                "metrics": metrics,
            }
        )
        del xtr_tune, xva_tune, _model
    selected = max(
        tuning,
        key=lambda row: (
            row["metrics"]["f1"],
            row["metrics"]["roc_auc"],
            -row["radius_px"],
        ),
    )
    selected_radius = float(selected["radius_px"])

    baseline_model, baseline_metrics = _fit_and_score(
        xtr_base, ytr, xva_base, yva
    )
    xtr_context, context_names = _assemble(xtr_base, ctx_train, selected_radius)
    xva_context, _ = _assemble(xva_base, ctx_val, selected_radius)
    context_model, context_metrics = _fit_and_score(
        xtr_context, ytr, xva_context, yva
    )
    shuffle_model, shuffle_metrics = _fit_and_score(
        xtr_context, ytr, xva_context, yva, shuffled=True
    )

    baseline_importance = _permutation_importance(
        baseline_model, xva_base, yva, list(BASE_FEATURE_NAMES)
    )
    context_importance = _permutation_importance(
        context_model, xva_context, yva, context_names
    )
    del xtr_context, xva_context

    delta = {
        key: round(context_metrics[key] - baseline_metrics[key], 6)
        for key in ("precision", "recall", "f1", "roc_auc")
    }
    if delta["f1"] >= 0.10:
        delta_band = "SUPPORT"
        occam = "FIXED_CONTEXT_AGGREGATES_REACH_SUPPORT_BAND"
    elif delta["f1"] >= 0.0:
        delta_band = "DEMOTE"
        occam = "POSITIVE_BUT_BELOW_SUPPORT_BAND"
    else:
        delta_band = "KILL"
        occam = "CONTEXT_MODEL_BELOW_BASELINE"
    shuffle_verdict = "PASS" if shuffle_metrics["roc_auc"] <= 0.55 else "FAIL"
    cell_verdict = delta_band if shuffle_verdict == "PASS" else "INVALID_LEAKAGE_SUSPECTED"

    return {
        "radius_tuning": {
            "selection_split": "val",
            "train_subset_rule": "drawing_gid % 7 == 0",
            "val_subset_rule": "drawing_gid % 4 == 0",
            "candidates": tuning,
            "selected_radius_px": selected_radius,
            "selected_radius_mm": selected_radius * SCALE_MM_PER_PX,
            "selection_key": "max val F1 at threshold 0.5; tie ROC-AUC; tie smaller R",
        },
        "models": {
            "hist_gbdt_baseline_6f": {
                "role": "baseline",
                "split": "val",
                "features": list(BASE_FEATURE_NAMES),
                "metrics": baseline_metrics,
            },
            "hist_gbdt_context_12f": {
                "role": "context",
                "split": "val",
                "features": context_names,
                "metrics": context_metrics,
            },
            "hist_gbdt_context_label_shuffle": {
                "role": "shuffle_control",
                "split": "val",
                "features": context_names,
                "metrics": shuffle_metrics,
                "shuffle_seed": SEED,
                "verdict": shuffle_verdict,
                "rule": "ROC-AUC <= 0.55",
            },
        },
        "delta_context_minus_baseline": delta,
        "delta_main_definition_for_this_cell": (
            "F1(HistGradientBoosting with 6 context aggregates) - "
            "F1(HistGradientBoosting frozen 6-feature baseline)"
        ),
        "delta_main_band": delta_band,
        "occam_implication": occam,
        "shuffle_control_verdict": shuffle_verdict,
        "cell_verdict": cell_verdict,
        "feature_importance": {
            "method": "validation permutation importance; ROC-AUC decrease",
            "baseline_all_6": baseline_importance,
            "context_top_10": context_importance[:10],
            "context_all_12": context_importance,
        },
    }


def _feature_definitions(selected_radius: float) -> list[dict[str, Any]]:
    lo = 50.0 / SCALE_MM_PER_PX
    hi = 400.0 / SCALE_MM_PER_PX
    return [
        {
            "feature": "parallel_band_neighbor_count",
            "definition": (
                "count of other segments with undirected angle difference <=2 deg, "
                "overlap ratio >=0.5, and perpendicular gap inside frozen thickness band"
            ),
            "parameters": {"band_px": [lo, hi], "band_mm": [50.0, 400.0]},
        },
        {
            "feature": "nearest_parallel_gap_px",
            "definition": (
                "minimum perpendicular gap to an angle<=2 deg, overlap>=0.5 neighbor; "
                "NaN when absent"
            ),
        },
        {
            "feature": "radius_density",
            "definition": "other segment midpoints within R divided by pi*R^2",
            "parameters": {
                "selected_radius_px": selected_radius,
                "selected_radius_mm": selected_radius * SCALE_MM_PER_PX,
            },
        },
        {
            "feature": "junction_degree",
            "definition": (
                "uncapped crossing/endpoint/T-junction neighbor count from the exact "
                "vectorized frozen detector geometry core"
            ),
            "parameters": {"snap_tol_px": 6.0 / SCALE_MM_PER_PX},
        },
        {
            "feature": "drawing_length_percentile",
            "definition": "empirical right-CDF rank of segment length within its drawing",
        },
        {
            "feature": "neighbor_angle_entropy",
            "definition": (
                "normalized Shannon entropy of 12-bin undirected angles among midpoint "
                "neighbors within selected R"
            ),
            "parameters": {"bins": ANGLE_BINS},
        },
    ]


def _render_report(result: dict[str, Any]) -> str:
    baseline = result["models"]["hist_gbdt_baseline_6f"]["metrics"]
    context = result["models"]["hist_gbdt_context_12f"]["metrics"]
    shuffle = result["models"]["hist_gbdt_context_label_shuffle"]["metrics"]
    delta = result["delta_context_minus_baseline"]
    bench = result["throughput"]["preflight_benchmark"]
    ext_train = result["throughput"]["full_extraction"]["train"]
    ext_val = result["throughput"]["full_extraction"]["val"]
    tuning = result["radius_tuning"]
    lines = [
        "# CML 문맥특징 확장 — 실행 보고서",
        "",
        f"- 실행 시각: {result['run']['completed_at']}",
        "- 범위: 기존 6특징 + 도면 단위 이름 비사용 문맥특징, train 학습 → val 평가",
        "- test 접근: 없음(코드가 `train`/`val` 외 split을 거부)",
        f"- seed: {SEED}",
        "",
        "## 결론",
        "",
        f"문맥 모델의 val F1은 **{context['f1']:.6f}**, 6특징 기준선은 "
        f"**{baseline['f1']:.6f}**로 Δ_main={delta['f1']:+.6f}이다. "
        f"판정 band는 **{result['delta_main_band']}**이며 셔플 대조군은 "
        f"AUC={shuffle['roc_auc']:.6f}로 **{result['shuffle_control_verdict']}**다.",
        "",
        f"Occam 판정: **{result['occam_implication']}**.",
        "",
        "## val 실측",
        "",
        "| 모델 | P@0.5 | R@0.5 | F1@0.5 | ROC-AUC | fit s | val infer s |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| HistGBDT 6특징 | {baseline['precision']:.6f} | {baseline['recall']:.6f} | "
        f"{baseline['f1']:.6f} | {baseline['roc_auc']:.6f} | {baseline['fit_seconds']:.3f} | "
        f"{baseline['val_inference_seconds']:.3f} |",
        f"| HistGBDT + 문맥 6종 | {context['precision']:.6f} | {context['recall']:.6f} | "
        f"{context['f1']:.6f} | {context['roc_auc']:.6f} | {context['fit_seconds']:.3f} | "
        f"{context['val_inference_seconds']:.3f} |",
        f"| 문맥 모델 label shuffle | {shuffle['precision']:.6f} | {shuffle['recall']:.6f} | "
        f"{shuffle['f1']:.6f} | {shuffle['roc_auc']:.6f} | {shuffle['fit_seconds']:.3f} | "
        f"{shuffle['val_inference_seconds']:.3f} |",
        "",
        f"행 수: train {result['data']['n_train']:,}, val {result['data']['n_val']:,}; "
        f"양성률 train {result['data']['wall_fraction']['train']:.6f}, "
        f"val {result['data']['wall_fraction']['val']:.6f}.",
        "",
        "## R 튜닝(val 전용)",
        "",
        f"선택 R={tuning['selected_radius_px']:.0f}px "
        f"({tuning['selected_radius_mm']:.0f}mm). 선택 규칙: {tuning['selection_key']}.",
        "",
        "| R px | R mm | tune-val F1 | tune-val AUC |",
        "|---:|---:|---:|---:|",
    ]
    for row in tuning["candidates"]:
        lines.append(
            f"| {row['radius_px']:.0f} | {row['radius_mm']:.0f} | "
            f"{row['metrics']['f1']:.6f} | {row['metrics']['roc_auc']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## 문맥특징 정의",
            "",
            "1. 동결 thickness 대역 안의 평행 이웃 수.",
            "2. overlap 조건을 만족하는 최근접 평행 이웃 gap(px, 없으면 NaN).",
            "3. 선택 반경의 midpoint 선분 밀도(count/πR²).",
            "4. crossing/endpoint/T-junction을 합친 uncapped 정션 차수.",
            "5. 도면 내 선분 길이 경험 백분위.",
            "6. 선택 반경 이웃의 12-bin 각도 히스토그램 정규화 엔트로피.",
            "",
            "raw 좌표, handle 문자열, 파일 순번, layer/name은 특징행렬에 넣지 않았다.",
            "",
            "## CPU 처리율",
            "",
            f"소표본 선행 실측: {bench['sample_drawings']}개 train 도면, "
            f"{bench['sample_rows']:,}행을 {bench['seconds']:.3f}s에 처리 "
            f"({bench['rows_per_second']:,.1f}행/s). 이 선형 외삽의 train 전량 예상은 "
            f"{bench['projected_train_seconds']:.1f}s ({bench['projected_train_hours']:.4f}h)였다.",
            "",
            f"전량 실측: train {ext_train['seconds']:.3f}s "
            f"({ext_train['rows_per_second']:,.1f}행/s), val {ext_val['seconds']:.3f}s "
            f"({ext_val['rows_per_second']:,.1f}행/s). 모든 도면의 base/context 행 정렬 검사는 PASS다.",
            "",
            "## 특징 중요도 상위 10",
            "",
            "val 100,000행에서 특징별 3회 permutation 후 ROC-AUC 감소 평균이다.",
            "",
            "| 순위 | 특징 | 평균 AUC 감소 | 표준편차 |",
            "|---:|---|---:|---:|",
        ]
    )
    for row in result["feature_importance"]["context_top_10"]:
        lines.append(
            f"| {row['rank']} | {row['feature']} | {row['mean_auc_drop']:.8f} | "
            f"{row['std_auc_drop']:.8f} |"
        )
    lines.extend(
        [
            "",
            "## 해석 제한",
            "",
            "이 셀의 Δ_main은 packet이 요구한 6특징 HistGBDT 대비 고정 문맥 집계의 val 이득이다. "
            "GraphSAGE FullEdge−NoMessage의 Δ_context나 test 일반화로 확대하지 않는다. "
            "val은 R 선택에 사용됐으므로 최종 held-out 주장도 하지 않는다.",
            "",
            "CELL_BLOCKED: evidence.xlsx requires unavailable @oai/artifact-tool runtime",
        ]
    )
    return "\n".join(lines)


def execute(benchmark_drawings: int) -> dict[str, Any]:
    started_at = _now_iso()
    train = _load_base("train")
    val = _load_base("val")
    if float(train["scale"]) != SCALE_MM_PER_PX or float(val["scale"]) != SCALE_MM_PER_PX:
        raise RuntimeError("base feature scale does not match frozen 12 mm/px")
    if train["X"].shape[1] != 6 or val["X"].shape[1] != 6:
        raise RuntimeError("expected exact six-feature baseline matrices")

    preflight = benchmark(train, n_drawings=benchmark_drawings)
    print("preflight:", json.dumps(preflight, ensure_ascii=False), flush=True)
    ctx_train, train_stats = extract_split("train", train)
    ctx_val, val_stats = extract_split("val", val)
    model_result = run_models(train, val, ctx_train, ctx_val)

    result: dict[str, Any] = {
        "schema": "ariadne.e2.cml_context_val.v1",
        "cell": "cml_ctx",
        "run": {
            "started_at": started_at,
            "completed_at": _now_iso(),
            "seed": SEED,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "scope": {
            "train_split": "train",
            "evaluation_split": "val",
            "test_accessed": False,
            "allowed_splits_enforced_in_code": sorted(ALLOWED_SPLITS),
            "source_ir": {
                "train": str(IR_ROOT / "train" / "*.segir.json"),
                "val": str(IR_ROOT / "val" / "*.segir.json"),
            },
        },
        "data": {
            "n_train": int(len(train["y"])),
            "n_val": int(len(val["y"])),
            "n_train_drawings": len(_split_files("train")),
            "n_val_drawings": len(_split_files("val")),
            "wall_fraction": {
                "train": round(float(train["y"].mean()), 8),
                "val": round(float(val["y"].mean()), 8),
            },
            "base_feature_source": {
                "train": str(BASE_FEATURE_DIR / "train.npz"),
                "val": str(BASE_FEATURE_DIR / "val.npz"),
                "reuse_per_packet": True,
            },
        },
        "feature_definitions": _feature_definitions(
            model_result["radius_tuning"]["selected_radius_px"]
        ),
        "throughput": {
            "preflight_benchmark": preflight,
            "full_extraction": {"train": train_stats, "val": val_stats},
        },
        "provenance": {
            "baseline_code": str(REPO_ROOT / "tools" / "e2" / "ext" / "cubicasa_ml.py"),
            "baseline_code_sha256": _sha256(
                REPO_ROOT / "tools" / "e2" / "ext" / "cubicasa_ml.py"
            ),
            "fast_score_code": str(REPO_ROOT / "tools" / "e2" / "w1_real_defs.py"),
            "fast_score_code_sha256": _sha256(
                REPO_ROOT / "tools" / "e2" / "w1_real_defs.py"
            ),
            "script_sha256": _sha256(Path(__file__).resolve()),
        },
        **model_result,
    }
    RESULTS_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    REPORT_PATH.write_text(_render_report(result), encoding="utf-8", newline="\n")
    del ctx_train, ctx_val
    shutil.rmtree(WORK_DIR, ignore_errors=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=("benchmark", "run"), help="benchmark train sample or execute full cell"
    )
    parser.add_argument("--benchmark-drawings", type=int, default=24)
    args = parser.parse_args()
    if args.mode == "benchmark":
        train = _load_base("train")
        print(json.dumps(benchmark(train, args.benchmark_drawings), indent=2))
        return 0
    result = execute(args.benchmark_drawings)
    print(
        json.dumps(
            {
                "cell_verdict": result["cell_verdict"],
                "delta_f1": result["delta_context_minus_baseline"]["f1"],
                "shuffle_auc": result["models"]["hist_gbdt_context_label_shuffle"][
                    "metrics"
                ]["roc_auc"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
