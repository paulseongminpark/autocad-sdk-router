#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic typed SEG-IR graph builder and Cell E1 audit runner.

The builder keeps source handles only as traceability sidecars.  Handles, input
order, filenames, block/layer names, and text are never node features or
top-k tie-breaks.  Spatial caps are ordered by geometry metrics followed by a
geometry-only SHA-256 hash.

Examples:
  python graph_builder.py --selftest
  python graph_builder.py build --segir drawing.segir.json --out graph.npz
  python graph_builder.py run-cell
"""
from __future__ import annotations

import argparse
import ctypes
import gc
import hashlib
import heapq
import importlib.util
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import numpy as np

try:
    import ezdxf
except ImportError:  # pragma: no cover - surfaced by the DXF audit path
    ezdxf = None


SCHEMA = "ariadne.e2.graph_ir.v1"
RECALL_SCHEMA = "ariadne.e2.graph_recall_audit.v1"
ENVELOPE_SCHEMA = "ariadne.e2.graph_envelope_audit.v1"
DEFAULT_REPO = Path(r"D:\dev\99_tools\autocad-sdk-router")
DEFAULT_CELL = Path(r"D:\runs\e2_program\cells\graph_builder")
RAM_BAND_BYTES = 48 * 1024**3

EDGE_TYPES = (
    "parallel_band",
    "intersection_junction",
    "proximity",
    "collinearity",
    "containment",
    "instancing",
)
EDGE_TYPE_ID = {name: i for i, name in enumerate(EDGE_TYPES)}

FEATURE_NAMES = (
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
    "handle", "sid", "sequence", "order", "filename", "file_name",
    "block_name", "layer", "text", "name", "family_id",
)


@dataclass(frozen=True)
class GraphConfig:
    """Frozen geometry-only graph configuration.

    Normalized distances use a 1000 mm reference for explicit millimetre input,
    otherwise the drawing's median non-degenerate segment length.
    """

    angle_parallel_deg: float = 6.0
    angle_collinear_deg: float = 2.0
    junction_snap_norm: float = 0.01
    proximity_radius_norm: float = 0.50
    parallel_offset_norm: float = 0.50
    parallel_min_overlap: float = 0.20
    # A continuation can change wall thickness at the break; 0.30 preserves the
    # shared axis across the resulting boundary-line offset (gen2 w05/w06,
    # w07/w08) while the angle/gap tests and top-k still bound the relation.
    collinear_offset_norm: float = 0.30
    collinear_gap_norm: float = 2.00
    topk_parallel: int = 12
    topk_proximity: int = 12
    topk_collinear: int = 8
    max_candidate_scan: int = 96
    # Hard pre-sort guard for pathological coincident buckets.  Relation top-k
    # remains 12/12/8; this guard is geometry-ordered and every truncation is
    # counted.  A 4096 rehearsal bound made the 412k-node staged maximum spend
    # over one hour sorting dense pools without reaching an artifact commit.
    max_candidate_collect: int = 256
    max_index_cells_per_segment: int = 512
    max_core_nodes_per_shard: int = 16384
    containment_entity_cap: int = 16
    geometry_round_digits: int = 9

    def canonical(self) -> dict[str, Any]:
        return asdict(self)

    def digest(self) -> str:
        payload = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_json_ready(v) for v in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(
        json.dumps(_json_ready(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temp, path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _quantiles(values: Sequence[float] | np.ndarray) -> dict[str, float | None]:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {key: None for key in ("min", "p50", "p90", "p95", "p99", "max")}
    qs = np.quantile(arr, [0.0, 0.5, 0.9, 0.95, 0.99, 1.0], method="linear")
    return {
        "min": float(qs[0]), "p50": float(qs[1]), "p90": float(qs[2]),
        "p95": float(qs[3]), "p99": float(qs[4]), "max": float(qs[5]),
    }


# ---------------------------------------------------------------------------
# Process working-set sampling (stdlib only, including NumPy allocations)
# ---------------------------------------------------------------------------


def current_working_set_bytes() -> int | None:
    if os.name == "nt":
        try:
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel32.GetCurrentProcess.argtypes = []
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            counters = PMC()
            counters.cb = ctypes.sizeof(counters)
            process = kernel32.GetCurrentProcess()
            ok = psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb)
            return int(counters.WorkingSetSize) if ok else None
        except Exception:
            return None
    try:  # pragma: no cover - Windows is the packet execution surface
        import resource

        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return value * (1024 if sys.platform != "darwin" else 1)
    except Exception:
        return None


class PeakMemorySampler:
    def __init__(self, interval: float = 0.02):
        self.interval = interval
        self.start_bytes = current_working_set_bytes()
        self.peak_bytes = self.start_bytes
        self.end_bytes = self.start_bytes
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            value = current_working_set_bytes()
            if value is not None and (self.peak_bytes is None or value > self.peak_bytes):
                self.peak_bytes = value

    def __enter__(self) -> "PeakMemorySampler":
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)
        self.end_bytes = current_working_set_bytes()
        if self.end_bytes is not None and (
            self.peak_bytes is None or self.end_bytes > self.peak_bytes
        ):
            self.peak_bytes = self.end_bytes

    def numbers(self) -> dict[str, int | None]:
        delta = None
        if self.start_bytes is not None and self.peak_bytes is not None:
            delta = max(0, self.peak_bytes - self.start_bytes)
        return {
            "working_set_start_bytes": self.start_bytes,
            "working_set_peak_bytes": self.peak_bytes,
            "working_set_end_bytes": self.end_bytes,
            "working_set_peak_delta_bytes": delta,
        }


# ---------------------------------------------------------------------------
# DXF -> SEG-IR conversion with occurrence paths and fail-closed diagnostics
# ---------------------------------------------------------------------------


Affine = tuple[float, float, float, float, float, float]


def _apply_affine(matrix: Affine | None, x: float, y: float) -> list[float]:
    if matrix is None:
        return [float(x), float(y)]
    a, b, tx, c, d, ty = matrix
    return [float(a * x + b * y + tx), float(c * x + d * y + ty)]


def _compose_affine(parent: Affine, child: Affine) -> Affine:
    pa, pb, ptx, pc, pd, pty = parent
    ca, cb, ctx, cc, cd, cty = child
    return (
        pa * ca + pb * cc,
        pa * cb + pb * cd,
        pa * ctx + pb * cty + ptx,
        pc * ca + pd * cc,
        pc * cb + pd * cd,
        pc * ctx + pd * cty + pty,
    )


def _block_base(block) -> tuple[float, float]:
    try:
        point = block.block.dxf.base_point
        return float(point[0]), float(point[1])
    except Exception:
        return 0.0, 0.0


def _insert_affine(insert, base: tuple[float, float]) -> Affine:
    point = insert.dxf.insert
    ix, iy = float(point[0]), float(point[1])
    rotation = math.radians(float(insert.dxf.get("rotation", 0.0) or 0.0))
    sx = float(insert.dxf.get("xscale", 1.0) or 1.0)
    sy = float(insert.dxf.get("yscale", 1.0) or 1.0)
    bx, by = base
    co, si = math.cos(rotation), math.sin(rotation)
    a, b, c, d = co * sx, -si * sy, si * sx, co * sy
    return (a, b, ix - a * bx - b * by, c, d, iy - c * bx - d * by)


def _entity_segments(entity, transform: Affine | None, insert_path: tuple[str, ...]) -> list[dict]:
    """SEG-IR subset matching the packet's line-segment node contract."""
    try:
        kind = entity.dxftype()
        handle = getattr(entity.dxf, "handle", None)
        layer = getattr(entity.dxf, "layer", "0")
    except Exception:
        return []

    def seg(a, b, geometry_kind: str, **extra) -> dict:
        item = {
            "handle": None if handle is None else str(handle),
            "pts": [_apply_affine(transform, float(a[0]), float(a[1])),
                    _apply_affine(transform, float(b[0]), float(b[1]))],
            "layer": str(layer),
            "kind": geometry_kind,
            "source": "native",
            "label": "unknown",
        }
        if insert_path:
            item["insert_path"] = list(insert_path)
        item.update(extra)
        return item

    try:
        if kind == "LINE":
            return [seg(entity.dxf.start, entity.dxf.end, "line")]
        if kind in ("LWPOLYLINE", "POLYLINE"):
            if kind == "LWPOLYLINE":
                points = [(float(p[0]), float(p[1])) for p in entity.get_points("xy")]
                closed = bool(entity.closed)
            else:
                points = [
                    (float(v.dxf.location[0]), float(v.dxf.location[1]))
                    for v in entity.vertices
                ]
                closed = bool(entity.is_closed)
            if closed and len(points) >= 3:
                points = points + [points[0]]
            return [seg(points[i], points[i + 1], "poly-edge", closed=closed)
                    for i in range(max(0, len(points) - 1))]
        if kind == "ARC":
            center = entity.dxf.center
            radius = float(entity.dxf.radius)
            start_deg = float(entity.dxf.start_angle)
            end_deg = float(entity.dxf.end_angle)
            start = (
                float(center[0]) + radius * math.cos(math.radians(start_deg)),
                float(center[1]) + radius * math.sin(math.radians(start_deg)),
            )
            end = (
                float(center[0]) + radius * math.cos(math.radians(end_deg)),
                float(center[1]) + radius * math.sin(math.radians(end_deg)),
            )
            sweep = (end_deg - start_deg) % 360.0
            sagitta = radius * (1.0 - math.cos(math.radians(sweep) / 2.0))
            if transform is not None:
                a, b, _, c, d, _ = transform
                sagitta *= math.sqrt(abs(a * d - b * c))
            return [seg(start, end, "arc-chord", sagitta=float(sagitta))]
        if kind == "MLINE":
            out: list[dict] = []
            for virtual in entity.virtual_entities():
                if virtual.dxftype() in ("LINE", "ARC"):
                    pieces = _entity_segments(virtual, transform, insert_path)
                    for piece in pieces:
                        piece["handle"] = None if handle is None else str(handle)
                    out.extend(pieces)
            return out
    except Exception:
        return []
    return []


def _units_from_doc(doc) -> str:
    try:
        return "mm" if int(doc.header.get("$INSUNITS", 0)) == 4 else "unknown"
    except Exception:
        return "unknown"


