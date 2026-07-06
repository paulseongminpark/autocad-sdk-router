#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "tools"))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import cross_verify as cv


def _mini_libredwg_doc():
    return {
        "OBJECTS": [
            {
                "object": "LAYER",
                "handle": [0, 1, 16],
                "name": "0",
            },
            {
                "object": "LAYER",
                "handle": [0, 1, 17],
                "name": "A-WALL",
            },
            {
                "object": "BLOCK_HEADER",
                "name": "*Model_Space",
                "entities": [
                    [3, 2, 100, 100],
                    [3, 2, 101, 101],
                    [3, 2, 102, 102],
                ],
            },
            {
                "entity": "LINE",
                "_subclass": "AcDbLine",
                "handle": [0, 2, 100],
                "layer": [5, 1, 16, 16],
            },
            {
                "entity": "TEXT",
                "_subclass": "AcDbText",
                "handle": [0, 2, 101],
                "layer": [5, 1, 17, 17],
            },
            {
                "entity": "ELLIPSE",
                "_subclass": "AcDbEllipse",
                "handle": [0, 2, 102],
                "layer": [5, 1, 16, 16],
            },
        ]
    }


def _mini_ir():
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "entities": [
            {"dxf_name": "LINE", "geometry": {"kind": "line"}, "layer": "0"},
            {"dxf_name": "TEXT", "geometry": {"kind": "text"}, "layer": "A-WALL"},
            {"dxf_name": "ELLIPSE", "geometry": {"kind": "ellipse"}, "layer": "0"},
        ],
        "symbol_tables": {
            "layers": [{"name": "0"}, {"name": "A-WALL"}],
        },
    }


def test_summarize_libredwg_doc_counts_modelspace_and_unmapped():
    summary = cv.summarize_libredwg_doc(_mini_libredwg_doc())

    assert summary["entity_total"] == 3
    assert summary["layer_count"] == 2
    assert summary["mapped_kind_counts"] == {"line": 1, "text": 1}
    assert summary["unmapped"] == [
        {"entity": "ELLIPSE", "subclass": "AcDbEllipse", "count": 1}
    ]


def test_build_verdict_reports_agreement_with_unmapped_surface():
    lib_summary = {
        "entity_total": 3,
        "layer_count": 2,
        "mapped_kind_counts": {"line": 1, "text": 1},
        "unmapped": [{"entity": "ELLIPSE", "subclass": "AcDbEllipse", "count": 1}],
    }
    ir_summary = {
        "entity_total": 3,
        "layer_count": 2,
        "mapped_kind_counts": {"line": 1, "text": 1},
    }

    verdict = cv.build_verdict(lib_summary, ir_summary)

    assert verdict["agree"] is True
    assert verdict["deltas"] == []
    assert verdict["unmapped"] == lib_summary["unmapped"]


def test_build_verdict_reports_total_kind_and_layer_deltas():
    lib_summary = {
        "entity_total": 4,
        "layer_count": 3,
        "mapped_kind_counts": {"line": 2, "text": 1},
        "unmapped": [],
    }
    ir_summary = {
        "entity_total": 3,
        "layer_count": 2,
        "mapped_kind_counts": {"line": 1, "text": 1},
    }

    verdict = cv.build_verdict(lib_summary, ir_summary)

    assert verdict["agree"] is False
    assert verdict["deltas"] == [
        {"field": "entity_total", "libredwg": 4, "ir": 3},
        {"field": "layer_count", "libredwg": 3, "ir": 2},
        {"field": "kind:line", "libredwg": 2, "ir": 1},
    ]


@pytest.mark.skipif(
    not Path(r"D:\dev\99_tools\libredwg\bin\dwgread.exe").exists(),
    reason="LibreDWG sidecar unavailable on this machine",
)
def test_cross_verify_live_fixture_against_real_arx_ir():
    fixture = Path(r"D:\dev\.build\cados_plan\wt\w5_gates\tests\fixtures\native_sample.dwg")
    ir_path = Path(r"D:\dev\.build\cados_plan\runs\t1_cert\pre_shared\dwg_graph_ir.json")
    if not ir_path.exists():
        pytest.skip("real ARX IR artifact not present")

    with tempfile.TemporaryDirectory() as td:
        verdict = cv.cross_verify_dwg(
            str(fixture),
            ir_path=str(ir_path),
            out_dir=td,
            libredwg_bin=r"D:\dev\99_tools\libredwg\bin",
        )

    assert verdict["status"] == "ok"
    assert verdict["agree"] is True
    assert verdict["libredwg"]["entity_total"] == 21747
    assert verdict["ir"]["entity_total"] == 21747
    assert verdict["libredwg"]["layer_count"] == 70
    assert verdict["ir"]["layer_count"] == 70
