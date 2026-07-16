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
      **COMPLETE: 40/41 fixtures promoted REACHABLE→RUNNABLE** (targeted reprobe merged → reachable_matrix_20260714.jsonl;
      RUNNABLE 300→340). PASS_WITH_DEFERRAL — remaining 140 REACHABLE are documented needs-state (handle-provisionable
      tail / needs richer fixture DWG / attended); not required for a defensible certification.
      Deferred (geometry-dependent params, no-guess rule): modify.curve.split/to_spline, modify.entity.xdata + symbol_tables
      inspects whose result may be empty (get_xdata/ext_dict/annoscale) — honest REACHABLE-by-design unless richer fixture DWG.
- [x] **P3c — DEGENERATE documentation** — PASS. 7 classified in SDK_CERTIFICATION_RESULTS §3.1: 5 ZERO_ARG_BY_CONTRACT
      (live.reactor.enable, live.overrule.enable, editor.react.events, define.assocaction.create, define.constraint.group)
      + 2 NEEDS_PROFILE_GEOMETRY (write.entity.body, write.entity.solid3d.loft). None a defect.
- [x] **P4a — constraints_associativity** — RESOLVED as NOT a headless build gap (evidence: reports/tickets/M08K-T03.md).
      The 23 blocked assoc ops need the in-app DCM solver / ASM surface modeler / eval callbacks, absent in headless
      CoreConsole; building them hostless would fake the result or invoke a forbidden solver (25 of the 58-op assoc
      brief ARE implemented solver-free; the 33 deferred are honestly deferred). Correctly-blocked, not un-built.
      (An attended-lane build could revisit; out of headless scope.)
- [x] **P4b — layouts_plot_publish** — RESOLVED as NOT a headless build gap (evidence: registry Wave3 no-fake-PASS
      audit notes). `plot.engine.run` = HOST_UNAVAILABLE (AcPlPlotEngine needs an attended/full-AutoCAD plot host);
      `plot.config.settings` = SAFETY_FORBIDDEN (live_edit page-setup mutation, no bounded CAD-OS staged-write contract).
      Both accepted as hard blocks. PLAN_M08PLOT.md retained as design record for a future attended lane / staged-write
      contract + read-only variant. **Net: 0 clean headless build gaps; the headless surface is complete.**
- [x] **P5a — runtime_commands reclassify** — PASS (2026-07-16). 16 blocked runtime_commands ops → `kind=module_event`,
      `dispatchable=false` (host-owned lifecycle deliveries / forbidden loader mutations — never job-dispatchable).
      Registry contract locked by tests/unit/test_module_event_registry.py (4 tests: exact 16-set, flags, no stray,
      10 RUNNABLE registration ops stay dispatchable). Lifecycle certified INDIRECTLY the only honest way — live run
      of tools/module_lifecycle_harness.py: staged fixture → sanctioned probe (inspect.runtime.capabilities) EXIT=0 +
      result ok ⇒ load → kInitAppMsg → dispatch → clean unload all occurred (HARNESS_EXIT=0).
- [ ] **P5b — attended lane** — com_activex 9 + ui/brep-subentity/live/editor incl. the 2 attended CRASH.
      active_document_write_original 4 STAY BLOCKED by design.
- [x] **P6 — fresh rebuild + SHA-256 stamp + full certification report + GitHub** — PASS. Fresh isolated rebuild
      PASS (EXIT=0, VS2026+ObjectARX 2027); SHA-256 manifest (MODULE_SHA256_MANIFEST.md); SDK_CERTIFICATION_RESULTS_20260714.md
      written; committed (82efbb7, 34 files) + **pushed to origin/main** (in sync).
      **⚠ FLAG FOR PAUL**: `prebuilt/2027/*.crx/.dbx/.arx` are already git-tracked (pre-existing commits) — conflicts
      with "source-only". NOT ripped from history autonomously (irreversible). Decide: keep prebuilt binaries in
      repo (common for SDK tools), or `git rm --cached` them + add to .gitignore for source-only.

## Non-goals / deprioritized

- [x] P2 (custom_objects/geometry arx→dbx capability audit): was DEPRIORITIZED (hygiene only) — **completed 2026-07-16**.
  P2a static audit (tools/dbx_capability_audit.py — declared native_api tokens + dispatch code slice + 1-level helper
  taint): 88 audited = 87 dbx_capable + 1 asm_boundary_review (modify.entity.solid3d.boolean, ASM defer line per
  ObjectDBX write-feasibility boundary) + 0 arx_required. Artifact: P2A_DBX_CAPABILITY_AUDIT_20260716.{json,md}.
  P2c applied: 57 ops re-tiered native_arx_only→objectdbx_capable (audit-provenance note per op; engine_tier is
  reporting-only — cadctl by_tier), totals.by_engine_tier rolled (177 arx_only / 306 dbx_capable), suite 1959 passed.
  Runtime corroboration: tools/dbx_import_audit.py (stdlib PE import-table parse) — Ariadne.AcadNativeDbx.dbx imports
  7 DLLs, ALL db-layer (acdb26, AcGe26, CRT/kernel; zero aced/acad/UI binding) ⇒ loadable by a pure DBX host; crx
  control shows the contrast (accore.dll + ASM/BRep enablers). Static verdicts necessary-not-sufficient; the dbx
  module's import purity is the runtime-level proof for the shared code paths.

## Failure-mode guards active this arc

- No fake PASS (R6): every count cites its artifact. Original *.dwg READ-ONLY (probe stages copies, sha-verified).
- FM2/FM8 caught: fleet gate-PASS ≠ applied — 8 fixture diffs were sitting unapplied; harvested + applied this session.
- FM6 caught: "rich sample DWG unlocks all needs-state" — refuted; sample is type-narrow (8 classes), 12 ops need solids absent from it.
- FM4 guard: handle-provisioning mechanism will be PROVEN on one op before any 41-op wave.
