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
