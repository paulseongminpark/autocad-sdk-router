from __future__ import annotations

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import modified_composition


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


def test_build_report_counts_modified_and_removed_by_kind():
    census = _ir(_block(
        "DOOR",
        _entity("L1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0]),
        _entity(
            "H1",
            "HATCH",
            "hatch",
            # pattern_scale is the REAL difference driving the modified pair:
            # the original is_associative-flag difference stopped counting
            # when LEX-0008 legislated the sourceless-flag fold (R4r/R4s).
            pattern_name="SOLID",
            pattern_scale=1.0,
            pattern_type=1.0,
            is_solid_fill=False,
            loops=[{"index": 0, "loop_type": 16, "closed": True}],
            pattern_definitions=[],
        ),
        _entity("A1", "ARC", "arc", center=[0, 0, 0], radius=2.0, start_angle=0.0, end_angle=1.0),
    ))
    post = _ir(_block(
        "DOOR",
        _entity("L9", "LINE", "line", start=[0, 0, 0], end=[2, 0, 0]),
        _entity(
            "H9",
            "HATCH",
            "hatch",
            pattern_name="SOLID",
            pattern_scale=2.0,
            pattern_type=1.0,
            is_solid_fill=False,
            loops=[{"index": 0, "loop_type": 16, "closed": True}],
            pattern_definitions=[],
        ),
    ))
    interior_diff = {
        "schema": "ariadne.blockdef_diff.v1",
        "per_def": [{
            "name": "DOOR",
            "a_total": 3,
            "b_total": 2,
            "diff0": 0,
            "removed": 1,
            "added": 0,
            "modified": 2,
            "missing_side": None,
        }],
    }

    report = modified_composition.build_report(census, post, interior_diff)

    assert report["schema"] == "ariadne.modified_composition.v1"
    assert report["by_kind"] == {
        "ARC": {"modified": 0, "removed": 1, "added": 0},
        "HATCH": {"modified": 1, "removed": 0, "added": 0},
        "LINE": {"modified": 1, "removed": 0, "added": 0},
    }
    assert report["totals"] == {
        "dirty_def_count": 1,
        "def_kind_rows": 3,
        "modified": 2,
        "removed": 1,
        "added": 0,
        "residual": 3,
    }
