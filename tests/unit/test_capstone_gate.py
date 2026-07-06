#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/unit/test_capstone_gate.py -- unit coverage for the Closeout
#129a/#130 fail-loud gate + real records regen/diff, and the new
tools/cert_artifact_index.py (codex-5.5-xhigh audit finding 6).

No accoreconsole/AutoCAD engine anywhere in this file: regen_gate_report/
combine_gate_statuses/build_records_patch/table_record_diff_reports are
exercised against SYNTHESIZED apply_result/census_ir fixtures (mirroring
the real reference-run defect: 14 requested, 12 applied, 2 silently
dropped -- runs/capstone_final_20260706_062040), and cert_artifact_index
is exercised against a tmp_path fixture tree, never the real runs/ dir.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.normpath(os.path.join(os.path.dirname(_THIS_DIR), "..", "tools"))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

frc = importlib.import_module("full_roundtrip_capstone")
cai = importlib.import_module("cert_artifact_index")


# --------------------------------------------------------------------------- #
# regen_gate_report (#129a) -- the requested-vs-applied arithmetic
# --------------------------------------------------------------------------- #

def test_regen_gate_report_all_applied_is_ok():
    apply_result = {"status": "ok", "op_count_applied": 5, "applied_ops": list(range(5))}
    gate = frc.regen_gate_report(5, apply_result)
    assert gate["gate_status"] == "ok"
    assert gate["ok"] is True
    assert gate["applied_count"] == 5
    assert gate["dropped_ops"] == []


def test_regen_gate_report_reference_run_defect_14_requested_12_applied():
    # Mirrors the real reference run (runs/capstone_final_20260706_062040):
    # 14 ops requested, 12 applied, apply_result status=="ok" -- the exact
    # case that used to silently report top-level status="ok".
    apply_result = {
        "status": "ok",
        "op_count_applied": 12,
        "applied_ops": list(range(12)),
        "deferred_ops": [
            {"index": 12, "operation": "insert_block", "reason": "no native write handler"},
            {"index": 13, "operation": "insert_block", "reason": "no native write handler"},
        ],
    }
    gate = frc.regen_gate_report(14, apply_result)
    assert gate["gate_status"] == "ok_with_drops"
    assert gate["ok"] is False
    assert gate["applied_count"] == 12
    assert gate["dropped_count"] == 2
    assert {d["operation"] for d in gate["dropped_ops"]} == {"insert_block"}


def test_regen_gate_report_falls_back_to_applied_ops_length_when_op_count_applied_absent():
    apply_result = {"status": "ok", "applied_ops": [1, 2, 3]}
    gate = frc.regen_gate_report(5, apply_result)
    assert gate["applied_count"] == 3
    assert gate["gate_status"] == "ok_with_drops"
    # 2 unaccounted for by applied_count + deferred_ops (empty) -> one synthetic entry
    assert gate["dropped_count"] == 1
    assert "unaccounted" in gate["dropped_ops"][0]["reason"]


def test_regen_gate_report_non_ok_status_passes_through_unchanged():
    apply_result = {"status": "blocked", "reason": "original_changed_pre_apply"}
    gate = frc.regen_gate_report(3, apply_result)
    assert gate["gate_status"] == "blocked"
    assert gate["ok"] is False
    assert gate["applied_count"] == 0
    assert gate["dropped_count"] == 1  # all 3 unaccounted for


def test_regen_gate_report_none_apply_result_and_zero_ops_is_unknown_not_ok():
    gate = frc.regen_gate_report(0, None)
    assert gate["applied_count"] == 0
    assert gate["dropped_ops"] == []
    assert gate["apply_status"] is None
    assert gate["gate_status"] == "unknown"


# --------------------------------------------------------------------------- #
# combine_gate_statuses
# --------------------------------------------------------------------------- #

def test_combine_gate_statuses_empty_is_ok():
    assert frc.combine_gate_statuses([]) == "ok"


def test_combine_gate_statuses_all_ok():
    assert frc.combine_gate_statuses(["ok", "ok"]) == "ok"


