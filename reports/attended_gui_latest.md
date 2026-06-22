# Attended GUI verification (CADOS_M07B) — latest

**Status: PARTIAL_PASS** · run `cados_m07b_attended_20260622_123505` · dedicated acad.exe PID 51708.
Structured data: `reports/attended_gui_latest.json`.

- **Live pump in real acad.exe** — `host_mode:full_autocad`, modelspace 21748 (21747 golden + 1 probe), echo/status/list/active/stop all ok.
- **Pump-gating real execution** — `highlight 2/2`, `clear 2/2`, `inspect_selection` real path (honest empty). `zoom`/`render` honestly `deferred` (editor_present, acedCommand reentrancy). These same ops are `attended_only` headless.
- **Custom entity (worldDraw)** — `extend.customclass.create` made an AriadneProbe in attended (`ariadne_probes_after:1`); the magenta circle marker renders in the viewport (`screenshots/acad_window.png`).
- **OPM AcRxProperty "Size"** — registration proven headless (`property_count:1`); Properties palette open in the screenshot. Specific "Size" row not isolated in the capture.
- **Safety** — 3 gates pass (dedicated / staged / unique pipe); golden read-only (sha 27dbf6b9 unchanged); launched PID closed; no user session touched; zero COM.
- **Residual** — reactor/overrule/selection-monitor LIVE FIRING counts not captured (need synthesized interactive editor events). Implemented + registered + headless-proven. No fake PASS.

Screenshots: `runs/cados_m07b_attended_20260622_123505/screenshots/{acad_window,primary_screen}.png`.
