#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2 W2 GNN formal numeric executor.

The executable is deliberately constrained to CubiCasa train and the exact
W2-09 val-A manifest.  It imports the frozen graph builder, screen-v2 encoder
and SSL primitives, and W2-02 protocol helpers read-only.  No orchestration
adoption/rejection verdict is computed here.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import math
import os
import random
import sys
import threading
import time
import traceback
import warnings
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


for _thread_env in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_thread_env, "8")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

import joblib
import numpy as np
import psutil
import torch
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score
from torch import nn
from torch.nn import functional as F


CELL_DIR = Path(__file__).resolve().parent
CKPT_DIR = CELL_DIR / "ckpt"
RESULTS_PATH = CELL_DIR / "results.json"
REPORT_PATH = CELL_DIR / "REPORT.md"
PREREG_PATH = CELL_DIR / "prereg.json"
PREREG_CSV_PATH = CELL_DIR / "PREREG.csv"

REPO_ROOT = Path(r"D:\dev\99_tools\autocad-sdk-router")
RUN_CELLS = Path(r"D:\runs\e2_program\cells")
PACKET_PATH = Path(r"D:\runs\e2_program\build\PACKET_gnn_formal.md")
DOSSIER_PATH = REPO_ROOT / "reports" / "e2" / "dossiers" / "calibration_P3.md"
PREREG_BASE_PATH = REPO_ROOT / "reports" / "e2" / "prereg_r2_v1.json"
AMENDMENT1_PATH = REPO_ROOT / "reports" / "e2" / "prereg_r2_v1_amendment1.json"
AMENDMENT2_PATH = REPO_ROOT / "reports" / "e2" / "prereg_r2_v1_amendment2.json"
GRAPH_BUILDER_PATH = REPO_ROOT / "tools" / "e2" / "cells" / "graph_builder.py"
SCREEN_V2_PATH = RUN_CELLS / "gnn_e2_screen_v2" / "gnn_e2_v2.py"
SCREEN_V2_RESULTS_PATH = RUN_CELLS / "gnn_e2_screen_v2" / "results.json"
W2_09_PATH = RUN_CELLS / "w2_09_valb" / "w2_09_valb.py"
SPLIT_MANIFEST_PATH = RUN_CELLS / "w2_09_valb" / "split_manifest.json"
W2_02_DIR = RUN_CELLS / "w2_02_twohop"
W2_02_PATH = W2_02_DIR / "w2_02_twohop.py"
W2_02_RESULTS_PATH = W2_02_DIR / "results.json"
W2_02_REPORT_PATH = W2_02_DIR / "REPORT.md"
W2_02_PREREG_PATH = W2_02_DIR / "prereg.json"
W2_02_README_PATH = W2_02_DIR / "README.md"
W2_01_RESULTS_PATH = RUN_CELLS / "w2_01_autopsy" / "autopsy_results.json"
CUBICASA_ML_PATH = REPO_ROOT / "tools" / "e2" / "ext" / "cubicasa_ml.py"
CML_CTX_PATH = RUN_CELLS / "cml_ctx" / "cml_ctx.py"
TRAIN_ROOT = REPO_ROOT / "runs" / "e2_ext_cubicasa" / "ir" / "train"
VAL_ROOT = REPO_ROOT / "runs" / "e2_ext_cubicasa" / "ir" / "val"
TRAIN_NPZ_PATH = REPO_ROOT / "runs" / "e2_ext_cubicasa" / "features" / "train.npz"
BASELINE_DESIGN_TRAIN_PATH = W2_02_DIR / "_work" / "design_full_train.npy"
BASELINE_CONTEXT_VAL_PATH = W2_02_DIR / "_work" / "context6_valA.npy"
BASELINE_TWOHOP_VAL_PATH = W2_02_DIR / "_work" / "twohop_valA.npy"

SEEDS = (17, 29, 43)
THRESHOLD = 0.5
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 43
RAM_CAP_BYTES = 48 * 1024**3
RTX_CAP_HOURS = 132.0
PRIOR_G5_CHARGE_HOURS = 0.4481405555555563
FORMAL_AVAILABLE_SECONDS = (RTX_CAP_HOURS - PRIOR_G5_CHARGE_HOURS) * 3600.0
EXPECTED_GRAPH_CONFIG_HASH = "56911f4633979a3fe00fd56be2d0a39ac06757ed255ed49ed18ca20ba9d4ac49"
EXPECTED_SPLIT_CONTENT_HASH = "5e16541d7191ad01c57a9cee72172f63112ed68590dd371aff5bf0aaaab8e07b"
EXPECTED_TRAIN_IR_AGGREGATE = "104179a194d977ac3433a7b0e91342bacf75e509dd676f5217e693c7f34570bf"
EXPECTED_VAL_A_IR_AGGREGATE = "1db9634138e715b29fa19d2387fbb878150770234b60b764f66a765c61c53cbb"
EXPECTED_PREREG_SHA256 = "53d10948a0e56f98cab77dfb962d8db5b6ccdbc639a962ff7327bbe4878bcaca"
EXPECTED_PREREG_CSV_SHA256 = "34dfdd6ec179d8fabfd211d3c78c1c67bbb5e45b1ca483fa69c2190a201ce476"

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
FORBIDDEN_FEATURE_TOKENS = (
    "handle",
    "sid",
    "sequence",
    "order",
    "filename",
    "file_name",
    "block_name",
    "layer",
    "text",
    "name",
    "family_id",
    "label",
)

EXPECTED_INPUT_HASHES = {
    "packet": (PACKET_PATH, "499e27629cc9391f14a222257e4b114c26d14b77874537d293073a87ee66d682"),
    "dossier": (DOSSIER_PATH, "6641dd63044ad22b94d6c2a61baf85f86ca4c9191745659171e8a806864c294d"),
    "prereg_base": (PREREG_BASE_PATH, "fc93dad9232cfd877802c1d53996357eccc710daff8cfb2cf7c865bf7f78bcd2"),
    "amendment1": (AMENDMENT1_PATH, "30f752db803f7f589d1a8d1f1a2d8557364ae2d624f76a639533161f552b8283"),
    "amendment2": (AMENDMENT2_PATH, "6e29bbd5f8c502a1bc36277a535521c117408b2460e80511907d610321dd442a"),
    "split_manifest": (SPLIT_MANIFEST_PATH, "8aad64eeda77df55296fc711c21d7befdeada7fe379aeafec81fd1691aea044f"),
    "w2_09_source": (W2_09_PATH, "85481aa49f6cf62307588e73ea502160079f1172de8f5f927a1a7c23bb5ef1de"),
    "graph_builder": (GRAPH_BUILDER_PATH, "c95d4a30d30e0db157fe56102053a7884902b7749464f7f4cb8852c0819321f6"),
    "screen_v2": (SCREEN_V2_PATH, "895249f0b6c77ac8f8a7cfb73e859a0882681ad6bba6e337480b55db269ce120"),
    "screen_v2_results": (SCREEN_V2_RESULTS_PATH, "564320aa1a2e92c0f80fbc56cd2438c3902edc7708e86b12ab96be7dcd60db14"),
    "w2_02_source": (W2_02_PATH, "ae81bf8c5311fc19c8ad38f7feca5d1c15bf39a71d41a1fb925775d6e63aafe6"),
    "w2_02_results": (W2_02_RESULTS_PATH, "391aedddf26c0b44116de89bcb27b1b3a6fed07aa1ae8b9dcae9d8b71995bbfb"),
    "w2_02_report": (W2_02_REPORT_PATH, "fb40b501ae603bd3ca67460c3445f0e4b5c9ed07891be3cda53ab7c968786751"),
    "w2_02_prereg": (W2_02_PREREG_PATH, "6c7db98abe8eb08edd05f09ef1b52d68aa849b9cc2aa803c033e66d01dff747d"),
    "w2_01_results": (W2_01_RESULTS_PATH, "251f01eb6a3f3e59c85ab12dcbb3a1c05a173cf2647c26508ab8bc6c7d316fd2"),
    "train_npz": (TRAIN_NPZ_PATH, "8f72d8931c6e08927bf027ee87f1bc5362ab1a85217862e09a0cddd6b0b0d5aa"),
    "baseline_design_full_train": (BASELINE_DESIGN_TRAIN_PATH, "8e2ca80cc52ab9ebcbb9f8f60fb1d4177186cd1e7fafcfee486cfcbc40335a11"),
    "baseline_context_val_A": (BASELINE_CONTEXT_VAL_PATH, "b568bb4c3dffce46629355bf7670cf00f6c86ecbfe14b5feb87f4e6103449a91"),
    "baseline_twohop_val_A": (BASELINE_TWOHOP_VAL_PATH, "ef0febd1d6da09a2a129c26dcc19028828e80bb4fa19c9db2b3eb5b423cef1df"),
    "cubicasa_ml": (CUBICASA_ML_PATH, "e9baf9f361ca9cfc1a113e084bf5c34be33cf9b6c14615c2ed080f771cd3b466"),
    "cml_ctx": (CML_CTX_PATH, "ac0ef389ca971a87645763bd4153cf4f564731d17f8689331bc9de04a67e1b98"),
}


@dataclass(frozen=True)
class FormalConfig:
    hidden_dim: int = 64
    dropout: float = 0.10
    learning_rate: float = 3e-3
    weight_decay: float = 1e-4
    finetune_epochs: int = 16
    pretrain_epochs: int = 20
    train_graph_batch_size: int = 4
    ssl_graph_batch_size: int = 5
    minimum_graph_batch_size: int = 1
    mask_probability: float = 0.15
    edge_keep_probability: float = 0.85
    contrastive_temperature: float = 0.20
    masked_loss_weight: float = 1.0
    contrastive_loss_weight: float = 1.0
    gradient_clip_norm: float = 5.0
    sampled_node_cap: int = 4096
    threshold: float = THRESHOLD
    bootstrap_seed: int = BOOTSTRAP_SEED
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES


@dataclass
class GraphSample:
    graph_id: str
    drawing_id: str
    family_id: str
    split: str
    x: np.ndarray
    edge_src: np.ndarray
    edge_dst: np.ndarray
    edge_type: np.ndarray
    node_y: np.ndarray
    eval_index: np.ndarray | None = None


class BudgetKill(RuntimeError):
    pass


class PersistentOOM(RuntimeError):
    pass


class Blocked(RuntimeError):
    pass


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


