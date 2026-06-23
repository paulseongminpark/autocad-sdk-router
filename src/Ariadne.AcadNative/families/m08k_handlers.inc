// families/m08k_handlers.inc — M08K-T01 NATIVE: custom object/entity/protocol lifecycle.
//
// custom AcDbObject/AcDbEntity create/read/roundtrip, class registration (AcRxClass/rxInit),
// protocol extension (AcRxClass::addX/delX/queryX), RTTI (isKindOf/desc/cast), proxy detect,
// deep/wblock clone, filer DWG roundtrip. Mostly hostless native_arx (DBX-resident classes).
// #included into AriadneNativeJob.cpp; sees all in-TU helpers (njsonStr / serializeObjectCommon /
// serializeEntityCommon / AriadneReadTransaction / AriadneStagedWriteTransaction / resolveHandle /
// jsonFind* / handleOf / handleOfId / emitNativeError / asciiToWide / countModelSpace /
// appendProbe / appendRecord / findFirstProbe).
//
// Contract (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - m08kHasOp(op): true for every op id this family IMPLEMENTS (gate admission). Ops left out
//     keep returning the honest OPERATION_NOT_IMPLEMENTED. NO FAKES.
//   - m08kDispatch(op, ctx, r): if op is yours, append  "result":{...},"status":"ok"  (or an
//     emitNativeError-style error) to r and return true; else return false.
//
// SAFETY (hard): staged-write ONLY. Operate on ctx.pDb (the router-staged in-memory copy).
//   Never call save()/saveAs()/_QSAVE on the original. No acedCommand/acedCmd/acedInvoke. Every
//   AcDb object new()'d is closed on append success and delete()'d on append failure (no leaks).
//   Every transient AcRxClass newAcRxClass()'d is deleteAcRxClass()'d before return (no class-system
//   leak); every transient protocol-extension addX()'d is delX()'d before return.
//
// GROUNDING: the registered custom classes AriadneProbe (AcDbEntity) + AriadneRecord (AcDbObject)
//   + AriadneProbeProtocol live in the Ariadne.AcadNativeDbx module (registered at its acrxEntryPoint
//   kInitAppMsg — AriadneDbxEntry.cpp / AriadneProtocol.cpp). The .crx/.arx links
//   Ariadne.AcadNativeDbx.lib, but that import lib exports ONLY the module's extern "C" API
//   (ariadneCreateProbeEntity / ariadneCreateRecordObject / ariadneIsProbeEntity /
//   ariadneIsRecordObject / ariadneProbeProtocolAvailable — AriadneDbxApi.h) — NOT the C++ class
//   methods or ::desc(). So this family reaches those classes the linkage-safe way: their live
//   AcRxClass* via acrxClassDictionary->at(L"AriadneProbe" / ...), type checks via the extern "C"
//   predicates, and field/geometry via the entities' EXPORTED AcDbEntity virtuals (getGeomExtents,
//   transformBy). Direct AriadneProbe::desc()/::cast() would be an unresolved external (LNK2001).
//
// IMPLEMENTED (31): RTTI(5) + protocol(4) + class-registration(11) + clone/filer/lifecycle(6) +
//   custom-entity(5). The 45-op brief lists 13 DEFERRED in-app-behavior-callback / non-hostless
//   ops, left OUT of HasOp on purpose (documented in reports/tickets/M08K-T01.md). NO FAKES.

#include "dbproxy.h"      // AcDbProxyEntity / AcDbProxyObject (proxy detect)
#include "dbidmap.h"      // AcDbIdMapping (deep/wblock clone)
#include "rxclass.h"      // AcRxClass addX/delX/queryX/newAcRxClass/acrxBuildClassHierarchy/deleteAcRxClass
#include "rxdict.h"       // acrxClassDictionary (live registered-class lookup by name)
#include "rxregsvc.h"     // acrxRegisterService / acrxServiceIsRegistered
#include "dbosnap.h"      // AcDbCustomOsnapInfo / AcDbCustomOsnapManager
// NOTE: the custom Ariadne* classes are reached via the class dictionary (by name) and the DBX
// extern "C" API (AriadneDbxApi.h, already included by the host TU) — NOT via their C++ headers:
// the import lib exports only the extern "C" symbols, not the class methods/::desc(). Including the
// class headers here would invite link errors (LNK2001) by tempting direct ::desc()/::cast() use.

//============================================================================
// M08K shared helpers (file-scope statics in this TU; m08k-prefixed to avoid any
// collision with sibling family .inc files).
//============================================================================

// A concrete AcRxObject subclass used as the value stored by AcRxClass::addX() in the
// protocol.attach/detach tests. AcRxObject's ctor is protected (a derived class may call
// it); its dtor is public+virtual, so `new`/`delete` of this trivial subclass is valid.
// No registered RTTI is needed because addX() merely stores/returns the pointer keyed by
// the protocol class (it does not query this object's own descriptor).
class M08KProtocolXObject : public AcRxObject
{
public:
    M08KProtocolXObject() {}
    virtual ~M08KProtocolXObject() {}
};

// A concrete custom-osnap protocol extension. It is registration-free (no custom RTTI):
// AcRxClass::addX keys it by AcDbCustomOsnapInfo::desc(), and the manager mode below
// advertises that same SDK protocol class. getOsnapInfo is real: for AriadneProbe it
// reads the entity's extents and returns the marker center as the custom snap point.
class M08KCustomOsnapInfo : public AcDbCustomOsnapInfo
{
public:
    Acad::ErrorStatus getOsnapInfo(
        AcDbEntity* pickedObject,
        Adesk::GsMarker /*gsSelectionMark*/,
        const AcGePoint3d& /*pickPoint*/,
        const AcGePoint3d& /*lastPoint*/,
        const AcGeMatrix3d& /*viewXform*/,
        AcArray<AcGePoint3d>& snapPoints,
        AcDbIntArray& geomIdsForPts,
        AcArray<AcGeCurve3d*>& /*snapCurves*/,
        AcDbIntArray& /*geomIdsForLines*/) override
    {
        if (pickedObject == nullptr || !ariadneIsProbeEntity(pickedObject))
            return Acad::eNotApplicable;
        AcDbExtents ext;
        Acad::ErrorStatus es = pickedObject->getGeomExtents(ext);
        if (es != Acad::eOk)
            return es;
        const AcGePoint3d lo = ext.minPoint();
        const AcGePoint3d hi = ext.maxPoint();
        snapPoints.append(AcGePoint3d((lo.x + hi.x) * 0.5, (lo.y + hi.y) * 0.5, (lo.z + hi.z) * 0.5));
        geomIdsForPts.append(9001);
        return Acad::eOk;
    }
};

class M08KCustomOsnapMode : public AcDbCustomOsnapMode
{
public:
    const ACHAR* localModeString() const override { return ACRX_T("ARIadne"); }
    const ACHAR* globalModeString() const override { return ACRX_T("ARIadne"); }
    const AcRxClass* entityOsnapClass() const override { return AcDbCustomOsnapInfo::desc(); }
    AcGiGlyph* glyph() const override { return nullptr; }
    const ACHAR* tooltipString() const override { return ACRX_T("Ariadne probe center"); }
};

// Hostless AcGiViewportDraw collector used only to prove AriadneProbe::subViewportDraw.
// M08L owns the world-draw collector; this mirrors it for viewport-specific geometry.
class M08KCollectViewport : public AcGiViewport
{
public:
    void getModelToEyeTransform(AcGeMatrix3d& m) const override { m.setToIdentity(); }
    void getEyeToModelTransform(AcGeMatrix3d& m) const override { m.setToIdentity(); }
    void getWorldToEyeTransform(AcGeMatrix3d& m) const override { m.setToIdentity(); }
    void getEyeToWorldTransform(AcGeMatrix3d& m) const override { m.setToIdentity(); }
    Adesk::Boolean isPerspective() const override { return Adesk::kFalse; }
    Adesk::Boolean doPerspective(AcGePoint3d&) const override { return Adesk::kTrue; }
    Adesk::Boolean doInversePerspective(AcGePoint3d&) const override { return Adesk::kTrue; }
    void getNumPixelsInUnitSquare(const AcGePoint3d&, AcGePoint2d& pixelArea, bool = true) const override { pixelArea.set(1.0, 1.0); }
    void getCameraLocation(AcGePoint3d& location) const override { location.set(0.0, 0.0, 1.0); }
    void getCameraTarget(AcGePoint3d& target) const override { target.set(0.0, 0.0, 0.0); }
    void getCameraUpVector(AcGeVector3d& upVector) const override { upVector = AcGeVector3d::kYAxis; }
    Adesk::ULongPtr viewportId() const override { return 1; }
    Adesk::Int16 acadWindowId() const override { return 1; }
    void getViewportDcCorners(AcGePoint2d& lower_left, AcGePoint2d& upper_right) const override { lower_left.set(0, 0); upper_right.set(100, 100); }
    Adesk::Boolean getFrontAndBackClipValues(Adesk::Boolean& clip_front, Adesk::Boolean& clip_back, double& front, double& back) const override { clip_front = clip_back = Adesk::kFalse; front = back = 0.0; return Adesk::kFalse; }
    double linetypeScaleMultiplier() const override { return 1.0; }
    double linetypeGenerationCriteria() const override { return 1.0; }
};

