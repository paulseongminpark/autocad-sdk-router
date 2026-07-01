# PATCH_ENGINE_SPEC — `tools/patch_engine.py`

Lane E **patch shell** for the CAD OS Layer. M01 = dry-run-only SAFE SHELL.
M02 = adds the **staged-write lifecycle** and `apply_staged(...)` over a real router write op.

## Purpose

A patch is an **`ariadne.cad_patch.v1`** document
(`schemas/cad_patch.v1.schema.json`): an ordered, idempotent batch of CAD
mutations that **always** target a STAGED copy of a drawing, never an original
in place.

> **M02 status — read this first (implementation-true).** The M01 surface
> (`validate_patch_schema`, `classify_patch_risk`, `dry_run_plan`, the three guards) is **landed and
> unchanged**. The M02 **`apply_staged(patch, dwg_path, out_dir)`** entrypoint and the full
> staged-write lifecycle (§A) are **landed on disk** (`tools/patch_engine.py`), as is the sibling
> **`tools/cad_diff.py` `compute_diff(...)`** it calls. The router write path is real and wired
> (`write.layer.create`, `write.entity.line`, `write.entity.circle` → `write_mode="write_copy"` →
> `_QSAVE` of a staged copy — see §B). `apply_staged` applies **one mutation per call**
> (`operations[0]`; later ops are recorded `deferred`) and proves the original is untouched by
> hashing it **before and after** (`sha256 before == after`). The MCP tool `cad.patch_apply_staged`
> is wired to it. Truthful degradation is preserved: a patch op with **no native write handler**, or
> an unavailable sibling (`ir_builder`/router host/`cad_diff`/`validator`), returns
> `not_implemented`/`partial`/`blocked` with a reason — **never a fake `ok`**. §C lists exactly what
> is live vs still deferred.

The M01 `dry_run_plan` path performs **no destructive writes**: it validates, risk-classifies, and
*plans* patches; execution of the declared mutation ops is `not_implemented` there.

## Safety guarantees

- **Standard library only.** No third-party imports, no pip.
- **No execution.** `dry_run_plan` resolves each op to its registry mapping and
  returns a PLAN; it never runs accoreconsole, the router, or any writer.
- **Original-DWG safety, enforced three ways:**
  - `require_staged_copy` — `policy.staged_copy` must be `true` and
    `target_dwg.staged_path` must be present and `!= original_path`.
  - `reject_write_original_by_default` — `policy.write_mode` of `write_original`
    or `live_edit` is refused by default (only `write_copy`/unset is allowed).
  - `require_validation` — a mutating patch must declare `postconditions` so the
    result is checkable (drives `validation_report` gates downstream).
- **No-fake-success.** Declared ops return `execution_status: "not_implemented"`;
  a patch failing schema validation or any guard yields `status: "rejected"`.

## Public API

```python
from patch_engine import (
    validate_patch_schema, classify_patch_risk, dry_run_plan,
    require_staged_copy, reject_write_original_by_default, require_validation,
    DECLARED_OPS, OP_REGISTRY_MAP, PATCH_SCHEMA_ID,
)
```

| function | returns |
|----------|---------|
| `validate_patch_schema(patch)` | `{"valid": bool, "errors": [...], "warnings": [...]}` — structural check vs cad_patch.v1 (schema const, required fields, `staged_path`, non-empty `operations[]`, `policy.staged_copy==true`, condition op enums). Not a full JSON-Schema engine. |
| `classify_patch_risk(patch)` | `{"risk": low\|medium\|high\|blocked, "reasons": [...], "per_op": [...]}` |
| `dry_run_plan(patch)` | a `ariadne.cad_patch.dry_run.v1` plan (see below) |
| guards | `{"ok": bool, "guard": id, "message": str}` each |

## Declared mutation ops → registry mapping

`OP_REGISTRY_MAP` maps each high-level patch op to the operation-registry id
(`config/operations.v2.json`) that would carry it. The patch-apply *pipeline*
itself routes through `apply.patch` (a `stub` op today), so EXECUTION of any op
is `not_implemented`.