def test_combine_gate_statuses_one_ok_with_drops_rolls_up():
    assert frc.combine_gate_statuses(["ok", "ok_with_drops"]) == "ok_with_drops"


def test_combine_gate_statuses_worse_status_outranks_ok_with_drops():
    assert frc.combine_gate_statuses(["ok_with_drops", "blocked"]) == "blocked"


def test_combine_gate_statuses_first_non_ok_family_status_wins():
    assert frc.combine_gate_statuses(["partial", "blocked"]) == "partial"


# --------------------------------------------------------------------------- #
# build_records_patch / table_record_diff_reports (#130) -- against a FAKE,
# reduced op_roundtrip_probe module (2 fake table classes) so this test does
# not depend on the real 7-table RECORD_TABLE_CLASSES field lists.
# --------------------------------------------------------------------------- #

class _FakeOrp:
    WIDGET_FIELDS = ("color", "size")
    GADGET_FIELDS = ("weight",)

    @staticmethod
    def widget_diff(expected, actual):
        if actual is None:
            return sorted(expected)
        return sorted(k for k, v in expected.items() if actual.get(k) != v)

    @staticmethod
    def gadget_diff(expected, actual):
        if actual is None:
            return sorted(expected)
        return sorted(k for k, v in expected.items() if actual.get(k) != v)


_FAKE_TABLE_CLASSES = (
    {"label": "widget", "op_name": "create_widget", "table_key": "widgets",
     "fields_attr": "WIDGET_FIELDS", "diff_attr": "widget_diff"},
    {"label": "gadget", "op_name": "create_gadget", "table_key": "gadgets",
     "fields_attr": "GADGET_FIELDS", "diff_attr": "gadget_diff"},
)


def test_record_op_args_from_record_only_requested_fields_present():
    record = {"name": "W1", "color": "red", "size": 3, "unrelated": "x"}
    args = frc.record_op_args_from_record(record, ("color", "size"))
    assert args == {"name": "W1", "color": "red", "size": 3}


def test_build_records_patch_builds_one_op_per_named_record_and_counts_unnamed():
    census_ir = {"symbol_tables": {
        "widgets": [{"name": "W1", "color": "red"}, {"color": "no-name-dropped"}],
        "gadgets": [{"name": "G1", "weight": 5}],
    }}
    patch, meta = frc.build_records_patch(
        census_ir, {"original_path": "a.dwg", "staged_path": "b.dwg"}, "pid",
        op_roundtrip_probe_mod=_FakeOrp(), table_classes=_FAKE_TABLE_CLASSES)
    ops = patch["operations"]
    assert len(ops) == 2
    op_names = {op["operation"] for op in ops}
    assert op_names == {"create_widget", "create_gadget"}
    assert meta["skipped_unnamed"] == {"widget": 1}
    assert meta["per_table_requested"] == {"widget": 1, "gadget": 1}
    assert patch["postconditions"] == []
    assert patch["policy"]["staged_copy"] is True


def test_build_records_patch_per_table_limit_truncates_each_table_independently():
    census_ir = {"symbol_tables": {
        "widgets": [{"name": "W%d" % i} for i in range(5)],
        "gadgets": [{"name": "G%d" % i} for i in range(5)],
    }}
    patch, meta = frc.build_records_patch(
        census_ir, {"original_path": "a.dwg", "staged_path": "b.dwg"}, "pid",
        op_roundtrip_probe_mod=_FakeOrp(), table_classes=_FAKE_TABLE_CLASSES, per_table_limit=2)
    assert meta["per_table_requested"] == {"widget": 2, "gadget": 2}
    assert len(patch["operations"]) == 4


def test_table_record_diff_reports_post_ir_none_is_explicit_not_a_zero_diff_pass():
    census_ir = {"symbol_tables": {"widgets": [{"name": "W1", "color": "red"}], "gadgets": []}}
    reports = frc.table_record_diff_reports(
        census_ir, None, op_roundtrip_probe_mod=_FakeOrp(), table_classes=_FAKE_TABLE_CLASSES,
        unavailable_reason="records regen never reached post-inspect")
    assert reports["widget"]["records_compared"] == 0
    assert reports["widget"]["zero_diff_count"] == 0
    assert "records regen never reached post-inspect" in reports["widget"]["structural_note"]
    assert reports["gadget"]["structural_note"]


