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

**Every handler delegates to a CAD OS Layer shell** (`cadctl` / `validator` / `patch_engine` /
`cad_diff` / `visual_report`) — **never to a raw SDK and never to ad-hoc DWG parsing**. Drawing
extraction always flows `cadctl → autocad-router.ps1` against a staged copy. The dispatch table
binds **12 tools** today; `set(_DISPATCH) == {t["name"] for t in manifest.tools}` (self-test
invariant).

### Wired tools (all in `_DISPATCH`, callable now)

| tool | delegates to | required args | return (inside `{"ok":true,"result":…}`) |
|------|--------------|---------------|------------------------------------------|
| `cad.status` | `cadctl.Cad().status()` | — | `ariadne.cadctl.status.v1` (route_count, available_count, native_available) — read-only snapshot of the published status JSON; never runs `-Action status` |
| `cad.inspect_drawing` | `cadctl.Cad().inspect(dwg, out, mode)` | `dwg`, `out` | `ariadne.cadctl.inspect.v1` envelope (cad_job, cad_result, dwg_graph_ir refs, entity_count) |
| `cad.query_entities` | `cadctl.Cad().query(ir, sql)` | `ir`, `sql` | `ariadne.cadctl.query.v1` (`columns`, `rows`, `row_count`) over the IR-backed SQLite store |
| `cad.get_entity` | `cadctl.Cad().query(ir, handle-SQL)` | `ir`, `handle` | same as `query_entities`, filtered to one handle |
| `cad.validate_ir` | `validator.validate_target(ir, run_dir)` | `ir` **and/or** `run_dir` | `ariadne.validation_report.v1` (14 gates) |
| `cad.registry_status` | `cadctl.Cad().registry_coverage()` | — | `ariadne.cadctl.registry_coverage.v1` (operation_count, wired_count, by_status) |
| `cad.registry_explain` | `cadctl.Cad().registry_explain(op_id)` | `op_id` | `ariadne.cadctl.registry_explain.v1` (the full v2 registry record for one op) |
| `cad.patch_dry_run` | `patch_engine.dry_run_plan(patch)` | `patch` | `ariadne.cad_patch.dry_run.v1` (plan only; `execution: "not_implemented"`) |
| `cad.patch_apply_staged` | `patch_engine.apply_staged(patch, dwg_path, out_dir)` | `patch`, `dwg_path`, `out_dir` | the staged-write result envelope (status `ok`/`blocked`/`not_implemented`/`partial`; refs to pre/post IR, `cad_diff.json`, `journal.json`, original-unchanged proof). See PATCH_ENGINE_SPEC §A. |
| `cad.diff_before_after` | `cad_diff.compute_diff(pre_ir, post_ir)` | `pre_ir`, `post_ir` | `ariadne.cad_diff.v1` (handle-keyed; `summary.added/removed/modified`; `comparison_basis: "handle"`). The handler loads the two IR paths (BOM-tolerant) and calls `compute_diff`. |
| `cad.visual_report` | `visual_report.build_visual_report(source_ref, kind)` | `source_ref` | `ariadne.visual_artifact.v1` — a render it cannot produce returns **`NOT_IMPLEMENTED`**, never a fake PASS |
| `cad.live_status` | truthful local liveness probe (no shell) | — | a truthful liveness report; the live ARX named-pipe pump is **not attached** (design-only) and is reported as such, not faked |

Each result envelope is `{"ok": true, "result": …}` on success, or
`{"ok": false, "status": "error", "error": "…", "delegate": "…"}` when the underlying shell is
unavailable (no-fake-success). `cad.get_entity` builds a read-only
`SELECT * FROM entities WHERE handle = '…'` (handle single-quote-escaped); read-only enforcement
lives in the cadctl/sqlite shell, not here. `cad.patch_apply_staged` mutates only a **staged copy**
(the shell stages the copy; the router `_QSAVE`s its own copy) and **never** the original.

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
`SELFTEST_OK | tools=12 transport=mock | validator_loaded=True cadctl_loaded=True`

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

## Not implemented yet (truthful degradation, not faked)

- **Real MCP transport.** This is a stdlib JSON-RPC mock (`transport == "mock"`), not an
  `mcp`-library-hosted server. Promoting it means binding the same `_DISPATCH`
  table to a real MCP server (`stdio`/SSE) once that dependency is permitted.
- **Shell availability.** Every tool is only as live as the shell it delegates to. All five shells
  (`cadctl`, `validator`, `patch_engine`, `cad_diff`, `visual_report`) are present today; if one
  were absent the tool returns an explicit `delegate`/`error` envelope (verified by the self-test,
  which exercises `cad.validate_ir` against a nonexistent IR and gets a truthful result, not a fake
  pass).
- **`cad.patch_dry_run`** plans only — declared-op execution there is `not_implemented`. Use
  **`cad.patch_apply_staged`** for the real staged write (see `PATCH_ENGINE_SPEC.md` §A).
- **`cad.patch_apply_staged`** returns a truthful `not_implemented` for any patch op that has no
  native write handler (only `create_line`/`create_circle`/`set_layer`/`create_layer` map to a live
  native op) and for any unavailable sibling/host — never a fake `ok`.
- **`cad.visual_report`** returns `NOT_IMPLEMENTED` for any render it cannot actually produce
  (no fake PASS). **`cad.live_status`** reports the live ARX pump as not-attached (design-only).

> Self-test invariant: `tools=12`, `transport=mock`, and `set(_DISPATCH) == {t["name"] for t in
> manifest.tools}`. The wired tool count is **12**; keep this in sync with `_DISPATCH`/`_TOOLS`.
