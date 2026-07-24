#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure residual block-definition composition from canonical cad_diff matches."""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

import blockdef_diff
import cad_diff

SCHEMA_ID = "ariadne.modified_composition.v1"
_INPUT_ENCODING = "utf-8-sig"

DEFAULT_CENSUS_IR = (
    r"D:\dev\99_tools\autocad-sdk-router\runs\e2e_1dwg_R4n_origin_20260709"
    r"\census\dwg_graph_ir.json"
)
DEFAULT_POST_IR = (
    r"D:\dev\99_tools\autocad-sdk-router\runs\e2e_1dwg_R4q_dashphase_20260709"
    r"\regen\post\dwg_graph_ir.json"
)
DEFAULT_INTERIOR_DIFF = (
    r"D:\dev\99_tools\autocad-sdk-router\runs\e2e_1dwg_R4q_dashphase_20260709"
    r"\interior_diff.json"
)
DEFAULT_OUT_JSON = r"reports\interior100\modified_composition_R4q.json"
DEFAULT_OUT_MD = r"reports\interior100\modified_composition_R4q.md"
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding=_INPUT_ENCODING) as fh:
        return json.load(fh)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _definitions_by_name(ir: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return blockdef_diff._definitions_by_name(ir or {})


def _load_name_map(report: Dict[str, Any]) -> Dict[str, str]:
    name_map: Dict[str, str] = {}
    for row in report.get("per_def") or []:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        b_name = row.get("b_name")
        if isinstance(name, str) and isinstance(b_name, str):
            name_map[name] = b_name
    return name_map


def _dirty_rows(interior_diff: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in interior_diff.get("per_def") or []:
        if not isinstance(row, dict):
            continue
        if int(row.get("a_total", 0) or 0) != int(row.get("diff0", 0) or 0):
            rows.append(row)
    return rows


def _diff_definition(name: str,
                     def_a: Optional[Dict[str, Any]],
                     def_b: Optional[Dict[str, Any]], *,
                     name_map: Optional[Dict[str, str]] = None,
                     tolerance: float = 1e-6) -> Dict[str, Any]:
    ents_a = blockdef_diff._definition_entities(def_a, name_map=name_map) if def_a else []
    ents_b = blockdef_diff._definition_entities(def_b) if def_b else []
    return cad_diff.compute_diff(
        blockdef_diff._synthetic_ir(ents_a),
        blockdef_diff._synthetic_ir(ents_b),
        comparison_basis="geometry",
        geometry_tolerance=tolerance,
        diff_scope=cad_diff.FULL_DATABASE,
    )


def _group_counts(def_name: str, diff: Dict[str, Any]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"modified": 0, "removed": 0, "added": 0}
    )
    for rec in diff.get("changed_handles") or []:
        if not isinstance(rec, dict):
            continue
        dxf_name = str(rec.get("dxf_name") or "")
        change = rec.get("change")
        if change in ("modified", "removed", "added"):
            grouped[dxf_name][change] += 1
    return [
        {
            "def": def_name,
            "dxf_name": dxf_name,
            "modified": counts["modified"],
            "removed": counts["removed"],
            "added": counts["added"],
        }
        for dxf_name, counts in sorted(grouped.items())
    ]


def build_report(census_ir: Dict[str, Any],
                 post_ir: Dict[str, Any],
                 interior_diff: Dict[str, Any]) -> Dict[str, Any]:
    name_map = _load_name_map(interior_diff)
    defs_a = _definitions_by_name(census_ir)
    defs_b = _definitions_by_name(post_ir)

    per_def: List[Dict[str, Any]] = []
    for row in _dirty_rows(interior_diff):
        def_name = str(row.get("name") or "")
        b_name = str(row.get("b_name") or def_name)
        diff = _diff_definition(
            def_name,
            defs_a.get(def_name),
            defs_b.get(b_name),
            name_map=name_map,
        )
        per_def.extend(_group_counts(def_name, diff))

    by_kind: Dict[str, Dict[str, int]] = {}
    for row in per_def:
        dxf_name = row["dxf_name"]
        slot = by_kind.setdefault(dxf_name, {"modified": 0, "removed": 0, "added": 0})
        for key in ("modified", "removed", "added"):
            slot[key] += int(row[key])

    by_def_kind_top = sorted(
        (
            {
                **row,
                "total": int(row["modified"]) + int(row["removed"]) + int(row["added"]),
            }
            for row in per_def
        ),
        key=lambda row: (-int(row["total"]), row["def"], row["dxf_name"]),
    )[:30]

    totals = {
        "dirty_def_count": len(_dirty_rows(interior_diff)),
        "def_kind_rows": len(per_def),
        "modified": sum(int(row["modified"]) for row in per_def),
        "removed": sum(int(row["removed"]) for row in per_def),
        "added": sum(int(row["added"]) for row in per_def),
    }
    totals["residual"] = totals["modified"] + totals["removed"] + totals["added"]

    return {
        "schema": SCHEMA_ID,
        "per_def": sorted(per_def, key=lambda row: (row["def"], row["dxf_name"])),
        "by_kind": {key: by_kind[key] for key in sorted(by_kind)},
        "by_def_kind_top": by_def_kind_top,
        "totals": totals,
    }


def _md_table(headers: List[str], rows: Iterable[Iterable[Any]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(out)


def render_markdown(report: Dict[str, Any]) -> str:
    totals = report.get("totals") or {}
    top_rows = report.get("by_def_kind_top") or []
    kind_rows = report.get("by_kind") or {}
    return "\n".join([
        "# Modified Composition",
        "",
        "## Totals",
        "",
        _md_table(
            ["dirty_def_count", "def_kind_rows", "modified", "removed", "added", "residual"],
            [[
                totals.get("dirty_def_count", 0),
                totals.get("def_kind_rows", 0),
                totals.get("modified", 0),
                totals.get("removed", 0),
                totals.get("added", 0),
                totals.get("residual", 0),
            ]],
        ),
        "",
        "## By Kind",
        "",
        _md_table(
            ["dxf_name", "modified", "removed", "added"],
            [
                [dxf_name, counts.get("modified", 0), counts.get("removed", 0), counts.get("added", 0)]
                for dxf_name, counts in kind_rows.items()
            ],
        ),
        "",
        "## Top Def/Kind Rows",
        "",
        _md_table(
            ["def", "dxf_name", "modified", "removed", "added", "total"],
            [
                [row.get("def"), row.get("dxf_name"), row.get("modified"),
                 row.get("removed"), row.get("added"), row.get("total")]
                for row in top_rows
            ],
        ),
        "",
    ]) + "\n"


def _resolve_out_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(_REPO_ROOT, path)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census-ir", default=DEFAULT_CENSUS_IR)
    parser.add_argument("--post-ir", default=DEFAULT_POST_IR)
    parser.add_argument("--interior-diff", default=DEFAULT_INTERIOR_DIFF)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)

    report = build_report(
        _load_json(args.census_ir),
        _load_json(args.post_ir),
        _load_json(args.interior_diff),
    )
    out_json = _resolve_out_path(args.out_json)
    out_md = _resolve_out_path(args.out_md)
    _write_json(out_json, report)
    parent = os.path.dirname(os.path.abspath(out_md))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
