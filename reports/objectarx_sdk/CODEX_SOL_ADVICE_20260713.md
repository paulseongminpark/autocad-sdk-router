Reading prompt from stdin...
OpenAI Codex v0.144.3
--------
workdir: D:\dev\99_tools\autocad-sdk-router
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: xhigh
reasoning summaries: none
session id: 019f5bb0-a9b2-75b3-a0b4-356fe622a169
--------
user
You are consulting as a senior ObjectARX / AutoCAD SDK + headless-CAD-automation architect. Give a prioritized STRATEGIC + TECHNICAL advisory on a full-system problem. Be concrete, ObjectARX-2027/accoreconsole-specific, and rank by impact. Assume the reader is an expert; skip basics.

## SYSTEM
`autocad-sdk-router` exposes the AutoCAD/ObjectARX 2027 SDK as a registry of 545 operations across 26 families, implemented as native C++ ObjectARX modules:
- `.crx` — loads in `accoreconsole.exe` (headless console host)
- `.dbx` — ObjectDBX Object Enabler (host-agnostic DB/geometry layer; loads in any RealDWG host incl. accoreconsole)
- `.arx` — loads in full `acad.exe` (interactive: editor/UI/graphics/COM)
One dispatch entry (`ariadneNativeJob`) matches an op-string to a handler; 16 family `.inc` files hold handlers; built via MSBuild + ObjectARX 2027 SDK. Original DWGs are READ-ONLY; every op runs against a staged copy.

## MEASURED STATE
- **484/545 ops already have real native handlers** (472 native `op==` branches + 17 router/managed-plane). A stale 2026-06-22 coverage report said "37 implemented" — that predated the bulk handler waves; the current 489-declared reconciles exactly (472 native + 17 managed).
- **2026-07-06 live headless probe** (accoreconsole, staged-copy fixtures) over 465 ops: **242 RUNNABLE** (real non-degenerate result), **161 REACHABLE** (dispatcher returns a structured arg/precondition error — needs valid-arg fixtures to do real work), **28 RUNNABLE_BUT_DEGENERATE** (succeeds on EMPTY args = input-unvalidated), **34 CRASH** (probe subprocess died / engine died mid-run / no parseable result).
- **Host split**: ~270 headless-eligible (dbx 250 + crx 20); ~234 wired ops need interactive acad.exe (ui_customization, com_activex live COM, editor prompts, graphics_system, live reactors).
- **61-op gap** (catalogued, no handler): constraints_associativity 23 (`define.assocarray.*`, `define.assocsurface.*`), runtime_commands 16 (`module.lifecycle/entrypoint/command.*` = ObjectARX load/unload callbacks), com_activex 9 (`automate.com.*` live COM), brep_solids 4 (`edit.subentity.*` interactive), active_document 4 (`command.invoke.*` — write_original policy-blocked), ui 2, layouts_plot_publish 2, editor 1.

## MANDATE (owner, emphatic)
Do the FULL scope — build/resolve EVERYTHING (including the unwired 61), fix EVERY problem found: all 34 CRASH, promote 161 REACHABLE→RUNNABLE, resolve 28 DEGENERATE (input validation), do the 2 registry re-tiers (custom_objects_protocols 57 arx→dbx; geometry_kernel 16 arx→dbx), fix tooling defects (a reconcile regex that misses w6/w7 family `.inc`; regenerate the stale coverage SoT), THEN upload to GitHub. Nothing deferred.

## ADVISE ON (prioritized, be specific)
1. **Sequencing / critical path**: ~89% wired but only ~half live-proven. Fastest+most-reliable order to reach "every op built AND headless-integrity-verified"? What blocks what?
2. **The 34 CRASH** — likeliest ObjectARX root-cause classes for a handler *crashing accoreconsole* (vs returning a clean error): ASM/modeler init, null AcDb pointer deref, exception thrown across the ARX C boundary, acutPrintf/format faults, worldDraw without a GS device, reactor firing headless. How to triage 34 systematically + cheaply?
3. **Headless feasibility verdicts** (the hard families): (a) AcDbAssocArray + associative constraints — does `AcDbAssocManager::evaluateTopLevelNetwork` + the DCM solver run under accoreconsole with no editor? (b) ASM init for constructive BRep/solid boolean ops headless — reliable or attended-only? (c) headless plot (`AcPlPlotEngine` → PDF/DWFx) under accoreconsole? (d) any of the 9 `automate.com.*` realizable in a console host, or strictly full-acad COM?
4. **runtime_commands 16** — these are `acrxEntryPoint`/`kInitAppMsg` load/unload callbacks, not job-dispatchable ops. Reclassify OUT of the op-registry, or is there a meaningful op-shaped exposure?
5. **Verification standard** — what makes an op "integrity-verified" headlessly (payload assertion, not rc=0)? For arx-only ops that can't be headless-smoked: mark `PASS_WITH_DEFERRAL:attended`, or require an attended acad.exe pass?
6. **custom_objects→dbx refactor** — share the family `.inc` into the `.dbx` vcxproj, extract shared headers, or a cleaner structure? Watch-outs for AcRxObject/AcDbObject subclassing + filers loaded as an Object Enabler.
7. **GitHub upload** — SDK headers/libs (`C:\ObjectARX 2027`) are Autodesk-licensed (never commit); built modules link Autodesk libs (non-redistributable). Source-only + build instructions, or a safe binary path? License landmines in shipping the op-registry/handler source?

Return: a ranked action plan (what to do in what order, with the gating dependencies) + firm technical verdicts on #2, #3, #4. Flag anything in the mandate that is technically infeasible or a bad idea, and say why.

codex
I’ll ground this in the current router surfaces first, then verify the hard feasibility claims against Autodesk 2027-era primary documentation where available. I’ll treat “everything” as an outcome requirement, but distinguish real operations from lifecycle events and flag any host-bound work that cannot honestly be called headless-verified.
  → Inspect memory and current repo truth surfaces, using CodeGraph first if indexed
  • Verify ObjectARX 2027 headless feasibility and licensing facts from primary sources
  • Synthesize ranked critical path, crash triage, verification gates, refactor, and release advice
