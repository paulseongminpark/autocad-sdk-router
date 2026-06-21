[PACKET]
PACKET_ID=CADOS_M03_NATIVE_ROUTER_RICH_IR_COMPLETION
PROJECT=autocad-sdk-router
ROOT=D:\dev\99_tools\autocad-sdk-router
TARGET_AGENT=aclaude
FALLBACK_AGENT=acodex
MODE=workflow+ultracode
ROLE=@executor
EXECUTION_SCOPE=Native router and rich IR completion
VERSION_TARGET=CAD OS Layer v1.0
PREVIOUS_PACKET=CADOS_M02_V1_COMPLETION_ULTRACODE

GOAL:
- Finish native read truth layer.
- Router-wire `inspect.database.graph`.
- Expand rich DWG Graph IR extraction.
- Resolve or safely version `.arx` build output.
- Fix non-ASCII string fidelity.
- Preserve M01 walking skeleton and existing 29 operations.

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

1. Baseline and recovery point
   - Read prior reports.
   - Run router status.
   - Run `python tools\cadctl_cli.py status`.
   - Run current tests.
   - Snapshot git status and HEAD.
   - Record every pre-existing dirty file.

2. Router-wire `inspect.database.graph`
   - Inspect existing router allow-list, alias, action parsing, job envelope, and native invocation path.
   - Add a safe route for:
     `-Action run -Operation inspect.database.graph -JobPath <job.json>`
   - Add explain route if missing:
     `-Action explain -Operation inspect.database.graph`
   - Do not remove any existing alias or wired operation.
   - Ensure result uses `result_ref`.
   - Every missing output artifact is an error, not success.

3. Rich native IR extraction
   Implement or finish extraction for:
   - database metadata
   - header variables where accessible
   - units / INSBASE / extents
   - summary info where accessible
   - layers
   - linetypes
   - text styles
   - dim styles
   - block table records
   - layouts
   - plot settings where accessible
   - modelspace entities
   - paperspace/layout entities
   - block definitions
   - block references and transforms
   - attributes
   - xrefs
   - named object dictionary
   - extension dictionaries
   - xrecords
   - xdata by regapp
   - groups
   - materials
   - constraints / associativity if accessible
   - reactors if accessible
   - custom classes
   - proxy objects
   - diagnostics/coverage

4. Geometry extraction priority
   - LINE
   - LWPOLYLINE
   - POLYLINE
   - CIRCLE
   - ARC
   - TEXT
   - MTEXT
   - INSERT
   - DIMENSION
   - HATCH
   - SPLINE
   - ELLIPSE
   - 3D polyline / solid diagnostics

5. Non-ASCII fidelity
   - Replace lossy `acharToAscii` or equivalent.
   - Output UTF-8 JSON.
   - Preserve layer, block, linetype, text style, text content, xdata strings.
   - Add staged fixture or targeted test for Korean/non-ASCII strings if safe.
   - If unavailable, create deterministic unit-level converter test.

6. `.arx` relink/versioned output
   - Do not kill AutoCAD.
   - If fixed `.arx` output is locked, build versioned output:
     `Ariadne.AcadNative.live_m03.arx`.
   - Document loader command.
   - Preserve prior working `.arx`.

7. Native build and smoke
   - Run actual build command, likely `tools\build_native_acad.ps1`.
   - Capture `reports\build_native_latest.log`.
   - Run accoreconsole smokes on staged DWG.
   - Run direct and router-routed graph op.
   - Validate entity count equality.

8. Update schemas/docs/tests
   - Update `schemas\dwg_graph_ir.v1.schema.json`.
   - Update `docs\DWG_GRAPH_IR_SPEC.md`.
   - Add tests for all rich IR sections.
   - Add integration test for router-routed graph op.

9. Reports and handoff
   - Generate `reports\rich_ir_latest.json`.
   - Generate `reports\native_smoke_latest.json`.
   - Update `reports\v1_acceptance_latest.json`.
   - Update Daedalus external CAD OS handoff.

ACCEPTANCE:
- Router-routed `inspect.database.graph` works on staged DWG or exact blocker recorded.
- Rich IR JSON parses and conforms to schema.
- Entity count matches prior truth.
- Major IR sections are present; empty sections are explicit, not missing.
- Non-ASCII fidelity is fixed or explicit blocker with test evidence.
- `.crx` builds.
- `.arx` fixed or versioned build succeeds, or exact lock blocker recorded.
- Existing 29 ops remain intact.
- Tests run.
- No original DWG modified.
- Reports and handoff zip produced.

FINAL_RESPONSE_FORMAT:
```txt
[CADOS M03 RESULT]
STATUS: PASS|PARTIAL_PASS|FAILED|BLOCKED
ROOT:
- ...
GIT:
- before:
- after:
- commit:
ROUTER GRAPH OP:
- status:
- command:
- result_ref:
RICH IR:
- status:
- sections_implemented:
- sections_partial:
- non_ascii_fidelity:
- ir_ref:
NATIVE BUILD:
- crx:
- arx:
- blockers:
TESTS:
- ...
REPORTS:
- ...
BLOCKERS:
- ...
NEXT:
- CADOS_M04_OPERATION_REGISTRY_AND_TOOL_SURFACE
[/CADOS M03 RESULT]
```
[/PACKET]
