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

from verification import file_snapshot as _file_snapshot

ROUTER_HOME = Path(__file__).resolve().parents[1]
ROUTER_PS1 = ROUTER_HOME / "tools" / "autocad-router.ps1"
_NATIVE_OUTPUT_OPERATIONS = frozenset({
    "transform.database.dxf_out",
    "transform.database.save_as",
    "transform.database.save_as_simple",
})


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not permitted: {value}")


def _reject_duplicate_json_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _strict_json_loads(value: str) -> object:
    """Parse router evidence without JSON duplicate/non-finite extensions."""
    return json.loads(
        value,
        object_pairs_hook=_reject_duplicate_json_object,
        parse_constant=_reject_json_constant,
    )


def _capture_native_result_document(
    reported_path: object,
) -> tuple[dict, str, str] | None:
    """Capture one router-owned native result file without following aliases."""

    if not isinstance(reported_path, str) or not reported_path:
        return None
    candidate = Path(reported_path)
    if not candidate.is_absolute():
        return None
    runs_root = Path(os.path.abspath(str(ROUTER_HOME / "runs")))
    candidate = Path(os.path.abspath(str(candidate)))
    try:
        relative = candidate.relative_to(runs_root).as_posix()
        snapshot = _file_snapshot.capture_file_set({
            "native_result": _file_snapshot.FileRequest(
                runs_root,
                relative,
                require_single_link=True,
            )
        })
        captured = snapshot.files["native_result"]
        document = _strict_json_loads(captured.content.decode("utf-8-sig"))
    except (
        ValueError,
        OSError,
        UnicodeError,
        _file_snapshot.SnapshotCaptureError,
    ):
        return None
    if not isinstance(document, dict):
        return None
    return document, str(candidate), captured.sha256


def _execution_facts(
    envelope: object,
    *,
    process_exit_code: int | None,
    timed_out: bool,
    launch_error: str | None,
) -> dict:
    """Preserve router/engine testimony without inventing missing facts.

    This is intentionally a transport normalizer, not an authorization check.
    ``cadctl`` owns the comparison between these reported facts and the
    operation/write mode/input that it authorized.
    """
    outer = envelope if isinstance(envelope, dict) else {}
    execution = outer.get("execution")
    execution = execution if isinstance(execution, dict) else {}
    engine_output = execution.get("engine_output")
    engine_output = engine_output if isinstance(engine_output, dict) else {}

    return {
        "router_schema": outer.get("schema"),
        "router_status": outer.get("status"),
        "executed_route": outer.get("executed_route"),
        "route": outer.get("executed_route"),
        "process_exit_code": process_exit_code,
        "timed_out": bool(timed_out),
        "launch_error": launch_error,
        "engine_exit_code": execution.get("engine_exit_code"),
        "engine_output_exit_code": engine_output.get("engine_exit_code"),
        "executed": engine_output.get("executed"),
        "status": engine_output.get("status"),
        "mode": engine_output.get("mode"),
        "operation": engine_output.get("operation"),
        "write_mode": engine_output.get("write_mode"),
        "input_kind": engine_output.get("input_kind"),
        "request_input": engine_output.get("request_input"),
        "original_input": engine_output.get("original_input"),
        "input": engine_output.get("input"),
        "working_sha256_before": engine_output.get("working_sha256_before"),
        "working_sha256_after": engine_output.get("working_sha256_after"),
        "save_command_issued": engine_output.get("save_command_issued"),
        "native_status": None,
        "native_schema": None,
        "native_engine": None,
        "native_operation": None,
        "native_result_source": None,
        "native_result_is_object": None,
        "native_error_code": None,
        "native_result_path": None,
        "native_result_sha256": None,
        "result_kind": None,
        "result_path": None,
        "limitation_code": engine_output.get("limitation_code"),
        "limitation_codes": engine_output.get("limitation_codes"),
    }


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
      {command, exit_code, stdout_path, stderr_path, envelope,
       execution (lossless normalized router/engine testimony),
       result_json (path|None), result (dict|None), staged_used (compat alias),
       timed_out, error}.
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
                "stderr_path": str(stderr_path), "envelope": None,
                "execution": _execution_facts(
                    None, process_exit_code=None, timed_out=False, launch_error=msg),
                "result_json": None, "result": None, "staged_used": None,
                "timed_out": False, "error": msg}

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
    facts = _execution_facts(
        envelope,
        process_exit_code=code,
        timed_out=timed_out,
        launch_error=error,
    )
    result_json = None
    result_obj = None
    native_doc = None
    native_result_source = None
    if isinstance(envelope, dict):
        execution = envelope.get("execution")
        execution = execution if isinstance(execution, dict) else {}
        eng = execution.get("engine_output")
        eng = eng if isinstance(eng, dict) else {}
        result_json = eng.get("result_json")
        inline = eng.get("result")
        if isinstance(inline, dict):
            native_doc = inline
            native_result_source = "inline"
    # A reported on-disk result is authoritative over the inline convenience
    # copy. If that file is absent, malformed, or ambiguous, do not retain an
    # inline value that could turn rejected evidence back into a fake success.
    if result_json is not None:
        result_obj = None
        native_doc = None
        native_result_source = None
        captured_native = _capture_native_result_document(result_json)
        if captured_native is not None:
            native_doc, native_result_path, native_result_sha256 = captured_native
            native_result_source = "file"
            facts["native_result_path"] = native_result_path
            facts["native_result_sha256"] = native_result_sha256
    if isinstance(native_doc, dict):
        facts["native_schema"] = (
            native_doc.get("schema")
            if isinstance(native_doc.get("schema"), str)
            else None
        )
        facts["native_engine"] = (
            native_doc.get("engine")
            if isinstance(native_doc.get("engine"), str)
            else None
        )
        facts["native_operation"] = (
            native_doc.get("operation")
            if isinstance(native_doc.get("operation"), str)
            else None
        )
        facts["native_status"] = (
            native_doc.get("status")
            if isinstance(native_doc.get("status"), str)
            else None
        )
        facts["native_error_code"] = (
            native_doc.get("error_code")
            if isinstance(native_doc.get("error_code"), str)
            and native_doc.get("error_code")
            else None
        )
        facts["native_result_source"] = native_result_source
        facts["native_result_is_object"] = isinstance(
            native_doc.get("result"), dict
        )
        if facts["native_result_is_object"]:
            result_obj = native_doc["result"]
        elif facts["native_status"] != "ok":
            # Preserve an authoritative structured native error for callers
            # that classify dispatcher reachability.  It remains an
            # unsuccessful outcome; the canonical receipt independently
            # verifies its schema/engine/operation/file provenance.
            result_obj = native_doc
    if operation in _NATIVE_OUTPUT_OPERATIONS:
        facts["result_kind"] = "native_output"
        if isinstance(result_obj, dict) and isinstance(
            result_obj.get("output_path"), str
        ):
            facts["result_path"] = result_obj["output_path"]
    else:
        facts["result_kind"] = "router_working_copy"
        facts["result_path"] = facts.get("input")
    staged_used = facts.get("result_path")

    return {"command": cmd, "exit_code": code, "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path), "envelope": envelope,
            "execution": facts,
            "result_json": result_json, "result": result_obj,
            "staged_used": staged_used, "timed_out": timed_out, "error": error}


