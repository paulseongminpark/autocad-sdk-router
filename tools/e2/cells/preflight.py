#!/usr/bin/env python3
"""W2-00 DGX/RTX preflight benchmark and evidence aggregator.

This program intentionally computes no model-quality score.  It measures only
training throughput, memory, same-seed loss-curve deviation, checkpoint cost,
and the CPU feature-kernel control requested by the cell packet.
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import gc
import hashlib
import json
import math
import os
import platform
import random
import statistics
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np

try:
    import psutil
except Exception:
    psutil = None  # type: ignore[assignment]
else:
    PSUTIL_PROCESS = psutil.Process(os.getpid())

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except Exception as exc:  # CPU control can still run and GPU arms become BLOCKED_ENV.
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]
    TORCH_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
else:
    TORCH_IMPORT_ERROR = None


SCHEMA_RAW = "w2_00_raw_v1"
SCHEMA_FINAL = "w2_00_throughput_v1"
SEED = 20260719
JOBS = ("gnn", "unet", "cpu_feature")

FULL_CONFIG: dict[str, Any] = {
    "seed": SEED,
    "repetitions": 3,
    "gpu": {
        "dtype": "float32",
        "amp": False,
        "tf32": False,
        "cudnn_benchmark": False,
        "cudnn_deterministic": True,
        "warmup_steps": 5,
        "measured_steps": 50,
    },
    "gnn": {
        "nodes": 100_000,
        "edges": 500_000,
        "input_features": 32,
        "hidden_features": 64,
        "output_features": 1,
        "layers": 2,
        "optimizer": "AdamW",
        "learning_rate": 1.0e-3,
        "weight_decay": 1.0e-4,
        "loss": "MSE",
        "sample_definition": "one graph node processed in a full-graph training step",
    },
    "unet": {
        "image_height": 512,
        "image_width": 512,
        "batch_size": 2,
        "input_channels": 1,
        "base_channels": 16,
        "optimizer": "AdamW",
        "learning_rate": 1.0e-3,
        "weight_decay": 1.0e-4,
        "loss": "BCEWithLogits",
        "sample_definition": "one 512x512 synthetic image in a training step",
    },
    "cpu_feature": {
        "rows": 2_000_000,
        "input_columns": 6,
        "output_features": 12,
        "inner_loops": 3,
        "dtype": "float32",
        "sample_definition": "one row transformed by the fixed 12-feature context-like kernel",
    },
    "equivalence_policy": {
        "description": "same code/config/data/initial-weight hashes and median loss curves compared stepwise",
        "absolute_floor": 1.0e-4,
        "relative_floor": 1.0e-3,
        "within_device_noise_multiplier": 5.0,
        "rule": "abs_delta <= absolute_band + relative_band * max(abs(local_loss), abs(dgx_loss)) at every step",
    },
}

SMOKE_CONFIG: dict[str, Any] = {
    **FULL_CONFIG,
    "repetitions": 1,
    "gpu": {**FULL_CONFIG["gpu"], "warmup_steps": 1, "measured_steps": 2},
    "gnn": {**FULL_CONFIG["gnn"], "nodes": 1_000, "edges": 5_000, "hidden_features": 16},
    "unet": {
        **FULL_CONFIG["unet"],
        "image_height": 64,
        "image_width": 64,
        "batch_size": 1,
        "base_channels": 4,
    },
    "cpu_feature": {**FULL_CONFIG["cpu_feature"], "rows": 10_000, "inner_loops": 1},
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_arrays(named_arrays: Iterable[tuple[str, np.ndarray]]) -> str:
    digest = hashlib.sha256()
    for name, array in named_arrays:
        contiguous = np.ascontiguousarray(array)
        header = canonical_json(
            {"name": name, "dtype": contiguous.dtype.str, "shape": list(contiguous.shape)}
        ).encode("utf-8")
        digest.update(len(header).to_bytes(8, "little"))
        digest.update(header)
        digest.update(memoryview(contiguous).cast("B"))
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)


def configure_torch() -> None:
    if torch is None:
        return
    torch.use_deterministic_algorithms(False)
    if hasattr(torch.backends, "cuda") and hasattr(torch.backends.cuda, "matmul"):
        torch.backends.cuda.matmul.allow_tf32 = False
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True


def sync_device(device: "torch.device") -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def current_rss_bytes() -> int:
    if psutil is not None:
        try:
            return int(PSUTIL_PROCESS.memory_info().rss)
        except Exception:
            pass
    if os.name == "nt":
        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        process = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(
            process, ctypes.byref(counters), counters.cb
        )
        return int(counters.WorkingSetSize) if ok else 0
    try:
        statm = Path("/proc/self/statm").read_text(encoding="ascii").split()
        return int(statm[1]) * int(os.sysconf("SC_PAGE_SIZE"))
    except Exception:
        return 0


class PeakRSSSampler:
    def __init__(self, interval_seconds: float = 0.01) -> None:
        self.interval_seconds = interval_seconds
        self.peak_bytes = current_rss_bytes()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _sample(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self.peak_bytes = max(self.peak_bytes, current_rss_bytes())

    def __enter__(self) -> "PeakRSSSampler":
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.peak_bytes = max(self.peak_bytes, current_rss_bytes())
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)


if nn is not None:
    class MeanMessagePassingGNN(nn.Module):
        def __init__(self, input_features: int, hidden_features: int) -> None:
            super().__init__()
            self.self_1 = nn.Linear(input_features, hidden_features)
            self.neigh_1 = nn.Linear(input_features, hidden_features, bias=False)
            self.self_2 = nn.Linear(hidden_features, 1)
            self.neigh_2 = nn.Linear(hidden_features, 1, bias=False)

        @staticmethod
        def aggregate(
            values: "torch.Tensor",
            source: "torch.Tensor",
            destination: "torch.Tensor",
            degree: "torch.Tensor",
        ) -> "torch.Tensor":
            aggregated = torch.zeros(
                (degree.shape[0], values.shape[1]), dtype=values.dtype, device=values.device
            )
            aggregated.index_add_(0, destination, values[source])
            return aggregated / degree.clamp_min(1.0).unsqueeze(1)

        def forward(
            self,
            features: "torch.Tensor",
            source: "torch.Tensor",
            destination: "torch.Tensor",
            degree: "torch.Tensor",
        ) -> "torch.Tensor":
            neighbor_1 = self.aggregate(features, source, destination, degree)
            hidden = F.relu(self.self_1(features) + self.neigh_1(neighbor_1))
            neighbor_2 = self.aggregate(hidden, source, destination, degree)
            return self.self_2(hidden) + self.neigh_2(neighbor_2)


    class DoubleConv(nn.Module):
        def __init__(self, input_channels: int, output_channels: int) -> None:
            super().__init__()
            self.layers = nn.Sequential(
                nn.Conv2d(input_channels, output_channels, kernel_size=3, padding=1),
                nn.ReLU(inplace=False),
                nn.Conv2d(output_channels, output_channels, kernel_size=3, padding=1),
                nn.ReLU(inplace=False),
            )

        def forward(self, value: "torch.Tensor") -> "torch.Tensor":
            return self.layers(value)


    class SmallUNet(nn.Module):
        def __init__(self, base_channels: int) -> None:
            super().__init__()
            base = base_channels
            self.enc_1 = DoubleConv(1, base)
            self.enc_2 = DoubleConv(base, base * 2)
            self.bottleneck = DoubleConv(base * 2, base * 4)
            self.up_2 = nn.ConvTranspose2d(base * 4, base * 2, kernel_size=2, stride=2)
            self.dec_2 = DoubleConv(base * 4, base * 2)
            self.up_1 = nn.ConvTranspose2d(base * 2, base, kernel_size=2, stride=2)
            self.dec_1 = DoubleConv(base * 2, base)
            self.output = nn.Conv2d(base, 1, kernel_size=1)

        def forward(self, value: "torch.Tensor") -> "torch.Tensor":
            enc_1 = self.enc_1(value)
            enc_2 = self.enc_2(F.max_pool2d(enc_1, 2))
            bottleneck = self.bottleneck(F.max_pool2d(enc_2, 2))
            dec_2 = self.dec_2(torch.cat((self.up_2(bottleneck), enc_2), dim=1))
            dec_1 = self.dec_1(torch.cat((self.up_1(dec_2), enc_1), dim=1))
            return self.output(dec_1)


def deterministic_model_init(model: "nn.Module", seed: int) -> None:
    generator = np.random.RandomState(seed)
    with torch.no_grad():
        for name, parameter in model.named_parameters():
            if name.endswith("bias"):
                array = np.zeros(tuple(parameter.shape), dtype=np.float32)
            else:
                fan_in = max(1, int(np.prod(parameter.shape[1:])))
                scale = math.sqrt(2.0 / fan_in)
                array = generator.normal(0.0, scale, size=tuple(parameter.shape)).astype(np.float32)
            parameter.copy_(torch.from_numpy(array).to(device=parameter.device))


def state_dict_sha256(model: "nn.Module") -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        array = tensor.detach().cpu().contiguous().numpy()
        header = canonical_json(
            {"name": name, "dtype": array.dtype.str, "shape": list(array.shape)}
        ).encode("utf-8")
        digest.update(len(header).to_bytes(8, "little"))
        digest.update(header)
        digest.update(memoryview(array).cast("B"))
    return digest.hexdigest()


def build_optimizer(model: "nn.Module", learning_rate: float, weight_decay: float) -> Any:
    return torch.optim.AdamW(
        model.parameters(),
        lr=learning_rate,
        weight_decay=weight_decay,
        foreach=False,
        fused=False,
    )


def make_gnn_data(config: dict[str, Any]) -> tuple[dict[str, np.ndarray], str]:
    generator = np.random.RandomState(SEED + 101)
    nodes = int(config["nodes"])
    edges = int(config["edges"])
    features = generator.standard_normal((nodes, int(config["input_features"]))).astype(np.float32)
    source = generator.randint(0, nodes, size=edges, dtype=np.int64)
    destination = generator.randint(0, nodes, size=edges, dtype=np.int64)
    degree = np.bincount(destination, minlength=nodes).astype(np.float32)
    neighbor_signal = np.zeros(nodes, dtype=np.float32)
    np.add.at(neighbor_signal, destination, features[source, 0])
    neighbor_signal /= np.maximum(degree, 1.0)
    target = np.tanh(
        0.55 * features[:, 0] - 0.30 * features[:, 1] + 0.40 * neighbor_signal
    ).astype(np.float32)[:, None]
    arrays = {
        "features": features,
        "source": source,
        "destination": destination,
        "degree": degree,
        "target": target,
    }
    return arrays, hash_arrays(arrays.items())


def make_unet_data(config: dict[str, Any]) -> tuple[dict[str, np.ndarray], str]:
    generator = np.random.RandomState(SEED + 202)
    batch = int(config["batch_size"])
    height = int(config["image_height"])
    width = int(config["image_width"])
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    images = np.empty((batch, 1, height, width), dtype=np.float32)
    masks = np.zeros((batch, 1, height, width), dtype=np.float32)
    for index in range(batch):
        center_x = width * (0.35 + 0.25 * index / max(1, batch - 1))
        center_y = height * (0.42 + 0.12 * index / max(1, batch - 1))
        radius = min(height, width) * (0.18 + 0.025 * index)
        circle = (xx - center_x) ** 2 + (yy - center_y) ** 2 <= radius**2
        rectangle = (
            (xx >= width * 0.12)
            & (xx <= width * (0.35 + 0.04 * index))
            & (yy >= height * 0.62)
            & (yy <= height * 0.84)
        )
        mask = np.logical_xor(circle, rectangle).astype(np.float32)
        texture = 0.12 * np.sin(xx / 13.0) + 0.10 * np.cos(yy / 17.0)
        noise = generator.normal(0.0, 0.08, size=(height, width)).astype(np.float32)
        images[index, 0] = (0.70 * mask + texture + noise).astype(np.float32)
        masks[index, 0] = mask
    arrays = {"images": images, "masks": masks}
    return arrays, hash_arrays(arrays.items())


def checkpoint_round_trip(
    model: "nn.Module",
    optimizer: Any,
    model_factory: Callable[[], "nn.Module"],
    optimizer_factory: Callable[["nn.Module"], Any],
    device: "torch.device",
    checkpoint_path: Path,
) -> dict[str, Any]:
    sync_device(device)
    trained_hash = state_dict_sha256(model)
    payload = {
        "cell": "w2_00",
        "seed": SEED,
        "model_state": model.state_dict(),
        "optimizer_state": optimizer.state_dict(),
    }
    save_start = time.perf_counter()
    with checkpoint_path.open("wb") as handle:
        torch.save(payload, handle)
        handle.flush()
        os.fsync(handle.fileno())
    sync_device(device)
    save_seconds = time.perf_counter() - save_start
    checkpoint_bytes = checkpoint_path.stat().st_size

    sync_device(device)
    restore_start = time.perf_counter()
    restored_payload = torch.load(checkpoint_path, map_location=device, weights_only=False)
    restored_model = model_factory().to(device)
    restored_optimizer = optimizer_factory(restored_model)
    restored_model.load_state_dict(restored_payload["model_state"])
    restored_optimizer.load_state_dict(restored_payload["optimizer_state"])
    sync_device(device)
    restore_seconds = time.perf_counter() - restore_start
    restored_hash = state_dict_sha256(restored_model)

    checkpoint_path.unlink()
    del restored_payload, restored_model, restored_optimizer, payload
    return {
        "save_seconds": save_seconds,
        "restore_seconds": restore_seconds,
        "checkpoint_bytes": checkpoint_bytes,
        "trained_model_sha256": trained_hash,
        "restored_model_sha256": restored_hash,
        "restore_hash_match": restored_hash == trained_hash,
        "temporary_checkpoint_removed": not checkpoint_path.exists(),
    }


def summarize_gpu_repeats(repeats: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "throughput_median": statistics.median(item["throughput"] for item in repeats),
        "steps_per_second_median": statistics.median(item["steps_per_second"] for item in repeats),
        "step_seconds_median": statistics.median(item["step_seconds"] for item in repeats),
        "peak_memory_allocated_bytes_median": statistics.median(
            item["peak_memory_allocated_bytes"] for item in repeats
        ),
        "peak_memory_allocated_bytes_max": max(
            item["peak_memory_allocated_bytes"] for item in repeats
        ),
        "peak_memory_reserved_bytes_max": max(
            item["peak_memory_reserved_bytes"] for item in repeats
        ),
        "checkpoint_save_seconds_median": statistics.median(
            item["checkpoint"]["save_seconds"] for item in repeats
        ),
        "checkpoint_restore_seconds_median": statistics.median(
            item["checkpoint"]["restore_seconds"] for item in repeats
        ),
        "checkpoint_bytes_median": statistics.median(
            item["checkpoint"]["checkpoint_bytes"] for item in repeats
        ),
    }


def run_gnn(config: dict[str, Any], device: "torch.device", output_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    data, data_hash = make_gnn_data(config["gnn"])
    tensors = {name: torch.from_numpy(value).to(device) for name, value in data.items()}
    del data
    repeats: list[dict[str, Any]] = []
    initial_hashes: list[str] = []
    warmup_steps = int(config["gpu"]["warmup_steps"])
    measured_steps = int(config["gpu"]["measured_steps"])
    nodes = int(config["gnn"]["nodes"])
    model_factory = lambda: MeanMessagePassingGNN(
        int(config["gnn"]["input_features"]), int(config["gnn"]["hidden_features"])
    )

    with PeakRSSSampler() as rss_sampler:
        for repetition in range(int(config["repetitions"])):
            set_seed(SEED)
            model = model_factory().to(device)
            deterministic_model_init(model, SEED + 303)
            initial_hash = state_dict_sha256(model)
            initial_hashes.append(initial_hash)
            optimizer_factory = lambda value: build_optimizer(
                value,
                float(config["gnn"]["learning_rate"]),
                float(config["gnn"]["weight_decay"]),
            )
            optimizer = optimizer_factory(model)

            for _ in range(warmup_steps):
                optimizer.zero_grad(set_to_none=True)
                prediction = model(
                    tensors["features"], tensors["source"], tensors["destination"], tensors["degree"]
                )
                loss = F.mse_loss(prediction, tensors["target"])
                loss.backward()
                optimizer.step()
            sync_device(device)
            if device.type == "cuda":
                torch.cuda.reset_peak_memory_stats(device)

            losses: list["torch.Tensor"] = []
            sync_device(device)
            measured_start = time.perf_counter()
            for _ in range(measured_steps):
                optimizer.zero_grad(set_to_none=True)
                prediction = model(
                    tensors["features"], tensors["source"], tensors["destination"], tensors["degree"]
                )
                loss = F.mse_loss(prediction, tensors["target"])
                loss.backward()
                optimizer.step()
                losses.append(loss.detach())
            sync_device(device)
            elapsed = time.perf_counter() - measured_start
            loss_values = [float(value.cpu()) for value in losses]
            peak_allocated = (
                int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else rss_sampler.peak_bytes
            )
            peak_reserved = (
                int(torch.cuda.max_memory_reserved(device)) if device.type == "cuda" else rss_sampler.peak_bytes
            )

            checkpoint_path = output_dir / f"._w2_00_gnn_{os.getpid()}_{repetition}.pt"
            checkpoint = checkpoint_round_trip(
                model, optimizer, model_factory, optimizer_factory, device, checkpoint_path
            )
            repeats.append(
                {
                    "repetition": repetition + 1,
                    "seed": SEED,
                    "warmup_steps": warmup_steps,
                    "measured_steps": measured_steps,
                    "elapsed_seconds": elapsed,
                    "step_seconds": elapsed / measured_steps,
                    "steps_per_second": measured_steps / elapsed,
                    "throughput": nodes * measured_steps / elapsed,
                    "throughput_unit": "samples/s",
                    "losses": loss_values,
                    "peak_memory_allocated_bytes": peak_allocated,
                    "peak_memory_reserved_bytes": peak_reserved,
                    "checkpoint": checkpoint,
                }
            )
            del model, optimizer, prediction, loss, losses
            gc.collect()
            if device.type == "cuda":
                torch.cuda.empty_cache()

    result = {
        "status": "COMPLETE",
        "job": "gnn",
        "design": config["gnn"],
        "data_sha256": data_hash,
        "initial_model_sha256": initial_hashes[0],
        "initial_model_hash_consistent": len(set(initial_hashes)) == 1,
        "repeats": repeats,
        "summary": summarize_gpu_repeats(repeats),
        "peak_process_rss_bytes": rss_sampler.peak_bytes,
        "job_wall_seconds": time.perf_counter() - started,
    }
    del tensors
    gc.collect()
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return result


def run_unet(config: dict[str, Any], device: "torch.device", output_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    data, data_hash = make_unet_data(config["unet"])
    images = torch.from_numpy(data["images"]).to(device)
    masks = torch.from_numpy(data["masks"]).to(device)
    del data
    repeats: list[dict[str, Any]] = []
    initial_hashes: list[str] = []
    warmup_steps = int(config["gpu"]["warmup_steps"])
    measured_steps = int(config["gpu"]["measured_steps"])
    batch_size = int(config["unet"]["batch_size"])
    model_factory = lambda: SmallUNet(int(config["unet"]["base_channels"]))

    with PeakRSSSampler() as rss_sampler:
        for repetition in range(int(config["repetitions"])):
            set_seed(SEED)
            model = model_factory().to(device)
            deterministic_model_init(model, SEED + 404)
            initial_hash = state_dict_sha256(model)
            initial_hashes.append(initial_hash)
            optimizer_factory = lambda value: build_optimizer(
                value,
                float(config["unet"]["learning_rate"]),
                float(config["unet"]["weight_decay"]),
            )
            optimizer = optimizer_factory(model)

            for _ in range(warmup_steps):
                optimizer.zero_grad(set_to_none=True)
                logits = model(images)
                loss = F.binary_cross_entropy_with_logits(logits, masks)
                loss.backward()
                optimizer.step()
            sync_device(device)
            if device.type == "cuda":
                torch.cuda.reset_peak_memory_stats(device)

            losses: list["torch.Tensor"] = []
            sync_device(device)
            measured_start = time.perf_counter()
            for _ in range(measured_steps):
                optimizer.zero_grad(set_to_none=True)
                logits = model(images)
                loss = F.binary_cross_entropy_with_logits(logits, masks)
                loss.backward()
                optimizer.step()
                losses.append(loss.detach())
            sync_device(device)
            elapsed = time.perf_counter() - measured_start
            loss_values = [float(value.cpu()) for value in losses]
            peak_allocated = (
                int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else rss_sampler.peak_bytes
            )
            peak_reserved = (
                int(torch.cuda.max_memory_reserved(device)) if device.type == "cuda" else rss_sampler.peak_bytes
            )

            checkpoint_path = output_dir / f"._w2_00_unet_{os.getpid()}_{repetition}.pt"
            checkpoint = checkpoint_round_trip(
                model, optimizer, model_factory, optimizer_factory, device, checkpoint_path
            )
            repeats.append(
                {
                    "repetition": repetition + 1,
                    "seed": SEED,
                    "warmup_steps": warmup_steps,
                    "measured_steps": measured_steps,
                    "elapsed_seconds": elapsed,
                    "step_seconds": elapsed / measured_steps,
                    "steps_per_second": measured_steps / elapsed,
                    "throughput": batch_size * measured_steps / elapsed,
                    "throughput_unit": "samples/s",
                    "losses": loss_values,
                    "peak_memory_allocated_bytes": peak_allocated,
                    "peak_memory_reserved_bytes": peak_reserved,
                    "checkpoint": checkpoint,
                }
            )
            del model, optimizer, logits, loss, losses
            gc.collect()
            if device.type == "cuda":
                torch.cuda.empty_cache()

    result = {
        "status": "COMPLETE",
        "job": "unet",
        "design": config["unet"],
        "data_sha256": data_hash,
        "initial_model_sha256": initial_hashes[0],
        "initial_model_hash_consistent": len(set(initial_hashes)) == 1,
        "repeats": repeats,
        "summary": summarize_gpu_repeats(repeats),
        "peak_process_rss_bytes": rss_sampler.peak_bytes,
        "job_wall_seconds": time.perf_counter() - started,
    }
    del images, masks
    gc.collect()
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return result


def make_cpu_data(config: dict[str, Any]) -> tuple[list[np.ndarray], str]:
    generator = np.random.RandomState(SEED + 505)
    rows = int(config["rows"])
    columns = [generator.uniform(-1000.0, 1000.0, size=rows).astype(np.float32) for _ in range(6)]
    return columns, hash_arrays((f"input_{index}", value) for index, value in enumerate(columns))


def cpu_feature_kernel(columns: list[np.ndarray]) -> np.ndarray:
    x1, y1, x2, y2, local_degree, scale = columns
    dx = x2 - x1
    dy = y2 - y1
    absolute_dx = np.abs(dx)
    absolute_dy = np.abs(dy)
    distance = np.sqrt(dx * dx + dy * dy + np.float32(1.0e-6))
    inverse_distance = np.float32(1.0) / (distance + np.float32(1.0e-3))
    output = np.empty((x1.shape[0], 12), dtype=np.float32)
    output[:, 0] = absolute_dx
    output[:, 1] = absolute_dy
    output[:, 2] = distance
    output[:, 3] = dx * inverse_distance
    output[:, 4] = dy * inverse_distance
    output[:, 5] = np.minimum(absolute_dx, absolute_dy) / (
        np.maximum(absolute_dx, absolute_dy) + np.float32(1.0e-3)
    )
    output[:, 6] = np.log1p(np.abs(local_degree))
    output[:, 7] = distance / (np.abs(scale) + np.float32(1.0))
    output[:, 8] = np.sin(dx * np.float32(0.01))
    output[:, 9] = np.cos(dy * np.float32(0.01))
    output[:, 10] = (dx * dy) * np.float32(1.0e-4)
    output[:, 11] = np.tanh((absolute_dx - absolute_dy) * np.float32(0.01))
    return output


def run_cpu_feature(config: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    columns, data_hash = make_cpu_data(config["cpu_feature"])
    rows = int(config["cpu_feature"]["rows"])
    inner_loops = int(config["cpu_feature"]["inner_loops"])
    repeats: list[dict[str, Any]] = []
    with PeakRSSSampler() as rss_sampler:
        warmup_rows = min(rows, 10_000)
        warmup = cpu_feature_kernel([value[:warmup_rows] for value in columns])
        del warmup
        for repetition in range(int(config["repetitions"])):
            gc.collect()
            checksum = 0.0
            measured_start = time.perf_counter()
            for _ in range(inner_loops):
                output = cpu_feature_kernel(columns)
                checksum += float(output[0, 0]) + float(output[-1, -1])
                del output
            elapsed = time.perf_counter() - measured_start
            processed_rows = rows * inner_loops
            repeats.append(
                {
                    "repetition": repetition + 1,
                    "seed": SEED,
                    "rows_per_loop": rows,
                    "inner_loops": inner_loops,
                    "processed_rows": processed_rows,
                    "elapsed_seconds": elapsed,
                    "throughput": processed_rows / elapsed,
                    "throughput_unit": "rows/s",
                    "kernel_passes_per_second": inner_loops / elapsed,
                    "checksum": checksum,
                }
            )
    summary = {
        "throughput_median": statistics.median(item["throughput"] for item in repeats),
        "kernel_passes_per_second_median": statistics.median(
            item["kernel_passes_per_second"] for item in repeats
        ),
        "peak_process_rss_bytes": rss_sampler.peak_bytes,
    }
    return {
        "status": "COMPLETE",
        "job": "cpu_feature",
        "design": config["cpu_feature"],
        "data_sha256": data_hash,
        "repeats": repeats,
        "summary": summary,
        "job_wall_seconds": time.perf_counter() - started,
    }


def runtime_metadata(device_text: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": sys.version,
        "python_executable": sys.executable,
        "numpy": np.__version__,
        "cpu_count_logical": os.cpu_count(),
        "requested_device": device_text,
        "torch_import_error": TORCH_IMPORT_ERROR,
    }
    if torch is not None:
        metadata.update(
            {
                "torch": torch.__version__,
                "torch_cuda": torch.version.cuda,
                "cudnn": torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else None,
                "cuda_available": torch.cuda.is_available(),
            }
        )
        if torch.cuda.is_available():
            properties = torch.cuda.get_device_properties(0)
            metadata["cuda_device"] = {
                "name": properties.name,
                "total_memory_bytes": int(properties.total_memory),
                "major": int(properties.major),
                "minor": int(properties.minor),
                "multiprocessor_count": int(properties.multi_processor_count),
            }
    return metadata


def blocked_job(job: str, code: str, message: str) -> dict[str, Any]:
    return {"status": code, "job": job, "message": message}


def run_suite(args: argparse.Namespace) -> int:
    config = SMOKE_CONFIG if args.profile == "smoke" else FULL_CONFIG
    output_path = Path(args.output).resolve()
    output_dir = output_path.parent
    started_at = utc_now()
    suite_start = time.perf_counter()
    configure_torch()
    result: dict[str, Any] = {
        "schema_version": SCHEMA_RAW,
        "cell": "w2_00",
        "profile": args.profile,
        "role": args.role,
        "started_at_utc": started_at,
        "launch": {"argv": sys.argv, "cwd": str(Path.cwd())},
        "code_sha256": sha256_file(Path(__file__).resolve()),
        "config": config,
        "config_sha256": sha256_bytes(canonical_json(config).encode("utf-8")),
        "runtime": runtime_metadata(args.device),
        "jobs": {},
        "failure_witnesses": [],
    }

    device: Any = None
    gpu_environment_error: str | None = None
    if torch is None:
        gpu_environment_error = f"torch import failed: {TORCH_IMPORT_ERROR}"
    elif args.device == "cuda" and not torch.cuda.is_available():
        gpu_environment_error = "requested CUDA device but torch.cuda.is_available() is false"
    else:
        device = torch.device(args.device)

    for job in JOBS:
        try:
            if job in ("gnn", "unet") and gpu_environment_error is not None:
                result["jobs"][job] = blocked_job(job, "BLOCKED_ENV", gpu_environment_error)
                result["failure_witnesses"].append(
                    {"job": job, "classification": "BLOCKED_ENV", "message": gpu_environment_error}
                )
                continue
            if job == "gnn":
                result["jobs"][job] = run_gnn(config, device, output_dir)
            elif job == "unet":
                result["jobs"][job] = run_unet(config, device, output_dir)
            else:
                result["jobs"][job] = run_cpu_feature(config)
        except Exception as exc:
            witness = {
                "job": job,
                "classification": "FAILED_RUNTIME",
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
            result["jobs"][job] = blocked_job(job, "FAILED_RUNTIME", f"{type(exc).__name__}: {exc}")
            result["failure_witnesses"].append(witness)

    statuses = [value["status"] for value in result["jobs"].values()]
    result["status"] = "COMPLETE" if all(value == "COMPLETE" for value in statuses) else "PARTIAL_BLOCKED"
    result["completed_at_utc"] = utc_now()
    result["suite_wall_seconds"] = time.perf_counter() - suite_start
    write_json(output_path, result)
    print(
        canonical_json(
            {
                "status": result["status"],
                "role": args.role,
                "output": str(output_path),
                "suite_wall_seconds": result["suite_wall_seconds"],
                "failures": len(result["failure_witnesses"]),
            }
        )
    )
    return 0 if result["status"] == "COMPLETE" else 2


def distribution(values: Iterable[float]) -> dict[str, float]:
    array = np.asarray(list(values), dtype=np.float64)
    if array.size == 0:
        raise ValueError("cannot summarize an empty distribution")
    return {
        "count": int(array.size),
        "min": float(np.min(array)),
        "median": float(np.median(array)),
        "mean": float(np.mean(array)),
        "p95": float(np.percentile(array, 95)),
        "p99": float(np.percentile(array, 99)),
        "max": float(np.max(array)),
        "rms": float(np.sqrt(np.mean(array * array))),
    }


def median_loss_curve(job: dict[str, Any]) -> np.ndarray:
    return np.median(
        np.asarray([repeat["losses"] for repeat in job["repeats"]], dtype=np.float64), axis=0
    )


def within_device_spread(job: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    curves = np.asarray([repeat["losses"] for repeat in job["repeats"]], dtype=np.float64)
    spread = np.max(curves, axis=0) - np.min(curves, axis=0)
    denominator = np.maximum(np.max(np.abs(curves), axis=0), 1.0e-12)
    return spread, spread / denominator


def equivalence_result(
    local_job: dict[str, Any], dgx_job: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    local_curve = median_loss_curve(local_job)
    dgx_curve = median_loss_curve(dgx_job)
    if local_curve.shape != dgx_curve.shape:
        return {
            "status": "BLOCKED_SHAPE_MISMATCH",
            "local_steps": int(local_curve.size),
            "dgx_steps": int(dgx_curve.size),
            "pass": False,
        }
    signed = dgx_curve - local_curve
    absolute = np.abs(signed)
    denominator = np.maximum(np.maximum(np.abs(local_curve), np.abs(dgx_curve)), 1.0e-12)
    relative = absolute / denominator
    local_spread, local_relative_spread = within_device_spread(local_job)
    dgx_spread, dgx_relative_spread = within_device_spread(dgx_job)
    within_absolute = np.concatenate((local_spread, dgx_spread))
    within_relative = np.concatenate((local_relative_spread, dgx_relative_spread))
    absolute_band = max(
        float(policy["absolute_floor"]),
        float(policy["within_device_noise_multiplier"]) * float(np.percentile(within_absolute, 99)),
    )
    relative_band = max(
        float(policy["relative_floor"]),
        float(policy["within_device_noise_multiplier"]) * float(np.percentile(within_relative, 99)),
    )
    per_step_limit = absolute_band + relative_band * denominator
    within = absolute <= per_step_limit
    rows = [
        {
            "step": index + 1,
            "local_median_loss": float(local_curve[index]),
            "dgx_median_loss": float(dgx_curve[index]),
            "signed_delta_dgx_minus_local": float(signed[index]),
            "absolute_delta": float(absolute[index]),
            "relative_delta": float(relative[index]),
            "allowed_absolute_delta": float(per_step_limit[index]),
            "within_band": bool(within[index]),
        }
        for index in range(local_curve.size)
    ]
    hash_checks = {
        "data_sha256_equal": local_job.get("data_sha256") == dgx_job.get("data_sha256"),
        "initial_model_sha256_equal": local_job.get("initial_model_sha256")
        == dgx_job.get("initial_model_sha256"),
        "local_initial_model_hash_consistent": bool(local_job.get("initial_model_hash_consistent")),
        "dgx_initial_model_hash_consistent": bool(dgx_job.get("initial_model_hash_consistent")),
    }
    hash_gate = all(hash_checks.values())
    return {
        "status": "COMPLETE",
        "pass": bool(np.all(within)) and hash_gate,
        "hash_gate_pass": hash_gate,
        "hash_checks": hash_checks,
        "band": {
            "absolute": absolute_band,
            "relative": relative_band,
            "absolute_floor": float(policy["absolute_floor"]),
            "relative_floor": float(policy["relative_floor"]),
            "within_device_noise_multiplier": float(policy["within_device_noise_multiplier"]),
            "rule": policy["rule"],
            "classification": "engineering tolerance, not a confidence interval",
        },
        "signed_delta_distribution": distribution(signed),
        "absolute_delta_distribution": distribution(absolute),
        "relative_delta_distribution": distribution(relative),
        "within_device_absolute_spread_distribution": distribution(within_absolute),
        "within_device_relative_spread_distribution": distribution(within_relative),
        "steps_outside_band": [int(index + 1) for index, value in enumerate(within) if not value],
        "per_step": rows,
    }


def completed_job(raw: dict[str, Any], job: str) -> dict[str, Any] | None:
    value = raw.get("jobs", {}).get(job)
    return value if value and value.get("status") == "COMPLETE" else None


def aggregate_results(args: argparse.Namespace) -> int:
    local_path = Path(args.local).resolve()
    dgx_path = Path(args.dgx).resolve()
    output_path = Path(args.output).resolve()
    report_path = Path(args.report).resolve()
    local = json.loads(local_path.read_text(encoding="utf-8"))
    dgx = json.loads(dgx_path.read_text(encoding="utf-8"))
    if local.get("profile") != "full" or dgx.get("profile") != "full":
        raise ValueError("aggregation requires two full-profile raw results")

    throughput_rows: list[dict[str, Any]] = []
    checkpoint_rows: list[dict[str, Any]] = []
    conversions: list[dict[str, Any]] = []
    equivalence: dict[str, Any] = {}
    blockers: list[dict[str, Any]] = []

    for job in JOBS:
        local_job = completed_job(local, job)
        dgx_job = completed_job(dgx, job)
        if local_job is None or dgx_job is None:
            blockers.append(
                {
                    "job": job,
                    "classification": "BLOCKED_MISSING_ARM",
                    "local_status": local.get("jobs", {}).get(job, {}).get("status", "MISSING"),
                    "dgx_status": dgx.get("jobs", {}).get(job, {}).get("status", "MISSING"),
                }
            )
            continue
        local_throughput = float(local_job["summary"]["throughput_median"])
        dgx_throughput = float(dgx_job["summary"]["throughput_median"])
        unit = "rows/s" if job == "cpu_feature" else "samples/s"
        throughput_rows.append(
            {
                "job": job,
                "unit": unit,
                "local_median": local_throughput,
                "dgx_median": dgx_throughput,
                "dgx_over_local_ratio": dgx_throughput / local_throughput,
                "ratio_meaning": "Grace CPU / local CPU" if job == "cpu_feature" else "GB10 / RTX 5070 Ti",
                "local_peak_memory_bytes": (
                    local_job["summary"].get("peak_process_rss_bytes")
                    if job == "cpu_feature"
                    else local_job["summary"].get("peak_memory_allocated_bytes_max")
                ),
                "dgx_peak_memory_bytes": (
                    dgx_job["summary"].get("peak_process_rss_bytes")
                    if job == "cpu_feature"
                    else dgx_job["summary"].get("peak_memory_allocated_bytes_max")
                ),
            }
        )
        if job in ("gnn", "unet"):
            equivalence[job] = equivalence_result(
                local_job, dgx_job, FULL_CONFIG["equivalence_policy"]
            )
            for role, source in (("local_rtx5070ti", local_job), ("dgx_gb10", dgx_job)):
                checkpoint_rows.append(
                    {
                        "job": job,
                        "role": role,
                        "save_seconds_median": source["summary"]["checkpoint_save_seconds_median"],
                        "restore_seconds_median": source["summary"]["checkpoint_restore_seconds_median"],
                        "checkpoint_bytes_median": source["summary"]["checkpoint_bytes_median"],
                        "all_restore_hashes_match": all(
                            repeat["checkpoint"]["restore_hash_match"] for repeat in source["repeats"]
                        ),
                    }
                )
            conversions.append(
                {
                    "job": job,
                    "gb10_steps_per_second": dgx_job["summary"]["steps_per_second_median"],
                    "gb10_steps_per_hour": dgx_job["summary"]["steps_per_second_median"] * 3600.0,
                    "gb10_steps_per_12_hour_cap": dgx_job["summary"]["steps_per_second_median"] * 43_200.0,
                    "step_definition": (
                        "one full 100k-node/500k-edge optimization step"
                        if job == "gnn"
                        else "one optimization step over batch size 2 of 512x512 images"
                    ),
                }
            )
        else:
            conversions.append(
                {
                    "job": job,
                    "dgx_host_kernel_passes_per_second": dgx_job["summary"][
                        "kernel_passes_per_second_median"
                    ],
                    "dgx_host_kernel_passes_per_hour": dgx_job["summary"][
                        "kernel_passes_per_second_median"
                    ]
                    * 3600.0,
                    "dgx_host_rows_per_hour": dgx_throughput * 3600.0,
                    "step_definition": "one complete 2,000,000-row feature-kernel pass",
                }
            )

    gpu_ratios = [
        row["dgx_over_local_ratio"] for row in throughput_rows if row["job"] in ("gnn", "unet")
    ]
    if len(gpu_ratios) == 2:
        routing_triggered = any(value < 2.0 for value in gpu_ratios)
        routing = {
            "status": "COMPLETE",
            "threshold": 2.0,
            "rule": "if any measured throughput workload has GB10/RTX ratio < 2x, downgrade DGX to memory-bound-only queue",
            "per_workload_ratios": {
                row["job"]: row["dgx_over_local_ratio"]
                for row in throughput_rows
                if row["job"] in ("gnn", "unet")
            },
            "geometric_mean_ratio": math.sqrt(gpu_ratios[0] * gpu_ratios[1]),
            "downgrade_triggered": routing_triggered,
            "decision": "DGX_MEMORY_BOUND_ONLY" if routing_triggered else "DGX_THROUGHPUT_ELIGIBLE",
        }
    else:
        routing = {
            "status": "BLOCKED_MISSING_GPU_ARM",
            "threshold": 2.0,
            "downgrade_triggered": None,
            "decision": "BLOCKED",
        }

    equivalence_complete = len(equivalence) == 2
    promotion_allowed = equivalence_complete and all(value.get("pass") for value in equivalence.values())
    failure_witnesses = list(local.get("failure_witnesses", [])) + list(
        dgx.get("failure_witnesses", [])
    )
    failure_witnesses.extend(blockers)
    status = "COMPLETE" if not blockers and local.get("status") == "COMPLETE" and dgx.get("status") == "COMPLETE" else "COMPLETE_WITH_BLOCKED_ARMS"

    result: dict[str, Any] = {
        "schema_version": SCHEMA_FINAL,
        "cell": "w2_00",
        "status": status,
        "generated_at_utc": utc_now(),
        "scope": {
            "scores_computed": False,
            "synthetic_data_only": True,
            "source_labels_accessed": False,
            "repository_modified": False,
            "vllm_started": False,
        },
        "contract": {
            "packet_path": args.packet_path,
            "packet_sha256": args.packet_sha256,
            "routing_threshold": 2.0,
            "caps_hours": {"dgx_gb10": 12.0, "local_rtx": 12.0, "cpu": 12.0},
        },
        "benchmark_design": FULL_CONFIG,
        "provenance": {
            "preflight_code_sha256": local.get("code_sha256"),
            "local_and_dgx_code_sha256_equal": local.get("code_sha256") == dgx.get("code_sha256"),
            "config_sha256": local.get("config_sha256"),
            "local_and_dgx_config_sha256_equal": local.get("config_sha256")
            == dgx.get("config_sha256"),
            "remote_script_sha256": args.remote_script_sha256,
            "dgx_image": args.image,
            "dgx_image_id": args.image_id,
            "dgx_image_digest": args.image_digest,
            "container_name": args.container_name,
            "remote_work_dir": args.remote_dir,
            "local_runtime": local.get("runtime"),
            "dgx_runtime": dgx.get("runtime"),
            "launch_commands": {
                "local_suite": args.local_command,
                "remote_transport": args.remote_transport_command,
                "dgx_container_suite": args.dgx_command,
                "aggregate": " ".join(sys.argv),
            },
            "raw_input_sha256": {
                "local": sha256_file(local_path),
                "dgx": sha256_file(dgx_path),
            },
        },
        "throughput_table": throughput_rows,
        "equivalence": {
            "policy": FULL_CONFIG["equivalence_policy"],
            "jobs": equivalence,
            "cross_device_promotion_allowed": promotion_allowed,
            "decision": "ALLOWED_FOR_MATCHING_HASHED_CONFIG" if promotion_allowed else "PROHIBITED",
        },
        "checkpoint_costs": checkpoint_rows,
        "gb10_hour_conversion": conversions,
        "routing_decision": routing,
        "resource_accounting": {
            "local_suite_wall_seconds": local.get("suite_wall_seconds"),
            "dgx_suite_wall_seconds": dgx.get("suite_wall_seconds"),
            "local_rtx_charged_seconds": sum(
                completed_job(local, job).get("job_wall_seconds", 0.0)
                if completed_job(local, job)
                else 0.0
                for job in ("gnn", "unet")
            ),
            "dgx_gb10_charged_seconds": sum(
                completed_job(dgx, job).get("job_wall_seconds", 0.0)
                if completed_job(dgx, job)
                else 0.0
                for job in ("gnn", "unet")
            ),
            "cpu_charged_seconds": sum(
                completed_job(source, "cpu_feature").get("job_wall_seconds", 0.0)
                if completed_job(source, "cpu_feature")
                else 0.0
                for source in (local, dgx)
            ),
        },
        "failure_witnesses": failure_witnesses,
        "unresolved": [
            "Measurements cover fixed synthetic FP32 micro-workloads, not full production models or datasets.",
            "The empirical equivalence band has three timing repetitions and 50 steps per GPU job; it is an engineering tolerance, not a confidence interval.",
            "Storage-specific checkpoint latency includes each host filesystem and is not isolated from filesystem cache effects.",
            "NVIDIA PyTorch 25.04 emits a GB10 support warning even though the CUDA allocation and full suite complete.",
        ],
        "raw": {"local": local, "dgx": dgx},
    }
    write_json(output_path, result)
    throughput_hash = sha256_file(output_path)
    render_report(report_path, result, throughput_hash)
    print(
        canonical_json(
            {
                "status": result["status"],
                "output": str(output_path),
                "report": str(report_path),
                "throughput_sha256": throughput_hash,
            }
        )
    )
    return 0 if result["status"] == "COMPLETE" else 2


def number(value: Any, digits: int = 6) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, int):
        return str(value)
    return f"{float(value):.{digits}g}"


def mib(value: Any) -> str:
    return "N/A" if value is None else f"{float(value) / (1024.0 * 1024.0):.3f}"


def render_report(path: Path, result: dict[str, Any], throughput_hash: str) -> None:
    lines: list[str] = []
    lines.extend(
        [
            "# W2-00 DGX-PREFLIGHT report",
            "",
            f"- Status: `{result['status']}`",
            f"- Generated (UTC): `{result['generated_at_utc']}`",
            "- Scope: synthetic data only; no labels, CAD, CubiCasa data, test set, or performance score was accessed or computed.",
            f"- Routing decision: `{result['routing_decision']['decision']}`",
            f"- Cross-device promotion: `{result['equivalence']['decision']}`",
            "",
            "## Fixed design",
            "",
            "- GNN: 100,000 nodes, 500,000 directed edges, 32 input features, 64 hidden features, two mean-message-passing layers, full-graph FP32 MSE training.",
            "- U-Net: batch 2, 1x512x512 synthetic images, base width 16, two down/up levels, FP32 BCE-with-logits training.",
            "- GPU timing: five warm-up steps followed by 50 measured optimization steps; three repetitions; median is the headline value.",
            "- CPU control: 2,000,000 fixed rows, six inputs to 12 context-like features, three kernel passes per repetition, three repetitions.",
            "- TF32 and AMP are disabled; cuDNN autotuning is disabled; same code/config/data/initial-weight hashes are required.",
            "",
            "## Throughput and peak memory",
            "",
            "| Job | Local median | DGX median | Unit | DGX/local ratio | Local peak MiB | DGX peak MiB |",
            "|---|---:|---:|---|---:|---:|---:|",
        ]
    )
    for row in result["throughput_table"]:
        lines.append(
            f"| {row['job']} | {number(row['local_median'])} | {number(row['dgx_median'])} | {row['unit']} | {number(row['dgx_over_local_ratio'])} | {mib(row['local_peak_memory_bytes'])} | {mib(row['dgx_peak_memory_bytes'])} |"
        )

    lines.extend(["", "### All repetition measurements", ""])
    for role in ("local", "dgx"):
        raw = result["raw"][role]
        lines.extend(
            [
                f"#### {role} — `{raw['role']}`",
                "",
                "| Job | Rep | Elapsed s | Throughput | Unit | Steps/s or passes/s | Peak allocated MiB | Peak reserved MiB | Checkpoint save s | restore s | bytes |",
                "|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for job in JOBS:
            value = raw["jobs"].get(job, {})
            if value.get("status") != "COMPLETE":
                lines.append(f"| {job} | - | BLOCKED | - | - | - | - | - | - | - | - |")
                continue
            for repeat in value["repeats"]:
                if job == "cpu_feature":
                    lines.append(
                        f"| {job} | {repeat['repetition']} | {number(repeat['elapsed_seconds'])} | {number(repeat['throughput'])} | rows/s | {number(repeat['kernel_passes_per_second'])} | {mib(value['summary']['peak_process_rss_bytes'])} RSS | N/A | N/A | N/A | N/A |"
                    )
                else:
                    checkpoint = repeat["checkpoint"]
                    lines.append(
                        f"| {job} | {repeat['repetition']} | {number(repeat['elapsed_seconds'])} | {number(repeat['throughput'])} | samples/s | {number(repeat['steps_per_second'])} | {mib(repeat['peak_memory_allocated_bytes'])} | {mib(repeat['peak_memory_reserved_bytes'])} | {number(checkpoint['save_seconds'])} | {number(checkpoint['restore_seconds'])} | {checkpoint['checkpoint_bytes']} |"
                    )
        lines.append("")

    lines.extend(
        [
            "## Routing rule result",
            "",
            f"The sealed threshold is `{number(result['routing_decision']['threshold'])}x`. The rule is evaluated per measured GPU workload; any ratio below the threshold triggers the downgrade.",
        ]
    )
    if result["routing_decision"]["status"] == "COMPLETE":
        lines.append(
            f"GNN ratio = `{number(result['routing_decision']['per_workload_ratios']['gnn'])}x`; U-Net ratio = `{number(result['routing_decision']['per_workload_ratios']['unet'])}x`; geometric mean = `{number(result['routing_decision']['geometric_mean_ratio'])}x`; downgrade triggered = `{str(result['routing_decision']['downgrade_triggered']).lower()}`."
        )
    else:
        lines.append("Routing is BLOCKED because one or more GPU arms are missing.")

    lines.extend(["", "## Same-seed equivalence bands", ""])
    policy = result["equivalence"]["policy"]
    lines.append(
        f"Band rule: `{policy['rule']}`. Floors are absolute `{number(policy['absolute_floor'])}` and relative `{number(policy['relative_floor'])}`; the larger of each floor and `{number(policy['within_device_noise_multiplier'])}x` the within-device p99 spread is sealed. This is an engineering tolerance, not a confidence interval."
    )
    lines.append("")
    lines.append("| Job | Pass | Abs band | Rel band | Abs median | Abs p95 | Abs max | Rel median | Rel p95 | Rel max | Steps outside |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for job, value in result["equivalence"]["jobs"].items():
        lines.append(
            f"| {job} | {value['pass']} | {number(value['band']['absolute'])} | {number(value['band']['relative'])} | {number(value['absolute_delta_distribution']['median'])} | {number(value['absolute_delta_distribution']['p95'])} | {number(value['absolute_delta_distribution']['max'])} | {number(value['relative_delta_distribution']['median'])} | {number(value['relative_delta_distribution']['p95'])} | {number(value['relative_delta_distribution']['max'])} | {','.join(map(str, value['steps_outside_band'])) or 'none'} |"
        )
    for job, value in result["equivalence"]["jobs"].items():
        lines.extend(
            [
                "",
                f"### {job} median loss curve and every stepwise deviation",
                "",
                "| Step | Local loss | DGX loss | Signed delta | Abs delta | Rel delta | Allowed abs delta | In band |",
                "|---:|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        for row in value["per_step"]:
            lines.append(
                f"| {row['step']} | {number(row['local_median_loss'], 9)} | {number(row['dgx_median_loss'], 9)} | {number(row['signed_delta_dgx_minus_local'], 9)} | {number(row['absolute_delta'], 9)} | {number(row['relative_delta'], 9)} | {number(row['allowed_absolute_delta'], 9)} | {row['within_band']} |"
            )

    lines.extend(
        [
            "",
            "## Checkpoint cost",
            "",
            "Checkpoint time includes serialization, close, and `fsync`; restore includes deserialize, model/optimizer load, and device synchronization.",
            "",
            "| Job | Device | Median save s | Median restore s | Median bytes | All restored hashes match |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for row in result["checkpoint_costs"]:
        lines.append(
            f"| {row['job']} | {row['role']} | {number(row['save_seconds_median'])} | {number(row['restore_seconds_median'])} | {number(row['checkpoint_bytes_median'])} | {row['all_restore_hashes_match']} |"
        )

    lines.extend(
        [
            "",
            "## GB10-hour conversion",
            "",
            "| Job | Steps/s or passes/s | Per hour | Per 12h cap or rows/hour | Definition |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for row in result["gb10_hour_conversion"]:
        if row["job"] == "cpu_feature":
            lines.append(
                f"| cpu_feature | {number(row['dgx_host_kernel_passes_per_second'])} passes/s | {number(row['dgx_host_kernel_passes_per_hour'])} passes/h | {number(row['dgx_host_rows_per_hour'])} rows/h | {row['step_definition']} |"
            )
        else:
            lines.append(
                f"| {row['job']} | {number(row['gb10_steps_per_second'])} steps/s | {number(row['gb10_steps_per_hour'])} steps/h | {number(row['gb10_steps_per_12_hour_cap'])} steps/12h | {row['step_definition']} |"
            )

    accounting = result["resource_accounting"]
    lines.extend(
        [
            "",
            "## Budget accounting",
            "",
            f"- Local suite wall: `{number(accounting['local_suite_wall_seconds'])}` s; charged RTX job wall: `{number(accounting['local_rtx_charged_seconds'])}` s (`{number(accounting['local_rtx_charged_seconds'] / 3600.0)}` h / 12 h cap).",
            f"- DGX suite wall: `{number(accounting['dgx_suite_wall_seconds'])}` s; charged GB10 job wall: `{number(accounting['dgx_gb10_charged_seconds'])}` s (`{number(accounting['dgx_gb10_charged_seconds'] / 3600.0)}` h / 12 h cap).",
            f"- Combined local+Grace CPU-control wall: `{number(accounting['cpu_charged_seconds'])}` s (`{number(accounting['cpu_charged_seconds'] / 3600.0)}` h / 12 h cap).",
            "",
            "## Provenance and launch witnesses",
            "",
            f"- Packet SHA-256: `{result['contract']['packet_sha256']}`",
            f"- `preflight.py` SHA-256: `{result['provenance']['preflight_code_sha256']}`; same on local/DGX: `{result['provenance']['local_and_dgx_code_sha256_equal']}`",
            f"- Config SHA-256: `{result['provenance']['config_sha256']}`; same on local/DGX: `{result['provenance']['local_and_dgx_config_sha256_equal']}`",
            f"- Remote script SHA-256: `{result['provenance']['remote_script_sha256']}`",
            f"- DGX image: `{result['provenance']['dgx_image']}`",
            f"- DGX image ID: `{result['provenance']['dgx_image_id']}`",
            f"- DGX image digest: `{result['provenance']['dgx_image_digest']}`",
            f"- Container: `{result['provenance']['container_name']}` (benchmark-owned, retained stopped; pre-existing vLLM containers untouched)",
            f"- Remote work directory: `{result['provenance']['remote_work_dir']}`",
            f"- Local runtime: `{canonical_json(result['provenance']['local_runtime'])}`",
            f"- DGX runtime: `{canonical_json(result['provenance']['dgx_runtime'])}`",
            f"- Local launch: `{result['provenance']['launch_commands']['local_suite']}`",
            f"- Remote transport: `{result['provenance']['launch_commands']['remote_transport']}`",
            f"- DGX container launch: `{result['provenance']['launch_commands']['dgx_container_suite']}`",
            f"- Aggregate launch: `{result['provenance']['launch_commands']['aggregate']}`",
            f"- `throughput.json` SHA-256 at report render: `{throughput_hash}`",
            "",
            "## BLOCKED / failure witnesses",
            "",
        ]
    )
    if result["failure_witnesses"]:
        for witness in result["failure_witnesses"]:
            lines.append(f"- `{canonical_json(witness)}`")
    else:
        lines.append("- None. All six requested machine/job arms completed.")

    lines.extend(["", "## Unresolved / interpretation limits", ""])
    for item in result["unresolved"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "All per-repetition raw loss values, memory values, checkpoint witnesses, hashes, runtime metadata, and failure fields are preserved in `throughput.json` under `raw`.",
            "",
            "CELL_COMPLETE: w2_00",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="run all three benchmark jobs on one machine")
    run_parser.add_argument("--role", required=True)
    run_parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    run_parser.add_argument("--profile", choices=("full", "smoke"), default="full")
    run_parser.add_argument("--output", required=True)
    run_parser.set_defaults(function=run_suite)

    aggregate_parser = subparsers.add_parser("aggregate", help="combine local and DGX raw results")
    aggregate_parser.add_argument("--local", required=True)
    aggregate_parser.add_argument("--dgx", required=True)
    aggregate_parser.add_argument("--output", required=True)
    aggregate_parser.add_argument("--report", required=True)
    aggregate_parser.add_argument("--packet-path", required=True)
    aggregate_parser.add_argument("--packet-sha256", required=True)
    aggregate_parser.add_argument("--remote-script-sha256", required=True)
    aggregate_parser.add_argument("--image", required=True)
    aggregate_parser.add_argument("--image-id", required=True)
    aggregate_parser.add_argument("--image-digest", required=True)
    aggregate_parser.add_argument("--container-name", required=True)
    aggregate_parser.add_argument("--remote-dir", required=True)
    aggregate_parser.add_argument("--local-command", required=True)
    aggregate_parser.add_argument("--remote-transport-command", required=True)
    aggregate_parser.add_argument("--dgx-command", required=True)
    aggregate_parser.set_defaults(function=aggregate_results)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.function(args))


if __name__ == "__main__":
    raise SystemExit(main())
