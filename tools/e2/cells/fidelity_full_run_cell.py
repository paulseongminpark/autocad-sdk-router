#!/usr/bin/env python3
"""Execute the E2 fidelity_full cell without modifying the source repository.

The source generator, fidelity calculator, and verifier are imported read-only.
All durable artifacts are written beside this script.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import math
import shutil
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import ezdxf
import numpy as np


CELL_ROOT = Path(__file__).resolve().parent
PACK_ROOT = CELL_ROOT / "packs"
SAMPLE_ROOT = CELL_ROOT / "_throughput_pack_sample"
SAMPLE_NUMBERS = CELL_ROOT / "_throughput_sample.json"
SEED_MANIFEST = CELL_ROOT / "seed_manifest.json"
FIDELITY_NUMBERS = CELL_ROOT / "fidelity_numbers.json"
VERIFIER_NUMBERS = CELL_ROOT / "verifier_far_frr_full.json"
REPORT_PATH = CELL_ROOT / "REPORT.md"

REPO_ROOT = Path(r"D:\dev\99_tools\autocad-sdk-router")
GEN2_PATH = REPO_ROOT / "tools" / "e2" / "gen2" / "gen2.py"
FIDELITY_PATH = REPO_ROOT / "tools" / "e2" / "gen2" / "fidelity_stats.py"
VERIFIER_PATH = REPO_ROOT / "tools" / "e2" / "instruments" / "verifier.py"
REFERENCE_FIDELITY = REPO_ROOT / "reports" / "e2" / "s2" / "fidelity_M_v2.json"
REFERENCE_ENTITY = REPO_ROOT / "reports" / "e2" / "s2" / "fidelity_M_v1_tv.json"

BASE_SEED = 20260719
N_PER_TIER = 50
ENTITY_TARGET_COUNT = 1400
CALIBRATION_PAIRS = 600
CLAIM_REPLICATES = 4
ARC_MAX_STEP_DEG = 7.5
CIRCLE_CHORDS = 32
SPLINE_CHORDS = 4
TIERS = ("S", "F", "M")
PERTURBATIONS = (
    "wall_remove_single",
    "wall_remove_pair",
    "lure_add",
    "neighbor_swap",
    "pair_swap",
    "orphan_add",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_module(name: str, path: Path):
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load module: {path}")
        module = importlib.util.module_from_spec(spec)
        # dataclasses resolves postponed annotations through sys.modules while
        # the class decorator runs, so the dynamic module must be registered.
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(name, None)
            raise
        return module
    finally:
        sys.dont_write_bytecode = previous


def load_sources():
    return (
        load_module("e2_fidelity_full_gen2", GEN2_PATH),
        load_module("e2_fidelity_full_stats", FIDELITY_PATH),
        load_module("e2_fidelity_full_verifier", VERIFIER_PATH),
    )


def source_hashes() -> dict[str, str]:
    return {
        "gen2.py": sha256(GEN2_PATH),
        "fidelity_stats.py": sha256(FIDELITY_PATH),
        "verifier.py": sha256(VERIFIER_PATH),
    }


def append_segment(
    segments: list[dict[str, Any]],
    handle: str | None,
    p0: Sequence[float],
    p1: Sequence[float],
    layer: str,
    kind: str,
) -> None:
    a = (float(p0[0]), float(p0[1]))
    b = (float(p1[0]), float(p1[1]))
    if not all(math.isfinite(value) for value in (*a, *b)):
        return
    if math.hypot(a[0] - b[0], a[1] - b[1]) <= 1e-9:
        return
    segments.append(
        {
            "sid": f"s{len(segments) + 1:07d}",
            "handle": handle,
            "pts": [[a[0], a[1]], [b[0], b[1]]],
            "layer": layer,
            "kind": kind,
            "label": "unknown",
            "source": "gen2-full-diversity",
        }
    )


def arc_points(entity: Any) -> list[tuple[float, float]]:
    start = float(entity.dxf.start_angle)
    sweep = (float(entity.dxf.end_angle) - start) % 360.0
    count = max(4, int(math.ceil(sweep / ARC_MAX_STEP_DEG)))
    center = entity.dxf.center
    radius = float(entity.dxf.radius)
    return [
        (
            float(center.x) + radius * math.cos(math.radians(start + sweep * i / count)),
            float(center.y) + radius * math.sin(math.radians(start + sweep * i / count)),
        )
        for i in range(count + 1)
    ]


def circle_points(entity: Any) -> list[tuple[float, float]]:
    center = entity.dxf.center
    radius = float(entity.dxf.radius)
    return [
        (
            float(center.x) + radius * math.cos(2.0 * math.pi * i / CIRCLE_CHORDS),
            float(center.y) + radius * math.sin(2.0 * math.pi * i / CIRCLE_CHORDS),
        )
        for i in range(CIRCLE_CHORDS + 1)
    ]


def spline_points(entity: Any) -> list[tuple[float, float]]:
    try:
        points = list(entity.construction_tool().approximate(segments=SPLINE_CHORDS))
    except Exception:
        points = list(entity.flattening(distance=1.0, segments=SPLINE_CHORDS))
    return [(float(point.x), float(point.y)) for point in points]


def dxf_to_seg_ir(dxf_path: Path, drawing_id: str) -> tuple[dict[str, Any], dict[str, int]]:
    """Convert verifier-relevant geometry using an explicit curve policy.

    This follows verifier.py's adapter for LINE/LWPOLYLINE/POLYLINE/ARC/CIRCLE
    and extends it with a deterministic four-chord SPLINE approximation.
    Non-segment semantic entities remain present in the source pack but are not
    represented in SEG-IR.
    """
    document = ezdxf.readfile(dxf_path)
    segments: list[dict[str, Any]] = []
    source_entities = Counter()
    emitted_by_type = Counter()
    for entity in document.modelspace():
        entity_type = entity.dxftype()
        source_entities[entity_type] += 1
        handle = str(entity.dxf.handle) if entity.dxf.handle is not None else None
        layer = str(getattr(entity.dxf, "layer", "") or "")
        before = len(segments)
        if entity_type == "LINE":
            append_segment(segments, handle, entity.dxf.start, entity.dxf.end, layer, "line")
        elif entity_type == "LWPOLYLINE":
            points = [(float(x), float(y)) for x, y in entity.get_points("xy")]
            pairs = list(zip(points, points[1:]))
            if entity.closed and len(points) > 2:
                pairs.append((points[-1], points[0]))
            for p0, p1 in pairs:
                append_segment(segments, handle, p0, p1, layer, "poly-edge")
        elif entity_type == "POLYLINE":
            points = [
                (float(vertex.dxf.location.x), float(vertex.dxf.location.y))
                for vertex in entity.vertices
            ]
            pairs = list(zip(points, points[1:]))
            if entity.is_closed and len(points) > 2:
                pairs.append((points[-1], points[0]))
            for p0, p1 in pairs:
                append_segment(segments, handle, p0, p1, layer, "poly-edge")
        elif entity_type == "ARC":
            points = arc_points(entity)
            for p0, p1 in zip(points, points[1:]):
                append_segment(segments, handle, p0, p1, layer, "arc-chord")
        elif entity_type == "CIRCLE":
            points = circle_points(entity)
            for p0, p1 in zip(points, points[1:]):
                append_segment(segments, handle, p0, p1, layer, "circle-chord")
        elif entity_type == "SPLINE":
            points = spline_points(entity)
            for p0, p1 in zip(points, points[1:]):
                append_segment(segments, handle, p0, p1, layer, "spline-chord")
        emitted_by_type[entity_type] += len(segments) - before
    return (
        {
            "ir": "seg.v1",
            "drawing_id": drawing_id,
            "units": "mm",
            "scale_mm_per_unit": 1.0,
            "segments": segments,
        },
        {
            "source_entities": sum(source_entities.values()),
            "emitted_segments": len(segments),
            **{f"segments_from_{key}": value for key, value in sorted(emitted_by_type.items())},
        },
    )


def rate_record() -> dict[str, Any]:
    return {"n": 0, "accepted": 0, "rejected": 0}


def observe(record: dict[str, Any], accepted: bool) -> None:
    record["n"] += 1
    record["accepted" if accepted else "rejected"] += 1


def finalize_true(record: dict[str, Any]) -> None:
    record["frr"] = record["rejected"] / record["n"] if record["n"] else None


def finalize_false(record: dict[str, Any]) -> None:
    record["far"] = record["accepted"] / record["n"] if record["n"] else None


def finite_summary(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "min": None, "p05": None, "p50": None, "p95": None, "max": None}
    array = np.asarray(values, dtype=np.float64)
    return {
        "n": int(array.size),
        "min": float(np.min(array)),
        "p05": float(np.quantile(array, 0.05)),
        "p50": float(np.quantile(array, 0.50)),
        "p95": float(np.quantile(array, 0.95)),
        "max": float(np.max(array)),
    }


def two_sample_ks(left: Sequence[float], right: Sequence[float]) -> float | None:
    if not left or not right:
        return None
    a = np.sort(np.asarray(left, dtype=np.float64))
    b = np.sort(np.asarray(right, dtype=np.float64))
    grid = np.sort(np.concatenate((a, b)))
    cdf_a = np.searchsorted(a, grid, side="right") / a.size
    cdf_b = np.searchsorted(b, grid, side="right") / b.size
    return float(np.max(np.abs(cdf_a - cdf_b)))


def total_variation_counts(left: Mapping[Any, int], right: Mapping[Any, int]) -> float | None:
    total_left = sum(left.values())
    total_right = sum(right.values())
    if total_left <= 0 or total_right <= 0:
        return None
    keys = set(left) | set(right)
    return 0.5 * sum(
        abs(left.get(key, 0) / total_left - right.get(key, 0) / total_right)
        for key in keys
    )


def segment_lengths(seg_ir: Mapping[str, Any]) -> list[float]:
    result = []
    for segment in seg_ir["segments"]:
        p0, p1 = segment["pts"][0], segment["pts"][-1]
        result.append(math.hypot(float(p1[0]) - float(p0[0]), float(p1[1]) - float(p0[1])))
    return [value for value in result if value > 0 and math.isfinite(value)]


def topology_degree_and_gaps(model: Mapping[str, Any], normalizer: float) -> tuple[Counter, list[float]]:
    records = list(model["expected_pairs"])
    adjacency = {index: set() for index in range(len(records))}
    segment_class = model["segments"][0].__class__
    for i, left in enumerate(records):
        la0, la1 = left["axis"]
        left_seg = segment_class("", "", None, la0, la1, "", "axis")
        for j in range(i + 1, len(records)):
            right = records[j]
            rb0, rb1 = right["axis"]
            right_seg = segment_class("", "", None, rb0, rb1, "", "axis")
            endpoint_close = min(
                math.hypot(pa[0] - pb[0], pa[1] - pb[1])
                for pa in (la0, la1)
                for pb in (rb0, rb1)
            ) <= model["junction_snap"]
            p = left_seg.p0
            r = (left_seg.p1[0] - p[0], left_seg.p1[1] - p[1])
            q = right_seg.p0
            s = (right_seg.p1[0] - q[0], right_seg.p1[1] - q[1])
            cross = r[0] * s[1] - r[1] * s[0]
            intersects = False
            if abs(cross) >= 1e-9:
                qp = (q[0] - p[0], q[1] - p[1])
                t = (qp[0] * s[1] - qp[1] * s[0]) / cross
                u = (qp[0] * r[1] - qp[1] * r[0]) / cross
                intersects = -1e-9 <= t <= 1.0 + 1e-9 and -1e-9 <= u <= 1.0 + 1e-9
            if endpoint_close or intersects:
                adjacency[i].add(j)
                adjacency[j].add(i)
    degree_counts = Counter(len(neighbors) for neighbors in adjacency.values())
    endpoints = [point for record in records for point in record["axis"]]
    gaps = []
    if normalizer > 0:
        for index, point in enumerate(endpoints):
            distances = [
                math.hypot(point[0] - other[0], point[1] - other[1])
                for j, other in enumerate(endpoints)
                if j != index and (j // 2) != (index // 2)
            ]
            if distances:
                gaps.append(min(distances) / normalizer)
    return degree_counts, gaps


def measure_pack_verifier(pack_root: Path, verifier: Any, *, replicates: int,
                          progress: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    overall_true = rate_record()
    overall_false = rate_record()
    by_perturbation = {name: rate_record() for name in PERTURBATIONS}
    name_blind_true = rate_record()
    by_tier: dict[str, Any] = {}
    failures: list[dict[str, Any]] = []
    conversion_totals = Counter()
    normalized_lengths: dict[str, list[float]] = defaultdict(list)
    endpoint_gaps: dict[str, list[float]] = defaultdict(list)
    topology_degrees: dict[str, Counter] = defaultdict(Counter)
    unique_drawings = 0
    started = time.perf_counter()

    for tier in TIERS:
        tier_true = rate_record()
        tier_false = rate_record()
        tier_blind = rate_record()
        tier_perturbations = {name: rate_record() for name in PERTURBATIONS}
        manifest = json.loads((pack_root / tier / "manifest.json").read_text(encoding="utf-8"))
        for entry in manifest["files"]:
            drawing_key = f"{tier}/{entry['drawing_id']}@{entry['seed']}"
            truth = json.loads((pack_root / tier / entry["truth"]).read_text(encoding="utf-8"))
            seg_ir, conversion = dxf_to_seg_ir(pack_root / tier / entry["dxf"], drawing_key)
            conversion_totals.update(conversion)
            lengths = segment_lengths(seg_ir)
            normalizer = statistics.median(lengths) if lengths else 1.0
            normalized_lengths[tier].extend(value / normalizer for value in lengths)
            model = verifier.analyze_seg_ir(seg_ir)
            degrees, gaps = topology_degree_and_gaps(model, normalizer)
            topology_degrees[tier].update(degrees)
            endpoint_gaps[tier].extend(gaps)
            true_handles = [str(value) for value in truth["wall_handles_flat"]]

            blind_ir = dict(seg_ir)
            blind_ir["segments"] = [
                {key: value for key, value in segment.items() if key != "layer"}
                for segment in seg_ir["segments"]
            ]
            blind_model = dict(model)
            blind_model["wallish_handles"] = set()
            blind_model["expected_handles"] = set()
            blind_model["expected_pairs"] = []
            blind_model["expected_topology"] = verifier._topology_signature(
                [], set(), model["junction_snap"]
            )

            for replicate in range(replicates):
                ordinal = unique_drawings * replicates + replicate
                true_result = verifier.verify_claim(seg_ir, true_handles, analysis=model)
                observe(overall_true, true_result["accepted"])
                observe(tier_true, true_result["accepted"])
                if not true_result["accepted"] and len(failures) < 50:
                    failures.append(
                        {
                            "kind": "true_reject",
                            "drawing": drawing_key,
                            "replicate": replicate,
                            "reason_codes": true_result["reason_codes"],
                            "missing": true_result["evidence"]["set_completeness"]["missing_handles"],
                            "extra": true_result["evidence"]["set_completeness"]["extra_handles"],
                        }
                    )

                perturbations = verifier._build_perturbations(model, truth, ordinal)
                for name in PERTURBATIONS:
                    result = verifier.verify_claim(seg_ir, perturbations[name], analysis=model)
                    observe(overall_false, result["accepted"])
                    observe(by_perturbation[name], result["accepted"])
                    observe(tier_false, result["accepted"])
                    observe(tier_perturbations[name], result["accepted"])
                    if result["accepted"] and len(failures) < 50:
                        failures.append(
                            {
                                "kind": "false_accept",
                                "drawing": drawing_key,
                                "replicate": replicate,
                                "perturbation": name,
                                "reason_codes": result["reason_codes"],
                            }
                        )

                blind_result = verifier.verify_claim(blind_ir, true_handles, analysis=blind_model)
                observe(name_blind_true, blind_result["accepted"])
                observe(tier_blind, blind_result["accepted"])

            unique_drawings += 1
            if progress and unique_drawings % 5 == 0:
                print(
                    f"verifier unique drawings {unique_drawings}: "
                    f"segments={len(seg_ir['segments'])} elapsed={time.perf_counter() - started:.1f}s",
                    flush=True,
                )
            del model, blind_model, blind_ir, seg_ir
            gc.collect()

        finalize_true(tier_true)
        finalize_false(tier_false)
        finalize_true(tier_blind)
        for record in tier_perturbations.values():
            finalize_false(record)
        by_tier[tier] = {
            "unique_drawings": len(manifest["files"]),
            "true_claims": tier_true,
            "false_claims": {
                **tier_false,
                "by_perturbation": tier_perturbations,
            },
            "name_blind_true_claims": tier_blind,
        }

    finalize_true(overall_true)
    finalize_false(overall_false)
    finalize_true(name_blind_true)
    for record in by_perturbation.values():
        finalize_false(record)
    elapsed = time.perf_counter() - started

    audit = {
        "schema": "e2.wall-claim-verifier.full-diversity-audit.v1",
        "measured_utc": utc_now(),
        "rate_definitions": {
            "far": "false complete-set claims accepted / false complete-set claims",
            "frr": "true complete-set claims rejected / true complete-set claims",
        },
        "source": {
            "verifier_path": str(VERIFIER_PATH),
            "verifier_sha256": sha256(VERIFIER_PATH),
            "generator_path": str(GEN2_PATH),
            "generator_sha256": sha256(GEN2_PATH),
        },
        "pack": {
            "path": str(pack_root),
            "unique_drawings": unique_drawings,
            "entity_ratios": "gen2.DEFAULT_ENTITY_RATIOS",
            "entity_target_count": ENTITY_TARGET_COUNT,
            "calibration_pairs": CALIBRATION_PAIRS,
        },
        "trial_design": {
            "claim_replicates_per_drawing": replicates,
            "true_claims_per_unique_drawing": replicates,
            "claims_per_perturbation_per_unique_drawing": replicates,
            "dependence_note": (
                "Replicate claims share one drawing and one geometric analysis; perturbation ordinal varies. "
                "Counts are claim evaluations, not independent drawing topologies."
            ),
        },
        "seg_ir_policy": {
            "included": ["LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "SPLINE"],
            "arc": f"uniform angular chords, maximum step {ARC_MAX_STEP_DEG} degrees",
            "circle": f"{CIRCLE_CHORDS} uniform angular chords",
            "spline": f"{SPLINE_CHORDS} equal-parameter chords from ezdxf BSpline.approximate",
            "omitted_nonsegment_types": [
                "3DFACE", "ELLIPSE", "HATCH", "INSERT", "MTEXT", "POINT", "TEXT", "WIPEOUT"
            ],
        },
        "conversion_totals": dict(sorted(conversion_totals.items())),
        "true_claims": overall_true,
        "false_claims": {
            **overall_false,
            "by_perturbation": by_perturbation,
        },
        "by_tier": by_tier,
        "name_blind": {
            "transform": "remove layer metadata from every SEG-IR segment",
            "true_claims": name_blind_true,
            "frr_delta_vs_full_metadata": (
                name_blind_true["frr"] - overall_true["frr"]
                if name_blind_true["frr"] is not None and overall_true["frr"] is not None
                else None
            ),
        },
        "runtime_seconds": round(elapsed, 6),
        "sample_anomalies": failures,
    }

    tier_pairs = (("S", "F"), ("S", "M"), ("F", "M"))
    face_stats = {
        "normalization": "each SEG-IR chord length divided by that drawing's median chord length",
        "normalized_primitive_length": {
            "summary_by_tier": {
                tier: finite_summary(normalized_lengths[tier]) for tier in TIERS
            },
            "pairwise_tier_ks": {
                f"{left}_vs_{right}": two_sample_ks(
                    normalized_lengths[left], normalized_lengths[right]
                )
                for left, right in tier_pairs
            },
        },
        "face_bridge_proxy_degree": {
            "definition": "degree of verifier expected-pair axis nodes under its junction snap",
            "counts_by_tier": {
                tier: {str(key): value for key, value in sorted(topology_degrees[tier].items())}
                for tier in TIERS
            },
            "pairwise_tier_tv": {
                f"{left}_vs_{right}": total_variation_counts(
                    topology_degrees[left], topology_degrees[right]
                )
                for left, right in tier_pairs
            },
        },
        "endpoint_gap_normalized": {
            "definition": "nearest endpoint distance between distinct expected-pair axes / drawing median chord length",
            "summary_by_tier": {
                tier: finite_summary(endpoint_gaps[tier]) for tier in TIERS
            },
            "pairwise_tier_ks": {
                f"{left}_vs_{right}": two_sample_ks(endpoint_gaps[left], endpoint_gaps[right])
                for left, right in tier_pairs
            },
        },
        "external_reference_limitation": (
            "The permitted aggregate reference JSON publishes entity mix and parallel-offset histograms, "
            "but no real-corpus normalized-length, face-degree, or endpoint-gap samples. External KS/TV "
            "for those three face diagnostics is therefore not fabricated; cross-tier statistics are reported."
        ),
    }
    return audit, face_stats


def collect_pack_summary(pack_root: Path) -> dict[str, Any]:
    aggregate_entities = Counter()
    aggregate_classes = Counter()
    aggregate_negative_classes = Counter()
    aggregate_wall = 0
    aggregate_labeled = 0
    per_tier = {}
    for tier in TIERS:
        manifest = json.loads((pack_root / tier / "manifest.json").read_text(encoding="utf-8"))
        tier_entities = Counter()
        tier_classes = Counter()
        tier_negative = Counter()
        tier_wall = 0
        tier_labeled = 0
        for entry in manifest["files"]:
            truth = json.loads((pack_root / tier / entry["truth"]).read_text(encoding="utf-8"))
            tier_entities.update(truth["entity_mix"])
            tier_classes.update(truth["class_counts"])
            tier_negative.update(truth["negative_class_counts"])
            tier_wall += len(truth["wall_handles_flat"])
            tier_labeled += len(truth["class_of_handle"])
        aggregate_entities.update(tier_entities)
        aggregate_classes.update(tier_classes)
        aggregate_negative_classes.update(tier_negative)
        aggregate_wall += tier_wall
        aggregate_labeled += tier_labeled
        total_entities = sum(tier_entities.values())
        per_tier[tier] = {
            "n_drawings": manifest["n"],
            "entity_counts": dict(sorted(tier_entities.items())),
            "entity_ratios": {
                key: value / total_entities for key, value in sorted(tier_entities.items())
            },
            "wall_handles": tier_wall,
            "labeled_handles": tier_labeled,
            "wall_frac": tier_wall / tier_labeled if tier_labeled else None,
            "negative_class_counts": dict(sorted(tier_negative.items())),
        }
    total_entities = sum(aggregate_entities.values())
    return {
        "n_drawings": sum(item["n_drawings"] for item in per_tier.values()),
        "entity_counts": dict(sorted(aggregate_entities.items())),
        "entity_ratios": {
            key: value / total_entities for key, value in sorted(aggregate_entities.items())
        },
        "entity_types_observed": sorted(aggregate_entities),
        "n_entity_types_observed": len(aggregate_entities),
        "class_counts": dict(sorted(aggregate_classes.items())),
        "negative_class_counts": dict(sorted(aggregate_negative_classes.items())),
        "wall_handles": aggregate_wall,
        "labeled_handles": aggregate_labeled,
        "wall_frac": aggregate_wall / aggregate_labeled if aggregate_labeled else None,
        "per_tier": per_tier,
    }


def build_seed_manifest(pack_root: Path, gen2: Any) -> dict[str, Any]:
    tiers = {}
    for tier in TIERS:
        path = pack_root / tier / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        tiers[tier] = {
            "manifest": f"packs/{tier}/manifest.json",
            "manifest_sha256": sha256(path),
            "n": manifest["n"],
            "seeds": manifest["seeds"],
        }
    return {
        "schema": "e2.fidelity-full.seed-manifest.v1",
        "created_utc": utc_now(),
        "generator": {
            "path": str(GEN2_PATH),
            "sha256": sha256(GEN2_PATH),
            "schema": gen2.GENERATOR_SCHEMA,
        },
        "recipe": {
            "entrypoint": "gen2.build_pack_root",
            "base_seed": BASE_SEED,
            "tier_seed_offsets": dict(gen2.TIER_SEED_OFFSETS),
            "n_per_tier": N_PER_TIER,
            "entity_target_count": ENTITY_TARGET_COUNT,
            "calibration_pairs": CALIBRATION_PAIRS,
            "entity_ratios": dict(sorted(gen2.DEFAULT_ENTITY_RATIOS.items())),
        },
        "pack_manifest": "packs/manifest.json",
        "pack_manifest_sha256": sha256(pack_root / "manifest.json"),
        "tiers": tiers,
    }


def validate_pack(pack_root: Path, required_negative_classes: set[str]) -> dict[str, Any]:
    errors: list[str] = []
    dxf_count = 0
    truth_count = 0
    for tier in TIERS:
        manifest_path = pack_root / tier / "manifest.json"
        if not manifest_path.is_file():
            errors.append(f"missing:{manifest_path}")
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("n") != N_PER_TIER:
            errors.append(f"{tier}:n={manifest.get('n')}")
        for entry in manifest.get("files", []):
            dxf_path = pack_root / tier / entry["dxf"]
            truth_path = pack_root / tier / entry["truth"]
            dxf_count += int(dxf_path.is_file())
            truth_count += int(truth_path.is_file())
            if not dxf_path.is_file() or not truth_path.is_file():
                errors.append(f"{tier}:{entry.get('drawing_id')}:missing_file")
                continue
            if sha256(dxf_path) != entry["dxf_sha256"]:
                errors.append(f"{tier}:{entry['drawing_id']}:dxf_hash")
            if sha256(truth_path) != entry["truth_sha256"]:
                errors.append(f"{tier}:{entry['drawing_id']}:truth_hash")
    summary = collect_pack_summary(pack_root)
    missing_classes = sorted(
        required_negative_classes - set(summary["negative_class_counts"])
    )
    if missing_classes:
        errors.append(f"missing_negative_classes:{missing_classes}")
    if summary["n_drawings"] != N_PER_TIER * len(TIERS):
        errors.append(f"drawings:{summary['n_drawings']}")
    return {
        "dxf_files": dxf_count,
        "truth_ledgers": truth_count,
        "tier_manifests": sum((pack_root / tier / "manifest.json").is_file() for tier in TIERS),
        "root_manifest": int((pack_root / "manifest.json").is_file()),
        "required_negative_classes": sorted(required_negative_classes),
        "missing_negative_classes": missing_classes,
        "errors": errors,
    }


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def render_report(seed_manifest: Mapping[str, Any], fidelity: Mapping[str, Any],
                  audit: Mapping[str, Any], sample: Mapping[str, Any],
                  integrity: Mapping[str, Any], runtimes: Mapping[str, float],
                  source_before: Mapping[str, str], source_after: Mapping[str, str]) -> str:
    pack = fidelity["pack_achieved"]
    fidelity_rows = []
    for tier in ("aggregate", *TIERS):
        record = fidelity if tier == "aggregate" else fidelity["per_tier"][tier]
        metrics = record["metrics"] if tier == "aggregate" else record
        samples = fidelity["sample_counts"] if tier == "aggregate" else record
        fidelity_rows.append(
            [
                tier,
                f"{metrics['thickness_ks']:.12f}",
                f"{metrics['entity_mix_tv']:.12f}",
                samples["n_drawings"],
                samples["n_parallel_pair_offsets"],
                samples["read_errors"],
            ]
        )
    verifier_rows = []
    for name in PERTURBATIONS:
        record = audit["false_claims"]["by_perturbation"][name]
        verifier_rows.append([name, record["n"], record["accepted"], record["rejected"], f"{record['far']:.9f}"])
    tier_rows = []
    for tier in TIERS:
        record = audit["by_tier"][tier]
        tier_rows.append(
            [
                tier,
                record["true_claims"]["n"],
                f"{record['true_claims']['frr']:.9f}",
                record["false_claims"]["n"],
                f"{record['false_claims']['far']:.9f}",
                f"{record['name_blind_true_claims']['frr']:.9f}",
            ]
        )
    lure_rows = [[key, value] for key, value in pack["negative_class_counts"].items()]
    total_entity_count = sum(pack["entity_counts"].values())
    ratio_rows = [[key, value, f"{value / total_entity_count:.9f}"] for key, value in pack["entity_counts"].items()]

    source_unchanged = source_before == source_after
    return f"""# fidelity_full 셀 실행 보고서

