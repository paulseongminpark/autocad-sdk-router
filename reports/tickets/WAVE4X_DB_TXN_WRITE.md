# WAVE4X DB TXN WRITE

## What landed

- Generic staged native mutation governor in `tools/patch_engine.py::apply_native_staged` (stage copy -> pre/post inspect -> diff -> validate -> journal -> original-hash proof).
- Router native cad-job gate in `tools/autocad-router.ps1` now honors registry `handler.router_lane == ARIADNE_NATIVE_JOB`, so newly implemented native family ops no longer fall through to the managed unsupported path.
- `m08e` staged-write residual handlers now commit staged mutations on success instead of scratch rollback-only probes.
- `m08kc` reopens `edit.assocdata.xref` and `repair.assocdata.audit` under a bounded staged-write contract.
- `live.apply_patch` is deprecated in favor of staged governors (`apply.patch` / `apply_native_staged`).

## Claim closeout

- `edit.assocdata.xref` -> **implemented**
- `repair.assocdata.audit` -> **implemented**
- `live.apply_patch` -> **deprecated**

## Implemented staged-safe subset

- `transaction.manager.start`
- `transaction.manager.get_object`
- `write.object.close`
- `write.object.upgrade_open`
- `write.object.downgrade_open`
- `write.object.create_ext_dict`
- `write.regapp.register`
- `write.dictionary.set`
- `write.entity.set_xdata`
- `write.block.append_entity`
- `transform.database.deep_clone`
- `transform.database.insert_block`
- `edit.assocdata.xref`
- `repair.assocdata.audit`

## Smoke

- `write.block.append_entity`: status=ok, validation=pass, out=`runs\wave4x_smoke_write_block_append_entity`
- `write.dictionary.set`: status=ok, validation=fail, out=`runs\wave4x_smoke_write_dictionary_set`
- `repair.assocdata.audit`: status=ok, validation=fail, out=`runs\wave4x_smoke_repair_assocdata_audit`
- `edit.assocdata.xref`: status=ok, validation=fail, out=`runs\wave4x_smoke_edit_assocdata_xref`

Notes: non-graph mutations (`write.dictionary.set`, `repair.assocdata.audit`, `edit.assocdata.xref`) commit on the staged copy and keep the original hash unchanged, but the current graph diff/validator stack does not yet surface non-entity DB mutations as diff-visible changes, so those smoke runs end with `validation_status=fail` on the zero-diff gate. Entity-appending smoke (`write.block.append_entity`) passes end-to-end.

## Validation

- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/build_native_acad.ps1` -> `status: ok`
- `python -m pytest tests -q` -> `493 passed, 20 skipped`
- `python tools/cadctl_cli.py registry coverage` -> `status: ok` (implemented 459 / blocked 57 / deprecated 1)
- `python tools/reconcile_native_registry.py` -> dry-run clean, 419 coded ops, 0 conflicts, 0 drift
