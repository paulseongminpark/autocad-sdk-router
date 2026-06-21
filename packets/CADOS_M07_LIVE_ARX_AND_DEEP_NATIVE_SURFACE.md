[PACKET]
PACKET_ID=CADOS_M07_LIVE_ARX_AND_DEEP_NATIVE_SURFACE
PROJECT=autocad-sdk-router
ROOT=D:\dev\99_tools\autocad-sdk-router
TARGET_AGENT=aclaude
FALLBACK_AGENT=acodex
MODE=workflow+ultracode
ROLE=@executor
EXECUTION_SCOPE=Live ARX pump and native-only deep surface completion
VERSION_TARGET=CAD OS Layer v1.0
PREVIOUS_PACKET=CADOS_M06_VISUAL_BATCH_GOLDEN_REGRESSION

GOAL:
- Build production-safe Live ARX Named Pipe Pump.
- Implement live read/status/visual operations.
- Implement or materially advance native-only deep surfaces.
- Keep write operations gated.
- Prove attended AutoCAD workflow if host is available.

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
   - Read M06 reports.
   - Verify `.dbx/.crx/.arx` build state.
   - Detect attended AutoCAD availability.
   - Do not kill or close AutoCAD.

2. Live ARX pump architecture
   Implement:
   - CADAGENT_START
   - CADAGENT_STOP
   - CADAGENT_STATUS
   - CADAGENT_PUMP
   - Named Pipe worker thread
   - local-only DACL where feasible
   - length-prefixed JSON
   - request queue
   - result queue
   - timeout/cancel
   - clean unload

3. Thread safety
   - Worker thread never touches AcDb directly.
   - All DB/editor operations run in AutoCAD main/document context through pump.
   - DllMain does not start worker threads.
   - Unload stops pipe and drains/cancels jobs safely.

4. Live operations
   Implement:
   - live.status
   - live.echo
   - live.list_documents
   - live.active_document
   - live.inspect_selection
   - live.inspect_entity
   - live.highlight_handles
   - live.clear_highlight
   - live.zoom_to_handles
   - live.render_view if feasible

5. Live write guard
   - live.apply_patch remains disabled unless M05 staged patch governor is explicitly reused.
   - No live save by default.
   - No original write.
   - Active command conflict rejects write-like jobs.

6. Deep native surfaces
   Implement or hard-block with evidence:
   - custom entity lifecycle
   - worldDraw rendering
   - AcRxProperty / OPM read/write
   - object overrules
   - persistent reactors
   - editor jigs
   - selection monitor
   - palette/status UI skeleton
   - custom object serialization/filer versioning
   - protocol extensions

7. Tests/smokes
   - unit protocol frame tests
   - queue lifecycle tests
   - safe shutdown tests
   - attended echo/status test if AutoCAD available
   - live list-documents if available
   - highlight/clear if available
   - deep native compile tests

8. Reports
   - `reports\live_pump_latest.json`
   - `reports\deep_native_latest.json`
   - `docs\LIVE_ARX_PUMP_SPIKE_REPORT.md`
   - `docs\NATIVE_DEEP_SURFACE_STATUS.md`

ACCEPTANCE:
- Live pump builds.
- Attended echo/status/list-docs passes when host available, or exact environment blocker recorded.
- No AcDb access from worker thread.
- Clean shutdown documented/tested.
- Native-only surfaces implemented or hard-blocked with evidence.
- Tests pass.
- Original DWGs unchanged.

FINAL_RESPONSE_FORMAT:
```txt
[CADOS M07 RESULT]
STATUS: PASS|PARTIAL_PASS|FAILED|BLOCKED
LIVE ARX:
- build:
- loaded:
- echo:
- status:
- list_documents:
- blocker:
DEEP NATIVE:
- implemented:
- blocked:
- evidence:
THREAD SAFETY:
- worker_acdb_access: no
- clean_shutdown:
TESTS:
- ...
NEXT:
- CADOS_M08_FULL_OPERATION_COVERAGE_CLOSURE
[/CADOS M07 RESULT]
```
[/PACKET]
