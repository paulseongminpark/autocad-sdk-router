# build_log.md -- lane ca2-capgate (respawn)

## Inherited state (killed lane, zero commits)

`git diff` on entry showed one uncommitted hunk in `tools/full_roundtrip_capstone.py`
(+282 lines, no deletions): `record_op_args_from_record`, `RECORD_TABLE_CLASSES`,
`build_records_patch`, `table_record_diff_reports`, `regen_gate_report`,
`combine_gate_statuses`. Docstrings cite "Closeout #129a"/"Closeout #130" and
this same build_log.md (which the dead lane never got to create).

Reviewed: coherent, correctly reuses existing `record_diff_report` /
`op_roundtrip_probe` field-list constants, matches the #129a/#130 spec in the
dispatch prompt exactly. NOT wired into `main()` -- `main()` still had the old
unconditional `summary["status"] = "ok"` and the old self-check
`layer_record_report` (diffing census_ir against itself). This is the building
blocks, not the fix. Decision: keep, commit as
`wip: inherited gate work from killed lane` (cc179af), continue from it.

Baseline before any of my own edits: `pytest tests/unit -q` -> 1073 passed,
14 skipped (1087 total) -- matches canonical repo total exactly.

## Plan

- A (#129a): wire `regen_gate_report`/`combine_gate_statuses` into `main()`,
  replacing the unconditional `summary["status"]="ok"`.
- B (#130): wire `build_records_patch` + `table_record_diff_reports` into the
  `--with-records` path (apply a real patch, use the real post_ir), rename
  the misleading `layer_record_report` output.
- C (finding 6): new `tools/cert_artifact_index.py`.
- Tests: `tests/unit/test_capstone_gate.py`.
- One bounded live E2E proving the gate fires on the known `insert_block`
  drop from the reference run.
