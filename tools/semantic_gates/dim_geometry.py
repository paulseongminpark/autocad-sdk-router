#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic L5 semantic gate for dimension-vs-geometry preservation."""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

DIM_SEMANTIC_GATE_SCHEMA_ID = "ariadne.dim_semantic_gate.v1"
_JSON_ENCODING = "utf-8-sig"
_ROUND_DIGITS = 6
_MUTATED_ROWS_CAP = 20
_DEFAULT_SNAP_TOLERANCE = 3000.0


def load_ir(path: str | Path) -> Dict[str, Any]:
    """Load a JSON IR document or fixture document."""
    return json.loads(Path(path).read_text(encoding=_JSON_ENCODING))


def _normalize_zero(value: float) -> float:
    return 0.0 if value == 0 else value


def _round_number(value: Any, digits: int = _ROUND_DIGITS) -> float:
    return _normalize_zero(round(float(value), digits))


def _round_point(point: Sequence[Any], digits: int = _ROUND_DIGITS) -> Tuple[float, ...]:
    return tuple(_round_number(coord, digits) for coord in point)


def _point_tuple(point: Sequence[Any]) -> Tuple[float, ...]:
    return tuple(float(coord) for coord in point)


def _distance(point_a: Sequence[Any], point_b: Sequence[Any]) -> float:
    a = _point_tuple(point_a)
    b = _point_tuple(point_b)
    size = max(len(a), len(b))
    if len(a) < size:
        a = a + (0.0,) * (size - len(a))
    if len(b) < size:
        b = b + (0.0,) * (size - len(b))
    return math.dist(a, b)


