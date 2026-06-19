# NATIVE_ARX_DBX_DESIGN.md — Native ObjectARX / ObjectDBX Controller Module

> **Status: NATIVE P1/P2 IMPLEMENTATION EXISTS / STATEFUL P2 GAP CLOSED (2026-06-19).**
> The native `.dbx` + `.crx` job lane is integrated with the router, schema, tests, and
> `ARIADNE_NATIVE_JOB` dispatcher. Current evidence includes P1 custom class/object/protocol
> operations, P2 Core Console CRUD/host-capability operations, the P2 Batch 5
> overrule/jig host split, and a fresh serialized stateful block batch. The older
> aggregate artifact `runs/p2_batch_check_20260618_183246.json` remains **26/27** and is
> retained as historical evidence; `runs/p2_stateful_batch_result_20260619_135949.json`
> closes the block create/insert/count gap.
> **Provenance:** grounded entirely in 10 official-doc research slices
> (`research/native_arx/*.md`), the completeness audit (`research/native_arx/_AUDIT.md`),
> and the unified operation catalog (`config/autocad_native_arx_operation_catalog.json`,
> **480 ops**, validated parse). No capability below is asserted without a cited slice/op.

**Implementation checkpoint (2026-06-19 evidence sync):**
- DBX core: `src/Ariadne.AcadNativeDbx/Ariadne.AcadNativeDbx.dbx.vcxproj`
  -> `Ariadne.AcadNativeDbx.dbx`.
- Headless command shell: `src/Ariadne.AcadNative/Ariadne.AcadNative.crx.vcxproj`
  -> `Ariadne.AcadNative.crx`.
- Attended AutoCAD shell: `src/Ariadne.AcadNative/Ariadne.AcadNative.arx.vcxproj`
  -> `Ariadne.AcadNative.arx`.
- Verified native route: `.dbx` loads; `.crx` loads; `ARIADNE_NATIVE_JOB` exposes the
  current 29-operation schema/router set for Core Console and full AutoCAD host modes.
- Verified P1/P2 operation surface exists in `schemas/cad_job.schema.json`,
  `tools/autocad-router.ps1`, `src/Ariadne.AcadNative/AriadneNativeJob.cpp`, and contract
  tests. The native session command now takes a document write lock before write-open work.
- Verified stateful P2 block sequence: `runs/p2_stateful_batch_result_20260619_135949.json`
  creates a block, inserts it, and confirms `target_found=true` on one staged DWG.
- Added Phase 1 Core Console CRUD ops: `write.entity.circle` and `inspect.entity.count`,
  verified by `runs/phase1_entity_batch_result_20260619_140223.json`.
- Verified P2 Batch 5 host split: `runs/p5_batch_check_20260618_185444.json` reports
  10/10 PASS across Core Console and full AutoCAD for overrule registry, overrule
  enable/disable, jig host support, and jig point probe.
  Current full AutoCAD read probes also pass:
  `runs/full_autocad_jig_host_support_probe_20260619_140323.json` and
  `runs/full_autocad_overrule_registry_probe_20260619_140336.json`.
  Direct `.arx` load in Core Console still fails; this matches the earlier official
  `fact.arx` failure and is treated as attended-AutoCAD shell behavior until proven otherwise.

---

## 0. One-paragraph thesis

The managed .NET plane we already run (`CadJobRunner`, 4 ops live) is the right owner of
**bulk DWG CRUD** — entities, symbol tables, dictionaries, geometry read. It cannot, by
construction, do the **221 `native_arx_only` operations** the research surfaced: defining
new persistent classes (custom entities/objects), object enablers, persistent reactors,
protocol extension / `queryX`, the `AcRxProperty`/OPM metamodel, `worldDraw` custom
rendering, interactive jigs, and the long-transaction/linker reactors. Those exist **only**
if we build a native C++ ObjectARX/ObjectDBX module. This design adds that module as the
**priority-1 engine** under the existing router, mirroring the managed job-control plane so
agents drive it with the same `verb.noun.detail` JSON contract.

