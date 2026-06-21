[PACKET]
PACKET_ID=CADOS_M04_OPERATION_REGISTRY_AND_TOOL_SURFACE
PROJECT=autocad-sdk-router
ROOT=D:\dev\99_tools\autocad-sdk-router
TARGET_AGENT=aclaude
FALLBACK_AGENT=acodex
MODE=workflow+ultracode
ROLE=@executor
EXECUTION_SCOPE=Operation Registry v2 and tool surface completion
VERSION_TARGET=CAD OS Layer v1.0
PREVIOUS_PACKET=CADOS_M03_NATIVE_ROUTER_RICH_IR_COMPLETION

GOAL:
- Make Operation Registry v2 authoritative for status/explain/coverage.
- Expand cadctl read/query/registry surface.
- Advance MCP tool contract skeleton into working dispatch.
- Ensure all catalogued operations are classified and high-value read operations are implemented.
- Preserve native/router stability.

CONTEXT:
- CAD OS M01 established a walking skeleton: cadctl -> router extraction -> DWG Graph IR -> SQLite -> validate.
- CAD OS M02 was intended to advance native graph/router/rich IR/patch/live foundations.
- This packet assumes the executor reads `reports/latest_status.json`, `docs/CAD_OS_BUILD_STATUS.md`, `handoff/NEXT_STEP.md`, and prior packet reports before changing anything.
- If prior packet outputs are missing, absorb the missing prerequisite work into this packet when safe; otherwise mark PARTIAL_PASS/BLOCKED honestly.

READ_ALLOW:
- D:\dev\99_tools\autocad-sdk-router
- D:\dev\99_tools\autocad-sdk-router\**
- D:\dev\_ariadne\_daedalus\external\cad_os\**
- AutoCAD 2027 installation paths required for build/test.
- ObjectARX/ObjectDBX SDK include/lib paths required for build/test.
- Visual Studio/MSBuild toolchain paths required for build/test.
- Staged/golden DWG folders under the CAD OS root.

CHANGE_ONLY:
- D:\dev\99_tools\autocad-sdk-router\README.md
- D:\dev\99_tools\autocad-sdk-router\.gitignore
- D:\dev\99_tools\autocad-sdk-router\tools\**
- D:\dev\99_tools\autocad-sdk-router\config\**
- D:\dev\99_tools\autocad-sdk-router\schemas\**
- D:\dev\99_tools\autocad-sdk-router\src\**
- D:\dev\99_tools\autocad-sdk-router\docs\**
- D:\dev\99_tools\autocad-sdk-router\tests\**
- D:\dev\99_tools\autocad-sdk-router\reports\**
- D:\dev\99_tools\autocad-sdk-router\runs\**
- D:\dev\99_tools\autocad-sdk-router\staging\**
- D:\dev\99_tools\autocad-sdk-router\handoff\**
- D:\dev\99_tools\autocad-sdk-router\packets\**
- D:\dev\_ariadne\_daedalus\external\cad_os\**

DO_NOT_CHANGE:
- Any original user DWG outside CAD OS staged test folders.
- Any Ariadne runtime DB / L0 / L1 / L3 / L4 / L5 store.
- Any Ariadne `data/events/agent_events.jsonl`.
- Any Daedalus source code outside `external\cad_os`.
- Any secret / `.env` / token / key / `.pem` / `.p12` / credential / auth cache.
- Any remote repository state.
- Do not push.
- Do not kill AutoCAD.
- Do not force-close user documents.
- Do not enable `write_original` by default.
- Do not expose raw AutoCAD command execution as an agent-facing API.
- Do not mark unimplemented or unavailable operations as PASS.

NON_GOALS:
- Do not build Daedalus app logic.
- Do not implement Ariadne runtime write.
- Do not perform original DWG writes.
- Do not claim v1 PASS unless all v1 gates pass.
- Do not hide skipped environment-dependent tests.


## Status Values

- `PASS`: packet acceptance gates are actually met.
- `PARTIAL_PASS`: substantial progress, but one or more non-fatal or environment-dependent gates remain incomplete and are explicitly recorded.
- `FAILED`: implementation or tests broke core behavior, or safe recovery/handoff could not be produced.
- `BLOCKED`: root/toolchain/host/golden fixture missing and no meaningful safe progress is possible.



## Required Continuity Outputs

At the end of this packet, update or create:

- `docs\CAD_OS_BUILD_STATUS.md`
- `docs\CAD_OS_FULL_STACK_HANDOFF.md`
- `docs\CAD_OS_V1_ACCEPTANCE.md`
- `reports\latest_status.json`
- `reports\<PACKET_ID>.md`
- `reports\operation_coverage_latest.json`
- `reports\validation_latest.json`
- `handoff\TAKEOVER.md`
- `handoff\NEXT_STEP.md`
- `handoff\zip\<PACKET_ID>.zip`
- `handoff\zip\index.md`
- `packets\<PACKET_ID>.md`
- `packets\PACKET_INDEX.md`

