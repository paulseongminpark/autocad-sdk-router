[PACKET]
PACKET_ID=CADOS_M05_PATCH_DIFF_VALIDATION_TRANSACTION
PROJECT=autocad-sdk-router
ROOT=D:\dev\99_tools\autocad-sdk-router
TARGET_AGENT=aclaude
FALLBACK_AGENT=acodex
MODE=workflow+ultracode
ROLE=@executor
EXECUTION_SCOPE=Patch, diff, validation, transaction, journal completion
VERSION_TARGET=CAD OS Layer v1.0
PREVIOUS_PACKET=CADOS_M04_OPERATION_REGISTRY_AND_TOOL_SURFACE

GOAL:
- Implement real staged-copy patch execution for initial safe operations.
- Implement CAD Diff.
- Implement deterministic validation and journal.
- Keep original DWG writes disabled.
- Ensure write lifecycle is Patch -> Staged Copy -> Apply -> Diff -> Validate -> Journal -> Report.

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
   - Read M04 reports.
   - Verify registry and rich IR are available.
   - Verify staged/golden DWG path and original hash.

2. Patch policy
   - `write_original=false` by default.
   - `staged_write` allowed.
   - `dry_run=true` default.
   - `commit` and `save` only apply to staged copy.
   - Raw command denied.
   - Original write requires explicit user-approved future packet, not M05.

3. Patch schema and ops
   Implement:
   - create_line
   - create_polyline
   - create_text
   - set_layer
   - move_entity
   - delete_entity only with `allow_delete_staged=true`
   - optional: insert_block if safe
   - optional: create_dimension if safe

4. Transaction lifecycle
   - validate schema
   - copy source DWG to staging
   - pre-inspect IR
   - apply patch to staged copy through native/router path
   - post-inspect IR
   - compute diff
   - validate diff and policy
   - write journal
   - return structured result

5. CAD Diff
   Implement:
   - created handles
   - deleted handles
   - modified handles
   - layer changes
   - geometry changes
   - bbox changes
   - text changes
   - type counts
   - allowed vs unexpected changes
   - unrelated changes

6. Validator gates
   - schema_valid
   - source_hash_unchanged
   - staged_copy_used
   - pre_ir_exists
   - post_ir_exists
   - diff_exists
   - expected_diff_present
   - no_unrelated_changes
   - journal_present
   - registry_operation_allowed
   - no_fake_success
   - artifacts_exist

7. Commands
   Implement:
   - `python tools\cadctl_cli.py patch dry-run --dwg <dwg> --patch <patch.json> --out <run_dir>`
   - `python tools\cadctl_cli.py patch apply-staged --dwg <dwg> --patch <patch.json> --out <run_dir>`
   - `python tools\cadctl_cli.py diff --before <pre_ir> --after <post_ir> --out <run_dir>`
   - `python tools\validator.py --run <run_dir>`

8. Native write route
   - Use existing ObjectARX/ObjectDBX/CoreConsole write operations if available.
   - If missing, implement minimal staged write native op(s).
   - Do not fake write success.
   - If native write unavailable, return PARTIAL_PASS with exact blocker.

9. Tests
   - patch policy tests
   - patch schema tests
   - staged copy hash tests
   - create_line staged apply
   - set_layer staged apply
   - diff expected changes
   - unrelated-change failure
   - validator gates
   - no original write

10. Reports
   - `reports\patch_diff_latest.json`
   - `reports\validation_latest.json`
   - `reports\journal_latest.json`

ACCEPTANCE:
- At least create_line or set_layer performs real staged mutation and diff.
- Original source hash unchanged.
- Diff detects expected change.
- Validator passes for good patch and fails for bad/unrelated patch.
- Journal exists.
- Tests pass.
- No original DWG modified.

FINAL_RESPONSE_FORMAT:
```txt
[CADOS M05 RESULT]
STATUS: PASS|PARTIAL_PASS|FAILED|BLOCKED
PATCH:
- supported_ops:
- staged_apply:
- dry_run:
DIFF:
- status:
- diff_ref:
VALIDATION:
- status:
- validation_ref:
DWG SAFETY:
- original_hash_before:
- original_hash_after:
- original_modified: no
TESTS:
- ...
BLOCKERS:
- ...
NEXT:
- CADOS_M06_VISUAL_BATCH_GOLDEN_REGRESSION
[/CADOS M05 RESULT]
```
[/PACKET]
