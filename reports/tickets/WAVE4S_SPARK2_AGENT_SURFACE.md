# WAVE4S SPARK2 AGENT SURFACE REPORT

- **Packet:** SPARK2_AGENT_SURFACE
- **Route:** `D:/dev/99_tools/autocad-sdk-router_w4s_spark2_surface`
- **Start timestamp:** 2026-06-24
- **Working branch:** `cados/w4s-spark2-agent-surface`

## Claim status
| Claim operation | Mode | Final status | Evidence summary |
|---|---|---|---|
| `command.invoke.coroutine` | secondary_implementation_or_evidence | completed (hard-blocked + exposed non-agent) | `config/operations.v2.json` `policy.v2` `docs/FALLBACK_POLICY.md` `tests/unit/test_m08o_fallback.py` |
| `command.invoke.sync` | secondary_implementation_or_evidence | completed (hard-blocked + exposed non-agent) | same as above |
| `command.invoke.sync.resbuf` | secondary_implementation_or_evidence | completed (hard-blocked + exposed non-agent) | same as above |
| `command.queue.post` | secondary_implementation_or_evidence | completed (hard-blocked + exposed non-agent) | same as above |
| `doc.sendstring` | secondary_implementation_or_evidence | completed (hard-blocked + exposed non-agent) | same as above |
| `automate.com.send_command` | secondary_implementation_or_evidence | completed (hard-blocked + exposed non-agent) | `config/operations.v2.json` `reports/WAVE3_REMAINING_HARDBLOCK_REAUDIT.md` `tests/unit/test_m08o_fallback.py` |
| `wave4s.agent_surface.capability_metadata` | primary | completed | `tools/operation_coverage_matrix.py` `tools/cadctl.py` `tools/cadctl_cli.py` `tests/unit/test_cadctl.py` `reports/operation_coverage_latest.json` |

## Implemented deltas
- Added global `--json` support to `cadctl_cli.py` (compatibility flag accepted at top-level while preserving per-command JSON output behavior).
- Added `cadctl explain <operation_id>` command alias to route directly to registry explain.
- Strengthened CLI test coverage for explain/status behavior with global JSON path in `tests/unit/test_cadctl.py`.

## Safety evidence
- `command.invoke.*`, `command.queue.post`, `module.command.lookup`, `doc.sendstring`, and `automate.com.send_command` are all
  `status: blocked` with `SAFETY_FORBIDDEN` blocker reasons.
- `operation_coverage_matrix.py` computes risk/agent exposure and the operation matrix gates enforce:
  - `no_agent_exposed_raw_command`
  - `no_original_write_default`
  - `zero_untested_implemented`
- MCP tool handler manifest still exposes only shell-backed tools with `transport: mock`.

## Report outputs (post-change)
- `reports/v1_operation_gate_latest.json` — all operation-coverage gate assertions pass.
- `reports/operation_coverage_latest.json` and `reports/operation_coverage_full_matrix.json` continue to reflect 517 ops with:
  - implemented: 457
  - blocked: 60
  - no catalogued/stub/unknown/deferred.

## Validation commands executed
```bash
python -m pytest tests/unit/test_cadctl.py \
                 tests/unit/test_mcp_tool_contract.py \
                 tests/unit/test_m08o_fallback.py \
                 tests/unit/test_m08_operation_coverage.py
```

## Result
**PASS** — SPARK2 agent-surface hardening and policy gates are in a verified, truthful state with no raw command exposure and no default original-write semantics.
