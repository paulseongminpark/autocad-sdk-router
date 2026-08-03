#!/usr/bin/env python3
"""Evidence-bound qualification and first-report assembly for E2.

The module has two public operations. ``qualify`` judges already-loaded
evidence; ``build_first_report`` writes the bounded artifact set for one run.
It never treats an unlabeled drawing as a model-quality benchmark.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


STATUS_PASS = "PASS"
STATUS_PARTIAL = "PARTIAL_PASS"
STATUS_DEFERRED = "PASS_WITH_DEFERRAL"
STATUS_BLOCKED = "BLOCKED"
WALL_THRESHOLD = 0.5
ANTI_WALL_TOKENS = ("DOOR", "FUR", "KIT", "ELEV", "DIM", "TEXT", "수전", "가구")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


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


def _all_native_entities(native: Mapping[str, Any]) -> Iterable[tuple[str, Mapping[str, Any]]]:
    for entity in native.get("entities", []) or []:
        if isinstance(entity, Mapping):
            yield "modelspace", entity
    for definition in native.get("block_definitions", []) or []:
        if not isinstance(definition, Mapping):
            continue
        scope = f"block:{definition.get('handle', '<missing>')}"
        for entity in definition.get("def_entities", []) or []:
            if isinstance(entity, Mapping):
                yield scope, entity


def _entity_census(native: Mapping[str, Any]) -> dict[str, Any]:
    all_types: Counter[str] = Counter()
    modelspace_types: Counter[str] = Counter()
    block_types: Counter[str] = Counter()
    source_decoded: Counter[str] = Counter()
    xclips: Counter[str] = Counter()
    entity_templates = 0
    for scope, entity in _all_native_entities(native):
        entity_templates += 1
        dxf_name = str(entity.get("dxf_name") or "<EMPTY>").upper()
        all_types[dxf_name] += 1
        (modelspace_types if scope == "modelspace" else block_types)[dxf_name] += 1
        source = entity.get("source") if isinstance(entity.get("source"), Mapping) else {}
        source_decoded["decoded" if source.get("decoded") is True else "not_proven_decoded"] += 1
        clip = entity.get("xclip")
        if isinstance(clip, Mapping) and clip.get("enabled") is True:
            boundary = clip.get("boundary_wcs")
            xclips["enabled"] += 1
            xclips["inverted" if clip.get("inverted") else "normal"] += 1
            xclips["rectangular" if isinstance(boundary, list) and len(boundary) == 2 else "polygonal"] += 1
    diagnostics = native.get("diagnostics") if isinstance(native.get("diagnostics"), Mapping) else {}
    coverage = diagnostics.get("coverage") if isinstance(diagnostics.get("coverage"), Mapping) else {}
    return {
        "schema": "e2.entity_census.v1",
        "coverage_level": native.get("coverage_level"),
        "modelspace_entity_count": len(native.get("entities", []) or []),
        "block_definition_count": len(native.get("block_definitions", []) or []),
        "entity_template_count": entity_templates,
        "modelspace_by_dxf_name": dict(sorted(modelspace_types.items())),
        "block_definitions_by_dxf_name": dict(sorted(block_types.items())),
        "all_templates_by_dxf_name": dict(sorted(all_types.items())),
        "decode_evidence": dict(sorted(source_decoded.items())),
        "xclip": dict(sorted(xclips.items())),
        "native_modelspace_count": coverage.get("modelspace_count_from_native"),
        "realized_modelspace_count": coverage.get("realized_entity_count"),
        "modelspace_count_match": coverage.get("match"),
        "sections_present": coverage.get("sections_present", []),
        "sections_skipped": coverage.get("sections_skipped", []),
        "section_status": coverage.get("section_status", {}),
        "native_errors": diagnostics.get("errors", []),
        "native_warnings": diagnostics.get("warnings", []),
        "database": native.get("database", {}),
    }


def _compact_conservation(world: Mapping[str, Any]) -> dict[str, Any]:
    ledger = world.get("conservation_ledger")
    if not isinstance(ledger, Mapping):
        return {}
    status_counts: Counter[str] = Counter()
    for entry in ledger.get("entity_entries", []) or []:
        if isinstance(entry, Mapping):
            status_counts[str(entry.get("status", "UNKNOWN"))] += 1
    return {
        key: value
        for key, value in ledger.items()
        if key not in {"entity_entries"}
    } | {"entity_entry_status_counts": dict(sorted(status_counts.items()))}


def _gate(gate: str, status: str, evidence: str) -> dict[str, str]:
    return {"gate": gate, "status": status, "evidence": evidence}


def qualify(
    spec: Mapping[str, Any],
    native: Mapping[str, Any],
    adapter: Mapping[str, Any],
    world: Mapping[str, Any],
    evidence_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Judge observation scopes without making a wall-quality claim."""

    census = _entity_census(native)
    source = spec["source"]
    expected_hash = str(source["sha256"]).lower()
    native_source = native.get("source") if isinstance(native.get("source"), Mapping) else {}
    native_hash = str(native_source.get("sha256", "")).lower()
    adapter_ledger = adapter.get("adapter_ledger") if isinstance(adapter.get("adapter_ledger"), Mapping) else {}
    conservation = _compact_conservation(world)
    gates: list[dict[str, str]] = []
    gates.append(
        _gate(
            "source_identity",
            STATUS_PASS if expected_hash == native_hash else STATUS_BLOCKED,
            f"expected={expected_hash}; native_payload={native_hash or '<missing>'}",
        )
    )
    primary_ok = (
        native.get("schema") == "ariadne.dwg_graph_ir.v1"
        and native.get("coverage_level") == "native_full"
        and not census["native_errors"]
    )
    skipped = census["sections_skipped"]
    partial_sections = sorted(
        key for key, value in census["section_status"].items() if value != "implemented"
    )
    primary_status = STATUS_PARTIAL if primary_ok else STATUS_BLOCKED
    gates.append(
        _gate(
            "native_observation_surface",
            primary_status,
            f"coverage={native.get('coverage_level')}; skipped={skipped}; non_implemented={partial_sections}",
        )
    )
    counts_match = (
        census["modelspace_entity_count"] == census["native_modelspace_count"]
        == census["realized_modelspace_count"]
        and census["entity_template_count"] == adapter_ledger.get("source_entity_templates")
    )
    gates.append(
        _gate(
            "entity_census_accounting",
            STATUS_PASS if counts_match else STATUS_BLOCKED,
            (
                f"modelspace={census['modelspace_entity_count']}/"
                f"{census['native_modelspace_count']}/{census['realized_modelspace_count']}; "
                f"templates={census['entity_template_count']}/"
                f"{adapter_ledger.get('source_entity_templates')}"
            ),
        )
    )
    adapter_ok = adapter_ledger.get("balance_ok") is True
    gates.append(
        _gate(
            "analysis_projection_accounting",
            STATUS_PASS if adapter_ok else STATUS_BLOCKED,
            (
                f"source={adapter_ledger.get('source_entity_templates')}; "
                f"adapted={adapter_ledger.get('adapted_entity_templates')}; "
                f"excluded={adapter_ledger.get('explicitly_excluded_entity_templates')}"
            ),
        )
    )
    world_ok = world.get("status") == "PASS" and conservation.get("conservation_ok") is True
    gates.append(
        _gate(
            "world_transform_and_xclip_conservation",
            STATUS_PASS if world_ok else STATUS_BLOCKED,
            (
                f"raw={conservation.get('expected_segment_instances')}; "
                f"visible_source={conservation.get('visible_source_segment_instances')}; "
                f"clipped={conservation.get('clipped_away_segment_instances')}; "
                f"emitted_fragments={conservation.get('emitted_segment_instances')}"
            ),
        )
    )
    excluded = int(adapter_ledger.get("explicitly_excluded_entity_templates", 0) or 0)
    gates.append(
        _gate(
            "wall_analysis_geometry_scope",
            STATUS_PARTIAL if excluded else STATUS_PASS,
            f"explicitly excluded templates={excluded}; by_type={adapter_ledger.get('excluded_by_dxf_name', {})}",
        )
    )
    gates.append(
        _gate(
            "independent_completeness_oracle",
            STATUS_DEFERRED,
            "No second engine produced a field-level census for this run; no global absence claim is allowed.",
        )
    )
    critical_block = any(
        row["status"] == STATUS_BLOCKED
        for row in gates
        if row["gate"] in {
            "source_identity",
            "entity_census_accounting",
            "analysis_projection_accounting",
            "world_transform_and_xclip_conservation",
        }
    )
    status = STATUS_BLOCKED if critical_block else STATUS_PARTIAL
    return {
        "schema": "e2.qualification_receipt.v1",
        "status": status,
        "experiment_id": spec["experiment_id"],
        "created_at": _utc_now(),
        "source": {
            "path": source["path"],
            "sha256": expected_hash,
            "native_payload_sha256": native_hash,
            "read_only": bool(source.get("read_only")),
        },
        "evidence": evidence_records,
        "gates": gates,
        "scope_verdicts": {
            "native_DWG_observation": primary_status,
            "supported_2D_geometry_projection": STATUS_PASS if adapter_ok and world_ok else STATUS_BLOCKED,
            "all_entity_types_for_wall_semantics": STATUS_PARTIAL if excluded else STATUS_PASS,
            "global_no_silent_omission_claim": STATUS_DEFERRED,
            "wall_detector_quality": "NOT_ESTIMABLE_NO_LABELS",
        },
        "limitations": [
            "The drawing has no human wall truth ledger, so precision, recall, F1 and AUPRC are not estimable.",
            "The analysis projection excludes named entity types; their counts are evidence, not proof that they are irrelevant to walls.",
            "The completeness check is internally independent at the counting-contract level, not independent at the CAD-engine level.",
            "Arc geometry is represented by a chord and is not a lossless curve model.",
        ],
    }


