# Native ObjectARX 2027 Research — Completeness / Contradiction / Coverage Audit

Adversarial completeness critic pass over the 6 slice files in this directory.
Method: every claim below is parsed from the on-disk slices and (where a gap was
suspected) confirmed against the local SDK at `C:\ObjectARX 2027\inc` /
`lib-x64` / `inc-x64` and the CHMs (`arxref.chm`, `arxdev.chm`). Op-row counting
is programmatic: a "real op" = a table row whose first cell is a backtick-wrapped
dotted id (e.g. `inspect.database.read_dwg`). Tier = the engine_tier cell;
"primary" = first tier listed when a row lists several.

Verdict up front: **all 6 slices are structurally complete** (every required
section present, no truncated/empty/malformed rows). Coverage is **NOT**
complete: **4 of the 18 catalog families are zero-or-near-zero** and need
another research pass before this can be called a full native capability map.

---

## 1. PER-SLICE COMPLETENESS

Expected section set per slice (5): Operation catalog · Classes & subsystems
covered · Build / integration notes · C++-only delta · Sources actually read.
`editor-delta` substitutes/adds a **DELTA TABLE (Part 2)** alongside its Part-1
op catalog (its "C++-only delta" lives as that table), which is the intended
shape for that slice.

| slice | required sections present | op_row_count (distinct) | truncated / empty / malformed rows | verdict |
|---|---|---|---|---|
| arx-framework.md | 5/5 (+ C++-only delta as its own §) | 25 | none | **complete** |
| acdb-core.md | 6/6 (adds explicit "Host-less verdict (precise)" §) | 42 | none | **complete** |
| entities-geometry-graphics.md | 5/5 | 90 | none | **complete** |
| custom-objects.md | 5/5 | 45 | none | **complete** |
| reactors-overrules.md | 5/5 (+ verdict-on-editor-delta inside C++-delta §) | 40 | none (2 rows are deliberately `(unverified)` cells, not malformed) | **complete** |
| editor-delta.md | 5/5 (Op catalog PART 1 + DELTA TABLE PART 2) | 42 | none | **complete** |

- No table row was found with a missing/empty engine_tier cell. 0 rows mapped to
  UNMAPPED tier across all 284 ops.
- `entities-geometry-graphics` legitimately carries 90 ops (it folds entities +
  AcGe geometry kernel + AcGi graphics into one slice); verified the rows are
  distinct op_ids, not a parser artifact.
- The only "(unverified)" *cells* (as opposed to row-level notes) are the two
  overrule rows in reactors-overrules (`overrule.dimstyle.install`,
  `overrule.drawable.install`) — intentional honesty markers, see §2.

---

## 2. UNVERIFIED INVENTORY (every "unverified" tag, + resolution)

11 distinct unverified markers exist. Most are honesty hedges on an exact header
line number, not on the existence of the API. 5 spot-checked against on-disk
headers this session; results recorded.

