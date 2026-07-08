#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_DIR = os.path.normpath(os.path.join(_THIS_DIR, "..", ".."))
_TOOLS_DIR = os.path.join(_REPO_DIR, "tools")
for _path in (_REPO_DIR, _TOOLS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import visual_gate as vg


def _make_line_ir(handle: str, start: tuple[float, float], end: tuple[float, float]) -> dict:
    min_x = min(start[0], end[0])
    min_y = min(start[1], end[1])
    max_x = max(start[0], end[0])
    max_y = max(start[1], end[1])
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "entities": [
            {
                "handle": handle,
                "class": "AcDbLine",
                "dxf_name": "LINE",
                "owner_handle": "1F",
                "space": "model",
                "layer": "TEST",
                "bbox": [min_x, min_y, 0.0, max_x, max_y, 0.0],
                "geometry": {
                    "kind": "line",
                    "start": [start[0], start[1], 0.0],
                    "end": [end[0], end[1], 0.0],
                },
                "source": {"extractor": "test", "decoded": True},
            }
        ],
        "diagnostics": {"entity_count": 1},
    }


def _make_deleted_diff(handle: str) -> dict:
    return {
        "schema": "ariadne.cad_diff.v1",
        "diff_id": f"deleted-{handle}",
        "changed_handles": [
            {"handle": handle, "change": "deleted", "dxf_name": "LINE", "layer": "TEST"}
        ],
        "summary": {"created_count": 0, "modified_count": 0, "deleted_count": 1},
    }


def _write_svg(path: Path, viewbox: str, transform: str) -> Path:
    path.write_text(
        "\n".join(
            [
                '<?xml version="1.0" encoding="UTF-8"?>',
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="1000" height="1000">',
                '  <rect x="0" y="0" width="10" height="10" fill="#ffffff"/>',
                f'  <g transform="{transform}">',
                '    <line x1="0" y1="0" x2="10" y2="10" stroke="#000000" stroke-width="1"/>',
                "  </g>",
                "</svg>",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_apply_common_viewbox_rewrites_both_svgs_to_union_frame(tmp_path: Path):
    before_svg = _write_svg(tmp_path / "before.svg", "0 0 10 10", "translate(0,10) scale(1,-1)")
    after_svg = _write_svg(tmp_path / "after.svg", "100 100 20 20", "translate(0,220) scale(1,-1)")

    common = vg._apply_common_viewbox((str(before_svg), str(after_svg)))

    assert common == pytest.approx((0.0, 0.0, 120.0, 120.0))
    for svg_path in (before_svg, after_svg):
        root = ET.parse(svg_path).getroot()
        assert vg._parse_viewbox(root.get("viewBox")) == pytest.approx(common)
        group = next(child for child in list(root) if child.tag.split("}")[-1] == "g")
        assert group.get("transform") == "translate(0,120) scale(1,-1)"


def test_measure_same_file_baseline_sets_reason_when_ssim_is_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        vg,
        "_render_visual_pair",
        lambda *args, **kwargs: {"before_png": "before.png", "after_png": "after.png", "artifact_path": "artifact.json"},
    )
    monkeypatch.setattr(vg.run_route, "compare_raster_images", lambda *args, **kwargs: {"status": "ok"})

    baseline = vg.measure_same_file_baseline("pre.json", out_dir=str(tmp_path / "baseline"))

    assert baseline["status"] == "blocked"
    assert isinstance(baseline["reason"], str)
    assert baseline["reason"] != ""


def test_visual_gate_sets_reason_when_compare_returns_no_ssim(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(vg, "measure_same_file_baseline", lambda *args, **kwargs: {"status": "ok", "threshold": 1.0})
    monkeypatch.setattr(
        vg,
        "_render_visual_pair",
        lambda *args, **kwargs: {
            "before_png": "before.png",
            "after_png": "after.png",
            "before_svg": "before.svg",
            "after_svg": "after.svg",
            "artifact_path": "artifact.json",
            "diff_path": None,
            "common_viewbox": (0.0, 0.0, 1.0, 1.0),
            "visual_diff_counts": None,
        },
    )
    monkeypatch.setattr(vg.run_route, "compare_raster_images", lambda *args, **kwargs: {"status": "ok"})

    result = vg.visual_gate_from_ir_paths("pre.json", "post.json", out_dir=str(tmp_path / "gate"))

    assert result["status"] == "blocked"
    assert result["pass"] is False
    assert isinstance(result["reason"], str)
    assert result["reason"] != ""


def test_same_content_still_passes(tmp_path: Path):
    pre = _make_line_ir("A1", (0.0, 0.0), (10.0, 10.0))

    result = vg.visual_gate_from_ir_docs(pre, pre, out_dir=str(tmp_path / "same"))

    assert result["status"] == "ok"
    assert result["pass"] is True
    assert result["ssim"] == pytest.approx(1.0, abs=1e-6)
    assert result["threshold"] == pytest.approx(1.0, abs=1e-6)
    assert "reason" not in result


def test_deleted_entities_block_with_entity_set_mismatch_reason(tmp_path: Path):
    pre = _make_line_ir("A1", (0.0, 0.0), (10.0, 10.0))
    post = {"schema": "ariadne.dwg_graph_ir.v1", "entities": [], "diagnostics": {"entity_count": 0}}

    result = vg.visual_gate_from_ir_docs(
        pre,
        post,
        diff_doc=_make_deleted_diff("A1"),
        out_dir=str(tmp_path / "deleted"),
    )

    assert result["status"] == "blocked"
    assert result["pass"] is False
    assert result["reason"] == "entity_set_mismatch: deleted=1 created=0 (deferred-regen ceiling)"
    assert result["visual_diff_counts"] == {"created": 0, "modified": 0, "deleted": 1}
