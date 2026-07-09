#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cluster block-interior residuals from an ariadne.blockdef_diff.v1 report.

Groups per_def rows that still mismatch after diff0 matching into
mechanical signature buckets (def-name family, dominant missing-side
entity kind if present, residual-count bucket) and ranks the clusters
by total residual entity count.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_ID = "ariadne.blockdef_diff.v1"

_ANON_PREFIX_RE = re.compile(r"^\*([A-Za-z]+)\d*")

FAMILY_TEXT = {
    "anon_dimension": "anon dimension-block family (*D / ARIADNE_ANON_D)",
    "anon_other": "anon non-dimension block family (*U/other anon prefix)",
    "dynamic_instance": "dynamic-block anonymous-instance family ($N suffix)",
    "named": "named block family",
}

SHAPE_LABEL = {
    "a_only": "a_only",
    "b_only": "b_only",
    "mutated": "mutated",
    "mixed": "mixed (single def with >1 residual kind)",
    "none": "none",
}


def classify_family(name: str, b_name: Optional[str] = None) -> str:
    for cand in (name, b_name):
        if not cand:
            continue
        m = _ANON_PREFIX_RE.match(cand)
        if m:
            return "anon_dimension" if m.group(1).upper() == "D" else "anon_other"
        if cand.startswith("ARIADNE_ANON_D"):
            return "anon_dimension"
    for cand in (name, b_name):
        if cand and "$" in cand:
            return "dynamic_instance"
    return "named"


def count_bucket(n: int) -> str:
    if n <= 0:
        return "0"
    if n < 10:
        return "1-9"
    if n < 100:
        return "10-99"
    if n < 1000:
        return "100-999"
    return "1000+"


def residual_total(row: Dict[str, Any]) -> int:
    return (int(row.get("removed", 0) or 0)
            + int(row.get("added", 0) or 0)
            + int(row.get("modified", 0) or 0))


def is_residual(row: Dict[str, Any]) -> bool:
    return residual_total(row) > 0


def dominant_kind(row: Dict[str, Any]) -> Optional[Tuple[str, int]]:
    """Dominant entity kind among the side that dominates the residual, if the
    row carries optional a_only_kinds/b_only_kinds breakdown dicts. The
    current blockdef_diff.py generator does not emit these (per-def rows have
    no kind breakdown); this supports report variants that do.
    """
    removed = int(row.get("removed", 0) or 0)
    added = int(row.get("added", 0) or 0)
    a_kinds = row.get("a_only_kinds") or None
    b_kinds = row.get("b_only_kinds") or None
    side_kinds = a_kinds if (removed >= added and a_kinds) else (b_kinds or a_kinds)
    if not side_kinds:
        return None
    kind_name, kind_count = max(side_kinds.items(), key=lambda kv: kv[1])
    return (kind_name, int(kind_count))


def shape_of(removed: int, added: int, modified: int) -> str:
    nonzero = [label for label, v in (("a_only", removed), ("b_only", added), ("mutated", modified)) if v > 0]
    if not nonzero:
        return "none"
    if len(nonzero) == 1:
        return nonzero[0]
    return "mixed"


Signature = Tuple[str, Optional[str], str]


def signature(row: Dict[str, Any]) -> Signature:
    family = classify_family(row.get("name", ""), row.get("b_name"))
    dk = dominant_kind(row)
    kind_name = dk[0] if dk else None
    bucket = count_bucket(residual_total(row))
    return (family, kind_name, bucket)


def cluster_residuals(per_def: List[Dict[str, Any]]) -> Dict[Signature, List[Dict[str, Any]]]:
    clusters: Dict[Signature, List[Dict[str, Any]]] = {}
    for row in per_def:
        if not is_residual(row):
            continue
        clusters.setdefault(signature(row), []).append(row)
    return clusters


def _cluster_label(sig: Signature) -> str:
    family, kind_name, bucket = sig
    label = f"{family}/{bucket}"
    if kind_name:
        label += f"/{kind_name}"
    return label


def build_hypothesis(family: str, dominant: Optional[Tuple[str, int]],
                      shape_breakdown: List[Tuple[str, int]],
                      n_defs: int, n_entities: int, bucket: str) -> str:
    shape_text = ", ".join(f"{cnt} defs {SHAPE_LABEL[shape]}" for shape, cnt in shape_breakdown)
    text = (f"{FAMILY_TEXT[family]}; {n_defs} defs / {n_entities} entities "
            f"[bucket {bucket}]; shape breakdown: {shape_text}")
    if dominant:
        kind_name, kind_count = dominant
        text += f"; dominant missing-side kind={kind_name} ({kind_count}) -> {kind_name}-heavy"
    return text


def summarize_clusters(clusters: Dict[Signature, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    table: List[Dict[str, Any]] = []
    for sig, rows in clusters.items():
        family, kind_name, bucket = sig
        n_defs = len(rows)
        n_entities = sum(residual_total(r) for r in rows)

        shape_counts = Counter(
            shape_of(int(r.get("removed", 0) or 0), int(r.get("added", 0) or 0), int(r.get("modified", 0) or 0))
            for r in rows
        )
        shape_breakdown = sorted(shape_counts.items(), key=lambda kv: (-kv[1], kv[0]))

        dominant: Optional[Tuple[str, int]] = None
        if kind_name:
            kind_count = sum(dk[1] for dk in (dominant_kind(r) for r in rows)
                              if dk and dk[0] == kind_name)
            dominant = (kind_name, kind_count)

        table.append({
            "cluster": _cluster_label(sig),
            "defs": n_defs,
            "entities": n_entities,
            "hypothesis": build_hypothesis(family, dominant, shape_breakdown, n_defs, n_entities, bucket),
        })

    table.sort(key=lambda row: (-row["entities"], -row["defs"], row["cluster"]))
    return table


def build_report_table(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    per_def = report.get("per_def") or []
    clusters = cluster_residuals(per_def)
    return summarize_clusters(clusters)


def _md_table(headers: List[str], rows: List[List[Any]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")
    return "\n".join(out)


def render_markdown(table: List[Dict[str, Any]], report: Dict[str, Any], source_path: str) -> str:
    totals = report.get("totals") or {}
    total_entities = sum(row["entities"] for row in table)
    total_defs = sum(row["defs"] for row in table)
    parts = [
        "# Residue Clusters",
        "",
        f"Source: `{source_path}`",
        "",
        "## Totals",
        "",
        _md_table(
            ["a_def_count", "b_def_count", "diff0_total", "residual_defs", "residual_entities"],
            [[
                totals.get("a_def_count"),
                totals.get("b_def_count"),
                totals.get("diff0_total"),
                total_defs,
                total_entities,
            ]],
        ),
        "",
        "## Ranked Clusters",
        "",
        _md_table(
            ["cluster", "defs", "entities", "hypothesis"],
            [[row["cluster"], row["defs"], row["entities"], row["hypothesis"]] for row in table],
        ),
        "",
    ]
    return "\n".join(parts)


def _load_report(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except UnicodeDecodeError:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Cluster blockdef_diff residuals by mechanical signature.")
    parser.add_argument("report", help="Path to a blockdef_diff.v1 JSON report.")
    parser.add_argument("--out", required=True, help="Path to write the ranked cluster markdown table.")
    args = parser.parse_args(argv)

    try:
        report = _load_report(args.report)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"residue_cluster: failed to load {args.report}: {exc}")
        return 1

    table = build_report_table(report)
    markdown = render_markdown(table, report, args.report)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(markdown)

    print(f"residue_cluster: {len(table)} clusters, {sum(r['entities'] for r in table)} residual entities -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
