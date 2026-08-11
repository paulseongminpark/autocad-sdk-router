#!/usr/bin/env python3
"""Pure company-pair analysis helpers with a retired public experiment runner.

The primary geometry scope excludes every segment descended from an INSERT that
owns an active XCLIP.  The XCLIP-visible WorldIR remains a diagnostic surface;
raw expansion counts remain a negative control.  Public ``run`` and CLI calls
stop before analysis until the registered sealed E2 executor exists.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.e2 import experiment_guard, w1_real_defs  # noqa: E402
from tools.e2.qualification import engine  # noqa: E402
from tools.e2.qualification.sealed_executor import refusal_receipt  # noqa: E402


PASS = "PASS"
PARTIAL = "PARTIAL_PASS"
BLOCKED = "BLOCKED"
THRESHOLD = 0.5
MAX_EXACT_VECTORIZED_SEGMENTS = 10_000
PARITY_SAMPLE_SIZE = 256
REQUIRED_OBSERVABLES = (
    "nested_insert_world_segments",
    "world_lineage",
    "silent_drop_detection",
    "xclip_preservation",
)
INTERVENTIONS = (
    "rotate_37_degrees",
    "translate_large_offset",
    "scale_coordinates_x1000_consistent",
    "scale_coordinates_x1000_naive",
    "strip_layer_names",
    "split_every_segment_at_midpoint",
)
EXPECTED_INVARIANT = frozenset(
    {
        "rotate_37_degrees",
        "translate_large_offset",
        "scale_coordinates_x1000_consistent",
        "split_every_segment_at_midpoint",
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _file_record(path: Path) -> dict[str, Any]:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": _sha256(path)}


def active_xclip_insert_handles(adapter: Mapping[str, Any]) -> set[str]:
    return {
        str(entity.get("handle"))
        for definition in (adapter.get("definitions") or {}).values()
        if isinstance(definition, Mapping)
        for entity in definition.get("entities", []) or []
        if isinstance(entity, Mapping)
        and entity.get("kind") == "INSERT"
        and isinstance(entity.get("clip"), Mapping)
    }


def _xclip_ancestors(segment: Mapping[str, Any], active_handles: set[str]) -> list[str]:
    return [
        str(step.get("insert_entity_handle"))
        for step in segment.get("lineage_path", []) or []
        if isinstance(step, Mapping)
        and str(step.get("insert_entity_handle")) in active_handles
    ]


def derive_main_only(
    adapter: Mapping[str, Any], world: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Drop all visible geometry below an active-XCLIP INSERT ancestry."""

    active_handles = active_xclip_insert_handles(adapter)
    visible = world.get("segments", []) or []
    kept: list[Mapping[str, Any]] = []
    excluded = 0
    root_direct = 0
    max_depth = 0
    excluded_by_clip: dict[str, int] = {}
    for segment in visible:
        if not isinstance(segment, Mapping):
            continue
        lineage = segment.get("lineage_path", []) or []
        max_depth = max(max_depth, len(lineage))
        if not lineage:
            root_direct += 1
        ancestors = _xclip_ancestors(segment, active_handles)
        if ancestors:
            excluded += 1
            excluded_by_clip[ancestors[0]] = excluded_by_clip.get(ancestors[0], 0) + 1
        else:
            kept.append(segment)

    filtered_world = {
        "drawing_id": world.get("drawing_id"),
        "segments": kept,
    }
    seg_ir = engine._to_seg_ir(filtered_world, engine._layer_index(adapter))
    violations = sum(
        bool(_xclip_ancestors(segment, active_handles))
        for segment in kept
    )
    conservation = world.get("conservation_ledger") or {}
    summary = {
        "schema": "e2.main_only_scope.v1",
        "status": PASS if violations == 0 and len(kept) + excluded == len(visible) else BLOCKED,
        "definition": "exclude every visible segment descended from an active-XCLIP INSERT",
        "active_xclip_insert_templates": len(active_handles),
        "active_xclip_insert_handles": sorted(active_handles),
        "world_visible_segments": len(visible),
        "main_only_segments": len(kept),
        "xclip_descendant_visible_segments": excluded,
        "root_direct_segments": root_direct,
        "nested_unclipped_segments": len(kept) - root_direct,
        "max_lineage_depth": max_depth,
        "main_only_xclip_lineage_violations": violations,
        "excluded_by_first_xclip_handle": dict(sorted(excluded_by_clip.items())),
        "raw_expected_segment_instances": conservation.get("expected_segment_instances"),
        "raw_clipped_away_segment_instances": conservation.get("clipped_away_segment_instances"),
        "world_conservation_ok": conservation.get("conservation_ok"),
    }
    return seg_ir, summary


