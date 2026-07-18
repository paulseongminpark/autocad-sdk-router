#!/usr/bin/env python3
"""C1v5 estimator: denominator-preserving consensus redesign for E2 loop L1d.

The sealed original and L1c/v2 estimators are imported read-only.  This module
normalizes explicit units before ratio-mode selection, collapses independence
to unique source handles, keeps reference-span fitting label-free, and computes
every confidence factor against the complete candidate denominator.
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
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


sys.dont_write_bytecode = True

CELL_DIR = Path(__file__).resolve().parent
ORIGINAL_C1_PATH = Path(r"D:\runs\e2_program\cells\feyerabend_c1\feyerabend_c1.py")
V2_PATH = Path(r"D:\runs\e2_program\cells\loop_l1c\feyerabend_c1_v2.py")
V1_COUNTEREXAMPLE_SCENE = Path(
    r"D:\runs\e2_program\cells\feyerabend_c0\scenes\scene_001_k1000.json"
)
L1B_SCENE_DIR = Path(r"D:\runs\e2_program\cells\loop_l1b\scenes_v3")
V1_SCENE_DIR = Path(r"D:\runs\e2_program\cells\feyerabend_c0\scenes")
PROPERTY_SEED = 20260719
PROPERTY_CASES = 600
STATUS_RANK = {"NONE": 0, "LOW": 1, "HIGH": 2}
TRACKED_FIELDS = (
    "confidence_score",
    "reference_confidence_score",
    "status",
    "unit_status",
    "reference_status",
)
PROPERTY_FAMILIES = (
    "outlier_clone",
    "stale_override",
    "suffix_removal",
    "exact_duplicate",
    "geometry_ratio_break",
    "reference_support_drop",
    "display_removal",
    "handle_collision",
    "type_to_grid",
)


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


ORIGINAL = _load_module("loop_l1d_original_c1_readonly", ORIGINAL_C1_PATH)
V2 = _load_module("loop_l1d_v2_readonly", V2_PATH)

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


def _handle_groups(anchors: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for anchor in anchors:
        groups[str(anchor["handle"])].append(dict(anchor))
    return dict(sorted(groups.items()))


def _ratio_entry(anchor: Mapping[str, Any]) -> dict[str, Any] | None:
    if str(anchor["anchor_type"]) not in ("DIM", "TEXT"):
        return None
    display = finite_float(anchor.get("display_value"))
    if display is None or display <= 0.0:
        return None
    unit = str(anchor.get("display_unit", "UNKNOWN")).upper()
    if unit in UNIT_TO_MM:
        space = "z_mm"
        normalized_display = float(display) * float(UNIT_TO_MM[unit])
    else:
        space = "z_raw"
        normalized_display = float(display)
    return {
        **dict(anchor),
        "ratio_space": space,
        "normalized_display": normalized_display,
        "log_ratio": math.log(normalized_display / float(anchor["raw_span"])),
    }


def _ratio_candidates(
    anchors: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return all ratio records, one eligible representative per handle, and observations."""
    all_records: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    for handle, group in _handle_groups(anchors).items():
        role_records: list[dict[str, Any]] = []
        entries: list[dict[str, Any]] = []
        for anchor in group:
            if str(anchor["anchor_type"]) not in ("DIM", "TEXT"):
                continue
            entry = _ratio_entry(anchor)
            if entry is None:
                role_records.append(
                    {
                        **dict(anchor),
                        "ratio_space": "missing",
                        "normalized_display": None,
                        "log_ratio": None,
                    }
                )
            else:
                role_records.append(entry)
                entries.append(entry)
        if not role_records:
            continue
        all_records.extend(role_records)
        if not entries:
            observations.append(
                {
                    "handle": handle,
                    "reason": "ratio_missing_denominator_only",
                    "record_count": len(role_records),
                    "ratio_spaces": ["missing"],
                }
            )
            continue
        spaces = sorted({str(entry["ratio_space"]) for entry in entries})
        values = [float(entry["log_ratio"]) for entry in entries]
        conflict = (
            len(entries) != len(role_records)
            or len(spaces) != 1
            or max(values) - min(values) > RANSAC_LOG_TOLERANCE + 1e-15
        )
        representative = copy.deepcopy(entries[0])
        representative["weight"] = max(float(entry["weight"]) for entry in entries)
        representative["source_record_count"] = len(entries)
        if conflict:
            observations.append(
                {
                    "handle": handle,
                    "reason": "source_handle_ratio_conflict",
                    "record_count": len(role_records),
                    "ratio_spaces": sorted(
                        {str(entry["ratio_space"]) for entry in role_records}
                    ),
                    "log_ratio_min": min(values),
                    "log_ratio_max": max(values),
                }
            )
        else:
            eligible.append(representative)
    return all_records, eligible, observations


