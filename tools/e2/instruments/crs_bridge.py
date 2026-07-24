#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Raster pixel <-> SEG-IR segment-handle CRS bridge.

The public API is :class:`RasterHandleBridge`.  Geometry is always retained
in the source SEG-IR; raster selections only select or score existing handles.
Overlapping segments are rasterized independently, so a pixel may keep more
than one ``(handle, coverage)`` provenance tuple.

Coordinate convention
---------------------
Affine transforms map source/SVG coordinates to pixel-edge coordinates.  The
centre of array pixel ``(row=y, column=x)`` is therefore ``(x+0.5, y+0.5)``.
Boxes use half-open bounds ``[x0,x1) x [y0,y1)``.  Masks have shape ``(H,W)``.

Only stdlib, NumPy, and Pillow are used.  Run ``python crs_bridge.py
--selftest`` for the required deterministic test battery.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - exercised only in an invalid runtime
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]


PIXEL_CENTER_CONVENTION = "array[y,x] center is (x+0.5,y+0.5)"
DEFAULT_DATA_ROOT = Path(
    r"D:\dev\_ariadne\huggingface\datasets\cubicasa5k\cubicasa5k\colorful"
)
DEFAULT_SMOKE_IDS = ("10052", "10062", "10106")


def _finite(value: float, name: str) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return value


@dataclass(frozen=True)
class AffineTransform:
    """Invertible 3x3 homogeneous source-to-pixel affine transform."""

    matrix: np.ndarray
    provenance: str = "explicit"

    def __post_init__(self) -> None:
        matrix = np.asarray(self.matrix, dtype=np.float64)
        if matrix.shape != (3, 3):
            raise ValueError(f"affine matrix must be 3x3, got {matrix.shape}")
        if not np.all(np.isfinite(matrix)):
            raise ValueError("affine matrix contains a non-finite value")
        if not np.allclose(matrix[2], (0.0, 0.0, 1.0), atol=1e-12):
            raise ValueError("only 2-D affine matrices with final row [0,0,1] are supported")
        if abs(float(np.linalg.det(matrix))) <= 1e-15:
            raise ValueError("affine matrix is singular")
        object.__setattr__(self, "matrix", matrix.copy())

    @classmethod
    def identity(cls, provenance: str = "identity") -> "AffineTransform":
        return cls(np.eye(3, dtype=np.float64), provenance)

    @classmethod
    def from_scale_offset(
        cls,
        scale_x: float,
        scale_y: float | None = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        provenance: str = "explicit_scale_offset",
    ) -> "AffineTransform":
        sx = _finite(scale_x, "scale_x")
        sy = sx if scale_y is None else _finite(scale_y, "scale_y")
        ox = _finite(offset_x, "offset_x")
        oy = _finite(offset_y, "offset_y")
        return cls(np.array(((sx, 0.0, ox), (0.0, sy, oy), (0.0, 0.0, 1.0))), provenance)

    @classmethod
    def from_viewbox(
        cls,
        viewbox: Sequence[float],
        image_size: Sequence[int],
    ) -> "AffineTransform":
        """Dimension-only fallback: stretch an SVG viewBox onto the full image.

        This is an estimate, not a claim that an SVG viewport occupies the full
        PNG.  :func:`smoke_cubicasa_sample` audits that assumption against raw
        image edges without consulting a wall mask or SVG class label.
        """

        if len(viewbox) != 4 or len(image_size) != 2:
            raise ValueError("viewbox must have 4 values and image_size must be (W,H)")
        min_x, min_y, width, height = map(float, viewbox)
        image_w, image_h = map(int, image_size)
        if width <= 0.0 or height <= 0.0:
            raise ValueError(f"degenerate SVG viewBox: {tuple(viewbox)!r}")
        if image_w <= 0 or image_h <= 0:
            raise ValueError(f"degenerate image size: {tuple(image_size)!r}")
        sx = image_w / width
        sy = image_h / height
        return cls.from_scale_offset(
            sx,
            sy,
            -min_x * sx,
            -min_y * sy,
            provenance="estimated_image_size_vs_svg_viewBox",
        )

    def apply(self, points: Sequence[Sequence[float]] | np.ndarray) -> np.ndarray:
        pts = np.asarray(points, dtype=np.float64)
        if pts.ndim == 1:
            pts = pts.reshape(1, -1)
        if pts.ndim != 2 or pts.shape[1] != 2:
            raise ValueError("points must have shape (N,2)")
        homogeneous = np.column_stack((pts, np.ones(len(pts), dtype=np.float64)))
        return (homogeneous @ self.matrix.T)[:, :2]

    def inverse(self) -> "AffineTransform":
        return AffineTransform(np.linalg.inv(self.matrix), f"inverse({self.provenance})")

    def roundtrip_error(self, points: Sequence[Sequence[float]] | np.ndarray) -> float:
        pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
        if len(pts) == 0:
            return 0.0
        returned = self.inverse().apply(self.apply(pts))
        return float(np.max(np.linalg.norm(returned - pts, axis=1)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "matrix": self.matrix.tolist(),
            "provenance": self.provenance,
            "pixel_center_convention": PIXEL_CENTER_CONVENTION,
        }


@dataclass(frozen=True)
class Segment:
    handle: str
    p1: tuple[float, float]
    p2: tuple[float, float]
    visible: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.handle, str) or not self.handle:
            raise ValueError("segment handle must be a non-empty string")
        p1 = tuple(_finite(v, "segment coordinate") for v in self.p1)
        p2 = tuple(_finite(v, "segment coordinate") for v in self.p2)
        if len(p1) != 2 or len(p2) != 2:
            raise ValueError("segment endpoints must each have 2 values")
        if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) <= 1e-12:
            raise ValueError(f"zero-length segment is not bridgeable: {self.handle}")
        object.__setattr__(self, "p1", p1)
        object.__setattr__(self, "p2", p2)


@dataclass(frozen=True)
class SparseSupport:
    """Sparse per-handle coverage; rows/columns index a mask array."""

    rows: np.ndarray
    cols: np.ndarray
    coverage: np.ndarray

    @property
    def n_pixels(self) -> int:
        return int(len(self.coverage))

    @property
    def coverage_sum(self) -> float:
        return float(np.sum(self.coverage, dtype=np.float64))