def _iter_dimension_entities(ir_doc: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    if isinstance(ir_doc.get("dimensions"), list):
        for entity in ir_doc["dimensions"]:
            if isinstance(entity, dict):
                yield entity
        return

    for entity in ir_doc.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        geometry = entity.get("geometry") or {}
        if geometry.get("kind") == "dimension":
            yield entity


def _iter_anchor_entities(ir_doc: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    if isinstance(ir_doc.get("anchor_geometry"), list):
        for entity in ir_doc["anchor_geometry"]:
            if isinstance(entity, dict):
                yield entity
        return

    for entity in ir_doc.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        geometry = entity.get("geometry") or {}
        if geometry.get("kind") in {"line", "lwpolyline"}:
            yield entity


def _anchor_points(entity: Dict[str, Any]) -> List[Dict[str, Any]]:
    geometry = entity.get("geometry") or {}
    handle = entity.get("handle")
    if not isinstance(handle, str) or not handle:
        return []

    points: List[Sequence[Any]] = []
    if geometry.get("kind") == "line":
        for key in ("start", "end"):
            value = geometry.get(key)
            if isinstance(value, list):
                points.append(value)
    elif geometry.get("kind") == "lwpolyline":
        for vertex in geometry.get("vertices") or []:
            if isinstance(vertex, dict) and isinstance(vertex.get("point"), list):
                points.append(vertex["point"])

    return [{"handle": handle, "point": list(_point_tuple(point))} for point in points]


def _nearest_anchor(
    target_point: Sequence[Any],
    anchor_points: Sequence[Dict[str, Any]],
    snap_tolerance: float,
) -> Optional[Dict[str, Any]]:
    best: Optional[Tuple[float, str, Tuple[float, ...], Dict[str, Any]]] = None
    for anchor in anchor_points:
        handle = anchor.get("handle")
        point = anchor.get("point")
        if not isinstance(handle, str) or not isinstance(point, list):
            continue
        point_key = _round_point(point)
        dist = _distance(target_point, point)
        candidate = (dist, handle, point_key, {"handle": handle, "point": list(_point_tuple(point))})
        if best is None or candidate < best:
            best = candidate

    if best is None or best[0] > snap_tolerance:
        return None
    return best[3]


def _sorted_anchor_pair(anchor_a: Dict[str, Any], anchor_b: Dict[str, Any]) -> List[Dict[str, Any]]:
    return sorted(
        [anchor_a, anchor_b],
        key=lambda item: (item["handle"], _round_point(item["point"])),
    )


def _dimension_span(geometry: Dict[str, Any]) -> float:
    xline1 = _point_tuple(geometry["xline1_point"])
    xline2 = _point_tuple(geometry["xline2_point"])
    rotation = float(geometry["rotation"])
    unit = (math.cos(rotation), math.sin(rotation))
    delta = (xline2[0] - xline1[0], xline2[1] - xline1[1])
    return abs((delta[0] * unit[0]) + (delta[1] * unit[1]))


def _value_close(value_a: float, value_b: float, tolerance: float) -> bool:
    return abs(value_a - value_b) <= tolerance * max(1.0, abs(value_a), abs(value_b))


def _canonical_key(row: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        _round_point(row["xline1_point"]),
        _round_point(row["xline2_point"]),
        _round_number(row["rotation"]),
    )


def extract_dim_relations(ir_doc: Dict[str, Any], *, tolerance: float = 1e-6) -> List[Dict[str, Any]]:
    """Extract deterministic dimension-relation rows from an IR or fixture document."""
    anchor_points: List[Dict[str, Any]] = []
    for entity in _iter_anchor_entities(ir_doc if isinstance(ir_doc, dict) else {}):
        anchor_points.extend(_anchor_points(entity))

    rows: List[Dict[str, Any]] = []
    for entity in _iter_dimension_entities(ir_doc if isinstance(ir_doc, dict) else {}):
        geometry = entity.get("geometry") or {}
        if not isinstance(geometry, dict):
            continue
        if geometry.get("kind") != "dimension":
            continue

        try:
            xline1 = list(_point_tuple(geometry["xline1_point"]))
            xline2 = list(_point_tuple(geometry["xline2_point"]))
            rotation = float(geometry["rotation"])
            measurement = float(geometry["measurement"])
        except (KeyError, TypeError, ValueError):
            continue

        span = _dimension_span(geometry)
        residual = measurement - span
        coherent = abs(residual) <= tolerance * max(1.0, span)

        anchor_1 = _nearest_anchor(xline1, anchor_points, _DEFAULT_SNAP_TOLERANCE)
        anchor_2 = _nearest_anchor(xline2, anchor_points, _DEFAULT_SNAP_TOLERANCE)
        anchor = _sorted_anchor_pair(anchor_1, anchor_2) if anchor_1 and anchor_2 else None

        rows.append(
            {
                "handle": entity.get("handle"),
                "layer": entity.get("layer"),
                "measurement": measurement,
                "span": span,
                "residual": residual,
                "coherent": coherent,
                "anchor": anchor,
                "xline1_point": xline1,
                "xline2_point": xline2,
                "rotation": rotation,
            }
        )

    return rows


def compare_dim_relations(
    rows_a: Sequence[Dict[str, Any]],
    rows_b: Sequence[Dict[str, Any]],
    *,
    tolerance: float = 1e-6,
) -> Dict[str, Any]:
    """Compare two extracted relation tables by canonical geometry identity."""
    index_a: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)
    index_b: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)

    for row in rows_a:
        index_a[_canonical_key(row)].append(row)
    for row in rows_b:
        index_b[_canonical_key(row)].append(row)

    for bucket in index_a.values():
        bucket.sort(key=lambda row: (row.get("handle") or "", row["measurement"], row["span"]))
    for bucket in index_b.values():
        bucket.sort(key=lambda row: (row.get("handle") or "", row["measurement"], row["span"]))

    preserved = 0
    missing = 0
    mutated = 0
    rows_mutated: List[Dict[str, Any]] = []

    for key in sorted(index_a):
        bucket_a = index_a[key]
        bucket_b = index_b.get(key, [])
        paired = min(len(bucket_a), len(bucket_b))

        for idx in range(paired):
            row_a = bucket_a[idx]
            row_b = bucket_b[idx]
            measurement_ok = _value_close(row_a["measurement"], row_b["measurement"], tolerance)
            span_ok = _value_close(row_a["span"], row_b["span"], tolerance)
            if measurement_ok and span_ok:
                preserved += 1
                continue

            mutated += 1
            if len(rows_mutated) < _MUTATED_ROWS_CAP:
                rows_mutated.append(
                    {
                        "handle_a": row_a.get("handle"),
                        "handle_b": row_b.get("handle"),
                        "key": {
                            "xline1_point": list(key[0]),
                            "xline2_point": list(key[1]),
                            "rotation": key[2],
                        },
                        "measurement_a": row_a["measurement"],
                        "measurement_b": row_b["measurement"],
                        "span_a": row_a["span"],
                        "span_b": row_b["span"],
                    }
                )

        if len(bucket_a) > paired:
            missing += len(bucket_a) - paired

    total_a = len(rows_a)
    total_b = len(rows_b)
    fraction = (preserved / total_a) if total_a else 1.0
    status = "ok" if fraction == 1.0 and total_b >= total_a else "blocked"

    return {
        "schema": DIM_SEMANTIC_GATE_SCHEMA_ID,
        "total_a": total_a,
        "total_b": total_b,
        "preserved": preserved,
        "missing": missing,
        "mutated": mutated,
        "fraction": fraction,
        "status": status,
        "rows_mutated": rows_mutated,
    }


def self_test_mutations() -> Dict[str, Any]:
    """Mutate the real fixture three ways and assert the judge convicts them."""
    fixture_path = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "dim_gate_samples.json"
    ir_a = load_ir(fixture_path)
    ir_b = copy.deepcopy(ir_a)

    dims_b = ir_b["dimensions"]
    dims_b[0]["geometry"]["measurement"] += 1.0
    dims_b[1]["geometry"]["xline1_point"][0] += 10.0
    del dims_b[2]

    report = compare_dim_relations(extract_dim_relations(ir_a), extract_dim_relations(ir_b))

    assert report["status"] == "blocked"
    assert report["mutated"] >= 1
    assert report["missing"] >= 2
    assert any(item["handle_a"] == ir_a["dimensions"][0]["handle"] for item in report["rows_mutated"])
    return report


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ir_a", help="Original IR JSON path")
    parser.add_argument("ir_b", help="Rebuilt IR JSON path")
    parser.add_argument("--out", help="Optional report output path")
    parser.add_argument("--tolerance", type=float, default=1e-6, help="Relative comparison tolerance")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    rows_a = extract_dim_relations(load_ir(args.ir_a), tolerance=args.tolerance)
    rows_b = extract_dim_relations(load_ir(args.ir_b), tolerance=args.tolerance)
    report = compare_dim_relations(rows_a, rows_b, tolerance=args.tolerance)
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.out:
        Path(args.out).write_text(f"{text}\n", encoding="utf-8")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
