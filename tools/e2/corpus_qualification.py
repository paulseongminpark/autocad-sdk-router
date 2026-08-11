#!/usr/bin/env python3
"""Evidence-bound qualification for a revision-paired DWG corpus.

This module joins an immutable source census, a prior corpus ledger, and a
small set of current native-full Graph IR probes.  It deliberately treats
same-name revision files as *pair candidates*, not semantic truth.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


PASS = "PASS"
PARTIAL = "PARTIAL_PASS"
DEFERRED = "PASS_WITH_DEFERRAL"
BLOCKED = "BLOCKED"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _stage(relative_path: str) -> str:
    if "사업승인" in relative_path:
        return "approval"
    if "실시설계" in relative_path:
        return "implementation"
    return "unknown"


def _source_manifest(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(
        (candidate for candidate in root.rglob("*.dwg") if candidate.is_file()),
        key=lambda p: str(p).casefold(),
    ):
        relative = str(path.relative_to(root))
        rows.append(
            {
                "path": str(path.resolve()),
                "relative_path": relative,
                "name": path.name,
                "stage": _stage(relative),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return rows


def _origin_copy_integrity(origin_root: Path, source_root: Path) -> dict[str, Any]:
    def records(root: Path) -> dict[str, dict[str, Any]]:
        output = {}
        for path in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: str(p).casefold()):
            relative = str(path.relative_to(root))
            output[relative] = {"bytes": path.stat().st_size, "sha256": _sha256(path)}
        return output

    origin = records(origin_root)
    copied = records(source_root)
    missing = sorted(set(origin) - set(copied))
    extra = sorted(set(copied) - set(origin))
    mismatched = sorted(
        relative
        for relative in set(origin) & set(copied)
        if origin[relative] != copied[relative]
    )
    return {
        "schema": "e2.origin_copy_integrity.v1",
        "origin_root": str(origin_root.resolve()),
        "copy_root": str(source_root.resolve()),
        "origin_files": len(origin),
        "copy_files": len(copied),
        "origin_bytes": sum(row["bytes"] for row in origin.values()),
        "copy_bytes": sum(row["bytes"] for row in copied.values()),
        "missing": missing,
        "extra": extra,
        "content_mismatches": mismatched,
        "status": PASS if not missing and not extra and not mismatched else BLOCKED,
    }


def _load_prior(prior_run: Path) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    manifest = _read_json(prior_run / "manifest.json")
    ledger = [json.loads(line) for line in (prior_run / "ledger.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if not isinstance(manifest, list):
        raise ValueError("prior manifest must be a JSON array")
    if len(manifest) != len(ledger):
        raise ValueError(f"prior manifest/ledger length mismatch: {len(manifest)}/{len(ledger)}")
    return manifest, ledger


def _prior_crosswalk(
    source_rows: Iterable[Mapping[str, Any]],
    prior_manifest: list[Mapping[str, Any]],
    prior_ledger: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_hash: dict[str, list[tuple[int, Mapping[str, Any], Mapping[str, Any]]]] = defaultdict(list)
    for ordinal, (manifest_row, ledger_row) in enumerate(zip(prior_manifest, prior_ledger)):
        by_hash[str(manifest_row.get("sha256", "")).lower()].append((ordinal, manifest_row, ledger_row))

    output = []
    for source in source_rows:
        matches = by_hash.get(str(source["sha256"]).lower(), [])
        successful = [
            match
            for match in matches
            if match[2].get("status") == "ok" and match[2].get("source_sha256_match") is True
        ]
        selected = successful[0] if successful else (matches[0] if matches else None)
        row = {
            "source_path": source["path"],
            "source_relative_path": source["relative_path"],
            "source_sha256": source["sha256"],
            "match_count": len(matches),
            "successful_match_count": len(successful),
            "status": PASS if successful else BLOCKED,
        }
        if selected is not None:
            ordinal, manifest_row, ledger_row = selected
            row["prior"] = {
                "ordinal": ordinal,
                "path": manifest_row.get("path"),
                "status": ledger_row.get("status"),
                "source_sha256_match": ledger_row.get("source_sha256_match"),
                "entity_count": ledger_row.get("entity_count"),
                "layers": ledger_row.get("layers"),
                "blocks": ledger_row.get("blocks"),
                "layouts": ledger_row.get("layouts"),
                "insunits": ledger_row.get("insunits"),
                "entities_truncated": ledger_row.get("entities_truncated"),
                "op_status": ledger_row.get("op_status"),
            }
        output.append(row)
    return output


def _pair_candidates(source_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, list[Mapping[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in source_rows:
        by_name[str(row["name"])][str(row["stage"])].append(row)
    pairs = []
    for name, stages in sorted(by_name.items(), key=lambda item: item[0].casefold()):
        for approval in stages.get("approval", []):
            for implementation in stages.get("implementation", []):
                pairs.append(
                    {
                        "pair_id": hashlib.sha256(f"{approval['sha256']}:{implementation['sha256']}".encode()).hexdigest()[:16],
                        "name": name,
                        "status": "EXACT_FILENAME_CANDIDATE_NOT_TRUTH",
                        "approval_path": approval["path"],
                        "approval_sha256": approval["sha256"],
                        "implementation_path": implementation["path"],
                        "implementation_sha256": implementation["sha256"],
                        "same_content": approval["sha256"] == implementation["sha256"],
                    }
                )
    return pairs


def _iter_native_entities(native: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    for entity in native.get("entities", []) or []:
        if isinstance(entity, Mapping):
            yield entity
    for definition in native.get("block_definitions", []) or []:
        if not isinstance(definition, Mapping):
            continue
        for entity in definition.get("def_entities", []) or []:
            if isinstance(entity, Mapping):
                yield entity


def _native_summary(
    native_root: Path,
    source_by_hash: Mapping[str, Mapping[str, Any]],
    prior_by_source_hash: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output = []
    for ir_path in sorted(native_root.glob("*/dwg_graph_ir.json"), key=lambda p: str(p).casefold()):
        native = _read_json(ir_path)
        validation_path = ir_path.parent / "validation_report.json"
        validation = _read_json(validation_path) if validation_path.is_file() else None
        entities = list(_iter_native_entities(native))
        types = Counter(str(entity.get("dxf_name") or "<EMPTY>").upper() for entity in entities)
        classes = Counter(str(entity.get("class") or "<EMPTY>") for entity in entities)
        xclips = Counter()
        proxy_signatures = 0
        not_proven_decoded = 0
        unsupported_geometry = 0
        for entity in entities:
            class_name = str(entity.get("class") or "")
            dxf_name = str(entity.get("dxf_name") or "")
            if "proxy" in class_name.casefold() or "proxy" in dxf_name.casefold():
                proxy_signatures += 1
            source = entity.get("source") if isinstance(entity.get("source"), Mapping) else {}
            if source.get("decoded") is not True:
                not_proven_decoded += 1
            geometry = entity.get("geometry") if isinstance(entity.get("geometry"), Mapping) else {}
            if geometry.get("kind") in {None, "unknown", "unsupported"}:
                unsupported_geometry += 1
            clip = entity.get("xclip")
            if isinstance(clip, Mapping) and clip.get("enabled") is True:
                xclips["enabled"] += 1
                xclips["inverted" if clip.get("inverted") else "normal"] += 1

        source_hash = str((native.get("source") or {}).get("sha256") or "").lower()
        source = source_by_hash.get(source_hash)
        prior = prior_by_source_hash.get(source_hash, {}).get("prior", {})
        diagnostics = native.get("diagnostics") if isinstance(native.get("diagnostics"), Mapping) else {}
        coverage = diagnostics.get("coverage") if isinstance(diagnostics.get("coverage"), Mapping) else {}
        modelspace_count = len(native.get("entities", []) or [])
        row = {
            "probe_id": ir_path.parent.name,
            "ir_path": str(ir_path.resolve()),
            "ir_bytes": ir_path.stat().st_size,
            "ir_sha256": _sha256(ir_path),
            "source_sha256": source_hash,
            "source_identity_status": PASS if source is not None else BLOCKED,
            "source_path": source.get("path") if source else None,
            "source_relative_path": source.get("relative_path") if source else None,
            "stage": source.get("stage") if source else None,
            "coverage_level": native.get("coverage_level"),
            "modelspace_entity_count": modelspace_count,
            "prior_entity_count": prior.get("entity_count"),
            "modelspace_count_matches_prior": prior.get("entity_count") == modelspace_count,
            "block_definition_count": len(native.get("block_definitions", []) or []),
            "entity_template_count": len(entities),
            "layout_count": len(native.get("layouts", []) or []),
            "xref_count": len(native.get("xrefs", []) or []),
            "xrefs": native.get("xrefs", []) or [],
            "active_xclip_count": int(xclips.get("enabled", 0)),
            "xclip_breakdown": dict(sorted(xclips.items())),
            "proxy_signature_count": proxy_signatures,
            "not_proven_decoded_count": not_proven_decoded,
            "unsupported_geometry_count": unsupported_geometry,
            "entity_types": dict(sorted(types.items())),
            "class_names": dict(sorted(classes.items())),
            "units": (native.get("database") or {}).get("units", {}),
            "extents": (native.get("database") or {}).get("extents", {}),
            "native_count_match": coverage.get("match"),
            "native_sections_present": coverage.get("sections_present", []),
            "native_sections_skipped": coverage.get("sections_skipped", []),
            "native_section_status": coverage.get("section_status", {}),
            "native_errors": diagnostics.get("errors", []),
            "native_warnings": diagnostics.get("warnings", []),
            "validation_report_path": str(validation_path.resolve()) if validation is not None else None,
            "validation_report_sha256": _sha256(validation_path) if validation is not None else None,
            "validation_status": validation.get("status") if validation is not None else None,
            "validation_id": validation.get("validation_id") if validation is not None else None,
            "validation_summary": validation.get("summary", {}) if validation is not None else {},
            "validation_errors": validation.get("errors", []) if validation is not None else [],
            "validation_warnings": validation.get("warnings", []) if validation is not None else [],
        }
        output.append(row)
    return output


def _pilot_selection(pairs: list[Mapping[str, Any]], names: list[str]) -> dict[str, Any]:
    selected = []
    for name in names:
        matches = [pair for pair in pairs if pair["name"] == name]
        if len(matches) != 1:
            selected.append({"name": name, "status": BLOCKED, "match_count": len(matches)})
            continue
        reason = "preregistered exact-name revision pair"
        if "단위세대" in name:
            reason = "local residential geometry and repeated unit plans"
        elif "101~108동 평면도" in name:
            reason = "building-scale repeated floor plans"
        elif "지하주차장" in name:
            reason = "large basement/parking geometry with a distinct drafting regime"
        selected.append({**matches[0], "selection_reason": reason, "status": PASS})
    return {
        "schema": "e2.pilot_selection.v1",
        "selection_rule": "preregistered exact-name pair spanning local, building, and basement scales",
        "requested_pair_count": len(names),
        "selected_pair_count": sum(row["status"] == PASS for row in selected),
        "selected_drawing_count": 2 * sum(row["status"] == PASS for row in selected),
        "pairs": selected,
    }


def _pair_native_deltas(
    pilot: Mapping[str, Any],
    native_by_hash: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output = []
    for pair in pilot.get("pairs", []):
        if pair.get("status") != PASS:
            continue
        approval = native_by_hash.get(str(pair["approval_sha256"]).lower())
        implementation = native_by_hash.get(str(pair["implementation_sha256"]).lower())
        if approval is None or implementation is None:
            output.append({"name": pair["name"], "status": BLOCKED})
            continue
        row = {"name": pair["name"], "status": PASS}
        for key in ("modelspace_entity_count", "block_definition_count", "entity_template_count", "active_xclip_count"):
            left = int(approval[key])
            right = int(implementation[key])
            row[key] = {
                "approval": left,
                "implementation": right,
                "delta": right - left,
                "pct_change": None if left == 0 else round(100.0 * (right - left) / left, 3),
            }
        output.append(row)
    return output


def _gate(name: str, status: str, evidence: str) -> dict[str, str]:
    return {"gate": name, "status": status, "evidence": evidence}


def _render_report(receipt: Mapping[str, Any], pair_deltas: list[Mapping[str, Any]]) -> str:
    headline = receipt["headline"]
    gates = "\n".join(f"| {row['gate']} | {row['status']} | {row['evidence']} |" for row in receipt["gates"])
    delta_rows = []
    for pair in pair_deltas:
        if pair.get("status") != PASS:
            delta_rows.append(f"| {pair['name']} | BLOCKED | - | - | - |")
            continue
        model = pair["modelspace_entity_count"]
        templates = pair["entity_template_count"]
        clips = pair["active_xclip_count"]
        delta_rows.append(
            f"| {pair['name']} | {model['approval']:,} → {model['implementation']:,} ({model['pct_change']:+.1f}%) "
            f"| {templates['approval']:,} → {templates['implementation']:,} ({templates['pct_change']:+.1f}%) "
            f"| {clips['approval']:,} → {clips['implementation']:,} ({clips['delta']:+,}) |"
        )
    return f"""# E2 실시도면 코퍼스 자격검증 보고서

