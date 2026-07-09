#!/usr/bin/env python3
"""Re-key per-definition population diffs onto a stable census namespace."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCHEMA_ID = "ariadne.population_forensics.v1"
_JSON_ENCODING = "utf-8-sig"
_POP_FIELDS = ("a_total", "diff0", "modified", "removed", "added")


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _write_text(path: str, text: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _block_defs(ir: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [d for d in (ir.get("block_definitions") or []) if isinstance(d, dict)]


def _def_entities(block_def: Dict[str, Any]) -> List[Dict[str, Any]]:
    entities = block_def.get("def_entities")
    if entities is None:
        entities = block_def.get("entities")
    return [e for e in (entities or []) if isinstance(e, dict)]


def _census_defs(ir: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for block_def in _block_defs(ir):
        name = block_def.get("name")
        if not isinstance(name, str) or name in seen:
            continue
        seen.add(name)
        out.append({
            "name": name,
            "handle": block_def.get("handle"),
            "entity_count": len(_def_entities(block_def)),
        })
    return out


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _population(row: Dict[str, Any]) -> Dict[str, int]:
    return {field: _to_int(row.get(field)) for field in _POP_FIELDS}


def _is_clean(pop: Optional[Dict[str, int]]) -> bool:
    if pop is None:
        return False
    return (
        pop["diff0"] == pop["a_total"]
        and pop["modified"] == 0
        and pop["removed"] == 0
        and pop["added"] == 0
    )


def _n_of_m(count: int, total: int) -> Dict[str, int]:
    return {"count": count, "total": total}


def _map_rows_to_census(
    census_defs: List[Dict[str, Any]],
    diff: Dict[str, Any],
    label: str,
) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Any]]:
    census_names = {d["name"] for d in census_defs}
    by_count: Dict[int, List[str]] = {}
    census_entity_counts: Dict[str, int] = {}
    for census_def in census_defs:
        census_entity_counts[census_def["name"]] = census_def["entity_count"]
        by_count.setdefault(census_def["entity_count"], []).append(census_def["name"])

    rows = [r for r in (diff.get("per_def") or []) if isinstance(r, dict)]
    name_matches = sum(1 for r in rows if r.get("name") in census_names)
    name_population_mismatches = [
        {
            "index": index,
            "name": row.get("name"),
            "row_a_total": _to_int(row.get("a_total")),
            "census_entity_count": census_entity_counts[row.get("name")],
        }
        for index, row in enumerate(rows)
        if row.get("name") in census_entity_counts
        and _to_int(row.get("a_total")) != census_entity_counts[row.get("name")]
    ]
    mapped: Dict[str, Dict[str, int]] = {}
    mapped_rows: List[Dict[str, Any]] = []
    unmatchable: List[Dict[str, Any]] = []
    mapped_by_name = 0
    mapped_by_fallback = 0

    used_indexes = set()
    for index, row in enumerate(rows):
        row_name = row.get("name")
        if not (isinstance(row_name, str) and row_name in census_names):
            continue
        used_indexes.add(index)
        if row_name in mapped:
            unmatchable.append({
                "index": index,
                "name": row_name,
                "a_total": _to_int(row.get("a_total")),
                "reason": "target_already_mapped",
                "candidate_count": 1,
                "candidate_names": [row_name],
            })
            continue
        mapped[row_name] = _population(row)
        mapped_by_name += 1
        mapped_rows.append({
            "index": index,
            "name": row_name,
            "census_name": row_name,
            "matched_by": "name",
        })

    for index, row in enumerate(rows):
        if index in used_indexes:
            continue
        row_name = row.get("name")
        target = None
        method = "a_total_unique"

        a_total = _to_int(row.get("a_total"))
        candidates = by_count.get(a_total, [])
        if len(candidates) == 1:
            target = candidates[0]
        else:
            reason = "ambiguous_entity_count" if candidates else "no_census_entity_count"
            unmatchable.append({
                "index": index,
                "name": row_name,
                "a_total": a_total,
                "reason": reason,
                "candidate_count": len(candidates),
                "candidate_names": candidates,
            })
            continue

        if target in mapped:
            unmatchable.append({
                "index": index,
                "name": row_name,
                "a_total": _to_int(row.get("a_total")),
                "reason": "target_already_mapped",
                "candidate_count": 1,
                "candidate_names": [target],
            })
            continue

        mapped[target] = _population(row)
        mapped_by_fallback += 1
        mapped_rows.append({
            "index": index,
            "name": row_name,
            "census_name": target,
            "matched_by": method,
        })

    if name_matches == len(rows):
        strategy = "name"
    elif mapped_by_fallback:
        strategy = "mixed_name_and_unique_a_total"
    else:
        strategy = "unresolved"

    diagnosis = {
        "label": label,
        "rows": len(rows),
        "names_matching_census": _n_of_m(name_matches, len(rows)),
        "mapped_rows": len(mapped),
        "matched_by_name": mapped_by_name,
        "matched_by_unique_a_total": mapped_by_fallback,
        "unmatchable_rows": unmatchable,
        "unmatchable_count": len(unmatchable),
        "name_population_mismatches": name_population_mismatches,
        "name_population_mismatch_count": len(name_population_mismatches),
        "strategy": strategy,
        "assignments": mapped_rows,
    }
    return mapped, diagnosis


def _transition(a_pop: Optional[Dict[str, int]], b_pop: Optional[Dict[str, int]]) -> str:
    in_a = a_pop is not None
    in_b = b_pop is not None
    if in_a and not in_b:
        return "a_only"
    if in_b and not in_a:
        return "b_only"
    if not in_a and not in_b:
        return "absent_both"
    a_clean = _is_clean(a_pop)
    b_clean = _is_clean(b_pop)
    if a_clean and b_clean:
        return "clean_both"
    if not a_clean and b_clean:
        return "healed"
    if a_clean and not b_clean:
        return "regressed"
    return "dirty_both"


def _diff_a_total(diff: Dict[str, Any]) -> int:
    totals = diff.get("totals") if isinstance(diff.get("totals"), dict) else {}
    if "a_entity_total" in totals:
        return _to_int(totals.get("a_entity_total"))
    return sum(_to_int(r.get("a_total")) for r in (diff.get("per_def") or []) if isinstance(r, dict))


def _census_consistency(primary: Dict[str, Any], other: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if other is None:
        return None
    primary_pairs = [(d.get("name"), d.get("handle")) for d in _block_defs(primary)]
    other_pairs = [(d.get("name"), d.get("handle")) for d in _block_defs(other)]
    first_mismatch = None
    for index, (left, right) in enumerate(zip(primary_pairs, other_pairs)):
        if left != right:
            first_mismatch = {"index": index, "primary": list(left), "other": list(right)}
            break
    if first_mismatch is None and len(primary_pairs) != len(other_pairs):
        first_mismatch = {"index": min(len(primary_pairs), len(other_pairs)), "primary": None, "other": None}
    return {
        "checked": True,
        "primary_block_definitions": len(primary_pairs),
        "other_block_definitions": len(other_pairs),
        "ordered_name_handle_identical": primary_pairs == other_pairs,
        "name_handle_set_identical": set(primary_pairs) == set(other_pairs),
        "first_mismatch": first_mismatch,
    }


def _other_census_name_matches(other: Optional[Dict[str, Any]], diff: Dict[str, Any]) -> Optional[Dict[str, int]]:
    if other is None:
        return None
    other_names = {d["name"] for d in _census_defs(other)}
    rows = [r for r in (diff.get("per_def") or []) if isinstance(r, dict)]
    return _n_of_m(sum(1 for r in rows if r.get("name") in other_names), len(rows))


def _post_b_side_name_matches(post_ir: Optional[Dict[str, Any]], diff: Dict[str, Any]) -> Optional[Dict[str, int]]:
    if post_ir is None:
        return None
    post_names = {d["name"] for d in _census_defs(post_ir)}
    rows = [r for r in (diff.get("per_def") or []) if isinstance(r, dict)]
    count = 0
    for row in rows:
        b_name = row.get("b_name") if isinstance(row.get("b_name"), str) else row.get("name")
        if b_name in post_names:
            count += 1
    return _n_of_m(count, len(rows))


def build_report(
    census: Dict[str, Any],
    diff_a: Dict[str, Any],
    diff_b: Dict[str, Any],
    label_a: str,
    label_b: str,
    *,
    census_b: Optional[Dict[str, Any]] = None,
    post_a: Optional[Dict[str, Any]] = None,
    post_b: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    census_defs = _census_defs(census)
    mapped_a, diag_a = _map_rows_to_census(census_defs, diff_a, label_a)
    mapped_b, diag_b = _map_rows_to_census(census_defs, diff_b, label_b)

    per_census_def: List[Dict[str, Any]] = []
    transition_counts = {
        "defs_in_a_only": 0,
        "defs_in_b_only": 0,
        "defs_both": 0,
        "absent_both": 0,
        "healed": 0,
        "regressed": 0,
        "clean_both": 0,
        "dirty_both": 0,
    }

    for census_def in census_defs:
        name = census_def["name"]
        a_pop = mapped_a.get(name)
        b_pop = mapped_b.get(name)
        transition = _transition(a_pop, b_pop)
        if transition == "a_only":
            transition_counts["defs_in_a_only"] += 1
        elif transition == "b_only":
            transition_counts["defs_in_b_only"] += 1
        elif transition == "absent_both":
            transition_counts["absent_both"] += 1
        else:
            transition_counts["defs_both"] += 1
            transition_counts[transition] += 1
        per_census_def.append({
            "census_name": name,
            "in_a": a_pop is not None,
            "in_b": b_pop is not None,
            "a": a_pop,
            "b": b_pop,
            "transition": transition,
        })

    census_consistency = _census_consistency(census, census_b)
    note_parts = [
        f"{label_a}: {diag_a['names_matching_census']['count']}/{diag_a['names_matching_census']['total']} "
        "per_def names match the selected census.",
        f"{label_b}: {diag_b['names_matching_census']['count']}/{diag_b['names_matching_census']['total']} "
        "per_def names match the selected census.",
    ]
    if diag_a["strategy"] != "name" or diag_b["strategy"] != "name":
        note_parts.append(
            "Rows whose names did not match the selected census were assigned only when "
            "a_total matched exactly one census definition entity count; ambiguous and "
            "unmatched rows are listed without forced mapping."
        )
    else:
        note_parts.append("per_def.name is a stable census-side key for both diffs against the selected census.")
    if census_consistency and not census_consistency["ordered_name_handle_identical"]:
        note_parts.append("The optional second census does not have identical block-definition name/handle pairs.")

    key_diagnosis = {
        "a_names_matching_census": diag_a["names_matching_census"],
        "b_names_matching_census": diag_b["names_matching_census"],
        "a_key_strategy": diag_a["strategy"],
        "b_key_strategy": diag_b["strategy"],
        "a_matched_by_unique_a_total": diag_a["matched_by_unique_a_total"],
        "b_matched_by_unique_a_total": diag_b["matched_by_unique_a_total"],
        "a_unmatchable_rows": diag_a["unmatchable_rows"],
        "b_unmatchable_rows": diag_b["unmatchable_rows"],
        "a_unmatchable_count": diag_a["unmatchable_count"],
        "b_unmatchable_count": diag_b["unmatchable_count"],
        "a_name_population_mismatches": diag_a["name_population_mismatches"],
        "b_name_population_mismatches": diag_b["name_population_mismatches"],
        "a_name_population_mismatch_count": diag_a["name_population_mismatch_count"],
        "b_name_population_mismatch_count": diag_b["name_population_mismatch_count"],
        "a_assignments": diag_a["assignments"],
        "b_assignments": diag_b["assignments"],
        "census_consistency": census_consistency,
        "a_names_matching_optional_census_b": _other_census_name_matches(census_b, diff_a),
        "b_names_matching_optional_census_b": _other_census_name_matches(census_b, diff_b),
        "a_b_side_names_matching_post": _post_b_side_name_matches(post_a, diff_a),
        "b_b_side_names_matching_post": _post_b_side_name_matches(post_b, diff_b),
        "note": " ".join(note_parts),
    }

    totals = dict(transition_counts)
    totals["population_delta_a_total"] = {
        "a": _diff_a_total(diff_a),
        "b": _diff_a_total(diff_b),
        "label_a": label_a,
        "label_b": label_b,
    }

    return {
        "schema": SCHEMA_ID,
        "census_defs": len(census_defs),
        "per_census_def": per_census_def,
        "totals": totals,
        "key_diagnosis": key_diagnosis,
    }


def _md_table(headers: List[str], rows: Iterable[Iterable[Any]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")
    return "\n".join(out)


def _pop_summary(pop: Optional[Dict[str, int]]) -> str:
    if pop is None:
        return ""
    return "a_total={a_total}, diff0={diff0}, modified={modified}, removed={removed}, added={added}".format(**pop)


def _verdict(report: Dict[str, Any], label_a: str, label_b: str) -> str:
    totals = report.get("totals") or {}
    diag = report.get("key_diagnosis") or {}
    unresolved = _to_int(diag.get("a_unmatchable_count")) + _to_int(diag.get("b_unmatchable_count"))
    population_mismatches = (
        _to_int(diag.get("a_name_population_mismatch_count"))
        + _to_int(diag.get("b_name_population_mismatch_count"))
    )
    consistency = diag.get("census_consistency") or {}
    if unresolved:
        return (
            f"Verdict: indeterminate. {label_b} cannot be claimed as strictly improved over "
            f"{label_a} def-for-def because {unresolved} diff rows could not be re-keyed "
            f"onto the selected census without ambiguity and {population_mismatches} "
            "name-matched rows have population mismatches. "
            f"Mapped evidence shows healed={totals.get('healed')}, "
            f"regressed={totals.get('regressed')}, dirty_both={totals.get('dirty_both')}, "
            f"a_only={totals.get('defs_in_a_only')}, b_only={totals.get('defs_in_b_only')}."
        )
    if population_mismatches or consistency.get("ordered_name_handle_identical") is False:
        return (
            f"Verdict: indeterminate. All mapped rows have keys, but population controls are not stable: "
            f"name_population_mismatches={population_mismatches}, "
            f"census_name_handle_identical={consistency.get('ordered_name_handle_identical')}."
        )
    if totals.get("regressed") or totals.get("defs_in_b_only"):
        return (
            f"Verdict: partial. {label_b} healed {totals.get('healed')} definitions but also "
            f"has regressed={totals.get('regressed')} and b_only={totals.get('defs_in_b_only')}."
        )
    return (
        f"Verdict: supported for mapped definitions. {label_b} healed {totals.get('healed')} "
        f"definitions with regressed={totals.get('regressed')} and b_only={totals.get('defs_in_b_only')}."
    )


def render_markdown(report: Dict[str, Any], label_a: str, label_b: str) -> str:
    totals = report.get("totals") or {}
    diag = report.get("key_diagnosis") or {}
    per_def = report.get("per_census_def") or []
    transition_rows = [
        ["clean_both", totals.get("clean_both")],
        ["dirty_both", totals.get("dirty_both")],
        ["healed", totals.get("healed")],
        ["regressed", totals.get("regressed")],
        ["a_only", totals.get("defs_in_a_only")],
        ["b_only", totals.get("defs_in_b_only")],
        ["absent_both", totals.get("absent_both")],
    ]
    interesting = [r for r in per_def if r.get("transition") in ("healed", "regressed")]
    interesting.sort(key=lambda r: (r.get("transition"), r.get("census_name", "")))

    unmatchable_rows: List[List[Any]] = []
    for side_key, label in (("a_unmatchable_rows", label_a), ("b_unmatchable_rows", label_b)):
        for row in diag.get(side_key) or []:
            unmatchable_rows.append([
                label,
                row.get("index"),
                row.get("name"),
                row.get("a_total"),
                row.get("reason"),
                row.get("candidate_count"),
            ])
    population_mismatch_rows: List[List[Any]] = []
    for side_key, label in (
        ("a_name_population_mismatches", label_a),
        ("b_name_population_mismatches", label_b),
    ):
        for row in diag.get(side_key) or []:
            population_mismatch_rows.append([
                label,
                row.get("index"),
                row.get("name"),
                row.get("row_a_total"),
                row.get("census_entity_count"),
            ])

    consistency = diag.get("census_consistency") or {}
    consistency_text = "not checked"
    if consistency:
        consistency_text = (
            f"ordered_name_handle_identical={consistency.get('ordered_name_handle_identical')}, "
            f"primary_defs={consistency.get('primary_block_definitions')}, "
            f"other_defs={consistency.get('other_block_definitions')}, "
            f"first_mismatch={consistency.get('first_mismatch')}"
        )

    parts = [
        "# Population Forensics",
        "",
        "## Transition Matrix",
        "",
        _md_table(["transition", "defs"], transition_rows),
        "",
        "## Healed And Regressed",
        "",
        _md_table(
            ["transition", "census_name", label_a, label_b],
            [[r.get("transition"), r.get("census_name"), _pop_summary(r.get("a")), _pop_summary(r.get("b"))]
             for r in interesting],
        ),
        "",
        "## Key Diagnosis",
        "",
        _md_table(
            ["measure", "value"],
            [
                [f"{label_a} names matching selected census", diag.get("a_names_matching_census")],
                [f"{label_b} names matching selected census", diag.get("b_names_matching_census")],
                [f"{label_a} key strategy", diag.get("a_key_strategy")],
                [f"{label_b} key strategy", diag.get("b_key_strategy")],
                [f"{label_a} unique-count fallback rows", diag.get("a_matched_by_unique_a_total")],
                [f"{label_b} unique-count fallback rows", diag.get("b_matched_by_unique_a_total")],
                [f"{label_a} unmatchable rows", diag.get("a_unmatchable_count")],
                [f"{label_b} unmatchable rows", diag.get("b_unmatchable_count")],
                [f"{label_a} name/population mismatches", diag.get("a_name_population_mismatch_count")],
                [f"{label_b} name/population mismatches", diag.get("b_name_population_mismatch_count")],
                ["optional census consistency", consistency_text],
                [f"{label_a} names matching optional census", diag.get("a_names_matching_optional_census_b")],
                [f"{label_b} names matching optional census", diag.get("b_names_matching_optional_census_b")],
                [f"{label_a} b-side names matching post IR", diag.get("a_b_side_names_matching_post")],
                [f"{label_b} b-side names matching post IR", diag.get("b_b_side_names_matching_post")],
            ],
        ),
        "",
        diag.get("note", ""),
        "",
        "## Unmatchable Rows",
        "",
        _md_table(
            ["side", "index", "name", "a_total", "reason", "candidate_count"],
            unmatchable_rows,
        ),
        "",
        "## Name Population Mismatches",
        "",
        _md_table(
            ["side", "index", "name", "row_a_total", "census_entity_count"],
            population_mismatch_rows,
        ),
        "",
        "## Verdict",
        "",
        _verdict(report, label_a, label_b),
        "",
    ]
    return "\n".join(parts)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Re-key two interior block-definition diffs onto a stable census namespace."
    )
    parser.add_argument("--census", required=True)
    parser.add_argument("--census-b", dest="census_b",
                        help="optional second census IR for cross-run name/handle consistency diagnosis")
    parser.add_argument("--post-a", dest="post_a",
                        help="optional regen post IR for diff-a b-side name existence diagnosis")
    parser.add_argument("--post-b", dest="post_b",
                        help="optional regen post IR for diff-b b-side name existence diagnosis")
    parser.add_argument("--diff-a", required=True)
    parser.add_argument("--diff-b", required=True)
    parser.add_argument("--label-a", required=True)
    parser.add_argument("--label-b", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--md")
    args = parser.parse_args(argv)

    for path in [args.census, args.diff_a, args.diff_b, args.census_b, args.post_a, args.post_b]:
        if path and not os.path.exists(path):
            return 3

    report = build_report(
        _load_json(args.census),
        _load_json(args.diff_a),
        _load_json(args.diff_b),
        args.label_a,
        args.label_b,
        census_b=_load_json(args.census_b) if args.census_b else None,
        post_a=_load_json(args.post_a) if args.post_a else None,
        post_b=_load_json(args.post_b) if args.post_b else None,
    )
    _write_json(args.out, report)
    if args.md:
        _write_text(args.md, render_markdown(report, args.label_a, args.label_b))
    else:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
