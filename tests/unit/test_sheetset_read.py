#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_TOOLS = os.path.join(_REPO, "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

import sheetset_read


def test_build_envelope_ok_shape():
    env = sheetset_read.build_envelope(
        status="ok",
        dst_path="C:/sample.dst",
        summary={"name": "Demo"},
        sheets=[{"number": "A1", "title": "Plan"}],
        subsets=[{"name": "Subset A"}],
        custom_properties={"Discipline": "Arch"},
        probe={"backend": {"status": "ok"}},
        blockers=[],
    )
    assert env["schema"] == "ariadne.sheetset.read.v1"
    assert env["status"] == "ok"
    assert env["dst_path"] == "C:/sample.dst"
    assert env["summary"]["name"] == "Demo"
    assert env["sheets"][0]["number"] == "A1"
    assert env["subsets"][0]["name"] == "Subset A"
    assert env["custom_properties"]["Discipline"] == "Arch"
    assert env["probe"]["backend"]["status"] == "ok"


def test_read_sheetset_reports_unavailable_without_registry(monkeypatch):
    monkeypatch.setattr(sheetset_read, "load_win32com_state", lambda: {"available": False, "detail": "missing"})
    monkeypatch.setattr(sheetset_read, "scan_registered_sheetset_progids", lambda: [])
    monkeypatch.setattr(sheetset_read, "find_autocad_dir", lambda: None)
    monkeypatch.setattr(sheetset_read, "find_sample_dst_files", lambda root=None: [])

    result = sheetset_read.read_sheetset()

    assert result["status"] == "unavailable"
    assert result["summary"] == {}
    assert result["sheets"] == []
    assert result["subsets"] == []
    assert result["probe"]["registry"]["progids"] == [sheetset_read.DEFAULT_VERSIONED_PROGID]
    assert result["blockers"]


def test_read_sheetset_reports_blocked_backend_error(monkeypatch):
    with tempfile.TemporaryDirectory(dir=_REPO) as tmpdir:
        sample = os.path.join(tmpdir, "sample.dst")
        with open(sample, "w", encoding="utf-8") as fh:
            fh.write("")

        monkeypatch.setattr(sheetset_read, "load_win32com_state", lambda: {"available": True, "detail": "ok"})
        monkeypatch.setattr(sheetset_read, "scan_registered_sheetset_progids", lambda: ["AcSmComponents.AcSmSheetSetMgr.26"])
        monkeypatch.setattr(sheetset_read, "find_autocad_dir", lambda: "C:/Program Files/Autodesk/AutoCAD 2027")
        monkeypatch.setattr(sheetset_read, "probe_win32com_dispatch", lambda progid: {"ok": False, "error": "non-dispatch"})
        monkeypatch.setattr(
            sheetset_read,
            "attempt_powershell_read",
            lambda dst_path, autocad_dir: {
                "status": "blocked",
                "error": "AXDBLib missing",
                "stderr": "",
                "stdout": "",
            },
        )

        result = sheetset_read.read_sheetset(sample)

        assert result["status"] == "blocked"
        assert "AXDBLib missing" in json.dumps(result, ensure_ascii=False)
        assert result["dst_path"] == sample
        assert result["probe"]["registry"]["progids"] == ["AcSmComponents.AcSmSheetSetMgr.26"]


def test_main_writes_json_out(monkeypatch, capsys):
    with tempfile.TemporaryDirectory(dir=_REPO) as tmpdir:
        out_path = os.path.join(tmpdir, "out.json")
        monkeypatch.setattr(
            sheetset_read,
            "read_sheetset",
            lambda dst_path=None: sheetset_read.build_envelope(
                status="ok",
                dst_path=dst_path or "x.dst",
                summary={"name": "Demo"},
                sheets=[],
                subsets=[],
                custom_properties={},
                probe={},
                blockers=[],
            ),
        )

        rc = sheetset_read.main(["--dst", "C:/demo.dst", "--json-out", out_path])
        captured = capsys.readouterr()

        assert rc == 0
        with open(out_path, "r", encoding="utf-8") as fh:
            assert json.load(fh)["status"] == "ok"
        assert json.loads(captured.out)["dst_path"] == "C:/demo.dst"


@pytest.mark.skipif(not sheetset_read.live_probe_available(), reason=sheetset_read.live_probe_skip_reason())
def test_live_measurement_reports_real_status():
    sample = sheetset_read.find_sample_dst_files()[0]
    result = sheetset_read.read_sheetset(sample)

    assert result["schema"] == "ariadne.sheetset.read.v1"
    assert result["dst_path"] == sample
    assert result["status"] in {"ok", "blocked"}
    assert result["probe"]["registry"]["progids"]
    if result["status"] == "ok":
        assert result["summary"]["name"]
    else:
        assert result["blockers"]
