#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cadagent_mcp.py -- Lane E MCP shell for the CAD OS Layer (stdio / MOCK).

Exposes the CAD OS Layer as a small set of agent-callable tools:

    cad.status             -> cadctl.Cad().status()
    cad.inspect_drawing    -> cadctl.Cad().inspect(dwg, out_dir, include_rich=?)
    cad.query_entities     -> cadctl.Cad().query(ir_path, sql)
    cad.get_entity         -> cadctl.Cad().query(ir_path, sql-by-handle)
    cad.validate_ir        -> validator.validate_target(ir_path, run_dir)
    cad.registry_status    -> cadctl.Cad().registry_coverage()
    cad.registry_explain   -> cadctl.Cad().registry_explain(op_id)
    cad.patch_dry_run      -> patch_engine.dry_run_plan(patch)
    cad.patch_apply_staged -> patch_engine.apply_staged(patch, dwg_path, out_dir)
    cad.diff_before_after  -> cad_diff.compute_diff(pre_ir, post_ir)  [two IR paths]
    cad.visual_report      -> visual_report.build_visual_report(source_ref, kind)
    cad.live_status        -> truthful liveness probe (live ARX pump not attached)

Each tool delegates to the cadctl / validator / patch_engine / cad_diff /
visual_report SHELLS -- never to a raw SDK and never to ad-hoc DWG parsing. That
keeps every safety invariant (staged-copy, router-only extraction,
no-fake-success, deterministic validation) in one place. Sibling shells that a
peer lane has not landed yet (e.g. cad_diff.compute_diff,
patch_engine.apply_staged) degrade to a truthful not_implemented/unavailable
result -- never a crash and never a fake success.

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
_visual_report, _visual_err = _import_sibling("cados_visual_report", "visual_report.py")
# cad_diff.py is defined by a peer lane in this same workflow; it may not be on
# disk yet. _import_sibling returns (None, "module file not found: ...") in that
# case, and the cad.diff_before_after handler degrades to not_implemented.
_cad_diff, _cad_diff_err = _import_sibling("cados_cad_diff", "cad_diff.py")


