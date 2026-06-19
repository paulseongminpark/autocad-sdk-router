#include <tchar.h>
#include "rxregsvc.h"
#include "AriadneProtocol.h"

ACRX_NO_CONS_DEFINE_MEMBERS(AriadneProbeProtocol, AcRxObject);

class AriadneProbeProtocolImpl : public AriadneProbeProtocol
{
public:
    virtual const ACHAR* protocolName() const override
    {
        return _T("AriadneProbeProtocol");
    }
};

static AriadneProbeProtocolImpl* gProbeProtocol = nullptr;

void ariadneRegisterProbeProtocol()
{
    if (gProbeProtocol != nullptr)
        return;

    AriadneProbeProtocol::rxInit();
    acrxBuildClassHierarchy();
    gProbeProtocol = new AriadneProbeProtocolImpl();
    AriadneProbe::desc()->addX(AriadneProbeProtocol::desc(), gProbeProtocol);
}

void ariadneUnregisterProbeProtocol()
{
    if (gProbeProtocol == nullptr)
        return;

    AriadneProbe::desc()->delX(AriadneProbeProtocol::desc());
    delete gProbeProtocol;
    gProbeProtocol = nullptr;
    deleteAcRxClass(AriadneProbeProtocol::desc());
    acrxBuildClassHierarchy();
}

extern "C" __declspec(dllexport) bool ariadneProbeProtocolAvailable()
{
    if (gProbeProtocol == nullptr)
        return false;

    AcRxObject* protocol = AriadneProbe::desc()->queryX(AriadneProbeProtocol::desc());
    return protocol != nullptr;
}
