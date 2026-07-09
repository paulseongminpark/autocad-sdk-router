from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import residue_tail_report as rtr


def _entity(handle: str, dxf_name: str, kind: str, **geometry):
    payload = {"kind": kind}
    payload.update(geometry)
    return {
        "handle": handle,
        "dxf_name": dxf_name,
        "layer": "0",
        "space": "block",
        "geometry": payload,
    }


def _block(name: str, *entities):
    return {"name": name, "handle": f"H_{name}", "def_entities": list(entities)}


def _ir(*block_defs):
    return {"schema": "ariadne.dwg_graph_ir.v1", "block_definitions": list(block_defs)}


def test_line_endpoint_mismatch_is_bucketed_by_end_field():
    ir_a = _ir(_block("DOOR", _entity("A1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])))
    ir_b = _ir(_block("DOOR", _entity("B1", "LINE", "line", start=[0, 0, 0], end=[2, 0, 0])))

    report = rtr.residue_tail_report(ir_a, ir_b)

    assert report["schema"] == "ariadne.residue_tail.v1"
    assert report["by_field_combo"] == {"end": 1}
    assert report["by_kind"] == {"LINE": 1}
    assert report["unmatched"] == {"a": 0, "b": 0}
    assert report["records"][0]["differing_fields"] == ("end",)
    assert report["totals"] == {"defs_examined": 1, "residual_entities": 1}


def test_a_side_only_extra_entity_is_marked_unmatched():
    ir_a = _ir(_block(
        "DOOR",
        _entity("A1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0]),
        _entity("A2", "CIRCLE", "circle", center=[5, 5, 0], radius=1.0),
    ))
    ir_b = _ir(_block(
        "DOOR",
        _entity("B1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0]),
    ))

    report = rtr.residue_tail_report(ir_a, ir_b)

    assert report["by_field_combo"] == {}
    assert report["by_kind"] == {"CIRCLE": 1}
    assert report["unmatched"] == {"a": 1, "b": 0}
    assert report["records"] == [{
        "def": "DOOR",
        "dxf_name": "CIRCLE",
        "side": "a",
        "handle": "A2",
        "reason": "unmatched",
    }]


def test_clean_definition_contributes_nothing():
    ir = _ir(_block("CLEAN", _entity("L1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])))

    report = rtr.residue_tail_report(ir, copy.deepcopy(ir))

    assert report["by_field_combo"] == {}
    assert report["by_kind"] == {}
    assert report["unmatched"] == {"a": 0, "b": 0}
    assert report["records"] == []
    assert report["totals"] == {"defs_examined": 0, "residual_entities": 0}


def test_hatch_phase_carrier_equivalence_is_not_residual():
    loops = [{"type": "polyline", "closed": True, "vertices": [[0, 0], [1, 0], [1, 1], [0, 1]]}]
    ir_a = _ir(_block("H", _entity(
        "HA",
        "HATCH",
        "hatch",
        pattern_type=1.0,
        pattern_scale=350.0,
        pattern_definitions=[{
            "angle": 0.0,
            "base": [250000.00000000023, -234000.0],
            "offset": [43.75, 43.75],
        }],
        loops=loops,
    )))
    ir_b = _ir(_block("H", _entity(
        "HB",
        "HATCH",
        "hatch",
        pattern_type=2.0,
        pattern_scale=350.0,
        pattern_origin=[250000.00000000023, -234000.0],
        pattern_definitions=[{
            "angle": 0.0,
            "base": [0.0, 0.0],
            "offset": [0.125, 0.125],
        }],
        loops=loops,
    )))

    report = rtr.residue_tail_report(ir_a, ir_b)

    assert report["by_field_combo"] == {}
    assert report["by_kind"] == {}
    assert report["records"] == []
    assert report["totals"]["residual_entities"] == 0


def test_output_is_deterministic_under_entity_reordering():
    a_first = _entity("A1", "LINE", "line", start=[0, 0, 0], end=[10, 0, 0])
    a_second = _entity("A2", "LINE", "line", start=[0, 1, 0], end=[20, 1, 0])
    b_first = _entity("B1", "LINE", "line", start=[0, 0, 0], end=[11, 0, 0])
    b_second = _entity("B2", "LINE", "line", start=[0, 1, 0], end=[21, 1, 0])

    report_a = rtr.residue_tail_report(
        _ir(_block("PAIR", a_second, a_first)),
        _ir(_block("PAIR", b_first, b_second)),
    )
    report_b = rtr.residue_tail_report(
        _ir(_block("PAIR", a_first, a_second)),
        _ir(_block("PAIR", b_second, b_first)),
    )

    assert json.dumps(report_a, sort_keys=True) == json.dumps(report_b, sort_keys=True)
