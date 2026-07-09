from __future__ import annotations

import math


_TWO_PI = 2.0 * math.pi


def _assert_finite_number(value) -> None:
    assert isinstance(value, (int, float))
    assert not isinstance(value, bool)
    assert math.isfinite(float(value))


def _assert_point2(value) -> None:
    assert isinstance(value, list)
    assert len(value) == 2
    for item in value:
        _assert_finite_number(item)


def _assert_radian_angle(value) -> None:
    _assert_finite_number(value)
    assert -_TWO_PI <= float(value) <= _TWO_PI


def _assert_edge(edge: dict) -> None:
    assert isinstance(edge, dict)
    edge_type = edge["type"]
    assert isinstance(edge_type, str)

    if edge_type == "line":
        assert set(edge) == {"type", "start", "end"}
        _assert_point2(edge["start"])
        _assert_point2(edge["end"])
        return

    if edge_type == "arc":
        assert set(edge) == {"type", "center", "radius", "start_angle", "end_angle", "ccw"}
        _assert_point2(edge["center"])
        _assert_finite_number(edge["radius"])
        assert float(edge["radius"]) > 0.0
        _assert_radian_angle(edge["start_angle"])
        _assert_radian_angle(edge["end_angle"])
        assert isinstance(edge["ccw"], bool)
        return

    if edge_type == "ellipse":
        assert set(edge) == {"type", "center", "major", "ratio", "start_angle", "end_angle", "ccw"}
        _assert_point2(edge["center"])
        _assert_point2(edge["major"])
        assert any(float(v) != 0.0 for v in edge["major"])
        _assert_finite_number(edge["ratio"])
        assert float(edge["ratio"]) >= 0.0
        _assert_radian_angle(edge["start_angle"])
        _assert_radian_angle(edge["end_angle"])
        assert isinstance(edge["ccw"], bool)
        return

    if edge_type == "spline":
        assert set(edge) == {"type", "degree", "control", "knots", "rational", "weights"}
        assert isinstance(edge["degree"], int)
        assert edge["degree"] >= 1
        assert isinstance(edge["control"], list)
        assert edge["control"]
        for point in edge["control"]:
            _assert_point2(point)
        assert isinstance(edge["knots"], list)
        assert edge["knots"]
        for knot in edge["knots"]:
            _assert_finite_number(knot)
        assert isinstance(edge["rational"], bool)
        assert isinstance(edge["weights"], list)
        for weight in edge["weights"]:
            _assert_finite_number(weight)
        return

    assert edge_type.startswith("unsupported_")
    assert set(edge) == {"type"}
    int(edge_type.split("_", 1)[1])


def _assert_edge_loop(loop: dict) -> None:
    assert isinstance(loop, dict)
    assert set(loop) == {"index", "loop_type", "closed", "status", "edges"}
    assert isinstance(loop["index"], int)
    assert isinstance(loop["loop_type"], int)
    assert isinstance(loop["closed"], bool)
    assert loop["status"] in {"ok", "unavailable"}
    assert isinstance(loop["edges"], list)
    for edge in loop["edges"]:
        _assert_edge(edge)


def test_edge_loop_contract_accepts_documented_supported_rows():
    loop = {
        "index": 0,
        "loop_type": 1,
        "closed": True,
        "status": "ok",
        "edges": [
            {"type": "line", "start": [0.0, 0.0], "end": [2.0, 0.0]},
            {
                "type": "arc",
                "center": [2.0, 1.0],
                "radius": 1.0,
                "start_angle": -math.pi / 2.0,
                "end_angle": math.pi / 2.0,
                "ccw": True,
            },
            {
                "type": "ellipse",
                "center": [1.0, 2.0],
                "major": [3.0, 0.0],
                "ratio": 0.5,
                "start_angle": 0.0,
                "end_angle": math.pi,
                "ccw": False,
            },
            {
                "type": "spline",
                "degree": 3,
                "control": [[0.0, 2.0], [1.0, 3.0], [2.0, 2.0], [3.0, 1.0]],
                "knots": [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0],
                "rational": True,
                "weights": [1.0, 0.75, 0.75, 1.0],
            },
        ],
    }

    _assert_edge_loop(loop)


def test_edge_loop_contract_preserves_unsupported_curve_passthrough():
    loop = {
        "index": 3,
        "loop_type": 17,
        "closed": False,
        "status": "ok",
        "edges": [{"type": "unsupported_99"}],
    }

    _assert_edge_loop(loop)


def test_edge_loop_angles_stay_radian_sized():
    loop = {
        "index": 1,
        "loop_type": 5,
        "closed": True,
        "status": "ok",
        "edges": [
            {
                "type": "arc",
                "center": [0.0, 0.0],
                "radius": 4.0,
                "start_angle": -math.pi,
                "end_angle": math.pi / 3.0,
                "ccw": True,
            },
            {
                "type": "ellipse",
                "center": [5.0, 5.0],
                "major": [0.0, 2.5],
                "ratio": 0.25,
                "start_angle": -math.pi / 4.0,
                "end_angle": math.pi / 4.0,
                "ccw": True,
            },
        ],
    }

    _assert_edge_loop(loop)
