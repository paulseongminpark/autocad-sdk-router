# -*- coding: utf-8 -*-
"""#47: the canonical batched lane (batch_options) must harvest the census->
rebuilt handle ledger from per-op native result files (handle_map.json) and
translate relink-op census handles through it right before each batch's job
docs are written. These tests drive apply_staged through the REAL
patch_batch_executor with an injected run_router_write_batch (no native host).
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import types
from pathlib import Path

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.normpath(os.path.join(os.path.dirname(_THIS_DIR), "..", "tools"))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

pe = importlib.import_module("patch_engine")
pbe = importlib.import_module("patch_batch_executor")
run_job_mod = importlib.import_module("run_job")


def _make_patch(original_path: Path, out_dir: Path, operations: list[dict]) -> dict:
    return {
        "schema": pe.PATCH_SCHEMA_ID,
        "patch_id": "handle-map-test-0001",
        "target_dwg": {
            "staged_path": str(out_dir / "staged_input.dwg"),
            "original_path": str(original_path),
        },
        "operations": operations,
        "postconditions": [{"subject": "entity_count", "op": "delta_ge", "value": 0}],
        "policy": {"staged_copy": True, "write_mode": "write_copy"},
    }


def _applied_records(specs: list[dict]) -> list[dict]:
    """specs: [{patch_op, native_op, args, source_handle?}] -> resolver output."""
    records = []
    for index, spec in enumerate(specs):
        record = {
            "index": index,
            "step_id": "s%d" % index,
            "patch_op": spec["patch_op"],
            "native_op": spec["native_op"],
            "args": spec.get("args", {}),
        }
        if spec.get("source_handle") is not None:
            record["source_handle"] = spec["source_handle"]
        records.append(record)
    return records


def _make_write_batch_runner(payload_by_index: dict[int, dict]):
    """Fake run_job.run_router_write_batch: writes each op's native result file
    ({"result": {"status": "ok", ...payload...}}), mutates the staged DWG in
    place, and persists a PASS+qsave envelope (resume contract)."""

    def run_router_write_batch(staged_dwg, run_dir, job_list_path, *,
                               batch_timeout_ms=0):
        entries = json.loads(Path(job_list_path).read_text(encoding="utf-8"))
        for e in entries:
            payload = {"status": "ok"}
            payload.update(payload_by_index.get(e["index"], {}))
            Path(e["result_file"]).parent.mkdir(parents=True, exist_ok=True)
            Path(e["result_file"]).write_text(
                json.dumps({"result": payload}), encoding="utf-8")
        with open(staged_dwg, "ab") as fh:
            fh.write(b"BATCHED")
        env = {
            "schema": "ariadne.autocad_native_write_batch.v1",
            "status": "PASS", "qsave_done": True, "engine_exit_code": 0,
            "results": [{"index": e["index"], "operation": e["operation"],
                         "status": "ok", "error_code": "",
                         "result_file": e["result_file"]} for e in entries],
        }
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        (Path(run_dir) / "write_batch_result.json").write_text(
            json.dumps(env), encoding="utf-8")
        return {"envelope": env, "error": None, "exit_code": 0}

    return run_router_write_batch


def _wire_batched_apply(monkeypatch, specs: list[dict],
                        payload_by_index: dict[int, dict]) -> None:
    modules = {
        "ir_builder": types.SimpleNamespace(build_ir_from_database_graph=object()),
        "run_job": run_job_mod,
        "patch_batch_executor": pbe,
    }

    def _fake_import_optional(name: str):
        mod = modules.get(name)
        return mod, (None if mod is not None else "missing")

    monkeypatch.setattr(pe, "_import_optional", _fake_import_optional)
    monkeypatch.setattr(pe, "_resolve_native_write_ops",
                        lambda patch: (_applied_records(specs), [], None))
    monkeypatch.setattr(run_job_mod, "run_router_write_batch",
                        _make_write_batch_runner(payload_by_index))


def _apply(tmp_path, monkeypatch, specs, payload_by_index):
    original = tmp_path / "input.dwg"
    original.write_bytes(b"ORIGINAL")
    out_dir = tmp_path / "run"
    operations = [{"step_id": "s%d" % i, "operation": s["patch_op"],
                   "args": s.get("args", {})} for i, s in enumerate(specs)]
    patch = _make_patch(original, out_dir, operations)
    _wire_batched_apply(monkeypatch, specs, payload_by_index)
    result = pe.apply_staged(patch, str(original), str(out_dir),
                             batch_options={"enabled": True})
    return result, out_dir


def _append_spec(source_handle, block="DOOR"):
    return {"patch_op": "append_block_entity",
            "native_op": "write.block.append_entity",
            "args": {"block_name": block},
            "source_handle": source_handle}


def test_batched_apply_writes_handle_map_pairs(monkeypatch, tmp_path):
    result, out_dir = _apply(
        tmp_path, monkeypatch,
        [_append_spec("OLD_A"), _append_spec("OLD_B")],
        {0: {"new_handle": "NEW_A"}, 1: {"new_handle": "NEW_B"}})

    assert result["status"] == "ok", result.get("reason")
    assert json.loads((out_dir / "handle_map.json").read_text(encoding="utf-8")) == {
        "schema": pe.HANDLE_MAP_SCHEMA_ID,
        "pairs": {
            "OLD_A": "NEW_A",
            "OLD_B": "NEW_B",
        },
        "coverage": {
            "ops_with_source": 2,
            "ops_with_new_handle": 2,
            "mapped": 2,
        },
    }


def test_batched_apply_writes_empty_handle_map_when_source_handles_are_missing(
        monkeypatch, tmp_path):
    specs = [
        _append_spec(None),
        {"patch_op": "create_block_simple",
         "native_op": "write.block.simple_create",
         "args": {"block_name": "DOOR"}, "source_handle": "OLD_B"},
    ]
    result, out_dir = _apply(
        tmp_path, monkeypatch, specs,
        {0: {"new_handle": "NEW_A"}, 1: {"names": ["DOOR"]}})

    assert result["status"] == "ok", result.get("reason")
    assert json.loads((out_dir / "handle_map.json").read_text(encoding="utf-8")) == {
        "schema": pe.HANDLE_MAP_SCHEMA_ID,
        "pairs": {},
        "coverage": {
            "ops_with_source": 1,
            "ops_with_new_handle": 1,
            "mapped": 0,
        },
    }


def test_batched_apply_translates_relink_census_handles_via_ledger(
        monkeypatch, tmp_path):
    # The planner's relink barrier puts the relink op in its OWN batch after
    # the appends, so the ledger the appends filled is complete before the
    # relink batch's job doc is written.
    specs = [
        _append_spec("OLD_H"),
        _append_spec("OLD_L1"),
        {"patch_op": "relink_hatch_assoc",
         "native_op": pe._RELINK_NATIVE_OP,
         "args": {"block_name": "B", "hatch_handle": "OLD_H",
                  "loops_source_handles": [["OLD_L1"]]}},
    ]
    result, out_dir = _apply(
        tmp_path, monkeypatch, specs,
        {0: {"new_handle": "NEW_H"}, 1: {"new_handle": "NEW_L1"}})

    assert result["status"] == "ok", result.get("reason")
    relink_job = (out_dir / "apply_batches" / "b001" / "jobs"
                  / "op_00002_write.block.relink_hatch_assoc.json")
    assert relink_job.is_file()
    job = json.loads(relink_job.read_text(encoding="utf-8"))
    assert job["args"]["hatch_handle"] == "NEW_H"
    assert job["args"]["loops_source_handles"] == [["NEW_L1"]]


def test_batched_apply_refuses_relink_with_unresolved_census_handle(
        monkeypatch, tmp_path):
    specs = [
        _append_spec("OLD_H"),
        {"patch_op": "relink_hatch_assoc",
         "native_op": pe._RELINK_NATIVE_OP,
         "args": {"block_name": "B", "hatch_handle": "OLD_H",
                  "loops_source_handles": [["OLD_MISSING"]]}},
    ]
    result, out_dir = _apply(
        tmp_path, monkeypatch, specs, {0: {"new_handle": "NEW_H"}})

    # the append batch persisted, so the pipeline stops truthfully as partial
    # -- never a fake relink against guessed object ids.
    assert result["status"] == "partial"
    assert "ASSOC_RELINK_UNRESOLVED" in (result.get("reason") or "")
    relink_job = (out_dir / "apply_batches" / "b001" / "jobs"
                  / "op_00001_write.block.relink_hatch_assoc.json")
    assert not relink_job.exists()
