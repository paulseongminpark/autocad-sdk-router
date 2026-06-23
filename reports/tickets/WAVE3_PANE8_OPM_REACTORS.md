# WAVE3 Pane 8 Result — OPM / Properties / Reactors

## Status

PASS

## Scope

- Claim file: `reports/tickets/WAVE3_PANE8_CLAIMS.json`
- Claimed ops: **9**
- Implemented ops: **9**
- Hard-blocked ops: **0**
- Deprecated ops: **0**
- Catalogued remaining in scope: **0**

## Implemented operations (9)

- `react.docmanager.attach`
- `react.docmanager.monitor`
- `react.editor.command_monitor`
- `react.editor.dwg_lifecycle`
- `react.editor.input_monitor`
- `react.editor.lisp_monitor`
- `react.editor.sysvar_monitor`
- `react.longtx.attach`
- `react.longtx.monitor`

## Native implementation summary

- Extended `src/Ariadne.AcadNative/families/m08m_handlers.inc` with real `AcEditorReactor`, `AcApDocManagerReactor`, and `AcApLongTransactionReactor` subclasses.
- Added full-host registration helpers, counter snapshots, bounded safe probes (`pickfirst`, `CMDECHO`, current-doc lock/unlock), and structured monitor results.
- Added unload cleanup wiring in `src/Ariadne.AcadNative/AriadneNativeJob.cpp` for the new monitor registrations.
- Updated `tests/unit/test_m08m_handlers.py` and added `tests/unit/test_wave3_pane8_registry.py`.
- Reconciled the registry so all 9 claimed ops are `implemented` and point at `m08mDispatch`.

## Validation

- `python -m pytest tests -q` — **PASS** (469 passed, 20 skipped)
- `python tools/cadctl_cli.py registry coverage` — **PASS** (consistent=true; implemented=411 blocked=9 catalogued=97)
- `python tools/reconcile_native_registry.py` — **PASS** (dry-run clean for m08m and repo-wide families; flips=0 drift=0 conflicts=0)
- `python -m json.tool reports/operation_coverage_latest.json` — **PASS** (operation_coverage_latest.json parses; implemented=411 blocked=9 catalogued=97)

## Native build

- Isolated output: `reports/tickets/native/WAVE3_PANE8_OPM_REACTORS`
- `D:\dev\99_tools\autocad-sdk-router_wave3_pane8_opm_reactors\reports\tickets\native\WAVE3_PANE8_OPM_REACTORS\bin\x64\Release\Ariadne.AcadNativeDbx.dbx` — exists=True bytes=48640
- `D:\dev\99_tools\autocad-sdk-router_wave3_pane8_opm_reactors\reports\tickets\native\WAVE3_PANE8_OPM_REACTORS\bin\x64\Release\Ariadne.AcadNative.crx` — exists=True bytes=690176
- `D:\dev\99_tools\autocad-sdk-router_wave3_pane8_opm_reactors\reports\tickets\native\WAVE3_PANE8_OPM_REACTORS\bin\x64\Release\Ariadne.AcadNative.arx` — exists=True bytes=697856

## Registry impact

- `reports/operation_coverage_latest.json`: implemented=411 blocked=9 catalogued=97
- `python tools/reconcile_native_registry.py` dry-run is clean for `m08m` (no flips/drift/conflicts remain).

## Notes

- No claimed op remains `catalogued`, `stub`, `unknown`, or `deferred`.
- No claimed op was hard-blocked or deprecated in this ticket.
- Live command/LISP/dwg-lifecycle/long-transaction callbacks still require a dedicated attended AutoCAD host to accumulate non-zero runtime counts, and the handler reports that honestly.

