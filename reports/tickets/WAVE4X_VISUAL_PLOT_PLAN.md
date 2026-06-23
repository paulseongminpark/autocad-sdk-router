# WAVE4X VISUAL PLOT PLAN

This plan maps out the implementation strategy, verification methods, and validation rules for the visual, render, plot, and page setup operations within the Pane 7 scope.

## 1. Target Operations & Implementation Strategy

| Operation ID | Family | Strategy | Implementation Route & Details |
|---|---|---|---|
| `plot.config.settings` | `layouts_plot_publish` | **Implement** | Retrieve the active layout or layout specified by the job, query its plot settings (device, media name, paper size, rotation, units, scale, plot type), and serialize them to JSON. Support write mode (`live_edit`) to update these plot settings in a transaction and return the updated properties. |
| `plot.engine.run` | `layouts_plot_publish` | **Implement** | Implement a native C++ runner using `AcPlPlotEngine` and `AcPlPlotFactory`. If the AutoCAD plot host or display device is unavailable (such as in headless `accoreconsole`), return a structured `HOST_UNAVAILABLE` error honestly. If a valid plot device (e.g. `DWG To PDF.pc3`) and layout are configured, attempt to write the plot output to the specified staged output path. |

## 2. Attended / Headless Verification Plan

* **Headless Verification**: The operations will be invoked via `cadctl` in `accoreconsole`. `plot.config.settings` will run in read and write mode on a staged drawing copy. `plot.engine.run` will check host capability and report `HOST_UNAVAILABLE` honestly if the plot engine cannot be instantiated or if no device matches.
* **Attended Verification**: An attended execution script will run inside a graphical AutoCAD session, utilizing `DWG To PDF.pc3` to plot the staged drawing layout to a real PDF file in the staged directory.
* **No Fake screenshot PASS**: We do not capture fake screenshot success; we verify generated plot configuration metadata and check that the generated PDF contains valid vector data.

## 3. Files to Edit

* `src/Ariadne.AcadNative/families/m08l_handlers.inc` - Implement C++ handlers for `plot.config.settings` and `plot.engine.run`. Wire them into `m08lHasOp` and `m08lDispatch`.
* `config/operations.v2.json` - Reopen `plot.config.settings` and `plot.engine.run` by promoting their status from `blocked` to `implemented` and setting `implementation_strategy` to `implemented`.
* `tests/unit/test_wave3_render_plot_registry_safety.py` - Update test expectations to assert that the plot operations are now `implemented`.

## 4. Tests to Run

* Native build: `powershell -File tools/build_native_acad.ps1`
* Python unit tests: `python -m pytest tests -q`
* Coverage check: `python tools/cadctl_cli.py registry coverage`