def _shell_status() -> Dict[str, Any]:
    """Report which sibling shells loaded (for the manifest / diagnostics)."""
    return {
        "validator": {"loaded": _validator is not None, "error": _validator_err},
        "patch_engine": {"loaded": _patch_engine is not None, "error": _patch_err},
        "cadctl": {"loaded": _cadctl is not None, "error": _cadctl_err},
        "visual_report": {"loaded": _visual_report is not None, "error": _visual_err},
        "cad_diff": {"loaded": _cad_diff is not None, "error": _cad_diff_err},
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
    # Rich native_full IR is selectable two ways: include_rich=True, or the
    # convenience alias mode="rich". cadctl.inspect's own `mode` arg only ever
    # distinguishes "graph" vs "extract", so collapse "rich" back to "graph"
    # before delegating and let include_rich carry the native-graph routing.
    mode = args.get("mode", "graph")
    include_rich = bool(args.get("include_rich", False)) or mode == "rich"
    delegate_mode = "graph" if mode == "rich" else mode
    try:
        return {"ok": True, "result": cad.inspect(dwg, out_dir,
                                                   mode=delegate_mode,
                                                   include_rich=include_rich)}
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


def _tool_registry_explain(args: Dict[str, Any]) -> Dict[str, Any]:
    op_id = args.get("op_id") or args.get("operation") or args.get("id")
    if not op_id:
        return _err("missing required arg: op_id")
    cad, e = _cad()
    if cad is None:
        return _err(e, delegate="cadctl.Cad.registry_explain")
    try:
        return {"ok": True, "result": cad.registry_explain(op_id)}
    except Exception as exc:  # noqa: BLE001
        return _err("cadctl.registry_explain failed: %r" % exc)


def _tool_patch_dry_run(args: Dict[str, Any]) -> Dict[str, Any]:
    patch = args.get("patch")
    if patch is None:
        return _err("missing required arg: patch (a cad_patch.v1 object)")
    cad, e = _cad()
    if cad is None:
        return _err(e, delegate="cadctl.Cad.patch_dry_run")
    try:
        return {"ok": True, "result": cad.patch_dry_run(patch)}
    except Exception as exc:  # noqa: BLE001
        return _err("cadctl.patch_dry_run failed: %r" % exc)


def _tool_patch_apply_staged(args: Dict[str, Any]) -> Dict[str, Any]:
    """Apply a patch on a STAGED copy via patch_engine.apply_staged.

    apply_staged is part of the M02 contract but a peer lane owns it; if that
    function is not present on the loaded patch_engine yet, degrade truthfully to
    not_implemented (never a fake apply).
    """
    if _patch_engine is None:
        return _err("patch_engine shell unavailable: %s" % _patch_err,
                    delegate="patch_engine.apply_staged")
    apply_fn = getattr(_patch_engine, "apply_staged", None)
    if apply_fn is None:
        return {
            "ok": True,
            "result": {
                "schema": "ariadne.cad_patch.apply_staged.v1",
                "status": "not_implemented",
                "reason": "patch_engine.apply_staged is not present on the loaded "
                          "patch_engine shell yet (peer lane not landed).",
                "delegate": "patch_engine.apply_staged",
            },
        }
    patch = args.get("patch")
    dwg_path = args.get("dwg_path") or args.get("dwg")
    out_dir = args.get("out_dir") or args.get("out")
    if patch is None:
        return _err("missing required arg: patch (a cad_patch.v1 object)")
    if not dwg_path:
        return _err("missing required arg: dwg_path")
    if not out_dir:
        return _err("missing required arg: out_dir")
    try:
        return {"ok": True, "result": apply_fn(patch, dwg_path, out_dir)}
    except Exception as exc:  # noqa: BLE001
        return _err("patch_engine.apply_staged failed: %r" % exc)


def _tool_diff_before_after(args: Dict[str, Any]) -> Dict[str, Any]:
    """Compute a structural IR diff (cad_diff.v1) between two IR documents.

    Delegates to cad_diff.compute_diff(pre_ir, post_ir). cad_diff is owned by a
    peer lane and may not be on disk yet -> truthful not_implemented; otherwise
    each IR path is read (utf-8-sig, BOM-tolerant) and passed as a dict.
    """
    pre = args.get("pre_ir") or args.get("pre_ir_path") or args.get("pre")
    post = args.get("post_ir") or args.get("post_ir_path") or args.get("post")
    if not pre or not post:
        return _err("missing required args: pre_ir, post_ir (paths to dwg_graph_ir.json)")
    cad, e = _cad()
    if cad is None:
        return _err(e, delegate="cadctl.Cad.diff_before_after")
    try:
        return {"ok": True, "result": cad.diff_before_after(pre, post)}
    except Exception as exc:  # noqa: BLE001
        return _err("cadctl.diff_before_after failed: %r" % exc)


def _tool_visual_report(args: Dict[str, Any]) -> Dict[str, Any]:
    """Build a visual_artifact.v1 envelope via visual_report.build_visual_report.

    The visual producer is no-fake-success: when no available render route can
    emit the requested kind, build_visual_report itself returns
    not_implemented/blocked with empty refs -- this handler just relays it.
    """
    source_ref = args.get("source_ref") or args.get("source") or args.get("ir") or args.get("dwg")
    if not source_ref:
        return _err("missing required arg: source_ref (a DWG/IR path)")
    cad, e = _cad()
    if cad is None:
        return _err(e, delegate="cadctl.Cad.visual_report")
    kind = args.get("kind", "png")
    try:
        return {"ok": True, "result": cad.visual_report(
            source_ref,
            kind=kind,
            artifact_id=args.get("artifact_id"),
            out_dir=args.get("out_dir"),
            route=args.get("route"),
        )}
    except Exception as exc:  # noqa: BLE001
        return _err("cadctl.visual_report failed: %r" % exc)


def _tool_live_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """Truthful liveness probe of a live in-process ObjectARX pump.

    No live ARX pump is attached to this MCP shell (every mutation goes through
    the router's staged accoreconsole job, not a persistent live document). This
    is reported honestly as not_implemented -- NEVER a fake "live" success.
    """
    cad, e = _cad()
    if cad is None:
        return _err(e, delegate="cadctl.Cad.live_status")
    try:
        return {"ok": True, "result": cad.live_status()}
    except Exception as exc:  # noqa: BLE001
        return _err("cadctl.live_status failed: %r" % exc)


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
        "description": "Stage a COPY of a DWG, run router DWG extraction, build the "
                       "IR, and write artifacts to out_dir. include_rich=true (or "
                       "mode='rich') routes the native inspect.database.graph op for "
                       "a coverage_level=native_full IR. Delegates to cadctl.Cad.inspect.",
        "delegates_to": "cadctl.Cad.inspect",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dwg": {"type": "string", "description": "Path to the source DWG (read-only original)."},
                "out": {"type": "string", "description": "Output run directory."},
                "mode": {"type": "string", "default": "graph",
                         "description": "'graph'|'extract'|'rich' ('rich' implies include_rich)."},
                "include_rich": {"type": "boolean", "default": False,
                                 "description": "Route the native_full database graph (symbol "
                                                "tables, blocks, layouts, xrefs, dictionaries, xrecords)."},
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
        "name": "cad.registry_explain",
        "description": "Return the full operation_registry.v2 record for one operation id. "
                       "Delegates to cadctl.Cad.registry_explain.",
        "delegates_to": "cadctl.Cad.registry_explain",
        "inputSchema": {
            "type": "object",
            "properties": {
                "op_id": {"type": "string", "description": "Operation id, e.g. 'inspect.database.graph'."},
            },
            "required": ["op_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "cad.patch_dry_run",
        "description": "Validate, risk-classify, and PLAN a cad_patch.v1 without "
                       "executing it (execution is not_implemented). Delegates to patch_engine.dry_run_plan.",
        "delegates_to": "cadctl.Cad.patch_dry_run",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patch": {"type": "object", "description": "An ariadne.cad_patch.v1 object."},
            },
            "required": ["patch"],
            "additionalProperties": False,
        },
    },
    {
        "name": "cad.patch_apply_staged",
        "description": "Apply a cad_patch.v1 on a STAGED copy (never the original) via "
                       "patch_engine.apply_staged. Degrades to not_implemented if the peer "
                       "lane's apply_staged is not present.",
        "delegates_to": "patch_engine.apply_staged",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patch": {"type": "object", "description": "An ariadne.cad_patch.v1 object."},
                "dwg_path": {"type": "string", "description": "DWG to copy+mutate (original stays read-only)."},
                "out_dir": {"type": "string", "description": "Run output directory."},
            },
            "required": ["patch", "dwg_path", "out_dir"],
            "additionalProperties": False,
        },
    },
    {
        "name": "cad.diff_before_after",
        "description": "Compute a structural IR diff (cad_diff.v1) between two "
                       "dwg_graph_ir.json documents. Delegates to cad_diff.compute_diff; "
                       "degrades to not_implemented if the peer lane's cad_diff is absent.",
        "delegates_to": "cadctl.Cad.diff_before_after",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pre_ir": {"type": "string", "description": "Path to the BEFORE dwg_graph_ir.json."},
                "post_ir": {"type": "string", "description": "Path to the AFTER dwg_graph_ir.json."},
            },
            "required": ["pre_ir", "post_ir"],
            "additionalProperties": False,
        },
    },
    {
        "name": "cad.visual_report",
        "description": "Build a visual_artifact.v1 envelope for a derived artifact "
                       "(png/svg/pdf/diff_overlay). No-fake-success: returns "
                       "not_implemented/blocked with empty refs when no producer is wired. "
                       "Delegates through cadctl.Cad.visual_report.",
        "delegates_to": "cadctl.Cad.visual_report",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_ref": {"type": "string", "description": "DWG/IR path (read-only provenance)."},
                "kind": {"type": "string", "default": "png",
                         "description": "png|jpg|svg|pdf|diff_overlay|..."},
                "artifact_id": {"type": "string"},
                "out_dir": {"type": "string"},
                "route": {"type": "string", "description": "Force a specific render route."},
            },
            "required": ["source_ref"],
            "additionalProperties": False,
        },
    },
    {
        "name": "cad.live_status",
        "description": "Truthful liveness probe. No live in-process ObjectARX pump is "
                       "attached to this shell -> returns not_implemented (never a fake live).",
        "delegates_to": "cadctl.Cad.live_status",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]