@dataclass(frozen=True)
class HandleMatch:
    handle: str
    score: float | None
    selected: bool
    raster_missing: bool
    support_pixels: int
    support_coverage: float
    selected_coverage: float
    touches_canvas_boundary: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "handle": self.handle,
            "score": self.score,
            "selected": self.selected,
            "raster_missing": self.raster_missing,
            "support_pixels": self.support_pixels,
            "support_coverage": self.support_coverage,
            "selected_coverage": self.selected_coverage,
            "touches_canvas_boundary": self.touches_canvas_boundary,
        }


def load_seg_ir(source: str | os.PathLike[str] | Mapping[str, Any]) -> list[Segment]:
    """Load the converter's ``segments[{handle,pts}]`` SEG-IR contract."""

    if isinstance(source, Mapping):
        payload = source
    else:
        with open(source, "r", encoding="utf-8") as stream:
            payload = json.load(stream)
    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list):
        raise ValueError("SEG-IR must contain a list field named 'segments'")
    result: list[Segment] = []
    for index, raw in enumerate(raw_segments):
        try:
            pts = raw["pts"]
            result.append(Segment(str(raw["handle"]), tuple(pts[0]), tuple(pts[1])))
        except (KeyError, TypeError, IndexError, ValueError) as exc:
            raise ValueError(f"invalid SEG-IR segment at index {index}: {exc}") from exc
    _assert_unique_handles(result)
    return result


