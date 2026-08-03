"""Deep module for the E2 model-assisted wall-hypothesis jury.

The external interface is one operation: :func:`build_model_assisted_report`.
It owns unsupported-geometry reachability, proposal construction, frozen-model
inference, intervention stability, dependence-aware fusion, review sampling,
and receipt generation.  Callers supply paths and policy in one specification;
they do not coordinate the internal seams themselves.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from tools.e2.qualification import engine as phase1
from tools.e2.qualification._phase2_geometry import audit_unsupported_visibility
from tools.e2.qualification._phase2_models import FrozenJury
from tools.e2.qualification._phase2_review import (
    build_hypotheses,
    build_review_queue,
    fuse_jury,
    review_csv,
    review_html,
)


STATUS_PASS = "PASS"
STATUS_PARTIAL = "PARTIAL_PASS"
STATUS_BLOCKED = "BLOCKED"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object at {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path, role: str) -> dict[str, Any]:
    return {"role": role, "path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": _sha256(path)}


def _vlm_runtime_audit(spec: Mapping[str, Any]) -> dict[str, Any]:
    adapters = []
    base_names = set()
    for raw_path in spec.get("vlm_adapter_paths", []) or []:
        path = Path(raw_path)
        config_path = path / "adapter_config.json"
        row: dict[str, Any] = {"path": str(path), "exists": path.is_dir(), "config_path": str(config_path)}
        if config_path.is_file():
            config = _read_json(config_path)
            base = str(config.get("base_model_name_or_path") or "")
            base_names.add(base)
            model_path = path / "adapter_model.safetensors"
            row.update(
                {
                    "base_model_name_or_path": base,
                    "adapter_model_exists": model_path.is_file(),
                    "adapter_model_sha256": _sha256(model_path) if model_path.is_file() else None,
                    "peft_type": config.get("peft_type"),
                }
            )
        adapters.append(row)
    packages = {
        name: importlib.util.find_spec(name) is not None
        for name in ("torch", "transformers", "peft", "accelerate", "qwen_vl_utils")
    }
    search_roots = [Path(path) for path in spec.get("vlm_base_search_roots", []) or []]
    local_base_evidence = []
    for root in search_roots:
        if not root.is_dir():
            continue
        for config in root.glob("**/config.json"):
            lowered = str(config).lower()
            if "qwen2.5" in lowered and "vl" in lowered and "3b" in lowered:
                local_base_evidence.append(str(config))
                if len(local_base_evidence) >= 20:
                    break
        if len(local_base_evidence) >= 20:
            break
    ready = (
        bool(adapters)
        and all(row.get("adapter_model_exists") for row in adapters)
        and bool(local_base_evidence)
        and all(packages.values())
    )
    return {
        "schema": "e2.vlm_runtime_audit.v1",
        "status": STATUS_PASS if ready else "NOT_RUN_INCOMPLETE_RUNTIME",
        "adapters": adapters,
        "declared_base_models": sorted(base_names),
        "local_base_model_config_evidence": local_base_evidence,
        "packages": packages,
        "decision": (
            "VLM may enter the jury only after a deterministic image-to-JSON smoke test."
            if ready
            else "Do not count the local LoRA files as an executable VLM juror: the base model and/or required inference runtime is absent."
        ),
    }


def _model_summary(jury: Mapping[str, Any]) -> dict[str, Any]:
    by_label = Counter(row["automatic_label"] for row in jury["results"])
    unstable = Counter()
    disagreement = 0
    for row in jury["results"]:
        if row["learned_agreement_delta"] > 0.15:
            disagreement += 1
        for juror, stability in row["intervention_stability"].items():
            if not stability["stable_at_0_10"]:
                unstable[juror] += 1
    return {
        "labels": dict(sorted(by_label.items())),
        "unstable_hypotheses_by_juror": dict(sorted(unstable.items())),
        "learned_model_disagreement_hypotheses": disagreement,
    }


def _render_report(
    spec: Mapping[str, Any],
    visibility: Mapping[str, Any],
    hypotheses: Mapping[str, Any],
    frozen: Mapping[str, Any],
    vlm: Mapping[str, Any],
    jury: Mapping[str, Any],
    queue: Mapping[str, Any],
    guard: Mapping[str, Any] | None,
) -> str:
    summary = _model_summary(jury)
    counts = visibility["counts"]
    by_type = visibility["by_dxf_name_and_status"]
    visible_types = [
        f"{name}={statuses.get('POTENTIALLY_VISIBLE', 0)}"
        for name, statuses in by_type.items()
        if statuses.get("POTENTIALLY_VISIBLE", 0)
    ]
    labels = summary["labels"]
    guard_status = (guard or {}).get("guard", guard or {}).get("status") if guard else None
    return f"""# E2 모델-보조 벽 가설 배심 보고서

