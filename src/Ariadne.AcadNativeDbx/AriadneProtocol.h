#pragma once

#include "rxobject.h"
#include "AriadneProbe.h"

class AriadneProbeProtocol : public AcRxObject
{
public:
    ACRX_DECLARE_MEMBERS(AriadneProbeProtocol);
    virtual const ACHAR* protocolName() const = 0;
};

void ariadneRegisterProbeProtocol();
void ariadneUnregisterProbeProtocol();