def _walk_insert(
    doc,
    insert,
    parent: Affine | None,
    path: tuple[str, ...],
    stack: frozenset[str],
    depth: int,
    out: list[dict],
    info: Counter,
) -> None:
    if depth > 16:
        info["max_depth_hit"] += 1
        return
    name = str(insert.dxf.name)
    if name in stack:
        info["cycle_skipped"] += 1
        return
    block = doc.blocks.get(name)
    if block is None:
        info["missing_block"] += 1
        return
    local = _insert_affine(insert, _block_base(block))
    transform = local if parent is None else _compose_affine(parent, local)
    insert_handle = getattr(insert.dxf, "handle", None)
    if insert_handle is None:
        token_bytes = struct.pack("<6d", *transform)
        insert_token = "geom:" + hashlib.sha256(token_bytes).hexdigest()[:24]
    else:
        insert_token = str(insert_handle)
    child_path = path + (insert_token,)
    info["inserts_walked"] += 1
    for entity in block:
        if entity.dxftype() == "INSERT":
            _walk_insert(
                doc, entity, transform, child_path, stack | {name}, depth + 1, out, info
            )
        else:
            pieces = _entity_segments(entity, transform, child_path)
            out.extend(pieces)
            info["nested_segments"] += len(pieces)


def segir_from_dxf_modelspace(path: Path) -> dict[str, Any]:
    if ezdxf is None:
        raise RuntimeError("ezdxf is required for synthetic DXF conversion")
    doc = ezdxf.readfile(path)
    out: list[dict] = []
    info: Counter = Counter()
    for entity in doc.modelspace():
        if entity.dxftype() == "INSERT":
            info["top_inserts"] += 1
            _walk_insert(doc, entity, None, (), frozenset(), 1, out, info)
        else:
            pieces = _entity_segments(entity, None, ())
            out.extend(pieces)
            info["top_segments"] += len(pieces)
    for index, item in enumerate(out, 1):
        item["sid"] = f"s{index:07d}"
    return {
        "ir": "seg.v1",
        "drawing_id": path.stem,
        "units": _units_from_doc(doc),
        "scale_mm_per_unit": None,
        "segments": out,
        "_expand_info": dict(info),
    }


def segir_from_block(doc, block_name: str) -> dict[str, Any]:
    """Flatten one staged block definition without reading any original CAD."""
    block = doc.blocks.get(block_name)
    if block is None:
        return {
            "ir": "seg.v1", "drawing_id": "staged-block", "units": _units_from_doc(doc),
            "scale_mm_per_unit": None, "segments": [],
            "_expand_info": {"missing_block": 1},
        }
    out: list[dict] = []
    info: Counter = Counter()
    root_stack = frozenset({block_name})
    for entity in block:
        if entity.dxftype() == "INSERT":
            _walk_insert(doc, entity, None, (), root_stack, 1, out, info)
        else:
            pieces = _entity_segments(entity, None, ())
            out.extend(pieces)
            info["top_segments"] += len(pieces)
    for index, item in enumerate(out, 1):
        item["sid"] = f"s{index:07d}"
    return {
        "ir": "seg.v1",
        "drawing_id": "staged-block",
        "units": _units_from_doc(doc),
        "scale_mm_per_unit": None,
        "segments": out,
        "_expand_info": dict(info),
    }


# ---------------------------------------------------------------------------
# Geometry canonicalization and typed edge construction
# ---------------------------------------------------------------------------


def _round_float(value: float, digits: int) -> float:
    result = round(float(value), digits)
    return 0.0 if result == 0.0 else result


