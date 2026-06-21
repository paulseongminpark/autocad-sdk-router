[PACKET]
PACKET_ID=CADOS_M06_VISUAL_BATCH_GOLDEN_REGRESSION
PROJECT=autocad-sdk-router
ROOT=D:\dev\99_tools\autocad-sdk-router
TARGET_AGENT=aclaude
FALLBACK_AGENT=acodex
MODE=workflow+ultracode
ROLE=@executor
EXECUTION_SCOPE=Visual verification, batch runner, golden regression completion
VERSION_TARGET=CAD OS Layer v1.0
PREVIOUS_PACKET=CADOS_M05_PATCH_DIFF_VALIDATION_TRANSACTION

GOAL:
- Implement visual verification artifacts where possible.
- Add batch/wave runner for multiple DWGs.
- Build golden regression suite.
- Add performance and scale gates.
- Produce review-ready reports.

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
   - Read M05 reports.
   - Verify patch/diff/validation artifacts.

2. Visual verification
   Implement or complete:
   - render.modelspace
   - render.layout
   - render.viewport
   - render.with_handle_overlay
   - compare.render_before_after

   Preferred routes:
   - CoreConsole plot/export if safe
   - existing router render route if available
   - full AutoCAD attended render only through controlled tool/adapter
   - no raw agent-facing command

3. Visual artifact schema
   Required:
   - before.png/pdf
   - after.png/pdf
   - overlay.png/pdf if feasible
   - visual_diff.json
   - viewport metadata
   - handles highlighted
   - render status

4. If render unavailable
   - Return NOT_IMPLEMENTED with exact reason.
   - Do not mark visual PASS.
   - Continue batch/golden lanes.

5. Batch/wave runner
   Implement:
   - manifest
   - per-DWG staging
   - read-only inspect batch
   - validation batch
   - optional patch batch only on staged copies
   - retry/quarantine
   - failure isolation
   - summary report

6. Golden regression
   Create/update:
   - `tests\golden\golden_manifest.json`
   - `tests\golden\expected_counts.json`
   - expected schema coverage
   - expected registry coverage
   - expected patch/diff result for staged fixture
   - expected no-original-write

7. Performance/scale
   Run on:
   - small fixture
   - known 21,747 entity fixture
   - large 291,706 entity smoke fixture if available
   Record:
   - duration
   - memory if available
   - output size
   - SQLite load time
   - validator time

8. Review reports
   Generate static HTML/MD report if possible:
   - run overview
   - artifacts
   - visual thumbnails/links
   - gate table
   - failures
   - quarantined files

9. Tests
   - visual schema
   - batch manifest
   - quarantine
   - golden counts
   - performance report parse
   - report generation

ACCEPTANCE:
- Batch runner works for read-only inspect/validate.
- Golden regression passes.
- Visual artifacts produced or explicit NOT_IMPLEMENTED with exact blocker.
- Reports generated.
- Tests pass.
- Original DWGs unchanged.

FINAL_RESPONSE_FORMAT:
```txt
[CADOS M06 RESULT]
STATUS: PASS|PARTIAL_PASS|FAILED|BLOCKED
VISUAL:
- status:
- artifacts:
BATCH:
- status:
- manifest:
- successes:
- failures:
GOLDEN:
- status:
- fixtures:
PERFORMANCE:
- status:
- large_fixture:
REPORTS:
- ...
BLOCKERS:
- ...
NEXT:
- CADOS_M07_LIVE_ARX_AND_DEEP_NATIVE_SURFACE
[/CADOS M06 RESULT]
```
[/PACKET]
