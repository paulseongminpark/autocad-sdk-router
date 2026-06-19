# Native ObjectARX 2027 — Synthesis Index (executive)

Compact map over the unified operation catalog
(`config/autocad_native_arx_operation_catalog.json`). Mechanical merge of the
10 research slices with the `_AUDIT.md` tier rulings applied. **No full op dump
here — see the catalog JSON for every row.**

- **Total operations: 480** (479 distinct native op rows merged from 10 slices +
  1 injected entry for the existing managed `inspect.database.summary`).
- **0 cross-slice op_id collisions; 0 unmapped family.**
- **By engine tier:** `native_arx_only` **221** · `objectdbx_capable` **198** ·
  `managed_also` **45** · `accoreconsole_lisp_also` **16**.
- **Audit tier overrides applied: 30** (28 overrules+reactors down/up per rulings
  2 & 3; ctx normalized to `hostless_dbx_in_accoreconsole` per ruling 1).
- **Already-implemented managed ops flagged: 4** (`inspect.database.summary`,
  `write.layer.create`, `write.entity.line`, `write.xrecord.set`).

---

## 1. FAMILY × TIER MATRIX (18 families × 4 tiers)

| family | native_arx_only | objectdbx_capable | managed_also | lisp_also | total |
|---|---:|---:|---:|---:|---:|
| runtime_commands | 23 | 1 | 0 | 2 | 26 |
| objectdbx_database | 3 | 17 | 1 | 0 | 21 |
| symbol_tables_dictionaries | 1 | 15 | 0 | 0 | 16 |
| entities | 0 | 56 | 0 | 0 | 56 |
| blocks_xrefs_clone | 1 | 4 | 0 | 0 | 5 |
| geometry_kernel | 16 | 9 | 0 | 0 | 25 |
| brep_solids | 10 | 44 | 0 | 0 | 54 |
| graphics_system | 9 | 0 | 0 | 0 | 9 |
| editor_input | 13 | 0 | 4 | 10 | 27 |
| reactors_events | 9 | 0 | 13 | 0 | 22 |
| custom_objects_protocols | 41 | 5 | 16 | 1 | 63 |
| constraints_associativity | 19 | 39 | 0 | 0 | 58 |
| layouts_plot_publish | 0 | 0 | 2 | 0 | 2 |
| ui_customization | 37 | 0 | 2 | 0 | 39 |
| com_activex | 38 | 8 | 3 | 0 | 49 |
| autolisp_visual_lisp | 0 | 0 | 0 | 0 | 0 |
| core_console | 0 | 0 | 0 | 0 | 0 |
| active_document_write_original | 1 | 0 | 4 | 3 | 8 |
| **TOTAL** | **221** | **198** | **45** | **16** | **480** |

> `autolisp_visual_lisp` and `core_console` show 0 op rows by design — the audit
> rules them **cross-cut tiers** (`accoreconsole_lisp_also` / execution_context),
> not standalone op families. Their reach is the 16 lisp-tier + the hostless
> execution_context rows, not dedicated ops.

---

## 2. NATIVE-ONLY BUILD SET (221 ops — the justification for the C++ module)

Grouped by capability cluster (count :: 3-6 highest-value op_ids). These are the
operations with **no managed-.NET and no headless-LISP equivalent** — they only
exist if we build the native ARX/DBX module.

