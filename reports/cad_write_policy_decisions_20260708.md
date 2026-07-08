# CAD write-policy decisions — 2026-07-08

Four open policy questions surfaced by the 2026-07-07/08 sweep + DCM work, decided by Paul (recommendations adopted). Recorded here as the durable ruling with evidence and reversibility.

| # | Decision | Ruling | Reversible? |
|---|----------|--------|-------------|
| 1 | xdata group-code **1004** binary write | **ACCEPT permanent read-only** | Yes (revisit on AutoCAD fix) |
| 2 | Hatch (`AcDbHatch`) write | **ACCEPT attended-gated**, folded into #4 | Yes (via #4 procedure) |
| 3 | `SAFETY_FORBIDDEN` blocked set | **HOLD as a list** — no bulk unblock; per-op ballots when a specific op is needed | Review: yes; opening an op: near-irreversible |
| 4 | `headless_safe` template flag | **BUILD a certification procedure** (in progress) | Procedure is safe (staged, original immutable) |

---

## 1. xdata 1004 = permanently read-only (ACCEPT)

**What.** Group code 1004 is the binary chunk of extended entity data (app-registered arbitrary bytes on a drawing entity).

**Evidence (2026-07-06, three independent paths).** Reading 1004 works (hex payload exposed). Writing does not: even a correctly-formed `acutNewRb` reconstruction corrupts the DWG on reopen. Decisively, the LibreDWG sidecar reads the *same* written file cleanly, and a 0-byte control passed — so the corruption is **AutoCAD 2027's EED-reconstruction internal defect**, not our code.

**Ruling.** 1004 write is accepted as permanently blocked at the SDK/reader level. We stop attempting to make it work.

**Reversibility.** Reversible — if a future AutoCAD release fixes the EED reconstruction bug, revisit. Until then, further effort is spent against a vendor defect we cannot fix.

## 2. Hatch write = attended-gated (ACCEPT, folded into #4)

**What.** Hatch write reached `diff=0` but only under an *attended* AutoCAD host (boundary/association re-evaluation is not faithfully reproduced under headless `accoreconsole`).

**Ruling.** Accepted as attended-gated (a structural limit today), and folded into decision #4: the headless-safe certification procedure is the correct venue to re-test hatch — if it can be certified headless-safe there with real evidence, the gate flips; if not, attended-gated stands, honestly.

**Reversibility.** Reversible via the #4 procedure.

## 3. SAFETY_FORBIDDEN set = hold as a list (no bulk unblock)

**What.** Of the 62 blocked ops, a design-intentional subset is `SAFETY_FORBIDDEN` — e.g. all 23 `constraints_associativity` blocked rows carry a `SAFETY_`-prefixed `blocked_reason` (associative-evaluator safety), plus raw-command dispatch and COM-reopen-crash classes.

**Ruling.** These stay blocked. The classification is kept as a standing "someday re-examine" list, **not** bulk-unblocked. Opening any individual op requires its own risk assessment and a per-op ballot at the time it is actually needed.

**Reversibility.** Reviewing the list is harmless (read-only). Actually opening an op is near-irreversible risk (a wrongly-unblocked associative/raw op can corrupt drawings), which is exactly why bulk-open is refused.

## 4. headless_safe certification procedure = BUILD (in progress)

**What / why.** 13 committed governed templates are gated by `headless_safe=false` and honestly refuse to run headless (`ATTENDED_ONLY_TEMPLATE`), but the flag is a bare binary with **no procedure to earn `true`**. This is the one forward-value item — it is the only path that actually unlocks those templates.

**Ruling.** Build a defined certification gate (analogous to the per-leg-timeout re-probe that resolved ATTENDED_ONLY 15→0). A template earns `headless_safe=true` only by passing, on a staged copy with the original byte-immutable: (1) headless completion, exit 0, no crash/timeout; (2) original sha unchanged; (3) the effect actually took on the staged copy (a no-op is not certifiable); (4) no attended/interactive dependency; (5) completed comfortably under budget. The gate will correctly *reject* genuinely-attended templates (e.g. hatch, per #2) and *accept* the ones that were only conservatively flagged.

**Status.** Offline tool + tests dispatched to codex 5.4 xhigh (octoloop LOOP-20260708052804). Orchestrator runs the live certification of the 13 templates after review/merge; passers get their flag flipped with an evidence ref, refusals stay honestly attended.

**Reversibility.** The procedure itself is safe (staged copies, original immutable). Flipping a flag is backed by a stored certification envelope and is re-runnable.
