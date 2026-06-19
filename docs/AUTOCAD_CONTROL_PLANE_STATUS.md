# AutoCAD Total-Control Plane — Build & Status Report

> **Question this report answers:** How did the agents (Codex + Claude) plan to build an
> environment in which AI agents can *perfectly **control**, **understand**, and **manipulate**
> all of AutoCAD's data* — and **how far has it actually been built?**
>
> **Scope reviewed:** how the AutoCAD SDKs were built, and every router in the stack.
> **As of:** 2026-06-19. **Router home:** `D:\dev\99_tools\autocad-sdk-router`.
> **Method:** four parallel investigations (router / native ObjectARX-DBX build /
> managed .NET + dispatch / vision + recency), then one synthesis. Ground truth was
> re-probed live (`-Action status`) during this audit.

---

## 0. TL;DR

- **The plan is a single-entrypoint "AutoCAD SDK Router"** that exposes the *entire* AutoCAD /
  ObjectARX SDK surface to agents as an **intent-driven control plane**, with a **native C++
  ObjectARX/ObjectDBX module as the #1 tier** — deliberately *not* managed .NET, not LISP.
- **It is real and partly built.** The router is live (`ALL_AVAILABLE`, 11/11 routes). A
  **compiled native module** (`.dbx` + `.crx` + `.arx`) loads and executes **29 real CAD
  operations** against staged DWGs through `accoreconsole`. A managed .NET engine implements a
  4-op subset (only 1 — `inspect.database.summary` — is actually routed to it; the other 3 are shadowed by the native allow-list). Every one of the 29 wired operations has **at least one successful end-to-end run**.
- **The depth gap is large.** The native capability catalog has **480 operations** (221 of them
  "native-only"). Only **~29 are wired/executable today (~6%)**. The deepest native-only
  capabilities — custom `worldDraw` graphics, OPM properties, lifecycle overrules, interactive
  jigs, persistent reactors, UI/COM — are **catalogued and designed but not yet built** (Phases 3–5).
- **The headless ↔ attended boundary bounds "total control."** RealDWG is excluded by license, so
  all DWG work is hosted *inside* AutoCAD. The **DB / object / CRUD lanes work headless** (via the
  `.crx` CoreConsole module). The **editor / graphics / UI lanes require full attended AutoCAD**
  and are not yet built. "Total headless control of all data" is therefore **not yet true**.
- **Top risk — RESOLVED 2026-06-19:** the router was **outside version control**; it is now a git repo
  (`main` branch). Source/tools/config/schemas/docs/research/tests tracked; bulky regenerable `runs/`,
  `staging/`, `bin/`, `obj/` and CAD binaries ignored.

---

## 1. The Vision — a native-first AutoCAD control plane

The architecture inverts the usual "managed .NET is easiest, start there" instinct. The declared
**priority order** (`config/autocad_official_sdk_catalog.json`) is the spine of the whole design:

| # | Tier | Why this rank |
|---|------|---------------|
| **1** | **`native_objectarx_objectdbx`** | Only native C++ can author **first-class** custom `AcDbEntity`/`AcDbObject` classes (not proxies), object enablers, OPM properties, lifecycle overrules, persistent reactors, and `worldDraw` graphics. Everything else degrades to proxy objects. |
| 2 | `managed_dotnet` | Convenient adapter; used where it is the correct host. |
| 3 | `autolisp_visual_lisp` | Entity-count / scripting fallback. |
| 4 | `core_console` (accoreconsole) | Headless host that actually *runs* the native + managed modules. |
| 5 | `full_autocad_com` | Live attended-document writes via COM `SendCommand` + mailbox. |

**RealDWG is explicitly excluded** (license). Consequence: there is **no zero-host standalone C++
DWG read**; all DWG I/O is hosted *inside* `accoreconsole` (headless) or attended AutoCAD.

**The 18 SDK families** the plan intends to cover (`autocad_official_sdk_catalog.json`):
`runtime_commands, objectdbx_database, symbol_tables_dictionaries, entities, blocks_xrefs_clone,
geometry_kernel, brep_solids, graphics_system, editor_input, reactors_events,
custom_objects_protocols, constraints_associativity, layouts_plot_publish, ui_customization,
com_activex, autolisp_visual_lisp, core_console, active_document_write_original`.

