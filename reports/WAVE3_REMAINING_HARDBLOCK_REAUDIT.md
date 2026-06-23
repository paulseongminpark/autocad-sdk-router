# Wave3 Remaining Hard-Block Re-Audit

Scope: post-merge re-audit of the remaining catalogued Wave3 operations after the pane merges and native reimplementation pass.

Rule applied: hard-block is accepted only for SDK_NOT_EXPOSED, HOST_UNAVAILABLE, LICENSE_UNAVAILABLE, SAFETY_FORBIDDEN, OBJECT_ENABLER_REQUIRED, or ORIGINAL_WRITE_FORBIDDEN. "Complex", "bespoke", "large scope", and "future version" were not used as blockers.

## Reversed To Implemented

### module.command.flags

Decision: implemented.

Evidence:
- `D:\dev\_tmp\sdk_route_reconstruction_20260605\ObjectARX_2027_net9_probe\inc\accmd-defs.h` exposes the `ACRX_CMD_*` command flag constants.
- `src/Ariadne.AcadNative/families/m08n_handlers.inc` implements a read-only flag inventory under `m08nDispatch`.
- `tests/unit/test_m08n_handlers.py::TestM08NHandlers::test_module_command_flags_is_read_only_inventory` prevents command-stack mutation or raw command exposure.

### inspect.subentity.color

Decision: implemented.

Evidence:
- ObjectARX 2027 headers expose read APIs: `AcDb3dSolid::getSubentColor`, `AcDbSurface::getSubentColor`, and `AcDbSubDMesh::getSubentColor`.
- `src/Ariadne.AcadNative/families/m08d_handlers.inc` implements a read-only handler for those supported entity classes.
- `tests/unit/test_m08d_handlers.py::TestM08DHandlers::test_subentity_color_read_uses_real_apis` requires real SDK getters and bans `setSubentColor`.

## Accepted Hard Blocks

### edit.subentity.add_paths
Blocker: SAFETY_FORBIDDEN.

Reason: `AcDbEntity::addSubentPaths` mutates subentity path association state on the target DB entity. The current CAD OS operation does not define a bounded staged-copy authoring contract for arbitrary subentity path mutation.

### edit.subentity.delete_paths
Blocker: SAFETY_FORBIDDEN.

Reason: `AcDbEntity::deleteSubentPaths` mutates subentity path association state. Safe read/status variants are implemented separately; this mutation is not exposed as an agent operation.

### edit.subentity.transform
Blocker: SAFETY_FORBIDDEN.

Reason: `AcDbEntity::transformSubentPathsBy` mutates selected subentity paths. The exact operation needs a validated staged authoring contract before exposure.

### ui.subentity.highlight
Blocker: HOST_UNAVAILABLE.

Reason: subentity highlighting requires a live graphics/editor selection context and graphics-system refresh. The integration route does not have a controlled attended AutoCAD editor host.

### automate.com.get_app
Blocker: SAFETY_FORBIDDEN.

Reason: exposes AutoCAD automation root `IDispatch` into the agent surface. Safe bridge-adjacent introspection exists elsewhere without returning COM pointers.

### automate.com.get_document
Blocker: SAFETY_FORBIDDEN.

Reason: exposes live document automation interfaces/pointers. The agent surface must not receive raw COM document handles.

### automate.com.get_for_command
Blocker: SAFETY_FORBIDDEN.

Reason: command-context COM acquisition exposes raw automation handles in a live command surface.

### automate.com.get_winapp
Blocker: SAFETY_FORBIDDEN.

Reason: exposes host application pointers/state outside a bounded introspection contract.

### automate.com.send_command
Blocker: SAFETY_FORBIDDEN.

Reason: COM `SendCommand` is raw command-string dispatch. It is not agent-exposed.

### automate.com.wrapper_for_object
Blocker: SAFETY_FORBIDDEN.

Reason: wraps raw AcDb objects into automation interfaces and exposes COM object handles to agents.

### embed.ole.frame
Blocker: HOST_UNAVAILABLE.

Reason: `AcDbOle2Frame` embedding/linking requires a live OLE client item and attended host context. No controlled attended OLE route or safe staged payload contract is available in this integration pass.

### module.command.remove_group
Blocker: SAFETY_FORBIDDEN.

Reason: arbitrary command group removal mutates the host command stack. The implemented lifecycle handlers only add/remove the bounded `ARIADNE_M08N` no-op command group during their own probe.

### module.entrypoint.define
Blocker: SDK_NOT_EXPOSED.

Reason: entrypoint definition is a compile/link-time ARX macro/export contract, not a runtime SDK operation callable by the CAD OS job dispatcher.

### module.entrypoint.dispatch
Blocker: HOST_UNAVAILABLE.

Reason: entrypoint dispatch is host-owned by the AutoCAD loader via `acrxEntryPoint`; the integration job dispatcher cannot synthesize loader messages safely.

### module.lifecycle.init
Blocker: HOST_UNAVAILABLE.

Reason: `On_kInitAppMsg` is delivered by the AutoCAD loader during module load. It is not a safe runtime job operation.

### module.lifecycle.on_load_dwg
Blocker: HOST_UNAVAILABLE.

Reason: `On_kLoadDwgMsg` is delivered by the AutoCAD host during document lifecycle events. No controlled attended lifecycle route is available.

### module.lifecycle.on_ole_unload
Blocker: HOST_UNAVAILABLE.

Reason: `On_kOleUnloadAppMsg` is a host lifecycle callback. It cannot be triggered safely from the CAD OS job surface.

### module.lifecycle.on_unload_dwg
Blocker: HOST_UNAVAILABLE.

Reason: `On_kUnloadDwgMsg` is host-owned document lifecycle dispatch, unavailable to the headless integration job route.

### module.lifecycle.other
Blocker: HOST_UNAVAILABLE.

Reason: arbitrary lifecycle message dispatch is host-owned and cannot be simulated safely by the agent job surface.

### module.lifecycle.unload
Blocker: HOST_UNAVAILABLE.

Reason: `On_kUnloadAppMsg` is delivered by the loader during module unload. The job dispatcher must not invoke it directly.

### module.load
Blocker: SAFETY_FORBIDDEN.

Reason: `acrxLoadModule` loads external code into the AutoCAD host process. Arbitrary module loading is not an agent-exposed operation.

### module.load.acad_rx
Blocker: SAFETY_FORBIDDEN.

Reason: ARX demand/load mechanics execute host modules and mutate runtime loader state.

### module.load.by_app
Blocker: SAFETY_FORBIDDEN.

Reason: application-driven module loading executes external code and mutates process loader state.

### module.load.lisp
Blocker: SAFETY_FORBIDDEN.

Reason: LISP loading executes script code in the AutoCAD host. It is not exposed as a raw agent load surface.

### module.unload
Blocker: SAFETY_FORBIDDEN.

Reason: `acrxUnloadModule` can unload host modules and destabilize the running process. It remains non-agent-exposed.