---

## 1. Capability map (the "why", from the catalog)

| metric | value |
|---|---|
| total operations cataloged | **480** (16 of 18 SDK families populated; `autolisp_visual_lisp` + `core_console` carry 0 native ops; 0 unmapped, 0 id-collisions) |
| `native_arx_only` (the build target) | **221** |
| `objectdbx_capable` (managed/DBX already reaches, host-less in accoreconsole) | **198** |
| `managed_also` (already reachable in managed plane) | **45** |
| `accoreconsole_lisp_also` (headless via `.scr`/LISP) | **16** |
| live in managed `CadJobRunner` today | 4 |

**Native-only value concentrates in the top clusters** (see catalog + `_SYNTHESIS_INDEX.md`):
custom entities/DBObjects 40 · UI palettes/menus 36 · runtime/command/module-load 22 ·
COM+OPM glue 21 · constraints/associativity 19 · OPM/AcRxProperty 17 · AcGe kernel 16 ·
interactive editor/jig 13 · BRep subentity 8 · persistent/low-level reactors 8 ·
custom graphics/worldDraw 7 · protocol-extension/queryX 2 · object enablers 2 ·
lifecycle overrules 2.

**Engineering line we will NOT cross:** the 198 `objectdbx_capable` CRUD ops and the 45
`managed_also` ops stay owned by the managed plane. Building them in C++ is wasted effort
(audit + synthesis ruling). The native module is *additive*, targeting the 221.

---

## 2. Module architecture

### 2.1 Two native modules — `.dbx` core + `.arx` shell

Per the custom-objects slice (verified `dbxEntryPoint.h`): split the persistent core from the
interactive shell.

**2026-06-18 implementation correction:** the persistent core is built as
`Ariadne.AcadNativeDbx.dbx`. The Core Console command shell is built as
`Ariadne.AcadNative.crx`; direct `.arx` load in Core Console failed, while the same shell built
as `.crx` loaded and executed `ARIADNE_NATIVE_JOB`. Keep `Ariadne.AcadNative.arx` as the
attended AutoCAD shell until a full AutoCAD smoke proves otherwise.

- **`Ariadne.AcadNative.dbx` (ObjectDBX, host-less).** Contains *only* class registration,
  filing (`dwg/dxfIn/OutFields`), `subWorldDraw`, clone, versioning, persistent-reactor
  attach, `AcRxProperty`/OPM definitions. **No editor/command/UI dependency** → loads in any
  RealDWG host **and inside `accoreconsole`**. This is also the **object enabler**: it makes
  Ariadne custom objects first-class (drawable/selectable/round-trippable) instead of proxies,
  in any consumer. Base class `AcRxDbxApp`; classes auto-registered via
  `ACDB_REGISTER_OBJECT_ENTRY_AUTO` into the `DBXCUSTOBJ$` linker section.
- **`Ariadne.AcadNative.arx` (ObjectARX, host).** The interactive/UI half: command
  registration, jigs, palettes, OPM dialog glue, COM bridging. Depends on the AutoCAD editor;
  loads into attended AutoCAD (or accoreconsole for the non-UI commands). Links the `.dbx` for
  the shared custom classes.

> **Decision rationale:** keeping the persistent core editor-free is exactly what guarantees
> host-less + accoreconsole operability — the property Paul wants for headless agent control.

### 2.2 Native job-control plane (mirror of `CadJobRunner`)

The managed plane already defines the contract: a JSON job `{operation, write_mode, save,
args}` (schema `cad_job.schema.json`) dispatched by a `switch(operation)` returning JSON.
We replicate it natively:

- A C++ `AriadneNativeJobRunner` reads a job JSON file (path via env, mirroring the existing
  `ARIADNE_CAD_JOB_IN`/`_OUT` pattern in `Commands.cs`), dispatches by `op_id` against the
  catalog, writes a JSON result. Same `verb.noun.detail` ids as the unified catalog.
