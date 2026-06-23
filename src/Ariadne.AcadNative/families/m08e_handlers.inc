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

#include "dbidmap.h"      // AcDbIdMapping for deep/wblock clone style ops

// ---- op id constants (single source for HasOp + Dispatch; avoids string drift) -------------
static const char* const kM08eOpEntityXdata   = "inspect.entity.get_xdata";
static const char* const kM08eOpDictNamed      = "inspect.dictionary.named_objects";
static const char* const kM08eOpDictGet        = "inspect.dictionary.get";
static const char* const kM08eOpBlockIterate   = "inspect.block.iterate";
static const char* const kM08eOpHostProvide    = "infra.hostapp.provide_services";
static const char* const kM08eOpDeepClone      = "transform.database.deep_clone";
static const char* const kM08eOpInsertBlock    = "transform.database.insert_block";
static const char* const kM08eOpAppendEntity   = "write.block.append_entity";
static const char* const kM08eOpDbCreate       = "acdb.database.create";
static const char* const kM08eOpDictSet        = "write.dictionary.set";
static const char* const kM08eOpEntitySetXdata = "write.entity.set_xdata";

static bool m08eHasOp(const std::string& op)
{
    return op == kM08eOpEntityXdata
        || op == kM08eOpDictNamed
        || op == kM08eOpDictGet
        || op == kM08eOpBlockIterate
        || op == kM08eOpHostProvide
        || op == kM08eOpDeepClone
        || op == kM08eOpInsertBlock
        || op == kM08eOpAppendEntity
        || op == kM08eOpDbCreate
        || op == kM08eOpDictSet
        || op == kM08eOpEntitySetXdata;
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

static bool m08eHandleHostProvide(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    AcDbHostApplicationServices* pSvc = acdbHostApplicationServices();
    const bool present = (pSvc != nullptr);
    std::string product;
    bool working = false;
    if (present) {
        const ACHAR* p = pSvc->product();
        if (p != nullptr) product = acharToAscii(p);
        working = (pSvc->workingDatabase() != nullptr);
    }
    r << "\"result\":{\"services_present\":" << (present ? "true" : "false")
      << ",\"provided\":" << (present ? "true" : "false")
      << ",\"product\":" << njsonStr(product)
      << ",\"working_db_present\":" << (working ? "true" : "false")
      << ",\"host_mode\":" << njsonStr(ctx.hostMode) << "},"
      << "\"status\":\"" << (present ? "ok" : "error") << "\"}";
    return true;
}

static bool m08eOpenModelSpaceForWrite(AcDbDatabase* pDb, AcDbBlockTableRecord*& pMS)
{
    pMS = nullptr;
    AcDbBlockTable* pBT = nullptr;
    if (pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk || pBT == nullptr)
        return false;
    Acad::ErrorStatus es = pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite);
    pBT->close();
    return es == Acad::eOk && pMS != nullptr;
}

static void m08ePoint(const std::string& job, const char* key,
                      double dx, double dy, double dz, AcGePoint3d& out)
{
    double x = dx, y = dy, z = dz;
    std::string obj;
    if (jsonFindObject(job, key, obj)) {
        jsonFindNumber(obj, "x", x); jsonFindNumber(obj, "y", y); jsonFindNumber(obj, "z", z);
    }
    out.set(x, y, z);
}

static bool m08eHandleDbCreate(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    double buildRaw = 1.0, noDocRaw = 1.0;
    jsonFindNumber(ctx.job, "build_default", buildRaw);
    jsonFindNumber(ctx.job, "no_document", noDocRaw);
    AcDbDatabase* pNew = new AcDbDatabase(buildRaw != 0.0, noDocRaw != 0.0);
    int total = 0, probes = 0;
    if (pNew != nullptr)
        countModelSpace(pNew, total, probes);
    const int layers = pNew != nullptr ? countSymbolTable(pNew->layerTableId()) : -1;
    const int blocks = pNew != nullptr ? countSymbolTable(pNew->blockTableId()) : -1;
    delete pNew;
    r << "\"result\":{\"created\":" << (layers >= 0 ? "true" : "false")
      << ",\"build_default\":" << (buildRaw != 0.0 ? "true" : "false")
      << ",\"no_document\":" << (noDocRaw != 0.0 ? "true" : "false")
      << ",\"layers\":" << layers
      << ",\"blocks\":" << blocks
      << ",\"modelspace_entities\":" << total
      << ",\"persisted\":false},"
      << "\"status\":\"" << (layers >= 0 ? "ok" : "error") << "\"}";
    return true;
}

