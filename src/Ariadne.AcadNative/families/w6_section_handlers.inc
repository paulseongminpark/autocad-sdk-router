// families/w6_section_handlers.inc — W6-SECTION family: AcDbSection read + create
// (CADOS wave 6, census P2 — section objects had ZERO catalog/registry coverage
// despite brep_solids being the strongest family; R3_coverage.md finding G0 /
// tools/catalog_completeness.py's KNOWN_UNCATALOGUED_DISPOSITIONS seeded
// ("section", "author", "AcDbSection/AcDbSectionSettings -- R3 G0: 0 ops.")).
//
// Owned by the W6-SECTION teammate (worktree-scoped, parallel with the other
// wave-6 family lanes). #included into AriadneNativeJob.cpp; sees every in-TU
// helper (njsonStr / point3Json / jsonFind* / handleOf(Id) / ensureLayer /
// countModelSpace / emitNativeError / AriadneJobCtx), same contract as the
// M08x families (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - w6sectionHasOp(op): true for every op id this family IMPLEMENTS (gate
//     admission). Ops left out keep returning the honest OPERATION_NOT_IMPLEMENTED.
//   - w6sectionDispatch(op, ctx, r): if op is yours, append "result":{...},
//     "status":"ok" (or an emitNativeError-style error) to r and return true;
//     else return false.
//
// SAFETY (hard): staged-write ONLY. Operate on ctx.pDb (the router-staged
//   in-memory copy). Never call save()/saveAs() on the original. No
//   acedCommand/acedCmd (compile-disabled in 2027). Original DWG bytes must
//   stay unchanged. We only appendAcDbEntity into the staged model space.
//
// IMPLEMENTED (3): inspect.section.objects (read: enumerate AcDbSection
//   entities in model space), write.entity.section (create: AcDbSection
//   plane/boundary/volume via the (pts, verticalDir[, viewingDir]) ctor),
//   write.section.generate2d (measurement op: transient AcDb3dSolid box +
//   transient AcDbSection -> generateSectionGeometry(); live-verified headless
//   under accoreconsole -- see the dispatch branch's own comment).
//
// Class provenance: AcDbSection/AcDbSectionSettings/AcDbSectionManager are
// declared via GEOMENT_DECLARE_MEMBERS (DbSection.h -- the same boiler macro
// AcDbBody uses, dbboiler.h), exported straight from acdb26.lib. Unlike
// AcDbHatch's area engine or AcDbRasterImage/AcDbMPolygon (m08g's wA-cert
// demand-loaded engine modules), there is no separate Section*.lib/.dbx on
// this SDK install (checked: only AcDbPointCloudObj.lib/acismobj26.lib/
// AcMPolygonObj.lib exist alongside acdb26.lib) — so no extra
// #pragma comment(lib,...) or m08gLoadEngineModule()-style force-load is
// expected to be needed here.
//
// Strings: entity content -> utf8ToWide() for setName (lossless UTF-8 ->
//   UTF-16); JSON output -> njsonStr (UTF-8, including the njsonStr(const
//   ACHAR*) overload for AcDbSection::getName()'s raw ACHAR* return).

#include "DbSection.h"    // AcDbSection / AcDbSectionSettings (State/SubItem/Height enums)
#include "gevec3d.h"      // AcGeVector3d (verticalDir / viewingDir / normal)
#include "dbsol3d.h"      // AcDb3dSolid::createBox (transient sectionable probe entity,
                          // write.section.generate2d measurement -- families/m08g_handlers.inc's
                          // own #include is textually BEFORE this file in the TU, but this file
                          // re-includes defensively per the sibling families' own convention)

//============================================================================
// W6-SECTION local helpers (family-private; complement the in-TU jsonFind*/
// point3Json). Mirrors m08hReadPointArray3d / m08gReadPointArray exactly (each
// family keeps its own copy so parallel teammates never touch a shared file).
//============================================================================

// Parse a JSON array of point objects ("key":[{x,y,z},...]) into an
// AcGePoint3dArray. Returns the number of points appended.
static int w6sectionReadPointArray(const std::string& job, const char* key, AcGePoint3dArray& out)
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

// "points" with a "vertices" fallback -- same dual-key convention m08g's
// write.entity.* creators use (points primary, vertices accepted too).
static int w6sectionReadPoints(const std::string& job, AcGePoint3dArray& out)
{
    int n = w6sectionReadPointArray(job, "points", out);
    if (n < 2)
        n = w6sectionReadPointArray(job, "vertices", out);
    return n;
}

