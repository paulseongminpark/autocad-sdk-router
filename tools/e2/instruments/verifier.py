#!/usr/bin/env python3
"""Label-blind verifier for claims about complete wall-handle sets.

The core verifier consumes only SEG-IR and a claimed list of handles.  It never
reads the SEG-IR ``label`` field.  Truth ledgers are confined to the fixed-seed
FAR/FRR audit harness, where they are used to construct true and procedurally
wrong claims; they are never passed to ``analyze_seg_ir`` or ``verify_claim``.

Examples:
  python verifier.py --selftest
  python verifier.py --seg-ir drawing.seg.json --claim claim.json
  python verifier.py --build --n 504 --seed 20260718
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
import sys
import tempfile
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
GEN2_PATH = Path(
    r"D:\dev\99_tools\autocad-sdk-router\tools\e2\gen2\gen2.py"
)
SCHEMA = "e2.wall-claim-verifier.v1"
AUDIT_SCHEMA = "e2.wall-claim-verifier.audit.v1"
DEFAULT_AUDIT_SEED = 20260718
DEFAULT_AUDIT_N = 504
PERTURBATION_NAMES = (
    "wall_remove_single",
    "wall_remove_pair",
    "lure_add",
    "neighbor_swap",
    "pair_swap",
    "orphan_add",
)


@dataclass(frozen=True)
class Segment:
    key: str
    sid: str
    handle: str | None
    p0: tuple[float, float]
    p1: tuple[float, float]
    layer: str
    kind: str

    @property
    def length(self) -> float:
        return math.hypot(self.p1[0] - self.p0[0], self.p1[1] - self.p0[1])

    @property
    def angle_deg(self) -> float:
        return math.degrees(
            math.atan2(self.p1[1] - self.p0[1], self.p1[0] - self.p0[0])
        ) % 180.0

    @property
    def midpoint(self) -> tuple[float, float]:
        return ((self.p0[0] + self.p1[0]) / 2.0, (self.p0[1] + self.p1[1]) / 2.0)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _finite_point(value: Any) -> tuple[float, float] | None:
    try:
        x = float(value[0])
        y = float(value[1])
    except (IndexError, KeyError, TypeError, ValueError):
        return None
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    return (x, y)


def _angle_diff_deg(a: float, b: float) -> float:
    difference = abs(a - b) % 180.0
    return min(difference, 180.0 - difference)


def _unit(p0: tuple[float, float], p1: tuple[float, float]) -> tuple[float, float]:
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy)
    if length <= 0.0:
        return (0.0, 0.0)
    return (dx / length, dy / length)


def _projection(point: tuple[float, float], origin: tuple[float, float],
                direction: tuple[float, float]) -> float:
    return (
        (point[0] - origin[0]) * direction[0]
        + (point[1] - origin[1]) * direction[1]
    )


def _overlap_ratio(a: Segment, b: Segment) -> float:
    direction = _unit(a.p0, a.p1)
    if direction == (0.0, 0.0):
        return 0.0
    aa = sorted((_projection(a.p0, a.p0, direction), _projection(a.p1, a.p0, direction)))
    bb = sorted((_projection(b.p0, a.p0, direction), _projection(b.p1, a.p0, direction)))
    overlap = max(0.0, min(aa[1], bb[1]) - max(aa[0], bb[0]))
    denominator = min(a.length, b.length)
    return overlap / denominator if denominator > 0 else 0.0


def _perpendicular_distance(point: tuple[float, float], line: Segment) -> float:
    direction = _unit(line.p0, line.p1)
    if direction == (0.0, 0.0):
        return float("inf")
    dx, dy = point[0] - line.p0[0], point[1] - line.p0[1]
    return abs(dx * direction[1] - dy * direction[0])


def _lateral_offset(a: Segment, b: Segment) -> float:
    return (
        _perpendicular_distance(b.midpoint, a)
        + _perpendicular_distance(a.midpoint, b)
    ) / 2.0


def _point_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _segments_intersect(a: Segment, b: Segment, epsilon: float = 1e-9) -> bool:
    p = a.p0
    r = (a.p1[0] - a.p0[0], a.p1[1] - a.p0[1])
    q = b.p0
    s = (b.p1[0] - b.p0[0], b.p1[1] - b.p0[1])
    cross = r[0] * s[1] - r[1] * s[0]
    if abs(cross) < epsilon:
        return False
    qp = (q[0] - p[0], q[1] - p[1])
    t = (qp[0] * s[1] - qp[1] * s[0]) / cross
    u = (qp[0] * r[1] - qp[1] * r[0]) / cross
    return -epsilon <= t <= 1.0 + epsilon and -epsilon <= u <= 1.0 + epsilon


def _wallish_layer(layer: str) -> bool:
    """Policy-visible CAD metadata test; this is not SEG-IR truth ``label``."""
    normalized = "".join(ch if ch.isalnum() else " " for ch in (layer or "").upper())
    tokens = set(normalized.split())
    return bool(tokens & {"WALL", "WALLS", "WA", "BEARING", "벽"})


def _natural_handle_key(value: str) -> tuple[int, int | str]:
    try:
        return (0, int(value, 16))
    except ValueError:
        return (1, value)


def _canonical_handles(values: Iterable[Any]) -> list[str]:
    return sorted({str(value) for value in values}, key=_natural_handle_key)


def _parse_segments(seg_ir: Mapping[str, Any]) -> tuple[list[Segment], list[str]]:
    errors: list[str] = []
    if seg_ir.get("ir") != "seg.v1":
        errors.append("invalid_ir_schema")
    raw_segments = seg_ir.get("segments")
    if not isinstance(raw_segments, list):
        return [], errors + ["segments_not_list"]
    parsed: list[Segment] = []
    seen_sids: set[str] = set()
    for index, raw in enumerate(raw_segments):
        if not isinstance(raw, Mapping):
            errors.append(f"segment_not_object:{index}")
            continue
        sid = str(raw.get("sid") or f"segment_{index:06d}")
        if sid in seen_sids:
            errors.append(f"duplicate_sid:{sid}")
        seen_sids.add(sid)
        pts = raw.get("pts")
        if not isinstance(pts, list) or len(pts) < 2:
            errors.append(f"invalid_points:{sid}")
            continue
        p0 = _finite_point(pts[0])
        p1 = _finite_point(pts[-1])
        if p0 is None or p1 is None or _point_distance(p0, p1) <= 1e-9:
            errors.append(f"degenerate_segment:{sid}")
            continue
        handle_value = raw.get("handle")
        handle = None if handle_value in (None, "") else str(handle_value)
        key = handle or sid
        # Deliberately do not access raw.get("label").
        parsed.append(
            Segment(
                key=key,
                sid=sid,
                handle=handle,
                p0=p0,
                p1=p1,
                layer=str(raw.get("layer") or ""),
                kind=str(raw.get("kind") or "unknown"),
            )
        )
    if not parsed:
        errors.append("no_usable_segments")
    return parsed, errors


def _pair_axis(a: Segment, b: Segment) -> tuple[tuple[float, float], tuple[float, float]]:
    """Mid-axis proxy for one qualifying pair, stable under side reversal."""
    if _point_distance(a.p0, b.p0) + _point_distance(a.p1, b.p1) <= (
        _point_distance(a.p0, b.p1) + _point_distance(a.p1, b.p0)
    ):
        b0, b1 = b.p0, b.p1
    else:
        b0, b1 = b.p1, b.p0
    return (
        ((a.p0[0] + b0[0]) / 2.0, (a.p0[1] + b0[1]) / 2.0),
        ((a.p1[0] + b1[0]) / 2.0, (a.p1[1] + b1[1]) / 2.0),
    )


def _topology_signature(pair_records: Sequence[Mapping[str, Any]],
                        selected: set[str], snap: float) -> dict[str, Any]:
    nodes = [record for record in pair_records if set(record["handles"]) <= selected]
    adjacency: dict[int, set[int]] = {index: set() for index in range(len(nodes))}
    for i, left in enumerate(nodes):
        la0, la1 = left["axis"]
        left_segment = Segment("", "", None, la0, la1, "", "axis")
        for j in range(i + 1, len(nodes)):
            right = nodes[j]
            if set(left["handles"]) == set(right["handles"]):
                continue
            rb0, rb1 = right["axis"]
            right_segment = Segment("", "", None, rb0, rb1, "", "axis")
            endpoint_close = min(
                _point_distance(pa, pb)
                for pa in (la0, la1)
                for pb in (rb0, rb1)
            ) <= snap
            if endpoint_close or _segments_intersect(left_segment, right_segment):
                adjacency[i].add(j)
                adjacency[j].add(i)
    components = 0
    unseen = set(adjacency)
    while unseen:
        components += 1
        queue = deque([unseen.pop()])
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
    degrees = [len(adjacency[index]) for index in range(len(nodes))]
    return {
        "pair_nodes": len(nodes),
        "junction_edges": sum(degrees) // 2,
        "components": components,
        "isolated_pair_nodes": sum(degree == 0 for degree in degrees),
        "open_pair_nodes": sum(degree <= 1 for degree in degrees),
    }


def analyze_seg_ir(seg_ir: Mapping[str, Any], *, angle_tol_deg: float = 5.0,
                   overlap_min: float = 0.65,
                   thickness_band_mm: tuple[float, float] = (50.0, 400.0)) -> dict[str, Any]:
    """Build a label-blind geometric model once for one SEG-IR drawing."""
    segments, errors = _parse_segments(seg_ir)
    scale_raw = seg_ir.get("scale_mm_per_unit")
    try:
        scale = float(scale_raw) if scale_raw is not None else 1.0
    except (TypeError, ValueError):
        scale = float("nan")
    if not math.isfinite(scale) or scale <= 0:
        errors.append("invalid_scale_mm_per_unit")
        scale = 1.0
    thickness_lo = thickness_band_mm[0] / scale
    thickness_hi = thickness_band_mm[1] / scale
    pair_by_handles: dict[tuple[str, str], dict[str, Any]] = {}
    support: dict[str, set[str]] = defaultdict(set)
    near_parallel: dict[str, set[str]] = defaultdict(set)
    by_handle: dict[str, list[Segment]] = defaultdict(list)
    for segment in segments:
        by_handle[segment.key].append(segment)
    for i, left in enumerate(segments):
        for right in segments[i + 1:]:
            if left.key == right.key:
                continue
            if _angle_diff_deg(left.angle_deg, right.angle_deg) > angle_tol_deg:
                continue
            overlap = _overlap_ratio(left, right)
            if overlap < overlap_min:
                continue
            near_parallel[left.key].add(right.key)
            near_parallel[right.key].add(left.key)
            offset = _lateral_offset(left, right)
            if not (thickness_lo <= offset <= thickness_hi):
                continue
            pair_key = tuple(sorted((left.key, right.key), key=_natural_handle_key))
            candidate = {
                "handles": list(pair_key),
                "overlap": overlap,
                "thickness_units": offset,
                "thickness_mm": offset * scale,
                "axis": _pair_axis(left, right),
                "layers": [left.layer, right.layer],
            }
            previous = pair_by_handles.get(pair_key)
            ranking = (candidate["overlap"], -abs(candidate["thickness_mm"] - 200.0))
            previous_ranking = (
                (previous["overlap"], -abs(previous["thickness_mm"] - 200.0))
                if previous else None
            )
            if previous is None or ranking > previous_ranking:
                pair_by_handles[pair_key] = candidate
            support[left.key].add(right.key)
            support[right.key].add(left.key)
    all_pairs = sorted(
        pair_by_handles.values(),
        key=lambda item: tuple(_natural_handle_key(value) for value in item["handles"]),
    )
    wallish_handles = {
        key for key, records in by_handle.items()
        if records and all(_wallish_layer(record.layer) for record in records)
    }
    expected_handles = {
        key for key in wallish_handles
        if any(partner in wallish_handles for partner in support.get(key, set()))
    }
    expected_pairs = [
        record for record in all_pairs
        if set(record["handles"]) <= expected_handles
        and all(_wallish_layer(layer) for layer in record["layers"])
    ]
    junction_snap = max(6.0 / scale, 0.7 * thickness_hi)
    expected_topology = _topology_signature(expected_pairs, expected_handles, junction_snap)
    centroids = {
        key: (
            sum(record.midpoint[0] for record in records) / len(records),
            sum(record.midpoint[1] for record in records) / len(records),
        )
        for key, records in by_handle.items()
    }
    return {
        "errors": errors,
        "segments": segments,
        "by_handle": by_handle,
        "centroids": centroids,
        "universe_handles": set(by_handle),
        "wallish_handles": wallish_handles,
        "expected_handles": expected_handles,
        "support": support,
        "near_parallel": near_parallel,
        "all_pairs": all_pairs,
        "expected_pairs": expected_pairs,
        "expected_topology": expected_topology,
        "junction_snap": junction_snap,
        "params": {
            "angle_tol_deg": angle_tol_deg,
            "overlap_min": overlap_min,
            "thickness_band_mm": list(thickness_band_mm),
            "scale_mm_per_unit": scale,
        },
    }


def verify_claim(seg_ir: Mapping[str, Any], claimed_handles: Sequence[Any],
                 *, analysis: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return an accept/reject verdict and decomposed constructive evidence."""
    model = dict(analysis) if analysis is not None else analyze_seg_ir(seg_ir)
    if not isinstance(claimed_handles, Sequence) or isinstance(claimed_handles, (str, bytes)):
        raw_claim: list[str] = []
        claim_type_error = True
    else:
        raw_claim = [str(value) for value in claimed_handles]
        claim_type_error = False
    counts = Counter(raw_claim)
    duplicates = _canonical_handles(key for key, amount in counts.items() if amount > 1)
    claimed = set(raw_claim)
    universe = set(model["universe_handles"])
    expected = set(model["expected_handles"])
    missing = expected - claimed
    extra = claimed - expected
    unknown = claimed - universe
    nonwall_layer = claimed - set(model["wallish_handles"])
    orphan_handles = {
        key for key in claimed
        if not (set(model["support"].get(key, set())) & claimed)
    }
    no_thickness_match = {
        key for key in claimed
        if key in universe
        and model["near_parallel"].get(key)
        and not model["support"].get(key)
    }
    claimed_pairs = [
        record for record in model["all_pairs"]
        if set(record["handles"]) <= claimed
    ]
    claimed_wall_pairs = [
        record for record in model["expected_pairs"]
        if set(record["handles"]) <= claimed
    ]
    claimed_topology = _topology_signature(
        model["expected_pairs"], claimed, model["junction_snap"]
    )
    topology_matches = claimed_topology == model["expected_topology"]
    checks = {
        "input_integrity": {
            "ok": not claim_type_error and not model["errors"] and not unknown and not duplicates,
            "schema_errors": list(model["errors"]),
            "claim_type_error": claim_type_error,
            "unknown_handles": _canonical_handles(unknown),
            "duplicate_handles": duplicates,
        },
        "sentinels": {
            "ok": bool(claimed) and claimed != universe,
            "empty_claim": not claimed,
            "whole_universe_claim": bool(universe) and claimed == universe,
        },
        "parallel_pairs": {
            "ok": bool(claimed) and not orphan_handles,
            "qualifying_pair_count": len(claimed_pairs),
            "wall_pair_count": len(claimed_wall_pairs),
            "orphan_handles": _canonical_handles(orphan_handles),
        },
        "thickness_consistency": {
            "ok": not no_thickness_match and bool(claimed_pairs),
            "band_mm": list(model["params"]["thickness_band_mm"]),
            "observed_mm": [round(record["thickness_mm"], 6) for record in claimed_pairs],
            "out_of_band_parallel_handles": _canonical_handles(no_thickness_match),
        },
        "junction_closure": {
            "ok": topology_matches and not missing,
            "claimed_topology": claimed_topology,
            "candidate_topology": model["expected_topology"],
            "missing_candidate_handles": _canonical_handles(missing),
        },
        "orphan_segments": {
            "ok": not orphan_handles,
            "handles": _canonical_handles(orphan_handles),
            "segment_count": sum(len(model["by_handle"].get(key, [])) for key in orphan_handles),
        },
        "layer_metadata": {
            "ok": not nonwall_layer,
            "nonwall_layer_handles": _canonical_handles(nonwall_layer),
            "note": "policy-visible CAD metadata; SEG-IR label is not read",
        },
        "set_completeness": {
            "ok": claimed == expected and bool(expected),
            "expected_count": len(expected),
            "claimed_count": len(claimed),
            "missing_handles": _canonical_handles(missing),
            "extra_handles": _canonical_handles(extra),
        },
    }
    accepted = all(check["ok"] for check in checks.values())
    reasons: list[str] = []
    for name, check in checks.items():
        if not check["ok"]:
            reasons.append(name)
    return {
        "schema": SCHEMA,
        "drawing_id": str(seg_ir.get("drawing_id") or ""),
        "verdict": "accept" if accepted else "reject",
        "accepted": accepted,
        "reason_codes": reasons,
        "claim": {
            "raw_count": len(raw_claim),
            "unique_count": len(claimed),
            "handles": _canonical_handles(claimed),
        },
        "evidence": checks,
        "parameters": model["params"],
        "label_usage": "none",
    }


