## Slice: arx-framework

> Application framework, module lifecycle, build & load toolchain for the native C++
> ObjectARX/ObjectDBX surface (ObjectARX SDK 2027, AutoCAD 2027, `ACD`/release `2027`).
> Every row is backed by a doc fetched or a header read THIS session — see *Sources actually read*.
> Engine-tier vocab: `native_arx_only` | `objectdbx_capable` | `managed_also` | `accoreconsole_lisp_also`.
> Citations: `[RG …]` = OARX-2027 Reference Guide HTML page (fetched); `[DOC …]` = AutoCAD-2027
> Customization/Core help page (fetched); `[HDR file:line]` = local header `C:\ObjectARX 2027\inc\…`
> read this session; `[SFDC …]` = Autodesk support article (fetched).

### Operation catalog

| proposed_op_id | native API (class::method / macro) | engine_tier | what it does | key inputs | key outputs | dwg_persisted? | execution_context | citation |
|---|---|---|---|---|---|---|---|---|
| `module.entrypoint.define` | `IMPLEMENT_ARX_ENTRYPOINT(classname)` (→ `IMPLEMENT_ARX_ENTRYPOINT_STD`) | `native_arx_only` | Emits the single `extern "C" __declspec(dllexport) acrxEntryPoint`, instantiates the app object `entryPointObject`, and defines `acrxGetApp()`. This is THE bootstrap macro a native module must invoke exactly once. | `classname` (your `AcRxArxApp`/`AcRxDbxApp` subclass) | exported `acrxEntryPoint`; global `AcRxDbxApp* acrxGetApp()`; `HINSTANCE _hdllInstance` | no | host or hostless_dbx (compile-time) | [HDR dbxEntryPoint.h:172-186] |
| `module.entrypoint.dispatch` | `AcRxDbxApp::acrxEntryPoint(AcRx::AppMsgCode msg, void* pkt)` | `native_arx_only` | Raw AutoCAD↔module message pump. A `switch(msg)` that routes each `AppMsgCode` to its `On_k*` virtual. Return `AcRx::AppRetCode` (`kRetOK` default). This is the C++-level mirror of nothing in managed — .NET hides it behind `IExtensionApplication`. | `msg` (AppMsgCode), `pkt` (object packet ptr) | `AcRx::AppRetCode` | no | host or hostless_dbx | [RG acrxEntryPoint], [HDR dbxEntryPoint.h:129-149] |
| `module.lifecycle.init` | `AcRxArxApp::On_kInitAppMsg(void* pkt)` / `AcRxDbxApp::On_kInitAppMsg` | `native_arx_only` | Load-time hook. ARX form registers ARX commands + command groups and may create the Dynamic Property Manager singleton; DBX base saves module instance, calls `RegisterServerComponents()`, registers custom AcRx classes (RTTI). Override target for "on load, register everything." | `pkt` | `AppRetCode` | no | host (ARX) / hostless_dbx (DBX) | [RG AcRxArxApp::On_kInitAppMsg], [HDR dbxEntryPoint.h:78-104] |
| `module.lifecycle.unload` | `AcRxArxApp::On_kUnloadAppMsg` / `AcRxDbxApp::On_kUnloadAppMsg` | `native_arx_only` | Unload-time hook. ARX form unregisters commands + groups, optionally releases Dynamic Property Manager; DBX base unregisters custom classes "in the right order" (descendant-first via `DeleteClassAndDescendant`). Override target for clean teardown. | `pkt` | `AppRetCode` | no | host (ARX) / hostless_dbx (DBX) | [RG AcRxArxApp::On_kUnloadAppMsg], [RG AcRxDbxApp::On_kUnloadAppMsg], [HDR dbxEntryPoint.h:105-167] |
| `module.lifecycle.on_load_dwg` | `AcRxDbxApp::On_kLoadDwgMsg(void* pkt)` | `native_arx_only` | Fired once the full acedXxx (editor) API is guaranteed available — the correct place to do work needing the document/editor, not `kInitAppMsg`. Default returns `kRetOK`. | `pkt` | `AppRetCode` | no | host | [HDR dbxEntryPoint.h:114], [RG AcRxDbxApp Methods] |
| `module.lifecycle.on_unload_dwg` | `AcRxDbxApp::On_kUnloadDwgMsg(void* pkt)` | `native_arx_only` | Per-document unload counterpart of `kLoadDwgMsg`. | `pkt` | `AppRetCode` | no | host | [HDR dbxEntryPoint.h:115] |
| `module.lifecycle.on_ole_unload` | `AcRxDbxApp::On_kOleUnloadAppMsg(void* pkt)` | `native_arx_only` | Hook to veto/limit unload while OLE/in-use; override to control unloadability. | `pkt` | `AppRetCode` | no | host | [HDR dbxEntryPoint.h:123], [RG AcRxDbxApp Methods] |
| `module.lifecycle.other` | `On_kCfgMsg`/`On_kEndMsg`/`On_kQuitMsg`/`On_kPreQuitMsg`/`On_kSaveMsg`/`On_kInvkSubrMsg`/`On_kDependencyMsg`/`On_kNoDependencyMsg`/`On_kInitDialogMsg`/`On_kEndDialogMsg`/`On_kNullMsg` | `native_arx_only` | The remaining 11 dispatched lifecycle messages; all default to `kRetOK`. Override only the ones you need. Full dispatched set = 16 (see C++-only delta). | `pkt` | `AppRetCode` | no | host | [HDR dbxEntryPoint.h:114-149], [RG AcRxDbxApp Methods] |
| `module.command.register_auto` | `ACED_ARXCOMMAND_ENTRYBYID_AUTO(classname, group, globCmd, locCmdId, cmdFlags, UIContext)` | `native_arx_only` | Declarative command registration: drops a `_ARXCOMMAND_ENTRY` into the `ARXCOMMAND$__m` linker section so `AcRxArxApp` auto-registers it at `kInitAppMsg` (no hand-written `addCommand`). The wizard/`AcRxArxApp` pattern. Handler = `classname::group##globCmd`. | classname, group, global cmd, local cmd resource id, cmd flags, UIContext | command registered in stack on load | no | host | [HDR dbxEntryPoint.h:65-67], [RG AcRxArxApp] |
| `module.command.register_manual` | `acedRegCmds->addCommand(grp, glob, loc, flags, fn, UIContext, fcode, resInst, &cmdPtr)` | `native_arx_only` (cmd object) | Imperative command registration into the one global command stack. Creates an `AcEdCommand`, copies names, stores flags + `AcRxFunctionPtr`. Group auto-created if new. Names ≤30 chars; dup → `eDuplicateKey`. This is the C++ mirror of `[CommandMethod]`. | group/global/local names, `commandFlags`, `AcRxFunctionPtr`, opt UIContext/fcode/resource | `Acad::ErrorStatus`; optional `AcEdCommand*` | no | host (session vs doc set by flags) | [RG AcEdCommandStack], [DOC AcEdCommandStack::addCommand], [DOC Command Stack] |
| `module.command.flags` | `commandFlags` bitmask (`ACRX_CMD_MODAL`/`_TRANSPARENT` + `_SESSION`/`_USEPICKSET`/`_REDRAW`/`_DOCREADLOCK`/`_DOCEXCLUSIVELOCK`/`_INTERRUPTIBLE`/`_NOHISTORY`/`_NO_UNDO_MARKER`/`_NOBEDIT`/`_UNDEFINED`/…) | `native_arx_only` | Defines a command's execution semantics. Primary (exactly one): `MODAL` vs `TRANSPARENT`. Key secondary: `ACRX_CMD_SESSION` = run in application (session) context vs current-document context — the lever for the router's "session vs document" distinction. `_DOCREADLOCK`/`_DOCEXCLUSIVELOCK` set lock mode. | flag constants OR'd | semantics applied at invoke | no | host | [DOC AcEdCommandStack::addCommand] |
| `module.command.remove_group` | `AcEdCommandStack::removeGroup(grpName)` (+ `removeCmd`) | `native_arx_only` | Cleanup: remove a whole command group (usual `kUnloadAppMsg` step) or one command. Required before unload. | group name (or cmd) | `Acad::ErrorStatus` | no | host | [DOC Command Stack] |
| `module.command.lookup` | `acedRegCmds->lookupCmd2(...)` via `acedCmdLookup2(cmdStr, globalLookup, retStruc, sf)` | `native_arx_only` | Search the command stack for a command; returns fn addr + flags + `AcEdCommand*` in `AcEdCommandStruc`. Lets the router introspect/verify a registered command before invoking. | cmd name, global/local flag, skip-flags | found struct / 0 on miss | no | host | [DOC acedCmdLookup2] |
| `module.command.stack_handle` | `acedRegCmds` macro = `AcEdCommandStack::cast(acrxSysRegistry()->at(ACRX_COMMAND_DOCK))` | `native_arx_only` | The single accessor to the one-per-session command stack. Entry point for all add/remove/lookup. | — | `AcEdCommandStack*` | no | host | [RG acedRegCmds], [RG AcEdCommandStack] |
| `module.ads.register_symbol` | `ACED_ADSSYMBOL_ENTRYBYID_AUTO(classname, name, nameId, regFunc)` / `ACED_ADSCOMMAND_ENTRYBYID_AUTO` | `native_arx_only` | Declaratively expose a native function as an AutoLISP/ADS-callable symbol (`classname::ads_##name`) via the `ADSSYMBOL$__m` section. How a native routine becomes callable from LISP — the router can drive native ops through `(symbol …)`. | classname, symbol name, name resource id, reg func | ADS symbol registered on load | no | host | [HDR dbxEntryPoint.h:114-119], [RG AcRxArxApp] |
| `module.load` | `acrxLoadModule(const ACHAR* moduleName, bool printit, bool asCmd=false)` | `native_arx_only` | Programmatically load a `.arx`/module into the running host from C++ (peer to `ARX`/`APPLOAD`/`arxload`). The router's "load a sibling native module" primitive. | module filename, printit, asCmd | `bool` success | no | host | [HDR rxregsvc.h:27] |
| `module.load.by_app` | `acrxLoadApp(const ACHAR* appname, bool asCmd=false)` | `native_arx_only` | Load by registered application name (demand-load registry key resolves the file). | app name, asCmd | `bool` | no | host | [HDR rxregsvc.h:31] |
| `module.unload` | `acrxUnloadModule(const ACHAR* moduleName, bool asCmd=false)` / `acrxUnloadApp(appName, asCmd)` | `native_arx_only` | Programmatically unload a module/app. Note: locked apps cannot be unloaded; ObjectARX apps cannot be *reloaded* without unload-then-load. | module/app name, asCmd | `bool` | no | host | [HDR rxregsvc.h:37,41], [DOC arxunload], [DOC Load/Unload Applications] |
| `module.load.demand_register` | Registry: `HKLM\…\R<ver>\<prodkey>\Applications\<app>` keys `LOADER`,`DESCRIPTION`,`LOADCTRLS`,`MANAGED` (+ optional command sub-keys) | `native_arx_only` | Register a native module for demand loading so the host loads it automatically on custom-object detect and/or command invoke. `LOADCTRLS` bitmask matches `DEMANDLOAD`; `MANAGED=0` for native ARX. The router's "install once, auto-available" path. | registry key + values; `acet-reg-machine-prodkey` gives the base path | persistent auto-load | no | host (install-time) | [SFDC How to autoload DLLs], [DOC DEMANDLOAD], [DOC acet-reg-machine-prodkey] |
| `module.load.acad_rx` | `acad.rx` file listing module names | `accoreconsole_lisp_also` | Per-directory ASCII file of ObjectARX module names auto-loaded at startup; honored by core (incl. accoreconsole startup). Lowest-friction host-side autoload. | text file of names | auto-load at startup | no | host | [DOC About Loading ObjectARX Applications] |
| `module.load.lisp` | `(arxload "name" [onfailure])` / `(arxunload "name")` / `(arx)` | `accoreconsole_lisp_also` | LISP-driven load/unload/list of native modules — usable from an accoreconsole `.scr` script. The hostless-batch lever for getting a native `.arx` into accoreconsole. | module name | program name / error | no | host or accoreconsole | [DOC arxload], [DOC arxunload], [DOC ARX (Command)] |
| `module.register_service` | `acrxRegisterService(const ACHAR* serviceName)` | `native_arx_only` | Register a named RX service in the system registry so other modules can find/depend on this one (`acrxSysRegistry()`/`ARX → Services`). Foundation for inter-module dependency. | service name (+ internal `AcRxService*` overload) | service ptr | no | host or hostless_dbx | [HDR rxregsvc.h:123,126], [DOC ARX (Command) → Services] |
| `module.register_mdi` | `acrxRegisterAppMDIAware(void* appId)` / `acrxRegisterAppNotMDIAware(void* appId)` | `native_arx_only` | Declare MDI (multi-document) awareness — must be called during init so the host knows the module is safe across multiple open documents. Order: declare before doing document work. | appId (from `pkt` at init) | `bool` | no | host | [HDR rxregsvc.h:159,164] |
| `module.class.register_object` | `AcRxObject`/`AcDbObject` RTTI registration via `RegisterServerComponents()` + DBX object-map (`__pDbxCustObjMapEntry…`) | `objectdbx_capable` | Custom class/RTTI registration driven from `On_kInitAppMsg`; pure-virtual `RegisterServerComponents()` is where a DBX/ARX module registers COM server + custom-entity info. Enables custom entities/objects to live in the DWG. | class descriptors via auto map | classes registered/RTTI live | yes (objects persist in DWG) | host or hostless_dbx | [HDR dbxEntryPoint.h:88-104,151], [RG AcRxDbxApp] |
| `module.app.accessor` | `acrxGetApp()` → `AcRxDbxApp*`; `GetModuleInstance()` → `HINSTANCE&` | `native_arx_only` | Retrieve the running app object / module HINSTANCE (for resource loading, re-entrancy). | — | `AcRxDbxApp*` / `HINSTANCE&` | no | host or hostless_dbx | [HDR dbxEntryPoint.h:152,170-178], [RG AcRxDbxApp Methods] |

