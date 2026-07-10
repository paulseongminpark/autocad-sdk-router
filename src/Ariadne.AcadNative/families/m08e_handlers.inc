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
#include "dbpl.h"         // AcDbPolyline (LWPOLYLINE append kind)
#include "dbspline.h"     // AcDbSpline
#include "dbelipse.h"     // AcDbEllipse
#include "gedblar.h"      // AcGeDoubleArray
#include "gevptar.h"      // AcGeVoidPointerArray
#include "imgdef.h"       // AcDbRasterImageDef (wipeout image def)
#include "imgent.h"       // AcDbRasterImage::ClipBoundaryType
#include "dbwipe.h"       // AcDbWipeout
#include "rxdlinkr.h"     // acrxDynamicLinker->loadModule

#pragma comment(lib, "acismobj26.lib")

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
static const char* const kM08eOpRelinkAssoc    = "write.block.relink_hatch_assoc";
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
        || op == kM08eOpRelinkAssoc
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

static bool m08eIsJsonSpace(char c)
{
    return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}

static size_t m08eFindMatchingJsonDelimiter(const std::string& json, size_t openPos,
                                            char openCh, char closeCh)
{
    int depth = 0;
    bool inString = false;
    bool escaped = false;
    for (size_t i = openPos; i < json.size(); ++i) {
        const char c = json[i];
        if (inString) {
            if (escaped) {
                escaped = false;
            } else if (c == '\\') {
                escaped = true;
            } else if (c == '"') {
                inString = false;
            }
            continue;
        }
        if (c == '"') {
            inString = true;
            continue;
        }
        if (c == openCh) {
            ++depth;
            continue;
        }
        if (c == closeCh) {
            --depth;
            if (depth == 0)
                return i;
            if (depth < 0)
                return std::string::npos;
        }
    }
    return std::string::npos;
}

static bool m08eFindArrayBounds(const std::string& json, const char* key,
                                size_t& lbOut, size_t& rbOut)
{
    const std::string keyTok = std::string("\"") + key + "\"";
    const size_t p = json.find(keyTok);
    if (p == std::string::npos)
        return false;
    lbOut = json.find('[', p);
    if (lbOut == std::string::npos)
        return false;
    rbOut = m08eFindMatchingJsonDelimiter(json, lbOut, '[', ']');
    return rbOut != std::string::npos;
}

static bool m08eFindFlag(const std::string& json, const char* key, bool& out)
{
    double raw = 0.0;
    if (jsonFindNumber(json, key, raw)) {
        out = (raw != 0.0);
        return true;
    }
    const std::string keyTok = std::string("\"") + key + "\"";
    const size_t p = json.find(keyTok);
    if (p == std::string::npos)
        return false;
    const size_t colon = json.find(':', p + keyTok.size());
    if (colon == std::string::npos)
        return false;
    size_t i = colon + 1;
    while (i < json.size() && m08eIsJsonSpace(json[i]))
        ++i;
    if (json.compare(i, 4, "true") == 0) {
        out = true;
        return true;
    }
    if (json.compare(i, 5, "false") == 0) {
        out = false;
        return true;
    }
    return false;
}

static bool m08eParsePlainNumberArray(const std::string& arrJson, std::vector<double>& out);

static void m08eReadPoint(const std::string& json, const char* key,
                          double dx, double dy, double dz, AcGePoint3d& out)
{
    std::string obj;
    if (jsonFindObject(json, key, obj)) {
        double x = dx, y = dy, z = dz;
        jsonFindNumber(obj, "x", x);
        jsonFindNumber(obj, "y", y);
        jsonFindNumber(obj, "z", z);
        out.set(x, y, z);
        return;
    }
    size_t lb = 0, rb = 0;
    if (m08eFindArrayBounds(json, key, lb, rb)) {
        std::vector<double> nums;
        if (m08eParsePlainNumberArray(json.substr(lb, rb - lb + 1), nums) && nums.size() >= 2) {
            out.set(nums[0], nums[1], nums.size() > 2 ? nums[2] : 0.0);
            return;
        }
    }
    out.set(dx, dy, dz);
}

static void m08eReadVector(const std::string& json, const char* key,
                           double dx, double dy, double dz, AcGeVector3d& out)
{
    std::string obj;
    if (jsonFindObject(json, key, obj)) {
        double x = dx, y = dy, z = dz;
        jsonFindNumber(obj, "x", x);
        jsonFindNumber(obj, "y", y);
        jsonFindNumber(obj, "z", z);
        out.set(x, y, z);
        return;
    }
    size_t lb = 0, rb = 0;
    if (m08eFindArrayBounds(json, key, lb, rb)) {
        std::vector<double> nums;
        if (m08eParsePlainNumberArray(json.substr(lb, rb - lb + 1), nums) && nums.size() >= 2) {
            out.set(nums[0], nums[1], nums.size() > 2 ? nums[2] : 0.0);
            return;
        }
    }
    out.set(dx, dy, dz);
}

static bool m08eParsePlainNumberArray(const std::string& arrJson, std::vector<double>& out)
{
    out.clear();
    const size_t lb = arrJson.find('[');
    if (lb == std::string::npos)
        return false;
    const size_t rb = m08eFindMatchingJsonDelimiter(arrJson, lb, '[', ']');
    if (rb == std::string::npos)
        return false;
    size_t i = lb + 1;
    while (i < rb) {
        while (i < rb && (arrJson[i] == ',' || m08eIsJsonSpace(arrJson[i])))
            ++i;
        if (i >= rb)
            break;
        char* parseEnd = nullptr;
        const double value = strtod(arrJson.c_str() + i, &parseEnd);
        if (parseEnd == arrJson.c_str() + i)
            return false;
        out.push_back(value);
        i = static_cast<size_t>(parseEnd - arrJson.c_str());
    }
    return true;
}

static bool m08eReadNumberTupleField(const std::string& json, const char* key,
                                     std::vector<double>& out)
{
    size_t lb = 0, rb = 0;
    if (!m08eFindArrayBounds(json, key, lb, rb))
        return false;
    return m08eParsePlainNumberArray(json.substr(lb, rb - lb + 1), out);
}

static bool m08eTryReadPoint(const std::string& json, const char* key, AcGePoint3d& out)
{
    std::string obj;
    if (jsonFindObject(json, key, obj)) {
        double x = 0.0, y = 0.0, z = 0.0;
        if (!parsePointFromObject(obj, x, y, z))
            return false;
        out.set(x, y, z);
        return true;
    }
    std::vector<double> nums;
    if (!m08eReadNumberTupleField(json, key, nums) || nums.size() < 2)
        return false;
    out.set(nums[0], nums[1], nums.size() > 2 ? nums[2] : 0.0);
    return true;
}

static bool m08eTryReadVector(const std::string& json, const char* key, AcGeVector3d& out)
{
    std::string obj;
    if (jsonFindObject(json, key, obj)) {
        double x = 0.0, y = 0.0, z = 0.0;
        if (!parsePointFromObject(obj, x, y, z))
            return false;
        out.set(x, y, z);
        return true;
    }
    std::vector<double> nums;
    if (!m08eReadNumberTupleField(json, key, nums) || nums.size() < 2)
        return false;
    out.set(nums[0], nums[1], nums.size() > 2 ? nums[2] : 0.0);
    return true;
}

static bool m08eTryReadPoint2d(const std::string& json, const char* key, AcGePoint2d& out)
{
    std::vector<double> nums;
    if (!m08eReadNumberTupleField(json, key, nums) || nums.size() < 2)
        return false;
    out = AcGePoint2d(nums[0], nums[1]);
    return true;
}

static bool m08eTryReadVector2d(const std::string& json, const char* key, AcGeVector2d& out)
{
    std::vector<double> nums;
    if (!m08eReadNumberTupleField(json, key, nums) || nums.size() < 2)
        return false;
    out = AcGeVector2d(nums[0], nums[1]);
    return true;
}

static bool m08eReadPoint2dArrayField(const std::string& json, const char* key, AcGePoint2dArray& out)
{
    out.removeAll();
    size_t lb = 0, rb = 0;
    if (!m08eFindArrayBounds(json, key, lb, rb))
        return false;
    size_t scan = lb + 1;
    while (scan < rb) {
        while (scan < rb && (json[scan] == ',' || m08eIsJsonSpace(json[scan])))
            ++scan;
        if (scan >= rb)
            break;
        if (json[scan] != '[')
            return false;
        const size_t pe = m08eFindMatchingJsonDelimiter(json, scan, '[', ']');
        if (pe == std::string::npos || pe > rb)
            return false;
        std::vector<double> nums;
        if (!m08eParsePlainNumberArray(json.substr(scan, pe - scan + 1), nums) || nums.size() < 2)
            return false;
        out.append(AcGePoint2d(nums[0], nums[1]));
        scan = pe + 1;
    }
    return out.length() > 0;
}

