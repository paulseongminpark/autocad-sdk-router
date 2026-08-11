# MCP_TOOL_CONTRACT — `tools/cadagent_mcp.py`

This document is the public contract for the CADAgent MCP endpoint on the PR #67
integration branch. The endpoint is the official Python MCP SDK over persistent
stdio; it is not the retired private JSON-RPC compatibility shim. The branch is
still Draft, so this document does not claim that the SDK integration is merged
into `main`.

## Purpose and safety boundary

`cadagent_mcp.py` owns the CAD OS Layer tool catalogue and dispatch table. Each
handler delegates to a CAD OS shell (`cadctl`, `validator`, `patch_engine`,
`cad_diff`, or `visual_report`) and does not parse a DWG or call a raw SDK
directly. The shells keep the safety rules in one place: original DWGs remain
read-only, writes use a staged copy, unavailable routes return a truthful
blocked/not-implemented result, and no result is fabricated as success.

The official SDK owns protocol negotiation, stdio framing, lifecycle
notifications, `ping`, and the `CallToolResult` model. The adapter in
`tools/cadagent_mcp_sdk.py` bridges the existing handler envelopes to the SDK
without changing the published tool schemas.

## SDK version lanes

The shared interpreter and the isolated compatibility target are deliberately
separate:

| lane | package | installation surface | required gate |
|---|---|---|---|
| v1 (default) | `mcp==1.27.1` | `requirements.txt` / `install.ps1` | The matrix removes inherited `PYTHONPATH` and `CADAGENT_MCP_V2_TARGET`, verifies the exact v1 version before pytest, and verifies that `mcp.__file__` is outside the v2 target. |
| v2 (compatibility) | `mcp==2.0.0` | `requirements-mcp-sdk-v2.txt` into a dedicated `--target` directory | The matrix imports from the exact target and rejects both a different version and a module path outside that target. |

Run the matrix with `tools/test_cadagent_mcp_sdk_matrix.ps1`. Both lanes use the
same real stdio integration test and no AutoCAD or DWG execution.

## Server and transport

Start the endpoint with:

```powershell
python tools/cadagent_mcp.py --serve
```

The server name is `cadagent-mcp`; the module version constant is `0.1.0`.
`tools_manifest()` reports `transport: "mcp-sdk"` and
`protocol: "official-mcp-sdk-over-stdio"`. The client performs the normal SDK
`initialize` exchange, sends `notifications/initialized`, and may send `ping`.

The public endpoint has exactly 19 registered tools. `tools/list` exposes the
closed schemas from `_TOOLS`; every schema has `additionalProperties: false`.
The exact names are:

1. `cad.status`
2. `cad.inspect_drawing`
3. `cad.query_entities`
4. `cad.get_entity`
5. `cad.validate_ir`
6. `cad.registry_status`
7. `cad.registry_explain`
8. `cad.patch_dry_run`
9. `cad.patch_apply_staged`
10. `cad.anchor_set`
11. `cad.anchor_get`
12. `cad.anchor_list`
13. `cad.anchor_clear`
14. `cad.diff_before_after`
15. `cad.visual_report`
16. `cad.live_status`
17. `cad.run_operation`
18. `cad.inspect_display_membership`
19. `cad.run_command_template`

The public schema is the source of truth for required fields, defaults, enum
values, and descriptions. The implementation and the integration test must
keep the 19-name set and each `inputSchema` equal.

## Tool surface and mutation rules

| tool family | public behavior |
|---|---|
| `cad.status`, `cad.registry_status`, `cad.registry_explain` | Read router status or registry records through `cadctl`. |
| `cad.inspect_drawing`, `cad.query_entities`, `cad.get_entity`, `cad.validate_ir` | Read/extract/query/validate through the CAD shells; drawing input is staged and the original is not modified. |
| `cad.patch_dry_run`, `cad.patch_apply_staged` | Plan or apply a patch only on a staged copy; a missing peer implementation is reported as `not_implemented`. |
| `cad.anchor_set`, `cad.anchor_clear` | Write semantic-anchor data to a staged copy; `anchor_get` and `anchor_list` read an extracted IR. |
| `cad.diff_before_after`, `cad.visual_report` | Produce a structured IR diff or visual artifact, with unavailable producers reported truthfully. |
| `cad.live_status` | Reports that the persistent live ObjectARX pump is not attached; it never fakes live success. |
| `cad.run_operation` | Uses the registry allow-list and write-mode gate; `write_original` is always refused and the source DWG remains read-only. |
| `cad.inspect_display_membership` | Full AutoCAD/ObjectARX display-membership observation on a staged copy; no headless fallback. |
| `cad.run_command_template` | Runs only a governed command template with typed slots; raw command strings are not accepted. |