def _assert_unique_handles(segments: Sequence[Segment]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for segment in segments:
        if segment.handle in seen:
            duplicates.add(segment.handle)
        seen.add(segment.handle)
    if duplicates:
        raise ValueError(f"duplicate handles are not allowed: {sorted(duplicates)!r}")


def _point_segment_distance(
    x: np.ndarray,
    y: np.ndarray,
    p1: np.ndarray,
    p2: np.ndarray,
) -> np.ndarray:
    dx = float(p2[0] - p1[0])
    dy = float(p2[1] - p1[1])
    denom = dx * dx + dy * dy
    if denom <= 1e-24:
        return np.hypot(x - p1[0], y - p1[1])
    t = np.clip(((x - p1[0]) * dx + (y - p1[1]) * dy) / denom, 0.0, 1.0)
    return np.hypot(x - (p1[0] + t * dx), y - (p1[1] + t * dy))


class RasterHandleBridge:
    """Bidirectional mapping between raster selections and SEG-IR handles."""

    def __init__(
        self,
        segments: Sequence[Segment],
        image_size: Sequence[int],
        transform: AffineTransform,
        line_width_px: float = 1.0,
        supersample: int = 1,
    ) -> None:
        self.segments = tuple(segments)
        _assert_unique_handles(self.segments)
        self.by_handle = {segment.handle: segment for segment in self.segments}
        if len(image_size) != 2:
            raise ValueError("image_size must be (W,H)")
        self.width, self.height = map(int, image_size)
        if self.width <= 0 or self.height <= 0:
            raise ValueError("image dimensions must be positive")
        self.transform = transform
        self.line_width_px = _finite(line_width_px, "line_width_px")
        if self.line_width_px <= 0.0:
            raise ValueError("line_width_px must be positive")
        self.supersample = int(supersample)
        if self.supersample < 1 or self.supersample > 16:
            raise ValueError("supersample must be in [1,16]")
        self._support_cache: dict[str, SparseSupport] = {}

    @classmethod
    def from_known_scale_offset(
        cls,
        segments: Sequence[Segment],
        image_size: Sequence[int],
        scale_x: float,
        scale_y: float | None = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        **kwargs: Any,
    ) -> "RasterHandleBridge":
        return cls(
            segments,
            image_size,
            AffineTransform.from_scale_offset(scale_x, scale_y, offset_x, offset_y),
            **kwargs,
        )

    @classmethod
    def from_viewbox_estimate(
        cls,
        segments: Sequence[Segment],
        image_size: Sequence[int],
        viewbox: Sequence[float],
        **kwargs: Any,
    ) -> "RasterHandleBridge":
        return cls(segments, image_size, AffineTransform.from_viewbox(viewbox, image_size), **kwargs)

    def _pixel_segment(self, segment: Segment) -> tuple[np.ndarray, np.ndarray]:
        transformed = self.transform.apply((segment.p1, segment.p2))
        return transformed[0], transformed[1]

    def support(self, handle: str) -> SparseSupport:
        """Return sparse fractional coverage for one handle.

        Each handle is evaluated independently.  Consequently coincident or
        crossing handles remain as separate provenance tuples.
        """

        if handle in self._support_cache:
            return self._support_cache[handle]
        if handle not in self.by_handle:
            raise KeyError(f"unknown handle: {handle}")
        p1, p2 = self._pixel_segment(self.by_handle[handle])
        radius = self.line_width_px / 2.0
        min_x = max(0, int(math.floor(min(p1[0], p2[0]) - radius - 0.5)))
        max_x = min(self.width - 1, int(math.ceil(max(p1[0], p2[0]) + radius - 0.5)))
        min_y = max(0, int(math.floor(min(p1[1], p2[1]) - radius - 0.5)))
        max_y = min(self.height - 1, int(math.ceil(max(p1[1], p2[1]) + radius - 0.5)))
        if max_x < min_x or max_y < min_y:
            result = SparseSupport(
                np.empty(0, dtype=np.int32),
                np.empty(0, dtype=np.int32),
                np.empty(0, dtype=np.float32),
            )
            self._support_cache[handle] = result
            return result

        rows, cols = np.mgrid[min_y : max_y + 1, min_x : max_x + 1]
        coverage = np.zeros(rows.shape, dtype=np.float64)
        offsets = (np.arange(self.supersample, dtype=np.float64) + 0.5) / self.supersample
        for oy in offsets:
            for ox in offsets:
                distances = _point_segment_distance(cols + ox, rows + oy, p1, p2)
                coverage += distances <= radius + 1e-12
        coverage /= float(self.supersample * self.supersample)
        keep = coverage > 0.0
        result = SparseSupport(
            rows[keep].astype(np.int32, copy=False),
            cols[keep].astype(np.int32, copy=False),
            coverage[keep].astype(np.float32, copy=False),
        )
        self._support_cache[handle] = result
        return result

    def provenance(self, handles: Iterable[str] | None = None) -> dict[int, list[tuple[str, float]]]:
        """Return a multi-hit sparse map keyed by linear pixel index."""

        chosen = tuple(self.by_handle) if handles is None else tuple(handles)
        result: dict[int, list[tuple[str, float]]] = {}
        for handle in chosen:
            support = self.support(handle)
            for row, col, coverage in zip(support.rows, support.cols, support.coverage):
                key = int(row) * self.width + int(col)
                result.setdefault(key, []).append((handle, float(coverage)))
        return result

    def handles_to_mask(self, handles: Iterable[str], combine: str = "max") -> np.ndarray:
        """Rasterize existing handles to a floating coverage mask."""

        result = np.zeros((self.height, self.width), dtype=np.float32)
        for handle in handles:
            support = self.support(handle)
            if combine == "max":
                result[support.rows, support.cols] = np.maximum(
                    result[support.rows, support.cols], support.coverage
                )
            elif combine == "sum":
                result[support.rows, support.cols] += support.coverage
            else:
                raise ValueError("combine must be 'max' or 'sum'")
        return result

    def handles_to_polylines(self, handles: Iterable[str]) -> dict[str, list[list[float]]]:
        result: dict[str, list[list[float]]] = {}
        for handle in handles:
            if handle not in self.by_handle:
                raise KeyError(f"unknown handle: {handle}")
            p1, p2 = self._pixel_segment(self.by_handle[handle])
            result[handle] = [p1.tolist(), p2.tolist()]
        return result

    def handles_to_boxes(self, handles: Iterable[str]) -> dict[str, list[float] | None]:
        result: dict[str, list[float] | None] = {}
        for handle in handles:
            support = self.support(handle)
            if support.n_pixels == 0:
                result[handle] = None
            else:
                result[handle] = [
                    float(np.min(support.cols)),
                    float(np.min(support.rows)),
                    float(np.max(support.cols) + 1),
                    float(np.max(support.rows) + 1),
                ]
        return result

    def mask_to_handles(
        self,
        mask: np.ndarray,
        score_threshold: float = 0.5,
        handles: Iterable[str] | None = None,
    ) -> list[HandleMatch]:
        """Score raster mask coverage on every source handle.

        ``score`` is the support-weighted mean mask value.  Handles clipped
        completely outside the canvas have ``score=None`` and
        ``raster_missing=True``; no arbitrary replacement probability is used.
        """

        array = np.asarray(mask, dtype=np.float64)
        if array.shape != (self.height, self.width):
            raise ValueError(
                f"mask shape must be {(self.height, self.width)}, got {array.shape}"
            )
        if not np.all(np.isfinite(array)):
            raise ValueError("mask contains a non-finite value")
        array = np.clip(array, 0.0, 1.0)
        threshold = _finite(score_threshold, "score_threshold")
        if threshold < 0.0 or threshold > 1.0:
            raise ValueError("score_threshold must be in [0,1]")
        chosen = tuple(self.by_handle) if handles is None else tuple(handles)
        matches: list[HandleMatch] = []
        for handle in chosen:
            support = self.support(handle)
            total = support.coverage_sum
            if total <= 0.0:
                matches.append(HandleMatch(handle, None, False, True, 0, 0.0, 0.0, False))
                continue
            selected_coverage = float(
                np.sum(array[support.rows, support.cols] * support.coverage, dtype=np.float64)
            )
            score = selected_coverage / total
            boundary = bool(
                np.any(support.rows == 0)
                or np.any(support.rows == self.height - 1)
                or np.any(support.cols == 0)
                or np.any(support.cols == self.width - 1)
            )
            matches.append(
                HandleMatch(
                    handle,
                    float(score),
                    bool(score >= threshold),
                    False,
                    support.n_pixels,
                    total,
                    selected_coverage,
                    boundary,
                )
            )
        return matches

    def box_to_handles(
        self, box: Sequence[float], score_threshold: float = 0.5
    ) -> list[HandleMatch]:
        return self.mask_to_handles(self.mask_from_box(box), score_threshold)

    def polygon_to_handles(
        self, polygon: Sequence[Sequence[float]], score_threshold: float = 0.5
    ) -> list[HandleMatch]:
        return self.mask_to_handles(self.mask_from_polygon(polygon), score_threshold)

    def mask_from_box(self, box: Sequence[float]) -> np.ndarray:
        if len(box) != 4:
            raise ValueError("box must be (x0,y0,x1,y1)")
        x0, y0, x1, y1 = map(float, box)
        if not all(math.isfinite(v) for v in (x0, y0, x1, y1)) or x1 <= x0 or y1 <= y0:
            raise ValueError(f"invalid half-open box: {tuple(box)!r}")
        mask = np.zeros((self.height, self.width), dtype=np.float32)
        ix0 = max(0, int(math.floor(x0)))
        iy0 = max(0, int(math.floor(y0)))
        ix1 = min(self.width, int(math.ceil(x1)))
        iy1 = min(self.height, int(math.ceil(y1)))
        if ix1 > ix0 and iy1 > iy0:
            mask[iy0:iy1, ix0:ix1] = 1.0
        return mask

    def mask_from_polygon(self, polygon: Sequence[Sequence[float]]) -> np.ndarray:
        if Image is None or ImageDraw is None:
            raise RuntimeError("Pillow is required for polygon rasterization")
        points = np.asarray(polygon, dtype=np.float64)
        if points.ndim != 2 or points.shape[0] < 3 or points.shape[1] != 2:
            raise ValueError("polygon must have shape (N>=3,2)")
        if not np.all(np.isfinite(points)):
            raise ValueError("polygon contains a non-finite coordinate")
        image = Image.new("L", (self.width, self.height), 0)
        ImageDraw.Draw(image).polygon([tuple(point) for point in points], fill=255)
        return np.asarray(image, dtype=np.float32) / 255.0


def parse_svg_viewbox(svg_path: str | os.PathLike[str]) -> tuple[float, float, float, float]:
    root = ET.parse(svg_path).getroot()
    raw = root.get("viewBox")
    if raw:
        values = [float(token) for token in raw.replace(",", " ").split()]
        if len(values) != 4:
            raise ValueError(f"invalid SVG viewBox: {raw!r}")
        viewbox = tuple(values)
    else:
        width = _parse_svg_length(root.get("width"))
        height = _parse_svg_length(root.get("height"))
        viewbox = (0.0, 0.0, width, height)
    if viewbox[2] <= 0.0 or viewbox[3] <= 0.0:
        raise ValueError(f"degenerate SVG viewBox: {viewbox!r}")
    return viewbox  # type: ignore[return-value]


_LENGTH_RE = re.compile(r"^\s*([-+0-9.eE]+)")


def _parse_svg_length(raw: str | None) -> float:
    if raw is None:
        raise ValueError("SVG has neither viewBox nor width/height")
    match = _LENGTH_RE.match(raw)
    if not match:
        raise ValueError(f"invalid SVG length: {raw!r}")
    return float(match.group(1))


_IDENT6 = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_TRANSFORM_RE = re.compile(r"(matrix|translate|scale|rotate)\s*\(([^)]*)\)")


def _matrix6_multiply(m: Sequence[float], n: Sequence[float]) -> tuple[float, ...]:
    a1, b1, c1, d1, e1, f1 = m
    a2, b2, c2, d2, e2, f2 = n
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _parse_svg_transform(raw: str) -> tuple[float, ...]:
    matrix: tuple[float, ...] = _IDENT6
    for kind, body in _TRANSFORM_RE.findall(raw or ""):
        values = [float(value) for value in body.replace(",", " ").split()]
        if kind == "matrix" and len(values) == 6:
            local = tuple(values)
        elif kind == "translate" and len(values) in (1, 2):
            local = (1.0, 0.0, 0.0, 1.0, values[0], values[1] if len(values) == 2 else 0.0)
        elif kind == "scale" and len(values) in (1, 2):
            local = (values[0], 0.0, 0.0, values[-1], 0.0, 0.0)
        elif kind == "rotate" and len(values) in (1, 3):
            radians = math.radians(values[0])
            cosine, sine = math.cos(radians), math.sin(radians)
            local = (cosine, sine, -sine, cosine, 0.0, 0.0)
            if len(values) == 3:
                cx, cy = values[1], values[2]
                local = _matrix6_multiply(
                    _matrix6_multiply((1.0, 0.0, 0.0, 1.0, cx, cy), local),
                    (1.0, 0.0, 0.0, 1.0, -cx, -cy),
                )
        else:
            continue
        matrix = _matrix6_multiply(matrix, local)
    return matrix


def _apply_matrix6(matrix: Sequence[float], point: Sequence[float]) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    x, y = point
    return (a * x + c * y + e, b * x + d * y + f)


def _svg_points(raw: str) -> list[tuple[float, float]]:
    try:
        values = [float(value) for value in raw.replace(",", " ").split()]
    except ValueError:
        return []
    if len(values) % 2:
        return []
    return list(zip(values[0::2], values[1::2]))


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _is_hidden(element: ET.Element, inherited: bool) -> bool:
    if inherited:
        return True
    style = (element.get("style") or "").replace(" ", "").lower()
    return (
        element.get("display", "").lower() == "none"
        or element.get("visibility", "").lower() == "hidden"
        or "display:none" in style
        or "visibility:hidden" in style
    )


def load_svg_segments(svg_path: str | os.PathLike[str]) -> list[Segment]:
    """Read the line/polygon/polyline subset used by ``cubicasa_ir.py``.

    Handles intentionally follow that converter's ``e{element}_s{edge}``
    convention.  Class labels are never read, joined, or returned.
    """

    root = ET.parse(svg_path).getroot()
    segments: list[Segment] = []
    element_index = 0

    def walk(element: ET.Element, matrix: Sequence[float], hidden: bool) -> None:
        nonlocal element_index
        transform = element.get("transform")
        if transform:
            matrix = _matrix6_multiply(matrix, _parse_svg_transform(transform))
        hidden = _is_hidden(element, hidden)
        tag = _local_name(element.tag)
        points: list[tuple[float, float]] | None = None
        closed = False
        if tag in ("polygon", "polyline"):
            points = _svg_points(element.get("points", ""))
            closed = tag == "polygon"
        elif tag == "line":
            try:
                points = [
                    (float(element.get("x1", "0")), float(element.get("y1", "0"))),
                    (float(element.get("x2", "0")), float(element.get("y2", "0"))),
                ]
            except ValueError:
                points = None
        if points and len(points) >= 2:
            element_index += 1
            transformed = [_apply_matrix6(matrix, point) for point in points]
            edge_count = len(transformed) if closed and len(transformed) >= 3 else len(transformed) - 1
            for edge_index in range(edge_count):
                p1 = transformed[edge_index]
                p2 = transformed[(edge_index + 1) % len(transformed)]
                if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) <= 1e-6:
                    continue
                segments.append(Segment(f"e{element_index}_s{edge_index}", p1, p2, not hidden))
        for child in element:
            walk(child, matrix, hidden)

    walk(root, _IDENT6, False)
    _assert_unique_handles(segments)
    return segments


