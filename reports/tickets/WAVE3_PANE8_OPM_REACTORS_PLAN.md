# WAVE3 Pane 8 Plan — OPM / Properties / Reactors

## Scope
Claim file: `reports/tickets/WAVE3_PANE8_CLAIMS.json`

Claimed ops (9):
- `react.docmanager.attach`
- `react.docmanager.monitor`
- `react.editor.command_monitor`
- `react.editor.dwg_lifecycle`
- `react.editor.input_monitor`
- `react.editor.lisp_monitor`
- `react.editor.sysvar_monitor`
- `react.longtx.attach`
- `react.longtx.monitor`

## Implementation plan
1. Extend `src/Ariadne.AcadNative/families/m08m_handlers.inc`.
   - Add real `AcEditorReactor`, `AcApDocManagerReactor`, and `AcApLongTransactionReactor` subclasses.
   - Add attach/detach lifecycle helpers and count snapshots.
   - Keep headless/CoreConsole honest via host gating (`supported:false` / no fake firing).
   - Add bounded safe probes where practical:
     - doc-manager lock/unlock round-trip
     - editor pickfirst/input round-trip
     - editor sysvar change/restore round-trip
   - Avoid raw command dispatch, original DWG writes, and canonical deploy.
2. Add safe cleanup wiring in `src/Ariadne.AcadNative/AriadneNativeJob.cpp` unload path.
3. Update tests.
   - Expand `tests/unit/test_m08m_handlers.py` for the 9 new implemented ops.
   - Add a Wave3 registry/claim test to ensure all claimed ops leave `catalogued` and land in the registry as implemented.
4. Reconcile registry.
   - Run `python tools/reconcile_native_registry.py --apply`.
   - Manually enrich the 9 records with Pane 8 evidence refs / ticket ownership if needed.
5. Validate.
   - `python -m pytest tests -q`
   - `python tools/cadctl_cli.py registry coverage`
   - `python tools/reconcile_native_registry.py`
   - `python -m json.tool reports/operation_coverage_latest.json`
   - isolated native build under `reports/tickets/native/WAVE3_PANE8_OPM_REACTORS`
6. Produce deliverables.
   - `reports/tickets/WAVE3_PANE8_OPM_REACTORS.md`
   - `reports/tickets/WAVE3_PANE8_OPM_REACTORS.json`
   - `reports/tickets/WAVE3_PANE8_OPM_REACTORS_OPS.json`
   - `packets/tickets/WAVE3_PANE8_OPM_REACTORS.md`
   - `handoff/tickets/WAVE3_PANE8_OPM_REACTORS.zip`
   - `handoff/pr/WAVE3_PANE8_OPM_REACTORS.patch`
