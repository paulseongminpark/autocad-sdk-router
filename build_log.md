# build_log.md -- lane cd2-cadctl (respawn)

## Inherited state (killed lane, uncommitted)

`git status`/`git diff` on entry showed: modified `tools/cadctl.py` (+27 lines,
no deletions) and a new untracked `tests/unit/test_staged_copy_snapshot.py`
(3 tests). The `cadctl.py` diff adds a docstring + `staged_copy_sha256` /
`staged_result` / `staged_result_sha256` fields to `Cad.run_operation`'s
returned envelope.

Reviewed both against ground truth before trusting them (Rule 8):
- Read `tools/autocad-router.ps1` `Invoke-CadJobRoute` lines 1054-1063 directly.
  Confirmed: whenever `-WriteMode` is not `write_original` (the only path
  reachable from `cadctl.Cad.run_operation`, which refuses `write_original`
  outright), the router copies `-InputPath` into its OWN second-level file
  under `staging/dwg_job_<stamp>/input.dwg` and only ever `_QSAVE`s that
  second copy. The path cadctl staged (`staged`) is passed as `-InputPath`
  and is never reopened/rewritten by the router. So the docstring's claim
  ("the copy staged here is never touched again... a true pre-write
  snapshot") is factually correct for the code as it stands today, not just
  a hopeful assumption.
- Cross-checked against `tools/patch_engine.py::apply_staged`'s existing,
  independently-correct handling of the identical router mechanism
  (`staged_input.dwg` kept pristine vs `staged_output.dwg` = explicit copy
  of the router's own mutated result) -- same pattern, consistent.
- Read the p6-hardening root-cause note in
  `D:\dev\.build\cados_plan\runs\waveP\hardening\build_log.md` (item 5b,
  lines ~203-259): before this diff, `run_operation`'s envelope only carried
  `staged_copy` (a bare path, no hash) -- a caller had no in-record artifact
  proving pre-write state, matching the reported "staged_copy=pre-write"
  ambiguity. The recommended fix in that note (second, separately-named
  snapshot + both shas in the record) is exactly what this diff implements.
- Read the inherited test file in full: 3 tests, tmp-file only (no
  accoreconsole), a `_FakeRouterRunJob` that deliberately mimics the real
  router's second-copy-then-mutate behavior (matches the ps1 read above),
  plus a "no fabricated hash when `staged_used` is absent" no-fake-success
  test. Coherent, complete, matches VERIFY criteria as given.

Decision: **keep**, commit as `wip: inherited snapshot work from killed
lane`, continue from it (no rewrite needed -- the fix was already correct;
what remained was verification, not repair).

Baseline before any of my own edits: `pytest tests/unit -q` -> 1076 passed,
14 skipped (1090 total) = canonical 1087 + the 3 new inherited tests.

## Plan

- Confirm inherited unit tests green in isolation and in the full suite
  (done above).
- Live E2E: one `write_copy` run via `cadctl.Cad.run_operation` (op
  `write.entity.line`, trivial args) against a staged copy of
  `tests/fixtures/native_sample.dwg`, to empirically confirm (not just
  read-confirm) that `staged_copy_sha256` != `staged_result_sha256` for a
  real write, that the fixture's own sha256 is unchanged, and that the
  run record alone proves the before/after story.
- Full `pytest tests/unit` once more after the E2E run (tmp-file churn
  under `staging/` should not affect collected test count).
- Commit the E2E evidence note; report back to team-lead.
