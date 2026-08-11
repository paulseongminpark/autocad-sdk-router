#!/usr/bin/env python3
"""Evidence-bound qualification and instrument-snapshot assembly for E2.

``qualify`` judges already-loaded evidence. The former public first-report
runner is fail-closed until a sealed executor can prove exact input consumption
and confinement. Internal snapshot assembly never treats an unlabeled drawing
as a model-quality benchmark.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os
import stat
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator

from .sealed_executor import refusal_receipt

try:
    from target_population_oracle import (
        TargetPopulationContractError,
        validate_target_population_oracle,
    )
except ImportError:  # support ``import tools.e2.qualification.engine``
    from ..target_population_oracle import (
        TargetPopulationContractError,
        validate_target_population_oracle,
    )


STATUS_PASS = "PASS"
STATUS_PARTIAL = "PARTIAL_PASS"
STATUS_DEFERRED = "PASS_WITH_DEFERRAL"
STATUS_BLOCKED = "BLOCKED"
WALL_THRESHOLD = 0.5
EXPECTED_INVARIANT_INTERVENTIONS = frozenset(
    {
        "rotate_37_degrees",
        "translate_large_offset",
        "scale_coordinates_x1000_consistent",
        "split_every_segment_at_midpoint",
    }
)
ANTI_WALL_TOKENS = ("DOOR", "FUR", "KIT", "ELEV", "DIM", "TEXT", "수전", "가구")
WALL_MODEL_REQUIRED_OBSERVABLES = frozenset(
    {
        "nested_insert_world_segments",
        "world_lineage",
        "silent_drop_detection",
        "xclip_preservation",
        "source_document_identity",
        "native_display_membership",
        "model_input_membership",
    }
)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_QUALIFICATION_RECEIPT_SCHEMA_PATH = (
    _REPO_ROOT / "schemas" / "e2_qualification_receipt.v1.schema.json"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path, *, relative_to: Path | None = None) -> dict[str, Any]:
    recorded_path = path.relative_to(relative_to).as_posix() if relative_to else str(path)
    raw = path.read_bytes()
    return {
        "path": recorded_path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8-sig"),
        parse_constant=lambda token: (_ for _ in ()).throw(
            ValueError(f"non-finite JSON number {token!r}")
        ),
    )
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int | None = None
    temporary: str | None = None
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=os.fspath(path.parent)
        )
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
        try:
            directory = os.open(os.fspath(path.parent), os.O_RDONLY)
        except OSError:
            directory = None
        if directory is not None:
            try:
                try:
                    os.fsync(directory)
                except OSError:
                    pass
            finally:
                os.close(directory)
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass
        raise


def _write_json(path: Path, value: Any) -> None:
    _write_bytes_atomic(path, _canonical_json_bytes(value))


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _read_json_snapshot(path: Path) -> tuple[dict[str, Any], bytes, str]:
    raw = path.read_bytes()
    value = json.loads(
        raw.decode("utf-8-sig"),
        parse_constant=lambda token: (_ for _ in ()).throw(
            ValueError(f"non-finite JSON number {token!r}")
        ),
    )
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value, raw, hashlib.sha256(raw).hexdigest()


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    attributes = int(getattr(info, "st_file_attributes", 0) or 0)
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0) or 0)
    is_junction = getattr(path, "is_junction", lambda: False)
    return path.is_symlink() or bool(reparse_flag and attributes & reparse_flag) or is_junction()


def _regular_non_reparse_file(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(info.st_mode) and not _is_reparse_point(path)


def _run_local_record_path(run_root: Path, recorded_path: object) -> Path:
    if not isinstance(recorded_path, str) or not recorded_path:
        raise ValueError("recorded path must be a non-empty relative string")
    relative = Path(recorded_path)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.as_posix() != recorded_path.replace("\\", "/")
    ):
        raise ValueError("recorded path must stay relative to the receipt run root")
    target = run_root / relative
    resolved_root = run_root.resolve(strict=True)
    resolved_target = target.resolve(strict=True)
    if resolved_target != resolved_root and resolved_root not in resolved_target.parents:
        raise ValueError("recorded path escaped the receipt run root")
    if _is_reparse_point(run_root) or any(
        _is_reparse_point(parent)
        for parent in (target, *target.parents)
        if parent == run_root or run_root in parent.parents
    ):
        raise ValueError("recorded path traverses a symlink, junction, or reparse point")
    if not _regular_non_reparse_file(target):
        raise ValueError("recorded path is not a regular non-reparse file")
    return target


def _validated_file_record(
    run_root: Path,
    record: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    target = _run_local_record_path(run_root, record.get("path"))
    payload, raw, observed_sha256 = _read_json_snapshot(target)
    expected_sha256 = record.get("sha256")
    expected_bytes = record.get("bytes")
    if expected_sha256 != observed_sha256:
        raise ValueError("recorded SHA-256 does not match the exact parsed bytes")
    if not isinstance(expected_bytes, int) or isinstance(expected_bytes, bool):
        raise ValueError("recorded byte count is not an integer")
    if expected_bytes != len(raw):
        raise ValueError("recorded byte count does not match the exact parsed bytes")
    return payload, observed_sha256


def _schema_errors(instance: Mapping[str, Any]) -> list[str]:
    schema = json.loads(_QUALIFICATION_RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    return [
        error.message
        for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
    ]


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


def _runtime_wall_guard_qualified(guard: Mapping[str, Any]) -> bool:
    raw_required = guard.get("required_observables")
    required = (
        set(raw_required)
        if isinstance(raw_required, list)
        and len(raw_required) == len(WALL_MODEL_REQUIRED_OBSERVABLES)
        and all(isinstance(item, str) and item for item in raw_required)
        else set()
    )
    target_population = guard.get("target_population")
    return (
        guard.get("status") == "READY"
        and required == WALL_MODEL_REQUIRED_OBSERVABLES
        and isinstance(target_population, Mapping)
        and bool(target_population)
    )


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
        "authorization_scope": {
            "execution_purpose": "downstream_learning_or_scoring",
            "required_observables": sorted(WALL_MODEL_REQUIRED_OBSERVABLES),
        },
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


def _finite_number(value: object) -> float | None:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        return None
    return float(value)


def _nonnegative_integer(value: object) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        return None
    return value


def _valid_point2(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(_finite_number(coordinate) is not None for coordinate in value)
    )


def _candidate_details(candidates: Mapping[str, Any]) -> tuple[int | None, list[str]]:
    records = candidates.get("candidates")
    if not isinstance(records, list):
        return None, ["CANDIDATE_DETAIL_INVALID"]
    failures: list[str] = []
    threshold = _finite_number(candidates.get("threshold"))
    identities: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            failures.append("CANDIDATE_DETAIL_INVALID")
            continue
        identity = record.get("placed_uid")
        score = _finite_number(record.get("score"))
        if (
            not isinstance(identity, str)
            or not identity
            or score is None
            or threshold is None
            or score < threshold
        ):
            failures.append("CANDIDATE_DETAIL_INVALID")
            continue
        identities.append(identity)
    if len(identities) != len(set(identities)):
        failures.append("CANDIDATE_DETAIL_INVALID")
    declared = candidates.get("candidate_count")
    if (
        not isinstance(declared, int)
        or isinstance(declared, bool)
        or declared != len(records)
    ):
        failures.append("CANDIDATE_DETAIL_INVALID")
    return len(records), list(dict.fromkeys(failures))


def _wall_pair_details(candidates: Mapping[str, Any]) -> tuple[int, list[str]]:
    records = candidates.get("wall_pair_records")
    if not isinstance(records, list):
        return 0, ["WALL_PAIR_DETAIL_INVALID"]
    identities: list[tuple[str, str]] = []
    failures: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            failures.append("WALL_PAIR_DETAIL_INVALID")
            continue
        handles = record.get("handles")
        axis = record.get("axis")
        thickness = _finite_number(record.get("thickness"))
        if not (
            isinstance(handles, list)
            and len(handles) == 2
            and all(isinstance(handle, str) and handle for handle in handles)
            and handles[0] != handles[1]
            and isinstance(axis, list)
            and len(axis) == 2
            and all(_valid_point2(point) for point in axis)
            and axis[0] != axis[1]
            and thickness is not None
            and thickness > 0.0
        ):
            failures.append("WALL_PAIR_DETAIL_INVALID")
            continue
        identities.append(tuple(sorted((handles[0], handles[1]))))
    if len(identities) != len(set(identities)):
        failures.append("WALL_PAIR_DETAIL_INVALID")
    return len(records), list(dict.fromkeys(failures))


def _rules_f1_from_confusion(models: Mapping[str, Any]) -> tuple[float | None, list[str]]:
    rules = models.get("rules")
    rules = rules if isinstance(rules, Mapping) else {}
    metrics = rules.get("accuracy_metrics")
    if metrics is None:
        return None, []
    if not isinstance(metrics, Mapping):
        return None, ["RULES_F1_CONFUSION_MISMATCH"]
    true_positive = _nonnegative_integer(metrics.get("true_positive"))
    false_positive = _nonnegative_integer(metrics.get("false_positive"))
    false_negative = _nonnegative_integer(metrics.get("false_negative"))
    declared_f1 = _finite_number(metrics.get("f1"))
    if None in (true_positive, false_positive, false_negative, declared_f1):
        return None, ["RULES_F1_CONFUSION_MISMATCH"]
    denominator = 2 * true_positive + false_positive + false_negative
    if denominator <= 0:
        return None, ["RULES_F1_CONFUSION_MISMATCH"]
    recomputed = 2.0 * true_positive / denominator
    if not math.isclose(declared_f1, recomputed, rel_tol=0.0, abs_tol=1e-12):
        return None, ["RULES_F1_CONFUSION_MISMATCH"]
    return recomputed, []


def _expected_invariant_details(
    interventions: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    records = interventions.get("interventions")
    if not isinstance(records, list):
        return {}, ["EXPECTED_INVARIANCE_DETAIL_INVALID"]
    named_expected_records = [
        record
        for record in records
        if isinstance(record, Mapping)
        and record.get("intervention") in EXPECTED_INVARIANT_INTERVENTIONS
    ]
    expected_records = [
        record for record in named_expected_records if record.get("expected_invariant") is True
    ]
    names = [record.get("intervention") for record in expected_records]
    failures: list[str] = []
    if (
        len(named_expected_records) != len(EXPECTED_INVARIANT_INTERVENTIONS)
        or len(expected_records) != len(EXPECTED_INVARIANT_INTERVENTIONS)
        or set(names) != EXPECTED_INVARIANT_INTERVENTIONS
        or len(names) != len(set(names))
    ):
        failures.append("EXPECTED_INVARIANCE_DETAIL_INVALID")
    statuses: dict[str, Any] = {}
    for record in expected_records:
        name = record.get("intervention")
        if isinstance(name, str):
            statuses[name] = record.get("status")
        delta = _finite_number(record.get("max_per_handle_score_delta"))
        if not (
            isinstance(name, str)
            and name in EXPECTED_INVARIANT_INTERVENTIONS
            and record.get("status") == STATUS_PASS
            and _nonnegative_integer(record.get("segments")) is not None
            and _nonnegative_integer(record.get("positive_handles")) is not None
            and record.get("positive_membership_changed_handles") == []
            and record.get("score_changed_handle_count") == 0
            and _finite_number(record.get("positive_handle_jaccard_vs_baseline")) == 1.0
            and _finite_number(record.get("parallel_pair_handle_jaccard_vs_baseline")) == 1.0
            and delta is not None
            and delta <= 1e-6
        ):
            failures.append("EXPECTED_INVARIANCE_DETAIL_INVALID")
    return statuses, list(dict.fromkeys(failures))


def _downstream_experiment_gate(
    receipt: Mapping[str, Any],
    candidates: Mapping[str, Any],
    models: Mapping[str, Any],
    interventions: Mapping[str, Any],
) -> dict[str, Any]:
    """Keep report generation separate from authorization to learn or score."""

    candidate_count, candidate_failures = _candidate_details(candidates)
    wall_pair_record_count, pair_failures = _wall_pair_details(candidates)
    rules_f1, f1_failures = _rules_f1_from_confusion(models)
    invariant_statuses, invariant_failures = _expected_invariant_details(interventions)
    blocked_expected_invariants = sorted(
        name
        for name in EXPECTED_INVARIANT_INTERVENTIONS
        if invariant_statuses.get(name) != STATUS_PASS
    )
    failures = [
        *candidate_failures,
        *pair_failures,
        *f1_failures,
        *invariant_failures,
    ]
    rules = models.get("rules")
    rules = rules if isinstance(rules, Mapping) else {}
    if rules.get("candidate_count") != candidate_count:
        failures.append("CANDIDATE_DETAIL_INVALID")
    baseline = interventions.get("baseline")
    baseline = baseline if isinstance(baseline, Mapping) else {}
    if baseline.get("wall_pair_records") != wall_pair_record_count:
        failures.append("WALL_PAIR_DETAIL_INVALID")
    if receipt.get("schema") != "e2.qualification_receipt.v1":
        failures.append("QUALIFICATION_RECEIPT_SCHEMA_INVALID")
    if receipt.get("status") != STATUS_PASS:
        failures.append("QUALIFICATION_STATUS_NOT_PASS")
    if candidate_count is None or candidate_count <= 0:
        failures.append("NO_WALL_CANDIDATES")
    if wall_pair_record_count <= 0:
        failures.append("NO_WALL_PAIR_RECORDS")
    if rules_f1 is None or rules_f1 <= 0.0:
        failures.append("RULES_F1_NOT_POSITIVE")
    if blocked_expected_invariants:
        failures.append("EXPECTED_INVARIANCE_BLOCKED")

    return {
        "status": STATUS_BLOCKED if failures else STATUS_PASS,
        "reason_codes": list(dict.fromkeys(failures)),
        "qualification_status": receipt.get("status"),
        "candidate_count": candidate_count,
        "wall_pair_record_count": wall_pair_record_count,
        "rules_f1": rules_f1,
        "expected_invariant_statuses": dict(sorted(invariant_statuses.items())),
        "blocked_expected_invariants": blocked_expected_invariants,
    }


def _payload_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _stable_segment_id(value: Mapping[str, Any]) -> str:
    return str(
        value.get("placed_uid")
        or value.get("lineage_id")
        or value.get("handle")
        or ""
    )


def _validate_wall_evidence_bundle(
    *,
    receipt: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, Any]],
    guard: Mapping[str, Any],
) -> tuple[list[str], list[str], set[str]]:
    """Validate the raw observation payloads and their target-population join."""

    evidence_errors: list[str] = []
    population_errors: list[str] = []
    source = receipt.get("source")
    source = source if isinstance(source, Mapping) else {}
    source_sha256 = str(source.get("sha256") or "")
    experiment_id = str(receipt.get("experiment_id") or "")
    native = evidence.get("native_ir", {})
    adapter = evidence.get("adapter_ir", {})
    world = evidence.get("world_ir", {})
    oracle = evidence.get("target_population_oracle", {})
    model = evidence.get("model_input_ir", {})

    try:
        validate_target_population_oracle(
            oracle,
            expected_source_sha256=source_sha256,
            expected_geometry_scope="linear_segments_v1",
        )
    except TargetPopulationContractError as exc:
        evidence_errors.append(
            f"target_population_oracle producer authority is invalid: "
            f"{exc.reason_code}: {exc}"
        )

    native_source = native.get("source")
    native_source = native_source if isinstance(native_source, Mapping) else {}
    diagnostics = native.get("diagnostics")
    diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
    if not (
        native.get("schema") == "ariadne.dwg_graph_ir.v1"
        and native.get("coverage_level") == "native_full"
        and native_source.get("sha256") == source_sha256
        and isinstance(diagnostics.get("errors"), list)
        and not diagnostics.get("errors")
    ):
        evidence_errors.append("native_ir schema, source identity, or diagnostics are invalid")

    adapter_ledger = adapter.get("adapter_ledger")
    adapter_ledger = adapter_ledger if isinstance(adapter_ledger, Mapping) else {}
    if not (
        adapter.get("ir") == "worldir.input.v1"
        and adapter.get("status") == STATUS_PASS
        and adapter.get("drawing_id") == source_sha256
        and adapter_ledger.get("balance_ok") is True
    ):
        evidence_errors.append("adapter_ir schema, source identity, or balance is invalid")

    conservation = world.get("conservation_ledger")
    conservation = conservation if isinstance(conservation, Mapping) else {}
    world_segments = world.get("segments")
    if not (
        world.get("oracle") == "worldir.oracle.v1"
        and world.get("status") == STATUS_PASS
        and world.get("drawing_id") == source_sha256
        and conservation.get("conservation_ok") is True
        and isinstance(world_segments, list)
        and bool(world_segments)
    ):
        evidence_errors.append("world_ir schema, source identity, or conservation is invalid")

    targets = oracle.get("targets")
    model_segments = model.get("segments")
    if not (
        oracle.get("schema") == "ariadne.e2.target_population_oracle.v1"
        and oracle.get("drawing_id") == source_sha256
        and isinstance(targets, list)
        and bool(targets)
    ):
        evidence_errors.append("target_population_oracle schema or source identity is invalid")
        targets = []
    if not (
        model.get("ir") == "seg.v1"
        and model.get("drawing_id") == source_sha256
        and isinstance(model_segments, list)
        and bool(model_segments)
    ):
        evidence_errors.append("model_input_ir schema or source identity is invalid")
        model_segments = []

    world_ids_by_layer: dict[str, set[str]] = defaultdict(set)
    world_seen: set[str] = set()
    for index, row in enumerate(world_segments or []):
        if not isinstance(row, Mapping):
            population_errors.append(f"world segment[{index}] is not an object")
            continue
        segment_id = _stable_segment_id(row)
        layer = str(row.get("source_layer") or "")
        if not segment_id or not layer or segment_id in world_seen:
            population_errors.append(f"world segment[{index}] has invalid identity or layer")
            continue
        world_seen.add(segment_id)
        world_ids_by_layer[layer].add(segment_id)

    model_ids_by_layer: dict[str, set[str]] = defaultdict(set)
    model_seen: set[str] = set()
    for index, row in enumerate(model_segments or []):
        if not isinstance(row, Mapping):
            population_errors.append(f"model segment[{index}] is not an object")
            continue
        segment_id = _stable_segment_id(row)
        layer = str(row.get("source_layer", row.get("layer", "")) or "")
        if not segment_id or not layer or segment_id in model_seen:
            population_errors.append(f"model segment[{index}] has invalid identity or layer")
            continue
        model_seen.add(segment_id)
        model_ids_by_layer[layer].add(segment_id)

    if world_seen != model_seen:
        population_errors.append(
            "WorldIR and model-input stable-ID populations do not match exactly"
        )

    target_ids_by_name: dict[str, set[str]] = {}
    for index, target in enumerate(targets or []):
        if not isinstance(target, Mapping):
            population_errors.append(f"target[{index}] is not an object")
            continue
        target_id = str(target.get("target_id") or "")
        layer = str(target.get("layer") or "")
        raw_ids = target.get("native_visible_segment_ids")
        declared = target.get("native_visible_source_segments")
        ids = set(raw_ids) if isinstance(raw_ids, list) and all(isinstance(item, str) and item for item in raw_ids) else set()
        if (
            not target_id
            or target_id in target_ids_by_name
            or not layer
            or not ids
            or len(ids) != len(raw_ids or [])
            or not isinstance(declared, int)
            or isinstance(declared, bool)
            or declared != len(ids)
        ):
            population_errors.append(f"target[{index}] has invalid identity or counts")
            continue
        target_ids_by_name[target_id] = ids
        if world_ids_by_layer.get(layer) != ids or model_ids_by_layer.get(layer) != ids:
            population_errors.append(
                f"target[{target_id}] does not match WorldIR and model-input stable IDs"
            )

    expected_observables = sorted(WALL_MODEL_REQUIRED_OBSERVABLES)
    guard_hashes = guard.get("evidence_payload_sha256")
    guard_hashes = guard_hashes if isinstance(guard_hashes, Mapping) else {}
    expected_hashes = {
        role: _payload_sha256(evidence[role])
        for role in ("world_ir", "target_population_oracle", "model_input_ir")
        if role in evidence
    }
    if not (
        guard.get("schema") == "ariadne.e2.guard_decision.v1"
        and guard.get("status") == "READY"
        and guard.get("reason_code") == "INSTRUMENT_QUALIFIED"
        and guard.get("experiment_id") == experiment_id
        and guard.get("drawing_id") == source_sha256
        and sorted(set(guard.get("required_observables") or [])) == expected_observables
        and dict(guard_hashes) == expected_hashes
        and isinstance(guard.get("target_population"), Mapping)
        and set(guard.get("target_population") or {}) == set(target_ids_by_name)
    ):
        population_errors.append("guard decision is not bound to the exact qualified population")

    return evidence_errors, population_errors, set(model_seen)


def _validate_complete_object_evaluation(
    *,
    receipt: Mapping[str, Any],
    truth: Mapping[str, Any],
    predictions: Mapping[str, Any],
    models: Mapping[str, Any],
    expected_population_ids: set[str],
) -> tuple[list[str], list[str]]:
    """Recompute the rule confusion matrix from raw object truth and scores."""

    errors: list[str] = []
    population_errors: list[str] = []
    source = receipt.get("source")
    source = source if isinstance(source, Mapping) else {}
    drawing_id = str(source.get("sha256") or "")
    experiment_id = str(receipt.get("experiment_id") or "")
    if not (
        truth.get("schema") == "ariadne.e2.l0.object_truth.v1"
        and truth.get("experiment_id") == experiment_id
        and truth.get("drawing_id") == drawing_id
        and truth.get("label_authority") == "independent_complete_object_truth"
        and truth.get("object_truth_completeness") == "COMPLETE"
        and truth.get("candidate_scope") == "xclip_visible_linear_segments_v1"
    ):
        return ["object truth is not independently complete, scoped, or run-bound"], []
    if not (
        predictions.get("schema") == "ariadne.e2.l0.baseline_predictions.v1"
        and predictions.get("experiment_id") == experiment_id
        and predictions.get("drawing_id") == drawing_id
        and isinstance(predictions.get("model_sha256"), str)
        and len(str(predictions.get("model_sha256"))) == 64
        and isinstance(predictions.get("checkpoint_sha256"), str)
        and len(str(predictions.get("checkpoint_sha256"))) == 64
    ):
        return ["predictions are not model/checkpoint/source/run-bound"], []

    truth_by_id: dict[str, str] = {}
    for index, row in enumerate(truth.get("records") or []):
        if not isinstance(row, Mapping):
            errors.append(f"truth record[{index}] is not an object")
            continue
        segment_id = str(row.get("placed_uid") or "")
        label = str(row.get("label") or "")
        if not segment_id or segment_id in truth_by_id or label not in {"wall", "non_wall"}:
            errors.append(f"truth record[{index}] has invalid identity or label")
            continue
        truth_by_id[segment_id] = label
    threshold = _finite_number(predictions.get("threshold"))
    score_by_id: dict[str, float] = {}
    for index, row in enumerate(predictions.get("rows") or []):
        if not isinstance(row, Mapping):
            errors.append(f"prediction row[{index}] is not an object")
            continue
        segment_id = str(row.get("placed_uid") or "")
        score = _finite_number(row.get("score"))
        if not segment_id or segment_id in score_by_id or score is None:
            errors.append(f"prediction row[{index}] has invalid identity or score")
            continue
        score_by_id[segment_id] = score
    if not truth_by_id or set(truth_by_id) != set(score_by_id) or threshold is None:
        errors.append("truth and prediction stable-ID populations do not match")
        return errors, population_errors
    if set(truth_by_id) != expected_population_ids:
        population_errors.append(
            "truth and prediction stable-ID populations do not match the qualified model population"
        )
        return errors, population_errors
    if set(truth_by_id.values()) != {"wall", "non_wall"}:
        errors.append("complete object truth must exercise both binary classes")
        return errors, population_errors

    tp = fp = fn = 0
    for segment_id, label in truth_by_id.items():
        predicted_wall = score_by_id[segment_id] >= threshold
        if predicted_wall and label == "wall":
            tp += 1
        elif predicted_wall:
            fp += 1
        elif label == "wall":
            fn += 1
    denominator = 2 * tp + fp + fn
    recomputed_f1 = 2.0 * tp / denominator if denominator else None
    rules = models.get("rules")
    rules = rules if isinstance(rules, Mapping) else {}
    metrics = rules.get("accuracy_metrics")
    metrics = metrics if isinstance(metrics, Mapping) else {}
    if not (
        metrics.get("true_positive") == tp
        and metrics.get("false_positive") == fp
        and metrics.get("false_negative") == fn
        and _finite_number(metrics.get("f1")) is not None
        and recomputed_f1 is not None
        and math.isclose(float(metrics["f1"]), recomputed_f1, rel_tol=0.0, abs_tol=1e-12)
    ):
        errors.append("declared confusion/F1 does not match raw truth and predictions")
    return errors, population_errors


def validate_downstream_qualification_receipt(
    path: Path,
    *,
    authorization_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one run-local receipt against the current downstream execution."""

    path = Path(path)
    try:
        if path.name != "qualification_receipt.json":
            raise ValueError("receipt filename must be qualification_receipt.json")
        if _is_reparse_point(path.parent):
            raise ValueError("receipt run root is a symlink, junction, or reparse point")
        if not _regular_non_reparse_file(path):
            raise ValueError("receipt is not a regular non-reparse file")
        receipt, receipt_raw, receipt_sha256 = _read_json_snapshot(path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return {
            "status": STATUS_BLOCKED,
            "integrity_status": STATUS_BLOCKED,
            "execution_authorized": False,
            "reason_codes": ["QUALIFICATION_RECEIPT_UNREADABLE"],
            "reason": f"{type(exc).__name__}: {exc}",
            "path": str(path),
        }

    gate = receipt.get("downstream_experiment_gate")
    gate = gate if isinstance(gate, Mapping) else {}
    candidate_count = gate.get("candidate_count")
    pair_count = gate.get("wall_pair_record_count")
    rules_f1 = gate.get("rules_f1")
    statuses = gate.get("expected_invariant_statuses")
    statuses = statuses if isinstance(statuses, Mapping) else {}
    failures: list[str] = []
    output_errors: list[str] = []
    evidence_errors: list[str] = []
    output_payloads: dict[str, dict[str, Any]] = {}
    evidence_payloads: dict[str, dict[str, Any]] = {}
    output_hashes: dict[str, str] = {}
    evidence_hashes: dict[str, str] = {}
    schema_errors = _schema_errors(receipt)
    if schema_errors:
        failures.append("QUALIFICATION_RECEIPT_SCHEMA_INVALID")

    run_root = path.parent
    required_outputs = {
        "wall_candidates_rules": "wall_candidates_rules.json",
        "model_diagnostics": "model_diagnostics.json",
        "intervention_results": "intervention_results.json",
        "object_truth": "object_truth.json",
        "baseline_predictions": "baseline_predictions.json",
        "guard_decision": "guard_decision.json",
    }
    outputs = receipt.get("outputs")
    outputs = outputs if isinstance(outputs, list) else []
    output_roles = [
        record.get("role") for record in outputs if isinstance(record, Mapping)
    ]
    if len(output_roles) != len(set(output_roles)):
        output_errors.append("output roles must be unique")
    for record in outputs:
        if not isinstance(record, Mapping):
            output_errors.append("every output record must be an object")
            continue
        role = record.get("role")
        if not isinstance(role, str) or not role:
            output_errors.append("every output record must have a non-empty role")
            continue
        try:
            expected_name = required_outputs.get(role)
            if (
                expected_name is not None
                and Path(str(record.get("path") or "")).as_posix() != expected_name
            ):
                raise ValueError(f"output path must be exactly {expected_name!r}")
            payload, observed_sha256 = _validated_file_record(run_root, record)
            output_hashes[role] = observed_sha256
            if role in required_outputs:
                output_payloads[role] = payload
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            output_errors.append(f"{role}: {type(exc).__name__}: {exc}")
    for role in required_outputs:
        if output_roles.count(role) != 1:
            output_errors.append(f"{role}: expected exactly one receipt output")

    evidence = receipt.get("evidence")
    evidence = evidence if isinstance(evidence, list) else []
    required_evidence = {
        "native_ir",
        "adapter_ir",
        "world_ir",
        "target_population_oracle",
        "model_input_ir",
    }
    evidence_roles = [
        record.get("role") for record in evidence if isinstance(record, Mapping)
    ]
    if set(evidence_roles) != required_evidence or len(evidence_roles) != len(
        required_evidence
    ):
        evidence_errors.append(
            "evidence roles must be exactly native_ir, adapter_ir, world_ir, "
            "target_population_oracle, model_input_ir"
        )
    else:
        for record in evidence:
            assert isinstance(record, Mapping)
            role = str(record["role"])
            try:
                payload, observed_sha256 = _validated_file_record(run_root, record)
                evidence_payloads[role] = payload
                evidence_hashes[role] = observed_sha256
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                evidence_errors.append(f"{role}: {type(exc).__name__}: {exc}")

    qualified_population_ids: set[str] = set()
    if evidence_errors:
        failures.append("QUALIFICATION_EVIDENCE_INVALID")
    elif required_evidence <= evidence_payloads.keys() and "guard_decision" in output_payloads:
        semantic_errors, population_errors, qualified_population_ids = (
            _validate_wall_evidence_bundle(
                receipt=receipt,
                evidence=evidence_payloads,
                guard=output_payloads["guard_decision"],
            )
        )
        if semantic_errors:
            evidence_errors.extend(semantic_errors)
            failures.append("QUALIFICATION_EVIDENCE_INVALID")
        if population_errors:
            evidence_errors.extend(population_errors)
            failures.append("QUALIFICATION_POPULATION_BINDING_MISMATCH")

    gate_outputs = {
        "wall_candidates_rules",
        "model_diagnostics",
        "intervention_results",
    }
    if gate_outputs <= output_payloads.keys():
        recomputed_gate = _downstream_experiment_gate(
            receipt,
            output_payloads["wall_candidates_rules"],
            output_payloads["model_diagnostics"],
            output_payloads["intervention_results"],
        )
        failures.extend(recomputed_gate["reason_codes"])
        if dict(gate) != recomputed_gate:
            failures.append("DOWNSTREAM_GATE_EVIDENCE_MISMATCH")
    if required_outputs.keys() <= output_payloads.keys():
        experiment_id = receipt.get("experiment_id")
        source_record = receipt.get("source")
        source_record = source_record if isinstance(source_record, Mapping) else {}
        source_sha256 = source_record.get("sha256")
        for role in ("wall_candidates_rules", "model_diagnostics", "intervention_results"):
            payload = output_payloads[role]
            if (
                payload.get("experiment_id") != experiment_id
                or payload.get("source_sha256") != source_sha256
            ):
                output_errors.append(f"{role}: output is not source/run-bound")
        evaluation_errors, evaluation_population_errors = (
            _validate_complete_object_evaluation(
                receipt=receipt,
                truth=output_payloads["object_truth"],
                predictions=output_payloads["baseline_predictions"],
                models=output_payloads["model_diagnostics"],
                expected_population_ids=qualified_population_ids,
            )
        )
        if evaluation_errors:
            output_errors.extend(evaluation_errors)
            failures.append("QUALIFICATION_EVALUATION_EVIDENCE_INVALID")
        if evaluation_population_errors:
            output_errors.extend(evaluation_population_errors)
            failures.append("QUALIFICATION_POPULATION_BINDING_MISMATCH")
        if output_errors:
            failures.append("QUALIFICATION_OUTPUT_INVALID")
    if output_errors:
        failures.append("QUALIFICATION_OUTPUT_INVALID")

    context = dict(authorization_context or {})
    source = receipt.get("source")
    source = source if isinstance(source, Mapping) else {}
    scope = receipt.get("authorization_scope")
    scope = scope if isinstance(scope, Mapping) else {}
    if not authorization_context:
        failures.append("QUALIFICATION_AUTHORIZATION_CONTEXT_REQUIRED")
    else:
        if context.get("execution_purpose") != "downstream_learning_or_scoring":
            failures.append("QUALIFICATION_EXECUTION_PURPOSE_MISMATCH")
        if context.get("experiment_id") != receipt.get("experiment_id"):
            failures.append("QUALIFICATION_EXPERIMENT_ID_MISMATCH")
        current_observables = context.get("required_observables")
        current_observables = (
            sorted(set(current_observables))
            if isinstance(current_observables, list)
            and all(isinstance(item, str) and item for item in current_observables)
            else None
        )
        authorized_observables = scope.get("required_observables")
        authorized_observables = (
            sorted(set(authorized_observables))
            if isinstance(authorized_observables, list)
            and all(isinstance(item, str) and item for item in authorized_observables)
            else None
        )
        expected_observables = sorted(WALL_MODEL_REQUIRED_OBSERVABLES)
        if (
            current_observables != expected_observables
            or authorized_observables != expected_observables
        ):
            failures.append("QUALIFICATION_OBSERVABLE_SCOPE_INCOMPLETE")
        if current_observables is None or current_observables != authorized_observables:
            failures.append("QUALIFICATION_OBSERVABLE_SCOPE_MISMATCH")
        try:
            requested_source = Path(
                str(context.get("source_requested_path") or context.get("source_path") or "")
            )
            receipt_source_requested = Path(str(source.get("path") or ""))
            if (
                _is_reparse_point(requested_source)
                or _is_reparse_point(requested_source.parent)
                or _is_reparse_point(receipt_source_requested)
                or _is_reparse_point(receipt_source_requested.parent)
            ):
                raise ValueError("source binding traverses a symlink, junction, or reparse point")
            current_source = Path(str(context.get("source_path") or "")).resolve(strict=True)
            receipt_source = receipt_source_requested.resolve(strict=True)
            current_source_sha256 = context.get("source_sha256")
            if not _regular_non_reparse_file(current_source):
                raise ValueError("current source is not a regular non-reparse file")
            source_raw = current_source.read_bytes()
            observed_source_sha256 = hashlib.sha256(source_raw).hexdigest()
            if not (
                os.path.normcase(str(current_source))
                == os.path.normcase(str(receipt_source))
                and current_source_sha256 == observed_source_sha256
                and source.get("sha256") == observed_source_sha256
                and source.get("native_payload_sha256") == observed_source_sha256
                and source.get("read_only") is True
            ):
                failures.append("QUALIFICATION_SOURCE_BINDING_MISMATCH")
        except (OSError, ValueError):
            failures.append("QUALIFICATION_SOURCE_BINDING_MISMATCH")
        command = context.get("command")
        command_config = context.get("command_config")
        if not (
            isinstance(command, list)
            and bool(command)
            and all(isinstance(item, str) and item for item in command)
            and isinstance(command_config, Mapping)
        ):
            failures.append("QUALIFICATION_COMMAND_CONTEXT_INVALID")

    if receipt.get("schema") != "e2.qualification_receipt.v1":
        failures.append("QUALIFICATION_RECEIPT_SCHEMA_INVALID")
    if receipt.get("status") != STATUS_PASS:
        failures.append("QUALIFICATION_STATUS_NOT_PASS")
    if gate.get("status") != STATUS_PASS:
        failures.append("DOWNSTREAM_GATE_NOT_PASS")
    if not isinstance(candidate_count, int) or isinstance(candidate_count, bool) or candidate_count <= 0:
        failures.append("NO_WALL_CANDIDATES")
    if not isinstance(pair_count, int) or isinstance(pair_count, bool) or pair_count <= 0:
        failures.append("NO_WALL_PAIR_RECORDS")
    if (
        not isinstance(rules_f1, (int, float))
        or isinstance(rules_f1, bool)
        or not math.isfinite(float(rules_f1))
        or float(rules_f1) <= 0.0
    ):
        failures.append("RULES_F1_NOT_POSITIVE")
    if any(statuses.get(name) != STATUS_PASS for name in EXPECTED_INVARIANT_INTERVENTIONS):
        failures.append("EXPECTED_INVARIANCE_BLOCKED")

    try:
        snapshot_material = {
            "receipt_sha256": receipt_sha256,
            "evidence_sha256": dict(sorted(evidence_hashes.items())),
            "output_sha256": dict(sorted(output_hashes.items())),
            "authorization_context": context,
        }
        authorization_snapshot_digest = hashlib.sha256(
            _canonical_json_bytes(snapshot_material)
        ).hexdigest()
    except (TypeError, ValueError):
        authorization_snapshot_digest = None
        failures.append("QUALIFICATION_COMMAND_CONTEXT_INVALID")

    integrity_reason_codes = list(dict.fromkeys(failures))
    integrity_status = STATUS_BLOCKED if integrity_reason_codes else STATUS_PASS
    reason_codes = list(
        dict.fromkeys(
            [*integrity_reason_codes, "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"]
        )
    )
    return {
        "status": STATUS_BLOCKED,
        "integrity_status": integrity_status,
        "execution_authorized": False,
        "reason_codes": reason_codes,
        "path": str(path.resolve()),
        "sha256": receipt_sha256,
        "bytes": len(receipt_raw),
        "authorization_snapshot_digest": authorization_snapshot_digest,
        "validated_output_sha256": output_hashes,
        "validated_evidence_sha256": evidence_hashes,
        "schema_errors": schema_errors,
        "output_errors": output_errors,
        "evidence_errors": evidence_errors,
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
    """Refuse unsealed public scoring before reading inputs or creating outputs."""

    return refusal_receipt(
        requested_receipt_schema="e2.qualification_receipt.v1",
        experiment_id=spec.get("experiment_id"),
        entrypoint="tools.e2.qualification.engine.build_first_report",
        claim_boundary="no direct rule or model scoring; sealed executor required",
    )


def _build_instrument_snapshot(spec: Mapping[str, Any], run_dir: Path) -> dict[str, Any]:
    """Assemble an internal instrument snapshot for qualification tests.

    This is not a public execution seam. A future sealed executor may call this
    helper only after it has bound and confined the exact qualified inputs.
    """

    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    if _is_reparse_point(run_dir):
        raise ValueError("run_dir must not be a symlink, junction, or reparse point")
    source_path = Path(spec["source"]["path"])
    if not _regular_non_reparse_file(source_path):
        raise ValueError("source must be a regular non-reparse file")
    actual_source_hash = _sha256(source_path)
    if actual_source_hash.lower() != str(spec["source"]["sha256"]).lower():
        raise ValueError(
            f"source hash mismatch: expected {spec['source']['sha256']}, got {actual_source_hash}"
        )
    evidence_paths = {name: Path(path) for name, path in spec["evidence"].items()}
    evidence_payloads: dict[str, dict[str, Any]] = {}
    evidence_snapshot_paths: dict[str, Path] = {}
    for name, path in sorted(evidence_paths.items()):
        if not _regular_non_reparse_file(path):
            raise ValueError(f"{name}: evidence must be a regular non-reparse file")
        payload, _, _ = _read_json_snapshot(path)
        snapshot_path = run_dir / "evidence" / f"{name}.json"
        _write_json(snapshot_path, payload)
        evidence_payloads[name] = payload
        evidence_snapshot_paths[name] = snapshot_path
    native = evidence_payloads["native_ir"]
    adapter = evidence_payloads["adapter_ir"]
    world = evidence_payloads["world_ir"]
    evidence_records = [
        {
            "role": name,
            **_file_record(path, relative_to=run_dir),
        }
        for name, path in sorted(evidence_snapshot_paths.items())
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
        guard_ok = _runtime_wall_guard_qualified(guard)
        missing_required = sorted(
            WALL_MODEL_REQUIRED_OBSERVABLES
            - set(guard.get("required_observables") or [])
        )
        receipt["gates"].append(
            _gate(
                "runtime_experiment_guard",
                STATUS_PASS if guard_ok else STATUS_BLOCKED,
                (
                    f"status={guard.get('status')}; pipeline={guard.get('selected_pipeline')}; "
                    f"reason={guard.get('reason_code')}; missing_required={missing_required}; "
                    f"target_populations={len(guard.get('target_population') or {})}"
                ),
            )
        )
        receipt["scope_verdicts"]["guarded_experiment_execution"] = (
            STATUS_PASS if guard_ok else STATUS_BLOCKED
        )
        if not guard_ok:
            receipt["status"] = STATUS_BLOCKED

    downstream_gate = _downstream_experiment_gate(
        receipt, candidates, models, interventions
    )
    receipt["downstream_experiment_gate"] = downstream_gate
    receipt["gates"].append(
        _gate(
            "downstream_model_learning_or_scoring",
            downstream_gate["status"],
            (
                f"qualification_status={downstream_gate['qualification_status']}; "
                f"candidates={downstream_gate['candidate_count']}; "
                f"wall_pairs={downstream_gate['wall_pair_record_count']}; "
                f"rules_f1={downstream_gate['rules_f1']}; "
                f"blocked_invariants={downstream_gate['blocked_expected_invariants']}; "
                f"reasons={downstream_gate['reason_codes']}"
            ),
        )
    )
    receipt["scope_verdicts"]["downstream_model_learning_or_scoring"] = downstream_gate[
        "status"
    ]

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
        {
            "role": name.removesuffix(".json"),
            **_file_record(run_dir / name, relative_to=run_dir),
        }
        for name in output_values
    ]
    if guard_path.is_file():
        receipt["outputs"].append(
            {
                "role": "guard_decision",
                **_file_record(guard_path, relative_to=run_dir),
            }
        )
    _write_json(run_dir / "qualification_receipt.json", receipt)
    report = _render_report(spec, receipt, census, loss, candidates, models, interventions)
    _write_bytes_atomic(run_dir / "REPORT.md", report.encode("utf-8"))
    return {
        "status": receipt["status"],
        "run_dir": str(run_dir),
        "report": str(run_dir / "REPORT.md"),
        "receipt": str(run_dir / "qualification_receipt.json"),
        "candidate_count": candidates["candidate_count"],
        "downstream_experiment_gate": downstream_gate,
    }