// Read a vector ("key":{x,y,z}) with a default when absent/partial.
static AcGeVector3d w6sectionReadVector(const std::string& job, const char* key,
                                        double dx, double dy, double dz)
{
    double x = dx, y = dy, z = dz;
    jsonFindPoint3(job, key, x, y, z);
    return AcGeVector3d(x, y, z);
}

static const char* w6sectionStateName(AcDbSection::State st)
{
    switch (st) {
        case AcDbSection::kPlane:    return "plane";
        case AcDbSection::kBoundary: return "boundary";
        case AcDbSection::kVolume:   return "volume";
        default:                     return "unknown";
    }
}

static AcDbSection::State w6sectionStateFromName(const std::string& s, AcDbSection::State def)
{
    if (s == "boundary") return AcDbSection::kBoundary;
    if (s == "volume")   return AcDbSection::kVolume;
    if (s == "plane")    return AcDbSection::kPlane;
    return def;
}

// Open model space kForWrite (the staged copy). Returns eOk + sets pMS (caller closes it).
static Acad::ErrorStatus w6sectionOpenModelSpace(AcDbDatabase* pDb, AcDbBlockTableRecord*& pMS)
{
    pMS = nullptr;
    AcDbBlockTable* pBT = nullptr;
    Acad::ErrorStatus es = pDb->getBlockTable(pBT, AcDb::kForRead);
    if (es != Acad::eOk)
        return es;
    es = pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite);
    pBT->close();
    return es;
}

// Append a freshly-new'd entity into the staged model space, honoring an
// optional layer. Takes ownership of pE: on success closes it (sets outId);
// on failure deletes it. Returns the append errorstatus (eOk == created).
static Acad::ErrorStatus w6sectionAppend(AcDbDatabase* pDb, const std::string& layer,
                                         AcDbEntity* pE, AcDbObjectId& outId)
{
    outId = AcDbObjectId::kNull;
    if (!layer.empty()) {
        bool created = false;
        Acad::ErrorStatus layerEs = ensureLayer(pDb, layer, 7, created);
        if (layerEs != Acad::eOk) {
            delete pE;
            return layerEs;
        }
        pE->setLayer(asciiToWide(layer).c_str());
    }
    AcDbBlockTableRecord* pMS = nullptr;
    Acad::ErrorStatus es = w6sectionOpenModelSpace(pDb, pMS);
    if (es != Acad::eOk) {
        delete pE;
        return es;
    }
    es = pMS->appendAcDbEntity(outId, pE);
    pMS->close();
    if (es == Acad::eOk)
        pE->close();
    else
        delete pE;
    return es;
}

// Serialize one open-for-read AcDbSection entity's full state (name, state,
// vertices, elevation/top/bottom plane, normal/vertical/viewing direction,
// live-section flag, linked AcDbSectionSettings presence) into a JSON object
// (no enclosing braces -- caller wraps).
static std::string w6sectionSerialize(AcDbSection* pSec)
{
    std::ostringstream o; o.precision(kJsonDoublePrecision);
    o << "\"handle\":" << njsonStr(handleOf(pSec));
    o << ",\"name\":" << njsonStr(pSec->getName());
    o << ",\"state\":" << njsonStr(std::string(w6sectionStateName(pSec->state())));
    o << ",\"is_slice\":" << (pSec->isSlice() ? "true" : "false");

    AcGePoint3dArray pts;
    pSec->getVertices(pts);
    o << ",\"num_vertices\":" << static_cast<int>(pts.length());
    o << ",\"vertices\":[";
    for (int i = 0; i < pts.length(); ++i) {
        if (i > 0) o << ",";
        o << point3Json(pts[i].x, pts[i].y, pts[i].z);
    }
    o << "]";

    o << ",\"elevation\":" << pSec->elevation();
    o << ",\"top_plane\":" << pSec->topPlane();
    o << ",\"bottom_plane\":" << pSec->bottomPlane();
    o << ",\"height_above\":" << pSec->height(AcDbSection::kHeightAboveSectionLine);
    o << ",\"height_below\":" << pSec->height(AcDbSection::kHeightBelowSectionLine);

    const AcGeVector3d normal = pSec->normal();
    o << ",\"normal\":" << point3Json(normal.x, normal.y, normal.z);
    const AcGeVector3d vdir = pSec->verticalDirection();
    o << ",\"vertical_direction\":" << point3Json(vdir.x, vdir.y, vdir.z);
    const AcGeVector3d wdir = pSec->viewingDirection();
    o << ",\"viewing_direction\":" << point3Json(wdir.x, wdir.y, wdir.z);

    o << ",\"has_jogs\":" << (pSec->hasJogs() ? "true" : "false");
    o << ",\"thickness_depth\":" << pSec->thicknessDepth();
    o << ",\"section_plane_offset\":" << pSec->sectionPlaneOffset();
    o << ",\"indicator_transparency\":" << pSec->indicatorTransparency();
    o << ",\"live_section_enabled\":" << (pSec->isLiveSectionEnabled() ? "true" : "false");

    // AcDbSectionSettings summary: presence + handle only (the settings object
    // carries ~10 per-generation-type flag groups -- out of scope for this
    // read op's "summary"; the handle lets a caller inspect.object.generic it).
    const AcDbObjectId settingsId = pSec->getSettings();
    const bool hasSettings = !settingsId.isNull();
    o << ",\"settings\":{\"present\":" << (hasSettings ? "true" : "false")
      << ",\"handle\":" << njsonStr(hasSettings ? handleOfId(settingsId) : std::string())
      << "}";
    return o.str();
}