## 범위와 실행 설계

gen2 v2의 기본 전체-다양성 비율로 S/F/M 각 50장, 총 150장을 새로 생성했다. 각 tier는 50개 고정 seed를 가지며, `seed_manifest.json`과 tier manifest의 DXF/truth SHA-256으로 재생 recipe를 고정했다. 원본 CAD와 외부 test split은 열지 않았고, source repo의 세 Python 파일은 read-only import했다.

- base seed: `{seed_manifest['recipe']['base_seed']}`
- entity target: {seed_manifest['recipe']['entity_target_count']} / drawing
- reference parallel pairs: {seed_manifest['recipe']['calibration_pairs']} / drawing
- 생성기 SHA-256: `{seed_manifest['generator']['sha256']}`
- source hash unchanged: `{source_unchanged}`
- pack files: DXF {integrity['dxf_files']}, truth ledger {integrity['truth_ledgers']}, tier manifest {integrity['tier_manifests']}, root manifest {integrity['root_manifest']}
- artifact integrity errors: {len(integrity['errors'])}

충실도 수치에는 prereg band 비교나 PASS/FAIL 판정을 붙이지 않았고, 검증기 수치에도 자격 판정을 붙이지 않았다.

## 소표본 처리율 선실측과 전량 예상

전량 전에 동일 config의 S/F/M 각 1장(3장)을 생성·통계·검증했다. 임시 샘플 팩은 측정 뒤 제거했다.

