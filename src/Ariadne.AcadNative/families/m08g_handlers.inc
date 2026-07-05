// families/m08g_handlers.inc — M08G WRITE family: entity creation + entity/geometry modify (staged-write).
//
// Owned by the M08G teammate (PR-scoped). #included into AriadneNativeJob.cpp; sees every in-TU
// helper. Contract (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - m08gHasOp(op): true for every op id this family IMPLEMENTS (gate admission). Ops left out
//     keep returning the honest OPERATION_NOT_IMPLEMENTED. NO FAKES.
//   - m08gDispatch(op, ctx, r): if op is yours, append  "result":{...},"status":"ok"  (or an
//     emitNativeError-style error) to r and return true; else return false.
//
// SAFETY (hard): staged-write ONLY. Operate on ctx.pDb (the router-staged in-memory copy).
//   Never call save()/saveAs() on the original. No acedCommand/acedCmd (compile-disabled in 2027).
//   Original DWG bytes must stay unchanged. Every AcDb object new()'d is closed on append success
//   and delete()'d on append failure (no leaks, no dangling DB objects).
//
// IMPLEMENTED (25): entity-create (18) + modify (7). Each does REAL ObjectARX work via an AcDb*
//   ctor + appendAcDbEntity, or an AcDbCurve/AcDbEntity modify protocol method. The full op brief
//   lists 45; the 20 not admitted here are HONEST deferrals (ASM modeler / external resource /
//   editor-bound) documented in reports/tickets/M08G.md — they keep returning OPERATION_NOT_IMPLEMENTED.
//
//   entity-create: arc, ellipse, point, ray, xline, trace, solid2d, face, spline, polyline,
//     polyline2d, polyline3d, attribdef, polygonmesh, region, blockref, minsert, tolerance
//   modify: modify.entity.transform, modify.entity.copy_transformed, modify.entity.common,
//     modify.entity.explode, modify.curve.offset, modify.curve.split, modify.curve.to_spline
//
// Reachability: AcDbArc/Point/Face/Solid/Trace/2dPolyline/3dPolyline/PolygonMesh/
//   AttributeDefinition/BlockReference/MInsertBlock come from dbents.h (main inc); AcDbPolyline
//   from dbpl.h (main inc); AcDbSpline from dbspline.h, AcDbEllipse from dbelipse.h, AcDbRay from
//   dbray.h, AcDbXline from dbxline.h, AcDbRegion from dbregion.h, AcDbFcf from dbfcf.h (added
//   below — all on the project's AdditionalIncludeDirectories, linked via acdbcore/acdb 26 already
//   on the .crx/.arx linker path). AcDbCurve modify protocol (getOffsetCurves/getSplitCurves/
//   getSpline) + AcGeMatrix3d/AcGeScale3d come from dbcurve.h/gemat3d.h/gescl3d.h pulled in by the
//   sibling m08d_handlers.inc earlier in this TU.

#include "dbspline.h"     // AcDbSpline (fit-point ctor)
#include "dbelipse.h"     // AcDbEllipse
#include "dbray.h"        // AcDbRay
#include "dbxline.h"      // AcDbXline
#include "dbregion.h"     // AcDbRegion::createFromCurves
#include "dbfcf.h"        // AcDbFcf (tolerance / feature control frame)
#include "dbmline.h"      // AcDbMline
#include "dbmstyle.h"     // AcDbMlineStyle / current mline style id
#include "dbsol3d.h"      // AcDb3dSolid heavy modeler operations
#include "dbbody.h"       // AcDbBody
#include "dbsurf.h"       // AcDbSurface::createFrom
#include "dbnurbsurf.h"   // AcDbNurbSurface
#include "dbSubD.h"       // AcDbSubDMesh
#include "dbmpolygon.h"   // AcDbMPolygon
#include "dbSweepOptions.h"
#include "dbRevolveOptions.h"
#include "dbLoftOptions.h"
#include "gekvec.h"       // AcGeKnotVector for NURBS surface
#include "imgdef.h"       // AcDbRasterImageDef
#include "imgent.h"       // AcDbRasterImage
#include "dbwipe.h"       // AcDbWipeout
#include "rxdlinkr.h"     // AcRxDynamicLinker / acrxDynamicLinker singleton (wA-cert engine-load fix)

#pragma comment(lib, "AcMPolygonObj.lib")
#pragma comment(lib, "acismobj26.lib")

//============================================================================
// M08G shared helpers (file-scope statics in this TU; m08g-prefixed to avoid any
// collision with sibling family .inc files).
//============================================================================

// Append a freshly-new()'d entity to model space (staged). Optionally ensures the
// named layer and stamps it onto the entity. Mirrors appendLine/appendCircle. On
// success: pEnt is closed, idOut set, ms count refreshed, returns eOk. On failure:
// pEnt is delete()'d (ownership consumed either way) and a non-eOk status returned.
static Acad::ErrorStatus m08gAppendEntity(AcDbDatabase* pDb, const std::string& layer,
                                          AcDbEntity* pEnt, AcDbObjectId& idOut,
                                          int& modelspaceAfter)
{
    idOut = AcDbObjectId::kNull;
    modelspaceAfter = 0;
    if (pEnt == nullptr)
        return Acad::eNullObjectPointer;

    if (!layer.empty()) {
        bool created = false;
        const Acad::ErrorStatus layerEs = ensureLayer(pDb, layer, 7, created);
        if (layerEs != Acad::eOk) { delete pEnt; return layerEs; }
    }

    AcDbBlockTable* pBT = nullptr;
    Acad::ErrorStatus es = pDb->getBlockTable(pBT, AcDb::kForRead);
    if (es != Acad::eOk) { delete pEnt; return es; }

    AcDbBlockTableRecord* pMS = nullptr;
    es = pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite);
    pBT->close();
    if (es != Acad::eOk) { delete pEnt; return es; }

    if (!layer.empty())
        pEnt->setLayer(asciiToWide(layer).c_str());

    es = pMS->appendAcDbEntity(idOut, pEnt);
    pMS->close();
    if (es == Acad::eOk)
        pEnt->close();
    else
        delete pEnt;

    int probes = 0;
    countModelSpace(pDb, modelspaceAfter, probes);
    return es;
}

// p3-insattr: like m08gAppendEntity above, but targets an ALREADY-OPEN-FOR-
// WRITE block table record the caller supplies, instead of the hardcoded
// ACDB_MODEL_SPACE -- needed for entities that only make sense as block-
// DEFINITION content (e.g. an ATTDEF template). Caller opens/closes pBlock;
// this function only owns pEnt (closed on success, delete()'d on failure,
// same contract as m08gAppendEntity).
static Acad::ErrorStatus m08gAppendEntityToBlock(AcDbBlockTableRecord* pBlock,
                                                 AcDbEntity* pEnt, AcDbObjectId& idOut)
{
    idOut = AcDbObjectId::kNull;
    if (pBlock == nullptr || pEnt == nullptr) {
        delete pEnt;
        return Acad::eNullObjectPointer;
    }
    const Acad::ErrorStatus es = pBlock->appendAcDbEntity(idOut, pEnt);
    if (es == Acad::eOk) pEnt->close();
    else delete pEnt;
    return es;
}

// wA-cert: force-load an AutoCAD engine .dbx module BEFORE constructing
// entities of a demand-loaded class. AcDbRasterImageDef/AcDbRasterImage/
// AcDbWipeout (module acismobj26.dbx) and AcDbMPolygon (module
// AcMPolygonObj26.dbx) are normally registered by AutoCAD's OWN demand-load
// table only when a document ALREADY containing an object of that class is
// opened, or a UI command that touches the class runs (e.g. IMAGEATTACH) --
// neither happens when this ARX module constructs a brand-new instance
// directly. Live-probed (a0-engineprep headless + r2-attended full acad.exe,
// both this same wave): without this, AcDbDictionary::setAt / AcDbBlockTable
// Record::appendAcDbEntity on these classes fails Acad::eNoClassId (409) even
// inside a full, attended acad.exe session -- not just headless
// accoreconsole. AcRxDynamicLinker::loadModule is idempotent (returns eOk if
// the module is already loaded), so calling this unconditionally at the top
// of every handler that needs the class is safe and cheap.
static bool m08gLoadEngineModule(const wchar_t* moduleFileName)
{
    AcRxDynamicLinker* linker = acrxDynamicLinker;
    if (linker == nullptr)
        return false;
    return linker->loadModule(moduleFileName, /*printit*/ false) == Acad::eOk;
}

// Standard create envelope: "result":{created,handle,layer,modelspace_entities_after},"status".
static void m08gEmitCreate(std::ostringstream& r, Acad::ErrorStatus es,
                           const AcDbObjectId& id, const std::string& layer, int msAfter)
{
    r << "\"result\":{\"created\":" << (es == Acad::eOk ? "true" : "false")
      << ",\"errorstatus\":" << static_cast<int>(es)
      << ",\"handle\":" << njsonStr(es == Acad::eOk ? handleOfId(id) : std::string())
      << ",\"layer\":" << njsonStr(layer)
      << ",\"modelspace_entities_after\":" << msAfter << "},"
      << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
}

// Read a point sub-object ("key":{x,y,z}) from the job (top-level or args), with a default.
static void m08gPoint(const std::string& job, const char* key,
                      double dx, double dy, double dz, AcGePoint3d& out)
{
    double x = dx, y = dy, z = dz;
    std::string obj;
    if (jsonFindObject(job, key, obj)) {
        jsonFindNumber(obj, "x", x); jsonFindNumber(obj, "y", y); jsonFindNumber(obj, "z", z);
    } else {
        std::string argsJson;
        if (jsonFindObject(job, "args", argsJson) && jsonFindObject(argsJson, key, obj)) {
            jsonFindNumber(obj, "x", x); jsonFindNumber(obj, "y", y); jsonFindNumber(obj, "z", z);
        }
    }
    out.set(x, y, z);
}

// Read a vector sub-object ("key":{x,y,z}) from the job, with a default.
static void m08gVector(const std::string& job, const char* key,
                       double dx, double dy, double dz, AcGeVector3d& out)
{
    double x = dx, y = dy, z = dz;
    std::string obj;
    if (jsonFindObject(job, key, obj)) {
        jsonFindNumber(obj, "x", x); jsonFindNumber(obj, "y", y); jsonFindNumber(obj, "z", z);
    }
    out.set(x, y, z);
}

// Pull a hex handle from the job ("handle", or args.handle).
static bool m08gFindHandle(const std::string& job, std::string& out)
{
    if (jsonFindString(job, "handle", out) && !out.empty())
        return true;
    std::string argsJson;
    if (jsonFindObject(job, "args", argsJson) &&
        jsonFindString(argsJson, "handle", out) && !out.empty())
        return true;
    return false;
}

// Parse a JSON array of point objects into an AcGePoint3dArray.
static int m08gReadPointArray(const std::string& job, const char* key, AcGePoint3dArray& out)
{
    out.removeAll();
    const std::string keyTok = std::string("\"") + key + "\"";
    size_t p = job.find(keyTok);
    if (p == std::string::npos)
        return 0;
    size_t lb = job.find('[', p);
    if (lb == std::string::npos)
        return 0;
    size_t rb = job.find(']', lb);
    if (rb == std::string::npos)
        rb = job.size();
    size_t scan = lb + 1;
    while (scan < rb) {
        size_t ob = job.find('{', scan);
        if (ob == std::string::npos || ob > rb) break;
        size_t oe = job.find('}', ob);
        if (oe == std::string::npos || oe > rb) break;
        const std::string one = job.substr(ob, oe - ob + 1);
        double x = 0.0, y = 0.0, z = 0.0;
        jsonFindNumber(one, "x", x); jsonFindNumber(one, "y", y); jsonFindNumber(one, "z", z);
        out.append(AcGePoint3d(x, y, z));
        scan = oe + 1;
    }
    return static_cast<int>(out.length());
}

// Open a model-resident entity for WRITE by hex handle (staged mutation target).
// Returns nullptr if the handle does not resolve or is not an entity. Caller closes.
static AcDbEntity* m08gOpenEntityForWrite(AcDbDatabase* pDb, const std::string& handleHex)
{
    AcDbObjectId id;
    if (!resolveHandle(pDb, handleHex, id))
        return nullptr;
    AcDbEntity* pEnt = nullptr;
    if (acdbOpenObject(pEnt, id, AcDb::kForWrite) != Acad::eOk)
        return nullptr;
    return pEnt;
}

// P10 (entity-handle-targeted xdata write): locate the [ ... ] span for a
// top-level array-valued key. Bracket-depth + string-aware (unlike the plain
// find(']', lb) m08gReadPointArray uses above), because a "values" item can
// itself carry a nested "value":[x,y,z] array -- a naive first-']' scan
// would truncate the outer array at that inner point payload's close bracket.
// Returns false if the key/array is not found. lb/rb land on '[' / matching ']'.
static bool m08gFindArraySpan(const std::string& job, const char* key,
                               size_t& lb, size_t& rb)
{
    const std::string k = std::string("\"") + key + "\"";
    size_t p = job.find(k);
    if (p == std::string::npos) return false;
    p = job.find(':', p + k.size());
    if (p == std::string::npos) return false;
    lb = job.find('[', p);
    if (lb == std::string::npos) return false;
    int depth = 0;
    bool inString = false, escaped = false;
    for (size_t i = lb; i < job.size(); ++i) {
        const char c = job[i];
        if (inString) {
            if (escaped) escaped = false;
            else if (c == '\\') escaped = true;
            else if (c == '"') inString = false;
            continue;
        }
        if (c == '"') { inString = true; continue; }
        if (c == '[') { ++depth; }
        else if (c == ']') { --depth; if (depth == 0) { rb = i; return true; } }
    }
    return false;
}

