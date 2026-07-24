#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic L5 semantic gate for centerline-topology preservation."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


CENTERLINE_TOPOLOGY_GATE_SCHEMA_ID = "ariadne.centerline_topology_gate.v1"
MODELSPACE_OWNER = "__modelspace__"
_JSON_ENCODING = "utf-8-sig"
_ROUND_DIGITS = 6
_DIFF_CAP = 20
_EPSILON = 1e-12

Point = Tuple[float, float]
Segment = Tuple[Point, Point]


def load_ir(path: str | Path) -> Dict[str, Any]:
    """Load a JSON IR document."""
    return json.loads(Path(path).read_text(encoding=_JSON_ENCODING))


def _normalize_zero(value: float) -> float:
    return 0.0 if value == 0 else value


def _round_number(value: float, digits: int = _ROUND_DIGITS) -> float:
    return _normalize_zero(round(float(value), digits))


def _round_point(point: Point, digits: int = _ROUND_DIGITS) -> List[float]:
    return [_round_number(point[0], digits), _round_number(point[1], digits)]


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number)


def _point2(value: Any) -> Optional[Point]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    if not _is_number(value[0]) or not _is_number(value[1]):
        return None
    return float(value[0]), float(value[1])


def _angle_mod_pi(dx: float, dy: float) -> float:
    return math.atan2(dy, dx) % math.pi


def _angle_diff(a: float, b: float) -> float:
    diff = abs(a - b)
    return min(diff, math.pi - diff)


def _mean_undirected_angle(angles: Sequence[float]) -> float:
    y = sum(math.sin(2.0 * angle) for angle in angles)
    x = sum(math.cos(2.0 * angle) for angle in angles)
    if abs(x) <= _EPSILON and abs(y) <= _EPSILON:
        return min(angles) if angles else 0.0
    return (0.5 * math.atan2(y, x)) % math.pi


def _dot(point: Point, vector: Point) -> float:
    return point[0] * vector[0] + point[1] * vector[1]


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _canonical_segment(start: Point, end: Point) -> Segment:
    a = (_normalize_zero(start[0]), _normalize_zero(start[1]))
    b = (_normalize_zero(end[0]), _normalize_zero(end[1]))
    return (a, b) if a <= b else (b, a)


def _segment_length(segment: Segment) -> float:
    return _distance(segment[0], segment[1])


def _segment_sort_key(segment: Segment) -> Tuple[float, float, float, float]:
    return (
        _round_number(segment[0][0]),
        _round_number(segment[0][1]),
        _round_number(segment[1][0]),
        _round_number(segment[1][1]),
    )


def _segment_to_json(segment: Segment) -> Dict[str, Any]:
    return {
        "start": _round_point(segment[0]),
        "end": _round_point(segment[1]),
        "length": _round_number(_segment_length(segment)),
    }


def _summary(segments: Sequence[Segment]) -> Dict[str, Any]:
    nodes = {
        tuple(_round_point(point))
        for segment in segments
        for point in segment
    }
    return {
        "segments": len(segments),
        "nodes": len(nodes),
        "total_length": _round_number(sum(_segment_length(segment) for segment in segments)),
    }


def _definition_entities(block_def: Dict[str, Any]) -> List[Dict[str, Any]]:
    entities = block_def.get("def_entities")
    if entities is None:
        entities = block_def.get("entities")
    if not isinstance(entities, list):
        return []
    return [entity for entity in entities if isinstance(entity, dict)]


def _iter_entity_buckets(ir_doc: Dict[str, Any]) -> Iterable[Tuple[str, List[Dict[str, Any]]]]:
    if not isinstance(ir_doc, dict):
        ir_doc = {}

    for block_def in ir_doc.get("block_definitions") or []:
        if not isinstance(block_def, dict):
            continue
        name = block_def.get("name")
        if not isinstance(name, str) or not name:
            continue
        yield name, _definition_entities(block_def)

    entities = ir_doc.get("entities")
    if isinstance(entities, list):
        yield MODELSPACE_OWNER, [entity for entity in entities if isinstance(entity, dict)]


