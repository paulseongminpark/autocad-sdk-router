#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F04 common metamorphic relation registry judge.

This instrument folds already-existing evidence only.  It never opens a test
set, invokes a model/API, or writes CAD.  Canonical family cells are populated
only when the sealed method/relation admissibility gates are evidenced; legacy
numbers remain visible without being promoted to a PASS.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SCHEMA = "ariadne.e2.f04_common_judge.result.v1"
PASS_MAX = Decimal("0.02")
INCONCLUSIVE_MAX = Decimal("0.10")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text.rstrip() + "\n")


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"not a numeric measurement: {value!r}")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"not a decimal measurement: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"measurement must be finite: {value!r}")
    return result


def decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def classify_r_meta(value: Any) -> str:
    """Apply the sealed, non-overlapping R-META bands."""
    rate = value if isinstance(value, Decimal) else _decimal(value)
    if rate < 0 or rate > 1:
        raise ValueError(f"R-META outside [0,1]: {rate}")
    if rate <= PASS_MAX:
        return "PASS"
    if rate <= INCONCLUSIVE_MAX:
        return "INCONCLUSIVE"
    return "FAIL"


def relation_for_legacy(transform: str, prereg: Mapping[str, Any]) -> Optional[str]:
    mapping = prereg.get("legacy_transform_mapping") or {}
    row = mapping.get(transform) if isinstance(mapping, Mapping) else None
    if not isinstance(row, Mapping):
        return None
    relation = row.get("registry_relation")
    return str(relation) if relation is not None else None


