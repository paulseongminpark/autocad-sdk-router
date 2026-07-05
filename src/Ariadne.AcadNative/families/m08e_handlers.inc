// families/m08e_handlers.inc — M08E READ family: blocks / dictionaries / xdata-xrecords reads.
//
// Owned by the M08E teammate (PR-scoped). #included into AriadneNativeJob.cpp (before the
// ariadneNativeJob() dispatcher), so it sees every in-TU helper. Contract
// (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - m08eHasOp(op): true for every op id this family implements (gate admission via familyHasOp).
//   - m08eDispatch(op, ctx, r): if op is yours, append  "result":{...},"status":"ok"  (or an
//     emitNativeError-style error) to r and return true; else return false.
//
// READ family = read-only. Implemented (real handlers, all objectdbx_capable / non-persisting):
//     inspect.entity.get_xdata       -- reuse AcDbObject::xData + xdataBlocksJson
//     inspect.dictionary.named_objects -- NOD root via getNamedObjectsDictionary + dictionaryEntriesJson
//     inspect.dictionary.get         -- AcDbDictionary::getAt (one entry; sub-dict listing)
//     inspect.block.iterate          -- BTR entity enumeration (model space / by handle / by name)
// The WRITE/create/clone ops in the M08E brief (write.block.append_entity, write.dictionary.set,
// write.entity.set_xdata, transform.database.deep_clone, transform.database.insert_block,
// acdb.database.create, infra.hostapp.provide_services) MUTATE or CREATE state -> they are NOT
// part of a read-only family, but ARE claimed by m08eHasOp/m08eDispatch below (this header
// comment + reports/tickets/M08E.md predate that and are stale on this point -- the ops were
// wired as always-rollback smoke PROBES, not left OPERATION_NOT_IMPLEMENTED). Each wraps its
// mutation in AriadneStagedWriteTransaction and never calls .commit(), so nothing survives the
// call -- except write.block.append_entity (p2-blockapp wave), which was graduated to a REAL,
// persisting primitive: it drops the transaction wrapper (matching every other real write
// handler in the codebase -- write.entity.line/circle/arc/text/... in m08g/m08h/
// AriadneNativeJob.cpp) so its appendAcDbEntity() survives to the staged-copy DWG the router job
// already operates on. It still never touches the ORIGINAL file; that invariant is enforced by
// the router/registry write_mode policy layer, same as every other write op. The remaining 6 ops
// stay probe-only (rolled back, no fabricated results).
//
// Reuses in-TU primitives only: njsonStr / jsonEscape, handleOf / handleOfId, resolveHandle,
// serializeObjectCommon / serializeEntityCommon, dictionaryEntriesJson / xrecordJson,
// xdataBlocksJson, jsonFindString / jsonFindNumber, AriadneReadTransaction, RichGraphCounters.
// NO original DWG writes (no save/saveAs/_QSAVE, no acedCommand/acedCmd, no append/set/clone).
#include "dbidmap.h"      // AcDbIdMapping / AcDbIdPair for staged deep-clone proof

// ---- op id constants (single source for HasOp + Dispatch; avoids string drift) -------------
static const char* const kM08eOpEntityXdata   = "inspect.entity.get_xdata";
static const char* const kM08eOpDictNamed      = "inspect.dictionary.named_objects";
static const char* const kM08eOpDictGet        = "inspect.dictionary.get";
static const char* const kM08eOpBlockIterate   = "inspect.block.iterate";
static const char* const kM08eOpHostServices   = "infra.hostapp.provide_services";
static const char* const kM08eOpDbCreate       = "acdb.database.create";
static const char* const kM08eOpCreateExtDict  = "write.object.create_ext_dict";
static const char* const kM08eOpRegappRegister = "write.regapp.register";
static const char* const kM08eOpDictionarySet  = "write.dictionary.set";
static const char* const kM08eOpEntitySetXdata = "write.entity.set_xdata";
static const char* const kM08eOpBlockAppend    = "write.block.append_entity";
static const char* const kM08eOpDeepClone      = "transform.database.deep_clone";
static const char* const kM08eOpInsertBlock    = "transform.database.insert_block";

static bool m08eHasOp(const std::string& op)
{
    return op == kM08eOpEntityXdata
        || op == kM08eOpDictNamed
        || op == kM08eOpDictGet
        || op == kM08eOpBlockIterate
        || op == kM08eOpHostServices
        || op == kM08eOpDbCreate
        || op == kM08eOpCreateExtDict
        || op == kM08eOpRegappRegister
        || op == kM08eOpDictionarySet
        || op == kM08eOpEntitySetXdata
        || op == kM08eOpBlockAppend
        || op == kM08eOpDeepClone
        || op == kM08eOpInsertBlock;
}