**Research foundation (unusually rigorous):** 10 official-doc research slices under
`research/native_arx/*.md` (~330 KB), a completeness/contradiction audit (`_AUDIT.md`, resolved 3
cross-slice tier contradictions), and a synthesis index (`_SYNTHESIS_INDEX.md`) computing an
**18-family × 4-tier matrix**. It quantifies a **221-op "native-only build set"** (ops with no
managed and no LISP equivalent) — the explicit justification for writing C++ at all.

---

## 2. Architecture at a glance

```
                          ┌─────────────────────────────────────────────┐
   agent intent  ──────▶  │   autocad-router.ps1   (single entrypoint)   │
   (status/select/run)    │   actions: status · select · run · explain   │
                          └───────────────┬─────────────────────────────┘
                                          │ intent → route (81 aliases) + capability fallback
            ┌─────────────────────────────┼─────────────────────────────────────────┐
            ▼                             ▼                                            ▼
   dwg_truth_autocad (pri 10)     10 Python routes (pri 20–50)              (probe / no-fake-success)
   engine = native_first          dxf · ifc · step/brep · parametric ·
            │                      libredwg-sidecar · mesh · pointcloud ·
            │                      geo-vector · pdf/svg · raster
            │
            │  5 DWG engine lanes:
            ├── Invoke-CadJobRoute ──── accoreconsole ──┬── NATIVE  : arxload .dbx + .crx → ARIADNE_NATIVE_JOB   (28-op allow-list)
            │                                           └── MANAGED : NETLOAD .dll       → ARIADNE_CAD_JOB       (1 op: inspect.database.summary)
            ├── Invoke-AutoCadRoute ─── accoreconsole — read/extract (arx→dbx→autolisp chain)
            ├── Invoke-FullAutoCadCadJob ─ acad.exe COM SendCommand + mailbox (live_edit / jig / reactor)
            ├── Invoke-FullAutoCadScript ─ raw .scr to active document over COM
            └── Invoke-DwgWriteOriginalScript ─ caller .scr against the ORIGINAL dwg (script owns SAVE)
```

**Component status:**

| Component | What | State |
|-----------|------|-------|
| `tools\autocad-router.ps1` (1,319 lines) | Single entrypoint, 4 actions, intent-alias + fallback, 5 DWG engine lanes | **WORKING** |
| 11 routes | 1 native DWG route + 10 Python engines | **WORKING** — live `ALL_AVAILABLE`, 11/11 |
| `Ariadne.AcadNativeDbx.dbx` (44.5 KB) | Persistent core: custom classes, filing, protocol | **BUILT + loads headless** |
| `Ariadne.AcadNative.crx` (146 KB) | CoreConsole shell: 29-op job dispatcher, commands | **BUILT + loads + runs headless** |
| `Ariadne.AcadNative.arx` (146 KB) | Full-AutoCAD shell (same TU as .crx) | **BUILT — loads in attended AutoCAD only** |
| `Ariadne.DwgGeometryExtractor.dll` (42.5 KB, net10) | Managed .NET engine: 4 ops implemented (1 routed, 3 shadowed) + geometry extract | **BUILT + runs headless** |
| `autocad_native_arx_operation_catalog.json` (297 KB) | 480-op native capability catalog | **DATA only** — 29 wired |
| `autocad_official_sdk_catalog.json` (6 KB) | 18-family SDK surface inventory | **DATA only** |
| `cad_job.schema.json` | 29-op operation enum + 4 write-modes | **WORKING contract** |

---

## 3. The Router layer

**Single entrypoint:** `tools\autocad-router.ps1`. Actions (`-Action`, ValidateSet):

- **`status`** (default) — live-probes every Python route via `tools\probe_routes.py`, **and** probes
  the native modules (`.dbx`/`.crx`/`.arx` presence + a *real* CoreConsole `arxload` load test), then
  writes `reports\autocad_router_status_latest.json`. (`Get-Status`, `Test-NativeAcadModules`.)
- **`select`** — maps `-Intent`/`-Route` to a route honoring availability + fallback; no execution.
- **`run`** — re-probes, selects, **refuses to fake an unavailable route** (emits `status: UNAVAILABLE`
  and stops), then dispatches.
- **`explain`** — select + full capability dump.