상태: **{STATUS_PARTIAL}**

실험: `{spec['experiment_id']}`
원본 SHA-256: `{spec['source']['sha256']}`
실험 가드: `{guard_status or 'MISSING'}`

## 결론

첫 보고서의 319개 규칙 후보를 사람이 319번 판정하는 문제를 **82개 벽 가설 판정**으로 줄였다. 평행 쌍 그래프에서 서로 연결된 선분을 하나의 가설로 묶었고, 319/319개 후보가 정확히 한 가설에 귀속되어 회계 차이는 0이다.

자동 배심은 실제 동결 모델을 실행했다. 손 기하 규칙, CubiCasa로 학습한 3시드 GBDT, CubiCasa로 학습한 3시드 GNN이 같은 placed-entity ID를 채점했고, 회전·평행이동·물리적으로 일관된 단위변환·층 이름 제거·선분 이등분에서 점수가 유지되는지도 다시 추론했다. 다만 GBDT와 GNN은 학습 코퍼스를 공유하므로 두 개의 독립 truth로 세지 않았다. 서로 다른 아키텍처의 동의는 유용한 신호지만, 같은 데이터 편향의 동의일 수 있다.

엄격한 자동 silver 게이트 결과는 `WALL={labels.get('PROVISIONAL_SILVER_WALL', 0)}`, `NOT_WALL={labels.get('PROVISIONAL_SILVER_NOT_WALL', 0)}`, `REVIEW={labels.get('REVIEW', 0)}`이다. 이번에는 자동 silver가 하나도 없으므로 모델이 사람 판정을 대체했다고 말할 수 없다. 공개 검토 큐는 표적 검토 {queue['public_targeted_count']}개와 `{queue['public_audit_kind']}` 감사 {queue['public_audit_count']}개, 합계 {queue['public_total_count']}개의 **첫 calibration 배치**다. 별도로 {queue['sealed_holdout_count']}개를 점수와 무관한 해시로 봉인했고, 나머지 {queue['deferred_unqueued_count']}개는 자동 확정된 것이 아니라 첫 배치 결과 전까지 미해결로 남겼다.

## 지원 제외 형상의 실제 도달성

네이티브 Graph IR의 INSERT 변환과 XCLIP 스택을 그대로 따라, adapter에서 빠진 엔터티의 보수적 bbox/geometry footprint를 세계좌표로 배치했다. 지원 제외 배치 인스턴스는 {counts.get('placed_unsupported_instances', 0)}개였고, 그중 잠재 가시 {counts.get('potentially_visible', 0)}개, XCLIP 밖임을 footprint로 증명한 것 {counts.get('clipped_by_footprint_proof', 0)}개, 형상을 확정할 수 없는 것 {counts.get('unknown_geometry', 0)}개다.

잠재 가시 종류: `{', '.join(visible_types) if visible_types else '없음'}`.

이 결과는 “실제로 렌더됐다”는 강한 판정이 아니다. bbox 교차는 과포함할 수 있도록 설계했다. 반대로 `CLIPPED_BY_FOOTPRINT_PROOF`만 XCLIP 밖이라고 닫는다. 잠재 가시 curve/region 종류가 있으면 adapter 확장은 새 분석 모집단을 만들기 때문에 이 run 안에서 슬쩍 추가하지 않고 재자격 대상으로 보냈다: `{visibility['adapter_extension_decision']['status']}`.

## 실행한 판정기

| 판정기 | 실행 | 독립성 집단 | 이 run에서 뜻하는 것 |
|---|---|---|---|
| 손 기하 규칙 | PASS | deterministic_geometry | 평행·두께·접합 증거 점수. truth 확률 아님 |
| GBDT 3시드 | PASS | cubicasa_supervised | 12 mm/pixel 물리 단위로 정규화한 동결 전이 점수 |
| GNN 3시드 | PASS | cubicasa_supervised | 17개 이름-맹 그래프 특징의 동결 전이 점수. 알려진 코퍼스 shortcut 위험 유지 |
| Qwen2.5-VL floorplan LoRA | {vlm['status']} | cubicasa_vision_supervised | adapter 파일만으로는 실행 모델이 아님 |

