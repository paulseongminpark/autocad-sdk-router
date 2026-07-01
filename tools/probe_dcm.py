#!/usr/bin/env python
"""
probe_dcm.py -- Live headless-DCM (dimensional/geometric constraint solver)
availability probe under accoreconsole [DCM probe -- v2-A5].

WHY this exists (a precondition, not a feature):
Several future Wave-0 nodes intend to claim "resolved geometry-diff=0"
acceptance for constraint-bearing operations (AcDbAssoc2dConstraintGroup /
AcDbAssocManager::evaluateTopLevelNetwork -- see
research/native_arx/constraints-associativity.md). That solver ("DCM") is
native/host-only: reachable from a full AutoCAD host or accoreconsole, but NOT
from a standalone RealDWG process (out of scope/excluded per the same doc).
This probe answers, with LIVE evidence (never a guess), whether the installed
accoreconsole on THIS machine can actually evaluate it headless.

METHOD (the only trustworthy AutoLISP-visible signal -- getDOF()/
solutionStatus()/constraintStatus() are native-or-managed-only per the research
doc, unreachable from script):
  1. Draw one LINE deliberately NOT horizontal (endpoints differ in Y).
  2. Select it via an explicit ssadd pickset -- verified this session to be the
     reliable selection form; a raw entity name or an (entity point) list was
     NOT reliably accepted by the single-object constraint-select prompt
     (GCHORIZONTAL) under accoreconsole and is not used here.
  3. Run AUTOCONSTRAIN on that one-entity selection.
  4. Read the endpoints back. If the solver ran, AutoCAD infers and applies a
     Horizontal geometric constraint and evaluates the network -- the two
     endpoints' Y values become EXACTLY equal. If unchanged, the solver did not
     fire.

This is a real geometry-diff -- exactly the primitive the Wave-0 P-gate is
built on (see the Wave-0 planning doc outside this repo:
D:/dev/.build/cados_plan/harden/H3_verification_gates.md section 3) -- not a
simulation of one.

Safety / no-fake-success:
  * The fixture DWG is READ-ONLY; every run works on a fresh ASCII-staged copy
    in a temp dir, and the script always QUITs without saving (matches
    tools/probe_routes.py / tools/autocad-router.ps1 Invoke-AccoreScr
    discipline -- see also Get-AutoLispExtractScr for the .lsp/.scr shape this
    mirrors).
  * If accoreconsole cannot be found on this machine, the probe does NOT
    attempt a run and does NOT claim availability either way -- it reports
    runtime_available=false plus the exact deferred command a runtime-having
    machine should run.
  * If accoreconsole runs but the result file is missing, or the "before"
    state was not actually non-horizontal (the probe's own test geometry
    misbehaved), the verdict is available=None ("inconclusive") -- never a
    fabricated true/false.

Usage:
    python probe_dcm.py [--out <path>] [--engine <accoreconsole.exe>]
                        [--fixture <dwg>] [--timeout <sec>] [--keep-stage]

No side effects on the original fixture DWG. Read-only.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROUTER_HOME = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROUTER_HOME / "tests" / "fixtures" / "native_sample.dwg"

# Deliberately non-horizontal by an amount empirically confirmed (this session,
# accoreconsole "X.60.0.0" / AutoCAD 2027, against DEFAULT_FIXTURE) to fall
# inside AUTOCONSTRAIN's default angular tolerance -- see report.md for the
# live transcript this was derived from. Not a guess.
LINE_P1 = (0.0, 0.0, 0.0)
LINE_P2 = (10.0, 0.02, 0.0)
GEOMETRY_TOL = 1e-6

ENV_OUT = "ARIADNE_DCM_PROBE_OUT"
LISP_DEFUN = "ARIADNE_DCM_PROBE"


def _detect_accoreconsole_candidates() -> list[str]:
    """Version-agnostic accoreconsole discovery.

    Deliberately self-contained rather than imported from tools/probe_routes.py
    -- this repo's existing convention is per-tool detection, not a shared
    import (tools/probe_routes.py._detect_accoreconsole_candidates and
    tools/autocad-router.ps1 Resolve-AcadEnginePath each duplicate the same
    resolution order independently rather than share a module).
    """
    cands: list[str] = []
    env = os.environ.get("ARIADNE_ACAD_ENGINE_PATH")
    if env:
        cands.append(env)
    seen = set()
    for base in (os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles"), r"C:\Program Files"):
        if not base:
            continue
        adsk = os.path.join(base, "Autodesk")
        for d in sorted(glob.glob(os.path.join(adsk, "AutoCAD 20*")), reverse=True):
            exe = os.path.join(d, "accoreconsole.exe")
            if exe not in seen:
                seen.add(exe)
                cands.append(exe)
    cands += ["accoreconsole.exe", "accoreconsole"]
    return cands


def find_accoreconsole(candidates: list[str] | None = None) -> str | None:
    """``candidates`` is an injection seam for tests (a controlled candidate
    list) -- defaults to the real, version-agnostic auto-detection."""
    for c in (candidates if candidates is not None else _detect_accoreconsole_candidates()):
        if os.path.isabs(c):
            if os.path.exists(c):
                return c
        else:
            found = shutil.which(c)
            if found:
                return found
    return None


def _build_lisp_text() -> str:
    """AutoLISP that draws one non-horizontal LINE, AUTOCONSTRAINs it alone,
    and writes the before/after endpoints as plain ``key=value`` lines.

    Not JSON: this file is a private intermediate consumed only by this
    script's own parser, so it avoids fighting AutoLISP string-escaping (the
    router's JSON-emitting scripts only ever quote string fields, never
    coordinates -- see Get-AutoLispExtractScr in tools/autocad-router.ps1).
    """
    x1, y1, z1 = LINE_P1
    x2, y2, z2 = LINE_P2
    lines = [
        f"(defun c:{LISP_DEFUN} (/ out f p1 p2 ln ed ss bx1 by1 bx2 by2 ax1 ay1 ax2 ay2)",
        f'  (setq out (getenv "{ENV_OUT}"))',
        '  (if (or (null out) (= out "")) (setq out "dcm_probe_result.txt"))',
        f"  (setq p1 (list {x1} {y1} {z1}))",
        f"  (setq p2 (list {x2} {y2} {z2}))",
        '  (command "_.LINE" p1 p2 "")',
        "  (setq ln (entlast))",
        "  (setq ed (entget ln))",
        "  (setq bx1 (car (cdr (assoc 10 ed))))",
        "  (setq by1 (cadr (cdr (assoc 10 ed))))",
        "  (setq bx2 (car (cdr (assoc 11 ed))))",
        "  (setq by2 (cadr (cdr (assoc 11 ed))))",
        "  (setq ss (ssadd))",
        "  (setq ss (ssadd ln ss))",
        '  (command "_.AUTOCONSTRAIN" ss "")',
        "  (command)",
        "  (setq ed (entget ln))",
        "  (setq ax1 (car (cdr (assoc 10 ed))))",
        "  (setq ay1 (cadr (cdr (assoc 10 ed))))",
        "  (setq ax2 (car (cdr (assoc 11 ed))))",
        "  (setq ay2 (cadr (cdr (assoc 11 ed))))",
        '  (setq f (open out "w"))',
        '  (write-line (strcat "before_x1=" (rtos bx1 2 8)) f)',
        '  (write-line (strcat "before_y1=" (rtos by1 2 8)) f)',
        '  (write-line (strcat "before_x2=" (rtos bx2 2 8)) f)',
        '  (write-line (strcat "before_y2=" (rtos by2 2 8)) f)',
        '  (write-line (strcat "after_x1=" (rtos ax1 2 8)) f)',
        '  (write-line (strcat "after_y1=" (rtos ay1 2 8)) f)',
        '  (write-line (strcat "after_x2=" (rtos ax2 2 8)) f)',
        '  (write-line (strcat "after_y2=" (rtos ay2 2 8)) f)',
        "  (close f)",
        f'  (princ "\\n{LISP_DEFUN}_DONE\\n")',
        "  (princ)",
        ")",
        "(princ)",
    ]
    return "\n".join(lines) + "\n"


def _build_scr_text(lisp_path_fwd: str) -> str:
    """Mirrors tools/autocad-router.ps1 Get-AutoLispExtractScr's shape: FILEDIA
    off (headless-safe), (load ...) the ASCII/forward-slashed .lsp, run the
    defun, QUIT (never save -- matches the router's universal "export/derive
    only" discipline). Unlike the extractor scripts, CMDECHO is left ON (1)
    here so the raw console transcript captured in stdout is itself readable
    evidence.
    """
    return "\n".join([
        "FILEDIA", "0",
        "CMDECHO", "1",
        f'(load "{lisp_path_fwd}")',
        LISP_DEFUN,
        "QUIT",
        "",
    ]) + "\n"


def _parse_result_kv(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, val = line.partition("=")
        try:
            out[key.strip()] = float(val.strip())
        except ValueError:
            continue
    return out


def classify(values: dict[str, float]) -> dict:
    """Turn parsed before/after endpoints into an honest verdict.

    Never returns True/False on a vacuous test: if the "before" line was not
    actually non-horizontal (the LINE step itself misbehaved), the verdict is
    None ("inconclusive"), not a fabricated pass or fail (Rule 12).
    """
    required = ("before_y1", "before_y2", "after_y1", "after_y2")
    missing = [k for k in required if k not in values]
    if missing:
        return {
            "available": None,
            "reason": "result_incomplete",
            "detail": f"missing keys: {sorted(missing)}",
        }
    before_dy = values["before_y2"] - values["before_y1"]
    after_dy = values["after_y2"] - values["after_y1"]
    if abs(before_dy) < GEOMETRY_TOL:
        return {
            "available": None,
            "reason": "test_precondition_failed",
            "detail": (f"drawn line was already horizontal (before_dy={before_dy!r}); "
                       "the probe's own test geometry is invalid, not evidence either way"),
            "before_dy": before_dy,
            "after_dy": after_dy,
        }
    if abs(after_dy) < GEOMETRY_TOL:
        return {
            "available": True,
            "reason": "autoconstrain_solved_geometry",
            "detail": ("AUTOCONSTRAIN snapped the deliberately-non-horizontal LINE to "
                       "exactly horizontal -- AcDbAssocManager::evaluateTopLevelNetwork "
                       "ran and mutated geometry"),
            "before_dy": before_dy,
            "after_dy": after_dy,
        }
    return {
        "available": False,
        "reason": "geometry_unchanged_after_autoconstrain",
        "detail": ("AUTOCONSTRAIN ran but the line's endpoints did not converge; "
                   "the DCM solver did not visibly fire"),
        "before_dy": before_dy,
        "after_dy": after_dy,
    }


def run_probe(engine: str | None = None, fixture: str | Path | None = None,
             timeout: int = 120, keep_stage: bool = False,
             runner=subprocess.run) -> dict:
    """Run the live probe end-to-end and return an honest result envelope.

    Never raises on an accoreconsole failure -- the failure is reported in the
    dict (run_error / timed_out / reason) so the caller can build a truthful
    not-available/inconclusive result instead of crashing (mirrors
    tools/run_job.py's run_router_extract contract).

    ``runner`` is an injection seam for tests -- defaults to the real
    ``subprocess.run``. A test can pass a stand-in with the same call shape
    (returning a real ``subprocess.CompletedProcess``) to exercise the full
    staging/env-wiring/parse/classify pipeline without a live accoreconsole.
    """
    fixture_path = Path(fixture) if fixture else DEFAULT_FIXTURE
    resolved_engine = engine or find_accoreconsole()
    deferred_command = f'"{sys.executable}" "{Path(__file__).resolve()}"'
    probed_at = datetime.now(timezone.utc).isoformat()

    if not resolved_engine or not os.path.exists(resolved_engine):
        return {
            "schema": "ariadne.dcm_probe.v1",
            "probed_at": probed_at,
            "runtime_available": False,
            "available": None,
            "reason": "accoreconsole_not_found",
            "engine_path": resolved_engine,
            "deferred_command": deferred_command,
        }
    if not fixture_path.exists():
        return {
            "schema": "ariadne.dcm_probe.v1",
            "probed_at": probed_at,
            "runtime_available": True,
            "available": None,
            "reason": "fixture_dwg_not_found",
            "engine_path": str(resolved_engine),
            "fixture": str(fixture_path),
            "deferred_command": deferred_command,
        }

    stage_dir = Path(tempfile.mkdtemp(prefix="cados_dcm_probe_"))
    staged_dwg = stage_dir / "staged.dwg"
    shutil.copyfile(fixture_path, staged_dwg)

    lisp_path = stage_dir / "dcm_probe.lsp"
    lisp_path.write_text(_build_lisp_text(), encoding="ascii")
    scr_path = stage_dir / "dcm_probe.scr"
    scr_path.write_text(_build_scr_text(str(lisp_path).replace("\\", "/")), encoding="ascii")
    result_path = stage_dir / "dcm_probe_result.txt"

    env = dict(os.environ)
    env[ENV_OUT] = str(result_path)
    cmd = [str(resolved_engine), "/i", str(staged_dwg), "/s", str(scr_path)]

    stdout_text = stderr_text = ""
    exit_code = None
    timed_out = False
    run_error = None
    try:
        proc = runner(
            cmd, cwd=str(stage_dir), env=env, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
        stdout_text = proc.stdout or ""
        stderr_text = proc.stderr or ""
        exit_code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        run_error = f"accoreconsole timed out after {timeout}s"
        stdout_text = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr_text = exc.stderr if isinstance(exc.stderr, str) else ""
    except OSError as exc:
        run_error = f"failed to launch accoreconsole: {exc}"

    (stage_dir / "stdout.txt").write_text(stdout_text, encoding="utf-8")
    (stage_dir / "stderr.txt").write_text(stderr_text, encoding="utf-8")

    payload = {
        "schema": "ariadne.dcm_probe.v1",
        "probed_at": probed_at,
        "runtime_available": True,
        "engine_path": str(resolved_engine),
        "fixture": str(fixture_path),
        "command": cmd,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "run_error": run_error,
        "stdout_tail": "\n".join(stdout_text.splitlines()[-40:]),
    }

    if run_error is not None:
        payload["available"] = None
        payload["reason"] = "accoreconsole_launch_error"
    elif not result_path.exists():
        payload["available"] = None
        payload["reason"] = "result_file_missing"
    else:
        values = _parse_result_kv(result_path.read_text(encoding="utf-8", errors="replace"))
        payload["endpoints"] = values
        payload.update(classify(values))

    if keep_stage:
        payload["stage_dir"] = str(stage_dir)
    else:
        shutil.rmtree(stage_dir, ignore_errors=True)
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=None, help="write probe JSON to this path")
    ap.add_argument("--engine", default=None, help="override accoreconsole.exe path")
    ap.add_argument("--fixture", default=None, help="override the staged input .dwg")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--keep-stage", action="store_true", help="keep the staging dir (debug)")
    args = ap.parse_args()

    payload = run_probe(engine=args.engine, fixture=args.fixture,
                        timeout=args.timeout, keep_stage=args.keep_stage)

    text = json.dumps(payload, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
    sys.stdout.write(text)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
