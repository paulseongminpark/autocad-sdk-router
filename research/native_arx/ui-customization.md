# ObjectARX 2027 — Native C++ Operation Catalog: `ui-customization`

> Research session: 2026-06-18. Grounded ONLY in ObjectARX 2027 SDK headers (`C:\ObjectARX 2027\inc`, `inc-x64`) and Autodesk official help (help.autodesk.com OARX/AutoCAD 2027) read this session. Every row cites a header:line or a GUID URL actually read. Items I could not verify in a header read this session are marked **unverified**.
>
> **execution_context note:** `accoreconsole.exe` ships with AutoCAD 2027 but is HEADLESS — it has no application frame, no status bar, no palette host, no ribbon. **Every operation in this family is `in_process_host` (attended AutoCAD GUI session) only.** None of these run under accoreconsole. This is the defining constraint of the slice.

---

## Slice: ui-customization

### Operation catalog

| proposed_op_id | native API (class::method) | engine_tier | what it does | key inputs | key outputs | dwg_persisted? | execution_context | citation |
|---|---|---|---|---|---|---|---|---|
| editor.toolpalette.window_get | `AcTcUiGetManager()` → `CAcTcUiManager`; `AcTcUiGetToolPaletteWindow()` → `CAcTcUiToolPaletteSet*` | native_arx_only (managed_also) | Get the global Tool Palettes manager / the live Tool Palettes window (the docked palette set) | none | manager ptr / tool-palette-set ptr | no (UI state) | in_process_host | AcTcUI.h:106, AcTcUI.h:118 |
| editor.toolpalette.window_show | `CAcTcUiManager::ShowToolPaletteWindow(BOOL bShow)`; `IsToolPaletteWindowVisible()` | native_arx_only | Show/hide the Tool Palettes window; query visibility | bShow | BOOL | no | in_process_host | AcTcUiManager.h:50-51 |
| editor.toolpalette.create | `CAcTcUiManager::CreatePalette(LPCTSTR pszPalName, DWORD dwFlags)` → `CAcTcUiToolPalette*` | native_arx_only | Create a new (empty) tool palette tab programmatically | palette name, flags | new palette ptr | no (palette = .atc XML, see persistence note) | in_process_host | AcTcUiManager.h:41-42 |
| editor.toolpalette.scheme_create | `CAcTcUiScheme::CreatePaletteSet(LPCTSTR pszPalSetName)` → `CAcTcUiToolPaletteSet*` | native_arx_only | Create a NEW named palette set (own dockable window) under a UI scheme — the supported way to make your own tool-palette window distinct from the built-in one | palette set name | palette-set ptr | no | in_process_host | AcTcUiScheme.h:51 |
| editor.toolpalette.scheme_register | `CAcTcUiManager::AddScheme(CAcTcUiScheme*)`; `GetScheme(name/idx)`; `GetSchemeCount()`; `RemoveScheme()` | native_arx_only | Register/lookup/remove a UI scheme (namespace for your palette sets so they don't collide with stock palettes) | scheme ptr / name / index | int / scheme ptr / BOOL | no | in_process_host | AcTcUiManager.h:63-67 |
| editor.toolpaletteset.add_palette | `CAcTcUiToolPaletteSet::AddPalette(CAdUiPalette*)`; `InsertPalette(idx, pal)`; `RemovePalette()` | native_arx_only | Add/insert/remove a palette (tab) within a tool palette set | palette ptr (+ index) | int index / BOOL | no | in_process_host | AcTcUiToolPaletteSet.h:52-55 |
| editor.toolpaletteset.show | `CAcTcUiToolPaletteSet::Show(BOOL)`; `SetActivePalette(pal/idx/name)`; `FindPalette(name,...)` | native_arx_only | Show the palette set; set/find the active palette tab by ptr, index, or name | BOOL / ptr / index / name | BOOL / palette ptr | no | in_process_host | AcTcUiToolPaletteSet.h:67-75 |
| editor.toolpalette.add_tool | `AcTcStockTool::CreateTool()` → `AcTcTool*`; then `AcTcCatalogItem::AddChild(pTool)` onto the palette's catalog item | native_arx_only (managed_also) | Populate a palette with a tool: instantiate a tool from a stock tool, set its command, add it as a child catalog item of the palette. (Tools are catalog items; a palette is `AcTcPalette : AcTcPackage : AcTcCatalogItem`.) | stock-tool template; tool props | new tool ptr / index | tool def → .atc XML (palette file), see persistence note | in_process_host | AcTc.h:685 (CreateTool), AcTc.h:457 (AddChild), AcTc.h:763-773 (AcTcPalette) |
| editor.toolpalette.tool_set_command | `AcTcTool::SetToolType(ToolType)`; `EnableFlyout(BOOL)`; `SetShapePackage()`; `SetStockToolID(GUID*)` | native_arx_only | Configure a tool's type (normal/flyout/text/separator), flyout, shape package, and which stock tool backs it | tool type, GUID, package | BOOL | tool def (.atc) | in_process_host | AcTc.h:731-739 |
| editor.toolpalette.tool_execute | `AcTcTool::Execute(int nFlag, HWND, POINT, DWORD dwKeyState)` | native_arx_only | Programmatically fire a tool as if the user clicked/dropped it | flags, hwnd, point, keystate | BOOL | depends on tool (may edit dwg) | in_process_host | AcTc.h:718-721 |
| editor.toolpalette.catalog_manager | `AcTcGetManager()` → `AcTcManager`; `LoadCatalogs()`, `SaveCatalogs()`, `AddCatalog()`, `GetCatalog()`, `FindItem(GUID)` | native_arx_only | Get the (non-UI) tool-catalog data manager; load/save/add/enumerate catalogs and stock-tool catalogs; resolve items by GUID | catalog-type & load/save flags | BOOL / catalog-item ptr | catalogs are .atc/.aws files on disk (not dwg) | in_process_host (data layer can run without GUI) | AcTc.h:805 (AcTcGetManager), AcTc.h:341-345 (Load/Save), AcTc.h:326-328 (Get/Find) |
| editor.toolpalette.stocktool_find | `AcTcManager::FindStockTool(GUID)`; `GetStockToolCatalog(idx)`; `GetStockToolCatalogCount()` | native_arx_only | Resolve a stock tool (the template that knows how to create a tool of a given type) by GUID; enumerate stock-tool catalogs | GUID / index | stock-tool ptr / catalog-item ptr | no (templates) | in_process_host | AcTc.h:322-324 |
| editor.toolpalette.catalog_item_props | `AcTcCatalogItem::SetName/SetDescription/SetToolTipText/SetHelpInfo/SetKeywords/SetImageList...` (+ Get*) | native_arx_only | Set/get the display metadata of any catalog item (tool, palette, package, category, catalog): name, description, tooltip, help, keywords, images | strings, image list | BOOL / int | item def (.atc XML) | in_process_host | AcTc.h:475-537 |
| editor.toolpalette.group_create | `CAcTcUiToolPaletteSet::GetToolPaletteGroup(BOOL bCreate)`; `CAcTcUiToolPaletteGroup::AddItem(palette/group)`, `InsertItem()`, `SetName()` | native_arx_only | Create/populate a Tool Palette **Group** (the right-click grouping of palettes); nest palettes and sub-groups | group name, palette/group ptrs | group ptr / int index | no (group = .xpg) | in_process_host | AcTcUiToolPaletteSet.h:59-65, AcTcUiToolPaletteGroup.h:36-45 |
| editor.toolpalette.group_activate | `CAcTcUiToolPaletteSet::SetActivePaletteGroup(group/name)`; `GetActivePaletteGroup()`; `GetAllPalettesGroup()` | native_arx_only | Switch the displayed palette group; query active/all-palettes group | group ptr / name | BOOL / group ptr | no | in_process_host | AcTcUiToolPaletteSet.h:60-65 |
| editor.toolpalette.export | `CAcTcUiManager::Export(file, palettes)`; `Import(file)`; `CAcTcUiScheme::Export/Import` | native_arx_only | Export/import tool palettes (.xtp) and groups (.xpg) to share/persist | file path, palette array | BOOL | writes .xtp/.xpg on disk | in_process_host | AcTcUiManager.h:43-45, AcTcUiScheme.h:63-66 |
| editor.toolpalette.refresh | `CAcTcUiScheme::Refresh(RefreshScope, dwFlag)`; `Show(ShowOption, key)`; `Unload()` | native_arx_only | Refresh palettes from their catalog source; show/hide/save-restore scheme state; unload scheme | scope/option enums | BOOL | no | in_process_host | AcTcUiScheme.h:67-72, :50 |
| editor.toolpalette.global_init | `AcTcInitialize()`/`AcTcUninitialize()` (catalog layer); `AcTcUiInitialize()` (UI layer); `AcTcSetHostInfo()` | native_arx_only | One-time init/teardown of the tool-catalog and tool-catalog-UI subsystems before use; set host version for target-product filtering | host version ints | BOOL | no | in_process_host | AcTc.h:803-804, AcTcUI.h:105, AcTc.h:824 |
| editor.palette.create_dockable | `CAdUiPaletteSet::Create(strTitle, dwStyle, rect, pwndParent, dwPaletteSetStyle)` + `CAdUiPalette::Create(dwStyle, name, pParent, paletteStyle)` | native_arx_only | Create a fully custom **modeless dockable window** (palette set) hosting your own `CAdUiPalette`-derived MFC panel(s). The general dockable-window mechanism (your own content, not a tool palette) | title, MFC styles, palette-set-style bitflags, parent CWnd, rect | BOOL + window | no (UI state) | in_process_host | aduiPaletteSet.h:79-81, aduiPalette.h:48-53 |
| editor.palette.dock | `CAdUiPaletteSet::EnableDocking(DWORD dwDockStyle)` | native_arx_only | Enable docking of a custom palette set to the AutoCAD frame edges | dock-style bits | void | no | in_process_host | aduiPaletteSet.h:211 |
| editor.palette.style | `CAdUiPaletteSet::SetPaletteSetStyle/SetName/SetOpacity/SetAutoRollup/SetTitleBarLocation/SetThemedIcon` | native_arx_only | Configure a custom palette set: style bitflags (close button, auto-rollup, snap, edit-name…), name, opacity, rollup, title-bar side, themed icon | bitflags / int / string / HICON | BOOL / void | no | in_process_host | aduiPaletteSet.h:84-86,100-102,127,149,202,337; PSS_* flags :28-42 |
| editor.palette.add_palette | `CAdUiPaletteSet::AddPalette/InsertPalette/RemovePalette/GetPalette/GetPaletteCount/SetActivePalette` | native_arx_only | Manage the panels (palettes) inside a custom palette set | palette ptr / index | int / BOOL / palette ptr | no | in_process_host | aduiPaletteSet.h:163-172,139-143 |
| editor.palette.persist | `CAdUiPaletteSet::Save(IUnknown*)` / `Load(IUnknown*)`; `CAdUiPalette::Save/Load` | native_arx_only | Save/restore custom palette-set + palette state to/from an XML stream (IUnknown) | IUnknown stream | BOOL | XML stream (caller-provided sink) | in_process_host | aduiPaletteSet.h:185-187, aduiPalette.h:65-67 |
| editor.statusbar.get | `acedGetApplicationStatusBar()` → `AcApStatusBar*` | native_arx_only | Get the application status bar (the singleton you add panes/tray items to). THE entry point for status-bar work | none | `AcApStatusBar*` | no | in_process_host | core_rxmfcapi.h:572-576 |
| editor.statusbar.add_pane | `AcApStatusBar::Add(AcPane*, BOOL bUpdate)`; `Insert(nIndex, AcPane*, bUpdate)` | native_arx_only | Add/insert a custom **pane** (text+icon cell, e.g. like SNAP/GRID) on the status bar | `AcPane*`, index, bUpdate | int index / BOOL | no | in_process_host | AcStatusBar.h:428,419 |
| editor.statusbar.pane_config | `AcPane::SetText/SetIcon/SetStyle/SetToolTipText/SetMinWidth/SetMaxWidth/SetPaneName/SetRegistryKey`; `DisplayPopupPaneMenu(CMenu&)` | native_arx_only | Configure a pane's text, icon, style (ACSB_* flags), tooltip, width, name, persistence key; show its popup menu | strings, HICON, style bits, CMenu | BOOL / int / UINT | pane name+state can persist to registry via SetRegistryKey | in_process_host | AcStatusBar.h:131-149; ACSB_* flags :106-115 |
| editor.statusbar.remove_pane | `AcApStatusBar::Remove(AcPane*/index, bUpdate)`; `RemoveAllPanes()`; `GetPane(idx)`; `GetPaneCount()`; `GetIndex()` | native_arx_only | Remove pane(s); enumerate/locate panes | pane ptr / index | BOOL / int / pane ptr | no | in_process_host | AcStatusBar.h:422-443 |
| editor.tray.add_item | `AcApStatusBar::Add(AcTrayItem*, bUpdate)`; `Insert(nIndex, AcTrayItem*, bUpdate)` | native_arx_only | Add a **tray icon** to the status-bar tray (right side, like the services icons) | `AcTrayItem*`, index | int / BOOL | no | in_process_host | AcStatusBar.h:429,420 |
| editor.tray.item_config | `AcTrayItem::SetIcon/SetToolTipText`; `ShowBubbleWindow(AcTrayItemBubbleWindowControl*)`; `CloseAllBubbleWindows()`; `GoToState(state, AcRxValue*)` | native_arx_only | Configure a tray icon; pop a notification **bubble window** (title/text/hyperlink/checkbox); drive its visual state machine | HICON, string, bubble-control obj | BOOL / void | no | in_process_host | AcStatusBar.h:316-324; bubble ctrl :228-306 |
| editor.tray.remove | `AcApStatusBar::Remove(AcTrayItem*/index)`; `RemoveAllTrayIcons()`; `GetTrayItem(idx)`; `GetTrayItemCount()`; `CloseAllBubbleWindows(item)` | native_arx_only | Remove tray item(s); enumerate; close bubbles | tray ptr / index | BOOL / int / tray ptr | no | in_process_host | AcStatusBar.h:423-424,445-449,477 |
| editor.statusbar.context_menu | `AcApStatusBar::DisplayContextMenu(CMenu&, CPoint)`; `DisplayPopupPaneMenu(AcPane*, CMenu&)`; `AcStatusBarItem::DisplayContextMenu()` | native_arx_only | Show a context menu on the status bar / on a specific pane | CMenu, point | UINT (chosen cmd) | no | in_process_host | AcStatusBar.h:459-460, :70 |
| editor.command.register | `acedRegCmds->addCommand(group, globalName, localName, cmdFlags, AcRxFunctionPtr, ...)` (`AcEdCommandStack::addCommand`) | native_arx_only | Register a new command (the prerequisite for wiring any UI element — menu/tool/ribbon macro — to your code). `acedRegCmds` macro yields the global `AcEdCommandStack`. This is the command↔UI glue. | group name, global+local names, flags, fn ptr | `Acad::ErrorStatus` | no | in_process_host (and accoreconsole — command registration itself is non-GUI) | accmd.h:166-167 (macro), accmd.h:169 (class), accmd.h:178 (addCommand) |
| editor.command.unregister | `AcEdCommandStack::removeCmd(group, globalName)`; `removeGroup(group)`; `popGroupToTop(group)` | native_arx_only | Remove a command or whole command group; raise a group's lookup priority | group / command names | `Acad::ErrorStatus` | no | in_process_host / accoreconsole | accmd.h:207-212 |
| editor.menu.menubar_get | `AdApplicationFrame::GetMenuBar()` → `AdMenuBar*` | native_arx_only | Get the application frame's classic menu bar object (only present when MENUBAR=1) | none | `AdMenuBar*` | no | in_process_host | AdApplicationFrame.h:232 |
| editor.menu.add_item | `AdMenuBar::AddMenuItem(HMENU, nPos, MENUITEMINFO&, LPFNADMENUCALLBACK, helpString)`; `RemoveMenuItem()`; `SetMenuHandle()`; `UpdateMenu()`; `GetMenuHandle()` | native_arx_only | Add/remove a Win32 menu item on the classic menu bar with a C callback + status-line help string; refresh the menu | HMENU, position, MENUITEMINFO, callback fn, help text | bool / HMENU | no | in_process_host | AdMenuBar.h:54-63; callback typedef :39 |
| editor.menu.context (shortcut) | *No dedicated native shortcut-menu builder header found this session.* Build context menus as Win32 `CMenu` and invoke via `AcApStatusBar::DisplayContextMenu` / pane menus; for drawing-area shortcut menus the documented path is **CUIx shortcut-menu definitions** + POP500-series aliases (CUI Editor / .cuix), not a C++ API. | CMenu (status-bar case) / CUIx (drawing case) | UINT / — | CUIx case persists to .cuix | in_process_host | AcStatusBar.h:459 (status-bar CMenu); CUI shortcut menus = GUID-AC84784E (Customization Guide) **unverified for a native C++ entry** |
| editor.menu.load_cuix | **Managed/command-only.** No native C++ `loadPartialCuix`/`menuLoad` export found in headers this session. Documented mechanisms: the `CUILOAD`/`MENULOAD` command (drive via `acedCommandS`/`acedCommand`), the managed API, or a `.cuix`/MNL on the support path. | CUIx file path (via command) | — | the .cuix file itself is the persisted UI | in_process_host | help GUID-12C8C414 / GUID-E2EEEA2A (partial CUIx model) — **native C++ loader: not found / unverified** |
| editor.ribbon.add_tab | **managed_also — NO native C++ ribbon API.** The ribbon is created/edited via the **CUI Editor + CUIx** (interactive) or the **managed `Autodesk.Windows.RibbonControl` / `RibbonTab` / `RibbonPanelSource`** (in `AdWindows.dll` / `AcWindows.dll`). ARX path: register commands (`addCommand`) + ship a partial CUIx whose ribbon-tab **Alias** (e.g. `ID_ADDINSTAB`) merges your tab. There is **no `*ribbon*.h` C++ header** in the SDK. | (managed) RibbonControl objects / (CUIx) tab+panel+alias | (managed) ribbon objects | ribbon layout persists in .cuix | in_process_host | **header verdict:** no `*ribbon*` header in `inc`/`inc-x64` (only managed `.dll`/`.xml`); CUIx ribbon model = help GUID-E2EEEA2A, GUID-12C8C414, GUID-915B7CA4 |

---

### Classes & subsystems covered

**Tool palettes — catalog (data) layer `AcTc.h` (non-UI, headless-capable for data):**
- `AcTcManager` (global via `AcTcGetManager()`) — catalogs, stock-tool catalogs, schemes, load/save.
- `AcTcScheme`, `AcTcCatalogSet` — scheme/catalog containers.
- `AcTcCatalogItem` (base) and subclasses `AcTcCategory`, `AcTcCatalog`, `AcTcStockTool`, `AcTcTool`, `AcTcPackage`, `AcTcPalette` — the tool/palette content model (a palette IS a catalog item; tools are its children).
- `AcTcImage`, `AcTcImageList` — tool/palette icons (incl. dark-theme variants).
- `AcTcCatalogItemReactor` — change notifications on catalog items.
- Globals: `AcTcInitialize/AcTcUninitialize/AcTcGetManager/AcTcDownloadItem/AcTcRefreshItem/AcTcSort/AcTcSetHostInfo`.

**Tool palettes — UI layer `AcTcUI.h` family:**
- `CAcTcUiManager` (global via `AcTcUiGetManager()`) — the Tool Palettes window, create palettes, schemes, import/export, show/hide.
- `CAcTcUiToolPaletteSet : CAdUiPaletteSet` — the tool-palette window itself; add/insert/remove palettes, groups, active palette.
- `CAcTcUiToolPalette : CAdUiPalette` — a single tool-palette tab; paste/import/export tools.
- `CAcTcUiToolPaletteGroup : CObject` — palette groups (nestable).
- `CAcTcUiScheme : CObject` — namespace for custom palette sets; create palette set, refresh, show/hide/save state.
- Globals: `AcTcUiInitialize/AcTcUiGetManager/AcTcUiGetToolPaletteWindow/AcTcUiCopyItems/AcTcUiPasteItems`.
- (Also present, not deep-dived: `AcTcUiCatalogView.h`, `AcTcUiCatalogViewItem.h`, `AcTcUiPaletteView.h` — the tray/catalog view widgets embedded in a palette.)

**Modeless / dockable palettes & dialogs — `adui*`/`acui*` family:**
- `CAdUiPaletteSet : CAdUiDockControlBar` (aduiPaletteSet.h) — general custom dockable window host; styles via `PSS_*`, docking, opacity, theming, save/load.
- `CAdUiPalette : CWnd` (aduiPalette.h) — base for custom palette content panels.
- Broader `adui*`/`acui*` control & dialog headers present in SDK (read by listing, not line-by-line this session): `aduiDialog.h`, `acuiDialog.h`, `aduiBaseDialog.h`, `aduiDialogBar.h`, `aduiDock.h`, `acuiDialogWorksheet.h`, `aduiButton.h`, `aduiComboBox.h`, `aduiEdit.h`, `aduiImage.h`, `aduiListBox.h`, `aduiTab*`, etc. — the MFC-derived dialog/control toolkit for ARX dialogs. **(CAdUiDialog / CAcUiDialog exact bases: present as headers but not line-verified this session — unverified.)**

**Status bar & tray — `AcStatusBar.h` + accessor in `core_rxmfcapi.h`:**
- `AcApStatusBar` (abstract; obtained via `acedGetApplicationStatusBar()`) — add/insert/remove panes & tray items, context menus, enumeration.
- `AcStatusBarItem` (base), `AcPane` (text/icon cell), `AcTrayItem` (tray icon) — with `AcTrayItemBubbleWindowControl` for notification bubbles.
- `AcDefaultPane` enum — IDs of all built-in panes (SNAP/GRID/ORTHO/POLAR/coords/…).
- `AcStatusBarMenuItem` — status-bar menu customization (mostly deprecated).

**Menus / CUI — `AdMenuBar.h` + command stack `accmd.h`:**
- `AdApplicationFrame::GetMenuBar()` → `AdMenuBar` — classic menu-bar item add/remove with a C callback and help string.
- `AcEdCommandStack` (`accmd.h`, via `acedRegCmds` macro) — command registration/removal; the command↔UI glue every menu/tool/ribbon element ultimately calls.
- CUIx / shortcut-menu / partial-customization editing: **documented as CUI-Editor + `.cuix` (interactive) or managed API**, not a native C++ builder.

**Ribbon:** see honest verdict below.

---

### Build / integration notes

- **DLLs/libs:** UI work links the standard ARX import libs in `C:\ObjectARX 2027\lib-x64` (e.g. `AcTc.lib`/`AcTcUi.lib` for tool palettes, `acui.lib`/`adui.lib` for the dialog/palette toolkit, `accore.lib`/`acad.lib`/`rxapi.lib` for command stack + status bar). Confirm exact lib names at build time from the lib-x64 listing (not enumerated per-class this session).
- **MFC required.** The entire `adui*`/`acui*`/`AcTcUi*` and `AcStatusBar`/`AdMenuBar` surface is MFC-based (`CWnd`, `CObject`, `CMenu`, `DECLARE_DYNCREATE`, `afx_msg`, `MENUITEMINFO`). Your ARX project must be built **MFC-extension / shared-MFC**, matching AutoCAD's MFC version (VS2026 / VS2022 toolset, the AutoCAD 2027 toolchain). A non-MFC ARX module cannot use this slice.
- **Init order:** call `AcTcInitialize()` + `AcTcUiInitialize()` (and `AcTcSetHostInfo`) before touching tool palettes; obtain `AcTcGetManager()`/`AcTcUiGetManager()` thereafter. Status bar: call `acedGetApplicationStatusBar()` at/after `kInitAppMsg` (it returns null when there is no frame — i.e. under accoreconsole).
- **Lifetime/ownership:** `AcPane`/`AcTrayItem` you `Add()` are owned by you — remove them in your `kUnloadAppMsg` handler (`RemoveAllPanes` won't free your heap objects). Tool-palette catalog items added as children follow the catalog item ownership rules in `AcTc.h`.
- **Command-first pattern:** to make ANY UI element actionable, `acedRegCmds->addCommand(...)` first, then have the menu item / tool macro / ribbon button invoke that command (by global name, prefixed `_` for language-independence — see "About Command Macro Strings", GUID-D991386C). This is the single integration spine across menus, tool palettes, and ribbon.
- **Persistence reality (the dwg_persisted column):** essentially nothing here writes to the DWG. UI artifacts persist to *side files*: tool palettes → `.atc` (XML) under `%appdata%\Autodesk\<product>\<rel>\<lang>\Support\ToolPalette\Palettes\`, exports → `.xtp`/`.xpg`, ribbon/menus/shortcut-menus → `.cuix`, pane state → registry (via `AcPane::SetRegistryKey`), custom palette-set state → an XML stream you supply to `Save(IUnknown*)`. (Tool-palette file locations: help "How to recover Tool Palettes in AutoCAD".)

---

### C++-only delta (and what is managed-only)

**Strong native C++ (no managed needed), `native_arx_only`:**
- Full programmatic **tool palettes**: create palette sets/schemes, create palettes, build tools from stock tools, populate, group, import/export, show/refresh. (`AcTc*` + `AcTcUi*`.) Managed `Autodesk.AutoCAD.Windows.ToolPalette*` exists too (→ `managed_also` on the create/add-tool rows) but the native surface is first-class and complete.
- Full **status bar & tray**: panes, tray icons, notification bubbles, context menus. (`AcApStatusBar`/`AcPane`/`AcTrayItem`.) This is a place native ARX is clearly ahead of casual managed use.
- **Custom dockable/modeless palettes & dialogs**: `CAdUiPaletteSet`/`CAdUiPalette` + the `adui*`/`acui*` MFC toolkit. (Managed equivalent = `PaletteSet` in `Autodesk.AutoCAD.Windows`; → conceptually `managed_also`, but the native MFC route is what these headers expose.)
- **Classic menu bar** item add/remove (`AdMenuBar`) and **command registration** (`AcEdCommandStack`).

**Managed-only / not-native (be honest):**
- **RIBBON.** There is **no native C++ ribbon API in ObjectARX 2027.** A full-tree search for `*ribbon*` returned only managed assemblies (`AdWindows.dll`, `AcWindows.dll`, `AcCui.dll`, `AdUiPalettes.dll` and their `.xml` docs) — these are .NET assemblies shipped inside `inc\`, **not** C++ headers. The supported programmatic ribbon surface is the managed **`Autodesk.Windows`** namespace (`RibbonControl`, `RibbonTab`, `RibbonPanel`, `RibbonPanelSource`, `RibbonButton`, …) plus the internal `Autodesk.Internal.Windows`. From native ARX you reach the ribbon only **indirectly**: register your command(s), then ship a partial **CUIx** whose ribbon tab carries a known **Alias** (e.g. `ID_ADDINSTAB` to merge into the Plug-ins tab — GUID-E2EEEA2A). Do **not** expect a native `RibbonControl::AddTab`.
- **CUIx authoring (ribbon tabs/panels, pull-down menus, toolbars, shortcut menus, workspaces)** is delivered as the **CUI Editor (interactive)** + the `.cuix` file format, or the managed customization API — **not** a native C++ builder. Native ARX participates by (a) registering commands and (b) shipping/merging a partial CUIx. No `loadPartialCuix`/`menuLoad` C++ export was found this session (drive `CUILOAD`/`MENULOAD` as commands if needed). → tagged `managed_also` / command-driven.
- **Classic toolbars** (`AcadToolbar`/`AcadToolbarItem`): exposed through the **COM/ActiveX** automation model, not these C++ headers (out of this slice's header set; would fall under the COM/OPM family). Not a native-C++ `ui-customization` header here.

---

### Sources actually read (this session)

**ObjectARX 2027 headers (`C:\ObjectARX 2027\inc`, read line-by-line):**
1. `AcTc.h` — tool-catalog data layer (managers, catalog items, tools, stock tools, images, globals).
2. `AcTcUI.h` — tool-palette UI globals + typedefs + drag/clipboard formats.
3. `AcTcUiManager.h` — `CAcTcUiManager`.
4. `AcTcUiToolPaletteSet.h` — `CAcTcUiToolPaletteSet`.
5. `AcTcUiToolPalette.h` — `CAcTcUiToolPalette`.
6. `AcTcUiToolPaletteGroup.h` — `CAcTcUiToolPaletteGroup`.
7. `AcTcUiScheme.h` — `CAcTcUiScheme`.
8. `AcStatusBar.h` — `AcApStatusBar`/`AcStatusBarItem`/`AcPane`/`AcTrayItem`/bubble control/`AcDefaultPane`.
9. `AdMenuBar.h` — `AdMenuBar`.
10. `aduiPaletteSet.h` — `CAdUiPaletteSet` + `PSS_*` styles.
11. `aduiPalette.h` — `CAdUiPalette`.
12. `accmd.h` (grep) — `acedRegCmds` macro + `AcEdCommandStack::addCommand/removeCmd/removeGroup/popGroupToTop`.
13. `core_rxmfcapi.h` (grep) — `acedGetApplicationStatusBar()` accessor.
14. `AdApplicationFrame.h` (grep) — `GetMenuBar()`.
15. Header **inventory** (`inc`/`inc-x64` listing): confirmed the full `acui*`/`adui*` dialog+control family present; confirmed **no `*ribbon*.h`** anywhere (only managed `.dll`/`.xml`).

**Autodesk official help (help.autodesk.com, AutoCAD/OARX 2027, read this session):**
- GUID-AC84784E — *To Customize a Ribbon Panel* (CUI Editor).
- GUID-12C8C414 — *To Customize a Ribbon Tab* (CUI Editor; "Aliases … used to reference the ribbon tab programmatically").
- GUID-E2EEEA2A — *About Customizing Ribbon Tabs* (partial CUIx merge, `ID_ADDINSTAB`).
- GUID-915B7CA4 — *Design Your Own Ribbon* (end-to-end CUI ribbon workflow).
- GUID-F31F2A7E / GUID-CF1117E9 / GUID-215BD17C — Tool Palette **Groups** + **export/import (.xtp/.xpg)**.
- GUID-D991386C — *About Command Macro Strings* (`^C^C_.cmd` macro syntax — the menu/tool/ribbon ↔ command wiring).
- GUID-3FF72BD0 — *About ObjectARX Applications* (ARX = compiled C++, new commands "operate exactly the same way as native commands").
- GUID-C5C9380F / GUID-E3B34B0A / GUID-AE87A0EA — Status bar & Tray Settings (UI semantics behind panes/tray).
- "How to recover Tool Palettes in AutoCAD" (SFDC) — `.atc` file format + on-disk palette locations.
