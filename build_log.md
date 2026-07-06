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

## Done

- A + B wired into `main()` (e036c57). Overall `summary["status"]` is now
  `combine_gate_statuses([entity_gate, records_gate])`, never a hardcoded
  `"ok"`. Exit code: 0 = ok, 1 = ok_with_drops, 2 = anything worse.
- C: `tools/cert_artifact_index.py` (a3fe93c). Smoke-tested read-only
  against the canonical repo's real `runs/` tree: found 55 genuinely
  malformed JSON files (unescaped control characters in M08N native-writer
  `input.get.point` etc. output) -- real signal, not a scanner bug; not in
  this lane's scope to fix (owned by whichever wave wrote that writer).
- 27 new tests, `tests/unit/test_capstone_gate.py` (a3fe93c, 6c4cf83). Caught
  two real defects in the inherited code before they reached a live run:
  1. `table_record_diff_reports`'s `diff_fn` fallback used
     `getattr(mod, attr, mod.layer_record_diff)` -- the default expression
     is evaluated eagerly, so it raised `AttributeError` on any module
     missing `layer_record_diff` even when the PRIMARY attr resolved fine.
     Fixed with short-circuit `or`.
  2. `build_records_patch` shipped `postconditions: []` unconditionally.
     Its own comment reasoned (correctly) that `classify_patch_risk`'s
     missing-postconditions risk bump only applies to mutation-of-existing
     ops -- but missed `patch_engine.require_validation`, a SEPARATE,
     unconditional guard (non-empty ops + empty postconditions -> blocked).
     This one was NOT caught by the unit tests (they inject a fake
     `patch_engine_mod`, bypassing the real guard) -- only the live E2E
     surfaced it. Fixed: one `{"subject": "<label>_exists", "op": "exists",
     "value": name}` postcondition per op, matching
     `op_roundtrip_probe._build_patch`'s existing single-record convention.

## Live E2E evidence (proof of gate firing)

`python tools/full_roundtrip_capstone.py --out-dir runs/capgate_e2e
--per-kind-limit 1 --with-records --mint-seed-if-missing`, exit code 1.

`runs/capgate_e2e/summary.json`:
- `regen.gate`: requested_count=7, applied_count=6, dropped_count=1,
  dropped_ops=[{"operation": "insert_block", "reason": "no live native
  write handler..."}], gate_status="ok_with_drops".
- `records_regen.gate`: requested_count=5, applied_count=5, dropped_count=0,
  gate_status="ok" (the postconditions fix above -- before it, this batch
  came back `apply_status="blocked"` / `"guards failed: require_validation"`
  on every run, 100% failure).
- top-level `summary["status"]` = `"ok_with_drops"` (never silently "ok"),
  `summary["dropped_ops"]` = exactly the one insert_block entry, tagged
  `batch: "entity"`.
- `table_record_diffs`: layer/dimstyle/linetype/textstyle all
  `records_compared=1, zero_diff_count=1` (true post-regen zero-diff, not
  the old self-check-against-itself placeholder). `vport` came back a REAL
  mismatch: the `"*Active"` viewport's `center/height/width` differ between
  census (production drawing's captured view state) and the regenerated
  blank seed's own default active-viewport state -- plausibly `"*Active"`
  is a reserved, AutoCAD-managed record that `create_vport` cannot fully
  override, not a bug in this batch's own diff machinery. Flagged, not
  chased (out of this lane's scope; #130 was to make the diff REAL, and it
  is -- catching a genuine discrepancy is the mechanism working, not a
  regression to fix here). `ucs`/`view` had 0 named records in this bounded
  run (`per-kind-limit 1` + this particular census), correctly reported as
  vacuous, not a false pass.