{markdown_table(
    ['단계', '소표본 초', '초/도면', '150장 예상 초'],
    [
        ['팩 생성', f"{sample['timings_seconds']['generation']:.6f}", f"{sample['rates_seconds_per_drawing']['generation']:.6f}", f"{sample['projected_seconds_for_150']['generation']:.3f}"],
        ['fidelity_stats 방식', f"{sample['timings_seconds']['fidelity']:.6f}", f"{sample['rates_seconds_per_drawing']['fidelity']:.6f}", f"{sample['projected_seconds_for_150']['fidelity']:.3f}"],
        ['SEG-IR+검증기', f"{sample['timings_seconds']['verifier']:.6f}", f"{sample['rates_seconds_per_drawing']['verifier']:.6f}", f"{sample['projected_seconds_for_150']['verifier']:.3f}"],
    ],
)}

전량 실제 시간은 생성 {runtimes['generation']:.3f}s, fidelity {runtimes['fidelity']:.3f}s, SEG-IR+검증 {runtimes['verifier']:.3f}s, pack hash 검증 {runtimes['integrity']:.3f}s였다.

## 팩 달성 분포와 진리 원장

- drawings: {pack['n_drawings']}
- observed entity types: {pack['n_entity_types_observed']} — `{', '.join(pack['entity_types_observed'])}`
- wall handles / explicitly labeled handles: {pack['wall_handles']} / {pack['labeled_handles']}
- aggregate wall_frac: {pack['wall_frac']:.9f}