static bool m08eHandleDictSet(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string key, value;
    if (!jsonFindString(ctx.job, "key", key) || key.empty())
        key = "ARIADNE_M08E";
    jsonFindString(ctx.job, "value", value);
    if (value.empty())
        value = "m08e dictionary value";

    AcDbDictionary* pDict = nullptr;
    std::string dictHandle;
    if (jsonFindString(ctx.job, "dict_handle", dictHandle) && !dictHandle.empty()) {
        AcDbObjectId did;
        if (!resolveHandle(ctx.pDb, dictHandle, did)) {
            emitNativeError(r, "HANDLE_NOT_FOUND", "no dictionary for dict_handle " + dictHandle);
            return true;
        }
        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, did, AcDb::kForWrite) != Acad::eOk || pObj == nullptr) {
            emitNativeError(r, "DICT_OPEN_FAILED", "could not open dict_handle for write");
            return true;
        }
        pDict = AcDbDictionary::cast(pObj);
        if (pDict == nullptr) {
            pObj->close();
            emitNativeError(r, "DICT_OPEN_FAILED", "dict_handle is not an AcDbDictionary");
            return true;
        }
    } else if (ctx.pDb->getNamedObjectsDictionary(pDict, AcDb::kForWrite) != Acad::eOk || pDict == nullptr) {
        emitNativeError(r, "NOD_OPEN_FAILED", "could not open named objects dictionary for write");
        return true;
    }
    const std::string actualDictHandle = handleOf(pDict);
    const std::wstring keyW = utf8ToWide(key);
    const std::wstring valueW = utf8ToWide(value);
    resbuf* rb = acutBuildList(AcDb::kDxfText, valueW.c_str(), 0);
    if (rb == nullptr) {
        pDict->close();
        emitNativeError(r, "OUT_OF_MEMORY", "could not allocate xrecord resbuf");
        return true;
    }
    bool replaced = false;
    AcDbObjectId valueId;
    AcDbObject* pExisting = nullptr;
    Acad::ErrorStatus es = pDict->getAt(keyW.c_str(), pExisting, AcDb::kForWrite);
    if (es == Acad::eOk && pExisting != nullptr) {
        AcDbXrecord* pX = AcDbXrecord::cast(pExisting);
        if (pX == nullptr) {
            pExisting->close();
            acutRelRb(rb);
            pDict->close();
            emitNativeError(r, "WRONG_OBJECT_TYPE", "dictionary entry exists but is not an AcDbXrecord");
            return true;
        }
        valueId = pX->objectId();
        es = pX->setFromRbChain(*rb);
        pX->close();
        replaced = true;
    } else if (es == Acad::eKeyNotFound) {
        AcDbXrecord* pX = new AcDbXrecord();
        es = pX->setFromRbChain(*rb);
        if (es == Acad::eOk)
            es = pDict->setAt(keyW.c_str(), pX, valueId);
        if (es == Acad::eOk) pX->close(); else delete pX;
    }
    acutRelRb(rb);
    pDict->close();
    r << "\"result\":{\"set\":" << (es == Acad::eOk ? "true" : "false")
      << ",\"errorstatus\":" << static_cast<int>(es)
      << ",\"dictionary_handle\":" << njsonStr(actualDictHandle)
      << ",\"key\":" << njsonStr(key)
      << ",\"value_handle\":" << njsonStr(es == Acad::eOk ? handleOfId(valueId) : std::string())
      << ",\"replaced\":" << (replaced ? "true" : "false") << "},"
      << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    return true;
}

