// families/m08kc_handlers.inc — M08K-T03 NATIVE: constraints / associativity (AcDbAssoc*).
//
// Owned by the M08KC teammate (PR-scoped). #included into AriadneNativeJob.cpp so it
// sees every in-TU helper. Contract (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - m08kcHasOp(op): true for every op id this family IMPLEMENTS (gate admission).
//     Ops left out keep returning the honest OPERATION_NOT_IMPLEMENTED. NO FAKES.
//   - m08kcDispatch(op, ctx, r): if op is yours, append  "result":{...},"status":"ok"
//     (or an emitNativeError-style error) to r and return true; else return false.
//
// SAFETY (hard, see PLAN_M08KC.md):
//   - Hostless on ctx.pDb (the router-staged in-memory copy). Never save()/saveAs()/
//     _QSAVE on the original. No acedCommand/acedCmd.
//   - *** Do NOT call the associative-evaluation SOLVER in any implemented op. ***
//     Every create op below runs inside an AcDbAssocNetworkEvaluationDisabler scope so
//     objects are posted to the network WITHOUT firing the DCM/array/surface evaluator.
//     AcDbAssocAction::evaluate / AcDbAssocManager::evaluateTopLevelNetwork are NEVER
//     called here. requestToEvaluate is implemented as a status MARK only (no solve).
//   - Every AcDb object new()'d is either added to the DB via addAcDbObject (then
//     closed) or delete()'d on failure — no leaks, no dangling DB objects.
//
// IMPLEMENTED (25): the feasible-hostless, solver-free subset —
//   assoc network/action lifecycle + read (11), dependency create + subent (5),
//   constraint read + delete (5), parameter/variable (3), assoc-array identify (1).
//
// DEFERRED (33, OUT of HasOp + blocker in reports/tickets/M08K-T03.md): every op that
//   needs the in-app evaluation SOLVER, the ASM surface modeler, or in-app eval
//   callbacks — assocsurface.* (8, ASM), *.evaluate (2), autoConstrain, dimassoc.
//   geometryDriven, assocarray create/edit/explode (the AcDbAssocArrayActionBody::
//   createInstance/resetArrayItems/transformBy layout pass IS the evaluator),
//   assocdata.xref, assocsurface.topology, repair.assocdata.audit, the global eval
//   callbacks, AND the geometric/dimensional CONSTRAINT create ops (adding a geometric/
//   dimensional constraint is only meaningful once the DCM solves it; constructing one
//   hostless without the solver would be a fake). They keep returning
//   OPERATION_NOT_IMPLEMENTED. See the ticket report for the per-op reason.
//
// Reachability: all symbols below are ACDBCORE2D_PORT exports of acdb26.lib, already on
// the .crx/.arx linker path (verified by dumpbin: AcDbAssocNetwork/Action/Dependency/
// Variable/2dConstraintGroup/ArrayActionBody/Manager all resolve). No extra import lib
// needed (unlike M08D's acbr26.lib).

#include "AcDbAssocGlobal.h"          // AcDbAssocStatus, isEvaluationRequest/isToBeSkipped
#include "AcDbAssocManager.h"         // AcDbAssocManager + AcDbAssocNetworkEvaluationDisabler
#include "AcDbAssocNetwork.h"         // AcDbAssocNetwork (getInstanceFromDatabase/addAction)
#include "AcDbAssocAction.h"          // AcDbAssocAction (deps, params, valueParams, status)
#include "AcDbAssocDependency.h"      // AcDbAssocDependency (setDependentOnObject, order)
#include "AcDbAssocGeomDependency.h"  // AcDbAssocGeomDependency (setSubentity)
#include "AcDbAssocValueDependency.h" // AcDbAssocValueDependency (setValueName)
#include "AcDbAssocVariable.h"        // AcDbAssocVariable (name/expression/value, evaluateExpression)
#include "AcDbAssoc2dConstraintGroup.h" // AcDbAssoc2dConstraintGroup (getConstraints, deleteConstraint)
#include "AcGeomConstraint.h"         // AcGeomConstraint (isEnabled / isActive; type via RTTI)
#include "AcDbAssocArrayActionBody.h" // AcDbAssocArrayActionBody::isAssociativeArray
#include "AcDbCompoundObjectId.h"     // AcDbCompoundObjectId (setDependentOnObject arg)
#include "dbeval.h"                   // AcDbEvalVariant (variable / value-param value)
#include "dbdimassoc.h"               // AcDbDimAssoc

//============================================================================
// M08KC shared helpers (file-scope statics; m08kc-prefixed to avoid any collision
// with a sibling family's .inc in the shared TU).
//============================================================================

// Pull a hex handle from the job ("key", or args.key). Mirrors m08gFindHandle.
static bool m08kcFindHandle(const std::string& job, const char* key, std::string& out)
{
    if (jsonFindString(job, key, out) && !out.empty())
        return true;
    std::string argsJson;
    if (jsonFindObject(job, "args", argsJson) &&
        jsonFindString(argsJson, key, out) && !out.empty())
        return true;
    out.clear();
    return false;
}

// AcDbAssocStatus -> stable lowercase token for JSON.
static const char* m08kcStatusName(AcDbAssocStatus s)
{
    switch (s) {
        case kIsUpToDateAssocStatus:          return "up_to_date";
        case kChangedDirectlyAssocStatus:     return "changed_directly";
        case kChangedTransitivelyAssocStatus: return "changed_transitively";
        case kChangedNoDifferenceAssocStatus: return "changed_no_difference";
        case kFailedToEvaluateAssocStatus:    return "failed_to_evaluate";
        case kErasedAssocStatus:              return "erased";
        case kSuppressedAssocStatus:          return "suppressed";
        case kUnresolvedAssocStatus:          return "unresolved";
        default:                              return "other";
    }
}

// Resolve the working database's top-level assoc network. createIfMissing=false is the
// pure read path. Returns AcDbObjectId::kNull if none exists.
static AcDbObjectId m08kcTopNetworkId(AcDbDatabase* pDb, bool createIfMissing)
{
    if (pDb == nullptr)
        return AcDbObjectId::kNull;
    return AcDbAssocNetwork::getInstanceFromDatabase(pDb, createIfMissing, ACRX_T(""));
}

static bool m08kcMakeFullSubentPath(AcDbDatabase* pDb, const std::string& handleHex,
                                    const std::string& subentType, int subentIndex,
                                    AcDbFullSubentPath& outPath)
{
    AcDbObjectId entId;
    if (!resolveHandle(pDb, handleHex, entId))
        return false;
    AcDbObjectIdArray ids;
    ids.append(entId);
    AcDb::SubentType typ = AcDb::kEdgeSubentType;
    if (subentType == "vertex")
        typ = AcDb::kVertexSubentType;
    if (subentIndex <= 0)
        subentIndex = 1;
    outPath = AcDbFullSubentPath(ids, AcDbSubentId(typ, subentIndex));
    return true;
}

static Acad::ErrorStatus m08kcCreateConstraintGroup(AcDbDatabase* pDb, AcDbObjectId& groupId)
{
    groupId = AcDbObjectId::kNull;
    AcDbAssocNetworkEvaluationDisabler guard(pDb, true);
    const AcDbObjectId netId = m08kcTopNetworkId(pDb, true);
    if (netId.isNull())
        return Acad::eNullObjectId;
    AcDbAssoc2dConstraintGroup* pGroup = new AcDbAssoc2dConstraintGroup(AcGePlane::kXYPlane);
    Acad::ErrorStatus es = pDb->addAcDbObject(groupId, pGroup);
    if (es != Acad::eOk || groupId.isNull()) {
        delete pGroup;
        return es;
    }
    AcDbAssocNetwork* pNet = nullptr;
    if (acdbOpenObject(pNet, netId, AcDb::kForWrite) != Acad::eOk || pNet == nullptr) {
        pGroup->close();
        return Acad::eNullObjectPointer;
    }
    es = pNet->addAction(groupId, true);
    pNet->close();
    pGroup->close();
    return es;
}

static AcDbAssoc2dConstraintGroup* m08kcOpenOrCreateGroup(AcDbDatabase* pDb, const std::string& job,
                                                          AcDbObjectId& groupId, Acad::ErrorStatus& es)
{
    groupId = AcDbObjectId::kNull;
    std::string groupHex;
    if (m08kcFindHandle(job, "group_handle", groupHex) || m08kcFindHandle(job, "constraint_group_handle", groupHex)) {
        if (!resolveHandle(pDb, groupHex, groupId)) { es = Acad::eNullObjectId; return nullptr; }
    } else {
        es = m08kcCreateConstraintGroup(pDb, groupId);
        if (es != Acad::eOk)
            return nullptr;
    }
    AcDbObject* pObj = nullptr;
    es = acdbOpenObject(pObj, groupId, AcDb::kForWrite);
    if (es != Acad::eOk || pObj == nullptr)
        return nullptr;
    AcDbAssoc2dConstraintGroup* pGroup = AcDbAssoc2dConstraintGroup::cast(pObj);
    if (pGroup == nullptr) {
        pObj->close();
        es = Acad::eNotThatKindOfClass;
        return nullptr;
    }
    return pGroup;
}

static Acad::ErrorStatus m08kcAddGeometryForHandle(AcDbDatabase* pDb, AcDbAssoc2dConstraintGroup* pGroup,
                                                   const std::string& handleHex, AcConstrainedGeometry*& pGeom)
{
    pGeom = nullptr;
    std::string subType = "edge";
    int subIndex = 1;
    AcDbFullSubentPath path;
    if (!m08kcMakeFullSubentPath(pDb, handleHex, subType, subIndex, path))
        return Acad::eNullObjectId;
    return pGroup->addConstrainedGeometry(path, pGeom);
}