**Intent → route** (`Resolve-IntentToRoute`, `Select-Route`): three-tier resolution — (1) `intent_aliases`
table (81 aliases), (2) literal route-id, (3) each route's `intents` array. Default `auto` →
`dwg_truth_autocad`. **Capability fallback:** if the mapped route's probed `available` is false, it walks
the route's `fallback_to` chain and records `fell_back` / `chain_tried` / reason. An explicit `-Route` is
forced and bypasses fallback.

**The 11 routes** (id / priority / engine / fallback):

| Route | Pri | Engine | Sample intents | Fallback |
|---|---|---|---|---|
| `dwg_truth_autocad` | 10 | **native_objectarx_objectdbx_first** (accoreconsole.exe) | dwg, arx, dbx, write_original, live_autocad, dynamic_block, xdata, layout, xref, plot, jig, reactor, overrule, custom_entity | dxf_fast_secondary, dwg_libredwg_sidecar |
| `dxf_fast_secondary` | 20 | python: ezdxf+shapely | dxf, polyline, 2d_geometry | dwg_truth_autocad |
| `ifc_bim_semantic` | 20 | python: ifcopenshell | ifc, bim, wall, storey, property_set | — |
| `solid_brep_occ` | 30 | python: cadquery+OCP | step, brep, solid, iges, topology | parametric_rebuild |
| `parametric_rebuild` | 40 | python: cadquery (generative) | rebuild, generate, parametric, export_step | — |
| `dwg_libredwg_sidecar` | 50 | cli: libredwg (GPL, sidecar-only) | libredwg, dwg_no_autocad, dwg_crosscheck | dwg_truth_autocad, dxf_fast_secondary |
| `mesh_analysis` | 30 | python: trimesh+meshio+open3d | mesh, stl, watertight, obj, ply | — |
| `pointcloud_route` | 30 | python: open3d+laspy | pointcloud, las, laz, rcs, icp | — |
| `geo_vector_route` | 30 | python: pyogrio(bundled GDAL)+pyproj | geo, shp, geojson, crs, dgn | — |
| `pdf_svg_vector_route` | 30 | python: svgpathtools+svgelements | pdf, svg, vector_path, overlay | — |
| `raster_compare_route` | 30 | python: opencv-headless+skimage | raster, image_compare, ssim, visual_qa | — |

**Live ground truth (re-run during this audit):** `schema: ariadne.autocad_router_status.v2`,
`status: ALL_AVAILABLE`, **route_count 11 / available_count 11 / unavailable []**. The `native_modules`
block: `status: PASS` — all three modules exist (`.dbx` 44,544 B; `.crx` & `.arx` 146,432 B each) and
**`coreconsole_load: PASS`** (a real `arxload` test against a staged blank DWG, `process_hygiene: PASS`,
no leaked `acad.exe`). The UTF-16 mojibake in `stdout_tail` is cosmetic (accoreconsole console encoding).

**Discipline imposed** (`reports\AUTO_CAD_ROUTER_AGENT_CONTRACT.md`, `SDK_ROUTER_USAGE.md`):
1. **Native ARX/DBX first** for DB / graphics / geometry / custom-object work; managed, LISP, COM are adapters.
2. **DWG original writes ARE now allowed** under `write_original` / `live_edit` / active-document intents
   (a deliberate evolution from the older "originals strictly read-only" stance) — otherwise ASCII staging.
3. **ASCII staging** (`staging\dwg_<stamp>\input.dwg`) for batch/copy/path-hygiene jobs.
4. **No fake success** — a route is `available:true` only if every required tool resolves under the live
   probe; a forced-but-unavailable route returns `UNAVAILABLE` and refuses to run.
5. **LibreDWG = GPL → sidecar only** (separate process; never link/import/bundle). Installed 0.13.4.
6. **RealDWG excluded.** Workflow order is mandatory: `status → select → run`.

