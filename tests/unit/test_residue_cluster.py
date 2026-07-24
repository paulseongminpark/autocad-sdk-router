#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for tools/residue_cluster.py residue clustering."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import residue_cluster as rc


def _row(name, removed=0, added=0, modified=0, missing_side=None, b_name=None,
         a_only_kinds=None, b_only_kinds=None, a_total=0, b_total=0, diff0=0):
    row = {
        "name": name,
        "a_total": a_total,
        "b_total": b_total,
        "diff0": diff0,
        "removed": removed,
        "added": added,
        "modified": modified,
        "missing_side": missing_side,
    }
    if b_name is not None:
        row["b_name"] = b_name
    if a_only_kinds is not None:
        row["a_only_kinds"] = a_only_kinds
    if b_only_kinds is not None:
        row["b_only_kinds"] = b_only_kinds
    return row


SYNTHETIC_ROWS = [
    _row("*D501", removed=9, missing_side="b", b_name="ARIADNE_ANON_D501",
         a_total=9, a_only_kinds={"spline": 7, "line": 2}),
    _row("*D502", removed=9, missing_side="b", b_name="ARIADNE_ANON_D502",
         a_total=9, a_only_kinds={"spline": 7, "line": 2}),
    _row("*D601", added=10, missing_side="a", b_total=10),
    _row("*U10", removed=3, missing_side="b", a_total=3),
    _row("LV2", modified=1, a_total=2, b_total=2, diff0=1),
    _row("X-FORM_test$0$Block_5", removed=2, a_total=6, b_total=4, diff0=4),
    _row("X-plan(base)", removed=5, modified=28, a_total=4723, b_total=4718, diff0=4690),
    _row("PLAINDEF", a_total=5, b_total=5, diff0=5),
]

SYNTHETIC_REPORT = {
    "schema": "ariadne.blockdef_diff.v1",
    "per_def": SYNTHETIC_ROWS,
    "totals": {
        "a_def_count": 8,
        "b_def_count": 7,
        "a_entity_total": 4763,
        "b_entity_total": 4747,
        "diff0_total": 4701,
        "interior_diff0_fraction": 0.9868,
    },
    "by_kind_gap": {},
}


# -- classify_family ---------------------------------------------------

def test_classify_family_anon_dimension_star_prefix():
    assert rc.classify_family("*D287") == "anon_dimension"


def test_classify_family_anon_dimension_via_b_name():
    assert rc.classify_family("weirdname", "ARIADNE_ANON_D9") == "anon_dimension"


def test_classify_family_anon_other_star_prefix():
    assert rc.classify_family("*U10") == "anon_other"


def test_classify_family_dynamic_instance():
    assert rc.classify_family("X-FORM_test$0$Block_5") == "dynamic_instance"


def test_classify_family_named():
    assert rc.classify_family("DIMDOT") == "named"


# -- count_bucket -------------------------------------------------------

def test_count_bucket_boundaries():
    assert rc.count_bucket(0) == "0"
    assert rc.count_bucket(1) == "1-9"
    assert rc.count_bucket(9) == "1-9"
    assert rc.count_bucket(10) == "10-99"
    assert rc.count_bucket(99) == "10-99"
    assert rc.count_bucket(100) == "100-999"
    assert rc.count_bucket(1000) == "1000+"


# -- residual_total / is_residual ---------------------------------------

def test_residual_total_sums_removed_added_modified():
    row = _row("x", removed=3, added=1, modified=2)
    assert rc.residual_total(row) == 6


def test_is_residual_false_for_pure_match_row():
    row = _row("PLAINDEF", a_total=5, b_total=5, diff0=5)
    assert rc.is_residual(row) is False


def test_is_residual_true_when_any_component_nonzero():
    assert rc.is_residual(_row("x", modified=1)) is True


# -- dominant_kind --------------------------------------------------------

def test_dominant_kind_prefers_larger_removed_side():
    row = _row("x", removed=5, added=1, a_only_kinds={"spline": 4, "line": 1},
               b_only_kinds={"line": 1})
    assert rc.dominant_kind(row) == ("spline", 4)


