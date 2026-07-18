#!/usr/bin/env python3
"""C1v4 estimator repair: ratio-consistent reference consensus.

The sealed C1 implementation is imported read-only.  This module preserves its
ratio estimator and evaluation schema while replacing the reference-consensus
path so a ratio-bearing DIM/TEXT anchor must be an inlier of the selected ratio
mode before it may contribute reference independence or spatial-bin support.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import io
import json
import math
import random
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


sys.dont_write_bytecode = True

CELL_DIR = Path(__file__).resolve().parent
ORIGINAL_C1_PATH = Path(r"D:\runs\e2_program\cells\feyerabend_c1\feyerabend_c1.py")
V1_COUNTEREXAMPLE_SCENE = Path(
    r"D:\runs\e2_program\cells\feyerabend_c0\scenes\scene_001_k1000.json"
)
L1B_SCENE_DIR = Path(r"D:\runs\e2_program\cells\loop_l1b\scenes_v3")
V1_SCENE_DIR = Path(r"D:\runs\e2_program\cells\feyerabend_c0\scenes")
PROPERTY_SEED = 20260719
PROPERTY_CASES = 300
STATUS_RANK = {"NONE": 0, "LOW": 1, "HIGH": 2}


def _load_module(name: str, path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ORIGINAL = _load_module("loop_l1c_original_c1_readonly", ORIGINAL_C1_PATH)

# Re-export the sealed helpers and constants used by the L1b tests/evaluator.
for _name in (
    "SCALES",
    "CONFIDENCE_LEVELS",
    "CORRUPTIONS",
    "RANSAC_LOG_TOLERANCE",
    "HUBER_DELTA",
    "HIGH_CONFIDENCE_THRESHOLD",
    "CONSENSUS_THRESHOLD",
    "MIN_INDEPENDENT",
    "ACCURACY_RELATIVE_ERROR",
    "EPSILON",
    "BASE_WEIGHTS",
    "UNIT_TO_MM",
    "SCORE_BINS",
    "canonical_bytes",
    "canonical_sha256",
    "sha256_file",
    "finite_float",
    "round_key",
    "scale_token",
    "weighted_median",
    "weighted_log_mad",
    "huber_location",
    "geometric_span",
    "midpoint",
    "canonical_anchor_key",
    "prepare_anchors",
    "spatial_bin_count",
    "maximum_consensus",
    "confidence_from_consensus",
    "assigned_corruption",
    "deterministic_index",
    "apply_corruption",
    "permute_pair_labels",
    "GuardedScene",
    "exact_fixture",
    "relative_error",
    "log_error",
    "numeric_distribution",
    "summarize_rows",
    "score_bin_for",
    "transition_counter",
    "corruption_summary",
    "aggregate_results",
):
    globals()[_name] = getattr(ORIGINAL, _name)


def _status(
    exists: bool,
    consensus: Mapping[str, Any] | None,
    confidence: Mapping[str, Any] | None,
) -> str:
    return ORIGINAL._status(exists, consensus, confidence)


def fit_anchor_model(raw_anchors: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Fit from anchors only, with a ratio-consistency guard on reference support."""
    anchors, audit = prepare_anchors(raw_anchors)

    ratio_records: list[dict[str, Any]] = []
    for anchor in anchors:
        if anchor["anchor_type"] not in ("DIM", "TEXT"):
            continue
        display = anchor["display_value"]
        if display is None or display <= 0.0:
            continue
        ratio_records.append(
            {
                **anchor,
                "log_ratio": math.log(float(display) / float(anchor["raw_span"])),
            }
        )

    ratio_consensus = maximum_consensus(
        ratio_records, "log_ratio", RANSAC_LOG_TOLERANCE
    )
    if ratio_consensus is None:
        scale_estimate = None
        ratio_confidence = None
        unit_status = "NONE"
        ratio_inliers: list[dict[str, Any]] = []
        ratio_outliers: list[dict[str, Any]] = []
    else:
        ratio_inliers = [
            ratio_records[index] for index in ratio_consensus["inlier_indices"]
        ]
        ratio_outliers = [
            ratio_records[index] for index in ratio_consensus["outlier_indices"]
        ]
        ratio_confidence = confidence_from_consensus(ratio_consensus, ratio_inliers)
        unit_status = _status(True, ratio_consensus, ratio_confidence)
        scale_estimate = math.exp(float(ratio_consensus["location"]))

    known_units = sorted(
        {
            str(anchor["display_unit"])
            for anchor in ratio_inliers
            if str(anchor["display_unit"]) in UNIT_TO_MM
        }
    )
    if len(known_units) == 1:
        physical_unit = known_units[0]
        mm_per_raw = float(scale_estimate) * UNIT_TO_MM[physical_unit]
    elif len(known_units) > 1:
        physical_unit = "MIXED"
        mm_per_raw = None
    else:
        physical_unit = "UNKNOWN"
        mm_per_raw = None

    # Repair principle: a DIM/TEXT anchor that carries a usable ratio is dual-
    # evidence.  If that ratio is outside the selected ratio mode, its span is
    # quarantined from reference consensus.  GRID and reference-only anchors do
    # not carry a ratio signal and retain the sealed reference path.
    ratio_inlier_handles = {str(anchor["handle"]) for anchor in ratio_inliers}
    ratio_outlier_handles = {str(anchor["handle"]) for anchor in ratio_outliers}
    reference_records: list[dict[str, Any]] = []
    reference_rejections: list[dict[str, Any]] = []
    for anchor in anchors:
        span = float(anchor["raw_span"])
        text_height = anchor["text_height"]
        if text_height is not None and text_height > 0.0 and span / text_height < 10.0:
            reference_rejections.append(
                {"handle": anchor["handle"], "reason": "annotation_scale_candidate"}
            )
            continue
        carries_ratio = (
            anchor["anchor_type"] in ("DIM", "TEXT")
            and anchor["display_value"] is not None
            and float(anchor["display_value"]) > 0.0
        )
        if carries_ratio and str(anchor["handle"]) not in ratio_inlier_handles:
            reference_rejections.append(
                {
                    "handle": anchor["handle"],
                    "reason": "ratio_space_outlier_guard",
                    "ratio_class": (
                        "outlier"
                        if str(anchor["handle"]) in ratio_outlier_handles
                        else "no_selected_ratio_mode"
                    ),
                }
            )
            continue
        reference_records.append({**anchor, "log_span": math.log(span)})

    reference_consensus = maximum_consensus(
        reference_records, "log_span", RANSAC_LOG_TOLERANCE
    )
    if reference_consensus is None:
        reference_span = None
        reference_confidence = None
        reference_status = "NONE"
        reference_inliers: list[dict[str, Any]] = []
        reference_outliers: list[dict[str, Any]] = []
    else:
        reference_inliers = [
            reference_records[index]
            for index in reference_consensus["inlier_indices"]
        ]
        reference_outliers = [
            reference_records[index]
            for index in reference_consensus["outlier_indices"]
        ]
        reference_confidence = confidence_from_consensus(
            reference_consensus, reference_inliers
        )
        reference_status = _status(True, reference_consensus, reference_confidence)
        reference_span = math.exp(float(reference_consensus["location"]))

    status = reference_status
    source_diversity = sorted({anchor["anchor_type"] for anchor in anchors})
    model = {
        "status": status,
        "unit_status": unit_status,
        "reference_status": reference_status,
        "display_per_raw": scale_estimate,
        "physical_unit": physical_unit,
        "mm_per_raw": mm_per_raw,
        "consensus_weight": None
        if ratio_consensus is None
        else float(ratio_consensus["consensus_weight"]),
        "log_mad": None
        if ratio_consensus is None
        else float(ratio_consensus["log_mad"]),
        "n_independent": 0
        if ratio_confidence is None
        else int(ratio_confidence["n_independent"]),
        "n_spatial_bins": 0
        if ratio_confidence is None
        else int(ratio_confidence["n_spatial_bins"]),
        "confidence_score": 0.0
        if ratio_confidence is None
        else float(ratio_confidence["score"]),
        "source_diversity": source_diversity,
        "reference_span": reference_span,
        "reference_consensus_weight": None
        if reference_consensus is None
        else float(reference_consensus["consensus_weight"]),
        "reference_log_mad": None
        if reference_consensus is None
        else float(reference_consensus["log_mad"]),
        "reference_n_independent": 0
        if reference_confidence is None
        else int(reference_confidence["n_independent"]),
        "reference_n_spatial_bins": 0
        if reference_confidence is None
        else int(reference_confidence["n_spatial_bins"]),
        "reference_confidence_score": 0.0
        if reference_confidence is None
        else float(reference_confidence["score"]),
        "provenance": {
            **audit,
            "ratio_inlier_handles": [anchor["handle"] for anchor in ratio_inliers],
            "ratio_outlier_handles": [anchor["handle"] for anchor in ratio_outliers],
            "reference_inlier_handles": [
                anchor["handle"] for anchor in reference_inliers
            ],
            "reference_outlier_handles": [
                anchor["handle"] for anchor in reference_outliers
            ],
            "reference_rejections": reference_rejections,
            "reference_guard": {
                "revision": "c1v4_ratio_consistency",
                "ratio_bearing_reference_anchor_rule": "selected_ratio_mode_inlier_required",
                "guarded_rejection_count": sum(
                    row["reason"] == "ratio_space_outlier_guard"
                    for row in reference_rejections
                ),
            },
        },
    }
    return model


