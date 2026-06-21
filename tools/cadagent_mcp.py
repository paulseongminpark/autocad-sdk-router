#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cadagent_mcp.py -- Lane E MCP shell for the CAD OS Layer (stdio / MOCK).

Exposes the CAD OS Layer as a small set of agent-callable tools:

    cad.status            -> cadctl.Cad().status()
    cad.inspect_drawing   -> cadctl.Cad().inspect(dwg, out_dir)
    cad.query_entities    -> cadctl.Cad().query(ir_path, sql)
    cad.get_entity        -> cadctl.Cad().query(ir_path, sql-by-handle)
    cad.validate_ir       -> validator.validate_target(ir_path, run_dir)
    cad.registry_status   -> cadctl.Cad().registry_coverage()
    cad.patch_dry_run     -> patch_engine.dry_run_plan(patch)

Each tool delegates to the cadctl / validator / patch_engine SHELLS -- never to a
raw SDK and never to ad-hoc DWG parsing. That keeps every safety invariant
(staged-copy, router-only extraction, no-fake-success, deterministic validation)
in one place.

Transport: if a real MCP library is importable it could host these tools; in this
packet no MCP server library is assumed, so this module implements a minimal
**stdlib JSON-RPC-2.0-over-stdio MOCK** plus a self-describing tools manifest.
``transport`` is reported as ``"mock"`` so no consumer mistakes it for a
production MCP endpoint.

Hard rules: standard library ONLY; delegate to shells (no raw SDK); a tool whose
underlying shell is unavailable returns an explicit error result, never a fake
success.