def _line_record(entity: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
    geometry = entity.get("geometry")
    if not isinstance(geometry, dict):
        return None
    if geometry.get("kind") != "line" and entity.get("dxf_name") != "LINE":
        return None

    start = _point2(geometry.get("start"))
    end = _point2(geometry.get("end"))
    if start is None or end is None:
        return None

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= _EPSILON:
        return None

    return {
        "index": index,
        "start": start,
        "end": end,
        "length": length,
        "angle": _angle_mod_pi(dx, dy),
    }


def _angle_clusters(lines: Sequence[Dict[str, Any]], angle_tol: float) -> List[List[int]]:
    if not lines:
        return []
    if angle_tol < 0.0:
        angle_tol = 0.0

    items = sorted((line["angle"], index) for index, line in enumerate(lines))
    if len(items) == 1:
        return [[items[0][1]]]

    gaps: List[Tuple[float, int]] = []
    for pos, (angle, _index) in enumerate(items):
        next_angle = items[(pos + 1) % len(items)][0]
        if pos == len(items) - 1:
            next_angle += math.pi
        gaps.append((next_angle - angle, pos))

    _gap, cut_pos = max(gaps, key=lambda item: (item[0], item[1]))
    ordered = [items[(cut_pos + 1 + offset) % len(items)] for offset in range(len(items))]

    clusters: List[List[int]] = []
    anchor_angle, first_index = ordered[0]
    current = [first_index]
    for angle, index in ordered[1:]:
        if _angle_diff(anchor_angle, angle) < angle_tol:
            current.append(index)
            continue
        clusters.append(current)
        anchor_angle = angle
        current = [index]
    clusters.append(current)

    return clusters


def _row_for_line(line: Dict[str, Any], direction: Point, normal: Point) -> Dict[str, Any]:
    t_start = _dot(line["start"], direction)
    t_end = _dot(line["end"], direction)
    offset_start = _dot(line["start"], normal)
    offset_end = _dot(line["end"], normal)
    return {
        "line": line,
        "t_min": min(t_start, t_end),
        "t_max": max(t_start, t_end),
        "offset": (offset_start + offset_end) * 0.5,
    }


def _centerline_for_pair(
    row_a: Dict[str, Any],
    row_b: Dict[str, Any],
    direction: Point,
    normal: Point,
    *,
    thickness_min: float,
    thickness_max: float,
    overlap_min_ratio: float,
    angle_tol: float,
) -> Optional[Segment]:
    line_a = row_a["line"]
    line_b = row_b["line"]
    if _angle_diff(line_a["angle"], line_b["angle"]) >= angle_tol:
        return None

    gap = abs(row_b["offset"] - row_a["offset"])
    if gap + _EPSILON < thickness_min or gap - _EPSILON > thickness_max:
        return None

    start_t = max(row_a["t_min"], row_b["t_min"])
    end_t = min(row_a["t_max"], row_b["t_max"])
    overlap = end_t - start_t
    if overlap <= _EPSILON:
        return None

    len_a = row_a["t_max"] - row_a["t_min"]
    len_b = row_b["t_max"] - row_b["t_min"]
    shorter = max(_EPSILON, min(len_a, len_b))
    if (overlap / shorter) + _EPSILON < overlap_min_ratio:
        return None

    mid_offset = (row_a["offset"] + row_b["offset"]) * 0.5
    start = (
        direction[0] * start_t + normal[0] * mid_offset,
        direction[1] * start_t + normal[1] * mid_offset,
    )
    end = (
        direction[0] * end_t + normal[0] * mid_offset,
        direction[1] * end_t + normal[1] * mid_offset,
    )
    return _canonical_segment(start, end)


def _extract_centerlines_from_lines(
    lines: Sequence[Dict[str, Any]],
    *,
    thickness_min: float,
    thickness_max: float,
    overlap_min_ratio: float,
    angle_tol: float,
) -> List[Segment]:
    if len(lines) < 2 or thickness_max < thickness_min:
        return []

    segments: List[Segment] = []
    for cluster in _angle_clusters(lines, angle_tol):
        if len(cluster) < 2:
            continue
        family_angle = _mean_undirected_angle([lines[index]["angle"] for index in cluster])
        direction = (math.cos(family_angle), math.sin(family_angle))
        normal = (-direction[1], direction[0])
        rows = [_row_for_line(lines[index], direction, normal) for index in cluster]
        rows.sort(key=lambda row: (
            row["offset"],
            row["t_min"],
            row["t_max"],
            row["line"]["index"],
        ))

        for left, right in zip(rows, rows[1:]):
            segment = _centerline_for_pair(
                left,
                right,
                direction,
                normal,
                thickness_min=thickness_min,
                thickness_max=thickness_max,
                overlap_min_ratio=overlap_min_ratio,
                angle_tol=angle_tol,
            )
            if segment is not None:
                segments.append(segment)

    return sorted(segments, key=_segment_sort_key)


def extract_centerline_topology(
    ir_doc: Dict[str, Any],
    *,
    thickness_min: float = 10.0,
    thickness_max: float = 400.0,
    overlap_min_ratio: float = 0.5,
    angle_tol: float = 1e-4,
    name_map: Optional[Dict[str, str]] = None,
) -> Dict[str, List[Segment]]:
    """Extract centerline segments per block definition and modelspace bucket.

    ``name_map`` aliases census block names onto their post-side names so a
    census anonymous block (``*U132``/``*D295``) pairs with its rebuilt
    counterpart (``ARIADNE_ANON_U132``/``...D295``), mirroring the convention in
    ``block_topology.py``. The modelspace bucket is never in the map.
    """
    mapping = name_map or {}
    per_block: Dict[str, List[Segment]] = {}
    for raw_name, entities in _iter_entity_buckets(ir_doc):
        block_name = mapping.get(raw_name, raw_name)
        per_block.setdefault(block_name, [])
        lines: List[Dict[str, Any]] = []
        for index, entity in enumerate(entities):
            line = _line_record(entity, index)
            if line is not None:
                lines.append(line)
        per_block[block_name].extend(
            _extract_centerlines_from_lines(
                lines,
                thickness_min=float(thickness_min),
                thickness_max=float(thickness_max),
                overlap_min_ratio=float(overlap_min_ratio),
                angle_tol=float(angle_tol),
            )
        )

    for block_name in list(per_block):
        per_block[block_name] = sorted(per_block[block_name], key=_segment_sort_key)
    return per_block


def _matching_diff(
    census_segments: Sequence[Segment],
    post_segments: Sequence[Segment],
    *,
    match_tol: float,
) -> Tuple[List[Segment], List[Segment]]:
    matches: List[Tuple[float, int, int]] = []
    for census_index, census_segment in enumerate(census_segments):
        for post_index, post_segment in enumerate(post_segments):
            distance = max(
                _distance(census_segment[0], post_segment[0]),
                _distance(census_segment[1], post_segment[1]),
            )
            if distance <= match_tol:
                matches.append((distance, census_index, post_index))

    matches.sort(key=lambda item: (
        item[0],
        _segment_sort_key(census_segments[item[1]]),
        _segment_sort_key(post_segments[item[2]]),
        item[1],
        item[2],
    ))

    matched_census = set()
    matched_post = set()
    for _distance_value, census_index, post_index in matches:
        if census_index in matched_census or post_index in matched_post:
            continue
        matched_census.add(census_index)
        matched_post.add(post_index)

    missing = [
        segment
        for index, segment in enumerate(census_segments)
        if index not in matched_census
    ]
    added = [
        segment
        for index, segment in enumerate(post_segments)
        if index not in matched_post
    ]
    return missing, added


def centerline_topology_gate_report(
    census_ir: Dict[str, Any],
    post_ir: Dict[str, Any],
    *,
    thickness_min: float = 10.0,
    thickness_max: float = 400.0,
    overlap_min_ratio: float = 0.5,
    angle_tol: float = 1e-4,
    match_tol: float = 1.0,
    name_map: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    census_topology = extract_centerline_topology(
        census_ir or {},
        thickness_min=thickness_min,
        thickness_max=thickness_max,
        overlap_min_ratio=overlap_min_ratio,
        angle_tol=angle_tol,
        name_map=name_map,
    )
    post_topology = extract_centerline_topology(
        post_ir or {},
        thickness_min=thickness_min,
        thickness_max=thickness_max,
        overlap_min_ratio=overlap_min_ratio,
        angle_tol=angle_tol,
        name_map=name_map,
    )

    params = {
        "thickness_min": float(thickness_min),
        "thickness_max": float(thickness_max),
        "overlap_min_ratio": float(overlap_min_ratio),
        "angle_tol": float(angle_tol),
        "match_tol": float(match_tol),
    }
    per_block: Dict[str, Any] = {}
    totals = {
        "census_segments": 0,
        "post_segments": 0,
        "missing_total": 0,
        "added_total": 0,
    }

    for block_name in sorted(set(census_topology) | set(post_topology)):
        census_segments = sorted(census_topology.get(block_name, []), key=_segment_sort_key)
        post_segments = sorted(post_topology.get(block_name, []), key=_segment_sort_key)
        missing, added = _matching_diff(census_segments, post_segments, match_tol=float(match_tol))

        totals["census_segments"] += len(census_segments)
        totals["post_segments"] += len(post_segments)
        totals["missing_total"] += len(missing)
        totals["added_total"] += len(added)

        per_block[block_name] = {
            "census": _summary(census_segments),
            "post": _summary(post_segments),
            "diff": {
                "missing_total": len(missing),
                "added_total": len(added),
                "missing": [_segment_to_json(segment) for segment in missing[:_DIFF_CAP]],
                "added": [_segment_to_json(segment) for segment in added[:_DIFF_CAP]],
            },
        }

    verdict = "PASS" if totals["missing_total"] == 0 and totals["added_total"] == 0 else "FAIL"
    return {
        "schema": CENTERLINE_TOPOLOGY_GATE_SCHEMA_ID,
        "params": params,
        "per_block": per_block,
        "totals": totals,
        "verdict": verdict,
    }


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("census_ir", help="Original/census IR JSON path")
    parser.add_argument("post_ir", help="Rebuilt/post IR JSON path")
    parser.add_argument("--out-json", help="Optional report output path")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    report = centerline_topology_gate_report(load_ir(args.census_ir), load_ir(args.post_ir))
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.out_json:
        Path(args.out_json).write_text(f"{text}\n", encoding="utf-8")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
