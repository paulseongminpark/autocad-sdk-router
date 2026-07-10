# Associative hatch re-link — design v0

> **OUTCOME 2026-07-11 (R4v flight + R4w remeasure): ARC CLOSED — relink landed 66/66.**
> Every relink op returned ok with `associative_after=true` (flight result files +
> `reports/interior100/R4v_remeasure_assoc.json`); net +59, R4v adjudicated FAIL-by-2
> against its band because the repair UNMASKED loop-notation drift of the id-derived
> re-derivation (the prereg risk-register item): 5 closed-cycle rotations (point-cloud
> 0.0, legislated LEX-0012, folded on R4w = 27,121/27,130 point-band hit) + 2 spline
> multi-span → per-Bézier re-decompositions (curve-identical 9.2e-4 proxy, accepted
> residue outside the fingerprint). Dissection: `loops_residue_analysis_R4v.json`.
> The design text below is preserved as-built.

> **STATUS 2026-07-10 (evening): LIVE — this design is the active repair arc (P3 → R4v).**
> The intervening orphan claim (`docs/ASSOC_ORPHAN_FINDING.md`, "sources do not
> exist, re-link is moot") is RETRACTED — it was a stale-deploy artifact; R4u's
> census (first flight of the loop-local emission) reads 66/66 flagged hatches
> with per-loop sources, all 77 refs resolving in-def (63 lwpolyline + 14
> spline). Implementation binding for R4v: Step A handle translation uses the
> append-op `source_handle` → result `new_handle` ledger accumulated by
> `patch_engine` across batches (explicit per-op correspondence, not positional);
> relink ops are emitted at the END of the op stream (all boundary sources
> exist by then — Step C ordering satisfied); Step B1 native op is
> `write.block.relink_hatch_assoc` (open by handle, `setAssociative(true)`,
> per-loop id-derived loop REPLACEMENT via `removeLoopAt` +
> `insertLoopAt(int, type, AcDbObjectIdArray)` — ObjectARX 2027 exposes no
> per-loop assoc setter; `setAssocObjIdsAt` named below predates the header
> check — then `evaluateHatch` + persistent reactors on sources); translate
> failure is a loud per-op error result (no fake success). Fingerprint
> comparison of the payload is legislated as per-loop cardinality (LEX-0011);
> exact-correspondence checking lives in the post-flight assoc audit (Gate 2).

## Evidence base
- Native extraction sealed diff exists at `D:\dev\99_tools\octoloop\runs\LOOP-20260709113826-18k0wul\evidence\assoc-source-extraction.diff.patch`.
- The diff introduces the IR field name `assoc_source_handles` in `AriadneNativeJob.cpp`.
- Emission path uses `AcDbHatch::getAssocObjIdsAt` for loop-local emission and `AcDbHatch::getAssocObjIds` as source fallback for broad compatibility.
- The loop payload is emitted in the same sequence as IR `loops[]`, so order is a stable contract for reattachment.
- Measured current state before this design: 66 hatches are `is_associative=true` in source; 63 of those previously also had hatch pattern phase deltas, and phase drift is now fixed independently from associativity.

## Extraction contract
- `assoc_source_handles` is stored per hatch as an outer JSON array aligned to hatch loops.
- Exact shape proposal:

```json
{
  "id": "hatch_handle_or_id",
  "loops": [...],
  "is_associative": true,
  "assoc_source_handles": [
    ["handle_loop_0_source_0", "handle_loop_0_source_1"],
    ["handle_loop_1_source_0"]
  ]
}
```

- Each `assoc_source_handles[i]` maps to `loops[i]`, not the hatch as a whole.
- Outer list length must equal hatch loop count when associative metadata is known.
- Handle format is the source native object handle string emitted by extraction (hex handle string as used by current IR handle vocabulary).
- Present but empty `assoc_source_handles` means "associative payload known, zero boundary sources", and the hatch should be treated as non-associative at regen.
- Missing `assoc_source_handles` means legacy extraction or unsupported source, and the hatch stays non-associative.
- Backward compatibility: readers must ignore `assoc_source_handles` for old docs; writers must treat missing field as opt-in data not required for processing.

## Re-link pipeline
- Step A: for each hatch, if `assoc_source_handles` exists, compute candidate source ids in regen space by iterating loops in index order and translating each source handle through the run `handle_map`.
- Step B: translate failures are terminal for that hatch.
- Step B1 (recommended implementation): native ObjectARX pass in `Ariadne.AcadNative`.
- Native path emits hatch non-associative first through existing append flow, then applies `AcDbHatch::setAssocObjIdsAt` for each loop index when all mapped source ids are available.
- Native path advantage is deterministic API-level reactor wiring, no UI, no command parser mode dependence, and no headless interaction ambiguity.
- Native direct-create option exists (`appendLoop` with assoc ids when supported by current writer surface), but is only enabled when the append pipeline can guarantee assoc ids are available at creation time.
- Step B2 (fallback only): generate an accoreconsole script template invoking `HATCHEDIT`/associative-edit behavior after hatch creation.
- Script route is rejected as primary because localization/prompt variance and weaker error observability make headless automation brittle in CI and batch conversion.
- Step C: enforce ordering constraints.
- Boundary sources must exist before relink to avoid orphaned or stale reactor attachments.
- `handle_map` lookup is performed after boundary/entity writes.
- Hatch creation must happen before relink call; re-arming in-place is the safe current order in an append-first pipeline.
- Step D: idempotency and dry-run.
- Idempotent behavior: if re-extracted output already reports `is_associative=true` and equal `assoc_source_handles`, skip the relink operation for that hatch.
- Dry-run mode emits an operation plan: hatch id, loop index, source handle candidates, mapped candidates, chosen route, and skip/reject rationale.
- In non-dry mode, successful re-link attempts are recorded in regen artifacts for traceability.

## Validation gates
- Gate 1: Structural expectation.
- All source hatches with `is_associative=true` and non-empty `assoc_source_handles` are discovered and attempted.
- Gate JSON (minimal):

```json
{
  "gate": "assoc_relink",
  "total": 0,
  "attempted": 0,
  "relinked": 0,
  "skipped": 0,
  "failed": 0,
  "drift_detected": 0
}
```

- Gate 2: Re-extract comparison.
- Re-run extraction on regenerated output.
- Verify for each candidate hatch: `is_associative` is true, loop-count matches, and `assoc_source_handles` round-trips exactly after handle remap to regen handles.
- Gate failure if any hatch loses associative flag or loses/reorders loop linkage.
- Gate 3: Metamorphic sanity check.
- In a staging copy, move exactly one source boundary entity for one linked hatch and re-extract; for linked hatches, hatch boundary geometry should change without handle replacement and remains linked to that boundary.
- Gate output includes pass/fail, moved entity id, and whether hatch geometry delta matches moved boundary, while object ids are stable.

## Failure modes
- Handle-map miss: detected when one or more source handles cannot be resolved to any regen handle; action is record `ASSOC_RELINK_UNRESOLVED` and emit hatch as non-associative without synthetic success.
- Source entity in different block/space: detected by mismatch in resolved target block context (space/owner/insert context differs); action is record `ASSOC_RELINK_OWNER_MISMATCH` and defer/demote to non-associative.
- Loop-index mismatch: detected when mapped loop count differs from target hatch loop count or order; action is record `ASSOC_RELINK_LOOP_MISMATCH`, abort hatch relink and keep non-associative.
- Reactor not firing in headless session: detected by post-append query still reporting no associative reactor links; action is record `ASSOC_RELINK_NO_REACTOR`, keep hatch non-associative and continue pipeline.
- Partial assoc (mixed good/bad loops): detected per-loop resolve/attach results are incomplete; action is record `ASSOC_RELINK_PARTIAL`, skip full attachment for that hatch and emit non-associative fallback with unresolved loop indices.
- Any unsupported object class encountered in `assoc_source_handles`: detected when mapped handle resolves to non-boundary entity; action is downgrade with `ASSOC_RELINK_UNSUPPORTED_SOURCE`.

## Open questions
1. Should missing `assoc_source_handles` be interpreted as explicitly unsupported source and therefore force non-associative, or should we preserve existing non-assoc behavior and only attempt when field exists?
2. Should loop-mismatch between source and target be hard-fail per hatch, or should we attempt loop trimming/padding and attempt best effort with partial-link semantics?
3. Should non-associative fallback set require a dedicated field in regenerated IR for traceability, or only runtime logs?
4. Is `assoc_source_handles` best represented as array-of-arrays only, or should future extensibility include a nested object with loop ids and source type metadata?
5. Do we want an always-on dry-run report in normal runs to support large-batch QA, or only emit when `--assoc-dry-run` is enabled?