// P10: parse a "value":[n0,n1,n2] raw number triple (xdata point payload) out
// of one item object's substring. Unlike m08gReadPointArray above (an array
// of {x,y,z} objects), an xdata point item's "value" travels as a plain
// 3-number JSON array, so it needs its own small scanner.
static bool m08gReadValueTriple(const std::string& obj, double out[3])
{
    size_t p = obj.find("\"value\"");
    if (p == std::string::npos) return false;
    p = obj.find('[', p);
    if (p == std::string::npos) return false;
    const char* s = obj.c_str() + p + 1;
    char* endp = nullptr;
    for (int i = 0; i < 3; ++i) {
        while (*s == ' ' || *s == ',') ++s;
        out[i] = strtod(s, &endp);
        if (endp == s) return false;
        s = endp;
    }
    return true;
}

// Build a transform matrix from the job. Supports any combination, applied as
// scale -> rotate(about Z @ pivot) -> translate (composed T*R*S). Reads:
//   "translate":{x,y,z}, "scale":<num> (uniform), "rotate":<radians>, "pivot":{x,y,z}.
// Absent keys are identity. Returns the composed matrix.
static AcGeMatrix3d m08gReadTransform(const std::string& job)
{
    AcGeMatrix3d composed;   // identity
    // scale (uniform, about pivot/origin)
    double factor = 1.0;
    if (jsonFindNumber(job, "scale", factor) && factor != 0.0 && factor != 1.0) {
        AcGePoint3d pivot(0.0, 0.0, 0.0);
        m08gPoint(job, "pivot", 0.0, 0.0, 0.0, pivot);
        AcGeMatrix3d s; s.setToScaling(factor, pivot);
        composed.preMultBy(s);
    }
    // rotate (radians about Z through pivot)
    double angle = 0.0;
    if (jsonFindNumber(job, "rotate", angle) && angle != 0.0) {
        AcGePoint3d pivot(0.0, 0.0, 0.0);
        m08gPoint(job, "pivot", 0.0, 0.0, 0.0, pivot);
        AcGeMatrix3d rot; rot.setToRotation(angle, AcGeVector3d(0.0, 0.0, 1.0), pivot);
        composed.preMultBy(rot);
    }
    // translate
    std::string t;
    if (jsonFindObject(job, "translate", t)) {
        double tx = 0.0, ty = 0.0, tz = 0.0;
        jsonFindNumber(t, "x", tx); jsonFindNumber(t, "y", ty); jsonFindNumber(t, "z", tz);
        AcGeMatrix3d tr; tr.setToTranslation(AcGeVector3d(tx, ty, tz));
        composed.preMultBy(tr);
    }
    return composed;
}

// Append every AcDbEntity* in a caller-owned AcDbVoidPtrArray (e.g. from explode/
// getOffsetCurves/getSplitCurves) to model space. Frees any element that fails to
// append; appended elements are closed. Returns count appended; statusOut is the
// first non-eOk (or eOk).
static int m08gAppendPieces(AcDbDatabase* pDb, AcDbVoidPtrArray& pieces,
                            std::ostringstream& handlesJson, Acad::ErrorStatus& statusOut,
                            const std::string& layer = std::string())
{
    // wS-solids/G2 fix: an optional target layer, applied the same way every
    // other m08g create-branch already does (ensureLayer at the database
    // level once, then AcDbEntity::setLayer on each not-yet-resident piece
    // BEFORE appendAcDbEntity -- mirrors write.entity.polyfacemesh's proven
    // ensureLayer+setLayer-before-append ordering just above in this file).
    // Default-empty preserves EXACT prior behavior for this function's other
    // 3 call sites (explode/getOffsetCurves/getSplitCurves pieces, which have
    // no "layer" job-arg concept and should keep inheriting the source
    // entity's own layer) -- only write.entity.region passes a real layer.
    statusOut = Acad::eOk;
    handlesJson << "[";
    int appended = 0;
    if (!layer.empty()) { bool c = false; ensureLayer(pDb, layer, 7, c); }
    AcDbBlockTable* pBT = nullptr;
    if (pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk) {
        // free everything; nothing appended
        for (int i = 0; i < pieces.length(); ++i)
            delete static_cast<AcDbEntity*>(pieces[i]);
        handlesJson << "]";
        statusOut = Acad::eInvalidInput;
        return 0;
    }
    AcDbBlockTableRecord* pMS = nullptr;
    Acad::ErrorStatus es = pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite);
    pBT->close();
    if (es != Acad::eOk) {
        for (int i = 0; i < pieces.length(); ++i)
            delete static_cast<AcDbEntity*>(pieces[i]);
        handlesJson << "]";
        statusOut = es;
        return 0;
    }
    for (int i = 0; i < pieces.length(); ++i) {
        AcDbEntity* pPiece = static_cast<AcDbEntity*>(pieces[i]);
        if (pPiece == nullptr)
            continue;
        if (!layer.empty())
            pPiece->setLayer(asciiToWide(layer).c_str());
        AcDbObjectId pid;
        const Acad::ErrorStatus pe = pMS->appendAcDbEntity(pid, pPiece);
        if (pe == Acad::eOk) {
            if (appended) handlesJson << ",";
            handlesJson << njsonStr(handleOfId(pid));
            pPiece->close();
            ++appended;
        } else {
            if (statusOut == Acad::eOk) statusOut = pe;
            delete pPiece;
        }
    }
    pMS->close();
    handlesJson << "]";
    return appended;
}

static AcDbPolyline* m08gMakeRectProfile(double w, double h)
{
    if (w <= 0.0) w = 1.0;
    if (h <= 0.0) h = 1.0;
    AcDbPolyline* p = new AcDbPolyline();
    p->addVertexAt(0, AcGePoint2d(0.0, 0.0), 0.0);
    p->addVertexAt(1, AcGePoint2d(w, 0.0), 0.0);
    p->addVertexAt(2, AcGePoint2d(w, h), 0.0);
    p->addVertexAt(3, AcGePoint2d(0.0, h), 0.0);
    p->setClosed(Adesk::kTrue);
    return p;
}

static bool m08gRead2dVertices(const std::string& job, AcGePoint2dArray& pts)
{
    pts.removeAll();
    AcGePoint3dArray pts3;
    if (m08gReadPointArray(job, "vertices", pts3) < 3)
        m08gReadPointArray(job, "points", pts3);
    for (int i = 0; i < pts3.length(); ++i)
        pts.append(AcGePoint2d(pts3[i].x, pts3[i].y));
    return pts.length() >= 3;
}

static void m08gEmitModelerCreate(std::ostringstream& r, const char* kind, Acad::ErrorStatus es,
                                  const AcDbObjectId& id, const std::string& layer, int msAfter)
{
    r << "\"result\":{\"created\":" << (es == Acad::eOk ? "true" : "false")
      << ",\"kind\":" << njsonStr(std::string(kind))
      << ",\"errorstatus\":" << static_cast<int>(es)
      << ",\"handle\":" << njsonStr(es == Acad::eOk ? handleOfId(id) : std::string())
      << ",\"layer\":" << njsonStr(layer)
      << ",\"modelspace_entities_after\":" << msAfter << "},"
      << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
}

//============================================================================
// HasOp — every op id this family IMPLEMENTS (gate admission). Kept in lockstep
// with the dispatch branches below (asserted by tests/unit/test_m08g_handlers.py).
//============================================================================
static bool m08gHasOp(const std::string& op)
{
    return
        // entity-create
        op == "write.entity.arc" ||
        op == "write.entity.ellipse" ||
        op == "write.entity.point" ||
        op == "write.entity.ray" ||
        op == "write.entity.xline" ||
        op == "write.entity.trace" ||
        op == "write.entity.solid2d" ||
        op == "write.entity.face" ||
        op == "write.entity.spline" ||
        op == "write.entity.polyline" ||
        op == "write.entity.polyline2d" ||
        op == "write.entity.polyline2d.deep" ||
        op == "write.entity.polyline3d" ||
        op == "write.entity.attribdef" ||
        op == "write.entity.attribute" ||
        op == "write.entity.body" ||
        op == "write.entity.mline" ||
        op == "write.entity.mpolygon" ||
        op == "write.entity.nurbsurface" ||
        op == "write.entity.rasterimage" ||
        op == "write.entity.shape" ||
        op == "write.entity.solid3d.extrude" ||
        op == "write.entity.solid3d.loft" ||
        op == "write.entity.solid3d.primitive" ||
        op == "write.entity.solid3d.revolve" ||
        op == "write.entity.solid3d.sweep" ||
        op == "write.entity.subdmesh" ||
        op == "write.entity.surface" ||
        op == "write.entity.wipeout" ||
        op == "write.entity.polygonmesh" ||
        op == "write.entity.polyfacemesh" ||
        op == "write.entity.region" ||
        op == "write.entity.blockref" ||
        op == "write.entity.minsert" ||
        op == "write.entity.tolerance" ||
        // modify / geometry-edit
        op == "modify.entity.transform" ||
        op == "modify.entity.copy_transformed" ||
        op == "modify.entity.common" ||
        op == "modify.entity.xdata" ||
        op == "modify.entity.explode" ||
        op == "modify.entity.solid3d.boolean" ||
        op == "modify.curve.offset" ||
        op == "modify.curve.split" ||
        op == "modify.curve.to_spline";
}