def _scalar_distance(px: float, py: float, p1: Sequence[float], p2: Sequence[float]) -> float:
    """Independent scalar oracle used only by the synthetic audit."""

    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    denominator = dx * dx + dy * dy
    if denominator <= 1e-24:
        return math.hypot(px - p1[0], py - p1[1])
    projection = ((px - p1[0]) * dx + (py - p1[1]) * dy) / denominator
    projection = min(1.0, max(0.0, projection))
    return math.hypot(px - (p1[0] + projection * dx), py - (p1[1] + projection * dy))


def _oracle_support(bridge: RasterHandleBridge, handle: str) -> SparseSupport:
    """Slow scalar implementation independent of the vectorized production path."""

    p1, p2 = bridge._pixel_segment(bridge.by_handle[handle])
    radius = bridge.line_width_px / 2.0
    rows: list[int] = []
    cols: list[int] = []
    coverage: list[float] = []
    offsets = [(index + 0.5) / bridge.supersample for index in range(bridge.supersample)]
    for row in range(bridge.height):
        for col in range(bridge.width):
            hits = 0
            for oy in offsets:
                for ox in offsets:
                    if _scalar_distance(col + ox, row + oy, p1, p2) <= radius + 1e-12:
                        hits += 1
            if hits:
                rows.append(row)
                cols.append(col)
                coverage.append(hits / (bridge.supersample * bridge.supersample))
    return SparseSupport(
        np.asarray(rows, dtype=np.int32),
        np.asarray(cols, dtype=np.int32),
        np.asarray(coverage, dtype=np.float32),
    )


