# CADOS M03 Native Router Rich IR Completion - Detailed Result

## Packet

- Packet ID: `CADOS_M03_NATIVE_ROUTER_RICH_IR_COMPLETION`
- Project: `autocad-sdk-router`
- Root: `D:\dev\99_tools\autocad-sdk-router`
- Execution scope: native router and rich IR completion
- Previous packet gate: `CADOS_M02_V1_COMPLETION_ULTRACODE`
- Result timestamp: `2026-06-22T04:25:50+09:00`
- Result status: `PASS`

## Boundary Confirmation

- Working folder used: `D:\dev\99_tools\autocad-sdk-router`
- Packet source used: `D:\dev\_ariadne\alm\docs\CADOS_COMPLETION_PACKET_BUNDLE_M03_TO_FINAL\packets\CADOS_M03_NATIVE_ROUTER_RICH_IR_COMPLETION.md`
- Claude Code session context checked before packet execution:
  - Claude project history source: `C:\Users\PAUL\.claude\history.jsonl`
  - Target title: `infra`
  - Target session id: `03c5e451-98f2-406a-a3c5-e9bfaa575265`
  - Latest M02 result in that session: `PASS`
  - M02 evidence recorded by Claude: final acceptance `15/15`, no remote push, no original DWG write.
- Scope was not widened to M05+.
- Daedalus/Ariadne app integration was not started.
- Remote push was not performed.
- Original DWG write was not enabled.
- AutoCAD was not killed or force-closed.

## Baseline Evidence

- Git before: `dc6bc03`
- Git after: `dc6bc03`
- Commit made by this packet: none
- Remote push: false
- Existing dirty files were preserved and worked with in place.
- Router live status used before/through execution:
  - Report: `reports\autocad_router_status_latest.json`
  - Router result: `ALL_AVAILABLE`
  - Route count: 11
  - Available count: 11
- cadctl/router continuity reports updated:
  - `reports\latest_status.json`
  - `reports\v1_acceptance_latest.json`
  - `reports\validation_latest.json`

## Router-Wired Operation

The M03 packet required the native graph operation to be available through the router surface, not only by direct helper scripts.

- Operation: `inspect.database.graph`
- Status: `PASS`
- Write mode: `read`
- Command:

```powershell
powershell -File tools\autocad-router.ps1 -Action run -Intent dwg -InputPath staging\dwg_20260617_191504\input.dwg -Operation inspect.database.graph -WriteMode read
```

- Native smoke report: `reports\native_smoke_latest.json`
- Result reference: `D:\dev\99_tools\autocad-sdk-router\runs\dwg_truth_autocad_cad_job_20260622_035227\native_cad_job_result.json`
- Job reference: `D:\dev\99_tools\autocad-sdk-router\runs\dwg_truth_autocad_cad_job_20260622_035227\cad_job_request.json`
- Staged runtime input: `D:\dev\99_tools\autocad-sdk-router\staging\dwg_job_20260622_035227\input.dwg`
- Original/staged golden input: `staging\dwg_20260617_191504\input.dwg`
- Modelspace entities returned by router graph op: 21,747
- Missing result artifact behavior: treated as failure; no synthetic PASS path was used.

## Rich DWG Graph IR

- Rich IR command:

```powershell
python tools\cadctl_cli.py inspect --dwg staging\dwg_20260617_191504\input.dwg --out runs\m03_rich_ir --mode rich --include-rich
```

- IR reference: `runs\m03_rich_ir\dwg_graph_ir.json`
- cadctl result reference: `runs\m03_rich_ir\cad_result.json`
- Run folder: `runs\m03_rich_ir`
- SQLite projection: `runs\m03_rich_ir\dwg_graph_ir.sqlite`
- IR schema: `ariadne.dwg_graph_ir.v1`
- Rich IR report: `reports\rich_ir_latest.json`
- Coverage level: `native_full`
- Entity count: 21,747
- Entity count consistency: `diagnostics.entity_count == len(entities) == 21747`
- Validation evidence: `reports\validation_latest.json`

## Entity Type Coverage

