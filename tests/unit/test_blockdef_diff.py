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


def test_identical_defs_yield_full_diff0_and_fraction_one():
    ir = _ir(
        _block("DOOR", _entity("A1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])),
        _block("*U172", _entity("A2", "CIRCLE", "circle", center=[2, 2, 0], radius=1.0)),
    )

    report = blockdef_diff.diff_block_definitions(ir, copy.deepcopy(ir))

    assert report["schema"] == "ariadne.blockdef_diff.v1"
    assert report["totals"]["diff0_total"] == 2
    assert report["totals"]["interior_diff0_fraction"] == 1.0
    assert _per_def(report, "*U172")["diff0"] == 1
    assert _per_def(report, "DOOR")["diff0"] == 1


def test_missing_definition_in_b_is_reported_and_counted():
    ir_a = _ir(
        _block("A", _entity("A1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])),
        _block("B", _entity("B1", "ARC", "arc", center=[0, 0, 0], radius=2.0, start_angle=0.0, end_angle=1.0)),
    )
    ir_b = _ir(
        _block("A", _entity("A9", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])),
    )

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)
    missing = _per_def(report, "B")

    assert missing["missing_side"] == "b"
    assert missing["a_total"] == 1
    assert missing["b_total"] == 0
    assert missing["removed"] == 1
    assert report["totals"]["a_def_count"] == 2
    assert report["totals"]["b_def_count"] == 1
    assert report["totals"]["a_entity_total"] == 2
    assert report["totals"]["b_entity_total"] == 1


def test_removed_entity_inside_definition_counts_as_removed():
    ir_a = _ir(
        _block(
            "DOOR",
            _entity("D1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0]),
            _entity("D2", "CIRCLE", "circle", center=[2, 0, 0], radius=1.0),
        )
    )
    ir_b = _ir(
        _block(
            "DOOR",
            _entity("D1X", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0]),
        )
    )

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)
    per_def = _per_def(report, "DOOR")

    assert per_def["diff0"] == 1
    assert per_def["removed"] == 1
    assert per_def["added"] == 0
    assert per_def["modified"] == 0


def test_kind_gap_aggregates_counts_across_all_definitions():
    ir_a = _ir(
        _block("A", _entity("A1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])),
        _block("B", _entity("B1", "CIRCLE", "circle", center=[1, 1, 0], radius=1.0)),
    )
    ir_b = _ir(
        _block("A", _entity("A9", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])),
        _block("C", _entity("C1", "LINE", "line", start=[2, 0, 0], end=[3, 0, 0])),
    )

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)

    assert report["by_kind_gap"] == {
        "circle": {"a_count": 1, "b_count": 0},
        "line": {"a_count": 1, "b_count": 2},
    }


def test_empty_a_entity_total_yields_none_fraction():
    ir_a = _ir(_block("EMPTY"))
    ir_b = _ir(_block("FULL", _entity("F1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])))

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)

    assert report["totals"]["a_entity_total"] == 0
    assert report["totals"]["interior_diff0_fraction"] is None


def test_spline_canonical_representation_matches_across_fit_asymmetry():
    # a-side: fit-authored spline (fit_points inline) + canonical top-level data;
    # b-side: rebuilt from control/knots - no fit_points. Same curve => diff0.
    cp = [[0.0, 0.0, 0.0], [1.0, 1.0, 0.0], [2.0, 0.0, 0.0]]
    kn = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
    def spl(with_fit):
        g = {"kind": "spline", "degree": 2.0, "closed": False}
        if with_fit:
            g["fit_points"] = [[0.0, 0.0, 0.0], [1.0, 0.5, 0.0], [2.0, 0.0, 0.0]]
        return {"handle": "S1", "layer": "0", "geometry": g,
                "spline_control_points": cp, "spline_knots": kn}
    ir_a = {"block_definitions": [{"name": "D", "def_entities": [spl(True)]}]}
    ir_b = {"block_definitions": [{"name": "D", "def_entities": [spl(False)]}]}
    res = blockdef_diff.diff_block_definitions(ir_a, ir_b)
    t = res["totals"]
    assert t["diff0_total"] == 1 and t["a_entity_total"] == 1
    assert t["interior_diff0_fraction"] == 1.0
    assert t["spline_fit_authored_a"] == 1
    assert t["spline_fit_authored_b"] == 0


def test_spline_different_control_points_still_mismatch():
    def spl(cp):
        return {"handle": "S1", "layer": "0",
                "geometry": {"kind": "spline", "degree": 2.0, "closed": False},
                "spline_control_points": cp,
                "spline_knots": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]}
    ir_a = {"block_definitions": [{"name": "D", "def_entities": [spl([[0.0, 0.0, 0.0], [1.0, 1.0, 0.0], [2.0, 0.0, 0.0]])]}]}
    ir_b = {"block_definitions": [{"name": "D", "def_entities": [spl([[0.0, 0.0, 0.0], [1.0, 9.9, 0.0], [2.0, 0.0, 0.0]])]}]}
    res = blockdef_diff.diff_block_definitions(ir_a, ir_b)
    assert res["totals"]["diff0_total"] == 0


# ---- *D dimension-derived-cache measurement contract (R4l program review) ----
# Measured on R4l: 2,183/2,534 residual mismatches were exactly 113 a-side *D
# orphans + 113 freshly-minted b-side *D defs, dual to the drawing's 113
# dimensions -- rendered caches, not authored content. The L5 dim_semantic_gate
# verifies the dimensions themselves (1.0 on the same run).

def test_dim_cache_defs_are_excluded_with_honest_accounting():
    # A's dimension minted *D7; B's rebuilt dimension minted a FRESH *D9.
    # Name-matched compare would score both as mismatches; the contract
    # excludes them and accounts for them in totals.
    ln = _entity("A1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])
    cache_a = _entity("C1", "MTEXT", "mtext", position=[5, 5, 0], text="1200")
    cache_b = _entity("C2", "MTEXT", "mtext", position=[6, 5, 0], text="1200")
    ir_a = _ir(_block("DOOR", copy.deepcopy(ln)), _block("*D7", cache_a))
    ir_b = _ir(_block("DOOR", copy.deepcopy(ln)), _block("*D9", cache_b))

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)

    assert [row["name"] for row in report["per_def"]] == ["DOOR"]
    totals = report["totals"]
    assert totals["a_def_count"] == 1
    assert totals["b_def_count"] == 1
    assert totals["a_entity_total"] == 1
    assert totals["diff0_total"] == 1
    assert totals["interior_diff0_fraction"] == 1.0
    assert totals["derived_cache_excluded"] == {
        "name_pattern": r"^\*D\d+$",
        "a_def_count": 1,
        "b_def_count": 1,
        "a_entity_total": 1,
        "b_entity_total": 1,
        "reason": totals["derived_cache_excluded"]["reason"],
    }
    assert "dim_semantic_gate" in totals["derived_cache_excluded"]["reason"]


def test_include_derived_caches_restores_legacy_full_compare():
    ln = _entity("A1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])
    cache_a = _entity("C1", "MTEXT", "mtext", position=[5, 5, 0], text="1200")
    ir_a = _ir(_block("DOOR", copy.deepcopy(ln)), _block("*D7", cache_a))
    ir_b = _ir(_block("DOOR", copy.deepcopy(ln)))

    report = blockdef_diff.diff_block_definitions(
        ir_a, ir_b, exclude_derived_caches=False)

    assert sorted(row["name"] for row in report["per_def"]) == ["*D7", "DOOR"]
    totals = report["totals"]
    assert totals["a_entity_total"] == 2
    assert totals["diff0_total"] == 1
    assert totals["interior_diff0_fraction"] == 0.5
    assert totals["derived_cache_excluded"] is None


def test_dim_cache_pattern_is_strict_star_d_digits():
    # Only *D<digits> is a dimension cache. "*D" alone, non-numeric suffixes,
    # and other anonymous families (*U/*X) stay in the comparison.
    ln = _entity("A1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])
    ir = _ir(
        _block("*D", copy.deepcopy(ln)),
        _block("*DX1", copy.deepcopy(ln)),
        _block("*U172", copy.deepcopy(ln)),
        _block("*D42", copy.deepcopy(ln)),
    )

    report = blockdef_diff.diff_block_definitions(ir, copy.deepcopy(ir))

    assert sorted(row["name"] for row in report["per_def"]) == ["*D", "*DX1", "*U172"]
    excluded = report["totals"]["derived_cache_excluded"]
    assert excluded["a_def_count"] == 1
    assert excluded["a_entity_total"] == 1


# ---- hatch pattern-definition canonicalization (R4l residue analysis) -------
# Measured pair (def X-...$0$111a, pattern H3, scale 300): original extracts
# pattern_type=1 with getPatternDefinitionAt values scale-BAKED; the .pat
# replay rebuild extracts pattern_type=2 with UNIT values serialized at %.10g.
# Same line families, two representations. Genuinely different pattern bases
# (per-hatch origin phase) must STILL mismatch.

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


def test_hatch_scale_baked_vs_unit_pat_replay_are_canonically_equal():
    # a: type-1, scale 300 baked into base/offset (census shape).
    # b: type-2, unit values at .pat %.10g precision (rebuild shape).
    ir_a = _ir(_block("W", _hatch(
        "A1", ptype=1.0, scale=300.0,
        base=[14135.0, -7334.999999999942],
        offset=[-300.0, 5.684341886080802e-14])))
    ir_b = _ir(_block("W", _hatch(
        "B1", ptype=2.0, scale=300.0,
        base=[47.1166666667, -24.45],
        offset=[-1.0, 6.123233995736766e-17])))

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)

    assert report["totals"]["diff0_total"] == 1
    assert report["totals"]["interior_diff0_fraction"] == 1.0


def test_hatch_distinct_pattern_base_phase_still_mismatches():
    # Per-hatch pattern origin (phase) is REAL render state, not
    # representation: bases differing by a non-multiple of the line spacing
    # shift the hatch lines. Canonicalization must not absorb it.
    ir_a = _ir(_block("W", _hatch(
        "A1", ptype=2.0, scale=300.0, base=[52.933333, 5.2], offset=[-1.0, 0.0])))
    ir_b = _ir(_block("W", _hatch(
        "B1", ptype=2.0, scale=300.0, base=[47.116667, -24.45], offset=[-1.0, 0.0])))

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)

    assert report["totals"]["diff0_total"] == 0


def test_hatch_canonicalization_is_self_stable():
    ir = _ir(_block("W", _hatch(
        "A1", ptype=1.0, scale=300.0, base=[14135.0, -7335.0], offset=[-300.0, 0.0])))

    report = blockdef_diff.diff_block_definitions(ir, copy.deepcopy(ir))

    assert report["totals"]["interior_diff0_fraction"] == 1.0


# ---- phase-carrier folding (R4n census, runs/e2e_1dwg_R4n_origin_20260709) --
# The per-hatch phase may live baked in the row base points (originals: the
# census pattern_origin field is [0,0]) OR on HPORIGIN over zero-phase rows
# (the rebased-.pat replay). Same rendered lattice, two carriers. Values below
# are the real defect pair (def X-...$0$84a, pattern H3, scale 350).

def test_hatch_phase_in_row_base_equals_phase_in_origin_field():
    ir_a = _ir(_block("W", _hatch(
        "A1", ptype=1.0, scale=350.0,
        base=[250000.00000000023, -234000.0], offset=[43.75, 43.75])))
    b = _hatch("B1", ptype=2.0, scale=350.0,
               base=[0.0, 0.0], offset=[0.125, 0.125])
    b["geometry"]["pattern_origin"] = [250000.00000000023, -234000.0]
    ir_b = _ir(_block("W", b))

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)

    assert report["totals"]["diff0_total"] == 1
    assert report["totals"]["interior_diff0_fraction"] == 1.0


def test_hatch_true_phase_difference_survives_folding():
    ir_a = _ir(_block("W", _hatch(
        "A1", ptype=1.0, scale=350.0,
        base=[250000.0, -234000.0], offset=[43.75, 43.75])))
    b = _hatch("B1", ptype=2.0, scale=350.0,
               base=[0.0, 0.0], offset=[0.125, 0.125])
    b["geometry"]["pattern_origin"] = [250012.5, -234000.0]  # half-spacing off
    ir_b = _ir(_block("W", b))

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)

    assert report["totals"]["diff0_total"] == 0