def _annotation_scale(anchor: Mapping[str, Any]) -> bool:
    text_height = finite_float(anchor.get("text_height"))
    return bool(
        text_height is not None
        and text_height > 0.0
        and float(anchor["raw_span"]) / text_height < 10.0
    )


def _reference_candidates(
    anchors: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Collect label-free spans; suspicious records remain in the denominator."""
    all_records: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    for handle, group in _handle_groups(anchors).items():
        entries = [{**dict(anchor), "log_span": math.log(float(anchor["raw_span"]))} for anchor in group]
        all_records.extend(entries)
        values = [float(entry["log_span"]) for entry in entries]
        span_conflict = max(values) - min(values) > RANSAC_LOG_TOLERANCE + 1e-15
        annotation = any(_annotation_scale(entry) for entry in entries)
        representative = copy.deepcopy(entries[0])
        representative["weight"] = max(float(entry["weight"]) for entry in entries)
        representative["source_record_count"] = len(entries)
        reasons: list[str] = []
        if span_conflict:
            reasons.append("source_handle_span_conflict")
        if annotation:
            reasons.append("annotation_scale_candidate")
        if reasons:
            observations.append(
                {
                    "handle": handle,
                    "reasons": reasons,
                    "record_count": len(entries),
                    "log_span_min": min(values),
                    "log_span_max": max(values),
                }
            )
        else:
            eligible.append(representative)
    return all_records, eligible, observations


def _select_consensus(
    eligible_records: Sequence[Mapping[str, Any]],
    value_key: str,
    *,
    spaces: bool,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not eligible_records:
        return None, []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in eligible_records:
        grouped[str(record.get("ratio_space", "span"))].append(dict(record))
    candidates: list[tuple[tuple[Any, ...], dict[str, Any], list[dict[str, Any]]]] = []
    for space, records in sorted(grouped.items()):
        consensus = maximum_consensus(records, value_key, RANSAC_LOG_TOLERANCE)
        assert consensus is not None
        inliers = [records[index] for index in consensus["inlier_indices"]]
        space_priority = 0 if space == "z_mm" else 1
        rank = (
            -float(consensus["inlier_weight"]),
            -len(inliers),
            float(consensus["log_mad"]),
            space_priority if spaces else 0,
            space,
        )
        selected = dict(consensus)
        selected["space"] = space
        candidates.append((rank, selected, inliers))
    candidates.sort(key=lambda row: row[0])
    return candidates[0][1], candidates[0][2]


def _denominator_confidence(
    consensus: Mapping[str, Any],
    inliers: Sequence[Mapping[str, Any]],
    all_candidates: Sequence[Mapping[str, Any]],
    *,
    trusted_handles: set[str] | None = None,
) -> dict[str, Any]:
    """Compute confidence in one candidate frame with a non-shrinking denominator.

    The selected mode still supplies the estimate, but HIGH confidence is
    intentionally conservative: every candidate record and every unique source
    handle must remain coherent with that mode.  A partial mode therefore stays
    measurable while receiving confidence score zero instead of being allowed
    to improve when one suspicious record reinforces it.
    """
    inlier_handles = {str(record["handle"]) for record in inliers}
    candidate_handles = {str(record["handle"]) for record in all_candidates}
    confidence_handles = (
        inlier_handles
        if trusted_handles is None
        else inlier_handles.intersection(trusted_handles)
    )
    inlier_weight = math.fsum(float(record["weight"]) for record in inliers)
    candidate_weight = math.fsum(float(record["weight"]) for record in all_candidates)
    consensus_fraction = (
        0.0
        if candidate_weight <= 0.0
        else min(1.0, max(0.0, inlier_weight / candidate_weight))
    )
    residual_factor = math.exp(
        -float(consensus["log_mad"]) / RANSAC_LOG_TOLERANCE
    )
    if math.isclose(residual_factor, 1.0, rel_tol=0.0, abs_tol=1e-12):
        residual_factor = 1.0
    independent_fraction = min(
        1.0,
        0.0
        if not candidate_handles
        else len(confidence_handles) / len(candidate_handles)
    )

    def bin_set(
        records: Sequence[Mapping[str, Any]],
        bounds: tuple[float, float, float, float],
    ) -> set[tuple[int, int]]:
        xmin, xmax, ymin, ymax = bounds

        def axis_bin(value: float, low: float, high: float) -> int:
            if abs(high - low) <= EPSILON:
                return 1
            return min(
                2,
                max(0, int(math.floor(3.0 * (value - low) / (high - low)))),
            )

        return {
            (
                axis_bin(midpoint(record)[0], xmin, xmax),
                axis_bin(midpoint(record)[1], ymin, ymax),
            )
            for record in records
        }

    candidate_points = [midpoint(record) for record in all_candidates]
    if candidate_points:
        bounds = (
            min(point[0] for point in candidate_points),
            max(point[0] for point in candidate_points),
            min(point[1] for point in candidate_points),
            max(point[1] for point in candidate_points),
        )
        candidate_bin_set = bin_set(all_candidates, bounds)
        inlier_bin_set = bin_set(inliers, bounds)
    else:
        candidate_bin_set = set()
        inlier_bin_set = set()
    inlier_bins = len(inlier_bin_set)
    candidate_bins = len(candidate_bin_set)
    spatial_fraction = min(
        1.0, 0.0 if candidate_bins <= 0 else inlier_bins / candidate_bins
    )
    all_candidates_coherent = (
        len(inliers) == len(all_candidates)
        and inlier_handles == candidate_handles
        and math.isclose(inlier_weight, candidate_weight, rel_tol=1e-12, abs_tol=1e-15)
    )
    score = (
        consensus_fraction
        * residual_factor
        * independent_fraction
        * spatial_fraction
        * int(all_candidates_coherent)
    )
    return {
        "score": float(score),
        "n_independent": len(confidence_handles),
        "n_candidate_handles": len(candidate_handles),
        "n_spatial_bins": inlier_bins,
        "n_candidate_spatial_bins": candidate_bins,
        "candidate_record_count": len(all_candidates),
        "inlier_record_count": len(inliers),
        "candidate_weight": float(candidate_weight),
        "inlier_weight": float(inlier_weight),
        "consensus_fraction": float(consensus_fraction),
        "residual_factor": float(residual_factor),
        "independent_fraction": float(independent_fraction),
        "spatial_fraction": float(spatial_fraction),
        "all_candidates_coherent": bool(all_candidates_coherent),
        "confidence_inlier_handles": sorted(confidence_handles),
    }


def _consensus_with_full_denominator(
    consensus: Mapping[str, Any] | None,
    confidence: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if consensus is None or confidence is None:
        return None
    output = dict(consensus)
    output["total_weight"] = float(confidence["candidate_weight"])
    output["inlier_weight"] = float(confidence["inlier_weight"])
    output["consensus_weight"] = float(confidence["consensus_fraction"])
    return output


def fit_anchor_model(raw_anchors: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Fit anchor-only scale and span models with immutable candidate denominators."""
    anchors, audit = prepare_anchors(raw_anchors)

    ratio_all, ratio_eligible, ratio_observations = _ratio_candidates(anchors)
    ratio_consensus_raw, ratio_inliers = _select_consensus(
        ratio_eligible, "log_ratio", spaces=True
    )
    if ratio_consensus_raw is None:
        ratio_confidence = None
        ratio_consensus = None
        scale_estimate = None
        unit_status = "NONE"
        ratio_space = None
    else:
        ratio_confidence = _denominator_confidence(
            ratio_consensus_raw, ratio_inliers, ratio_all
        )
        ratio_consensus = _consensus_with_full_denominator(
            ratio_consensus_raw, ratio_confidence
        )
        assert ratio_consensus is not None
        scale_estimate = math.exp(float(ratio_consensus["location"]))
        unit_status = _status(True, ratio_consensus, ratio_confidence)
        ratio_space = str(ratio_consensus_raw["space"])

    ratio_inlier_handles = {str(record["handle"]) for record in ratio_inliers}
    ratio_candidate_handles = {str(record["handle"]) for record in ratio_all}
    ratio_outlier_handles = sorted(ratio_candidate_handles - ratio_inlier_handles)
    if ratio_space == "z_mm":
        physical_unit = "MM"
        mm_per_raw = scale_estimate
    elif ratio_space == "z_raw":
        physical_unit = "UNKNOWN"
        mm_per_raw = None
    else:
        physical_unit = "UNKNOWN"
        mm_per_raw = None

    reference_all, reference_eligible, reference_observations = _reference_candidates(
        anchors
    )
    reference_consensus_raw, reference_inliers = _select_consensus(
        reference_eligible, "log_span", spaces=False
    )
    if reference_consensus_raw is None:
        reference_confidence = None
        reference_consensus = None
        reference_span = None
        reference_status = "NONE"
    else:
        reference_span_inlier_handles = {
            str(record["handle"]) for record in reference_inliers
        }
        reference_trusted_handles = reference_span_inlier_handles - set(
            ratio_outlier_handles
        )
        reference_confidence = _denominator_confidence(
            reference_consensus_raw,
            reference_inliers,
            reference_all,
            trusted_handles=reference_trusted_handles,
        )
        reference_consensus = _consensus_with_full_denominator(
            reference_consensus_raw, reference_confidence
        )
        assert reference_consensus is not None
        reference_span = math.exp(float(reference_consensus["location"]))
        reference_status = _status(True, reference_consensus, reference_confidence)

    reference_inlier_handles = {str(record["handle"]) for record in reference_inliers}
    reference_candidate_handles = {str(record["handle"]) for record in reference_all}
    reference_outlier_handles = sorted(
        reference_candidate_handles - reference_inlier_handles
    )
    source_diversity = sorted({str(anchor["anchor_type"]) for anchor in anchors})
    return {
        "status": reference_status,
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
        "n_candidate_handles": 0
        if ratio_confidence is None
        else int(ratio_confidence["n_candidate_handles"]),
        "n_spatial_bins": 0
        if ratio_confidence is None
        else int(ratio_confidence["n_spatial_bins"]),
        "n_candidate_spatial_bins": 0
        if ratio_confidence is None
        else int(ratio_confidence["n_candidate_spatial_bins"]),
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
        "reference_n_candidate_handles": 0
        if reference_confidence is None
        else int(reference_confidence["n_candidate_handles"]),
        "reference_n_spatial_bins": 0
        if reference_confidence is None
        else int(reference_confidence["n_spatial_bins"]),
        "reference_n_candidate_spatial_bins": 0
        if reference_confidence is None
        else int(reference_confidence["n_candidate_spatial_bins"]),
        "reference_confidence_score": 0.0
        if reference_confidence is None
        else float(reference_confidence["score"]),
        "provenance": {
            **audit,
            "revision": "c1v5_denominator_preserving_consensus",
            "ratio_mode_space": ratio_space,
            "ratio_inlier_handles": sorted(ratio_inlier_handles),
            "ratio_outlier_handles": ratio_outlier_handles,
            "ratio_observations": ratio_observations,
            "reference_inlier_handles": sorted(reference_inlier_handles),
            "reference_confidence_inlier_handles": []
            if reference_confidence is None
            else list(reference_confidence["confidence_inlier_handles"]),
            "reference_outlier_handles": reference_outlier_handles,
            "reference_rejections": reference_observations,
            "reference_label_policy": "label_free_span_space",
            "independence_key": "unique_source_handle",
            "denominator_policy": {
                "ratio": None if ratio_confidence is None else ratio_confidence,
                "reference": None
                if reference_confidence is None
                else reference_confidence,
                "candidate_records_removed_after_classification": 0,
            },
        },
    }


def anchor_artifact_from_scene(scene: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "artifact_schema": "ariadne.e2.feyerabend_c1.anchor_artifact.v3",
        "model": fit_anchor_model(copy.deepcopy(scene["anchors"])),
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
            "reference_confidence_score_before": model[
                "reference_confidence_score"
            ],
            "reference_confidence_score_after": corrupted_model[
                "reference_confidence_score"
            ],
            "reference_n_independent_before": model["reference_n_independent"],
            "reference_n_independent_after": corrupted_model[
                "reference_n_independent"
            ],
            "reference_n_spatial_bins_before": model["reference_n_spatial_bins"],
            "reference_n_spatial_bins_after": corrupted_model[
                "reference_n_spatial_bins"
            ],
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


def _snapshot(model: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "confidence_score": float(model["confidence_score"]),
        "reference_confidence_score": float(model["reference_confidence_score"]),
        "status": str(model["status"]),
        "unit_status": str(model["unit_status"]),
        "reference_status": str(model["reference_status"]),
        "display_per_raw": model["display_per_raw"],
        "mm_per_raw": model["mm_per_raw"],
        "consensus_weight": model["consensus_weight"],
        "reference_consensus_weight": model["reference_consensus_weight"],
        "n_independent": int(model["n_independent"]),
        "n_candidate_handles": int(
            model.get("n_candidate_handles", model.get("n_independent", 0))
        ),
        "n_spatial_bins": int(model["n_spatial_bins"]),
        "reference_n_independent": int(model["reference_n_independent"]),
        "reference_n_candidate_handles": int(
            model.get(
                "reference_n_candidate_handles",
                model.get("reference_n_independent", 0),
            )
        ),
        "reference_n_spatial_bins": int(model["reference_n_spatial_bins"]),
        "ratio_inlier_handles": list(model["provenance"]["ratio_inlier_handles"]),
        "ratio_outlier_handles": list(model["provenance"]["ratio_outlier_handles"]),
        "reference_inlier_handles": list(
            model["provenance"]["reference_inlier_handles"]
        ),
        "reference_outlier_handles": list(
            model["provenance"]["reference_outlier_handles"]
        ),
    }


def _increases(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, bool]:
    return {
        "confidence_score": float(after["confidence_score"])
        > float(before["confidence_score"]) + 1e-15,
        "reference_confidence_score": float(after["reference_confidence_score"])
        > float(before["reference_confidence_score"]) + 1e-15,
        "status": STATUS_RANK[str(after["status"])]
        > STATUS_RANK[str(before["status"])],
        "unit_status": STATUS_RANK[str(after["unit_status"])]
        > STATUS_RANK[str(before["unit_status"])],
        "reference_status": STATUS_RANK[str(after["reference_status"])]
        > STATUS_RANK[str(before["reference_status"])],
    }


def _ratio_indices(anchors: Sequence[Mapping[str, Any]]) -> list[int]:
    return [
        index
        for index, anchor in enumerate(anchors)
        if str(anchor.get("anchor_type", "")).upper() in ("DIM", "TEXT")
        and finite_float(anchor.get("display_value")) not in (None, 0.0)
    ]


def randomized_corruption(
    raw_anchors: Sequence[Mapping[str, Any]],
    family: str,
    rng: random.Random,
    case_index: int,
) -> list[dict[str, Any]]:
    if family not in PROPERTY_FAMILIES:
        raise ValueError(f"unknown property family: {family}")
    anchors = [copy.deepcopy(dict(anchor)) for anchor in raw_anchors]
    ratio_indices = _ratio_indices(anchors)
    if not anchors or not ratio_indices:
        return anchors
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
        clone["weight"] = min(
            float(clone.get("weight", 1.0)), rng.uniform(0.05, 1.0)
        )
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
    elif family == "display_removal":
        anchors[index]["display_value"] = None
        anchors[index]["diagnostic_mutation"] = family
    elif family == "handle_collision":
        clone = copy.deepcopy(anchors[index])
        shift = rng.uniform(1.0e4, 1.0e8)
        for key in ("p0", "p1"):
            clone[key] = [float(clone[key][0]) + shift, float(clone[key][1]) + shift]
        clone["display_value"] = float(clone["display_value"]) * factor
        clone["diagnostic_mutation"] = family
        anchors.append(clone)
    elif family == "type_to_grid":
        anchors[index]["anchor_type"] = "GRID"
        anchors[index].pop("display_value", None)
        anchors[index].pop("display_unit", None)
        anchors[index]["diagnostic_mutation"] = family
    return anchors


def monotonicity_property_test(
    case_count: int = PROPERTY_CASES, seed: int = PROPERTY_SEED
) -> dict[str, Any]:
    scene_paths = sorted(L1B_SCENE_DIR.glob("scene_*.json")) + sorted(
        V1_SCENE_DIR.glob("scene_*.json")
    )
    if len(scene_paths) != 400:
        raise RuntimeError(f"expected 400 replay scenes, found {len(scene_paths)}")
    loaded = []
    for path in scene_paths:
        scene = json.loads(path.read_text(encoding="utf-8"))
        loaded.append((path, scene, len(_ratio_indices(scene["anchors"]))))
    rng = random.Random(seed)
    upward = Counter({field: 0 for field in TRACKED_FIELDS})
    family_counts: Counter[str] = Counter()
    family_by_cohort: dict[str, Counter[str]] = defaultdict(Counter)
    counterexamples: list[dict[str, Any]] = []
    case_digests: list[str] = []
    for case_index in range(case_count):
        family = PROPERTY_FAMILIES[case_index % len(PROPERTY_FAMILIES)]
        pool = (
            [row for row in loaded if row[2] >= 3]
            if family in ("outlier_clone", "handle_collision")
            else loaded
        )
        path, scene, ratio_count = pool[rng.randrange(len(pool))]
        before_model = fit_anchor_model(scene["anchors"])
        corrupted = randomized_corruption(
            scene["anchors"], family, rng, case_index
        )
        after_model = fit_anchor_model(corrupted)
        before = _snapshot(before_model)
        after = _snapshot(after_model)
        rises = _increases(before, after)
        for field, rose in rises.items():
            upward[field] += int(rose)
        family_counts[family] += 1
        cohort = "l1b" if path.parent == L1B_SCENE_DIR else "c1_original"
        family_by_cohort[family][cohort] += 1
        record = {
            "case_index": case_index,
            "scene": path.name,
            "cohort": cohort,
            "family": family,
            "input_ratio_anchor_count": ratio_count,
            "before": before,
            "after": after,
            "increases": rises,
        }
        case_digests.append(canonical_sha256(record))
        if any(rises.values()) and len(counterexamples) < 20:
            counterexamples.append(record)
    return {
        "seed": seed,
        "case_count": case_count,
        "scene_pool_count": len(scene_paths),
        "family_counts": dict(sorted(family_counts.items())),
        "family_by_cohort": {
            family: dict(sorted(counts.items()))
            for family, counts in sorted(family_by_cohort.items())
        },
        "upward_counts": dict(upward),
        "observed_zero_upward": sum(upward.values()) == 0,
        "counterexamples": counterexamples,
        "cases_digest": canonical_sha256(case_digests),
    }


def _make_anchor(
    handle: str,
    span: float,
    display: Any,
    x: float,
    y: float,
    *,
    anchor_type: str = "DIM",
    unit: str = "MM",
    weight: float = 1.0,
    text_height: float | None = None,
) -> dict[str, Any]:
    return {
        "handle": handle,
        "anchor_type": anchor_type,
        "region": "P",
        "p0": [x, y],
        "p1": [x + span, y],
        "raw_span": span,
        "display_value": display,
        "display_unit": unit,
        "text_height": text_height,
        "weight": weight,
    }


POSITIONS = (
    (0.0, 0.0),
    (0.0, 10000.0),
    (10000.0, 0.0),
    (10000.0, 10000.0),
    (5000.0, 5000.0),
    (20000.0, 0.0),
    (0.0, 20000.0),
    (20000.0, 20000.0),
)


def _probe_transition(
    estimator: Any,
    before_anchors: Sequence[Mapping[str, Any]],
    after_anchors: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    before = _snapshot(estimator.fit_anchor_model(before_anchors))
    after = _snapshot(estimator.fit_anchor_model(after_anchors))
    return {"before": before, "after": after, "increases": _increases(before, after)}


def _probe_all_estimators(
    before_anchors: Sequence[Mapping[str, Any]],
    after_anchors: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "v1": _probe_transition(ORIGINAL, before_anchors, after_anchors),
        "v2": _probe_transition(V2, before_anchors, after_anchors),
        "v3": _probe_transition(sys.modules[__name__], before_anchors, after_anchors),
    }


def fleet_probe_suite() -> dict[str, Any]:
    scene = json.loads(V1_COUNTEREXAMPLE_SCENE.read_text(encoding="utf-8"))
    anchors = scene["anchors"]
    base_id = str(scene["base_scene_id"])
    sealed = apply_corruption(anchors, "single_outlier", base_id)
    probes: dict[str, Any] = {
        "P0_first_fleet_live_counterexample": _probe_all_estimators(anchors, sealed)
    }

    def variant(tag: str, mutation: str) -> None:
        mutated = apply_corruption(anchors, "single_outlier", base_id)
        clone = mutated[-1]
        if mutation == "display_removal":
            clone["display_value"] = None
        elif mutation == "handle_collision":
            clone["handle"] = str(clone["handle"]).split("__OUT_")[0]
        elif mutation == "type_to_grid":
            clone["anchor_type"] = "GRID"
            clone.pop("display_value", None)
            clone.pop("display_unit", None)
            clone.pop("weight", None)
        elif mutation == "ratio_consistent_complete_forgery":
            clone["display_value"] = float(clone["display_value"]) / 10.0
        else:
            raise ValueError(mutation)
        probes[tag] = _probe_all_estimators(anchors, mutated)

    variant("B2_display_removal", "display_removal")
    variant("B3_handle_collision", "handle_collision")
    variant("B1_type_to_grid", "type_to_grid")
    variant("B4_ratio_consistent_complete_forgery", "ratio_consistent_complete_forgery")

    mixed = [
        _make_anchor("MIX_MM_0", 100.0, 250.0, 0.0, 0.0, unit="MM", text_height=1.0),
        _make_anchor("MIX_MM_1", 100.0, 250.0, 200.0, 0.0, unit="MM", text_height=1.0),
        _make_anchor("MIX_MM_2", 100.0, 250.0, 0.0, 200.0, unit="MM", text_height=1.0),
        _make_anchor("MIX_M_0", 100.0, 0.25, 200.0, 200.0, unit="M", text_height=1.0),
        _make_anchor("MIX_M_1", 100.0, 0.25, 100.0, 100.0, unit="M", text_height=1.0),
    ]
    stale = [
        _make_anchor("STALE_0", 100.0, 250.0, 0.0, 0.0, text_height=1.0),
        _make_anchor("STALE_1", 100.0, 250.0, 200.0, 0.0, text_height=1.0),
        _make_anchor("STALE_2", 100.0, 250.0, 0.0, 200.0, text_height=1.0),
        _make_anchor("STALE_3", 100.0, 225.0, 200.0, 200.0, text_height=1.0),
    ]
    capture = [
        _make_anchor("TRUE_0", 100.0, 250.0, 0.0, 0.0, text_height=1.0),
        _make_anchor("TRUE_1", 100.0, 250.0, 200.0, 0.0, text_height=1.0),
        _make_anchor("TRUE_2", 100.0, 250.0, 0.0, 200.0, text_height=1.0),
        _make_anchor("FAKE_0", 100.0, 2500.0, 400.0, 400.0, text_height=1.0),
        _make_anchor("FAKE_1", 100.0, 2500.0, 600.0, 400.0, text_height=1.0),
        _make_anchor("FAKE_2", 100.0, 2500.0, 400.0, 600.0, text_height=1.0),
        _make_anchor("FAKE_3", 100.0, 2500.0, 600.0, 600.0, text_height=1.0),
    ]
    probes["O1_honest_mixed_unit"] = {
        "v1": _snapshot(ORIGINAL.fit_anchor_model(mixed)),
        "v2": _snapshot(V2.fit_anchor_model(mixed)),
        "v3": _snapshot(fit_anchor_model(mixed)),
    }
    probes["O2_stale_label"] = {
        "v1": _snapshot(ORIGINAL.fit_anchor_model(stale)),
        "v2": _snapshot(V2.fit_anchor_model(stale)),
        "v3": _snapshot(fit_anchor_model(stale)),
    }
    probes["O3_mode_capture"] = {
        "v1": _snapshot(ORIGINAL.fit_anchor_model(capture)),
        "v2": _snapshot(V2.fit_anchor_model(capture)),
        "v3": _snapshot(fit_anchor_model(capture)),
    }

    two = [
        _make_anchor("B4_LOW_0", 100.0, 250.0, *POSITIONS[0]),
        _make_anchor("B4_LOW_1", 100.0, 250.0, *POSITIONS[1]),
    ]
    two_plus_forgery = copy.deepcopy(two)
    forged = copy.deepcopy(two[0])
    forged["handle"] = "B4_LOW_FORGED"
    forged["p0"] = list(POSITIONS[2])
    forged["p1"] = [POSITIONS[2][0] + 100.0, POSITIONS[2][1]]
    two_plus_forgery.append(forged)
    probes["B4_information_limit_two_to_three"] = _probe_all_estimators(
        two, two_plus_forgery
    )

    sweep: list[dict[str, Any]] = []
    for good_count in range(3, 9):
        for outlier_count in range(1, 4):
            for factor in (1.25, 2.0, 25.0):
                before = [
                    _make_anchor(
                        f"G{index}", 100.0, 100.0, *POSITIONS[index % len(POSITIONS)]
                    )
                    for index in range(good_count)
                ]
                for index in range(outlier_count):
                    pos = POSITIONS[(good_count + index) % len(POSITIONS)]
                    before.append(
                        _make_anchor(
                            f"O{index}",
                            1000.0 + 100.0 * index,
                            1000.0 + 100.0 * index,
                            *pos,
                        )
                    )
                after = copy.deepcopy(before)
                after[good_count]["display_value"] = (
                    float(after[good_count]["display_value"]) * factor
                )
                result = _probe_all_estimators(before, after)
                sweep.append(
                    {
                        "good_count": good_count,
                        "outlier_count": outlier_count,
                        "factor": factor,
                        "result": result,
                    }
                )

    gate_probe_ids = (
        "P0_first_fleet_live_counterexample",
        "B1_type_to_grid",
        "B2_display_removal",
        "B3_handle_collision",
    )
    gate_upward = Counter({field: 0 for field in TRACKED_FIELDS})
    for probe_id in gate_probe_ids:
        for field, rose in probes[probe_id]["v3"]["increases"].items():
            gate_upward[field] += int(rose)
    sweep_upward = Counter({field: 0 for field in TRACKED_FIELDS})
    for row in sweep:
        for field, rose in row["result"]["v3"]["increases"].items():
            sweep_upward[field] += int(rose)
    o1_downgrade = int(
        STATUS_RANK[probes["O1_honest_mixed_unit"]["v3"]["status"]]
        < STATUS_RANK[probes["O1_honest_mixed_unit"]["v1"]["status"]]
    )
    o2_downgrade = int(
        STATUS_RANK[probes["O2_stale_label"]["v3"]["status"]]
        < STATUS_RANK[probes["O2_stale_label"]["v1"]["status"]]
    )
    return {
        "probes": probes,
        "denominator_cleanup_sweep": {
            "case_count": len(sweep),
            "v3_upward_counts": dict(sweep_upward),
            "cases": sweep,
        },
        "observed_metrics": {
            "gated_probe_count": len(gate_probe_ids),
            "gated_probe_upward_counts": dict(gate_upward),
            "o1_status_downgrade_count": o1_downgrade,
            "o2_status_downgrade_count": o2_downgrade,
            "b4_gate": False,
            "b4_measured_v3_upward_counts": {
                field: int(rose)
                for field, rose in probes[
                    "B4_ratio_consistent_complete_forgery"
                ]["v3"]["increases"].items()
            },
            "b4_low_evidence_v3_upward_counts": {
                field: int(rose)
                for field, rose in probes[
                    "B4_information_limit_two_to_three"
                ]["v3"]["increases"].items()
            },
        },
    }


def run_selftests(stream: io.TextIOBase) -> dict[str, Any]:
    tests: list[dict[str, Any]] = []

    def observe(name: str, value: bool, detail: Mapping[str, Any]) -> None:
        observed = bool(value)
        tests.append({"name": name, "observed": observed, "detail": dict(detail)})
        print(
            f"SELFTEST {name} observed={int(observed)} detail={json.dumps(detail, ensure_ascii=False, sort_keys=True)}",
            file=stream,
        )

    fixture = exact_fixture()
    exact = fit_anchor_model(fixture)
    observe(
        "exact_scale",
        exact["display_per_raw"] is not None
        and math.isclose(float(exact["display_per_raw"]), 2.5, rel_tol=1e-12, abs_tol=1e-12),
        {"estimate": exact["display_per_raw"]},
    )
    observe(
        "exact_unit_high",
        exact["unit_status"] == "HIGH",
        {"unit_status_rank": STATUS_RANK[exact["unit_status"]], "confidence": exact["confidence_score"]},
    )
    empty = fit_anchor_model([])
    observe(
        "empty_honest",
        empty["display_per_raw"] is None
        and empty["unit_status"] == "NONE"
        and empty["status"] == "NONE",
        {
            "estimate_is_none": int(empty["display_per_raw"] is None),
            "unit_status_rank": STATUS_RANK[empty["unit_status"]],
            "status_rank": STATUS_RANK[empty["status"]],
        },
    )
    guarded = GuardedScene(fixture)
    guarded_artifact = anchor_artifact_from_scene(guarded)
    observe(
        "truth_key_access",
        guarded.accessed == ["anchors"]
        and guarded_artifact["model"]["display_per_raw"] is not None,
        {"accessed_keys": len(guarded.accessed)},
    )
    reproducible = all(
        canonical_sha256(apply_corruption(fixture, kind, "fixture_base"))
        == canonical_sha256(apply_corruption(fixture, kind, "fixture_base"))
        for kind in CORRUPTIONS
    )
    observe(
        "corruption_reproducibility",
        reproducible,
        {"corruption_count": len(CORRUPTIONS)},
    )

    fleet = fleet_probe_suite()
    metrics = fleet["observed_metrics"]
    observe(
        "fleet_gated_upward_zero",
        sum(metrics["gated_probe_upward_counts"].values()) == 0,
        metrics["gated_probe_upward_counts"],
    )
    observe(
        "denominator_cleanup_54_upward_zero",
        fleet["denominator_cleanup_sweep"]["case_count"] == 54
        and sum(fleet["denominator_cleanup_sweep"]["v3_upward_counts"].values()) == 0,
        {
            "case_count": fleet["denominator_cleanup_sweep"]["case_count"],
            "upward_total": sum(
                fleet["denominator_cleanup_sweep"]["v3_upward_counts"].values()
            ),
        },
    )
    observe(
        "mixed_unit_no_status_loss",
        metrics["o1_status_downgrade_count"] == 0,
        {"status_downgrade_count": metrics["o1_status_downgrade_count"]},
    )
    observe(
        "stale_label_no_status_loss",
        metrics["o2_status_downgrade_count"] == 0,
        {"status_downgrade_count": metrics["o2_status_downgrade_count"]},
    )
    o1 = fleet["probes"]["O1_honest_mixed_unit"]["v3"]
    observe(
        "z_mm_pre_mode_normalization",
        o1["n_independent"] == 5
        and o1["unit_status"] == "HIGH"
        and o1["mm_per_raw"] is not None
        and math.isclose(float(o1["mm_per_raw"]), 2.5, rel_tol=1e-12, abs_tol=1e-12),
        {
            "n_independent": o1["n_independent"],
            "unit_status_rank": STATUS_RANK[o1["unit_status"]],
            "mm_per_raw": o1["mm_per_raw"],
        },
    )
    b3 = fleet["probes"]["B3_handle_collision"]["v3"]["after"]
    observe(
        "unique_handle_independence",
        b3["n_candidate_handles"] < len(
            fleet["probes"]["B3_handle_collision"]["v3"]["after"][
                "ratio_inlier_handles"
            ]
        )
        + len(b3["ratio_outlier_handles"])
        + 2,
        {
            "n_candidate_handles": b3["n_candidate_handles"],
            "n_independent": b3["n_independent"],
        },
    )
    o2 = fleet["probes"]["O2_stale_label"]["v3"]
    observe(
        "reference_span_label_free",
        len(o2["reference_inlier_handles"]) == 4
        and o2["reference_n_independent"] == 3
        and o2["reference_status"] == "HIGH",
        {
            "reference_span_inlier_count": len(o2["reference_inlier_handles"]),
            "reference_n_independent": o2["reference_n_independent"],
            "reference_status_rank": STATUS_RANK[o2["reference_status"]],
        },
    )

    property_result = monotonicity_property_test()
    observe(
        "seeded_property_600_upward_zero",
        property_result["case_count"] == PROPERTY_CASES
        and property_result["observed_zero_upward"],
        {
            "case_count": property_result["case_count"],
            "seed": property_result["seed"],
            "upward_total": sum(property_result["upward_counts"].values()),
        },
    )
    observed_count = sum(int(test["observed"]) for test in tests)
    print(
        f"SELFTEST_SUMMARY observed_count={observed_count} total={len(tests)}",
        file=stream,
    )
    return {
        "observed_count": observed_count,
        "total": len(tests),
        "tests": tests,
        "fleet": fleet,
        "monotonicity_property": property_result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    arguments = parser.parse_args(argv)
    if not arguments.selftest:
        parser.error("only --selftest is supported; use loop_l1d.py for replay")
    stream = io.StringIO()
    results = run_selftests(stream)
    print(stream.getvalue(), end="")
    return 0 if results["observed_count"] == results["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
