## Slice: editor-delta

ObjectARX 2027 native C++ EDITOR/interaction surface + the authoritative
native-vs-managed-vs-accoreconsole capability DELTA TABLE.

**Grounding rule:** every row below is backed by a doc or header read in this
research session. Citations are either local SDK headers (`C:\ObjectARX 2027\inc\<file>:<line>`,
read via grep/sed this session) or Autodesk Help docs (GUID + cloudhelp URL,
retrieved via the `autodesk-product-help` MCP this session). Items I could not
confirm against a read source are tagged `unverified`.

**Engine-tier vocabulary:** `native_arx_only` | `objectdbx_capable` | `managed_also` | `accoreconsole_lisp_also`.

**Key environment facts (verified this session):**
- ObjectARX SDK 2027 is the supported SDK for AutoCAD 2027; .NET runtime for 2027 is **10.0**. (MCP: "About Application Compatibility", GUID-D54B0935 — SDK/.NET support matrix.)
- Managed wrapper classes are provided for **most** ObjectARX classes and expose database functionality, the **command prompt, drawing editor, and publishing/plotting** UI; managed is **Windows-only** and **not in AutoCAD LT**. (MCP: "About .NET Managed Applications", GUID-3A5E2EE7.)
- ObjectARX dev is **not supported in AutoCAD LT** and not on Web. (MCP: "Related Developer References", GUID-7884190F.)
- Custom objects and object enablers are created by **ObjectARX** applications. (MCP: "About Custom Objects and Proxy Objects", GUID-6515268E.)

---

### Operation catalog (PART 1)

Native EDITOR / interaction surface. `dwg_persisted?` = does the op, by itself, change persistent DWG content. `execution_context`: `in_process_host` (must run inside the running AutoCAD editor via ARX load / NETLOAD), `host_session` (session-context, MDI-wide), `objectdbx_hostless` (works in an ObjectDBX/host-less process with no editor).

