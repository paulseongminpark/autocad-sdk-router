# WAVE3 PANE3 VISUAL / LIVE PLAN

This plan maps out the implementation strategy, verification methods, and validation rules for the visual, render, plot, and live operations within the Pane 3 scope.

## 1. Target Operations & Implementation Strategy

| Operation ID | Family | Strategy | Implementation Route & Details |
|---|---|---|---|
| `render.draw.viewportgeom` | `graphics_system` | **Implement** | Subclass `AcGiViewportGeometry` and `AcGiViewportDraw` to capture and tally eye/display-space geometry primitives (e.g. `polylineEye`, `polygonEye`). Wire inside `families/m08l_handlers.inc`. |
| `extend.customentity.draw_world` | `custom_objects_protocols` | **Implement** | Override `subWorldDraw` in custom entity `AriadneProbe` to return `Adesk::kFalse`. Expose a native dispatcher in `m08l_handlers.inc` calling `pEnt->worldDraw()` to verify execution and result. |
| `extend.customentity.draw_viewport` | `custom_objects_protocols` | **Implement** | Override `subViewportDraw` in `AriadneProbe` using `mode->geometry().circle()`. Expose dispatcher in `m08l_handlers.inc` using `M08LCollectViewportDraw` to capture and tally drawing. |
| `extend.customentity.grips` | `custom_objects_protocols` | **Implement** | Override `subGetGripPoints` and `subMoveGripPointsAt` in `AriadneProbe`. Expose dispatch handler in `m08l_handlers.inc` / `m08k_handlers.inc` to query/trigger them. |
| `extend.customentity.osnap` | `custom_objects_protocols` | **Implement** | Override `subGetOsnapPoints` in `AriadneProbe`. Expose snap-point query dispatcher in `m08l_handlers.inc` / `m08k_handlers.inc`. |
| `extend.customentity.stretch` | `custom_objects_protocols` | **Implement** | Override `subGetStretchPoints` and `subMoveStretchPointsAt` in `AriadneProbe`. Expose stretch dispatcher in `m08l_handlers.inc` / `m08k_handlers.inc`. |
| `extend.customobject.filer_dxfin` | `custom_objects_protocols` | **Implement** | Expose dispatcher in `m08k_handlers.inc` doing a database `dxfIn` with a temporary stream containing `AriadneRecord` / `AriadneProbe` DXF representation. |
| `extend.customobject.filer_dxfout` | `custom_objects_protocols` | **Implement** | Expose dispatcher in `m08k_handlers.inc` that triggers `dxfOut` on a temporary database containing `AriadneRecord` / `AriadneProbe` to verify output fields. |
| `extend.customentity.define` | `custom_objects_protocols` | **Hard Block** | Blocked with reason `SDK_NOT_EXPOSED: C++ ObjectARX requires compile-time class registration (AcRxClass / rxInit); dynamic class definition at runtime is not supported by the AutoCAD native runtime`. |
| `extend.customobject.define` | `custom_objects_protocols` | **Hard Block** | Blocked with reason `SDK_NOT_EXPOSED: C++ ObjectARX requires compile-time class registration (AcRxClass / rxInit); dynamic class definition at runtime is not supported by the AutoCAD native runtime`. |
| `overrule.dimstyle.install` | `custom_objects_protocols` | **Hard Block** | Blocked with reason `SDK_NOT_EXPOSED: AcDbDimStyleOverrule is not present in ObjectARX 2027 SDK headers`. |

## 2. Attended Verification Plan
No interactive GUI session is available. However, for any attended operations (like `plot.engine.run`), the verification strategy involves:
* Providing an `attended_test_plan.json` for manual or automated verification when a display device/layout graphics engine is present.
* Generating vector outputs (e.g. SVG/PDF) in staging to check correctness.
* No direct UI interaction; all operations run through non-interactive controlled routes.

## 3. Files to Edit
* `src/Ariadne.AcadNative/AriadneProbe.h` - Add overrides for custom entity callbacks.
* `src/Ariadne.AcadNative/AriadneProbe.cpp` - Implement overrides for custom entity callbacks.
* `src/Ariadne.AcadNative/families/m08l_handlers.inc` - Add `render.draw.viewportgeom` class & handler, custom entity dispatchers, and overrule hard block.
* `src/Ariadne.AcadNative/families/m08k_handlers.inc` - Add custom object filing (DXF in/out) dispatchers and definition hard blocks.
* `src/Ariadne.AcadNative/AriadneNativeJob.cpp` - Wire newly implemented handlers to the native operations table.
* `config/operations.v2.json` - Promote status from `catalogued` to `implemented` or `blocked`.
* `tests/unit/test_m08l_handlers.py` - Promote `render.draw.viewportgeom` to `_IMPLEMENTED`.
* `tests/unit/test_m08k_handlers.py` - Promote target operations to `_IMPLEMENTED`.

## 4. Tests to Run
* Native build using `tools/build_native_acad.ps1`.
* Test runner using `python -m pytest tests -q`.
* Operation coverage validation using `python tools/cadctl_cli.py registry coverage`.