def _relation_tuples(
    supports: Mapping[str, SparseSupport], coverage_quantum: float = 1e-6
) -> set[tuple[int, int, str, int]]:
    result: set[tuple[int, int, str, int]] = set()
    for handle, support in supports.items():
        for row, col, coverage in zip(support.rows, support.cols, support.coverage):
            quantized = int(round(float(coverage) / coverage_quantum))
            result.add((int(row), int(col), handle, quantized))
    return result


def _set_metrics(truth: set[str], predicted: set[str]) -> dict[str, float]:
    true_positive = len(truth & predicted)
    precision = true_positive / len(predicted) if predicted else (1.0 if not truth else 0.0)
    recall = true_positive / len(truth) if truth else 1.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def diagnose_recovery(
    bridge: RasterHandleBridge,
    truth: set[str],
    matches: Sequence[HandleMatch],
    expected_transform: AffineTransform | None = None,
) -> dict[str, Any]:
    """Decompose failed recovery into the packet's three requested causes."""

    predicted = {match.handle for match in matches if match.selected}
    missed = truth - predicted
    extras = predicted - truth
    provenance = bridge.provenance()
    collision_handles: set[str] = set()
    collision_pixels = 0
    for entries in provenance.values():
        if len(entries) > 1:
            collision_pixels += 1
            collision_handles.update(handle for handle, _ in entries)
    boundary_handles = {
        match.handle for match in matches if match.touches_canvas_boundary or match.raster_missing
    }
    matrix_error = 0.0
    if expected_transform is not None:
        matrix_error = float(np.max(np.abs(bridge.transform.matrix - expected_transform.matrix)))
    return {
        "missed_handles": sorted(missed),
        "extra_handles": sorted(extras),
        "boundary_pixel": {
            "implicated_handles": sorted((missed | extras) & boundary_handles),
            "all_boundary_or_clipped_handles": sorted(boundary_handles),
        },
        "overlap": {
            "collision_pixels": collision_pixels,
            "implicated_handles": sorted((missed | extras) & collision_handles),
            "all_collision_handles": sorted(collision_handles),
        },
        "scale_error": {
            "max_abs_matrix_delta": matrix_error,
            "implicated": bool(matrix_error > 1e-9),
        },
    }


def _run_exact_case() -> dict[str, Any]:
    segments = [
        Segment("H_A", (4.0, 8.0), (34.0, 8.0)),
        Segment("H_B", (5.0, 35.0), (35.0, 35.0)),
        Segment("H_C", (42.0, 10.0), (57.0, 29.0)),
        Segment("H_OVER_1", (12.0, 22.0), (30.0, 22.0)),
        Segment("H_OVER_2", (12.0, 22.0), (30.0, 22.0)),
    ]
    transform = AffineTransform.from_scale_offset(1.25, 1.10, 3.0, 4.0)
    bridge = RasterHandleBridge(segments, (84, 56), transform, line_width_px=2.4, supersample=2)
    truth = {"H_A", "H_C", "H_OVER_1", "H_OVER_2"}
    oracle_supports = {handle: _oracle_support(bridge, handle) for handle in bridge.by_handle}
    implementation_supports = {handle: bridge.support(handle) for handle in bridge.by_handle}
    oracle_relation = _relation_tuples(oracle_supports)
    implementation_relation = _relation_tuples(implementation_supports)
    union = oracle_relation | implementation_relation
    intersection = oracle_relation & implementation_relation
    mapacc = len(intersection) / len(union) if union else 1.0

    oracle_mask = np.zeros((bridge.height, bridge.width), dtype=np.float32)
    for handle in truth:
        support = oracle_supports[handle]
        # The authoritative synthetic oracle is a binary wall mask.  Fractional
        # values belong to provenance A[p,h], not to Q[p].
        oracle_mask[support.rows, support.cols] = 1.0
    matches = bridge.mask_to_handles(oracle_mask, score_threshold=0.95)
    predicted = {match.handle for match in matches if match.selected}
    metrics = _set_metrics(truth, predicted)
    diagnostic = diagnose_recovery(bridge, truth, matches, expected_transform=transform)
    provenance = bridge.provenance(("H_OVER_1", "H_OVER_2"))
    overlap_preserved = any(
        {handle for handle, _ in entries} == {"H_OVER_1", "H_OVER_2"}
        for entries in provenance.values()
    )
    roundtrip_points = np.array([segment.p1 for segment in segments] + [segment.p2 for segment in segments])
    status = "PASS" if metrics["recall"] == 1.0 and metrics["precision"] == 1.0 else "FAIL"
    return {
        "name": "synthetic_exact",
        "status": status,
        "truth_handles": sorted(truth),
        "predicted_handles": sorted(predicted),
        "handle_recovery": metrics,
        "mapacc": mapacc,
        "crs_error": 1.0 - mapacc,
        "roundtrip_max_error_source_units": transform.roundtrip_error(roundtrip_points),
        "multi_hit_overlap_preserved": overlap_preserved,
        "failure_cause_decomposition": diagnostic,
    }


