#!/usr/bin/env python3
"""Unit tests for cross_verify.py's corpus-scale batch mode.

WHY: cross_verify_batch must isolate per-file failures (a missing IR
artifact or a crashing cross_verify_dwg call must not abort the rest of the
manifest) and its verdicts.jsonl + summary counters are the only evidence a
166-DWG-scale run leaves behind, so their arithmetic must be pinned. These
tests monkeypatch cross_verify_dwg itself -- no LibreDWG binary or real DWG
input is required.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "tools"))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import cross_verify as cv


def _write_manifest(tmp_path, rows):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(rows), encoding="utf-8")
    return str(manifest_path)


def _write_ir_artifact(ir_dir, ordinal):
    case_dir = ir_dir / f"{ordinal:04d}"
    case_dir.mkdir(parents=True, exist_ok=True)
    ir_path = case_dir / "dwg_graph_ir.json"
    ir_path.write_text("{}", encoding="utf-8")
    return str(ir_path)


def _read_jsonl(path):
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def test_ir_artifact_path_uses_zero_padded_ordinal_convention(tmp_path):
    assert cv._ir_artifact_path(str(tmp_path), 0) == os.path.join(str(tmp_path), "0000", "dwg_graph_ir.json")
    assert cv._ir_artifact_path(str(tmp_path), 12) == os.path.join(str(tmp_path), "0012", "dwg_graph_ir.json")


def test_load_batch_manifest_assigns_zero_based_ordinals(tmp_path):
    manifest_path = _write_manifest(tmp_path, [{"path": "a.dwg", "sha256": "aa"}, {"path": "b.dwg"}])

    rows = cv._load_batch_manifest(manifest_path)

    assert [row["ordinal"] for row in rows] == [0, 1]
    assert rows[0]["path"] == "a.dwg" and rows[0]["sha256"] == "aa"
    assert rows[1]["path"] == "b.dwg" and rows[1]["sha256"] is None


def test_load_batch_manifest_rejects_non_list_payload(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"files": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="must be a JSON list"):
        cv._load_batch_manifest(str(manifest_path))


def test_load_batch_manifest_rejects_row_without_path(tmp_path):
    manifest_path = _write_manifest(tmp_path, [{"sha256": "aa"}])

    with pytest.raises(ValueError, match="'path' field"):
        cv._load_batch_manifest(manifest_path)


def test_cross_verify_batch_covers_agree_disagree_skip_and_error_rows(tmp_path, monkeypatch):
    manifest_rows = [
        {"path": "agree.dwg"},
        {"path": "disagree.dwg"},
        {"path": "missing_ir.dwg"},
        {"path": "boom.dwg"},
    ]
    manifest_path = _write_manifest(tmp_path, manifest_rows)

    ir_dir = tmp_path / "ir"
    _write_ir_artifact(ir_dir, 0)
    _write_ir_artifact(ir_dir, 1)
    # ordinal 2 (missing_ir.dwg) intentionally has no IR artifact.
    _write_ir_artifact(ir_dir, 3)

    def fake_cross_verify_dwg(dwg_path, *, ir_path=None, out_dir=None, libredwg_bin=None):
        assert ir_path is not None and os.path.isfile(ir_path)
        if dwg_path == "agree.dwg":
            return {"status": "ok", "agree": True, "deltas": [], "unmapped": []}
        if dwg_path == "disagree.dwg":
            return {
                "status": "mismatch",
                "agree": False,
                "deltas": [{"field": "entity_total", "libredwg": 4, "ir": 3}],
                "unmapped": [{"entity": "ELLIPSE", "subclass": None, "count": 1}],
            }
        if dwg_path == "boom.dwg":
            raise RuntimeError("sidecar exploded")
        raise AssertionError(f"unexpected dwg_path {dwg_path}")

    monkeypatch.setattr(cv, "cross_verify_dwg", fake_cross_verify_dwg)

    out_dir = tmp_path / "out"
    summary = cv.cross_verify_batch(manifest_path, str(out_dir), ir_dir=str(ir_dir))

    assert summary["files"] == 4
    assert summary["agree"] == 1
    assert summary["disagree"] == 1
    assert summary["skipped"] == 1
    assert summary["errors"] == 1
    assert summary["verified"] == summary["agree"] + summary["disagree"]
    assert summary["files"] == summary["verified"] + summary["skipped"] + summary["errors"]

    rows = _read_jsonl(summary["verdicts_path"])
    assert [row["source_path"] for row in rows] == [
        "agree.dwg",
        "disagree.dwg",
        "missing_ir.dwg",
        "boom.dwg",
    ]

    agree_row, disagree_row, skipped_row, error_row = rows

    assert agree_row["status"] == "ok"
    assert agree_row["agree"] is True
    assert agree_row["error_class"] is None

    assert disagree_row["status"] == "mismatch"
    assert disagree_row["agree"] is False
    assert disagree_row["error_class"] is None
    assert disagree_row["deltas"] == [{"field": "entity_total", "libredwg": 4, "ir": 3}]
    assert disagree_row["unmapped"] == [{"entity": "ELLIPSE", "subclass": None, "count": 1}]

    assert skipped_row["status"] == "skipped"
    assert skipped_row["agree"] is None
    assert skipped_row["error_class"] == "ir_missing"

    assert error_row["status"] == "error"
    assert error_row["agree"] is None
    assert error_row["error_class"] == "RuntimeError"
    assert error_row["reason"] == "sidecar exploded"


def test_cross_verify_batch_skips_every_row_when_ir_dir_omitted(tmp_path, monkeypatch):
    manifest_path = _write_manifest(tmp_path, [{"path": "a.dwg"}, {"path": "b.dwg"}])

    def fail_if_called(*args, **kwargs):
        raise AssertionError("cross_verify_dwg must not be called when no IR artifact resolves")

    monkeypatch.setattr(cv, "cross_verify_dwg", fail_if_called)

    out_dir = tmp_path / "out"
    summary = cv.cross_verify_batch(manifest_path, str(out_dir))

    assert summary == {
        "files": 2,
        "verified": 0,
        "agree": 0,
        "disagree": 0,
        "skipped": 2,
        "errors": 0,
        "verdicts_path": str(out_dir / "verdicts.jsonl"),
    }
    rows = _read_jsonl(summary["verdicts_path"])
    assert all(row["status"] == "skipped" and row["error_class"] == "ir_missing" for row in rows)


def test_cross_verify_batch_treats_unexpected_verdict_status_as_error(tmp_path, monkeypatch):
    manifest_path = _write_manifest(tmp_path, [{"path": "weird.dwg"}])
    ir_dir = tmp_path / "ir"
    _write_ir_artifact(ir_dir, 0)

    def fake_cross_verify_dwg(dwg_path, *, ir_path=None, out_dir=None, libredwg_bin=None):
        return {"status": "blocked", "agree": False, "reason": "sidecar missing binary"}

    monkeypatch.setattr(cv, "cross_verify_dwg", fake_cross_verify_dwg)

    out_dir = tmp_path / "out"
    summary = cv.cross_verify_batch(manifest_path, str(out_dir), ir_dir=str(ir_dir))

    assert summary["files"] == 1
    assert summary["verified"] == 0
    assert summary["errors"] == 1

    (row,) = _read_jsonl(summary["verdicts_path"])
    assert row["status"] == "blocked"
    assert row["agree"] is None
    assert row["error_class"] == "blocked"
    assert row["reason"] == "sidecar missing binary"