exec
"C:\\Program Files\\WindowsApps\\Microsoft.PowerShell_7.6.3.0_x64__8wekyb3d8bbwe\\pwsh.exe" -Command "rg -n -i \"CAD OS packet bundle|accoreconsole|custom_objects|runtime_commands|coverage|reconcile|ObjectARX|headless\" \"C:\\Users\\PAUL\\.codex\\memories\\MEMORY.md\"" in D:\dev\99_tools\autocad-sdk-router
2026-07-13T13:35:53.830082Z ERROR codex_core::exec: exec error: windows sandbox: runner failed during SpawnChild: CreateProcessAsUserW failed: 1312 (지정한 로그온 세션이 없습니다. 이미 종료되었을 수도 있습니다.) | cwd=C:\Users\CodexSandboxOffline\.codex\.sandbox\cwd\aca5bac0736a413c | cmd="C:\Program Files\WindowsApps\Microsoft.PowerShell_7.6.3.0_x64__8wekyb3d8bbwe\pwsh.exe" -NoProfile -Command "try { [Console]::OutputEncoding=[System.Text.Encoding]::UTF8 } catch {}
rg -n -i \"CAD OS packet bundle|accoreconsole|custom_objects|runtime_commands|coverage|reconcile|ObjectARX|headless\" \"C:\Users\PAUL\.codex\memories\MEMORY.md\"" | env_u16_len=11976 | si_flags=256 | creation_flags=525312 (Windows error 1312)
2026-07-13T13:35:53.830354Z ERROR codex_core::tools::router: error=execution error: Io(Custom { kind: Other, error: "windows sandbox: runner failed during SpawnChild: CreateProcessAsUserW failed: 1312 (지정한 로그온 세션이 없습니다. 이미 종료되었을 수도 있습니다.) | cwd=C:\\Users\\CodexSandboxOffline\\.codex\\.sandbox\\cwd\\aca5bac0736a413c | cmd=\"C:\\Program Files\\WindowsApps\\Microsoft.PowerShell_7.6.3.0_x64__8wekyb3d8bbwe\\pwsh.exe\" -NoProfile -Command \"try { [Console]::OutputEncoding=[System.Text.Encoding]::UTF8 } catch {}\nrg -n -i \\\"CAD OS packet bundle|accoreconsole|custom_objects|runtime_commands|coverage|reconcile|ObjectARX|headless\\\" \\\"C:\\Users\\PAUL\\.codex\\memories\\MEMORY.md\\\"\" | env_u16_len=11976 | si_flags=256 | creation_flags=525312 (Windows error 1312)" })
 exited -1 in 0ms:
execution error: Io(Custom { kind: Other, error: "windows sandbox: runner failed during SpawnChild: CreateProcessAsUserW failed: 1312 (지정한 로그온 세션이 없습니다. 이미 종료되었을 수도 있습니다.) | cwd=C:\\Users\\CodexSandboxOffline\\.codex\\.sandbox\\cwd\\aca5bac0736a413c | cmd=\"C:\\Program Files\\WindowsApps\\Microsoft.PowerShell_7.6.3.0_x64__8wekyb3d8bbwe\\pwsh.exe\" -NoProfile -Command \"try { [Console]::OutputEncoding=[System.Text.Encoding]::UTF8 } catch {}\nrg -n -i \\\"CAD OS packet bundle|accoreconsole|custom_objects|runtime_commands|coverage|reconcile|ObjectARX|headless\\\" \\\"C:\\Users\\PAUL\\.codex\\memories\\MEMORY.md\\\"\" | env_u16_len=11976 | si_flags=256 | creation_flags=525312 (Windows error 1312)" })
exec
"C:\\Program Files\\WindowsApps\\Microsoft.PowerShell_7.6.3.0_x64__8wekyb3d8bbwe\\pwsh.exe" -Command 'Get-Location; Get-ChildItem -Force | Select-Object -First 30 Name,Mode' in D:\dev\99_tools\autocad-sdk-router
2026-07-13T13:35:58.589457Z ERROR codex_core::exec: exec error: windows sandbox: runner failed during SpawnChild: CreateProcessAsUserW failed: 1312 (지정한 로그온 세션이 없습니다. 이미 종료되었을 수도 있습니다.) | cwd=D:\dev\99_tools\autocad-sdk-router | cmd="C:\Program Files\WindowsApps\Microsoft.PowerShell_7.6.3.0_x64__8wekyb3d8bbwe\pwsh.exe" -NoProfile -Command "try { [Console]::OutputEncoding=[System.Text.Encoding]::UTF8 } catch {}
Get-Location; Get-ChildItem -Force | Select-Object -First 30 Name,Mode" | env_u16_len=11976 | si_flags=256 | creation_flags=525312 (Windows error 1312)
2026-07-13T13:35:58.589659Z ERROR codex_core::tools::router: error=execution error: Io(Custom { kind: Other, error: "windows sandbox: runner failed during SpawnChild: CreateProcessAsUserW failed: 1312 (지정한 로그온 세션이 없습니다. 이미 종료되었을 수도 있습니다.) | cwd=D:\\dev\\99_tools\\autocad-sdk-router | cmd=\"C:\\Program Files\\WindowsApps\\Microsoft.PowerShell_7.6.3.0_x64__8wekyb3d8bbwe\\pwsh.exe\" -NoProfile -Command \"try { [Console]::OutputEncoding=[System.Text.Encoding]::UTF8 } catch {}\nGet-Location; Get-ChildItem -Force | Select-Object -First 30 Name,Mode\" | env_u16_len=11976 | si_flags=256 | creation_flags=525312 (Windows error 1312)" })
 exited -1 in 0ms:
execution error: Io(Custom { kind: Other, error: "windows sandbox: runner failed during SpawnChild: CreateProcessAsUserW failed: 1312 (지정한 로그온 세션이 없습니다. 이미 종료되었을 수도 있습니다.) | cwd=D:\\dev\\99_tools\\autocad-sdk-router | cmd=\"C:\\Program Files\\WindowsApps\\Microsoft.PowerShell_7.6.3.0_x64__8wekyb3d8bbwe\\pwsh.exe\" -NoProfile -Command \"try { [Console]::OutputEncoding=[System.Text.Encoding]::UTF8 } catch {}\nGet-Location; Get-ChildItem -Force | Select-Object -First 30 Name,Mode\" | env_u16_len=11976 | si_flags=256 | creation_flags=525312 (Windows error 1312)" })
mcp: codegraph/codegraph_explore started
mcp: codegraph/codegraph_explore (completed)
mcp: codegraph/codegraph_explore started
mcp: codegraph/codegraph_explore (completed)
mcp: codegraph/codegraph_explore started
mcp: codegraph/codegraph_explore (completed)
codex
The current checkout adds an important wrinkle to the mandate: its own crash cross-check says the original 34-row sweep included a router-lane failure mode, and a later “Lane I” re-probe resolved many rows without native handler changes. I’m separating historical CRASH classifications from currently reproducible process faults before prescribing low-level ObjectARX fixes.
mcp: codegraph/codegraph_explore started
mcp: codegraph/codegraph_explore (completed)
mcp: codegraph/codegraph_explore started
mcp: codegraph/codegraph_explore (completed)
mcp: codegraph/codegraph_explore started
mcp: codegraph/codegraph_explore (completed)
mcp: autodeskProductHelp/search_help_content started
mcp: autodeskProductHelp/search_help_content started
mcp: autodeskProductHelp/search_help_content started
mcp: autodeskProductHelp/search_help_content started
mcp: autodeskProductHelp/search_help_content (completed)
mcp: autodeskProductHelp/search_help_content (completed)
mcp: autodeskProductHelp/search_help_content (completed)
mcp: autodeskProductHelp/search_help_content (completed)
mcp: autodeskProductHelp/search_help_content started
mcp: autodeskProductHelp/search_help_content started
mcp: autodeskProductHelp/search_help_content started
mcp: autodeskProductHelp/search_help_content started
mcp: autodeskProductHelp/search_help_content (completed)
mcp: autodeskProductHelp/search_help_content (completed)
mcp: autodeskProductHelp/search_help_content (completed)
mcp: autodeskProductHelp/search_help_content (completed)
mcp: codegraph/codegraph_explore started
mcp: codegraph/codegraph_explore (completed)
mcp: codegraph/codegraph_explore started
mcp: codegraph/codegraph_explore (completed)
mcp: codegraph/codegraph_explore started
mcp: codegraph/codegraph_explore (completed)
web search: 
web search: site:help.autodesk.com ObjectARX AcDbAssocManager evaluateTopLevelNetwork ...
web search: 
web search: site:help.autodesk.com/view/OARX "evaluateTopLevelNetwork" ...
web search: 
web search: 
web search: 
web search: site:aps.autodesk.com ObjectARX redistributable ARX binaries license ...
mcp: codegraph/codegraph_explore started
mcp: codegraph/codegraph_explore (completed)
web search: 
web search: site:help.autodesk.com/view/OARX/2027/ENU AutoCAD Core Console CRX ObjectARX limitations ...
mcp: codegraph/codegraph_explore started
mcp: codegraph/codegraph_explore (completed)
mcp: codegraph/codegraph_explore started
mcp: codegraph/codegraph_explore (completed)
web search: 
web search: https://help.autodesk.com/view/OARX/2026/ENU/?guid=OARX-RefGuide-AcDbAssocManager
web search: 
web search: site:help.autodesk.com/view/OARX/2026/ENU "AcDb3dSolid" "createBox" ...
web search: 
web search: site:help.autodesk.com/view/OARX/2027/ENU acrxEntryPoint kInitAppMsg kUnloadAppMsg ...
web search: 
web search: site:forums.autodesk.com accoreconsole ActiveX COM not supported Autodesk employee ...
web search: 
web search: site:aps.autodesk.com/en/docs/design-automation/v3/developers_guide/restrictions COM AutoCAD ...
mcp: codegraph/codegraph_explore started
mcp: codegraph/codegraph_explore (completed)
codex
The hard-family verdicts are converging: associative networks/DCM and ASM solids are valid Core Console targets, plotting is a Core Console target but not an ObjectDBX target, and AutoCAD ActiveX is a full-`acad.exe` host boundary. The only mandate item I would reject outright is claiming all catalog items are “headless verified”; lifecycle events and full-host APIs need different, mandatory gates—not deferrals disguised as passes.
Repo and Autodesk primary-source review complete; synthesizing the ranked architecture and acceptance gates now.
  ✓ Inspect memory and current repo truth surfaces, using CodeGraph first if indexed
  ✓ Verify ObjectARX 2027 headless feasibility and licensing facts from primary sources
  → Synthesize ranked critical path, crash triage, verification gates, refactor, and release advice
  ✓ Inspect memory and current repo truth surfaces, using CodeGraph first if indexed
  ✓ Verify ObjectARX 2027 headless feasibility and licensing facts from primary sources
  ✓ Synthesize ranked critical path, crash triage, verification gates, refactor, and release advice
codex
The mandate is achievable only as a three-lane certification program—not as “545 headless passes”:

1. Core Console lane: every genuinely headless-capable operation.
2. Full-`acad.exe` lane: COM, UI, editor, live graphics/reactors.
3. Module-lifecycle lane: `acrxEntryPoint`, load/unload, and command registration contracts.

No `PASS_WITH_DEFERRAL`. An attended-only operation must pass an attended test; a lifecycle event must pass a lifecycle test.

## Ranked critical path

| Priority | Work | Exit gate | Blocks |
|---|---|---|---|
| P0 | Repair the registry/reconcile/coverage truth model | One generated manifest reconciles catalog, compiled dispatch table, host tier, fixtures, and results | Everything |
| P1 | Re-run the historical CRASH-34 on the current build | Zero unexplained process deaths; every old row reclassified from fresh evidence | Bulk probing |
| P2 | Stabilize CRX/DBX/ARX boundaries and apply the two re-tiers | Clean dependency/import audit; DBX loads in Core Console independently | Reliable headless tests |
| P3 | Build typed argument schemas, fixtures, and semantic oracles | Every dispatchable op has valid, invalid, and persistence assertions | REACHABLE/DEGENERATE closure |
| P4 | Close all headless-capable gaps | All Core Console candidates pass semantic round trips | Attended closure |
| P5 | Close full-AutoCAD and lifecycle lanes | COM/UI/editor/reactor/lifecycle items pass in controlled `acad.exe` sessions | Release |
| P6 | Full matrix certification, soak, packaging, GitHub release | No crash, hollow success, stale evidence, original mutation, or deferral | Ship |

### P0 — fix the truth system before writing more handlers

The current reconcile regex accepts only `m08*_handlers.inc` names:

- [`RE_FAMFILE`](</D:/dev/99_tools/autocad-sdk-router/tools/reconcile_native_registry.py:73>) excludes the w6/w7 files.
- The real dispatcher explicitly includes w6/w7 families in [`familyHasOp`](</D:/dev/99_tools/autocad-sdk-router/src/Ariadne.AcadNative/AriadneNativeJob.cpp:6162>).
- The coverage generator still contains stale prose/count constants such as “517-operation” and `catalog_total_ops: 480` in [`operation_coverage_matrix.py`](</D:/dev/99_tools/autocad-sdk-router/tools/operation_coverage_matrix.py:341>).