// inspect.entity.get_xdata: read an object's extended data (xdata) by handle.
// API: AcDbObject::xData(const ACHAR* regappName=nullptr) const  (dbObject.h:265; resbuf*,
// caller frees via acutRelRb). acdb-core.md row inspect.entity.get_xdata. Serialized through the
// existing xdataBlocksJson (the same app/items shape M02's entities[] uses).
static bool m08eHandleEntityXdata(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string handleHex;
    if (!jsonFindString(ctx.job, "handle", handleHex) || handleHex.empty()) {
        emitNativeError(r, "MISSING_HANDLE", "inspect.entity.get_xdata requires a 'handle'");
        return true;
    }
    std::string regapp;
    const bool hasRegapp = jsonFindString(ctx.job, "regapp", regapp) && !regapp.empty();

    AriadneReadTransaction rt(ctx.pDb);

    AcDbObjectId id;
    if (!resolveHandle(ctx.pDb, handleHex, id)) {
        emitNativeError(r, "HANDLE_NOT_FOUND", "no object for handle '" + handleHex + "'");
        return true;
    }
    AcDbObject* pObj = nullptr;
    if (acdbOpenObject(pObj, id, AcDb::kForRead) != Acad::eOk || pObj == nullptr) {
        emitNativeError(r, "OBJECT_OPEN_FAILED", "could not open object '" + handleHex + "' for read");
        return true;
    }

    const ACHAR* cls = (pObj->isA() != nullptr) ? pObj->isA()->name() : nullptr;
    resbuf* xd = pObj->xData(hasRegapp ? asciiToWide(regapp).c_str() : nullptr);
    int blockCount = 0;
    int itemCount = 0;
    std::string xdataJson = "[]";
    if (xd != nullptr) {
        xdataJson = xdataBlocksJson(xd, blockCount, itemCount);
        acutRelRb(xd);
    }
    pObj->close();

    r << "\"result\":{\"handle\":" << njsonStr(handleOfId(id))
      << ",\"class\":" << njsonStr(cls)
      << ",\"regapp_filter\":" << (hasRegapp ? njsonStr(regapp) : std::string("null"))
      << ",\"xdata_present\":" << (blockCount > 0 ? "true" : "false")
      << ",\"block_count\":" << blockCount
      << ",\"item_count\":" << itemCount
      << ",\"xdata\":" << xdataJson << "},"
      << "\"status\":\"ok\"}";
    return true;
}

// inspect.dictionary.named_objects: list the Named Object Dictionary (root of all non-graphical
// dictionaries). API: AcDbDatabase::getNamedObjectsDictionary(AcDbDictionary*&, kForRead)
// (acdb-core.md). Per-entry shape + any directly-owned xrecords come from the existing
// dictionaryEntriesJson (key / value_handle / class_name / is_xrecord) + xrecordJson.
static bool m08eHandleDictNamed(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    AriadneReadTransaction rt(ctx.pDb);

    AcDbDictionary* pNOD = nullptr;
    if (ctx.pDb->getNamedObjectsDictionary(pNOD, AcDb::kForRead) != Acad::eOk || pNOD == nullptr) {
        emitNativeError(r, "NOD_OPEN_FAILED", "could not open the named objects dictionary");
        return true;
    }
    const std::string nodHandle = handleOf(pNOD);

    std::ostringstream xrecs; xrecs.precision(kJsonDoublePrecision);
    xrecs << "[";
    bool xrecordFirst = true;
    RichGraphCounters counters;
    const std::string entries =
        dictionaryEntriesJson(pNOD, nodHandle, xrecs, xrecordFirst, counters);
    xrecs << "]";
    pNOD->close();

    r << "\"result\":{\"handle\":" << njsonStr(nodHandle)
      << ",\"entry_count\":" << counters.extensionDictionaryEntries
      << ",\"xrecord_count\":" << counters.extensionXrecords
      << ",\"entries\":" << entries
      << ",\"xrecords\":" << xrecs.str() << "},"
      << "\"status\":\"ok\"}";
    return true;
}

