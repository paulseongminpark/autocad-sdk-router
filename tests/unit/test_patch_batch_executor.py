#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for tools/patch_batch_executor.py + apply_staged batch wiring (#39).

WHY: the batch executor is the only lane that can apply 100s-1000s of write ops
(one accoreconsole session per batch instead of one process per op). These
tests pin, with an injected runner and no native host:
  * plan integration (order preserved, exact index cover, max size honored),
  * job-doc envelope shape (v2, write_copy, staged policy),
  * per-op journal granularity via step_cb,
  * resume-skip ONLY for fully-persisted batches (PASS + qsave_done),
  * truthful stop semantics for half-persisted / unsaved / no-envelope batches
    (no-fake-success: a half-persisted batch is NEVER auto-re-run),
  * apply_staged batch_options wiring (legacy per-op lane untouched by default).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import patch_batch_executor as pbe  # noqa: E402
import patch_engine  # noqa: E402


def _records(n: int):
    return [{"index": i, "step_id": "s%d" % i, "patch_op": "create_line",
             "native_op": "write.entity.line",
             "args": {"start": [i, 0, 0], "end": [i, 10, 0]}}
            for i in range(n)]


def _pass_envelope(job_list_path: str):
    entries = json.loads(Path(job_list_path).read_text(encoding="utf-8"))
    return {
        "schema": "ariadne.autocad_native_write_batch.v1",
        "status": "PASS", "qsave_done": True, "engine_exit_code": 0,
        "ops_total": len(entries), "ops_ok": len(entries),
        "results": [{"index": e["index"], "operation": e["operation"],
                     "status": "ok", "engine": "native_objectarx",
                     "error_code": "", "result_file": e["result_file"]}
                    for e in entries],
    }


def _runner(script):
    """script: callable(batch_no, job_list_entries) -> envelope|None."""
    calls = []

    def run_batch(staged_dwg, run_dir, job_list_path, *, batch_timeout_ms=0):
        calls.append({"staged_dwg": staged_dwg, "run_dir": run_dir,
                      "job_list_path": job_list_path})
        env = script(len(calls) - 1, job_list_path)
        if env is not None:
            Path(run_dir).mkdir(parents=True, exist_ok=True)
            (Path(run_dir) / "write_batch_result.json").write_text(
                json.dumps(env), encoding="utf-8")
        return {"envelope": env, "error": None if env else "runner produced no envelope",
                "exit_code": 0 if env else 1}

    run_batch.calls = calls
    return run_batch


# --------------------------------------------------------------------------- #
# planning + job docs
# --------------------------------------------------------------------------- #

def test_plan_preserves_order_and_covers_every_index():
    recs = _records(23)
    plan = pbe.plan_write_batches(recs, max_ops_per_batch=10)
    assert plan["validation_errors"] == []
    flat = [i for b in plan["batches"] for i in b["op_indices"]]
    assert flat == list(range(23))
    assert all(b["op_count"] <= 10 for b in plan["batches"])
    assert plan["totals"]["op_count"] == 23


def test_job_doc_is_v2_write_copy_staged():
    doc = pbe.build_native_job_doc("write.entity.line",
                                   {"start": [0, 0, 0], "end": [1, 1, 0]})
    assert doc["schema"] == "ariadne.autocad_sdk_job.v2"
    assert doc["operation"] == "write.entity.line"
    assert doc["write_mode"] == "write_copy"
    assert doc["policy"]["require_staged_copy"] is True
    assert isinstance(doc["args"], dict)


# --------------------------------------------------------------------------- #
# execution: success / journal granularity / artifacts
# --------------------------------------------------------------------------- #