def _fixture() -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    segments: list[dict[str, Any]] = []

    def add(handle: str, p0: tuple[float, float], p1: tuple[float, float],
            layer: str, label: str) -> None:
        segments.append({
            "sid": f"s{len(segments) + 1:04d}",
            "handle": handle,
            "pts": [list(p0), list(p1)],
            "layer": layer,
            "kind": "line",
            "label": label,
            "source": "synth",
        })

    add("A1", (0, 0), (2000, 0), "A-WALL", "other")
    add("A2", (0, 200), (2000, 200), "A-WALL", "other")
    add("B1", (0, 1800), (2000, 1800), "A-WALL", "other")
    add("B2", (0, 2000), (2000, 2000), "A-WALL", "other")
    add("C1", (0, 0), (0, 2000), "A-WALL", "other")
    add("C2", (200, 0), (200, 2000), "A-WALL", "other")
    add("D1", (1800, 0), (1800, 2000), "A-WALL", "other")
    add("D2", (2000, 0), (2000, 2000), "A-WALL", "other")
    add("L1", (3000, 3000), (4700, 3000), "DIM", "wall")
    add("L2", (3000, 3180), (4700, 3180), "DIM", "wall")
    add("F1", (5200, 3000), (5200, 4200), "DOOR", "wall")
    add("F2", (5320, 3000), (5320, 4200), "DOOR", "wall")
    add("O1", (6200, 3000), (6550, 3290), "ANNO", "wall")
    ir = {
        "ir": "seg.v1",
        "drawing_id": "selftest",
        "units": "mm",
        "scale_mm_per_unit": 1.0,
        "segments": segments,
    }
    truth = ["A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2"]
    ledger = {
        "walls": [
            {"handles": ["A1", "A2"]},
            {"handles": ["B1", "B2"]},
            {"handles": ["C1", "C2"]},
            {"handles": ["D1", "D2"]},
        ],
        "wall_handles_flat": truth,
        "class_of_handle": {
            **{handle: "wall" for handle in truth},
            "L1": "dimension_helper", "L2": "dimension_helper",
            "F1": "door_frame", "F2": "door_frame", "O1": "direction_arrow",
        },
    }
    return ir, truth, ledger


