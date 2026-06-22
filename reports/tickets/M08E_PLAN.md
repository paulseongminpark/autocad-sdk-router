# M08E_PLAN — native READ family E (blocks / dictionaries-xdata-xrecords)

**Branch:** `cados/M08E` (worktree off `main`).
**File owned (only source edit):** `src/Ariadne.AcadNative/families/m08e_handlers.inc`.
**Family:** M08E READ family = read-only. Implement the READ/inspect ops as real handlers;
leave the WRITE/create/clone ops OUT of `m08eHasOp` and record them as catalogued-remaining
(they mutate or create → belong to the M08G write lane, not a read-only family).

## Contract recap (docs/M08_FAMILY_HANDLER_CONTRACT.md)

- Fill `m08eHasOp(const std::string& op)` (true for every op id this family implements) and
  `m08eDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)`
  (handle → append `"result":{...},"status":"ok"`, return true; else return false).
- `r` already carries the prefix `{"schema":...,"engine":"native_objectarx","operation":"<op>",`.
  Success: append `"result":{...},"status":"ok"}`. Error: `emitNativeError(r, "CODE", "msg")`.
- Reuse in-TU primitives (verified present in `AriadneNativeJob.cpp`): `njsonStr` (UTF-8 JSON
  string), `jsonEscape`, `handleOf`/`handleOfId`, `resolveHandle`, `serializeEntityCommon`,
  `resbufItemsJson`, `xdataBlocksJson`, `xrecordJson`, `dictionaryEntriesJson`, `jsonFindString`,
  `jsonFindNumber`, `AriadneReadTransaction`, `RichGraphCounters`.
- HARD: no original DWG write; no `acedCommand`/`acedCmd`; all strings through `njsonStr`
  (preserve Korean layer/block names); no fake PASS.

## Gate / parity note (why this is conflict-free and test-safe)

The four family ops are admitted via `familyHasOp(op)` (the dispatcher gate
`findAriadneNativeOp(op)==nullptr && !familyHasOp(op)`). They are **NOT** added to
`kAriadneNativeOperationTable`. `tests/unit/test_m08b_dispatcher_table.py::test_table_handler_parity`
scans `op == "..."` strings **only inside the `ariadneNativeJob()` function region**
(`static void ariadneNativeJob()` … `static bool readCommandArg`); the `m08e_handlers.inc`
content is `#include`d *before* that function (line 3121), so the `op == "..."` comparisons in
`m08eDispatch` are outside the scanned region and do not perturb the table↔handler parity
invariant. Confirmed by reading the test.

---

## IMPLEMENTED ops (4 — real handlers, read-only)

All run host-less in accoreconsole on the working/staged DB (`ctx.pDb`); all are
`objectdbx_capable`, `dwg_persisted=false` per `config/autocad_native_arx_operation_catalog.json`.

### 1. `inspect.entity.get_xdata` — the clean win
- **API:** `AcDbObject::xData(const ACHAR* regappName=nullptr) const`
  (`C:\ObjectARX 2027\inc\dbObject.h:265`, `resbuf*`; caller frees via `acutRelRb`).
  Optional regapp filter. Object opened by handle via `resolveHandle` + `acdbOpenObject(kForRead)`.
  acdb-core.md row `inspect.entity.get_xdata`.
- **Args:** `handle` (hex, required), `regapp` (optional string → filter).
- **Result shape:**
  ```json
  "result":{"handle":"<hex>","class":"<rxclass>","regapp_filter":"<name|null>",
            "xdata_present":true,"block_count":N,"item_count":M,"xdata":[{"app":"..","items":[{"code":..,"value":..}]}]}
  ```
  Reuses `xdataBlocksJson(rb,&blockCount,&itemCount)` verbatim (same shape the M02
  `inspect.database.graph` entities[] xdata uses; covered by existing resbuf/xdata tests). When
  the object has no xdata: `xdata_present:false, block_count:0, item_count:0, xdata:[]` (still ok).
