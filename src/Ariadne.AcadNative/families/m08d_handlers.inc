// families/m08d_handlers.inc — M08D READ family: entities / geometry-kernel / BRep-solid topology read.
//
// Owned by the M08D teammate (PR-scoped). #included into AriadneNativeJob.cpp; sees every
// in-TU helper. Contract (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - m08dHasOp(op): true for every op id this family implements.
//   - m08dDispatch(op, ctx, r): handle it (append "result":{...},"status":"ok") and return true; else false.
// Use serializeEntityCommon for entity-common fields, AriadneReadTransaction for scoped reads,
// resolveHandle for hex->id, the resbuf serializers for xdata. NO original DWG writes.
//
// Build-reachability (see reports/tickets/M08D_PLAN.md): Groups A (entities) + B (geometry
// kernel) + the main-path subentity reads use only main-`inc` headers (AcGe / AcDbEntity /
// AcDbCurve / dbsubeid.h) that are already on the .crx/.arx include path and linked
// (acge26.lib/acdb26.lib). The AcBr BRep group lives under C:\ObjectARX 2027\utils\brep\inc\
// (NOT on the include path) and needs the AcBr import lib acbr26.lib + acgex26.lib (in
// utils\brep\lib-x64, NOT on the linker path) plus acgeoment.lib (AcDb3dSolid/AcGeNurbSurface;
// in the on-path lib-x64). NOTE: the research slice wrongly named AcDrawBridge.lib as the AcBr
// import lib — dumpbin proves AcDrawBridge.lib has ZERO AcBr symbols (only Config@DrawBridge).
// We reach all of it WITHOUT editing the vcxproj via an absolute #include block + absolute-path
// #pragma comment(lib) below — both legal in this TU and keeping the disjoint-file contract.

#include "dbcurve.h"      // AcDbCurve protocol (start/end/closed/planar/area)
#include "dbsol3d.h"      // AcDb3dSolid::checkInterference
#include "dbsurf.h"       // AcDbSurface::getSubentColor
#include "dbSubD.h"       // AcDbSubDMesh::getSubentColor
#include "AcCmColor.h"    // AcCmColor payload for subentity color reads
#include "dbsubeid.h"     // AcDbSubentId / AcDbFullSubentPath
#include "gept3dar.h"     // AcGePoint3dArray
#include "gemat3d.h"      // AcGeMatrix3d
#include "gescl3d.h"      // AcGeScale3d
#include "gelnsg3d.h"     // AcGeLineSeg3d
#include "gearc3d.h"      // AcGeCircArc3d
#include "geell3d.h"      // AcGeEllipArc3d
#include "genurb3d.h"     // AcGeNurbCurve3d
#include "genurbsf.h"     // AcGeNurbSurface
#include "gexbndsf.h"     // AcGeExternalBoundedSurface (complete type for delete)
#include "gecomp3d.h"     // AcGeCompositeCurve3d
#include "gecint3d.h"     // AcGeCurveCurveInt3d
#include "geponc3d.h"     // AcGePointOnCurve3d
#include "gekvec.h"       // AcGeKnotVector
#include "gevptar.h"      // AcGeVoidPointerArray
#include "geline3d.h"     // AcGeLine3d (concrete AcGeLinearEnt3d for line containment)
#include "getol.h"        // AcGeTol
#include "geintrvl.h"     // AcGeInterval

// --- AcBr (BRep) reach-without-vcxproj-edit ---------------------------------
// Absolute include dir is not on the project's AdditionalIncludeDirectories and the
// contract forbids editing the .vcxproj; absolute #include is the in-`.inc` way in.
// AcDrawBridge.lib is the AcBr import lib; lib-x64 is already on AdditionalLibraryDirectories.
#define ARIADNE_M08D_BREP 1
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brgbl.h"
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brent.h"
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brbrep.h"
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brcplx.h"
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brshell.h"
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brface.h"
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brloop.h"
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\bredge.h"
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brvtx.h"
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brprops.h"
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brhit.h"
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brbctrav.h"   // AcBrBrepComplexTraverser
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brbstrav.h"   // AcBrBrepShellTraverser
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brbftrav.h"   // AcBrBrepFaceTraverser
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brbetrav.h"   // AcBrBrepEdgeTraverser
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brbvtrav.h"   // AcBrBrepVertexTraverser
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brcstrav.h"   // AcBrComplexShellTraverser
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brsftrav.h"   // AcBrShellFaceTraverser
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brfltrav.h"   // AcBrFaceLoopTraverser
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brletrav.h"   // AcBrLoopEdgeTraverser
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brlvtrav.h"   // AcBrLoopVertexTraverser
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\breltrav.h"   // AcBrEdgeLoopTraverser
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brvetrav.h"   // AcBrVertexEdgeTraverser
#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\brvltrav.h"   // AcBrVertexLoopTraverser
#include "geblok3d.h"   // AcGeBoundBlock3d (main inc path)
#include "gelent3d.h"   // AcGeLinearEnt3d (line containment arg; main inc path)
// AcBr import lib lives in the brep utils dir (NOT AcDrawBridge.lib — the research
// slice was wrong: AcDrawBridge.lib is a DrawBridge/Config localization lib with no
// AcBr symbols). acbr26.lib (274 AcBr symbols) + acgex26.lib are under
// utils\brep\lib-x64 (NOT on the project's AdditionalLibraryDirectories), so we name
// them by ABSOLUTE path in the pragma. acgeoment.lib (AcDb3dSolid + AcGeNurbSurface;
// in the on-path lib-x64) is what the brep SAMPLE vcxproj itself links.
#pragma comment(lib, "C:\\ObjectARX 2027\\utils\\brep\\lib-x64\\acbr26.lib")
#pragma comment(lib, "C:\\ObjectARX 2027\\utils\\brep\\lib-x64\\acgex26.lib")
#pragma comment(lib, "acgeoment.lib")

//============================================================================
// M08D shared helpers (file-scope statics inside this TU; m08d-prefixed to
// avoid any collision with sibling family .inc files).
//============================================================================

// Open a model-resident entity for read by hex handle. Returns nullptr if the
// handle does not resolve or the object is not an entity. Caller closes.
static AcDbEntity* m08dOpenEntity(AcDbDatabase* pDb, const std::string& handleHex)
{
    AcDbObjectId id;
    if (!resolveHandle(pDb, handleHex, id))
        return nullptr;
    AcDbEntity* pEnt = nullptr;
    if (acdbOpenObject(pEnt, id, AcDb::kForRead) != Acad::eOk)
        return nullptr;
    return pEnt;
}

// Pull a hex handle from the job: top-level "handle", or args.handle.
static bool m08dFindHandle(const std::string& job, std::string& out)
{
    if (jsonFindString(job, "handle", out) && !out.empty())
        return true;
    std::string argsJson;
    if (jsonFindObject(job, "args", argsJson) &&
        jsonFindString(argsJson, "handle", out) && !out.empty())
        return true;
    return false;
}

// Parse a named point sub-object ("a":{x,y,z}) from job or job.args.
static bool m08dFindNamedPoint(const std::string& job, const char* key,
                               double& x, double& y, double& z)
{
    std::string obj;
    if (jsonFindObject(job, key, obj) && parsePointFromObject(obj, x, y, z))
        return true;
    std::string argsJson;
    if (jsonFindObject(job, "args", argsJson) &&
        jsonFindObject(argsJson, key, obj) && parsePointFromObject(obj, x, y, z))
        return true;
    return false;
}

static std::string m08dPointJson(const AcGePoint3d& p)
{
    std::ostringstream o;
    o << "[" << p.x << "," << p.y << "," << p.z << "]";
    return o.str();
}
static std::string m08dVectorJson(const AcGeVector3d& v)
{
    std::ostringstream o;
    o << "[" << v.x << "," << v.y << "," << v.z << "]";
    return o.str();
}
static std::string m08dMatrixJson(const AcGeMatrix3d& m)
{
    std::ostringstream o;
    o << "[";
    for (int row = 0; row < 4; ++row) {
        if (row) o << ",";
        o << "[" << m(row, 0) << "," << m(row, 1) << "," << m(row, 2) << "," << m(row, 3) << "]";
    }
    o << "]";
    return o.str();
}

// AcGe::EntityId -> short stable kind string (curve/surface classification).
static const char* m08dGeEntityKind(AcGe::EntityId id)
{
    switch (id) {
        case AcGe::kLineSeg3d:              return "line_seg";
        case AcGe::kCircArc3d:              return "circular_arc";
        case AcGe::kEllipArc3d:             return "elliptical_arc";
        case AcGe::kNurbCurve3d:            return "nurb_curve";
        case AcGe::kExternalCurve3d:        return "external_curve";
        case AcGe::kPlane:                  return "plane";
        case AcGe::kCylinder:               return "cylinder";
        case AcGe::kCone:                   return "cone";
        case AcGe::kSphere:                 return "sphere";
        case AcGe::kTorus:                  return "torus";
        case AcGe::kNurbSurface:            return "nurb_surface";
        case AcGe::kExternalBoundedSurface: return "external_bounded_surface";
        default:                            return "other";
    }
}

