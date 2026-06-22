# M08C_PLAN — native db / object / symbol-table READ handlers

Family **C** (READ): database metadata / object lifecycle / symbol-table reads, in
`src/Ariadne.AcadNative/families/m08c_handlers.inc` (the only source file edited).
Branch `cados/M08C` off `main`. Contract: `docs/M08_FAMILY_HANDLER_CONTRACT.md`.
API per op cited from `research/native_arx/acdb-core.md` (= ObjectARX 2027 Reference Guide).

The READ family is **read-only**: handlers operate on the router-staged working db
(`ctx.pDb`); no `save`/`saveAs`/`_QSAVE`, no original-DWG mutation. Result envelope: the
dispatcher pre-seeds `r` with `{"schema":...,"engine":"native_objectarx","operation":"<op>",`;
each handler appends `"result":{...},"status":"ok"}` and returns true, or calls
`emitNativeError(r,"CODE","msg")`. Strings go through `njsonStr` (UTF-8, lossless).

## Catalog grounding (config/operations.v2.json `operations[]`)

All 25 ops are `status: catalogued` today (no router handler). The catalog
`write_level.default_write_mode` is the decisive read/write signal used below:
`read` = candidate for this family; `write_copy` / `live_edit` = write lane (deferred).

## A. WILL IMPLEMENT — 11 read handlers

| op_id | ObjectARX API (acdb-core.md) | result JSON | host |
|---|---|---|---|
| `infra.hostapp.get_services` | `acdbHostApplicationServices()` (global, inline) — dbapserv.h:627 | `{services_present:bool, product:str, working_db_present:bool}` | both |
| `inspect.database.summaryinfo` | `acdbGetSummaryInfo(AcDbDatabase*, AcDbDatabaseSummaryInfo*&)` (summinfo.h:189) + `getTitle/getSubject/getAuthor/getKeywords/getComments/getLastSavedBy/getRevisionNumber/getHyperlinkBase(AcString&)` + `numCustomInfo()`/`getCustomSummaryInfo(int,AcString&,AcString&)` | `{title,subject,author,keywords,comments,last_saved_by,revision_number,hyperlink_base, custom_count:int, custom:[{key,value}]}` | both |
| `inspect.database.sysvar` | **READ-only** via typed `AcDbDatabase` header accessors (dbmain.h): `lunits()` (Int16), `insunits()` (`AcDb::UnitsValue`), `measurement()` (`AcDb::MeasurementValue`), `getFingerprintGuid(AcString&)`; plus, when a `name` arg is given AND host-resident, `acedGetVar(const ACHAR*, resbuf*)` (acedads.h:186) serialized via `resbufItemJson`. **No `setSysVar`.** | `{lunits:int, insunits:int, measurement:int, fingerprint_guid:str [, name:str, value:{resbuf-item}|null]}` | both (named-var read: host) |
| `inspect.object.open` | `resolveHandle` → `acdbOpenObject(AcDbObject*&, id, kForRead)` → `serializeObjectCommon` → `close()` | `{handle, found:bool, opened:bool, errorstatus:int, object:{handle,class,owner}\|null}` | both |
| `inspect.object.id` | `resolveHandle` → object resident? `objectId()` non-null; report persistent handle (the printable form of the id) | `{handle, resident:bool, object_id_null:bool}` | both |
| `inspect.object.handle` | `resolveHandle` → `acdbOpenObject(kForRead)` → `getAcDbHandle(AcDbHandle&)` round-trip via `handleOf` | `{handle, found:bool, handle_roundtrip:str, matches:bool}` | both |
| `inspect.object.ext_dict` | `resolveHandle` → `acdbOpenObject(kForRead)` → `extensionDictionary()` | `{handle, found:bool, has_extension_dictionary:bool, extension_dictionary_handle:str\|null}` | both |
| `inspect.symboltable.block` | `getBlockTable(AcDbBlockTable*&, kForRead)` + `AcDbSymbolTable` iterator (reuse `symbolTableRecordsJson(blockTableId())`). Optional `name` arg → `getAt(name,id,false)` to resolve. | `{count:int, records:[{handle,name}] [, lookup:{name,found:bool,handle:str\|null}]}` | both |
| `inspect.symboltable.layers` | `getSymbolTable(AcDbLayerTable*&,...)` + `getAt(const ACHAR*, AcDbObjectId&, bool)` (reuse `layersRichJson`). Optional `name` arg → resolve via `AcDbLayerTable::getAt`. | `{count:int, records:[{handle,name,color_index,frozen,off,locked,plottable,is_xref_dependent}] [, lookup:{name,found,handle}]}` | both |
| `transform.database.wblock` | `AcDbDatabase::wblock(AcDbDatabase*& pOut)` — clones ENTIRE db to a NEW in-memory db; **probe only**: count model-space entities in the clone, then `delete pOut`. **Never saveAs.** Original byte-identical. Catalog `default_write_mode=read`. | `{wblock_ok:bool, errorstatus:int, cloned_modelspace_entities:int, output_saved:false}` | hostless_dbx (both) |
| `write.object.cancel` | `resolveHandle` → `acdbOpenObject(kForRead)` → `cancel()` (on a read-open, discards nothing) → report. No persistence. Catalog `default_write_mode=read`. | `{handle, found:bool, cancelled:bool, errorstatus:int}` | both |