**Full config surface:** `config\` (4): `autocad_router_capabilities.json` 16.6 KB,
`autocad_native_arx_operation_catalog.json` 297 KB, `autocad_official_sdk_catalog.json` 6 KB,
`cad_job_operation_aliases.json` 14.8 KB (29 wired aliases). `reports\` (5), `schemas\` (2: `cad_job`,
`dwg_geometry_extract`), `docs\` (3 incl. this report's siblings + 2 superpowers plans).

---

## 4. The Native ObjectARX / ObjectDBX SDK build

**Verdict: BUILT and EXERCISED for the headless (`.crx`) + ObjectDBX (`.dbx`) lane. The standalone
`.arx` is BUILT but does not load in headless `accoreconsole` (loads only in full/attended AutoCAD) —
a known, accepted limitation, worked around by shipping a `.crx` instead.**

### 4.1 The three-module design

Three coupled VS projects under `src\`, producing into one shared `bin\x64\Release\`:

| Project | Module | SDK props | Role |
|---|---|---|---|
| `Ariadne.AcadNativeDbx\…dbx.vcxproj` | `.dbx` (44.5 KB) | `rxsdk_Releasecfg.props` + **`dbx.props`** | **Persistent core** — editor-free so it loads host-less / in accoreconsole. Registers the custom classes + protocol. |
| `Ariadne.AcadNative\…crx.vcxproj` | `.crx` (146 KB) | `rxsdk_Releasecfg.props` + **`arx.props`** (+`TargetExt=.crx`, define `ARIADNE_NATIVE_CRX`) | **CoreConsole shell** — the 29-op job dispatcher + commands. **This is the working headless executor.** |
| `Ariadne.AcadNative\…arx.vcxproj` | `.arx` (146 KB) | `rxsdk_Releasecfg.props` + **`arx.props`** | **Full-AutoCAD shell** — byte-identical TU to `.crx`; retained for attended AutoCAD (jig/reactor/UI lanes). |

All three: `DynamicLibrary`, `Release|x64`, **`PlatformToolset=v143`** (VS2022), `/utf-8`, no `.def` file
(`#pragma comment(linker,"/export:acrxGetApiVersion,PRIVATE")`). The `.crx`/`.arx` link the `.dbx`'s
import lib; the entity class (`AriadneProbe.cpp`) is compiled **into the DBX** (persistent core), not the shell.

### 4.2 Custom classes authored (real first-class objects, not proxies)

- **`AriadneProbe : AcDbEntity`** — `ACRX_DXF_DEFINE_MEMBERS(…, ARIADNEPROBE, "AriadneAcadNative1.0…")`.
  Implements the 4 mandatory filers (`dwg/dxfIn/OutFields`), version-`Int16`-first with
  `eMakeMeProxy` forward-compat, and the **protected** `subWorldDraw` (draws a circle), `subGetGeomExtents`,
  `subTransformBy` — correctly avoiding the `ADESK_SEALED` public overrides.
- **`AriadneRecord : AcDbObject`** — the custom dictionary-resident object (created via
  `extend.customobject.create`).
- **`AriadneProbeProtocol`** — a protocol extension (queried by `inspect.protocol.queryx`).
- In-process helpers in the shell TU: `AriadneEditorReactor : AcEditorReactor`,
  `AriadneObjectOverrule : AcDbObjectOverrule`, `AriadneLineJig : AcEdJig`.

**Registration (`acrxEntryPoint`):** the DBX `kInitAppMsg` → `AriadneProbe::rxInit()` +
`AriadneRecord::rxInit()` + `acrxBuildClassHierarchy()` + protocol register; reverse-cleans on unload
(`deleteAcRxClass` after unregister). The shell `kInitAppMsg` → unlock/register MDI-aware → **load the
sibling `.dbx`** (`loadDbxCore()`) → register commands in group `ARIADNE_NATIVE`: `ARIADNE_NATIVE_JOB`
(env/mailbox-driven), `ARIADNE_NATIVE_JOB_ARGS`, `ARIADNE_NATIVE_JOB_MAILBOX`. Clean load/unload confirmed
(`diag_unload_native_direct.txt`: `ARXUNLOAD_OK` + `DBXUNLOAD_OK`).

### 4.3 The arxload mystery — RESOLVED (worked around)

The previous session was blocked because `ARIADNE_NATIVE_JOB` returned "unknown command" and the module
never appeared in the `(arx)` loaded list. The diagnostics tell the full story:

- `diag.txt` / `diag3.txt` (baseline): `ARXLOAD_ERROR` and **`FACT_LOAD: FAILED`** — even **Autodesk's own
  `fact.arx` sample** will not `arxload` into `accoreconsole`. So the failure was **systemic, not our code.**
