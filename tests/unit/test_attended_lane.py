#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Wave-R TEST -- tools/attended_lane.py + tools/attended/run_attended_job.ps1.

Intent (WHY):
  * rasterimage/wipeout/hatch/mpolygon need AutoCAD engine modules (ISM/raster,
    hatch area engine) that headless accoreconsole never loads. attended_lane.py
    drives the SAME native job dispatcher inside a dedicated full acad.exe
    instead. A live AutoCAD launch cannot run in CI/headless boxes, so this
    suite splits like the M07/M07B precedent: pure logic (job-doc construction,
    ground-truth builders, envelope parsing) is unit-tested with INJECTED fake
    siblings -- no subprocess, no AutoCAD, ever -- and the genuine end-to-end
    proof is a separate CADOS_LIVE=1 (+ acad.exe present) smoke, skipped by
    default with an explicit reason (never a silent pass).
  * The PS1 launcher cannot be unit-tested without a live editor either, so its
    safety-critical properties (SECURELOAD/TRUSTEDPATHS restored, not just
    set -- the M07B script never restored them; this wave's whole point is not
    to repeat that gap -- dedicated-instance gate, taskkill-only-launched-PID)
    are pinned as source-presence guards, mirroring
    tests/unit/test_m07b_pump_gating_and_job_channel.py's own convention.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import attended_lane as al  # noqa: E402

ROOT = Path(_REPO)
PS1_LAUNCHER = ROOT / "tools" / "attended" / "run_attended_job.ps1"


def _final_attended_receipt(operation: str, job_out: Path) -> dict:
    """A compact, post-cleanup launcher receipt.

    The native payload remains in job_out.json; the launcher receipt must only
    certify the dedicated-instance and restoration cleanup that job_out cannot
    prove by itself.
    """
    return {
        "schema": "ariadne.cad_os.attended_job_result.v1",
        "phase": "finalized",
        "status": "ok",
        "run_id": job_out.parent.name,
        "operation": operation,
        "receipt_authority": "powershell_launcher",
        "recovered_from_launcher_finalization_hang": False,
        "launched_pid": 4242,
        "dedicated_instance": True,
        "timed_out": False,
        "launched_pid_closed": True,
        "user_session_touched": False,
        "job_out": str(job_out),
        "job_out_present": True,
        "degraded": False,
        "security": {"restored": True},
    }


def _completion_receipt(operation: str, job_out: Path, *, cleanup_wait_sec: int = 45) -> dict:
    """The bounded pre-cleanup signal; intentionally not a success result."""
    return {
        "schema": "ariadne.cad_os.attended_job_completion.v1",
        "phase": "cleanup_pending",
        "status": "observed",
        "run_id": "run",
        "operation": operation,
        "launched_pid": 4242,
        "launched_start_time_utc": "2026-08-10T00:00:00.0000000Z",
        "dedicated_instance": True,
        "timed_out": False,
        "job_out": str(job_out),
        "job_out_present": True,
        "pre_existing_pids": [],
        "pre_existing_processes": [],
        "cleanup_wait_sec": cleanup_wait_sec,
    }


# ========================================================================== #
# 1. build_job_doc -- pure, no I/O
# ========================================================================== #

def test_build_job_doc_flat_shape():
    """The ARIADNE_NATIVE_JOB_ARGS env-file channel's job_in.json is FLAT
    ({"operation": ..., <args...>}), confirmed by docs/LIVE_JOB_ARGUMENT_
    CONTRACT.md and CADOS_M07B's own probe-create job -- NOT patch_engine.
    _native_job_doc's nested {"args": {...}} envelope (a different, headless-
    only ARIADNE_NATIVE_JOB contract)."""
    doc = al.build_job_doc("write.entity.hatch", {"layer": "L1", "vertices": [{"x": 0, "y": 0, "z": 0}]})
    assert doc == {"operation": "write.entity.hatch", "layer": "L1",
                   "vertices": [{"x": 0, "y": 0, "z": 0}]}


def test_build_job_doc_ignores_operation_key_in_args():
    """A caller-supplied args["operation"] must never shadow the real op_id --
    the function param is the single source of truth."""
    doc = al.build_job_doc("write.entity.hatch", {"operation": "sneaky", "layer": "L1"})
    assert doc["operation"] == "write.entity.hatch"


def test_build_job_doc_empty_args_ok():
    assert al.build_job_doc("inspect.database.graph", {}) == {"operation": "inspect.database.graph"}
    assert al.build_job_doc("inspect.database.graph", None) == {"operation": "inspect.database.graph"}


@pytest.mark.parametrize("bad_op", ["", None])
def test_build_job_doc_rejects_empty_operation(bad_op):
    with pytest.raises(ValueError):
        al.build_job_doc(bad_op, {})


# ========================================================================== #
# 2. expect_hatch -- pure ground-truth builder
# ========================================================================== #