| declared op | registry op | risk |
|-------------|-------------|------|
| `create_line` | `write.entity.create` | low |
| `create_polyline` | `write.entity.create` | low |
| `create_text` | `write.entity.create` | low |
| `set_layer` | `modify.entity.common` | medium |
| `move_entity` | `modify.entity.transform` | medium |
| `delete_entity` | `modify.entity.explode` | high |

> CADOS F8: `set_layer`/`move_entity`/`delete_entity` used to map to
> `write.entity.modify`/`write.entity.delete` -- ids that do not exist
> anywhere in `config/operations.v2.json` (a dangling target neither this
> table nor a live dispatch could ever resolve). Repointed at the real,
> `implemented`, live-dispatchable ids above (`tools/reconcile_native_registry.
> check_vocab_lockstep` now cross-checks this map against the registry + the
> native HasOp gates on every promotion). `delete_entity`'s target,
> `modify.entity.explode`, is honestly NOT a delete/erase (it appends the
> exploded pieces and preserves the source, and its own `write_level` is
> `default_write_mode="read"` / `dwg_persisted=false` -- nothing is even
> persisted); no real erase/delete-entity op exists in this registry yet.

Risk roll-up: max over ops; bumped to `high` if the patch mutates/deletes
existing entities with no `postconditions`; `blocked` if a hard guard fails
(no staged copy, or write_mode targets the original).

## dry_run_plan output

```jsonc
{
  "schema": "ariadne.cad_patch.dry_run.v1",
  "patch_id": "...",
  "schema_validation": { "valid": true, "errors": [], "warnings": [] },
  "risk": { "risk": "medium", "reasons": [...], "per_op": [...] },
  "guards": [ {"ok": true, "guard": "require_staged_copy", "message": "..."}, ... ],
  "guards_ok": true,
  "planned_ops": [
    { "index": 0, "operation": "create_line", "registry_op": "write.entity.create",
      "registry_status": "<status or null>", "apply_pipeline_op": "apply.patch",
      "apply_pipeline_status": "stub", "args": {...}, "risk": "low",
      "execution_status": "not_implemented" }
  ],
  "execution": "not_implemented",
  "status": "planned",        // or "rejected" on schema/guard failure
  "notes": [ "EXECUTION is not_implemented in this packet (no destructive writes)" ]
}
```

`registry_status`/`apply_pipeline_status` are read live from
`operations.v2.json`; both are `null` when the registry is unavailable (noted).

## Exact commands

```bash
# Self-test: dry-run a sample patch + a negative (write_original) case.
python tools/patch_engine.py        # exit 0 = SELFTEST_OK

# Verdict line example:
#   SELFTEST_OK | status=planned risk=medium guards_ok=True | neg_status=rejected
```

---

## A. The M02 staged-write lifecycle (`apply_staged`)

`apply_staged(patch: dict, dwg_path: str, out_dir: str) -> dict` is the single execution entrypoint.
It NEVER mutates `dwg_path` (the original); it stages a copy and mutates the copy. The pipeline:

```
 validate ─▶ risk ─▶ stage ─▶ pre-IR ─▶ apply(write_copy) ─▶ post-IR ─▶ diff ─▶ validate ─▶ journal
   │          │        │         │            │                  │          │        │          │
   │          │        │         │            │                  │          │        │          └ write run-dir manifest
   │          │        │         │            │                  │          │        └ validator.validate_target(post-IR, run_dir)
   │          │        │         │            │                  │          └ cad_diff.compute_diff(pre_ir, post_ir) → cad_diff.v1
   │          │        │         │            │                  └ cadctl.inspect(staged_out, include_rich) → post dwg_graph_ir.v1
   │          │        │         │            └ run_job.run_router_cad_job(staged, run_dir, op, write_mode="write_copy")
   │          │        │         └ cadctl.inspect(staged, include_rich) → pre dwg_graph_ir.v1
   │          │        └ shutil.copy2(original → staging/golden/<ts>/input.dwg) + chmod writable
   │          └ classify_patch_risk(patch); a `blocked` risk stops here
   └ validate_patch_schema(patch) + the three guards; a `rejected` verdict stops here (no staging)
```

Stage-by-stage contract:

| stage | calls | hard rule |
|---|---|---|
| **validate** | `validate_patch_schema` + `_run_guards` | `policy.staged_copy==true`, `staged_path != original_path`; fail ⇒ `status: "rejected"`, no copy made |
| **risk** | `classify_patch_risk` | `risk=="blocked"` (guard breach) ⇒ stop before any write |
| **stage** | `shutil.copy2` → `staging/golden/<ts>/` then `os.chmod(…, 0o666)` | the ORIGINAL is opened read-only and never written; the copy is the only writable target |
| **pre-IR** | `cadctl.Cad().inspect(staged, run_dir, include_rich=?)` | the before-state IR; its `entity_count` is the precondition baseline |
| **apply** | `run_job.run_router_cad_job(staged_copy, run_dir, op, write_mode="write_copy")` per op, in BUNDLE/array order | every op's stdout+stderr+exit captured into `run_dir`; the router stages ITS OWN copy and `_QSAVE`s a `staged_output.dwg` carrying the mutation |
| **post-IR** | `cadctl.Cad().inspect(staged_output, run_dir, include_rich=?)` | the after-state IR |
| **diff** | `cad_diff.compute_diff(pre_ir, post_ir)` → `ariadne.cad_diff.v1` | handle-keyed; `summary.added/removed/modified`; `comparison_basis: "handle"` |
| **validate** | `validator.validate_target(ir_path=post_ir, run_dir=run_dir)` + postcondition eval | `postconditions` (e.g. `entity_count delta_eq +1`) checked against `pre`→`post`; a mutating patch with no postconditions is refused by `require_validation` |
| **journal** | write the run manifest (patch, plan, pre/post IR refs, diff ref, validation ref) into `out_dir` | the durable audit trail |

**Policy defaults (safety-first):** `policy.dry_run` defaults **false** in the schema, but
`apply_staged` treats an absent/true `dry_run` as plan-only (delegates to `dry_run_plan`); a real
write requires `dry_run == false` AND `write_mode ∈ {write_copy}` (the default).
`write_original`/`live_edit` are **refused** by `reject_write_original_by_default` regardless of
`dry_run`. `atomic == true` ⇒ on any sub-op failure the staged result is discarded.

**Op mapping (declared op → native router op).** `apply_staged` resolves the patch's high-level op
to a native, router-wired write op via the landed **`NATIVE_WRITE_OP_MAP`**. The cad_job carries the
op's native args (`name`, `color_index`, `point`/`center`/`start`/`end`, `radius`, etc.) read by the
native job via `jsonFind`. The **live** map (the only ops with a native write handler today):

| declared op | live native router op (write_copy) | job args (minimal, real) |
|---|---|---|
| `create_line` | **`write.entity.line`** | `start:[x,y,z]`, `end:[x,y,z]`, `layer` |
| `create_circle` | **`write.entity.circle`** | `center:[x,y,z]`, `radius`, `layer` |
| `set_layer` | **`modify.entity.common`** | `handle`, `layer` (resolves the entity by `handle` and REASSIGNS its layer via `set_layer`) |
| `create_layer` | **`write.layer.create`** | `name`, `color_index` |