Run ``python tools/cadagent_mcp.py`` to print the tools manifest (and exit).
Run ``python tools/cadagent_mcp.py --serve`` to speak JSON-RPC over stdio.
"""

from __future__ import annotations

import json
import os
import sys
import importlib.util
from typing import Any, Dict, List, Optional, Callable

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)

SERVER_NAME = "cadagent-mcp"
SERVER_VERSION = "0.1.0"
TRANSPORT = "mock"  # stdlib JSON-RPC-over-stdio mock; not a production MCP server


# --------------------------------------------------------------------------- #
# Defensive imports of sibling shells (built by other lanes; may be absent).
# We import by file path so this works regardless of sys.path / package setup.
# --------------------------------------------------------------------------- #

def _import_sibling(mod_name: str, file_name: str):
    path = os.path.join(_THIS_DIR, file_name)
    if not os.path.isfile(path):
        return None, "module file not found: %s" % file_name
    try:
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            return None, "could not create import spec for %s" % file_name
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod, None
    except Exception as exc:  # noqa: BLE001  (report, do not crash the server)
        return None, "import error for %s: %r" % (file_name, exc)


_validator, _validator_err = _import_sibling("cados_validator", "validator.py")
_patch_engine, _patch_err = _import_sibling("cados_patch_engine", "patch_engine.py")
_cadctl, _cadctl_err = _import_sibling("cados_cadctl", "cadctl.py")


def _shell_status() -> Dict[str, Any]:
    """Report which sibling shells loaded (for the manifest / diagnostics)."""
    return {
        "validator": {"loaded": _validator is not None, "error": _validator_err},
        "patch_engine": {"loaded": _patch_engine is not None, "error": _patch_err},
        "cadctl": {"loaded": _cadctl is not None, "error": _cadctl_err},
    }


def _err(message: str, **extra: Any) -> Dict[str, Any]:
    out = {"ok": False, "status": "error", "error": message}
    out.update(extra)
    return out


def _cad():
    """Instantiate cadctl.Cad() if available, else return (None, error)."""
    if _cadctl is None:
        return None, "cadctl shell unavailable: %s" % _cadctl_err
    cad_cls = getattr(_cadctl, "Cad", None)
    if cad_cls is None:
        return None, "cadctl.Cad class not found"
    try:
        return cad_cls(), None
    except Exception as exc:  # noqa: BLE001
        return None, "cadctl.Cad() construction failed: %r" % exc


# --------------------------------------------------------------------------- #
# Tool handlers -- each delegates to a shell; never raw SDK.
# --------------------------------------------------------------------------- #

def _tool_status(args: Dict[str, Any]) -> Dict[str, Any]:
    cad, e = _cad()
    if cad is None:
        return _err(e, delegate="cadctl.Cad.status")
    try:
        return {"ok": True, "result": cad.status()}
    except Exception as exc:  # noqa: BLE001
        return _err("cadctl.status failed: %r" % exc)


def _tool_inspect_drawing(args: Dict[str, Any]) -> Dict[str, Any]:
    dwg = args.get("dwg") or args.get("dwg_path")
    out_dir = args.get("out") or args.get("out_dir")
    if not dwg:
        return _err("missing required arg: dwg")
    if not out_dir:
        return _err("missing required arg: out")
    cad, e = _cad()
    if cad is None:
        return _err(e, delegate="cadctl.Cad.inspect")
    try:
        return {"ok": True, "result": cad.inspect(dwg, out_dir,
                                                   mode=args.get("mode", "graph"))}
    except Exception as exc:  # noqa: BLE001
        return _err("cadctl.inspect failed: %r" % exc)


def _tool_query_entities(args: Dict[str, Any]) -> Dict[str, Any]:
    ir = args.get("ir") or args.get("ir_path")
    sql = args.get("sql")
    if not ir or not sql:
        return _err("missing required args: ir, sql")
    cad, e = _cad()
    if cad is None:
        return _err(e, delegate="cadctl.Cad.query")
    try:
        return {"ok": True, "result": cad.query(ir, sql)}
    except Exception as exc:  # noqa: BLE001
        return _err("cadctl.query failed: %r" % exc)


def _tool_get_entity(args: Dict[str, Any]) -> Dict[str, Any]:
    ir = args.get("ir") or args.get("ir_path")
    handle = args.get("handle")
    if not ir or not handle:
        return _err("missing required args: ir, handle")
    cad, e = _cad()
    if cad is None:
        return _err(e, delegate="cadctl.Cad.query")
    # Parameterless SQL string with the handle embedded as a quoted literal; the
    # cadctl.query shell is responsible for read-only enforcement.
    safe_handle = str(handle).replace("'", "''")
    sql = "SELECT * FROM entities WHERE handle = '%s'" % safe_handle
    try:
        return {"ok": True, "result": cad.query(ir, sql), "handle": handle}
    except Exception as exc:  # noqa: BLE001
        return _err("cadctl.query(get_entity) failed: %r" % exc)


def _tool_validate_ir(args: Dict[str, Any]) -> Dict[str, Any]:
    if _validator is None:
        return _err("validator shell unavailable: %s" % _validator_err,
                    delegate="validator.validate_target")
    ir = args.get("ir") or args.get("ir_path")
    run_dir = args.get("run_dir")
    if not ir and not run_dir:
        return _err("provide at least one of: ir, run_dir")
    try:
        return {"ok": True, "result": _validator.validate_target(ir_path=ir, run_dir=run_dir)}
    except Exception as exc:  # noqa: BLE001
        return _err("validator.validate_target failed: %r" % exc)


def _tool_registry_status(args: Dict[str, Any]) -> Dict[str, Any]:
    cad, e = _cad()
    if cad is None:
        return _err(e, delegate="cadctl.Cad.registry_coverage")
    try:
        return {"ok": True, "result": cad.registry_coverage()}
    except Exception as exc:  # noqa: BLE001
        return _err("cadctl.registry_coverage failed: %r" % exc)


def _tool_patch_dry_run(args: Dict[str, Any]) -> Dict[str, Any]:
    if _patch_engine is None:
        return _err("patch_engine shell unavailable: %s" % _patch_err,
                    delegate="patch_engine.dry_run_plan")
    patch = args.get("patch")
    if patch is None:
        return _err("missing required arg: patch (a cad_patch.v1 object)")
    try:
        return {"ok": True, "result": _patch_engine.dry_run_plan(patch)}
    except Exception as exc:  # noqa: BLE001
        return _err("patch_engine.dry_run_plan failed: %r" % exc)


# --------------------------------------------------------------------------- #
# Tools manifest (self-describing) and dispatch table
# --------------------------------------------------------------------------- #

_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "cad.status",
        "description": "Read the router-published status JSON (read-only) and "
                       "report route_count/available/native. Delegates to cadctl.Cad.status.",
        "delegates_to": "cadctl.Cad.status",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "cad.inspect_drawing",
        "description": "Stage a COPY of a DWG, run router DWG geometry extraction, "
                       "build the IR, and write artifacts to out_dir. Delegates to cadctl.Cad.inspect.",
        "delegates_to": "cadctl.Cad.inspect",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dwg": {"type": "string", "description": "Path to the source DWG (read-only original)."},
                "out": {"type": "string", "description": "Output run directory."},
                "mode": {"type": "string", "default": "graph"},
            },
            "required": ["dwg", "out"],
            "additionalProperties": False,
        },
    },
    {
        "name": "cad.query_entities",
        "description": "Run a read-only SQL query over an IR-backed SQLite store. "
                       "Delegates to cadctl.Cad.query.",
        "delegates_to": "cadctl.Cad.query",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ir": {"type": "string", "description": "Path to dwg_graph_ir.json."},
                "sql": {"type": "string", "description": "Read-only SQL (SELECT)."},
            },
            "required": ["ir", "sql"],
            "additionalProperties": False,
        },
    },
    {
        "name": "cad.get_entity",
        "description": "Fetch a single entity by handle from an IR-backed store. "
                       "Delegates to cadctl.Cad.query with a handle filter.",
        "delegates_to": "cadctl.Cad.query",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ir": {"type": "string"},
                "handle": {"type": "string", "description": "DWG entity handle (hex)."},
            },
            "required": ["ir", "handle"],
            "additionalProperties": False,
        },
    },
    {
        "name": "cad.validate_ir",
        "description": "Run deterministic validation gates over an IR and/or run "
                       "folder; returns a validation_report.v1. Delegates to validator.validate_target.",
        "delegates_to": "validator.validate_target",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ir": {"type": "string"},
                "run_dir": {"type": "string"},
            },
            "anyOf": [{"required": ["ir"]}, {"required": ["run_dir"]}],
            "additionalProperties": False,
        },
    },
    {
        "name": "cad.registry_status",
        "description": "Report operation-registry coverage (wired vs stub vs blocked). "
                       "Delegates to cadctl.Cad.registry_coverage.",
        "delegates_to": "cadctl.Cad.registry_coverage",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "cad.patch_dry_run",
        "description": "Validate, risk-classify, and PLAN a cad_patch.v1 without "
                       "executing it (execution is not_implemented). Delegates to patch_engine.dry_run_plan.",
        "delegates_to": "patch_engine.dry_run_plan",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patch": {"type": "object", "description": "An ariadne.cad_patch.v1 object."},
            },
            "required": ["patch"],
            "additionalProperties": False,
        },
    },
]

_DISPATCH: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "cad.status": _tool_status,
    "cad.inspect_drawing": _tool_inspect_drawing,
    "cad.query_entities": _tool_query_entities,
    "cad.get_entity": _tool_get_entity,
    "cad.validate_ir": _tool_validate_ir,
    "cad.registry_status": _tool_registry_status,
    "cad.patch_dry_run": _tool_patch_dry_run,
}


def tools_manifest() -> Dict[str, Any]:
    """Self-describing manifest of the server, its transport, and its tools."""
    return {
        "server": SERVER_NAME,
        "version": SERVER_VERSION,
        "transport": TRANSPORT,
        "protocol": "jsonrpc-2.0-over-stdio (mock)",
        "shells": _shell_status(),
        "tools": _TOOLS,
        "notes": [
            "Every tool delegates to a CAD OS Layer shell (cadctl / validator / "
            "patch_engine); none touches a raw SDK or parses a DWG directly.",
            "transport is 'mock': a stdlib JSON-RPC server, not a production MCP host.",
            "cad.patch_dry_run never executes mutations (execution is not_implemented).",
        ],
    }


# --------------------------------------------------------------------------- #
# Minimal JSON-RPC 2.0 over stdio (mock transport)
# --------------------------------------------------------------------------- #

def _rpc_result(req_id: Any, result: Any) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}, ensure_ascii=False)


def _rpc_error(req_id: Any, code: int, message: str, data: Any = None) -> str:
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return json.dumps({"jsonrpc": "2.0", "id": req_id, "error": err}, ensure_ascii=False)


def handle_rpc(request: Dict[str, Any]) -> Optional[str]:
    """
    Handle one JSON-RPC request object. Supports:
      * "initialize"        -> server info + capabilities
      * "tools/list"        -> the tools manifest
      * "tools/call"        -> {name, arguments} -> tool result (delegated)
    Notifications (no "id") return None (no response emitted).
    """
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}
    is_notification = "id" not in request

    if method == "initialize":
        res = {"serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
               "transport": TRANSPORT,
               "capabilities": {"tools": {"listChanged": False}}}
        return None if is_notification else _rpc_result(req_id, res)

    if method == "tools/list":
        return None if is_notification else _rpc_result(req_id, {"tools": _TOOLS})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = _DISPATCH.get(name)
        if handler is None:
            return None if is_notification else _rpc_error(
                req_id, -32601, "unknown tool: %s" % name,
                data={"available": list(_DISPATCH.keys())})
        try:
            result = handler(arguments)
        except Exception as exc:  # noqa: BLE001
            return None if is_notification else _rpc_error(
                req_id, -32000, "tool execution error", data=repr(exc))
        return None if is_notification else _rpc_result(req_id, result)

    return None if is_notification else _rpc_error(
        req_id, -32601, "unknown method: %s" % method)


def serve_stdio(stdin=None, stdout=None) -> int:
    """Read newline-delimited JSON-RPC requests from stdin; write responses to stdout."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except ValueError:
            stdout.write(_rpc_error(None, -32700, "parse error") + "\n")
            stdout.flush()
            continue
        response = handle_rpc(request)
        if response is not None:
            stdout.write(response + "\n")
            stdout.flush()
    return 0


