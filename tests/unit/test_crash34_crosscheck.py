#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/unit/test_crash34_crosscheck.py -- unit coverage for
tools/crash34_host_crosscheck.py (closeout follow-up F-b).

Two layers, same split as test_capstone_gate.py:
  * synthetic fixture tests (tmp_path matrix/registry files) exercise
    classify_one's decision rules in isolation -- no dependency on the real
    465-op sweep ever changing shape.
  * real-artifact tests run build_report against the REAL, already-committed
    measure/reachable_matrix.jsonl + config/operations.v2.json (read-only --
    this test never writes to either) and check join completeness, verdict
    enum validity, and the bucket counts against the 2026-07-06 manual
    triage (com_activex=16/live=5/custom-class=6/misc=7).
"""
from __future__ import annotations

import importlib
import json
import os
import sys

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.normpath(os.path.join(os.path.dirname(_THIS_DIR), "..", "tools"))
_ROUTER_HOME = os.path.normpath(os.path.join(os.path.dirname(_THIS_DIR), ".."))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

c34 = importlib.import_module("crash34_host_crosscheck")

_REAL_MATRIX = os.path.join(_ROUTER_HOME, "measure", "reachable_matrix.jsonl")
_REAL_REGISTRY = os.path.join(_ROUTER_HOME, "config", "operations.v2.json")


# --------------------------------------------------------------------------- #
# classify_one -- synthetic rows/ops, one per decision branch
# --------------------------------------------------------------------------- #

def _row(op_id, fixture_available=False, fixture_evidence=None):
    return {
        "op_id": op_id, "class": "CRASH", "fixture_available": fixture_available,
        "fixture_evidence": fixture_evidence,
        "empty_arg_probe": {"reason": "native job produced no parseable result JSON"},
    }


def test_classify_one_catalogued_not_runnable_is_expected_crash():
    row = _row("fake.op.a")
    op = {"family": "misc_family", "engine_tier": "native_arx_only",
          "host_eligibility": ["arx_adapter", "full_autocad"],
          "policy": {"status_policy": "catalogued_not_runnable"},
          "handler": {"router_lane": "ARIADNE_NATIVE_JOB", "native_api": ""},
          "summary": "does a thing"}
    result = c34.classify_one(row, op)
    assert result["verdict"] == c34.VERDICT_EXPECTED
    assert result["registry_action"] == c34.ACTION_NONE
    assert "catalogued_not_runnable" in result["reason"]


def test_classify_one_core_console_caveat_is_expected_crash():
    row = _row("live.jig.point_probe")
    op = {"family": "live", "engine_tier": "native_arx_only",
          "host_eligibility": ["full_autocad"],
          "policy": {"status_policy": "implemented"},
          "handler": {"router_lane": "ARIADNE_NATIVE_JOB", "native_api": ""},
          "summary": "Router job drives a point probe; Core Console can only report support status."}
    result = c34.classify_one(row, op)
    assert result["verdict"] == c34.VERDICT_EXPECTED
    assert result["registry_action"] == c34.ACTION_NONE
    assert "already documented" in result["reason"]


def test_classify_one_implemented_with_no_caveat_is_anomalous_open():
    row = _row("live.overrule.enable")
    op = {"family": "live", "engine_tier": "native_arx_only",
          "host_eligibility": ["arx_adapter", "full_autocad"],
          "policy": {"status_policy": "implemented"},
          "handler": {"router_lane": "ARIADNE_NATIVE_JOB", "native_api": ""},
          "summary": "Router job installs the object overrule."}
    result = c34.classify_one(row, op)
    assert result["verdict"] == c34.VERDICT_ANOMALOUS
    assert result["registry_action"] == c34.ACTION_OPEN
    assert "owner triage" in result["reason"]


def test_classify_one_implemented_with_working_fixture_still_anomalous():
    # extend.customclass.create's real shape: implemented + a working
    # fixture on file -- still anomalous, since neither predicts a crash.
    row = _row("extend.customclass.create", fixture_available=True,
               fixture_evidence="test_native/job_create_args.json (existing working fixture)")
    op = {"family": "extend", "engine_tier": "native_arx_only",
          "host_eligibility": ["arx_adapter", "full_autocad"],
          "policy": {"status_policy": "implemented"},
          "handler": {"router_lane": "ARIADNE_NATIVE_JOB", "native_api": ""},
          "summary": "Create a custom class instance."}
    result = c34.classify_one(row, op)
    assert result["verdict"] == c34.VERDICT_ANOMALOUS
    assert result["registry_action"] == c34.ACTION_OPEN
    assert result["evidence"]["fixture_available"] is True


@pytest.mark.parametrize("op_id,family,expected_bucket", [
    ("extend.property.units", "com_activex", "com_activex"),
    ("live.overrule.enable", "live", "live"),
    ("extend.customobject.create", "extend", "custom-class"),
    ("extend.customentity.define", "custom_objects_protocols", "custom-class"),
    ("define.constraint.autoConstrain", "constraints_associativity", "misc"),
])
def test_crash_bucket_matches_manual_triage_grouping(op_id, family, expected_bucket):
    assert c34.crash_bucket(op_id, family) == expected_bucket


# --------------------------------------------------------------------------- #
# build_report -- synthetic matrix+registry files (tmp_path), full pipeline
# --------------------------------------------------------------------------- #

def test_build_report_flags_missing_registry_entry_as_unjoined(tmp_path):
    matrix_path = tmp_path / "matrix.jsonl"
    matrix_path.write_text(
        json.dumps({"op_id": "ghost.op", "class": "CRASH", "fixture_available": False}) + "\n",
        encoding="utf-8")
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps({"operations": []}), encoding="utf-8")

    report = c34.build_report(str(matrix_path), str(registry_path))
    assert report["crash_total"] == 1
    assert report["joined_count"] == 0
    assert report["unjoined_op_ids"] == ["ghost.op"]


def test_build_report_ignores_non_crash_rows(tmp_path):
    matrix_path = tmp_path / "matrix.jsonl"
    rows = [
        {"op_id": "a", "class": "RUNNABLE", "fixture_available": True},
        {"op_id": "b", "class": "CRASH", "fixture_available": False,
         "empty_arg_probe": {"reason": "x"}},
    ]
    matrix_path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps({"operations": [
        {"id": "b", "family": "misc", "policy": {"status_policy": "catalogued_not_runnable"},
         "handler": {}},
    ]}), encoding="utf-8")

    report = c34.build_report(str(matrix_path), str(registry_path))
    assert report["crash_total"] == 1
    assert report["joined_count"] == 1
    assert report["rows"][0]["op_id"] == "b"


def test_main_writes_json_and_md_and_exit_code(tmp_path):
    matrix_path = tmp_path / "matrix.jsonl"
    matrix_path.write_text(json.dumps({
        "op_id": "x", "class": "CRASH", "fixture_available": False,
        "empty_arg_probe": {"reason": "native job produced no parseable result JSON"},
    }), encoding="utf-8")
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps({"operations": [
        {"id": "x", "family": "misc", "policy": {"status_policy": "catalogued_not_runnable"},
         "handler": {}},
    ]}), encoding="utf-8")
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"

    rc = c34.main(["--matrix", str(matrix_path), "--registry", str(registry_path),
                   "--out-json", str(out_json), "--out-md", str(out_md)])
    assert rc == 0
    written = json.loads(out_json.read_text(encoding="utf-8"))
    assert written["joined_count"] == 1
    assert "CRASH-34" in out_md.read_text(encoding="utf-8")


def test_main_nonzero_exit_when_unjoined(tmp_path):
    matrix_path = tmp_path / "matrix.jsonl"
    matrix_path.write_text(json.dumps({"op_id": "ghost", "class": "CRASH",
                                       "fixture_available": False}), encoding="utf-8")
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps({"operations": []}), encoding="utf-8")
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"

    rc = c34.main(["--matrix", str(matrix_path), "--registry", str(registry_path),
                   "--out-json", str(out_json), "--out-md", str(out_md)])
    assert rc == 2


# --------------------------------------------------------------------------- #
# Real-artifact checks (read-only -- never writes measure/ or config/):
# join completeness, verdict enum validity, report schema, bucket totals.
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(not (os.path.isfile(_REAL_MATRIX) and os.path.isfile(_REAL_REGISTRY)),
                    reason="real sweep artifacts not present in this checkout")
class TestRealCrash34Sweep:
    def test_all_34_crash_rows_join_to_a_registry_record(self):
        report = c34.build_report(_REAL_MATRIX, _REAL_REGISTRY)
        assert report["crash_total"] == 34
        assert report["joined_count"] == 34
        assert report["unjoined_op_ids"] == []

    def test_every_row_has_a_valid_verdict_and_action(self):
        report = c34.build_report(_REAL_MATRIX, _REAL_REGISTRY)
        for row in report["rows"]:
            assert row["verdict"] in c34.VALID_VERDICTS
            assert row["registry_action"] in c34.VALID_ACTIONS

    def test_bucket_counts_match_manual_triage_16_5_6_7(self):
        report = c34.build_report(_REAL_MATRIX, _REAL_REGISTRY)
        assert report["bucket_counts"] == {
            "com_activex": 16, "live": 5, "custom-class": 6, "misc": 7,
        }

    def test_report_json_schema_has_required_top_level_keys(self):
        report = c34.build_report(_REAL_MATRIX, _REAL_REGISTRY)
        for key in ("schema", "crash_total", "joined_count", "unjoined_op_ids",
                    "verdict_counts", "bucket_counts", "registry_action_counts", "rows"):
            assert key in report
        for row in report["rows"]:
            for key in ("op_id", "bucket", "verdict", "registry_action", "evidence", "reason"):
                assert key in row
