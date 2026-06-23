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
// part of a read-only family. They are deliberately left OUT of m08eHasOp (so they keep returning
// the honest OPERATION_NOT_IMPLEMENTED) and recorded as catalogued-remaining in reports/tickets/M08E.md
// for the M08G write lane. No fabricated results.
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

    std::ostringstream xrecs;
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
            std::ostringstream xrecs;   // discarded: this op reports the child-key list, not xrecord payloads
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

    std::ostringstream arr;
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

static bool m08eHandleBlockAppend(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    AriadneStagedWriteTransaction wt(ctx.pDb);
    AcDbBlockTable* pBT = nullptr;
    Acad::ErrorStatus es = ctx.pDb->getBlockTable(pBT, AcDb::kForRead);
    AcDbBlockTableRecord* pMS = nullptr;
    if (es == Acad::eOk && pBT != nullptr) {
        es = pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite);
        pBT->close();
    }
    AcDbObjectId lineId = AcDbObjectId::kNull;
    if (es == Acad::eOk && pMS != nullptr) {
        AcDbLine* pLine = new AcDbLine(AcGePoint3d(0,0,0), AcGePoint3d(1,0,0));
        es = pMS->appendAcDbEntity(lineId, pLine);
        if (es == Acad::eOk) pLine->close(); else delete pLine;
        pMS->close();
    }
    r << "\"result\":{\"appended\":" << (es == Acad::eOk ? "true" : "false")
      << ",\"new_handle\":" << (lineId.isNull() ? std::string("null") : njsonStr(handleOfId(lineId)))
      << ",\"staged_rolled_back\":true,\"errorstatus\":" << static_cast<int>(es)
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