def test_dominant_kind_uses_added_side_when_larger():
    row = _row("x", removed=1, added=5, b_only_kinds={"arc": 5})
    assert rc.dominant_kind(row) == ("arc", 5)


def test_dominant_kind_none_when_no_kind_data():
    row = _row("x", removed=9, missing_side="b")
    assert rc.dominant_kind(row) is None


# -- shape_of --------------------------------------------------------------

def test_shape_of_pure_a_only():
    assert rc.shape_of(9, 0, 0) == "a_only"


def test_shape_of_pure_b_only():
    assert rc.shape_of(0, 10, 0) == "b_only"


def test_shape_of_pure_mutated():
    assert rc.shape_of(0, 0, 1) == "mutated"


def test_shape_of_mixed_when_multiple_nonzero():
    assert rc.shape_of(5, 0, 28) == "mixed"


# -- cluster_residuals ------------------------------------------------------

def test_cluster_residuals_excludes_non_residual_rows():
    clusters = rc.cluster_residuals(SYNTHETIC_ROWS)
    all_rows = [row for rows in clusters.values() for row in rows]
    assert all(row["name"] != "PLAINDEF" for row in all_rows)


def test_cluster_residuals_groups_same_signature_together():
    clusters = rc.cluster_residuals(SYNTHETIC_ROWS)
    matching = [rows for rows in clusters.values()
                if {row["name"] for row in rows} == {"*D501", "*D502"}]
    assert len(matching) == 1


def test_cluster_residuals_separates_different_buckets():
    clusters = rc.cluster_residuals(SYNTHETIC_ROWS)
    # *D601 (added=10, bucket 10-99) must NOT share a cluster with *D501/*D502 (bucket 1-9)
    for rows in clusters.values():
        names = {row["name"] for row in rows}
        if "*D601" in names:
            assert "*D501" not in names


# -- build_report_table (ranking + hypothesis content) -----------------------

def test_build_report_table_ranked_by_entities_desc():
    table = rc.build_report_table(SYNTHETIC_REPORT)
    entities = [row["entities"] for row in table]
    assert entities == sorted(entities, reverse=True)


def test_build_report_table_top_cluster_is_named_mixed_family():
    table = rc.build_report_table(SYNTHETIC_REPORT)
    top = table[0]
    assert top["entities"] == 33
    assert top["defs"] == 1
    assert "named" in top["hypothesis"]
    assert "mixed" in top["hypothesis"]


def test_build_report_table_anon_dimension_cluster_mentions_kind_and_shape():
    table = rc.build_report_table(SYNTHETIC_REPORT)
    anon_cluster = next(row for row in table if row["entities"] == 18)
    assert anon_cluster["defs"] == 2
    assert "anon" in anon_cluster["hypothesis"]
    assert "dimension" in anon_cluster["hypothesis"]
    assert "spline" in anon_cluster["hypothesis"]
    assert "a_only" in anon_cluster["hypothesis"]


def test_build_report_table_omits_non_residual_defs_entirely():
    table = rc.build_report_table(SYNTHETIC_REPORT)
    total_defs = sum(row["defs"] for row in table)
    assert total_defs == 7  # 8 rows minus the 1 pure-match PLAINDEF row


# -- CLI main() -----------------------------------------------------------

def test_main_writes_markdown_report(tmp_path):
    report_path = tmp_path / "blockdef_diff_mini.json"
    report_path.write_text(json.dumps(SYNTHETIC_REPORT, ensure_ascii=False), encoding="utf-8")
    out_path = tmp_path / "residue_clusters_mini.md"

    exit_code = rc.main([str(report_path), "--out", str(out_path)])

    assert exit_code == 0
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "cluster" in content.lower()
    assert "hypothesis" in content.lower()
    assert "*D501" not in content  # table is cluster-level, not per-def


def test_main_returns_nonzero_on_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    out_path = tmp_path / "out.md"
    exit_code = rc.main([str(missing), "--out", str(out_path)])
    assert exit_code != 0
