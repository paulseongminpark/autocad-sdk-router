# -*- coding: utf-8 -*-
"""R4t replay-repair contracts (R4s residue dissection, 2026-07-10).

Three REAL replay defects measured on reports/interior100/
loops_residue_analysis_R4s.json get their repair contracts pinned here:

  1. orphan-def sweep (ir_to_patch): reference-reachability missed 4 defs /
     28 entities (DIMDOT + _ArchTick referenced only from excluded *D caches;
     $0$ins-l + $0$ng unreferenced) -- every non-*D census def must be
     emitted.
  2. lwpolyline elevation carry (patch_ops.blocks): census bakes OCS
     elevation into vertex z; 25 pairs flattened to 0 because nothing
     carried it.
  3. per-vintage .pat synthesis (patch_engine): a per-NAME shared .pat
     forced the seed vintage onto a 4-vintage H3 population (154 hatches
     re-rendered X-grid -> plus-grid).
"""

from __future__ import annotations

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ir_to_patch
import patch_engine
from patch_ops import blocks as patch_blocks


# --------------------------------------------------------------------------- #
# 1. orphan-def sweep
# --------------------------------------------------------------------------- #

def _line_ent(handle):
    return {"handle": handle, "layer": "0",
            "geometry": {"kind": "line", "start": [0, 0, 0], "end": [1, 0, 0]}}


def _blockref_ent(handle, name):
    return {"handle": handle, "layer": "0",
            "geometry": {"kind": "block_reference", "block_name": name,
                         "position": [0, 0, 0], "scale": [1, 1, 1],
                         "rotation": 0.0}}


def _sweep_ir():
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "entities": [_blockref_ent("E1", "USED")],
        "block_definitions": [
            {"name": "USED", "def_entities": [_line_ent("U1")]},
            {"name": "ORPHAN", "def_entities": [_line_ent("O1")]},
            {"name": "*D42", "def_entities": [_line_ent("D1")]},
        ],
    }


def _created_block_names(patch):
    return [op["args"].get("name") or op["args"].get("block_name")
            for op in patch["operations"]
            if op.get("operation") == "create_block"]


def test_orphan_defs_are_swept_after_entity_stream():
    patch, deferred = ir_to_patch.build_patch_from_ir(
        _sweep_ir(), {"staged_path": "", "original_path": ""}, "test", None)
    created = _created_block_names(patch)
    assert "USED" in created
    assert "ORPHAN" in created


def test_sweep_never_emits_dim_caches():
    patch, _deferred = ir_to_patch.build_patch_from_ir(
        _sweep_ir(), {"staged_path": "", "original_path": ""}, "test", None)
    created = _created_block_names(patch)
    assert not any(str(name).startswith("*D") or "ANON_D42" in str(name)
                   for name in created)


def test_kind_filtered_runs_stay_partial_no_sweep():
    patch, _deferred = ir_to_patch.build_patch_from_ir(
        _sweep_ir(), {"staged_path": "", "original_path": ""}, "test",
        {"line"})
    assert "ORPHAN" not in _created_block_names(patch)


# --------------------------------------------------------------------------- #
# 2. lwpolyline elevation carry
# --------------------------------------------------------------------------- #

def _lw_geometry(z_values):
    return {
        "kind": "lwpolyline",
        "closed": False,
        "vertices": [
            {"point": [float(i), float(i) * 2.0, z], "bulge": 0.0}
            for i, z in enumerate(z_values)
        ],
    }


def _lw_op(g):
    ent = {"handle": "L1", "layer": "0", "geometry": g}
    return patch_blocks._def_entity_append_op("W", ent)


def test_lwpolyline_common_vertex_z_rides_as_elevation():
    op = _lw_op(_lw_geometry([0.4010621945564553] * 4))
    entity = op["args"]["entity"]
    assert entity["kind"] == "lwpolyline"
    assert entity["elevation"] == 0.4010621945564553


def test_lwpolyline_zero_z_carries_no_elevation_key():
    op = _lw_op(_lw_geometry([0.0] * 4))
    assert "elevation" not in op["args"]["entity"]


def test_lwpolyline_mixed_z_fails_safe_to_no_carry():
    op = _lw_op(_lw_geometry([0.4, 0.4, 0.5, 0.4]))
    assert "elevation" not in op["args"]["entity"]


# --------------------------------------------------------------------------- #
# 3. per-vintage .pat synthesis
# --------------------------------------------------------------------------- #

def _hatch_op(handle, rows, *, name="H3", scale=40.0, pattern_type=None):
    entity = {
        "kind": "hatch", "pattern_name": name, "pattern_scale": scale,
        "pattern_definitions": rows,
    }
    if pattern_type is not None:
        entity["pattern_type"] = pattern_type
    return {"operation": "append_block_entity",
            "args": {"block_name": "W", "entity": entity}}


def _pat_row_delta_y(line):
    # .pat row: angle, x-origin, y-origin, delta-x, delta-y[, dashes...]
    return float([f.strip() for f in line.split(",")][4])