### 엔티티 수와 달성 비율

{markdown_table(['entity', 'count', 'ratio'], ratio_rows)}

### 명시적 음성 클래스 수 (요구 8개 미끼 포함)

{markdown_table(['class', 'count'], lure_rows)}

## 충실도 수치

`fidelity_stats.py`의 동일 계산으로 reference aggregate JSON의 parallel-offset histogram KS와 entity-mix TV를 산출했다.

{markdown_table(['scope', 'thickness KS', 'entity TV', 'drawings', 'pair offsets', 'read errors'], fidelity_rows)}

소비자 표기는 같은 관측 수치를 서로 다른 prereg 정의에 연결할 뿐 판정을 내리지 않는다. Calibration 소비자에는 thickness-offset KS와 entity-type TV를 기록했다. Face 소비자에는 같은 reference-based entity TV와 함께 normalized primitive length, expected-pair axis degree, endpoint-gap의 tier간 KS/TV를 `fidelity_numbers.json`에 기록했다. 허용된 real aggregate에는 후자 세 분포의 원표본이 없으므로 real-vs-synthetic 값을 만들지 않았다.

## SEG-IR 곡선 근사 정책

- ARC: 균일 각도 chord, 최대 {ARC_MAX_STEP_DEG}° step.
- CIRCLE: {CIRCLE_CHORDS}개 균일 chord.
- SPLINE: ezdxf `BSpline.approximate`의 equal-parameter {SPLINE_CHORDS}개 chord.
- 포함: LINE/LWPOLYLINE/POLYLINE/ARC/CIRCLE/SPLINE.
- 비선분 타입 3DFACE/ELLIPSE/HATCH/INSERT/MTEXT/POINT/TEXT/WIPEOUT은 pack에는 남아 있고 verifier SEG-IR에서는 생략했다.

