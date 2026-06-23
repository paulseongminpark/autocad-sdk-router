//////////////////////////////////////////////////////////////////////////////
// AriadneProbe.cpp — implementation of the minimal Ariadne custom entity.
//////////////////////////////////////////////////////////////////////////////
#include <tchar.h>
#include <windows.h>
#include "dbgrip.h"
#include "AriadneProbe.h"
// OPM/AcRxProperty surface (M07A): expose AriadneProbe::size() as a runtime
// property so the Properties palette (attended) and the headless member-query
// path both see it. Registered via the WITH_PROPERTIES class macro below.
#include "rxprop.h"
#include "rxvalue.h"
#include "rxvaluetype.h"
#include "rxmember.h"

// Persisted data-member version. First item written/read; on a newer-than-known
// version we return eMakeMeProxy so the object round-trips safely (research:
// custom-objects slice, GUID-8BC0B508 / GUID-E3A9EC7B).
static const Adesk::Int16 kAriadneProbeVersion = 1;

//----------------------------------------------------------------------------
// AcRxProperty (OPM) — "Size" runtime property backed by size()/setSize().
// The member-collection builder has a private ctor (rxmember.h); the canonical
// way to attach members is the MAKEPROPS callback passed through newAcRxClass at
// class registration (ACRX_DXF_DEFINE_MEMBERS_WITH_PROPERTIES, rxboiler.h:289).
// Write idiom: AcRxValue::operator=(double); read: rxvalue_cast<double> (rxvalue.h).
//----------------------------------------------------------------------------
class AriadneSizeProperty : public AcRxProperty
{
public:
    AriadneSizeProperty()
        : AcRxProperty(ACRX_T("Size"), AcRxValueType::Desc<double>::value(), NULL) {}
    // AcRxMember::operator delete is protected (the SDK owns member lifetime). Expose a
    // forwarding delete so the compiler can pair it with `new` (ctor-cleanup path); the
    // member collection still frees it through the SDK's own friended path.
    void operator delete(void* p) { AcRxMember::operator delete(p); }
protected:
    Acad::ErrorStatus subGetValue(const AcRxObject* pO, AcRxValue& value) const override
    {
        const AriadneProbe* probe = AriadneProbe::cast(pO);
        if (probe == NULL) return Acad::eNotApplicable;
        value = probe->size();
        return Acad::eOk;
    }
    Acad::ErrorStatus subSetValue(AcRxObject* pO, const AcRxValue& value) const override
    {
        AriadneProbe* probe = AriadneProbe::cast(pO);
        if (probe == NULL) return Acad::eNotApplicable;
        const double* pd = rxvalue_cast<double>(&value);
        if (pd == NULL) return Acad::eInvalidInput;
        return probe->setSize(*pd); // setSize enforces > 0
    }
};

static void ariadneMakeProbeMembers(AcRxMemberCollectionBuilder& builder, void*)
{
    builder.add(new AriadneSizeProperty());
}

//----------------------------------------------------------------------------
// Runtime-class registration. DWG/DXF-persistent custom class: birth version
// kDHL_CURRENT/kMReleaseCurrent, all proxy operations allowed, DXF record name
// ARIADNEPROBE, owning app string. (Mirrors poly.cpp:173.) WITH_PROPERTIES binds
// the OPM "Size" member at rxInit() via the makeMembers callback.
//----------------------------------------------------------------------------
ACRX_DXF_DEFINE_MEMBERS_WITH_PROPERTIES(
    AriadneProbe, AcDbEntity,
    AcDb::kDHL_CURRENT, AcDb::kMReleaseCurrent,
    AcDbProxyEntity::kAllAllowedBits, ARIADNEPROBE,
    "AriadneAcadNative1.0\
|Product Desc:     Ariadne Native ObjectARX Controller\
|Company:          Ariadne",
    ariadneMakeProbeMembers);

//----------------------------------------------------------------------------
AriadneProbe::AriadneProbe()
    : mCenter(0.0, 0.0, 0.0), mSize(1.0)
{
}

AriadneProbe::~AriadneProbe()
{
}

//----------------------------------------------------------------------------
AcGePoint3d AriadneProbe::center() const
{
    assertReadEnabled();
    return mCenter;
}

