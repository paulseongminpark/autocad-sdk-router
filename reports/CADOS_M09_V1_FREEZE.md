# CADOS M09 — V1 Release Freeze + Daedalus Handoff

- date: 2026-06-26
- frozen source: commit `bc0832a` (`Integrate Wave3 and close unfinished CAD OS ops`)
- code tag: `cad-os-v1.0.0` (pre-existing, "CAD OS Layer v1.0.0 final release") — points at `bc0832a`
- freeze/doc tag: `cad-os-v1.0.1` (this freeze record + refreshed acceptance doc + build record; doc-only over v1.0.0 code)
- repo: `github.com/paulseongminpark/autocad-sdk-router` (private)

## What V1 is

The AutoCAD SDK control plane ("CAD OS"): a headless-first ObjectARX native module
(`Ariadne.AcadNative.{dbx,crx,arx}`) + Python router/registry exposing **517 catalogued
AutoCAD SDK operations**, all driven to a closure state:

- **457 implemented** (each with a native dispatcher symbol + evidence)
- **60 hard-blocked** (each with a genuine SDK/safety/host blocker_reason)
- **0 catalogued / 0 stub / 0 unknown / 0 deprecated** → `closure_gate_pass = true`

This is honest closure: nothing is silently unfinished. Hard-blocks are principled
(ASM associative solver, COM automation roots, host-lifecycle loader callbacks,
subentity-path mutation, plot engine/config — see acceptance doc).

## Freeze evidence (all verified 2026-06-26)

| Check | Result |
|---|---|
| native build (VS2026, Release x64, combined-TU) | exit 0; `.dbx` 54272 / `.crx` 756224 / `.arx` 764416 |
| managed build (dotnet 10.0.300) | exit 0 |
| full pytest | 504 passed, 3 skipped |
| closure gate | PASS (457/60, 0 open buckets) |
| native headless smoke (fresh `.crx`) | golden 21747 (3-way match), `native_full`, original DWG unchanged |
| raw-command exposure | none (hard-blocked/internal) |
| original-write default | none (staged-write only) |
| git index | clean (0 staged); HEAD == deployed binary source |

Build record: `reports/merge/BUILD-CADOS-FULL-REBUILD.{json,md}`.
Closure gate: `reports/closure_gate_latest.json`. Acceptance: `docs/CAD_OS_V1_ACCEPTANCE.md`.

## Plot-ops re-examination (the 459/58 variant) — verdict: hard-block stands

A WAVE4X branch (`cados/w4x-visual-plot` @ `7adc82e`) implemented `plot.config.settings`
+ `plot.engine.run` (would make 459/58, or 466/51 with loader/doc). It was **not merged**.
Re-examined this freeze:

- `plot.engine.run` — uses `AcPlPlotEngine`, requires a full plot host; **does not link/run
  in the headless `.crx`**, and the branch carried explicit "attended verification debt"
  (never actually verified to plot). Marking it implemented headless = fake-implemented.
- `plot.config.settings` — `AcDbPlotSettings` is a DB object; a read/inspect subset is
  arguably headless-safe, but the current hard-block (no bounded staged-write handler) is
  conservative and the branch bundled it with the unverified engine op.
- **Decision:** keep both HARD-BLOCKED in V1. The legitimate path is a dedicated
  attended / full-AutoCAD `.arx` target (M07B live-pump infra) with real attended plot
  verification — future scope. The branch work is preserved in git reflog + the WAVE4X
  ticket reports if revisited.

## Honest gaps (declared, non-blocking)

- Dedicated scale/stress benchmark not run (golden 21747 + 504 suite are the regression evidence).
- Wave4 blocked→impl candidates deferred: visual/plot +2 (attended), loader/doc +7 (re-audit).
- Working tree carries `core.autocrlf` LF→CRLF noise (~223 files) + untracked report artifacts;
  cosmetic, no source divergence from HEAD. (A `.gitattributes` `* text=auto` would end the noise — optional.)

## Daedalus handoff

CAD OS V1 is the **operation/runtime substrate** for the Daedalus CAD Agent Control Plane
(`D:\dev\_ariadne\_daedalus`). What Daedalus can build on, frozen at `bc0832a`:

- **Operation surface**: 457 implemented ops (registry `config/operations.v2.json`, the SoT;
  coverage `reports/operation_coverage_latest.json`). Each op = `{op_id, status, handler.dispatcher_symbol, evidence_refs, blocker_reason?}`.
- **Entrypoints**: the router (`tools/autocad-router.ps1` family) selects engine by op;
  native ops dispatch through `ARIADNE_NATIVE_JOB` into the `.crx`/`.arx`; MCP surface via
  `tools/cadagent_mcp.py`; live attended pump via M07B (`CADAGENT_PUMP` named pipe).
- **Invariants Daedalus must honor**: originals are READ-ONLY (staged-write only); no
  agent-exposed raw command; closure states are `{implemented, hard_blocked, deprecated}`
  only; the 60 hard-blocks are intentional (do not "implement" them without the attended
  target + real verification).
- **Verification harness available**: `pytest tests` (504), `CADOS_LIVE=1` native live tests,
  `build_native_acad.ps1 -RouterHome <abs>` (cwd-independent rebuild), golden 21747 smoke.

## Status

**M09 V1 FREEZE: COMPLETE (local).** Code frozen at `cad-os-v1.0.0`/`bc0832a`; freeze docs at
`cad-os-v1.0.1`. Not pushed to origin (awaiting explicit push approval).