def stable_int(*parts: str) -> int:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little", signed=False)


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def assert_output(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(CELL_DIR.resolve())
    except ValueError as error:
        raise RuntimeError(f"write escaped cell root: {resolved}") from error
    return resolved


def atomic_write_json(path: Path, value: Any) -> None:
    path = assert_output(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(json_ready(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def atomic_write_text(path: Path, value: str) -> None:
    path = assert_output(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    temporary.replace(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import read-only module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def assert_feature_allowlist(names: Sequence[str]) -> None:
    if tuple(names) != EXPECTED_FEATURE_NAMES:
        raise RuntimeError(f"17-feature allowlist drift: {tuple(names)!r}")
    hits = {
        name: token
        for name in names
        for token in FORBIDDEN_FEATURE_TOKENS
        if token in name.casefold()
    }
    if hits:
        raise RuntimeError(f"identifier/name/layer/label feature guard: {hits}")


class ResourceMonitor:
    def __init__(self, interval_seconds: float = 0.1):
        self.interval_seconds = interval_seconds
        self.started_wall = time.perf_counter()
        self.process = psutil.Process()
        self.peak_rss_bytes = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _rss(self) -> int:
        total = self.process.memory_info().rss
        for child in self.process.children(recursive=True):
            try:
                total += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return int(total)

    def _sample(self) -> None:
        self.peak_rss_bytes = max(self.peak_rss_bytes, self._rss())

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._sample()

    def start(self) -> None:
        self._sample()
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._sample()

    def check(self, phase: str) -> None:
        self._sample()
        elapsed = time.perf_counter() - self.started_wall
        if self.peak_rss_bytes > RAM_CAP_BYTES:
            raise BudgetKill(
                f"BUDGET_KILL RAM cap during {phase}: {self.peak_rss_bytes / 1024**3:.6f} GiB"
            )
        if elapsed >= FORMAL_AVAILABLE_SECONDS:
            raise BudgetKill(
                f"BUDGET_KILL cumulative G5 RTX cap before {phase}: "
                f"{PRIOR_G5_CHARGE_HOURS + elapsed / 3600.0:.6f} h"
            )

    def metrics(self) -> dict[str, Any]:
        self._sample()
        elapsed = time.perf_counter() - self.started_wall
        output = {
            "formal_elapsed_seconds": elapsed,
            "formal_elapsed_hours": elapsed / 3600.0,
            "prior_G5_charge_hours": PRIOR_G5_CHARGE_HOURS,
            "cumulative_G5_charge_hours": PRIOR_G5_CHARGE_HOURS + elapsed / 3600.0,
            "G5_RTX_cap_hours": RTX_CAP_HOURS,
            "peak_process_tree_rss_bytes": self.peak_rss_bytes,
            "peak_process_tree_rss_gib": self.peak_rss_bytes / 1024**3,
            "RAM_cap_gib": RAM_CAP_BYTES / 1024**3,
        }
        if torch.cuda.is_available():
            output.update(
                {
                    "peak_cuda_allocated_bytes": int(torch.cuda.max_memory_allocated()),
                    "peak_cuda_allocated_gib": torch.cuda.max_memory_allocated() / 1024**3,
                    "peak_cuda_reserved_bytes": int(torch.cuda.max_memory_reserved()),
                    "peak_cuda_reserved_gib": torch.cuda.max_memory_reserved() / 1024**3,
                }
            )
        return output


class GuardedDataset:
    """Read wrapper whose forbidden decisions occur before path construction/stat/read."""

    def __init__(self, split_manifest: dict[str, Any]):
        records = split_manifest["frozen"]["drawing_records"]
        self.val_a_records = [row for row in records if row["split"] == "A"]
        self.val_a_ids = {str(row["drawing_id"]) for row in self.val_a_records}
        self.val_b_ids = {str(row["drawing_id"]) for row in records if row["split"] == "B"}
        self.train_root = TRAIN_ROOT.resolve()
        self.val_root = VAL_ROOT.resolve()
        self.filesystem_calls = 0
        self.counters = {
            "train_ir_reads": 0,
            "train_truth_reads": 0,
            "val_A_ir_reads": 0,
            "val_A_truth_reads": 0,
            "val_B_drawing_reads": 0,
            "test_reads": 0,
            "original_CAD_reads": 0,
            "forbidden_attempts_blocked_before_filesystem": 0,
        }

    def train_files(self) -> list[Path]:
        files = sorted(self.train_root.glob("*.segir.json"))
        if len(files) != 4200:
            raise RuntimeError(f"expected 4200 train SEG-IR files, found {len(files)}")
        return files

    def _read_bytes(self, path: Path) -> bytes:
        self.filesystem_calls += 1
        return path.read_bytes()

    def read_train(self, path: Path, *, truth: bool = False) -> bytes:
        resolved = path.resolve()
        if resolved.parent != self.train_root:
            self.counters["forbidden_attempts_blocked_before_filesystem"] += 1
            raise PermissionError("blocked non-train input")
        suffix = ".truth.json" if truth else ".segir.json"
        if not resolved.name.endswith(suffix):
            self.counters["forbidden_attempts_blocked_before_filesystem"] += 1
            raise PermissionError(f"train suffix guard: {suffix}")
        self.counters["train_truth_reads" if truth else "train_ir_reads"] += 1
        return self._read_bytes(resolved)

    def read_val_a(self, drawing_id: str, *, truth: bool = False) -> bytes:
        if drawing_id not in self.val_a_ids:
            self.counters["forbidden_attempts_blocked_before_filesystem"] += 1
            if drawing_id in self.val_b_ids:
                raise PermissionError("blocked val-B drawing before filesystem")
            raise PermissionError("drawing is not in frozen val-A before filesystem")
        suffix = ".truth.json" if truth else ".segir.json"
        path = (self.val_root / f"{drawing_id}{suffix}").resolve()
        if path.parent != self.val_root:
            raise PermissionError("val-A path containment failed")
        self.counters["val_A_truth_reads" if truth else "val_A_ir_reads"] += 1
        return self._read_bytes(path)

    def probe_test_block(self) -> None:
        self.counters["forbidden_attempts_blocked_before_filesystem"] += 1
        raise PermissionError("test access structurally blocked before filesystem")


def collate_graphs(
    samples: Sequence[GraphSample],
    device: torch.device,
    *,
    shuffle_edge_types: bool = False,
    shuffle_seed: int = 0,
) -> dict[str, torch.Tensor]:
    if not samples:
        raise ValueError("empty graph batch")
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    srcs: list[np.ndarray] = []
    dsts: list[np.ndarray] = []
    types: list[np.ndarray] = []
    graph_indices: list[np.ndarray] = []
    offset = 0
    for graph_position, sample in enumerate(samples):
        xs.append(sample.x)
        ys.append(sample.node_y)
        srcs.append(sample.edge_src.astype(np.int64, copy=False) + offset)
        dsts.append(sample.edge_dst.astype(np.int64, copy=False) + offset)
        edge_type = sample.edge_type
        if shuffle_edge_types:
            rng = np.random.default_rng(
                stable_int(str(shuffle_seed), sample.drawing_id, "edge-type-shuffle")
            )
            edge_type = rng.permutation(edge_type)
        types.append(edge_type.astype(np.int64, copy=False))
        graph_indices.append(np.full(len(sample.x), graph_position, dtype=np.int64))
        offset += len(sample.x)
    return {
        "x": torch.as_tensor(np.concatenate(xs), dtype=torch.float32, device=device),
        "node_y": torch.as_tensor(np.concatenate(ys), dtype=torch.float32, device=device),
        "edge_src": torch.as_tensor(np.concatenate(srcs), dtype=torch.long, device=device),
        "edge_dst": torch.as_tensor(np.concatenate(dsts), dtype=torch.long, device=device),
        "edge_type": torch.as_tensor(np.concatenate(types), dtype=torch.long, device=device),
        "graph_index": torch.as_tensor(
            np.concatenate(graph_indices), dtype=torch.long, device=device
        ),
        "graph_count": torch.tensor(len(samples), dtype=torch.long, device=device),
    }


class NodeGNN(nn.Module):
    def __init__(self, screen: Any, relation_count: int, config: FormalConfig):
        super().__init__()
        self.encoder = screen.TypedEncoder(
            len(EXPECTED_FEATURE_NAMES), config.hidden_dim, relation_count, config.dropout
        )
        self.node_head = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim // 2),
            nn.GELU(),
            nn.Linear(config.hidden_dim // 2, 1),
        )

    def forward(self, batch: dict[str, torch.Tensor], message_mode: str = "full") -> torch.Tensor:
        hidden = self.encoder(
            batch["x"],
            batch["edge_src"],
            batch["edge_dst"],
            batch["edge_type"],
            message_mode,
        )
        return self.node_head(hidden).squeeze(1)


class SSLObjective(nn.Module):
    def __init__(self, encoder: nn.Module, config: FormalConfig):
        super().__init__()
        self.encoder = encoder
        self.decoder = nn.Linear(config.hidden_dim, len(EXPECTED_FEATURE_NAMES))
        self.projector = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.hidden_dim),
        )


def clone_state(model: nn.Module) -> dict[str, torch.Tensor]:
    return {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}


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


def verify_inputs() -> dict[str, Any]:
    if sha256_file(PREREG_PATH) != EXPECTED_PREREG_SHA256:
        raise RuntimeError("local prereg.json dual-seal hash drift")
    if sha256_file(PREREG_CSV_PATH) != EXPECTED_PREREG_CSV_SHA256:
        raise RuntimeError("local PREREG.csv dual-seal hash drift")
    observed_hashes: dict[str, str] = {}
    for name, (path, expected) in EXPECTED_INPUT_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(f"missing read-only prerequisite {name}: {path}")
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(f"read-only input hash drift for {name}: {observed} != {expected}")
        observed_hashes[name] = observed

    local_prereg = load_json(PREREG_PATH)
    if tuple(local_prereg["frozen"]["seeds"]) != SEEDS:
        raise RuntimeError("local seed seal drift")
    if local_prereg["frozen"]["graph"]["config_sha256"] != EXPECTED_GRAPH_CONFIG_HASH:
        raise RuntimeError("local graph-config seal drift")
    base = load_json(PREREG_BASE_PATH)
    amendment1_text = AMENDMENT1_PATH.read_text(encoding="utf-8")
    try:
        json.loads(amendment1_text)
        amendment1_json_valid = True
    except json.JSONDecodeError:
        amendment1_json_valid = False
    amendment2 = load_json(AMENDMENT2_PATH)
    if int(base["test_policy"]["wave_test_contact"]) != 0:
        raise RuntimeError("base prereg no-test policy drift")
    if "G5 RTX 총 132h" not in amendment1_text:
        raise RuntimeError("amendment1 G5 RTX cap drift")
    if "dual_seal_mandate" not in amendment2:
        raise RuntimeError("amendment2 dual-seal mandate missing")

    manifest = load_json(SPLIT_MANIFEST_PATH)
    if manifest["content_hash"] != EXPECTED_SPLIT_CONTENT_HASH:
        raise RuntimeError("split manifest content hash drift")
    if canonical_hash(manifest["frozen"]) != manifest["content_hash"]:
        raise RuntimeError("split manifest canonical content hash mismatch")
    split_a = manifest["frozen"]["splits"]["A"]
    if (int(split_a["drawing_count"]), int(split_a["row_count"])) != (198, 167556):
        raise RuntimeError("val-A size drift")
    if int(manifest["frozen"]["family_crossing_count"]) != 0:
        raise RuntimeError("W2-09 family crossing is nonzero")

    w2_results = load_json(W2_02_RESULTS_PATH)
    reference = float(w2_results["metrics"]["summaries"]["full"]["primary_auprc"]["mean"])
    if reference != 0.8740823342431078:
        raise RuntimeError("W2-02 reference AUPRC drift")
    autopsy = load_json(W2_01_RESULTS_PATH)
    bottom_20 = [str(row["stratum"]) for row in autopsy["analysis"]["family_auprc"]["bottom_20"]]
    if bottom_20 != list(local_prereg["frozen"]["w2_01_bottom_20_family_ids"]):
        raise RuntimeError("W2-01 bottom-20 family seal drift")

    if not torch.cuda.is_available():
        raise Blocked("local RTX unavailable")
    gpu_name = torch.cuda.get_device_name(0)
    if "RTX" not in gpu_name.upper():
        raise Blocked(f"non-RTX CUDA device: {gpu_name}")
    return {
        "checked_at": now_iso(),
        "input_hashes": observed_hashes,
        "dual_seal": {
            "prereg_json_sha256": EXPECTED_PREREG_SHA256,
            "prereg_csv_sha256": EXPECTED_PREREG_CSV_SHA256,
        },
        "split_manifest_content_hash": manifest["content_hash"],
        "w2_02_reference_val_A_AUPRC_mean": reference,
        "amendment1_json_valid": amendment1_json_valid,
        "amendment1_validation": "byte hash plus sealed G5 RTX total 132h text",
        "w2_02_README_present": W2_02_README_PATH.is_file(),
        "w2_02_narrative_fallback": str(W2_02_REPORT_PATH),
        "gpu": {
            "name": gpu_name,
            "memory_total_bytes": int(torch.cuda.get_device_properties(0).total_memory),
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
        },
    }


def deterministic_sample_graph(sample: GraphSample, seed: int, cap: int) -> GraphSample:
    n = len(sample.x)
    if n <= cap:
        cap = max(256, n // 2)
    positives = np.flatnonzero(sample.node_y == 1)
    if len(positives) > cap:
        raise PersistentOOM(
            f"cannot preserve {len(positives)} positives inside sampled cap {cap} for {sample.graph_id}"
        )
    positive_set = set(int(value) for value in positives)
    negatives = [index for index in range(n) if index not in positive_set]
    ranked = sorted(
        negatives,
        key=lambda index: (
            hashlib.sha256(
                str(seed).encode("ascii") + b"\0" + sample.x[index].tobytes()
            ).digest(),
            index,
        ),
    )
    selected = np.asarray(sorted([*positive_set, *ranked[: max(0, cap - len(positives))]]), dtype=np.int64)
    old_to_new = np.full(n, -1, dtype=np.int32)
    old_to_new[selected] = np.arange(len(selected), dtype=np.int32)
    keep_edge = (old_to_new[sample.edge_src] >= 0) & (old_to_new[sample.edge_dst] >= 0)
    return GraphSample(
        graph_id=sample.graph_id,
        drawing_id=sample.drawing_id,
        family_id=sample.family_id,
        split=sample.split + "_SAMPLED_OOM_DOWNGRADE",
        x=sample.x[selected],
        edge_src=old_to_new[sample.edge_src[keep_edge]].astype(np.int32, copy=False),
        edge_dst=old_to_new[sample.edge_dst[keep_edge]].astype(np.int32, copy=False),
        edge_type=sample.edge_type[keep_edge].astype(np.int16, copy=False),
        node_y=sample.node_y[selected],
        eval_index=None,
    )


def run_selftest(
    config: FormalConfig,
    preflight: dict[str, Any],
    builder: Any,
    screen: Any,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    lines = ["SELFTEST_BEGIN"]
    details: dict[str, Any] = {}

    device = torch.device("cpu")
    mini = GraphSample(
        graph_id="selftest",
        drawing_id="selftest",
        family_id="selftest",
        split="selftest",
        x=np.asarray(
            [[math.sin((row + 1) * (column + 1)) for column in range(17)] for row in range(6)],
            dtype=np.float32,
        ),
        edge_src=np.asarray([0, 1, 1, 2, 2, 3, 3, 4, 4, 5], dtype=np.int32),
        edge_dst=np.asarray([1, 0, 2, 1, 3, 2, 4, 3, 5, 4], dtype=np.int32),
        edge_type=np.asarray([0, 0, 1, 1, 2, 2, 3, 3, 4, 4], dtype=np.int16),
        node_y=np.asarray([1, 1, 0, 0, 1, 0], dtype=np.float32),
    )

    def one_step() -> tuple[float, dict[str, torch.Tensor]]:
        screen.set_seed(17)
        model = NodeGNN(screen, 6, FormalConfig(hidden_dim=16, dropout=0.0)).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        batch = collate_graphs([mini], device)
        optimizer.zero_grad(set_to_none=True)
        loss = F.binary_cross_entropy_with_logits(
            model(batch), batch["node_y"], pos_weight=torch.tensor(1.0)
        )
        loss.backward()
        optimizer.step()
        return float(loss.detach()), clone_state(model)

    loss_1, state_1 = one_step()
    loss_2, state_2 = one_step()
    max_delta = max(
        float(torch.max(torch.abs(state_1[key] - state_2[key]))) for key in state_1
    )
    reproducible = loss_1 == loss_2 and max_delta == 0.0
    details["one_step_reproducibility"] = {
        "ok": reproducible,
        "loss_run_1": loss_1,
        "loss_run_2": loss_2,
        "max_parameter_abs_delta": max_delta,
    }
    lines.append(
        "one_step_reproducibility "
        f"ok={int(reproducible)} loss1={loss_1:.12f} loss2={loss_2:.12f} max_delta={max_delta:.3e}"
    )

    allowlist_ok = True
    malicious_rejected = False
    try:
        assert_feature_allowlist(builder.FEATURE_NAMES)
    except Exception:
        allowlist_ok = False
    try:
        assert_feature_allowlist((*EXPECTED_FEATURE_NAMES[:-1], "layer_name"))
    except RuntimeError:
        malicious_rejected = True
    feature_guard_ok = allowlist_ok and malicious_rejected
    details["feature_name_label_guard"] = {
        "ok": feature_guard_ok,
        "feature_count": len(builder.FEATURE_NAMES),
        "forbidden_feature_count": 0,
        "malicious_layer_name_rejected": malicious_rejected,
        "labels_are_separate_tensor": True,
    }
    lines.append(
        "feature_name_label_guard "
        f"ok={int(feature_guard_ok)} features=17 forbidden=0 malicious_rejected={int(malicious_rejected)}"
    )

    dataset = GuardedDataset(manifest)
    filesystem_before = dataset.filesystem_calls
    val_b_blocked = test_blocked = False
    try:
        dataset.read_val_a(sorted(dataset.val_b_ids)[0])
    except PermissionError:
        val_b_blocked = True
    filesystem_after_val_b = dataset.filesystem_calls
    try:
        dataset.probe_test_block()
    except PermissionError:
        test_blocked = True
    filesystem_after_test = dataset.filesystem_calls
    isolation_ok = (
        val_b_blocked
        and test_blocked
        and filesystem_before == filesystem_after_val_b == filesystem_after_test
        and dataset.counters["val_B_drawing_reads"] == 0
        and dataset.counters["test_reads"] == 0
    )
    details["forbidden_split_pre_filesystem_guard"] = {
        "ok": isolation_ok,
        "val_B_probe_blocked": val_b_blocked,
        "test_probe_blocked": test_blocked,
        "filesystem_calls_before": filesystem_before,
        "filesystem_calls_after_val_B_probe": filesystem_after_val_b,
        "filesystem_calls_after_test_probe": filesystem_after_test,
        "val_B_drawing_reads": 0,
        "test_reads": 0,
    }
    lines.append(
        "forbidden_split_pre_filesystem_guard "
        f"ok={int(isolation_ok)} valB_blocked={int(val_b_blocked)} test_blocked={int(test_blocked)} "
        f"filesystem_calls={filesystem_after_test}"
    )

    frozen = manifest["frozen"]
    records = frozen["drawing_records"]
    a_records = [row for row in records if row["split"] == "A"]
    b_records = [row for row in records if row["split"] == "B"]
    a_families = {str(row["family_id"]) for row in a_records}
    b_families = {str(row["family_id"]) for row in b_records}
    bottom_20 = set(load_json(PREREG_PATH)["frozen"]["w2_01_bottom_20_family_ids"])
    a_ids = sorted(str(row["drawing_id"]) for row in a_records)
    a_family_ids = sorted(a_families)
    family_ok = (
        canonical_hash(frozen) == manifest["content_hash"]
        and len(a_records) == 198
        and len(b_records) == 198
        and not (a_families & b_families)
        and int(frozen["family_crossing_count"]) == 0
        and canonical_hash(a_ids) == frozen["splits"]["A"]["drawing_ids_sha256"]
        and canonical_hash(a_family_ids) == frozen["splits"]["A"]["family_ids_sha256"]
        and bottom_20 <= a_families
    )
    details["family_fold_integrity"] = {
        "ok": family_ok,
        "manifest_content_hash": manifest["content_hash"],
        "val_A_drawings": len(a_records),
        "val_B_drawings_metadata_only": len(b_records),
        "val_A_families": len(a_families),
        "val_B_families_metadata_only": len(b_families),
        "family_overlap_count": len(a_families & b_families),
        "W2_01_bottom_20_in_val_A": bottom_20 <= a_families,
    }
    lines.append(
        "family_fold_integrity "
        f"ok={int(family_ok)} valA=198 family_overlap={len(a_families & b_families)} "
        f"bottom20_in_valA={int(bottom_20 <= a_families)}"
    )

    large = GraphSample(
        graph_id="oom-sim",
        drawing_id="oom-sim",
        family_id="oom-sim",
        split="selftest",
        x=np.tile(mini.x, (834, 1))[:5000],
        edge_src=np.arange(4999, dtype=np.int32),
        edge_dst=np.arange(1, 5000, dtype=np.int32),
        edge_type=np.arange(4999, dtype=np.int32).astype(np.int16) % 6,
        node_y=np.r_[np.ones(50, dtype=np.float32), np.zeros(4950, dtype=np.float32)],
    )
    sampled = deterministic_sample_graph(large, 17, config.sampled_node_cap)
    oom_ok = (
        len(sampled.x) == config.sampled_node_cap
        and int(sampled.node_y.sum()) == 50
        and len(sampled.edge_src) < len(large.edge_src)
        and "SAMPLED_OOM_DOWNGRADE" in sampled.split
    )
    oom_transcript = [
        {"attempted_graph_batch_size": size, "outcome": "simulated_cuda_oom"}
        for size in (8, 4, 2, 1)
    ]
    oom_transcript.append(
        {
            "outcome": "deterministic_sampled_downgrade_success",
            "original_nodes": len(large.x),
            "sampled_nodes": len(sampled.x),
            "positive_nodes_preserved": int(sampled.node_y.sum()),
        }
    )
    details["oom_honest_downgrade"] = {
        "ok": oom_ok,
        "simulation_only": True,
        "attempts": oom_transcript,
        "actual_run_events_recorded_separately": True,
    }
    lines.append(
        "oom_honest_downgrade "
        f"ok={int(oom_ok)} simulation_only=1 nodes=5000->{len(sampled.x)} positives=50->50"
    )

    details["dual_seal"] = {"ok": True, **preflight["dual_seal"]}
    lines.append(
        "dual_seal ok=1 "
        f"prereg_json_sha256={EXPECTED_PREREG_SHA256} prereg_csv_sha256={EXPECTED_PREREG_CSV_SHA256}"
    )
    details["ok"] = all(
        details[key]["ok"]
        for key in (
            "one_step_reproducibility",
            "feature_name_label_guard",
            "forbidden_split_pre_filesystem_guard",
            "family_fold_integrity",
            "oom_honest_downgrade",
            "dual_seal",
        )
    )
    lines.append(f"honest_status={'OK' if details['ok'] else 'ERROR'}")
    lines.append("SELFTEST_END")
    return {"ok": details["ok"], "details": details, "transcript": "\n".join(lines)}


def point_metrics(y: np.ndarray, probability: np.ndarray) -> dict[str, Any]:
    y = np.asarray(y, dtype=np.int8)
    probability = np.asarray(probability, dtype=np.float64)
    if len(y) != len(probability) or not np.all(np.isfinite(probability)):
        raise RuntimeError("metric input length or finiteness failure")
    predicted = probability >= THRESHOLD
    positive = y == 1
    tp = int(np.sum(predicted & positive))
    fp = int(np.sum(predicted & ~positive))
    fn = int(np.sum(~predicted & positive))
    tn = int(np.sum(~predicted & ~positive))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "auprc": float(average_precision_score(y, probability)),
        "f1": float(f1),
        "precision": float(precision),
        "recall": float(recall),
        "threshold": THRESHOLD,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "n": int(len(y)),
        "positive_count": int(np.sum(positive)),
    }


def ece_10bin(y: np.ndarray, probability: np.ndarray) -> dict[str, Any]:
    y = np.asarray(y, dtype=np.float64)
    probability = np.asarray(probability, dtype=np.float64)
    bins: list[dict[str, Any]] = []
    ece = 0.0
    for index in range(10):
        low = index / 10.0
        high = (index + 1) / 10.0
        mask = (probability >= low) & (
            probability <= high if index == 9 else probability < high
        )
        count = int(np.sum(mask))
        confidence = float(np.mean(probability[mask])) if count else None
        accuracy = float(np.mean(y[mask])) if count else None
        gap = abs(confidence - accuracy) if count else None
        if count:
            ece += count / len(y) * float(gap)
        bins.append(
            {
                "index": index,
                "low_inclusive": low,
                "high_inclusive": index == 9,
                "high": high,
                "count": count,
                "mean_probability": confidence,
                "positive_rate": accuracy,
                "absolute_gap": gap,
            }
        )
    return {"ece": float(ece), "bin_count": 10, "bins": bins}


def metric_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {"seed_count": len(rows)}
    for metric in ("auprc", "f1", "ece"):
        values = np.asarray([float(row[metric]) for row in rows], dtype=np.float64)
        output[metric] = {
            "mean": float(values.mean()),
            "std_population": float(values.std(ddof=0)),
            "min": float(values.min()),
            "max": float(values.max()),
        }
    return output


def graph_sample_from_result(
    *,
    graph_id: str,
    drawing_id: str,
    family_id: str,
    split: str,
    result: dict[str, Any],
    labels: np.ndarray,
    eval_index: np.ndarray | None = None,
) -> GraphSample:
    if len(result["features"]) != len(labels):
        raise RuntimeError(f"graph/label row mismatch: {graph_id}")
    return GraphSample(
        graph_id=graph_id,
        drawing_id=drawing_id,
        family_id=family_id,
        split=split,
        x=np.asarray(result["features"], dtype=np.float32),
        edge_src=np.asarray(result["edge_src"], dtype=np.int32),
        edge_dst=np.asarray(result["edge_dst"], dtype=np.int32),
        edge_type=np.asarray(result["edge_type"], dtype=np.int16),
        node_y=np.asarray(labels, dtype=np.float32),
        eval_index=(
            None if eval_index is None else np.asarray(eval_index, dtype=np.int32)
        ),
    )


def build_datasets(
    builder: Any,
    screen: Any,
    w2: Any,
    manifest: dict[str, Any],
    resources: ResourceMonitor,
) -> dict[str, Any]:
    """Build every train and val-A drawing with the frozen graph builder."""

    dataset = GuardedDataset(manifest)
    config = builder.GraphConfig()
    assert_feature_allowlist(builder.FEATURE_NAMES)
    if config.digest() != EXPECTED_GRAPH_CONFIG_HASH:
        raise RuntimeError("frozen graph config hash drift")

    with np.load(TRAIN_NPZ_PATH, allow_pickle=False) as archive:
        train_y_archive = np.asarray(archive["y"], dtype=np.int8)
        train_gid = np.asarray(archive["gid"], dtype=np.int32)
        train_scale = float(np.asarray(archive["scale"]).item())
    if train_scale != 12.0 or len(train_y_archive) != 3862317:
        raise RuntimeError("train feature archive universe drift")

    train_files = dataset.train_files()
    if int(train_gid.min()) != 0 or int(train_gid.max()) + 1 != len(train_files):
        raise RuntimeError("train gid coverage does not match sorted train drawings")
    expected_by_gid = np.bincount(train_gid, minlength=len(train_files))
    cubicasa_module, _context_module = w2._load_modules()
    train_samples: list[GraphSample] = []
    train_families: set[str] = set()
    train_ir_aggregate = hashlib.sha256()
    train_truth_aggregate = hashlib.sha256()
    graph_totals = {
        "train_nodes": 0,
        "train_directed_edges": 0,
        "val_A_nodes": 0,
        "val_A_directed_edges": 0,
        "max_nodes_per_graph": 0,
        "max_directed_edges_per_graph": 0,
        "unresolved_reference_count": 0,
    }
    offset = 0
    train_started = time.perf_counter()
    for drawing_index, ir_path in enumerate(train_files):
        resources.check(f"train graph build {drawing_index + 1}")
        truth_path = ir_path.with_name(ir_path.name.replace(".segir.json", ".truth.json"))
        ir_raw = dataset.read_train(ir_path)
        truth_raw = dataset.read_train(truth_path, truth=True)
        train_ir_aggregate.update(ir_path.name.encode("utf-8"))
        train_ir_aggregate.update(b"\0")
        train_ir_aggregate.update(hashlib.sha256(ir_raw).digest())
        train_truth_aggregate.update(truth_path.name.encode("utf-8"))
        train_truth_aggregate.update(b"\0")
        train_truth_aggregate.update(hashlib.sha256(truth_raw).digest())
        ir = json.loads(ir_raw)
        truth = json.loads(truth_raw)
        result = builder.build_graph(ir, config, collect_edges=True)
        handles = [str(row["handle"]) for row in result["prepared"]["records"]]
        if len(handles) != len(set(handles)):
            raise RuntimeError(f"duplicate prepared handles in train graph {ir_path.name}")
        wall_handles = {str(value) for value in truth["wall_handles_flat"]}
        labels = np.asarray([handle in wall_handles for handle in handles], dtype=np.int8)
        baseline_base, baseline_labels = w2._base_features_labels(
            ir, truth, cubicasa_module
        )
        expected = int(expected_by_gid[drawing_index])
        end = offset + expected
        if (
            len(handles) != expected
            or baseline_base.shape != (expected, len(w2.BASE_FEATURE_NAMES))
            or baseline_labels is None
            or not np.array_equal(baseline_labels, train_y_archive[offset:end])
            or int(labels.sum()) != int(baseline_labels.sum())
        ):
            raise RuntimeError(f"train graph/truth/archive alignment mismatch: {ir_path.name}")
        offset = end
        family_id = screen.canonical_geometry_fingerprint(ir)
        train_families.add(family_id)
        sample = graph_sample_from_result(
            graph_id=f"train/{ir_path.stem.replace('.segir', '')}",
            drawing_id=ir_path.name.removesuffix(".segir.json"),
            family_id=family_id,
            split="train",
            result=result,
            labels=labels,
        )
        train_samples.append(sample)
        graph_totals["train_nodes"] += len(sample.x)
        graph_totals["train_directed_edges"] += len(sample.edge_src)
        graph_totals["max_nodes_per_graph"] = max(
            graph_totals["max_nodes_per_graph"], len(sample.x)
        )
        graph_totals["max_directed_edges_per_graph"] = max(
            graph_totals["max_directed_edges_per_graph"], len(sample.edge_src)
        )
        graph_totals["unresolved_reference_count"] += int(
            result["stats"]["unresolved_reference_count"]
        )
        if (drawing_index + 1) % 50 == 0 or drawing_index + 1 == len(train_files):
            elapsed = time.perf_counter() - train_started
            print(
                f"[graph:train] {drawing_index + 1}/4200 drawings "
                f"nodes={graph_totals['train_nodes']:,} edges={graph_totals['train_directed_edges']:,} "
                f"seconds={elapsed:.1f}",
                flush=True,
            )
            gc.collect()
        del result, ir, truth, ir_raw, truth_raw

    if offset != len(train_y_archive):
        raise RuntimeError("final train row alignment mismatch")
    if train_ir_aggregate.hexdigest() != EXPECTED_TRAIN_IR_AGGREGATE:
        raise RuntimeError("train IR aggregate hash drift")

    val_records = dataset.val_a_records
    family_ids = sorted({str(row["family_id"]) for row in val_records})
    family_position = {value: index for index, value in enumerate(family_ids)}
    if len(family_ids) != 198:
        raise RuntimeError("val-A family count drift")
    val_rows = int(manifest["frozen"]["splits"]["A"]["row_count"])
    val_base = np.empty((val_rows, len(w2.BASE_FEATURE_NAMES)), dtype=np.float32)
    val_y = np.empty(val_rows, dtype=np.int8)
    val_family_index = np.empty(val_rows, dtype=np.int32)
    context_val = np.load(BASELINE_CONTEXT_VAL_PATH, mmap_mode="r")
    twohop_val = np.load(BASELINE_TWOHOP_VAL_PATH, mmap_mode="r")
    if context_val.shape != (val_rows, len(w2.CONTEXT_FEATURE_NAMES)):
        raise RuntimeError("W2-02 val-A context work artifact shape drift")
    if twohop_val.shape != (val_rows, len(w2.TWOHOP_FEATURE_NAMES)):
        raise RuntimeError("W2-02 val-A two-hop work artifact shape drift")

    val_samples: list[GraphSample] = []
    val_ir_aggregate = hashlib.sha256()
    val_truth_aggregate = hashlib.sha256()
    val_families_observed: set[str] = set()
    val_offset = 0
    val_started = time.perf_counter()
    for record_index, record in enumerate(val_records):
        resources.check(f"val-A graph build {record_index + 1}")
        drawing_id = str(record["drawing_id"])
        ir_raw = dataset.read_val_a(drawing_id)
        truth_raw = dataset.read_val_a(drawing_id, truth=True)
        val_ir_aggregate.update(f"{drawing_id}.segir.json".encode("utf-8"))
        val_ir_aggregate.update(b"\0")
        val_ir_aggregate.update(hashlib.sha256(ir_raw).digest())
        val_truth_aggregate.update(f"{drawing_id}.truth.json".encode("utf-8"))
        val_truth_aggregate.update(b"\0")
        val_truth_aggregate.update(hashlib.sha256(truth_raw).digest())
        ir = json.loads(ir_raw)
        truth = json.loads(truth_raw)
        result = builder.build_graph(ir, config, collect_edges=True)
        handles = [str(row["handle"]) for row in result["prepared"]["records"]]
        if len(handles) != len(set(handles)):
            raise RuntimeError(f"duplicate prepared handles in val-A graph {drawing_id}")
        wall_handles = {str(value) for value in truth["wall_handles_flat"]}
        labels = np.asarray([handle in wall_handles for handle in handles], dtype=np.int8)
        base, baseline_labels = w2._base_features_labels(ir, truth, cubicasa_module)
        expected = int(record["row_count"])
        score = cubicasa_module.w1_real_defs.fast_score(
            ir,
            params=cubicasa_module.ce._params(float(cubicasa_module._frozen())),
        )
        baseline_handles = [str(handle) for handle in score["per_handle"]]
        graph_index_by_handle = {handle: index for index, handle in enumerate(handles)}
        if any(handle not in graph_index_by_handle for handle in baseline_handles):
            raise RuntimeError(f"val-A common-handle universe mismatch: {drawing_id}")
        eval_index = np.asarray(
            [graph_index_by_handle[handle] for handle in baseline_handles], dtype=np.int32
        )
        if (
            len(handles) != expected
            or base.shape != (expected, len(w2.BASE_FEATURE_NAMES))
            or baseline_labels is None
            or len(baseline_handles) != expected
            or not np.array_equal(labels[eval_index], baseline_labels)
        ):
            raise RuntimeError(f"val-A graph/baseline alignment mismatch: {drawing_id}")
        family_id = str(record["family_id"])
        fingerprint = screen.canonical_geometry_fingerprint(ir)
        if fingerprint != str(record["family_fingerprint"]):
            raise RuntimeError(f"val-A geometry-family fingerprint drift: {drawing_id}")
        val_families_observed.add(fingerprint)
        end = val_offset + expected
        val_base[val_offset:end] = base
        val_y[val_offset:end] = baseline_labels
        val_family_index[val_offset:end] = family_position[family_id]
        val_offset = end
        sample = graph_sample_from_result(
            graph_id=f"val-A/{drawing_id}",
            drawing_id=drawing_id,
            family_id=family_id,
            split="val-A",
            result=result,
            labels=labels,
            eval_index=eval_index,
        )
        val_samples.append(sample)
        graph_totals["val_A_nodes"] += len(sample.x)
        graph_totals["val_A_directed_edges"] += len(sample.edge_src)
        graph_totals["max_nodes_per_graph"] = max(
            graph_totals["max_nodes_per_graph"], len(sample.x)
        )
        graph_totals["max_directed_edges_per_graph"] = max(
            graph_totals["max_directed_edges_per_graph"], len(sample.edge_src)
        )
        graph_totals["unresolved_reference_count"] += int(
            result["stats"]["unresolved_reference_count"]
        )
        if (record_index + 1) % 20 == 0 or record_index + 1 == len(val_records):
            print(
                f"[graph:val-A] {record_index + 1}/198 drawings "
                f"rows={val_offset:,} seconds={time.perf_counter() - val_started:.1f}",
                flush=True,
            )
            gc.collect()
        del result, ir, truth, ir_raw, truth_raw

    if val_offset != val_rows or graph_totals["val_A_nodes"] != val_rows:
        raise RuntimeError("final val-A row alignment mismatch")
    if val_ir_aggregate.hexdigest() != EXPECTED_VAL_A_IR_AGGREGATE:
        raise RuntimeError("val-A IR subset aggregate hash drift")
    train_val_family_overlap = train_families & val_families_observed
    if train_val_family_overlap:
        raise Blocked(
            f"near-duplicate geometry family crosses train and val-A: {len(train_val_family_overlap)}"
        )
    if dataset.counters["val_B_drawing_reads"] or dataset.counters["test_reads"]:
        raise RuntimeError("forbidden read counter became nonzero")

    val_design = np.column_stack((val_base, context_val, twohop_val)).astype(
        np.float32, copy=False
    )
    if val_design.shape != (val_rows, len(w2.FULL_FEATURE_NAMES)):
        raise RuntimeError("W2-02 full val-A design shape drift")
    return {
        "train_samples": train_samples,
        "val_samples": val_samples,
        "train_y": train_y_archive,
        "val_y": val_y,
        "val_family_index": val_family_index,
        "family_ids": family_ids,
        "baseline_val_design": val_design,
        "audit": {
            "graph_config_hash": config.digest(),
            "feature_names": list(builder.FEATURE_NAMES),
            "feature_count": len(builder.FEATURE_NAMES),
            "identifier_name_layer_text_label_feature_count": 0,
            "train_drawings": len(train_samples),
            "train_rows": len(train_y_archive),
            "train_geometry_families": len(train_families),
            "train_ir_aggregate_sha256": train_ir_aggregate.hexdigest(),
            "train_truth_aggregate_sha256": train_truth_aggregate.hexdigest(),
            "val_A_drawings": len(val_samples),
            "val_A_rows": len(val_y),
            "val_A_families": len(family_ids),
            "val_A_ir_subset_aggregate_sha256": val_ir_aggregate.hexdigest(),
            "val_A_truth_subset_aggregate_sha256": val_truth_aggregate.hexdigest(),
            "train_val_A_geometry_family_collision_count": 0,
            "totals": graph_totals,
            "read_counters": dataset.counters,
            "filesystem_calls": dataset.filesystem_calls,
            "train_build_seconds": time.perf_counter() - train_started,
            "val_A_build_seconds": time.perf_counter() - val_started,
        },
    }


def graph_batches(
    samples: Sequence[GraphSample], batch_size: int, epoch_seed: int
) -> list[list[GraphSample]]:
    order = list(samples)
    random.Random(epoch_seed).shuffle(order)
    return [order[start : start + batch_size] for start in range(0, len(order), batch_size)]


def run_batches_with_oom_policy(
    groups: list[list[GraphSample]],
    operation: Any,
    *,
    stage: str,
    seed: int,
    config: FormalConfig,
    sampled_cache: dict[str, GraphSample],
    oom_events: list[dict[str, Any]],
) -> tuple[list[float], int]:
    losses: list[float] = []
    smallest_success = min((len(group) for group in groups), default=0)
    queue = list(groups)
    while queue:
        group = queue.pop(0)
        try:
            losses.append(float(operation(group)))
            smallest_success = min(smallest_success or len(group), len(group))
        except torch.cuda.OutOfMemoryError as error:
            event: dict[str, Any] = {
                "stage": stage,
                "seed": seed,
                "attempted_graph_batch_size": len(group),
                "outcome": "cuda_out_of_memory",
                "message": str(error)[:500],
                "recorded_at": now_iso(),
            }
            oom_events.append(event)
            torch.cuda.empty_cache()
            gc.collect()
            if len(group) > config.minimum_graph_batch_size:
                split = max(config.minimum_graph_batch_size, len(group) // 2)
                left, right = group[:split], group[split:]
                event["downgrade"] = "graph_batch_halved"
                event["downgraded_max_graph_batch_size"] = max(len(left), len(right))
                queue = [left, right] + queue
                continue
            sample = group[0]
            if "SAMPLED_OOM_DOWNGRADE" in sample.split:
                event["downgrade"] = "persistent_after_sampled_downgrade"
                raise PersistentOOM(
                    f"{stage}: persistent CUDA OOM after deterministic sampled downgrade"
                ) from error
            sampled = deterministic_sample_graph(sample, seed, config.sampled_node_cap)
            sampled_cache[sample.graph_id] = sampled
            event.update(
                {
                    "downgrade": "deterministic_induced_node_sampling",
                    "original_nodes": len(sample.x),
                    "sampled_nodes": len(sampled.x),
                    "original_edges": len(sample.edge_src),
                    "sampled_edges": len(sampled.edge_src),
                    "positive_nodes_preserved": int(sampled.node_y.sum()),
                }
            )
            queue = [[sampled]] + queue
    return losses, smallest_success


def cuda_sync() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def train_ssl(
    *,
    seed: int,
    encoder: nn.Module,
    samples: Sequence[GraphSample],
    screen: Any,
    config: FormalConfig,
    device: torch.device,
    resources: ResourceMonitor,
    oom_events: list[dict[str, Any]],
) -> tuple[dict[str, torch.Tensor], list[dict[str, Any]], dict[str, Any]]:
    model = SSLObjective(encoder, config).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    history: list[dict[str, Any]] = []
    sampled_cache: dict[str, GraphSample] = {}
    smallest_batch = config.ssl_graph_batch_size
    for epoch in range(config.pretrain_epochs):
        resources.check(f"SSL seed {seed} epoch {epoch + 1}")
        effective = [sampled_cache.get(sample.graph_id, sample) for sample in samples]
        groups = graph_batches(effective, config.ssl_graph_batch_size, seed + 1000 + epoch)
        step_position = 0
        cuda_sync()
        started = time.perf_counter()

        def operation(group: list[GraphSample]) -> float:
            nonlocal step_position
            optimizer.zero_grad(set_to_none=True)
            batch = collate_graphs(group, device)
            generator = torch.Generator(device=device)
            generator.manual_seed(seed + epoch * 100_000 + step_position)
            step_position += 1
            view_1 = screen.augmented_view(
                batch, generator, config.mask_probability, config.edge_keep_probability
            )
            view_2 = screen.augmented_view(
                batch, generator, config.mask_probability, config.edge_keep_probability
            )
            hidden_1 = model.encoder(view_1[0], view_1[1], view_1[2], view_1[3])
            hidden_2 = model.encoder(view_2[0], view_2[1], view_2[2], view_2[3])
            reconstruction = 0.5 * (
                F.mse_loss(model.decoder(hidden_1)[view_1[4]], batch["x"][view_1[4]])
                + F.mse_loss(model.decoder(hidden_2)[view_2[4]], batch["x"][view_2[4]])
            )
            graph_count = len(group)
            pooled_1 = screen.mean_pool(hidden_1, batch["graph_index"], graph_count)
            pooled_2 = screen.mean_pool(hidden_2, batch["graph_index"], graph_count)
            z_1 = F.normalize(model.projector(pooled_1), dim=1)
            z_2 = F.normalize(model.projector(pooled_2), dim=1)
            logits = z_1 @ z_2.T / config.contrastive_temperature
            targets = torch.arange(graph_count, device=device)
            contrastive = 0.5 * (
                F.cross_entropy(logits, targets) + F.cross_entropy(logits.T, targets)
            )
            loss = (
                config.masked_loss_weight * reconstruction
                + config.contrastive_loss_weight * contrastive
            )
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), config.gradient_clip_norm)
            optimizer.step()
            return float(loss.detach())

        losses, successful_batch = run_batches_with_oom_policy(
            groups,
            operation,
            stage=f"SSL_seed_{seed}_epoch_{epoch + 1}",
            seed=seed,
            config=config,
            sampled_cache=sampled_cache,
            oom_events=oom_events,
        )
        cuda_sync()
        smallest_batch = min(smallest_batch, successful_batch)
        row = {
            "epoch": epoch + 1,
            "mean_total_loss": float(np.mean(losses)),
            "steps": len(losses),
            "elapsed_seconds": time.perf_counter() - started,
        }
        history.append(row)
        print(
            f"[ssl seed={seed}] epoch={epoch + 1}/{config.pretrain_epochs} "
            f"loss={row['mean_total_loss']:.6f} steps={row['steps']} seconds={row['elapsed_seconds']:.2f}",
            flush=True,
        )
    return clone_state(model.encoder), history, {
        "smallest_successful_graph_batch_size": smallest_batch,
        "sampled_graph_count": len(sampled_cache),
        "sampled_graph_ids": sorted(sampled_cache),
    }


def train_node_model(
    *,
    arm: str,
    seed: int,
    initial_state: dict[str, torch.Tensor],
    pretrained_encoder_state: dict[str, torch.Tensor] | None,
    samples: Sequence[GraphSample],
    screen: Any,
    relation_count: int,
    positive_weight: float,
    config: FormalConfig,
    device: torch.device,
    resources: ResourceMonitor,
    oom_events: list[dict[str, Any]],
) -> tuple[NodeGNN, list[dict[str, Any]], dict[str, Any]]:
    screen.set_seed(seed)
    model = NodeGNN(screen, relation_count, config)
    model.load_state_dict(initial_state)
    if pretrained_encoder_state is not None:
        model.encoder.load_state_dict(pretrained_encoder_state)
    model.to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    pos_weight = torch.tensor(positive_weight, dtype=torch.float32, device=device)
    history: list[dict[str, Any]] = []
    sampled_cache: dict[str, GraphSample] = {}
    smallest_batch = config.train_graph_batch_size
    for epoch in range(config.finetune_epochs):
        resources.check(f"{arm} seed {seed} epoch {epoch + 1}")
        model.train()
        effective = [sampled_cache.get(sample.graph_id, sample) for sample in samples]
        groups = graph_batches(effective, config.train_graph_batch_size, seed + epoch)
        cuda_sync()
        started = time.perf_counter()

        def operation(group: list[GraphSample]) -> float:
            optimizer.zero_grad(set_to_none=True)
            batch = collate_graphs(group, device)
            logits = model(batch)
            loss = F.binary_cross_entropy_with_logits(
                logits, batch["node_y"], pos_weight=pos_weight
            )
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), config.gradient_clip_norm)
            optimizer.step()
            return float(loss.detach())

        losses, successful_batch = run_batches_with_oom_policy(
            groups,
            operation,
            stage=f"{arm}_seed_{seed}_epoch_{epoch + 1}",
            seed=seed,
            config=config,
            sampled_cache=sampled_cache,
            oom_events=oom_events,
        )
        cuda_sync()
        smallest_batch = min(smallest_batch, successful_batch)
        row = {
            "epoch": epoch + 1,
            "mean_node_loss": float(np.mean(losses)),
            "steps": len(losses),
            "elapsed_seconds": time.perf_counter() - started,
        }
        history.append(row)
        print(
            f"[{arm} seed={seed}] epoch={epoch + 1}/{config.finetune_epochs} "
            f"loss={row['mean_node_loss']:.6f} steps={row['steps']} seconds={row['elapsed_seconds']:.2f}",
            flush=True,
        )
    return model, history, {
        "positive_class_weight": positive_weight,
        "smallest_successful_graph_batch_size": smallest_batch,
        "sampled_graph_count": len(sampled_cache),
        "sampled_graph_ids": sorted(sampled_cache),
    }


def predict_node_model(
    *,
    model: NodeGNN,
    samples: Sequence[GraphSample],
    device: torch.device,
    resources: ResourceMonitor,
    seed: int,
    message_mode: str = "full",
    shuffle_edge_types: bool = False,
) -> np.ndarray:
    model.eval()
    probabilities: list[np.ndarray] = []
    with torch.no_grad():
        for index, sample in enumerate(samples):
            resources.check(f"val-A inference seed {seed} graph {index + 1}")
            try:
                batch = collate_graphs(
                    [sample],
                    device,
                    shuffle_edge_types=shuffle_edge_types,
                    shuffle_seed=seed,
                )
                logits = model(batch, message_mode)
                graph_probability = torch.sigmoid(logits).cpu().numpy()
                if sample.eval_index is not None:
                    graph_probability = graph_probability[sample.eval_index]
                probabilities.append(graph_probability)
            except torch.cuda.OutOfMemoryError as error:
                torch.cuda.empty_cache()
                raise PersistentOOM(
                    "full-graph val-A evaluation OOM; sampled evaluation is forbidden"
                ) from error
    return np.concatenate(probabilities).astype(np.float64, copy=False)


def fit_baseline_control(
    *,
    w2: Any,
    train_y: np.ndarray,
    val_y: np.ndarray,
    val_design: np.ndarray,
    resources: ResourceMonitor,
) -> tuple[dict[int, np.ndarray], list[dict[str, Any]], list[dict[str, Any]]]:
    train_design = np.load(BASELINE_DESIGN_TRAIN_PATH, mmap_mode="r")
    if train_design.shape != (len(train_y), len(w2.FULL_FEATURE_NAMES)):
        raise RuntimeError("W2-02 full train design shape drift")
    expected_params = load_json(PREREG_PATH)["frozen"]["arms"][
        "control_twohop_GBDT_full"
    ]["estimator_parameters_except_seed"]
    reference_rows = {
        int(row["seed"]): row
        for row in load_json(W2_02_RESULTS_PATH)["metrics"]["seed_metrics"]["full"]
    }
    predictions: dict[int, np.ndarray] = {}
    records: list[dict[str, Any]] = []
    model_artifacts: list[dict[str, Any]] = []
    for seed in SEEDS:
        resources.check(f"two-hop control fit seed {seed}")
        model = HistGradientBoostingClassifier(random_state=seed)
        actual_params = normalized_estimator_params(model)
        if actual_params != expected_params:
            raise RuntimeError("HistGradientBoosting parameters drift from W2-02")
        started = time.perf_counter()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model.fit(train_design, train_y)
        fit_seconds = time.perf_counter() - started
        probability = model.predict_proba(val_design)[:, 1].astype(np.float64)
        metrics = point_metrics(val_y, probability)
        calibration = ece_10bin(val_y, probability)
        metrics["ece"] = calibration["ece"]
        reference = reference_rows[seed]
        reproduction_delta = {
            "auprc": metrics["auprc"] - float(reference["primary_auprc"]),
            "f1": metrics["f1"] - float(reference["f1"]),
        }
        if max(abs(value) for value in reproduction_delta.values()) > 1e-12:
            raise RuntimeError(
                f"fresh W2-02 refit did not reproduce seed {seed}: {reproduction_delta}"
            )
        checkpoint_path = CKPT_DIR / f"control_twohop_full_seed_{seed}.joblib"
        joblib.dump(
            {
                "schema": "e2.gnn_formal.control_checkpoint.v1",
                "arm": "control_twohop_GBDT_full",
                "seed": seed,
                "fit_universe": "train only",
                "evaluation_universe": "val-A only",
                "features": list(w2.FULL_FEATURE_NAMES),
                "threshold": THRESHOLD,
                "model": model,
            },
            assert_output(checkpoint_path),
            compress=3,
        )
        predictions[seed] = probability
        records.append(
            {
                "seed": seed,
                **metrics,
                "ece_10bin": calibration,
                "fit_seconds": fit_seconds,
                "n_iter": int(model.n_iter_),
                "warning_count": len(caught),
                "warnings": [str(item.message)[:300] for item in caught],
                "W2_02_reproduction_delta": reproduction_delta,
            }
        )
        model_artifacts.append(
            {
                "arm": "control_twohop_GBDT_full",
                "seed": seed,
                "path": str(checkpoint_path),
                "sha256": sha256_file(checkpoint_path),
            }
        )
        print(
            f"[control seed={seed}] valA_AUPRC={metrics['auprc']:.8f} "
            f"valA_F1={metrics['f1']:.8f} seconds={fit_seconds:.2f}",
            flush=True,
        )
        del model
        gc.collect()
    return predictions, records, model_artifacts


def fit_gnn_arms(
    *,
    screen: Any,
    relation_count: int,
    train_samples: Sequence[GraphSample],
    val_samples: Sequence[GraphSample],
    val_y: np.ndarray,
    config: FormalConfig,
    device: torch.device,
    resources: ResourceMonitor,
) -> dict[str, Any]:
    positive_count = float(sum(np.sum(sample.node_y) for sample in train_samples))
    total_count = int(sum(len(sample.node_y) for sample in train_samples))
    negative_count = total_count - positive_count
    if positive_count <= 0 or negative_count <= 0:
        raise RuntimeError("train node truth requires both classes")
    positive_weight = negative_count / positive_count

    predictions: dict[str, dict[str, dict[int, np.ndarray]]] = {
        arm: {"full": {}, "NoMessage": {}, "edge_type_shuffle": {}}
        for arm in ("GNN_A_no_pretrain", "GNN_B_SSL_pretrain")
    }
    seed_records: dict[str, list[dict[str, Any]]] = {
        "GNN_A_no_pretrain": [],
        "GNN_B_SSL_pretrain": [],
    }
    training_records: dict[str, dict[str, Any]] = {
        "GNN_A_no_pretrain": {},
        "GNN_B_SSL_pretrain": {},
    }
    model_artifacts: list[dict[str, Any]] = []
    oom_events: list[dict[str, Any]] = []

    for seed in SEEDS:
        resources.check(f"GNN seed {seed} initialization")
        screen.set_seed(seed)
        template = NodeGNN(screen, relation_count, config)
        initial_state = clone_state(template)
        del template

        model_a, history_a, training_a = train_node_model(
            arm="GNN_A_no_pretrain",
            seed=seed,
            initial_state=initial_state,
            pretrained_encoder_state=None,
            samples=train_samples,
            screen=screen,
            relation_count=relation_count,
            positive_weight=positive_weight,
            config=config,
            device=device,
            resources=resources,
            oom_events=oom_events,
        )
        full_a = predict_node_model(
            model=model_a,
            samples=val_samples,
            device=device,
            resources=resources,
            seed=seed,
        )
        no_message_a = predict_node_model(
            model=model_a,
            samples=val_samples,
            device=device,
            resources=resources,
            seed=seed,
            message_mode="none",
        )
        shuffled_a = predict_node_model(
            model=model_a,
            samples=val_samples,
            device=device,
            resources=resources,
            seed=seed,
            shuffle_edge_types=True,
        )
        metrics_a = point_metrics(val_y, full_a)
        calibration_a = ece_10bin(val_y, full_a)
        metrics_a["ece"] = calibration_a["ece"]
        ablations_a = {
            "NoMessage": point_metrics(val_y, no_message_a),
            "edge_type_shuffle": point_metrics(val_y, shuffled_a),
        }
        for name, probability in (
            ("NoMessage", no_message_a),
            ("edge_type_shuffle", shuffled_a),
        ):
            ablations_a[name]["ece"] = ece_10bin(val_y, probability)["ece"]
        checkpoint_a = CKPT_DIR / f"GNN_A_no_pretrain_seed_{seed}.pt"
        torch.save(
            {
                "schema": "e2.gnn_formal.gnn_checkpoint.v1",
                "arm": "GNN_A_no_pretrain",
                "seed": seed,
                "config": asdict(config),
                "feature_names": list(EXPECTED_FEATURE_NAMES),
                "relation_count": relation_count,
                "fit_universe": "train only",
                "evaluation_universe": "val-A only",
                "state_dict": clone_state(model_a),
                "history": history_a,
            },
            assert_output(checkpoint_a),
        )
        predictions["GNN_A_no_pretrain"]["full"][seed] = full_a
        predictions["GNN_A_no_pretrain"]["NoMessage"][seed] = no_message_a
        predictions["GNN_A_no_pretrain"]["edge_type_shuffle"][seed] = shuffled_a
        seed_records["GNN_A_no_pretrain"].append(
            {
                "seed": seed,
                **metrics_a,
                "ece_10bin": calibration_a,
                "ablations": ablations_a,
            }
        )
        training_records["GNN_A_no_pretrain"][str(seed)] = {
            "history": history_a,
            "training": training_a,
        }
        model_artifacts.append(
            {
                "arm": "GNN_A_no_pretrain",
                "seed": seed,
                "path": str(checkpoint_a),
                "sha256": sha256_file(checkpoint_a),
            }
        )
        print(
            f"[GNN_A seed={seed}] valA_AUPRC={metrics_a['auprc']:.8f} "
            f"valA_F1={metrics_a['f1']:.8f} ECE={metrics_a['ece']:.8f}",
            flush=True,
        )
        del model_a
        torch.cuda.empty_cache()
        gc.collect()

        screen.set_seed(seed)
        ssl_template = NodeGNN(screen, relation_count, config)
        ssl_template.load_state_dict(initial_state)
        pretrained_state, ssl_history, ssl_training = train_ssl(
            seed=seed,
            encoder=ssl_template.encoder,
            samples=train_samples,
            screen=screen,
            config=config,
            device=device,
            resources=resources,
            oom_events=oom_events,
        )
        ssl_checkpoint = CKPT_DIR / f"GNN_B_SSL_pretrain_encoder_seed_{seed}.pt"
        torch.save(
            {
                "schema": "e2.gnn_formal.ssl_checkpoint.v1",
                "arm": "GNN_B_SSL_pretrain",
                "seed": seed,
                "config": asdict(config),
                "fit_universe": "4200 train graphs without labels",
                "encoder_state_dict": pretrained_state,
                "history": ssl_history,
            },
            assert_output(ssl_checkpoint),
        )
        del ssl_template
        torch.cuda.empty_cache()
        gc.collect()

        model_b, history_b, training_b = train_node_model(
            arm="GNN_B_SSL_pretrain",
            seed=seed,
            initial_state=initial_state,
            pretrained_encoder_state=pretrained_state,
            samples=train_samples,
            screen=screen,
            relation_count=relation_count,
            positive_weight=positive_weight,
            config=config,
            device=device,
            resources=resources,
            oom_events=oom_events,
        )
        full_b = predict_node_model(
            model=model_b,
            samples=val_samples,
            device=device,
            resources=resources,
            seed=seed,
        )
        no_message_b = predict_node_model(
            model=model_b,
            samples=val_samples,
            device=device,
            resources=resources,
            seed=seed,
            message_mode="none",
        )
        shuffled_b = predict_node_model(
            model=model_b,
            samples=val_samples,
            device=device,
            resources=resources,
            seed=seed,
            shuffle_edge_types=True,
        )
        metrics_b = point_metrics(val_y, full_b)
        calibration_b = ece_10bin(val_y, full_b)
        metrics_b["ece"] = calibration_b["ece"]
        ablations_b = {
            "NoMessage": point_metrics(val_y, no_message_b),
            "edge_type_shuffle": point_metrics(val_y, shuffled_b),
        }
        for name, probability in (
            ("NoMessage", no_message_b),
            ("edge_type_shuffle", shuffled_b),
        ):
            ablations_b[name]["ece"] = ece_10bin(val_y, probability)["ece"]
        checkpoint_b = CKPT_DIR / f"GNN_B_SSL_pretrain_seed_{seed}.pt"
        torch.save(
            {
                "schema": "e2.gnn_formal.gnn_checkpoint.v1",
                "arm": "GNN_B_SSL_pretrain",
                "seed": seed,
                "config": asdict(config),
                "feature_names": list(EXPECTED_FEATURE_NAMES),
                "relation_count": relation_count,
                "fit_universe": "train-only SSL then train-only supervised fine-tune",
                "evaluation_universe": "val-A only",
                "state_dict": clone_state(model_b),
                "history": history_b,
            },
            assert_output(checkpoint_b),
        )
        predictions["GNN_B_SSL_pretrain"]["full"][seed] = full_b
        predictions["GNN_B_SSL_pretrain"]["NoMessage"][seed] = no_message_b
        predictions["GNN_B_SSL_pretrain"]["edge_type_shuffle"][seed] = shuffled_b
        seed_records["GNN_B_SSL_pretrain"].append(
            {
                "seed": seed,
                **metrics_b,
                "ece_10bin": calibration_b,
                "ablations": ablations_b,
            }
        )
        training_records["GNN_B_SSL_pretrain"][str(seed)] = {
            "ssl_history": ssl_history,
            "ssl_training": ssl_training,
            "finetune_history": history_b,
            "finetune_training": training_b,
        }
        model_artifacts.extend(
            [
                {
                    "arm": "GNN_B_SSL_pretrain_encoder",
                    "seed": seed,
                    "path": str(ssl_checkpoint),
                    "sha256": sha256_file(ssl_checkpoint),
                },
                {
                    "arm": "GNN_B_SSL_pretrain",
                    "seed": seed,
                    "path": str(checkpoint_b),
                    "sha256": sha256_file(checkpoint_b),
                },
            ]
        )
        print(
            f"[GNN_B seed={seed}] valA_AUPRC={metrics_b['auprc']:.8f} "
            f"valA_F1={metrics_b['f1']:.8f} ECE={metrics_b['ece']:.8f}",
            flush=True,
        )
        del model_b, pretrained_state, initial_state
        torch.cuda.empty_cache()
        gc.collect()

    return {
        "predictions": predictions,
        "seed_records": seed_records,
        "summaries": {
            arm: metric_summary(rows) for arm, rows in seed_records.items()
        },
        "training": training_records,
        "model_artifacts": model_artifacts,
        "oom_events": oom_events,
        "train_class_balance": {
            "rows": total_count,
            "positive": int(positive_count),
            "negative": int(negative_count),
            "positive_class_weight": positive_weight,
        },
    }


def bootstrap_summary(values: np.ndarray) -> dict[str, Any]:
    values = np.asarray(values, dtype=np.float64)
    if len(values) != BOOTSTRAP_REPLICATES or not np.all(np.isfinite(values)):
        raise RuntimeError("bootstrap distribution incomplete or nonfinite")
    return {
        "replicates": int(len(values)),
        "mean": float(values.mean()),
        "std_population": float(values.std(ddof=0)),
        "standard_error": float(values.std(ddof=1)),
        "ci95_low": float(np.quantile(values, 0.025)),
        "ci95_high": float(np.quantile(values, 0.975)),
    }


def paired_family_bootstrap(
    *,
    w2: Any,
    val_y: np.ndarray,
    family_index: np.ndarray,
    predictions: dict[str, dict[int, np.ndarray]],
    resources: ResourceMonitor,
) -> dict[str, Any]:
    family_count = int(family_index.max()) + 1
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    counts = rng.multinomial(
        family_count,
        np.full(family_count, 1.0 / family_count),
        size=BOOTSTRAP_REPLICATES,
    ).astype(np.int16)
    distributions: dict[str, dict[str, np.ndarray]] = {}
    for arm, by_seed in predictions.items():
        ap_by_seed: list[np.ndarray] = []
        f1_by_seed: list[np.ndarray] = []
        for seed in SEEDS:
            resources.check(f"bootstrap {arm} seed {seed}")
            ap, f1 = w2._cluster_bootstrap_ap_f1(
                val_y,
                by_seed[seed],
                family_index,
                counts,
                THRESHOLD,
            )
            ap_by_seed.append(ap)
            f1_by_seed.append(f1)
            print(
                f"[bootstrap] arm={arm} seed={seed} replicates={BOOTSTRAP_REPLICATES}",
                flush=True,
            )
        distributions[arm] = {
            "auprc": np.mean(np.vstack(ap_by_seed), axis=0),
            "f1": np.mean(np.vstack(f1_by_seed), axis=0),
        }

    comparison_pairs = (
        ("GNN_A_minus_control", "GNN_A_no_pretrain", "control_twohop_GBDT_full"),
        ("GNN_B_minus_control", "GNN_B_SSL_pretrain", "control_twohop_GBDT_full"),
        ("GNN_B_minus_GNN_A_SSL_lift", "GNN_B_SSL_pretrain", "GNN_A_no_pretrain"),
    )
    comparisons: dict[str, Any] = {}
    point_metrics_by_arm = {
        arm: {
            metric: float(
                np.mean(
                    [
                        point_metrics(val_y, by_seed[seed])[metric]
                        for seed in SEEDS
                    ]
                )
            )
            for metric in ("auprc", "f1")
        }
        for arm, by_seed in predictions.items()
    }
    for label, left, right in comparison_pairs:
        comparisons[label] = {
            "left": left,
            "right": right,
            "delta_definition": f"{left} minus {right}",
            "observed_delta_auprc": point_metrics_by_arm[left]["auprc"]
            - point_metrics_by_arm[right]["auprc"],
            "observed_delta_f1": point_metrics_by_arm[left]["f1"]
            - point_metrics_by_arm[right]["f1"],
            "delta_auprc": bootstrap_summary(
                distributions[left]["auprc"] - distributions[right]["auprc"]
            ),
            "delta_f1": bootstrap_summary(
                distributions[left]["f1"] - distributions[right]["f1"]
            ),
        }
    return {
        "unit": "W2-09 geometry family cluster",
        "family_count": family_count,
        "replicates": BOOTSTRAP_REPLICATES,
        "seed": BOOTSTRAP_SEED,
        "pairing": "identical family multiplicities across arms and matched seeds",
        "seed_aggregation": "metric computed per seed inside each replicate then arithmetic mean across seeds",
        "family_draw_count_matrix_sha256": hashlib.sha256(counts.tobytes()).hexdigest(),
        "arm_distributions": {
            arm: {metric: bootstrap_summary(values) for metric, values in metrics.items()}
            for arm, metrics in distributions.items()
        },
        "comparisons": comparisons,
    }


def summarize_arm_predictions(
    *,
    val_y: np.ndarray,
    predictions: dict[str, dict[int, np.ndarray]],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for arm, by_seed in predictions.items():
        rows = []
        for seed in SEEDS:
            metrics = point_metrics(val_y, by_seed[seed])
            calibration = ece_10bin(val_y, by_seed[seed])
            metrics.update({"seed": seed, "ece": calibration["ece"], "ece_10bin": calibration})
            rows.append(metrics)
        output[arm] = {"per_seed": rows, "summary": metric_summary(rows)}
    return output


def summarize_ablations(
    *,
    val_y: np.ndarray,
    gnn_predictions: dict[str, dict[str, dict[int, np.ndarray]]],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for arm, modes in gnn_predictions.items():
        output[arm] = {}
        full = modes["full"]
        for mode in ("NoMessage", "edge_type_shuffle"):
            rows = []
            delta_rows = []
            for seed in SEEDS:
                metrics = point_metrics(val_y, modes[mode][seed])
                calibration = ece_10bin(val_y, modes[mode][seed])
                metrics.update({"seed": seed, "ece": calibration["ece"]})
                full_metrics = point_metrics(val_y, full[seed])
                delta_rows.append(
                    {
                        "seed": seed,
                        "full_minus_ablation_auprc": full_metrics["auprc"] - metrics["auprc"],
                        "full_minus_ablation_f1": full_metrics["f1"] - metrics["f1"],
                    }
                )
                rows.append(metrics)
            output[arm][mode] = {
                "per_seed": rows,
                "summary": metric_summary(rows),
                "full_minus_ablation": {
                    metric: {
                        "mean": float(np.mean([row[metric] for row in delta_rows])),
                        "std_population": float(
                            np.std([row[metric] for row in delta_rows], ddof=0)
                        ),
                    }
                    for metric in (
                        "full_minus_ablation_auprc",
                        "full_minus_ablation_f1",
                    )
                },
            }
    return output


def bottom_20_family_metrics(
    *,
    val_y: np.ndarray,
    family_index: np.ndarray,
    family_ids: Sequence[str],
    predictions: dict[str, dict[int, np.ndarray]],
) -> dict[str, Any]:
    sealed_ids = list(load_json(PREREG_PATH)["frozen"]["w2_01_bottom_20_family_ids"])
    family_position = {value: index for index, value in enumerate(family_ids)}
    missing = [value for value in sealed_ids if value not in family_position]
    if missing:
        raise RuntimeError(f"W2-01 bottom-20 families absent from val-A: {missing}")
    selected_positions = {family_position[value] for value in sealed_ids}
    subset_mask = np.asarray(
        [int(value) in selected_positions for value in family_index], dtype=bool
    )
    output: dict[str, Any] = {
        "source": str(W2_01_RESULTS_PATH),
        "family_ids": sealed_ids,
        "family_count": len(sealed_ids),
        "pooled_row_count": int(np.sum(subset_mask)),
        "arms": {},
    }
    for arm, by_seed in predictions.items():
        rows = []
        for seed in SEEDS:
            metrics = point_metrics(val_y[subset_mask], by_seed[seed][subset_mask])
            calibration = ece_10bin(val_y[subset_mask], by_seed[seed][subset_mask])
            metrics.update({"seed": seed, "ece": calibration["ece"]})
            rows.append(metrics)
        per_family = []
        ensemble = np.mean(np.vstack([by_seed[seed] for seed in SEEDS]), axis=0)
        for family_id in sealed_ids:
            mask = family_index == family_position[family_id]
            per_family.append(
                {
                    "family_id": family_id,
                    "rows": int(np.sum(mask)),
                    "positive": int(np.sum(val_y[mask])),
                    "ensemble_probability_auprc": float(
                        average_precision_score(val_y[mask], ensemble[mask])
                    ),
                }
            )
        output["arms"][arm] = {
            "pooled_per_seed": rows,
            "pooled_summary": metric_summary(rows),
            "per_family_three_seed_mean_probability": per_family,
        }
    return output


def fmt(value: Any, digits: int = 8) -> str:
    if value is None:
        return "NA"
    return f"{float(value):.{digits}f}"


def render_report(result: dict[str, Any]) -> str:
    arms = result["metrics"]["arms"]
    comparisons = result["bootstrap"]["comparisons"]
    lines = [
        "# GNN formal numeric report",
        "",
        f"- prereg.json SHA-256: `{result['dual_seal']['prereg_json_sha256']}`",
        f"- PREREG.csv SHA-256: `{result['dual_seal']['prereg_csv_sha256']}`",
        f"- gnn_formal.py SHA-256: `{result['artifacts']['gnn_formal_py_sha256']}`",
        f"- completed UTC: `{result['completed_at']}`",
        "- Output boundary: numeric measurements and unresolved items only; no adoption/rejection adjudication is emitted.",
        "",
        "## Design",
        "",
        "- Universe: 4,200 CubiCasa train drawings -> 198 W2-09 manifest-listed val-A drawings.",
        "- Graph: frozen GraphConfig, one drawing per graph, segment nodes, 17 numeric allowlisted features, two typed message-passing layers.",
        "- Arms: GNN-A no-pretrain; GNN-B masked+contrastive SSL then identical fine-tune; W2-02 full 2-hop HistGBDT freshly refit train-only.",
        "- Seeds: 17, 29, 43. Threshold: 0.5. Bootstrap: 10,000 paired W2-09 family-cluster resamples, seed 43.",
        "- Calibration measurement: ECE with 10 equal-width bins, without calibration or threshold refitting.",
        "",
        "## Self-test transcript",
        "",
        "```text",
        result["selftest"]["transcript"],
        "```",
        "",
        "## Three-seed val-A measurements",
        "",
        "| Arm | Mean AUPRC | AUPRC population SD | Mean F1 | F1 population SD | Mean ECE-10 | ECE population SD |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in (
        "GNN_A_no_pretrain",
        "GNN_B_SSL_pretrain",
        "control_twohop_GBDT_full",
    ):
        summary = arms[arm]["summary"]
        lines.append(
            f"| {arm} | {fmt(summary['auprc']['mean'])} | {fmt(summary['auprc']['std_population'])} | "
            f"{fmt(summary['f1']['mean'])} | {fmt(summary['f1']['std_population'])} | "
            f"{fmt(summary['ece']['mean'])} | {fmt(summary['ece']['std_population'])} |"
        )
    lines.extend(
        [
            "",
            "| Arm | Seed | AUPRC | F1 | Precision | Recall | ECE-10 | TP | FP | FN | TN |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for arm in (
        "GNN_A_no_pretrain",
        "GNN_B_SSL_pretrain",
        "control_twohop_GBDT_full",
    ):
        for row in arms[arm]["per_seed"]:
            lines.append(
                f"| {arm} | {row['seed']} | {fmt(row['auprc'])} | {fmt(row['f1'])} | "
                f"{fmt(row['precision'])} | {fmt(row['recall'])} | {fmt(row['ece'])} | "
                f"{row['tp']} | {row['fp']} | {row['fn']} | {row['tn']} |"
            )

    lines.extend(
        [
            "",
            "## Paired family-cluster bootstrap deltas",
            "",
            "| Comparison | Observed ΔAUPRC | Bootstrap ΔAUPRC mean | 95% CI | Observed ΔF1 | Bootstrap ΔF1 mean | 95% CI |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in (
        "GNN_A_minus_control",
        "GNN_B_minus_control",
        "GNN_B_minus_GNN_A_SSL_lift",
    ):
        row = comparisons[label]
        ap = row["delta_auprc"]
        f1 = row["delta_f1"]
        lines.append(
            f"| {label} | {fmt(row['observed_delta_auprc'])} | {fmt(ap['mean'])} | "
            f"[{fmt(ap['ci95_low'])}, {fmt(ap['ci95_high'])}] | "
            f"{fmt(row['observed_delta_f1'])} | {fmt(f1['mean'])} | "
            f"[{fmt(f1['ci95_low'])}, {fmt(f1['ci95_high'])}] |"
        )

    lines.extend(
        [
            "",
            "## Inference ablations",
            "",
            "| GNN arm | Ablation | Mean AUPRC | Mean F1 | Mean ECE-10 | Mean full-minus-ablation ΔAUPRC | Mean full-minus-ablation ΔF1 |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for arm in ("GNN_A_no_pretrain", "GNN_B_SSL_pretrain"):
        for mode in ("NoMessage", "edge_type_shuffle"):
            row = result["ablations"][arm][mode]
            summary = row["summary"]
            delta = row["full_minus_ablation"]
            lines.append(
                f"| {arm} | {mode} | {fmt(summary['auprc']['mean'])} | "
                f"{fmt(summary['f1']['mean'])} | {fmt(summary['ece']['mean'])} | "
                f"{fmt(delta['full_minus_ablation_auprc']['mean'])} | "
                f"{fmt(delta['full_minus_ablation_f1']['mean'])} |"
            )

    bottom = result["w2_01_bottom_20"]
    lines.extend(
        [
            "",
            "## W2-01 lowest-20 family slice",
            "",
            f"- Families: {bottom['family_count']}; pooled rows: {bottom['pooled_row_count']}.",
            "",
            "| Arm | Pooled mean AUPRC | AUPRC population SD | Pooled mean F1 | F1 population SD |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for arm in (
        "GNN_A_no_pretrain",
        "GNN_B_SSL_pretrain",
        "control_twohop_GBDT_full",
    ):
        summary = bottom["arms"][arm]["pooled_summary"]
        lines.append(
            f"| {arm} | {fmt(summary['auprc']['mean'])} | {fmt(summary['auprc']['std_population'])} | "
            f"{fmt(summary['f1']['mean'])} | {fmt(summary['f1']['std_population'])} |"
        )
    lines.extend(
        [
            "",
            "| Family | GNN-A ensemble AUPRC | GNN-B ensemble AUPRC | Control ensemble AUPRC |",
            "|---|---:|---:|---:|",
        ]
    )
    per_family = {
        arm: {
            row["family_id"]: row["ensemble_probability_auprc"]
            for row in bottom["arms"][arm]["per_family_three_seed_mean_probability"]
        }
        for arm in bottom["arms"]
    }
    for family_id in bottom["family_ids"]:
        lines.append(
            f"| `{family_id}` | {fmt(per_family['GNN_A_no_pretrain'][family_id])} | "
            f"{fmt(per_family['GNN_B_SSL_pretrain'][family_id])} | "
            f"{fmt(per_family['control_twohop_GBDT_full'][family_id])} |"
        )

    audit = result["graph_audit"]
    usage = result["resource_usage"]
    lines.extend(
        [
            "",
            "## Graph and resource measurements",
            "",
            f"- Graph config SHA-256: `{audit['graph_config_hash']}`",
            f"- Train graph nodes / directed edges: {audit['totals']['train_nodes']:,} / {audit['totals']['train_directed_edges']:,}",
            f"- val-A graph nodes / directed edges: {audit['totals']['val_A_nodes']:,} / {audit['totals']['val_A_directed_edges']:,}",
            f"- Largest drawing nodes / directed edges: {audit['totals']['max_nodes_per_graph']:,} / {audit['totals']['max_directed_edges_per_graph']:,}",
            f"- Train-val-A geometry-family collisions: {audit['train_val_A_geometry_family_collision_count']}",
            f"- val-B drawing reads / test reads / original CAD reads: {audit['read_counters']['val_B_drawing_reads']} / {audit['read_counters']['test_reads']} / {audit['read_counters']['original_CAD_reads']}",
            f"- Formal elapsed: {fmt(usage['formal_elapsed_hours'], 6)} h; cumulative G5 charge: {fmt(usage['cumulative_G5_charge_hours'], 6)} / {fmt(usage['G5_RTX_cap_hours'], 1)} h",
            f"- Peak process-tree RSS: {fmt(usage['peak_process_tree_rss_gib'], 6)} GiB / 48 GiB",
            f"- Peak CUDA allocated / reserved: {fmt(usage.get('peak_cuda_allocated_gib'), 6)} / {fmt(usage.get('peak_cuda_reserved_gib'), 6)} GiB",
            f"- CUDA OOM events: {len(result['oom_events'])}; sampled training graphs: {result['sampled_training_graph_count']}",
            "",
            "## Full ECE-10 measurements",
            "",
            "All per-seed 10-bin counts, mean probabilities, positive rates, and absolute gaps are recorded in `results.json` under `metrics.arms.*.per_seed.*.ece_10bin`.",
            "",
            "## Unresolved",
            "",
        ]
    )
    for item in result["unresolved"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "- Adoption/rejection AND-gate adjudication remains intentionally outside this cell.",
            "",
            "CELL_COMPLETE: gnn_formal",
        ]
    )
    return "\n".join(lines)


def execute() -> dict[str, Any]:
    if RESULTS_PATH.exists() or REPORT_PATH.exists() or CKPT_DIR.exists():
        raise RuntimeError("refusing to modify pre-existing formal results, report, or ckpt directory")
    config = FormalConfig()
    resources = ResourceMonitor()
    resources.start()
    try:
        preflight = verify_inputs()
        builder = load_module(GRAPH_BUILDER_PATH, "gnn_formal_graph_builder_ro")
        screen = load_module(SCREEN_V2_PATH, "gnn_formal_screen_v2_ro")
        w2 = load_module(W2_02_PATH, "gnn_formal_w2_02_ro")
        assert_feature_allowlist(builder.FEATURE_NAMES)
        if builder.GraphConfig().digest() != EXPECTED_GRAPH_CONFIG_HASH:
            raise RuntimeError("graph builder frozen config mismatch")
        manifest = load_json(SPLIT_MANIFEST_PATH)
        selftest = run_selftest(config, preflight, builder, screen, manifest)
        print(selftest["transcript"], flush=True)
        if not selftest["ok"]:
            raise RuntimeError("formal selftest error")

        CKPT_DIR.mkdir(parents=True, exist_ok=False)
        data = build_datasets(builder, screen, w2, manifest, resources)
        resources.check("post graph build")

        baseline_predictions, baseline_records, baseline_artifacts = fit_baseline_control(
            w2=w2,
            train_y=data["train_y"],
            val_y=data["val_y"],
            val_design=data["baseline_val_design"],
            resources=resources,
        )
        gnn = fit_gnn_arms(
            screen=screen,
            relation_count=len(builder.EDGE_TYPES),
            train_samples=data["train_samples"],
            val_samples=data["val_samples"],
            val_y=data["val_y"],
            config=config,
            device=torch.device("cuda:0"),
            resources=resources,
        )
        main_predictions = {
            "GNN_A_no_pretrain": gnn["predictions"]["GNN_A_no_pretrain"]["full"],
            "GNN_B_SSL_pretrain": gnn["predictions"]["GNN_B_SSL_pretrain"]["full"],
            "control_twohop_GBDT_full": baseline_predictions,
        }
        arm_metrics = summarize_arm_predictions(
            val_y=data["val_y"], predictions=main_predictions
        )
        ablations = summarize_ablations(
            val_y=data["val_y"], gnn_predictions=gnn["predictions"]
        )
        bootstrap = paired_family_bootstrap(
            w2=w2,
            val_y=data["val_y"],
            family_index=data["val_family_index"],
            predictions=main_predictions,
            resources=resources,
        )
        bottom_20 = bottom_20_family_metrics(
            val_y=data["val_y"],
            family_index=data["val_family_index"],
            family_ids=data["family_ids"],
            predictions=main_predictions,
        )
        resources.check("final numeric assembly")
        resources.stop()

        sampled_graph_count = sum(
            int(event.get("downgrade") == "deterministic_induced_node_sampling")
            for event in gnn["oom_events"]
        )
        unresolved = []
        if not preflight["amendment1_json_valid"]:
            unresolved.append(
                "The hash-sealed amendment1 source is syntactically malformed JSON at its final object boundary; it was kept read-only and validated by exact SHA-256 plus the sealed G5 RTX total 132h text."
            )
        if not preflight["w2_02_README_present"]:
            unresolved.append(
                "The packet names a W2-02 README, but no README file exists in the cell; the existing REPORT.md, results.json, prereg.json, source, work arrays, and fresh exact refit reproduction were used without inventing a README."
            )
        if sampled_graph_count:
            unresolved.append(
                f"CUDA OOM invoked the sealed deterministic sampled training downgrade for {sampled_graph_count} graph events; exact events are retained in results.json."
            )
        else:
            unresolved.append(
                "The sealed sampled OOM downgrade was not invoked; all train and val-A graphs used full topology."
            )

        artifacts = [*baseline_artifacts, *gnn["model_artifacts"]]
        result = {
            "schema": "e2.gnn_formal.results.v1",
            "completed_at": now_iso(),
            "completion_state": "numeric_measurements_complete",
            "judgment_emitted": False,
            "judgment_policy": "adoption/rejection adjudication is orchestrator-only",
            "dual_seal": preflight["dual_seal"],
            "config": asdict(config),
            "preflight": preflight,
            "selftest": selftest,
            "graph_audit": data["audit"],
            "metrics": {"arms": arm_metrics},
            "bootstrap": bootstrap,
            "ablations": ablations,
            "w2_01_bottom_20": bottom_20,
            "training": {
                "GNN": gnn["training"],
                "GNN_train_class_balance": gnn["train_class_balance"],
                "control_fresh_refit": baseline_records,
            },
            "oom_events": gnn["oom_events"],
            "sampled_training_graph_count": sampled_graph_count,
            "resource_usage": resources.metrics(),
            "execution_scope": {
                "write_root": str(CELL_DIR),
                "repository_files_modified": 0,
                "subagents_used": 0,
                "git_commands_used_after_packet_read": 0,
                "val_B_drawing_reads": data["audit"]["read_counters"]["val_B_drawing_reads"],
                "test_reads": data["audit"]["read_counters"]["test_reads"],
                "original_CAD_reads": data["audit"]["read_counters"]["original_CAD_reads"],
            },
            "models": artifacts,
            "unresolved": unresolved,
            "artifacts": {
                "prereg_json": str(PREREG_PATH),
                "prereg_json_sha256": EXPECTED_PREREG_SHA256,
                "prereg_csv": str(PREREG_CSV_PATH),
                "prereg_csv_sha256": EXPECTED_PREREG_CSV_SHA256,
                "gnn_formal_py": str(Path(__file__).resolve()),
                "gnn_formal_py_sha256": sha256_file(Path(__file__).resolve()),
                "ckpt_dir": str(CKPT_DIR),
                "checkpoint_count": len(artifacts),
            },
        }
        atomic_write_json(RESULTS_PATH, result)
        atomic_write_text(REPORT_PATH, render_report(result))
        print(
            f"[complete] results={RESULTS_PATH} report={REPORT_PATH} checkpoints={len(artifacts)}",
            flush=True,
        )
        return result
    finally:
        resources.stop()


def selftest_only() -> dict[str, Any]:
    config = FormalConfig()
    preflight = verify_inputs()
    builder = load_module(GRAPH_BUILDER_PATH, "gnn_formal_selftest_builder_ro")
    screen = load_module(SCREEN_V2_PATH, "gnn_formal_selftest_screen_ro")
    manifest = load_json(SPLIT_MANIFEST_PATH)
    result = run_selftest(config, preflight, builder, screen, manifest)
    print(result["transcript"], flush=True)
    if not result["ok"]:
        raise RuntimeError("selftest error")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="run guards only; write nothing")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.selftest:
        selftest_only()
    else:
        execute()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        print(
            f"FORMAL_EXECUTION_ERROR {type(error).__name__}: {error}",
            file=sys.stderr,
            flush=True,
        )
        traceback.print_exc()
        raise
