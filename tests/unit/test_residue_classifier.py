#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for residue_classifier (stdlib only, real interior_diff schema)."""
from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TOOLS = os.path.join(_ROOT, "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

import residue_classifier as rc  # noqa: E402


def _diff(by_kind, fraction=0.95):
    """Build an interior_diff.json-shaped dict. by_kind maps kind -> (a, b)."""
    return {
        "schema": "ariadne.interior_diff.v1",
        "totals": {"interior_diff0_fraction": fraction},
        "by_kind_gap": {k: {"a_count": a, "b_count": b} for k, (a, b) in by_kind.items()},
    }


# Baseline mirrors 1.dwg (R4l): residue-bearing kinds are block_reference / line /
# lwpolyline / solid / wipeout; hatch / spline / arc roundtrip clean.
_BASELINE = _diff({
    "block_reference": (1183, 956),
    "line": (100, 110),
    "lwpolyline": (50, 48),
    "solid": (0, 226),
    "wipeout": (33, 0),
    "hatch": (265, 265),
    "spline": (100, 100),
    "arc": (10, 10),
}, fraction=0.95)


def test_kind_gaps_and_residue_kinds():
    gaps = rc.kind_gaps(_BASELINE)
    assert gaps["wipeout"]["gap"] == -33
    assert gaps["solid"]["gap"] == 226
    assert gaps["hatch"]["gap"] == 0
    kinds = rc.residue_kinds(_BASELINE)
    assert kinds == {"block_reference", "line", "lwpolyline", "solid", "wipeout"}


def test_generalizes_when_signature_subset_of_baseline():
    # target residue only in known kinds; wipeout drop is deferred.
    target = _diff({
        "line": (200, 205),        # known residue kind
        "wipeout": (10, 0),        # known + dropped
        "hatch": (300, 300),       # clean
        "spline": (400, 400),      # clean
    }, fraction=0.97)
    deferred = [{"kind": "wipeout", "handle": "AB"} for _ in range(10)]
    rep = rc.classify(target, _BASELINE, target_deferred=deferred)
    assert rep["verdict"] == "GENERALIZES"
    assert rep["novel_class_found"] is False
    assert rep["deferred_integrity"]["ok"] is True


def test_novel_class_flagged_when_clean_kind_gains_gap():
    # hatch was CLEAN on baseline; a gap here is a NOVEL residue class.
    target = _diff({
        "hatch": (20, 22),         # novel: hatch clean on baseline
        "line": (100, 101),        # known
    }, fraction=0.90)
    rep = rc.classify(target, _BASELINE, target_deferred=[])
    assert rep["verdict"] == "NOVEL_CLASS"
    assert rep["novel_class_found"] is True
    assert rep["novel_residue_kinds"] == ["hatch"]


def test_silent_drop_flagged_when_drop_not_deferred():
    # wipeout dropped on rebuild but NOT present in deferred.json -> FM8.
    target = _diff({"wipeout": (5, 0), "line": (10, 12)}, fraction=0.80)
    rep = rc.classify(target, _BASELINE, target_deferred=None)
    assert rep["verdict"] == "SILENT_DROP"
    assert rep["deferred_integrity"]["ok"] is False
    assert rep["deferred_integrity"]["undeferred_drops"] == ["wipeout"]


def test_deferred_drop_is_not_silent():
    target = _diff({"wipeout": (5, 0)}, fraction=0.99)
    deferred = [{"kind": "wipeout"}]
    rep = rc.classify(target, _BASELINE, target_deferred=deferred)
    assert rep["deferred_integrity"]["ok"] is True
    assert rep["verdict"] == "GENERALIZES"


def test_silent_drop_takes_precedence_over_novel():
    # both a novel hatch gap AND an undeferred wipeout drop -> SILENT_DROP wins
    # the single verdict, but the novel class is STILL reported in full.
    target = _diff({"hatch": (20, 25), "wipeout": (4, 0)}, fraction=0.70)
    rep = rc.classify(target, _BASELINE, target_deferred=[])
    assert rep["verdict"] == "SILENT_DROP"
    assert rep["novel_class_found"] is True
    assert "hatch" in rep["novel_residue_kinds"]


def test_main_cli_writes_report_and_exit_code(tmp_path):
    base_p = tmp_path / "baseline.json"
    tgt_p = tmp_path / "target.json"
    out_p = tmp_path / "report.json"
    base_p.write_text(json.dumps(_BASELINE), encoding="utf-8")
    # a clean target (only known residue kinds) -> GENERALIZES -> exit 0
    tgt_p.write_text(json.dumps(_diff({"line": (10, 12)})), encoding="utf-8")
    rc_code = rc.main(["--target", str(tgt_p), "--baseline", str(base_p),
                       "--out", str(out_p)])
    assert rc_code == 0
    loaded = json.loads(out_p.read_text(encoding="utf-8"))
    assert loaded["verdict"] == "GENERALIZES"
    # a novel target -> exit 2 (honest gate)
    tgt_p.write_text(json.dumps(_diff({"circle": (5, 9)})), encoding="utf-8")
    assert rc.main(["--target", str(tgt_p), "--baseline", str(base_p)]) == 2