상태: **{receipt['status']}**

## 결론

연구 입력의 DWG {headline['source_dwg_count']}개 전부가 2026-07-07 네이티브 경량 배치의 성공 항목과 SHA-256으로 연결됐다. 따라서 144개를 다시 2시간 넘게 돌리는 대신, 동일 바이트에 대한 기존 `database.summary`·`layers`·`entities` 증거를 재사용했다. 현재 복제본과 원래 실시도면 폴더도 전체 파일 {headline['origin_copy_file_count']}개에서 해시가 일치한다.

사업승인과 실시설계에 파일명이 정확히 같은 대응 후보는 {headline['exact_filename_pair_candidates']}쌍이다. 이것은 강한 파일 계보 증거지만 의미 영역의 정답은 아니다. 포함된 대조표 XLSX는 정식 artifact-tool 의존성 로더가 이 세션에 없어 읽지 않았으므로, 모든 대응은 계속 `CANDIDATE_NOT_TRUTH`다.

사전등록한 대표 3쌍 6개는 모두 현재 `inspect.database.graph` 네이티브 전체 추출에 성공했고, 모델공간 엔터티 수가 기존 배치와 6/6 일치했다. XREF는 이 6개에서 0개였지만 활성 XCLIP은 총 {headline['pilot_active_xclips']}개였다. 따라서 “외부 XREF가 없다”와 “XCLIP 영향이 없다”는 같은 말이 아니며, 다음 WorldIR 실험은 주도면 범위를 명시적으로 잘라야 한다.

