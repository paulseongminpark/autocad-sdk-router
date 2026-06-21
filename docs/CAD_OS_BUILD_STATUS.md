# CAD OS Build Status

Updated: 2026-06-22T03:55:00+09:00

## Current Packet

- M03 Native Router/Rich IR Completion: PASS
- M04 Operation Registry/Tool Surface: PASS
- Next: CADOS_M05_PATCH_DIFF_VALIDATION_TRANSACTION

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
- implemented: 34
- catalogued: 474
- unknown: 0
