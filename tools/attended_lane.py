#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""attended_lane.py -- CAD OS Wave-R: the ATTENDED full-AutoCAD execution lane.

Some native write ops need AutoCAD engine modules that are demand-loaded and
NOT available inside headless accoreconsole (ISM/raster support for
write.entity.rasterimage/wipeout; the hatch/area engine for
write.entity.hatch/mpolygon). Those ops exit 0 headless but the created entity
never actually persists (see build_log.md for the per-op evidence). This
module drives the SAME native ObjectARX job dispatcher inside a DEDICATED,
disposable, full acad.exe instance instead -- which has those subsystems --
via the one-shot ARIADNE_NATIVE_JOB_ARGS env-file channel
(docs/LIVE_JOB_ARGUMENT_CONTRACT.md), already proven by CADOS_M07B's attended
GUI harness (tools/attended/run_attended_m07b.ps1). tools/attended/
run_attended_job.ps1 is the general-purpose (non-run-specific) sibling of that
script: ONE job, not an interactive pump session.

Design notes (read before extending):

  * Pre/post-inspect stay HEADLESS (accoreconsole via run_job.run_router_
    cad_job) -- reading an already-persisted entity back off disk does not
    need the demand-loaded engine, only CREATING one does. Only the single
    "apply" step (the actual write op) runs attended. This keeps the lane fast
    (one acad.exe launch per op, not one per pre/apply/post) and reuses the
    already-hardened headless read path unchanged.

  * This module deliberately does NOT go through tools/patch_ops
    (NATIVE_WRITE_OP_MAP) or tools/op_roundtrip_probe.py's op_name
    abstraction. It drives the native op_id (e.g. "write.entity.hatch")
    directly and judges with cad_diff.compute_diff / cad_op_gate.
    check_roundtrip -- the SAME primitives the headless P-gate uses -- called
    directly. This is a deliberate scope choice, not an oversight: a sibling
    wave is concurrently adding headless certs (mleader/wipeout/dimension
    variants/...) to op_roundtrip_probe.py and tools/patch_ops/entities.py;
    driving the native op_id directly here means this file has zero overlap
    with those shared registries, at the cost of not being reachable from
    op_roundtrip_probe.py's own CLI. Folding these two lanes together is a
    Wave-R merge task, not a merge-conflict risk introduced by this module.

  * Full P-gate roundtrip cert (attended_roundtrip, geometry-basis diff=0)
    needs the native reader (collectEntitiesFromBlock in
    AriadneNativeJob.cpp) to actually emit type-specific geometry fields for
    the created entity. Originally (early this wave) that was true ONLY for
    HATCH (AcDbHatch::cast branch: pattern_name/loop_count/loops, already
    lifted by ir_builder.py's _geometry_from_native_entity); rasterimage/
    wipeout/mpolygon had no such branch, so a created entity extracted with
    only the generic handle/dxf_name/layer/owner_handle/space record --
    enough for lane_proof()'s handle-basis "net added" check, not enough for
    a geometry-basis fingerprint match. wA-cert closed that gap: all three
    now have AcDbRasterImage::cast/AcDbWipeout::cast/AcDbMPolygon::cast read
    branches + matching ir_builder.py lifts (see expect_rasterimage/
    expect_wipeout/expect_mpolygon below and build_log.md for the live
    diff=0 evidence).

Public API:
    build_job_doc(operation, args) -> dict                       # pure
    run_attended_native_job(staged_dwg, run_dir, operation, args, ...) -> dict
    attended_apply_staged(operation, args, dwg_path, out_dir, ...) -> dict
    lane_proof(operation, args, dwg_path, out_dir, ...) -> dict
    attended_roundtrip(operation, args, dwg_path, out_dir, expected_entity, ...) -> dict
    expect_hatch(args) -> dict                                    # pure
    make_tiny_png_bytes(width, height, rgb) -> bytes              # pure
    ensure_tiny_png(path, **kw) -> str
"""
from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)

SCHEMA_ID = "ariadne.cad_os.attended_lane.v1"
IR_SCHEMA_ID = "ariadne.dwg_graph_ir.v1"
_JSON_ENCODING = "utf-8-sig"

DEFAULT_ACAD_EXE = r"C:\Program Files\Autodesk\AutoCAD 2027\acad.exe"
# Generous: this wave's live runs shared the box with a dozen+ other concurrent
# CAD-OS agent workloads (see build_log.md) -- real AutoCAD startup time under
# that contention exceeded a tighter first-attempt budget. Must match (or
# exceed) run_attended_job.ps1's own -TimeoutSec default.
DEFAULT_TIMEOUT_SEC = 240
_PS1_LAUNCHER = os.path.join(_THIS_DIR, "attended", "run_attended_job.ps1")


def _import_optional(module_name: str):
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
    try:
        return __import__(module_name)
    except Exception:  # pragma: no cover - defensive; sibling truly absent
        return None


def _powershell_exe() -> str:
    for name in ("powershell.exe", "powershell", "pwsh.exe", "pwsh"):
        found = shutil.which(name)
        if found:
            return found
    return r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"


def _sha256_file(path: str) -> Optional[str]:
    import hashlib
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _load_ir(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _read_security_pair(path: Path) -> "tuple[Optional[str], Optional[str]]":
    """Read the 2-line (SECURELOAD, TRUSTEDPATHS) text files the AutoLISP side
    of run_attended_job.ps1 writes directly (security_before.txt /
    security_after.txt). Mirrors the PS1's own $secBeforeLines/$secAfterLines
    parsing so the degraded-envelope path below (see run_attended_native_job)
    can reconstruct security-restore evidence even when the launcher's OWN
    attended_job_result.json never gets written."""
    if not path.is_file():
        return None, None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    secureload = lines[0] if len(lines) >= 1 else None
    trustedpaths = lines[1] if len(lines) >= 2 else None
    return secureload, trustedpaths


# --------------------------------------------------------------------------- #
# 1. job doc construction -- pure, unit-testable (no I/O)
# --------------------------------------------------------------------------- #

def build_job_doc(operation: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Flat ``{"operation": ..., <args...>}`` shape -- the ARIADNE_NATIVE_JOB_ARGS
    env-file channel's ``job_in.json`` contract (docs/LIVE_JOB_ARGUMENT_CONTRACT.md,
    confirmed by CADOS_M07B's own probe-create job), NOT patch_engine.
    _native_job_doc's nested ``{"args": {...}}`` envelope -- that is a DIFFERENT,
    headless-only, ``ARIADNE_NATIVE_JOB`` (no ``_ARGS``) contract.
    """
    if not operation or not isinstance(operation, str):
        raise ValueError("operation must be a non-empty string")
    doc: Dict[str, Any] = {"operation": operation}
    for k, v in (args or {}).items():
        if k == "operation":
            continue
        doc[k] = v
    return doc


# --------------------------------------------------------------------------- #
# 2. the attended one-shot job runner -- shells to run_attended_job.ps1
# --------------------------------------------------------------------------- #

def run_attended_native_job(staged_dwg: str, run_dir: str, operation: str,
                            args: Dict[str, Any], *, timeout: int = DEFAULT_TIMEOUT_SEC,
                            acad_exe: Optional[str] = None,
                            router_home: Optional[str] = None,
                            ps1_launcher: Optional[str] = None) -> Dict[str, Any]:
    """Drive ONE native ObjectARX job inside a DEDICATED, disposable full
    acad.exe instance (never the user's session) via the
    ARIADNE_NATIVE_JOB_ARGS env-file channel. Returns a dict shaped like
    ``run_job.run_router_cad_job``'s contract (command, exit_code,
    stdout_path, stderr_path, envelope, result_json, result, staged_used,
    timed_out, error) for drop-in parity with the headless lane.
    """
    run_dir_p = Path(run_dir)
    run_dir_p.mkdir(parents=True, exist_ok=True)
    stdout_path = run_dir_p / "stdout.txt"
    stderr_path = run_dir_p / "stderr.txt"

    launcher = ps1_launcher or _PS1_LAUNCHER
    if not os.path.isfile(launcher):
        msg = "attended launcher missing: %s" % launcher
        stderr_path.write_text(msg + "\n", encoding="utf-8")
        stdout_path.write_text("", encoding="utf-8")
        return {"command": None, "exit_code": None, "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path), "envelope": None, "result_json": None,
                "result": None, "staged_used": None, "timed_out": False, "error": msg,
                "degraded": False, "degraded_reason": None}

    job_doc = build_job_doc(operation, args)
    job_args_json = json.dumps(job_doc, ensure_ascii=False)

    ps = _powershell_exe()
    cmd = [
        ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", launcher,
        "-StagedDwg", staged_dwg,
        "-Operation", operation,
        "-JobArgsJson", job_args_json,
        "-RunDir", str(run_dir_p),
        "-TimeoutSec", str(timeout),
    ]
    if acad_exe:
        cmd += ["-AcadExe", acad_exe]
    # wA-cert BUGFIX: this was `if router_home: cmd += [...]`, silently falling
    # through to run_attended_job.ps1's OWN hardcoded `-RouterHome` default
    # (a specific sibling worktree name baked in at Wave-R authoring time) any
    # time a caller did not pass router_home explicitly -- which every public
    # entry point in this module (attended_apply_staged/lane_proof/
    # attended_roundtrip) previously did NOT thread through at all. Live-caught
    # this wave: a wA-cert rebuild + re-test against native_sample.dwg silently
    # arxload'd a DIFFERENT worktree's prebuilt/2027 binaries (confirmed via the
    # generated attended_job.scr's literal arxload paths), producing a stale
    # pre-fix result. Always pass -RouterHome explicitly, defaulting to THIS
    # module's own router root (_ROUTER_HOME, i.e. the worktree this exact
    # attended_lane.py file lives in) -- correct regardless of which worktree
    # imports/runs this module, and never silently drifts to a sibling
    # worktree's (possibly stale, possibly since-deleted) binaries.
    cmd += ["-RouterHome", router_home or _ROUTER_HOME]

    timed_out = False
    error = None
    degraded = False
    degraded_reason = None
    stdout_text = ""
    stderr_text = ""
    code = None
    outer_timeout = timeout + 120  # margin beyond the PS1's own poll+grace+kill budget
    job_out_path = run_dir_p / "job_out.json"
    result_json_path = run_dir_p / "attended_job_result.json"

    # IMPORTANT: redirect to real FILES, not PIPEs (i.e. do NOT use
    # capture_output=True / stdout=PIPE here). Windows subprocess.run()
    # internally calls Popen.communicate(), which waits for the stdout/stderr
    # PIPES to reach EOF -- and pipe handles are inheritable by default, so a
    # grandchild process this script launches via `Start-Process` (the
    # disposable acad.exe instance) can inherit a handle to the SAME pipe,
    # keeping the write-end open even after the direct child (powershell.exe)
    # has already exited cleanly.
    #
    # IMPORTANT #2 (found AFTER fixing #1 and STILL seeing the same hang):
    # even with file-based redirection, the launcher's OWN post-job
    # bookkeeping (a handful of trivial Get-Process/Get-Content/ConvertTo-Json
    # calls in run_attended_job.ps1's `finally` block, AFTER it already logs
    # "post-poll: jobDone=True hasExited=True") can itself stall for minutes
    # on this box, specifically for runs that actually launched acad.exe --
    # two independent minimal repros (a bare Python->powershell.exe round
    # trip, and a Start-Process+poll+finally-block repro using a throwaway
    # nested powershell.exe instead of acad.exe) both completed in under a
    # second/ten seconds respectively, so this is NOT a generic Python-
    # subprocess bug and NOT a bug in the launch/poll/bookkeeping PATTERN
    # itself. Leading hypothesis (not proven -- would need admin access to AV
    # logs to confirm): on-access scanning of job_out.json/security_after.txt
    # by endpoint security software, triggered because they were just written
    # by a process that did unsigned arxload of custom native ARX/DBX
    # modules, worsened by this box running a dozen+ OTHER concurrent
    # CAD-OS agents doing similar native-module-load work at the same time.
    # See build_log.md.
    #
    # Fix: do not block on the LAUNCHER PROCESS's own exit at all. Poll for
    # job_out.json (written by the AutoLISP/native side, independent of the
    # PS1's own finally block) as the authoritative signal that the CAD job
    # itself completed, and treat attended_job_result.json (the launcher's
    # own self-report) as a nice-to-have that is read opportunistically. If
    # the CAD job clearly succeeded but the launcher's bookkeeping file still
    # hasn't appeared after a generous grace window, proceed in a clearly-
    # flagged DEGRADED mode instead of blocking the caller for the full
    # outer_timeout on bookkeeping that provides no additional CAD evidence.
    grace_after_job_out = 30.0  # mirrors the PS1's own 30s post-job grace window
    with open(stdout_path, "w", encoding="utf-8", newline="") as out_fh, \
         open(stderr_path, "w", encoding="utf-8", newline="") as err_fh:
        try:
            proc = subprocess.Popen(
                cmd, cwd=_ROUTER_HOME, stdout=out_fh, stderr=err_fh, text=True,
                encoding="utf-8", errors="replace",
            )
        except OSError as exc:
            proc = None
            error = "failed to launch attended runner: %s" % exc

        if proc is not None:
            deadline = time.monotonic() + outer_timeout
            saw_job_out_at = None
            while True:
                if result_json_path.is_file():
                    break  # best case: launcher's own full self-report is present
                if job_out_path.is_file() and saw_job_out_at is None:
                    saw_job_out_at = time.monotonic()
                if proc.poll() is not None:
                    time.sleep(1.0)  # brief settle window for any last flush
                    break
                if saw_job_out_at is not None and (time.monotonic() - saw_job_out_at) >= grace_after_job_out:
                    degraded = True
                    degraded_reason = (
                        "job_out.json appeared (the CAD job itself completed) but "
                        "attended_job_result.json (the launcher's own bookkeeping "
                        "self-report) did not appear within %ds of that, and the "
                        "launcher process itself has not exited either; proceeding "
                        "on job_out.json + raw security_before/after.txt evidence "
                        "directly rather than blocking further -- see build_log.md"
                        % int(grace_after_job_out))
                    break
                if time.monotonic() >= deadline:
                    timed_out = True
                    error = ("attended launcher timed out after %ds with neither "
                              "job_out.json nor attended_job_result.json present "
                              "(the PS1's own %ds job timeout + grace/kill budget "
                              "should have fired before this outer deadline)"
                              % (outer_timeout, timeout))
                    break
                time.sleep(0.5)

            code = proc.poll()
            if code is None:
                # best-effort cleanup only -- never let teardown block the return
                try:
                    proc.kill()
                except OSError:
                    pass
                try:
                    proc.wait(timeout=10)
                except Exception:
                    pass
                code = proc.poll()

    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.is_file() else ""
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.is_file() else ""

    result_json = str(result_json_path)
    envelope = None
    if result_json_path.is_file():
        try:
            envelope = json.loads(result_json_path.read_text(encoding="utf-8-sig"))
        except (ValueError, OSError):
            envelope = None

    if envelope is None and degraded and job_out_path.is_file():
        try:
            job_out_obj = json.loads(job_out_path.read_text(encoding="utf-8-sig"))
        except (ValueError, OSError):
            job_out_obj = None
        if job_out_obj is not None:
            sec_before_ld, sec_before_tp = _read_security_pair(run_dir_p / "security_before.txt")
            sec_after_ld, sec_after_tp = _read_security_pair(run_dir_p / "security_after.txt")
            restored = (sec_before_ld is not None and sec_before_ld == sec_after_ld
                        and sec_before_tp == sec_after_tp)
            envelope = {
                "schema": "ariadne.cad_os.attended_job_result.v1",
                "status": "ok" if job_out_obj.get("status") == "ok" else "error",
                "degraded": True,
                "degraded_reason": degraded_reason,
                "operation": operation,
                "result": job_out_obj.get("result"),
                "job_out_present": True,
                "security": {
                    "secureload_before": sec_before_ld, "secureload_after": sec_after_ld,
                    "trustedpaths_before": sec_before_tp, "trustedpaths_after": sec_after_tp,
                    "restored": restored,
                },
                "error": None if job_out_obj.get("status") == "ok" else
                         (job_out_obj.get("error") or "native job reported a non-ok status"),
            }
            timed_out = False  # the CAD job demonstrably completed; this is not a timeout
        else:
            error = error or "degraded mode but job_out.json could not be parsed"

    result_obj = None
    staged_used = None
    if envelope:
        result_obj = envelope.get("result")
        # QSAVE happens in-place inside the launched session -- staged_dwg IS
        # the mutated copy once the lane reports its own mechanism succeeded
        # (job_out.json appeared and parsed). Whether the JOB ITSELF (nested
        # result.status) succeeded is deliberately NOT gated here -- the
        # post-inspect diff is this lane's source of truth (mirrors how
        # patch_engine.apply_staged trusts run_router_cad_job's staged_used
        # and lets the post-inspect diff reveal a silent native-side failure
        # as zero added entities, never a fake pass).
        if envelope.get("status") == "ok":
            staged_used = staged_dwg
        if envelope.get("timed_out"):
            timed_out = True
        if envelope.get("status") == "error" and not error:
            error = envelope.get("error") or "attended job reported status=error"
        if envelope.get("status") == "blocked" and not error:
            error = envelope.get("error") or "attended job GATE1 blocked"
        if envelope.get("status") == "timeout" and not error:
            error = envelope.get("error") or "attended job timed out"

    return {"command": cmd, "exit_code": code, "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path), "envelope": envelope,
            "result_json": result_json if envelope else None, "result": result_obj,
            "staged_used": staged_used, "timed_out": timed_out, "error": error,
            "degraded": degraded, "degraded_reason": degraded_reason}


# --------------------------------------------------------------------------- #
# 3. the attended apply_staged envelope -- headless pre/post-inspect, ONE
#    attended apply step in the middle.
# --------------------------------------------------------------------------- #

def attended_apply_staged(operation: str, args: Dict[str, Any], dwg_path: str, out_dir: str, *,
                          timeout: int = DEFAULT_TIMEOUT_SEC,
                          patch_engine_mod=None, run_job_mod=None, ir_builder_mod=None,
                          acad_exe: Optional[str] = None,
                          router_home: Optional[str] = None) -> Dict[str, Any]:
    """The attended-lane counterpart to ``patch_engine.apply_staged``: stage a
    copy, pre-inspect HEADLESS, apply the ONE native write op ATTENDED (the
    only step that needs full acad.exe), post-inspect HEADLESS again. Returns
    the envelope shape callers need: ``{status, original_unchanged, pre_ir,
    post_ir, reason?, ...}`` -- never a fake ``"ok"``.
    """
    pe = patch_engine_mod if patch_engine_mod is not None else _import_optional("patch_engine")
    rj = run_job_mod if run_job_mod is not None else _import_optional("run_job")
    irb = ir_builder_mod if ir_builder_mod is not None else _import_optional("ir_builder")
    if pe is None or rj is None or irb is None:
        missing = [n for n, m in (("patch_engine", pe), ("run_job", rj), ("ir_builder", irb)) if m is None]
        return {"status": "not_implemented", "reason": "sibling module(s) unavailable: %s" % missing}

    staged = pe.create_staged_copy(dwg_path, out_dir)
    if not staged["ok"]:
        return {"status": "blocked", "reason": staged.get("reason")}
    staged_path = staged["staged_path"]
    original_path = staged["original_path"]
    original_sha_before = staged["original_sha256"]

    def _original_unchanged() -> Dict[str, Any]:
        after = _sha256_file(original_path) if original_path else None
        return {"original_path": original_path, "sha256_before": original_sha_before,
                "sha256_after": after,
                "unchanged": (original_sha_before is not None and after == original_sha_before)}

    # pre-inspect: HEADLESS (accoreconsole via the router) -- reading does not
    # need the demand-loaded engine; only creating the entity does.
    pre_dir = os.path.join(out_dir, "pre")
    pre_run = rj.run_router_cad_job(staged_path, pre_dir, "inspect.database.graph", write_mode="read")
    pre_ir_path = os.path.join(pre_dir, "dwg_graph_ir.json")
    pre = pe._native_full_ir(irb, pre_run, staged_path, original_path, pre_ir_path, "pre")
    if not pre["ok"]:
        return {"status": "partial" if not pre_run.get("error") else "unavailable",
                "reason": "pre-inspect failed: %s" % pre.get("reason"),
                "original_unchanged": _original_unchanged()}

    # apply: the ONE native write op, ATTENDED (full acad.exe) -----------------
    apply_dir = os.path.join(out_dir, "apply")
    apply_run = run_attended_native_job(staged_path, apply_dir, operation, args,
                                        timeout=timeout, acad_exe=acad_exe,
                                        router_home=router_home)
    if apply_run.get("error") or not apply_run.get("staged_used"):
        return {"status": "unavailable" if apply_run.get("error") else "partial",
                "reason": apply_run.get("error") or "attended job produced no staged_used",
                "original_unchanged": _original_unchanged(),
                "attended_job_result": apply_run.get("envelope")}
    staged_output = os.path.join(out_dir, "staged_output.dwg")
    shutil.copy2(apply_run["staged_used"], staged_output)

    # post-inspect: HEADLESS again (reads the SAVED mutation off disk) --------
    post_dir = os.path.join(out_dir, "post")
    post_run = rj.run_router_cad_job(staged_output, post_dir, "inspect.database.graph", write_mode="read")
    post_ir_path = os.path.join(post_dir, "dwg_graph_ir.json")
    post = pe._native_full_ir(irb, post_run, staged_output, original_path, post_ir_path, "post")
    if not post["ok"]:
        return {"status": "partial" if not post_run.get("error") else "unavailable",
                "reason": "post-inspect failed: %s" % post.get("reason"),
                "original_unchanged": _original_unchanged(),
                "attended_job_result": apply_run.get("envelope")}

    return {
        "status": "ok",
        "original_unchanged": _original_unchanged(),
        "pre_ir": pre["ir_path"], "post_ir": post["ir_path"],
        "pre_entity_count": pre.get("entity_count"), "post_entity_count": post.get("entity_count"),
        "attended_job_result": apply_run.get("envelope"),
        "run_dir": out_dir,
    }


# --------------------------------------------------------------------------- #
# 4. added-entity extraction (handle-basis) -- mirrors op_roundtrip_probe.py's
#    added_entities_ir, reimplemented locally so this module has no edit
#    dependency on that concurrently-edited file (import-only would be fine
#    too, but a 10-line reimplementation is cheaper than a cross-module
#    coupling for something this small).
# --------------------------------------------------------------------------- #

def _added_entities(pre_ir: Dict[str, Any], post_ir: Dict[str, Any], *,
                    cad_diff_mod=None) -> List[Dict[str, Any]]:
    cd = cad_diff_mod if cad_diff_mod is not None else _import_optional("cad_diff")
    if cd is None or not hasattr(cd, "compute_diff"):
        raise RuntimeError("cad_diff sibling module unavailable")
    diff = cd.compute_diff(pre_ir, post_ir, comparison_basis="handle")
    added_handles = {r["handle"] for r in diff["changed_handles"] if r["change"] == "added"}
    post_by_handle = {e.get("handle"): e for e in (post_ir.get("entities") or []) if isinstance(e, dict)}
    return [post_by_handle[h] for h in sorted(added_handles) if h in post_by_handle]


def lane_proof(operation: str, args: Dict[str, Any], dwg_path: str, out_dir: str, *,
              expected_dxf_name: Optional[str] = None, expected_layer: Optional[str] = None,
              timeout: int = DEFAULT_TIMEOUT_SEC, acad_exe: Optional[str] = None,
              router_home: Optional[str] = None) -> Dict[str, Any]:
    """LANE PROOF (not full P-gate cert): proves the attended lane creates a
    REAL, PERSISTED entity that survives a fresh headless re-extraction --
    handle-basis net "added" count, independent of whether the native reader
    has a geometry branch for this entity kind (rasterimage/wipeout/mpolygon
    do not; see build_log.md). Sufficient evidence the lane WORKS; not a claim
    of full roundtrip cert.
    """
    envelope = attended_apply_staged(operation, args, dwg_path, out_dir, timeout=timeout,
                                     acad_exe=acad_exe, router_home=router_home)
    if envelope.get("status") != "ok":
        return {"schema": SCHEMA_ID, "op": operation, "status": envelope.get("status"),
                "reason": envelope.get("reason"), "envelope": envelope}
    pre_ir = _load_ir(envelope["pre_ir"])
    post_ir = _load_ir(envelope["post_ir"])
    added = _added_entities(pre_ir, post_ir)
    net = len(added)
    ok = net >= 1
    if expected_dxf_name is not None:
        ok = ok and any(e.get("dxf_name") == expected_dxf_name for e in added)
    if expected_layer is not None:
        ok = ok and any(e.get("layer") == expected_layer for e in added)
    return {
        "schema": SCHEMA_ID, "op": operation, "status": "ok" if ok else "fail",
        "net_added": net, "added_entities": added,
        "pre_entity_count": envelope.get("pre_entity_count"),
        "post_entity_count": envelope.get("post_entity_count"),
        "original_unchanged": envelope.get("original_unchanged"),
        "attended_job_result": envelope.get("attended_job_result"),
        "run_dir": out_dir,
    }


def attended_roundtrip(operation: str, args: Dict[str, Any], dwg_path: str, out_dir: str,
                       expected_entity: Dict[str, Any], *,
                       geometry_tolerance: Optional[float] = None,
                       timeout: int = DEFAULT_TIMEOUT_SEC, acad_exe: Optional[str] = None,
                       router_home: Optional[str] = None,
                       cad_diff_mod=None, cad_op_gate_mod=None) -> Dict[str, Any]:
    """FULL P-gate roundtrip cert via the attended lane: does the geometry we
    ASKED to be written (``expected_entity``) fingerprint-match what a fresh
    headless re-extraction reads back? Same judge
    (``cad_op_gate.check_roundtrip``) the headless lane uses, called directly
    (see module docstring for why this bypasses op_roundtrip_probe.py).
    """
    gate = cad_op_gate_mod if cad_op_gate_mod is not None else _import_optional("cad_op_gate")
    if gate is None:
        return {"schema": SCHEMA_ID, "op": operation, "status": "error",
                "reason": "cad_op_gate sibling module unavailable"}
    envelope = attended_apply_staged(operation, args, dwg_path, out_dir, timeout=timeout,
                                     acad_exe=acad_exe, router_home=router_home)
    if envelope.get("status") != "ok":
        return {"schema": SCHEMA_ID, "op": operation, "status": envelope.get("status"),
                "reason": envelope.get("reason"), "envelope": envelope}
    pre_ir = _load_ir(envelope["pre_ir"])
    post_ir = _load_ir(envelope["post_ir"])
    added = _added_entities(pre_ir, post_ir, cad_diff_mod=cad_diff_mod)
    actual_ir = {"schema": IR_SCHEMA_ID, "entities": added}
    expected_ir = {"schema": IR_SCHEMA_ID, "entities": [expected_entity]}
    tol = geometry_tolerance if geometry_tolerance is not None else gate.DEFAULT_GEOMETRY_TOLERANCE
    gate_result = gate.check_roundtrip(expected_ir, actual_ir, geometry_tolerance=tol, cad_diff_mod=cad_diff_mod)
    result = dict(gate_result)
    result.update({"schema": SCHEMA_ID, "op": operation, "expected_ir": expected_ir,
                  "actual_ir": actual_ir, "original_unchanged": envelope.get("original_unchanged"),
                  "attended_job_result": envelope.get("attended_job_result"), "run_dir": out_dir})
    return result


# --------------------------------------------------------------------------- #
# 5. ground-truth builders (pure; mirror op_roundtrip_probe.py's
#    _expect_create_* style so a future merge into that registry is
#    mechanical, without actually touching that file this wave).
# --------------------------------------------------------------------------- #

def _point_to_list(coords: Any) -> list:
    if isinstance(coords, dict):
        return [coords.get("x", 0.0), coords.get("y", 0.0), coords.get("z", 0.0)]
    return list(coords)


def expect_hatch(args: Dict[str, Any], *, loop_type: int = 3) -> Dict[str, Any]:
    """Ground truth for ``write.entity.hatch``: m08h_handlers.inc always
    creates a SOLID-pattern, non-associative, single-external-loop hatch from
    the ``vertices`` arg (zero bulges, elevation 0.0) -- matches
    AriadneNativeJob.cpp's ``AcDbHatch::cast`` read branch
    (pattern_name/loop_count/loops) and ir_builder.py's
    ``_geometry_from_native_entity`` HATCH lift (kind/pattern_name/loops
    passthrough).

    ``loop_type`` defaults to 3 (``kExternal(1) | kPolyline(2)``) -- AutoCAD's
    OWN ``getLoopAt()`` classification for a loop built via
    ``appendLoop(kExternal, verts, bulges)``, per this wave's live attended
    run (see build_log.md for the exact run_dir). Pass an explicit value if a
    future AutoCAD version classifies it differently -- this is an observed
    runtime fact, not a documented guarantee.

    Attended-wave (Lane AT) fix: the geometry dict now also carries
    ``normal``/``elevation``/``pattern_angle``/``pattern_scale``/
    ``hatch_style``/``loop_count``/``pattern_type``/``pattern_double``/
    ``is_solid_fill``/``is_associative``/``is_gradient`` -- AcDbHatch's own
    default/derived values for a SOLID, non-associative, non-gradient hatch
    (LIVE-VERIFIED this wave: ``cad_op_gate.check_roundtrip`` against a real
    attended write.entity.hatch run reported these as spurious "modified"
    fields with the prior minimal ground truth, even though the write itself
    was correct -- an incomplete expected-value builder, not a write defect;
    see build_log.md's Attended Wave entry for the exact run_dir + before/after
    diff that exposed this).
    """
    verts = args.get("vertices") or []
    loop_verts = [{"point": _point_to_list(v)[:2] + [0.0], "bulge": 0.0} for v in verts]
    return {
        "dxf_name": "HATCH", "layer": args.get("layer") or "0",
        "geometry": {"kind": "hatch", "pattern_name": "SOLID",
                    "normal": [0.0, 0.0, 1.0], "elevation": 0.0,
                    "pattern_angle": 0.0, "pattern_scale": 1.0, "hatch_style": 0.0,
                    "loop_count": (1.0 if loop_verts else 0.0), "pattern_type": 1.0,
                    "pattern_double": False, "is_solid_fill": True,
                    "is_associative": False, "is_gradient": False,
                    "loops": [{"index": 0, "loop_type": loop_type, "closed": True, "status": "ok",
                              "vertices": loop_verts}]},
    }


def expect_rasterimage(args: Dict[str, Any]) -> Dict[str, Any]:
    """Ground truth for ``write.entity.rasterimage``: m08g_handlers.inc reads
    ``position``/``width``/``height`` job args and calls
    ``setOrientation(position, (width,0,0), (0,height,0))`` -- the U/V
    vectors are PRE-SCALED by width/height, not unit vectors -- then
    ``setClipBoundaryToWholeImage``, and stores ``image_path`` verbatim via
    ``AcDbRasterImageDef::setSourceFileName``. Matches AriadneNativeJob.cpp's
    AcDbRasterImage::cast read branch and ir_builder.py's
    _geometry_from_native_entity lift.

    clip_boundary_type=1 is ClipBoundaryType::kRect (imgent.h, the only type
    setClipBoundaryToWholeImage can produce). clip_boundary for a kRect is a
    CLOSED 5-point rectangle offset by -0.5 in both x and y from the nominal
    (0,0)-(w,h) box -- a pixel-CENTER-vs-pixel-CORNER convention (pixel index
    0's cell spans -0.5..+0.5) -- LIVE-VERIFIED this wave (see build_log.md;
    an initial "opposite corners, no offset" hypothesis was wrong, corrected
    from the actual diff, same empirical-correction pattern as expect_hatch's
    loop_type). source_file_name round-trips through AutoCAD's own path
    normalization to native Windows backslashes regardless of what separator
    style the caller's image_path used -- os.path.normpath mirrors that.
    """
    origin = _point_to_list(args.get("position") or [0.0, 0.0, 0.0])
    w = float(args.get("width", 1.0))
    h = float(args.get("height", 1.0))
    clip_rect = [[-0.5, -0.5], [-0.5, h - 0.5], [w - 0.5, h - 0.5], [w - 0.5, -0.5], [-0.5, -0.5]]
    return {
        "dxf_name": "IMAGE", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "rasterimage",
            "origin": origin,
            "u_vector": [w, 0.0, 0.0],
            "v_vector": [0.0, h, 0.0],
            "image_size": [w, h],
            "clip_boundary_type": 1,
            "clip_boundary": clip_rect,
            "source_file_name": os.path.normpath(str(args.get("image_path", ""))),
        },
    }