def test_expect_hatch_shape_matches_native_reader_and_ir_lift():
    """Must fingerprint-match AriadneNativeJob.cpp's AcDbHatch::cast read
    branch (pattern_name/loop_count/loops) as lifted by ir_builder.py's
    _geometry_from_native_entity (kind="hatch", pattern_name, loops
    passthrough) -- these are the exact keys cad_op_gate.check_roundtrip's
    geometry-basis diff will compare against the real extraction."""
    args = {"layer": "HLAYER", "vertices": [
        {"x": 0.0, "y": 0.0, "z": 0.0}, {"x": 10.0, "y": 0.0, "z": 0.0},
        {"x": 10.0, "y": 10.0, "z": 0.0}, {"x": 0.0, "y": 10.0, "z": 0.0},
    ]}
    ent = al.expect_hatch(args)
    assert ent["dxf_name"] == "HATCH"
    assert ent["layer"] == "HLAYER"
    geom = ent["geometry"]
    assert geom["kind"] == "hatch"
    assert geom["pattern_name"] == "SOLID"
    assert len(geom["loops"]) == 1
    loop = geom["loops"][0]
    assert loop["status"] == "ok"
    assert loop["vertices"] == [
        {"point": [0.0, 0.0, 0.0], "bulge": 0.0}, {"point": [10.0, 0.0, 0.0], "bulge": 0.0},
        {"point": [10.0, 10.0, 0.0], "bulge": 0.0}, {"point": [0.0, 10.0, 0.0], "bulge": 0.0},
    ]


def test_expect_hatch_defaults_layer_to_zero():
    ent = al.expect_hatch({"vertices": [{"x": 0, "y": 0}]})
    assert ent["layer"] == "0"


def test_expect_hatch_loop_type_is_overridable():
    """loop_type is an OBSERVED runtime fact (this wave's live attended run),
    not a documented API guarantee -- must stay a parameter, not a constant,
    so a future AutoCAD version's different classification doesn't require
    editing the function body."""
    ent = al.expect_hatch({"vertices": [{"x": 0, "y": 0}]}, loop_type=99)
    assert ent["geometry"]["loops"][0]["loop_type"] == 99


# ========================================================================== #
# 3. tiny PNG fixture -- pure, stdlib-only (no Pillow dependency)
# ========================================================================== #

def test_make_tiny_png_bytes_is_a_valid_png():
    data = al.make_tiny_png_bytes(width=4, height=4, rgb=(255, 255, 255))
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"IHDR" in data[:20]
    assert data.endswith(b"IEND\xaeB`\x82")  # fixed CRC for an empty IEND chunk


def test_ensure_tiny_png_creates_and_is_idempotent(tmp_path):
    target = tmp_path / "sub" / "tiny.png"
    p1 = al.ensure_tiny_png(str(target))
    assert os.path.isfile(p1)
    first_bytes = Path(p1).read_bytes()
    p2 = al.ensure_tiny_png(str(target))  # second call must not raise / must not truncate
    assert Path(p2).read_bytes() == first_bytes


# ========================================================================== #
# 4. run_attended_native_job -- command construction + result parsing, via a
#    monkeypatched subprocess.run (never a real launch in this suite).
# ========================================================================== #

def test_run_attended_native_job_missing_launcher_is_truthful(tmp_path):
    """No fake success: a missing launcher script must report status via
    `error`, never silently return as if a job ran."""
    res = al.run_attended_native_job(
        str(tmp_path / "staged.dwg"), str(tmp_path / "run"), "write.entity.hatch", {},
        ps1_launcher=str(tmp_path / "does_not_exist.ps1"))
    assert res["error"] is not None
    assert res["result"] is None
    assert res["staged_used"] is None


