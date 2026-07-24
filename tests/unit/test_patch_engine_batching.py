# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import types
from pathlib import Path

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.join(os.path.dirname(_THIS_DIR), "..", "tools")
_TOOLS_DIR = os.path.normpath(_TOOLS_DIR)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

pe = importlib.import_module("patch_engine")


def _make_patch(original_path: Path, out_dir: Path, operations: list[dict]) -> dict:
    return {
        "schema": pe.PATCH_SCHEMA_ID,
        "patch_id": "batch-test-0001",
        "target_dwg": {
            "staged_path": str(out_dir / "staged_input.dwg"),
            "original_path": str(original_path),
        },
        "operations": operations,
        "postconditions": [{"subject": "entity_count", "op": "delta_ge", "value": 0}],
        "policy": {"staged_copy": True, "write_mode": "write_copy"},
    }


def _applied_records(operations: list[dict]) -> list[dict]:
    records = []
    for index, op in enumerate(operations):
        records.append({
            "index": index,
            "step_id": op.get("step_id"),
            "patch_op": op["operation"],
            "native_op": "native.%s" % op["operation"],
            "args": op.get("args", {}),
        })
    return records


class _FakeRunJob:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run_router_cad_job(self, staged_dwg, run_dir, operation, *,
                           intent="dwg", write_mode="read",
                           job_path=None, timeout=600):
        self.calls.append({
            "staged_dwg": staged_dwg,
            "run_dir": run_dir,
            "operation": operation,
            "write_mode": write_mode,
            "job_path": job_path,
            "timeout": timeout,
            "intent": intent,
        })
        run_dir_p = Path(run_dir)
        run_dir_p.mkdir(parents=True, exist_ok=True)
        stdout_path = run_dir_p / "stdout.txt"
        stderr_path = run_dir_p / "stderr.txt"
        stdout_path.write_text("{}", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        staged_used = run_dir_p / "router_stage.dwg"
        shutil.copy2(staged_dwg, staged_used)
        if write_mode in ("write_copy", "write_original", "live_edit"):
            with open(staged_used, "ab") as fh:
                fh.write(b"MUTATED")
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


def _wire_apply_success(monkeypatch, operations: list[dict]) -> _FakeRunJob:
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

    monkeypatch.setattr(pe, "_import_optional", _fake_import_optional)
    monkeypatch.setattr(pe, "_resolve_native_write_ops",
                        lambda patch: (_applied_records(operations), [], None))
    monkeypatch.setattr(pe, "_native_job_doc",
                        lambda native_op, args: {"operation": native_op, "args": args})
    monkeypatch.setattr(pe, "_native_full_ir", _fake_native_full_ir)
    monkeypatch.setattr(pe, "_call_validator", lambda *args, **kwargs: {
        "ok": True,
        "report": {"status": "pass"},
        "passed_kwargs": {},
        "diff_aware": True,
    })
    return run_job


def _make_batch_runner(*, missing_end_indices=(), missing_result_indices=()):
    calls: list[dict] = []
    missing_end = set(missing_end_indices)
    missing_result = set(missing_result_indices)

    def _runner(run_job, staged_dwg: str, batch_dir: str, batch_id: str, op_records: list[dict]):
        calls.append({
            "batch_id": batch_id,
            "indices": [record["index"] for record in op_records],
        })
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
            if record["index"] not in missing_result:
                result_path.write_text(json.dumps({
                    "status": "ok",
                    "engine": "native_objectarx",
                }), encoding="utf-8")
            if record["index"] not in missing_end:
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

    return _runner, calls


def test_batch_size_none_skips_planner_and_batch_runner(monkeypatch, tmp_path):
    operations = [
        {"step_id": "s1", "operation": "create_line", "args": {"start": [0, 0, 0], "end": [1, 0, 0]}},
    ]
    run_job = _wire_apply_success(monkeypatch, operations)
    original = tmp_path / "input.dwg"
    original.write_bytes(b"ORIGINAL")
    out_dir = tmp_path / "run"
    patch = _make_patch(original, out_dir, operations)

    plan_called = False

    def _unexpected_plan(*args, **kwargs):
        nonlocal plan_called
        plan_called = True
        raise AssertionError("plan_batches should not run when batch_size=None")

    monkeypatch.setattr(pe.patch_batch_planner, "plan_batches", _unexpected_plan)
    monkeypatch.setattr(pe, "_run_batched_native_ops",
                        lambda *args, **kwargs: pytest.fail("_run_batched_native_ops should not run"))

    result = pe.apply_staged(patch, str(original), str(out_dir), batch_size=None)

    assert result["status"] == "ok"
    assert plan_called is False
    assert [call["write_mode"] for call in run_job.calls] == ["read", "write_copy", "read"]


def test_batched_path_uses_planner_and_all_ok_results(monkeypatch, tmp_path):
    operations = [
        {"step_id": "s0", "operation": "create_line", "args": {}},
        {"step_id": "s1", "operation": "create_circle", "args": {}},
        {"step_id": "s2", "operation": "create_block", "args": {"name": "DOOR"}},
        {"step_id": "s3", "operation": "append_block_entity", "args": {"block_name": "DOOR"}},
        {"step_id": "s4", "operation": "append_block_entity", "args": {"block_name": "DOOR"}},
        {"step_id": "s5", "operation": "create_text", "args": {}},
        {"step_id": "s6", "operation": "create_arc", "args": {}},
    ]
    _wire_apply_success(monkeypatch, operations)
    original = tmp_path / "input.dwg"
    original.write_bytes(b"ORIGINAL")
    out_dir = tmp_path / "run"
    patch = _make_patch(original, out_dir, operations)

    orig_plan_batches = pe.patch_batch_planner.plan_batches
    orig_validate_plan = pe.patch_batch_planner.validate_plan
    planner_calls = []
    validate_calls = []

    def _plan_batches(ops, *, max_ops_per_batch):
        planner_calls.append({
            "ops": [op["operation"] for op in ops],
            "max_ops_per_batch": max_ops_per_batch,
        })
        return orig_plan_batches(ops, max_ops_per_batch=max_ops_per_batch)

    def _validate_plan(plan, ops):
        validate_calls.append({
            "batch_ids": [batch["batch_id"] for batch in plan["batches"]],
            "op_count": len(ops),
        })
        return orig_validate_plan(plan, ops)

    batch_runner, batch_calls = _make_batch_runner()
    monkeypatch.setattr(pe.patch_batch_planner, "plan_batches", _plan_batches)
    monkeypatch.setattr(pe.patch_batch_planner, "validate_plan", _validate_plan)
    monkeypatch.setattr(pe, "_run_batched_native_ops", batch_runner)

    result = pe.apply_staged(patch, str(original), str(out_dir), batch_size=3)

    assert result["status"] == "ok"
    assert result["batch_size"] == 3
    assert result["batch_count"] == 3
    assert [row["status"] for row in result["op_results"]] == ["ok"] * 7
    assert planner_calls == [{
        "ops": [op["operation"] for op in operations],
        "max_ops_per_batch": 3,
    }]
    assert validate_calls == [{"batch_ids": ["b000", "b001", "b002"], "op_count": 7}]
    assert [call["indices"] for call in batch_calls] == [[0, 1], [2, 3, 4], [5, 6]]

    journal = json.loads((out_dir / "journal.json").read_text(encoding="utf-8"))
    batch_steps = [step for step in journal["steps"] if step["step"].startswith("apply_batch[")]
    assert len(batch_steps) == 3
    assert all(step.get("elapsed_seconds") == 0.25 for step in batch_steps)


def test_batched_path_marks_aborted_batch_and_upstream_ops(monkeypatch, tmp_path):
    operations = [
        {"step_id": "s0", "operation": "create_line", "args": {}},
        {"step_id": "s1", "operation": "create_circle", "args": {}},
        {"step_id": "s2", "operation": "create_arc", "args": {}},
    ]
    _wire_apply_success(monkeypatch, operations)
    original = tmp_path / "input.dwg"
    original.write_bytes(b"ORIGINAL")
    out_dir = tmp_path / "run"
    patch = _make_patch(original, out_dir, operations)

    batch_runner, _calls = _make_batch_runner(missing_end_indices={1})
    monkeypatch.setattr(pe, "_run_batched_native_ops", batch_runner)

    result = pe.apply_staged(patch, str(original), str(out_dir), batch_size=10)

    assert result["status"] == "partial"
    assert result["batch_count"] == 1
    assert [row["status"] for row in result["op_results"]] == ["ok", "failed", "failed"]
    assert result["op_results"][1]["reason"] == "batch_aborted_before_end_marker"
    assert result["op_results"][2]["reason"] == "batch_aborted_upstream"


def test_batched_path_fails_closed_when_ok_marker_has_no_result_file(monkeypatch, tmp_path):
    operations = [
        {"step_id": "s0", "operation": "create_line", "args": {}},
        {"step_id": "s1", "operation": "create_circle", "args": {}},
    ]
    _wire_apply_success(monkeypatch, operations)
    original = tmp_path / "input.dwg"
    original.write_bytes(b"ORIGINAL")
    out_dir = tmp_path / "run"
    patch = _make_patch(original, out_dir, operations)

    batch_runner, _calls = _make_batch_runner(missing_result_indices={0})
    monkeypatch.setattr(pe, "_run_batched_native_ops", batch_runner)

    result = pe.apply_staged(patch, str(original), str(out_dir), batch_size=10)

    assert result["status"] == "partial"
    assert result["op_results"][0]["status"] == "failed"
    assert result["op_results"][0]["reason"] == "marker_result_mismatch:missing_result_file"
    assert result["op_results"][1]["reason"] == "batch_aborted_upstream"


def test_batched_path_raises_when_validate_plan_reports_violations(tmp_path, monkeypatch):
    operations = [
        {"step_id": "s0", "operation": "create_line", "args": {}},
    ]
    original = tmp_path / "input.dwg"
    original.write_bytes(b"ORIGINAL")
    out_dir = tmp_path / "run"
    patch = _make_patch(original, out_dir, operations)

    monkeypatch.setattr(pe.patch_batch_planner, "plan_batches", lambda *args, **kwargs: {
        "schema": "ariadne.patch_batch_plan.v1",
        "batches": [],
        "atomic_groups": [],
        "totals": {"op_count": 1, "batch_count": 0},
        "max_ops_per_batch": 3,
    })
    monkeypatch.setattr(pe.patch_batch_planner, "validate_plan",
                        lambda plan, ops: ["x"])

    with pytest.raises(RuntimeError, match="invalid native batch plan: x"):
        pe.apply_staged(patch, str(original), str(out_dir), batch_size=3)