def anchor_artifact_from_scene(scene: Mapping[str, Any]) -> dict[str, Any]:
    model = fit_anchor_model(copy.deepcopy(scene["anchors"]))
    return {
        "artifact_schema": "ariadne.e2.feyerabend_c1.anchor_artifact.v2",
        "model": model,
    }


def evaluate_scene(scene: Mapping[str, Any]) -> dict[str, Any]:
    artifact_before = anchor_artifact_from_scene(scene)
    model = artifact_before["model"]
    truth_scale = float(scene["truth_unit_scale"])
    estimate = model["display_per_raw"]

    permuted = permute_pair_labels(scene)
    artifact_after = anchor_artifact_from_scene(permuted)
    before_digest = canonical_sha256(artifact_before)
    after_digest = canonical_sha256(artifact_after)
    truth_before_digest = canonical_sha256(scene.get("truth_pairs", []))
    truth_after_digest = canonical_sha256(permuted.get("truth_pairs", []))

    corruption_rows: dict[str, Any] = {}
    for kind in CORRUPTIONS:
        corrupted_anchors = apply_corruption(
            scene["anchors"], kind, str(scene["base_scene_id"])
        )
        corrupted_model = fit_anchor_model(corrupted_anchors)
        corrupted_estimate = corrupted_model["display_per_raw"]
        same_estimate = (
            estimate is None
            and corrupted_estimate is None
            or estimate is not None
            and corrupted_estimate is not None
            and math.isclose(
                float(estimate),
                float(corrupted_estimate),
                rel_tol=1e-12,
                abs_tol=1e-15,
            )
        )
        corruption_rows[kind] = {
            "status_before": model["status"],
            "status_after": corrupted_model["status"],
            "unit_status_before": model["unit_status"],
            "unit_status_after": corrupted_model["unit_status"],
            "reference_status_before": model["reference_status"],
            "reference_status_after": corrupted_model["reference_status"],
            "physical_unit_before": model["physical_unit"],
            "physical_unit_after": corrupted_model["physical_unit"],
            "scale_estimate_before": estimate,
            "scale_estimate_after": corrupted_estimate,
            "scale_estimate_unchanged": same_estimate,
            "relative_error_after": relative_error(corrupted_estimate, truth_scale),
            "e_s_after": log_error(corrupted_estimate, truth_scale),
            "confidence_score_before": model["confidence_score"],
            "confidence_score_after": corrupted_model["confidence_score"],
            "reference_confidence_score_before": model["reference_confidence_score"],
            "reference_confidence_score_after": corrupted_model["reference_confidence_score"],
            "reference_n_independent_before": model["reference_n_independent"],
            "reference_n_independent_after": corrupted_model["reference_n_independent"],
            "reference_n_spatial_bins_before": model["reference_n_spatial_bins"],
            "reference_n_spatial_bins_after": corrupted_model["reference_n_spatial_bins"],
            "reference_guarded_rejection_count": corrupted_model["provenance"][
                "reference_guard"
            ]["guarded_rejection_count"],
            "artifact_digest": canonical_sha256(
                {
                    "artifact_schema": artifact_before["artifact_schema"],
                    "model": corrupted_model,
                }
            ),
            "input_anchor_count_after": len(corrupted_anchors),
        }

    score = float(model["confidence_score"])
    return {
        "input_file": str(scene.get("_input_file", "")),
        "scene_id": scene["scene_id"],
        "base_scene_id": scene["base_scene_id"],
        "seed": int(scene["seed"]),
        "scale_kappa": float(scene["scale_kappa"]),
        "truth_unit_scale": truth_scale,
        "input_anchor_count": len(scene["anchors"]),
        "input_anchor_types": sorted(
            {str(anchor.get("anchor_type")) for anchor in scene["anchors"]}
        ),
        "scale_estimate": estimate,
        "e_s": log_error(estimate, truth_scale),
        "relative_error": relative_error(estimate, truth_scale),
        "status": model["status"],
        "unit_status": model["unit_status"],
        "reference_status": model["reference_status"],
        "confidence_score": score,
        "confidence_score_bin": score_bin_for(score),
        "physical_unit": model["physical_unit"],
        "anchor_model": model,
        "assigned_corruption": assigned_corruption(str(scene["base_scene_id"])),
        "corruption_diagnostics": corruption_rows,
        "pair_label_permutation": {
            "truth_label_digest_before": truth_before_digest,
            "truth_label_digest_after": truth_after_digest,
            "truth_label_input_changed": truth_before_digest != truth_after_digest,
            "anchor_artifact_digest_before": before_digest,
            "anchor_artifact_digest_after": after_digest,
            "anchor_artifact_digest_equal": before_digest == after_digest,
        },
    }