static bool m08eReadFlagArray(const std::string& json, const char* key, std::vector<bool>& out)
{
    out.clear();
    size_t lb = 0, rb = 0;
    if (!m08eFindArrayBounds(json, key, lb, rb))
        return false;
    size_t scan = lb + 1;
    while (scan < rb) {
        while (scan < rb && (json[scan] == ',' || m08eIsJsonSpace(json[scan])))
            ++scan;
        if (scan >= rb)
            break;
        if (json.compare(scan, 4, "true") == 0) {
            out.push_back(true);
            scan += 4;
            continue;
        }
        if (json.compare(scan, 5, "false") == 0) {
            out.push_back(false);
            scan += 5;
            continue;
        }
        char* parseEnd = nullptr;
        const double raw = strtod(json.c_str() + scan, &parseEnd);
        if (parseEnd == json.c_str() + scan)
            return false;
        out.push_back(raw != 0.0);
        scan = static_cast<size_t>(parseEnd - json.c_str());
    }
    return true;
}

static bool m08eReadPoint3dArray(const std::string& json, const char* key, AcGePoint3dArray& out)
{
    out.removeAll();
    size_t lb = 0, rb = 0;
    if (!m08eFindArrayBounds(json, key, lb, rb))
        return false;
    size_t scan = lb + 1;
    while (scan < rb) {
        while (scan < rb && (json[scan] == ',' || m08eIsJsonSpace(json[scan])))
            ++scan;
        if (scan >= rb)
            break;
        if (json[scan] == '{') {
            const size_t oe = m08eFindMatchingJsonDelimiter(json, scan, '{', '}');
            if (oe == std::string::npos || oe > rb)
                return false;
            const std::string one = json.substr(scan, oe - scan + 1);
            double x = 0.0, y = 0.0, z = 0.0;
            if (!parsePointFromObject(one, x, y, z))
                return false;
            out.append(AcGePoint3d(x, y, z));
            scan = oe + 1;
            continue;
        }
        if (json[scan] == '[') {
            const size_t ae = m08eFindMatchingJsonDelimiter(json, scan, '[', ']');
            if (ae == std::string::npos || ae > rb)
                return false;
            std::vector<double> nums;
            if (!m08eParsePlainNumberArray(json.substr(scan, ae - scan + 1), nums) || nums.size() < 2)
                return false;
            out.append(AcGePoint3d(nums[0], nums[1], nums.size() > 2 ? nums[2] : 0.0));
            scan = ae + 1;
            continue;
        }
        return false;
    }
    return true;
}

struct M08eVertex2d
{
    double x = 0.0;
    double y = 0.0;
    double bulge = 0.0;
    double startWidth = 0.0;
    double endWidth = 0.0;
};

static bool m08eReadVertex2dArray(const std::string& json, const char* key,
                                  bool includeWidths, std::vector<M08eVertex2d>& out)
{
    out.clear();
    size_t lb = 0, rb = 0;
    if (!m08eFindArrayBounds(json, key, lb, rb))
        return false;
    size_t scan = lb + 1;
    while (scan < rb) {
        while (scan < rb && (json[scan] == ',' || m08eIsJsonSpace(json[scan])))
            ++scan;
        if (scan >= rb)
            break;
        if (json[scan] != '{')
            return false;
        const size_t oe = m08eFindMatchingJsonDelimiter(json, scan, '{', '}');
        if (oe == std::string::npos || oe > rb)
            return false;
        const std::string one = json.substr(scan, oe - scan + 1);
        M08eVertex2d v;
        if (!jsonFindNumber(one, "x", v.x) || !jsonFindNumber(one, "y", v.y))
            return false;
        jsonFindNumber(one, "bulge", v.bulge);
        if (includeWidths) {
            jsonFindNumber(one, "start_width", v.startWidth);
            jsonFindNumber(one, "end_width", v.endWidth);
        }
        out.push_back(v);
        scan = oe + 1;
    }
    return true;
}

static bool m08eLoadWipeoutModule()
{
    static bool attempted = false;
    static bool loaded = false;
    if (!attempted) {
        attempted = true;
        // loadModule returns bool (true=loaded), NOT Acad::ErrorStatus.
        // Comparing to eOk(=0) inverted the gate: a successful load (true=1)
        // reported WIPEOUT_MODULE_UNAVAILABLE (live-measured, R4l cert run).
        loaded = (acrxDynamicLinker != nullptr &&
                  acrxDynamicLinker->loadModule(L"acismobj26.dbx", false));
    }
    return loaded;
}

static bool m08eEnsureWipeoutImageDef(AcDbDatabase* pDb,
                                      AcDbObjectId& defId,
                                      std::string& errCode,
                                      std::string& errMsg)
{
    defId = AcDbObjectId::kNull;
    if (!m08eLoadWipeoutModule()) {
        errCode = "WIPEOUT_MODULE_UNAVAILABLE";
        errMsg = "acismobj26.dbx could not be loaded for AcDbWipeout";
        return false;
    }

    AcDbObjectId dictId = AcDbRasterImageDef::imageDictionary(pDb);
    Acad::ErrorStatus es = Acad::eOk;
    if (dictId.isNull())
        es = AcDbRasterImageDef::createImageDictionary(pDb, dictId);
    if (es != Acad::eOk || dictId.isNull()) {
        errCode = "WIPEOUT_DICT_FAILED";
        errMsg = "ACAD_IMAGE_DICT createImageDictionary errorstatus " +
                 std::to_string(static_cast<int>(es));
        return false;
    }

    AcDbDictionary* pDict = nullptr;
    es = acdbOpenObject(pDict, dictId, AcDb::kForWrite);
    if (es != Acad::eOk || pDict == nullptr) {
        errCode = "WIPEOUT_DICT_OPEN_FAILED";
        errMsg = "could not open ACAD_IMAGE_DICT errorstatus " +
                 std::to_string(static_cast<int>(es));
        return false;
    }

    const wchar_t* key = L"ARIADNE_WIPEOUT_DEF";
    es = pDict->getAt(key, defId);
    if (es == Acad::eOk && !defId.isNull()) {
        pDict->close();
        return true;
    }
    if (es != Acad::eKeyNotFound) {
        pDict->close();
        errCode = "WIPEOUT_DEF_FAILED";
        errMsg = "ARIADNE_WIPEOUT_DEF lookup errorstatus " +
                 std::to_string(static_cast<int>(es));
        return false;
    }

    AcDbRasterImageDef* pDef = new AcDbRasterImageDef();
    es = pDict->setAt(key, pDef, defId);
    pDict->close();
    if (es == Acad::eOk) {
        pDef->close();
        return true;
    }

    delete pDef;
    errCode = "WIPEOUT_DEF_FAILED";
    errMsg = "ARIADNE_WIPEOUT_DEF setAt errorstatus " +
             std::to_string(static_cast<int>(es));
    return false;
}

struct M08eHatchLoop
{
    Adesk::Int32 loopType = 0;
    bool hasEdges = false;
    AcGePoint2dArray vertices;
    AcGeDoubleArray bulges;
    AcGeVoidPointerArray edgePtrs;
    AcGeIntArray edgeTypes;
};

enum M08eHatchLoopReadStatus
{
    kM08eHatchLoopReadOk = 0,
    kM08eHatchLoopReadMissing,
    kM08eHatchLoopReadMalformedEdge,
};

static void m08eReleaseHatchLoop(M08eHatchLoop& loop)
{
    for (int i = 0; i < loop.edgePtrs.length(); ++i) {
        AcGeCurve2d* curve = static_cast<AcGeCurve2d*>(loop.edgePtrs[i]);
        if (curve == nullptr)
            continue;
        const int edgeType = (i < loop.edgeTypes.length()) ? loop.edgeTypes[i] : -1;
        switch (edgeType) {
        case AcDbHatch::kLine:
            delete static_cast<AcGeLineSeg2d*>(curve);
            break;
        case AcDbHatch::kCirArc:
            delete static_cast<AcGeCircArc2d*>(curve);
            break;
        case AcDbHatch::kEllArc:
            delete static_cast<AcGeEllipArc2d*>(curve);
            break;
        case AcDbHatch::kSpline:
            delete static_cast<AcGeNurbCurve2d*>(curve);
            break;
        default:
            break;
        }
    }
    loop.edgePtrs.removeAll();
    loop.edgeTypes.removeAll();
    loop.vertices.removeAll();
    loop.bulges.removeAll();
    loop.hasEdges = false;
}

static void m08eReleaseHatchLoops(std::vector<M08eHatchLoop>& loops)
{
    for (size_t i = 0; i < loops.size(); ++i)
        m08eReleaseHatchLoop(loops[i]);
    loops.clear();
}

