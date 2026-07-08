#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for roundtrip_corpus_sweep (no CAD)."""
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

import roundtrip_corpus_sweep as rcs  # noqa: E402


def test_load_dwg_list_skips_comments_and_blank_lines(tmp_path):
    dwg_a = tmp_path / "alpha.dwg"
    dwg_b = tmp_path / "beta.dwg"
    dwg_a.write_bytes(b"a")
    dwg_b.write_bytes(b"b")
    list_path = tmp_path / "dwgs.txt"
    list_path.write_text(
        "\n".join(
            [
                "# header comment",
                f"  {dwg_a.resolve()}  ",
                "",
                f"{dwg_b.resolve()}",
                "# trailing",
            ]
        ),
        encoding="utf-8",
    )

    loaded = rcs.load_dwg_list(list_path)

    assert loaded == [str(dwg_a.resolve()), str(dwg_b.resolve())]


def test_build_sweep_plan_two_entries(tmp_path):
    dwg_a = tmp_path / "first.dwg"
    dwg_b = tmp_path / "second.dwg"
    dwg_a.write_bytes(b"a")
    dwg_b.write_bytes(b"b")
    out_root = tmp_path / "sweep_out"
    python_exe = sys.executable

    plan = rcs.build_sweep_plan([str(dwg_a.resolve()), str(dwg_b.resolve())], str(out_root), python_exe=python_exe)

    assert plan["schema"] == "ariadne.roundtrip_sweep_plan.v1"
    assert len(plan["entries"]) == 2

    first = plan["entries"][0]
    second = plan["entries"][1]
    assert first["dwg"] == str(dwg_a.resolve())
    assert second["dwg"] == str(dwg_b.resolve())
    assert first["out_dir"] == os.path.join(str(out_root.resolve()), "001_first")
    assert second["out_dir"] == os.path.join(str(out_root.resolve()), "002_second")

    assert first["cmd"] == [
        python_exe,
        str(rcs.CAPSTONE_SCRIPT),
        "--dwg",
        str(dwg_a.resolve()),
        "--out-dir",
        first["out_dir"],
        "--census-only",
        "--skip-identity",
    ]
    assert second["cmd"][2:4] == ["--dwg", str(dwg_b.resolve())]
    assert second["cmd"][-2:] == ["--census-only", "--skip-identity"]


def test_plan_only_writes_sweep_plan(tmp_path):
    dwg_a = tmp_path / "one.dwg"
    dwg_b = tmp_path / "two.dwg"
    dwg_a.write_bytes(b"a")
    dwg_b.write_bytes(b"b")
    list_path = tmp_path / "dwgs.txt"
    list_path.write_text(f"{dwg_a.resolve()}\n{dwg_b.resolve()}\n", encoding="utf-8")
    out_root = tmp_path / "out"

    rc = rcs.main(
        [
            "--dwg-list",
            str(list_path),
            "--out-root",
            str(out_root),
            "--plan-only",
            "--python",
            sys.executable,
        ]
    )
    assert rc == 0

    plan_path = out_root / "sweep_plan.json"
    assert plan_path.is_file()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["schema"] == "ariadne.roundtrip_sweep_plan.v1"
    assert len(plan["entries"]) == 2
    assert plan["entries"][0]["out_dir"].endswith("001_one")
    assert plan["entries"][1]["out_dir"].endswith("002_two")
    assert not (out_root / "corpus_census_summary.json").exists()


def test_aggregate_census_two_fixtures_and_missing(tmp_path):
    dwg_a = "C:/corpus/a.dwg"
    dwg_b = "C:/corpus/b.dwg"
    dwg_c = "C:/corpus/c.dwg"
    out_a = tmp_path / "001_a"
    out_b = tmp_path / "002_b"
    out_c = tmp_path / "003_c"
    out_a.mkdir()
    out_b.mkdir()
    out_c.mkdir()

    report_a = {
        "modelspace_entity_total": 100,
        "certified_total": 80,
        "out_of_class_total": 20,
        "by_bucket": [
            {"dxf_name": "LINE", "kind": "line", "count": 50, "certified": True},
            {"dxf_name": "TEXT", "kind": "text", "count": 30, "certified": True},
            {"dxf_name": "SPLINE", "kind": "spline", "count": 20, "certified": False},
        ],
    }
    report_b = {
        "modelspace_entity_total": 200,
        "certified_total": 200,
        "out_of_class_total": 0,
        "by_bucket": [
            {"dxf_name": "LINE", "kind": "line", "count": 150, "certified": True},
            {"dxf_name": "CIRCLE", "kind": "circle", "count": 50, "certified": True},
        ],
    }
    (out_a / "census_report.json").write_text(json.dumps(report_a), encoding="utf-8")
    (out_b / "census_report.json").write_text(json.dumps(report_b), encoding="utf-8")

    plan = {
        "schema": "ariadne.roundtrip_sweep_plan.v1",
        "entries": [
            {"dwg": dwg_a, "out_dir": str(out_a)},
            {"dwg": dwg_b, "out_dir": str(out_b)},
            {"dwg": dwg_c, "out_dir": str(out_c)},
        ],
    }
    (tmp_path / "sweep_plan.json").write_text(json.dumps(plan), encoding="utf-8")

    summary = rcs.aggregate_census(str(tmp_path))

    assert summary["schema"] == "ariadne.roundtrip_corpus_census.v1"
    assert summary["totals"] == {
        "drawings": 3,
        "census_ok": 2,
        "modelspace_entity_total": 300,
    }

    assert summary["per_dxf"]["LINE"] == {
        "total_count": 200,
        "drawings_present": 2,
        "certified": True,
    }
    assert summary["per_dxf"]["TEXT"] == {
        "total_count": 30,
        "drawings_present": 1,
        "certified": True,
    }
    assert summary["per_dxf"]["SPLINE"] == {
        "total_count": 20,
        "drawings_present": 1,
        "certified": False,
    }
    assert summary["per_dxf"]["CIRCLE"] == {
        "total_count": 50,
        "drawings_present": 1,
        "certified": True,
    }

    drawings_by_dwg = {row["dwg"]: row for row in summary["drawings"]}
    assert drawings_by_dwg[dwg_a]["ok"] is True
    assert drawings_by_dwg[dwg_a]["modelspace_entity_total"] == 100
    assert drawings_by_dwg[dwg_b]["ok"] is True
    assert drawings_by_dwg[dwg_c]["ok"] is False
    assert drawings_by_dwg[dwg_c]["modelspace_entity_total"] is None

    md = rcs.render_census_summary_md(summary)
    assert "| LINE | 200 | 2 | true |" in md
    assert "| TEXT | 30 | 1 | true |" in md
    assert "| SPLINE | 20 | 1 | false |" in md
    assert "| CIRCLE | 50 | 1 | true |" in md

    json_path, md_path = rcs.write_census_summary(str(tmp_path), summary)
    assert Path(json_path).is_file()
    assert Path(md_path).is_file()
    assert "LINE" in Path(md_path).read_text(encoding="utf-8")
