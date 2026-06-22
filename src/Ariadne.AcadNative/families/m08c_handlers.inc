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
        || op == "write.object.cancel";
}

static bool m08cDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    AcDbDatabase* pDb = ctx.pDb;   // working (router-staged) database; non-null (gated upstream)
    const std::string& job = ctx.job;   // raw job JSON (arg parsing via jsonFind*)

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

    return false;   // not an M08C op
}
