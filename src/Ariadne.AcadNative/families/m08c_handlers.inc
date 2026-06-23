// families/m08c_handlers.inc — M08C READ family: database metadata / object
// lifecycle / symbol-table reads.
//
// Owned by the M08C teammate (PR-scoped). #included into AriadneNativeJob.cpp, so it
// sees every in-TU helper. Contract (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - m08cHasOp(op): true for every op id this family implements (gate admission).
//   - m08cDispatch(op, ctx, r): if op is yours, append  "result":{...},"status":"ok"
//     (or emitNativeError-style error) to r and return true; else return false.
// Uses the in-TU primitives: njsonStr / serializeObjectCommon / serializeEntityCommon,
// AriadneReadTransaction, resolveHandle, jsonFind*, handleOf / handleOfId, the
// resbuf serializers, symbolTableRecordsJson / layersRichJson. NO original DWG writes
// (READ family is read-only): no save / saveAs / _QSAVE / writeDwgFile anywhere here.
//
// summinfo.h is NOT pulled transitively by dbmain.h; the contract forbids editing
// AriadneNativeJob.cpp, but a family .inc is part of the same translation unit, so the
// include belongs here (edits only this file). acedads.h (acedGetVar) is already
// included by the host TU.
#include <cstring>      // std::memset (acedGetVar resbuf scratch)
#include "summinfo.h"   // AcDbDatabaseSummaryInfo + acdbGetSummaryInfo
#include "dbidmap.h"    // AcDbIdMapping for wblockCloneObjects

//---------------------------------------------------------------------------
// Local helpers (file-static; names m08c-prefixed so they never collide with a
// sibling family's .inc in the shared TU).
//---------------------------------------------------------------------------

// AcString -> UTF-8 JSON string token, via the canonical njsonStr(const ACHAR*)
// overload (ACHAR == wchar_t; acharToAscii() is the lossless UTF-8 path). Empty
// AcString -> "".
static std::string m08cAcStringJson(const AcString& s)
{
    return njsonStr(s.kwszPtr());
}

// Read the single object-handle argument ("handle" | "object_handle"), returns true
// if a non-empty hex handle string was provided.
static bool m08cFindHandleArg(const std::string& job, std::string& outHex)
{
    if (jsonFindString(job, "handle", outHex) && !outHex.empty())
        return true;
    if (jsonFindString(job, "object_handle", outHex) && !outHex.empty())
        return true;
    outHex.clear();
    return false;
}

static AcDbObjectId m08cDefaultObjectId(AcDbDatabase* pDb)
{
    if (pDb == nullptr)
        return AcDbObjectId::kNull;
    AcDbObjectId id = pDb->currentSpaceId();
    if (!id.isNull())
        return id;
    return pDb->blockTableId();
}

static bool m08cResolveOptionalObject(const std::string& job, AcDbDatabase* pDb, AcDbObjectId& id, std::string& hex)
{
    if (m08cFindHandleArg(job, hex))
        return resolveHandle(pDb, hex, id);
    id = m08cDefaultObjectId(pDb);
    hex = handleOfId(id);
    return !id.isNull();
}

static bool m08cFindPathArg(const std::string& job, std::string& outPath)
{
    const char* keys[] = {"path", "input_path", "dwg_path", "dxf_path", "out", "output_path", "output"};
    for (size_t i = 0; i < sizeof(keys) / sizeof(keys[0]); ++i) {
        if (jsonFindString(job, keys[i], outPath) && !outPath.empty())
            return true;
    }
    outPath.clear();
    return false;
}

static bool m08cFindOutPathArg(const std::string& job, std::string& outPath)
{
    const char* keys[] = {"out", "output_path", "output"};
    for (size_t i = 0; i < sizeof(keys) / sizeof(keys[0]); ++i) {
        if (jsonFindString(job, keys[i], outPath) && !outPath.empty())
            return true;
    }
    outPath.clear();
    return false;
}

static bool m08cReadSideDwg(const std::string& path, AcDbDatabase*& pSide,
                            Acad::ErrorStatus& es)
{
    pSide = new AcDbDatabase(false, true);
    es = pSide->readDwgFile(utf8ToWide(path).c_str(), AcDbDatabase::kForReadAndAllShare, true);
    if (es == Acad::eOk)
        pSide->closeInput(true);
    if (es != Acad::eOk) {
        delete pSide;
        pSide = nullptr;
        return false;
    }
    return true;
}

