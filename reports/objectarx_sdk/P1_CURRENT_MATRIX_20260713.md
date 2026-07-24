# P1 — Current-build reachability matrix + CRASH triage

**Status: PASS** · sweep v2 `b9tyvha1x` SWEEP_EXIT=0 · 2026-07-13
Matrix: `measure/reachable_matrix_20260713.jsonl` — 489 rows, 489 unique op_ids,
0 dups, every row `classification_source: live_probe` (accoreconsole, staged-copy
fixtures, original sha verified unchanged).

## Distribution (489 implemented ops probed) vs the Jul-6 baseline

| class | Jul-6 (465) | **current (489)** | meaning |
|---|---|---|---|
| RUNNABLE | 242 | **300** | real non-degenerate result live |
| REACHABLE | 161 | **180** | dispatch + arg-validation OK; needs valid-arg fixture (P3b) |
| RUNNABLE_BUT_DEGENERATE | 28 | **7** | succeeds on empty args (P3c) |
| CRASH | 34 | **2** | — |

## CRASH triage — ZERO genuine native faults

The 34→2 collapse confirms the Lane I router fix (`reports/lane_i_router_fix_resolution.json`,
33/34 pre-fix artifacts) + the fresh build. The 2 remaining:

- `live.jig.point_probe` (fam=live) — the exact 1 op Lane I did NOT resolve;
  `handler.execution_host_class == full_autocad` (interactive jig).
- `live.status` (fam=live) — live-runtime status; live.* effects are observable
  only in an attended session (`config/host_matrix.v2.json` live-family note).

Both are **attended-only ops failing headless as expected — not native bugs.**
They belong in the P5b attended lane and should carry `verification_lane: attended`.
Net: **no headless handler crashes to patch.**

## P3c — the 7 DEGENERATE are the known intentional no-fixture set

`live.reactor.enable`, `live.overrule.enable`, `define.assocaction.create`,
`define.constraint.group`, `editor.react.events`, `write.entity.body`,
`write.entity.solid3d.loft` — exactly the set `probe_reachability.py` documents as
deliberately fixture-less (would game the RUNNABLE classifier, or attended-only).
P3c = document them as ZERO_ARG_BY_CONTRACT / attended, not "fix validation".

## P3b — 180 REACHABLE fixture-authoring targets (20 families)

brep_solids 50 · entities 36 · constraints_associativity 27 · objectdbx_database 14 ·
symbol_tables_dictionaries 10 · geometry_kernel 10 · graphics_system 8 · anchor 4 ·
blocks_xrefs_clone 4 · custom_objects_protocols 4 · validate 2 · patch 2 · inspect 2 ·
query/render/apply/diff/com_activex/corpus/verify 1 each.

Pipeline: per-family fragment `measure/reachable_fixtures/<family>.json` (disjoint) →
`_merge_reachable_fixtures` → re-probe → RUNNABLE promotion is the objective gate.
Validate the pipeline inline on one family, then fleet the rest.
