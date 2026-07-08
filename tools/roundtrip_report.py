#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build ALM-style roundtrip fidelity reports from capstone run artifacts."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

REPORT_SCHEMA = "ariadne.roundtrip_report.v1"
RULE_KIND_DRIFT = "R_KIND_DRIFT_POLYLINE_LWPOLYLINE"
RULE_DEFERRED_BLOCK_DEF = "R_DEFERRED_BLOCK_DEF"
KIND_DRIFT_NOTE = (
    "AutoCAD regenerates 2D polylines as LWPOLYLINE; geometric content preserved - "
    "candidate harmless pending human ratification"
)
DEFERRED_BLOCK_DEF_NOTE = "Deferred op references a missing block definition; real fidelity loss."
HARMLESS_RULES = [
    {
        "id": RULE_KIND_DRIFT,
        "note": KIND_DRIFT_NOTE,
    },
    {
        "id": RULE_DEFERRED_BLOCK_DEF,
        "match": "no block_definitions entry",
        "judgment": "harmful",
        "note": DEFERRED_BLOCK_DEF_NOTE,
    },
]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_run(run_dir) -> dict:
    """Load known capstone run artifacts, returning ``None`` for missing files."""
    base = Path(run_dir)
    file_map = {
        "census_report": "census_report.json",
        "verdict": "verdict.json",
        "regen_summary": "regen_summary.json",
        "deferred": "deferred.json",
        "summary": "summary.json",
    }
    loaded = {}
    for key, filename in file_map.items():
        path = base / filename
        loaded[key] = _load_json(path) if path.is_file() else None
    return loaded


def naive_count_verdict(verdict) -> dict:
    """Return the deliberately weak foil verdict.

    This foil is blind to moved/relabeled entities that manifest as one removed
    plus one added of the same dxf_name, and blind to modifications; it exists
    so reports can show smart-vs-naive contrast (a gate that cannot fail is not
    a gate).
    """
    rows_out = []
    for row in (verdict or {}).get("rows") or []:
        naive_pass = int(row.get("added_count", 0) or 0) == int(row.get("removed_count", 0) or 0)
        rows_out.append(
            {
                "dxf_name": row.get("dxf_name"),
                "naive_pass": naive_pass,
                "added_count": int(row.get("added_count", 0) or 0),
                "removed_count": int(row.get("removed_count", 0) or 0),
                "modified_count": int(row.get("modified_count", 0) or 0),
            }
        )
    return {
        "rows": rows_out,
        "naive_pass": all(row["naive_pass"] for row in rows_out),
    }


def _normalize_rules(harmless_rules) -> dict[str, dict]:
    rules = harmless_rules or HARMLESS_RULES
    merged = {rule["id"]: dict(rule) for rule in HARMLESS_RULES}
    for rule in rules:
        if "id" in rule:
            merged[rule["id"]] = dict(rule)
    return merged


def _context_from_layer(layer: Any) -> str:
    text = str(layer or "").strip()
    if not text:
        return "layer:unspecified"
    for sep in ("|", "/", ":"):
        if sep in text:
            text = text.split(sep, 1)[0].strip()
            break
    return f"layer:{text or 'unspecified'}"


def _context_from_reason(reason: Any) -> str:
    text = " ".join(str(reason or "").strip().split())
    return f"reason:{text or 'unspecified'}"


def _make_signature(dxf_name: Any, change: str, context: str) -> tuple[str, str, str]:
    return (str(dxf_name or "UNKNOWN"), str(change or "unknown"), str(context or "unspecified"))


def _make_pattern(signature: tuple[str, str, str]) -> dict:
    return {
        "signature": {
            "dxf_name": signature[0],
            "change": signature[1],
            "context": signature[2],
        },
        "count": 0,
        "examples": [],
        "judgment": "unreviewed",
        "rule_id": None,
        "note": "",
    }


def _record_pattern_entry(patterns: dict, signature: tuple[str, str, str], example: dict | None, count: int = 1) -> None:
    pattern = patterns.setdefault(signature, _make_pattern(signature))
    pattern["count"] += int(count)
    if example is not None and len(pattern["examples"]) < 3:
        pattern["examples"].append(example)