static bool m08eReadHatchPolylineLoop(const std::string& loopJson, M08eHatchLoop& loop)
{
    loop.vertices.removeAll();
    loop.bulges.removeAll();
    size_t vlb = 0, vrb = 0;
    if (!m08eFindArrayBounds(loopJson, "vertices", vlb, vrb))
        return false;
    size_t vscan = vlb + 1;
    while (vscan < vrb) {
        while (vscan < vrb && (loopJson[vscan] == ',' || m08eIsJsonSpace(loopJson[vscan])))
            ++vscan;
        if (vscan >= vrb)
            break;
        if (loopJson[vscan] != '{') {
            loop.vertices.removeAll();
            loop.bulges.removeAll();
            return false;
        }
        const size_t voe = m08eFindMatchingJsonDelimiter(loopJson, vscan, '{', '}');
        if (voe == std::string::npos || voe > vrb) {
            loop.vertices.removeAll();
            loop.bulges.removeAll();
            return false;
        }
        const std::string vertexJson = loopJson.substr(vscan, voe - vscan + 1);
        std::vector<double> pointNums;
        if (!m08eReadNumberTupleField(vertexJson, "point", pointNums) || pointNums.size() < 2) {
            loop.vertices.removeAll();
            loop.bulges.removeAll();
            return false;
        }
        double bulge = 0.0;
        jsonFindNumber(vertexJson, "bulge", bulge);
        loop.vertices.append(AcGePoint2d(pointNums[0], pointNums[1]));
        loop.bulges.append(bulge);
        vscan = voe + 1;
    }
    if (loop.vertices.length() < 2) {
        loop.vertices.removeAll();
        loop.bulges.removeAll();
        return false;
    }
    loop.hasEdges = false;
    return true;
}

static bool m08eReadHatchEdge(const std::string& edgeJson, void*& edgePtr, Adesk::Int32& edgeType)
{
    edgePtr = nullptr;
    edgeType = 0;

    std::string edgeKind;
    if (!jsonFindString(edgeJson, "type", edgeKind) || edgeKind.empty())
        return false;

    if (edgeKind == "line") {
        AcGePoint2d start, end;
        if (!m08eTryReadPoint2d(edgeJson, "start", start) ||
            !m08eTryReadPoint2d(edgeJson, "end", end)) {
            return false;
        }
        edgePtr = static_cast<void*>(new AcGeLineSeg2d(start, end));
        edgeType = AcDbHatch::kLine;
        return true;
    }

    if (edgeKind == "arc") {
        AcGePoint2d center;
        double radius = 0.0, startAngle = 0.0, endAngle = 0.0;
        bool ccw = false;
        if (!m08eTryReadPoint2d(edgeJson, "center", center) ||
            !jsonFindNumber(edgeJson, "radius", radius) ||
            !jsonFindNumber(edgeJson, "start_angle", startAngle) ||
            !jsonFindNumber(edgeJson, "end_angle", endAngle) ||
            !m08eFindFlag(edgeJson, "ccw", ccw) ||
            radius <= 0.0) {
            return false;
        }
        edgePtr = static_cast<void*>(new AcGeCircArc2d(
            center,
            radius,
            startAngle,
            endAngle,
            AcGeVector2d::kXAxis,
            ccw ? Adesk::kFalse : Adesk::kTrue));
        edgeType = AcDbHatch::kCirArc;
        return true;
    }

    if (edgeKind == "ellipse") {
        AcGePoint2d center;
        AcGeVector2d major;
        double ratio = 0.0, startAngle = 0.0, endAngle = 0.0;
        bool ccw = false;
        if (!m08eTryReadPoint2d(edgeJson, "center", center) ||
            !m08eTryReadVector2d(edgeJson, "major", major) ||
            !jsonFindNumber(edgeJson, "ratio", ratio) ||
            !jsonFindNumber(edgeJson, "start_angle", startAngle) ||
            !jsonFindNumber(edgeJson, "end_angle", endAngle) ||
            !m08eFindFlag(edgeJson, "ccw", ccw) ||
            ratio <= 0.0) {
            return false;
        }
        const double majorRadius = major.length();
        if (majorRadius <= 0.0)
            return false;
        const double minorRadius = majorRadius * ratio;
        if (minorRadius <= 0.0)
            return false;
        const AcGeVector2d majorAxisUnit(major.x / majorRadius, major.y / majorRadius);
        const AcGeVector2d minorAxisUnit = ccw
            ? AcGeVector2d(-majorAxisUnit.y, majorAxisUnit.x)
            : AcGeVector2d(majorAxisUnit.y, -majorAxisUnit.x);
        edgePtr = static_cast<void*>(new AcGeEllipArc2d(
            center,
            majorAxisUnit,
            minorAxisUnit,
            majorRadius,
            minorRadius,
            startAngle,
            endAngle));
        edgeType = AcDbHatch::kEllArc;
        return true;
    }

    if (edgeKind == "spline") {
        double degreeRaw = 0.0;
        bool rational = false;
        AcGePoint2dArray control;
        if (!jsonFindNumber(edgeJson, "degree", degreeRaw) ||
            !m08eFindFlag(edgeJson, "rational", rational) ||
            !m08eReadPoint2dArrayField(edgeJson, "control", control)) {
            return false;
        }
        const int degree = static_cast<int>(degreeRaw);
        if (degree < 1)
            return false;
        const std::vector<double> knotVals = jsonFindNumberArray(edgeJson, "knots");
        if (knotVals.empty())
            return false;
        AcGeKnotVector knots;
        for (size_t i = 0; i < knotVals.size(); ++i)
            knots.append(knotVals[i]);
        if (rational) {
            const std::vector<double> weightVals = jsonFindNumberArray(edgeJson, "weights");
            if (weightVals.size() != static_cast<size_t>(control.length()))
                return false;
            AcGeDoubleArray weights;
            for (size_t i = 0; i < weightVals.size(); ++i)
                weights.append(weightVals[i]);
            edgePtr = static_cast<void*>(new AcGeNurbCurve2d(
                degree, knots, control, weights, Adesk::kFalse));
        } else {
            edgePtr = static_cast<void*>(new AcGeNurbCurve2d(
                degree, knots, control, Adesk::kFalse));
        }
        edgeType = AcDbHatch::kSpline;
        return true;
    }

    return false;
}

static M08eHatchLoopReadStatus m08eReadHatchEdgeLoop(const std::string& loopJson, M08eHatchLoop& loop)
{
    size_t elb = 0, erb = 0;
    if (!m08eFindArrayBounds(loopJson, "edges", elb, erb))
        return kM08eHatchLoopReadMissing;

    loop.hasEdges = true;
    loop.edgePtrs.removeAll();
    loop.edgeTypes.removeAll();
    size_t escan = elb + 1;
    while (escan < erb) {
        while (escan < erb && (loopJson[escan] == ',' || m08eIsJsonSpace(loopJson[escan])))
            ++escan;
        if (escan >= erb)
            break;
        if (loopJson[escan] != '{') {
            m08eReleaseHatchLoop(loop);
            return kM08eHatchLoopReadMalformedEdge;
        }
        const size_t eoe = m08eFindMatchingJsonDelimiter(loopJson, escan, '{', '}');
        if (eoe == std::string::npos || eoe > erb) {
            m08eReleaseHatchLoop(loop);
            return kM08eHatchLoopReadMalformedEdge;
        }
        const std::string edgeJson = loopJson.substr(escan, eoe - escan + 1);
        void* edgePtr = nullptr;
        Adesk::Int32 edgeType = 0;
        if (!m08eReadHatchEdge(edgeJson, edgePtr, edgeType)) {
            m08eReleaseHatchLoop(loop);
            return kM08eHatchLoopReadMalformedEdge;
        }
        loop.edgePtrs.append(edgePtr);
        loop.edgeTypes.append(edgeType);
        escan = eoe + 1;
    }
    if (loop.edgePtrs.length() < 1) {
        m08eReleaseHatchLoop(loop);
        return kM08eHatchLoopReadMalformedEdge;
    }
    return kM08eHatchLoopReadOk;
}

static M08eHatchLoopReadStatus m08eReadHatchLoops(const std::string& json, std::vector<M08eHatchLoop>& out)
{
    out.clear();
    size_t lb = 0, rb = 0;
    if (!m08eFindArrayBounds(json, "loops", lb, rb))
        return kM08eHatchLoopReadMissing;
    size_t scan = lb + 1;
    while (scan < rb) {
        while (scan < rb && (json[scan] == ',' || m08eIsJsonSpace(json[scan])))
            ++scan;
        if (scan >= rb)
            break;
        if (json[scan] != '{') {
            m08eReleaseHatchLoops(out);
            return kM08eHatchLoopReadMissing;
        }
        const size_t oe = m08eFindMatchingJsonDelimiter(json, scan, '{', '}');
        if (oe == std::string::npos || oe > rb) {
            m08eReleaseHatchLoops(out);
            return kM08eHatchLoopReadMissing;
        }
        const std::string loopJson = json.substr(scan, oe - scan + 1);
        double loopTypeRaw = 0.0;
        if (!jsonFindNumber(loopJson, "loop_type", loopTypeRaw)) {
            m08eReleaseHatchLoops(out);
            return kM08eHatchLoopReadMissing;
        }
        M08eHatchLoop loop;
        loop.loopType = static_cast<Adesk::Int32>(loopTypeRaw);
        if (m08eReadHatchPolylineLoop(loopJson, loop)) {
            out.push_back(loop);
            scan = oe + 1;
            continue;
        }

        const M08eHatchLoopReadStatus edgeStatus = m08eReadHatchEdgeLoop(loopJson, loop);
        if (edgeStatus == kM08eHatchLoopReadOk) {
            out.push_back(loop);
            scan = oe + 1;
            continue;
        }
        if (edgeStatus == kM08eHatchLoopReadMalformedEdge) {
            m08eReleaseHatchLoops(out);
            return kM08eHatchLoopReadMalformedEdge;
        }
        m08eReleaseHatchLoops(out);
        return kM08eHatchLoopReadMissing;
    }
    if (out.empty())
        return kM08eHatchLoopReadMissing;
    return kM08eHatchLoopReadOk;
}

