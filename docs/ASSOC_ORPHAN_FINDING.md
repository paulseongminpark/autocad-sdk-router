# Orphan-assoc finding

> **RETRACTED 2026-07-10 (evening) — falsifier (b) fired.** The claim below is
> FALSE; it was an artifact of the stale-deploy trap (`prereg_R4t_vintage_reflight.json`
> forensics): both probe runs cited under Evidence arxloaded the 2026-07-09
> prebuilt crx, which predates the `getAssocObjIdsAt` emission code (commit
> `6d59fd5`, 07-10 10:23) entirely. Measured mechanism: both probe census IRs
> contain ZERO occurrences of the `assoc_source_handles` field (not
> present-but-empty — never emitted). The first flight that actually carried
> the emission code is R4u (`runs/e2e_1dwg_R4u_lwz_20260710`, refreshed
> prebuilt): its census reads **66/66 flagged hatches WITH per-loop source
> handles, and all 77 source refs resolve to real entities in the same block
> def** (63 lwpolyline + 14 spline, 0 unresolved — probe
> `assoc_source_resolve_probe.py`, 2026-07-10). The sources exist; re-link is
> feasible; `docs/ASSOC_RELINK_DESIGN.md` is live work (falsifier (b)'s exact
> consequence). The LibreDWG probe (#3) remains unexplained in isolation
> (suspected projection gap for this format vintage) but cannot outweigh two
> live positive reads on the pinned file. LEX-0008's RULE (derived flag,
> compare payload when sources exist) stands; its observation is corrected in
> the ledger. Flag-copy replay (the Implication below) flew in R4u and did NOT
> persist (post reads `is_associative=false` 258/258) — consistent with a
> sourceless flag being unsaveable; real re-link with sources is the repair.

## Claim

The 66 `is_associative=true` hatches in `1.dwg` (sha `14eb65eb...`) reference boundary sources that **do not exist** in the drawing. The associativity flag is orphaned — there is nothing left to re-link it to. Consequently "re-linking" the boundary is not a feasible operation; faithful replay reduces to copying the flag verbatim rather than reconstructing an association.

## Evidence

Three independent probes, all run 2026-07-10, all against `1.dwg` (sha `14eb65eb...`), all agree:

1. **ObjectARX hatch-level.** `AcDbHatch::getAssocObjIds` returned empty for 66/66 flagged hatches. Census run: `runs/census_assoc_20260710`.
2. **ObjectARX loop-local.** `AcDbHatch::getAssocObjIdsAt` returned empty for **every loop** of all 66 hatches (not just the hatch-level rollup). Census run: `runs/census_assoc2_20260710`. Emission code at commit `6d59fd5`.
3. **LibreDWG projection (independent codepath).** `dwg2dxf` projection of `1.dwg` shows no group 97 source-object counts and no boundary-source group 330 refs in any HATCH entity — i.e. no DXF-level trace of associativity data either.

All three probes — two via the native ObjectARX SDK (hatch-level and loop-level) and one via an entirely independent OSS toolchain (LibreDWG) — converge on the same result: zero boundary-source references behind a `true` flag.

## Implication

This is the assoc residue class: 66 canonical mismatches, exactly the `is_associative` flag. The residue folds by flag replay — commit `6d59fd5` consumes the census `is_associative` value directly in the native append builder (previously hardcoded to `kFalse`). No association reconstruction is attempted or needed, because there is no source data to reconstruct from.

R4r adjudicates this against the preregistered target (26,900/27,130).

## Falsifiers

- **(a)** If the R4r assoc class does not fold, flag replay does not survive save/reopen — investigate `evaluateHatch` ordering.
- **(b)** If a future drawing shows nonzero `getAssocObjIdsAt`, the extraction path is validated after all, and the re-link pipeline (`docs/ASSOC_RELINK_DESIGN.md`) becomes live work rather than moot.
- **(c)** If AutoCAD itself resets orphaned assoc flags on save, accept this as an engine-level quotient and legislate it in the LEX ledger.
