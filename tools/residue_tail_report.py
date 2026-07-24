#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic forensic classifier for block-definition residue tails."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import blockdef_diff

SCHEMA_ID = "ariadne.residue_tail.v1"
_INPUT_ENCODING = "utf-8-sig"
_RECORD_CAP = 500


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding=_INPUT_ENCODING) as fh:
        return json.load(fh)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")


def _definitions_by_name(ir: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for block_def in (ir or {}).get("block_definitions") or []:
        if not isinstance(block_def, dict):
            continue
        name = block_def.get("name")
        if isinstance(name, str):
            out[name] = block_def
    return out


def _definition_entities(block_def: Optional[Dict[str, Any]], *,
                         name_map: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    if not block_def:
        return []
    entities = block_def.get("def_entities")
    if entities is None:
        entities = block_def.get("entities")
    return [
        blockdef_diff._canonical_entity(entity, name_map=name_map)
        for entity in (entities or [])
        if isinstance(entity, dict)
    ]


def _json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _geometry(entity: Dict[str, Any]) -> Dict[str, Any]:
    geometry = entity.get("geometry")
    return geometry if isinstance(geometry, dict) else {}


def _entity_sort_key(entity: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        str(entity.get("handle") or ""),
        str(entity.get("dxf_name") or ""),
        _json_key(_geometry(entity)),
    )


def _record_sort_key(record: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        str(record.get("def") or ""),
        str(record.get("dxf_name") or ""),
        0 if "differing_fields" in record else 1,
        tuple(record.get("differing_fields") or ()),
        str(record.get("a_handle") or ""),
        str(record.get("b_handle") or ""),
        str(record.get("side") or ""),
        str(record.get("handle") or ""),
    )


def _differing_fields(a_entity: Dict[str, Any], b_entity: Dict[str, Any]) -> Tuple[str, ...]:
    a_geom = _geometry(a_entity)
    b_geom = _geometry(b_entity)
    keys = sorted(set(a_geom) | set(b_geom))
    return tuple(key for key in keys if a_geom.get(key) != b_geom.get(key))


def _drop_exact_geometry_matches(a_entities: Sequence[Dict[str, Any]],
                                 b_entities: Sequence[Dict[str, Any]]
                                 ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    grouped_a: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    grouped_b: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for entity in sorted(a_entities, key=_entity_sort_key):
        grouped_a[_json_key(_geometry(entity))].append(entity)
    for entity in sorted(b_entities, key=_entity_sort_key):
        grouped_b[_json_key(_geometry(entity))].append(entity)

    a_left: List[Dict[str, Any]] = []
    b_left: List[Dict[str, Any]] = []
    for geom_key in sorted(set(grouped_a) | set(grouped_b)):
        a_group = grouped_a.get(geom_key, [])
        b_group = grouped_b.get(geom_key, [])
        matched = min(len(a_group), len(b_group))
        a_left.extend(a_group[matched:])
        b_left.extend(b_group[matched:])
    a_left.sort(key=_entity_sort_key)
    b_left.sort(key=_entity_sort_key)
    return a_left, b_left


def _pair_group(def_name: str, dxf_name: str,
                a_entities: Sequence[Dict[str, Any]],
                b_entities: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    a_left, b_left = _drop_exact_geometry_matches(a_entities, b_entities)
    records: List[Dict[str, Any]] = []

    while a_left and b_left:
        best: Optional[Tuple[Tuple[Any, ...], int, int, Tuple[str, ...]]] = None
        for a_index, a_entity in enumerate(a_left):
            a_key = _entity_sort_key(a_entity)
            for b_index, b_entity in enumerate(b_left):
                diff_fields = _differing_fields(a_entity, b_entity)
                candidate = (
                    len(diff_fields),
                    diff_fields,
                    a_key,
                    _entity_sort_key(b_entity),
                )
                if best is None or candidate < best[0]:
                    best = (candidate, a_index, b_index, diff_fields)
        assert best is not None
        _, a_index, b_index, diff_fields = best
        a_entity = a_left.pop(a_index)
        b_entity = b_left.pop(b_index)
        if diff_fields:
            records.append({
                "def": def_name,
                "dxf_name": dxf_name,
                "a_handle": a_entity.get("handle"),
                "b_handle": b_entity.get("handle"),
                "differing_fields": diff_fields,
            })

    for entity in a_left:
        records.append({
            "def": def_name,
            "dxf_name": dxf_name,
            "side": "a",
            "handle": entity.get("handle"),
            "reason": "unmatched",
        })
    for entity in b_left:
        records.append({
            "def": def_name,
            "dxf_name": dxf_name,
            "side": "b",
            "handle": entity.get("handle"),
            "reason": "unmatched",
        })
    return records


def _group_by_dxf(entities: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for entity in entities:
        grouped[str(entity.get("dxf_name") or "")].append(entity)
    return grouped


def _is_residual_row(row: Dict[str, Any]) -> bool:
    return any(int(row.get(key, 0) or 0) > 0 for key in ("removed", "added", "modified"))


def residue_tail_report(a_ir: Dict[str, Any], b_ir: Dict[str, Any], *,
                        name_map: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    diff_report = blockdef_diff.diff_block_definitions(a_ir, b_ir, name_map=name_map)
    defs_a = _definitions_by_name(a_ir or {})
    defs_b = _definitions_by_name(b_ir or {})

    all_records: List[Dict[str, Any]] = []
    defs_examined = 0

    for row in diff_report.get("per_def") or []:
        if not isinstance(row, dict) or not _is_residual_row(row):
            continue
        defs_examined += 1
        def_name = str(row.get("name") or "")
        b_name = str(row.get("b_name") or def_name)
        a_entities = _definition_entities(defs_a.get(def_name), name_map=name_map)
        b_entities = _definition_entities(defs_b.get(b_name))
        grouped_a = _group_by_dxf(a_entities)
        grouped_b = _group_by_dxf(b_entities)
        for dxf_name in sorted(set(grouped_a) | set(grouped_b)):
            all_records.extend(_pair_group(
                def_name,
                dxf_name,
                grouped_a.get(dxf_name, []),
                grouped_b.get(dxf_name, []),
            ))

    all_records.sort(key=_record_sort_key)

    by_field_combo = Counter()
    by_kind = Counter()
    unmatched = {"a": 0, "b": 0}
    for record in all_records:
        by_kind[str(record.get("dxf_name") or "")] += 1
        if "differing_fields" in record:
            by_field_combo[",".join(record["differing_fields"])] += 1
        else:
            unmatched[str(record.get("side") or "")] += 1

    return {
        "schema": SCHEMA_ID,
        "by_field_combo": {key: by_field_combo[key] for key in sorted(by_field_combo)},
        "by_kind": {key: by_kind[key] for key in sorted(by_kind)},
        "unmatched": unmatched,
        "records": all_records[:_RECORD_CAP],
        "records_truncated": len(all_records) > _RECORD_CAP,
        "totals": {
            "defs_examined": defs_examined,
            "residual_entities": len(all_records),
        },
    }


def _load_name_map(path: str) -> Dict[str, str]:
    report = _load_json(path)
    name_map: Dict[str, str] = {}
    for row in report.get("per_def") or []:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        b_name = row.get("b_name")
        if isinstance(name, str) and isinstance(b_name, str):
            name_map[name] = b_name
    return name_map


def _example_handle(record: Dict[str, Any]) -> str:
    if "differing_fields" in record:
        return f"{record.get('a_handle')}->{record.get('b_handle')}"
    return f"{record.get('side')}:{record.get('handle')}"


def _render_markdown(report: Dict[str, Any]) -> str:
    combo_examples: Dict[str, List[str]] = defaultdict(list)
    for record in report.get("records") or []:
        if "differing_fields" not in record:
            continue
        combo = ",".join(record["differing_fields"])
        combo_examples[combo].append(_example_handle(record))

    rows: List[List[Any]] = []
    by_field_combo = report.get("by_field_combo") or {}
    for combo, count in sorted(by_field_combo.items(), key=lambda item: (-item[1], item[0])):
        examples = ", ".join(combo_examples.get(combo, [])[:5])
        rows.append([combo, count, examples])

    parts = [
        "# Residue Tail Report",
        "",
        "| differing_fields | count | example_handles |",
        "| --- | --- | --- |",
    ]
    for combo, count, examples in rows:
        parts.append(f"| {combo} | {count} | {examples} |")
    if not rows:
        parts.append("|  | 0 |  |")
    return "\n".join(parts) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Classify residual block-definition entities by differing geometry fields.")
    parser.add_argument("--a", required=True, help="Path to the census DWG graph IR JSON.")
    parser.add_argument("--b", required=True, help="Path to the post DWG graph IR JSON.")
    parser.add_argument("--interior-diff", required=True,
                        help="Path to the interior blockdef_diff JSON used to extract name remaps.")
    parser.add_argument("--out", required=True, help="Path to write the residue-tail JSON report.")
    parser.add_argument("--md", help="Optional path to write a markdown summary.")
    args = parser.parse_args(argv)

    try:
        report = residue_tail_report(
            _load_json(args.a),
            _load_json(args.b),
            name_map=_load_name_map(args.interior_diff),
        )
        _write_json(args.out, report)
        if args.md:
            with open(args.md, "w", encoding="utf-8") as fh:
                fh.write(_render_markdown(report))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"residue_tail_report: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