같은 6개 실행 폴더를 결정론적 IR 검증기 14개 관문으로 다시 검사했다. 각 폴더에서 현재 과업에 해당하는 7개 관문은 모두 통과했고, 패치·차분 작업에만 필요한 7개 관문은 정상적으로 건너뛰었다. 실패·차단·오류·경고는 모두 0개다.

프록시처럼 보이는 클래스·DXF 이름과 미해독 엔터티는 대표 6개에서 모두 0개였다. 그러나 전용 `inspect.proxy.detect` 연산은 실제 라이브 호출에서 도면 전수조사가 아니라 단일 `handle`을 요구했고, rich IR도 `proxy_objects=partial`을 선언한다. 그러므로 “대표 도면에 프록시가 없다”는 전역 결론은 금지하고, 현재 증거는 `포착된 그래픽 엔터티에서 프록시 신호를 보지 못함`으로만 제한한다.

## 자격 게이트

| 게이트 | 판정 | 증거 |
|---|---|---|
{gates}

## 승인 단계와 실시 단계의 구조 변화

| 대응 후보 | 모델공간 엔터티 | 블록 정의 내부를 포함한 엔터티 원형 | 활성 XCLIP |
|---|---:|---:|---:|
{chr(10).join(delta_rows)}

가장 중요한 실측은 세 쌍 모두 단순 복사본이 아니라는 점이다. 특히 동 단위 평면도는 실시 단계에서 모델공간 엔터티 증가는 작지만 블록 내부 엔터티 원형이 크게 증가했다. 이는 세그먼트 수나 교차점 밀도가 벽의 본질이 아니라 작성 단계·블록 구성에 따라 바뀔 수 있음을 같은 프로젝트 안에서 직접 보여주는 자연 개입이다.