def test_run_attended_native_job_builds_expected_command_and_parses_result(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    staged = tmp_path / "staged.dwg"
    staged.write_bytes(b"fake-dwg")
    launcher = tmp_path / "run_attended_job.ps1"
    launcher.write_text("# stub, never executed in this test\n", encoding="utf-8")

    captured = {}
    native = {
        "schema": "ariadne.autocad_native_job_result.v1",
        "status": "ok",
        "result": {"created": True, "handle": "ABCD"},
    }

    class _FakeProc:
        """Stand-in for the Popen object run_attended_native_job() now uses
        (NOT subprocess.run -- see the comment at the real call site: the
        launcher's own post-job bookkeeping can stall for minutes on this box
        even after the CAD job itself succeeded, so the runner polls for
        job_out.json/final receipt directly instead of blocking on
        the child process's exit). returncode=0 means "already exited" so the
        very first poll-loop iteration (which finds the final receipt
        already on disk, written below) breaks out immediately."""
        def __init__(self):
            self.returncode = 0
        def poll(self):
            return self.returncode
        def kill(self):
            pass
        def wait(self, timeout=None):
            pass

    def fake_popen(cmd, cwd, stdout, stderr, text, encoding, errors):
        captured["cmd"] = cmd
        stdout.write("ok\n")
        # The final launcher receipt is compact; the full native payload lives
        # in job_out.json and is read by the Python side only after cleanup is
        # certified.
        job_out = run_dir / "job_out.json"
        job_out.write_text(json.dumps(native), encoding="utf-8")
        (run_dir / "attended_job_final_receipt.json").write_text(
            json.dumps(_final_attended_receipt("write.entity.hatch", job_out)),
            encoding="utf-8",
        )
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    res = al.run_attended_native_job(str(staged), str(run_dir), "write.entity.hatch",
                                     {"layer": "L1", "vertices": [{"x": 0, "y": 0, "z": 0}]},
                                     timeout=99, ps1_launcher=str(launcher))

    cmd = captured["cmd"]
    assert "-StagedDwg" in cmd and str(staged) in cmd
    assert "-Operation" in cmd and "write.entity.hatch" in cmd
    assert "-TimeoutSec" in cmd and "99" in cmd
    job_args_idx = cmd.index("-JobArgsJson") + 1
    job_args = json.loads(cmd[job_args_idx])
    assert job_args == {"operation": "write.entity.hatch", "layer": "L1",
                        "vertices": [{"x": 0, "y": 0, "z": 0}]}

    assert res["error"] is None
    assert res["staged_used"] == str(staged)
    assert res["result"] == native
    assert res["timed_out"] is False
    assert res["degraded"] is False


def test_run_attended_native_job_threads_isolated_native_bin_dir(tmp_path, monkeypatch):
    """A proof build must be selected explicitly; falling through to a stale
    sibling/prebuilt ARX would invalidate an attended experiment."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    staged = tmp_path / "staged.dwg"
    staged.write_bytes(b"fake-dwg")
    launcher = tmp_path / "run_attended_job.ps1"
    launcher.write_text("# stub\n", encoding="utf-8")
    native_bin = tmp_path / "proof-bin"
    native_bin.mkdir()
    captured = {}

    class _FakeProc:
        returncode = 0

        def poll(self):
            return self.returncode

        def kill(self):
            pass

        def wait(self, timeout=None):
            pass

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        job_out = run_dir / "job_out.json"
        job_out.write_text(json.dumps({"status": "ok", "result": {"status": "ok"}}), encoding="utf-8")
        (run_dir / "attended_job_final_receipt.json").write_text(
            json.dumps(_final_attended_receipt("e2.inspect.xclip_membership", job_out)),
            encoding="utf-8",
        )
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    al.run_attended_native_job(
        str(staged),
        str(run_dir),
        "e2.inspect.xclip_membership",
        {"target_layers": ["W1"]},
        native_bin_dir=str(native_bin),
        ps1_launcher=str(launcher),
    )

    cmd = captured["cmd"]
    assert "-NativeBinDir" in cmd
    assert cmd[cmd.index("-NativeBinDir") + 1] == str(native_bin)


def test_run_attended_native_job_reports_gate1_block_as_error(tmp_path, monkeypatch):
    """A GATE1 (dedicated-instance) failure must surface as a truthful error,
    never as staged_used-present success."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    launcher = tmp_path / "run_attended_job.ps1"
    launcher.write_text("# stub\n", encoding="utf-8")

    class _FakeProc:
        def __init__(self):
            self.returncode = 9
        def poll(self):
            return self.returncode
        def kill(self):
            pass
        def wait(self, timeout=None):
            pass

    def fake_popen(cmd, **kw):
        (run_dir / "attended_job_final_receipt.json").write_text(json.dumps({
            "status": "blocked", "error": "GATE1 FAIL: launched PID collides", "launched_pid": 1234,
        }), encoding="utf-8")
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    res = al.run_attended_native_job(str(tmp_path / "staged.dwg"), str(run_dir),
                                     "write.entity.hatch", {}, ps1_launcher=str(launcher))
    assert res["error"] is not None and "GATE1" in res["error"]
    assert res["staged_used"] is None


def test_run_attended_native_job_waits_for_final_receipt_after_completion_signal(tmp_path, monkeypatch):
    """A compact completion receipt arrives before cleanup, then the final
    receipt follows after the old 30-second fallback boundary. The Python
    caller must not kill the launcher or switch to a degraded reconstruction
    while the bounded cleanup window remains open."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    launcher = tmp_path / "run_attended_job.ps1"
    launcher.write_text("# stub\n", encoding="utf-8")

    job_out = run_dir / "job_out.json"
    native = {
        "schema": "ariadne.autocad_native_job_result.v1", "status": "ok",
        "result": {"created": True, "class": "AcDbHatch", "handle": "19191"},
    }
    job_out.write_text(json.dumps(native), encoding="utf-8")
    (run_dir / "attended_job_completion.json").write_text(
        json.dumps(_completion_receipt("write.entity.hatch", job_out, cleanup_wait_sec=45)),
        encoding="utf-8",
    )

    class _FakeProc:
        """Cleanup is still running until the final receipt is written."""
        killed = False

        def poll(self):
            return None

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            pass

    proc = _FakeProc()
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)

    # The final receipt lands after 31 seconds, deliberately later than the
    # old raw-job_out fallback threshold but inside the receipt's 45-second
    # cleanup budget.
    clock = {"t": 1_000_000.0}
    monkeypatch.setattr(al.time, "monotonic", lambda: clock["t"])

    def advance_clock(seconds):
        clock["t"] += seconds
        if clock["t"] >= 1_000_031.0 and not (run_dir / "attended_job_final_receipt.json").exists():
            (run_dir / "attended_job_final_receipt.json").write_text(
                json.dumps(_final_attended_receipt("write.entity.hatch", job_out)),
                encoding="utf-8",
            )

    monkeypatch.setattr(al.time, "sleep", advance_clock)

    res = al.run_attended_native_job(str(tmp_path / "staged.dwg"), str(run_dir),
                                     "write.entity.hatch", {}, timeout=60, ps1_launcher=str(launcher))

    assert proc.killed is False
    assert res["degraded"] is False
    assert res["timed_out"] is False
    assert res["error"] is None
    assert res["result"] == native
    assert res["envelope"]["security"]["restored"] is True
    assert res["staged_used"] == str(tmp_path / "staged.dwg")


def test_run_attended_native_job_rejects_completion_without_final_safety_receipt(tmp_path, monkeypatch):
    """A native job output plus pre-cleanup receipt cannot become success.

    It lacks proof that the dedicated process was closed, the user's sessions
    were untouched, and SECURELOAD/TRUSTEDPATHS were restored.
    """
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    launcher = tmp_path / "run_attended_job.ps1"
    launcher.write_text("# stub\n", encoding="utf-8")
    job_out = run_dir / "job_out.json"
    job_out.write_text(json.dumps({"status": "ok", "result": {"created": True}}), encoding="utf-8")
    (run_dir / "attended_job_completion.json").write_text(
        json.dumps(_completion_receipt("write.entity.hatch", job_out, cleanup_wait_sec=5)),
        encoding="utf-8",
    )

    class _FakeProc:
        killed = False

        def poll(self):
            return None

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            pass

    proc = _FakeProc()
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)
    clock = {"t": 1_000_000.0}
    monkeypatch.setattr(al.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(al.time, "sleep", lambda s: clock.__setitem__("t", clock["t"] + s))

    res = al.run_attended_native_job(str(tmp_path / "staged.dwg"), str(run_dir),
                                     "write.entity.hatch", {}, timeout=60, ps1_launcher=str(launcher))

    assert proc.killed is True
    assert res["degraded"] is False
    assert res["timed_out"] is False
    assert res["envelope"] is None
    assert res["result"] is None
    assert res["staged_used"] is None
    assert res["error"] is not None and "final" in res["error"].lower()


def test_run_attended_native_job_recovers_final_receipt_only_after_independent_cleanup_checks(
    tmp_path, monkeypatch
):
    """When PowerShell stalls after cleanup, Python may finish the receipt only
    from independently observable facts: the launched PID is gone, every
    pre-existing PID remains, and both security values were restored."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    launcher = tmp_path / "run_attended_job.ps1"
    launcher.write_text("# stub\n", encoding="utf-8")
    job_out = run_dir / "job_out.json"
    native = {"schema": "ariadne.autocad_native_job_result.v1", "status": "ok", "result": {"created": True}}
    job_out.write_text(json.dumps(native), encoding="utf-8")
    (run_dir / "security_before.txt").write_text("0\nC:/trusted\n", encoding="utf-8")
    (run_dir / "security_after.txt").write_text("0\nC:/trusted\n", encoding="utf-8")
    completion = _completion_receipt("write.entity.hatch", job_out, cleanup_wait_sec=1)
    completion["launched_pid"] = 4242
    completion["pre_existing_pids"] = [3131]
    completion["pre_existing_processes"] = [{
        "pid": 3131,
        "process_name": "acad",
        "start_time_utc": "2026-08-10T00:00:01.0000000Z",
    }]
    (run_dir / "attended_job_completion.json").write_text(json.dumps(completion), encoding="utf-8")

    class _FakeProc:
        def __init__(self):
            self.killed = False

        def poll(self):
            return 0 if self.killed else None

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            pass

    proc = _FakeProc()
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)
    monkeypatch.setattr(
        al,
        "_query_process_identities",
        lambda pids: {
            4242: {
                "pid": 4242,
                "known": True,
                "present": False,
                "process_name": None,
                "start_time_utc": None,
            },
            3131: {
                "pid": 3131,
                "known": True,
                "present": True,
                "process_name": "acad",
                "start_time_utc": "2026-08-10T00:00:01.0000000Z",
            },
        },
    )
    clock = {"t": 1_000_000.0}
    monkeypatch.setattr(al.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(al.time, "sleep", lambda seconds: clock.__setitem__("t", clock["t"] + seconds))

    res = al.run_attended_native_job(str(tmp_path / "staged.dwg"), str(run_dir),
                                     "write.entity.hatch", {}, timeout=60, ps1_launcher=str(launcher))

    assert proc.killed is True
    assert res["error"] is None
    assert res["degraded"] is False
    assert res["staged_used"] == str(tmp_path / "staged.dwg")
    assert res["result"] == native
    assert res["envelope"]["phase"] == "finalized"
    assert res["envelope"]["receipt_authority"] == "python_independent_safety_validator"
    assert res["envelope"]["recovered_from_launcher_finalization_hang"] is True
    assert res["envelope"]["powershell_helper_closed"] is True
    assert res["envelope"]["launched_pid_identity_verified"] is True
    assert res["envelope"]["pre_existing_identity_verified"] is True
    assert res["envelope"]["pre_existing_still_alive"] == [3131]
    assert res["envelope"]["security"]["restored"] is True
    assert (run_dir / "attended_job_final_receipt.json").is_file()


def test_independent_recovery_blocks_when_process_identity_is_unknown(tmp_path, monkeypatch):
    """A failed or ambiguous identity lookup is a blocker, never an absent
    process.  This pins the no-false-PASS branch independently of Popen."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    job_out = run_dir / "job_out.json"
    job_out.write_text(json.dumps({"status": "ok", "result": {}}), encoding="utf-8")
    (run_dir / "security_before.txt").write_text("0\nC:/trusted\n", encoding="utf-8")
    (run_dir / "security_after.txt").write_text("0\nC:/trusted\n", encoding="utf-8")
    completion = _completion_receipt("write.entity.hatch", job_out)
    monkeypatch.setattr(al, "_query_process_identities", lambda pids: None)

    receipt, error = al._build_independent_recovery_receipt(
        completion=completion,
        completion_path=run_dir / "attended_job_completion.json",
        final_path=run_dir / "attended_job_final_receipt.json",
        job_out_path=job_out,
        security_before_path=run_dir / "security_before.txt",
        security_after_path=run_dir / "security_after.txt",
    )

    assert receipt is None
    assert error is not None and "unknown" in error


def test_run_attended_native_job_genuine_timeout_when_neither_file_appears(tmp_path, monkeypatch):
    """No fake success on the OTHER side either: if the CAD job produced
    NEITHER job_out.json NOR a final launcher receipt before the outer
    deadline, that is a real timeout, not a degraded-but-ok result."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    launcher = tmp_path / "run_attended_job.ps1"
    launcher.write_text("# stub\n", encoding="utf-8")

    class _FakeProc:
        def poll(self):
            return None
        def kill(self):
            pass
        def wait(self, timeout=None):
            pass

    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: _FakeProc())
    clock = {"t": 1_000_000.0}
    monkeypatch.setattr(al.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(al.time, "sleep", lambda s: clock.__setitem__("t", clock["t"] + s))

    res = al.run_attended_native_job(str(tmp_path / "staged.dwg"), str(run_dir),
                                     "write.entity.hatch", {}, timeout=10, ps1_launcher=str(launcher))

    assert res["timed_out"] is True
    assert res["degraded"] is False
    assert res["error"] is not None
    assert res["staged_used"] is None
    assert res["result"] is None


# ========================================================================== #
# 5. attended_apply_staged -- orchestration, via INJECTED fake siblings
#    (mirrors op_roundtrip_probe.py's own apply_staged= injection pattern;
#    no accoreconsole/AutoCAD ever invoked in this suite).
# ========================================================================== #

class _FakePatchEngine:
    def __init__(self, staged_ok=True):
        self.staged_ok = staged_ok

    def create_staged_copy(self, dwg_path, out_dir):
        if not self.staged_ok:
            return {"ok": False, "reason": "input DWG not found"}
        staged_path = os.path.join(out_dir, "staged_input.dwg")
        os.makedirs(out_dir, exist_ok=True)
        Path(staged_path).write_bytes(b"fake-staged-dwg")  # attended_apply_staged's
        # shutil.copy2(apply_run["staged_used"], staged_output) needs a REAL file here.
        return {"ok": True, "staged_path": staged_path,
                "original_path": os.path.abspath(dwg_path), "original_sha256": "deadbeef"}

    def _native_full_ir(self, ir_builder, run_res, staged_path, original_path, ir_out_path, phase):
        if run_res.get("error"):
            return {"ok": False, "reason": run_res["error"]}
        Path(ir_out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(ir_out_path).write_text(json.dumps({"schema": "ariadne.dwg_graph_ir.v1", "entities": []}),
                                     encoding="utf-8")
        return {"ok": True, "ir_path": ir_out_path, "entity_count": 0}


class _FakeRunJob:
    def run_router_cad_job(self, staged_dwg, run_dir, operation, write_mode="read"):
        return {"result": {"entities": []}, "exit_code": 0, "stdout_path": None,
                "stderr_path": None, "error": None}


def test_attended_apply_staged_reports_blocked_when_staging_fails(tmp_path):
    res = al.attended_apply_staged(
        "write.entity.hatch", {}, str(tmp_path / "missing.dwg"), str(tmp_path / "out"),
        patch_engine_mod=_FakePatchEngine(staged_ok=False), run_job_mod=_FakeRunJob(),
        ir_builder_mod=object())
    assert res["status"] == "blocked"
    assert "reason" in res


def test_attended_apply_staged_success_path_never_touches_attended_when_faked(tmp_path, monkeypatch):
    dwg = tmp_path / "orig.dwg"
    dwg.write_bytes(b"fake")

    def fake_attended_job(staged_dwg, run_dir, operation, args, **kw):
        return {"error": None, "staged_used": staged_dwg, "envelope": {"status": "ok"}, "result": {}}

    monkeypatch.setattr(al, "run_attended_native_job", fake_attended_job)
    res = al.attended_apply_staged(
        "write.entity.hatch", {"layer": "L1"}, str(dwg), str(tmp_path / "out"),
        patch_engine_mod=_FakePatchEngine(), run_job_mod=_FakeRunJob(), ir_builder_mod=object())
    assert res["status"] == "ok"
    assert res["pre_ir"] and res["post_ir"]
    assert os.path.isfile(res["pre_ir"]) and os.path.isfile(res["post_ir"])
    assert res["original_unchanged"]["original_path"] == str(dwg.resolve()) or \
        res["original_unchanged"]["original_path"] == os.path.abspath(str(dwg))


def test_attended_apply_staged_surfaces_attended_failure_truthfully(tmp_path, monkeypatch):
    dwg = tmp_path / "orig.dwg"
    dwg.write_bytes(b"fake")

    def fake_attended_job_fails(staged_dwg, run_dir, operation, args, **kw):
        return {"error": "attended launcher missing", "staged_used": None, "envelope": None, "result": None}

    monkeypatch.setattr(al, "run_attended_native_job", fake_attended_job_fails)
    res = al.attended_apply_staged(
        "write.entity.hatch", {}, str(dwg), str(tmp_path / "out"),
        patch_engine_mod=_FakePatchEngine(), run_job_mod=_FakeRunJob(), ir_builder_mod=object())
    assert res["status"] == "unavailable"
    assert "attended launcher missing" in res["reason"]


# ========================================================================== #
# 6. lane_proof / attended_roundtrip -- judge logic, via a fake
#    attended_apply_staged (isolates the diff/gate wiring from the
#    orchestration already covered above).
# ========================================================================== #

def _write_ir(path, entities):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({"schema": al.IR_SCHEMA_ID, "entities": entities}), encoding="utf-8")
    return str(path)


def test_lane_proof_detects_net_added_entity(tmp_path, monkeypatch):
    pre = _write_ir(tmp_path / "pre.json", [])
    post = _write_ir(tmp_path / "post.json",
                     [{"handle": "1A", "dxf_name": "HATCH", "layer": "L1", "owner_handle": "0", "space": "model"}])

    def fake_apply(operation, args, dwg_path, out_dir, **kw):
        return {"status": "ok", "pre_ir": pre, "post_ir": post,
                "pre_entity_count": 0, "post_entity_count": 1, "original_unchanged": {"unchanged": True}}

    monkeypatch.setattr(al, "attended_apply_staged", fake_apply)
    res = al.lane_proof("write.entity.hatch", {}, "dummy.dwg", str(tmp_path),
                        expected_dxf_name="HATCH", expected_layer="L1")
    assert res["status"] == "ok"
    assert res["net_added"] == 1
    assert res["added_entities"][0]["handle"] == "1A"


def test_lane_proof_fails_when_expected_dxf_name_absent(tmp_path, monkeypatch):
    pre = _write_ir(tmp_path / "pre.json", [])
    post = _write_ir(tmp_path / "post.json",
                     [{"handle": "1A", "dxf_name": "LINE", "layer": "L1", "owner_handle": "0", "space": "model"}])

    def fake_apply(operation, args, dwg_path, out_dir, **kw):
        return {"status": "ok", "pre_ir": pre, "post_ir": post}

    monkeypatch.setattr(al, "attended_apply_staged", fake_apply)
    res = al.lane_proof("write.entity.hatch", {}, "dummy.dwg", str(tmp_path), expected_dxf_name="HATCH")
    assert res["status"] == "fail"


def test_lane_proof_propagates_non_ok_envelope_without_a_diff(tmp_path, monkeypatch):
    def fake_apply(operation, args, dwg_path, out_dir, **kw):
        return {"status": "unavailable", "reason": "attended launcher missing"}

    monkeypatch.setattr(al, "attended_apply_staged", fake_apply)
    res = al.lane_proof("write.entity.rasterimage", {}, "dummy.dwg", str(tmp_path))
    assert res["status"] == "unavailable"
    assert res["reason"] == "attended launcher missing"


def test_attended_roundtrip_geometry_match_passes(tmp_path, monkeypatch):
    expected = al.expect_hatch({"layer": "L1", "vertices": [{"x": 0, "y": 0, "z": 0}, {"x": 1, "y": 0, "z": 0},
                                                            {"x": 1, "y": 1, "z": 0}]})
    actual_entity = {"handle": "1A", "dxf_name": "HATCH", "layer": "L1", "owner_handle": "0", "space": "model",
                     "geometry": expected["geometry"]}
    pre = _write_ir(tmp_path / "pre.json", [])
    post = _write_ir(tmp_path / "post.json", [actual_entity])

    def fake_apply(operation, args, dwg_path, out_dir, **kw):
        return {"status": "ok", "pre_ir": pre, "post_ir": post, "original_unchanged": {"unchanged": True}}

    monkeypatch.setattr(al, "attended_apply_staged", fake_apply)
    res = al.attended_roundtrip("write.entity.hatch", {"layer": "L1"}, "dummy.dwg", str(tmp_path), expected)
    assert res["status"] == "ok"


def test_attended_roundtrip_geometry_mismatch_fails(tmp_path, monkeypatch):
    expected = al.expect_hatch({"layer": "L1", "vertices": [{"x": 0, "y": 0, "z": 0}, {"x": 1, "y": 0, "z": 0},
                                                            {"x": 1, "y": 1, "z": 0}]})
    wrong_entity = {"handle": "1A", "dxf_name": "HATCH", "layer": "L1", "owner_handle": "0", "space": "model",
                    "geometry": {"kind": "hatch", "pattern_name": "SOLID",
                                "loops": [{"index": 0, "loop_type": 3, "status": "ok",
                                          "vertices": [{"point": [9, 9, 0], "bulge": 0.0}]}]}}
    pre = _write_ir(tmp_path / "pre.json", [])
    post = _write_ir(tmp_path / "post.json", [wrong_entity])

    def fake_apply(operation, args, dwg_path, out_dir, **kw):
        return {"status": "ok", "pre_ir": pre, "post_ir": post, "original_unchanged": {"unchanged": True}}

    monkeypatch.setattr(al, "attended_apply_staged", fake_apply)
    res = al.attended_roundtrip("write.entity.hatch", {"layer": "L1"}, "dummy.dwg", str(tmp_path), expected)
    assert res["status"] == "fail"


# ========================================================================== #
# 7. run_attended_job.ps1 -- source-presence guards (cannot execute without a
#    live editor; mirrors test_m07b_pump_gating_and_job_channel.py's convention)
# ========================================================================== #

@pytest.fixture(scope="module")
def ps1_src() -> str:
    assert PS1_LAUNCHER.is_file(), f"attended launcher missing: {PS1_LAUNCHER}"
    return PS1_LAUNCHER.read_text(encoding="utf-8-sig")


def test_ps1_restores_security_settings_not_just_sets_them(ps1_src: str):
    """The M07B attended harness set SECURELOAD=0 and appended TRUSTEDPATHS but
    never restored them, permanently weakening the AutoCAD profile. This
    wave's whole point is fixing that: both values must be read BEFORE the
    change and set back to their ORIGINAL values before QUIT."""
    assert '(setq _ariadneOsl (getvar "SECURELOAD"))' in ps1_src
    assert '(setq _ariadneOtp (getvar "TRUSTEDPATHS"))' in ps1_src
    assert '(setvar "SECURELOAD" _ariadneOsl)' in ps1_src
    assert '(setvar "TRUSTEDPATHS" _ariadneOtp)' in ps1_src
    # both before AND after values are logged to disk for evidence
    assert "security_before.txt" in ps1_src
    assert "security_after.txt" in ps1_src


def test_ps1_uses_the_env_file_job_channel_and_persists_the_write(ps1_src: str):
    assert "ARIADNE_NATIVE_JOB_ARGS" in ps1_src
    assert "_QSAVE" in ps1_src
    assert "_QUIT" in ps1_src


def test_ps1_sets_the_job_args_env_var_before_launch(ps1_src: str):
    """Regression guard for a real hang found in this wave's first live run:
    Start-Process only inherits env vars set in the CALLING process at launch
    time -- writing live_job_args.json to disk is not enough. Without
    $env:ARIADNE_NATIVE_JOB_ARGS set before Start-Process, the AutoCAD command
    falls back to its documented interactive prompt and hangs indefinitely
    (nothing ever answers it). Must appear BEFORE the Start-Process call, and
    must be cleared during teardown so it never leaks into another launch."""
    env_set_idx = ps1_src.index("$env:ARIADNE_NATIVE_JOB_ARGS = $argsF")
    launch_idx = ps1_src.index("Start-Process -FilePath $AcadExe")
    assert env_set_idx < launch_idx, "env var must be set BEFORE Start-Process, not merely written to disk"
    assert "$env:ARIADNE_NATIVE_JOB_ARGS = $null" in ps1_src


def test_ps1_never_attaches_to_a_pre_existing_session(ps1_src: str):
    """Gate 1: record pre-existing acad PIDs BEFORE launch; abort without
    driving if the launched PID somehow collides; only ever Stop-Process the
    launched PID, never a pre-existing one."""
    assert "$preProcesses = @(" in ps1_src
    assert "Get-Process acad -ErrorAction SilentlyContinue" in ps1_src
    assert "start_time_utc = $started" in ps1_src
    assert "$dedicatedOk = ($preIds -notcontains $launchedPid)" in ps1_src
    assert "Stop-Process -Id $launchedPid -Force" in ps1_src


def test_ps1_has_a_hard_timeout_and_taskkill_fallback(ps1_src: str):
    assert "TimeoutSec" in ps1_src
    assert "$timedOut" in ps1_src
    assert "taskkill fallback" in ps1_src


def test_ps1_teardown_prefers_the_launched_process_handle_and_bounds_taskkill(ps1_src: str):
    """An exited Process object is stronger evidence than a numeric PID, which
    can be reused. The fallback must also be bounded so it cannot postpone the
    final safety receipt indefinitely."""
    assert "if ($null -ne $proc)" in ps1_src
    assert "$stillRunning = -not $proc.HasExited" in ps1_src
    assert "$taskkillProc.WaitForExit(10000)" in ps1_src
    assert "$launchedExited = $false" in ps1_src
    assert "$launchedExited = $proc.HasExited" in ps1_src


def test_ps1_writes_a_compact_atomic_completion_receipt_before_cleanup(ps1_src: str):
    """The early receipt buys cleanup time, but never carries enough data to
    be mistaken for the final launcher safety result."""
    assert "function WriteJsonAtomic" in ps1_src
    assert "$completionReceipt = Join-Path $RunDir 'attended_job_completion.json'" in ps1_src
    assert "$finalReceipt = Join-Path $RunDir 'attended_job_final_receipt.json'" in ps1_src
    assert "schema = 'ariadne.cad_os.attended_job_completion.v1'" in ps1_src
    assert "phase = 'cleanup_pending'" in ps1_src
    assert "launched_start_time_utc = $launchedStartTimeUtc" in ps1_src
    assert "pre_existing_pids = $preIds" in ps1_src
    assert "pre_existing_processes = $preProcesses" in ps1_src
    assert "cleanup_wait_sec = $completionCleanupWaitSec" in ps1_src
    assert "WriteJsonAtomic $completion $completionReceipt" in ps1_src
    assert ps1_src.index("WriteJsonAtomic $completion $completionReceipt") < ps1_src.index(
        "# ---- teardown: close ONLY the launched PID"
    )
    assert "result = $jobOutObj" not in ps1_src
    assert "phase = 'finalized'" in ps1_src
    assert "receipt_authority = 'powershell_launcher'" in ps1_src


def test_ps1_loads_the_canonical_prebuilt_modules(ps1_src: str):
    """Attended (full acad.exe) loads .dbx + .arx -- NOT .crx, which M07B's
    own docs mark as the coreconsole-only variant."""
    assert "prebuilt\\2027\\Ariadne.AcadNativeDbx.dbx" in ps1_src
    assert "prebuilt\\2027\\Ariadne.AcadNative.arx" in ps1_src
    assert ".crx" not in ps1_src


# ========================================================================== #
# 8. genuine end-to-end proof -- CADOS_LIVE=1 + acad.exe present only.
#    Skipped by default with an explicit reason; never a silent/fake pass.
# ========================================================================== #

_GOLDEN_DWG = str(ROOT / "tests" / "fixtures" / "native_sample.dwg")
_ACAD_EXE = al.DEFAULT_ACAD_EXE


def _attended_live_available() -> bool:
    return (os.environ.get("CADOS_LIVE") == "1"
            and os.path.isfile(_ACAD_EXE)
            and os.path.isfile(_GOLDEN_DWG))


def _attended_live_skip_reason() -> str:
    reasons = []
    if os.environ.get("CADOS_LIVE") != "1":
        reasons.append("CADOS_LIVE!=1")
    if not os.path.isfile(_ACAD_EXE):
        reasons.append("acad.exe not found")
    if not os.path.isfile(_GOLDEN_DWG):
        reasons.append("golden fixture missing")
    return "attended live smoke skipped: " + ", ".join(reasons)


@pytest.mark.skipif(not _attended_live_available(), reason=_attended_live_skip_reason())
def test_attended_hatch_full_cert_live(tmp_path):
    """The genuine live proof: create.entity.hatch inside a REAL dedicated
    acad.exe, re-extract headless, geometry-basis diff=0. Golden DWG must be
    byte-unchanged after."""
    import hashlib

    def _sha256(path):
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    sha_before = _sha256(_GOLDEN_DWG)
    args = {"layer": "ARIADNE_LIVE_TEST_HATCH",
           "vertices": [{"x": 0.0, "y": 0.0, "z": 0.0}, {"x": 50.0, "y": 0.0, "z": 0.0},
                        {"x": 50.0, "y": 50.0, "z": 0.0}, {"x": 0.0, "y": 50.0, "z": 0.0}]}
    expected = al.expect_hatch(args)
    res = al.attended_roundtrip("write.entity.hatch", args, _GOLDEN_DWG, str(tmp_path / "run"), expected)
    assert res["status"] == "ok", res.get("reason") or res
    assert res["original_unchanged"]["unchanged"] is True
    assert _sha256(_GOLDEN_DWG) == sha_before