static bool m08eHandleEntitySetXdata(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string handle;
    if (!jsonFindString(ctx.job, "handle", handle) || handle.empty()) {
        emitNativeError(r, "MISSING_HANDLE", "write.entity.set_xdata requires handle");
        return true;
    }
    std::string app, value;
    jsonFindString(ctx.job, "regapp", app); if (app.empty()) app = "ARIADNE";
    jsonFindString(ctx.job, "value", value); if (value.empty()) value = "m08e xdata";
    Acad::ErrorStatus es = ensureRegApp(ctx.pDb, app);
    if (es != Acad::eOk) {
        emitNativeError(r, "REGAPP_FAILED", "ensureRegApp es=" + std::to_string(static_cast<int>(es)));
        return true;
    }
    AcDbObjectId id;
    if (!resolveHandle(ctx.pDb, handle, id)) {
        emitNativeError(r, "HANDLE_NOT_FOUND", "no object for handle " + handle);
        return true;
    }
    AcDbObject* pObj = nullptr;
    if (acdbOpenObject(pObj, id, AcDb::kForWrite) != Acad::eOk || pObj == nullptr) {
        emitNativeError(r, "OBJECT_OPEN_FAILED", "could not open object for xdata write");
        return true;
    }
    const std::wstring appW = utf8ToWide(app);
    const std::wstring valueW = utf8ToWide(value);
    resbuf* rb = acutBuildList(
        AcDb::kDxfRegAppName, appW.c_str(),
        AcDb::kDxfXdAsciiString, valueW.c_str(),
        0);
    if (rb == nullptr) {
        pObj->close();
        emitNativeError(r, "OUT_OF_MEMORY", "could not allocate xdata resbuf");
        return true;
    }
    es = pObj->setXData(rb);
    acutRelRb(rb);
    pObj->close();
    r << "\"result\":{\"set\":" << (es == Acad::eOk ? "true" : "false")
      << ",\"errorstatus\":" << static_cast<int>(es)
      << ",\"handle\":" << njsonStr(handle)
      << ",\"regapp\":" << njsonStr(app) << "},"
      << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    return true;
}

static bool m08eHandleAppendEntity(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string blockName, blockHandle, kind;
    jsonFindString(ctx.job, "block_name", blockName);
    jsonFindString(ctx.job, "block_handle", blockHandle);
    jsonFindString(ctx.job, "entity", kind);
    if (kind.empty()) kind = "line";

    AcDbBlockTableRecord* pBTR = nullptr;
    if (!blockHandle.empty()) {
        AcDbObjectId bid;
        if (!resolveHandle(ctx.pDb, blockHandle, bid)) {
            emitNativeError(r, "BLOCK_NOT_FOUND", "no block for block_handle " + blockHandle);
            return true;
        }
        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, bid, AcDb::kForWrite) != Acad::eOk || pObj == nullptr) {
            emitNativeError(r, "BTR_OPEN_FAILED", "could not open block_handle for write");
            return true;
        }
        pBTR = AcDbBlockTableRecord::cast(pObj);
        if (pBTR == nullptr) { pObj->close(); emitNativeError(r, "BLOCK_NOT_FOUND", "block_handle is not a BTR"); return true; }
    } else {
        AcDbBlockTable* pBT = nullptr;
        if (ctx.pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk || pBT == nullptr) {
            emitNativeError(r, "BLOCK_TABLE_OPEN_FAILED", "could not open block table");
            return true;
        }
        Acad::ErrorStatus es = blockName.empty()
            ? pBT->getAt(ACDB_MODEL_SPACE, pBTR, AcDb::kForWrite)
            : pBT->getAt(utf8ToWide(blockName).c_str(), pBTR, AcDb::kForWrite);
        pBT->close();
        if (es != Acad::eOk || pBTR == nullptr) {
            emitNativeError(r, "BLOCK_NOT_FOUND", blockName.empty() ? "modelspace not found" : ("no block named " + blockName));
            return true;
        }
    }
    std::string layer; jsonFindString(ctx.job, "layer", layer);
    if (!layer.empty()) { bool c = false; ensureLayer(ctx.pDb, layer, 7, c); }
    AcDbEntity* pEnt = nullptr;
    if (kind == "text") {
        std::string text; jsonFindString(ctx.job, "text", text); if (text.empty()) text = "Ariadne";
        double height = 2.5; jsonFindNumber(ctx.job, "height", height);
        AcGePoint3d pos(0.0, 0.0, 0.0); m08ePoint(ctx.job, "position", 0.0, 0.0, 0.0, pos);
        AcDbText* pText = new AcDbText();
        pText->setPosition(pos);
        if (height > 0.0) pText->setHeight(height);
        pText->setTextString(utf8ToWide(text).c_str());
        pEnt = pText;
    } else {
        AcGePoint3d a, b;
        m08ePoint(ctx.job, "start", 0.0, 0.0, 0.0, a);
        m08ePoint(ctx.job, "end", 1.0, 0.0, 0.0, b);
        pEnt = new AcDbLine(a, b);
    }
    if (!layer.empty()) pEnt->setLayer(utf8ToWide(layer).c_str());
    AcDbObjectId id;
    Acad::ErrorStatus es = pBTR->appendAcDbEntity(id, pEnt);
    pBTR->close();
    if (es == Acad::eOk) pEnt->close(); else delete pEnt;
    int probes = 0, ms = 0; countModelSpace(ctx.pDb, ms, probes);
    r << "\"result\":{\"created\":" << (es == Acad::eOk ? "true" : "false")
      << ",\"errorstatus\":" << static_cast<int>(es)
      << ",\"handle\":" << njsonStr(es == Acad::eOk ? handleOfId(id) : std::string())
      << ",\"target_block\":" << njsonStr(blockName.empty() ? std::string("MODEL_SPACE") : blockName)
      << ",\"entity\":" << njsonStr(kind)
      << ",\"modelspace_entities_after\":" << ms << "},"
      << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    return true;
}