def test_table_record_diff_reports_real_post_ir_gives_true_zero_diff():
    census_ir = {"symbol_tables": {"widgets": [{"name": "W1", "color": "red", "size": 3}], "gadgets": []}}
    post_ir = {"symbol_tables": {"widgets": [{"name": "W1", "color": "red", "size": 3}]}}
    reports = frc.table_record_diff_reports(
        census_ir, post_ir, op_roundtrip_probe_mod=_FakeOrp(), table_classes=_FAKE_TABLE_CLASSES)
    assert reports["widget"]["records_compared"] == 1
    assert reports["widget"]["zero_diff_count"] == 1
    assert reports["widget"]["diffs"] == []


def test_table_record_diff_reports_detects_a_real_mismatch():
    census_ir = {"symbol_tables": {"widgets": [{"name": "W1", "color": "red", "size": 3}], "gadgets": []}}
    post_ir = {"symbol_tables": {"widgets": [{"name": "W1", "color": "BLUE", "size": 3}]}}
    reports = frc.table_record_diff_reports(
        census_ir, post_ir, op_roundtrip_probe_mod=_FakeOrp(), table_classes=_FAKE_TABLE_CLASSES)
    assert reports["widget"]["zero_diff_count"] == 0
    assert len(reports["widget"]["diffs"]) == 1
    assert reports["widget"]["diffs"][0]["record_diff"] == ["color"]


def test_table_record_diff_reports_zero_named_records_is_flagged_vacuous():
    census_ir = {"symbol_tables": {"widgets": [], "gadgets": []}}
    post_ir = {"symbol_tables": {"widgets": []}}
    reports = frc.table_record_diff_reports(
        census_ir, post_ir, op_roundtrip_probe_mod=_FakeOrp(), table_classes=_FAKE_TABLE_CLASSES)
    assert reports["widget"]["records_compared"] == 0
    assert "vacuously" in reports["widget"]["structural_note"]


# --------------------------------------------------------------------------- #
# run_records_batch -- fake patch_engine_mod (no real accoreconsole call);
# verifies the glue (build_records_patch -> apply_staged -> shape), same
# split as test_isolate_regenerated_entities_delegates_to_added_entities_ir.
# --------------------------------------------------------------------------- #

def test_run_records_batch_calls_apply_staged_with_built_patch(tmp_path):
    calls = {}

    class _FakePatchEngine:
        @staticmethod
        def apply_staged(patch, dwg_path, out_dir):
            calls["patch"] = patch
            calls["dwg_path"] = dwg_path
            calls["out_dir"] = out_dir
            return {"status": "ok", "op_count_applied": len(patch["operations"]),
                   "applied_ops": patch["operations"]}

    census_ir = {"symbol_tables": {"widgets": [{"name": "W1", "color": "red"}], "gadgets": []}}
    result = frc.run_records_batch(
        census_ir, "seed.dwg", str(tmp_path), "pid", table_classes=_FAKE_TABLE_CLASSES,
        op_roundtrip_probe_mod=_FakeOrp(), patch_engine_mod=_FakePatchEngine())
    assert result["op_count"] == 1
    assert calls["dwg_path"] == "seed.dwg"
    assert calls["out_dir"] == str(tmp_path)
    assert result["apply_result"]["status"] == "ok"
    assert result["seconds_per_op"] is not None


# --------------------------------------------------------------------------- #
# cert_artifact_index -- glob-based scan over a tmp_path fixture tree
# --------------------------------------------------------------------------- #

def test_discover_run_dirs_missing_root_returns_empty(tmp_path):
    assert cai.discover_run_dirs(str(tmp_path / "does_not_exist")) == []


