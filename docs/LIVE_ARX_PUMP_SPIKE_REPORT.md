# Live ARX Pump — As-Built Report (CADOS_M07)

> Supersedes the "NOT BUILT" status in `docs/LIVE_ARX_NAMED_PIPE_DESIGN.md`. The pump
> was built in M02 (4 ops) and **completed in M07** (12 ops + `CADAGENT_STATUS`).
> Every value here is a real result from this session's rebuild + headless run.

## 1. What the pump is

`CADAGENT_PUMP` is a **single-threaded, main-thread, blocking named-pipe server invoked AS
an AutoCAD command** (`AriadneNativeJob.cpp` `ariadneCadAgentPump`). Because it runs on
AutoCAD's document/command thread, every `AcDb` access it makes is already on the correct
thread — **no worker thread, no marshaling** (the deliberate §3 answer: you cannot touch
`AcDb` off-thread if there is no off-thread). The identical command path runs **headless**
(accoreconsole loads the `.crx`) and **attended** (the `.arx` in a running AutoCAD).

## 2. Wire protocol

Length-prefixed frames in **both** directions: `[ uint32 LE body-length ][ UTF-8 JSON body ]`.
- `pumpWriteFrame` packs the 4-byte LE header then the body.
- Read loop rejects `n == 0` or `n > (1u << 20)` (1 MiB cap), then reads exactly `n` bytes.
- Frame schema `ariadne.cad_pump_frame.v1`; status schema `ariadne.cad_pump_status.v1`.
- Codec + boundary rules locked by `tests/unit/test_pump_frame_codec.py` (always-run, incl. UTF-8 `평면도`).

## 3. Self-termination

Pipe created `FILE_FLAG_OVERLAPPED`; connect + every read/write use an `OVERLAPPED` +
manual-reset event + `WaitForSingleObject(timeout)`; on timeout `CancelIo` and fail closed.
The pump **can never hang a headless accoreconsole session**. Pipe/timeout from
`ARIADNE_PUMP_PIPE` / `ARIADNE_PUMP_TIMEOUT` (defaults `\\.\pipe\ariadne_cad_pump`, 30s).

## 4. Op set (all headless-verified in `runs/m07_pump_test`, 17/17)

| op | status | notes |
|---|---|---|
| `live.echo` | PASS | echo round-trip |
| `live.status` | PASS | running, has_database, modelspace_entities 21747 |
| `live.list_documents` | PASS | single working database |
| `live.active_document` | PASS | dwg_path, modelspace_handle `1F`, counts (pure read) |
| `live.inspect_entity` | PASS | by hex handle; same geometry shape as `inspect.database.graph`; honest `not_found` |
| `live.apply_patch` | PASS as **disabled** | §5 write guard; governor pointer; `original_dwg:read_only`; never saves |
| `live.inspect_selection` | attended_only | needs editor selection set (acedSSGet) |
| `live.highlight_handles` | attended_only | needs graphics subsystem |
| `live.clear_highlight` | attended_only | needs graphics subsystem |
| `live.zoom_to_handles` | attended_only | needs live editor viewport |
| `live.render_view` | attended_only | needs render pipeline + viewport |
| `live.stop` | PASS | clean exit |

Unknown ops return `not_implemented` with the supported-op list — never a fabricated result.

## 5. Commands

`acrxEntryPoint` registers **`CADAGENT_PUMP`** (`ACRX_CMD_MODAL`) and **`CADAGENT_STATUS`**
(`ACRX_CMD_MODAL`, non-blocking). The original design named `CADAGENT_START/STOP/STATUS/PUMP`;
the as-built folds START+PUMP into the one blocking command and exposes STOP as the in-band
`live.stop` frame. `CADAGENT_STATUS` prints the v1 status JSON (verified headless).

## 6. Write guard (§5)

`live.apply_patch` hard-returns `disabled` and points at the **M05 staged governor**
(`autocad-router.ps1 apply_staged`: staged copy → diff → validate → journal, original
READ-ONLY). The pump opens no db for write and never calls SAVE. The pump is read-only.

## 7. Clean shutdown

Normal exit (`live.stop` / framing / timeout) runs `InterlockedExchange(gPumpServing,0)` →
`FlushFileBuffers` → `DisconnectNamedPipe` → `CloseHandle(evt)` → `CloseHandle(pipe)`. Module
unload additionally `disableEditorReactor` + `disableObjectOverrule` + `removeGroup(ARIADNE_NATIVE)`
+ `acrxUnloadModule(.dbx)`. No handle or reactor leaks across unload.

## 8. Verification ledger (real)

| claim | how | result |
|---|---|---|
| Pump builds `.crx`/versioned `.arx` | `tools/build_native_acad.ps1` | PASS (.crx 229888; arx versioned lock-bypass) |
| `.crx` loads in accoreconsole | arxload in pump.scr | PASS |
| 12 ops behave per contract headless | `runs/m07_pump_test` pipe client | PASS (17/17) |
| Protocol framing | `tests/unit/test_pump_frame_codec.py` | PASS (11) |
| Shutdown / no-worker-thread | source guards | PASS (`test_pump_shutdown_and_deep_native_source.py`) |
| Original golden DWG unchanged | sha256 before/after | PASS (`27dbf6b9…`) |
| Attended live proof on PID 49460 | — | **attended_blocked** (no channel; must not disrupt) |
