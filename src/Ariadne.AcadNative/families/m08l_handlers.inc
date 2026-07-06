// families/m08l_handlers.inc — M08L NATIVE: graphics system (27 ops).
//
// Owned by the M08L teammate (PR-scoped). #included into AriadneNativeJob.cpp, so it sees every
// in-TU helper (njsonStr / serializeEntityCommon / AriadneReadTransaction / resolveHandle /
// jsonFind* / handleOf / handleOfId / emitNativeError / asciiToWide / acharToAscii). Contract
// (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - m08lHasOp(op): true for every op id this family IMPLEMENTS (gate admission). Ops left out
//     keep returning the honest OPERATION_NOT_IMPLEMENTED. NO FAKES.
//   - m08lDispatch(op, ctx, r): if op is yours, append  "result":{...},"status":"ok"  (or an
//     emitNativeError-style error) and return true; else return false.
//
// SAFETY (hard): READ / register-lifecycle only. Operate on ctx.pDb (the router-staged in-memory
//   copy). NEVER save()/saveAs()/_QSAVE on the original. No acedCommand/acedCmd. Entities opened
//   kForRead only. worldDraw() drives the entity's graphics elaboration into a hostless collector
//   (no DB mutation). Overrule registration is process-global; each probe ADDS then REMOVES its
//   overrule so the registry is left exactly as found (no persisted global mutation).
//
// FEASIBILITY (verified against the ObjectARX 2027 headers + the build):
//   T01 worldDraw/graphics (8): an AcGiWorldDraw collector that overrides every AcGi* pure
//     virtual and records the primitives an entity emits is HOSTLESS — AcGiDrawable::worldDraw()
//     (drawable.h:162, ACDBCORE2D_PORT, public, sealed) elaborates the entity's view-independent
//     graphics with no GS/viewport. 7 implemented; render.draw.viewportgeom DEFERRED (it needs an
//     AcGiViewportDraw bound to a live viewport — no hostless surface; see ticket).
//   T02 overrules/grips (19): AcRxOverrule::addOverrule/removeOverrule/setIsOverruling/
//     isOverruling/hasOverrule (rxoverrule.h, ACBASE_PORT, all static) register/query/remove a
//     concrete AcDb*Overrule against a target AcRxClass — HOSTLESS. The overrule's EFFECT fires
//     only during in-app operations (attended); we implement the register/query/remove/enable
//     LIFECYCLE (that IS the op) and say so honestly (effect_fires:"in_app_only"). 13 install +
//     global.enable + applicable + query.has + remove + inspect.entity.grips = 18 implemented;
//     overrule.dimstyle.install DEFERRED (no AcDbDimStyleOverrule class exists in ObjectARX 2027 —
//     verified by header scan of inc\*overrule*.h).
//
//   IMPLEMENTED 25, DEFERRED 2 (render.draw.viewportgeom, overrule.dimstyle.install).
//
// LNK note (from M08K): the DBX import lib exports only the module extern-C API, not custom-class
//   ::desc()/::cast(). M08L uses ONLY standard AcDb/AcRx/AcGi classes (AcDbEntity, AcDbPoint,
//   AcRxOverrule, AcDb*Overrule, AcGi*), all exported by acdbcore2d/acbase — no custom-class
//   linkage risk.

#include "acgi.h"           // AcGiWorldDraw / AcGiWorldGeometry / AcGiGeometry / AcGiSubEntityTraits / AcGiContext
#include "acgidefs.h"       // AcGiRegenType / AcGiArcType / AcGiFillType
#include "drawable.h"       // AcGiDrawable::worldDraw/setAttributes ; AcGiDrawableOverrule
#include "rxoverrule.h"     // AcRxOverrule (addOverrule/removeOverrule/setIsOverruling/hasOverrule)
#include "dbobjectoverrule.h"  // AcDbObjectOverrule
#include "dbentityoverrule.h"  // AcDbPropertiesOverrule/Osnap/Transform/Grip/Subentity/Highlight/HighlightState/Visibility/Geometry overrules
#include "dbgrip.h"         // AcDbGripDataPtrArray
#include "dbents.h"         // AcDbPoint (transient subject for overrule applicability probes)
#include "dbdim.h"          // AcDbDimension / AcDbDimensionStyleOverrule

//============================================================================
// M08L hostless AcGiWorldDraw collector
//============================================================================
// A complete, concrete AcGiWorldDraw that an entity's worldDraw() can be driven into with no
// graphics system. Every AcGi* pure virtual is overridden; geometry primitives are tallied (and
// the first vertex captured) so the op can REPORT what the entity actually emitted. No GS, no
// viewport, no DB mutation — pure elaboration capture.
//
// These collector classes are plain C++ subclasses (NO ACRX_DECLARE_MEMBERS): nothing queries
// their RTTI — AcGiDrawable::worldDraw() invokes the virtuals through the vtable. This mirrors
// M08K's M08KProtocolXObject (a registration-free AcRxObject subclass).

#ifndef ARIADNE_M08L_GRAPHICS
#define ARIADNE_M08L_GRAPHICS 1

// Tally of primitives captured during a worldDraw elaboration.
struct M08LGraphicsTally
{
    unsigned long circle = 0, circularArc = 0, ellipticalArc = 0;
    unsigned long polyline = 0, polygon = 0, polyPolyline = 0, polyPolygon = 0;
    unsigned long mesh = 0, shell = 0, text = 0, xline = 0, ray = 0;
    unsigned long pline = 0, image = 0, draw = 0, edge = 0, dots = 0;
    unsigned long faceDataSeen = 0;     // shell/mesh calls that carried a non-null AcGiFaceData
    unsigned long vertexTotal = 0;      // running count of vertices passed to polyline/polygon/shell/mesh
    bool extentsSet = false;
    AcGePoint3d extMin, extMax;
    bool haveSample = false;
    AcGePoint3d sample;

    unsigned long total() const {
        return circle + circularArc + ellipticalArc + polyline + polygon + polyPolyline +
               polyPolygon + mesh + shell + text + xline + ray + pline + image + draw + edge + dots;
    }
    void capture(Adesk::UInt32 n, const AcGePoint3d* pv) {
        if (!haveSample && pv != nullptr && n > 0) { sample = pv[0]; haveSample = true; }
    }
};

// --- AcGiContext (3 pure virtuals) -----------------------------------------
class M08LCollectContext : public AcGiContext
{
public:
    explicit M08LCollectContext(AcDbDatabase* pDb) : m_pDb(pDb) {}
    bool          isPlotGeneration() const override { return false; }
    AcDbDatabase* database() const override { return m_pDb; }
    bool          isBoundaryClipping() const override { return false; }
private:
    AcDbDatabase* m_pDb;
};

// --- AcGiSubEntityTraits (13 pure virtuals + inline defaults) ---------------
// Records the attribute state an entity sets during elaboration.
class M08LCollectTraits : public AcGiSubEntityTraits
{
public:
    void setColor(const Adesk::UInt16 color) override { m_color = color; m_colorSet = true; }
    void setTrueColor(const AcCmEntityColor& color) override { m_trueColor = color; m_trueColorSet = true; }
    void setLayer(const AcDbObjectId layerId) override { m_layerId = layerId; }
    void setLineType(const AcDbObjectId linetypeId) override { m_lineTypeId = linetypeId; }
    void setSelectionMarker(const Adesk::LongPtr markerId) override { m_marker = markerId; }
    void setFillType(const AcGiFillType ft) override { m_fillType = ft; }
    void setLineWeight(const AcDb::LineWeight lw) override { m_lineWeight = lw; m_lwSet = true; }
    void setLineTypeScale(double s = 1.0) override { m_ltScale = s; }
    void setThickness(double t) override { m_thickness = t; }

