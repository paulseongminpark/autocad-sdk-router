# CAD OS Takeover

Current status: M03–M06 PASS, **M07 PARTIAL_PASS**, **M07A** implemented + build-verified,
**M07B PARTIAL_PASS** (attended GUI verification + native deploy closure). Deep native now
10/10 implemented-or-verified (0 attended_blocked); the residual is reactor/overrule/
selection-monitor LIVE FIRING counts.

**M07B re-entry — read first:** `reports/CADOS_M07B_ATTENDED_GUI_VERIFICATION_AND_NATIVE_DEPLOY.md`,
`reports/attended_gui_latest.json`, `reports/{live_pump,deep_native}_latest.json`,
`docs/LIVE_JOB_ARGUMENT_CONTRACT.md`. Attended evidence:
`runs/cados_m07b_attended_20260622_123505/` (screenshots + pump result). Native build:
`tools/build_native_acad.ps1` (canonical: .dbx 48128 / .crx 247808 / .arx 255488). Re-run attended:
`tools/attended/run_attended_m07b.ps1` (dedicated acad.exe, zero COM, unique pipe, 3 safety gates).
Next packet: **CADOS_M08_FULL_OPERATION_COVERAGE_CLOSURE_WITH_LIVE_PARTIAL_REVIEW**.

Start from `reports/latest_status.json`, then read:

- `reports/CADOS_M03_NATIVE_ROUTER_RICH_IR_COMPLETION.md`
- `reports/CADOS_M04_OPERATION_REGISTRY_AND_TOOL_SURFACE.md`
- `reports/CADOS_M05_PATCH_DIFF_VALIDATION_TRANSACTION.md`
- `reports/CADOS_M06_VISUAL_BATCH_GOLDEN_REGRESSION.md`
- `reports/CADOS_M07_LIVE_ARX_AND_DEEP_NATIVE_SURFACE.md`
- `reports/live_pump_latest.json`
- `reports/deep_native_latest.json`
- `reports/rich_ir_latest.json`
- `reports/operation_coverage_latest.json`
- `reports/tool_surface_latest.json`
- `reports/mcp_contract_latest.json`
- `reports/patch_diff_latest.json`
- `reports/validation_latest.json`
- `reports/journal_latest.json`
- `reports/visual_verification_latest.json`
- `reports/batch_latest.json`
- `reports/golden_regression_latest.json`
- `reports/performance_latest.json`

M07 evidence: `runs/m07_pump_test/` (accoreconsole + pipe client, 17/17, original golden unchanged),
`tests/unit/test_pump_frame_codec.py` (11), `tests/unit/test_pump_shutdown_and_deep_native_source.py` (16),
`docs/LIVE_ARX_PUMP_SPIKE_REPORT.md`, `docs/NATIVE_DEEP_SURFACE_STATUS.md`.

Next packet: CADOS_M08_FULL_OPERATION_COVERAGE_CLOSURE.

Boundaries: no original DWG writes, no remote push, no Daedalus app logic yet (close the CAD OS v1 gate first; M09 freeze, M10 burn-down if M09 not PASS).
