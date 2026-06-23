# M08C Deferred Sweep — Plan

## Scope
- Burn down remaining feasible READ/WRITE cleanup items that do not need attended GUI or canonical deploy.
- Remove invented/dead handler drift.
- Keep registry/test/report consistency honest.

## Current focus
1. Reconcile native family sources against `config/operations.v2.json`.
2. Remove dead/invented handler branches from:
   - `src/Ariadne.AcadNative/families/m08k_handlers.inc`
   - `src/Ariadne.AcadNative/families/m08m_handlers.inc`
3. Update source-level tests so they:
   - pin the real implemented sets,
   - assert drift ops stay out of `HasOp`/`Dispatch`,
   - keep existing deferred ops out of `HasOp`.
4. Validate:
   - `python -m pytest tests -q`
   - `python tools\cadctl_cli.py registry coverage`
   - `python -m json.tool reports\operation_coverage_latest.json`
   - no original DWG modification

## Completion rule
- Every touched op ends as implemented, hard_blocked, or deprecated.
- No invented/dead handler refs remain in the assigned cleanup scope.
