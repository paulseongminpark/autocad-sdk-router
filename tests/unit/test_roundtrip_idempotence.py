#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).resolve().parent
_TOOLS_DIR = (_THIS_DIR.parent.parent / "tools").resolve()
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

rti = importlib.import_module("roundtrip_idempotence")


def _line_entity(handle: str, start, end, layer: str = "0") -> dict:
    return {
        "handle": handle,
        "class": "AcDbLine",
        "dxf_name": "LINE",
        "owner_handle": "1F",
        "space": "model",
        "layer": layer,
        "bbox": [start[0], start[1], start[2], end[0], end[1], end[2]],
        "geometry": {"kind": "line", "start": list(start), "end": list(end)},
        "source": {"extractor": "test", "decoded": True},
    }


def _write_ir(path: Path, entities: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema": "ariadne.dwg_graph_ir.v1",
        "entities": entities,
        "diagnostics": {"entity_count": len(entities)},
    }, indent=2), encoding="utf-8")


def _write_gen1_artifacts(run_dir: Path) -> None:
    (run_dir / "regen").mkdir(parents=True, exist_ok=True)
    (run_dir / "regen" / "staged_output.dwg").write_bytes(b"dwg")
    _write_ir(run_dir / "regen" / "post" / "dwg_graph_ir.json", [])


def test_plan_only_writes_exact_command(tmp_path: Path):
    gen1 = tmp_path / "gen1"
    out_dir = tmp_path / "gen2"
    _write_gen1_artifacts(gen1)

    exit_code = rti.main([
        "--gen1-run-dir", str(gen1),
        "--out-dir", str(out_dir),
        "--plan-only",
        "--batch-size", "17",
        "--python", "py-custom",
    ])

    assert exit_code == 0
    plan = json.loads((out_dir / "idempotence_plan.json").read_text(encoding="utf-8"))
    assert plan["schema"] == "ariadne.roundtrip_idempotence_plan.v1"
    assert plan["gen1_run_dir"] == str(gen1.resolve())
    assert plan["gen2_cmd"] == [
        "py-custom",
        "tools/full_roundtrip_capstone.py",
        "--dwg", str((gen1 / "regen" / "staged_output.dwg").resolve()),
        "--seed", "tests/fixtures/blank_seed.dwg",
        "--out-dir", str(out_dir),
        "--max-def-entities-per-block", "25000",
        "--with-records",
        "--skip-identity",
        "--batch-size", "17",
    ]


def test_missing_gen1_artifacts_returns_3(tmp_path: Path):
    exit_code = rti.main([
        "--gen1-run-dir", str(tmp_path / "missing"),
        "--out-dir", str(tmp_path / "out"),
        "--plan-only",
    ])
    assert exit_code == 3


def test_build_idempotence_report_detects_fixed_point(tmp_path: Path):
    gen1_ir = tmp_path / "gen1.json"
    gen2_ir = tmp_path / "gen2.json"
    _write_ir(gen1_ir, [_line_entity("AAA", (0, 0, 0), (10, 5, 0))])
    _write_ir(gen2_ir, [_line_entity("ZZZ", (0, 0, 0), (10, 5, 0))])

    report = rti.build_idempotence_report(str(gen1_ir), str(gen2_ir))

    assert report["schema"] == "ariadne.roundtrip_idempotence.v1"
    assert report["entities"] == {
        "diff0": True,
        "removed": 0,
        "added": 0,
        "modified": 0,
        "total": 0,
    }
    # blockdef_diff is an optional sibling: absent -> 'unavailable'; present (it
    # is now a repo tool) -> a real ariadne.blockdef_diff.v1 result. Both are
    # fixed-point-compatible here (no block definitions in either IR).
    interiors = report["interiors"]
    if interiors != "unavailable":
        assert interiors["schema"] == "ariadne.blockdef_diff.v1"
        assert interiors["totals"]["a_entity_total"] == 0
    assert report["fixed_point"] is True


def test_build_idempotence_report_detects_drift(tmp_path: Path):
    gen1_ir = tmp_path / "gen1.json"
    gen2_ir = tmp_path / "gen2.json"
    _write_ir(gen1_ir, [_line_entity("AAA", (0, 0, 0), (10, 5, 0))])
    _write_ir(gen2_ir, [_line_entity("ZZZ", (0, 0, 0), (10, 5.5, 0))])

    report = rti.build_idempotence_report(str(gen1_ir), str(gen2_ir))

    assert report["entities"]["diff0"] is False
    assert report["entities"]["modified"] == 1
    assert report["entities"]["total"] == 1
    assert report["fixed_point"] is False


def test_blockdef_diff_import_failure_is_tolerated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    gen1_ir = tmp_path / "gen1.json"
    gen2_ir = tmp_path / "gen2.json"
    _write_ir(gen1_ir, [_line_entity("AAA", (0, 0, 0), (10, 5, 0))])
    _write_ir(gen2_ir, [_line_entity("ZZZ", (0, 0, 0), (10, 5, 0))])

    real_import_module = rti.importlib.import_module

    def _boom(name: str):
        if name == "blockdef_diff":
            raise ImportError("missing on purpose")
        return real_import_module(name)

    monkeypatch.setattr(rti.importlib, "import_module", _boom)
    report = rti.build_idempotence_report(str(gen1_ir), str(gen2_ir))
    assert report["interiors"] == "unavailable"
    assert report["fixed_point"] is True
