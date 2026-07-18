#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_batch_executor -- staged WRITE batches in one accoreconsole session per
batch (#39). This wires tools/patch_batch_planner.py (previously a pure
prototype) into a real executor consumed by patch_engine.apply_staged.

WHY: apply_staged's per-op lane launches one accoreconsole process per
operation (staging copy + DWG open + one job + QSAVE + copy-back, ~10-20s per
op on a large drawing). That is correct for a handful of ops and unusable for
thousands. The router's smoke lane (Invoke-CadNativeBatchRoute) already proved
the mechanism: load .dbx/.crx once, then repeat (setenv job/result +
ARIADNE_NATIVE_JOB) inside ONE session -- 454 ops in ~1 min instead of ~75.
This module drives the WRITE variant of that lane
(autocad-router.ps1 -Action run-native-write-batch) which adds a single _QSAVE
after the batch, persisting every mutation into the engine-owned staged copy
IN PLACE so consecutive batches chain without a full-DWG copy per op.

PERSISTENCE / RESUME SEMANTICS (batch-granular, no-fake-success):
  * A batch persists all-or-nothing at the DWG level: mutations live in memory
    until the trailing _QSAVE. qsave_done=false => the staged DWG on disk is
    byte-wise unchanged by this batch => the batch is safe to re-run.
  * qsave_done=true + every op ok  => batch complete (resume skips it).
  * qsave_done=true + some ops NOT ok => the ok ops ARE persisted; re-running
    the whole batch would double-apply them. The executor STOPS there and
    reports exactly which ops failed; it never auto-re-runs a half-persisted
    batch. Fixing that state is a caller decision (new patch for the missing
    ops), not something to paper over.
  * Journal granularity stays per-op: every op's own result JSON is written by
    the native module the moment the op runs, and the executor emits one
    journal step per op via ``step_cb``.

The caller owns staging: ``staged_dwg`` must ALREADY be a writable staged copy
(patch_engine.apply_staged stages it and proves the original untouched via
sha256 before/after).
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Callable, Dict, List, Optional

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import patch_batch_planner  # noqa: E402
import patch_ops  # noqa: E402

SCHEMA = "ariadne.cad_patch.batch_execution.v1"

# Default batch size for write-only batches. The planner's own default (100)
# was sized for mixed/atomic-group smoke planning; pure write batches are
# cheap per-op once the session is up, so a larger default amortizes the
# ~10-20s accoreconsole startup further. Callers tune per drawing size.
DEFAULT_MAX_OPS_PER_BATCH = 500


def _sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name or "op")