def test_hatch_intra_pattern_structure_survives_rebase():
    # Two-row pattern (H3 shape): the rows' RELATIVE bases are structure, not
    # phase -- rebasing must preserve them while folding the common phase.
    a = _hatch("A1", ptype=1.0, scale=350.0,
               base=[100.0, 200.0], offset=[43.75, 43.75])
    a["geometry"]["pattern_definitions"].append(
        {"angle": 0.5, "base": [100.0, 243.75], "offset": [43.75, 43.75],
         "dashes": []})
    b = _hatch("B1", ptype=2.0, scale=350.0,
               base=[0.0, 0.0], offset=[0.125, 0.125])
    b["geometry"]["pattern_definitions"].append(
        {"angle": 0.5, "base": [0.0, 0.125], "offset": [0.125, 0.125],
         "dashes": []})
    b["geometry"]["pattern_origin"] = [100.0, 200.0]
    ir_a, ir_b = _ir(_block("W", a)), _ir(_block("W", b))

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)

    assert report["totals"]["diff0_total"] == 1


# ---- predefined-name (type-1) unit replay (R4p, runs/e2e_1dwg_R4p_phase_
# 20260709): predefined patterns (DASH x66 on 1.dwg) replay as TYPE-1 with
# UNIT rows -- the drawing resolves the name, nothing bakes the scale --
# carrying their per-hatch phase on HPORIGIN. pattern_type is provenance,
# not baking truth: baked-vs-unit must be read off the row magnitudes.


