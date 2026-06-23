# M08L — native graphics system: worldDraw + overrules/grips (27 ops)

You implement native ObjectARX handlers in ONE file: `m08l_handlers.inc`.

## Worktree / paths (ABSOLUTE ONLY — never `cd`, never relative)
- ROOT: `D:\dev\99_tools\autocad-sdk-router_M08L`
- CHANGE_ONLY: `src\Ariadne.AcadNative\families\m08l_handlers.inc`, `tests\unit\test_m08l_handlers.py`,
  `reports\tickets\M08L.md` (cover both T01 + T02 in this one report).
- Do NOT touch AriadneNativeJob.cpp / .vcxproj / registry / other family `.inc`. Seam wires `m08lHasOp`/`m08lDispatch`.
- git: `git -C D:\dev\99_tools\autocad-sdk-router_M08L ...`. shell: absolute paths.

## Mission
Fill `m08l_handlers.inc` (stub) for the feasible-hostless subset; HONESTLY defer the rest (out of HasOp +
blocker). **NO FAKES.** Hostless on `ctx.pDb`.

## Reference (READ FIRST)
- Read/serialize pattern: `families\m08c_handlers.inc` / `m08d_handlers.inc` (njsonStr, serializeEntityCommon, AriadneReadTransaction).
- ⚠️ **LNK2001 wall (from M08K)**: the DBX import lib exports ONLY the module extern-C API, NOT custom-class
  `::desc()/::cast()`. If you reference Ariadne custom classes, reach them via
  `acrxClassDictionary()->at(L"AriadneProbe")` + the extern-C predicates — do NOT call `AriadneProbe::desc()`.
  Most L ops operate on STANDARD AcDb entities (no issue); only the custom-entity worldDraw path is at risk.

## Op set (27) — feasibility (VERIFY by building)
### L-T01 worldDraw/graphics (8, native_arx, read_safe) — drive AcGiWorldDraw hostless
HIGH feasibility (a custom AcGiWorldDraw/AcGiGeometry collector capturing primitives is hostless):
- `render.draw.worldgeom` (call entity->worldDraw(collector) → capture geometry primitives),
- `render.drawable.def` (AcGiDrawable info: isPersistent/id/setAttributes),
- `render.traits.set` (AcGiSubEntityTraits: color/layer/lineweight on a collector),
- `render.polyline.helper` (AcGiGeometry::polyline/polygon helper capture),
- `render.facedata.attach` (AcGiFaceData attach to a shell/mesh capture),
- `render.context.query` (AcGiWorldDraw/AcGiContext regen-type/query),
- `render.entity.worlddraw_override` (invoke an entity's subWorldDraw and report what it emitted).
DEFER if it needs a live viewport/GS: `render.draw.viewportgeom` (AcGiViewportDraw needs a viewport context).

### L-T02 overrules/grips (19, mostly managed_also, read_safe) — register/query lifecycle is hostless
KEY: an overrule REGISTERS hostless (`AcRxOverrule::addOverrule(AcRxClass*, AcRxOverrule*, bool)`) but its
EFFECT fires during in-app operations. Implement the **register / query / remove / enable lifecycle** (that
IS the op); the effect-firing is attended (note it, don't fake it).
HIGH feasibility (lifecycle): `overrule.install`, `overrule.object.install`, `overrule.drawable.install`,
`overrule.geometry.install`, `overrule.transform.install`, `overrule.osnap.install`, `overrule.subentity.install`,
`overrule.properties.install`, `overrule.highlight.install`, `overrule.highlightstate.install`,
`overrule.visibility.install`, `overrule.grip.install`, `overrule.queryx.install`, `overrule.dimstyle.install`
(each = construct + addOverrule for the matching AcDb*Overrule base, return registered=true + handle/class),
`overrule.global.enable` (AcRxOverrule::setIsOverruling), `overrule.applicable`/`overrule.query.has`
(isApplicable / query registration), `overrule.remove` (removeOverrule), `inspect.entity.grips`
(AcDbEntity::getGripPoints → serialize the grip point list — pure read, hostless).
Defer any that genuinely cannot register/query without the app.

## Canonical patterns
- read/draw op: AriadneReadTransaction (or none), build a collector, emit `r << "\"result\":{...},\"status\":\"ok\"}";`.
- overrule register op: construct a static overrule subclass instance, `AcRxOverrule::addOverrule(AcDbEntity::desc(), pOv, true)`,
  report registered + class; provide a matching remove. (Registration persists for the module session — fine.)
- failure → `emitNativeError(r,CODE,msg); return true;` — never fake ok.

## In-TU helpers
jsonFindString/Number/Object, jsonEscape, njsonStr, handleOf, resolveHandle, serializeEntityCommon,
AriadneReadTransaction, AriadneStagedWriteTransaction, emitNativeError. Plus AcGi*/AcRxOverrule/AcDb*Overrule API.

## Hard constraints
- Hostless on ctx.pDb. NO save()/saveAs()/_QSAVE. NO acedCommand. HasOp↔Dispatch lockstep. Unimplemented OUT of HasOp. NO FAKES.
- UTF-8 via njsonStr. close()/delete AcDb objects correctly. Static overrule instances are fine (module-lifetime).

## Build gate (MUST be exit 0)
`powershell -NoProfile -ExecutionPolicy Bypass -File D:\dev\99_tools\autocad-sdk-router_M08L\tools\build_native_acad.ps1 -RouterHome D:\dev\99_tools\autocad-sdk-router_M08L`
Iterate until final JSON `"status":"ok"` + exit 0. Defer any op that won't link hostless.

## Tests (test_m08l_handlers.py)
Mirror `tests\unit\test_m08d_handlers.py`: HasOp↔Dispatch lockstep, no save/saveAs/acedCommand, sane min count.
Run: `python -m pytest D:\dev\99_tools\autocad-sdk-router_M08L\tests\unit\test_m08l_handlers.py -q` (PYTHONIOENCODING=utf-8).

## Ticket report (reports/tickets/M08L.md)
Implemented (with AcGi*/AcRxOverrule class), deferred (with concrete blocker), build sizes + exit. Honest.

## Commit + report back (do NOT push/PR/merge)
`git -C D:\dev\99_tools\autocad-sdk-router_M08L add -A` then commit `-m "M08L: native graphics system — worldDraw + overrules/grips"`.
Return: implemented count+list, deferred count+reasons, build exit + artifact sizes, unit-test result, commit hash. Precise data.
