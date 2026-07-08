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

from full_roundtrip_capstone import CERTIFIED_BUCKETS

REPORT_SCHEMA = "ariadne.roundtrip_report.v1"
RULE_KIND_DRIFT = "R_KIND_DRIFT_POLYLINE_LWPOLYLINE"
RULE_DEFERRED_BLOCK_DEF = "R_DEFERRED_BLOCK_DEF"
CERTIFIED_DXF_NAMES = {dxf_name for (dxf_name, _kind) in CERTIFIED_BUCKETS}
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


def _status_from_counts(attempted: int, diff0: int) -> str:
    if attempted > 0:
        return "PASS" if diff0 == attempted else "FAIL"
    return "VACUOUS"


def _def_entity_budget(summary, census_report) -> dict | None:
    summary = summary or {}
    census_report = census_report or {}
    budget = summary.get("def_entity_budget")
    if budget is None:
        return None

    dropped_defs = []
    for entry in budget.get("dropped_block_definitions") or []:
        dropped_defs.append(
            {
                "name": entry.get("name"),
                "def_entity_count": int(entry.get("def_entity_count", 0) or 0),
            }
        )
    dropped_defs.sort(key=lambda item: (-item["def_entity_count"], str(item.get("name") or "")))

    dropped_def_entity_total = sum(item["def_entity_count"] for item in dropped_defs)
    census_total = int(census_report.get("block_definitions_entity_total", 0) or 0)
    dropped_pct = round((dropped_def_entity_total / census_total) * 100, 1) if census_total else None

    max_budget = budget.get("max_def_entities_per_block")
    if max_budget is not None:
        max_budget = int(max_budget)

    return {
        "max_def_entities_per_block": max_budget,
        "dropped_def_count": len(dropped_defs),
        "dropped_def_entity_total": dropped_def_entity_total,
        "dropped_defs": dropped_defs,
        "dropped_pct_of_block_def_entities": dropped_pct,
    }


def _per_layer_rollup(verdict) -> dict:
    verdict = verdict or {}
    per_layer: dict[str, dict[str, int]] = {}
    for row in verdict.get("rows") or []:
        examples_by_change = row.get("examples") or {}
        for change in ("removed", "added", "modified"):
            for example in examples_by_change.get(change) or []:
                layer = str(example.get("layer") or "unspecified")
                bucket = per_layer.setdefault(layer, {"removed": 0, "added": 0, "modified": 0})
                bucket[change] += 1
    return dict(sorted(per_layer.items()))