def run_legacy_selftests(stream: io.TextIOBase) -> dict[str, Any]:
    """The six sealed C1 checks, rerouted through the repaired estimator."""
    tests: list[dict[str, Any]] = []

    def check(name: str, condition: bool, detail: str) -> None:
        passed = bool(condition)
        print(f"SELFTEST {name}: {'PASS' if passed else 'FAIL'} | {detail}", file=stream)
        tests.append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            raise AssertionError(f"selftest failed: {name}: {detail}")

    fixture = exact_fixture()
    exact_model = fit_anchor_model(fixture)
    estimate = exact_model["display_per_raw"]
    check(
        "exact_anchor_exact_scale",
        estimate is not None
        and math.isclose(float(estimate), 2.5, rel_tol=1e-12, abs_tol=1e-12),
        f"estimate={estimate!r} expected=2.5 unit_status={exact_model['unit_status']}",
    )
    check(
        "exact_anchor_high_confidence",
        exact_model["unit_status"] == "HIGH",
        f"unit_status={exact_model['unit_status']} confidence={exact_model['confidence_score']:.12g}",
    )
    empty_model = fit_anchor_model([])
    check(
        "no_anchor_honest_no_estimate",
        empty_model["display_per_raw"] is None
        and empty_model["unit_status"] == "NONE"
        and empty_model["status"] == "NONE",
        f"estimate={empty_model['display_per_raw']!r} unit_status={empty_model['unit_status']} status={empty_model['status']}",
    )
    reproducible = True
    mutation_digests: dict[str, str] = {}
    for kind in CORRUPTIONS:
        first = apply_corruption(fixture, kind, "fixture_base")
        second = apply_corruption(fixture, kind, "fixture_base")
        first_digest = canonical_sha256(first)
        reproducible = reproducible and first_digest == canonical_sha256(second)
        mutation_digests[kind] = first_digest
    check(
        "corruption_reproducibility",
        reproducible,
        " ".join(f"{key}={value[:12]}" for key, value in mutation_digests.items()),
    )
    outlier_model = fit_anchor_model(
        apply_corruption(fixture, "single_outlier", "fixture_base")
    )
    check(
        "single_outlier_mode_or_downgrade",
        (
            outlier_model["display_per_raw"] is not None
            and math.isclose(
                float(outlier_model["display_per_raw"]), 2.5, rel_tol=1e-12, abs_tol=1e-12
            )
        )
        or outlier_model["unit_status"] == "LOW",
        f"estimate={outlier_model['display_per_raw']!r} unit_status={outlier_model['unit_status']}",
    )
    guarded = GuardedScene(fixture)
    guarded_artifact = anchor_artifact_from_scene(guarded)
    check(
        "truth_key_access_guard",
        guarded.accessed == ["anchors"]
        and guarded_artifact["model"]["display_per_raw"] is not None,
        f"accessed_keys={guarded.accessed!r}",
    )
    passed = sum(test["passed"] for test in tests)
    print(f"SELFTEST SUMMARY: {passed}/{len(tests)} passed", file=stream)
    return {"passed": passed, "total": len(tests), "tests": tests}