def _paired_negative_pair(model: Mapping[str, Any], negatives: set[str]) -> tuple[str, str]:
    for record in model["all_pairs"]:
        left, right = record["handles"]
        if left in negatives and right in negatives:
            return left, right
    ordered = _canonical_handles(negatives)
    if len(ordered) < 2:
        raise ValueError("audit drawing lacks two negative handles")
    return ordered[0], ordered[1]


def _build_perturbations(model: Mapping[str, Any], truth: Mapping[str, Any],
                         ordinal: int) -> dict[str, list[str]]:
    true_handles = set(map(str, truth.get("wall_handles_flat", [])))
    walls = [
        [str(value) for value in wall.get("handles", [])]
        for wall in truth.get("walls", [])
        if wall.get("handles")
    ]
    if not true_handles or not walls:
        raise ValueError("truth ledger has no wall handles/walls")
    classes = {str(key): str(value) for key, value in truth.get("class_of_handle", {}).items()}
    negatives = {
        key for key, value in classes.items()
        if value != "wall" and key in model["universe_handles"]
    }
    if not negatives:
        raise ValueError("truth ledger has no geometric negative handles")
    ordered_true = _canonical_handles(true_handles)
    removed = ordered_true[ordinal % len(ordered_true)]
    wall = walls[ordinal % len(walls)]
    paired_left, paired_right = _paired_negative_pair(model, negatives)
    paired_negatives = {paired_left, paired_right}
    orphan_negatives = {
        key for key in negatives
        if not (set(model["support"].get(key, set())) & negatives)
    }
    orphan = _canonical_handles(orphan_negatives or negatives)[ordinal % len(orphan_negatives or negatives)]
    lure = _canonical_handles(paired_negatives)[ordinal % 2]
    removed_centroid = model["centroids"][removed]
    neighbor = min(
        negatives,
        key=lambda key: (
            _point_distance(removed_centroid, model["centroids"][key]),
            _natural_handle_key(key),
        ),
    )

    def canon(values: Iterable[str]) -> list[str]:
        return _canonical_handles(values)

    return {
        "wall_remove_single": canon(true_handles - {removed}),
        "wall_remove_pair": canon(true_handles - set(wall)),
        "lure_add": canon(true_handles | {lure}),
        "neighbor_swap": canon((true_handles - {removed}) | {neighbor}),
        "pair_swap": canon((true_handles - set(wall)) | paired_negatives),
        "orphan_add": canon(true_handles | {orphan}),
    }