## 검증기 전체-다양성 FAR/FRR 수치

150개 고유 도면마다 4개 perturbation ordinal을 사용했다. 참 complete-set claim은 도면당 동일하므로 총 600회지만 독립 topology 600개로 해석하지 않는다. 각 교란은 ordinal에 따라 제거/교체 handle이 달라지며 종별 600회다.

- full-metadata true claims: n={audit['true_claims']['n']}, accept={audit['true_claims']['accepted']}, reject={audit['true_claims']['rejected']}, FRR={audit['true_claims']['frr']:.9f}
- full-metadata false claims: n={audit['false_claims']['n']}, accept={audit['false_claims']['accepted']}, reject={audit['false_claims']['rejected']}, FAR={audit['false_claims']['far']:.9f}
- name-blind true claims: n={audit['name_blind']['true_claims']['n']}, accept={audit['name_blind']['true_claims']['accepted']}, reject={audit['name_blind']['true_claims']['rejected']}, FRR={audit['name_blind']['true_claims']['frr']:.9f}
- name-blind FRR delta: {audit['name_blind']['frr_delta_vs_full_metadata']:.9f}

### 교란 종별

{markdown_table(['perturbation', 'n', 'accept', 'reject', 'FAR'], verifier_rows)}

### 티어별

{markdown_table(['tier', 'true n', 'FRR', 'false n', 'FAR', 'name-blind FRR'], tier_rows)}

