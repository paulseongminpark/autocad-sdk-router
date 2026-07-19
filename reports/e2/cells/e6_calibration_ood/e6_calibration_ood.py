#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E6 GNN-A calibration and IID style-slice numeric executor.

This file is intentionally local to the E6 cell.  It adopts the inherited
preregistration seals, loads frozen GNN-A checkpoints for inference only,
reproduces the sealed train-only classical control fit, and never searches a
classification threshold.
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import importlib.util
import io
import json
import math
import os
import sys
import time
import warnings
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


for _thread_env in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_thread_env, "8")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

import numpy as np
import psutil
import torch
from scipy.optimize import minimize_scalar
from scipy.special import expit
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score


CELL_DIR = Path(r"D:\runs\e2_program\cells\e6_calibration_ood")
PREREG_PATH = CELL_DIR / "prereg.json"
PREREG_CSV_PATH = CELL_DIR / "PREREG.csv"
SCRIPT_PATH = CELL_DIR / "e6_calibration_ood.py"
RESULTS_PATH = CELL_DIR / "results.json"
EVIDENCE_CSV_PATH = CELL_DIR / "evidence.csv"
REPORT_PATH = CELL_DIR / "REPORT.md"

REPO_ROOT = Path(r"D:\dev\99_tools\autocad-sdk-router")
RUN_CELLS = Path(r"D:\runs\e2_program\cells")
PACKET_PATH = Path(r"D:\runs\e2_program\build\PACKET_e6_calibration_ood.md")
RESUME_NOTE_PATH = Path(r"D:\runs\e2_program\build\RESUME_NOTE_g5_e6.md")
DOSSIER_PATH = REPO_ROOT / "reports" / "e2" / "dossiers" / "calibration_P3.md"
SPLIT_MANIFEST_PATH = RUN_CELLS / "w2_09_valb" / "split_manifest.json"
FORMAL_DIR = RUN_CELLS / "gnn_formal"
FORMAL_RUNNER_PATH = FORMAL_DIR / "gnn_formal.py"
FORMAL_RESULTS_PATH = FORMAL_DIR / "results.json"
FORMAL_CKPT_DIR = FORMAL_DIR / "ckpt"
GRAPH_BUILDER_PATH = REPO_ROOT / "tools" / "e2" / "cells" / "graph_builder.py"
SCREEN_V2_PATH = RUN_CELLS / "gnn_e2_screen_v2" / "gnn_e2_v2.py"
W2_02_PATH = RUN_CELLS / "w2_02_twohop" / "w2_02_twohop.py"
TRAIN_NPZ_PATH = REPO_ROOT / "runs" / "e2_ext_cubicasa" / "features" / "train.npz"
VAL_ROOT = REPO_ROOT / "runs" / "e2_ext_cubicasa" / "ir" / "val"
BASELINE_DESIGN_TRAIN_PATH = RUN_CELLS / "w2_02_twohop" / "_work" / "design_full_train.npy"
BASELINE_CONTEXT_VAL_PATH = RUN_CELLS / "w2_02_twohop" / "_work" / "context6_valA.npy"
BASELINE_TWOHOP_VAL_PATH = RUN_CELLS / "w2_02_twohop" / "_work" / "twohop_valA.npy"

SEEDS = (17, 29, 43)
THRESHOLD = 0.5
CAL_SPLIT_SEED = 43
CAL_SPLIT_NAMESPACE = "e6.calibration.ood.v1"
CAL_FIT_FAMILY_COUNT = 99
TEMPERATURE_LOG_BOUNDS = (-4.0, 4.0)
TEMPERATURE_XATOL = 1e-12
TEMPERATURE_MAXITER = 1000
PROBABILITY_CLIP = 1e-12
RTX_CAP_SECONDS = 8.0 * 3600.0
EXPECTED_GRAPH_CONFIG_HASH = "56911f4633979a3fe00fd56be2d0a39ac06757ed255ed49ed18ca20ba9d4ac49"
EXPECTED_SPLIT_CONTENT_HASH = "5e16541d7191ad01c57a9cee72172f63112ed68590dd371aff5bf0aaaab8e07b"
EXPECTED_VAL_A_IR_AGGREGATE = "1db9634138e715b29fa19d2387fbb878150770234b60b764f66a765c61c53cbb"
EXPECTED_VAL_A_TRUTH_AGGREGATE = "06ddbdf25c279d947cc75560002896c9acdb81ea16c98250e1353f7c03ed1813"
EXPECTED_SEAL_HASHES = {
    "prereg.json": "7cc9492512980396ca0062a23d75a2a4f77cfb8ad65416f1fbefdc5e280d6083",
    "PREREG.csv": "191fb4ad45bf83c252041cab55d580e222e2f1a81dd3491b404b09ad8488928f",
}
EXPECTED_RESUME_NOTE_HASH = "27390773344cd74d2cf280704eb06a97db09b4fda4e3e4ba845df9e4ee59e14a"

EXPECTED_INPUT_HASHES: dict[str, tuple[Path, str]] = {
    "packet": (PACKET_PATH, "a9ea210148cde7ad6488a0c97ba384b7fd453247925649adb976f3911db2cfc2"),
    "resume_note": (RESUME_NOTE_PATH, EXPECTED_RESUME_NOTE_HASH),
    "calibration_dossier": (DOSSIER_PATH, "6641dd63044ad22b94d6c2a61baf85f86ca4c9191745659171e8a806864c294d"),
    "split_manifest": (SPLIT_MANIFEST_PATH, "8aad64eeda77df55296fc711c21d7befdeada7fe379aeafec81fd1691aea044f"),
    "formal_runner": (FORMAL_RUNNER_PATH, "0413f1035de76ab8a175c37c291c3fca634a2f1effb8135b5371aa357d5a94c0"),
    "graph_builder": (GRAPH_BUILDER_PATH, "c95d4a30d30e0db157fe56102053a7884902b7749464f7f4cb8852c0819321f6"),
    "screen_v2": (SCREEN_V2_PATH, "895249f0b6c77ac8f8a7cfb73e859a0882681ad6bba6e337480b55db269ce120"),
    "W2_02_source": (W2_02_PATH, "ae81bf8c5311fc19c8ad38f7feca5d1c15bf39a71d41a1fb925775d6e63aafe6"),
    "train_labels": (TRAIN_NPZ_PATH, "8f72d8931c6e08927bf027ee87f1bc5362ab1a85217862e09a0cddd6b0b0d5aa"),
    "baseline_design_train": (BASELINE_DESIGN_TRAIN_PATH, "8e2ca80cc52ab9ebcbb9f8f60fb1d4177186cd1e7fafcfee486cfcbc40335a11"),
    "baseline_context_val_A": (BASELINE_CONTEXT_VAL_PATH, "b568bb4c3dffce46629355bf7670cf00f6c86ecbfe14b5feb87f4e6103449a91"),
    "baseline_twohop_val_A": (BASELINE_TWOHOP_VAL_PATH, "ef0febd1d6da09a2a129c26dcc19028828e80bb4fa19c9db2b3eb5b423cef1df"),
    "GNN_A_seed_17": (FORMAL_CKPT_DIR / "GNN_A_no_pretrain_seed_17.pt", "612e4bf954ff5967853f7a08e66195b79dfa15250d6e9d42f88a877c92a3952c"),
    "GNN_A_seed_29": (FORMAL_CKPT_DIR / "GNN_A_no_pretrain_seed_29.pt", "1b4bbd004491609cfe8cfc217d18b0ec5ff344f8fee43c67b392a4c37dbc6877"),
    "GNN_A_seed_43": (FORMAL_CKPT_DIR / "GNN_A_no_pretrain_seed_43.pt", "ab37cf25894e8ed7f2e96ca287a21da961c68d37bcf2bd9633ae1cb9b663e2a3"),
    "formal_control_seed_17": (FORMAL_CKPT_DIR / "control_twohop_full_seed_17.joblib", "7de0cddb8a6d5f8690ecacbd24a1c3a39f4594ffdb5fe2145edbf785189f09df"),
    "formal_control_seed_29": (FORMAL_CKPT_DIR / "control_twohop_full_seed_29.joblib", "3e868c986a68f5a4a97ed481a825ec7b648338b5697bc5d62ccaf0e5253437aa"),
    "formal_control_seed_43": (FORMAL_CKPT_DIR / "control_twohop_full_seed_43.joblib", "797dd0fce30489fa44de585a3b20ef63df3e38038728db5a92addb44d017ad58"),
}