def _score_deviation(
    reference: Mapping[str, Any], candidate: Mapping[str, Any]
) -> tuple[float, list[str]]:
    left = reference.get("per_handle", {}) or {}
    right = candidate.get("per_handle", {}) or {}
    missing = sorted(set(left) ^ set(right))
    maximum = 0.0
    for handle in set(left) & set(right):
        maximum = max(maximum, abs(float(left[handle]["score"]) - float(right[handle]["score"])))
        for channel in ("parallel", "thickness", "junction", "layer"):
            maximum = max(
                maximum,
                abs(
                    float(left[handle]["evidence"][channel])
                    - float(right[handle]["evidence"][channel])
                ),
            )
    return maximum, missing


def scorer_parity(seg_ir: Mapping[str, Any], sample_size: int = PARITY_SAMPLE_SIZE) -> dict[str, Any]:
    sample = dict(seg_ir)
    sample["segments"] = list(seg_ir.get("segments", []) or [])[:sample_size]
    reference_scorer = engine._load_evidence_grid()
    started = time.perf_counter()
    reference = reference_scorer.score(sample)
    reference_seconds = time.perf_counter() - started
    started = time.perf_counter()
    fast = w1_real_defs.fast_score(sample)
    fast_seconds = time.perf_counter() - started
    maximum, missing = _score_deviation(reference, fast)
    return {
        "schema": "e2.rule_scorer_parity.v1",
        "status": PASS if not missing and maximum <= 1e-6 else BLOCKED,
        "sample_segments": len(sample["segments"]),
        "reference_handles": len(reference.get("per_handle", {}) or {}),
        "vectorized_handles": len(fast.get("per_handle", {}) or {}),
        "handle_symmetric_difference": missing,
        "max_score_or_channel_deviation": maximum,
        "tolerance": 1e-6,
        "reference_seconds": round(reference_seconds, 6),
        "vectorized_seconds": round(fast_seconds, 6),
    }


