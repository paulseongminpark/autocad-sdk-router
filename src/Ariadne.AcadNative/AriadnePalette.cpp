//////////////////////////////////////////////////////////////////////////////
// AriadnePalette.cpp  (M07B)
//
// Attended-only status UI for the CAD agent. Compiled ONLY into the .arx module
// (it is listed solely in Ariadne.AcadNative.arx.vcxproj, never the headless
// .crx project), and its registration in acrxEntryPoint is wrapped in
// #ifndef ARIADNE_NATIVE_CRX, so the headless module neither compiles nor links
// any of this.
//
// Registers the ARIADNE_PALETTE command which, in a full AutoCAD editor, shows a
// status surface (CAD agent wiring + live-pump command names + working-database
// presence) via acedAlert. This is the MFC-FREE status-panel skeleton: a full
// docked CAdUiPaletteSet is the deliberate MFC-dependent enhancement
// (docs/NATIVE_DEEP_SURFACE_STATUS.md). Pulling MFC into this ObjectARX module
// would change its runtime/linkage and risk the existing (non-MFC) build, which
// the M07B packet forbids ("do not destabilize headless .crx / existing build"),
// so the skeleton is intentionally MFC-free.
//
// It is acedEditor-guarded: a no-op (command-line note) without a live editor.
// It exposes NO raw command surface and initiates no destructive command.
//////////////////////////////////////////////////////////////////////////////
#include <string>
#include <sstream>
#include <tchar.h>
#include <windows.h>

#include "aced.h"
#include "rxregsvc.h"
#include "dbmain.h"
#include "dbapserv.h"
#include "acutads.h"
#include "adscodes.h"
#include "acedads.h"   // acedAlert

// ARIADNE_PALETTE command body: attended-only status dialog.
static void ariadnePaletteShow()
{
    if (acedEditor == nullptr) {
        acutPrintf(_T("\nARIADNE_PALETTE requires a full AutoCAD editor (attended).\n"));
        return;
    }
    AcDbDatabase* pDb = acdbHostApplicationServices()->workingDatabase();

    std::wostringstream s;
    s << L"Ariadne CAD Agent  status\n\n"
      << L"Live pump command  : CADAGENT_PUMP\n"
      << L"Pump health command: CADAGENT_STATUS\n"
      << L"Native job command : ARIADNE_NATIVE_JOB / ARIADNE_NATIVE_JOB_ARGS\n"
      << L"Working database   : " << (pDb != nullptr ? L"present" : L"none") << L"\n\n"
      << L"Read-only surface. Mutation routes through the M05 staged-patch governor.";
    acedAlert(s.str().c_str());
    acutPrintf(_T("\nARIADNE_PALETTE: status surface shown.\n"));
}

// Called by acrxEntryPoint (AriadneNativeJob.cpp) under #ifndef ARIADNE_NATIVE_CRX
// so the command is registered ONLY in the attended .arx module. extern "C" gives
// it an undecorated name so the cross-TU reference resolves deterministically.
extern "C" void ariadneRegisterPaletteCommand()
{
    acedRegCmds->addCommand(_T("ARIADNE_NATIVE"),
                            _T("ARIADNE_PALETTE"),
                            _T("ARIADNE_PALETTE"),
                            ACRX_CMD_MODAL,
                            &ariadnePaletteShow);
}