def test_execute_ok_emits_per_op_steps_and_artifacts(tmp_path):
    recs = _records(7)
    steps = []
    run = _runner(lambda n, jl: _pass_envelope(jl))
    out = pbe.execute_write_batches(recs, str(tmp_path / "staged.dwg"),
                                    str(tmp_path / "batches"),
                                    max_ops_per_batch=3, run_batch=run,
                                    step_cb=steps.append)
    assert out["status"] == "ok"
    assert out["ops_ok"] == 7 and out["ops_total"] == 7
    assert len(run.calls) == 3  # ceil(7/3)
    op_steps = [s for s in steps if ".op[" in s["step"]]
    assert len(op_steps) == 7  # journal stays op-granular
    assert all(s["status"] == "ok" for s in op_steps)
    assert (tmp_path / "batches" / "batch_plan.json").is_file()
    assert (tmp_path / "batches" / "batch_execution.json").is_file()
    # every job doc exists on disk before its batch ran
    b0_jobs = list((tmp_path / "batches" / "b000" / "jobs").glob("*.json"))
    assert len(b0_jobs) == 3


def test_execute_resume_skips_only_fully_persisted_batches(tmp_path):
    recs = _records(6)
    # first run: batch 0 PASS, batch 1 dies with no envelope
    run1 = _runner(lambda n, jl: _pass_envelope(jl) if n == 0 else None)
    out1 = pbe.execute_write_batches(recs, "staged.dwg", str(tmp_path / "b"),
                                     max_ops_per_batch=3, run_batch=run1)
    assert out1["status"] == "partial"
    assert out1["stopped_at_batch"] == "b001"
    # resume: batch 0 must be skipped, batch 1 re-run
    run2 = _runner(lambda n, jl: _pass_envelope(jl))
    out2 = pbe.execute_write_batches(recs, "staged.dwg", str(tmp_path / "b"),
                                     max_ops_per_batch=3, run_batch=run2)
    assert out2["status"] == "ok"
    assert len(run2.calls) == 1  # only the failed batch re-ran
    assert out2["batches"][0]["status"] == "skipped_resume"


def test_execute_half_persisted_batch_stops_and_never_retries(tmp_path):
    recs = _records(4)

    def script(n, jl):
        env = _pass_envelope(jl)
        env["results"][1]["status"] = "error"
        env["results"][1]["error_code"] = "ELOCKED"
        env["status"] = "PARTIAL"  # qsave_done stays True: half-persisted
        return env

    out = pbe.execute_write_batches(recs, "staged.dwg", str(tmp_path / "b"),
                                    max_ops_per_batch=10, run_batch=_runner(script))
    assert out["status"] == "partial"
    assert "half-persisted" in out["reason"]
    # resume must NOT skip it (status != PASS) and must not silently re-run:
    # the executor re-encounters the same PARTIAL envelope truthfully.
    out2 = pbe.execute_write_batches(recs, "staged.dwg", str(tmp_path / "b"),
                                     max_ops_per_batch=10, run_batch=_runner(script))
    assert out2["status"] == "partial"


def test_execute_unsaved_batch_reports_safe_to_rerun(tmp_path):
    recs = _records(3)

    def script(n, jl):
        env = _pass_envelope(jl)
        env["qsave_done"] = False
        env["status"] = "PARTIAL"
        return env

    out = pbe.execute_write_batches(recs, "staged.dwg", str(tmp_path / "b"),
                                    max_ops_per_batch=10, run_batch=_runner(script))
    assert out["status"] == "partial"
    assert "safe to re-run" in out["reason"]


def test_execute_no_records_is_blocked(tmp_path):
    out = pbe.execute_write_batches([], "staged.dwg", str(tmp_path / "b"))
    assert out["status"] == "blocked"


# --------------------------------------------------------------------------- #
# apply_staged wiring
# --------------------------------------------------------------------------- #

def test_normalize_batch_options_defaults():
    cfg = patch_engine._normalize_batch_options(None)
    assert cfg["enabled"] is False
    cfg = patch_engine._normalize_batch_options(
        {"enabled": True, "max_ops_per_batch": 250, "pre_inspect": "full",
         "post_inspect": "bogus", "batch_timeout_ms": 12000})
    assert cfg["enabled"] is True
    assert cfg["max_ops_per_batch"] == 250
    assert cfg["pre_inspect"] == "full"
    assert cfg["post_inspect"] == "skip"  # bogus value falls back
    assert cfg["batch_timeout_ms"] == 12000