def build_native_job_doc(native_op: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """ariadne.autocad_sdk_job.v2 envelope for one native write op.

    Mirrors patch_engine._native_job_doc (write_copy + staged policy) -- kept
    here as well so the executor is importable without patch_engine (the
    dependency direction is patch_engine -> executor).
    """
    return {
        "schema": "ariadne.autocad_sdk_job.v2",
        "operation": native_op,
        "write_mode": "write_copy",
        "policy": {"write_mode": "write_copy", "require_staged_copy": True,
                   "save": True, "lock_document": True},
        "source_agent": "patch_batch_executor",
        "args": patch_ops.build_job_args(native_op, args),
    }


def plan_write_batches(applied_records: List[Dict[str, Any]], *,
                       max_ops_per_batch: int = DEFAULT_MAX_OPS_PER_BATCH) -> Dict[str, Any]:
    """plan_batches over the resolved records, preserving op order + atomic
    groups (block-append runs). Batch ``op_indices`` index into
    ``applied_records`` positionally."""
    planner_ops = [{"operation": r.get("patch_op"), "args": r.get("args") or {}}
                   for r in applied_records]
    plan = patch_batch_planner.plan_batches(planner_ops,
                                            max_ops_per_batch=max_ops_per_batch)
    errors = patch_batch_planner.validate_plan(plan, planner_ops)
    plan["validation_errors"] = errors
    return plan


def _write_json(path: str, obj: Any) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    return path


def _load_cached_envelope(run_dir: str) -> Optional[Dict[str, Any]]:
    p = os.path.join(run_dir, "write_batch_result.json")
    if not os.path.isfile(p):
        return None
    try:
        with open(p, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def execute_write_batches(applied_records: List[Dict[str, Any]],
                          staged_dwg: str,
                          batches_dir: str, *,
                          max_ops_per_batch: int = DEFAULT_MAX_OPS_PER_BATCH,
                          run_batch: Optional[Callable[..., Dict[str, Any]]] = None,
                          resume: bool = True,
                          step_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
                          batch_timeout_ms: int = 0) -> Dict[str, Any]:
    """Execute every resolved write op against ``staged_dwg`` in planned batches.

    applied_records: patch_engine._resolve_native_write_ops output
        ([{index, step_id, patch_op, native_op, args}], order preserved).
    run_batch: injectable runner (tests); default run_job.run_router_write_batch.
        Called as run_batch(staged_dwg, run_dir, job_list_path,
                            batch_timeout_ms=...) -> {envelope, error, ...}.
    step_cb: receives one journal-step dict per op and per batch (op-granular
        journal contract).

    Returns {schema, status: ok|partial|blocked, plan, batches, ops_total,
             ops_ok, stopped_at_batch?, reason?}.
    """
    if run_batch is None:
        import run_job  # local sibling; deferred so tests can inject
        run_batch = run_job.run_router_write_batch

    def _emit(rec: Dict[str, Any]) -> None:
        if step_cb is not None:
            step_cb(rec)

    if not applied_records:
        return {"schema": SCHEMA, "status": "blocked", "plan": None, "batches": [],
                "ops_total": 0, "ops_ok": 0, "reason": "no applied records"}

    plan = plan_write_batches(applied_records, max_ops_per_batch=max_ops_per_batch)
    if plan.get("validation_errors"):
        return {"schema": SCHEMA, "status": "blocked", "plan": plan, "batches": [],
                "ops_total": len(applied_records), "ops_ok": 0,
                "reason": "batch plan failed validation: %s"
                          % "; ".join(plan["validation_errors"])}

    os.makedirs(batches_dir, exist_ok=True)
    _write_json(os.path.join(batches_dir, "batch_plan.json"), plan)

    batches_out: List[Dict[str, Any]] = []
    ops_ok_total = 0
    status = "ok"
    stopped_at = None
    reason = None

    for b in plan["batches"]:
        bid = b["batch_id"]
        bdir = os.path.join(batches_dir, bid)
        jobs_dir = os.path.join(bdir, "jobs")
        results_dir = os.path.join(bdir, "results")
        run_dir = os.path.join(bdir, "run")
        os.makedirs(jobs_dir, exist_ok=True)
        os.makedirs(results_dir, exist_ok=True)

        recs = [applied_records[i] for i in b["op_indices"]]

        # resume: a batch that previously finished FULLY (every op ok + QSAVE
        # proof) is skipped; anything less is NOT auto-skipped (see module doc).
        if resume:
            cached = _load_cached_envelope(run_dir)
            if cached and cached.get("status") == "PASS" and cached.get("qsave_done"):
                ops_ok_total += len(recs)
                batches_out.append({"batch_id": bid, "status": "skipped_resume",
                                    "ops": len(recs), "run_dir": run_dir})
                _emit({"step": "apply_batch[%s]" % bid, "status": "skipped_resume",
                       "op_count": len(recs), "run_dir": run_dir})
                continue

        job_list = []
        for rec in recs:
            gi = rec["index"]
            safe = "op_%05d_%s" % (gi, _sanitize(rec["native_op"]))
            job_file = os.path.join(jobs_dir, safe + ".json")
            result_file = os.path.join(results_dir, safe + ".json")
            _write_json(job_file, build_native_job_doc(rec["native_op"], rec["args"]))
            job_list.append({"index": gi, "operation": rec["native_op"],
                             "job_file": job_file, "result_file": result_file})
        job_list_path = _write_json(os.path.join(bdir, "job_list.json"), job_list)

        run_res = run_batch(staged_dwg, run_dir, job_list_path,
                            batch_timeout_ms=batch_timeout_ms)
        envelope = (run_res or {}).get("envelope") or {}
        env_status = envelope.get("status")
        qsave_done = bool(envelope.get("qsave_done"))
        per_op = {r.get("index"): r for r in (envelope.get("results") or [])
                  if isinstance(r, dict)}

        ops_ok = 0
        for rec in recs:
            r = per_op.get(rec["index"], {})
            op_status = r.get("status") or "no_result"
            if op_status == "ok":
                ops_ok += 1
            _emit({"step": "apply_batch[%s].op[%d]" % (bid, rec["index"]),
                   "status": op_status, "native_op": rec["native_op"],
                   "patch_op": rec.get("patch_op"), "step_id": rec.get("step_id"),
                   "error_code": r.get("error_code") or None,
                   "result_file": r.get("result_file")})
        ops_ok_total += ops_ok

        brec = {"batch_id": bid, "status": env_status or "no_envelope",
                "ops": len(recs), "ops_ok": ops_ok, "qsave_done": qsave_done,
                "run_dir": run_dir,
                "engine_exit_code": envelope.get("engine_exit_code"),
                "error": (run_res or {}).get("error")}
        batches_out.append(brec)
        _emit({"step": "apply_batch[%s]" % bid,
               "status": "pass" if env_status == "PASS" else (env_status or "unavailable"),
               "op_count": len(recs), "ops_ok": ops_ok, "qsave_done": qsave_done,
               "run_dir": run_dir, "reason": (run_res or {}).get("error")})

        if env_status == "PASS" and qsave_done:
            continue

        # Anything else stops the pipeline truthfully (see resume semantics).
        stopped_at = bid
        if qsave_done and ops_ok < len(recs):
            status = "partial"
            reason = ("batch %s half-persisted: %d/%d ops ok but _QSAVE ran; "
                      "NOT safe to re-run this batch automatically (ok ops are "
                      "already persisted). Inspect %s"
                      % (bid, ops_ok, len(recs), run_dir))
        elif not qsave_done and ops_ok > 0:
            status = "partial"
            reason = ("batch %s ran %d/%d ops but _QSAVE did not complete; the "
                      "staged DWG is unchanged by this batch -- safe to re-run "
                      "(resume will retry it). Inspect %s"
                      % (bid, ops_ok, len(recs), run_dir))
        else:
            status = "partial" if ops_ok_total > 0 else "blocked"
            reason = ((run_res or {}).get("error")
                      or envelope.get("detail")
                      or "batch %s produced no usable envelope" % bid)
        break

    out = {"schema": SCHEMA, "status": status, "plan": plan, "batches": batches_out,
           "ops_total": len(applied_records), "ops_ok": ops_ok_total}
    if stopped_at is not None:
        out["stopped_at_batch"] = stopped_at
    if reason:
        out["reason"] = reason
    _write_json(os.path.join(batches_dir, "batch_execution.json"), out)
    return out