#ifdef ARIADNE_M08D_BREP
// Bind an AcBrBrep to a DB entity by hex handle (read-only). Returns AcBr::eOk on
// success and leaves brep set; otherwise a non-eOk status. pEnt is opened+closed here.
static AcBr::ErrorStatus m08dBindBrep(AcDbDatabase* pDb, const std::string& handleHex,
                                      AcBrBrep& brep, std::string& classNameOut)
{
    AcDbEntity* pEnt = m08dOpenEntity(pDb, handleHex);
    if (pEnt == nullptr)
        return AcBr::eInvalidObject;
    if (pEnt->isA() != nullptr)
        classNameOut = acharToAscii(pEnt->isA()->name());
    const AcBr::ErrorStatus es = brep.set(*pEnt);
    pEnt->close();
    return es;
}

// "kind" string for an AcBr loop type.
static const char* m08dLoopTypeKind(AcBr::LoopType t)
{
    switch (t) {
        case AcBr::kLoopExterior: return "exterior";
        case AcBr::kLoopInterior: return "interior";
        case AcBr::kLoopWinding:  return "winding";
        default:                  return "unclassified";
    }
}
static const char* m08dShellTypeKind(AcBr::ShellType t)
{
    switch (t) {
        case AcBr::kShellExterior: return "exterior";
        case AcBr::kShellInterior: return "interior";
        default:                   return "unclassified";
    }
}
#endif // ARIADNE_M08D_BREP

//============================================================================
// HasOp — every op id this family implements (gate admission). Kept in lockstep
// with the dispatch branches below (asserted by tests/unit/test_m08d_handlers.py).
//============================================================================
static bool m08dHasOp(const std::string& op)
{
    return
        // Group A — entities
        op == "inspect.entity.common" ||
        op == "inspect.entity.geomextents" ||
        op == "inspect.entity.osnap" ||
        op == "inspect.curve.protocol" ||
        // Group B — geometry kernel
        op == "compute.geometry.point.distance" ||
        op == "compute.geometry.point.transform" ||
        op == "compute.geometry.matrix.build" ||
        op == "compute.geometry.matrix.compose" ||
        op == "compute.geometry.scale.build" ||
        op == "compute.geometry.lineseg" ||
        op == "compute.geometry.circarc" ||
        op == "compute.geometry.elliparc" ||
        op == "compute.geometry.tolerance" ||
        op == "compute.geometry.curve.eval" ||
        op == "compute.geometry.curve.sample" ||
        op == "compute.geometry.curve.closest" ||
        op == "compute.geometry.curve.intersect" ||
        op == "compute.geometry.nurbcurve" ||
        op == "compute.geometry.compositecurve" ||
        op == "compute.geometry.surface.nurb" ||
        op == "compute.entity.intersect" ||
        op == "compute.solid3d.interference" ||
        // Group C (main-path subentity reads)
        op == "inspect.subentity.geom_extents" ||
        op == "inspect.subentity.class_id" ||
        op == "inspect.subentity.ptr" ||
        op == "inspect.subentity.color" ||
        op == "inspect.subentity.markers_at_path" ||
        op == "inspect.subentity.path_at_marker" ||
        op == "ui.subentity.highlight" ||
#ifdef ARIADNE_M08D_BREP
        // Group C — AcBr BRep
        op == "inspect.brep.from_entity" ||
        op == "inspect.brep.validate" ||
        op == "inspect.brep.changed" ||
        op == "inspect.brep.validation_level" ||
        op == "inspect.brep.bounds" ||
        op == "inspect.brep.owner" ||
        op == "inspect.brep.solid_roundtrip" ||
        op == "inspect.brep.from_subentpath" ||
        op == "compute.brep.volume" ||
        op == "compute.brep.surface_area" ||
        op == "compute.brep.perimeter" ||
        op == "compute.brep.massprops" ||
        op == "compute.brep.point_containment" ||
        op == "compute.brep.line_containment" ||
        op == "traverse.brep.complexes" ||
        op == "traverse.brep.shells" ||
        op == "traverse.brep.faces" ||
        op == "traverse.brep.edges" ||
        op == "traverse.brep.vertices" ||
        op == "traverse.complex.shells" ||
        op == "traverse.shell.faces" ||
        op == "traverse.face.loops" ||
        op == "traverse.loop.edges" ||
        op == "traverse.loop.vertices" ||
        op == "traverse.edge.loops" ||
        op == "traverse.vertex.edges" ||
        op == "traverse.vertex.loops" ||
        op == "inspect.shell.type" ||
        op == "inspect.shell.complex" ||
        op == "inspect.face.area" ||
        op == "inspect.face.orientation" ||
        op == "inspect.face.shell" ||
        op == "inspect.face.surface" ||
        op == "inspect.face.surface_type" ||
        op == "inspect.face.surface_as_nurb" ||
        op == "inspect.face.surface_as_trimmed_nurbs" ||
        op == "inspect.edge.curve" ||
        op == "inspect.edge.curve_type" ||
        op == "inspect.edge.curve_as_nurb" ||
        op == "inspect.edge.orientation" ||
        op == "inspect.edge.vertices" ||
        op == "inspect.vertex.point" ||
        op == "inspect.loop.type" ||
        op == "inspect.loop.face" ||
#endif // ARIADNE_M08D_BREP
        false;
}

