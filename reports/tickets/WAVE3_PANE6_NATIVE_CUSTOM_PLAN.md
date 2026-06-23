# WAVE3 Pane 6 Native Custom Object / Filer / Protocol Plan

## Scope

Claim file: `reports/tickets/WAVE3_PANE6_CLAIMS.json` (13 ops).

Claimed operations:

1. `extend.customentity.define`
2. `extend.customentity.draw_viewport`
3. `extend.customentity.draw_world`
4. `extend.customentity.grips`
5. `extend.customentity.osnap`
6. `extend.customentity.stretch`
7. `extend.customobject.define`
8. `extend.customobject.embedded`
9. `extend.customobject.filer_dxfin`
10. `extend.customobject.filer_dxfout`
11. `extend.customobject.partial_undo`
12. `extend.object_enabler.demand_register`
13. `extend.osnap.custom_mode`

## Existing substrate

- `AriadneProbe` is the registered custom `AcDbEntity` in `src/Ariadne.AcadNative/AriadneProbe.*`.
- `AriadneRecord` is the registered custom `AcDbObject` in `src/Ariadne.AcadNativeDbx/AriadneRecord.*`.
- `AriadneProbeProtocol` already proves one protocol-extension path in `src/Ariadne.AcadNativeDbx/AriadneProtocol.*`.
- `m08k_handlers.inc` owns the custom object/entity/protocol lifecycle dispatcher.

## Implementation approach

1. Extend native class bodies instead of adding catalog-only routing:
   - `AriadneProbe`: add viewport draw, grip, osnap, stretch, and embedded-object/DXF evidence hooks.
   - `AriadneRecord`: add partial undo override and DXF in/out observability helpers.
   - DBX exports: add linkage-safe C exports for record value/version/protocol evidence so ARX handlers never directly link to C++ class methods.
2. Add m08k dispatcher handlers for all 13 claimed ops with source-backed or runtime-backed results.
   - Use staged scratch transactions for DB mutations.
   - No original DWG write, no canonical DBX/CRX/ARX deploy, no editor-command reentrancy.
3. Update `tests/unit/test_m08k_handlers.py` from the old deferred contract to the Wave 3 implemented contract.
4. Update `config/operations.v2.json` by running `tools/reconcile_native_registry.py --apply` and, if needed, by explicit evidence/ticket edits so claimed ops have:
   - `status: implemented`
   - `handler.dispatcher_symbol: m08kDispatch`
   - `tests` including `tests/unit/test_m08k_handlers.py`
   - `evidence_refs` including source/report/native build evidence.
5. Validate:
   - `python -m pytest tests -q`
   - `python tools/cadctl_cli.py registry coverage`
   - `python -m json.tool reports/operation_coverage_latest.json`
   - `python -m json.tool reports/v1_operation_gate_latest.json`
   - `python tools/reconcile_native_registry.py`
   - isolated native build and `reports/tickets/WAVE3_PANE6_native_build.json`.
6. Produce final report, machine JSON, ops JSON, packet, patch, zip, and commit on `cados/wave3-pane6-native-custom`.

## Closure policy

Target closure: all 13 `implemented`.
Hard-block only if actual SDK/host/license/safety evidence blocks implementation.
Forbidden closure states (`catalogued`, `stub`, `unknown`, `deferred`, `future_version`, `v1_target_false_escape`) will not remain for claimed ops.