// inspect.dictionary.get: resolve one entry by key in a dictionary (NOD by default, or a sub-dict
// by handle). API: AcDbDictionary::getAt(const ACHAR* entryName, AcDbObjectId&) const
// (dbdict.h:106; eKeyNotFound = a normal lookup miss, reported as found:false, NOT an error).
// If the resolved value is itself a dictionary, its children are listed via dictionaryEntriesJson.
static bool m08eHandleDictGet(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string key;
    if (!jsonFindString(ctx.job, "key", key) || key.empty()) {
        emitNativeError(r, "MISSING_KEY", "inspect.dictionary.get requires a 'key'");
        return true;
    }

    AriadneReadTransaction rt(ctx.pDb);

    // Resolve the dictionary to look in: explicit dict_handle, else the NOD root.
    std::string dictHandleArg;
    const bool hasDictHandle = jsonFindString(ctx.job, "dict_handle", dictHandleArg) && !dictHandleArg.empty();
    AcDbDictionary* pDict = nullptr;
    if (hasDictHandle) {
        AcDbObjectId dictId;
        if (!resolveHandle(ctx.pDb, dictHandleArg, dictId)) {
            emitNativeError(r, "HANDLE_NOT_FOUND", "no object for dict_handle '" + dictHandleArg + "'");
            return true;
        }
        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, dictId, AcDb::kForRead) != Acad::eOk || pObj == nullptr) {
            emitNativeError(r, "DICT_OPEN_FAILED", "could not open dict_handle '" + dictHandleArg + "'");
            return true;
        }
        pDict = AcDbDictionary::cast(pObj);
        if (pDict == nullptr) {
            pObj->close();
            emitNativeError(r, "DICT_OPEN_FAILED", "object '" + dictHandleArg + "' is not a dictionary");
            return true;
        }
    }
    else if (ctx.pDb->getNamedObjectsDictionary(pDict, AcDb::kForRead) != Acad::eOk || pDict == nullptr) {
        emitNativeError(r, "DICT_OPEN_FAILED", "could not open the named objects dictionary");
        return true;
    }

    const std::string dictHandle = handleOf(pDict);
    AcDbObjectId valueId;
    const Acad::ErrorStatus es = pDict->getAt(asciiToWide(key).c_str(), valueId);

    if (es != Acad::eOk || valueId.isNull()) {
        // eKeyNotFound (or any miss) is a valid "not found" lookup result, not an error.
        pDict->close();
        r << "\"result\":{\"dictionary_handle\":" << njsonStr(dictHandle)
          << ",\"key\":" << njsonStr(key)
          << ",\"found\":false"
          << ",\"value_handle\":\"\""
          << ",\"class_name\":\"\""
          << ",\"is_dictionary\":false},"
          << "\"status\":\"ok\"}";
        return true;
    }

    const std::string valueHandle = handleOfId(valueId);
    std::string className;
    bool isDictionary = false;
    std::string childEntries;   // populated only when the value is itself a dictionary

    AcDbObject* pValue = nullptr;
    if (acdbOpenObject(pValue, valueId, AcDb::kForRead) == Acad::eOk && pValue != nullptr) {
        if (pValue->isA() != nullptr)
            className = acharToAscii(pValue->isA()->name());
        AcDbDictionary* pChild = AcDbDictionary::cast(pValue);
        if (pChild != nullptr) {
            isDictionary = true;
            std::ostringstream xrecs; xrecs.precision(kJsonDoublePrecision);   // discarded: this op reports the child-key list, not xrecord payloads
            bool xrecordFirst = true;
            RichGraphCounters counters;
            childEntries = dictionaryEntriesJson(pChild, valueHandle, xrecs, xrecordFirst, counters);
        }
        pValue->close();
    }
    pDict->close();

    r << "\"result\":{\"dictionary_handle\":" << njsonStr(dictHandle)
      << ",\"key\":" << njsonStr(key)
      << ",\"found\":true"
      << ",\"value_handle\":" << njsonStr(valueHandle)
      << ",\"class_name\":" << njsonStr(className)
      << ",\"is_dictionary\":" << (isDictionary ? "true" : "false");
    if (isDictionary)
        r << ",\"entries\":" << childEntries;
    r << "},\"status\":\"ok\"}";
    return true;
}

