//////////////////////////////////////////////////////////////////////////////
// AriadneProbe.cpp — implementation of the minimal Ariadne custom entity.
//////////////////////////////////////////////////////////////////////////////
#include <tchar.h>
#include "AriadneProbe.h"

// Persisted data-member version. First item written/read; on a newer-than-known
// version we return eMakeMeProxy so the object round-trips safely (research:
// custom-objects slice, GUID-8BC0B508 / GUID-E3A9EC7B).
static const Adesk::Int16 kAriadneProbeVersion = 1;

//----------------------------------------------------------------------------
// Runtime-class registration. DWG/DXF-persistent custom class: birth version
// kDHL_CURRENT/kMReleaseCurrent, all proxy operations allowed, DXF record name
// ARIADNEPROBE, owning app string. (Mirrors poly.cpp:173.)
//----------------------------------------------------------------------------
ACRX_DXF_DEFINE_MEMBERS(
    AriadneProbe, AcDbEntity,
    AcDb::kDHL_CURRENT, AcDb::kMReleaseCurrent,
    AcDbProxyEntity::kAllAllowedBits, ARIADNEPROBE,
    "AriadneAcadNative1.0\
|Product Desc:     Ariadne Native ObjectARX Controller\
|Company:          Ariadne");

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
// Graphics — AcGi worldDraw (view-independent). Draw a circle marker of radius
// mSize at mCenter, in the XY plane.
//----------------------------------------------------------------------------
Adesk::Boolean AriadneProbe::subWorldDraw(AcGiWorldDraw* mode)
{
    assertReadEnabled();
    mode->geometry().circle(mCenter, mSize, AcGeVector3d::kZAxis);
    return Adesk::kTrue;   // fully view-independent; no subViewportDraw needed
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