_DISPATCH: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "cad.status": _tool_status,
    "cad.inspect_drawing": _tool_inspect_drawing,
    "cad.query_entities": _tool_query_entities,
    "cad.get_entity": _tool_get_entity,
    "cad.validate_ir": _tool_validate_ir,
    "cad.registry_status": _tool_registry_status,
    "cad.registry_explain": _tool_registry_explain,
    "cad.patch_dry_run": _tool_patch_dry_run,
    "cad.patch_apply_staged": _tool_patch_apply_staged,
    "cad.diff_before_after": _tool_diff_before_after,
    "cad.visual_report": _tool_visual_report,
    "cad.live_status": _tool_live_status,
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
            "patch_engine / cad_diff / visual_report); none touches a raw SDK or "
            "parses a DWG directly.",
            "transport is 'mock': a stdlib JSON-RPC server, not a production MCP host.",
            "cad.patch_dry_run never executes mutations (execution is not_implemented).",
            "cad.patch_apply_staged mutates only a STAGED copy; the original DWG is "
            "READ-ONLY. It degrades to not_implemented until patch_engine.apply_staged lands.",
            "cad.diff_before_after degrades to not_implemented until the peer "
            "cad_diff.compute_diff shell is on disk.",
            "cad.visual_report and cad.live_status are no-fake-success: they return "
            "not_implemented/blocked (never a fabricated PASS) when no producer/live "
            "pump is wired.",
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