// inspect.block.iterate: enumerate the entities of a block-table record. Target BTR =
// model space (default), or by block_handle, or by block_name. APIs:
// AcDbDatabase::getBlockTable -> AcDbBlockTable::getAt(ACDB_MODEL_SPACE | name, ...) /
// resolveHandle; AcDbBlockTableRecord::newIterator (acdb-core.md inspect.block.iterate);
// AcDbBlockTableRecordIterator::getEntity (dbsymtb.h:1654). Each entity via serializeEntityCommon;
// optional per-entity xdata when include_xdata=true. Pure enumeration -- no geometry decode.
static bool m08eHandleBlockIterate(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    double includeXdataRaw = 0.0;
    jsonFindNumber(ctx.job, "include_xdata", includeXdataRaw);
    const bool includeXdata = includeXdataRaw != 0.0;

    AriadneReadTransaction rt(ctx.pDb);

    // Resolve the target BTR.
    std::string blockHandleArg;
    const bool hasBlockHandle = jsonFindString(ctx.job, "block_handle", blockHandleArg) && !blockHandleArg.empty();
    std::string blockNameArg;
    const bool hasBlockName = jsonFindString(ctx.job, "block_name", blockNameArg) && !blockNameArg.empty();

    AcDbBlockTableRecord* pBTR = nullptr;
    if (hasBlockHandle) {
        AcDbObjectId btrId;
        if (!resolveHandle(ctx.pDb, blockHandleArg, btrId)) {
            emitNativeError(r, "BLOCK_NOT_FOUND", "no object for block_handle '" + blockHandleArg + "'");
            return true;
        }
        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, btrId, AcDb::kForRead) != Acad::eOk || pObj == nullptr) {
            emitNativeError(r, "BTR_OPEN_FAILED", "could not open block_handle '" + blockHandleArg + "'");
            return true;
        }
        pBTR = AcDbBlockTableRecord::cast(pObj);
        if (pBTR == nullptr) {
            pObj->close();
            emitNativeError(r, "BLOCK_NOT_FOUND", "object '" + blockHandleArg + "' is not a block-table record");
            return true;
        }
    }
    else {
        AcDbBlockTable* pBT = nullptr;
        if (ctx.pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk || pBT == nullptr) {
            emitNativeError(r, "BLOCK_TABLE_OPEN_FAILED", "could not open the block table");
            return true;
        }
        const Acad::ErrorStatus es = hasBlockName
            ? pBT->getAt(asciiToWide(blockNameArg).c_str(), pBTR, AcDb::kForRead)
            : pBT->getAt(ACDB_MODEL_SPACE, pBTR, AcDb::kForRead);
        pBT->close();
        if (es != Acad::eOk || pBTR == nullptr) {
            emitNativeError(r, "BLOCK_NOT_FOUND",
                            hasBlockName ? ("no block named '" + blockNameArg + "'")
                                         : std::string("model space block record not found"));
            return true;
        }
    }

    const ACHAR* nameRaw = nullptr;
    std::string btrName;
    if (pBTR->getName(nameRaw) == Acad::eOk)
        btrName = acharToAscii(nameRaw);
    const std::string btrHandle = handleOf(pBTR);

    AcDbBlockTableRecordIterator* pIt = nullptr;
    if (pBTR->newIterator(pIt) != Acad::eOk) {
        pBTR->close();
        emitNativeError(r, "BTR_ITER_FAILED", "could not iterate block record '" + btrHandle + "'");
        return true;
    }

    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    int count = 0;
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbEntity* pEnt = nullptr;
        if (pIt->getEntity(pEnt, AcDb::kForRead) != Acad::eOk || pEnt == nullptr)
            continue;
        const ACHAR* dxf = (pEnt->isA() != nullptr) ? pEnt->isA()->dxfName() : nullptr;
        if (!first)
            arr << ",";
        first = false;
        arr << "{" << serializeEntityCommon(pEnt)
            << ",\"dxf_name\":" << njsonStr(dxf);
        if (includeXdata) {
            resbuf* xd = pEnt->xData(nullptr);
            int bc = 0, ic = 0;
            std::string xj = "[]";
            if (xd != nullptr) {
                xj = xdataBlocksJson(xd, bc, ic);
                acutRelRb(xd);
            }
            arr << ",\"xdata\":" << xj;
        }
        arr << "}";
        ++count;
        pEnt->close();
    }
    delete pIt;
    pBTR->close();
    arr << "]";

    r << "\"result\":{\"block_handle\":" << njsonStr(btrHandle)
      << ",\"block_name\":" << njsonStr(btrName)
      << ",\"entity_count\":" << count
      << ",\"entities\":" << arr.str() << "},"
      << "\"status\":\"ok\"}";
    return true;
}

static bool m08eHandleHostServices(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    AcDbHostApplicationServices* pSvc = acdbHostApplicationServices();
    const bool present = (pSvc != nullptr);
    const bool working = present && (pSvc->workingDatabase() != nullptr);
    std::string product;
    if (present && pSvc->product() != nullptr)
        product = acharToAscii(pSvc->product());
    int total = 0, probes = 0;
    countModelSpace(ctx.pDb, total, probes);
    r << "\"result\":{\"services_present\":" << (present ? "true" : "false")
      << ",\"working_db_present\":" << (working ? "true" : "false")
      << ",\"product\":" << njsonStr(product)
      << ",\"modelspace_count\":" << total
      << "},\"status\":\"ok\"}";
    return true;
}

