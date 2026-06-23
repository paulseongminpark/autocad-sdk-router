# M08CDEF_READ_GRAPH_QUERY_30 PLAN

Branch: `cados/m08cdef-read-graph-query-30`  
Worktree: `D:/dev/99_tools/autocad-sdk-router_m08cdef_read_graph_query`  
Baseline: `main` at `0ec8b08` with registry totals implemented=358 / blocked=9 / catalogued=150.

## Mission
Implement at least 30 remaining catalogued operations from read/database graph/entity inspect/query-adjacent families without changing original DWG sources. Do not close feasible reads as future work; any hard-block must carry a real blocker code.

## Candidate operation set (30+)

Primary implementation candidates are hostless/ObjectDBX/native read or staged-scratch operations. The exact first-pass target set is 34 candidates; at least 30 must be implemented, otherwise shortfall gets evidence-backed blockers.

### M08C / M08B database + transaction handlers (12)
1. `infra.hostapp.set_working_db`
2. `inspect.database.read_dwg`
3. `inspect.database.read_dwg_handle`
4. `inspect.database.dxf_in`
5. `inspect.database.flush_input`
6. `write.object.upgrade_open`
7. `write.object.close`
8. `write.object.downgrade_open`
9. `transaction.manager.start`
10. `transaction.manager.get_object`
11. `transform.database.dxf_out` (only if safe output arg is present; otherwise honest blocker)
12. `transform.database.save_as_simple` (only if safe output arg is present; otherwise honest blocker)

### M08E dictionary/block/xdata/clone handlers (8)
13. `infra.hostapp.provide_services`
14. `acdb.database.create`
15. `write.object.create_ext_dict`
16. `write.regapp.register`
17. `write.dictionary.set`
18. `write.entity.set_xdata`
19. `write.block.append_entity`
20. `transform.database.deep_clone`

### M08M/M08O reflective read handlers (8)
21. `inspect.entity.properties`
22. `inspect.members.promoted`
23. `inspect.value.to_string`
24. `extend.members.facet_provider`
25. `automate.com.bridge_objectid`
26. `automate.com.hold_objectref`
27. `automate.com.entity_helpers`
28. `automate.com.objectid_from_iunknown`

### M08M reactors / graph-adjacent read or staged-scratch handlers (6)
29. `react.entity.monitor`
30. `react.longtx.attach`
31. `react.longtx.monitor`
32. `react.docmanager.attach` (full AutoCAD/doc-manager only; likely hard-block if no hostless SDK surface)
33. `react.docmanager.monitor` (full AutoCAD/doc-manager only; likely hard-block if no hostless SDK surface)
34. `react.editor.command_monitor` (editor reactor only; likely hard-block if attended-only)

### M08D subentity inspection hard-block checks (not counted unless truly implementable)
- `inspect.subentity.color`
- `inspect.subentity.markers_at_path`
- `inspect.subentity.path_at_marker`
- `ui.subentity.highlight`

## Handler files
- `src/Ariadne.AcadNative/families/m08c_handlers.inc` for database/transaction/object lifecycle probes.
- `src/Ariadne.AcadNative/families/m08e_handlers.inc` for dictionary, xdata, ext-dict, block append, clone scratch probes.
- `src/Ariadne.AcadNative/families/m08m_handlers.inc` for AcRx property/member/value reflection and reactor extras.
- `tests/unit/test_m08c_handlers.py`, `tests/unit/test_m08e_handlers.py`, `tests/unit/test_m08m_handlers.py` for source contract updates.
- `config/operations.v2.json` via `tools/reconcile_native_registry.py --apply` where handlers are real.

## Generic dispatcher opportunities
- Extend existing `m08cHasOp/m08cDispatch`, `m08eHasOp/m08eDispatch`, and `m08mHasOp/m08mDispatch` rather than adding one-off top-level dispatcher paths.
- Reuse in-TU utilities: `AriadneReadTransaction`, `AriadneStagedWriteTransaction`, `resolveHandle`, `serializeObjectCommon`, `serializeEntityCommon`, `dictionaryEntriesJson`, `xdataBlocksJson`, `njsonStr`, `jsonFind*`.
- Prefer scratch, rollback-only staged mutations where an op is inherently write-copy (`write.object.create_ext_dict`, `write.dictionary.set`, xdata registration, block append, deep clone). No original persistence.

## SQLite/query updates
- Existing `query.entities` and `sqlite_ir_store.py` remain the query surface for rich IR. If new query operations are not present in `operations.v2.json`, do not invent them for count. Rich IR/query smokes will validate that the graph and SQLite query path still work.

## Tests
- Update family exact implemented-set tests for newly implemented ops.
- Add source-safety assertions for scratch-write handlers: staged transaction only, no save/QSAVE/writeDwgFile, no raw commands, no commit where rollback proof is required.
- Add ticket-specific operation list/report tests if needed.
- Full validation commands from packet will be run before commit.

## Isolated native build strategy
- Use `tools/build_native_acad.ps1` with isolated output parameters (`-OutputRoot` and ticket suffix if available) so no canonical `.dbx/.crx/.arx` deploy occurs.
- If native build cannot be completed due host/toolchain availability, record exact command, output, and blocker. Do not fake native PASS.

## Hard-block criteria
Only use hard-block for touched operations with concrete evidence:
- `HOST_UNAVAILABLE`: full editor/doc-manager/interactive GS required and no hostless ObjectDBX/CoreConsole surface exists.
- `SDK_NOT_EXPOSED`: SDK header/import surface does not expose the required call in this build.
- `SAFETY_FORBIDDEN`: raw command/original-DWG mutation would be required.
- `ORIGINAL_WRITE_FORBIDDEN`: op cannot be performed without writing original input.

## DWG safety
- CAD-like source access will go through the shared AutoCAD router first.
- Any smoke uses staged/router copies only.
- Original hash before/after will be recorded when a DWG fixture is used.
