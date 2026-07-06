# Closeout-wave lane logs (merged)

---
## Lane cd2-cadctl (#117)

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

## Live E2E result (DONE)

Ran `cad.run_operation("write.entity.line", args={layer:"0",
start:{0,0,0}, end:{10,0,0}}, write_mode="write_copy",
dwg_path=tests/fixtures/native_sample.dwg)` for real, headless, through
the actual router (`accoreconsole`, native ARX/DBX lane) -- no mocks.

```
staged_copy_sha256   (pre)  = eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76
staged_result_sha256 (post) = 070471ddcf13535f6e4fe3b9594127dc470ae85c9b4527b5d798993d4229b32c
fixture sha before == after = eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76 (unchanged)
result.modelspace_entities_after = 21748 (a new entity really landed)
exit_code = 0, status = ok
```

Independent recomputation of both shas from the files on disk matched the
record's values exactly. Pre != post, proving a real write happened; the
original fixture's sha is bit-identical before and after; the run record
alone (no re-derivation) proves the before/after story, which was exactly
the gap item 5b called out.

**Correction to the p6-hardening root-cause note, made with live evidence,
not assumption**: that note said `cadctl.run_operation` reports
`env["staged_copy"] = str(staged)` and that "by return time [this] holds
POST-write bytes if a write op ran." This run disproves that specific
claim: `staged_copy_sha256` above equals the ORIGINAL fixture's sha
byte-for-byte -- `staged` (cadctl's own copy) was never touched, exactly
as the inherited docstring/tests assert and as reading
`autocad-router.ps1` lines 1054-1063 predicts (the router always makes
its OWN second-level copy before any `_QSAVE`, because `write_original`
is unreachable from this surface). The REAL pre-existing bug was narrower
than that phrasing suggests: no hash of any kind was ever recorded for
either the pre- or post-write state, so a caller had nothing to verify
from the record alone -- not that the wrong file was being hashed. The
fix (both shas, both labeled and present in the record) closes the actual
gap either way.

Full suite after the E2E run: `pytest tests/unit -q` -> 1076 passed, 14
skipped (1090 = canonical 1087 + 3 new tests), unchanged from the
pre-E2E baseline. `git status` after the run showed only
`reports/autocad_router_status_latest.json` touched (the router's own
volatile live-probe snapshot, regenerated as a side effect of any
`-Action run` invocation, out of this ticket's scope) -- reverted with
`git checkout --` to keep the diff surgical.

---
## Lane cb2-irmap (#129b + #119)

# build_log.md — lane cb2-irmap (tickets #129b + #119: IR->patch mapping truth)

Respawn of a lane killed by a usage limit; worktree survived clean, zero commits. Branch
`cados/cb-irmap`. Scope: `tools/ir_to_patch.py`, `tools/patch_ops/{entities,blocks}.py`,
`config/operations.v2.json` registry metadata scalars, new unit tests. Did not touch
`tools/full_roundtrip_capstone.py`, `tools/op_roundtrip_probe.py`, C++ sources, `tools/cadctl*`.

## #129b -- INSERT emits create_blockref, never insert_block

Root cause: `patch_ops/entities.py`'s `ir_op_for` never had a `kind == "block_reference"` case
even though `create_blockref` (`write.entity.blockref`) was fully wired in `WRITE_OP_MAP` /
`build_job_args` since the w3-insert wave. Every INSERT fell through to
`patch_ops/blocks.py`'s own `ir_op_for`, which emitted `{"operation": "insert_block", ...}` --
an op id no registry entry ever declares (matches regen/journal.json's "insert_block is not
declared" warning; the canonical capstone run `runs/capstone_final_20260706_062040` showed 2
INSERTs silently skipped). blocks.py's own header comment already claimed this "degrades to
not_implemented / deferred" -- the code did not actually do that; it emitted a fake op id
instead of returning `None`.

Fix:
- `entities.py`: added the missing `kind == "block_reference"` case -> `create_blockref` with
  `block_name/position/scale/rotation/layer` (matches `build_job_args`'s existing
  `write.entity.blockref` branch exactly; `block_name -> "name"` rename lives there, not here).
- `blocks.py`: `ir_op_for` now unconditionally returns `None` (this family maps no IR kind of
  its own); removed the `insert_block` stand-in.

Block-def dependency (same ticket): a fresh/seed regen target has none of the source DWG's
custom block definitions, so a bare `create_blockref` fails native `BLOCK_NOT_FOUND`
(m08g_handlers.inc: `pBT->getAt(name, blockId)` errors if the name isn't in the target's block
table). Added:
- `blocks.py`: `block_def_ops(block_def)` -- one IR `block_definitions[]` entry -> `(ops,
  deferred)`: a `create_block` (idempotent BTR creation) plus one `append_block_entity` per
  `def_entities` item whose kind `write.block.append_entity`'s native handler
  (`m08eBuildEntityForAppend`) can represent (line/circle/arc/text only). An entry with no
  inlined `def_entities` at all, or a `def_entities` item of an unsupported kind, is reported in
  `deferred` (with a `reason`), never silently dropped or silently emitted as an empty block.
- `ir_to_patch.py`'s `build_patch_from_ir`: for each `block_reference` entity, looks up
  `ir.get("block_definitions")` by `block_name`. Found + not yet emitted this patch -> prepend
  `block_def_ops()`'s ops once per name. Not found -> honest deferral for that INSERT (never
  falls back to an undeclared op).

## #119 -- heavy 2D/3D polyline keeps its legacy type on regen

Root cause: `AcDb2dPolyline` (true legacy 2D) and `AcDb3dPolyline` both normalize to IR
`kind: "polyline"` / `dxf_name: "POLYLINE"` (`ir_builder.py`'s `_NATIVE_CLASS_TO_DXF_KIND`), but
`entities.py`'s `ir_op_for` folded `("lwpolyline", "polyline")` into the SAME branch ->
`create_polyline` (`write.entity.polyline`, which regenerates a real `AcDbPolyline`/LWPOLYLINE).
Capstone evidence: `POLYLINE attempted=2 removed=2` + `LWPOLYLINE added=2` -- the legacy entity
was silently downgraded. (Golden-DWG fact check: `tests/golden/expected_counts.json` shows all
1874 `POLYLINE` entities in that DWG are `AcDb2dPolyline` -- 0 `AcDb3dPolyline` -- so the
capstone's 2-entity sample is consistent with this being the only class actually hit so far, but
the mapping bug applies to either class equally.)

Fix: split the branch on the entity's own `"class"` field (not just `geometry.kind`):
- `kind == "lwpolyline"` (unchanged) -> `create_polyline`.
- `kind == "polyline"`, `class == "AcDb2dPolyline"` -> `create_polyline2d_deep`
  (`write.entity.polyline2d.deep`; already a live-wired op from the p4-poly2d wave, just never
  reachable from `ir_to_patch`). Carries per-vertex `bulge/start_width/end_width` plus entity-level
  `elevation/closed/default_start_width/default_end_width`.
- `kind == "polyline"`, `class == "AcDb3dPolyline"` -> `create_polyline3d`
  (`write.entity.polyline3d`; also already live-wired, also never reachable). Plain `{x,y,z}`
  points, no bulge, no `closed` (the native handler never reads it either).
- `kind == "polyline"`, any other class -> `None` (honest deferral; no class-guessing).

## config/operations.v2.json -- rollup scalar reconciliation (ticket point 3)

Recomputed every `totals`/`coverage` scalar directly from the 525-record `operations[]` array
(same methodology the already-matching sibling fields in the same blocks already use) and
compared:

| Scalar | Declared (before) | Recomputed | Fixed to |
|---|---|---|---|
| `totals.total` | 521 | 525 | 525 |
| `totals.by_engine_tier.native_arx_only` | 233 | 232 | 232 |
| `totals.by_engine_tier.objectdbx_capable` | 222 | 227 | 227 |
| `coverage.wired_ops` | 33 | 29 | 29 |

`coverage.wired_ops`'s fix is internally cross-checked, not just array-recomputed: its own
siblings `wired_native` (28) + `wired_managed` (1) already summed to 29, not 33 -- the declared
33 disagreed with the registry's own internal arithmetic, independent of any external
recomputation.

Already matching (no change): `totals.operations` (525), `totals.by_status`, `totals.by_family`,
`coverage.operation_records` (525), `coverage.{implemented,wired,stub,catalogued,blocked,
deprecated,unknown}`.

Explicitly left alone (per ticket instruction -- historical, different axis, not this ticket's
scope): every `catalog_*` key (`catalog_total_ops`, `catalog_family_heads`, `catalog_by_tier`,
`catalog_by_family`, `catalog_classified_ops`, `catalog_unclassified_ops`,
`catalog_classification_status`) -- the frozen 480-op SDK catalog census, a different question
than the 525-op build registry.

**Flagged, not fixed** (honest disclosure, no guess-fix): `coverage.target_families_first_class`
declared `12`. Tried three candidate recomputations from the per-op `target_family_first_class`
field: distinct families where it's `True` = 9; distinct families where it's populated (`True`
or `False`) = 13; total ops where it's `True` = 15. None reproduces 12, and there is no sibling
scalar to cross-check against (unlike `wired_ops`). Left as-is rather than guess a fourth
formula.

Serialization preserved exactly: diff is 4 lines changed, 0 lines added/removed, same
`indent=2`/key order/BOM (surgical text edit, not a json.load+json.dump round-trip).

Verified `config/op_dag.json` (generated from per-op `handler.composed_of`/etc., not these
rollups) is byte-identical after `python tools/op_dag_generate.py` -- git flagged it "modified"
only due to LF-vs-CRLF normalization on checkout (`git diff` showed zero content lines);
reverted that spurious line-ending-only change, no regeneration/commit needed.

## Stale sibling records sweep (ticket point 4)

Scanned all 525 records for path-like fields resolving to nonexistent files, and specifically
for `*__w*`/`*_wave3*` worktree-suffix patterns (this lane's own worktree is named
`autocad-sdk-router__cb_irmap`, so a leftover reference to some OTHER pruned lane worktree would
look similar). Two rounds:

1. A broad regex flagged 696 "missing path" + 141 "worktree pattern" hits -- almost entirely
   false positives from an overly loose pattern: `#anchor` fragments on `evidence_refs` entries
   (e.g. `config/cad_job_operation_aliases.json#inspect.database.summary`) were being checked
   for existence WITH the fragment attached (always fails); and `_wave3` matched ordinary,
   real, currently-existing test filenames (`tests/unit/test_wave3_render_plot_registry_safety.py`
   et al.) and policy-status string values (`hard_blocked_after_wave3_reaudit`) that merely
   contain the substring "wave3" as a normal word, not a worktree directory fragment.
2. Tightened: stripped `#fragment` before existence checks, and restricted the worktree pattern
   to `autocad-sdk-router__<suffix>` / `[\\/]__w<suffix>[\\/]` / `_wave3[\\/]`-as-a-path-segment
   shapes. Result: **0 genuine worktree-suffix path hits**. The remaining 40 "missing path" hits
   are all `runs/<name>/*.json` evidence references -- `runs/` is gitignored
   (`git log --all -- runs/...` returns empty history for every one checked), so these are
   legitimate pointers to ephemeral, never-committed run-evidence directories, not staleness
   from a pruned worktree.

Conclusion: no unambiguous stale-worktree-path records to fix. Verified `tools/cadctl.py` (one
of the flagged "paths", actually a `module.py::Class.method` citation, not a filesystem path)
does exist, closing out that category too. Reporting the negative result rather than silently
skipping it.

## Tests

New file `tests/unit/test_ir_to_patch_mappings.py` (20 tests): create_blockref never
insert_block + it's a declared op; LWPOLYLINE unchanged; AcDb2dPolyline -> deep op;
AcDb3dPolyline -> polyline3d; unrecognized class for `kind=="polyline"` defers; both polyline
native ops are declared; block-def preamble emitted once per name (with/without content,
with/without a second INSERT of the same block); INSERT with no block_definitions source defers
honestly; an unsupported def_entity kind is deferred not dropped; every
`operations.v2.json` totals/coverage scalar reconciles against a live recomputation from the
records (not a hardcoded snapshot).

Updated `tests/unit/test_patch_ops_split.py`'s pinned pre-split oracle: removed the
`block_reference` fixture case from `test_every_original_kind_branch_byte_identical` (it was
pinning the `insert_block` bug as a "byte-identical to pre-split" invariant -- that invariant is
intentionally broken by this fix, documented inline with a dated comment; `_original_op_for`
itself is left untouched as the historical snapshot).

Registry content check: none of the operations.v2.json edits touched any individual operation
record (only rollup scalars), so `op_dag_generate.py`'s per-op-derived output is unaffected
(verified above).

### Results

- `pytest tests/unit`: **1093 passed, 0 failed, 0 skipped**.
- Baseline before this lane's new test file (verified via `git stash`): 1073 passed. +20 from
  the new file = 1093. Matches exactly.
- Note on the "canonical 1087 (passed+skipped)" figure from the task brief: this worktree's
  actual pre-existing baseline (at the commit this lane started from, before any of this lane's
  changes) measures 1073, not 1087 -- reporting the measured number rather than forcing a match
  to a brief that may predate other work landing on `cados/wave0-build`. No skips observed at
  any point (rtk's pytest summary reports skip/fail counts when nonzero; none appeared).

### Deliberately not run (optional, per ticket)

"Cheap live proof: single op_roundtrip_probe create_blockref run on staged copy of
tests/fixtures/native_sample.dwg" -- marked optional in the brief. Skipped: this session's
environment enforces routing CAD engine invocations through the `cad.*` MCP surface rather than
direct accoreconsole-invoking tooling, and standing up an equivalent MCP-mediated check (a full
IR extraction + block_definitions-bearing INSERT + staged patch/diff cycle) is disproportionate
to what the brief calls a "cheap" optional check. The unit suite already exercises the exact
changed code paths directly (20 targeted tests + full regression, 0 failures) and is the
required gate; disclosing the skip rather than silently omitting it or faking a run.

## Commits

1. `fix(cb2-irmap/#129b,#119): INSERT emits create_blockref, heavy 2D polyline keeps its legacy
   type` -- entities.py/blocks.py/ir_to_patch.py/test_patch_ops_split.py.
2. `fix(#119): recompute stale scalar rollups in operations.v2.json against the operations[]
   array` -- config/operations.v2.json only (4-line diff).
3. (this commit) new test file + build_log.md.

---
## Lane ca2-capgate (#129a + #130 + finding6)

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

---
## Lane cc2-cpp (#118 + #128)

# build_log.md -- lane cc2-cpp (branch `cados/cc-cpp`)

Native C++ work log for tickets #118 and #128. Referenced by an existing
inline comment in `families/m08g_handlers.inc` ("1002 ... and 1004 (binary
chunk) are excluded -- see build_log.md") that predates this file's creation
in this worktree; this file is now that reference.

## #128 -- VPORT record circle_sides UPDATE-path anomaly

**Symptom (as given):** `write.vport.create`'s upsert -- create persists
`circle_sides`, updating an existing record does not.

**Code reading (before any live probe):** `upsertVportRecord` /
`applyVportProperties` in `AriadneNativeJob.cpp` -- the UPDATE branch opens
`kForWrite` (not `kForRead`) and calls the exact same `applyVportProperties`
the CREATE branch calls, which calls `pRec->setCircleSides(...)`
unconditionally when `props.hasCircleSides`. No code-level asymmetry between
create and update was found by inspection -- the ticket's hypothesized root
cause ("update branch opens kForRead or skips setCircleSides") does not
match what the code does.

**Live reproduction** (`op_roundtrip_probe.probe_vport_mutation`, baseline
`circle_sides=8` -> change `circle_sides=16`, staged copy of
`tests/fixtures/native_sample.dwg`): reproduced. `pre_record.circle_sides=8`,
`post_record.circle_sides=8` (unchanged) after the update call reported
`errorstatus:0, updated:true`. `status=hollow`,
`reason="the requested change to ['circle_sides'] was not detected on
re-extraction (invisible data)"`.

**Control test** (same driver, `height` instead of `circle_sides`,
9 -> 20): `status=ok`, height persisted correctly. Rules out a
generically-broken update path -- only `circle_sides` is affected.

**In-process readback (temporary diagnostic, since removed):** added a debug
field to `write.vport.create`'s own result JSON that re-opens the
just-written record for read in the SAME accoreconsole session, before that
session's own subsequent `_QSAVE`. Result: `circle_sides_readback_debug: 16`
-- `setCircleSides()` DOES update the in-memory value correctly. The value is
lost somewhere between "in-memory, correct" and "the saved DWG file",
specifically only when `circle_sides` is the ONLY field an update call
touches.

**Combo test:** bundling `circle_sides` with `height` in the SAME update
call (`{"height": 20, "circle_sides": 16}`): both persisted correctly.
`status=ok`, `changed_fields=["circle_sides","height"]`.

**Conclusion:** a `circle_sides`-only update to an EXISTING
`AcDbViewportTableRecord` is not recognized as a real drawing modification
by AutoCAD's own save pipeline (measured behavior, not something this
codebase's C++ controls) -- the in-memory value is correct but the file
save silently keeps the old on-disk value. Any OTHER field change bundled
into the same update call causes the whole record (including the
already-correct in-memory `circle_sides`) to be recognized and saved.

**Fix:** in `upsertVportRecord`'s UPDATE branch, when `props.hasCircleSides`
is set, re-assert `pRec->setHeight(pRec->height())` immediately after
`applyVportProperties` -- a true no-op (re-sets height to its own current
value) that reliably forces AutoCAD to recognize the record as modified.
Scoped to the UPDATE branch only (CREATE was never broken); scoped to
`hasCircleSides` only (this ticket's field; other "newer" per-record toggles
-- `grid_enabled`/`snap_enabled`/`ucs_follow_mode`/`ucs_per_viewport` -- were
not reported broken and were not touched or investigated further here).

**Live re-verification (final binary):** `probe_vport_mutation` circle_sides
8->16 alone: `status=ok, changed_fields=["circle_sides"]`,
`post_record.circle_sides=16`. Verdict: **FIXED**.

## #118 -- xdata 1004 (binary chunk) read classification

**Code reading:** `resbufItemJson` (`AriadneNativeJob.cpp`) already
classified codes 310/1004 as `"value_kind":"binary"` (not "unhandled") --
not a misclassification in the sense of being lumped into the wrong bucket.
But it emitted ONLY `byte_count`, never the actual bytes -- unlike every
other supported group code, which always carries a `"value"`. That is the
real gap: the payload is genuinely dropped, just not misclassified.

**Write-side finding (unexpected):** the ticket assumed "the existing xdata
write op" already supports writing a 1004 item. It does not:
`modify.entity.xdata` (`families/m08g_handlers.inc`) explicitly rejects code
1004 at parse time (`"unsupported or reserved xdata group code 1004"`, by
design, pre-existing). Live-probed baseline (before any change):
`probe_entity_xdata_roundtrip` with a `{"code":1004,...}` item ->
`status=fail`, `actual_items=[]` (the write was refused, no exception, no
crash, original untouched).

**Read-side fix:** added `bytesToHexLower(buf, len)` and changed the
310/1004 branch in `resbufItemJson` to also emit
`"value": "<lowercase hex>"` alongside `byte_count`. Guards `buf==nullptr`
and `len<=0` (returns empty string). Verified correct in isolation (a
standalone Python transliteration of the identical nibble-splitting logic,
all-256-byte-value round trip, null/zero/negative-length edge cases --
`ALL PASS`), and live-verified NOT to regress ordinary string xdata
(`probe_entity_xdata_roundtrip` with a plain `{"code":1000,...}` item after
the fix: `status=ok`, diff empty) or the full-database graph walk used by
every other probe in this session (multiple `inspect.database.graph` runs
against the real fixture, no crash).

**Write-side attempt and retraction (important, do not repeat without new
information):** to get a REAL 1004-bearing entity for a genuine live
round-trip, `modify.entity.xdata` was extended to accept code 1004 (`value`
as a hex string, decoded via a new `hexToBytes`, built into the resbuf chain
via `acutBuildList(1004, ads_binary{...}, 0)` -- the same
by-value-struct-through-varargs shape already used for `ads_point` on codes
1010-1013). Rebuilt, deployed, live-probed:

- The WRITE call itself returned success (`"set":true,"errorstatus":0`).
- The VERY NEXT step (a completely separate accoreconsole process
  re-opening the saved staged file for `inspect.database.graph`) crashed:
  `Unhandled Access Violation Reading 0x0005 Exception at 61DA7F13h`,
  `engine_exit_code: -3`. `original_unchanged` stayed true throughout (the
  crash was on a STAGED copy; the original fixture was never touched).
- Isolation: the plain-fixture graph walk (no 1004 anywhere, e.g. the #128
  probes above, run with the SAME binary) never crashed -- ruling out a
  generic regression in the read-side hex change. The crash only appears
  once a REAL 1004 chunk written by this new code exists in the file, which
  means the WRITE side produced a malformed/corrupt resbuf (the ABI
  assumption that `ads_binary`-by-value flows through `acutBuildList`'s
  varargs the same way `ads_point` does was not actually verified anywhere
  and turned out to be unsafe in practice), not that the read side has a
  live bug.
- **Retracted.** All three write-side edits (`XdItem::bin` field, the 1004
  parse branch, the 1004 resbuf-build branch) and the now-unused
  `hexToBytes` helper were reverted. `modify.entity.xdata` is back to
  exactly its original behavior (1004 still excluded, matching the
  ORIGINAL pre-#118 code and comment). This is a deliberate, live-probed
  finding, not a fabricated pass -- write support for 1004 needs a properly
  verified manual `acutNewRb` + explicit-ownership construction (and
  confirmation of what `acutRelRb` actually does with `rbinary.buf`) before
  it is safe to ship; that is future work, out of this ticket's scope.

**Verdict:** #118 **FIXED** (read path: `byte_count`-only -> real hex
`value`, verified safe against regression and against a full live database
walk). A genuine end-to-end "AutoCAD-written real 1004 xdata reads back
correctly" proof was not obtained in this pass -- the safe way to construct
one needs write-side work this ticket explicitly did not ask for and that
this investigation showed is non-trivial to get right. Recorded here rather
than silently dropped (Rule 12 / no fake success).

## Regression baseline

`pytest tests/unit`: **1073 passed, 14 skipped** (1087 total) -- 0 failed,
both before and after these changes.

---
## Lane F (branch `cados/closeout-f`)

### F-a -- vport "*Active" managed-field policy

**Task**: `tools/full_roundtrip_capstone.py`'s table-record diff (Closeout
#130) reported the reserved `*Active` viewport's `center/height/width` as a
plain "modified" real diff, blanket-informational (never gate-wired either
way). Paul wanted a real, evidence-bounded policy instead of a guess.

**Evidence gathered first** (no field excluded without proof): read
`runs/capstone_composed_20260706/table_record_diffs.json` -- the vport row
for `*Active` shows `record_diff: ["center", "height", "width"]`, nothing
else. Confirmed that run's own `regen_records/patch.json` (221 applied ops,
`records_regen_summary.json`) contains zero vport-touching operations (no
"vport"/"viewport" substring anywhere in the patch) -- so nothing this run
issued could have written those fields; the drift is AutoCAD's own
open/regen/save rewrite of the reserved active-viewport record, matching
build_log.md's own #130 note ("plausibly *Active is a reserved,
AutoCAD-managed record...").

**Implementation** (`tools/full_roundtrip_capstone.py`):
- `VPORT_MANAGED_FIELDS = ("center", "height", "width")` -- exactly the 3
  fields the evidence run supports, nothing broader.
- `classify_vport_managed_drift(row)`: for the `name == "*Active"` vport
  row ONLY, splits `record_diff` into managed (moved to a new
  `managed_field_drift` list, `{field, expected, actual}`, annotated not
  swallowed) vs real (stays in `record_diff`). Any other vport record, or a
  non-managed field on `*Active`, is returned untouched -- still a real
  diff, still fails.
- `table_record_diff_reports` invokes this only for `cls["label"] ==
  "vport"`, then recomputes `zero_diff_count`/`diffs` from the
  (possibly-reclassified) rows -- mathematically identical to the old
  computation for all 6 other table classes (layer/dimstyle/linetype/
  textstyle/ucs/view), touched only to source `rows` uniformly.

**Verification**:
- New unit tests in `tests/unit/test_capstone_gate.py` (fake vport-labeled
  table class, no live CAD): managed-only drift on `*Active` -> 0 real
  diffs, drift annotated; non-managed field on `*Active` -> still fails;
  managed-named field (`center`) on a non-`*Active` record -> still fails.
  Plus 2 direct unit tests on `classify_vport_managed_drift` itself.
- Re-ran the record-diff stage against `runs/capstone_composed_20260706`'s
  own real `expected`/`actual` vport values (evidence run, not a live
  accoreconsole re-run -- see task note on acceptable scope): now
  `diffs=0`, `zero_diff_count=1`, `managed_field_drift` lists all 3 fields
  with their real old/new values, `record_diff` (post-policy) `== []`.
- `pytest tests/unit -q`: 1119 passed, 0 failed (was 1073 passed / 14
  skipped pre-lane baseline noted above in this same file -- delta is this
  lane's added tests plus whatever accrued on `cados/wave0-build` since).

### F-b -- CRASH-34 host_eligibility cross-check

**Task**: cross-check the 465-op live reachability sweep's 34 CRASH-classified
ops (`measure/reachable_matrix.jsonl`, `sweep_watchdog.ps1` -> live_probe,
totals reproduced exactly: RUNNABLE 242 / REACHABLE 161 /
RUNNABLE_BUT_DEGENERATE 28 / CRASH 34) against their own registry record
(`config/operations.v2.json`) to see whether the manual triage split
(com_activex 16 / live 5 / custom-class 6 / misc 7, "believed to be honestly
headless-impossible") holds up as an evidence-backed verdict, not just a
belief.

**Tool**: `tools/crash34_host_crosscheck.py` -- joins all 34 CRASH rows to
`config/operations.v2.json` by `id`, classifies each via
`classify_one()`:
- `expected_crash` if `policy.status_policy == "catalogued_not_runnable"`
  (the registry's own words: no live dispatcher wired yet) -- 27 of 34.
- `expected_crash` if the op's own `summary`/`notes` text already states
  Core Console cannot execute it -- exactly 1 (`live.jig.point_probe`:
  "Core Console can only report support status", quoted verbatim from the
  registry, already documented before this lane touched anything).
- `anomalous_crash` (registry_action=`open`) otherwise: `policy.
  status_policy == "implemented"` (a wired, runnable dispatcher claimed)
  with no textual host caveat -- 6 of 34.

**Key finding that changed the plan**: `engine_tier == "native_arx_only"`
alone does NOT predict CRASH -- 157 of 191 native_arx_only ops in this same
sweep came back RUNNABLE/REACHABLE (only 34/191 crashed), so
"host_eligibility excludes coreconsole" is not, by itself, a reliable
per-op signal; the real discriminator is each op's OWN
`policy.status_policy`.

Anomalous 6 (registry_action=`open`, NOT registry-edited):
- `extend.customclass.create`, `extend.customobject.create` -- registry
  says `implemented` with a WORKING fixture on file (`test_native/
  job_create_args.json`, `job_record_create.json`, referenced by 3+
  existing test files) yet crashed on BOTH the empty-arg AND valid-arg
  probe. No registry field predicts this; could be a live regression or an
  isolated-subprocess-harness difference from whatever harness those
  fixtures were last proven against -- flagged for owner triage, not
  guessed at.
- `live.overrule.enable/disable`, `live.reactor.enable/disable` -- registry
  says `implemented`, `execution_host_class: "arx_adapter"` (in-process,
  not textually attended-only like `live.jig.point_probe`). Plausible that
  overrule/reactor installation needs a persistent editor command-loop a
  one-shot native job doesn't have, but nothing in the registry says so --
  left OPEN rather than silently annotated.

No registry edit was made this lane (`registry_action_counts: {"none": 28,
"open": 6}`, `"annotated": 0`) -- none of the 6 anomalies met the
"unambiguous" bar the task set for a bot-authored annotation.

**Outputs**: `reports/crash34_host_eligibility_crosscheck.json` +
`.md` (34/34 joined, bucket counts reproduce 16/5/6/7 exactly, verdict
split 28 expected / 6 anomalous).

**Verification**: `tests/unit/test_crash34_crosscheck.py` -- synthetic
fixture tests for each `classify_one` branch + `build_report`/`main` glue
(tmp_path, no dependency on the real sweep ever changing shape), plus a
`TestRealCrash34Sweep` class run against the real, already-committed
`measure/reachable_matrix.jsonl` + `config/operations.v2.json`
(read-only) asserting join completeness (34/34), verdict/action enum
validity, and the 16/5/6/7 bucket totals.

`pytest tests/unit -q`: 1136 passed, 23 skipped, 0 failed (both F-a and
F-b changes included).

## Lane E (closeout follow-up wave) -- worktree `wt/laneE`, branch `cados/closeout-e`

### Research phase (before any code change)

**Fixture path correction:** the assigned fixture path in the task brief
(`fixtures/native_sample.dwg`) does not exist in the canonical repo -- only
`fixtures/blank_seed.dwg` lives there. The actual `native_sample.dwg` (sha256
`eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76`, matches
the brief) lives at `tests/fixtures/native_sample.dwg` (see
`tools/fixture_foundry.py:82`, `DEFAULT_SEED_DWG`). Copied into this worktree
at that corrected path; sha256 verified identical to the canonical copy
before any use.

**Locating the cc2 1004-write revert:** the exact commit hash named in the
task brief (`2916541`) does not resolve in this repo's `git log --all`. The
revert appears to have been squashed/folded rather than preserved as a
standalone commit. However, the FULL mechanism and evidence survive as an
already-committed code comment (not lost): `AriadneNativeJob.cpp:767-777`
(the `bytesToHexLower` doc comment, #118) and
`m08g_handlers.inc:1696-1710` (the `modify.entity.xdata` Pass-1 comment)
both describe it verbatim: a by-value `ads_binary` through `acutBuildList`'s
variadic 1004 slot built a resbuf that made `setXData` report success, but
the VERY NEXT accoreconsole process to reopen the saved staged file crashed
with an Access Violation (`engine_exit_code: -3`) inside AutoCAD's own DWG
reader, reproduced live via `op_roundtrip_probe.probe_entity_xdata_roundtrip`
and fully reverted. `modify.entity.xdata` currently rejects 1004 explicitly
(`"unsupported or reserved xdata group code 1004"`) -- confirmed by reading
the live code, not just the comment.

**Root-cause hypothesis (two independent candidates, both addressed):**
1. **ABI hazard.** `struct ads_binary { short clen; char* buf; }`
   (`C:\ObjectARX 2027\inc\adsdef.h:125-131`) is 16 bytes (2-byte `short` +
   6-byte pad + 8-byte pointer) on x64 -- too large for the MSVC x64 ABI to
   pass inline through a variadic slot; the calling convention silently
   passes a pointer-to-a-temporary-copy instead of the struct itself.
   `acutBuildList`'s internal `va_arg` consumption for a 1004 slot has no
   documented contract for this, unlike the fixed-size scalar codes
   (1000/1040/1070/point codes) already proven safe by the existing working
   code. This is consistent with the crash appearing only on REOPEN (a
   corrupted length/pointer serialized into the file) rather than
   immediately in the writer process.
2. **127-byte chunk limit.** `dbObject.h:270-276`
   (`AcDbObject::setBinaryData` doc comment) states ObjectARX's OWN
   convention: "The binary data is broken into 127-byte chunks for storage
   in the resbuf chain" -- i.e. a single DXF group-code-1004 resbuf node is
   only valid up to 127 bytes; this matches the well-known AutoLISP DXF
   reference limit for XDATA binary chunks. If cc2's probe payload exceeded
   127 bytes in one node, that alone would explain file corruption
   independent of the ABI issue.

**Design decision (scope-bounded, defensible):** implement 1004 WRITE via
manual `acutNewRb(1004)` (never `acutBuildList` for this code -- sidesteps
hazard #1 entirely) with an explicit-ownership byte buffer: WE allocate
(`new[]`) and copy the decoded hex bytes into `resval.rbinary.buf`/`clen`
ourselves. Since `AcDbEntity::setXData` takes `const resbuf*` (deep-copies
internally, does not take ownership -- confirmed from
`dbObject.h:267`), our buffer is definitely still ours to free after the
call. What is NOT documented anywhere in the SDK headers is whether
`acutRelRb` (which frees the whole chain, `dbeval.h:96`) also tries to free
`resval.rbinary.buf` on a 1004 node -- since that buffer was never allocated
by `acutBuildList`/`acutNewRb` in the first place (unlike its handling of
`rstring`), that is genuinely unverifiable from headers alone. Defensive
fix: neutralize every 1004 node (`buf=nullptr,clen=0`) AFTER `setXData()`
copies what it needs but BEFORE `acutRelRb(head)` walks the chain, then free
our own buffers explicitly ourselves. This makes the design correct
regardless of what `acutRelRb`'s internal 1004 handling actually is.
Payloads are capped at <=127 bytes per item (hazard #2) with a structured
rejection above that -- multi-chunk (>127B) concatenation is a NAMED,
OUT-OF-SCOPE gap (would require matching read-side changes to
`resbufItemJson`/`xdataBlocksJson` that this ticket does not touch, to avoid
regressing the already-shipped #118 read fix under this ticket's time/risk
budget).

**Correction:** the exact commit `2916541` DOES exist (my earlier
`git log --all | grep -i "916541"` search was a false negative, cause
unknown) -- it is the merge commit `merge(cc-cpp): #118 xdata 1004 payload
emission + #128 vport circle_sides persistence` (parent of `007713c`, this
lane's base). Its message independently confirms the mechanism above
verbatim (by-value `ads_binary` through `acutBuildList`, 0xC0000005 on
reopen, "HONEST REVERT", "Follow-up: manual acutNewRb explicit-ownership
construction (recorded in build_log)" -- i.e. this is that exact follow-up).

### E-a implementation, live test, and the actual result

Implemented exactly as designed above: `modify.entity.xdata` accepts code
1004 (hex-string `value`, <=127 bytes), built via manual `acutNewRb(1004)` +
an explicitly-allocated (`new[]`) byte buffer, with every 1004 node
neutralized (`buf=nullptr,clen=0`) after `setXData()` but before
`acutRelRb(head)`, and the real buffers freed ourselves via a new
`m08gReleaseOwnedXdataBinBuffers()` helper. Rebuilt clean (isolated
`build_iso`, 0 build errors), deployed to `prebuilt/2027/` (previous
baseline rotated into `_bak/`).

**Live test 1 (the mandatory acceptance test):** `op_roundtrip_probe.
probe_entity_xdata_roundtrip("ARIADNE_E_A_TEST", [{"code":1004,
"value":"48656c6c6f"}], "tests/fixtures/native_sample.dwg", ...)` (payload =
hex for ASCII "Hello", 5 bytes, well under the 127-byte cap):

- Step 2 (the write): `apply/op_00/stdout.txt` shows
  `"set":true,"errorstatus":0,"item_count":1` -- the write itself reports
  success, exactly like cc2's attempt did.
- Step 2's own post-inspect (a **SEPARATE accoreconsole process** re-opening
  the just-saved `staged_output.dwg` to run `inspect.database.graph`) --
  `post/stdout.txt`: **`Unhandled Access Violation Reading 0x0005 Exception
  at 6A798473h`**, `engine_output.status:"native_cad_job_failed"`,
  `result:null`. Probe result: `status:"partial", exit_code:2, reason:
  "post-inspect failed: native graph (post) produced no result object"`.
  **The crash reproduces identically with the "correct" manual-acutNewRb
  construction.** The ABI-hazard hypothesis (hazard #1 above) is therefore
  NOT the (sole) cause -- a construction path that entirely avoids
  `acutBuildList`'s variadic slot still crashes the same way.

**Control test (rule out a generic regression in this rebuild):** same
rebuilt binary, same fixture, code 1000 plain string instead of 1004 --
`probe_entity_xdata_roundtrip` returns `status:"ok", exit_code:0,
record_diff:[]`, both `original_unchanged_step{1,2}` true. The rebuild
itself is not broken; the crash is specific to 1004.

**Independent cross-check (LibreDWG sidecar, read-only diagnostic --
never used for production per the GPL-sidecar-only rule):** ran
`dwgread.exe -v2 -O JSON` (a completely independent, non-Autodesk DWG
parser) against the EXACT `staged_output.dwg` that crashed AutoCAD's own
reopen. **It succeeded** (`SUCCESS 0x0`) and its JSON shows the LINE
entity (handle `0x19190`) with `"eed":[{"size":7,"handle":[5,3,102820],
"code":4,"value":"48656C6C6F"}]` -- the exact 5 bytes we wrote, byte-for-
byte correct. **This proves the SAVED FILE IS NOT CORRUPT.** The crash is
not in what we wrote to disk; it is inside AutoCAD/ObjectARX 2027's OWN
`xData()`/EED-reconstruction code when it re-parses a real, non-empty 1004
chunk back into memory -- outside anything this resbuf-construction
discipline controls. (Also consistent with the crash address pattern:
`6A798473h` falls in a system-DLL load-address range, not inside our own
`.crx` module.)

**Precision test (isolate the exact trigger):** same everything, but
`{"code":1004,"value":""}` -- a **0-byte** binary chunk (`clen=0,
buf=nullptr`). This round-trips and re-reads **cleanly**: `status:"ok",
exit_code:0, record_diff:[]`, no crash on reopen. This precisely isolates
the trigger: it is not "any 1004 group code" that is fatal to AutoCAD's
own reopen -- it is specifically **non-empty binary content**. An empty
chunk is fine; real bytes are not.

**Verdict: E-a is BLOCKED**, not by any flaw in this ticket's
resbuf-construction/ownership design (which is demonstrably correct -- byte-
perfect per an independent reader) but by a crash inside AutoCAD 2027's own
internals when it reads back a real 1004 payload, regardless of how it was
written. This is a STRONGER, more precise finding than cc2's original
(which blamed the ABI hazard specifically) -- it now looks unfixable from
the write side entirely. Per the task's own stated acceptance criteria
("If ... reopen still crashes ... REVERT your write path to blocked ...
that is acceptable"), the write-enabling code was fully reverted: the 1004
parse branch, the `acutNewRb`/manual-buffer build branch, the now-orphaned
`hexToBytes()` (`AriadneNativeJob.cpp`) and `m08gReleaseOwnedXdataBinBuffers()`
(`m08g_handlers.inc`) helpers were all removed (no dead code left in the
tree), and `modify.entity.xdata`'s original "1004 excluded" behavior and
error message are restored, with an updated comment recording this entire
two-attempt history for whoever looks at this next.

**Post-revert verification:** rebuilt clean again, redeployed,
re-ran the SAME 1004 write probe: `status:"fail", exit_code:1,
actual_items:[]` (correctly rejected again, matching pre-E-a behavior),
`original_unchanged_step{1,2}` both true throughout every experiment in
this investigation -- no origin file was ever at risk.

### E-b: M08N-era native JSON writer control-char escaping fix

**Root cause, found by reading, not guessing:** `jsonEscape()`
(`AriadneNativeJob.cpp`) is the canonical UTF-8 JSON string-escape used by
every `njsonStr()` call in the whole native module (per its own doc
comment). It only escaped `"` and `\` -- any raw control byte (< 0x20) in a
string value, e.g. a literal `\n`, fell through unescaped.

**Confirmed against the actual failing evidence, not just in theory:**
ran `tools/cert_artifact_index.py` (read-only, scans `runs/` +
`attended_runs/`) against the canonical repo's run history (this worktree
has no `runs/` of its own to scan; `--scan-root` pointed at the canonical
repo's absolute path, `--out` written only into this worktree's own
`reports/`, never touching the canonical repo): **5851 artifacts scanned,
55 invalid** -- matches the ticket's claimed count exactly. Picked the named
example, `runs/native_batch_20260629_135844/results/245_input.get.point.json`
(369 bytes): `json.loads` fails with `Invalid control character at: line 1
column 128 (char 127)`; the raw bytes at that offset are
`":"input.get.point","result":{"prompt":"\nAriadne M08N input: ",...` -- a
literal `0x0A` inside the `"prompt"` string. Traced the source string to
`m08n_handlers.inc:498`: `m08nStringArg(job, "prompt", "\nAriadne M08N
input: ")` -- the DEFAULT prompt for every `input.get.*`/
`interact.jig.acquire` op.

**Fix:** `jsonEscape()` now emits `\b \f \n \r \t` as their standard short
escapes and every other byte < 0x20 as `\u00XX`; bytes >= 0x80 (all
UTF-8 continuation/lead bytes -- Korean/non-ASCII content) are untouched,
preserving the "lossless UTF-8" guarantee `njsonStr()`'s own doc comment
already promises.

**Live verification (real op, real crash-prone input, not a synthetic
unit test):** ran `input.get.point` headlessly via `cadctl.run_operation`
against `tests/fixtures/native_sample.dwg` on the rebuilt binary. Loaded the
raw result file
(`runs\dwg_truth_autocad_cad_job_20260706_140610\native_cad_job_result.json`,
370 bytes) as raw bytes: **zero literal `0x0A` bytes anywhere in the file**;
the on-disk bytes read `{"prompt":"\\nAriadne M08N input: ",...` (backslash-
n, two ASCII chars, properly escaped); `json.loads(raw.decode("utf-8"))`
(Python's strict default -- no `utf-8-sig` tolerance) parses without error;
the round-tripped value is `'\nAriadne M08N input: '`, byte-for-byte the
original semantic string. This is the exact op/input that produced one of
the 55 malformed artifacts pre-fix.

**Regression:** `write.entity.line` roundtrip probe (a previously-certified
op) on the same rebuilt binary: `status:"ok"`, diff `added:0, removed:0,
modified:0, unchanged:1` -- diff=0, no regression.

**Historical malformed artifacts:** the 55 pre-existing malformed result
JSONs under `runs/`/`attended_runs/` were left untouched (explicitly
optional per the task -- "evidence records"). Only the emitter was fixed.

## Regression gate (both E-a revert + E-b fix together)

`python -m pytest tests/unit -q`: **1114 passed, 23 skipped, 0 failed**
(exit code 0).

## Lane H (closeout wave, worktree `wt/laneH`, branch `cados/closeout-h`) --
## 1004 binary xdata WRITE, AutoLISP `entmod` alternate-path experiment

Experiment lane, NO production `src/` changes (Lane G owns C++ this wave).
Ordered to exhaust the remaining avenue on Lane E's `1004 xdata write` finding
before accepting permanence: Lane E proved the ObjectARX `setXData` path
(both `acutBuildList` and a manual `acutNewRb` construction) writes a
byte-perfect non-empty 1004 chunk that then crashes AutoCAD 2027's OWN reader
(0xC0000005) on the very next reopen. This lane asks the same question
through a completely different write path -- raw AutoLISP `entmod`/`entget`,
never touching ObjectARX's `setXData` at all -- via a new, isolated one-off
script: `tools/experiments/lane_h_1004_lisp_probe.ps1` (not wired into the
router, `cadctl`, or any production op).

**Mechanism (mirrors the router's own staging discipline, duplicated in
miniature rather than dot-sourcing the production router file, to keep this
experiment fully isolated from Lane G's concurrent C++ wave):** ASCII
staging dir under `staging/` per stage, forward-slash paths, `SECURELOAD 0`
/ `FILEDIA 0` / `CMDECHO 0` / `(vl-load-com)`, `accoreconsole.exe /i
<staged.dwg> /s <script.scr>` -- the exact same primitives as
`Resolve-AcadEnginePath`/`Invoke-AccoreScr` in `tools/autocad-router.ps1`.
Each of 3 stages uses its OWN staged copy of `tests/fixtures/native_sample.dwg`
(sha256 `eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76`,
verified unchanged before AND after the entire run -- `fixture_unchanged:
true` in every run's `summary.json`), so one stage's `entmod` attempt can
never contaminate another stage's saved file. Per stage: WRITE (`entmake` a
fresh LINE, `regapp`, build a `-3` xdata list via `entmod`, immediate
in-session `entget` readback, `_QSAVE`) in ONE `accoreconsole` process, then
REOPEN (a SEPARATE, fresh `accoreconsole` process, `handent`-by-handle +
`entget` readback, no save) in a second process -- mirrors Lane E's
write/reopen/crash-detection methodology exactly.

**Key unknown resolved empirically (AutoLISP has no dedicated binary
datatype -- docs disagree across releases on whether/how group 1004 is
LISP-constructible):** tested BOTH candidate representations against
AutoCAD 2027 directly, rather than trusting stale documentation.

- **Stage A (`stageA_string1004`):** 1004 value given as a plain AutoLISP
  STRING, `(cons 1004 "Hello")`. `entmod` (wrapped in `vl-catch-all-apply`,
  so the failure is caught cleanly, not a process crash) returned an error
  object; `vl-catch-all-error-message` (raw bytes decoded as `cp949` --
  AutoCAD's own console/message locale on this machine -- since the message
  is Korean): **`1004 그룹 내의 유효하지 않은 문자`** ("invalid character
  within group 1004"). In-session `entget` readback confirms NOTHING was
  attached to the entity (no `-3` block at all) -- the write never took
  effect even transiently.
- **Stage B (`stageB_listint1004`):** 1004 value given as a LIST OF
  INTEGERS, `(cons 1004 (list 72 101 108 108 111))` (== ASCII "Hello",
  byte-for-byte the same payload Lane E used) -- the AutoLISP Reference's
  historically-documented binary-chunk shape. `entmod` STILL rejected it,
  this time with a stronger, more categorical error:
  **`잘못된 DXF 그룹: (-3 ("ARIADNELANEH" (1000 . "stageB_listint1004_marker")
  (1004 72 101 108 108 111)))`** ("invalid DXF group: (-3 (...))") -- the
  entire xdata sublist is rejected as malformed, not just the 1004 item.
  Same as stage A: no `-3` block attached, nothing persisted even
  transiently.
- **Stage C (`stageC_control_1000`, no 1004 at all -- proves this script's
  OWN write/reopen/readback plumbing is sound, mirroring Lane E's control-
  test rigor):** `entmod` with only a `1000` string item:
  `ENTMOD_RESULT=SUCCESS`; in-session readback AND the separate-process
  REOPEN readback both show the correct
  `(-3 ("ARIADNELANEH" (1000 . "stageC_control_1000_marker")))` block intact,
  byte-for-byte. Both WRITE and REOPEN processes exited 0, no crash, no AV.
  Confirms the crash/rejection behavior in stages A/B is specific to group
  1004, not a bug in this experiment's write/save/reopen/readback mechanics.

**Verdict: Outcome B -- CONFIRMED non-constructible from AutoLISP.** Unlike
the ARX path (which "succeeds" at write time and only fails on reopen),
`entmod` refuses to build DXF group 1004 at ALL on this AutoCAD 2027 build,
in either candidate Lisp representation, rejecting the attempt immediately
and cleanly (a caught Lisp error, zero crash risk, zero partial/invisible
writes -- confirmed via immediate in-session readback showing no `-3` block
after either failed attempt). This is a cleaner failure mode than the ARX
path but the same practical conclusion: 1004 stays read-only. It also
resolves a specific ambiguity in the task brief: the suggested
`(1001 . "APPID")(1002 . "{")(1004 . <data>)(1002 . "}")` DXF-group-code
shape is the raw **DXF FILE encoding** of xdata (used when hand-parsing a
`.dxf` text stream); AutoLISP's own `entget`/`entmod` association-list
convention abstracts that away entirely -- the registered app name string
itself heads the `-3` sublist (no manual `1001`/`1002` brace markers needed
or accepted) -- confirmed by this experiment's own control stage (C) working
correctly without them.

**Secondary avenue (documented, not attempted per the task's own scope
note):** COM/ActiveX `SetXData` on the AutoCAD COM object model is
attended-only per the registry's `com_activex` class (requires a live,
user-owned AutoCAD session) -- not driven here. If a future session has
explicit attended access, that remains the one theoretically untested
avenue; given stage B's categorical "invalid DXF group" rejection surfaces
from AutoCAD's own DXF-group validator (not something obviously specific to
the LISP entry point), there is no strong reason to expect a different
result from COM, but this has not been empirically verified.

**Evidence:** `runs/lane_h_1004_lisp_probe_<stamp>/summary.json` (this
lane's own worktree-local, gitignored `runs/`) plus per-stage
`write_result.txt`/`reopen_result.txt`/`*_stdout.txt`/`*_stderr.txt` under
each stage's subdirectory. `fixture_sha256_before` == `fixture_sha256_after`
== `eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76` in
every run (original never touched, only ASCII-staged copies). All 6
`accoreconsole` processes (3 stages x write+reopen) exited 0 -- zero crashes
anywhere in this path, a materially different signature from Lane E's ARX
reopen-crash.

**Regression gate:** `python -m pytest tests/unit -q`: **1136 passed, 0
failed** (exit code 0) -- unchanged from the canonical rebuild baseline; no
production code was touched by this lane.

## Lane G

**Task:** root-cause `extend.customclass.create` / `extend.customobject.create`
CRASH regression flagged by F-b's `crash34_host_crosscheck.py` as
`anomalous_crash` (`policy.status_policy=="implemented"`, a working fixture on
file, yet CRASH on both empty-arg and valid-arg probes -- see build_log.md's
F-b entry above).

**Verdict: harness difference, not a real regression. Both native handlers
are correct and unmodified; no C++ fix, no rebuild.**

**Step 1 -- reproduce the CRASH live (sweep-style):** ran
`tools/probe_reachability.py --live --ops extend.customclass.create,extend.
customobject.create --dwg tests/fixtures/native_sample.dwg` against this
worktree's own `prebuilt/2027/` (canonical, unmodified since 688155d) --
mirrors the 2026-07-06 sweep's own isolated-subprocess invocation exactly.
Result: **both CRASH again**, confirming this is a real, deterministic,
reproducible outcome, not sweep flakiness. Root artifact:
`runs/laneG_repro/sweep_style_matrix.jsonl`; per-op detail under
`runs/laneG_repro/sweep_style_work/`. The actual failure signature, read from
the `valid/stdout.txt` of the underlying router invocation, is **not** a
native-module crash at all:
```
"status": "NO_ACTIVE_AUTOCAD",
"detail": "No running AutoCAD COM application was found for full_autocad native job mode."
```
`cadctl.run_operation` maps that router-level `NO_ACTIVE_AUTOCAD` envelope
(no `result`/`result_json` present) to `status:"partial"`, which
`probe_reachability.classify_probe_response` in turn buckets as `CRASH` --
the sweep's CRASH class conflates "native module crashed" with "router
couldn't even reach the native module." The .crx/.dbx dispatcher
(`createCustomEntity`/`createCustomObject`, `AriadneNativeJob.cpp`) was never
invoked.

**Root cause (traced in `tools/autocad-router.ps1`):** both ops' registry
record (`config/operations.v2.json`) has `write_level.default_write_mode ==
"live_edit"` (no `"read"` option). The `Action=='run'` dispatcher
(`autocad-router.ps1` around the `dwg_truth_autocad` branch) checks
`($HostMode -eq 'full_autocad' -or $effectiveWriteMode -eq 'live_edit')`
**before** it ever considers `Invoke-CadJobRoute` (the headless Core Console
`arxload` dbx+crx path that `Test-NativeP1CadJobOperation` would otherwise
select for these two ops). Because `effectiveWriteMode` resolves to
`live_edit` from the registry default, every call unconditionally takes the
`Invoke-FullAutoCadCadJob` branch, which does `[Runtime.InteropServices.
Marshal]::GetActiveObject('AutoCAD.Application')` -- i.e. it requires an
**already-open, interactive AutoCAD session reachable via COM**. Neither
`cadctl.run_operation` nor `probe_reachability.py`'s isolated subprocess ever
opens or attaches to one, so this branch always fails with
`NO_ACTIVE_AUTOCAD`, regardless of whether the native handler works.

This is not specific to these two ops. Cross-checked every `engine_tier==
"native_arx_only"` row in the real, already-committed
`measure/reachable_matrix.jsonl` (191 ops total) against its own
`write_level.default_write_mode`: **all 34 CRASH rows have
`default_write_mode=="live_edit"`; all 157 non-CRASH rows (RUNNABLE/
REACHABLE/RUNNABLE_BUT_DEGENERATE) have `default_write_mode=="read"`** -- a
100% clean split. The other 4 `anomalous_crash` rows from F-b's crosscheck
(`live.overrule.enable/disable`, `live.reactor.enable/disable`) show the
same `default_write_mode=="live_edit"` shape and almost certainly hit the
identical router branch -- flagged here as a strong lead for whoever owns
that triage, left untouched (out of this lane's assigned scope; no
registry/tool edit made for those 4).

`git log -S Invoke-FullAutoCadCadJob -- tools/autocad-router.ps1` shows this
branch has existed since `33b2932` (repo's very first tracked commit) -- this
is a standing dispatch gap, not something a later build wave broke.

**Step 2 -- bisect against the historically-proven invocation style:** the
"working fixture" evidence cited by the registry
(`test_native/job_create_args.json`, `job_record_create.json`) is not
exercised live by any current pytest test -- `tests/test_native_arx_dbx_
contract.py` / `tests/test_cad_job_control_plane.py` only assert the op_id
strings/schema shapes appear as text (static contract checks, no live
AutoCAD call). The actual historical proof mechanism is named directly in
`AriadneNativeJob.cpp`'s `ariadneNativeJobArgs()` comment: "this is what the
M07B attended harness uses to run custom ops (e.g. ... extend.customclass.
create) ... host_mode defaults to full_autocad (this command path is
attended)" -- i.e. a **dedicated, disposable full acad.exe** driven through
the `ARIADNE_NATIVE_JOB_ARGS` env-file channel
(`tools/attended_lane.py` + `tools/attended/run_attended_job.ps1`), not
`cadctl.run_operation`'s headless `-Intent dwg` surface at all.

Ran the exact same op_ids + exact same fixture args
(`{"center":{"x":10,"y":20,"z":0},"size":5}` / `{"key":"recordA",
"value":42}`, matching `test_native/job_create_args.json` /
`job_record_create.json` byte-for-byte) through `attended_lane.
run_attended_native_job()` against this worktree's own `router_home`
(dedicated acad.exe launch, never attaches to a pre-existing session --
distinct from `Invoke-FullAutoCadCadJob`'s COM-attach requirement). Both
**PASS**:
```
extend.customclass.create  -> result: {"created": true, "errorstatus": 0, "center": [10,20,0], "size": 5, "ariadne_probes_after": 1}
extend.customobject.create -> result: {"created": true, "errorstatus": 0, "key": "recordA", "value": 42, "ariadne_records_after": 1}
```
Evidence: `runs/laneG_repro/attended/customclass_run/attended_job_result.json`,
`runs/laneG_repro/attended/customobject_run/attended_job_result.json`.
Security scoping (`SECURELOAD`/`TRUSTEDPATHS`) was set then restored
(`"restored": true` in both envelopes). Driver script used:
`laneg_attended_repro.py` (scratchpad, not committed -- a thin, evidence-
inlined caller of the repo's own `attended_lane.run_attended_native_job`,
no ad-hoc CAD parsing).

**Bisect result: (a) sweep-style (headless, `-Intent dwg`) CRASHES; (b)
attended-lane style (dedicated full acad.exe, `ARIADNE_NATIVE_JOB_ARGS`)
PASSES**, with byte-identical op+args and this worktree's own unmodified
`prebuilt/2027` binaries in both cases -- textbook harness difference. The
differing condition is exactly the router-dispatch gap above: `live_edit`
write mode is being used by `autocad-router.ps1` as an "attended-COM-only"
signal, when the registry actually means it as a *persistence* signal
(`dwg_persisted:true`, no `read` mode exists for these ops) that
`Invoke-CadJobRoute`'s own headless Core-Console path already knows how to
honor (it appends `_QSAVE` for `write_copy`/`write_original`/`live_edit`
alike) -- had the dispatcher reached that branch instead, this likely would
have passed headlessly too, but that is a broader router-dispatch fix
outside this lane's 2-op scope and is called out here, not silently patched.

**Step 3 -- truth surfaces updated (measured facts only, no guessing):**
- `config/operations.v2.json`: appended a caveat sentence to both ops'
  `summary` and `notes` (the field `crash34_host_crosscheck.py` already
  reads) documenting the exact mechanism above, plus an `evidence_refs` entry
  pointing at the two `attended_job_result.json` proof artifacts.
- `tools/crash34_host_crosscheck.py`: added a second, generic, verbatim
  substring caveat check (`_ATTENDED_ONLY_CAVEAT = "requires an already-open
  autocad session"`, mirrors the existing `_CORE_CONSOLE_CAVEAT` pattern
  exactly) so `classify_one()` now recognizes this documented case as
  `expected_crash`/`registry_action:"none"` instead of `anomalous_crash`/
  `"open"`. Additive only -- every existing branch/test is untouched; the 4
  `live.overrule`/`live.reactor` rows are deliberately left `anomalous_crash`/
  `"open"` (no caveat text added to their registry entries -- not this
  lane's scope to assert on their behalf).
- Regenerated `reports/crash34_host_eligibility_crosscheck.{json,md}`:
  `verdict_counts` moved from `{"expected_crash":28,"anomalous_crash":6}` to
  `{"expected_crash":30,"anomalous_crash":4}`; `bucket_counts` unchanged
  (`16/5/6/7`, as expected -- bucketing is presentational, independent of
  verdict).

**Verification:** `python -m pytest tests/unit -q` -- **1136 passed, 0
failed** (includes the pre-existing `tests/unit/test_crash34_crosscheck.py`,
all 17 still green; its synthetic
`test_classify_one_implemented_with_working_fixture_still_anomalous` test
constructs its own op dict with no caveat text, so it is unaffected by the
real registry's new caveat sentence). No C++ touched; no rebuild performed
(this worktree's `prebuilt/2027` binaries are the same canonical build from
688155d used by every other lane this wave).

## Lane I

**Task:** fix the router `live_edit` dispatch defect that Lane G root-caused
(the `Action=='run'` `dwg_truth_autocad` branch treated
`effectiveWriteMode -eq 'live_edit'` as an attended-COM-only signal, routing
every `live_edit`-default job-based op to `Invoke-FullAutoCadCadJob` ->
`GetActiveObject("AutoCAD.Application")` -> `NO_ACTIVE_AUTOCAD` under any
headless probe, before `Invoke-CadJobRoute`'s own headless Core Console path
was ever considered), then re-probe the 34 CRASH rows against the fix.

**Fix (`tools/autocad-router.ps1`):** added `Get-CadOperationExecutionHostClassMap`
(cached, mtime/size-invalidated read of `config/operations.v2.json`, same
pattern as the pre-existing `Get-NativeJobOpSet`) and
`Test-CadJobRequiresAttendedHost`, which resolves the job's operation id
(from `-Operation`, or `Get-CadJobOperation` on `-JobPath` when `-Operation`
is absent) and returns true ONLY when the registry's
`handler.execution_host_class == "full_autocad"` -- i.e. the op has no
`arx_adapter`/`coreconsole`/`dbx` alternative and can only run inside an
already-open, interactive AutoCAD session. The `Action=='run'`
`dwg_truth_autocad` job-based dispatch now reads:

```
if (($HostMode -eq 'full_autocad' -or $jobRequiresAttendedHost) -and $hasJob) {
  $exec = Invoke-FullAutoCadCadJob -RunOut $runOut
}
elseif ($hasJob) {
  $exec = Invoke-CadJobRoute -Capabilities $capabilities
}
elseif (...) { ... }  # unchanged: non-job raw -Script branch (Invoke-FullAutoCadScript)
```

Unknown/unregistered op ids default to headless (`Test-CadJobRequiresAttendedHost`
returns false when the op is absent from the registry map) --
`Invoke-CadJobRoute`'s own NETLOAD fallback already handled arbitrary op ids,
so this is no worse off than before the fix. The non-job raw `-Script`
branch (`Invoke-FullAutoCadScript`, arbitrary AutoLISP against the live
active document) is untouched: there is no registry-backed op id to check
eligibility against for an arbitrary script, so it correctly stays gated on
`-HostMode full_autocad` / `write_mode=='live_edit'` as before. Safety
invariants preserved: `Invoke-CadJobRoute` stages its own copy and only that
copy is `_QSAVE`d (never the original); `write_original` still refused from
the agent surface; no fake availability.

`python -m pytest tests/unit -q`: 1136 passed, 0 failed (no regression from
the dispatch change alone).

**Cross-registry landmine found while wiring the fix (flagged, not
independently investigated further -- out of this lane's assigned scope):**
many of these 34 ops have a TOP-LEVEL `"status": "implemented"` (the field
`cadctl.Cad.run_operation`'s allow-list gate actually reads) but a STALE
nested `policy.status_policy == "catalogued_not_runnable"` (a legacy
sub-field `tools/crash34_host_crosscheck.py`'s old heuristic keyed off
instead). The two fields had drifted out of sync; this is why 27 of the 33
ops resolved below had been mis-classified `expected_crash` by the old
crosscheck logic for the wrong reason (it believed no dispatcher was wired,
when one was -- see `reports/lane_i_router_fix_resolution.json` and the
crosscheck's new resolution-first check, which reads the measured live
re-probe result instead of trusting the stale sub-field).

**Re-probe (Task 2), sweep-style, this worktree's own fixed router + own
`prebuilt/2027` (unmodified since 688155d):**

1. All 34 previously-CRASH ops (`tools/probe_reachability.py --live --ops
   <34 ids> --dwg tests/fixtures/native_sample.dwg`, artifacts under
   `runs/laneI_reprobe/` -- gitignored, not committed; the measured result is
   captured in the committed `reports/lane_i_router_fix_resolution.json`):
   **33 of 34 flipped away from CRASH** -- 28 RUNNABLE (`status:"ok"`, real
   native results, e.g. `extend.customclass.create` ->
   `{"created":true,"errorstatus":0,...}`, `live.overrule.enable` ->
   `{"registered":true,"created":true,"name":"AriadneObjectOverrule",...}`),
   3 REACHABLE (native module reached, clean `MISSING_ARG`/`MISSING_HANDLE`
   validation errors on the empty-arg fixture -- e.g.
   `define.constraint.autoConstrain`, `transform.database.wblock_clone`), 2
   RUNNABLE_BUT_DEGENERATE (`live.overrule.enable`, `live.reactor.enable` --
   genuine `status:"ok"` successes; "degenerate" here is
   `probe_reachability.py`'s own presentational bucket for "no valid-arg
   fixture provided," unrelated to the router fix). **1 of 34 stayed CRASH**:
   `live.jig.point_probe` -- its registry `handler.execution_host_class` is
   genuinely `"full_autocad"` (no headless alternative; it drives an
   `AcEdJig` prompt via `SendCommand` on a live document), and it still
   fails with the same honest `NO_ACTIVE_AUTOCAD` / "No running AutoCAD COM
   application was found for full_autocad native job mode" envelope as
   before -- correctly routed to the attended branch, correctly refusing to
   fake success under an isolated probe with no open AutoCAD session.
2. Regression subset -- 10 previously-RUNNABLE/REACHABLE ops spanning `read`
   (`acdb.database.create`, `automate.com.bridge_objectid`,
   `automate.com.entity_helpers`, `automate.com.hold_objectref`,
   `automate.com.lock_document`) and `write_copy`-allowed (`apply.patch`,
   `automate.property.set`, `compute.solid3d.interference`,
   `define.assocaction.addDependency`, `define.assocaction.valueParam`):
   **all 10 classify identically before vs after the fix** -- no regression.
3. Fixture integrity: `tests/fixtures/native_sample.dwg` sha256
   `eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76`
   verified before the fix commit and after both probe batches (crash34
   re-probe + regression subset) -- unchanged throughout.

**Truth surfaces (Task 3):**
- New committed artifact `reports/lane_i_router_fix_resolution.json`: the
  measured before/after (`old_class`/`new_class`/`resolved`) for all 34
  op_ids, plus fix commit/file and reprobe method/fixture sha -- the
  evidentiary record for everything below (raw per-op probe artifacts live
  under gitignored `runs/laneI_reprobe/` and are not committed).
- `tools/crash34_host_crosscheck.py`: added `load_resolution_map()` +
  `VERDICT_RESOLVED = "resolved_by_router_fix"` /
  `ACTION_RESOLVED = "resolved_by_fix"`. `classify_one()` now takes an
  optional `resolution` map argument (default `None`, so the existing
  synthetic unit tests that call it directly with 2 positional args are
  byte-for-byte unaffected -- same pattern Lane G's own caveat-text change
  used) and checks it FIRST, ahead of the `catalogued_not_runnable`/caveat-
  text/anomalous heuristics: a resolved op_id short-circuits straight to
  `resolved_by_router_fix` with the fix commit/file and new_class inlined
  into `evidence`. `build_report()` / `main()` gained a third
  `resolution_path` parameter / `--resolution` flag (default
  `reports/lane_i_router_fix_resolution.json`; a missing file soft-fails to
  `{}`, reproducing pre-Lane-I behavior exactly).
- Regenerated `reports/crash34_host_eligibility_crosscheck.{json,md}`:
  `verdict_counts` moved from `{"expected_crash":30,"anomalous_crash":4}` to
  `{"resolved_by_router_fix":33,"expected_crash":1}` -- zero `anomalous_crash`
  remaining; `bucket_counts` unchanged (`16/5/6/7`, presentational,
  independent of verdict); `live.jig.point_probe` is the sole
  `expected_crash` row.
- `config/operations.v2.json`: revised the stale caveat sentence Lane G
  added to `extend.customclass.create` / `extend.customobject.create`
  (`summary` + `notes`, both fields, both ops -- it previously asserted these
  ops "always" route to the attended COM branch, which is no longer true)
  to state the router bug is fixed and the op is now live-re-probed
  RUNNABLE headlessly; appended an `evidence_refs` entry pointing at
  `reports/lane_i_router_fix_resolution.json` for both ops. Regenerating
  `config/op_dag.json` afterward (`python tools/op_dag_generate.py`) picked
  up the new evidence_refs path token as an additional `target_files` entry
  for both ops (2-line diff, `tools/op_dag_generate.py`'s own deterministic
  parse of registry evidence_refs -- not a manual edit).
- Added 7 new unit tests to `tests/unit/test_crash34_crosscheck.py`
  (resolution-first classify_one behavior, resolution-map-present-but-not-
  resolved fallthrough, `load_resolution_map` missing-file + metadata-inline
  behavior, and a new `TestRealCrash34SweepAfterLaneIFix` class asserting the
  real artifact's new verdict counts / the single remaining expected_crash /
  fix-commit-in-evidence for all 33 resolved rows).

**Verification:** `python -m pytest tests/unit -q` -- **1143 passed, 0
failed** (1136 baseline + 7 new; includes the full, now-24-test
`test_crash34_crosscheck.py`, all green). No C++ touched; no rebuild
performed (same canonical `prebuilt/2027` from 688155d as every other lane
this wave, confirmed unchanged by this lane).

## Attended Wave (worktree `wt/laneAT`, branch `cados/attended-wave`)

Assigned 5 priority-ordered missions against a claimed already-open attended AutoCAD
session. **Session-existence check FIRST** (before touching anything): `Get-Process acad`
+ `tasklist` both showed **zero** acad.exe running -- the brief's premise was false at
task start. Flagged to team-lead, did registry-only analysis while waiting, and a real
session (PID 8180, empty, `Documents.Count=0`, "시작"/Start-tab title) appeared mid-task,
presumably Paul opening it in response. All live work below used that real session (COM
attach, opening ONLY our own staged copies as additional documents, never touching/
closing anything else) or a genuinely separate dedicated `acad.exe` launch (verified safe
to coexist -- see Mission 3).

### Mission 1 (com_activex, 7 blocked) + Mission 4 (brep_solids, 4 blocked) + Mission 5
### (best-effort remnants, 6 ops): registry-only verdict, 0/17 promotable, by design

Pulled every one of the 17 named blocked/gated ops (`config/operations.v2.json`) before
touching anything live, to avoid burning session time on dead ends. All 17 fall into
exactly 3 buckets, none of which "attended access" can close:

- **`SAFETY_FORBIDDEN` (14 ops)** -- deliberate design decisions, not capability gaps:
  6 `automate.com.*` (raw COM/IDispatch handle exposure), 3 `edit.subentity.*`
  (subentity-path mutation, no validated staged-authoring schema), `plot.config.settings`,
  `command.menu.invoke`, `editor.toolpalette.tool_execute`, `command.queue.post`
  (raw command-string dispatch). Attempting to "prove and promote" any of these would
  defeat an intentional guardrail, not close a real gap -- refused on principle, not
  attempted even with live access.
- **`HOST_UNAVAILABLE` + `dispatcher_symbol: null` (3 ops)** -- `embed.ole.frame`,
  `ui.subentity.highlight`, `plot.engine.run`. No ARX handler code exists for any of
  these at all (would need new C++ authored + built + relinked -- out of scope for
  "drive the documented COM call", which is an execution task, not a build ticket).
- **`live.apply_patch` (1 op)** -- blocked pending "explicit write_original approval",
  an owner-level gate (`dev-change-control`) a lane cannot grant itself.

**Net: 0/17 promoted, all correctly stay blocked.** No registry edit made for any of
these 17 (nothing to promote, nothing incorrectly blocked).

### Bonus find in the com_activex family: `automate.property.set` (M08M-T01) --
### real handler, write path broken, NOT promoted

Not one of the 7 blocked ops (`status: implemented`, real `m08mDispatch` handler,
`src/Ariadne.AcadNative/families/m08m_handlers.inc:1193`) but stuck at
`policy.status_policy: catalogued_not_runnable` pending a live native-job smoke test.
`host_eligibility` includes `coreconsole`/`dbx` (no attended session actually required) --
ran it headless against a staged copy of `tests/fixtures/native_sample.dwg` (sha256
verified `eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76` before and
after every experiment in this wave).

- **Read path: real and correct.** `found`/`read_only`/`before` all verified against 3
  distinct properties across 2 entity classes, including real Korean MTEXT content
  (`Contents` on handle `1199B`: `before:"전실"`, matches the golden fixture verbatim).
- **Lookup gap (own-class only):** `m08mFindClassProperty(pObj->isA(), ...)` walks only
  the concrete instance's OWN class member collection, never inherited base-class members
  -- `Layer`/`LayerId` (declared on `AcDbEntity`) are unreachable from any concrete entity
  subtype instance (`AcDbLine`, `AcDbMText`, ...) via this op, confirmed via
  `inspect.property.metadata` (`class=AcDbLine` -> 5 own members only: Normal/Thickness/
  Angle/Length/Delta; `class=AcDbEntity` -> 17 members including LayerId, but that class
  is never the runtime type of any real entity).
- **Write path: broken for every type tried.** `Thickness` (double, found, not read-only)
  -> `set_status:3` (`eInvalidInput`), value unchanged. `Contents` (AcString, found, not
  read-only) -> same `eInvalidInput`, value unchanged. `Text` (read-only) correctly
  refused with `set_status:2` (`eNotApplicable`) -- the read-only guard itself works. The
  handler always boxes the new value as a generic `AcRxValue(const ACHAR*)`
  (`m08m_handlers.inc:1233-1234`) regardless of the property's actual declared type; this
  looks like a real marshalling defect (plain string boxing doesn't satisfy
  `AcRxProperty::setValue`'s type check for non-string properties, and apparently not even
  for the AcString-typed ones tried), not an attended-vs-headless issue.
- **Verdict: NOT promoted.** `found:true` is not a working set (this wave's own
  `dev-validation-and-qa` convention: "a catalogued_not_runnable op looks green" is
  exactly this trap). `policy.status_policy` left at `catalogued_not_runnable`,
  `operations.v2.json` untouched for this op. This is diagnostic evidence for whoever
  owns M08M next, not a fix -- fixing the C++ marshalling is out of this lane's scope.
- Evidence: `runs/attended_wave_aps_smoke/` (staging + pre-inspect) and 4 ad-hoc
  `apply*`/`meta_*` subdirs under the same tree (headless native-job runs, each with its
  own `native_cad_job_result.json`).

### Mission 2: 1004 binary xdata via COM `SetXData` -- the 4th and last avenue, EXHAUSTED

Per Lane E (ARX `setXData`: byte-perfect write, AutoCAD 2027's own reader crashes
0xC0000005 on reopen) and Lane H (AutoLISP `entmod`: categorically REJECTS constructing
group 1004 outright, both string and list-of-ints representations, before any write),
COM `SetXData` was the one remaining untested avenue. Drove it live via `pywin32`
(`win32com.client`) attached to the real attended session (`GetActiveObject`), opening
ONLY our own staged copy of the fixture as an additional document (`Documents.Open`,
never touching the pre-existing empty document state), resolving the target entity by
handle (`Document.HandleToObject`).

- **Marshalling, empirically resolved:** a plain Python `bytes` object for the 1004 slot
  fails immediately (`SetXData` COM error `잘못된 인수 type` -- "invalid argument type").
  The construction that actually works is an explicit nested `VARIANT` per the mission's
  own hint ("vbBinary-typed 1004 element"): `DataType` as `VT_ARRAY|VT_I2` (`[1001,
  1004]`), `Data` as `VT_ARRAY|VT_VARIANT` whose 1004 slot is itself a
  `VT_ARRAY|VT_UI1` byte-array `VARIANT` (`win32com.client.VARIANT(pythoncom.VT_ARRAY |
  pythoncom.VT_UI1, list(payload_bytes))`), payload = `bytes([72,101,108,108,111])`
  (ASCII "Hello", same payload Lane E/H used, for direct comparability).
- **In-session: SUCCEEDS.** `SetXData` raised no exception; immediate `GetXData("APPNAME")`
  readback in the SAME session showed `types:[1001,1004]` and the byte payload present.
  `doc.Save()` (staged copy only) succeeded. `RegisteredApplications.Add` confirmed the
  APPID registered. Original fixture sha256 unchanged throughout
  (`eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76`, before==after).
- **Independent cross-check (LibreDWG sidecar, read-only diagnostic, GPL-sidecar-only
  per repo rule):** `dwgread.exe -v2 -O JSON` on the just-saved staged file succeeded
  (`SUCCESS 0x0`) and shows, on the target LINE (`"handle":[0,3,71989]` = hex `0x11935`,
  our exact target), `"eed":[{"size":7,"handle":[5,3,102800],"code":4,
  "value":"48656C6C6F"}]` -- byte-perfect "Hello", the RegApp entry
  (`"name":"ARIADNE_COM_1004_TEST"`) present and correctly wired. **The saved file is not
  corrupt; COM wrote exactly what was asked, same as the ARX path did.**
- **Reopen in a SEPARATE, fresh `accoreconsole` process (headless
  `inspect.entity.get_xdata`, via `run_job.run_router_cad_job` -- never the same process
  that wrote it): CRASHES.** `engine_output.status:"native_cad_job_failed"`,
  `exit_code:-3`, `"Unhandled Access Violation Reading 0x0005 Exception at 41D2835h"` --
  the SAME class of fault (0xC0000005-family AV, "Reading 0x0005") Lane E found via ARX,
  at a different address but the same signature (system-DLL load-address range, not our
  own module).
- **Verdict: outcome is the mission's own named "write-succeeds-but-reopen-crashes" =
  final confirmation of an AutoCAD-2027-internal fault**, now triple-independently
  confirmed across all 3 possible write avenues (AutoLISP entmod: rejected outright; ARX
  setXData: writes clean, crashes reopen; COM SetXData: writes clean, crashes reopen).
  1004 binary xdata WRITE stays permanently blocked/read-only in this CAD OS -- not an
  implementation gap on any of the 3 avenues, a genuine AutoCAD-internal reader defect.
  No further avenue exists to test. No registry change (nothing was ever "implemented"
  to begin with for 1004 write; `modify.entity.xdata` already correctly rejects it).
- Evidence: `runs/attended_wave_m2_com_1004/` (`staged_m2.dwg`, `mission2_setxdata_result.json`,
  `staged_m2_libredwg.json` cross-check) + the reopen-crash's own
  `runs/dwg_truth_autocad_cad_job_20260706_154527/` router run dir.

### Mission 3: hatch write attended cert -- PROMOTED, diff=0

`write.entity.hatch` (owner_ticket M08H-T02) had a real handler (`m08hDispatch`,
`AcDbHatch::setPattern/appendLoop/setAssociative/setGradient/setHatchStyle +
evaluateHatch()`) but `policy.status_policy: catalogued_not_runnable` pending an
attended smoke test (the hatch AREA ENGINE is demand-loaded and not available in
headless accoreconsole even though `host_eligibility` optimistically lists it --
`tools/attended_lane.py`'s own docstring documents this exact gap).

- **Environment note (real, worth recording):** launching a SECOND, genuinely separate
  dedicated `acad.exe` while the real session (PID 8180) was open works completely fine
  -- verified with a throwaway diagnostic launch (new PID, opened its own doc, fully
  responsive, no license/single-instance conflict, screenshot confirms a clean working
  session). The two first attempts at running `attended_lane.py --mode full-cert` via
  its CLI (240s then 480s timeout, `job_out_present:false`, no `security_before.txt`
  ever written) were **not** an AutoCAD problem: I had passed a *relative* `--out-dir`
  to the CLI, which flows through unchanged into `run_attended_job.ps1`'s `-RunDir` and
  into the generated `.scr`'s `(open "runs/.../security_before.txt" "w")` call -- a
  relative path that resolves against the LAUNCHED acad.exe's own working directory, not
  the caller's, and fails silently in AutoLISP (`open` returns nil, the very next
  `write-line` on a nil file handle halts the rest of the script) before ever reaching
  `arxload`. Confirmed by reproducing the exact same script content with all-absolute
  paths in a standalone diagnostic (wrote `security_before.txt` within 10s, no hang) and
  then re-running the real CLI with an absolute `--out-dir` (worked end-to-end). The
  canonical entry point (`tests/unit/test_attended_lane.py::test_attended_hatch_full_cert_live`,
  which uses pytest's `tmp_path` -- always absolute) was never at risk; this was a
  mistake in my own ad-hoc CLI invocation, not a latent bug in the shipped harness or its
  own test, but worth noting for the next person who invokes the CLI by hand with a
  relative path.
- **Live run (`runs/attended_wave_m3_hatch_v2/`):** real dedicated `acad.exe`, staged
  copy of the golden fixture, `write.entity.hatch` with a 4-vertex square
  (0,0)-(100,0)-(100,100)-(0,100). Result: `created:true, class:AcDbHatch,
  pattern:SOLID, loop_vertices:4, handle:19190, modelspace_entities_after:21748`
  (21747+1, a genuinely new persisted entity). Security scoping restored
  (`secureload`/`trustedpaths` before==after). `original_unchanged:true`.
- **Ground-truth builder fix (`tools/attended_lane.py::expect_hatch`):** the FIRST
  roundtrip attempt reported `status:fail` (`modified:1`) even though the write was
  visibly correct -- `cad_op_gate.check_roundtrip`'s geometry-basis diff flagged
  `normal/elevation/pattern_angle/pattern_scale/hatch_style/loop_count/pattern_type/
  pattern_double/is_solid_fill/is_associative/is_gradient` and the loop's `closed` key as
  "changed", because `expect_hatch()`'s prior minimal ground truth simply didn't declare
  them -- an incomplete expected-value builder, not a write defect (every one of those
  fields' actual values exactly matches what a correctly-created SOLID/non-associative/
  non-gradient hatch should have). Added the missing fields (all constants, matching
  `AcDbHatch`'s own defaults for this handler's fixed SOLID/non-associative/non-gradient
  construction) plus `"closed": true` on the loop. Re-verified offline against the SAME
  live run's `pre_ir`/`post_ir` first (`cad_op_gate.check_roundtrip` -> `status:ok,
  exit_code:0, diff added:0 removed:0 modified:0 unchanged:1`), then via the real,
  tracked, `CADOS_LIVE=1`-gated pytest entry point itself:
  `pytest tests/unit/test_attended_lane.py -k hatch` -> **4 passed** including
  `test_attended_hatch_full_cert_live` (85s, fresh live attended run, independent of the
  CLI run above). Existing `expect_hatch`-consuming unit tests (`test_expect_hatch_*`,
  `test_attended_roundtrip_geometry_{match,mismatch}_*`) all still pass unmodified --
  additive-only fields, and the roundtrip tests derive `actual` FROM `expected` or from a
  deliberately-wrong fixture, so they were never coupled to the old minimal shape.
- **Registry promotion (`config/operations.v2.json`):** `write.entity.hatch`'s
  `policy.status_policy` flipped `catalogued_not_runnable` -> `implemented`,
  `runtime_behavior` removed (stale once promoted, mirrors `promote_op.py::_flip_axis_a`'s
  convention even though that tool's own scope is patch_op/WRITE_OP_MAP wiring and
  doesn't cover this M08M/M08H-style op family), evidence_refs' `deferred_attended`
  tag replaced with the real `attended_live_verified` run + pytest reference, stale
  `notes` (which claimed "has no CAD OS router handler yet" -- false, has since M08H)
  replaced with an accurate one, `tests` list extended with the live pytest test.
  `config/op_dag.json` regenerated (`tools/op_dag_generate.py`) to stay in sync (a
  derived artifact `test_op_dag_generate.py` asserts freshness against the registry).
- **Regression gate:** `python -m pytest tests/unit -q` -> **1136 passed, 0 failed, 23
  skipped** (unchanged from the canonical baseline; the op_dag regen was required and
  applied in the same commit).

### Fixture integrity (all missions)

`tests/fixtures/native_sample.dwg` sha256 `eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76`
verified before this wave's first use and re-verified after every single live/attended
run across all 4 missions above -- unchanged throughout. No original file was ever
opened directly; every attended/COM operation ran against a fresh staged copy, and every
document this lane opened in the live session was closed by this lane.

## Lane W5-TMPL

**Task:** design + build a GOVERNED middle path for the raw-command-dispatch
family blocked ops (`command.invoke.*`, `doc.sendstring`, `command.queue.post`,
`command.menu.invoke`, `editor.toolpalette.tool_execute`,
`automate.com.{get_for_command,send_command}`, `module.command.lookup`): typed
per-command templates so a small set of high-value built-in commands
(maintenance class: `AUDIT`, `-PURGE`) become agent-usable WITHOUT ever
exposing a raw command string, plus an honest headless-coverage estimate for
the 23 `constraints_associativity` ops. Full design rationale, threat model,
and the section-by-section measured findings live in
`docs/GOVERNED_COMMAND_TEMPLATES.md` (design doc committed first, per the
mission's own instruction) -- this entry is the compressed run log.

**Registry recon (measured, not trusted from the brief):** the brief cited
"16 runtime_commands ops blocked." Re-derived directly from
`config/operations.v2.json` (525 ops): every `blocked_reason` starting
`SAFETY_FORBIDDEN` that names raw command-string dispatch
(`acedCommand`/`sendStringToExecute`/`acedMenuCmd`/`AcTcTool::Execute`/
`SendCommand`) totals **10**, spread across 4 families (not 1) --
`active_document_write_original` (4), `com_activex` (2), `editor_input` (1),
`runtime_commands` (1), `ui_customization` (2). The `runtime_commands` family
itself has 7 more `SAFETY_FORBIDDEN` ops but they're ARX module load/unload
hazards (loading arbitrary code into the host process), a different threat
this lane's templates do not address. The briefed "23 constraints/DCM-blocked"
figure DID reproduce exactly (`family == "constraints_associativity"`, all 23
`SAFETY_FORBIDDEN`). Flagged the "16" discrepancy rather than silently
substituting it; full evidence table in the design doc section 0.

**Built:** `config/command_templates.json` (template registry: `template_id`,
fixed `command_sequence` of `{"literal"}`/`{"slot"}` steps, typed `slots`
(enum/int_range/float_range/name_token/staged_path), `postconditions`,
`headless_safe` flag) + `tools/command_template_engine.py` (validate args ->
render `.scr` -> stage a copy (never the original) -> run
`accoreconsole.exe /i <staged> /s <script>` (mirrors
`autocad-router.ps1`'s `Invoke-CadJobRoute`/`Invoke-AccoreScr` staging/
accoreconsole-invocation pattern, reimplemented in Python rather than adding a
new router `-Action`, per the brief's preference not to touch the router) ->
enforce postconditions -> emit an `ariadne.autocad_sdk_result.v2`-shaped
envelope). A universal hostile-character gate (control chars, quotes,
semicolon, LISP parens) runs on every slot value before its type-specific
validator, regardless of declared type -- the literal implementation of "no
free-text slot ever reaches the command line." `write_original` is impossible
by construction: the registry loader hard-rejects any template whose
`write_mode.allowed` contains anything but `read`/`write_copy`.

**Live-verified, both templates, real accoreconsole (AutoCAD 2027, this
machine's Korean-locale build), staged copies of
`tests/fixtures/native_sample.dwg`:**
- `maintenance.drawing.audit` (`AUDIT`, `fix_answer` slot): regex-captured the
  real Korean console text (`전체 (\d+)건의 오류를 찾아서 (\d+)건이 수정됨`)
  -> `errors_found=0, errors_fixed=0`; entity-count probe (AutoLISP
  `(sslength (ssget "_X" ...))` written to a run-dir file before+after)
  `21747 == 21747` -- exact match to the fixture's documented baseline. `ok`
  in both `read` and `write_copy` write modes, `accoreconsole` exit 0.
- `maintenance.drawing.purge` (`-PURGE A * N`, no agent-controllable slots --
  the "verify each name" prompt is a hardcoded literal `N`, never exposed,
  specifically to close the unbounded per-item-confirmation hazard): real
  named-object deletions observed and regex-captured (a layer, a text style, 3
  dimstyles, a leader style across two separate runs), entity count
  `21747 == 21747` both times (PURGE never touches entities, confirmed).
  `ok` in `write_copy` mode, exit 0.
- Original DWG sha256 `eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76`
  verified unchanged before/after every one of ~12 live runs (successful,
  postcondition-failed, and timed-out alike) via an `ORIGINAL_MUTATED`
  hard-check that overrides every other status.

**Real bugs found + fixed during live verification (not assumed away):**
1. `accoreconsole`'s stdout is UTF-16LE with no BOM (measured) -- decoding as
   UTF-8 produced null-byte-interleaved mojibake and silently broke every
   regex postcondition. Added `_read_accoreconsole_stdout()`'s NUL-density
   heuristic.
2. First staging implementation passed a `run_dir`-relative `.scr` path into
   the `/s` argument while `cwd` was set to the STAGED DWG's own directory (a
   different absolute path) -- accoreconsole correctly reported "file not
   found" for the script. Fixed by resolving `run_dir` to absolute before
   deriving any path from it.
3. **`AUDIT`'s `fix_answer="N"` deterministically hangs `accoreconsole` on
   process exit** -- 4/4 trials, alternated against 4/4 clean exits for
   `"Y"` on the byte-identical `.scr` apart from one character, ruling out
   generic system-load flakiness as the explanation. In every "N" trial the
   AUDIT report text and the after-probe entity-count file were both written
   correctly to disk BEFORE the hang (verified) -- all real work completes;
   only the process's own shutdown never returns, until the engine's
   timeout+kill fires (`status: "error"`, `code: "ACCORECONSOLE_TIMEOUT"`,
   `retryable: true`; original confirmed unchanged in these trials too). Root
   cause not established (native accoreconsole behavior, not this lane's
   script generation). Response: shipped `fix_answer` enum is `["Y"]` only;
   `"N"` is now rejected by validation before ever reaching accoreconsole (a
   dedicated regression test asserts this). Full narrative in design doc
   section 5.

**DCM / `constraints_associativity` coverage estimate (23 ops):** the
command names the brief suggested mapping against (`GEOMCONSTRAINT`/
`DIMCONSTRAINT`/`DELCONSTRAINT`/`PARAMETERS`) belong to a DIFFERENT ObjectARX
class hierarchy (`AcDbAssoc2dConstraintGroup`, the 2D sketch/parametric
constraint manager) than what these 23 ops' `blocked_reason` text actually
references (`AcDbAssocArrayActionBody`/`AcDbAssocXxxSurfaceActionBody`/
`AcDbAssocManager` -- the associative array/surface/network-evaluation
subsystem); confirmed zero registry matches for those 4 command names.
Flagged rather than silently substituted (design doc section 4 has the real
class-to-command correspondence table). Live-attempted `REGEN` (candidate
trigger for `inspect.assocaction.evaluate` +`inspect.assocnetwork.evaluate`,
one-off, not a shipped template): runs headless cleanly, exit 0, original
unchanged -- but does NOT count as promoting either op, because `REGEN`'s
whole purpose is to force the exact solver-evaluation callback path their
`blocked_reason` forbids; typed-argument-slot safety (what a template
provides) does not bound what a solver callback does once invoked, so
templating a working command here does not resolve the actual safety
rationale. Second candidate (`-ARRAYRECT`/`ARRAYEDIT` for the 10
`assocarray.*` ops) was NOT live-attempted: its multi-prompt "grip edit"
script sequence is unestablished in this repo, and the ceiling was already
known (unbounded array-solver evaluation, same class of risk as `REGEN`) --
spending a live cycle to prove the mechanics would not change the verdict.
**Verdict: 0 of 23 promoted.** Reported honestly as the brief's own accepted
possible outcome, not padded.

**Registry update -- deliberately NOT the pattern first tried.** First
attempt appended 2 new op records (`maintenance.drawing.audit`,
`maintenance.drawing.purge`) directly to `config/operations.v2.json`'s
`operations` array and bumped `totals`. Measured consequence:
**11 test failures** in OTHER lanes' files (`test_catalog_completeness.py`,
`test_op_dag_generate.py`, `test_m08a_catalog_reopen.py`) -- the array's total
count (525) and `by_status`/`by_family` totals are a frozen cross-wave
invariant several other lanes' tests hardcode, and
`operation_coverage_matrix.is_raw_command()`'s substring heuristic
(`"acedCommand" in native_api`) false-positived on this lane's OWN defensive
phrasing ("never a raw acedCommand... surface") in the new records' text.
Reverted both `config/operations.v2.json` and the regenerated
`config/op_dag.json` back to HEAD. Re-did it the way this file's OWN
established convention actually works (`m02_extend`, `m04_operation_registry_
completion`, `m05_patch_diff_validation_transaction`, `m08a_catalog_reopen` are
all top-level namespaced keys, none of them touch the `operations` array): added
`w5_tmpl_governed_command_templates` as a new additive top-level key (27-line
diff) with template_ids/evidence/status, explicitly noting these ops are not
yet wired into `cadctl.Cad.run_operation`'s allow-list dispatch (a follow-up
integration task, not claimed done here).

**Tests:** `tests/unit/test_command_template_engine.py` (30 new tests --
registry load/write-mode guard, injection-gate coverage across every slot
type with literal hostile strings, `render_script` determinism +
undeclared/unknown-arg rejection, `evaluate_postconditions` as a pure
function against synthetic evidence including the REAL registry's regex
pattern, `run_template` gate short-circuits, a dedicated regression test
pinning `fix_answer="N"` to VALIDATION_ERROR, and 2 `CADOS_LIVE`-gated live
certs). `python -m pytest tests/unit -q` -> **1173 passed, 0 failed** (1143
baseline + 30 new); `CADOS_LIVE=1 python -m pytest tests/unit -q` -> **1176
passed, 0 failed** (both live certs run and pass).

**Fixture integrity:** `tests/fixtures/native_sample.dwg` sha256
`eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76` unchanged
throughout every experiment above (script-logic bugs, the fix_answer hang, and
clean successes alike). `config/operations.v2.json`/`config/op_dag.json` are
byte-identical to HEAD apart from the intentional additive
`w5_tmpl_governed_command_templates` key (op_dag regen from the first, wrong
attempt was reverted, not left as drift).


