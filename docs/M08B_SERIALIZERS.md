# M08B-T02 — Generic Serializers & UTF-8 JSON Writer

## Primitives added (`src/Ariadne.AcadNative/AriadneNativeJob.cpp`)

The reusable serialization primitives the M08 family tickets (C–F) build on, so per-op handlers never
re-implement string encoding or the common object/entity field shapes:

- **`njsonStr(...)`** — the canonical **UTF-8 JSON-string writer**. Three overloads: `const ACHAR*`
  (entity/layer/class names), `const std::wstring&`, `const std::string&` (already-decoded handles). Returns a
  fully-quoted, escaped JSON string token; non-ASCII code points are preserved as **UTF-8 bytes** (e.g. the
  Korean layer `설비OPEN`), only JSON metacharacters are escaped, `nullptr → ""`. Routes through
  `acharToAscii()`→`wideToUtf8()` (lossless) — **never** the lossy `wideToAscii()` `'?'` funnel.
- **`serializeObjectCommon(AcDbObject*)`** — `handle`, `class` (RX class name), `owner` handle (no braces; caller
  wraps).
- **`serializeEntityCommon(AcDbEntity*)`** — object-common + `layer`, `color_index`, `linetype`, `visible`.

## Already-present (formalized as the generic resbuf/xdata/xrecord serializer)

`resbufItemJson` / `resbufItemsJson` / `xdataBlocksJson` cover the full DXF group-code taxonomy
(string/point/real/int16/int32/bool/binary) and are the generic resbuf/xdata/xrecord serializer. M08B-T02
routes their **string value** through `njsonStr()` (byte-identical output) so the new UTF-8 writer is exercised
under the existing resbuf/xdata tests.

## UTF-8 fidelity (the VALIDATE bar)

Every string primitive uses the lossless UTF-8 path. `test_non_ascii_fidelity.py` proves it at runtime (native
emits the Korean code points, not `'?'`); `test_m08b_serializers.py` asserts source-side that no primitive is
re-routed through `wideToAscii`. No `'?'` lossy output except the explicitly-diagnostic `wideToAscii()` (kept
only for ASCII-only diagnostic contexts).

## Scope honesty

`serializeObjectCommon`/`serializeEntityCommon` are added as the C–F primitives: compile-verified (native build
links them) + source-contract-tested here, and runtime-exercised when C–F call them. The heavily-tested inline
entity emission in `collectModelSpaceGraph` is left intact (refactoring it would risk changing tested field
names/order for no T02 benefit).
