# Deep native surface (CADOS_M07B) — latest

**Status: PARTIAL_PASS.** Data: `reports/deep_native_latest.json`. 10 surfaces implemented/verified;
0 attended_blocked; 0 design_only.

| Surface | Status |
|---|---|
| custom_entity_lifecycle | implemented (probe created attended) |
| worlddraw_rendering | **verified** (circle rendered attended, screenshot) |
| object_overrules | implemented (registered; live firing residual) |
| persistent_reactors | implemented (registered; live firing residual) |
| editor_jigs | implemented (drag attended-only) |
| custom_object_filer_versioning | implemented (roundtrip) |
| protocol_extensions | implemented (queryx) |
| acrxproperty_opm | **verified** (property_count 1 + OPM palette open attended) |
| selection_monitor | implemented (registry implemented:true; live pickfirst firing residual) |
| palette_status_ui | implemented (MFC-free ARIADNE_PALETTE; docked CAdUiPaletteSet deferred) |

**Live-firing residual:** reactor / overrule / selection-monitor firing COUNTS need synthesized
interactive editor events (command start / entity open / pickfirst pick) the automated zero-COM
harness does not generate. Registered + headless-proven. Deferred to M07C / M08-with-live-partial-review.
No fake PASS.
