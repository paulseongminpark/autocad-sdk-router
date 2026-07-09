from __future__ import annotations

import copy
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import blockdef_diff


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


def _per_def(report, name: str):
    return next(row for row in report["per_def"] if row["name"] == name)


def _hatch(handle, *, ptype, scale, base, offset, angle=1.5707963267948966):
    return _entity(
        handle, "HATCH", "hatch",
        pattern_name="H3", pattern_scale=scale, pattern_type=ptype,
        pattern_angle=0.7853981633974483, is_solid_fill=False,
        loops=[{"index": 0, "loop_type": 16, "closed": True}],
        pattern_definitions=[
            {"angle": angle, "base": list(base), "offset": list(offset), "dashes": []},
        ],
    )


def test_partial_rows_match_full_diff_for_singletons_and_subset():
    hatch_b = _hatch("B1", ptype=2.0, scale=350.0,
                     base=[0.0, 0.0], offset=[0.125, 0.125])
    hatch_b["geometry"]["pattern_origin"] = [250000.00000000023, -234000.0]
    ir_a = _ir(
        _block("A_LINE", _entity("A1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])),
        _block("B_HATCH", _hatch(
            "A2", ptype=1.0, scale=350.0,
            base=[250000.00000000023, -234000.0], offset=[43.75, 43.75])),
        _block(
            "C_MIXED",
            _entity("A3", "LINE", "line", start=[1, 0, 0], end=[2, 0, 0]),
            _entity("A4", "CIRCLE", "circle", center=[2, 0, 0], radius=1.0),
        ),
    )
    ir_b = _ir(
        _block("A_LINE", _entity("B9", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])),
        _block("B_HATCH", hatch_b),
        _block("C_MIXED", _entity("B3", "LINE", "line", start=[1, 0, 0], end=[2, 0, 0])),
        _block("Z_ONLY_IN_B", _entity("BZ", "LINE", "line", start=[9, 0, 0], end=[10, 0, 0])),
    )
    names = ["A_LINE", "B_HATCH", "C_MIXED"]

    full = blockdef_diff.diff_block_definitions(ir_a, ir_b)

    for name in names:
        partial = blockdef_diff.diff_block_definitions_partial(ir_a, ir_b, [name])
        assert partial["schema"] == "ariadne.blockdef_diff.partial.v1"
        assert partial["per_def"] == [_per_def(full, name)]
        assert partial["partial"] == {
            "requested": [name],
            "compared": 1,
            "missing": [],
        }
        assert partial["totals"] == {
            "a_entity_total": _per_def(full, name)["a_total"],
            "b_entity_total": _per_def(full, name)["b_total"],
            "diff0_total": _per_def(full, name)["diff0"],
        }

    partial_all = blockdef_diff.diff_block_definitions_partial(ir_a, ir_b, names)

    assert partial_all["per_def"] == [_per_def(full, name) for name in names]
    assert partial_all["partial"] == {
        "requested": names,
        "compared": 3,
        "missing": [],
    }
    assert partial_all["totals"] == {
        "a_entity_total": 4,
        "b_entity_total": 3,
        "diff0_total": 3,
    }


def test_partial_name_map_matches_full_diff_rows():
    ir_a = _ir(
        _block(
            "*U172",
            _entity("A1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0]),
            _entity("A2", "INSERT", "block_reference", block_name="*U9", position=[0, 0, 0]),
        ),
        _block("*U9", _entity("B1", "LINE", "line", start=[2, 0, 0], end=[3, 0, 0])),
    )
    ir_b = _ir(
        _block(
            "ARIADNE_ANON_U172",
            _entity("C1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0]),
            _entity("C2", "INSERT", "block_reference",
                    block_name="ARIADNE_ANON_U9", position=[0, 0, 0]),
        ),
        _block("ARIADNE_ANON_U9", _entity("D1", "LINE", "line", start=[2, 0, 0], end=[3, 0, 0])),
    )
    name_map = {"*U172": "ARIADNE_ANON_U172", "*U9": "ARIADNE_ANON_U9"}

    full = blockdef_diff.diff_block_definitions(ir_a, ir_b, name_map=name_map)
    partial = blockdef_diff.diff_block_definitions_partial(
        ir_a, ir_b, ["*U172", "*U9"], name_map=name_map)

    assert partial["per_def"] == [_per_def(full, "*U172"), _per_def(full, "*U9")]
    assert partial["partial"] == {
        "requested": ["*U172", "*U9"],
        "compared": 2,
        "missing": [],
    }
    assert partial["totals"] == {
        "a_entity_total": 3,
        "b_entity_total": 3,
        "diff0_total": 3,
    }


def test_partial_unknown_name_is_reported_missing():
    ir = _ir(_block("KNOWN", _entity("A1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])))

    partial = blockdef_diff.diff_block_definitions_partial(ir, copy.deepcopy(ir), ["UNKNOWN"])

    assert partial["per_def"] == []
    assert partial["partial"] == {
        "requested": ["UNKNOWN"],
        "compared": 0,
        "missing": [{"name": "UNKNOWN", "reason": "not_found"}],
    }
    assert partial["totals"] == {
        "a_entity_total": 0,
        "b_entity_total": 0,
        "diff0_total": 0,
    }


def test_partial_derived_cache_request_is_reported_missing_not_compared():
    ln = _entity("A1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])
    cache_a = _entity("C1", "MTEXT", "mtext", position=[5, 5, 0], text="1200")
    cache_b = _entity("C2", "MTEXT", "mtext", position=[6, 5, 0], text="1200")
    ir_a = _ir(_block("DOOR", copy.deepcopy(ln)), _block("*D7", cache_a))
    ir_b = _ir(_block("DOOR", copy.deepcopy(ln)), _block("*D9", cache_b))

    partial = blockdef_diff.diff_block_definitions_partial(ir_a, ir_b, ["*D7", "DOOR"])

    assert partial["per_def"] == [{
        "name": "DOOR",
        "a_total": 1,
        "b_total": 1,
        "diff0": 1,
        "removed": 0,
        "added": 0,
        "modified": 0,
        "missing_side": None,
    }]
    assert partial["partial"] == {
        "requested": ["*D7", "DOOR"],
        "compared": 1,
        "missing": [{"name": "*D7", "reason": "excluded_derived_cache"}],
    }
    assert partial["totals"] == {
        "a_entity_total": 1,
        "b_entity_total": 1,
        "diff0_total": 1,
    }