> CADOS F8/H-5: `set_layer` used to map to `write.layer.create` too, sharing
> `create_layer`'s handler -- but that handler only ENSURES a layer exists and
> never reads `handle`, so a `set_layer` op "succeeded" without ever
> reassigning the target entity's layer (an active fake-success). It is now
> wired to the real relayer `modify.entity.common`
> (`src/Ariadne.AcadNative/families/m08g_handlers.inc`, dispatcher
> `m08gDispatch`), which resolves `handle` and calls `AcDbEntity::setLayer`.
>
> `OP_REGISTRY_MAP` (the M01 plan-only map) still maps the broader declared set
> (`create_polyline`/`create_text`/`move_entity`/`delete_entity`) to registry ids
> (`write.entity.create`/`modify.entity.transform`/`modify.entity.explode`) for `dry_run_plan`, but those
> (aside from `set_layer` above) have **no native write handler** yet. In `apply_staged` any op not in
> `NATIVE_WRITE_OP_MAP` (`create_polyline`, `create_text`, `move_entity`, `delete_entity`, or unknown)
> returns **`not_implemented`** with a reason — never a fake success. `apply_staged` applies
> `operations[0]` only per call; later ops are journalled `deferred` ("apply_staged applies one
> mutation per call").

**Artifact layout** (under `out_dir`, as written by the landed `apply_staged`):

```
out_dir/
  patch.json                the patch as handed in (provenance)
  staged_input.dwg          the writable copy of the original (before mutation)
  staged_output.dwg         the mutated copy the router _QSAVE'd (carries the new entity)
  pre/   dwg_graph_ir.json   before-state native_full IR (+ its cad_job/cad_result/stdout/stderr)
  post/  dwg_graph_ir.json   after-state native_full IR
  cad_diff.json             ariadne.cad_diff.v1 (pre vs post, handle-keyed)
  validation_report.json    ariadne.validation_report.v1 (post-state + patch/diff gates)
  journal.json              ariadne.cad_patch.journal.v1 (ordered steps + every command's stdout/stderr/exit ref + original-unchanged proof)
  result.json               the run-result envelope (status, refs, original_unchanged)
```

The journal records, per step, the status and (for external commands) the captured
stdout/stderr/exit refs, plus the `sha256` of the original **before and after** the whole run as the
no-original-write proof.

## B. Router recipe for a real staged write (live)

```python
import run_job
res = run_job.run_router_cad_job(
    staged_copy_dwg,            # a shutil.copy2 of the original under staging/ (writable)
    run_dir,
    "write.entity.line",        # or write.layer.create / write.entity.circle (live native write ops)
    write_mode="write_copy",    # router stages ITS OWN copy, runs the native ObjectARX write, then _QSAVE
)
# res["staged_used"]  -> the mutated copy path (carries the new entity)
# res["result"]       -> the native result object; res["result_json"] -> its on-disk path
# stdout/stderr/exit are captured into run_dir (mandatory)
```

The original DWG is opened read-only at every hop; the only thing `_QSAVE`d is a staged copy. This
is the `write_mode == "write_copy"` branch in `autocad-router.ps1` (it appends `_QSAVE` to the
native job `.scr` only for `write_copy`/`write_original`/`live_edit`; `read` never saves).

## C. Live today vs deferred (honest)

**Live (M02, landed on disk):**
- M01 plan-only surface: `validate_patch_schema`, `classify_patch_risk`, `dry_run_plan`, guards.
- **`apply_staged(patch, dwg_path, out_dir)`** — the full staged-write lifecycle (§A), with truthful
  statuses `ok`/`blocked`/`not_implemented`/`partial`, one mutation per call, and an
  original-unchanged proof (sha256 before == after).
- **`tools/cad_diff.py` `compute_diff(pre_ir, post_ir)`** — handle-keyed, deterministic
  (`diff_id` is a content hash; no timestamps), `comparison_basis: "handle"`, with
  `summary.added/removed/modified` (+ `created_count/deleted_count` aliases) and
  `layer_changes`/`geometry_changes`/`bbox_changes` projections.
- The router write path: native write ops `write.layer.create` / `write.entity.line` /
  `write.entity.circle`, `write_copy` staged `_QSAVE`, stdout/stderr/exit capture.
- `cadctl.inspect(..., include_rich=True)` producing the pre/post native_full IR the lifecycle needs.
- The patch/diff `validation_report.v1` gates (`patch_policy`, `staged_copy_used`, `journal_present`,
  `original_dwg_unchanged`, `cad_diff_schema`, `diff_expected_changes`, `no_unrelated_changes`) are
  landed and run when a patch run / diff is supplied (see `VALIDATION_SPEC.md`).

**Deferred / partial (no-fake-success):**
- **Native write ops for** `create_polyline / create_text / move_entity / delete_entity` — not built;
  `apply_staged` returns `not_implemented` for them (only the four ops in `NATIVE_WRITE_OP_MAP` are
  live).
- **Multi-op batches** — `apply_staged` applies `operations[0]` per call; later ops are journalled
  `deferred`. A true multi-op transactional apply is future work.
- **Precondition/postcondition *value* evaluation against live drawing state** — the lifecycle builds
  the post-IR and computes the diff (so deltas are *available*); a full pre/postcondition evaluator
  is the next increment.
- No full JSON-Schema validation (stdlib only) — structural checks only.
- A live AutoCAD host is required for the write path; with the `.arx` lock (acceptance D1) the
  native pump degrades truthfully rather than faking a write.
