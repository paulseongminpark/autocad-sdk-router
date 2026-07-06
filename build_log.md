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
