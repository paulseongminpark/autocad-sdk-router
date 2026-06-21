# MCP_TOOL_CONTRACT — `tools/cadagent_mcp.py`

Lane E MCP shell for the CAD OS Layer (stdio / **MOCK** transport).

## Purpose

Expose the CAD OS Layer as a small set of agent-callable MCP tools. **Every tool
delegates to a CAD OS Layer shell** (`cadctl` / `validator` / `patch_engine`) —
never to a raw SDK and never to ad-hoc DWG parsing. That keeps every safety
invariant (staged-copy, router-only extraction, no-fake-success, deterministic
validation) in exactly one place.

## Transport

If a real MCP server library were importable it could host these tools. In this
packet **no MCP library is assumed**, so this module ships a minimal stdlib
**JSON-RPC 2.0 over stdio MOCK** plus a self-describing manifest.
`transport == "mock"` is reported everywhere so no consumer mistakes it for a
production MCP endpoint.

## Safety guarantees

- **Standard library only.** Sibling shells are imported by file path with
  `importlib`, defensively — a missing/erroring shell is reported in the
  manifest (`shells.<name>.loaded/error`), it does not crash the server.
- **Delegation only.** No tool touches a raw SDK or parses a DWG; each calls a
  shell function. Drawing extraction flows `cadctl → router` (staged copy).
- **No-fake-success.** A tool whose shell is unavailable returns
  `{"ok": false, "status": "error", "error": "…"}` — never a fake success.
  `cad.patch_dry_run` plans only (execution `not_implemented`).

## Tools

| tool | delegates to | required args |
|------|--------------|---------------|
| `cad.status` | `cadctl.Cad.status` | — |
| `cad.inspect_drawing` | `cadctl.Cad.inspect` | `dwg`, `out` |
| `cad.query_entities` | `cadctl.Cad.query` | `ir`, `sql` |
| `cad.get_entity` | `cadctl.Cad.query` (handle filter) | `ir`, `handle` |
| `cad.validate_ir` | `validator.validate_target` | `ir` and/or `run_dir` |
| `cad.registry_status` | `cadctl.Cad.registry_coverage` | — |
| `cad.patch_dry_run` | `patch_engine.dry_run_plan` | `patch` |

`cad.get_entity` builds a read-only `SELECT * FROM entities WHERE handle = '…'`
(handle single-quote-escaped) and delegates to `cadctl.Cad.query`; read-only
enforcement lives in the cadctl/sqlite shell, not here.

## JSON-RPC methods

| method | params | result |
|--------|--------|--------|
| `initialize` | — | `{serverInfo, transport, capabilities}` |
| `tools/list` | — | `{tools: [...]}` (the manifest tool list) |
| `tools/call` | `{name, arguments}` | the delegated tool result, or a JSON-RPC error |

- Unknown tool → JSON-RPC error `-32601` with `data.available`.
- Tool raising → JSON-RPC error `-32000` with `data` = repr of the exception.
- Notifications (requests without `id`) produce no response.
- Parse errors → `-32700`.

Each tool result envelope is `{"ok": bool, "result": ...}` on success or
`{"ok": false, "status": "error", "error": "...", "delegate": "..."}` when the
underlying shell is unavailable.

## Exact commands

```bash
# Print the self-describing tools manifest (default), verdict on last line.
python tools/cadagent_mcp.py        # exit 0 = SELFTEST_OK

# Speak JSON-RPC 2.0 over stdio (newline-delimited requests on stdin):
python tools/cadagent_mcp.py --serve
# e.g. echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python tools/cadagent_mcp.py --serve
```

Verdict line example:
`SELFTEST_OK | tools=7 transport=mock | validator_loaded=True cadctl_loaded=True`

## Manifest shape

```jsonc
{
  "server": "cadagent-mcp", "version": "0.1.0",
  "transport": "mock", "protocol": "jsonrpc-2.0-over-stdio (mock)",
  "shells": { "validator": {"loaded": true, "error": null}, "patch_engine": {...}, "cadctl": {...} },
  "tools": [ { "name": "cad.status", "delegates_to": "cadctl.Cad.status", "inputSchema": {...} }, ... ],
  "notes": [ "Every tool delegates to a shell …", "transport is 'mock' …", "cad.patch_dry_run never executes …" ]
}
```

## Not implemented yet

- **Real MCP transport.** This is a stdlib JSON-RPC mock, not an
  `mcp`-library-hosted server. Promoting it means binding the same `_DISPATCH`
  table to a real MCP server (`stdio`/SSE) once that dependency is permitted.
- **`cad.inspect_drawing` / `cad.query_entities` / `cad.get_entity` /
  `cad.registry_status` / `cad.status`** are only as live as the `cadctl` shell
  they delegate to (built by Lane B1). When `cadctl` is absent the tools return
  an explicit `delegate`/`error` envelope (verified by the self-test, which
  exercises `cad.validate_ir` against a nonexistent IR and gets a truthful
  result, not a fake pass).
- **`cad.patch_dry_run`** plans only — patch execution is `not_implemented`
  (see `PATCH_ENGINE_SPEC.md`).