def run_selftest(*, emit: bool = True) -> tuple[bool, list[str]]:
    ir, true_handles, ledger = _fixture()
    model = analyze_seg_ir(ir)
    perturbations = _build_perturbations(model, ledger, 0)
    lines = ["=== verifier selftest ==="]
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str) -> None:
        status = "OK" if condition else "FAIL"
        lines.append(f"[{status}] {name}: {detail}")
        if not condition:
            failures.append(name)

    true_result = verify_claim(ir, true_handles, analysis=model)
    check("obvious_true", true_result["accepted"], f"verdict={true_result['verdict']}")
    false_result = verify_claim(ir, ["L1", "L2"], analysis=model)
    check("obvious_false", not false_result["accepted"],
          f"verdict={false_result['verdict']} reasons={false_result['reason_codes']}")
    empty_result = verify_claim(ir, [], analysis=model)
    check("degenerate_empty", not empty_result["accepted"],
          f"verdict={empty_result['verdict']} reasons={empty_result['reason_codes']}")
    all_handles = _canonical_handles(model["universe_handles"])
    all_result = verify_claim(ir, all_handles, analysis=model)
    check("degenerate_whole_universe", not all_result["accepted"],
          f"verdict={all_result['verdict']} reasons={all_result['reason_codes']}")
    poisoned = json.loads(json.dumps(ir))
    for segment in poisoned["segments"]:
        segment["label"] = "wall" if segment["handle"] not in true_handles else "other"
    poisoned_result = verify_claim(poisoned, true_handles)
    check("label_independence", poisoned_result["accepted"] == true_result["accepted"],
          f"original={true_result['verdict']} poisoned={poisoned_result['verdict']}")
    for name in PERTURBATION_NAMES:
        result = verify_claim(ir, perturbations[name], analysis=model)
        check(f"perturbation_{name}", not result["accepted"],
              f"verdict={result['verdict']} reasons={result['reason_codes']}")
    if failures:
        lines.append(f"SELFTEST_RESULT: FAIL ({len(failures)}): {', '.join(failures)}")
    else:
        lines.append("SELFTEST_RESULT: PASS")
    if emit:
        print("\n".join(lines))
    return not failures, lines


