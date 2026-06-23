# WAVE4X DB TXN WRITE — plan

## Scope

Pane 5 claim set:
- `edit.assocdata.xref`
- `repair.assocdata.audit`
- `live.apply_patch`

Residual staged-write/object-lifecycle subset called out by the packet:
- transaction wrappers/status helpers
- safe object lifecycle open/close upgrade/downgrade flows
- extension dictionary creation
- dictionary/xrecord/xdata staged writes
- diff/validation/journal evidence for mutation paths

## Findings before coding

1. `m08e` still contains several "write" handlers that intentionally roll back (`staged_rolled_back:true`) instead of committing a staged copy. That is good for scratch probes, but it is not bounded write evidence for claimed mutation closure.
2. `patch_engine.apply_staged(...)` already has the full staged-copy journal/diff/validation lifecycle, but only for the patch-op map. There is no equivalent generic staged executor for arbitrary native write operations.
3. `edit.assocdata.xref` and `repair.assocdata.audit` were blocked for safety because there was no bounded staged-write contract. With a staged executor + native handler + no-original-write proof, they are reopenable.
4. `live.apply_patch` exact semantics (mutate active document) conflicts with the packet safety rules. Safe staged replacement already exists (`apply.patch` / patch engine). Likely closeout = `deprecated`, not exact in-place implementation.

## Implementation plan

1. **Generic staged native mutation executor**
   - Extend `tools/patch_engine.py` with a generic staged native-op path that:
     - stages a copy
     - runs pre/post `inspect.database.graph`
     - applies an arbitrary native op in `write_copy`
     - computes diff
     - validates
     - writes journal/result artifacts
   - Keep original DWG hash proof.
   - Make native job docs pass args both top-level and in `args` for compatibility.

2. **Object lifecycle / staged-write correctness**
   - Convert `m08e` write residual handlers from rollback-only scratch probes to real staged mutations on `ctx.pDb` with explicit `commit()`.
   - Keep no-original-write invariant (router-staged copy only).
   - Preserve structured result envelopes.

3. **Assoc mutation handlers**
   - Reopen `edit.assocdata.xref` in `m08kc_handlers.inc` with staged transaction + document lock + xref/assoc state reporting.
   - Reopen `repair.assocdata.audit` in `m08kc_handlers.inc` with staged transaction + document lock + audit result reporting.
   - Update source tests to allow these two exact APIs while still forbidding solver-only surfaces.

4. **Registry closeout**
   - `edit.assocdata.xref` -> `implemented`
   - `repair.assocdata.audit` -> `implemented`
   - `live.apply_patch` -> `deprecated` (safe staged replacement = `apply.patch` / staged executor)
   - Add WAVE4X evidence refs / notes.
   - Update host/coverage reports if needed after reconcile.

5. **Validation**
   - targeted unit tests first
   - full `pytest tests -q`
   - `python tools/cadctl_cli.py registry coverage`
   - `python tools/reconcile_native_registry.py`
   - native build if source changes require compile proof

## Expected outputs

- `reports/tickets/WAVE4X_DB_TXN_WRITE.md`
- `reports/tickets/WAVE4X_DB_TXN_WRITE.json`
- `reports/tickets/WAVE4X_DB_TXN_WRITE_OPS.json`
- `handoff/pr/WAVE4X_DB_TXN_WRITE.patch`
- `handoff/tickets/WAVE4X_DB_TXN_WRITE.zip`
