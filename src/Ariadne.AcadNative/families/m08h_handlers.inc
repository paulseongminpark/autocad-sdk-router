// families/m08h_handlers.inc — M08H WRITE family: dimensions / annotations / hatch (staged-write).
//
// Owned by the M08H teammate (PR-scoped). #included into AriadneNativeJob.cpp; sees every in-TU
// helper. Contract (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - m08hHasOp(op): true for every op id this family IMPLEMENTS (gate admission). Ops left out
//     keep returning the honest OPERATION_NOT_IMPLEMENTED. NO FAKES.
//   - m08hDispatch(op, ctx, r): if op is yours, append  "result":{...},"status":"ok"  (or an
//     emitNativeError-style error) to r and return true; else return false.
//
// SAFETY (hard): staged-write ONLY. Operate on ctx.pDb (the router-staged in-memory copy).
//   Never call save()/saveAs() on the original. No acedCommand/acedCmd (compile-disabled in 2027).
//   Original DWG bytes must stay unchanged. We only appendAcDbEntity into the staged model space.
//
// IMPLEMENTED (12): write.entity.text (AcDbText), write.entity.mtext (AcDbMText),
//   write.entity.dim.aligned (AcDbAlignedDimension), write.entity.dim.rotated (AcDbRotatedDimension),
//   write.entity.dim.radial (AcDbRadialDimension), write.entity.dim.diametric (AcDbDiametricDimension),
//   write.entity.dim.angular2line (AcDb2LineAngularDimension),
//   write.entity.dim.angular3pt (AcDb3PointAngularDimension),
//   write.entity.dim.ordinate (AcDbOrdinateDimension), write.entity.dim.arc (AcDbArcDimension),
//   write.entity.dim.radiallarge (AcDbRadialDimensionLarge), write.entity.hatch (AcDbHatch, solid fill).
// DEFERRED (3, NOT in HasOp — see reports/tickets/M08H.md for the concrete blocker):
//   write.entity.leader, write.entity.mleader, write.entity.table.
//
// Strings: entity content -> utf8ToWide() (lossless UTF-8 -> UTF-16; ASCII is a strict subset, so the
//   ASCII path is unchanged) for setTextString/setContents/dim text; JSON output -> njsonStr (UTF-8).
// Dimension subclasses all take the DB default dim-style id (pDb->dimstyle()) when none is requested.
//
// All entity classes here are core AcDb (AcDbText/AcDbMText in dbents.h/dbmtext.h, the dimension
// subclasses in dbdim.h, AcDbHatch in dbhatch.h) exported by the same acdb import lib that already
// links write.entity.line/circle — so NO extra #pragma comment(lib,...) is required (unlike the M08D
// BRep group, which needed acbr26.lib). dbents.h / dbmtext.h / dbhatch.h are already #included by the
// enclosing TU; dbdim.h and the AcGe 2D-array headers are pulled in here for this family.

#include "dbdim.h"      // AcDbAlignedDimension / Rotated / Radial / Diametric / angular / ordinate / arc / large
#include "gept2dar.h"   // AcGePoint2dArray (hatch loop vertices)
#include "gedblar.h"    // AcGeDoubleArray  (hatch loop bulges)
#include "gepnt2d.h"    // AcGePoint2d
#include "gevec3d.h"    // AcGeVector3d (hatch normal)

//============================================================================
// M08H local arg helpers (family-private; complement the in-TU jsonFind*).
//============================================================================

// Read a named {x,y,z} point object out of the job JSON. Missing members default to 0.
// Returns true if the named object was present (so callers can require it).
static bool m08hReadPoint(const std::string& job, const char* key, AcGePoint3d& out)
{
    std::string obj;
    if (!jsonFindObject(job, key, obj))
        return false;
    double x = 0.0, y = 0.0, z = 0.0;
    jsonFindNumber(obj, "x", x);
    jsonFindNumber(obj, "y", y);
    jsonFindNumber(obj, "z", z);
    out.set(x, y, z);
    return true;
}