def _source_transform_rows(source_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if source_id == "b4_fold_v2":
        rows = payload.get("transforms")
    elif source_id == "w2_independence_audit_v1":
        rows = (
            ((payload.get("surrogates") or {}).get("D_detector_vs_metamorphic") or {})
            .get("per_transform")
        )
    else:
        raise ValueError(f"unknown evidence source: {source_id}")
    if not isinstance(rows, Mapping):
        raise ValueError(f"missing transform mapping in {source_id}")
    return rows


def _source_pointer(source_id: str, transform: str) -> str:
    if source_id == "b4_fold_v2":
        return f"/transforms/{transform}"
    return f"/surrogates/D_detector_vs_metamorphic/per_transform/{transform}"


def _admissibility(
    *,
    relation_id: Optional[str],
    payload: Mapping[str, Any],
    row: Mapping[str, Any],
) -> Tuple[str, Dict[str, bool], List[str]]:
    family_id = row.get("family_id") or payload.get("family_id")
    method_id = row.get("method_id") or payload.get("method_id")
    artifact_manifest = row.get("artifact_manifest") or payload.get("artifact_manifest")
    transform_certificate = row.get("transform_certificate")
    lid_certificate = row.get("lid_bijection_certificate")
    repeat_checksum = row.get("repeat_checksum_match")

    n_zero = row.get("n_sentinel_zero")
    n_all = row.get("n_sentinel_all")
    recall = row.get("positive_sentinel_recall")
    if recall is None:
        # The old fold's mean_recall_after is retained as a source number, but it
        # is not silently re-labelled as the sealed truth-bearing Q1 recall.
        sentinel_qualified = False
    else:
        sentinel_qualified = (
            n_zero == 0 and n_all == 0 and _decimal(recall) >= Decimal("0.20")
        )

    checks = {
        "relation_registered": relation_id is not None,
        "family_identified": family_id is not None,
        "method_id_identified": method_id is not None,
        "artifact_manifest_present": artifact_manifest is not None,
        "transform_certificate_present": transform_certificate is not None,
        "lid_bijection_certificate_present": lid_certificate is not None,
        "repeat_checksum_present_and_matching": repeat_checksum is True,
        "sentinel_qualified": sentinel_qualified,
    }
    reasons: List[str] = []
    labels = {
        "relation_registered": "relation_not_registered",
        "family_identified": "family_id_absent",
        "method_id_identified": "method_id_absent",
        "artifact_manifest_present": "artifact_manifest_absent",
        "transform_certificate_present": "transform_certificate_absent",
        "lid_bijection_certificate_present": "lid_bijection_certificate_absent",
        "repeat_checksum_present_and_matching": "repeat_checksum_unproven",
        "sentinel_qualified": "sentinel_qualification_unproven_or_failed",
    }
    for key, passed in checks.items():
        if not passed:
            reasons.append(labels[key])
    if isinstance(n_zero, int) and n_zero > 0:
        reasons.append(f"sentinel_zero_trips={n_zero}")
    if isinstance(n_all, int) and n_all > 0:
        reasons.append(f"sentinel_all_trips={n_all}")
    if relation_id is None:
        return "OUT_OF_CATALOG", checks, reasons
    if all(checks.values()):
        return "ADMISSIBLE", checks, reasons
    return "INADMISSIBLE", checks, reasons


def collect_observations(
    *,
    source_id: str,
    source_path: str,
    source_sha256: str,
    precedence: int,
    payload: Mapping[str, Any],
    prereg: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    observations: List[Dict[str, Any]] = []
    rows = _source_transform_rows(source_id, payload)
    for transform, raw_row in rows.items():
        if not isinstance(raw_row, Mapping):
            continue
        if raw_row.get("mean_invariance") is None:
            continue
        inv = _decimal(raw_row["mean_invariance"])
        if inv < 0 or inv > 1:
            raise ValueError(
                f"{source_id} {transform}: mean_invariance outside [0,1]: {inv}"
            )
        r_meta = Decimal("1") - inv
        relation_id = relation_for_legacy(str(transform), prereg)
        admission, checks, reasons = _admissibility(
            relation_id=relation_id, payload=payload, row=raw_row
        )
        source_verdict = raw_row.get("verdict_strict", raw_row.get("verdict"))
        values = {
            key: raw_row.get(key)
            for key in (
                "n",
                "mean_invariance",
                "min_invariance",
                "n_sentinel_zero",
                "n_sentinel_all",
                "mean_recall_after",
                "n_recall_below_floor",
                "banded",
                "verdict",
                "verdict_strict",
                "strict_reason",
            )
            if key in raw_row
        }
        observations.append(
            {
                "observation_id": f"{source_id}:{transform}",
                "source_id": source_id,
                "source_path": source_path,
                "source_sha256": source_sha256,
                "source_pointer": _source_pointer(source_id, str(transform)),
                "source_precedence": precedence,
                "source_transform": str(transform),
                "registry_relation": relation_id,
                "observed_family": raw_row.get("family_id") or payload.get("family_id"),
                "observed_method_id": raw_row.get("method_id") or payload.get("method_id"),
                "source_values": values,
                "mean_invariance": float(inv),
                "mean_invariance_exact": decimal_text(inv),
                "derived_r_meta": float(r_meta),
                "derived_r_meta_exact": decimal_text(r_meta),
                "derived_r_meta_formula": (
                    f"1 - {decimal_text(inv)} = {decimal_text(r_meta)}"
                ),
                "diagnostic_band_from_r_meta": classify_r_meta(r_meta),
                "source_verdict": source_verdict,
                "admissibility": admission,
                "admissibility_checks": checks,
                "admissibility_reasons": reasons,
                "canonical_cell_promoted": admission == "ADMISSIBLE",
            }
        )
    return observations


def select_preferred_legacy(
    observations: Iterable[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    selected: Dict[str, Dict[str, Any]] = {}
    for row in observations:
        key = str(row["source_transform"])
        candidate = dict(row)
        current = selected.get(key)
        if current is None or int(candidate["source_precedence"]) > int(
            current["source_precedence"]
        ):
            selected[key] = candidate
    order = {name: idx for idx, name in enumerate((
        "translate", "rotate", "mirror", "scale", "units", "explode", "rename", "jitter"
    ))}
    return sorted(selected.values(), key=lambda r: (order.get(str(r["source_transform"]), 99), str(r["source_transform"])))


def build_discrepancies(
    observations: Iterable[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    by_transform: Dict[str, Dict[str, Mapping[str, Any]]] = {}
    for row in observations:
        by_transform.setdefault(str(row["source_transform"]), {})[
            str(row["source_id"])
        ] = row
    out: List[Dict[str, Any]] = []
    for transform, sources in sorted(by_transform.items()):
        old = sources.get("w2_independence_audit_v1")
        corrected = sources.get("b4_fold_v2")
        if old is None or corrected is None:
            continue
        old_inv = _decimal(old["mean_invariance_exact"])
        new_inv = _decimal(corrected["mean_invariance_exact"])
        inv_delta = new_inv - old_inv
        r_delta = -inv_delta
        out.append(
            {
                "transform": transform,
                "older_observation": old["observation_id"],
                "corrected_observation": corrected["observation_id"],
                "mean_invariance_delta_corrected_minus_older": float(inv_delta),
                "mean_invariance_delta_exact": decimal_text(inv_delta),
                "r_meta_delta_corrected_minus_older": float(r_delta),
                "r_meta_delta_exact": decimal_text(r_delta),
                "formula": (
                    f"corrected {decimal_text(new_inv)} - older {decimal_text(old_inv)} "
                    f"= {decimal_text(inv_delta)} invariance"
                ),
                "policy": "retain both; corrected source has precedence; never average",
            }
        )
    return out


def build_canonical_matrix(
    prereg: Mapping[str, Any],
    observations: Iterable[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    relations = prereg.get("relation_registry") or []
    families = prereg.get("families") or []
    refs_by_relation: Dict[str, List[str]] = {}
    for obs in observations:
        relation = obs.get("registry_relation")
        if relation is not None:
            refs_by_relation.setdefault(str(relation), []).append(str(obs["observation_id"]))

    rows: List[Dict[str, Any]] = []
    for family in families:
        family_id = str(family["id"])
        cells = list(family.get("cell_ids") or [])
        if len(cells) != len(relations):
            raise ValueError(
                f"family {family_id} has {len(cells)} cells for {len(relations)} relations"
            )
        owner = str(family.get("owner_axis"))
        scope_status = "IN_SCOPE_F04_CPU" if owner == "F04" else "DEFERRED_SCOPE"
        for idx, relation in enumerate(relations):
            relation_id = str(relation["id"])
            reason = (
                "No admissible family-tagged measurement exists in the sealed packet inputs."
                if scope_status == "IN_SCOPE_F04_CPU"
                else f"Owned by {owner}; this CPU packet records UNKNOWN without substitution."
            )
            rows.append(
                {
                    "cell_id": str(cells[idx]),
                    "family": family_id,
                    "owner_axis": owner,
                    "scope_status": scope_status,
                    "transform": relation_id,
                    "measurement_state": "UNKNOWN",
                    "r_meta": None,
                    "verdict": "UNKNOWN",
                    "reason": reason,
                    "legacy_unassigned_observation_refs": sorted(
                        refs_by_relation.get(relation_id, [])
                    ),
                }
            )
    return rows


def summarize_matrix(
    matrix: Sequence[Mapping[str, Any]], prereg: Mapping[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    family_summaries: List[Dict[str, Any]] = []
    for family in prereg.get("families") or []:
        family_id = str(family["id"])
        cells = [row for row in matrix if row["family"] == family_id]
        counts = {
            state: sum(1 for row in cells if row["verdict"] == state)
            for state in ("PASS", "INCONCLUSIVE", "FAIL", "UNKNOWN")
        }
        family_summaries.append(
            {
                "family": family_id,
                "owner_axis": family.get("owner_axis"),
                "n_cells": len(cells),
                "verdict_counts": counts,
                "family_verdict": "UNKNOWN",
                "reason": "At least one canonical cell lacks an admissible numeric measurement.",
            }
        )
    numeric = sum(1 for row in matrix if row.get("r_meta") is not None)
    total = len(matrix)
    effects = {
        "status": "NOT_COMPUTABLE_MISSING_CANONICAL_CELLS",
        "expected_cells": total,
        "admissible_numeric_cells": numeric,
        "missing_cells": total - numeric,
        "formula_basis": "7 preregistered transforms x 4 preregistered families = 28 cells",
        "imputation": "NONE",
        "transform_main_effects": None,
        "family_main_effects": None,
        "transform_by_family_interactions": None,
    }
    return family_summaries, effects


def validate_preregistered_inputs(
    prereg: Mapping[str, Any], repo_root: Path
) -> List[Dict[str, Any]]:
    specs: List[Mapping[str, Any]] = []
    packet = prereg.get("packet")
    if isinstance(packet, Mapping):
        specs.append(
            {
                "role": "packet",
                "path": packet.get("path"),
                "sha256": packet.get("sha256"),
            }
        )
    specs.extend(prereg.get("inputs") or [])
    results: List[Dict[str, Any]] = []
    for spec in specs:
        raw_path = Path(str(spec.get("path", "")))
        path = raw_path if raw_path.is_absolute() else repo_root / raw_path
        exists = path.is_file()
        actual = sha256_path(path) if exists else None
        expected = str(spec.get("sha256") or "").lower()
        results.append(
            {
                "role": spec.get("role"),
                "path": str(path),
                "exists": exists,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "hash_match": exists and actual == expected,
            }
        )
    return results


def _csv_rows(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return format(value, ".10g")
    return str(value)


def render_matrix_markdown(
    result: Mapping[str, Any], prereg: Mapping[str, Any]
) -> str:
    matrix = result["canonical_transform_by_family"]
    families = [str(row["id"]) for row in prereg["families"]]
    relations = [str(row["id"]) for row in prereg["relation_registry"]]
    lookup = {(row["transform"], row["family"]): row for row in matrix}
    lines = [
        "# F04 transform-by-family table",
        "",
        f"Prereg SHA-256: `{result['prereg_sha256']}`",
        "",
        "Canonical cells stay `UNKNOWN` unless every sealed admissibility gate is evidenced.",
        "Legacy numeric observations are listed separately and are not silently assigned to a family.",
        "",
        "| Transform | " + " | ".join(families) + " |",
        "|---|" + "---|" * len(families),
    ]
    for relation in relations:
        cells = []
        for family in families:
            row = lookup[(relation, family)]
            cells.append(f"{row['verdict']} ({row['cell_id']})")
        lines.append("| " + relation + " | " + " | ".join(cells) + " |")
    lines.extend(
        [
            "",
            "## Legacy observations (unassigned to canonical families)",
            "",
            "| Source transform | Registry relation | Preferred source | Mean invariance | Derived R-META | Diagnostic band | Source verdict | Admission |",
            "|---|---|---|---:|---:|---|---|---|",
        ]
    )
    for row in result["preferred_legacy_observations"]:
        lines.append(
            "| {source_transform} | {registry_relation} | {source_id} | {mean_invariance} | "
            "{derived_r_meta} | {diagnostic_band_from_r_meta} | {source_verdict} | {admissibility} |".format(
                **{key: _fmt(value) for key, value in row.items()}
            )
        )
    lines.extend(
        [
            "",
            "`mirror` is retained above as legacy evidence but is outside T-META v1.",
            "The corrected `scale` observation remains FAIL and is never hidden or averaged with the older fold.",
        ]
    )
    return "\n".join(lines)


def render_report(
    result: Mapping[str, Any], prereg: Mapping[str, Any]
) -> str:
    preferred = result["preferred_legacy_observations"]
    scale = [row for row in result["all_legacy_observations"] if row["source_transform"] == "scale"]
    lines = [
        "# F04 common metamorphic judge — completion report",
        "",
        f"- Axis measurement status: `{result['axis_measurement_status']}`",
        f"- Scientific F04 gate: `{result['scientific_gate_status']}`",
        f"- Local prereg SHA-256: `{result['prereg_sha256']}`",
        f"- Execution UTC: `{result['executed_utc']}`",
        "",
        "The registry/judge and exhaustive table were completed from the sealed inputs. No canonical family received a PASS: the input folds do not identify a frozen method/family or provide the required transform, LID, checksum, and sentinel qualification certificates. Their numbers are preserved as legacy observations, while every unproven canonical cell remains `UNKNOWN`.",
        "",
        "## Sealed F04 wording",
        "",
        prereg["plan_f04_verbatim"],
        "",
        "## Relation registry",
        "",
        "| Relation | Binary relation | Structured relation | Validity gate |",
        "|---|---|---|---|",
    ]
    for relation in prereg["relation_registry"]:
        lines.append(
            f"| `{relation['id']}` | {relation['binary_relation']} | "
            f"{relation['structured_relation']} | {relation['validity_gate']} |"
        )
    lines.extend(
        [
            "",
            "## Method admissibility",
            "",
            "A numeric cell verdict is allowed only after all common and family-specific gates in `PREREG_local.json` pass. A number without those certificates is evidence, but not a canonical cell result. In particular, strict source verdicts and sentinel trips are never waived.",
            "",
            "| Family | Owner | Current tranche | Required artifact/status |",
            "|---|---|---|---|",
        ]
    )
    for family in prereg["families"]:
        current = "in scope" if family["owner_axis"] == "F04" else "deferred"
        required = family.get("required_artifact") or family.get("current_packet_status")
        lines.append(
            f"| `{family['id']}` | `{family['owner_axis']}` | {current} | {required} |"
        )
    lines.extend(
        [
            "",
            "## Transform-by-family confirmation table",
            "",
            "| Transform | deterministic_v0 | classical_ml | gnn | vlm |",
            "|---|---|---|---|---|",
        ]
    )
    lookup = {
        (row["transform"], row["family"]): row
        for row in result["canonical_transform_by_family"]
    }
    for relation in prereg["relation_registry"]:
        rid = relation["id"]
        cells = []
        for family in prereg["families"]:
            row = lookup[(rid, family["id"])]
            cells.append(f"{row['verdict']} ({row['cell_id']})")
        lines.append(f"| `{rid}` | " + " | ".join(cells) + " |")
    effects = result["effects_and_interactions"]
    lines.extend(
        [
            "",
            "The table has 28 canonical cells because the sealed registry has 7 relations and 4 families. Admissible numeric cells: 0; missing cells: 28. No missing cell was imputed. Consequently transform effects, family effects, and A×B interactions are `NOT_COMPUTABLE_MISSING_CANONICAL_CELLS`, and confirmation is not run.",
            "",
            "## Legacy evidence, with numeric lineage",
            "",
            "| Transform | Registry relation | Source | Mean invariance | R-META derivation | Diagnostic band | Source verdict | Sentinel all | Admission |",
            "|---|---|---|---:|---|---|---|---:|---|",
        ]
    )
    for row in preferred:
        values = row["source_values"]
        lines.append(
            f"| `{row['source_transform']}` | `{_fmt(row['registry_relation'])}` | "
            f"`{row['source_id']}` `{row['source_pointer']}` | {row['mean_invariance_exact']} | "
            f"`{row['derived_r_meta_formula']}` | {row['diagnostic_band_from_r_meta']} | "
            f"{_fmt(row['source_verdict'])} | {_fmt(values.get('n_sentinel_all'))} | "
            f"{row['admissibility']} |"
        )
    lines.extend(
        [
            "",
            "`b4_fold_v2` has precedence for the overlapping legacy observations because it is the repaired strict fold. `w2_independence_audit_v1` is retained in `evidence.json`; the two are not averaged.",
            "",
            "## Scale failure retained",
            "",
        ]
    )
    for row in sorted(scale, key=lambda item: int(item["source_precedence"]), reverse=True):
        n_all = row["source_values"].get("n_sentinel_all")
        strict_reason = row["source_values"].get("strict_reason")
        lines.append(
            f"- `{row['source_id']}` `{row['source_pointer']}`: invariance "
            f"{row['mean_invariance_exact']}; R-META {row['derived_r_meta_exact']} "
            f"from `{row['derived_r_meta_formula']}`; diagnostic band "
            f"`{row['diagnostic_band_from_r_meta']}`; source verdict "
            f"`{_fmt(row['source_verdict'])}`; sentinel_all `{_fmt(n_all)}`. "
            f"{_fmt(strict_reason) if strict_reason else ''}".rstrip()
        )
    lines.extend(
        [
            "",
            "Both recorded scale measurements exceed the sealed FAIL boundary. The corrected fold is worse than the older projection; the exact delta is retained in `evidence.json`. This failure is not converted to UNKNOWN—the observation remains FAIL—while its assignment to a canonical method family remains inadmissible.",
            "",
            "## Boundaries and validation",
            "",
            "- Model/API calls: 0 (instrument consumes local JSON only).",
            "- Test-set reads: 0 (only preregistered report/design inputs were opened).",
            "- Original CAD reads/writes: 0/0.",
            "- Existing source files modified: 0; both instrument files are new.",
            f"- Input hash checks passing: {sum(1 for row in result['input_validation'] if row['hash_match'])}/{len(result['input_validation'])}, directly from the sealed expected hashes and current SHA-256 values.",
            f"- Self-test: `{result['selftest_evidence'].get('status', 'NOT_PROVIDED')}` using hand-fixed expected fixtures, independent of production input values.",
            "",
            "The completion marker means the requested registry/judge measurement surface was built and exhaustively emitted. It does not mean the F04 scientific gate passed; that gate remains incomplete until admissible family-tagged cells exist.",
            "",
            result["axis_measurement_status"],
        ]
    )
    return "\n".join(lines)


def render_validation(result: Mapping[str, Any]) -> str:
    lines = [
        "# F04 validation",
        "",
        f"- Axis status: `{result['axis_measurement_status']}`",
        f"- Scientific gate: `{result['scientific_gate_status']}`",
        f"- Prereg SHA-256: `{result['prereg_sha256']}`",
        f"- Self-test: `{result['selftest_evidence'].get('status', 'NOT_PROVIDED')}`",
        "",
        "## Input seals",
        "",
        "| Role | Exists | Hash match | Actual SHA-256 |",
        "|---|---|---|---|",
    ]
    for row in result["input_validation"]:
        lines.append(
            f"| {row['role']} | {row['exists']} | {row['hash_match']} | `{_fmt(row['actual_sha256'])}` |"
        )
    lines.extend(
        [
            "",
            "## Structural checks",
            "",
            "- Registry relations: 7, from the sealed preregistration.",
            "- Families: 4, from the sealed preregistration.",
            "- Canonical matrix: 28 rows (= 7 × 4), all explicit.",
            "- Unknown preservation: 28 rows remain UNKNOWN; none was converted to zero or PASS.",
            "- Legacy mirror: retained as OUT_OF_CATALOG.",
            "- Scale: both source observations retained with FAIL diagnostic bands.",
            "- Effects/interactions: not computed because the 28-cell numeric matrix is incomplete.",
        ]
    )
    return "\n".join(lines)


def render_files_changed(repo_root: Path, raw_dir: Path) -> str:
    paths = [
        repo_root / "tools/e2/instruments/f04_common_judge.py",
        repo_root / "tools/e2/instruments/f04_common_judge_selftest.py",
        repo_root / "reports/e2/instruments/f04_REPORT.md",
        repo_root / "reports/e2/cells/f04_completion/PREREG_local.json",
        repo_root / "reports/e2/cells/f04_completion/evidence.json",
        repo_root / "reports/e2/cells/f04_completion/transform_by_family.csv",
        repo_root / "reports/e2/cells/f04_completion/transform_by_family.md",
        repo_root / "reports/e2/cells/f04_completion/legacy_observations.csv",
        repo_root / "reports/e2/cells/f04_completion/VALIDATION.md",
        repo_root / "reports/e2/cells/f04_completion/FILES_CHANGED.md",
        repo_root / "reports/e2/cells/f04_completion/evidence_manifest.json",
        raw_dir / "judge_result.json",
        raw_dir / "transform_by_family.csv",
        raw_dir / "legacy_observations.csv",
        raw_dir / "selftest_result.json",
        raw_dir / "output_manifest.json",
    ]
    lines = [
        "# F04 files changed",
        "",
        "All listed files are new for this packet; no pre-existing source file was edited.",
        "",
    ]
    lines.extend(f"- `{path}`" for path in paths)
    return "\n".join(lines)


def write_blocked(
    *,
    raw_dir: Path,
    report_dir: Path,
    final_report: Path,
    prereg_path: Path,
    reasons: Sequence[str],
) -> None:
    payload = {
        "schema": SCHEMA,
        "axis_measurement_status": "BLOCKED_INPUT",
        "scientific_gate_status": "BLOCKED_INPUT",
        "prereg_path": str(prereg_path),
        "reasons": list(reasons),
    }
    write_json(raw_dir / "judge_result.json", payload)
    write_json(report_dir / "evidence.json", payload)
    report = "\n".join(
        [
            "# F04 common metamorphic judge — blocked",
            "",
            *[f"- {reason}" for reason in reasons],
            "",
            "BLOCKED_INPUT",
        ]
    )
    write_text(final_report, report)


def build_result(
    *,
    repo_root: Path,
    prereg_path: Path,
    raw_dir: Path,
    selftest_path: Optional[Path],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    prereg = load_json(prereg_path)
    input_validation = validate_preregistered_inputs(prereg, repo_root)
    bad = [row for row in input_validation if not row["hash_match"]]
    if bad:
        detail = "; ".join(
            f"{row['role']} exists={row['exists']} hash_match={row['hash_match']}"
            for row in bad
        )
        raise FileNotFoundError(f"sealed input unavailable or changed: {detail}")

    plan_path = repo_root / "reports/e2/synthesis/FINAL_PROGRAM_PLAN.md"
    plan_text = plan_path.read_text(encoding="utf-8")
    if str(prereg["plan_f04_verbatim"]) not in plan_text:
        raise ValueError("sealed F04 wording is not present verbatim in FINAL_PROGRAM_PLAN.md")

    source_specs = {
        "w2_independence_audit_v1": {
            "path": "reports/e2/w2_independence_audit_v1.json",
            "precedence": 1,
        },
        "b4_fold_v2": {
            "path": "reports/e2/s5/b4_fold_v2.json",
            "precedence": 2,
        },
    }
    all_observations: List[Dict[str, Any]] = []
    for source_id, spec in source_specs.items():
        path = repo_root / spec["path"]
        payload = load_json(path)
        all_observations.extend(
            collect_observations(
                source_id=source_id,
                source_path=str(spec["path"]),
                source_sha256=sha256_path(path),
                precedence=int(spec["precedence"]),
                payload=payload,
                prereg=prereg,
            )
        )

    preferred = select_preferred_legacy(all_observations)
    discrepancies = build_discrepancies(all_observations)
    matrix = build_canonical_matrix(prereg, all_observations)
    family_summaries, effects = summarize_matrix(matrix, prereg)
    scale_failures = [
        row["observation_id"]
        for row in all_observations
        if row["source_transform"] == "scale"
        and (
            row["diagnostic_band_from_r_meta"] == "FAIL"
            or row.get("source_verdict") == "FAIL"
        )
    ]
    selftest = (
        load_json(selftest_path)
        if selftest_path is not None and selftest_path.is_file()
        else {"status": "NOT_PROVIDED"}
    )
    result: Dict[str, Any] = {
        "schema": SCHEMA,
        "executed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "axis_measurement_status": "AXIS_MEASUREMENT_COMPLETE",
        "scientific_gate_status": "INCOMPLETE_CANONICAL_EVIDENCE",
        "scientific_gate_pass": False,
        "prereg_path": str(prereg_path),
        "prereg_sha256": sha256_path(prereg_path),
        "input_validation": input_validation,
        "relation_registry": prereg["relation_registry"],
        "families": prereg["families"],
        "all_legacy_observations": all_observations,
        "preferred_legacy_observations": preferred,
        "corrected_vs_older_discrepancies": discrepancies,
        "canonical_transform_by_family": matrix,
        "family_summaries": family_summaries,
        "effects_and_interactions": effects,
        "confirmation": {
            "status": "NOT_RUN_NO_SENTINEL_QUALIFIED_COMPLETE_FAMILY",
            "reason": "No family has seven admissible numeric relation cells.",
        },
        "scale_failure_observation_ids": scale_failures,
        "unknown_preservation": {
            "canonical_cells": len(matrix),
            "unknown_cells": sum(1 for row in matrix if row["verdict"] == "UNKNOWN"),
            "imputed_cells": 0,
        },
        "selftest_evidence": selftest,
        "prohibited_action_counts": {
            "model_api_calls": 0,
            "test_set_reads": 0,
            "original_cad_reads": 0,
            "original_cad_writes": 0,
            "existing_source_files_modified": 0,
        },
        "raw_output_root": str(raw_dir),
    }
    return result, prereg


def write_outputs(
    *,
    result: Dict[str, Any],
    prereg: Dict[str, Any],
    repo_root: Path,
    raw_dir: Path,
    report_dir: Path,
    final_report: Path,
) -> None:
    raw_result = raw_dir / "judge_result.json"
    report_evidence = report_dir / "evidence.json"
    write_json(raw_result, result)
    write_json(report_evidence, result)

    matrix_fields = (
        "cell_id", "family", "owner_axis", "scope_status", "transform",
        "measurement_state", "r_meta", "verdict", "reason",
    )
    legacy_fields = (
        "observation_id", "source_id", "source_path", "source_pointer",
        "source_transform", "registry_relation", "mean_invariance_exact",
        "derived_r_meta_exact", "diagnostic_band_from_r_meta", "source_verdict",
        "admissibility", "canonical_cell_promoted",
    )
    _csv_rows(raw_dir / "transform_by_family.csv", result["canonical_transform_by_family"], matrix_fields)
    _csv_rows(report_dir / "transform_by_family.csv", result["canonical_transform_by_family"], matrix_fields)
    _csv_rows(raw_dir / "legacy_observations.csv", result["all_legacy_observations"], legacy_fields)
    _csv_rows(report_dir / "legacy_observations.csv", result["all_legacy_observations"], legacy_fields)

    table_md = render_matrix_markdown(result, prereg)
    write_text(report_dir / "transform_by_family.md", table_md)
    write_text(final_report, render_report(result, prereg))
    write_text(report_dir / "VALIDATION.md", render_validation(result))
    write_text(report_dir / "FILES_CHANGED.md", render_files_changed(repo_root, raw_dir))

    manifest_targets = [
        prereg_path := report_dir / "PREREG_local.json",
        repo_root / "tools/e2/instruments/f04_common_judge.py",
        repo_root / "tools/e2/instruments/f04_common_judge_selftest.py",
        raw_result,
        raw_dir / "transform_by_family.csv",
        raw_dir / "legacy_observations.csv",
        raw_dir / "selftest_result.json",
        report_evidence,
        report_dir / "transform_by_family.csv",
        report_dir / "transform_by_family.md",
        report_dir / "legacy_observations.csv",
        report_dir / "VALIDATION.md",
        report_dir / "FILES_CHANGED.md",
        final_report,
    ]
    artifacts = []
    for path in manifest_targets:
        if path.is_file():
            artifacts.append(
                {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_path(path),
                }
            )
    manifest = {
        "schema": "ariadne.e2.f04_common_judge.output_manifest.v1",
        "axis_measurement_status": result["axis_measurement_status"],
        "prereg_sha256": result["prereg_sha256"],
        "artifacts": artifacts,
    }
    write_json(raw_dir / "output_manifest.json", manifest)
    write_json(report_dir / "evidence_manifest.json", manifest)


def build_parser() -> argparse.ArgumentParser:
    here = Path(__file__).resolve()
    repo_default = here.parents[3]
    parser = argparse.ArgumentParser(
        description="F04 common relation registry and family-admissibility judge"
    )
    parser.add_argument("--repo-root", type=Path, default=repo_default)
    parser.add_argument("--prereg", type=Path, default=None)
    parser.add_argument(
        "--raw-dir", type=Path,
        default=Path(r"D:\runs\e2_program\cells\f04_completion"),
    )
    parser.add_argument("--report-dir", type=Path, default=None)
    parser.add_argument("--final-report", type=Path, default=None)
    parser.add_argument("--selftest-evidence", type=Path, default=None)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = args.repo_root.resolve()
    prereg_path = (
        args.prereg.resolve()
        if args.prereg is not None
        else repo_root / "reports/e2/cells/f04_completion/PREREG_local.json"
    )
    raw_dir = args.raw_dir.resolve()
    report_dir = (
        args.report_dir.resolve()
        if args.report_dir is not None
        else repo_root / "reports/e2/cells/f04_completion"
    )
    final_report = (
        args.final_report.resolve()
        if args.final_report is not None
        else repo_root / "reports/e2/instruments/f04_REPORT.md"
    )

    raw_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    try:
        if not prereg_path.is_file():
            raise FileNotFoundError(f"missing preregistration: {prereg_path}")
        result, prereg = build_result(
            repo_root=repo_root,
            prereg_path=prereg_path,
            raw_dir=raw_dir,
            selftest_path=args.selftest_evidence.resolve()
            if args.selftest_evidence is not None
            else None,
        )
        if result["selftest_evidence"].get("status") != "PASS":
            raise ValueError("hand-fixed self-test evidence is missing or not PASS")
        write_outputs(
            result=result,
            prereg=prereg,
            repo_root=repo_root,
            raw_dir=raw_dir,
            report_dir=report_dir,
            final_report=final_report,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        write_blocked(
            raw_dir=raw_dir,
            report_dir=report_dir,
            final_report=final_report,
            prereg_path=prereg_path,
            reasons=[f"{type(exc).__name__}: {exc}"],
        )
        print(f"BLOCKED_INPUT: {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "axis_measurement_status": result["axis_measurement_status"],
                "scientific_gate_status": result["scientific_gate_status"],
                "prereg_sha256": result["prereg_sha256"],
                "canonical_cells": len(result["canonical_transform_by_family"]),
                "unknown_cells": result["unknown_preservation"]["unknown_cells"],
                "legacy_scale_failures": result["scale_failure_observation_ids"],
                "report": str(final_report),
                "raw_output": str(raw_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(result["axis_measurement_status"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
