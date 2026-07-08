from __future__ import annotations

import os
import sys

import pytest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import blockdef_diff
import ir_to_patch


def _insert(block_name: str, x: float = 0.0) -> dict:
    return {
        "handle": "ins_%s_%s" % (block_name, x),
        "layer": "0",
        "class": "AcDbBlockReference",
        "geometry": {"kind": "block_reference", "block_name": block_name, "position": [x, 0, 0]},
    }


def _line(handle: str) -> dict:
    return {
        "handle": handle,
        "layer": "0",
        "geometry": {"kind": "line", "start": [0, 0, 0], "end": [1, 0, 0]},
    }


def _nested_ref(block_name: str, handle: str) -> dict:
    return {
        "handle": handle,
        "layer": "0",
        "geometry": {
            "kind": "block_reference",
            "block_name": block_name,
            "position": [0, 0, 0],
        },
    }


def _build_patch(ir: dict, patch_id: str = "anon"):
    return ir_to_patch.build_patch_from_ir(
        ir, {"staged_path": "s", "original_path": "o"}, patch_id)


def _block(name: str, *entities):
    return {"name": name, "handle": "H_%s" % (name,), "def_entities": list(entities)}


def _entity(handle: str, kind: str, **geometry):
    payload = {"kind": kind}
    payload.update(geometry)
    return {
        "handle": handle,
        "dxf_name": kind.upper(),
        "layer": "0",
        "space": "block",
        "geometry": payload,
    }


def _per_def(report: dict, name: str) -> dict:
    return next(row for row in report["per_def"] if row["name"] == name)


def test_anonymous_defs_emit_under_clone_names_and_record_provenance():
    ir = {
        "entities": [_insert("*U172")],
        "block_definitions": [
            {"name": "*U172", "handle": "U172", "anonymous": True,
             "def_entities": [_line("U172-L1"), _nested_ref("*U9", "U172-R1")]},
            {"name": "*U9", "handle": "U9", "anonymous": True,
             "def_entities": [_line("U9-L1")]},
        ],
    }

    patch, deferred = _build_patch(ir)

    assert deferred == []
    assert patch["anon_remap"] == {
        "*U172": "ARIADNE_ANON_U172",
        "*U9": "ARIADNE_ANON_U9",
    }
    assert [op["operation"] for op in patch["operations"]] == [
        "create_block", "append_block_entity",
        "create_block", "append_block_entity", "append_block_entity",
        "create_blockref",
    ]
    assert patch["operations"][0]["args"] == {
        "name": "ARIADNE_ANON_U9",
        "seed_line": 0,
    }
    assert patch["operations"][2]["args"] == {
        "name": "ARIADNE_ANON_U172",
        "seed_line": 0,
    }
    assert patch["operations"][4]["args"]["block_name"] == "ARIADNE_ANON_U172"
    assert patch["operations"][4]["args"]["entity"]["block_name"] == "ARIADNE_ANON_U9"
    assert patch["operations"][5]["args"]["block_name"] == "ARIADNE_ANON_U172"


def test_anonymous_clone_name_collision_gets_suffix():
    ir = {
        "entities": [_insert("*U172")],
        "block_definitions": [
            {"name": "*U172", "handle": "U172", "anonymous": True,
             "def_entities": [_line("U172-L1")]},
            {"name": "ARIADNE_ANON_U172", "handle": "NAMED",
             "def_entities": [_line("N-L1")]},
        ],
    }

    patch, deferred = _build_patch(ir)

    assert deferred == []
    assert patch["anon_remap"] == {"*U172": "ARIADNE_ANON_U172_2"}
    assert patch["operations"][0]["args"]["name"] == "ARIADNE_ANON_U172_2"
    assert patch["operations"][-1]["args"]["block_name"] == "ARIADNE_ANON_U172_2"


