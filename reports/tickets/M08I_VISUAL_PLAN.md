# M08I_VISUAL_PLAN — visual render, plot, and diff overlay (Reopened)

This plan covers the visual family implementation, attended verification strategies, and registry validation for the M08I phase.

## A. IMPLEMENTATION ROUTING DECISIONS

1. **`render.layout`**: **Implemented**
   * **Route**: Option 3 (Existing router/cadctl render path).
   * **Details**: Fulfills rendering layout space to standard SVG format via the existing `ir_svg` vector path in `visual_report.py`.
   * **Host Eligibility**: Works on `dbx`, `coreconsole`, `arx_adapter`, and `full_autocad`.

2. **`plot.config.settings`**: **Implemented**
   * **Route**: Option 3 (Existing router/cadctl render path / ObjectDBX).
   * **Details**: Read/write of named page setups and plot configurations (`AcDbPlotSettings` database objects) is fully supported headlessly via the `arx_adapter` and ObjectDBX without requiring an attended host.

3. **`plot.engine.run`**: **Implemented (Attended Verification)**
   * **Route**: Option 2 (Full AutoCAD attended controlled route).
   * **Details**: Marked as requiring attended verification because running the plotting engine (`AcPlPlotEngine` beginPlot/endPlot) is host-bound (requires ActiveX automation COM / graphics subsystem present in full AutoCAD).
   * **Strategy**: Below is the detailed attended implementation and verification plan.

---

## B. ATTENDED IMPLEMENTATION & VERIFICATION PLAN

For operations requiring a live display, ActiveX Automation server, or user interaction, verification is routed to an attended host.

### 1. Attended Plot Engine Run Protocol (`plot.engine.run`)
* **Objective**: Plot a drawing layout to a physical/vector device (e.g., PDF) using the native plot engine.
* **Control Mechanism**:
  1. Instantiate full AutoCAD using standard COM Automation (`AutoCAD.Application`).
  2. Access the active document's layout dictionary and plot settings.
  3. Query `AcPlPlotConfigMgr` to fetch available system printer devices (e.g., `DWG To PDF.pc3`).
  4. Call `AcPlPlotEngine::beginPlot` via the ObjectARX adapter to start the document plotting pipeline.
  5. Commit `beginDocument` -> `beginPage` -> `endPage` -> `endDocument` -> `endPlot`.
* **Execution Environment**: Windows Desktop, AutoCAD 2027 with valid license and graphics hardware acceleration.
* **Verification steps**:
  1. Launch full AutoCAD attended session.
  2. Execute `plot.engine.run` via the runner.
  3. Verify that a valid, non-empty PDF file is generated in the output directory.
  4. Visually inspect the PDF output to confirm layout entities match drawing geometry.

### 2. Attended Layout Render Verification (`render.layout`)
* **Objective**: Attended layout visualization to verify rasterization fidelity.
* **Verification steps**:
  1. Boot AutoCAD with display adapter enabled.
  2. Plot active layout viewport to a PNG device (`PublishToWeb PNG.pc3`).
  3. Compare generated PNG geometry against the headless `ir_svg` output.

---

## C. TESTS TO RUN
1. `python -m pytest tests/unit/test_visual_report.py -q`
2. `python -m pytest tests/unit/test_m08a_catalog_reopen.py -q`
3. `python tools/cadctl_cli.py registry coverage`