//============================================================================
// Dispatch — one branch per admitted op (lockstep with HasOp). Each does real
// ObjectARX staged-write work on ctx.pDb and emits a result/error envelope.
//============================================================================
static bool m08gDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    if (!m08gHasOp(op))
        return false;

    AcDbDatabase* pDb = ctx.pDb;
    const std::string& job = ctx.job;

    std::string layer;
    jsonFindString(job, "layer", layer);

    //========================================================================
    // entity-create
    //========================================================================
    if (op == "write.entity.arc") {
        AcGePoint3d center; m08gPoint(job, "center", 0.0, 0.0, 0.0, center);
        double radius = 1.0, sa = 0.0, ea = 6.28318530717958647692;
        jsonFindNumber(job, "radius", radius);
        jsonFindNumber(job, "start_angle", sa);
        jsonFindNumber(job, "end_angle", ea);
        AcDbArc* pE = new AcDbArc(center, radius, sa, ea);
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitCreate(r, es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.ellipse") {
        AcGePoint3d center; m08gPoint(job, "center", 0.0, 0.0, 0.0, center);
        AcGeVector3d normal; m08gVector(job, "normal", 0.0, 0.0, 1.0, normal);
        AcGeVector3d major; m08gVector(job, "major_axis", 1.0, 0.0, 0.0, major);
        double ratio = 1.0, sa = 0.0, ea = 6.28318530717958647692;
        jsonFindNumber(job, "radius_ratio", ratio);
        jsonFindNumber(job, "start_angle", sa);
        jsonFindNumber(job, "end_angle", ea);
        AcDbEllipse* pE = new AcDbEllipse(center, normal, major, ratio, sa, ea);
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitCreate(r, es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.point") {
        AcGePoint3d pos; m08gPoint(job, "position", 0.0, 0.0, 0.0, pos);
        AcDbPoint* pE = new AcDbPoint(pos);
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitCreate(r, es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.ray") {
        AcGePoint3d base; m08gPoint(job, "base", 0.0, 0.0, 0.0, base);
        AcGeVector3d dir; m08gVector(job, "direction", 1.0, 0.0, 0.0, dir);
        AcDbRay* pE = new AcDbRay();
        pE->setBasePoint(base);
        if (!dir.isZeroLength()) pE->setUnitDir(dir);
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitCreate(r, es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.xline") {
        AcGePoint3d base; m08gPoint(job, "base", 0.0, 0.0, 0.0, base);
        AcGeVector3d dir; m08gVector(job, "direction", 1.0, 0.0, 0.0, dir);
        AcDbXline* pE = new AcDbXline();
        pE->setBasePoint(base);
        if (!dir.isZeroLength()) pE->setUnitDir(dir);
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitCreate(r, es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.trace") {
        AcGePoint3d p0, p1, p2, p3;
        m08gPoint(job, "p0", 0.0, 0.0, 0.0, p0);
        m08gPoint(job, "p1", 1.0, 0.0, 0.0, p1);
        m08gPoint(job, "p2", 1.0, 1.0, 0.0, p2);
        m08gPoint(job, "p3", 0.0, 1.0, 0.0, p3);
        AcDbTrace* pE = new AcDbTrace(p0, p1, p2, p3);
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitCreate(r, es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.solid2d") {
        AcGePoint3d p0, p1, p2, p3;
        m08gPoint(job, "p0", 0.0, 0.0, 0.0, p0);
        m08gPoint(job, "p1", 1.0, 0.0, 0.0, p1);
        m08gPoint(job, "p2", 1.0, 1.0, 0.0, p2);
        m08gPoint(job, "p3", 0.0, 1.0, 0.0, p3);
        AcDbSolid* pE = new AcDbSolid(p0, p1, p2, p3);
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitCreate(r, es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.face") {
        AcGePoint3d p0, p1, p2, p3;
        m08gPoint(job, "p0", 0.0, 0.0, 0.0, p0);
        m08gPoint(job, "p1", 1.0, 0.0, 0.0, p1);
        m08gPoint(job, "p2", 1.0, 1.0, 0.0, p2);
        m08gPoint(job, "p3", 0.0, 1.0, 0.0, p3);
        AcDbFace* pE = new AcDbFace(p0, p1, p2, p3);
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitCreate(r, es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.spline") {
        // Fit-point spline. Reads "points":[{x,y,z},...]; needs >= 2 points.
        AcGePoint3dArray fitPts;
        std::string ptsArr;
        if (jsonFindObject(job, "points_wrap", ptsArr)) { /* unused alt */ }
        // hand-roll: collect every {x:..,y:..,z:..} object inside the "points" array.
        {
            const std::string key = "\"points\"";
            size_t p = job.find(key);
            if (p != std::string::npos) {
                size_t lb = job.find('[', p);
                size_t rb = (lb == std::string::npos) ? std::string::npos : job.find(']', lb);
                size_t scan = (lb == std::string::npos) ? std::string::npos : lb + 1;
                while (scan != std::string::npos && rb != std::string::npos && scan < rb) {
                    size_t ob = job.find('{', scan);
                    if (ob == std::string::npos || ob > rb) break;
                    size_t oe = job.find('}', ob);
                    if (oe == std::string::npos || oe > rb) break;
                    const std::string one = job.substr(ob, oe - ob + 1);
                    double x = 0.0, y = 0.0, z = 0.0;
                    jsonFindNumber(one, "x", x); jsonFindNumber(one, "y", y); jsonFindNumber(one, "z", z);
                    fitPts.append(AcGePoint3d(x, y, z));
                    scan = oe + 1;
                }
            }
        }
        if (fitPts.length() < 2) {
            emitNativeError(r, "MISSING_ARG", "write.entity.spline requires 'points':[>=2 {x,y,z}]");
            return true;
        }
        double order = 4.0;
        jsonFindNumber(job, "order", order);
        if (order < 2) order = 4;
        AcDbSpline* pE = new AcDbSpline(fitPts, static_cast<int>(order), 0.0);
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitCreate(r, es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.polyline" || op == "write.entity.polyline2d") {
        // Lightweight AcDbPolyline (LWPOLYLINE). 2D vertices in the XY plane; both
        // op ids map here (a 2d polyline IS the lightweight polyline for create).
        AcDbPolyline* pE = new AcDbPolyline();
        int n = 0;
        const std::string key = "\"points\"";
        size_t p = job.find(key);
        if (p != std::string::npos) {
            size_t lb = job.find('[', p);
            size_t rb = (lb == std::string::npos) ? std::string::npos : job.find(']', lb);
            size_t scan = (lb == std::string::npos) ? std::string::npos : lb + 1;
            while (scan != std::string::npos && rb != std::string::npos && scan < rb) {
                size_t ob = job.find('{', scan);
                if (ob == std::string::npos || ob > rb) break;
                size_t oe = job.find('}', ob);
                if (oe == std::string::npos || oe > rb) break;
                const std::string one = job.substr(ob, oe - ob + 1);
                double x = 0.0, y = 0.0, bulge = 0.0;
                jsonFindNumber(one, "x", x); jsonFindNumber(one, "y", y);
                jsonFindNumber(one, "bulge", bulge);
                pE->addVertexAt(static_cast<unsigned int>(n), AcGePoint2d(x, y), bulge);
                ++n;
                scan = oe + 1;
            }
        }
        if (n < 2) { delete pE; emitNativeError(r, "MISSING_ARG", "polyline requires 'points':[>=2 {x,y}]"); return true; }
        bool closed = false;
        { double cf = 0.0; if (jsonFindNumber(job, "closed", cf)) closed = (cf != 0.0); }
        if (closed) pE->setClosed(Adesk::kTrue);
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitCreate(r, es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.polyline3d") {
        // True AcDb3dPolyline: append the (empty) polyline first so it is DB-resident,
        // then append vertices to it (the AcDb append-vertex contract). Roll back via
        // the staged transaction if any step fails.
        AcGePoint3dArray verts;
        const std::string key = "\"points\"";
        size_t p = job.find(key);
        if (p != std::string::npos) {
            size_t lb = job.find('[', p);
            size_t rb = (lb == std::string::npos) ? std::string::npos : job.find(']', lb);
            size_t scan = (lb == std::string::npos) ? std::string::npos : lb + 1;
            while (scan != std::string::npos && rb != std::string::npos && scan < rb) {
                size_t ob = job.find('{', scan);
                if (ob == std::string::npos || ob > rb) break;
                size_t oe = job.find('}', ob);
                if (oe == std::string::npos || oe > rb) break;
                const std::string one = job.substr(ob, oe - ob + 1);
                double x = 0.0, y = 0.0, z = 0.0;
                jsonFindNumber(one, "x", x); jsonFindNumber(one, "y", y); jsonFindNumber(one, "z", z);
                verts.append(AcGePoint3d(x, y, z));
                scan = oe + 1;
            }
        }
        if (verts.length() < 2) {
            emitNativeError(r, "MISSING_ARG", "write.entity.polyline3d requires 'points':[>=2 {x,y,z}]");
            return true;
        }
        if (!layer.empty()) { bool c = false; ensureLayer(pDb, layer, 7, c); }
        AcDbBlockTable* pBT = nullptr;
        Acad::ErrorStatus es = pDb->getBlockTable(pBT, AcDb::kForRead);
        if (es != Acad::eOk) { emitNativeError(r, "DB_ERROR", "getBlockTable"); return true; }
        AcDbBlockTableRecord* pMS = nullptr;
        es = pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite);
        pBT->close();
        if (es != Acad::eOk) { emitNativeError(r, "DB_ERROR", "getAt modelspace"); return true; }
        AcDb3dPolyline* pE = new AcDb3dPolyline();
        if (!layer.empty()) pE->setLayer(asciiToWide(layer).c_str());
        AcDbObjectId id;
        es = pMS->appendAcDbEntity(id, pE);
        if (es != Acad::eOk) { delete pE; pMS->close(); emitNativeError(r, "APPEND_FAILED", "appendAcDbEntity 3dpolyline"); return true; }
        Acad::ErrorStatus vEs = Acad::eOk;
        for (int i = 0; i < verts.length(); ++i) {
            AcDb3dPolylineVertex* pV = new AcDb3dPolylineVertex(verts[i]);
            AcDbObjectId vid;
            const Acad::ErrorStatus e2 = pE->appendVertex(vid, pV);
            if (e2 == Acad::eOk) pV->close();
            else { delete pV; vEs = e2; break; }
        }
        pE->close();
        pMS->close();
        int probes = 0, ms = 0; countModelSpace(pDb, ms, probes);
        if (vEs != Acad::eOk) { emitNativeError(r, "APPEND_FAILED", "appendVertex 3dpolyline"); return true; }
        m08gEmitCreate(r, Acad::eOk, id, layer, ms);
        return true;
    }
    if (op == "write.entity.polyline2d.deep") {
        // p4-poly2d: the TRUE legacy AcDb2dPolyline -- distinct from
        // write.entity.polyline2d above (which is an ALIAS building
        // AcDbPolyline/LWPOLYLINE, see that branch's comment). Scope:
        // k2dSimplePoly only (the ctor default polyType()), with per-vertex
        // bulge/start_width/end_width, a shared elevation, a closed flag, and
        // polyline-level default widths (AutoCAD's "constant width" case: a
        // vertex whose own start/end width is 0/0 renders at
        // defaultStartWidth/defaultEndWidth instead). Curve-fit/spline-fit
        // poly types (k2dFitCurvePoly/k2dQuadSplinePoly/k2dCubicSplinePoly)
        // are OUT OF SCOPE: AutoCAD synthesizes extra fit/spline vertices for
        // those that are not args-derivable, so a diff=0 roundtrip claim
        // would be dishonest -- left uncertified on purpose.
        AcGePoint3dArray pts;
        AcGeDoubleArray bulges, startWidths, endWidths;
        {
            const std::string key = "\"points\"";
            size_t p = job.find(key);
            if (p != std::string::npos) {
                size_t lb = job.find('[', p);
                size_t rb = (lb == std::string::npos) ? std::string::npos : job.find(']', lb);
                size_t scan = (lb == std::string::npos) ? std::string::npos : lb + 1;
                while (scan != std::string::npos && rb != std::string::npos && scan < rb) {
                    size_t ob = job.find('{', scan);
                    if (ob == std::string::npos || ob > rb) break;
                    size_t oe = job.find('}', ob);
                    if (oe == std::string::npos || oe > rb) break;
                    const std::string one = job.substr(ob, oe - ob + 1);
                    double x = 0.0, y = 0.0, bulge = 0.0, sw = 0.0, ew = 0.0;
                    jsonFindNumber(one, "x", x); jsonFindNumber(one, "y", y);
                    jsonFindNumber(one, "bulge", bulge);
                    jsonFindNumber(one, "start_width", sw);
                    jsonFindNumber(one, "end_width", ew);
                    pts.append(AcGePoint3d(x, y, 0.0));
                    bulges.append(bulge);
                    startWidths.append(sw);
                    endWidths.append(ew);
                    scan = oe + 1;
                }
            }
        }
        if (pts.length() < 2) {
            emitNativeError(r, "MISSING_ARG", "write.entity.polyline2d.deep requires 'points':[>=2 {x,y}]");
            return true;
        }
        double elevation = 0.0; jsonFindNumber(job, "elevation", elevation);
        bool closed = false;
        { double cf = 0.0; if (jsonFindNumber(job, "closed", cf)) closed = (cf != 0.0); }
        double defStartW = 0.0, defEndW = 0.0;
        jsonFindNumber(job, "default_start_width", defStartW);
        jsonFindNumber(job, "default_end_width", defEndW);
        if (!layer.empty()) { bool c = false; ensureLayer(pDb, layer, 7, c); }
        AcDbBlockTable* pBT = nullptr;
        Acad::ErrorStatus es = pDb->getBlockTable(pBT, AcDb::kForRead);
        if (es != Acad::eOk) { emitNativeError(r, "DB_ERROR", "getBlockTable"); return true; }
        AcDbBlockTableRecord* pMS = nullptr;
        es = pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite);
        pBT->close();
        if (es != Acad::eOk) { emitNativeError(r, "DB_ERROR", "getAt modelspace"); return true; }
        AcDb2dPolyline* pE = new AcDb2dPolyline();
        if (!layer.empty()) pE->setLayer(asciiToWide(layer).c_str());
        pE->setElevation(elevation);
        if (closed) pE->setClosed(Adesk::kTrue);
        pE->setDefaultStartWidth(defStartW);
        pE->setDefaultEndWidth(defEndW);
        AcDbObjectId id;
        es = pMS->appendAcDbEntity(id, pE);
        if (es != Acad::eOk) { delete pE; pMS->close(); emitNativeError(r, "APPEND_FAILED", "appendAcDbEntity 2dpolyline"); return true; }
        Acad::ErrorStatus vEs = Acad::eOk;
        for (int i = 0; i < pts.length(); ++i) {
            AcDb2dVertex* pV = new AcDb2dVertex(AcGePoint3d(pts[i].x, pts[i].y, elevation),
                                                 bulges[i], startWidths[i], endWidths[i]);
            AcDbObjectId vid;
            const Acad::ErrorStatus e2 = pE->appendVertex(vid, pV);
            if (e2 == Acad::eOk) pV->close();
            else { delete pV; vEs = e2; break; }
        }
        pE->close();
        pMS->close();
        int probes = 0, ms = 0; countModelSpace(pDb, ms, probes);
        if (vEs != Acad::eOk) { emitNativeError(r, "APPEND_FAILED", "appendVertex 2dpolyline"); return true; }
        m08gEmitCreate(r, Acad::eOk, id, layer, ms);
        return true;
    }
    if (op == "write.entity.attribdef") {
        AcGePoint3d pos; m08gPoint(job, "position", 0.0, 0.0, 0.0, pos);
        std::string text, tag, prompt, blockName;
        jsonFindString(job, "text", text);
        jsonFindString(job, "tag", tag);
        jsonFindString(job, "prompt", prompt);
        // p3-insattr: optional "block" targets a NAMED block definition's own
        // entity list (see the m08gAppendEntityToBlock branch below) so this
        // ATTDEF serves as a real block template; absent "block", behavior is
        // byte-identical to before this change (modelspace, via
        // m08gAppendEntity).
        jsonFindString(job, "block", blockName);
        double height = 1.0; jsonFindNumber(job, "height", height);
        AcDbAttributeDefinition* pE = new AcDbAttributeDefinition();
        pE->setPosition(pos);
        if (height > 0.0) pE->setHeight(height);
        if (!text.empty())   pE->setTextString(utf8ToWide(text).c_str());
        if (!tag.empty())    pE->setTag(utf8ToWide(tag).c_str());
        if (!prompt.empty()) pE->setPrompt(utf8ToWide(prompt).c_str());
        // p3-insattr: the four ATTDEF mode flags (dbents.h). Each is read only
        // when the job supplies it (jsonFindNumber's bool return), so omitting
        // them keeps the ObjectARX ctor defaults (all false) -- no silent
        // behavior change for callers who don't pass them.
        double flagVal = 0.0;
        if (jsonFindNumber(job, "constant", flagVal))
            pE->setConstant(flagVal != 0.0 ? Adesk::kTrue : Adesk::kFalse);
        if (jsonFindNumber(job, "invisible", flagVal))
            pE->setInvisible(flagVal != 0.0 ? Adesk::kTrue : Adesk::kFalse);
        if (jsonFindNumber(job, "verifiable", flagVal))
            pE->setVerifiable(flagVal != 0.0 ? Adesk::kTrue : Adesk::kFalse);
        if (jsonFindNumber(job, "preset", flagVal))
            pE->setPreset(flagVal != 0.0 ? Adesk::kTrue : Adesk::kFalse);
        if (!blockName.empty()) {
            AcDbBlockTable* pBT = nullptr;
            Acad::ErrorStatus bes = pDb->getBlockTable(pBT, AcDb::kForRead);
            AcDbObjectId targetBlockId;
            if (bes == Acad::eOk) {
                bes = pBT->getAt(asciiToWide(blockName).c_str(), targetBlockId);
                pBT->close();
            }
            AcDbBlockTableRecord* pTargetBlock = nullptr;
            if (bes == Acad::eOk)
                bes = acdbOpenObject(pTargetBlock, targetBlockId, AcDb::kForWrite);
            if (bes != Acad::eOk) {
                delete pE;
                emitNativeError(r, "BLOCK_NOT_FOUND",
                                "write.entity.attribdef: no block definition named '" + blockName + "'");
                return true;
            }
            AcDbObjectId id;
            const Acad::ErrorStatus es = m08gAppendEntityToBlock(pTargetBlock, pE, id);
            pTargetBlock->close();
            r << "\"result\":{\"created\":" << (es == Acad::eOk ? "true" : "false")
              << ",\"errorstatus\":" << static_cast<int>(es)
              << ",\"handle\":" << njsonStr(es == Acad::eOk ? handleOfId(id) : std::string())
              << ",\"block\":" << njsonStr(blockName) << "},"
              << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
            return true;
        }
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitCreate(r, es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.attribute") {
        std::string blockRefHandle;
        if (!jsonFindString(job, "blockref_handle", blockRefHandle) || blockRefHandle.empty())
            m08gFindHandle(job, blockRefHandle);
        if (blockRefHandle.empty()) {
            emitNativeError(r, "MISSING_ARG", "write.entity.attribute requires blockref_handle/handle for owning AcDbBlockReference");
            return true;
        }
        AcDbObjectId brId;
        if (!resolveHandle(pDb, blockRefHandle, brId)) {
            emitNativeError(r, "BLOCKREF_NOT_FOUND", "no block reference for handle " + blockRefHandle);
            return true;
        }
        AcDbBlockReference* pRef = nullptr;
        if (acdbOpenObject(pRef, brId, AcDb::kForWrite) != Acad::eOk || pRef == nullptr) {
            emitNativeError(r, "BLOCKREF_OPEN_FAILED", "could not open block reference for write");
            return true;
        }
        AcGePoint3d pos; m08gPoint(job, "position", 0.0, 0.0, 0.0, pos);
        std::string text, tag;
        jsonFindString(job, "text", text); if (text.empty()) text = "VALUE";
        jsonFindString(job, "tag", tag); if (tag.empty()) tag = "ARIADNE";
        AcDbAttribute* pA = new AcDbAttribute(pos, utf8ToWide(text).c_str(), utf8ToWide(tag).c_str(), pDb->textstyle());
        double height = 1.0; jsonFindNumber(job, "height", height);
        if (height > 0.0) pA->setHeight(height);
        AcDbObjectId attrId;
        const Acad::ErrorStatus es = pRef->appendAttribute(attrId, pA);
        if (es == Acad::eOk) pA->close(); else delete pA;
        pRef->close();
        int probes = 0, ms = 0; countModelSpace(pDb, ms, probes);
        r << "\"result\":{\"created\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"handle\":" << njsonStr(es == Acad::eOk ? handleOfId(attrId) : std::string())
          << ",\"owner_blockref\":" << njsonStr(blockRefHandle)
          << ",\"tag\":" << njsonStr(tag)
          << ",\"modelspace_entities_after\":" << ms << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }
    if (op == "write.entity.mline") {
        AcGePoint3dArray pts;
        if (m08gReadPointArray(job, "points", pts) < 2)
            m08gReadPointArray(job, "vertices", pts);
        if (pts.length() < 2) {
            emitNativeError(r, "MISSING_ARG", "write.entity.mline requires points/vertices array with >=2 {x,y,z}");
            return true;
        }
        // BUGFIX (w3-wbug): the original code called setStyle/setScale/appendSeg
        // without checking ErrorStatus at all, so a silently-failing appendSeg
        // still reported created=true/errorstatus=0 with a real, database-
        // resident but geometrically-empty (numVertices()==0) MLINE. LIVE-
        // DISCOVERED root cause (op_roundtrip_probe.py direct run against
        // tests/fixtures/native_sample.dwg): a freshly new()'d AcDbMline's normal
        // defaults to a zero vector, not +Z -- appendSeg needs a well-defined
        // normal to project points onto the mline's working plane and fails with
        // eInvalidNormal (291, C:\ObjectARX 2027\inc\acadstrc.h) on every call
        // until setNormal() is given a real vector; the original code never
        // called setNormal at all. Every ObjectARX call that shapes the mline is
        // now threaded through one ErrorStatus and short-circuits on the first
        // failure; setNormal/setJustification (neither ever called before) are
        // now explicit rather than relying on whatever an unset AcDbMline
        // defaults to.
        AcDbMline* pE = new AcDbMline();
        pE->setDatabaseDefaults(pDb);
        Acad::ErrorStatus es = pE->setNormal(AcGeVector3d(0.0, 0.0, 1.0));
        const AcDbObjectId styleId = pDb->cmlstyleID();
        if (es == Acad::eOk && !styleId.isNull())
            es = pE->setStyle(styleId);
        if (es == Acad::eOk)
            es = pE->setJustification(Mline::kTop);
        double scale = 1.0; jsonFindNumber(job, "scale", scale);
        if (es == Acad::eOk && scale != 0.0)
            es = pE->setScale(scale);
        for (int i = 0; es == Acad::eOk && i < pts.length(); ++i)
            es = pE->appendSeg(pts[i]);
        double closed = 0.0;
        if (es == Acad::eOk && jsonFindNumber(job, "closed", closed) && closed != 0.0)
            es = pE->setClosedMline(true);
        if (es != Acad::eOk) {
            delete pE;
            emitNativeError(r, "MLINE_BUILD_FAILED", "AcDbMline build errorstatus " + std::to_string(static_cast<int>(es)));
            return true;
        }
        // Defensive, no-fake-success check: capture the REAL vertex count while pE
        // is still ours to query (m08gAppendEntity closes -- and on failure
        // delete()s -- pE, so numVertices() must be read before that call).
        const int builtVertexCount = pE->numVertices();
        if (builtVertexCount <= 0) {
            delete pE;
            emitNativeError(r, "MLINE_EMPTY", "AcDbMline reported eOk at every build step but numVertices()==0");
            return true;
        }
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus appendEs = m08gAppendEntity(pDb, layer, pE, id, ms);
        r << "\"result\":{\"created\":" << (appendEs == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(appendEs)
          << ",\"handle\":" << njsonStr(appendEs == Acad::eOk ? handleOfId(id) : std::string())
          << ",\"vertex_count\":" << builtVertexCount
          << ",\"layer\":" << njsonStr(layer)
          << ",\"modelspace_entities_after\":" << ms << "},"
          << "\"status\":\"" << (appendEs == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }
    if (op == "write.entity.shape") {
        AcGePoint3d pos; m08gPoint(job, "position", 0.0, 0.0, 0.0, pos);
        double size = 1.0, rotation = 0.0, width = 1.0, num = 0.0;
        jsonFindNumber(job, "size", size);
        jsonFindNumber(job, "rotation", rotation);
        jsonFindNumber(job, "width_factor", width);
        jsonFindNumber(job, "shape_number", num);
        std::string name; jsonFindString(job, "name", name);
        if (name.empty()) name = "ARIADNE";
        AcDbShape* pE = new AcDbShape(pos, size, rotation, width);
        pE->setDatabaseDefaults(pDb);
        if (!pDb->textstyle().isNull())
            pE->setStyleId(pDb->textstyle());
        pE->setName(utf8ToWide(name).c_str());
        if (num > 0.0)
            pE->setShapeNumber(static_cast<Adesk::Int16>(num));
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, layer, pE, id, ms);
        r << "\"result\":{\"created\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"handle\":" << njsonStr(es == Acad::eOk ? handleOfId(id) : std::string())
          << ",\"name\":" << njsonStr(name)
          << ",\"layer\":" << njsonStr(layer)
          << ",\"modelspace_entities_after\":" << ms << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }
    if (op == "write.entity.polygonmesh") {
        // Rectangular polygon mesh from an m x n grid of vertices (one-shot ctor).
        double mD = 0.0, nD = 0.0;
        jsonFindNumber(job, "m_size", mD);
        jsonFindNumber(job, "n_size", nD);
        const int mSize = static_cast<int>(mD), nSize = static_cast<int>(nD);
        AcGePoint3dArray verts;
        const std::string key = "\"points\"";
        size_t p = job.find(key);
        if (p != std::string::npos) {
            size_t lb = job.find('[', p);
            size_t rb = (lb == std::string::npos) ? std::string::npos : job.find(']', lb);
            size_t scan = (lb == std::string::npos) ? std::string::npos : lb + 1;
            while (scan != std::string::npos && rb != std::string::npos && scan < rb) {
                size_t ob = job.find('{', scan);
                if (ob == std::string::npos || ob > rb) break;
                size_t oe = job.find('}', ob);
                if (oe == std::string::npos || oe > rb) break;
                const std::string one = job.substr(ob, oe - ob + 1);
                double x = 0.0, y = 0.0, z = 0.0;
                jsonFindNumber(one, "x", x); jsonFindNumber(one, "y", y); jsonFindNumber(one, "z", z);
                verts.append(AcGePoint3d(x, y, z));
                scan = oe + 1;
            }
        }
        if (mSize < 2 || nSize < 2 || verts.length() != mSize * nSize) {
            emitNativeError(r, "MISSING_ARG",
                "write.entity.polygonmesh requires m_size>=2,n_size>=2 and points length == m_size*n_size");
            return true;
        }
        AcDbPolygonMesh* pE = new AcDbPolygonMesh(
            AcDb::kSimpleMesh, static_cast<Adesk::Int16>(mSize), static_cast<Adesk::Int16>(nSize),
            verts, Adesk::kFalse, Adesk::kFalse);
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitCreate(r, es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.polyfacemesh") {
        AcGePoint3dArray verts;
        if (m08gReadPointArray(job, "points", verts) < 3)
            m08gReadPointArray(job, "vertices", verts);
        if (verts.length() < 3) {
            emitNativeError(r, "MISSING_ARG", "write.entity.polyfacemesh requires points/vertices array with >=3 {x,y,z}");
            return true;
        }
        if (verts.length() > 32767) {
            emitNativeError(r, "INVALID_INPUT", "polyfacemesh vertex count exceeds 32767 index limit");
            return true;
        }
        if (!layer.empty()) { bool c = false; ensureLayer(pDb, layer, 7, c); }
        AcDbBlockTable* pBT = nullptr;
        Acad::ErrorStatus es = pDb->getBlockTable(pBT, AcDb::kForRead);
        if (es != Acad::eOk) { emitNativeError(r, "DB_ERROR", "getBlockTable"); return true; }
        AcDbBlockTableRecord* pMS = nullptr;
        es = pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite);
        pBT->close();
        if (es != Acad::eOk) { emitNativeError(r, "DB_ERROR", "getAt modelspace"); return true; }
        AcDbPolyFaceMesh* pE = new AcDbPolyFaceMesh();
        if (!layer.empty()) pE->setLayer(asciiToWide(layer).c_str());
        AcDbObjectId id;
        es = pMS->appendAcDbEntity(id, pE);
        pMS->close();
        if (es != Acad::eOk) { delete pE; emitNativeError(r, "APPEND_FAILED", "appendAcDbEntity polyfacemesh"); return true; }
        Acad::ErrorStatus childEs = Acad::eOk;
        for (int i = 0; childEs == Acad::eOk && i < verts.length(); ++i) {
            AcDbPolyFaceMeshVertex* pV = new AcDbPolyFaceMeshVertex(verts[i]);
            AcDbObjectId vid;
            childEs = pE->appendVertex(vid, pV);
            if (childEs == Acad::eOk) pV->close(); else delete pV;
        }
        if (childEs == Acad::eOk) {
            const Adesk::Int16 i1 = 1, i2 = 2, i3 = 3;
            const Adesk::Int16 i4 = static_cast<Adesk::Int16>(verts.length() >= 4 ? 4 : 3);
            AcDbFaceRecord* pF = new AcDbFaceRecord(i1, i2, i3, i4);
            AcDbObjectId fid;
            childEs = pE->appendFaceRecord(fid, pF);
            if (childEs == Acad::eOk) pF->close(); else delete pF;
        }
        pE->close();
        int probes = 0, ms = 0; countModelSpace(pDb, ms, probes);
        if (childEs != Acad::eOk) {
            emitNativeError(r, "POLYFACEMESH_BUILD_FAILED", "vertex/face append es=" + std::to_string(static_cast<int>(childEs)));
            return true;
        }
        r << "\"result\":{\"created\":true"
          << ",\"handle\":" << njsonStr(handleOfId(id))
          << ",\"vertex_count\":" << verts.length()
          << ",\"face_count\":1"
          << ",\"layer\":" << njsonStr(layer)
          << ",\"modelspace_entities_after\":" << ms << "},"
          << "\"status\":\"ok\"}";
        return true;
    }
    if (op == "write.entity.region") {
        // Build region(s) from existing coplanar closed curves named by handle.
        // Reads "curves":["<hex>",...]. createFromCurves consumes COPIES we clone.
        const std::vector<std::string> handles = jsonFindStringArray(job, "curves");
        if (handles.empty()) {
            emitNativeError(r, "MISSING_ARG", "write.entity.region requires 'curves':[<handle>,...]");
            return true;
        }
        AcDbVoidPtrArray curveSegs;   // clones we own and feed to createFromCurves
        for (size_t i = 0; i < handles.size(); ++i) {
            AcDbObjectId cid;
            if (!resolveHandle(pDb, handles[i], cid)) continue;
            AcDbEntity* pSrc = nullptr;
            if (acdbOpenObject(pSrc, cid, AcDb::kForRead) != Acad::eOk) continue;
            AcDbCurve* pCurve = AcDbCurve::cast(pSrc);
            if (pCurve == nullptr) { pSrc->close(); continue; }
            AcDbEntity* pClone = AcDbEntity::cast(pCurve->clone());
            if (pClone != nullptr)
                curveSegs.append(static_cast<void*>(pClone));
            pSrc->close();
        }
        if (curveSegs.length() == 0) {
            emitNativeError(r, "INVALID_INPUT", "no resolvable curve entities in 'curves'");
            return true;
        }
        AcDbVoidPtrArray regions;
        const Acad::ErrorStatus es = AcDbRegion::createFromCurves(curveSegs, regions);
        // We own the curve clones either way -> free them.
        for (int i = 0; i < curveSegs.length(); ++i)
            delete static_cast<AcDbEntity*>(curveSegs[i]);
        if (es != Acad::eOk || regions.length() == 0) {
            for (int i = 0; i < regions.length(); ++i)
                delete static_cast<AcDbEntity*>(regions[i]);
            emitNativeError(r, "REGION_FAILED",
                "AcDbRegion::createFromCurves errorstatus " + std::to_string(static_cast<int>(es)));
            return true;
        }
        std::ostringstream handlesJson; handlesJson.precision(kJsonDoublePrecision);
        Acad::ErrorStatus appendEs = Acad::eOk;
        // wS-solids/G2 fix: pass 'layer' through so the created region(s)
        // actually land on the requested layer instead of always "0" (was
        // echoed in the reply below but silently dropped -- WaveS0 finding G2).
        const int appended = m08gAppendPieces(pDb, regions, handlesJson, appendEs, layer);
        int probes = 0, ms = 0; countModelSpace(pDb, ms, probes);
        r << "\"result\":{\"created\":" << (appended > 0 ? "true" : "false")
          << ",\"region_count\":" << appended
          << ",\"handles\":" << handlesJson.str()
          << ",\"layer\":" << njsonStr(layer)
          << ",\"modelspace_entities_after\":" << ms << "},"
          << "\"status\":\"" << (appended > 0 ? "ok" : "error") << "\"}";
        return true;
    }
    if (op == "write.entity.blockref" || op == "write.entity.minsert") {
        std::string name;
        if (!jsonFindString(job, "name", name) || name.empty()) {
            emitNativeError(r, "MISSING_ARG", op + " requires block 'name'");
            return true;
        }
        AcGePoint3d pos; m08gPoint(job, "position", 0.0, 0.0, 0.0, pos);
        // w3-insert: scale/rotation were catalogued (registry native_api lists
        // setScaleFactors/setRotation) but never actually read/applied here --
        // any caller-supplied scale/rotation silently vanished (read back as
        // the AcDbBlockReference default 1/1/1 and 0.0 regardless of the arg;
        // live-verified 2026-07-02 before this fix). "scale" is a {x,y,z}
        // point-shape arg (DWG_GRAPH_IR_SPEC's block_reference.scale X/Y/Z),
        // not m08gReadTransform's unrelated uniform-number "scale" -- read via
        // m08gPoint like every other point/vector arg, default 1,1,1.
        AcGePoint3d scalePt; m08gPoint(job, "scale", 1.0, 1.0, 1.0, scalePt);
        double rotation = 0.0; jsonFindNumber(job, "rotation", rotation);
        AcDbBlockTable* pBT = nullptr;
        Acad::ErrorStatus es = pDb->getBlockTable(pBT, AcDb::kForRead);
        if (es != Acad::eOk) { emitNativeError(r, "DB_ERROR", "getBlockTable"); return true; }
        AcDbObjectId blockId;
        es = pBT->getAt(asciiToWide(name).c_str(), blockId);
        if (es != Acad::eOk) {
            pBT->close();
            emitNativeError(r, "BLOCK_NOT_FOUND", "no block definition named '" + name + "'");
            return true;
        }
        AcDbBlockTableRecord* pMS = nullptr;
        es = pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite);
        pBT->close();
        if (es != Acad::eOk) { emitNativeError(r, "DB_ERROR", "getAt modelspace"); return true; }
        AcDbBlockReference* pRef = nullptr;
        if (op == "write.entity.minsert") {
            double colsD = 1.0, rowsD = 1.0, colSp = 1.0, rowSp = 1.0;
            jsonFindNumber(job, "columns", colsD);
            jsonFindNumber(job, "rows", rowsD);
            jsonFindNumber(job, "col_spacing", colSp);
            jsonFindNumber(job, "row_spacing", rowSp);
            if (colsD < 1) colsD = 1; if (rowsD < 1) rowsD = 1;
            pRef = new AcDbMInsertBlock(pos, blockId,
                static_cast<Adesk::UInt16>(colsD), static_cast<Adesk::UInt16>(rowsD), colSp, rowSp);
        } else {
            pRef = new AcDbBlockReference(pos, blockId);
        }
        // Applies to both branches (AcDbMInsertBlock derives from
        // AcDbBlockReference, same setters) -- fire-and-forget, matching
        // setLayer below (no ErrorStatus check anywhere in this handler).
        pRef->setScaleFactors(AcGeScale3d(scalePt.x, scalePt.y, scalePt.z));
        pRef->setRotation(rotation);
        if (!layer.empty()) {
            bool c = false; ensureLayer(pDb, layer, 7, c);
            pRef->setLayer(asciiToWide(layer).c_str());
        }
        AcDbObjectId id;
        es = pMS->appendAcDbEntity(id, pRef);
        pMS->close();
        // p3-insattr: optional "attributes":[{tag,value,position?,height?}] --
        // only meaningful once the block reference is database-resident
        // (appendAttribute's contract; mirrors the existing write.entity.
        // attribute handler above, which requires an ALREADY-resident blockref
        // resolved by handle). Real ObjectARX INSERT+ATTRIB pattern: for each
        // requested tag, find the matching AcDbAttributeDefinition owned by the
        // referenced block definition and instantiate a bound AcDbAttribute via
        // setAttributeFromBlock (copies position/height/rotation/style/flags,
        // transformed through this block reference's own blockTransform()),
        // then overwrite the value with the caller's text UNLESS the ATTDEF is
        // constant (real AutoCAD INSERT behavior: a constant attribute's value
        // is fixed by its ATTDEF and cannot be overridden per-instance). A tag
        // with no matching ATTDEF is silently skipped (not an error -- the
        // blockref itself already succeeded); attributes_created in the result
        // envelope below is the honest count, so a caller can tell a typo'd tag
        // from a real failure without this op ever claiming a fake success.
        int attributesCreated = 0;
        if (es == Acad::eOk) {
            const std::string attrsKey = "\"attributes\"";
            const size_t ap = job.find(attrsKey);
            if (ap != std::string::npos) {
                const size_t lb = job.find('[', ap);
                const size_t rb = (lb == std::string::npos) ? std::string::npos : job.find(']', lb);
                if (lb != std::string::npos && rb != std::string::npos) {
                    AcDbBlockTableRecord* pDef = nullptr;
                    if (acdbOpenObject(pDef, blockId, AcDb::kForRead) == Acad::eOk) {
                        size_t scan = lb + 1;
                        while (scan != std::string::npos && scan < rb) {
                            const size_t ob = job.find('{', scan);
                            if (ob == std::string::npos || ob > rb) break;
                            const size_t oe = job.find('}', ob);
                            if (oe == std::string::npos || oe > rb) break;
                            const std::string one = job.substr(ob, oe - ob + 1);
                            std::string reqTag, reqValue;
                            jsonFindString(one, "tag", reqTag);
                            jsonFindString(one, "value", reqValue);
                            if (!reqTag.empty()) {
                                AcDbBlockTableRecordIterator* pDIt = nullptr;
                                if (pDef->newIterator(pDIt) == Acad::eOk) {
                                    for (pDIt->start(); !pDIt->done(); pDIt->step()) {
                                        AcDbEntity* pDefEnt = nullptr;
                                        if (pDIt->getEntity(pDefEnt, AcDb::kForRead) != Acad::eOk)
                                            continue;
                                        AcDbAttributeDefinition* pAttDef =
                                            AcDbAttributeDefinition::cast(pDefEnt);
                                        if (pAttDef != nullptr &&
                                            acharToAscii(pAttDef->tagConst()) == reqTag) {
                                            AcDbAttribute* pA = new AcDbAttribute();
                                            pA->setAttributeFromBlock(pAttDef, pRef->blockTransform());
                                            std::string posObj;
                                            if (jsonFindObject(one, "position", posObj)) {
                                                AcGePoint3d ov; m08gPoint(one, "position", 0.0, 0.0, 0.0, ov);
                                                pA->setPosition(ov);
                                            }
                                            double ovh = 0.0;
                                            if (jsonFindNumber(one, "height", ovh) && ovh > 0.0)
                                                pA->setHeight(ovh);
                                            if (!pAttDef->isConstant())
                                                pA->setTextString(utf8ToWide(reqValue).c_str());
                                            AcDbObjectId attrId;
                                            const Acad::ErrorStatus aes = pRef->appendAttribute(attrId, pA);
                                            if (aes == Acad::eOk) { pA->close(); ++attributesCreated; }
                                            else delete pA;
                                        }
                                        pDefEnt->close();
                                    }
                                    delete pDIt;
                                }
                            }
                            scan = oe + 1;
                        }
                        pDef->close();
                    }
                }
            }
        }
        if (es == Acad::eOk) pRef->close(); else delete pRef;
        int probes = 0, ms = 0; countModelSpace(pDb, ms, probes);
        r << "\"result\":{\"created\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"handle\":" << njsonStr(es == Acad::eOk ? handleOfId(id) : std::string())
          << ",\"block\":" << njsonStr(name)
          << ",\"layer\":" << njsonStr(layer)
          << ",\"attributes_created\":" << attributesCreated
          << ",\"modelspace_entities_after\":" << ms << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }
    if (op == "write.entity.tolerance") {
        AcGePoint3d loc; m08gPoint(job, "location", 0.0, 0.0, 0.0, loc);
        AcGeVector3d normal; m08gVector(job, "normal", 0.0, 0.0, 1.0, normal);
        AcGeVector3d dir; m08gVector(job, "direction", 1.0, 0.0, 0.0, dir);
        std::string text; jsonFindString(job, "text", text);
        if (text.empty()) text = "%%v";   // a minimal valid FCF frame
        AcDbFcf* pE = new AcDbFcf(utf8ToWide(text).c_str(), loc, normal, dir);
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitCreate(r, es, id, layer, ms);
        return true;
    }

    if (op == "write.entity.body") {
        AcDbBody* pE = new AcDbBody();
        pE->setDatabaseDefaults(pDb);
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitModelerCreate(r, "AcDbBody", es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.solid3d.primitive") {
        std::string primitive; jsonFindString(job, "primitive", primitive);
        if (primitive.empty()) primitive = "box";
        double x = 1.0, y = 1.0, z = 1.0, radius = 0.5, height = 1.0, top = 0.0, minor = 0.2;
        jsonFindNumber(job, "x", x); jsonFindNumber(job, "x_len", x);
        jsonFindNumber(job, "y", y); jsonFindNumber(job, "y_len", y);
        jsonFindNumber(job, "z", z); jsonFindNumber(job, "z_len", z);
        jsonFindNumber(job, "radius", radius); jsonFindNumber(job, "height", height);
        jsonFindNumber(job, "top_radius", top); jsonFindNumber(job, "minor_radius", minor);
        AcDb3dSolid* pE = new AcDb3dSolid();
        pE->setDatabaseDefaults(pDb);
        Acad::ErrorStatus es = Acad::eOk;
        if (primitive == "sphere") es = pE->createSphere(radius);
        else if (primitive == "torus") es = pE->createTorus(radius, minor);
        else if (primitive == "wedge") es = pE->createWedge(x, y, z);
        else if (primitive == "pyramid") es = pE->createPyramid(height, 4, radius, top);
        else if (primitive == "frustum") es = pE->createFrustum(height, radius, radius, top);
        else es = pE->createBox(x, y, z);
        if (es != Acad::eOk) { delete pE; emitNativeError(r, "MODELER_CREATE_FAILED", "AcDb3dSolid primitive errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        AcDbObjectId id; int ms = 0;
        es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitModelerCreate(r, "AcDb3dSolid", es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.solid3d.extrude") {
        double w = 1.0, h = 1.0, height = 1.0;
        jsonFindNumber(job, "width", w); jsonFindNumber(job, "depth", h); jsonFindNumber(job, "height", height);
        AcDbPolyline* pProfile = m08gMakeRectProfile(w, h);
        AcDbSweepOptions opts;
        AcDb3dSolid* pE = new AcDb3dSolid();
        pE->setDatabaseDefaults(pDb);
        Acad::ErrorStatus es = pE->createExtrudedSolid(pProfile, AcGeVector3d(0.0, 0.0, height), opts);
        delete pProfile;
        if (es != Acad::eOk) { delete pE; emitNativeError(r, "EXTRUDE_FAILED", "createExtrudedSolid errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        AcDbObjectId id; int ms = 0; es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitModelerCreate(r, "AcDb3dSolid", es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.solid3d.revolve") {
        double w = 0.5, h = 1.0, angle = 6.28318530717958647692;
        jsonFindNumber(job, "width", w); jsonFindNumber(job, "height", h); jsonFindNumber(job, "angle", angle);
        AcDbPolyline* pProfile = m08gMakeRectProfile(w, h);
        AcDbRevolveOptions opts;
        AcDb3dSolid* pE = new AcDb3dSolid();
        pE->setDatabaseDefaults(pDb);
        Acad::ErrorStatus es = pE->createRevolvedSolid(pProfile, AcGePoint3d(0.0, 0.0, 0.0), AcGeVector3d(0.0, 1.0, 0.0), angle, 0.0, opts);
        delete pProfile;
        if (es != Acad::eOk) { delete pE; emitNativeError(r, "REVOLVE_FAILED", "createRevolvedSolid errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        AcDbObjectId id; int ms = 0; es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitModelerCreate(r, "AcDb3dSolid", es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.solid3d.sweep") {
        double w = 0.2, h = 0.2, length = 2.0;
        jsonFindNumber(job, "width", w); jsonFindNumber(job, "height", h); jsonFindNumber(job, "length", length);
        AcDbPolyline* pProfile = m08gMakeRectProfile(w, h);
        AcDbLine* pPath = new AcDbLine(AcGePoint3d(0.0, 0.0, 0.0), AcGePoint3d(0.0, 0.0, length));
        AcDbSweepOptions opts;
        AcDb3dSolid* pE = new AcDb3dSolid();
        pE->setDatabaseDefaults(pDb);
        Acad::ErrorStatus es = pE->createSweptSolid(pProfile, pPath, opts);
        delete pProfile; delete pPath;
        if (es != Acad::eOk) { delete pE; emitNativeError(r, "SWEEP_FAILED", "createSweptSolid errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        AcDbObjectId id; int ms = 0; es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitModelerCreate(r, "AcDb3dSolid", es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.solid3d.loft") {
        double w1 = 1.0, h1 = 1.0, w2 = 0.5, h2 = 0.5, dz = 1.0;
        jsonFindNumber(job, "width", w1); jsonFindNumber(job, "depth", h1); jsonFindNumber(job, "top_width", w2); jsonFindNumber(job, "top_depth", h2); jsonFindNumber(job, "height", dz);
        AcDbPolyline* p1 = m08gMakeRectProfile(w1, h1);
        AcDbPolyline* p2 = m08gMakeRectProfile(w2, h2);
        AcGeMatrix3d tr; tr.setToTranslation(AcGeVector3d(0.0, 0.0, dz));
        p2->transformBy(tr);
        AcArray<AcDbEntity*> sections; sections.append(p1); sections.append(p2);
        AcArray<AcDbEntity*> guides;
        AcDbLoftOptions opts;
        AcDb3dSolid* pE = new AcDb3dSolid();
        pE->setDatabaseDefaults(pDb);
        Acad::ErrorStatus es = pE->createLoftedSolid(sections, guides, nullptr, opts);
        delete p1; delete p2;
        if (es != Acad::eOk) { delete pE; emitNativeError(r, "LOFT_FAILED", "createLoftedSolid errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        AcDbObjectId id; int ms = 0; es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitModelerCreate(r, "AcDb3dSolid", es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.surface") {
        double w = 1.0, h = 1.0; jsonFindNumber(job, "width", w); jsonFindNumber(job, "height", h);
        AcDbPolyline* pProfile = m08gMakeRectProfile(w, h);
        AcDbSurface* pSurf = nullptr;
        Acad::ErrorStatus es = AcDbSurface::createFrom(pProfile, pSurf);
        delete pProfile;
        if (es != Acad::eOk || pSurf == nullptr) { delete pSurf; emitNativeError(r, "SURFACE_CREATE_FAILED", "AcDbSurface::createFrom errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        AcDbObjectId id; int ms = 0; es = m08gAppendEntity(pDb, layer, pSurf, id, ms);
        m08gEmitModelerCreate(r, "AcDbSurface", es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.nurbsurface") {
        // wS-solids/S6 fix (closes WaveS0 finding G4): read real width/height
        // job args instead of the previous hardcoded 1x1 unit patch, which
        // produced the IDENTICAL bounds/area on every call regardless of what
        // was requested. Degree-1, non-rational, 2x2 control grid is an exact
        // planar bilinear patch, so surface_area == width*height exactly --
        // the same closed-form-cert shape every other S-wave op gets.
        double w = 1.0, h = 1.0;
        jsonFindNumber(job, "width", w); jsonFindNumber(job, "height", h);
        if (w <= 0.0) w = 1.0;
        if (h <= 0.0) h = 1.0;
        AcGePoint3dArray cps;
        cps.append(AcGePoint3d(0.0, 0.0, 0.0)); cps.append(AcGePoint3d(w, 0.0, 0.0));
        cps.append(AcGePoint3d(0.0, h, 0.0)); cps.append(AcGePoint3d(w, h, 0.0));
        AcGeDoubleArray weights; weights.append(1.0); weights.append(1.0); weights.append(1.0); weights.append(1.0);
        AcGeKnotVector uKnots; uKnots.append(0.0); uKnots.append(0.0); uKnots.append(1.0); uKnots.append(1.0);
        AcGeKnotVector vKnots; vKnots.append(0.0); vKnots.append(0.0); vKnots.append(1.0); vKnots.append(1.0);
        AcDbNurbSurface* pE = new AcDbNurbSurface();
        pE->setDatabaseDefaults(pDb);
        Acad::ErrorStatus es = pE->set(1, 1, false, 2, 2, cps, weights, uKnots, vKnots);
        if (es != Acad::eOk) { delete pE; emitNativeError(r, "NURBSURFACE_SET_FAILED", "AcDbNurbSurface::set errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        AcDbObjectId id; int ms = 0; es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitModelerCreate(r, "AcDbNurbSurface", es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.subdmesh") {
        double x = 1.0, y = 1.0, z = 1.0; jsonFindNumber(job, "x_len", x); jsonFindNumber(job, "y_len", y); jsonFindNumber(job, "z_len", z);
        AcDbSubDMesh* pE = new AcDbSubDMesh();
        pE->setDatabaseDefaults(pDb);
        Acad::ErrorStatus es = pE->setBox(x, y, z, 1, 1, 1, 0);
        if (es != Acad::eOk) { delete pE; emitNativeError(r, "SUBDMESH_SET_FAILED", "AcDbSubDMesh::setBox errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        AcDbObjectId id; int ms = 0; es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitModelerCreate(r, "AcDbSubDMesh", es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.mpolygon") {
        // wA-cert: force-load the MPolygon boundary/loop-management engine
        // (AcMPolygonObj26.dbx) BEFORE any AcDbMPolygon use -- see
        // m08gLoadEngineModule's doc comment above.
        const bool mpolyEngineLoaded = m08gLoadEngineModule(L"AcMPolygonObj26.dbx");
        AcGePoint2dArray verts;
        if (!m08gRead2dVertices(job, verts)) {
            verts.append(AcGePoint2d(0.0, 0.0)); verts.append(AcGePoint2d(1.0, 0.0)); verts.append(AcGePoint2d(1.0, 1.0)); verts.append(AcGePoint2d(0.0, 1.0));
        }
        AcGeDoubleArray bulges; for (int i = 0; i < verts.length(); ++i) bulges.append(0.0);
        // BUGFIX (a0-engineprep): the original code built the WHOLE mpolygon
        // (setPattern/appendMPolygonLoop/evaluateHatch/balanceDisplay) on a
        // bare, ownerless new()'d AcDbMPolygon* and only appended it to model
        // space (m08gAppendEntity) at the very end -- appendMPolygonLoop
        // live-probed to eNoClassId (409, C:\ObjectARX 2027\inc\acadstrc.h):
        // AcDbMPolygon's boundary/loop-management engine (AcMPolygonObj)
        // needs the entity to already be database-resident before it can
        // register loop geometry against it. AcDb3dPolyline and
        // AcDbPolyFaceMesh (this same file, above) already establish the
        // correct convention for this class of entity -- append the empty
        // shell FIRST, THEN populate it -- mirrored here verbatim.
        if (!layer.empty()) { bool c = false; ensureLayer(pDb, layer, 7, c); }
        AcDbBlockTable* pBT = nullptr;
        Acad::ErrorStatus es = pDb->getBlockTable(pBT, AcDb::kForRead);
        if (es != Acad::eOk) { emitNativeError(r, "DB_ERROR", "getBlockTable"); return true; }
        AcDbBlockTableRecord* pMS = nullptr;
        es = pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite);
        pBT->close();
        if (es != Acad::eOk) { emitNativeError(r, "DB_ERROR", "getAt modelspace"); return true; }
        AcDbMPolygon* pE = new AcDbMPolygon();
        pE->setDatabaseDefaults(pDb);
        if (!layer.empty()) pE->setLayer(asciiToWide(layer).c_str());
        AcDbObjectId id;
        es = pMS->appendAcDbEntity(id, pE);
        pMS->close();
        if (es != Acad::eOk) { delete pE; emitNativeError(r, "APPEND_FAILED", "appendAcDbEntity mpolygon errorstatus " + std::to_string(static_cast<int>(es)) + " engine_module_loaded=" + (mpolyEngineLoaded ? "true" : "false")); return true; }
        es = pE->setNormal(AcGeVector3d(0.0, 0.0, 1.0));
        if (es == Acad::eOk) es = pE->setElevation(0.0);
        if (es == Acad::eOk) es = pE->setPattern(AcDbHatch::kPreDefined, L"SOLID");
        if (es == Acad::eOk) es = pE->appendMPolygonLoop(verts, bulges, true);
        if (es == Acad::eOk) es = pE->evaluateHatch();
        if (es == Acad::eOk) es = pE->balanceDisplay();
        pE->close();
        int probes = 0, ms = 0; countModelSpace(pDb, ms, probes);
        if (es != Acad::eOk) { emitNativeError(r, "MPOLYGON_BUILD_FAILED", "AcDbMPolygon build errorstatus " + std::to_string(static_cast<int>(es)) + " engine_module_loaded=" + (mpolyEngineLoaded ? "true" : "false")); return true; }
        m08gEmitModelerCreate(r, "AcDbMPolygon", Acad::eOk, id, layer, ms);
        return true;
    }
    if (op == "write.entity.rasterimage") {
        // wA-cert: force-load the ISM/raster engine (acismobj26.dbx) BEFORE any
        // AcDbRasterImageDef/AcDbRasterImage use -- see m08gLoadEngineModule's
        // doc comment above.
        const bool ismEngineLoaded = m08gLoadEngineModule(L"acismobj26.dbx");
        std::string imagePath; if (!jsonFindString(job, "image_path", imagePath) || imagePath.empty()) { emitNativeError(r, "MISSING_ARG", "write.entity.rasterimage requires image_path"); return true; }
        AcDbObjectId dictId = AcDbRasterImageDef::imageDictionary(pDb);
        Acad::ErrorStatus es = Acad::eOk;
        if (dictId.isNull()) es = AcDbRasterImageDef::createImageDictionary(pDb, dictId);
        if (es != Acad::eOk || dictId.isNull()) { emitNativeError(r, "IMAGE_DICT_FAILED", "image dictionary errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        AcDbDictionary* pDict = nullptr;
        if (acdbOpenObject(pDict, dictId, AcDb::kForWrite) != Acad::eOk || pDict == nullptr) { emitNativeError(r, "IMAGE_DICT_OPEN_FAILED", "could not open image dictionary"); return true; }
        AcDbRasterImageDef* pDef = new AcDbRasterImageDef();
        pDef->setSourceFileName(utf8ToWide(imagePath).c_str());
        pDef->setActiveFileName(utf8ToWide(imagePath).c_str());
        std::string name = "ARIADNE_IMAGE";
        jsonFindString(job, "name", name);
        AcDbObjectId defId;
        es = pDict->setAt(utf8ToWide(name).c_str(), pDef, defId);
        pDict->close();
        if (es == Acad::eOk) pDef->close(); else { delete pDef; emitNativeError(r, "IMAGE_DEF_FAILED", "image def setAt errorstatus " + std::to_string(static_cast<int>(es)) + " engine_module_loaded=" + (ismEngineLoaded ? "true" : "false")); return true; }
        AcGePoint3d origin; m08gPoint(job, "position", 0.0, 0.0, 0.0, origin);
        double w = 1.0, h = 1.0; jsonFindNumber(job, "width", w); jsonFindNumber(job, "height", h);
        AcDbRasterImage* pE = new AcDbRasterImage();
        pE->setDatabaseDefaults(pDb);
        pE->setImageDefId(defId);
        pE->setOrientation(origin, AcGeVector3d(w, 0.0, 0.0), AcGeVector3d(0.0, h, 0.0));
        AcGeVector2d sz(w, h); pE->setClipBoundaryToWholeImage(sz);
        AcDbObjectId id; int ms = 0; es = m08gAppendEntity(pDb, layer, pE, id, ms);
        m08gEmitModelerCreate(r, "AcDbRasterImage", es, id, layer, ms);
        return true;
    }
    if (op == "write.entity.wipeout") {
        // wA-cert: force-load the ISM/raster engine (acismobj26.dbx) BEFORE any
        // AcDbRasterImageDef/AcDbWipeout use -- see m08gLoadEngineModule's doc
        // comment above (AcDbWipeout IS-A AcDbRasterImage, same engine as
        // write.entity.rasterimage above).
        const bool ismEngineLoaded = m08gLoadEngineModule(L"acismobj26.dbx");
        AcGePoint2dArray verts;
        if (!m08gRead2dVertices(job, verts)) { verts.append(AcGePoint2d(0.0, 0.0)); verts.append(AcGePoint2d(1.0, 0.0)); verts.append(AcGePoint2d(1.0, 1.0)); verts.append(AcGePoint2d(0.0, 1.0)); }
        // BUGFIX (a0-engineprep): the original code called the static, no-arg
        // AcDbWipeout::createImageDefinition() and then NEVER retrieved or
        // attached any image-definition id at all -- setImageDefId() was never
        // called. AcDbWipeout IS-A AcDbRasterImage (dbwipe.h) and, like every
        // other raster-image entity, is invalid until wired to a database-
        // resident AcDbRasterImageDef via setImageDefId() (see the working
        // write.entity.rasterimage branch above, which this now mirrors).
        // A wipeout has no real backing file, so a placeholder def is minted in
        // ctx.pDb's own ACAD_IMAGE_DICT the same way rasterimage does
        // (AcDbRasterImageDef::imageDictionary/createImageDictionary +
        // AcDbDictionary::setAt) instead of depending on the legacy
        // createImageDefinition() static helper, which live-probed to
        // eKeyNotFound (22) against this handler's staged db.
        AcDbObjectId dictId = AcDbRasterImageDef::imageDictionary(pDb);
        Acad::ErrorStatus es = Acad::eOk;
        if (dictId.isNull()) es = AcDbRasterImageDef::createImageDictionary(pDb, dictId);
        if (es != Acad::eOk || dictId.isNull()) { emitNativeError(r, "WIPEOUT_DICT_FAILED", "image dictionary errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        AcDbDictionary* pDict = nullptr;
        if (acdbOpenObject(pDict, dictId, AcDb::kForWrite) != Acad::eOk || pDict == nullptr) { emitNativeError(r, "WIPEOUT_DICT_OPEN_FAILED", "could not open image dictionary"); return true; }
        AcDbRasterImageDef* pDef = new AcDbRasterImageDef();
        std::string defName = "ARIADNE_WIPEOUT_IMAGEDEF";
        jsonFindString(job, "name", defName);
        AcDbObjectId defId;
        es = pDict->setAt(utf8ToWide(defName).c_str(), pDef, defId);
        pDict->close();
        if (es == Acad::eOk) pDef->close(); else { delete pDef; emitNativeError(r, "WIPEOUT_DEF_FAILED", "image def setAt errorstatus " + std::to_string(static_cast<int>(es)) + " engine_module_loaded=" + (ismEngineLoaded ? "true" : "false")); return true; }

        // wA-cert BUGFIX v2: setClipBoundary(kPoly, verts) live-probed to
        // Acad::eInvalidInput(3). First hypothesis (residency -- append the
        // empty shell via the generic AcDbBlockTableRecord::appendAcDbEntity
        // FIRST, mirroring the 3dpolyline/polyfacemesh/mpolygon convention in
        // this file) reproduced the IDENTICAL error -- ruled out. dbwipe.h
        // reveals AcDbWipeout provides its OWN dedicated
        // `Acad::ErrorStatus append(AcDbObjectId&)` member -- unusual for a
        // plain AcDbEntity subclass (most rely solely on the generic
        // AcDbBlockTableRecord append path), strongly suggesting the generic
        // append is not this class's intended construction protocol. Reverted
        // to configure-then-append (matching Autodesk's documented Wipeout
        // creation pattern) but using the class's own append() instead of
        // m08gAppendEntity/appendAcDbEntity.
        if (!layer.empty()) { bool c = false; ensureLayer(pDb, layer, 7, c); }
        AcDbWipeout* pE = new AcDbWipeout();
        pE->setDatabaseDefaults(pDb);
        if (!layer.empty()) pE->setLayer(asciiToWide(layer).c_str());
        es = pE->setImageDefId(defId);
        if (es != Acad::eOk) { delete pE; emitNativeError(r, "WIPEOUT_IMAGEDEFID_FAILED", "setImageDefId errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        pE->setOrientation(AcGePoint3d(0.0, 0.0, 0.0), AcGeVector3d(1.0, 0.0, 0.0), AcGeVector3d(0.0, 1.0, 0.0));
        // wA-cert diagnostic split: setClipBoundary and append() previously
        // shared one error code/status variable, making it impossible to tell
        // from the JSON error alone which call actually failed when both
        // return the SAME numeric ErrorStatus by coincidence. Kept as two
        // distinct checks with distinct error codes.
        es = pE->setClipBoundary(AcDbRasterImage::kPoly, verts);
        if (es != Acad::eOk) { delete pE; emitNativeError(r, "WIPEOUT_CLIP_FAILED", "setClipBoundary errorstatus " + std::to_string(static_cast<int>(es)) + " engine_module_loaded=" + (ismEngineLoaded ? "true" : "false")); return true; }
        AcDbObjectId id;
        es = pE->append(id);
        if (es != Acad::eOk) { delete pE; emitNativeError(r, "WIPEOUT_APPEND_FAILED", "wipeout append() errorstatus " + std::to_string(static_cast<int>(es))); return true; }
        pE->close();
        int probes = 0, ms = 0; countModelSpace(pDb, ms, probes);
        m08gEmitModelerCreate(r, "AcDbWipeout", Acad::eOk, id, layer, ms);
        return true;
    }

    //========================================================================
    // modify / geometry-edit
    //========================================================================
    if (op == "modify.entity.transform") {
        std::string handle;
        if (!m08gFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "modify.entity.transform requires 'handle'");
            return true;
        }
        AcDbEntity* pEnt = m08gOpenEntityForWrite(pDb, handle);
        if (pEnt == nullptr) { emitNativeError(r, "ENTITY_NOT_FOUND", "no writable entity for handle " + handle); return true; }
        const AcGeMatrix3d xform = m08gReadTransform(job);
        const Acad::ErrorStatus es = pEnt->transformBy(xform);
        pEnt->close();
        r << "\"result\":{\"transformed\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"handle\":" << njsonStr(handle) << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }
    if (op == "modify.entity.copy_transformed") {
        std::string handle;
        if (!m08gFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "modify.entity.copy_transformed requires 'handle'");
            return true;
        }
        AcDbObjectId srcId;
        if (!resolveHandle(pDb, handle, srcId)) { emitNativeError(r, "ENTITY_NOT_FOUND", "no entity for handle " + handle); return true; }
        AcDbEntity* pSrc = nullptr;
        if (acdbOpenObject(pSrc, srcId, AcDb::kForRead) != Acad::eOk) { emitNativeError(r, "ENTITY_NOT_FOUND", "open failed " + handle); return true; }
        const AcGeMatrix3d xform = m08gReadTransform(job);
        AcDbEntity* pCopy = nullptr;
        const Acad::ErrorStatus tcEs = pSrc->getTransformedCopy(xform, pCopy);
        pSrc->close();
        if (tcEs != Acad::eOk || pCopy == nullptr) { emitNativeError(r, "COPY_FAILED", "getTransformedCopy errorstatus " + std::to_string(static_cast<int>(tcEs))); return true; }
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, std::string(), pCopy, id, ms);
        r << "\"result\":{\"created\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"source\":" << njsonStr(handle)
          << ",\"handle\":" << njsonStr(es == Acad::eOk ? handleOfId(id) : std::string())
          << ",\"modelspace_entities_after\":" << ms << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }
    if (op == "modify.entity.common") {
        std::string handle;
        if (!m08gFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "modify.entity.common requires 'handle'");
            return true;
        }
        AcDbEntity* pEnt = m08gOpenEntityForWrite(pDb, handle);
        if (pEnt == nullptr) { emitNativeError(r, "ENTITY_NOT_FOUND", "no writable entity for handle " + handle); return true; }
        std::string setLayer, setLinetype;
        bool didLayer = false, didColor = false, didLinetype = false;
        if (jsonFindString(job, "set_layer", setLayer) && !setLayer.empty()) {
            bool c = false; ensureLayer(pDb, setLayer, 7, c);
            didLayer = (pEnt->setLayer(asciiToWide(setLayer).c_str()) == Acad::eOk);
        }
        { double ci = 0.0; if (jsonFindNumber(job, "set_color_index", ci)) {
            didColor = (pEnt->setColorIndex(static_cast<Adesk::UInt16>(static_cast<int>(ci))) == Acad::eOk); } }
        if (jsonFindString(job, "set_linetype", setLinetype) && !setLinetype.empty()) {
            didLinetype = (pEnt->setLinetype(asciiToWide(setLinetype).c_str()) == Acad::eOk);
        }
        pEnt->close();
        r << "\"result\":{\"modified\":true"
          << ",\"layer_set\":" << (didLayer ? "true" : "false")
          << ",\"color_set\":" << (didColor ? "true" : "false")
          << ",\"linetype_set\":" << (didLinetype ? "true" : "false")
          << ",\"handle\":" << njsonStr(handle) << "},"
          << "\"status\":\"ok\"}";
        return true;
    }
    if (op == "modify.entity.xdata") {
        // P10: entity-handle-targeted xdata write. Distinct code path from the
        // DATABASE-level write.xdata.set/inspect.xdata.get (Ariadne's own NOD
        // dictionary, single app+value string via setDatabaseXdata/
        // getDatabaseXdata) -- those and the set_entity_xdata patch op that
        // aliases to write.entity.set_xdata are untouched by this ticket. This
        // op sets a full multi-item xdata block on an arbitrary resolved
        // entity via AcDbEntity::setXData, the write-side counterpart of the
        // xData()/xdataBlocksJson() read already used by collectModelSpaceGraph.
        std::string handle;
        if (!m08gFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "modify.entity.xdata requires 'handle'");
            return true;
        }
        std::string appName;
        if (!jsonFindString(job, "app_name", appName) || appName.empty()) {
            emitNativeError(r, "MISSING_ARG", "modify.entity.xdata requires 'app_name'");
            return true;
        }
        size_t lb = 0, rb = 0;
        if (!m08gFindArraySpan(job, "values", lb, rb)) {
            emitNativeError(r, "MISSING_ARG", "modify.entity.xdata requires a 'values' array");
            return true;
        }

        // Pass 1: parse + validate every item BEFORE touching the entity --
        // atomic all-or-nothing (fail-loud, no partial/silent-drop writes).
        // Accepted codes are the DXF 1000-1071 xdata range only (the generic
        // resbufCodeIs* families also match non-xdata codes below 1000, which
        // are not valid xdata group codes at all). 1001 (appname) is
        // synthesized by this handler, never caller-supplied; 1002 (control
        // string) and 1004 (binary chunk) are excluded -- see build_log.md.
        struct XdItem { short code; std::string str; double num; double pt[3]; };
        std::vector<XdItem> items;
        size_t scan = lb + 1;
        int index = 0;
        std::string badReason;
        while (scan < rb) {
            size_t ob = job.find('{', scan);
            if (ob == std::string::npos || ob > rb) break;
            size_t oe = job.find('}', ob);
            if (oe == std::string::npos || oe > rb) break;
            const std::string one = job.substr(ob, oe - ob + 1);
            double codeD = 0.0;
            if (!jsonFindNumber(one, "code", codeD)) {
                badReason = "values[" + std::to_string(index) + "] missing 'code'";
                break;
            }
            XdItem item;
            item.code = static_cast<short>(codeD);
            item.num = 0.0; item.pt[0] = item.pt[1] = item.pt[2] = 0.0;
            const short code = item.code;
            if (code == 1000 || code == 1003 || code == 1005) {
                if (!jsonFindString(one, "value", item.str)) {
                    badReason = "values[" + std::to_string(index) + "] code "
                        + std::to_string(code) + " requires a string 'value'";
                    break;
                }
            } else if (code == 1040 || code == 1041 || code == 1042 ||
                       code == 1070 || code == 1071) {
                if (!jsonFindNumber(one, "value", item.num)) {
                    badReason = "values[" + std::to_string(index) + "] code "
                        + std::to_string(code) + " requires a numeric 'value'";
                    break;
                }
            } else if (code == 1010 || code == 1011 || code == 1012 || code == 1013) {
                if (!m08gReadValueTriple(one, item.pt)) {
                    badReason = "values[" + std::to_string(index) + "] code "
                        + std::to_string(code) + " requires a 3-number 'value' array";
                    break;
                }
            } else {
                badReason = "values[" + std::to_string(index)
                    + "] unsupported or reserved xdata group code " + std::to_string(code);
                break;
            }
            items.push_back(item);
            scan = oe + 1;
            ++index;
        }

        if (!badReason.empty()) {
            emitNativeError(r, "MALFORMED_XDATA_CODE", badReason);
            return true;
        }
        if (items.empty()) {
            emitNativeError(r, "MISSING_ARG", "modify.entity.xdata requires at least one item in 'values'");
            return true;
        }

        AcDbEntity* pEnt = m08gOpenEntityForWrite(pDb, handle);
        if (pEnt == nullptr) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "no writable entity for handle " + handle);
            return true;
        }

        const Acad::ErrorStatus regEs = ensureRegApp(pDb, appName);
        if (regEs != Acad::eOk) {
            pEnt->close();
            emitNativeError(r, "REGAPP_FAILED",
                            "ensureRegApp errorstatus " + std::to_string(static_cast<int>(regEs)));
            return true;
        }

        // Build the resbuf chain: 1001(app) then each item, via repeated
        // single-pair acutBuildList calls manually linked (acutBuildList's
        // fixed variadic shape can't take a runtime-variable item count in one
        // call; setDatabaseXdata's 2-pair call above is the fixed-shape
        // sibling this reuses the same primitive as). acutBuildList deep-
        // copies its string/point payload, so the local wstrings/ads_point
        // below only need to outlive their own call.
        const std::wstring appW = asciiToWide(appName);
        resbuf* head = acutBuildList(AcDb::kDxfRegAppName, appW.c_str(), 0);
        resbuf* tail = head;
        bool buildFailed = (head == nullptr);
        for (size_t i = 0; i < items.size() && !buildFailed; ++i) {
            const XdItem& it = items[i];
            resbuf* node = nullptr;
            if (it.code == 1000 || it.code == 1003 || it.code == 1005) {
                const std::wstring w = asciiToWide(it.str);
                node = acutBuildList(it.code, w.c_str(), 0);
            } else if (it.code == 1070) {
                node = acutBuildList(it.code, static_cast<int>(it.num), 0);
            } else if (it.code == 1071) {
                node = acutBuildList(it.code, static_cast<long>(it.num), 0);
            } else if (it.code == 1040 || it.code == 1041 || it.code == 1042) {
                node = acutBuildList(it.code, it.num, 0);
            } else {
                ads_point pt = { it.pt[0], it.pt[1], it.pt[2] };
                node = acutBuildList(it.code, pt, 0);
            }
            if (node == nullptr) { buildFailed = true; break; }
            tail->rbnext = node;
            tail = node;
        }

        if (buildFailed) {
            if (head != nullptr) acutRelRb(head);
            pEnt->close();
            emitNativeError(r, "OUT_OF_MEMORY", "failed building the xdata resbuf chain");
            return true;
        }

        const Acad::ErrorStatus es = pEnt->setXData(head);
        acutRelRb(head);
        pEnt->close();

        r << "\"result\":{\"set\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"handle\":" << njsonStr(handle)
          << ",\"app_name\":" << njsonStr(appName)
          << ",\"item_count\":" << items.size() << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }
    if (op == "modify.entity.explode") {
        std::string handle;
        if (!m08gFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "modify.entity.explode requires 'handle'");
            return true;
        }
        AcDbObjectId srcId;
        if (!resolveHandle(pDb, handle, srcId)) { emitNativeError(r, "ENTITY_NOT_FOUND", "no entity for handle " + handle); return true; }
        AcDbEntity* pSrc = nullptr;
        if (acdbOpenObject(pSrc, srcId, AcDb::kForRead) != Acad::eOk) { emitNativeError(r, "ENTITY_NOT_FOUND", "open failed " + handle); return true; }
        AcDbVoidPtrArray pieces;
        const Acad::ErrorStatus exEs = pSrc->explode(pieces);
        pSrc->close();
        if (exEs != Acad::eOk) {
            for (int i = 0; i < pieces.length(); ++i) delete static_cast<AcDbEntity*>(pieces[i]);
            emitNativeError(r, "EXPLODE_FAILED", "explode errorstatus " + std::to_string(static_cast<int>(exEs)));
            return true;
        }
        std::ostringstream handlesJson; handlesJson.precision(kJsonDoublePrecision);
        Acad::ErrorStatus appendEs = Acad::eOk;
        const int appended = m08gAppendPieces(pDb, pieces, handlesJson, appendEs);
        int probes = 0, ms = 0; countModelSpace(pDb, ms, probes);
        r << "\"result\":{\"exploded\":true,\"piece_count\":" << appended
          << ",\"handles\":" << handlesJson.str()
          << ",\"source\":" << njsonStr(handle)
          << ",\"modelspace_entities_after\":" << ms << "},"
          << "\"status\":\"ok\"}";
        return true;
    }
    if (op == "modify.entity.solid3d.boolean") {
        std::string handle, otherHandle;
        if (!m08gFindHandle(job, handle)) { emitNativeError(r, "MISSING_ARG", "modify.entity.solid3d.boolean requires handle"); return true; }
        if (!jsonFindString(job, "other_handle", otherHandle) || otherHandle.empty()) { emitNativeError(r, "MISSING_ARG", "modify.entity.solid3d.boolean requires other_handle"); return true; }
        AcDbEntity* pEnt = m08gOpenEntityForWrite(pDb, handle);
        AcDb3dSolid* pSolid = AcDb3dSolid::cast(pEnt);
        if (pSolid == nullptr) { if (pEnt) pEnt->close(); emitNativeError(r, "INVALID_INPUT", "target handle is not AcDb3dSolid"); return true; }
        AcDbObjectId otherId;
        if (!resolveHandle(pDb, otherHandle, otherId)) { pSolid->close(); emitNativeError(r, "ENTITY_NOT_FOUND", "other_handle not found"); return true; }
        AcDbEntity* pOtherEnt = nullptr;
        if (acdbOpenObject(pOtherEnt, otherId, AcDb::kForRead) != Acad::eOk || pOtherEnt == nullptr) { pSolid->close(); emitNativeError(r, "ENTITY_NOT_FOUND", "could not open other_handle"); return true; }
        AcDb3dSolid* pOther = AcDb3dSolid::cast(pOtherEnt);
        if (pOther == nullptr) { pOtherEnt->close(); pSolid->close(); emitNativeError(r, "INVALID_INPUT", "other_handle is not AcDb3dSolid"); return true; }
        AcDb3dSolid* pClone = AcDb3dSolid::cast(pOther->clone());
        pOther->close();
        if (pClone == nullptr) { pSolid->close(); emitNativeError(r, "CLONE_FAILED", "could not clone boolean operand"); return true; }
        std::string boolOp; jsonFindString(job, "bool_op", boolOp); if (boolOp.empty()) boolOp = "unite";
        AcDb::BoolOperType bop = AcDb::kBoolUnite;
        if (boolOp == "subtract" || boolOp == "difference") bop = AcDb::kBoolSubtract;
        else if (boolOp == "intersect" || boolOp == "intersection") bop = AcDb::kBoolIntersect;
        const Acad::ErrorStatus es = pSolid->booleanOper(bop, pClone);
        delete pClone;
        pSolid->close();
        r << "\"result\":{\"modified\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"handle\":" << njsonStr(handle)
          << ",\"other_handle\":" << njsonStr(otherHandle)
          << ",\"bool_op\":" << njsonStr(boolOp) << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }
    if (op == "modify.curve.offset") {
        std::string handle;
        if (!m08gFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "modify.curve.offset requires 'handle'");
            return true;
        }
        double dist = 0.0;
        if (!jsonFindNumber(job, "distance", dist) || dist == 0.0) {
            emitNativeError(r, "MISSING_ARG", "modify.curve.offset requires nonzero 'distance'");
            return true;
        }
        AcDbObjectId cid;
        if (!resolveHandle(pDb, handle, cid)) { emitNativeError(r, "ENTITY_NOT_FOUND", "no entity for handle " + handle); return true; }
        AcDbEntity* pEnt = nullptr;
        if (acdbOpenObject(pEnt, cid, AcDb::kForRead) != Acad::eOk) { emitNativeError(r, "ENTITY_NOT_FOUND", "open failed " + handle); return true; }
        AcDbCurve* pCurve = AcDbCurve::cast(pEnt);
        if (pCurve == nullptr) { pEnt->close(); emitNativeError(r, "INVALID_INPUT", "handle " + handle + " is not a curve"); return true; }
        AcDbVoidPtrArray offsets;
        const Acad::ErrorStatus offEs = pCurve->getOffsetCurves(dist, offsets);
        pEnt->close();
        if (offEs != Acad::eOk) {
            for (int i = 0; i < offsets.length(); ++i) delete static_cast<AcDbEntity*>(offsets[i]);
            emitNativeError(r, "OFFSET_FAILED", "getOffsetCurves errorstatus " + std::to_string(static_cast<int>(offEs)));
            return true;
        }
        std::ostringstream handlesJson; handlesJson.precision(kJsonDoublePrecision);
        Acad::ErrorStatus appendEs = Acad::eOk;
        const int appended = m08gAppendPieces(pDb, offsets, handlesJson, appendEs);
        int probes = 0, ms = 0; countModelSpace(pDb, ms, probes);
        r << "\"result\":{\"created\":" << (appended > 0 ? "true" : "false")
          << ",\"offset_count\":" << appended
          << ",\"handles\":" << handlesJson.str()
          << ",\"source\":" << njsonStr(handle)
          << ",\"distance\":" << dist
          << ",\"modelspace_entities_after\":" << ms << "},"
          << "\"status\":\"" << (appended > 0 ? "ok" : "error") << "\"}";
        return true;
    }
    if (op == "modify.curve.split") {
        std::string handle;
        if (!m08gFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "modify.curve.split requires 'handle'");
            return true;
        }
        AcGeDoubleArray params;
        const std::string key = "\"params\"";
        size_t pp = job.find(key);
        if (pp != std::string::npos) {
            size_t lb = job.find('[', pp);
            size_t rb = (lb == std::string::npos) ? std::string::npos : job.find(']', lb);
            if (lb != std::string::npos && rb != std::string::npos) {
                size_t i = lb + 1;
                while (i < rb) {
                    // skip whitespace/commas
                    while (i < rb && (job[i] == ' ' || job[i] == ',' || job[i] == '\t' || job[i] == '\n' || job[i] == '\r')) ++i;
                    if (i >= rb) break;
                    char* endp = nullptr;
                    const double v = strtod(job.c_str() + i, &endp);
                    if (endp == job.c_str() + i) break;
                    params.append(v);
                    i = static_cast<size_t>(endp - job.c_str());
                }
            }
        }
        if (params.length() == 0) {
            emitNativeError(r, "MISSING_ARG", "modify.curve.split requires 'params':[param,...] (curve param values)");
            return true;
        }
        AcDbObjectId cid;
        if (!resolveHandle(pDb, handle, cid)) { emitNativeError(r, "ENTITY_NOT_FOUND", "no entity for handle " + handle); return true; }
        AcDbEntity* pEnt = nullptr;
        if (acdbOpenObject(pEnt, cid, AcDb::kForRead) != Acad::eOk) { emitNativeError(r, "ENTITY_NOT_FOUND", "open failed " + handle); return true; }
        AcDbCurve* pCurve = AcDbCurve::cast(pEnt);
        if (pCurve == nullptr) { pEnt->close(); emitNativeError(r, "INVALID_INPUT", "handle " + handle + " is not a curve"); return true; }
        AcDbVoidPtrArray segs;
        const Acad::ErrorStatus spEs = pCurve->getSplitCurves(params, segs);
        pEnt->close();
        if (spEs != Acad::eOk) {
            for (int i = 0; i < segs.length(); ++i) delete static_cast<AcDbEntity*>(segs[i]);
            emitNativeError(r, "SPLIT_FAILED", "getSplitCurves errorstatus " + std::to_string(static_cast<int>(spEs)));
            return true;
        }
        std::ostringstream handlesJson; handlesJson.precision(kJsonDoublePrecision);
        Acad::ErrorStatus appendEs = Acad::eOk;
        const int appended = m08gAppendPieces(pDb, segs, handlesJson, appendEs);
        int probes = 0, ms = 0; countModelSpace(pDb, ms, probes);
        r << "\"result\":{\"created\":" << (appended > 0 ? "true" : "false")
          << ",\"segment_count\":" << appended
          << ",\"handles\":" << handlesJson.str()
          << ",\"source\":" << njsonStr(handle)
          << ",\"modelspace_entities_after\":" << ms << "},"
          << "\"status\":\"" << (appended > 0 ? "ok" : "error") << "\"}";
        return true;
    }
    if (op == "modify.curve.to_spline") {
        std::string handle;
        if (!m08gFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "modify.curve.to_spline requires 'handle'");
            return true;
        }
        AcDbObjectId cid;
        if (!resolveHandle(pDb, handle, cid)) { emitNativeError(r, "ENTITY_NOT_FOUND", "no entity for handle " + handle); return true; }
        AcDbEntity* pEnt = nullptr;
        if (acdbOpenObject(pEnt, cid, AcDb::kForRead) != Acad::eOk) { emitNativeError(r, "ENTITY_NOT_FOUND", "open failed " + handle); return true; }
        AcDbCurve* pCurve = AcDbCurve::cast(pEnt);
        if (pCurve == nullptr) { pEnt->close(); emitNativeError(r, "INVALID_INPUT", "handle " + handle + " is not a curve"); return true; }
        AcDbSpline* pSpline = nullptr;
        const Acad::ErrorStatus gsEs = pCurve->getSpline(pSpline);
        pEnt->close();
        if (gsEs != Acad::eOk || pSpline == nullptr) {
            delete pSpline;
            emitNativeError(r, "TO_SPLINE_FAILED", "getSpline errorstatus " + std::to_string(static_cast<int>(gsEs)));
            return true;
        }
        AcDbObjectId id; int ms = 0;
        const Acad::ErrorStatus es = m08gAppendEntity(pDb, layer, pSpline, id, ms);
        r << "\"result\":{\"created\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"source\":" << njsonStr(handle)
          << ",\"handle\":" << njsonStr(es == Acad::eOk ? handleOfId(id) : std::string())
          << ",\"modelspace_entities_after\":" << ms << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }

    // Admitted by HasOp but no branch handled it -> seam drift. Emit the structured
    // guard (lockstep invariant; mirrors the sibling family modules).
    emitNativeError(r, "OPERATION_DISPATCH_MISMATCH",
                    "operation '" + op + "' admitted by m08gHasOp but not handled in m08gDispatch");
    return true;
}