| cluster | ops | highest-value op_ids |
|---|---:|---|
| **Custom entities / DBObjects** (authoring, filer, subentity paths, custom class decl/define) | 40 | `extend.customclass.declare`, `extend.customclass.define`, `extend.customclass.define_cons`, `edit.subentity.add_paths`, `inspect.subentity.class_id`, `extend.opm.dialog_property` |
| **UI palettes / status-bar / menus** (tool palettes, CAdUi palette sets, panes, tray, classic menus, command reg) | 36 | `editor.toolpalette.create`, `editor.toolpaletteset.add_palette`, `editor.palette.create_dockable`, `editor.statusbar.add_pane`, `editor.tray.add_item`, `editor.menu.add_item` |
| **Runtime / command registration / module loading** (ARX entrypoints, command stack, ADS symbols, demand-load) | 22 | `command.register.define`, `module.command.register_auto`, `module.app.accessor`, `module.command.flags`, `module.ads.register_symbol`, `module.command.lookup` |
| **COM automation + OPM glue** (IUnknown↔ObjectId, doc lock via COM, app/win accessors, objectref hold) | 21 | `automate.com.objectid_from_iunknown`, `automate.com.lock_document`, `automate.com.get_for_command`, `automate.com.hold_objectref`, `automate.com.get_winapp`, `automate.com.entity_helpers` |
| **Constraints / associativity native bits** (assoc-eval callbacks, assoc-surface action bodies, global callbacks) | 19 | `config.assoceval.callback`, `config.constraint.globalCallback`, `define.assocsurface.loft`, `define.assocsurface.blend`, `define.assocsurface.extrude`, `define.assocsurface.fillet` |
| **OPM / AcRxProperty** (dynamic property definition, category map, dispid, enum) | 17 | `extend.opm.define_property`, `extend.opm.define_property2`, `extend.opm.map_category`, `extend.opm.enum_property`, `extend.opm.get_dispid`, `extend.opm.get_manager` |
| **Geometry kernel native** (AcGe in-proc curve eval/intersect/sample/closest — no managed AcGe) | 16 | `compute.geometry.curve.intersect`, `compute.geometry.curve.eval`, `compute.geometry.curve.closest`, `compute.geometry.curve.sample`, `compute.geometry.compositecurve`, `compute.geometry.circarc` |
| **Interactive editor / jig / live input** (point/angle/dist/corner acquisition, command queue post, editor events) | 13 | `input.get.point`, `input.get.angle`, `input.get.corner`, `input.get.dist`, `command.queue.post`, `editor.react.events` |
| **BRep subentity authoring** (AcBr face/edge traversal, subent transform/markers/extents) | 8 | `inspect.subentity.path_at_marker`, `inspect.subentity.markers_at_path`, `edit.subentity.transform`, `edit.subentity.delete_paths`, `inspect.subentity.geom_extents`, `inspect.subentity.color` |
| **Persistent / low-level reactors** (persistent, long-transaction, linker, AcRxEvent — no managed surface) | 8 | `react.persistent.attach`, `react.persistent.detach`, `react.longtx.attach`, `react.linker.attach`, `react.linker.monitor`, `react.longtx.monitor` |
| **Custom graphics / worldDraw** (AcGi custom drawable, viewport geom, face data, grips render) | 7 | `render.drawable.def`, `render.draw.viewportgeom`, `render.facedata.attach`, `render.context.query`, `inspect.entity.grips`, `render.polyline.helper` |
| **Protocol extension / queryX** (AcRxProtocolReactor / queryX overrule — extension protocol hook) | 2 | `overrule.queryx.install`, `extend.customclass.define_nocons` |
| **Object enablers** (DBX module entrypoint + class registration for headless enabling) | 2 | `extend.object_enabler.register_classes`, `extend.module.entrypoint` |
| **Lifecycle overrules** (AcDbObjectOverrule open/close/erase/clone + dimstyle overrule) | 2 | `overrule.object.install`, `overrule.dimstyle.install` |
| **residual native singletons** | 6 | `transform.database.deep_clone`, `transform.database.wblock_clone`, `react.config.disable_namespace`, `command.invoke.coroutine`, `extend.property.overrule`, `transaction.manager.start` |

**Total native-only clustered: 221.** The native module's *unique* value lives in
the top 4 clusters (custom entities/objects, UI palettes+menus, runtime/command
loading, COM+OPM glue) — 119 of 221 ops.

---

## 3. ALREADY-COVERED (skip in C++ — reachable via the existing managed plane)

45 `managed_also` ops already have a .NET path; the 4 marked
`already_implemented_managed` are live in today's `CadJobRunner`.

| cluster | ops | notes |
|---|---:|---|
| Mainstream transient reactors (object/entity/database/editor/docmanager) | 13 | `react.editor.*`, `react.database.*`, `react.docmanager.*` — overridden to managed_also per audit ruling 3 |
| Base + entity-level overrules (Drawable/Geometry/Transform/Osnap/Grip/Properties/Visibility/Subentity/Highlight) | 16 | `overrule.*.install` family + `overrule.global.enable/install/remove/query.has/applicable` — audit ruling 2 |
| Active-document ops (current/lock/new/syncopen) | 4 | `doc.current`, `doc.lock`, `doc.new`, `doc.syncopen` |
| Selection-set + alerts | 4 | `select.ss.addremove`, `select.ss.count`, `select.ss.free`, `prompt.alert` |
| COM app/document/sendcommand | 3 | `automate.com.get_app`, `automate.com.get_document`, `automate.com.send_command` |
| Plot config + engine | 2 | `plot.config.settings`, `plot.engine.run` |
| Palette create + status-bar pane (basic) | 2 | `editor.palette.create`, `editor.statusbar.pane` |
| **Live in CadJobRunner today** | 4 | `inspect.database.summary`, `write.layer.create`, `write.entity.line`, `write.xrecord.set` |

