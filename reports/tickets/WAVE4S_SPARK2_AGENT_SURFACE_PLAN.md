# WAVE4S SPARK2 AGENT SURFACE PLAN

## Objective
Implement and harden the cadctl / MCP agent surface so:
- raw command entry paths stay non-exposed and hard-blocked,
- agent-facing wrappers remain JSON-only and truthful,
- explain/status routes are surfaced through the control shell and router,
- policy gates enforce `write_original` safety and live-attended constraints.

## Claim scope
Primary claim source: `reports/tickets/WAVE4S_SPARK2_AGENT_SURFACE_CLAIMS.json`

Claimed ops:
- `command.invoke.coroutine`
- `command.invoke.sync`
- `command.invoke.sync.resbuf`
- `command.queue.post`
- `doc.sendstring`
- `automate.com.send_command`
- `wave4s.agent_surface.capability_metadata`

## Planned implementation edits (applied)
1. **cadctl CLI/Wrapper hardening**
   - `tools/cadctl_cli.py`
     - keep compatibility with `--json` at top-level (`cadctl --json <command>`).
     - add top-level `explain` alias for registry explain (`cadctl explain <operation_id>`).

2. **Existing wrappers already in place**
   - `tools/cadctl.py`:
     - read-only status snapshot from published router status JSON,
     - registry explain/list/coverage,
     - staged extraction/IR pathways.
   - `tools/cadagent_mcp.py`:
     - JSON-RPC stdlib mock transport (`transport: mock`),
     - fixed 12 `cad.*` tools and dispatch coverage,
     - all handlers delegated to shells (`cadctl` / `patch_engine` / `validator` / `cad_diff` / `visual_report`).
   - `tools/operation_coverage_matrix.py`:
     - raw-command detection + policy-derived risk class + `agent_exposed` gates.

3. **Policy and evidence sources already present**
   - `config/policy.v2.json`
   - `config/operations.v2.json`
   - `docs/FALLBACK_POLICY.md`

## Validation tasks
- Run focused pytest:
  - `tests/unit/test_cadctl.py`
  - `tests/unit/test_mcp_tool_contract.py`
  - `tests/unit/test_m08o_fallback.py`
  - `tests/unit/test_m08_operation_coverage.py`
- Check reports for closure and gate status:
  - `reports/v1_operation_gate_latest.json`
  - `reports/operation_coverage_latest.json`

## Exit criteria (closeout)
- No raw-command operation is `agent_exposed`.
- No operation defaults to `original_write_default == true`.
- Raw-command hard-block operations carry `SAFETY_FORBIDDEN` reasons and evidence refs.
- cadctl CLI exposes explain/status surfaces and accepts global `--json`.
- MCP transport remains mock with no raw SDK handlers.

## Notes
This SPARK2 is surface/policy closure work; no catalogued/wired behavior changes are required beyond harden-and-doc.
