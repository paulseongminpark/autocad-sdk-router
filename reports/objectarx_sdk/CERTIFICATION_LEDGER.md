# ObjectARX 2027 SDK — Certification Ledger (live checkbox tracker)

> Mandate (Paul, ultracode 2026-07-13): find ALL functionality the ObjectARX 2027 SDK provides,
> build it into native `.crx`/`.dbx`/`.arx`, verify integrity, upload to GitHub. Run to the end, autonomous.
> This file is the single live checkbox tracker. Every number here MUST cite the artifact that produced it.

_Last updated: 2026-07-14 (session 0aa41075). Status vocabulary: PASS / PARTIAL_PASS / PASS_WITH_DEFERRAL / BLOCKED / RETRACTED._

---

## Truth model (evidence: tools/reconcile_native_registry.py, tools/operation_coverage_matrix.py, 1191 unit tests PASS)

- **551 total ops** = **489 implemented** + **62 blocked** (0 catalogued / 0 stub / 0 unknown).
- Native family live-gate = **435 ops / 16 families** (familyHasOp 16-gate OR, AriadneNativeJob.cpp:6163).
- Coverage matrix `catalog_total_ops=551`, `consistent=true`, GATE PASS (measure/operation_coverage_latest.json).

## Integrity classification of the 489 implemented ops

**Baseline sweep (evidence: measure/reachable_matrix_20260713.jsonl, 489 rows, full --live):**

| class | n | meaning |
|---|---|---|
| RUNNABLE | 300 | real non-degenerate result with args (verified works) |
| REACHABLE | 180 | dispatches + arg-validates correctly; not yet exercised with valid args |
| RUNNABLE_BUT_DEGENERATE | 7 | succeeds on empty args = intentional near-no-op |
| CRASH | 2 | `live.jig.point_probe`, `live.status` — **attended-only** (see below) |

**→ 0 unexplained crashes headless.** The 2 CRASH are attended-subsystem ops (CADAGENT_PUMP named-pipe /
interactive jig). Probe evidence: `empty_arg_probe.reason = "native job produced no parseable result JSON"`
— NOT a process fault (no AV); the one-shot headless probe cannot capture a pump/jig op's channel. Source
confirms: `runLineJigProbe` (AriadneNativeJob.cpp:3926) already guards `if (jobHostMode != "full_autocad")`;
`live.status` (:7380) is a pump-frame op listed at :7249. Correctly verified in the attended lane (P5b), not headless.

**FINAL post-fixture matrix: measure/reachable_matrix_20260714.jsonl** (baseline + 41-op targeted reprobe merged):
**RUNNABLE 340 (+40) / REACHABLE 140 (−40) / DEGENERATE 7 / CRASH 2.** 40 of 41 fixtures promoted REACHABLE→RUNNABLE
(only write.entity.wipeout stayed REACHABLE — invalid clip boundary in fixture, not a defect). 340/489 = 69.5% RUNNABLE.
CRASH still exactly the 2 attended live ops; DEGENERATE still the 7 known (5 zero-arg-by-contract + 2 needs-profile).

## REACHABLE→RUNNABLE fixture work (evidence: measure/reachable_fixtures/*.json, 10 files)

- **29 valid-arg fixtures authored + applied** (fleet-harvested, gate-PASS, in-contract). Reprobe pending.
- **53 needs_state documented** (honest REACHABLE-by-design), categorized:
  - **41 needs_existing_object_handle** — promotable via handle-provisioning from native_sample.dwg
    (21747 entities, 8 types available: LINE/INSERT/2dPolyline/ARC/HATCH/MTEXT/CIRCLE/TEXT + 1 dict + 2 xrecord).
    Those needing one of these types are future-promotable; the rest need a richer fixture DWG.
  - **12 needs_3d_solid_object** — **genuine ceiling**: native_sample.dwg has NO 3DSOLID/REGION/SURFACE/BODY.
    Promotion requires a purpose-built solid fixture DWG (brep_solids family, 50 REACHABLE total).