> **unverified** (do NOT emit as fact without re-check): `acrxServiceIsLoaded(...)` and an
> `ACRX_SERVICE_ENTRY_AUTO` macro — NOT found in `rxregsvc.h`/`dbxEntryPoint.h` for 2027 this
> session. The exact `AcRx::AppMsgCode`/`AppRetCode` enum *declaration* lives in a header not
> opened this session (the 16 enumerators are nonetheless ground-truthed from the
> `acrxEntryPoint` switch, [HDR dbxEntryPoint.h:131-146]). `removeGroup`/`removeCmd`/`lookupCmd2`
> exact 2027 signatures are from DevGuide/older-RefGuide prose, not the 2027 RefGuide method page.

### Classes & subsystems covered

- **`AcRxDbxApp`** (`dbxEntryPoint.h`) — base application class for **DBX modules** (host-less, ObjectDBX). Defines the `acrxEntryPoint` dispatch `switch`, the 16 `On_k*` virtuals (all default `kRetOK` except `kInitAppMsg`/`kUnloadAppMsg` which manage RTTI class registration), pure-virtual `RegisterServerComponents()`, and `GetModuleInstance()`. [RG AcRxDbxApp], [HDR dbxEntryPoint.h:68-167]
- **`AcRxArxApp : public AcRxDbxApp`** (`arxEntryPoint.h`) — application class for **full `.arx` apps** (require AutoCAD host). Adds ARX/ADS **command** + **symbol** auto-registration and Dynamic Property Manager singleton creation; its `On_kInitAppMsg`/`On_kUnloadAppMsg` register/unregister commands and groups. [RG AcRxArxApp], [HDR arxEntryPoint.h:122]
- **Entry-point macros** (`dbxEntryPoint.h`) — `IMPLEMENT_ARX_ENTRYPOINT` ≡ `..._STD` ≡ `..._CLR` (all identical in 2027): instantiate app object, export `acrxEntryPoint`, define `acrxGetApp()`. [HDR dbxEntryPoint.h:172-186]
- **Auto-registration macros** (`dbxEntryPoint.h`) — `ACED_ARXCOMMAND_ENTRYBYID_AUTO` (command), `ACED_ADSSYMBOL_ENTRYBYID_AUTO`/`ACED_ADSCOMMAND_ENTRYBYID_AUTO` (LISP/ADS symbol) write entries into named PE sections (`ARXCOMMAND$__m`, `ADSSYMBOL$__m`) that `AcRxArxApp` walks at init. [HDR dbxEntryPoint.h:65-119]
- **`AcEdCommandStack`** + **`AcEdCommand`** + **`acedRegCmds`** (`accmd.h`) — one-per-session command registry; `addCommand`/`removeGroup`/`removeCmd`/`lookupCmd2`; command-flag taxonomy incl. the `ACRX_CMD_SESSION` (session vs document) and lock flags. [RG AcEdCommandStack], [RG AcEdCommand], [RG acedRegCmds], [DOC AcEdCommandStack::addCommand], [DOC Command Stack]
- **RX runtime / loader** (`rxregsvc.h`) — `acrxLoadModule`/`acrxLoadApp`/`acrxUnloadModule`/`acrxUnloadApp`, `acrxRegisterService`, `acrxRegisterAppMDIAware`/`acrxRegisterAppNotMDIAware`. [HDR rxregsvc.h:27-165]
- **Host load surface** — `ARX`/`APPLOAD` commands, Startup Suite, `acad.rx`, demand-load registry keys (`LOADER`/`LOADCTRLS`/`MANAGED`), `DEMANDLOAD` sysvar, `SECURELOAD`/`TRUSTEDPATHS` security gate. [DOC ARX (Command)], [DOC About Loading ObjectARX Applications], [DOC DEMANDLOAD], [SFDC How to autoload DLLs]

