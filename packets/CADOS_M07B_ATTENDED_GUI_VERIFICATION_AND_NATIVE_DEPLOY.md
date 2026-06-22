# CADOS_M07B_ATTENDED_GUI_VERIFICATION_AND_NATIVE_DEPLOY (packet record)

Source packet: `D:\dev\_ariadne\alm\docs\CADOS_M07B_ATTENDED_GUI_VERIFICATION_AND_NATIVE_DEPLOY.md`
Executed by: aclaude (workflow+ultracode → inline keystone, per the M07 precedent — the native
build/attended-GUI loop is a serial single-build single-instance keystone, not safely fanned out).

**Result: PARTIAL_PASS.** Report: `reports/CADOS_M07B_ATTENDED_GUI_VERIFICATION_AND_NATIVE_DEPLOY.md`.

## Delivered

- Pump-gating C++ integrated (host-EXE gate `hostIsFullAutoCad()`): attended `highlight 2/2`,
  `clear 2/2`, `inspect_selection` real; `zoom`/`render` honestly deferred (acedCommand reentrancy);
  headless 17/17 preserved.
- `ARIADNE_NATIVE_JOB_ARGS` env-file job channel finalized (M07A blocker resolved) +
  `docs/LIVE_JOB_ARGUMENT_CONTRACT.md`.
- MFC-free palette `ARIADNE_PALETTE` (arx-only TU); docked CAdUiPaletteSet deferred (build stability).
- Native build canonical (`.dbx` 48128 / `.crx` 247808 / `.arx` 255488).
- Dedicated-instance attended GUI verification (`tools/attended/run_attended_m07b.ps1`, zero COM,
  run `cados_m07b_attended_20260622_123505`): live pump host_mode full_autocad, real highlight/selection,
  worldDraw circle rendered, OPM palette open, custom entity created; 3 safety gates pass; golden read-only.
- pytest 294 passed / 3 skipped (9 new M07B source guards).

## Residual

Reactor / overrule / selection-monitor LIVE FIRING counts (need synthesized interactive editor events).
Implemented + registered + headless-proven. → carried to M08 live-partial review.

NEXT: `CADOS_M08_FULL_OPERATION_COVERAGE_CLOSURE_WITH_LIVE_PARTIAL_REVIEW`.