double AriadneProbe::size() const
{
    assertReadEnabled();
    return mSize;
}

Acad::ErrorStatus AriadneProbe::setCenter(const AcGePoint3d& c)
{
    assertWriteEnabled();
    mCenter = c;
    return Acad::eOk;
}

Acad::ErrorStatus AriadneProbe::setSize(double s)
{
    assertWriteEnabled();
    if (s <= 0.0)
        return Acad::eInvalidInput;
    mSize = s;
    return Acad::eOk;
}

//----------------------------------------------------------------------------
// Filing — DWG
//----------------------------------------------------------------------------
Acad::ErrorStatus AriadneProbe::dwgOutFields(AcDbDwgFiler* filer) const
{
    assertReadEnabled();
    Acad::ErrorStatus es = AcDbEntity::dwgOutFields(filer);
    if (es != Acad::eOk)
        return es;

    filer->writeInt16(kAriadneProbeVersion);   // version FIRST
    filer->writePoint3d(mCenter);
    filer->writeDouble(mSize);
    return filer->filerStatus();
}

Acad::ErrorStatus AriadneProbe::dwgInFields(AcDbDwgFiler* filer)
{
    assertWriteEnabled();
    Acad::ErrorStatus es = AcDbEntity::dwgInFields(filer);
    if (es != Acad::eOk)
        return es;

    Adesk::Int16 version = 0;
    filer->readInt16(&version);
    if (version > kAriadneProbeVersion)
        return Acad::eMakeMeProxy;             // forward-compat: degrade to proxy

    filer->readPoint3d(&mCenter);
    filer->readDouble(&mSize);
    return filer->filerStatus();
}

//----------------------------------------------------------------------------
// Filing — DXF
//----------------------------------------------------------------------------
Acad::ErrorStatus AriadneProbe::dxfOutFields(AcDbDxfFiler* filer) const
{
    assertReadEnabled();
    Acad::ErrorStatus es = AcDbEntity::dxfOutFields(filer);
    if (es != Acad::eOk)
        return es;

    filer->writeItem(AcDb::kDxfSubclass, _T("AriadneProbe"));
    filer->writeInt16(AcDb::kDxfInt16, kAriadneProbeVersion);
    filer->writePoint3d(AcDb::kDxfXCoord, mCenter);
    filer->writeDouble(AcDb::kDxfReal, mSize);
    return filer->filerStatus();
}

Acad::ErrorStatus AriadneProbe::dxfInFields(AcDbDxfFiler* filer)
{
    assertWriteEnabled();
    Acad::ErrorStatus es = AcDbEntity::dxfInFields(filer);
    if (es != Acad::eOk)
        return es;

    if (filer->atSubclassData(_T("AriadneProbe")) != Adesk::kTrue)
        return filer->filerStatus();

    // Order-tolerant read of the codes we wrote.
    struct resbuf rb;
    while (filer->readResBuf(&rb) == Acad::eOk) {
        switch (rb.restype) {
        case AcDb::kDxfInt16:
            // version (rb.resval.rint) — accepted as-is for v1
            break;
        case AcDb::kDxfXCoord:
            mCenter.set(rb.resval.rpoint[0], rb.resval.rpoint[1], rb.resval.rpoint[2]);
            break;
        case AcDb::kDxfReal:
            mSize = rb.resval.rreal;
            break;
        default:
            break;
        }
    }
    return filer->filerStatus();
}

//----------------------------------------------------------------------------
// Graphics — AcGi worldDraw (view-independent). Compose the probe from a real
// embedded AcDbCircle and forward its worldDraw. The persisted fields remain the
// probe's center/size; the embedded circle is rebuilt on demand so custom-object
// proxy fallback can still round-trip using our compact filers.
//----------------------------------------------------------------------------
Adesk::Boolean AriadneProbe::subWorldDraw(AcGiWorldDraw* mode)
{
    assertReadEnabled();
    if (mode == NULL)
        return Adesk::kFalse;

    AcDbCircle embedded(mCenter, AcGeVector3d::kZAxis, mSize);
    embedded.setPropertiesFrom(this);
    if (embedded.worldDraw(mode) != Adesk::kTrue)
        mode->geometry().circle(mCenter, mSize, AcGeVector3d::kZAxis);
    return Adesk::kTrue;   // fully view-independent; viewportDraw is an optional overlay
}