Do not merely broaden the regex. Replace source scraping with compiled descriptors:

```cpp
struct OperationDescriptor {
    const char* id;
    HandlerFn handler;
    HostClass host;
    ArgumentContract contract;
};
```

Per-family descriptor tables should feed:

- Dispatch admission.
- Handler invocation.
- Registry reconciliation.
- Fixture enumeration.
- Coverage generation.

A function pointer makes a missing handler a compile/link failure. Generate a machine-readable build manifest from these tables; join it with `operations.v2.json` and fresh probe results. Coverage artifacts must carry the Git commit, module SHA-256/build ID, AutoCAD build, SDK release, and probe timestamp. Reject reports whose build ID does not match the tested module.

Also add explicit catalog fields:

```text
kind = operation | module_event | host_capability
dispatchable = true | false
verification_lane = coreconsole | full_autocad | lifecycle
```

You may preserve 545 catalog entries, but the 16 lifecycle entries must not inflate the dispatchable-op denominator.

### P1 — first establish whether CRASH-34 still exists

The checkout is already ahead of the stated July 6 snapshot. Its crash cross-check says a later router `live_edit` dispatch fix resolved 33 historical rows and warns that old CRASH rows can be artifacts of the pre-fix router, not native faults; see [`crash34_host_crosscheck.py`](</D:/dev/99_tools/autocad-sdk-router/tools/crash34_host_crosscheck.py:171>). Therefore, do not start by patching 34 handlers. Re-run all 34 against the current binary and current registry.

Cheap systematic triage:

1. Run exactly one operation per `accoreconsole.exe` process.
2. Record five flushed milestones: module loaded, command entered, handler entered, result committed, unload entered/completed.
3. Capture exit code, stderr/stdout, Windows event, and a full dump using WER LocalDumps or ProcDump.
4. Stack-hash dumps and investigate one representative per signature cluster.
5. Run each with both the empty control and a valid fixture.
6. After repair, repeat the affected family and then the full matrix; soak previously crashing cases at least 10–20 times.

Rank the probable causes this way:

1. **Router/host-lane misclassification.** Highest probability given the repository’s later evidence.
2. **Load/unload and class-registration lifetime faults.** ABI mismatch, duplicate `rxInit`, incorrect `deleteAcRxClass` ordering, unloading DBX/modeler modules with live objects, or reactors still registered. Exit-time crashes strongly implicate this class.
3. **Unchecked `Acad::ErrorStatus` and invalid object lifetime.** Every `acdbOpenObject` result and pointer must be checked. Never delete database-owned objects; never use a pointer after `close()`.
4. **Calling AcEd/AcGs/COM/UI services from Core Console.** `worldDraw()` must not be called manually with a null or fake draw context. Device-dependent semantics require a real GS device or full host.
5. **ASM invalid-input/lifetime errors.** Validate finite dimensions, tolerances, topology and operand state. On successful `AcDb3dSolid::booleanOper`, the other solid’s ShapeManager becomes null; touching it as if still geometrically valid is a classic post-boolean fault. Autodesk documents these ownership/error semantics in the [AcDb3dSolid method reference](https://help.autodesk.com/cloudhelp/2017/ENU/OARXMAC-RefGuide/files/OREFMAC-__MEMBERTYPE_Methods_AcDb3dSolid.html).
6. **Reactor reentrancy.** Do not write to the notifying object or recursively evaluate from notification callbacks. Queue work and suppress your own notifications with scoped guards.
7. **Exceptions/varargs crossing module boundaries.** No C++ exception may escape a command callback or `acrxEntryPoint`. Catch `std::exception` and `...`, emit a structured failure, and return. Treat SEH access violations as dump-and-terminate, not recoverable exceptions. Prefer preformatted strings over `acutPrintf` varargs; `%s/%ls/%hs` mismatches are process-fatal possibilities.

## Firm feasibility verdicts

### AcDbAssocArray, associative constraints, and DCM: headless-capable

**Verdict: YES in `accoreconsole`, with semantic proof required per action-body type. Not guaranteed in an arbitrary RealDWG host.**

The associative framework is database/action-network based. Autodesk identifies `AcDbAssocManager::evaluateTopLevelNetwork()` as the correct top-level evaluator; changes mark networks dirty but evaluation is explicitly initiated by the client, not by editor UI. [AcDbAssocAction reference](https://help.autodesk.com/cloudhelp/2018/ENU/OARX-RefGuide/files/OREF-AcDbAssocAction.html).

Implementation sequence should be:

1. Create source geometry and action body/dependencies.
2. Close all write-open objects; do not evaluate while retaining conflicting open pointers.
3. Mark the action/network appropriately dirty.
4. Call `evaluateTopLevelNetwork`.
5. Assert action/dependency statuses are up-to-date.
6. Assert actual dependent geometry changed.
7. Save, close, reopen, re-evaluate, and assert idempotence.

For constraints, assert solver status, DOF, and a driven mutation—not merely that a constraint object exists. For arrays, assert item count and item transforms. `define.assocsurface.*` additionally depends on the ASM lane and therefore gates on P2’s modeler proof.

### ASM solids and Boolean operations: headless-capable

**Verdict: YES; not attended-only.**

`AcDb3dSolid`, regions, and surfaces wrap ShapeManager geometry and expose primitive and Boolean APIs returning `Acad::ErrorStatus`. Autodesk describes `AcDb3dSolid` as the interface to the ShapeManager object and documents normal failures such as `eGeneralModelingFailure`. [ObjectARX class reference](https://help.autodesk.com/view/OARX/2026/ENU/?guid=OARX-RefGuide-AcDb_Classes).

Do not manually initialize ASM. Let the AutoCAD 2027 Core Console host load its matching modeler components. At startup, verify required runtime classes/modules are present; reject cleanly if not. Serialize modeler-heavy work within a process and use process isolation for fault containment.

The acceptance probe should create two known overlapping solids, calculate expected pre-volume/intersection, Boolean them, and verify volume/topology/bounds after reopen. The repository’s existing create-two-boxes/translate/union approach is the right baseline.

### Headless PDF/DWFx plotting: feasible, but CRX—not DBX

**Verdict: YES in Core Console. Operationally environment-sensitive, but not attended-only.**

Autodesk’s current Automation API explicitly supports plotting AutoCAD DWGs to DWF and PDF using the core engine. [Automation API overview](https://aps.autodesk.com/en/docs/design-automation/v3/developers_guide/overview/).

For direct `AcPlPlotEngine` use:

- Put the operation in CRX, because AcPl/current-layout services are host services.
- Set the target layout current and activate the correct paper-space viewport.
- Set `BACKGROUNDPLOT=0`.
- Validate with `AcPlPlotInfoValidator`.
- Require `processPlotState()==kNotPlotting`.
- Create only one plot engine at a time and strictly nest begin/end calls.
- Pin PC3/PMP, media canonical name, CTB/STB, fonts and output location.
- Destroy the engine on every path.

The API requires the layout and viewport to be current in the editor context. [PlotEngine reference](https://help.autodesk.com/cloudhelp/2022/ENU/OARX-ManagedRefGuide/files/OARX-ManagedRefGuide-Autodesk_AutoCAD_PlottingServices_PlotEngine.html).

Verification means parseable PDF/DWFx, expected page count and dimensions, nonblank content, and preferably expected text/vector markers—not “file exists.”

### `automate.com.*`: full AutoCAD only

**Verdict: NO for AutoCAD ActiveX in `accoreconsole`.**

The nine operations are realizable only against full `acad.exe` and the AutoCAD `AcadApplication` automation server. AutoCAD 2027 uses `AutoCAD.Application.26`. [AutoCAD 2027 ActiveX API history](https://help.autodesk.com/cloudhelp/2027/ENU/AutoCAD-ActiveX/files/GUID-F6CC58AF-B36D-4BFA-8701-3D976E5D82B6.htm). Autodesk’s core-engine automation guidance also states that ActiveX/COM object types are unsupported. [APS automation guidance](https://aps.autodesk.com/blog/design-automation-civil-3d-public-beta).

The full host may run with `Visible=false`, but it still requires:

- A logged-in interactive desktop session.
- STA COM initialization and a message pump.
- Busy/rejected-call retry handling.
- Serialized sessions to avoid ROT/profile collisions.

If an operation’s true semantic goal can be implemented through AcDb in Core Console, create a separate AcDb operation. Do not call that a COM verification.

## `runtime_commands` 16

**Firm verdict: remove them from the dispatchable operation registry.**

`acrxEntryPoint`, `kInitAppMsg`, and `kUnloadAppMsg` are host-to-module callbacks. Autodesk explicitly defines `acrxEntryPoint` as the host entry point replacing program `main()`. [ObjectARX entry-point documentation](https://help.autodesk.com/cloudhelp/2022/ENU/OARX-DevGuide/files/GUID-EF283E4A-4A67-444C-AD13-F03A2A88A08A.htm).

A command running inside a module cannot meaningfully test unloading that same module. Fake handlers would only prove that a dispatcher branch exists.

Retain the 16 IDs as `kind=module_event`, `dispatchable=false`, and verify them with a host lifecycle harness:

1. Start a clean host.
2. Load DBX then CRX/ARX.
3. Assert class/service/command registration.
4. Invoke a harmless registered command.
5. Unload from outside the module.
6. Assert commands, protocols, overrules, reactors and services are removed.
7. Reload and verify no duplicates.
8. Exit and verify no unload-time crash.

A callable `module.status` or `module.selftest` is useful, but it is a separate operation—not a substitute for actual lifecycle testing.

## Verification standard

A passing operation needs all of the following:

- Correct host, current build ID, current registry revision.
- Empty/invalid argument test returning a structured error without mutation.
- Valid-argument execution.
- Operation-specific semantic assertion.
- Original DWG hash unchanged.
- For writes: exact staged pre/post delta, save/close/reopen persistence, and no collateral change.
- No dialog, timeout, crash, unparseable result, or background residue.
- Evidence artifact containing inputs, fixture hash, output, exit code, and assertion details.

Classify final success only as:

```text
PASS_HEADLESS
PASS_ATTENDED
PASS_LIFECYCLE
```

Do not use `PASS_WITH_DEFERRAL` under this mandate.

Also, not every empty-argument success is degenerate. A true zero-argument inspection operation should declare `arguments_required=false`. Split the current 28 into:

- `ZERO_ARG_BY_CONTRACT`
- `INVALIDLY_DEFAULTED`

Only the latter needs rejection logic.

## DBX re-tier architecture

Do not compile the same family `.inc` containing class definitions into both CRX and DBX. That risks duplicate runtime descriptors, ODR problems, double `rxInit`, and incorrect filer ownership.

Use this ownership:

- **DBX:** custom `AcDbObject`/`AcDbEntity` definitions, filers, audit/clone behavior, protocol extensions, DB-only algorithms, AcGe geometry.
- **CRX:** job JSON decoding, staged-document command, Core Console host adapter, document locking, result serialization.
- **ARX:** AcEd/AcAp/AcUi, COM, palettes, editor prompts, GS-device interactions and attended wrappers.

The current checkout is already moving correctly: [`AriadneDbxEntry.cpp`](</D:/dev/99_tools/autocad-sdk-router/src/Ariadne.AcadNativeDbx/AriadneDbxEntry.cpp:112>) owns class initialization and exposes a narrow C ABI to the host module.

Keep that pattern. Avoid passing STL objects or ownership-sensitive C++ objects across DLL boundaries. Export C functions using `AcDbObject*`/`AcDbEntity*`, primitive values and explicit ownership rules. Autodesk recommends separating custom database classes into Object Enablers and warns about `__declspec(dllimport)` header-sharing pitfalls. [ObjectDBX/UI separation guidance](https://help.autodesk.com/cloudhelp/2022/ENU/OARX-DevGuide/files/GUID-CC6F7B70-7133-4F8C-882B-14145EE3E0FE.htm).

For the 57+16 re-tiers, verify with an import audit:

- No `aced*`, AcAp, AcUi, AcPl, COM or editor-only dependency in DBX.
- AcGi `worldDraw` implementations may remain for custom-object display, but must not create or assume an editor GS device.
- Load optional shared DBX dependencies by class/service presence and do not unload a modeler/AcBr module that another component may own.

## GitHub release

Public source-only is the safest default:

- Commit your registry, handlers, tests, schemas and build scripts.
- Require the user to install ObjectARX 2027 separately.
- Resolve the SDK through an environment/property-sheet path, never `C:\ObjectARX 2027`.
- Ignore SDK headers, import libraries, dumps, PDBs, host DLLs and locally licensed fixtures.
- Build on a licensed self-hosted runner. AutoCAD 2027 targets the R26.0/VS2026 VC++ 145 generation. [Autodesk’s 2027 engine notice](https://aps.autodesk.com/blog/end-autocad-2021-engine-new-autocad-2027-engine-released).

A binary release is not categorically prohibited. Autodesk explicitly describes Object Enablers as distributable and the SDK has a `Redistrib-x64` set intended for permitted dependencies. [Object Enabler overview](https://help.autodesk.com/cloudhelp/2022/ENU/OARX-DevGuide/files/GUID-FF60A11B-1169-483C-9A65-85203B3A1440.htm), [SDK directory/redist guidance](https://help.autodesk.com/cloudhelp/2022/ENU/OARX-DevGuide/files/GUID-4A1AEF78-79CE-4352-9BDC-318E594F00AF.htm).

If shipping binaries:

- Package only your ARX/CRX/DBX and explicitly permitted 2027 redistributables.
- Never bundle `acad.exe`, `acdb*.dll`, ASM/modeler DLLs, headers or import libraries unless the 2027 redist/license expressly lists them.
- Require a compatible licensed host.
- Code-sign ARX/CRX/DBX. Autodesk recommends signing these binary types. [Signing guidance](https://help.autodesk.com/cloudhelp/2027/ENU/AutoCAD-Customization/files/GUID-0A93626D-8389-45FC-969B-B86A2F37D691.htm).
- Audit copied Autodesk sample code and every third-party dependency before publishing.

The op-registry and original handler source are ordinarily your source code; calling documented Autodesk APIs is not itself a license problem. The landmines are copied SDK/sample material, redistributed Autodesk binaries, trademarks implying endorsement, and accidentally creating a purported standalone DWG host without a RealDWG license. The governing 2027 terms are published in Autodesk’s [ObjectARX SDK license](https://aps.autodesk.com/developer/overview/autocad-objectarx-sdk-licensing); legal review should decide the final public binary bundle.
tokens used
248,055
The mandate is achievable only as a three-lane certification program—not as “545 headless passes”:

1. Core Console lane: every genuinely headless-capable operation.
2. Full-`acad.exe` lane: COM, UI, editor, live graphics/reactors.
3. Module-lifecycle lane: `acrxEntryPoint`, load/unload, and command registration contracts.

No `PASS_WITH_DEFERRAL`. An attended-only operation must pass an attended test; a lifecycle event must pass a lifecycle test.

## Ranked critical path

| Priority | Work | Exit gate | Blocks |
|---|---|---|---|
| P0 | Repair the registry/reconcile/coverage truth model | One generated manifest reconciles catalog, compiled dispatch table, host tier, fixtures, and results | Everything |
| P1 | Re-run the historical CRASH-34 on the current build | Zero unexplained process deaths; every old row reclassified from fresh evidence | Bulk probing |
| P2 | Stabilize CRX/DBX/ARX boundaries and apply the two re-tiers | Clean dependency/import audit; DBX loads in Core Console independently | Reliable headless tests |
| P3 | Build typed argument schemas, fixtures, and semantic oracles | Every dispatchable op has valid, invalid, and persistence assertions | REACHABLE/DEGENERATE closure |
| P4 | Close all headless-capable gaps | All Core Console candidates pass semantic round trips | Attended closure |
| P5 | Close full-AutoCAD and lifecycle lanes | COM/UI/editor/reactor/lifecycle items pass in controlled `acad.exe` sessions | Release |
| P6 | Full matrix certification, soak, packaging, GitHub release | No crash, hollow success, stale evidence, original mutation, or deferral | Ship |

### P0 — fix the truth system before writing more handlers

The current reconcile regex accepts only `m08*_handlers.inc` names:

- [`RE_FAMFILE`](</D:/dev/99_tools/autocad-sdk-router/tools/reconcile_native_registry.py:73>) excludes the w6/w7 files.
- The real dispatcher explicitly includes w6/w7 families in [`familyHasOp`](</D:/dev/99_tools/autocad-sdk-router/src/Ariadne.AcadNative/AriadneNativeJob.cpp:6162>).
- The coverage generator still contains stale prose/count constants such as “517-operation” and `catalog_total_ops: 480` in [`operation_coverage_matrix.py`](</D:/dev/99_tools/autocad-sdk-router/tools/operation_coverage_matrix.py:341>).

Do not merely broaden the regex. Replace source scraping with compiled descriptors:

```cpp
struct OperationDescriptor {
    const char* id;
    HandlerFn handler;
    HostClass host;
    ArgumentContract contract;
};
```

Per-family descriptor tables should feed:

- Dispatch admission.
- Handler invocation.
- Registry reconciliation.
- Fixture enumeration.
- Coverage generation.

A function pointer makes a missing handler a compile/link failure. Generate a machine-readable build manifest from these tables; join it with `operations.v2.json` and fresh probe results. Coverage artifacts must carry the Git commit, module SHA-256/build ID, AutoCAD build, SDK release, and probe timestamp. Reject reports whose build ID does not match the tested module.

Also add explicit catalog fields:

```text
kind = operation | module_event | host_capability
dispatchable = true | false
verification_lane = coreconsole | full_autocad | lifecycle
```

You may preserve 545 catalog entries, but the 16 lifecycle entries must not inflate the dispatchable-op denominator.

### P1 — first establish whether CRASH-34 still exists

The checkout is already ahead of the stated July 6 snapshot. Its crash cross-check says a later router `live_edit` dispatch fix resolved 33 historical rows and warns that old CRASH rows can be artifacts of the pre-fix router, not native faults; see [`crash34_host_crosscheck.py`](</D:/dev/99_tools/autocad-sdk-router/tools/crash34_host_crosscheck.py:171>). Therefore, do not start by patching 34 handlers. Re-run all 34 against the current binary and current registry.

Cheap systematic triage:

1. Run exactly one operation per `accoreconsole.exe` process.
2. Record five flushed milestones: module loaded, command entered, handler entered, result committed, unload entered/completed.
3. Capture exit code, stderr/stdout, Windows event, and a full dump using WER LocalDumps or ProcDump.
4. Stack-hash dumps and investigate one representative per signature cluster.
5. Run each with both the empty control and a valid fixture.
6. After repair, repeat the affected family and then the full matrix; soak previously crashing cases at least 10–20 times.

Rank the probable causes this way:

1. **Router/host-lane misclassification.** Highest probability given the repository’s later evidence.
2. **Load/unload and class-registration lifetime faults.** ABI mismatch, duplicate `rxInit`, incorrect `deleteAcRxClass` ordering, unloading DBX/modeler modules with live objects, or reactors still registered. Exit-time crashes strongly implicate this class.
3. **Unchecked `Acad::ErrorStatus` and invalid object lifetime.** Every `acdbOpenObject` result and pointer must be checked. Never delete database-owned objects; never use a pointer after `close()`.
4. **Calling AcEd/AcGs/COM/UI services from Core Console.** `worldDraw()` must not be called manually with a null or fake draw context. Device-dependent semantics require a real GS device or full host.
5. **ASM invalid-input/lifetime errors.** Validate finite dimensions, tolerances, topology and operand state. On successful `AcDb3dSolid::booleanOper`, the other solid’s ShapeManager becomes null; touching it as if still geometrically valid is a classic post-boolean fault. Autodesk documents these ownership/error semantics in the [AcDb3dSolid method reference](https://help.autodesk.com/cloudhelp/2017/ENU/OARXMAC-RefGuide/files/OREFMAC-__MEMBERTYPE_Methods_AcDb3dSolid.html).
6. **Reactor reentrancy.** Do not write to the notifying object or recursively evaluate from notification callbacks. Queue work and suppress your own notifications with scoped guards.
7. **Exceptions/varargs crossing module boundaries.** No C++ exception may escape a command callback or `acrxEntryPoint`. Catch `std::exception` and `...`, emit a structured failure, and return. Treat SEH access violations as dump-and-terminate, not recoverable exceptions. Prefer preformatted strings over `acutPrintf` varargs; `%s/%ls/%hs` mismatches are process-fatal possibilities.

## Firm feasibility verdicts

### AcDbAssocArray, associative constraints, and DCM: headless-capable

**Verdict: YES in `accoreconsole`, with semantic proof required per action-body type. Not guaranteed in an arbitrary RealDWG host.**

The associative framework is database/action-network based. Autodesk identifies `AcDbAssocManager::evaluateTopLevelNetwork()` as the correct top-level evaluator; changes mark networks dirty but evaluation is explicitly initiated by the client, not by editor UI. [AcDbAssocAction reference](https://help.autodesk.com/cloudhelp/2018/ENU/OARX-RefGuide/files/OREF-AcDbAssocAction.html).

Implementation sequence should be:

1. Create source geometry and action body/dependencies.
2. Close all write-open objects; do not evaluate while retaining conflicting open pointers.
3. Mark the action/network appropriately dirty.
4. Call `evaluateTopLevelNetwork`.
5. Assert action/dependency statuses are up-to-date.
6. Assert actual dependent geometry changed.
7. Save, close, reopen, re-evaluate, and assert idempotence.

For constraints, assert solver status, DOF, and a driven mutation—not merely that a constraint object exists. For arrays, assert item count and item transforms. `define.assocsurface.*` additionally depends on the ASM lane and therefore gates on P2’s modeler proof.

### ASM solids and Boolean operations: headless-capable

**Verdict: YES; not attended-only.**

`AcDb3dSolid`, regions, and surfaces wrap ShapeManager geometry and expose primitive and Boolean APIs returning `Acad::ErrorStatus`. Autodesk describes `AcDb3dSolid` as the interface to the ShapeManager object and documents normal failures such as `eGeneralModelingFailure`. [ObjectARX class reference](https://help.autodesk.com/view/OARX/2026/ENU/?guid=OARX-RefGuide-AcDb_Classes).

Do not manually initialize ASM. Let the AutoCAD 2027 Core Console host load its matching modeler components. At startup, verify required runtime classes/modules are present; reject cleanly if not. Serialize modeler-heavy work within a process and use process isolation for fault containment.

The acceptance probe should create two known overlapping solids, calculate expected pre-volume/intersection, Boolean them, and verify volume/topology/bounds after reopen. The repository’s existing create-two-boxes/translate/union approach is the right baseline.

### Headless PDF/DWFx plotting: feasible, but CRX—not DBX

**Verdict: YES in Core Console. Operationally environment-sensitive, but not attended-only.**

Autodesk’s current Automation API explicitly supports plotting AutoCAD DWGs to DWF and PDF using the core engine. [Automation API overview](https://aps.autodesk.com/en/docs/design-automation/v3/developers_guide/overview/).

For direct `AcPlPlotEngine` use:

- Put the operation in CRX, because AcPl/current-layout services are host services.
- Set the target layout current and activate the correct paper-space viewport.
- Set `BACKGROUNDPLOT=0`.
- Validate with `AcPlPlotInfoValidator`.
- Require `processPlotState()==kNotPlotting`.
- Create only one plot engine at a time and strictly nest begin/end calls.
- Pin PC3/PMP, media canonical name, CTB/STB, fonts and output location.
- Destroy the engine on every path.

The API requires the layout and viewport to be current in the editor context. [PlotEngine reference](https://help.autodesk.com/cloudhelp/2022/ENU/OARX-ManagedRefGuide/files/OARX-ManagedRefGuide-Autodesk_AutoCAD_PlottingServices_PlotEngine.html).

Verification means parseable PDF/DWFx, expected page count and dimensions, nonblank content, and preferably expected text/vector markers—not “file exists.”

### `automate.com.*`: full AutoCAD only

**Verdict: NO for AutoCAD ActiveX in `accoreconsole`.**

The nine operations are realizable only against full `acad.exe` and the AutoCAD `AcadApplication` automation server. AutoCAD 2027 uses `AutoCAD.Application.26`. [AutoCAD 2027 ActiveX API history](https://help.autodesk.com/cloudhelp/2027/ENU/AutoCAD-ActiveX/files/GUID-F6CC58AF-B36D-4BFA-8701-3D976E5D82B6.htm). Autodesk’s core-engine automation guidance also states that ActiveX/COM object types are unsupported. [APS automation guidance](https://aps.autodesk.com/blog/design-automation-civil-3d-public-beta).

The full host may run with `Visible=false`, but it still requires:

- A logged-in interactive desktop session.
- STA COM initialization and a message pump.
- Busy/rejected-call retry handling.
- Serialized sessions to avoid ROT/profile collisions.

If an operation’s true semantic goal can be implemented through AcDb in Core Console, create a separate AcDb operation. Do not call that a COM verification.

## `runtime_commands` 16

**Firm verdict: remove them from the dispatchable operation registry.**

`acrxEntryPoint`, `kInitAppMsg`, and `kUnloadAppMsg` are host-to-module callbacks. Autodesk explicitly defines `acrxEntryPoint` as the host entry point replacing program `main()`. [ObjectARX entry-point documentation](https://help.autodesk.com/cloudhelp/2022/ENU/OARX-DevGuide/files/GUID-EF283E4A-4A67-444C-AD13-F03A2A88A08A.htm).

A command running inside a module cannot meaningfully test unloading that same module. Fake handlers would only prove that a dispatcher branch exists.

Retain the 16 IDs as `kind=module_event`, `dispatchable=false`, and verify them with a host lifecycle harness:

1. Start a clean host.
2. Load DBX then CRX/ARX.
3. Assert class/service/command registration.
4. Invoke a harmless registered command.
5. Unload from outside the module.
6. Assert commands, protocols, overrules, reactors and services are removed.
7. Reload and verify no duplicates.
8. Exit and verify no unload-time crash.

A callable `module.status` or `module.selftest` is useful, but it is a separate operation—not a substitute for actual lifecycle testing.

## Verification standard

A passing operation needs all of the following:

- Correct host, current build ID, current registry revision.
- Empty/invalid argument test returning a structured error without mutation.
- Valid-argument execution.
- Operation-specific semantic assertion.
- Original DWG hash unchanged.
- For writes: exact staged pre/post delta, save/close/reopen persistence, and no collateral change.
- No dialog, timeout, crash, unparseable result, or background residue.
- Evidence artifact containing inputs, fixture hash, output, exit code, and assertion details.

Classify final success only as:

```text
PASS_HEADLESS
PASS_ATTENDED
PASS_LIFECYCLE
```

Do not use `PASS_WITH_DEFERRAL` under this mandate.

Also, not every empty-argument success is degenerate. A true zero-argument inspection operation should declare `arguments_required=false`. Split the current 28 into:

- `ZERO_ARG_BY_CONTRACT`
- `INVALIDLY_DEFAULTED`

Only the latter needs rejection logic.

## DBX re-tier architecture

Do not compile the same family `.inc` containing class definitions into both CRX and DBX. That risks duplicate runtime descriptors, ODR problems, double `rxInit`, and incorrect filer ownership.

Use this ownership:

- **DBX:** custom `AcDbObject`/`AcDbEntity` definitions, filers, audit/clone behavior, protocol extensions, DB-only algorithms, AcGe geometry.
- **CRX:** job JSON decoding, staged-document command, Core Console host adapter, document locking, result serialization.
- **ARX:** AcEd/AcAp/AcUi, COM, palettes, editor prompts, GS-device interactions and attended wrappers.

The current checkout is already moving correctly: [`AriadneDbxEntry.cpp`](</D:/dev/99_tools/autocad-sdk-router/src/Ariadne.AcadNativeDbx/AriadneDbxEntry.cpp:112>) owns class initialization and exposes a narrow C ABI to the host module.

Keep that pattern. Avoid passing STL objects or ownership-sensitive C++ objects across DLL boundaries. Export C functions using `AcDbObject*`/`AcDbEntity*`, primitive values and explicit ownership rules. Autodesk recommends separating custom database classes into Object Enablers and warns about `__declspec(dllimport)` header-sharing pitfalls. [ObjectDBX/UI separation guidance](https://help.autodesk.com/cloudhelp/2022/ENU/OARX-DevGuide/files/GUID-CC6F7B70-7133-4F8C-882B-14145EE3E0FE.htm).

For the 57+16 re-tiers, verify with an import audit:

- No `aced*`, AcAp, AcUi, AcPl, COM or editor-only dependency in DBX.
- AcGi `worldDraw` implementations may remain for custom-object display, but must not create or assume an editor GS device.
- Load optional shared DBX dependencies by class/service presence and do not unload a modeler/AcBr module that another component may own.

## GitHub release

Public source-only is the safest default:

- Commit your registry, handlers, tests, schemas and build scripts.
- Require the user to install ObjectARX 2027 separately.
- Resolve the SDK through an environment/property-sheet path, never `C:\ObjectARX 2027`.
- Ignore SDK headers, import libraries, dumps, PDBs, host DLLs and locally licensed fixtures.
- Build on a licensed self-hosted runner. AutoCAD 2027 targets the R26.0/VS2026 VC++ 145 generation. [Autodesk’s 2027 engine notice](https://aps.autodesk.com/blog/end-autocad-2021-engine-new-autocad-2027-engine-released).

A binary release is not categorically prohibited. Autodesk explicitly describes Object Enablers as distributable and the SDK has a `Redistrib-x64` set intended for permitted dependencies. [Object Enabler overview](https://help.autodesk.com/cloudhelp/2022/ENU/OARX-DevGuide/files/GUID-FF60A11B-1169-483C-9A65-85203B3A1440.htm), [SDK directory/redist guidance](https://help.autodesk.com/cloudhelp/2022/ENU/OARX-DevGuide/files/GUID-4A1AEF78-79CE-4352-9BDC-318E594F00AF.htm).

If shipping binaries:

- Package only your ARX/CRX/DBX and explicitly permitted 2027 redistributables.
- Never bundle `acad.exe`, `acdb*.dll`, ASM/modeler DLLs, headers or import libraries unless the 2027 redist/license expressly lists them.
- Require a compatible licensed host.
- Code-sign ARX/CRX/DBX. Autodesk recommends signing these binary types. [Signing guidance](https://help.autodesk.com/cloudhelp/2027/ENU/AutoCAD-Customization/files/GUID-0A93626D-8389-45FC-969B-B86A2F37D691.htm).
- Audit copied Autodesk sample code and every third-party dependency before publishing.

The op-registry and original handler source are ordinarily your source code; calling documented Autodesk APIs is not itself a license problem. The landmines are copied SDK/sample material, redistributed Autodesk binaries, trademarks implying endorsement, and accidentally creating a purported standalone DWG host without a RealDWG license. The governing 2027 terms are published in Autodesk’s [ObjectARX SDK license](https://aps.autodesk.com/developer/overview/autocad-objectarx-sdk-licensing); legal review should decide the final public binary bundle.