- **Errors:** `MISSING_HANDLE` (no/empty `handle` arg); `HANDLE_NOT_FOUND` (`resolveHandle` false);
  `OBJECT_OPEN_FAILED` (`acdbOpenObject` != eOk).

### 2. `inspect.dictionary.named_objects` — NOD root listing
- **API:** `AcDbDatabase::getNamedObjectsDictionary(AcDbDictionary*&, AcDb::kForRead)`
  (acdb-core.md row `inspect.dictionary.named_objects`) → `AcDbDictionary::newIterator()` →
  iterate `name()`/`objectId()`. Mirrors the proven in-TU `namedObjectDictJson` walk.
- **Args:** none.
- **Result shape:**
  ```json
  "result":{"handle":"<nod_hex>","entry_count":N,
            "entries":[{"key":"ACAD_GROUP","value_handle":"<hex>","class_name":"AcDbDictionary","is_xrecord":false}, ...]}
  ```
  Reuses `dictionaryEntriesJson(pDict, dictHandle, xrecords, xrecordFirst, counters)` to get the
  per-entry `{key,value_handle,class_name,is_xrecord}` shape; any XRECORDs directly under the NOD
  are surfaced in an `xrecords` array (same `xrecordJson` shape as M02). Read under
  `AriadneReadTransaction rt(pDb)`.
- **Errors:** `NOD_OPEN_FAILED` (getNamedObjectsDictionary != eOk).

### 3. `inspect.dictionary.get` — resolve one dictionary entry / list a sub-dictionary
- **API:** `AcDbDictionary::getAt(const ACHAR* entryName, AcDbObjectId&) const`
  (`C:\ObjectARX 2027\inc\dbdict.h:106`, `eKeyNotFound`/`eInvalidKey`); NOD root via
  `getNamedObjectsDictionary`. acdb-core.md row `inspect.dictionary.get`.
