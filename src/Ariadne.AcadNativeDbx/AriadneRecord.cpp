#include <tchar.h>
#include "AriadneRecord.h"

static const Adesk::Int16 kAriadneRecordVersion = 1;

ACRX_DXF_DEFINE_MEMBERS(
    AriadneRecord, AcDbObject,
    AcDb::kDHL_CURRENT, AcDb::kMReleaseCurrent,
    0, ARIADNERECORD,
    "AriadneAcadNative1.0\
|Product Desc:     Ariadne Native ObjectDBX Controller\
|Company:          Ariadne");

AriadneRecord::AriadneRecord()
    : mValue(0)
{
}

AriadneRecord::AriadneRecord(Adesk::Int16 value)
    : mValue(value)
{
}

AriadneRecord::~AriadneRecord()
{
}

Adesk::Int16 AriadneRecord::value() const
{
    assertReadEnabled();
    return mValue;
}

Acad::ErrorStatus AriadneRecord::setValue(Adesk::Int16 value)
{
    assertWriteEnabled();
    mValue = value;
    return Acad::eOk;
}

Acad::ErrorStatus AriadneRecord::dwgOutFields(AcDbDwgFiler* filer) const
{
    assertReadEnabled();
    Acad::ErrorStatus es = AcDbObject::dwgOutFields(filer);
    if (es != Acad::eOk)
        return es;

    filer->writeInt16(kAriadneRecordVersion);
    filer->writeItem(mValue);
    return filer->filerStatus();
}

Acad::ErrorStatus AriadneRecord::dwgInFields(AcDbDwgFiler* filer)
{
    assertWriteEnabled();
    Acad::ErrorStatus es = AcDbObject::dwgInFields(filer);
    if (es != Acad::eOk)
        return es;

    Adesk::Int16 version = 0;
    filer->readInt16(&version);
    if (version > kAriadneRecordVersion)
        return Acad::eMakeMeProxy;

    filer->readItem(&mValue);
    return filer->filerStatus();
}

Acad::ErrorStatus AriadneRecord::dxfOutFields(AcDbDxfFiler* filer) const
{
    assertReadEnabled();
    Acad::ErrorStatus es = AcDbObject::dxfOutFields(filer);
    if (es != Acad::eOk)
        return es;

    filer->writeItem(AcDb::kDxfSubclass, _T("AriadneRecord"));
    filer->writeItem(AcDb::kDxfInt16, kAriadneRecordVersion);
    filer->writeItem(AcDb::kDxfInt16, mValue);
    return filer->filerStatus();
}

Acad::ErrorStatus AriadneRecord::dxfInFields(AcDbDxfFiler* filer)
{
    assertWriteEnabled();
    Acad::ErrorStatus es = AcDbObject::dxfInFields(filer);
    if (es != Acad::eOk)
        return es;

    if (filer->atSubclassData(_T("AriadneRecord")) != Adesk::kTrue)
        return Acad::eBadDxfSequence;

    struct resbuf rb;
    bool sawVersion = false;
    while (filer->readItem(&rb) == Acad::eOk) {
        if (rb.restype == AcDb::kDxfInt16) {
            if (!sawVersion) {
                sawVersion = true;
                if (rb.resval.rint > kAriadneRecordVersion)
                    return Acad::eMakeMeProxy;
            }
            else {
                mValue = rb.resval.rint;
            }
        }
    }
    return filer->filerStatus();
}
