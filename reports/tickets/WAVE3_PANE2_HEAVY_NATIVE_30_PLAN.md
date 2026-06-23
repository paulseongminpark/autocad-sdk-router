# WAVE3 Pane 2 — Heavy Native / Live / Visual / Editor Builder plan

## Preconditions

- Worktree: `D:\dev\99_tools\autocad-sdk-router_wave3_pane2`
- Branch: `cados/wave3-pane2-heavy-native-30`
- Base/source commit: `023fc16` (Pane 1 dependency branches merged into `main`).
- Claim file copied into this worktree from Pane 1 output and validated with `python -m json.tool`:
  `reports/tickets/WAVE3_PANE2_CLAIMS.json`.

## Claimed operations (21)

### Heavy staged entity / modeler ops (M08G, 13)
1. `write.entity.body`
2. `write.entity.mpolygon`
3. `write.entity.nurbsurface`
4. `write.entity.rasterimage`
5. `write.entity.solid3d.extrude`
6. `write.entity.solid3d.loft`
7. `write.entity.solid3d.primitive`
8. `write.entity.solid3d.revolve`
9. `write.entity.solid3d.sweep`
10. `write.entity.subdmesh`
11. `write.entity.surface`
12. `write.entity.wipeout`
13. `modify.entity.solid3d.boolean`

### Constraint / associativity authoring ops (M08KC, 8)
14. `define.constraint.addGeometry`
15. `define.constraint.autoConstrain`
16. `define.constraint.dimensional.angle`
17. `define.constraint.dimensional.distance`
18. `define.constraint.dimensional.radiusDiameter`
19. `define.constraint.geometric`
20. `define.constraint.group`
21. `define.dimassoc.geometryDriven`

## Implementation route per op

### M08G heavy entity/modeler

Target source: `src/Ariadne.AcadNative/families/m08g_handlers.inc`.

- `write.entity.solid3d.primitive`: construct `AcDb3dSolid`, call `createBox`/`createSphere`/`createWedge`/etc. from `dbsol3d.h`, append via existing staged model-space append helper.
- `write.entity.solid3d.extrude`: create an in-memory closed `AcDbPolyline` profile and call `AcDb3dSolid::createExtrudedSolid` with `AcDbSweepOptions`.
- `write.entity.solid3d.revolve`: create in-memory closed profile and call `AcDb3dSolid::createRevolvedSolid` with `AcDbRevolveOptions`.
- `write.entity.solid3d.sweep`: create in-memory profile + path (`AcDbPolyline`/`AcDbLine`) and call `AcDb3dSolid::createSweptSolid` with `AcDbSweepOptions`.
- `write.entity.solid3d.loft`: create two in-memory profile entities and call `AcDb3dSolid::createLoftedSolid` with `AcDbLoftOptions`.
- `modify.entity.solid3d.boolean`: resolve two `AcDb3dSolid` handles, clone or operate on the target in the staged DB, call `booleanOper` with an operation enum selected from JSON.
- `write.entity.body`: instantiate `AcDbBody` and append as a DB-resident AcDb entity if SDK allows an empty body object; if runtime returns invalid object append status, report structured error but keep real handler.
- `write.entity.surface`: create a closed in-memory polyline profile and call `AcDbSurface::createFrom` to make a planar surface, append the returned surface.
- `write.entity.nurbsurface`: use `AcDbNurbSurface` (from `dbsurf.h`) with a minimal rectangular point grid if constructor/API is exposed; otherwise hard-block only with SDK evidence.
- `write.entity.subdmesh`: call `AcDbSubDMesh::setBox` or `setSubDMesh` and append.
- `write.entity.mpolygon`: include/link `dbmpolygon.h` + `AcMPolygonObj.lib`, create SOLID pattern MPolygon from vertices via `appendMPolygonLoop` + `evaluateHatch`/`balanceDisplay`, append.
- `write.entity.rasterimage`: include/link `imgdef.h`/`imgent.h` + `acismobj26.lib`; require `image_path`, create `AcDbRasterImageDef` in the image dictionary, set source/active file, then append `AcDbRasterImage` oriented on staged DB. Missing `image_path` is a validation error, not a fake success.
- `write.entity.wipeout`: include/link `dbwipe.h` + `acismobj26.lib`; create image definition via `AcDbWipeout::createImageDefinition`, construct clipped wipeout boundary where SDK permits; otherwise hard-block only if the WipeOut RX service/ISM object cannot be linked/loaded.