static bool m08eFileExists(const std::wstring& path)
{
    const DWORD attrs = GetFileAttributesW(path.c_str());
    return attrs != INVALID_FILE_ATTRIBUTES && !(attrs & FILE_ATTRIBUTE_DIRECTORY);
}

static bool m08eCurrentWorkingDirectory(std::wstring& outDir)
{
    outDir.clear();
    const DWORD needed = GetCurrentDirectoryW(0, nullptr);
    if (needed == 0)
        return false;
    std::wstring buf(static_cast<size_t>(needed), L'\0');
    const DWORD got = GetCurrentDirectoryW(needed, &buf[0]);
    if (got == 0 || got >= needed)
        return false;
    buf.resize(static_cast<size_t>(got));
    outDir = buf;
    return true;
}

static std::wstring m08eJoinPath(const std::wstring& dir, const std::wstring& leaf)
{
    if (dir.empty())
        return leaf;
    const wchar_t last = dir[dir.size() - 1];
    if (last == L'\\' || last == L'/')
        return dir + leaf;
    return dir + L"\\" + leaf;
}

static bool m08eEnsureCustomPatDiscoverable(const std::string& patternName,
                                            const std::string& patternPatPathUtf8,
                                            std::string& errMsg)
{
    errMsg.clear();
    const std::wstring sourcePath = utf8ToWide(patternPatPathUtf8);
    if (sourcePath.empty()) {
        errMsg = "entity.kind=hatch custom pattern '" + patternName + "' requires 'pattern_pat_path'";
        return false;
    }
    if (!m08eFileExists(sourcePath)) {
        errMsg = "entity.kind=hatch custom pattern '" + patternName + "' missing source pat '"
               + patternPatPathUtf8 + "'";
        return false;
    }

    std::wstring cwd;
    if (!m08eCurrentWorkingDirectory(cwd)) {
        errMsg = "entity.kind=hatch custom pattern '" + patternName
               + "' could not resolve accoreconsole working directory";
        return false;
    }

    const size_t slash = sourcePath.find_last_of(L"\\/");
    const std::wstring leaf = (slash == std::wstring::npos)
        ? sourcePath
        : sourcePath.substr(slash + 1);
    const std::wstring stagedPath = m08eJoinPath(cwd, leaf);
    if (lstrcmpiW(sourcePath.c_str(), stagedPath.c_str()) == 0)
        return true;

    if (!CopyFileW(sourcePath.c_str(), stagedPath.c_str(), FALSE)) {
        const DWORD copyErr = GetLastError();
        errMsg = "entity.kind=hatch custom pattern '" + patternName + "' copy failed from '"
               + patternPatPathUtf8 + "' to '" + wideToUtf8(stagedPath) + "' win32="
               + std::to_string(static_cast<unsigned long>(copyErr));
        return false;
    }
    return true;
}

static void m08eReadScaleFactors(const std::string& json, AcGeScale3d& out)
{
    double sx = 1.0, sy = 1.0, sz = 1.0;
    std::string scaleJson;
    if (jsonFindObject(json, "scale", scaleJson)) {
        jsonFindNumber(scaleJson, "x", sx);
        jsonFindNumber(scaleJson, "y", sy);
        jsonFindNumber(scaleJson, "z", sz);
    } else {
        double uniform = 1.0;
        if (jsonFindNumber(json, "scale", uniform))
            sx = sy = sz = uniform;
    }
    out = AcGeScale3d(sx, sy, sz);
}

