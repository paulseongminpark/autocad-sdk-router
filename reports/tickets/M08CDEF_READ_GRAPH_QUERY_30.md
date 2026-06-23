# M08CDEF_READ_GRAPH_QUERY_30 — Read / DB graph / query implementation ticket

## Result

Status: **PASS**
Branch: `cados/m08cdef-read-graph-query-30`

Implemented **30** remaining catalogued operations with native family handlers and registry reconciliation.

Registry totals after reconciliation:

- implemented: **388**
- blocked: **9**
- catalogued: **120**
- unknown/stub: **0**

## Implemented operations

See `reports/tickets/M08CDEF_READ_GRAPH_QUERY_30_OPS.json` for per-op handler/test/evidence metadata.

### m08cDispatch (7)
- `infra.hostapp.set_working_db`
- `inspect.database.flush_input`
- `transaction.manager.start`
- `transaction.manager.get_object`
- `write.object.upgrade_open`
- `write.object.downgrade_open`
- `write.object.close`

### m08eDispatch (9)
- `infra.hostapp.provide_services`
- `acdb.database.create`
- `write.object.create_ext_dict`
- `write.regapp.register`
- `write.dictionary.set`
- `write.entity.set_xdata`
- `write.block.append_entity`
- `transform.database.deep_clone`
- `transform.database.insert_block`

### m08mDispatch (14)
- `inspect.entity.properties`
- `inspect.members.promoted`
- `inspect.value.to_string`
- `extend.members.facet_provider`
- `automate.com.bridge_objectid`
- `automate.com.hold_objectref`
- `automate.com.entity_helpers`
- `automate.com.objectid_from_iunknown`
- `automate.com.lock_document`
- `extend.property.define_collection`
- `extend.property.define_dictionary`
- `extend.property.define_indexed`
- `extend.property.overrule`
- `react.entity.monitor`

## Native build

Isolated native build succeeded. No canonical main deploy.

Command basis:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_native_acad.ps1 \
  -RouterHome D:/dev/99_tools/autocad-sdk-router_m08cdef_read_graph_query \
  -OutputRoot D:/dev/99_tools/autocad-sdk-router_m08cdef_read_graph_query/runs/M08CDEF_READ_GRAPH_QUERY_30_native_canonical
```

Artifacts:

- `runs/M08CDEF_READ_GRAPH_QUERY_30_native_canonical/bin/x64/Release/Ariadne.AcadNativeDbx.dbx` — 48,640 bytes
- `runs/M08CDEF_READ_GRAPH_QUERY_30_native_canonical/bin/x64/Release/Ariadne.AcadNative.crx` — 642,048 bytes
- `runs/M08CDEF_READ_GRAPH_QUERY_30_native_canonical/bin/x64/Release/Ariadne.AcadNative.arx` — 649,728 bytes

## Rich IR / query smoke

CAD router was called first for DWG routing, then cadctl used a staged copy.

DWG: `D:/dev/_ariadne/alm/build/input0616.dwg`

Original hash:

- before: `eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76`
- after:  `eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76`
- `original_dwg_modified`: **false**

Smoke outputs:

- inspect: `python tools/cadctl_cli.py inspect --dwg D:/dev/_ariadne/alm/build/input0616.dwg --out runs/M08CDEF_READ_GRAPH_QUERY_30_rich --mode graph --include-rich` → status `ok`, entity_count `21747`
- query: `select count(*) as n from entities` → `21747`
- validate: status `ok`, validation report `pass`

## Validation

- `python -m pytest tests/unit/test_m08c_handlers.py tests/unit/test_m08e_handlers.py tests/unit/test_m08m_handlers.py -q` → 37 passed
- `python -m pytest tests/unit -q` → 409 passed, 13 skipped
- `python -m pytest tests -q` → **463 passed, 20 skipped**
- `python tools/cadctl_cli.py registry coverage` → status `ok`, consistent `true`
- `python -m json.tool reports/operation_coverage_latest.json` → pass
- `python -m json.tool reports/v1_operation_gate_latest.json` → pass
- `python tools/reconcile_native_registry.py` → dry-run flips `0`, drift `0`, conflicts `0`

## Safety

- No original DWG writes.
- Scratch write-shaped ops use staged transaction rollback or transient in-memory databases/classes.
- No raw command surface was added.
- `tools/autocad-router.ps1` now honors `ARIADNE_NATIVE_ACAD_BIN_DIR` so smokes can load isolated native build artifacts without canonical deployment.