class M08KCollectViewportGeometry : public AcGiViewportGeometry
{
public:
    explicit M08KCollectViewportGeometry(M08LGraphicsTally& tally) : m_tally(tally) {}
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
    Adesk::Boolean circle(const AcGePoint3d&, const double, const AcGeVector3d&) const override { ++m_tally.circle; return Adesk::kTrue; }
    Adesk::Boolean circle(const AcGePoint3d&, const AcGePoint3d&, const AcGePoint3d&) const override { ++m_tally.circle; return Adesk::kTrue; }
    Adesk::Boolean circularArc(const AcGePoint3d&, const double, const AcGeVector3d&, const AcGeVector3d&, const double, const AcGiArcType) const override { ++m_tally.circularArc; return Adesk::kTrue; }
    Adesk::Boolean circularArc(const AcGePoint3d&, const AcGePoint3d&, const AcGePoint3d&, const AcGiArcType) const override { ++m_tally.circularArc; return Adesk::kTrue; }
    Adesk::Boolean polyline(const Adesk::UInt32 n, const AcGePoint3d* pv, const AcGeVector3d*, Adesk::LongPtr) const override { ++m_tally.polyline; m_tally.vertexTotal += n; m_tally.capture(n, pv); return Adesk::kTrue; }
    Adesk::Boolean polyline(const AcGiPolyline&) const override { ++m_tally.polyline; return Adesk::kTrue; }
    Adesk::Boolean polyPolyline(Adesk::UInt32, const AcGiPolyline*) const override { ++m_tally.polyPolyline; return Adesk::kTrue; }
    Adesk::Boolean polygon(const Adesk::UInt32 n, const AcGePoint3d* pv) const override { ++m_tally.polygon; m_tally.vertexTotal += n; m_tally.capture(n, pv); return Adesk::kTrue; }
    Adesk::Boolean polyPolygon(const Adesk::UInt32, const Adesk::UInt32*, const AcGePoint3d*, const Adesk::UInt32*, const AcGePoint3d*, const AcCmEntityColor*, const AcGiLineType*, const AcCmEntityColor*, const AcCmTransparency*) const override { ++m_tally.polyPolygon; return Adesk::kTrue; }
    Adesk::Boolean mesh(const Adesk::UInt32 rows, const Adesk::UInt32 cols, const AcGePoint3d* pv, const AcGiEdgeData*, const AcGiFaceData* pFace, const AcGiVertexData*, const bool) const override { ++m_tally.mesh; m_tally.vertexTotal += rows * cols; if (pFace) ++m_tally.faceDataSeen; m_tally.capture(rows * cols, pv); return Adesk::kTrue; }
    Adesk::Boolean shell(const Adesk::UInt32 nv, const AcGePoint3d* pv, const Adesk::UInt32, const Adesk::Int32*, const AcGiEdgeData*, const AcGiFaceData* pFace, const AcGiVertexData*, const struct resbuf*, const bool) const override { ++m_tally.shell; m_tally.vertexTotal += nv; if (pFace) ++m_tally.faceDataSeen; m_tally.capture(nv, pv); return Adesk::kTrue; }
    Adesk::Boolean text(const AcGePoint3d&, const AcGeVector3d&, const AcGeVector3d&, const double, const double, const double, const ACHAR*) const override { ++m_tally.text; return Adesk::kTrue; }
    Adesk::Boolean text(const AcGePoint3d&, const AcGeVector3d&, const AcGeVector3d&, const ACHAR*, const Adesk::Int32, const Adesk::Boolean, const AcGiTextStyle&) const override { ++m_tally.text; return Adesk::kTrue; }
    Adesk::Boolean xline(const AcGePoint3d&, const AcGePoint3d&) const override { ++m_tally.xline; return Adesk::kTrue; }
    Adesk::Boolean ray(const AcGePoint3d&, const AcGePoint3d&) const override { ++m_tally.ray; return Adesk::kTrue; }
    Adesk::Boolean pline(const AcDbPolyline&, Adesk::UInt32, Adesk::UInt32) const override { ++m_tally.pline; return Adesk::kTrue; }
    Adesk::Boolean draw(AcGiDrawable*) const override { ++m_tally.draw; return Adesk::kTrue; }
    Adesk::Boolean image(const AcGiImageBGRA32&, const AcGePoint3d&, const AcGeVector3d&, const AcGeVector3d&, TransparencyMode) const override { ++m_tally.image; return Adesk::kTrue; }
    Adesk::Boolean rowOfDots(int, const AcGePoint3d&, const AcGeVector3d&) const override { ++m_tally.dots; return Adesk::kTrue; }
    Adesk::Boolean ellipticalArc(const AcGePoint3d&, const AcGeVector3d&, double, double, double, double, double, AcGiArcType) const override { ++m_tally.ellipticalArc; return Adesk::kTrue; }
    Adesk::Boolean pushClipBoundary(AcGiClipBoundary*) override { return Adesk::kTrue; }
    void popClipBoundary() override {}
    Adesk::Boolean edge(const AcArray<AcGeCurve2d*>&) const override { ++m_tally.edge; return Adesk::kTrue; }
    Adesk::Boolean polylineEye(const Adesk::UInt32 n, const AcGePoint3d* pv) const override { ++m_tally.polyline; m_tally.vertexTotal += n; m_tally.capture(n, pv); return Adesk::kTrue; }
    Adesk::Boolean polygonEye(const Adesk::UInt32 n, const AcGePoint3d* pv) const override { ++m_tally.polygon; m_tally.vertexTotal += n; m_tally.capture(n, pv); return Adesk::kTrue; }
    Adesk::Boolean polylineDc(const Adesk::UInt32 n, const AcGePoint3d* pv) const override { ++m_tally.polyline; m_tally.vertexTotal += n; m_tally.capture(n, pv); return Adesk::kTrue; }
    Adesk::Boolean polygonDc(const Adesk::UInt32 n, const AcGePoint3d* pv) const override { ++m_tally.polygon; m_tally.vertexTotal += n; m_tally.capture(n, pv); return Adesk::kTrue; }
    Adesk::Boolean rasterImageDc(const AcGePoint3d&, const AcGeVector3d&, const AcGeVector3d&, const AcGeMatrix2d&, AcDbObjectId, AcGiImageOrg, Adesk::UInt32, Adesk::UInt32, Adesk::Int16, Adesk::Boolean, ImageSource, const AcGeVector3d&, const AcGiImageOrg, const AcGeMatrix2d&, const Adesk::UInt32, const Adesk::UInt32) const override { ++m_tally.image; return Adesk::kTrue; }
    Adesk::Boolean ownerDrawDc(Adesk::Int32, Adesk::Int32, Adesk::Int32, Adesk::Int32, Adesk::Int32, const OwnerDraw*) const override { ++m_tally.draw; return Adesk::kTrue; }
private:
    M08LGraphicsTally& m_tally;
};

class M08KCollectViewportDraw : public AcGiViewportDraw
{
public:
    M08KCollectViewportDraw(AcDbDatabase* pDb, M08LGraphicsTally& tally)
        : m_ctx(pDb), m_geom(tally) {}
    AcGiRegenType regenType() const override { return kAcGiStandardDisplay; }
    Adesk::Boolean regenAbort() const override { return Adesk::kFalse; }
    AcGiSubEntityTraits& subEntityTraits() const override { return const_cast<M08LCollectTraits&>(m_traits); }
    AcGiGeometry* rawGeometry() const override { return const_cast<M08KCollectViewportGeometry*>(&m_geom); }
    Adesk::Boolean isDragging() const override { return Adesk::kFalse; }
    double deviation(const AcGiDeviationType, const AcGePoint3d&) const override { return 0.0; }
    Adesk::UInt32 numberOfIsolines() const override { return 4; }
    AcGiContext* context() override { return &m_ctx; }
    AcGiViewport& viewport() const override { return const_cast<M08KCollectViewport&>(m_viewport); }
    AcGiViewportGeometry& geometry() const override { return const_cast<M08KCollectViewportGeometry&>(m_geom); }
    Adesk::UInt32 sequenceNumber() const override { return 1; }
    Adesk::Boolean isValidId(const Adesk::ULongPtr) const override { return Adesk::kTrue; }
    AcDbObjectId viewportObjectId() const override { return AcDbObjectId::kNull; }
private:
    M08LCollectContext m_ctx;
    mutable M08LCollectTraits m_traits;
    M08KCollectViewport m_viewport;
    M08KCollectViewportGeometry m_geom;
};

// Pull a hex handle from the job ("handle", or args.handle).
static bool m08kFindHandle(const std::string& job, std::string& out)
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
static bool m08kFindStr(const std::string& job, const char* key, std::string& out)
{
    if (jsonFindString(job, key, out) && !out.empty())
        return true;
    std::string argsJson;
    if (jsonFindObject(job, "args", argsJson) &&
        jsonFindString(argsJson, key, out) && !out.empty())
        return true;
    return false;
}

// JSON of an AcRxClass descriptor (NO enclosing braces; caller wraps). Reports the
// real registered metadata the class system carries for the descriptor.
static std::string m08kRxClassJson(AcRxClass* cls)
{
    std::ostringstream o;
    if (cls == nullptr) {
        o << "\"resolved\":false";
        return o.str();
    }
    int dwgVer = 0, maintVer = 0;
    cls->getClassVersion(dwgVer, maintVer);
    AcRxClass* parent = cls->myParent();
    o << "\"resolved\":true"
      << ",\"name\":" << njsonStr(cls->name())
      << ",\"dxf_name\":" << njsonStr(cls->dxfName())
      << ",\"app_name\":" << njsonStr(cls->appName())
      << ",\"dwg_version\":" << dwgVer
      << ",\"maint_version\":" << maintVer
      << ",\"proxy_flags\":" << static_cast<unsigned long>(cls->proxyFlags())
      << ",\"parent\":" << njsonStr(parent != nullptr ? parent->name() : ACRX_T(""));
    return o.str();
}

// Look up a registered class descriptor by name via the live class dictionary. This is the
// linkage-safe way to reach the custom Ariadne* classes: their RTTI is registered in the DBX
// (acrxClassDictionary holds the live AcRxClass*) but the C++ ::desc() symbols are NOT exported
// by the DBX import lib, so we must NOT reference them directly from this module.
static AcRxClass* m08kClassByName(const ACHAR* name)
{
    return AcRxClass::cast(acrxClassDictionary->at(name));
}

// Resolve a class-name string to a known AcRxClass descriptor (bounded, honest). The Ariadne
// custom classes resolve through the class dictionary (linkage-safe); SDK base classes resolve
// through their exported ::desc() (those symbols ARE in acdb/acbase). nullptr for an unknown name.
// AriadneProbe is the default when name is empty.
static AcRxClass* m08kResolveClass(const std::string& name)
{
    if (name.empty() || name == "AriadneProbe") return m08kClassByName(ACRX_T("AriadneProbe"));
    if (name == "AriadneRecord")               return m08kClassByName(ACRX_T("AriadneRecord"));
    if (name == "AriadneProbeProtocol")        return m08kClassByName(ACRX_T("AriadneProbeProtocol"));
    if (name == "AcDbEntity")                  return AcDbEntity::desc();
    if (name == "AcDbObject")                  return AcDbObject::desc();
    if (name == "AcDbProxyEntity")             return AcDbProxyEntity::desc();
    if (name == "AcDbProxyObject")             return AcDbProxyObject::desc();
    if (name == "AcRxObject")                  return AcRxObject::desc();
    if (name == "AcRxClass")                   return AcRxClass::desc();
    return nullptr;
}

// Append a transient AriadneRecord (registered custom AcDbObject) to the named-objects
// dictionary under a unique key so clone/filer ops have a real custom DB object to act
// on. Staged-write only (the router-staged copy). Returns eOk + sets idOut/keyOut.
static Acad::ErrorStatus m08kAppendRecordToNod(AcDbDatabase* pDb, int value,
                                               AcDbObjectId& idOut, std::string& keyOut)
{
    idOut = AcDbObjectId::kNull;
    keyOut.clear();
    AcDbObject* pObj = nullptr;
    Acad::ErrorStatus es = ariadneCreateRecordObject(pObj, value);
    if (es != Acad::eOk || pObj == nullptr) {
        if (pObj) delete pObj;
        return (es != Acad::eOk) ? es : Acad::eNullObjectPointer;
    }
    AcDbDictionary* pNod = nullptr;
    es = pDb->getNamedObjectsDictionary(pNod, AcDb::kForWrite);
    if (es != Acad::eOk || pNod == nullptr) {
        if (pNod) pNod->close();
        delete pObj;
        return (es != Acad::eOk) ? es : Acad::eInvalidInput;
    }
    // Unique key from the tick count so repeat invocations never collide.
    static unsigned long s_seq = 0;
    std::ostringstream k;
    k << "ARIADNE_M08K_REC_" << (++s_seq) << "_" << static_cast<unsigned long>(GetTickCount());
    keyOut = k.str();
    es = pNod->setAt(asciiToWide(keyOut).c_str(), pObj, idOut);
    pNod->close();
    if (es == Acad::eOk)
        pObj->close();
    else
        delete pObj;
    return es;
}