static AcDbEntity* m08eBuildExtendedEntityForAppend(AcDbDatabase* pDb,
                                                    const std::string& entityJson,
                                                    const std::string& kind,
                                                    std::string& errCode,
                                                    std::string& errMsg)
{
    if (kind == "ellipse") {
        AcGePoint3d center; m08eReadPoint(entityJson, "center", 0.0, 0.0, 0.0, center);
        AcGeVector3d normal; m08eReadVector(entityJson, "normal", 0.0, 0.0, 1.0, normal);
        AcGeVector3d major; m08eReadVector(entityJson, "major_axis", 1.0, 0.0, 0.0, major);
        double ratio = 1.0, sa = 0.0, ea = 6.28318530717958647692;
        jsonFindNumber(entityJson, "radius_ratio", ratio);
        jsonFindNumber(entityJson, "start_angle", sa);
        jsonFindNumber(entityJson, "end_angle", ea);
        return new AcDbEllipse(center, normal, major, ratio, sa, ea);
    }
    if (kind == "point") {
        AcGePoint3d pos; m08eReadPoint(entityJson, "position", 0.0, 0.0, 0.0, pos);
        return new AcDbPoint(pos);
    }
    if (kind == "spline") {
        AcGePoint3dArray fitPts;
        AcGePoint3dArray controlPts;
        const bool hasFitPoints = m08eReadPoint3dArray(entityJson, "fit_points", fitPts);
        const bool hasControlPoints = m08eReadPoint3dArray(entityJson, "control_points", controlPts);
        std::vector<double> knotVals = jsonFindNumberArray(entityJson, "knots");
        if (knotVals.empty())
            knotVals = jsonFindNumberArray(entityJson, "spline_knots");
        const std::vector<double> weightVals = jsonFindNumberArray(entityJson, "weights");
        double degreeRaw = 3.0;
        jsonFindNumber(entityJson, "degree", degreeRaw);
        int degree = static_cast<int>(degreeRaw);
        if (degree < 1)
            degree = 3;
        bool closed = false;
        m08eFindFlag(entityJson, "closed", closed);

        if (hasControlPoints && controlPts.length() > 0 && !knotVals.empty()) {
            if (!weightVals.empty() && weightVals.size() != static_cast<size_t>(controlPts.length())) {
                errCode = "INVALID_INPUT";
                errMsg = "entity.kind=spline weights length must equal control_points length";
                return nullptr;
            }
            AcGeDoubleArray knots;
            for (size_t i = 0; i < knotVals.size(); ++i)
                knots.append(knotVals[i]);
            AcGeDoubleArray weights;
            for (size_t i = 0; i < weightVals.size(); ++i)
                weights.append(weightVals[i]);
            AcDbSpline* pSpline = new AcDbSpline();
            const Acad::ErrorStatus es = pSpline->setNurbsData(
                degree,
                weightVals.empty() ? Adesk::kFalse : Adesk::kTrue,
                closed ? Adesk::kTrue : Adesk::kFalse,
                Adesk::kFalse,
                controlPts,
                knots,
                weights,
                0.0,
                0.0);
            if (es != Acad::eOk) {
                delete pSpline;
                errCode = "BUILD_FAILED";
                errMsg = "entity.kind=spline setNurbsData errorstatus " +
                         std::to_string(static_cast<int>(es));
                return nullptr;
            }
            return pSpline;
        }
        if (!hasFitPoints || fitPts.length() < 2) {
            errCode = "MISSING_ARG";
            errMsg = (hasControlPoints && controlPts.length() > 0)
                ? "entity.kind=spline control_points require 'knots' for native append"
                : "entity.kind=spline requires 'fit_points':[>=2 [x,y,z]]";
            return nullptr;
        }
        if (closed)
            return new AcDbSpline(fitPts, true, AcGe::kUniform, degree, 0.0);
        int order = degree + 1;
        if (order < 2)
            order = 4;
        return new AcDbSpline(fitPts, order, 0.0);
    }
    if (kind == "lwpolyline") {
        std::vector<M08eVertex2d> verts;
        if (!m08eReadVertex2dArray(entityJson, "points", false, verts) || verts.size() < 2) {
            errCode = "MISSING_ARG";
            errMsg = "entity.kind=lwpolyline requires 'points':[>=2 {x,y}]";
            return nullptr;
        }
        AcDbPolyline* pPoly = new AcDbPolyline();
        for (size_t i = 0; i < verts.size(); ++i) {
            const Acad::ErrorStatus es = pPoly->addVertexAt(
                static_cast<unsigned int>(i),
                AcGePoint2d(verts[i].x, verts[i].y),
                verts[i].bulge);
            if (es != Acad::eOk) {
                delete pPoly;
                errCode = "BUILD_FAILED";
                errMsg = "entity.kind=lwpolyline addVertexAt errorstatus " +
                         std::to_string(static_cast<int>(es));
                return nullptr;
            }
        }
        bool closed = false;
        if (m08eFindFlag(entityJson, "closed", closed) && closed)
            pPoly->setClosed(Adesk::kTrue);
        double constWidth = 0.0;
        if (jsonFindNumber(entityJson, "const_width", constWidth)) {
            const Acad::ErrorStatus es = pPoly->setConstantWidth(constWidth);
            if (es != Acad::eOk) {
                delete pPoly;
                errCode = "BUILD_FAILED";
                errMsg = "entity.kind=lwpolyline setConstantWidth errorstatus " +
                         std::to_string(static_cast<int>(es));
                return nullptr;
            }
        }
        // OCS elevation: the census bakes it into every vertex z and the job
        // carries the common value as 'elevation' (R4s measured 25 pairs
        // flattened to 0 without this; patch_ops/blocks.py _common_vertex_z).
        // AcDbPolyline::setElevation returns void (unlike AcDb2dPolyline's).
        double elevation = 0.0;
        if (jsonFindNumber(entityJson, "elevation", elevation) && elevation != 0.0)
            pPoly->setElevation(elevation);
        return pPoly;
    }
    if (kind == "block_reference") {
        std::string blockName;
        if (!jsonFindString(entityJson, "block_name", blockName) || blockName.empty()) {
            errCode = "MISSING_ARG";
            errMsg = "entity.kind=block_reference requires 'block_name'";
            return nullptr;
        }
        AcDbBlockTable* pBT = nullptr;
        Acad::ErrorStatus es = pDb->getBlockTable(pBT, AcDb::kForRead);
        if (es != Acad::eOk || pBT == nullptr) {
            errCode = "BLOCK_TABLE_OPEN_FAILED";
            errMsg = "could not open the block table";
            return nullptr;
        }
        AcDbObjectId blockId = AcDbObjectId::kNull;
        es = pBT->getAt(asciiToWide(blockName).c_str(), blockId);
        pBT->close();
        if (es != Acad::eOk || blockId.isNull()) {
            errCode = "BLOCK_NOT_FOUND";
            errMsg = "no block definition named '" + blockName + "'";
            return nullptr;
        }

        AcGePoint3d pos; m08eReadPoint(entityJson, "position", 0.0, 0.0, 0.0, pos);
        AcGeScale3d scale;
        m08eReadScaleFactors(entityJson, scale);
        double rotation = 0.0;
        jsonFindNumber(entityJson, "rotation", rotation);

        AcDbBlockReference* pRef = new AcDbBlockReference(pos, blockId);
        es = pRef->setScaleFactors(scale);
        if (es != Acad::eOk) {
            delete pRef;
            errCode = "BUILD_FAILED";
            errMsg = "entity.kind=block_reference setScaleFactors errorstatus " +
                     std::to_string(static_cast<int>(es));
            return nullptr;
        }
        es = pRef->setRotation(rotation);
        if (es != Acad::eOk) {
            delete pRef;
            errCode = "BUILD_FAILED";
            errMsg = "entity.kind=block_reference setRotation errorstatus " +
                     std::to_string(static_cast<int>(es));
            return nullptr;
        }
        return pRef;
    }
    if (kind == "wipeout") {
        AcDbObjectId defId = AcDbObjectId::kNull;
        if (!m08eEnsureWipeoutImageDef(pDb, defId, errCode, errMsg))
            return nullptr;

        AcGePoint3d origin;
        m08eReadPoint(entityJson, "origin", 0.0, 0.0, 0.0, origin);
        AcGeVector3d uVec;
        m08eReadVector(entityJson, "u_vector", 1.0, 0.0, 0.0, uVec);
        AcGeVector3d vVec;
        m08eReadVector(entityJson, "v_vector", 0.0, 1.0, 0.0, vVec);

        AcGePoint2dArray clipBoundary;
        if (!m08eReadPoint2dArrayField(entityJson, "clip_boundary", clipBoundary) ||
            clipBoundary.length() < 3) {
            errCode = "MISSING_ARG";
            errMsg = "entity.kind=wipeout requires 'clip_boundary':[>=3 [x,y]]";
            return nullptr;
        }
        const AcGePoint2d firstClipPoint = clipBoundary[0];
        const AcGePoint2d lastClipPoint = clipBoundary[clipBoundary.length() - 1];
        if (firstClipPoint.x != lastClipPoint.x || firstClipPoint.y != lastClipPoint.y)
            clipBoundary.append(firstClipPoint);

        double clipTypeRaw = static_cast<double>(AcDbRasterImage::kPoly);
        jsonFindNumber(entityJson, "clip_boundary_type", clipTypeRaw);
        AcDbRasterImage::ClipBoundaryType clipType =
            static_cast<AcDbRasterImage::ClipBoundaryType>(static_cast<int>(clipTypeRaw));

        AcDbWipeout* pWipe = new AcDbWipeout();
        pWipe->setDatabaseDefaults(pDb);
        Acad::ErrorStatus es = pWipe->setImageDefId(defId);
        if (es != Acad::eOk) {
            delete pWipe;
            errCode = "WIPEOUT_IMAGEDEFID_FAILED";
            errMsg = "entity.kind=wipeout setImageDefId errorstatus " +
                     std::to_string(static_cast<int>(es));
            return nullptr;
        }
        if (!pWipe->setOrientation(origin, uVec, vVec)) {
            delete pWipe;
            errCode = "BUILD_FAILED";
            errMsg = "entity.kind=wipeout setOrientation failed";
            return nullptr;
        }
        es = pWipe->setClipBoundary(clipType, clipBoundary);
        if (es != Acad::eOk) {
            delete pWipe;
            errCode = "WIPEOUT_CLIP_FAILED";
            errMsg = "entity.kind=wipeout setClipBoundary errorstatus " +
                     std::to_string(static_cast<int>(es));
            return nullptr;
        }
        // frame_on has no public AcDbWipeout setter; preserve the default.
        return pWipe;
    }
    if (kind == "hatch") {
        bool isGradient = false;
        m08eFindFlag(entityJson, "is_gradient", isGradient);
        if (isGradient) {
            errCode = "INVALID_INPUT";
            errMsg = "entity.kind=hatch gradient replay is not supported";
            return nullptr;
        }

        AcGeVector3d normal(0.0, 0.0, 1.0);
        m08eTryReadVector(entityJson, "normal", normal);
        double elevation = 0.0;
        jsonFindNumber(entityJson, "elevation", elevation);
        double patternAngle = 0.0;
        jsonFindNumber(entityJson, "pattern_angle", patternAngle);
        double patternScale = 1.0;
        jsonFindNumber(entityJson, "pattern_scale", patternScale);
        double hatchStyleRaw = static_cast<double>(AcDbHatch::kNormal);
        jsonFindNumber(entityJson, "hatch_style", hatchStyleRaw);
        bool patternDouble = false;
        m08eFindFlag(entityJson, "pattern_double", patternDouble);
        bool isSolidFill = false;
        m08eFindFlag(entityJson, "is_solid_fill", isSolidFill);

        std::string patternName;
        if (!jsonFindString(entityJson, "pattern_name", patternName) || patternName.empty()) {
            errCode = "MISSING_ARG";
            errMsg = "entity.kind=hatch requires 'pattern_name'";
            return nullptr;
        }
        std::string patternPatPath;
        const bool hasPatternPatPath =
            jsonFindString(entityJson, "pattern_pat_path", patternPatPath) && !patternPatPath.empty();

        AcDbHatch* pHatch = new AcDbHatch();
        pHatch->setDatabaseDefaults(pDb);
        Acad::ErrorStatus es = pHatch->setNormal(normal);
        if (es != Acad::eOk) {
            delete pHatch;
            errCode = "BUILD_FAILED";
            errMsg = "entity.kind=hatch setNormal errorstatus " + std::to_string(static_cast<int>(es));
            return nullptr;
        }
        es = pHatch->setElevation(elevation);
        if (es != Acad::eOk) {
            delete pHatch;
            errCode = "BUILD_FAILED";
            errMsg = "entity.kind=hatch setElevation errorstatus " + std::to_string(static_cast<int>(es));
            return nullptr;
        }
        if (isSolidFill) {
            es = pHatch->setPattern(AcDbHatch::kPreDefined, L"SOLID");
        } else if (hasPatternPatPath) {
            std::string customPatErr;
            // The router copies the batch .scr into its staged DWG directory and
            // launches accoreconsole with that directory as the working dir.
            // setPattern(kCustomDefined, name) resolves <name>.pat through that cwd,
            // so stage the synthesized batch artifact there before resolving.
            if (!m08eEnsureCustomPatDiscoverable(patternName, patternPatPath, customPatErr)) {
                delete pHatch;
                errCode = "HATCH_CUSTOM_PAT_UNRESOLVED";
                errMsg = customPatErr;
                return nullptr;
            }
            es = pHatch->setPattern(AcDbHatch::kCustomDefined, utf8ToWide(patternName).c_str());
        } else {
            es = pHatch->setPattern(AcDbHatch::kPreDefined, utf8ToWide(patternName).c_str());
        }
        if (es != Acad::eOk) {
            delete pHatch;
            if (hasPatternPatPath) {
                errCode = "HATCH_CUSTOM_PAT_UNRESOLVED";
                errMsg = "entity.kind=hatch custom pattern '" + patternName + "' unresolved from '"
                       + patternPatPath + "' errorstatus " + std::to_string(static_cast<int>(es));
            } else {
                errCode = "BUILD_FAILED";
                errMsg = "entity.kind=hatch setPattern errorstatus " + std::to_string(static_cast<int>(es));
            }
            return nullptr;
        }
        if (!isSolidFill) {
            es = pHatch->setPatternAngle(patternAngle);
            if (es != Acad::eOk) {
                delete pHatch;
                errCode = "BUILD_FAILED";
                errMsg = "entity.kind=hatch setPatternAngle errorstatus " + std::to_string(static_cast<int>(es));
                return nullptr;
            }
            es = pHatch->setPatternScale(patternScale);
            if (es != Acad::eOk) {
                delete pHatch;
                errCode = "BUILD_FAILED";
                errMsg = "entity.kind=hatch setPatternScale errorstatus " + std::to_string(static_cast<int>(es));
                return nullptr;
            }
            es = pHatch->setPatternDouble(patternDouble);
            if (es != Acad::eOk) {
                delete pHatch;
                errCode = "BUILD_FAILED";
                errMsg = "entity.kind=hatch setPatternDouble errorstatus " + std::to_string(static_cast<int>(es));
                return nullptr;
            }
            // Optional per-hatch pattern origin (HPORIGIN). R4l residue: 21/22
            // boundary-paired custom hatches mismatched only in the per-hatch
            // pattern phase -- the originals carry per-hatch origins, the .pat
            // replay shares one base. Fail-loud: an origin the caller asked
            // for that cannot be set must not silently degrade to phase drift.
            AcGeVector2d patternOrigin(0.0, 0.0);
            if (m08eTryReadVector2d(entityJson, "pattern_origin", patternOrigin)) {
                es = pHatch->setOriginPoint(AcGePoint2d(patternOrigin.x, patternOrigin.y));
                if (es != Acad::eOk) {
                    delete pHatch;
                    errCode = "BUILD_FAILED";
                    errMsg = "entity.kind=hatch setOriginPoint errorstatus " + std::to_string(static_cast<int>(es));
                    return nullptr;
                }
            }
        }
        es = pHatch->setHatchStyle(static_cast<AcDbHatch::HatchStyle>(static_cast<int>(hatchStyleRaw)));
        if (es != Acad::eOk) {
            delete pHatch;
            errCode = "BUILD_FAILED";
            errMsg = "entity.kind=hatch setHatchStyle errorstatus " + std::to_string(static_cast<int>(es));
            return nullptr;
        }
        std::vector<M08eHatchLoop> loops;
        const M08eHatchLoopReadStatus loopStatus = m08eReadHatchLoops(entityJson, loops);
        if (loopStatus != kM08eHatchLoopReadOk) {
            delete pHatch;
            if (loopStatus == kM08eHatchLoopReadMalformedEdge) {
                errCode = "HATCH_EDGE_LOOP_MALFORMED";
                errMsg = "HATCH_EDGE_LOOP_MALFORMED";
            } else {
                errCode = "MISSING_ARG";
                errMsg = "entity.kind=hatch requires 'loops' with polyline 'vertices' or supported 'edges'";
            }
            return nullptr;
        }
        for (size_t i = 0; i < loops.size(); ++i) {
            if (loops[i].hasEdges) {
                es = pHatch->appendLoop(loops[i].loopType, loops[i].edgePtrs, loops[i].edgeTypes);
                if (es == Acad::eOk) {
                    // The AcGeCurve2d* overload TRANSFERS ownership: the hatch
                    // keeps these exact pointers (measured: deleting them here
                    // left dangling edges and evaluateHatch AV'd reading 0x0000
                    // -- the R4i b037 process kill). Drop our references without
                    // deleting; m08eReleaseHatchLoops then only frees loops that
                    // never made it into the hatch (error paths).
                    loops[i].edgePtrs.removeAll();
                    loops[i].edgeTypes.removeAll();
                    loops[i].hasEdges = false;
                }
            } else {
                es = pHatch->appendLoop(loops[i].loopType, loops[i].vertices, loops[i].bulges);
            }
            if (es != Acad::eOk) {
                m08eReleaseHatchLoops(loops);
                delete pHatch;
                errCode = "BUILD_FAILED";
                errMsg = "entity.kind=hatch appendLoop[" + std::to_string(i) +
                         "] errorstatus " + std::to_string(static_cast<int>(es));
                return nullptr;
            }
        }
        m08eReleaseHatchLoops(loops);
        if (hasPatternPatPath && pHatch->numPatternDefinitions() <= 0) {
            // Instrument, fail-loud: setPattern(kCustomDefined) returned eOk but
            // no definition lines were actually loaded -- the .pat was not
            // resolved by accoreconsole's pattern search. Proceeding would hand
            // evaluateHatch a patternless custom hatch (eInvalidInput at best).
            delete pHatch;
            errCode = "HATCH_CUSTOM_PAT_EMPTY";
            errMsg = "entity.kind=hatch custom pattern '" + patternName
                   + "' loaded 0 definition lines (pat not resolved by search path)";
            return nullptr;
        }
        // Associativity at CREATE time is flag-only and does NOT survive save
        // without sources (measured R4u: job true -> saved false, 258/258).
        // The orphan premise behind the original flag-copy is RETRACTED
        // (docs/ASSOC_ORPHAN_FINDING.md): the 0/66 probes flew a stale binary;
        // the sources are real and per-loop readable. The REAL re-link happens
        // after the append pass via write.block.relink_hatch_assoc
        // (m08eHandleRelinkHatchAssoc below), which sets the ids + persistent
        // reactors so the flag persists. The flag replay here stays harmless
        // (kFalse-equivalent after save) and keeps the job payload contract.
        bool isAssociativeIn = false;
        m08eFindFlag(entityJson, "is_associative", isAssociativeIn);
        es = pHatch->setAssociative(isAssociativeIn ? Adesk::kTrue : Adesk::kFalse);
        if (es != Acad::eOk) {
            delete pHatch;
            errCode = "BUILD_FAILED";
            errMsg = "entity.kind=hatch setAssociative errorstatus " + std::to_string(static_cast<int>(es));
            return nullptr;
        }
        es = pHatch->evaluateHatch();
        if (es != Acad::eOk) {
            delete pHatch;
            errCode = "BUILD_FAILED";
            errMsg = "entity.kind=hatch evaluateHatch errorstatus " + std::to_string(static_cast<int>(es));
            return nullptr;
        }
        return pHatch;
    }
    if (kind == "face3d") {
        AcGePoint3d p0, p1, p2, p3;
        if (!m08eTryReadPoint(entityJson, "p0", p0) ||
            !m08eTryReadPoint(entityJson, "p1", p1) ||
            !m08eTryReadPoint(entityJson, "p2", p2) ||
            !m08eTryReadPoint(entityJson, "p3", p3)) {
            errCode = "MISSING_ARG";
            errMsg = "entity.kind=face3d requires p0/p1/p2/p3";
            return nullptr;
        }
        std::vector<bool> edgeVisibility;
        if (!m08eReadFlagArray(entityJson, "edge_visibility", edgeVisibility) ||
            edgeVisibility.size() != 4) {
            errCode = "MISSING_ARG";
            errMsg = "entity.kind=face3d requires 'edge_visibility':[4 bool]";
            return nullptr;
        }
        AcDbFace* pFace = new AcDbFace(p0, p1, p2, p3);
        for (size_t i = 0; i < edgeVisibility.size(); ++i) {
            const Acad::ErrorStatus es = edgeVisibility[i]
                ? pFace->makeEdgeVisibleAt(static_cast<Adesk::UInt16>(i))
                : pFace->makeEdgeInvisibleAt(static_cast<Adesk::UInt16>(i));
            if (es != Acad::eOk) {
                delete pFace;
                errCode = "BUILD_FAILED";
                errMsg = "entity.kind=face3d edge_visibility[" + std::to_string(i) +
                         "] errorstatus " + std::to_string(static_cast<int>(es));
                return nullptr;
            }
        }
        return pFace;
    }

    errCode = "UNSUPPORTED_KIND";
    errMsg = "write.block.append_entity supports entity.kind in {line,circle,arc,text,ellipse,point,spline,lwpolyline,polyline,block_reference,hatch,face3d,wipeout}; got '" + kind + "'";
    return nullptr;
}

