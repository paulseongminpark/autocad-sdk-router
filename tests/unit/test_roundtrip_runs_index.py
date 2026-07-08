#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for tools/roundtrip_runs_index.py."""
from __future__ import annotations

import importlib
import json
import os
import sys

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "tools"))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

rri = importlib.import_module("roundtrip_runs_index")

FULL_SHA256 = "14eb65eb292d8a07f38ab5662dcafe9761c6185bc5ff0c8a9a008be15b598961"
FULL_SHA16 = FULL_SHA256[:16]


def _write_full_run(run_dir, *, staged_at="2026-07-08T09:00:00+00:00"):
    run_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "staged": {
            "original_path": "D:/x/1.dwg",
            "original_sha256": FULL_SHA256,
            "staged_at": staged_at,
        },
        "status": "blocked",
        "regen": {
            "op_count": 17,
            "apply_status": "ok",
        },
    }
    verdict = {
        "totals": {
            "regen_attempted_count": 16,
            "diff0_count": 14,
            "removed_count": 2,
            "modified_count": 0,
            "added_count": 0,
        }
    }
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (run_dir / "verdict.json").write_text(json.dumps(verdict), encoding="utf-8")


def _write_corrupt_run(run_dir):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_bytes(b'{"status": "broken", not valid json')


@pytest.fixture
def fixture_runs_root(tmp_path):
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    _write_full_run(runs_root / "e2e_full_run")
    _write_corrupt_run(runs_root / "e2e_corrupt_run")
    return runs_root


def test_build_index_rows_sha16_sort_and_parse_error(fixture_runs_root):
    index = rri.build_index(str(fixture_runs_root))

    assert index["schema"] == "ariadne.roundtrip_runs_index.v1"
    assert index["generated_from"] == os.path.abspath(str(fixture_runs_root))
    assert len(index["runs"]) == 2

    full = index["runs"][0]
    corrupt = index["runs"][1]

    assert full["run_dir"] == "e2e_full_run"
    assert full["source_dwg"] == "D:/x/1.dwg"
    assert full["original_sha256"] == FULL_SHA256
    assert full["status"] == "blocked"
    assert full["regen"] == {"op_count": 17, "apply_status": "ok"}
    assert full["verdict_totals"] == {
        "regen_attempted_count": 16,
        "diff0_count": 14,
        "removed_count": 2,
        "modified_count": 0,
        "added_count": 0,
    }
    assert full["staged_at"] == "2026-07-08T09:00:00+00:00"
    assert full.get("parse_error") is None

    assert corrupt["run_dir"] == "e2e_corrupt_run"
    assert corrupt.get("parse_error")
    assert corrupt.get("staged_at") is None


def test_render_markdown_contains_both_runs_and_formatted_columns(fixture_runs_root):
    index = rri.build_index(str(fixture_runs_root))
    md = rri.render_markdown(index, str(fixture_runs_root))

    assert "| Run | DWG | sha16 | status | ops | diff0/att | timestamp |" in md
    assert "e2e_full_run" in md
    assert "e2e_corrupt_run" in md
    assert FULL_SHA16 in md
    assert "D:/x/1.dwg" in md
    assert "blocked" in md
    assert "17/ok" in md
    assert "14/16" in md
    assert "2026-07-08T09:00:00+00:00" in md


def test_sort_order_newest_first_missing_staged_at_last(tmp_path):
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    _write_full_run(runs_root / "e2e_older", staged_at="2026-07-08T08:00:00+00:00")
    _write_full_run(runs_root / "e2e_newer", staged_at="2026-07-08T10:00:00+00:00")
    _write_corrupt_run(runs_root / "e2e_corrupt_run")

    index = rri.build_index(str(runs_root))
    names = [row["run_dir"] for row in index["runs"]]
    assert names == ["e2e_newer", "e2e_older", "e2e_corrupt_run"]


def test_pattern_filter_excludes_non_matching_dirs(tmp_path):
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    _write_full_run(runs_root / "e2e_included")
    _write_full_run(runs_root / "other_run")

    index = rri.build_index(str(runs_root), patterns=["e2e_*"])
    assert [row["run_dir"] for row in index["runs"]] == ["e2e_included"]


def test_main_writes_json_and_markdown_outputs(fixture_runs_root, tmp_path):
    out_json = tmp_path / "out" / "index.json"
    out_md = tmp_path / "out" / "index.md"

    rc = rri.main([
        "--runs-root", str(fixture_runs_root),
        "--out-json", str(out_json),
        "--out-md", str(out_md),
    ])
    assert rc == 0
    assert out_json.is_file()
    assert out_md.is_file()

    written = json.loads(out_json.read_text(encoding="utf-8"))
    assert written["schema"] == "ariadne.roundtrip_runs_index.v1"
    assert len(written["runs"]) == 2

    md = out_md.read_text(encoding="utf-8")
    assert "e2e_full_run" in md
    assert "e2e_corrupt_run" in md