//----------------------------------------------------------------------------
// Viewport-specific graphics — draw a small diamond in device/viewport space
// when AutoCAD explicitly asks for a viewport pass. Because subWorldDraw returns
// kTrue this is normally only exercised by direct viewportDraw probes or special
// regen paths, but the callback is real and safe when a viewport context exists.
//----------------------------------------------------------------------------
void AriadneProbe::subViewportDraw(AcGiViewportDraw* mode)
{
    assertReadEnabled();
    if (mode == NULL)
        return;

    const double d = (mSize > 0.0) ? (mSize * 0.20) : 0.20;
    AcGePoint3d pts[5] = {
        AcGePoint3d(mCenter.x,     mCenter.y + d, mCenter.z),
        AcGePoint3d(mCenter.x + d, mCenter.y,     mCenter.z),
        AcGePoint3d(mCenter.x,     mCenter.y - d, mCenter.z),
        AcGePoint3d(mCenter.x - d, mCenter.y,     mCenter.z),
        AcGePoint3d(mCenter.x,     mCenter.y + d, mCenter.z)
    };
    mode->geometry().polyline(5, pts);
}

//----------------------------------------------------------------------------
Acad::ErrorStatus AriadneProbe::subGetGeomExtents(AcDbExtents& extents) const
{
    assertReadEnabled();
    const AcGeVector3d d(mSize, mSize, 0.0);
    extents.set(mCenter - d, mCenter + d);
    return Acad::eOk;
}

//----------------------------------------------------------------------------
Acad::ErrorStatus AriadneProbe::subTransformBy(const AcGeMatrix3d& xform)
{
    assertWriteEnabled();
    mCenter.transformBy(xform);
    mSize *= xform.scale();   // uniform-scale component
    return Acad::eOk;
}

//----------------------------------------------------------------------------
// Grip protocol — expose center + four quadrant points; moving any grip translates
// the probe by the supplied offset. The rich-grip overload mirrors the legacy
// point set so both editor protocols are covered.
//----------------------------------------------------------------------------
Acad::ErrorStatus AriadneProbe::subGetGripPoints(
    AcGePoint3dArray& gripPoints,
    AcDbIntArray& osnapModes,
    AcDbIntArray& geomIds) const
{
    assertReadEnabled();
    gripPoints.append(mCenter);
    gripPoints.append(AcGePoint3d(mCenter.x + mSize, mCenter.y, mCenter.z));
    gripPoints.append(AcGePoint3d(mCenter.x, mCenter.y + mSize, mCenter.z));
    gripPoints.append(AcGePoint3d(mCenter.x - mSize, mCenter.y, mCenter.z));
    gripPoints.append(AcGePoint3d(mCenter.x, mCenter.y - mSize, mCenter.z));
    for (int i = 0; i < 5; ++i) {
        osnapModes.append(i == 0 ? AcDb::kOsModeCen : AcDb::kOsModeQuad);
        geomIds.append(i);
    }
    return Acad::eOk;
}

Acad::ErrorStatus AriadneProbe::subGetGripPoints(
    AcDbGripDataPtrArray& grips,
    const double /*curViewUnitSize*/,
    const int /*gripSize*/,
    const AcGeVector3d& /*curViewDir*/,
    const int /*bitflags*/) const
{
    assertReadEnabled();
    AcGePoint3dArray pts;
    AcDbIntArray modes, geomIds;
    Acad::ErrorStatus es = subGetGripPoints(pts, modes, geomIds);
    if (es != Acad::eOk)
        return es;
    for (int i = 0; i < pts.length(); ++i) {
        AcDbGripData* gd = new AcDbGripData();
        gd->setGripPoint(pts[i]);
        gd->setAppData(reinterpret_cast<void*>(static_cast<Adesk::IntPtr>(i + 1)));
        grips.append(gd);
    }
    return Acad::eOk;
}

Acad::ErrorStatus AriadneProbe::subMoveGripPointsAt(
    const AcDbIntArray& indices,
    const AcGeVector3d& offset)
{
    assertWriteEnabled();
    if (indices.isEmpty())
        return Acad::eInvalidInput;
    mCenter += offset;
    return Acad::eOk;
}