## 미해결과 해석 제한

- 600회 true/종별 false 계측은 150개 고유 도면에서 네 ordinal을 반복한 correlated claim 수다. gen2의 tier별 벽 topology도 seed마다 새 grammar가 아니라 고정 구조에 가깝다.
- name-blind arm은 layer metadata를 완전히 제거한다. verifier의 현재 `layer_metadata`와 candidate reconstruction 계약 때문에 변화 원인이 분리 가능하지만, 이 수치를 다른 name-blind 정의와 혼합하지 않는다.
- face 소비자의 real-corpus normalized-length/face-degree/endpoint-gap 원분포는 허용된 aggregate JSON에 없다. tier간 수치는 측정했지만 real-vs-synthetic face KS/TV는 만들지 않았다.
- HATCH 포셰, ELLIPSE, INSERT 내부 geometry 등은 full pack에는 존재하지만 이번 verifier SEG-IR adapter의 claim universe에는 들어가지 않는다.
- sample anomaly records: {len(audit['sample_anomalies'])}. 상세는 `verifier_far_frr_full.json`에 있다.
- 수치만 제공하며 fidelity band 또는 verifier 자격 결론은 이 셀에서 출력하지 않는다.

CELL_COMPLETE: fidelity_full
"""


def run_sample() -> int:
    if SAMPLE_ROOT.exists():
        raise FileExistsError(f"sample path already exists: {SAMPLE_ROOT}")
    gen2, fidelity, verifier = load_sources()
    source_before = source_hashes()
    started = utc_now()
    print("sample: gen2 selftest", flush=True)
    gen2_selftest_rc = gen2.selftest()
    print("sample: verifier selftest", flush=True)
    verifier_selftest_ok, verifier_selftest_lines = verifier.run_selftest(emit=True)
    if gen2_selftest_rc != 0 or not verifier_selftest_ok:
        raise RuntimeError("source selftest failed")
    try:
        t0 = time.perf_counter()
        gen2.build_pack_root(
            SAMPLE_ROOT,
            BASE_SEED,
            1,
            entity_ratios=gen2.DEFAULT_ENTITY_RATIOS,
            entity_count=ENTITY_TARGET_COUNT,
            calibration_pairs=CALIBRATION_PAIRS,
        )
        generation_seconds = time.perf_counter() - t0
        print(f"sample: generation {generation_seconds:.6f}s", flush=True)

        t0 = time.perf_counter()
        sample_fidelity = fidelity.numeric_report(
            SAMPLE_ROOT, REFERENCE_FIDELITY, REFERENCE_ENTITY
        )
        fidelity_seconds = time.perf_counter() - t0
        print(f"sample: fidelity {fidelity_seconds:.6f}s", flush=True)

        t0 = time.perf_counter()
        sample_audit, _ = measure_pack_verifier(
            SAMPLE_ROOT, verifier, replicates=CLAIM_REPLICATES, progress=True
        )
        verifier_seconds = time.perf_counter() - t0
        print(f"sample: verifier {verifier_seconds:.6f}s", flush=True)
    finally:
        if SAMPLE_ROOT.exists():
            resolved = SAMPLE_ROOT.resolve()
            resolved.relative_to(CELL_ROOT.resolve())
            shutil.rmtree(resolved)

    n = len(TIERS)
    rates = {
        "generation": generation_seconds / n,
        "fidelity": fidelity_seconds / n,
        "verifier": verifier_seconds / n,
    }
    projected = {key: value * (N_PER_TIER * len(TIERS)) for key, value in rates.items()}
    payload = {
        "schema": "e2.fidelity-full.throughput-sample.v1",
        "started_utc": started,
        "completed_utc": utc_now(),
        "sample_drawings": n,
        "config": {
            "base_seed": BASE_SEED,
            "n_per_tier": 1,
            "entity_target_count": ENTITY_TARGET_COUNT,
            "calibration_pairs": CALIBRATION_PAIRS,
            "claim_replicates": CLAIM_REPLICATES,
        },
        "selftests": {
            "gen2_return_code": gen2_selftest_rc,
            "verifier_ok": verifier_selftest_ok,
            "verifier_last_line": verifier_selftest_lines[-1],
        },
        "timings_seconds": {
            "generation": round(generation_seconds, 6),
            "fidelity": round(fidelity_seconds, 6),
            "verifier": round(verifier_seconds, 6),
        },
        "rates_seconds_per_drawing": {key: round(value, 6) for key, value in rates.items()},
        "projected_seconds_for_150": {key: round(value, 3) for key, value in projected.items()},
        "projected_total_seconds_for_150": round(sum(projected.values()), 3),
        "sample_fidelity_metrics": sample_fidelity["metrics"],
        "sample_verifier": {
            "true_claims": sample_audit["true_claims"],
            "false_claims": {
                key: sample_audit["false_claims"][key]
                for key in ("n", "accepted", "rejected", "far")
            },
            "name_blind": sample_audit["name_blind"],
            "conversion_totals": sample_audit["conversion_totals"],
        },
        "source_hashes_before": source_before,
        "source_hashes_after": source_hashes(),
    }
    write_json(SAMPLE_NUMBERS, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


def run_full() -> int:
    if not SAMPLE_NUMBERS.is_file():
        raise FileNotFoundError("run --sample before --full")
    if PACK_ROOT.exists():
        raise FileExistsError(f"refusing to overwrite existing pack: {PACK_ROOT}")
    for output in (SEED_MANIFEST, FIDELITY_NUMBERS, VERIFIER_NUMBERS, REPORT_PATH):
        if output.exists():
            raise FileExistsError(f"refusing to overwrite existing output: {output}")

    sample = json.loads(SAMPLE_NUMBERS.read_text(encoding="utf-8"))
    gen2, fidelity, verifier = load_sources()
    source_before = source_hashes()

    print("full: generating 150 drawings", flush=True)
    t0 = time.perf_counter()
    gen2.build_pack_root(
        PACK_ROOT,
        BASE_SEED,
        N_PER_TIER,
        entity_ratios=gen2.DEFAULT_ENTITY_RATIOS,
        entity_count=ENTITY_TARGET_COUNT,
        calibration_pairs=CALIBRATION_PAIRS,
    )
    generation_seconds = time.perf_counter() - t0
    print(f"full: generation complete {generation_seconds:.3f}s", flush=True)

    seed_manifest = build_seed_manifest(PACK_ROOT, gen2)
    write_json(SEED_MANIFEST, seed_manifest)

    print("full: computing fidelity statistics", flush=True)
    t0 = time.perf_counter()
    fidelity_report = fidelity.numeric_report(
        PACK_ROOT, REFERENCE_FIDELITY, REFERENCE_ENTITY
    )
    fidelity_seconds = time.perf_counter() - t0
    print(f"full: fidelity complete {fidelity_seconds:.3f}s", flush=True)

    print("full: converting SEG-IR and measuring verifier", flush=True)
    t0 = time.perf_counter()
    audit, face_stats = measure_pack_verifier(
        PACK_ROOT, verifier, replicates=CLAIM_REPLICATES, progress=True
    )
    verifier_seconds = time.perf_counter() - t0
    print(f"full: verifier complete {verifier_seconds:.3f}s", flush=True)

    pack_summary = collect_pack_summary(PACK_ROOT)
    fidelity_report.update(
        {
            "measured_utc": utc_now(),
            "pack_path": str(PACK_ROOT),
            "pack_achieved": pack_summary,
            "consumer_views": {
                "calibration_P1": {
                    "continuous_ks": {
                        "parallel_pair_offset_mm": fidelity_report["metrics"]["thickness_ks"]
                    },
                    "categorical_tv": {
                        "entity_type": fidelity_report["metrics"]["entity_mix_tv"]
                    },
                },
                "feyerabend_P1": {
                    "reference_based": {
                        "parallel_pair_offset_ks": fidelity_report["metrics"]["thickness_ks"],
                        "entity_type_tv": fidelity_report["metrics"]["entity_mix_tv"],
                    },
                    "face_consumer_diagnostics": face_stats,
                },
            },
            "runtime_seconds": round(fidelity_seconds, 6),
        }
    )
    write_json(FIDELITY_NUMBERS, fidelity_report)
    write_json(VERIFIER_NUMBERS, audit)

    print("full: validating manifests and hashes", flush=True)
    t0 = time.perf_counter()
    integrity = validate_pack(PACK_ROOT, set(gen2.REQUIRED_HARD_NEGATIVE_CLASSES))
    integrity_seconds = time.perf_counter() - t0
    if integrity["errors"]:
        raise RuntimeError(f"pack integrity errors: {integrity['errors'][:10]}")
    if audit["true_claims"]["n"] < 500:
        raise RuntimeError("true-claim sample count below 500")
    for name in PERTURBATIONS:
        if audit["false_claims"]["by_perturbation"][name]["n"] < 500:
            raise RuntimeError(f"perturbation sample count below 500: {name}")
    if pack_summary["n_drawings"] != 150:
        raise RuntimeError("pack does not contain 150 drawings")

    source_after = source_hashes()
    if source_before != source_after:
        raise RuntimeError("read-only source hash changed during execution")
    runtimes = {
        "generation": generation_seconds,
        "fidelity": fidelity_seconds,
        "verifier": verifier_seconds,
        "integrity": integrity_seconds,
    }
    report = render_report(
        seed_manifest,
        fidelity_report,
        audit,
        sample,
        integrity,
        runtimes,
        source_before,
        source_after,
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    if REPORT_PATH.read_text(encoding="utf-8").splitlines()[-1] != "CELL_COMPLETE: fidelity_full":
        raise RuntimeError("REPORT completion marker missing")
    print(f"full: wrote {SEED_MANIFEST}", flush=True)
    print(f"full: wrote {FIDELITY_NUMBERS}", flush=True)
    print(f"full: wrote {VERIFIER_NUMBERS}", flush=True)
    print(f"full: wrote {REPORT_PATH}", flush=True)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sample", action="store_true")
    mode.add_argument("--full", action="store_true")
    args = parser.parse_args(argv)
    return run_sample() if args.sample else run_full()


if __name__ == "__main__":
    raise SystemExit(main())