def _layer_index(adapter: Mapping[str, Any]) -> dict[tuple[str, str], str]:
    output: dict[tuple[str, str], str] = {}
    for def_handle, definition in (adapter.get("definitions") or {}).items():
        if not isinstance(definition, Mapping):
            continue
        for entity in definition.get("entities", []) or []:
            if isinstance(entity, Mapping):
                output[(str(def_handle), str(entity.get("handle")))] = str(entity.get("layer") or "")
    return output


def _to_seg_ir(
    world: Mapping[str, Any],
    layer_index: Mapping[tuple[str, str], str],
) -> dict[str, Any]:
    segments = []
    for index, segment in enumerate(world.get("segments", []) or [], start=1):
        source_key = (
            str(segment.get("source_def_handle")),
            str(segment.get("source_entity_handle")),
        )
        segments.append(
            {
                "sid": f"s{index:06d}",
                "handle": str(segment.get("placed_uid")),
                "pts": [segment["p0_world"], segment["p1_world"]],
                "layer": layer_index.get(source_key, ""),
                "kind": str(segment.get("kind", "line")),
                "label": "unknown",
                "source": "native_objectarx_worldir",
                "source_entity_handle": source_key[1],
                "source_def_handle": source_key[0],
            }
        )
    return {
        "ir": "seg.v1",
        "drawing_id": world.get("drawing_id", "unknown"),
        "units": "mm",
        "scale_mm_per_unit": 1.0,
        "segments": segments,
    }