| # | slice | item flagged unverified | resolvable by | SPOT-CHECK RESULT |
|---|---|---|---|---|
| 1 | arx-framework | `acrxServiceIsLoaded(...)` "do NOT emit as fact" | header grep | **REFUTED / correctly flagged** — NOT present in any `inc\*.h`. Only `acrxLoadModule` exists (`rxregsvc.h:27,31`). The slice was right to refuse to assert it. |
| 2 | reactors-overrules | `AcDbDimensionStyleOverrule` signatures NOT read | `dbdim.h` | **RESOLVED** — exists `dbdim.h:919`, `: public AcRxOverrule`, real methods: `dimensionStyle / setDimensionStyle / getDimstyleData / setDimstyleData`. Fillable now. |
| 3 | reactors-overrules | `AcGiDrawableOverrule` signatures NOT read | `drawable.h` | **RESOLVED** — exists `drawable.h:222`, `: public AcRxOverrule`. Fillable now. |
| 4 | custom-objects | exact `lib-x64` .lib filenames not enumerated; `AcRxProtocolReactor` body not opened | `lib-x64` dir + `rxprodct.h` | **PARTIAL** — `lib-x64` confirmed present (contains `acdb26.lib, accore.lib, acge26.lib, rxapi.lib, acdbmgd.lib, AcDrawBridge.lib`); the PE/protocol-reactor body remains unopened (grounded indirectly via queryX/addX sample). Low risk. |
| 5 | editor-delta | `acedPostCommand` exact signature; `acutPrintf` exact line; `acedSSAdd/Del/Name` exact lines; context-menu CUI API | `aced.h`/`acedads.h`/`AdMenuBar.h` | **PARTIAL** — the functions are real and the headers (`aced.h`, `acedads.h`, `AdMenuBar.h`) are confirmed present on disk; only the precise line numbers were hedged. The *capability* claims stand; only citation precision is soft. |
| 6 | acdb-core | header intro: marks anything not directly evidenced as (unverified) | — | meta-disclaimer, no concrete unverified op. |
| 7 | acdb-core | `transaction.manager.end/.abort` nested-abort behavior | arxdev.chm GUID-BFA742C3 | doc-page-backed in the slice's own sources list; not a true gap. |
| 8 | acdb-core | `write.regapp.register` host/hostless context note | — | hedge on execution-context label, not on the API. |
| 9 | acdb-core | `inspect.database.sysvar` per-var typed getters | arxref.chm | enumerable from CHM if needed; bounded. |
| 10 | entities-geometry-graphics | explicitly states "Items marked unverified: none" (only truncated overload arg-lists) | arxref.chm | self-clean; only some `createExtrudedSolid`/`append*` defaulted-arg lists truncated. |
| 11 | custom-objects | header intro disclaimer + `.props` header/dir list note | `inc\*.props` | meta; `dbx.props / rxsdk_common.props / rxsdk_debugcfg.props` named. |

**Net:** no unverified item turned out to be a fabrication. One (`acrxServiceIsLoaded`)
is genuinely non-existent and was correctly withheld. Two overrule signatures
(items 2,3) are now resolved against headers and should be promoted from
"(unverified detail)" to verified in a cleanup pass. The rest are line-number
precision hedges on APIs that do exist.

---

## 3. CROSS-SLICE CONTRADICTIONS — RULINGS

### (a) "Host-less DWG library I/O" tier — RESOLVED (no real contradiction; a definitional split)

arx-framework / editor-delta label standalone DWG read/write `native_C++_only`
because **RealDWG is excluded from the project license**; acdb-core's managed
plane already reads a side DB via `new Database(false,true)` + `ReadDwgFile`
*inside accoreconsole*. These are **not in conflict** — they describe two
different "host-less" meanings, and acdb-core's "Host-less verdict (precise)" §
(L99) already adjudicates it verbatim:

- **"host-less" has a hard prerequisite stated in the docs**: a non-AutoCAD
  process MUST instantiate an `AcDbHostApplicationServices` subclass (no default
  provided), override pure-virtual `findFile()`, call
  `acdbSetHostApplicationServices()` once, and `setWorkingDatabase()`. *That host-
  services object IS the host.* → **There is no zero-host C++ DWG read.**
- Two distinct meanings:
  - **standalone .exe, no AutoCAD at all** = the **RealDWG** path = **license-
    EXCLUDED** for this project. Native ObjectARX libs are free, but shipping a
    non-AutoCAD exe that links them is RealDWG. (Cited: `dbapserv.h` AcDbHost-
    ApplicationServices class :108 / pure-virtual findFile :166-171 / setWorking-
    Database :310.)
  - **inside accoreconsole, no current document** = accoreconsole IS the host and
    supplies host-application-services. `new Database(false,true)` + ReadDwgFile
    is proven there by our managed plane; an `.arx` ARX-loaded into accoreconsole
    gets the identical no-document `AcDbDatabase` surface. **License-clean.**

**CORRECT engine_tier for side-database DWG read/write:** **`objectdbx_capable`**,
read precisely as *"runs host-less inside accoreconsole (no current document)"* —
**NOT** `native_arx_only` and **NOT** "runs in a bare standalone exe." The
`native_C++_only` label in arx-framework/editor-delta is correct **only** for the
standalone-exe (RealDWG) reading, which is out of license scope. **Action:** the
two delta tables should annotate their `native_C++_only` host-less rows with
"(= RealDWG standalone only; accoreconsole-hosted DWG I/O is objectdbx_capable)"
to remove the apparent contradiction. **Flag for Paul: the RealDWG license boundary
is the real constraint, not an engine capability.**