def _model_snapshot(model: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "confidence_score": float(model["confidence_score"]),
        "status": str(model["status"]),
        "unit_status": str(model["unit_status"]),
        "reference_status": str(model["reference_status"]),
        "reference_confidence_score": float(model["reference_confidence_score"]),
        "reference_n_independent": int(model["reference_n_independent"]),
        "reference_n_spatial_bins": int(model["reference_n_spatial_bins"]),
        "guarded_rejection_count": int(
            model["provenance"].get("reference_guard", {}).get(
                "guarded_rejection_count", 0
            )
        ),
    }


def counterexample_regression() -> dict[str, Any]:
    scene = json.loads(V1_COUNTEREXAMPLE_SCENE.read_text(encoding="utf-8"))
    corrupted = apply_corruption(
        scene["anchors"], "single_outlier", str(scene["base_scene_id"])
    )
    old_before = ORIGINAL.fit_anchor_model(scene["anchors"])
    old_after = ORIGINAL.fit_anchor_model(corrupted)
    new_before = fit_anchor_model(scene["anchors"])
    new_after = fit_anchor_model(corrupted)
    old_status_rise = int(
        STATUS_RANK[str(old_after["status"])] > STATUS_RANK[str(old_before["status"])]
    )
    new_upward = {
        "confidence_score": int(
            float(new_after["confidence_score"])
            > float(new_before["confidence_score"]) + 1e-15
        ),
        "status": int(
            STATUS_RANK[str(new_after["status"])]
            > STATUS_RANK[str(new_before["status"])]
        ),
        "unit_status": int(
            STATUS_RANK[str(new_after["unit_status"])]
            > STATUS_RANK[str(new_before["unit_status"])]
        ),
        "reference_status": int(
            STATUS_RANK[str(new_after["reference_status"])]
            > STATUS_RANK[str(new_before["reference_status"])]
        ),
    }
    passed = (
        old_status_rise == 1
        and old_before["reference_status"] == "LOW"
        and old_after["reference_status"] == "HIGH"
        and sum(new_upward.values()) == 0
        and new_after["reference_status"] == "LOW"
        and int(new_after["reference_n_independent"])
        == int(new_before["reference_n_independent"])
        and int(new_after["reference_n_spatial_bins"])
        == int(new_before["reference_n_spatial_bins"])
    )
    return {
        "passed": passed,
        "scene": str(V1_COUNTEREXAMPLE_SCENE),
        "base_scene_id": scene["base_scene_id"],
        "old_before": _model_snapshot(old_before),
        "old_after": _model_snapshot(old_after),
        "new_before": _model_snapshot(new_before),
        "new_after": _model_snapshot(new_after),
        "old_status_rise_count": old_status_rise,
        "new_upward_counts": new_upward,
    }


