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

Each gate carries `id`, `status` ∈ `{pass, fail, skipped, blocked}`, `required` (bool), and
`expected`/`actual`/`operator`/`message`/`evidence_ref` evidence. **Pass/skip semantics:** a gate
is `pass` only when its assertion actually ran and held; a gate whose **required input is missing**
reports `blocked` (required gate) or is **softly skipped** (non-required), and **never** `pass`
(no-fake-success).

`validate_target` runs **14 gates**: a base group (over an IR + run folder) and a patch/diff group
(over a diff/patch/patch-run). The patch/diff gates are **non-required** and **skip cleanly** when
no diff/patch is supplied — that skip is the truthful result, not a failure.

### Base gates (IR + run folder)

| id | required | what it asserts | operator | blocked/skip when |
|----|----------|-----------------|----------|-------------------|
| `ir_schema_present` | yes | `ir.schema == "ariadne.dwg_graph_ir.v1"` | eq | no IR supplied ⇒ `blocked` |
| `entity_count_consistency` | yes | `ir.diagnostics.entity_count == len(ir.entities)` **and** `== independent summary count` when present (truth gate) | eq | no IR ⇒ `blocked`; missing `entities[]`/`entity_count` ⇒ `fail` |
| `required_artifacts_exist` | yes | run folder contains `cad_job.json`, `cad_result.json`, `dwg_graph_ir.json` | exists | no `run_dir` ⇒ `blocked` |
| `no_original_write_evidence` | yes | extraction operated on a **staged copy**: `source.dwg_path` present and `!= source.original_path` (ideally under `staging/`) | ne | no IR ⇒ `blocked`; distinct-but-weak evidence ⇒ `partial` (non-required) |
| `registry_status_consistency` | yes | wired-baseline ops present and `status=="implemented"` in `operations.v2.json` | eq | `operations.v2.json` missing/unreadable ⇒ `blocked` |
| `run_folder_completeness` | no | run folder captured `stdout*` and `stderr*` evidence | exists | no `run_dir` ⇒ soft-skip |
| `no_fake_success` | yes | IR coverage flags are honest: no section flagged `section_status=="implemented"` whose IR key is **entirely absent**, and `coverage.modelspace_count_from_native` (when set) is backed by `len(entities)`. **Present-but-empty is honest** (e.g. `xrefs == []` for a drawing with no xrefs is NOT flagged). | eq | always runs when an IR is present |

### Patch / diff gates (non-required; skip when no diff/patch supplied)

| id | required | what it asserts |
|----|----------|-----------------|
| `cad_diff_schema` | no | a supplied diff conforms to `ariadne.cad_diff.v1` (schema/required keys) |
| `diff_expected_changes` | no | the diff's `summary.added/removed/modified` matches the patch's declared expectation |
| `no_unrelated_changes` | no | the diff contains no changes outside the patch's declared scope |
| `patch_policy` | no | the patch's `policy` is safe (`staged_copy==true`, `write_mode != write_original/live_edit`) |
| `staged_copy_used` | no | the patch run operated on a staged copy (run-dir is a patch run) |
| `journal_present` | no | the patch run wrote a `journal.json` audit trail |
| `original_dwg_unchanged` | no | the patch run's original-unchanged proof holds (sha256 before == after) |

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
- Postcondition checking of an applied patch is out of scope of the gate set
  here; it runs inside the patch lifecycle once execution exists (see below).

## M02 — gates against the live native_full IR (measured)

Run `validate_target(ir_path="runs/m02_cadctl_rich/dwg_graph_ir.json",
run_dir="runs/m02_cadctl_rich")` — overall **`status == pass`**, **14 gates: 7 pass, 0 fail,
7 skipped** (the patch/diff group skips cleanly because no diff/patch was supplied):

```
ir_schema_present            pass    (schema == ariadne.dwg_graph_ir.v1)
entity_count_consistency     pass    (21747 == len(entities) == sum(entities_by_type))  ← the truth gate
required_artifacts_exist     pass    (cad_job.json, cad_result.json, dwg_graph_ir.json present)
no_original_write_evidence   pass    (source.dwg_path under staging/golden/… != original_path)
registry_status_consistency  pass    (inspect.database.summary + inspect.entity.count == implemented)
run_folder_completeness      pass    (stdout.txt + stderr.txt captured)             [non-required]
no_fake_success              pass    (coverage flags honest; xrefs==[] is honest-empty, not flagged)
cad_diff_schema              skipped (no diff supplied)                              [non-required]
diff_expected_changes        skipped (no diff supplied)                              [non-required]
no_unrelated_changes         skipped (no diff supplied)                              [non-required]
patch_policy                 skipped (no patch supplied)                             [non-required]
staged_copy_used             skipped (run_dir is not a patch run)                    [non-required]
journal_present              skipped (not a patch run)                               [non-required]
original_dwg_unchanged       skipped (not a patch run)                               [non-required]
```

The truth gate is exact, not sampled: `entity_count` is set to `len(entities)` by the IR producer,
so a mismatch is structurally impossible unless the native asserted count disagrees — in which case
`entity_count_consistency` still compares `entity_count` to `len(entities)` (always equal) **and**
the producer records a `diagnostics.warnings` entry + `coverage.match=false`. For this artifact the
native asserted `modelspace_entities == 21747` agrees, so there is no warning.

**`no_fake_success` honesty note.** This required gate would `fail` if a section were flagged
`section_status=="implemented"` while its IR key is **absent**, or if a claimed native modelspace
count were unbacked by `len(entities)`. It deliberately does **not** flag present-but-empty sections:
the reference IR's `xrefs == []` (`section_status.xrefs == "implemented"`) is a *truthful* empty
result (the drawing binds no xrefs) and passes. (A transient early run during concurrent peer-lane
edits mis-reported this as a failure against a stale module load; the authoritative behavior on the
settled tree is `pass` — present-but-empty is honest.)

## Patch-lifecycle gates are LIVE (run when a patch/diff is supplied)

The patch/diff gates above are **landed**, not planned. They run with real assertions when
`patch_engine.apply_staged` produces a patch run (diff + journal + original-unchanged proof) and that
run folder / diff is passed to `validate_target`. With no diff/patch supplied they skip (non-required)
— which is why an IR-only validation is `pass` with 7 skips, never a fake pass.