| Entity type | Count | M03 status |
|---|---:|---|
| LINE | 16,276 | implemented |
| INSERT | 2,027 | implemented |
| MTEXT | 106 | implemented |
| HATCH | 669 | implemented with loop extraction |
| POLYLINE | 1,874 | implemented |
| ARC | 753 | implemented |
| CIRCLE | 33 | implemented |
| TEXT | 9 | implemented |

The packet's requested geometry priority list was addressed for the golden DWG surface actually present in this staged fixture. Entity types not present in this fixture remain covered through schema/diagnostic handling where available rather than being faked as fixture evidence.

## Rich Section Coverage

Implemented / present in the M03 IR:

- `database`
- `symbol_tables`
- `block_table_records`
- `block_definitions`
- `layouts`
- `xrefs`
- `dictionaries`
- `extension_dictionaries`
- `xrecords`
- `xdata`
- `hatch_loops`
- `entities`

Implemented section counts:

| Section | Count |
|---|---:|
| layers | 70 |
| linetypes | 15 |
| text_styles | 4 |
| dim_styles | 4 |
| viewports | 1 |
| app_ids | 9 |
| block_table_records | 248 |
| block_definitions | 245 |
| layouts | 3 |
| xrefs | 0 |
| dictionary_entries | 16 |
| xrecords | 2 |
| xrecord_items | 7 |
| xdata_blocks | 751 |
| xdata_items | 1,069 |
| extension_dictionaries | 0 |
| extension_dictionary_entries | 0 |
| extension_xrecords | 0 |
| extension_xrecord_items | 0 |
| hatch_loops | 702 |
| hatch_loop_vertices | 9,572 |

Explicit non-faked limitations:

- `proxy_objects`: partial diagnostics only.
- `groups`: explicitly skipped for this packet result.
- `materials`: explicitly skipped for this packet result.
- `plot_settings`: explicitly skipped for this packet result.
- Empty sections such as `xrefs` and `extension_dictionaries` are emitted explicitly instead of being omitted.

## Non-ASCII Fidelity

- Status: `PASS`
- Evidence file: `reports\rich_ir_latest.json`
- Evidence field: `non_ascii_fidelity.sample_layer`
- Preserved sample value is stored in UTF-8 JSON in the evidence file.
- A console rendering issue can display mojibake in some PowerShell output, but the JSON evidence file itself contains the UTF-8 string.
- The native conversion path was changed away from lossy ASCII conversion for layer/block/table/xdata strings where surfaced by the native reader.

## Native Build And ARX Relink

- Build wrapper: `tools\build_native_acad.ps1`
- Build report: `reports\build_native_latest.json`
- Build log: `reports\build_native_latest.log`
- Wrapper log: `reports\build_native_wrapper_latest.log`
- CRX: `PASS`
- ARX: `PASS`
- ARX relink mode: `versioned_lock_bypass`
- Versioned ARX name: `Ariadne.AcadNative.live_20260622_034352`
- Versioned ARX artifact: `src\Ariadne.AcadNative\bin\x64\Release\Ariadne.AcadNative.live_20260622_034352.arx`
- Canonical ARX was locked by the running AutoCAD process, so the packet used versioned output rather than killing AutoCAD.
- Blockers: none for M03 acceptance.

## Native Code / Tooling Changes

Primary implementation surfaces updated by M03:

- `src\Ariadne.AcadNative\AriadneNativeJob.cpp`
  - Added richer database graph extraction.
  - Added xdata grouping and resbuf decoding.
  - Added xrecord decoding.
  - Added extension dictionary surface.
  - Added hatch loop extraction.
  - Added coverage diagnostics for new rich sections.
- `tools\ir_builder.py`
  - Carries native rich sections into `dwg_graph_ir.json`.
  - Preserves entity xdata, hatch loops, pattern names, closure state, and extension dictionary handles.
- `tools\build_native_acad.ps1`
  - Fixed wrapper result handling so MSBuild output does not corrupt exit-code logic.
- `tests\unit\test_dwg_graph_ir_schema.py`
  - Added M03 rich section carry-through coverage.

## Validation And Tests

Fresh full test evidence from the repo-root rerun after report generation:

- `CADOS_LIVE=1 python -m pytest -q`
  - Result: `250 passed in 74.56s`
