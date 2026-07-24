#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic wall-pair candidate claims over DWG graph IR line entities."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from typing import Any

_SCHEMA = "ariadne.semantic.wall_pairs.v0"
_MODELSPACE = "__modelspace__"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _point2(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    coords = value[:3]
    if not all(_is_number(coord) for coord in coords):
        return None
    return float(value[0]), float(value[1])


def _angle_mod_pi(dx: float, dy: float) -> float:
    return math.atan2(dy, dx) % math.pi


def _angle_diff(a: float, b: float) -> float:
    diff = abs(a - b)
    return min(diff, math.pi - diff)


def _mean_angle(a: float, b: float) -> float:
    y = math.sin(2.0 * a) + math.sin(2.0 * b)
    x = math.cos(2.0 * a) + math.cos(2.0 * b)
    return (0.5 * math.atan2(y, x)) % math.pi


def _line_record(entity: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(entity, dict) or entity.get("dxf_name") != "LINE":
        return None
    handle = entity.get("handle")
    geometry = entity.get("geometry")
    if not isinstance(handle, str) or not handle or not isinstance(geometry, dict):
        return None
    start = _point2(geometry.get("start"))
    end = _point2(geometry.get("end"))
    if start is None or end is None:
        return None

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= 0.0:
        return None

    return {
        "index": index,
        "handle": handle,
        "layer": entity.get("layer"),
        "start": start,
        "end": end,
        "dx": dx,
        "dy": dy,
        "length": length,
        "angle": _angle_mod_pi(dx, dy),
    }


def _gap_and_overlap(a: dict[str, Any], b: dict[str, Any]) -> tuple[float, float]:
    longer, shorter = (a, b) if a["length"] >= b["length"] else (b, a)
    ux = longer["dx"] / longer["length"]
    uy = longer["dy"] / longer["length"]
    sx = (shorter["start"][0] + shorter["end"][0]) * 0.5
    sy = (shorter["start"][1] + shorter["end"][1]) * 0.5
    gap = abs((sx - longer["start"][0]) * uy - (sy - longer["start"][1]) * ux)

    def project(point: tuple[float, float]) -> float:
        return (point[0] - longer["start"][0]) * ux + (point[1] - longer["start"][1]) * uy

    long_min, long_max = 0.0, longer["length"]
    short_a = project(shorter["start"])
    short_b = project(shorter["end"])
    short_min, short_max = sorted((short_a, short_b))
    overlap = max(0.0, min(long_max, short_max) - max(long_min, short_min))
    return gap, overlap / shorter["length"]


def _confidence(overlap_ratio: float, gap: float, gap_min: float, gap_max: float) -> float:
    """70% clamped overlap plus 30% normalized reciprocal gap within gap_range."""
    overlap_score = min(1.0, max(0.0, overlap_ratio))
    if gap > 0.0 and gap_min > 0.0 and gap_max > gap_min:
        denom = (1.0 / gap_min) - (1.0 / gap_max)
        gap_score = ((1.0 / gap) - (1.0 / gap_max)) / denom if denom else 1.0
    elif gap_max > gap_min:
        gap_score = (gap_max - gap) / (gap_max - gap_min)
    else:
        gap_score = 1.0
    gap_score = min(1.0, max(0.0, gap_score))
    return min(1.0, max(0.0, 0.7 * overlap_score + 0.3 * gap_score))


def _claim_for_pair(
    a: dict[str, Any],
    b: dict[str, Any],
    *,
    angle_tol_rad: float,
    gap: float,
    overlap_ratio: float,
    gap_min: float,
    gap_max: float,
) -> dict[str, Any]:
    if a["handle"] <= b["handle"]:
        first, second = a, b
    else:
        first, second = b, a
    conf = _confidence(overlap_ratio, gap, gap_min, gap_max)
    return {
        "kind": "wall_pair_candidate",
        "pair": [first["handle"], second["handle"]],
        "gap": gap,
        "overlap_ratio": overlap_ratio,
        "angle": _mean_angle(a["angle"], b["angle"]),
        "layers": [first["layer"], second["layer"]],
        "conf": conf,
        "evidence": {
            "parallel_within": angle_tol_rad,
            "gap": gap,
            "overlap_ratio": overlap_ratio,
        },
    }


def propose_wall_pairs(
    def_entities: list,
    *,
    angle_tol_rad: float = 0.005,
    gap_range: tuple[float, float] = (30.0, 500.0),
    min_overlap_ratio: float = 0.5,
    max_pairs_per_line: int = 4,
) -> list[dict[str, Any]]:
    """Return bounded wall-pair candidate claims for near-parallel LINE segments."""
    if angle_tol_rad <= 0.0 or max_pairs_per_line <= 0:
        return []
    gap_min, gap_max = float(gap_range[0]), float(gap_range[1])
    if gap_max < gap_min:
        return []

    lines: list[dict[str, Any]] = []
    for index, entity in enumerate(def_entities if isinstance(def_entities, list) else []):
        line = _line_record(entity, index)
        if line is not None:
            lines.append(line)
    if len(lines) < 2:
        return []

    period = max(1, int(round(math.pi / angle_tol_rad)))
    buckets: dict[int, list[int]] = defaultdict(list)
    for idx, line in enumerate(lines):
        buckets[round(line["angle"] / angle_tol_rad) % period].append(idx)

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for bucket_key in sorted(buckets):
        for offset in (-1, 0, 1):
            other_key = (bucket_key + offset) % period
            if other_key not in buckets:
                continue
            for idx_a in buckets[bucket_key]:
                for idx_b in buckets[other_key]:
                    if idx_a >= idx_b:
                        continue
                    pair_key = (idx_a, idx_b)
                    if pair_key in seen:
                        continue
                    seen.add(pair_key)
                    a = lines[idx_a]
                    b = lines[idx_b]
                    if _angle_diff(a["angle"], b["angle"]) > angle_tol_rad:
                        continue
                    gap, overlap_ratio = _gap_and_overlap(a, b)
                    if not (gap_min <= gap <= gap_max and overlap_ratio >= min_overlap_ratio):
                        continue
                    claim = _claim_for_pair(
                        a,
                        b,
                        angle_tol_rad=angle_tol_rad,
                        gap=gap,
                        overlap_ratio=overlap_ratio,
                        gap_min=gap_min,
                        gap_max=gap_max,
                    )
                    claim["_line_indices"] = pair_key
                    candidates.append(claim)

    counts: dict[int, int] = defaultdict(int)
    selected: list[dict[str, Any]] = []
    candidates.sort(key=lambda claim: (-claim["overlap_ratio"], claim["pair"][0], claim["pair"][1]))
    for claim in candidates:
        idx_a, idx_b = claim["_line_indices"]
        if counts[idx_a] >= max_pairs_per_line or counts[idx_b] >= max_pairs_per_line:
            continue
        counts[idx_a] += 1
        counts[idx_b] += 1
        claim.pop("_line_indices", None)
        selected.append(claim)

    selected.sort(key=lambda claim: (-claim["conf"], claim["pair"][0], claim["pair"][1]))
    return selected


def propose_for_ir(ir: dict, *, def_name: str | None = None, **kw: Any) -> dict[str, Any]:
    """Run wall-pair proposal for block definitions, or modelspace via __modelspace__."""
    per_def: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(ir, dict):
        ir = {}

    if def_name == _MODELSPACE:
        entities = ir.get("entities") if isinstance(ir.get("entities"), list) else []
        per_def[_MODELSPACE] = propose_wall_pairs(entities, **kw)
    else:
        for block_def in ir.get("block_definitions") or []:
            if not isinstance(block_def, dict):
                continue
            name = block_def.get("name")
            if not isinstance(name, str) or not name:
                continue
            if def_name is not None and name != def_name:
                continue
            entities = block_def.get("def_entities") if isinstance(block_def.get("def_entities"), list) else []
            per_def[name] = propose_wall_pairs(entities, **kw)
            if def_name is not None:
                break

    return {
        "schema": _SCHEMA,
        "per_def": per_def,
        "totals": {
            "defs": len(per_def),
            "claims": sum(len(claims) for claims in per_def.values()),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ir", required=True)
    parser.add_argument("--def", dest="def_name")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    with open(args.ir, "r", encoding="utf-8-sig") as fh:
        ir = json.load(fh)
    report = propose_for_ir(ir, def_name=args.def_name)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