- Exposed as a registered command **`ARIADNE_NATIVE_JOB`** via
  `acedRegCmds->addCommand(group, "ARIADNE_NATIVE_JOB", localName, ACRX_CMD_SESSION|ACRX_CMD_MODAL, fn)`
  — the native mirror of the managed `[CommandMethod("ARIADNE_CAD_JOB", Session)]`.
  `ACRX_CMD_SESSION` is the session-vs-document execution-context lever (arx-framework slice).
- The router invokes it the same way it invokes the managed extractor: load module → run
  command → read JSON out. Native module loaded into accoreconsole (headless) or attended
  AutoCAD.

### 2.3 Custom-class wiring (the P1 core)

For each Ariadne custom entity/object (research: custom-objects slice, header-verified):
1. Header: `ACRX_DECLARE_MEMBERS(AriadneFoo)`.
2. `.cpp`: `ACRX_DXF_DEFINE_MEMBERS(AriadneFoo, AcDbEntity, AcDb::kDHL_CURRENT,
   AcDb::kMReleaseCurrent, 0, "ARIADNEFOO", "ARIADNE")` + `ACDB_REGISTER_OBJECT_ENTRY_AUTO(AriadneFoo)`.
3. Override the **protected `subXxx`** virtuals (public `worldDraw`/`transformBy`/etc. are
   `ADESK_SEALED` — entities + editor-delta slices both confirm): `subWorldDraw`,
   `subGetGeomExtents`, `subTransformBy`, the 4 filers, plus grips/osnap/explode as needed.
4. Filing must write a version `Int16` first and return `Acad::eMakeMeProxy` on newer-than-known
   (forward-compat / proxy round-trip).

### 2.4 Loading & execution contexts

| context | how | reaches |
|---|---|---|
| attended AutoCAD | `ARX`/demand-load the `.arx` (+`.dbx`) | all 221 native ops incl. UI/jig |
| `accoreconsole` (headless) | load `.dbx` + `.crx` in the `.scr`, run `ARIADNE_NATIVE_JOB` | non-UI native ops + all objectdbx ops, host-less side DB |
| any RealDWG consumer | the `.dbx` object-enabler (demand-load registry) | custom objects render as real, not proxies |

Demand-load registry (object enabler): `HKLM\SOFTWARE\Autodesk\ObjectDBX\R<ver>\Applications\Ariadne`
with `DESCRIPTION`/`LOADCTRLS`/`LOADER` (custom-objects slice). Prefer MSI/installer registration.

### 2.5 Router integration

- Register the native module as the **priority-1 engine** for `dwg_truth_autocad` in
  `config/autocad_router_capabilities.json` (the existing `priority_order` already lists
  `native_objectarx_objectdbx` first). The router gains a native job lane above the managed
  extractor; managed remains the fallback and the owner of bulk CRUD.
- Extend `schemas/cad_job.schema.json` `operation` enum from the current 4 toward the catalog
  (phased — see §6; do **not** dump all 480 into the enum at once).

---

## 3. Build toolchain (confirmed on this machine)

- **Compiler:** C++ toolset **v143** (VS 2022), x64 only. Recompile-per-release (AutoCAD 2027 ⇒
  ObjectARX 2027 SDK ⇒ .NET 10.0 pairing; arx-framework + entities slices, GUID-D54B0935).
- **Includes:** `C:\ObjectARX 2027\inc` + `C:\ObjectARX 2027\inc-x64`. SDK MSBuild property
  sheets present: `dbx.props`, `rxsdk_common.props`, `rxsdk_debugcfg.props`.
- **Libs** (`C:\ObjectARX 2027\lib-x64`, audit-confirmed present): `acdb26.lib`, `accore.lib`,
  `acge26.lib`, `rxapi.lib`, `acdbmgd.lib`, **`AcDrawBridge.lib`** (needed for the AcBr BRep
  topology ops). Exact per-op lib mapping to be finalized at implementation against the SDK
  `samples` project files.
