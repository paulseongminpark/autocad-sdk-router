# Live Job Argument Contract (CADOS_M07B)

Finalizes the non-interactive, reproducible channel for driving native ObjectARX
jobs (custom ops) inside **attended** AutoCAD — the piece left open as a TBD in
M07A (loose `ARIADNE_CAD_JOB_IN`/`_OUT` env vars did not reliably drive a custom
op from a startup `.scr`). The command never prompts for keyboard text, so it is
drivable from a dedicated `acad.exe /b startup.scr` with zero human input.

## Mechanism

1. The harness writes a **run-scoped args file** `runs/<run_id>/live_job_args.json`.
2. It sets the env var **`ARIADNE_NATIVE_JOB_ARGS`** = absolute path to that file.
3. The startup script runs the AutoCAD command **`ARIADNE_NATIVE_JOB_ARGS`**.
4. `ariadneNativeJobArgs()` (AriadneNativeJob.cpp):
   - reads the env var (via `acedGetEnv`, then process `_wgetenv`),
   - reads the args file once, parses `job_in` / `job_out` / `host_mode`,
   - sets the in-process job overrides and calls `ariadneNativeJob()`,
   - clears the overrides. **No interactive prompt.**
5. `ariadneNativeJob()` reads the `job_in` file, dispatches by the **`operation`**
   key, and writes the result JSON to `job_out`.

If `ARIADNE_NATIVE_JOB_ARGS` is unset or its file lacks `job_in`, the command
falls back to the **documented interactive prompts** (`ARIADNE_CAD_JOB_IN:` …) —
kept only so an operator can still drive a job by hand.

## Schemas

### `live_job_args.json` (the args file)
```json
{ "job_in": "D:/.../runs/<run_id>/job_in.json",
  "job_out": "D:/.../runs/<run_id>/job_out.json",
  "host_mode": "full_autocad" }
```
- **Paths use forward slashes** (`/`). The hand-rolled JSON reader returns raw
  inter-quote substrings (no unescaping), and Win32 file APIs accept `/`, so
  forward slashes avoid any `\\` escaping ambiguity. Paths are UTF-8 → UTF-16
  via `utf8ToWide`.
- `host_mode`: `coreconsole` (headless) or `full_autocad` (attended). Defaults to
  `full_autocad` if absent (this command path is attended-oriented).

### `job_in.json` (the job)
```json
{ "operation": "inspect.probe.property_count" }
```
- The **native job dispatcher key is `operation`** (the live pump frame key is
  `op` — they are different surfaces). Op-specific keys (e.g. `cx`/`cy`/`cz`/`size`
  for `extend.customclass.create`) sit alongside `operation`.

### `job_out.json` (the result)
```json
{ "schema": "ariadne.autocad_native_job_result.v1",
  "engine": "native_objectarx",
  "operation": "inspect.probe.property_count",
  "result": { "property_count": 1, "property": "Size", "opm_registration": true,
              "panel_display": "attended_only" },
  "status": "ok" }
```

## Proven headless (CADOS_M07B)

`runs/m07b_native_smoke/run_native_smoke.ps1` drives the channel under
accoreconsole (`host_mode=coreconsole`), original golden read-only:

| operation | result |
|---|---|
| `inspect.probe.property_count` | `{property_count:1, property:"Size", opm_registration:true}` → OPM AcRxProperty registration proven |
| `inspect.runtime.capabilities` | full matrix, all surfaces `implemented:true` |
| `inspect.selection.monitor.registry` | `implemented:true, registered:false` (honest headless gate) |

The attended harness (`tools/attended/run_attended_m07b.ps1`) uses the **same**
channel with `host_mode=full_autocad` to create an `AriadneProbe`
(`extend.customclass.create`) inside the dedicated `acad.exe` before serving the
pump.

## Invariants

- Read-only with respect to the original DWG; mutation still routes only through
  the M05 staged-patch governor.
- The command never blocks on user input when the env channel is present.
- The pump (`CADAGENT_PUMP`) remains a separate live channel (named pipe, `op`
  key); this contract is for the one-shot `ARIADNE_NATIVE_JOB(_ARGS)` dispatch.
