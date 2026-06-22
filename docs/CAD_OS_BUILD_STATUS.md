# CAD OS Build Status

Updated: 2026-06-22T14:10:00+09:00

## Current Packet

- M03 Native Router/Rich IR Completion: PASS
- M04 Operation Registry/Tool Surface: PASS
- M05 Patch Diff Validation Transaction: PASS
- M06 Visual Batch Golden Regression: PASS
- M07 Live ARX Pump / Deep Native Surface: PARTIAL_PASS
- M07A Deep-native remainder (selection monitor + AcRxProperty/OPM): implemented + build-verified
- M07B Attended GUI Verification + Native Deploy Closure: **PASS**
- M08 Full Operation Coverage Closure: **PASS**
- Next: CADOS_M09_V1_RELEASE_FREEZE_AND_DAEDALUS_HANDOFF

## M08 — Full Operation Coverage Closure (PASS)

- **Coverage matrix:** all **517** ops projected into the 13-field M08 taxonomy
  (`tools/operation_coverage_matrix.py`, deterministic) → `reports/operation_coverage_full_matrix.json`
  + `.md`. **0 unknown, 0 missing field, 0 v1-target deferred.** v1 gate **11/11 PASS**
  (`reports/v1_operation_gate_latest.json`).
- **Status rollup:** implemented **41** · stub **0** · blocked **2** · catalogued **474**
  (was 37/4/2/474). cadctl `registry coverage` consistent=true.
- **v1-target = 43** (status ∈ {implemented, blocked}): 41 implemented + 2 hard-blocked with evidence
  (`render.layout` plot host, `live.apply_patch` attended live-edit+approval). The 474 `catalogued` ops
  are classified future-version native capability (v1_target=false), not omitted.
- **Implementation sweep (4 stubs → implemented):**
  - `inspect.layers` / `inspect.blocks` / `inspect.entities` — **built natively** (`listLayerRecords`,
    `listBlockDefinitionsDetailed`, `listModelSpaceEntities` in `AriadneNativeJob.cpp`), accoreconsole-smoked
    on a staged golden copy: **layers 70 · blocks 245 · modelspace entities 21747** — cross-validates the
    M03 rich-IR truth (70/245/21747). Non-ASCII **UTF-8 preserved** (code-point verified: `U+D3C9 U+BA74
    U+B3C4` = 평면도; 0 U+FFFD, 0 literal `?`). `inspect.entities` is bounded (limit, `returned`/`truncated`,
    honest total — no silent cap). Evidence `runs/m08_inspect_ops/`.
  - `live.status` — promoted (real handler `pumpDispatch`, M07 pump headless 17/17 + M07B attended).
- **Native build canonical:** `.dbx` 48128 · `.crx` 260096 · `.arx` 268288 (`reports/build_native_m08.log`).
- **Risk classes:** read_safe 349 · staged_write 113 · live_edit 50 · raw_command 5. The 5 raw-command ops
  (`acedCommand*`/`command.invoke`) are all `catalogued` and **0 are agent-exposed** (packet hard rule).
  agent_exposed = 41 (every implemented op is agent-permitted; raw-command and original-write are excluded).
- **Original golden DWG modified: no** (`27dbf6b9…` before/after, staged copies only). No remote push.
  pytest **313 passed / 3 skipped** (default); **316 passed / 0 skipped** (`CADOS_LIVE=1`).

## M07B — Attended GUI Verification + Native Deploy (PASS)

- **Native build: canonical** via `tools/build_native_acad.ps1` — `.dbx` 48128, `.crx` 250368,
  `.arx` 258048 (canonical relink, no lock; AutoCAD not killed). Log `reports/build_native_m07b.log`.
- **Pump-gating:** the 5 formerly-`attended_only` ops gate on `hostIsFullAutoCad()` (host EXE name —
  reliable; `acedEditor` is non-null in both hosts and the host_mode env hint does not propagate).
  Attended: `highlight`/`clear`/`inspect_selection` execute for real; `zoom`/`render` honestly deferred
  (acedCommand reentrancy). Headless 17/17 preserved.
- **Live job channel:** `ARIADNE_NATIVE_JOB_ARGS` env-file channel finalized (M07A blocker resolved);
  `inspect.probe.property_count → property_count 1` headless. Contract `docs/LIVE_JOB_ARGUMENT_CONTRACT.md`.
- **Palette:** `ARIADNE_PALETTE` (MFC-free, arx-only); docked CAdUiPaletteSet (MFC) deferred to keep build stable.
- **Attended (dedicated acad.exe, zero COM, run `cados_m07b_attended_20260622_123505`, PID 51708):**
  `ATTENDED_PUMP_OK: True` — live pump host_mode full_autocad, highlight 2/2, clear 2/2, worldDraw circle
  rendered + OPM palette open (screenshot), probe created (`ariadne_probes 1`). 3 safety gates pass.
- **Deep-native firing CLOSED:** reactor (1/1) + overrule (2/3) + selmon (1/1) live counts captured in
  BOTH headless and attended via `firing_selftest` + `firing_report` (no acedCommand reentrancy, no human,
  zero COM). `reports/firing_latest.json` · `runs/m07b_firing/`.
