# Deep native surface (CADOS_M07B) — latest

**Status: PASS.** Data: `reports/deep_native_latest.json`. 10 surfaces implemented/verified;
0 attended_blocked; 0 design_only. Firing residual CLOSED (live counts, headless + attended).

| Surface | Status |
|---|---|
| custom_entity_lifecycle | implemented (probe created attended) |
| worlddraw_rendering | **verified** (circle rendered attended, screenshot) |
| object_overrules | **verified** (live firing: open 2 / close 3, headless+attended) |
| persistent_reactors | **verified** (live firing: command_starts 1 / ends 1, headless+attended) |
| editor_jigs | implemented (drag attended-only) |
| custom_object_filer_versioning | implemented (roundtrip) |
| protocol_extensions | implemented (queryx) |
| acrxproperty_opm | **verified** (property_count 1 + OPM palette open attended) |
| selection_monitor | **verified** (live firing: pickfirst_modified 1 / command_ends 1, headless+attended) |
| palette_status_ui | implemented (MFC-free ARIADNE_PALETTE; docked CAdUiPaletteSet deferred) |

**Live-firing CLOSED:** reactor / overrule / selection-monitor firing COUNTS captured with live data
in BOTH headless and attended via `extend.deep_native.firing_selftest` (overrule = `acdbOpenObject`,
selmon = `acedSSSetFirst`) + `inspect.deep_native.firing_report` (reactor `commandWillStart` on a 2nd
command). No acedCommand reentrancy, no human, zero COM. `reports/firing_latest.json` · `runs/m07b_firing/`.