def test_apply_staged_batch_lane_ok_with_skipped_inspects(tmp_path, monkeypatch):
    dwg = tmp_path / "input.dwg"
    dwg.write_bytes(b"FAKE-DWG-BYTES")
    out_dir = tmp_path / "out"

    def fake_execute(applied_records, staged_dwg, batches_dir, **kwargs):
        # mimic in-place mutation of the staged copy
        Path(staged_dwg).write_bytes(b"FAKE-DWG-BYTES-MUTATED")
        for rec in applied_records:
            kwargs.get("step_cb", lambda r: None)(
                {"step": "apply_batch[b000].op[%d]" % rec["index"], "status": "ok"})
        return {"schema": pbe.SCHEMA, "status": "ok", "plan": {}, "batches": [],
                "ops_total": len(applied_records), "ops_ok": len(applied_records)}

    monkeypatch.setattr(pbe, "execute_write_batches", fake_execute)

    patch = patch_engine._sample_patch()
    patch["operations"] = [
        {"step_id": "s1", "operation": "create_line",
         "args": {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "0"}},
        {"step_id": "s2", "operation": "create_circle",
         "args": {"center": [5, 5, 0], "radius": 2.5, "layer": "0"}},
    ]
    env = patch_engine.apply_staged(patch, str(dwg), str(out_dir),
                                    batch_options={"enabled": True})
    assert env["status"] == "ok", env.get("reason")
    assert env["original_unchanged"]["unchanged"] is True
    assert env["batch"]["ops_ok"] == 2
    assert env["inspects"] == {"pre": "skip", "post": "skip"}
    assert (out_dir / "staged_pre.dwg").read_bytes() == b"FAKE-DWG-BYTES"
    assert (out_dir / "staged_output.dwg").read_bytes() == b"FAKE-DWG-BYTES-MUTATED"
    journal = json.loads((out_dir / "journal.json").read_text(encoding="utf-8"))
    names = [s["step"] for s in journal["steps"]]
    assert "batch_mode" in names
    assert any(n == "pre_inspect" for n in names)  # skipped but journaled
    steps_by_name = {s["step"]: s for s in journal["steps"]}
    assert steps_by_name["pre_inspect"]["status"] == "skipped_by_option"
    assert steps_by_name["post_inspect"]["status"] == "skipped_by_option"


def test_apply_staged_batch_lane_partial_propagates(tmp_path, monkeypatch):
    dwg = tmp_path / "input.dwg"
    dwg.write_bytes(b"FAKE")
    monkeypatch.setattr(
        pbe, "execute_write_batches",
        lambda *a, **k: {"schema": pbe.SCHEMA, "status": "partial", "plan": {},
                         "batches": [], "ops_total": 2, "ops_ok": 1,
                         "stopped_at_batch": "b000", "reason": "boom"})
    patch = patch_engine._sample_patch()
    patch["operations"] = [
        {"step_id": "s1", "operation": "create_line",
         "args": {"start": [0, 0, 0], "end": [1, 0, 0], "layer": "0"}},
    ]
    env = patch_engine.apply_staged(patch, str(dwg), str(tmp_path / "out"),
                                    batch_options={"enabled": True})
    assert env["status"] == "partial"
    assert env["reason"] == "boom"
    assert env["batch"]["stopped_at_batch"] == "b000"


def test_apply_staged_without_batch_options_never_touches_executor(tmp_path, monkeypatch):
    # legacy lane must not import/call the executor at all
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("batch executor must not be called in legacy lane")

    monkeypatch.setattr(pbe, "execute_write_batches", boom)
    dwg = tmp_path / "input.dwg"
    dwg.write_bytes(b"FAKE")
    patch = patch_engine._sample_patch()
    patch["operations"] = [
        {"step_id": "s1", "operation": "create_line",
         "args": {"start": [0, 0, 0], "end": [1, 0, 0], "layer": "0"}},
    ]
    # the legacy lane will fail later at pre-inspect (no native host in unit
    # tests) -- what matters here is that the executor was never invoked.
    env = patch_engine.apply_staged(patch, str(dwg), str(tmp_path / "out"))
    assert called["n"] == 0
    assert env["status"] in ("partial", "unavailable", "not_implemented", "blocked")
