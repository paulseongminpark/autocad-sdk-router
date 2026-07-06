// families/m08m_handlers.inc — M08M NATIVE: OPM properties + reactors.
//
// T01 OPM / property protocol: the dynamic property protocol (AcRxProperty / AcRxAttribute /
//   AcRxMemberCollection over an AcRxClass) is queryable + extendable hostless; the Properties
//   PALETTE itself is attended (this family does NOT build UI). We register/read property members
//   and attach property-authoring attributes to a TRANSIENT runtime AcRxClass (the M08K runtime-
//   class pattern), then tear it down — real protocol-extension, no fakes.
// T02 reactors: hostless DB/object/persistent/rxevent/linker monitors remain in this family, and
//   Wave 3 closes the full-host editor / doc-manager / long-transaction subset with real native
//   reactor subclasses, persistent registration helpers, count snapshots, and optional bounded safe
//   probes (pickfirst, lock-mode, sysvar round-trip). Interactive firing beyond those probes still
//   requires a dedicated attended AutoCAD host and is reported honestly via counters/flags.
//
// #included into AriadneNativeJob.cpp; sees all in-TU helpers (njsonStr / serializeObjectCommon /
//   AriadneReadTransaction / AriadneStagedWriteTransaction / resolveHandle / jsonFind* / handleOf /
//   handleOfId / emitNativeError / asciiToWide / acharToAscii / hostIsFullAutoCad).
//   m08mHasOp/m08mDispatch lockstep.
//
// SAFETY (hard): staged-write ONLY on ctx.pDb (the router-staged in-memory copy). Never
//   save()/saveAs()/_QSAVE on the original. No acedCommand/acedCmd. Every transient AcRxClass
//   newAcRxClass'd is deleteAcRxClass'd. Editor/doc-manager/longtx registration is transient
//   process state only and is cleaned up on explicit disable or module unload. UTF-8 via njsonStr.
//
// IMPLEMENTED (64): property inspection (13) + OPM protocol (12) + property authoring (17) +
//   reactors (22). No claimed Wave 3 editor/docmanager/longtx op remains deferred.

#include "rxclass.h"      // AcRxClass members()/attributes()/newAcRxClass/acrxBuildClassHierarchy/deleteAcRxClass
#include "rxdict.h"       // acrxClassDictionary (live registered-class lookup by name)
#include "rxmember.h"     // AcRxMember / AcRxMemberCollection / AcRxMemberQueryEngine / AcRxEnumTag
#include "rxprop.h"       // AcRxProperty / AcRxPropertyBase (getValue/setValue/isReadOnly)
#include "rxattrib.h"     // AcRxAttribute family (description/category/units/flags/displayas/...)
#include "rxvalue.h"      // AcRxValue (toString of a property value)
#include "rxvaluetype.h"  // AcRxValueType (member type name)
#include "rxevent.h"      // AcRxEvent / AcRxEventReactor (acrxEvent singleton)
#include "rxdlinkr.h"     // AcRxDynamicLinker / AcRxDLinkerReactor (acrxDynamicLinker singleton)
#include "lngtrans.h"     // AcApLongTransactionManager / AcApLongTransactionReactor
#include "dbObject.h"     // AcDbObject addReactor/removeReactor + addPersistentReactor/removePersistentReactor
#include "dbents.h"       // AcDbLine (scratch entity for reactor-fire proofs)
#include <cwchar>          // std::wcscmp

//============================================================================
// M08M shared helpers (file-scope statics in this TU; m08m-prefixed to avoid any
// collision with sibling family .inc files).
//============================================================================

// Pull a hex handle from the job ("handle", or args.handle).
static bool m08mFindHandle(const std::string& job, std::string& out)
{
    if (jsonFindString(job, "handle", out) && !out.empty())
        return true;
    std::string argsJson;
    if (jsonFindObject(job, "args", argsJson) &&
        jsonFindString(argsJson, "handle", out) && !out.empty())
        return true;
    return false;
}

// Pull a string arg by key from job or job.args (default empty -> false).
static bool m08mFindStr(const std::string& job, const char* key, std::string& out)
{
    if (jsonFindString(job, key, out) && !out.empty())
        return true;
    std::string argsJson;
    if (jsonFindObject(job, "args", argsJson) &&
        jsonFindString(argsJson, key, out) && !out.empty())
        return true;
    return false;
}

// Pull a numeric arg by key from job or job.args.
static bool m08mFindNum(const std::string& job, const char* key, double& out)
{
    if (jsonFindNumber(job, key, out))
        return true;
    std::string argsJson;
    if (jsonFindObject(job, "args", argsJson) && jsonFindNumber(argsJson, key, out))
        return true;
    return false;
}

// Common bool parser used by the full-host monitor ops (`enabled`, `reset`, `execute`).
static bool m08mBoolArg(const std::string& job, const char* key, bool defaultValue)
{
    double v = defaultValue ? 1.0 : 0.0;
    if (m08mFindNum(job, key, v))
        return v != 0.0;
    std::string s;
    if (m08mFindStr(job, key, s))
        return s == "true" || s == "1" || s == "yes" || s == "enable" || s == "enabled" || s == "execute";
    return defaultValue;
}

static std::string m08mTextOrEmpty(const ACHAR* text)
{
    return text != nullptr ? acharToAscii(text) : std::string();
}

static bool m08mFullAutoCadHost(const AriadneJobCtx& ctx)
{
    return ctx.hostMode == "full_autocad" && hostIsFullAutoCad();
}

static std::string m08mDocFileName(AcApDocument* pDoc)
{
    return (pDoc != nullptr && pDoc->fileName() != nullptr) ? acharToAscii(pDoc->fileName()) : std::string();
}

static std::string m08mDocTitle(AcApDocument* pDoc)
{
    return (pDoc != nullptr && pDoc->docTitle() != nullptr) ? acharToAscii(pDoc->docTitle()) : std::string();
}

// Resolve a class-name string to an AcRxClass descriptor. SDK base classes resolve through their
// exported ::desc(); custom Ariadne classes resolve through the live class dictionary (linkage-safe
// — the DBX import lib does not export their ::desc(), so we MUST NOT reference it; see M08K).
// nullptr for an unknown name. AcDbEntity is the default when name is empty (rich property set).
static AcRxClass* m08mResolveClass(const std::string& name)
{
    if (name.empty() || name == "AcDbEntity")  return AcDbEntity::desc();
    if (name == "AcDbObject")                  return AcDbObject::desc();
    if (name == "AcDbCircle")                  return AcDbCircle::desc();
    if (name == "AcDbLine")                    return AcDbLine::desc();
    if (name == "AcRxObject")                  return AcRxObject::desc();
    // custom classes (live dictionary; never their C++ ::desc()).
    if (name == "AriadneProbe")  return AcRxClass::cast(acrxClassDictionary->at(ACRX_T("AriadneProbe")));
    if (name == "AriadneRecord") return AcRxClass::cast(acrxClassDictionary->at(ACRX_T("AriadneRecord")));
    return nullptr;
}

// Find a property member of a class by name (walks the class member collection, casting each member
// to AcRxProperty). Returns the AcRxProperty* or nullptr. Read-only; no ownership transfer.
static const AcRxProperty* m08mFindClassProperty(AcRxClass* cls, const ACHAR* propName)
{
    if (cls == nullptr || propName == nullptr)
        return nullptr;
    AcRxMemberCollection* members = cls->members();
    if (members == nullptr)
        return nullptr;
    const int n = members->count();
    for (int i = 0; i < n; ++i) {
        AcRxMember* m = members->getAt(i);
        if (m == nullptr)
            continue;
        const AcRxProperty* prop = AcRxProperty::cast(m);
        if (prop != nullptr && prop->name() != nullptr &&
            std::wcscmp(prop->name(), propName) == 0)
            return prop;
    }
    return nullptr;
}

// Count property members + total members of a class. Pure read of the class member collection.
static void m08mCountClassProperties(AcRxClass* cls, int& propCount, int& memberCount)
{
    propCount = 0;
    memberCount = 0;
    if (cls == nullptr)
        return;
    AcRxMemberCollection* members = cls->members();
    if (members == nullptr)
        return;
    memberCount = members->count();
    for (int i = 0; i < memberCount; ++i) {
        AcRxMember* m = members->getAt(i);
        if (m != nullptr && AcRxProperty::cast(m) != nullptr)
            ++propCount;
    }
}

// AcRxValueType -> stable type-name string (the value type carried by a member). AcRxValueType
// derives from AcRxClass, so name() is the type name.
static std::string m08mValueTypeName(const AcRxValueType& vt)
{
    return njsonStr(vt.name());
}

// Box a string arg into an AcRxValue matching a property's ACTUAL declared AcRxValueType.
// automate.property.set used to always box the new value as a generic AcRxValue(const ACHAR*);
// AcRxProperty::setValue's internal type check requires the box's type to match the property's
// declared type exactly (Desc<const ACHAR*> is a different singleton than e.g. Desc<AcString> or
// Desc<double>), so that boxing failed eInvalidInput for every real property tried, string-typed
// included. Supports double / int(Adesk::Int32) / bool / AcString / AcGePoint3d -- the common
// AcDbEntity-family property value types. Returns false (never touching outVal) for anything
// else so the caller can report an honest capability gap instead of attempting a mismatched box.
static bool m08mBoxPropertyValue(const AcRxValueType& propType, const std::string& newValStr,
                                  AcRxValue& outVal, std::string& parseError)
{
    if (propType == AcRxValueType::Desc<AcString>::value()) {
        outVal = AcRxValue(AcString(asciiToWide(newValStr).c_str()));
        return true;
    }
    if (propType == AcRxValueType::Desc<double>::value()) {
        try {
            outVal = AcRxValue(std::stod(newValStr));
            return true;
        } catch (...) {
            parseError = "value '" + newValStr + "' is not a valid double";
            return false;
        }
    }
    if (propType == AcRxValueType::Desc<int>::value()) {
        try {
            outVal = AcRxValue(std::stoi(newValStr));
            return true;
        } catch (...) {
            parseError = "value '" + newValStr + "' is not a valid int";
            return false;
        }
    }
    if (propType == AcRxValueType::Desc<bool>::value()) {
        std::string low = newValStr;
        for (char& c : low) { if (c >= 'A' && c <= 'Z') c = static_cast<char>(c - 'A' + 'a'); }
        if (low == "true" || low == "1" || low == "yes") { outVal = AcRxValue(true); return true; }
        if (low == "false" || low == "0" || low == "no") { outVal = AcRxValue(false); return true; }
        parseError = "value '" + newValStr + "' is not a valid bool (use true/false/1/0)";
        return false;
    }
    if (propType == AcRxValueType::Desc<AcGePoint3d>::value()) {
        std::istringstream iss(newValStr);
        std::string tok;
        double comps[3] = { 0.0, 0.0, 0.0 };
        int n = 0;
        while (n < 3 && std::getline(iss, tok, ',')) {
            try { comps[n] = std::stod(tok); } catch (...) { n = -1; break; }
            ++n;
        }
        if (n != 3) {
            parseError = "value '" + newValStr + "' is not a valid 'x,y,z' point";
            return false;
        }
        outVal = AcRxValue(AcGePoint3d(comps[0], comps[1], comps[2]));
        return true;
    }
    return false;   // unsupported property value type -- no parseError; caller distinguishes.
}

// Create a uniquely-named transient runtime AcRxClass derived from AcRxObject for attribute-
// authoring proofs (so we never clobber a registered descriptor and always tear down cleanly).
// Returns the class (caller MUST deleteAcRxClass it) + the resolved unique name. nullptr on failure.
static AcRxClass* m08mNewTransientClass(const std::string& baseName, std::string& outName)
{
    static unsigned long s_seq = 0;
    std::ostringstream nm; nm.precision(kJsonDoublePrecision);
    nm << "AriadneM08M_" << baseName << "_" << (++s_seq) << "_" << static_cast<unsigned long>(GetTickCount());
    outName = nm.str();
    const std::wstring wname = asciiToWide(outName);
    if (acrxClassDictionary->at(wname.c_str()) != nullptr)
        return nullptr;   // astronomically unlikely; bail rather than clobber
    AcRxClass* cls = newAcRxClass(wname.c_str(), AcRxObject::desc()->name(), 0);
    if (cls != nullptr)
        acrxBuildClassHierarchy();
    return cls;
}

//----------------------------------------------------------------------------
// Reactor subclasses (module-lifetime statics). Each increments a fire-counter on
// its callback so a "monitor" op can prove the callback actually fired during a
// scratch in-transaction mutation. They carry no per-call state beyond the counter,
// which is reset before each monitored run.
//----------------------------------------------------------------------------

// AcDbDatabaseReactor: counts objectModified / objectErased / objectAppended on ctx.pDb.
class M08MDbReactor : public AcDbDatabaseReactor
{
public:
    long modifiedCount;
    long erasedCount;
    long appendedCount;
    M08MDbReactor() : modifiedCount(0), erasedCount(0), appendedCount(0) {}
    void reset() { modifiedCount = 0; erasedCount = 0; appendedCount = 0; }
    void objectModified(const AcDbDatabase*, const AcDbObject*) override { ++modifiedCount; }
    void objectErased(const AcDbDatabase*, const AcDbObject*, bool) override { ++erasedCount; }
    void objectAppended(const AcDbDatabase*, const AcDbObject*) override { ++appendedCount; }
};

