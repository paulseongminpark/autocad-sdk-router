// families/m08m_handlers.inc — M08M NATIVE: OPM properties + reactors.
//
// T01 OPM / property protocol: the dynamic property protocol (AcRxProperty / AcRxAttribute /
//   AcRxMemberCollection over an AcRxClass) is queryable + extendable hostless; the Properties
//   PALETTE itself is attended (this family does NOT build UI). We register/read property members
//   and attach property-authoring attributes to a TRANSIENT runtime AcRxClass (the M08K runtime-
//   class pattern), then tear it down — real protocol-extension, no fakes.
// T02 reactors: AcDbDatabaseReactor / AcDbObjectReactor (transient + persistent) / AcRxEventReactor /
//   AcRxDLinkerReactor attach hostless and FIRE on an in-transaction modify/erase (proven via a
//   scratch mutation in an AriadneStagedWriteTransaction whose dtor rolls back). AcEditorReactor /
//   AcApDocManagerReactor / AcApLongTransactionReactor need the running editor / doc-manager /
//   long-transaction (workspace) subsystem — DEFERRED (left OUT of HasOp; see reports/tickets/M08M.md).
//
// #included into AriadneNativeJob.cpp; sees all in-TU helpers (njsonStr / serializeObjectCommon /
//   AriadneReadTransaction / AriadneStagedWriteTransaction / resolveHandle / jsonFind* / handleOf /
//   handleOfId / emitNativeError / asciiToWide / acharToAscii). m08mHasOp/m08mDispatch lockstep.
//
// SAFETY (hard): staged-write ONLY on ctx.pDb (the router-staged in-memory copy). Never
//   save()/saveAs()/_QSAVE on the original. No acedCommand/acedCmd. Every reactor addReactor'd is
//   removeReactor'd before return. Every transient AcRxClass newAcRxClass'd is deleteAcRxClass'd.
//   Every AcRxAttribute new()'d is handed to a collection (which takes ownership) or deleted. UTF-8
//   via njsonStr.
//
// IMPLEMENTED (44): property inspection (4) + OPM protocol (12) + property authoring (16) +
//   reactors (12). DEFERRED (11): editor/docmanager/longtx reactors — documented + OUT of HasOp.

#include "rxclass.h"      // AcRxClass members()/attributes()/newAcRxClass/acrxBuildClassHierarchy/deleteAcRxClass
#include "rxdict.h"       // acrxClassDictionary (live registered-class lookup by name)
#include "rxmember.h"     // AcRxMember / AcRxMemberCollection / AcRxMemberQueryEngine / AcRxEnumTag
#include "rxprop.h"       // AcRxProperty / AcRxPropertyBase (getValue/setValue/isReadOnly)
#include "rxattrib.h"     // AcRxAttribute family (description/category/units/flags/displayas/...)
#include "rxvalue.h"      // AcRxValue (toString of a property value)
#include "rxvaluetype.h"  // AcRxValueType (member type name)
#include "rxevent.h"      // AcRxEvent / AcRxEventReactor (acrxEvent singleton)
#include "rxdlinkr.h"     // AcRxDynamicLinker / AcRxDLinkerReactor (acrxDynamicLinker singleton)
#include "dbObject.h"     // AcDbObject addReactor/removeReactor + addPersistentReactor/removePersistentReactor
#include "dbents.h"       // AcDbLine (scratch entity for reactor-fire proofs)
#include <cwchar>         // std::wcscmp

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

// Create a uniquely-named transient runtime AcRxClass derived from AcRxObject for attribute-
// authoring proofs (so we never clobber a registered descriptor and always tear down cleanly).
// Returns the class (caller MUST deleteAcRxClass it) + the resolved unique name. nullptr on failure.
static AcRxClass* m08mNewTransientClass(const std::string& baseName, std::string& outName)
{
    static unsigned long s_seq = 0;
    std::ostringstream nm;
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
        // --- T02 reactors (DB / object / persistent / rxevent / linker — hostless attach+fire) ---
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
        std::ostringstream o;
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
        std::ostringstream props;
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
        std::ostringstream arr;
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
        // Attempt the set via the property protocol with a string AcRxValue (many AcDbEntity props,
        // e.g. Layer, accept a const ACHAR* value).
        const std::wstring wval = asciiToWide(newValStr);
        AcRxValue newVal(static_cast<const ACHAR*>(wval.c_str()));
        Acad::ErrorStatus setEs = Acad::eNotApplicable;
        if (!readOnly)
            setEs = prop->setValue(pObj, newVal);
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
          << ",\"before\":" << njsonStr(beforeStr)
          << ",\"requested\":" << njsonStr(newValStr)
          << ",\"after\":" << njsonStr(afterStr)
          << ",\"set_status\":" << static_cast<int>(setEs)
          << ",\"staged_rolled_back\":true"
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
