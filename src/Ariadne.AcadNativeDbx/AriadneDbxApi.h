#pragma once

#include "dbmain.h"
#include "dbents.h"

#ifdef ARIADNE_DBX_BUILD
#define ARIADNE_DBX_API __declspec(dllexport)
#else
#define ARIADNE_DBX_API __declspec(dllimport)
#endif

extern "C" {
ARIADNE_DBX_API Acad::ErrorStatus ariadneCreateProbeEntity(
    AcDbEntity*& entity,
    double cx,
    double cy,
    double cz,
    double size);

ARIADNE_DBX_API bool ariadneIsProbeEntity(const AcDbEntity* entity);

ARIADNE_DBX_API Acad::ErrorStatus ariadneCreateRecordObject(
    AcDbObject*& object,
    int value);

ARIADNE_DBX_API bool ariadneIsRecordObject(const AcDbObject* object);

ARIADNE_DBX_API bool ariadneProbeProtocolAvailable();

// M07A: count registered AcRxProperty members named "Size" on AriadneProbe::desc()
// (headless proof of OPM property registration). Returns >=1 if registered, 0 if
// none, -1 if the class/engine is unavailable.
ARIADNE_DBX_API int ariadneProbePropertyCount();
}
