# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import types
from pathlib import Path

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.normpath(os.path.join(os.path.dirname(_THIS_DIR), "..", "tools"))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

pe = importlib.import_module("patch_engine")


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


def _applied_records(operations: list[dict],
                     source_handles: list[str | None]) -> list[dict]:
    records = []
    for index, op in enumerate(operations):
        record = {
            "index": index,
            "step_id": op.get("step_id"),
            "patch_op": op["operation"],
            "native_op": "native.%s" % op["operation"],
            "args": op.get("args", {}),
        }
        source_handle = source_handles[index]
        if source_handle is not None:
            record["source_handle"] = source_handle
        records.append(record)
    return records


class _FakeRunJob:
    def run_router_cad_job(self, staged_dwg, run_dir, operation, *,
                           intent="dwg", write_mode="read",
                           job_path=None, timeout=600):
        run_dir_p = Path(run_dir)
        run_dir_p.mkdir(parents=True, exist_ok=True)
        stdout_path = run_dir_p / "stdout.txt"
        stderr_path = run_dir_p / "stderr.txt"
        stdout_path.write_text("{}", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        staged_used = run_dir_p / "router_stage.dwg"
        shutil.copy2(staged_dwg, staged_used)
        result_json = run_dir_p / "result.json"
        result_json.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        return {
            "command": ["fake"],
            "exit_code": 0,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "envelope": {"status": "ok"},
            "result_json": str(result_json),
            "result": {"status": "ok"},
            "staged_used": str(staged_used),
            "timed_out": False,
            "error": None,
            "job_path": job_path,
            "timeout": timeout,
            "intent": intent,
            "operation": operation,
            "write_mode": write_mode,
        }


def _fake_native_full_ir(_ir_builder, run_res, staged_path, original_path, ir_out_path, phase):
    Path(ir_out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(ir_out_path).write_text(json.dumps({
        "phase": phase,
        "source": staged_path,
        "original": original_path,
        "entities": [],
    }), encoding="utf-8")
    return {
        "ok": True,
        "ir_path": ir_out_path,
        "entity_count": 0,
        "stdout": run_res.get("stdout_path"),
        "stderr": run_res.get("stderr_path"),
        "exit_code": run_res.get("exit_code"),
    }


def _wire_apply_success(monkeypatch, operations: list[dict],
                        source_handles: list[str | None]) -> None:
    run_job = _FakeRunJob()
    modules = {
        "ir_builder": types.SimpleNamespace(build_ir_from_database_graph=object()),
        "run_job": run_job,
        "cad_diff": types.SimpleNamespace(
            compute_diff=lambda pre_ir, post_ir: {"summary": {"by_type": {}}}
        ),
        "validator": types.SimpleNamespace(validate_target=object()),
    }

    def _fake_import_optional(name: str):
        mod = modules.get(name)
        return mod, (None if mod is not None else "missing")

    def _plan_batches(ops, *, max_ops_per_batch):
        return {
            "schema": "ariadne.patch_batch_plan.v1",
            "batches": [{
                "batch_id": "b000",
                "op_indices": list(range(len(ops))),
            }],
            "atomic_groups": [],
            "totals": {
                "op_count": len(ops),
                "batch_count": 1,
            },
            "max_ops_per_batch": max_ops_per_batch,
        }

    monkeypatch.setattr(pe, "_import_optional", _fake_import_optional)
    monkeypatch.setattr(pe, "_resolve_native_write_ops",
                        lambda patch: (_applied_records(operations, source_handles), [], None))
    monkeypatch.setattr(pe, "_native_full_ir", _fake_native_full_ir)
    monkeypatch.setattr(pe, "_call_validator", lambda *args, **kwargs: {
        "ok": True,
        "report": {"status": "pass"},
        "passed_kwargs": {},
        "diff_aware": True,
    })
    monkeypatch.setattr(pe.patch_batch_planner, "plan_batches", _plan_batches)
    monkeypatch.setattr(pe.patch_batch_planner, "validate_plan",
                        lambda plan, ops: [])


def _make_batch_runner(result_payloads: dict[int, dict]):
    def _runner(run_job, staged_dwg: str, batch_dir: str, batch_id: str, op_records: list[dict]):
        batch_dir_p = Path(batch_dir)
        batch_dir_p.mkdir(parents=True, exist_ok=True)
        results_dir = batch_dir_p / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = batch_dir_p / "stdout.txt"
        stderr_path = batch_dir_p / "stderr.txt"
        staged_used = batch_dir_p / "staged_step_input.dwg"
        shutil.copy2(staged_dwg, staged_used)
        with open(staged_used, "ab") as fh:
            fh.write(b"BATCHED")

        lines = []
        result_paths = {}
        for seq, record in enumerate(op_records):
            marker_id = record["batch_marker_id"]
            lines.append("ARIADNE_OP_START %s" % marker_id)
            result_path = results_dir / ("%02d_%s.json" % (seq, marker_id))
            result_paths[marker_id] = str(result_path)
            result_obj = {"status": "ok"}
            result_obj.update(result_payloads.get(record["index"], {}))
            result_path.write_text(json.dumps({"result": result_obj}), encoding="utf-8")
            lines.append("ARIADNE_OP_END %s STATUS=OK" % marker_id)

        stdout_path.write_text("\n".join(lines), encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return {
            "command": ["fake-batch"],
            "exit_code": 0,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "router_stdout_path": str(stdout_path),
            "router_stderr_path": str(stderr_path),
            "staged_used": str(staged_used),
            "timed_out": False,
            "error": None,
            "elapsed_seconds": 0.25,
            "script_timeout_ms": 600000,
            "result_paths": result_paths,
        }

    return _runner


def test_batched_apply_writes_handle_map_pairs(monkeypatch, tmp_path):
    operations = [
        {"step_id": "s0", "operation": "append_block_entity", "args": {"block_name": "DOOR"}},
        {"step_id": "s1", "operation": "append_block_entity", "args": {"block_name": "DOOR"}},
    ]
    original = tmp_path / "input.dwg"
    original.write_bytes(b"ORIGINAL")
    out_dir = tmp_path / "run"
    patch = _make_patch(original, out_dir, operations)

    _wire_apply_success(monkeypatch, operations, ["OLD_A", "OLD_B"])
    monkeypatch.setattr(pe, "_run_batched_native_ops", _make_batch_runner({
        0: {"new_handle": "NEW_A"},
        1: {"new_handle": "NEW_B"},
    }))

    result = pe.apply_staged(patch, str(original), str(out_dir), batch_size=10)

    assert result["status"] == "ok"
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
    operations = [
        {"step_id": "s0", "operation": "append_block_entity", "args": {"block_name": "DOOR"}},
        {"step_id": "s1", "operation": "create_block", "args": {"name": "DOOR"}},
    ]
    original = tmp_path / "input.dwg"
    original.write_bytes(b"ORIGINAL")
    out_dir = tmp_path / "run"
    patch = _make_patch(original, out_dir, operations)

    _wire_apply_success(monkeypatch, operations, [None, "OLD_B"])
    monkeypatch.setattr(pe, "_run_batched_native_ops", _make_batch_runner({
        0: {"new_handle": "NEW_A"},
        1: {"names": ["DOOR"]},
    }))

    result = pe.apply_staged(patch, str(original), str(out_dir), batch_size=10)

    assert result["status"] == "ok"
    assert json.loads((out_dir / "handle_map.json").read_text(encoding="utf-8")) == {
        "schema": pe.HANDLE_MAP_SCHEMA_ID,
        "pairs": {},
        "coverage": {
            "ops_with_source": 1,
            "ops_with_new_handle": 1,
            "mapped": 0,
        },
    }
