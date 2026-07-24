#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ir_section_coverage.py -- compare two dwg_graph_ir.v1 documents by section."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

JSON_ENCODING = "utf-8-sig"
SCHEMA_ID = "ariadne.ir_section_coverage.v1"
XDATA_FIELD = "xdata"
_MISSING_SAMPLE_LIMIT = 20
_WORST_SECTION_LIMIT = 5


def _pct(a_count: int, b_count: int) -> float:
    if a_count <= 0:
        return 100.0
    return round((min(a_count, b_count) / float(a_count)) * 100.0, 2)


def _is_absent(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, dict, tuple, set, str)):
        return len(value) == 0
    return False


def _ensure_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _ensure_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding=JSON_ENCODING) as fh:
        return json.load(fh)


def _write_text(path: str, text: str) -> str:
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding=JSON_ENCODING) as fh:
        fh.write(text)
    return path


def _section_list(ir: Dict[str, Any], key: str, side: str, absent: List[str]) -> List[Any]:
    raw = ir.get(key)
    if _is_absent(raw):
        absent.append("%s.%s" % (side, key))
    return _ensure_list(raw)


def _section_dict(ir: Dict[str, Any], key: str, side: str, absent: List[str]) -> Dict[str, Any]:
    raw = ir.get(key)
    if _is_absent(raw):
        absent.append("%s.%s" % (side, key))
    return _ensure_dict(raw)