    Adesk::UInt16    color() const override { return m_color; }
    AcCmEntityColor  trueColor() const override { return m_trueColor; }
    AcDbObjectId     layerId() const override { return m_layerId; }
    AcDbObjectId     lineTypeId() const override { return m_lineTypeId; }
    AcGiFillType     fillType() const override { return m_fillType; }
    AcDb::LineWeight lineWeight() const override { return m_lineWeight; }
    double           lineTypeScale() const override { return m_ltScale; }
    double           thickness() const override { return m_thickness; }

    bool colorSet() const { return m_colorSet; }
    bool trueColorSet() const { return m_trueColorSet; }
    bool lineWeightSet() const { return m_lwSet; }

private:
    Adesk::UInt16    m_color = 256;        // 256 == ByLayer
    AcCmEntityColor  m_trueColor;
    AcDbObjectId     m_layerId;
    AcDbObjectId     m_lineTypeId;
    AcGiFillType     m_fillType = kAcGiFillNever;
    AcDb::LineWeight m_lineWeight = AcDb::kLnWtByLayer;
    double           m_ltScale = 1.0;
    double           m_thickness = 0.0;
    Adesk::LongPtr   m_marker = -1;
    bool             m_colorSet = false;
    bool             m_trueColorSet = false;
    bool             m_lwSet = false;
};

// --- AcGiWorldGeometry (AcGiGeometry ~30 pure virtuals + setExtents) --------
// Each draw primitive is tallied; geometry is NOT forwarded anywhere (no GS).
class M08LCollectGeometry : public AcGiWorldGeometry
{
public:
    explicit M08LCollectGeometry(M08LGraphicsTally& tally) : m_tally(tally) {}

    // ---- coordinate transforms (identity / accept-and-ignore) ----
    void getModelToWorldTransform(AcGeMatrix3d& m) const override { m.setToIdentity(); }
    void getWorldToModelTransform(AcGeMatrix3d& m) const override { m.setToIdentity(); }
    Adesk::Boolean pushModelTransform(const AcGeVector3d&) override { return Adesk::kTrue; }
    Adesk::Boolean pushModelTransform(const AcGeMatrix3d&) override { return Adesk::kTrue; }
    Adesk::Boolean popModelTransform() override { return Adesk::kTrue; }
    AcGeMatrix3d pushPositionTransform(AcGiPositionTransformBehavior, const AcGePoint3d&) override { return AcGeMatrix3d::kIdentity; }
    AcGeMatrix3d pushPositionTransform(AcGiPositionTransformBehavior, const AcGePoint2d&) override { return AcGeMatrix3d::kIdentity; }
    AcGeMatrix3d pushScaleTransform(AcGiScaleTransformBehavior, const AcGePoint3d&) override { return AcGeMatrix3d::kIdentity; }
    AcGeMatrix3d pushScaleTransform(AcGiScaleTransformBehavior, const AcGePoint2d&) override { return AcGeMatrix3d::kIdentity; }
    AcGeMatrix3d pushOrientationTransform(AcGiOrientationTransformBehavior) override { return AcGeMatrix3d::kIdentity; }

    // ---- primitives ----
    Adesk::Boolean circle(const AcGePoint3d&, const double, const AcGeVector3d&) const override
        { ++m_tally.circle; return Adesk::kTrue; }
    Adesk::Boolean circle(const AcGePoint3d&, const AcGePoint3d&, const AcGePoint3d&) const override
        { ++m_tally.circle; return Adesk::kTrue; }
    Adesk::Boolean circularArc(const AcGePoint3d&, const double, const AcGeVector3d&,
                               const AcGeVector3d&, const double, const AcGiArcType) const override
        { ++m_tally.circularArc; return Adesk::kTrue; }
    Adesk::Boolean circularArc(const AcGePoint3d&, const AcGePoint3d&, const AcGePoint3d&,
                               const AcGiArcType) const override
        { ++m_tally.circularArc; return Adesk::kTrue; }
    Adesk::Boolean polyline(const Adesk::UInt32 n, const AcGePoint3d* pv,
                            const AcGeVector3d*, Adesk::LongPtr) const override
        { ++m_tally.polyline; m_tally.vertexTotal += n; m_tally.capture(n, pv); return Adesk::kTrue; }
    Adesk::Boolean polyline(const AcGiPolyline&) const override
        { ++m_tally.polyline; return Adesk::kTrue; }
    Adesk::Boolean polyPolyline(Adesk::UInt32 n, const AcGiPolyline*) const override
        { ++m_tally.polyPolyline; (void)n; return Adesk::kTrue; }
    Adesk::Boolean polygon(const Adesk::UInt32 n, const AcGePoint3d* pv) const override
        { ++m_tally.polygon; m_tally.vertexTotal += n; m_tally.capture(n, pv); return Adesk::kTrue; }
    Adesk::Boolean polyPolygon(const Adesk::UInt32, const Adesk::UInt32*, const AcGePoint3d*,
                               const Adesk::UInt32*, const AcGePoint3d*, const AcCmEntityColor*,
                               const AcGiLineType*, const AcCmEntityColor*,
                               const AcCmTransparency*) const override
        { ++m_tally.polyPolygon; return Adesk::kTrue; }
    Adesk::Boolean mesh(const Adesk::UInt32 rows, const Adesk::UInt32 cols, const AcGePoint3d* pv,
                        const AcGiEdgeData*, const AcGiFaceData* pFace, const AcGiVertexData*,
                        const bool) const override
        { ++m_tally.mesh; m_tally.vertexTotal += (rows * cols);
          if (pFace != nullptr) ++m_tally.faceDataSeen; m_tally.capture(rows * cols, pv); return Adesk::kTrue; }
    Adesk::Boolean shell(const Adesk::UInt32 nv, const AcGePoint3d* pv, const Adesk::UInt32,
                         const Adesk::Int32*, const AcGiEdgeData*, const AcGiFaceData* pFace,
                         const AcGiVertexData*, const struct resbuf*, const bool) const override
        { ++m_tally.shell; m_tally.vertexTotal += nv;
          if (pFace != nullptr) ++m_tally.faceDataSeen; m_tally.capture(nv, pv); return Adesk::kTrue; }
    Adesk::Boolean text(const AcGePoint3d&, const AcGeVector3d&, const AcGeVector3d&,
                        const double, const double, const double, const ACHAR*) const override
        { ++m_tally.text; return Adesk::kTrue; }
    Adesk::Boolean text(const AcGePoint3d&, const AcGeVector3d&, const AcGeVector3d&,
                        const ACHAR*, const Adesk::Int32, const Adesk::Boolean,
                        const AcGiTextStyle&) const override
        { ++m_tally.text; return Adesk::kTrue; }
    Adesk::Boolean xline(const AcGePoint3d&, const AcGePoint3d&) const override
        { ++m_tally.xline; return Adesk::kTrue; }
    Adesk::Boolean ray(const AcGePoint3d&, const AcGePoint3d&) const override
        { ++m_tally.ray; return Adesk::kTrue; }
    Adesk::Boolean pline(const AcDbPolyline&, Adesk::UInt32, Adesk::UInt32) const override
        { ++m_tally.pline; return Adesk::kTrue; }
    Adesk::Boolean draw(AcGiDrawable*) const override
        { ++m_tally.draw; return Adesk::kTrue; }
    Adesk::Boolean image(const AcGiImageBGRA32&, const AcGePoint3d&, const AcGeVector3d&,
                         const AcGeVector3d&, TransparencyMode) const override
        { ++m_tally.image; return Adesk::kTrue; }
    Adesk::Boolean rowOfDots(int, const AcGePoint3d&, const AcGeVector3d&) const override
        { ++m_tally.dots; return Adesk::kTrue; }
    Adesk::Boolean ellipticalArc(const AcGePoint3d&, const AcGeVector3d&, double, double,
                                 double, double, double, AcGiArcType) const override
        { ++m_tally.ellipticalArc; return Adesk::kTrue; }
    Adesk::Boolean pushClipBoundary(AcGiClipBoundary*) override { return Adesk::kTrue; }
    void           popClipBoundary() override {}
    Adesk::Boolean edge(const AcArray<AcGeCurve2d*>&) const override
        { ++m_tally.edge; return Adesk::kTrue; }

