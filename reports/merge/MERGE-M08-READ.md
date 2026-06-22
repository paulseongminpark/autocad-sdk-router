# MERGE-M08-READ — merge record

- **Role:** merge_executor (single-writer to main)
- **Date:** 2026-06-22
- **Scope:** M08C/M08D/M08E READ families. (M08F = 0 catalogued ops — already implemented; nothing to merge.)
- **main after merge:** `a11f982`

## Merged (disjoint family .inc — conflict-free)

- **PR #8** `cados/M08E` (m08e) — blocks / dictionaries / xdata reads. 4 ops.
- **PR #9** `cados/M08C-iso` (m08c) — db metadata / object lifecycle / symbol-table reads. 11 ops.
- **PR #11** `cados/M08D-iso` (m08d) — entities / AcGe geometry / AcBr BRep topology. 69 ops. (Superseded PR #10,
  which m08d closed after re-homing to an isolated worktree.)

**84 native read handlers** added to main (m08c 11 + m08d 69 + m08e 4), each in its own
`families/m08X_handlers.inc` via the M08C0 seam. Admitted through `familyHasOp`; NOT added to
`kAriadneNativeOperationTable` → the M08B dispatcher-parity invariant is untouched.

## Honest deferrals (left OUT of HasOp → stay OPERATION_NOT_IMPLEMENTED; NO fakes)

- m08c: 14 write-lane/side-db ops (save_as*, dxf_out, wblock_clone, write.object.*, create_ext_dict, regapp.register,
  set_working_db, read_dwg*, dxf_in, flush_input) → M08G write lane / a DBX hostless-side-db ticket.
- m08e: 7 write/create ops (write.block.append_entity, write.dictionary.set, write.entity.set_xdata,
  transform.database.deep_clone/insert_block, acdb.database.create, infra.hostapp.provide_services) → M08G.
- m08d: 4 (ui.subentity.highlight = attended/graphics; inspect.subentity.markers_at_path + path_at_marker =
  editor/GS-marker pick, none headless; inspect.subentity.color = AcDbSubentColor header unverified in this SDK).
- 0 hard-blocked.

## Pre-merge integration verification + post-merge gate

- **Consolidated build BEFORE merge** (integration worktree `integ/m08-cde`, all 3 families octopus-merged):
  `build_native_acad.ps1` exit 0; `pytest tests/unit` = 311 passed. This proved the 3-way combination links in the
  shared translation unit with **no cross-family static-symbol collision** (each family strictly namespaces its
  statics: m08c*/m08d*/m08e*).
- **Post-merge gate on main** (`a11f982`): build exit 0 (`.dbx` 48128 / `.crx` 343552 / `.arx` 350720, ObjectARX
  2027, canonical relink); `pytest tests/unit` = **324 passed, 0 failed** (all 3 family tests + seam + dispatcher
  parity green).

## REJECT_IF audit (all clear)

- original DWG changed: NO (all families read-only; every `acdbOpenObject` is `kForRead`; no save/saveAs/_QSAVE).
- secrets staged: NO · raw command agent-exposed: NO · existing frozen ops regress: NO · ticket reports missing:
  NO (C/D/E reports+packets+handoff on their branches) · tests fail: NO · disjoint .inc: YES (verified per-PR file
  lists + clean octopus merge).

## Key finding (research/design correction — m08d)

The brep-topology slice + `NATIVE_ARX_DBX_DESIGN.md` §3 wrongly named `AcDrawBridge.lib` as the AcBr import lib
(dumpbin: 0 AcBr symbols). Real = `utils/brep/lib-x64/acbr26.lib` + `acgex26.lib` + `acgeoment.lib`. m08d linked
via `#pragma comment(lib, <abs path>)` inside the `.inc` (no vcxproj edit). → **doc-only follow-up** to fix the
slice + §3, and parameterize the absolute lib path (machine-specific today).

## Process note (lesson)

`teammateMode: in-process` → teammates share the shell cwd + the primary working tree; the Agent `isolation:worktree`
held for only one of three. m08c+m08d collided in the primary tree (TOCTOU stub/impl flips). Recovered: each family
→ its own worktree off main + a fresh `-iso` branch + **absolute paths only**. No work lost. Lesson: in-process
parallel teammates need own-worktree + absolute paths from the start (or serialize).

[MERGE-M08-READ RESULT]
STATUS: PASS
MERGED: PR #8 (M08E), PR #9 (M08C), PR #11 (M08D)
REJECTED: PR #10 (superseded by #11)
TESTS: build exit 0; pytest tests/unit = 324 passed; pre-merge integ = 311 passed
MAIN_COMMIT: a11f982
NEXT: registry reconciliation (mark the 84 implemented read ops in config/operations.v2.json with evidence +
regenerate closure_gate); then WRITE (M08G/H), VISLIVE (M08I/J), NATIVE (M08K/L/M/N), FALLBACK (M08O) waves.
No M09 until catalogued/stub/unknown/deferred = 0.
[/MERGE-M08-READ RESULT]
