# WAVE4X Visual Plot Attended Verification Plan

This plan details the strategy for verifying `plot.config.settings` and `plot.engine.run` under an active, attended desktop AutoCAD environment.

## 1. Objective
Verify layout plot configuration settings and successful `AcPlPlotEngine` creation in a full desktop AutoCAD host.

## 2. Design of the attended harness
We implement `tools/attended/run_attended_visual_plot.ps1` modeled on the existing attended harness pattern.

### Key rules and invariants
- **Dedicated AutoCAD instance**: query active `acad.exe` PIDs before launch and ensure the launched instance uses a distinct PID. Only the launched PID is terminated.
- **Staged DWG**: the golden baseline DWG (`staging/dwg_20260617_191504/input.dwg`) is copied to a unique staged directory (`staging/attended_visual/<run_id>/attended.dwg`).
- **No Original Write**: original DWG hashes are verified before and after the run to prove they are unmodified.
- **Unique Live Channel**: a unique named pipe (`\\.\pipe\ariadne-cadagent-visual-plot-<run_id>`) is opened for the CAD agent pump.
- **Verification Client**: `attended_visual_client.py` connects to the pipe, drives the pump, invokes `plot.config.settings`, and runs `plot.engine.run`.

## 3. Deliverables
- `tools/attended/run_attended_visual_plot.ps1`
- `tools/attended/attended_visual_client.py`
- `reports/tickets/WAVE4X_FAST_B_VISUAL_ATTENDED_R2.md`
- `reports/tickets/WAVE4X_FAST_B_VISUAL_ATTENDED_R2.json`
- `reports/visual_plot_attended_latest.md`
- `reports/visual_plot_attended_latest.json`
