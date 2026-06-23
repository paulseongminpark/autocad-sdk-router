# M08M — native OPM properties + reactors (55 ops)

You implement native ObjectARX handlers in ONE file: `m08m_handlers.inc`.

## Worktree / paths (ABSOLUTE ONLY — never `cd`, never relative)
- ROOT: `D:\dev\99_tools\autocad-sdk-router_M08M`
- CHANGE_ONLY: `src\Ariadne.AcadNative\families\m08m_handlers.inc`, `tests\unit\test_m08m_handlers.py`,
  `reports\tickets\M08M.md` (cover T01 + T02 in this one report).
- Do NOT touch AriadneNativeJob.cpp / .vcxproj / registry / other family `.inc`. Seam wires `m08mHasOp`/`m08mDispatch`.
- git: `git -C D:\dev\99_tools\autocad-sdk-router_M08M ...`. shell: absolute paths.

## Mission
Fill `m08m_handlers.inc` (stub) for the feasible-hostless subset; HONESTLY defer the rest (out of HasOp +
blocker). **NO FAKES.** Hostless on `ctx.pDb`.

## Reference (READ FIRST)
- Read/serialize: `families\m08c_handlers.inc` / `m08d_handlers.inc` (njsonStr, serializeObjectCommon, AriadneReadTransaction).
- ⚠️ **LNK2001 wall (from M08K)**: DBX import lib does NOT export custom-class `::desc()/::cast()`. If you
  touch Ariadne custom classes, use `acrxClassDictionary()->at(L"...")` + extern-C predicates. Most M ops use
  the AcRxProperty / AcDb*Reactor API on STANDARD classes (no issue).

## Op set (55) — feasibility (VERIFY by building)
### M-T01 OPM / property protocol (33) — registration + inspection is hostless
The dynamic property protocol (AcRxProperty / AcRxAttribute / AcRxMemberCollection over an AcRxClass) is
queryable + extendable hostless; the Properties PALETTE itself is attended (you are NOT building UI).
HIGH feasibility:
- inspect: `inspect.property.by_name`, `inspect.property.is_readonly`, `inspect.property.metadata`
  (AcRxClass property lookup → name/type/readonly/category over a class — pure read), `automate.property.set`
  (set a value property on an object via the protocol → staged).
- OPM registration: `extend.opm.register_provider`, `extend.opm.get_manager`, `extend.opm.get_dispid`,
  `extend.opm.map_category`, `extend.opm.define_property`/`define_property2`, `extend.opm.enum_property`,
  `extend.opm.dialog_property`, `extend.opm.per_instance_source`, `extend.opm.property_expander`,
  `extend.opm.property_expression`, `extend.opm.property_extension` (register/query the OPM property protocol
  on a class — hostless protocol-extension, like M08K's protocol ops).
- property authoring: `extend.property.define`/`define_collection`/`define_indexed`/`define_dictionary`,
  `.describe`, `.category`, `.display_as`, `.units`, `.flags`, `.default_value`, `.enum_tag`, `.refers_to`,
  `.localize_name`, `.com_name`, `.expose_to_com`, `.filepath`, `.overrule` (AcRxProperty/AcRxAttribute build
  + attach to the class member collection — hostless). These are risk=live_edit; implement what registers
  cleanly hostless, defer any that need a running app to take effect.

### M-T02 reactors (22) — DB/object/persistent/rx reactors are hostless; editor/docmanager are attended
HIGH feasibility (attach a reactor to the staged db/object; fire on in-transaction modify/erase — hostless):
- `react.database.attach`/`.monitor` (AcDbDatabaseReactor on ctx.pDb), `react.object.attach_transient`/
  `.detach_transient`/`.monitor` (AcDbObjectReactor), `react.persistent.attach`/`.detach` (AcDbObject
  persistent reactor), `react.rxevent.attach`/`.monitor` (AcRxEvent), `react.linker.attach`/`.monitor`
  (AcRxDynamicLinker reactor), `react.longtx.attach`/`.monitor` (AcApLongTransactionReactor — if it links
  hostless), `react.config.disable_namespace` (reactor namespace toggle). Attach + trigger a real
  modify/erase within an AriadneStagedWriteTransaction to PROVE the callback fires, then report counts.
DEFER (attended — need the editor / doc manager / app message loop):
- `react.editor.command_monitor`/`.input_monitor`/`.lisp_monitor`/`.sysvar_monitor`/`.dwg_lifecycle`
  (AcEditorReactor — needs the running editor), `react.docmanager.attach`/`.monitor` (AcApDocManager — needs
  the document manager / attended app). Leave OUT of HasOp + blocker.

## Canonical patterns
- inspect/property-read op: walk AcRxClass property collection → serialize via njsonStr.
- reactor op: instantiate a static reactor subclass (counters), `pDb->addReactor(pR)` or
  `pObj->addReactor(pR)`; for "monitor" do a scratch modify in AriadneStagedWriteTransaction (dtor-rollback)
  to fire the callback, report fired-count, then removeReactor. Never persist.
- failure → `emitNativeError(r,CODE,msg); return true;` — never fake ok.

## In-TU helpers
jsonFindString/Number/Object, jsonEscape, njsonStr, handleOf, resolveHandle, serializeObjectCommon,
AriadneReadTransaction, AriadneStagedWriteTransaction, emitNativeError. Plus AcRxProperty/AcRxAttribute/AcDb*Reactor/AcRxEvent API.

## Hard constraints
- Hostless on ctx.pDb. NO save()/saveAs()/_QSAVE. NO acedCommand. HasOp↔Dispatch lockstep. Unimplemented OUT of HasOp. NO FAKES.
- Always removeReactor what you addReactor; static reactor instances are module-lifetime (fine). UTF-8 via njsonStr.

## Build gate (MUST be exit 0)
`powershell -NoProfile -ExecutionPolicy Bypass -File D:\dev\99_tools\autocad-sdk-router_M08M\tools\build_native_acad.ps1 -RouterHome D:\dev\99_tools\autocad-sdk-router_M08M`
Iterate until final JSON `"status":"ok"` + exit 0. Defer any op that won't link hostless.

## Tests (test_m08m_handlers.py)
Mirror `tests\unit\test_m08d_handlers.py`: HasOp↔Dispatch lockstep, no save/saveAs/acedCommand, editor/docmanager
reactors excluded from HasOp, sane min count. Run: `python -m pytest D:\dev\99_tools\autocad-sdk-router_M08M\tests\unit\test_m08m_handlers.py -q` (PYTHONIOENCODING=utf-8).

## Ticket report (reports/tickets/M08M.md)
Implemented (with AcRxProperty/AcDb*Reactor class), deferred (with concrete blocker), build sizes + exit. Honest.

## Commit + report back (do NOT push/PR/merge)
`git -C D:\dev\99_tools\autocad-sdk-router_M08M add -A` then commit `-m "M08M: native OPM properties + reactors"`.
Return: implemented count+list, deferred count+reasons, build exit + artifact sizes, unit-test result, commit hash. Precise data.