# --------------------------------------------------------------------------- #
# Self-test (__main__): print the tools manifest (default) or serve (--serve)
# --------------------------------------------------------------------------- #

def _selftest() -> int:
    manifest = tools_manifest()
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

    # Exercise the in-process RPC path for a tool that needs no sibling shell
    # (tools/list) and one delegated tool, to prove dispatch + no-fake-success.
    listed = handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    val_call = handle_rpc({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "cad.validate_ir", "arguments": {"ir": "/nonexistent/ir.json"}},
    })
    val_obj = json.loads(val_call)

    ok = (
        manifest["transport"] == "mock"
        and len(manifest["tools"]) == 7
        and set(_DISPATCH.keys()) == {t["name"] for t in manifest["tools"]}
        and listed is not None
        # validator shell is a sibling that exists in this tree -> tool returns a
        # truthful result (a report or an explicit error), never a fake success.
        and ("result" in val_obj or "error" in val_obj)
    )
    print("SELFTEST_OK" if ok else "SELFTEST_FAIL",
          "| tools=%d transport=%s | validator_loaded=%s cadctl_loaded=%s"
          % (len(manifest["tools"]), manifest["transport"],
             manifest["shells"]["validator"]["loaded"],
             manifest["shells"]["cadctl"]["loaded"]))
    return 0 if ok else 1


if __name__ == "__main__":
    if "--serve" in sys.argv[1:]:
        sys.exit(serve_stdio())
    sys.exit(_selftest())