static bool m08eHandleDbCreate(const AriadneJobCtx&, std::ostringstream& r)
{
    AcDbDatabase* pScratch = new AcDbDatabase(true, true);
    const bool ok = (pScratch != nullptr);
    int layers = -1, blocks = -1, ltypes = -1;
    if (ok) {
        layers = countSymbolTable(pScratch->layerTableId());
        blocks = countSymbolTable(pScratch->blockTableId());
        ltypes = countSymbolTable(pScratch->linetypeTableId());
    }
    delete pScratch;
    r << "\"result\":{\"database_created\":" << (ok ? "true" : "false")
      << ",\"build_default_drawing\":true"
      << ",\"layer_count\":" << layers
      << ",\"block_count\":" << blocks
      << ",\"linetype_count\":" << ltypes
      << ",\"deleted_after_probe\":true},\"status\":\"ok\"}";
    return true;
}

static AcDbObjectId m08eDefaultWritableObjectId(AcDbDatabase* pDb)
{
    if (pDb == nullptr)
        return AcDbObjectId::kNull;
    AcDbObjectId id = pDb->currentSpaceId();
    if (!id.isNull())
        return id;
    return pDb->blockTableId();
}

static bool m08eResolveOptionalObject(const AriadneJobCtx& ctx, AcDbObjectId& id, std::string& handle)
{
    if (jsonFindString(ctx.job, "handle", handle) && !handle.empty())
        return resolveHandle(ctx.pDb, handle, id);
    id = m08eDefaultWritableObjectId(ctx.pDb);
    handle = handleOfId(id);
    return !id.isNull();
}

static bool m08eHandleCreateExtDict(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    AcDbObjectId id;
    std::string handle;
    if (!m08eResolveOptionalObject(ctx, id, handle)) {
        emitNativeError(r, "OBJECT_NOT_FOUND", "write.object.create_ext_dict could not resolve object");
        return true;
    }
    AriadneStagedWriteTransaction wt(ctx.pDb);
    AcDbObject* pObj = nullptr;
    Acad::ErrorStatus es = acdbOpenObject(pObj, id, AcDb::kForWrite);
    bool created = false;
    std::string dictHandle;
    if (es == Acad::eOk && pObj != nullptr) {
        if (pObj->extensionDictionary().isNull()) {
            es = pObj->createExtensionDictionary();
            created = (es == Acad::eOk);
        }
        AcDbObjectId did = pObj->extensionDictionary();
        if (!did.isNull()) dictHandle = handleOfId(did);
        pObj->close();
    }
    r << "\"result\":{\"handle\":" << njsonStr(handle)
      << ",\"created\":" << (created ? "true" : "false")
      << ",\"extension_dictionary_handle\":" << (dictHandle.empty() ? std::string("null") : njsonStr(dictHandle))
      << ",\"staged_rolled_back\":true,\"errorstatus\":" << static_cast<int>(es)
      << "},\"status\":\"ok\"}";
    return true;
}

static bool m08eHandleRegappRegister(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string app;
    if (!jsonFindString(ctx.job, "app", app) || app.empty()) app = "ARIADNE_M08CDEF";
    AriadneStagedWriteTransaction wt(ctx.pDb);
    const Acad::ErrorStatus es = ensureRegApp(ctx.pDb, app);
    r << "\"result\":{\"app\":" << njsonStr(app)
      << ",\"registered\":" << (es == Acad::eOk ? "true" : "false")
      << ",\"staged_rolled_back\":true,\"errorstatus\":" << static_cast<int>(es)
      << "},\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    return true;
}

static bool m08eHandleDictionarySet(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string key, value;
    if (!jsonFindString(ctx.job, "key", key) || key.empty()) key = "M08CDEF_PROBE";
    if (!jsonFindString(ctx.job, "value", value)) value = "scratch";
    AriadneStagedWriteTransaction wt(ctx.pDb);
    const Acad::ErrorStatus es = setXrecord(ctx.pDb, key, value);
    r << "\"result\":{\"key\":" << njsonStr(key)
      << ",\"value\":" << njsonStr(value)
      << ",\"xrecord_set\":" << (es == Acad::eOk ? "true" : "false")
      << ",\"staged_rolled_back\":true,\"errorstatus\":" << static_cast<int>(es)
      << "},\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    return true;
}

static bool m08eHandleEntitySetXdata(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string app, value;
    if (!jsonFindString(ctx.job, "app", app) || app.empty()) app = "ARIADNE_M08CDEF";
    if (!jsonFindString(ctx.job, "value", value)) value = "scratch";
    AriadneStagedWriteTransaction wt(ctx.pDb);
    const Acad::ErrorStatus es = setDatabaseXdata(ctx.pDb, app, value);
    r << "\"result\":{\"app\":" << njsonStr(app)
      << ",\"value\":" << njsonStr(value)
      << ",\"xdata_set\":" << (es == Acad::eOk ? "true" : "false")
      << ",\"staged_rolled_back\":true,\"errorstatus\":" << static_cast<int>(es)
      << "},\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    return true;
}