- `diag_dbx_after_build.txt`: **`DBXLOAD_OK`** — the `.dbx` loads fine headless; the `.arx` still errors.
- `diag_crx_after_build.txt`: **the breakthrough** — rebuilding the *same shell* as a **`.crx`** yields
  **`CRXLOAD_OK`**. This is *why the `.crx` project exists.* `create_crx.scr` / `count_crx.scr` then ran
  `ARIADNE_NATIVE_JOB` for real: `extend.customclass.create` → `{"created":true,"ariadne_probes_after":1}`
  and `inspect.customclass.count` → `{"ariadne_probes":1}`. **The custom entity round-trips headless.**
- `diag_arx_fullacad.txt`: under **full attended AutoCAD** both load (`DBXLOAD_OK` + `ARXLOAD_OK`, both
  listed in `(arx)`).

Diagnostics set `SECURELOAD 0` + add the bin dir to `TRUSTEDPATHS`, so this is **not** a signing/trust
failure — the `.arx` simply will not register in the CoreConsole host. **Resolution is architectural:**
`.crx` for headless, `.arx` for attended AutoCAD, `.dbx` shared persistent core.

### 4.4 The 29-operation native dispatcher

`ariadneNativeJob()` is an `if/else` chain on the JSON `operation` field. I/O: a 4-level path
resolution (command-arg override → file mailbox → `acedGetEnv("ARIADNE_CAD_JOB_IN/_OUT/_HOST_MODE")` →
process env), a **hand-rolled JSON scanner** (no vendored lib yet), an RAII document write-lock, and a
result envelope `{"schema":"ariadne.autocad_native_job_result.v1","engine":"native_objectarx",…,"status":"ok|error"}`.

| Group | Ops |
|---|---|
| Inspect/read (14) | `inspect.database.summary`, `inspect.entity.count`, `inspect.xrecord.get`, `inspect.xdata.get`, `inspect.block.count`, `inspect.layout.list`, `inspect.xref.list`, `inspect.runtime.capabilities`, `inspect.reactor.registry`, `inspect.overrule.registry`, `inspect.jig.host_support`, `inspect.customclass.count`, `inspect.customobject.count`, `inspect.protocol.queryx` |
| Write/CRUD (8) | `write.layer.create`, `write.entity.line`, `write.entity.circle`, `write.xrecord.set`, `write.xdata.set`, `write.block.simple_create`, `write.block.insert`, `write.layout.create` |
| Extend / custom (2) | `extend.customclass.create` (appends an `AriadneProbe`), `extend.customobject.create` (appends an `AriadneRecord`) |
| Live / interactive (5) | `live.reactor.enable/disable`, `live.overrule.enable/disable`, `live.jig.point_probe` — gated on `host == "full_autocad"`; return `supported:false` under CoreConsole |

---

## 5. The managed .NET engine & dispatch pipeline

**One managed project:** `Ariadne.DwgGeometryExtractor` (`net10.0-windows`; refs `acmgd` / `acdbmgd` /
`accoremgd` → AutoCAD 2027, `Private=false`). Built dll: `bin\Release\net10.0-windows\Ariadne.DwgGeometryExtractor.dll`
(42.5 KB, 2026-06-17). Auto-built by the router via `dotnet build -c Release` if missing.

**Commands registered** (`Commands.cs`, `[CommandClass]` + `IExtensionApplication`):
`ARIADNE_DWG_GEOM_EXTRACT` (active-doc geometry), `ARIADNE_DWG_DBX_EXTRACT` (side-DB read),
`ARIADNE_CAD_JOB` (the job runner). The managed `CadJobRunner.Run()` switch implements **exactly 4**
operations: `inspect.database.summary`, `write.layer.create`, `write.entity.line`, `write.xrecord.set`
(default → `NotSupportedException`). Job I/O = JSON file via `ARIADNE_CAD_JOB_IN` → `ARIADNE_CAD_JOB_OUT`;
ops run inside `document.LockDocument()`.

**The two-engine split (the key dispatch finding):** `Invoke-CadJobRoute` branches on an allow-list,
`Test-NativeP1CadJobOperation`:

- **In the allow-list → NATIVE path:** `.scr` does `arxload` of `.dbx` + `.crx`, then runs `ARIADNE_NATIVE_JOB`.
- **Not in the list → MANAGED path:** `.scr` does `NETLOAD` of the `.dll`, then runs `ARIADNE_CAD_JOB`.