//============================================================================
// Dispatch — handle the op (append result + status, return true) or return false.
//============================================================================
static bool m08dDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    if (!m08dHasOp(op))
        return false;

    AcDbDatabase* pDb = ctx.pDb;
    const std::string& job = ctx.job;

    //========================================================================
    // Group A — entities (read by handle; serializeEntityCommon + op-specific)
    //========================================================================
    if (op == "inspect.entity.common") {
        std::string handle;
        if (!m08dFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "inspect.entity.common requires 'handle'");
            return true;
        }
        AcDbEntity* pEnt = m08dOpenEntity(pDb, handle);
        if (pEnt == nullptr) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "no entity for handle " + handle);
            return true;
        }
        AriadneReadTransaction rt(pDb);
        std::ostringstream o;
        o << serializeEntityCommon(pEnt);
        o << ",\"lineweight\":" << static_cast<int>(pEnt->lineWeight());
        pEnt->close();
        r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "inspect.entity.geomextents") {
        std::string handle;
        if (!m08dFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "inspect.entity.geomextents requires 'handle'");
            return true;
        }
        AcDbEntity* pEnt = m08dOpenEntity(pDb, handle);
        if (pEnt == nullptr) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "no entity for handle " + handle);
            return true;
        }
        AcDbExtents ext;
        const Acad::ErrorStatus es = pEnt->getGeomExtents(ext);
        std::ostringstream o;
        o << serializeEntityCommon(pEnt);
        if (es == Acad::eOk) {
            o << ",\"min\":" << m08dPointJson(ext.minPoint())
              << ",\"max\":" << m08dPointJson(ext.maxPoint());
        } else {
            o << ",\"extents_status\":" << static_cast<int>(es);
        }
        pEnt->close();
        r << "\"result\":{" << o.str()
          << ",\"has_extents\":" << (es == Acad::eOk ? "true" : "false")
          << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "inspect.entity.osnap") {
        std::string handle;
        if (!m08dFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "inspect.entity.osnap requires 'handle'");
            return true;
        }
        AcDbEntity* pEnt = m08dOpenEntity(pDb, handle);
        if (pEnt == nullptr) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "no entity for handle " + handle);
            return true;
        }
        // Headless osnap probe: kOsModeEnd, null GS marker, pick/last at origin,
        // identity view xform (a pure DB query; entities-geometry slice row).
        AcGePoint3dArray snapPts;
        AcDbIntArray geomIds;
        AcGePoint3d origin(0.0, 0.0, 0.0);
        AcGeMatrix3d viewXform;   // identity
        const Acad::ErrorStatus es = pEnt->getOsnapPoints(
            AcDb::kOsModeEnd, 0, origin, origin, viewXform, snapPts, geomIds);
        std::ostringstream o;
        o << "\"snap_mode\":\"end\",\"point_count\":" << snapPts.length()
          << ",\"points\":[";
        for (int i = 0; i < snapPts.length(); ++i) {
            if (i) o << ",";
            o << m08dPointJson(snapPts[i]);
        }
        o << "],\"osnap_status\":" << static_cast<int>(es);
        pEnt->close();
        r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "inspect.curve.protocol") {
        std::string handle;
        if (!m08dFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "inspect.curve.protocol requires 'handle'");
            return true;
        }
        AcDbEntity* pEnt = m08dOpenEntity(pDb, handle);
        if (pEnt == nullptr) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "no entity for handle " + handle);
            return true;
        }
        AcDbCurve* pCurve = AcDbCurve::cast(pEnt);
        std::ostringstream o;
        o << "\"is_curve\":" << (pCurve != nullptr ? "true" : "false");
        if (pCurve != nullptr) {
            AcGePoint3d sp, ep;
            const bool gotStart = (pCurve->getStartPoint(sp) == Acad::eOk);
            const bool gotEnd = (pCurve->getEndPoint(ep) == Acad::eOk);
            const bool closed = (pCurve->isClosed() == Adesk::kTrue);
            const bool planar = (pCurve->isPlanar() == Adesk::kTrue);
            if (gotStart) o << ",\"start\":" << m08dPointJson(sp);
            if (gotEnd)   o << ",\"end\":" << m08dPointJson(ep);
            o << ",\"closed\":" << (closed ? "true" : "false")
              << ",\"planar\":" << (planar ? "true" : "false");
            if (closed) {
                double area = 0.0;
                if (pCurve->getArea(area) == Acad::eOk)
                    o << ",\"area\":" << area;
            }
        }
        pEnt->close();
        r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
        return true;
    }

    //========================================================================
    // Group B — geometry kernel (pure AcGe compute; args from JSON; host-less)
    //========================================================================
    if (op == "compute.geometry.point.distance") {
        double ax, ay, az, bx, by, bz;
        if (!m08dFindNamedPoint(job, "a", ax, ay, az) ||
            !m08dFindNamedPoint(job, "b", bx, by, bz)) {
            emitNativeError(r, "MISSING_ARG", "compute.geometry.point.distance requires points 'a' and 'b'");
            return true;
        }
        const AcGePoint3d a(ax, ay, az), b(bx, by, bz);
        r << "\"result\":{\"a\":" << m08dPointJson(a) << ",\"b\":" << m08dPointJson(b)
          << ",\"distance\":" << a.distanceTo(b) << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "compute.geometry.point.transform") {
        double px, py, pz;
        if (!m08dFindNamedPoint(job, "point", px, py, pz)) {
            emitNativeError(r, "MISSING_ARG", "compute.geometry.point.transform requires 'point'");
            return true;
        }
        double tx = 0.0, ty = 0.0, tz = 0.0;
        m08dFindNamedPoint(job, "translate", tx, ty, tz);  // default: identity translate
        AcGeMatrix3d m;
        m.setToTranslation(AcGeVector3d(tx, ty, tz));
        AcGePoint3d p(px, py, pz);
        const AcGePoint3d before = p;
        p.transformBy(m);
        r << "\"result\":{\"input\":" << m08dPointJson(before)
          << ",\"translate\":[" << tx << "," << ty << "," << tz << "]"
          << ",\"output\":" << m08dPointJson(p) << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "compute.geometry.matrix.build") {
        // kind: translate (default) | scale ; vector from "translate" or scalar "factor".
        std::string kind = "translate";
        jsonFindString(job, "kind", kind);
        AcGeMatrix3d m;
        if (kind == "scale") {
            double factor = 1.0;
            jsonFindNumber(job, "factor", factor);
            m.setToScaling(factor);
            r << "\"result\":{\"kind\":\"scale\",\"factor\":" << factor
              << ",\"matrix\":" << m08dMatrixJson(m) << "},\"status\":\"ok\"}";
        } else {
            double tx = 0.0, ty = 0.0, tz = 0.0;
            m08dFindNamedPoint(job, "translate", tx, ty, tz);
            m.setToTranslation(AcGeVector3d(tx, ty, tz));
            r << "\"result\":{\"kind\":\"translate\",\"translate\":[" << tx << "," << ty << "," << tz << "]"
              << ",\"matrix\":" << m08dMatrixJson(m) << "},\"status\":\"ok\"}";
        }
        return true;
    }
    if (op == "compute.geometry.matrix.compose") {
        // Build T(translate) then S(factor), compose (T*S) and report the inverse.
        double tx = 0.0, ty = 0.0, tz = 0.0;
        m08dFindNamedPoint(job, "translate", tx, ty, tz);
        double factor = 1.0;
        jsonFindNumber(job, "factor", factor);
        AcGeMatrix3d t, s;
        t.setToTranslation(AcGeVector3d(tx, ty, tz));
        s.setToScaling(factor);
        AcGeMatrix3d composed = t;
        composed.preMultBy(s);
        AcGeMatrix3d inv;
        const Adesk::Boolean invertible = composed.inverse(inv, 1.0e-12);
        r << "\"result\":{\"composed\":" << m08dMatrixJson(composed)
          << ",\"invertible\":" << (invertible == Adesk::kTrue ? "true" : "false");
        if (invertible == Adesk::kTrue)
            r << ",\"inverse\":" << m08dMatrixJson(inv);
        r << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "compute.geometry.scale.build") {
        double sx = 1.0, sy = 1.0, sz = 1.0;
        bool haveXyz = jsonFindNumber(job, "sx", sx);
        haveXyz = jsonFindNumber(job, "sy", sy) || haveXyz;
        haveXyz = jsonFindNumber(job, "sz", sz) || haveXyz;
        double factor = 1.0;
        const bool haveFactor = jsonFindNumber(job, "factor", factor);
        AcGeScale3d scale = haveFactor && !haveXyz ? AcGeScale3d(factor) : AcGeScale3d(sx, sy, sz);
        r << "\"result\":{\"sx\":" << scale.sx << ",\"sy\":" << scale.sy << ",\"sz\":" << scale.sz
          << ",\"proportional\":" << (scale.isProportional() == Adesk::kTrue ? "true" : "false")
          << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "compute.geometry.lineseg") {
        double ax, ay, az, bx, by, bz;
        if (!m08dFindNamedPoint(job, "a", ax, ay, az) ||
            !m08dFindNamedPoint(job, "b", bx, by, bz)) {
            emitNativeError(r, "MISSING_ARG", "compute.geometry.lineseg requires points 'a' and 'b'");
            return true;
        }
        const AcGePoint3d a(ax, ay, az), b(bx, by, bz);
        AcGeLineSeg3d seg(a, b);
        const AcGePoint3d mid = seg.midPoint();
        r << "\"result\":{\"start\":" << m08dPointJson(a) << ",\"end\":" << m08dPointJson(b)
          << ",\"length\":" << a.distanceTo(b) << ",\"midpoint\":" << m08dPointJson(mid)
          << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "compute.geometry.circarc") {
        double cx, cy, cz;
        if (!m08dFindNamedPoint(job, "center", cx, cy, cz)) {
            emitNativeError(r, "MISSING_ARG", "compute.geometry.circarc requires 'center'");
            return true;
        }
        double radius = 1.0;
        jsonFindNumber(job, "radius", radius);
        const AcGePoint3d c(cx, cy, cz);
        AcGeCircArc3d arc(c, AcGeVector3d::kZAxis, radius);
        AcGePoint3d evalStart = arc.evalPoint(0.0);
        r << "\"result\":{\"center\":" << m08dPointJson(c) << ",\"radius\":" << arc.radius()
          << ",\"point_at_param0\":" << m08dPointJson(evalStart) << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "compute.geometry.elliparc") {
        double cx, cy, cz;
        if (!m08dFindNamedPoint(job, "center", cx, cy, cz)) {
            emitNativeError(r, "MISSING_ARG", "compute.geometry.elliparc requires 'center'");
            return true;
        }
        double major = 2.0, minor = 1.0;
        jsonFindNumber(job, "major", major);
        jsonFindNumber(job, "minor", minor);
        const AcGePoint3d c(cx, cy, cz);
        AcGeEllipArc3d ell(c, AcGeVector3d::kXAxis, AcGeVector3d::kYAxis, major, minor);
        const double ratio = (major != 0.0) ? (minor / major) : 0.0;
        r << "\"result\":{\"center\":" << m08dPointJson(c)
          << ",\"major_radius\":" << ell.majorRadius() << ",\"minor_radius\":" << ell.minorRadius()
          << ",\"radius_ratio\":" << ratio << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "compute.geometry.tolerance") {
        AcGeTol tol;
        const double eq = tol.equalPoint();
        const double ev = tol.equalVector();
        r << "\"result\":{\"equal_point\":" << eq << ",\"equal_vector\":" << ev
          << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "compute.geometry.curve.eval") {
        // Build a circular arc (center/radius) and evaluate at param.
        double cx = 0.0, cy = 0.0, cz = 0.0;
        m08dFindNamedPoint(job, "center", cx, cy, cz);
        double radius = 1.0, param = 0.0;
        jsonFindNumber(job, "radius", radius);
        jsonFindNumber(job, "param", param);
        AcGeCircArc3d arc(AcGePoint3d(cx, cy, cz), AcGeVector3d::kZAxis, radius);
        const AcGeCurve3d& curve = arc;
        const AcGePoint3d p = curve.evalPoint(param);
        r << "\"result\":{\"param\":" << param << ",\"point\":" << m08dPointJson(p)
          << ",\"curve_kind\":\"" << m08dGeEntityKind(arc.type()) << "\"},\"status\":\"ok\"}";
        return true;
    }
    if (op == "compute.geometry.curve.sample") {
        double cx = 0.0, cy = 0.0, cz = 0.0;
        m08dFindNamedPoint(job, "center", cx, cy, cz);
        double radius = 1.0;
        double countRaw = 8.0;
        jsonFindNumber(job, "radius", radius);
        jsonFindNumber(job, "count", countRaw);
        int count = static_cast<int>(countRaw);
        if (count < 2) count = 2;
        if (count > 1024) count = 1024;
        AcGeCircArc3d arc(AcGePoint3d(cx, cy, cz), AcGeVector3d::kZAxis, radius);
        const AcGeCurve3d& curve = arc;
        AcGePoint3dArray pts;
        curve.getSamplePoints(count, pts);
        r << "\"result\":{\"requested\":" << count << ",\"point_count\":" << pts.length()
          << ",\"points\":[";
        for (int i = 0; i < pts.length(); ++i) { if (i) r << ","; r << m08dPointJson(pts[i]); }
        r << "]},\"status\":\"ok\"}";
        return true;
    }
    if (op == "compute.geometry.curve.closest") {
        double cx = 0.0, cy = 0.0, cz = 0.0, qx, qy, qz;
        m08dFindNamedPoint(job, "center", cx, cy, cz);
        if (!m08dFindNamedPoint(job, "query", qx, qy, qz)) {
            emitNativeError(r, "MISSING_ARG", "compute.geometry.curve.closest requires 'query' point");
            return true;
        }
        double radius = 1.0;
        jsonFindNumber(job, "radius", radius);
        AcGeCircArc3d arc(AcGePoint3d(cx, cy, cz), AcGeVector3d::kZAxis, radius);
        const AcGeCurve3d& curve = arc;
        const AcGePoint3d q(qx, qy, qz);
        AcGePointOnCurve3d poc;
        curve.getClosestPointTo(q, poc);
        const AcGePoint3d cp = poc.point();
        r << "\"result\":{\"query\":" << m08dPointJson(q) << ",\"closest_point\":" << m08dPointJson(cp)
          << ",\"distance\":" << q.distanceTo(cp) << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "compute.geometry.curve.intersect") {
        // Two coplanar circular arcs (center/radius a,b); report intersection points.
        double ax = 0.0, ay = 0.0, az = 0.0, bx = 0.0, by = 0.0, bz = 0.0;
        m08dFindNamedPoint(job, "a", ax, ay, az);
        m08dFindNamedPoint(job, "b", bx, by, bz);
        double ra = 1.0, rb = 1.0;
        jsonFindNumber(job, "radius_a", ra);
        jsonFindNumber(job, "radius_b", rb);
        AcGeCircArc3d arcA(AcGePoint3d(ax, ay, az), AcGeVector3d::kZAxis, ra);
        AcGeCircArc3d arcB(AcGePoint3d(bx, by, bz), AcGeVector3d::kZAxis, rb);
        AcGeCurveCurveInt3d cci(arcA, arcB);
        const int n = cci.numIntPoints();
        r << "\"result\":{\"int_point_count\":" << n << ",\"points\":[";
        for (int i = 0; i < n; ++i) { if (i) r << ","; r << m08dPointJson(cci.intPoint(i)); }
        r << "]},\"status\":\"ok\"}";
        return true;
    }
    if (op == "compute.geometry.nurbcurve") {
        // Degree-1 NURBS through provided control points (or a default unit square path).
        AcGePoint3dArray ctrl;
        // accept up to 4 named control points p0..p3; fall back to a unit triangle.
        for (int i = 0; i < 8; ++i) {
            char key[8]; std::snprintf(key, sizeof(key), "p%d", i);
            double x, y, z;
            if (m08dFindNamedPoint(job, key, x, y, z))
                ctrl.append(AcGePoint3d(x, y, z));
        }
        if (ctrl.length() < 2) {
            ctrl.setLogicalLength(0);
            ctrl.append(AcGePoint3d(0, 0, 0));
            ctrl.append(AcGePoint3d(1, 0, 0));
            ctrl.append(AcGePoint3d(1, 1, 0));
        }
        AcGeKnotVector knots;
        const int degree = 1;
        const int n = ctrl.length();
        // open uniform knot vector for a degree-1 polyline: 0,0,1,2,...,n-1,n-1
        knots.append(0.0);
        for (int i = 0; i < n; ++i) knots.append(static_cast<double>(i));
        knots.append(static_cast<double>(n - 1));
        AcGeDoubleArray weights;  // empty => non-rational
        AcGeNurbCurve3d nurb(degree, knots, ctrl, weights, Adesk::kFalse);
        const AcGeCurve3d& curve = nurb;
        AcGeInterval iv;
        curve.getInterval(iv);
        const AcGePoint3d startPt = curve.evalPoint(iv.lowerBound());
        r << "\"result\":{\"degree\":" << degree << ",\"control_point_count\":" << n
          << ",\"start_point\":" << m08dPointJson(startPt)
          << ",\"curve_kind\":\"" << m08dGeEntityKind(nurb.type()) << "\"},\"status\":\"ok\"}";
        return true;
    }
    if (op == "compute.geometry.compositecurve") {
        // Compose two line segments into one composite curve; report continuity.
        double ax = 0.0, ay = 0.0, az = 0.0, bx = 1.0, by = 0.0, bz = 0.0, cx = 1.0, cy = 1.0, cz = 0.0;
        m08dFindNamedPoint(job, "a", ax, ay, az);
        m08dFindNamedPoint(job, "b", bx, by, bz);
        m08dFindNamedPoint(job, "c", cx, cy, cz);
        AcGeLineSeg3d* seg1 = new AcGeLineSeg3d(AcGePoint3d(ax, ay, az), AcGePoint3d(bx, by, bz));
        AcGeLineSeg3d* seg2 = new AcGeLineSeg3d(AcGePoint3d(bx, by, bz), AcGePoint3d(cx, cy, cz));
        AcGeVoidPointerArray curves;
        curves.append(static_cast<void*>(seg1));
        curves.append(static_cast<void*>(seg2));
        AcGeCompositeCurve3d composite(curves);
        const AcGeCurve3d& curve = composite;
        AcGeInterval iv;
        curve.getInterval(iv);
        const double len = iv.upperBound() - iv.lowerBound();
        r << "\"result\":{\"segment_count\":2,\"param_length\":" << len
          << ",\"closed\":" << (curve.isClosed() == Adesk::kTrue ? "true" : "false")
          << "},\"status\":\"ok\"}";
        // AcGeCompositeCurve3d copies its input curves; free our temporaries.
        delete seg1;
        delete seg2;
        return true;
    }
    if (op == "compute.geometry.surface.nurb") {
        // Build a planar bilinear (degree 1x1) NURBS surface over a unit quad; eval center.
        // ctor takes raw C arrays for control points + weights (genurbsf.h:34).
        AcGeKnotVector uKnots, vKnots;
        uKnots.append(0.0); uKnots.append(0.0); uKnots.append(1.0); uKnots.append(1.0);
        vKnots.append(0.0); vKnots.append(0.0); vKnots.append(1.0); vKnots.append(1.0);
        const AcGePoint3d cps[4] = {
            AcGePoint3d(0, 0, 0), AcGePoint3d(1, 0, 0),
            AcGePoint3d(0, 1, 0), AcGePoint3d(1, 1, 0)
        };
        const double weights[4] = { 1.0, 1.0, 1.0, 1.0 };
        AcGeNurbSurface surf(1, 1, 2, 2, 2, 2, cps, weights, uKnots, vKnots);
        const AcGePoint3d center = surf.evalPoint(AcGePoint2d(0.5, 0.5));
        r << "\"result\":{\"u_degree\":1,\"v_degree\":1,\"control_point_count\":4"
          << ",\"center_point\":" << m08dPointJson(center) << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "compute.entity.intersect") {
        std::string ha, hb;
        std::string argsJson; jsonFindObject(job, "args", argsJson);
        if (!(jsonFindString(job, "handle_a", ha) || jsonFindString(argsJson, "handle_a", ha)) ||
            !(jsonFindString(job, "handle_b", hb) || jsonFindString(argsJson, "handle_b", hb))) {
            emitNativeError(r, "MISSING_ARG", "compute.entity.intersect requires 'handle_a' and 'handle_b'");
            return true;
        }
        AcDbEntity* pA = m08dOpenEntity(pDb, ha);
        AcDbEntity* pB = m08dOpenEntity(pDb, hb);
        if (pA == nullptr || pB == nullptr) {
            if (pA) pA->close();
            if (pB) pB->close();
            emitNativeError(r, "ENTITY_NOT_FOUND", "one or both handles did not resolve to entities");
            return true;
        }
        AcGePoint3dArray pts;
        const Acad::ErrorStatus es = pA->intersectWith(pB, AcDb::kOnBothOperands, pts);
        pA->close();
        pB->close();
        r << "\"result\":{\"intersect_status\":" << static_cast<int>(es)
          << ",\"point_count\":" << pts.length() << ",\"points\":[";
        for (int i = 0; i < pts.length(); ++i) { if (i) r << ","; r << m08dPointJson(pts[i]); }
        r << "]},\"status\":\"ok\"}";
        return true;
    }
    if (op == "compute.solid3d.interference") {
        std::string ha, hb;
        std::string argsJson; jsonFindObject(job, "args", argsJson);
        if (!(jsonFindString(job, "handle_a", ha) || jsonFindString(argsJson, "handle_a", ha)) ||
            !(jsonFindString(job, "handle_b", hb) || jsonFindString(argsJson, "handle_b", hb))) {
            emitNativeError(r, "MISSING_ARG", "compute.solid3d.interference requires 'handle_a' and 'handle_b'");
            return true;
        }
        AcDbEntity* pA = m08dOpenEntity(pDb, ha);
        AcDbEntity* pB = m08dOpenEntity(pDb, hb);
        AcDb3dSolid* sA = (pA != nullptr) ? AcDb3dSolid::cast(pA) : nullptr;
        AcDb3dSolid* sB = (pB != nullptr) ? AcDb3dSolid::cast(pB) : nullptr;
        if (sA == nullptr || sB == nullptr) {
            if (pA) pA->close();
            if (pB) pB->close();
            emitNativeError(r, "WRONG_OBJECT_TYPE", "both handles must be AcDb3dSolid");
            return true;
        }
        Adesk::Boolean interfere = Adesk::kFalse;
        AcDb3dSolid* pCommon = nullptr;   // createNewSolid=false, but the API still takes the out-ptr
        const Acad::ErrorStatus es = sA->checkInterference(sB, Adesk::kFalse, interfere, pCommon);
        if (pCommon != nullptr) delete pCommon;   // defensive: not appended to DB
        pA->close();
        pB->close();
        r << "\"result\":{\"check_status\":" << static_cast<int>(es)
          << ",\"solids_interfere\":" << (interfere == Adesk::kTrue ? "true" : "false")
          << "},\"status\":\"ok\"}";
        return true;
    }

    //========================================================================
    // Group C — subentity reads on the main path (no AcBr lib needed)
    //========================================================================
    if (op == "inspect.subentity.geom_extents" ||
        op == "inspect.subentity.class_id" ||
        op == "inspect.subentity.ptr" ||
        op == "inspect.subentity.color" ||
        op == "inspect.subentity.markers_at_path" ||
        op == "inspect.subentity.path_at_marker" ||
        op == "ui.subentity.highlight") {
        std::string handle;
        if (!m08dFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", op + " requires 'handle'");
            return true;
        }
        AcDbObjectId id;
        if (!resolveHandle(pDb, handle, id)) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "no entity for handle " + handle);
            return true;
        }
        // Build a face subentity path: index from "subent_index" (default 1, first marker).
        double idxRaw = 1.0;
        jsonFindNumber(job, "subent_index", idxRaw);
        const Adesk::GsMarker marker = static_cast<Adesk::GsMarker>(static_cast<long>(idxRaw));
        std::string subTypeStr = "face";
        jsonFindString(job, "subent_type", subTypeStr);
        AcDb::SubentType st = AcDb::kFaceSubentType;
        if (subTypeStr == "edge") st = AcDb::kEdgeSubentType;
        else if (subTypeStr == "vertex") st = AcDb::kVertexSubentType;
        AcDbFullSubentPath path(id, st, marker);

        AcDbEntity* pEnt = nullptr;
        if (acdbOpenObject(pEnt, id, AcDb::kForRead) != Acad::eOk) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "could not open entity " + handle);
            return true;
        }
        if (op == "inspect.subentity.geom_extents") {
            AcDbExtents ext;
            const Acad::ErrorStatus es = pEnt->getSubentPathGeomExtents(path, ext);
            std::ostringstream o;
            o << "\"subent_type\":\"" << subTypeStr << "\",\"marker\":" << static_cast<long>(marker)
              << ",\"extents_status\":" << static_cast<int>(es);
            if (es == Acad::eOk)
                o << ",\"min\":" << m08dPointJson(ext.minPoint())
                  << ",\"max\":" << m08dPointJson(ext.maxPoint());
            pEnt->close();
            r << "\"result\":{" << o.str() << ",\"has_extents\":"
              << (es == Acad::eOk ? "true" : "false") << "},\"status\":\"ok\"}";
            return true;
        }
        if (op == "inspect.subentity.class_id") {
            CLSID clsid;
            const Acad::ErrorStatus es = pEnt->getSubentClassId(path, &clsid);
            std::ostringstream o;
            o << "\"subent_type\":\"" << subTypeStr << "\",\"marker\":" << static_cast<long>(marker)
              << ",\"class_id_status\":" << static_cast<int>(es)
              << ",\"resolved\":" << (es == Acad::eOk ? "true" : "false");
            pEnt->close();
            r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
            return true;
        }
        // inspect.subentity.ptr — materialize transient subentity, report class + extents.
        if (op == "inspect.subentity.markers_at_path") {
            AcArray<Adesk::GsMarker> markers;
            const Acad::ErrorStatus es = pEnt->getGsMarkersAtSubentPath(path, markers);
            std::ostringstream o;
            o << "\"subent_type\":\"" << subTypeStr << "\",\"marker\":" << static_cast<long>(marker)
              << ",\"markers_status\":" << static_cast<int>(es)
              << ",\"marker_count\":" << markers.length()
              << ",\"markers\":[";
            for (int i = 0; i < markers.length(); ++i) {
                if (i) o << ",";
                o << static_cast<long>(markers[i]);
            }
            o << "]";
            pEnt->close();
            r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
            return true;
        }
        if (op == "inspect.subentity.path_at_marker") {
            AcGePoint3d pick(0.0, 0.0, 0.0);
            AcGeMatrix3d viewXform;
            viewXform.setToIdentity();
            int numPaths = 0;
            AcDbFullSubentPath* paths = nullptr;
            const Acad::ErrorStatus es = pEnt->getSubentPathsAtGsMarker(
                st, marker, pick, viewXform, numPaths, paths);
            if (paths != nullptr)
                delete[] paths;
            pEnt->close();
            r << "\"result\":{\"subent_type\":\"" << subTypeStr
              << "\",\"marker\":" << static_cast<long>(marker)
              << ",\"path_status\":" << static_cast<int>(es)
              << ",\"path_count\":" << numPaths
              << ",\"pick_point\":" << m08dPointJson(pick)
              << "},\"status\":\"ok\"}";
            return true;
        }
        if (op == "inspect.subentity.color") {
            AcCmColor color;
            Acad::ErrorStatus es = Acad::eNotApplicable;
            const char* supportedClass = "none";
            if (AcDb3dSolid::cast(pEnt) != nullptr) {
                supportedClass = "AcDb3dSolid";
                es = AcDb3dSolid::cast(pEnt)->getSubentColor(path.subentId(), color);
            } else if (AcDbSurface::cast(pEnt) != nullptr) {
                supportedClass = "AcDbSurface";
                es = AcDbSurface::cast(pEnt)->getSubentColor(path.subentId(), color);
            } else if (AcDbSubDMesh::cast(pEnt) != nullptr) {
                supportedClass = "AcDbSubDMesh";
                es = AcDbSubDMesh::cast(pEnt)->getSubentColor(path.subentId(), color);
            }
            pEnt->close();
            if (supportedClass == std::string("none")) {
                emitNativeError(r, "UNSUPPORTED_ENTITY",
                                "inspect.subentity.color requires AcDb3dSolid, AcDbSurface, or AcDbSubDMesh");
                return true;
            }
            r << "\"result\":{\"subent_type\":\"" << subTypeStr
              << "\",\"marker\":" << static_cast<long>(marker)
              << ",\"supported_class\":\"" << supportedClass << "\""
              << ",\"color_status\":" << static_cast<int>(es)
              << ",\"color_method\":" << static_cast<int>(color.colorMethod())
              << ",\"color_index\":" << static_cast<int>(color.colorIndex())
              << ",\"rgb\":[" << static_cast<int>(color.red())
              << "," << static_cast<int>(color.green())
              << "," << static_cast<int>(color.blue()) << "]"
              << "},\"status\":\"ok\"}";
            return true;
        }
        if (op == "ui.subentity.highlight") {
            double executeRaw = 0.0;
            jsonFindNumber(job, "execute", executeRaw);
            const bool execute = executeRaw != 0.0;
            double clearRaw = 0.0;
            jsonFindNumber(job, "clear", clearRaw);
            const bool clear = clearRaw != 0.0;
            double allRaw = 0.0;
            jsonFindNumber(job, "highlight_all", allRaw);
            const bool highlightAll = allRaw != 0.0;
            AcArray<Adesk::GsMarker> markers;
            const Acad::ErrorStatus markersEs = pEnt->getGsMarkersAtSubentPath(path, markers);
            const bool attended = ctx.hostMode == "full_autocad" && acedEditor != nullptr;
            Acad::ErrorStatus es = Acad::eNotApplicable;
            if (execute) {
                if (!attended) {
                    pEnt->close();
                    emitNativeError(r, "HOST_UNAVAILABLE",
                                    op + " requires a dedicated full AutoCAD editor host; host_mode=" +
                                    ctx.hostMode + "; subentity highlight needs a graphics device + display flush");
                    return true;
                }
                es = clear
                    ? pEnt->unhighlight(path, highlightAll ? Adesk::kTrue : Adesk::kFalse)
                    : pEnt->highlight(path, highlightAll ? Adesk::kTrue : Adesk::kFalse);
                if (es == Acad::eOk)
                    acedUpdateDisplay();
            }
            pEnt->close();
            r << "\"result\":{\"subent_type\":\"" << subTypeStr
              << "\",\"marker\":" << static_cast<long>(marker)
              << ",\"execute_requested\":" << (execute ? "true" : "false")
              << ",\"clear_requested\":" << (clear ? "true" : "false")
              << ",\"highlight_all\":" << (highlightAll ? "true" : "false")
              << ",\"host_mode\":" << njsonStr(ctx.hostMode)
              << ",\"attended_editor_required\":true"
              << ",\"attended_editor_present\":" << (attended ? "true" : "false")
              << ",\"markers_status\":" << static_cast<int>(markersEs)
              << ",\"marker_count\":" << markers.length()
              << ",\"highlight_status\":" << static_cast<int>(es)
              << ",\"display_flush\":" << (execute ? "true" : "false")
              << "},\"status\":\"ok\"}";
            return true;
        }
        AcDbEntity* pSub = pEnt->subentPtr(path);
        std::ostringstream o;
        o << "\"subent_type\":\"" << subTypeStr << "\",\"marker\":" << static_cast<long>(marker)
          << ",\"materialized\":" << (pSub != nullptr ? "true" : "false");
        if (pSub != nullptr) {
            o << ",\"sub_class\":" << njsonStr(pSub->isA() != nullptr ? pSub->isA()->name() : ACRX_T(""));
            AcDbExtents subExt;
            if (pSub->getGeomExtents(subExt) == Acad::eOk)
                o << ",\"min\":" << m08dPointJson(subExt.minPoint())
                  << ",\"max\":" << m08dPointJson(subExt.maxPoint());
            delete pSub;   // transient subentity is caller-owned (not DB-resident)
        }
        pEnt->close();
        r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
        return true;
    }

