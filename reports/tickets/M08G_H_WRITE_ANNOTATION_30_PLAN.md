# M08G/H WRITE+ANNOTATION 30 — plan

## Scope

Worktree: `D:\dev\99_tools\autocad-sdk-router_m08g_h_write_annotation`  
Branch: `cados/m08g-h-write-annotation-30`

Goal: close at least 30 remaining catalogued staged write / annotation / symbol/style/database mutation operations with native ObjectARX handlers, registry updates, unit tests, native build evidence, report JSON/packet/handoff, and local commit.

## Safety invariants

- No original DWG write. All persistent mutations operate on `ctx.pDb`, the router-staged working database/copy.
- No raw AutoCAD command surface (`acedCommand`, `acedCmd`, `acedInvoke`, `sendstring` remain forbidden).
- Any file export/write op must require an explicit output path and write only a derivative artifact, never the source DWG.
- Host-global working-db changes, if exercised, must restore the previous working database before return.
- No fake pass: unsupported external-resource/modeler/editor-only ops become `blocked` in registry/report with a concrete hard-block code.

## Planned implemented ops (target 31)

### M08H annotation entities (3)
1. `write.entity.leader` — `AcDbLeader`, `appendVertex`, default `pDb->dimstyle()`, optional annotation mtext.
2. `write.entity.mleader` — `AcDbMLeader`, `setContentType(kMTextContent)`, `setMText`, leader line vertices.
3. `write.entity.table` — `AcDbTable`, `setTableStyle(pDb->tablestyle())`, `setSize`, row/column dimensions, cell text.

### M08G staged entity writes (3)
4. `write.entity.attribute` — append `AcDbAttribute` to an existing `AcDbBlockReference` instance by handle.
5. `write.entity.mline` — `AcDbMline`, `setStyle(pDb->cmlstyleID())`, `appendSeg`, optional closed/scale.
6. `write.entity.polyfacemesh` — `AcDbPolyFaceMesh`, append vertices and face records.

### M08E block/dictionary/xdata writes (7)
7. `infra.hostapp.provide_services` — verify host services are present/provided; report product + working DB.
8. `transform.database.deep_clone` — `AcDbDatabase::deepCloneObjects` selected handles into staged model space.
9. `transform.database.insert_block` — create an in-memory source DB and `AcDbDatabase::insert` it as a staged block definition.
10. `write.block.append_entity` — append a minimal line/text entity into model space or a named/handled BTR.
11. `acdb.database.create` — construct/delete an in-memory `AcDbDatabase`; report default tables/entities.
12. `write.dictionary.set` — set an `AcDbXrecord` into NOD or a target dictionary via `AcDbDictionary::setAt`.
13. `write.entity.set_xdata` — register regapp if needed and attach minimal xdata (`1001` + `1000`) to an object.

### M08C staged database/object operations (16)
14. `infra.hostapp.set_working_db` — temporarily set working DB to `ctx.pDb`, then restore previous DB.
15. `inspect.database.read_dwg` — read a side DWG into a new side database and count model space.
16. `inspect.database.read_dwg_handle` — read side DWG and resolve/report one handle.
17. `inspect.database.dxf_in` — DXF-in to a new side database and count model space.
18. `inspect.database.flush_input` — `ctx.pDb->closeInput(true)` on the staged database.
19. `transform.database.dxf_out` — write staged DB to explicit derivative DXF output path.
20. `transform.database.save_as` — write staged DB to explicit derivative DWG output path.
21. `transform.database.save_as_simple` — same safe staged `saveAs` path with default version.
22. `write.object.close` — open target object and close it; report `errorstatus`.
23. `write.object.downgrade_open` — open target kForWrite, downgrade, then close.
24. `write.object.upgrade_open` — open target kForRead, upgrade, downgrade/close.
25. `transform.database.wblock_clone` — `wblockCloneObjects` selected handles to a new in-memory destination DB owner.
26. `write.object.create_ext_dict` — open target kForWrite and create extension dictionary.
27. `write.regapp.register` — `AcDbDatabase::registerApp` / `isAppRegistered` on staged DB.
28. `transaction.manager.start` — start/end a native transaction via `AcTransactionManager`.
29. `transaction.manager.get_object` — transaction-managed `getObject` by handle.

### Stretch if compile-safe (2)
30. `write.entity.shape` — only if default text/shape style and name can create a valid DB-resident `AcDbShape`; otherwise hard-block as `OBJECT_ENABLER_REQUIRED`/external SHX.
31. `write.entity.subdmesh` or other mesh/surface op only if a non-modeler ObjectARX creation path is verified; otherwise hard-block.

## Planned hard-blocked ops

- ASM/ShapeManager/modeler-bound: `write.entity.solid3d.*`, `modify.entity.solid3d.boolean`, `write.entity.body`, `write.entity.surface`, `write.entity.nurbsurface`, `write.entity.subdmesh` if no safe hostless constructor path.
- External resource/enabler-bound: `write.entity.rasterimage`, `write.entity.wipeout`, `write.entity.mpolygon`, possibly `write.entity.shape`.
- Subentity edit ops requiring editor pick/associative full subentity paths: `edit.subentity.*`.

## Tests / validation

- Update source-level unit tests for changed families:
  - `tests/unit/test_m08g_handlers.py`
  - `tests/unit/test_m08h_handlers.py`
  - `tests/unit/test_m08e_handlers.py`
  - `tests/unit/test_m08c_handlers.py`
  - add focused `tests/unit/test_m08g_h_write_annotation_30.py` if useful for cross-family count/safety.
- Reconcile `config/operations.v2.json` from native HasOp; manually mark hard-blocked touched ops as `blocked` with evidence.
- Validation commands:
  - `python -m pytest tests -q`
  - `python tools/cadctl_cli.py registry coverage`
  - `powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_native_acad.ps1 -RouterHome <worktree> -OutputRoot reports/tickets/native/M08G_H_WRITE_ANNOTATION_30 -TargetSuffix .m08g_h_write_annotation_30`

## Outputs

- `reports/tickets/M08G_H_WRITE_ANNOTATION_30.md`
- `reports/tickets/M08G_H_WRITE_ANNOTATION_30.json`
- `packets/tickets/M08G_H_WRITE_ANNOTATION_30.md`
- `handoff/tickets/M08G_H_WRITE_ANNOTATION_30.zip`
- local commit on `cados/m08g-h-write-annotation-30`