    // ---- AcGiWorldGeometry pure virtual ----
    void setExtents(AcGePoint3d* p) const override
        { if (p != nullptr) { m_tally.extentsSet = true; m_tally.extMin = p[0]; m_tally.extMax = p[1]; } }

private:
    M08LGraphicsTally& m_tally;
};

// --- AcGiWorldDraw (AcGiCommonDraw 8 pure + geometry()) ---------------------
class M08LCollectWorldDraw : public AcGiWorldDraw
{
public:
    M08LCollectWorldDraw(AcDbDatabase* pDb, M08LGraphicsTally& tally, AcGiRegenType rt)
        : m_ctx(pDb), m_geom(tally), m_regen(rt) {}

    // AcGiCommonDraw (pure)
    AcGiRegenType        regenType() const override { return m_regen; }
    Adesk::Boolean       regenAbort() const override { return Adesk::kFalse; }
    AcGiSubEntityTraits& subEntityTraits() const override { return const_cast<M08LCollectTraits&>(m_traits); }
    AcGiGeometry*        rawGeometry() const override { return const_cast<M08LCollectGeometry*>(&m_geom); }
    Adesk::Boolean       isDragging() const override { return Adesk::kFalse; }
    double               deviation(const AcGiDeviationType, const AcGePoint3d&) const override { return 0.0; }
    Adesk::UInt32        numberOfIsolines() const override { return 4; }
    AcGiContext*         context() override { return &m_ctx; }
    // AcGiWorldDraw (pure)
    AcGiWorldGeometry&   geometry() const override { return const_cast<M08LCollectGeometry&>(m_geom); }

    const M08LCollectTraits& traits() const { return m_traits; }

private:
    M08LCollectContext  m_ctx;
    M08LCollectGeometry m_geom;
    M08LCollectTraits   m_traits;
    AcGiRegenType       m_regen;
};

// --- AcGiViewportGeometry ---
class M08LCollectViewportGeometry : public AcGiViewportGeometry
{
public:
    explicit M08LCollectViewportGeometry(M08LGraphicsTally& tally) : m_tally(tally) {}

    // ---- coordinate transforms ----
    void getModelToWorldTransform(AcGeMatrix3d& m) const override { m.setToIdentity(); }
    void getWorldToModelTransform(AcGeMatrix3d& m) const override { m.setToIdentity(); }
    Adesk::Boolean pushModelTransform(const AcGeVector3d&) override { return Adesk::kTrue; }
    Adesk::Boolean pushModelTransform(const AcGeMatrix3d&) override { return Adesk::kTrue; }
    Adesk::Boolean popModelTransform() override { return Adesk::kTrue; }
    AcGeMatrix3d pushPositionTransform(AcGiPositionTransformBehavior, const AcGePoint3d&) override { return AcGeMatrix3d::kIdentity; }
    AcGeMatrix3d pushPositionTransform(AcGiPositionTransformBehavior, const AcGePoint2d&) override { return AcGeMatrix3d::kIdentity; }
    AcGeMatrix3d pushScaleTransform(AcGiScaleTransformBehavior, const AcGePoint3d&) override { return AcGeMatrix3d::kIdentity; }
    AcGeMatrix3d pushScaleTransform(AcGiScaleTransformBehavior, const AcGePoint2d&) override { return AcGeMatrix3d::kIdentity; }
    AcGeMatrix3d pushOrientationTransform(AcGiOrientationTransformBehavior) override { return AcGeMatrix3d::kIdentity; }

    // ---- primitives ----
    Adesk::Boolean circle(const AcGePoint3d&, const double, const AcGeVector3d&) const override
        { ++m_tally.circle; return Adesk::kTrue; }
    Adesk::Boolean circle(const AcGePoint3d&, const AcGePoint3d&, const AcGePoint3d&) const override
        { ++m_tally.circle; return Adesk::kTrue; }
    Adesk::Boolean circularArc(const AcGePoint3d&, const double, const AcGeVector3d&,
                               const AcGeVector3d&, const double, const AcGiArcType) const override
        { ++m_tally.circularArc; return Adesk::kTrue; }
    Adesk::Boolean circularArc(const AcGePoint3d&, const AcGePoint3d&, const AcGePoint3d&,
                               const AcGiArcType) const override
        { ++m_tally.circularArc; return Adesk::kTrue; }
    Adesk::Boolean polyline(const Adesk::UInt32 n, const AcGePoint3d* pv,
                            const AcGeVector3d*, Adesk::LongPtr) const override
        { ++m_tally.polyline; m_tally.vertexTotal += n; m_tally.capture(n, pv); return Adesk::kTrue; }
    Adesk::Boolean polyline(const AcGiPolyline&) const override
        { ++m_tally.polyline; return Adesk::kTrue; }
    Adesk::Boolean polyPolyline(Adesk::UInt32, const AcGiPolyline*) const override
        { ++m_tally.polyPolyline; return Adesk::kTrue; }
    Adesk::Boolean polygon(const Adesk::UInt32 n, const AcGePoint3d* pv) const override
        { ++m_tally.polygon; m_tally.vertexTotal += n; m_tally.capture(n, pv); return Adesk::kTrue; }
    Adesk::Boolean polyPolygon(const Adesk::UInt32, const Adesk::UInt32*, const AcGePoint3d*,
                               const Adesk::UInt32*, const AcGePoint3d*, const AcCmEntityColor*,
                               const AcGiLineType*, const AcCmEntityColor*,
                               const AcCmTransparency*) const override
        { ++m_tally.polyPolygon; return Adesk::kTrue; }
    Adesk::Boolean mesh(const Adesk::UInt32 rows, const Adesk::UInt32 cols, const AcGePoint3d* pv,
                        const AcGiEdgeData*, const AcGiFaceData* pFace, const AcGiVertexData*,
                        const bool) const override
        { ++m_tally.mesh; m_tally.vertexTotal += (rows * cols);
          if (pFace != nullptr) ++m_tally.faceDataSeen; m_tally.capture(rows * cols, pv); return Adesk::kTrue; }
    Adesk::Boolean shell(const Adesk::UInt32 nv, const AcGePoint3d* pv, const Adesk::UInt32,
                         const Adesk::Int32*, const AcGiEdgeData*, const AcGiFaceData* pFace,
                         const AcGiVertexData*, const struct resbuf*, const bool) const override
        { ++m_tally.shell; m_tally.vertexTotal += nv;
          if (pFace != nullptr) ++m_tally.faceDataSeen; m_tally.capture(nv, pv); return Adesk::kTrue; }
    Adesk::Boolean text(const AcGePoint3d&, const AcGeVector3d&, const AcGeVector3d&,
                        const double, const double, const double, const ACHAR*) const override
        { ++m_tally.text; return Adesk::kTrue; }
    Adesk::Boolean text(const AcGePoint3d&, const AcGeVector3d&, const AcGeVector3d&,
                        const ACHAR*, const Adesk::Int32, const Adesk::Boolean,
                        const AcGiTextStyle&) const override
        { ++m_tally.text; return Adesk::kTrue; }
    Adesk::Boolean xline(const AcGePoint3d&, const AcGePoint3d&) const override
        { ++m_tally.xline; return Adesk::kTrue; }
    Adesk::Boolean ray(const AcGePoint3d&, const AcGePoint3d&) const override
        { ++m_tally.ray; return Adesk::kTrue; }
    Adesk::Boolean pline(const AcDbPolyline&, Adesk::UInt32, Adesk::UInt32) const override
        { ++m_tally.pline; return Adesk::kTrue; }
    Adesk::Boolean draw(AcGiDrawable*) const override
        { ++m_tally.draw; return Adesk::kTrue; }
    Adesk::Boolean image(const AcGiImageBGRA32&, const AcGePoint3d&, const AcGeVector3d&,
                         const AcGeVector3d&, TransparencyMode) const override
        { ++m_tally.image; return Adesk::kTrue; }
    Adesk::Boolean rowOfDots(int, const AcGePoint3d&, const AcGeVector3d&) const override
        { ++m_tally.dots; return Adesk::kTrue; }
    Adesk::Boolean ellipticalArc(const AcGePoint3d&, const AcGeVector3d&, double, double,
                                 double, double, double, AcGiArcType) const override
        { ++m_tally.ellipticalArc; return Adesk::kTrue; }
    Adesk::Boolean pushClipBoundary(AcGiClipBoundary*) override { return Adesk::kTrue; }
    void           popClipBoundary() override {}
    Adesk::Boolean edge(const AcArray<AcGeCurve2d*>&) const override
        { ++m_tally.edge; return Adesk::kTrue; }