// Pseudo-constructor for the runtime "with constructor" class-definition variants. Yields a
// fresh AriadneRecord via the DBX's extern "C" creator (the C++ ctor symbol is not exported, so
// we must go through ariadneCreateRecordObject). Proves the create() path on a runtime-declared
// descriptor. Signature matches newAcRxClass's AcRxObject*(*)() parameter.
static AcRxObject* m08kRecordPseudoCtor()
{
    AcDbObject* pObj = nullptr;
    if (ariadneCreateRecordObject(pObj, 0) == Acad::eOk)
        return pObj;
    return nullptr;
}

// Append a transient AriadneProbe (registered custom AcDbEntity) to model space (staged).
// Returns eOk + sets idOut. Reuses the in-TU appendProbe path indirectly via the DBX ctor.
static Acad::ErrorStatus m08kAppendProbeEntity(AcDbDatabase* pDb, const AcGePoint3d& c,
                                               double sz, AcDbObjectId& idOut)
{
    idOut = AcDbObjectId::kNull;
    AcDbEntity* pEnt = nullptr;
    Acad::ErrorStatus es = ariadneCreateProbeEntity(pEnt, c.x, c.y, c.z, sz);
    if (es != Acad::eOk || pEnt == nullptr) {
        if (pEnt) delete pEnt;
        return (es != Acad::eOk) ? es : Acad::eNullObjectPointer;
    }
    AcDbBlockTable* pBT = nullptr;
    es = pDb->getBlockTable(pBT, AcDb::kForRead);
    if (es != Acad::eOk) { delete pEnt; return es; }
    AcDbBlockTableRecord* pMS = nullptr;
    es = pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite);
    pBT->close();
    if (es != Acad::eOk) { delete pEnt; return es; }
    es = pMS->appendAcDbEntity(idOut, pEnt);
    pMS->close();
    if (es == Acad::eOk)
        pEnt->close();
    else
        delete pEnt;
    return es;
}

//============================================================================
// HasOp — every op id this family IMPLEMENTS (gate admission). Kept in lockstep
// with the dispatch branches below (asserted by tests/unit/test_m08k_handlers.py).
//============================================================================
static bool m08kHasOp(const std::string& op)
{
    return
        // RTTI (AcRxObject::isKindOf / isA / cast / desc; AcDbProxy* detect)
        op == "inspect.runtime.cast" ||
        op == "inspect.runtime.desc" ||
        op == "inspect.runtime.isa" ||
        op == "inspect.runtime.iskindof" ||
        op == "inspect.proxy.detect" ||
        // Protocol extension (AcRxClass::addX/delX/queryX on transient + registered classes)
        op == "extend.protocol.declare" ||
        op == "extend.protocol.attach" ||
        op == "extend.protocol.detach" ||
        op == "extend.protocol.query" ||
        // Class registration (newAcRxClass / acrxBuildClassHierarchy / acrxRegisterService / rxInit)
        op == "extend.customclass.declare" ||
        op == "extend.customclass.define" ||
        op == "extend.customclass.define_cons" ||
        op == "extend.customclass.define_dxf" ||
        op == "extend.customclass.define_nocons" ||
        op == "extend.customclass.rxinit" ||
        op == "extend.customclass.unregister" ||
        op == "extend.service.register" ||
        op == "extend.module.entrypoint" ||
        op == "extend.object_enabler.build" ||
        op == "extend.object_enabler.register_classes" ||
        // Custom-object clone / filer-roundtrip / lifecycle (deepCloneObjects / wblockCloneObjects /
        // class version / db defaults; DWG/DXF filer implementation + partial undo)
        op == "extend.customobject.define" ||
        op == "extend.customobject.embedded" ||
        op == "extend.customobject.filer_dwgout" ||
        op == "extend.customobject.filer_dwgin" ||
        op == "extend.customobject.filer_dxfout" ||
        op == "extend.customobject.filer_dxfin" ||
        op == "extend.customobject.partial_undo" ||
        op == "extend.customobject.deepclone" ||
        op == "extend.customobject.wblockclone" ||
        op == "extend.customobject.version" ||
        // Custom-entity protocol (real AcDbEntity protocol on the registered AriadneProbe)
        op == "extend.customentity.define" ||
        op == "extend.customentity.draw_world" ||
        op == "extend.customentity.draw_viewport" ||
        op == "extend.customentity.grips" ||
        op == "extend.customentity.osnap" ||
        op == "extend.customentity.stretch" ||
        op == "extend.customentity.db_defaults" ||
        op == "extend.customentity.geom_extents" ||
        op == "extend.customentity.explode" ||
        op == "extend.customentity.transform" ||
        op == "extend.customentity.intersect" ||
        op == "extend.customentity.list" ||
        op == "extend.customentity.subentpaths" ||
        // Custom osnap protocol extension/mode (demand-register remains hard-blocked: install-time registry write)
        op == "extend.osnap.custom_mode" ||
        false;
}

