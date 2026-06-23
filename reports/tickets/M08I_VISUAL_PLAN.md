# M08I_VISUAL_PLAN — visual render, plot, and diff overlay

This plan covers the visual family implementation and registry validation for the M08I phase.

## A. WILL IMPLEMENT / UPDATE

1. **Registry Operations (config/operations.v2.json)**
   * **`plot.config.settings`**: Update status from `catalogued` to `blocked`.
     * Blocker reason: `Requires full_autocad plot/publish host; page setups / plot settings not runnable headlessly (no-fake-success).`
   * **`plot.engine.run`**: Update status from `catalogued` to `blocked`.
     * Blocker reason: `Requires full_autocad plot/publish host; plot engine beginPlot/endPlot not runnable headlessly (no-fake-success).`
   * **`render.layout`**: Remains `blocked` with blocker reason: `Requires full_autocad plot/publish host; no headless render path implemented (no-fake-success).`
   * Update the `totals` block at the top of `operations.v2.json`:
     * Decrement `catalogued` count by 2.
     * Increment `blocked` count by 2.

2. **Visual Capabilities Mapping (tools/visual_report.py)**
   * Headless plotting (PDF/PNG) is natively blocked on this host due to Core Console locale prompt desync and ActiveX COM absence.
   * Feasible visual routes are fulfilled by the pure-stdlib `ir_svg` route.
   * `render.modelspace` filters entities on `space == "model"`.
   * `render.with_overlay` is fully supported via `overlay.svg` (stroking created/modified handles red).
   * Extents/Zoom/Viewport metadata is computed and exposed as 2D bounding boxes in `viewbox` ([minx, miny, width, height]).

## B. TESTS TO RUN
1. `python -m pytest tests/unit/test_visual_report.py -q`
2. `python tools/cadctl_cli.py registry coverage`