def _load_gen2():
    if not GEN2_PATH.is_file():
        raise FileNotFoundError(f"gen2 source not found: {GEN2_PATH}")
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("e2_gen2_readonly", GEN2_PATH)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load gen2 module from {GEN2_PATH}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = previous


def _append_ir_segment(segments: list[dict[str, Any]], handle: str | None,
                       p0: Sequence[float], p1: Sequence[float], layer: str,
                       kind: str) -> None:
    a = (float(p0[0]), float(p0[1]))
    b = (float(p1[0]), float(p1[1]))
    if _point_distance(a, b) <= 1e-9:
        return
    segments.append({
        "sid": f"s{len(segments) + 1:06d}",
        "handle": handle,
        "pts": [[a[0], a[1]], [b[0], b[1]]],
        "layer": layer,
        "kind": kind,
        "label": "unknown",
        "source": "synth",
    })


def _dxf_to_seg_ir(dxf_path: Path, drawing_id: str) -> dict[str, Any]:
    """Measurement-only adapter; ezdxf is not used by the core verifier."""
    import ezdxf  # allowed only for generated-pack replay

    document = ezdxf.readfile(dxf_path)
    segments: list[dict[str, Any]] = []
    for entity in document.modelspace():
        entity_type = entity.dxftype()
        handle = str(entity.dxf.handle) if entity.dxf.handle is not None else None
        layer = str(entity.dxf.layer or "")
        if entity_type == "LINE":
            _append_ir_segment(segments, handle, entity.dxf.start, entity.dxf.end, layer, "line")
        elif entity_type == "LWPOLYLINE":
            points = [(float(x), float(y)) for x, y in entity.get_points("xy")]
            pairs = list(zip(points, points[1:]))
            if entity.closed and len(points) > 2:
                pairs.append((points[-1], points[0]))
            for p0, p1 in pairs:
                _append_ir_segment(segments, handle, p0, p1, layer, "poly-edge")
        elif entity_type == "POLYLINE":
            points = [(float(vertex.dxf.location.x), float(vertex.dxf.location.y))
                      for vertex in entity.vertices]
            pairs = list(zip(points, points[1:]))
            if entity.is_closed and len(points) > 2:
                pairs.append((points[-1], points[0]))
            for p0, p1 in pairs:
                _append_ir_segment(segments, handle, p0, p1, layer, "poly-edge")
        elif entity_type == "ARC":
            sweep = (float(entity.dxf.end_angle) - float(entity.dxf.start_angle)) % 360.0
            chord_count = max(4, int(math.ceil(sweep / 7.5)))
            angles = [
                math.radians(float(entity.dxf.start_angle) + sweep * index / chord_count)
                for index in range(chord_count + 1)
            ]
            center = entity.dxf.center
            radius = float(entity.dxf.radius)
            points = [
                (float(center.x) + radius * math.cos(angle),
                 float(center.y) + radius * math.sin(angle))
                for angle in angles
            ]
            for p0, p1 in zip(points, points[1:]):
                _append_ir_segment(segments, handle, p0, p1, layer, "arc-chord")
        elif entity_type == "CIRCLE":
            center = entity.dxf.center
            radius = float(entity.dxf.radius)
            points = [
                (float(center.x) + radius * math.cos(2.0 * math.pi * index / 32),
                 float(center.y) + radius * math.sin(2.0 * math.pi * index / 32))
                for index in range(33)
            ]
            for p0, p1 in zip(points, points[1:]):
                _append_ir_segment(segments, handle, p0, p1, layer, "arc-chord")
    return {
        "ir": "seg.v1",
        "drawing_id": drawing_id,
        "units": "mm",
        "scale_mm_per_unit": 1.0,
        "segments": segments,
    }