static bool m08eHandleDeepClone(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::vector<std::string> handles = jsonFindStringArray(ctx.job, "handles");
    std::string one;
    if (handles.empty() && jsonFindString(ctx.job, "handle", one) && !one.empty())
        handles.push_back(one);
    if (handles.empty()) {
        emitNativeError(r, "MISSING_HANDLE", "transform.database.deep_clone requires handle or handles array");
        return true;
    }
    AcDbObjectIdArray ids;
    for (size_t i = 0; i < handles.size(); ++i) {
        AcDbObjectId id;
        if (resolveHandle(ctx.pDb, handles[i], id))
            ids.append(id);
    }
    if (ids.isEmpty()) {
        emitNativeError(r, "HANDLE_NOT_FOUND", "no cloneable handles resolved");
        return true;
    }
    AcDbBlockTable* pBT = nullptr;
    if (ctx.pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk || pBT == nullptr) {
        emitNativeError(r, "BLOCK_TABLE_OPEN_FAILED", "could not open block table");
        return true;
    }
    AcDbObjectId owner;
    Acad::ErrorStatus es = pBT->getAt(ACDB_MODEL_SPACE, owner);
    pBT->close();
    if (es != Acad::eOk) { emitNativeError(r, "MODELSPACE_NOT_FOUND", "model space owner not found"); return true; }
    AcDbIdMapping idMap;
    es = ctx.pDb->deepCloneObjects(ids, owner, idMap, false);
    int probes = 0, ms = 0; countModelSpace(ctx.pDb, ms, probes);
    r << "\"result\":{\"cloned\":" << (es == Acad::eOk ? "true" : "false")
      << ",\"errorstatus\":" << static_cast<int>(es)
      << ",\"input_count\":" << ids.length()
      << ",\"owner\":" << njsonStr(handleOfId(owner))
      << ",\"modelspace_entities_after\":" << ms << "},"
      << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    return true;
}

static bool m08eHandleInsertBlock(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string blockName;
    jsonFindString(ctx.job, "name", blockName);
    if (blockName.empty())
        blockName = "ARIADNE_INSERTED_BLOCK";
    AcDbDatabase src(true, true);
    AcDbBlockTableRecord* pMS = nullptr;
    if (m08eOpenModelSpaceForWrite(&src, pMS)) {
        AcDbLine* pLine = new AcDbLine(AcGePoint3d(0.0, 0.0, 0.0), AcGePoint3d(1.0, 0.0, 0.0));
        AcDbObjectId lid;
        Acad::ErrorStatus les = pMS->appendAcDbEntity(lid, pLine);
        pMS->close();
        if (les == Acad::eOk) pLine->close(); else delete pLine;
    }
    AcDbObjectId blockId;
    Acad::ErrorStatus es = ctx.pDb->insert(blockId, utf8ToWide(blockName).c_str(), &src, true);
    r << "\"result\":{\"inserted\":" << (es == Acad::eOk ? "true" : "false")
      << ",\"errorstatus\":" << static_cast<int>(es)
      << ",\"block_name\":" << njsonStr(blockName)
      << ",\"block_handle\":" << njsonStr(es == Acad::eOk ? handleOfId(blockId) : std::string()) << "},"
      << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
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
    if (op == kM08eOpHostProvide)
        return m08eHandleHostProvide(ctx, r);
    if (op == kM08eOpDbCreate)
        return m08eHandleDbCreate(ctx, r);
    if (op == kM08eOpDictSet)
        return m08eHandleDictSet(ctx, r);
    if (op == kM08eOpEntitySetXdata)
        return m08eHandleEntitySetXdata(ctx, r);
    if (op == kM08eOpAppendEntity)
        return m08eHandleAppendEntity(ctx, r);
    if (op == kM08eOpDeepClone)
        return m08eHandleDeepClone(ctx, r);
    if (op == kM08eOpInsertBlock)
        return m08eHandleInsertBlock(ctx, r);
    return false;
}
