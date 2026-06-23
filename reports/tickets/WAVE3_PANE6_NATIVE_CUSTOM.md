# WAVE3 Pane 6 Native Custom Object / Filer / Protocol Result

- status: **PARTIAL_PASS**
- branch: `cados/wave3-pane6-native-custom`
- claimed ops: 13
- implemented ops: 12
- hard-blocked ops: 1
- claimed catalogued remaining: 0

## Implemented ops

- `extend.customentity.define`
- `extend.customentity.draw_viewport`
- `extend.customentity.draw_world`
- `extend.customentity.grips`
- `extend.customentity.osnap`
- `extend.customentity.stretch`
- `extend.customobject.define`
- `extend.customobject.embedded`
- `extend.customobject.filer_dxfin`
- `extend.customobject.filer_dxfout`
- `extend.customobject.partial_undo`
- `extend.osnap.custom_mode`

## Hard-blocked ops

- `extend.object_enabler.demand_register` — hard-blocked: install-time HKLM/ObjectDBX demand-load registration requires canonical DBX deploy/registry write; Pane 6 native build rule permits isolated build only and says canonical deploy is Pane 1 only.

## Native implementation evidence

- `AriadneProbe` now implements custom entity lifecycle callbacks: `subWorldDraw`, `subViewportDraw`, grip, osnap, stretch, transform/extents, and embedded `AcDbCircle` worldDraw forwarding.
- `AriadneRecord` now implements `applyPartialUndo` plus exported value/set helpers for linkage-safe ARX dispatch evidence.
- `m08kDispatch` now handles the claimed custom object/entity/DXF/partial-undo/custom-osnap operations (except the hard-blocked demand-register install op).
- `extend.osnap.custom_mode` attaches an `AcDbCustomOsnapInfo` protocol extension and registers/removes a custom osnap mode when the manager is available.

## Validation

- `python -m pytest tests -q` → 464 passed, 20 skipped
- `python tools/cadctl_cli.py registry coverage` → status ok, consistent true
- `python -m json.tool reports/operation_coverage_latest.json` → ok
- `python -m json.tool reports/v1_operation_gate_latest.json` → ok
- `python tools/reconcile_native_registry.py` → flips=0, conflicts=0, drift=0
- isolated native build → ok; canonical deploy not performed

## Native build

- `runs/wave3_pane6_native_build_final/bin/x64/Release/Ariadne.AcadNativeDbx.dbx` exists=True bytes=54272
- `runs/wave3_pane6_native_build_final/bin/x64/Release/Ariadne.AcadNative.crx` exists=True bytes=676864
- `runs/wave3_pane6_native_build_final/bin/x64/Release/Ariadne.AcadNative.arx` exists=True bytes=684544

## Files

- plan: `reports/tickets/WAVE3_PANE6_NATIVE_CUSTOM_PLAN.md`
- ops: `reports/tickets/WAVE3_PANE6_NATIVE_CUSTOM_OPS.json`
- native_build: `reports/tickets/WAVE3_PANE6_native_build.json`
- report: `reports/tickets/WAVE3_PANE6_NATIVE_CUSTOM.md`
- packet: `packets/tickets/WAVE3_PANE6_NATIVE_CUSTOM.md`
- patch: `handoff/pr/WAVE3_PANE6_NATIVE_CUSTOM.patch`
- zip: `handoff/tickets/WAVE3_PANE6_NATIVE_CUSTOM.zip`
