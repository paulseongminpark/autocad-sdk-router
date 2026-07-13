Repo structure and all file targets confirmed on disk. The 16 family `.inc` files match Finding 2 exactly (m08c–m08n + 3×w6 + 2×w7; m08f is a 1 KB stub = 0 ops), both `.crx`/`.arx` vcxproj present, and the `.dbx` module (`Ariadne.AcadNativeDbx`) is a separate thin codebase that does **not** currently share the family `.inc` handlers — a load-bearing fact for the build plan. All key config/tool/schema files present. I have what I need to synthesize.

Below is the dossier (my final output — returned verbatim, not written to a file).

---

# PHASE-0 DOSSIER — Full ObjectARX 2027 SDK Surface Across `.crx` / `.arx` / `.dbx`

**Repo:** `D:\dev\99_tools\autocad-sdk-router` · **SDK:** `C:\ObjectARX 2027` (630 headers in `inc\`) · **Date:** 2026-07-13
**Mandate (Paul):** find and build ALL functionality the SDK provides, verify integrity, upload to GitHub.

## Provenance & integrity note (read first)

This dossier synthesizes **3 of 5** delivered research findings plus the session GROUND FACTS, and I verified the build-plan file targets exist on disk (16 family `.inc` files, both vcxproj, `.dbx` module, all cited config/tool/schema files — confirmed this session).

- **Finding 2 (Wiring ground-truth)** — delivered, cross-verified with file:line. Primary source for §1.
- **Finding 3 (Gap matrix JSON)** — delivered, per-family numbers. Primary source for §3.
- **Finding 5 (Host boundary)** — delivered, SDK-doc-confirmed. Primary source for §2 module targeting and §4/§6.
- **Finding 1 (SDK Surface)** — **NOT DELIVERED.** §2 is reconstructed from Finding 5's SDK-service map + the registry family catalog + header directory facts. A full header-by-header SDK census (the intended Finding 1) is itself an open Phase-0 work-unit (§4, WU-0).
- **Finding 4 (Build Playbook)** — **NOT DELIVERED.** §5's validation protocol is reconstructed from Finding 2's explicit "runtime frontier" statement + this repo's CADOS invariants. Flagged as reconstructed, not authoritative; a validation-protocol spec is an open work-unit (§4, WU-0).

Status vocabulary is used strictly (`PASS`/`PARTIAL_PASS`/`PASS_WITH_DEFERRAL`/`BLOCKED`). No number below is asserted without the artifact that produced it.

---

## 1. CURRENT STATE — the 489-vs-37 discrepancy, RESOLVED

**Verdict: `PASS` (evidence-cited). The "37" is a stale re-tally, not an honest audit. Native handler coverage is effectively complete; the real open item is runtime proof, not missing code.**

### 1.1 The two numbers measure the same field at two timestamps

| Artifact | mtime | Schema | Records | `implemented` | Meaning |
|---|---|---|---|---|---|
| `config\operations.v2.json` (SoT) | **2026-07-11** | `ariadne.operations_registry.v2` | **551** | **489** (+62 blocked, 0 catalogued, 0 stub) | current |
| `reports\registry_coverage_latest.json` | **2026-06-22** | `ariadne.cadctl.registry_coverage.v1` | 517 | **37** (wired_native=28) | **stale, superseded** |

Both numbers are `count(status=="implemented")` over the registry. The coverage report's generator merely **re-counts the registry's own `status` field** (`registry_coverage_latest.json:96-101`) — it performs **no independent handler verification**. Its "37" is the count on 2026-06-22 against a 517-record registry that predated the bulk of the `m08*` family handlers. It is not "honest 37 vs inflated 489"; it is "old 37 vs current 489."

### 1.2 What the native `.crx` gate actually wires (method + evidence)

The single admission gate is `ariadneNativeJob()`:
- `src\Ariadne.AcadNative\AriadneNativeJob.cpp:6217` — `if (findAriadneNativeOp(op)==nullptr && !familyHasOp(op))` → emits `OPERATION_NOT_IMPLEMENTED`.
- `findAriadneNativeOp` scans `kAriadneNativeOperationTable[]` (`:6052`) = **45** op strings.
- `familyHasOp` (`:6163-6174`) ORs **16** family gates (`m08c/d/e/f/g/h/k/kc/l/m/n` + `w6LayerState`/`w6dynblk`/`w6section` + `materialsRead`/`annoscaleRead`).

Parsing each family's `HasOp` body (same regex shape the repo's own `tools\reconcile_native_registry.py` and `tests\unit\test_m08b_dispatcher_table.py` use) and unioning with the table yields **478 native op strings**:

- **472** are registry ids, all `status=implemented`.
- **6** are native-only diagnostics not in the registry (`extend.deep_native.firing_selftest`, `inspect.deep_native.firing_report`, `inspect.probe.property_count`, `inspect.selection.monitor.registry`, `live.selection.monitor.enable/disable`).
- **0** `blocked` ops leak into the gate (clean).

Handlers are **real AcDb/AcGe/AcBr work, not echo** — cross-confirmed: `write.layer.create→upsertLayerRecord` (`:6305`), `write.dimstyle.create` (~180 lines DIMVAR mapping, `:6315-6500`), `symbolTableRecordsJson` iterating `AcDbSymbolTable` (`:2564`); family handler `families\m08d_handlers.inc` does `acdbOpenObject`/`AcDbEntity` reads (`:93-102`), AcGe types, and AcBr BRep traversers linked via `#pragma comment(lib, acbr26.lib/acgex26.lib/acgeoment.lib)` from `C:\ObjectARX 2027\utils\brep\inc\` (`:50-84`).

### 1.3 The reconciliation

- **472** implemented ops have a real native `.crx` handler.
- **17** implemented ops are **managed/router-plane by design** (`anchor.set/get/list/clear`, `patch.dry_run`, `patch.apply_staged`, `apply.patch`, `diff.before_after`, `validate.ir`, `validate.patch`, `query.entities`, `render.layout`, `run.corpus.batch`, `verify.cross_engine.dwg`, `live.status`, `inspect.entity.identity_contract`, `inspect.xdata.semantic_anchor`) — cross-engine/orchestration ops that live in `tools\run_route.py` DISPATCH and `src\Ariadne.DwgGeometryExtractor\CadJobRunner.cs`, not in a single `.crx` job.
- **472 + 17 = 489.** Exact reconciliation. All 489 carry non-empty `evidence_refs`, `tests`, `handler`, `handler.dispatcher_symbol` (Finding 2 measured 489/489 for each).

**Minor cross-finding discrepancy (surfaced, not averaged):** Finding 3's independent scan counted **474** native registry-id branches (473 implemented + `live.apply_patch`, which is registry-`blocked` but has a branch) vs Finding 2's **472** implemented. The ~2-op delta is the blocked-but-branched `live.apply_patch` plus one boundary op. Both agree on the headline: ~472–474 native-wired, ~17 router, = 489 implemented; the 37 is stale.

### 1.4 The honest caveat — what "implemented" does and does NOT mean

`reconcile_native_registry.py:150` records closing evidence as `runtime_native_job_smoke:deferred_attended`. So **`implemented` = statically wired + built (`.crx`/`.arx` exit 0) + per-family unit test — NOT a live `accoreconsole` per-op job-smoke.** The CADOS invariant ("`available:true` only from a live probe") still applies at runtime.

**Therefore the true remaining gap is runtime, not code** (Finding 2, verbatim): "promote the 472 from `deferred_attended` build+unit evidence to per-op live `ARIADNE_NATIVE_JOB` smoke under `accoreconsole`." This reframes Paul's "build ALL" mandate: the functionality is **already wired**; the program is mostly **PROVE-all + correctly-target + upload**, not "write hundreds of new handlers."

### 1.5 Two secondary defects to fix (from Finding 2)

1. **Tooling blind spot:** `reconcile_native_registry.py:74` `RE_FAMFILE = ^m08([a-z]+)_handlers\.inc$` matches only `m08*`, silently skipping the 5 non-`m08` families (`w6_*`, `materials_read`, `annoscale_read`). Its `all_coded_ops` reports 463, undercounting the true native gate (478) by 15. Consequence: the F8 four-surface vocab-lockstep check (`check_vocab_lockstep`, `:258-307`) is blind to any patch-op pointed at a w6/w7 native id.
2. **Stale SoT:** `reports\registry_coverage_latest.json` must be regenerated (`cadctl registry-coverage`) → will recompute to 551/489. Anyone citing it today gets 3-week-old 517/37.

---

## 2. SDK SURFACE BY FAMILY — capabilities + host-eligibility

**(Reconstructed; Finding 1 not delivered — a full 630-header census is WU-0.)** Module vocabulary is a **capability ladder, not one axis** (Finding 5, SDK-doc-confirmed):

| Module | Host exe | Has | Lacks | Headless |
|---|---|---|---|---|
| **`.dbx`** (Object Enabler) | ANY RealDWG host | AcDb, AcGe, AcBr, AcRx | editor, editor-reactors, host-app API | **yes** (most portable) |
| **`.crx`** (Console Runtime eXtension) | `accoreconsole.exe` | `.dbx` **+** `acedRegCmds`, single working doc (`acDocManager`), console-safe `acedCommand`, AutoLISP, reactor *registration*, `worldDraw` | graphics device, interactive input, UI, COM | **yes** |
| **`.arx`** | `acad.exe` | everything **+** interactive input, AcGs/AcGi graphics, full UI, COM server, live reactor/overrule/jig delivery | — | **no** |

Autodesk's own rule legislates the `.dbx`/`.arx` boundary: *"an Object Enabler may not use the AutoCAD editor, editor reactors, or any other APIs specific to the AutoCAD host application"* (OARX-DevGuide, "Overview of ObjectDBX and Object Enablers"). `AcDbAssocManager::evaluateTopLevelNetwork` is `ACDBCORE2D_PORT` → associative eval is DB-core, hence headless-capable.

### DB-core families → `.dbx` (headless, max portability)

- **entities (61)** — AcDb entities (`dbents.h`, `dbpl.h`, `dbspline.h`, `dbhatch.h`, `dbdim.h`, `dbmtext.h`) + geom queries (osnap/geomextents/offset/split). 61/61 headless. `worldDraw` hostless.
- **geometry_kernel (25)** — AcGe header-only math (`geell2d.h`, `genurb2d.h`, `gepnt3d.h`, matrices/curves). Host-agnostic; constructs into a staged `AcDbDatabase`. ⚠️ registry over-tags 16/25 `native_arx_only` — **mis-tiered** (§6).
- **brep_solids (54)** — AcBr topology (`br*.h` from `utils\brep\inc\`) + `AcDb3dSolid`/`Region`/`Surface`/`Body` (`dbsol3d.h`, `dbsurf.h`, `dbregion.h`, `dbbody.h`). massprops/volume/area/containment proven hostless (51/54); subentity edit/highlight (4) need GS/pick → arx.
- **symbol_tables_dictionaries (31)** — `AcDbSymbolTable`/`Record`, `AcDbDictionary`, xrecord (`dbsymtb.h`, `dbdict.h`, `dbxrecrd.h`). 28/31 headless.
- **objectdbx_database (21)** — `AcDbDatabase` lifecycle: create/readDwg/dxfIn/working-db/deepClone, `acdbHostApplicationServices()` (both hosts provide it, `m08c_handlers.inc:143`). This IS the ObjectDBX layer. 18/21 headless.
- **blocks_xrefs_clone (9)** — BTR iterate, `deepClone`/`wblockClone`, insert, xref attach/bind/relink (DB-level). 8/9 headless.
- **constraints_associativity (58)** — `AcDbAssoc*` network + `AcDbAssoc2dConstraintGroup`; `evaluateTopLevelNetwork` is DB-core. 39 headless; interactive constraint commands / bars / infer (19) → arx; 23 blocked (DCM solver).
- **custom_objects_protocols (63)** — Autodesk's canonical `.dbx` use: `AcRxObject`/`AcDbObject` subclassing, `ACRX_DXF_DEFINE_MEMBERS` (`rxboiler.h`), dwg/dxfInFields filers, protocol extensions, overrules, `worldDraw`. ⚠️ registry over-tags 57/63 `arx_adapter` — **incorrect per Autodesk's own definition** (§6). Editor-reactor-bound + `viewportDraw` protocols (≈57 runtime) are attended.
- **inspect (18)** — read-only DB queries (entity/block/layout/xref count, xdata, capabilities). 15 headless (2 are router-plane).
- **write / query / validate / patch / apply / diff / anchor / corpus / verify** (router-synthetic) — IR ops over a staged `AcDbDatabase`; all headless.

### Console-host families → `.crx`

- **runtime_commands (26)** — command **registration** (`acedRegCmds`) + module init/unload (`acrxEntryPoint`), console-safe `acedCommand`. 10 wired; 16 unbuilt are `module.lifecycle.*`/`module.command.*`/`module.entrypoint.*` = ObjectARX **load/unload callbacks** (`kInitAppMsg`), **not job-dispatchable ops** (§6).
- **reactors_events (22)** — DB reactors (`AcDbDatabaseReactor`/`AcDbObjectReactor`) register AND fire headless; editor/doc/app/linker reactors register headless but **events** need attended `acad.exe` (`m08m_handlers.inc:655-671`, `acedEditor`-gated).

### Interactive/host families → `.arx` only (headless-inert)

- **editor_input (27)** — `acedGetPoint`/`GetString`/`SSGet`/`EntSel` prompts (`aced.h`). Code gate: *"accoreconsole has no interactive editor"* (`AriadneNativeJob.cpp:7504`). 10 non-blocking (command-queue) ops are crx-eligible.
- **graphics_system (9)** — AcGs viewport/view/model, `AcGiViewportDraw`, grips, render. *"accoreconsole has no graphics device"* (`:7542`); zoom needs live view (`:7599`); render needs pipeline (`:7668`). Only `worldDraw` is hostless.
- **ui_customization (39)** — menus/CUI/ribbon/palettes/statusbar (AcAp/AcTcUi/adui). 39/39 `arx_adapter`. No UI in accoreconsole.
- **com_activex (51)** — `IAcadApplication`/`IAcadDocument`/COM wrappers; accoreconsole is not a COM automation server. 8 host-agnostic `AcAxDbEntity`/axdb bridge helpers are dbx-usable.
- **live (7)** — live reactors/overrules + jig (`acedGetPoint`, `:3942`); attended by definition.
- **active_document_write_original (8)** — live active-doc semantics via `AcApDocManager`; also **policy-blocked** (`write_original` forbidden regardless of host).
- **layouts_plot_publish (2)** — `AcPlPlotEngine`; 2/2 blocked. ⚠️ headless plot-to-PDF may be feasible — feasibility probe flagged (§6).

---

## 3. GAP MATRIX (Finding 3 numbers, verbatim; module-target from Finding 5)

Totals (Finding 3): **catalogued 545** (26 named families) **+ 6 router-internal** (anchor 4, corpus 1, verify 1) **= 551** registry · **really-implemented 484** (over named) · **gap 61**. Headless-eligible partition: **dbx 250 + crx 20 = 270** (= project RUNNABLE-270). "Headless" column = crx_eligible + dbx_layer (row-level). "Gap" = catalogued − really-implemented.

| Family | Cat. | Really-impl | Module target | crx | dbx | arx | Headless | Gap |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| custom_objects_protocols | 63 | 63 | **dbx** ⚠️(tagged arx) | 1 | 5 | 57 | 6 | 0 |
| constraints_associativity | 58 | 35 | dbx | 0 | 39 | 19 | 39 | 23 |
| entities | 61 | 61 | dbx | 0 | 61 | 0 | 61 | 0 |
| brep_solids | 54 | 50 | dbx | 0 | 44 | 10 | 44 | 4 |
| com_activex | 51 | 42 | arx | 0 | 8 | 43 | 8 | 9 |
| ui_customization | 39 | 37 | arx | 0 | 0 | 39 | 0 | 2 |
| editor_input | 27 | 26 | arx (+10 crx) | 10 | 0 | 17 | 10 | 1 |
| runtime_commands | 26 | 10 | crx | 2 | 1 | 23 | 3 | 16 |
| geometry_kernel | 25 | 25 | dbx | 0 | 9 | 16 | 9 (→25*) | 0 |
| reactors_events | 22 | 22 | crx/arx | 0 | 0 | 22 | 0 | 0 |
| objectdbx_database | 21 | 21 | dbx | 0 | 18 | 3 | 18 | 0 |
| symbol_tables_dictionaries | 31 | 31 | dbx | 0 | 28 | 3 | 28 | 0 |
| inspect | 18 | 18 | dbx | 4 | 11 | 3 | 15 | 0 |
| graphics_system | 9 | 9 | arx | 0 | 0 | 9 | 0 | 0 |
| active_document_write_original | 8 | 4 | arx | 3 | 0 | 5 | 3 | 4 |
| live | 7 | 7 | arx | 0 | 0 | 7 | 0 | 0 |
| blocks_xrefs_clone | 9 | 9 | dbx | 0 | 8 | 1 | 8 | 0 |
| write | 4 | 4 | dbx | 0 | 4 | 0 | 4 | 0 |
| extend | 2 | 2 | arx | 0 | 0 | 2 | 0 | 0 |
| validate | 2 | 2 | dbx (router) | 0 | 2 | 0 | 2 | 0 |
| patch | 2 | 2 | dbx (router) | 0 | 2 | 0 | 2 | 0 |
| layouts_plot_publish | 2 | 0 | arx | 0 | 0 | 2 | 0 | 2 |
| query | 1 | 1 | dbx (router) | 0 | 1 | 0 | 1 | 0 |
| render | 1 | 1 | dbx (router) | 0 | 1 | 0 | 1 | 0 |
| apply | 1 | 1 | dbx (router) | 0 | 1 | 0 | 1 | 0 |
| diff | 1 | 1 | dbx (router) | 0 | 1 | 0 | 1 | 0 |

`*` geometry_kernel: 16 ops mis-tagged `native_arx_only`; if re-tiered (§6), family becomes 25/25 headless.

**The 61-op gap ≈ the 62 registry-`blocked` ops** (Finding 2 clustering: constraints 23, runtime_commands 16, com_activex 9, active_doc 4, brep 4, ui 2, layouts 2, editor 1, live 1). **Of the 474 wired ops, only 240 are headless-eligible; 234 compile in but need interactive `acad.exe` at runtime.** The residual headless-eligible-but-implemented count (270 − 240) is carried by the **router-plane** ops (validate/patch/query/render/apply/diff/anchor + the 17 managed) — correct by design.

**Headless slice of the 61-op gap is SMALL:** candidates are `constraints_associativity.define.assocarray.*` (~4; `AcDbAssocArray` is a DB object) and possibly `layouts_plot_publish` (2, pending the accoreconsole-plot probe). The rest — `com_activex.automate.*`, `ui.menu.invoke`, `editor.command.queue.post`, `active_document.command.invoke.*`, and especially the ~16 `runtime_commands.module.lifecycle/entrypoint` callbacks (not job-dispatchable) — are **arx-only or non-op by nature**.

---

## 4. BUILD PLAN — disjoint per-family work-units for parallel workers

### 4.0 Premise correction (surface, don't average)

The task frames this as "decompose the IN-SCOPE gap into per-family build units." **The evidence (Finding 2) says native handler coverage is effectively complete (0 catalogued/stub; 472–474 native branches with real AcDb/AcGe/AcBr work).** So the parallel program is dominated by **live-smoke validation + correct module targeting + upload**, with only a **tiny** new-handler tail. Building the plan around "write 450 missing handlers" would be an FM4/optimistic-path error. The buckets below reflect the true work.

### 4.1 Disjointness architecture (the hard constraint)

Confirmed on disk: family handlers live in **16 separate `.inc` files** under `src\Ariadne.AcadNative\families\`, but the **mapping is many-to-one** — `m08d` holds entities+brep+geometry; `m08e` holds symtab+blocks; `m08m` holds com+reactors; `m08n` holds ui+editor+runtime+active_doc. Three files are **shared contention points**:

- `src\Ariadne.AcadNative\AriadneNativeJob.cpp` — the dispatch gate (`:6217`), `kAriadneNativeOperationTable` (`:6052`), `familyHasOp` OR-list (`:6163-6174`), and `#include families/*.inc` (`:6145-6160`).
- `config\operations.v2.json` — the registry SoT (re-tier / status edits).
- `tools\reconcile_native_registry.py` — the reconcile tool.

**Rules for the parallel phase:**
1. **Validation units edit NO source** — they run smoke and write disjoint evidence files (`reports\live_smoke\<family>.json`). Zero source contention → massively parallel. Partition by `.inc` file (not by family, since families share files).
2. **New-code units CREATE a new `.inc`** (e.g. `constraints_assocarray_handlers.inc`) rather than edit a shared one — keeps worker diffs disjoint (per the task's "separate source files per family" directive).
3. **ALL edits to the 3 shared files are SERIALIZED through one integration unit** (or `merge_executor`), run AFTER family units. No worker hand-edits `AriadneNativeJob.cpp`, the registry, or the reconcile tool in parallel. (Aligns with memory: in-process-teammate cwd collision → own-worktree; octoloop workers issue no git commands.)
4. Workers run in isolated worktrees (`D:\runs\wt\autocad-sdk-router__<lane>`), report disk-first.

### 4.2 Work-units

**WU-0 — Close the two missing Phase-0 findings (blocks nothing; do first, cheap).** Owner: 1 worker.
- (a) **SDK header census** (intended Finding 1): enumerate `C:\ObjectARX 2027\inc\*.h` (630) + `inc-x64\` (8) + `utils\brep\inc\`, map each header/class-family to the 26 op-families, emit `reports\sdk_header_census.json`. Read-only SDK; no repo source touched.
- (b) **Validation-protocol spec** (intended Finding 4): ratify §5 below into `docs\PER_OP_VALIDATION_PROTOCOL.md`. New file, disjoint.

**Bucket A — LIVE-SMOKE VALIDATION (the main body; ~240 headless ops).** This is the genuine frontier (§1.4). One unit per `.inc` file (disjoint evidence outputs, zero source edits):

| Unit | `.inc` file | Families covered | Headless ops to smoke |
|---|---|---|---|
| A1 | `m08c_handlers.inc` | objectdbx_database | 18 |
| A2 | `m08d_handlers.inc` | entities + brep_solids + geometry_kernel | 61+44+9 |
| A3 | `m08e_handlers.inc` | symbol_tables + blocks_xrefs | 28+8 |
| A4 | `m08kc_handlers.inc` | constraints (headless slice) | 39 |
| A5 | `m08k_handlers.inc` | custom_objects (dbx-definable slice) | 6 |
| A6 | `w6_layerstate/dynblk/section` + `materials_read` + `annoscale_read` | w6/w7 | (15 native, per §1.5) |
| A7 | table ops in `AriadneNativeJob.cpp` | write/inspect/live/extend native table (READ-ONLY smoke; no edit) | 45 |
| A8 | `m08g_handlers.inc` (44 ops), `m08h_handlers.inc` (15 ops) | **family unmapped in findings** — census first (WU-0a) then smoke |

Each A-unit: for its ops with `host_eligibility ∈ {dbx, coreconsole}`, run the §5 protocol against a fixture DWG, emit `reports\live_smoke\<unit>.json`, and record per-op `PASS`/`BLOCKED(reason)`. **Note A7:** table handlers live inside the shared `AriadneNativeJob.cpp` but validation reads/executes only — it must not edit the file, so no contention with the integration unit.

**Bucket B — REGISTRY RE-TIER CORRECTIONS (2 items; SERIALIZED, integration unit).** Not parallel — both edit `config\operations.v2.json`.
- B1: `custom_objects_protocols` 57 ops `arx_adapter → objectdbx_capable` (Autodesk-defined; §6-Q1). **Build implication:** currently these handlers compile only into `.crx`/`.arx` via `Ariadne.AcadNative`; the `.dbx` module (`Ariadne.AcadNativeDbx`, a *separate thin codebase* — confirmed on disk) does **not** include the `m08k` handlers. Re-targeting to `.dbx` requires either adding the `.inc` to `Ariadne.AcadNativeDbx.dbx.vcxproj` or a shared-header refactor → **this is real build work, flag as B1-heavy.**
- B2: `geometry_kernel` 16 ops `native_arx_only → objectdbx_capable`.

**Bucket C — GENUINE HEADLESS GAP-FILL (small; NEW files).** Each worker creates a new `.inc`, integration unit wires it:
- C1: `constraints_assocarray_handlers.inc` — `define.assocarray.create/path/polar/rectangular` (4). **Feasibility-gate first** (AcDbAssocArray headless eval).
- C2: (conditional) `layouts_plot_handlers.inc` — `plot.config.settings`, `plot.engine.run` (2) — **only if** the §6-Q4 accoreconsole-plot probe passes; else leave blocked.

**Bucket D — ARX-TIER BUILD/CONFIRM (out of headless scope; build into `.arx` only).** These families are **already native-wired** and compile into `.arx` via `Ariadne.AcadNative.arx.vcxproj` (which adds `AriadnePalette.cpp`, the sole `#ifndef ARIADNE_NATIVE_CRX` unit). Work = confirm `.arx` build (exit 0), confirm each op is runtime-gated by `hostMode=="full_autocad"` (`AriadneNativeJob.cpp:577-580`), and stub the interactive tail with the existing honest-gap pattern. **Do NOT wire these against `.crx`.** Families: ui_customization, com_activex (minus 8 axdb helpers → dbx), graphics_system, editor_input (interactive 17), live, reactors (editor/doc/app tail), active_document_write_original. One confirm-unit per `.inc` (`m08l`, `m08m`, `m08n`), evidence-only, disjoint. **Non-op reclassification:** the ~16 `runtime_commands.module.lifecycle/entrypoint` callbacks should be moved out of the op-registry into a "module hooks" classification (registry edit → integration unit B).

**Bucket E — TOOLING + SoT REFRESH (SERIALIZED, integration unit).**
- E1: fix `reconcile_native_registry.py:74` `RE_FAMFILE` to also match `w6_*`/`materials_read`/`annoscale_read` (§1.5-1).
- E2: regenerate `reports\registry_coverage_latest.json` via `cadctl registry-coverage` → 551/489 (§1.5-2). Ordering: **after** A/B/C/D so counts reflect final state.

**Bucket F — INTEGRATION (single serialized owner / `merge_executor`).** Applies all `AriadneNativeJob.cpp` table/gate/`#include` additions for C1/C2, all `operations.v2.json` edits (B1/B2/D-reclass/status promotions), rebuild `.crx`/`.arx`/`.dbx` via `tools\build_native_acad.ps1` (isolated `-OutputRoot`), confirm three modules link (exit 0). **This is the only unit that touches the 3 shared files.**

**Bucket G — GITHUB UPLOAD (last; gated on integrity).** See §6-Q5.

### 4.3 Ordering / dependencies

```
WU-0 (census+spec) ──► A1..A8 (parallel validation, no deps) ──┐
                                                                ├─► E2 (regen coverage)
B1,B2 / D-reclass ─► F (integration+rebuild) ◄── C1,(C2) ──────┤
E1 (tool fix, independent) ─────────────────────────────────────┘
                                        F PASS ─► G (upload)
```
- A-units depend only on WU-0a for the two unmapped `.inc` (A8).
- C-units are gated on their feasibility probes (§6).
- F must run after B/C/D; E2 after F; G after E2 + integrity gate.

---

## 5. PER-OP VALIDATION PROTOCOL

**(Reconstructed — Finding 4 not delivered. Source: Finding 2's runtime-frontier statement + this repo's CADOS invariants + the `cad.*` MCP surface. Ratify as WU-0b before Bucket A executes.)**

**Goal:** promote each of the ~240 headless-eligible wired ops from `deferred_attended` (build+unit evidence) to **live `accoreconsole` per-op smoke** — the only evidence that satisfies "`available:true` from a live probe."

**Per-op procedure (headless, `.crx`/`.dbx` via `accoreconsole.exe`):**
1. **Stage** an ASCII-pathed copy of a fixture DWG (`fixtures\`); original stays READ-ONLY (invariant: original-immutable). Never `write_original`.
2. **Invoke** the op through the native job path — `ARIADNE_NATIVE_JOB` under `accoreconsole` (equivalently `cad.run_operation` MCP with `write_mode` gate), passing a minimal valid job payload for the op.
3. **Assert on the payload, not the exit code** (FM8: `rc=0` ≠ domain success). Parse `writeResult()` JSON (`jsonEscape`/`njsonStr` helpers, `AriadneNativeJob.cpp`): require `found`/`ok` true AND the op-specific field (e.g. an entity handle for `write.entity.line`, a mass-properties struct for `compute.brep.massprops`). An op that returns `host_required`/`OPERATION_NOT_IMPLEMENTED` → `BLOCKED(reason)`, not PASS.
4. **Mutating ops** run the dry-run→apply→diff triad (`cad.patch_dry_run → cad.patch_apply_staged → cad.diff_before_after`) on the staged copy; assert the diff shows exactly the intended delta.
5. **Record evidence** to `reports\live_smoke\<unit>.json`: `{op_id, command, stdout_digest, result_payload_excerpt, verdict}`. Digest large output via context-mode; never inline raw bytes.
6. **Verdict vocabulary (strict):** `PASS` (payload-cited) · `BLOCKED` (host_required/unsupported, with reason) · `PARTIAL_PASS` (ran but reduced scope). No status inflation (FM1).

**arx-tier ops (Bucket D):** cannot be smoked headless by definition. Evidence = `.arx` build exit 0 + presence of the `hostMode=="full_autocad"` runtime gate + (optional, attended) a manual `acad.exe` run. Mark `PASS_WITH_DEFERRAL(attended_acad_required)` — never `PASS` from a headless run.

**Batch gate:** a family unit is `PASS` only when every headless op in it is `PASS` or an explicitly-reasoned `BLOCKED`; any silent skip fails the unit (FM2: stale/rc=0 ≠ fresh output — check mtime + content of the evidence file).

---

## 6. RISKS / OPEN QUESTIONS

**Q1 — custom_objects_protocols module target (highest-value correction).** Registry tags 57/63 `arx_adapter`, but Autodesk's own definition makes the Object Enabler (`.dbx`) *the* mechanism for custom-object definition/registration/filers/protocol/`worldDraw`. Confirmed structural obstacle: the `.dbx` module (`Ariadne.AcadNativeDbx`) is a **separate thin codebase** (`AriadneDbxEntry.cpp` etc., ~4 KB each) that does **not** include `m08k_handlers.inc`. Re-targeting 63 ops to `.dbx` is **real build/refactor work** (share the `.inc` into `Ariadne.AcadNativeDbx.dbx.vcxproj`, or extract shared headers), not just a registry flag. **Decision needed before B1.**

**Q2 — geometry_kernel over-tagging.** 16/25 AcGe ops tagged `native_arx_only` despite AcGe being host-agnostic header math. Low-risk re-tier (B2), but confirm each of the 16 actually constructs into a staged DB (not into a live editor selection) before flipping.

**Q3 — ASM / BRep headless dependency.** brep_solids links `acbr26.lib`/`acgex26.lib`/`acgeoment.lib` and the underlying solid modeler is ASM (Autodesk Shape Manager). massprops/volume/area/containment are proven hostless (51/54, `execution_context=hostless_dbx_in_accoreconsole`), but **solid creation / boolean ops may require ASM to initialize under `accoreconsole`** — not yet proven per-op. Bucket A2 must smoke the constructive BRep ops specifically, not just the analytic ones; treat ASM-init failure as `BLOCKED`, not a code gap.

**Q4 — headless plot feasibility (`layouts_plot_publish`).** Registry marks both blocked, but `AcPlPlotEngine` **can** plot-to-PDF/DWFx headless in some accoreconsole configs. Run a bounded feasibility probe before accepting the blocked tag (gates C2). If it fails, keep blocked with evidence.

**Q5 — GitHub upload integrity (Paul's explicit target).** Blockers to clear **before** Bucket G:
- **License:** `C:\ObjectARX 2027` headers/libs are Autodesk-licensed — **MUST NOT be committed**. Verify `.gitignore`/`.gitattributes` exclude any vendored SDK content and the built `.crx`/`.arx`/`.dbx` binaries (which link Autodesk libs). Repo already has `.gitignore` (3.1 KB) + `.graphifyignore` — audit them against an allowlist policy (memory: "Ariadne git repo = ALLOWLIST gitignore").
- **Secrets:** confirm no `*.env`/`*credential*`/`*token*`/`*key*`/`*.pem` under the repo; `prebuilt/`, `staging/`, `runs/`, `ErrorReports/`, `handoff/`, `tmp*/` directories are present and likely local-only — exclude.
- **Binary policy decision:** commit built modules, or source-only + build instructions (`INSTALL.md`/`install.ps1` exist)? Recommend source-only (Autodesk-lib linkage makes binaries non-redistributable).
- This is an **irreversible external-share action** → requires explicit Paul sign-off (memory: external-share is the security boundary; irreversible ops always pre-confirm).

**Q6 — the "implemented ≠ headless-functional" gap is the real deliverable risk.** 489 declared-implemented, but only ~240 are headless-eligible and **none are yet live-smoke-proven** (all `deferred_attended`). If the build phase reports "489 done" without Bucket A live evidence, that is FM1/FM8. The dossier's PASS claim in §1 is about **wiring** (evidenced); the **runtime** claim remains `PASS_WITH_DEFERRAL` until Bucket A completes. The project's own certification also flags ~24 ops as degenerate — reconcile that list against Bucket A results.

**Q7 — m08g / m08h family identity unknown.** `m08g_handlers.inc` (110 KB, 44 ops) and `m08h_handlers.inc` (32 KB, 15 ops) are the two largest/second-tier `.inc` files but **no delivered finding maps them to a named family.** WU-0a census must resolve their family + host-eligibility before A8 can smoke them; until then their 59 ops are `PASS_WITH_DEFERRAL(unmapped)`.

---

## Key files (absolute, verified on disk this session)

- Dispatch gate + table (SHARED): `D:\dev\99_tools\autocad-sdk-router\src\Ariadne.AcadNative\AriadneNativeJob.cpp` (357.6 KB; gate `:6217`, `familyHasOp :6163-6174`, `kAriadneNativeOperationTable :6052`, `#include :6145-6160`, hostMode gate `:577-580`)
- Family handlers (16 `.inc`, disjoint units): `...\src\Ariadne.AcadNative\families\{m08c,m08d,m08e,m08f,m08g,m08h,m08k,m08kc,m08l,m08m,m08n}_handlers.inc`, `{w6_layerstate,w6_dynblk,w6_section}_handlers.inc`, `materials_read.inc`, `annoscale_read.inc`
- arx-only UI unit: `...\src\Ariadne.AcadNative\AriadnePalette.cpp` · worldDraw/viewportDraw probe: `...\AriadneProbe.cpp`
- Build targets: `...\src\Ariadne.AcadNative\Ariadne.AcadNative.crx.vcxproj`, `...\Ariadne.AcadNative.arx.vcxproj`
- `.dbx` module (separate thin codebase — Q1): `...\src\Ariadne.AcadNativeDbx\{Ariadne.AcadNativeDbx.dbx.vcxproj,AriadneDbxEntry.cpp,AriadneRecord.cpp,AriadneProtocol.cpp,AriadneDbxApi.h}`
- Managed/router layer (17 non-native ops): `...\src\Ariadne.DwgGeometryExtractor\CadJobRunner.cs`, `...\tools\run_route.py`
- Registry SoT (551/489/62): `...\config\operations.v2.json` · aliases: `...\config\cad_job_operation_aliases.json` · DAG: `...\config\op_dag.json`
- Reconcile tool (defines "implemented"; regex bug `:74`, evidence `:150`): `...\tools\reconcile_native_registry.py`
- Native build script (isolated `-OutputRoot`): `...\tools\build_native_acad.ps1`
- Stale coverage report (517/37, regenerate): `...\reports\registry_coverage_latest.json` · schema: `...\schemas\operation_registry.v2.schema.json`
- SDK (never commit): `C:\ObjectARX 2027\{inc\ (630 .h), inc-x64\, lib-x64\, utils\brep\inc\}`

## Bottom line for the build phase

1. **The 489 is real and current; the 37 is a stale re-tally.** 472 native handlers + 17 router = 489, all evidence-backed at the **wiring** level (`PASS`), but **build-evidenced, not runtime-proven** (`PASS_WITH_DEFERRAL` on runtime).
2. **The dominant Phase-2 work is live-smoke validation (Bucket A, ~240 headless ops), not new handlers.** The genuine new-code headless gap is ~4–6 ops (assocarray, maybe plot), pending feasibility gates.
3. **Two registry re-tiers (custom_objects→dbx [63], geometry→dbx [16])** materially change module targeting; custom_objects→dbx carries a real refactor cost (the `.dbx` module doesn't share the `.inc` handlers today).
4. **Disjointness is achievable:** validation edits no source (partition by `.inc`, evidence-only); all shared-file edits (`AriadneNativeJob.cpp`, `operations.v2.json`, reconcile tool) funnel through ONE serialized integration unit.
5. **GitHub upload is gated on a license/secrets audit and explicit sign-off** — do not commit the ObjectARX SDK or Autodesk-linked binaries; recommend source-only.