def _names_in_order(records: Sequence[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        name = record.get("name")
        if isinstance(name, str) and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _count_nonempty_xdata(entities: Iterable[Any]) -> int:
    count = 0
    for entity in entities:
        if isinstance(entity, dict) and _ensure_list(entity.get(XDATA_FIELD)):
            count += 1
    return count


def _count_def_entities(defs: Iterable[Any]) -> int:
    total = 0
    for block_def in defs:
        if not isinstance(block_def, dict):
            continue
        total += len(_ensure_list(block_def.get("def_entities")))
    return total


def _missing_names_sample(a_defs: Sequence[Dict[str, Any]], b_defs: Sequence[Dict[str, Any]]) -> List[str]:
    b_names = set(_names_in_order(b_defs))
    sample: List[str] = []
    for name in _names_in_order(a_defs):
        if name not in b_names:
            sample.append(name)
        if len(sample) >= _MISSING_SAMPLE_LIMIT:
            break
    return sample


def section_coverage(ir_a: Dict[str, Any], ir_b: Dict[str, Any]) -> Dict[str, Any]:
    absent: List[str] = []

    entities_a = _section_list(ir_a, "entities", "a", absent)
    entities_b = _section_list(ir_b, "entities", "b", absent)
    defs_a = _section_list(ir_a, "block_definitions", "a", absent)
    defs_b = _section_list(ir_b, "block_definitions", "b", absent)
    sym_a = _section_dict(ir_a, "symbol_tables", "a", absent)
    sym_b = _section_dict(ir_b, "symbol_tables", "b", absent)
    layouts_a = _section_list(ir_a, "layouts", "a", absent)
    layouts_b = _section_list(ir_b, "layouts", "b", absent)
    dicts_a = _section_list(ir_a, "dictionaries", "a", absent)
    dicts_b = _section_list(ir_b, "dictionaries", "b", absent)
    xrecords_a = _section_list(ir_a, "xrecords", "a", absent)
    xrecords_b = _section_list(ir_b, "xrecords", "b", absent)
    ext_dicts_a = _section_list(ir_a, "extension_dictionaries", "a", absent)
    ext_dicts_b = _section_list(ir_b, "extension_dictionaries", "b", absent)

    a_layout_names = _names_in_order(layouts_a)
    b_layout_names = set(_names_in_order(layouts_b))

    symbol_tables: Dict[str, Dict[str, Any]] = {}
    for table_name in sorted(set(sym_a) | set(sym_b)):
        a_records = len(_ensure_list(sym_a.get(table_name)))
        b_records = len(_ensure_list(sym_b.get(table_name)))
        symbol_tables[table_name] = {
            "a_records": a_records,
            "b_records": b_records,
            "pct": _pct(a_records, b_records),
        }

    block_defs = {
        "a_defs": len(defs_a),
        "b_defs": len(defs_b),
        "a_def_entities": _count_def_entities(defs_a),
        "b_def_entities": _count_def_entities(defs_b),
    }
    block_defs["pct_defs"] = _pct(block_defs["a_defs"], block_defs["b_defs"])
    block_defs["pct_def_entities"] = _pct(
        block_defs["a_def_entities"], block_defs["b_def_entities"]
    )
    block_defs["missing_def_names_sample"] = _missing_names_sample(defs_a, defs_b)

    sections = {
        "entities": {
            "a": len(entities_a),
            "b": len(entities_b),
            "pct": _pct(len(entities_a), len(entities_b)),
        },
        "block_definitions": block_defs,
        "symbol_tables": {"per_table": symbol_tables},
        "layouts": {
            "a": len(layouts_a),
            "b": len(layouts_b),
            "names_missing_in_b": [name for name in a_layout_names if name not in b_layout_names],
        },
        "dictionaries": {"a": len(dicts_a), "b": len(dicts_b)},
        "xrecords": {"a": len(xrecords_a), "b": len(xrecords_b)},
        "extension_dictionaries": {"a": len(ext_dicts_a), "b": len(ext_dicts_b)},
        "xdata": {
            "entities_with_xdata_a": _count_nonempty_xdata(entities_a),
            "entities_with_xdata_b": _count_nonempty_xdata(entities_b),
        },
    }

    weighted_pairs: List[Tuple[str, int, int]] = [
        ("entities", sections["entities"]["a"], sections["entities"]["b"]),
        ("block_definitions", block_defs["a_defs"], block_defs["b_defs"]),
        ("block_definitions.def_entities", block_defs["a_def_entities"], block_defs["b_def_entities"]),
        ("layouts", sections["layouts"]["a"], sections["layouts"]["b"]),
        ("dictionaries", sections["dictionaries"]["a"], sections["dictionaries"]["b"]),
        ("xrecords", sections["xrecords"]["a"], sections["xrecords"]["b"]),
        (
            "extension_dictionaries",
            sections["extension_dictionaries"]["a"],
            sections["extension_dictionaries"]["b"],
        ),
        (
            "xdata",
            sections["xdata"]["entities_with_xdata_a"],
            sections["xdata"]["entities_with_xdata_b"],
        ),
    ]
    for table_name, counts in symbol_tables.items():
        weighted_pairs.append(
            ("symbol_tables.%s" % table_name, counts["a_records"], counts["b_records"])
        )

    total_a = sum(a_count for _, a_count, _ in weighted_pairs)
    total_matched = sum(min(a_count, b_count) for _, a_count, b_count in weighted_pairs)
    overall_weighted_pct = 100.0 if total_a == 0 else round((total_matched / float(total_a)) * 100.0, 2)

    worst_sections = []
    ranked = sorted(
        (
            {
                "section": name,
                "missing": max(a_count - b_count, 0),
                "a": a_count,
                "b": b_count,
            }
            for name, a_count, b_count in weighted_pairs
        ),
        key=lambda item: (-item["missing"], item["section"]),
    )
    for item in ranked:
        if item["missing"] <= 0:
            continue
        worst_sections.append(item)
        if len(worst_sections) >= _WORST_SECTION_LIMIT:
            break

    return {
        "schema": SCHEMA_ID,
        "sections_absent": absent,
        "sections": sections,
        "headline": {
            "overall_weighted_pct": overall_weighted_pct,
            "worst_sections": worst_sections,
        },
    }


def _markdown_report(report: Dict[str, Any], ir_a_path: str, ir_b_path: str) -> str:
    sections = report["sections"]
    lines = [
        "# IR Section Coverage",
        "",
        "A: `%s`" % ir_a_path,
        "B: `%s`" % ir_b_path,
        "",
        "Overall weighted coverage: %.2f%%" % report["headline"]["overall_weighted_pct"],
        "Sections absent: %s" % (", ".join(report["sections_absent"]) if report["sections_absent"] else "(none)"),
        "",
        "| Section | A | B | Coverage | Notes |",
        "| --- | ---: | ---: | ---: | --- |",
        "| entities | {a} | {b} | {pct:.2f}% | |".format(**sections["entities"]),
        "| block_definitions | {a_defs} | {b_defs} | {pct_defs:.2f}% | missing sample: {sample} |".format(
            a_defs=sections["block_definitions"]["a_defs"],
            b_defs=sections["block_definitions"]["b_defs"],
            pct_defs=sections["block_definitions"]["pct_defs"],
            sample=", ".join(sections["block_definitions"]["missing_def_names_sample"]) or "(none)",
        ),
        "| block_definitions.def_entities | {a_def_entities} | {b_def_entities} | {pct_def_entities:.2f}% | |".format(
            **sections["block_definitions"]
        ),
        "| layouts | {a} | {b} | {pct:.2f}% | missing names: {names} |".format(
            a=sections["layouts"]["a"],
            b=sections["layouts"]["b"],
            pct=_pct(sections["layouts"]["a"], sections["layouts"]["b"]),
            names=", ".join(sections["layouts"]["names_missing_in_b"]) or "(none)",
        ),
        "| dictionaries | {a} | {b} | {pct:.2f}% | |".format(
            a=sections["dictionaries"]["a"],
            b=sections["dictionaries"]["b"],
            pct=_pct(sections["dictionaries"]["a"], sections["dictionaries"]["b"]),
        ),
        "| xrecords | {a} | {b} | {pct:.2f}% | |".format(
            a=sections["xrecords"]["a"],
            b=sections["xrecords"]["b"],
            pct=_pct(sections["xrecords"]["a"], sections["xrecords"]["b"]),
        ),
        "| extension_dictionaries | {a} | {b} | {pct:.2f}% | |".format(
            a=sections["extension_dictionaries"]["a"],
            b=sections["extension_dictionaries"]["b"],
            pct=_pct(
                sections["extension_dictionaries"]["a"],
                sections["extension_dictionaries"]["b"],
            ),
        ),
        "| xdata entities | {a} | {b} | {pct:.2f}% | |".format(
            a=sections["xdata"]["entities_with_xdata_a"],
            b=sections["xdata"]["entities_with_xdata_b"],
            pct=_pct(
                sections["xdata"]["entities_with_xdata_a"],
                sections["xdata"]["entities_with_xdata_b"],
            ),
        ),
    ]

    per_table = sections["symbol_tables"]["per_table"]
    if per_table:
        for table_name in sorted(per_table):
            row = per_table[table_name]
            lines.append(
                "| symbol_tables.%s | %d | %d | %.2f%% | |"
                % (table_name, row["a_records"], row["b_records"], row["pct"])
            )

    if report["headline"]["worst_sections"]:
        lines.extend(["", "Worst sections:"])
        for item in report["headline"]["worst_sections"]:
            lines.append(
                "- %s: missing %d (%d -> %d)"
                % (item["section"], item["missing"], item["a"], item["b"])
            )
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two dwg_graph_ir.v1 documents by section.")
    parser.add_argument("ir_a")
    parser.add_argument("ir_b")
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    args = parser.parse_args(argv)

    missing = [path for path in (args.ir_a, args.ir_b) if not os.path.isfile(path)]
    if missing:
        for path in missing:
            print("error: missing file: %s" % path, file=sys.stderr)
        return 3

    try:
        ir_a = _load_json(args.ir_a)
        ir_b = _load_json(args.ir_b)
    except (OSError, json.JSONDecodeError) as exc:
        print("error: failed to load IRs: %s" % exc, file=sys.stderr)
        return 1

    report = section_coverage(ir_a, ir_b)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    md_text = _markdown_report(report, args.ir_a, args.ir_b)

    if args.out_json:
        _write_text(args.out_json, text)
    if args.out_md:
        _write_text(args.out_md, md_text)

    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
