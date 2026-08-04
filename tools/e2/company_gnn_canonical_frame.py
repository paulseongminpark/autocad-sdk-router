#!/usr/bin/env python3
"""Test a physical-mm, centered coordinate adapter for the frozen E2 GNN."""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.e2 import company_gnn_intervention as base


ROUND_DIGITS_MM = 6


def canonicalize_physical_frame(seg_ir: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convert to centered physical mm and quantize below meaningful CAD tolerance."""

    transformed = copy.deepcopy(dict(seg_ir))
    try:
        scale = float(transformed["scale_mm_per_unit"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("scale_mm_per_unit must be a finite positive number") from exc
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("scale_mm_per_unit must be a finite positive number")

    physical_points: list[tuple[float, float]] = []
    for segment in transformed.get("segments", []) or []:
        for point in segment.get("pts", []) or []:
            x, y = float(point[0]) * scale, float(point[1]) * scale
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("non-finite point after physical-mm conversion")
            physical_points.append((x, y))
    if not physical_points:
        raise ValueError("cannot canonicalize an empty SEG-IR")
    x_min = min(point[0] for point in physical_points)
    x_max = max(point[0] for point in physical_points)
    y_min = min(point[1] for point in physical_points)
    y_max = max(point[1] for point in physical_points)
    center_x = (x_min + x_max) * 0.5
    center_y = (y_min + y_max) * 0.5

    maximum_rounding_error = 0.0
    for segment in transformed.get("segments", []) or []:
        output_points = []
        for point in segment.get("pts", []) or []:
            shifted_x = float(point[0]) * scale - center_x
            shifted_y = float(point[1]) * scale - center_y
            rounded_x = round(shifted_x, ROUND_DIGITS_MM)
            rounded_y = round(shifted_y, ROUND_DIGITS_MM)
            maximum_rounding_error = max(
                maximum_rounding_error,
                abs(shifted_x - rounded_x),
                abs(shifted_y - rounded_y),
            )
            output_points.append([rounded_x, rounded_y])
        segment["pts"] = output_points
        if segment.get("sagitta") is not None:
            physical_sagitta = float(segment["sagitta"]) * scale
            rounded_sagitta = round(physical_sagitta, ROUND_DIGITS_MM)
            maximum_rounding_error = max(
                maximum_rounding_error, abs(physical_sagitta - rounded_sagitta)
            )
            segment["sagitta"] = rounded_sagitta
    transformed["units"] = "mm"
    transformed["scale_mm_per_unit"] = 1.0
    return transformed, {
        "schema": "e2.company_physical_frame_adapter.v1",
        "input_scale_mm_per_unit": scale,
        "physical_bbox_mm": [x_min, y_min, x_max, y_max],
        "removed_origin_mm": [center_x, center_y],
        "round_digits_mm": ROUND_DIGITS_MM,
        "grid_mm": 10.0 ** (-ROUND_DIGITS_MM),
        "maximum_rounding_error_mm": maximum_rounding_error,
        "segment_count": len(transformed.get("segments", []) or []),
    }


def _digest(value: Mapping[str, Any]) -> str:
    import hashlib

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compare_canonical_geometry(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    def records(ir: Mapping[str, Any]) -> dict[str, tuple[Any, Any, Any]]:
        return {
            str(segment["handle"]): (
                segment.get("kind"),
                segment.get("pts"),
                segment.get("sagitta"),
            )
            for segment in ir.get("segments", []) or []
        }

    left, right = records(baseline), records(candidate)
    handle_difference = sorted(set(left) ^ set(right))
    changed = sorted(handle for handle in set(left) & set(right) if left[handle] != right[handle])
    return {
        "status": base.PASS if not handle_difference and not changed else base.BLOCKED,
        "handle_symmetric_difference_count": len(handle_difference),
        "changed_geometry_handle_count": len(changed),
        "first_changed_handles": changed[:20],
    }


def _process_environment(
    name: str,
    environment_spec: Mapping[str, Any],
    run_dir: Path,
    c1: Any,
    components: Mapping[str, Any],
) -> dict[str, Any]:
    source = Path(environment_spec["source_dwg"])
    expected_hash = str(environment_spec["source_sha256"]).lower()
    before_hash = base._sha256(source)
    result: dict[str, Any] = {
        "environment": name,
        "source": {"path": str(source.resolve()), "sha256_before": before_hash},
        "seg_ir": base._file_record(Path(environment_spec["seg_ir"])),
    }
    if before_hash != expected_hash:
        result.update(status=base.BLOCKED, error="source hash mismatch")
        return result

    raw = base._read_json(Path(environment_spec["seg_ir"]))
    translated_raw, translated_map = base.transform_translate(raw)
    scaled_raw, scaled_map = base.transform_consistent_scale(raw)
    canonical, canonical_meta = canonicalize_physical_frame(raw)
    canonical_twice, _ = canonicalize_physical_frame(canonical)
    translated, translated_meta = canonicalize_physical_frame(translated_raw)
    scaled, scaled_meta = canonicalize_physical_frame(scaled_raw)

    idempotent = _digest(canonical) == _digest(canonical_twice)
    geometry = {
        "translated": compare_canonical_geometry(canonical, translated),
        "consistent_scale": compare_canonical_geometry(canonical, scaled),
    }
    builder = components["builder"]
    graph_config = components["graph_config"]
    baseline_graph = builder.build_graph(canonical, graph_config, collect_edges=True)
    translated_graph = builder.build_graph(translated, graph_config, collect_edges=True)
    scaled_graph = builder.build_graph(scaled, graph_config, collect_edges=True)
    graph_comparisons = {
        "translated": base.compare_graphs(
            baseline_graph, translated_graph, tuple(builder.EDGE_TYPES), base.GRAPH_TOLERANCE
        ),
        "consistent_scale": base.compare_graphs(
            baseline_graph, scaled_graph, tuple(builder.EDGE_TYPES), base.GRAPH_TOLERANCE
        ),
    }

    raw_prediction = c1.infer(raw, components, want_chains=False)
    canonical_prediction = c1.infer(canonical, components, want_chains=False)
    translated_prediction = c1.infer(translated, components, want_chains=False)
    scaled_prediction = c1.infer(scaled, components, want_chains=False)
    identity = {str(segment["handle"]): str(segment["handle"]) for segment in raw["segments"]}
    adapter_effect = base.paired_unlabeled(raw_prediction, canonical_prediction, identity)
    prediction_comparisons = {
        "translated": base.paired_unlabeled(
            canonical_prediction, translated_prediction, translated_map
        ),
        "consistent_scale": base.paired_unlabeled(
            canonical_prediction, scaled_prediction, scaled_map
        ),
    }

    prediction_pass = all(
        comparison["max_abs_delta"] <= base.EXACT_TOLERANCE
        and comparison["flip_rate_at_0_5"] == 0.0
        and comparison["missing_baseline_handle_count"] == 0
        for comparison in prediction_comparisons.values()
    )
    graph_pass = all(
        comparison["status"] == base.PASS
        and comparison["edge_attribute_sidecar_status"] == base.PASS
        for comparison in graph_comparisons.values()
    )
    geometry_pass = all(comparison["status"] == base.PASS for comparison in geometry.values())
    validation = base.validate_seg_ir(canonical)
    all_pass = idempotent and geometry_pass and graph_pass and prediction_pass and validation["status"] == base.PASS
    result.update(
        {
            "status": base.PASS if all_pass else base.BLOCKED,
            "canonicalization": {
                "baseline": canonical_meta,
                "translated": translated_meta,
                "consistent_scale": scaled_meta,
                "idempotent": idempotent,
                "canonical_digest": _digest(canonical),
                "canonical_twice_digest": _digest(canonical_twice),
                "seg_ir_validation": validation,
            },
            "geometry_comparisons": geometry,
            "graph_comparisons": graph_comparisons,
            "prediction_comparisons": prediction_comparisons,
            "raw_to_canonical_adapter_effect": adapter_effect,
            "canonical_baseline": base._prediction_summary(
                canonical_prediction["handles"], canonical_prediction["gnn"]
            ),
        }
    )
    after_hash = base._sha256(source)
    result["source"]["sha256_after"] = after_hash
    if after_hash != before_hash:
        result.update(status=base.BLOCKED, error="source DWG changed")
    base._write_json(run_dir / name / "canonical_frame_result.json", result)
    return result


def _render_report(receipt: Mapping[str, Any]) -> str:
    lines = [
        "# E2 A30 동결 GNN 물리 좌표 canonical frame 복구 결과",
        "",
        f"상태: **{receipt['status']}**",
        "",
        "## 결론",
        "",
    ]
    if receipt["repair_status"] == base.PASS:
        lines.append(
            "물리 mm 변환→도면 중심 원점 제거→1e-6mm 반올림의 세 단계만으로, 앞 셀에서 실패했던 평행이동과 올바른 단위 재표현의 그래프 입력과 GNN 확률을 두 환경 모두 완전히 복구했다."
        )
    else:
        lines.append("canonical frame이 사전등록한 원점·단위 불변성을 두 환경 모두 복구하지 못했다.")
    lines.extend(
        [
            "",
            "## 결과",
            "",
            "| 환경 | 멱등성 | 변환 | 기하 | 그래프 입력 | 최대 확률변화 | 뒤집힘 |",
            "|---|---|---|---|---|---:|---:|",
        ]
    )
    for environment in receipt["environments"]:
        for key, label in (("translated", "평행이동"), ("consistent_scale", "올바른 단위 재표현")):
            geometry = environment["geometry_comparisons"][key]
            graph = environment["graph_comparisons"][key]
            prediction = environment["prediction_comparisons"][key]
            lines.append(
                f"| {environment['environment']} | {environment['canonicalization']['idempotent']} | {label} | "
                f"{geometry['status']} | {graph['status']} / sidecar {graph['edge_attribute_sidecar_status']} | "
                f"{prediction['max_abs_delta']:.9f} | {prediction['flip_count_at_0_5']:,}/{prediction['matched_original_handles']:,} |"
            )
    lines.extend(
        [
            "",
            "## 어댑터가 baseline을 얼마나 바꿨나",
            "",
            "| 환경 | 평균 절대 확률변화 | p95 | 최대 | 0.5 판정 뒤집힘 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for environment in receipt["environments"]:
        effect = environment["raw_to_canonical_adapter_effect"]
        lines.append(
            f"| {environment['environment']} | {effect['mean_abs_delta']:.6f} | {effect['p95_abs_delta']:.6f} | "
            f"{effect['max_abs_delta']:.6f} | {effect['flip_count_at_0_5']:,}/{effect['matched_original_handles']:,} |"
        )
    lines.extend(
        [
            "",
            "raw→canonical 변화는 정확도 개선량이 아니다. raw 경로가 임의 원점에 의존한다는 반례가 이미 있으므로, canonical frame은 동일 물리 도면에 하나의 입력만 주기 위한 결정적 선택이다. 어느 baseline이 벽을 더 잘 맞히는지는 wall truth가 생긴 뒤에만 판정할 수 있다.",
            "",
            "## 의미",
            "",
            "- 현재 동결 GNN을 회사 도면에 붙일 때는 raw SEG-IR을 직접 graph builder에 넣으면 안 된다. 이 canonical frame을 입력계약의 일부로 승격해야 한다.",
            "- 이 복구는 회전과 선분 분절 취약성을 건드리지 않았다. 회전은 orientation/bbox 특징 또는 회전 등변 모델, 분절은 collinear-chain canonicalization을 별도 개입으로 검증해야 한다.",
            "- wall truth가 없으므로 정확도·회사 적응 성공·배포 가능성은 여전히 판단할 수 없다.",
            "",
        ]
    )
    return "\n".join(lines)


def run(spec: Mapping[str, Any], run_dir: Path, prereg: Path) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    c1_path = Path(spec["c1_path"])
    c1 = base._import_module(c1_path, "e2_company_canonical_c1")
    integrity = c1.verify_integrity()
    components = c1.load_components()
    environments = [
        _process_environment(name, spec["environments"][name], run_dir, c1, components)
        for name in ("approval", "implementation")
    ]
    repair_pass = all(environment.get("status") == base.PASS for environment in environments)
    receipt = {
        "schema": "e2.company_gnn_canonical_frame_receipt.v1",
        "status": base.PARTIAL_PASS if repair_pass else base.BLOCKED,
        "repair_status": base.PASS if repair_pass else base.BLOCKED,
        "created_at": base._utc_now(),
        "experiment_id": spec["experiment_id"],
        "prereg": base._file_record(prereg),
        "integrity": integrity,
        "environments": environments,
        "accuracy_metrics": None,
        "claim_boundary": "origin and unit representation repair only; no wall accuracy",
        "code_provenance": [
            base._file_record(Path(__file__)),
            base._file_record(Path(base.__file__)),
            base._file_record(c1_path),
        ],
    }
    base._write_json(run_dir / "experiment_spec.json", spec)
    base._write_json(run_dir / "repair_receipt.json", receipt)
    (run_dir / "REPORT.md").write_text(_render_report(receipt), encoding="utf-8", newline="\n")
    base._write_json(run_dir / "artifact_manifest.json", base._artifact_manifest(run_dir))
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--prereg", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt = run(base._read_json(args.spec), args.run_dir, args.prereg)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "repair_status": receipt["repair_status"],
                "environments": [
                    {"environment": row["environment"], "status": row["status"]}
                    for row in receipt["environments"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if receipt["repair_status"] == base.PASS else 2


if __name__ == "__main__":
    raise SystemExit(main())
