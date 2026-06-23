# WAVE4X SUBENTITY BREP Result

- status: **PASS**
- branch: `cados/w4x-subentity-brep`
- claimed ops: 4
- implemented ops: 4
- hard-blocked ops: 0
- claimed catalogued remaining: 0

## Implemented ops

- `edit.subentity.add_paths`
- `edit.subentity.delete_paths`
- `edit.subentity.transform`
- `inspect.assocsurface.topology`

## What changed

### Staged subentity mutation
- Added explicit `AcDbFullSubentPath` parsing helpers in `m08g_handlers.inc`.
- Supports bounded path specs: owning `handle`, `subent_type`, `subent_index`/`marker`, optional `insert_stack`.
- `edit.subentity.{add_paths,delete_paths,transform}` now route through `ARIADNE_NATIVE_JOB` / `m08gDispatch`.
- Mutations are staged-copy only (`write_copy`) and emit before/after subentity readback (`subentPtr`, markers, geom extents).
- No editor picks, no raw AutoCAD commands, no original DWG write.

### Read-only assoc-surface topology
- `inspect.assocsurface.topology` now routes through `ARIADNE_NATIVE_JOB` / `m08kcDispatch`.
- Uses only public static read helpers on `AcDbAssocSurfaceActionBody`:
  - `findActionsThatAffectedTopologicalSubentity`
  - `getTopologicalSubentitiesForActionsOnEntity`
  - `getSurfacesDirectlyDependentOnObject`
- No solver evaluation, repair traversal, xref sync, or modeler mutation.

## Validation

- `python -m pytest tests -q` → **494 passed, 20 skipped**
- `python tools/cadctl_cli.py registry coverage` → **status ok, consistent true**
- `python tools/reconcile_native_registry.py` → **dry-run ok; flips 0, conflicts 0, drift 0**
- isolated native build → **ok**

## Native build artifacts

- `src/Ariadne.AcadNative/bin/x64/Release/Ariadne.AcadNativeDbx.dbx` — 54,272 bytes
- `src/Ariadne.AcadNative/bin/x64/Release/Ariadne.AcadNative.crx` — 777,216 bytes
- `src/Ariadne.AcadNative/bin/x64/Release/Ariadne.AcadNative.arx` — 785,920 bytes

## Notes

- Runtime native-job smoke for the new paths/topology ops remains recorded as `deferred_attended`; closure evidence here is source implementation + unit coverage + native build + registry reconciliation.
- `ui.subentity.highlight` remains outside this pane claim and is still handled separately by the live-editor lane.

## Files

- claims: `reports/tickets/WAVE4X_PANE3_SUBENTITY_BREP_CLAIMS.json`
- plan: `reports/tickets/WAVE4X_SUBENTITY_BREP_PLAN.md`
- report json: `reports/tickets/WAVE4X_SUBENTITY_BREP.json`
- ops: `reports/tickets/WAVE4X_SUBENTITY_BREP_OPS.json`
- native build: `reports/tickets/WAVE4X_SUBENTITY_BREP_native_build.json`
- patch: `handoff/pr/WAVE4X_SUBENTITY_BREP.patch`
- zip: `handoff/tickets/WAVE4X_SUBENTITY_BREP.zip`
