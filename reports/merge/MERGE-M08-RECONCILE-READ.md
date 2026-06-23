# MERGE-M08-RECONCILE-READ

- **role**: merge_executor (single-writer)
- **date**: 2026-06-23
- **status**: PASS
- **main commit**: `d11c6ee` (merge of PR #12)

## Scope

Registry reconciliation for the M08 C/D/E READ wave. The handlers were already
on `main` (MERGE-M08-READ, `1feeb1f`), but the wave's CHANGE_ONLY was the `.inc`
files only — so the 84 native read ops stayed `catalogued` in
`config/operations.v2.json` and `closure_gate` read a stale 474. This merge
brings the registry in line with the code that actually dispatches.

## Result

| metric | before | after |
|---|---|---|
| implemented | 41 | **125** |
| catalogued | 474 | **390** |
| blocked | 2 | 2 |

- 84 flips (m08c 11, m08d 69, m08e 4) — **drift 0, conflicts 0**.
- `totals.by_status` + `coverage` re-synced; reports regenerated.
- New deterministic tool `tools/reconcile_native_registry.py` (reusable for the
  remaining waves).

## Honesty

- Evidence per op = handler (`.inc:dispatch`) + unit test + native build + merge record.
- Runtime `ARIADNE_NATIVE_JOB` smoke = **deferred_attended(MERGE-M08-READ)**, recorded not claimed.
- `closure_gate` stays **False** (390 catalogued remain); **M09 blocked**.
- No C++ changed → native artifacts unaffected. Post-merge: **324 passed**.

## Next

M08G/H WRITE wave → M08I/J VISLIVE → M08K/L/M/N NATIVE → M08O FALLBACK.
No M09 until catalogued/stub/unknown/deferred = 0.
