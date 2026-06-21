# CADOS_M07 — Live ARX Pump + Deep Native Surface (Result)

**Status: PARTIAL_PASS** (every acceptance criterion satisfied — the attended-only
items via the packet's explicit "OR exact blocker recorded" / "OR hard-block with
evidence" allowances). Built by Claude (aclaude) via ultracode workflow (parallel
design/test/report breadth) + inline native compile/test keystone. No fake PASS.
Original golden DWG byte-identical. No remote push.

## What M07 added (genuinely new this packet)

The live ARX pump went from 4 ops to **12**, plus a new non-blocking status command:

- `CADAGENT_STATUS` — non-blocking health/config report (build_id, pipe, timeout,
  host_mode, serving flag, 12 supported_ops, write_policy). Prints headless + attended.
- `live.active_document` — working-db dwg path + model-space handle + entity counts (pure read).
- `live.inspect_entity` — read one entity by hex handle; same geometry shape as
  `inspect.database.graph`; honest `not_found` on miss.
- `live.apply_patch` — **§5 write guard**: always `disabled`, points at the M05 staged
  governor; pump opens no db for write, never saves.
- `live.inspect_selection` / `live.highlight_handles` / `live.clear_highlight` /
  `live.zoom_to_handles` / `live.render_view` — **attended_only** honest stubs (exact
  GUI/graphics reason; no fake success).
- §3 thread-safety statement + clean-shutdown contract documented in the source;
  `gPumpServing` flag so STATUS reports serving truthfully.

## Verification (all real, no TBD)

- **Native build GREEN**: `tools/build_native_acad.ps1` → `.dbx` 44544, **`.crx` 229888**
  (canonical/fresh, +14336 over baseline), `.arx` versioned `Ariadne.AcadNative.live_20260622_061225`
  (lock bypass; attended acad.exe NOT killed). build_id `Jun 22 2026 06:12:22`.
- **Headless pump GREEN (17/17)**: `runs/m07_pump_test/run_m07_pump_test.ps1` — accoreconsole
  loads the `.crx`, a pipe client drives every op. `M07_PUMP_OPS_OK: True`. modelspace 21747.
  `inspect_entity` proven on real golden handles (LINE 11935, CIRCLE 12B4C r=25, TEXT 19166)
  + `FFFFFFFF → not_found`. `apply_patch → disabled`. 5 GUI ops → `attended_only`. `stop → clean`.
  `CADAGENT_STATUS` v1 JSON printed headless.
- **Original golden DWG unchanged**: sha256 `27dbf6b9…` before==after (test only copies
  FROM it; the disposable staged working copy is what accoreconsole rewrites on quit).
- **pytest**: `284 passed, 3 skipped` (3 = env-gated CADOS_LIVE) — full repo, 0 fail.
  New: `tests/unit/test_pump_frame_codec.py` (11), `tests/unit/test_pump_shutdown_and_deep_native_source.py` (16).

## Deep native surface — corrected matrix (7 implemented / 3 attended_blocked / 0 design_only)

See `docs/NATIVE_DEEP_SURFACE_STATUS.md` + `reports/deep_native_latest.json`.

- **implemented (7)**: custom_entity_lifecycle (`AriadneProbe : AcDbEntity`); worldDraw_rendering
  (`AriadneProbe::subWorldDraw` circle marker — render callback compiled, pixel proof attended-only);
  object_overrules; persistent_reactors; editor_jigs (host-gated); custom_object_filer_versioning
  (`AriadneRecord` version + eMakeMeProxy); protocol_extensions (`AriadneProbeProtocol` addX + `inspect.protocol.queryx`).
- **attended_blocked (3)**: acrxproperty_opm (Properties palette is MFC GUI); selection_monitor
  (needs live pick stream); palette_status_ui (MFC dock/status GUI). All have NO headless surface
  and must not be driven into PID 49460 — exact reasons recorded, not faked.
- **Correction vs the M07 design stream**: worldDraw + protocol were miscounted as not-implemented
  because the stream grepped only `AriadneNativeJob.cpp` and missed `AriadneProbe.cpp` /
  `AriadneProtocol.cpp`. Ground-truth verified + codified by two source-presence tests.

