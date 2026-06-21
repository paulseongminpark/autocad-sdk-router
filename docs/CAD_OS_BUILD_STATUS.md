# CAD OS Build Status

Updated: 2026-06-22T05:22:29+09:00

## Current Packet

- M03 Native Router/Rich IR Completion: PASS
- M04 Operation Registry/Tool Surface: PASS
- M05 Patch Diff Validation Transaction: PASS
- M06 Visual Batch Golden Regression: PASS
- Next: CADOS_M07_LIVE_ARX_AND_DEEP_NATIVE_SURFACE

## Native Build

- DBX/CRX: PASS
- ARX: PASS via versioned lock bypass `Ariadne.AcadNative.live_20260622_034352`; AutoCAD was not killed.
- Build log: `reports/build_native_wrapper_latest.log`

## Rich IR

- IR: `runs/m03_rich_ir/dwg_graph_ir.json`
- entities: 21747
- HATCH loops: 702
- xdata blocks/items: 751 / 1069
- xrecords/items: 2 / 7
- non-ASCII: PASS

## Registry

- total: 517
- implemented: 37
- stub: 4
- catalogued: 474
- unknown: 0
- M05 implemented ops: `apply.patch`, `diff.before_after`, `validate.patch`

## Patch / Diff / Validation

- Patch run: `runs/m05_patch_create_line/`
- dry-run: PASS, `runs/m05_patch_create_line/dry_run/dry_run_plan.json`
- staged apply: PASS, `runs/m05_patch_create_line/result.json`
- CAD diff: PASS, `reports/patch_diff_latest.json` (+1 LINE, 0 removed, 0 modified)
- validator: PASS, `reports/validation_latest.json` (14/14 gates)
- journal: `reports/journal_latest.json`
- original DWG modified: no (`27dbf6b95ff72a89fd53b153891187365b9e8ebc4c05a97cfed307057bf49bc8` before/after)

## Visual / Batch / Golden / Performance

- Visual verification: PASS, `reports/visual_verification_latest.json`
- Visual artifacts: `runs/m06_visual_batch_golden/visual/before.svg`, `after.svg`, `overlay.svg`, `visual_diff.json`
- Batch runner: PASS, `reports/batch_latest.json` (4 successes / 0 failures)
- Golden regression: PASS, `reports/golden_regression_latest.json`
- Performance: PASS, `reports/performance_latest.json`
- Large fixture: `runs/native_graph_20260621_234158/result_scale_graph.json`

## Verification

- M06 focused: `28 passed in 1.35s`
- M05/M06 combined focused: `127 passed in 2.78s`
- Full pytest: `260 passed in 74.84s`
- unittest discover: `Ran 223 tests in 18.823s, OK (skipped=3)`
- staging DWG SHA256: `27dbf6b95ff72a89fd53b153891187365b9e8ebc4c05a97cfed307057bf49bc8`
