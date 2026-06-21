#!/usr/bin/env python
"""normalize_result.py -- normalize a router/native result envelope to cad_result.v2.

Lane B1 helper. The router emits an `ariadne.autocad_router_run.v2` envelope
(status PASS/ROUTE_NONZERO/UNAVAILABLE + selection + execution.engine_output).
A native/managed CAD job writes an `ariadne.autocad_sdk_result.v2`-ish JSON. This
module folds either shape into a single `ariadne.autocad_sdk_result.v2` dict
(schemas/cad_result.v2.schema.json) so downstream consumers (cadctl, validator)
never branch on the producing lane.

No-fake-success: the status enum is closed; an envelope that did not actually
succeed maps to error / blocked / unavailable / partial / not_implemented -- never
ok. When status != ok the error envelope is populated.

Standard library only.
"""
from __future__ import annotations

RESULT_SCHEMA = "ariadne.autocad_sdk_result.v2"

# Router run status -> (cad_result status, error code or None)
_ROUTER_STATUS_MAP = {
    "PASS": ("ok", None),
    "ROUTE_NONZERO": ("error", "ROUTE_NONZERO_EXIT"),
    "UNAVAILABLE": ("unavailable", "HOST_UNAVAILABLE"),
}


def _err(code: str, message: str, retryable: bool = False, **details) -> dict:
    env = {"code": code, "message": message, "retryable": retryable}
    if details:
        env["details"] = details
    return env


def normalize_router_run(
    run_envelope: dict,
    *,
    operation: str = "inspect.geometry.extract",
    job_ref: str | None = None,
    write_mode: str = "read",
    ir_ref: str | None = None,
    stdout_ref: str | None = None,
    stderr_ref: str | None = None,
) -> dict:
    """Fold an `ariadne.autocad_router_run.v2` envelope into a cad_result.v2 dict.

    run_envelope is the parsed JSON the router printed for `-Action run`. When the
    router output could not be parsed at all, pass {"status": "PARSE_ERROR", ...}
    and this maps to error/ROUTE_NONZERO_EXIT.
    """
    router_status = str((run_envelope or {}).get("status", "PARSE_ERROR"))
    mapped_status, err_code = _ROUTER_STATUS_MAP.get(
        router_status, ("error", "ROUTE_NONZERO_EXIT")
    )

    execution = (run_envelope or {}).get("execution") or {}
    engine_output = execution.get("engine_output")
    if not isinstance(engine_output, dict):
        engine_output = {}
    exit_code = execution.get("engine_exit_code")
    selection = (run_envelope or {}).get("selection") or {}
    executed_route = (run_envelope or {}).get("executed_route") or selection.get(
        "selected_route"
    )

    diagnostics: dict = {}
    if exit_code is not None:
        try:
            diagnostics["exit_code"] = int(exit_code)
        except (TypeError, ValueError):
            diagnostics["exit_code"] = exit_code
    if stdout_ref:
        diagnostics["stdout_ref"] = stdout_ref
    if stderr_ref:
        diagnostics["stderr_ref"] = stderr_ref

    # Surface the extract entity count when the router inlined a summary.
    extract_summary = engine_output.get("extract_summary")
    if isinstance(extract_summary, dict):
        msc = extract_summary.get("modelspace_count")
        if isinstance(msc, int):
            diagnostics["entity_count"] = msc

    result_ref = engine_output.get("extract_json")

    host: dict = {}
    if executed_route:
        host["router_lane"] = "geometry_native" if executed_route == "dwg_truth_autocad" else None
        host["engine_tier"] = engine_output.get("winning_engine")
    host = {k: v for k, v in host.items() if v is not None}

    out: dict = {
        "schema": RESULT_SCHEMA,
        "operation": operation,
        "status": mapped_status,
        "write_mode": write_mode,
        "executed_route": executed_route,
        "router_status": router_status,
        "diagnostics": diagnostics,
    }
    if job_ref:
        out["job_ref"] = job_ref
    if host:
        out["host"] = host
    if ir_ref:
        out["ir_ref"] = ir_ref
    if mapped_status in ("ok",) and result_ref:
        out["result_ref"] = result_ref

    artifacts = []
    if result_ref:
        artifacts.append({"kind": "json", "ref": result_ref})
    if isinstance(engine_output.get("staged_input"), str):
        artifacts.append({"kind": "dwg_staged", "ref": engine_output["staged_input"]})
    if stdout_ref:
        artifacts.append({"kind": "log", "ref": stdout_ref})
    if stderr_ref:
        artifacts.append({"kind": "log", "ref": stderr_ref})
    if artifacts:
        out["artifacts"] = artifacts

    if mapped_status != "ok":
        detail = {"router_status": router_status}
        if executed_route:
            detail["executed_route"] = executed_route
        eo_status = engine_output.get("status")
        if eo_status:
            detail["engine_status"] = eo_status
        if "exit_code" in diagnostics:
            detail["exit_code"] = diagnostics["exit_code"]
        out["error"] = _err(
            err_code,
            f"router run status={router_status}"
            + (f" (engine: {eo_status})" if eo_status else ""),
            retryable=(mapped_status == "unavailable"),
            **detail,
        )
    return out