def _ratio_indices(anchors: Sequence[Mapping[str, Any]]) -> list[int]:
    return [
        index
        for index, anchor in enumerate(anchors)
        if str(anchor.get("anchor_type", "")).upper() in ("DIM", "TEXT")
        and finite_float(anchor.get("display_value")) not in (None, 0.0)
    ]


def randomized_corruption(
    raw_anchors: Sequence[Mapping[str, Any]], rng: random.Random, case_index: int
) -> tuple[list[dict[str, Any]], str]:
    anchors = [copy.deepcopy(dict(anchor)) for anchor in raw_anchors]
    ratio_indices = _ratio_indices(anchors)
    if not anchors or not ratio_indices:
        return anchors, "no_ratio_anchor"
    family = rng.choice(
        (
            "outlier_clone",
            "stale_override",
            "suffix_removal",
            "exact_duplicate",
            "geometry_ratio_break",
            "reference_support_drop",
        )
    )
    index = rng.choice(ratio_indices)
    factor = rng.uniform(1.25, 25.0)
    if family == "outlier_clone":
        clone = copy.deepcopy(anchors[index])
        shift = rng.uniform(1.0e4, 1.0e8)
        for key in ("p0", "p1"):
            clone[key] = [
                float(clone[key][0]) + shift,
                float(clone[key][1]) - 0.375 * shift,
            ]
        clone["handle"] = f"{clone.get('handle', 'ANCHOR')}__PROP_OUT_{case_index:03d}"
        clone["display_value"] = float(clone["display_value"]) * factor
        clone["weight"] = min(float(clone.get("weight", 1.0)), rng.uniform(0.05, 1.0))
        clone["diagnostic_mutation"] = family
        anchors.append(clone)
    elif family == "stale_override":
        anchors[index]["display_value"] = float(anchors[index]["display_value"]) * factor
        anchors[index]["diagnostic_mutation"] = family
    elif family == "suffix_removal":
        for ratio_index in ratio_indices:
            anchors[ratio_index]["display_unit"] = "UNKNOWN"
            anchors[ratio_index]["diagnostic_mutation"] = family
    elif family == "exact_duplicate":
        clone = copy.deepcopy(anchors[index])
        clone["handle"] = f"{clone.get('handle', 'ANCHOR')}__PROP_DUP_{case_index:03d}"
        clone["diagnostic_mutation"] = family
        anchors.append(clone)
    elif family == "geometry_ratio_break":
        p0 = [float(value) for value in anchors[index]["p0"][:2]]
        p1 = [float(value) for value in anchors[index]["p1"][:2]]
        geometry_factor = rng.choice((0.1, 0.2, 3.0, 5.0))
        anchors[index]["p1"] = [
            p0[0] + (p1[0] - p0[0]) * geometry_factor,
            p0[1] + (p1[1] - p0[1]) * geometry_factor,
        ]
        anchors[index]["diagnostic_mutation"] = family
    elif family == "reference_support_drop":
        span = geometric_span(anchors[index])
        assert span is not None
        anchors[index]["text_height"] = float(span) / rng.uniform(1.1, 9.9)
        anchors[index]["diagnostic_mutation"] = family
    return anchors, family