- `CADOS_LIVE=1 python -m unittest discover -s tests -p "test*.py"`
  - Result: `Ran 213 tests in 72.214s`, `OK`

M03-specific validation evidence:

- `reports\validation_latest.json`
  - Status: `pass`
  - Required artifact gate: pass
  - IR schema gate: pass
  - Entity count consistency gate: pass
  - No-original-write evidence gate: pass
- `reports\native_smoke_latest.json`
  - Status: `PASS`
  - Router status: `PASS`
  - Operation: `inspect.database.graph`
  - Write mode: `read`

## Required Continuity Outputs

Created or updated for this packet:

- `docs\CAD_OS_BUILD_STATUS.md`
- `docs\CAD_OS_FULL_STACK_HANDOFF.md`
- `docs\CAD_OS_V1_ACCEPTANCE.md`
- `reports\latest_status.json`
- `reports\CADOS_M03_NATIVE_ROUTER_RICH_IR_COMPLETION.md`
- `reports\operation_coverage_latest.json`
- `reports\validation_latest.json`
- `reports\rich_ir_latest.json`
- `reports\native_smoke_latest.json`
- `handoff\TAKEOVER.md`
- `handoff\NEXT_STEP.md`
- `handoff\zip\CADOS_M03_NATIVE_ROUTER_RICH_IR_COMPLETION.zip`
- `handoff\zip\index.md`
- `packets\CADOS_M03_NATIVE_ROUTER_RICH_IR_COMPLETION.md`
- `packets\PACKET_INDEX.md`

Daedalus-consumable handoff updated:

- `D:\dev\_ariadne\_daedalus\external\cad_os\CADOS_LATEST_SUMMARY.md`
- `D:\dev\_ariadne\_daedalus\external\cad_os\cad_os_latest_status.json`
- `D:\dev\_ariadne\_daedalus\external\cad_os\CAD_OS_ADAPTER_IMPORT_NOTES.md`
- `D:\dev\_ariadne\_daedalus\external\cad_os\CAD_OS_V1_CAPABILITIES.json`

## Safety Gates

- No original DWG was modified.
- The graph run used staged copies under `staging\`.
- `write_original` was not enabled.
- Raw AutoCAD command execution was not exposed as an agent-facing API.
- No unavailable operation was marked as implemented.
- No remote push was performed.
- AutoCAD was not killed.

## Packet Final Result Block

```txt
[CADOS M03 RESULT]
STATUS: PASS
ROOT:
- D:\dev\99_tools\autocad-sdk-router
GIT:
- before: dc6bc03
- after: dc6bc03
- commit: none
ROUTER GRAPH OP:
- status: PASS
- command: powershell -File tools\autocad-router.ps1 -Action run -Intent dwg -InputPath staging\dwg_20260617_191504\input.dwg -Operation inspect.database.graph -WriteMode read
- result_ref: D:\dev\99_tools\autocad-sdk-router\runs\dwg_truth_autocad_cad_job_20260622_035227\native_cad_job_result.json
RICH IR:
- status: PASS
- sections_implemented: database, symbol_tables, block_table_records, block_definitions, layouts, xrefs, dictionaries, extension_dictionaries, xrecords, xdata, hatch_loops
- sections_partial: proxy_objects only; groups/materials/plot_settings skipped explicitly
- non_ascii_fidelity: PASS; evidence in reports\rich_ir_latest.json
- ir_ref: runs\m03_rich_ir\dwg_graph_ir.json
NATIVE BUILD:
- crx: PASS
- arx: PASS via versioned_lock_bypass (Ariadne.AcadNative.live_20260622_034352)
- blockers: none; canonical .arx was locked by running AutoCAD, versioned relink succeeded without killing AutoCAD
TESTS:
- pytest: 250 passed
- unittest: 213 OK
REPORTS:
- reports\rich_ir_latest.json
- reports\native_smoke_latest.json
- reports\validation_latest.json
- handoff\zip\CADOS_M03_NATIVE_ROUTER_RICH_IR_COMPLETION.zip
BLOCKERS:
- none for M03
NEXT:
- CADOS_M04_OPERATION_REGISTRY_AND_TOOL_SURFACE
[/CADOS M03 RESULT]
```
