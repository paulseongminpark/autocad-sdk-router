#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for transfer_report (no CAD, stdlib only)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import transfer_report as tr  # noqa: E402


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2), encoding="utf-8")


def _build_fixture_sweep(tmp_path: Path) -> Path:
    sweep_root = tmp_path / "sweep"
    alpha_dir = sweep_root / "00_alpha"
    beta_dir = sweep_root / "01_beta"
    alpha_dir.mkdir(parents=True)
    beta_dir.mkdir(parents=True)

    _write_json(
        alpha_dir / "summary.json",
        {
            "census_report": {
                "modelspace_entity_total": 100,
                "certified_total": 100,
                "out_of_class_total": 0,
                "by_bucket": [
                    {
                        "dxf_name": "LINE",
                        "kind": "line",
                        "count": 100,
                        "certified": True,
                        "label": "certified",
                    }
                ],
                "block_definitions_by_bucket": [],
            },
            "regen": {"op_count": 200, "apply_status": "ok", "gate": {"ok": True}},
            "status": "ok",
            "verdict": {"rows": []},
        },
    )
    _write_json(alpha_dir / "interior_diff.json", {"interior_diff0_fraction": 1.0})
    _write_json(
        alpha_dir / "verdict.json",
        {"schema": "opaque", "rows": []},
    )

    _write_json(
        beta_dir / "summary.json",
        {
            "census_report": {
                "modelspace_entity_total": 50,
                "certified_total": 40,
                "out_of_class_total": 10,
                "by_bucket": [
                    {
                        "dxf_name": "HATCH",
                        "kind": "hatch",
                        "count": 10,
                        "certified": False,
                        "label": "unsupported",
                    }
                ],
                "block_definitions_by_bucket": [],
            },
            "regen": {"op_count": 0, "apply_status": "blocked", "gate": {"ok": False}},
            "status": "blocked",
            "verdict": None,
        },
    )

    _write_json(
        sweep_root / "parallel_sweep_summary.json",
        {
            "schema": "ariadne.parallel_roundtrip_sweep.v1",
            "out_root": str(sweep_root),
            "workers": 2,
            "passthrough": [],
            "drawing_count": 2,
            "overall": "blocked",
            "results": [
                {
                    "drawing": str(tmp_path / "alpha.dwg"),
                    "out_dir": str(alpha_dir),
                    "status": "success",
                    "exit_code": 0,
                    "elapsed_s": 1.2,
                    "capstone_status": "ok",
                    "verdict_present": True,
                    "interior_diff0_fraction": 1.0,
                    "note": "",
                },
                {
                    "drawing": str(tmp_path / "beta.dwg"),
                    "out_dir": str(beta_dir),
                    "status": "blocked",
                    "exit_code": 2,
                    "elapsed_s": 0.4,
                    "capstone_status": "blocked",
                    "verdict_present": False,
                    "interior_diff0_fraction": None,
                    "note": "regen blocked",
                },
            ],
        },
    )
    return sweep_root


def test_transfer_report_rollup_and_honesty(tmp_path, capsys):
    sweep_root = _build_fixture_sweep(tmp_path)
    out_path = sweep_root / "transfer_report.json"

    report = tr.build_transfer_report(str(sweep_root), str(out_path))

    assert report["schema"] == tr.REPORT_SCHEMA
    assert report["rollup"]["succeeded"] == 1
    assert report["rollup"]["blocked"] == 1
    assert report["rollup"]["mean_interior_diff0_fraction"] == 1.0
    assert report["rollup"]["min_interior_diff0_fraction"] == 1.0
    assert report["honesty"]["drawings_without_verdict"] == ["01_beta"]

    assert out_path.is_file()
    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert loaded["rollup"]["succeeded"] == 1

    captured = capsys.readouterr()
    assert "00_alpha" in captured.out
    assert "01_beta" in captured.out
    assert "success" in captured.out
    assert "blocked" in captured.out


def test_transfer_report_cli_main(tmp_path):
    sweep_root = _build_fixture_sweep(tmp_path)
    rc = tr.main(["--sweep-root", str(sweep_root)])
    assert rc == 0
    assert os.path.isfile(os.path.join(str(sweep_root), "transfer_report.json"))
