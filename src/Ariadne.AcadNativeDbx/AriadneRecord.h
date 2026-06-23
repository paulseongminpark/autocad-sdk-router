#pragma once

#include "dbmain.h"

class AriadneRecord : public AcDbObject
{
public:
    ACRX_DECLARE_MEMBERS(AriadneRecord);

    AriadneRecord();
    explicit AriadneRecord(Adesk::Int16 value);
    virtual ~AriadneRecord();

    Adesk::Int16 value() const;
    Acad::ErrorStatus setValue(Adesk::Int16 value);

    virtual Acad::ErrorStatus applyPartialUndo(AcDbDwgFiler* undoFiler, AcRxClass* classObj) override;
    virtual Acad::ErrorStatus dwgInFields(AcDbDwgFiler* filer) override;
    virtual Acad::ErrorStatus dwgOutFields(AcDbDwgFiler* filer) const override;
    virtual Acad::ErrorStatus dxfInFields(AcDbDxfFiler* filer) override;
    virtual Acad::ErrorStatus dxfOutFields(AcDbDxfFiler* filer) const override;

private:
    Adesk::Int16 mValue;
};