### (b) OVERRULES tier — editor-delta `managed_also` is an OVER-GENERALIZATION; reactors-overrules is correct

reactors-overrules explicitly rules on the editor-delta claim (C++-delta §). Ruling,
cited to headers read this session (`rxoverrule.h`, `dbobjectoverrule.h`,
`dbentityoverrule.h`):

- The **base mechanism + the mainstream entity-level overrules** (`Overrule`,
  `DrawableOverrule`, `GeometryOverrule`, `TransformOverrule`, `OsnapOverrule`,
  `GripOverrule`, `PropertiesOverrule`, `VisibilityOverrule`, `SubentityOverrule`,
  `HighlightStateOverrule`) **are genuinely `managed_also`** — editor-delta is fair
  there.
- **But the C++ surface is strictly larger and those parts are `native_arx_only`:**
  `AcRxQueryXOverrule` (protocol-extension queryX hook), `AcDbObjectOverrule`
  (open/close/cancel/erase/deepClone/wblockClone at the AcDbObject lifecycle level),
  `AcDbDimensionStyleOverrule`, and any overrule used to author custom
  entities/object-enablers.

**CORRECT tier:** there is **no single tier for "overrules."** Per-op:
entity-level + base = `managed_also`; queryX/object-lifecycle/custom-authoring
overrules = `native_arx_only`. Treat **editor-delta's blanket `managed_also` as
imprecise; reactors-overrules' per-op split is authoritative.**

### (c) TRANSIENT vs PERSISTENT reactors — CONFIRMED with one correction