// Build one of the 4 certified entity kinds (line/circle/arc/text) from an "entity" job
// sub-object -- {"kind":"...", ...kind-specific fields, same field names write.entity.line/
// circle/arc/text already use}. m08e-local MINIMAL DUPLICATE of the per-kind AcDb* construction
// m08gAppendEntity/m08hAppend already certify (not a shared refactor: those family .inc files are
// owned by sibling lanes editing the same TU concurrently, and both hardcode ACDB_MODEL_SPACE
// anyway, so there is nothing there this handler could call as-is). All 4 classes come from
// dbents.h, already #included at the top of the TU before any family .inc. On success returns a
// freshly new()'d AcDbEntity* (caller owns: appendAcDbEntity() or delete() consumes it). On
// failure returns nullptr and fills errCode/errMsg for an emitNativeError envelope.
static AcDbEntity* m08eBuildEntityForAppend(const std::string& entityJson,
                                            std::string& kindOut,
                                            std::string& errCode,
                                            std::string& errMsg)
{
    jsonFindString(entityJson, "kind", kindOut);

    if (kindOut == "line") {
        AcGePoint3d start(0.0, 0.0, 0.0), end(1.0, 0.0, 0.0);
        std::string ptJson;
        if (jsonFindObject(entityJson, "start", ptJson)) {
            double x = 0.0, y = 0.0, z = 0.0;
            jsonFindNumber(ptJson, "x", x); jsonFindNumber(ptJson, "y", y); jsonFindNumber(ptJson, "z", z);
            start.set(x, y, z);
        }
        if (jsonFindObject(entityJson, "end", ptJson)) {
            double x = 1.0, y = 0.0, z = 0.0;
            jsonFindNumber(ptJson, "x", x); jsonFindNumber(ptJson, "y", y); jsonFindNumber(ptJson, "z", z);
            end.set(x, y, z);
        }
        return new AcDbLine(start, end);
    }
    if (kindOut == "circle") {
        AcGePoint3d center(0.0, 0.0, 0.0);
        std::string ptJson;
        if (jsonFindObject(entityJson, "center", ptJson)) {
            double x = 0.0, y = 0.0, z = 0.0;
            jsonFindNumber(ptJson, "x", x); jsonFindNumber(ptJson, "y", y); jsonFindNumber(ptJson, "z", z);
            center.set(x, y, z);
        }
        double radius = 1.0;
        jsonFindNumber(entityJson, "radius", radius);
        if (radius <= 0.0) {
            errCode = "INVALID_INPUT"; errMsg = "entity.kind=circle requires 'radius' > 0";
            return nullptr;
        }
        return new AcDbCircle(center, AcGeVector3d(0.0, 0.0, 1.0), radius);
    }
    if (kindOut == "arc") {
        AcGePoint3d center(0.0, 0.0, 0.0);
        std::string ptJson;
        if (jsonFindObject(entityJson, "center", ptJson)) {
            double x = 0.0, y = 0.0, z = 0.0;
            jsonFindNumber(ptJson, "x", x); jsonFindNumber(ptJson, "y", y); jsonFindNumber(ptJson, "z", z);
            center.set(x, y, z);
        }
        double radius = 1.0, sa = 0.0, ea = 6.28318530717958647692;
        jsonFindNumber(entityJson, "radius", radius);
        jsonFindNumber(entityJson, "start_angle", sa);
        jsonFindNumber(entityJson, "end_angle", ea);
        if (radius <= 0.0) {
            errCode = "INVALID_INPUT"; errMsg = "entity.kind=arc requires 'radius' > 0";
            return nullptr;
        }
        return new AcDbArc(center, radius, sa, ea);
    }
    if (kindOut == "text") {
        AcGePoint3d pos(0.0, 0.0, 0.0);
        std::string ptJson;
        if (jsonFindObject(entityJson, "position", ptJson)) {
            double x = 0.0, y = 0.0, z = 0.0;
            jsonFindNumber(ptJson, "x", x); jsonFindNumber(ptJson, "y", y); jsonFindNumber(ptJson, "z", z);
            pos.set(x, y, z);
        }
        std::string content;
        jsonFindString(entityJson, "text", content);
        double height = 2.5;
        jsonFindNumber(entityJson, "height", height);

        AcDbText* pText = new AcDbText();
        pText->setPosition(pos);
        if (height > 0.0)
            pText->setHeight(height);
        pText->setTextString(utf8ToWide(content).c_str());
        return pText;
    }

    errCode = "UNSUPPORTED_KIND";
    errMsg = "write.block.append_entity supports entity.kind in {line,circle,arc,text}; got '" + kindOut + "'";
    return nullptr;
}

