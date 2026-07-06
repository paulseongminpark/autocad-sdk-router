#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "tools"))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import cross_engine_verify as cev


def _tmp_dwg(path: Path):
    path.write_bytes(b"cross-engine-verify-bytes")


def _tmp_autocad_ir(path: Path, entity_count=2):
    ir = {
        "schema": "ariadne.dwg_graph_ir.v1",
        "entities": [
            {"layer": "0"},
            {"layer": "A-WALL"},
        ][:entity_count],
        "symbol_tables": {"layers": [{"name": "0"}, {"name": "A-WALL"}]},
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ir, fh)


def _libredwg_payload(entity_count, layers):
    return json.dumps({"entities": [{}] * entity_count, "layers": list(layers)})


def test_match_reports_concordant(monkeypatch, tmp_path):
    dwg_path = tmp_path / "input.dwg"
    _tmp_dwg(dwg_path)
    ir_path = tmp_path / "dwg_graph_ir.json"
    _tmp_autocad_ir(ir_path)

    lib_dir = tmp_path / "libredwg"
    lib_dir.mkdir()
    (lib_dir / "dwgread.exe").write_text("", encoding="utf-8")

    calls = []

    def fake_run(cmd, capture_output=True, text=True, timeout=120, check=False):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout=_libredwg_payload(2, {"0", "A-WALL"}), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = cev.verify_cross_engine(str(dwg_path), autocad_ir_path=str(ir_path), libredwg_bin_dir=str(lib_dir))

    assert result["ok"] is True
    assert result["status"] == "ok"
    assert result["concordant"] is True
    assert set(result["autocad"]["layers"]) == {"0", "A-WALL"}
    assert result["libredwg"]["entities"] == 2
    assert set(result["libredwg"]["layers"]) == {"0", "A-WALL"}
    assert result["deltas"]["entity_count"] == 0
    assert result["deltas"]["layers_only_autocad"] == []
    assert result["deltas"]["layers_only_libredwg"] == []
    assert result["original_unchanged"] is True

    # Proof that the operation used a staged copy, not the original path.
    assert calls, "subprocess.run was not invoked"
    assert str(dwg_path) not in calls[0]


def test_mismatch_reports_deltas(monkeypatch, tmp_path):
    dwg_path = tmp_path / "input.dwg"
    _tmp_dwg(dwg_path)
    ir_path = tmp_path / "dwg_graph_ir.json"
    _tmp_autocad_ir(ir_path)

    lib_dir = tmp_path / "libredwg"
    lib_dir.mkdir()
    (lib_dir / "dwgread.exe").write_text("", encoding="utf-8")

    def fake_run(cmd, capture_output=True, text=True, timeout=120, check=False):
        return SimpleNamespace(returncode=0, stdout=_libredwg_payload(3, {"0", "B-ELEV"}), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = cev.verify_cross_engine(str(dwg_path), autocad_ir_path=str(ir_path), libredwg_bin_dir=str(lib_dir))

    assert result["ok"] is True
    assert result["status"] == "ok"
    assert result["concordant"] is False
    assert result["deltas"]["entity_count"] == 1
    assert set(result["deltas"]["layers_only_autocad"]) == {"A-WALL"}
    assert set(result["deltas"]["layers_only_libredwg"]) == {"B-ELEV"}


def test_missing_libredwg_bin_returns_not_available(monkeypatch, tmp_path):
    dwg_path = tmp_path / "input.dwg"
    _tmp_dwg(dwg_path)

    # An empty directory without dwgread.exe guarantees a deterministic miss.
    empty_bin = tmp_path / "empty_libredwg"
    empty_bin.mkdir()

    result = cev.verify_cross_engine(str(dwg_path), libredwg_bin_dir=str(empty_bin))

    assert result["ok"] is True
    assert result["status"] == "not_available"
    assert "dwgread binary not found" in result["reason"]
