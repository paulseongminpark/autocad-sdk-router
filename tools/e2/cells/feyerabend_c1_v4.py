#!/usr/bin/env python3
"""C1v6 estimator for E2 loop L1e.

This module imports the sealed v3 estimator read-only and replaces only the
consensus/confidence path.  The replacement is handle-set based, requires two
distinct supporting handles for any estimate and three for HIGH, keeps
suspicious evidence out of estimates, and replaces v3's binary coherence gate
with a continuous capped-quadratic attenuation.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import io
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


sys.dont_write_bytecode = True

CELL_DIR = Path(__file__).resolve().parent
V3_PATH = Path(
    r"D:\dev\99_tools\autocad-sdk-router\tools\e2\cells\feyerabend_c1_v3.py"
)
REVISION = "c1v6_witness_principle_continuous_handle_consensus"
MIN_HANDLES_NON_NONE = 2
MIN_HANDLES_HIGH = 3
SEVERE_ATTENUATION_START_TAU = 2.5
SEVERE_ATTENUATION_ZERO_TAU = 3.5
CONTINUOUS_FORMULA = (
    "p_h=min(1,(abs(z_h-z*)/tau)^2); "
    "A_handle=1-mean_h(p_h); "
    "A_space=mean_bins(max_h_in_bin(1-p_h)); "
    "A_severe=1 for dmax<=2.5tau, smoothstep(3.5-dmax) for "
    "2.5tau<dmax<3.5tau, and 0 for dmax>=3.5tau or structural "
    "mixed/conflict/missing evidence; "
    "ratio_score=A_handle*exp(-logMAD/tau)*A_space*A_severe; "
    "reference_score=span_score*mean_h(1-p_ratio,h)*A_severe"
)
BOUNDARY_BEHAVIOR = (
    "At |z_h-z*|=tau the capped quadratic penalty is exactly 1 on both "
    "one-sided limits; therefore an infinitesimal tau crossing cannot create "
    "v3's finite 1-to-0 coherence jump."
)
ESTIMATOR_INPUT_FIELDS = (
    "handle",
    "anchor_type",
    "region",
    "p0",
    "p1",
    "raw_span",
    "display_value",
    "display_unit",
    "text_height",
    "weight",
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


V3 = _load_module("loop_l1e_v3_readonly", V3_PATH)
ORIGINAL = V3.ORIGINAL
V2 = V3.V2

# Re-export the stable v3/original surface used by replay and probe harnesses.
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
    "PROPERTY_SEED",
    "PROPERTY_CASES",
    "STATUS_RANK",
    "TRACKED_FIELDS",
    "PROPERTY_FAMILIES",
    "L1B_SCENE_DIR",
    "V1_SCENE_DIR",
    "V1_COUNTEREXAMPLE_SCENE",
    "POSITIONS",
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
    "randomized_corruption",
    "_ratio_indices",
    "_make_anchor",
):
    globals()[_name] = getattr(V3, _name)


def _handle_groups(
    anchors: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for anchor in anchors:
        groups[str(anchor["handle"])].append(dict(anchor))
    return dict(sorted(groups.items()))


def _first_by_handle(
    anchors: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for anchor in anchors:
        output.setdefault(str(anchor["handle"]), dict(anchor))
    return output


def _distance_penalty(distance: float) -> float:
    """Continuous, saturated suspicion penalty with matching tau limits."""
    scaled = abs(float(distance)) / RANSAC_LOG_TOLERANCE
    return float(min(1.0, scaled * scaled))


def _severity_attenuation(max_scaled_distance: float, structural: bool) -> float:
    """Continuous severe-residual envelope, zero for structural suspicion."""
    if structural:
        return 0.0
    value = float(max_scaled_distance)
    if value <= SEVERE_ATTENUATION_START_TAU:
        return 1.0
    if value >= SEVERE_ATTENUATION_ZERO_TAU:
        return 0.0
    t = (value - SEVERE_ATTENUATION_START_TAU) / (
        SEVERE_ATTENUATION_ZERO_TAU - SEVERE_ATTENUATION_START_TAU
    )
    smooth = 3.0 * t * t - 2.0 * t * t * t
    return float(1.0 - smooth)


def _axis_bin(value: float, low: float, high: float) -> int:
    if abs(high - low) <= EPSILON:
        return 1
    return min(2, max(0, int(math.floor(3.0 * (value - low) / (high - low)))))


def _continuous_policy(
    anchors: Sequence[Mapping[str, Any]],
    candidate_handles: set[str],
    penalty_by_handle: Mapping[str, float],
    support_handles: set[str],
    consensus: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if consensus is None or not candidate_handles:
        return None
    representatives = _first_by_handle(anchors)
    ordered = sorted(candidate_handles)
    penalties = {
        handle: float(min(1.0, max(0.0, penalty_by_handle.get(handle, 1.0))))
        for handle in ordered
    }
    coherence = max(0.0, 1.0 - math.fsum(penalties.values()) / len(ordered))
    residual = math.exp(-float(consensus["log_mad"]) / RANSAC_LOG_TOLERANCE)
    if math.isclose(residual, 1.0, rel_tol=0.0, abs_tol=1e-12):
        residual = 1.0

    points = {
        handle: midpoint(representatives[handle])
        for handle in ordered
        if handle in representatives
    }
    if points:
        xs = [point[0] for point in points.values()]
        ys = [point[1] for point in points.values()]
        bounds = (min(xs), max(xs), min(ys), max(ys))
        bin_quality: dict[tuple[int, int], float] = {}
        for handle, point in points.items():
            key = (
                _axis_bin(point[0], bounds[0], bounds[1]),
                _axis_bin(point[1], bounds[2], bounds[3]),
            )
            bin_quality[key] = max(
                bin_quality.get(key, 0.0), 1.0 - penalties[handle]
            )
        spatial = math.fsum(bin_quality.values()) / len(bin_quality)
        supported_bins = sum(value > 0.0 for value in bin_quality.values())
        candidate_bins = len(bin_quality)
    else:
        spatial = 0.0
        supported_bins = 0
        candidate_bins = 0

    score = coherence * residual * spatial
    return {
        "score": float(score),
        "n_independent": len(support_handles),
        "n_candidate_handles": len(candidate_handles),
        "n_spatial_bins": int(supported_bins),
        "n_candidate_spatial_bins": int(candidate_bins),
        "candidate_record_count": len(candidate_handles),
        "inlier_record_count": len(support_handles),
        "candidate_weight": float(len(candidate_handles)),
        "inlier_weight": float(len(support_handles)),
        "consensus_fraction": float(coherence),
        "residual_factor": float(residual),
        "independent_fraction": float(coherence),
        "spatial_fraction": float(spatial),
        "all_candidates_coherent": all(
            penalty <= 1e-15 for penalty in penalties.values()
        ),
        "confidence_inlier_handles": sorted(support_handles),
        "handle_penalties": penalties,
        "coherence_factor": float(coherence),
        "continuous_formula": CONTINUOUS_FORMULA,
    }


def _ratio_state(
    anchors: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    ratio_all, ratio_eligible, observations = V3._ratio_candidates(anchors)
    consensus, inliers = V3._select_consensus(
        ratio_eligible, "log_ratio", spaces=True
    )
    all_anchor_handles = set(_handle_groups(anchors))
    ratio_surface_handles = {str(record["handle"]) for record in ratio_all}
    eligible_by_handle = {
        str(record["handle"]): dict(record) for record in ratio_eligible
    }
    support_handles = {str(record["handle"]) for record in inliers}
    penalties: dict[str, float] = {}
    scaled_distances: dict[str, float] = {}
    structural_handles: set[str] = set()
    selected_space = None if consensus is None else str(consensus["space"])
    selected_location = None if consensus is None else float(consensus["location"])

    for handle in sorted(ratio_surface_handles):
        record = eligible_by_handle.get(handle)
        if record is None or consensus is None:
            penalties[handle] = 1.0
            structural_handles.add(handle)
        elif str(record["ratio_space"]) != selected_space:
            penalties[handle] = 1.0
            structural_handles.add(handle)
        else:
            distance = abs(float(record["log_ratio"]) - float(selected_location))
            scaled_distances[handle] = distance / RANSAC_LOG_TOLERANCE
            penalties[handle] = _distance_penalty(distance)

    insufficient_support = len(support_handles) < MIN_HANDLES_NON_NONE
    severe_handles = {
        handle
        for handle, scaled in scaled_distances.items()
        if scaled >= SEVERE_ATTENUATION_ZERO_TAU
    }
    semantic_hard_handles = set(structural_handles) | severe_handles
    hard_suspicion = bool(semantic_hard_handles)
    candidate_handles = set(ratio_surface_handles)
    if hard_suspicion and ratio_surface_handles:
        # A residual outlier keeps retyped GRID or display-hidden handles in
        # the denominator.  This is the stateless CE-B2 anti-laundering rule.
        candidate_handles = set(all_anchor_handles)
        for handle in candidate_handles - ratio_surface_handles:
            penalties[handle] = 1.0
    if insufficient_support:
        for handle in candidate_handles:
            penalties[handle] = 1.0

    policy = _continuous_policy(
        anchors, candidate_handles, penalties, support_handles, consensus
    )
    severity = _severity_attenuation(
        max(scaled_distances.values(), default=0.0), bool(structural_handles)
    )
    if policy is not None and insufficient_support:
        policy["score"] = 0.0
        policy["consensus_fraction"] = 0.0
        policy["coherence_factor"] = 0.0
        policy["independent_fraction"] = 0.0

    if policy is not None:
        policy["severe_residual_attenuation"] = float(severity)
        policy["severe_attenuation_start_tau"] = SEVERE_ATTENUATION_START_TAU
        policy["severe_attenuation_zero_tau"] = SEVERE_ATTENUATION_ZERO_TAU
        policy["max_scaled_distance_tau"] = max(
            scaled_distances.values(), default=0.0
        )
        policy["structural_suspicion_handles"] = sorted(structural_handles)
        policy["score"] = float(policy["score"] * severity)
        if severity <= 1e-15:
            policy["score"] = 0.0
            policy["consensus_fraction"] = 0.0
            policy["coherence_factor"] = 0.0
            policy["independent_fraction"] = 0.0
            policy["spatial_fraction"] = 0.0
            policy["n_independent"] = 0
            policy["n_spatial_bins"] = 0

    hard_handles = sorted(semantic_hard_handles)
    attenuated_handles = sorted(
        handle for handle, penalty in penalties.items() if penalty > 1e-15
    )
    return {
        "all_records": ratio_all,
        "eligible": ratio_eligible,
        "observations": observations,
        "consensus": consensus,
        "inliers": inliers,
        "support_handles": support_handles,
        "candidate_handles": candidate_handles,
        "penalties": penalties,
        "policy": policy,
        "selected_space": selected_space,
        "insufficient_support": insufficient_support,
        "hard_suspicion": hard_suspicion,
        "severity_attenuation": float(severity),
        "structural_suspicion_handles": sorted(structural_handles),
        "scaled_distances_tau": scaled_distances,
        "hard_suspicious_handles": hard_handles,
        "attenuated_handles": attenuated_handles,
    }


def _reference_state(
    anchors: Sequence[Mapping[str, Any]], ratio: Mapping[str, Any]
) -> dict[str, Any]:
    reference_all, reference_eligible, observations = V3._reference_candidates(anchors)
    consensus, inliers = V3._select_consensus(
        reference_eligible, "log_span", spaces=False
    )
    all_handles = {str(record["handle"]) for record in reference_all}
    eligible_by_handle = {
        str(record["handle"]): dict(record) for record in reference_eligible
    }
    span_support_handles = {str(record["handle"]) for record in inliers}
    penalties: dict[str, float] = {}
    location = None if consensus is None else float(consensus["location"])
    for handle in sorted(all_handles):
        record = eligible_by_handle.get(handle)
        if record is None or consensus is None:
            penalties[handle] = 1.0
        else:
            penalties[handle] = _distance_penalty(
                float(record["log_span"]) - float(location)
            )
    insufficient_support = len(span_support_handles) < MIN_HANDLES_NON_NONE
    if insufficient_support:
        for handle in all_handles:
            penalties[handle] = 1.0
    base_policy = _continuous_policy(
        anchors, all_handles, penalties, span_support_handles, consensus
    )

    ratio_surface_exists = bool(ratio["all_records"])
    if ratio_surface_exists:
        ratio_penalties = {
            handle: float(ratio["penalties"].get(handle, 1.0))
            for handle in all_handles
        }
        ratio_trust_factor = (
            0.0
            if not all_handles
            else math.fsum(1.0 - value for value in ratio_penalties.values())
            / len(all_handles)
        )
        trusted_handles = {
            handle
            for handle in span_support_handles
            if ratio_penalties.get(handle, 1.0) < 1.0 - 1e-15
        }
    else:
        ratio_penalties = {handle: 0.0 for handle in all_handles}
        ratio_trust_factor = 1.0
        trusted_handles = set(span_support_handles)

    if base_policy is not None:
        base_policy["span_score_before_ratio_attenuation"] = float(
            base_policy["score"]
        )
        base_policy["ratio_suspicion_attenuation"] = float(ratio_trust_factor)
        base_policy["ratio_handle_penalties"] = ratio_penalties
        severity = float(ratio.get("severity_attenuation", 1.0))
        base_policy["ratio_severe_residual_attenuation"] = severity
        base_policy["score"] = float(
            base_policy["score"] * ratio_trust_factor * severity
        )
        base_policy["n_independent"] = len(trusted_handles)
        base_policy["confidence_inlier_handles"] = sorted(trusted_handles)
        if severity <= 1e-15:
            base_policy["score"] = 0.0
            base_policy["n_independent"] = 0
            base_policy["confidence_inlier_handles"] = []
    return {
        "all_records": reference_all,
        "eligible": reference_eligible,
        "observations": observations,
        "consensus": consensus,
        "inliers": inliers,
        "span_support_handles": span_support_handles,
        "trusted_handles": trusted_handles,
        "candidate_handles": all_handles,
        "penalties": penalties,
        "ratio_trust_factor": float(ratio_trust_factor),
        "policy": base_policy,
        "insufficient_support": insufficient_support,
    }


def _status_from_policy(
    estimate: float | None,
    consensus: Mapping[str, Any] | None,
    policy: Mapping[str, Any] | None,
) -> str:
    if estimate is None or consensus is None or policy is None:
        return "NONE"
    if int(policy["n_independent"]) < MIN_HANDLES_NON_NONE:
        return "NONE"
    high = (
        int(policy["n_independent"]) >= MIN_HANDLES_HIGH
        and float(policy["consensus_fraction"]) >= CONSENSUS_THRESHOLD
        and float(consensus["log_mad"]) <= RANSAC_LOG_TOLERANCE
        and float(policy["score"]) >= HIGH_CONFIDENCE_THRESHOLD
    )
    return "HIGH" if high else "LOW"


def _consensus_public(
    consensus: Mapping[str, Any] | None,
    policy: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if consensus is None or policy is None:
        return None
    output = dict(consensus)
    output["total_weight"] = float(policy["candidate_weight"])
    output["inlier_weight"] = float(policy["inlier_weight"])
    output["consensus_weight"] = float(policy["consensus_fraction"])
    return output


def fit_anchor_model(raw_anchors: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Fit anchor-only models under the L1e witness-principle repairs."""
    anchors, audit = prepare_anchors(raw_anchors)
    ratio = _ratio_state(anchors)
    ratio_consensus_raw = ratio["consensus"]
    ratio_policy = ratio["policy"]
    ratio_support = set(ratio["support_handles"])
    if ratio_consensus_raw is None or len(ratio_support) < MIN_HANDLES_NON_NONE:
        scale_estimate = None
        ratio_consensus = None
        unit_status = "NONE"
    else:
        scale_estimate = math.exp(float(ratio_consensus_raw["location"]))
        ratio_consensus = _consensus_public(ratio_consensus_raw, ratio_policy)
        unit_status = _status_from_policy(
            scale_estimate, ratio_consensus_raw, ratio_policy
        )

    ratio_space = ratio["selected_space"]
    if scale_estimate is not None and ratio_space == "z_mm":
        physical_unit = "MM"
        mm_per_raw = scale_estimate
    else:
        physical_unit = "UNKNOWN"
        mm_per_raw = None

    reference = _reference_state(anchors, ratio)
    reference_consensus_raw = reference["consensus"]
    reference_policy = reference["policy"]
    reference_support = set(reference["span_support_handles"])
    if (
        reference_consensus_raw is None
        or len(reference_support) < MIN_HANDLES_NON_NONE
    ):
        reference_span = None
        reference_consensus = None
        reference_status = "NONE"
    else:
        reference_span = math.exp(float(reference_consensus_raw["location"]))
        reference_consensus = _consensus_public(
            reference_consensus_raw, reference_policy
        )
        reference_status = _status_from_policy(
            reference_span, reference_consensus_raw, reference_policy
        )

    ratio_inlier_handles = sorted(ratio_support)
    ratio_outlier_handles = sorted(ratio["hard_suspicious_handles"])
    reference_inlier_handles = sorted(reference_support)
    reference_outlier_handles = sorted(
        set(reference["candidate_handles"]) - reference_support
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
        if ratio_consensus_raw is None
        else float(ratio_consensus_raw["log_mad"]),
        "n_independent": 0
        if ratio_policy is None
        else int(ratio_policy["n_independent"]),
        "n_candidate_handles": 0
        if ratio_policy is None
        else int(ratio_policy["n_candidate_handles"]),
        "n_spatial_bins": 0
        if ratio_policy is None
        else int(ratio_policy["n_spatial_bins"]),
        "n_candidate_spatial_bins": 0
        if ratio_policy is None
        else int(ratio_policy["n_candidate_spatial_bins"]),
        "confidence_score": 0.0
        if ratio_policy is None
        else float(ratio_policy["score"]),
        "source_diversity": source_diversity,
        "reference_span": reference_span,
        "reference_consensus_weight": None
        if reference_consensus is None
        else float(reference_consensus["consensus_weight"]),
        "reference_log_mad": None
        if reference_consensus_raw is None
        else float(reference_consensus_raw["log_mad"]),
        "reference_n_independent": 0
        if reference_policy is None
        else int(reference_policy["n_independent"]),
        "reference_n_candidate_handles": 0
        if reference_policy is None
        else int(reference_policy["n_candidate_handles"]),
        "reference_n_spatial_bins": 0
        if reference_policy is None
        else int(reference_policy["n_spatial_bins"]),
        "reference_n_candidate_spatial_bins": 0
        if reference_policy is None
        else int(reference_policy["n_candidate_spatial_bins"]),
        "reference_confidence_score": 0.0
        if reference_policy is None
        else float(reference_policy["score"]),
        "provenance": {
            **audit,
            "revision": REVISION,
            "ratio_mode_space": ratio_space,
            "ratio_inlier_handles": ratio_inlier_handles,
            "ratio_outlier_handles": ratio_outlier_handles,
            "ratio_attenuated_handles": list(ratio["attenuated_handles"]),
            "ratio_observations": ratio["observations"],
            "reference_inlier_handles": reference_inlier_handles,
            "reference_confidence_inlier_handles": sorted(
                reference["trusted_handles"]
            ),
            "reference_outlier_handles": reference_outlier_handles,
            "reference_rejections": reference["observations"],
            "reference_label_policy": "label_free_span_space",
            "independence_key": "unique_source_handle",
            "minimum_handles_non_none": MIN_HANDLES_NON_NONE,
            "minimum_handles_high": MIN_HANDLES_HIGH,
            "suspicious_evidence_role": "denominator_only_never_estimate",
            "continuous_attenuation": {
                "formula": CONTINUOUS_FORMULA,
                "boundary_behavior": BOUNDARY_BEHAVIOR,
            },
            "denominator_policy": {
                "ratio": ratio_policy,
                "reference": reference_policy,
                "candidate_records_removed_after_classification": 0,
                "subset_basis": "source_handle_sets",
            },
        },
    }