// write.block.append_entity: append a real entity (line/circle/arc/text, per
// m08eBuildEntityForAppend above) into a NAMED block-table record ('block_name'), or model space
// if block_name is omitted. REAL, PERSISTING primitive -- unlike this family's other write ops
// (see the file header comment), this one does NOT wrap in AriadneStagedWriteTransaction: it
// mutates ctx.pDb directly, the same no-wrapper shape every other real write handler in the
// codebase uses (write.entity.line/circle/arc/text/... in m08g_handlers.inc / m08h_handlers.inc /
// AriadneNativeJob.cpp), so the appended entity survives to the staged-copy DWG the router job
// already operates on. Still never touches the ORIGINAL file (write_mode policy layer, same as
// every other write op).
// APIs: AcDbBlockTable::getAt(name, AcDbBlockTableRecord*&, AcDb::kForWrite) (dbsymtb.h) to
// resolve the target BTR by name (same read-mode shape m08eHandleBlockIterate above already
// uses); AcDbBlockTableRecord::appendAcDbEntity(AcDbObjectId&, AcDbEntity*) (dbsymtb.h) to add
// the built entity to it (acdb-core.md's citation for this op).
static bool m08eHandleBlockAppend(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string blockName;
    const bool hasBlockName = jsonFindString(ctx.job, "block_name", blockName) && !blockName.empty();

    std::string entityJson;
    if (!jsonFindObject(ctx.job, "entity", entityJson)) {
        emitNativeError(r, "MISSING_ARG", "write.block.append_entity requires an 'entity' object ({kind,...})");
        return true;
    }

    std::string kind, buildErrCode, buildErrMsg;
    AcDbEntity* pEnt = m08eBuildEntityForAppend(entityJson, kind, buildErrCode, buildErrMsg);
    if (pEnt == nullptr) {
        if (buildErrCode.empty())
            emitNativeError(r, "BUILD_FAILED", buildErrMsg);
        else
            emitNativeError(r, buildErrCode.c_str(), buildErrMsg);
        return true;
    }

    std::string layer;
    jsonFindString(ctx.job, "layer", layer);
    if (!layer.empty()) {
        bool layerCreated = false;
        const Acad::ErrorStatus layerEs = ensureLayer(ctx.pDb, layer, 7, layerCreated);
        if (layerEs != Acad::eOk) {
            delete pEnt;
            emitNativeError(r, "LAYER_FAILED",
                            "ensureLayer('" + layer + "') errorstatus " + std::to_string(static_cast<int>(layerEs)));
            return true;
        }
    }

    AcDbBlockTable* pBT = nullptr;
    Acad::ErrorStatus es = ctx.pDb->getBlockTable(pBT, AcDb::kForRead);
    if (es != Acad::eOk || pBT == nullptr) {
        delete pEnt;
        emitNativeError(r, "BLOCK_TABLE_OPEN_FAILED", "could not open the block table");
        return true;
    }

    AcDbBlockTableRecord* pBTR = nullptr;
    es = hasBlockName
        ? pBT->getAt(asciiToWide(blockName).c_str(), pBTR, AcDb::kForWrite)
        : pBT->getAt(ACDB_MODEL_SPACE, pBTR, AcDb::kForWrite);
    pBT->close();
    if (es != Acad::eOk || pBTR == nullptr) {
        delete pEnt;
        emitNativeError(r, "BLOCK_NOT_FOUND",
                        hasBlockName ? ("no block named '" + blockName + "'")
                                     : std::string("model space block record not found"));
        return true;
    }

    const std::string btrHandle = handleOf(pBTR);
    const std::string btrName = hasBlockName ? blockName : std::string("*MODEL_SPACE");

    if (!layer.empty())
        pEnt->setLayer(asciiToWide(layer).c_str());

    AcDbObjectId newId;
    es = pBTR->appendAcDbEntity(newId, pEnt);
    if (es == Acad::eOk)
        pEnt->close();
    else
        delete pEnt;

    int entityCountAfter = -1;
    if (es == Acad::eOk) {
        AcDbBlockTableRecordIterator* pIt = nullptr;
        if (pBTR->newIterator(pIt) == Acad::eOk && pIt != nullptr) {
            entityCountAfter = 0;
            for (pIt->start(); !pIt->done(); pIt->step())
                ++entityCountAfter;
            delete pIt;
        }
    }
    pBTR->close();

    r << "\"result\":{\"appended\":" << (es == Acad::eOk ? "true" : "false")
      << ",\"block_name\":" << njsonStr(btrName)
      << ",\"block_handle\":" << njsonStr(btrHandle)
      << ",\"kind\":" << njsonStr(kind)
      << ",\"new_handle\":" << (es == Acad::eOk ? njsonStr(handleOfId(newId)) : std::string("null"))
      << ",\"layer\":" << njsonStr(layer)
      << ",\"block_entity_count_after\":" << entityCountAfter
      << ",\"staged_rolled_back\":false"
      << ",\"errorstatus\":" << static_cast<int>(es)
      << "},\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    return true;
}