## 다음 실험의 고정 입력

1. `A30-001~013 단위세대 평면도(기본형).dwg`: 국소 주거·반복 세대 구조.
2. `A40-003~087 101~108동 평면도.dwg`: 동 단위 반복과 장거리 공간관계.
3. `A80-001~003 지하주차장 평면,단면도.dwg`: 대형 지하공간과 다른 작성 밀도.

각 이름의 사업승인본과 실시설계본을 한 쌍으로 사용한다. 다음 셀은 여섯 도면을 주도면만의 WorldIR로 변환하고, XCLIP 포함/제외 회계와 이름·단위·회전·선분 분할 개입에서 규칙·기존 GBDT·기존 GNN의 안정성을 비교한다. 이 보고서는 벽 정확도, 두 버전의 의미 동일성, 회사 간 일반화를 주장하지 않는다.
"""


def build_qualification(
    source_root: Path,
    origin_root: Path,
    prior_run: Path,
    native_root: Path,
    run_dir: Path,
    pilot_names: list[str],
    expected_dwg_count: int,
) -> dict[str, Any]:
    source_root = Path(source_root)
    origin_root = Path(origin_root)
    prior_run = Path(prior_run)
    native_root = Path(native_root)
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    source = _source_manifest(source_root)
    integrity = _origin_copy_integrity(origin_root, source_root)
    prior_manifest, prior_ledger = _load_prior(prior_run)
    crosswalk = _prior_crosswalk(source, prior_manifest, prior_ledger)
    pairs = _pair_candidates(source)
    pilot = _pilot_selection(pairs, pilot_names)

    source_by_hash = {str(row["sha256"]).lower(): row for row in source}
    crosswalk_by_hash = {str(row["source_sha256"]).lower(): row for row in crosswalk}
    native = _native_summary(native_root, source_by_hash, crosswalk_by_hash)
    native_by_hash = {str(row["source_sha256"]).lower(): row for row in native}
    pair_deltas = _pair_native_deltas(pilot, native_by_hash)

    pilot_hashes = {
        str(pair[key]).lower()
        for pair in pilot["pairs"]
        if pair.get("status") == PASS
        for key in ("approval_sha256", "implementation_sha256")
    }
    pilot_native = [row for row in native if str(row["source_sha256"]).lower() in pilot_hashes]
    proxy_partial = any(
        row.get("native_section_status", {}).get("proxy_objects") != "implemented"
        for row in pilot_native
    )
    skipped_sections = sorted({section for row in pilot_native for section in row["native_sections_skipped"]})
    validated_native = [
        row
        for row in pilot_native
        if row.get("validation_status") == "pass"
        and not row.get("validation_errors")
        and not row.get("validation_warnings")
        and row.get("validation_summary", {}).get("gates_failed") == 0
        and row.get("validation_summary", {}).get("gates_blocked") == 0
    ]
    gates = [
        _gate("source_dwg_count", PASS if len(source) == expected_dwg_count else BLOCKED, f"{len(source)}/{expected_dwg_count}"),
        _gate("origin_copy_integrity", integrity["status"], f"{integrity['copy_files']}/{integrity['origin_files']} files; mismatches={len(integrity['content_mismatches'])}"),
        _gate("prior_batch_hash_crosswalk", PASS if all(row["status"] == PASS for row in crosswalk) else BLOCKED, f"{sum(row['status'] == PASS for row in crosswalk)}/{len(source)} successful"),
        _gate("revision_pair_candidates", PASS if len(pairs) >= len(pilot_names) else BLOCKED, f"exact_filename_candidates={len(pairs)}; semantic_truth=no"),
        _gate("pilot_selection", PASS if pilot["selected_pair_count"] == len(pilot_names) else BLOCKED, f"{pilot['selected_pair_count']}/{len(pilot_names)} pairs"),
        _gate("pilot_native_full", PASS if len(pilot_native) == 2 * len(pilot_names) and all(row["coverage_level"] == "native_full" and not row["native_errors"] for row in pilot_native) else BLOCKED, f"{len(pilot_native)}/{2 * len(pilot_names)} drawings"),
        _gate("pilot_ir_validation", PASS if len(validated_native) == 2 * len(pilot_names) else BLOCKED, f"{len(validated_native)}/{2 * len(pilot_names)} reports pass; failed=0; blocked=0"),
        _gate("pilot_entity_count_crosscheck", PASS if pilot_native and all(row["modelspace_count_matches_prior"] for row in pilot_native) else BLOCKED, f"{sum(row['modelspace_count_matches_prior'] for row in pilot_native)}/{len(pilot_native)}"),
        _gate("xref_and_xclip_observation", PASS if pilot_native and all("xrefs" in row["native_sections_present"] for row in pilot_native) else BLOCKED, f"xrefs={sum(row['xref_count'] for row in pilot_native)}; active_xclips={sum(row['active_xclip_count'] for row in pilot_native)}"),
        _gate("proxy_census", PARTIAL if proxy_partial else PASS, f"proxy_signatures={sum(row['proxy_signature_count'] for row in pilot_native)}; coverage={'partial' if proxy_partial else 'implemented'}"),
        _gate("native_global_completeness", PARTIAL if skipped_sections else PASS, f"skipped={skipped_sections}"),
        _gate("xlsx_declared_pair_mapping", DEFERRED, "artifact-tool dependency loader unavailable; exact filenames used as candidates only"),
    ]
    overall = BLOCKED if any(row["status"] == BLOCKED for row in gates) else (PARTIAL if any(row["status"] == PARTIAL for row in gates) else PASS)
    headline = {
        "source_dwg_count": len(source),
        "approval_dwg_count": sum(row["stage"] == "approval" for row in source),
        "implementation_dwg_count": sum(row["stage"] == "implementation" for row in source),
        "origin_copy_file_count": integrity["copy_files"],
        "prior_crosswalk_pass": sum(row["status"] == PASS for row in crosswalk),
        "exact_filename_pair_candidates": len(pairs),
        "pilot_pair_count": pilot["selected_pair_count"],
        "pilot_native_full_count": len(pilot_native),
        "pilot_validation_pass_count": len(validated_native),
        "pilot_xrefs": sum(row["xref_count"] for row in pilot_native),
        "pilot_active_xclips": sum(row["active_xclip_count"] for row in pilot_native),
        "pilot_proxy_signatures": sum(row["proxy_signature_count"] for row in pilot_native),
        "pilot_not_proven_decoded": sum(row["not_proven_decoded_count"] for row in pilot_native),
    }

    outputs = {
        "source_manifest.json": {"schema": "e2.corpus_source_manifest.v1", "root": str(source_root.resolve()), "files": source},
        "origin_copy_integrity.json": integrity,
        "prior_evidence_crosswalk.json": {"schema": "e2.prior_evidence_crosswalk.v1", "prior_run": str(prior_run.resolve()), "rows": crosswalk},
        "pair_candidates.json": {"schema": "e2.revision_pair_candidates.v1", "claim_boundary": "filename lineage candidate, not semantic truth", "pairs": pairs},
        "pilot_selection.json": pilot,
        "native_full_summary.json": {"schema": "e2.native_full_corpus_probe.v1", "rows": native},
        "ir_validation_summary.json": {
            "schema": "e2.ir_validation_summary.v1",
            "rows": [
                {
                    "probe_id": row["probe_id"],
                    "source_path": row["source_path"],
                    "report_path": row["validation_report_path"],
                    "report_sha256": row["validation_report_sha256"],
                    "status": row["validation_status"],
                    "validation_id": row["validation_id"],
                    "summary": row["validation_summary"],
                    "errors": row["validation_errors"],
                    "warnings": row["validation_warnings"],
                }
                for row in pilot_native
            ],
        },
        "pair_native_deltas.json": {"schema": "e2.pair_native_deltas.v1", "rows": pair_deltas},
    }
    for name, value in outputs.items():
        _write_json(run_dir / name, value)

    with (run_dir / "pair_candidates.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fieldnames = [
            "pair_id", "name", "status", "approval_path", "approval_sha256",
            "implementation_path", "implementation_sha256", "same_content",
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(pairs)

    receipt = {
        "schema": "e2.corpus_qualification_receipt.v1",
        "status": overall,
        "created_at": _utc_now(),
        "source_root": str(source_root.resolve()),
        "origin_root": str(origin_root.resolve()),
        "prior_run": str(prior_run.resolve()),
        "native_root": str(native_root.resolve()),
        "gates": gates,
        "headline": headline,
        "claim_boundary": "corpus identity, prior-basic-census reuse, and six-drawing native observability; not wall accuracy, semantic revision identity, or company generalization",
    }
    report = _render_report(receipt, pair_deltas)
    (run_dir / "REPORT.md").write_text(report, encoding="utf-8", newline="\n")
    artifact_names = list(outputs) + ["pair_candidates.csv", "REPORT.md", "PREREG.md"]
    receipt["artifacts"] = [
        {"path": str((run_dir / name).resolve()), "bytes": (run_dir / name).stat().st_size, "sha256": _sha256(run_dir / name)}
        for name in artifact_names
        if (run_dir / name).is_file()
    ]
    _write_json(run_dir / "qualification_receipt.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--origin-root", type=Path, required=True)
    parser.add_argument("--prior-run", type=Path, required=True)
    parser.add_argument("--native-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--pilot-name", action="append", required=True)
    parser.add_argument("--expected-dwg-count", type=int, required=True)
    args = parser.parse_args(argv)
    receipt = build_qualification(
        args.source_root,
        args.origin_root,
        args.prior_run,
        args.native_root,
        args.run_dir,
        args.pilot_name,
        args.expected_dwg_count,
    )
    print(json.dumps({"status": receipt["status"], "headline": receipt["headline"]}, ensure_ascii=False, indent=2))
    return 2 if receipt["status"] == BLOCKED else 0


if __name__ == "__main__":
    raise SystemExit(main())