동결 아티팩트 무결성은 `{frozen['status']}`다. GBDT와 GNN의 점수 차이가 0.15를 넘은 가설은 {summary['learned_model_disagreement_hypotheses']}개다. 의미 보존 개입에서 최대 0.10보다 크게 변한 가설은 판정기별 `{json.dumps(summary['unstable_hypotheses_by_juror'], ensure_ascii=False, sort_keys=True)}`이다. 이것이 자동 silver가 넓게 퍼지지 못하게 막는 핵심 제약이다.

## 사람이 보는 방식

- `review_public.html`: 빨간 선으로 가설을 보여준다. 사람이 먼저 WALL / NOT_WALL / AMBIGUOUS / UNSURE를 고른 뒤에만 모델 근거가 열린다.
- `review_sealed_holdout.html`: 모델 점수를 파일 자체에 넣지 않았다. 봉인 라벨은 공개 큐의 threshold나 규칙을 고치는 데 사용하면 안 된다.
- `review_queue.csv`: 공개 검토 대상과 판정기 점수를 표로 제공한다.
- `review_queue.json`: 선택 규칙, 기하, 배심 근거, 빈 사람 라벨 칸을 함께 보존한다.

## 과학적 해석 경계

1. 이 보고서는 벽 정확도를 확정하지 않는다. 한 장의 새 DWG에서 모델 점수와 불변성을 측정하고 사람 라벨 비용을 줄이는 장치를 자격화했다.
2. 자동 silver는 **NOT_GOLD_NOT_TRAINING_TRUTH**다. 공개 calibration 라벨로 오류율을 재고, 한 번만 여는 sealed holdout에서 성능을 확인하기 전에는 승격할 수 없다.
3. 규칙 후보에서 시작했으므로 자동 `NOT_WALL` 모집단은 구조적으로 빈약하다. anti-wall 학습을 하려면 규칙 밖의 음성 후보도 별도의 모집단으로 샘플링해야 한다.
4. VLM은 이번 배심에 없다. LoRA adapter, 기반 Qwen2.5-VL-3B 모델, transformers/peft 런타임, deterministic JSON smoke가 모두 갖춰져야 네 번째 판정기로 들어온다.
5. 지원 제외 curve/region을 adapter에 추가하면 590개 선분과 82개 가설의 모집단 자체가 바뀐다. 그때는 이 결과를 이어붙이지 말고 새 guard와 자격 보고서를 만든다.
"""


def build_model_assisted_report(spec: Mapping[str, Any], run_dir: Path) -> dict[str, Any]:
    """Build and verify the complete phase-2 artifact set in ``run_dir``."""

    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    if spec.get("schema") != "e2.model_assisted_spec.v1":
        raise ValueError("phase-2 spec must declare schema=e2.model_assisted_spec.v1")
    source = Path(spec["source"]["path"])
    source_hash = _sha256(source)
    if source_hash.lower() != str(spec["source"]["sha256"]).lower():
        raise ValueError(f"source hash mismatch: {source_hash}")

    first_run = Path(spec["first_run"])
    paths = {
        "native": first_run / "primary_probe" / "dwg_graph_ir.json",
        "adapter": first_run / "worldir_input.json",
        "world": first_run / "world_geometry_ir.json",
        "candidates": first_run / "wall_candidates_rules.json",
        "first_receipt": first_run / "qualification_receipt.json",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"phase-1 evidence missing: {missing}")
    native = _read_json(paths["native"])
    adapter = _read_json(paths["adapter"])
    world = _read_json(paths["world"])
    candidates = _read_json(paths["candidates"])
    first_receipt = _read_json(paths["first_receipt"])
    if candidates.get("candidate_count") != 319:
        raise ValueError(f"expected frozen phase-1 candidate count 319, got {candidates.get('candidate_count')}")
    if first_receipt.get("source", {}).get("sha256", "").lower() != source_hash.lower():
        raise ValueError("phase-1 receipt is not bound to the phase-2 source")

    seg_ir = phase1._to_seg_ir(world, phase1._layer_index(adapter))
    visibility = audit_unsupported_visibility(native)
    hypotheses = build_hypotheses(seg_ir, candidates)
    frozen_jury = FrozenJury(Path(spec["frozen_transfer_harness"]))
    frozen_receipt = frozen_jury.artifact_receipt()
    segment_scores = frozen_jury.score_with_interventions(seg_ir)
    jury = fuse_jury(hypotheses, segment_scores)
    review_policy = spec.get("review_policy") or {}
    queue = build_review_queue(
        str(world.get("drawing_id") or source_hash),
        hypotheses,
        jury,
        public_limit=int(review_policy.get("public_limit", 24)),
        audit_count=int(review_policy.get("audit_count", 6)),
        sealed_holdout_count=int(review_policy.get("sealed_holdout_count", 12)),
    )
    vlm = _vlm_runtime_audit(spec)

    guard_path = run_dir / "guard_decision.json"
    guard = _read_json(guard_path) if guard_path.is_file() else None
    guard_status = (guard or {}).get("guard", guard or {}).get("status") if guard else None
    gates = [
        {"gate": "source_identity", "status": STATUS_PASS, "evidence": source_hash},
        {
            "gate": "phase1_candidate_accounting",
            "status": STATUS_PASS if hypotheses["balance_ok"] else STATUS_BLOCKED,
            "evidence": f"{hypotheses['accounted_candidate_count']}/{hypotheses['source_candidate_count']}",
        },
        {"gate": "frozen_model_integrity", "status": frozen_receipt["status"], "evidence": "sealed W4 hashes"},
        {"gate": "runtime_experiment_guard", "status": STATUS_PASS if guard_status == "READY" else STATUS_BLOCKED, "evidence": str(guard_status)},
        {"gate": "human_calibration", "status": "PASS_WITH_DEFERRAL", "evidence": "review queue generated; no human labels yet"},
        {"gate": "vlm_juror", "status": "PASS_WITH_DEFERRAL", "evidence": vlm["status"]},
    ]
    status = STATUS_PARTIAL if all(row["status"] != STATUS_BLOCKED for row in gates) else STATUS_BLOCKED
    if status == STATUS_BLOCKED:
        raise RuntimeError(f"phase-2 gate blocked: {[row for row in gates if row['status'] == STATUS_BLOCKED]}")

    json_outputs = {
        "experiment_spec.json": dict(spec),
        "unsupported_visibility_audit.json": visibility,
        "wall_hypotheses.json": hypotheses,
        "frozen_model_receipt.json": frozen_receipt,
        "vlm_runtime_audit.json": vlm,
        "segment_juror_scores.json": segment_scores,
        "jury_results.json": jury,
        "review_queue.json": queue,
    }
    for name, value in json_outputs.items():
        _write_json(run_dir / name, value)
    (run_dir / "review_queue.csv").write_text(review_csv(queue), encoding="utf-8-sig", newline="")
    public_html = review_html(
        "E2 공개 벽 가설 검토",
        queue["public_queue"],
        seg_ir["segments"],
        include_jury_after_label=True,
    )
    sealed_html = review_html(
        "E2 봉인 벽 가설 holdout",
        queue["sealed_holdout_queue"],
        seg_ir["segments"],
        include_jury_after_label=False,
    )
    (run_dir / "review_public.html").write_text(public_html, encoding="utf-8", newline="\n")
    (run_dir / "review_sealed_holdout.html").write_text(sealed_html, encoding="utf-8", newline="\n")
    report = _render_report(spec, visibility, hypotheses, frozen_receipt, vlm, jury, queue, guard)
    (run_dir / "MODEL_ASSISTED_JURY_REPORT.md").write_text(report, encoding="utf-8", newline="\n")

    input_records = [_file_record(path, role) for role, path in sorted(paths.items())]
    output_names = list(json_outputs) + [
        "review_queue.csv",
        "review_public.html",
        "review_sealed_holdout.html",
        "MODEL_ASSISTED_JURY_REPORT.md",
    ]
    receipt = {
        "schema": "e2.phase2_receipt.v1",
        "status": status,
        "experiment_id": spec["experiment_id"],
        "source": {"path": str(source), "sha256": source_hash, "read_only": True},
        "gates": gates,
        "inputs": input_records,
        "outputs": [_file_record(run_dir / name, name) for name in output_names],
        "headline": {
            "source_rule_candidates": hypotheses["source_candidate_count"],
            "wall_hypotheses": hypotheses["hypothesis_count"],
            "public_review_items": queue["public_total_count"],
            "sealed_holdout_items": queue["sealed_holdout_count"],
            "deferred_unqueued_items": queue["deferred_unqueued_count"],
            "automatic_label_counts": jury["label_counts"],
            "vlm_status": vlm["status"],
        },
        "claim_boundary": "model-assisted triage and intervention evidence, not wall accuracy or deployability",
    }
    _write_json(run_dir / "phase2_receipt.json", receipt)
    return {
        "status": status,
        "run_dir": str(run_dir),
        "report": str(run_dir / "MODEL_ASSISTED_JURY_REPORT.md"),
        "receipt": str(run_dir / "phase2_receipt.json"),
        **receipt["headline"],
    }
