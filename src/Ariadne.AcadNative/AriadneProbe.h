//////////////////////////////////////////////////////////////////////////////
// AriadneProbe.h
//
// Minimal custom AcDbEntity for the Ariadne native ObjectARX controller
// (P1 de-risk milestone). Proves: custom-class registration, DWG/DXF filing,
// AcGi rendering (subWorldDraw), extents, and transform — the native-only
// surface managed .NET cannot author.
//
// Grounded in C:\ObjectARX 2027\samples\entity\polysamp (poly.h/poly.cpp).
//////////////////////////////////////////////////////////////////////////////
#pragma once

#include "dbmain.h"
#include "dbents.h"
#include "dbproxy.h"
#include "acdbabb.h"
#include "acgi.h"
#include "gepnt3d.h"
#include "gemat3d.h"
#include "geassign.h"

class AriadneProbe : public AcDbEntity
{
public:
    ACRX_DECLARE_MEMBERS(AriadneProbe);

    AriadneProbe();
    virtual ~AriadneProbe();

    // Ariadne-specific accessors
    AcGePoint3d        center() const;
    double             size()   const;
    Acad::ErrorStatus  setCenter(const AcGePoint3d& c);
    Acad::ErrorStatus  setSize(double s);

    // AcDbObject persistence (filing). The 4 mandatory custom-class overrides.
    virtual Acad::ErrorStatus dwgInFields(AcDbDwgFiler* filer) override;
    virtual Acad::ErrorStatus dwgOutFields(AcDbDwgFiler* filer) const override;
    virtual Acad::ErrorStatus dxfInFields(AcDbDxfFiler* filer) override;
    virtual Acad::ErrorStatus dxfOutFields(AcDbDxfFiler* filer) const override;

protected:
    // Public worldDraw/getGeomExtents/transformBy are ADESK_SEALED in 2027 —
    // override the protected subXxx virtuals (research: entities + editor-delta).
    virtual Adesk::Boolean    subWorldDraw(AcGiWorldDraw* mode) override;
    virtual Acad::ErrorStatus subGetGeomExtents(AcDbExtents& extents) const override;
    virtual Acad::ErrorStatus subTransformBy(const AcGeMatrix3d& xform) override;

private:
    AcGePoint3d mCenter;
    double      mSize;
};
