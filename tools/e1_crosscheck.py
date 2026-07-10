#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable

_JSON_ENCODING = "utf-8-sig"
SCHEMA = "ariadne.e1_crosscheck.v0"
HIGH_LIKELIHOOD_CUTOFF = 0.7
LOW_LIKELIHOOD_CUTOFF = 0.3
MANY_PAIRS_CUTOFF = 5


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding=_JSON_ENCODING) as handle:
        return json.load(handle)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding=_JSON_ENCODING) as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _normalize_def_name(def_name: str | None) -> str:
    return "".join((def_name or "").split())


def _handle_value(handle: Any) -> str | None:
    if isinstance(handle, dict):
        value = handle.get("handle")
    else:
        value = handle
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _ornith_handle_set(row: dict[str, Any]) -> set[str]:
    parsed = row.get("parsed") if isinstance(row.get("parsed"), dict) else {}
    handles = set()
    for item in parsed.get("wall_line_handles") or []:
        value = _handle_value(item)
        if value is not None:
            handles.add(value)
    return handles


def _pair_handle_set(pair_rows: Iterable[dict[str, Any]]) -> set[str]:
    handles = set()
    for pair_row in pair_rows:
        for value in pair_row.get("pair") or []:
            handle = _handle_value(value)
            if handle is not None:
                handles.add(handle)
    return handles


def _jaccard(lhs: set[str], rhs: set[str]) -> float:
    union = lhs | rhs
    if not union:
        return 1.0
    return len(lhs & rhs) / len(union)


def _containment(lhs: set[str], rhs: set[str]) -> float:
    return len(lhs & rhs) / max(1, len(lhs))


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if not var_x or not var_y:
        return None
    return cov / math.sqrt(var_x * var_y)


def _candidate_divergence(row: dict[str, Any]) -> str | None:
    likelihood = row.get("wall_likelihood")
    if not isinstance(likelihood, (int, float)):
        return None
    if row.get("n_pairs", 0) == 0 and likelihood >= HIGH_LIKELIHOOD_CUTOFF:
        return "high_likelihood_zero_pairs"
    if row.get("n_pairs", 0) >= MANY_PAIRS_CUTOFF and likelihood <= LOW_LIKELIHOOD_CUTOFF:
        return "many_pairs_low_likelihood"
    return None


def _score_divergence(row: dict[str, Any]) -> tuple[int, float, float, str]:
    kind = row["divergence_kind"]
    if kind == "high_likelihood_zero_pairs":
        return (0, -float(row["wall_likelihood"]), 0.0, row["def"])
    return (1, -float(row["n_pairs"]), float(row["wall_likelihood"]), row["def"])