def classify_patterns(verdict, deferred, harmless_rules=None) -> list[dict]:
    """Group verdict examples and deferred entries into reviewable diff patterns."""
    patterns: dict[tuple[str, str, str], dict] = {}
    rules = _normalize_rules(harmless_rules)

    for row in (verdict or {}).get("rows") or []:
        dxf_name = row.get("dxf_name", "UNKNOWN")
        examples_by_change = row.get("examples") or {}
        for change in ("modified", "removed", "added"):
            total = int(row.get(f"{change}_count", 0) or 0)
            if total <= 0:
                continue
            examples = list(examples_by_change.get(change) or [])
            for example in examples:
                signature = _make_signature(
                    example.get("dxf_name", dxf_name),
                    change,
                    _context_from_layer(example.get("layer")),
                )
                _record_pattern_entry(patterns, signature, dict(example), 1)
            remainder = total - len(examples)
            if remainder > 0:
                signature = _make_signature(dxf_name, change, "layer:unspecified")
                _record_pattern_entry(
                    patterns,
                    signature,
                    {
                        "change": change,
                        "dxf_name": dxf_name,
                        "layer": None,
                        "synthetic": True,
                    },
                    remainder,
                )

    for entry in deferred or []:
        dxf_name = entry.get("dxf_name") or entry.get("kind") or "UNKNOWN"
        reason = entry.get("reason")
        signature = _make_signature(dxf_name, "deferred", _context_from_reason(reason))
        _record_pattern_entry(patterns, signature, dict(entry), 1)

    kind_drift_note = rules.get(RULE_KIND_DRIFT, {}).get("note", KIND_DRIFT_NOTE)
    grouped_by_context: dict[str, dict[str, dict]] = {}
    for pattern in patterns.values():
        context = pattern["signature"]["context"]
        grouped_by_context.setdefault(context, {})[
            (pattern["signature"]["dxf_name"], pattern["signature"]["change"])
        ] = pattern
    for siblings in grouped_by_context.values():
        removed_polyline = siblings.get(("POLYLINE", "removed"))
        added_lwpolyline = siblings.get(("LWPOLYLINE", "added"))
        if removed_polyline and added_lwpolyline and removed_polyline["count"] == added_lwpolyline["count"]:
            removed_polyline["judgment"] = "harmless"
            removed_polyline["rule_id"] = RULE_KIND_DRIFT
            removed_polyline["note"] = kind_drift_note
            added_lwpolyline["judgment"] = "harmless"
            added_lwpolyline["rule_id"] = RULE_KIND_DRIFT
            added_lwpolyline["note"] = kind_drift_note

    block_def_rule = rules.get(RULE_DEFERRED_BLOCK_DEF, {})
    match_text = str(block_def_rule.get("match", "no block_definitions entry")).lower()
    block_def_note = block_def_rule.get("note", DEFERRED_BLOCK_DEF_NOTE)
    for pattern in patterns.values():
        if pattern["judgment"] != "unreviewed":
            continue
        if pattern["signature"]["change"] != "deferred":
            continue
        context = pattern["signature"]["context"].lower()
        if match_text in context:
            pattern["judgment"] = "harmful"
            pattern["rule_id"] = RULE_DEFERRED_BLOCK_DEF
            pattern["note"] = block_def_note

    return sorted(
        patterns.values(),
        key=lambda item: (
            item["signature"]["dxf_name"],
            item["signature"]["change"],
            item["signature"]["context"],
        ),
    )


