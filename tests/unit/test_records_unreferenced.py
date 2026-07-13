#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Real-schema tests for build_records_patch's include_unreferenced /
excluded_table_kinds honesty (P5 records-widening).

The fixture field names mirror the ACTUAL dwg_graph_ir.v1 census schema,
verified against runs/e2e_1dwg_R4x_ccw_20260711/census/dwg_graph_ir.json:
  - symbol_tables.layers[].{name, linetype, color_index}
  - symbol_tables.linetypes[].{name, dash_lengths}
  - symbol_tables.text_styles[].{name, font_file}
  - symbol_tables.dim_styles[].{name, dimtxsty, dimltype}
  - symbol_tables.app_ids[].{handle, name}
  - symbol_tables.viewports[].{name}          (incl. the reserved '*Active')
  - entities[].{dxf_name, layer, geometry}     -- 'layer' is the ONLY record-
    reference field the IR records; TEXT/MTEXT carry NO 'style' key (all 384 in
    1.dwg), so text styles are unreachable from entities.

The prior (rejected) version's fixture used a top-level entity 'dimstyle' key
the real extractor never emits, so its "reference detection" test exercised a
path that does not exist (defect 3). These tests use only real field names.
"""
from __future__ import annotations

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.full_roundtrip_capstone import (  # noqa: E402
    build_records_patch,
    referenced_record_names,
    EXCLUDED_TABLE_KINDS,
)

TARGET = {"original_path": "seed.dwg", "staged_path": "staged.dwg"}


def _census():
    return {
        "symbol_tables": {
            "layers": [
                {"name": "0", "linetype": "Continuous", "color_index": 7},
                {"name": "WALLS", "linetype": "DASHED", "color_index": 1},
                {"name": "UNUSED_LAYER", "linetype": "Continuous", "color_index": 2},
            ],
            "linetypes": [
                {"name": "Continuous", "dash_lengths": []},
                {"name": "DASHED", "dash_lengths": [0.5, -0.25]},
                {"name": "PHANTOM", "dash_lengths": [1.0, -0.5]},
            ],
            "text_styles": [
                {"name": "Standard", "font_file": "txt.shx"},
                {"name": "TITLE", "font_file": "romans.shx"},
            ],
            "dim_styles": [
                {"name": "Standard", "dimtxsty": "Standard", "dimltype": "Continuous"},
                {"name": "ARCH", "dimtxsty": "TITLE", "dimltype": "DASHED"},
            ],
            "app_ids": [
                {"handle": "12", "name": "ACAD"},
                {"handle": "9E", "name": "ACAD_PSEXT"},
            ],
            "viewports": [
                {"name": "*Active", "height": 100.0, "width": 200.0},
            ],
            "ucs": [],
            "views": [],
        },
        "entities": [
            {"dxf_name": "LINE", "layer": "WALLS",
             "geometry": {"kind": "line", "start": [0, 0, 0], "end": [1, 0, 0]}},
            # TEXT entity that, like the real extractor, carries NO style field:
            {"dxf_name": "TEXT", "layer": "0",
             "geometry": {"kind": "text", "position": [0, 0, 0], "height": 2.5, "text": "A"}},
        ],
        "block_definitions": [],
    }


def _ops_by_label(patch):
    counts = {}
    for op in patch["operations"]:
        label = op["step_id"].rsplit("_", 1)[0]
        counts[label] = counts.get(label, 0) + 1
    return counts


def test_include_unreferenced_true_replays_all_named_records():
    patch, meta = build_records_patch(_census(), TARGET, "P")
    counts = _ops_by_label(patch)
    # every named record of each handled table kind is replayed (the ship mode)
    assert counts.get("layer") == 3
    assert counts.get("linetype") == 3
    assert counts.get("textstyle") == 2
    assert counts.get("dimstyle") == 2
    assert counts.get("vport") == 1
    assert meta["include_unreferenced"] is True
    assert not meta["skipped_unreferenced"]           # nothing dropped
    # app_id is never emitted as an op in any mode
    assert "app_id" not in counts
    assert all("regapp" not in op["operation"] for op in patch["operations"])


def test_include_unreferenced_false_replays_documented_subset():
    patch, meta = build_records_patch(_census(), TARGET, "P", include_unreferenced=False)
    counts = _ops_by_label(patch)
    assert counts.get("layer") == 2         # '0' (reserved/used) + 'WALLS' (entity.layer)
    assert counts.get("linetype") == 2      # 'Continuous' (reserved) + 'DASHED' (layer->linetype)
    assert counts.get("textstyle") == 1     # 'Standard' only -- TITLE is unreachable
    assert counts.get("dimstyle") == 1      # 'Standard' only -- ARCH is unreachable
    assert counts.get("vport") == 1         # '*Active' reserved, always kept
    # the dropped records are REPORTED, not silently shrunk
    assert meta["skipped_unreferenced"] == {
        "layer": 1, "linetype": 1, "textstyle": 1, "dimstyle": 1,
    }
    assert meta["include_unreferenced"] is False


def test_reference_scan_matches_documented_reachability():
    used = referenced_record_names(_census())
    assert used["layer"] == {"WALLS", "0"}          # both entities' layers
    # layer->linetype hop fires for BOTH used layers: WALLS->DASHED, '0'->Continuous
    assert used["linetype"] == {"DASHED", "Continuous"}
    # NOT reachable -- the IR records no entity->style / entity->dimstyle edge:
    assert used["textstyle"] == set()
    assert used["dimstyle"] == set()


def test_vport_active_carveout_is_byte_identical_in_both_modes():
    p_true, _ = build_records_patch(_census(), TARGET, "P")
    p_false, _ = build_records_patch(_census(), TARGET, "P", include_unreferenced=False)

    def _active(patch):
        return [op for op in patch["operations"]
                if op["operation"] == "create_vport" and op["args"].get("name") == "*Active"]

    a_true, a_false = _active(p_true), _active(p_false)
    assert len(a_true) == 1 and len(a_false) == 1
    assert a_true[0] == a_false[0]           # identical op: args + step_id + operation


def test_app_id_is_excluded_not_applied():
    patch, meta = build_records_patch(_census(), TARGET, "P")
    # app_id surfaces as an explicit DEFERRAL with the rollback-only reason...
    assert "app_id" in meta["excluded_table_kinds"]
    assert "app_id" in EXCLUDED_TABLE_KINDS
    assert "regapp" in meta["excluded_table_kinds"]["app_id"].lower()
    assert "rollback" in meta["excluded_table_kinds"]["app_id"].lower()
    # ...and is never counted applied (no op targets it, no regapp op emitted)
    assert all(op["operation"] != "create_app_id" for op in patch["operations"])
    assert all("regapp" not in op["operation"] for op in patch["operations"])
