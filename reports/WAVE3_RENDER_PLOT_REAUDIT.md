# Wave3 Render/Plot Registry Re-Audit

Scope: final no-fake-PASS audit of render/plot records that were already marked implemented before this integration pass.

## render.layout

Decision: implemented, but registry handler evidence was corrected.

The actual CAD OS render route is the deterministic IR to SVG visual report path implemented by `tools/visual_report.py::build_visual_report`, surfaced through `cad.visual_report`. It does not call AutoCAD plot/publish or mutate an original DWG.

Evidence:
- `tools/visual_report.py`
- `tests/unit/test_visual_report.py`

## plot.config.settings

Decision: hard-blocked.

Blocker: SAFETY_FORBIDDEN.

The registry record describes a read/write named page setup and plot configuration operation with `default_write_mode: live_edit`. This tree has no bounded CAD OS handler for exact plot-settings mutation or a staged validation contract. Leaving it implemented would be a fake PASS.

## plot.engine.run

Decision: hard-blocked.

Blocker: HOST_UNAVAILABLE.

The exact operation drives the AutoCAD plot engine (`AcPlPlotEngine` begin/end plot sequence), which requires a controlled attended/full AutoCAD plot host. No controlled attended plot route is available in this integration validation, so the operation is not agent-exposed as implemented.