// Parse the "vertices" JSON array (a list of {x,y} objects) into a 2D point array.
// Hand-rolled to match the file's minimal-JSON convention (jsonFind* are scalar/object only).
// Scans brace-delimited objects inside the array and pulls x,y from each. z is ignored (hatch
// loops are planar in the entity ECS). Returns the count appended.
static int m08hReadVertexArray(const std::string& job, AcGePoint2dArray& outPts)
{
    outPts.removeAll();
    // locate  "vertices"  then the following '['
    const std::string keyTok = "\"vertices\"";
    size_t k = job.find(keyTok);
    if (k == std::string::npos)
        return 0;
    size_t lb = job.find('[', k);
    if (lb == std::string::npos)
        return 0;
    size_t rb = job.find(']', lb);
    if (rb == std::string::npos)
        rb = job.size();
    const std::string arr = job.substr(lb + 1, rb - lb - 1);

    size_t pos = 0;
    while (pos < arr.size()) {
        size_t ob = arr.find('{', pos);
        if (ob == std::string::npos)
            break;
        size_t oe = arr.find('}', ob);
        if (oe == std::string::npos)
            break;
        const std::string objStr = arr.substr(ob, oe - ob + 1);
        double x = 0.0, y = 0.0;
        jsonFindNumber(objStr, "x", x);
        jsonFindNumber(objStr, "y", y);
        outPts.append(AcGePoint2d(x, y));
        pos = oe + 1;
    }
    return static_cast<int>(outPts.length());
}

// Open model space kForWrite (the staged copy). Returns eOk + sets pMS (caller closes it).
static Acad::ErrorStatus m08hOpenModelSpace(AcDbDatabase* pDb, AcDbBlockTableRecord*& pMS)
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