def kind_buckets(census_report, verdict) -> dict:
    """Summarize per-kind PASS/FAIL/VACUOUS status from census certification and verdict rows."""
    census_report = census_report or {}
    verdict = verdict or {}
    row_by_name = {row.get("dxf_name"): row for row in verdict.get("rows") or []}
    buckets = {}
    census_names = {bucket.get("dxf_name") for bucket in census_report.get("by_bucket") or []}

    for bucket in census_report.get("by_bucket") or []:
        if not bucket.get("certified"):
            continue
        dxf_name = bucket.get("dxf_name")
        row = row_by_name.get(dxf_name) or {}
        attempted = int(row.get("regen_attempted_count", 0) or 0)
        diff0 = int(row.get("diff0_count", 0) or 0)
        attempted_live = int(row.get("attempted_live_count", attempted) or attempted)
        deferred_count = int(row.get("deferred_count", 0) or 0)
        buckets[dxf_name] = {
            "status": _status_from_counts(attempted, diff0),
            "certified": True,
            "label": bucket.get("label"),
            "kind": bucket.get("kind"),
            "census_count": int(bucket.get("count", 0) or 0),
            "attempted_count": attempted,
            "attempted_live_count": attempted_live,
            "deferred_count": deferred_count,
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
        attempted_live = int(row.get("attempted_live_count", attempted) or attempted)
        deferred_count = int(row.get("deferred_count", 0) or 0)
        buckets[dxf_name] = {
            "status": _status_from_counts(attempted, diff0),
            "certified": False,
            "label": None,
            "kind": None,
            "census_count": 0,
            "attempted_count": attempted,
            "attempted_live_count": attempted_live,
            "deferred_count": deferred_count,
            "diff0_count": diff0,
            "modified_count": int(row.get("modified_count", 0) or 0),
            "removed_count": int(row.get("removed_count", 0) or 0),
            "added_count": int(row.get("added_count", 0) or 0),
        }

    for dxf_name in CERTIFIED_DXF_NAMES:
        if dxf_name in census_names or dxf_name in row_by_name or dxf_name in buckets:
            continue
        buckets[dxf_name] = {
            "status": "VACUOUS",
            "certified": True,
            "label": None,
            "kind": None,
            "census_count": 0,
            "attempted_count": 0,
            "attempted_live_count": 0,
            "deferred_count": 0,
            "diff0_count": 0,
            "modified_count": 0,
            "removed_count": 0,
            "added_count": 0,
            "absent_from_drawing": True,
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
    ceiling = {
        "modelspace_entity_total": int(census.get("modelspace_entity_total", 0) or 0),
        "certified_total": int(census.get("certified_total", 0) or 0),
        "out_of_class_total": int(census.get("out_of_class_total", 0) or 0),
        "deferred_count": len(deferred),
    }
    def_entity_budget = _def_entity_budget(summary, census)
    if def_entity_budget is not None:
        ceiling["def_entity_budget"] = def_entity_budget

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
        "ceiling": ceiling,
        "kind_buckets": kind_buckets(census, verdict),
        "per_layer": _per_layer_rollup(verdict),
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
        ]
    )
    def_entity_budget = ceiling.get("def_entity_budget")
    if def_entity_budget is not None:
        dropped_pct = def_entity_budget.get("dropped_pct_of_block_def_entities")
        lines.extend(
            [
                "",
                "### Deferred block-definition budget",
                f"- Max def entities per block: {def_entity_budget.get('max_def_entities_per_block')}",
                f"- Dropped definitions: {def_entity_budget.get('dropped_def_count', 0)}",
                f"- Dropped def entities: {def_entity_budget.get('dropped_def_entity_total', 0)}",
                f"- Dropped pct of block-def entities: {'n/a' if dropped_pct is None else f'{dropped_pct:.1f}%'}",
            ]
        )
        dropped_defs = def_entity_budget.get("dropped_defs") or []
        if dropped_defs:
            lines.extend(
                [
                    "",
                    "| Block definition | Def entities |",
                    "| --- | ---: |",
                ]
            )
            for entry in dropped_defs:
                lines.append(
                    "| {name} | {count} |".format(
                        name=entry.get("name"),
                        count=entry.get("def_entity_count", 0),
                    )
                )
    lines.append("")

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
            attempted = bucket.get("attempted_count", 0)
            attempted_live = bucket.get("attempted_live_count", attempted)
            deferred_count = bucket.get("deferred_count", 0)
            lines.append(
                "| {dxf} | {certified} | {census} | {attempted} | {diff0} | {status} |".format(
                    dxf=dxf_name,
                    certified="yes" if bucket.get("certified") else "no",
                    census=bucket.get("census_count", 0),
                    attempted=f"{attempted} (live {attempted_live})",
                    diff0=bucket.get("diff0_count", 0),
                    status=f"{bucket.get('status', '')} [deferred {deferred_count}]",
                )
            )
    else:
        lines.append("| (none) | no | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |")
    lines.append("")

    per_layer = report.get("per_layer") or {}
    lines.extend(
        [
            "## Per-layer example rollup",
            "- Aggregated from verdict examples only; if row totals exceed recorded examples, this table is a sample rather than a full census.",
            "| Layer | Removed | Added | Modified | Total |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    ranked_layers = sorted(
        per_layer.items(),
        key=lambda item: (
            -(item[1].get("removed", 0) + item[1].get("added", 0) + item[1].get("modified", 0)),
            item[0],
        ),
    )[:20]
    if ranked_layers:
        for layer, counts_by_change in ranked_layers:
            total = (
                counts_by_change.get("removed", 0)
                + counts_by_change.get("added", 0)
                + counts_by_change.get("modified", 0)
            )
            lines.append(
                "| {layer} | {removed} | {added} | {modified} | {total} |".format(
                    layer=layer,
                    removed=counts_by_change.get("removed", 0),
                    added=counts_by_change.get("added", 0),
                    modified=counts_by_change.get("modified", 0),
                    total=total,
                )
            )
    else:
        lines.append("| (none) | 0 | 0 | 0 | 0 |")
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