static bool m08eHandleInsertBlock(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string name;
    if (!jsonFindString(ctx.job, "name", name) || name.empty()) name = "ARIADNE_M08CDEF_BLOCK";
    AriadneStagedWriteTransaction wt(ctx.pDb);
    AcDbBlockTable* pBT = nullptr;
    Acad::ErrorStatus es = ctx.pDb->getBlockTable(pBT, AcDb::kForWrite);
    AcDbObjectId btrId = AcDbObjectId::kNull;
    if (es == Acad::eOk && pBT != nullptr) {
        AcDbBlockTableRecord* pNew = new AcDbBlockTableRecord();
        pNew->setName(asciiToWide(name).c_str());
        es = pBT->add(btrId, pNew);
        if (es == Acad::eOk) pNew->close(); else delete pNew;
        pBT->close();
    }
    r << "\"result\":{\"block_name\":" << njsonStr(name)
      << ",\"created_block_record\":" << (es == Acad::eOk ? "true" : "false")
      << ",\"block_handle\":" << (btrId.isNull() ? std::string("null") : njsonStr(handleOfId(btrId)))
      << ",\"staged_rolled_back\":true,\"errorstatus\":" << static_cast<int>(es)
      << "},\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    return true;
}

static bool m08eHandleDeepClone(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    AriadneStagedWriteTransaction wt(ctx.pDb);
    AcDbBlockTable* pBT = nullptr;
    Acad::ErrorStatus es = ctx.pDb->getBlockTable(pBT, AcDb::kForRead);
    AcDbBlockTableRecord* pMS = nullptr;
    if (es == Acad::eOk && pBT != nullptr) {
        es = pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForRead);
        pBT->close();
    }
    AcDbObjectId firstId = AcDbObjectId::kNull;
    if (es == Acad::eOk && pMS != nullptr) {
        AcDbBlockTableRecordIterator* pIt = nullptr;
        if (pMS->newIterator(pIt) == Acad::eOk && pIt != nullptr) {
            if (!pIt->done()) pIt->getEntityId(firstId);
            delete pIt;
        }
        pMS->close();
    }
    bool cloned = false;
    std::string cloneHandle;
    if (!firstId.isNull()) {
        AcDbObjectIdArray ids; ids.append(firstId);
        AcDbIdMapping idMap;
        es = ctx.pDb->deepCloneObjects(ids, ctx.pDb->currentSpaceId(), idMap, false);
        cloned = (es == Acad::eOk);
        if (cloned) {
            AcDbIdPair pair(firstId, AcDbObjectId::kNull, false, false, false);
            if (idMap.compute(pair) && pair.isCloned())
                cloneHandle = handleOfId(pair.value());
        }
    }
    r << "\"result\":{\"source_handle\":" << (firstId.isNull() ? std::string("null") : njsonStr(handleOfId(firstId)))
      << ",\"cloned\":" << (cloned ? "true" : "false")
      << ",\"clone_handle\":" << (cloneHandle.empty() ? std::string("null") : njsonStr(cloneHandle))
      << ",\"staged_rolled_back\":true,\"errorstatus\":" << static_cast<int>(es)
      << "},\"status\":\"" << (cloned ? "ok" : "error") << "\"}";
    return true;
}

static bool m08eDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    if (op == kM08eOpEntityXdata)
        return m08eHandleEntityXdata(ctx, r);
    if (op == kM08eOpDictNamed)
        return m08eHandleDictNamed(ctx, r);
    if (op == kM08eOpDictGet)
        return m08eHandleDictGet(ctx, r);
    if (op == kM08eOpBlockIterate)
        return m08eHandleBlockIterate(ctx, r);
    if (op == kM08eOpHostServices)
        return m08eHandleHostServices(ctx, r);
    if (op == kM08eOpDbCreate)
        return m08eHandleDbCreate(ctx, r);
    if (op == kM08eOpCreateExtDict)
        return m08eHandleCreateExtDict(ctx, r);
    if (op == kM08eOpRegappRegister)
        return m08eHandleRegappRegister(ctx, r);
    if (op == kM08eOpDictionarySet)
        return m08eHandleDictionarySet(ctx, r);
    if (op == kM08eOpEntitySetXdata)
        return m08eHandleEntitySetXdata(ctx, r);
    if (op == kM08eOpBlockAppend)
        return m08eHandleBlockAppend(ctx, r);
    if (op == kM08eOpDeepClone)
        return m08eHandleDeepClone(ctx, r);
    if (op == kM08eOpInsertBlock)
        return m08eHandleInsertBlock(ctx, r);
    return false;
}