Plus the **198 `objectdbx_capable`** ops (entities 56, brep 44, constraints 39,
db 17, symtab 15, geometry 9, com 8, custom-obj 5, blocks 4, runtime 1) — all
reachable **host-less inside accoreconsole** via the managed/DBX plane without C++.
This is the bulk CRUD surface; the managed plane should keep owning it.

---

## 4. ACCORECONSOLE / LISP-REACHABLE (16 ops — headless, no C++ needed)

| cluster | ops | op_ids |
|---|---:|---|
| Interactive prompt/select primitives (headless-scriptable) | 10 | `input.get.int/keyword/real/string`, `input.initget.constrain`, `prompt.print`, `select.entity.pick`, `select.pickfirst.get/set`, `select.ssget.interactive` |
| Command invocation (sync/sendstring) | 3 | `command.invoke.sync`, `command.invoke.sync.resbuf`, `doc.sendstring` |
| Object-enabler demand register | 1 | `extend.object_enabler.demand_register` |
| Module load (acad.rx / lisp) | 2 | `module.load.acad_rx`, `module.load.lisp` |

These are doable today with `.scr` / AutoLISP through accoreconsole. Wire them
through the existing CAD router's accoreconsole route rather than the C++ module.

---

## 5. RECOMMENDED C++ BUILD PRIORITY (ordered)

| pri | cluster(s) | rationale |
|---|---|---|
| **P1** | Custom entities/DBObjects + Object enablers + Protocol extension/queryX (44 ops) | The core reason native exists: author custom `AcDbEntity`/`AcDbObject` classes, filers, subentity paths, and the DBX object-enabler so derived drawings carry first-class typed objects (not proxies). Everything downstream — OPM, custom graphics, persistent reactors — depends on a real custom class existing first. |
| **P2** | OPM / AcRxProperty + Lifecycle overrules + Custom graphics/worldDraw (26 ops) | Make the custom objects *useful in-session*: expose properties to the Properties palette (OPM), control open/close/clone lifecycle (`AcDbObjectOverrule`), and render via `worldDraw`. Highest leverage per op once P1 lands. |
| **P3** | Interactive editor / jig / live input (13 ops) | Native point/angle/dist acquisition + jigs — the only way to drive *interactive* authoring of the new entities. No managed-headless equivalent; required for any attended workflow. |
| **P4** | Persistent / low-level reactors + Constraints/associativity native callbacks (27 ops) | Persistent reactors (write ObjectId links into the DWG) + assoc-eval/action-body callbacks. Needed for self-maintaining associative derived geometry, but only after objects exist (P1) and can be edited (P3). |
| **P5** | UI palettes / status-bar / menus + COM+OPM automation glue (57 ops) | Largest cluster but lowest unique-value-per-op: most are session chrome (tool palettes, panes, tray, menus) and COM IUnknown↔ObjectId plumbing. Build last; much is optional polish and partially approximable via managed `Autodesk.Windows` + CUIx. |

Geometry-kernel-native (16) and BRep-subentity (8) ride along with P1–P2 where a
specific op is needed (e.g. subentity authoring is part of P1; AcGe curve eval is
pulled in by whatever consumer needs it) rather than as standalone phases.

---

## 6. RESIDUAL GAPS / UNCERTAINTIES FOR THE LEAD

1. **RealDWG license boundary (audit ruling 1)** is the real constraint, not an
   engine capability. No op row is tagged standalone-exe; all DWG I/O is
   `objectdbx_capable` + `hostless_dbx_in_accoreconsole`. Confirm the module ships
   **as an `.arx` loaded into accoreconsole**, never as a standalone RealDWG exe.
2. **Cluster boundaries are heuristic.** A few ops land by keyword, not by hand
   (e.g. `write.entity.line` → `geometry_kernel` family, command-registration ops
   folded into the UI/menu cluster). Family/tier on each row is correct; only the
   *cluster* grouping in §2 is a convenience view. Re-cluster if a phase plan needs
   exact membership.
3. **`inspect.database.summary` is synthetic** — injected as `managed_also` /
   `existing_managed_plane` because it has no native op_id (closest native is
   `inspect.database.summaryinfo`, which is DWG SummaryInfo metadata, a different
   thing). Confirm you want it counted in the catalog total (drives 480 vs 479).
4. **`managed_also = 45`** assumes the audit's reactor/overrule downgrades. If the
   eventual managed plane cannot actually reach a given transient reactor /
   entity-overrule, those flip back to `native_arx_only` and P5 grows. Verify the
   managed CadJobRunner can host overrules/reactors before treating them as covered.
5. **2 families (autolisp, core_console) hold 0 ops** by the cross-cut ruling. If
   you want them represented as first-class ops (e.g. explicit `lisp.*` /
   `console.*` entries), that is a deliberate schema extension, not a gap to fill
   from existing slices.
