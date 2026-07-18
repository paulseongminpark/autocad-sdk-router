#!/usr/bin/env python
"""run_job.py -- invoke the AutoCAD SDK router run lane and capture the result.

Lane B1 helper. cadctl never parses a DWG itself; it shells out to the canonical
router entrypoint (tools/autocad-router.ps1) which performs the ObjectARX ->
ObjectDBX -> AutoLISP extraction on a staged copy. This module:

  * builds the exact router command,
  * runs it via powershell.exe,
  * captures stdout + stderr + exit code into the caller's run dir (mandatory for
    any external command), and
  * parses the router's JSON envelope (best-effort).

Standard library only. No CAD parsing here.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROUTER_HOME = Path(__file__).resolve().parents[1]
ROUTER_PS1 = ROUTER_HOME / "tools" / "autocad-router.ps1"


def _powershell_exe() -> str:
    for name in ("powershell.exe", "powershell", "pwsh.exe", "pwsh"):
        found = shutil.which(name)
        if found:
            return found
    # Last-resort absolute path for Windows PowerShell 5.1.
    fallback = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    return fallback


def build_extract_command(staged_dwg: str, *, intent: str = "dwg",
                          extract_mode: str = "geometry_native") -> list[str]:
    """The exact router invocation that produces a dwg_geometry_extract.v1 JSON.

    Runs:  powershell -File <router> -Action run -Intent dwg
           -InputPath <staged_dwg> -ExtractMode geometry_native

    geometry_native pins the ObjectARX-only extractor chain (the most authoritative
    engine), which writes the dwg_geometry_extract.v1 file and returns its path in
    execution.engine_output.extract_json.
    """
    ps = _powershell_exe()
    return [
        ps,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy", "Bypass",
        "-File", str(ROUTER_PS1),
        "-Action", "run",
        "-Intent", intent,
        "-InputPath", str(staged_dwg),
        "-ExtractMode", extract_mode,
    ]


def run_router_extract(staged_dwg: str, run_dir: str, *, intent: str = "dwg",
                       extract_mode: str = "geometry_native",
                       timeout: int = 600) -> dict:
    """Invoke the router extract lane on a staged DWG; capture everything.

    Writes <run_dir>/stdout.txt, <run_dir>/stderr.txt, and returns:
      {command, exit_code, stdout_path, stderr_path, envelope (parsed JSON|None),
       timed_out (bool), error (str|None)}.
    Never raises on a router failure -- the failure is reported in the dict so the
    caller can build a truthful not_implemented/error result.
    """
    run_dir_p = Path(run_dir)
    run_dir_p.mkdir(parents=True, exist_ok=True)
    stdout_path = run_dir_p / "stdout.txt"
    stderr_path = run_dir_p / "stderr.txt"

    if not ROUTER_PS1.exists():
        msg = f"router entrypoint missing: {ROUTER_PS1}"
        stderr_path.write_text(msg + "\n", encoding="utf-8")
        stdout_path.write_text("", encoding="utf-8")
        return {
            "command": None,
            "exit_code": None,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "envelope": None,
            "timed_out": False,
            "error": msg,
        }

    cmd = build_extract_command(staged_dwg, intent=intent, extract_mode=extract_mode)
    timed_out = False
    error = None
    stdout_text = ""
    stderr_text = ""
    code = None
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROUTER_HOME),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        stdout_text = proc.stdout or ""
        stderr_text = proc.stderr or ""
        code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        error = f"router run timed out after {timeout}s"
        stdout_text = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr_text = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
    except OSError as exc:  # powershell not found / spawn failure
        error = f"failed to launch router: {exc}"

    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")

    envelope = None
    if stdout_text.strip():
        envelope = _parse_first_json_object(stdout_text)

    return {
        "command": cmd,
        "exit_code": code,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "envelope": envelope,
        "timed_out": timed_out,
        "error": error,
    }


def build_cad_job_command(staged_dwg: str, operation: str, *,
                          intent: str = "dwg", write_mode: str = "read",
                          job_path: str | None = None) -> list[str]:
    """Router invocation for a NATIVE cad job (ObjectARX ARIADNE_NATIVE_JOB).

    Runs:  powershell -File <router> -Action run -Intent dwg
           -InputPath <staged_dwg> -Operation <op> -WriteMode <mode>

    The router routes ``inspect.database.graph`` (and the P1 write ops) to the
    native .dbx/.crx job path, which writes a native result JSON whose path comes
    back in execution.engine_output.result_json. write_mode 'write_copy' makes the
    router stage a copy and _QSAVE it -> a real staged mutation (never the original).
    """
    ps = _powershell_exe()
    cmd = [
        ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", str(ROUTER_PS1),
        "-Action", "run", "-Intent", intent,
        "-InputPath", str(staged_dwg),
        "-Operation", operation,
    ]
    if write_mode:
        cmd += ["-WriteMode", write_mode]
    if job_path:
        cmd += ["-JobPath", str(job_path)]
    return cmd


def run_router_cad_job(staged_dwg: str, run_dir: str, operation: str, *,
                       intent: str = "dwg", write_mode: str = "read",
                       job_path: str | None = None, timeout: int = 2400) -> dict:
    """Invoke the router NATIVE cad-job lane; capture stdout/stderr/exit + result.

    Returns:
      {command, exit_code, stdout_path, stderr_path, envelope, result_json (path|None),
       result (dict|None), staged_used (path|None), timed_out, error}.
    Never raises on router failure. The native result JSON path is read from
    execution.engine_output.result_json; ``result`` is its parsed ``result`` object.
    """
    run_dir_p = Path(run_dir)
    run_dir_p.mkdir(parents=True, exist_ok=True)
    stdout_path = run_dir_p / "stdout.txt"
    stderr_path = run_dir_p / "stderr.txt"

    if not ROUTER_PS1.exists():
        msg = f"router entrypoint missing: {ROUTER_PS1}"
        stderr_path.write_text(msg + "\n", encoding="utf-8")
        stdout_path.write_text("", encoding="utf-8")
        return {"command": None, "exit_code": None, "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path), "envelope": None, "result_json": None,
                "result": None, "staged_used": None, "timed_out": False, "error": msg}

    cmd = build_cad_job_command(staged_dwg, operation, intent=intent,
                                write_mode=write_mode, job_path=job_path)
    timed_out = False
    error = None
    stdout_text = ""
    stderr_text = ""
    code = None
    try:
        proc = subprocess.run(
            cmd, cwd=str(ROUTER_HOME), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        stdout_text = proc.stdout or ""
        stderr_text = proc.stderr or ""
        code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        error = f"router cad job timed out after {timeout}s"
        stdout_text = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr_text = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
    except OSError as exc:
        error = f"failed to launch router: {exc}"

    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")

    envelope = _parse_first_json_object(stdout_text) if stdout_text.strip() else None
    result_json = None
    result_obj = None
    staged_used = None
    if envelope:
        eng = (envelope.get("execution") or {}).get("engine_output") or {}
        result_json = eng.get("result_json")
        staged_used = eng.get("input")
        inline = eng.get("result")
        if isinstance(inline, dict):
            result_obj = inline.get("result", inline)
    # Prefer reading the on-disk result file (authoritative, full).
    if result_json and Path(result_json).exists():
        try:
            doc = json.loads(Path(result_json).read_text(encoding="utf-8-sig"))
            result_obj = doc.get("result", doc)
        except (ValueError, OSError):
            pass

    return {"command": cmd, "exit_code": code, "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path), "envelope": envelope,
            "result_json": result_json, "result": result_obj,
            "staged_used": staged_used, "timed_out": timed_out, "error": error}


def _parse_first_json_object(text: str) -> dict | None:
    """Best-effort: parse the router's JSON envelope from stdout.

    The router prints a single ConvertTo-Json object. Try whole-text first, then
    fall back to the largest brace-balanced span.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except (ValueError, TypeError):
            return None
    return None


if __name__ == "__main__":
    import argparse
    import sys
    import tempfile

    ap = argparse.ArgumentParser(description="run the router extract lane on a staged DWG")
    ap.add_argument("--staged", required=True, help="path to a STAGED dwg copy (never the original)")
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--extract-mode", default="geometry_native")
    args = ap.parse_args()
    rd = args.run_dir or tempfile.mkdtemp(prefix="cadctl_runjob_")
    res = run_router_extract(args.staged, rd, extract_mode=args.extract_mode)
    res_print = {k: v for k, v in res.items() if k != "envelope"}
    res_print["envelope_status"] = (res["envelope"] or {}).get("status") if res["envelope"] else None
    print(json.dumps(res_print, ensure_ascii=False, indent=2))
    sys.exit(0)