    // ---- AcGiViewportGeometry pure virtuals ----
    Adesk::Boolean polylineEye(const Adesk::UInt32 numPoints, const AcGePoint3d* vertexes) const override
        { ++m_tally.polyline; m_tally.vertexTotal += numPoints; m_tally.capture(numPoints, vertexes); return Adesk::kTrue; }
    Adesk::Boolean polygonEye(const Adesk::UInt32 numPoints, const AcGePoint3d* vertexes) const override
        { ++m_tally.polygon; m_tally.vertexTotal += numPoints; m_tally.capture(numPoints, vertexes); return Adesk::kTrue; }
    Adesk::Boolean polylineDc(const Adesk::UInt32 numPoints, const AcGePoint3d* vertexes) const override
        { ++m_tally.polyline; m_tally.vertexTotal += numPoints; m_tally.capture(numPoints, vertexes); return Adesk::kTrue; }
    Adesk::Boolean polygonDc(const Adesk::UInt32 numPoints, const AcGePoint3d* vertexes) const override
        { ++m_tally.polygon; m_tally.vertexTotal += numPoints; m_tally.capture(numPoints, vertexes); return Adesk::kTrue; }
    Adesk::Boolean rasterImageDc(
        const AcGePoint3d& origin,
        const AcGeVector3d& u,
        const AcGeVector3d& v,
        const AcGeMatrix2d& pixelToDc,
        AcDbObjectId entityId,
        AcGiImageOrg imageOrg,
        Adesk::UInt32 imageWidth,
        Adesk::UInt32 imageHeight,
        Adesk::Int16 imageColorDepth,
        Adesk::Boolean transparency,
        ImageSource source,
        const AcGeVector3d& unrotatedU,
        const AcGiImageOrg origionalImageOrg,
        const AcGeMatrix2d& unrotatedPixelToDc,
        const Adesk::UInt32 unrotatedImageWidth,
        const Adesk::UInt32 unrotatedImageHeight
    ) const override { ++m_tally.image; return Adesk::kTrue; }
    Adesk::Boolean ownerDrawDc(
        Adesk::Int32                       vpnumber,
        Adesk::Int32                       left,
        Adesk::Int32                       top,
        Adesk::Int32                       right,
        Adesk::Int32                       bottom,
        const OwnerDraw*           pOwnerDraw
    ) const override { return Adesk::kTrue; }

private:
    M08LGraphicsTally& m_tally;
};

// --- AcGiViewport ---
class M08LCollectViewport : public AcGiViewport
{
public:
    void getCameraLocation(AcGePoint3d& loc) const override { loc.set(0, 0, 0); }
    void getCameraTarget(AcGePoint3d& target) const override { target.set(0, 0, 0); }
    void getCameraUpVector(AcGeVector3d& up) const override { up.set(0, 1, 0); }
    void getEyeToWorldTransform(AcGeMatrix3d& m) const override { m.setToIdentity(); }
    void getWorldToEyeTransform(AcGeMatrix3d& m) const override { m.setToIdentity(); }
    Adesk::Boolean isPerspective() const override { return Adesk::kFalse; }
    void getViewportDcCorners(AcGePoint2d& lowerLeft, AcGePoint2d& upperRight) const override { lowerLeft.set(0,0); upperRight.set(100,100); }
    Adesk::Boolean getFrontAndBackClipValues(Adesk::Boolean& clipFront, Adesk::Boolean& clipBack, double& front, double& back) const override { clipFront = Adesk::kFalse; clipBack = Adesk::kFalse; front = 0; back = 0; return Adesk::kTrue; }
    double linetypeScaleMultiplier() const override { return 1.0; }
    void getEyeToModelTransform(AcGeMatrix3d& m) const override { m.setToIdentity(); }
    void getModelToEyeTransform(AcGeMatrix3d& m) const override { m.setToIdentity(); }
    
    Adesk::Boolean doPerspective(AcGePoint3d &) const override { return Adesk::kFalse; }
    Adesk::Boolean doInversePerspective(AcGePoint3d &) const override { return Adesk::kFalse; }
    void getNumPixelsInUnitSquare(const AcGePoint3d &,AcGePoint2d &,bool) const override {}
    Adesk::ULongPtr viewportId() const override { return 0; }
    Adesk::Int16 acadWindowId() const override { return 0; }
    double linetypeGenerationCriteria() const override { return 1.0; }
};

// --- AcGiViewportDraw ---
class M08LCollectViewportDraw : public AcGiViewportDraw
{
public:
    M08LCollectViewportDraw(AcDbDatabase* pDb, M08LGraphicsTally& tally, AcGiRegenType rt)
        : m_ctx(pDb), m_geom(tally), m_regen(rt) {}

    // AcGiCommonDraw (pure)
    AcGiRegenType        regenType() const override { return m_regen; }
    Adesk::Boolean       regenAbort() const override { return Adesk::kFalse; }
    AcGiSubEntityTraits& subEntityTraits() const override { return const_cast<M08LCollectTraits&>(m_traits); }
    AcGiGeometry*        rawGeometry() const override { return const_cast<M08LCollectViewportGeometry*>(&m_geom); }
    Adesk::Boolean       isDragging() const override { return Adesk::kFalse; }
    double               deviation(const AcGiDeviationType, const AcGePoint3d&) const override { return 0.0; }
    Adesk::UInt32        numberOfIsolines() const override { return 4; }
    AcGiContext*         context() override { return &m_ctx; }
    
    // AcGiViewportDraw (pure)
    AcGiViewport&        viewport() const override { return const_cast<M08LCollectViewport&>(m_viewport); }
    AcGiViewportGeometry& geometry() const override { return const_cast<M08LCollectViewportGeometry&>(m_geom); }
    Adesk::UInt32        sequenceNumber() const override { return 0; }
    Adesk::Boolean       isValidId(const Adesk::ULongPtr) const override { return Adesk::kTrue; }
    AcDbObjectId         viewportObjectId() const override { return AcDbObjectId::kNull; }

    const M08LCollectTraits& traits() const { return m_traits; }

private:
    M08LCollectContext          m_ctx;
    M08LCollectViewportGeometry m_geom;
    M08LCollectTraits           m_traits;
    M08LCollectViewport         m_viewport;
    AcGiRegenType               m_regen;
};

#endif // ARIADNE_M08L_GRAPHICS

//============================================================================
// M08L overrule lifecycle subclasses
//============================================================================
// Each AcDb*Overrule base leaves AcRxOverrule::isApplicable() pure, so a concrete instance needs
// a thin subclass that implements it. We DO NOT add ACRX_DECLARE_MEMBERS (no registered RTTI is
// required — addOverrule only stores the instance pointer keyed by the target AcRxClass). The
// inherited ACDBCORE2D_PORT protocol methods resolve from acdbcore2d (already linked). One static
// instance per kind (module-lifetime; addOverrule/removeOverrule reference it stably).