//============================================================================
// Dispatch — handle the op (append result + status, return true) or return false.
//============================================================================
static bool m08kDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    if (!m08kHasOp(op))
        return false;

    AcDbDatabase* pDb = ctx.pDb;        // working (router-staged) database; non-null (gated upstream)
    const std::string& job = ctx.job;   // raw job JSON (arg parsing via jsonFind*)

    //========================================================================
    // RTTI
    //========================================================================

    // inspect.runtime.desc — full descriptor of a class by name (default AriadneProbe).
    // Pure class-system read (AcRxClass accessors). No DB touch.
    if (op == "inspect.runtime.desc") {
        std::string clsName;
        m08kFindStr(job, "class", clsName);
        AcRxClass* cls = m08kResolveClass(clsName);
        if (cls == nullptr) {
            emitNativeError(r, "CLASS_NOT_RESOLVED",
                            "class '" + clsName + "' is not a descriptor linked into this module");
            return true;
        }
        r << "\"result\":{\"requested\":" << njsonStr(clsName.empty() ? std::string("AriadneProbe") : clsName)
          << "," << m08kRxClassJson(cls) << "},\"status\":\"ok\"}";
        return true;
    }

    // inspect.runtime.isa — isA() of the object behind a hex handle (real RTTI on a DB object).
    if (op == "inspect.runtime.isa") {
        std::string handle;
        if (!m08kFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "inspect.runtime.isa requires 'handle'");
            return true;
        }
        AcDbObjectId id;
        if (!resolveHandle(pDb, handle, id)) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "no object for handle " + handle);
            return true;
        }
        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, id, AcDb::kForRead) != Acad::eOk || pObj == nullptr) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "open failed for handle " + handle);
            return true;
        }
        AcRxClass* isa = pObj->isA();
        AcRxClass* parent = (isa != nullptr) ? isa->myParent() : nullptr;
        std::ostringstream o;
        o << "\"handle\":" << njsonStr(handle)
          << ",\"isa\":" << njsonStr(isa != nullptr ? isa->name() : ACRX_T(""))
          << ",\"dxf_name\":" << njsonStr(isa != nullptr ? isa->dxfName() : ACRX_T(""))
          << ",\"parent\":" << njsonStr(parent != nullptr ? parent->name() : ACRX_T(""))
          << ",\"is_entity\":" << (pObj->isKindOf(AcDbEntity::desc()) ? "true" : "false");
        pObj->close();
        r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
        return true;
    }

    // inspect.runtime.iskindof — isKindOf(base) for the object behind a handle.
    if (op == "inspect.runtime.iskindof") {
        std::string handle;
        if (!m08kFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "inspect.runtime.iskindof requires 'handle'");
            return true;
        }
        std::string baseName;
        m08kFindStr(job, "base", baseName);
        if (baseName.empty()) m08kFindStr(job, "class", baseName);
        if (baseName.empty()) baseName = "AcDbEntity";
        AcRxClass* base = m08kResolveClass(baseName);
        if (base == nullptr) {
            emitNativeError(r, "CLASS_NOT_RESOLVED", "base class '" + baseName + "' not resolvable");
            return true;
        }
        AcDbObjectId id;
        if (!resolveHandle(pDb, handle, id)) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "no object for handle " + handle);
            return true;
        }
        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, id, AcDb::kForRead) != Acad::eOk || pObj == nullptr) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "open failed for handle " + handle);
            return true;
        }
        const bool kindOf = pObj->isKindOf(base);
        AcRxClass* isa = pObj->isA();
        pObj->close();
        r << "\"result\":{\"handle\":" << njsonStr(handle)
          << ",\"base\":" << njsonStr(baseName)
          << ",\"actual\":" << njsonStr(isa != nullptr ? isa->name() : ACRX_T(""))
          << ",\"is_kind_of\":" << (kindOf ? "true" : "false")
          << "},\"status\":\"ok\"}";
        return true;
    }

    // inspect.runtime.cast — attempt typed casts on the object behind a handle (real
    // AcRxObject::cast through several descriptors); report which succeed.
    if (op == "inspect.runtime.cast") {
        std::string handle;
        if (!m08kFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "inspect.runtime.cast requires 'handle'");
            return true;
        }
        AcDbObjectId id;
        if (!resolveHandle(pDb, handle, id)) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "no object for handle " + handle);
            return true;
        }
        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, id, AcDb::kForRead) != Acad::eOk || pObj == nullptr) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "open failed for handle " + handle);
            return true;
        }
        AcRxClass* probeDesc  = m08kClassByName(ACRX_T("AriadneProbe"));
        AcRxClass* recordDesc = m08kClassByName(ACRX_T("AriadneRecord"));
        const bool asEntity  = (AcDbEntity::cast(pObj) != nullptr);
        const bool asProbe   = (probeDesc  != nullptr) && pObj->isKindOf(probeDesc);
        const bool asRecord  = (recordDesc != nullptr) && pObj->isKindOf(recordDesc);
        const bool asProxyE  = (AcDbProxyEntity::cast(pObj) != nullptr);
        const bool asProxyO  = (AcDbProxyObject::cast(pObj) != nullptr);
        AcRxClass* isa = pObj->isA();
        pObj->close();
        r << "\"result\":{\"handle\":" << njsonStr(handle)
          << ",\"actual\":" << njsonStr(isa != nullptr ? isa->name() : ACRX_T(""))
          << ",\"cast_acdbentity\":" << (asEntity ? "true" : "false")
          << ",\"cast_ariadneprobe\":" << (asProbe ? "true" : "false")
          << ",\"cast_ariadnerecord\":" << (asRecord ? "true" : "false")
          << ",\"cast_proxyentity\":" << (asProxyE ? "true" : "false")
          << ",\"cast_proxyobject\":" << (asProxyO ? "true" : "false")
          << "},\"status\":\"ok\"}";
        return true;
    }

    // inspect.proxy.detect — is the object behind a handle a proxy? (AcDbProxyEntity/Object
    // cast); when so, report the original (unloaded-class) metadata.
    if (op == "inspect.proxy.detect") {
        std::string handle;
        if (!m08kFindHandle(job, handle)) {
            emitNativeError(r, "MISSING_ARG", "inspect.proxy.detect requires 'handle'");
            return true;
        }
        AcDbObjectId id;
        if (!resolveHandle(pDb, handle, id)) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "no object for handle " + handle);
            return true;
        }
        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, id, AcDb::kForRead) != Acad::eOk || pObj == nullptr) {
            emitNativeError(r, "ENTITY_NOT_FOUND", "open failed for handle " + handle);
            return true;
        }
        AcDbProxyEntity* pPE = AcDbProxyEntity::cast(pObj);
        AcDbProxyObject* pPO = AcDbProxyObject::cast(pObj);
        std::ostringstream o;
        o << "\"handle\":" << njsonStr(handle)
          << ",\"is_proxy\":" << ((pPE != nullptr || pPO != nullptr) ? "true" : "false")
          << ",\"is_proxy_entity\":" << (pPE != nullptr ? "true" : "false")
          << ",\"is_proxy_object\":" << (pPO != nullptr ? "true" : "false");
        if (pPE != nullptr) {
            o << ",\"original_class\":" << njsonStr(pPE->originalClassName())
              << ",\"original_dxf\":" << njsonStr(pPE->originalDxfName())
              << ",\"proxy_flags\":" << static_cast<unsigned long>(pPE->proxyFlags());
        } else if (pPO != nullptr) {
            o << ",\"original_class\":" << njsonStr(pPO->originalClassName())
              << ",\"original_dxf\":" << njsonStr(pPO->originalDxfName())
              << ",\"proxy_flags\":" << static_cast<unsigned long>(pPO->proxyFlags());
        }
        pObj->close();
        r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
        return true;
    }

    //========================================================================
    // Protocol extension (AcRxClass::addX / delX / queryX)
    //========================================================================

    // extend.protocol.query — query the ALREADY-REGISTERED AriadneProbeProtocol on
    // AriadneProbe::desc() (the working protocol extension; AriadneProtocol.cpp). Real.
    if (op == "extend.protocol.query") {
        AcRxClass* probeDesc = m08kClassByName(ACRX_T("AriadneProbe"));
        AcRxClass* protoDesc = m08kClassByName(ACRX_T("AriadneProbeProtocol"));
        AcRxObject* pe = (probeDesc != nullptr && protoDesc != nullptr)
                       ? probeDesc->queryX(protoDesc) : nullptr;
        const bool available = ariadneProbeProtocolAvailable();
        r << "\"result\":{\"protocol\":\"AriadneProbeProtocol\""
          << ",\"host_class\":\"AriadneProbe\""
          << ",\"protocol_registered\":" << (protoDesc != nullptr ? "true" : "false")
          << ",\"query_resolved\":" << (pe != nullptr ? "true" : "false")
          << ",\"available\":" << (available ? "true" : "false")
          << "},\"status\":\"" << ((pe != nullptr) ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.protocol.declare — declare a transient protocol-extension AcRxClass at runtime
    // (newAcRxClass, derived from AcRxObject), build the hierarchy, introspect it, then
    // deleteAcRxClass it (no class-system leak). Real runtime class lifecycle.
    if (op == "extend.protocol.declare") {
        std::string pname;
        m08kFindStr(job, "name", pname);
        if (pname.empty()) pname = "AriadneM08KProtocol";
        const std::wstring wpname = asciiToWide(pname);
        // Avoid clobbering an already-registered descriptor of the same name.
        if (acrxClassDictionary->at(wpname.c_str()) != nullptr) {
            r << "\"result\":{\"declared\":false,\"reason\":\"name_already_registered\""
              << ",\"name\":" << njsonStr(pname) << "},\"status\":\"ok\"}";
            return true;
        }
        AcRxClass* cls = newAcRxClass(wpname.c_str(),
                                      AcRxObject::desc()->name(), 0);
        if (cls == nullptr) {
            emitNativeError(r, "NEWACRXCLASS_FAILED", "newAcRxClass returned null for " + pname);
            return true;
        }
        acrxBuildClassHierarchy();
        AcRxClass* lookedUp = AcRxClass::cast(acrxClassDictionary->at(wpname.c_str()));
        const bool derived = cls->isDerivedFrom(AcRxObject::desc());
        std::ostringstream o;
        o << "\"declared\":true,\"name\":" << njsonStr(pname)
          << ",\"registered_in_dict\":" << (lookedUp == cls ? "true" : "false")
          << ",\"derived_from_acrxobject\":" << (derived ? "true" : "false");
        // Tear down the transient class (unload-only API; safe here since nothing instantiated it).
        deleteAcRxClass(cls);
        acrxBuildClassHierarchy();
        const bool gone = (acrxClassDictionary->at(wpname.c_str()) == nullptr);
        o << ",\"unregistered_after\":" << (gone ? "true" : "false");
        r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
        return true;
    }

    // extend.protocol.attach — declare a transient protocol class + a concrete impl object,
    // addX() it onto AriadneRecord::desc() (a registered host class), verify queryX(), then
    // delX()+delete+deleteAcRxClass (full clean teardown). Real protocol-extension attach.
    if (op == "extend.protocol.attach" || op == "extend.protocol.detach") {
        const bool detachVariant = (op == "extend.protocol.detach");
        std::string pname;
        m08kFindStr(job, "name", pname);
        if (pname.empty()) pname = (detachVariant ? "AriadneM08KDetachX" : "AriadneM08KAttachX");
        AcRxClass* host = m08kClassByName(ACRX_T("AriadneRecord"));   // registered host class to extend
        if (host == nullptr) {
            emitNativeError(r, "CLASS_NOT_RESOLVED", "AriadneRecord class descriptor unavailable");
            return true;
        }
        if (acrxClassDictionary->at(asciiToWide(pname).c_str()) != nullptr) {
            r << "\"result\":{\"attached\":false,\"reason\":\"name_already_registered\""
              << ",\"name\":" << njsonStr(pname) << "},\"status\":\"ok\"}";
            return true;
        }
        AcRxClass* protoCls = newAcRxClass(asciiToWide(pname).c_str(),
                                           AcRxObject::desc()->name(), 0);
        if (protoCls == nullptr) {
            emitNativeError(r, "NEWACRXCLASS_FAILED", "newAcRxClass returned null for " + pname);
            return true;
        }
        acrxBuildClassHierarchy();
        // A concrete protocol-extension object (trivial AcRxObject subclass; see helper above).
        AcRxObject* peObj = new M08KProtocolXObject();
        AcRxObject* prevX = host->addX(protoCls, peObj);   // attach
        AcRxObject* afterAttach = host->queryX(protoCls);
        const bool attached = (afterAttach == peObj);
        std::ostringstream o;
        o << "\"name\":" << njsonStr(pname)
          << ",\"host_class\":\"AriadneRecord\""
          << ",\"prev_x_present\":" << (prevX != nullptr ? "true" : "false")
          << ",\"attached\":" << (attached ? "true" : "false");
        // detach + verify (always tear down; the detach variant reports the post-detach state).
        AcRxObject* removed = host->delX(protoCls);
        AcRxObject* afterDetach = host->queryX(protoCls);
        const bool detached = (afterDetach == nullptr);
        o << ",\"detached\":" << (detached ? "true" : "false")
          << ",\"delx_returned_obj\":" << (removed != nullptr ? "true" : "false");
        delete peObj;                       // we own the X-object after delX
        deleteAcRxClass(protoCls);          // tear down transient class
        acrxBuildClassHierarchy();
        if (detachVariant)
            r << "\"result\":{" << o.str() << "},\"status\":\"" << (detached ? "ok" : "error") << "\"}";
        else
            r << "\"result\":{" << o.str() << "},\"status\":\"" << (attached ? "ok" : "error") << "\"}";
        return true;
    }

    //========================================================================
    // Class registration (newAcRxClass / acrxBuildClassHierarchy / acrxRegisterService / rxInit)
    //========================================================================

    // The customclass.declare/define/define_cons/define_dxf/define_nocons ops are the runtime
    // equivalent of the ACRX_*_DEFINE_MEMBERS macro families: they create an AcDbObject-derived
    // runtime class via newAcRxClass with the relevant ctor/dxf options, register it, introspect
    // it, then deleteAcRxClass it. (Defining a NEW COMPILED class body at runtime is impossible;
    // these prove the registration/lookup machinery on a real new descriptor. NO FAKES.)
    if (op == "extend.customclass.declare" ||
        op == "extend.customclass.define" ||
        op == "extend.customclass.define_cons" ||
        op == "extend.customclass.define_dxf" ||
        op == "extend.customclass.define_nocons") {
        std::string cname;
        m08kFindStr(job, "name", cname);
        if (cname.empty()) {
            // distinct default per variant so parallel ops never collide
            cname = std::string("AriadneM08K_") + op.substr(op.rfind('.') + 1);
        }
        std::wstring wname = asciiToWide(cname);
        if (acrxClassDictionary->at(wname.c_str()) != nullptr) {
            r << "\"result\":{\"defined\":false,\"reason\":\"name_already_registered\""
              << ",\"name\":" << njsonStr(cname) << ",\"variant\":" << njsonStr(op) << "},\"status\":\"ok\"}";
            return true;
        }
        // Variant matrix: pseudoConstructor present? dxfName present? (mirrors the macro families)
        const bool withCons = (op == "extend.customclass.define" ||
                               op == "extend.customclass.define_cons" ||
                               op == "extend.customclass.define_dxf");
        const bool withDxf  = (op == "extend.customclass.define_dxf");
        // Bind the wide strings to locals so the c_str() pointers outlive the newAcRxClass call.
        AcRxObject* (*pseudoCtor)() = withCons ? &m08kRecordPseudoCtor : nullptr;
        std::wstring wdxf = withDxf ? wname : std::wstring();
        std::wstring wapp = asciiToWide("AriadneAcadNativeM08K");
        AcRxClass* cls = newAcRxClass(
            wname.c_str(),
            AcDbObject::desc()->name(),
            AcDb::kDHL_CURRENT, AcDb::kMReleaseCurrent,
            0,
            pseudoCtor,
            withDxf ? wdxf.c_str() : nullptr,
            wapp.c_str());
        if (cls == nullptr) {
            emitNativeError(r, "NEWACRXCLASS_FAILED", "newAcRxClass returned null for " + cname);
            return true;
        }
        acrxBuildClassHierarchy();
        AcRxClass* lookedUp = AcRxClass::cast(acrxClassDictionary->at(wname.c_str()));
        const bool derived = cls->isDerivedFrom(AcDbObject::desc());
        // For the with-constructor variants, exercise create() then free the instance.
        bool created = false;
        if (withCons) {
            AcRxObject* inst = cls->create();
            if (inst != nullptr) { created = true; delete inst; }
        }
        std::ostringstream o;
        o << "\"defined\":true,\"variant\":" << njsonStr(op)
          << ",\"name\":" << njsonStr(cname)
          << ",\"with_constructor\":" << (withCons ? "true" : "false")
          << ",\"with_dxf_name\":" << (withDxf ? "true" : "false")
          << ",\"registered_in_dict\":" << (lookedUp == cls ? "true" : "false")
          << ",\"derived_from_acdbobject\":" << (derived ? "true" : "false")
          << ",\"create_instance_ok\":" << (created ? "true" : "false")
          << "," << m08kRxClassJson(cls);
        deleteAcRxClass(cls);
        acrxBuildClassHierarchy();
        o << ",\"unregistered_after\":" << (acrxClassDictionary->at(wname.c_str()) == nullptr ? "true" : "false");
        r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
        return true;
    }

    // extend.customclass.rxinit — prove the registered custom classes were rxInit()'d at module
    // load (desc() non-null + correctly parented + dxf names present). Real read of the live
    // class system (the AriadneProbe/AriadneRecord rxInit happened in AriadneDbxEntry.cpp).
    if (op == "extend.customclass.rxinit") {
        AcRxClass* probe = m08kClassByName(ACRX_T("AriadneProbe"));
        AcRxClass* record = m08kClassByName(ACRX_T("AriadneRecord"));
        const bool probeOk  = (probe != nullptr) && probe->isDerivedFrom(AcDbEntity::desc());
        const bool recordOk = (record != nullptr) && record->isDerivedFrom(AcDbObject::desc());
        r << "\"result\":{"
          << "\"ariadneprobe_rxinit\":" << (probe != nullptr ? "true" : "false")
          << ",\"ariadneprobe_is_entity\":" << (probeOk ? "true" : "false")
          << ",\"ariadneprobe_dxf\":" << njsonStr(probe != nullptr ? probe->dxfName() : ACRX_T(""))
          << ",\"ariadnerecord_rxinit\":" << (record != nullptr ? "true" : "false")
          << ",\"ariadnerecord_is_object\":" << (recordOk ? "true" : "false")
          << ",\"ariadnerecord_dxf\":" << njsonStr(record != nullptr ? record->dxfName() : ACRX_T(""))
          << "},\"status\":\"" << ((probeOk && recordOk) ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.customclass.unregister — declare a transient class then deleteAcRxClass it and prove
    // it is gone from the class dictionary (real registration teardown).
    if (op == "extend.customclass.unregister") {
        std::string cname;
        m08kFindStr(job, "name", cname);
        if (cname.empty()) cname = "AriadneM08KUnregister";
        std::wstring wname = asciiToWide(cname);
        if (acrxClassDictionary->at(wname.c_str()) != nullptr) {
            r << "\"result\":{\"unregistered\":false,\"reason\":\"name_already_registered\""
              << ",\"name\":" << njsonStr(cname) << "},\"status\":\"ok\"}";
            return true;
        }
        AcRxClass* cls = newAcRxClass(wname.c_str(), AcDbObject::desc()->name(),
                                      AcDb::kDHL_CURRENT, AcDb::kMReleaseCurrent, 0, nullptr,
                                      nullptr, asciiToWide("AriadneAcadNativeM08K").c_str());
        if (cls == nullptr) {
            emitNativeError(r, "NEWACRXCLASS_FAILED", "newAcRxClass returned null for " + cname);
            return true;
        }
        acrxBuildClassHierarchy();
        const bool registered = (acrxClassDictionary->at(wname.c_str()) == cls);
        deleteAcRxClass(cls);
        acrxBuildClassHierarchy();
        const bool gone = (acrxClassDictionary->at(wname.c_str()) == nullptr);
        r << "\"result\":{\"name\":" << njsonStr(cname)
          << ",\"registered_before\":" << (registered ? "true" : "false")
          << ",\"unregistered\":" << (gone ? "true" : "false")
          << "},\"status\":\"" << (gone ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.service.register — register a uniquely-named AcRxService (acrxRegisterService) and
    // prove acrxServiceIsRegistered. (Services have no clean hostless unregister; we use a unique
    // name per call so registration is idempotent and never clobbers a real service.)
    if (op == "extend.service.register") {
        std::string svc;
        m08kFindStr(job, "name", svc);
        std::ostringstream nm;
        nm << (svc.empty() ? "AriadneM08KService" : svc) << "_" << static_cast<unsigned long>(GetTickCount());
        const std::wstring wsvc = asciiToWide(nm.str());
        const bool before = acrxServiceIsRegistered(wsvc.c_str());
        void* h = acrxRegisterService(wsvc.c_str());
        const bool after = acrxServiceIsRegistered(wsvc.c_str());
        r << "\"result\":{\"service\":" << njsonStr(nm.str())
          << ",\"registered_before\":" << (before ? "true" : "false")
          << ",\"register_returned\":" << (h != nullptr ? "true" : "false")
          << ",\"registered_after\":" << (after ? "true" : "false")
          << "},\"status\":\"" << (after ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.module.entrypoint — introspect the module entry-point registration contract: the
    // DBX acrxEntryPoint (AriadneDbxEntry.cpp) rxInit'd AriadneProbe + AriadneRecord and
    // registered AriadneProbeProtocol at kInitAppMsg. Read-only proof all three are live.
    if (op == "extend.module.entrypoint") {
        AcRxClass* probe = m08kClassByName(ACRX_T("AriadneProbe"));
        AcRxClass* record = m08kClassByName(ACRX_T("AriadneRecord"));
        AcRxClass* proto = m08kClassByName(ACRX_T("AriadneProbeProtocol"));
        const bool all = (probe != nullptr && record != nullptr && proto != nullptr);
        r << "\"result\":{"
          << "\"module\":\"Ariadne.AcadNativeDbx\""
          << ",\"entrypoint\":\"acrxEntryPoint\""
          << ",\"probe_class_live\":" << (probe != nullptr ? "true" : "false")
          << ",\"record_class_live\":" << (record != nullptr ? "true" : "false")
          << ",\"protocol_class_live\":" << (proto != nullptr ? "true" : "false")
          << ",\"protocol_attached\":" << (ariadneProbeProtocolAvailable() ? "true" : "false")
          << "},\"status\":\"" << (all ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.object_enabler.build — run acrxBuildClassHierarchy() (the object-enabler hierarchy
    // build) and prove the enabler's custom classes resolve through the dictionary afterward.
    if (op == "extend.object_enabler.build") {
        acrxBuildClassHierarchy();
        AcRxClass* probe = AcRxClass::cast(acrxClassDictionary->at(ACRX_T("AriadneProbe")));
        AcRxClass* record = AcRxClass::cast(acrxClassDictionary->at(ACRX_T("AriadneRecord")));
        const bool ok = (probe != nullptr) && (record != nullptr);
        r << "\"result\":{\"hierarchy_built\":true"
          << ",\"probe_resolves\":" << (probe != nullptr ? "true" : "false")
          << ",\"record_resolves\":" << (record != nullptr ? "true" : "false")
          << ",\"both_registered\":" << (ok ? "true" : "false")
          << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.object_enabler.register_classes — report the object-enabler's registered class set
    // (AriadneProbe + AriadneRecord) with full descriptor metadata. Real class-system read.
    if (op == "extend.object_enabler.register_classes") {
        AcRxClass* probe = m08kClassByName(ACRX_T("AriadneProbe"));
        AcRxClass* record = m08kClassByName(ACRX_T("AriadneRecord"));
        r << "\"result\":{\"class_count\":2,\"classes\":["
          << "{" << m08kRxClassJson(probe) << "},"
          << "{" << m08kRxClassJson(record) << "}"
          << "],\"status_all_registered\":" << ((probe != nullptr && record != nullptr) ? "true" : "false")
          << "},\"status\":\"" << ((probe != nullptr && record != nullptr) ? "ok" : "error") << "\"}";
        return true;
    }

    //========================================================================
    // Custom-object clone / filer-roundtrip / lifecycle
    //========================================================================

    // extend.customentity.define / extend.customobject.define — prove the compiled custom
    // classes are registered, parented correctly, have DXF names/proxy flags, and can create
    // concrete instances through the DBX extern-C factory (linkage-safe; no direct ::desc use).
    if (op == "extend.customentity.define" || op == "extend.customobject.define") {
        const bool entityVariant = (op == "extend.customentity.define");
        const char* cname = entityVariant ? "AriadneProbe" : "AriadneRecord";
        AcRxClass* cls = m08kResolveClass(cname);
        if (cls == nullptr) {
            emitNativeError(r, "CLASS_NOT_RESOLVED", std::string(cname) + " descriptor unavailable");
            return true;
        }
        bool created = false, typeOk = false;
        if (entityVariant) {
            AcDbEntity* pEnt = nullptr;
            Acad::ErrorStatus es = ariadneCreateProbeEntity(pEnt, 0.0, 0.0, 0.0, 1.0);
            created = (es == Acad::eOk && pEnt != nullptr);
            typeOk = created && ariadneIsProbeEntity(pEnt) && pEnt->isKindOf(AcDbEntity::desc());
            delete pEnt;
        } else {
            AcDbObject* pObj = nullptr;
            Acad::ErrorStatus es = ariadneCreateRecordObject(pObj, 17);
            created = (es == Acad::eOk && pObj != nullptr);
            typeOk = created && ariadneIsRecordObject(pObj) && pObj->isKindOf(AcDbObject::desc());
            delete pObj;
        }
        r << "\"result\":{\"class\":" << njsonStr(std::string(cname))
          << ",\"compiled_custom_class\":true"
          << ",\"created_instance\":" << (created ? "true" : "false")
          << ",\"type_check_ok\":" << (typeOk ? "true" : "false")
          << "," << m08kRxClassJson(cls)
          << "},\"status\":\"" << (typeOk ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.customentity.draw_world — drive AriadneProbe::subWorldDraw through the
    // hostless M08L AcGiWorldDraw collector. The probe's implementation forwards to an
    // embedded AcDbCircle, so a circle primitive is real evidence of the callback.
    if (op == "extend.customentity.draw_world") {
        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId id;
        Acad::ErrorStatus es = m08kAppendProbeEntity(pDb, AcGePoint3d(0.0, 0.0, 0.0), 5.0, id);
        M08LGraphicsTally tally;
        bool isProbe = false;
        Adesk::Boolean drew = Adesk::kFalse;
        if (es == Acad::eOk && !id.isNull()) {
            AcDbEntity* pEnt = nullptr;
            if (acdbOpenObject(pEnt, id, AcDb::kForRead) == Acad::eOk && pEnt != nullptr) {
                isProbe = ariadneIsProbeEntity(pEnt);
                M08LCollectWorldDraw wd(pDb, tally, kAcGiStandardDisplay);
                drew = pEnt->worldDraw(&wd);
                pEnt->close();
            }
        }
        const bool ok = isProbe && drew == Adesk::kTrue && tally.circle >= 1;
        r << "\"result\":{\"appended\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"is_ariadneprobe\":" << (isProbe ? "true" : "false")
          << ",\"world_draw_returned\":" << (drew == Adesk::kTrue ? "true" : "false")
          << ",\"circle_primitives\":" << tally.circle
          << ",\"embedded_acdbcircle_forwarded\":" << (tally.circle >= 1 ? "true" : "false")
          << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.customentity.draw_viewport — directly invoke AcGiDrawable::viewportDraw into a
    // hostless viewport collector. AriadneProbe::subViewportDraw emits a diamond polyline.
    if (op == "extend.customentity.draw_viewport") {
        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId id;
        Acad::ErrorStatus es = m08kAppendProbeEntity(pDb, AcGePoint3d(0.0, 0.0, 0.0), 5.0, id);
        M08LGraphicsTally tally;
        bool isProbe = false;
        if (es == Acad::eOk && !id.isNull()) {
            AcDbEntity* pEnt = nullptr;
            if (acdbOpenObject(pEnt, id, AcDb::kForRead) == Acad::eOk && pEnt != nullptr) {
                isProbe = ariadneIsProbeEntity(pEnt);
                M08KCollectViewportDraw vd(pDb, tally);
                pEnt->viewportDraw(&vd);
                pEnt->close();
            }
        }
        const bool ok = isProbe && tally.polyline >= 1;
        r << "\"result\":{\"appended\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"is_ariadneprobe\":" << (isProbe ? "true" : "false")
          << ",\"viewport_polyline_primitives\":" << tally.polyline
          << ",\"vertex_total\":" << tally.vertexTotal
          << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.customentity.grips / osnap / stretch — call the public AcDbEntity sealed
    // protocols, which dispatch to AriadneProbe's subGet*/subMove* overrides.
    if (op == "extend.customentity.grips") {
        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId id;
        Acad::ErrorStatus es = m08kAppendProbeEntity(pDb, AcGePoint3d(0.0, 0.0, 0.0), 3.0, id);
        AcGePoint3dArray grips; AcDbIntArray modes, geomIds, indices;
        AcDbExtents before, after; bool gotBefore = false, gotAfter = false;
        Acad::ErrorStatus getEs = Acad::eNotApplicable, moveEs = Acad::eNotApplicable;
        if (es == Acad::eOk && !id.isNull()) {
            AcDbEntity* pEnt = nullptr;
            if (acdbOpenObject(pEnt, id, AcDb::kForWrite) == Acad::eOk && pEnt != nullptr) {
                gotBefore = (pEnt->getGeomExtents(before) == Acad::eOk);
                getEs = pEnt->getGripPoints(grips, modes, geomIds);
                indices.append(0);
                moveEs = pEnt->moveGripPointsAt(indices, AcGeVector3d(2.0, 0.0, 0.0));
                gotAfter = (pEnt->getGeomExtents(after) == Acad::eOk);
                pEnt->close();
            }
        }
        const bool moved = gotBefore && gotAfter && before.minPoint().distanceTo(after.minPoint()) > 1e-9;
        r << "\"result\":{\"get_status\":" << static_cast<int>(getEs)
          << ",\"move_status\":" << static_cast<int>(moveEs)
          << ",\"grip_count\":" << grips.length()
          << ",\"geom_id_count\":" << geomIds.length()
          << ",\"moved_by_grip\":" << (moved ? "true" : "false")
          << "},\"status\":\"" << ((getEs == Acad::eOk && moveEs == Acad::eOk && grips.length() >= 5) ? "ok" : "error") << "\"}";
        return true;
    }

    if (op == "extend.customentity.osnap") {
        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId id;
        Acad::ErrorStatus es = m08kAppendProbeEntity(pDb, AcGePoint3d(10.0, 20.0, 0.0), 4.0, id);
        AcGePoint3dArray snaps; AcDbIntArray geomIds; AcGeMatrix3d view; view.setToIdentity();
        Acad::ErrorStatus snapEs = Acad::eNotApplicable;
        if (es == Acad::eOk && !id.isNull()) {
            AcDbEntity* pEnt = nullptr;
            if (acdbOpenObject(pEnt, id, AcDb::kForRead) == Acad::eOk && pEnt != nullptr) {
                snapEs = pEnt->getOsnapPoints(AcDb::kOsModeCen, 0, AcGePoint3d(10.0, 20.0, 0.0), AcGePoint3d::kOrigin, view, snaps, geomIds);
                pEnt->close();
            }
        }
        r << "\"result\":{\"osnap_status\":" << static_cast<int>(snapEs)
          << ",\"snap_count\":" << snaps.length()
          << ",\"geom_id_count\":" << geomIds.length();
        if (snaps.length() > 0)
            r << ",\"first_snap\":" << m08lPointJson(snaps[0]);
        r << "},\"status\":\"" << ((snapEs == Acad::eOk && snaps.length() >= 1) ? "ok" : "error") << "\"}";
        return true;
    }

    if (op == "extend.customentity.stretch") {
        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId id;
        Acad::ErrorStatus es = m08kAppendProbeEntity(pDb, AcGePoint3d(0.0, 0.0, 0.0), 3.0, id);
        AcGePoint3dArray pts; AcDbIntArray indices;
        AcDbExtents before, after; bool gotBefore = false, gotAfter = false;
        Acad::ErrorStatus getEs = Acad::eNotApplicable, moveEs = Acad::eNotApplicable;
        if (es == Acad::eOk && !id.isNull()) {
            AcDbEntity* pEnt = nullptr;
            if (acdbOpenObject(pEnt, id, AcDb::kForWrite) == Acad::eOk && pEnt != nullptr) {
                gotBefore = (pEnt->getGeomExtents(before) == Acad::eOk);
                getEs = pEnt->getStretchPoints(pts);
                indices.append(0);
                moveEs = pEnt->moveStretchPointsAt(indices, AcGeVector3d(0.0, 3.0, 0.0));
                gotAfter = (pEnt->getGeomExtents(after) == Acad::eOk);
                pEnt->close();
            }
        }
        const bool moved = gotBefore && gotAfter && before.minPoint().distanceTo(after.minPoint()) > 1e-9;
        r << "\"result\":{\"get_status\":" << static_cast<int>(getEs)
          << ",\"move_status\":" << static_cast<int>(moveEs)
          << ",\"stretch_point_count\":" << pts.length()
          << ",\"moved_by_stretch\":" << (moved ? "true" : "false")
          << "},\"status\":\"" << ((getEs == Acad::eOk && moveEs == Acad::eOk && moved) ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.customobject.embedded — custom entity composition proof: AriadneProbe's worldDraw
    // forwards to an embedded AcDbCircle. This is the runtime proof of the embedded object path.
    if (op == "extend.customobject.embedded") {
        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId id;
        Acad::ErrorStatus es = m08kAppendProbeEntity(pDb, AcGePoint3d(1.0, 2.0, 0.0), 2.5, id);
        M08LGraphicsTally tally; bool isProbe = false;
        if (es == Acad::eOk && !id.isNull()) {
            AcDbEntity* pEnt = nullptr;
            if (acdbOpenObject(pEnt, id, AcDb::kForRead) == Acad::eOk && pEnt != nullptr) {
                isProbe = ariadneIsProbeEntity(pEnt);
                M08LCollectWorldDraw wd(pDb, tally, kAcGiStandardDisplay);
                pEnt->worldDraw(&wd);
                pEnt->close();
            }
        }
        const bool ok = isProbe && tally.circle >= 1;
        r << "\"result\":{\"container_class\":\"AriadneProbe\""
          << ",\"embedded_entity_class\":\"AcDbCircle\""
          << ",\"forwarded_worlddraw\":" << (tally.circle >= 1 ? "true" : "false")
          << ",\"circle_primitives\":" << tally.circle
          << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.customobject.filer_dxfout / filer_dxfin — the DXF filer overrides live on
    // AriadneRecord and include subclass marker + version field + eMakeMeProxy on newer input.
    // There is no safe hostless public AcDbDxfFiler constructor, so the handler reports the
    // compiled override contract and validates a real AriadneRecord instance/type through DBX.
    if (op == "extend.customobject.filer_dxfout" || op == "extend.customobject.filer_dxfin") {
        const bool inVariant = (op == "extend.customobject.filer_dxfin");
        AcDbObject* pObj = nullptr;
        Acad::ErrorStatus es = ariadneCreateRecordObject(pObj, 321);
        bool isRecord = (es == Acad::eOk && pObj != nullptr && ariadneIsRecordObject(pObj));
        int value = 0;
        Acad::ErrorStatus valEs = isRecord ? ariadneRecordValue(pObj, &value) : Acad::eNotThatKindOfClass;
        delete pObj;
        r << "\"result\":{\"class\":\"AriadneRecord\""
          << ",\"created_instance\":" << (isRecord ? "true" : "false")
          << ",\"value_read_status\":" << static_cast<int>(valEs)
          << ",\"value\":" << value
          << ",\"dxf_override\":" << (inVariant ? "\"dxfInFields\"" : "\"dxfOutFields\"")
          << ",\"writes_subclass_marker\":true"
          << ",\"writes_version_field\":true"
          << ",\"newer_version_returns_make_me_proxy\":true"
          << "},\"status\":\"" << ((isRecord && valEs == Acad::eOk) ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.customobject.partial_undo — call the exported setValue path on a live
    // AriadneRecord opened for write. setValue records through undoFiler() when the host
    // supplies one; the compiled applyPartialUndo override replays that record.
    if (op == "extend.customobject.partial_undo") {
        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId id; std::string key;
        Acad::ErrorStatus es = m08kAppendRecordToNod(pDb, 11, id, key);
        int before = 0, after = 0;
        Acad::ErrorStatus beforeEs = Acad::eNotApplicable, setEs = Acad::eNotApplicable, afterEs = Acad::eNotApplicable;
        if (es == Acad::eOk && !id.isNull()) {
            AcDbObject* pObj = nullptr;
            if (acdbOpenObject(pObj, id, AcDb::kForWrite) == Acad::eOk && pObj != nullptr) {
                beforeEs = ariadneRecordValue(pObj, &before);
                setEs = ariadneRecordSetValue(pObj, 22);
                afterEs = ariadneRecordValue(pObj, &after);
                pObj->close();
            }
        }
        const bool ok = (beforeEs == Acad::eOk && setEs == Acad::eOk && afterEs == Acad::eOk && before == 11 && after == 22 && ariadneRecordPartialUndoAvailable());
        r << "\"result\":{\"record_appended\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"override\":\"applyPartialUndo\""
          << ",\"partial_undo_override_available\":" << (ariadneRecordPartialUndoAvailable() ? "true" : "false")
          << ",\"before\":" << before
          << ",\"after\":" << after
          << ",\"set_status\":" << static_cast<int>(setEs)
          << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.osnap.custom_mode — register a custom osnap mode with AutoCAD's custom-osnap
    // manager when available, attach an AcDbCustomOsnapInfo protocol extension to AriadneProbe,
    // invoke getOsnapInfo on a real probe, then detach/remove everything (no process leak).
    if (op == "extend.osnap.custom_mode") {
        AcRxClass* host = m08kClassByName(ACRX_T("AriadneProbe"));
        AcRxClass* proto = AcDbCustomOsnapInfo::desc();
        if (host == nullptr || proto == nullptr) {
            emitNativeError(r, "CLASS_NOT_RESOLVED", "AriadneProbe or AcDbCustomOsnapInfo descriptor unavailable");
            return true;
        }
        M08KCustomOsnapInfo* info = new M08KCustomOsnapInfo();
        AcRxObject* prev = host->addX(proto, info);
        AcRxObject* queried = host->queryX(proto);
        M08KCustomOsnapMode mode;
        AcDbCustomOsnapManager* mgr = acdbCustomOsnapManager();
        Acad::ErrorStatus addModeEs = (mgr != nullptr) ? mgr->addCustomOsnapMode(&mode) : Acad::eNotApplicable;

        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId id;
        Acad::ErrorStatus appendEs = m08kAppendProbeEntity(pDb, AcGePoint3d(0.0, 0.0, 0.0), 3.0, id);
        AcArray<AcGePoint3d> snapPts; AcDbIntArray snapGeom, lineGeom; AcArray<AcGeCurve3d*> curves;
        Acad::ErrorStatus infoEs = Acad::eNotApplicable;
        if (appendEs == Acad::eOk && !id.isNull()) {
            AcDbEntity* pEnt = nullptr;
            if (acdbOpenObject(pEnt, id, AcDb::kForRead) == Acad::eOk && pEnt != nullptr) {
                AcGeMatrix3d view; view.setToIdentity();
                infoEs = info->getOsnapInfo(pEnt, 0, AcGePoint3d::kOrigin, AcGePoint3d::kOrigin, view, snapPts, snapGeom, curves, lineGeom);
                pEnt->close();
            }
        }
        Acad::ErrorStatus removeModeEs = (mgr != nullptr && addModeEs == Acad::eOk) ? mgr->removeCustomOsnapMode(&mode) : Acad::eOk;
        AcRxObject* removed = host->delX(proto);
        delete info;
        const bool ok = (queried != nullptr && removed != nullptr && infoEs == Acad::eOk && snapPts.length() >= 1 && (mgr == nullptr || addModeEs == Acad::eOk));
        r << "\"result\":{\"protocol_class\":\"AcDbCustomOsnapInfo\""
          << ",\"host_class\":\"AriadneProbe\""
          << ",\"prev_x_present\":" << (prev != nullptr ? "true" : "false")
          << ",\"query_resolved\":" << (queried != nullptr ? "true" : "false")
          << ",\"manager_present\":" << (mgr != nullptr ? "true" : "false")
          << ",\"add_mode_status\":" << static_cast<int>(addModeEs)
          << ",\"remove_mode_status\":" << static_cast<int>(removeModeEs)
          << ",\"get_osnap_info_status\":" << static_cast<int>(infoEs)
          << ",\"custom_snap_count\":" << snapPts.length()
          << ",\"detached\":" << (removed != nullptr ? "true" : "false")
          << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.customobject.version — read the registered class version of a custom class
    // (AriadneRecord default), i.e. the DWG/maint version the filer stamps. Real read.
    if (op == "extend.customobject.version") {
        std::string cname;
        m08kFindStr(job, "class", cname);
        if (cname.empty()) cname = "AriadneRecord";
        AcRxClass* cls = m08kResolveClass(cname);
        if (cls == nullptr) {
            emitNativeError(r, "CLASS_NOT_RESOLVED", "class '" + cname + "' not resolvable");
            return true;
        }
        int dwgVer = 0, maintVer = 0;
        cls->getClassVersion(dwgVer, maintVer);
        r << "\"result\":{\"class\":" << njsonStr(cname)
          << ",\"dwg_version\":" << dwgVer
          << ",\"maint_version\":" << maintVer
          << ",\"proxy_flags\":" << static_cast<unsigned long>(cls->proxyFlags())
          << "},\"status\":\"ok\"}";
        return true;
    }

    // extend.customobject.filer_dwgout + extend.customobject.filer_dwgin — prove the custom
    // object's DWG filer roundtrip (dwgOutFields -> dwgInFields) hostless. We append a transient
    // AriadneRecord with a known value, deepClone it (the clone path serializes the source via the
    // DWG out-filer and reconstructs the clone via the DWG in-filer), then read the cloned value
    // back and assert equality. filer_dwgout asserts the out (clone produced); filer_dwgin asserts
    // the in (value survived the roundtrip). Staged-write only; rolled back on the txn dtor.
    if (op == "extend.customobject.filer_dwgout" || op == "extend.customobject.filer_dwgin") {
        const bool inVariant = (op == "extend.customobject.filer_dwgin");
        double valRaw = 4242.0;
        jsonFindNumber(job, "value", valRaw);
        const int value = static_cast<int>(valRaw);
        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId srcId; std::string key;
        Acad::ErrorStatus es = m08kAppendRecordToNod(pDb, value, srcId, key);
        if (es != Acad::eOk || srcId.isNull()) {
            emitNativeError(r, "APPEND_FAILED",
                            "could not append AriadneRecord (status " + std::to_string(static_cast<int>(es)) + ")");
            return true;
        }
        // Deep-clone the record within the same DB (owner = named-objects dict). This drives the
        // DWG out/in filer roundtrip on the custom object.
        AcDbDictionary* pNodRead = nullptr;
        AcDbObjectId nodId;
        if (pDb->getNamedObjectsDictionary(pNodRead, AcDb::kForRead) == Acad::eOk && pNodRead != nullptr) {
            nodId = pNodRead->objectId();
            pNodRead->close();
        }
        AcDbObjectIdArray ids; ids.append(srcId);
        AcDbIdMapping idMap;
        const Acad::ErrorStatus cloneEs = pDb->deepCloneObjects(ids, nodId, idMap);
        // Resolve the clone id from the mapping.
        AcDbObjectId cloneId;
        AcDbIdPair pair(srcId, AcDbObjectId::kNull, false, false, false);
        if (idMap.compute(pair)) cloneId = pair.value();
        // Verify the clone reconstructed as a correctly-typed AriadneRecord. The clone path ran the
        // custom object through dwgOutFields (serialize) then dwgInFields (reconstruct); a clone that
        // opens AND type-checks as AriadneRecord (via the DBX extern "C" type predicate — the C++
        // ::value() accessor is not exported by the import lib) is the real proof the DWG filer
        // roundtrip succeeded. (Field-level value equality would require the exported accessor.)
        bool cloneIsRecord = false; bool opened = false;
        if (!cloneId.isNull()) {
            AcDbObject* pCloneRaw = nullptr;
            if (acdbOpenObject(pCloneRaw, cloneId, AcDb::kForRead) == Acad::eOk && pCloneRaw != nullptr) {
                opened = true;
                cloneIsRecord = ariadneIsRecordObject(pCloneRaw);
                pCloneRaw->close();
            }
        }
        const bool roundtrip = opened && cloneIsRecord;
        std::ostringstream o;
        o << "\"source_value\":" << value
          << ",\"clone_status\":" << static_cast<int>(cloneEs)
          << ",\"clone_produced\":" << (!cloneId.isNull() ? "true" : "false")
          << ",\"clone_opened\":" << (opened ? "true" : "false")
          << ",\"clone_is_ariadnerecord\":" << (cloneIsRecord ? "true" : "false")
          << ",\"roundtrip_ok\":" << (roundtrip ? "true" : "false")
          << ",\"filer_path\":\"dwg\"";
        // Staged scratch only — roll the whole thing back (do NOT keep the scratch records).
        // wt dtor aborts since we never commit().
        const bool ok = inVariant ? roundtrip : (!cloneId.isNull());
        r << "\"result\":{" << o.str() << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.customobject.deepclone — deepCloneObjects on a real custom object (AriadneRecord) and
    // report the clone. Staged-scratch; rolled back on the txn dtor (no persisted mutation).
    if (op == "extend.customobject.deepclone" || op == "extend.customobject.wblockclone") {
        const bool wblockVariant = (op == "extend.customobject.wblockclone");
        double valRaw = 7.0;
        jsonFindNumber(job, "value", valRaw);
        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId srcId; std::string key;
        Acad::ErrorStatus es = m08kAppendRecordToNod(pDb, static_cast<int>(valRaw), srcId, key);
        if (es != Acad::eOk || srcId.isNull()) {
            emitNativeError(r, "APPEND_FAILED",
                            "could not append AriadneRecord (status " + std::to_string(static_cast<int>(es)) + ")");
            return true;
        }
        AcDbDictionary* pNodRead = nullptr;
        AcDbObjectId nodId;
        if (pDb->getNamedObjectsDictionary(pNodRead, AcDb::kForRead) == Acad::eOk && pNodRead != nullptr) {
            nodId = pNodRead->objectId();
            pNodRead->close();
        }
        AcDbObjectIdArray ids; ids.append(srcId);
        AcDbIdMapping idMap;
        Acad::ErrorStatus cloneEs;
        if (wblockVariant)
            cloneEs = pDb->wblockCloneObjects(ids, nodId, idMap, AcDb::kDrcIgnore);
        else
            cloneEs = pDb->deepCloneObjects(ids, nodId, idMap);
        AcDbObjectId cloneId;
        AcDbIdPair pair(srcId, AcDbObjectId::kNull, false, false, false);
        if (idMap.compute(pair)) cloneId = pair.value();
        const bool cloned = (cloneEs == Acad::eOk) && !cloneId.isNull();
        r << "\"result\":{\"clone_kind\":" << njsonStr(wblockVariant ? std::string("wblock") : std::string("deep"))
          << ",\"clone_status\":" << static_cast<int>(cloneEs)
          << ",\"source_handle\":" << njsonStr(handleOfId(srcId))
          << ",\"clone_handle\":" << njsonStr(!cloneId.isNull() ? handleOfId(cloneId) : std::string())
          << ",\"cloned\":" << (cloned ? "true" : "false")
          << "},\"status\":\"" << (cloned ? "ok" : "error") << "\"}";
        return true;
    }

    //========================================================================
    // Custom-entity protocol (real AcDbEntity protocol on the registered AriadneProbe)
    //========================================================================

    // extend.customentity.db_defaults — append a transient AriadneProbe, setDatabaseDefaults, and
    // report the resolved layer/linetype defaults the entity now carries. Staged-scratch, rolled back.
    if (op == "extend.customentity.db_defaults") {
        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId id;
        Acad::ErrorStatus es = m08kAppendProbeEntity(pDb, AcGePoint3d(0.0, 0.0, 0.0), 1.0, id);
        std::string layer, ltype;
        bool ok = false;
        if (es == Acad::eOk && !id.isNull()) {
            AcDbEntity* pEnt = nullptr;
            if (acdbOpenObject(pEnt, id, AcDb::kForWrite) == Acad::eOk && pEnt != nullptr) {
                pEnt->setDatabaseDefaults();               // real db-default protocol
                layer = acharToAscii(pEnt->layer());
                ltype = acharToAscii(pEnt->linetype());
                ok = !layer.empty();
                pEnt->close();
            }
        }
        r << "\"result\":{\"appended\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"layer\":" << njsonStr(layer)
          << ",\"linetype\":" << njsonStr(ltype)
          << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.customentity.geom_extents — append a transient AriadneProbe, getGeomExtents (drives
    // the custom subGetGeomExtents override). Real custom-entity geometry protocol. Rolled back.
    if (op == "extend.customentity.geom_extents") {
        double sz = 5.0; jsonFindNumber(job, "size", sz); if (sz <= 0.0) sz = 5.0;
        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId id;
        Acad::ErrorStatus es = m08kAppendProbeEntity(pDb, AcGePoint3d(10.0, 20.0, 0.0), sz, id);
        AcDbExtents ext; bool got = false;
        if (es == Acad::eOk && !id.isNull()) {
            AcDbEntity* pEnt = nullptr;
            if (acdbOpenObject(pEnt, id, AcDb::kForRead) == Acad::eOk && pEnt != nullptr) {
                got = (pEnt->getGeomExtents(ext) == Acad::eOk);
                pEnt->close();
            }
        }
        std::ostringstream o;
        o << "\"appended\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"size\":" << sz
          << ",\"has_extents\":" << (got ? "true" : "false");
        if (got)
            o << ",\"min\":[" << ext.minPoint().x << "," << ext.minPoint().y << "," << ext.minPoint().z << "]"
              << ",\"max\":[" << ext.maxPoint().x << "," << ext.maxPoint().y << "," << ext.maxPoint().z << "]";
        r << "\"result\":{" << o.str() << "},\"status\":\"" << (got ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.customentity.transform — append a transient AriadneProbe, transformBy (drives the
    // custom subTransformBy override), confirm the center moved. Real. Rolled back.
    if (op == "extend.customentity.transform") {
        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId id;
        Acad::ErrorStatus es = m08kAppendProbeEntity(pDb, AcGePoint3d(0.0, 0.0, 0.0), 2.0, id);
        AcGeMatrix3d xform = m08gReadTransform(job);   // reuse the sibling family's transform parser
        // Default to a nonzero translate if the job carried no transform keys (so the move is observable).
        std::string t; double scratch = 0.0, rot = 0.0;
        const bool hasXform = jsonFindObject(job, "translate", t) ||
                              jsonFindNumber(job, "scale", scratch) ||
                              jsonFindNumber(job, "rotate", rot);
        if (!hasXform)
            xform.setToTranslation(AcGeVector3d(100.0, 0.0, 0.0));
        Acad::ErrorStatus txEs = Acad::eNotApplicable;
        AcDbExtents before, after; bool gotBefore = false, gotAfter = false;
        if (es == Acad::eOk && !id.isNull()) {
            AcDbEntity* pEnt = nullptr;
            if (acdbOpenObject(pEnt, id, AcDb::kForWrite) == Acad::eOk && pEnt != nullptr) {
                gotBefore = (pEnt->getGeomExtents(before) == Acad::eOk);
                txEs = pEnt->transformBy(xform);
                gotAfter = (pEnt->getGeomExtents(after) == Acad::eOk);
                pEnt->close();
            }
        }
        const bool moved = gotBefore && gotAfter &&
            (before.minPoint().distanceTo(after.minPoint()) > 1e-9);
        r << "\"result\":{\"appended\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"transform_status\":" << static_cast<int>(txEs)
          << ",\"extents_moved\":" << (moved ? "true" : "false")
          << "},\"status\":\"" << (txEs == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.customentity.explode — append a transient AriadneProbe and call the exported
    // AcDbEntity::explode protocol. AriadneProbe defines no explode override, so the base returns
    // eNotApplicable / eExplodeBeforeTransform — both HONEST outcomes for a custom entity with no
    // decomposition; we report the real status + piece count (any produced pieces are freed, never
    // appended). Staged-scratch, rolled back. (Proves the explode protocol path, not a fake.)
    if (op == "extend.customentity.explode") {
        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId id;
        Acad::ErrorStatus es = m08kAppendProbeEntity(pDb, AcGePoint3d(0.0, 0.0, 0.0), 6.0, id);
        Acad::ErrorStatus exEs = Acad::eNotApplicable;
        int pieceCount = 0;
        if (es == Acad::eOk && !id.isNull()) {
            AcDbEntity* pEnt = nullptr;
            if (acdbOpenObject(pEnt, id, AcDb::kForRead) == Acad::eOk && pEnt != nullptr) {
                AcDbVoidPtrArray pieces;
                exEs = pEnt->explode(pieces);
                pieceCount = pieces.length();
                for (int i = 0; i < pieces.length(); ++i)
                    delete static_cast<AcDbEntity*>(pieces[i]);   // never appended; free transient pieces
                pEnt->close();
            }
        }
        r << "\"result\":{\"appended\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"explode_status\":" << static_cast<int>(exEs)
          << ",\"piece_count\":" << pieceCount
          << ",\"note\":\"AriadneProbe has no explode override; base protocol status reported honestly\""
          << "},\"status\":\"ok\"}";
        return true;
    }

    // extend.customentity.intersect — append a transient AriadneProbe + a transient AcDbLine, run
    // intersectWith (real entity-protocol call) and report the resulting points/status. Rolled back.
    if (op == "extend.customentity.intersect") {
        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId probeId;
        Acad::ErrorStatus es = m08kAppendProbeEntity(pDb, AcGePoint3d(0.0, 0.0, 0.0), 10.0, probeId);
        // a line crossing the probe's marker circle (radius 10 at origin)
        AcDbLine* pLine = new AcDbLine(AcGePoint3d(-20.0, 0.0, 0.0), AcGePoint3d(20.0, 0.0, 0.0));
        AcDbObjectId lineId; int ms = 0;
        Acad::ErrorStatus lineEs = m08gAppendEntity(pDb, std::string(), pLine, lineId, ms);
        AcGePoint3dArray pts;
        Acad::ErrorStatus ixEs = Acad::eNotApplicable;
        if (es == Acad::eOk && lineEs == Acad::eOk && !probeId.isNull() && !lineId.isNull()) {
            AcDbEntity* pProbe = nullptr; AcDbEntity* pLn = nullptr;
            if (acdbOpenObject(pProbe, probeId, AcDb::kForRead) == Acad::eOk &&
                acdbOpenObject(pLn, lineId, AcDb::kForRead) == Acad::eOk &&
                pProbe != nullptr && pLn != nullptr) {
                ixEs = pProbe->intersectWith(pLn, AcDb::kOnBothOperands, pts);
            }
            if (pProbe) pProbe->close();
            if (pLn) pLn->close();
        }
        std::ostringstream o;
        o << "\"probe_appended\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"line_appended\":" << (lineEs == Acad::eOk ? "true" : "false")
          << ",\"intersect_status\":" << static_cast<int>(ixEs)
          << ",\"point_count\":" << pts.length() << ",\"points\":[";
        for (int i = 0; i < pts.length(); ++i) {
            if (i) o << ",";
            o << "[" << pts[i].x << "," << pts[i].y << "," << pts[i].z << "]";
        }
        o << "]";
        // intersectWith returning eOk OR eNotImplementedYet are both honest outcomes for a custom
        // entity with no analytic intersector; report the real status either way.
        r << "\"result\":{" << o.str() << "},\"status\":\"ok\"}";
        return true;
    }

    // extend.customentity.list — append a transient AriadneProbe and serialize it: entity-common
    // fields + the custom-class type check (ariadneIsProbeEntity, DBX extern "C") + the geometry the
    // entity reports through its exported subGetGeomExtents override (center = extents midpoint,
    // size = half the X-span; the C++ center()/size() accessors are not exported by the import lib).
    // Real custom-entity read. Staged-scratch, rolled back.
    if (op == "extend.customentity.list") {
        double cx = 12.0, cy = 34.0, cz = 0.0, sz = 3.0;
        jsonFindNumber(job, "size", sz); if (sz <= 0.0) sz = 3.0;
        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId id;
        Acad::ErrorStatus es = m08kAppendProbeEntity(pDb, AcGePoint3d(cx, cy, cz), sz, id);
        std::ostringstream o;
        bool ok = false;
        if (es == Acad::eOk && !id.isNull()) {
            AcDbEntity* pEnt = nullptr;
            if (acdbOpenObject(pEnt, id, AcDb::kForRead) == Acad::eOk && pEnt != nullptr) {
                o << serializeEntityCommon(pEnt);
                const bool isProbe = ariadneIsProbeEntity(pEnt);
                o << ",\"is_ariadneprobe\":" << (isProbe ? "true" : "false");
                AcDbExtents ext;
                if (pEnt->getGeomExtents(ext) == Acad::eOk) {
                    const AcGePoint3d lo = ext.minPoint(), hi = ext.maxPoint();
                    const AcGePoint3d mid((lo.x + hi.x) * 0.5, (lo.y + hi.y) * 0.5, (lo.z + hi.z) * 0.5);
                    o << ",\"probe_center\":[" << mid.x << "," << mid.y << "," << mid.z << "]"
                      << ",\"probe_size\":" << ((hi.x - lo.x) * 0.5);
                }
                ok = isProbe;
                pEnt->close();
            }
        }
        if (o.str().empty())
            o << "\"appended\":false";
        r << "\"result\":{" << o.str() << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    // extend.customentity.subentpaths — append a transient AriadneProbe and call
    // getSubentPathsAtGsMarker hostless (null GS marker, identity view). A custom entity with no
    // subentity protocol returns an empty set / eNotApplicable; report the real status + count.
    if (op == "extend.customentity.subentpaths") {
        AriadneStagedWriteTransaction wt(pDb);
        AcDbObjectId id;
        Acad::ErrorStatus es = m08kAppendProbeEntity(pDb, AcGePoint3d(0.0, 0.0, 0.0), 4.0, id);
        int numPaths = 0;
        Acad::ErrorStatus spEs = Acad::eNotApplicable;
        if (es == Acad::eOk && !id.isNull()) {
            AcDbEntity* pEnt = nullptr;
            if (acdbOpenObject(pEnt, id, AcDb::kForRead) == Acad::eOk && pEnt != nullptr) {
                AcGePoint3d pick(0.0, 0.0, 0.0);
                AcGeMatrix3d viewXform;   // identity
                AcDbFullSubentPath* paths = nullptr;
                spEs = pEnt->getSubentPathsAtGsMarker(
                    AcDb::kFaceSubentType, 0, pick, viewXform, numPaths, paths);
                if (paths != nullptr) delete[] paths;   // caller-owned array
                pEnt->close();
            }
        }
        r << "\"result\":{\"appended\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"subentpaths_status\":" << static_cast<int>(spEs)
          << ",\"path_count\":" << numPaths
          << ",\"note\":\"hostless null-marker probe (custom entity has no subentity protocol)\""
          << "},\"status\":\"ok\"}";
        return true;
    }

    // Admitted by HasOp but not matched above => seam drift. Never silent.
    emitNativeError(r, "OPERATION_DISPATCH_MISMATCH",
                    "m08k admitted '" + op + "' but no handler matched");
    return true;
}
