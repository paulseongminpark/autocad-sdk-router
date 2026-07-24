#!/usr/bin/env python3
"""G5 full-graph, unsampled inference and cross-device measurement cell.

The two existing preregistration files are immutable adopted seals.  This
driver validates them and every frozen input by SHA-256; it never creates or
updates a seal, trains a model, samples the target graph, or reads truth/test/
val-B/original-CAD inputs.
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import importlib.util
import json
import math
import os
import platform
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

sys.dont_write_bytecode = True

import numpy as np
import psutil
import torch
from torch import nn


SCHEMA = "e2.g5_full_graph.results.v1"
RAW_SCHEMA = "e2.g5_full_graph.raw.v1"
SELFTEST_SCHEMA = "e2.g5_full_graph.selftest.v1"
CELL_ID = "g5_full_graph"
TARGET_DEFINITION = "X-평면도(기본형)"
TARGET_SEGMENT_COUNT = 412_775
TARGET_BLOCK_NAME = TARGET_DEFINITION
REFERENCE_DRAWING_ID = "high_quality_architectural_6347"
REFERENCE_FAMILY_ID = "0eb060c9bd798071dee0bf7f5ff8cdc5bc1cf9102ba3781c16dfc570c37971f5"
SEEDS = (17, 29, 43)
RELATION_COUNT = 6
FEATURE_COUNT = 17
THRESHOLD = 0.5
CAP_HOURS = 36.0
CAP_SECONDS = CAP_HOURS * 3600.0
ABSOLUTE_FLOOR = 1.0e-4
RELATIVE_FLOOR = 1.0e-3
WITHIN_MULTIPLIER = 5.0
REFERENCE_REPEAT_COUNT = 2
CLAIM_POLICY = "휘발 필드(runtime·타임스탬프) 제외 수치 전 필드 동일"

CELL_ROOT = Path(r"D:\runs\e2_program\cells\g5_full_graph")
REPO_ROOT = Path(r"D:\dev\99_tools\autocad-sdk-router")
DEFAULT_PREREG = CELL_ROOT / "prereg.json"
DEFAULT_PREREG_CSV = CELL_ROOT / "PREREG.csv"
DEFAULT_BUILDER = REPO_ROOT / "tools" / "e2" / "cells" / "graph_builder.py"
DEFAULT_ARCHITECTURE = Path(
    r"D:\runs\e2_program\cells\gnn_e2_screen_v2\gnn_e2_v2.py"
)
DEFAULT_DXF = REPO_ROOT / "runs" / "e2_b3_dxfout_20260717" / "1_export.dxf"
DEFAULT_REFERENCE = (
    REPO_ROOT
    / "runs"
    / "e2_ext_cubicasa"
    / "ir"
    / "val"
    / f"{REFERENCE_DRAWING_ID}.segir.json"
)
DEFAULT_CHECKPOINT_DIR = Path(r"D:\runs\e2_program\cells\gnn_formal\ckpt")

EXPECTED_HASHES = {
    "prereg.json": "44a06ba6620d77bd2430bdc9cc0d52ababac1465dcf69c207c5381df037a1bf7",
    "PREREG.csv": "6dd37584767469dc36d294fdb295fc5904a42eb3768d4f731b307a7bd6239bd5",
    "graph_builder.py": "c95d4a30d30e0db157fe56102053a7884902b7749464f7f4cb8852c0819321f6",
    "gnn_e2_v2.py": "895249f0b6c77ac8f8a7cfb73e859a0882681ad6bba6e337480b55db269ce120",
    "1_export.dxf": "5a6035721630cddc6d753b1b97b898e7a4ce4d5988342ce85e2c465cdb81deff",
    f"{REFERENCE_DRAWING_ID}.segir.json": "decbb00686815ff8d3426e3b38cbdb499a1edc8d77784f93b649b295eab22565",
    "GNN_A_no_pretrain_seed_17.pt": "612e4bf954ff5967853f7a08e66195b79dfa15250d6e9d42f88a877c92a3952c",
    "GNN_A_no_pretrain_seed_29.pt": "1b4bbd004491609cfe8cfc217d18b0ec5ff344f8fee43c67b392a4c37dbc6877",
    "GNN_A_no_pretrain_seed_43.pt": "ab37cf25894e8ed7f2e96ca287a21da961c68d37bcf2bd9633ae1cb9b663e2a3",
}
EXPECTED_CONFIG_HASH = "56911f4633979a3fe00fd56be2d0a39ac06757ed255ed49ed18ca20ba9d4ac49"
EXPECTED_FEATURE_NAMES = (
    "log1p_length_norm",
    "midpoint_x_drawing_norm",
    "midpoint_y_drawing_norm",
    "bbox_width_norm",
    "bbox_height_norm",
    "sin_2theta",
    "cos_2theta",
    "sagitta_norm",
    "closed_geometry",
    "kind_line",
    "kind_poly_edge",
    "kind_arc_chord",
    "log1p_endpoint_degree",
    "log1p_junction_count",
    "log1p_parallel_count",
    "log1p_collinear_count",
    "block_depth_norm",
)
EXPECTED_EDGE_TYPES = (
    "parallel_band",
    "intersection_junction",
    "proximity",
    "collinearity",
    "containment",
    "instancing",
)

FORBIDDEN_INPUT_KINDS = frozenset({"original_CAD", "test", "val_B", "val_A_truth"})
ALLOWED_INPUT_KINDS = frozenset(
    {
        "adopted_prereg",
        "adopted_prereg_csv",
        "staged_DXF_copy",
        "frozen_graph_builder",
        "frozen_architecture",
        "GNN_A_checkpoint",
        "sealed_val_A_SEG_IR",
    }
)


class BudgetKill(RuntimeError):
    pass


class BlockedOOM(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(json_ready(payload), stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def ensure_hash(path: Path, expected: str, label: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"missing read-only input {label}: {path}")
    observed = sha256_file(path)
    if observed != expected:
        raise RuntimeError(f"SHA-256 drift for {label}: {observed} != {expected}")
    return observed


def authorize_input(kind: str) -> None:
    # This decision must happen before path construction, stat, open, or hashing.
    if kind in FORBIDDEN_INPUT_KINDS:
        raise PermissionError(f"blocked forbidden input kind before filesystem: {kind}")
    if kind not in ALLOWED_INPUT_KINDS:
        raise PermissionError(f"blocked unregistered input kind before filesystem: {kind}")


def guarded_read_bytes(kind: str, path_like: Any, expected_hash: str) -> bytes:
    authorize_input(kind)
    path = Path(path_like)
    data = path.read_bytes()
    observed = hashlib.sha256(data).hexdigest()
    if observed != expected_hash:
        raise RuntimeError(f"SHA-256 drift for {kind}: {observed} != {expected_hash}")
    return data


def load_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def verify_seals(prereg_path: Path, prereg_csv_path: Path) -> dict[str, Any]:
    hashes = {
        "prereg_json_sha256": ensure_hash(
            prereg_path, EXPECTED_HASHES["prereg.json"], "adopted prereg.json"
        ),
        "prereg_csv_sha256": ensure_hash(
            prereg_csv_path, EXPECTED_HASHES["PREREG.csv"], "adopted PREREG.csv"
        ),
    }
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    if prereg.get("cell_id") != CELL_ID:
        raise RuntimeError("adopted seal cell_id drift")
    if prereg.get("target", {}).get("segment_count") != TARGET_SEGMENT_COUNT:
        raise RuntimeError("adopted target segment count drift")
    if prereg.get("graph", {}).get("config_sha256") != EXPECTED_CONFIG_HASH:
        raise RuntimeError("adopted graph config hash drift")
    if tuple(prereg.get("model", {}).get("seeds", ())) != SEEDS:
        raise RuntimeError("adopted seed list drift")
    if prereg.get("cross_device_reference", {}).get("drawing_id") != REFERENCE_DRAWING_ID:
        raise RuntimeError("adopted reference drawing drift")
    if prereg.get("resource_cap", {}).get("cap_hours") != CAP_HOURS:
        raise RuntimeError("adopted DGX cap drift")
    if prereg.get("output_policy", {}).get("repo_writes_allowed") is not False:
        raise RuntimeError("adopted output boundary drift")
    return {"status": "ADOPTED_IMMUTABLE", **hashes, "sealed_utc": prereg["sealed_utc"]}


def load_frozen_modules(builder_path: Path, architecture_path: Path) -> tuple[Any, Any]:
    ensure_hash(builder_path, EXPECTED_HASHES["graph_builder.py"], "frozen graph builder")
    ensure_hash(architecture_path, EXPECTED_HASHES["gnn_e2_v2.py"], "frozen architecture")
    stamp = str(os.getpid())
    builder = load_module(builder_path, f"g5_graph_builder_{stamp}")
    architecture = load_module(architecture_path, f"g5_architecture_{stamp}")
    config = builder.GraphConfig()
    if config.digest() != EXPECTED_CONFIG_HASH:
        raise RuntimeError("frozen graph config digest drift")
    if tuple(builder.FEATURE_NAMES) != EXPECTED_FEATURE_NAMES:
        raise RuntimeError("frozen feature allowlist drift")
    if tuple(builder.EDGE_TYPES) != EXPECTED_EDGE_TYPES:
        raise RuntimeError("frozen edge-type list drift")
    return builder, architecture


@dataclass(frozen=True)
class InferenceConfig:
    hidden_dim: int = 64
    dropout: float = 0.10


class NodeGNN(nn.Module):
    def __init__(self, architecture: Any, config: InferenceConfig):
        super().__init__()
        self.encoder = architecture.TypedEncoder(
            FEATURE_COUNT, config.hidden_dim, RELATION_COUNT, config.dropout
        )
        self.node_head = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim // 2),
            nn.GELU(),
            nn.Linear(config.hidden_dim // 2, 1),
        )

    def forward(self, batch: dict[str, torch.Tensor]) -> torch.Tensor:
        hidden = self.encoder(
            batch["x"], batch["edge_src"], batch["edge_dst"], batch["edge_type"], "full"
        )
        return self.node_head(hidden).squeeze(1)


def checkpoint_path(checkpoint_dir: Path, seed: int) -> Path:
    return checkpoint_dir / f"GNN_A_no_pretrain_seed_{seed}.pt"


def checkpoint_hashes(checkpoint_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for seed in SEEDS:
        path = checkpoint_path(checkpoint_dir, seed)
        expected = EXPECTED_HASHES[path.name]
        result[str(seed)] = ensure_hash(path, expected, f"GNN-A checkpoint seed {seed}")
    return result


def load_model(
    checkpoint_dir: Path,
    seed: int,
    architecture: Any,
    device: torch.device,
) -> NodeGNN:
    path = checkpoint_path(checkpoint_dir, seed)
    ensure_hash(path, EXPECTED_HASHES[path.name], f"GNN-A checkpoint seed {seed}")
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if payload.get("schema") != "e2.gnn_formal.gnn_checkpoint.v1":
        raise RuntimeError(f"checkpoint schema drift for seed {seed}")
    if payload.get("arm") != "GNN_A_no_pretrain" or int(payload.get("seed")) != seed:
        raise RuntimeError(f"checkpoint identity drift for seed {seed}")
    if tuple(payload.get("feature_names", ())) != EXPECTED_FEATURE_NAMES:
        raise RuntimeError(f"checkpoint feature list drift for seed {seed}")
    if int(payload.get("relation_count")) != RELATION_COUNT:
        raise RuntimeError(f"checkpoint relation count drift for seed {seed}")
    raw_config = payload.get("config", {})
    if int(raw_config.get("hidden_dim")) != 64:
        raise RuntimeError(f"checkpoint hidden_dim drift for seed {seed}")
    model = NodeGNN(
        architecture,
        InferenceConfig(hidden_dim=64, dropout=float(raw_config.get("dropout", 0.10))),
    )
    model.load_state_dict(payload["state_dict"], strict=True)
    model.eval()
    return model.to(device)


class PeakRSSMonitor:
    def __init__(self, interval_seconds: float = 0.10):
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.process = psutil.Process(os.getpid())
        self.peak_rss_bytes = 0

    def _sample(self) -> None:
        try:
            self.peak_rss_bytes = max(self.peak_rss_bytes, int(self.process.memory_info().rss))
        except psutil.Error:
            pass

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._sample()

    def start(self) -> None:
        self._sample()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> int:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._sample()
        return self.peak_rss_bytes


def cuda_sync() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def runtime_record(device: torch.device) -> dict[str, Any]:
    result: dict[str, Any] = {
        "captured_utc": utc_now(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "python_executable": sys.executable,
        "numpy": np.__version__,
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "psutil": psutil.__version__,
        "requested_device": str(device),
        "cpu_count_logical": os.cpu_count(),
        "process_rss_bytes": int(psutil.Process(os.getpid()).memory_info().rss),
        "host_virtual_memory": json_ready(psutil.virtual_memory()._asdict()),
    }
    if device.type == "cuda" and torch.cuda.is_available():
        props = torch.cuda.get_device_properties(device)
        free_bytes, total_bytes = torch.cuda.mem_get_info(device)
        result["cuda_device"] = {
            "name": props.name,
            "total_memory_bytes": int(props.total_memory),
            "major": int(props.major),
            "minor": int(props.minor),
            "multiprocessor_count": int(props.multi_processor_count),
            "memory_free_bytes": int(free_bytes),
            "memory_total_bytes_from_mem_get_info": int(total_bytes),
        }
    return result


def http_probe(url: str, timeout_seconds: float = 10.0) -> dict[str, Any]:
    started = utc_now()
    t0 = time.perf_counter()
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read(1_000_000)
            return {
                "started_utc": started,
                "elapsed_seconds": time.perf_counter() - t0,
                "reachable": True,
                "http_status": int(response.status),
                "body_sha256": hashlib.sha256(body).hexdigest(),
                "body_bytes": len(body),
            }
    except Exception as error:  # noqa: BLE001 - probe evidence must retain failure class
        return {
            "started_utc": started,
            "elapsed_seconds": time.perf_counter() - t0,
            "reachable": False,
            "http_status": None,
            "error_type": type(error).__name__,
            "error": str(error)[:500],
        }


def make_batch(result: dict[str, Any], device: torch.device) -> dict[str, torch.Tensor]:
    return {
        "x": torch.as_tensor(
            np.asarray(result["features"], dtype=np.float32), dtype=torch.float32, device=device
        ),
        "edge_src": torch.as_tensor(
            np.asarray(result["edge_src"], dtype=np.int64), dtype=torch.long, device=device
        ),
        "edge_dst": torch.as_tensor(
            np.asarray(result["edge_dst"], dtype=np.int64), dtype=torch.long, device=device
        ),
        "edge_type": torch.as_tensor(
            np.asarray(result["edge_type"], dtype=np.int64), dtype=torch.long, device=device
        ),
    }


def distribution(values: np.ndarray) -> dict[str, Any]:
    data = np.asarray(values, dtype=np.float64).reshape(-1)
    if not data.size:
        return {
            "count": 0,
            "histogram_bin_edges": list(np.linspace(0.0, 1.0, 21)),
            "histogram_counts": [0] * 20,
        }
    bin_edges = np.linspace(0.0, 1.0, 21)
    counts, edges = np.histogram(data, bins=bin_edges)
    q = np.quantile(data, [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99])
    return {
        "count": int(data.size),
        "histogram_bin_edges": edges.tolist(),
        "histogram_counts": counts.astype(np.int64).tolist(),
        "min": float(np.min(data)),
        "p01": float(q[0]),
        "p05": float(q[1]),
        "p25": float(q[2]),
        "p50": float(q[3]),
        "p75": float(q[4]),
        "p95": float(q[5]),
        "p99": float(q[6]),
        "max": float(np.max(data)),
        "mean": float(np.mean(data)),
        "std_population": float(np.std(data, ddof=0)),
        "positive_ratio_at_0_5": float(np.mean(data >= THRESHOLD)),
    }


def delta_metrics(first: np.ndarray, second: np.ndarray) -> dict[str, float]:
    a = np.asarray(first, dtype=np.float64).reshape(-1)
    b = np.asarray(second, dtype=np.float64).reshape(-1)
    if a.shape != b.shape:
        raise RuntimeError(f"delta shape mismatch: {a.shape} != {b.shape}")
    absolute = np.abs(a - b)
    denominator = np.maximum(np.maximum(np.abs(a), np.abs(b)), 1.0e-12)
    relative = absolute / denominator
    return {
        "max_abs": float(np.max(absolute)) if absolute.size else 0.0,
        "p99_abs": float(np.quantile(absolute, 0.99)) if absolute.size else 0.0,
        "max_rel": float(np.max(relative)) if relative.size else 0.0,
        "p99_rel": float(np.quantile(relative, 0.99)) if relative.size else 0.0,
    }


def unsampled_inference(
    graph_result: dict[str, Any],
    architecture: Any,
    checkpoint_dir: Path,
    device: torch.device,
    deadline: float,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    if time.monotonic() >= deadline:
        raise BudgetKill("BUDGET_KILL before tensor materialization")
    tensor_monitor = PeakRSSMonitor()
    tensor_monitor.start()
    tensor_started = time.perf_counter()
    batch = make_batch(graph_result, device)
    cuda_sync()
    tensor_seconds = time.perf_counter() - tensor_started
    tensor_peak_rss = tensor_monitor.stop()

    seed_rows: list[dict[str, Any]] = []
    score_vectors: dict[int, np.ndarray] = {}
    for seed in SEEDS:
        if time.monotonic() >= deadline:
            raise BudgetKill(f"BUDGET_KILL before inference seed {seed}")
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)
        monitor = PeakRSSMonitor()
        monitor.start()
        model = load_model(checkpoint_dir, seed, architecture, device)
        cuda_sync()
        started = time.perf_counter()
        try:
            with torch.inference_mode():
                logits = model(batch)
                probabilities_device = torch.sigmoid(logits)
            cuda_sync()
        except torch.cuda.OutOfMemoryError as error:
            torch.cuda.empty_cache()
            raise BlockedOOM(f"full unsampled forward OOM for seed {seed}") from error
        elapsed = time.perf_counter() - started
        probabilities = probabilities_device.detach().cpu().numpy().astype(np.float64, copy=False)
        peak_allocated = int(torch.cuda.max_memory_allocated(device))
        peak_reserved = int(torch.cuda.max_memory_reserved(device))
        peak_rss = monitor.stop()
        seed_rows.append(
            {
                "seed": seed,
                "single_forward_wall_seconds": elapsed,
                "nodes_per_second": len(probabilities) / elapsed,
                "single_sample_empirical_p95_seconds": elapsed,
                "latency_sample_count": 1,
                "peak_cuda_allocated_bytes": peak_allocated,
                "peak_cuda_reserved_bytes": peak_reserved,
                "peak_host_rss_bytes": peak_rss,
                "output_distribution": distribution(probabilities),
            }
        )
        score_vectors[seed] = probabilities.copy()
        del probabilities_device, logits, model
        torch.cuda.empty_cache()

    binary = {seed: score_vectors[seed] >= THRESHOLD for seed in SEEDS}
    pairwise = []
    for left, right in ((17, 29), (17, 43), (29, 43)):
        pairwise.append(
            {
                "seed_left": left,
                "seed_right": right,
                "pairwise_binary_agreement": float(np.mean(binary[left] == binary[right])),
            }
        )
    stacked_binary = np.stack([binary[seed] for seed in SEEDS], axis=0)
    stacked_scores = np.stack([score_vectors[seed] for seed in SEEDS], axis=0)
    per_node_std = np.std(stacked_scores, axis=0, ddof=0)
    agreement = {
        "pairwise_binary_agreement": pairwise,
        "three_seed_unanimous_ratio": float(
            np.mean(np.all(stacked_binary == stacked_binary[0:1, :], axis=0))
        ),
        "per_node_score_std_summary": distribution(per_node_std),
    }
    tensor_record = {
        "materialization_wall_seconds": tensor_seconds,
        "peak_host_rss_bytes": tensor_peak_rss,
        "x_bytes": int(batch["x"].numel() * batch["x"].element_size()),
        "edge_src_bytes": int(batch["edge_src"].numel() * batch["edge_src"].element_size()),
        "edge_dst_bytes": int(batch["edge_dst"].numel() * batch["edge_dst"].element_size()),
        "edge_type_bytes": int(batch["edge_type"].numel() * batch["edge_type"].element_size()),
    }
    del batch
    torch.cuda.empty_cache()
    return seed_rows, agreement, tensor_record


def run_reference(
    *,
    role: str,
    builder_path: Path,
    architecture_path: Path,
    reference_path: Path,
    checkpoint_dir: Path,
    prereg_path: Path,
    prereg_csv_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    started_utc = utc_now()
    wall_started = time.perf_counter()
    seals = verify_seals(prereg_path, prereg_csv_path)
    builder, architecture = load_frozen_modules(builder_path, architecture_path)
    reference_bytes = guarded_read_bytes(
        "sealed_val_A_SEG_IR",
        reference_path,
        EXPECTED_HASHES[f"{REFERENCE_DRAWING_ID}.segir.json"],
    )
    ir = json.loads(reference_bytes)
    if str(ir.get("drawing_id")) != REFERENCE_DRAWING_ID:
        raise RuntimeError("sealed reference drawing_id drift")
    graph_monitor = PeakRSSMonitor()
    graph_monitor.start()
    graph_started = time.perf_counter()
    graph = builder.build_graph(ir, builder.GraphConfig(), collect_edges=True)
    graph_seconds = time.perf_counter() - graph_started
    graph_peak_rss = graph_monitor.stop()
    device = torch.device("cuda")
    if not torch.cuda.is_available():
        raise RuntimeError(f"CUDA unavailable for {role} reference")
    batch = make_batch(graph, device)
    seed_records: list[dict[str, Any]] = []
    for seed in SEEDS:
        model = load_model(checkpoint_dir, seed, architecture, device)
        repeat_scores: list[list[float]] = []
        repeat_seconds: list[float] = []
        for repeat_index in range(REFERENCE_REPEAT_COUNT):
            cuda_sync()
            t0 = time.perf_counter()
            with torch.inference_mode():
                probabilities_device = torch.sigmoid(model(batch))
            cuda_sync()
            repeat_seconds.append(time.perf_counter() - t0)
            repeat_scores.append(
                probabilities_device.detach().cpu().numpy().astype(np.float64).tolist()
            )
            del probabilities_device
        within = delta_metrics(
            np.asarray(repeat_scores[0], dtype=np.float64),
            np.asarray(repeat_scores[1], dtype=np.float64),
        )
        seed_records.append(
            {
                "seed": seed,
                "repeat_count": REFERENCE_REPEAT_COUNT,
                "repeat_wall_seconds": repeat_seconds,
                "within_device": within,
                "scores": repeat_scores,
            }
        )
        del model
        torch.cuda.empty_cache()
    payload = {
        "schema": RAW_SCHEMA,
        "cell": CELL_ID,
        "phase": "cross_device_reference",
        "role": role,
        "status": "COMPLETE",
        "started_utc": started_utc,
        "completed_utc": utc_now(),
        "wall_seconds": time.perf_counter() - wall_started,
        "seals": seals,
        "runtime": runtime_record(device),
        "reference": {
            "drawing_id": REFERENCE_DRAWING_ID,
            "family_id": REFERENCE_FAMILY_ID,
            "seg_ir_bytes": len(reference_bytes),
            "seg_ir_sha256": hashlib.sha256(reference_bytes).hexdigest(),
            "truth_access_count": 0,
            "node_count": int(graph["stats"]["node_count"]),
            "directed_edge_count": int(graph["stats"]["directed_edge_count"]),
            "graph_hash": graph["stats"]["graph_hash"],
            "config_hash": graph["stats"]["config_hash"],
            "graph_build_wall_seconds": graph_seconds,
            "graph_build_peak_host_rss_bytes": graph_peak_rss,
        },
        "checkpoint_hashes_before": checkpoint_hashes(checkpoint_dir),
        "seeds": seed_records,
        "checkpoint_hashes_after": checkpoint_hashes(checkpoint_dir),
        "access_counters": {
            "sealed_val_A_SEG_IR_reads": 1,
            "val_A_truth_reads": 0,
            "val_B_reads": 0,
            "test_reads": 0,
            "original_CAD_reads": 0,
        },
    }
    atomic_write_json(output_path, payload)
    return payload


def run_dgx(
    *,
    builder_path: Path,
    architecture_path: Path,
    dxf_path: Path,
    reference_path: Path,
    checkpoint_dir: Path,
    prereg_path: Path,
    prereg_csv_path: Path,
    output_path: Path,
    vllm_probe_url: str,
) -> dict[str, Any]:
    started_utc = utc_now()
    wall_started = time.perf_counter()
    deadline = time.monotonic() + CAP_SECONDS
    base: dict[str, Any] = {
        "schema": RAW_SCHEMA,
        "cell": CELL_ID,
        "phase": "dgx_full_graph",
        "role": "dgx_gb10",
        "started_utc": started_utc,
        "resource_cap_hours": CAP_HOURS,
        "sampling_allowed": False,
        "retraining_allowed": False,
        "vllm": {
            "pre_job_probe": http_probe(vllm_probe_url),
            "stop_command_issued": False,
            "restart_command_issued": False,
        },
    }

    def alarm_handler(_signum: int, _frame: Any) -> None:
        raise BudgetKill("BUDGET_KILL 36h DGX cap")

    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, alarm_handler)
        signal.alarm(int(CAP_SECONDS))
    try:
        seals = verify_seals(prereg_path, prereg_csv_path)
        builder, architecture = load_frozen_modules(builder_path, architecture_path)
        before_hashes = checkpoint_hashes(checkpoint_dir)
        device = torch.device("cuda")
        if not torch.cuda.is_available():
            raise RuntimeError("DGX CUDA unavailable")
        if "GB10" not in torch.cuda.get_device_name(device).upper():
            raise RuntimeError(f"unexpected DGX device: {torch.cuda.get_device_name(device)}")
        base["seals"] = seals
        base["runtime_pre"] = runtime_record(device)
        ensure_hash(dxf_path, EXPECTED_HASHES["1_export.dxf"], "staged DXF copy")

        import ezdxf

        build_monitor = PeakRSSMonitor()
        build_monitor.start()
        full_build_started = time.perf_counter()
        dxf_started = time.perf_counter()
        doc = ezdxf.readfile(dxf_path)
        dxf_read_seconds = time.perf_counter() - dxf_started
        segir_started = time.perf_counter()
        ir = builder.segir_from_block(doc, TARGET_BLOCK_NAME)
        segir_seconds = time.perf_counter() - segir_started
        del doc
        gc.collect()
        if len(ir.get("segments") or []) != TARGET_SEGMENT_COUNT:
            raise RuntimeError(
                f"staged target segment count drift: {len(ir.get('segments') or [])}"
            )
        if time.monotonic() >= deadline:
            raise BudgetKill("BUDGET_KILL before typed graph construction")
        typed_started = time.perf_counter()
        graph = builder.build_graph(ir, builder.GraphConfig(), collect_edges=True)
        typed_seconds = time.perf_counter() - typed_started
        full_build_seconds = time.perf_counter() - full_build_started
        build_peak_rss = build_monitor.stop()
        del ir
        gc.collect()
        graph_stats = json_ready(graph["stats"])
        base["graph_build"] = {
            "target_definition": TARGET_DEFINITION,
            "staged_dxf_sha256": EXPECTED_HASHES["1_export.dxf"],
            "input_segment_count": TARGET_SEGMENT_COUNT,
            "node_count": int(graph_stats["node_count"]),
            "directed_edge_count": int(graph_stats["directed_edge_count"]),
            "build_wall_seconds": full_build_seconds,
            "dxf_read_wall_seconds": dxf_read_seconds,
            "seg_ir_expand_wall_seconds": segir_seconds,
            "typed_graph_build_wall_seconds": typed_seconds,
            "peak_host_rss_bytes": build_peak_rss,
            "graph_hash": graph_stats["graph_hash"],
            "config_hash": graph_stats["config_hash"],
            "dropped_input_segments": graph_stats["dropped_input_segments"],
            "relation_directed_edge_counts": graph_stats[
                "relation_directed_edge_counts"
            ],
            "candidate_scan": graph_stats["candidate_scan"],
            "shard_count": graph_stats["shard_count"],
            "maximum_shard_core_nodes": graph_stats["maximum_shard_core_nodes"],
            "maximum_shard_nodes_with_halo": graph_stats[
                "maximum_shard_nodes_with_halo"
            ],
            "maximum_shard_directed_edges": graph_stats[
                "maximum_shard_directed_edges"
            ],
        }
        inference, agreement, tensor_record = unsampled_inference(
            graph, architecture, checkpoint_dir, device, deadline
        )
        base["full_graph_inference"] = inference
        base["seed_agreement"] = agreement
        base["device_tensor_materialization"] = tensor_record
        del graph
        gc.collect()
        torch.cuda.empty_cache()

        reference_temp = output_path.with_name(output_path.name + ".reference.tmp.json")
        reference_payload = run_reference(
            role="dgx_gb10",
            builder_path=builder_path,
            architecture_path=architecture_path,
            reference_path=reference_path,
            checkpoint_dir=checkpoint_dir,
            prereg_path=prereg_path,
            prereg_csv_path=prereg_csv_path,
            output_path=reference_temp,
        )
        try:
            reference_temp.unlink(missing_ok=True)
        except OSError:
            pass
        base["cross_device_reference"] = reference_payload
        base["checkpoint_hashes_before"] = before_hashes
        base["checkpoint_hashes_after"] = checkpoint_hashes(checkpoint_dir)
        base["status"] = "COMPLETE"
    except (torch.cuda.OutOfMemoryError, MemoryError, BlockedOOM) as error:
        torch.cuda.empty_cache()
        base["status"] = "BLOCKED_OOM"
        base["blocker"] = {"type": type(error).__name__, "message": str(error)[:1000]}
    except BudgetKill as error:
        base["status"] = "BUDGET_KILL"
        base["blocker"] = {"type": type(error).__name__, "message": str(error)[:1000]}
    except Exception as error:  # noqa: BLE001 - blocked artifact must retain exact cause
        base["status"] = "BLOCKED_RUNTIME"
        base["blocker"] = {
            "type": type(error).__name__,
            "message": str(error)[:2000],
            "traceback": traceback.format_exc(limit=20),
        }
    finally:
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)
        base["completed_utc"] = utc_now()
        base["wall_seconds"] = time.perf_counter() - wall_started
        base["vllm"]["post_job_probe"] = http_probe(vllm_probe_url)
        base["runtime_post"] = runtime_record(torch.device("cuda"))
        atomic_write_json(output_path, base)
    return base


class PoisonPath:
    def __init__(self) -> None:
        self.touched = False

    def __fspath__(self) -> str:
        self.touched = True
        raise AssertionError("filesystem conversion occurred")


def run_selftest(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    seals_before = verify_seals(args.prereg, args.prereg_csv)
    builder, architecture = load_frozen_modules(args.builder, args.architecture)
    checkpoints_before = checkpoint_hashes(args.checkpoint_dir)
    blocked: list[str] = []
    for kind in sorted(FORBIDDEN_INPUT_KINDS):
        poison = PoisonPath()
        try:
            guarded_read_bytes(kind, poison, "0" * 64)
        except PermissionError:
            blocked.append(kind)
        if poison.touched:
            raise AssertionError(f"forbidden kind touched filesystem: {kind}")
    if set(blocked) != set(FORBIDDEN_INPUT_KINDS):
        raise AssertionError("forbidden-input guard coverage drift")

    builder_ok, builder_lines, builder_details = builder.run_selftest()
    if not builder_ok:
        raise AssertionError("frozen graph builder selftest failed")
    mini_ir = {
        "ir": "seg.v1",
        "drawing_id": "g5-selftest",
        "units": "mm",
        "segments": [
            {"sid": "a", "handle": "a", "kind": "line", "pts": [[0.0, 0.0], [1000.0, 0.0]]},
            {"sid": "b", "handle": "b", "kind": "line", "pts": [[0.0, 200.0], [1000.0, 200.0]]},
            {"sid": "c", "handle": "c", "kind": "line", "pts": [[500.0, -100.0], [500.0, 300.0]]},
        ],
    }
    first_graph = builder.build_graph(mini_ir, builder.GraphConfig(), collect_edges=True)
    second_graph = builder.build_graph(mini_ir, builder.GraphConfig(), collect_edges=True)
    if first_graph["stats"]["graph_hash"] != second_graph["stats"]["graph_hash"]:
        raise AssertionError("same-input graph hash determinism drift")
    device = torch.device("cpu")
    model = load_model(args.checkpoint_dir, 17, architecture, device)
    batch = make_batch(first_graph, device)
    with torch.inference_mode():
        first_scores = torch.sigmoid(model(batch)).cpu().numpy()
        second_scores = torch.sigmoid(model(batch)).cpu().numpy()
    score_max_abs = float(np.max(np.abs(first_scores - second_scores)))
    if score_max_abs != 0.0:
        raise AssertionError(f"same-input forward determinism drift: {score_max_abs}")
    checkpoints_after = checkpoint_hashes(args.checkpoint_dir)
    seals_after = verify_seals(args.prereg, args.prereg_csv)
    if checkpoints_before != checkpoints_after:
        raise AssertionError("checkpoint hash changed during selftest")
    if seals_before != seals_after:
        raise AssertionError("adopted seal hash changed during selftest")
    payload = {
        "schema": SELFTEST_SCHEMA,
        "cell": CELL_ID,
        "status": "COMPLETE",
        "wall_seconds": time.perf_counter() - started,
        "same_input_graph_hash_equal": True,
        "same_input_forward_max_abs": score_max_abs,
        "forbidden_kinds_blocked_before_filesystem": blocked,
        "forbidden_filesystem_calls": 0,
        "checkpoint_hashes_before": checkpoints_before,
        "checkpoint_hashes_after": checkpoints_after,
        "adopted_seals_before": seals_before,
        "adopted_seals_after": seals_after,
        "frozen_builder_selftest_lines": builder_lines,
        "frozen_builder_selftest_details": builder_details,
    }
    if args.selftest_output is not None:
        atomic_write_json(args.selftest_output, payload)
    print(json.dumps(json_ready(payload), ensure_ascii=False, sort_keys=True))
    return payload


def aggregate_equivalence(
    local_reference: dict[str, Any], dgx_reference: dict[str, Any]
) -> dict[str, Any]:
    local_by_seed = {int(item["seed"]): item for item in local_reference["seeds"]}
    dgx_by_seed = {int(item["seed"]): item for item in dgx_reference["seeds"]}
    per_seed: list[dict[str, Any]] = []
    local_first_all: list[np.ndarray] = []
    local_second_all: list[np.ndarray] = []
    dgx_first_all: list[np.ndarray] = []
    dgx_second_all: list[np.ndarray] = []
    for seed in SEEDS:
        local_scores = [np.asarray(row, dtype=np.float64) for row in local_by_seed[seed]["scores"]]
        dgx_scores = [np.asarray(row, dtype=np.float64) for row in dgx_by_seed[seed]["scores"]]
        local_median = np.median(np.stack(local_scores, axis=0), axis=0)
        dgx_median = np.median(np.stack(dgx_scores, axis=0), axis=0)
        local_within = delta_metrics(local_scores[0], local_scores[1])
        dgx_within = delta_metrics(dgx_scores[0], dgx_scores[1])
        cross = delta_metrics(local_median, dgx_median)
        absolute_limit = max(
            ABSOLUTE_FLOOR,
            WITHIN_MULTIPLIER * max(local_within["p99_abs"], dgx_within["p99_abs"]),
        )
        relative_limit = max(
            RELATIVE_FLOOR,
            WITHIN_MULTIPLIER * max(local_within["p99_rel"], dgx_within["p99_rel"]),
        )
        per_seed.append(
            {
                "seed": seed,
                "local_within_max_abs": local_within["max_abs"],
                "local_within_p99_abs": local_within["p99_abs"],
                "local_within_max_rel": local_within["max_rel"],
                "local_within_p99_rel": local_within["p99_rel"],
                "dgx_within_max_abs": dgx_within["max_abs"],
                "dgx_within_p99_abs": dgx_within["p99_abs"],
                "dgx_within_max_rel": dgx_within["max_rel"],
                "dgx_within_p99_rel": dgx_within["p99_rel"],
                "cross_device_max_abs": cross["max_abs"],
                "cross_device_p99_abs": cross["p99_abs"],
                "cross_device_max_rel": cross["max_rel"],
                "cross_device_p99_rel": cross["p99_rel"],
                "sealed_absolute_limit": absolute_limit,
                "sealed_relative_limit": relative_limit,
            }
        )
        local_first_all.append(local_scores[0])
        local_second_all.append(local_scores[1])
        dgx_first_all.append(dgx_scores[0])
        dgx_second_all.append(dgx_scores[1])
    local_first = np.concatenate(local_first_all)
    local_second = np.concatenate(local_second_all)
    dgx_first = np.concatenate(dgx_first_all)
    dgx_second = np.concatenate(dgx_second_all)
    local_within = delta_metrics(local_first, local_second)
    dgx_within = delta_metrics(dgx_first, dgx_second)
    cross = delta_metrics(
        np.median(np.stack([local_first, local_second]), axis=0),
        np.median(np.stack([dgx_first, dgx_second]), axis=0),
    )
    aggregate = {
        "local_within_max_abs": local_within["max_abs"],
        "local_within_p99_abs": local_within["p99_abs"],
        "local_within_max_rel": local_within["max_rel"],
        "local_within_p99_rel": local_within["p99_rel"],
        "dgx_within_max_abs": dgx_within["max_abs"],
        "dgx_within_p99_abs": dgx_within["p99_abs"],
        "dgx_within_max_rel": dgx_within["max_rel"],
        "dgx_within_p99_rel": dgx_within["p99_rel"],
        "cross_device_max_abs": cross["max_abs"],
        "cross_device_p99_abs": cross["p99_abs"],
        "cross_device_max_rel": cross["max_rel"],
        "cross_device_p99_rel": cross["p99_rel"],
        "sealed_absolute_limit": max(
            ABSOLUTE_FLOOR,
            WITHIN_MULTIPLIER * max(local_within["p99_abs"], dgx_within["p99_abs"]),
        ),
        "sealed_relative_limit": max(
            RELATIVE_FLOOR,
            WITHIN_MULTIPLIER * max(local_within["p99_rel"], dgx_within["p99_rel"]),
        ),
    }
    return {
        "reference_drawing_id": REFERENCE_DRAWING_ID,
        "reference_family_id": REFERENCE_FAMILY_ID,
        "repeat_count_per_device": REFERENCE_REPEAT_COUNT,
        "config_sha256_local": local_reference["reference"]["config_hash"],
        "config_sha256_dgx": dgx_reference["reference"]["config_hash"],
        "graph_sha256_local": local_reference["reference"]["graph_hash"],
        "graph_sha256_dgx": dgx_reference["reference"]["graph_hash"],
        "per_seed": per_seed,
        "aggregate": aggregate,
        "rule": "abs≤max(1e-4, 5×p99_within) ∧ rel≤max(1e-3, 5×p99_within)",
        "verdict_emitted": False,
    }


def flatten_rows(prefix: str, value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key in sorted(value):
            child = f"{prefix}.{key}" if prefix else str(key)
            yield from flatten_rows(child, value[key])
    elif isinstance(value, list):
        for index, item in enumerate(value):
            child = f"{prefix}[{index}]"
            yield from flatten_rows(child, item)
    else:
        yield prefix, value


def write_evidence_csv(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["field", "value"])
            for field, value in flatten_rows("", result):
                if isinstance(value, bool):
                    rendered = "true" if value else "false"
                elif value is None:
                    rendered = ""
                else:
                    rendered = value
                writer.writerow([field, rendered])
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def fmt_number(value: Any, digits: int = 9) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


def render_report(result: dict[str, Any], evidence_reason: str) -> str:
    graph = result.get("graph_build", {})
    inference = result.get("full_graph_inference", [])
    eq = result.get("cross_device_equivalence", {})
    aggregate = eq.get("aggregate", {})
    occupancy = result.get("dgx_occupancy", {})
    lines = [
        "# G5 full-graph 무샘플링 계측 REPORT",
        "",
        "## 승계 봉인",
        "",
        f"- 승계 봉인 `prereg.json` SHA-256: `{result['seals']['prereg_json_sha256']}`",
        f"- 승계 봉인 `PREREG.csv` SHA-256: `{result['seals']['prereg_csv_sha256']}`",
        "- 재봉인·수정: `0`회",
        f"- claim_policy: `{CLAIM_POLICY}`",
        "- 판정 정책: 수치 계측만 기록; 봉투/동등성 판정 미출력.",
        "",
        "## 실행 범위",
        "",
        f"- 상태: `{result['status']}`",
        f"- 대상 def: `{TARGET_DEFINITION}`",
        f"- 입력 선분 수: `{fmt_number(graph.get('input_segment_count'))}`",
        "- sampling: `0`; retraining: `0`; accuracy claim: `0`.",
        "- 입력은 기존 staged DXF, frozen graph builder, 3개 GNN-A checkpoint, 봉인 val-A SEG-IR 1개로 제한.",
        "",
        "## DGX 점유 기록",
        "",
        f"- 최초 SSH 실호출 UTC: `{occupancy.get('initial_ssh_probe_utc')}`",
        f"- 최초 :8000 HTTP 상태: `{occupancy.get('initial_vllm_http_state')}`",
        f"- 최초 container 상태: `{occupancy.get('initial_vllm_container_state')}`",
        f"- 실행 전 host available bytes: `{fmt_number(occupancy.get('initial_host_available_bytes'))}`",
        f"- vLLM stop 명령: `{occupancy.get('vllm_stop_command')}`",
        f"- vLLM restart 명령: `{occupancy.get('vllm_restart_command')}`",
        f"- 실행 후 :8000 HTTP reachable: `{occupancy.get('post_job_vllm_http_reachable')}`",
        f"- DGX container launch: `{occupancy.get('container_launch_command')}`",
        f"- remote cleanup: `{occupancy.get('remote_cleanup_command')}`",
        "",
        "## full-graph 구축 수치",
        "",
        "| metric | value |",
        "|---|---:|",
        f"| node_count | {fmt_number(graph.get('node_count'))} |",
        f"| directed_edge_count | {fmt_number(graph.get('directed_edge_count'))} |",
        f"| build_wall_seconds | {fmt_number(graph.get('build_wall_seconds'))} |",
        f"| dxf_read_wall_seconds | {fmt_number(graph.get('dxf_read_wall_seconds'))} |",
        f"| seg_ir_expand_wall_seconds | {fmt_number(graph.get('seg_ir_expand_wall_seconds'))} |",
        f"| typed_graph_build_wall_seconds | {fmt_number(graph.get('typed_graph_build_wall_seconds'))} |",
        f"| peak_host_rss_bytes | {fmt_number(graph.get('peak_host_rss_bytes'))} |",
        f"| graph_hash | `{graph.get('graph_hash', '')}` |",
        f"| config_hash | `{graph.get('config_hash', '')}` |",
        "",
        "## 무샘플링 inference 수치",
        "",
        "| seed | forward_s | nodes/s | empirical_p95_s (n=1) | peak_cuda_alloc_B | peak_cuda_reserved_B | peak_host_rss_B | positive_ratio@0.5 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in inference:
        dist = row["output_distribution"]
        lines.append(
            "| {seed} | {wall} | {rate} | {p95} | {alloc} | {reserved} | {rss} | {ratio} |".format(
                seed=row["seed"],
                wall=fmt_number(row["single_forward_wall_seconds"]),
                rate=fmt_number(row["nodes_per_second"]),
                p95=fmt_number(row["single_sample_empirical_p95_seconds"]),
                alloc=fmt_number(row["peak_cuda_allocated_bytes"]),
                reserved=fmt_number(row["peak_cuda_reserved_bytes"]),
                rss=fmt_number(row["peak_host_rss_bytes"]),
                ratio=fmt_number(dist["positive_ratio_at_0_5"]),
            )
        )
    lines.extend(
        [
            "",
            "## 출력 분포 수치",
            "",
            "| seed | min | p01 | p05 | p25 | p50 | p75 | p95 | p99 | max | mean | std_population |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in inference:
        d = row["output_distribution"]
        values = [fmt_number(d[key]) for key in ("min", "p01", "p05", "p25", "p50", "p75", "p95", "p99", "max", "mean", "std_population")]
        lines.append(f"| {row['seed']} | " + " | ".join(values) + " |")
    lines.extend(
        [
            "",
            "## 시드 간 일치도 수치",
            "",
        ]
    )
    for row in result.get("seed_agreement", {}).get("pairwise_binary_agreement", []):
        lines.append(
            f"- seed {row['seed_left']}↔{row['seed_right']} binary agreement: `{fmt_number(row['pairwise_binary_agreement'])}`"
        )
    lines.append(
        f"- three-seed unanimous ratio: `{fmt_number(result.get('seed_agreement', {}).get('three_seed_unanimous_ratio'))}`"
    )
    lines.extend(
        [
            "",
            "## 장치 간 동등성 입력 수치 (판정 없음)",
            "",
            f"- reference drawing_id: `{REFERENCE_DRAWING_ID}`",
            f"- rule: `{eq.get('rule', '')}`",
            "",
            "| metric | value |",
            "|---|---:|",
        ]
    )
    for key in (
        "local_within_max_abs",
        "local_within_p99_abs",
        "local_within_max_rel",
        "local_within_p99_rel",
        "dgx_within_max_abs",
        "dgx_within_p99_abs",
        "dgx_within_max_rel",
        "dgx_within_p99_rel",
        "cross_device_max_abs",
        "cross_device_p99_abs",
        "cross_device_max_rel",
        "cross_device_p99_rel",
        "sealed_absolute_limit",
        "sealed_relative_limit",
    ):
        lines.append(f"| {key} | {fmt_number(aggregate.get(key))} |")
    lines.extend(
        [
            "",
            "## selftest / 불변성",
            "",
            f"- same-input forward max_abs: `{fmt_number(result['selftest']['same_input_forward_max_abs'])}`",
            f"- forbidden filesystem calls: `{result['selftest']['forbidden_filesystem_calls']}`",
            f"- blocked-before-filesystem kinds: `{', '.join(result['selftest']['forbidden_kinds_blocked_before_filesystem'])}`",
            "- checkpoint SHA-256 before/after: 동일 문자열 기록.",
            "- adopted seal SHA-256 before/after: 동일 문자열 기록.",
            "",
            "## 증거 파일",
            "",
            f"- `evidence.csv` fallback reason: {evidence_reason}",
            "",
            "## 미해결",
            "",
            "- 원 패킷은 Ornith-35B vLLM(:8000)이 실행 중이라고 기술했으나, 착수 전 SSH/HTTP 실측에서 `vllm-qwen` container는 이미 exited(0), :8000은 unreachable이었다. 본 셀은 stop/restart 명령을 발행하지 않았다.",
            "- 승계 봉인은 `val_A_truth`를 추가 금지한다. 원 패킷보다 엄격한 봉인 문언을 적용했고 truth 접근은 0이다.",
            "- 봉인 output_policy는 `evidence.xlsx`를 요구하지만 필수 spreadsheet artifact dependency loader가 이 실행 세션에 없어 원 패킷이 허용한 CSV fallback을 사용했다. 이 충돌은 봉인 우선 규약상 unresolved로 유지한다.",
            "- `single_sample_empirical_p95_seconds`는 봉인 필드명대로 seed당 단일 forward 표본의 empirical p95이며 표본 수는 1이다.",
            "",
            "CELL_COMPLETE: g5_full_graph",
        ]
    )
    return "\n".join(lines) + "\n"


def finalize(args: argparse.Namespace) -> dict[str, Any]:
    local_reference = json.loads(args.local_reference.read_text(encoding="utf-8"))
    dgx_raw = json.loads(args.dgx_raw.read_text(encoding="utf-8"))
    selftest = json.loads(args.selftest_json.read_text(encoding="utf-8"))
    if local_reference.get("status") != "COMPLETE":
        raise RuntimeError("local reference is not complete")
    if dgx_raw.get("status") != "COMPLETE":
        raise RuntimeError(f"DGX raw status is not complete: {dgx_raw.get('status')}")
    dgx_reference = dgx_raw["cross_device_reference"]
    equivalence = aggregate_equivalence(local_reference, dgx_reference)
    seals = verify_seals(args.prereg, args.prereg_csv)
    if dgx_raw.get("seals", {}).get("prereg_json_sha256") != seals["prereg_json_sha256"]:
        raise RuntimeError("DGX adopted prereg hash mismatch")
    code_hash = sha256_file(Path(__file__).resolve())
    result = {
        "schema": SCHEMA,
        "cell": CELL_ID,
        "status": "COMPLETE",
        "generated_utc": utc_now(),
        "claim_policy": CLAIM_POLICY,
        "judgment_policy": "numeric_measurements_only_no_envelope_or_equivalence_verdict",
        "seals": seals,
        "provenance": {
            "g5_full_graph_py_sha256": code_hash,
            "graph_builder_sha256": EXPECTED_HASHES["graph_builder.py"],
            "architecture_source_sha256": EXPECTED_HASHES["gnn_e2_v2.py"],
            "staged_dxf_sha256": EXPECTED_HASHES["1_export.dxf"],
            "reference_seg_ir_sha256": EXPECTED_HASHES[f"{REFERENCE_DRAWING_ID}.segir.json"],
            "checkpoint_sha256": dgx_raw["checkpoint_hashes_after"],
            "local_reference_raw_sha256": sha256_file(args.local_reference),
            "dgx_raw_sha256": sha256_file(args.dgx_raw),
            "selftest_raw_sha256": sha256_file(args.selftest_json),
        },
        "scope": {
            "target_definition": TARGET_DEFINITION,
            "target_input_segment_count": TARGET_SEGMENT_COUNT,
            "sampling_count": 0,
            "retraining_count": 0,
            "accuracy_claim_count": 0,
            "original_CAD_reads": 0,
            "test_reads": 0,
            "val_B_reads": 0,
            "val_A_truth_reads": 0,
        },
        "graph_build": dgx_raw["graph_build"],
        "full_graph_inference": dgx_raw["full_graph_inference"],
        "seed_agreement": dgx_raw["seed_agreement"],
        "device_tensor_materialization": dgx_raw["device_tensor_materialization"],
        "cross_device_equivalence": equivalence,
        "resource_accounting": {
            "dgx_wall_seconds": dgx_raw["wall_seconds"],
            "dgx_cap_hours": CAP_HOURS,
            "oom_downgrade_count": 0,
        },
        "dgx_occupancy": {
            "initial_ssh_probe_utc": args.initial_ssh_probe_utc,
            "initial_vllm_http_state": args.initial_vllm_http_state,
            "initial_vllm_container_state": args.initial_vllm_container_state,
            "initial_host_available_bytes": args.initial_host_available_bytes,
            "container_launch_command": args.container_launch_command,
            "remote_cleanup_command": args.remote_cleanup_command,
            "vllm_stop_command": "NOT_ISSUED_PREEXISTING_DOWN",
            "vllm_restart_command": "NOT_ISSUED_NO_CELL_STOP_ACTION",
            "pre_job_vllm_probe": dgx_raw["vllm"]["pre_job_probe"],
            "post_job_vllm_probe": dgx_raw["vllm"]["post_job_probe"],
            "post_job_vllm_http_reachable": dgx_raw["vllm"]["post_job_probe"]["reachable"],
        },
        "selftest": selftest,
        "unresolved": [
            "pre-existing vLLM :8000 outage observed before any G5 action",
            "spreadsheet artifact dependency loader unavailable; evidence.csv fallback used",
            "single-sample empirical p95 has n=1 per seed",
        ],
    }
    atomic_write_json(args.results, result)
    write_evidence_csv(args.evidence_csv, result)
    report = render_report(result, args.evidence_reason)
    atomic_write_text(args.report, report)
    return result


def add_common_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--builder", type=Path, default=DEFAULT_BUILDER)
    parser.add_argument("--architecture", type=Path, default=DEFAULT_ARCHITECTURE)
    parser.add_argument("--checkpoint-dir", type=Path, default=DEFAULT_CHECKPOINT_DIR)
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--prereg-csv", type=Path, default=DEFAULT_PREREG_CSV)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--selftest-output", type=Path)
    add_common_inputs(parser)
    subparsers = parser.add_subparsers(dest="command")

    reference = subparsers.add_parser("reference", help="run the sealed val-A reference")
    add_common_inputs(reference)
    reference.add_argument("--role", required=True)
    reference.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    reference.add_argument("--output", type=Path, required=True)

    dgx = subparsers.add_parser("dgx", help="run full graph and reference on DGX")
    add_common_inputs(dgx)
    dgx.add_argument("--dxf", type=Path, required=True)
    dgx.add_argument("--reference", type=Path, required=True)
    dgx.add_argument("--output", type=Path, required=True)
    dgx.add_argument("--vllm-probe-url", default="http://127.0.0.1:8000/v1/models")

    aggregate = subparsers.add_parser("finalize", help="aggregate raw measurements")
    add_common_inputs(aggregate)
    aggregate.add_argument("--local-reference", type=Path, required=True)
    aggregate.add_argument("--dgx-raw", type=Path, required=True)
    aggregate.add_argument("--selftest-json", type=Path, required=True)
    aggregate.add_argument("--results", type=Path, required=True)
    aggregate.add_argument("--evidence-csv", type=Path, required=True)
    aggregate.add_argument("--report", type=Path, required=True)
    aggregate.add_argument("--initial-ssh-probe-utc", required=True)
    aggregate.add_argument("--initial-vllm-http-state", required=True)
    aggregate.add_argument("--initial-vllm-container-state", required=True)
    aggregate.add_argument("--initial-host-available-bytes", type=int, required=True)
    aggregate.add_argument("--container-launch-command", required=True)
    aggregate.add_argument("--remote-cleanup-command", required=True)
    aggregate.add_argument("--evidence-reason", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.selftest:
        run_selftest(args)
        return 0
    if args.command == "reference":
        payload = run_reference(
            role=args.role,
            builder_path=args.builder,
            architecture_path=args.architecture,
            reference_path=args.reference,
            checkpoint_dir=args.checkpoint_dir,
            prereg_path=args.prereg,
            prereg_csv_path=args.prereg_csv,
            output_path=args.output,
        )
        print(json.dumps({"status": payload["status"], "output": str(args.output)}))
        return 0
    if args.command == "dgx":
        payload = run_dgx(
            builder_path=args.builder,
            architecture_path=args.architecture,
            dxf_path=args.dxf,
            reference_path=args.reference,
            checkpoint_dir=args.checkpoint_dir,
            prereg_path=args.prereg,
            prereg_csv_path=args.prereg_csv,
            output_path=args.output,
            vllm_probe_url=args.vllm_probe_url,
        )
        print(json.dumps({"status": payload["status"], "output": str(args.output)}))
        return 0 if payload["status"] == "COMPLETE" else 2
    if args.command == "finalize":
        result = finalize(args)
        print(json.dumps({"status": result["status"], "results": str(args.results)}))
        return 0
    parser.error("choose --selftest, reference, dgx, or finalize")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