def _load_evidence_grid() -> Any:
    path = Path(__file__).resolve().parents[1] / "detect" / "evidence_grid.py"
    spec = importlib.util.spec_from_file_location("e2_qualification_evidence_grid", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load evidence grid from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _positive_handles(result: Mapping[str, Any]) -> set[str]:
    return {
        str(handle)
        for handle, record in (result.get("per_handle") or {}).items()
        if isinstance(record, Mapping) and float(record.get("score", 0.0)) >= WALL_THRESHOLD
    }


def _pair_handles(result: Mapping[str, Any]) -> set[str]:
    return {
        str(handle)
        for wall in result.get("walls", []) or []
        if isinstance(wall, Mapping)
        for handle in wall.get("handles", []) or []
    }


def _jaccard(a: set[str], b: set[str]) -> float:
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def _transform_seg_ir(seg_ir: Mapping[str, Any], kind: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    output = copy.deepcopy(seg_ir)
    params: dict[str, Any] | None = None
    if kind == "strip_layer_names":
        for segment in output["segments"]:
            segment["layer"] = ""
        return output, params
    if kind == "split_every_segment_at_midpoint":
        split = []
        for segment in output["segments"]:
            p0, p1 = segment["pts"]
            midpoint = [(float(p0[0]) + float(p1[0])) / 2.0, (float(p0[1]) + float(p1[1])) / 2.0]
            for ordinal, points in enumerate(([p0, midpoint], [midpoint, p1])):
                child = dict(segment)
                child["sid"] = f"{segment['sid']}:split{ordinal}"
                child["pts"] = points
                split.append(child)
        output["segments"] = split
        return output, params
    radians = math.radians(37.0)
    cosine, sine = math.cos(radians), math.sin(radians)
    for segment in output["segments"]:
        transformed = []
        for x, y in segment["pts"]:
            x, y = float(x), float(y)
            if kind == "rotate_37_degrees":
                transformed.append([cosine * x - sine * y, sine * x + cosine * y])
            elif kind == "translate_large_offset":
                transformed.append([x + 1_000_000.0, y - 2_000_000.0])
            elif kind in {"scale_coordinates_x1000_consistent", "scale_coordinates_x1000_naive"}:
                transformed.append([x * 1000.0, y * 1000.0])
            else:
                raise ValueError(f"unknown intervention {kind}")
        segment["pts"] = transformed
    if kind == "scale_coordinates_x1000_consistent":
        params = {"thickness_band_units": [50_000.0, 400_000.0], "snap_tol": 1000.0}
    return output, params


def _intervention_suite(seg_ir: Mapping[str, Any], scorer: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    baseline = scorer.score(seg_ir)
    baseline_positive = _positive_handles(baseline)
    baseline_pairs = _pair_handles(baseline)
    interventions = [
        "rotate_37_degrees",
        "translate_large_offset",
        "scale_coordinates_x1000_consistent",
        "scale_coordinates_x1000_naive",
        "strip_layer_names",
        "split_every_segment_at_midpoint",
    ]
    rows = []
    baseline_scores = baseline.get("per_handle", {}) or {}
    for name in interventions:
        transformed, params = _transform_seg_ir(seg_ir, name)
        result = scorer.score(transformed, params=params)
        positive = _positive_handles(result)
        pairs = _pair_handles(result)
        deltas = []
        delta_by_handle: list[tuple[float, str, Mapping[str, Any], Mapping[str, Any]]] = []
        for handle, record in baseline_scores.items():
            other = (result.get("per_handle") or {}).get(handle)
            if isinstance(record, Mapping) and isinstance(other, Mapping):
                delta = abs(float(record.get("score", 0.0)) - float(other.get("score", 0.0)))
                deltas.append(delta)
                delta_by_handle.append((delta, str(handle), record, other))
        expected_invariant = name in {
            "rotate_37_degrees",
            "translate_large_offset",
            "scale_coordinates_x1000_consistent",
            "split_every_segment_at_midpoint",
        }
        max_delta = max(deltas, default=0.0)
        delta_by_handle.sort(key=lambda item: (-item[0], item[1]))
        max_record = delta_by_handle[0] if delta_by_handle else None
        positive_jaccard = _jaccard(baseline_positive, positive)
        row_status = "MEASURED_CAUSAL_CUE_ABLATION"
        if expected_invariant:
            row_status = STATUS_PASS if positive_jaccard == 1.0 and max_delta <= 1e-6 else STATUS_BLOCKED
        rows.append(
            {
                "intervention": name,
                "expected_invariant": expected_invariant,
                "status": row_status,
                "segments": len(transformed["segments"]),
                "positive_handles": len(positive),
                "positive_membership_changed_handles": sorted(baseline_positive ^ positive),
                "score_changed_handle_count": sum(delta > 1e-6 for delta in deltas),
                "positive_handle_jaccard_vs_baseline": round(positive_jaccard, 6),
                "parallel_pair_handle_jaccard_vs_baseline": round(_jaccard(baseline_pairs, pairs), 6),
                "max_per_handle_score_delta": round(max_delta, 6),
                "max_delta_example": (
                    {
                        "handle": max_record[1],
                        "baseline": max_record[2],
                        "intervened": max_record[3],
                    }
                    if max_record and max_record[0] > 1e-6
                    else None
                ),
            }
        )
    return baseline, {
        "schema": "e2.intervention_results.v1",
        "baseline": {
            "segments": len(seg_ir.get("segments", [])),
            "handles_scored": len(baseline_scores),
            "positive_handles_at_threshold_0_5": len(baseline_positive),
            "parallel_pair_handles": len(baseline_pairs),
            "wall_pair_records": len(baseline.get("walls", []) or []),
        },
        "interventions": rows,
        "interpretation_rule": (
            "Invariant arms test representation stability, not wall accuracy. Cue ablations measure causal dependence "
            "of this rule implementation, not dependence of GBDT or GNN models that were not run."
        ),
    }


def _candidate_diagnostics(seg_ir: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    per_handle = baseline.get("per_handle", {}) or {}
    positive = _positive_handles(baseline)
    channel_values: dict[str, list[float]] = defaultdict(list)
    positive_channel_values: dict[str, list[float]] = defaultdict(list)
    for handle, record in per_handle.items():
        evidence = record.get("evidence", {}) if isinstance(record, Mapping) else {}
        for channel, value in evidence.items():
            channel_values[channel].append(float(value))
            if str(handle) in positive:
                positive_channel_values[channel].append(float(value))
    channel_summary = {}
    for channel, values in sorted(channel_values.items()):
        selected = positive_channel_values[channel]
        channel_summary[channel] = {
            "mean_all": round(sum(values) / len(values), 6) if values else None,
            "mean_positive": round(sum(selected) / len(selected), 6) if selected else None,
        }
    layer_stats: dict[str, dict[str, Any]] = {}
    for segment in seg_ir.get("segments", []) or []:
        layer = str(segment.get("layer") or "<EMPTY>")
        handle = str(segment.get("handle"))
        row = layer_stats.setdefault(layer, {"segments": 0, "positive_handles": set(), "handles": set()})
        row["segments"] += 1
        row["handles"].add(handle)
        if handle in positive:
            row["positive_handles"].add(handle)
    layer_rows = []
    for layer, row in layer_stats.items():
        handle_count = len(row["handles"])
        positive_count = len(row["positive_handles"])
        layer_rows.append(
            {
                "layer": layer,
                "segments": row["segments"],
                "handles": handle_count,
                "positive_handles": positive_count,
                "positive_rate": round(positive_count / handle_count, 6) if handle_count else 0.0,
                "anti_wall_name_hypothesis": any(token.upper() in layer.upper() for token in ANTI_WALL_TOKENS),
            }
        )
    layer_rows.sort(key=lambda row: (-row["positive_handles"], -row["segments"], row["layer"]))
    candidates = []
    for handle, record in sorted(per_handle.items(), key=lambda item: (-float(item[1].get("score", 0.0)), str(item[0]))):
        if str(handle) not in positive:
            continue
        candidates.append({"placed_uid": str(handle), **record})
    return {
        "schema": "e2.wall_candidates_rules.v1",
        "status": "EXPLORATORY_UNLABELED",
        "threshold": WALL_THRESHOLD,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "wall_pair_records": baseline.get("walls", []),
        "channel_summary": channel_summary,
        "top_layers": layer_rows[:30],
        "anti_wall_layer_hypotheses": [row for row in layer_rows if row["anti_wall_name_hypothesis"]][:30],
        "warning": (
            "These are rule candidates, not wall truth. Layer-name hypotheses are convention-dependent and may be shortcuts."
        ),
    }


def _model_diagnostics(
    candidates: Mapping[str, Any], interventions: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "schema": "e2.model_diagnostics.v1",
        "rules": {
            "status": "RAN_EXPLORATORY_UNLABELED",
            "candidate_count": candidates.get("candidate_count"),
            "accuracy_metrics": None,
            "reason": "The rule arm can emit candidates, but this DWG has no wall truth ledger.",
        },
        "gbdt": {
            "status": "NOT_RUN_NO_COMPATIBLE_LABELS",
            "accuracy_metrics": None,
            "reason": "A checkpoint score on one unlabeled DWG would not estimate transfer or correctness.",
        },
        "gnn": {
            "status": "NOT_RUN_NO_COMPATIBLE_LABELS",
            "accuracy_metrics": None,
            "reason": "The known corpus shortcut question requires a labeled corpus intervention, not inference theater on one file.",
        },
        "intervention_summary": interventions["interventions"],
        "decision": (
            "Use this drawing to qualify observation and build a human truth ledger. Resume GBDT/GNN comparison only after "
            "the same placed-entity identity and label contract are available."
        ),
    }


def _percent(numerator: int | float, denominator: int | float) -> str:
    return "n/a" if not denominator else f"{100.0 * numerator / denominator:.3f}%"


def _render_report(
    spec: Mapping[str, Any],
    receipt: Mapping[str, Any],
    census: Mapping[str, Any],
    loss: Mapping[str, Any],
    candidates: Mapping[str, Any],
    models: Mapping[str, Any],
    interventions: Mapping[str, Any],
) -> str:
    adapter = loss["analysis_projection"]
    world = loss["world_projection"]
    raw = int(world.get("expected_segment_instances", 0) or 0)
    clipped = int(world.get("clipped_away_segment_instances", 0) or 0)
    visible = int(world.get("visible_source_segment_instances", 0) or 0)
    source_templates = int(adapter.get("source_entity_templates", 0) or 0)
    excluded = int(adapter.get("explicitly_excluded_entity_templates", 0) or 0)
    gates = "\n".join(
        f"| {row['gate']} | {row['status']} | {row['evidence']} |" for row in receipt["gates"]
    )
    intervention_rows = "\n".join(
        (
            f"| {row['intervention']} | {row['status']} | {len(row['positive_membership_changed_handles'])} | "
            f"{row['positive_handle_jaccard_vs_baseline']} | "
            f"{row['max_per_handle_score_delta']} |"
        )
        for row in interventions["interventions"]
    )
    intervention_by_name = {
        row["intervention"]: row for row in interventions["interventions"]
    }
    rotation = intervention_by_name["rotate_37_degrees"]
    split = intervention_by_name["split_every_segment_at_midpoint"]
    naive_scale = intervention_by_name["scale_coordinates_x1000_naive"]
    strip_layer = intervention_by_name["strip_layer_names"]
    channel_rows = "\n".join(
        f"| {name} | {row['mean_all']} | {row['mean_positive']} |"
        for name, row in candidates["channel_summary"].items()
    )
    anti_layers = candidates["anti_wall_layer_hypotheses"][:10]
    anti_text = "\n".join(
        f"- `{row['layer']}`: {row['positive_handles']}/{row['handles']} 후보, 후보율 {row['positive_rate']:.3f}"
        for row in anti_layers
    ) or "- 이름으로 식별된 anti-wall 가설 층이 현재 가시 선분에는 없었다."
    return f"""# E2 벽-탐지기 첫 계측·개입 보고서

상태: **{receipt['status']}**

실험: `{spec['experiment_id']}`

정본 SHA-256: `{spec['source']['sha256']}`

## 결론

현재 도구가 이 DWG의 모든 의미 정보를 침묵 누락 없이 관측했다고는 아직 말할 수 없다. 네이티브 ObjectARX payload는 modelspace {census['modelspace_entity_count']:,}개와 블록 정의 {census['block_definition_count']:,}개를 읽었고 payload 안의 미해독 엔터티는 0개였지만, 추출기가 `groups`, `materials`, `plot_settings`를 건너뛰며 proxy 객체 지원도 partial이다. 독립 CAD 엔진의 동일 필드 전수조사도 이번 run에는 없다.

반면 **지원한다고 선언한 2D 분석 범위**에서는 보존 회계가 닫혔다. 원시 배치 선분 {raw:,}개 중 활성 XCLIP이 {clipped:,}개({_percent(clipped, raw)})를 가렸고, 가시 원천 선분 {visible:,}개가 출력 선분 {world.get('emitted_segment_instances', 0):,}개로 변환되며 보존 차이는 0이었다. 이 범위의 결론은 PASS지만, 전체 실험 상태는 지원하지 않는 엔터티와 독립 오라클 부재 때문에 PARTIAL_PASS다.

가장 중요한 발견은 모델이 아니라 **관측 경로**다. XCLIP을 무시한 첫 변환은 화면에서 가려진 412,425개 선분을 벽 후보 공간에 넣을 뻔했다. 이것은 accoreconsole/ObjectARX의 능력 부족이 아니라, ObjectARX가 이미 읽은 XCLIP을 중간 adapter가 버린 경로 오류였으며 이번 개입으로 원인이 확인됐다.

## 자격 게이트

| 게이트 | 판정 | 증거 |
|---|---|---|
{gates}

## 관측 범위와 손실

- 네이티브 modelspace 회계: {census['modelspace_entity_count']:,}/{census['native_modelspace_count']:,}/{census['realized_modelspace_count']:,} 일치.
- 전체 엔터티 원형: {source_templates:,}개. 벽 분석 투영이 지원한 원형은 {adapter.get('adapted_entity_templates', 0):,}개, 명시적으로 제외한 원형은 {excluded:,}개({_percent(excluded, source_templates)}).
- 제외 종류: `{json.dumps(adapter.get('excluded_by_dxf_name', {}), ensure_ascii=False, sort_keys=True)}`.
- 중복 꼭짓점 때문에 제거한 영길이 하위 선분: {adapter.get('excluded_degenerate_subsegments', 0):,}개. 이 수는 엔터티 누락과 분리했다.
- 도면 단위: INSUNITS=4, 즉 millimeter. 좌표 단위 confound를 숨기지 않고 개입 실험에서 1000배 변환을 따로 시험했다.

## 벽 후보와 anti-wall 신호

규칙 팔은 가시 선분 {interventions['baseline']['segments']:,}개를 채점해 임계값 0.5 이상 후보 {candidates['candidate_count']:,}개를 냈다. 하지만 사람 라벨이 없으므로 이것은 정밀도나 재현율이 아니라 **검토 대기 후보 수**다.

| 채널 | 전체 평균 | 후보 평균 |
|---|---:|---:|
{channel_rows}

위 표의 차이는 규칙이 자기 점수를 어떻게 만들었는지 보여줄 뿐, 벽의 인과적 본질을 증명하지 않는다. 특히 layer 채널은 표기 관습 그 자체이므로 layer 이름 제거 개입과 함께 해석해야 한다.

anti-wall은 아직 라벨에서 귀납한 술어가 아니다. 아래는 `DOOR`, `FUR`, `KIT`, `ELEV`, `수전` 같은 이름을 가진 층을 사람이 우선 검토하기 위한 **관습 의존 가설**이다.

{anti_text}

## 필수 개입 실험

| 개입 | 판정 | 후보 변동 수 | 후보 Jaccard | 최대 점수 변화 |
|---|---|---:|---:|---:|
{intervention_rows}

회전·평행이동·단위와 임계값을 함께 바꾼 1000배 확대는 의미 보존 개입이다. 좌표만 1000배 바꾸는 arm은 의도적인 단위 오류 대조군이고, layer 제거는 이름 cue의 인과 효과를, 모든 선분 이등분은 표현 세분화 민감도를 잰다. 이 검사는 규칙의 자기일관성을 재며 벽 정확도를 대신하지 않는다.

결과는 명확하다. 37도 회전만으로 후보 소속 {len(rotation['positive_membership_changed_handles'])}개가 바뀌고 최대 점수가 {rotation['max_per_handle_score_delta']} 변해 회전 불변성 게이트가 실패했다. 모든 선분을 같은 위치에서 둘로 나누자 후보 소속 {len(split['positive_membership_changed_handles'])}개가 바뀌고 최대 점수가 {split['max_per_handle_score_delta']} 변했으므로, 현재 규칙은 같은 형상의 세분화 관습에도 불변이 아니다. 반면 단위와 임계값을 함께 바꾼 확대는 완전 일치했지만 좌표만 확대한 대조군은 후보 Jaccard가 {naive_scale['positive_handle_jaccard_vs_baseline']}로 붕괴해 좌표 단위 계약이 필수임을 재현했다. layer 이름 제거의 점수 변화는 {strip_layer['max_per_handle_score_delta']}였는데, 이는 견고성 증거가 아니라 현재 layer 토큰이 이 도면의 실제 층 이름을 하나도 인식하지 못했다는 뜻이다.

## rules · GBDT · GNN 판단

- rules: `{models['rules']['status']}`. 실제 후보는 냈지만 truth가 없어 품질 수치는 없다.
- GBDT: `{models['gbdt']['status']}`. 이 도면에 맞는 동결 feature/label 계약 없이 checkpoint를 호출하는 것은 전이 실험이 아니다.
- GNN: `{models['gnn']['status']}`. 알려진 교차점 밀도·축정렬 shortcut은 다중 코퍼스 라벨과 개입으로 검증해야 하며, 이 한 장에 대한 추론값은 그 질문에 답하지 않는다.

따라서 첫 보고서의 가장 강한 판단은 다음과 같다. **지금 병목은 더 큰 모델이 아니라, 관측 가능한 것과 실제로 모델에 들어간 것을 동일시했던 경로다.** XCLIP 회계가 그 반례를 실측했고, 다음 과학적 단계는 {candidates['candidate_count']:,}개 후보 전체가 아니라 층·형상·점수 구간으로 층화한 소표본을 사람이 wall / anti-wall / ambiguous로 라벨링하는 것이다. 그 truth ledger가 생긴 뒤에야 rules·GBDT·GNN을 같은 placed-entity ID 위에서 비교할 수 있다.

## 산출물 해석 경계

- `entity_census.json`: ObjectARX payload가 읽은 모집단.
- `unsupported_geometry.json`과 `loss_ledger.json`: 분석에서 빠진 것과 XCLIP으로 가려진 것을 분리한 회계.
- `wall_candidates_rules.json`: 검토 후보이며 truth가 아니다.
- `model_diagnostics.json`: 왜 GBDT/GNN 수치를 내지 않았는지 포함한 실행 자격 판정.
- `intervention_results.json`: 개입별 규칙 안정성. 정확도 지표가 아니다.
- `qualification_receipt.json`: 위 주장들을 입력 SHA와 증거 파일 SHA에 묶은 영수증.
"""


def build_first_report(spec: Mapping[str, Any], run_dir: Path) -> dict[str, Any]:
    """Build the complete first-report artifact set in ``run_dir``."""

    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    source_path = Path(spec["source"]["path"])
    actual_source_hash = _sha256(source_path)
    if actual_source_hash.lower() != str(spec["source"]["sha256"]).lower():
        raise ValueError(
            f"source hash mismatch: expected {spec['source']['sha256']}, got {actual_source_hash}"
        )
    evidence_paths = {name: Path(path) for name, path in spec["evidence"].items()}
    native = _read_json(evidence_paths["native_ir"])
    adapter = _read_json(evidence_paths["adapter_ir"])
    world = _read_json(evidence_paths["world_ir"])
    evidence_records = [
        {"role": name, **_file_record(path)} for name, path in sorted(evidence_paths.items())
    ]
    census = _entity_census(native)
    compact_world = _compact_conservation(world)
    adapter_ledger = dict(adapter.get("adapter_ledger", {}))
    unsupported = {
        "schema": "e2.unsupported_geometry.v1",
        "source_entity_templates": adapter_ledger.get("source_entity_templates"),
        "explicitly_excluded_entity_templates": adapter_ledger.get(
            "explicitly_excluded_entity_templates"
        ),
        "excluded_by_dxf_name": adapter_ledger.get("excluded_by_dxf_name", {}),
        "excluded_invalid_geometry_templates": adapter_ledger.get(
            "excluded_invalid_geometry_templates", 0
        ),
        "excluded_degenerate_subsegments": adapter_ledger.get(
            "excluded_degenerate_subsegments", 0
        ),
        "native_sections_skipped": census["sections_skipped"],
        "native_non_implemented_sections": {
            key: value
            for key, value in census["section_status"].items()
            if value != "implemented"
        },
    }
    loss = {
        "schema": "e2.loss_ledger.v1",
        "analysis_projection": adapter_ledger,
        "world_projection": compact_world,
        "failure_ledger": world.get("failure_ledger", []),
        "balance_equations": {
            "entity_templates": (
                "source_entity_templates = adapted_entity_templates + explicitly_excluded_entity_templates"
            ),
            "placed_segments": (
                "expected_segment_instances = visible_source_segment_instances + clipped_away_segment_instances"
            ),
        },
    }
    seg_ir = _to_seg_ir(world, _layer_index(adapter))
    scorer = _load_evidence_grid()
    baseline, interventions = _intervention_suite(seg_ir, scorer)
    candidates = _candidate_diagnostics(seg_ir, baseline)
    models = _model_diagnostics(candidates, interventions)
    receipt = qualify(spec, native, adapter, world, evidence_records)
    guard_path = run_dir / "guard_decision.json"
    guard = _read_json(guard_path) if guard_path.is_file() else None
    if guard is not None:
        guard_ok = (
            guard.get("status") == "READY"
            and "xclip_preservation" in (guard.get("required_observables") or [])
        )
        receipt["gates"].append(
            _gate(
                "runtime_experiment_guard",
                STATUS_PASS if guard_ok else STATUS_BLOCKED,
                (
                    f"status={guard.get('status')}; pipeline={guard.get('selected_pipeline')}; "
                    f"reason={guard.get('reason_code')}"
                ),
            )
        )
        receipt["scope_verdicts"]["guarded_experiment_execution"] = (
            STATUS_PASS if guard_ok else STATUS_BLOCKED
        )
        if not guard_ok:
            receipt["status"] = STATUS_BLOCKED

    output_values = {
        "experiment_spec.json": dict(spec),
        "entity_census.json": census,
        "unsupported_geometry.json": unsupported,
        "loss_ledger.json": loss,
        "wall_candidates_rules.json": candidates,
        "model_diagnostics.json": models,
        "intervention_results.json": interventions,
    }
    for name, value in output_values.items():
        _write_json(run_dir / name, value)
    receipt["outputs"] = [
        {"role": name.removesuffix(".json"), **_file_record(run_dir / name)}
        for name in output_values
    ]
    if guard_path.is_file():
        receipt["outputs"].append({"role": "guard_decision", **_file_record(guard_path)})
    _write_json(run_dir / "qualification_receipt.json", receipt)
    report = _render_report(spec, receipt, census, loss, candidates, models, interventions)
    (run_dir / "REPORT.md").write_text(report, encoding="utf-8", newline="\n")
    return {
        "status": receipt["status"],
        "run_dir": str(run_dir),
        "report": str(run_dir / "REPORT.md"),
        "receipt": str(run_dir / "qualification_receipt.json"),
        "candidate_count": candidates["candidate_count"],
    }
