# Attended GUI verification (CADOS_M07B) — latest

**Status: PASS** · run `cados_m07b_attended_20260622_123505` (+ firing run, dedicated PID 36096).
Structured data: `reports/attended_gui_latest.json` · `reports/firing_latest.json`.

- **Live pump in real acad.exe** — `host_mode:full_autocad`, modelspace 21748 (21747 golden + 1 probe), echo/status/list/active/stop all ok.
- **Pump-gating real execution** — `highlight 2/2`, `clear 2/2`, `inspect_selection` real path (honest empty). `zoom`/`render` honestly `deferred` (editor_present, acedCommand reentrancy). These same ops are `attended_only` headless.
- **Custom entity (worldDraw)** — `extend.customclass.create` made an AriadneProbe in attended (`ariadne_probes_after:1`); the magenta circle marker renders in the viewport (`screenshots/acad_window.png`).
- **OPM AcRxProperty "Size"** — registration proven headless (`property_count:1`); Properties palette open in the screenshot. Specific "Size" row not isolated in the capture.
- **Safety** — 3 gates pass (dedicated / staged / unique pipe); golden read-only (sha 27dbf6b9 unchanged); launched PID closed; no user session touched; zero COM.
- **Firing CLOSED** — reactor (1/1) + overrule (2/3) + selmon (1/1) live counts captured in BOTH headless and attended via `firing_selftest` + `firing_report` (overrule=`acdbOpenObject`, selmon=`acedSSSetFirst`, reactor=`commandWillStart` on a 2nd command). No acedCommand reentrancy, no human, zero COM. `reports/firing_latest.json`.

Screenshots: `runs/cados_m07b_attended_20260622_123505/screenshots/{acad_window,primary_screen}.png`.