def build_write_batch_command(staged_dwg: str, job_list_path: str, *,
                              out_dir: str | None = None,
                              batch_timeout_ms: int = 0) -> list[str]:
    """Router invocation for a NATIVE write BATCH (#39).

    Runs:  powershell -File <router> -Action run-native-write-batch
           -InputPath <staged_dwg> -JobListPath <jobs.json> [-Out <run_out>]

    One accoreconsole session runs EVERY job in the list against ``staged_dwg``
    IN PLACE and _QSAVEs once at the end. ``staged_dwg`` MUST be an engine-owned
    staged copy -- the route never stages and never touches an original (that
    guarantee is the caller's lifecycle, e.g. patch_engine.apply_staged).
    """
    ps = _powershell_exe()
    cmd = [
        ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", str(ROUTER_PS1),
        "-Action", "run-native-write-batch",
        "-InputPath", str(staged_dwg),
        "-JobListPath", str(job_list_path),
    ]
    if out_dir:
        cmd += ["-Out", str(out_dir)]
    if batch_timeout_ms and batch_timeout_ms > 0:
        cmd += ["-BatchTimeoutMs", str(int(batch_timeout_ms))]
    return cmd


def run_router_write_batch(staged_dwg: str, run_dir: str, job_list_path: str, *,
                           timeout: int = 3600,
                           batch_timeout_ms: int = 0) -> dict:
    """Invoke the router native write-batch lane; capture everything.

    Returns:
      {command, exit_code, stdout_path, stderr_path, envelope (parsed
       write_batch_result|None), timed_out, error}.
    Never raises on a router failure. The authoritative envelope is read from
    <run_dir>/write_batch_result.json (written by the route before it returns);
    stdout parsing is only the fallback. ``envelope.qsave_done`` is the
    batch-persisted proof; ``envelope.results`` is the per-op status list.
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
                "stderr_path": str(stderr_path), "envelope": None,
                "timed_out": False, "error": msg}

    cmd = build_write_batch_command(staged_dwg, job_list_path, out_dir=run_dir,
                                    batch_timeout_ms=batch_timeout_ms)
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
        error = f"router write batch timed out after {timeout}s"
        stdout_text = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr_text = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
    except OSError as exc:
        error = f"failed to launch router: {exc}"

    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")

    envelope = None
    result_file = run_dir_p / "write_batch_result.json"
    if result_file.exists():
        try:
            envelope = json.loads(result_file.read_text(encoding="utf-8-sig"))
        except (ValueError, OSError):
            envelope = None
    if envelope is None and stdout_text.strip():
        envelope = _parse_first_json_object(stdout_text)

    return {"command": cmd, "exit_code": code, "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path), "envelope": envelope,
            "timed_out": timed_out, "error": error}


def _parse_first_json_object(text: str) -> dict | None:
    """Best-effort: parse the router's JSON envelope from stdout.

    The router prints a single ConvertTo-Json object. Try whole-text first, then
    fall back to the largest brace-balanced span.
    """
    text = text.strip()
    try:
        value = _strict_json_loads(text)
        return value if isinstance(value, dict) else None
    except (ValueError, TypeError):
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            value = _strict_json_loads(text[start:end + 1])
            return value if isinstance(value, dict) else None
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