static Acad::ErrorStatus m08eAppendPolylineEntityForAppend(const std::string& entityJson,
                                                           AcDbBlockTableRecord* pBTR,
                                                           const std::string& layer,
                                                           AcDbObjectId& newIdOut,
                                                           std::string& errCode,
                                                           std::string& errMsg)
{
    newIdOut = AcDbObjectId::kNull;
    errCode.clear();
    errMsg.clear();
    std::string nativeClass;
    jsonFindString(entityJson, "class", nativeClass);

    if (nativeClass == "AcDb3dPolyline") {
        AcGePoint3dArray verts;
        if (!m08eReadPoint3dArray(entityJson, "points", verts) || verts.length() < 2) {
            errCode = "MISSING_ARG";
            errMsg = "entity.kind=polyline class=AcDb3dPolyline requires 'points':[>=2 {x,y,z}]";
            return Acad::eInvalidInput;
        }
        AcDb3dPolyline* pPoly = new AcDb3dPolyline();
        if (!layer.empty())
            pPoly->setLayer(asciiToWide(layer).c_str());
        Acad::ErrorStatus es = pBTR->appendAcDbEntity(newIdOut, pPoly);
        if (es != Acad::eOk) {
            delete pPoly;
            return es;
        }
        for (int i = 0; i < verts.length(); ++i) {
            AcDb3dPolylineVertex* pV = new AcDb3dPolylineVertex(verts[i]);
            AcDbObjectId vid;
            es = pPoly->appendVertex(vid, pV);
            if (es == Acad::eOk) {
                pV->close();
                continue;
            }
            delete pV;
            newIdOut = AcDbObjectId::kNull;
            const Acad::ErrorStatus eraseEs = pPoly->erase();
            pPoly->close();
            if (eraseEs != Acad::eOk) {
                errCode = "APPEND_FAILED";
                errMsg = "appendVertex 3dpolyline rollback errorstatus " +
                         std::to_string(static_cast<int>(eraseEs));
            }
            return es;
        }
        pPoly->close();
        return Acad::eOk;
    }

    if (nativeClass == "AcDb2dPolyline") {
        std::vector<M08eVertex2d> verts;
        if (!m08eReadVertex2dArray(entityJson, "points", true, verts) || verts.size() < 2) {
            errCode = "MISSING_ARG";
            errMsg = "entity.kind=polyline class=AcDb2dPolyline requires 'points':[>=2 {x,y}]";
            return Acad::eInvalidInput;
        }
        double elevation = 0.0;
        jsonFindNumber(entityJson, "elevation", elevation);
        bool closed = false;
        m08eFindFlag(entityJson, "closed", closed);
        double defStartW = 0.0, defEndW = 0.0;
        jsonFindNumber(entityJson, "default_start_width", defStartW);
        jsonFindNumber(entityJson, "default_end_width", defEndW);

        AcDb2dPolyline* pPoly = new AcDb2dPolyline();
        Acad::ErrorStatus es = pPoly->setElevation(elevation);
        if (es != Acad::eOk) {
            delete pPoly;
            errCode = "BUILD_FAILED";
            errMsg = "entity.kind=polyline setElevation errorstatus " +
                     std::to_string(static_cast<int>(es));
            return es;
        }
        if (closed) {
            es = pPoly->setClosed(Adesk::kTrue);
            if (es != Acad::eOk) {
                delete pPoly;
                errCode = "BUILD_FAILED";
                errMsg = "entity.kind=polyline setClosed errorstatus " +
                         std::to_string(static_cast<int>(es));
                return es;
            }
        }
        es = pPoly->setDefaultStartWidth(defStartW);
        if (es != Acad::eOk) {
            delete pPoly;
            errCode = "BUILD_FAILED";
            errMsg = "entity.kind=polyline setDefaultStartWidth errorstatus " +
                     std::to_string(static_cast<int>(es));
            return es;
        }
        es = pPoly->setDefaultEndWidth(defEndW);
        if (es != Acad::eOk) {
            delete pPoly;
            errCode = "BUILD_FAILED";
            errMsg = "entity.kind=polyline setDefaultEndWidth errorstatus " +
                     std::to_string(static_cast<int>(es));
            return es;
        }
        if (!layer.empty())
            pPoly->setLayer(asciiToWide(layer).c_str());

        es = pBTR->appendAcDbEntity(newIdOut, pPoly);
        if (es != Acad::eOk) {
            delete pPoly;
            return es;
        }
        for (size_t i = 0; i < verts.size(); ++i) {
            AcDb2dVertex* pV = new AcDb2dVertex(
                AcGePoint3d(verts[i].x, verts[i].y, elevation),
                verts[i].bulge,
                verts[i].startWidth,
                verts[i].endWidth);
            AcDbObjectId vid;
            es = pPoly->appendVertex(vid, pV);
            if (es == Acad::eOk) {
                pV->close();
                continue;
            }
            delete pV;
            newIdOut = AcDbObjectId::kNull;
            const Acad::ErrorStatus eraseEs = pPoly->erase();
            pPoly->close();
            if (eraseEs != Acad::eOk) {
                errCode = "APPEND_FAILED";
                errMsg = "appendVertex 2dpolyline rollback errorstatus " +
                         std::to_string(static_cast<int>(eraseEs));
            }
            return es;
        }
        pPoly->close();
        return Acad::eOk;
    }

    errCode = "INVALID_INPUT";
    errMsg = "entity.kind=polyline requires 'class' in {AcDb2dPolyline,AcDb3dPolyline}";
    return Acad::eInvalidInput;
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
// "text" is BOTH the kind VALUE and the content KEY in this payload
// ({"kind": "text", "position": {...}, "text": "..."}). The global
// jsonFindString takes the FIRST occurrence -- the kind value -- then reads
// the next quoted token after a colon, which is position's "x" key: every
// appended text became literal "x" (measured: 72/72 X-FORM_청주 texts on
// R4c). Locate the KEY occurrence ('"text"' followed by ':') and delegate to
// jsonFindString on the tail so its proven unescape logic parses the value.
static bool m08eFindTextContent(const std::string& entityJson, std::string& out)
{
    const std::string needle = "\"text\"";
    size_t pos = 0;
    while ((pos = entityJson.find(needle, pos)) != std::string::npos) {
        size_t after = pos + needle.size();
        while (after < entityJson.size()
               && std::isspace(static_cast<unsigned char>(entityJson[after])))
            ++after;
        if (after < entityJson.size() && entityJson[after] == ':')
            return jsonFindString(entityJson.substr(pos), "text", out);
        pos = after;
    }
    return false;
}

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
        m08eFindTextContent(entityJson, content);
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
    errMsg = "write.block.append_entity supports entity.kind in {line,circle,arc,text,ellipse,point,spline,lwpolyline,polyline,block_reference,wipeout}; got '" + kindOut + "'";
    return nullptr;
}