def test_missing_and_cycle_targets_still_defer_honestly():
    missing_ir = {
        "entities": [_insert("*MISSING")],
    }
    _patch, missing_deferred = _build_patch(missing_ir, patch_id="missing")
    assert missing_deferred == [{
        "index": 0,
        "handle": "ins_*MISSING_0.0",
        "kind": "block_reference",
        "reason": "no block_definitions entry for block_name '*MISSING'",
    }]

    cycle_ir = {
        "entities": [_insert("*U1")],
        "block_definitions": [
            {"name": "*U1", "handle": "U1", "anonymous": True,
             "def_entities": [_line("U1-L1"), _nested_ref("*U2", "U1-R1")]},
            {"name": "*U2", "handle": "U2", "anonymous": True,
             "def_entities": [_line("U2-L1"), _nested_ref("*U1", "U2-R1")]},
        ],
    }
    patch, cycle_deferred = _build_patch(cycle_ir, patch_id="cycle")
    reasons = [d.get("reason", "") for d in cycle_deferred]

    assert patch["operations"][-1]["args"]["block_name"] == "ARIADNE_ANON_U1"
    assert any("definition cycle detected at '*U1'" in reason for reason in reasons)
    assert any("not synthesized (anonymous/missing/cycle)" in reason for reason in reasons)


def test_blockdef_diff_name_map_matches_remapped_defs_and_nested_refs():
    ir_a = {
        "schema": "ariadne.dwg_graph_ir.v1",
        "block_definitions": [
            _block(
                "*U172",
                _entity("A1", "line", start=[0, 0, 0], end=[1, 0, 0]),
                _entity("A2", "block_reference", block_name="*U9", position=[0, 0, 0]),
            ),
            _block("*U9", _entity("B1", "line", start=[2, 0, 0], end=[3, 0, 0])),
        ],
    }
    ir_b = {
        "schema": "ariadne.dwg_graph_ir.v1",
        "block_definitions": [
            _block(
                "ARIADNE_ANON_U172",
                _entity("C1", "line", start=[0, 0, 0], end=[1, 0, 0]),
                _entity("C2", "block_reference",
                        block_name="ARIADNE_ANON_U9", position=[0, 0, 0]),
            ),
            _block("ARIADNE_ANON_U9", _entity("D1", "line", start=[2, 0, 0], end=[3, 0, 0])),
        ],
    }
    name_map = {
        "*U172": "ARIADNE_ANON_U172",
        "*U9": "ARIADNE_ANON_U9",
    }

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b, name_map=name_map)

    assert report["totals"]["diff0_total"] == 3
    assert _per_def(report, "*U172") == {
        "name": "*U172",
        "b_name": "ARIADNE_ANON_U172",
        "a_total": 2,
        "b_total": 2,
        "diff0": 2,
        "removed": 0,
        "added": 0,
        "modified": 0,
        "missing_side": None,
    }
    assert _per_def(report, "*U9") == {
        "name": "*U9",
        "b_name": "ARIADNE_ANON_U9",
        "a_total": 1,
        "b_total": 1,
        "diff0": 1,
        "removed": 0,
        "added": 0,
        "modified": 0,
        "missing_side": None,
    }


def test_blockdef_diff_without_name_map_stays_name_sensitive():
    ir_a = {"schema": "ariadne.dwg_graph_ir.v1",
            "block_definitions": [_block("*U172", _entity("A1", "line", start=[0, 0, 0], end=[1, 0, 0]))]}
    ir_b = {"schema": "ariadne.dwg_graph_ir.v1",
            "block_definitions": [_block("ARIADNE_ANON_U172",
                                         _entity("B1", "line", start=[0, 0, 0], end=[1, 0, 0]))]}

    report = blockdef_diff.diff_block_definitions(ir_a, ir_b)

    assert report["totals"]["diff0_total"] == 0
    assert _per_def(report, "*U172")["missing_side"] == "b"
    assert _per_def(report, "ARIADNE_ANON_U172")["missing_side"] == "a"