_X_GRID = [
    {"angle": 0.7853981633974483, "base": [100.0, 200.0],
     "offset": [-28.2842712474619, 28.284271247461902], "dashes": []},
    {"angle": 2.356194490192345, "base": [100.0, 200.0],
     "offset": [-28.284271247461902, -28.2842712474619], "dashes": []},
]
_PLUS_GRID = [
    {"angle": 1.5707963267948966, "base": [0.0, 0.0],
     "offset": [-40.0, 0.0], "dashes": []},
    {"angle": 3.141592653589793, "base": [0.0, 0.0],
     "offset": [0.0, -40.0], "dashes": []},
]


def test_same_name_different_vintage_gets_separate_pat_files(tmp_path):
    op_x = _hatch_op("A1", [dict(r, base=list(r["base"])) for r in _X_GRID])
    op_plus = _hatch_op("A2", [dict(r, base=list(r["base"])) for r in _PLUS_GRID])
    patch_engine._synthesize_batch_pat_files(str(tmp_path), [op_x, op_plus])
    path_x = op_x["args"]["entity"]["pattern_pat_path"]
    path_plus = op_plus["args"]["entity"]["pattern_pat_path"]
    assert path_x != path_plus
    # leaf name must stay <NAME>.pat on BOTH (cwd-resolution contract)
    assert path_x.rsplit("/", 1)[-1] == "H3.pat"
    assert path_plus.rsplit("/", 1)[-1] == "H3.pat"
    assert os.path.exists(path_x) and os.path.exists(path_plus)
    with open(path_x, encoding="utf-8") as fh:
        content_x = fh.read()
    with open(path_plus, encoding="utf-8") as fh:
        content_plus = fh.read()
    assert content_x != content_plus
    assert content_x.startswith("*H3") and content_plus.startswith("*H3")


def test_same_vintage_different_phase_dedupes_to_one_file(tmp_path):
    rows_a = [dict(r, base=list(r["base"])) for r in _X_GRID]
    rows_b = [dict(r, base=[r["base"][0] + 77.5, r["base"][1] - 12.25])
              for r in _X_GRID]
    op_a = _hatch_op("A1", rows_a)
    op_b = _hatch_op("A2", rows_b)
    patch_engine._synthesize_batch_pat_files(str(tmp_path), [op_a, op_b])
    assert (op_a["args"]["entity"]["pattern_pat_path"]
            == op_b["args"]["entity"]["pattern_pat_path"])


# ---- GEN2c idempotence repair: pattern-scale double-division ---------------
# The .pat synthesizer divides base/offset/dashes by pattern_scale to undo the
# scale-baking of a kPreDefined census read. But a REBUILT hatch is created as
# kCustomDefined(2) and its census offset comes back in DEFINITION space (raw);
# dividing that again shrinks the family spacing by `scale` every regeneration
# (measured GEN2c: 2F3A gen1 0.7071 -> gen2 0.017678 = /40). The divide must be
# gated on the read convention (pattern_type <= 1 == baked).

_UNIT_ROW = {"angle": 0.0, "base": [0.0, 0.0], "offset": [0.0, 40.0], "dashes": []}


def test_predefined_row_divides_scale_out():
    # kPreDefined(1) census offset is scale-baked -> divide (forward fidelity;
    # keeps R4x at 27,128 unchanged). offset 40 / scale 40 == unit spacing 1.
    line = patch_engine._pattern_definition_line(
        dict(_UNIT_ROW), scale=40.0, pattern_type=1.0)
    assert _pat_row_delta_y(line) == 1.0


def test_absent_pattern_type_keeps_legacy_divide():
    # No pattern_type threaded -> legacy all-divide default (unchanged behavior
    # for any caller that does not know the read convention).
    line = patch_engine._pattern_definition_line(dict(_UNIT_ROW), scale=40.0)
    assert _pat_row_delta_y(line) == 1.0


def test_customdefined_row_does_not_re_divide_scale():
    # kCustomDefined(2) census offset is already definition-space (raw). It must
    # NOT be divided again: delta-y == the raw offset, not offset/scale.
    line = patch_engine._pattern_definition_line(
        dict(_UNIT_ROW), scale=40.0, pattern_type=2.0)
    assert _pat_row_delta_y(line) == 40.0


def test_custom_pattern_is_a_scale_fixed_point():
    # The idempotence property the GEN2c reflight validates: for a custom
    # (type 2) hatch, the delta the synthesizer writes equals the offset a
    # subsequent census reads back, so a second synthesis is byte-identical --
    # a fixed point. Pre-fix this shrank by `scale` each pass.
    scale = 40.0
    off = 0.7071067811865476
    row1 = {"angle": 0.0, "base": [0.0, 0.0], "offset": [0.0, off], "dashes": []}
    line1 = patch_engine._pattern_definition_line(
        row1, scale=scale, pattern_type=2.0)
    read_back = _pat_row_delta_y(line1)          # census re-reads this raw
    # NOT shrunk by scale (pre-fix this was off/40 == 0.017678); equal to the
    # input within the .pat write precision (10dp).
    assert abs(read_back - off) < 1e-9
    assert abs(read_back - off / scale) > 1e-3    # explicitly not the /scale bug
    row2 = {"angle": 0.0, "base": [0.0, 0.0], "offset": [0.0, read_back],
            "dashes": []}
    line2 = patch_engine._pattern_definition_line(
        row2, scale=scale, pattern_type=2.0)
    assert line1 == line2                          # byte-identical == fixed point