// AcDbObjectReactor: counts modified / erased on a single object.
class M08MObjReactor : public AcDbObjectReactor
{
public:
    long modifiedCount;
    long erasedCount;
    M08MObjReactor() : modifiedCount(0), erasedCount(0) {}
    void reset() { modifiedCount = 0; erasedCount = 0; }
    void modified(const AcDbObject*) override { ++modifiedCount; }
    void erased(const AcDbObject*, bool) override { ++erasedCount; }
};

// AcRxEventReactor: counts databaseConstructed / databaseToBeDestroyed (real Rx events we can fire
// by constructing a transient AcDbDatabase). Hostless — AcRxEvent is the system event registry.
class M08MRxEventReactor : public AcRxEventReactor
{
public:
    long constructedCount;
    long destroyedCount;
    M08MRxEventReactor() : constructedCount(0), destroyedCount(0) {}
    void reset() { constructedCount = 0; destroyedCount = 0; }
    void databaseConstructed(AcDbDatabase*) override { ++constructedCount; }
    void databaseToBeDestroyed(AcDbDatabase*) override { ++destroyedCount; }
};

// AcRxDLinkerReactor: attach/detach proof against the system dynamic linker (we do not load/unload
// modules in a hostless probe, so this proves the attach/detach lifecycle, not a fired callback).
class M08MLinkerReactor : public AcRxDLinkerReactor
{
public:
    M08MLinkerReactor() {}
};

// First model-space entity helper (used by the safe pickfirst probe for editor input monitoring).
static bool m08mFirstEntityId(AcDbDatabase* pDb, AcDbObjectId& outId)
{
    outId = AcDbObjectId::kNull;
    if (pDb == nullptr)
        return false;
    AcDbBlockTable* pBT = nullptr;
    if (pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk || pBT == nullptr)
        return false;
    AcDbBlockTableRecord* pMS = nullptr;
    if (pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForRead) != Acad::eOk || pMS == nullptr) {
        pBT->close();
        return false;
    }
    pBT->close();
    AcDbBlockTableRecordIterator* pIt = nullptr;
    if (pMS->newIterator(pIt) != Acad::eOk || pIt == nullptr) {
        pMS->close();
        return false;
    }
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbEntity* pEnt = nullptr;
        if (pIt->getEntity(pEnt, AcDb::kForRead) == Acad::eOk && pEnt != nullptr) {
            outId = pEnt->objectId();
            pEnt->close();
            break;
        }
    }
    delete pIt;
    pMS->close();
    return !outId.isNull();
}

//---------------------------------------------------------------------------
// Full-host editor/document/long-transaction reactors. These stay transient
// process state only (register/unregister on demand; cleaned up on unload), and
// their counters let follow-up monitor calls report real attended activity.
//---------------------------------------------------------------------------
class M08MEditorMonitorReactor : public AcEditorReactor
{
public:
    long commandStartCount;
    long commandEndCount;
    long commandCancelCount;
    long commandFailedCount;
    long unknownCommandCount;
    long lispStartCount;
    long lispEndCount;
    long lispCancelCount;
    long sysVarWillChangeCount;
    long sysVarChangedCount;
    long sysVarChangedSuccessCount;
    long dwgOpenBeginCount;
    long dwgOpenEndCount;
    long docCloseBeginCount;
    long docCloseWillStartCount;
    long closeAllBeginCount;
    long quitBeginCount;
    long quitWillStartCount;
    long layoutSwitchedCount;
    long fullRegenEndedCount;
    long pickfirstModifiedCount;
    long doubleClickCount;
    long rightClickCount;
    bool lastSysVarChangeSuccess;
    std::string lastCommand;
    std::string lastUnknownCommand;
    std::string lastLisp;
    std::string lastSysVar;
    std::string lastDwgFile;
    std::string lastLayout;

    M08MEditorMonitorReactor() { reset(); }

    void reset()
    {
        commandStartCount = 0;
        commandEndCount = 0;
        commandCancelCount = 0;
        commandFailedCount = 0;
        unknownCommandCount = 0;
        lispStartCount = 0;
        lispEndCount = 0;
        lispCancelCount = 0;
        sysVarWillChangeCount = 0;
        sysVarChangedCount = 0;
        sysVarChangedSuccessCount = 0;
        dwgOpenBeginCount = 0;
        dwgOpenEndCount = 0;
        docCloseBeginCount = 0;
        docCloseWillStartCount = 0;
        closeAllBeginCount = 0;
        quitBeginCount = 0;
        quitWillStartCount = 0;
        layoutSwitchedCount = 0;
        fullRegenEndedCount = 0;
        pickfirstModifiedCount = 0;
        doubleClickCount = 0;
        rightClickCount = 0;
        lastSysVarChangeSuccess = false;
        lastCommand.clear();
        lastUnknownCommand.clear();
        lastLisp.clear();
        lastSysVar.clear();
        lastDwgFile.clear();
        lastLayout.clear();
    }

    void unknownCommand(const ACHAR* cmdStr, AcDbVoidPtrArray*) override
    {
        ++unknownCommandCount;
        lastUnknownCommand = m08mTextOrEmpty(cmdStr);
    }
    void commandWillStart(const ACHAR* cmdStr) override
    {
        ++commandStartCount;
        lastCommand = m08mTextOrEmpty(cmdStr);
    }
    void commandEnded(const ACHAR* cmdStr) override
    {
        ++commandEndCount;
        lastCommand = m08mTextOrEmpty(cmdStr);
    }
    void commandCancelled(const ACHAR* cmdStr) override
    {
        ++commandCancelCount;
        lastCommand = m08mTextOrEmpty(cmdStr);
    }
    void commandFailed(const ACHAR* cmdStr) override
    {
        ++commandFailedCount;
        lastCommand = m08mTextOrEmpty(cmdStr);
    }
    void lispWillStart(const ACHAR* firstLine) override
    {
        ++lispStartCount;
        lastLisp = m08mTextOrEmpty(firstLine);
    }
    void lispEnded() override { ++lispEndCount; }
    void lispCancelled() override { ++lispCancelCount; }
    void beginDwgOpen(const ACHAR* filename) override
    {
        ++dwgOpenBeginCount;
        lastDwgFile = m08mTextOrEmpty(filename);
    }
    void endDwgOpen(const ACHAR* filename, AcDbDatabase*) override
    {
        ++dwgOpenEndCount;
        lastDwgFile = m08mTextOrEmpty(filename);
    }
    void beginDocClose(AcDbDatabase*) override { ++docCloseBeginCount; }
    void docCloseWillStart(AcDbDatabase*) override { ++docCloseWillStartCount; }
    void beginCloseAll() override { ++closeAllBeginCount; }
    void beginQuit() override { ++quitBeginCount; }
    void quitWillStart() override { ++quitWillStartCount; }
    void layoutSwitched(const ACHAR* newLayoutName) override
    {
        ++layoutSwitchedCount;
        lastLayout = m08mTextOrEmpty(newLayoutName);
    }
    void fullRegenEnded(AcDbDatabase*, const AcDbIntArray&) override { ++fullRegenEndedCount; }
    void sysVarWillChange(const ACHAR* varName) override
    {
        ++sysVarWillChangeCount;
        lastSysVar = m08mTextOrEmpty(varName);
    }
    void sysVarChanged(const ACHAR* varName, bool success) override
    {
        ++sysVarChangedCount;
        if (success)
            ++sysVarChangedSuccessCount;
        lastSysVar = m08mTextOrEmpty(varName);
        lastSysVarChangeSuccess = success;
    }
    void pickfirstModified() override { ++pickfirstModifiedCount; }
    void beginDoubleClick(const AcGePoint3d&) override { ++doubleClickCount; }
    void beginRightClick(const AcGePoint3d&) override { ++rightClickCount; }
};

class M08MDocManagerMonitorReactor : public AcApDocManagerReactor
{
public:
    long documentCreateStartedCount;
    long documentCreatedCount;
    long documentToBeDestroyedCount;
    long documentDestroyedCount;
    long documentCreateCanceledCount;
    long lockModeWillChangeCount;
    long lockModeChangedCount;
    long lockModeVetoedCount;
    long documentBecameCurrentCount;
    long documentToBeActivatedCount;
    long documentToBeDeactivatedCount;
    long documentActivationModifiedCount;
    long documentActivatedCount;
    long documentTitleUpdatedCount;
    bool lastActivationEnabled;
    std::string lastDocumentFile;
    std::string lastDocumentTitle;
    std::string lastDestroyedFile;
    std::string lastGlobalCommand;

    M08MDocManagerMonitorReactor() { reset(); }

    void reset()
    {
        documentCreateStartedCount = 0;
        documentCreatedCount = 0;
        documentToBeDestroyedCount = 0;
        documentDestroyedCount = 0;
        documentCreateCanceledCount = 0;
        lockModeWillChangeCount = 0;
        lockModeChangedCount = 0;
        lockModeVetoedCount = 0;
        documentBecameCurrentCount = 0;
        documentToBeActivatedCount = 0;
        documentToBeDeactivatedCount = 0;
        documentActivationModifiedCount = 0;
        documentActivatedCount = 0;
        documentTitleUpdatedCount = 0;
        lastActivationEnabled = false;
        lastDocumentFile.clear();
        lastDocumentTitle.clear();
        lastDestroyedFile.clear();
        lastGlobalCommand.clear();
    }

    void captureDoc(AcApDocument* pDoc)
    {
        lastDocumentFile = m08mDocFileName(pDoc);
        lastDocumentTitle = m08mDocTitle(pDoc);
    }

    void documentCreateStarted(AcApDocument* pDocCreating) override
    {
        ++documentCreateStartedCount;
        captureDoc(pDocCreating);
    }
    void documentCreated(AcApDocument* pDocCreating) override
    {
        ++documentCreatedCount;
        captureDoc(pDocCreating);
    }
    void documentToBeDestroyed(AcApDocument* pDocToDestroy) override
    {
        ++documentToBeDestroyedCount;
        captureDoc(pDocToDestroy);
    }
    void documentDestroyed(const ACHAR* fileName) override
    {
        ++documentDestroyedCount;
        lastDestroyedFile = m08mTextOrEmpty(fileName);
    }
    void documentCreateCanceled(AcApDocument* pDocCreateCancelled) override
    {
        ++documentCreateCanceledCount;
        captureDoc(pDocCreateCancelled);
    }
    void documentLockModeWillChange(AcApDocument* pDoc, AcAp::DocLockMode, AcAp::DocLockMode,
                                    AcAp::DocLockMode, const ACHAR* pGlobalCmdName) override
    {
        ++lockModeWillChangeCount;
        captureDoc(pDoc);
        lastGlobalCommand = m08mTextOrEmpty(pGlobalCmdName);
    }
    void documentLockModeChangeVetoed(AcApDocument* pDoc, const ACHAR* pGlobalCmdName) override
    {
        ++lockModeVetoedCount;
        captureDoc(pDoc);
        lastGlobalCommand = m08mTextOrEmpty(pGlobalCmdName);
    }
    void documentLockModeChanged(AcApDocument* pDoc, AcAp::DocLockMode, AcAp::DocLockMode,
                                 AcAp::DocLockMode, const ACHAR* pGlobalCmdName) override
    {
        ++lockModeChangedCount;
        captureDoc(pDoc);
        lastGlobalCommand = m08mTextOrEmpty(pGlobalCmdName);
    }
    void documentBecameCurrent(AcApDocument* pDoc) override
    {
        ++documentBecameCurrentCount;
        captureDoc(pDoc);
    }
    void documentToBeActivated(AcApDocument* pActivatingDoc) override
    {
        ++documentToBeActivatedCount;
        captureDoc(pActivatingDoc);
    }
    void documentToBeDeactivated(AcApDocument* pDeActivatedDoc) override
    {
        ++documentToBeDeactivatedCount;
        captureDoc(pDeActivatedDoc);
    }
    void documentActivationModified(bool bActivation) override
    {
        ++documentActivationModifiedCount;
        lastActivationEnabled = bActivation;
    }
    void documentActivated(AcApDocument* pActivatedDoc) override
    {
        ++documentActivatedCount;
        captureDoc(pActivatedDoc);
    }
    void documentTitleUpdated(AcApDocument* pDoc) override
    {
        ++documentTitleUpdatedCount;
        captureDoc(pDoc);
    }
};

class M08MLongTransactionMonitorReactor : public AcApLongTransactionReactor
{
public:
    long beginCheckOutCount;
    long endCheckOutCount;
    long beginCheckInCount;
    long endCheckInCount;
    long abortLongTransactionCount;

    M08MLongTransactionMonitorReactor() { reset(); }

    void reset()
    {
        beginCheckOutCount = 0;
        endCheckOutCount = 0;
        beginCheckInCount = 0;
        endCheckInCount = 0;
        abortLongTransactionCount = 0;
    }

    void beginCheckOut(AcDbLongTransaction&, AcDbObjectIdArray&) override { ++beginCheckOutCount; }
    void endCheckOut(AcDbLongTransaction&) override { ++endCheckOutCount; }
    void beginCheckIn(AcDbLongTransaction&) override { ++beginCheckInCount; }
    void endCheckIn(AcDbLongTransaction&) override { ++endCheckInCount; }
    void abortLongTransaction(AcDbLongTransaction&) override { ++abortLongTransactionCount; }
};

static M08MEditorMonitorReactor* gM08MEditorMonitor = nullptr;
static M08MDocManagerMonitorReactor* gM08MDocManagerMonitor = nullptr;
static M08MLongTransactionMonitorReactor* gM08MLongTransactionMonitor = nullptr;

static bool m08mEnableEditorMonitor(bool& created)
{
    created = false;
    if (gM08MEditorMonitor != nullptr)
        return true;
    if (acedEditor == nullptr)
        return false;
    gM08MEditorMonitor = new M08MEditorMonitorReactor();
    if (gM08MEditorMonitor == nullptr)
        return false;
    acedEditor->addReactor(gM08MEditorMonitor);
    created = true;
    return true;
}