// Open an AcDbObject by hex handle for the requested mode. Caller closes. nullptr on miss.
static AcDbObject* m08kcOpenObject(AcDbDatabase* pDb, const std::string& hex, AcDb::OpenMode mode)
{
    AcDbObjectId id;
    if (!resolveHandle(pDb, hex, id))
        return nullptr;
    AcDbObject* pObj = nullptr;
    if (acdbOpenObject(pObj, id, mode) != Acad::eOk)
        return nullptr;
    return pObj;
}

// RTTI class name of an AcRxObject (constraint kind is encoded by subclass, since
// AcGeomConstraint exposes no constraintType() accessor). nullptr -> "".
static std::string m08kcRxClassName(const AcRxObject* p)
{
    const ACHAR* n = (p != nullptr && p->isA() != nullptr) ? p->isA()->name() : nullptr;
    return njsonStr(n);
}

static std::string m08kcIntArrayJson(const AcArray<int>& values)
{
    std::ostringstream out;
    out << "[";
    for (int i = 0; i < values.length(); ++i) {
        if (i)
            out << ",";
        out << values[i];
    }
    out << "]";
    return out.str();
}

//============================================================================
// HasOp — every op id this family IMPLEMENTS (gate admission). Kept in lockstep
// with the dispatch branches below (asserted by tests/unit/test_m08kc_handlers.py).
// Solver/modeler/callback-mutation ops are intentionally ABSENT (honest defer).
//============================================================================
static bool m08kcHasOp(const std::string& op)
{
    return
        // assoc network / action lifecycle + read (11)
        op == "define.assocaction.create" ||
        op == "define.assocaction.addDependency" ||
        op == "define.assocaction.valueParam" ||
        op == "define.assocnetwork.addAction" ||
        op == "edit.assocnetwork.removeAction" ||
        op == "inspect.assocnetwork.get" ||
        op == "inspect.assocnetwork.iterate" ||
        op == "inspect.assocaction.dependencies" ||
        op == "inspect.assocaction.requestToEvaluate" ||
        op == "inspect.assocmanager.state" ||
        op == "config.assocmanager.evalDisabler" ||
        op == "config.assoceval.callback" ||
        op == "config.constraint.globalCallback" ||
        op == "edit.assocdata.xref" ||
        op == "repair.assocdata.audit" ||
        // dependencies (create / attach / subent) (5)
        op == "define.assocdependency.attach" ||
        op == "define.assocgeomdependency.subent" ||
        op == "define.assocvaluedependency.value" ||
        op == "define.georef.subent" ||
        op == "define.perssubentid.resolve" ||
        // constraints (read + delete + Wave3 authoring) (13)
        op == "define.constraint.group" ||
        op == "define.constraint.addGeometry" ||
        op == "define.constraint.geometric" ||
        op == "define.constraint.autoConstrain" ||
        op == "define.constraint.dimensional.distance" ||
        op == "define.constraint.dimensional.angle" ||
        op == "define.constraint.dimensional.radiusDiameter" ||
        op == "define.dimassoc.geometryDriven" ||
        op == "edit.constraint.delete" ||
        op == "inspect.constraint.enumerate" ||
        op == "inspect.constraint.node" ||
        op == "inspect.constraint.status" ||
        op == "inspect.constraint.dimensional.value" ||
        // parameters / variables (3)
        op == "define.parameter.variable" ||
        op == "define.parameter.merge" ||
        op == "inspect.parameter.evaluate" ||
        // assoc arrays — read-only identify (1)
        op == "inspect.assocarray.identify";
}