#ifndef ARIADNE_M08L_OVERRULES
#define ARIADNE_M08L_OVERRULES 1

#define M08L_DEFINE_OVERRULE(NAME, BASE)                                                  \
    class NAME : public BASE {                                                            \
    public:                                                                               \
        bool isApplicable(const AcRxObject* /*pSubject*/) const override { return true; } \
    }

M08L_DEFINE_OVERRULE(M08LObjectOverrule,         AcDbObjectOverrule);
M08L_DEFINE_OVERRULE(M08LDrawableOverrule,       AcGiDrawableOverrule);
M08L_DEFINE_OVERRULE(M08LGeometryOverrule,       AcDbGeometryOverrule);
M08L_DEFINE_OVERRULE(M08LTransformOverrule,      AcDbTransformOverrule);
M08L_DEFINE_OVERRULE(M08LOsnapOverrule,          AcDbOsnapOverrule);
M08L_DEFINE_OVERRULE(M08LSubentityOverrule,      AcDbSubentityOverrule);
M08L_DEFINE_OVERRULE(M08LPropertiesOverrule,     AcDbPropertiesOverrule);
M08L_DEFINE_OVERRULE(M08LHighlightOverrule,      AcDbHighlightOverrule);
M08L_DEFINE_OVERRULE(M08LHighlightStateOverrule, AcDbHighlightStateOverrule);
M08L_DEFINE_OVERRULE(M08LVisibilityOverrule,     AcDbVisibilityOverrule);
M08L_DEFINE_OVERRULE(M08LGripOverrule,           AcDbGripOverrule);
M08L_DEFINE_OVERRULE(M08LQueryXOverrule,         AcRxQueryXOverrule);
M08L_DEFINE_OVERRULE(M08LDimensionStyleOverrule, AcDbDimensionStyleOverrule);

#undef M08L_DEFINE_OVERRULE

// Resolve an install op id to (overrule instance, overrule-class descriptor, friendly name).
// Single static instance per kind. Returns false for an unknown / deferred install op
// (e.g. overrule.dimstyle.install — no such SDK class).
static bool m08lOverruleFor(const std::string& installOp, AcRxOverrule*& pOv,
                            AcRxClass*& pOvClass, const char*& className)
{
    static M08LObjectOverrule         sObject;
    static M08LDrawableOverrule       sDrawable;
    static M08LGeometryOverrule       sGeometry;
    static M08LTransformOverrule      sTransform;
    static M08LOsnapOverrule          sOsnap;
    static M08LSubentityOverrule      sSubentity;
    static M08LPropertiesOverrule     sProperties;
    static M08LHighlightOverrule      sHighlight;
    static M08LHighlightStateOverrule sHighlightState;
    static M08LVisibilityOverrule     sVisibility;
    static M08LGripOverrule           sGrip;
    static M08LQueryXOverrule         sQueryX;
    static M08LDimensionStyleOverrule sDimensionStyle;

    // overrule.install (generic) maps to the AcDbObject overrule (the broadest DB base).
    if (installOp == "overrule.install" || installOp == "overrule.object.install") {
        pOv = &sObject; pOvClass = AcDbObjectOverrule::desc(); className = "AcDbObjectOverrule"; return true;
    }
    if (installOp == "overrule.drawable.install") {
        pOv = &sDrawable; pOvClass = AcGiDrawableOverrule::desc(); className = "AcGiDrawableOverrule"; return true;
    }
    if (installOp == "overrule.geometry.install") {
        pOv = &sGeometry; pOvClass = AcDbGeometryOverrule::desc(); className = "AcDbGeometryOverrule"; return true;
    }
    if (installOp == "overrule.transform.install") {
        pOv = &sTransform; pOvClass = AcDbTransformOverrule::desc(); className = "AcDbTransformOverrule"; return true;
    }
    if (installOp == "overrule.osnap.install") {
        pOv = &sOsnap; pOvClass = AcDbOsnapOverrule::desc(); className = "AcDbOsnapOverrule"; return true;
    }
    if (installOp == "overrule.subentity.install") {
        pOv = &sSubentity; pOvClass = AcDbSubentityOverrule::desc(); className = "AcDbSubentityOverrule"; return true;
    }
    if (installOp == "overrule.properties.install") {
        pOv = &sProperties; pOvClass = AcDbPropertiesOverrule::desc(); className = "AcDbPropertiesOverrule"; return true;
    }
    if (installOp == "overrule.highlight.install") {
        pOv = &sHighlight; pOvClass = AcDbHighlightOverrule::desc(); className = "AcDbHighlightOverrule"; return true;
    }
    if (installOp == "overrule.highlightstate.install") {
        pOv = &sHighlightState; pOvClass = AcDbHighlightStateOverrule::desc(); className = "AcDbHighlightStateOverrule"; return true;
    }
    if (installOp == "overrule.visibility.install") {
        pOv = &sVisibility; pOvClass = AcDbVisibilityOverrule::desc(); className = "AcDbVisibilityOverrule"; return true;
    }
    if (installOp == "overrule.grip.install") {
        pOv = &sGrip; pOvClass = AcDbGripOverrule::desc(); className = "AcDbGripOverrule"; return true;
    }
    if (installOp == "overrule.queryx.install") {
        pOv = &sQueryX; pOvClass = AcRxQueryXOverrule::desc(); className = "AcRxQueryXOverrule"; return true;
    }
    if (installOp == "overrule.dimstyle.install") {
        pOv = &sDimensionStyle; pOvClass = AcDbDimensionStyleOverrule::desc(); className = "AcDbDimensionStyleOverrule"; return true;
    }
    return false;
}

#endif // ARIADNE_M08L_OVERRULES

//============================================================================
// M08L shared helpers (file-scope statics; m08l-prefixed to avoid sibling collisions)
//============================================================================

// Pull a hex handle from the job ("handle", or args.handle).
static bool m08lFindHandle(const std::string& job, std::string& out)
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
static bool m08lFindStr(const std::string& job, const char* key, std::string& out)
{
    if (jsonFindString(job, key, out) && !out.empty())
        return true;
    std::string argsJson;
    if (jsonFindObject(job, "args", argsJson) &&
        jsonFindString(argsJson, key, out) && !out.empty())
        return true;
    return false;
}

// Open a model-resident entity for read by hex handle. Returns nullptr if it does not resolve or
// is not an entity. Caller closes.
static AcDbEntity* m08lOpenEntity(AcDbDatabase* pDb, const std::string& handleHex)
{
    AcDbObjectId id;
    if (!resolveHandle(pDb, handleHex, id))
        return nullptr;
    AcDbEntity* pEnt = nullptr;
    if (acdbOpenObject(pEnt, id, AcDb::kForRead) != Acad::eOk)
        return nullptr;
    return pEnt;
}

static std::string m08lPointJson(const AcGePoint3d& p)
{
    std::ostringstream o; o.precision(kJsonDoublePrecision);
    o << "[" << p.x << "," << p.y << "," << p.z << "]";
    return o.str();
}

// Map an optional "regen_type" arg to an AcGiRegenType (default kAcGiStandardDisplay).
static AcGiRegenType m08lRegenType(const std::string& job)
{
    std::string s;
    if (!m08lFindStr(job, "regen_type", s))
        return kAcGiStandardDisplay;
    if (s == "shaded" || s == "shaded_display")           return kAcGiShadedDisplay;
    if (s == "explode" || s == "for_explode")             return kAcGiForExplode;
    if (s == "proxy" || s == "save_world_draw_for_proxy") return kAcGiSaveWorldDrawForProxy;
    if (s == "hide_or_shade")                             return kAcGiHideOrShadeCommand;
    return kAcGiStandardDisplay;
}