def monotonicity_property_test(
    case_count: int = PROPERTY_CASES, seed: int = PROPERTY_SEED
) -> dict[str, Any]:
    scene_paths = sorted(L1B_SCENE_DIR.glob("scene_*.json")) + sorted(
        V1_SCENE_DIR.glob("scene_*.json")
    )
    if len(scene_paths) != 400:
        raise RuntimeError(f"expected 400 replay scenes, found {len(scene_paths)}")
    rng = random.Random(seed)
    upward = {
        "confidence_score": 0,
        "status": 0,
        "unit_status": 0,
        "reference_status": 0,
    }
    family_counts: dict[str, int] = {}
    counterexamples: list[dict[str, Any]] = []
    case_digests: list[str] = []
    for case_index in range(case_count):
        path = scene_paths[rng.randrange(len(scene_paths))]
        scene = json.loads(path.read_text(encoding="utf-8"))
        before = fit_anchor_model(scene["anchors"])
        corrupted, family = randomized_corruption(scene["anchors"], rng, case_index)
        after = fit_anchor_model(corrupted)
        family_counts[family] = family_counts.get(family, 0) + 1
        increases = {
            "confidence_score": float(after["confidence_score"])
            > float(before["confidence_score"]) + 1e-15,
            "status": STATUS_RANK[str(after["status"])]
            > STATUS_RANK[str(before["status"])],
            "unit_status": STATUS_RANK[str(after["unit_status"])]
            > STATUS_RANK[str(before["unit_status"])],
            "reference_status": STATUS_RANK[str(after["reference_status"])]
            > STATUS_RANK[str(before["reference_status"])],
        }
        for field, increased in increases.items():
            upward[field] += int(increased)
        record = {
            "case_index": case_index,
            "scene": path.name,
            "family": family,
            "before": _model_snapshot(before),
            "after": _model_snapshot(after),
            "increases": increases,
        }
        case_digests.append(canonical_sha256(record))
        if any(increases.values()) and len(counterexamples) < 10:
            counterexamples.append(record)
    return {
        "passed": sum(upward.values()) == 0,
        "seed": seed,
        "case_count": case_count,
        "family_counts": dict(sorted(family_counts.items())),
        "upward_counts": upward,
        "counterexamples": counterexamples,
        "cases_digest": canonical_sha256(case_digests),
    }


