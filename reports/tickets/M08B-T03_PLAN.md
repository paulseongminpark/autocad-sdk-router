# M08B-T03 — PLAN

TICKET: M08B-T03 — Transaction/document lock wrappers
BRANCH: cados/M08B-T03 (stacked on cados/M08B-T02 — same file, conflict-free)

## Current state

- `AriadneDocumentWriteLock` (RAII doc write-lock) — present → the **document lock wrapper** deliverable.
- `handleOf`/`handleOfId` (object/id → hex) — present. Handle **resolution** (hex → id) exists only **inline** in
  the live pump (`AcDbHandle h(hex); pDb->getAcDbObjectId(id,false,h)`) — not factored.
- **No transaction-manager usage anywhere** → the transaction wrappers are net-new.

## Deliverables (additive, RAII, low-risk)

1. **Read transaction wrapper** `AriadneReadTransaction` — RAII over `pDb->transactionManager()->startTransaction()`;
   `endTransaction()` on scope exit (read: nothing to roll back).
2. **Staged write transaction wrapper** `AriadneStagedWriteTransaction` — RAII; `commit()` keeps the staged
   mutation; if `commit()` is NOT called before scope exit (early return / failure / exception), the dtor
   **abortTransaction() → rollback**. Operates on the router-staged copy only; never the original.
3. **Document lock wrapper** — `AriadneDocumentWriteLock` (present) is the canonical wrapper; kept as-is.
4. **Handle resolver** `resolveHandle(AcDbDatabase*, const std::string& hex, AcDbObjectId&)` — reusable factoring
   of the inline hex→id pattern (inverse of `handleOf`).

Add `#include "dbtrans.h"` (AcTransactionManager/AcTransaction).

## Honesty note

The transaction wrappers + resolver are the reusable safe-access primitives the C–F/G handlers will call. They are
compile-verified (native build links them) + source-contract-tested here; the "failure rolls back" property is
RAII-by-construction (dtor aborts any uncommitted transaction). Runtime exercise lands when G (write ops) uses
them. I do NOT refactor the delicate live-pump inline resolver (line-shifted, .arx-only, pump-tested) — no T03
benefit, real risk.

## CHANGE_ONLY: src/ tests/unit/ docs/

- `src/Ariadne.AcadNative/AriadneNativeJob.cpp` — `#include "dbtrans.h"` + the 3 wrappers/helper before
  `AriadneDocumentWriteLock`.
- `tests/unit/test_m08b_transactions.py` — source contract: wrappers exist; staged-write dtor aborts when
  uncommitted (rollback); wrappers never call `saveAs`/`save` (no original write); resolver uses
  `AcDbHandle`+`getAcDbObjectId`.
- `docs/M08B_TRANSACTIONS.md`.

## Validate

- `build_native_acad.ps1` → exit 0.
- `pytest tests/unit` → all pass (incl. new transaction contract test); no regression.
- no-original-write: source-assert no save/saveAs in the wrappers. failure-rolls-back: source-assert dtor abort.
