#!/usr/bin/env python3
"""Pure GNN intervention helpers with a retired public experiment runner.

Public ``run`` and CLI calls stop before importing a checkpoint or reading an
input until the registered sealed E2 executor exists.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.e2.qualification.sealed_executor import refusal_receipt  # noqa: E402


PASS = "PASS"
PARTIAL_PASS = "PARTIAL_PASS"
BLOCKED = "BLOCKED"
EXACT_TOLERANCE = 1e-6
GRAPH_TOLERANCE = 1e-7
STABILITY_MEAN_ABS_LIMIT = 0.02
STABILITY_FLIP_RATE_LIMIT = 0.05
THRESHOLD = 0.5


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    return {"path": str(resolved), "bytes": resolved.stat().st_size, "sha256": _sha256(resolved)}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return _json_ready(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(_json_ready(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def _import_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import frozen module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def compare_runtime_replay(
    baseline: Mapping[str, Any], replay: Mapping[str, Any], tolerance: float = 1e-12
) -> dict[str, Any]:
    """Compare sealed smoke results, excluding only runtime-volatile fields."""

    ignored_keys = {"created_at", "wall_seconds"}
    differences: list[dict[str, Any]] = []
    numeric_fields = 0
    maximum_numeric_delta = 0.0

    def walk(left: Any, right: Any, pointer: str = "") -> None:
        nonlocal numeric_fields, maximum_numeric_delta
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            keys = sorted(set(left) | set(right))
            for key in keys:
                if key in ignored_keys:
                    continue
                child = f"{pointer}/{key}"
                if key not in left or key not in right:
                    differences.append({"path": child, "kind": "missing"})
                else:
                    walk(left[key], right[key], child)
            return
        if isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                differences.append(
                    {"path": pointer, "kind": "length", "baseline": len(left), "replay": len(right)}
                )
                return
            for index, (l_item, r_item) in enumerate(zip(left, right)):
                walk(l_item, r_item, f"{pointer}/{index}")
            return
        if isinstance(left, (int, float)) and not isinstance(left, bool) and isinstance(
            right, (int, float)
        ) and not isinstance(right, bool):
            numeric_fields += 1
            delta = abs(float(left) - float(right))
            maximum_numeric_delta = max(maximum_numeric_delta, delta)
            if delta > tolerance:
                differences.append(
                    {
                        "path": pointer,
                        "kind": "numeric",
                        "baseline": left,
                        "replay": right,
                        "absolute_delta": delta,
                    }
                )
            return
        if left != right:
            differences.append(
                {"path": pointer, "kind": "value", "baseline": left, "replay": right}
            )

    walk(baseline, replay)
    return {
        "schema": "e2.c1_runtime_replay_comparison.v1",
        "status": PASS if not differences else BLOCKED,
        "ignored_keys": sorted(ignored_keys),
        "absolute_tolerance": tolerance,
        "numeric_fields_compared": numeric_fields,
        "maximum_numeric_delta": maximum_numeric_delta,
        "difference_count": len(differences),
        "first_differences": differences[:50],
    }


def validate_seg_ir(seg_ir: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if seg_ir.get("ir") != "seg.v1":
        errors.append(f"ir must be seg.v1, observed={seg_ir.get('ir')!r}")
    if str(seg_ir.get("units") or "").lower() != "mm":
        errors.append(f"units must be mm, observed={seg_ir.get('units')!r}")
    try:
        scale = float(seg_ir.get("scale_mm_per_unit"))
    except (TypeError, ValueError):
        scale = math.nan
    if not math.isclose(scale, 1.0, rel_tol=0.0, abs_tol=1e-12):
        errors.append(f"scale_mm_per_unit must be 1.0, observed={seg_ir.get('scale_mm_per_unit')!r}")

    segments = seg_ir.get("segments") or []
    if not isinstance(segments, list) or not segments:
        errors.append("segments must be a non-empty list")
        segments = []
    handles: list[str] = []
    invalid_coordinate_segments = 0
    for index, segment in enumerate(segments):
        if not isinstance(segment, Mapping):
            errors.append(f"segment[{index}] is not an object")
            continue
        handle = str(segment.get("handle") or "")
        handles.append(handle)
        if not handle:
            errors.append(f"segment[{index}] has an empty handle")
        points = segment.get("pts") or []
        valid = len(points) >= 2
        if valid:
            try:
                valid = all(
                    len(point) >= 2
                    and math.isfinite(float(point[0]))
                    and math.isfinite(float(point[1]))
                    for point in points
                )
            except (TypeError, ValueError):
                valid = False
        if not valid:
            invalid_coordinate_segments += 1
    duplicate_handles = sorted({handle for handle in handles if handles.count(handle) > 1})
    if duplicate_handles:
        errors.append(f"duplicate handles: {duplicate_handles[:10]}")
    if invalid_coordinate_segments:
        errors.append(f"segments with invalid coordinates: {invalid_coordinate_segments}")
    return {
        "status": PASS if not errors else BLOCKED,
        "segment_count": len(segments),
        "unique_handle_count": len(set(handles)),
        "invalid_coordinate_segments": invalid_coordinate_segments,
        "errors": errors,
    }


def _feature_map(graph: Mapping[str, Any]) -> dict[str, np.ndarray]:
    records = graph["prepared"]["records"]
    features = graph["features"]
    return {str(record["handle"]): np.asarray(features[index], dtype=np.float64) for index, record in enumerate(records)}


def _edge_map(graph: Mapping[str, Any], edge_types: tuple[str, ...]) -> dict[tuple[str, str, str], list[tuple[float, ...]]]:
    records = graph["prepared"]["records"]
    handles = [str(record["handle"]) for record in records]
    grouped: dict[tuple[str, str, str], list[tuple[float, ...]]] = defaultdict(list)
    for source, target, relation, attributes in zip(
        graph["edge_src"], graph["edge_dst"], graph["edge_type"], graph["edge_attr"]
    ):
        key = (handles[int(source)], handles[int(target)], edge_types[int(relation)])
        grouped[key].append(tuple(float(value) for value in attributes))
    for values in grouped.values():
        values.sort()
    return dict(grouped)


def compare_graphs(
    left: Mapping[str, Any], right: Mapping[str, Any], edge_types: tuple[str, ...], tolerance: float
) -> dict[str, Any]:
    left_features = _feature_map(left)
    right_features = _feature_map(right)
    feature_handle_difference = sorted(set(left_features) ^ set(right_features))
    max_feature_delta = 0.0
    for handle in set(left_features) & set(right_features):
        max_feature_delta = max(
            max_feature_delta,
            float(np.max(np.abs(left_features[handle] - right_features[handle]))),
        )

    left_edges = _edge_map(left, edge_types)
    right_edges = _edge_map(right, edge_types)
    edge_key_difference = sorted(set(left_edges) ^ set(right_edges))
    edge_multiplicity_difference = 0
    max_edge_attribute_delta = 0.0
    for key in set(left_edges) & set(right_edges):
        l_values, r_values = left_edges[key], right_edges[key]
        if len(l_values) != len(r_values):
            edge_multiplicity_difference += 1
            continue
        for l_attrs, r_attrs in zip(l_values, r_values):
            max_edge_attribute_delta = max(
                max_edge_attribute_delta,
                max(abs(a - b) for a, b in zip(l_attrs, r_attrs)),
            )
    same_hash = left["stats"]["graph_hash"] == right["stats"]["graph_hash"]
    model_input_ok = (
        not feature_handle_difference
        and max_feature_delta <= tolerance
        and not edge_key_difference
        and edge_multiplicity_difference == 0
        and same_hash
    )
    sidecar_ok = max_edge_attribute_delta <= tolerance
    return {
        # The sealed GNN consumes x/edge_src/edge_dst/edge_type only.  It does
        # not copy edge_attr into GraphSample.  Keep sidecar drift explicit,
        # but do not misclassify a field the model cannot observe as model
        # input drift (see run-local INPUT_CONTRACT_AMENDMENT.md).
        "status": PASS if model_input_ok else BLOCKED,
        "model_consumed_fields": ["features", "edge_src", "edge_dst", "edge_type"],
        "edge_attribute_sidecar_status": PASS if sidecar_ok else "SIDECAR_ORDER_SENSITIVITY",
        "same_graph_hash": same_hash,
        "left_graph_hash": left["stats"]["graph_hash"],
        "right_graph_hash": right["stats"]["graph_hash"],
        "feature_handle_symmetric_difference_count": len(feature_handle_difference),
        "first_feature_handle_differences": feature_handle_difference[:20],
        "max_handle_aligned_feature_delta": max_feature_delta,
        "edge_key_symmetric_difference_count": len(edge_key_difference),
        "first_edge_key_differences": [list(key) for key in edge_key_difference[:20]],
        "edge_multiplicity_difference_count": edge_multiplicity_difference,
        "max_edge_attribute_delta": max_edge_attribute_delta,
        "tolerance": tolerance,
    }


def diagnose_model_input_change(
    baseline_graph: Mapping[str, Any],
    transformed_graph: Mapping[str, Any],
    builder: Any,
    original_of: Mapping[str, str | None],
) -> dict[str, Any]:
    """Describe changes in the tensors the frozen GNN actually consumes."""

    baseline_handles = [str(row["handle"]) for row in baseline_graph["prepared"]["records"]]
    transformed_handles = [str(row["handle"]) for row in transformed_graph["prepared"]["records"]]
    identity_mapping = (
        len(baseline_handles) == len(transformed_handles)
        and all(original_of.get(handle, handle) == handle for handle in transformed_handles)
    )
    base_stats = baseline_graph["stats"]
    transformed_stats = transformed_graph["stats"]
    common = {
        "baseline_nodes": int(base_stats["node_count"]),
        "transformed_nodes": int(transformed_stats["node_count"]),
        "baseline_directed_edges": int(base_stats["directed_edge_count"]),
        "transformed_directed_edges": int(transformed_stats["directed_edge_count"]),
        "directed_edge_count_delta": int(transformed_stats["directed_edge_count"])
        - int(base_stats["directed_edge_count"]),
        "relation_directed_edge_count_delta": {
            name: int(transformed_stats["relation_directed_edge_counts"][name])
            - int(base_stats["relation_directed_edge_counts"][name])
            for name in builder.EDGE_TYPES
        },
        "same_raw_geometry_graph_hash": base_stats["graph_hash"] == transformed_stats["graph_hash"],
    }
    if not identity_mapping:
        return {
            **common,
            "comparison": "NOT_HANDLE_IDENTICAL_AFTER_STRUCTURAL_TRANSFORM",
            "model_input_identical": False,
        }

    baseline_features = _feature_map(baseline_graph)
    transformed_features = _feature_map(transformed_graph)
    handles = sorted(set(baseline_features) & set(transformed_features))
    feature_delta_by_name: dict[str, dict[str, Any]] = {}
    maximum_feature_delta = 0.0
    for index, name in enumerate(builder.FEATURE_NAMES):
        deltas = np.asarray(
            [abs(float(baseline_features[h][index]) - float(transformed_features[h][index])) for h in handles],
            dtype=np.float64,
        )
        maximum = float(deltas.max()) if deltas.size else 0.0
        maximum_feature_delta = max(maximum_feature_delta, maximum)
        feature_delta_by_name[name] = {
            "max_abs_delta": maximum,
            "changed_handle_count_gt_1e_7": int(np.sum(deltas > GRAPH_TOLERANCE)),
        }

    baseline_edges = set(_edge_map(baseline_graph, tuple(builder.EDGE_TYPES)))
    transformed_edges = set(_edge_map(transformed_graph, tuple(builder.EDGE_TYPES)))
    removed = baseline_edges - transformed_edges
    added = transformed_edges - baseline_edges
    edge_changes_by_relation = {
        name: {
            "removed": sum(key[2] == name for key in removed),
            "added": sum(key[2] == name for key in added),
        }
        for name in builder.EDGE_TYPES
    }
    identical = (
        set(baseline_features) == set(transformed_features)
        and maximum_feature_delta <= GRAPH_TOLERANCE
        and not removed
        and not added
    )
    return {
        **common,
        "comparison": "HANDLE_ALIGNED_MODEL_INPUT",
        "model_input_identical": identical,
        "feature_handle_symmetric_difference_count": len(set(baseline_features) ^ set(transformed_features)),
        "max_feature_delta": maximum_feature_delta,
        "feature_delta_by_name": feature_delta_by_name,
        "typed_edge_removed": len(removed),
        "typed_edge_added": len(added),
        "typed_edge_symmetric_difference": len(removed) + len(added),
        "typed_edge_changes_by_relation": edge_changes_by_relation,
    }


def qualify_graph_contract(seg_ir: Mapping[str, Any], components: Mapping[str, Any]) -> dict[str, Any]:
    shape = validate_seg_ir(seg_ir)
    if shape["status"] != PASS:
        return {"schema": "e2.company_gnn_graph_contract.v1", "status": BLOCKED, "seg_ir": shape}

    builder = components["builder"]
    config = components["graph_config"]
    first = builder.build_graph(dict(seg_ir), config, collect_edges=True)
    repeat = builder.build_graph(dict(seg_ir), config, collect_edges=True)
    reversed_ir = copy.deepcopy(dict(seg_ir))
    reversed_ir["segments"] = list(reversed(reversed_ir["segments"]))
    permuted = builder.build_graph(reversed_ir, config, collect_edges=True)

    stats = first["stats"]
    features = np.asarray(first["features"])
    node_count = int(stats["node_count"])
    edge_count = int(stats["directed_edge_count"])
    fixed_checks = {
        "builder_status_ok": stats.get("status") == "ok",
        "input_segment_count_matches": int(stats.get("input_segment_count", -1)) == shape["segment_count"],
        "node_count_matches": node_count == shape["segment_count"],
        "no_dropped_segments": not bool(stats.get("dropped_input_segments")),
        "no_unresolved_references": int(stats.get("unresolved_reference_count", -1)) == 0,
        "feature_shape_n_by_17": features.shape == (node_count, 17),
        "features_all_finite": bool(np.isfinite(features).all()),
        "six_edge_types": len(builder.EDGE_TYPES) == 6,
        "edge_arrays_match_count": all(
            len(first[name]) == edge_count for name in ("edge_src", "edge_dst", "edge_type", "edge_attr")
        ),
        "edge_indices_in_range": bool(
            edge_count == 0
            or (
                int(np.min(first["edge_src"])) >= 0
                and int(np.min(first["edge_dst"])) >= 0
                and int(np.max(first["edge_src"])) < node_count
                and int(np.max(first["edge_dst"])) < node_count
            )
        ),
        "edge_types_in_range": bool(
            edge_count == 0
            or (
                int(np.min(first["edge_type"])) >= 0
                and int(np.max(first["edge_type"])) < len(builder.EDGE_TYPES)
            )
        ),
        "robust_scale_1000": math.isclose(
            float(stats.get("robust_scale_units", math.nan)), 1000.0, rel_tol=0.0, abs_tol=1e-12
        ),
        "explicit_scale_source": stats.get("scale_source") == "scale_mm_per_unit",
        "config_hash_matches": stats.get("config_hash") == components["graph_config"].digest(),
    }
    repeat_comparison = compare_graphs(first, repeat, tuple(builder.EDGE_TYPES), GRAPH_TOLERANCE)
    permutation_comparison = compare_graphs(first, permuted, tuple(builder.EDGE_TYPES), GRAPH_TOLERANCE)
    ok = all(fixed_checks.values()) and repeat_comparison["status"] == PASS and permutation_comparison["status"] == PASS
    return {
        "schema": "e2.company_gnn_graph_contract.v1",
        "status": PASS if ok else BLOCKED,
        "seg_ir": shape,
        "feature_names": list(builder.FEATURE_NAMES),
        "edge_types": list(builder.EDGE_TYPES),
        "fixed_checks": fixed_checks,
        "graph_stats": {
            key: stats[key]
            for key in (
                "status",
                "node_count",
                "directed_edge_count",
                "relation_directed_edge_counts",
                "input_segment_count",
                "dropped_input_segments",
                "robust_scale_units",
                "scale_source",
                "unresolved_reference_count",
                "graph_hash",
                "config_hash",
            )
        },
        "repeat_comparison": repeat_comparison,
        "reversed_input_comparison": permutation_comparison,
        "sidecar_warning": (
            None
            if repeat_comparison["edge_attribute_sidecar_status"] == PASS
            and permutation_comparison["edge_attribute_sidecar_status"] == PASS
            else "edge_attr changes under input permutation but is not consumed by this frozen GNN"
        ),
    }


def _map_identity(seg_ir: Mapping[str, Any]) -> dict[str, str]:
    return {str(segment["handle"]): str(segment["handle"]) for segment in seg_ir.get("segments", [])}


def transform_translate(seg_ir: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    transformed = copy.deepcopy(dict(seg_ir))
    for segment in transformed.get("segments", []):
        segment["pts"] = [
            [float(point[0]) + 1_000_000.0, float(point[1]) - 2_000_000.0]
            for point in segment.get("pts", [])
        ]
    return transformed, _map_identity(transformed)


def transform_consistent_scale(
    seg_ir: Mapping[str, Any], factor: float = 1000.0
) -> tuple[dict[str, Any], dict[str, str]]:
    transformed = copy.deepcopy(dict(seg_ir))
    for segment in transformed.get("segments", []):
        segment["pts"] = [
            [float(point[0]) * factor, float(point[1]) * factor]
            for point in segment.get("pts", [])
        ]
        if segment.get("sagitta") is not None:
            segment["sagitta"] = float(segment["sagitta"]) * factor
    transformed["scale_mm_per_unit"] = float(transformed["scale_mm_per_unit"]) / factor
    return transformed, _map_identity(transformed)


def transform_strip_layers(seg_ir: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    transformed = copy.deepcopy(dict(seg_ir))
    for segment in transformed.get("segments", []):
        segment["layer"] = ""
    return transformed, _map_identity(transformed)


def _prediction_summary(handles: list[str], probabilities: np.ndarray) -> dict[str, Any]:
    values = np.asarray(probabilities, dtype=np.float64)
    candidate_count = int(np.sum(values >= THRESHOLD))
    return {
        "node_count": len(handles),
        "threshold": THRESHOLD,
        "candidate_count_at_0_5": candidate_count,
        "candidate_rate_at_0_5": candidate_count / len(handles) if handles else None,
        "probability_min": float(values.min()) if values.size else None,
        "probability_mean": float(values.mean()) if values.size else None,
        "probability_median": float(np.median(values)) if values.size else None,
        "probability_max": float(values.max()) if values.size else None,
    }


def paired_unlabeled(
    baseline: Mapping[str, Any], transformed: Mapping[str, Any], original_of: Mapping[str, str | None]
) -> dict[str, Any]:
    baseline_probability = {
        str(handle): float(probability)
        for handle, probability in zip(baseline["handles"], baseline["gnn"])
    }
    grouped: dict[str, list[float]] = defaultdict(list)
    without_origin = 0
    for handle, probability in zip(transformed["handles"], transformed["gnn"]):
        original = original_of.get(str(handle), str(handle))
        if original is None:
            without_origin += 1
        else:
            grouped[str(original)].append(float(probability))

    rows: list[dict[str, Any]] = []
    for handle in sorted(baseline_probability):
        if handle not in grouped:
            continue
        base_value = baseline_probability[handle]
        transformed_value = float(np.mean(grouped[handle]))
        delta = abs(base_value - transformed_value)
        flipped = (base_value >= THRESHOLD) != (transformed_value >= THRESHOLD)
        rows.append(
            {
                "handle": handle,
                "baseline_probability": base_value,
                "transformed_probability_mean": transformed_value,
                "transformed_child_count": len(grouped[handle]),
                "absolute_delta": delta,
                "flipped_at_0_5": flipped,
            }
        )
    deltas = np.asarray([row["absolute_delta"] for row in rows], dtype=np.float64)
    flips = sum(bool(row["flipped_at_0_5"]) for row in rows)
    missing = sorted(set(baseline_probability) - set(grouped))
    extra_origins = sorted(set(grouped) - set(baseline_probability))
    return {
        "baseline_handles": len(baseline_probability),
        "matched_original_handles": len(rows),
        "missing_baseline_handle_count": len(missing),
        "first_missing_baseline_handles": missing[:20],
        "extra_original_handle_count": len(extra_origins),
        "first_extra_original_handles": extra_origins[:20],
        "transformed_nodes_without_origin": without_origin,
        "mean_abs_delta": float(deltas.mean()) if deltas.size else None,
        "p95_abs_delta": float(np.quantile(deltas, 0.95)) if deltas.size else None,
        "max_abs_delta": float(deltas.max()) if deltas.size else None,
        "changed_handle_count_gt_1e_6": int(np.sum(deltas > EXACT_TOLERANCE)) if deltas.size else 0,
        "flip_count_at_0_5": flips,
        "flip_rate_at_0_5": flips / len(rows) if rows else None,
        "top_25_changes": sorted(rows, key=lambda row: (-row["absolute_delta"], row["handle"]))[:25],
        "per_handle": rows,
    }


def _intervention_status(name: str, measurement: Mapping[str, Any]) -> str:
    complete = (
        measurement["missing_baseline_handle_count"] == 0
        and measurement["extra_original_handle_count"] == 0
        and measurement["transformed_nodes_without_origin"] == 0
    )
    if not complete:
        return BLOCKED
    if name in {"translate_large_offset", "scale_coordinates_x1000_consistent", "strip_layer_names"}:
        return (
            "EXACT_INVARIANCE_PASS"
            if measurement["max_abs_delta"] <= EXACT_TOLERANCE
            and measurement["flip_rate_at_0_5"] == 0.0
            else "EXACT_INVARIANCE_FAIL"
        )
    if name in {"rotate_37_degrees", "reflect_x_axis", "split_every_segment_at_midpoint"}:
        return (
            "STABILITY_PASS"
            if measurement["mean_abs_delta"] <= STABILITY_MEAN_ABS_LIMIT
            and measurement["flip_rate_at_0_5"] <= STABILITY_FLIP_RATE_LIMIT
            else "STABILITY_FAIL"
        )
    return "MEASURED_NEGATIVE_CONTROL"


def intervention_registry(c1: Any) -> dict[str, Callable[[Mapping[str, Any]], tuple[dict[str, Any], dict[str, str | None]]]]:
    return {
        "translate_large_offset": transform_translate,
        "scale_coordinates_x1000_consistent": transform_consistent_scale,
        "strip_layer_names": transform_strip_layers,
        "rotate_37_degrees": lambda ir: c1.t_rotate(dict(ir), 37.0, reflect=False),
        "reflect_x_axis": lambda ir: c1.t_rotate(dict(ir), 0.0, reflect=True),
        "split_every_segment_at_midpoint": lambda ir: c1.t_split(dict(ir)),
        "scale_coordinates_x1000_naive": lambda ir: c1.t_scale(dict(ir), 1000.0),
    }


def measure_interventions(
    seg_ir: Mapping[str, Any], c1: Any, components: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    builder = components["builder"]
    baseline_graph = builder.build_graph(dict(seg_ir), components["graph_config"], collect_edges=True)
    baseline = c1.infer(dict(seg_ir), components, want_chains=False)
    baseline_output = {
        "schema": "e2.company_gnn_baseline_predictions.v1",
        "status": "EXPLORATORY_UNLABELED",
        "summary": _prediction_summary(baseline["handles"], baseline["gnn"]),
        "predictions": [
            {"handle": str(handle), "gnn_probability": float(probability)}
            for handle, probability in sorted(
                zip(baseline["handles"], baseline["gnn"]), key=lambda item: str(item[0])
            )
        ],
        "accuracy_metrics": None,
        "warning": "Frozen GNN probabilities are candidates, not wall truth.",
    }
    intervention_rows = []
    for name, transform in intervention_registry(c1).items():
        transformed_ir, original_of = transform(seg_ir)
        transformed_graph = builder.build_graph(
            transformed_ir, components["graph_config"], collect_edges=True
        )
        input_diagnosis = diagnose_model_input_change(
            baseline_graph, transformed_graph, builder, original_of
        )
        transformed = c1.infer(transformed_ir, components, want_chains=False)
        measurement = paired_unlabeled(baseline, transformed, original_of)
        status = _intervention_status(name, measurement)
        intervention_rows.append(
            {
                "intervention": name,
                "status": status,
                "transformed_node_count": len(transformed["handles"]),
                "limits": (
                    {"max_abs_delta": EXACT_TOLERANCE, "flip_rate": 0.0}
                    if name
                    in {"translate_large_offset", "scale_coordinates_x1000_consistent", "strip_layer_names"}
                    else {
                        "mean_abs_delta": STABILITY_MEAN_ABS_LIMIT,
                        "flip_rate": STABILITY_FLIP_RATE_LIMIT,
                    }
                    if name in {"rotate_37_degrees", "reflect_x_axis", "split_every_segment_at_midpoint"}
                    else None
                ),
                "model_input_diagnosis": input_diagnosis,
                "measurement": measurement,
            }
        )
    return baseline_output, {
        "schema": "e2.company_gnn_interventions.v1",
        "status": "MEASURED",
        "threshold": THRESHOLD,
        "interventions": intervention_rows,
        "accuracy_metrics": None,
        "claim_boundary": "paired prediction stability on unlabeled company geometry, not wall accuracy",
    }


def _render_report(receipt: Mapping[str, Any]) -> str:
    lines = [
        "# E2 A30 회사 도면 동결 GNN 입력계약·개입 결과",
        "",
        f"상태: **{receipt['status']}**",
        "",
        "## 결론",
        "",
    ]
    if receipt["status"] == BLOCKED:
        lines.append("동결 GNN의 입력계약 또는 원본 불변성 게이트가 실패해 회사 도면 추론을 닫았다.")
    else:
        lines.append(
            "동결 GNN은 두 회사 도면의 XCLIP 제외 주도면 SEG-IR에서 기술적으로 실행 가능했다. "
            "다만 사람 벽 정답이 없으므로 아래 수치는 정확도가 아니라 표현 변화에 대한 자기일관성이다."
        )
    replay = receipt["runtime_replay"]
    lines.extend(
        [
            "",
            "## 동결 경로 재현",
            "",
            f"체크포인트·그래프 생성기·규칙 자산 해시는 {sum(1 for row in receipt['integrity'].values() if row.get('match'))}/{len(receipt['integrity'])}개 일치했다. "
            f"기존 C1 smoke와 현재 재실행의 비교 수치 {replay['numeric_fields_compared']:,}개 중 차이는 {replay['difference_count']}개였고 최대 수치 편차는 `{replay['maximum_numeric_delta']}`였다.",
            "",
            "## 회사 도면 결과",
            "",
            "| 환경 | 그래프 계약 | 노드 | 관계 edge | GNN 후보(≥0.5) | 후보 비율 |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for environment in receipt["environments"]:
        if environment.get("contract", {}).get("status") != PASS:
            lines.append(f"| {environment['environment']} | BLOCKED | - | - | - | - |")
            continue
        graph = environment["contract"]["graph_stats"]
        baseline = environment["baseline_summary"]
        lines.append(
            f"| {environment['environment']} | PASS | {graph['node_count']:,} | "
            f"{graph['directed_edge_count']:,} | {baseline['candidate_count_at_0_5']:,} | "
            f"{baseline['candidate_rate_at_0_5']:.3f} |"
        )

    if any(environment.get("contract", {}).get("sidecar_warning") for environment in receipt["environments"]):
        lines.extend(
            [
                "",
                "입력 순서를 뒤집었을 때 현재 GNN이 읽는 17특징과 typed edge는 같았지만, 모델이 읽지 않는 8개 edge 부가값은 최대 0.125 달라졌다. 이는 현 GNN 추론을 바꾸지 않으므로 투명한 계약 정정 뒤 진행했지만, 그 부가값을 사용할 후속 Graph Transformer는 생성기의 순위 tie 결정을 고치기 전까지 실행하면 안 된다.",
            ]
        )

    lines.extend(
        [
            "",
            "후보 수는 벽 개수나 정확도가 아니다. CubiCasa에서 학습한 모델이 이 회사 도면에 부여한 확률을 같은 도면의 개입 전후로 대응시키기 위한 기준점이다.",
            "",
            "## 의미보존 개입",
            "",
            "| 환경 | 개입 | 판정 | 평균 절대변화 | p95 | 최대변화 | 0.5 판정 뒤집힘 |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for environment in receipt["environments"]:
        for row in environment.get("interventions", []):
            measurement = row["measurement"]
            lines.append(
                f"| {environment['environment']} | {row['intervention']} | {row['status']} | "
                f"{measurement['mean_abs_delta']:.6f} | {measurement['p95_abs_delta']:.6f} | "
                f"{measurement['max_abs_delta']:.6f} | {measurement['flip_count_at_0_5']:,}/"
                f"{measurement['matched_original_handles']:,} ({measurement['flip_rate_at_0_5']:.3f}) |"
            )

    lines.extend(
        [
            "",
            "## 확률 변화의 발생 위치",
            "",
            "| 환경 | 개입 | handle별 특징 최대변화 | typed edge 대칭차 | edge 수 변화 |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for environment in receipt["environments"]:
        for row in environment.get("interventions", []):
            diagnosis = row["model_input_diagnosis"]
            feature_delta = diagnosis.get("max_feature_delta")
            edge_difference = diagnosis.get("typed_edge_symmetric_difference")
            lines.append(
                f"| {environment['environment']} | {row['intervention']} | "
                f"{feature_delta:.6f} | {edge_difference:,} | {diagnosis['directed_edge_count_delta']:+,} |"
                if feature_delta is not None and edge_difference is not None
                else f"| {environment['environment']} | {row['intervention']} | 구조 변환 | 구조 변환 | {diagnosis['directed_edge_count_delta']:+,} |"
            )

    lines.extend(
        [
            "",
            "평행이동과 올바른 단위 재표현에서도 typed edge가 달라졌다면 확률 변화는 신경망만의 수치 민감성이 아니라 graph builder의 임계경계·후보선택이 좌표 표현에 의존한다는 뜻이다. layer 제거에서 모델 입력과 확률이 함께 완전 동일하면 layer가 이 체크포인트에 들어가지 않는다는 음성 대조가 성립한다.",
        ]
    )

    lines.extend(
        [
            "",
            "평행이동·일관 단위 재표현·layer 제거는 모델 입력의 물리 의미가 완전히 같아야 하므로 최대 확률 편차 1e-6과 뒤집힘 0개를 요구했다. 회전·반사·선분 이등분은 벽 의미는 같지만 모델이 명시적으로 불변이 아니어서 사전등록한 평균 변화 0.02와 뒤집힘 5% 문턱으로 판정했다.",
            "",
            "좌표만 1000배 확대하는 갈래는 `scale_mm_per_unit`을 일부러 고치지 않은 음성 대조군이다. 이 결과는 모델의 결함 판정에 쓰지 않고 단위 계약을 깨면 입력 그래프가 달라진다는 계측으로만 남겼다.",
            "",
            "## 주장 경계와 다음 판단",
            "",
            "- wall truth가 없으므로 AUPRC·정밀도·재현율은 계산하지 않았다.",
            "- 승인본과 실시설계본은 파일명 대응 후보일 뿐 선분별 같은 정답이 아니어서 서로의 확률 일치도를 정확도로 해석하지 않았다.",
            "- 이 셀에서 안정성에 실패한 변환은 회사 학습 전에 고쳐야 할 표현 취약성이다. 안정성에 통과해도 벽 정확도를 보장하지 않는다.",
            "- GBDT는 CubiCasa 절대축척 계약이 충돌해 실행하지 않았고, Transformer 계열은 봉인된 회사 SEG-IR 입력계약과 체크포인트가 없어 실행하지 않았다.",
            "",
        ]
    )
    return "\n".join(lines)


def _artifact_manifest(run_dir: Path) -> dict[str, Any]:
    files = [path for path in run_dir.rglob("*") if path.is_file() and path.name != "artifact_manifest.json"]
    return {
        "schema": "e2.company_gnn_artifact_manifest.v1",
        "created_at": _utc_now(),
        "files": [_file_record(path) for path in sorted(files)],
    }


def run(spec: Mapping[str, Any], run_dir: Path, prereg: Path) -> dict[str, Any]:
    return refusal_receipt(
        requested_receipt_schema="e2.company_gnn_intervention_receipt.v1",
        experiment_id=spec.get("experiment_id"),
        entrypoint="tools.e2.company_gnn_intervention.run",
        claim_boundary="no direct model inference; sealed executor required",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--prereg", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt = run({}, args.run_dir, args.prereg)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
