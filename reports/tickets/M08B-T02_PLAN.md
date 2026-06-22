# M08B-T02 — PLAN

TICKET: M08B-T02 — Generic serializers and UTF-8 writer
BRANCH: cados/M08B-T02 (stacked on cados/M08B-T01 — same file, conflict-free)
DESIGN: NATIVE_ARX_DBX_DESIGN.md; M02 non-ASCII fidelity work (wideToUtf8)

## Current state (what already exists)

- `wideToUtf8()` (lossless UTF-16→UTF-8), `acharToAscii()` (repurposed to UTF-8), `jsonEscape()` — present.
- Generic resbuf/xdata serializer: `resbufItemJson` / `resbufItemsJson` / `xdataBlocksJson` — present + complete
  (string/point/real/int16/int32/bool/binary group-code ranges) + already exercised by tests.

## Deliverables (additive, low-risk)

1. **UTF-8 JSON writer primitive** `njsonStr()` (overloads: `const ACHAR*`, `const std::wstring&`,
   `const std::string&`) → a fully-quoted, escaped UTF-8 JSON string token. Always routes through
   acharToAscii()/wideToUtf8() (lossless) — never the lossy `wideToAscii()` '?' funnel.
2. **Generic `serializeObjectCommon(AcDbObject*)`** → handle/class/owner fields.
3. **Generic `serializeEntityCommon(AcDbEntity*)`** → object-common + layer/color_index/linetype/visible.
   (These are the reusable primitives the C–F per-op handlers call so they never re-roll field encoding.)
4. **Exercise** njsonStr at runtime by a **byte-identical** refactor of the resbuf string-value emission
   (`resbufItemJson`) to call njsonStr — output unchanged, but the writer is now covered by existing resbuf
   tests. (resbuf/xdata serializer = bullet 3, already generic + tested.)

## Honesty note

serializeObjectCommon/serializeEntityCommon are added as the C–F primitives; they are compile-verified + source-
contract-tested here and runtime-exercised when C–F call them. I do NOT refactor the heavily-tested inline entity
emission in collectModelSpaceGraph (would risk changing tested field names/order for no T02 benefit).

## CHANGE_ONLY: src/ tests/unit/ schemas/ docs/

- `src/Ariadne.AcadNative/AriadneNativeJob.cpp` — add helpers; refactor resbuf string path to use njsonStr.
- `tests/unit/test_m08b_serializers.py` — source contract: helpers exist; njsonStr routes through UTF-8
  (acharToAscii/wideToUtf8), not wideToAscii; resbuf string path uses njsonStr; no new lossy funnel.
- `docs/M08B_SERIALIZERS.md`.

## Validate

- `build_native_acad.ps1` → exit 0 (compile+link of the new helpers + refactor).
- `pytest tests/unit` → all pass incl. `test_non_ascii_fidelity.py` (the UTF-8/no-'?' VALIDATE) + new serializer
  contract test. No regression.