### M08KC constraints/associativity

Target source: `src/Ariadne.AcadNative/families/m08kc_handlers.inc`.

- `define.constraint.group`: create `AcDbAssoc2dConstraintGroup` with `AcGePlane::kXYPlane`, post to staged DB, add to top assoc network under `AcDbAssocNetworkEvaluationDisabler`.
- `define.constraint.addGeometry`: open group by `group_handle` or create one, construct `AcDbFullSubentPath` from `target_handle` + subent type/index, call `addConstrainedGeometry`.
- `define.constraint.geometric`: call `addGeometricalConstraint` on either supplied paths or created constrained geometry pointers; default to horizontal/coincident-style simple cases.
- `define.constraint.dimensional.distance`: call `addDistanceConstraint` on two constrained geometry nodes; value dependency/dim dependency optional/null.
- `define.constraint.dimensional.angle`: call `addAngleConstraint` where two constrained lines are available; otherwise return structured `INVALID_INPUT`.
- `define.constraint.dimensional.radiusDiameter`: call `addRadiusDiameterConstraint` on circle/ellipse constrained geometry.
- `define.constraint.autoConstrain`: call `autoConstrain` on supplied full subent paths with tolerance and null callback; no top-level network evaluate call.
- `define.dimassoc.geometryDriven`: create `AcDbDimAssoc`/assoc dim dependency object where SDK symbols are exposed; if required headers/libs are not present, hard-block with `SDK_NOT_EXPOSED` evidence.

## Expected source/test files

- `src/Ariadne.AcadNative/families/m08g_handlers.inc`
- `src/Ariadne.AcadNative/families/m08kc_handlers.inc`
- `tests/unit/test_m08g_handlers.py`
- `tests/unit/test_m08kc_handlers.py`
- `tests/unit/test_wave3_pane2_claims.py` (cross-check claim closure/registry/evidence)
- `config/operations.v2.json`
- `reports/tickets/WAVE3_PANE2_*`
- generated coverage reports under `reports/`

## Attended requirements

- Primary implementation is hostless ObjectDBX/CoreConsole native source + source-level tests + isolated native build.
- Some modeler/constraint paths may require live AutoCAD/graphics/modeler runtime to prove success. If a dedicated attended instance/channel/staged DWG is not safely available, verification is recorded as `pending_attended`; the handler remains implemented if SDK call and error handling are real.
- No attended run will touch user session/original DWG.

## Isolated native build strategy

Run only isolated build output:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_native_acad.ps1 `
  -RouterHome D:\dev\99_tools\autocad-sdk-router_wave3_pane2 `
  -OutputRoot reports\tickets\native\WAVE3_PANE2
```

Do not canonical deploy `.dbx/.crx/.arx`.

## Blocker criteria

Only use hard-block when supported by evidence:

- `SDK_NOT_EXPOSED`: required class/method/header/import library absent in ObjectARX 2027.
- `HOST_UNAVAILABLE`: requires an attended/full AutoCAD service unavailable to the safe runner and cannot be expressed as source support.
- `LICENSE_UNAVAILABLE`: installed SDK/runtime lacks a licensed component.
- `SAFETY_FORBIDDEN`: would require raw command execution or unsafe user-session/original-DWG mutation.
- `OBJECT_ENABLER_REQUIRED`: custom/proxy/enabler service is required and absent.
- `ORIGINAL_WRITE_FORBIDDEN`: operation semantics require writing original source, not staged/derived output.

Complexity, bespoke implementation effort, or pending attended verification are not blockers.