def anchor_artifact_from_scene(scene: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "artifact_schema": "ariadne.e2.feyerabend_c1.anchor_artifact.v4",
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
        "n_candidate_handles": int(model["n_candidate_handles"]),
        "n_spatial_bins": int(model["n_spatial_bins"]),
        "reference_n_independent": int(model["reference_n_independent"]),
        "reference_n_candidate_handles": int(
            model["reference_n_candidate_handles"]
        ),
        "reference_n_spatial_bins": int(model["reference_n_spatial_bins"]),
        "ratio_inlier_handles": list(model["provenance"]["ratio_inlier_handles"]),
        "ratio_outlier_handles": list(
            model["provenance"]["ratio_outlier_handles"]
        ),
        "ratio_attenuated_handles": list(
            model["provenance"]["ratio_attenuated_handles"]
        ),
        "reference_inlier_handles": list(
            model["provenance"]["reference_inlier_handles"]
        ),
        "reference_outlier_handles": list(
            model["provenance"]["reference_outlier_handles"]
        ),
    }


def _increases(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, bool]:
    return V3._increases(before, after)


def estimator_input_surface(
    raw_anchors: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Exact ordered projection of every field read by the estimator."""
    surface: list[dict[str, Any]] = []
    for anchor in raw_anchors:
        record: dict[str, Any] = {}
        for field in ESTIMATOR_INPUT_FIELDS:
            if field in anchor:
                record[field] = copy.deepcopy(anchor[field])
        surface.append(record)
    return surface


def suspicion_analysis(
    raw_anchors: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    anchors, _audit = prepare_anchors(raw_anchors)
    ratio = _ratio_state(anchors)
    reference = _reference_state(anchors, ratio)
    ratio_spaces = sorted(
        {
            str(record["ratio_space"])
            for record in ratio["eligible"]
            if record.get("ratio_space") not in (None, "missing")
        }
    )
    ratio_conflicts = sorted(
        {
            str(row["handle"])
            for row in ratio["observations"]
            if row.get("reason") == "source_handle_ratio_conflict"
        }
    )
    missing_ratio = sorted(
        {
            str(row["handle"])
            for row in ratio["observations"]
            if row.get("reason") == "ratio_missing_denominator_only"
        }
    )
    span_conflicts = sorted(
        {
            str(row["handle"])
            for row in reference["observations"]
            if "source_handle_span_conflict" in row.get("reasons", [])
        }
    )
    residual = {
        "ratio_hard_suspicious_handles": list(ratio["hard_suspicious_handles"]),
        "ratio_conflict_handles": ratio_conflicts,
        "ratio_missing_handles": missing_ratio,
        "mixed_ratio_spaces": ratio_spaces if len(ratio_spaces) > 1 else [],
        "span_conflict_handles": span_conflicts,
    }
    return {
        **residual,
        "residual_suspicion_count": sum(len(value) for value in residual.values()),
        "observation_digest": canonical_sha256(residual),
    }


def run_selftests(stream: io.TextIOBase) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []

    def observe(identifier: str, value: bool, detail: Mapping[str, Any]) -> None:
        row = {"id": identifier, "observed": bool(value), "detail": dict(detail)}
        observations.append(row)
        print(json.dumps(row, ensure_ascii=False, sort_keys=True), file=stream)
        if not value:
            raise AssertionError(identifier)

    clean = fit_anchor_model(exact_fixture())
    observe(
        "clean_exact_model",
        clean["unit_status"] == "HIGH"
        and math.isclose(float(clean["display_per_raw"]), 2.5, rel_tol=1e-12),
        {"unit_status": clean["unit_status"], "estimate": clean["display_per_raw"]},
    )
    singleton = fit_anchor_model(exact_fixture()[:1])
    observe(
        "singleton_is_none",
        singleton["unit_status"] == "NONE"
        and singleton["display_per_raw"] is None,
        {
            "unit_status": singleton["unit_status"],
            "estimate": singleton["display_per_raw"],
        },
    )
    base = exact_fixture()[:3]
    duplicate = copy.deepcopy(base)
    repeat = copy.deepcopy(base[0])
    repeat["p0"] = [300.0, 300.0]
    repeat["p1"] = [400.0, 300.0]
    duplicate.append(repeat)
    before = _snapshot(fit_anchor_model(base))
    after = _snapshot(fit_anchor_model(duplicate))
    observe(
        "same_handle_repeat_is_handle_set_neutral",
        before == after,
        {"before_digest": canonical_sha256(before), "after_digest": canonical_sha256(after)},
    )
    tau = RANSAC_LOG_TOLERANCE
    edge_lo = [
        _make_anchor("E0", 100.0, 250.0, *POSITIONS[0]),
        _make_anchor("E1", 100.0, 250.0, *POSITIONS[1]),
        _make_anchor(
            "E2", 100.0, 250.0 * math.exp((1.0 - 1e-9) * tau), *POSITIONS[2]
        ),
    ]
    edge_hi = copy.deepcopy(edge_lo)
    edge_hi[2]["display_value"] = 250.0 * math.exp((1.0 + 1e-9) * tau)
    low_score = fit_anchor_model(edge_lo)["confidence_score"]
    high_score = fit_anchor_model(edge_hi)["confidence_score"]
    observe(
        "tau_boundary_continuous",
        abs(float(low_score) - float(high_score)) < 1e-7,
        {"below": low_score, "above": high_score, "absolute_delta": abs(low_score-high_score)},
    )
    return {
        "observed_count": sum(int(row["observed"]) for row in observations),
        "total": len(observations),
        "observations": observations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    arguments = parser.parse_args(argv)
    if not arguments.selftest:
        parser.error("only --selftest is supported; use loop_l1e.py for the full run")
    stream = io.StringIO()
    result = run_selftests(stream)
    print(stream.getvalue(), end="")
    return 0 if result["observed_count"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
