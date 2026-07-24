from __future__ import annotations

import copy
import json
import os
import sys

import pytest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from search.repair_search import RepairCandidate, default_gate, dfs_repair_search


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


def _find_block(ir, name: str):
    return next(b for b in ir["block_definitions"] if b["name"] == name)


def _set_line_end(ir, block_name: str, handle: str, end):
    block = _find_block(ir, block_name)
    for ent in block["def_entities"]:
        if ent["handle"] == handle:
            ent["geometry"]["end"] = list(end)
            return
    raise KeyError(handle)


def _set_circle_center(ir, block_name: str, handle: str, center):
    block = _find_block(ir, block_name)
    for ent in block["def_entities"]:
        if ent["handle"] == handle:
            ent["geometry"]["center"] = list(center)
            return
    raise KeyError(handle)


def _census_and_post():
    line = _entity("L1", "LINE", "line", start=[0, 0, 0], end=[1, 0, 0])
    circle = _entity("C1", "CIRCLE", "circle", center=[2, 0, 0], radius=1.0)
    census = _ir(_block("W", copy.deepcopy(line), copy.deepcopy(circle)))

    bad_line = copy.deepcopy(line)
    bad_line["geometry"]["end"] = [9, 0, 0]
    post = _ir(_block("W", bad_line, copy.deepcopy(circle)))
    return census, post


def _candidate_fn(state, target_def):
    def fix_line(ir):
        out = copy.deepcopy(ir)
        _set_line_end(out, target_def, "L1", [1, 0, 0])
        return out

    def worsen_line(ir):
        out = copy.deepcopy(ir)
        _set_circle_center(out, target_def, "C1", [99, 99, 0])
        return out

    def noop(ir):
        return copy.deepcopy(ir)

    return [
        RepairCandidate("worsen", "break the matching circle", worsen_line, score=10.0),
        RepairCandidate("noop", "leave state unchanged", noop, score=5.0),
        RepairCandidate("fix", "restore line endpoint", fix_line, score=1.0),
    ]


def _bad_only_candidate_fn(state, target_def):
    def worsen_line(ir):
        out = copy.deepcopy(ir)
        _set_circle_center(out, target_def, "C1", [99, 99, 0])
        return out

    def noop(ir):
        return copy.deepcopy(ir)

    return [
        RepairCandidate("worsen", "break the matching circle", worsen_line, score=10.0),
        RepairCandidate("noop", "leave state unchanged", noop, score=5.0),
    ]


def test_dfs_repair_search_success_and_trace(tmp_path):
    census, post = _census_and_post()
    trace_path = tmp_path / "trace.jsonl"

    result = dfs_repair_search(
        census,
        post,
        "W",
        _candidate_fn,
        default_gate,
        max_steps=20,
        max_depth=3,
        trace_path=str(trace_path),
    )

    assert result["success"] is True
    final_verdict = default_gate(census, result["final_ir"], "W")
    assert final_verdict["clean"] is True

    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == result["steps_used"]
    records = [json.loads(line) for line in lines]
    assert all(isinstance(rec, dict) for rec in records)

    worsen_rows = [rec for rec in records if rec["candidate"] == "worsen"]
    assert worsen_rows, "expected worsening candidate in trace"
    assert any(rec["pruned"] for rec in worsen_rows)


def test_dfs_repair_search_budget_exhaustion(tmp_path):
    census, post = _census_and_post()
    trace_path = tmp_path / "budget_trace.jsonl"

    result = dfs_repair_search(
        census,
        post,
        "W",
        _bad_only_candidate_fn,
        default_gate,
        max_steps=1,
        max_depth=3,
        trace_path=str(trace_path),
    )

    assert result["success"] is False
    assert result["steps_used"] == 1
    assert result["best_diff0"] == default_gate(census, post, "W")["diff0"]

    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["candidate"] == "__root__"