def _build_rows(ornith_rows: list[dict[str, Any]], pair_doc: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    per_def = pair_doc.get("per_def") if isinstance(pair_doc.get("per_def"), dict) else {}
    pair_keys = [key for key in per_def if isinstance(key, str) and key]
    normalized_pairs: dict[str, str | None] = {}
    for def_name in pair_keys:
        norm = _normalize_def_name(def_name)
        existing = normalized_pairs.get(norm)
        if existing is None and norm not in normalized_pairs:
            normalized_pairs[norm] = def_name
        else:
            normalized_pairs[norm] = None

    rows: list[dict[str, Any]] = []
    joined_pair_keys: set[str] = set()
    joined_ornith_count = 0
    unjoined_ornith = 0

    for orn_row in ornith_rows:
        parsed = orn_row.get("parsed") if isinstance(orn_row.get("parsed"), dict) else {}
        def_name = parsed.get("def")
        if not isinstance(def_name, str) or not def_name.strip():
            unjoined_ornith += 1
            continue
        pair_key = None
        if def_name in per_def:
            pair_key = def_name
        else:
            pair_key = normalized_pairs.get(_normalize_def_name(def_name))
        if pair_key is None or pair_key in joined_pair_keys:
            unjoined_ornith += 1
            continue

        joined_pair_keys.add(pair_key)
        joined_ornith_count += 1
        pair_rows = per_def.get(pair_key) or []
        h_ornith = _ornith_handle_set(orn_row)
        h_det = _pair_handle_set(pair_rows)
        row = {
            "def": def_name,
            "wall_likelihood": parsed.get("wall_likelihood"),
            "n_pairs": len(pair_rows),
            "n_h_ornith": len(h_ornith),
            "n_h_det": len(h_det),
            "jaccard": _jaccard(h_ornith, h_det),
            "containment": _containment(h_ornith, h_det),
        }
        row["divergence_kind"] = _candidate_divergence(row)
        rows.append(row)

    unjoined_pairs = sum(1 for key in pair_keys if key not in joined_pair_keys)
    rows.sort(key=lambda row: (
        row["wall_likelihood"] is None,
        -(row["wall_likelihood"] if isinstance(row["wall_likelihood"], (int, float)) else -1.0),
        row["def"],
    ))
    summary = {
        "joined": joined_ornith_count,
        "unjoined_ornith": unjoined_ornith,
        "unjoined_pairs": unjoined_pairs,
    }
    return rows, summary


def _top_divergent(rows: list[dict[str, Any]]) -> list[str]:
    candidates = [row for row in rows if row.get("divergence_kind")]
    candidates.sort(key=_score_divergence)
    return [row["def"] for row in candidates[:20]]


def run(ornith_path: str | Path, pairs_path: str | Path) -> dict[str, Any]:
    ornith_rows = _load_jsonl(Path(ornith_path))
    pair_doc = _load_json(Path(pairs_path))
    rows, summary = _build_rows(ornith_rows, pair_doc)
    joined_likelihoods: list[float] = []
    joined_pairs: list[float] = []
    for row in rows:
        likelihood = row.get("wall_likelihood")
        if isinstance(likelihood, (int, float)):
            joined_likelihoods.append(float(likelihood))
            joined_pairs.append(float(row["n_pairs"]))
    summary["likelihood_vs_pairs_pearson"] = _pearson(joined_likelihoods, joined_pairs)
    summary["top20_divergent"] = _top_divergent(rows)
    for row in rows:
        row.pop("divergence_kind", None)
    return {
        "schema": SCHEMA,
        "per_def": rows,
        "summary": summary,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    rows = report["per_def"]
    lines = [
        "# E1 Crosscheck",
        "",
        "## Summary",
        f"- Joined defs: {summary['joined']}",
        f"- Unjoined ornith rows: {summary['unjoined_ornith']}",
        f"- Unjoined pair defs: {summary['unjoined_pairs']}",
        f"- Pearson likelihood vs pair count: {summary['likelihood_vs_pairs_pearson'] if summary['likelihood_vs_pairs_pearson'] is not None else 'n/a'}",
        "",
        "## Top-20 Divergent",
        "| def | wall_likelihood | n_pairs | n_h_ornith | n_h_det | jaccard | containment |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    divergent = set(summary.get("top20_divergent") or [])
    for row in rows:
        if row["def"] not in divergent:
            continue
        lines.append(
            "| {def_name} | {wall_likelihood} | {n_pairs} | {n_h_ornith} | {n_h_det} | {jaccard:.3f} | {containment:.3f} |".format(
                def_name=row["def"],
                wall_likelihood=row["wall_likelihood"],
                n_pairs=row["n_pairs"],
                n_h_ornith=row["n_h_ornith"],
                n_h_det=row["n_h_det"],
                jaccard=row["jaccard"],
                containment=row["containment"],
            )
        )
    if len(lines) == 8:
        lines.append("| (none) |  |  |  |  |  |  |")
    lines.append("")
    return "\n".join(lines)


def write_reports(report: dict[str, Any], out_path: str | Path, md_path: str | Path | None = None) -> None:
    _write_json(Path(out_path), report)
    if md_path is not None:
        _write_text(Path(md_path), _render_markdown(report))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cross-check ornith wall annotations against wall-pair candidates.")
    parser.add_argument("--ornith", required=True, help="ornith JSONL path")
    parser.add_argument("--pairs", required=True, help="wall_pairs JSON path")
    parser.add_argument("--out", required=True, help="output JSON path")
    parser.add_argument("--md", help="optional Markdown output path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = run(args.ornith, args.pairs)
    write_reports(report, args.out, args.md)
    print(
        "joined={0} unjoined_ornith={1} unjoined_pairs={2}".format(
            report["summary"]["joined"],
            report["summary"]["unjoined_ornith"],
            report["summary"]["unjoined_pairs"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