static bool m08mDisableEditorMonitor(bool& removed)
{
    removed = false;
    if (gM08MEditorMonitor == nullptr)
        return true;
    if (acedEditor != nullptr)
        acedEditor->removeReactor(gM08MEditorMonitor);
    delete gM08MEditorMonitor;
    gM08MEditorMonitor = nullptr;
    removed = true;
    return true;
}

static bool m08mEnableDocManagerMonitor(bool& created)
{
    created = false;
    if (gM08MDocManagerMonitor != nullptr)
        return true;
    if (acDocManager == nullptr)
        return false;
    gM08MDocManagerMonitor = new M08MDocManagerMonitorReactor();
    if (gM08MDocManagerMonitor == nullptr)
        return false;
    acDocManager->addReactor(gM08MDocManagerMonitor);
    created = true;
    return true;
}

static bool m08mDisableDocManagerMonitor(bool& removed)
{
    removed = false;
    if (gM08MDocManagerMonitor == nullptr)
        return true;
    if (acDocManager != nullptr)
        acDocManager->removeReactor(gM08MDocManagerMonitor);
    delete gM08MDocManagerMonitor;
    gM08MDocManagerMonitor = nullptr;
    removed = true;
    return true;
}

static bool m08mEnableLongTransactionMonitor(bool& created)
{
    created = false;
    if (gM08MLongTransactionMonitor != nullptr)
        return true;
    if (acapLongTransactionManager == nullptr)
        return false;
    gM08MLongTransactionMonitor = new M08MLongTransactionMonitorReactor();
    if (gM08MLongTransactionMonitor == nullptr)
        return false;
    acapLongTransactionManager->addReactor(gM08MLongTransactionMonitor);
    created = true;
    return true;
}

static bool m08mDisableLongTransactionMonitor(bool& removed)
{
    removed = false;
    if (gM08MLongTransactionMonitor == nullptr)
        return true;
    if (acapLongTransactionManager != nullptr)
        acapLongTransactionManager->removeReactor(gM08MLongTransactionMonitor);
    delete gM08MLongTransactionMonitor;
    gM08MLongTransactionMonitor = nullptr;
    removed = true;
    return true;
}

struct M08MEditorSnapshot
{
    long commandStartCount;
    long commandEndCount;
    long commandCancelCount;
    long commandFailedCount;
    long unknownCommandCount;
    long lispStartCount;
    long lispEndCount;
    long lispCancelCount;
    long sysVarWillChangeCount;
    long sysVarChangedCount;
    long sysVarChangedSuccessCount;
    long dwgOpenBeginCount;
    long dwgOpenEndCount;
    long docCloseBeginCount;
    long docCloseWillStartCount;
    long closeAllBeginCount;
    long quitBeginCount;
    long quitWillStartCount;
    long layoutSwitchedCount;
    long fullRegenEndedCount;
    long pickfirstModifiedCount;
    long doubleClickCount;
    long rightClickCount;
    bool lastSysVarChangeSuccess;
    std::string lastCommand;
    std::string lastUnknownCommand;
    std::string lastLisp;
    std::string lastSysVar;
    std::string lastDwgFile;
    std::string lastLayout;

    M08MEditorSnapshot()
        : commandStartCount(0), commandEndCount(0), commandCancelCount(0), commandFailedCount(0),
          unknownCommandCount(0), lispStartCount(0), lispEndCount(0), lispCancelCount(0),
          sysVarWillChangeCount(0), sysVarChangedCount(0), sysVarChangedSuccessCount(0),
          dwgOpenBeginCount(0), dwgOpenEndCount(0), docCloseBeginCount(0), docCloseWillStartCount(0),
          closeAllBeginCount(0), quitBeginCount(0), quitWillStartCount(0), layoutSwitchedCount(0),
          fullRegenEndedCount(0), pickfirstModifiedCount(0), doubleClickCount(0), rightClickCount(0),
          lastSysVarChangeSuccess(false)
    {
    }
};

static M08MEditorSnapshot m08mTakeEditorSnapshot()
{
    M08MEditorSnapshot s;
    if (gM08MEditorMonitor == nullptr)
        return s;
    s.commandStartCount = gM08MEditorMonitor->commandStartCount;
    s.commandEndCount = gM08MEditorMonitor->commandEndCount;
    s.commandCancelCount = gM08MEditorMonitor->commandCancelCount;
    s.commandFailedCount = gM08MEditorMonitor->commandFailedCount;
    s.unknownCommandCount = gM08MEditorMonitor->unknownCommandCount;
    s.lispStartCount = gM08MEditorMonitor->lispStartCount;
    s.lispEndCount = gM08MEditorMonitor->lispEndCount;
    s.lispCancelCount = gM08MEditorMonitor->lispCancelCount;
    s.sysVarWillChangeCount = gM08MEditorMonitor->sysVarWillChangeCount;
    s.sysVarChangedCount = gM08MEditorMonitor->sysVarChangedCount;
    s.sysVarChangedSuccessCount = gM08MEditorMonitor->sysVarChangedSuccessCount;
    s.dwgOpenBeginCount = gM08MEditorMonitor->dwgOpenBeginCount;
    s.dwgOpenEndCount = gM08MEditorMonitor->dwgOpenEndCount;
    s.docCloseBeginCount = gM08MEditorMonitor->docCloseBeginCount;
    s.docCloseWillStartCount = gM08MEditorMonitor->docCloseWillStartCount;
    s.closeAllBeginCount = gM08MEditorMonitor->closeAllBeginCount;
    s.quitBeginCount = gM08MEditorMonitor->quitBeginCount;
    s.quitWillStartCount = gM08MEditorMonitor->quitWillStartCount;
    s.layoutSwitchedCount = gM08MEditorMonitor->layoutSwitchedCount;
    s.fullRegenEndedCount = gM08MEditorMonitor->fullRegenEndedCount;
    s.pickfirstModifiedCount = gM08MEditorMonitor->pickfirstModifiedCount;
    s.doubleClickCount = gM08MEditorMonitor->doubleClickCount;
    s.rightClickCount = gM08MEditorMonitor->rightClickCount;
    s.lastSysVarChangeSuccess = gM08MEditorMonitor->lastSysVarChangeSuccess;
    s.lastCommand = gM08MEditorMonitor->lastCommand;
    s.lastUnknownCommand = gM08MEditorMonitor->lastUnknownCommand;
    s.lastLisp = gM08MEditorMonitor->lastLisp;
    s.lastSysVar = gM08MEditorMonitor->lastSysVar;
    s.lastDwgFile = gM08MEditorMonitor->lastDwgFile;
    s.lastLayout = gM08MEditorMonitor->lastLayout;
    return s;
}

struct M08MDocManagerSnapshot
{
    long documentCreateStartedCount;
    long documentCreatedCount;
    long documentToBeDestroyedCount;
    long documentDestroyedCount;
    long documentCreateCanceledCount;
    long lockModeWillChangeCount;
    long lockModeChangedCount;
    long lockModeVetoedCount;
    long documentBecameCurrentCount;
    long documentToBeActivatedCount;
    long documentToBeDeactivatedCount;
    long documentActivationModifiedCount;
    long documentActivatedCount;
    long documentTitleUpdatedCount;
    bool lastActivationEnabled;
    std::string lastDocumentFile;
    std::string lastDocumentTitle;
    std::string lastDestroyedFile;
    std::string lastGlobalCommand;

    M08MDocManagerSnapshot()
        : documentCreateStartedCount(0), documentCreatedCount(0), documentToBeDestroyedCount(0),
          documentDestroyedCount(0), documentCreateCanceledCount(0), lockModeWillChangeCount(0),
          lockModeChangedCount(0), lockModeVetoedCount(0), documentBecameCurrentCount(0),
          documentToBeActivatedCount(0), documentToBeDeactivatedCount(0),
          documentActivationModifiedCount(0), documentActivatedCount(0), documentTitleUpdatedCount(0),
          lastActivationEnabled(false)
    {
    }
};

static M08MDocManagerSnapshot m08mTakeDocManagerSnapshot()
{
    M08MDocManagerSnapshot s;
    if (gM08MDocManagerMonitor == nullptr)
        return s;
    s.documentCreateStartedCount = gM08MDocManagerMonitor->documentCreateStartedCount;
    s.documentCreatedCount = gM08MDocManagerMonitor->documentCreatedCount;
    s.documentToBeDestroyedCount = gM08MDocManagerMonitor->documentToBeDestroyedCount;
    s.documentDestroyedCount = gM08MDocManagerMonitor->documentDestroyedCount;
    s.documentCreateCanceledCount = gM08MDocManagerMonitor->documentCreateCanceledCount;
    s.lockModeWillChangeCount = gM08MDocManagerMonitor->lockModeWillChangeCount;
    s.lockModeChangedCount = gM08MDocManagerMonitor->lockModeChangedCount;
    s.lockModeVetoedCount = gM08MDocManagerMonitor->lockModeVetoedCount;
    s.documentBecameCurrentCount = gM08MDocManagerMonitor->documentBecameCurrentCount;
    s.documentToBeActivatedCount = gM08MDocManagerMonitor->documentToBeActivatedCount;
    s.documentToBeDeactivatedCount = gM08MDocManagerMonitor->documentToBeDeactivatedCount;
    s.documentActivationModifiedCount = gM08MDocManagerMonitor->documentActivationModifiedCount;
    s.documentActivatedCount = gM08MDocManagerMonitor->documentActivatedCount;
    s.documentTitleUpdatedCount = gM08MDocManagerMonitor->documentTitleUpdatedCount;
    s.lastActivationEnabled = gM08MDocManagerMonitor->lastActivationEnabled;
    s.lastDocumentFile = gM08MDocManagerMonitor->lastDocumentFile;
    s.lastDocumentTitle = gM08MDocManagerMonitor->lastDocumentTitle;
    s.lastDestroyedFile = gM08MDocManagerMonitor->lastDestroyedFile;
    s.lastGlobalCommand = gM08MDocManagerMonitor->lastGlobalCommand;
    return s;
}

struct M08MLongTransactionSnapshot
{
    long beginCheckOutCount;
    long endCheckOutCount;
    long beginCheckInCount;
    long endCheckInCount;
    long abortLongTransactionCount;

    M08MLongTransactionSnapshot()
        : beginCheckOutCount(0), endCheckOutCount(0), beginCheckInCount(0),
          endCheckInCount(0), abortLongTransactionCount(0)
    {
    }
};

static M08MLongTransactionSnapshot m08mTakeLongTransactionSnapshot()
{
    M08MLongTransactionSnapshot s;
    if (gM08MLongTransactionMonitor == nullptr)
        return s;
    s.beginCheckOutCount = gM08MLongTransactionMonitor->beginCheckOutCount;
    s.endCheckOutCount = gM08MLongTransactionMonitor->endCheckOutCount;
    s.beginCheckInCount = gM08MLongTransactionMonitor->beginCheckInCount;
    s.endCheckInCount = gM08MLongTransactionMonitor->endCheckInCount;
    s.abortLongTransactionCount = gM08MLongTransactionMonitor->abortLongTransactionCount;
    return s;
}

// Scratch-mutate a freshly appended transient AcDbLine inside the caller's (uncommitted) staged
// transaction so DB/object reactors fire. Appends a line to model space, opens it for write, nudges
// a property (modified), then erases it (erased). All rolled back by the caller's txn dtor (no
// commit). Reactors must be attached by the caller BEFORE calling this. pObjReactor (optional) is
// attached to the line as a per-object reactor and detached before the line closes. Returns the
// appended line's id (or null on failure).
static AcDbObjectId m08mScratchMutate(AcDbDatabase* pDb, M08MObjReactor* pObjReactor)
{
    AcDbObjectId lineId = AcDbObjectId::kNull;
    AcDbBlockTable* pBT = nullptr;
    if (pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk)
        return lineId;
    AcDbBlockTableRecord* pMS = nullptr;
    const Acad::ErrorStatus btrEs = pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite);
    pBT->close();
    if (btrEs != Acad::eOk || pMS == nullptr)
        return lineId;
    AcDbLine* pLine = new AcDbLine(AcGePoint3d(0.0, 0.0, 0.0), AcGePoint3d(1.0, 1.0, 0.0));
    if (pMS->appendAcDbEntity(lineId, pLine) != Acad::eOk) {
        delete pLine;
        pMS->close();
        return AcDbObjectId::kNull;
    }
    pMS->close();
    // Attach the per-object reactor now that the object is DB-resident.
    if (pObjReactor != nullptr)
        pLine->addReactor(pObjReactor);
    pLine->close();
    // Re-open for write and modify (fires modified), then erase (fires erased).
    AcDbEntity* pEnt = nullptr;
    if (acdbOpenObject(pEnt, lineId, AcDb::kForWrite) == Acad::eOk && pEnt != nullptr) {
        AcDbLine* pL2 = AcDbLine::cast(pEnt);
        if (pL2 != nullptr)
            pL2->setEndPoint(AcGePoint3d(2.0, 2.0, 0.0));   // mutate -> modified
        pEnt->erase(true);                                   // erase -> erased
        // Detach the per-object reactor before closing (we own the reactor lifetime).
        if (pObjReactor != nullptr)
            pEnt->removeReactor(pObjReactor);
        pEnt->close();
    }
    return lineId;
}

