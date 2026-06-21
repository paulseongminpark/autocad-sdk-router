# VALIDATION_SPEC — `tools/validator.py`

Lane E deterministic validation shell for the CAD OS Layer.

## Purpose

Given a DWG-graph IR document (`ariadne.dwg_graph_ir.v1`) and/or a `cadctl` run
folder, emit an **`ariadne.validation_report.v1`** document
(`schemas/validation_report.v1.schema.json`) by running a fixed set of
**deterministic gates**. The report's overall `status` is `pass` only when every
**required** gate passed.

This is the canonical home of the **entity-count truth gate**:
`diagnostics.entity_count == len(entities)` (and `== an independent summary
count` when one is recoverable).

## Safety guarantees

- **Standard library only** (Python 3.12). No third-party imports, no pip.
- **No LLM, no heuristics, no sampling.** Every gate is a pure assertion over
  structured inputs. Identical inputs always produce an identical report
  (`validation_id` is the only nondeterministic field — a fresh uuid per run).
- **Read-only.** Never writes the IR, the run folder, or any DWG. Only reads
  files (config/operations.v2.json with `utf-8-sig`, the IR, run-dir listings).
- **No-fake-success.** A gate whose input is missing reports `blocked` (required)
  or is softly skipped (non-required) — never `pass`. Overall `status` is never
  `pass` when a required gate did not actually execute.

## Public API

```python
from validator import validate_target
report = validate_target(ir_path="…/dwg_graph_ir.json", run_dir="…/runs/<ts>")
# report conforms to ariadne.validation_report.v1
```

`validate_target(ir_path=None, run_dir=None) -> dict`. Either argument may be
`None`; gates that need a missing input report `blocked`/skip softly.

## Gates

| id | required | what it asserts | operator |
|----|----------|-----------------|----------|
| `ir_schema_present` | yes | `ir.schema == "ariadne.dwg_graph_ir.v1"` | eq |
| `entity_count_consistency` | yes | `ir.diagnostics.entity_count == len(ir.entities)` **and** `== independent summary count` when present (truth gate) | eq |
| `required_artifacts_exist` | no | run folder contains `cad_job.json`, `cad_result.json`, `dwg_graph_ir.json` | exists |
| `no_original_write_evidence` | yes | extraction operated on a **staged copy**: `source.dwg_path` present and `!= source.original_path` (ideally under `staging/`) | ne |
| `registry_status_consistency` | yes | wired-baseline ops present and `status=="implemented"` in `operations.v2.json` | eq |
| `run_folder_completeness` | no | run folder captured `stdout*` and `stderr*` evidence | exists |

**Independent summary count** for the truth gate is recovered, in order, from:
`diagnostics.realized_entity_count` → `sum(diagnostics.entities_by_type)` →
`source.summary_modelspace_count`. If none exists, only the primary
`entity_count == len(entities)` assertion is enforced.

**Wired-baseline ops** (`_REQUIRED_WIRED_OPS`): `inspect.database.summary`,
`inspect.entity.count`. These are a deliberately small, stable subset of the 29
implemented ops — enough to detect registry regression without coupling the gate
to every catalog edit.

## Overall status roll-up

- any **required** gate `fail` → `fail`
- else any **required** gate `blocked` → `blocked`
- else any non-required `fail`/`partial`, or any `blocked`/`skipped` → `partial`
- else → `pass`

## Exact commands

```bash
# Self-test: validate a tiny inline fixture IR, print the report, verdict on last line.
python tools/validator.py            # exit 0 = SELFTEST_OK

# Programmatic
python -c "from tools.validator import validate_target; \
import json; print(json.dumps(validate_target(ir_path='IR.json', run_dir='RUN'), indent=2))"
```

The self-test prints the full report then a verdict line:
`SELFTEST_OK | overall=partial | ir_schema=pass count=pass staged=pass`
(`overall=partial` because no `run_dir` is supplied, so the two non-required
run-folder gates are blocked-soft — this is the truthful result, not a failure).

## Not implemented yet

- No JSON-Schema engine is bundled (stdlib only) — gates assert the specific
  fields they need, not full-document schema validation. Full schema validation
  is deferred to a future lane / external `jsonschema` step.
- Cross-engine agreement (e.g. native == DXF == LibreDWG counts) is **not** a
  gate here; this validator asserts internal IR consistency. Multi-engine
  agreement belongs to a higher-level orchestration that feeds several IRs in.
- Postcondition checking of an applied patch is out of scope (patches do not
  execute in this packet — see `PATCH_ENGINE_SPEC.md`).
