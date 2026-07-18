#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Freeze the non-GNN CubiCasa development baseline for calibration_P3 Cell E3.

This runner is deliberately limited to the literal ``train`` and ``val``
directories.  It never enumerates the IR parent directory and has no code path
for any other split.

Phases:
  preflight  - validate inputs, dependency hashes, and path guards
  extract    - regenerate the frozen six context features and leakage audit data
  model      - execute all arms/controls and write the frozen artifacts
  all        - extract, then model (default)
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
import threading
import time
import warnings
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


# Bound native numerical pools before importing NumPy/scikit-learn.  The values
# are part of the frozen execution environment and keep this CPU cell well below
# the 48 GB packet ceiling.
for _thread_env in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_thread_env, "8")

import joblib
import numpy as np
import psutil
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
)
from sklearn.model_selection import train_test_split


CELL_DIR = Path(__file__).resolve().parent
WORK_DIR = CELL_DIR / "_work"
REPO_ROOT = Path(r"D:\dev\99_tools\autocad-sdk-router")
IR_ROOT = REPO_ROOT / "runs" / "e2_ext_cubicasa" / "ir"
FEATURE_DIR = REPO_ROOT / "runs" / "e2_ext_cubicasa" / "features"
PACKET_PATH = Path(r"D:\runs\e2_program\build\PACKET_baseline_freeze.md")
SPEC_PATH = REPO_ROOT / "reports" / "e2" / "dossiers" / "calibration_P3.md"
CUBICASA_ML_PATH = REPO_ROOT / "tools" / "e2" / "ext" / "cubicasa_ml.py"
W1_DEFS_PATH = REPO_ROOT / "tools" / "e2" / "w1_real_defs.py"
CML_CTX_PATH = Path(r"D:\runs\e2_program\cells\cml_ctx\cml_ctx.py")
CML_CTX_RESULTS_PATH = Path(r"D:\runs\e2_program\cells\cml_ctx\results.json")

RESULTS_PATH = CELL_DIR / "results.json"
MANIFEST_PATH = CELL_DIR / "bstar_manifest.json"
MODEL_PATH = CELL_DIR / "bstar_model.joblib"
EVIDENCE_ROWS_PATH = CELL_DIR / "evidence_rows.json"
REPORT_PATH = CELL_DIR / "REPORT.md"
EXTRACTION_META_PATH = WORK_DIR / "extraction_meta.json"

ALLOWED_SPLITS = ("train", "val")
MODEL_SEEDS = (17, 29, 43)
# This list is defined at import time, before any label array is loaded.
PERMUTATION_SEEDS = tuple(range(1001, 1065))
SOURCE_CLASSIFIER_ROWS_PER_SPLIT = 100_000
SELECTED_CONTEXT_RADIUS_PX = 20.0
FINGERPRINT_QUANTIZATION = 1000
MATRIX_CHUNK_ROWS = 250_000

BASE_FEATURE_NAMES = (
    "parallel",
    "thickness",
    "junction",
    "log10_len",
    "sin2t",
    "cos2t",
)
CONTEXT_FEATURE_NAMES = (
    "parallel_band_neighbor_count",
    "nearest_parallel_gap_px",
    "junction_degree",
    "drawing_length_percentile",
    "radius_density_r20_per_px2",
    "neighbor_angle_entropy_r20",
)
P2B_FEATURE_NAMES = BASE_FEATURE_NAMES + CONTEXT_FEATURE_NAMES
DIAGNOSTIC_FEATURE_NAMES = P2B_FEATURE_NAMES + (
    "layer_name_wallish",
    "layer_name_hash16",
)
FORBIDDEN_PRIMARY_FEATURE_FRAGMENTS = (
    "handle",
    "filename",
    "file_path",
    "filepath",
    "block_name",
    "layer_name",
    "text_content",
    "drawing_id",
    "family_id",
    "sequence_index",
    "source_id",
    "class_name",
    "label",
)
EXCLUSION_CONTRACT = {
    "included": "first unique, valid, non-zero-length segment record per handle",
    "excluded": [
        "segment records with fewer than two points",
        "zero-length segment records",
        "later duplicate valid records for an already-seen handle",
    ],
    "additional_arm_specific_exclusions": 0,
    "row_universe_source": "frozen train.npz/val.npz X,y,gid arrays",
}


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


def _assert_cell_output(path: Path) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(CELL_DIR.resolve())
    except ValueError as exc:
        raise RuntimeError(f"refusing output outside cell directory: {resolved}") from exc


def _write_json(path: Path, value: Any) -> None:
    _assert_cell_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _write_text(path: Path, value: str) -> None:
    _assert_cell_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def _split_files(split: str) -> list[Path]:
    if split not in ALLOWED_SPLITS:
        raise ValueError(f"forbidden split {split!r}; allowed={ALLOWED_SPLITS}")
    directory = (IR_ROOT / split).resolve()
    expected = (IR_ROOT.resolve() / split).resolve()
    if directory != expected or directory.name != split:
        raise RuntimeError("split path guard failed")
    files = sorted(directory.glob("*.segir.json"))
    if not files:
        raise FileNotFoundError(f"no SEG-IR files in allowed directory {directory}")
    return files


