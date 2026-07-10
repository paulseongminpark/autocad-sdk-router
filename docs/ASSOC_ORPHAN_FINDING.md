# Orphan-assoc finding

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