STYLE_CATEGORIES = (
    "high_quality_architectural",
    "high_quality",
    "colorful",
)
STYLE_CATEGORY_CODE = {name: index for index, name in enumerate(STYLE_CATEGORIES)}
METRIC_SCALARS = (
    "auprc",
    "ece",
    "brier",
    "brier_rel",
    "brier_res",
    "brier_unc",
    "brier_decomposition_reconstruction",
    "brier_decomposition_residual",
    "nll",
    "precision",
    "recall",
    "f1",
    "tp",
    "fp",
    "fn",
    "tn",
    "n",
    "positive_count",
)
EVIDENCE_FALLBACK_REASON = (
    "The required load_workspace_dependencies surface for @oai/artifact-tool is not "
    "available in this runtime; the inherited seal authorizes a single row-complete "
    "evidence.csv fallback, and no alternate workbook library was used."
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RuntimeError(f"non-finite numeric output: {value}")
        return value
    if isinstance(value, Path):
        return str(value)
    return value


def assert_cell_output(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.parent != CELL_DIR.resolve():
        raise RuntimeError(f"write escaped E6 cell: {resolved}")
    if resolved in (PREREG_PATH.resolve(), PREREG_CSV_PATH.resolve()):
        raise RuntimeError("inherited seals are immutable")
    return resolved


def atomic_write_text(path: Path, text: str) -> None:
    target = assert_cell_output(path)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(target)


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(
        path,
        json.dumps(json_ready(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import read-only module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def install_deterministic_inference_reduction(screen: Any) -> dict[str, Any]:
    """Replace CUDA atomic relation aggregation with a deterministic CPU reduction.

    Checkpoint weights, relation-specific linear transforms, normalization, and
    the node head remain on the RTX.  Only the relation sum/degree reduction is
    performed as a stable destination-sorted NumPy reduction, which is the
    packet-authorized CPU-assist path and removes CUDA index_add_ ordering noise.
    """

    layer_class = screen.TypedMessageLayer
    original_forward = layer_class.forward
    if getattr(original_forward, "_e6_deterministic_cpu_reduction", False):
        return {
            "name": "destination_sorted_cpu_segmented_sum_v1",
            "installed": True,
            "already_installed": True,
        }

    def deterministic_forward(
        self: Any,
        x: torch.Tensor,
        edge_src: torch.Tensor,
        edge_dst: torch.Tensor,
        edge_type: torch.Tensor,
        message_mode: str = "full",
    ) -> torch.Tensor:
        if torch.is_grad_enabled():
            raise RuntimeError("deterministic CPU reduction is inference-only")
        out = self.self_linear(x)
        if message_mode != "none" and edge_src.numel():
            for relation, linear in enumerate(self.relation_linears):
                mask = edge_type == relation
                if not bool(mask.any()):
                    continue
                src = edge_src[mask]
                dst = edge_dst[mask]
                messages = linear(x[src])
                dst_numpy = dst.detach().cpu().numpy().astype(np.int64, copy=False)
                message_numpy = messages.detach().cpu().numpy()
                order = np.argsort(dst_numpy, kind="stable")
                sorted_dst = dst_numpy[order]
                sorted_messages = message_numpy[order]
                unique_dst, starts, counts = np.unique(
                    sorted_dst, return_index=True, return_counts=True
                )
                reduced = np.add.reduceat(
                    sorted_messages, starts, axis=0, dtype=message_numpy.dtype
                )
                aggregate_numpy = np.zeros(
                    (len(x), x.shape[1]), dtype=message_numpy.dtype
                )
                degree_numpy = np.zeros((len(x),), dtype=message_numpy.dtype)
                aggregate_numpy[unique_dst] = reduced
                degree_numpy[unique_dst] = counts.astype(message_numpy.dtype, copy=False)
                aggregate = torch.from_numpy(aggregate_numpy).to(device=x.device)
                degree = torch.from_numpy(degree_numpy).to(device=x.device)
                out = out + aggregate / degree.clip(min=1.0).unsqueeze(1)
        return self.dropout(torch.nn.functional.gelu(self.norm(out)))

    deterministic_forward._e6_deterministic_cpu_reduction = True  # type: ignore[attr-defined]
    layer_class.forward = deterministic_forward
    return {
        "name": "destination_sorted_cpu_segmented_sum_v1",
        "installed": True,
        "already_installed": False,
        "RTX_operations": "checkpoint linear transforms, layer normalization, GELU, residuals, node head",
        "CPU_auxiliary_operation": "stable destination-sorted relation sum and degree reduction",
        "checkpoint_or_weight_mutation": False,
    }


def source_category(drawing_id: str) -> str:
    for category in STYLE_CATEGORIES:
        if drawing_id.startswith(category + "_"):
            return category
    raise RuntimeError(f"unrecognized source category: {drawing_id}")


def normalized_estimator_params(model: HistGradientBoostingClassifier) -> dict[str, Any]:
    return json.loads(
        json.dumps(
            {
                key: value
                for key, value in model.get_params(deep=False).items()
                if key != "random_state"
            },
            default=str,
        )
    )


@dataclass
class RuntimeGuard:
    started: float
    peak_rss_bytes: int = 0
    rtx_inference_seconds: float = 0.0

    @classmethod
    def create(cls) -> "RuntimeGuard":
        guard = cls(started=time.perf_counter())
        guard.check("initialization")
        return guard

    def check(self, stage: str) -> None:
        elapsed = time.perf_counter() - self.started
        if elapsed > RTX_CAP_SECONDS:
            raise RuntimeError(f"E6 8h cap exceeded at {stage}: {elapsed:.3f}s")
        self.peak_rss_bytes = max(
            self.peak_rss_bytes, int(psutil.Process().memory_info().rss)
        )

    def metrics(self) -> dict[str, Any]:
        elapsed = time.perf_counter() - self.started
        cuda_metrics: dict[str, Any] = {}
        if torch.cuda.is_available():
            cuda_metrics = {
                "peak_cuda_allocated_bytes": int(torch.cuda.max_memory_allocated()),
                "peak_cuda_reserved_bytes": int(torch.cuda.max_memory_reserved()),
            }
        return {
            "wall_seconds": float(elapsed),
            "peak_rss_bytes": int(self.peak_rss_bytes),
            "rtx_inference_seconds": float(self.rtx_inference_seconds),
            "rtx_cap_seconds": RTX_CAP_SECONDS,
            **cuda_metrics,
        }


class GuardedValReader:
    """Reject forbidden splits before any path construction or filesystem call."""

    def __init__(self, manifest: dict[str, Any]):
        records = manifest["frozen"]["drawing_records"]
        self.val_a_ids = {str(row["drawing_id"]) for row in records if row["split"] == "A"}
        self.val_b_ids = {str(row["drawing_id"]) for row in records if row["split"] == "B"}
        self.path_constructions = 0
        self.filesystem_reads = 0
        self.counters = {
            "val_A_ir_reads": 0,
            "val_A_truth_reads": 0,
            "val_B_drawing_reads": 0,
            "test_reads": 0,
            "original_CAD_reads": 0,
            "forbidden_attempts_blocked_before_path_construction": 0,
        }

    def read(self, *, split: str, drawing_id: str, truth: bool = False) -> bytes:
        if split != "A":
            self.counters["forbidden_attempts_blocked_before_path_construction"] += 1
            if split == "B":
                self.counters["val_B_drawing_reads"] += 0
                raise PermissionError("val-B blocked before path construction/read")
            self.counters["test_reads"] += 0
            raise PermissionError("test blocked before path construction/read")
        if drawing_id not in self.val_a_ids:
            self.counters["forbidden_attempts_blocked_before_path_construction"] += 1
            if drawing_id in self.val_b_ids:
                raise PermissionError("val-B drawing blocked before path construction/read")
            raise PermissionError("drawing outside sealed val-A blocked before path construction/read")
        self.path_constructions += 1
        suffix = ".truth.json" if truth else ".segir.json"
        path = (VAL_ROOT / f"{drawing_id}{suffix}").resolve()
        if path.parent != VAL_ROOT.resolve():
            raise PermissionError("val-A path containment failure")
        self.filesystem_reads += 1
        self.counters["val_A_truth_reads" if truth else "val_A_ir_reads"] += 1
        return path.read_bytes()


def val_a_records(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    records = [
        dict(row)
        for row in manifest["frozen"]["drawing_records"]
        if row["split"] == "A"
    ]
    expected_ids = [str(value) for value in manifest["frozen"]["splits"]["A"]["drawing_ids"]]
    observed_ids = [str(row["drawing_id"]) for row in records]
    if observed_ids != expected_ids:
        raise RuntimeError("val-A manifest record order drift")
    return records


def make_calibration_split(
    records: Sequence[dict[str, Any]], prereg: dict[str, Any]
) -> dict[str, Any]:
    by_family: dict[str, list[str]] = defaultdict(list)
    for record in records:
        by_family[str(record["family_id"])].append(str(record["drawing_id"]))
    if len(by_family) != 198:
        raise RuntimeError(f"expected 198 val-A families, found {len(by_family)}")

    def family_key(family_id: str) -> tuple[str, str, str]:
        digest = hashlib.sha256(
            f"{CAL_SPLIT_NAMESPACE}|{CAL_SPLIT_SEED}|{family_id}".encode("utf-8")
        ).hexdigest()
        return digest, family_id, min(by_family[family_id])

    ordered_families = sorted(by_family, key=family_key)
    fit_families = set(ordered_families[:CAL_FIT_FAMILY_COUNT])
    eval_families = set(ordered_families[CAL_FIT_FAMILY_COUNT:])
    assignments = [
        {
            "drawing_id": str(record["drawing_id"]),
            "family_id": str(record["family_id"]),
            "split": "cal-fit" if str(record["family_id"]) in fit_families else "cal-eval",
            "row_count": int(record["row_count"]),
            "source_category": source_category(str(record["drawing_id"])),
        }
        for record in sorted(records, key=lambda row: str(row["drawing_id"]))
    ]
    serialization = "".join(
        f"{row['drawing_id']},{row['family_id']},{row['split']}\n" for row in assignments
    )
    assignment_hash = hashlib.sha256(serialization.encode("utf-8")).hexdigest()

    def subset_summary(split: str) -> dict[str, Any]:
        subset = [row for row in assignments if row["split"] == split]
        drawing_ids = sorted(row["drawing_id"] for row in subset)
        ids_serialization = "".join(f"{drawing_id}\n" for drawing_id in drawing_ids)
        categories = {
            category: sum(row["source_category"] == category for row in subset)
            for category in STYLE_CATEGORIES
        }
        return {
            "drawing_count": len(subset),
            "row_count": sum(int(row["row_count"]) for row in subset),
            "drawing_ids_sha256": hashlib.sha256(ids_serialization.encode("utf-8")).hexdigest(),
            "category_drawing_counts": categories,
        }

    output = {
        "seed": CAL_SPLIT_SEED,
        "namespace": CAL_SPLIT_NAMESPACE,
        "assignment_sha256": assignment_hash,
        "family_intersection_count": len(fit_families & eval_families),
        "fit_families": sorted(fit_families),
        "eval_families": sorted(eval_families),
        "assignments": assignments,
        "cal_fit": subset_summary("cal-fit"),
        "cal_eval": subset_summary("cal-eval"),
    }
    sealed = prereg["calibration_split"]
    checks = (
        output["assignment_sha256"] == sealed["assignment_sha256"],
        output["cal_fit"]["drawing_count"] == sealed["cal_fit"]["drawing_count"],
        output["cal_fit"]["row_count"] == sealed["cal_fit"]["row_count"],
        output["cal_fit"]["drawing_ids_sha256"] == sealed["cal_fit"]["drawing_ids_sha256"],
        output["cal_eval"]["drawing_count"] == sealed["cal_eval"]["drawing_count"],
        output["cal_eval"]["row_count"] == sealed["cal_eval"]["row_count"],
        output["cal_eval"]["drawing_ids_sha256"] == sealed["cal_eval"]["drawing_ids_sha256"],
        output["cal_fit"]["category_drawing_counts"] == sealed["cal_fit"]["category_drawing_counts"],
        output["cal_eval"]["category_drawing_counts"] == sealed["cal_eval"]["category_drawing_counts"],
        output["family_intersection_count"] == sealed["required_family_intersection_count"],
    )
    if not all(checks):
        raise RuntimeError("deterministic calibration split differs from inherited seal")
    return output


def verify_preflight() -> dict[str, Any]:
    cell_files = sorted(path.name for path in CELL_DIR.iterdir())
    allowed_files = {
        "prereg.json",
        "PREREG.csv",
        "e6_calibration_ood.py",
        "results.json",
        "evidence.csv",
        "REPORT.md",
    }
    unexpected = sorted(set(cell_files) - allowed_files)
    if unexpected:
        raise RuntimeError(f"unexpected E6 cell residue; not modifying: {unexpected}")

    seal_hashes = {
        "prereg.json": sha256_file(PREREG_PATH),
        "PREREG.csv": sha256_file(PREREG_CSV_PATH),
    }
    if seal_hashes != EXPECTED_SEAL_HASHES:
        raise RuntimeError(f"inherited seal hash drift: {seal_hashes}")

    observed_hashes: dict[str, str] = {}
    for name, (path, expected) in EXPECTED_INPUT_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(f"missing sealed input {name}: {path}")
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(f"sealed input hash drift for {name}: {observed} != {expected}")
        observed_hashes[name] = observed

    prereg = load_json(PREREG_PATH)
    if prereg["schema"] != "e2.e6_calibration_ood.prereg.v1":
        raise RuntimeError("E6 prereg schema drift")
    if prereg["scope"]["threshold"] != THRESHOLD:
        raise RuntimeError("fixed threshold seal drift")
    if tuple(prereg["arms"]["GNN_A_no_pretrain"]["seeds"]) != SEEDS:
        raise RuntimeError("GNN-A seed seal drift")
    if tuple(prereg["arms"]["control_twohop_GBDT_full"]["seeds"]) != SEEDS:
        raise RuntimeError("control seed seal drift")
    if prereg["scope"]["repository_mutation"] != "forbidden":
        raise RuntimeError("repository mutation seal drift")
    if prereg["scope"]["threshold_search"] != "forbidden":
        raise RuntimeError("threshold-search seal drift")

    manifest = load_json(SPLIT_MANIFEST_PATH)
    if manifest["content_hash"] != EXPECTED_SPLIT_CONTENT_HASH:
        raise RuntimeError("split manifest content hash drift")
    if canonical_hash(manifest["frozen"]) != manifest["content_hash"]:
        raise RuntimeError("split manifest canonical hash mismatch")
    split_a = manifest["frozen"]["splits"]["A"]
    if (int(split_a["drawing_count"]), int(split_a["row_count"])) != (198, 167556):
        raise RuntimeError("sealed val-A universe size drift")
    if int(manifest["frozen"]["family_crossing_count"]) != 0:
        raise RuntimeError("W2-09 family crossing count is nonzero")

    if not torch.cuda.is_available():
        raise RuntimeError("local RTX unavailable")
    gpu_name = torch.cuda.get_device_name(0)
    if "RTX" not in gpu_name.upper():
        raise RuntimeError(f"CUDA device is not an RTX: {gpu_name}")

    return {
        "checked_at_utc": now_iso(),
        "cell_files_at_runtime_start": cell_files,
        "resume_observed_files_before_implementation": ["PREREG.csv", "prereg.json"],
        "unexpected_residue": unexpected,
        "inherited_seals": {
            "mode": "승계 봉인",
            "hashes": seal_hashes,
            "modified": False,
        },
        "input_hashes": observed_hashes,
        "split_manifest_content_hash": manifest["content_hash"],
        "gpu": {
            "name": gpu_name,
            "memory_total_bytes": int(torch.cuda.get_device_properties(0).total_memory),
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
        },
        "evidence_xlsx_status": "BLOCKED_TOOL_UNAVAILABLE",
        "evidence_fallback_reason": EVIDENCE_FALLBACK_REASON,
    }


def _expect_permission_error(operation: Any) -> bool:
    try:
        operation()
    except PermissionError:
        return True
    return False


def assert_universe(universe: str, expected: str, operation: str) -> None:
    if universe != expected:
        raise PermissionError(f"{operation} requires {expected}, received {universe}")


def run_selftest(preflight: dict[str, Any] | None = None) -> dict[str, Any]:
    if preflight is None:
        preflight = verify_preflight()
    prereg = load_json(PREREG_PATH)
    manifest = load_json(SPLIT_MANIFEST_PATH)
    records = val_a_records(manifest)
    split_left = make_calibration_split(records, prereg)
    split_right = make_calibration_split(records, prereg)
    reader = GuardedValReader(manifest)
    val_b_id = next(
        str(row["drawing_id"])
        for row in manifest["frozen"]["drawing_records"]
        if row["split"] == "B"
    )
    before_path = reader.path_constructions
    before_fs = reader.filesystem_reads
    val_b_blocked = _expect_permission_error(
        lambda: reader.read(split="B", drawing_id=val_b_id)
    )
    val_b_pre_path = reader.path_constructions == before_path and reader.filesystem_reads == before_fs
    test_blocked = _expect_permission_error(
        lambda: reader.read(split="test", drawing_id="forbidden_test_probe")
    )
    test_pre_path = reader.path_constructions == before_path and reader.filesystem_reads == before_fs
    fit_guard = _expect_permission_error(
        lambda: assert_universe("cal-eval", "cal-fit", "temperature fit")
    )
    metric_guard = _expect_permission_error(
        lambda: assert_universe("cal-fit", "cal-eval", "reported metric")
    )
    details = {
        "split_determinism": {
            "ok": split_left["assignment_sha256"] == split_right["assignment_sha256"],
            "assignment_sha256": split_left["assignment_sha256"],
        },
        "cal_fit_cal_eval_family_intersection_zero": {
            "ok": split_left["family_intersection_count"] == 0,
            "count": split_left["family_intersection_count"],
        },
        "GNN_A_checkpoint_hashes_unchanged": {
            "ok": all(
                preflight["input_hashes"][f"GNN_A_seed_{seed}"]
                == EXPECTED_INPUT_HASHES[f"GNN_A_seed_{seed}"][1]
                for seed in SEEDS
            ),
            "hashes": {
                str(seed): preflight["input_hashes"][f"GNN_A_seed_{seed}"]
                for seed in SEEDS
            },
        },
        "val_B_blocked_before_path_construction_read": {
            "ok": val_b_blocked and val_b_pre_path,
            "path_construction_delta": reader.path_constructions - before_path,
            "filesystem_read_delta": reader.filesystem_reads - before_fs,
        },
        "test_blocked_before_path_construction_read": {
            "ok": test_blocked and test_pre_path,
            "path_construction_delta": reader.path_constructions - before_path,
            "filesystem_read_delta": reader.filesystem_reads - before_fs,
        },
        "fixed_threshold_0_5": {"ok": THRESHOLD == 0.5, "threshold": THRESHOLD},
        "universe_guards": {
            "ok": fit_guard and metric_guard,
            "temperature_fit_required_universe": "cal-fit",
            "reported_metric_required_universe": "cal-eval",
        },
    }
    return {
        "ok": all(bool(row["ok"]) for row in details.values()),
        "details": details,
    }


def build_val_a_data(
    *,
    formal: Any,
    builder: Any,
    screen: Any,
    w2: Any,
    manifest: dict[str, Any],
    cal_split: dict[str, Any],
    guard: RuntimeGuard,
) -> dict[str, Any]:
    records = val_a_records(manifest)
    assignment_by_drawing = {
        row["drawing_id"]: row for row in cal_split["assignments"]
    }
    reader = GuardedValReader(manifest)
    config = builder.GraphConfig()
    if config.digest() != EXPECTED_GRAPH_CONFIG_HASH:
        raise RuntimeError("frozen graph config hash drift")
    if tuple(builder.FEATURE_NAMES) != tuple(formal.EXPECTED_FEATURE_NAMES):
        raise RuntimeError("17-feature graph allowlist drift")

    row_count = int(manifest["frozen"]["splits"]["A"]["row_count"])
    val_base = np.empty((row_count, len(w2.BASE_FEATURE_NAMES)), dtype=np.float32)
    val_y = np.empty(row_count, dtype=np.int8)
    row_is_cal_fit = np.empty(row_count, dtype=bool)
    row_category_code = np.empty(row_count, dtype=np.int8)
    context_val = np.load(BASELINE_CONTEXT_VAL_PATH, mmap_mode="r")
    twohop_val = np.load(BASELINE_TWOHOP_VAL_PATH, mmap_mode="r")
    if context_val.shape != (row_count, len(w2.CONTEXT_FEATURE_NAMES)):
        raise RuntimeError("sealed val-A context array shape drift")
    if twohop_val.shape != (row_count, len(w2.TWOHOP_FEATURE_NAMES)):
        raise RuntimeError("sealed val-A two-hop array shape drift")

    cubicasa_module, _context_module = w2._load_modules()
    samples: list[Any] = []
    drawing_slices: list[dict[str, Any]] = []
    ir_aggregate = hashlib.sha256()
    truth_aggregate = hashlib.sha256()
    offset = 0
    directed_edges = 0
    max_nodes = 0
    max_edges = 0
    started = time.perf_counter()
    for index, record in enumerate(records):
        guard.check(f"val-A graph build {index + 1}/198")
        drawing_id = str(record["drawing_id"])
        ir_raw = reader.read(split="A", drawing_id=drawing_id, truth=False)
        truth_raw = reader.read(split="A", drawing_id=drawing_id, truth=True)
        ir_aggregate.update(f"{drawing_id}.segir.json".encode("utf-8"))
        ir_aggregate.update(b"\0")
        ir_aggregate.update(hashlib.sha256(ir_raw).digest())
        truth_aggregate.update(f"{drawing_id}.truth.json".encode("utf-8"))
        truth_aggregate.update(b"\0")
        truth_aggregate.update(hashlib.sha256(truth_raw).digest())

        ir = json.loads(ir_raw)
        truth = json.loads(truth_raw)
        graph_result = builder.build_graph(ir, config, collect_edges=True)
        handles = [str(row["handle"]) for row in graph_result["prepared"]["records"]]
        if len(handles) != len(set(handles)):
            raise RuntimeError(f"duplicate graph handles: {drawing_id}")
        wall_handles = {str(value) for value in truth["wall_handles_flat"]}
        graph_labels = np.asarray([handle in wall_handles for handle in handles], dtype=np.int8)
        base, baseline_labels = w2._base_features_labels(ir, truth, cubicasa_module)
        score = cubicasa_module.w1_real_defs.fast_score(
            ir,
            params=cubicasa_module.ce._params(float(cubicasa_module._frozen())),
        )
        baseline_handles = [str(handle) for handle in score["per_handle"]]
        graph_index_by_handle = {handle: position for position, handle in enumerate(handles)}
        if any(handle not in graph_index_by_handle for handle in baseline_handles):
            raise RuntimeError(f"graph/baseline handle universe mismatch: {drawing_id}")
        eval_index = np.asarray(
            [graph_index_by_handle[handle] for handle in baseline_handles], dtype=np.int32
        )
        expected = int(record["row_count"])
        if (
            len(handles) != expected
            or len(baseline_handles) != expected
            or base.shape != (expected, len(w2.BASE_FEATURE_NAMES))
            or baseline_labels is None
            or not np.array_equal(graph_labels[eval_index], baseline_labels)
        ):
            raise RuntimeError(f"val-A row/truth alignment mismatch: {drawing_id}")
        fingerprint = screen.canonical_geometry_fingerprint(ir)
        if fingerprint != str(record["family_fingerprint"]):
            raise RuntimeError(f"geometry family fingerprint drift: {drawing_id}")

        end = offset + expected
        val_base[offset:end] = base
        val_y[offset:end] = baseline_labels
        assignment = assignment_by_drawing[drawing_id]
        row_is_cal_fit[offset:end] = assignment["split"] == "cal-fit"
        category = source_category(drawing_id)
        row_category_code[offset:end] = STYLE_CATEGORY_CODE[category]
        drawing_slices.append(
            {
                "drawing_id": drawing_id,
                "family_id": str(record["family_id"]),
                "calibration_split": assignment["split"],
                "source_category": category,
                "row_start": offset,
                "row_end_exclusive": end,
                "row_count": expected,
            }
        )
        sample = formal.graph_sample_from_result(
            graph_id=f"val-A/{drawing_id}",
            drawing_id=drawing_id,
            family_id=str(record["family_id"]),
            split="val-A",
            result=graph_result,
            labels=graph_labels,
            eval_index=eval_index,
        )
        samples.append(sample)
        directed_edges += len(sample.edge_src)
        max_nodes = max(max_nodes, len(sample.x))
        max_edges = max(max_edges, len(sample.edge_src))
        offset = end
        if (index + 1) % 20 == 0 or index + 1 == len(records):
            print(
                f"[graph:val-A] {index + 1}/198 rows={offset:,} "
                f"seconds={time.perf_counter() - started:.1f}",
                flush=True,
            )
            gc.collect()
        del graph_result, ir, truth, ir_raw, truth_raw

    if offset != row_count:
        raise RuntimeError("final val-A row count mismatch")
    if ir_aggregate.hexdigest() != EXPECTED_VAL_A_IR_AGGREGATE:
        raise RuntimeError("val-A IR aggregate hash drift")
    if truth_aggregate.hexdigest() != EXPECTED_VAL_A_TRUTH_AGGREGATE:
        raise RuntimeError("val-A truth aggregate hash drift")
    if int(row_is_cal_fit.sum()) != int(cal_split["cal_fit"]["row_count"]):
        raise RuntimeError("cal-fit row mask size drift")
    if int((~row_is_cal_fit).sum()) != int(cal_split["cal_eval"]["row_count"]):
        raise RuntimeError("cal-eval row mask size drift")
    if reader.counters["val_B_drawing_reads"] or reader.counters["test_reads"]:
        raise RuntimeError("forbidden read counter became nonzero")

    val_design = np.column_stack((val_base, context_val, twohop_val)).astype(
        np.float32, copy=False
    )
    if val_design.shape != (row_count, len(w2.FULL_FEATURE_NAMES)):
        raise RuntimeError("sealed 30-feature val-A design shape drift")
    return {
        "samples": samples,
        "y": val_y,
        "design": val_design,
        "row_is_cal_fit": row_is_cal_fit,
        "row_category_code": row_category_code,
        "drawing_slices": drawing_slices,
        "audit": {
            "drawing_count": len(records),
            "row_count": row_count,
            "positive_count": int(val_y.sum()),
            "graph_config_sha256": config.digest(),
            "feature_count": len(builder.FEATURE_NAMES),
            "directed_edge_count": directed_edges,
            "max_nodes_per_graph": max_nodes,
            "max_directed_edges_per_graph": max_edges,
            "val_A_ir_aggregate_sha256": ir_aggregate.hexdigest(),
            "val_A_truth_aggregate_sha256": truth_aggregate.hexdigest(),
            "read_counters": reader.counters,
            "path_constructions": reader.path_constructions,
            "filesystem_reads": reader.filesystem_reads,
            "build_seconds": time.perf_counter() - started,
        },
    }


def classification_metrics(y: np.ndarray, probability: np.ndarray) -> dict[str, Any]:
    predicted = np.asarray(probability, dtype=np.float64) >= THRESHOLD
    positive = np.asarray(y, dtype=np.int8) == 1
    tp = int(np.sum(predicted & positive))
    fp = int(np.sum(predicted & ~positive))
    fn = int(np.sum(~predicted & positive))
    tn = int(np.sum(~predicted & ~positive))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "n": int(len(y)),
        "positive_count": int(np.sum(positive)),
        "threshold": THRESHOLD,
    }


def reliability_table(y: np.ndarray, probability: np.ndarray) -> list[dict[str, Any]]:
    y_float = np.asarray(y, dtype=np.float64)
    probability = np.asarray(probability, dtype=np.float64)
    if len(y_float) != len(probability) or not len(y_float):
        raise RuntimeError("reliability input length failure")
    rows: list[dict[str, Any]] = []
    for index in range(10):
        low = index / 10.0
        high = (index + 1) / 10.0
        mask = (probability >= low) & (
            probability <= high if index == 9 else probability < high
        )
        count = int(mask.sum())
        confidence = float(probability[mask].mean()) if count else None
        positive_rate = float(y_float[mask].mean()) if count else None
        signed_gap = (
            float(confidence - positive_rate) if count and confidence is not None and positive_rate is not None else None
        )
        rows.append(
            {
                "bin_index": index,
                "low_inclusive": low,
                "high": high,
                "high_inclusive": index == 9,
                "count": count,
                "mean_probability": confidence,
                "positive_rate": positive_rate,
                "signed_gap_confidence_minus_positive_rate": signed_gap,
                "absolute_gap": abs(signed_gap) if signed_gap is not None else None,
            }
        )
    if sum(row["count"] for row in rows) != len(y_float):
        raise RuntimeError("reliability bins do not cover evaluation rows")
    return rows


def direction_profile(
    y: np.ndarray, probability: np.ndarray, reliability: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    n = len(y)
    weighted_gaps = [
        row["count"] / n * float(row["signed_gap_confidence_minus_positive_rate"])
        for row in reliability
        if row["count"]
    ]
    positive_mass = sum(max(value, 0.0) for value in weighted_gaps)
    negative_mass = sum(min(value, 0.0) for value in weighted_gaps)
    positive_rows = sum(
        row["count"]
        for row in reliability
        if row["count"] and float(row["signed_gap_confidence_minus_positive_rate"]) > 0
    )
    negative_rows = sum(
        row["count"]
        for row in reliability
        if row["count"] and float(row["signed_gap_confidence_minus_positive_rate"]) < 0
    )
    class_metrics = classification_metrics(y, probability)
    prevalence = float(np.mean(y))
    mean_probability = float(np.mean(probability))
    return {
        "signed_gap_definition": "mean_probability - positive_rate; positive sign is overconfidence",
        "recall_at_0_5": class_metrics["recall"],
        "recall_minus_0_99": class_metrics["recall"] - 0.99,
        "mean_probability": mean_probability,
        "positive_rate": prevalence,
        "mean_probability_minus_positive_rate": mean_probability - prevalence,
        "positive_signed_gap_mass": float(positive_mass),
        "negative_signed_gap_mass": float(negative_mass),
        "net_signed_gap_mass": float(sum(weighted_gaps)),
        "positive_signed_gap_bin_row_fraction": positive_rows / n,
        "negative_signed_gap_bin_row_fraction": negative_rows / n,
        "zero_signed_gap_bin_row_fraction": (n - positive_rows - negative_rows) / n,
    }


def metrics_record(
    y: np.ndarray, probability: np.ndarray, *, universe: str
) -> dict[str, Any]:
    assert_universe(universe, "cal-eval", "reported metric")
    y = np.asarray(y, dtype=np.int8)
    probability = np.asarray(probability, dtype=np.float64)
    if len(y) != len(probability) or not len(y) or not np.all(np.isfinite(probability)):
        raise RuntimeError("metric input length/finiteness failure")
    if np.any(probability < 0.0) or np.any(probability > 1.0):
        raise RuntimeError("probability outside [0,1]")
    reliability = reliability_table(y, probability)
    n = len(y)
    ece = sum(
        row["count"] / n * float(row["absolute_gap"])
        for row in reliability
        if row["count"]
    )
    overall_rate = float(np.mean(y))
    brier = float(np.mean((probability - y) ** 2))
    rel = sum(
        row["count"] / n
        * float(row["mean_probability"] - row["positive_rate"]) ** 2
        for row in reliability
        if row["count"]
    )
    res = sum(
        row["count"] / n * float(row["positive_rate"] - overall_rate) ** 2
        for row in reliability
        if row["count"]
    )
    unc = overall_rate * (1.0 - overall_rate)
    reconstruction = rel - res + unc
    clipped = np.clip(probability, PROBABILITY_CLIP, 1.0 - PROBABILITY_CLIP)
    nll = float(-np.mean(y * np.log(clipped) + (1 - y) * np.log1p(-clipped)))
    output = {
        "auprc": float(average_precision_score(y, probability)),
        "ece": float(ece),
        "brier": brier,
        "brier_rel": float(rel),
        "brier_res": float(res),
        "brier_unc": float(unc),
        "brier_decomposition_reconstruction": float(reconstruction),
        "brier_decomposition_residual": float(brier - reconstruction),
        "nll": nll,
        **classification_metrics(y, probability),
        "reliability": reliability,
    }
    output["direction_numeric_profile"] = direction_profile(y, probability, reliability)
    return output


def fit_temperature(
    y: np.ndarray, probability: np.ndarray, *, universe: str
) -> tuple[float, dict[str, Any]]:
    assert_universe(universe, "cal-fit", "temperature fit")
    y = np.asarray(y, dtype=np.float64)
    probability = np.asarray(probability, dtype=np.float64)
    clipped = np.clip(probability, PROBABILITY_CLIP, 1.0 - PROBABILITY_CLIP)
    logits = np.log(clipped / (1.0 - clipped))

    def objective(log_temperature: float) -> float:
        temperature = math.exp(float(log_temperature))
        scaled = expit(logits / temperature)
        scaled = np.clip(scaled, PROBABILITY_CLIP, 1.0 - PROBABILITY_CLIP)
        return float(-np.mean(y * np.log(scaled) + (1.0 - y) * np.log1p(-scaled)))

    result = minimize_scalar(
        objective,
        bounds=TEMPERATURE_LOG_BOUNDS,
        method="bounded",
        options={"xatol": TEMPERATURE_XATOL, "maxiter": TEMPERATURE_MAXITER},
    )
    if not bool(result.success) or not math.isfinite(float(result.x)):
        raise RuntimeError(f"temperature optimizer failed: {result}")
    temperature = math.exp(float(result.x))
    return temperature, {
        "T": float(temperature),
        "log_T": float(result.x),
        "optimizer_success": bool(result.success),
        "optimizer_status": int(result.status),
        "optimizer_nfev": int(result.nfev),
        "optimizer_nit": int(result.nit),
        "log_T_lower_bound": TEMPERATURE_LOG_BOUNDS[0],
        "log_T_upper_bound": TEMPERATURE_LOG_BOUNDS[1],
        "xatol": TEMPERATURE_XATOL,
        "maxiter": TEMPERATURE_MAXITER,
        "fit_row_count": int(len(y)),
        "fit_universe": "cal-fit",
        "objective_value_reported": False,
    }


def apply_temperature(probability: np.ndarray, temperature: float) -> np.ndarray:
    clipped = np.clip(
        np.asarray(probability, dtype=np.float64),
        PROBABILITY_CLIP,
        1.0 - PROBABILITY_CLIP,
    )
    logits = np.log(clipped / (1.0 - clipped))
    return expit(logits / float(temperature)).astype(np.float64, copy=False)


def style_slices(
    *,
    y: np.ndarray,
    probability: np.ndarray,
    category_codes: np.ndarray,
    drawing_counts: dict[str, int],
    universe: str,
) -> list[dict[str, Any]]:
    assert_universe(universe, "cal-eval", "style slice metric")
    pooled_class = classification_metrics(y, probability)
    pooled_ap = float(average_precision_score(y, probability))
    pooled = {
        "category": "pooled",
        "drawing_count": int(sum(drawing_counts.values())),
        "row_count": int(len(y)),
        "positive_count": int(np.sum(y)),
        "auprc": pooled_ap,
        "f1": pooled_class["f1"],
        "precision": pooled_class["precision"],
        "recall": pooled_class["recall"],
        "pooled_minus_category_auprc": 0.0,
        "pooled_minus_category_f1": 0.0,
    }
    rows = [pooled]
    for category in STYLE_CATEGORIES:
        mask = category_codes == STYLE_CATEGORY_CODE[category]
        if not np.any(mask):
            raise RuntimeError(f"empty sealed style slice: {category}")
        class_row = classification_metrics(y[mask], probability[mask])
        ap = float(average_precision_score(y[mask], probability[mask]))
        rows.append(
            {
                "category": category,
                "drawing_count": int(drawing_counts[category]),
                "row_count": int(mask.sum()),
                "positive_count": int(np.sum(y[mask])),
                "auprc": ap,
                "f1": class_row["f1"],
                "precision": class_row["precision"],
                "recall": class_row["recall"],
                "pooled_minus_category_auprc": pooled_ap - ap,
                "pooled_minus_category_f1": pooled_class["f1"] - class_row["f1"],
            }
        )
    return rows


def full_val_reference_metrics(y: np.ndarray, probability: np.ndarray) -> dict[str, Any]:
    reliability = reliability_table(y, probability)
    ece = sum(
        row["count"] / len(y) * float(row["absolute_gap"])
        for row in reliability
        if row["count"]
    )
    return {
        "auprc": float(average_precision_score(y, probability)),
        "ece": float(ece),
        **classification_metrics(y, probability),
    }


def predict_frozen_gnn_a(
    *,
    formal: Any,
    screen: Any,
    samples: Sequence[Any],
    guard: RuntimeGuard,
    reduction_info: dict[str, Any],
) -> tuple[dict[int, np.ndarray], list[dict[str, Any]]]:
    predictions: dict[int, np.ndarray] = {}
    records: list[dict[str, Any]] = []
    device = torch.device("cuda:0")
    relation_count = 6
    for seed in SEEDS:
        guard.check(f"GNN-A seed {seed} load")
        checkpoint_path = FORMAL_CKPT_DIR / f"GNN_A_no_pretrain_seed_{seed}.pt"
        before_hash = sha256_file(checkpoint_path)
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        if (
            checkpoint.get("schema") != "e2.gnn_formal.gnn_checkpoint.v1"
            or checkpoint.get("arm") != "GNN_A_no_pretrain"
            or int(checkpoint.get("seed")) != seed
            or int(checkpoint.get("relation_count")) != relation_count
            or tuple(checkpoint.get("feature_names", [])) != tuple(formal.EXPECTED_FEATURE_NAMES)
            or checkpoint.get("fit_universe") != "train only"
            or checkpoint.get("evaluation_universe") != "val-A only"
        ):
            raise RuntimeError(f"GNN-A checkpoint contract drift for seed {seed}")
        config = formal.FormalConfig(**checkpoint["config"])
        model = formal.NodeGNN(screen, relation_count, config)
        model.load_state_dict(checkpoint["state_dict"], strict=True)
        model.to(device)
        torch.cuda.synchronize()
        started = time.perf_counter()
        probability = formal.predict_node_model(
            model=model,
            samples=samples,
            device=device,
            resources=guard,
            seed=seed,
        )
        torch.cuda.synchronize()
        inference_seconds = time.perf_counter() - started
        guard.rtx_inference_seconds += inference_seconds
        repeat_started = time.perf_counter()
        repeat_probability = formal.predict_node_model(
            model=model,
            samples=samples,
            device=device,
            resources=guard,
            seed=seed,
        )
        torch.cuda.synchronize()
        repeat_inference_seconds = time.perf_counter() - repeat_started
        guard.rtx_inference_seconds += repeat_inference_seconds
        repeat_equal = np.array_equal(probability, repeat_probability)
        repeat_max_absolute_delta = float(
            np.max(np.abs(probability - repeat_probability), initial=0.0)
        )
        if not repeat_equal:
            raise RuntimeError(
                f"deterministic repeat inference differs for GNN-A seed {seed}: "
                f"max_abs_delta={repeat_max_absolute_delta}"
            )
        after_hash = sha256_file(checkpoint_path)
        if before_hash != after_hash or after_hash != EXPECTED_INPUT_HASHES[f"GNN_A_seed_{seed}"][1]:
            raise RuntimeError(f"GNN-A checkpoint mutated during inference: seed {seed}")
        predictions[seed] = probability
        records.append(
            {
                "seed": seed,
                "checkpoint_path": str(checkpoint_path),
                "checkpoint_sha256_before": before_hash,
                "checkpoint_sha256_after": after_hash,
                "checkpoint_mutated": False,
                "inference_seconds": inference_seconds,
                "repeat_inference_seconds": repeat_inference_seconds,
                "inference_row_count": int(len(probability)),
                "device": str(device),
                "relation_aggregation": reduction_info,
                "repeat_probability_bitwise_equal": repeat_equal,
                "repeat_probability_max_absolute_delta": repeat_max_absolute_delta,
            }
        )
        print(
            f"[GNN-A seed={seed}] rows={len(probability):,} "
            f"inference_seconds={inference_seconds:.2f} "
            f"repeat_seconds={repeat_inference_seconds:.2f} bitwise_equal={int(repeat_equal)}",
            flush=True,
        )
        del model, checkpoint, repeat_probability
        torch.cuda.empty_cache()
        gc.collect()
    return predictions, records


def fit_classical_control(
    *,
    w2: Any,
    prereg: dict[str, Any],
    val_design: np.ndarray,
    guard: RuntimeGuard,
) -> tuple[dict[int, np.ndarray], list[dict[str, Any]]]:
    with np.load(TRAIN_NPZ_PATH, allow_pickle=False) as archive:
        train_y = np.asarray(archive["y"], dtype=np.int8)
    train_design = np.load(BASELINE_DESIGN_TRAIN_PATH, mmap_mode="r")
    if train_design.shape != (len(train_y), len(w2.FULL_FEATURE_NAMES)):
        raise RuntimeError("sealed full train design shape drift")
    expected_params = prereg["arms"]["control_twohop_GBDT_full"][
        "estimator_parameters_except_seed"
    ]
    predictions: dict[int, np.ndarray] = {}
    records: list[dict[str, Any]] = []
    for seed in SEEDS:
        guard.check(f"two-hop classical train-only fit seed {seed}")
        model = HistGradientBoostingClassifier(random_state=seed)
        actual_params = normalized_estimator_params(model)
        if actual_params != expected_params:
            raise RuntimeError(
                f"HistGradientBoosting parameters drift for seed {seed}: {actual_params}"
            )
        started = time.perf_counter()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model.fit(train_design, train_y)
        fit_seconds = time.perf_counter() - started
        probability = model.predict_proba(val_design)[:, 1].astype(np.float64, copy=False)
        predictions[seed] = probability
        records.append(
            {
                "seed": seed,
                "fit_universe": "sealed train labels and 30-feature train design only",
                "evaluation_universe": "sealed val-A only",
                "fit_seconds": fit_seconds,
                "n_iter": int(model.n_iter_),
                "warning_count": len(caught),
                "warnings": [str(item.message)[:300] for item in caught],
                "model_persisted": False,
                "estimator_parameters_except_seed": actual_params,
            }
        )
        print(
            f"[control seed={seed}] train_rows={len(train_y):,} "
            f"fit_seconds={fit_seconds:.2f}",
            flush=True,
        )
        del model
        gc.collect()
    return predictions, records


def compare_formal_reference(
    *, arm: str, seed: int, measured: dict[str, Any], formal_results: dict[str, Any]
) -> dict[str, Any]:
    reference = next(
        row
        for row in formal_results["metrics"]["arms"][arm]["per_seed"]
        if int(row["seed"]) == seed
    )
    deltas = {
        metric: float(measured[metric]) - float(reference[metric])
        for metric in ("auprc", "ece", "f1", "precision", "recall")
    }
    count_deltas = {
        metric: int(measured[metric]) - int(reference[metric])
        for metric in ("tp", "fp", "fn", "tn", "n", "positive_count")
    }
    tolerances = {
        # The formal result was captured from the in-memory trained model.  A
        # fresh frozen-checkpoint CUDA pass can reorder floating reductions by
        # a few ulps while preserving every threshold decision/count exactly.
        "auprc": 2e-6,
        "ece": 1e-9,
        "f1": 1e-15,
        "precision": 1e-15,
        "recall": 1e-15,
    }
    within_tolerance = {
        metric: abs(value) <= tolerances[metric] for metric, value in deltas.items()
    }
    ok = all(within_tolerance.values()) and not any(count_deltas.values())
    if not ok:
        raise RuntimeError(
            f"full val-A inference/refit does not reproduce formal reference {arm} seed {seed}: "
            f"{deltas}, {count_deltas}"
        )
    return {
        "ok": ok,
        "numeric_deltas": deltas,
        "absolute_tolerances": tolerances,
        "within_tolerance": within_tolerance,
        "count_deltas": count_deltas,
    }


def evaluate_arms(
    *,
    predictions: dict[str, dict[int, np.ndarray]],
    y: np.ndarray,
    row_is_cal_fit: np.ndarray,
    row_category_code: np.ndarray,
    cal_split: dict[str, Any],
    formal_results: dict[str, Any],
) -> dict[str, Any]:
    fit_mask = row_is_cal_fit
    eval_mask = ~fit_mask
    y_fit = y[fit_mask]
    y_eval = y[eval_mask]
    eval_categories = row_category_code[eval_mask]
    drawing_counts = cal_split["cal_eval"]["category_drawing_counts"]
    output: dict[str, Any] = {}
    for arm, seed_predictions in predictions.items():
        per_seed: list[dict[str, Any]] = []
        for seed in SEEDS:
            probability = np.asarray(seed_predictions[seed], dtype=np.float64)
            if len(probability) != len(y):
                raise RuntimeError(f"prediction row count drift: {arm} seed {seed}")
            full_metrics = full_val_reference_metrics(y, probability)
            reference_check = compare_formal_reference(
                arm=arm,
                seed=seed,
                measured=full_metrics,
                formal_results=formal_results,
            )
            temperature, temperature_record = fit_temperature(
                y_fit, probability[fit_mask], universe="cal-fit"
            )
            scaled = apply_temperature(probability, temperature)
            before_metrics = metrics_record(
                y_eval, probability[eval_mask], universe="cal-eval"
            )
            after_metrics = metrics_record(y_eval, scaled[eval_mask], universe="cal-eval")
            before_style = style_slices(
                y=y_eval,
                probability=probability[eval_mask],
                category_codes=eval_categories,
                drawing_counts=drawing_counts,
                universe="cal-eval",
            )
            after_style = style_slices(
                y=y_eval,
                probability=scaled[eval_mask],
                category_codes=eval_categories,
                drawing_counts=drawing_counts,
                universe="cal-eval",
            )
            decision_mismatch = int(
                np.sum(
                    (probability[eval_mask] >= THRESHOLD)
                    != (scaled[eval_mask] >= THRESHOLD)
                )
            )
            style_invariance = []
            for before_row, after_row in zip(before_style, after_style, strict=True):
                if before_row["category"] != after_row["category"]:
                    raise RuntimeError("style slice ordering drift")
                style_invariance.append(
                    {
                        "category": before_row["category"],
                        "auprc_delta_after_minus_before": after_row["auprc"] - before_row["auprc"],
                        "f1_delta_after_minus_before": after_row["f1"] - before_row["f1"],
                    }
                )
            max_ap_delta = max(abs(row["auprc_delta_after_minus_before"]) for row in style_invariance)
            max_f1_delta = max(abs(row["f1_delta_after_minus_before"]) for row in style_invariance)
            if decision_mismatch != 0 or max_f1_delta > 1e-15 or max_ap_delta > 1e-12:
                raise RuntimeError(
                    f"positive-temperature ranking/decision invariant failed: {arm} seed {seed}"
                )
            per_seed.append(
                {
                    "seed": seed,
                    "temperature_fit": temperature_record,
                    "full_val_A_reference_numeric_check": {
                        "metrics": full_metrics,
                        "comparison": reference_check,
                    },
                    "cal_eval": {
                        "before_temperature": {
                            "metrics": before_metrics,
                            "style_slices": before_style,
                        },
                        "after_temperature": {
                            "metrics": after_metrics,
                            "style_slices": after_style,
                        },
                    },
                    "temperature_invariance": {
                        "decision_mismatch_count_at_0_5": decision_mismatch,
                        "pooled_auprc_delta_after_minus_before": after_metrics["auprc"] - before_metrics["auprc"],
                        "pooled_f1_delta_after_minus_before": after_metrics["f1"] - before_metrics["f1"],
                        "max_absolute_style_auprc_delta": max_ap_delta,
                        "max_absolute_style_f1_delta": max_f1_delta,
                        "style_rows": style_invariance,
                    },
                }
            )
        output[arm] = {
            "per_seed": per_seed,
            "summary": aggregate_arm(per_seed),
        }
    return output


def distribution(values: Iterable[float]) -> dict[str, Any]:
    array = np.asarray(list(values), dtype=np.float64)
    return {
        "mean": float(array.mean()),
        "std_population": float(array.std(ddof=0)),
        "min": float(array.min()),
        "max": float(array.max()),
    }


def aggregate_arm(per_seed: Sequence[dict[str, Any]]) -> dict[str, Any]:
    states: dict[str, Any] = {}
    for state in ("before_temperature", "after_temperature"):
        states[state] = {
            metric: distribution(
                row["cal_eval"][state]["metrics"][metric] for row in per_seed
            )
            for metric in METRIC_SCALARS
        }
        states[state]["direction_numeric_profile"] = {
            key: distribution(
                row["cal_eval"][state]["metrics"]["direction_numeric_profile"][key]
                for row in per_seed
            )
            for key in (
                "recall_at_0_5",
                "recall_minus_0_99",
                "mean_probability",
                "positive_rate",
                "mean_probability_minus_positive_rate",
                "positive_signed_gap_mass",
                "negative_signed_gap_mass",
                "net_signed_gap_mass",
                "positive_signed_gap_bin_row_fraction",
                "negative_signed_gap_bin_row_fraction",
                "zero_signed_gap_bin_row_fraction",
            )
        }
        states[state]["style_slices"] = {}
        for category in ("pooled", *STYLE_CATEGORIES):
            category_rows = [
                next(
                    item
                    for item in row["cal_eval"][state]["style_slices"]
                    if item["category"] == category
                )
                for row in per_seed
            ]
            states[state]["style_slices"][category] = {
                metric: distribution(item[metric] for item in category_rows)
                for metric in (
                    "auprc",
                    "f1",
                    "precision",
                    "recall",
                    "pooled_minus_category_auprc",
                    "pooled_minus_category_f1",
                )
            }
            states[state]["style_slices"][category].update(
                {
                    "drawing_count": category_rows[0]["drawing_count"],
                    "row_count": category_rows[0]["row_count"],
                    "positive_count": category_rows[0]["positive_count"],
                }
            )
    return {
        "seed_count": len(per_seed),
        "temperature_T": distribution(row["temperature_fit"]["T"] for row in per_seed),
        "states": states,
    }


def stable_numeric_measurement_sha256(
    *, calibration_split: dict[str, Any], arms: dict[str, Any]
) -> str:
    """Hash the E6 measurement payload while excluding declared volatile fields.

    Supplemental comparisons to the earlier in-memory formal run are excluded;
    the hash covers the deterministic split, fitted temperatures, all cal-eval
    metrics/bins/slices, invariance measurements, and seed summaries.
    """

    stable_arms: dict[str, Any] = {}
    for arm, arm_result in arms.items():
        stable_arms[arm] = {
            "per_seed": [
                {
                    "seed": row["seed"],
                    "temperature_fit": row["temperature_fit"],
                    "cal_eval": row["cal_eval"],
                    "temperature_invariance": row["temperature_invariance"],
                }
                for row in arm_result["per_seed"]
            ],
            "summary": arm_result["summary"],
        }
    return canonical_hash(
        json_ready(
            {
                "calibration_split": calibration_split,
                "arms": stable_arms,
            }
        )
    )


def evidence_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, value in result["preflight"]["inherited_seals"]["hashes"].items():
        rows.append(
            {
                "record_type": "inherited_seal",
                "name": name,
                "path": str(CELL_DIR / name),
                "sha256": value,
                "status": "adopted_unchanged",
            }
        )
    for name, value in result["preflight"]["input_hashes"].items():
        rows.append(
            {
                "record_type": "input_hash",
                "name": name,
                "path": str(EXPECTED_INPUT_HASHES[name][0]),
                "sha256": value,
                "status": "matched_seal",
            }
        )
    for name, detail in result["selftest"]["details"].items():
        rows.append(
            {
                "record_type": "selftest",
                "name": name,
                "status": "ok" if detail["ok"] else "error",
                "value": int(bool(detail["ok"])),
                "details_json": json.dumps(json_ready(detail), ensure_ascii=False, sort_keys=True),
            }
        )
    rows.append(
        {
            "record_type": "reproducibility",
            "name": "stable_numeric_measurement_sha256",
            "sha256": result["reproducibility"]["stable_numeric_measurement_sha256"],
            "status": "bitwise_repeat_ok"
            if result["reproducibility"]["GNN_A_repeat_probability_bitwise_equal_all_seeds"]
            else "error",
            "value": int(
                result["reproducibility"]["GNN_A_repeat_probability_bitwise_equal_all_seeds"]
            ),
        }
    )
    for assignment in result["calibration_split"]["assignments"]:
        rows.append(
            {
                "record_type": "split_assignment",
                "drawing_id": assignment["drawing_id"],
                "family_id": assignment["family_id"],
                "calibration_split": assignment["split"],
                "category": assignment["source_category"],
                "count": assignment["row_count"],
            }
        )
    for arm, arm_result in result["arms"].items():
        for seed_row in arm_result["per_seed"]:
            seed = seed_row["seed"]
            for key, value in seed_row["temperature_fit"].items():
                if isinstance(value, (int, float, bool)):
                    rows.append(
                        {
                            "record_type": "temperature_fit",
                            "arm": arm,
                            "seed": seed,
                            "metric": key,
                            "value": value,
                            "universe": "cal-fit",
                        }
                    )
            for state in ("before_temperature", "after_temperature"):
                state_result = seed_row["cal_eval"][state]
                metrics = state_result["metrics"]
                for metric in METRIC_SCALARS:
                    rows.append(
                        {
                            "record_type": "metric",
                            "arm": arm,
                            "seed": seed,
                            "state": state,
                            "metric": metric,
                            "value": metrics[metric],
                            "universe": "cal-eval",
                        }
                    )
                for key, value in metrics["direction_numeric_profile"].items():
                    if isinstance(value, (int, float)):
                        rows.append(
                            {
                                "record_type": "direction_numeric_profile",
                                "arm": arm,
                                "seed": seed,
                                "state": state,
                                "metric": key,
                                "value": value,
                                "universe": "cal-eval",
                            }
                        )
                for bin_row in metrics["reliability"]:
                    rows.append(
                        {
                            "record_type": "reliability_bin",
                            "arm": arm,
                            "seed": seed,
                            "state": state,
                            "bin_index": bin_row["bin_index"],
                            "bin_low": bin_row["low_inclusive"],
                            "bin_high": bin_row["high"],
                            "count": bin_row["count"],
                            "mean_probability": bin_row["mean_probability"],
                            "positive_rate": bin_row["positive_rate"],
                            "signed_gap": bin_row["signed_gap_confidence_minus_positive_rate"],
                            "absolute_gap": bin_row["absolute_gap"],
                            "universe": "cal-eval",
                        }
                    )
                for style_row in state_result["style_slices"]:
                    rows.append(
                        {
                            "record_type": "style_slice",
                            "arm": arm,
                            "seed": seed,
                            "state": state,
                            "category": style_row["category"],
                            "drawing_count": style_row["drawing_count"],
                            "count": style_row["row_count"],
                            "positive_count": style_row["positive_count"],
                            "auprc": style_row["auprc"],
                            "f1": style_row["f1"],
                            "precision": style_row["precision"],
                            "recall": style_row["recall"],
                            "pooled_minus_category_auprc": style_row["pooled_minus_category_auprc"],
                            "pooled_minus_category_f1": style_row["pooled_minus_category_f1"],
                            "universe": "cal-eval",
                        }
                    )
        for state, summary in arm_result["summary"]["states"].items():
            for metric in METRIC_SCALARS:
                rows.append(
                    {
                        "record_type": "seed_summary",
                        "arm": arm,
                        "state": state,
                        "metric": metric,
                        "value": summary[metric]["mean"],
                        "std_population": summary[metric]["std_population"],
                        "universe": "cal-eval",
                    }
                )
            for metric, stats in summary["direction_numeric_profile"].items():
                rows.append(
                    {
                        "record_type": "direction_seed_summary",
                        "arm": arm,
                        "state": state,
                        "metric": metric,
                        "value": stats["mean"],
                        "std_population": stats["std_population"],
                        "universe": "cal-eval",
                    }
                )
            for category, category_summary in summary["style_slices"].items():
                for metric in (
                    "auprc",
                    "f1",
                    "precision",
                    "recall",
                    "pooled_minus_category_auprc",
                    "pooled_minus_category_f1",
                ):
                    stats = category_summary[metric]
                    rows.append(
                        {
                            "record_type": "style_seed_summary",
                            "arm": arm,
                            "state": state,
                            "category": category,
                            "metric": metric,
                            "value": stats["mean"],
                            "std_population": stats["std_population"],
                            "drawing_count": category_summary["drawing_count"],
                            "count": category_summary["row_count"],
                            "positive_count": category_summary["positive_count"],
                            "universe": "cal-eval",
                        }
                    )
    return rows


def write_evidence_csv(rows: Sequence[dict[str, Any]]) -> None:
    fieldnames = [
        "record_type",
        "name",
        "path",
        "sha256",
        "status",
        "arm",
        "seed",
        "state",
        "universe",
        "metric",
        "value",
        "std_population",
        "drawing_id",
        "family_id",
        "calibration_split",
        "category",
        "drawing_count",
        "count",
        "positive_count",
        "bin_index",
        "bin_low",
        "bin_high",
        "mean_probability",
        "positive_rate",
        "signed_gap",
        "absolute_gap",
        "auprc",
        "f1",
        "precision",
        "recall",
        "pooled_minus_category_auprc",
        "pooled_minus_category_f1",
        "details_json",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json_ready(value) for key, value in row.items()})
    atomic_write_text(EVIDENCE_CSV_PATH, stream.getvalue())


def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
        *("| " + " | ".join(fmt(value) for value in row) + " |" for row in rows),
    ]


def render_report(result: dict[str, Any]) -> str:
    seals = result["preflight"]["inherited_seals"]["hashes"]
    lines = [
        "# E6 Calibration and IID Style-Slice Numeric Report",
        "",
        f"승계 봉인 SHA-256 — `prereg.json`: `{seals['prereg.json']}`",
        f"승계 봉인 SHA-256 — `PREREG.csv`: `{seals['PREREG.csv']}`",
        "",
        "The two inherited seals were adopted unchanged; no re-sealing was performed.",
        "",
        "## Execution scope",
        "",
        "- Frozen GNN-A checkpoints: inference only; seeds 17, 29, 43.",
        "- RTX inference with deterministic destination-sorted CPU auxiliary relation reduction; two bitwise comparison passes per seed.",
        "- Classical control: fresh sealed 30-feature HistGradientBoosting fit on train-only labels/design.",
        "- Calibration split: deterministic family-hash cal-fit/cal-eval; temperature fit only on cal-fit.",
        "- Reported measurement universe: cal-eval only.",
        "- Classification threshold: 0.5 fixed; threshold search count: 0.",
        "- Band adjudication output count: 0.",
        "- Repository file mutation count: 0; git command count after packet read: 0; subagent count: 0.",
        "",
        "## Inherited band text (not adjudicated)",
        "",
        *[f"- {text}" for text in result["contract"]["sealed_band_text"]],
        "",
        "## Selftest",
        "",
        *markdown_table(
            ("test", "ok", "numeric/detail"),
            [
                (
                    name,
                    int(detail["ok"]),
                    json.dumps(json_ready(detail), ensure_ascii=False, sort_keys=True),
                )
                for name, detail in result["selftest"]["details"].items()
            ],
        ),
        "",
        "## Calibration split",
        "",
        f"Assignment SHA-256: `{result['calibration_split']['assignment_sha256']}`",
        "",
        *markdown_table(
            ("split", "drawings", "rows", "families_crossing", *STYLE_CATEGORIES),
            [
                (
                    split_name,
                    result["calibration_split"][split_name]["drawing_count"],
                    result["calibration_split"][split_name]["row_count"],
                    result["calibration_split"]["family_intersection_count"],
                    *(
                        result["calibration_split"][split_name]["category_drawing_counts"][category]
                        for category in STYLE_CATEGORIES
                    ),
                )
                for split_name in ("cal_fit", "cal_eval")
            ],
        ),
        "",
        "## Per-seed cal-eval measurements",
        "",
    ]
    metric_headers = (
        "arm",
        "seed",
        "state",
        "T",
        "ECE",
        "Brier",
        "REL",
        "RES",
        "UNC",
        "decomp residual",
        "NLL",
        "AUPRC",
        "P",
        "R",
        "F1",
        "TP",
        "FP",
        "FN",
        "TN",
    )
    metric_rows = []
    for arm, arm_result in result["arms"].items():
        for seed_row in arm_result["per_seed"]:
            for state in ("before_temperature", "after_temperature"):
                metrics = seed_row["cal_eval"][state]["metrics"]
                metric_rows.append(
                    (
                        arm,
                        seed_row["seed"],
                        state,
                        seed_row["temperature_fit"]["T"],
                        metrics["ece"],
                        metrics["brier"],
                        metrics["brier_rel"],
                        metrics["brier_res"],
                        metrics["brier_unc"],
                        metrics["brier_decomposition_residual"],
                        metrics["nll"],
                        metrics["auprc"],
                        metrics["precision"],
                        metrics["recall"],
                        metrics["f1"],
                        metrics["tp"],
                        metrics["fp"],
                        metrics["fn"],
                        metrics["tn"],
                    )
                )
    lines.extend(markdown_table(metric_headers, metric_rows))
    lines.extend(["", "## Three-seed mean and population SD", ""])
    summary_rows = []
    for arm, arm_result in result["arms"].items():
        for state in ("before_temperature", "after_temperature"):
            summary = arm_result["summary"]["states"][state]
            for metric in (
                "ece",
                "brier",
                "brier_rel",
                "brier_res",
                "brier_unc",
                "brier_decomposition_residual",
                "nll",
                "auprc",
                "precision",
                "recall",
                "f1",
            ):
                summary_rows.append(
                    (
                        arm,
                        state,
                        metric,
                        summary[metric]["mean"],
                        summary[metric]["std_population"],
                        summary[metric]["min"],
                        summary[metric]["max"],
                    )
                )
        summary_rows.append(
            (
                arm,
                "temperature_fit",
                "T",
                arm_result["summary"]["temperature_T"]["mean"],
                arm_result["summary"]["temperature_T"]["std_population"],
                arm_result["summary"]["temperature_T"]["min"],
                arm_result["summary"]["temperature_T"]["max"],
            )
        )
    lines.extend(markdown_table(("arm", "state", "metric", "mean", "SD(pop)", "min", "max"), summary_rows))
    lines.extend(["", "## IID source-category style slices (cal-eval)", ""])
    style_rows = []
    for arm, arm_result in result["arms"].items():
        for seed_row in arm_result["per_seed"]:
            for state in ("before_temperature", "after_temperature"):
                for row in seed_row["cal_eval"][state]["style_slices"]:
                    style_rows.append(
                        (
                            arm,
                            seed_row["seed"],
                            state,
                            row["category"],
                            row["drawing_count"],
                            row["row_count"],
                            row["auprc"],
                            row["f1"],
                            row["pooled_minus_category_auprc"],
                            row["pooled_minus_category_f1"],
                        )
                    )
    lines.extend(
        markdown_table(
            (
                "arm",
                "seed",
                "state",
                "category",
                "drawings",
                "rows",
                "AUPRC",
                "F1",
                "pooled-category AUPRC",
                "pooled-category F1",
            ),
            style_rows,
        )
    )
    lines.extend(["", "## Three-seed style-slice mean and population SD", ""])
    style_summary_rows = []
    for arm, arm_result in result["arms"].items():
        for state in ("before_temperature", "after_temperature"):
            summaries = arm_result["summary"]["states"][state]["style_slices"]
            for category in ("pooled", *STYLE_CATEGORIES):
                for metric in (
                    "auprc",
                    "f1",
                    "pooled_minus_category_auprc",
                    "pooled_minus_category_f1",
                ):
                    stats = summaries[category][metric]
                    style_summary_rows.append(
                        (
                            arm,
                            state,
                            category,
                            summaries[category]["drawing_count"],
                            summaries[category]["row_count"],
                            metric,
                            stats["mean"],
                            stats["std_population"],
                        )
                    )
    lines.extend(
        markdown_table(
            ("arm", "state", "category", "drawings", "rows", "metric", "mean", "SD(pop)"),
            style_summary_rows,
        )
    )
    lines.extend(["", "## Reliability diagram numeric table (cal-eval)", ""])
    reliability_rows = []
    for arm, arm_result in result["arms"].items():
        for seed_row in arm_result["per_seed"]:
            for state in ("before_temperature", "after_temperature"):
                for row in seed_row["cal_eval"][state]["metrics"]["reliability"]:
                    reliability_rows.append(
                        (
                            arm,
                            seed_row["seed"],
                            state,
                            row["bin_index"],
                            row["low_inclusive"],
                            row["high"],
                            row["count"],
                            row["mean_probability"],
                            row["positive_rate"],
                            row["signed_gap_confidence_minus_positive_rate"],
                            row["absolute_gap"],
                        )
                    )
    lines.extend(
        markdown_table(
            ("arm", "seed", "state", "bin", "low", "high", "count", "conf", "acc", "signed gap", "abs gap"),
            reliability_rows,
        )
    )
    lines.extend(["", "## Direction numeric profile (cal-eval)", ""])
    direction_rows = []
    for arm, arm_result in result["arms"].items():
        for seed_row in arm_result["per_seed"]:
            for state in ("before_temperature", "after_temperature"):
                profile = seed_row["cal_eval"][state]["metrics"]["direction_numeric_profile"]
                direction_rows.append(
                    (
                        arm,
                        seed_row["seed"],
                        state,
                        profile["recall_at_0_5"],
                        profile["recall_minus_0_99"],
                        profile["mean_probability_minus_positive_rate"],
                        profile["positive_signed_gap_mass"],
                        profile["negative_signed_gap_mass"],
                        profile["positive_signed_gap_bin_row_fraction"],
                        profile["negative_signed_gap_bin_row_fraction"],
                    )
                )
    lines.extend(
        markdown_table(
            (
                "arm",
                "seed",
                "state",
                "recall@0.5",
                "recall-0.99",
                "mean_p-positive_rate",
                "positive gap mass",
                "negative gap mass",
                "positive-bin row frac",
                "negative-bin row frac",
            ),
            direction_rows,
        )
    )
    lines.extend(
        [
            "",
            "Signed gap is mean probability minus positive rate; positive sign is overconfidence.",
            "",
            "## Temperature invariance measurements",
            "",
        ]
    )
    invariant_rows = []
    for arm, arm_result in result["arms"].items():
        for seed_row in arm_result["per_seed"]:
            inv = seed_row["temperature_invariance"]
            invariant_rows.append(
                (
                    arm,
                    seed_row["seed"],
                    inv["decision_mismatch_count_at_0_5"],
                    inv["pooled_auprc_delta_after_minus_before"],
                    inv["pooled_f1_delta_after_minus_before"],
                    inv["max_absolute_style_auprc_delta"],
                    inv["max_absolute_style_f1_delta"],
                )
            )
    lines.extend(
        markdown_table(
            (
                "arm",
                "seed",
                "decision mismatch",
                "pooled AUPRC delta",
                "pooled F1 delta",
                "max style AUPRC delta",
                "max style F1 delta",
            ),
            invariant_rows,
        )
    )
    lines.extend(
        [
            "",
            "## Data and resource audit",
            "",
            *markdown_table(
                ("measurement", "value"),
                [
                    ("val-A drawings", result["data_audit"]["drawing_count"]),
                    ("val-A rows", result["data_audit"]["row_count"]),
                    ("val-A positives", result["data_audit"]["positive_count"]),
                    ("val-A directed edges", result["data_audit"]["directed_edge_count"]),
                    ("val-B reads", result["execution_scope"]["val_B_drawing_reads"]),
                    ("test reads", result["execution_scope"]["test_reads"]),
                    ("original CAD reads", result["execution_scope"]["original_CAD_reads"]),
                    ("RTX inference seconds", result["resource_usage"]["rtx_inference_seconds"]),
                    ("wall seconds", result["resource_usage"]["wall_seconds"]),
                    ("peak RSS bytes", result["resource_usage"]["peak_rss_bytes"]),
                    ("peak CUDA allocated bytes", result["resource_usage"].get("peak_cuda_allocated_bytes", 0)),
                ],
            ),
            "",
            "## Explicit style limitation",
            "",
            result["contract"]["style_limit"],
            "",
            "## Reproducibility",
            "",
            result["contract"]["reproducibility_claim"],
            "",
            f"Stable numeric measurement SHA-256: `{result['reproducibility']['stable_numeric_measurement_sha256']}`",
            f"GNN-A repeat probability bitwise equality (all seeds): {int(result['reproducibility']['GNN_A_repeat_probability_bitwise_equal_all_seeds'])}",
            "",
            "## Unresolved",
            "",
            *[f"- {item}" for item in result["unresolved"]],
            "",
            "## Artifact hashes",
            "",
            *markdown_table(
                ("artifact", "SHA-256"),
                [(name, value) for name, value in result["artifacts"].items() if name.endswith("sha256")],
            ),
            "",
            "CELL_COMPLETE: e6_calibration_ood",
        ]
    )
    return "\n".join(lines) + "\n"


def execute() -> dict[str, Any]:
    guard = RuntimeGuard.create()
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    preflight = verify_preflight()
    selftest = run_selftest(preflight)
    if not selftest["ok"]:
        raise RuntimeError(f"E6 selftest failed: {selftest}")
    print("[selftest] all sealed guards OK", flush=True)

    prereg = load_json(PREREG_PATH)
    manifest = load_json(SPLIT_MANIFEST_PATH)
    cal_split = make_calibration_split(val_a_records(manifest), prereg)
    formal = load_module(FORMAL_RUNNER_PATH, "e6_formal_ro")
    builder = load_module(GRAPH_BUILDER_PATH, "e6_graph_builder_ro")
    screen = load_module(SCREEN_V2_PATH, "e6_screen_v2_ro")
    w2 = load_module(W2_02_PATH, "e6_w2_02_ro")
    reduction_info = install_deterministic_inference_reduction(screen)
    if builder.GraphConfig().digest() != EXPECTED_GRAPH_CONFIG_HASH:
        raise RuntimeError("graph builder config differs from inherited seal")

    data = build_val_a_data(
        formal=formal,
        builder=builder,
        screen=screen,
        w2=w2,
        manifest=manifest,
        cal_split=cal_split,
        guard=guard,
    )
    gnn_predictions, gnn_execution = predict_frozen_gnn_a(
        formal=formal,
        screen=screen,
        samples=data["samples"],
        guard=guard,
        reduction_info=reduction_info,
    )
    control_predictions, control_execution = fit_classical_control(
        w2=w2,
        prereg=prereg,
        val_design=data["design"],
        guard=guard,
    )
    formal_results = load_json(FORMAL_RESULTS_PATH)
    formal_results_hash = sha256_file(FORMAL_RESULTS_PATH)
    arms = evaluate_arms(
        predictions={
            "GNN_A_no_pretrain": gnn_predictions,
            "control_twohop_GBDT_full": control_predictions,
        },
        y=data["y"],
        row_is_cal_fit=data["row_is_cal_fit"],
        row_category_code=data["row_category_code"],
        cal_split=cal_split,
        formal_results=formal_results,
    )
    guard.check("numeric assembly")

    final_seal_hashes = {
        "prereg.json": sha256_file(PREREG_PATH),
        "PREREG.csv": sha256_file(PREREG_CSV_PATH),
    }
    if final_seal_hashes != EXPECTED_SEAL_HASHES:
        raise RuntimeError("inherited seal changed during E6 execution")
    final_checkpoint_hashes = {
        str(seed): sha256_file(FORMAL_CKPT_DIR / f"GNN_A_no_pretrain_seed_{seed}.pt")
        for seed in SEEDS
    }
    if any(
        final_checkpoint_hashes[str(seed)] != EXPECTED_INPUT_HASHES[f"GNN_A_seed_{seed}"][1]
        for seed in SEEDS
    ):
        raise RuntimeError("GNN-A checkpoint hash changed during E6 execution")

    del data["samples"], data["design"], data["y"], data["row_is_cal_fit"], data["row_category_code"]
    gc.collect()
    execution_scope = {
        "write_root": str(CELL_DIR),
        "repository_files_modified": 0,
        "git_commands_used_after_packet_read": 0,
        "subagents_used": 0,
        "GNN_training_or_refit_count": 0,
        "threshold_search_count": 0,
        "threshold": THRESHOLD,
        "val_B_drawing_reads": data["audit"]["read_counters"]["val_B_drawing_reads"],
        "test_reads": data["audit"]["read_counters"]["test_reads"],
        "original_CAD_reads": data["audit"]["read_counters"]["original_CAD_reads"],
        "band_adjudication_count": 0,
    }
    result_calibration_split = {
        key: value
        for key, value in cal_split.items()
        if key not in ("fit_families", "eval_families")
    }
    stable_measurement_hash = stable_numeric_measurement_sha256(
        calibration_split=result_calibration_split,
        arms=arms,
    )
    repeat_inference_ok = all(
        bool(row["repeat_probability_bitwise_equal"])
        for row in gnn_execution
    )
    result: dict[str, Any] = {
        "schema": "e2.e6_calibration_ood.results.v1",
        "completed_at_utc": now_iso(),
        "completion_state": "numeric_measurements_complete",
        "judgment_emitted": False,
        "judgment_policy": "numeric measurements only; band adjudication is orchestrator-only",
        "preflight": preflight,
        "selftest": selftest,
        "contract": {
            "threshold": THRESHOLD,
            "threshold_search": "forbidden",
            "temperature_fit_universe": "cal-fit only",
            "reported_metric_universe": "cal-eval only",
            "binning": "10 equal-width bins [0.0,0.1),...,[0.9,1.0]",
            "sealed_band_text": prereg["sealed_band_text"],
            "band_adjudication": prereg["band_adjudication"],
            "style_limit": prereg["style_limit"],
            "reproducibility_claim": prereg["reproducibility_claim"],
        },
        "calibration_split": result_calibration_split,
        "data_audit": data["audit"],
        "arms": arms,
        "execution_records": {
            "inference_reduction": reduction_info,
            "GNN_A_no_pretrain": gnn_execution,
            "control_twohop_GBDT_full": control_execution,
        },
        "full_val_A_formal_results_sha256_observed": formal_results_hash,
        "execution_scope": execution_scope,
        "resource_usage": guard.metrics(),
        "post_execution_immutability": {
            "inherited_seals": final_seal_hashes,
            "GNN_A_checkpoints": final_checkpoint_hashes,
        },
        "reproducibility": {
            "claim": prereg["reproducibility_claim"],
            "stable_numeric_measurement_sha256": stable_measurement_hash,
            "GNN_A_repeat_probability_bitwise_equal_all_seeds": repeat_inference_ok,
            "volatile_field_paths": [
                "completed_at_utc",
                "preflight.checked_at_utc",
                "data_audit.build_seconds",
                "execution_records.GNN_A_no_pretrain[*].inference_seconds",
                "execution_records.GNN_A_no_pretrain[*].repeat_inference_seconds",
                "execution_records.control_twohop_GBDT_full[*].fit_seconds",
                "resource_usage",
                "full_val_A_reference_numeric_check",
            ],
        },
        "unresolved": [
            EVIDENCE_FALLBACK_REASON,
            prereg["style_limit"],
        ],
    }
    rows = evidence_rows(result)
    write_evidence_csv(rows)
    result["evidence"] = {
        "preferred": "evidence.xlsx",
        "status": "CSV_FALLBACK_AUTHORIZED_BY_INHERITED_SEAL",
        "path": str(EVIDENCE_CSV_PATH),
        "row_count": len(rows),
        "fallback_reason": EVIDENCE_FALLBACK_REASON,
    }
    result["artifacts"] = {
        "e6_calibration_ood_py_sha256": sha256_file(SCRIPT_PATH),
        "evidence_csv_sha256": sha256_file(EVIDENCE_CSV_PATH),
        "prereg_json_sha256": final_seal_hashes["prereg.json"],
        "prereg_csv_sha256": final_seal_hashes["PREREG.csv"],
    }
    atomic_write_json(RESULTS_PATH, result)
    result["artifacts"]["results_json_sha256"] = sha256_file(RESULTS_PATH)
    atomic_write_text(REPORT_PATH, render_report(result))
    print(
        f"[complete] results={RESULTS_PATH} evidence={EVIDENCE_CSV_PATH} report={REPORT_PATH}",
        flush=True,
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="run sealed guards only; write nothing")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.selftest:
        result = run_selftest()
        print(json.dumps(json_ready(result), ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result["ok"] else 1
    execute()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