// write.block.append_entity: append a real entity (the 4 legacy simple kinds via
// m08eBuildEntityForAppend above, plus ellipse/point/spline/lwpolyline/polyline/block_reference/
// hatch/face3d via m08e-local helpers that mirror the modelspace create handlers in
// m08g_handlers.inc / m08h_handlers.inc) into a
// NAMED block-table record ('block_name'), or model space if block_name is omitted. REAL,
// PERSISTING primitive -- unlike this family's other write ops (see the file header comment),
// this one does NOT wrap in AriadneStagedWriteTransaction: it mutates ctx.pDb directly, the same
// no-wrapper shape every other real write handler in the codebase uses (write.entity.line/circle/
// arc/text/... in m08g_handlers.inc / m08h_handlers.inc / AriadneNativeJob.cpp), so the appended
// entity survives to the staged-copy DWG the router job already operates on. Still never touches
// the ORIGINAL file (write_mode policy layer, same as every other write op).
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
    if (pEnt == nullptr && buildErrCode != "UNSUPPORTED_KIND") {
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

    AcDbObjectId newId = AcDbObjectId::kNull;
    if (pEnt != nullptr) {
        if (!layer.empty())
            pEnt->setLayer(asciiToWide(layer).c_str());

        es = pBTR->appendAcDbEntity(newId, pEnt);
        if (es == Acad::eOk)
            pEnt->close();
        else
            delete pEnt;
    } else if (kind == "polyline") {
        es = m08eAppendPolylineEntityForAppend(entityJson, pBTR, layer, newId, buildErrCode, buildErrMsg);
        if (es != Acad::eOk && !buildErrCode.empty()) {
            pBTR->close();
            emitNativeError(r, buildErrCode.c_str(), buildErrMsg);
            return true;
        }
    } else {
        pEnt = m08eBuildExtendedEntityForAppend(ctx.pDb, entityJson, kind, buildErrCode, buildErrMsg);
        if (pEnt == nullptr) {
            pBTR->close();
            if (buildErrCode.empty())
                emitNativeError(r, "BUILD_FAILED", buildErrMsg);
            else
                emitNativeError(r, buildErrCode.c_str(), buildErrMsg);
            return true;
        }
        if (!layer.empty())
            pEnt->setLayer(asciiToWide(layer).c_str());

        es = pBTR->appendAcDbEntity(newId, pEnt);
        if (es == Acad::eOk)
            pEnt->close();
        else {
            delete pEnt;
            if (kind == "wipeout" && (es == Acad::eInvalidInput || es == Acad::eNoClassId)) {
                pBTR->close();
                emitNativeError(r, "WIPEOUT_BTR_APPEND_UNPROVEN",
                                "AcDbBlockTableRecord::appendAcDbEntity(AcDbWipeout) errorstatus " +
                                std::to_string(static_cast<int>(es)));
                return true;
            }
        }
    }

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

// "loops_source_handles": [["1BD9"],["1BE1","1BE0"],...] -- outer array aligned
// to the hatch's loops[] (the loop-local extraction contract of
// assoc_source_handles), each inner array the handle strings of that loop's
// boundary sources. Same hand-rolled scanning idiom as m08eReadHatchLoops.
static bool m08eReadLoopsSourceHandles(const std::string& json,
                                       std::vector<std::vector<std::string>>& out)
{
    out.clear();
    size_t lb = 0, rb = 0;
    if (!m08eFindArrayBounds(json, "loops_source_handles", lb, rb))
        return false;
    size_t scan = lb + 1;
    while (scan < rb) {
        while (scan < rb && (json[scan] == ',' || m08eIsJsonSpace(json[scan])))
            ++scan;
        if (scan >= rb)
            break;
        if (json[scan] != '[')
            return false;
        const size_t ie = m08eFindMatchingJsonDelimiter(json, scan, '[', ']');
        if (ie == std::string::npos || ie > rb)
            return false;
        std::vector<std::string> loop;
        size_t s = scan + 1;
        while (s < ie) {
            while (s < ie && (json[s] == ',' || m08eIsJsonSpace(json[s])))
                ++s;
            if (s >= ie)
                break;
            if (json[s] != '"')
                return false;
            size_t e = s + 1;
            while (e < ie && json[e] != '"') {
                if (json[e] == '\\')
                    ++e;
                ++e;
            }
            if (e >= ie)
                return false;
            loop.push_back(json.substr(s + 1, e - s - 1));
            s = e + 1;
        }
        out.push_back(loop);
        scan = ie + 1;
    }
    return !out.empty();
}

// write.block.relink_hatch_assoc: re-arm hatch associativity AFTER the append
// pass (P3 assoc-relink arc, docs/ASSOC_RELINK_DESIGN.md Step B1). The job
// carries REBUILT-drawing handles -- patch_engine translates the census
// handles through its append-result ledger before this job is written, so
// this handler never sees a census handle. Steps: open the hatch kForWrite,
// verify the loop count matches the payload, resolve EVERY source id first
// (all-or-nothing per hatch), setAssociative(kTrue), setAssocObjIdsAt per
// loop, then addPersistentReactor(hatch) on each source -- the reactor is
// what makes the association real; a sourceless flag does not survive save
// (measured R4u: job true -> saved false, 258/258). Every failure mode is a
// loud ASSOC_RELINK_* error (design doc's failure-mode ledger), never a
// silent skip. Like write.block.append_entity, mutates ctx.pDb directly (no
// staged-write wrapper): the router job already operates on the staged copy
// and the ORIGINAL file is protected by the write_mode policy layer.
static bool m08eHandleRelinkHatchAssoc(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string hatchHandle;
    if (!jsonFindString(ctx.job, "hatch_handle", hatchHandle) || hatchHandle.empty()) {
        emitNativeError(r, "MISSING_ARG",
                        "write.block.relink_hatch_assoc requires 'hatch_handle'");
        return true;
    }
    std::vector<std::vector<std::string>> loopsSources;
    if (!m08eReadLoopsSourceHandles(ctx.job, loopsSources)) {
        emitNativeError(r, "MISSING_ARG",
                        "write.block.relink_hatch_assoc requires 'loops_source_handles' "
                        "(array of per-loop handle-string arrays)");
        return true;
    }
    AcDbObjectId hatchId = AcDbObjectId::kNull;
    if (!resolveHandle(ctx.pDb, hatchHandle, hatchId)) {
        emitNativeError(r, "ASSOC_RELINK_HATCH_NOT_FOUND",
                        "no object with handle '" + hatchHandle + "'");
        return true;
    }
    AcDbEntity* pEnt = nullptr;
    Acad::ErrorStatus es = acdbOpenObject(pEnt, hatchId, AcDb::kForWrite);
    if (es != Acad::eOk || pEnt == nullptr) {
        emitNativeError(r, "ASSOC_RELINK_HATCH_OPEN_FAILED",
                        "acdbOpenObject('" + hatchHandle + "') errorstatus "
                        + std::to_string(static_cast<int>(es)));
        return true;
    }
    AcDbHatch* pHatch = AcDbHatch::cast(pEnt);
    if (pHatch == nullptr) {
        pEnt->close();
        emitNativeError(r, "ASSOC_RELINK_NOT_A_HATCH",
                        "object '" + hatchHandle + "' is not an AcDbHatch");
        return true;
    }
    const int numLoops = pHatch->numLoops();
    if (numLoops != static_cast<int>(loopsSources.size())) {
        pHatch->close();
        emitNativeError(r, "ASSOC_RELINK_LOOP_MISMATCH",
                        "hatch '" + hatchHandle + "' has "
                        + std::to_string(numLoops) + " loops but payload carries "
                        + std::to_string(loopsSources.size()));
        return true;
    }
    // Resolve every source BEFORE mutating anything: all-or-nothing per hatch.
    std::vector<AcDbObjectIdArray> loopIds(loopsSources.size());
    for (size_t i = 0; i < loopsSources.size(); ++i) {
        for (size_t k = 0; k < loopsSources[i].size(); ++k) {
            AcDbObjectId sid = AcDbObjectId::kNull;
            if (!resolveHandle(ctx.pDb, loopsSources[i][k], sid)) {
                pHatch->close();
                emitNativeError(r, "ASSOC_RELINK_SOURCE_NOT_FOUND",
                                "loop " + std::to_string(i) + " source handle '"
                                + loopsSources[i][k] + "' does not resolve");
                return true;
            }
            loopIds[i].append(sid);
        }
    }
    // ObjectARX 2027 has NO per-loop assoc SETTER (dbhatch.h association
    // methods: getAssocObjIdsAt / getAssocObjIds / removeAssocObjIds only).
    // The WRITE path is the id-derived loop overload under "Hatch Association
    // Methods": insertLoopAt(int, Adesk::Int32, const AcDbObjectIdArray&).
    // Re-arm by REPLACING each geometric loop with an id-derived loop at the
    // same index and type -- the same (type, ids) pairing the original
    // drawing's own associative hatches store; the loop geometry re-derives
    // from the rebuilt boundary sources, which themselves round-trip diff0.
    es = pHatch->setAssociative(true);
    if (es != Acad::eOk) {
        pHatch->close();
        emitNativeError(r, "ASSOC_RELINK_SET_ASSOC_FAILED",
                        "setAssociative(true) errorstatus "
                        + std::to_string(static_cast<int>(es)));
        return true;
    }
    int sourcesLinked = 0;
    int loopsReplaced = 0;
    for (int i = 0; i < numLoops; ++i) {
        if (loopIds[static_cast<size_t>(i)].isEmpty())
            continue;  // per-loop empty list = that loop stays underived (contract)
        const Adesk::Int32 loopType = pHatch->loopTypeAt(i);
        es = pHatch->removeLoopAt(i);
        if (es != Acad::eOk) {
            pHatch->close();
            emitNativeError(r, "ASSOC_RELINK_REMOVE_LOOP_FAILED",
                            "removeLoopAt(" + std::to_string(i) + ") errorstatus "
                            + std::to_string(static_cast<int>(es)));
            return true;
        }
        es = pHatch->insertLoopAt(i, loopType, loopIds[static_cast<size_t>(i)]);
        if (es != Acad::eOk) {
            pHatch->close();
            emitNativeError(r, "ASSOC_RELINK_INSERT_LOOP_FAILED",
                            "insertLoopAt(" + std::to_string(i) + ", ids) errorstatus "
                            + std::to_string(static_cast<int>(es))
                            + " (loop " + std::to_string(i)
                            + " removed but not re-inserted -- batch aborts, run is partial)");
            return true;
        }
        sourcesLinked += loopIds[static_cast<size_t>(i)].length();
        ++loopsReplaced;
    }
    if (loopsReplaced > 0) {
        es = pHatch->evaluateHatch();
        if (es != Acad::eOk) {
            pHatch->close();
            emitNativeError(r, "ASSOC_RELINK_EVALUATE_FAILED",
                            "evaluateHatch after loop replacement errorstatus "
                            + std::to_string(static_cast<int>(es)));
            return true;
        }
    }
    int reactorsAdded = 0;
    for (size_t i = 0; i < loopIds.size(); ++i) {
        for (int k = 0; k < loopIds[i].length(); ++k) {
            AcDbEntity* pSrc = nullptr;
            es = acdbOpenObject(pSrc, loopIds[i].at(k), AcDb::kForWrite);
            if (es != Acad::eOk || pSrc == nullptr) {
                pHatch->close();
                emitNativeError(r, "ASSOC_RELINK_SOURCE_OPEN_FAILED",
                                "loop " + std::to_string(i) + " source open errorstatus "
                                + std::to_string(static_cast<int>(es)));
                return true;
            }
            pSrc->addPersistentReactor(hatchId);
            pSrc->close();
            ++reactorsAdded;
        }
    }
    const bool assocAfter = pHatch->associative();
    pHatch->close();
    r << "\"result\":{\"relinked\":true"
      << ",\"hatch_handle\":" << njsonStr(hatchHandle)
      << ",\"loops\":" << numLoops
      << ",\"loops_replaced\":" << loopsReplaced
      << ",\"sources_linked\":" << sourcesLinked
      << ",\"reactors_added\":" << reactorsAdded
      << ",\"associative_after\":" << (assocAfter ? "true" : "false")
      << ",\"errorstatus\":0"
      << "},\"status\":\"ok\"}";
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
    if (op == kM08eOpRelinkAssoc)
        return m08eHandleRelinkHatchAssoc(ctx, r);
    if (op == kM08eOpDeepClone)
        return m08eHandleDeepClone(ctx, r);
    if (op == kM08eOpInsertBlock)
        return m08eHandleInsertBlock(ctx, r);
    return false;
}