def _geometry_signature(
    p0: tuple[float, float],
    p1: tuple[float, float],
    kind: str,
    sagitta: float,
    closed: bool,
    digits: int,
) -> tuple[str, str]:
    a = (_round_float(p0[0], digits), _round_float(p0[1], digits))
    b = (_round_float(p1[0], digits), _round_float(p1[1], digits))
    if b < a:
        a, b = b, a
    geometry_family = (
        "arc" if "arc" in kind else "poly" if "poly" in kind else "line"
    )
    signature = json.dumps(
        [a[0], a[1], b[0], b[1], geometry_family,
         _round_float(sagitta, digits), bool(closed)],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return signature, hashlib.sha256(signature.encode("ascii")).hexdigest()


def prepare_nodes(ir: dict[str, Any], config: GraphConfig) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    dropped = Counter()
    for source_position, segment in enumerate(ir.get("segments") or []):
        points = segment.get("pts") or []
        if len(points) < 2:
            dropped["missing_endpoints"] += 1
            continue
        try:
            p0 = (float(points[0][0]), float(points[0][1]))
            p1 = (float(points[-1][0]), float(points[-1][1]))
        except (TypeError, ValueError, IndexError):
            dropped["invalid_endpoints"] += 1
            continue
        if not all(math.isfinite(v) for v in (*p0, *p1)):
            dropped["nonfinite"] += 1
            continue
        length = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if length <= 1e-12:
            dropped["zero_length"] += 1
            continue
        kind = str(segment.get("kind") or "line").lower()
        sagitta = float(segment.get("sagitta") or 0.0)
        closed = bool(segment.get("closed") or False)
        signature, geometry_hash = _geometry_signature(
            p0, p1, kind, sagitta, closed, config.geometry_round_digits
        )
        # Canonical endpoint orientation makes direction reversal graph-invariant.
        if p1 < p0:
            p0, p1 = p1, p0
        records.append({
            "p0": p0,
            "p1": p1,
            "length": length,
            "kind": kind,
            "sagitta": sagitta,
            "closed": closed,
            "handle": "" if segment.get("handle") is None else str(segment.get("handle")),
            "insert_path": tuple(str(v) for v in (segment.get("insert_path") or [])),
            "geometry_signature": signature,
            "geometry_hash": geometry_hash,
            # Retained only to prove it is not used in canonical sorting/tie-breaking.
            "_source_position": source_position,
        })
    records.sort(key=lambda item: (item["geometry_hash"], item["geometry_signature"]))
    n = len(records)
    if n:
        coords = np.asarray(
            [[*item["p0"], *item["p1"]] for item in records], dtype=np.float64
        )
        lengths = np.asarray([item["length"] for item in records], dtype=np.float64)
        xmin = np.minimum(coords[:, 0], coords[:, 2])
        ymin = np.minimum(coords[:, 1], coords[:, 3])
        xmax = np.maximum(coords[:, 0], coords[:, 2])
        ymax = np.maximum(coords[:, 1], coords[:, 3])
    else:
        coords = np.zeros((0, 4), dtype=np.float64)
        lengths = np.zeros(0, dtype=np.float64)
        xmin = ymin = xmax = ymax = np.zeros(0, dtype=np.float64)

    explicit_scale = ir.get("scale_mm_per_unit")
    if explicit_scale is not None:
        try:
            explicit_scale = float(explicit_scale)
        except (TypeError, ValueError):
            explicit_scale = None
    if explicit_scale is not None and explicit_scale > 0:
        robust_scale = 1000.0 / explicit_scale
        scale_source = "scale_mm_per_unit"
    elif str(ir.get("units", "")).lower() == "mm":
        robust_scale = 1000.0
        scale_source = "explicit_mm_1000"
    elif n:
        robust_scale = float(np.median(lengths))
        if not math.isfinite(robust_scale) or robust_scale <= 1e-12:
            robust_scale = 1.0
        scale_source = "median_segment_length_fallback"
    else:
        robust_scale = 1.0
        scale_source = "empty_fallback"

    return {
        "records": records,
        "coords": coords,
        "lengths": lengths,
        "xmin": xmin,
        "ymin": ymin,
        "xmax": xmax,
        "ymax": ymax,
        "robust_scale": robust_scale,
        "scale_source": scale_source,
        "dropped": dict(dropped),
        "input_segment_count": len(ir.get("segments") or []),
    }


def _segment_cells(
    p0: tuple[float, float],
    p1: tuple[float, float],
    cell_size: float,
    cap: int,
) -> tuple[tuple[tuple[int, int], ...], bool]:
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ideal_steps = max(1, int(math.ceil(max(abs(dx), abs(dy)) / cell_size)))
    steps = min(cap, ideal_steps)
    truncated = ideal_steps > cap
    cells = {
        (math.floor((p0[0] + dx * (k / steps)) / cell_size),
         math.floor((p0[1] + dy * (k / steps)) / cell_size))
        for k in range(steps + 1)
    }
    return tuple(sorted(cells)), truncated


def _bbox_distance(prepared: dict[str, Any], i: int, j: int) -> float:
    dx = max(
        0.0,
        float(prepared["xmin"][i] - prepared["xmax"][j]),
        float(prepared["xmin"][j] - prepared["xmax"][i]),
    )
    dy = max(
        0.0,
        float(prepared["ymin"][i] - prepared["ymax"][j]),
        float(prepared["ymin"][j] - prepared["ymax"][i]),
    )
    return math.hypot(dx, dy)


def _point_segment_distance(
    point: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> tuple[float, float]:
    dx, dy = b[0] - a[0], b[1] - a[1]
    denom = dx * dx + dy * dy
    if denom <= 1e-24:
        return math.hypot(point[0] - a[0], point[1] - a[1]), 0.0
    t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / denom
    tc = min(1.0, max(0.0, t))
    qx, qy = a[0] + tc * dx, a[1] + tc * dy
    return math.hypot(point[0] - qx, point[1] - qy), tc


def _cross(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def _intersection_and_distance(
    a0: tuple[float, float],
    a1: tuple[float, float],
    b0: tuple[float, float],
    b1: tuple[float, float],
    snap: float,
) -> tuple[float, int]:
    """Return minimum distance and intersection class.

    Class: 0 none, 1 endpoint-endpoint, 2 endpoint-interior,
    3 interior-interior crossing, 4 collinear overlap.
    """
    ax, ay = a1[0] - a0[0], a1[1] - a0[1]
    bx, by = b1[0] - b0[0], b1[1] - b0[1]
    qx, qy = b0[0] - a0[0], b0[1] - a0[1]
    denominator = _cross(ax, ay, bx, by)
    scale = max(math.hypot(ax, ay), math.hypot(bx, by), 1.0)
    eps = max(1e-12 * scale * scale, snap * 1e-9)
    if abs(denominator) > eps:
        ta = _cross(qx, qy, bx, by) / denominator
        tb = _cross(qx, qy, ax, ay) / denominator
        tolerance = snap / scale
        if -tolerance <= ta <= 1.0 + tolerance and -tolerance <= tb <= 1.0 + tolerance:
            endpoint_a = ta <= tolerance or ta >= 1.0 - tolerance
            endpoint_b = tb <= tolerance or tb >= 1.0 - tolerance
            if endpoint_a and endpoint_b:
                return 0.0, 1
            if endpoint_a or endpoint_b:
                return 0.0, 2
            return 0.0, 3
    else:
        normal = abs(_cross(qx, qy, ax, ay)) / max(math.hypot(ax, ay), 1e-12)
        if normal <= snap:
            length_sq = ax * ax + ay * ay
            t0 = (qx * ax + qy * ay) / max(length_sq, 1e-24)
            t1 = t0 + (bx * ax + by * ay) / max(length_sq, 1e-24)
            if min(max(t0, t1), 1.0) >= max(min(t0, t1), 0.0):
                return 0.0, 4

    distances = [
        _point_segment_distance(a0, b0, b1),
        _point_segment_distance(a1, b0, b1),
        _point_segment_distance(b0, a0, a1),
        _point_segment_distance(b1, a0, a1),
    ]
    distance, _ = min(distances, key=lambda item: item[0])
    if distance <= snap:
        endpoint_hits = 0
        for endpoint in (a0, a1):
            if min(math.hypot(endpoint[0] - q[0], endpoint[1] - q[1])
                   for q in (b0, b1)) <= snap:
                endpoint_hits += 1
        return distance, 1 if endpoint_hits else 2
    return distance, 0


def _pair_metrics(
    a: dict[str, Any], b: dict[str, Any], snap: float
) -> dict[str, float | int]:
    a0, a1, b0, b1 = a["p0"], a["p1"], b["p0"], b["p1"]
    adx, ady = a1[0] - a0[0], a1[1] - a0[1]
    bdx, bdy = b1[0] - b0[0], b1[1] - b0[1]
    alen, blen = a["length"], b["length"]
    aux, auy = adx / alen, ady / alen
    bux, buy = bdx / blen, bdy / blen
    dot = min(1.0, max(-1.0, abs(aux * bux + auy * buy)))
    angle = math.degrees(math.acos(dot))
    distance, intersection_code = _intersection_and_distance(a0, a1, b0, b1, snap)
    t0 = (b0[0] - a0[0]) * aux + (b0[1] - a0[1]) * auy
    t1 = (b1[0] - a0[0]) * aux + (b1[1] - a0[1]) * auy
    blo, bhi = min(t0, t1), max(t0, t1)
    overlap_length = max(0.0, min(alen, bhi) - max(0.0, blo))
    overlap = overlap_length / max(min(alen, blen), 1e-12)
    along_gap = max(0.0, max(0.0, blo) - min(alen, bhi))
    amid = ((a0[0] + a1[0]) * 0.5, (a0[1] + a1[1]) * 0.5)
    bmid = ((b0[0] + b1[0]) * 0.5, (b0[1] + b1[1]) * 0.5)
    normal_offset = abs((bmid[0] - amid[0]) * (-auy) + (bmid[1] - amid[1]) * aux)
    return {
        "distance": distance,
        "intersection_code": intersection_code,
        "angle": angle,
        "overlap": overlap,
        "normal_offset": normal_offset,
        "along_gap": along_gap,
    }


def _select_ranked(
    candidates: list[tuple[tuple[Any, ...], int, tuple[float, ...]]], k: int
) -> tuple[list[tuple[tuple[Any, ...], int, tuple[float, ...]]], int, int]:
    if not candidates:
        return [], 0, 0
    candidates.sort(key=lambda item: item[0])
    if k <= 0 or len(candidates) <= k:
        return candidates, 0, 0
    boundary = candidates[k - 1][0]
    selected = [item for item in candidates if item[0] <= boundary]
    overflow = max(0, len(selected) - k)
    return selected, len(candidates) - len(selected), overflow


def _make_structural_edges(
    records: list[dict[str, Any]], config: GraphConfig
) -> tuple[dict[int, list[tuple[int, int, float]]], dict[str, int]]:
    """Geometry-ordered structural connectivity; identifiers only define membership."""
    adjacency: dict[int, list[tuple[int, int, float]]] = defaultdict(list)
    entity_groups: dict[tuple[str, tuple[str, ...]], list[int]] = defaultdict(list)
    container_groups: dict[tuple[str, ...], list[int]] = defaultdict(list)
    handle_paths: dict[str, dict[tuple[str, ...], list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for i, record in enumerate(records):
        handle = record["handle"]
        path = record["insert_path"]
        if handle:
            entity_groups[(handle, path)].append(i)
            if path:
                handle_paths[handle][path].append(i)
        if path:
            container_groups[path].append(i)

    def add_both(a: int, b: int, type_name: str, depth: float) -> None:
        if a == b:
            return
        type_id = EDGE_TYPE_ID[type_name]
        adjacency[a].append((type_id, b, depth))
        adjacency[b].append((type_id, a, depth))

    entity_relation_pairs = 0
    for members in entity_groups.values():
        if len(members) < 2:
            continue
        ordered = sorted(members, key=lambda i: (
            records[i]["geometry_hash"], records[i]["geometry_signature"]
        ))
        if len(ordered) <= config.containment_entity_cap:
            for pos, a in enumerate(ordered):
                for b in ordered[pos + 1:]:
                    add_both(a, b, "containment", float(len(records[a]["insert_path"])))
                    entity_relation_pairs += 1
        else:
            for a, b in zip(ordered, ordered[1:]):
                add_both(a, b, "containment", float(len(records[a]["insert_path"])))
                entity_relation_pairs += 1

    container_chain_pairs = 0
    for path, members in container_groups.items():
        if len(members) < 2:
            continue
        ordered = sorted(members, key=lambda i: (
            records[i]["geometry_hash"], records[i]["geometry_signature"]
        ))
        for a, b in zip(ordered, ordered[1:]):
            add_both(a, b, "containment", float(len(path)))
            container_chain_pairs += 1

    instancing_pairs = 0
    for path_map in handle_paths.values():
        if len(path_map) < 2:
            continue
        representatives = [
            min(members, key=lambda i: (
                records[i]["geometry_hash"], records[i]["geometry_signature"]
            ))
            for members in path_map.values()
        ]
        representatives.sort(key=lambda i: (
            records[i]["geometry_hash"], records[i]["geometry_signature"]
        ))
        for a, b in zip(representatives, representatives[1:]):
            add_both(a, b, "instancing", 0.0)
            instancing_pairs += 1

    return adjacency, {
        "entity_containment_undirected_pairs": entity_relation_pairs,
        "container_chain_undirected_pairs": container_chain_pairs,
        "instancing_chain_undirected_pairs": instancing_pairs,
    }


def _features(
    prepared: dict[str, Any], fanout_by_type: dict[str, np.ndarray], config: GraphConfig
) -> np.ndarray:
    records = prepared["records"]
    n = len(records)
    if not n:
        return np.zeros((0, len(FEATURE_NAMES)), dtype=np.float32)
    coords = prepared["coords"]
    lengths = prepared["lengths"]
    scale = prepared["robust_scale"]
    xmin, ymin = float(coords[:, [0, 2]].min()), float(coords[:, [1, 3]].min())
    xmax, ymax = float(coords[:, [0, 2]].max()), float(coords[:, [1, 3]].max())
    span = max(xmax - xmin, ymax - ymin, scale, 1e-12)
    center_x, center_y = (xmin + xmax) * 0.5, (ymin + ymax) * 0.5
    snap = max(config.junction_snap_norm * scale, 1e-12)
    endpoint_counts: Counter[tuple[int, int]] = Counter()
    endpoint_keys: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for record in records:
        keys = tuple(
            (int(round(point[0] / snap)), int(round(point[1] / snap)))
            for point in (record["p0"], record["p1"])
        )
        endpoint_keys.append(keys)  # type: ignore[arg-type]
        endpoint_counts.update(keys)

    output = np.zeros((n, len(FEATURE_NAMES)), dtype=np.float32)
    for i, record in enumerate(records):
        p0, p1 = record["p0"], record["p1"]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        theta = math.atan2(dy, dx)
        kind = record["kind"]
        endpoint_degree = sum(max(0, endpoint_counts[key] - 1) for key in endpoint_keys[i])
        values = (
            math.log1p(lengths[i] / scale),
            (((p0[0] + p1[0]) * 0.5) - center_x) / span,
            (((p0[1] + p1[1]) * 0.5) - center_y) / span,
            abs(dx) / scale,
            abs(dy) / scale,
            math.sin(2.0 * theta),
            math.cos(2.0 * theta),
            float(record["sagitta"]) / scale,
            1.0 if record["closed"] else 0.0,
            1.0 if "line" in kind and "poly" not in kind else 0.0,
            1.0 if "poly" in kind else 0.0,
            1.0 if "arc" in kind else 0.0,
            math.log1p(endpoint_degree),
            math.log1p(int(fanout_by_type["intersection_junction"][i])),
            math.log1p(int(fanout_by_type["parallel_band"][i])),
            math.log1p(int(fanout_by_type["collinearity"][i])),
            min(16, len(record["insert_path"])) / 16.0,
        )
        output[i] = np.asarray(values, dtype=np.float32)
    return output


def build_graph(
    ir: dict[str, Any],
    config: GraphConfig | None = None,
    *,
    collect_edges: bool = True,
) -> dict[str, Any]:
    """Build a deterministic directed typed graph.

    For large inputs, ``collect_edges=False`` retains exact counts, fanout, hash,
    cap-drop accounting, and shard sizes while streaming edge rows instead of
    materializing the full table.
    """
    config = config or GraphConfig()
    started = time.perf_counter()
    prepared = prepare_nodes(ir, config)
    records: list[dict[str, Any]] = prepared["records"]
    n = len(records)
    info = Counter(ir.get("_expand_info") or {})
    unresolved = int(
        info.get("missing_block", 0)
        + info.get("cycle_skipped", 0)
        + info.get("max_depth_hit", 0)
    )
    if unresolved:
        status = "invalid_unresolved_reference"
    elif n == 0:
        status = "degenerate_empty"
    elif n == 1:
        status = "degenerate_singleton"
    else:
        status = "ok"

    fanout = np.zeros(n, dtype=np.int32)
    fanout_by_type = {name: np.zeros(n, dtype=np.int32) for name in EDGE_TYPES}
    edge_src: list[int] = []
    edge_dst: list[int] = []
    edge_type: list[int] = []
    edge_attr: list[tuple[float, ...]] = []
    relation_counts: Counter[str] = Counter()
    eligible_counts: Counter[str] = Counter()
    cap_drops: Counter[str] = Counter()
    cap_tie_overflow: Counter[str] = Counter()
    candidate_numbers: Counter[str] = Counter()

    digest = hashlib.sha256()
    digest.update(f"{SCHEMA}|{config.digest()}|{status}|{n}\n".encode("ascii"))
    for record in records:
        digest.update(("N|" + record["geometry_hash"] + "\n").encode("ascii"))

    if n:
        scale = float(prepared["robust_scale"])
        max_radius_norm = max(
            config.proximity_radius_norm,
            config.parallel_offset_norm,
            config.collinear_gap_norm,
        )
        cell_size = max(max_radius_norm * scale, 1e-9)
        grid: dict[tuple[int, int], list[int]] = defaultdict(list)
        node_cells: list[tuple[tuple[int, int], ...]] = []
        for i, record in enumerate(records):
            cells, truncated = _segment_cells(
                record["p0"], record["p1"], cell_size,
                config.max_index_cells_per_segment,
            )
            node_cells.append(cells)
            if truncated:
                candidate_numbers["index_truncated_segments"] += 1
            for cell in cells:
                grid[cell].append(i)
        for bucket in grid.values():
            bucket.sort(key=lambda j: (
                records[j]["geometry_hash"], records[j]["geometry_signature"]
            ))
        candidate_numbers["spatial_grid_cells"] = len(grid)
        candidate_numbers["spatial_grid_entries"] = sum(len(v) for v in grid.values())
        structural, structural_numbers = _make_structural_edges(records, config)
    else:
        scale = 1.0
        cell_size = 1.0
        grid = {}
        node_cells = []
        structural = {}
        structural_numbers = {
            "entity_containment_undirected_pairs": 0,
            "container_chain_undirected_pairs": 0,
            "instancing_chain_undirected_pairs": 0,
        }

    snap = config.junction_snap_norm * scale
    shard_records: list[dict[str, int]] = []
    core_cap = max(1, config.max_core_nodes_per_shard)

    for shard_start in range(0, n, core_cap):
        shard_end = min(n, shard_start + core_cap)
        shard_nodes = set(range(shard_start, shard_end))
        shard_edge_count = 0
        for i in range(shard_start, shard_end):
            query_cells: set[tuple[int, int]] = set()
            for cx, cy in node_cells[i]:
                for ox in (-1, 0, 1):
                    for oy in (-1, 0, 1):
                        query_cells.add((cx + ox, cy + oy))
            pool: set[int] = set()
            hard_truncated = False
            for cell in sorted(query_cells):
                for j in grid.get(cell, ()):
                    if j == i or j in pool:
                        continue
                    pool.add(j)
                    if len(pool) >= config.max_candidate_collect:
                        hard_truncated = True
                        break
                if hard_truncated:
                    break
            candidate_numbers["candidate_pool_collected"] += len(pool)
            if hard_truncated:
                candidate_numbers["hard_collect_truncated_nodes"] += 1

            cheap_ranked = [
                ((
                    round(_bbox_distance(prepared, i, j) / scale, 12),
                    records[j]["geometry_hash"],
                    records[j]["geometry_signature"],
                ), j)
                for j in pool
            ]
            if len(cheap_ranked) > config.max_candidate_scan:
                smallest = heapq.nsmallest(
                    config.max_candidate_scan, cheap_ranked, key=lambda item: item[0]
                )
                boundary = max(item[0] for item in smallest)
                selected_ranked = [item for item in cheap_ranked if item[0] <= boundary]
                selected_ranked.sort(key=lambda item: item[0])
                scanned = [j for _rank, j in selected_ranked]
                candidate_numbers["candidate_scan_dropped"] += (
                    len(cheap_ranked) - len(scanned)
                )
                candidate_numbers["scan_truncated_nodes"] += 1
                candidate_numbers["scan_tie_overflow"] += max(
                    0, len(scanned) - config.max_candidate_scan
                )
            else:
                cheap_ranked.sort(key=lambda item: item[0])
                scanned = [j for _rank, j in cheap_ranked]
            candidate_numbers["candidate_pairs_scanned_directed"] += len(scanned)

            ranked: dict[str, list[tuple[tuple[Any, ...], int, tuple[float, ...]]]] = {
                "parallel_band": [], "proximity": [], "collinearity": []
            }
            edge_map: dict[tuple[int, int], tuple[float, ...]] = {}
            source = records[i]
            for j in scanned:
                target = records[j]
                metrics = _pair_metrics(source, target, snap)
                dist_norm = float(metrics["distance"]) / scale
                angle = float(metrics["angle"])
                overlap = float(metrics["overlap"])
                offset_norm = float(metrics["normal_offset"]) / scale
                gap_norm = float(metrics["along_gap"]) / scale
                intersection_code = int(metrics["intersection_code"])
                base_attr = (
                    round(dist_norm, 8),
                    round(angle / 180.0, 8),
                    round(overlap, 8),
                    round(offset_norm, 8),
                    round(gap_norm, 8),
                    round(intersection_code / 4.0, 8),
                    0.0,
                    0.0,
                )
                target_hash = target["geometry_hash"]
                if intersection_code:
                    edge_map[(EDGE_TYPE_ID["intersection_junction"], j)] = base_attr
                    eligible_counts["intersection_junction"] += 1
                if dist_norm <= config.proximity_radius_norm:
                    rank = (round(dist_norm, 12), target_hash, target["geometry_signature"])
                    ranked["proximity"].append((rank, j, base_attr))
                    eligible_counts["proximity"] += 1
                if (
                    angle <= config.angle_parallel_deg
                    and overlap >= config.parallel_min_overlap
                    and offset_norm <= config.parallel_offset_norm
                ):
                    rank = (
                        round(offset_norm, 12), round(1.0 - overlap, 12),
                        round(angle, 12), target_hash, target["geometry_signature"],
                    )
                    ranked["parallel_band"].append((rank, j, base_attr))
                    eligible_counts["parallel_band"] += 1
                if (
                    angle <= config.angle_collinear_deg
                    and offset_norm <= config.collinear_offset_norm
                    and gap_norm <= config.collinear_gap_norm
                ):
                    rank = (
                        round(offset_norm, 12), round(gap_norm, 12),
                        round(angle, 12), target_hash, target["geometry_signature"],
                    )
                    ranked["collinearity"].append((rank, j, base_attr))
                    eligible_counts["collinearity"] += 1

            for relation, k in (
                ("parallel_band", config.topk_parallel),
                ("proximity", config.topk_proximity),
                ("collinearity", config.topk_collinear),
            ):
                selected, dropped, overflow = _select_ranked(ranked[relation], k)
                cap_drops[relation] += dropped
                cap_tie_overflow[relation] += overflow
                type_id = EDGE_TYPE_ID[relation]
                for rank_position, (_, j, attrs) in enumerate(selected, 1):
                    updated = list(attrs)
                    updated[7] = round(rank_position / max(1, k), 8)
                    edge_map[(type_id, j)] = tuple(updated)

            for type_id, j, depth in structural.get(i, ()):
                attrs = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                         round(min(depth, 16.0) / 16.0, 8), 0.0)
                key = (type_id, j)
                if key not in edge_map or attrs < edge_map[key]:
                    edge_map[key] = attrs

            ordered_edges = sorted(
                edge_map.items(),
                key=lambda item: (
                    item[0][0], records[item[0][1]]["geometry_hash"],
                    records[item[0][1]]["geometry_signature"], item[1],
                ),
            )
            fanout[i] = len(ordered_edges)
            shard_edge_count += len(ordered_edges)
            for (type_id, j), attrs in ordered_edges:
                relation_name = EDGE_TYPES[type_id]
                relation_counts[relation_name] += 1
                fanout_by_type[relation_name][i] += 1
                shard_nodes.add(j)
                digest.update(
                    (
                        "E|" + source["geometry_hash"] + "|" + relation_name + "|"
                        + records[j]["geometry_hash"] + "|"
                        + ",".join(f"{v:.8g}" for v in attrs) + "\n"
                    ).encode("ascii")
                )
                if collect_edges:
                    edge_src.append(i)
                    edge_dst.append(j)
                    edge_type.append(type_id)
                    edge_attr.append(attrs)
        shard_records.append({
            "shard_index": len(shard_records),
            "core_nodes": shard_end - shard_start,
            "nodes_with_halo": len(shard_nodes),
            "directed_edges": shard_edge_count,
        })

    edge_count = int(fanout.sum(dtype=np.int64))
    features = _features(prepared, fanout_by_type, config) if collect_edges else None
    elapsed = time.perf_counter() - started
    stats = {
        "schema": SCHEMA,
        "status": status,
        "node_count": n,
        "directed_edge_count": edge_count,
        "edge_node_ratio": (edge_count / n) if n else 0.0,
        "fanout_quantiles": _quantiles(fanout),
        "relation_directed_edge_counts": {
            name: int(relation_counts.get(name, 0)) for name in EDGE_TYPES
        },
        "relation_fanout_quantiles": {
            name: _quantiles(fanout_by_type[name]) for name in EDGE_TYPES
        },
        "eligible_directed_candidate_counts": {
            name: int(eligible_counts.get(name, 0)) for name in EDGE_TYPES
        },
        "relation_cap_drops": {
            name: int(cap_drops.get(name, 0)) for name in EDGE_TYPES
        },
        "relation_cap_tie_overflow": {
            name: int(cap_tie_overflow.get(name, 0)) for name in EDGE_TYPES
        },
        "candidate_scan": dict(sorted(candidate_numbers.items())),
        "structural_construction": structural_numbers,
        "input_segment_count": prepared["input_segment_count"],
        "dropped_input_segments": prepared["dropped"],
        "robust_scale_units": prepared["robust_scale"],
        "scale_source": prepared["scale_source"],
        "unresolved_reference_count": unresolved,
        "expand_info": dict(sorted(info.items())),
        "graph_hash": digest.hexdigest(),
        "config_hash": config.digest(),
        "build_seconds": elapsed,
        "shard_count": len(shard_records),
        "maximum_shard_core_nodes": max((r["core_nodes"] for r in shard_records), default=0),
        "maximum_shard_nodes_with_halo": max(
            (r["nodes_with_halo"] for r in shard_records), default=0
        ),
        "maximum_shard_directed_edges": max(
            (r["directed_edges"] for r in shard_records), default=0
        ),
    }
    return {
        "stats": stats,
        "config": config,
        "prepared": prepared,
        "features": features,
        "fanout": fanout,
        "fanout_by_type": fanout_by_type,
        "edge_src": np.asarray(edge_src, dtype=np.int64) if collect_edges else None,
        "edge_dst": np.asarray(edge_dst, dtype=np.int64) if collect_edges else None,
        "edge_type": np.asarray(edge_type, dtype=np.int16) if collect_edges else None,
        "edge_attr": (
            np.asarray(edge_attr, dtype=np.float32).reshape((-1, 8))
            if collect_edges else None
        ),
        "shards": shard_records,
    }


def save_graph(path: Path, result: dict[str, Any]) -> None:
    if result["edge_src"] is None or result["features"] is None:
        raise ValueError("save_graph requires build_graph(..., collect_edges=True)")
    path = path.with_suffix(".npz")
    path.parent.mkdir(parents=True, exist_ok=True)
    prepared = result["prepared"]
    records = prepared["records"]
    handles = np.asarray([record["handle"] for record in records], dtype=np.str_)
    geometry_hashes = np.asarray(
        [record["geometry_hash"] for record in records], dtype="<U64"
    )
    depths = np.asarray([len(record["insert_path"]) for record in records], dtype=np.int16)
    metadata = {
        "schema": SCHEMA,
        "feature_names": list(FEATURE_NAMES),
        "edge_type_names": list(EDGE_TYPES),
        "edge_attribute_names": [
            "distance_norm", "angle_fraction_180", "projected_overlap",
            "normal_offset_norm", "along_gap_norm", "intersection_class_fraction",
            "shared_container_depth_norm", "cap_rank_fraction",
        ],
        "identifier_policy": {
            "node_handle": "traceability_sidecar_only",
            "feature_or_tiebreak_use": 0,
        },
        "config": result["config"].canonical(),
        "stats": result["stats"],
        "shards": result["shards"],
    }
    temp = path.with_name(path.stem + ".tmp.npz")
    np.savez_compressed(
        temp,
        node_features=result["features"].astype(np.float32, copy=False),
        node_geometry=prepared["coords"].astype(np.float64, copy=False),
        node_handle=handles,
        node_geometry_hash=geometry_hashes,
        node_block_depth=depths,
        edge_src=result["edge_src"],
        edge_dst=result["edge_dst"],
        edge_type=result["edge_type"],
        edge_attr=result["edge_attr"],
        feature_names=np.asarray(FEATURE_NAMES, dtype=np.str_),
        edge_type_names=np.asarray(EDGE_TYPES, dtype=np.str_),
        metadata_json=np.asarray(
            json.dumps(_json_ready(metadata), ensure_ascii=False, sort_keys=True),
            dtype=np.str_,
        ),
    )
    os.replace(temp, path)
    sidecar = path.with_suffix(".json")
    metadata["npz_sha256"] = _sha256_file(path)
    write_json(sidecar, metadata)


def load_segir(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


# ---------------------------------------------------------------------------
# Selftest and synthetic relation-recall oracle
# ---------------------------------------------------------------------------


def _edge_pairs(result: dict[str, Any], relation: str) -> set[tuple[int, int]]:
    if result["edge_src"] is None:
        raise ValueError("edge lookup requires a collected graph")
    type_id = EDGE_TYPE_ID[relation]
    return {
        (int(src), int(dst))
        for src, dst, edge_type in zip(
            result["edge_src"], result["edge_dst"], result["edge_type"]
        )
        if int(edge_type) == type_id
    }


def _indices_by_handle(result: dict[str, Any]) -> dict[str, set[int]]:
    output: dict[str, set[int]] = defaultdict(set)
    for i, record in enumerate(result["prepared"]["records"]):
        if record["handle"]:
            output[record["handle"]].add(i)
    return output


def _has_cross_edge(
    edges: set[tuple[int, int]], a: Iterable[int], b: Iterable[int]
) -> bool:
    left, right = set(a), set(b)
    return any((i, j) in edges or (j, i) in edges for i in left for j in right if i != j)


def run_selftest() -> tuple[bool, list[str], dict[str, Any]]:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str) -> None:
        checks.append((name, bool(condition), detail))

    mini_segments = [
        {"handle": "a", "pts": [[0, 0], [10, 0]], "kind": "line"},
        {"handle": "b", "pts": [[0, 1], [10, 1]], "kind": "line"},
        {"handle": "x", "pts": [[5, -2], [5, 2]], "kind": "line"},
        {"handle": "c", "pts": [[12, 0], [20, 0]], "kind": "line"},
        {"handle": "near", "pts": [[0, 2], [10, 2]], "kind": "line"},
        {"handle": "poly", "pts": [[30, 0], [35, 0]], "kind": "poly-edge",
         "insert_path": ["container"]},
        {"handle": "poly", "pts": [[35, 0], [35, 5]], "kind": "poly-edge",
         "insert_path": ["container"]},
        {"handle": "leaf", "pts": [[40, 0], [45, 0]], "kind": "line",
         "insert_path": ["ref-a"]},
        {"handle": "leaf", "pts": [[50, 0], [55, 0]], "kind": "line",
         "insert_path": ["ref-b"]},
    ]
    mini = {
        "ir": "seg.v1", "drawing_id": "mini", "units": "unknown",
        "scale_mm_per_unit": None, "segments": mini_segments,
    }
    first = build_graph(mini, collect_edges=True)
    second = build_graph(mini, collect_edges=True)
    shuffled = dict(mini)
    shuffled["segments"] = list(reversed(mini_segments))
    permuted = build_graph(shuffled, collect_edges=True)
    check(
        "same_input_graph_hash",
        first["stats"]["graph_hash"] == second["stats"]["graph_hash"],
        first["stats"]["graph_hash"],
    )
    check(
        "node_permutation_graph_hash",
        first["stats"]["graph_hash"] == permuted["stats"]["graph_hash"],
        permuted["stats"]["graph_hash"],
    )
    by_handle = _indices_by_handle(first)
    relation_expectations = {
        "parallel_band": (by_handle["a"], by_handle["b"]),
        "intersection_junction": (by_handle["a"], by_handle["x"]),
        "proximity": (by_handle["a"], by_handle["near"]),
        "collinearity": (by_handle["a"], by_handle["c"]),
        "containment": (by_handle["poly"], by_handle["poly"]),
        "instancing": (by_handle["leaf"], by_handle["leaf"]),
    }
    for relation, (a, b) in relation_expectations.items():
        edges = _edge_pairs(first, relation)
        check(
            f"mini_relation_{relation}",
            _has_cross_edge(edges, a, b),
            f"support_pair_nodes={len(a)}x{len(b)} directed_edges={len(edges)}",
        )

    empty = build_graph({"ir": "seg.v1", "segments": []}, collect_edges=True)
    singleton = build_graph({
        "ir": "seg.v1",
        "segments": [{"handle": "only", "pts": [[0, 0], [1, 0]]}],
    }, collect_edges=True)
    degenerate = build_graph({
        "ir": "seg.v1",
        "segments": [{"handle": "zero", "pts": [[0, 0], [0, 0]]}],
    }, collect_edges=True)
    check(
        "empty_honest_status",
        empty["stats"]["status"] == "degenerate_empty"
        and empty["stats"]["node_count"] == 0
        and empty["stats"]["directed_edge_count"] == 0,
        f"status={empty['stats']['status']} nodes={empty['stats']['node_count']} "
        f"edges={empty['stats']['directed_edge_count']}",
    )
    check(
        "singleton_honest_status",
        singleton["stats"]["status"] == "degenerate_singleton"
        and singleton["stats"]["node_count"] == 1
        and singleton["stats"]["directed_edge_count"] == 0,
        f"status={singleton['stats']['status']} nodes={singleton['stats']['node_count']} "
        f"edges={singleton['stats']['directed_edge_count']}",
    )
    check(
        "zero_length_not_recast",
        degenerate["stats"]["status"] == "degenerate_empty"
        and degenerate["stats"]["dropped_input_segments"].get("zero_length") == 1,
        json.dumps(degenerate["stats"]["dropped_input_segments"], sort_keys=True),
    )
    forbidden_hits = [
        name for name in FEATURE_NAMES
        if any(token in name.lower() for token in FORBIDDEN_FEATURE_TOKENS)
    ]
    check(
        "identifier_name_feature_exclusion",
        not forbidden_hits,
        f"feature_count={len(FEATURE_NAMES)} forbidden_hits={forbidden_hits}",
    )
    feature_shape = first["features"].shape if first["features"] is not None else None
    check(
        "numeric_feature_matrix",
        feature_shape == (len(mini_segments), len(FEATURE_NAMES))
        and np.isfinite(first["features"]).all(),
        f"shape={feature_shape}",
    )

    ok_count = sum(1 for _, ok, _ in checks if ok)
    lines = [
        "=== graph_builder --selftest ===",
        f"python={sys.version.split()[0]} numpy={np.__version__} "
        f"ezdxf={getattr(ezdxf, '__version__', 'unavailable')}",
    ]
    for name, ok, detail in checks:
        lines.append(f"[{('OK' if ok else 'ERROR')}] {name}: {detail}")
    all_ok = ok_count == len(checks)
    lines.append(f"SELFTEST_RESULT: {('OK' if all_ok else 'ERROR')} ({ok_count}/{len(checks)})")
    details = {
        "checks_total": len(checks),
        "checks_ok": ok_count,
        "checks_error": len(checks) - ok_count,
        "graph_hash": first["stats"]["graph_hash"],
        "mini_nodes": first["stats"]["node_count"],
        "mini_directed_edges": first["stats"]["directed_edge_count"],
    }
    return all_ok, lines, details


def _axis_record(points: Sequence[Sequence[float]]) -> dict[str, Any]:
    p0 = (float(points[0][0]), float(points[0][1]))
    p1 = (float(points[-1][0]), float(points[-1][1]))
    return {"p0": p0, "p1": p1, "length": math.hypot(p1[0] - p0[0], p1[1] - p0[1])}


def _semantic_oracle_units(
    truth: dict[str, Any], ir: dict[str, Any], result: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    units: dict[str, list[dict[str, Any]]] = {name: [] for name in EDGE_TYPES}
    walls = truth.get("walls") or []
    wall_by_id = {str(wall.get("id")): wall for wall in walls}
    for wall in walls:
        handles = [str(h) for h in wall.get("handles") or []]
        if len(handles) >= 2:
            units["parallel_band"].append({
                "a_handles": [handles[0]], "b_handles": handles[1:],
                "oracle": "gen2.wall.handles",
            })
    for i, wall_a in enumerate(walls):
        axis_a = _axis_record(wall_a["axis"])
        for wall_b in walls[i + 1:]:
            axis_b = _axis_record(wall_b["axis"])
            metrics = _pair_metrics(axis_a, axis_b, 1e-6)
            a_handles = [str(h) for h in wall_a.get("handles") or []]
            b_handles = [str(h) for h in wall_b.get("handles") or []]
            if int(metrics["intersection_code"]) > 0:
                units["intersection_junction"].append({
                    "a_handles": a_handles, "b_handles": b_handles,
                    "oracle": "gen2.wall.axis_intersection",
                })
            if (
                float(metrics["angle"]) <= 1e-5
                and float(metrics["normal_offset"]) <= 1e-5
                and 1e-6 < float(metrics["along_gap"]) <= 2000.0
            ):
                units["collinearity"].append({
                    "a_handles": a_handles, "b_handles": b_handles,
                    "oracle": "gen2.wall.axis_collinear_fragment",
                })

    class_of_handle = {
        str(handle): str(class_name)
        for handle, class_name in (truth.get("class_of_handle") or {}).items()
    }
    prepared_records = result["prepared"]["records"]
    records_by_handle: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in prepared_records:
        records_by_handle[record["handle"]].append(record)
    door_handles = [
        handle for handle, class_name in class_of_handle.items()
        if class_name == "door_swing" and handle in records_by_handle
    ]
    unused = set(door_handles)
    for opening in truth.get("openings") or []:
        wall = wall_by_id.get(str(opening.get("wall_id")))
        if not wall or not unused:
            continue
        axis = _axis_record(wall["axis"])
        chosen = min(
            unused,
            key=lambda handle: min(
                _pair_metrics(axis, record, 1e-6)["distance"]
                for record in records_by_handle[handle]
            ),
        )
        unused.remove(chosen)
        units["proximity"].append({
            "a_handles": [chosen],
            "b_handles": [str(h) for h in wall.get("handles") or []],
            "oracle": "gen2.opening.wall_id_plus_nearest_door_geometry",
        })

    grouped_nodes: dict[tuple[str, tuple[str, ...]], list[int]] = defaultdict(list)
    handle_paths: dict[str, dict[tuple[str, ...], list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for index, record in enumerate(prepared_records):
        handle, path = record["handle"], record["insert_path"]
        if handle:
            grouped_nodes[(handle, path)].append(index)
            if path:
                handle_paths[handle][path].append(index)
    for (handle, _path), nodes in grouped_nodes.items():
        if len(nodes) >= 2 and handle in class_of_handle:
            units["containment"].append({
                "a_nodes": nodes, "b_nodes": nodes,
                "oracle": "dxf.entity_component_structure_with_truth_handle",
            })
    for _handle, path_map in handle_paths.items():
        if len(path_map) < 2:
            continue
        all_paths = list(path_map)
        for path in all_paths:
            other_nodes = [
                node for other_path, nodes in path_map.items() if other_path != path
                for node in nodes
            ]
            units["instancing"].append({
                "a_nodes": path_map[path], "b_nodes": other_nodes,
                "oracle": "dxf.insert_occurrence_structure",
            })
    return units


def _unit_recovered(
    unit: dict[str, Any], result: dict[str, Any], edges: set[tuple[int, int]]
) -> bool:
    if "a_nodes" in unit:
        return _has_cross_edge(edges, unit["a_nodes"], unit["b_nodes"])
    by_handle = _indices_by_handle(result)
    a = {node for handle in unit["a_handles"] for node in by_handle.get(handle, ())}
    b = {node for handle in unit["b_handles"] for node in by_handle.get(handle, ())}
    return bool(a and b and _has_cross_edge(edges, a, b))


def audit_synthetic_recall(
    repo: Path,
    outdir: Path,
    graph_samples: Path,
    config: GraphConfig,
    *,
    seed: int = 20260718,
    n_per_tier: int = 3,
) -> dict[str, Any]:
    gen2 = repo / "tools" / "e2" / "gen2" / "gen2.py"
    if not gen2.is_file():
        raise FileNotFoundError(gen2)
    totals = {
        name: {"support": 0, "recovered": 0, "uncapped_recovered": 0,
               "cap_attributable_false_negatives": 0, "oracle_sources": Counter()}
        for name in EDGE_TYPES
    }
    graph_rows: list[dict[str, Any]] = []
    unresolved_total = 0
    uncapped = replace(
        config,
        topk_parallel=100000,
        topk_proximity=100000,
        topk_collinear=100000,
        max_candidate_scan=max(2048, config.max_candidate_scan),
        max_candidate_collect=max(8192, config.max_candidate_collect),
    )
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="_gen2_recall_", dir=outdir) as temp_name:
        pack = Path(temp_name) / "pack"
        process = subprocess.run(
            [
                sys.executable, str(gen2), "build", "--out", str(pack),
                "--seed", str(seed), "--n-per-tier", str(n_per_tier),
                "--entity-count", "1400", "--calibration-pairs", "600",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"gen2 build rc={process.returncode}: {(process.stderr or process.stdout)[-1000:]}"
            )
        for tier in ("S", "F", "M"):
            manifest = json.loads((pack / tier / "manifest.json").read_text(encoding="utf-8"))
            for file_index, entry in enumerate(manifest["files"]):
                dxf_path = pack / tier / entry["dxf"]
                truth_path = pack / tier / entry["truth"]
                ir = segir_from_dxf_modelspace(dxf_path)
                capped_result = build_graph(ir, config, collect_edges=True)
                uncapped_result = build_graph(ir, uncapped, collect_edges=True)
                truth = json.loads(truth_path.read_text(encoding="utf-8"))
                units = _semantic_oracle_units(truth, ir, capped_result)
                per_type: dict[str, Any] = {}
                for relation in EDGE_TYPES:
                    capped_edges = _edge_pairs(capped_result, relation)
                    uncapped_edges = _edge_pairs(uncapped_result, relation)
                    support = len(units[relation])
                    recovered = sum(
                        _unit_recovered(unit, capped_result, capped_edges)
                        for unit in units[relation]
                    )
                    uncapped_recovered = sum(
                        _unit_recovered(unit, uncapped_result, uncapped_edges)
                        for unit in units[relation]
                    )
                    cap_fn = sum(
                        (not _unit_recovered(unit, capped_result, capped_edges))
                        and _unit_recovered(unit, uncapped_result, uncapped_edges)
                        for unit in units[relation]
                    )
                    totals[relation]["support"] += support
                    totals[relation]["recovered"] += recovered
                    totals[relation]["uncapped_recovered"] += uncapped_recovered
                    totals[relation]["cap_attributable_false_negatives"] += cap_fn
                    totals[relation]["oracle_sources"].update(
                        unit["oracle"] for unit in units[relation]
                    )
                    per_type[relation] = {
                        "support": support,
                        "recovered": recovered,
                        "recall": (recovered / support) if support else None,
                        "uncapped_recovered": uncapped_recovered,
                        "cap_attributable_false_negatives": cap_fn,
                    }
                unresolved = capped_result["stats"]["unresolved_reference_count"]
                unresolved_total += unresolved
                graph_rows.append({
                    "tier": tier,
                    "seed": entry["seed"],
                    "nodes": capped_result["stats"]["node_count"],
                    "directed_edges": capped_result["stats"]["directed_edge_count"],
                    "graph_hash": capped_result["stats"]["graph_hash"],
                    "unresolved_references": unresolved,
                    "relation_recall": per_type,
                })
                if file_index == 0:
                    save_graph(graph_samples / f"gen2_{tier.lower()}_sample.npz", capped_result)
                del ir, capped_result, uncapped_result
                gc.collect()

    typed: dict[str, Any] = {}
    micro_support = micro_recovered = micro_uncapped = micro_cap_fn = 0
    for relation in EDGE_TYPES:
        row = totals[relation]
        support, recovered = row["support"], row["recovered"]
        typed[relation] = {
            "support": support,
            "recovered": recovered,
            "recall": (recovered / support) if support else None,
            "uncapped_recovered": row["uncapped_recovered"],
            "cap_attributable_false_negatives": row["cap_attributable_false_negatives"],
            "oracle_sources": dict(sorted(row["oracle_sources"].items())),
        }
        micro_support += support
        micro_recovered += recovered
        micro_uncapped += row["uncapped_recovered"]
        micro_cap_fn += row["cap_attributable_false_negatives"]
    return {
        "schema": RECALL_SCHEMA,
        "generator": str(gen2),
        "generator_sha256": _sha256_file(gen2),
        "seed": seed,
        "n_per_tier": n_per_tier,
        "drawing_count": len(graph_rows),
        "config": config.canonical(),
        "config_hash": config.digest(),
        "uncapped_comparison_config_hash": uncapped.digest(),
        "relation_types": typed,
        "micro": {
            "support": micro_support,
            "recovered": micro_recovered,
            "recall": (micro_recovered / micro_support) if micro_support else None,
            "uncapped_recovered": micro_uncapped,
            "cap_attributable_false_negatives": micro_cap_fn,
        },
        "unresolved_required_reference_count": unresolved_total,
        "elapsed_seconds": time.perf_counter() - started,
        "graphs": graph_rows,
        "truth_boundary_note": (
            "wall parallel/intersection/collinearity/opening proximity units derive from "
            "gen2 wall/opening ledger; containment and instancing units derive from the "
            "read-only DXF entity/INSERT structure because wall.v1 has no explicit relation table"
        ),
    }


# ---------------------------------------------------------------------------
# CubiCasa val full-volume and staged-real envelope audit
# ---------------------------------------------------------------------------


def _audit_record(
    source_kind: str,
    source_ref: str,
    result: dict[str, Any],
    memory: dict[str, int | None],
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stats = result["stats"]
    record = {
        "source_kind": source_kind,
        "source_ref": source_ref,
        "status": stats["status"],
        "node_count": stats["node_count"],
        "directed_edge_count": stats["directed_edge_count"],
        "edge_node_ratio": stats["edge_node_ratio"],
        "fanout_quantiles": stats["fanout_quantiles"],
        "relation_directed_edge_counts": stats["relation_directed_edge_counts"],
        "relation_fanout_quantiles": stats["relation_fanout_quantiles"],
        "relation_cap_drops": stats["relation_cap_drops"],
        "candidate_scan": stats["candidate_scan"],
        "build_seconds": stats["build_seconds"],
        "graph_hash": stats["graph_hash"],
        "unresolved_reference_count": stats["unresolved_reference_count"],
        "shard_count": stats["shard_count"],
        "maximum_shard_core_nodes": stats["maximum_shard_core_nodes"],
        "maximum_shard_nodes_with_halo": stats["maximum_shard_nodes_with_halo"],
        "maximum_shard_directed_edges": stats["maximum_shard_directed_edges"],
        **memory,
    }
    if extra:
        record.update(extra)
    return record


def _aggregate_records(
    records: list[dict[str, Any]], fanouts: list[np.ndarray]
) -> dict[str, Any]:
    if not records:
        return {
            "drawing_count": 0,
            "status_counts": {},
            "node_count_total": 0,
            "directed_edge_count_total": 0,
            "edge_node_ratio_quantiles": _quantiles([]),
            "pooled_fanout_quantiles": _quantiles([]),
            "working_set_peak_bytes_quantiles": _quantiles([]),
            "build_seconds_total": 0.0,
            "unresolved_reference_count_total": 0,
        }
    pooled = np.concatenate(fanouts) if fanouts else np.zeros(0, dtype=np.int32)
    relation_totals = {
        name: sum(int(row["relation_directed_edge_counts"].get(name, 0)) for row in records)
        for name in EDGE_TYPES
    }
    max_nodes = max(records, key=lambda row: row["node_count"])
    max_edges = max(records, key=lambda row: row["directed_edge_count"])
    max_shard = max(records, key=lambda row: row["maximum_shard_nodes_with_halo"])
    return {
        "drawing_count": len(records),
        "status_counts": dict(sorted(Counter(row["status"] for row in records).items())),
        "node_count_total": sum(int(row["node_count"]) for row in records),
        "directed_edge_count_total": sum(int(row["directed_edge_count"]) for row in records),
        "relation_directed_edge_count_totals": relation_totals,
        "node_count_quantiles": _quantiles([row["node_count"] for row in records]),
        "directed_edge_count_quantiles": _quantiles(
            [row["directed_edge_count"] for row in records]
        ),
        "edge_node_ratio_quantiles": _quantiles(
            [row["edge_node_ratio"] for row in records]
        ),
        "pooled_fanout_quantiles": _quantiles(pooled),
        "working_set_peak_bytes_quantiles": _quantiles([
            row["working_set_peak_bytes"]
            for row in records if row["working_set_peak_bytes"] is not None
        ]),
        "working_set_peak_delta_bytes_quantiles": _quantiles([
            row["working_set_peak_delta_bytes"]
            for row in records if row["working_set_peak_delta_bytes"] is not None
        ]),
        "build_seconds_quantiles": _quantiles([row["build_seconds"] for row in records]),
        "build_seconds_total": sum(float(row["build_seconds"]) for row in records),
        "unresolved_reference_count_total": sum(
            int(row["unresolved_reference_count"]) for row in records
        ),
        "maximum_source_nodes": {
            "source_ref": max_nodes["source_ref"], "value": max_nodes["node_count"]
        },
        "maximum_source_directed_edges": {
            "source_ref": max_edges["source_ref"],
            "value": max_edges["directed_edge_count"],
        },
        "maximum_shard_nodes_with_halo": {
            "source_ref": max_shard["source_ref"],
            "value": max_shard["maximum_shard_nodes_with_halo"],
            "core_nodes": max_shard["maximum_shard_core_nodes"],
            "directed_edges": max_shard["maximum_shard_directed_edges"],
        },
    }


def audit_envelope(
    repo: Path,
    graph_samples: Path,
    config: GraphConfig,
    *,
    cubicasa_limit: int = 0,
    real_top: int = 3,
) -> dict[str, Any]:
    started = time.perf_counter()
    val_dir = repo / "runs" / "e2_ext_cubicasa" / "ir" / "val"
    val_files = sorted(val_dir.glob("*.segir.json"))
    discovered_val_count = len(val_files)
    if cubicasa_limit > 0:
        val_files = val_files[:cubicasa_limit]
    if len(val_files) < 50:
        raise RuntimeError(f"CubiCasa val coverage requires >=50 drawings; found {len(val_files)}")

    val_records: list[dict[str, Any]] = []
    val_fanouts: list[np.ndarray] = []
    pilot_count = min(10, len(val_files))
    pilot_started = time.perf_counter()
    pilot_nodes = pilot_edges = 0
    for index, path in enumerate(val_files):
        collect = index < 3
        with PeakMemorySampler() as memory_sampler:
            ir = load_segir(path)
            result = build_graph(ir, config, collect_edges=collect)
        memory = memory_sampler.numbers()
        record = _audit_record(
            "cubicasa_val", f"val/{path.name}", result, memory,
            extra={"file_bytes": path.stat().st_size},
        )
        val_records.append(record)
        val_fanouts.append(result["fanout"].copy())
        if index < pilot_count:
            pilot_nodes += result["stats"]["node_count"]
            pilot_edges += result["stats"]["directed_edge_count"]
        if collect:
            save_graph(graph_samples / f"cubicasa_val_sample_{index + 1:03d}.npz", result)
        if index + 1 == pilot_count:
            pilot_seconds = time.perf_counter() - pilot_started
            print(
                f"CUBICASA_PILOT drawings={pilot_count} nodes={pilot_nodes} "
                f"edges={pilot_edges} seconds={pilot_seconds:.3f} "
                f"nodes_per_second={pilot_nodes / max(pilot_seconds, 1e-9):.1f}",
                flush=True,
            )
        if (index + 1) % 25 == 0 or index + 1 == len(val_files):
            print(
                f"CUBICASA_PROGRESS {index + 1}/{len(val_files)} "
                f"last_nodes={record['node_count']} last_edges={record['directed_edge_count']}",
                flush=True,
            )
        del ir, result
        if (index + 1) % 25 == 0:
            gc.collect()
    pilot_seconds = time.perf_counter() - pilot_started if pilot_count == len(val_files) else (
        sum(float(row["build_seconds"]) for row in val_records[:pilot_count])
    )
    # The build-only and wall-clock pilot numbers are both retained.  The former
    # is the throughput estimator used before proceeding through the remaining val set.
    pilot_build_seconds = sum(float(row["build_seconds"]) for row in val_records[:pilot_count])
    throughput = {
        "pilot_drawings": pilot_count,
        "pilot_nodes": pilot_nodes,
        "pilot_directed_edges": pilot_edges,
        "pilot_build_seconds": pilot_build_seconds,
        "pilot_nodes_per_build_second": pilot_nodes / max(pilot_build_seconds, 1e-9),
        "pilot_edges_per_build_second": pilot_edges / max(pilot_build_seconds, 1e-9),
        "full_val_started_after_pilot_drawings": pilot_count,
    }

    real_records: list[dict[str, Any]] = []
    real_fanouts: list[np.ndarray] = []
    real_boundary: dict[str, Any]
    census_path = repo / "reports" / "e2" / "s4" / "real_defs_v1.json"
    if real_top <= 0:
        real_boundary = {"status": "NOT_REQUESTED", "definitions_processed": 0}
    elif not census_path.is_file():
        real_boundary = {
            "status": "BLOCKED_DATA", "reason": "real definition census missing",
            "census_path": str(census_path), "definitions_processed": 0,
        }
    else:
        census = json.loads(census_path.read_text(encoding="utf-8-sig"))
        staged_relative = Path(str(census.get("summary", {}).get("dxf", "")))
        staged_path = (repo / staged_relative).resolve()
        runs_root = (repo / "runs").resolve()
        safe_staged = staged_path.is_relative_to(runs_root) and staged_path.suffix.lower() == ".dxf"
        if not safe_staged or not staged_path.is_file():
            real_boundary = {
                "status": "BLOCKED_DATA",
                "reason": "staged DXF unavailable or outside repo/runs boundary",
                "staged_path": str(staged_path),
                "definitions_processed": 0,
            }
        elif ezdxf is None:
            real_boundary = {
                "status": "BLOCKED_DATA", "reason": "ezdxf unavailable",
                "staged_path": str(staged_path), "definitions_processed": 0,
            }
        else:
            ranked = sorted(
                census.get("rows") or [],
                key=lambda row: int(row.get("n_segments") or 0),
                reverse=True,
            )[:real_top]
            with PeakMemorySampler() as staged_sampler:
                doc = ezdxf.readfile(staged_path)
                for rank, row in enumerate(ranked, 1):
                    block_name = str(row.get("def"))
                    print(
                        f"REAL_DEF_START rank={rank}/{len(ranked)} "
                        f"expected_segments={int(row.get('n_segments') or 0)}",
                        flush=True,
                    )
                    with PeakMemorySampler() as memory_sampler:
                        ir = segir_from_block(doc, block_name)
                        result = build_graph(ir, config, collect_edges=False)
                    memory = memory_sampler.numbers()
                    actual = result["stats"]["input_segment_count"]
                    record = _audit_record(
                        "staged_real_definition", f"staged_real_rank_{rank:03d}",
                        result, memory,
                        extra={
                            "definition_name_sha256": hashlib.sha256(
                                block_name.encode("utf-8")
                            ).hexdigest(),
                            "expected_segment_count_from_readonly_census": int(
                                row.get("n_segments") or 0
                            ),
                            "actual_extracted_segment_count": actual,
                            "census_count_delta": actual - int(row.get("n_segments") or 0),
                        },
                    )
                    real_records.append(record)
                    real_fanouts.append(result["fanout"].copy())
                    print(
                        f"REAL_DEF_DONE rank={rank}/{len(ranked)} nodes={record['node_count']} "
                        f"edges={record['directed_edge_count']} "
                        f"seconds={record['build_seconds']:.3f}",
                        flush=True,
                    )
                    del ir, result
                    gc.collect()
            real_boundary = {
                "status": "MEASURED",
                "source_kind": "staged_dxf_only",
                "staged_path": str(staged_path),
                "staged_sha256": _sha256_file(staged_path),
                "definition_universe_in_readonly_census": len(census.get("rows") or []),
                "definitions_processed": len(real_records),
                "selection": "largest n_segments from complete readonly 384-definition census",
                "whole_staged_phase_memory": staged_sampler.numbers(),
            }

    val_aggregate = _aggregate_records(val_records, val_fanouts)
    real_aggregate = _aggregate_records(real_records, real_fanouts)
    combined_records = val_records + real_records
    combined_fanouts = val_fanouts + real_fanouts
    combined_aggregate = _aggregate_records(combined_records, combined_fanouts)

    edge_p95 = val_aggregate["directed_edge_count_quantiles"]["p95"]
    memory_p95 = val_aggregate["working_set_peak_bytes_quantiles"]["p95"]
    val_edge_exceed = sum(
        row["directed_edge_count"] > edge_p95 for row in val_records
    ) if edge_p95 is not None else 0
    val_memory_exceed = sum(
        row["working_set_peak_bytes"] is not None
        and memory_p95 is not None
        and row["working_set_peak_bytes"] > memory_p95
        for row in val_records
    )
    real_edge_exceed = sum(
        row["directed_edge_count"] > edge_p95 for row in real_records
    ) if edge_p95 is not None else 0
    real_memory_exceed = sum(
        row["working_set_peak_bytes"] is not None
        and memory_p95 is not None
        and row["working_set_peak_bytes"] > memory_p95
        for row in real_records
    )
    observed_peak = max(
        (int(row["working_set_peak_bytes"]) for row in combined_records
         if row["working_set_peak_bytes"] is not None),
        default=0,
    )
    return {
        "schema": ENVELOPE_SCHEMA,
        "generated_at": datetime.now().astimezone().isoformat(),
        "config": config.canonical(),
        "config_hash": config.digest(),
        "data_boundary": {
            "cubicasa_partition_accessed": "val",
            "cubicasa_test_files_accessed": 0,
            "cubicasa_val_discovered": discovered_val_count,
            "cubicasa_val_processed": len(val_records),
            "staged_real": real_boundary,
            "original_cad_files_accessed": 0,
        },
        "throughput_pilot": throughput,
        "aggregates": {
            "cubicasa_val": val_aggregate,
            "staged_real_definitions": real_aggregate,
            "combined": combined_aggregate,
        },
        "production_p95_measurement_basis": {
            "preexisting_frozen_p95_reference_available": False,
            "reference_source": "current full CubiCasa val empirical p95",
            "directed_edge_count_p95": edge_p95,
            "working_set_peak_bytes_p95": memory_p95,
            "cubicasa_edge_exceedance_count": val_edge_exceed,
            "cubicasa_edge_exceedance_rate": val_edge_exceed / len(val_records),
            "cubicasa_memory_exceedance_count": val_memory_exceed,
            "cubicasa_memory_exceedance_rate": val_memory_exceed / len(val_records),
            "staged_real_edge_exceedance_count": real_edge_exceed,
            "staged_real_edge_exceedance_rate": (
                real_edge_exceed / len(real_records) if real_records else None
            ),
            "staged_real_memory_exceedance_count": real_memory_exceed,
            "staged_real_memory_exceedance_rate": (
                real_memory_exceed / len(real_records) if real_records else None
            ),
        },
        "ram_numbers": {
            "hard_band_bytes": RAM_BAND_BYTES,
            "observed_process_working_set_peak_bytes": observed_peak,
            "observed_to_band_fraction": observed_peak / RAM_BAND_BYTES,
        },
        "elapsed_seconds": time.perf_counter() - started,
        "records": combined_records,
    }


def render_report(
    path: Path,
    selftest_lines: list[str],
    selftest_details: dict[str, Any],
    recall: dict[str, Any],
    envelope: dict[str, Any],
) -> None:
    recall_numbers = {
        key: recall[key]
        for key in (
            "schema", "seed", "n_per_tier", "drawing_count", "config_hash",
            "relation_types", "micro", "unresolved_required_reference_count",
            "elapsed_seconds", "graphs", "truth_boundary_note",
        )
    }
    envelope_numbers = {
        key: envelope[key]
        for key in (
            "schema", "config_hash", "data_boundary", "throughput_pilot",
            "aggregates", "production_p95_measurement_basis", "ram_numbers",
            "elapsed_seconds",
        )
    }
    unresolved: list[str] = []
    if recall["unresolved_required_reference_count"]:
        unresolved.append(
            f"Synthetic unresolved-reference count: {recall['unresolved_required_reference_count']}."
        )
    else:
        unresolved.append("Synthetic unresolved-reference count measured as 0.")
    real_status = envelope["data_boundary"]["staged_real"]["status"]
    if real_status == "BLOCKED_DATA":
        unresolved.append(
            "Staged-real stress metrics are BLOCKED_DATA: "
            + str(envelope["data_boundary"]["staged_real"].get("reason"))
        )
    else:
        deltas = [
            row.get("census_count_delta")
            for row in envelope["records"]
            if row["source_kind"] == "staged_real_definition"
        ]
        unresolved.append(f"Staged-real census/extraction count deltas: {deltas}.")
    unresolved.append(
        "The source dossier supplies no previously frozen numeric production p95 edge/memory "
        "reference. This cell records the full CubiCasa-val empirical p95 and exceedance rates "
        "as a freeze basis; it emits no compliance verdict."
    )
    unresolved.append(
        "gen2 wall.v1 has no explicit relation-pair table. Wall/opening relation units are "
        "derived from its wall axes, wall handles, and opening wall_id; containment/instancing "
        "units are independently read from DXF entity/INSERT structure and are labeled as such."
    )

    text = [
        "# Graph Builder Cell E1 Report",
        "",
        "## Scope and data boundary",
        "",
        "This run built a segment-node typed Graph IR, audited fixed-seed gen2 relation "
        "recovery, processed the complete CubiCasa validation SEG-IR set after a 10-drawing "
        "throughput pilot, and stress-built the largest staged real definitions selected from "
        "the read-only 384-definition census. No CubiCasa test file, original CAD file, Git "
        "surface, or repository file was read for output mutation.",
        "",
        "## Design",
        "",
        "- Nodes are non-degenerate SEG-IR segments. Source handles are preserved only in the "
        "`node_handle` NPZ sidecar.",
        "- Numeric features contain geometry type, normalized length/bbox/midpoint/orientation, "
        "curvature/closed state, topology counts, and block depth. Identifier and name fields "
        "are absent.",
        "- Directed edge types are `parallel_band`, `intersection_junction`, `proximity`, "
        "`collinearity`, `containment`, and `instancing`. Multiple types may coexist per pair.",
        "- Spatial lookup uses a segment-cell index. Capped relation neighbors are ranked by "
        "geometry metrics and geometry SHA-256; exact geometry ties are retained and counted.",
        "- Large graphs stream source-owned edge rows in canonical geometry order. Each shard "
        "records core nodes, halo targets, and directed edges without materializing an unbounded "
        "whole-graph edge table.",
        "- NPZ serialization uses only numeric and Unicode arrays (no pickle). JSON sidecars "
        "carry schema, config, graph hash, feature names, edge mappings, and audit statistics.",
        "",
        "### Frozen graph config",
        "",
        "```json",
        json.dumps(recall["config"], ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "### Feature allowlist",
        "",
        "```json",
        json.dumps(list(FEATURE_NAMES), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Selftest transcript",
        "",
        "```text",
        *selftest_lines,
        "```",
        "",
        "Selftest counters:",
        "",
        "```json",
        json.dumps(selftest_details, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Relation recall numbers",
        "",
        "```json",
        json.dumps(_json_ready(recall_numbers), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Edge/RAM envelope numbers",
        "",
        "```json",
        json.dumps(_json_ready(envelope_numbers), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "Per-drawing numeric records are preserved without hand-copying in "
        "`envelope_numbers.json`; per-synthetic-drawing recall rows are in "
        "`recall_numbers.json`.",
        "",
        "## Unresolved and interpretation boundaries",
        "",
        *[f"- {item}" for item in unresolved],
        "",
        "No preregistration threshold judgment is emitted by this cell.",
        "",
        "CELL_COMPLETE: graph_builder",
    ]
    path.write_text("\n".join(text) + "\n", encoding="utf-8")


def run_cell(
    repo: Path,
    outdir: Path,
    *,
    cubicasa_limit: int = 0,
    real_top: int = 3,
    synthetic_n_per_tier: int = 3,
) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    graph_samples = outdir / "graphs_sample"
    graph_samples.mkdir(parents=True, exist_ok=True)
    config = GraphConfig()
    ok, selftest_lines, selftest_details = run_selftest()
    print("\n".join(selftest_lines), flush=True)
    if not ok:
        raise RuntimeError("selftest reported one or more implementation errors")
    print("SYNTHETIC_RECALL_START", flush=True)
    recall = audit_synthetic_recall(
        repo, outdir, graph_samples, config, n_per_tier=synthetic_n_per_tier
    )
    write_json(outdir / "recall_numbers.json", recall)
    print(
        f"SYNTHETIC_RECALL_DONE drawings={recall['drawing_count']} "
        f"support={recall['micro']['support']} recovered={recall['micro']['recovered']}",
        flush=True,
    )
    print("ENVELOPE_AUDIT_START", flush=True)
    envelope = audit_envelope(
        repo, graph_samples, config,
        cubicasa_limit=cubicasa_limit,
        real_top=real_top,
    )
    write_json(outdir / "envelope_numbers.json", envelope)
    render_report(outdir / "REPORT.md", selftest_lines, selftest_details, recall, envelope)
    print(
        f"CELL_ARTIFACTS_WRITTEN outdir={outdir} "
        f"val={envelope['data_boundary']['cubicasa_val_processed']} "
        f"real={envelope['data_boundary']['staged_real'].get('definitions_processed', 0)}",
        flush=True,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--selftest", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    build = subparsers.add_parser("build", help="build one SEG-IR graph")
    build.add_argument("--segir", required=True)
    build.add_argument("--out", required=True)
    run = subparsers.add_parser("run-cell", help="execute the complete Cell E1 packet")
    run.add_argument("--repo", default=str(DEFAULT_REPO))
    run.add_argument("--outdir", default=str(DEFAULT_CELL))
    run.add_argument("--cubicasa-limit", type=int, default=0)
    run.add_argument("--real-top", type=int, default=3)
    run.add_argument("--synthetic-n-per-tier", type=int, default=3)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.selftest:
        ok, lines, _details = run_selftest()
        print("\n".join(lines))
        return 0 if ok else 1
    if args.command == "build":
        ir = load_segir(Path(args.segir))
        result = build_graph(ir, collect_edges=True)
        save_graph(Path(args.out), result)
        print(json.dumps(_json_ready(result["stats"]), ensure_ascii=False, indent=2))
        return 0
    if args.command == "run-cell":
        return run_cell(
            Path(args.repo), Path(args.outdir),
            cubicasa_limit=args.cubicasa_limit,
            real_top=args.real_top,
            synthetic_n_per_tier=args.synthetic_n_per_tier,
        )
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
