# -*- coding: utf-8 -*-
"""apply_staged lane selection (#47): the per-op lane is the only path when
batch_options is absent, and it truthfully refuses relink ops (which need the
batched lane's handle ledger). The batched lane itself is covered by
test_patch_batch_executor.py and test_handle_map_harvest.py.
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import types
from pathlib import Path

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
            "native_op": op.get("native_op") or ("native.%s" % op["operation"]),
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


def test_per_op_lane_is_default_and_chains_read_write_read(monkeypatch, tmp_path):
    operations = [
        {"step_id": "s1", "operation": "create_line", "args": {"start": [0, 0, 0], "end": [1, 0, 0]}},
    ]
    run_job = _wire_apply_success(monkeypatch, operations)
    original = tmp_path / "input.dwg"
    original.write_bytes(b"ORIGINAL")
    out_dir = tmp_path / "run"
    patch = _make_patch(original, out_dir, operations)

    result = pe.apply_staged(patch, str(original), str(out_dir))

    assert result["status"] == "ok"
    assert [call["write_mode"] for call in run_job.calls] == ["read", "write_copy", "read"]


def test_per_op_lane_refuses_relink_and_points_at_batch_options(monkeypatch, tmp_path):
    operations = [
        {"step_id": "s0", "operation": "relink_hatch_assoc",
         "native_op": pe._RELINK_NATIVE_OP,
         "args": {"block_name": "B", "hatch_handle": "AA",
                  "loops_source_handles": [["BB"]]}},
    ]
    _wire_apply_success(monkeypatch, operations)
    original = tmp_path / "input.dwg"
    original.write_bytes(b"ORIGINAL")
    out_dir = tmp_path / "run"
    patch = _make_patch(original, out_dir, operations)

    result = pe.apply_staged(patch, str(original), str(out_dir))

    assert result["status"] == "blocked"
    assert "batch_options" in (result.get("reason") or "")
    assert "relink_hatch_assoc" in (result.get("reason") or "")