def test_build_index_finds_nested_json_and_kind_is_filename_stem(tmp_path):
    run1 = tmp_path / "runs" / "run1"
    (run1 / "nested").mkdir(parents=True)
    (run1 / "summary.json").write_text('{"status": "ok"}', encoding="utf-8")
    (run1 / "nested" / "deep.json").write_text('{"a": 1}', encoding="utf-8")

    index = cai.build_index(router_home=str(tmp_path), scan_roots=["runs", "attended_runs"])
    assert index["artifact_count"] == 2
    kinds = {a["kind"] for a in index["artifacts"]}
    assert kinds == {"summary", "deep"}
    roots = {r["name"]: r["exists"] for r in index["scan_roots"]}
    assert roots == {"runs": True, "attended_runs": False}


def test_build_index_sha256_matches_hashlib(tmp_path):
    run1 = tmp_path / "runs" / "run1"
    run1.mkdir(parents=True)
    content = b'{"a": 1}'
    (run1 / "summary.json").write_bytes(content)
    index = cai.build_index(router_home=str(tmp_path), scan_roots=["runs"])
    assert index["artifacts"][0]["sha256"] == hashlib.sha256(content).hexdigest()
    assert index["artifacts"][0]["path"] == "runs/run1/summary.json"


def test_build_index_flags_invalid_json_without_crashing(tmp_path):
    run1 = tmp_path / "runs" / "run1"
    run1.mkdir(parents=True)
    (run1 / "good.json").write_text('{"ok": true}', encoding="utf-8")
    # A raw (unescaped) control character inside a string value -- invalid
    # per strict JSON, and a real pattern found in this repo's own runs/
    # tree (native_batch_*/results/*.json prompt fields).
    (run1 / "bad.json").write_bytes(b'{"prompt": "\nnot escaped"}')

    index = cai.build_index(router_home=str(tmp_path), scan_roots=["runs"])
    assert index["artifact_count"] == 2
    assert index["invalid_count"] == 1
    assert index["invalid_paths"] == ["runs/run1/bad.json"]
    by_kind = {a["kind"]: a for a in index["artifacts"]}
    assert by_kind["good"]["json_valid"] is True
    assert by_kind["bad"]["json_valid"] is False
    assert by_kind["bad"]["json_error"]


def test_build_index_ignores_non_json_files(tmp_path):
    run1 = tmp_path / "runs" / "run1"
    run1.mkdir(parents=True)
    (run1 / "summary.json").write_text("{}", encoding="utf-8")
    (run1 / "staged_input.dwg").write_bytes(b"not json, a fake dwg")
    index = cai.build_index(router_home=str(tmp_path), scan_roots=["runs"])
    assert index["artifact_count"] == 1
    assert index["artifacts"][0]["kind"] == "summary"


def test_build_index_is_idempotent_on_an_unchanged_tree(tmp_path):
    run1 = tmp_path / "runs" / "run1"
    run1.mkdir(parents=True)
    (run1 / "summary.json").write_text('{"x": 1}', encoding="utf-8")

    first = cai.build_index(router_home=str(tmp_path), scan_roots=["runs"])
    second = cai.build_index(router_home=str(tmp_path), scan_roots=["runs"])
    first.pop("generated_at")
    second.pop("generated_at")
    assert first == second


def test_main_writes_report_and_exit_code_reflects_invalid_count(tmp_path):
    run1 = tmp_path / "runs" / "run1"
    run1.mkdir(parents=True)
    (run1 / "summary.json").write_text('{"ok": true}', encoding="utf-8")
    out_path = tmp_path / "reports" / "cert_artifact_index.json"

    rc = cai.main(["--router-home", str(tmp_path), "--scan-root", "runs", "--out", str(out_path)])
    assert rc == 0
    assert out_path.is_file()
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["artifact_count"] == 1

    (run1 / "bad.json").write_bytes(b'{"x": "\x01"}')
    rc2 = cai.main(["--router-home", str(tmp_path), "--scan-root", "runs", "--out", str(out_path)])
    assert rc2 == 1