- **Original golden DWG modified: no** (`27dbf6b9…` before/after). No remote push.
  pytest 295 passed / 3 skipped (default); 298 passed / 0 skipped (`CADOS_LIVE=1` → 3 live tests run+pass).

### Versioned vs canonical ARX
The build relinks the canonical `.arx` when no acad.exe holds it (M07B: canonical). If a running acad.exe
locks it (LNK1104), the script falls back to a versioned `Ariadne.AcadNative.live_<ts>.arx` and the `.crx`
(what accoreconsole loads) stays canonical/fresh. AutoCAD is never killed.

## Live ARX Pump / Deep Native (M07)

- Native build: PASS via `tools/build_native_acad.ps1` — `.dbx` 44544, `.crx` 229888 (canonical/fresh, +14336 over baseline), `.arx` versioned `Ariadne.AcadNative.live_20260622_061225` (lock bypass; AutoCAD not killed). build_id `Jun 22 2026 06:12:22`.
- Live pump: 12 ops + `CADAGENT_STATUS`. Headless-verified `runs/m07_pump_test/run_m07_pump_test.ps1` (`M07_PUMP_OPS_OK: True`, 17/17). modelspace 21747. `inspect_entity` on real handles 11935/12B4C/19166 + `FFFFFFFF`→not_found. `apply_patch`→disabled (§5). 5 GUI ops→attended_only. `stop`→clean. CADAGENT_STATUS v1 JSON printed headless.
- §3 thread-safety: no worker thread (main-thread pump); clean shutdown documented + tested.
- Deep native: 7 implemented (custom entity, worldDraw, overrules, reactors, jigs[host-gated], filer versioning, protocol extensions) / 3 attended_blocked (AcRxProperty/OPM, selection monitor, palette/status UI) / 0 design_only. See `reports/deep_native_latest.json`, `docs/NATIVE_DEEP_SURFACE_STATUS.md`.
- Original golden DWG modified: no (`27dbf6b9…` before/after; staged copies only).
- Attended live-pump proof: attended_blocked (acad.exe PID 49460, no automation channel, must not disrupt) — identical `.crx` code path headless-verified.

## Native Build

- DBX/CRX: PASS
- ARX: PASS via versioned lock bypass `Ariadne.AcadNative.live_20260622_034352`; AutoCAD was not killed.
- Build log: `reports/build_native_wrapper_latest.log`

## Rich IR

- IR: `runs/m03_rich_ir/dwg_graph_ir.json`
- entities: 21747
- HATCH loops: 702
- xdata blocks/items: 751 / 1069
- xrecords/items: 2 / 7
- non-ASCII: PASS

## Registry

- total: 517
- implemented: 41
- stub: 0
- blocked: 2
- catalogued: 474
- unknown: 0
- M05 implemented ops: `apply.patch`, `diff.before_after`, `validate.patch`
- M08 promoted ops: `inspect.layers`, `inspect.blocks`, `inspect.entities` (native), `live.status` (pump)
- 13-field coverage matrix: `reports/operation_coverage_full_matrix.json` (+ `.md`); v1 gate `reports/v1_operation_gate_latest.json`

## Patch / Diff / Validation

- Patch run: `runs/m05_patch_create_line/`
- dry-run: PASS, `runs/m05_patch_create_line/dry_run/dry_run_plan.json`
- staged apply: PASS, `runs/m05_patch_create_line/result.json`
- CAD diff: PASS, `reports/patch_diff_latest.json` (+1 LINE, 0 removed, 0 modified)
- validator: PASS, `reports/validation_latest.json` (14/14 gates)
- journal: `reports/journal_latest.json`
- original DWG modified: no (`27dbf6b95ff72a89fd53b153891187365b9e8ebc4c05a97cfed307057bf49bc8` before/after)

## Visual / Batch / Golden / Performance

- Visual verification: PASS, `reports/visual_verification_latest.json`
- Visual artifacts: `runs/m06_visual_batch_golden/visual/before.svg`, `after.svg`, `overlay.svg`, `visual_diff.json`
- Batch runner: PASS, `reports/batch_latest.json` (4 successes / 0 failures)
- Golden regression: PASS, `reports/golden_regression_latest.json`
- Performance: PASS, `reports/performance_latest.json`
- Large fixture: `runs/native_graph_20260621_234158/result_scale_graph.json`

## Verification

- M06 focused: `28 passed in 1.35s`
- M05/M06 combined focused: `127 passed in 2.78s`
- M07 unit: `tests/unit/test_pump_frame_codec.py` 11 + `tests/unit/test_pump_shutdown_and_deep_native_source.py` 16 = 27 passed
- Full pytest (M08): `313 passed, 3 skipped` (default; 3 skipped = env-gated CADOS_LIVE) · `316 passed, 0 skipped` (`CADOS_LIVE=1`)
- M08 coverage tests: `tests/unit/test_m08_operation_coverage.py` (17 — taxonomy/gate/promotions/native-source)
- staging DWG SHA256: `27dbf6b95ff72a89fd53b153891187365b9e8ebc4c05a97cfed307057bf49bc8`
