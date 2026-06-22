# M08 Family Handler Contract (the `.inc` seam)

How a C–F READ-family teammate adds native operations **without touching any shared file** — so parallel
worktrees merge cleanly.

## You own exactly one file

`src/Ariadne.AcadNative/families/m08X_handlers.inc` (X ∈ {c,d,e,f}). It is `#include`d into
`AriadneNativeJob.cpp`, so it compiles into `.crx` + `.arx` as part of that translation unit and sees **every
in-TU helper**. You do NOT edit `AriadneNativeJob.cpp`, the `.vcxproj`, or any other family's `.inc`.

## The two functions you fill

```cpp
static bool m08xHasOp(const std::string& op);                 // true for every op id you implement
static bool m08xDispatch(const std::string& op,               // if op is yours: append result to r, return true
                         const AriadneJobCtx& ctx,             // else: return false
                         std::ostringstream& r);
```

`AriadneJobCtx { const std::string& job; AcDbDatabase* pDb; const std::string& hostMode; }`.

## Result envelope (append to `r`)

`r` already carries the prefix `{"schema":...,"engine":"native_objectarx","operation":"<op>",`. Your handler
appends the rest and closes the object:

- success: `r << "\"result\":{ ... },\"status\":\"ok\"}";`
- error:   `emitNativeError(r, "YOUR_CODE", "message");`  (appends status+error_code+error, closes `}`)

Return `true` once you've written the result. The dispatcher writes `r` to the out file.

## In-TU primitives you MUST reuse (do not re-roll)

- **UTF-8 JSON**: `njsonStr(const ACHAR*| std::wstring | std::string)` → quoted, escaped, UTF-8 (never lossy `?`).
  `jsonEscape(std::string)` for raw escaping.
- **Generic serializers**: `serializeObjectCommon(AcDbObject*)` (handle/class/owner),
  `serializeEntityCommon(AcDbEntity*)` (+layer/color_index/linetype/visible). resbuf/xdata: `resbufItemsJson`,
  `xdataBlocksJson`.
- **Transactions**: `AriadneReadTransaction rt(pDb);` for scoped reads; `AriadneStagedWriteTransaction` (commit()
  or auto-rollback) — but READ family is read-only.
- **Handles**: `resolveHandle(pDb, hex, AcDbObjectId&)` (hex→id), `handleOf(AcDbObject*)`, `handleOfId(id)`.
- **Args**: `jsonFindString(job, "key", out)`, `jsonFindNumber(job, "key", dbl)`.

## Hard constraints (NON-NEGOTIABLE — from NATIVE_ARX_DBX_DESIGN §4)

- **No original DWG write.** READ family is read-only; never `save`/`saveAs`/`_QSAVE`. Use ReadTransaction or
  plain `acdbOpenObject(..., AcDb::kForRead)`.
- **No `acedCommand`/`acedCmd`** (compile-disabled in 2027) — use `acedCommandS`/`acedCommandC` only if truly needed.
- Override only protected `subXxx` virtuals if you touch entity rendering (you shouldn't for read).
- **UTF-8 fidelity**: all strings through `njsonStr` (preserve non-ASCII, e.g. Korean layer names). No lossy `?`.
- **No fake PASS.** An op you cannot implement → leave it OUT of HasOp (it stays OPERATION_NOT_IMPLEMENTED) and
  record it in your report as catalogued-remaining with the exact blocker. Never return a fabricated result.

## Workflow (per the ticket protocol)

1. Read the design (`docs/NATIVE_ARX_DBX_DESIGN.md`) + your family research slice
   (`research/native_arx/<slice>.md`) + your op list (handed in your brief, from `full_sdk_implementation_map.json`).
2. Write `reports/tickets/<TICKET>_PLAN.md` (plan first): exact ops, the ObjectARX API per op (cite the slice),
   the result shape, tests.
3. Implement in your `.inc` (auto-accept within your file only).
4. **Build**: `powershell -File tools/build_native_acad.ps1` → must be exit 0.
5. **Test**: add `tests/unit/test_<family>_*.py` (source-contract: HasOp lists your ops; Dispatch handles them;
   no `save`/`saveAs`; UTF-8 via njsonStr). `python -m pytest tests/unit -q` → all pass (no regression).
6. Commit on your branch; push; open PR (base = the seam/main as your brief states). Write
   `reports/tickets/<TICKET>.{md,json}`, `packets/tickets/<TICKET>.md`, `handoff/tickets/<TICKET>.zip`.
7. Report: implemented ops, hard-blocked ops (with evidence), catalogued-remaining, tests, NEXT.

## Why this shape

Disjoint files = the "WRITE must not overlap" rule satisfied → the merge orchestrator merges your PR with zero
conflicts. The gate (`familyHasOp`) admits your ops; unknown ops still return structured
`OPERATION_NOT_IMPLEMENTED`; a HasOp/Dispatch mismatch surfaces `OPERATION_DISPATCH_MISMATCH` (never silent).
