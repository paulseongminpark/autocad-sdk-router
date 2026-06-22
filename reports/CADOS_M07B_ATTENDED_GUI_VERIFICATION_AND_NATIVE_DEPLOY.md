# CADOS_M07B — Attended GUI Verification + Native Deploy Closure

**Status: PASS.** No fake PASS. Original golden DWG unchanged. No remote push.

> Originally closed PARTIAL_PASS on the reactor/overrule/selection-monitor live-firing
> residual; that residual is now **CLOSED** — live firing counts captured in BOTH headless
> and attended via `extend.deep_native.firing_selftest` + `inspect.deep_native.firing_report`
> (no acedCommand reentrancy, no human, zero COM). The 3 `CADOS_LIVE=1`-gated tests also run +
> pass (298 passed / 0 skipped under `CADOS_LIVE=1`). See §5 + `reports/firing_latest.json`.

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
| Reactor/overrule/selection-monitor LIVE FIRING | **verified** (live counts, headless + attended: reactor 1/1, overrule 2/3, selmon 1/1) |
| pytest | **295 passed / 3 skipped** (default) · **298 passed / 0 skipped** (`CADOS_LIVE=1`) |
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

## 5. Firing residual — CLOSED (was the only PARTIAL reason)

The **live firing counts** of the persistent reactor, object overrule, and selection
monitor are now captured with live counts in BOTH headless and attended, with **no
acedCommand reentrancy, no human, zero COM** — via two new native ops:

- `extend.deep_native.firing_selftest` (cmd1, `ARIADNE_NATIVE_JOB_ARGS`): enables all three,
  ensures a probe, then **FIRES the overrule** by `acdbOpenObject(probe)` (invokes
  `AriadneObjectOverrule::open/close`) and **FIRES the selection monitor** by
  `acedSSSetFirst(NULL, ss)` (invokes `AriadneSelectionMonitor::pickfirstModified`).
- `inspect.deep_native.firing_report` (cmd2, `ARIADNE_NATIVE_JOB_MAILBOX`): the reactor was
  registered in cmd1, so **cmd2's start fires `commandWillStart`**, read here.

Captured counts (identical headless + attended — the surfaces are DB/editor-level, host-independent):

| surface | counts |
|---|---|
| reactor (`AriadneEditorReactor`) | `command_starts:1, command_ends:1` |
| overrule (`AriadneObjectOverrule`) | `open_calls:2, close_calls:3, global_overruling:true` |
| selection monitor (`AriadneSelectionMonitor`) | `pickfirst_modified:1, command_ends:1` |

Harness `runs/m07b_firing/run_firing.ps1` (`-Mode headless|attended`); evidence
`reports/firing_latest.json`. Original golden unchanged in both runs. A stale headless
registry string ("selection callbacks never fire") was corrected — the live count disproves it.

The OPM "Size" registration is proven by `property_count=1`; the Properties palette is shown
open in the attended screenshot.

The 3 `CADOS_LIVE=1`-gated live-AutoCAD tests (live pump round-trip, native graph router,
native inspect) were also **run and passed**: `298 passed / 0 skipped` under `CADOS_LIVE=1`
(default no-env run keeps them as honest env-gated skips: `295 passed / 3 skipped`).

## 6. NEXT

`CADOS_M08_FULL_OPERATION_COVERAGE_CLOSURE` — M07B is a full PASS (no live-partial carry).

## Evidence index

- `reports/attended_gui_latest.json` · `reports/live_pump_latest.json` · `reports/deep_native_latest.json`
- `reports/opm_property_latest.json` · `reports/worlddraw_latest.json` · `reports/native_smoke_latest.json`
- `reports/live_job_args_contract_latest.json` · `reports/attended_shutdown_latest.json`
- `runs/cados_m07b_attended_20260622_123505/` (plan, pump result, probe-create result, screenshots)
- `runs/m07b_native_smoke/` · `runs/m07_pump_test/`
- `docs/LIVE_JOB_ARGUMENT_CONTRACT.md`
- tests: `tests/unit/test_m07b_pump_gating_and_job_channel.py` (9) + existing M07/M07A guards