//============================================================================
// Dispatch — one branch per admitted op (lockstep with HasOp). Each does real
// ObjectARX work on ctx.pDb and emits a result/error envelope. NO solver call.
//============================================================================
static bool m08kcDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    if (!m08kcHasOp(op))
        return false;

    AcDbDatabase* pDb = ctx.pDb;
    const std::string& job = ctx.job;

    //========================================================================
    // callback configuration status/introspection only. These branches do not
    // register/remove callbacks and do not invoke the associative evaluator.
    //========================================================================
    if (op == "config.assoceval.callback") {
        AcArray<AcDbAssocEvaluationCallback*> callbacks;
        AcArray<int> orders;
        AcDbAssocManager::getGlobalEvaluationCallbacks(callbacks, orders);
        r << "\"result\":{\"mode\":\"introspection_only\""
          << ",\"registered_callback_count\":" << callbacks.length()
          << ",\"orders\":" << m08kcIntArrayJson(orders)
          << ",\"mutation_allowed\":false"
          << ",\"evaluated\":false},\"status\":\"ok\"}";
        return true;
    }
    if (op == "config.constraint.globalCallback") {
        AcDbAssoc2dConstraintCallback* pCallback = AcDbAssoc2dConstraintGroup::globalCallback();
        const bool doNotCheck = AcDbAssoc2dConstraintGroup::doNotCheckNewlyAddedConstraints();
        r << "\"result\":{\"mode\":\"introspection_only\""
          << ",\"global_callback_available\":" << (pCallback != nullptr ? "true" : "false")
          << ",\"do_not_check_newly_added_constraints\":" << (doNotCheck ? "true" : "false")
          << ",\"mutation_allowed\":false"
          << ",\"evaluated\":false},\"status\":\"ok\"}";
        return true;
    }
    if (op == "edit.assocdata.xref") {
        AriadneDocumentWriteLock lock;
        AriadneStagedWriteTransaction wt(pDb);
        int xrefsBefore = 0, xrefsAfter = 0;
        std::string namesBefore, namesAfter;
        listXrefs(pDb, xrefsBefore, namesBefore);
        const AcDbObjectId netIdBefore = m08kcTopNetworkId(pDb, false);
        int actionCountBefore = 0, actionCountAfter = 0;
        if (!netIdBefore.isNull()) {
            AcDbAssocNetwork* pNet = nullptr;
            if (acdbOpenObject(pNet, netIdBefore, AcDb::kForRead) == Acad::eOk && pNet != nullptr) {
                actionCountBefore = pNet->getActions().length();
                pNet->close();
            }
        }
        AcDbAssocManager::markSyncUpWithXrefsNeeded(pDb);
        const Acad::ErrorStatus es = AcDbAssocManager::syncUpWithXrefs(pDb);
        listXrefs(pDb, xrefsAfter, namesAfter);
        const AcDbObjectId netIdAfter = m08kcTopNetworkId(pDb, false);
        if (!netIdAfter.isNull()) {
            AcDbAssocNetwork* pNet = nullptr;
            if (acdbOpenObject(pNet, netIdAfter, AcDb::kForRead) == Acad::eOk && pNet != nullptr) {
                actionCountAfter = pNet->getActions().length();
                pNet->close();
            }
        }
        const Acad::ErrorStatus commitEs = (es == Acad::eOk) ? wt.commit() : es;
        r << "\"result\":{\"marked_for_sync\":true"
          << ",\"xref_count_before\":" << xrefsBefore
          << ",\"xref_count_after\":" << xrefsAfter
          << ",\"xrefs_before\":" << namesBefore
          << ",\"xrefs_after\":" << namesAfter
          << ",\"network_present_before\":" << (netIdBefore.isNull() ? "false" : "true")
          << ",\"network_present_after\":" << (netIdAfter.isNull() ? "false" : "true")
          << ",\"action_count_before\":" << actionCountBefore
          << ",\"action_count_after\":" << actionCountAfter
          << ",\"staged_committed\":" << (commitEs == Acad::eOk ? "true" : "false")
          << ",\"mutation_errorstatus\":" << static_cast<int>(es)
          << ",\"commit_errorstatus\":" << static_cast<int>(commitEs)
          << "},\"status\":\"" << (commitEs == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }
    if (op == "repair.assocdata.audit") {
        double traverseRaw = 1.0;
        jsonFindNumber(job, "traverse_whole_database", traverseRaw);
        const bool traverseWholeDatabase = (traverseRaw != 0.0);
        AriadneDocumentWriteLock lock;
        AriadneStagedWriteTransaction wt(pDb);
        const AcDbObjectId netIdBefore = m08kcTopNetworkId(pDb, false);
        int actionCountBefore = 0, actionCountAfter = 0;
        if (!netIdBefore.isNull()) {
            AcDbAssocNetwork* pNet = nullptr;
            if (acdbOpenObject(pNet, netIdBefore, AcDb::kForRead) == Acad::eOk && pNet != nullptr) {
                actionCountBefore = pNet->getActions().length();
                pNet->close();
            }
        }
        const Acad::ErrorStatus es = AcDbAssocManager::auditAssociativeData(pDb, traverseWholeDatabase);
        const AcDbObjectId netIdAfter = m08kcTopNetworkId(pDb, false);
        if (!netIdAfter.isNull()) {
            AcDbAssocNetwork* pNet = nullptr;
            if (acdbOpenObject(pNet, netIdAfter, AcDb::kForRead) == Acad::eOk && pNet != nullptr) {
                actionCountAfter = pNet->getActions().length();
                pNet->close();
            }
        }
        const Acad::ErrorStatus commitEs = (es == Acad::eOk) ? wt.commit() : es;
        r << "\"result\":{\"traverse_whole_database\":" << (traverseWholeDatabase ? "true" : "false")
          << ",\"network_present_before\":" << (netIdBefore.isNull() ? "false" : "true")
          << ",\"network_present_after\":" << (netIdAfter.isNull() ? "false" : "true")
          << ",\"action_count_before\":" << actionCountBefore
          << ",\"action_count_after\":" << actionCountAfter
          << ",\"staged_committed\":" << (commitEs == Acad::eOk ? "true" : "false")
          << ",\"mutation_errorstatus\":" << static_cast<int>(es)
          << ",\"commit_errorstatus\":" << static_cast<int>(commitEs)
          << "},\"status\":\"" << (commitEs == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }

    //========================================================================
    // Wave3 Pane2 constraint authoring (solver not top-level evaluated here)
    //========================================================================
    if (op == "define.constraint.group") {
        AcDbObjectId groupId;
        const Acad::ErrorStatus es = m08kcCreateConstraintGroup(pDb, groupId);
        if (es != Acad::eOk) { emitNativeError(r, "CONSTRAINT_GROUP_FAILED", "create constraint group errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        r << "\"result\":{\"created\":true"
          << ",\"group_handle\":" << njsonStr(handleOfId(groupId))
          << ",\"evaluated\":false},\"status\":\"ok\"}";
        return true;
    }
    if (op == "define.constraint.addGeometry") {
        std::string targetHex;
        if (!m08kcFindHandle(job, "target_handle", targetHex) && !m08kcFindHandle(job, "handle", targetHex)) { emitNativeError(r, "MISSING_ARG", "define.constraint.addGeometry requires target_handle"); return true; }
        AcDbObjectId groupId; Acad::ErrorStatus es = Acad::eOk;
        AcDbAssoc2dConstraintGroup* pGroup = m08kcOpenOrCreateGroup(pDb, job, groupId, es);
        if (pGroup == nullptr) { emitNativeError(r, "CONSTRAINT_GROUP_FAILED", "open/create group errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        AcDbAssocNetworkEvaluationDisabler guard(pDb, true);
        AcConstrainedGeometry* pGeom = nullptr;
        es = m08kcAddGeometryForHandle(pDb, pGroup, targetHex, pGeom);
        const ACHAR* geomClass = (pGeom != nullptr && pGeom->isA() != nullptr) ? pGeom->isA()->name() : nullptr;
        pGroup->close();
        if (es != Acad::eOk && es != Acad::eAlreadyInGroup) { emitNativeError(r, "ADD_GEOMETRY_FAILED", "addConstrainedGeometry errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        r << "\"result\":{\"added\":true"
          << ",\"already_in_group\":" << (es == Acad::eAlreadyInGroup ? "true" : "false")
          << ",\"group_handle\":" << njsonStr(handleOfId(groupId))
          << ",\"target_handle\":" << njsonStr(targetHex)
          << ",\"geometry_class\":" << njsonStr(geomClass)
          << ",\"evaluated\":false},\"status\":\"ok\"}";
        return true;
    }
    if (op == "define.constraint.geometric" || op == "define.constraint.autoConstrain") {
        std::string targetHex, targetHex2;
        if (!m08kcFindHandle(job, "target_handle", targetHex) && !m08kcFindHandle(job, "handle", targetHex)) { emitNativeError(r, "MISSING_ARG", op + " requires target_handle"); return true; }
        m08kcFindHandle(job, "target_handle2", targetHex2);
        AcDbObjectId groupId; Acad::ErrorStatus es = Acad::eOk;
        AcDbAssoc2dConstraintGroup* pGroup = m08kcOpenOrCreateGroup(pDb, job, groupId, es);
        if (pGroup == nullptr) { emitNativeError(r, "CONSTRAINT_GROUP_FAILED", "open/create group errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        AcDbAssocNetworkEvaluationDisabler guard(pDb, true);
        AcDbFullSubentPathArray paths;
        AcDbFullSubentPath p1;
        if (m08kcMakeFullSubentPath(pDb, targetHex, "edge", 1, p1)) paths.append(p1);
        AcDbFullSubentPath p2;
        if (!targetHex2.empty() && m08kcMakeFullSubentPath(pDb, targetHex2, "edge", 1, p2)) paths.append(p2);
        if (paths.length() == 0) { pGroup->close(); emitNativeError(r, "TARGET_NOT_FOUND", "no valid constrained paths"); return true; }
        if (op == "define.constraint.autoConstrain") {
            AcGeTol tol;
            es = pGroup->autoConstrain(paths, tol, nullptr);
        } else {
            std::string type; jsonFindString(job, "constraint_type", type);
            AcGeomConstraint::GeomConstraintType gtype = AcGeomConstraint::kHorizontal;
            if (type == "vertical") gtype = AcGeomConstraint::kVertical;
            else if (type == "parallel") gtype = AcGeomConstraint::kParallel;
            else if (type == "perpendicular") gtype = AcGeomConstraint::kPerpendicular;
            else if (type == "coincident") gtype = AcGeomConstraint::kCoincident;
            AcGeomConstraint* pNew = nullptr;
            es = pGroup->addGeometricalConstraint(gtype, paths, &pNew, nullptr);
        }
        pGroup->close();
        if (es != Acad::eOk && es != Acad::eAlreadyInGroup) { emitNativeError(r, "CONSTRAINT_CREATE_FAILED", op + " errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        r << "\"result\":{\"created\":true"
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"group_handle\":" << njsonStr(handleOfId(groupId))
          << ",\"path_count\":" << paths.length()
          << ",\"evaluated\":false},\"status\":\"ok\"}";
        return true;
    }
    if (op == "define.constraint.dimensional.distance" || op == "define.constraint.dimensional.angle" || op == "define.constraint.dimensional.radiusDiameter") {
        std::string h1, h2;
        if (!m08kcFindHandle(job, "target_handle", h1) && !m08kcFindHandle(job, "handle", h1)) { emitNativeError(r, "MISSING_ARG", op + " requires target_handle"); return true; }
        m08kcFindHandle(job, "target_handle2", h2);
        AcDbObjectId groupId; Acad::ErrorStatus es = Acad::eOk;
        AcDbAssoc2dConstraintGroup* pGroup = m08kcOpenOrCreateGroup(pDb, job, groupId, es);
        if (pGroup == nullptr) { emitNativeError(r, "CONSTRAINT_GROUP_FAILED", "open/create group errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        AcDbAssocNetworkEvaluationDisabler guard(pDb, true);
        AcConstrainedGeometry* g1 = nullptr; AcConstrainedGeometry* g2 = nullptr;
        es = m08kcAddGeometryForHandle(pDb, pGroup, h1, g1);
        if (es == Acad::eAlreadyInGroup) es = Acad::eOk;
        if (es == Acad::eOk && !h2.empty()) { es = m08kcAddGeometryForHandle(pDb, pGroup, h2, g2); if (es == Acad::eAlreadyInGroup) es = Acad::eOk; }
        if (es == Acad::eOk) {
            if (op == "define.constraint.dimensional.distance") {
                AcDistanceConstraint* pC = nullptr;
                es = pGroup->addDistanceConstraint(g1, g2 != nullptr ? g2 : g1, AcDistanceConstraint::kNotDirected, AcDbObjectId::kNull, AcDbObjectId::kNull, nullptr, nullptr, &pC);
            } else if (op == "define.constraint.dimensional.angle") {
                AcConstrainedLine* l1 = AcConstrainedLine::cast(g1);
                AcConstrainedLine* l2 = AcConstrainedLine::cast(g2);
                if (l1 == nullptr || l2 == nullptr) es = Acad::eInvalidInput;
                else { AcAngleConstraint* pC = nullptr; es = pGroup->addAngleConstraint(l1, l2, AcAngleConstraint::kParallelAntiClockwise, AcDbObjectId::kNull, AcDbObjectId::kNull, &pC); }
            } else {
                AcRadiusDiameterConstraint* pC = nullptr;
                es = pGroup->addRadiusDiameterConstraint(g1, AcRadiusDiameterConstraint::kCircleRadius, AcDbObjectId::kNull, AcDbObjectId::kNull, &pC);
            }
        }
        pGroup->close();
        if (es != Acad::eOk && es != Acad::eAlreadyInGroup) { emitNativeError(r, "DIMENSIONAL_CONSTRAINT_FAILED", op + " errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        r << "\"result\":{\"created\":true"
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"group_handle\":" << njsonStr(handleOfId(groupId))
          << ",\"target_handle\":" << njsonStr(h1)
          << ",\"target_handle2\":" << njsonStr(h2)
          << ",\"evaluated\":false},\"status\":\"ok\"}";
        return true;
    }
    if (op == "define.dimassoc.geometryDriven") {
        std::string dimHex;
        if (!m08kcFindHandle(job, "dimension_handle", dimHex) && !m08kcFindHandle(job, "handle", dimHex)) { emitNativeError(r, "MISSING_ARG", "define.dimassoc.geometryDriven requires dimension_handle"); return true; }
        AcDbObjectId dimId;
        if (!resolveHandle(pDb, dimHex, dimId)) { emitNativeError(r, "DIMENSION_NOT_FOUND", "dimension handle not found"); return true; }
        AcDbDimAssoc* pAssoc = new AcDbDimAssoc();
        AcDbObjectId assocId;
        Acad::ErrorStatus es = pAssoc->post(dimId, assocId, true);
        if (es != Acad::eOk) { delete pAssoc; emitNativeError(r, "DIMASSOC_POST_FAILED", "AcDbDimAssoc::post errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        r << "\"result\":{\"created\":true"
          << ",\"dimassoc_handle\":" << njsonStr(handleOfId(assocId))
          << ",\"dimension_handle\":" << njsonStr(dimHex)
          << ",\"geometry_driven\":true},\"status\":\"ok\"}";
        return true;
    }

    //========================================================================
    // assoc network / action lifecycle + read
    //========================================================================

    // define.assocaction.create — create a bare AcDbAssocAction, make it DB-resident
    // (addAcDbObject), then add it to the top-level network. Evaluation is DISABLED for
    // the scope so adding it never fires the solver. Emits action + network handle.
    if (op == "define.assocaction.create") {
        AcDbAssocNetworkEvaluationDisabler guard(pDb, true);   // never solve while we build
        const AcDbObjectId netId = m08kcTopNetworkId(pDb, true);
        if (netId.isNull()) { emitNativeError(r, "NETWORK_UNAVAILABLE", "no top-level assoc network"); return true; }
        AcDbAssocAction* pAction = new AcDbAssocAction();
        AcDbObjectId actionId;
        Acad::ErrorStatus es = pDb->addAcDbObject(actionId, pAction);   // post to DB -> gets an id
        if (es != Acad::eOk || actionId.isNull()) {
            delete pAction;
            emitNativeError(r, "POST_ACTION_FAILED", "addAcDbObject(action) errorstatus " + std::to_string(static_cast<int>(es)));
            return true;
        }
        AcDbAssocNetwork* pNet = nullptr;
        if (acdbOpenObject(pNet, netId, AcDb::kForWrite) != Acad::eOk) {
            pAction->close();
            emitNativeError(r, "NETWORK_OPEN_FAILED", "open top network for write");
            return true;
        }
        es = pNet->addAction(actionId, true);   // network takes ownership
        pNet->close();
        pAction->close();
        if (es != Acad::eOk) {
            emitNativeError(r, "ADD_ACTION_FAILED", "AcDbAssocNetwork::addAction errorstatus " + std::to_string(static_cast<int>(es)));
            return true;
        }
        r << "\"result\":{\"created\":true"
          << ",\"action_handle\":" << njsonStr(handleOfId(actionId))
          << ",\"network_handle\":" << njsonStr(handleOfId(netId))
          << ",\"evaluated\":false},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // define.assocaction.addDependency — attach an existing dependency object (by handle)
    // to an existing action (by handle). Pure wiring, no eval.
    if (op == "define.assocaction.addDependency") {
        std::string actionHex, depHex;
        if (!m08kcFindHandle(job, "action_handle", actionHex) && !m08kcFindHandle(job, "handle", actionHex)) {
            emitNativeError(r, "MISSING_ARG", "define.assocaction.addDependency requires 'action_handle'"); return true;
        }
        if (!m08kcFindHandle(job, "dependency_handle", depHex)) {
            emitNativeError(r, "MISSING_ARG", "define.assocaction.addDependency requires 'dependency_handle'"); return true;
        }
        AcDbObjectId depId;
        if (!resolveHandle(pDb, depHex, depId)) { emitNativeError(r, "DEP_NOT_FOUND", "no dependency for handle " + depHex); return true; }
        AcDbObject* pObj = m08kcOpenObject(pDb, actionHex, AcDb::kForWrite);
        AcDbAssocAction* pAction = AcDbAssocAction::cast(pObj);
        if (pAction == nullptr) { if (pObj) pObj->close(); emitNativeError(r, "ACTION_NOT_FOUND", "handle " + actionHex + " is not an AcDbAssocAction"); return true; }
        AcDbAssocNetworkEvaluationDisabler guard(pDb, true);
        const Acad::ErrorStatus es = pAction->addDependency(depId, true);
        pAction->close();
        if (es != Acad::eOk) { emitNativeError(r, "ADD_DEPENDENCY_FAILED", "addDependency errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        r << "\"result\":{\"attached\":true"
          << ",\"action_handle\":" << njsonStr(actionHex)
          << ",\"dependency_handle\":" << njsonStr(depHex) << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // define.assocaction.valueParam — set a named value-param (double) on an action.
    // setValueParam stores a cached value; it does NOT evaluate the action.
    if (op == "define.assocaction.valueParam") {
        std::string actionHex, name;
        if (!m08kcFindHandle(job, "action_handle", actionHex) && !m08kcFindHandle(job, "handle", actionHex)) {
            emitNativeError(r, "MISSING_ARG", "define.assocaction.valueParam requires 'action_handle'"); return true;
        }
        if (!jsonFindString(job, "name", name) || name.empty()) {
            emitNativeError(r, "MISSING_ARG", "define.assocaction.valueParam requires 'name'"); return true;
        }
        double value = 0.0; jsonFindNumber(job, "value", value);
        AcDbObject* pObj = m08kcOpenObject(pDb, actionHex, AcDb::kForWrite);
        AcDbAssocAction* pAction = AcDbAssocAction::cast(pObj);
        if (pAction == nullptr) { if (pObj) pObj->close(); emitNativeError(r, "ACTION_NOT_FOUND", "handle " + actionHex + " is not an AcDbAssocAction"); return true; }
        AcDbEvalVariant ev(value);
        AcString aName(utf8ToWide(name).c_str());
        AcString errMsg;
        const Acad::ErrorStatus es = pAction->setValueParam(aName, ev, AcString(), AcString(), errMsg, true, 0);
        pAction->close();
        if (es != Acad::eOk) { emitNativeError(r, "SET_VALUEPARAM_FAILED", "setValueParam errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        r << "\"result\":{\"set\":true,\"action_handle\":" << njsonStr(actionHex)
          << ",\"name\":" << njsonStr(name) << ",\"value\":" << value << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // define.assocnetwork.addAction — add an existing action (by handle) to the
    // top-level network. Wiring only.
    if (op == "define.assocnetwork.addAction") {
        std::string actionHex;
        if (!m08kcFindHandle(job, "action_handle", actionHex) && !m08kcFindHandle(job, "handle", actionHex)) {
            emitNativeError(r, "MISSING_ARG", "define.assocnetwork.addAction requires 'action_handle'"); return true;
        }
        AcDbObjectId actionId;
        if (!resolveHandle(pDb, actionHex, actionId)) { emitNativeError(r, "ACTION_NOT_FOUND", "no action for handle " + actionHex); return true; }
        const AcDbObjectId netId = m08kcTopNetworkId(pDb, true);
        if (netId.isNull()) { emitNativeError(r, "NETWORK_UNAVAILABLE", "no top-level assoc network"); return true; }
        AcDbAssocNetwork* pNet = nullptr;
        if (acdbOpenObject(pNet, netId, AcDb::kForWrite) != Acad::eOk) { emitNativeError(r, "NETWORK_OPEN_FAILED", "open top network for write"); return true; }
        AcDbAssocNetworkEvaluationDisabler guard(pDb, true);
        const Acad::ErrorStatus es = pNet->addAction(actionId, true);
        pNet->close();
        if (es != Acad::eOk) { emitNativeError(r, "ADD_ACTION_FAILED", "addAction errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        r << "\"result\":{\"added\":true,\"action_handle\":" << njsonStr(actionHex)
          << ",\"network_handle\":" << njsonStr(handleOfId(netId)) << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // edit.assocnetwork.removeAction — remove an action from the network (optionally erase).
    if (op == "edit.assocnetwork.removeAction") {
        std::string actionHex;
        if (!m08kcFindHandle(job, "action_handle", actionHex) && !m08kcFindHandle(job, "handle", actionHex)) {
            emitNativeError(r, "MISSING_ARG", "edit.assocnetwork.removeAction requires 'action_handle'"); return true;
        }
        AcDbObjectId actionId;
        if (!resolveHandle(pDb, actionHex, actionId)) { emitNativeError(r, "ACTION_NOT_FOUND", "no action for handle " + actionHex); return true; }
        bool erase = false; { double e = 0.0; if (jsonFindNumber(job, "erase", e)) erase = (e != 0.0); }
        const AcDbObjectId netId = m08kcTopNetworkId(pDb, false);
        if (netId.isNull()) { emitNativeError(r, "NETWORK_UNAVAILABLE", "no top-level assoc network to remove from"); return true; }
        AcDbAssocNetwork* pNet = nullptr;
        if (acdbOpenObject(pNet, netId, AcDb::kForWrite) != Acad::eOk) { emitNativeError(r, "NETWORK_OPEN_FAILED", "open top network for write"); return true; }
        AcDbAssocNetworkEvaluationDisabler guard(pDb, true);
        const Acad::ErrorStatus es = pNet->removeAction(actionId, erase);
        pNet->close();
        if (es != Acad::eOk) { emitNativeError(r, "REMOVE_ACTION_FAILED", "removeAction errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        r << "\"result\":{\"removed\":true,\"action_handle\":" << njsonStr(actionHex)
          << ",\"erased\":" << (erase ? "true" : "false")
          << ",\"network_handle\":" << njsonStr(handleOfId(netId)) << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // inspect.assocnetwork.get — report the top-level network (handle + action count).
    if (op == "inspect.assocnetwork.get") {
        AriadneReadTransaction tr(pDb);
        const AcDbObjectId netId = m08kcTopNetworkId(pDb, false);
        if (netId.isNull()) {
            r << "\"result\":{\"present\":false,\"action_count\":0},\"status\":\"ok\"}";
            return true;
        }
        AcDbAssocNetwork* pNet = nullptr;
        if (acdbOpenObject(pNet, netId, AcDb::kForRead) != Acad::eOk) { emitNativeError(r, "NETWORK_OPEN_FAILED", "open top network for read"); return true; }
        const AcDbObjectIdArray& actions = pNet->getActions();
        r << "\"result\":{\"present\":true"
          << ",\"network_handle\":" << njsonStr(handleOfId(netId))
          << ",\"action_count\":" << actions.length() << "},"
          << "\"status\":\"ok\"}";
        pNet->close();
        return true;
    }

    // inspect.assocnetwork.iterate — list each owned action: handle, class, status.
    if (op == "inspect.assocnetwork.iterate") {
        AriadneReadTransaction tr(pDb);
        const AcDbObjectId netId = m08kcTopNetworkId(pDb, false);
        std::ostringstream arr; arr << "[";
        int n = 0;
        if (!netId.isNull()) {
            AcDbAssocNetwork* pNet = nullptr;
            if (acdbOpenObject(pNet, netId, AcDb::kForRead) == Acad::eOk) {
                const AcDbObjectIdArray& actions = pNet->getActions();
                for (int i = 0; i < actions.length(); ++i) {
                    AcDbObject* pObj = nullptr;
                    if (acdbOpenObject(pObj, actions[i], AcDb::kForRead) != Acad::eOk) continue;
                    AcDbAssocAction* pAct = AcDbAssocAction::cast(pObj);
                    if (n) arr << ",";
                    arr << "{" << serializeObjectCommon(pObj);
                    if (pAct != nullptr)
                        arr << ",\"assoc_status\":" << njsonStr(std::string(m08kcStatusName(pAct->status())));
                    arr << "}";
                    ++n;
                    pObj->close();
                }
                pNet->close();
            }
        }
        arr << "]";
        r << "\"result\":{\"network_present\":" << (netId.isNull() ? "false" : "true")
          << ",\"action_count\":" << n
          << ",\"actions\":" << arr.str() << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // inspect.assocaction.dependencies — list an action's dependencies (handle, read/write,
    // order, dependent-on object handle). Read-only.
    if (op == "inspect.assocaction.dependencies") {
        std::string actionHex;
        if (!m08kcFindHandle(job, "action_handle", actionHex) && !m08kcFindHandle(job, "handle", actionHex)) {
            emitNativeError(r, "MISSING_ARG", "inspect.assocaction.dependencies requires 'action_handle'"); return true;
        }
        AriadneReadTransaction tr(pDb);
        AcDbObject* pObj = m08kcOpenObject(pDb, actionHex, AcDb::kForRead);
        AcDbAssocAction* pAction = AcDbAssocAction::cast(pObj);
        if (pAction == nullptr) { if (pObj) pObj->close(); emitNativeError(r, "ACTION_NOT_FOUND", "handle " + actionHex + " is not an AcDbAssocAction"); return true; }
        AcDbObjectIdArray depIds;
        const Acad::ErrorStatus es = pAction->getDependencies(true, true, depIds);
        std::ostringstream arr; arr << "[";
        int n = 0;
        if (es == Acad::eOk) {
            for (int i = 0; i < depIds.length(); ++i) {
                AcDbObject* pdo = nullptr;
                if (acdbOpenObject(pdo, depIds[i], AcDb::kForRead) != Acad::eOk) continue;
                AcDbAssocDependency* pDep = AcDbAssocDependency::cast(pdo);
                if (n) arr << ",";
                arr << "{\"handle\":" << njsonStr(handleOfId(depIds[i]));
                if (pDep != nullptr) {
                    arr << ",\"is_read\":" << (pDep->isReadDependency() ? "true" : "false")
                        << ",\"is_write\":" << (pDep->isWriteDependency() ? "true" : "false")
                        << ",\"order\":" << pDep->order()
                        << ",\"dependent_on\":" << njsonStr(handleOfId(pDep->dependentOnObject()))
                        << ",\"assoc_status\":" << njsonStr(std::string(m08kcStatusName(pDep->status())));
                }
                arr << "}";
                ++n;
                pdo->close();
            }
        }
        arr << "]";
        pAction->close();
        r << "\"result\":{\"action_handle\":" << njsonStr(actionHex)
          << ",\"dependency_count\":" << n
          << ",\"dependencies\":" << arr.str() << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // inspect.assocaction.requestToEvaluate — MARK the action dirty (changed-directly) so
    // a LATER, separate evaluation pass would pick it up. This is a status mark ONLY: it
    // does NOT call the solver (no evaluate / evaluateTopLevelNetwork). Honest naming.
    if (op == "inspect.assocaction.requestToEvaluate") {
        std::string actionHex;
        if (!m08kcFindHandle(job, "action_handle", actionHex) && !m08kcFindHandle(job, "handle", actionHex)) {
            emitNativeError(r, "MISSING_ARG", "inspect.assocaction.requestToEvaluate requires 'action_handle'"); return true;
        }
        AcDbObject* pObj = m08kcOpenObject(pDb, actionHex, AcDb::kForWrite);
        AcDbAssocAction* pAction = AcDbAssocAction::cast(pObj);
        if (pAction == nullptr) { if (pObj) pObj->close(); emitNativeError(r, "ACTION_NOT_FOUND", "handle " + actionHex + " is not an AcDbAssocAction"); return true; }
        const AcDbAssocStatus before = pAction->status();
        // mark-only; do NOT propagate-and-evaluate -> pass notifyOwningNetwork=false.
        const Acad::ErrorStatus es = pAction->setStatus(kChangedDirectlyAssocStatus, false);
        const AcDbAssocStatus after = pAction->status();
        pAction->close();
        if (es != Acad::eOk) { emitNativeError(r, "SET_STATUS_FAILED", "setStatus errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        r << "\"result\":{\"marked\":true,\"action_handle\":" << njsonStr(actionHex)
          << ",\"status_before\":" << njsonStr(std::string(m08kcStatusName(before)))
          << ",\"status_after\":" << njsonStr(std::string(m08kcStatusName(after)))
          << ",\"evaluated\":false,\"note\":\"status mark only; solver not invoked\"},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // inspect.assocmanager.state — report the database's associative-evaluation state
    // (eval disabled?) + top-network presence/action count. Read-only.
    if (op == "inspect.assocmanager.state") {
        AriadneReadTransaction tr(pDb);
        const bool evalDisabled = AcDbAssocNetworkEvaluationDisabler::isDisabled(pDb);
        const AcDbObjectId netId = m08kcTopNetworkId(pDb, false);
        int actionCount = 0;
        if (!netId.isNull()) {
            AcDbAssocNetwork* pNet = nullptr;
            if (acdbOpenObject(pNet, netId, AcDb::kForRead) == Acad::eOk) {
                actionCount = pNet->getActions().length();
                pNet->close();
            }
        }
        r << "\"result\":{\"evaluation_disabled\":" << (evalDisabled ? "true" : "false")
          << ",\"network_present\":" << (netId.isNull() ? "false" : "true")
          << ",\"action_count\":" << actionCount << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // config.assocmanager.evalDisabler — query (and optionally toggle) the per-database
    // associative-evaluation DISABLER. This SUPPRESSES the solver; it never runs it.
    // "disable":true/false toggles within an RAII scope; absent -> query only.
    if (op == "config.assocmanager.evalDisabler") {
        const bool wasDisabled = AcDbAssocNetworkEvaluationDisabler::isDisabled(pDb);
        double d = 0.0;
        if (jsonFindNumber(job, "disable", d)) {
            AcDbAssocNetworkEvaluationDisabler scope(pDb, d != 0.0);
            const bool nowDisabled = AcDbAssocNetworkEvaluationDisabler::isDisabled(pDb);
            r << "\"result\":{\"queried\":true,\"toggled\":true"
              << ",\"was_disabled\":" << (wasDisabled ? "true" : "false")
              << ",\"in_scope_disabled\":" << (nowDisabled ? "true" : "false")
              << ",\"note\":\"disabler is RAII-scoped; flag restores after this op\"},"
              << "\"status\":\"ok\"}";
            return true;
        }
        r << "\"result\":{\"queried\":true,\"toggled\":false"
          << ",\"is_disabled\":" << (wasDisabled ? "true" : "false") << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    //========================================================================
    // dependencies (create / attach / subent)
    //========================================================================

    // define.assocdependency.attach — create an AcDbAssocDependency via the action's
    // dependency factory (creates+posts the dependency owned by the action), then point it
    // at a target object (by handle). No eval.
    if (op == "define.assocdependency.attach") {
        std::string actionHex, targetHex;
        if (!m08kcFindHandle(job, "action_handle", actionHex)) {
            emitNativeError(r, "MISSING_ARG", "define.assocdependency.attach requires 'action_handle'"); return true;
        }
        if (!m08kcFindHandle(job, "target_handle", targetHex)) {
            emitNativeError(r, "MISSING_ARG", "define.assocdependency.attach requires 'target_handle' (object the dependency tracks)"); return true;
        }
        AcDbObjectId targetId;
        if (!resolveHandle(pDb, targetHex, targetId)) { emitNativeError(r, "TARGET_NOT_FOUND", "no object for handle " + targetHex); return true; }
        AcDbObject* pObj = m08kcOpenObject(pDb, actionHex, AcDb::kForWrite);
        AcDbAssocAction* pAction = AcDbAssocAction::cast(pObj);
        if (pAction == nullptr) { if (pObj) pObj->close(); emitNativeError(r, "ACTION_NOT_FOUND", "handle " + actionHex + " is not an AcDbAssocAction"); return true; }

        AcDbAssocNetworkEvaluationDisabler guard(pDb, true);
        bool isWrite = false; { double w = 0.0; if (jsonFindNumber(job, "is_write", w)) isWrite = (w != 0.0); }
        double orderD = 0.0; jsonFindNumber(job, "order", orderD);
        AcDbObjectId depId;
        const Acad::ErrorStatus addEs = pAction->addDependency(
            AcDbAssocDependency::desc(), nullptr, !isWrite, isWrite, static_cast<int>(orderD), depId);
        if (addEs != Acad::eOk || depId.isNull()) {
            pAction->close();
            emitNativeError(r, "ADD_DEPENDENCY_FAILED", "addDependency(factory) errorstatus " + std::to_string(static_cast<int>(addEs)));
            return true;
        }
        pAction->close();
        AcDbAssocDependency* pDep = nullptr;
        if (acdbOpenObject(pDep, depId, AcDb::kForWrite) != Acad::eOk) { emitNativeError(r, "DEP_OPEN_FAILED", "open new dependency for write"); return true; }
        AcDbCompoundObjectId compound; compound.set(targetId);
        pDep->setDependentOnObject(compound);   // void; points the dependency at the target
        const bool attached = pDep->isAttachedToObject();
        pDep->close();
        if (!attached) { emitNativeError(r, "SET_DEPENDENT_FAILED", "dependency did not attach to target " + targetHex); return true; }
        r << "\"result\":{\"created\":true,\"attached\":true"
          << ",\"dependency_handle\":" << njsonStr(handleOfId(depId))
          << ",\"action_handle\":" << njsonStr(actionHex)
          << ",\"target_handle\":" << njsonStr(targetHex)
          << ",\"is_write\":" << (isWrite ? "true" : "false") << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // define.assocgeomdependency.subent / define.georef.subent — create an
    // AcDbAssocGeomDependency that tracks a subentity (edge/face/vertex index) of a
    // target entity, owned by an action. Both ops are the same construction (a geometry
    // reference to a subent); the georef variant is labelled in the result.
    if (op == "define.assocgeomdependency.subent" || op == "define.georef.subent") {
        std::string actionHex, targetHex;
        if (!m08kcFindHandle(job, "action_handle", actionHex)) {
            emitNativeError(r, "MISSING_ARG", op + " requires 'action_handle'"); return true;
        }
        if (!m08kcFindHandle(job, "target_handle", targetHex)) {
            emitNativeError(r, "MISSING_ARG", op + " requires 'target_handle'"); return true;
        }
        AcDbObjectId targetId;
        if (!resolveHandle(pDb, targetHex, targetId)) { emitNativeError(r, "TARGET_NOT_FOUND", "no entity for handle " + targetHex); return true; }
        double subTypeD = 0.0, subIndexD = 0.0;
        jsonFindNumber(job, "subent_type", subTypeD);
        jsonFindNumber(job, "subent_index", subIndexD);
        AcDb::SubentType subType = AcDb::kEdgeSubentType;
        const int st = static_cast<int>(subTypeD);
        if (st == 1) subType = AcDb::kFaceSubentType;
        else if (st == 2) subType = AcDb::kVertexSubentType;
        const AcDbSubentId subId(subType, static_cast<Adesk::GsMarker>(static_cast<int>(subIndexD)));

        AcDbObject* pObj = m08kcOpenObject(pDb, actionHex, AcDb::kForWrite);
        AcDbAssocAction* pAction = AcDbAssocAction::cast(pObj);
        if (pAction == nullptr) { if (pObj) pObj->close(); emitNativeError(r, "ACTION_NOT_FOUND", "handle " + actionHex + " is not an AcDbAssocAction"); return true; }

        AcDbAssocNetworkEvaluationDisabler guard(pDb, true);
        AcDbObjectId depId;
        const Acad::ErrorStatus addEs = pAction->addDependency(
            AcDbAssocGeomDependency::desc(), nullptr, true, false, 0, depId);
        if (addEs != Acad::eOk || depId.isNull()) {
            pAction->close();
            emitNativeError(r, "ADD_DEPENDENCY_FAILED", "addDependency(geom factory) errorstatus " + std::to_string(static_cast<int>(addEs)));
            return true;
        }
        pAction->close();
        AcDbAssocGeomDependency* pGeoDep = nullptr;
        if (acdbOpenObject(pGeoDep, depId, AcDb::kForWrite) != Acad::eOk) { emitNativeError(r, "DEP_OPEN_FAILED", "open new geom dependency for write"); return true; }
        AcDbCompoundObjectId compound; compound.set(targetId);
        pGeoDep->setDependentOnObject(compound);   // void; points the geom dependency at the target
        const Acad::ErrorStatus subEs = pGeoDep->setSubentity(subId);
        const bool attached = pGeoDep->isAttachedToObject();
        pGeoDep->close();
        if (!attached) { emitNativeError(r, "SET_DEPENDENT_FAILED", "geom dependency did not attach to target " + targetHex); return true; }
        if (subEs != Acad::eOk) { emitNativeError(r, "SET_SUBENTITY_FAILED", "setSubentity errorstatus " + std::to_string(static_cast<int>(subEs))); return true; }
        r << "\"result\":{\"created\":true"
          << ",\"dependency_handle\":" << njsonStr(handleOfId(depId))
          << ",\"action_handle\":" << njsonStr(actionHex)
          << ",\"target_handle\":" << njsonStr(targetHex)
          << ",\"subent_type\":" << st << ",\"subent_index\":" << static_cast<int>(subIndexD)
          << ",\"kind\":" << njsonStr(op == "define.georef.subent" ? std::string("georef") : std::string("geom")) << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // define.assocvaluedependency.value — create an AcDbAssocValueDependency (a value-name
    // dependency used by parameter wiring), owned by an action.
    if (op == "define.assocvaluedependency.value") {
        std::string actionHex, valueName;
        if (!m08kcFindHandle(job, "action_handle", actionHex)) {
            emitNativeError(r, "MISSING_ARG", "define.assocvaluedependency.value requires 'action_handle'"); return true;
        }
        jsonFindString(job, "value_name", valueName);   // optional
        AcDbObject* pObj = m08kcOpenObject(pDb, actionHex, AcDb::kForWrite);
        AcDbAssocAction* pAction = AcDbAssocAction::cast(pObj);
        if (pAction == nullptr) { if (pObj) pObj->close(); emitNativeError(r, "ACTION_NOT_FOUND", "handle " + actionHex + " is not an AcDbAssocAction"); return true; }
        AcDbAssocNetworkEvaluationDisabler guard(pDb, true);
        AcDbObjectId depId;
        const Acad::ErrorStatus addEs = pAction->addDependency(
            AcDbAssocValueDependency::desc(), nullptr, true, false, 0, depId);
        if (addEs != Acad::eOk || depId.isNull()) {
            pAction->close();
            emitNativeError(r, "ADD_DEPENDENCY_FAILED", "addDependency(value factory) errorstatus " + std::to_string(static_cast<int>(addEs)));
            return true;
        }
        pAction->close();
        Acad::ErrorStatus nameEs = Acad::eOk;
        if (!valueName.empty()) {
            AcDbAssocValueDependency* pValDep = nullptr;
            if (acdbOpenObject(pValDep, depId, AcDb::kForWrite) == Acad::eOk) {
                nameEs = pValDep->setValueName(AcString(utf8ToWide(valueName).c_str()));
                pValDep->close();
            }
        }
        if (nameEs != Acad::eOk) { emitNativeError(r, "SET_VALUENAME_FAILED", "setValueName errorstatus " + std::to_string(static_cast<int>(nameEs))); return true; }
        r << "\"result\":{\"created\":true"
          << ",\"dependency_handle\":" << njsonStr(handleOfId(depId))
          << ",\"action_handle\":" << njsonStr(actionHex)
          << ",\"value_name\":" << njsonStr(valueName) << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // define.perssubentid.resolve — enumerate a target entity's subentities of a given
    // type via the read-only subentity protocol (subentPtr). Reports the gs-marker indices
    // the entity exposes. Read/compute, no eval.
    if (op == "define.perssubentid.resolve") {
        std::string targetHex;
        if (!m08kcFindHandle(job, "target_handle", targetHex) && !m08kcFindHandle(job, "handle", targetHex)) {
            emitNativeError(r, "MISSING_ARG", "define.perssubentid.resolve requires 'target_handle'"); return true;
        }
        double subTypeD = 0.0; jsonFindNumber(job, "subent_type", subTypeD);
        AcDb::SubentType subType = AcDb::kEdgeSubentType;
        const int st = static_cast<int>(subTypeD);
        if (st == 1) subType = AcDb::kFaceSubentType;
        else if (st == 2) subType = AcDb::kVertexSubentType;
        AriadneReadTransaction tr(pDb);
        AcDbObjectId entId;
        if (!resolveHandle(pDb, targetHex, entId)) { emitNativeError(r, "TARGET_NOT_FOUND", "no entity for handle " + targetHex); return true; }
        AcDbEntity* pEnt = nullptr;
        if (acdbOpenObject(pEnt, entId, AcDb::kForRead) != Acad::eOk) { emitNativeError(r, "TARGET_NOT_FOUND", "open failed " + targetHex); return true; }
        int count = 0;
        std::ostringstream arr; arr << "[";
        for (int marker = 1; marker <= 256; ++marker) {
            // subentPtr takes a full subent PATH (object id chain + subent id); build the
            // single-leaf path for this entity + (type,marker) and resolve it read-only.
            const AcDbSubentId sid(subType, static_cast<Adesk::GsMarker>(marker));
            const AcDbFullSubentPath path(entId, sid);
            AcDbEntity* pSub = pEnt->subentPtr(path);   // heap subentity copy or nullptr
            if (pSub != nullptr) {
                if (count) arr << ",";
                arr << "{\"subent_type\":" << st << ",\"index\":" << marker << "}";
                ++count;
                delete pSub;
            }
        }
        arr << "]";
        pEnt->close();
        r << "\"result\":{\"target_handle\":" << njsonStr(targetHex)
          << ",\"subent_type\":" << st
          << ",\"resolved_count\":" << count
          << ",\"subentities\":" << arr.str() << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    //========================================================================
    // constraints (read + delete only)
    //========================================================================

    // edit.constraint.delete — delete one geometric constraint (by index) from a
    // constraint group (by handle). Pure removal — adding would need the DCM solver, but
    // deletion does not solve.
    if (op == "edit.constraint.delete") {
        std::string groupHex;
        if (!m08kcFindHandle(job, "group_handle", groupHex) && !m08kcFindHandle(job, "handle", groupHex)) {
            emitNativeError(r, "MISSING_ARG", "edit.constraint.delete requires 'group_handle' (AcDbAssoc2dConstraintGroup)"); return true;
        }
        double idxD = 0.0; jsonFindNumber(job, "constraint_index", idxD);
        const int idx = static_cast<int>(idxD);
        AcDbObject* pObj = m08kcOpenObject(pDb, groupHex, AcDb::kForWrite);
        AcDbAssoc2dConstraintGroup* pGroup = AcDbAssoc2dConstraintGroup::cast(pObj);
        if (pGroup == nullptr) { if (pObj) pObj->close(); emitNativeError(r, "GROUP_NOT_FOUND", "handle " + groupHex + " is not an AcDbAssoc2dConstraintGroup"); return true; }
        AcArray<AcGeomConstraint*> cons;
        const Acad::ErrorStatus getEs = pGroup->getConstraints(cons);
        if (getEs != Acad::eOk || idx < 0 || idx >= cons.length() || cons[idx] == nullptr) {
            pGroup->close();
            emitNativeError(r, "CONSTRAINT_INDEX_OOR", "constraint_index out of range (have " + std::to_string(cons.length()) + ")");
            return true;
        }
        AcDbAssocNetworkEvaluationDisabler guard(pDb, true);
        const std::string tcls = m08kcRxClassName(cons[idx]);
        const Acad::ErrorStatus delEs = pGroup->deleteConstraint(cons[idx]);
        pGroup->close();
        if (delEs != Acad::eOk) { emitNativeError(r, "DELETE_CONSTRAINT_FAILED", "deleteConstraint errorstatus " + std::to_string(static_cast<int>(delEs))); return true; }
        r << "\"result\":{\"deleted\":true,\"group_handle\":" << njsonStr(groupHex)
          << ",\"constraint_index\":" << idx
          << ",\"constraint_class\":" << tcls << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // inspect.constraint.enumerate — list constraints of a constraint group (by handle):
    // index, RTTI class, enabled, active. Read-only.
    if (op == "inspect.constraint.enumerate") {
        std::string groupHex;
        if (!m08kcFindHandle(job, "group_handle", groupHex) && !m08kcFindHandle(job, "handle", groupHex)) {
            emitNativeError(r, "MISSING_ARG", "inspect.constraint.enumerate requires 'group_handle'"); return true;
        }
        AriadneReadTransaction tr(pDb);
        AcDbObject* pObj = m08kcOpenObject(pDb, groupHex, AcDb::kForRead);
        AcDbAssoc2dConstraintGroup* pGroup = AcDbAssoc2dConstraintGroup::cast(pObj);
        if (pGroup == nullptr) { if (pObj) pObj->close(); emitNativeError(r, "GROUP_NOT_FOUND", "handle " + groupHex + " is not an AcDbAssoc2dConstraintGroup"); return true; }
        AcArray<AcGeomConstraint*> cons;
        const Acad::ErrorStatus getEs = pGroup->getConstraints(cons);
        std::ostringstream arr; arr << "[";
        int n = 0;
        if (getEs == Acad::eOk) {
            for (int i = 0; i < cons.length(); ++i) {
                if (cons[i] == nullptr) continue;
                if (n) arr << ",";
                arr << "{\"index\":" << i
                    << ",\"class\":" << m08kcRxClassName(cons[i])
                    << ",\"enabled\":" << (cons[i]->isEnabled() ? "true" : "false")
                    << ",\"active\":" << (cons[i]->isActive() ? "true" : "false") << "}";
                ++n;
            }
        }
        arr << "]";
        pGroup->close();
        r << "\"result\":{\"group_handle\":" << njsonStr(groupHex)
          << ",\"constraint_count\":" << n
          << ",\"constraints\":" << arr.str() << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // inspect.constraint.node — read one constraint (by index) in a group: RTTI class,
    // enabled, active, implied, internal. Read-only.
    if (op == "inspect.constraint.node") {
        std::string groupHex;
        if (!m08kcFindHandle(job, "group_handle", groupHex) && !m08kcFindHandle(job, "handle", groupHex)) {
            emitNativeError(r, "MISSING_ARG", "inspect.constraint.node requires 'group_handle'"); return true;
        }
        double idxD = 0.0; jsonFindNumber(job, "constraint_index", idxD);
        const int idx = static_cast<int>(idxD);
        AriadneReadTransaction tr(pDb);
        AcDbObject* pObj = m08kcOpenObject(pDb, groupHex, AcDb::kForRead);
        AcDbAssoc2dConstraintGroup* pGroup = AcDbAssoc2dConstraintGroup::cast(pObj);
        if (pGroup == nullptr) { if (pObj) pObj->close(); emitNativeError(r, "GROUP_NOT_FOUND", "handle " + groupHex + " is not an AcDbAssoc2dConstraintGroup"); return true; }
        AcArray<AcGeomConstraint*> cons;
        const Acad::ErrorStatus getEs = pGroup->getConstraints(cons);
        if (getEs != Acad::eOk || idx < 0 || idx >= cons.length() || cons[idx] == nullptr) {
            pGroup->close();
            emitNativeError(r, "CONSTRAINT_INDEX_OOR", "constraint_index out of range (have " + std::to_string(cons.length()) + ")");
            return true;
        }
        AcGeomConstraint* pC = cons[idx];
        r << "\"result\":{\"group_handle\":" << njsonStr(groupHex)
          << ",\"constraint_index\":" << idx
          << ",\"class\":" << m08kcRxClassName(pC)
          << ",\"enabled\":" << (pC->isEnabled() ? "true" : "false")
          << ",\"active\":" << (pC->isActive() ? "true" : "false")
          << ",\"implied\":" << (pC->isImplied() ? "true" : "false")
          << ",\"internal\":" << (pC->isInternal() ? "true" : "false") << "},"
          << "\"status\":\"ok\"}";
        pGroup->close();
        return true;
    }

    // inspect.constraint.status — report the constraint group's assoc status + constraint/
    // constrained-geometry counts (a health read). Read-only, no eval.
    if (op == "inspect.constraint.status") {
        std::string groupHex;
        if (!m08kcFindHandle(job, "group_handle", groupHex) && !m08kcFindHandle(job, "handle", groupHex)) {
            emitNativeError(r, "MISSING_ARG", "inspect.constraint.status requires 'group_handle'"); return true;
        }
        AriadneReadTransaction tr(pDb);
        AcDbObject* pObj = m08kcOpenObject(pDb, groupHex, AcDb::kForRead);
        AcDbAssoc2dConstraintGroup* pGroup = AcDbAssoc2dConstraintGroup::cast(pObj);
        if (pGroup == nullptr) { if (pObj) pObj->close(); emitNativeError(r, "GROUP_NOT_FOUND", "handle " + groupHex + " is not an AcDbAssoc2dConstraintGroup"); return true; }
        AcArray<AcGeomConstraint*> cons;
        pGroup->getConstraints(cons);
        AcArray<AcConstrainedGeometry*> geoms;
        pGroup->getConstrainedGeometries(geoms);
        const AcDbAssocStatus st = pGroup->status();
        r << "\"result\":{\"group_handle\":" << njsonStr(groupHex)
          << ",\"assoc_status\":" << njsonStr(std::string(m08kcStatusName(st)))
          << ",\"constraint_count\":" << cons.length()
          << ",\"constrained_geometry_count\":" << geoms.length() << "},"
          << "\"status\":\"ok\"}";
        pGroup->close();
        return true;
    }

    // inspect.constraint.dimensional.value — read the current value of a dimensional
    // constraint's backing variable (by variable handle). Read-only (returns the cached
    // value(); no expression solve).
    if (op == "inspect.constraint.dimensional.value") {
        std::string varHex;
        if (!m08kcFindHandle(job, "variable_handle", varHex) && !m08kcFindHandle(job, "handle", varHex)) {
            emitNativeError(r, "MISSING_ARG", "inspect.constraint.dimensional.value requires 'variable_handle' (AcDbAssocVariable)"); return true;
        }
        AriadneReadTransaction tr(pDb);
        AcDbObject* pObj = m08kcOpenObject(pDb, varHex, AcDb::kForRead);
        AcDbAssocVariable* pVar = AcDbAssocVariable::cast(pObj);
        if (pVar == nullptr) { if (pObj) pObj->close(); emitNativeError(r, "VARIABLE_NOT_FOUND", "handle " + varHex + " is not an AcDbAssocVariable"); return true; }
        const AcString name = pVar->name();
        const AcString expr = pVar->expression();
        double dv = 0.0;
        pVar->value().getValue(dv);   // best-effort numeric read of the cached value
        r << "\"result\":{\"variable_handle\":" << njsonStr(varHex)
          << ",\"name\":" << njsonStr(name.kwszPtr())
          << ",\"expression\":" << njsonStr(expr.kwszPtr())
          << ",\"value\":" << dv << "},"
          << "\"status\":\"ok\"}";
        pVar->close();
        return true;
    }

    //========================================================================
    // parameters / variables
    //========================================================================

    // define.parameter.variable — create an AcDbAssocVariable (name + expression/value),
    // make it DB-resident, and add it to the top-level network as an action. No eval.
    if (op == "define.parameter.variable") {
        std::string name, expression;
        if (!jsonFindString(job, "name", name) || name.empty()) {
            emitNativeError(r, "MISSING_ARG", "define.parameter.variable requires 'name'"); return true;
        }
        jsonFindString(job, "expression", expression);
        double value = 0.0; const bool hasValue = jsonFindNumber(job, "value", value);
        if (expression.empty() && hasValue) { std::ostringstream e; e << value; expression = e.str(); }
        if (expression.empty()) expression = "0";

        AcDbAssocNetworkEvaluationDisabler guard(pDb, true);
        const AcDbObjectId netId = m08kcTopNetworkId(pDb, true);
        if (netId.isNull()) { emitNativeError(r, "NETWORK_UNAVAILABLE", "no top-level assoc network"); return true; }
        AcDbAssocVariable* pVar = new AcDbAssocVariable();
        AcDbObjectId varId;
        Acad::ErrorStatus postEs = pDb->addAcDbObject(varId, pVar);
        if (postEs != Acad::eOk || varId.isNull()) {
            delete pVar;
            emitNativeError(r, "POST_VARIABLE_FAILED", "addAcDbObject(variable) errorstatus " + std::to_string(static_cast<int>(postEs)));
            return true;
        }
        // configure before reparenting into the network.
        AcString errMsg;
        const Acad::ErrorStatus setEs = pVar->setExpression(
            AcString(utf8ToWide(expression).c_str()), AcString(), true, false, errMsg);
        const Acad::ErrorStatus nameEs = pVar->setName(AcString(utf8ToWide(name).c_str()), true);
        if (hasValue) { AcDbEvalVariant ev(value); pVar->setValue(ev); }
        pVar->close();
        AcDbAssocNetwork* pNet = nullptr;
        if (acdbOpenObject(pNet, netId, AcDb::kForWrite) != Acad::eOk) { emitNativeError(r, "NETWORK_OPEN_FAILED", "open top network for write"); return true; }
        const Acad::ErrorStatus addEs = pNet->addAction(varId, true);
        pNet->close();
        if (addEs != Acad::eOk) { emitNativeError(r, "ADD_VARIABLE_FAILED", "addAction(variable) errorstatus " + std::to_string(static_cast<int>(addEs))); return true; }
        if (nameEs != Acad::eOk) { emitNativeError(r, "SET_NAME_FAILED", "setName errorstatus " + std::to_string(static_cast<int>(nameEs))); return true; }
        r << "\"result\":{\"created\":true"
          << ",\"variable_handle\":" << njsonStr(handleOfId(varId))
          << ",\"name\":" << njsonStr(name)
          << ",\"expression\":" << njsonStr(expression)
          << ",\"expr_status\":" << static_cast<int>(setEs) << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // define.parameter.merge — set/overwrite an existing variable's expression by name, OR
    // create it if absent (idempotent "merge"). Searches the network for the name.
    if (op == "define.parameter.merge") {
        std::string name, expression;
        if (!jsonFindString(job, "name", name) || name.empty()) {
            emitNativeError(r, "MISSING_ARG", "define.parameter.merge requires 'name'"); return true;
        }
        jsonFindString(job, "expression", expression);
        if (expression.empty()) expression = "0";

        AcDbAssocNetworkEvaluationDisabler guard(pDb, true);
        const AcDbObjectId netId = m08kcTopNetworkId(pDb, true);
        if (netId.isNull()) { emitNativeError(r, "NETWORK_UNAVAILABLE", "no top-level assoc network"); return true; }
        AcDbAssocNetwork* pNet = nullptr;
        if (acdbOpenObject(pNet, netId, AcDb::kForWrite) != Acad::eOk) { emitNativeError(r, "NETWORK_OPEN_FAILED", "open top network for write"); return true; }
        const AcDbObjectIdArray actions = pNet->getActions();
        AcDbObjectId existingId;
        const AcString wantName(utf8ToWide(name).c_str());
        for (int i = 0; i < actions.length() && existingId.isNull(); ++i) {
            AcDbObject* pObj = nullptr;
            if (acdbOpenObject(pObj, actions[i], AcDb::kForRead) != Acad::eOk) continue;
            AcDbAssocVariable* pV = AcDbAssocVariable::cast(pObj);
            if (pV != nullptr && pV->name() == wantName) existingId = actions[i];
            pObj->close();
        }
        bool created = false;
        AcDbObjectId varId = existingId;
        AcString errMsg;
        Acad::ErrorStatus setEs = Acad::eOk;
        if (existingId.isNull()) {
            AcDbAssocVariable* pVar = new AcDbAssocVariable();
            Acad::ErrorStatus postEs = pDb->addAcDbObject(varId, pVar);
            if (postEs != Acad::eOk || varId.isNull()) { delete pVar; pNet->close(); emitNativeError(r, "POST_VARIABLE_FAILED", "addAcDbObject(variable) errorstatus " + std::to_string(static_cast<int>(postEs))); return true; }
            pVar->setName(wantName, true);
            setEs = pVar->setExpression(AcString(utf8ToWide(expression).c_str()), AcString(), true, false, errMsg);
            pVar->close();
            const Acad::ErrorStatus addEs = pNet->addAction(varId, true);
            if (addEs != Acad::eOk) { pNet->close(); emitNativeError(r, "ADD_VARIABLE_FAILED", "addAction(variable) errorstatus " + std::to_string(static_cast<int>(addEs))); return true; }
            created = true;
        } else {
            AcDbAssocVariable* pVar = nullptr;
            if (acdbOpenObject(pVar, existingId, AcDb::kForWrite) == Acad::eOk) {
                setEs = pVar->setExpression(AcString(utf8ToWide(expression).c_str()), AcString(), true, false, errMsg);
                pVar->close();
            }
        }
        pNet->close();
        r << "\"result\":{\"merged\":true,\"created\":" << (created ? "true" : "false")
          << ",\"variable_handle\":" << njsonStr(handleOfId(varId))
          << ",\"name\":" << njsonStr(name)
          << ",\"expression\":" << njsonStr(expression)
          << ",\"expr_status\":" << static_cast<int>(setEs) << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // inspect.parameter.evaluate — evaluate a standalone expression via the AcDbAssocVariable
    // static EXPRESSION evaluator (math/parameter parser, resolving names against the
    // network). This is NOT the network solver; it parses+evaluates a formula string.
    if (op == "inspect.parameter.evaluate") {
        std::string expression;
        if (!jsonFindString(job, "expression", expression) || expression.empty()) {
            emitNativeError(r, "MISSING_ARG", "inspect.parameter.evaluate requires 'expression'"); return true;
        }
        const AcDbObjectId netId = m08kcTopNetworkId(pDb, false);
        AcDbEvalVariant result;
        AcString assignedSym, errMsg;
        const Acad::ErrorStatus es = AcDbAssocVariable::evaluateExpression(
            AcString(utf8ToWide(expression).c_str()), AcString(), netId, result, assignedSym, errMsg);
        if (es != Acad::eOk) {
            r << "\"result\":{\"evaluated\":false,\"expression\":" << njsonStr(expression)
              << ",\"errorstatus\":" << static_cast<int>(es)
              << ",\"message\":" << njsonStr(errMsg.kwszPtr() ? acharToAscii(errMsg.kwszPtr()) : std::string()) << "},"
              << "\"status\":\"ok\"}";
            return true;
        }
        double dv = 0.0; result.getValue(dv);
        r << "\"result\":{\"evaluated\":true,\"expression\":" << njsonStr(expression)
          << ",\"value\":" << dv << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    //========================================================================
    // assoc arrays — read-only identify
    //========================================================================

    // inspect.assocarray.identify — is the target entity an associative array? If so,
    // report its controlling action-body handle. Pure read (no layout eval).
    if (op == "inspect.assocarray.identify") {
        std::string targetHex;
        if (!m08kcFindHandle(job, "target_handle", targetHex) && !m08kcFindHandle(job, "handle", targetHex)) {
            emitNativeError(r, "MISSING_ARG", "inspect.assocarray.identify requires 'target_handle'"); return true;
        }
        AriadneReadTransaction tr(pDb);
        AcDbObjectId entId;
        if (!resolveHandle(pDb, targetHex, entId)) { emitNativeError(r, "TARGET_NOT_FOUND", "no entity for handle " + targetHex); return true; }
        AcDbEntity* pEnt = nullptr;
        if (acdbOpenObject(pEnt, entId, AcDb::kForRead) != Acad::eOk) { emitNativeError(r, "TARGET_NOT_FOUND", "open failed " + targetHex); return true; }
        const bool isArray = AcDbAssocArrayActionBody::isAssociativeArray(pEnt);
        std::string bodyHandle;
        if (isArray) {
            const AcDbObjectId bodyId = AcDbAssocArrayActionBody::getControllingActionBody(pEnt);
            if (!bodyId.isNull()) bodyHandle = handleOfId(bodyId);
        }
        pEnt->close();
        r << "\"result\":{\"target_handle\":" << njsonStr(targetHex)
          << ",\"is_associative_array\":" << (isArray ? "true" : "false")
          << ",\"action_body_handle\":" << njsonStr(bodyHandle) << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // Admitted by HasOp but no branch handled it -> seam drift. Emit the structured
    // guard (lockstep invariant; mirrors the sibling family modules).
    emitNativeError(r, "OPERATION_DISPATCH_MISMATCH",
                    "operation '" + op + "' admitted by m08kcHasOp but not handled in m08kcDispatch");
    return true;
}