// Append a freshly-new'd entity into the staged model space, honoring an optional layer.
// Takes ownership of pE: on success closes it (sets outId); on failure deletes it.
// Returns the append errorstatus (eOk == created).
static Acad::ErrorStatus m08hAppend(AcDbDatabase* pDb, const std::string& layer,
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
    Acad::ErrorStatus es = m08hOpenModelSpace(pDb, pMS);
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

// Emit the family's standard success envelope after a successful append.
static void m08hEmitCreated(std::ostringstream& r, AcDbDatabase* pDb,
                            const std::string& acdbClass, const AcDbObjectId& id,
                            const std::string& layer)
{
    int probes = 0, after = 0;
    countModelSpace(pDb, after, probes);
    r << "\"result\":{\"created\":true"
      << ",\"class\":" << njsonStr(acdbClass)
      << ",\"handle\":" << njsonStr(handleOfId(id))
      << ",\"layer\":" << njsonStr(layer)
      << ",\"modelspace_entities_after\":" << after << "},"
      << "\"status\":\"ok\"}";
}

//============================================================================
// HasOp / Dispatch
//============================================================================
static bool m08hHasOp(const std::string& op)
{
    return op == "write.entity.text"
        || op == "write.entity.mtext"
        || op == "write.entity.dim.aligned"
        || op == "write.entity.dim.rotated"
        || op == "write.entity.dim.radial"
        || op == "write.entity.dim.diametric"
        || op == "write.entity.dim.angular2line"
        || op == "write.entity.dim.angular3pt"
        || op == "write.entity.dim.ordinate"
        || op == "write.entity.dim.arc"
        || op == "write.entity.dim.radiallarge"
        || op == "write.entity.hatch";
}

static bool m08hDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    if (!m08hHasOp(op))
        return false;
    AcDbDatabase* pDb = ctx.pDb;
    if (pDb == nullptr) {
        emitNativeError(r, "DB_ERROR", "null database");
        return true;
    }
    const std::string& job = ctx.job;

    // ---- M08H-T01: annotation ------------------------------------------------
    if (op == "write.entity.text") {
        std::string layer;   jsonFindString(job, "layer", layer);
        std::string content; jsonFindString(job, "text", content);
        AcGePoint3d pos(0.0, 0.0, 0.0); m08hReadPoint(job, "position", pos);
        double height = 2.5; jsonFindNumber(job, "height", height);

        AcDbText* pE = new AcDbText();
        pE->setPosition(pos);
        if (height > 0.0)
            pE->setHeight(height);
        pE->setTextString(utf8ToWide(content).c_str());

        AcDbObjectId id;
        const Acad::ErrorStatus es = m08hAppend(pDb, layer, pE, id);
        if (es != Acad::eOk) {
            emitNativeError(r, "APPEND_FAILED", "AcDbText append es=" + std::to_string(static_cast<int>(es)));
            return true;
        }
        m08hEmitCreated(r, pDb, "AcDbText", id, layer);
        return true;
    }

    if (op == "write.entity.mtext") {
        std::string layer;   jsonFindString(job, "layer", layer);
        std::string content; jsonFindString(job, "text", content);
        AcGePoint3d loc(0.0, 0.0, 0.0); m08hReadPoint(job, "position", loc);
        double height = 2.5; jsonFindNumber(job, "height", height);

        AcDbMText* pE = new AcDbMText();
        pE->setLocation(loc);
        if (height > 0.0)
            pE->setTextHeight(height);
        pE->setContents(utf8ToWide(content).c_str());

        AcDbObjectId id;
        const Acad::ErrorStatus es = m08hAppend(pDb, layer, pE, id);
        if (es != Acad::eOk) {
            emitNativeError(r, "APPEND_FAILED", "AcDbMText append es=" + std::to_string(static_cast<int>(es)));
            return true;
        }
        m08hEmitCreated(r, pDb, "AcDbMText", id, layer);
        return true;
    }

    // ---- M08H-T01: dimensions (all take pDb->dimstyle() as the default style) -
    // Optional user override text for the dimension measurement string.
    if (op == "write.entity.dim.aligned") {
        std::string layer; jsonFindString(job, "layer", layer);
        std::string dimText; jsonFindString(job, "dim_text", dimText);
        AcGePoint3d p1, p2, dimLine;
        const bool ok = m08hReadPoint(job, "xline1", p1) && m08hReadPoint(job, "xline2", p2)
                     && m08hReadPoint(job, "dim_line", dimLine);
        if (!ok) {
            emitNativeError(r, "MISSING_ARG", "aligned dim needs xline1, xline2, dim_line points");
            return true;
        }
        const std::wstring dt = utf8ToWide(dimText);
        AcDbAlignedDimension* pE = new AcDbAlignedDimension(
            p1, p2, dimLine, dimText.empty() ? nullptr : dt.c_str(), pDb->dimstyle());
        AcDbObjectId id;
        const Acad::ErrorStatus es = m08hAppend(pDb, layer, pE, id);
        if (es != Acad::eOk) {
            emitNativeError(r, "APPEND_FAILED", "AcDbAlignedDimension append es=" + std::to_string(static_cast<int>(es)));
            return true;
        }
        m08hEmitCreated(r, pDb, "AcDbAlignedDimension", id, layer);
        return true;
    }

    if (op == "write.entity.dim.rotated") {
        std::string layer; jsonFindString(job, "layer", layer);
        std::string dimText; jsonFindString(job, "dim_text", dimText);
        double rotation = 0.0; jsonFindNumber(job, "rotation", rotation);
        AcGePoint3d p1, p2, dimLine;
        const bool ok = m08hReadPoint(job, "xline1", p1) && m08hReadPoint(job, "xline2", p2)
                     && m08hReadPoint(job, "dim_line", dimLine);
        if (!ok) {
            emitNativeError(r, "MISSING_ARG", "rotated dim needs xline1, xline2, dim_line points");
            return true;
        }
        const std::wstring dt = utf8ToWide(dimText);
        AcDbRotatedDimension* pE = new AcDbRotatedDimension(
            rotation, p1, p2, dimLine, dimText.empty() ? nullptr : dt.c_str(), pDb->dimstyle());
        AcDbObjectId id;
        const Acad::ErrorStatus es = m08hAppend(pDb, layer, pE, id);
        if (es != Acad::eOk) {
            emitNativeError(r, "APPEND_FAILED", "AcDbRotatedDimension append es=" + std::to_string(static_cast<int>(es)));
            return true;
        }
        m08hEmitCreated(r, pDb, "AcDbRotatedDimension", id, layer);
        return true;
    }

    if (op == "write.entity.dim.radial") {
        std::string layer; jsonFindString(job, "layer", layer);
        std::string dimText; jsonFindString(job, "dim_text", dimText);
        double leaderLength = 0.0; jsonFindNumber(job, "leader_length", leaderLength);
        AcGePoint3d center, chord;
        const bool ok = m08hReadPoint(job, "center", center) && m08hReadPoint(job, "chord_point", chord);
        if (!ok) {
            emitNativeError(r, "MISSING_ARG", "radial dim needs center, chord_point");
            return true;
        }
        const std::wstring dt = utf8ToWide(dimText);
        AcDbRadialDimension* pE = new AcDbRadialDimension(
            center, chord, leaderLength, dimText.empty() ? nullptr : dt.c_str(), pDb->dimstyle());
        AcDbObjectId id;
        const Acad::ErrorStatus es = m08hAppend(pDb, layer, pE, id);
        if (es != Acad::eOk) {
            emitNativeError(r, "APPEND_FAILED", "AcDbRadialDimension append es=" + std::to_string(static_cast<int>(es)));
            return true;
        }
        m08hEmitCreated(r, pDb, "AcDbRadialDimension", id, layer);
        return true;
    }

    if (op == "write.entity.dim.diametric") {
        std::string layer; jsonFindString(job, "layer", layer);
        std::string dimText; jsonFindString(job, "dim_text", dimText);
        double leaderLength = 0.0; jsonFindNumber(job, "leader_length", leaderLength);
        AcGePoint3d chord, farChord;
        const bool ok = m08hReadPoint(job, "chord_point", chord) && m08hReadPoint(job, "far_chord_point", farChord);
        if (!ok) {
            emitNativeError(r, "MISSING_ARG", "diametric dim needs chord_point, far_chord_point");
            return true;
        }
        const std::wstring dt = utf8ToWide(dimText);
        AcDbDiametricDimension* pE = new AcDbDiametricDimension(
            chord, farChord, leaderLength, dimText.empty() ? nullptr : dt.c_str(), pDb->dimstyle());
        AcDbObjectId id;
        const Acad::ErrorStatus es = m08hAppend(pDb, layer, pE, id);
        if (es != Acad::eOk) {
            emitNativeError(r, "APPEND_FAILED", "AcDbDiametricDimension append es=" + std::to_string(static_cast<int>(es)));
            return true;
        }
        m08hEmitCreated(r, pDb, "AcDbDiametricDimension", id, layer);
        return true;
    }

    if (op == "write.entity.dim.angular2line") {
        std::string layer; jsonFindString(job, "layer", layer);
        std::string dimText; jsonFindString(job, "dim_text", dimText);
        AcGePoint3d l1s, l1e, l2s, l2e, arcPt;
        const bool ok = m08hReadPoint(job, "xline1_start", l1s) && m08hReadPoint(job, "xline1_end", l1e)
                     && m08hReadPoint(job, "xline2_start", l2s) && m08hReadPoint(job, "xline2_end", l2e)
                     && m08hReadPoint(job, "arc_point", arcPt);
        if (!ok) {
            emitNativeError(r, "MISSING_ARG", "angular2line dim needs xline1_start/end, xline2_start/end, arc_point");
            return true;
        }
        const std::wstring dt = utf8ToWide(dimText);
        AcDb2LineAngularDimension* pE = new AcDb2LineAngularDimension(
            l1s, l1e, l2s, l2e, arcPt, dimText.empty() ? nullptr : dt.c_str(), pDb->dimstyle());
        AcDbObjectId id;
        const Acad::ErrorStatus es = m08hAppend(pDb, layer, pE, id);
        if (es != Acad::eOk) {
            emitNativeError(r, "APPEND_FAILED", "AcDb2LineAngularDimension append es=" + std::to_string(static_cast<int>(es)));
            return true;
        }
        m08hEmitCreated(r, pDb, "AcDb2LineAngularDimension", id, layer);
        return true;
    }

    if (op == "write.entity.dim.angular3pt") {
        std::string layer; jsonFindString(job, "layer", layer);
        std::string dimText; jsonFindString(job, "dim_text", dimText);
        AcGePoint3d center, p1, p2, arcPt;
        const bool ok = m08hReadPoint(job, "center", center) && m08hReadPoint(job, "xline1", p1)
                     && m08hReadPoint(job, "xline2", p2) && m08hReadPoint(job, "arc_point", arcPt);
        if (!ok) {
            emitNativeError(r, "MISSING_ARG", "angular3pt dim needs center, xline1, xline2, arc_point");
            return true;
        }
        const std::wstring dt = utf8ToWide(dimText);
        AcDb3PointAngularDimension* pE = new AcDb3PointAngularDimension(
            center, p1, p2, arcPt, dimText.empty() ? nullptr : dt.c_str(), pDb->dimstyle());
        AcDbObjectId id;
        const Acad::ErrorStatus es = m08hAppend(pDb, layer, pE, id);
        if (es != Acad::eOk) {
            emitNativeError(r, "APPEND_FAILED", "AcDb3PointAngularDimension append es=" + std::to_string(static_cast<int>(es)));
            return true;
        }
        m08hEmitCreated(r, pDb, "AcDb3PointAngularDimension", id, layer);
        return true;
    }

    if (op == "write.entity.dim.ordinate") {
        std::string layer; jsonFindString(job, "layer", layer);
        std::string dimText; jsonFindString(job, "dim_text", dimText);
        bool useXAxis = true; { double ax = 1.0; if (jsonFindNumber(job, "use_x_axis", ax)) useXAxis = (ax != 0.0); }
        AcGePoint3d defPt, leaderEnd;
        const bool ok = m08hReadPoint(job, "defining_point", defPt) && m08hReadPoint(job, "leader_end_point", leaderEnd);
        if (!ok) {
            emitNativeError(r, "MISSING_ARG", "ordinate dim needs defining_point, leader_end_point");
            return true;
        }
        const std::wstring dt = utf8ToWide(dimText);
        AcDbOrdinateDimension* pE = new AcDbOrdinateDimension(
            useXAxis ? Adesk::kTrue : Adesk::kFalse, defPt, leaderEnd,
            dimText.empty() ? nullptr : dt.c_str(), pDb->dimstyle());
        AcDbObjectId id;
        const Acad::ErrorStatus es = m08hAppend(pDb, layer, pE, id);
        if (es != Acad::eOk) {
            emitNativeError(r, "APPEND_FAILED", "AcDbOrdinateDimension append es=" + std::to_string(static_cast<int>(es)));
            return true;
        }
        m08hEmitCreated(r, pDb, "AcDbOrdinateDimension", id, layer);
        return true;
    }

    if (op == "write.entity.dim.arc") {
        std::string layer; jsonFindString(job, "layer", layer);
        std::string dimText; jsonFindString(job, "dim_text", dimText);
        AcGePoint3d center, p1, p2, arcPt;
        const bool ok = m08hReadPoint(job, "center", center) && m08hReadPoint(job, "xline1", p1)
                     && m08hReadPoint(job, "xline2", p2) && m08hReadPoint(job, "arc_point", arcPt);
        if (!ok) {
            emitNativeError(r, "MISSING_ARG", "arc dim needs center, xline1, xline2, arc_point");
            return true;
        }
        const std::wstring dt = utf8ToWide(dimText);
        AcDbArcDimension* pE = new AcDbArcDimension(
            center, p1, p2, arcPt, dimText.empty() ? nullptr : dt.c_str(), pDb->dimstyle());
        AcDbObjectId id;
        const Acad::ErrorStatus es = m08hAppend(pDb, layer, pE, id);
        if (es != Acad::eOk) {
            emitNativeError(r, "APPEND_FAILED", "AcDbArcDimension append es=" + std::to_string(static_cast<int>(es)));
            return true;
        }
        m08hEmitCreated(r, pDb, "AcDbArcDimension", id, layer);
        return true;
    }

    if (op == "write.entity.dim.radiallarge") {
        std::string layer; jsonFindString(job, "layer", layer);
        std::string dimText; jsonFindString(job, "dim_text", dimText);
        double jogAngle = 0.785398163397448; jsonFindNumber(job, "jog_angle", jogAngle); // default 45deg
        AcGePoint3d center, chord, overrideCenter, jogPoint;
        const bool ok = m08hReadPoint(job, "center", center) && m08hReadPoint(job, "chord_point", chord)
                     && m08hReadPoint(job, "override_center", overrideCenter) && m08hReadPoint(job, "jog_point", jogPoint);
        if (!ok) {
            emitNativeError(r, "MISSING_ARG", "radiallarge dim needs center, chord_point, override_center, jog_point");
            return true;
        }
        const std::wstring dt = utf8ToWide(dimText);
        AcDbRadialDimensionLarge* pE = new AcDbRadialDimensionLarge(
            center, chord, overrideCenter, jogPoint, jogAngle,
            dimText.empty() ? nullptr : dt.c_str(), pDb->dimstyle());
        AcDbObjectId id;
        const Acad::ErrorStatus es = m08hAppend(pDb, layer, pE, id);
        if (es != Acad::eOk) {
            emitNativeError(r, "APPEND_FAILED", "AcDbRadialDimensionLarge append es=" + std::to_string(static_cast<int>(es)));
            return true;
        }
        m08hEmitCreated(r, pDb, "AcDbRadialDimensionLarge", id, layer);
        return true;
    }

    // ---- M08H-T02: hatch (solid fill over one closed loop) -------------------
    if (op == "write.entity.hatch") {
        std::string layer; jsonFindString(job, "layer", layer);
        AcGePoint2dArray verts;
        const int n = m08hReadVertexArray(job, verts);
        if (n < 3) {
            emitNativeError(r, "MISSING_ARG", "hatch needs a 'vertices' array of >=3 {x,y} points (closed loop)");
            return true;
        }
        // zero-bulge (straight-edge) polyline loop
        AcGeDoubleArray bulges;
        for (int i = 0; i < n; ++i)
            bulges.append(0.0);

        AcDbHatch* pE = new AcDbHatch();
        pE->setAssociative(false);
        pE->setDatabaseDefaults(pDb);
        pE->setNormal(AcGeVector3d(0.0, 0.0, 1.0));
        pE->setElevation(0.0);
        pE->setHatchStyle(AcDbHatch::kNormal);
        Acad::ErrorStatus pes = pE->setPattern(AcDbHatch::kPreDefined, L"SOLID");
        if (pes != Acad::eOk) {
            delete pE;
            emitNativeError(r, "HATCH_PATTERN_FAILED", "setPattern SOLID es=" + std::to_string(static_cast<int>(pes)));
            return true;
        }
        Acad::ErrorStatus les = pE->appendLoop(AcDbHatch::kExternal, verts, bulges);
        if (les != Acad::eOk) {
            delete pE;
            emitNativeError(r, "HATCH_LOOP_FAILED", "appendLoop es=" + std::to_string(static_cast<int>(les)));
            return true;
        }
        Acad::ErrorStatus ees = pE->evaluateHatch();
        if (ees != Acad::eOk) {
            delete pE;
            emitNativeError(r, "HATCH_EVAL_FAILED", "evaluateHatch es=" + std::to_string(static_cast<int>(ees)));
            return true;
        }

        AcDbObjectId id;
        const Acad::ErrorStatus es = m08hAppend(pDb, layer, pE, id);
        if (es != Acad::eOk) {
            emitNativeError(r, "APPEND_FAILED", "AcDbHatch append es=" + std::to_string(static_cast<int>(es)));
            return true;
        }
        int probes = 0, after = 0;
        countModelSpace(pDb, after, probes);
        r << "\"result\":{\"created\":true"
          << ",\"class\":\"AcDbHatch\""
          << ",\"pattern\":\"SOLID\""
          << ",\"loop_vertices\":" << n
          << ",\"handle\":" << njsonStr(handleOfId(id))
          << ",\"layer\":" << njsonStr(layer)
          << ",\"modelspace_entities_after\":" << after << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    // HasOp admitted an op with no dispatch branch -> coherent-seam guard (no silent fall-through).
    emitNativeError(r, "OPERATION_DISPATCH_MISMATCH", "m08hHasOp admitted op with no handler: " + op);
    return true;
}
