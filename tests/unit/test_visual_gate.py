#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_DIR = os.path.normpath(os.path.join(_THIS_DIR, "..", ".."))
_TOOLS_DIR = os.path.join(_REPO_DIR, "tools")
for _path in (_REPO_DIR, _TOOLS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import ir_builder
import visual_gate as vg


def _write_json(path: Path, obj) -> Path:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _post_with_added_line(pre, handle="2FF"):
    post = json.loads(json.dumps(pre))
    post["entities"].append(
        {
            "handle": handle,
            "class": "AcDbLine",
            "dxf_name": "LINE",
            "owner_handle": "1F",
            "space": "model",
            "layer": "ARIADNE_PROBE",
            "bbox": [0.0, 0.0, 0.0, 5.0, 5.0, 0.0],
            "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [5.0, 5.0, 0.0]},
            "source": {"extractor": "test", "decoded": True},
        }
    )
    post["diagnostics"]["entity_count"] = len(post["entities"])
    return post


def _diff_added(handle="2FF"):
    return {
        "schema": "ariadne.cad_diff.v1",
        "diff_id": f"test-added-{handle}",
        "changed_handles": [
            {"handle": handle, "change": "added", "dxf_name": "LINE", "layer": "ARIADNE_PROBE"}
        ],
        "summary": {"created_count": 1, "modified_count": 0, "deleted_count": 0},
    }


def test_same_file_baseline_sets_threshold_from_measurement():
    pre = ir_builder.make_fixture_ir()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        pre_path = _write_json(td_path / "pre.json", pre)
        baseline = vg.measure_same_file_baseline(str(pre_path), out_dir=str(td_path / "baseline"))
        gate = vg.visual_gate_from_ir_paths(
            str(pre_path),
            str(pre_path),
            diff_path=None,
            out_dir=str(td_path / "gate"),
        )

    assert baseline["status"] == "ok"
    assert baseline["baseline_ssim"] == pytest.approx(1.0, abs=1e-6)
    assert baseline["threshold"] == pytest.approx(1.0, abs=1e-6)
    assert gate["status"] == "ok"
    assert gate["pass"] is True
    assert gate["ssim"] == pytest.approx(1.0, abs=1e-6)
    assert gate["threshold"] == pytest.approx(1.0, abs=1e-6)


def test_visual_gate_fails_when_render_changes_below_threshold():
    pre = ir_builder.make_fixture_ir()
    post = _post_with_added_line(pre)
    diff = _diff_added()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        pre_path = _write_json(td_path / "pre.json", pre)
        post_path = _write_json(td_path / "post.json", post)
        diff_path = _write_json(td_path / "diff.json", diff)
        gate = vg.visual_gate_from_ir_paths(
            str(pre_path),
            str(post_path),
            diff_path=str(diff_path),
            out_dir=str(td_path / "gate"),
        )

    assert gate["status"] == "mismatch"
    assert gate["pass"] is False
    assert gate["ssim"] < gate["threshold"]


def test_svg_raster_artifacts_are_written():
    pre = ir_builder.make_fixture_ir()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        pre_path = _write_json(td_path / "pre.json", pre)
        gate = vg.visual_gate_from_ir_paths(
            str(pre_path),
            str(pre_path),
            diff_path=None,
            out_dir=str(td_path / "gate"),
        )
        assert Path(gate["before_png"]).is_file()
        assert Path(gate["after_png"]).is_file()
        assert Path(gate["visual_artifact"]).is_file()


@pytest.mark.skipif(
    not Path(r"D:\dev\.build\cados_plan\runs\t1_cert\pre_shared\dwg_graph_ir.json").exists(),
    reason="real ARX IR artifacts not present",
)
def test_visual_gate_live_real_ir_pair_records_real_numbers():
    pre_ir = Path(r"D:\dev\.build\cados_plan\runs\t1_cert\pre_shared\dwg_graph_ir.json")
    post_ir = Path(r"D:\dev\.build\cados_plan\runs\t1_cert\text\post\dwg_graph_ir.json")
    if not post_ir.exists():
        pytest.skip("real post-write IR artifact not present")

    with tempfile.TemporaryDirectory() as td:
        gate = vg.visual_gate_from_ir_paths(
            str(pre_ir),
            str(post_ir),
            diff_path=None,
            out_dir=td,
        )

    assert gate["baseline"]["status"] == "ok"
    assert gate["baseline"]["baseline_ssim"] == pytest.approx(1.0, abs=1e-6)
    assert gate["status"] in {"ok", "mismatch"}
    assert 0.0 <= gate["ssim"] <= 1.0