### Build / integration notes (how a native ARX/DBX module is built & loaded so the router can call it)

**Minimal native module skeleton (router's invokable target):**
1. One source defines `class MyApp : public AcRxArxApp { public: virtual AcRx::AppRetCode On_kInitAppMsg(void* pkt){ AcRxArxApp::On_kInitAppMsg(pkt); /* register cmds */ return AcRx::kRetOK; } virtual AcRx::AppRetCode On_kUnloadAppMsg(void* pkt){ /* removeGroup */ return AcRxArxApp::On_kUnloadAppMsg(pkt);} virtual void RegisterServerComponents(){} };`
2. `IMPLEMENT_ARX_ENTRYPOINT(MyApp)` once — this is the only required exported symbol (`acrxEntryPoint`). [HDR dbxEntryPoint.h:172-186]
3. Register each op as a command via `ACED_ARXCOMMAND_ENTRYBYID_AUTO(...)` (declarative) or `acedRegCmds->addCommand(...)` in `On_kInitAppMsg` (imperative). For router "session vs document" choice, OR in `ACRX_CMD_SESSION` (session/application context) vs leave unset (current-document context). [HDR dbxEntryPoint.h:65-67], [DOC AcEdCommandStack::addCommand]

**`.arx` (full host) vs `.dbx` (host-less ObjectDBX):**
- `.arx` = DLL renamed `.arx`; loads into AutoCAD's address space; full `acedXxx` editor/command API; the file the router NETLOAD-analogue (`acrxLoadModule`/`ARX`/`arxload`) pulls in. [DOC About ObjectARX Applications]
- `.dbx` = ObjectDBX module subclassing `AcRxDbxApp`; **host-less** — no editor/command API, just database+RTTI+custom objects. This is what runs under **accoreconsole** (and RealDWG hosts), so DWG read/write + custom-entity enablement without a UI. Map router ops needing the editor → `.arx` (host); ops that are pure DWG/database → `.dbx` (hostless_dbx, accoreconsole-capable). [RG AcRxDbxApp], [DOC About ObjectARX Applications]

**Toolchain / link (2027):**
- **SDK**: AutoCAD 2027 ⇄ ObjectARX SDK **2027** only (no cross-version mix; recompile per release; .NET pairing = 10.0). [DOC About Application Compatibility]
- **Compiler/IDE**: Microsoft Visual Studio (C++) on Windows; module is a Win64 DLL. [DOC About ObjectARX Applications]
- **Headers**: `C:\ObjectARX 2027\inc` (entry-point: `arxEntryPoint.h`, `dbxEntryPoint.h`; commands: `accmd.h`; RX loader/service: `rxregsvc.h`). [HDR, verified present]
- **Libs**: link the 2027 import libs under `C:\ObjectARX 2027\lib-x64\` (e.g. `acad.lib`, `accore.lib`, `acdb*.lib`, `acge*.lib`, `rxapi.lib`/`acrxXX.lib`) — *exact lib filename set is in the SDK `lib-x64` dir / wizard property sheets; not all enumerated from a doc this session → confirm against the dir before quoting filenames.* The `arxEntryPoint.h`/`dbxEntryPoint.h` + `accmd.h` + `rxregsvc.h` includes determine which libs are mandatory (rxapi/accore/acdb at minimum).
- **Wizard**: the ObjectARX project/app wizard generates exactly the `AcRxArxApp`/`AcRxDbxApp` subclass + `IMPLEMENT_ARX_ENTRYPOINT` + auto-command-map scaffold described above ("This class is used by the ObjectARX Wizards"). [RG AcRxArxApp], [RG AcRxDbxApp]
- **64-bit only**; binary compatibility is per-release (ABI breaks each version → the recompile rule). [DOC About Application Compatibility]

**Loading paths for the router (most-certain → least):**
1. C++ in-process: `acrxLoadModule("MyApp.arx", true)` from a controlling module. [HDR rxregsvc.h:27]
2. accoreconsole `.scr`: `(arxload "MyApp")` for hostless/batch (DBX or ARX). [DOC arxload]
3. Demand-load registry (`LOADER`/`LOADCTRLS`/`MANAGED=0`) for auto-availability on command-invoke / custom-object detect. [SFDC How to autoload DLLs], [DOC DEMANDLOAD]
4. `acad.rx` / Startup Suite (APPLOAD) for startup autoload. [DOC About Loading ObjectARX Applications]
- **Security gate**: under `SECURELOAD=1|2` the module path MUST be in `TRUSTEDPATHS` or load is refused. The router must register its module dir as trusted. [DOC About Loading ObjectARX Applications]

### C++-only delta (what managed .NET cannot do / does weaker, and why)

- **Raw message-pump control.** `acrxEntryPoint`'s 16-message `switch` (`kInitAppMsg, kUnloadAppMsg, kLoadDwgMsg, kUnloadDwgMsg, kInvkSubrMsg, kCfgMsg, kEndMsg, kQuitMsg, kSaveMsg, kDependencyMsg, kNoDependencyMsg, kOleUnloadAppMsg, kPreQuitMsg, kInitDialogMsg, kEndDialogMsg, kNullMsg`) is C++-only; managed surfaces only `Initialize`/`Terminate` (`IExtensionApplication`). Fine-grained dependency/quit/dialog/OLE-unload hooks have no managed equivalent. [HDR dbxEntryPoint.h:131-146]
- **Host-less ObjectDBX (`.dbx`).** A native `AcRxDbxApp`/`.dbx` can run with **no AutoCAD UI** (under accoreconsole / RealDWG hosts). Managed .NET requires the AutoCAD/`accoremgd` host; there is no managed "DBX-only host-less" app. This is the decisive lever for the router's headless tier. [RG AcRxDbxApp], [DOC About ObjectARX Applications]
- **Custom object/entity enablers + RTTI registration order.** `RegisterServerComponents()` + the DBX object-map descendant-first class teardown is native C++; managed custom objects ultimately wrap this and cannot author a standalone object enabler. [HDR dbxEntryPoint.h:88-167]
- **Section-based auto-registration & `acrxLoadModule`/service registry.** Linker-section command/symbol maps (`ARXCOMMAND$__m`/`ADSSYMBOL$__m`) and the `acrxRegisterService` inter-module service registry are C++ link-time/runtime mechanisms with no managed analogue (managed uses `[CommandMethod]`/`[LispFunction]` reflection, and has no native RX service registry). [HDR dbxEntryPoint.h:65-119], [HDR rxregsvc.h:123-165]
- **MDI-awareness declaration** (`acrxRegisterAppMDIAware`) is a native init-time contract; managed apps are MDI-managed by the runtime and don't call it. [HDR rxregsvc.h:159-165]
- (Everything managed *can* do — basic commands, DB CRUD, xrecords — it does by **wrapping** ObjectARX; so managed is a strict subset here, except convenience.)

### Sources actually read

OARX 2027 Reference Guide (HTML, fetched via ctx_fetch_and_index this session):
- AcRxArxApp — https://help.autodesk.com/cloudhelp/2027/ENU/OARX-RefGuide/files/OARX-RefGuide-AcRxArxApp.html
- AcRxDbxApp — https://help.autodesk.com/cloudhelp/2027/ENU/OARX-RefGuide/files/OARX-RefGuide-AcRxDbxApp.html
- AcRxDbxApp::acrxEntryPoint — https://help.autodesk.com/cloudhelp/2027/ENU/OARX-RefGuide/files/OARX-RefGuide-AcRxDbxApp__acrxEntryPoint_AcRx__AppMsgCode_void__.html
- AcRxArxApp::On_kInitAppMsg — …OARX-RefGuide-AcRxArxApp__On_kInitAppMsg_void__.html
- AcRxArxApp::On_kUnloadAppMsg — …OARX-RefGuide-AcRxArxApp__On_kUnloadAppMsg_void__.html
- AcRxDbxApp::On_kUnloadAppMsg / On_kInitAppMsg / acrxEntryPoint / AcRxDbxApp Methods — …OARX-RefGuide-__MEMBERTYPE_Methods_AcRxDbxApp.html
- acedRegCmds — https://help.autodesk.com/cloudhelp/2027/ENU/OARX-RefGuide/files/OARX-RefGuide-acedRegCmds.html
- AcEdCommandStack — https://help.autodesk.com/cloudhelp/2027/ENU/OARX-RefGuide/files/OARX-RefGuide-AcEdCommandStack.html
- AcEdCommand — https://help.autodesk.com/cloudhelp/2027/ENU/OARX-RefGuide/files/OARX-RefGuide-AcEdCommand.html
- AcEdCommandStack::addCommand (signature page, 2025 RefGuide variant cross-checked) — …OARXMAC-RefGuide-AcEdCommandStack__addCommand_…html
- acedCmdLookup2 — …OARXMAC-RefGuide-acedCmdLookup2_…html

AutoCAD 2027 Customization / Core / AutoLISP help (fetched / MCP search this session):
- About ObjectARX Applications — …AutoCAD-Customization/…GUID-3FF72BD0-9863-4739-8A45-B14AF1B67B06.htm
- About Loading ObjectARX Applications — …GUID-409E18E6-7164-41CB-A188-97E79E42BC5A.htm
- ARX (Command) — …AutoCAD-Core/…GUID-477DDABE-C3D3-47A2-B481-60401C50492F.htm
- Load/Unload Applications Dialog Box (APPLOAD) — …GUID-49BC17B0-D6CC-4FD2-980F-184ACC9708E8.htm
- DEMANDLOAD (System Variable) — …GUID-D83F2DEA-CB76-4B3C-99A4-88D4904DB3E5.htm
- Command Stack (DevGuide) — …OARXMAC-DevGuide/…GUID-3AD35E70-ECDE-4042-B27B-2C9269996015.htm
- About Application Compatibility (SDK↔release matrix) — …AutoCAD-Customization/…GUID-D54B0935-1638-4F97-8B37-1EC3635A1E71.htm
- arxload / arxunload (AutoLISP Reference) — …GUID-965A0D2A-… / GUID-29092087-…
- acet-reg-machine-prodkey — …GUID-B7A7AC96-…
- (APS overview page fetched: https://aps.autodesk.com/developer/overview/objectarx-autocad-sdk)

Autodesk support article (fetched/MCP):
- How to autoload DLLs with AutoCAD products (demand-load registry keys LOADER/LOADCTRLS/MANAGED) — …How-to-autoload-DLLs-with-AutoCAD.html

Local headers read this session (`C:\ObjectARX 2027\inc\`, secondary signature cross-check):
- `dbxEntryPoint.h` (lines ~65-187: AcRxDbxApp class, On_k* virtuals, acrxEntryPoint switch, IMPLEMENT_ARX_ENTRYPOINT, ACED_*_ENTRYBYID_AUTO macros)
- `arxEntryPoint.h` (AcRxArxApp class + ARX command/ADS auto-entry macros)
- `rxregsvc.h` (acrxLoadModule/acrxLoadApp/acrxUnloadModule/acrxUnloadApp, acrxRegisterService, acrxRegisterAppMDIAware/NotMDIAware)

> NOTE on unreachable sources: the two requested DevGuide deep-links (GUID-9B4F6629… and
> GUID-C3F3C736…) returned SPA shells ("Help" only) via fetch this session — their substantive
> content was recovered through the static RefGuide pages + Customization pages above, not assumed.