def run_measurement(n: int, seed: int, *, progress: bool = True) -> dict[str, Any]:
    if n < 500:
        raise ValueError("FAR/FRR audit requires n >= 500 true drawings")
    gen2 = _load_gen2()
    per_tier = int(math.ceil(n / len(gen2.TIERS)))
    temp_root = Path(tempfile.mkdtemp(prefix=".audit_pack_", dir=SCRIPT_DIR))
    pack_root = temp_root / "pack"
    started = time.perf_counter()
    true_accepts = 0
    true_rejects = 0
    by_perturbation = {
        name: {"n": 0, "accepted": 0, "rejected": 0}
        for name in PERTURBATION_NAMES
    }
    evaluated = 0
    tier_counts: Counter[str] = Counter()
    sample_failures: list[dict[str, Any]] = []
    try:
        if progress:
            print(
                f"generating fixed-seed gen2 pack: tiers={len(gen2.TIERS)} "
                f"n_per_tier={per_tier} generated={per_tier * len(gen2.TIERS)}",
                flush=True,
            )
        gen2.build_pack_root(
            pack_root,
            int(seed),
            per_tier,
            entity_ratios={"LINE": 1.0},
            entity_count=96,
            calibration_pairs=8,
        )
        for tier in gen2.TIERS:
            manifest = json.loads(
                (pack_root / tier / "manifest.json").read_text(encoding="utf-8")
            )
            for entry in manifest["files"]:
                if evaluated >= n:
                    break
                dxf_path = pack_root / tier / entry["dxf"]
                truth_path = pack_root / tier / entry["truth"]
                truth = json.loads(truth_path.read_text(encoding="utf-8"))
                drawing_key = f"{tier}/{entry['drawing_id']}@{entry['seed']}"
                seg_ir = _dxf_to_seg_ir(dxf_path, drawing_key)
                model = analyze_seg_ir(seg_ir)
                true_handles = [str(value) for value in truth["wall_handles_flat"]]
                true_result = verify_claim(seg_ir, true_handles, analysis=model)
                if true_result["accepted"]:
                    true_accepts += 1
                else:
                    true_rejects += 1
                    if len(sample_failures) < 20:
                        sample_failures.append({
                            "kind": "true_reject",
                            "drawing": drawing_key,
                            "reasons": true_result["reason_codes"],
                            "missing": true_result["evidence"]["set_completeness"]["missing_handles"],
                            "extra": true_result["evidence"]["set_completeness"]["extra_handles"],
                        })
                perturbations = _build_perturbations(model, truth, evaluated)
                for name, handles in perturbations.items():
                    result = verify_claim(seg_ir, handles, analysis=model)
                    record = by_perturbation[name]
                    record["n"] += 1
                    if result["accepted"]:
                        record["accepted"] += 1
                        if len(sample_failures) < 20:
                            sample_failures.append({
                                "kind": "false_accept",
                                "perturbation": name,
                                "drawing": drawing_key,
                                "reasons": result["reason_codes"],
                            })
                    else:
                        record["rejected"] += 1
                evaluated += 1
                tier_counts[tier] += 1
                if progress and evaluated % 50 == 0:
                    print(f"evaluated {evaluated}/{n}", flush=True)
            if evaluated >= n:
                break
        false_n = sum(record["n"] for record in by_perturbation.values())
        false_accepts = sum(record["accepted"] for record in by_perturbation.values())
        false_rejects = sum(record["rejected"] for record in by_perturbation.values())
        for record in by_perturbation.values():
            record["far"] = record["accepted"] / record["n"] if record["n"] else None
        elapsed = time.perf_counter() - started
        return {
            "schema": AUDIT_SCHEMA,
            "measured_utc": datetime.now(timezone.utc).isoformat(),
            "rate_definitions": {
                "far": "false claims accepted / false claims",
                "frr": "true claims rejected / true claims",
            },
            "generator": {
                "path": str(GEN2_PATH),
                "sha256": _sha256(GEN2_PATH),
                "schema": str(gen2.GENERATOR_SCHEMA),
                "base_seed": int(seed),
                "generated_drawings": per_tier * len(gen2.TIERS),
                "evaluated_drawings": evaluated,
                "n_per_tier_generated": per_tier,
                "evaluated_by_tier": dict(sorted(tier_counts.items())),
                "entity_ratios": {"LINE": 1.0},
                "entity_count": 96,
                "calibration_pairs": 8,
            },
            "true_claims": {
                "n": evaluated,
                "accepted": true_accepts,
                "rejected": true_rejects,
                "frr": true_rejects / evaluated if evaluated else None,
            },
            "false_claims": {
                "n": false_n,
                "accepted": false_accepts,
                "rejected": false_rejects,
                "far": false_accepts / false_n if false_n else None,
                "by_perturbation": by_perturbation,
            },
            "runtime_seconds": round(elapsed, 6),
            "sample_failures": sample_failures,
        }
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def _format_rate(value: float | None) -> str:
    return "null" if value is None else f"{value:.9f}"