The allow-list holds **28 operations** → all routed NATIVE. The **one** remaining schema op,
`inspect.database.summary`, is **not** in the list and is the only op that actually reaches the MANAGED
engine. Both run headless through `accoreconsole` against an ASCII-staged copy of the DWG (original
untouched unless `write_original`, where the router injects `_QSAVE` into the script — the managed dll
only flags `save_requested`, it does not save itself).

> ⚠️ **Shadowed managed implementations (verified 2026-06-19):** the managed `CadJobRunner` implements **4**
> ops, but **3** of them (`write.layer.create`, `write.entity.line`, `write.xrecord.set`) are *also* in the
> 28-op native allow-list, so the router always routes those native. Only `inspect.database.summary` reaches
> managed at runtime. 28 native + 1 managed = the 29-op schema (no count "bug"); the 3 shadowed managed
> write-ops are harmless dead paths and are candidates for removal.

---

## 6. Operation coverage — catalog vs. implemented (the real gap)

| Layer | Count | Status |
|---|---:|---|
| `autocad_native_arx_operation_catalog.json` — total native ops | **480** | Inventory (data only) |
| └ tier `native_arx_only` | 221 | The "must build C++" set |
| └ tier `objectdbx_capable` | 198 | Headless-capable in accoreconsole |
| └ tier `managed_also` | 45 | Doable from .NET |
| └ tier `accoreconsole_lisp_also` | 16 | LISP-reachable |
| `cad_job.schema.json` — exposed operation enum | **29** | Working contract |
| **Wired + executable end-to-end today** | **29** | **Every one has ≥1 successful run** |
| └ routed to managed .NET | 1 | `inspect.database.summary` (the only op not in the native allow-list) |
| └ routed to native ARX/DBX | 28 | the `Test-NativeP1CadJobOperation` allow-list |
| └ (of those 28) managed-implemented but shadowed | 3 | `write.layer.create`, `write.entity.line`, `write.xrecord.set` |

**Evidence of execution (run corpus):** 11 managed `cad_job_result.json` (9 ok / 2 early errors:
`eLockViolation`, `eFilerError`, since fixed) + **434 native `native_cad_job_result.json`**
(engine `native_objectorx`, near-all ok). **All 29 catalogued operations have at least one successful
end-to-end run.** Only two ops are intermittently reliable: `write.block.insert` (≈13 err / 11 ok) and
`write.block.simple_create` (2 err / 21 ok) — partially reliable; the latest stateful batch
(`p2_stateful_batch_result_20260619_135949.json`) shows the block create→insert→count round-trip passing.

**Headline:** **29 of 480 catalogued operations (~6%) are executable today.** Of the 221 *native-only*
ops specifically — the deep capabilities that justified writing C++ — only a handful (custom class/object
create+count, protocol queryX, reactor/overrule registry) are wired; the bulk (custom `worldDraw`
graphics, OPM properties, lifecycle overrules, interactive jigs, live persistent reactors, UI/COM) is
**catalogued and designed, not built.**

---

## 7. Phase roadmap & status (P0 → P5)

From `docs\NATIVE_ARX_DBX_DESIGN.md` §6 and `docs\superpowers\plans\2026-06-19-phase0-to-phase5-…md`:

| Phase | Scope | Status |
|---|---|---|
| **P0** | Evidence/hardening — rebuild, status, smokes, serialized loads | ✅ **DONE** (2026-06-19) |
| **P1** | ObjectDBX/CoreConsole CRUD — DB summary, layers, entities, xrecords, xdata, blocks, layouts, xrefs, write-original | ✅ **largely evidenced** (write_original `QSAVE` persistence still an open checkbox) |
| **P2** | Custom object/enabler/protocol — typed Ariadne entities, `queryX`, filers | 🟡 **partially evidenced** (ops dispatch; full DBX filing/version + enabler-load round-trip not fully closed) |
| **P3** | ARX OPM / `AcRxProperty` / lifecycle overrules / `subWorldDraw` graphics | ⬜ **mostly planned** |
| **P4** | Full-AutoCAD jig + reactor lane (`AcEdJig`, `acedGetPoint`, persistent reactors) | ⬜ **probe-level only** (host-support checks pass; live loop unbuilt) |
| **P5** | UI/COM last — palettes, status bar, CUI, ActiveX | ⬜ **deferred** |