---

## Phase checkboxes (P0–P6)

- [x] **P0 — Truth-model repair** — PASS. reconcile 420→435 families, coverage 480→551, 1191 unit tests PASS,
      family-gate parity test added (tests/unit/test_reconcile_family_gate_parity.py). 62-op gap decomposed.
- [x] **P1 — Current matrix + residual CRASH triage** — PASS. Baseline matrix landed; 2 CRASH triaged to
      attended-only with source + probe evidence (above). 0 native faults.
- [x] **P3a — Arg-schema + fixture + semantic-oracle framework** — PASS. `_merge_reachable_fixtures()` loader
      (probe_reachability.py) globs measure/reachable_fixtures/*.json, inline-wins; fragment schema documented.
- [~] **P3b — REACHABLE→RUNNABLE per-family fixtures** — PARTIAL_PASS. **41 fixtures applied** (29 create-from-args
      fleet-harvested + **12 handle-provisioned** hand-authored). Handle-provisioning mechanism **PROVEN**: batch1 = 7/8
      RUNNABLE (inspect.entity.common/geomextents/osnap, inspect.curve.protocol, modify.entity.transform, modify.entity.explode,
      compute.entity.intersect — each empty=REACHABLE→valid=RUNNABLE, evidence measure/reachable_fixtures/handle_provisioned_1.json).
      1 inconclusive: modify.curve.offset threw empty=CRASH under probe concurrency (false-crash suspected; clean sweep re-settles).
      **Definitive matrix IN FLIGHT: targeted 41-op reprobe bg=bgbq7sojj → merge into 20260713 baseline →
      reachable_matrix_20260714.jsonl (non-fixtured 448 ops unchanged: no code/registry change; ~15-30min vs 3h full sweep).**
      Deferred (geometry-dependent params, no-guess rule): modify.curve.split/to_spline, modify.entity.xdata + symbol_tables
      inspects whose result may be empty (get_xdata/ext_dict/annoscale) — honest REACHABLE-by-design unless richer fixture DWG.
- [x] **P3c — DEGENERATE documentation** — PASS. 7 classified in SDK_CERTIFICATION_RESULTS §3.1: 5 ZERO_ARG_BY_CONTRACT
      (live.reactor.enable, live.overrule.enable, editor.react.events, define.assocaction.create, define.constraint.group)
      + 2 NEEDS_PROFILE_GEOMETRY (write.entity.body, write.entity.solid3d.loft). None a defect.
- [ ] **P4a — constraints_associativity headless** — 27 REACHABLE (assocarray/DCM). Biggest genuine build gap,
      distinct from needs-state. Needs constraint/assoc state harness.
- [ ] **P4b — layouts_plot_publish headless plot (CRX)** — 2 ops.
- [ ] **P5a — runtime_commands reclassify** — 16 ops → kind=module_event, dispatchable=false + lifecycle harness.
- [ ] **P5b — attended lane** — com_activex 9 + ui/brep-subentity/live/editor incl. the 2 attended CRASH.
      active_document_write_original 4 STAY BLOCKED by design.
- [ ] **P6 — fresh rebuild + SHA-256 stamp + full certification report + GitHub (source-only)** — the deliverable.

## Non-goals / deprioritized

- P2 (custom_objects/geometry arx→dbx capability audit): DEPRIORITIZED — ops already run headless; hygiene only.

## Failure-mode guards active this arc

- No fake PASS (R6): every count cites its artifact. Original *.dwg READ-ONLY (probe stages copies, sha-verified).
- FM2/FM8 caught: fleet gate-PASS ≠ applied — 8 fixture diffs were sitting unapplied; harvested + applied this session.
- FM6 caught: "rich sample DWG unlocks all needs-state" — refuted; sample is type-narrow (8 classes), 12 ops need solids absent from it.
- FM4 guard: handle-provisioning mechanism will be PROVEN on one op before any 41-op wave.