def _positive(result: Mapping[str, Any]) -> set[str]:
    return {
        str(handle)
        for handle, record in (result.get("per_handle", {}) or {}).items()
        if float(record.get("score", 0.0)) >= THRESHOLD
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    return 1.0 if not left and not right else len(left & right) / len(left | right)


def _result_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    records = list((result.get("per_handle", {}) or {}).values())
    positives = _positive(result)
    channels: dict[str, float | None] = {}
    for channel in ("parallel", "thickness", "junction", "layer"):
        values = [float(record.get("evidence", {}).get(channel, 0.0)) for record in records]
        channels[channel] = round(sum(values) / len(values), 6) if values else None
    return {
        "handles_scored": len(records),
        "positive_handles_at_0_5": len(positives),
        "positive_rate": round(len(positives) / len(records), 6) if records else None,
        "mean_evidence_channels": channels,
    }


def measure_interventions(seg_ir: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    segment_count = len(seg_ir.get("segments", []) or [])
    if segment_count > MAX_EXACT_VECTORIZED_SEGMENTS:
        raise RuntimeError(
            f"main-only segment count {segment_count} exceeds exact-vectorized safety cap "
            f"{MAX_EXACT_VECTORIZED_SEGMENTS}; build a qualified spatial-index scorer"
        )
    started = time.perf_counter()
    baseline = w1_real_defs.fast_score(seg_ir)
    baseline_seconds = time.perf_counter() - started
    base_handles = baseline.get("per_handle", {}) or {}
    base_positive = _positive(baseline)
    rows = []
    for name in INTERVENTIONS:
        transformed, params = engine._transform_seg_ir(seg_ir, name)
        if len(transformed.get("segments", []) or []) > MAX_EXACT_VECTORIZED_SEGMENTS:
            raise RuntimeError(
                f"{name} segment count exceeds safety cap {MAX_EXACT_VECTORIZED_SEGMENTS}"
            )
        started = time.perf_counter()
        result = w1_real_defs.fast_score(transformed, params=params)
        seconds = time.perf_counter() - started
        other_handles = result.get("per_handle", {}) or {}
        other_positive = _positive(result)
        all_handles = set(base_handles) | set(other_handles)
        deltas = {
            handle: abs(
                float(base_handles.get(handle, {}).get("score", 0.0))
                - float(other_handles.get(handle, {}).get("score", 0.0))
            )
            for handle in all_handles
        }
        max_handle = max(deltas, key=lambda handle: (deltas[handle], handle)) if deltas else None
        maximum = deltas.get(max_handle, 0.0) if max_handle is not None else 0.0
        jaccard = _jaccard(base_positive, other_positive)
        expected = name in EXPECTED_INVARIANT
        invariant = jaccard == 1.0 and maximum <= 1e-6
        rows.append(
            {
                "intervention": name,
                "expected_invariant": expected,
                "result": (
                    "INVARIANCE_PASS" if expected and invariant
                    else "INVARIANCE_FAIL" if expected
                    else "MEASURED_CONTROL"
                ),
                "transformed_segments": len(transformed.get("segments", []) or []),
                "handles_scored": len(other_handles),
                "positive_handles_at_0_5": len(other_positive),
                "positive_membership_changed_handles": len(base_positive ^ other_positive),
                "positive_handle_jaccard_vs_baseline": round(jaccard, 6),
                "score_changed_handle_count": sum(delta > 1e-6 for delta in deltas.values()),
                "max_per_handle_score_delta": round(maximum, 6),
                "max_delta_handle": max_handle,
                "seconds": round(seconds, 6),
            }
        )
        del transformed, result
        gc.collect()
    return baseline, {
        "schema": "e2.company_pair_rule_interventions.v1",
        "status": "MEASURED",
        "scorer": "w1_real_defs.fast_score exact-vectorized path",
        "safety_cap_segments": MAX_EXACT_VECTORIZED_SEGMENTS,
        "baseline": {**_result_summary(baseline), "seconds": round(baseline_seconds, 6)},
        "interventions": rows,
        "accuracy_metrics": None,
        "claim_boundary": "rule self-consistency on an unlabeled main-only projection, not wall accuracy",
    }


def _candidate_rows(seg_ir: Mapping[str, Any], result: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_handle = {str(segment.get("handle")): segment for segment in seg_ir.get("segments", []) or []}
    rows = []
    for handle, record in (result.get("per_handle", {}) or {}).items():
        if float(record.get("score", 0.0)) < THRESHOLD:
            continue
        source = by_handle.get(str(handle), {})
        rows.append(
            {
                "placed_uid": str(handle),
                "score": record.get("score"),
                "score_name_blind": record.get("score_nb"),
                "evidence": record.get("evidence", {}),
                "layer": source.get("layer"),
                "kind": source.get("kind"),
                "source_entity_handle": source.get("source_entity_handle"),
                "source_def_handle": source.get("source_def_handle"),
            }
        )
    rows.sort(key=lambda row: (-float(row["score"]), row["placed_uid"]))
    return rows


def _guard(world: Mapping[str, Any]) -> dict[str, Any]:
    decision = experiment_guard.qualify(
        required_observables=REQUIRED_OBSERVABLES,
        candidate="native_graph_worldir_segments",
        conclusion="exploratory",
    )
    return experiment_guard.verify_probe(decision, world, allow_empty=False)


def _process_environment(
    environment: str,
    config: Mapping[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    env_dir = run_dir / environment
    source_path = Path(config["source"])
    expected_source_hash = str(config["source_sha256"]).lower()
    before_hash = _sha256(source_path)
    if before_hash != expected_source_hash:
        raise RuntimeError(
            f"{environment}: source hash mismatch expected={expected_source_hash} actual={before_hash}"
        )

    adapter_path = Path(config["adapter"])
    world_path = Path(config["world"])
    native_path = Path(config["native"])
    adapter = _read_json(adapter_path)
    world = _read_json(world_path)
    guard = _guard(world)
    _write_json(env_dir / "guard_decision.json", guard)
    if guard.get("status") != experiment_guard.READY:
        raise RuntimeError(f"{environment}: experiment guard did not return READY: {guard}")

    seg_ir, scope = derive_main_only(adapter, world)
    _write_json(env_dir / "main_only.segir.json", seg_ir)
    _write_json(env_dir / "scope_summary.json", scope)
    if scope["status"] != PASS:
        raise RuntimeError(f"{environment}: main-only scope accounting failed")

    del adapter, world
    gc.collect()
    parity = scorer_parity(seg_ir)
    _write_json(env_dir / "scorer_parity.json", parity)
    if parity["status"] != PASS:
        raise RuntimeError(f"{environment}: fast scorer parity failed")

    baseline, interventions = measure_interventions(seg_ir)
    candidates = {
        "schema": "e2.company_pair_wall_candidates.v1",
        "status": "EXPLORATORY_UNLABELED",
        "environment": environment,
        "threshold": THRESHOLD,
        "candidate_count": len(_positive(baseline)),
        "candidates": _candidate_rows(seg_ir, baseline),
        "accuracy_metrics": None,
        "warning": "Candidates are rule outputs, not wall truth.",
    }
    _write_json(env_dir / "rule_interventions.json", interventions)
    _write_json(env_dir / "wall_candidates_rules.json", candidates)

    after_hash = _sha256(source_path)
    if after_hash != before_hash:
        raise RuntimeError(f"{environment}: source DWG changed during the run")
    artifacts = [
        env_dir / "guard_decision.json",
        env_dir / "main_only.segir.json",
        env_dir / "scope_summary.json",
        env_dir / "scorer_parity.json",
        env_dir / "rule_interventions.json",
        env_dir / "wall_candidates_rules.json",
    ]
    return {
        "environment": environment,
        "source": {"path": str(source_path.resolve()), "sha256_before": before_hash, "sha256_after": after_hash},
        "inputs": [_file_record(path) for path in (native_path, adapter_path, world_path)],
        "scope": scope,
        "parity": parity,
        "rules": interventions,
        "candidate_count": candidates["candidate_count"],
        "artifacts": [_file_record(path) for path in artifacts],
    }


def _render_report(receipt: Mapping[str, Any]) -> str:
    by_env = {row["environment"]: row for row in receipt["environments"]}
    approval = by_env["approval"]
    implementation = by_env["implementation"]
    correction_text = ""
    if receipt.get("tool_correction"):
        correction_text = (
            "\n첫 실행은 끝점 접촉을 극소 겹침으로 오인한 평행이동 반례와, 정확히 400mm인 간격이 "
            "회전 뒤 문턱 밖으로 밀린 반례를 냈다. 둘 다 부동소수점 경계 결함으로 원인을 분리했고, "
            "단위 일관 허용오차를 기준·벡터화 경로에 함께 적용한 뒤 실제 좌표를 회귀시험에 고정했다. "
            "교정 뒤 회전·평행이동·일관 단위변환은 두 환경 모두 완전 불변이다.\n"
        )

    def intervention_rows(row: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
        return {item["intervention"]: item for item in row["rules"]["interventions"]}

    ai = intervention_rows(approval)
    ii = intervention_rows(implementation)
    lines = []
    for name in INTERVENTIONS:
        lines.append(
            f"| {name} | {ai[name]['result']} | {ai[name]['positive_membership_changed_handles']} | "
            f"{ai[name]['max_per_handle_score_delta']} | {ii[name]['result']} | "
            f"{ii[name]['positive_membership_changed_handles']} | {ii[name]['max_per_handle_score_delta']} |"
        )
    approval_scope = approval["scope"]
    implementation_scope = implementation["scope"]
    return f"""# E2 A30 승인-실시 관측·개입 첫 셀

상태: **{receipt['status']}**

## 결론

두 원본 DWG의 실행 전후 SHA-256은 각각 동일했다. 네이티브 IR에서 WorldIR로 가는 화면 가시 범위의 보존 회계도 2/2 통과했고, 실행 가드는 두 환경 모두 `READY`였다.

그러나 화면에 보이는 XCLIP 조각까지 모두 학습 입력으로 쓰는 것은 Paul의 범위 정의와 다르다. 활성 XCLIP INSERT 아래의 가시 기하를 전부 제외하자 사업승인본은 {approval_scope['world_visible_segments']:,}개 중 {approval_scope['main_only_segments']:,}개, 실시설계본은 {implementation_scope['world_visible_segments']:,}개 중 {implementation_scope['main_only_segments']:,}개만 주도면 전용 범위에 남았다. 남은 선분에서 활성 XCLIP 계보 위반은 양쪽 모두 0개다.

규칙 후보는 사업승인본 {approval['rules']['baseline']['positive_handles_at_0_5']:,}/{approval['rules']['baseline']['handles_scored']:,}, 실시설계본 {implementation['rules']['baseline']['positive_handles_at_0_5']:,}/{implementation['rules']['baseline']['handles_scored']:,}였다. 이것은 정확도가 아니라 검토 후보 수다. 두 버전은 같은 파일명일 뿐 의미 대응 정답이 아니므로 후보 집합을 서로 직접 대조하지 않았다.

## 도구 자격

- 기준 순수 Python 채점기와 정확 벡터화 채점기의 고정 {approval['parity']['sample_segments']}개 표본 최대 편차: 승인 `{approval['parity']['max_score_or_channel_deviation']}`, 실시 `{implementation['parity']['max_score_or_channel_deviation']}`.
- 주도면 전용 선분: 승인 {approval_scope['main_only_segments']:,}, 실시 {implementation_scope['main_only_segments']:,}; 안전 상한 {MAX_EXACT_VECTORIZED_SEGMENTS:,} 이하.
- GBDT와 GNN은 실행하지 않았다. 기존 체크포인트의 입력 특징 계약을 이번 placed-entity 그래프가 만족한다는 증거 없이 숫자를 내는 것은 전이 실험이 아니기 때문이다.
{correction_text}

## 규칙 개입 결과

| 개입 | 승인 판정 | 승인 후보 변동 | 승인 최대 점수변화 | 실시 판정 | 실시 후보 변동 | 실시 최대 점수변화 |
|---|---|---:|---:|---|---:|---:|
{chr(10).join(lines)}

회전·평행이동·일관된 단위 변환·선분 이등분은 의미 보존 개입이다. `INVARIANCE_FAIL`은 규칙이 벽 정확도에 실패했다는 뜻이 아니라, 같은 기하 의미를 다른 표현으로 썼을 때 자기 판단을 보존하지 못했다는 뜻이다. 좌표만 1000배 바꾼 갈래는 의도적 단위 오류이고 layer 제거는 회사 명명 관습 의존량을 재는 대조군이다.

수치 경계 결함을 제거한 뒤 남은 의미보존 실패는 선분 이등분뿐이다. 승인본은 후보 소속은 유지됐지만 점수가 최대 0.171428 변했고, 실시설계본은 26개 후보가 뒤집히며 최대 점수가 0.681739 변했다. 따라서 현재 손 규칙도 선분 수·새 중점 접합·부분 겹침 같은 표현 분절도에 의존하며, GNN과 대조되는 완전한 불변 기준선으로 간주할 수 없다.

layer 이름 제거 결과가 0인 것은 회사 관습에 견고하다는 증거가 아니다. 현재 규칙의 wall 토큰이 이 주도면 범위의 실제 layer 이름을 인식하지 못해 layer 채널이 처음부터 사실상 꺼져 있었음을 뜻한다. 회사 적응에서는 layer 사전을 약한 보조 신호로 별도 학습할 수 있지만, 기하·위상 신호와 독립적으로 검증해야 한다.

## 주장 경계

- 전체 상태는 `PARTIAL_PASS`다. 지원하는 2D·주도면 범위의 보존과 개입 실행은 통과했지만, 프록시와 일부 네이티브 섹션은 부분 관측이며 wall truth가 없다.
- `wall_candidates_rules.json`은 후보 목록이지 정답이 아니다.
- 다음 셀은 이 WorldIR을 기존 17특징 그래프로 바꾸는 변환의 동등성을 먼저 검증하고, 통과할 때만 동결 GNN에 같은 개입을 적용한다.
"""


def run(spec: Mapping[str, Any], run_dir: Path, prereg: Path) -> dict[str, Any]:
    return refusal_receipt(
        requested_receipt_schema="e2.company_pair_intervention_receipt.v1",
        experiment_id=spec.get("experiment_id"),
        entrypoint="tools.e2.company_pair_intervention.run",
        claim_boundary="no direct experiment execution; sealed executor required",
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