def _load_cml_context_module() -> Any:
    spec = importlib.util.spec_from_file_location("baseline_freeze_cml_ctx", CML_CTX_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load context implementation: {CML_CTX_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_base(split: str) -> dict[str, np.ndarray]:
    if split not in ALLOWED_SPLITS:
        raise ValueError(f"forbidden split {split!r}")
    path = FEATURE_DIR / f"{split}.npz"
    with np.load(path, allow_pickle=False) as archive:
        required = {"X", "y", "gid", "scale"}
        if set(archive.files) != required:
            raise RuntimeError(f"{path}: NPZ keys {archive.files!r} != {sorted(required)!r}")
        data = {
            "X": np.asarray(archive["X"], dtype=np.float32),
            "y": np.asarray(archive["y"], dtype=np.int8),
            "gid": np.asarray(archive["gid"], dtype=np.int32),
            "scale": np.asarray(archive["scale"]),
        }
    if data["X"].ndim != 2 or data["X"].shape[1] != len(BASE_FEATURE_NAMES):
        raise RuntimeError(f"{split}: unexpected base matrix shape {data['X'].shape}")
    if not (len(data["X"]) == len(data["y"]) == len(data["gid"])):
        raise RuntimeError(f"{split}: X/y/gid row count mismatch")
    return data


class PeakMemorySampler:
    """Sample RSS for this process and any transient child processes."""

    def __init__(self, interval_seconds: float = 0.2):
        self.interval_seconds = interval_seconds
        self.peak_bytes = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _sample(self) -> None:
        process = psutil.Process()
        total = process.memory_info().rss
        for child in process.children(recursive=True):
            try:
                total += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self.peak_bytes = max(self.peak_bytes, int(total))

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._sample()

    def start(self) -> None:
        self._sample()
        self._thread.start()

    def stop(self) -> int:
        self._stop.set()
        self._thread.join(timeout=5.0)
        self._sample()
        return self.peak_bytes


def _geometry_and_layers(
    ir: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, list[str], int]:
    seen: set[str] = set()
    first: list[tuple[float, float]] = []
    second: list[tuple[float, float]] = []
    layers: list[str] = []
    duplicate_valid = 0
    for segment in ir.get("segments", []) or []:
        points = segment.get("pts") or []
        if len(points) < 2:
            continue
        a = (float(points[0][0]), float(points[0][1]))
        b = (float(points[-1][0]), float(points[-1][1]))
        if math.hypot(b[0] - a[0], b[1] - a[1]) == 0.0:
            continue
        handle = str(segment.get("handle") or segment.get("sid"))
        if handle in seen:
            duplicate_valid += 1
            continue
        seen.add(handle)
        first.append(a)
        second.append(b)
        layers.append(str(segment.get("layer") or ""))
    return (
        np.asarray(first, dtype=np.float64).reshape((-1, 2)),
        np.asarray(second, dtype=np.float64).reshape((-1, 2)),
        layers,
        duplicate_valid,
    )


def _canonical_geometry_fingerprint(p1: np.ndarray, p2: np.ndarray) -> str:
    """Quantized geometry family hash, invariant to translation/scale/D4 symmetry."""
    if len(p1) == 0:
        return hashlib.sha256(b"empty-geometry").hexdigest()
    points = np.stack((p1, p2), axis=1)
    flat = points.reshape((-1, 2))
    minimum = flat.min(axis=0)
    span = flat.max(axis=0) - minimum
    scale = float(max(span[0], span[1]))
    if scale <= 0.0:
        scale = 1.0
    normalized = (points - minimum) / scale
    transforms = (
        np.asarray(((1.0, 0.0), (0.0, 1.0))),
        np.asarray(((-1.0, 0.0), (0.0, 1.0))),
        np.asarray(((1.0, 0.0), (0.0, -1.0))),
        np.asarray(((-1.0, 0.0), (0.0, -1.0))),
        np.asarray(((0.0, 1.0), (1.0, 0.0))),
        np.asarray(((0.0, -1.0), (1.0, 0.0))),
        np.asarray(((0.0, 1.0), (-1.0, 0.0))),
        np.asarray(((0.0, -1.0), (-1.0, 0.0))),
    )
    candidate_hashes: list[str] = []
    prefix = np.asarray((len(points), FINGERPRINT_QUANTIZATION), dtype="<i8").tobytes()
    for transform in transforms:
        transformed = normalized @ transform.T
        transformed -= transformed.reshape((-1, 2)).min(axis=0)
        quantized = np.rint(transformed * FINGERPRINT_QUANTIZATION).astype("<i4")
        left = quantized[:, 0, :]
        right = quantized[:, 1, :]
        swap = (left[:, 0] > right[:, 0]) | (
            (left[:, 0] == right[:, 0]) & (left[:, 1] > right[:, 1])
        )
        ordered_left = np.where(swap[:, None], right, left)
        ordered_right = np.where(swap[:, None], left, right)
        records = np.column_stack((ordered_left, ordered_right)).astype("<i4", copy=False)
        order = np.lexsort(
            (records[:, 3], records[:, 2], records[:, 1], records[:, 0])
        )
        candidate_hashes.append(
            hashlib.sha256(prefix + records[order].tobytes()).hexdigest()
        )
    return min(candidate_hashes)


def _layer_features(
    names: Iterable[str], wallish_function: Any, cache: dict[str, tuple[float, float]]
) -> np.ndarray:
    rows: list[tuple[float, float]] = []
    for name in names:
        if name not in cache:
            digest = hashlib.sha256(name.encode("utf-8")).digest()
            hash16 = int.from_bytes(digest[:2], "big") / 65535.0
            cache[name] = (1.0 if wallish_function(name) else 0.0, hash16)
        rows.append(cache[name])
    return np.asarray(rows, dtype=np.float32).reshape((-1, 2))


def _input_hashes() -> dict[str, str]:
    paths = {
        "packet": PACKET_PATH,
        "calibration_P3": SPEC_PATH,
        "cubicasa_ml": CUBICASA_ML_PATH,
        "w1_real_defs": W1_DEFS_PATH,
        "cml_ctx": CML_CTX_PATH,
        "cml_ctx_results": CML_CTX_RESULTS_PATH,
        "train_npz": FEATURE_DIR / "train.npz",
        "val_npz": FEATURE_DIR / "val.npz",
        "baseline_freeze_py": Path(__file__).resolve(),
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing required inputs: {missing}")
    return {name: _sha256(path) for name, path in paths.items()}


def _preflight() -> dict[str, Any]:
    hashes = _input_hashes()
    context_result = json.loads(CML_CTX_RESULTS_PATH.read_text(encoding="utf-8"))
    selected = float(context_result["radius_tuning"]["selected_radius_px"])
    if selected != SELECTED_CONTEXT_RADIUS_PX:
        raise RuntimeError(
            f"context radius drift: expected {SELECTED_CONTEXT_RADIUS_PX}, got {selected}"
        )
    train_files = _split_files("train")
    val_files = _split_files("val")
    for split, files in (("train", train_files), ("val", val_files)):
        base_path = FEATURE_DIR / f"{split}.npz"
        with np.load(base_path, allow_pickle=False) as archive:
            gids = np.asarray(archive["gid"])
            if int(gids.min()) != 0 or int(gids.max()) + 1 != len(files):
                raise RuntimeError(f"{split}: gid coverage does not match SEG-IR files")
    toy1 = np.asarray(((0.0, 0.0), (0.0, 1.0), (1.0, 0.0)))
    toy2 = np.asarray(((1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))
    base_fp = _canonical_geometry_fingerprint(toy1, toy2)
    shifted_scaled_rotated_p1 = np.column_stack((-toy1[:, 1], toy1[:, 0])) * 3 + 7
    shifted_scaled_rotated_p2 = np.column_stack((-toy2[:, 1], toy2[:, 0])) * 3 + 7
    if base_fp != _canonical_geometry_fingerprint(
        shifted_scaled_rotated_p1, shifted_scaled_rotated_p2
    ):
        raise RuntimeError("geometry fingerprint invariance self-check failed")
    return {
        "checked_at": _now_iso(),
        "allowed_splits": list(ALLOWED_SPLITS),
        "split_file_counts": {"train": len(train_files), "val": len(val_files)},
        "selected_context_radius_px": selected,
        "model_seeds": list(MODEL_SEEDS),
        "permutation_seed_count": len(PERMUTATION_SEEDS),
        "permutation_seed_list_sha256": _canonical_hash(list(PERMUTATION_SEEDS)),
        "geometry_fingerprint_invariance_self_check": 1,
        "input_hashes": hashes,
        "xlsx_status": "BLOCKED_XLSX",
        "xlsx_block_reason": (
            "required artifact-tool workspace dependency loader is unavailable; "
            "row-complete JSON fallback is emitted"
        ),
    }


def _extract_one_split(
    split: str, base: dict[str, np.ndarray], context_module: Any
) -> dict[str, Any]:
    files = _split_files(split)
    gids = base["gid"]
    if int(gids.min()) != 0 or int(gids.max()) + 1 != len(files):
        raise RuntimeError(f"{split}: gid coverage mismatch")
    expected_by_gid = np.bincount(gids, minlength=len(files))
    context_path = WORK_DIR / f"context6_{split}.npy"
    layer_path = WORK_DIR / f"layer_name2_{split}.npy"
    _assert_cell_output(context_path)
    _assert_cell_output(layer_path)
    context_target = np.lib.format.open_memmap(
        context_path,
        mode="w+",
        dtype=np.float32,
        shape=(len(base["y"]), len(CONTEXT_FEATURE_NAMES)),
    )
    layer_target = np.lib.format.open_memmap(
        layer_path, mode="w+", dtype=np.float32, shape=(len(base["y"]), 2)
    )
    context_indices = context_module._selected_context_indices(  # noqa: SLF001
        SELECTED_CONTEXT_RADIUS_PX
    )
    selected_names = [
        context_module._context_names_all()[index]  # noqa: SLF001
        for index in context_indices
    ]
    if tuple(selected_names) != CONTEXT_FEATURE_NAMES:
        raise RuntimeError(
            f"context feature drift: expected {CONTEXT_FEATURE_NAMES}, got {selected_names}"
        )

    offset = 0
    duplicate_valid_handles = 0
    layer_counts: Counter[str] = Counter()
    layer_cache: dict[str, tuple[float, float]] = {}
    drawing_records: list[dict[str, Any]] = []
    aggregate_ir_hash = hashlib.sha256()
    started = time.perf_counter()
    for gid, path in enumerate(files):
        raw = path.read_bytes()
        aggregate_ir_hash.update(path.name.encode("utf-8"))
        aggregate_ir_hash.update(b"\0")
        aggregate_ir_hash.update(hashlib.sha256(raw).digest())
        ir = json.loads(raw)
        p1, p2, layers, duplicates = _geometry_and_layers(ir)
        context_all, context_meta = context_module.drawing_context(ir)
        expected = int(expected_by_gid[gid])
        if len(p1) != expected or len(context_all) != expected:
            raise RuntimeError(
                f"{split}: alignment mismatch {path.name}: "
                f"geometry={len(p1)} context={len(context_all)} base={expected}"
            )
        if int(context_meta["duplicates"]) != duplicates:
            raise RuntimeError(f"{split}: duplicate accounting drift in {path.name}")
        context_target[offset : offset + expected] = context_all[:, context_indices]
        layer_target[offset : offset + expected] = _layer_features(
            layers,
            context_module.w1_real_defs.evidence_grid._layer_is_wallish,  # noqa: SLF001
            layer_cache,
        )
        layer_counts.update(layers)
        duplicate_valid_handles += duplicates
        drawing_id = str(ir.get("drawing_id") or path.name.removesuffix(".segir.json"))
        drawing_records.append(
            {
                "drawing_id": drawing_id,
                "family_fingerprint": _canonical_geometry_fingerprint(p1, p2),
                "row_count": expected,
            }
        )
        offset += expected
        if (gid + 1) % 200 == 0 or gid + 1 == len(files):
            elapsed = time.perf_counter() - started
            print(
                f"[{split}] {gid + 1}/{len(files)} drawings; {offset:,} rows; "
                f"{offset / max(elapsed, 1e-9):,.0f} rows/s",
                flush=True,
            )
    context_target.flush()
    layer_target.flush()
    elapsed = time.perf_counter() - started
    if offset != len(base["y"]):
        raise RuntimeError(f"{split}: final extracted row count mismatch")
    return {
        "split": split,
        "drawings": len(files),
        "rows": int(offset),
        "wall_fraction": float(np.mean(base["y"])),
        "seconds": elapsed,
        "rows_per_second": offset / max(elapsed, 1e-9),
        "duplicate_valid_handle_records": int(duplicate_valid_handles),
        "alignment_mismatch_count": 0,
        "context_path": str(context_path),
        "context_sha256": _sha256(context_path),
        "layer_path": str(layer_path),
        "layer_sha256": _sha256(layer_path),
        "layer_unique_name_count": len(layer_counts),
        "layer_name_counts": dict(sorted(layer_counts.items())),
        "layer_wallish_row_count": int(
            sum(
                count
                for name, count in layer_counts.items()
                if layer_cache[name][0] == 1.0
            )
        ),
        "ir_aggregate_sha256": aggregate_ir_hash.hexdigest(),
        "drawing_records": drawing_records,
    }


def _family_audit(
    train_records: list[dict[str, Any]], val_records: list[dict[str, Any]]
) -> dict[str, Any]:
    train_ids = {row["drawing_id"] for row in train_records}
    val_ids = {row["drawing_id"] for row in val_records}
    drawing_id_collisions = sorted(train_ids & val_ids)
    by_split: dict[str, dict[str, list[str]]] = {
        "train": defaultdict(list),
        "val": defaultdict(list),
    }
    for split, rows in (("train", train_records), ("val", val_records)):
        for row in rows:
            by_split[split][row["family_fingerprint"]].append(row["drawing_id"])
    cross_fingerprints = sorted(set(by_split["train"]) & set(by_split["val"]))
    cross_pairs = sum(
        len(by_split["train"][fingerprint]) * len(by_split["val"][fingerprint])
        for fingerprint in cross_fingerprints
    )
    examples = []
    for fingerprint in cross_fingerprints[:20]:
        examples.append(
            {
                "family_fingerprint": fingerprint,
                "train_drawing_ids": by_split["train"][fingerprint][:10],
                "val_drawing_ids": by_split["val"][fingerprint][:10],
            }
        )
    within_train = sum(1 for values in by_split["train"].values() if len(values) > 1)
    within_val = sum(1 for values in by_split["val"].values() if len(values) > 1)
    return {
        "family_definition": (
            "drawing_id OR SHA-256 of endpoint-order-invariant segment geometry "
            "normalized for translation, global scale, rotation, and reflection; "
            f"coordinates quantized to 1/{FINGERPRINT_QUANTIZATION} max-bbox span"
        ),
        "drawing_id_collision_count": len(drawing_id_collisions),
        "geometry_family_collision_count": len(cross_fingerprints),
        "geometry_cross_fold_drawing_pair_count": int(cross_pairs),
        "family_collision_count": len(drawing_id_collisions)
        + len(cross_fingerprints),
        "within_train_duplicate_family_count": int(within_train),
        "within_val_duplicate_family_count": int(within_val),
        "drawing_id_collision_examples": drawing_id_collisions[:20],
        "geometry_family_collision_examples": examples,
    }


def extract() -> dict[str, Any]:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    preflight = _preflight()
    context_module = _load_cml_context_module()
    train = _load_base("train")
    val = _load_base("val")
    if float(train["scale"]) != float(val["scale"]):
        raise RuntimeError("train/val scale mismatch")
    train_meta = _extract_one_split("train", train, context_module)
    val_meta = _extract_one_split("val", val, context_module)
    family = _family_audit(train_meta["drawing_records"], val_meta["drawing_records"])
    split_payload = {
        "schema": "e2.baseline_freeze.split.v1",
        "allowed_splits": list(ALLOWED_SPLITS),
        "exclusion_contract": EXCLUSION_CONTRACT,
        "train_npz_sha256": preflight["input_hashes"]["train_npz"],
        "val_npz_sha256": preflight["input_hashes"]["val_npz"],
        "train_ir_aggregate_sha256": train_meta["ir_aggregate_sha256"],
        "val_ir_aggregate_sha256": val_meta["ir_aggregate_sha256"],
        "train_drawings": train_meta["drawing_records"],
        "val_drawings": val_meta["drawing_records"],
    }
    meta = {
        "schema": "e2.baseline_freeze.extraction.v1",
        "created_at": _now_iso(),
        "preflight": preflight,
        "scale_mm_per_px": float(train["scale"]),
        "selected_context_radius_px": SELECTED_CONTEXT_RADIUS_PX,
        "base_features": list(BASE_FEATURE_NAMES),
        "context_features": list(CONTEXT_FEATURE_NAMES),
        "exclusion_contract": EXCLUSION_CONTRACT,
        "split_hash": _canonical_hash(split_payload),
        "split_hash_payload_sha256": _canonical_hash(split_payload),
        "family_audit": family,
        "splits": {"train": train_meta, "val": val_meta},
    }
    _write_json(EXTRACTION_META_PATH, meta)
    print(
        "extraction complete: "
        f"split_hash={meta['split_hash']} family_collisions={family['family_collision_count']}",
        flush=True,
    )
    return meta


def _load_extraction_meta() -> dict[str, Any]:
    if not EXTRACTION_META_PATH.is_file():
        raise FileNotFoundError(
            f"missing {EXTRACTION_META_PATH}; run --phase extract before --phase model"
        )
    meta = json.loads(EXTRACTION_META_PATH.read_text(encoding="utf-8"))
    if meta.get("schema") != "e2.baseline_freeze.extraction.v1":
        raise RuntimeError("unsupported extraction metadata schema")
    current_hashes = _input_hashes()
    for key in (
        "packet",
        "calibration_P3",
        "cubicasa_ml",
        "w1_real_defs",
        "cml_ctx",
        "cml_ctx_results",
        "train_npz",
        "val_npz",
        "baseline_freeze_py",
    ):
        expected = meta["preflight"]["input_hashes"][key]
        if current_hashes[key] != expected:
            raise RuntimeError(f"input drift after extraction: {key}")
    for split in ALLOWED_SPLITS:
        split_meta = meta["splits"][split]
        for kind in ("context", "layer"):
            path = Path(split_meta[f"{kind}_path"])
            if not path.is_file() or _sha256(path) != split_meta[f"{kind}_sha256"]:
                raise RuntimeError(f"{split}: {kind} cache missing or hash mismatch")
    return meta


def _open_design_matrices(
    train: dict[str, np.ndarray], val: dict[str, np.ndarray], meta: dict[str, Any]
) -> tuple[np.memmap, np.memmap, np.memmap, np.memmap]:
    outputs: list[np.memmap] = []
    for split, base in (("train", train), ("val", val)):
        context = np.load(meta["splits"][split]["context_path"], mmap_mode="r")
        layer = np.load(meta["splits"][split]["layer_path"], mmap_mode="r")
        if context.shape != (len(base["y"]), len(CONTEXT_FEATURE_NAMES)):
            raise RuntimeError(f"{split}: context cache shape mismatch")
        if layer.shape != (len(base["y"]), 2):
            raise RuntimeError(f"{split}: layer cache shape mismatch")
        context_design_path = WORK_DIR / f"p2b_design_{split}.npy"
        diagnostic_design_path = WORK_DIR / f"leaky_design_{split}.npy"
        context_design = np.lib.format.open_memmap(
            context_design_path,
            mode="w+",
            dtype=np.float32,
            shape=(len(base["y"]), len(P2B_FEATURE_NAMES)),
        )
        diagnostic_design = np.lib.format.open_memmap(
            diagnostic_design_path,
            mode="w+",
            dtype=np.float32,
            shape=(len(base["y"]), len(DIAGNOSTIC_FEATURE_NAMES)),
        )
        for start in range(0, len(base["y"]), MATRIX_CHUNK_ROWS):
            end = min(start + MATRIX_CHUNK_ROWS, len(base["y"]))
            context_design[start:end, : len(BASE_FEATURE_NAMES)] = base["X"][start:end]
            context_design[start:end, len(BASE_FEATURE_NAMES) :] = context[start:end]
            diagnostic_design[start:end, : len(P2B_FEATURE_NAMES)] = context_design[
                start:end
            ]
            diagnostic_design[start:end, len(P2B_FEATURE_NAMES) :] = layer[start:end]
        context_design.flush()
        diagnostic_design.flush()
        outputs.extend((context_design, diagnostic_design))
    return outputs[0], outputs[1], outputs[2], outputs[3]


def _metric_record(y: np.ndarray, probability: np.ndarray) -> dict[str, Any]:
    probability = np.asarray(probability, dtype=np.float64)
    if len(y) != len(probability) or not np.all(np.isfinite(probability)):
        raise RuntimeError("metric input length or finiteness failure")
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
        "auprc": float(average_precision_score(y, probability)),
        "f1": float(f1),
        "precision": float(precision),
        "recall": float(recall),
        "threshold": 0.5,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "n": int(len(y)),
    }


def _fit_model(
    kind: str,
    seed: int,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
) -> tuple[Any, dict[str, Any]]:
    if kind == "logistic":
        estimator: Any = LogisticRegression(max_iter=2000, random_state=seed)
    elif kind == "hist_gbdt":
        estimator = HistGradientBoostingClassifier(random_state=seed)
    else:
        raise ValueError(f"unknown model kind {kind!r}")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        started = time.perf_counter()
        estimator.fit(x_train, y_train)
        fit_seconds = time.perf_counter() - started
    started = time.perf_counter()
    probability = estimator.predict_proba(x_val)[:, 1]
    inference_seconds = time.perf_counter() - started
    metrics = _metric_record(y_val, probability)
    metrics.update(
        {
            "fit_seconds": fit_seconds,
            "val_inference_seconds": inference_seconds,
            "warning_count": len(caught),
            "warnings": [str(item.message)[:300] for item in caught],
        }
    )
    if hasattr(estimator, "n_iter_"):
        n_iter = np.asarray(estimator.n_iter_).reshape(-1)
        metrics["n_iter"] = [int(value) for value in n_iter]
    return estimator, metrics


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {"seed_count": len(rows)}
    for metric in ("auprc", "f1", "precision", "recall"):
        values = np.asarray([row[metric] for row in rows], dtype=np.float64)
        output[metric] = {
            "mean": float(np.mean(values)),
            "std_population": float(np.std(values, ddof=0)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
        }
    return output


def _feature_audit() -> dict[str, Any]:
    primary = {
        "fast_score_p1": list(BASE_FEATURE_NAMES[:3]),
        "logistic_local6": list(BASE_FEATURE_NAMES),
        "hist_gbdt_local6_p2a": list(BASE_FEATURE_NAMES),
        "hist_gbdt_context12_p2b": list(P2B_FEATURE_NAMES),
    }
    diagnostic = {"hist_gbdt_context_layer_name_diagnostic": list(DIAGNOSTIC_FEATURE_NAMES)}

    def hits(names: Iterable[str]) -> list[dict[str, str]]:
        found = []
        for name in names:
            lowered = name.lower()
            for fragment in FORBIDDEN_PRIMARY_FEATURE_FRAGMENTS:
                if fragment in lowered:
                    found.append({"feature": name, "forbidden_fragment": fragment})
        return found

    primary_hits = {
        arm: hits(names) for arm, names in primary.items() if hits(names)
    }
    diagnostic_hits = {
        arm: hits(names) for arm, names in diagnostic.items() if hits(names)
    }
    allowlist_payload = {
        "primary": primary,
        "diagnostic": diagnostic,
        "forbidden_fragments": list(FORBIDDEN_PRIMARY_FEATURE_FRAGMENTS),
    }
    return {
        **allowlist_payload,
        "primary_identifier_or_name_feature_count": sum(
            len(value) for value in primary_hits.values()
        ),
        "primary_forbidden_hits": primary_hits,
        "diagnostic_name_feature_count": sum(
            len(value) for value in diagnostic_hits.values()
        ),
        "diagnostic_forbidden_hits": diagnostic_hits,
        "allowlist_sha256": _canonical_hash(allowlist_payload),
    }


def _distribution(values: Iterable[float]) -> dict[str, Any]:
    array = np.asarray(list(values), dtype=np.float64)
    return {
        "n": int(len(array)),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
        "mean": float(np.mean(array)),
        "std_population": float(np.std(array, ddof=0)),
        "median": float(np.median(array)),
        "central_95_low": float(np.quantile(array, 0.025)),
        "central_95_high": float(np.quantile(array, 0.975)),
    }


def _percentile_position(value: float, reference: Iterable[float]) -> float:
    array = np.asarray(list(reference), dtype=np.float64)
    below = np.sum(array < value)
    equal = np.sum(array == value)
    return float((below + 0.5 * equal) / len(array))


def _source_classifier(
    train_x: np.ndarray, val_x: np.ndarray
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    take = min(SOURCE_CLASSIFIER_ROWS_PER_SPLIT, len(train_x), len(val_x))
    for seed in MODEL_SEEDS:
        rng = np.random.default_rng(seed + 500_000)
        train_indices = np.sort(rng.choice(len(train_x), size=take, replace=False))
        val_indices = np.sort(rng.choice(len(val_x), size=take, replace=False))
        features = np.vstack((train_x[train_indices], val_x[val_indices]))
        source = np.concatenate((np.zeros(take, dtype=np.int8), np.ones(take, dtype=np.int8)))
        x_fit, x_eval, y_fit, y_eval = train_test_split(
            features,
            source,
            test_size=0.30,
            random_state=seed,
            stratify=source,
        )
        model = HistGradientBoostingClassifier(random_state=seed)
        started = time.perf_counter()
        model.fit(x_fit, y_fit)
        fit_seconds = time.perf_counter() - started
        prediction = model.predict(x_eval)
        rows.append(
            {
                "seed": seed,
                "sample_rows_per_source": int(take),
                "fit_rows": int(len(y_fit)),
                "eval_rows": int(len(y_eval)),
                "accuracy": float(accuracy_score(y_eval, prediction)),
                "balanced_accuracy": float(balanced_accuracy_score(y_eval, prediction)),
                "fit_seconds": fit_seconds,
            }
        )
        del features, source, x_fit, x_eval, y_fit, y_eval, model, prediction
        gc.collect()
    return rows, {
        "accuracy": _distribution(row["accuracy"] for row in rows),
        "balanced_accuracy": _distribution(
            row["balanced_accuracy"] for row in rows
        ),
        "method": (
            "balanced random row sample from train and val; 70/30 stratified "
            "diagnostic split; local6 features only; not used in B* selection"
        ),
    }


def _render_report(result: dict[str, Any], artifact_hashes: dict[str, str]) -> str:
    lines = [
        "# Non-GNN Baseline Freeze — Numeric Execution Report",
        "",
        f"- Completed: {result['run']['completed_at']}",
        "- Development universe: CubiCasa train to val",
        f"- Rows: train {result['data']['train_rows']:,}; val {result['data']['val_rows']:,}",
        f"- Drawings: train {result['data']['train_drawings']:,}; val {result['data']['val_drawings']:,}",
        f"- Split hash: `{result['split_hash']}`",
        f"- Test-split reads: {result['run']['test_split_reads']}",
        f"- Peak sampled RSS: {result['run']['peak_rss_gib']:.3f} GiB",
        "",
        "## Primary arms (val, three-seed mean ± population std)",
        "",
        "| Arm | AUPRC | F1@0.5 |",
        "|---|---:|---:|",
    ]
    for arm in result["primary_arm_order"]:
        summary = result["arm_summaries"][arm]
        lines.append(
            f"| {arm} | {summary['auprc']['mean']:.8f} ± "
            f"{summary['auprc']['std_population']:.8f} | "
            f"{summary['f1']['mean']:.8f} ± {summary['f1']['std_population']:.8f} |"
        )
    bstar = result["bstar"]
    lines.extend(
        [
            "",
            "## Frozen B*",
            "",
            f"- Arm: `{bstar['arm']}`",
            f"- Selection metric: mean val AUPRC = {bstar['auprc_mean']:.10f}",
            f"- Mean val F1@0.5: {bstar['f1_mean']:.10f}",
            f"- Model artifact SHA-256: `{bstar['model_artifact_sha256']}`",
            "",
            "## Leakage, shuffle, and family controls",
            "",
            f"- Primary identifier/name feature count: {result['feature_audit']['primary_identifier_or_name_feature_count']}",
            f"- Diagnostic name-derived feature count: {result['feature_audit']['diagnostic_name_feature_count']}",
            f"- Leaky-minus-masked AUPRC: {result['controls']['leaky_vs_masked_delta']['auprc_mean_delta']:+.10f}",
            f"- Leaky-minus-masked F1: {result['controls']['leaky_vs_masked_delta']['f1_mean_delta']:+.10f}",
            f"- Shuffle-null AUPRC central 95%: [{result['controls']['permutation_null']['auprc']['central_95_low']:.10f}, {result['controls']['permutation_null']['auprc']['central_95_high']:.10f}]",
            f"- P2-b observed AUPRC percentile position in shuffle null: {result['controls']['permutation_null']['observed_p2b_auprc_percentile']:.10f}",
            f"- Held-out shuffle AUPRC percentile position among remaining shuffles: {result['controls']['permutation_null']['heldout_shuffle_position']['auprc_percentile']:.10f}",
            f"- Family collision count: {result['family_audit']['family_collision_count']}",
            f"- Cross-fold geometry-family count: {result['family_audit']['geometry_family_collision_count']}",
            f"- Cross-fold drawing-ID count: {result['family_audit']['drawing_id_collision_count']}",
            f"- Source-classifier accuracy mean: {result['controls']['source_classifier']['summary']['accuracy']['mean']:.10f}",
            "",
            "## Evidence artifact status",
            "",
            "- `BLOCKED_XLSX`: the required artifact-tool dependency loader was unavailable in this executor.",
            "- Row-complete substitute: `evidence_rows.json`.",
            "",
            "## Artifact hashes",
            "",
        ]
    )
    for name, digest in artifact_hashes.items():
        lines.append(f"- {name}: `{digest}`")
    lines.extend(["", "CELL_COMPLETE: baseline_freeze"])
    return "\n".join(lines) + "\n"


def _evidence_payload(result: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    arm_rows = []
    for arm, rows in result["arm_seed_metrics"].items():
        for row in rows:
            arm_rows.append({"arm": arm, **row})
    summary_rows = []
    for arm, summary in result["arm_summaries"].items():
        summary_rows.append(
            {
                "arm": arm,
                "seed_count": summary["seed_count"],
                "auprc_mean": summary["auprc"]["mean"],
                "auprc_std_population": summary["auprc"]["std_population"],
                "f1_mean": summary["f1"]["mean"],
                "f1_std_population": summary["f1"]["std_population"],
            }
        )
    feature_rows = []
    for scope in ("primary", "diagnostic"):
        for arm, names in result["feature_audit"][scope].items():
            for position, name in enumerate(names):
                feature_rows.append(
                    {
                        "scope": scope,
                        "arm": arm,
                        "feature_position": position,
                        "feature": name,
                    }
                )
    return {
        "schema": "e2.baseline_freeze.evidence_rows.v1",
        "workbook_status": "BLOCKED_XLSX",
        "workbook_block_reason": result["evidence"]["xlsx_block_reason"],
        "sheets": {
            "README": [
                {"key": "split_hash", "value": result["split_hash"]},
                {"key": "bstar_arm", "value": result["bstar"]["arm"]},
                {"key": "bstar_auprc_mean", "value": result["bstar"]["auprc_mean"]},
                {"key": "test_split_reads", "value": result["run"]["test_split_reads"]},
                {"key": "family_collision_count", "value": result["family_audit"]["family_collision_count"]},
                {"key": "manifest_content_hash", "value": manifest["content_hash"]},
            ],
            "arm_seed_metrics": arm_rows,
            "arm_summary": summary_rows,
            "permutation_null": result["controls"]["permutation_null"]["rows"],
            "source_classifier": result["controls"]["source_classifier"]["rows"],
            "feature_allowlist": feature_rows,
            "family_audit": [result["family_audit"]],
            "hashes": [
                {"artifact": name, "sha256": digest}
                for name, digest in result["input_hashes"].items()
            ],
        },
    }


def model(memory_sampler: PeakMemorySampler) -> dict[str, Any]:
    meta = _load_extraction_meta()
    train = _load_base("train")
    val = _load_base("val")
    xtr_base = train["X"]
    xva_base = val["X"]
    ytr = train["y"].astype(np.int8, copy=False)
    yva = val["y"].astype(np.int8, copy=False)
    xtr_context, xtr_leaky, xva_context, xva_leaky = _open_design_matrices(
        train, val, meta
    )
    feature_audit = _feature_audit()
    if feature_audit["primary_identifier_or_name_feature_count"] != 0:
        raise RuntimeError("primary feature allowlist contains identifier/name features")

    primary_order = (
        "fast_score_p1",
        "logistic_local6",
        "hist_gbdt_local6_p2a",
        "hist_gbdt_context12_p2b",
    )
    arm_seed_metrics: dict[str, list[dict[str, Any]]] = {
        arm: [] for arm in primary_order
    }
    diagnostic_arm = "hist_gbdt_context_layer_name_diagnostic"
    arm_seed_metrics[diagnostic_arm] = []
    models_by_arm: dict[str, dict[int, Any]] = defaultdict(dict)

    p1_probability = (
        0.35 * xva_base[:, 0] + 0.25 * xva_base[:, 1] + 0.20 * xva_base[:, 2]
    ) / 0.80
    p1_metrics = _metric_record(yva, p1_probability)
    for seed in MODEL_SEEDS:
        arm_seed_metrics["fast_score_p1"].append(
            {"seed": seed, **p1_metrics, "fit_seconds": 0.0, "val_inference_seconds": 0.0}
        )

    learned_specs = (
        ("logistic_local6", "logistic", xtr_base, xva_base),
        ("hist_gbdt_local6_p2a", "hist_gbdt", xtr_base, xva_base),
        ("hist_gbdt_context12_p2b", "hist_gbdt", xtr_context, xva_context),
        (diagnostic_arm, "hist_gbdt", xtr_leaky, xva_leaky),
    )
    for arm, kind, x_train, x_val in learned_specs:
        for seed in MODEL_SEEDS:
            estimator, metrics = _fit_model(kind, seed, x_train, ytr, x_val, yva)
            arm_seed_metrics[arm].append({"seed": seed, **metrics})
            models_by_arm[arm][seed] = estimator
            print(
                f"[{arm}] seed={seed} AUPRC={metrics['auprc']:.8f} "
                f"F1={metrics['f1']:.8f}",
                flush=True,
            )

    arm_summaries = {
        arm: _aggregate(rows) for arm, rows in arm_seed_metrics.items()
    }
    champion = max(
        primary_order,
        key=lambda arm: (
            arm_summaries[arm]["auprc"]["mean"],
            arm_summaries[arm]["f1"]["mean"],
            -primary_order.index(arm),
        ),
    )

    null_rows: list[dict[str, Any]] = []
    for index, seed in enumerate(PERMUTATION_SEEDS, 1):
        permuted = np.random.default_rng(seed).permutation(ytr)
        estimator = HistGradientBoostingClassifier(random_state=seed)
        started = time.perf_counter()
        estimator.fit(xtr_context, permuted)
        fit_seconds = time.perf_counter() - started
        started = time.perf_counter()
        probability = estimator.predict_proba(xva_context)[:, 1]
        inference_seconds = time.perf_counter() - started
        metrics = _metric_record(yva, probability)
        null_rows.append(
            {
                "seed": seed,
                **metrics,
                "fit_seconds": fit_seconds,
                "val_inference_seconds": inference_seconds,
            }
        )
        del permuted, estimator, probability
        if index % 8 == 0 or index == len(PERMUTATION_SEEDS):
            print(
                f"[permutation-null] {index}/{len(PERMUTATION_SEEDS)}; "
                f"last AUPRC={metrics['auprc']:.8f}",
                flush=True,
            )
        gc.collect()

    null_auprc = [row["auprc"] for row in null_rows]
    null_f1 = [row["f1"] for row in null_rows]
    observed_p2b = arm_summaries["hist_gbdt_context12_p2b"]["auprc"]["mean"]
    heldout = null_rows[0]
    remaining = null_rows[1:]
    permutation_control = {
        "seed_list": list(PERMUTATION_SEEDS),
        "seed_list_sha256": _canonical_hash(list(PERMUTATION_SEEDS)),
        "rows": null_rows,
        "auprc": _distribution(null_auprc),
        "f1": _distribution(null_f1),
        "observed_p2b_auprc": observed_p2b,
        "observed_p2b_auprc_percentile": _percentile_position(
            observed_p2b, null_auprc
        ),
        "heldout_shuffle_position": {
            "seed": heldout["seed"],
            "auprc": heldout["auprc"],
            "auprc_percentile": _percentile_position(
                heldout["auprc"], (row["auprc"] for row in remaining)
            ),
            "reference_auprc": _distribution(row["auprc"] for row in remaining),
            "f1": heldout["f1"],
            "f1_percentile": _percentile_position(
                heldout["f1"], (row["f1"] for row in remaining)
            ),
            "reference_f1": _distribution(row["f1"] for row in remaining),
        },
    }

    source_rows, source_summary = _source_classifier(xtr_base, xva_base)
    masked_summary = arm_summaries["hist_gbdt_context12_p2b"]
    leaky_summary = arm_summaries[diagnostic_arm]
    leaky_delta = {
        "matched_masked_arm": "hist_gbdt_context12_p2b",
        "diagnostic_arm": diagnostic_arm,
        "auprc_mean_delta": leaky_summary["auprc"]["mean"]
        - masked_summary["auprc"]["mean"],
        "f1_mean_delta": leaky_summary["f1"]["mean"]
        - masked_summary["f1"]["mean"],
        "per_seed": [
            {
                "seed": seed,
                "auprc_delta": arm_seed_metrics[diagnostic_arm][position]["auprc"]
                - arm_seed_metrics["hist_gbdt_context12_p2b"][position]["auprc"],
                "f1_delta": arm_seed_metrics[diagnostic_arm][position]["f1"]
                - arm_seed_metrics["hist_gbdt_context12_p2b"][position]["f1"],
            }
            for position, seed in enumerate(MODEL_SEEDS)
        ],
    }

    champion_features = {
        "fast_score_p1": BASE_FEATURE_NAMES[:3],
        "logistic_local6": BASE_FEATURE_NAMES,
        "hist_gbdt_local6_p2a": BASE_FEATURE_NAMES,
        "hist_gbdt_context12_p2b": P2B_FEATURE_NAMES,
    }[champion]
    model_bundle: dict[str, Any] = {
        "schema": "e2.baseline_freeze.bstar_model_bundle.v1",
        "created_at": _now_iso(),
        "bstar_arm": champion,
        "model_seeds": list(MODEL_SEEDS),
        "features": list(champion_features),
        "split_hash": meta["split_hash"],
        "feature_allowlist_sha256": feature_audit["allowlist_sha256"],
        "baseline_freeze_py_sha256": meta["preflight"]["input_hashes"][
            "baseline_freeze_py"
        ],
        "inference_rule": "report each seed; optional bundle probability is arithmetic mean",
    }
    if champion == "fast_score_p1":
        model_bundle["artifact_type"] = "deterministic_formula"
        model_bundle["formula"] = {
            "numerator": "0.35*parallel + 0.25*thickness + 0.20*junction",
            "denominator": 0.80,
        }
    else:
        model_bundle["artifact_type"] = "three_seed_sklearn_bundle"
        model_bundle["models_by_seed"] = models_by_arm[champion]
    _assert_cell_output(MODEL_PATH)
    joblib.dump(model_bundle, MODEL_PATH, compress=3)
    model_hash = _sha256(MODEL_PATH)

    frozen_content = {
        "bstar": {
            "arm": champion,
            "selection_rule": "maximum three-seed mean val AUPRC; tie mean F1; tie preregistered arm order",
            "auprc_mean": arm_summaries[champion]["auprc"]["mean"],
            "auprc_std_population": arm_summaries[champion]["auprc"][
                "std_population"
            ],
            "f1_mean": arm_summaries[champion]["f1"]["mean"],
            "f1_std_population": arm_summaries[champion]["f1"]["std_population"],
        },
        "model_artifact": {
            "path": str(MODEL_PATH),
            "sha256": model_hash,
            "type": model_bundle["artifact_type"],
        },
        "split_hash": meta["split_hash"],
        "exclusion_contract": EXCLUSION_CONTRACT,
        "feature_allowlist": feature_audit,
        "model_seeds": list(MODEL_SEEDS),
        "permutation_seed_list": list(PERMUTATION_SEEDS),
        "permutation_seed_list_sha256": _canonical_hash(list(PERMUTATION_SEEDS)),
        "input_hashes": meta["preflight"]["input_hashes"],
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scikit_learn": __import__("sklearn").__version__,
            "joblib": joblib.__version__,
        },
    }
    manifest = {
        "schema": "e2.baseline_freeze.bstar_manifest.v1",
        "created_at": _now_iso(),
        "frozen": frozen_content,
        "content_hash": _canonical_hash(frozen_content),
    }
    _write_json(MANIFEST_PATH, manifest)

    peak_bytes = memory_sampler.peak_bytes
    result = {
        "schema": "e2.baseline_freeze.results.v1",
        "run": {
            "completed_at": _now_iso(),
            "allowed_splits": list(ALLOWED_SPLITS),
            "test_split_reads": 0,
            "subagents_used": 0,
            "model_seeds": list(MODEL_SEEDS),
            "peak_rss_bytes_sampled": int(peak_bytes),
            "peak_rss_gib": peak_bytes / (1024**3),
        },
        "data": {
            "truth_namespace": "CubiCasa development",
            "train_rows": int(len(ytr)),
            "val_rows": int(len(yva)),
            "train_drawings": int(meta["splits"]["train"]["drawings"]),
            "val_drawings": int(meta["splits"]["val"]["drawings"]),
            "train_wall_fraction": float(np.mean(ytr)),
            "val_wall_fraction": float(np.mean(yva)),
            "scale_mm_per_px": float(meta["scale_mm_per_px"]),
            "selected_context_radius_px": SELECTED_CONTEXT_RADIUS_PX,
            "shared_exclusion_contract": EXCLUSION_CONTRACT,
            "alignment_mismatch_count": 0,
        },
        "split_hash": meta["split_hash"],
        "primary_arm_order": list(primary_order),
        "arm_seed_metrics": arm_seed_metrics,
        "arm_summaries": arm_summaries,
        "bstar": {
            "arm": champion,
            "auprc_mean": arm_summaries[champion]["auprc"]["mean"],
            "f1_mean": arm_summaries[champion]["f1"]["mean"],
            "model_artifact": str(MODEL_PATH),
            "model_artifact_sha256": model_hash,
            "manifest_content_hash": manifest["content_hash"],
        },
        "feature_audit": feature_audit,
        "family_audit": meta["family_audit"],
        "controls": {
            "leaky_vs_masked_delta": leaky_delta,
            "permutation_null": permutation_control,
            "source_classifier": {"rows": source_rows, "summary": source_summary},
        },
        "input_hashes": meta["preflight"]["input_hashes"],
        "evidence": {
            "xlsx_status": "BLOCKED_XLSX",
            "xlsx_block_reason": meta["preflight"]["xlsx_block_reason"],
            "fallback_path": str(EVIDENCE_ROWS_PATH),
        },
    }
    _write_json(RESULTS_PATH, result)
    evidence = _evidence_payload(result, manifest)
    _write_json(EVIDENCE_ROWS_PATH, evidence)
    artifact_hashes = {
        "baseline_freeze.py": _sha256(Path(__file__).resolve()),
        "results.json": _sha256(RESULTS_PATH),
        "bstar_manifest.json": _sha256(MANIFEST_PATH),
        "bstar_model.joblib": model_hash,
        "evidence_rows.json": _sha256(EVIDENCE_ROWS_PATH),
    }
    _write_text(REPORT_PATH, _render_report(result, artifact_hashes))
    print(
        f"model phase complete: B*={champion} "
        f"AUPRC={result['bstar']['auprc_mean']:.8f}",
        flush=True,
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=("preflight", "extract", "model", "all"),
        default="all",
    )
    args = parser.parse_args(argv)
    sampler = PeakMemorySampler()
    sampler.start()
    try:
        if args.phase == "preflight":
            print(json.dumps(_preflight(), ensure_ascii=False, indent=2))
        elif args.phase == "extract":
            extract()
        elif args.phase == "model":
            model(sampler)
        else:
            extract()
            model(sampler)
    finally:
        peak = sampler.stop()
        print(f"sampled peak RSS: {peak / (1024**3):.3f} GiB", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
