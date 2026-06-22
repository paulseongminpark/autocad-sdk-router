# M08B-T01 — PLAN (plan-mode artifact)

TICKET: M08B-T01 — Native OperationSpec dispatcher core
BRANCH: cados/M08B-T01 (off main 7178853 — foundation merged)
WORKTREE: D:\dev\99_tools\autocad-sdk-router_M08B-T01
DEPENDS_ON: M08A (merged to main)
DESIGN SPEC: docs/NATIVE_ARX_DBX_DESIGN.md §2.2 (native job-control plane), §4 (hard constraints)

## Baseline (verified before touching anything)

`tools/build_native_acad.ps1` in this worktree → **exit 0**, all 3 artifacts built clean:
`.dbx` 48640 B · `.crx` 260096 B · `.arx` 268288 B. Build env works (VS MSBuild + ObjectARX 2027).

## Current state

`ARIADNE_NATIVE_JOB` (`ariadneNativeJob()`, AriadneNativeJob.cpp ~2867) dispatches via a single
`if (op == "...")` chain of **39 ops**; unknown ops fall to `else { "status":"error","error":"unsupported
operation" }`. Result envelope = `{"schema":"ariadne.autocad_native_job_result.v1","engine":"native_objectarx",
"operation":<op>, ... "status":...}`.

## Goal (3 IMPLEMENT bullets)

1. Native **dispatch table** (OperationSpec).
2. **Replace/bridge** if-else **without breaking old ops**.
3. **Standard result/error envelope** + structured **OPERATION_NOT_IMPLEMENTED**.

## Design (faithful, low-risk, non-breaking)

- Add `struct AriadneOperationSpec { const char* op_id; const char* family; }` + a static
  `kAriadneNativeOperationTable[]` enumerating exactly the 39 implemented op_ids (family mirrors
  operations.v2.json; 5 native-only diagnostics carry a native family) + `findAriadneNativeOp(op)`.
  This is the **authoritative registry** of what the native module implements — the seam family tickets extend.
- Add `emitNativeError(r, errorCode, message)` → appends `"status":"error","error_code":"<code>","error":"<msg>"}`
  (additive `error_code`; preserves the human `error` string → non-breaking).
- **Table-gate the dispatcher**: right after the envelope prefix, `if (!findAriadneNativeOp(op))` →
  `OPERATION_NOT_IMPLEMENTED` + return (replaces the generic else for the 474 catalogued ops; reported even
  with no working DB). pDb-null → `NO_WORKING_DATABASE`. Final else → defensive `OPERATION_DISPATCH_MISMATCH`
  (table-says-implemented-but-no-handler drift guard; unreachable in normal flow).
- **The 39 handler bodies are NOT touched** (byte-identical) → the existing ops cannot regress.

## Hard constraints honored (design §4)

No `acedCommand`/`acedCmd` introduced. No public sealed-virtual overrides touched. Pure additive C++
(table + helper + control-flow gate). x64/v143. No original DWG write. No secrets.

## CHANGE_ONLY: src/ tests/unit/ docs/ reports/

- `src/Ariadne.AcadNative/AriadneNativeJob.cpp` — table + helpers + gate (additive).
- `tests/unit/test_m08b_dispatcher_table.py` — source-level **table↔handler parity** drift guard +
  envelope/error-code contract + OPERATION_NOT_IMPLEMENTED present + no `acedCommand(` bareword.
- `docs/M08B_NATIVE_DISPATCHER.md` — the dispatcher-core contract.
- `reports/tickets/`, `reports/` artifacts.

## Validate

1. `tools/build_native_acad.ps1` → exit 0, 3 artifacts (compile proof — the real native gate).
2. `pytest tests/unit -q` → all pass incl. new table-parity test; 18 frozen coverage + M08A tests unaffected.
3. Runtime smoke (if accoreconsole runner available): a known op still returns status ok; a catalogued op
   returns `error_code=OPERATION_NOT_IMPLEMENTED`. If headless runner not available here, record as deferred
   with the source+build proof standing.
4. No original DWG changed; no secrets; no fake PASS.

## Outputs

reports/tickets/M08B-T01.{md,json} · handoff/tickets/M08B-T01.zip · packets/tickets/M08B-T01.md · branch +
PR (remote available) → base main.