_EXPECTED_TOOLS = {
    "cad.status", "cad.inspect_drawing", "cad.query_entities", "cad.get_entity",
    "cad.validate_ir", "cad.registry_status", "cad.registry_explain",
    "cad.patch_dry_run", "cad.patch_apply_staged", "cad.diff_before_after",
    "cad.visual_report", "cad.live_status",
}

# Trivial (often invalid/missing) args per tool. The contract: EVERY handler must
# return a dict and NEVER crash, whether it succeeds, reports a missing arg, or
# truthfully degrades to not_implemented. We do NOT supply a real DWG path here,
# so handlers that would mutate/extract just report a missing-arg or degraded dict.
_SELFTEST_ARGS: Dict[str, Dict[str, Any]] = {
    "cad.status": {},
    "cad.inspect_drawing": {},  # missing dwg/out -> _err dict
    "cad.query_entities": {},   # missing ir/sql -> _err dict
    "cad.get_entity": {},       # missing ir/handle -> _err dict
    "cad.validate_ir": {"ir": "/nonexistent/ir.json"},
    "cad.registry_status": {},
    "cad.registry_explain": {"op_id": "inspect.database.graph"},
    "cad.patch_dry_run": {"patch": {"schema": "ariadne.cad_patch.v1"}},
    "cad.patch_apply_staged": {},  # missing args / degraded -> dict
    "cad.diff_before_after": {},   # missing args / degraded -> dict
    "cad.visual_report": {"source_ref": "/nonexistent/source.dwg", "kind": "png"},
    "cad.live_status": {},
}


def _selftest() -> int:
    manifest = tools_manifest()
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

    manifest_names = {t["name"] for t in manifest["tools"]}

    # Dispatch EVERY tool handler through the in-process RPC path with a trivial
    # arg; confirm each returns a JSON-RPC result whose payload is a dict. A
    # not_implemented / missing-arg / error dict is acceptable -- a crash is not.
    per_tool: Dict[str, str] = {}
    all_dicts = True
    for name in sorted(_DISPATCH.keys()):
        call = handle_rpc({
            "jsonrpc": "2.0", "id": "t-%s" % name, "method": "tools/call",
            "params": {"name": name, "arguments": _SELFTEST_ARGS.get(name, {})},
        })
        if call is None:
            per_tool[name] = "no-response"
            all_dicts = False
            continue
        obj = json.loads(call)
        payload = obj.get("result")
        # tools/call always returns a JSON-RPC "result" wrapping the handler dict.
        if not isinstance(payload, dict):
            per_tool[name] = "non-dict"
            all_dicts = False
        else:
            # surface the handler's own status word when present
            inner = payload.get("result")
            status_word = None
            if isinstance(inner, dict):
                status_word = inner.get("status")
            per_tool[name] = status_word or ("ok" if payload.get("ok") else "err")

    listed = handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    ok = (
        manifest["transport"] == "mock"
        and len(manifest["tools"]) == 12
        and manifest_names == _EXPECTED_TOOLS
        # manifest and dispatch table must agree exactly (no orphan tools).
        and set(_DISPATCH.keys()) == manifest_names
        and listed is not None
        and all_dicts
    )
    print("SELFTEST_OK" if ok else "SELFTEST_FAIL",
          "| tools=%d transport=%s all_dict=%s"
          % (len(manifest["tools"]), manifest["transport"], all_dicts))
    print("  shells:", json.dumps({k: v["loaded"] for k, v in manifest["shells"].items()},
                                   ensure_ascii=False))
    print("  per_tool:", json.dumps(per_tool, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    if "--serve" in sys.argv[1:]:
        sys.exit(serve_stdio())
    sys.exit(_selftest())
