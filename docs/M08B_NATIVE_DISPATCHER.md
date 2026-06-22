# M08B-T01 — Native OperationSpec Dispatcher Core

## What changed

`ARIADNE_NATIVE_JOB` (`src/Ariadne.AcadNative/AriadneNativeJob.cpp`) previously dispatched via a single
`if (op == "...")` chain of 39 ops, with unknown ops falling to a generic
`else { "status":"error","error":"unsupported operation" }`. M08B-T01 makes the dispatch **table-gated**:

- **`kAriadneNativeOperationTable[]`** — a static `{op_id, family}` table that is the **authoritative
  registry** of the operations the native module implements (39 today: 34 mirror `operations.v2.json`
  families; 5 are native-only diagnostics — selection-monitor ×3, `inspect.probe.property_count`,
  `deep_native` ×2). `findAriadneNativeOp(op)` looks an op up.
- **Table-gated dispatch**: the `ariadneNativeJob()` dispatcher consults the table *before* handling. An
  op_id absent from the table returns a **structured `OPERATION_NOT_IMPLEMENTED`** and stops — this is the
  honest contract for the 474 catalogued ops the M08 family tickets (C–O) will build. (Reported even with no
  working database, since "not implemented here" is a contract fact, not a DB error.)
- **Standard error envelope** (additive, non-breaking): `emitNativeError(r, code, message)` appends a
  machine-stable `error_code` alongside the legacy human `error` string. Dispatcher-level errors now carry
  codes: `OPERATION_NOT_IMPLEMENTED`, `NO_WORKING_DATABASE`, and `OPERATION_DISPATCH_MISMATCH` (the final
  `else`, now a defensive drift guard — unreachable in normal flow).
- **The 39 handler bodies are byte-identical** — the existing ops cannot regress. The table *gates* and the
  bridged if-chain *handles*; family tickets extend by adding a `{op_id, family}` row + a handler branch.

The success result envelope is unchanged: `{"schema":"ariadne.autocad_native_job_result.v1",
"engine":"native_objectarx","operation":<op>, "result":{...}, "status":"ok"}`.

## Invariant (CI-enforced)

`tests/unit/test_m08b_dispatcher_table.py` asserts **table ↔ handler parity**: the table op_id set equals the
dispatcher's `op == "..."` branch set. Drift in either direction (a family ticket adds a handler but forgets
the table, or registers an op_id it never handles) fails CI — preventing a catalogued op from silently
reading as "implemented" or vice-versa. The test is source-level (no AutoCAD needed); the native build proves
it compiles + links.

## Design-spec adherence (docs/NATIVE_ARX_DBX_DESIGN.md)

- §2.2 native job-control plane: dispatch by op_id, structured JSON result — preserved + formalized.
- §4 hard constraints: no `acedCommand`/`acedCmd` introduced; no sealed-virtual overrides touched; pure
  additive C++; x64/v143; ships into accoreconsole (`.crx`)/attended AutoCAD (`.arx`); no original DWG write.

## Build

`tools/build_native_acad.ps1` → `.dbx` (persistent core, dispatcher not included — unchanged) + `.crx`
(headless command shell) + `.arx` (attended shell). The dispatcher change lands in `.crx` + `.arx`.

## Reproduce

```
powershell -File tools/build_native_acad.ps1          # exit 0, 3 artifacts
python -m pytest tests/unit/test_m08b_dispatcher_table.py -q   # table<->handler parity
```
