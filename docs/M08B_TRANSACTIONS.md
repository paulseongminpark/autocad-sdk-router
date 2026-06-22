# M08B-T03 — Transaction / Document-Lock / Handle-Resolver Wrappers

Safe scoped DB-access infra the M08 family/write tickets build on
(`src/Ariadne.AcadNative/AriadneNativeJob.cpp`, `#include "dbtrans.h"`).

- **`AriadneReadTransaction(AcDbDatabase*)`** — RAII over `transactionManager()->startTransaction()`; ends on
  scope exit (a read rolls back nothing). `active()`/`txn()` accessors.
- **`AriadneStagedWriteTransaction(AcDbDatabase*)`** — RAII; `commit()` (→ `endTransaction()`) keeps the staged
  mutation. Any **uncommitted** scope exit (early return / failure / thrown) triggers the dtor's
  `abortTransaction()` → **rollback** ("failure rolls back"). Operates on the router-staged copy only.
- **`AriadneDocumentWriteLock`** (pre-existing) — the canonical document-lock wrapper; kept as-is.
- **`resolveHandle(AcDbDatabase*, const std::string& hex, AcDbObjectId&)`** — hex-handle → `AcDbObjectId`
  (inverse of `handleOf()`); reusable factoring of the inline `AcDbHandle`+`getAcDbObjectId` pattern.

## Safety contracts (CI-enforced by `test_m08b_transactions.py`)

- **No original write**: the wrappers never call `save()`/`saveAs()` — verified source-side.
- **Failure rolls back**: the staged-write dtor `abortTransaction()`s guarded by `!mCommitted` — verified
  source-side; RAII makes it true by construction.

## Scope honesty

These are the reusable primitives for M08G (write/patch) + the read families: compile-verified (the native build
links them against the ObjectARX `AcTransactionManager` API) + source-contract-tested here, runtime-exercised when
G uses them. The delicate live-pump inline resolver is intentionally left untouched (line-shifted, .arx-only,
pump-tested) — factoring it carries risk with no T03 benefit.

## Build / reproduce

```
powershell -File tools/build_native_acad.ps1            # exit 0
python -m pytest tests/unit/test_m08b_transactions.py -q
```
