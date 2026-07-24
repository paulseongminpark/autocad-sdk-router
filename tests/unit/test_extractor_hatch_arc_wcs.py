from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import jsonschema
import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from ir_builder import build_ir_from_database_graph  # noqa: E402


NATIVE_SOURCE = ROOT / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
SCHEMA = ROOT / "schemas" / "dwg_graph_ir.v1.schema.json"


def _cross(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _normalize(
    vector: tuple[float, float, float],
) -> tuple[float, float, float]:
    length = math.sqrt(sum(component * component for component in vector))
    return tuple(component / length for component in vector)


def _arbitrary_axis_basis(
    extrusion: tuple[float, float, float],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """AutoCAD arbitrary axis algorithm, isomorphic to the C++ helper."""
    normal = _normalize(extrusion)
    if abs(normal[0]) < 1.0 / 64.0 and abs(normal[1]) < 1.0 / 64.0:
        ocs_x = _normalize(_cross((0.0, 1.0, 0.0), normal))
    else:
        ocs_x = _normalize(_cross((0.0, 0.0, 1.0), normal))
    ocs_y = _normalize(_cross(normal, ocs_x))
    return ocs_x, ocs_y


def _wcs_angle_degrees(
    angle_radians: float,
    extrusion: tuple[float, float, float],
    parameter_x: tuple[float, float] = (1.0, 0.0),
    parameter_y: tuple[float, float] = (0.0, 1.0),
) -> float:
    """Python-isomorphic copy of hatchWcsAngleDegrees in C++."""
    ocs_x, ocs_y = _arbitrary_axis_basis(extrusion)
    local_x = (
        parameter_x[0] * math.cos(angle_radians)
        + parameter_y[0] * math.sin(angle_radians)
    )
    local_y = (
        parameter_x[1] * math.cos(angle_radians)
        + parameter_y[1] * math.sin(angle_radians)
    )
    world = tuple(
        ocs_x[index] * local_x + ocs_y[index] * local_y for index in range(3)
    )
    degrees = math.degrees(math.atan2(world[1], world[0]))
    return degrees + 360.0 if degrees < 0.0 else degrees


def _circle_point(
    center: tuple[float, float],
    radius: float,
    angle_degrees: float,
) -> tuple[float, float]:
    angle = math.radians(angle_degrees)
    return (
        center[0] + radius * math.cos(angle),
        center[1] + radius * math.sin(angle),
    )


def test_negative_extrusion_large_radius_arc_reproduces_wcs_endpoints():
    center = (127.0, -286.7)
    radius = 914.29
    extrusion = (0.0, 0.0, -1.0)
    start = math.radians(59.18)
    end = math.radians(59.182)  # measured failure class: only a 0.002 degree sweep

    start_wcs = _wcs_angle_degrees(start, extrusion)
    end_wcs = _wcs_angle_degrees(end, extrusion)
    start_point = _circle_point(center, radius, start_wcs)
    end_point = _circle_point(center, radius, end_wcs)

    assert start_wcs == pytest.approx(120.82, abs=1e-12)
    assert end_wcs == pytest.approx(120.818, abs=1e-12)
    assert start_point == pytest.approx(
        (-341.42977722713664, 498.47497916511264),
        abs=1e-9,
    )
    assert end_point == pytest.approx(
        (-341.4023691645771, 498.4913299706073),
        abs=1e-9,
    )
    assert start_point[1] > center[1]
    assert end_point[1] > center[1]
    assert math.dist(start_point, end_point) < 0.04


def test_positive_extrusion_arc_conversion_is_identity_in_degrees():
    for angle_degrees in (0.0, 59.18, 180.0, 300.0):
        converted = _wcs_angle_degrees(
            math.radians(angle_degrees),
            (0.0, 0.0, 1.0),
        )
        assert converted == pytest.approx(angle_degrees, abs=1e-12)


def test_negative_extrusion_reflects_ellipse_major_axis_and_parameters():
    major_angle = math.radians(30.0)
    major_axis = (math.cos(major_angle), math.sin(major_angle))
    minor_axis = (-math.sin(major_angle), math.cos(major_angle))

    reflected_major = _wcs_angle_degrees(
        0.0,
        (0.0, 0.0, -1.0),
        major_axis,
        minor_axis,
    )
    reflected_start = _wcs_angle_degrees(
        math.radians(20.0),
        (0.0, 0.0, -1.0),
        major_axis,
        minor_axis,
    )
    reflected_end = _wcs_angle_degrees(
        math.radians(80.0),
        (0.0, 0.0, -1.0),
        major_axis,
        minor_axis,
    )

    assert reflected_major == pytest.approx(150.0, abs=1e-12)
    assert reflected_start == pytest.approx(130.0, abs=1e-12)
    assert reflected_end == pytest.approx(70.0, abs=1e-12)


def test_native_hatch_arc_branches_emit_extrusion_and_wcs_degree_angles():
    source = NATIVE_SOURCE.read_text(encoding="utf-8")
    start = source.index("static std::string hatchEdgeJson")
    end = source.index("static std::string hatchLoopsJson", start)
    helper = source[start:end]

    assert "const AcGeVector3d& extrusion" in helper
    assert "1.0 / 64.0" in source
    assert "crossProduct" in source
    assert '\\"extrusion\\"' in helper
    assert '\\"start_angle_wcs_deg\\"' in helper
    assert '\\"end_angle_wcs_deg\\"' in helper
    assert "e->majorAxis()" in helper
    assert "e->minorAxis()" in helper


def test_hatch_arc_additive_fields_survive_ir_lifting_and_schema_validation():
    edge = {
        "type": "arc",
        "center": [127.0, -286.7],
        "radius": 914.29,
        "start_angle": math.radians(59.18),
        "end_angle": math.radians(59.182),
        "ccw": False,
        "extrusion": [0.0, 0.0, -1.0],
        "start_angle_wcs_deg": 120.82,
        "end_angle_wcs_deg": 120.818,
    }
    graph = {
        "modelspace_entities": 1,
        "entities": [
            {
                "handle": "41",
                "dxf_name": "AcDbHatch",
                "layer": "0",
                "normal": [0.0, 0.0, -1.0],
                "loops": [
                    {
                        "index": 0,
                        "loop_type": 1,
                        "closed": True,
                        "status": "ok",
                        "edges": [edge],
                    }
                ],
            }
        ],
    }

    ir = build_ir_from_database_graph(graph, {"dwg_path": "fixture.dwg"})

    assert ir["entities"][0]["geometry"]["loops"][0]["edges"][0] == edge
    schema = json.loads(SCHEMA.read_text(encoding="utf-8-sig"))
    edge_properties = (
        schema["$defs"]["geometry"]["properties"]["loops"]["items"]["properties"]
        ["edges"]["items"]["properties"]
    )
    assert {
        "extrusion",
        "start_angle_wcs_deg",
        "end_angle_wcs_deg",
    }.issubset(edge_properties)
    jsonschema.Draft7Validator(schema).validate(ir)
