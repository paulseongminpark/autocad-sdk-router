#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate ALM bench v0 READ tasks from a DWG graph IR JSON file.

Every gold answer below is computed directly from the loaded IR -- never
hand-typed -- so regenerating against the same IR always reproduces the
same tasks byte-for-byte. Stdlib only.
"""
from __future__ import annotations

import argparse
import io
import json
import re
from collections import Counter

_BLOCK_NAME_RE = re.compile(r"^\*D\d+$")


def _load_ir(ir_path: str) -> dict:
    with io.open(ir_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _modelspace_entities(ir: dict) -> list:
    return [e for e in ir.get("entities", []) if e.get("space") == "model"]


def _count_dxf_name(entities: list, dxf_name: str) -> int:
    return sum(1 for e in entities if e.get("dxf_name") == dxf_name)


def _largest_block_definition_name(block_definitions: list) -> str:
    max_count = max(bd.get("entity_count", 0) for bd in block_definitions)
    candidates = sorted(bd["name"] for bd in block_definitions if bd.get("entity_count") == max_count)
    return candidates[0]


def compute_tasks(ir: dict, source_ir: str) -> dict:
    ms_entities = _modelspace_entities(ir)
    block_definitions = ir.get("block_definitions", [])
    block_references = ir.get("block_references", [])

    def_entities_total = sum(len(bd.get("def_entities", [])) for bd in block_definitions)
    hatch_def_entities = sum(
        1
        for bd in block_definitions
        for de in bd.get("def_entities", [])
        if de.get("dxf_name") == "HATCH"
    )
    distinct_dxf_names = len(Counter(e.get("dxf_name") for e in ms_entities))
    star_d_blocks = sum(1 for bd in block_definitions if _BLOCK_NAME_RE.match(bd.get("name", "")))

    tasks = [
        {
            "id": "READ-001",
            "question": "모델스페이스(entities) 엔티티는 총 몇 개입니까?",
            "gold": len(ms_entities),
            "gold_derivation": "count(entities where space == 'model')",
            "rubric": "exact_match",
            "budget_axis": "single_pass",
        },
        {
            "id": "READ-002",
            "question": "모델스페이스 엔티티 중 DIMENSION(dxf_name)은 몇 개입니까?",
            "gold": _count_dxf_name(ms_entities, "DIMENSION"),
            "gold_derivation": "count(entities where space == 'model' and dxf_name == 'DIMENSION')",
            "rubric": "exact_match",
            "budget_axis": "single_pass",
        },
        {
            "id": "READ-003",
            "question": "모델스페이스 엔티티 중 TEXT(dxf_name)는 몇 개입니까?",
            "gold": _count_dxf_name(ms_entities, "TEXT"),
            "gold_derivation": "count(entities where space == 'model' and dxf_name == 'TEXT')",
            "rubric": "exact_match",
            "budget_axis": "single_pass",
        },
        {
            "id": "READ-004",
            "question": "block_definitions 목록에 있는 블록 정의는 총 몇 개입니까?",
            "gold": len(block_definitions),
            "gold_derivation": "len(block_definitions)",
            "rubric": "exact_match",
            "budget_axis": "single_pass",
        },
        {
            "id": "READ-005",
            "question": "이름이 정규식 ^\\*D\\d+$ 패턴과 일치하는 block_definitions는 몇 개입니까?",
            "gold": star_d_blocks,
            "gold_derivation": "count(block_definitions where regex('^\\*D\\d+$').match(name))",
            "rubric": "exact_match",
            "budget_axis": "single_pass",
        },
        {
            "id": "READ-006",
            "question": "모든 block_definitions의 def_entities를 합산하면 총 몇 개입니까?",
            "gold": def_entities_total,
            "gold_derivation": "sum(len(bd.def_entities) for bd in block_definitions)",
            "rubric": "exact_match",
            "budget_axis": "single_pass",
        },
        {
            "id": "READ-007",
            "question": "모든 block_definitions의 def_entities 중 dxf_name이 HATCH인 항목은 몇 개입니까?",
            "gold": hatch_def_entities,
            "gold_derivation": "sum(count(de in bd.def_entities where de.dxf_name == 'HATCH') for bd in block_definitions)",
            "rubric": "exact_match",
            "budget_axis": "single_pass",
        },
        {
            "id": "READ-008",
            "question": "모델스페이스 entities에서 서로 다른 dxf_name 값은 몇 종류입니까?",
            "gold": distinct_dxf_names,
            "gold_derivation": "len(set(e.dxf_name for e in entities where space == 'model'))",
            "rubric": "exact_match",
            "budget_axis": "single_pass",
        },
        {
            "id": "READ-009",
            "question": "block_references 목록에 있는 블록 참조는 총 몇 개입니까?",
            "gold": len(block_references),
            "gold_derivation": "len(block_references)",
            "rubric": "exact_match",
            "budget_axis": "single_pass",
        },
        {
            "id": "READ-010",
            "question": "entity_count가 가장 큰 block_definition의 이름은 무엇입니까? (동률이면 사전순으로 가장 앞선 이름)",
            "gold": _largest_block_definition_name(block_definitions),
            "gold_derivation": "min(sorted(name for bd in block_definitions where bd.entity_count == max(entity_count)))",
            "rubric": "exact_match",
            "budget_axis": "single_pass",
        },
    ]

    return {
        "schema": "ariadne.alm_bench.read.v0",
        "source_ir": source_ir,
        "tasks": tasks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ir", required=True, help="path to dwg_graph_ir.json")
    parser.add_argument("--out", default="bench/read_tasks.json", help="output path for read_tasks.json")
    args = parser.parse_args()

    ir = _load_ir(args.ir)
    bench = compute_tasks(ir, args.ir)

    with io.open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(bench, f, sort_keys=True, ensure_ascii=False, indent=2)
        f.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