- **Args:** `key` (required) — entry to resolve in a dictionary; `dict_handle` (optional) — the
  dictionary to look in; default = the NOD. (Supports the common "get layout/group/plotsettings
  dict, then resolve a named child" path.)
- **Result shape:**
  ```json
  "result":{"dictionary_handle":"<hex>","key":"<key>","found":true,
            "value_handle":"<hex>","class_name":"<rxclass>","is_dictionary":true,
            "entries":[ ...present only when the value is itself a dictionary... ]}
  ```
  When the resolved value is an `AcDbDictionary`, its children are emitted via
  `dictionaryEntriesJson` (so "named_objects → get(ACAD_LAYOUT) → entries" yields the layout list).
  When `found:false`: `value_handle:"",class_name:"",is_dictionary:false` and no `entries`.
- **Errors:** `MISSING_KEY` (no `key`); `DICT_OPEN_FAILED` (NOD or `dict_handle` not openable as a
  dictionary); `HANDLE_NOT_FOUND` (bad `dict_handle`). A missing key is **not** an error — it is a
  valid `found:false` result (matches `getAt` returning `eKeyNotFound` as a normal lookup miss).

### 4. `inspect.block.iterate` — enumerate entities in a block-table record
- **API:** `AcDbDatabase::getBlockTable(AcDbBlockTable*&, kForRead)` → resolve the target BTR
  (model space default via `AcDbBlockTable::getAt(ACDB_MODEL_SPACE,...)`, or by `block_handle`, or
  by `block_name`) → `AcDbBlockTableRecord::newIterator(AcDbBlockTableRecordIterator*&)`
  (acdb-core.md row `inspect.block.iterate`) → per entity `getEntityId(AcDbObjectId&)`
  (`dbsymtb.h:1652`) + open `kForRead`.
- **Args:** `block_handle` (optional hex) OR `block_name` (optional) → the BTR to iterate;
  default = model space. `include_xdata` (optional bool, default false) → also attach each
  entity's `xdataBlocksJson`.
- **Result shape:**
  ```json
  "result":{"block_handle":"<btr_hex>","block_name":"<name>","entity_count":N,
            "entities":[{"handle":..,"class":..,"owner":..,"layer":..,"color_index":..,
                         "linetype":..,"visible":..,"dxf_name":".."}, ...]}
  ```
  Each entity uses `serializeEntityCommon(pEnt)` (object-common + layer/color/linetype/visible) +
  `dxf_name` (`pEnt->isA()->name()` lower-level dxf name when available). Walk under
  `AriadneReadTransaction`. Pure enumeration — no geometry decode here (geometry decode is M08D's
  lane; this is the block/owner-scoped entity list).
- **Errors:** `BLOCK_TABLE_OPEN_FAILED`; `BLOCK_NOT_FOUND` (named/handle BTR not resolvable);
  `BTR_OPEN_FAILED` / `BTR_ITER_FAILED`.

---

## DEFERRED / not-in-HasOp (catalogued-remaining — WRITE/create lane, NOT read-only)

These mutate or create state (`dwg_persisted=true` or construct a new DB/host) → excluded from a
READ family by the contract. Left OUT of `m08eHasOp` so they keep returning the honest
`OPERATION_NOT_IMPLEMENTED` until the M08G write lane builds them. No fabricated results.

| op | catalog tier / persist | why deferred |
|---|---|---|
| `write.block.append_entity` | objectdbx_capable / persist=true | appends an entity to a BTR — original-DWG mutation; write lane. |
| `write.dictionary.set` | objectdbx_capable / persist=true | adds/replaces a NOD/dict entry — mutation; write lane. |
| `write.entity.set_xdata` | objectdbx_capable / persist=true | attaches xdata (needs regapp in APPID) — mutation; write lane. |
| `transform.database.deep_clone` | native_arx_only / persist=true / ctx=host | `deepCloneObjects` is a host-only mutation mechanism; not read-only, not headless. |
| `transform.database.insert_block` | objectdbx_capable / persist=true | `AcDbDatabase::insert` creates a BTR + copies entities — mutation; write lane. |
| `acdb.database.create` | objectdbx_capable / persist=false | constructs a *new* `AcDbDatabase`; the headless job already owns/serves the working DB via `AcDbHostApplicationServices` — creating side DBs is host/runtime-infra, not a read op on `ctx.pDb`. |
| `infra.hostapp.provide_services` | objectdbx_capable / ctx=hostless | the host-application-services subclass IS the accoreconsole host bootstrap (already provided by the running `.crx` host); not an op a per-job READ handler performs. Runtime/infra lane. |

**Catalogued-remaining count for M08E:** 7 (the 4 reads above are implemented; these 7 are the
remainder of the 11-op brief, deferred with the stated blocker).

## Tests (tests/unit/test_m08e_handlers.py — source-contract, no AutoCAD needed)

1. `m08eHasOp` returns true for exactly the 4 implemented op ids and false for the 7 deferred ids
   (and for an unrelated id) — parsed from the `.inc` source (HasOp membership) so it can't drift
   silently.
2. `m08eDispatch` contains an `op ==`/branch for each implemented op, and the deferred write ops do
   **not** appear as handled branches.
3. No original-DWG-write tokens in the `.inc` (`saveAs`, `_QSAVE`, `acedCommand`, `acdbSetHostApplicationServices`,
   `appendAcDbEntity`, `setXData(`, `setFromRbChain`, `deepCloneObjects`, `->insert(`) — read-only proof.
4. Every name emission goes through `njsonStr`/`jsonEscape` (no lossy `wideToAscii(` direct into JSON
   for names) — UTF-8 fidelity.
5. The seam invariant still holds (`m08eHasOp`/`m08eDispatch` signatures match the contract regex).

The native build (`tools/build_native_acad.ps1`) separately proves the change compiles + links
(.dbx + .crx must be exit 0; .arx may relink to a versioned target if a live AutoCAD holds the lock).
