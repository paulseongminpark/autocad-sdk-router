#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for tools/batch_equivalence_check.py."""
from __future__ import annotations

import importlib
import json
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "tools"))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

bec = importlib.import_module("batch_equivalence_check")


def _deep_merge(base, override):
    if not isinstance(override, dict):
        return override
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _base_summary(sha="a" * 64):
    return {
        "status": "ok",
        "regen": {"op_count": 3},
        "staged": {
            "original_path": "D:/drawings/source.dwg",
            "original_sha256": sha,
        },
    }


def _base_verdict():
    return {
        "rows": [
            {
                "dxf_name": "CIRCLE",
                "regen_attempted_count": 1,
                "diff0_count": 1,
                "modified_count": 0,
                "removed_count": 0,
                "added_count": 0,
            },
            {
                "dxf_name": "LINE",
                "regen_attempted_count": 2,
                "diff0_count": 2,
                "modified_count": 0,
                "removed_count": 0,
                "added_count": 0,
                "deferred_count": 0,
            },
        ],
        "totals": {
            "regen_attempted_count": 3,
            "diff0_count": 3,
            "modified_count": 0,
            "removed_count": 0,
            "added_count": 0,
            "deferred_count": 0,
        },
    }


def _base_diff():
    return {
        "summary": {
            "by_type": {
                "CIRCLE": {"added": 0, "removed": 0, "modified": 0},
                "LINE": {"added": 0, "removed": 0, "modified": 0},
            }
        }
    }


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_run(run_dir, *, summary=None, verdict=None, diff=None, deferred=None, omit=()):
    run_dir.mkdir(parents=True, exist_ok=True)
    if "summary.json" not in omit:
        _write_json(run_dir / "summary.json", _base_summary() if summary is None else summary)
    if "verdict.json" not in omit:
        _write_json(run_dir / "verdict.json", _base_verdict() if verdict is None else verdict)
    if "geometry_diff.json" not in omit:
        _write_json(run_dir / "geometry_diff.json", _base_diff() if diff is None else diff)
    if deferred is not None and "deferred.json" not in omit:
        _write_json(run_dir / "deferred.json", deferred)


def test_identical_runs_return_exit_zero(tmp_path):
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    _write_run(run_a)
    _write_run(run_b)

    result = bec.check_equivalence(str(run_a), str(run_b))

    assert result["equivalent"] is True
    assert result["mismatches"] == []
    assert result["exit_code"] == 0
    assert bec.main([str(run_a), str(run_b)]) == 0


def test_verdict_count_drift_reports_mismatch(tmp_path):
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    _write_run(run_a)
    drifted = _deep_merge(
        _base_verdict(),
        {
            "rows": [
                {
                    "dxf_name": "CIRCLE",
                    "regen_attempted_count": 1,
                    "diff0_count": 1,
                    "modified_count": 0,
                    "removed_count": 0,
                    "added_count": 0,
                },
                {
                    "dxf_name": "LINE",
                    "regen_attempted_count": 2,
                    "diff0_count": 1,
                    "modified_count": 1,
                    "removed_count": 0,
                    "added_count": 0,
                    "deferred_count": 0,
                },
            ],
            "totals": {
                "diff0_count": 2,
                "modified_count": 1,
            },
        },
    )
    _write_run(run_b, verdict=drifted)

    result = bec.check_equivalence(str(run_a), str(run_b))

    assert result["equivalent"] is False
    assert result["exit_code"] == 2
    assert any(
        mismatch["path"] == "verdict.json" and mismatch["field"] == "rows[LINE].diff0_count"
        for mismatch in result["mismatches"]
    )


def test_deferred_multiset_ignores_handles_and_indices(tmp_path):
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    deferred_a = [
        {"index": 1, "handle": "AA", "kind": "block_reference", "reason": "missing def"},
        {"index": 2, "handle": "AB", "kind": "block_reference", "reason": "missing def"},
        {"index": 3, "handle": "AC", "kind": "line", "reason": "unsupported"},
    ]
    deferred_b = [
        {"index": 9, "handle": "FF", "kind": "line", "reason": "unsupported"},
        {"index": 4, "handle": "00", "kind": "block_reference", "reason": "missing def"},
        {"index": 5, "handle": "01", "kind": "block_reference", "reason": "missing def"},
    ]
    _write_run(run_a, deferred=deferred_a)
    _write_run(run_b, deferred=deferred_b)

    result = bec.check_equivalence(str(run_a), str(run_b))

    assert result["equivalent"] is True
    assert result["exit_code"] == 0
    assert not any(m["path"] == "deferred.json" for m in result["mismatches"])


def test_missing_verdict_json_returns_code_three(tmp_path, capsys):
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    _write_run(run_a)
    _write_run(run_b, omit=("verdict.json",))

    exit_code = bec.main([str(run_a), str(run_b)])
    captured = capsys.readouterr()

    assert exit_code == 3
    assert "verdict.json" in captured.out
    assert "MISSING_ARTIFACT" in captured.out


def test_different_original_sha_reports_different_source(tmp_path):
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    _write_run(run_a, summary=_base_summary("a" * 64))
    _write_run(run_b, summary=_base_summary("b" * 64))

    result = bec.check_equivalence(str(run_a), str(run_b))

    assert result["equivalent"] is False
    assert result["exit_code"] == 2
    assert any(
        mismatch["path"] == "summary.json"
        and mismatch["field"] == "staged.original_sha256"
        and mismatch.get("code") == "DIFFERENT_SOURCE"
        for mismatch in result["mismatches"]
    )


def test_out_json_is_written_with_schema_id(tmp_path):
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    out_json = tmp_path / "report.json"
    _write_run(run_a)
    _write_run(run_b)

    exit_code = bec.main([str(run_a), str(run_b), "--out-json", str(out_json)])

    assert exit_code == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["schema"] == "ariadne.batch_equivalence.v1"
    assert payload["equivalent"] is True
