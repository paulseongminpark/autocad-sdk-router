from __future__ import annotations

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import population_forensics


def _entity(handle: str):
    return {"handle": handle, "geometry": {"kind": "line"}}


def _block(name: str, count: int):
    return {
        "name": name,
        "handle": f"H_{name}",
        "def_entities": [_entity(f"{name}_{i}") for i in range(count)],
    }


def _diff(*rows):
    return {
        "schema": "ariadne.blockdef_diff.v1",
        "per_def": list(rows),
        "totals": {"a_entity_total": sum(row["a_total"] for row in rows)},
    }


def _row(name: str, a_total: int, diff0: int, *, modified=0, removed=0, added=0):
    return {
        "name": name,
        "a_total": a_total,
        "diff0": diff0,
        "modified": modified,
        "removed": removed,
        "added": added,
    }


def _by_name(report, name: str):
    return next(row for row in report["per_census_def"] if row["census_name"] == name)


def test_population_forensics_transitions_and_fallback_diagnostics():
    census = {
        "schema": "ariadne.dwg_graph_ir.v1",
        "block_definitions": [
            _block("A", 1),
            _block("B", 2),
            _block("C", 2),
        ],
    }
    diff_a = _diff(
        _row("A", 1, 0, modified=1),
        _row("B", 2, 1, removed=1),
        _row("C", 2, 2),
    )
    diff_b = _diff(
        _row("RENAMED_A", 1, 1),
        _row("B", 2, 1, removed=1),
        _row("RENAMED_UNKNOWN", 2, 2),
    )

    report = population_forensics.build_report(census, diff_a, diff_b, "old", "new")

    assert report["schema"] == "ariadne.population_forensics.v1"
    assert _by_name(report, "A")["transition"] == "healed"
    assert _by_name(report, "B")["transition"] == "dirty_both"
    assert _by_name(report, "C")["transition"] == "a_only"
    assert report["totals"]["healed"] == 1
    assert report["totals"]["dirty_both"] == 1
    assert report["totals"]["defs_in_a_only"] == 1
    assert report["key_diagnosis"]["b_matched_by_unique_a_total"] == 1
    assert report["key_diagnosis"]["b_unmatchable_count"] == 1
    assert report["key_diagnosis"]["b_unmatchable_rows"][0]["reason"] == "ambiguous_entity_count"


def test_name_matches_take_precedence_over_count_fallback():
    census = {
        "schema": "ariadne.dwg_graph_ir.v1",
        "block_definitions": [
            _block("A", 1),
            _block("B", 2),
            _block("C", 3),
        ],
    }
    diff_a = _diff(_row("B", 2, 2))
    diff_b = _diff(
        _row("RENAMED_B", 2, 0, modified=2),
        _row("B", 2, 2),
    )

    report = population_forensics.build_report(census, diff_a, diff_b, "old", "new")

    assert _by_name(report, "B")["b"] == {
        "a_total": 2,
        "diff0": 2,
        "modified": 0,
        "removed": 0,
        "added": 0,
    }
    assert report["key_diagnosis"]["b_matched_by_unique_a_total"] == 0
    assert report["key_diagnosis"]["b_unmatchable_rows"][0]["reason"] == "target_already_mapped"
