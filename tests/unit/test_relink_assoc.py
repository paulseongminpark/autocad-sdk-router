#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3 assoc-relink arc (R4v) contract tests.

Covers the Python half of write.block.relink_hatch_assoc end to end:
op emission (patch_ops.blocks), stream placement (ir_to_patch), the
census->rebuilt handle translation + ledger passthrough (patch_engine),
the batch barrier (patch_batch_planner), and registry lockstep. The native
half (m08eHandleRelinkHatchAssoc) is proven by the live probe + R4v flight.
"""

from __future__ import annotations

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools import ir_to_patch  # noqa: E402
from tools import patch_batch_planner  # noqa: E402
from tools import patch_engine  # noqa: E402
from tools.patch_ops import blocks as patch_blocks  # noqa: E402


def _assoc_hatch(handle, srcs):
    return {
        "handle": handle,
        "dxf_name": "HATCH",
        "layer": "L1",
        "geometry": {
            "kind": "hatch",
            "pattern_name": "SOLID",
            "is_solid_fill": True,
            "is_associative": True,
            "assoc_source_handles": srcs,
            "normal": [0.0, 0.0, 1.0],
            "loops": [
                {"loop_type": 0,
                 "vertices": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]}
                for _ in srcs
            ],
        },
    }


def _boundary_lw(handle):
    return {
        "handle": handle,
        "dxf_name": "LWPOLYLINE",
        "layer": "L1",
        "geometry": {
            "kind": "lwpolyline",
            "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0]],
            "closed": True,
        },
    }


def _ir_with_assoc_def():
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "entities": [
            {"handle": "FF1", "dxf_name": "INSERT", "layer": "0",
             "geometry": {"kind": "block_reference", "block_name": "DEF_A",
                          "position": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0],
                          "rotation": 0.0}},
        ],
        "block_definitions": [
            {"name": "DEF_A", "handle": "D1", "def_entities": [
                _boundary_lw("1BD9"),
                _assoc_hatch("1BD8", [["1BD9"]]),
            ]},
        ],
    }


# ---- patch_ops.blocks: op emission ------------------------------------------


def test_relink_ops_emitted_for_assoc_hatch_with_sources():
    block_def = {"name": "DEF_A", "def_entities": [
        _boundary_lw("1BD9"), _assoc_hatch("1BD8", [["1BD9"]])]}

    ops = patch_blocks.relink_hatch_assoc_ops(block_def)

    assert len(ops) == 1
    op = ops[0]
    assert op["operation"] == "relink_hatch_assoc"
    assert op["args"]["hatch_handle"] == "1BD8"
    assert op["args"]["loops_source_handles"] == [["1BD9"]]
    assert op["source"] == {"handle": "1BD8"}


def test_relink_ops_skip_nonassoc_and_sourceless():
    plain = _assoc_hatch("AA10", [["AA11"]])
    plain["geometry"]["is_associative"] = False
    empty = _assoc_hatch("AA20", [])
    empty_loops = _assoc_hatch("AA30", [[]])
    block_def = {"name": "DEF_B", "def_entities": [plain, empty, empty_loops]}

    assert patch_blocks.relink_hatch_assoc_ops(block_def) == []


def test_append_op_carries_census_source_handle():
    op = patch_blocks._def_entity_append_op("DEF_A", _boundary_lw("1BD9"))

    assert op is not None
    assert op["source"] == {"handle": "1BD9"}


def test_build_job_args_passthrough_for_relink():
    out = patch_blocks.build_job_args(
        "write.block.relink_hatch_assoc",
        {"block_name": "DEF_A", "hatch_handle": "7621",
         "loops_source_handles": [["7622"]], "stray": 1})

    assert out == {"block_name": "DEF_A", "hatch_handle": "7621",
                   "loops_source_handles": [["7622"]]}


# ---- ir_to_patch: stream placement -------------------------------------------


def test_relink_ops_are_stream_tail():
    patch, deferred = ir_to_patch.build_patch_from_ir(
        _ir_with_assoc_def(), {"path": "x.dwg"}, "p-test")

    ops = patch["operations"]
    relinks = [op for op in ops if op["operation"] == "relink_hatch_assoc"]
    assert len(relinks) == 1
    assert ops[-1]["operation"] == "relink_hatch_assoc"
    assert relinks[0]["args"]["hatch_handle"] == "1BD8"
    # every append precedes every relink
    last_append = max(i for i, op in enumerate(ops)
                      if op["operation"] != "relink_hatch_assoc")
    first_relink = min(i for i, op in enumerate(ops)
                       if op["operation"] == "relink_hatch_assoc")
    assert last_append < first_relink


# ---- patch_engine: resolver passthrough + translation ------------------------


def test_resolver_carries_source_through_applied_records():
    patch = {"operations": [
        {"operation": "append_block_entity",
         "args": {"block_name": "DEF_A",
                  "entity": {"kind": "line", "start": [0, 0, 0], "end": [1, 0, 0]},
                  "layer": "L1"},
         "source": {"handle": "1BD9"}},
    ]}

    applied, deferred, err = patch_engine._resolve_native_write_ops(patch)

    assert err is None and not deferred
    assert applied[0]["source"] == {"handle": "1BD9"}
    assert patch_engine._source_handle_from_op_record(applied[0]) == "1BD9"


def test_translate_relink_records_maps_census_to_rebuilt():
    records = [{
        "index": 5, "native_op": patch_engine._RELINK_NATIVE_OP,
        "args": {"block_name": "DEF_A", "hatch_handle": "1BD8",
                 "loops_source_handles": [["1BD9"], ["1BDA", "1BDB"]]},
    }]
    ledger = {"pairs": {"1BD8": "7621", "1BD9": "7622",
                        "1BDA": "7623", "1BDB": "7624"}}

    translated, reason = patch_engine._translate_relink_records(records, ledger)

    assert reason is None
    args = translated[0]["args"]
    assert args["hatch_handle"] == "7621"
    assert args["loops_source_handles"] == [["7622"], ["7623", "7624"]]
    # the original record's args must stay census-side (patch provenance)
    assert records[0]["args"]["hatch_handle"] == "1BD8"


def test_translate_relink_records_fail_loud_on_missing_handle():
    records = [{
        "index": 7, "native_op": patch_engine._RELINK_NATIVE_OP,
        "args": {"block_name": "DEF_A", "hatch_handle": "1BD8",
                 "loops_source_handles": [["DEAD"]]},
    }]
    ledger = {"pairs": {"1BD8": "7621"}}

    translated, reason = patch_engine._translate_relink_records(records, ledger)

    assert translated is None
    assert "ASSOC_RELINK_UNRESOLVED" in reason
    assert "DEAD" in reason


def test_translate_leaves_non_relink_records_alone():
    rec = {"index": 0, "native_op": "write.block.append_entity",
           "args": {"block_name": "DEF_A"}}

    translated, reason = patch_engine._translate_relink_records([rec], {"pairs": {}})

    assert reason is None
    assert translated[0] is rec


# ---- patch_batch_planner: relink barrier --------------------------------------


def _append_op(name="DEF_A"):
    return {"operation": "append_block_entity", "args": {"block_name": name}}


def _relink_op(handle="1BD8"):
    return {"operation": "relink_hatch_assoc",
            "args": {"block_name": "DEF_A", "hatch_handle": handle,
                     "loops_source_handles": [["1BD9"]]}}


def test_planner_never_mixes_relink_with_appends():
    ops = [_append_op() for _ in range(5)] + [_relink_op("H%d" % i) for i in range(3)]

    plan = patch_batch_planner.plan_batches(ops, max_ops_per_batch=100)

    assert patch_batch_planner.validate_plan(plan, ops) == []
    for batch in plan["batches"]:
        kinds = {ops[i]["operation"] == "relink_hatch_assoc"
                 for i in batch["op_indices"]}
        assert len(kinds) == 1
    # order preserved: relink batch(es) strictly after append batches
    flat = [i for b in plan["batches"] for i in b["op_indices"]]
    assert flat == list(range(len(ops)))


def test_validate_plan_flags_mixed_relink_batch():
    ops = [_append_op(), _relink_op()]
    plan = patch_batch_planner.plan_batches(ops, max_ops_per_batch=100)
    # sabotage: merge everything into one batch
    bad = dict(plan)
    bad["batches"] = [{"batch_id": "b000", "op_indices": [0, 1], "op_count": 2}]
    bad["totals"] = {"op_count": 2, "batch_count": 1}

    violations = patch_batch_planner.validate_plan(bad, ops)

    assert any("mixes relink" in v for v in violations)


# ---- registry lockstep ---------------------------------------------------------


def test_native_write_op_map_lockstep_with_registry():
    # Fails loudly if write.block.relink_hatch_assoc is missing from
    # config/operations.v2.json or not implemented on the native lane.
    patch_engine.assert_native_write_op_map_lockstep(
        patch_engine.NATIVE_WRITE_OP_MAP)