//============================================================================
// HasOp / Dispatch
//============================================================================
static bool w6sectionHasOp(const std::string& op)
{
    return op == "inspect.section.objects"
        || op == "write.entity.section"
        || op == "write.section.generate2d";
}

static bool w6sectionDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    if (!w6sectionHasOp(op))
        return false;
    AcDbDatabase* pDb = ctx.pDb;
    if (pDb == nullptr) {
        emitNativeError(r, "DB_ERROR", "null database");
        return true;
    }
    const std::string& job = ctx.job;

    // ---- inspect.section.objects: enumerate AcDbSection entities ---------
    if (op == "inspect.section.objects") {
        AcDbBlockTable* pBT = nullptr;
        if (pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk) {
            emitNativeError(r, "DB_ERROR", "getBlockTable failed");
            return true;
        }
        AcDbBlockTableRecord* pMS = nullptr;
        if (pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForRead) != Acad::eOk) {
            pBT->close();
            emitNativeError(r, "DB_ERROR", "model space open failed");
            return true;
        }
        pBT->close();

        AcDbBlockTableRecordIterator* pIt = nullptr;
        if (pMS->newIterator(pIt) != Acad::eOk) {
            pMS->close();
            emitNativeError(r, "DB_ERROR", "model space iterator failed");
            return true;
        }
        std::ostringstream items;
        int count = 0;
        for (pIt->start(); !pIt->done(); pIt->step()) {
            AcDbEntity* pEnt = nullptr;
            if (pIt->getEntity(pEnt, AcDb::kForRead) != Acad::eOk || pEnt == nullptr)
                continue;
            AcDbSection* pSec = AcDbSection::cast(pEnt);
            if (pSec != nullptr) {
                if (count > 0) items << ",";
                items << "{" << w6sectionSerialize(pSec) << "}";
                ++count;
            }
            pEnt->close();
        }
        delete pIt;
        pMS->close();

        r << "\"result\":{\"count\":" << count
          << ",\"scope\":\"model_space\""
          << ",\"sections\":[" << items.str() << "]},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // ---- write.entity.section: create an AcDbSection plane/boundary/volume -
    if (op == "write.entity.section") {
        std::string layer; jsonFindString(job, "layer", layer);
        std::string name;  jsonFindString(job, "name", name);
        std::string stateStr; jsonFindString(job, "state", stateStr);

        AcGePoint3dArray pts;
        if (w6sectionReadPoints(job, pts) < 2) {
            emitNativeError(r, "MISSING_ARG",
                "write.entity.section needs a points/vertices array with >=2 {x,y,z} points");
            return true;
        }
        // Default verticalDir: Z-up (the common case: a horizontal section
        // line with a vertical cut plane). Callers slicing a non-Z-up model
        // must supply vertical_dir explicitly.
        const AcGeVector3d verticalDir = w6sectionReadVector(job, "vertical_dir", 0.0, 0.0, 1.0);

        std::string viewingObj;
        const bool hasViewingDir = jsonFindObject(job, "viewing_dir", viewingObj);
        AcDbSection* pE = hasViewingDir
            ? new AcDbSection(pts, verticalDir, w6sectionReadVector(job, "viewing_dir", 0.0, 0.0, 1.0))
            : new AcDbSection(pts, verticalDir);

        if (!name.empty()) {
            const Acad::ErrorStatus nameEs = pE->setName(utf8ToWide(name).c_str());
            if (nameEs != Acad::eOk) {
                delete pE;
                emitNativeError(r, "INVALID_ARG",
                    "AcDbSection::setName failed es=" + std::to_string(static_cast<int>(nameEs))
                    + " (blank or non-unique name, or contains '|')");
                return true;
            }
        }
        if (!stateStr.empty()) {
            const AcDbSection::State st = w6sectionStateFromName(stateStr, AcDbSection::kPlane);
            pE->setState(st);
        }

        AcDbObjectId id;
        const Acad::ErrorStatus es = w6sectionAppend(pDb, layer, pE, id);
        if (es != Acad::eOk) {
            emitNativeError(r, "APPEND_FAILED",
                "AcDbSection append es=" + std::to_string(static_cast<int>(es)));
            return true;
        }

        int probes = 0, after = 0;
        countModelSpace(pDb, after, probes);
        r << "\"result\":{\"created\":true"
          << ",\"class\":\"AcDbSection\""
          << ",\"handle\":" << njsonStr(handleOfId(id))
          << ",\"layer\":" << njsonStr(layer)
          << ",\"name\":" << njsonStr(name)
          << ",\"state\":" << njsonStr(stateStr.empty() ? std::string("plane") : stateStr)
          << ",\"num_vertices\":" << static_cast<int>(pts.length())
          << ",\"modelspace_entities_after\":" << after << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // ---- write.section.generate2d: transient AcDb3dSolid + AcDbSection probe -
    // Measurement op (see the module header comment): builds a transient
    // (non-database-resident) AcDb3dSolid box and a transient AcDbSection
    // bisecting it, calls generateSectionGeometry, and reports the 5 output
    // array lengths + errorstatus. Neither transient object is ever appended
    // to ctx.pDb -- pure in-memory geometry probe, no staged-DB mutation.
    if (op == "write.section.generate2d") {
        double xLen = 100.0, yLen = 100.0, zLen = 100.0;
        jsonFindNumber(job, "x_len", xLen);
        jsonFindNumber(job, "y_len", yLen);
        jsonFindNumber(job, "z_len", zLen);

        AcDb3dSolid* pSolid = new AcDb3dSolid();
        const Acad::ErrorStatus boxEs = pSolid->createBox(xLen, yLen, zLen);
        if (boxEs != Acad::eOk) {
            delete pSolid;
            emitNativeError(r, "CREATE_BOX_FAILED",
                "AcDb3dSolid::createBox es=" + std::to_string(static_cast<int>(boxEs)));
            return true;
        }

        // Section line through the origin along Y, verticalDir=Z -> plane x=0,
        // bisecting a box centered at the origin (createBox's own convention).
        AcGePoint3dArray secPts;
        secPts.append(AcGePoint3d(0.0, -(yLen + 100.0), 0.0));
        secPts.append(AcGePoint3d(0.0, (yLen + 100.0), 0.0));
        AcDbSection* pSection = new AcDbSection(secPts, AcGeVector3d(0.0, 0.0, 1.0));

        AcArray<AcDbEntity*> intBoundaryEnts, intFillEnts, backgroundEnts,
                              foregroundEnts, curveTangencyEnts;
        const Acad::ErrorStatus genEs = pSection->generateSectionGeometry(
            pSolid, intBoundaryEnts, intFillEnts, backgroundEnts,
            foregroundEnts, curveTangencyEnts);

        const int nBoundary = static_cast<int>(intBoundaryEnts.length());
        const int nFill = static_cast<int>(intFillEnts.length());
        const int nBackground = static_cast<int>(backgroundEnts.length());
        const int nForeground = static_cast<int>(foregroundEnts.length());
        const int nTangency = static_cast<int>(curveTangencyEnts.length());

        for (int i = 0; i < intBoundaryEnts.length(); ++i) delete intBoundaryEnts[i];
        for (int i = 0; i < intFillEnts.length(); ++i) delete intFillEnts[i];
        for (int i = 0; i < backgroundEnts.length(); ++i) delete backgroundEnts[i];
        for (int i = 0; i < foregroundEnts.length(); ++i) delete foregroundEnts[i];
        for (int i = 0; i < curveTangencyEnts.length(); ++i) delete curveTangencyEnts[i];
        delete pSection;
        delete pSolid;

        if (genEs != Acad::eOk) {
            emitNativeError(r, "GENERATE_FAILED",
                "AcDbSection::generateSectionGeometry es=" + std::to_string(static_cast<int>(genEs))
                + " (probe box " + std::to_string(xLen) + "x" + std::to_string(yLen)
                + "x" + std::to_string(zLen) + ")");
            return true;
        }

        r << "\"result\":{\"generated\":true"
          << ",\"intersection_boundary_count\":" << nBoundary
          << ",\"intersection_fill_count\":" << nFill
          << ",\"background_count\":" << nBackground
          << ",\"foreground_count\":" << nForeground
          << ",\"curve_tangency_count\":" << nTangency << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // HasOp admitted an op with no dispatch branch -> coherent-seam guard (no silent fall-through).
    emitNativeError(r, "OPERATION_DISPATCH_MISMATCH", "w6sectionHasOp admitted op with no handler: " + op);
    return true;
}
