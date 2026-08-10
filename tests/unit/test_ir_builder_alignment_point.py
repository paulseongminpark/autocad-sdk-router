from __future__ import annotations

import io
import os
import sys

import ezdxf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from ir_builder import build_ir_from_database_graph  # noqa: E402
from build_from_ir import build_dxf_from_ir  # noqa: E402


NATIVE_SOURCE = os.path.join(
    ROOT, "src", "Ariadne.AcadNative", "AriadneNativeJob.cpp")


def _reload(doc):
    stream = io.StringIO()
    doc.write(stream)
    stream.seek(0)
    return ezdxf.read(stream)


def test_text_alignment_point_survives_native_graph_to_ir():
    graph = {
        "modelspace_entities": 2,
        "entities": [
            {
                "handle": "10",
                "dxf_name": "AcDbText",
                "layer": "TEXT",
                "position": [1.0, 2.0, 0.0],
                "alignment_point": {"x": 4.0, "y": 5.0, "z": 0.0},
                "is_default_alignment": False,
                "horizontal_mode": 1,
                "vertical_mode": 0,
            },
            {
                "handle": "11",
                "dxf_name": "AcDbText",
                "layer": "TEXT",
                "position": [7.0, 8.0, 0.0],
                "is_default_alignment": True,
                "horizontal_mode": 0,
                "vertical_mode": 0,
            },
        ],
    }

    ir = build_ir_from_database_graph(graph, {"dwg_path": "fixture.dwg"})
    by_handle = {entity["handle"]: entity for entity in ir["entities"]}

    assert by_handle["10"]["geometry"]["alignment_point"] == [4.0, 5.0, 0.0]
    assert "alignment_point" not in by_handle["11"]["geometry"]


def test_native_text_emits_alignment_state_modes_and_nondefault_point():
    source = open(NATIVE_SOURCE, encoding="utf-8").read()
    region = source[source.index("else if (AcDbText* pT"):
                    source.index("else if (AcDbPolyline* pPl")]

    assert "isDefaultAlignment()" in region
    assert '\\"is_default_alignment\\":' in region
    assert '\\"horizontal_mode\\":' in region
    assert '\\"vertical_mode\\":' in region
    assert "alignmentPoint()" in region


def test_nondefault_origin_alignment_restores_modes_and_point_after_reload():
    graph = {
        "modelspace_entities": 2,
        "entities": [
            {
                "handle": "10",
                "dxf_name": "AcDbText",
                "layer": "TEXT",
                "position": [10.0, 20.0, 0.0],
                "alignment_point": [0.0, 0.0, 0.0],
                "is_default_alignment": False,
                "horizontal_mode": 1,
                "vertical_mode": 2,
                "text": "origin-aligned",
                "height": 2.5,
            },
            {
                "handle": "11",
                "dxf_name": "AcDbText",
                "layer": "TEXT",
                "position": [30.0, 40.0, 0.0],
                # This is the native sentinel shape; the explicit state says
                # it is not a usable alignment point.
                "alignment_point": [0.0, 0.0, 0.0],
                "is_default_alignment": True,
                "horizontal_mode": 0,
                "vertical_mode": 0,
                "text": "default",
                "height": 2.5,
            },
        ],
    }
    ir = build_ir_from_database_graph(graph, {"dwg_path": "fixture.dwg"})
    doc, report = build_dxf_from_ir(ir)
    assert report.added["text"] == 2
    texts = {entity.dxf.text: entity for entity in _reload(doc).modelspace().query("TEXT")}

    aligned = texts["origin-aligned"]
    assert tuple(aligned.dxf.align_point) == (0.0, 0.0, 0.0)
    assert aligned.dxf.halign == 1
    assert aligned.dxf.valign == 2

    default = texts["default"]
    assert default.dxf.get("align_point") is None
    assert default.dxf.get("halign") is None
    assert default.dxf.get("valign") is None


def test_legacy_alignment_without_state_uses_modes_not_point_coordinates():
    graph = {
        "modelspace_entities": 1,
        "entities": [{
            "handle": "12",
            "dxf_name": "AcDbText",
            "layer": "TEXT",
            "position": [8.0, 9.0, 0.0],
            "alignment_point": [0.0, 0.0, 0.0],
            "horizontal_mode": 1,
            "vertical_mode": 0,
            "text": "legacy-aligned",
        }],
    }
    ir = build_ir_from_database_graph(graph, {"dwg_path": "fixture.dwg"})
    doc, report = build_dxf_from_ir(ir)
    assert report.added["text"] == 1
    text = list(_reload(doc).modelspace().query("TEXT"))[0]
    assert tuple(text.dxf.align_point) == (0.0, 0.0, 0.0)
    assert text.dxf.halign == 1


def test_ray_and_xline_builder_dispatch_survives_reload():
    graph = {
        "modelspace_entities": 2,
        "entities": [
            {
                "handle": "20",
                "dxf_name": "AcDbRay",
                "layer": "GUIDE",
                "base_point": [1.0, 2.0, 0.0],
                "unit_dir": [0.0, 1.0, 0.0],
            },
            {
                "handle": "21",
                "dxf_name": "AcDbXline",
                "layer": "GUIDE",
                "base_point": [3.0, 4.0, 0.0],
                "unit_dir": [1.0, 0.0, 0.0],
            },
        ],
    }
    ir = build_ir_from_database_graph(graph, {"dwg_path": "fixture.dwg"})
    doc, report = build_dxf_from_ir(ir)
    reloaded = _reload(doc).modelspace()

    assert report.added["ray"] == 1
    assert report.added["xline"] == 1
    ray = list(reloaded.query("RAY"))[0]
    xline = list(reloaded.query("XLINE"))[0]
    assert tuple(ray.dxf.start) == (1.0, 2.0, 0.0)
    assert tuple(ray.dxf.unit_vector) == (0.0, 1.0, 0.0)
    assert tuple(xline.dxf.start) == (3.0, 4.0, 0.0)
    assert tuple(xline.dxf.unit_vector) == (1.0, 0.0, 0.0)