#ifdef ARIADNE_M08D_BREP
    //========================================================================
    // Group C — AcBr BRep topology (absolute-include + AcDrawBridge.lib)
    //========================================================================
    // All brep ops bind via a hex 'handle' to a 3dSolid/Surface/Region/Body.
    {
        // brep-binding ops share the handle bind; compute which family this op is.
        const bool isBrepOp =
            op.rfind("inspect.brep.", 0) == 0 || op.rfind("compute.brep.", 0) == 0 ||
            op.rfind("traverse.", 0) == 0 ||
            op.rfind("inspect.face.", 0) == 0 || op.rfind("inspect.edge.", 0) == 0 ||
            op.rfind("inspect.loop.", 0) == 0 || op.rfind("inspect.shell.", 0) == 0 ||
            op.rfind("inspect.vertex.", 0) == 0;
        if (isBrepOp) {
            std::string handle;
            if (!m08dFindHandle(job, handle)) {
                emitNativeError(r, "MISSING_ARG", op + " requires 'handle' (a 3dSolid/Surface/Region/Body)");
                return true;
            }
            AriadneReadTransaction rt(pDb);
            AcBrBrep brep;
            std::string className;
            const AcBr::ErrorStatus bes = m08dBindBrep(pDb, handle, brep, className);
            if (bes != AcBr::eOk) {
                std::ostringstream m;
                m << "AcBrBrep::set failed (AcBr status " << static_cast<int>(bes)
                  << ", class " << className << ")";
                emitNativeError(r, "BREP_BIND_FAILED", m.str());
                return true;
            }

            // ---- brep-level inspect/compute ----
            if (op == "inspect.brep.from_entity") {
                r << "\"result\":{\"bound\":true,\"source_class\":" << njsonStr(className)
                  << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "inspect.brep.validate") {
                const Adesk::Boolean ok = brep.checkEntity();
                r << "\"result\":{\"valid\":" << (ok == Adesk::kTrue ? "true" : "false")
                  << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "inspect.brep.changed") {
                const Adesk::Boolean changed = brep.brepChanged();
                r << "\"result\":{\"brep_changed\":" << (changed == Adesk::kTrue ? "true" : "false")
                  << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "inspect.brep.validation_level") {
                AcBr::ValidationLevel level = AcBr::kFullValidation;
                const AcBr::ErrorStatus es = brep.getValidationLevel(level);
                r << "\"result\":{\"validation_level\":"
                  << (level == AcBr::kNoValidation ? "\"no_validation\"" : "\"full_validation\"")
                  << ",\"status_code\":" << static_cast<int>(es) << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "inspect.brep.bounds") {
                AcGeBoundBlock3d block;
                const AcBr::ErrorStatus es = brep.getBoundBlock(block);
                std::ostringstream o;
                o << "\"bounds_status\":" << static_cast<int>(es);
                if (es == AcBr::eOk) {
                    AcGePoint3d lo, hi;
                    block.getMinMaxPoints(lo, hi);
                    o << ",\"min\":" << m08dPointJson(lo) << ",\"max\":" << m08dPointJson(hi);
                }
                r << "\"result\":{" << o.str() << ",\"has_bounds\":"
                  << (es == AcBr::eOk ? "true" : "false") << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "inspect.brep.owner") {
                AcBrBrep owner;
                const AcBr::ErrorStatus es = brep.getBrep(owner);
                r << "\"result\":{\"owner_status\":" << static_cast<int>(es)
                  << ",\"resolved\":" << (es == AcBr::eOk ? "true" : "false")
                  << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "inspect.brep.solid_roundtrip") {
                AcDb3dSolid* pSolid = nullptr;
                const AcBr::ErrorStatus es = brep.get(pSolid);
                std::ostringstream o;
                o << "\"roundtrip_status\":" << static_cast<int>(es)
                  << ",\"got_solid\":" << (es == AcBr::eOk && pSolid != nullptr ? "true" : "false");
                if (pSolid != nullptr) {
                    o << ",\"solid_class\":" << njsonStr(pSolid->isA() != nullptr ? pSolid->isA()->name() : ACRX_T(""));
                    delete pSolid;   // clone-out is caller-owned
                }
                r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "inspect.brep.from_subentpath") {
                // whole-brep null subentity path bind round-trip (re-set via path API).
                AcDbObjectId id;
                resolveHandle(pDb, handle, id);
                AcDbFullSubentPath whole(id, AcDb::kNullSubentType, 0);
                AcBrBrep viaPath;
                const AcBr::ErrorStatus es = viaPath.set(whole);
                r << "\"result\":{\"path_bind_status\":" << static_cast<int>(es)
                  << ",\"bound\":" << (es == AcBr::eOk ? "true" : "false")
                  << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "compute.brep.volume") {
                double vol = 0.0;
                const AcBr::ErrorStatus es = brep.getVolume(vol);
                r << "\"result\":{\"volume\":" << vol << ",\"status_code\":" << static_cast<int>(es)
                  << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "compute.brep.surface_area") {
                double area = 0.0;
                const AcBr::ErrorStatus es = brep.getSurfaceArea(area);
                r << "\"result\":{\"surface_area\":" << area << ",\"status_code\":" << static_cast<int>(es)
                  << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "compute.brep.perimeter") {
                double len = 0.0;
                const AcBr::ErrorStatus es = brep.getPerimeterLength(len);
                r << "\"result\":{\"perimeter\":" << len << ",\"status_code\":" << static_cast<int>(es)
                  << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "compute.brep.massprops") {
                AcBrMassProps mp;
                const AcBr::ErrorStatus es = brep.getMassProps(mp);
                std::ostringstream o;
                o << "\"massprops_status\":" << static_cast<int>(es);
                if (es == AcBr::eOk) {
                    o << ",\"volume\":" << mp.mVolume << ",\"mass\":" << mp.mMass
                      << ",\"centroid\":" << m08dPointJson(mp.mCentroid)
                      << ",\"radii_gyration\":[" << mp.mRadiiGyration[0] << "," << mp.mRadiiGyration[1]
                      << "," << mp.mRadiiGyration[2] << "]"
                      << ",\"principal_moments\":[" << mp.mPrinMoments[0] << "," << mp.mPrinMoments[1]
                      << "," << mp.mPrinMoments[2] << "]";
                }
                r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "compute.brep.point_containment") {
                double px, py, pz;
                if (!m08dFindNamedPoint(job, "point", px, py, pz)) {
                    emitNativeError(r, "MISSING_ARG", "compute.brep.point_containment requires 'point'");
                    return true;
                }
                const AcGePoint3d pt(px, py, pz);
                AcGe::PointContainment pc = AcGe::kOutside;
                AcBrEntity* pContainer = nullptr;
                const AcBr::ErrorStatus es = brep.getPointContainment(pt, pc, pContainer);
                const char* pcStr = (pc == AcGe::kInside) ? "inside"
                                    : (pc == AcGe::kOnBoundary) ? "on_boundary" : "outside";
                if (pContainer != nullptr)
                    delete pContainer;   // caller-owned per slice
                r << "\"result\":{\"point\":" << m08dPointJson(pt)
                  << ",\"containment\":\"" << pcStr << "\",\"status_code\":" << static_cast<int>(es)
                  << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "compute.brep.line_containment") {
                double ax, ay, az, bx, by, bz;
                if (!m08dFindNamedPoint(job, "a", ax, ay, az) ||
                    !m08dFindNamedPoint(job, "b", bx, by, bz)) {
                    emitNativeError(r, "MISSING_ARG", "compute.brep.line_containment requires line points 'a' and 'b'");
                    return true;
                }
                const AcGeLine3d line(AcGePoint3d(ax, ay, az), AcGePoint3d(bx, by, bz));
                AcBrHit* hits = nullptr;
                Adesk::UInt32 numFound = 0;
                const Adesk::UInt32 numWanted = 0;   // 0 => all
                const AcBr::ErrorStatus es = brep.getLineContainment(line, numWanted, numFound, hits);
                if (hits != nullptr)
                    delete[] hits;   // caller delete[]s per slice
                r << "\"result\":{\"hit_count\":" << numFound << ",\"status_code\":" << static_cast<int>(es)
                  << "},\"status\":\"ok\"}";
                return true;
            }

            // ---- brep-rooted traversal COUNTS ----
            if (op == "traverse.brep.complexes") {
                AcBrBrepComplexTraverser t;
                int n = 0;
                if (t.setBrep(brep) == AcBr::eOk)
                    for (; t.done() == Adesk::kFalse; t.next()) ++n;
                r << "\"result\":{\"complex_count\":" << n << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "traverse.brep.shells") {
                AcBrBrepShellTraverser t;
                int n = 0;
                if (t.setBrep(brep) == AcBr::eOk)
                    for (; t.done() == Adesk::kFalse; t.next()) ++n;
                r << "\"result\":{\"shell_count\":" << n << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "traverse.brep.faces") {
                AcBrBrepFaceTraverser t;
                int n = 0;
                if (t.setBrep(brep) == AcBr::eOk)
                    for (; t.done() == Adesk::kFalse; t.next()) ++n;
                r << "\"result\":{\"face_count\":" << n << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "traverse.brep.edges") {
                AcBrBrepEdgeTraverser t;
                int n = 0;
                if (t.setBrep(brep) == AcBr::eOk)
                    for (; t.done() == Adesk::kFalse; t.next()) ++n;
                r << "\"result\":{\"edge_count\":" << n << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "traverse.brep.vertices") {
                AcBrBrepVertexTraverser t;
                int n = 0;
                if (t.setBrep(brep) == AcBr::eOk)
                    for (; t.done() == Adesk::kFalse; t.next()) ++n;
                r << "\"result\":{\"vertex_count\":" << n << "},\"status\":\"ok\"}";
                return true;
            }

            // ---- hierarchical traversal COUNTS (bind first parent of the right kind) ----
            if (op == "traverse.complex.shells") {
                AcBrBrepComplexTraverser bt;
                int n = 0; bool got = false;
                if (bt.setBrep(brep) == AcBr::eOk && bt.done() == Adesk::kFalse) {
                    AcBrComplex complex;
                    if (bt.getComplex(complex) == AcBr::eOk) {
                        got = true;
                        AcBrComplexShellTraverser st;
                        if (st.setComplex(complex) == AcBr::eOk)
                            for (; st.done() == Adesk::kFalse; st.next()) ++n;
                    }
                }
                r << "\"result\":{\"shell_count\":" << n << ",\"complex_bound\":"
                  << (got ? "true" : "false") << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "traverse.shell.faces") {
                AcBrBrepShellTraverser bt;
                int n = 0; bool got = false;
                if (bt.setBrep(brep) == AcBr::eOk && bt.done() == Adesk::kFalse) {
                    AcBrShell shell;
                    if (bt.getShell(shell) == AcBr::eOk) {
                        got = true;
                        AcBrShellFaceTraverser ft;
                        if (ft.setShell(shell) == AcBr::eOk)
                            for (; ft.done() == Adesk::kFalse; ft.next()) ++n;
                    }
                }
                r << "\"result\":{\"face_count\":" << n << ",\"shell_bound\":"
                  << (got ? "true" : "false") << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "traverse.face.loops") {
                AcBrBrepFaceTraverser bt;
                int n = 0; bool got = false;
                if (bt.setBrep(brep) == AcBr::eOk && bt.done() == Adesk::kFalse) {
                    AcBrFace face;
                    if (bt.getFace(face) == AcBr::eOk) {
                        got = true;
                        AcBrFaceLoopTraverser lt;
                        if (lt.setFace(face) == AcBr::eOk)
                            for (; lt.done() == Adesk::kFalse; lt.next()) ++n;
                    }
                }
                r << "\"result\":{\"loop_count\":" << n << ",\"face_bound\":"
                  << (got ? "true" : "false") << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "traverse.loop.edges") {
                AcBrBrepFaceTraverser bt;
                int n = 0; bool got = false;
                if (bt.setBrep(brep) == AcBr::eOk && bt.done() == Adesk::kFalse) {
                    AcBrFace face;
                    if (bt.getFace(face) == AcBr::eOk) {
                        AcBrFaceLoopTraverser lt;
                        if (lt.setFace(face) == AcBr::eOk && lt.done() == Adesk::kFalse) {
                            AcBrLoop loop;
                            if (lt.getLoop(loop) == AcBr::eOk) {
                                got = true;
                                AcBrLoopEdgeTraverser et;
                                if (et.setLoop(loop) == AcBr::eOk)
                                    for (; et.done() == Adesk::kFalse; et.next()) ++n;
                            }
                        }
                    }
                }
                r << "\"result\":{\"edge_count\":" << n << ",\"loop_bound\":"
                  << (got ? "true" : "false") << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "traverse.loop.vertices") {
                AcBrBrepFaceTraverser bt;
                int n = 0; bool got = false;
                if (bt.setBrep(brep) == AcBr::eOk && bt.done() == Adesk::kFalse) {
                    AcBrFace face;
                    if (bt.getFace(face) == AcBr::eOk) {
                        AcBrFaceLoopTraverser lt;
                        if (lt.setFace(face) == AcBr::eOk && lt.done() == Adesk::kFalse) {
                            AcBrLoop loop;
                            if (lt.getLoop(loop) == AcBr::eOk) {
                                got = true;
                                AcBrLoopVertexTraverser vt;
                                if (vt.setLoop(loop) == AcBr::eOk)
                                    for (; vt.done() == Adesk::kFalse; vt.next()) ++n;
                            }
                        }
                    }
                }
                r << "\"result\":{\"vertex_count\":" << n << ",\"loop_bound\":"
                  << (got ? "true" : "false") << ",\"note\":\"loop-vertex applies to singularity loops\"},\"status\":\"ok\"}";
                return true;
            }
            if (op == "traverse.edge.loops") {
                AcBrBrepEdgeTraverser bt;
                int n = 0; bool got = false;
                if (bt.setBrep(brep) == AcBr::eOk && bt.done() == Adesk::kFalse) {
                    AcBrEdge edge;
                    if (bt.getEdge(edge) == AcBr::eOk) {
                        got = true;
                        AcBrEdgeLoopTraverser lt;
                        if (lt.setEdge(edge) == AcBr::eOk)
                            for (; lt.done() == Adesk::kFalse; lt.next()) ++n;
                    }
                }
                r << "\"result\":{\"loop_count\":" << n << ",\"edge_bound\":"
                  << (got ? "true" : "false") << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "traverse.vertex.edges") {
                AcBrBrepVertexTraverser bt;
                int n = 0; bool got = false;
                if (bt.setBrep(brep) == AcBr::eOk && bt.done() == Adesk::kFalse) {
                    AcBrVertex vertex;
                    if (bt.getVertex(vertex) == AcBr::eOk) {
                        got = true;
                        AcBrVertexEdgeTraverser et;
                        if (et.setVertex(vertex) == AcBr::eOk)
                            for (; et.done() == Adesk::kFalse; et.next()) ++n;
                    }
                }
                r << "\"result\":{\"edge_count\":" << n << ",\"vertex_bound\":"
                  << (got ? "true" : "false") << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "traverse.vertex.loops") {
                AcBrBrepVertexTraverser bt;
                int n = 0; bool got = false;
                if (bt.setBrep(brep) == AcBr::eOk && bt.done() == Adesk::kFalse) {
                    AcBrVertex vertex;
                    if (bt.getVertex(vertex) == AcBr::eOk) {
                        got = true;
                        AcBrVertexLoopTraverser lt;
                        if (lt.setVertex(vertex) == AcBr::eOk)
                            for (; lt.done() == Adesk::kFalse; lt.next()) ++n;
                    }
                }
                r << "\"result\":{\"loop_count\":" << n << ",\"vertex_bound\":"
                  << (got ? "true" : "false") << "},\"status\":\"ok\"}";
                return true;
            }

            // ---- per-element inspect (bind FIRST element of that kind) ----
            if (op == "inspect.shell.type" || op == "inspect.shell.complex") {
                AcBrBrepShellTraverser bt;
                AcBrShell shell; bool got = false;
                if (bt.setBrep(brep) == AcBr::eOk && bt.done() == Adesk::kFalse)
                    got = (bt.getShell(shell) == AcBr::eOk);
                if (!got) { emitNativeError(r, "NO_SUBELEMENT", "brep has no shell to inspect"); return true; }
                if (op == "inspect.shell.type") {
                    AcBr::ShellType t = AcBr::kShellUnclassified;
                    const AcBr::ErrorStatus es = shell.getType(t);
                    r << "\"result\":{\"index\":0,\"shell_type\":\"" << m08dShellTypeKind(t)
                      << "\",\"status_code\":" << static_cast<int>(es) << "},\"status\":\"ok\"}";
                } else {
                    AcBrComplex complex;
                    const AcBr::ErrorStatus es = shell.getComplex(complex);
                    r << "\"result\":{\"index\":0,\"complex_resolved\":"
                      << (es == AcBr::eOk ? "true" : "false") << ",\"status_code\":"
                      << static_cast<int>(es) << "},\"status\":\"ok\"}";
                }
                return true;
            }
            if (op == "inspect.face.area" || op == "inspect.face.orientation" ||
                op == "inspect.face.shell" || op == "inspect.face.surface" ||
                op == "inspect.face.surface_type" || op == "inspect.face.surface_as_nurb" ||
                op == "inspect.face.surface_as_trimmed_nurbs") {
                AcBrBrepFaceTraverser bt;
                AcBrFace face; bool got = false;
                if (bt.setBrep(brep) == AcBr::eOk && bt.done() == Adesk::kFalse)
                    got = (bt.getFace(face) == AcBr::eOk);
                if (!got) { emitNativeError(r, "NO_SUBELEMENT", "brep has no face to inspect"); return true; }
                if (op == "inspect.face.area") {
                    double area = 0.0;
                    const AcBr::ErrorStatus es = face.getArea(area);
                    r << "\"result\":{\"index\":0,\"area\":" << area << ",\"status_code\":"
                      << static_cast<int>(es) << "},\"status\":\"ok\"}";
                } else if (op == "inspect.face.orientation") {
                    Adesk::Boolean orient = Adesk::kTrue;
                    const AcBr::ErrorStatus es = face.getOrientToSurface(orient);
                    r << "\"result\":{\"index\":0,\"orient_to_surface\":"
                      << (orient == Adesk::kTrue ? "true" : "false") << ",\"status_code\":"
                      << static_cast<int>(es) << "},\"status\":\"ok\"}";
                } else if (op == "inspect.face.shell") {
                    AcBrShell shell;
                    const AcBr::ErrorStatus es = face.getShell(shell);
                    r << "\"result\":{\"index\":0,\"shell_resolved\":"
                      << (es == AcBr::eOk ? "true" : "false") << ",\"status_code\":"
                      << static_cast<int>(es) << "},\"status\":\"ok\"}";
                } else if (op == "inspect.face.surface_type") {
                    AcGe::EntityId kind = AcGe::kEntity3d;
                    const AcBr::ErrorStatus es = face.getSurfaceType(kind);
                    r << "\"result\":{\"index\":0,\"surface_kind\":\"" << m08dGeEntityKind(kind)
                      << "\",\"status_code\":" << static_cast<int>(es) << "},\"status\":\"ok\"}";
                } else if (op == "inspect.face.surface") {
                    AcGeSurface* pSurf = nullptr;
                    const AcBr::ErrorStatus es = face.getSurface(pSurf);
                    std::ostringstream o;
                    o << "\"index\":0,\"surface_status\":" << static_cast<int>(es)
                      << ",\"got_surface\":" << (es == AcBr::eOk && pSurf != nullptr ? "true" : "false");
                    if (pSurf != nullptr) {
                        o << ",\"surface_kind\":\"" << m08dGeEntityKind(pSurf->type()) << "\"";
                        delete pSurf;   // caller-owned
                    }
                    r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
                } else if (op == "inspect.face.surface_as_nurb") {
                    AcGeNurbSurface nurb;
                    const AcBr::ErrorStatus es = face.getSurfaceAsNurb(nurb);
                    r << "\"result\":{\"index\":0,\"as_nurb_status\":" << static_cast<int>(es)
                      << ",\"converted\":" << (es == AcBr::eOk ? "true" : "false")
                      << "},\"status\":\"ok\"}";
                } else { // inspect.face.surface_as_trimmed_nurbs
                    Adesk::UInt32 count = 0;
                    AcGeExternalBoundedSurface** patches = nullptr;
                    const AcBr::ErrorStatus es = face.getSurfaceAsTrimmedNurbs(count, patches);
                    if (patches != nullptr) {
                        for (Adesk::UInt32 i = 0; i < count; ++i) delete patches[i];
                        delete[] patches;   // caller delete[]s per slice
                    }
                    r << "\"result\":{\"index\":0,\"patch_count\":" << count << ",\"status_code\":"
                      << static_cast<int>(es) << "},\"status\":\"ok\"}";
                }
                return true;
            }
            if (op == "inspect.edge.curve" || op == "inspect.edge.curve_type" ||
                op == "inspect.edge.curve_as_nurb" || op == "inspect.edge.orientation" ||
                op == "inspect.edge.vertices") {
                AcBrBrepEdgeTraverser bt;
                AcBrEdge edge; bool got = false;
                if (bt.setBrep(brep) == AcBr::eOk && bt.done() == Adesk::kFalse)
                    got = (bt.getEdge(edge) == AcBr::eOk);
                if (!got) { emitNativeError(r, "NO_SUBELEMENT", "brep has no edge to inspect"); return true; }
                if (op == "inspect.edge.curve") {
                    AcGeCurve3d* pCurve = nullptr;
                    const AcBr::ErrorStatus es = edge.getCurve(pCurve);
                    std::ostringstream o;
                    o << "\"index\":0,\"curve_status\":" << static_cast<int>(es)
                      << ",\"got_curve\":" << (es == AcBr::eOk && pCurve != nullptr ? "true" : "false");
                    if (pCurve != nullptr) {
                        o << ",\"curve_kind\":\"" << m08dGeEntityKind(pCurve->type()) << "\"";
                        delete pCurve;   // caller-owned
                    }
                    r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
                } else if (op == "inspect.edge.curve_type") {
                    AcGe::EntityId kind = AcGe::kEntity3d;
                    const AcBr::ErrorStatus es = edge.getCurveType(kind);
                    r << "\"result\":{\"index\":0,\"curve_kind\":\"" << m08dGeEntityKind(kind)
                      << "\",\"status_code\":" << static_cast<int>(es) << "},\"status\":\"ok\"}";
                } else if (op == "inspect.edge.curve_as_nurb") {
                    AcGeNurbCurve3d nurb;
                    const AcBr::ErrorStatus es = edge.getCurveAsNurb(nurb);
                    r << "\"result\":{\"index\":0,\"as_nurb_status\":" << static_cast<int>(es)
                      << ",\"converted\":" << (es == AcBr::eOk ? "true" : "false")
                      << "},\"status\":\"ok\"}";
                } else if (op == "inspect.edge.orientation") {
                    Adesk::Boolean orient = Adesk::kTrue;
                    const AcBr::ErrorStatus es = edge.getOrientToCurve(orient);
                    r << "\"result\":{\"index\":0,\"orient_to_curve\":"
                      << (orient == Adesk::kTrue ? "true" : "false") << ",\"status_code\":"
                      << static_cast<int>(es) << "},\"status\":\"ok\"}";
                } else { // inspect.edge.vertices
                    AcBrVertex v1, v2;
                    const AcBr::ErrorStatus es1 = edge.getVertex1(v1);
                    const AcBr::ErrorStatus es2 = edge.getVertex2(v2);
                    std::ostringstream o;
                    o << "\"index\":0,\"vertex1_status\":" << static_cast<int>(es1)
                      << ",\"vertex2_status\":" << static_cast<int>(es2);
                    AcGePoint3d p1, p2;
                    if (es1 == AcBr::eOk && v1.getPoint(p1) == AcBr::eOk)
                        o << ",\"vertex1\":" << m08dPointJson(p1);
                    if (es2 == AcBr::eOk && v2.getPoint(p2) == AcBr::eOk)
                        o << ",\"vertex2\":" << m08dPointJson(p2);
                    r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
                }
                return true;
            }
            if (op == "inspect.vertex.point") {
                AcBrBrepVertexTraverser bt;
                AcBrVertex vertex; bool got = false;
                if (bt.setBrep(brep) == AcBr::eOk && bt.done() == Adesk::kFalse)
                    got = (bt.getVertex(vertex) == AcBr::eOk);
                if (!got) { emitNativeError(r, "NO_SUBELEMENT", "brep has no vertex to inspect"); return true; }
                AcGePoint3d p;
                const AcBr::ErrorStatus es = vertex.getPoint(p);
                std::ostringstream o;
                o << "\"index\":0,\"point_status\":" << static_cast<int>(es);
                if (es == AcBr::eOk) o << ",\"point\":" << m08dPointJson(p);
                r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
                return true;
            }
            if (op == "inspect.loop.type" || op == "inspect.loop.face") {
                // first loop of the first face
                AcBrBrepFaceTraverser bt;
                AcBrFace face; AcBrLoop loop; bool got = false;
                if (bt.setBrep(brep) == AcBr::eOk && bt.done() == Adesk::kFalse &&
                    bt.getFace(face) == AcBr::eOk) {
                    AcBrFaceLoopTraverser lt;
                    if (lt.setFace(face) == AcBr::eOk && lt.done() == Adesk::kFalse)
                        got = (lt.getLoop(loop) == AcBr::eOk);
                }
                if (!got) { emitNativeError(r, "NO_SUBELEMENT", "brep has no loop to inspect"); return true; }
                if (op == "inspect.loop.type") {
                    AcBr::LoopType t = AcBr::kLoopUnclassified;
                    const AcBr::ErrorStatus es = loop.getType(t);
                    r << "\"result\":{\"index\":0,\"loop_type\":\"" << m08dLoopTypeKind(t)
                      << "\",\"status_code\":" << static_cast<int>(es) << "},\"status\":\"ok\"}";
                } else {
                    AcBrFace owner;
                    const AcBr::ErrorStatus es = loop.getFace(owner);
                    r << "\"result\":{\"index\":0,\"face_resolved\":"
                      << (es == AcBr::eOk ? "true" : "false") << ",\"status_code\":"
                      << static_cast<int>(es) << "},\"status\":\"ok\"}";
                }
                return true;
            }
        }
    }
#endif // ARIADNE_M08D_BREP

    // Admitted by HasOp but not routed above => surface the drift (never silent).
    emitNativeError(r, "OPERATION_DISPATCH_MISMATCH",
                    "operation '" + op + "' admitted by m08dHasOp but not handled in m08dDispatch");
    return true;
}