```
[CADOS M07 RESULT]
status: PARTIAL_PASS
packet: CADOS_M07_LIVE_ARX_AND_DEEP_NATIVE_SURFACE
build_base: ef603b8  (all build/test outcomes below are real, this session)

LIVE ARX PUMP
  command: CADAGENT_PUMP (single-threaded, main-thread blocking named-pipe server; ACRX_CMD_MODAL)
  status_command: CADAGENT_STATUS (non-blocking; v1 JSON: build_id/pipe/timeout/host_mode/serving/12 ops/write_policy) -- printed headless OK
  build: PASS (build_native_acad.ps1 -> dbx 44544, crx 229888, arx versioned live_20260622_061225 lock-bypass; AutoCAD not killed)
  loaded: PASS (accoreconsole arxload dbx+crx)
  wire: 4-byte LE uint32 length + UTF-8 JSON body, both directions (1 MiB frame cap)
  echo: PASS               (echo == CADOS_M07_PUMP)
  status: PASS             (running, has_database true, modelspace_entities 21747)
  list_documents: PASS     (ok)
  active_document: PASS    (dwg_path set, modelspace_handle 1F, modelspace_entities 21747)
  inspect_entity: PASS     (11935->AcDbLine start/end; 12B4C->AcDbCircle center/radius 25; 19166->AcDbText text; FFFFFFFF->not_found)
  apply_patch (write, §5): PASS as DISABLED (reason+governor pointer+original_dwg read_only; no live save)
  inspect_selection/highlight_handles/clear_highlight/zoom_to_handles/render_view: attended_only (interactive_editor_required true, exact reason; NOT faked)
  stop: PASS               (stopped true -> clean exit)
  self_terminating: yes    (overlapped connect/read/write + timeout + CancelIo; ARIADNE_PUMP_TIMEOUT default 30s)
  headless_proof: runs/m07_pump_test (M07_PUMP_OPS_OK True, 17/17 checks); pytest tests/unit (27 tests)
  blocker (attended): acad.exe PID 49460 running but NO automation channel from this session and MUST NOT be disrupted -> attended echo/status/list-docs not exercised live; identical .crx code path is headless-verified

DEEP NATIVE
  implemented (7): custom_entity_lifecycle; worldDraw_rendering (AriadneProbe::subWorldDraw circle; pixel proof attended-only); object_overrules; persistent_reactors; editor_jigs (host-gated full_autocad); custom_object_filer_versioning (AriadneRecord version+eMakeMeProxy); protocol_extensions (AriadneProbeProtocol addX + inspect.protocol.queryx)
  attended_blocked (3): acrxproperty_opm (Properties palette MFC GUI); selection_monitor (live pick stream); palette_status_ui (MFC dock/status GUI) -- no headless surface; exact reasons recorded; PID 49460 not driven
  design_only (0)
  evidence: reports/deep_native_latest.json; docs/NATIVE_DEEP_SURFACE_STATUS.md; tests/unit/test_pump_shutdown_and_deep_native_source.py

THREAD SAFETY (§3)
  worker_acdb_access: no (NO worker thread; pump runs on AutoCAD document/command thread; DllMain/acrxEntryPoint start no threads)
  clean_shutdown: yes (gPumpServing->0 -> FlushFileBuffers -> DisconnectNamedPipe -> CloseHandle; kUnloadAppMsg disables reactor+overrule, removeGroup, unloads .dbx); tested via live.stop path + headless run

TESTS
  unit (always): tests/unit/test_pump_frame_codec.py = 11 passed; tests/unit/test_pump_shutdown_and_deep_native_source.py = 16 passed
  full repo: pytest 284 passed, 3 skipped (CADOS_LIVE env-gated), 0 failed
  original DWG unchanged: yes (sha256 27dbf6b9...; staged copies only; no remote push)

NEXT: CADOS_M08_FULL_OPERATION_COVERAGE_CLOSURE
  1) full operation coverage closure: every op implemented / blocked / deprecated / tested / evidenced; unknown 0
  2) dedicated ATTENDED packet later: load .arx into an agent-drivable AutoCAD to prove OPM/selection-monitor/palette + attended live pump (the 3 attended_blocked surfaces + attended pump proof)
[/CADOS M07 RESULT]
```