def test_hatch_predefined_type1_unit_replay_with_origin_equals_baked():
    ir_a = _ir(_block("W", _hatch(
        "A1", ptype=1.0, scale=350.0,
        base=[-24474.999999999516, -149365.00000000003],
        offset=[43.75, 43.75])))
    b = _hatch("B1", ptype=1.0, scale=350.0, base=[0.0, 0.0], offset=[0.125, 0.125])
    b["geometry"]["pattern_origin"] = [-24474.999999999516, -149365.00000000003]
    ir_b = _ir(_block("W", b))

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)

    assert report["totals"]["diff0_total"] == 1


def test_hatch_predefined_unit_replay_real_phase_shift_still_mismatches():
    # Replay origin off by half a line spacing (0.0625 * 350 = 21.875 world
    # units): a REAL phase difference folding must keep.
    ir_a = _ir(_block("W", _hatch(
        "A1", ptype=1.0, scale=350.0,
        base=[-24475.0, -149365.0],
        offset=[43.75, 43.75])))
    b = _hatch("B1", ptype=1.0, scale=350.0, base=[0.0, 0.0], offset=[0.125, 0.125])
    b["geometry"]["pattern_origin"] = [-24453.125, -149365.0]
    ir_b = _ir(_block("W", b))

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)

    assert report["totals"]["diff0_total"] == 0