//============================================================================
// HasOp — every op id this family IMPLEMENTS (gate admission). Lockstep with the
// dispatch branches below (asserted by tests/unit/test_m08l_handlers.py).
//============================================================================
static bool m08lHasOp(const std::string& op)
{
    return
        // T01 — worldDraw / graphics capture (8)
        op == "render.draw.worldgeom" ||
        op == "render.draw.viewportgeom" ||
        op == "render.drawable.def" ||
        op == "render.traits.set" ||
        op == "render.polyline.helper" ||
        op == "render.facedata.attach" ||
        op == "render.context.query" ||
        op == "render.entity.worlddraw_override" ||
        // T02 — overrule register lifecycle (13; overrule.dimstyle.install DEFERRED)
        op == "overrule.install" ||
        op == "overrule.object.install" ||
        op == "overrule.drawable.install" ||
        op == "overrule.geometry.install" ||
        op == "overrule.transform.install" ||
        op == "overrule.osnap.install" ||
        op == "overrule.subentity.install" ||
        op == "overrule.properties.install" ||
        op == "overrule.highlight.install" ||
        op == "overrule.highlightstate.install" ||
        op == "overrule.visibility.install" ||
        op == "overrule.grip.install" ||
        op == "overrule.queryx.install" ||
        op == "overrule.dimstyle.install" ||
        // T02 — overrule global/query/remove + grips read (5)
        op == "overrule.global.enable" ||
        op == "overrule.applicable" ||
        op == "overrule.query.has" ||
        op == "overrule.remove" ||
        op == "inspect.entity.grips" ||
        false;
}