def _run_estimated_scale_case() -> dict[str, Any]:
    viewbox = (10.0, 20.0, 120.0, 80.0)
    image_size = (300, 120)
    expected = AffineTransform.from_scale_offset(2.5, 1.5, -25.0, -30.0)
    estimated = AffineTransform.from_viewbox(viewbox, image_size)
    segments = [
        Segment("EST_A", (20.0, 30.0), (70.0, 30.0)),
        Segment("EST_B", (80.0, 40.0), (110.0, 80.0)),
    ]
    bridge = RasterHandleBridge(segments, image_size, estimated, line_width_px=2.0)
    mask = bridge.handles_to_mask(("EST_A", "EST_B"))
    matches = bridge.mask_to_handles(mask, score_threshold=0.99)
    predicted = {match.handle for match in matches if match.selected}
    matrix_delta = float(np.max(np.abs(expected.matrix - estimated.matrix)))
    anisotropy = abs(estimated.matrix[0, 0] - estimated.matrix[1, 1]) / max(
        abs(estimated.matrix[0, 0]), abs(estimated.matrix[1, 1])
    )
    status = "PASS" if predicted == {"EST_A", "EST_B"} and matrix_delta <= 1e-12 else "FAIL"
    return {
        "name": "viewbox_scale_estimate",
        "status": status,
        "viewbox": list(viewbox),
        "image_size": list(image_size),
        "estimated_transform": estimated.to_dict(),
        "max_abs_expected_matrix_delta": matrix_delta,
        "scale_anisotropy_fraction": float(anisotropy),
        "recovered_handles": sorted(predicted),
    }


def _expect_failure(name: str, callback: Any) -> dict[str, Any]:
    try:
        callback()
    except (ValueError, KeyError) as exc:
        return {"name": name, "status": "PASS", "observed": type(exc).__name__, "message": str(exc)}
    return {"name": name, "status": "FAIL", "observed": "no exception"}


def _run_degenerate_cases() -> dict[str, Any]:
    segment = Segment("OK", (0.0, 0.0), (2.0, 2.0))
    bridge = RasterHandleBridge((Segment("OUTSIDE", (20.0, 20.0), (22.0, 22.0)),), (8, 8), AffineTransform.identity())
    missing_match = bridge.mask_to_handles(np.zeros((8, 8), dtype=np.float32))[0]
    empty_bridge = RasterHandleBridge((segment,), (8, 8), AffineTransform.identity())
    empty_selected = [match.handle for match in empty_bridge.mask_to_handles(np.zeros((8, 8))) if match.selected]
    cases = [
        _expect_failure("zero_width_viewbox", lambda: AffineTransform.from_viewbox((0, 0, 0, 10), (10, 10))),
        _expect_failure(
            "singular_affine", lambda: AffineTransform(np.array(((0, 0, 0), (0, 1, 0), (0, 0, 1))))
        ),
        _expect_failure("zero_length_segment", lambda: Segment("ZERO", (1, 1), (1, 1))),
        _expect_failure("invalid_polygon", lambda: empty_bridge.mask_from_polygon(((0, 0), (1, 1)))),
        _expect_failure("unknown_handle", lambda: empty_bridge.support("MISSING")),
        {
            "name": "fully_clipped_segment",
            "status": "PASS" if missing_match.raster_missing and missing_match.score is None else "FAIL",
            "match": missing_match.to_dict(),
        },
        {
            "name": "empty_mask",
            "status": "PASS" if not empty_selected else "FAIL",
            "selected_handles": empty_selected,
        },
    ]
    return {
        "name": "degenerate_cases",
        "status": "PASS" if all(case["status"] == "PASS" for case in cases) else "FAIL",
        "cases": cases,
    }


def run_selftest() -> dict[str, Any]:
    """Run exact, viewBox-estimation, and degenerate deterministic cases."""

    tests = [_run_exact_case(), _run_estimated_scale_case(), _run_degenerate_cases()]
    return {
        "schema": "e2.crs_bridge.selftest.v1",
        "status": "PASS" if all(test["status"] == "PASS" for test in tests) else "FAIL",
        "pixel_center_convention": PIXEL_CENTER_CONVENTION,
        "tests": tests,
    }


def _sample_source_points(segments: Sequence[Segment], max_points: int = 12000) -> np.ndarray:
    points: list[tuple[float, float]] = []
    visible = [segment for segment in segments if segment.visible]
    for segment in visible:
        length = math.hypot(segment.p2[0] - segment.p1[0], segment.p2[1] - segment.p1[1])
        count = max(2, min(48, int(math.ceil(length / 8.0)) + 1))
        for fraction in np.linspace(0.0, 1.0, count):
            points.append(
                (
                    segment.p1[0] + float(fraction) * (segment.p2[0] - segment.p1[0]),
                    segment.p1[1] + float(fraction) * (segment.p2[1] - segment.p1[1]),
                )
            )
    if not points:
        return np.empty((0, 2), dtype=np.float64)
    if len(points) > max_points:
        indices = np.linspace(0, len(points) - 1, max_points, dtype=np.int64)
        return np.asarray(points, dtype=np.float64)[indices]
    return np.asarray(points, dtype=np.float64)


def _raw_edge_map(image_path: Path) -> tuple[np.ndarray, tuple[int, int], float]:
    if Image is None:
        raise RuntimeError("Pillow is required for the real-data smoke test")
    with Image.open(image_path) as image:
        gray = np.asarray(image.convert("L"), dtype=np.int16)
        size = image.size
    gradient = np.zeros(gray.shape, dtype=np.int16)
    gradient[:, 1:] = np.maximum(gradient[:, 1:], np.abs(gray[:, 1:] - gray[:, :-1]))
    gradient[:, :-1] = np.maximum(gradient[:, :-1], np.abs(gray[:, 1:] - gray[:, :-1]))
    gradient[1:, :] = np.maximum(gradient[1:, :], np.abs(gray[1:, :] - gray[:-1, :]))
    gradient[:-1, :] = np.maximum(gradient[:-1, :], np.abs(gray[1:, :] - gray[:-1, :]))
    nonzero = gradient[gradient > 0]
    threshold = max(20.0, float(np.percentile(nonzero, 60.0))) if len(nonzero) else 20.0
    return gradient >= threshold, size, threshold