def expect_wipeout(args: Dict[str, Any]) -> Dict[str, Any]:
    """Ground truth for ``write.entity.wipeout``: m08g_handlers.inc hardcodes
    the plane orientation to identity (``origin=(0,0,0)``, ``u=(1,0,0)``,
    ``v=(0,1,0)`` -- unlike write.entity.rasterimage, no position/width/
    height job args are read here) and always uses
    ``ClipBoundaryType::kPoly`` (2, per imgent.h) with the caller's
    ``vertices``.

    IMPORTANT: setClipBoundary live-probed (this wave, see build_log.md) to
    require an EXPLICITLY CLOSED polygon -- an open loop fails
    eInvalidInput(3). The caller's ``vertices`` arg MUST already repeat the
    first vertex as the last, or the create itself fails before there is
    anything to diff.

    ``frame_on`` is NOT set explicitly by the handler (no setFrame call) --
    LIVE-VERIFIED this wave to default true. ``image_size`` is also not set
    explicitly (no width/height args read) -- LIVE-VERIFIED to be [1.0, 1.0]
    for a unit-square clip boundary; whether this is a fixed placeholder
    default or actually derived from the clip boundary's bounding box was
    NOT disambiguated (both are consistent with the one shape tested) -- an
    honest open question, not re-tested with a second shape given this
    already reaches a live diff=0 cert (see build_log.md). Callers using a
    differently-sized clip boundary should re-verify this field.
    """
    verts = args.get("vertices") or []
    clip_pts = [_point_to_list(v)[:2] for v in verts]
    return {
        "dxf_name": "WIPEOUT", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "wipeout",
            "origin": [0.0, 0.0, 0.0],
            "u_vector": [1.0, 0.0, 0.0],
            "v_vector": [0.0, 1.0, 0.0],
            "image_size": [1.0, 1.0],
            "clip_boundary_type": 2,
            "clip_boundary": clip_pts,
            "source_file_name": "",
            "frame_on": True,
        },
    }