def kind_buckets(census_report, verdict) -> dict:
    """Summarize per-kind PASS/FAIL/VACUOUS status from census certification and verdict rows."""
    census_report = census_report or {}
    verdict = verdict or {}
    row_by_name = {row.get("dxf_name"): row for row in verdict.get("rows") or []}
    buckets = {}

    for bucket in census_report.get("by_bucket") or []:
        if not bucket.get("certified"):
            continue
        dxf_name = bucket.get("dxf_name")
        row = row_by_name.get(dxf_name) or {}
        attempted = int(row.get("regen_attempted_count", 0) or 0)
        diff0 = int(row.get("diff0_count", 0) or 0)
        if attempted > 0:
            status = "PASS" if diff0 == attempted else "FAIL"
        else:
            status = "VACUOUS"
        buckets[dxf_name] = {
            "status": status,
            "certified": True,
            "label": bucket.get("label"),
            "kind": bucket.get("kind"),
            "census_count": int(bucket.get("count", 0) or 0),
            "attempted_count": attempted,
            "diff0_count": diff0,
            "modified_count": int(row.get("modified_count", 0) or 0),
            "removed_count": int(row.get("removed_count", 0) or 0),
            "added_count": int(row.get("added_count", 0) or 0),
        }

    for dxf_name, row in row_by_name.items():
        if dxf_name in buckets:
            continue
        attempted = int(row.get("regen_attempted_count", 0) or 0)
        diff0 = int(row.get("diff0_count", 0) or 0)
        if attempted > 0:
            status = "PASS" if diff0 == attempted else "FAIL"
        else:
            status = "VACUOUS"
        buckets[dxf_name] = {
            "status": status,
            "certified": False,
            "label": None,
            "kind": None,
            "census_count": 0,
            "attempted_count": attempted,
            "diff0_count": diff0,
            "modified_count": int(row.get("modified_count", 0) or 0),
            "removed_count": int(row.get("removed_count", 0) or 0),
            "added_count": int(row.get("added_count", 0) or 0),
        }

    return dict(sorted(buckets.items()))


def _smart_all_diff0(verdict: dict | None) -> bool:
    totals = (verdict or {}).get("totals") or {}
    attempted = int(totals.get("regen_attempted_count", 0) or 0)
    diff0 = int(totals.get("diff0_count", 0) or 0)
    return attempted > 0 and attempted == diff0


def build_report(run_dir, harmless_rules=None) -> dict:
    """Build the machine-readable roundtrip report for one capstone run directory."""
    run = load_run(run_dir)
    census = run.get("census_report") or {}
    verdict = run.get("verdict") or {}
    deferred = run.get("deferred") or []
    summary = run.get("summary") or {}
    source = (summary.get("staged") or {}).copy()
    patterns = classify_patterns(verdict, deferred, harmless_rules=harmless_rules)
    naive = naive_count_verdict(verdict)
    smart_all_diff0 = _smart_all_diff0(verdict)

    if naive["naive_pass"] and not smart_all_diff0:
        contrast_note = "Naive foil passes while smart diff0 gate fails; the foil is blind to moves and modifications."
    elif naive["naive_pass"] and smart_all_diff0:
        contrast_note = "Naive foil and smart diff0 gate both pass on this run."
    else:
        contrast_note = "Naive foil already fails; smart diff0 gate remains the authoritative ceiling-aware verdict."

    harmful_count = sum(1 for pattern in patterns if pattern["judgment"] == "harmful")
    harmless_count = sum(1 for pattern in patterns if pattern["judgment"] == "harmless")
    unreviewed_count = sum(1 for pattern in patterns if pattern["judgment"] == "unreviewed")

    return {
        "schema": REPORT_SCHEMA,
        "run_dir": str(Path(run_dir)),
        "source": source,
        "ceiling": {
            "modelspace_entity_total": int(census.get("modelspace_entity_total", 0) or 0),
            "certified_total": int(census.get("certified_total", 0) or 0),
            "out_of_class_total": int(census.get("out_of_class_total", 0) or 0),
            "deferred_count": len(deferred),
        },
        "kind_buckets": kind_buckets(census, verdict),
        "patterns": patterns,
        "naive_vs_smart": {
            "naive_pass": naive["naive_pass"],
            "smart_all_diff0": smart_all_diff0,
            "contrast_note": contrast_note,
        },
        "totals": {
            **((verdict or {}).get("totals") or {}),
            "deferred_count": len(deferred),
            "pattern_count": len(patterns),
            "harmful_pattern_count": harmful_count,
            "harmless_pattern_count": harmless_count,
            "unreviewed_pattern_count": unreviewed_count,
        },
    }


def _status_counts(kind_bucket_map: dict) -> dict[str, int]:
    counts = {"PASS": 0, "FAIL": 0, "VACUOUS": 0}
    for bucket in kind_bucket_map.values():
        status = bucket.get("status")
        if status in counts:
            counts[status] += 1
    return counts


def _format_signature(signature: dict) -> str:
    return f"{signature.get('dxf_name')} / {signature.get('change')} / {signature.get('context')}"