- **PERSISTENT reactor = `native_arx_only`: CONFIRMED.**
  `AcDbObject::addPersistentReactor(AcDbObjectId)` (`dbObject.h:384`) writes an
  ObjectId link into the DWG; the reacting object must be a real serialized
  AcDbObject (object-enabler/DBX territory). AutoLISP `vlr-pers` only flips an
  existing reactor's persistence flag — it cannot *create* the C++ persistent
  reactor. (Cited: arxref `dbObject.h`; doc GUID-0A632CD0 "Transient and
  Persistent Reactors", GUID-A55D4A3D persistent-reactor DXF serialization.)
- **TRANSIENT reactor = `managed_also`: TRUE ONLY FOR THE COMMON ONES — correct
  the blanket label.** Common object/database/editor reactors are managed_also
  (`ObjectOverrule`/`...Reactor`, `Database.ObjectAppended`, `Editor` events,
  `Application.DocumentManager` events). **But** several transient families have
  **no managed surface** and are native-only: `AcApLongTransactionReactor`
  (REFEDIT/long-transaction), `AcRxDLinkerReactor` (module load/unload), and the
  low-level `AcRxEventReactor` deep-clone/wblock granularity.

**CORRECT:** persistent = `native_arx_only` (firm). Transient = `managed_also`
for the mainstream set, **but not uniformly** — long-transaction / linker /
low-level Rx-event reactors are `native_arx_only` even though transient. The
slices' per-op tiers already encode this; editor-delta's one-line "TRANSIENT =
managed_also" is the over-simplification.

### (d) Operations claimed by TWO slices with different tier — NONE (literal), but TWO capability-level overlaps

- **Literal op_id collisions across files: ZERO.** Programmatic check: 284
  distinct op_ids, no op_id appears in more than one slice. So there is no
  same-op/two-tier contradiction at the id level.
- **Capability-level overlaps (same capability, two slices, reconciled above):**
  1. **Overrules** — appear as op rows in reactors-overrules (`overrule.*`,
     mostly `native_arx_only`) and as a capability row in editor-delta's DELTA
     TABLE (`managed_also_equivalent`). Reconciled in (b): per-op split wins.
  2. **Custom-object filing / protocols** — touched by custom-objects (authoring,
     `native_arx_only`) and acdb-core/entities (consuming standard objects,
     `objectdbx_capable`). Not contradictory: authoring custom classes is native;
     reading standard objects is objectdbx — different operations, consistent
     tiers.

---

## 4. COVERAGE MATRIX — 18 catalog families

Coverage scored by signature-keyword presence in slice text, then the 4 high-risk
families hard-verified against on-disk headers.

| # | family | covered by slice(s) | approx ops | status |
|---|---|---|---|---|
| 1 | runtime_commands | arx-framework (core), editor-delta (cmd reg) | ~22 | covered |
| 2 | objectdbx_database | acdb-core (core) | ~35 | covered |
| 3 | symbol_tables_dictionaries | acdb-core | ~10 (within 42) | covered |
| 4 | entities | entities-geometry-graphics | ~40 | covered |
| 5 | blocks_xrefs_clone | acdb-core + custom-objects (clone) + entities | ~12 | covered |
| 6 | geometry_kernel (AcGe) | entities-geometry-graphics | ~20 | covered |
| 7 | **brep_solids** | entities (AcDb3dSolid create/bool/loft + `getArea`/`getMassProp`) only | solid-modeling yes; **AcBr topology = 0** | **PARTIAL GAP** |
| 8 | graphics_system (AcGi) | entities + custom-objects (worldDraw) + editor-delta | ~25 | covered |
| 9 | editor_input | editor-delta (core) | ~40 | covered |
| 10 | reactors_events | reactors-overrules (core) + editor-delta | ~25 | covered |
| 11 | custom_objects_protocols | custom-objects (core) + reactors-overrules (overrules) | ~45 | covered |
| 12 | **constraints_associativity** | **NONE** | **0** | **ZERO — REAL GAP** |
| 13 | layouts_plot_publish | editor-delta (plot engine + plot settings) | ~5 | thin but present |
| 14 | **ui_customization** | editor-delta: palette-create + context-menu only | **2** | **NEAR-ZERO GAP** |
| 15 | **com_activex** | **NONE (automation)** — only `getClassID` CLSID-resolution + ActiveX ref used as a name cross-check | **0 automation ops** | **EFFECTIVELY ZERO — REAL GAP** |
| 16 | autolisp_visual_lisp | cross-cut: editor-delta + reactors-overrules + acdb-core (the `accoreconsole_lisp_also` tier) | ~16 (as tier tag) | covered (as cross-cut) |
| 17 | core_console | cross-cut everywhere (host-less verdict, execution_context) | n/a (cross-cut) | covered |
| 18 | active_document_write_original | editor-delta (acedCommandS/syncopen) + acdb-core | ~6 | covered |

### Hard-verified findings on the 4 specifically-named families

- **constraints_associativity = ZERO coverage, and it is a REAL, fillable gap.**
  No slice mentions any `AcDbAssoc*` / constraint / associative-array API. The SDK
  ships **~60 headers** for it: `AcDbAssocAction(Body).h`, `AcDbAssoc2dConstraint
  Group.h`, `AcConstrainedGeometry.h`, `AcGeomConstraint.h`,
  `AcDbAssocArray{Rectangular,Polar,Path}Parameters.h`, `AcDbAssocArrayAction
  Body.h`, `AcDbAssocManager.h`, `AcDbAssocNetwork.h`, `AcDbAssocDependency.h`,
  `AcDbGeomRef.h`, `dbdimassoc.h`, etc. **Geometric + dimensional constraints AND
  associative arrays are entirely unresearched.** Needs a 7th slice.
- **brep_solids = PARTIAL.** Solid *creation/booleans/interference/mass-props*
  (`AcDb3dSolid`, `getArea`, `getMassProp` in `dbsol3d.h`) are covered in
  entities. **But the AcBr topology layer is missing**: zero `AcBr*` / `AcBrBrep`
  / `AcBrFace` / `AcBrEdge` / `AcDbSubentId` coverage. AcBr is NOT in main `inc`
  (it ships as `AcDrawBridge.lib` in `lib-x64`; headers are in the brep SDK
  subset). **Subentity-level topology traversal and BRep face/edge enumeration are
  unresearched.**
- **ui_customization = NEAR-ZERO (2 ops).** Only `editor.palette.create`
  (`CAdUiPaletteSet::AddPalette`) and `editor.menu.context` (CUI/`AdMenuBar.h`).
  The SDK ships the full UI surface — **tool palettes** (`AcTc.h`, `AcTcUI.h`,
  `AcTcUiToolPalette(Set/Group).h`, `AcTcUiManager.h`, `AcTcUiScheme.h`),
  **ribbon** (no `Ribbon*` op researched at all), **CUI file editing**, status-bar
  `AcStatusBarItem`/`AcPane`/`AcTrayItem` (named in prose, no op rows), and the
  `acui*`/`adui*` dialog family. **Ribbon = 0, tool-palette population = 0, CUI
  edit = 0.**
- **com_activex = EFFECTIVELY ZERO automation.** NO `IDispatch`, NO
  `AcadApplication`/`AcadDocument`/`AcadObject` automation object, NO COM
  operation rows. The only COM-adjacent items are `AcDbPropertiesOverrule::
  getClassID` (CLSID resolution for OPM) and an ActiveX-Reference page used *only*
  to cross-check C++ method names. The SDK ships the bridge (`axboiler.h`,
  `axdispids.h`, `axlock.h`, `axobjref.h`, `dbole.h`, `oleaprot.h`, the `opm*.h`
  Object Property Manager family). **Application/Document automation + OPM property
  exposure are unresearched.**

---

## 5. TOTALS

- **Total distinct ops across all 6 slices: 284** (no cross-slice op_id duplicates).
- **By engine_tier (PRIMARY = first-listed tier on each row):**
  | tier | ops (primary) |
  |---|---|
  | native_arx_only | 141 |
  | objectdbx_capable | 114 |
  | managed_also | 13 |
  | accoreconsole_lisp_also | 16 |
  | (unmapped) | 0 |
- **By engine_tier (APPEARS-IN = an op counted once per tier it lists; ops are
  multi-tier):**
  | tier | ops listing this tier |
  |---|---|
  | native_arx_only | 141 |
  | objectdbx_capable | 131 |
  | managed_also | 117 |
  | accoreconsole_lisp_also | 31 |

Interpretation: ~50% of ops are native-only as their primary tier (the genuine
"why we need native C++" surface), but ~41% (117/284) also have a managed-.NET
equivalent and ~46% an ObjectDBX-capable path — i.e. the native module's
*unique* value concentrates in the 141 native_arx_only ops (custom objects,
persistent reactors, queryX/object-lifecycle overrules, interactive editor input,
jigs), not in the entity/database CRUD that managed already covers.

---

## Bottom line for the requester

1. **Structurally complete: YES** — all 6 slices have every required section,
   284 well-formed op rows, 0 empty/malformed tier cells, 0 unmapped tiers.
2. **Host-less contradiction (a): RESOLVED, no real conflict.** Side-DB DWG
   read/write = **`objectdbx_capable`, hosted inside accoreconsole** (license-
   clean). `native_C++_only` is correct ONLY for a standalone RealDWG exe, which
   is out of license scope. acdb-core already states this verbatim; the two delta
   tables should add the annotation. **RealDWG license = the real boundary — Paul
   decision.**
3. **Overrule contradiction (b): editor-delta `managed_also` is an over-
   generalization.** Correct = per-op split: entity-level/base overrules
   `managed_also`; queryX + object-lifecycle + custom-authoring overrules
   `native_arx_only`. reactors-overrules is authoritative.
4. **Transient-vs-persistent (c): persistent = native_arx_only (firm,
   `dbObject.h:384`); transient = managed_also for mainstream, but long-
   transaction/linker/low-level Rx-event reactors are native_arx_only even though
   transient.** editor-delta's flat "transient = managed_also" is imprecise.
5. **ZERO/near-zero families that still need research:**
   - **constraints_associativity — ZERO** (~60 `AcDbAssoc*`/constraint/assoc-array
     headers exist; geometric+dimensional constraints + associative arrays
     entirely unresearched). **Highest-value gap.**
   - **com_activex — ZERO automation** (axdb/OPM headers exist; Application/Document
     automation + OPM unresearched).
   - **ui_customization — 2 ops only** (ribbon=0, tool-palette population=0, CUI
     edit=0; `AcTc*`/`acui*`/`adui*` headers all present).
   - **brep_solids — PARTIAL** (3dSolid+mass-props covered; AcBr topology +
     AcDbSubentId subentities unresearched; `AcDrawBridge.lib` present).
6. **Total: 284 ops** — native_arx_only 141 / objectdbx_capable 114 / managed_also
   13 / accoreconsole_lisp_also 16 (primary-tier).
