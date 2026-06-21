# PATCH_ENGINE_SPEC — `tools/patch_engine.py`

Lane E **safe patch shell** for the CAD OS Layer.

## Purpose

A patch is an **`ariadne.cad_patch.v1`** document
(`schemas/cad_patch.v1.schema.json`): an ordered, idempotent batch of CAD
mutations that **always** target a STAGED copy of a drawing, never an original
in place.

This module is a SAFE SHELL only. In this packet it performs **no destructive
writes**. It validates, risk-classifies, and *plans* patches; execution of the
declared mutation ops is `not_implemented`.

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
| `set_layer` | `write.entity.modify` | medium |
| `move_entity` | `write.entity.modify` | medium |
| `delete_entity` | `write.entity.delete` | high |

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

## Not implemented yet

- **Execution of all mutation ops** — `create_line/create_polyline/create_text/
  set_layer/move_entity/delete_entity` return `not_implemented`. Wiring them
  means implementing the `apply.patch` registry op (currently `stub`) through the
  router against a staged copy, then re-validating via `validator.py`.
- **Precondition/postcondition evaluation against live drawing state** — the
  shell records conditions but does not evaluate them (that needs an applied,
  re-extracted drawing). `validator.py` consumes the resulting IR once execution
  exists.
- No full JSON-Schema validation (stdlib only) — structural checks only.