def _nearest_edge_metrics(edge_map: np.ndarray, points: np.ndarray, radius: int = 12) -> dict[str, Any]:
    height, width = edge_map.shape
    if len(points) == 0:
        return {
            "sample_points": 0,
            "in_bounds_fraction": 0.0,
            "matched_within_radius_fraction": 0.0,
            "rmse_px": None,
            "median_px": None,
            "p95_px": None,
        }
    cols = np.rint(points[:, 0]).astype(np.int64)
    rows = np.rint(points[:, 1]).astype(np.int64)
    in_bounds = (cols >= 0) & (cols < width) & (rows >= 0) & (rows < height)
    cols = cols[in_bounds]
    rows = rows[in_bounds]
    if len(cols) == 0:
        return {
            "sample_points": int(len(points)),
            "in_bounds_fraction": 0.0,
            "matched_within_radius_fraction": 0.0,
            "rmse_px": None,
            "median_px": None,
            "p95_px": None,
        }
    best = np.full(len(cols), float(radius + 1), dtype=np.float64)
    offsets = [
        (math.hypot(dx, dy), dx, dy)
        for dy in range(-radius, radius + 1)
        for dx in range(-radius, radius + 1)
        if math.hypot(dx, dy) <= radius
    ]
    offsets.sort()
    for distance, dx, dy in offsets:
        unresolved = best > distance
        if not np.any(unresolved):
            break
        candidate_cols = cols + dx
        candidate_rows = rows + dy
        valid = (
            unresolved
            & (candidate_cols >= 0)
            & (candidate_cols < width)
            & (candidate_rows >= 0)
            & (candidate_rows < height)
        )
        indices = np.flatnonzero(valid)
        if len(indices):
            hit_indices = indices[edge_map[candidate_rows[indices], candidate_cols[indices]]]
            best[hit_indices] = distance
    matched = best <= radius
    return {
        "sample_points": int(len(points)),
        "in_bounds_fraction": float(len(cols) / len(points)),
        "matched_within_radius_fraction": float(np.mean(matched)),
        "rmse_px": float(math.sqrt(float(np.mean(best * best)))),
        "median_px": float(np.median(best)),
        "p95_px": float(np.percentile(best, 95.0)),
        "search_radius_px": radius,
    }


