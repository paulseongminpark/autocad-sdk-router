# CADOS_M07B — Attended GUI Verification + Native Deploy Closure

**Status: PARTIAL_PASS.** No fake PASS. Original golden DWG unchanged. No remote push.

Built by Claude (aclaude) on the M07A commit `5db2e6c`. Closes the M07/M07A attended
residue: the pump-gating real-execution path, the env-file job channel, the palette
skeleton, and a real dedicated-instance attended GUI verification.

## Outcome summary

| Area | Result |
|---|---|
| Native build (.dbx/.crx/.arx) | **canonical** — 48128 / 247808 / 255488 |
| Pump-gating C++ | **integrated + tested** (real highlight/selection attended; honest zoom/render deferral; headless 17/17 preserved) |
| Palette | **implemented** (MFC-free `ARIADNE_PALETTE`, arx-only; docked CAdUiPaletteSet MFC enhancement deferred) |
| Live job argument channel | **finalized** (`ARIADNE_NATIVE_JOB_ARGS` env-file; M07A blocker resolved) |
| Attended live pump | **verified** in dedicated acad.exe (host_mode full_autocad) |
| Pump-gating real execution | **verified** (highlight 2/2, clear 2/2, selection real path) |
| worldDraw pixel | **verified** (custom-entity circle rendered, screenshot) |
| OPM AcRxProperty "Size" | **verified** (registration property_count=1 + OPM palette open) |
| Reactor/overrule/selection-monitor LIVE FIRING | **residual** (implemented + registered + headless-proven; live firing needs interactive events) |
| pytest | **294 passed, 3 skipped** |
| Original DWG | **unchanged** (sha 27dbf6b9…) |

## 1. Pump-gating (the real deep-native advance)

The 5 formerly-`attended_only` pump ops now gate on `hostIsFullAutoCad()` — a reliable
host-EXE discriminator (`acad.exe` vs `accoreconsole.exe`). Two earlier gate attempts
were wrong and corrected by evidence:
- `hostMode == "full_autocad"` (env hint) — the env var did **not** propagate into the
  attended process (only `ARIADNE_PUMP_PIPE` did), so the gate never fired attended.
- `acedEditor != nullptr` — **acedEditor is non-null in accoreconsole too** (it has an
  AcEditor singleton), so it broke the headless 17/17.

The host-EXE name is bulletproof. Under the gate, the **command-free** AcDb/ADS ops
execute for real (safe inside the modal `CADAGENT_PUMP` command):
- `live.inspect_selection` → `acedSSGet("_I", …)` pickfirst set.
- `live.highlight_handles` → `AcDbEntity::highlight()`.
- `live.clear_highlight` → `AcDbEntity::unhighlight()`.

`live.zoom_to_handles` / `live.render_view` need an `acedCommand` context, which **cannot**
run reentrantly from inside the modal pump command — so they return `status:"deferred"`
with `editor_present:true` and the exact reason. **Not faked.** Headless accoreconsole keeps
the honest `attended_only` stub (17/17 preserved).

## 2. Live job argument channel (M07A blocker resolved)

`ARIADNE_NATIVE_JOB_ARGS` (env var) → a run-scoped JSON args file
`{job_in, job_out, host_mode}` (forward-slash, UTF-8). The `ARIADNE_NATIVE_JOB_ARGS`
command reads it once, non-interactively, and runs the dispatcher (key `operation`).
Interactive prompts remain only as a documented fallback. Headless-proven
(`runs/m07b_native_smoke`): `inspect.probe.property_count → property_count 1`,
`inspect.runtime.capabilities`, `inspect.selection.monitor.registry` — golden unchanged.
Contract: `docs/LIVE_JOB_ARGUMENT_CONTRACT.md`.

## 3. Palette (MFC-free, build-stable)

`AriadnePalette.cpp` is an **arx-only** TU (in `Ariadne.AcadNative.arx.vcxproj` only;
its registration is `#ifndef ARIADNE_NATIVE_CRX`), registering `ARIADNE_PALETTE` → an
`acedAlert` status surface. A full docked `CAdUiPaletteSet` needs MFC, which would change
this ObjectARX module's runtime/linkage and risk the existing (non-MFC) build — so the
skeleton is intentionally MFC-free, and the docked palette is the deliberately deferred
enhancement (packet: *do not destabilize the existing build*).

## 4. Attended GUI verification (run `cados_m07b_attended_20260622_123505`)

Harness `tools/attended/run_attended_m07b.ps1` (zero-COM): a **dedicated** `acad.exe`
launched (`/b startup.scr`), arxload `.dbx`+`.arx`, create an `AriadneProbe` via the
env-file channel, zoom + open Properties, then serve `CADAGENT_PUMP` on a **unique pipe**.

**Three safety gates — all pass:** dedicated instance (no pre-existing acad.exe; PID 51708
distinct) · staged document (golden only copied from) · unique live channel (pipe name
carries run_id; clean shutdown). User session never touched; only the launched PID closed.

**`ATTENDED_PUMP_OK: True` (10/10 checks):**
- pump running in real acad.exe, `host_mode:"full_autocad"`, modelspace 21748 (= 21747 + 1 probe);
- `live.highlight_handles` → `highlighted:2/2` (**real** `AcDbEntity::highlight`); `clear:2/2`;
- `live.inspect_selection` → real `acedSSGet` path (honest empty: no pickfirst);
- `live.zoom_to_handles` / `live.render_view` → `deferred` (`editor_present:true`, honest);
- `extend.customclass.create` → `created:true, ariadne_probes_after:1` (custom entity in attended);
- screenshot `screenshots/acad_window.png`: real AutoCAD 2027 window, **OPM Properties palette open**,
  **magenta worldDraw circle marker** in the viewport.

## 5. Honest residual (why PARTIAL_PASS, not PASS)

The **live firing counts** of the persistent reactor, object overrule, and selection
monitor (`AriadneEditorReactor::commandWillStart`, `AriadneObjectOverrule::open/close`,
`AriadneSelectionMonitor::pickfirstModified`) were **not captured**. They are implemented,
registered, and headless-proven (registry ops report `implemented:true`), but their live
firing requires **synthesized interactive editor events** (a command running while the
reactor is enabled; an `AriadneProbe` opened while the overrule is enabled; an interactive
pickfirst pick). The automated zero-COM pump harness drives the named-pipe pump but does
not generate genuine interactive editor events; doing so reliably needs a human operator or
a fragile UI-automation layer. **No fake PASS** — recorded as the exact blocker.

Also PARTIAL on the OPM screenshot specificity: the Properties palette is open and rendered,
but the specific "Size" row is not isolated/zoomed in the capture (registration is
independently proven by `property_count=1`).

## 6. NEXT

`CADOS_M08_FULL_OPERATION_COVERAGE_CLOSURE_WITH_LIVE_PARTIAL_REVIEW` — the build + live
structured counters pass; the firing residual carries forward as a live-partial review item.

## Evidence index

- `reports/attended_gui_latest.json` · `reports/live_pump_latest.json` · `reports/deep_native_latest.json`
- `reports/opm_property_latest.json` · `reports/worlddraw_latest.json` · `reports/native_smoke_latest.json`
- `reports/live_job_args_contract_latest.json` · `reports/attended_shutdown_latest.json`
- `runs/cados_m07b_attended_20260622_123505/` (plan, pump result, probe-create result, screenshots)
- `runs/m07b_native_smoke/` · `runs/m07_pump_test/`
- `docs/LIVE_JOB_ARGUMENT_CONTRACT.md`
- tests: `tests/unit/test_m07b_pump_gating_and_job_channel.py` (9) + existing M07/M07A guards