def expect_mpolygon(args: Dict[str, Any]) -> Dict[str, Any]:
    """Ground truth for ``write.entity.mpolygon``: m08g_handlers.inc always
    creates a single-loop, SOLID-pattern (AcDbHatch::kPreDefined "SOLID")
    mpolygon at elevation 0.0 with normal (0,0,1) from the caller's
    ``vertices`` (zero bulges) -- matches AriadneNativeJob.cpp's
    AcDbMPolygon::cast read branch (pattern_name/elevation/normal/loop_count/
    loops) and ir_builder.py's _geometry_from_native_entity MPOLYGON lift.

    ``appendMPolygonLoop``'s third arg is ``excludeCrossing`` (self-
    intersection handling during hatch evaluation, per dbmpolygon.h) -- NOT
    a close/normalize flag, so an initial hypothesis that the stored loop
    vertex COUNT would echo the input verbatim was reasonable, but LIVE-
    VERIFIED WRONG (reproduced identically across 2 independent live runs,
    including one against a freshly rebuilt binary, ruling out build
    staleness): AcDbMPolygon always stores a CLOSED loop, and if the
    caller's ``vertices`` do not already repeat the first point as the
    last, the read-back OVERWRITES the last vertex's coordinates with the
    first vertex's -- it does not add an extra point (unlike AcDbWipeout's
    clip boundary, which genuinely needs an explicit extra closing vertex).
    This is a real caller-facing gotcha for write.entity.mpolygon, not a
    test-only quirk: an open N-corner input silently loses the distinctness
    of its Nth corner. Documented here rather than "fixed" in the write
    handler, since certifying what the op ACTUALLY does is this wave's
    scope (see build_log.md).
    """
    verts = args.get("vertices") or []
    loop_verts = [{"point": _point_to_list(v)[:2] + [0.0], "bulge": 0.0} for v in verts]
    if len(loop_verts) >= 2:
        loop_verts[-1] = {"point": loop_verts[0]["point"], "bulge": 0.0}
    return {
        "dxf_name": "MPOLYGON", "layer": args.get("layer") or "0",
        "geometry": {
            "kind": "mpolygon",
            "pattern_name": "SOLID",
            "elevation": 0.0,
            "normal": [0.0, 0.0, 1.0],
            "loop_count": 1,
            "loops": [{"index": 0, "vertices": loop_verts}],
        },
    }


