# M08KC — native constraints / associativity (AcDbAssoc*) (58 ops)

You implement native ObjectARX handlers in ONE file: `m08kc_handlers.inc` (M08K-T03).

## Worktree / paths (ABSOLUTE ONLY — never `cd`, never relative)
- ROOT: `D:\dev\99_tools\autocad-sdk-router_M08KC`
- CHANGE_ONLY:
  - `D:\dev\99_tools\autocad-sdk-router_M08KC\src\Ariadne.AcadNative\families\m08kc_handlers.inc`
  - `D:\dev\99_tools\autocad-sdk-router_M08KC\tests\unit\test_m08kc_handlers.py`
  - `D:\dev\99_tools\autocad-sdk-router_M08KC\reports\tickets\M08K-T03.md`
- Do NOT touch AriadneNativeJob.cpp / .vcxproj / registry / other family `.inc`. Seam wires `m08kcHasOp`/`m08kcDispatch`.
- git: `git -C D:\dev\99_tools\autocad-sdk-router_M08KC ...`. shell: absolute paths.

## Mission
Fill `m08kc_handlers.inc` (stub) with real handlers for the feasible-hostless subset of the AcDbAssoc*
associativity/constraints network; HONESTLY defer the solver/modeler-bound rest (out of HasOp + blocker).
**NO FAKES.** Runs hostless on `ctx.pDb`.

## Reference (READ FIRST)
- Read-handler + serializer pattern: `families\m08c_handlers.inc` / `m08d_handlers.inc` (serializeObjectCommon,
  njsonStr, AriadneReadTransaction). Staged-write/create pattern: `families\m08g_handlers.inc` +
  `AriadneStagedWriteTransaction` / appendLine in AriadneNativeJob.cpp (~line 2036, 2936).
- Headers: AcDbAssocAction/AcDbAssocNetwork (`dbassocnetwork.h`/`dbassocaction.h`), AcDbAssoc2dConstraintGroup
  + AcDbGeomConstraint (`dbConstraintsInterface.h` / `AcConstraintGroupNode.h`), AcDbAssocArray
  (`dbassocarray.h`), AcDbAssocDependency. Link via the acdb import libs (no extra lib expected; if a symbol
  needs an extra .lib, find it via dumpbin like M08D's acbr26.lib and `#pragma comment(lib, <abs>)` in the .inc).

## Op set (58) — feasibility (VERIFY by building)
HIGH feasibility hostless — objectdbx_capable, staged_write/read_safe (implement these; DB-resident assoc/
constraint objects create + read without the live solver):
- assoc network/action: `define.assocaction.create`/`.addDependency`/`.valueParam`,
  `define.assocnetwork.addAction`, `edit.assocnetwork.removeAction`, `inspect.assocnetwork.get`/`.iterate`,
  `inspect.assocaction.dependencies`/`.requestToEvaluate`, `inspect.assocmanager.state`,
  `config.assocmanager.evalDisabler`.
- dependencies: `define.assocdependency.attach`, `define.assocgeomdependency.subent`,
  `define.assocvaluedependency.value`, `define.georef.subent`, `define.perssubentid.resolve`.
- constraints: `define.constraint.addGeometry`, `.geometric`, `.group`, `.dimensional.angle`/`.distance`/
  `.radiusDiameter`, `edit.constraint.delete`, `inspect.constraint.enumerate`/`.node`/`.status`/
  `.dimensional.value`.
- parameters: `define.parameter.variable`/`.merge`, `inspect.parameter.evaluate`.
- assoc arrays (DB-resident): `define.assocarray.create`/`.rectangular`/`.polar`/`.path`,
  `edit.assocarray.item`/`.itemReplace`/`.reset`/`.source`/`.transform`, `inspect.assocarray.identify`.
DEFER (honest, out of HasOp + blocker) — native_arx_only + risk live_edit; need the in-app evaluation
SOLVER or the ASM surface modeler, not available hostless:
- `define.assocsurface.*` (blend/extrude/fillet/loft/offset/patch/result/trim — ASM modeler),
- `inspect.assocaction.evaluate`, `inspect.assocnetwork.evaluate`, `define.constraint.autoConstrain`,
  `define.dimassoc.geometryDriven`, `edit.assocarray.explode`, `edit.assocdata.xref`,
  `inspect.assocsurface.topology`, `repair.assocdata.audit`, `config.assoceval.callback`,
  `config.constraint.globalCallback` (global eval callbacks fire in-app).
Roughly ~39 objectdbx_capable feasible vs ~19 native solver-bound → defer the solver/modeler/callback ones.

## Canonical patterns
- create/staged op: `AriadneStagedWriteTransaction txn(ctx.pDb)` → create the AcDbAssoc*/constraint object,
  add to the assoc network / db, `txn.commit()`. dtor rolls back on failure. Emit handle + result.
- inspect op: `AriadneReadTransaction` → walk the assoc network → serialize. NO solver eval.
- On failure: `emitNativeError(r,CODE,msg); return true;` — never fake ok.

## In-TU helpers
jsonFindString/Number/Object, jsonEscape, njsonStr, handleOf, resolveHandle, serializeObjectCommon,
AriadneReadTransaction, AriadneStagedWriteTransaction, emitNativeError. Plus all AcDbAssoc*/AcDbGeomConstraint API.

## Hard constraints
- Hostless on ctx.pDb. NO save()/saveAs()/_QSAVE on original. NO acedCommand. **Do NOT call the constraint
  evaluation solver** (AcDbAssocAction::evaluate / network evaluate) — that's the deferred set.
- HasOp ↔ Dispatch lockstep. Unimplemented OUT of HasOp. NO FAKES. UTF-8 via njsonStr. Correct close()/delete.

## Build gate (MUST be exit 0)
`powershell -NoProfile -ExecutionPolicy Bypass -File D:\dev\99_tools\autocad-sdk-router_M08KC\tools\build_native_acad.ps1 -RouterHome D:\dev\99_tools\autocad-sdk-router_M08KC`
Iterate until final JSON `"status":"ok"` + exit 0. Defer any op that won't link hostless.

## Tests (test_m08kc_handlers.py)
Mirror `tests\unit\test_m08d_handlers.py`: HasOp↔Dispatch lockstep, no save/saveAs/acedCommand, no solver-eval
call in implemented ops, sane min count. Run: `python -m pytest D:\dev\99_tools\autocad-sdk-router_M08KC\tests\unit\test_m08kc_handlers.py -q` (PYTHONIOENCODING=utf-8).

## Ticket report (reports/tickets/M08K-T03.md)
Implemented (with AcDbAssoc* class), deferred (with concrete blocker — "needs in-app eval solver" / "ASM modeler"), build sizes + exit. Honest.

## Commit + report back (do NOT push/PR/merge)
`git -C D:\dev\99_tools\autocad-sdk-router_M08KC add -A` then commit `-m "M08K-T03: native constraints/associativity (AcDbAssoc*)"`.
Return: implemented count+list, deferred count+reasons, build exit + artifact sizes, unit-test result, commit hash. Precise data, not prose.
