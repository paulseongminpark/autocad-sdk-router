# M08PLOT — native layouts_plot_publish (2 blocked ops → headless build)

Execution-ready ticket for the SOLE remaining headless-buildable blocked ops. Follows the M08L/M08KC
family-addition pattern. **NO FAKES.** Hostless on `ctx.pDb`. Verify feasibility BY BUILDING + PROBING.

## Scope (2 ops, family `layouts_plot_publish`)
- `plot.config.settings` — read (and optionally set) a layout's plot settings. **HIGH feasibility (DB-resident).**
- `plot.engine.run` — run the plot pipeline to a file. **UNCERTAIN headless — VERIFY, defer honestly if infeasible.**

## CHANGE_ONLY
- NEW `src/Ariadne.AcadNative/families/m08p_handlers.inc` (m08pHasOp / m08pDispatch, mirror m08c/m08d shape).
- `src/Ariadne.AcadNative/AriadneNativeJob.cpp` — seam ONLY: (a) `#include "families/m08p_handlers.inc"` next to
  the other family includes; (b) add `|| m08pHasOp(op)` to `familyHasOp()` (line ~6167); (c) add
  `|| m08pDispatch(op, ctx, r)` to the dispatch chain (line ~6183). No other logic.
- `config/operations.v2.json` + `config/policy.v2.json` — flip the 2 ops `blocked`→`implemented` ONLY IF they
  build + probe non-fake. If `plot.engine.run` proves headless-infeasible, LEAVE it blocked + document.
- NEW `tests/unit/test_m08p_handlers.py` (mirror test_m08d: HasOp↔Dispatch lockstep, no save/saveAs/acedCommand).
- NEW `reports/tickets/M08PLOT.md` (implemented/deferred with concrete blocker, build sizes+exit, honest).

## Op 1 — plot.config.settings (IMPLEMENT; hostless DB read/write)
`AcDbLayout` **derives from** `AcDbPlotSettings`. Path:
1. Resolve the target layout: arg `layout` (name, default "Model") OR `layout_handle`. Open the layout object
   (via the layout dictionary `pDb->getLayoutDictionaryId()` → get named entry, or open by handle) for read
   (or write if setting).
2. READ (default): cast to `AcDbPlotSettings*` and serialize getters — `getPlotCfgName()`/`getCanonicalMediaName()`,
   `plotType()`, `plotRotation()`, `plotPaperUnits()`, `getPlotPaperSize()`, `useStandardScale()`, `getStdScale()`,
   `getPlotOrigin()`, `getPlotWindowArea()`, `shadePlot()`, `scaleLineweights()`, `plotPlotStyles()`. Emit JSON.
3. WRITE (if any set_* arg present): mutations MUST go through `AcDbPlotSettingsValidator`
   (`pDb->plotSettingsValidator()` / `acdbHostApplicationServices()->plotSettingsValidator()`):
   `setPlotCfgName`, `setCanonicalMediaName`, `setPlotRotation`, `setPlotPaperUnits`, `setStdScale`,
   `setPlotType`, etc. Direct setters on AcDbPlotSettings are NOT public — the validator is the only sanctioned
   write path (do NOT hand-set). Open layout for write, apply via validator, close.
Hostless-safe: pure DB-resident object read/write; no plot engine, no device, no save.

## Op 2 — plot.engine.run (VERIFY; likely defer)
`AcPlPlotEngine` (AcPlPlotEngine.h) pipeline: `AcPlPlotFactory::createPublishEngine`/`createPlotEngine` →
`beginPlot(progress)` → `beginDocument(plotInfo, docname, …, bPlotToFile=true, pFileName)` →
`beginPage(pageInfo, plotInfo, lastPage)` → `endPage` → `endDocument` → `endPlot`. `AcPlPlotInfo` binds an
`AcDbPlotSettings` + validated device via `AcPlPlotConfig` (AcPlPlotConfigMgr). **RISK**: the engine needs a
valid plot CONFIG/DEVICE (PC3 / "DWG To PDF.pc3") and `AcPlHostAppServices`; in headless accoreconsole a live
plot device may be unavailable or unsafe — same class of limitation as the M08KC solver deferrals. **Attempt a
plot-to-PDF to a staged temp path; if it errors/needs a device that CoreConsole lacks, DEFER (out of HasOp) with
the concrete blocker in the ticket.** Never fake an "ok" without a real output file.

## Build gate (MUST be exit 0)
`powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_native_acad.ps1 -RouterHome <worktree>`
Iterate until final JSON `"status":"ok"` + exit 0. Link libs: AcPl* symbols from `acPlot*.lib` — if a missing
import lib blocks linking `plot.engine.run`, defer that op (config.settings needs only acdb, always linked).

## Probe (the real gate — no fake PASS)
After build, deploy + `python tools/probe_reachability.py --live --ops "plot.config.settings,plot.engine.run"`.
Promote in the registry ONLY the op(s) that probe non-CRASH/non-fake. Expected: config.settings → RUNNABLE
(reads a real layout's settings); engine.run → RUNNABLE if it writes a real PDF, else stays blocked (documented).

## Hard constraints
Hostless on ctx.pDb. NO save()/saveAs/_QSAVE, NO acedCommand. HasOp↔Dispatch lockstep. Unimplemented OUT of
HasOp. Original DWG untouched (staged copy only). Honest deferral over a fake.