**6 hard constraints honored** (from the design doc): (1) `acedCommand/Cmd` are compile-disabled in 2027
→ use `…S`/`…C` variants; (2) public draw/transform are sealed → override protected `subXxx`; (3) no
zero-host C++ DWG read (ship into accoreconsole, never standalone = RealDWG); (4) filing version-Int16-first
+ `eMakeMeProxy`; (5) module unload must reverse-clean; (6) `SECURELOAD` → `TRUSTEDPATHS`.

---

## 8. What "total control of all AutoCAD data" means *today*

| Capability lane | Headless (accoreconsole, `.crx`+`.dbx`) | Attended (full AutoCAD, `.arx` / COM) |
|---|---|---|
| Read DB (tables, dicts, modelspace, blocks, layouts, xrefs) | ✅ working | ✅ working |
| Write CRUD (layers, lines, circles, xrecords, xdata, blocks) | ✅ working | ✅ working |
| Custom first-class objects (`AcDbEntity`/`AcDbObject`, protocol) | ✅ create/count working; full filing round-trip 🟡 | ✅ |
| Write to **original** DWG (`write_original` / `live_edit`) | 🟡 script-`QSAVE` path, persistence not fully confirmed | ✅ COM SendCommand lane exists |
| Custom **graphics** (`worldDraw`), OPM properties | ⬜ not built (P3) | ⬜ not built (P3) |
| Interactive **jigs**, point input, live **persistent reactors** | ⛔ host-gated (returns `supported:false`) | ⬜ probe-only, lane unbuilt (P4) |
| UI: palettes / status bar / CUI / ActiveX | ⬜ not built (P5) | ⬜ not built (P5) |

**Boundary statement:** the system gives agents **strong headless control over the *data/object* model**
(the DB, entities, custom objects, CRUD) and a working *path* to attended live editing — but the **editor,
graphics, and UI lanes are not yet built**, and RealDWG-free standalone access is out of scope by license.
So "perfectly control, understand, and manipulate **all** AutoCAD data" is **achieved for the database/object
tier headless**, and **planned-but-unbuilt for the interactive editor/graphics/UI tier.**

---

## 9. Risks & honesty flags