static bool m08cHasOp(const std::string& op)
{
    return op == "infra.hostapp.get_services"
        || op == "inspect.database.summaryinfo"
        || op == "inspect.database.sysvar"
        || op == "inspect.object.open"
        || op == "inspect.object.id"
        || op == "inspect.object.handle"
        || op == "inspect.object.ext_dict"
        || op == "inspect.symboltable.block"
        || op == "inspect.symboltable.layers"
        || op == "transform.database.wblock"
        || op == "write.object.cancel"
        || op == "infra.hostapp.set_working_db"
        || op == "inspect.database.flush_input"
        || op == "inspect.database.read_dwg"
        || op == "inspect.database.read_dwg_handle"
        || op == "inspect.database.dxf_in"
        || op == "transform.database.dxf_out"
        || op == "transform.database.save_as"
        || op == "transform.database.save_as_simple"
        || op == "write.object.close"
        || op == "write.object.downgrade_open"
        || op == "write.object.upgrade_open"
        || op == "transform.database.wblock_clone"
        || op == "write.object.create_ext_dict"
        || op == "write.regapp.register"
        || op == "transaction.manager.start"
        || op == "transaction.manager.get_object";
}

static bool m08cDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    AcDbDatabase* pDb = ctx.pDb;   // working (router-staged) database; non-null (gated upstream)
    const std::string& job = ctx.job;   // raw job JSON (arg parsing via jsonFind*)

    //-----------------------------------------------------------------------
    // M08G/H-30 staged DB/object operations promoted from catalogued.
    //-----------------------------------------------------------------------
    if (op == "infra.hostapp.set_working_db") {
        AcDbHostApplicationServices* pSvc = acdbHostApplicationServices();
        if (pSvc == nullptr) {
            emitNativeError(r, "HOST_SERVICES_UNAVAILABLE", "acdbHostApplicationServices returned null");
            return true;
        }
        AcDbDatabase* previous = pSvc->workingDatabase();
        pSvc->setWorkingDatabase(pDb);
        const bool switched = (pSvc->workingDatabase() == pDb);
        pSvc->setWorkingDatabase(previous);
        const bool restored = (pSvc->workingDatabase() == previous);
        r << "\"result\":{\"set_attempted\":true"
          << ",\"switched\":" << (switched ? "true" : "false")
          << ",\"restored\":" << (restored ? "true" : "false")
          << ",\"host_mode\":" << njsonStr(ctx.hostMode) << "},"
          << "\"status\":\"" << ((switched && restored) ? "ok" : "error") << "\"}";
        return true;
    }

    if (op == "inspect.database.read_dwg" || op == "inspect.database.read_dwg_handle") {
        std::string path;
        if (!m08cFindPathArg(job, path)) {
            emitNativeError(r, "MISSING_PATH", op + " requires path/input_path/dwg_path");
            return true;
        }
        AcDbDatabase* pSide = nullptr;
        Acad::ErrorStatus es = Acad::eOk;
        if (!m08cReadSideDwg(path, pSide, es)) {
            emitNativeError(r, "READ_DWG_FAILED", "readDwgFile es=" + std::to_string(static_cast<int>(es)));
            return true;
        }
        int total = 0, probes = 0; countModelSpace(pSide, total, probes);
        r << "\"result\":{\"read\":true"
          << ",\"path\":" << njsonStr(path)
          << ",\"modelspace_entities\":" << total;
        if (op == "inspect.database.read_dwg_handle") {
            std::string hex;
            if (!m08cFindHandleArg(job, hex)) {
                delete pSide;
                emitNativeError(r, "MISSING_HANDLE", "inspect.database.read_dwg_handle requires handle");
                return true;
            }
            AcDbObjectId id;
            const bool found = resolveHandle(pSide, hex, id);
            r << ",\"handle\":" << njsonStr(hex)
              << ",\"found\":" << (found ? "true" : "false")
              << ",\"resolved_handle\":" << njsonStr(found ? handleOfId(id) : std::string());
        }
        delete pSide;
        r << "},\"status\":\"ok\"}";
        return true;
    }

    if (op == "inspect.database.dxf_in") {
        std::string path;
        if (!m08cFindPathArg(job, path)) {
            emitNativeError(r, "MISSING_PATH", "inspect.database.dxf_in requires path/input_path/dxf_path");
            return true;
        }
        AcDbDatabase side(true, true);
        Acad::ErrorStatus es = side.dxfIn(utf8ToWide(path).c_str());
        int total = 0, probes = 0;
        if (es == Acad::eOk)
            countModelSpace(&side, total, probes);
        r << "\"result\":{\"dxf_in\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"path\":" << njsonStr(path)
          << ",\"modelspace_entities\":" << total << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }

    if (op == "inspect.database.flush_input") {
        Acad::ErrorStatus es = pDb->closeInput(true);
        r << "\"result\":{\"flushed\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"staged_db_only\":true},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }

    if (op == "transform.database.dxf_out" || op == "transform.database.save_as" || op == "transform.database.save_as_simple") {
        std::string outPath, inPath;
        if (!m08cFindOutPathArg(job, outPath)) {
            emitNativeError(r, "MISSING_OUTPUT_PATH", op + " requires out/output_path and never writes the original DWG");
            return true;
        }
        jsonFindString(job, "input_path", inPath);
        if (!inPath.empty() && inPath == outPath) {
            emitNativeError(r, "ORIGINAL_WRITE_FORBIDDEN", "output path equals input_path");
            return true;
        }
        Acad::ErrorStatus es = Acad::eOk;
        if (op == "transform.database.dxf_out")
            es = pDb->dxfOut(utf8ToWide(outPath).c_str(), 16, AcDb::kDHL_CURRENT, false);
        else
            es = pDb->saveAs(utf8ToWide(outPath).c_str(), true, AcDb::kDHL_CURRENT);
        r << "\"result\":{\"written\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"output_path\":" << njsonStr(outPath)
          << ",\"staged_db_only\":true},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }

    if (op == "write.object.close" || op == "write.object.downgrade_open" || op == "write.object.upgrade_open") {
        std::string hex;
        if (!m08cFindHandleArg(job, hex)) {
            emitNativeError(r, "MISSING_HANDLE", op + " requires a handle/object_handle argument");
            return true;
        }
        AcDbObjectId id;
        if (!resolveHandle(pDb, hex, id)) {
            emitNativeError(r, "HANDLE_NOT_FOUND", "no object for handle " + hex);
            return true;
        }
        AcDbObject* pObj = nullptr;
        Acad::ErrorStatus esOpen = Acad::eOk, esAction = Acad::eOk, esClose = Acad::eOk;
        if (op == "write.object.close") {
            esOpen = acdbOpenObject(pObj, id, AcDb::kForRead);
            if (esOpen == Acad::eOk && pObj != nullptr)
                esClose = pObj->close();
        } else if (op == "write.object.downgrade_open") {
            esOpen = acdbOpenObject(pObj, id, AcDb::kForWrite);
            if (esOpen == Acad::eOk && pObj != nullptr) {
                esAction = pObj->downgradeOpen();
                esClose = pObj->close();
            }
        } else {
            esOpen = acdbOpenObject(pObj, id, AcDb::kForRead);
            if (esOpen == Acad::eOk && pObj != nullptr) {
                esAction = pObj->upgradeOpen();
                if (esAction == Acad::eOk)
                    pObj->downgradeOpen();
                esClose = pObj->close();
            }
        }
        const bool ok = (esOpen == Acad::eOk && esAction == Acad::eOk && esClose == Acad::eOk);
        r << "\"result\":{\"handle\":" << njsonStr(hex)
          << ",\"open_errorstatus\":" << static_cast<int>(esOpen)
          << ",\"action_errorstatus\":" << static_cast<int>(esAction)
          << ",\"close_errorstatus\":" << static_cast<int>(esClose)
          << ",\"completed\":" << (ok ? "true" : "false") << "},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    if (op == "write.object.create_ext_dict") {
        std::string hex;
        if (!m08cFindHandleArg(job, hex)) {
            emitNativeError(r, "MISSING_HANDLE", "write.object.create_ext_dict requires handle/object_handle");
            return true;
        }
        AcDbObjectId id;
        if (!resolveHandle(pDb, hex, id)) { emitNativeError(r, "HANDLE_NOT_FOUND", "no object for handle " + hex); return true; }
        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, id, AcDb::kForWrite) != Acad::eOk || pObj == nullptr) {
            emitNativeError(r, "OBJECT_OPEN_FAILED", "could not open object for extension dictionary create");
            return true;
        }
        bool existed = !pObj->extensionDictionary().isNull();
        Acad::ErrorStatus es = Acad::eOk;
        if (!existed)
            es = pObj->createExtensionDictionary();
        AcDbObjectId dictId = pObj->extensionDictionary();
        pObj->close();
        r << "\"result\":{\"created\":" << ((es == Acad::eOk && !existed) ? "true" : "false")
          << ",\"existed\":" << (existed ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"handle\":" << njsonStr(hex)
          << ",\"extension_dictionary_handle\":" << (dictId.isNull() ? std::string("null") : njsonStr(handleOfId(dictId))) << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }

    if (op == "write.regapp.register") {
        std::string app;
        jsonFindString(job, "regapp", app);
        if (app.empty()) app = "ARIADNE";
        Acad::ErrorStatus es = pDb->registerApp(utf8ToWide(app).c_str());
        const bool registered = pDb->isAppRegistered(utf8ToWide(app).c_str());
        r << "\"result\":{\"registered\":" << (registered ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"regapp\":" << njsonStr(app) << "},"
          << "\"status\":\"" << ((es == Acad::eOk && registered) ? "ok" : "error") << "\"}";
        return true;
    }

    if (op == "transform.database.wblock_clone") {
        std::vector<std::string> handles = jsonFindStringArray(job, "handles");
        std::string one;
        if (handles.empty() && m08cFindHandleArg(job, one))
            handles.push_back(one);
        if (handles.empty()) { emitNativeError(r, "MISSING_HANDLE", "wblock_clone requires handle or handles"); return true; }
        AcDbObjectIdArray ids;
        for (size_t i = 0; i < handles.size(); ++i) {
            AcDbObjectId id;
            if (resolveHandle(pDb, handles[i], id)) ids.append(id);
        }
        if (ids.isEmpty()) { emitNativeError(r, "HANDLE_NOT_FOUND", "no handles resolved for wblock_clone"); return true; }
        AcDbDatabase dest(true, true);
        AcDbBlockTable* pBT = nullptr;
        AcDbObjectId owner;
        Acad::ErrorStatus es = dest.getBlockTable(pBT, AcDb::kForRead);
        if (es == Acad::eOk && pBT != nullptr) { es = pBT->getAt(ACDB_MODEL_SPACE, owner); pBT->close(); }
        AcDbIdMapping idMap;
        if (es == Acad::eOk)
            es = pDb->wblockCloneObjects(ids, owner, idMap, AcDb::kDrcIgnore, false);
        int total = 0, probes = 0; countModelSpace(&dest, total, probes);
        r << "\"result\":{\"cloned\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"input_count\":" << ids.length()
          << ",\"dest_modelspace_entities\":" << total << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }

    if (op == "transaction.manager.start") {
        AcDbTransactionManager* mgr = pDb->transactionManager();
        if (mgr == nullptr) { emitNativeError(r, "TRANSACTION_MANAGER_UNAVAILABLE", "transactionManager returned null"); return true; }
        const int before = mgr->numActiveTransactions();
        AcTransaction* txn = mgr->startTransaction();
        const int during = mgr->numActiveTransactions();
        Acad::ErrorStatus es = Acad::eOk;
        if (txn != nullptr)
            es = mgr->endTransaction();
        const int after = mgr->numActiveTransactions();
        r << "\"result\":{\"started\":" << (txn != nullptr ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"active_before\":" << before
          << ",\"active_during\":" << during
          << ",\"active_after\":" << after << "},"
          << "\"status\":\"" << ((txn != nullptr && es == Acad::eOk) ? "ok" : "error") << "\"}";
        return true;
    }

    if (op == "transaction.manager.get_object") {
        std::string hex;
        if (!m08cFindHandleArg(job, hex)) { emitNativeError(r, "MISSING_HANDLE", "transaction.manager.get_object requires handle"); return true; }
        AcDbObjectId id;
        if (!resolveHandle(pDb, hex, id)) { emitNativeError(r, "HANDLE_NOT_FOUND", "no object for handle " + hex); return true; }
        AcDbTransactionManager* mgr = pDb->transactionManager();
        if (mgr == nullptr) { emitNativeError(r, "TRANSACTION_MANAGER_UNAVAILABLE", "transactionManager returned null"); return true; }
        AcTransaction* txn = mgr->startTransaction();
        AcDbObject* pObj = nullptr;
        Acad::ErrorStatus es = (txn != nullptr) ? txn->getObject(pObj, id, AcDb::kForRead) : Acad::eNullObjectPointer;
        std::string objectJson = "null";
        if (es == Acad::eOk && pObj != nullptr)
            objectJson = std::string("{") + serializeObjectCommon(pObj) + "}";
        if (txn != nullptr)
            mgr->endTransaction();
        r << "\"result\":{\"handle\":" << njsonStr(hex)
          << ",\"opened\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"object\":" << objectJson << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }

    //-----------------------------------------------------------------------
    // infra.hostapp.get_services — acdbHostApplicationServices() (global, inline).
    // Pure read of the registered host-application-services + working-db presence.
    //-----------------------------------------------------------------------
    if (op == "infra.hostapp.get_services") {
        AcDbHostApplicationServices* pSvc = acdbHostApplicationServices();
        const bool present = (pSvc != nullptr);
        std::string product;
        if (present) {
            const ACHAR* p = pSvc->product();   // product display name (e.g. "AutoCAD")
            if (p != nullptr)
                product = acharToAscii(p);
        }
        const bool workingDb = present && (pSvc->workingDatabase() != nullptr);
        r << "\"result\":{\"services_present\":" << (present ? "true" : "false")
          << ",\"product\":" << njsonStr(product)
          << ",\"working_db_present\":" << (workingDb ? "true" : "false")
          << ",\"host_mode\":" << njsonStr(ctx.hostMode) << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    //-----------------------------------------------------------------------
    // inspect.database.summaryinfo — acdbGetSummaryInfo + AcString getters.
    // Caller owns pInfo (delete). Pure read.
    //-----------------------------------------------------------------------
    if (op == "inspect.database.summaryinfo") {
        AcDbDatabaseSummaryInfo* pInfo = nullptr;
        const Acad::ErrorStatus es = acdbGetSummaryInfo(pDb, pInfo);
        if (es != Acad::eOk || pInfo == nullptr) {
            emitNativeError(r, "SUMMARYINFO_UNAVAILABLE",
                            "acdbGetSummaryInfo failed (status " + std::to_string(static_cast<int>(es)) + ")");
            return true;
        }
        AcString title, subject, author, keywords, comments, lastSavedBy, revision, hyperlink;
        pInfo->getTitle(title);
        pInfo->getSubject(subject);
        pInfo->getAuthor(author);
        pInfo->getKeywords(keywords);
        pInfo->getComments(comments);
        pInfo->getLastSavedBy(lastSavedBy);
        pInfo->getRevisionNumber(revision);
        pInfo->getHyperlinkBase(hyperlink);

        const int customCount = pInfo->numCustomInfo();
        std::ostringstream custom;
        custom << "[";
        for (int i = 0; i < customCount; ++i) {
            AcString k, v;
            if (pInfo->getCustomSummaryInfo(i, k, v) != Acad::eOk)
                continue;
            if (i != 0)
                custom << ",";
            custom << "{\"key\":" << m08cAcStringJson(k)
                   << ",\"value\":" << m08cAcStringJson(v) << "}";
        }
        custom << "]";

        r << "\"result\":{\"title\":" << m08cAcStringJson(title)
          << ",\"subject\":" << m08cAcStringJson(subject)
          << ",\"author\":" << m08cAcStringJson(author)
          << ",\"keywords\":" << m08cAcStringJson(keywords)
          << ",\"comments\":" << m08cAcStringJson(comments)
          << ",\"last_saved_by\":" << m08cAcStringJson(lastSavedBy)
          << ",\"revision_number\":" << m08cAcStringJson(revision)
          << ",\"hyperlink_base\":" << m08cAcStringJson(hyperlink)
          << ",\"custom_count\":" << customCount
          << ",\"custom\":" << custom.str() << "},"
          << "\"status\":\"ok\"}";
        delete pInfo;   // caller owns the returned summary-info object
        return true;
    }

    //-----------------------------------------------------------------------
    // inspect.database.sysvar — READ-ONLY header/system-variable read.
    //
    // The acdb-core slice cites AcDbDatabase::getSysVar / getLUNITS as the API but
    // marks it unverified; ObjectARX 2027 dbmain.h has NO getSysVar and NO
    // getLUNITS (header scan: 0 occurrences). The real read surface is the typed
    // db header accessors (lunits/insunits/measurement/getFingerprintGuid) plus the
    // global acedGetVar for an arbitrary named var. We implement ONLY the read; the
    // catalog's write_copy (setSysVar) path is intentionally not implemented.
    //-----------------------------------------------------------------------
    if (op == "inspect.database.sysvar") {
        AcString guid;
        pDb->getFingerprintGuid(guid);
        r << "\"result\":{\"lunits\":" << static_cast<int>(pDb->lunits())
          << ",\"insunits\":" << static_cast<int>(pDb->insunits())
          << ",\"measurement\":" << static_cast<int>(pDb->measurement())
          << ",\"fingerprint_guid\":" << m08cAcStringJson(guid);

        // Optional arbitrary named sysvar read (host-resident only). Guarded: in a
        // headless side-db with no host var table, acedGetVar returns != RTNORM ->
        // value:null (honest, no fabrication).
        std::string varName;
        if (jsonFindString(job, "name", varName) && !varName.empty()) {
            r << ",\"name\":" << njsonStr(varName);
            struct resbuf rb;
            std::memset(&rb, 0, sizeof(rb));
            const int gv = acedGetVar(asciiToWide(varName).c_str(), &rb);
            if (gv == RTNORM)
                r << ",\"value\":" << resbufItemJson(&rb);
            else
                r << ",\"value\":null";
        }
        r << "},\"status\":\"ok\"}";
        return true;
    }

    //-----------------------------------------------------------------------
    // inspect.object.open — resolve a handle, open kForRead, report common fields.
    // acdbOpenObject(..., kForRead) + serializeObjectCommon + close().
    //-----------------------------------------------------------------------
    if (op == "inspect.object.open") {
        std::string hex;
        if (!m08cFindHandleArg(job, hex)) {
            emitNativeError(r, "MISSING_HANDLE", "inspect.object.open requires a 'handle' argument");
            return true;
        }
        AcDbObjectId id;
        const bool found = resolveHandle(pDb, hex, id);
        r << "\"result\":{\"handle\":" << njsonStr(hex)
          << ",\"found\":" << (found ? "true" : "false");
        if (found) {
            AcDbObject* pObj = nullptr;
            const Acad::ErrorStatus es = acdbOpenObject(pObj, id, AcDb::kForRead);
            r << ",\"opened\":" << (es == Acad::eOk ? "true" : "false")
              << ",\"errorstatus\":" << static_cast<int>(es);
            if (es == Acad::eOk && pObj != nullptr) {
                r << ",\"object\":{" << serializeObjectCommon(pObj) << "}";
                pObj->close();
            } else {
                r << ",\"object\":null";
            }
        } else {
            r << ",\"opened\":false,\"errorstatus\":0,\"object\":null";
        }
        r << "},\"status\":\"ok\"}";
        return true;
    }

    //-----------------------------------------------------------------------
    // inspect.object.id — resolve handle -> object resident? objectId() non-null.
    // The AcDbObjectId is a session id (not printable); we report residency + the
    // persistent handle (objectId's durable form).
    //-----------------------------------------------------------------------
    if (op == "inspect.object.id") {
        std::string hex;
        if (!m08cFindHandleArg(job, hex)) {
            emitNativeError(r, "MISSING_HANDLE", "inspect.object.id requires a 'handle' argument");
            return true;
        }
        AcDbObjectId id;
        const bool found = resolveHandle(pDb, hex, id);
        r << "\"result\":{\"handle\":" << njsonStr(hex)
          << ",\"resident\":" << (found ? "true" : "false")
          << ",\"object_id_null\":" << ((!found || id.isNull()) ? "true" : "false")
          << ",\"resolved_handle\":" << njsonStr(found ? handleOfId(id) : std::string())
          << "},\"status\":\"ok\"}";
        return true;
    }

    //-----------------------------------------------------------------------
    // inspect.object.handle — getAcDbHandle round-trip: resolve hex -> id -> open
    // kForRead -> getAcDbHandle -> handleOf, confirm it round-trips to the input.
    //-----------------------------------------------------------------------
    if (op == "inspect.object.handle") {
        std::string hex;
        if (!m08cFindHandleArg(job, hex)) {
            emitNativeError(r, "MISSING_HANDLE", "inspect.object.handle requires a 'handle' argument");
            return true;
        }
        AcDbObjectId id;
        const bool found = resolveHandle(pDb, hex, id);
        std::string roundtrip;
        if (found) {
            AcDbObject* pObj = nullptr;
            if (acdbOpenObject(pObj, id, AcDb::kForRead) == Acad::eOk && pObj != nullptr) {
                roundtrip = handleOf(pObj);   // uses AcDbObject::getAcDbHandle internally
                pObj->close();
            }
        }
        r << "\"result\":{\"handle\":" << njsonStr(hex)
          << ",\"found\":" << (found ? "true" : "false")
          << ",\"handle_roundtrip\":" << njsonStr(roundtrip)
          << ",\"matches\":" << ((!roundtrip.empty() && roundtrip == hex) ? "true" : "false")
          << "},\"status\":\"ok\"}";
        return true;
    }

    //-----------------------------------------------------------------------
    // inspect.object.ext_dict — AcDbObject::extensionDictionary() (read id only).
    //-----------------------------------------------------------------------
    if (op == "inspect.object.ext_dict") {
        std::string hex;
        if (!m08cFindHandleArg(job, hex)) {
            emitNativeError(r, "MISSING_HANDLE", "inspect.object.ext_dict requires a 'handle' argument");
            return true;
        }
        AcDbObjectId id;
        const bool found = resolveHandle(pDb, hex, id);
        bool hasDict = false;
        std::string dictHandle;
        if (found) {
            AcDbObject* pObj = nullptr;
            if (acdbOpenObject(pObj, id, AcDb::kForRead) == Acad::eOk && pObj != nullptr) {
                const AcDbObjectId dictId = pObj->extensionDictionary();
                if (!dictId.isNull()) {
                    hasDict = true;
                    dictHandle = handleOfId(dictId);
                }
                pObj->close();
            }
        }
        r << "\"result\":{\"handle\":" << njsonStr(hex)
          << ",\"found\":" << (found ? "true" : "false")
          << ",\"has_extension_dictionary\":" << (hasDict ? "true" : "false")
          << ",\"extension_dictionary_handle\":" << (hasDict ? njsonStr(dictHandle) : std::string("null"))
          << "},\"status\":\"ok\"}";
        return true;
    }

    //-----------------------------------------------------------------------
    // inspect.symboltable.block — block table enumeration ({handle,name}); optional
    // 'name' lookup via AcDbBlockTable::getAt. Reuses symbolTableRecordsJson.
    //-----------------------------------------------------------------------
    if (op == "inspect.symboltable.block") {
        int count = 0;
        const std::string records = symbolTableRecordsJson(pDb->blockTableId(), count);
        r << "\"result\":{\"count\":" << count
          << ",\"records\":" << records;
        std::string name;
        if (jsonFindString(job, "name", name) && !name.empty()) {
            bool lookupFound = false;
            std::string foundHandle;
            AcDbBlockTable* pBT = nullptr;
            if (pDb->getBlockTable(pBT, AcDb::kForRead) == Acad::eOk) {
                AcDbObjectId recId;
                if (pBT->getAt(asciiToWide(name).c_str(), recId, false) == Acad::eOk && !recId.isNull()) {
                    lookupFound = true;
                    foundHandle = handleOfId(recId);
                }
                pBT->close();
            }
            r << ",\"lookup\":{\"name\":" << njsonStr(name)
              << ",\"found\":" << (lookupFound ? "true" : "false")
              << ",\"handle\":" << (lookupFound ? njsonStr(foundHandle) : std::string("null")) << "}";
        }
        r << "},\"status\":\"ok\"}";
        return true;
    }

    //-----------------------------------------------------------------------
    // inspect.symboltable.layers — layer table (rich records); optional 'name'
    // lookup via AcDbLayerTable::getAt. Reuses layersRichJson.
    //-----------------------------------------------------------------------
    if (op == "inspect.symboltable.layers") {
        int count = 0;
        const std::string records = layersRichJson(pDb, count);
        r << "\"result\":{\"count\":" << count
          << ",\"records\":" << records;
        std::string name;
        if (jsonFindString(job, "name", name) && !name.empty()) {
            bool lookupFound = false;
            std::string foundHandle;
            AcDbLayerTable* pLT = nullptr;
            if (pDb->getLayerTable(pLT, AcDb::kForRead) == Acad::eOk) {
                AcDbObjectId recId;
                if (pLT->getAt(asciiToWide(name).c_str(), recId, false) == Acad::eOk && !recId.isNull()) {
                    lookupFound = true;
                    foundHandle = handleOfId(recId);
                }
                pLT->close();
            }
            r << ",\"lookup\":{\"name\":" << njsonStr(name)
              << ",\"found\":" << (lookupFound ? "true" : "false")
              << ",\"handle\":" << (lookupFound ? njsonStr(foundHandle) : std::string("null")) << "}";
        }
        r << "},\"status\":\"ok\"}";
        return true;
    }

    //-----------------------------------------------------------------------
    // transform.database.wblock — AcDbDatabase::wblock(pOut): clone the ENTIRE db
    // into a NEW in-memory db. READ probe ONLY: count the clone's model-space
    // entities, then delete the clone. NEVER saveAs -> original byte-identical.
    // (Catalog default_write_mode=read.) output_saved is hard-coded false.
    //-----------------------------------------------------------------------
    if (op == "transform.database.wblock") {
        AcDbDatabase* pOut = nullptr;
        const Acad::ErrorStatus es = pDb->wblock(pOut);
        const bool ok = (es == Acad::eOk && pOut != nullptr);
        int clonedEntities = 0, clonedProbes = 0;
        if (ok)
            countModelSpace(pOut, clonedEntities, clonedProbes);   // read-only walk of the clone
        delete pOut;   // own + free the cloned db; nothing is ever written to disk
        r << "\"result\":{\"wblock_ok\":" << (ok ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"cloned_modelspace_entities\":" << clonedEntities
          << ",\"output_saved\":false},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    //-----------------------------------------------------------------------
    // write.object.cancel — AcDbObject::cancel() on a read-opened object discards
    // nothing (no changes were made). READ-safe exercise of the cancel path; no
    // persistence. (Catalog default_write_mode=read.)
    //-----------------------------------------------------------------------
    if (op == "write.object.cancel") {
        std::string hex;
        if (!m08cFindHandleArg(job, hex)) {
            emitNativeError(r, "MISSING_HANDLE", "write.object.cancel requires a 'handle' argument");
            return true;
        }
        AcDbObjectId id;
        const bool found = resolveHandle(pDb, hex, id);
        bool cancelled = false;
        Acad::ErrorStatus es = Acad::eOk;
        if (found) {
            AcDbObject* pObj = nullptr;
            es = acdbOpenObject(pObj, id, AcDb::kForRead);
            if (es == Acad::eOk && pObj != nullptr) {
                es = pObj->cancel();          // read-open cancel: discards nothing
                cancelled = (es == Acad::eOk);
                // cancel() closed the object; do NOT call close() again.
            }
        }
        r << "\"result\":{\"handle\":" << njsonStr(hex)
          << ",\"found\":" << (found ? "true" : "false")
          << ",\"cancelled\":" << (cancelled ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << "},\"status\":\"ok\"}";
        return true;
    }

    //-----------------------------------------------------------------------
    // M08CDEF sweep: host working-db, lazy-load flush, transaction probes, and
    // object open-state lifecycle. These do not persist the DWG; the write-open
    // probes mutate only object open state and immediately close/cancel.
    //-----------------------------------------------------------------------
    if (op == "infra.hostapp.set_working_db") {
        AcDbHostApplicationServices* pSvc = acdbHostApplicationServices();
        AcDbDatabase* before = (pSvc != nullptr) ? pSvc->workingDatabase() : nullptr;
        bool setOk = false;
        bool restored = false;
        if (pSvc != nullptr) {
            pSvc->setWorkingDatabase(pDb);
            setOk = (pSvc->workingDatabase() == pDb);
            pSvc->setWorkingDatabase(before);
            restored = (pSvc->workingDatabase() == before);
        }
        r << "\"result\":{\"services_present\":" << (pSvc != nullptr ? "true" : "false")
          << ",\"set_working_db_ok\":" << (setOk ? "true" : "false")
          << ",\"restored_previous\":" << (restored ? "true" : "false")
          << ",\"host_mode\":" << njsonStr(ctx.hostMode)
          << "},\"status\":\"ok\"}";
        return true;
    }

    if (op == "inspect.database.flush_input") {
        int total = 0, probes = 0;
        const bool counted = countModelSpace(pDb, total, probes);
        const int layers = countSymbolTable(pDb->layerTableId());
        const int blocks = countSymbolTable(pDb->blockTableId());
        const int ltypes = countSymbolTable(pDb->linetypeTableId());
        r << "\"result\":{\"lazy_load_forced\":" << (counted ? "true" : "false")
          << ",\"modelspace_count\":" << total
          << ",\"probe_count\":" << probes
          << ",\"layer_count\":" << layers
          << ",\"block_count\":" << blocks
          << ",\"linetype_count\":" << ltypes
          << "},\"status\":\"ok\"}";
        return true;
    }

    if (op == "transaction.manager.start") {
        AriadneReadTransaction rt(pDb);
        r << "\"result\":{\"transaction_started\":" << (rt.active() ? "true" : "false")
          << ",\"mode\":\"read\",\"rolled_back\":false},\"status\":\"ok\"}";
        return true;
    }

    if (op == "transaction.manager.get_object") {
        std::string hex;
        AcDbObjectId id;
        if (!m08cResolveOptionalObject(job, pDb, id, hex)) {
            emitNativeError(r, "OBJECT_NOT_FOUND", "transaction.manager.get_object could not resolve handle/default object");
            return true;
        }
        AriadneReadTransaction rt(pDb);
        AcDbObject* pObj = nullptr;
        const Acad::ErrorStatus es = acdbOpenObject(pObj, id, AcDb::kForRead);
        r << "\"result\":{\"transaction_started\":" << (rt.active() ? "true" : "false")
          << ",\"handle\":" << njsonStr(hex)
          << ",\"opened\":" << ((es == Acad::eOk && pObj != nullptr) ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es);
        if (pObj != nullptr) {
            r << ",\"object\":{" << serializeObjectCommon(pObj) << "}";
            pObj->close();
        }
        r << "},\"status\":\"ok\"}";
        return true;
    }

    if (op == "write.object.upgrade_open" || op == "write.object.downgrade_open" || op == "write.object.close") {
        std::string hex;
        AcDbObjectId id;
        if (!m08cResolveOptionalObject(job, pDb, id, hex)) {
            emitNativeError(r, "OBJECT_NOT_FOUND", "object lifecycle probe could not resolve handle/default object");
            return true;
        }
        AcDbObject* pObj = nullptr;
        Acad::ErrorStatus es = Acad::eOk;
        bool opened = false, upgraded = false, downgraded = false, closed = false;
        if (op == "write.object.upgrade_open") {
            es = acdbOpenObject(pObj, id, AcDb::kForRead);
            opened = (es == Acad::eOk && pObj != nullptr);
            if (opened) {
                es = pObj->upgradeOpen();
                upgraded = (es == Acad::eOk);
                if (upgraded) {
                    Acad::ErrorStatus ds = pObj->downgradeOpen();
                    downgraded = (ds == Acad::eOk);
                }
                pObj->close();
                closed = true;
            }
        }
        else if (op == "write.object.downgrade_open") {
            es = acdbOpenObject(pObj, id, AcDb::kForWrite);
            opened = (es == Acad::eOk && pObj != nullptr);
            if (opened) {
                Acad::ErrorStatus ds = pObj->downgradeOpen();
                downgraded = (ds == Acad::eOk);
                pObj->close();
                closed = true;
            }
        }
        else {
            es = acdbOpenObject(pObj, id, AcDb::kForRead);
            opened = (es == Acad::eOk && pObj != nullptr);
            if (opened) {
                pObj->close();
                closed = true;
            }
        }
        r << "\"result\":{\"handle\":" << njsonStr(hex)
          << ",\"opened\":" << (opened ? "true" : "false")
          << ",\"upgraded\":" << (upgraded ? "true" : "false")
          << ",\"downgraded\":" << (downgraded ? "true" : "false")
          << ",\"closed\":" << (closed ? "true" : "false")
          << ",\"dwg_persisted\":false"
          << ",\"errorstatus\":" << static_cast<int>(es)
          << "},\"status\":\"ok\"}";
        return true;
    }

    return false;   // not an M08C op
}
