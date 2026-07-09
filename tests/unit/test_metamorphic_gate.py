from __future__ import annotations

import copy
import os
import sys

import pytest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import metamorphic_gate


def _entity(handle: str, dxf_name: str, kind: str, *, layer: str = "0", **geometry):
    payload = {"kind": kind}
    payload.update(geometry)
    return {
        "handle": handle,
        "dxf_name": dxf_name,
        "layer": layer,
        "space": "block",
        "geometry": payload,
    }


def _ir(*block_defs):
    return {"schema": "ariadne.dwg_graph_ir.v1", "block_definitions": list(block_defs)}


def _block(name: str, *entities):
    return {"name": name, "handle": f"H_{name}", "def_entities": list(entities)}


def _phase_carrier_equal_pair():
    """Gate-EQUAL hatch pair: phase in row base (a) vs pattern_origin (b)."""
    loops = [
        {
            "index": 0,
            "loop_type": 1,
            "closed": True,
            "vertices": [
                {"point": [0.0, 0.0]},
                {"point": [100.0, 0.0]},
                {"point": [100.0, 100.0]},
                {"point": [0.0, 100.0]},
            ],
        }
    ]
    a = _entity(
        "A1",
        "HATCH",
        "hatch",
        pattern_name="H3",
        pattern_scale=350.0,
        pattern_type=1.0,
        pattern_angle=0.0,
        is_solid_fill=False,
        loops=copy.deepcopy(loops),
        pattern_definitions=[
            {
                "angle": 0.0,
                "base": [250000.00000000023, -234000.0],
                "offset": [43.75, 43.75],
                "dashes": [43.75, -43.75],
            }
        ],
    )
    b = _entity(
        "B1",
        "HATCH",
        "hatch",
        pattern_name="H3",
        pattern_scale=350.0,
        pattern_type=2.0,
        pattern_angle=0.0,
        is_solid_fill=False,
        loops=copy.deepcopy(loops),
        pattern_definitions=[
            {
                "angle": 0.0,
                "base": [0.0, 0.0],
                "offset": [0.125, 0.125],
                "dashes": [0.125, -0.125],
            }
        ],
        pattern_origin=[250000.00000000023, -234000.0],
    )
    return _ir(_block("W", a)), _ir(_block("W", b))


def test_hatch_phase_carrier_pair_is_equivariant_with_diff0():
    ir_a, ir_b = _phase_carrier_equal_pair()

    report = metamorphic_gate.measure_equivariance_report(ir_a, ir_b)

    assert report["schema"] == "ariadne.metamorphic_gate.v1"
    assert report["equivariant"] is True
    assert report["baseline"]["diff0_total"] == 1
    for verdict in report["verdicts"]:
        assert verdict["diff0_total"] == 1


def test_real_line_difference_stays_diff0_zero_at_every_offset():
    ir_a = _ir(
        _block(
            "L",
            _entity("A1", "LINE", "line", start=[0.0, 0.0, 0.0], end=[1.0, 0.0, 0.0]),
        )
    )
    ir_b = _ir(
        _block(
            "L",
            _entity("B1", "LINE", "line", start=[0.0, 0.0, 0.0], end=[2.0, 0.0, 0.0]),
        )
    )

    report = metamorphic_gate.measure_equivariance_report(ir_a, ir_b)

    assert report["equivariant"] is True
    for verdict in report["verdicts"]:
        assert verdict["diff0_total"] == 0


def test_translate_ir_does_not_mutate_input():
    ir_a, _ = _phase_carrier_equal_pair()
    before = copy.deepcopy(ir_a)

    translated = metamorphic_gate.translate_ir(ir_a, 10.0, -20.0)

    assert ir_a == before
    assert translated is not ir_a
    # Sanity: translation actually moved a world-space coordinate.
    a_base = ir_a["block_definitions"][0]["def_entities"][0]["geometry"][
        "pattern_definitions"
    ][0]["base"]
    t_base = translated["block_definitions"][0]["def_entities"][0]["geometry"][
        "pattern_definitions"
    ][0]["base"]
    assert t_base[0] == pytest.approx(a_base[0] + 10.0)
    assert t_base[1] == pytest.approx(a_base[1] - 20.0)
