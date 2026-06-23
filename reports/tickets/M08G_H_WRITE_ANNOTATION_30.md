# M08G/H WRITE+ANNOTATION 30 — result

## Status

PASS — implemented 30 additional catalogued native operations on branch `cados/m08g-h-write-annotation-30`.

## Implemented ops (30)

### M08G entities (4)
- `write.entity.attribute`
- `write.entity.mline`
- `write.entity.polyfacemesh`
- `write.entity.shape`

### M08H annotations (3)
- `write.entity.leader`
- `write.entity.mleader`
- `write.entity.table`

### M08E block/dictionary/xdata/database create (7)
- `infra.hostapp.provide_services`
- `transform.database.deep_clone`
- `transform.database.insert_block`
- `write.block.append_entity`
- `acdb.database.create`
- `write.dictionary.set`
- `write.entity.set_xdata`

### M08C database/object/transaction operations (16)
- `infra.hostapp.set_working_db`
- `inspect.database.read_dwg`
- `inspect.database.read_dwg_handle`
- `inspect.database.dxf_in`
- `inspect.database.flush_input`
- `transform.database.dxf_out`
- `transform.database.save_as`
- `transform.database.save_as_simple`
- `write.object.close`
- `write.object.downgrade_open`
- `write.object.upgrade_open`
- `transform.database.wblock_clone`
- `write.object.create_ext_dict`
- `write.regapp.register`
- `transaction.manager.start`
- `transaction.manager.get_object`

## Safety notes

- No raw AutoCAD command surface was added (`acedCommand`, `acedCmd`, `acedInvoke` remain absent from touched handlers).
- Mutating handlers operate on the router-staged `ctx.pDb` only.
- Export handlers (`save_as`, `save_as_simple`, `dxf_out`) require explicit `out`/`output_path` and reject `input_path == output_path` with `ORIGINAL_WRITE_FORBIDDEN`.
- `infra.hostapp.set_working_db` restores the previous working database before returning.
- Native build used isolated output under `reports/tickets/native/M08G_H_WRITE_ANNOTATION_30`.

## Registry

`config/operations.v2.json` reconciled from native HasOp:
- implemented: 358 -> 388
- catalogued: 150 -> 120
- blocked: 9 unchanged
- touched catalogued remaining: 0

## Validation

- `python -m pytest tests -q` → `464 passed, 20 skipped`
- `python tools/cadctl_cli.py registry coverage` → `status: ok`, `consistent: true`, `implemented: 388`, `catalogued: 120`
- `python tools/operation_coverage_matrix.py` → `GATE PASS: True`
- `powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_native_acad.ps1 -RouterHome 'D:/dev/99_tools/autocad-sdk-router_m08g_h_write_annotation' -OutputRoot 'reports/tickets/native/M08G_H_WRITE_ANNOTATION_30'` → `status: ok`

Native artifacts:
- `reports/tickets/native/M08G_H_WRITE_ANNOTATION_30/bin/x64/Release/Ariadne.AcadNativeDbx.dbx` — 48,640 bytes
- `reports/tickets/native/M08G_H_WRITE_ANNOTATION_30/bin/x64/Release/Ariadne.AcadNative.crx` — 664,064 bytes
- `reports/tickets/native/M08G_H_WRITE_ANNOTATION_30/bin/x64/Release/Ariadne.AcadNative.arx` — 673,792 bytes

## Files changed

- `src/Ariadne.AcadNative/families/m08c_handlers.inc`
- `src/Ariadne.AcadNative/families/m08e_handlers.inc`
- `src/Ariadne.AcadNative/families/m08g_handlers.inc`
- `src/Ariadne.AcadNative/families/m08h_handlers.inc`
- `tests/unit/test_m08c_handlers.py`
- `tests/unit/test_m08e_handlers.py`
- `tests/unit/test_m08g_handlers.py`
- `tests/unit/test_m08h_handlers.py`
- `config/operations.v2.json`
- generated coverage/build/ticket artifacts under `reports/`

## Not run

Attended AutoCAD smoke was not run; this ticket is hostless/native-build + unit/registry validated.