Reused in-TU primitives: `njsonStr`, `serializeObjectCommon`, `handleOf`, `handleOfId`,
`resolveHandle`, `symbolTableRecordsJson`, `layersRichJson`, `resbufItemJson`,
`AriadneReadTransaction`, `jsonFindString`, `emitNativeError`. New SDK calls introduced by
this family: `acdbGetSummaryInfo` + summary getters, `acedGetVar`, `AcDbDatabase::lunits/insunits/measurement/getFingerprintGuid`, `AcDbDatabase::wblock`, `AcDbObject::cancel`,
`AcDbObject::extensionDictionary`, `AcDbBlockTable::getAt`, `AcDbLayerTable::getAt`.
`summinfo.h` will be added to the `#include` block of `AriadneNativeJob.cpp`? — **No**: the
contract forbids editing that file. `summinfo.h` is pulled in transitively by `dbmain.h`
(AcDbDatabase API); if the build proves it is not, I fold the summaryinfo read to the typed
DB getters only and record the rest as catalogued-remaining (no fake). Verified at the build gate.

## B. DEFER — 14 catalogued-remaining (exact reason)

Write/host-mutation ops — NOT the READ family (would violate "no original DWG write" or
mutate host/db state). Left OUT of `m08cHasOp` (stay `OPERATION_NOT_IMPLEMENTED`).

| op_id | catalog wmode / tier | reason deferred |
|---|---|---|
| `infra.hostapp.set_working_db` | read / objectdbx_capable | `setWorkingDatabase` mutates global host working-db pointer — side effect on host state, not a read. Host-setup lane. |
| `inspect.database.read_dwg` | read / objectdbx_capable | side-db constructor op: needs a fresh `AcDbDatabase(buildDefaultDrawing=false, noDocument=true)` + `readDwgFile`; running on the live working `ctx.pDb` clobbers the staged graph. DBX hostless-side-db lane. |
| `inspect.database.read_dwg_handle` | read / objectdbx_capable | same as read_dwg, from an `AcDwgFileHandle` (ref-marked "internal use"). DBX side-db lane. |
| `inspect.database.dxf_in` | read / objectdbx_capable | side-db constructor op: ref MANDATES a fresh never-reused db; cannot run on the working db. DBX side-db lane. |
| `inspect.database.flush_input` | read / native_arx_only | `closeInput` — ref: "AutoCAD internal use; undesirable results in ObjectARX"; host-only. Unsafe on the working db. |
| `write.object.upgrade_open` | read / objectdbx_capable | `upgradeOpen()` is a write-INTENT primitive (kForRead→kForWrite); belongs to the staged-write lane, not a read. |
| `transform.database.dxf_out` | write_copy / objectdbx_capable | writes a `.dxf` file — export/write lane (M08 staged-write/export). |
| `transform.database.save_as` | write_copy / objectdbx_capable | writes a `.dwg` (the DWG-write primitive) — write lane; barred for original. |
| `transform.database.save_as_simple` | write_copy / objectdbx_capable | `saveAs` convenience overload — write lane. |
| `write.object.close` | write_copy / objectdbx_capable | `close()` is the commit point for open/close edits — write lane. |
| `write.object.downgrade_open` | write_copy / objectdbx_capable | `downgradeOpen()` commits changes + fires modified — write lane. |
| `transform.database.wblock_clone` | live_edit / native_arx_only | `wblockCloneObjects` clones INTO an owner (db mutation) — write/clone lane. |
| `write.object.create_ext_dict` | write_copy / objectdbx_capable | `createExtensionDictionary()` mutates the object — write lane. |
| `write.regapp.register` | write_copy / objectdbx_capable | `AcDbRegAppTable::add`/`acdbRegApp` registers an APPID — write lane. |

## Correction recorded (no-fake honesty)

`research/native_arx/acdb-core.md` row `inspect.database.sysvar` cites
`AcDbDatabase::getSysVar(...)` / `getLUNITS` and marks the signature **unverified**. Header
scan of ObjectARX 2027 `dbmain.h` finds **`getSysVar` = 0 occurrences** and no
`getLUNITS`/`getINSUNITS`. The real 2027 read surface is the typed accessors
`lunits()`/`insunits()`/`measurement()`/`getFingerprintGuid(AcString&)` plus the global
`acedGetVar`. `inspect.database.sysvar` is therefore implemented as a curated **read** over
those; the catalog's `write_copy` (the `setSysVar` path) is NOT implemented. This is noted in
the ticket report.

## Tests (tests/unit/test_m08c_handlers.py, source-contract, stdlib only)

1. `m08cHasOp` returns true for exactly the 11 implemented op-ids and false for the 14 deferred + a bogus id.
2. `m08cDispatch` has an `op == "<id>"` branch for each of the 11.
3. No `saveAs` / `\bsave\b` / `_QSAVE` / `writeDwgFile` token in the `.inc` (read-only proof).
4. Every string emission uses `njsonStr` (no `wideToAscii(` lossy funnel; no bare `"\""<<` raw name).
5. `summinfo`/`wblock` probe never calls `pOut->saveAs` (token check); wblock output deleted.
6. Whole `tests/unit` suite passes (no regression to the seam/dispatcher/serializer tests).

## Gate

`powershell -File tools/build_native_acad.ps1` exit 0 (compiles + links .dbx/.crx/.arx with
the real ObjectARX 2027 SDK). If a chosen API fails to compile, fix against the SDK header or
drop that op to catalogued-remaining with the exact compiler error — never leave broken or fake.
