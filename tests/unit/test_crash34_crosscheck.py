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
    # No resolution map passed (defaults to None) -- reproduces pre-Lane-I
    # behavior exactly, unaffected by the real registry's new Lane I text.
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


def test_classify_one_resolved_by_resolution_map_overrides_catalogued_not_runnable():
    # Lane I: a row the legacy heuristic would call "expected_crash" (stale
    # catalogued_not_runnable) must be re-verdicted resolved_by_router_fix
    # when the resolution map says Lane I proved it runs now.
    row = _row("fake.op.b")
    op = {"family": "misc_family", "engine_tier": "native_arx_only",
          "host_eligibility": ["arx_adapter", "full_autocad"],
          "policy": {"status_policy": "catalogued_not_runnable"},
          "handler": {"router_lane": "ARIADNE_NATIVE_JOB", "native_api": ""},
          "summary": "does a thing"}
    resolution = {
        "fake.op.b": {
            "op_id": "fake.op.b", "old_class": "CRASH", "new_class": "RUNNABLE",
            "resolved": True,
            "_manifest": {"fix_commit": "deadbee", "fix_file": "tools/autocad-router.ps1"},
        }
    }
    result = c34.classify_one(row, op, resolution)
    assert result["verdict"] == c34.VERDICT_RESOLVED
    assert result["registry_action"] == c34.ACTION_RESOLVED
    assert result["evidence"]["resolved_new_class"] == "RUNNABLE"
    assert result["evidence"]["resolved_fix_commit"] == "deadbee"


def test_classify_one_resolution_map_present_but_op_not_resolved_falls_through():
    # live.jig.point_probe's real shape: present in the resolution map (it
    # was part of the 34 re-probed) but resolved=False (still genuinely
    # attended-only) -- must fall through to the pre-existing Core Console
    # caveat heuristic unchanged, not silently marked resolved.
    row = _row("live.jig.point_probe")
    op = {"family": "live", "engine_tier": "native_arx_only",
          "host_eligibility": ["full_autocad"],
          "policy": {"status_policy": "implemented"},
          "handler": {"router_lane": "ARIADNE_NATIVE_JOB", "native_api": ""},
          "summary": "Router job drives a point probe; Core Console can only report support status."}
    resolution = {
        "live.jig.point_probe": {
            "op_id": "live.jig.point_probe", "old_class": "CRASH", "new_class": "CRASH",
            "resolved": False,
        }
    }
    result = c34.classify_one(row, op, resolution)
    assert result["verdict"] == c34.VERDICT_EXPECTED
    assert result["registry_action"] == c34.ACTION_NONE


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


def test_load_resolution_map_missing_file_returns_empty_dict(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    assert c34.load_resolution_map(str(missing)) == {}


def test_load_resolution_map_inlines_manifest_metadata_per_row(tmp_path):
    resolution_path = tmp_path / "resolution.json"
    resolution_path.write_text(json.dumps({
        "fix_commit": "abc1234",
        "fix_file": "tools/autocad-router.ps1",
        "rows": [
            {"op_id": "foo.bar", "old_class": "CRASH", "new_class": "RUNNABLE", "resolved": True},
        ],
    }), encoding="utf-8")
    result = c34.load_resolution_map(str(resolution_path))
    assert result["foo.bar"]["resolved"] is True
    assert result["foo.bar"]["_manifest"]["fix_commit"] == "abc1234"


# --------------------------------------------------------------------------- #
# Real-artifact checks (read-only -- never writes measure/ or config/):
# join completeness, verdict enum validity, report schema, bucket totals.
# --------------------------------------------------------------------------- #

_REAL_RESOLUTION = os.path.join(_ROUTER_HOME, "reports", "lane_i_router_fix_resolution.json")


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


@pytest.mark.skipif(not (os.path.isfile(_REAL_MATRIX) and os.path.isfile(_REAL_REGISTRY)
                          and os.path.isfile(_REAL_RESOLUTION)),
                    reason="Lane I resolution artifact not present in this checkout")
class TestRealCrash34SweepAfterLaneIFix:
    """Lane I fixed the router's live_edit dispatch bug (root-caused by Lane
    G) and live-re-probed all 34 CRASH ops against the fix. These assertions
    guard that measured result: 33 of the 34 rows must now read as
    resolved_by_router_fix (not the pre-fix expected_crash/anomalous_crash
    verdicts), and the one genuinely attended-only op must NOT be silently
    swept into "resolved" just because it happens to sit in the resolution
    file.
    """

    def test_verdict_counts_reflect_the_router_fix(self):
        report = c34.build_report(_REAL_MATRIX, _REAL_REGISTRY, _REAL_RESOLUTION)
        assert report["verdict_counts"] == {
            "resolved_by_router_fix": 33,
            "expected_crash": 1,
        }
        assert "anomalous_crash" not in report["verdict_counts"]

    def test_live_jig_point_probe_is_the_one_still_expected_crash(self):
        report = c34.build_report(_REAL_MATRIX, _REAL_REGISTRY, _REAL_RESOLUTION)
        still_crash = [r for r in report["rows"] if r["verdict"] == c34.VERDICT_EXPECTED]
        assert [r["op_id"] for r in still_crash] == ["live.jig.point_probe"]

    def test_resolved_rows_carry_the_fix_commit_in_evidence(self):
        report = c34.build_report(_REAL_MATRIX, _REAL_REGISTRY, _REAL_RESOLUTION)
        resolved = [r for r in report["rows"] if r["verdict"] == c34.VERDICT_RESOLVED]
        assert len(resolved) == 33
        for r in resolved:
            assert r["evidence"]["resolved_fix_commit"]
            assert r["evidence"]["resolved_new_class"] != "CRASH"
