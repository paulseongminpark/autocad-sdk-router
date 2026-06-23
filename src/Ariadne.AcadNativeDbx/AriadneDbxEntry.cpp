#include "rxregsvc.h"

#define ARIADNE_DBX_BUILD
#include "AriadneDbxApi.h"
#include "..\Ariadne.AcadNative\AriadneProbe.h"
#include "AriadneRecord.h"
#include "AriadneProtocol.h"
#include "rxmember.h"
#include <tchar.h>

#ifdef _WIN64
#pragma comment(linker, "/export:acrxGetApiVersion,PRIVATE")
#else
#pragma comment(linker, "/export:_acrxGetApiVersion,PRIVATE")
#endif

extern "C" ARIADNE_DBX_API Acad::ErrorStatus ariadneCreateProbeEntity(
    AcDbEntity*& entity,
    double cx,
    double cy,
    double cz,
    double size)
{
    entity = nullptr;
    if (size <= 0.0)
        return Acad::eInvalidInput;

    AriadneProbe* probe = new AriadneProbe();
    Acad::ErrorStatus es = probe->setCenter(AcGePoint3d(cx, cy, cz));
    if (es == Acad::eOk)
        es = probe->setSize(size);
    if (es != Acad::eOk) {
        delete probe;
        return es;
    }

    entity = probe;
    return Acad::eOk;
}

extern "C" ARIADNE_DBX_API bool ariadneIsProbeEntity(const AcDbEntity* entity)
{
    return entity != nullptr && entity->isKindOf(AriadneProbe::desc());
}

extern "C" ARIADNE_DBX_API Acad::ErrorStatus ariadneCreateRecordObject(
    AcDbObject*& object,
    int value)
{
    object = nullptr;
    if (value < -32768 || value > 32767)
        return Acad::eInvalidInput;

    object = new AriadneRecord(static_cast<Adesk::Int16>(value));
    return Acad::eOk;
}

extern "C" ARIADNE_DBX_API bool ariadneIsRecordObject(const AcDbObject* object)
{
    return object != nullptr && object->isKindOf(AriadneRecord::desc());
}

extern "C" ARIADNE_DBX_API Acad::ErrorStatus ariadneRecordValue(const AcDbObject* object, int* valueOut)
{
    if (valueOut == nullptr)
        return Acad::eInvalidInput;
    *valueOut = 0;
    const AriadneRecord* record = AriadneRecord::cast(object);
    if (record == nullptr)
        return Acad::eNotThatKindOfClass;
    *valueOut = static_cast<int>(record->value());
    return Acad::eOk;
}

extern "C" ARIADNE_DBX_API Acad::ErrorStatus ariadneRecordSetValue(AcDbObject* object, int value)
{
    AriadneRecord* record = AriadneRecord::cast(object);
    if (record == nullptr)
        return Acad::eNotThatKindOfClass;
    if (value < -32768 || value > 32767)
        return Acad::eInvalidInput;
    return record->setValue(static_cast<Adesk::Int16>(value));
}

extern "C" ARIADNE_DBX_API bool ariadneRecordPartialUndoAvailable()
{
    return AriadneRecord::desc() != nullptr;
}

// M07A headless proof: is the OPM "Size" AcRxProperty registered on AriadneProbe?
// Uses the runtime member-query engine (the real OPM lookup path). Returns 1 if
// "Size" is found, 0 if not, -1 if the class/engine is unavailable (e.g. engine
// not present in this host). The attended OPM panel is verified separately.
extern "C" ARIADNE_DBX_API int ariadneProbePropertyCount()
{
    AcRxClass* cls = AriadneProbe::desc();
    if (cls == nullptr)
        return -1;
    AcRxMemberQueryEngine* eng = AcRxMemberQueryEngine::theEngine();
    if (eng == nullptr)
        return -1;
    AriadneProbe probe; // transient instance to query members on
    AcRxMemberIterator* it = eng->newMemberIterator(&probe);
    if (it == nullptr)
        return 0;
    AcRxMember* m = it->find(ACRX_T("Size")); // member owned by collection; do not free
    const int found = (m != nullptr) ? 1 : 0;
    delete it; // public virtual dtor (rxmember.h:373)
    return found;
}

extern "C" AcRx::AppRetCode __declspec(dllexport)
acrxEntryPoint(AcRx::AppMsgCode msg, void* pkt)
{
    switch (msg) {
    case AcRx::kInitAppMsg:
        acrxUnlockApplication(pkt);
        acrxRegisterAppMDIAware(pkt);
        AriadneProbe::rxInit();
        AriadneRecord::rxInit();
        acrxBuildClassHierarchy();
        ariadneRegisterProbeProtocol();
        break;

    case AcRx::kUnloadAppMsg:
        ariadneUnregisterProbeProtocol();
        deleteAcRxClass(AriadneRecord::desc());
        deleteAcRxClass(AriadneProbe::desc());
        acrxBuildClassHierarchy();
        break;

    default:
        break;
    }
    return AcRx::kRetOK;
}