1. **🟢 Version control — ESTABLISHED 2026-06-19.** `D:\dev\99_tools\autocad-sdk-router` is now a git repo
   (`main` branch). Tracked: `src\` (C++/C# source + `.vcxproj`/`.csproj`), `tools\`, `config\`, `schemas\`,
   `docs\`, `research\`, `tests\`, top-level `*.md`. Ignored (bulky/regenerable): `runs\` (~1.3 GB), `staging\`
   (~743 MB), `bin\`/`obj\` build outputs, `*.pdb`, `*.dwg`/`*.dxf`, caches, secrets. Native binaries
   regenerate from source via `tools\build_native_acad.ps1`.
2. **🟡 `.arx` is dead weight for the headless router** — only `.crx`+`.dbx` work in accoreconsole. The `.arx`
   is retained for attended AutoCAD and was last load-verified on 2026-06-18, **not** re-verified after
   today's 14:02 rebuild (no reason to expect it changed, but unverified).
3. **🟢 Doc drift — CORRECTED 2026-06-19.** `NATIVE_ARX_DBX_DESIGN.md` previously said toolset **v145/VS2026**
   (actual: **v143/VS2022**) and **"480 (18 families)"** (the native catalog's `by_family` has **16**; 18 is
   the SDK taxonomy, of which `autolisp_visual_lisp` + `core_console` carry 0 native ops). Both lines are
   now fixed in the design doc.
4. **🟡 Hand-rolled JSON parsing** in the native dispatcher (no vendored lib) — brittle on non-trivial payloads.
5. **🟢 Allow-list "mismatch" — RESOLVED (not a bug).** 28-op native allow-list + 1 managed op
   (`inspect.database.summary`) = 29 schema ops; the managed runner's 3 extra write-ops are shadowed dead
   paths (see §5).
6. **🟡 `write_original` persistence** relies on a router-injected `_QSAVE` in the `.scr`, not the engine —
   a P1 open checkbox, not yet confirmed end-to-end.
7. **🟢 Intermittent ops:** `write.block.insert` / `write.block.simple_create` are only partially reliable.

---

## 10. Recent build timeline (from mtimes + plan dates)

- **2026-06-16** — Router localized/rebuilt locally (Drive mirror abandoned); Python route engine
  (`run_route.py`, `probe_routes.py`), LibreDWG sidecar.
- **2026-06-17** — Managed .NET path: `Ariadne.DwgGeometryExtractor` (`GeometryExtractor.cs`, `CadJobRunner.cs`,
  built to `net10.0-windows`); geometry-extract schema.
- **2026-06-18** — **Native C++ module born.** `AriadneProbe.{h,cpp}` → DBX core
  (`AriadneRecord`, `AriadneProtocol`, `AriadneDbxEntry`) → first `.dbx` built; `.crx`/`.arx` vcxproj added;
  P2 batch 26/27, P5 host-split 10/10.
- **2026-06-19 ~04–05h** — `tools\build_native_acad.ps1`; full rebuild of `.arx`/`.crx`/`.dbx`; schema +
  aliases bumped to the 29-op surface; new ops `write.entity.circle`, `inspect.entity.count`.
- **2026-06-19 ~14h** — **P2 gap closed** (block create→insert→count PASS); full-AutoCAD jig/overrule read
  probes; repeated `native_status_*` runs regenerating live status (`ALL_AVAILABLE`, native PASS).

---

## 11. Evidence appendix (key files)

**Router:** `tools\autocad-router.ps1` (actions, fallback, 5 engine lanes, native module resolution, P1
allow-list); `config\autocad_router_capabilities.json` (11 routes, 81 aliases);
`reports\autocad_router_status_latest.json` (live ALL_AVAILABLE 11/11, native PASS);
`reports\AUTO_CAD_ROUTER_AGENT_CONTRACT.md`, `SDK_ROUTER_USAGE.md`, `README.md`.

**Native build:** `src\Ariadne.AcadNative\AriadneNativeJob.cpp` (1,949 lines, 29-op dispatch, `acrxEntryPoint`);
`src\Ariadne.AcadNative\AriadneProbe.{h,cpp}` (custom `AcDbEntity`);
`src\Ariadne.AcadNativeDbx\{AriadneDbxEntry.cpp, AriadneRecord.cpp, AriadneProtocol.cpp, AriadneDbxApi.h}`
(DBX core); `…\*.arx.vcxproj` / `*.crx.vcxproj` / `*.dbx.vcxproj` (all v143, x64 Release);
`bin\x64\Release\{*.arx, *.crx, *.dbx}` (built modules);
`test_native\diag_arx_after_build.txt` (ARX headless fail), `diag_crx_after_build.txt` (CRX OK),
`diag_arx_fullacad.txt` (both load attended), `diag.txt`/`diag3.txt` (FACT_LOAD FAILED baseline),
`native_create_result.json` / `native_count_result.json` (proof of headless native run);
`tools\build_native_acad.ps1` (MSBuild driver).

**Managed + dispatch:** `src\Ariadne.DwgGeometryExtractor\{Ariadne.DwgGeometryExtractor.csproj, CadJobRunner.cs,
Commands.cs, CadJobDtos.cs, GeometryExtractor.cs, JsonWriter.cs}`; `schemas\cad_job.schema.json` (29-op enum,
4 write-modes); `bin\Release\net10.0-windows\Ariadne.DwgGeometryExtractor.dll`.

**Vision + catalogs:** `config\autocad_official_sdk_catalog.json` (priority_order, 18 families);
`config\autocad_native_arx_operation_catalog.json` (480 ops, 4 tiers, 16 families);
`config\cad_job_operation_aliases.json` (29 wired); `docs\NATIVE_ARX_DBX_DESIGN.md` (thesis, phases, 6
constraints); `research\native_arx\` (10 slices + `_AUDIT.md` + `_SYNTHESIS_INDEX.md`, 221-op native-only set);
`docs\superpowers\plans\2026-06-19-phase0-to-phase5-autocad-native-build.md`,
`docs\superpowers\plans\2026-06-18-p2-native-cad-job-ops.md`.

**Run evidence:** `runs\p2_stateful_batch_result_20260619_135949.json` (block round-trip PASS),
`runs\phase1_entity_batch_result_20260619_140223.json`, `runs\p5_batch_check_20260618_185444.json` (10/10),
`runs\p2_batch_check_20260618_183246.json` (26/27); plus 434 `native_cad_job_result.json` + 11
`cad_job_result.json` across `runs\`.

---

*Report generated 2026-06-19 by a 4-way parallel audit (router · native build · managed/dispatch · vision/recency), synthesized into one document. Ground truth re-probed live during the audit.*