def normalize_native_result(
    native: dict,
    *,
    operation: str | None = None,
    job_ref: str | None = None,
    write_mode: str = "read",
) -> dict:
    """Fold a native/managed CAD-job result JSON into a cad_result.v2 dict.

    A native handler writes {operation, status, ...}; status 'ok' means it ran.
    Anything else (including missing) is treated truthfully (error by default).
    """
    native = native or {}
    op = operation or native.get("operation") or "unknown"
    nstatus = str(native.get("status", "error"))
    mapped = nstatus if nstatus in (
        "ok",
        "error",
        "blocked",
        "partial",
        "not_implemented",
        "unavailable",
    ) else "error"

    out: dict = {
        "schema": RESULT_SCHEMA,
        "operation": op,
        "status": mapped,
        "write_mode": write_mode,
    }
    if job_ref:
        out["job_ref"] = job_ref
    diagnostics = {}
    for k in ("entity_count", "affected_handles", "warnings"):
        if k in native:
            diagnostics[k] = native[k]
    if diagnostics:
        out["diagnostics"] = diagnostics
    # Pass through a result payload when present and successful.
    if mapped in ("ok", "partial") and "result" in native:
        out["result"] = native["result"]
    if mapped != "ok":
        msg = native.get("message") or native.get("error") or f"native status={nstatus}"
        out["error"] = _err(
            "NATIVE_RESULT_NONOK",
            str(msg),
            retryable=False,
            native_status=nstatus,
            operation=op,
        )
    return out


def blocked_result(operation: str, code: str, message: str, **details) -> dict:
    """Build a truthful blocked/unavailable/not_implemented cad_result.v2 dict."""
    status = "blocked"
    if code in ("HOST_UNAVAILABLE", "ROUTE_UNAVAILABLE"):
        status = "unavailable"
    elif code in ("OPERATION_NOT_IMPLEMENTED",):
        status = "not_implemented"
    return {
        "schema": RESULT_SCHEMA,
        "operation": operation,
        "status": status,
        "error": _err(code, message, retryable=(status == "unavailable"), **details),
    }


if __name__ == "__main__":
    import argparse
    import json
    import sys
    from pathlib import Path

    ap = argparse.ArgumentParser(description="normalize a router/native envelope to cad_result.v2")
    ap.add_argument("envelope_json", help="path to a router-run or native-result JSON")
    ap.add_argument("--native", action="store_true", help="treat input as a native result")
    ap.add_argument("--operation", default=None)
    args = ap.parse_args()
    data = json.loads(Path(args.envelope_json).read_text(encoding="utf-8-sig"))
    if args.native:
        print(json.dumps(normalize_native_result(data, operation=args.operation), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(normalize_router_run(data, operation=args.operation or "inspect.geometry.extract"), ensure_ascii=False, indent=2))
    sys.exit(0)