def run_selftests(stream: io.TextIOBase) -> dict[str, Any]:
    legacy = run_legacy_selftests(stream)
    counterexample = counterexample_regression()
    print(
        "SELFTEST live_counterexample_regression: "
        f"{'PASS' if counterexample['passed'] else 'FAIL'} | "
        f"old_status_rise={counterexample['old_status_rise_count']} "
        f"new_upward={sum(counterexample['new_upward_counts'].values())}",
        file=stream,
    )
    property_result = monotonicity_property_test()
    print(
        "SELFTEST seeded_monotonicity_300: "
        f"{'PASS' if property_result['passed'] else 'FAIL'} | "
        f"seed={property_result['seed']} cases={property_result['case_count']} "
        f"upward={sum(property_result['upward_counts'].values())}",
        file=stream,
    )
    tests = [
        *legacy["tests"],
        {
            "name": "live_counterexample_regression",
            "passed": counterexample["passed"],
            "detail": counterexample,
        },
        {
            "name": "seeded_monotonicity_300",
            "passed": property_result["passed"],
            "detail": property_result,
        },
    ]
    passed = sum(bool(test["passed"]) for test in tests)
    print(f"SELFTEST SUMMARY EXTENDED: {passed}/{len(tests)} passed", file=stream)
    return {
        "passed": passed,
        "total": len(tests),
        "tests": tests,
        "legacy": legacy,
        "counterexample": counterexample,
        "monotonicity_property": property_result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    arguments = parser.parse_args(argv)
    if not arguments.selftest:
        parser.error("only --selftest is supported; use loop_l1c.py for cohort replay")
    stream = io.StringIO()
    results = run_selftests(stream)
    print(stream.getvalue(), end="")
    return 0 if results["passed"] == results["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