## Hidden legacy aliases and argument binding

The adapter accepts **hidden legacy aliases** for compatibility with existing
callers, but aliases are not present in `tools/list` and must not be added to a
published `inputSchema`. The accepted aliases are:

| public tool | hidden aliases accepted by the runtime binder |
|---|---|
| `cad.inspect_drawing` | `dwg_path`, `out_dir` |
| `cad.query_entities`, `cad.get_entity`, `cad.validate_ir`, `cad.anchor_get`, `cad.anchor_list` | `ir_path` |
| `cad.registry_explain` | `operation`, `id` |
| `cad.patch_apply_staged` | `dwg`, `out` |
| `cad.anchor_set` | `dwg_path`, `out_dir` |
| `cad.anchor_clear` | `dwg_path`, `out_dir` |
| `cad.diff_before_after` | `pre_ir_path`, `pre`, `post_ir_path`, `post` |
| `cad.visual_report` | `source`, `ir`, `dwg` |
| `cad.run_operation` | `operation`, `id`, `dwg_path`, `out_dir` |
| `cad.run_command_template` | `dwg_path` |
| `cad.inspect_display_membership` | `dwg_path`, `out_dir` |

The adapter uses an internal missing sentinel. Therefore an **omitted** optional
argument is absent from the handler dictionary, while an explicit JSON `null`
is retained as Python `None`. For example, omitted `mode` on
`cad.inspect_drawing` reaches the handler default, while `"mode": null` is
forwarded explicitly; omitted `geometry_scope` on
`cad.inspect_display_membership` selects `strict_layer_entities_v1`, while an
explicit JSON null is rejected as a structured error. This distinction is part
of the contract and is tested through a real `ClientSession`.

## Results and errors

For a registered tool, the adapter returns an SDK `CallToolResult` with:

- one text item in `content`, containing the JSON-serialized CAD handler
  envelope;
- the same handler envelope in `structuredContent`; and
- `isError` equal to `true` exactly when the envelope has `ok: false`.

Normal CAD outcomes such as a truthful `status: "blocked"` result remain a
structured tool result. A handler exception is caught and converted to a
**structured error** envelope with `ok: false`, `status: "error"`, an error
message, and the tool name; the SDK result then has `isError=true` and the same
object in `structuredContent`.

An unknown tool is different: the official SDK rejects it before a CAD handler
is called and returns a `CallToolResult` with `isError=true`,
`structuredContent=null`, and a text item beginning `Unknown tool:`. This is the
public behavior; the old local `_dispatch_tool` helper is test/diagnostic
coverage only and is not a JSON-RPC endpoint.

## Resources

The server registers no resources or resource templates. The official SDK
responses are therefore:

- `resources/list` → `resources: []`
- `resources/templates/list` → `resourceTemplates: []`

These empty lists are a deliberate contract, not an indication that the server
failed to initialize.

## Verification commands

```powershell
# Shared/default lane: requirements.txt installs both jsonschema and mcp==1.27.1.
python -m pip install -r requirements.txt

# Real stdio contract; uses nonexistent DWG paths and temporary directories only.
python -m pytest -q tests/integration/test_cadagent_mcp_sdk_stdio.py

# v1 + isolated v2 matrix (v2 is installed only under the target directory).
powershell -ExecutionPolicy Bypass -File .\tools\test_cadagent_mcp_sdk_matrix.ps1 -InstallV2
```

The matrix performs the exact version/path checks before each lane's pytest
run. It restores inherited `PYTHONPATH` and `CADAGENT_MCP_V2_TARGET` values in
`finally` blocks, including when a preflight or test fails.