def _render_report(audit: Mapping[str, Any], selftest_lines: Sequence[str]) -> str:
    true = audit["true_claims"]
    false = audit["false_claims"]
    generator = audit["generator"]
    rows = []
    for name in PERTURBATION_NAMES:
        record = false["by_perturbation"][name]
        rows.append(
            f"| `{name}` | {record['n']} | {record['accepted']} | "
            f"{record['rejected']} | {_format_rate(record['far'])} |"
        )
    failure_text = (
        "없음." if not audit["sample_failures"]
        else "```json\n" + json.dumps(
            audit["sample_failures"], indent=2, ensure_ascii=False, sort_keys=True
        ) + "\n```"
    )
    return f"""# 벽-주장 검증기 빌드 보고서

## 구현 요약

`verifier.py`는 SEG-IR의 기하와 policy-visible CAD 메타데이터만으로 완전한 벽 핸들 집합 주장을 판정한다. `label` 필드는 파싱·분석·판정 어느 경로에서도 읽지 않는다. 평행짝(각도·종방향 겹침), 도면 단위로 환산한 50–400 mm 두께, 짝 중심축의 정션 토폴로지, 고아 핸들, 벽 레이어 메타데이터, 후보 집합 완전성, 빈/전체 주장 센티널을 각각 분리해 출력한다.

판정은 보수적이다. 기하+레이어로 재구성한 후보 전체와 주장이 정확히 같고, 모든 주장 핸들이 두께 대역의 평행짝을 가지며, 후보 정션 토폴로지가 보존되고, 입력/센티널/고아 검사가 모두 성립할 때만 `accept`한다. 진리 원장은 이 함수에 전달되지 않는다.

CLI:

```text
python verifier.py --seg-ir <seg-ir.json> --claim <claim.json-or-json-list>
python verifier.py --selftest
python verifier.py --build --n 504 --seed 20260718
```

## Selftest 전문

```text
{chr(10).join(selftest_lines)}
```

## FAR/FRR 실측

- generator: `{generator['path']}`
- generator SHA-256: `{generator['sha256']}`
- 고정 base seed: `{generator['base_seed']}`
- 생성 도면: {generator['generated_drawings']}건; 평가 도면: {generator['evaluated_drawings']}건 ({generator['evaluated_by_tier']})
- 참 주장: n={true['n']}, accept={true['accepted']}, reject={true['rejected']}, FRR={_format_rate(true['frr'])}
- 거짓 주장: n={false['n']}, accept={false['accepted']}, reject={false['rejected']}, FAR={_format_rate(false['far'])}
- runtime_seconds: {audit['runtime_seconds']}

수치는 고정 시드 audit의 관측값만 기록한다. 자격 판정은 이 빌드 산출물에서 내리지 않는다.

### 교란 종별 FAR

| 절차 교란 | n | accept | reject | FAR |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

교란은 (1) 벽 한쪽 제거, (2) 벽 pair 전체 제거, (3) 벽처럼 보이는 미끼 추가, (4) 공간상 가장 가까운 음성 핸들과 이웃 스왑, (5) 참 pair를 음성 평행 pair로 교체, (6) 평행 지지가 없는 고아 추가다. 각 교란은 모든 평가 도면에 한 번씩 적용했다.

## 감사 경계

- gen2는 `sys.dont_write_bytecode=True` 상태에서 read-only import했고 원본 repo에 쓰지 않았다.
- ezdxf는 audit 중 gen2가 만든 임시 팩을 SEG-IR로 재생하는 경로에서만 lazy import한다. 핵심 verifier는 stdlib만 사용한다.
- 임시 팩은 이 산출 디렉토리 안에서 만들고 측정 종료 시 제거했다.
- `far_frr_numbers.json`에는 수치와 provenance만 있으며 자격 verdict/threshold 비교는 넣지 않았다.

## 미해결·해석 제한

- gen2 v2의 벽 토폴로지는 tier별로 고정되고 seed는 주로 calibration context를 바꾼다. 따라서 n은 서로 다른 재생 seed/팩의 주장 수이지만, 완전히 독립적인 n개 벽 토폴로지 family로 해석하면 안 된다.
- 벽 레이어 메타데이터가 제거·오염된 name-blind SEG-IR에서는 이 보수적 verifier가 거부할 수 있다. 이는 라벨 누출을 피하면서 현재 팩의 hard-negative 평행 구조를 분리하기 위한 명시적 범위다.
- ARC는 audit adapter에서 7.5도 이하 chord로 근사한다. 원본 SEG-IR이 다른 chord 정책을 쓰면 동일 파라미터로 재계측해야 한다.

### 실측 중 이상 표본

{failure_text}

BUILD_COMPLETE: verifier
"""