| proposed_op_id | native API | engine_tier | what it does | key inputs | key outputs | dwg_persisted? | execution_context | citation |
|---|---|---|---|---|---|---|---|---|
| `command.invoke.sync` | `acedCommandS(int rtype, ...)` | `accoreconsole_lisp_also` | Runs a *full* AutoCAD command synchronously via a private command-line processor initialized at the "Command:" prompt; replaces the now-disabled `acedCommand`. | RT-coded varargs (e.g. `RTSTR`,`RT3DPOINT`,`RTLONG`), terminated by `RTNONE`/0 | `int` status (`RTNORM`=success) | yes (if the command edits) | in_process_host | `acedCmdNF.h:46`; `acedads.h:70` (`acedCommand` #defined to "MustSwitchTo_acedCommandC_or_acedCommandS") |
| `command.invoke.sync.resbuf` | `acedCmdS(const resbuf* rb, bool, AcApDocument*)` | `accoreconsole_lisp_also` | Same as `acedCommandS` but takes a resbuf chain instead of varargs. | resbuf chain | `int` status | yes | in_process_host | `acedCmdNF.h:50-53` |
| `command.invoke.coroutine` | `acedCommandC(AcEdCoroutineCallback, void*, int rtype, ...)` / `acedCmdC(...)` | `native_arx_only` | Coroutine/fiber-based command invocation: fires a callback when the issued command pauses for input, enabling non-blocking command chaining. Replaces `acedCmd`. | callback fn ptr, return-parm ptr, RT varargs / resbuf | `int` status | yes | in_process_host | `acedCmdNF.h:146-151`; `acedFiberWorld()` `acedCmdNF.h:31`; `acedads.h:71` (`acedCmd` disabled) |
| `command.queue.post` | `acedPostCommand` / `acedPostCommandPrompt()` | `native_arx_only` | Queues a command string to run when the editor is next idle (cannot run mid-command); `acedPostCommandPrompt` reposts the last prompt. | command string | `void` | yes (if cmd edits) | in_process_host | `aced.h:175` (`acedPostCommandPrompt`); `acedads.h:70-71` context. `acedPostCommand` token form `unverified` (exact signature not read) |
| `command.menu.invoke` | `acedMenuCmd(const ACHAR*)` | `native_arx_only` | Issues a menu/macro command string. | menu cmd string | `int` | maybe | in_process_host | `acedads.h:214` |
| `command.register.define` | `acedRegCmd` + `ACRX_CMD_*` flags | `native_arx_only` | Registers a new command with group/flags so it behaves like a native command (referenced via UNDEFINE/REDEFINE doc). Flags: `ACRX_CMD_MODAL`(0x0), `_TRANSPARENT`(0x1), `_USEPICKSET`(0x2), `_REDRAW`(0x4), `_NOPAPERSPACE`(0x40), `_DOCREADLOCK`(0x80000), `_DOCEXCLUSIVELOCK`(0x100000), `_SESSION`(0x200000), `_INTERRUPTIBLE`(0x400000). | cmd group/name/flags, fn ptr | registration | no | in_process_host | `accmd-defs.h:31-72`; MCP "UNDEFINE (Command)" (`acedRegCmd`, group.command syntax) |
| `prompt.print` | `acutPrintf` / `acedPrompt(const ACHAR*)` | `accoreconsole_lisp_also` | Writes text to the command line / prompt area. | format/string | `int`/`void` | no | in_process_host | `acedads.h:206` (`acedPrompt`); `acutPrintf` in acedads.h header set (`unverified` exact line) |
| `prompt.alert` | `acedAlert(const ACHAR*)` | `managed_also` | Modal alert dialog. | string | `int` | no | in_process_host | `acedads.h:216` |
| `input.get.point` | `acedGetPoint(const ads_point, const ACHAR* prompt, ads_point result)` | `native_arx_only` | Interactive point pick (rubber-band from optional base pt). | base pt, prompt | `ads_point`, status | no | in_process_host | `acedads.h:223` |
| `input.get.corner` | `acedGetCorner(const ads_point, const ACHAR*, ads_point)` | `native_arx_only` | Interactive corner (rubber-band rectangle). | base pt, prompt | corner pt | no | in_process_host | `acedads.h:220` |
| `input.get.dist` | `acedGetDist(const ads_point, const ACHAR*, double*)` | `native_arx_only` | Interactive distance. | base pt, prompt | double | no | in_process_host | `acedads.h:221` |
| `input.get.angle` | `acedGetAngle(const ads_point, const ACHAR*, double*)` / `acedGetOrient(...)` | `native_arx_only` | Interactive angle / orientation (radians). | base pt, prompt | double | no | in_process_host | `acedads.h:219`,`acedads.h` GetOrient line |
| `input.get.real` | `acedGetReal(const ACHAR*, double*)` | `accoreconsole_lisp_also` | Prompt for a real. | prompt | double | no | in_process_host | `acedads.h:231` |
| `input.get.int` | `acedGetInt(const ACHAR*, int*)` | `accoreconsole_lisp_also` | Prompt for an integer (16-bit overload deprecated; wider overloads exist). | prompt | int | no | in_process_host | `acedads.h:226` |
| `input.get.string` | `acedGetString(int cronly, const ACHAR* prompt, ACHAR* result, size_t)` | `accoreconsole_lisp_also` | Prompt for a string. | cronly flag, prompt, buf | string | no | in_process_host | `acedads.h:209` |
| `input.get.keyword` | `acedGetKword(const ACHAR*, ACHAR*, size_t)` | `accoreconsole_lisp_also` | Prompt for a keyword (paired with `acedInitGet`). | prompt, buf | keyword string | no | in_process_host | `acedads.h:228` |
| `input.initget.constrain` | `acedInitGet(int val, const ACHAR* kwl)` | `accoreconsole_lisp_also` | Sets bit-coded constraints + keyword list for the *next* getXXX/entsel (e.g. 1=no null, 2=no zero, 4=no negative). Mirrors LISP `initget`. | bits, keyword list | — | no | in_process_host | `acedads.h:194`; MCP "About Controlling User-Input Function Conditions", GUID-44553A7D (bit semantics) |
| `select.entity.pick` | `acedEntSel(const ACHAR*, ads_name, ads_point)` | `accoreconsole_lisp_also` | Single-entity pick + pick point. | prompt | ename, pt | no | in_process_host | `acedads.h:111-115` |
| `select.nentity.pick` | `acedNEntSel` / `acedNEntSelP` | `native_arx_only` | Nested entity pick, returns xform/containers; `...P` adds matrix. | prompt | nested ename, matrix | no | in_process_host | `acedads.h:118-121` |
| `select.ssget.interactive` | `acedSSGet(const ACHAR* str, const void* pt1, const void* pt2, const resbuf* filter, ads_name ss)` | `accoreconsole_lisp_also` | Builds a selection set. `str` selects mode: `"W"`/`"C"` window/crossing, `"WP"`/`"CP"` window/crossing polygon, `"F"` fence, `"P"` previous, `"L"` last, `"I"` implied/pickfirst, `"X"` whole-DB filter scan. `filter` = DXF-coded resbuf (group 0 type, 8 layer, 62 color, -4 logical operators). | mode str, pts, DXF filter | `ads_name` ss | no | in_process_host (`"X"` mode is DB-scan, also reachable host-less conceptually) | `acedads.h:125-127`; MCP "About Selection Set Filter Lists", GUID-7BE77062 (modes/filters); "About Logical Grouping", GUID-5CB54129 (-4 operators) |
| `select.ssget.preview` | `acedSSGet(..., AcSelectionPreview*)` | `native_arx_only` | C++ overload with selection-preview highlight object. | + preview obj | ss | no | in_process_host | `acedads.h:129-131` |
| `select.pickfirst.get` | `acedSSGetFirst(resbuf** gset, resbuf** pset)` | `accoreconsole_lisp_also` | Reads the pickfirst (noun-verb) gripped/selected set. | — | grip set, pick set | no | in_process_host | `acedads.h:133`; MCP "ssgetfirst", GUID-F18CB64C |
| `select.pickfirst.set` | `acedSSSetFirst(const ads_name pset, const ads_name)` | `accoreconsole_lisp_also` | Sets the gripped/selected set. | pickset | — | no | in_process_host | `acedads.h:134` |
| `select.ss.count` | `acedSSLength(const ads_name, Adesk::Int32*)` | `managed_also` | Member count of a selection set. | ss | length | no | in_process_host | `acedads.h:137` |
| `select.ss.free` | `acedSSFree(const ads_name)` | `managed_also` | Releases a selection set. | ss | status | no | in_process_host | `acedads.h:135` |
| `select.ss.addremove` | `acedSSAdd` / `acedSSDel` / `acedSSName` | `managed_also` | Add/remove/index entities in a selection set. | ss, ename, idx | ename/status | no | in_process_host | listed in acedads.h editor-fn block (`acedSSAdd/SSDel/SSName`; exact lines `unverified`) |
| `interact.jig.run` | `AcEdJig` (`public AcRxObject`): `drag()`, virtual `sampler()`, virtual `update()`, virtual `entity()`, `append()` | `native_arx_only` | Interactive "jig": drag loop that re-samples user input, updates a temp entity's geometry each frame, then appends it to the DB. `sampler()` calls `acquirePoint/acquireAngle/acquireDist/acquireString`; returns `DragStatus`. | jig subclass, prompt counters | `AcDbObjectId` (on append), `DragStatus` | yes (on `append()`) | in_process_host | `dbjig.h:36,66,104-123,131` |
| `interact.jig.acquire` | `AcEdJig::acquirePoint/acquireAngle/acquireDist/acquireString` | `native_arx_only` | The per-frame value acquisition inside `sampler()`. | base pt (opt) | value + DragStatus | no | in_process_host | `dbjig.h:117-123` |
| `interact.inputpoint.monitor` | `AcEdInputPointManager::addPointMonitor(AcEdInputPointMonitor*)`; `AcEdInputPointMonitor::monitorInputPoint(...)` | `native_arx_only` | Registers a monitor invoked on every input-point event (cursor move/osnap) for live feedback/HUD — observe without consuming input. | monitor subclass | callback stream | no | in_process_host | `acedinpt.h:38-86,508-578` |
| `interact.inputpoint.filter` | `AcEdInputPointManager::registerPointFilter(AcEdInputPointFilter*)`; `AcEdInputPointFilter::*` | `native_arx_only` | Registers a filter that can *modify/replace* the computed input point (custom snapping). | filter subclass | filtered point | no | in_process_host | `acedinpt.h:53-69,387-497` |
| `interact.inputcontext.react` | `AcEdInputPointManager::addInputContextReactor(AcEdInputContextReactor*)` | `native_arx_only` | Reactor for input-context (prompt/drag) state changes. | reactor subclass | callbacks | no | in_process_host | `acedinpt.h:97-105,595-621` |
| `editor.react.events` | `AcEditorReactor : public AcRxEventReactor` | `native_arx_only` | Editor-wide event reactor (command start/end, sysvar change, mouse, lisp, etc.) — a *transient*, non-persistent reactor. | reactor subclass | callbacks | no | in_process_host | `aced.h:376`; `rxevent.h:43` |
| `editor.palette.create` | `CAdUiPaletteSet::AddPalette(CAdUiPalette*)` (+ `acedGetAcadDockCmdBars`/host) | `managed_also` | Creates/docks a modeless palette set (Properties-style dockable pane) hosting custom UI. | palette objects | palette set handle | no | in_process_host | `aduiPaletteSet.h:64,163`; `aduiPalette.h:34` |
| `editor.statusbar.pane` | `AcPane : AcStatusBarItem`; `AcTrayItem`; `AcStatusBarMenuItem` | `managed_also` | Adds a status-bar pane / tray icon / status-bar menu item. | item subclass | status-bar item | no | in_process_host | `AcStatusBar.h:34,121,309,481` |
| `editor.menu.context` | shortcut/context menu via `AcRxObject`-derived menu hooks (CUI / `AdMenuBar.h`) | `native_arx_only` | Adds context/shortcut menu entries programmatically. | menu defn | menu item | no | in_process_host | header `AdMenuBar.h` present; exact menu API `unverified` (CUI route is the documented path, MCP "Customization Guide Reference" GUID-91E01021) |
| `doc.lock` | `AcApDocManager::lockDocument(AcApDocument*, DocLockMode)` / `unlockDocument` | `managed_also` | Locks the document for write before editing from a non-command/session context. `DocLockMode`: `kNone`=0,`kAutoWrite`=0x1,`kNotLocked`=0x2,`kProtectedAutoWrite`=0x14, plus shared/exclusive. | doc ptr, mode | status | no (lock only) | host_session | `acdocman.h:278-283`; `AcApDocLockmode.h:25-29` |
| `doc.current` | `AcApDocManager::curDocument()` / `acDocManager` / `curDoc()` | `managed_also` | Gets/sets the current-context document (MDI). | — | `AcApDocument*` | no | host_session | `acdocman.h:271,471` |
| `doc.sendstring` | `AcApDocManager::sendStringToExecute(AcApDocument*, ...)` | `accoreconsole_lisp_also` | Queues a command string into a target document's command stream (cross-document automation). | doc, string | status | yes (if edits) | host_session | `acdocman.h:322,413` |
| `doc.new` | `AcApDocManager::appContextNewDocument(const ACHAR* template)` | `managed_also` | Creates a new MDI document from a template in app context. | template name | new doc | yes (new file) | host_session | `acdocman.h:332` |
| `doc.syncopen` | `acedSyncFileOpen(const ACHAR*, const wchar_t* pwd)` | `managed_also` | Synchronously opens a DWG into the editor. | path, pwd | status | no (open) | host_session | `aced.h` (acedSyncFileOpen decl, ~line 182) |
| `plot.engine.run` | `AcPlPlotEngine`: `beginPlot/beginDocument/beginPage/endPage/endDocument/endPlot` (created via `AcPlPlotFactory`) | `managed_also` | Drives the full plot/publish pipeline (also preview engine). Operates on `AcPlPlotInfo`/`AcPlPlotPageInfo`. | plot info, progress | plotted output / preview | no (produces file/print) | in_process_host (publish/DSD can be host-less via core) | `AcPlPlotEngine.h:62-79`; `AcPlPlotInfo.h`, `AcPlPlotFactory.h` present |
| `plot.config.settings` | `AcDbPlotSettings` / `AcPlPlotConfig` / `AcPlPlotConfigMgr` | `managed_also` | Reads/writes named page setups / plot configs; `AcDbPlotSettings` is a DB object so it persists. | settings | config | yes (`AcDbPlotSettings` in DWG) | objectdbx_capable (settings object) / in_process_host (engine) | `AcPlPlotConfig.h`, `AcPlPlotConfigMgr.h` present; `AcDbPlotSettings` is a dbents object (`unverified` exact line) |

---

### DELTA TABLE (PART 2)

For each capability family: tier ∈ {`native_C++_only` | `managed_also_equivalent` | `accoreconsole_lisp_reachable`} + WHY + citation. Where a family splits, the split is called out explicitly.

| capability_family | tier | why | citation |
|---|---|---|---|
| **Database read/write — host-less** | `native_C++_only` | A standalone process that opens/saves DWG with no running AutoCAD requires linking ObjectDBX (`AcDbDatabase::readDwgFile`/`saveAs`, `AcDbHostApplicationServices`, ObjectDBX startup/shutdown). The managed API runs **in-process** to AutoCAD; **RealDWG (the redistributable host-less .NET DWG toolkit) is EXCLUDED from our license**, so host-less DWG I/O is native ObjectDBX only. (accoreconsole gives host-less DWG read/write but only via LISP/script + console, not a linkable library.) | `dbmain.h:236,246,494,516-526`; `dbapserv.h:108-115`; RealDWG excluded = task ground-fact |
| **Database read/write — in host** | `managed_also_equivalent` | Inside a running editor, managed `Database`/`Transaction`/`DBObject` fully wrap the ObjectARX DB layer. | MCP "About .NET Managed Applications", GUID-3A5E2EE7 ("read and write drawing format (DWG) files") |
| **Entity CRUD (standard types)** | `managed_also_equivalent` | Managed wraps `AcDbEntity`/all standard entity classes; "managed classes implement database functionality." Also fully reachable host-less via ObjectDBX and via LISP `entmake`/`entmod` in accoreconsole. | MCP GUID-3A5E2EE7; MCP "IAcadEntity Interface" GUID-FCA7867D ("IAcadEntity exposes AcDbEntity functionality"); `dbmain.h` AcDbEntity |
| **AcGe geometry (math library)** | `managed_also_equivalent` | The `Geometry` managed namespace mirrors `AcGe*`. Pure math, no editor; works host-less and is header-only-ish in native. | MCP GUID-3A5E2EE7 (managed wraps "most of the classes"); AcGe headers present in SDK |
| **AcGi custom rendering (worldDraw on YOUR entity)** | `native_C++_only` | `AcGiDrawable::worldDraw/viewportDraw` are `ADESK_SEALED`; the real override points are the **protected pure-virtual** `subWorldDraw`/`subViewportDraw`/`subSetAttributes`, overridden only by C++ subclasses of `AcDbEntity`/`AcGiDrawable`. Managed cannot subclass a custom DB entity at this level (see custom entities). Custom *transient* graphics are partially reachable, but per-entity render is native. | `drawable.h:162-205`; `dbObject.h:575-577` (`subWorldDraw` override) |
| **Custom entities / custom DB objects** | `native_C++_only` | Custom objects are "created by an ObjectARX application." Managed explicitly cannot define new persistent custom AcDb classes (the documented "essentially all functionality EXCEPT custom objects" boundary). | MCP "About Custom Objects and Proxy Objects", GUID-6515268E; MCP GUID-3A5E2EE7 (managed = "most" classes); task ground-fact |
| **Object enablers** | `native_C++_only` | An object enabler is an ObjectARX module (`.dbx`) that teaches the host to instantiate a vendor's custom object; it is built on the native custom-object framework. | MCP "About Custom Objects and Proxy Objects", GUID-6515268E |
| **Transient reactors (editor/db events)** | `managed_also_equivalent` | Editor and DB event notifications are surfaced as managed `.NET` events (`Editor`, `Database`, `Document` events) wrapping `AcEditorReactor`/`AcDbDatabaseReactor`. | `aced.h:376` (`AcEditorReactor`); `dbmain.h:44-49`; MCP GUID-3A5E2EE7 ("access to ... the drawing editor") |
| **PERSISTENT reactors** | `native_C++_only` | A reactor that is *serialized with the object* and survives save/reload (e.g. `AcDbObjectReactor` persistent attachment / `addPersistentReactor`) requires a native custom reactor object; managed events are process-transient only. | `dbObject.h:28` (`AcDbObjectReactor`); MCP "Related Developer References", GUID-7884190F ("reactor functionality is implemented through ObjectARX") |
| **Overrules** | `managed_also_equivalent` | `AcRxOverrule` family (`AcDbOsnapOverrule`, `AcDbTransformOverrule`, `AcDbGripOverrule`, `AcDbVisibilityOverrule`, `AcDbGeometryOverrule`, `AcGiDrawableOverrule`) has managed equivalents (`Autodesk.AutoCAD.Runtime` Overrule classes). Global toggle `AcRxOverrule::setIsOverruling`. **Caveat:** `AcGiDrawableOverrule::worldDraw` overrule of rendering still ultimately routes to `subWorldDraw` — overruling *draw* of an existing entity is managed-reachable, but defining a *new custom entity's* draw is native. | `dbentityoverrule.h:77,173,277,879,934`; `rxoverrule.h:121`; `drawable.h:222-277` |
| **Jigs / interactive input** | `managed_also_equivalent` | Managed `Jig`/`EntityJig`/`DrawJig` and `PromptXxxOptions` wrap `AcEdJig` + the `acedGetXxx` family. **Not reachable from accoreconsole** (no interactive editor). | `dbjig.h:36,104-131` (native); MCP GUID-3A5E2EE7 ("access to ... the drawing editor") |
| **Input point monitor / filter** | `native_C++_only` (monitor partially managed) | `AcEdInputPointMonitor` exists in managed form for some scenarios, but `AcEdInputPointFilter` (replacing the computed point / custom osnap) and `AcDbCustomOsnapMode` are native-centric. Mark filter native-only; monitor `managed_also` for read-only feedback. | `acedinpt.h:38-105,387-578`; monitor-managed claim `unverified` (not separately confirmed in docs read) |
| **Selection sets** | `accoreconsole_lisp_reachable` | `acedSSGet` + filters has direct managed (`Editor.SelectXxx`, `SelectionFilter`) AND LISP (`ssget`) equivalents; the `"X"` whole-DB filtered scan is the host-less-ish path. Interactive on-screen selection needs the editor (not pure accoreconsole batch). | `acedads.h:125-137`; MCP GUID-7BE77062, GUID-5CB54129; "ssgetfirst" GUID-F18CB64C |
| **Command invocation** | `accoreconsole_lisp_reachable` | `acedCommandS`/`acedCmdS` (and managed `Editor.Command`/`Document.SendStringToExecute`) and accoreconsole script `.scr`/LISP all issue commands. Native-only nuance: the **coroutine** form `acedCommandC` (callback on pause) is C++-only; managed `Command()` is the modern equivalent for most cases. `acedCommand`/`acedCmd` are **compile-disabled** in 2027 — must use the S/C forms. | `acedCmdNF.h:46,146`; `acedads.h:70-71` |
| **Editor / UI / palettes** | `managed_also_equivalent` | Managed exposes `PaletteSet`, status-bar `Pane`, and dialog UI ("access to user interface elements, including ... feature dialog boxes"). Native `CAdUiPaletteSet`/`AcPane` are the C++ equivalents. Not reachable from accoreconsole (no UI). | MCP GUID-3A5E2EE7; `aduiPaletteSet.h:163`; `AcStatusBar.h:121` |
| **Plotting / publishing** | `managed_also_equivalent` | Managed wraps the "publishing and plotting components" (`AcPlPlotEngine`/`AcPlPlotInfo` ↔ managed `PlotEngine`/`PlotInfo`); accoreconsole can also `-PLOT`/`PUBLISH`/`EXPORTPDF` via script. So this family is reachable in all three lanes; native gives lowest-level pipeline control. | MCP GUID-3A5E2EE7; `AcPlPlotEngine.h:62-79`; MCP "EXPORTPDF (Command)" GUID-E9CB4A20 (script-reachable) |
| **Xdata / xrecord / dictionaries** | `managed_also_equivalent` | `AcDbXrecord`, extension dictionaries, named-object dictionary, and xdata (`GetXData`/`SetXData`) are fully wrapped in managed and reachable host-less via ObjectDBX; LISP also reads xdata (group -3). The existing managed `write.xrecord.set` op already proves this lane. | MCP "IAcadEntity" GUID-FCA7867D (`GetXData/SetXData`); MCP GUID-7BE77062 (group -3 xdata); `dbdict.h` present; existing CadJobRunner `write.xrecord.set` (task fact) |

**Condensed verdict:**
- **Native C++ ONLY (no managed, no accoreconsole substitute):** host-less DWG library I/O (because RealDWG excluded), custom entities/objects, object enablers, persistent reactors, custom-entity `subWorldDraw` rendering, custom input-point *filters*/osnap, coroutine command invocation.
- **Managed .NET equivalent (do these in the existing CadJobRunner — no C++ needed):** in-host DB & entity CRUD, AcGe geometry, transient editor/DB event reactors, overrules, jigs/interactive input, palettes/status-bar UI, plotting/publishing pipeline, xdata/xrecord/dictionaries.
- **accoreconsole + LISP reachable (batch, no editor, no C++):** command invocation, selection sets (incl. `"X"` DB scan), basic prompts, plot/export via script, host-less DWG read/write through LISP entity functions.

---

### Classes & subsystems covered

- **Command invocation:** `acedCommandS`, `acedCmdS`, `acedCommandC`, `acedCmdC`, `acedFiberWorld`, `acedMenuCmd`, `acedRegCmd` + `ACRX_CMD_*` flag set, `acedPostCommandPrompt`. — `acedCmdNF.h:31,46,50,146`; `acedads.h:70-71,214`; `accmd-defs.h:31-74`; `aced.h:175`.
- **User input / prompts:** `acedGetPoint/GetCorner/GetDist/GetAngle/GetOrient/GetReal/GetInt/GetString/GetKword`, `acedInitGet`, `acedEntSel/NEntSel/NEntSelP`, `acedAlert`, `acedPrompt`. — `acedads.h:111-231`.
- **Input point pipeline:** `AcEdInputPointManager`, `AcEdInputPointMonitor::monitorInputPoint`, `AcEdInputPointFilter`, `AcEdInputContextReactor`, `AcEdInputPoint`, `AcDbCustomOsnapMode`. — `acedinpt.h:21-621`.
- **Selection sets:** `acedSSGet` (+`AcSelectionPreview` overload), `acedSSGetFirst/SSSetFirst/SSFree/SSLength/SSName/SSAdd/SSDel`, DXF filter lists, `-4` logical grouping. — `acedads.h:125-137`; MCP GUID-7BE77062 / GUID-5CB54129 / GUID-F18CB64C.
- **Interactive jig:** `AcEdJig` (`sampler/update/entity/append/drag/acquirePoint/acquireAngle/acquireDist/acquireString`, `enum DragStatus`). — `dbjig.h:36-137`.
- **Editor reactors:** `AcEditorReactor : AcRxEventReactor`; `AcDbDatabaseReactor`, `AcDbObjectReactor`, `AcDbEntityReactor`. — `aced.h:376`; `dbmain.h:44-49`; `dbObject.h:28`; `rxevent.h:43`.
- **Editor UI:** `CAdUiPaletteSet::AddPalette`, `CAdUiPalette`; `AcStatusBarItem`/`AcPane`/`AcTrayItem`/`AcStatusBarMenuItem`; menu via CUI/`AdMenuBar.h`. — `aduiPaletteSet.h:64,163`; `aduiPalette.h:34`; `AcStatusBar.h:34,121,309,481`.
- **Document management & locking:** `AcApDocManager` (`curDocument/lockDocument/unlockDocument/sendStringToExecute/appContextNewDocument`), `AcApDocLockmode::DocLockMode`, `curDoc()`, `acedSyncFileOpen`. — `acdocman.h:271-471`; `AcApDocLockmode.h:25-29`; `aced.h`.
- **Overrule framework:** `AcRxOverrule::setIsOverruling`; `AcDbOsnapOverrule`, `AcDbTransformOverrule`, `AcDbGripOverrule`, `AcDbVisibilityOverrule`, `AcDbGeometryOverrule`, `AcGiDrawableOverrule`. — `rxoverrule.h:121`; `dbentityoverrule.h:77-934`; `drawable.h:222-277`.
- **AcGi rendering:** `AcGiDrawable` (`worldDraw/viewportDraw` SEALED; `subWorldDraw/subViewportDraw/subSetAttributes` protected pure-virtual), `AcGiWorldDraw`, `AcGiViewportDraw`, `AcGiGeometry`; `AcDbObject` override. — `drawable.h:162-205`; `acgi.h:858-1676`; `dbObject.h:575-577`.
- **Plot / publish:** `AcPlPlotEngine` (`beginPlot/beginDocument/beginPage/endPage/endDocument/endPlot`), `AcPlPlotInfo`, `AcPlPlotFactory`, `AcPlPlotConfig(Mgr)`, `AcDbPlotSettings`. — `AcPlPlotEngine.h:62-79`; header inventory.
- **Host-less ObjectDBX:** `AcDbDatabase::readDwgFile/saveAs`, `AcDbHostApplicationServices`, ObjectDBX startup/shutdown. — `dbmain.h:236-526`; `dbapserv.h:108-115`.

---

### Build / integration notes

1. **Most of PART 1 is in-process editor surface (`in_process_host`)** — it requires loading the native `.arx` into a *running* AutoCAD (ARX/NETLOAD-style) and cannot run in `accoreconsole` (no editor) nor in a bare ObjectDBX process. For the router, interactive ops (jig, getPoint, palettes, status-bar) are an **attended-AutoCAD lane**, distinct from the headless `accoreconsole` lane the router already uses for `dwg_truth_autocad`.
2. **`acedCommand`/`acedCmd` are compile-time disabled in 2027** (`acedads.h:70-71` rewires them to an invalid token). Any C++ controller MUST use `acedCommandS`/`acedCmdS` (full commands) or `acedCommandC`/`acedCmdC` (coroutine). This is a hard migration gate, not advice.
3. **Document locking is mandatory** for any edit issued outside a registered command's own context (e.g. from a session-context command, a palette callback, or a modeless reactor): wrap edits in `lockDocument(...kWrite...)`/`unlockDocument` or register the command with `ACRX_CMD_DOCEXCLUSIVELOCK`. (`acdocman.h:278`; `accmd-defs.h:58`.)
4. **Scope decision for the C++ module:** the existing managed `CadJobRunner` already covers everything in the "managed_also_equivalent" rows. The C++ module should be **scoped to the native-only verdict set**: (a) host-less ObjectDBX DWG library I/O (since RealDWG is excluded), (b) custom entities / object enablers, (c) persistent reactors, (d) custom `subWorldDraw` rendering, (e) custom input-point filters/osnap, (f) coroutine command sequencing. Building C++ for the managed-reachable families is wasted effort.
5. **Two native deployment shapes:** ARX (`.arx`, in-process to AutoCAD editor — gives PART 1 editor surface) vs ObjectDBX app (`.dbx`/host-less — gives DB/custom-object/enabler surface, NO editor). The router likely wants both: a `.dbx` host-less worker for batch DB/custom-object truth, and an `.arx` for any attended-editor interaction op.
6. **`select.ssget` `"X"` mode** is the bridge: a whole-database DXF-filtered scan that does not need a pick, so it can drive extraction-style ops even in a minimally-attended editor; the host-less equivalent is iterating `AcDbDatabase` block tables directly via ObjectDBX.

---

### Sources actually read (this session)

**Autodesk Help (via `autodesk-product-help` MCP, locale en_US, product ACD, release 2027):**
- "About .NET Managed Applications" — GUID-3A5E2EE7 — https://help.autodesk.com/cloudhelp/2027/ENU/AutoCAD-Customization/files/GUID-3A5E2EE7-9A06-4965-A614-AD97A49B849A.htm
- "About ObjectARX Applications" — GUID-3FF72BD0 — .../GUID-3FF72BD0-9863-4739-8A45-B14AF1B67B06.htm
- "About Custom Objects and Proxy Objects" — GUID-6515268E — https://help.autodesk.com/cloudhelp/2027/ENU/AutoCAD-Core/files/GUID-6515268E-3D71-4CBC-8D3C-2059CFAA4E38.htm
- "Related Developer References (AutoLISP)" — GUID-7884190F — .../AutoCAD-AutoLISP/files/GUID-7884190F-4603-4E9F-8FB3-0D683BD7C4C9.htm
- "About Application Compatibility" (SDK/.NET version matrix; 2027→.NET 10.0) — GUID-D54B0935 — .../AutoCAD-Customization/files/GUID-D54B0935-1638-4F97-8B37-1EC3635A1E71.htm
- "About Selection Set Filter Lists (AutoLISP)" — GUID-7BE77062 — .../AutoCAD-AutoLISP/files/GUID-7BE77062-C359-4D01-915B-69CF672C653B.htm
- "About Logical Grouping of Selection Filter Tests" — GUID-5CB54129 — .../GUID-5CB54129-22A1-42B9-B97C-2D2F5597F90E.htm
- "ssgetfirst (AutoLISP)" — GUID-F18CB64C — .../AutoCAD-AutoLISP-Reference/files/GUID-F18CB64C-1B18-46F3-BAD4-24D83214CE0D.htm
- "About Controlling User-Input Function Conditions (AutoLISP)" (initget bits) — GUID-44553A7D — .../GUID-44553A7D-EFFF-4C26-8CF9-DF163ECACCB9.htm
- "UNDEFINE (Command)" (acedRegCmd, group.command syntax) — GUID-FC323813 — .../AutoCAD-Core/files/GUID-FC323813-D88D-4507-8665-67B215BF9EAD.htm
- "IAcadEntity Interface (ActiveX)" (IAcadEntity ↔ AcDbEntity) — GUID-FCA7867D — .../AutoCAD-ActiveX-Reference/files/GUID-FCA7867D-E354-4F48-9C47-DB22C53A3460.htm
- "EXPORTPDF (Command)" (script-reachable plot) — GUID-E9CB4A20 — .../AutoCAD-Core/files/GUID-E9CB4A20-A2AF-4395-A070-610A84853D48.htm
- "About Loading ObjectARX Applications" — GUID-409E18E6 (ARX/APPLOAD/acad.rx/SECURELOAD).
- Status-bar topics (GUID-C5C9380F, GUID-9B416455) — context for status-bar surface.

**Local ObjectARX 2027 SDK headers (read via grep/sed this session, `C:\ObjectARX 2027\inc\`):**
- `acedads.h` (lines 70-71 command-disable; 111-137 entsel/ssget; 194-231 getXXX/initget/alert/prompt; 214 menuCmd)
- `acedCmdNF.h` (31 acedFiberWorld; 46 acedCommandS; 50-53 acedCmdS; 146-151 acedCommandC/acedCmdC; AcEdCoroutineCallback typedef)
- `accmd-defs.h` (31-74 full `ACRX_CMD_*` flag bitmask incl. SESSION/DOCREADLOCK/DOCEXCLUSIVELOCK)
- `dbjig.h` (36 class AcEdJig; 66 DragStatus; 104-123 drag/sampler/update/acquire*; 131 entity)
- `acedinpt.h` (38-105 AcEdInputPointManager add/remove monitor/filter/contextReactor; 387-497 filter; 508-578 monitor; 595-621 context reactor)
- `aced.h` (124 AcApDocument fwd; 175 acedPostCommandPrompt; 182 acedSyncFileOpen; 376 AcEditorReactor : AcRxEventReactor)
- `acdocman.h` (271 curDocument; 278-283 lockDocument/unlockDocument; 322 sendStringToExecute; 332 appContextNewDocument; 471 curDoc())
- `AcApDocLockmode.h` (25-29 DocLockMode enum: kNone/kAutoWrite/kNotLocked/kProtectedAutoWrite)
- `rxoverrule.h` (121 AcRxOverrule::setIsOverruling)
- `dbentityoverrule.h` (77 Osnap; 173 Transform; 277 Grip; 879 Visibility; 934 Geometry overrules)
- `drawable.h` (162-170 SEALED worldDraw/viewportDraw; 199-205 protected pure-virtual subSetAttributes/subWorldDraw/subViewportDraw; 222-277 AcGiDrawableOverrule)
- `dbObject.h` (28 AcDbObjectReactor; 575-577 AcDbObject subSetAttributes/subWorldDraw/subViewportDraw overrides)
- `acgi.h` (858 AcGiWorldDraw; 870 AcGiViewportDraw; 1676 AcGiGeometry)
- `dbmain.h` (236/246 ObjectDBX startup/shutdown; 44-49 reactor fwds; 494-526 readDwgFile/saveAs)
- `dbapserv.h` (108-115 AcDbHostApplicationServices)
- `AcPlPlotEngine.h` (62-79 beginPlot/endPlot/beginDocument/endDocument/beginPage/endPage); `AcPlPlotInfo.h`, `AcPlPlotFactory.h`, `AcPlPlotConfig.h`, `AcPlPlotConfigMgr.h` (header inventory)
- `aduiPaletteSet.h` (64 class CAdUiPaletteSet; 163 AddPalette); `aduiPalette.h` (34 class CAdUiPalette)
- `AcStatusBar.h` (34 AcStatusBarItem; 121 AcPane; 309 AcTrayItem; 481 AcStatusBarMenuItem)
- inc/ directory listing (confirmed presence of overrule, plot, palette, status, jig, inputpt, docman, acgi headers)

**APS overview page:** https://aps.autodesk.com/developer/overview/objectarx-autocad-sdk (C++ and C# interfaces statement; SPA help-viewer GUID pages returned only "Help" shell on plain fetch — content obtained via MCP instead).