- **Reference at implementation time:** `C:\ObjectARX 2027\docs\arxref.chm` (Reference Guide)
  + `arxdev.chm` (Developer's Guide) — confirmed on disk; the authoritative source for exact
  overload signatures the header scan truncated.
- **Output:** `.dbx`, `.crx`, and `.arx` (renamed DLLs). Place under a TRUSTEDPATHS dir (SECURELOAD).

---

## 4. Hard constraints (must obey — from research, non-negotiable)

1. **`acedCommand`/`acedCmd` are COMPILE-DISABLED in 2027** (`acedads.h:70-71`). Use
   `acedCommandS`/`acedCmdS` (full command) or `acedCommandC`/`acedCmdC` (coroutine). — editor-delta.
2. **Public `worldDraw`/`viewportDraw`/`transformBy`/`getGeomExtents`/… are `ADESK_SEALED`.**
   Override the **protected `subXxx`** virtuals only. — entities + editor-delta + custom-objects.
3. **No zero-host C++ DWG read.** Host-less requires an `AcDbHostApplicationServices` subclass
   (`acdbSetHostApplicationServices`); **`accoreconsole` supplies it**. A standalone no-AutoCAD
   exe linking the libs = **RealDWG = license-EXCLUDED**. → ship the module **into accoreconsole**,
   never as a standalone exe. (audit ruling 1; acdb-core host-less verdict.)
4. **Custom-object filing:** version `Int16` first, `eMakeMeProxy` on newer; for built-in-derived
   classes use `getObjectSaveVersion()` not `filer->dwgVersion()`. — custom-objects.
5. **Module unload must reverse-clean** (delX before deleteAcRxClass; remove reactors/overrules)
   to avoid orphaned class descriptors. — custom-objects + reactors-overrules.
6. **SECURELOAD=1|2** → module dir in `TRUSTEDPATHS`. — arx-framework.

---

## 5. Tier rulings already baked into the catalog (so the build trusts it)

- **Host-less side-DB DWG I/O = `objectdbx_capable` (in accoreconsole)**, not native-only.
- **Overrules per-op:** entity-level/base = `managed_also`; `queryX`/object-lifecycle/
  custom-authoring/dimstyle = `native_arx_only`.
- **Reactors:** persistent = `native_arx_only`; mainstream transient = `managed_also`;
  long-transaction/linker/`AcRxEvent` = `native_arx_only`.

These resolved the only 3 cross-slice contradictions; 30 op rows were tier-overridden accordingly.

---

## 6. Continuation build plan (Phase 0 -> Phase 5)

| phase | clusters (ops) | what it delivers | key APIs |
|---|---|---|---|
| **Phase 0** | Evidence/hardening | Produce clean current evidence before widening the surface: rebuild, status, pytest, serialized Core Console/full AutoCAD smokes, and a fresh stateful P2 batch that replaces the stale 26/27 artifact. | DONE 2026-06-19: router status, pytest, `tools/build_native_acad.ps1`, `runs/p2_stateful_batch_result_20260619_135949.json` |
| **Phase 1** | ObjectDBX/CoreConsole CRUD | Stabilize the headless DB lane: database summary, layers, entities, xrecords, xdata, blocks, layouts, xrefs, and write-original persistence from Core Console. | `AcDbDatabase`, symbol tables, NOD/xrecords, xdata, block/layout APIs |
| **Phase 2** | Custom object/enabler/protocol | Harden typed Ariadne custom entities/objects, DBX object-enabler behavior, filing, count/inspect ops, and protocol-extension/queryX behavior. | `ACRX_DXF_DEFINE_MEMBERS`, `dwg/dxfIn/OutFields`, `AcRxDbxApp`, `queryX/addX` |
| **Phase 3** | ARX OPM/overrule/worldDraw | Make typed objects useful in-session: OPM/`AcRxProperty`, lifecycle overrules, and custom graphics via protected `subWorldDraw`. | `AcRxProperty`/`AcRxAttribute`, `AcDbObjectOverrule`, `subWorldDraw` |
| **Phase 4** | Full AutoCAD jig/reactor lane | Keep interactive editor work explicit and host-bound: full AutoCAD runner, jig point probes, transient/persistent reactor behavior, and honest Core Console unsupported contracts. | `AcEdJig`, `acedGetPoint`, `addPersistentReactor`, full AutoCAD COM runner |
| **Phase 5** | UI/COM glue last | Add palettes, status-bar/menu/CUI surfaces, COM/ActiveX bridges, and UI automation glue only after the DB/object/graphics/editor lanes have clean evidence. | `AcTcUi*`, `AcStatusBar`, `axlock.h`, `axobjref.h` |

- **Geometry-kernel-native (16 AcGe ops)** and **BRep-subentity (8 ops)** ride along inside
  Phase 1/Phase 2 where a consumer needs them, not as standalone phases.
- **Current evidence milestone:** P1/P2 implementation exists, P2 Batch 5 overrule/jig
  evidence exists, and the stateful block gap is closed by
  `runs/p2_stateful_batch_result_20260619_135949.json`.

---

## 7. Non-goals for the C++ module (stay managed / headless)

- 198 `objectdbx_capable` bulk CRUD (entities 56, brep-read 44, constraints-read 39, db 17,
  symtab 15, geometry-read 9, …) → managed `CadJobRunner` keeps owning these.
- 45 `managed_also` (transient reactors, base/entity overrules, plot, basic palette) → managed.
- 16 `accoreconsole_lisp_also` (prompt/select primitives, command invoke, demand-register) →
  wire through the existing accoreconsole `.scr`/LISP route, not C++.

---

## 8. Open decisions for Paul (current)

1. **RealDWG boundary — confirm.** The module ships as **`.arx`/`.dbx` loaded into accoreconsole
   / attended AutoCAD**, never as a standalone RealDWG exe (license). All DWG I/O is
   `objectdbx_capable` hosted in accoreconsole. ✅ proceed on this basis?
2. **P2 closeout evidence.** Keep `runs/p2_stateful_batch_result_20260619_135949.json`
   as the current clean stateful closeout artifact. The old aggregate artifact remains
   26/27 historical evidence.
3. **OPM/AcRxProperty depth.** Decide whether Phase 3 should stop at inspectable property
   metadata or include full Properties palette editing behavior before Phase 4.
4. **Module identity / deployment.** Name (`Ariadne.AcadNative.{arx,dbx}`?), TRUSTEDPATHS dir,
   demand-load registration (installer vs manual). 
5. **UI/COM deferral.** Keep UI/COM glue as Phase 5 unless a specific downstream workflow needs
   it earlier.

---

## 9. Artifacts

- Research (10 slices): `research/native_arx/{arx-framework, acdb-core, entities-geometry-graphics,
  custom-objects, reactors-overrules, editor-delta, constraints-associativity, brep-topology,
  ui-customization, com-activex-opm}.md`
- Audit: `research/native_arx/_AUDIT.md`
- Unified op catalog (480 ops): `config/autocad_native_arx_operation_catalog.json`
- Executive index: `research/native_arx/_SYNTHESIS_INDEX.md`
- P2 incomplete aggregate artifact: `runs/p2_batch_check_20260618_183246.json` (26/27;
  `write.block.insert` failed)
- P2 stateful closeout artifact: `runs/p2_stateful_batch_result_20260619_135949.json`
- Phase 1 entity CRUD artifact: `runs/phase1_entity_batch_result_20260619_140223.json`
- P2 Batch 5 overrule/jig artifact: `runs/p5_batch_check_20260618_185444.json` (10/10 PASS)
- This design: `docs/NATIVE_ARX_DBX_DESIGN.md`