def build_artifacts(n: int, seed: int) -> int:
    selftest_ok, selftest_lines = run_selftest(emit=True)
    if not selftest_ok:
        print("ERROR: refusing measurement because selftest failed", file=sys.stderr)
        return 1
    audit = run_measurement(n, seed, progress=True)
    audit["verifier_sha256"] = _sha256(Path(__file__).resolve())
    numbers_path = SCRIPT_DIR / "far_frr_numbers.json"
    report_path = SCRIPT_DIR / "REPORT.md"
    _write_json(numbers_path, audit)
    report_path.write_text(_render_report(audit, selftest_lines), encoding="utf-8")
    print(f"wrote {numbers_path}")
    print(f"wrote {report_path}")
    return 0


def _load_claim(value: str) -> list[Any]:
    candidate = Path(value)
    if candidate.is_file():
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    else:
        payload = json.loads(value)
    if isinstance(payload, Mapping):
        payload = payload.get("handles")
    if not isinstance(payload, list):
        raise ValueError("claim must be a JSON list or an object with a handles list")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--selftest", action="store_true")
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--seg-ir", help="SEG-IR JSON path")
    parser.add_argument("--claim", help="claim JSON path or inline JSON list")
    parser.add_argument("--n", type=int, default=DEFAULT_AUDIT_N)
    parser.add_argument("--seed", type=int, default=DEFAULT_AUDIT_SEED)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.selftest:
        ok, _ = run_selftest(emit=True)
        return 0 if ok else 1
    if args.build:
        return build_artifacts(args.n, args.seed)
    if not args.claim:
        print("ERROR: --claim is required with --seg-ir", file=sys.stderr)
        return 2
    try:
        seg_ir = json.loads(Path(args.seg_ir).read_text(encoding="utf-8"))
        claim = _load_claim(args.claim)
        result = verify_claim(seg_ir, claim)
    except Exception as exc:  # noqa: BLE001 - CLI evidence path
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
