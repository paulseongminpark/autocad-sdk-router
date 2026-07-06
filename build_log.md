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
