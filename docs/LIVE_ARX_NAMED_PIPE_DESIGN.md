# Live ARX Named-Pipe Pump — Design (DEFERRED / UNBUILT)

> **Status: NOT BUILT.** This document is a design only. As of `CADOS_M01` there is **no live
> pump**: `patch_engine` execution and `visual_report` rendering are non-destructive safety
> shells, and the live ObjectARX command pump described here is **gated to a later packet**
> (`CADOS_M02` / a dedicated live-pump packet) and to **attended AutoCAD**.
>
> Nothing in `CADOS_M01` starts a pipe server, a worker thread, or any in-process AutoCAD
> mutation. This file exists so the contract and the hard safety rules are written down
> **before** anyone implements it.

---

## 1. Why this exists (and why it is gated)

The headless lanes — ObjectDBX read, Core Console (`.crx`) database/CRUD ops — already work
without a live editor. But a class of operations (custom `worldDraw` graphics, OPM properties,
overrules, interactive jigs, persistent reactors, editor/UI/COM, anything needing a live
`AcDb` transaction in document context) can only run **inside attended AutoCAD**.

A **live ARX named-pipe pump** would let an external agent (via the router / cadctl) drive an
attended AutoCAD session command-by-command. It is deferred because:

- It runs **in-process inside AutoCAD** with full write capability — the blast radius is the
  user's live drawing. That demands the explicit, attended, later-packet gate.
- The router's contract is **originals are READ-ONLY**; a live mutating pump is a separate,
  consciously-scoped capability, not a silent extension of the headless extract path.
- The threading rules below are unforgiving; getting them wrong crashes AutoCAD. This must be
  built deliberately, not bolted onto `CADOS_M01`.

---

## 2. Pump contract (proposed)

A single named pipe (e.g. `\\.\pipe\cadagent`) carrying line-delimited JSON commands. The ARX
module registers verbs and a pump that the agent drives:

| command | meaning |
|---|---|
| `CADAGENT_START` | create the named-pipe server and arm the pump (idempotent; no-op if already armed) |
| `CADAGENT_STOP` | disarm the pump and tear down the pipe server cleanly |
| `CADAGENT_STATUS` | report pump state (armed? pipe connected? last job id / result) without mutating anything |
| `CADAGENT_PUMP` | drain queued jobs and execute them **in the main/document context** (see rules) |

- **Transport:** one JSON object per line in, one JSON result object per line out, mirroring the
  router's existing line-delimited convention.
- **Result envelope:** reuse `cad_result.v2` (`schemas\cad_result.v2.schema.json`) so live
  results are shaped identically to headless results.
- **Job envelope:** reuse `cad_job.v2` (`schemas\cad_job.v2.schema.json`); the registry op id
  (Operation Registry v2) selects the verb.

---

## 3. Hard rules (non-negotiable)

These are the rules that make a live in-process pump safe. Violating any of them is a defect:

1. **Never start threads in `DllMain`.** Do all server/thread setup from a registered command
   (`CADAGENT_START`) on AutoCAD's own thread — never from the loader entry point.
2. **Never touch `AcDb` from the pipe worker thread.** The I/O thread may only read bytes off
   the pipe and enqueue/return JSON. **All** database access happens on the main/document thread.
3. **Main / document-context pump only.** Actual job execution (`CADAGENT_PUMP`) runs on
   AutoCAD's main thread in document context — e.g. drained on idle / command-context — so every
   `AcDb` transaction is on the correct thread.
4. **Attended AutoCAD only.** The pump requires a live, attended `acad.exe`; it is **not** a
   headless / Core Console capability and must not be reachable from the headless lanes.
5. **Explicit, later-packet gate.** It is enabled only by a deliberate future packet, never
   implicitly. `CADOS_M01` ships it as **unbuilt**.
6. **Honesty over success.** Until built, `STATUS` would report "not armed / not implemented";
   no shell may fake a started pump or a successful live mutation.

---

## 4. Relationship to the rest of the stack

- **Headless today:** `dwg_truth_autocad` via `.crx` (Core Console) + `.dbx` (ObjectDBX read)
  covers DB / object / CRUD lanes with no live editor. That is what `CADOS_M01` uses.
- **Attended later:** this pump is the bridge to editor / graphics / UI / overrule / jig /
  reactor lanes that headless cannot reach.
- **Same envelopes:** by reusing `cad_job.v2` / `cad_result.v2` and the Operation Registry v2
  op ids, live and headless paths stay interchangeable from the agent's point of view.

---

## 5. Status restated

**Unbuilt.** No pipe server, no worker thread, no live `AcDb` mutation exists in `CADOS_M01`.
This contract + these rules are the brief for whoever implements it in a later, explicitly
attended-AutoCAD packet. See `docs\CAD_OS_BUILD_STATUS.md` §8 (D5) and
`docs\CAD_OS_FULL_STACK_HANDOFF.md` §6.