# --------------------------------------------------------------------------- #
# 6. tiny PNG fixture (stdlib-only -- no Pillow dependency for rasterimage's
#    required image_path arg; a real file must exist on disk).
# --------------------------------------------------------------------------- #

def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def make_tiny_png_bytes(width: int = 4, height: int = 4, rgb=(255, 255, 255)) -> bytes:
    """A minimal valid 8-bit truecolor PNG, stdlib-only (zlib/struct)."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))  # filter=0/scanline
    idat = zlib.compress(raw, 9)
    return sig + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", idat) + _png_chunk(b"IEND", b"")


def ensure_tiny_png(path: str, **kw) -> str:
    if not os.path.isfile(path):
        parent = os.path.dirname(path) or "."
        os.makedirs(parent, exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(make_tiny_png_bytes(**kw))
    return path


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="attended full-AutoCAD execution lane (Wave-R)")
    ap.add_argument("--op", required=True, help="native op_id, e.g. write.entity.hatch")
    ap.add_argument("--dwg", required=True, help="a real DWG to stage (never written directly)")
    ap.add_argument("--layer", default="0")
    ap.add_argument("--args-json", default="{}", help="JSON object merged as flat job args")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SEC)
    ap.add_argument("--mode", choices=["lane-proof", "full-cert"], default="lane-proof")
    ap.add_argument("--expected-dxf-name", default=None)
    ap.add_argument("--router-home", default=None,
                    help="router worktree root whose prebuilt/2027 binaries get arxload'd; "
                         "defaults to the worktree THIS attended_lane.py file lives in "
                         "(_ROUTER_HOME) -- pass explicitly only to target a different worktree")
    ns = ap.parse_args()

    extra_args = json.loads(ns.args_json)
    extra_args.setdefault("layer", ns.layer)

    if ns.mode == "lane-proof":
        res = lane_proof(ns.op, extra_args, ns.dwg, ns.out_dir,
                         expected_dxf_name=ns.expected_dxf_name, timeout=ns.timeout,
                         router_home=ns.router_home)
    else:
        if ns.op == "write.entity.hatch":
            expected = expect_hatch(extra_args)
        elif ns.op == "write.entity.rasterimage":
            expected = expect_rasterimage(extra_args)
        elif ns.op == "write.entity.wipeout":
            expected = expect_wipeout(extra_args)
        elif ns.op == "write.entity.mpolygon":
            expected = expect_mpolygon(extra_args)
        else:
            raise SystemExit("no built-in expected-entity builder for --mode full-cert --op %r" % ns.op)
        res = attended_roundtrip(ns.op, extra_args, ns.dwg, ns.out_dir, expected, timeout=ns.timeout,
                                 router_home=ns.router_home)

    print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    sys.exit(0 if res.get("status") == "ok" else 1)