Also update Daedalus-consumable handoff:

- `D:\dev\_ariadne\_daedalus\external\cad_os\CADOS_LATEST_SUMMARY.md`
- `D:\dev\_ariadne\_daedalus\external\cad_os\cad_os_latest_status.json`
- `D:\dev\_ariadne\_daedalus\external\cad_os\CAD_OS_ADAPTER_IMPORT_NOTES.md`
- `D:\dev\_ariadne\_daedalus\external\cad_os\CAD_OS_V1_CAPABILITIES.json`

If the Daedalus path is unavailable, do not fail the CAD OS packet solely for that reason. Record the skipped handoff and continue.


BUNDLE:

1. Baseline
   - Read M03 reports.
   - Verify router graph op status.
   - Run `python tools\cadctl_cli.py registry coverage`.
   - Run tests.

2. Registry source of truth
   - Update `config\operations.v2.json`, `host_matrix.v2.json`, `capabilities.v2.json`, `policy.v2.json`.
   - Ensure every catalogued op has:
     operation, family, status, hosts, engines, write_level, handler, schema refs, policy, tests, evidence_refs, notes.
   - Status values only:
     implemented, wired, stub, catalogued, blocked, deprecated.
   - No `unknown`.
   - No unclassified operation.

3. Coverage policy
   - `implemented`: handler + current test/evidence exists.
   - `wired`: route exists but coverage incomplete.
   - `stub`: intentionally returns NOT_IMPLEMENTED.
   - `blocked`: hard API/host/license/environment blocker with evidence.
   - `catalogued`: known op not yet target/implementation.
   - `deprecated`: explicitly not used.

4. Router/cadctl integration
   - `autocad-router.ps1 -Action explain -Operation <op>` returns registry-derived explanation where safe.
   - `cadctl_cli.py registry list`.
   - `cadctl_cli.py registry coverage`.
   - `cadctl_cli.py registry explain <op>`.
   - `cadctl_cli.py status --json` includes registry summary.
   - Result envelopes include `registry_operation_status`.

5. Tool surface
   Implement/advance:
   - status
   - inspect
   - query
   - get-entity
   - validate
   - registry list/coverage/explain
   - patch dry-run shell
   - diff shell
   - visual report shell
   - live status shell

6. MCP contract
   - `tools\cadagent_mcp.py` exposes:
     cad.status, cad.inspect_drawing, cad.query_entities, cad.get_entity,
     cad.validate_ir, cad.registry_status, cad.registry_explain,
     cad.patch_dry_run, cad.diff_before_after, cad.visual_report, cad.live_status.
   - Tool handlers call cadctl, not raw SDK.
   - If true MCP dependency unavailable, use stdio/mock handler with identical request/response schema.

7. Implement additional high-value read operations
   Target all feasible:
   - inspect.layers
   - inspect.linetypes
   - inspect.text_styles
   - inspect.dim_styles
   - inspect.blocks
   - inspect.layouts
   - inspect.xrefs
   - inspect.dictionaries
   - inspect.xdata
   - inspect.xrecords
   - inspect.entities
   - query.entities
   - validate.ir

8. Tests
   - registry schema
   - no unknown ops
   - every operation has schema/policy/evidence fields
   - coverage math
   - cadctl registry CLI
   - router explain if implemented
   - MCP handler dispatch

9. Reports
   - `reports\operation_coverage_latest.json`
   - `reports\operation_coverage_latest.md`
   - `reports\tool_surface_latest.json`
   - `reports\mcp_contract_latest.json`

ACCEPTANCE:
- Registry has 100% classification.
- No `unknown` operations.
- Existing 29 ops mapped.
- `inspect.database.graph` mapped as implemented if M03 passed.
- cadctl registry commands work.
- MCP/tool skeleton handlers work without raw SDK.
- Tests pass.
- Reports/handoff generated.
- No original DWG modified.

FINAL_RESPONSE_FORMAT:
```txt
[CADOS M04 RESULT]
STATUS: PASS|PARTIAL_PASS|FAILED|BLOCKED
REGISTRY:
- total:
- implemented:
- wired:
- stub:
- catalogued:
- blocked:
- deprecated:
- unknown: 0
TOOL SURFACE:
- cadctl:
- mcp:
- router_explain:
TESTS:
- ...
REPORTS:
- ...
BLOCKERS:
- ...
NEXT:
- CADOS_M05_PATCH_DIFF_VALIDATION_TRANSACTION
[/CADOS M04 RESULT]
```
[/PACKET]