Acad::ErrorStatus AriadneProbe::subMoveGripPointsAt(
    const AcDbVoidPtrArray& gripAppData,
    const AcGeVector3d& offset,
    const int /*bitflags*/)
{
    assertWriteEnabled();
    if (gripAppData.isEmpty())
        return Acad::eInvalidInput;
    mCenter += offset;
    return Acad::eOk;
}

//----------------------------------------------------------------------------
// STRETCH protocol — identical control points to the grip protocol, with the
// same translate-on-move semantics.
//----------------------------------------------------------------------------
Acad::ErrorStatus AriadneProbe::subGetStretchPoints(AcGePoint3dArray& stretchPoints) const
{
    assertReadEnabled();
    AcDbIntArray modes, geomIds;
    return subGetGripPoints(stretchPoints, modes, geomIds);
}

Acad::ErrorStatus AriadneProbe::subMoveStretchPointsAt(
    const AcDbIntArray& indices,
    const AcGeVector3d& offset)
{
    assertWriteEnabled();
    if (indices.isEmpty())
        return Acad::eInvalidInput;
    mCenter += offset;
    return Acad::eOk;
}

//----------------------------------------------------------------------------
// OSNAP protocol — provide center/centroid/node/insert, quadrants, and a nearest
// fallback for the probe marker. The insertion-matrix overload transforms the
// computed points for block-reference contexts.
//----------------------------------------------------------------------------
Acad::ErrorStatus AriadneProbe::subGetOsnapPoints(
    AcDb::OsnapMode osnapMode,
    Adesk::GsMarker /*gsSelectionMark*/,
    const AcGePoint3d& pickPoint,
    const AcGePoint3d& /*lastPoint*/,
    const AcGeMatrix3d& /*viewXform*/,
    AcGePoint3dArray& snapPoints,
    AcDbIntArray& geomIds) const
{
    assertReadEnabled();
    switch (osnapMode) {
    case AcDb::kOsModeCen:
    case AcDb::kOsModeCentroid:
    case AcDb::kOsModeNode:
    case AcDb::kOsModeIns:
    case AcDb::kOsModeMid:
        snapPoints.append(mCenter);
        geomIds.append(0);
        break;
    case AcDb::kOsModeEnd:
    case AcDb::kOsModeQuad:
        snapPoints.append(AcGePoint3d(mCenter.x + mSize, mCenter.y, mCenter.z)); geomIds.append(1);
        snapPoints.append(AcGePoint3d(mCenter.x, mCenter.y + mSize, mCenter.z)); geomIds.append(2);
        snapPoints.append(AcGePoint3d(mCenter.x - mSize, mCenter.y, mCenter.z)); geomIds.append(3);
        snapPoints.append(AcGePoint3d(mCenter.x, mCenter.y - mSize, mCenter.z)); geomIds.append(4);
        break;
    case AcDb::kOsModeNear: {
        AcGeVector3d v = pickPoint - mCenter;
        if (v.length() <= 1e-9)
            v = AcGeVector3d::kXAxis;
        v.normalize();
        snapPoints.append(mCenter + (v * mSize));
        geomIds.append(5);
        break;
    }
    default:
        return Acad::eOk;
    }
    return Acad::eOk;
}

Acad::ErrorStatus AriadneProbe::subGetOsnapPoints(
    AcDb::OsnapMode osnapMode,
    Adesk::GsMarker gsSelectionMark,
    const AcGePoint3d& pickPoint,
    const AcGePoint3d& lastPoint,
    const AcGeMatrix3d& viewXform,
    AcGePoint3dArray& snapPoints,
    AcDbIntArray& geomIds,
    const AcGeMatrix3d& insertionMat) const
{
    const int before = snapPoints.length();
    Acad::ErrorStatus es = subGetOsnapPoints(
        osnapMode, gsSelectionMark, pickPoint, lastPoint, viewXform, snapPoints, geomIds);
    if (es != Acad::eOk)
        return es;
    for (int i = before; i < snapPoints.length(); ++i)
        snapPoints[i].transformBy(insertionMat);
    return Acad::eOk;
}