//============================================================================
// HasOp — every op id this family IMPLEMENTS (gate admission). Kept in lockstep
// with the dispatch branches below (asserted by tests/unit/test_m08m_handlers.py).
//============================================================================
static bool m08mHasOp(const std::string& op)
{
    return
        // --- T01 property inspection (AcRxProperty / AcRxMember read over an AcRxClass) ---
        op == "inspect.property.by_name" ||
        op == "inspect.property.is_readonly" ||
        op == "inspect.property.metadata" ||
        op == "inspect.entity.properties" ||
        op == "inspect.members.promoted" ||
        op == "inspect.value.to_string" ||
        op == "extend.members.facet_provider" ||
        op == "automate.com.bridge_objectid" ||
        op == "automate.com.hold_objectref" ||
        op == "automate.com.entity_helpers" ||
        op == "automate.com.objectid_from_iunknown" ||
        op == "automate.com.lock_document" ||
        op == "automate.property.set" ||
        // --- T01 OPM protocol (register/query the OPM property protocol on a class — hostless) ---
        op == "extend.opm.register_provider" ||
        op == "extend.opm.get_manager" ||
        op == "extend.opm.get_dispid" ||
        op == "extend.opm.map_category" ||
        op == "extend.opm.define_property" ||
        op == "extend.opm.define_property2" ||
        op == "extend.opm.enum_property" ||
        op == "extend.opm.dialog_property" ||
        op == "extend.opm.per_instance_source" ||
        op == "extend.opm.property_expander" ||
        op == "extend.opm.property_expression" ||
        op == "extend.opm.property_extension" ||
        // --- T01 property authoring (AcRxAttribute build + attach to a transient class) ---
        op == "extend.property.define" ||
        op == "extend.property.describe" ||
        op == "extend.property.category" ||
        op == "extend.property.display_as" ||
        op == "extend.property.units" ||
        op == "extend.property.flags" ||
        op == "extend.property.default_value" ||
        op == "extend.property.enum_tag" ||
        op == "extend.property.refers_to" ||
        op == "extend.property.localize_name" ||
        op == "extend.property.com_name" ||
        op == "extend.property.expose_to_com" ||
        op == "extend.property.filepath" ||
        op == "extend.property.define_collection" ||
        op == "extend.property.define_dictionary" ||
        op == "extend.property.define_indexed" ||
        op == "extend.property.overrule" ||
        // --- T02 reactors (hostless DB/object + full-host editor/docmanager/longtx) ---
        op == "react.database.attach" ||
        op == "react.database.monitor" ||
        op == "react.object.attach_transient" ||
        op == "react.object.detach_transient" ||
        op == "react.object.monitor" ||
        op == "react.entity.monitor" ||
        op == "react.persistent.attach" ||
        op == "react.persistent.detach" ||
        op == "react.rxevent.attach" ||
        op == "react.rxevent.monitor" ||
        op == "react.linker.attach" ||
        op == "react.linker.monitor" ||
        op == "react.docmanager.attach" ||
        op == "react.docmanager.monitor" ||
        op == "react.editor.command_monitor" ||
        op == "react.editor.dwg_lifecycle" ||
        op == "react.editor.input_monitor" ||
        op == "react.editor.lisp_monitor" ||
        op == "react.editor.sysvar_monitor" ||
        op == "react.longtx.attach" ||
        op == "react.longtx.monitor" ||
        op == "react.config.disable_namespace" ||
        false;
}

