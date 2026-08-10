from __future__ import annotations

import io
import os
import sys

import ezdxf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import cross_oracle  # noqa: E402
from ir_builder import build_ir_from_database_graph, build_ir_from_extract  # noqa: E402
from build_from_ir import build_dxf_from_ir  # noqa: E402


NATIVE_SOURCE = os.path.join(
    ROOT, "src", "Ariadne.AcadNative", "AriadneNativeJob.cpp")
MANAGED_SOURCE = os.path.join(
    ROOT, "src", "Ariadne.DwgGeometryExtractor", "GeometryExtractor.cs")
MANAGED_DTOS = os.path.join(
    ROOT, "src", "Ariadne.DwgGeometryExtractor", "GeometryDtos.cs")


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


def test_managed_text_oracle_declares_and_emits_alignment_state():
    source = open(MANAGED_SOURCE, encoding="utf-8").read()
    dtos = open(MANAGED_DTOS, encoding="utf-8").read()

    assert "DBText text => ExtractText(text)" in source
    assert "text.IsDefaultAlignment" in source
    assert "text.HorizontalMode" in source
    assert "text.VerticalMode" in source
    assert "isDefaultAlignment ? null : ToPoint(text.AlignmentPoint)" in source
    for json_name in (
        "alignment_point",
        "is_default_alignment",
        "horizontal_mode",
        "vertical_mode",
    ):
        assert f'JsonProperty("{json_name}")' in dtos


def test_managed_and_native_text_alignment_state_compare_as_certified_data():
    managed_extract = {
        "summary": {"modelspace_count": 1},
        "entities": [{
            "handle": "10",
            "type": "TEXT",
            "layer": "TEXT",
            "geometry": {
                "kind": "text",
                "position": {"x": 10.0, "y": 20.0, "z": 0.0},
                "alignment_point": {"x": 0.0, "y": 0.0, "z": 0.0},
                "is_default_alignment": False,
                "horizontal_mode": 1,
                "vertical_mode": 2,
                "text": "origin-aligned",
                "height": 2.5,
                "rotation": 0.0,
            },
        }],
    }
    native_graph = {
        "modelspace_entities": 1,
        "entities": [{
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
            "rotation": 0.0,
        }],
    }

    managed_ir = build_ir_from_extract(
        managed_extract, None, {"extractor": "managed_test"})
    native_ir = build_ir_from_database_graph(
        native_graph, {"extractor": "native_test"})
    result = cross_oracle.compare_multiset(managed_ir, native_ir)

    assert result["status"] == cross_oracle.STATUS_OK
    assert result["exit_code"] == cross_oracle.EXIT_OK
    assert result["disagreements"] == []


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


def test_ray_and_xline_without_explicit_valid_geometry_are_skipped():
    invalid_geometry = [
        {},
        {"base_point": [1.0, 2.0, 0.0]},
        {"base_point": [1.0, 2.0], "unit_dir": [1.0, 0.0, 0.0]},
        {"base_point": [1.0, 2.0, 0.0], "unit_dir": [0.0, 0.0, 0.0]},
        {"base_point": [1.0, "bad", 0.0], "unit_dir": [1.0, 0.0, 0.0]},
    ]
    entities = []
    handle = 30
    geometry_by_handle = {}
    for dxf_name, kind in (("AcDbRay", "ray"), ("AcDbXline", "xline")):
        for geometry in invalid_geometry:
            geometry_by_handle[str(handle)] = {"kind": kind, **geometry}
            entities.append({
                "handle": str(handle),
                "dxf_name": dxf_name,
                "layer": "GUIDE",
            })
            handle += 1

    graph = {"modelspace_entities": len(entities), "entities": entities}
    ir = build_ir_from_database_graph(graph, {"dwg_path": "fixture.dwg"})
    for entity in ir["entities"]:
        entity["geometry"] = geometry_by_handle[entity["handle"]]
    doc, report = build_dxf_from_ir(ir)
    reloaded = _reload(doc).modelspace()

    assert report.added["ray"] == 0
    assert report.added["xline"] == 0
    assert report.skipped["ray:no_geom"] == len(invalid_geometry)
    assert report.skipped["xline:no_geom"] == len(invalid_geometry)
    assert list(reloaded.query("RAY")) == []
    assert list(reloaded.query("XLINE")) == []