//============================================================================
// Dispatch — handle the op (append result + status, return true) or return false.
//============================================================================
static bool m08lDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    if (!m08lHasOp(op))
        return false;

    AcDbDatabase* pDb = ctx.pDb;        // working (router-staged) database; non-null (gated upstream)
    const std::string& job = ctx.job;   // raw job JSON (arg parsing via jsonFind*)

    //========================================================================
    // T01 — worldDraw / graphics capture
    //========================================================================

    // render.draw.worldgeom / render.entity.worlddraw_override / render.polyline.helper /
    // render.facedata.attach — drive AcGiDrawable::worldDraw() on an entity into the hostless
    // collector and report the geometry primitives it emitted. The real, view-independent
    // graphics elaboration (no GS, no viewport). READ-only. The four ops share the elaboration
    // and differ only in the extra slice they surface (worlddraw_override frames it as the
    // entity's subWorldDraw output; polyline.helper highlights the polyline path; facedata.attach
    // highlights shells/meshes that carried AcGiFaceData).
    if (op == "render.draw.worldgeom" || op == "render.entity.worlddraw_override" ||
        op == "render.polyline.helper" || op == "render.facedata.attach") {
        std::string handle;
        if (!m08lFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", op + " requires 'handle'");
            return true;
        }
        AcDbEntity* pEnt = m08lOpenEntity(pDb, handle);
        if (pEnt == nullptr) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "no entity for handle " + handle);
            return true;
        }
        AriadneReadTransaction rt(pDb);
        M08LGraphicsTally tally;
        M08LCollectWorldDraw wd(pDb, tally, m08lRegenType(job));
        const Adesk::Boolean drew = pEnt->worldDraw(&wd);   // hostless elaboration
        const std::string entClass = (pEnt->isA() != nullptr) ? acharToAscii(pEnt->isA()->name()) : std::string();
        pEnt->close();

        std::ostringstream o; o.precision(kJsonDoublePrecision);
        o << "\"handle\":" << njsonStr(handle)
          << ",\"entity_class\":" << njsonStr(entClass)
          << ",\"world_draw_returned\":" << (drew == Adesk::kTrue ? "true" : "false")
          << ",\"primitive_total\":" << tally.total()
          << ",\"vertex_total\":" << tally.vertexTotal
          << ",\"primitives\":{"
          << "\"circle\":" << tally.circle
          << ",\"circular_arc\":" << tally.circularArc
          << ",\"elliptical_arc\":" << tally.ellipticalArc
          << ",\"polyline\":" << tally.polyline
          << ",\"polygon\":" << tally.polygon
          << ",\"poly_polyline\":" << tally.polyPolyline
          << ",\"poly_polygon\":" << tally.polyPolygon
          << ",\"mesh\":" << tally.mesh
          << ",\"shell\":" << tally.shell
          << ",\"text\":" << tally.text
          << ",\"xline\":" << tally.xline
          << ",\"ray\":" << tally.ray
          << ",\"pline\":" << tally.pline
          << ",\"image\":" << tally.image
          << ",\"draw_nested\":" << tally.draw
          << ",\"edge\":" << tally.edge
          << ",\"dots\":" << tally.dots
          << "}";
        if (op == "render.facedata.attach")
            o << ",\"face_data_bearing_surfaces\":" << tally.faceDataSeen;
        if (op == "render.polyline.helper")
            o << ",\"polyline_calls\":" << (tally.polyline + tally.polyPolyline);
        if (tally.haveSample)
            o << ",\"first_vertex\":" << m08lPointJson(tally.sample);
        if (tally.extentsSet)
            o << ",\"extents\":{\"min\":" << m08lPointJson(tally.extMin)
              << ",\"max\":" << m08lPointJson(tally.extMax) << "}";
        r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
        return true;
    }

    // render.draw.viewportgeom — drive viewportDraw on an entity and report the eye/display-space geometry primitives it emitted.
    if (op == "render.draw.viewportgeom") {
        std::string handle;
        if (!m08lFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", op + " requires 'handle'");
            return true;
        }
        AcDbEntity* pEnt = m08lOpenEntity(pDb, handle);
        if (pEnt == nullptr) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "no entity for handle " + handle);
            return true;
        }
        AriadneReadTransaction rt(pDb);
        M08LGraphicsTally tally;
        M08LCollectWorldDraw wd(pDb, tally, m08lRegenType(job));
        const Adesk::Boolean drewWorld = pEnt->worldDraw(&wd);
        Adesk::Boolean drewViewport = Adesk::kFalse;
        if (!drewWorld) {
            M08LCollectViewportDraw vd(pDb, tally, m08lRegenType(job));
            pEnt->viewportDraw(&vd);
            drewViewport = Adesk::kTrue;
        }
        const std::string entClass = (pEnt->isA() != nullptr) ? acharToAscii(pEnt->isA()->name()) : std::string();
        pEnt->close();

        std::ostringstream o; o.precision(kJsonDoublePrecision);
        o << "\"handle\":" << njsonStr(handle)
          << ",\"entity_class\":" << njsonStr(entClass)
          << ",\"world_draw_returned\":" << (drewWorld == Adesk::kTrue ? "true" : "false")
          << ",\"viewport_draw_called\":" << (drewViewport == Adesk::kTrue ? "true" : "false")
          << ",\"primitive_total\":" << tally.total()
          << ",\"vertex_total\":" << tally.vertexTotal
          << ",\"primitives\":{"
          << "\"circle\":" << tally.circle
          << ",\"circular_arc\":" << tally.circularArc
          << ",\"elliptical_arc\":" << tally.ellipticalArc
          << ",\"polyline\":" << tally.polyline
          << ",\"polygon\":" << tally.polygon
          << ",\"poly_polyline\":" << tally.polyPolyline
          << ",\"poly_polygon\":" << tally.polyPolygon
          << ",\"mesh\":" << tally.mesh
          << ",\"shell\":" << tally.shell
          << ",\"text\":" << tally.text
          << ",\"xline\":" << tally.xline
          << ",\"ray\":" << tally.ray
          << ",\"pline\":" << tally.pline
          << ",\"image\":" << tally.image
          << ",\"draw_nested\":" << tally.draw
          << ",\"edge\":" << tally.edge
          << ",\"dots\":" << tally.dots
          << "}";
        if (tally.haveSample)
            o << ",\"first_vertex\":" << m08lPointJson(tally.sample);
        r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
        return true;
    }

    // render.drawable.def — AcGiDrawable identity/protocol of the entity behind a handle:
    // isPersistent / id / drawableType. READ-only.
    if (op == "render.drawable.def") {
        std::string handle;
        if (!m08lFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "render.drawable.def requires 'handle'");
            return true;
        }
        AcDbEntity* pEnt = m08lOpenEntity(pDb, handle);
        if (pEnt == nullptr) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "no entity for handle " + handle);
            return true;
        }
        AriadneReadTransaction rt(pDb);
        AcGiDrawable* pDrawable = static_cast<AcGiDrawable*>(pEnt);   // AcDbEntity IS-A AcGiDrawable
        const bool persistent = (pDrawable->isPersistent() == Adesk::kTrue);
        const AcGiDrawable::DrawableType dt = pDrawable->drawableType();
        const bool idMatches = (pDrawable->id() == pEnt->objectId());
        const std::string entClass = (pEnt->isA() != nullptr) ? acharToAscii(pEnt->isA()->name()) : std::string();
        pEnt->close();
        r << "\"result\":{\"handle\":" << njsonStr(handle)
          << ",\"entity_class\":" << njsonStr(entClass)
          << ",\"is_persistent\":" << (persistent ? "true" : "false")
          << ",\"id_resolves_to_self\":" << (idMatches ? "true" : "false")
          << ",\"drawable_type\":" << static_cast<int>(dt)
          << ",\"is_geometry_drawable\":" << (dt == AcGiDrawable::kGeometry ? "true" : "false")
          << "},\"status\":\"ok\"}";
        return true;
    }

    // render.traits.set — drive the entity's worldDraw and report the AcGiSubEntityTraits the
    // entity SET during elaboration (color/lineweight/fill/linetype-scale/thickness). Real, hostless.
    if (op == "render.traits.set") {
        std::string handle;
        if (!m08lFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "render.traits.set requires 'handle'");
            return true;
        }
        AcDbEntity* pEnt = m08lOpenEntity(pDb, handle);
        if (pEnt == nullptr) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "no entity for handle " + handle);
            return true;
        }
        AriadneReadTransaction rt(pDb);
        M08LGraphicsTally tally;
        M08LCollectWorldDraw wd(pDb, tally, m08lRegenType(job));
        pEnt->worldDraw(&wd);
        const M08LCollectTraits& tr = wd.traits();
        pEnt->close();
        r << "\"result\":{\"handle\":" << njsonStr(handle)
          << ",\"color_set\":" << (tr.colorSet() ? "true" : "false")
          << ",\"color\":" << static_cast<int>(tr.color())
          << ",\"true_color_set\":" << (tr.trueColorSet() ? "true" : "false")
          << ",\"lineweight_set\":" << (tr.lineWeightSet() ? "true" : "false")
          << ",\"lineweight\":" << static_cast<int>(tr.lineWeight())
          << ",\"linetype_scale\":" << tr.lineTypeScale()
          << ",\"thickness\":" << tr.thickness()
          << ",\"fill_type\":" << static_cast<int>(tr.fillType())
          << "},\"status\":\"ok\"}";
        return true;
    }

    // render.context.query — construct a hostless AcGiWorldDraw collector and report the
    // AcGiCommonDraw/AcGiContext query surface (regenType / numberOfIsolines / isDragging /
    // context.database). Proves the collector's context is well-formed without an entity. READ.
    if (op == "render.context.query") {
        M08LGraphicsTally tally;
        M08LCollectWorldDraw wd(pDb, tally, m08lRegenType(job));
        AcGiContext* pCtx = wd.context();
        const bool dbBound = (pCtx != nullptr && pCtx->database() == pDb);
        const bool plot = (pCtx != nullptr && pCtx->isPlotGeneration());
        r << "\"result\":{\"regen_type\":" << static_cast<int>(wd.regenType())
          << ",\"is_standard_display\":" << (wd.regenType() == kAcGiStandardDisplay ? "true" : "false")
          << ",\"number_of_isolines\":" << wd.numberOfIsolines()
          << ",\"is_dragging\":" << (wd.isDragging() == Adesk::kTrue ? "true" : "false")
          << ",\"regen_abort\":" << (wd.regenAbort() == Adesk::kTrue ? "true" : "false")
          << ",\"context_present\":" << (pCtx != nullptr ? "true" : "false")
          << ",\"context_database_bound\":" << (dbBound ? "true" : "false")
          << ",\"is_plot_generation\":" << (plot ? "true" : "false")
          << "},\"status\":\"ok\"}";
        return true;
    }

    //========================================================================
    // T02 — overrule register / query / remove / enable lifecycle
    //========================================================================

    // overrule.{install,object,drawable,geometry,transform,osnap,subentity,properties,highlight,
    //   highlightstate,visibility,grip,queryx}.install — construct the matching concrete overrule
    // and addOverrule() it against AcDbEntity::desc() (AcRxObject::desc() for queryx, or an
    // explicit "target_class"). Reports registered + the overrule class + that hasOverrule
    // confirms it (with global overruling momentarily ON). Then immediately removeOverrule() and
    // restores the global flag so this probe leaves the registry exactly as found. The EFFECT
    // fires only in-app — reported honestly (effect_fires:"in_app_only"), never faked.
    {
        AcRxOverrule* pOv = nullptr; AcRxClass* pOvClass = nullptr; const char* className = nullptr;
        if (op.rfind("overrule.", 0) == 0 &&
            op != "overrule.global.enable" && op != "overrule.applicable" &&
            op != "overrule.query.has" && op != "overrule.remove" &&
            m08lOverruleFor(op, pOv, pOvClass, className)) {
            AcRxClass* target = (op == "overrule.queryx.install") ? AcRxObject::desc() :
                (op == "overrule.dimstyle.install" ? AcDbDimension::desc() : AcDbEntity::desc());
            std::string targetName;
            if (m08lFindStr(job, "target_class", targetName)) {
                if (targetName == "AcDbObject")      target = AcDbObject::desc();
                else if (targetName == "AcDbEntity") target = AcDbEntity::desc();
                else if (targetName == "AcDbDimension") target = AcDbDimension::desc();
                else if (targetName == "AcRxObject") target = AcRxObject::desc();
            }
            const bool overrulingWasOn = AcRxOverrule::isOverruling();
            const Acad::ErrorStatus addEs = AcRxOverrule::addOverrule(target, pOv, /*bAddAtLast*/ true);
            const bool registered = (addEs == Acad::eOk);
            AcRxOverrule::setIsOverruling(true);   // hasOverrule reports true only when overruling is on

            // Subject for the applicability/registration query: a transient AcDbPoint (IS-A
            // AcRxObject AND AcDbEntity, concrete), valid for both target families. AcRxObject
            // itself is abstract (protected ctor) so it cannot be instantiated directly.
            bool hasOv = false, applicable = false;
            {
                AcDbPoint* pPt = new AcDbPoint(AcGePoint3d(0, 0, 0));
                hasOv = AcRxOverrule::hasOverrule(pPt, pOvClass);
                applicable = pOv->isApplicable(pPt);
                delete pPt;
            }
            const Acad::ErrorStatus remEs = AcRxOverrule::removeOverrule(target, pOv);
            AcRxOverrule::setIsOverruling(overrulingWasOn);   // restore global state
            r << "\"result\":{\"overrule_class\":" << njsonStr(std::string(className))
              << ",\"target_class\":" << njsonStr(acharToAscii(target->name()))
              << ",\"registered\":" << (registered ? "true" : "false")
              << ",\"add_status\":" << static_cast<int>(addEs)
              << ",\"has_overrule_after_add\":" << (hasOv ? "true" : "false")
              << ",\"is_applicable\":" << (applicable ? "true" : "false")
              << ",\"removed\":" << (remEs == Acad::eOk ? "true" : "false")
              << ",\"effect_fires\":\"in_app_only\""
              << "},\"status\":\"" << (registered ? "ok" : "error") << "\"}";
            return true;
        }
    }

    // overrule.global.enable — AcRxOverrule::setIsOverruling + isOverruling (the global
    // application-wide overruling switch). Reads current; if "enable" arg present, sets it,
    // observes, then RESTORES the original (non-destructive of global state).
    if (op == "overrule.global.enable") {
        const bool before = AcRxOverrule::isOverruling();
        double enableRaw = 0.0;
        std::string argsJson; jsonFindObject(job, "args", argsJson);
        const bool haveEnable = jsonFindNumber(job, "enable", enableRaw) ||
                                jsonFindNumber(argsJson, "enable", enableRaw);
        bool observedAfterSet = before;
        if (haveEnable) {
            const bool want = (enableRaw != 0.0);
            AcRxOverrule::setIsOverruling(want);
            observedAfterSet = AcRxOverrule::isOverruling();
            AcRxOverrule::setIsOverruling(before);   // restore
        }
        r << "\"result\":{\"is_overruling\":" << (before ? "true" : "false")
          << ",\"toggle_requested\":" << (haveEnable ? "true" : "false")
          << ",\"observed_after_set\":" << (observedAfterSet ? "true" : "false")
          << ",\"restored\":" << (AcRxOverrule::isOverruling() == before ? "true" : "false")
          << "},\"status\":\"ok\"}";
        return true;
    }

    // overrule.applicable / overrule.query.has — register a chosen overrule (default object), turn
    // global overruling on, and report isApplicable(subject) / hasOverrule(subject, class) for the
    // entity behind 'handle' (or a transient point). Removes the registration + restores the flag.
    if (op == "overrule.applicable" || op == "overrule.query.has") {
        std::string kind;
        if (!m08lFindStr(job, "overrule_kind", kind))
            kind = "object";
        AcRxOverrule* pOv = nullptr; AcRxClass* pOvClass = nullptr; const char* className = nullptr;
        if (!m08lOverruleFor("overrule." + kind + ".install", pOv, pOvClass, className))
            m08lOverruleFor("overrule.object.install", pOv, pOvClass, className);   // fallback
        AcRxClass* target = AcDbEntity::desc();
        const bool overrulingWasOn = AcRxOverrule::isOverruling();
        const Acad::ErrorStatus addEs = AcRxOverrule::addOverrule(target, pOv, true);
        AcRxOverrule::setIsOverruling(true);

        std::string handle;
        bool usedHandle = false, applicable = false, hasOv = false;
        std::string subjectClass;
        AcDbEntity* pEnt = nullptr;
        if (m08lFindHandle(job, handle))
            pEnt = m08lOpenEntity(pDb, handle);
        if (pEnt != nullptr) {
            usedHandle = true;
            subjectClass = (pEnt->isA() != nullptr) ? acharToAscii(pEnt->isA()->name()) : std::string();
            applicable = pOv->isApplicable(pEnt);
            hasOv = AcRxOverrule::hasOverrule(pEnt, pOvClass);
            pEnt->close();
        } else {
            AcDbPoint* pPt = new AcDbPoint(AcGePoint3d(0, 0, 0));
            subjectClass = "AcDbPoint";
            applicable = pOv->isApplicable(pPt);
            hasOv = AcRxOverrule::hasOverrule(pPt, pOvClass);
            delete pPt;
        }
        const Acad::ErrorStatus remEs = AcRxOverrule::removeOverrule(target, pOv);
        AcRxOverrule::setIsOverruling(overrulingWasOn);

        r << "\"result\":{\"overrule_class\":" << njsonStr(std::string(className))
          << ",\"subject_class\":" << njsonStr(subjectClass)
          << ",\"used_handle\":" << (usedHandle ? "true" : "false")
          << ",\"registered\":" << (addEs == Acad::eOk ? "true" : "false")
          << ",\"is_applicable\":" << (applicable ? "true" : "false")
          << ",\"has_overrule\":" << (hasOv ? "true" : "false")
          << ",\"removed\":" << (remEs == Acad::eOk ? "true" : "false")
          << "},\"status\":\"" << (addEs == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }

    // overrule.remove — full add→remove round-trip on a chosen overrule kind, proving
    // removeOverrule() unregisters it (hasOverrule false afterward). Default kind: object.
    if (op == "overrule.remove") {
        std::string kind;
        if (!m08lFindStr(job, "overrule_kind", kind))
            kind = "object";
        AcRxOverrule* pOv = nullptr; AcRxClass* pOvClass = nullptr; const char* className = nullptr;
        if (!m08lOverruleFor("overrule." + kind + ".install", pOv, pOvClass, className))
            m08lOverruleFor("overrule.object.install", pOv, pOvClass, className);
        AcRxClass* target = AcDbEntity::desc();
        const bool overrulingWasOn = AcRxOverrule::isOverruling();
        const Acad::ErrorStatus addEs = AcRxOverrule::addOverrule(target, pOv, true);
        AcRxOverrule::setIsOverruling(true);
        AcDbPoint* pPt = new AcDbPoint(AcGePoint3d(0, 0, 0));
        const bool hadBefore = AcRxOverrule::hasOverrule(pPt, pOvClass);
        const Acad::ErrorStatus remEs = AcRxOverrule::removeOverrule(target, pOv);
        const bool hasAfter = AcRxOverrule::hasOverrule(pPt, pOvClass);
        delete pPt;
        AcRxOverrule::setIsOverruling(overrulingWasOn);
        r << "\"result\":{\"overrule_class\":" << njsonStr(std::string(className))
          << ",\"added\":" << (addEs == Acad::eOk ? "true" : "false")
          << ",\"had_overrule_before_remove\":" << (hadBefore ? "true" : "false")
          << ",\"remove_status\":" << static_cast<int>(remEs)
          << ",\"has_overrule_after_remove\":" << (hasAfter ? "true" : "false")
          << ",\"removed\":" << ((remEs == Acad::eOk && !hasAfter) ? "true" : "false")
          << "},\"status\":\"" << ((remEs == Acad::eOk && !hasAfter) ? "ok" : "error") << "\"}";
        return true;
    }

    // inspect.entity.grips — AcDbEntity::getGripPoints(AcGePoint3dArray&, osnapModes, geomIds):
    // the simple grip-point read. The entity computes its grip points without an editor/GS;
    // serialize the grip point list. READ-only, hostless.
    if (op == "inspect.entity.grips") {
        std::string handle;
        if (!m08lFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "inspect.entity.grips requires 'handle'");
            return true;
        }
        AcDbEntity* pEnt = m08lOpenEntity(pDb, handle);
        if (pEnt == nullptr) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "no entity for handle " + handle);
            return true;
        }
        AriadneReadTransaction rt(pDb);
        AcGePoint3dArray grips;
        AcDbIntArray osnapModes, geomIds;
        const Acad::ErrorStatus es = pEnt->getGripPoints(grips, osnapModes, geomIds);
        const std::string entClass = (pEnt->isA() != nullptr) ? acharToAscii(pEnt->isA()->name()) : std::string();
        pEnt->close();
        std::ostringstream o; o.precision(kJsonDoublePrecision);
        o << "\"handle\":" << njsonStr(handle)
          << ",\"entity_class\":" << njsonStr(entClass)
          << ",\"grip_status\":" << static_cast<int>(es)
          << ",\"grip_count\":" << grips.length()
          << ",\"grips\":[";
        for (int i = 0; i < grips.length(); ++i) { if (i) o << ","; o << m08lPointJson(grips[i]); }
        o << "]";
        r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
        return true;
    }

    // Lockstep guard: HasOp admitted this op but no branch handled it.
    emitNativeError(r, "OPERATION_DISPATCH_MISMATCH",
                    "m08lHasOp admitted '" + op + "' but m08lDispatch has no handler");
    return true;
}