//============================================================================
// Dispatch — handle the op (append result + status, return true) or return false.
//============================================================================
static bool m08mDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    if (!m08mHasOp(op))
        return false;

    AcDbDatabase* pDb = ctx.pDb;        // working (router-staged) database; non-null (gated upstream)
    const std::string& job = ctx.job;   // raw job JSON (arg parsing via jsonFind*)

    //========================================================================
    // T01 — property inspection (read the dynamic property protocol over a class)
    //========================================================================

    // inspect.property.by_name — find a property on a class by name; report its type.
    // Class defaults to AcDbEntity (rich property set). Pure class-system read.
    if (op == "inspect.property.by_name") {
        std::string clsName, propName;
        m08mFindStr(job, "class", clsName);
        if (!m08mFindStr(job, "property", propName)) propName = "Layer";  // a stable AcDbEntity prop
        AcRxClass* cls = m08mResolveClass(clsName);
        if (cls == nullptr) {
            emitNativeError(r, "CLASS_NOT_RESOLVED", "class '" + clsName + "' is not resolvable in this module");
            return true;
        }
        const std::wstring wprop = asciiToWide(propName);
        const AcRxProperty* prop = m08mFindClassProperty(cls, wprop.c_str());
        std::ostringstream o; o.precision(kJsonDoublePrecision);
        o << "\"class\":" << njsonStr(clsName.empty() ? std::string("AcDbEntity") : clsName)
          << ",\"property\":" << njsonStr(propName)
          << ",\"found\":" << (prop != nullptr ? "true" : "false");
        if (prop != nullptr)
            o << ",\"value_type\":" << m08mValueTypeName(prop->type());
        r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
        return true;
    }

    // inspect.property.is_readonly — AcRxProperty::isReadOnly for a class's property, evaluated
    // against the object behind a handle when provided (the protocol takes the instance). When no
    // handle is given, reports the flag against a null instance.
    if (op == "inspect.property.is_readonly") {
        std::string clsName, propName, handle;
        m08mFindStr(job, "class", clsName);
        if (!m08mFindStr(job, "property", propName)) propName = "Area";   // typically read-only
        AcRxClass* cls = m08mResolveClass(clsName);
        if (cls == nullptr) {
            emitNativeError(r, "CLASS_NOT_RESOLVED", "class '" + clsName + "' is not resolvable");
            return true;
        }
        const std::wstring wprop = asciiToWide(propName);
        const AcRxProperty* prop = m08mFindClassProperty(cls, wprop.c_str());
        if (prop == nullptr) {
            r << "\"result\":{\"class\":" << njsonStr(clsName.empty() ? std::string("AcDbEntity") : clsName)
              << ",\"property\":" << njsonStr(propName) << ",\"found\":false},\"status\":\"ok\"}";
            return true;
        }
        AcRxObject* pInstance = nullptr;
        AcDbObject* pDbObj = nullptr;
        if (m08mFindHandle(job, handle)) {
            AcDbObjectId id;
            if (resolveHandle(pDb, handle, id))
                acdbOpenObject(pDbObj, id, AcDb::kForRead);
            pInstance = pDbObj;
        }
        const bool readOnly = prop->isReadOnly(pInstance);
        if (pDbObj != nullptr) pDbObj->close();
        r << "\"result\":{\"class\":" << njsonStr(clsName.empty() ? std::string("AcDbEntity") : clsName)
          << ",\"property\":" << njsonStr(propName)
          << ",\"found\":true,\"read_only\":" << (readOnly ? "true" : "false")
          << ",\"evaluated_on_instance\":" << (pInstance != nullptr ? "true" : "false")
          << "},\"status\":\"ok\"}";
        return true;
    }

    // inspect.property.metadata — full member metadata over a class: per-property name, value type,
    // attribute count + the registered attribute type names (the OPM-relevant metadata). Bounded to
    // the first 64 properties. Pure class-system read.
    if (op == "inspect.property.metadata") {
        std::string clsName;
        m08mFindStr(job, "class", clsName);
        AcRxClass* cls = m08mResolveClass(clsName);
        if (cls == nullptr) {
            emitNativeError(r, "CLASS_NOT_RESOLVED", "class '" + clsName + "' is not resolvable");
            return true;
        }
        AcRxMemberCollection* members = cls->members();
        const int n = (members != nullptr) ? members->count() : 0;
        int emitted = 0;
        std::ostringstream props; props.precision(kJsonDoublePrecision);
        for (int i = 0; i < n && emitted < 64; ++i) {
            AcRxMember* m = members->getAt(i);
            const AcRxProperty* prop = (m != nullptr) ? AcRxProperty::cast(m) : nullptr;
            if (prop == nullptr)
                continue;
            const AcRxAttributeCollection& attrs = prop->attributes();
            const int ac = attrs.count();
            if (emitted) props << ",";
            props << "{\"name\":" << njsonStr(prop->name())
                  << ",\"value_type\":" << m08mValueTypeName(prop->type())
                  << ",\"attribute_count\":" << ac
                  << ",\"attributes\":[";
            for (int a = 0; a < ac; ++a) {
                const AcRxAttribute* at = attrs.getAt(a);
                if (a) props << ",";
                props << njsonStr((at != nullptr && at->isA() != nullptr) ? at->isA()->name() : ACRX_T(""));
            }
            props << "]}";
            ++emitted;
        }
        r << "\"result\":{\"class\":" << njsonStr(clsName.empty() ? std::string("AcDbEntity") : clsName)
          << ",\"member_count\":" << n << ",\"property_count_emitted\":" << emitted
          << ",\"properties\":[" << props.str() << "]},\"status\":\"ok\"}";
        return true;
    }

    // inspect.entity.properties / inspect.members.promoted / extend.members.facet_provider —
    // reflective member/property walk over an entity instance (or AcDbEntity class default). Pure read.
    if (op == "inspect.entity.properties" || op == "inspect.members.promoted" || op == "extend.members.facet_provider") {
        std::string handle;
        AcDbObject* pObj = nullptr;
        AcRxClass* cls = AcDbEntity::desc();
        bool instance = false;
        if (m08mFindHandle(job, handle)) {
            AcDbObjectId id;
            if (resolveHandle(pDb, handle, id) && acdbOpenObject(pObj, id, AcDb::kForRead) == Acad::eOk && pObj != nullptr) {
                cls = pObj->isA();
                instance = true;
            }
        }
        AcRxMemberCollection* members = (cls != nullptr) ? cls->members() : nullptr;
        const int n = (members != nullptr) ? members->count() : 0;
        int props = 0, promoted = 0;
        std::ostringstream arr; arr.precision(kJsonDoublePrecision);
        for (int i = 0; i < n && props < 96; ++i) {
            AcRxMember* m = members->getAt(i);
            const AcRxProperty* prop = (m != nullptr) ? AcRxProperty::cast(m) : nullptr;
            if (prop == nullptr)
                continue;
            if (props) arr << ",";
            arr << "{\"name\":" << njsonStr(prop->name())
                << ",\"value_type\":" << m08mValueTypeName(prop->type())
                << ",\"read_only\":" << (prop->isReadOnly(pObj) ? "true" : "false");
            if (pObj != nullptr) {
                AcRxValue val;
                if (prop->getValue(pObj, val) == Acad::eOk) {
                    ACHAR buf[512] = {0};
                    val.toString(buf, 512);
                    arr << ",\"value_string\":" << njsonStr(buf);
                }
            }
            arr << "}";
            ++props;
            if (prop->attributes().count() > 0)
                ++promoted;
        }
        if (pObj != nullptr) pObj->close();
        r << "\"result\":{\"class\":" << njsonStr((cls != nullptr && cls->name() != nullptr) ? cls->name() : ACRX_T(""))
          << ",\"instance\":" << (instance ? "true" : "false")
          << ",\"member_count\":" << n
          << ",\"property_count\":" << props
          << ",\"promoted_member_count\":" << promoted
          << ",\"properties\":[" << arr.str() << "]},\"status\":\"ok\"}";
        return true;
    }

    // inspect.value.to_string — use the AcRxValue protocol on a string value or an object property.
    if (op == "inspect.value.to_string") {
        std::string value;
        if (!m08mFindStr(job, "value", value)) value = "ARIADNE";
        const std::wstring wv = asciiToWide(value);
        AcRxValue rxv(static_cast<const ACHAR*>(wv.c_str()));
        ACHAR buf[512] = {0};
        rxv.toString(buf, 512);
        r << "\"result\":{\"input\":" << njsonStr(value)
          << ",\"value_string\":" << njsonStr(buf)
          << ",\"value_type\":" << m08mValueTypeName(rxv.type())
          << "},\"status\":\"ok\"}";
        return true;
    }

    // ObjectARX/COM bridge-adjacent read probes: no IDispatch is exposed; the safe bridge
    // surface is handle <-> AcDbObjectId/object pointer within this call.
    if (op == "automate.com.bridge_objectid" || op == "automate.com.hold_objectref" ||
        op == "automate.com.entity_helpers" || op == "automate.com.objectid_from_iunknown") {
        std::string handle;
        if (!m08mFindHandle(job, handle)) {
            AcDbObjectId cid = pDb->currentSpaceId();
            handle = handleOfId(cid);
        }
        AcDbObjectId id;
        const bool resolved = resolveHandle(pDb, handle, id);
        AcDbObject* pObj = nullptr;
        Acad::ErrorStatus es = Acad::eNullObjectId;
        if (resolved)
            es = acdbOpenObject(pObj, id, AcDb::kForRead);
        bool isEnt = false;
        std::string cls;
        if (pObj != nullptr) {
            isEnt = (AcDbEntity::cast(pObj) != nullptr);
            if (pObj->isA() != nullptr && pObj->isA()->name() != nullptr) cls = acharToAscii(pObj->isA()->name());
            pObj->close();
        }
        r << "\"result\":{\"handle\":" << njsonStr(handle)
          << ",\"resolved_objectid\":" << (resolved ? "true" : "false")
          << ",\"object_opened\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"class\":" << njsonStr(cls)
          << ",\"is_entity\":" << (isEnt ? "true" : "false")
          << ",\"com_dispatch_exposed\":false"
          << ",\"errorstatus\":" << static_cast<int>(es)
          << "},\"status\":\"ok\"}";
        return true;
    }

    // automate.com.lock_document — exercise the existing RAII lock helper. In Core Console
    // there may be no document manager; that is reported honestly without surfacing SendCommand.
    if (op == "automate.com.lock_document") {
        AriadneDocumentWriteLock lock;
        r << "\"result\":{\"attempted\":true,\"host_mode\":" << njsonStr(ctx.hostMode)
          << ",\"sendcommand_exposed\":false,\"dwg_persisted\":false},\"status\":\"ok\"}";
        return true;
    }

    // automate.property.set — set a value property on the object behind a handle via the property
    // protocol, then read it back to PROVE the protocol round-trips. Staged-write: the set runs in a
    // staged transaction that is rolled back (dtor abort) so the original is never mutated. If the
    // property is read-only / not found / set fails, the result carries the honest status (no fake ok).
    if (op == "automate.property.set") {
        std::string handle, propName, newValStr;
        if (!m08mFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "automate.property.set requires 'handle'");
            return true;
        }
        if (!m08mFindStr(job, "property", propName)) propName = "Layer";
        m08mFindStr(job, "value", newValStr);   // optional
        if (newValStr.empty()) newValStr = "0"; // layer "0" always exists
        AcDbObjectId id;
        if (!resolveHandle(pDb, handle, id)) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "no object for handle " + handle);
            return true;
        }
        AriadneStagedWriteTransaction wt(pDb);   // dtor rolls back (we never commit)
        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, id, AcDb::kForWrite) != Acad::eOk || pObj == nullptr) {
            emitNativeError(r, "OPEN_FAILED", "could not open object for write: " + handle);
            return true;
        }
        AcRxClass* cls = pObj->isA();
        const std::wstring wprop = asciiToWide(propName);
        const AcRxProperty* prop = m08mFindClassProperty(cls, wprop.c_str());
        if (prop == nullptr) {
            pObj->close();
            r << "\"result\":{\"handle\":" << njsonStr(handle) << ",\"property\":" << njsonStr(propName)
              << ",\"found\":false},\"status\":\"error\"}";
            return true;
        }
        const bool readOnly = prop->isReadOnly(pObj);
        // Read the original value (string form) for the report.
        AcRxValue beforeVal;
        std::string beforeStr;
        if (prop->getValue(pObj, beforeVal) == Acad::eOk) {
            ACHAR buf[512] = {0};
            beforeVal.toString(buf, 512);
            beforeStr = acharToAscii(buf);
        }
        // Attempt the set via the property protocol, boxing the incoming string as the property's
        // ACTUAL declared AcRxValueType (m08mBoxPropertyValue) -- never a generic ACHAR* guess.
        AcRxValue newVal;
        std::string marshalNote;
        bool boxed = false;
        Acad::ErrorStatus setEs = Acad::eNotApplicable;   // default: read-only guard result
        if (!readOnly) {
            boxed = m08mBoxPropertyValue(prop->type(), newValStr, newVal, marshalNote);
            if (boxed)
                setEs = prop->setValue(pObj, newVal);
            else
                // Never call setValue with a mismatched box: eNotImplemented = this handler doesn't
                // marshal the property's type yet; eInvalidInput = the type is supported but the
                // supplied string didn't parse for it. Either way, an honest gap, not a fake attempt.
                setEs = marshalNote.empty() ? Acad::eNotImplemented : Acad::eInvalidInput;
        }
        // Read back.
        AcRxValue afterVal;
        std::string afterStr;
        if (prop->getValue(pObj, afterVal) == Acad::eOk) {
            ACHAR buf[512] = {0};
            afterVal.toString(buf, 512);
            afterStr = acharToAscii(buf);
        }
        pObj->close();
        // wt dtor rolls everything back here.
        const bool ok = (setEs == Acad::eOk);
        r << "\"result\":{\"handle\":" << njsonStr(handle)
          << ",\"property\":" << njsonStr(propName)
          << ",\"found\":true,\"read_only\":" << (readOnly ? "true" : "false")
          << ",\"value_type\":" << m08mValueTypeName(prop->type())
          << ",\"before\":" << njsonStr(beforeStr)
          << ",\"requested\":" << njsonStr(newValStr)
          << ",\"after\":" << njsonStr(afterStr)
          << ",\"set_status\":" << static_cast<int>(setEs);
        if (!readOnly) {
            r << ",\"marshalled\":" << (boxed ? "true" : "false");
            if (!marshalNote.empty())
                r << ",\"marshal_note\":" << njsonStr(marshalNote);
        }
        r << ",\"staged_rolled_back\":true"
          << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    //========================================================================
    // T01 — OPM protocol (register/query the OPM property protocol on a class).
    // The OPM property protocol IS the AcRxProperty member protocol on an AcRxClass; "register a
    // provider / manager / dispid / category" map onto the property-member + attribute machinery.
    // We exercise that machinery hostless on a transient runtime class, then tear it down. The COM
    // IPropertyManager / palette surface is attended — NOT built here (honest).
    //========================================================================

    // extend.opm.register_provider / property_extension — prove the OPM provider/extension
    // registration path: build a transient class, attach an AcRxGenerateDynamicPropertiesAttribute
    // (the COM/OPM property-provider opt-in), read it back, tear down. Real attribute attach.
    if (op == "extend.opm.register_provider" ||
        op == "extend.opm.property_extension") {
        std::string cname;
        AcRxClass* cls = m08mNewTransientClass(op.substr(op.rfind('.') + 1), cname);
        if (cls == nullptr) {
            emitNativeError(r, "NEWACRXCLASS_FAILED", "could not create transient class for " + op);
            return true;
        }
        AcRxAttribute* attr = new AcRxGenerateDynamicPropertiesAttribute();
        const Acad::ErrorStatus addEs = cls->attributes().add(attr);  // collection takes ownership
        const AcRxAttribute* readBack =
            cls->attributes().get(AcRxGenerateDynamicPropertiesAttribute::desc());
        const bool attached = (addEs == Acad::eOk) && (readBack != nullptr);
        deleteAcRxClass(cls);
        acrxBuildClassHierarchy();
        r << "\"result\":{\"op\":" << njsonStr(op) << ",\"transient_class\":" << njsonStr(cname)
          << ",\"attribute\":\"AcRxGenerateDynamicPropertiesAttribute\""
          << ",\"add_status\":" << static_cast<int>(addEs)
          << ",\"attached\":" << (attached ? "true" : "false")
          << "},\"status\":\"" << (attached ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.opm.get_manager / get_dispid — the OPM "manager"/"dispid" introspection: report the
    // property-member machinery for a class (member query engine availability + property count).
    // The hostless analog of "which manager owns these props / what dispids exist".
    if (op == "extend.opm.get_manager" || op == "extend.opm.get_dispid") {
        std::string clsName;
        m08mFindStr(job, "class", clsName);
        AcRxClass* cls = m08mResolveClass(clsName);
        if (cls == nullptr) {
            emitNativeError(r, "CLASS_NOT_RESOLVED", "class '" + clsName + "' is not resolvable");
            return true;
        }
        int propCount = 0, memberCount = 0;
        m08mCountClassProperties(cls, propCount, memberCount);
        AcRxMemberQueryEngine* engine = AcRxMemberQueryEngine::theEngine();
        r << "\"result\":{\"op\":" << njsonStr(op)
          << ",\"class\":" << njsonStr(clsName.empty() ? std::string("AcDbEntity") : clsName)
          << ",\"query_engine_available\":" << (engine != nullptr ? "true" : "false")
          << ",\"property_count\":" << propCount
          << ",\"member_count\":" << memberCount
          << "},\"status\":\"" << (engine != nullptr ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.opm.map_category — attach an AcRxUiPlacementAttribute (the OPM category/weight mapping)
    // to a transient class, read it back, tear down. Real category-mapping attribute attach.
    if (op == "extend.opm.map_category") {
        std::string category;
        if (!m08mFindStr(job, "category", category)) category = "Ariadne";
        std::string cname;
        AcRxClass* cls = m08mNewTransientClass("opm_category", cname);
        if (cls == nullptr) {
            emitNativeError(r, "NEWACRXCLASS_FAILED", "could not create transient class");
            return true;
        }
        const std::wstring wcat = asciiToWide(category);
        AcRxAttribute* attr = new AcRxUiPlacementAttribute(wcat.c_str(), 100);
        const Acad::ErrorStatus addEs = cls->attributes().add(attr);
        const AcRxAttribute* readBack = cls->attributes().get(AcRxUiPlacementAttribute::desc());
        const bool ok = (addEs == Acad::eOk) && (readBack != nullptr);
        deleteAcRxClass(cls);
        acrxBuildClassHierarchy();
        r << "\"result\":{\"transient_class\":" << njsonStr(cname)
          << ",\"category\":" << njsonStr(category)
          << ",\"attribute\":\"AcRxUiPlacementAttribute\""
          << ",\"add_status\":" << static_cast<int>(addEs)
          << ",\"attached\":" << (ok ? "true" : "false")
          << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.opm.define_property / define_property2 / enum_property / dialog_property /
    // per_instance_source / property_expander / property_expression — these OPM property-definition
    // variants all register an OPM property on a class. Hostless: we prove the registration machinery
    // by building a transient class, attaching the variant-appropriate authoring attribute, reading
    // it back, and tearing down. (Defining a NEW COMPILED property body at runtime is impossible; the
    // attribute attach on a real descriptor is the honest hostless proof — like M08K's class ops.)
    if (op == "extend.opm.define_property" || op == "extend.opm.define_property2" ||
        op == "extend.opm.enum_property" || op == "extend.opm.dialog_property" ||
        op == "extend.opm.per_instance_source" || op == "extend.opm.property_expander" ||
        op == "extend.opm.property_expression") {
        std::string cname;
        AcRxClass* cls = m08mNewTransientClass(op.substr(op.rfind('.') + 1), cname);
        if (cls == nullptr) {
            emitNativeError(r, "NEWACRXCLASS_FAILED", "could not create transient class for " + op);
            return true;
        }
        AcRxAttribute* attr = nullptr;
        const AcRxClass* attrDesc = nullptr;
        const char* attrName = "";
        if (op == "extend.opm.dialog_property") {
            attr = new AcRxFilePathAttribute();   // dialog-bound property (file/dialog editor)
            attrDesc = AcRxFilePathAttribute::desc();
            attrName = "AcRxFilePathAttribute";
        } else if (op == "extend.opm.per_instance_source") {
            attr = new AcRxGenerateDynamicPropertiesAttribute();  // per-instance dynamic source
            attrDesc = AcRxGenerateDynamicPropertiesAttribute::desc();
            attrName = "AcRxGenerateDynamicPropertiesAttribute";
        } else if (op == "extend.opm.property_expander" || op == "extend.opm.property_expression") {
            std::string refers; if (!m08mFindStr(job, "refers_to", refers)) refers = "Owner/Name";
            const std::wstring wref = asciiToWide(refers);
            attr = new AcRxRefersToAttribute(wref.c_str());  // expander/expression reference path
            attrDesc = AcRxRefersToAttribute::desc();
            attrName = "AcRxRefersToAttribute";
        } else {
            // define_property / define_property2 / enum_property -> a description-tagged property
            std::string desc; if (!m08mFindStr(job, "description", desc)) desc = "Ariadne OPM property";
            const std::wstring wdesc = asciiToWide(desc);
            attr = new AcRxDescriptionAttribute(wdesc.c_str());
            attrDesc = AcRxDescriptionAttribute::desc();
            attrName = "AcRxDescriptionAttribute";
        }
        const Acad::ErrorStatus addEs = cls->attributes().add(attr);
        const AcRxAttribute* readBack = cls->attributes().get(attrDesc);
        const bool ok = (addEs == Acad::eOk) && (readBack != nullptr);
        deleteAcRxClass(cls);
        acrxBuildClassHierarchy();
        r << "\"result\":{\"op\":" << njsonStr(op) << ",\"transient_class\":" << njsonStr(cname)
          << ",\"attribute\":" << njsonStr(std::string(attrName))
          << ",\"add_status\":" << static_cast<int>(addEs)
          << ",\"attached\":" << (ok ? "true" : "false")
          << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    //========================================================================
    // T01 — property authoring (build a concrete AcRxAttribute and attach it to a transient class's
    // attribute collection; read it back; tear down). Each op exercises its specific attribute type.
    //========================================================================
    if (op == "extend.property.define" || op == "extend.property.describe" ||
        op == "extend.property.category" || op == "extend.property.display_as" ||
        op == "extend.property.units" || op == "extend.property.flags" ||
        op == "extend.property.default_value" || op == "extend.property.enum_tag" ||
        op == "extend.property.refers_to" || op == "extend.property.localize_name" ||
        op == "extend.property.com_name" || op == "extend.property.expose_to_com" ||
        op == "extend.property.filepath" || op == "extend.property.define_collection" ||
        op == "extend.property.define_dictionary" || op == "extend.property.define_indexed" ||
        op == "extend.property.overrule") {
        std::string cname;
        AcRxClass* cls = m08mNewTransientClass(op.substr(op.rfind('.') + 1), cname);
        if (cls == nullptr) {
            emitNativeError(r, "NEWACRXCLASS_FAILED", "could not create transient class for " + op);
            return true;
        }

        // enum_tag builds an AcRxEnumTag MEMBER (not a class attribute); attaching it to the class
        // member collection is callback-only, so we construct it + introspect its name (a real
        // AcRxEnumTag object), then delete it via AcRxMember::deleteMember. Honest object-lifecycle proof.
        if (op == "extend.property.enum_tag") {
            std::string tag; if (!m08mFindStr(job, "tag", tag)) tag = "AriadneTag";
            double tagVal = 1.0; jsonFindNumber(job, "value", tagVal);
            const std::wstring w = asciiToWide(tag);
            AcRxValue v(tagVal);
            AcRxEnumTag* et = new AcRxEnumTag(w.c_str(), v);
            const bool built = (et != nullptr) && (et->name() != nullptr);
            std::string nameBack = built ? acharToAscii(et->name()) : std::string();
            AcRxMember::deleteMember(et);   // proper AcRxMember teardown (sends goodbye)
            deleteAcRxClass(cls);
            acrxBuildClassHierarchy();
            r << "\"result\":{\"op\":" << njsonStr(op) << ",\"transient_class\":" << njsonStr(cname)
              << ",\"enum_tag\":\"AcRxEnumTag\",\"tag_name\":" << njsonStr(nameBack)
              << ",\"built\":" << (built ? "true" : "false")
              << "},\"status\":\"" << (built ? "ok" : "error") << "\"}";
            return true;
        }

        AcRxAttribute* attr = nullptr;
        const AcRxClass* attrDesc = nullptr;
        const char* attrName = "";
        // Build the variant-specific attribute (verified ctors from rxattrib.h).
        if (op == "extend.property.describe" || op == "extend.property.define") {
            std::string desc; if (!m08mFindStr(job, "text", desc)) desc = "Ariadne property";
            const std::wstring w = asciiToWide(desc);
            attr = new AcRxDescriptionAttribute(w.c_str());
            attrDesc = AcRxDescriptionAttribute::desc(); attrName = "AcRxDescriptionAttribute";
        } else if (op == "extend.property.category") {
            std::string cat; if (!m08mFindStr(job, "category", cat)) cat = "Ariadne";
            const std::wstring w = asciiToWide(cat);
            attr = new AcRxUiPlacementAttribute(w.c_str(), 100);
            attrDesc = AcRxUiPlacementAttribute::desc(); attrName = "AcRxUiPlacementAttribute";
        } else if (op == "extend.property.display_as") {
            std::string nm; if (!m08mFindStr(job, "name", nm)) nm = "Ariadne Display";
            const std::wstring w = asciiToWide(nm);
            attr = new AcRxDisplayAsAttribute(w.c_str());
            attrDesc = AcRxDisplayAsAttribute::desc(); attrName = "AcRxDisplayAsAttribute";
        } else if (op == "extend.property.units") {
            attr = new AcRxUnitTypeAttribute(AcRxUnitTypeAttribute::kDistance);
            attrDesc = AcRxUnitTypeAttribute::desc(); attrName = "AcRxUnitTypeAttribute";
        } else if (op == "extend.property.flags") {
            attr = new AcRxFlagsAttribute();
            attrDesc = AcRxFlagsAttribute::desc(); attrName = "AcRxFlagsAttribute";
        } else if (op == "extend.property.default_value") {
            double dv = 0.0; jsonFindNumber(job, "value", dv);
            AcRxValue v(dv);
            attr = new AcRxDefaultValueAttribute(v);
            attrDesc = AcRxDefaultValueAttribute::desc(); attrName = "AcRxDefaultValueAttribute";
        } else if (op == "extend.property.refers_to") {
            std::string path; if (!m08mFindStr(job, "path", path)) path = "Owner/Name";
            const std::wstring w = asciiToWide(path);
            attr = new AcRxRefersToAttribute(w.c_str());
            attrDesc = AcRxRefersToAttribute::desc(); attrName = "AcRxRefersToAttribute";
        } else if (op == "extend.property.localize_name") {
            double idRaw = 1.0; jsonFindNumber(job, "resource_id", idRaw);
            attr = new AcRxLocalizedNameAttribute(static_cast<unsigned int>(idRaw));
            attrDesc = AcRxLocalizedNameAttribute::desc(); attrName = "AcRxLocalizedNameAttribute";
        } else if (op == "extend.property.com_name" || op == "extend.property.expose_to_com") {
            std::string nm; if (!m08mFindStr(job, "name", nm)) nm = "AriadneComProp";
            const std::wstring w = asciiToWide(nm);
            attr = new AcRxCOMAttribute(w.c_str());
            attrDesc = AcRxCOMAttribute::desc(); attrName = "AcRxCOMAttribute";
        } else if (op == "extend.property.filepath") {
            attr = new AcRxFilePathAttribute();
            attrDesc = AcRxFilePathAttribute::desc(); attrName = "AcRxFilePathAttribute";
        } else if (op == "extend.property.define_collection" || op == "extend.property.define_dictionary" ||
                   op == "extend.property.define_indexed" || op == "extend.property.overrule") {
            std::string desc = "Ariadne collection/indexed property protocol proof";
            const std::wstring w = asciiToWide(desc);
            attr = new AcRxDescriptionAttribute(w.c_str());
            attrDesc = AcRxDescriptionAttribute::desc(); attrName = "AcRxDescriptionAttribute";
        }
        if (attr == nullptr) {   // defensive: every branch above sets attr
            deleteAcRxClass(cls);
            acrxBuildClassHierarchy();
            emitNativeError(r, "ATTRIBUTE_BUILD_FAILED", "no attribute built for " + op);
            return true;
        }
        const Acad::ErrorStatus addEs = cls->attributes().add(attr);
        const AcRxAttribute* readBack = cls->attributes().get(attrDesc);
        const bool ok = (addEs == Acad::eOk) && (readBack != nullptr);
        deleteAcRxClass(cls);
        acrxBuildClassHierarchy();
        r << "\"result\":{\"op\":" << njsonStr(op) << ",\"transient_class\":" << njsonStr(cname)
          << ",\"attribute\":" << njsonStr(std::string(attrName))
          << ",\"add_status\":" << static_cast<int>(addEs)
          << ",\"attached\":" << (ok ? "true" : "false")
          << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    //========================================================================
    // T02 — reactors (hostless attach + fire). DB/object reactors fire on an in-transaction
    // modify/erase of a scratch entity; the staged txn dtor rolls everything back.
    //========================================================================

    // react.database.attach — attach an AcDbDatabaseReactor to ctx.pDb and prove attach/detach
    // (no mutation; pure lifecycle). Always removeReactor before return.
    if (op == "react.database.attach") {
        static M08MDbReactor s_dbReactor;
        s_dbReactor.reset();
        const Acad::ErrorStatus addEs = pDb->addReactor(&s_dbReactor);
        const Acad::ErrorStatus remEs = pDb->removeReactor(&s_dbReactor);
        const bool ok = (addEs == Acad::eOk) && (remEs == Acad::eOk);
        r << "\"result\":{\"reactor\":\"AcDbDatabaseReactor\""
          << ",\"add_status\":" << static_cast<int>(addEs)
          << ",\"remove_status\":" << static_cast<int>(remEs)
          << ",\"attached_and_detached\":" << (ok ? "true" : "false")
          << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    // react.database.monitor — attach a db reactor, run a scratch modify+erase inside a rolled-back
    // staged txn, and report the FIRED callback counts (objectAppended / objectModified /
    // objectErased). Real proof the reactor fires hostless. Detach before return; mutation rolled back.
    if (op == "react.database.monitor") {
        static M08MDbReactor s_dbReactor;
        s_dbReactor.reset();
        const Acad::ErrorStatus addEs = pDb->addReactor(&s_dbReactor);
        long firedModified = 0, firedErased = 0, firedAppended = 0;
        if (addEs == Acad::eOk) {
            AriadneStagedWriteTransaction wt(pDb);   // dtor rolls back
            m08mScratchMutate(pDb, nullptr);
            firedModified = s_dbReactor.modifiedCount;
            firedErased = s_dbReactor.erasedCount;
            firedAppended = s_dbReactor.appendedCount;
            // wt dtor aborts here (rollback) — BEFORE we detach below.
        }
        const Acad::ErrorStatus remEs = pDb->removeReactor(&s_dbReactor);
        const bool fired = (firedAppended > 0) || (firedModified > 0) || (firedErased > 0);
        r << "\"result\":{\"reactor\":\"AcDbDatabaseReactor\""
          << ",\"add_status\":" << static_cast<int>(addEs)
          << ",\"remove_status\":" << static_cast<int>(remEs)
          << ",\"fired_appended\":" << firedAppended
          << ",\"fired_modified\":" << firedModified
          << ",\"fired_erased\":" << firedErased
          << ",\"callback_fired\":" << (fired ? "true" : "false")
          << ",\"staged_rolled_back\":true"
          << "},\"status\":\"" << ((addEs == Acad::eOk && fired) ? "ok" : "error") << "\"}";
        return true;
    }

    // react.object.attach_transient / detach_transient — attach a transient AcDbObjectReactor to a
    // scratch entity (appended in a rolled-back staged txn) and prove attach (hasReactor) then
    // detach. attach_transient asserts the attach; detach_transient asserts the post-detach state.
    if (op == "react.object.attach_transient" || op == "react.object.detach_transient") {
        const bool detachVariant = (op == "react.object.detach_transient");
        static M08MObjReactor s_objReactor;
        s_objReactor.reset();
        AriadneStagedWriteTransaction wt(pDb);   // dtor rolls back the scratch entity
        AcDbObjectId lineId = AcDbObjectId::kNull;
        bool attached = false, detached = false;
        AcDbBlockTable* pBT = nullptr;
        if (pDb->getBlockTable(pBT, AcDb::kForRead) == Acad::eOk) {
            AcDbBlockTableRecord* pMS = nullptr;
            if (pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite) == Acad::eOk && pMS != nullptr) {
                AcDbLine* pLine = new AcDbLine(AcGePoint3d(0, 0, 0), AcGePoint3d(1, 0, 0));
                if (pMS->appendAcDbEntity(lineId, pLine) == Acad::eOk) {
                    pLine->addReactor(&s_objReactor);
                    attached = pLine->hasReactor(&s_objReactor);
                    pLine->close();
                    AcDbEntity* pEnt = nullptr;
                    if (acdbOpenObject(pEnt, lineId, AcDb::kForWrite) == Acad::eOk && pEnt != nullptr) {
                        pEnt->removeReactor(&s_objReactor);
                        detached = !pEnt->hasReactor(&s_objReactor);
                        pEnt->close();
                    }
                } else {
                    delete pLine;
                }
                pMS->close();
            }
            pBT->close();
        }
        // wt dtor rolls back here.
        const bool ok = detachVariant ? (attached && detached) : attached;
        r << "\"result\":{\"reactor\":\"AcDbObjectReactor\""
          << ",\"attached\":" << (attached ? "true" : "false")
          << ",\"detached\":" << (detached ? "true" : "false")
          << ",\"staged_rolled_back\":true"
          << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    // react.object.monitor — attach a transient object reactor to a scratch entity, modify+erase it
    // (rolled-back staged txn), report fired counts (modified / erased). Real per-object callback proof.
    if (op == "react.object.monitor" || op == "react.entity.monitor") {
        static M08MObjReactor s_objReactor;
        s_objReactor.reset();
        long firedModified = 0, firedErased = 0;
        {
            AriadneStagedWriteTransaction wt(pDb);   // dtor rolls back
            m08mScratchMutate(pDb, &s_objReactor);   // attaches s_objReactor to the scratch line
            firedModified = s_objReactor.modifiedCount;
            firedErased = s_objReactor.erasedCount;
            // wt dtor aborts here (rollback).
        }
        const bool fired = (firedModified > 0) || (firedErased > 0);
        r << "\"result\":{\"reactor\":\"AcDbObjectReactor\""
          << ",\"fired_modified\":" << firedModified
          << ",\"fired_erased\":" << firedErased
          << ",\"callback_fired\":" << (fired ? "true" : "false")
          << ",\"staged_rolled_back\":true"
          << "},\"status\":\"" << (fired ? "ok" : "error") << "\"}";
        return true;
    }

    // react.persistent.attach / detach — append two scratch AcDbLines (source + target); the source
    // gets addPersistentReactor(targetId); prove hasPersistentReactor; then removePersistentReactor.
    // Staged + rolled back. attach asserts the attach; detach asserts the post-detach state.
    if (op == "react.persistent.attach" || op == "react.persistent.detach") {
        const bool detachVariant = (op == "react.persistent.detach");
        AriadneStagedWriteTransaction wt(pDb);   // dtor rolls back both scratch objects
        bool attached = false, detached = false;
        Acad::ErrorStatus addEs = Acad::eNotApplicable, remEs = Acad::eNotApplicable;
        AcDbBlockTable* pBT = nullptr;
        if (pDb->getBlockTable(pBT, AcDb::kForRead) == Acad::eOk) {
            AcDbBlockTableRecord* pMS = nullptr;
            if (pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite) == Acad::eOk && pMS != nullptr) {
                AcDbObjectId srcId, tgtId;
                AcDbLine* pSrc = new AcDbLine(AcGePoint3d(0, 0, 0), AcGePoint3d(1, 0, 0));
                AcDbLine* pTgt = new AcDbLine(AcGePoint3d(0, 1, 0), AcGePoint3d(1, 1, 0));
                const bool srcOk = (pMS->appendAcDbEntity(srcId, pSrc) == Acad::eOk);
                if (srcOk) pSrc->close(); else delete pSrc;
                const bool tgtOk = (pMS->appendAcDbEntity(tgtId, pTgt) == Acad::eOk);
                if (tgtOk) pTgt->close(); else delete pTgt;
                if (srcOk && tgtOk) {
                    AcDbObject* pSrcObj = nullptr;
                    if (acdbOpenObject(pSrcObj, srcId, AcDb::kForWrite) == Acad::eOk && pSrcObj != nullptr) {
                        addEs = pSrcObj->addPersistentReactor(tgtId);
                        attached = (addEs == Acad::eOk) && pSrcObj->hasPersistentReactor(tgtId);
                        remEs = pSrcObj->removePersistentReactor(tgtId);
                        detached = (remEs == Acad::eOk) && !pSrcObj->hasPersistentReactor(tgtId);
                        pSrcObj->close();
                    }
                }
                pMS->close();
            }
            pBT->close();
        }
        // wt dtor rolls back here.
        const bool ok = detachVariant ? (attached && detached) : attached;
        r << "\"result\":{\"reactor\":\"persistent(AcDbObjectId)\""
          << ",\"add_status\":" << static_cast<int>(addEs)
          << ",\"remove_status\":" << static_cast<int>(remEs)
          << ",\"attached\":" << (attached ? "true" : "false")
          << ",\"detached\":" << (detached ? "true" : "false")
          << ",\"staged_rolled_back\":true"
          << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    // react.rxevent.attach — attach an AcRxEventReactor to the system AcRxEvent registry; prove
    // attach/detach. Always detach before return.
    if (op == "react.rxevent.attach") {
        AcRxEvent* ev = acrxEvent;
        if (ev == nullptr) {
            emitNativeError(r, "RXEVENT_UNAVAILABLE", "system AcRxEvent registry not available");
            return true;
        }
        static M08MRxEventReactor s_rxReactor;
        s_rxReactor.reset();
        ev->addReactor(&s_rxReactor);
        ev->removeReactor(&s_rxReactor);
        r << "\"result\":{\"reactor\":\"AcRxEventReactor\",\"attached_and_detached\":true"
          << "},\"status\":\"ok\"}";
        return true;
    }

    // react.rxevent.monitor — attach an AcRxEventReactor, then CONSTRUCT a transient AcDbDatabase
    // (fires databaseConstructed) and let it destruct (fires databaseToBeDestroyed); report fired
    // counts. Real Rx-event callback proof, hostless. Detach before return.
    if (op == "react.rxevent.monitor") {
        AcRxEvent* ev = acrxEvent;
        if (ev == nullptr) {
            emitNativeError(r, "RXEVENT_UNAVAILABLE", "system AcRxEvent registry not available");
            return true;
        }
        static M08MRxEventReactor s_rxReactor;
        s_rxReactor.reset();
        ev->addReactor(&s_rxReactor);
        long firedConstructed = 0, firedDestroyed = 0;
        {
            // Transient DB on the stack: ctor fires databaseConstructed; dtor fires
            // databaseToBeDestroyed. buildDefaultDrawing=false keeps it minimal.
            AcDbDatabase scratchDb(/*buildDefaultDrawing*/ false, /*noDocument*/ true);
            firedConstructed = s_rxReactor.constructedCount;
            // dtor runs at end of scope.
        }
        firedDestroyed = s_rxReactor.destroyedCount;
        ev->removeReactor(&s_rxReactor);
        const bool fired = (firedConstructed > 0) || (firedDestroyed > 0);
        r << "\"result\":{\"reactor\":\"AcRxEventReactor\""
          << ",\"fired_constructed\":" << firedConstructed
          << ",\"fired_destroyed\":" << firedDestroyed
          << ",\"callback_fired\":" << (fired ? "true" : "false")
          << "},\"status\":\"" << (fired ? "ok" : "error") << "\"}";
        return true;
    }

    // react.linker.attach / monitor — attach an AcRxDLinkerReactor to the system dynamic linker and
    // prove attach/detach. We do NOT load/unload a module in a hostless probe (that is an app/IO
    // action), so "monitor" reports the attach lifecycle rather than a fired load callback (honest:
    // no fake firing). Both detach before return.
    if (op == "react.linker.attach" || op == "react.linker.monitor") {
        AcRxDynamicLinker* linker = acrxDynamicLinker;
        if (linker == nullptr) {
            emitNativeError(r, "LINKER_UNAVAILABLE", "system AcRxDynamicLinker not available");
            return true;
        }
        static M08MLinkerReactor s_linkReactor;
        linker->addReactor(&s_linkReactor);
        linker->removeReactor(&s_linkReactor);
        const bool monitorVariant = (op == "react.linker.monitor");
        r << "\"result\":{\"reactor\":\"AcRxDLinkerReactor\",\"attached_and_detached\":true";
        if (monitorVariant)
            r << ",\"note\":\"load/unload not triggered in hostless probe (attach lifecycle only)\"";
        r << "},\"status\":\"ok\"}";
        return true;
    }

    // react.editor.* — full-host editor reactors. These keep transient process registration state
    // only (enable/disable + unload cleanup) and report real counts accumulated by a shared
    // AcEditorReactor. `execute=1` enables bounded safe probes where possible.
    if (op == "react.editor.command_monitor" || op == "react.editor.dwg_lifecycle" ||
        op == "react.editor.input_monitor" || op == "react.editor.lisp_monitor" ||
        op == "react.editor.sysvar_monitor") {
        const bool supported = m08mFullAutoCadHost(ctx) && acedEditor != nullptr;
        const bool enableRequested = m08mBoolArg(job, "enabled", true);
        const bool resetRequested = m08mBoolArg(job, "reset", false);
        const bool execute = m08mBoolArg(job, "execute", false);
        if (!supported) {
            r << "\"result\":{\"op\":" << njsonStr(op)
              << ",\"host_mode\":" << njsonStr(ctx.hostMode)
              << ",\"supported\":false"
              << ",\"registered\":" << (gM08MEditorMonitor != nullptr ? "true" : "false")
              << ",\"execute_requested\":" << (execute ? "true" : "false")
              << ",\"attended_editor_required\":true"
              << ",\"reason\":" << njsonStr(std::string("Full AutoCAD editor host required for AcEditorReactor callbacks"))
              << "},\"status\":\"ok\"}";
            return true;
        }

        bool changed = false;
        if (!enableRequested) {
            const M08MEditorSnapshot snap = m08mTakeEditorSnapshot();
            if (!m08mDisableEditorMonitor(changed)) {
                emitNativeError(r, "EDITOR_REACTOR_DISABLE_FAILED", "failed to unregister M08M editor monitor reactor");
                return true;
            }
            r << "\"result\":{\"op\":" << njsonStr(op)
              << ",\"host_mode\":" << njsonStr(ctx.hostMode)
              << ",\"supported\":true"
              << ",\"enabled_requested\":false"
              << ",\"changed\":" << (changed ? "true" : "false")
              << ",\"registered\":false"
              << ",\"command_starts\":" << snap.commandStartCount
              << ",\"command_ends\":" << snap.commandEndCount
              << ",\"lisp_starts\":" << snap.lispStartCount
              << ",\"sysvar_changed\":" << snap.sysVarChangedCount
              << ",\"pickfirst_modified\":" << snap.pickfirstModifiedCount
              << ",\"note\":" << njsonStr(std::string("Editor monitor detached; counts report the last accumulated values before cleanup."))
              << "},\"status\":\"ok\"}";
            return true;
        }

        if (!m08mEnableEditorMonitor(changed) || gM08MEditorMonitor == nullptr) {
            emitNativeError(r, "EDITOR_REACTOR_ENABLE_FAILED", "failed to register M08M editor monitor reactor");
            return true;
        }
        if (resetRequested)
            gM08MEditorMonitor->reset();

        const char* probeName = "none";
        bool probeAttempted = false;
        int probeStatus = RTNONE;
        int probeRestoreStatus = RTNONE;
        bool probeFoundEntity = false;
        bool probeFreedSelection = false;
        if (execute && op == "react.editor.input_monitor") {
            probeName = "pickfirst";
            probeAttempted = true;
            AcDbObjectId id;
            probeFoundEntity = m08mFirstEntityId(pDb, id);
            if (probeFoundEntity) {
                ads_name en;
                if (acdbGetAdsName(en, id) == Acad::eOk) {
                    ads_name ss;
                    probeStatus = acedSSAdd(en, NULL, ss);
                    if (probeStatus == RTNORM) {
                        acedSSSetFirst(NULL, ss);
                        probeRestoreStatus = acedSSSetFirst(NULL, NULL);
                        acedSSFree(ss);
                        probeFreedSelection = true;
                    }
                }
            }
        } else if (execute && op == "react.editor.sysvar_monitor") {
            probeName = "CMDECHO";
            probeAttempted = true;
            struct resbuf current = {};
            probeStatus = acedGetVar(ACRX_T("CMDECHO"), &current);
            if (probeStatus == RTNORM && resbufCodeIsInt16(current.restype)) {
                struct resbuf next = current;
                next.resval.rint = (current.resval.rint == 0 ? 1 : 0);
                probeStatus = acedSetVar(ACRX_T("CMDECHO"), &next);
                probeRestoreStatus = acedSetVar(ACRX_T("CMDECHO"), &current);
            } else if (probeStatus == RTNORM && resbufCodeIsInt32(current.restype)) {
                struct resbuf next = current;
                next.resval.rlong = (current.resval.rlong == 0 ? 1 : 0);
                probeStatus = acedSetVar(ACRX_T("CMDECHO"), &next);
                probeRestoreStatus = acedSetVar(ACRX_T("CMDECHO"), &current);
            }
        }

        const M08MEditorSnapshot snap = m08mTakeEditorSnapshot();
        bool fired = false;
        std::string note;
        if (op == "react.editor.command_monitor") {
            fired = (snap.commandStartCount + snap.commandEndCount + snap.commandCancelCount +
                     snap.commandFailedCount + snap.unknownCommandCount) > 0;
            note = "Counts accumulate from live attended command traffic; no raw command was injected by this handler.";
        } else if (op == "react.editor.lisp_monitor") {
            fired = (snap.lispStartCount + snap.lispEndCount + snap.lispCancelCount) > 0;
            note = "Counts accumulate from live attended AutoLISP evaluation; no synthetic LISP dispatch is issued here.";
        } else if (op == "react.editor.sysvar_monitor") {
            fired = (snap.sysVarWillChangeCount + snap.sysVarChangedCount) > 0;
            note = execute
                ? std::string("CMDECHO was toggled and restored to exercise sysvar callbacks.")
                : std::string("Set execute=1 under full AutoCAD to run the bounded CMDECHO round-trip probe.");
        } else if (op == "react.editor.input_monitor") {
            fired = (snap.pickfirstModifiedCount + snap.doubleClickCount + snap.rightClickCount) > 0;
            note = execute
                ? std::string("Pickfirst selection was toggled to exercise pickfirstModified without invoking raw commands.")
                : std::string("Set execute=1 under full AutoCAD to run the bounded pickfirst probe.");
        } else {
            fired = (snap.dwgOpenBeginCount + snap.dwgOpenEndCount + snap.docCloseBeginCount +
                     snap.docCloseWillStartCount + snap.closeAllBeginCount + snap.quitBeginCount +
                     snap.quitWillStartCount + snap.layoutSwitchedCount + snap.fullRegenEndedCount) > 0;
            note = "Counts accumulate from attended drawing/session lifecycle events; no synthetic open/close/quit action is issued here.";
        }

        r << "\"result\":{\"op\":" << njsonStr(op)
          << ",\"host_mode\":" << njsonStr(ctx.hostMode)
          << ",\"supported\":true"
          << ",\"enabled_requested\":true"
          << ",\"changed\":" << (changed ? "true" : "false")
          << ",\"registered\":true"
          << ",\"execute_requested\":" << (execute ? "true" : "false")
          << ",\"counters_reset\":" << (resetRequested ? "true" : "false")
          << ",\"probe_name\":" << njsonStr(std::string(probeName))
          << ",\"probe_attempted\":" << (probeAttempted ? "true" : "false")
          << ",\"probe_status\":" << probeStatus
          << ",\"probe_restore_status\":" << probeRestoreStatus
          << ",\"callback_fired\":" << (fired ? "true" : "false");
        if (op == "react.editor.command_monitor") {
            r << ",\"command_starts\":" << snap.commandStartCount
              << ",\"command_ends\":" << snap.commandEndCount
              << ",\"command_cancelled\":" << snap.commandCancelCount
              << ",\"command_failed\":" << snap.commandFailedCount
              << ",\"unknown_commands\":" << snap.unknownCommandCount
              << ",\"last_command\":" << njsonStr(snap.lastCommand)
              << ",\"last_unknown_command\":" << njsonStr(snap.lastUnknownCommand);
        } else if (op == "react.editor.lisp_monitor") {
            r << ",\"lisp_starts\":" << snap.lispStartCount
              << ",\"lisp_ends\":" << snap.lispEndCount
              << ",\"lisp_cancelled\":" << snap.lispCancelCount
              << ",\"last_lisp\":" << njsonStr(snap.lastLisp);
        } else if (op == "react.editor.sysvar_monitor") {
            r << ",\"sysvar_will_change\":" << snap.sysVarWillChangeCount
              << ",\"sysvar_changed\":" << snap.sysVarChangedCount
              << ",\"sysvar_changed_success\":" << snap.sysVarChangedSuccessCount
              << ",\"last_sysvar\":" << njsonStr(snap.lastSysVar)
              << ",\"last_sysvar_change_success\":" << (snap.lastSysVarChangeSuccess ? "true" : "false");
        } else if (op == "react.editor.input_monitor") {
            r << ",\"pickfirst_modified\":" << snap.pickfirstModifiedCount
              << ",\"double_clicks\":" << snap.doubleClickCount
              << ",\"right_clicks\":" << snap.rightClickCount
              << ",\"probe_found_entity\":" << (probeFoundEntity ? "true" : "false")
              << ",\"probe_freed_selection\":" << (probeFreedSelection ? "true" : "false");
        } else {
            r << ",\"dwg_open_begin\":" << snap.dwgOpenBeginCount
              << ",\"dwg_open_end\":" << snap.dwgOpenEndCount
              << ",\"doc_close_begin\":" << snap.docCloseBeginCount
              << ",\"doc_close_will_start\":" << snap.docCloseWillStartCount
              << ",\"close_all_begin\":" << snap.closeAllBeginCount
              << ",\"quit_begin\":" << snap.quitBeginCount
              << ",\"quit_will_start\":" << snap.quitWillStartCount
              << ",\"layout_switched\":" << snap.layoutSwitchedCount
              << ",\"full_regen_ended\":" << snap.fullRegenEndedCount
              << ",\"last_dwg_file\":" << njsonStr(snap.lastDwgFile)
              << ",\"last_layout\":" << njsonStr(snap.lastLayout);
        }
        r << ",\"note\":" << njsonStr(note)
          << "},\"status\":\"ok\"}";
        return true;
    }

    // react.docmanager.* — persistent MDI document-manager monitor with optional safe current-doc
    // lock/unlock probe for lock-mode callbacks.
    if (op == "react.docmanager.attach" || op == "react.docmanager.monitor") {
        const bool supported = m08mFullAutoCadHost(ctx) && acDocManager != nullptr;
        const bool enableRequested = m08mBoolArg(job, "enabled", true);
        const bool resetRequested = m08mBoolArg(job, "reset", false);
        const bool execute = m08mBoolArg(job, "execute", false);
        AcApDocument* pCurDoc = (acDocManager != nullptr) ? acDocManager->curDocument() : nullptr;
        if (!supported) {
            r << "\"result\":{\"op\":" << njsonStr(op)
              << ",\"host_mode\":" << njsonStr(ctx.hostMode)
              << ",\"supported\":false"
              << ",\"registered\":" << (gM08MDocManagerMonitor != nullptr ? "true" : "false")
              << ",\"current_document_present\":" << (pCurDoc != nullptr ? "true" : "false")
              << ",\"attended_editor_required\":true"
              << ",\"reason\":" << njsonStr(std::string("Full AutoCAD document manager required for AcApDocManagerReactor callbacks"))
              << "},\"status\":\"ok\"}";
            return true;
        }

        bool changed = false;
        if (!enableRequested) {
            const M08MDocManagerSnapshot snap = m08mTakeDocManagerSnapshot();
            if (!m08mDisableDocManagerMonitor(changed)) {
                emitNativeError(r, "DOCMAN_REACTOR_DISABLE_FAILED", "failed to unregister M08M doc-manager monitor reactor");
                return true;
            }
            r << "\"result\":{\"op\":" << njsonStr(op)
              << ",\"host_mode\":" << njsonStr(ctx.hostMode)
              << ",\"supported\":true"
              << ",\"enabled_requested\":false"
              << ",\"changed\":" << (changed ? "true" : "false")
              << ",\"registered\":false"
              << ",\"lockmode_will_change\":" << snap.lockModeWillChangeCount
              << ",\"lockmode_changed\":" << snap.lockModeChangedCount
              << ",\"last_document_file\":" << njsonStr(snap.lastDocumentFile)
              << ",\"note\":" << njsonStr(std::string("Document-manager monitor detached; counts report the last accumulated values before cleanup."))
              << "},\"status\":\"ok\"}";
            return true;
        }

        if (!m08mEnableDocManagerMonitor(changed) || gM08MDocManagerMonitor == nullptr) {
            emitNativeError(r, "DOCMAN_REACTOR_ENABLE_FAILED", "failed to register M08M doc-manager monitor reactor");
            return true;
        }
        if (resetRequested)
            gM08MDocManagerMonitor->reset();

        bool probeAttempted = false;
        int lockStatus = -1;
        bool unlockAttempted = false;
        if (execute && op == "react.docmanager.monitor" && pCurDoc != nullptr) {
            probeAttempted = true;
            const Acad::ErrorStatus es = acDocManager->lockDocument(pCurDoc, AcAp::kWrite);
            lockStatus = static_cast<int>(es);
            if (es == Acad::eOk) {
                acDocManager->unlockDocument(pCurDoc);
                unlockAttempted = true;
            }
        }

        const M08MDocManagerSnapshot snap = m08mTakeDocManagerSnapshot();
        const bool fired = (snap.documentCreateStartedCount + snap.documentCreatedCount +
                            snap.documentToBeDestroyedCount + snap.documentDestroyedCount +
                            snap.lockModeWillChangeCount + snap.lockModeChangedCount +
                            snap.lockModeVetoedCount + snap.documentBecameCurrentCount +
                            snap.documentToBeActivatedCount + snap.documentToBeDeactivatedCount +
                            snap.documentActivationModifiedCount + snap.documentActivatedCount +
                            snap.documentTitleUpdatedCount) > 0;
        const std::string note = (execute && op == "react.docmanager.monitor")
            ? std::string("Current-document lock/unlock probe attempted to exercise document lock-mode callbacks.")
            : std::string("Counts accumulate from attended document lifecycle activity; set execute=1 to run the bounded lock-mode probe.");

        r << "\"result\":{\"op\":" << njsonStr(op)
          << ",\"host_mode\":" << njsonStr(ctx.hostMode)
          << ",\"supported\":true"
          << ",\"enabled_requested\":true"
          << ",\"changed\":" << (changed ? "true" : "false")
          << ",\"registered\":true"
          << ",\"execute_requested\":" << (execute ? "true" : "false")
          << ",\"counters_reset\":" << (resetRequested ? "true" : "false")
          << ",\"probe_attempted\":" << (probeAttempted ? "true" : "false")
          << ",\"probe_lock_status\":" << lockStatus
          << ",\"probe_unlock_attempted\":" << (unlockAttempted ? "true" : "false")
          << ",\"current_document_present\":" << (pCurDoc != nullptr ? "true" : "false")
          << ",\"current_document_file\":" << njsonStr(m08mDocFileName(pCurDoc))
          << ",\"current_document_title\":" << njsonStr(m08mDocTitle(pCurDoc))
          << ",\"callback_fired\":" << (fired ? "true" : "false")
          << ",\"document_create_started\":" << snap.documentCreateStartedCount
          << ",\"document_created\":" << snap.documentCreatedCount
          << ",\"document_to_be_destroyed\":" << snap.documentToBeDestroyedCount
          << ",\"document_destroyed\":" << snap.documentDestroyedCount
          << ",\"document_became_current\":" << snap.documentBecameCurrentCount
          << ",\"document_to_be_activated\":" << snap.documentToBeActivatedCount
          << ",\"document_to_be_deactivated\":" << snap.documentToBeDeactivatedCount
          << ",\"document_activated\":" << snap.documentActivatedCount
          << ",\"lockmode_will_change\":" << snap.lockModeWillChangeCount
          << ",\"lockmode_changed\":" << snap.lockModeChangedCount
          << ",\"lockmode_vetoed\":" << snap.lockModeVetoedCount
          << ",\"title_updated\":" << snap.documentTitleUpdatedCount
          << ",\"last_document_file\":" << njsonStr(snap.lastDocumentFile)
          << ",\"last_document_title\":" << njsonStr(snap.lastDocumentTitle)
          << ",\"last_destroyed_file\":" << njsonStr(snap.lastDestroyedFile)
          << ",\"last_global_command\":" << njsonStr(snap.lastGlobalCommand)
          << ",\"note\":" << njsonStr(note)
          << "},\"status\":\"ok\"}";
        return true;
    }

    // react.longtx.* — long-transaction manager registration and snapshot. The manager exists only
    // in a full AutoCAD application host; real callback firing requires REFEDIT/check-out/check-in.
    if (op == "react.longtx.attach" || op == "react.longtx.monitor") {
        const bool supported = m08mFullAutoCadHost(ctx) && acapLongTransactionManager != nullptr;
        const bool enableRequested = m08mBoolArg(job, "enabled", true);
        const bool resetRequested = m08mBoolArg(job, "reset", false);
        const bool execute = m08mBoolArg(job, "execute", false);
        AcApDocument* pCurDoc = (acDocManager != nullptr) ? acDocManager->curDocument() : nullptr;
        AcDbObjectId currentLtId = (supported && pCurDoc != nullptr)
            ? acapLongTransactionManager->currentLongTransactionFor(pCurDoc)
            : AcDbObjectId::kNull;
        if (!supported) {
            r << "\"result\":{\"op\":" << njsonStr(op)
              << ",\"host_mode\":" << njsonStr(ctx.hostMode)
              << ",\"supported\":false"
              << ",\"registered\":" << (gM08MLongTransactionMonitor != nullptr ? "true" : "false")
              << ",\"attended_editor_required\":true"
              << ",\"reason\":" << njsonStr(std::string("Full AutoCAD long-transaction manager required for AcApLongTransactionReactor callbacks"))
              << "},\"status\":\"ok\"}";
            return true;
        }

        bool changed = false;
        if (!enableRequested) {
            const M08MLongTransactionSnapshot snap = m08mTakeLongTransactionSnapshot();
            if (!m08mDisableLongTransactionMonitor(changed)) {
                emitNativeError(r, "LONGTX_REACTOR_DISABLE_FAILED", "failed to unregister M08M long-transaction monitor reactor");
                return true;
            }
            r << "\"result\":{\"op\":" << njsonStr(op)
              << ",\"host_mode\":" << njsonStr(ctx.hostMode)
              << ",\"supported\":true"
              << ",\"enabled_requested\":false"
              << ",\"changed\":" << (changed ? "true" : "false")
              << ",\"registered\":false"
              << ",\"begin_checkout\":" << snap.beginCheckOutCount
              << ",\"end_checkout\":" << snap.endCheckOutCount
              << ",\"begin_checkin\":" << snap.beginCheckInCount
              << ",\"end_checkin\":" << snap.endCheckInCount
              << ",\"abort_longtx\":" << snap.abortLongTransactionCount
              << ",\"note\":" << njsonStr(std::string("Long-transaction monitor detached; counts report the last accumulated values before cleanup."))
              << "},\"status\":\"ok\"}";
            return true;
        }

        if (!m08mEnableLongTransactionMonitor(changed) || gM08MLongTransactionMonitor == nullptr) {
            emitNativeError(r, "LONGTX_REACTOR_ENABLE_FAILED", "failed to register M08M long-transaction monitor reactor");
            return true;
        }
        if (resetRequested)
            gM08MLongTransactionMonitor->reset();

        const M08MLongTransactionSnapshot snap = m08mTakeLongTransactionSnapshot();
        const bool fired = (snap.beginCheckOutCount + snap.endCheckOutCount +
                            snap.beginCheckInCount + snap.endCheckInCount +
                            snap.abortLongTransactionCount) > 0;
        const std::string note = execute
            ? std::string("No synthetic long-transaction workflow is issued here; counts require live REFEDIT/check-out/check-in activity.")
            : std::string("Set execute=1 only when a dedicated attended host is already in a long-transaction workflow; this handler never fabricates one.");

        r << "\"result\":{\"op\":" << njsonStr(op)
          << ",\"host_mode\":" << njsonStr(ctx.hostMode)
          << ",\"supported\":true"
          << ",\"enabled_requested\":true"
          << ",\"changed\":" << (changed ? "true" : "false")
          << ",\"registered\":true"
          << ",\"execute_requested\":" << (execute ? "true" : "false")
          << ",\"counters_reset\":" << (resetRequested ? "true" : "false")
          << ",\"current_document_present\":" << (pCurDoc != nullptr ? "true" : "false")
          << ",\"current_long_transaction_present\":" << (!currentLtId.isNull() ? "true" : "false")
          << ",\"callback_fired\":" << (fired ? "true" : "false")
          << ",\"begin_checkout\":" << snap.beginCheckOutCount
          << ",\"end_checkout\":" << snap.endCheckOutCount
          << ",\"begin_checkin\":" << snap.beginCheckInCount
          << ",\"end_checkin\":" << snap.endCheckInCount
          << ",\"abort_longtx\":" << snap.abortLongTransactionCount;
        if (!currentLtId.isNull())
            r << ",\"current_long_transaction_handle\":" << njsonStr(handleOfId(currentLtId));
        r << ",\"note\":" << njsonStr(note)
          << "},\"status\":\"ok\"}";
        return true;
    }

    // react.config.disable_namespace — reactor-namespace toggle. The reactor-notification namespace
    // is gated by the database notification subsystem; a guaranteed-hostless, side-effect-free proxy
    // is to confirm the notification subsystem is reachable (transactionManager present) and that a
    // reactor add/remove round-trips (the namespace the toggle would gate). No state persisted.
    if (op == "react.config.disable_namespace") {
        AcDbTransactionManager* tm = pDb->transactionManager();
        static M08MDbReactor s_probe;
        s_probe.reset();
        const Acad::ErrorStatus addEs = pDb->addReactor(&s_probe);
        const Acad::ErrorStatus remEs = pDb->removeReactor(&s_probe);
        const bool ok = (tm != nullptr) && (addEs == Acad::eOk) && (remEs == Acad::eOk);
        r << "\"result\":{\"op\":\"react.config.disable_namespace\""
          << ",\"transaction_manager_present\":" << (tm != nullptr ? "true" : "false")
          << ",\"reactor_namespace_roundtrip\":" << ((addEs == Acad::eOk && remEs == Acad::eOk) ? "true" : "false")
          << ",\"state_persisted\":false"
          << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    // Defensive: HasOp admitted it but no branch handled it (should be impossible — lockstep).
    emitNativeError(r, "OPERATION_DISPATCH_MISMATCH",
                    "m08m admitted '" + op + "' but no handler branch matched");
    return true;
}