def smoke_cubicasa_sample(sample_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Label-free SVG/image alignment audit for one CubiCasa sample."""

    sample = Path(sample_dir)
    svg_path = sample / "model.svg"
    image_path = sample / "F1_scaled.png"
    if not svg_path.is_file() or not image_path.is_file():
        raise FileNotFoundError(f"sample must contain model.svg and F1_scaled.png: {sample}")
    edge_map, image_size, edge_threshold = _raw_edge_map(image_path)
    viewbox = parse_svg_viewbox(svg_path)
    segments = load_svg_segments(svg_path)
    source_points = _sample_source_points(segments)

    identity = AffineTransform.identity("CubiCasa SVG coordinate identity candidate")
    estimated = AffineTransform.from_viewbox(viewbox, image_size)
    identity_metrics = _nearest_edge_metrics(edge_map, identity.apply(source_points))
    estimated_metrics = _nearest_edge_metrics(edge_map, estimated.apply(source_points))
    sx = float(estimated.matrix[0, 0])
    sy = float(estimated.matrix[1, 1])
    aspect_mismatch = abs((image_size[0] / image_size[1]) / (viewbox[2] / viewbox[3]) - 1.0)
    anisotropy = abs(sx - sy) / max(abs(sx), abs(sy))
    identity_rmse = identity_metrics["rmse_px"]
    estimated_rmse = estimated_metrics["rmse_px"]
    if identity_rmse is not None and (estimated_rmse is None or identity_rmse <= estimated_rmse):
        selected = "identity_svg_coordinates_are_pixel_coordinates"
        selected_metrics = identity_metrics
    else:
        selected = "dimension_ratio_estimate"
        selected_metrics = estimated_metrics
    selected_rmse = selected_metrics["rmse_px"]
    selected_in_bounds = selected_metrics["in_bounds_fraction"]
    status = "PASS" if selected_rmse is not None and selected_rmse <= 6.0 and selected_in_bounds >= 0.90 else "FAIL"
    fallback_status = (
        "SUPPORTED"
        if estimated_rmse is not None
        and estimated_rmse <= 6.0
        and estimated_metrics["in_bounds_fraction"] >= 0.90
        else "REJECTED_BY_EDGE_AUDIT"
    )
    original_size: tuple[int, int] | None = None
    original_path = sample / "F1_original.png"
    if original_path.is_file() and Image is not None:
        with Image.open(original_path) as original:
            original_size = original.size
    return {
        "sample_id": sample.name,
        "status": status,
        "inputs": {"image": str(image_path), "svg": str(svg_path)},
        "wall_mask_or_class_labels_used": False,
        "image_size": list(image_size),
        "original_image_size": list(original_size) if original_size else None,
        "svg_viewbox": list(viewbox),
        "segments_examined": len(segments),
        "visible_segments_examined": sum(segment.visible for segment in segments),
        "edge_gradient_threshold": edge_threshold,
        "dimension_ratio_estimate": {
            "transform": estimated.to_dict(),
            "scale_x": sx,
            "scale_y": sy,
            "scale_anisotropy_fraction": anisotropy,
            "aspect_ratio_mismatch_fraction": aspect_mismatch,
            "audit_status": fallback_status,
            "raw_edge_alignment": estimated_metrics,
        },
        "identity_candidate": {"transform": identity.to_dict(), "raw_edge_alignment": identity_metrics},
        "selected_alignment": selected,
        "selected_alignment_error": selected_metrics,
        "roundtrip_max_error_source_units": estimated.roundtrip_error(
            np.array(
                (
                    (viewbox[0], viewbox[1]),
                    (viewbox[0] + viewbox[2], viewbox[1]),
                    (viewbox[0], viewbox[1] + viewbox[3]),
                    (viewbox[0] + viewbox[2], viewbox[1] + viewbox[3]),
                )
            )
        ),
    }


def run_cubicasa_smoke(sample_dirs: Sequence[str | os.PathLike[str]] | None = None) -> dict[str, Any]:
    if sample_dirs is None:
        sample_dirs = [DEFAULT_DATA_ROOT / sample_id for sample_id in DEFAULT_SMOKE_IDS]
    samples: list[dict[str, Any]] = []
    for sample_dir in sample_dirs[:3]:
        try:
            samples.append(smoke_cubicasa_sample(sample_dir))
        except Exception as exc:  # noqa: BLE001 - report honest per-sample failure
            samples.append(
                {
                    "sample_id": Path(sample_dir).name,
                    "status": "FAIL",
                    "error": f"{type(exc).__name__}: {exc}",
                    "wall_mask_or_class_labels_used": False,
                }
            )
    return {
        "schema": "e2.crs_bridge.cubicasa_smoke.v1",
        "status": "PASS" if samples and all(sample["status"] == "PASS" for sample in samples) else "FAIL",
        "method": "raw grayscale edge proximity; no wall mask and no SVG class label",
        "samples": samples,
    }


def _load_mask(path: str | os.PathLike[str], size: tuple[int, int]) -> np.ndarray:
    if Image is None:
        raise RuntimeError("Pillow is required to load masks")
    with Image.open(path) as image:
        if image.size != size:
            raise ValueError(f"mask image size must be {size}, got {image.size}")
        return np.asarray(image.convert("L"), dtype=np.float32) / 255.0


def _load_polygon_argument(raw: str) -> list[list[float]]:
    candidate = Path(raw)
    if candidate.is_file():
        with open(candidate, "r", encoding="utf-8") as stream:
            payload = json.load(stream)
    else:
        payload = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError("polygon must be a JSON list of [x,y] points")
    return payload


def _save_mask(mask: np.ndarray, path: str | os.PathLike[str]) -> None:
    if Image is None:
        raise RuntimeError("Pillow is required to save masks")
    clipped = np.clip(mask, 0.0, 1.0)
    Image.fromarray(np.rint(clipped * 255.0).astype(np.uint8), mode="L").save(path)


def _write_or_print(payload: Mapping[str, Any], output: str | None) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if output:
        with open(output, "w", encoding="utf-8") as stream:
            stream.write(rendered + "\n")
    print(rendered)


def _mapping_cli(args: argparse.Namespace) -> dict[str, Any]:
    if Image is None:
        raise RuntimeError("Pillow is required for mapping CLI image I/O")
    with Image.open(args.image) as image:
        image_size = image.size
    if args.seg_ir:
        segments = load_seg_ir(args.seg_ir)
    else:
        segments = load_svg_segments(args.svg)
    if args.scale_x is not None:
        transform = AffineTransform.from_scale_offset(
            args.scale_x,
            args.scale_y,
            args.offset_x,
            args.offset_y,
        )
    else:
        if not args.svg:
            raise ValueError("unknown scale requires --svg so its viewBox can be inspected")
        transform = AffineTransform.from_viewbox(parse_svg_viewbox(args.svg), image_size)
    bridge = RasterHandleBridge(
        segments,
        image_size,
        transform,
        line_width_px=args.line_width,
        supersample=args.supersample,
    )
    if args.handles:
        mask = bridge.handles_to_mask(args.handles)
        if args.output_mask:
            _save_mask(mask, args.output_mask)
        return {
            "mode": "handles_to_pixels",
            "transform": transform.to_dict(),
            "handles": list(args.handles),
            "polylines_px": bridge.handles_to_polylines(args.handles),
            "boxes_px": bridge.handles_to_boxes(args.handles),
            "mask_nonzero_pixels": int(np.count_nonzero(mask)),
            "output_mask": args.output_mask,
        }
    if args.mask:
        mask = _load_mask(args.mask, image_size)
        source_kind = "mask"
    elif args.box:
        mask = bridge.mask_from_box(args.box)
        source_kind = "box"
    elif args.polygon:
        mask = bridge.mask_from_polygon(_load_polygon_argument(args.polygon))
        source_kind = "polygon"
    else:
        raise ValueError("mapping requires one of --handles, --mask, --box, or --polygon")
    matches = bridge.mask_to_handles(mask, args.score_threshold)
    return {
        "mode": "pixels_to_handles",
        "source_kind": source_kind,
        "transform": transform.to_dict(),
        "selected_handles": [match.handle for match in matches if match.selected],
        "matches": [match.to_dict() for match in matches],
    }


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="run deterministic required tests")
    parser.add_argument("--smoke", action="store_true", help="run 1-3 label-free CubiCasa alignment smokes")
    parser.add_argument("--samples", nargs="*", help="sample directories for --smoke (maximum 3)")
    parser.add_argument("--seg-ir", help="SEG-IR JSON for mapping mode")
    parser.add_argument("--svg", help="SVG geometry/viewBox for mapping mode")
    parser.add_argument("--image", help="raster image establishing mapping canvas size")
    parser.add_argument("--mask", help="selection mask image")
    parser.add_argument("--box", nargs=4, type=float, metavar=("X0", "Y0", "X1", "Y1"))
    parser.add_argument("--polygon", help="JSON polygon text or path")
    parser.add_argument("--handles", nargs="+", help="source handles to rasterize")
    parser.add_argument("--output-mask", help="optional output for --handles rasterization")
    parser.add_argument("--scale-x", type=float, help="known source-to-pixel X scale")
    parser.add_argument("--scale-y", type=float, help="known source-to-pixel Y scale; defaults to X")
    parser.add_argument("--offset-x", type=float, default=0.0)
    parser.add_argument("--offset-y", type=float, default=0.0)
    parser.add_argument("--line-width", type=float, default=1.0)
    parser.add_argument("--supersample", type=int, default=1)
    parser.add_argument("--score-threshold", type=float, default=0.5)
    parser.add_argument("--json-out", help="also write JSON output to this path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            payload = run_selftest()
        elif args.smoke:
            payload = run_cubicasa_smoke(args.samples or None)
        else:
            if not args.image or not (args.seg_ir or args.svg):
                parser.error("mapping mode requires --image and one of --seg-ir/--svg")
            payload = _mapping_cli(args)
    except Exception as exc:  # noqa: BLE001 - CLI must emit an auditable failure
        payload = {
            "status": "FAIL",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        _write_or_print(payload, args.json_out)
        return 1
    _write_or_print(payload, args.json_out)
    return 0 if payload.get("status", "PASS") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