def render_markdown(report) -> str:
    """Render the report as a concise human-readable Markdown summary."""
    lines = ["# Roundtrip Fidelity Report", ""]

    source = report.get("source") or {}
    lines.extend(
        [
            "## Source + SHA",
            f"- Original path: `{source.get('original_path', '')}`",
            f"- Original sha256: `{source.get('original_sha256', '')}`",
            f"- Staged sha256: `{source.get('staged_sha256', '')}`",
            "",
        ]
    )

    ceiling = report.get("ceiling") or {}
    lines.extend(
        [
            "## Honest ceiling",
            f"- Modelspace entities: {ceiling.get('modelspace_entity_total', 0)}",
            f"- Certified total: {ceiling.get('certified_total', 0)}",
            f"- Out-of-class total: {ceiling.get('out_of_class_total', 0)}",
            f"- Deferred count: {ceiling.get('deferred_count', 0)}",
            "",
        ]
    )

    buckets = report.get("kind_buckets") or {}
    counts = _status_counts(buckets)
    lines.extend(
        [
            "## Per-kind verdict table",
            f"PASS: {counts['PASS']} | FAIL: {counts['FAIL']} | VACUOUS: {counts['VACUOUS']}",
            "",
            "| DXF Name | Certified | Census | Attempted | Diff0 | Status |",
            "| --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    if buckets:
        for dxf_name, bucket in buckets.items():
            lines.append(
                "| {dxf} | {certified} | {census} | {attempted} | {diff0} | {status} |".format(
                    dxf=dxf_name,
                    certified="yes" if bucket.get("certified") else "no",
                    census=bucket.get("census_count", 0),
                    attempted=bucket.get("attempted_count", 0),
                    diff0=bucket.get("diff0_count", 0),
                    status=bucket.get("status", ""),
                )
            )
    else:
        lines.append("| (none) | no | 0 | 0 | 0 | VACUOUS |")
    lines.append("")

    patterns = report.get("patterns") or []
    lines.extend(
        [
            "## Diff patterns table",
            "| Signature | Count | Judgment | Note |",
            "| --- | ---: | --- | --- |",
        ]
    )
    if patterns:
        for pattern in patterns:
            lines.append(
                "| {signature} | {count} | {judgment} | {note} |".format(
                    signature=_format_signature(pattern.get("signature") or {}),
                    count=pattern.get("count", 0),
                    judgment=pattern.get("judgment", ""),
                    note=pattern.get("note", ""),
                )
            )
    else:
        lines.append("| (none) | 0 | unreviewed | |")
    lines.append("")

    naive = report.get("naive_vs_smart") or {}
    lines.extend(
        [
            "## Naive-foil vs smart contrast",
            f"- naive_pass: `{naive.get('naive_pass', False)}`",
            f"- smart_all_diff0: `{naive.get('smart_all_diff0', False)}`",
            f"- note: {naive.get('contrast_note', '')}",
            "",
        ]
    )

    run_dir = Path(report.get("run_dir") or ".")
    evidence_files = [
        "summary.json",
        "census_report.json",
        "verdict.json",
        "regen_summary.json",
        "deferred.json",
    ]
    lines.append("## Evidence paths")
    for name in evidence_files:
        lines.append(f"- `{run_dir / name}`")
    lines.append("")

    return "\n".join(lines)


def _load_harmless_rules_arg(path: str | None):
    if not path:
        return None
    return _load_json(Path(path))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build roundtrip fidelity JSON and Markdown reports.")
    parser.add_argument("--run-dir", required=True, help="Capstone run directory.")
    parser.add_argument("--out-json", required=True, help="Machine-readable output JSON path.")
    parser.add_argument("--out-md", required=True, help="Human-readable output Markdown path.")
    parser.add_argument("--harmless-rules", help="Optional JSON file overriding harmless/harmful rules.")
    parser.add_argument("--strict", action="store_true", help="Exit 3 if any harmful pattern is present.")
    args = parser.parse_args(argv)

    rules = _load_harmless_rules_arg(args.harmless_rules)
    report = build_report(args.run_dir, harmless_rules=rules)
    _write_json(Path(args.out_json), report)
    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_md).write_text(render_markdown(report), encoding="utf-8")

    if args.strict and any(pattern.get("judgment") == "harmful" for pattern in report.get("patterns") or []):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
