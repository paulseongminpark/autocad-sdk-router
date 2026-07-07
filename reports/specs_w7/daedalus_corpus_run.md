# Daedalus Corpus Run — 414-File Batch Execution Plan

Status: design (not yet executed). Track 4, wave 7 (octoloop).

Scope: a concrete, operator-executable plan for running a 414-file DWG corpus
through this repo's existing batch machinery, `tools/corpus_batch.py`, and
turning the resulting per-file envelopes into corpus-level aggregates
(per-layer counts, entity-type histogram, anomaly flags). This plan
introduces **no new code**. It sequences and parameterizes machinery that
already exists at HEAD:

- `tools/corpus_batch.py` — per-file worker isolation, staging, resume,
  summary (read in full for this plan; see `docs/CORPUS_BATCH.md` for its
  standing reference doc).
- `tools/cadctl.py::Cad.run_operation` — the governed op-dispatch surface the
  worker calls per file. This is the same surface `cadagent-mcp`'s
  `cad.run_operation` MCP tool wraps; the corpus run drives it headlessly,
  file-by-file, instead of interactively.
- `schemas/dwg_graph_ir.v1.schema.json` — the output shape `inspect.layers`
  and `inspect.entities` emit, and the schema the aggregation stage reads
  against.

## Machinery recap (grounding)

`corpus_batch.py` takes exactly one of `--manifest <json>` or
`--glob <pattern>`, resolves that to an ordered list of `CorpusEntry`
records, and for each entry spawns a **separate worker subprocess**
(`sys.executable -X utf8 corpus_batch.py --worker-request <path>`) with a
per-file timeout (`--timeout-sec`, default `DEFAULT_TIMEOUT_SEC = 240`).

Per file, the worker:

1. Verifies the input is `.dwg` (else terminal `status=failed`,
   `error_class=non-dwg`).
2. `sha256`-hashes the source; if the manifest row pinned an
   `expected_sha256` and it does not match, terminal
   `status=failed`, `error_class=unreadable` — the file is never opened.
3. `shutil.copy2`s the source to `<case_dir>/source_staged.dwg` (staging
   layer 1 — the batch-level copy; the original is never touched again).
4. Runs the configured ops in order through
   `cadctl.Cad(router_home=ROOT).run_operation(op_id, args=..., dwg_path=staged_path, out_dir=op_dir)`.
   Inside `run_operation`, a **second** staged copy is made under
   `staging/dwg_job_<stamp>/input.dwg` (staging layer 2) before accoreconsole
   ever runs, and the *original* source's sha is re-hashed after the run to
   assert `original_unchanged`. Two independent staging layers stand between
   every op and the source file.
5. Persists `result_envelope.json` incrementally — once after staging, once
   after each op.

Default ops (`DEFAULT_OPS`, used when `--ops`/`--ops-file` is omitted) are
all `inspect.*` — registry `write_level.default_write_mode = "read"`,
`allowed_write_modes = ["read"]` for every one of them (verified against
`config/operations.v2.json`):

```json
[
  { "id": "inspect.database.summary", "args": {} },
  { "id": "inspect.layers",           "args": {} },
  { "id": "inspect.entities",         "args": {} }
]
```

This plan uses the default op set unchanged. It is the minimum read-only op
set that covers every aggregation this plan needs: `inspect.database.summary`
gives header/unit/modelspace-count context, `inspect.layers` gives the
symbol-table layer records, `inspect.entities` gives the full per-entity list
with `diagnostics.entities_by_type` and per-entity `layer`/`geometry.kind`/
`source.decoded`. `write_mode` is never passed explicitly by
`corpus_batch.py`, so every op runs at its registry default (`read`); nothing
in this plan requests or requires a write mode, and `write_original` is
categorically refused by `run_operation` regardless.

## Inputs

**Corpus location convention.** The 414-file corpus is not checked into this
repo (it is real, potentially large/sensitive drawing data). Stage it
outside version control, under one directory the operator controls, e.g.:

```
D:\dev\_ariadne\corpora\dae414\
  <file001>.dwg
  <file002>.dwg
  ...
```

Any location works — `corpus_batch.py` takes an absolute manifest or glob, so
the corpus root is a run-time parameter, not a repo convention. What *is*
fixed by this plan: the corpus root is treated as **read-only** for the
duration of the run (matching the repo-wide non-negotiable — originals are
never opened for write), and it is never copied into `runs/` wholesale; only
`corpus_batch.py`'s own per-file staged copies live under `runs/`.

**Manifest vs. glob.** For a 414-file governed run, prefer an explicit
**manifest with `sha256` pins** over `--glob`, for three reasons the code
already supports:

1. `load_manifest_entries` preserves manifest row order exactly (ordinal =
   row index) — deterministic, reviewable, diffable across re-runs. `--glob`
   is also deterministic (sorted by case-insensitive absolute path via
   `expand_glob_entries`), but a hand-reviewed manifest is an explicit,
   auditable input artifact instead of an implicit filesystem snapshot.
2. `expected_sha256` gives per-file integrity verification for free: the
   worker refuses to stage-and-run a file whose bytes drifted from what was
   catalogued (`error_class=unreadable`, `source_sha256_match=false`), before
   any op runs.
3. A manifest survives corpus reorganization; a glob pattern does not.

Manifest shape (`load_manifest_entries` contract):

```json
[
  { "path": "D:\\dev\\_ariadne\\corpora\\dae414\\0001.dwg", "sha256": "<lowercase hex, optional>" },
  { "path": "D:\\dev\\_ariadne\\corpora\\dae414\\0002.dwg" }
]
```

Relative `path` values resolve against the manifest file's own directory
first, falling back to repo-root-relative only if the manifest-relative path
does not exist and the repo-root-relative one does
(`_resolve_manifest_path`). For a corpus outside the repo, use absolute
paths in the manifest and this ambiguity never arises.

Building the manifest for the real 414-file set is an operator step outside
this plan's code surface (e.g. one `Get-ChildItem -Recurse -Filter *.dwg`
plus a `Get-FileHash` pass, piped to JSON) — this plan does not add a new
tool for that; it is a few lines of ad hoc PowerShell run once per corpus
snapshot, not part of the governed machinery.

## Ledger

`corpus_batch.py` has no separate ledger file today — the resumable ledger
**is** the set of per-case `result_envelope.json` files plus the run-level
`summary.json`/`summary.md` written once at the end of `run_batch()`. Resume
semantics (`should_resume_skip`) are real and exact:

- A case is skipped (and its prior terminal envelope reused, tagged
  `resumed: true`) only when `<case_dir>/result_envelope.json` exists **and**
  its `status` is one of `TERMINAL_STATUSES = {"ok", "failed", "timeout"}`.
- `--force` clears the case directory and reruns it unconditionally.
- Re-invoking the identical command with the identical `--out-dir` is the
  entire resume operation — no separate flag, no separate state file.

For a 414-file run at multi-minute per-file cost, the run-level
`summary.json` is **not** available until every file has resolved (it is
computed after the `for entry in entries` loop completes in `run_batch`).
Per-case `result_envelope.json` files, by contrast, appear as soon as that
file's ops finish and are safe to read mid-run. This plan adds one derived,
read-only convenience artifact on top of that — a JSONL tail — without
touching `corpus_batch.py`:

```powershell
Get-ChildItem "$RUN_DIR\*\result_envelope.json" |
  ForEach-Object { Get-Content $_ -Raw } |
  Set-Content "$RUN_DIR\ledger.jsonl"
```

Run that (or an equivalent short `python -c` one-liner) at any point during
or after the batch to get a single append-friendly JSONL file — one
result-envelope JSON per line, in whatever order the filesystem currently
has them — for `tail`-style progress inspection without opening 414
individual files. It is a derived view, not a new source of truth; the
per-case envelopes remain authoritative and this file can be regenerated at
any time.

## Output layout

```
runs/
  corpus_dae414_<stamp>/          <-- --out-dir, stamp = YYYYMMDD_HHMMSS
    0000_<name>/
      worker_request.json
      worker_stdout.txt
      worker_stderr.txt
      source_staged.dwg           <-- staging layer 1 (batch-level copy)
      result_envelope.json        <-- per-file ledger entry
      op_00_inspect_database_summary/
      op_01_inspect_layers/
      op_02_inspect_entities/
    0001_<name>/
      ...
    ...
    0413_<name>/
    summary.json                  <-- written once, after all 414 resolve
    summary.md
    ledger.jsonl                  <-- derived, see Ledger section
    aggregate/                    <-- this plan's aggregation stage, see below
      layer_counts.json
      entity_type_histogram.json
      anomalies.json
      aggregate_summary.md
```

`<idx>_<name>` ordinals are zero-padded to the manifest's own row count
width convention used by `corpus_batch.py` (`f"{ordinal:04d}"` — 4 digits,
sufficient for 414 and any corpus up to 9999 files without change).

## Operator commands

All commands run from the repo root with `PYTHONUTF8=1` (the module sets
this itself via `os.environ.setdefault`, but set it in the shell too for
consistent console encoding on non-ASCII layer names).

**1. Calibration sub-batch (10 files) before committing to the full 414** —
required by the Limits section below, not optional:

```powershell
python -X utf8 tools\corpus_batch.py `
  --manifest D:\dev\_ariadne\corpora\dae414\manifest_calib10.json `
  --out-dir runs\corpus_dae414_calib `
  --timeout-sec 240
```

Inspect `runs\corpus_dae414_calib\summary.json` — `total_elapsed_sec` divided
by 10 is this corpus's real observed seconds/file, replacing the estimate in
Limits below before running the full set.

**2. Full run:**

```powershell
python -X utf8 tools\corpus_batch.py `
  --manifest D:\dev\_ariadne\corpora\dae414\manifest.json `
  --out-dir runs\corpus_dae414_<stamp> `
  --timeout-sec 240
```

**3. Resume after an interruption (identical command, identical `--out-dir`):**

```powershell
python -X utf8 tools\corpus_batch.py `
  --manifest D:\dev\_ariadne\corpora\dae414\manifest.json `
  --out-dir runs\corpus_dae414_<stamp> `
  --timeout-sec 240
```

Files with a terminal envelope are skipped; unfinished/never-started files
run.

**4. Force-rerun specific files:** re-run with `--force` against a manifest
containing only the subset to redo (a filtered copy of the full manifest —
`--force` reruns every entry passed to it, not a specific ordinal list).

## Aggregation

Aggregation reads the per-case `result_envelope.json` files plus each op's
`result_ref` JSON (the parsed `dwg_graph_ir.v1` document for `inspect.layers`
/ `inspect.entities`; `cadctl.Cad.run_operation` records that path verbatim
as `env["result_ref"] = run_res.get("result_json")`). No new extraction
happens in this stage — it is a pure read-and-tally pass over artifacts the
batch run already produced.

**Per-layer counts.** Two views, both derived from real schema fields:

- *Layer table size per file*: `len(symbol_tables.layers)` from each file's
  `inspect.layers` result — how many `LAYER` records the drawing defines.
- *Entities per layer*: group `entities[]` (from the `inspect.entities`
  result) by each entity's `layer` field, count per group, per file. Roll
  up corpus-wide into `{layer_name: {file_count, entity_count}}` — how many
  files use a given layer name and how many entities live on it in total.
  Korcorrelates directly with `database.codepage` in the IR — layer names
  are not assumed ASCII (the schema flags this explicitly for
  `DWGCODEPAGE`/Korean text).

**Entity-type histogram.** `inspect.entities`' own
`diagnostics.entities_by_type` (a `{DXF type: count}` object the extractor
already computes, summing to `diagnostics.entity_count` for its declared
`count_scope`) is read as-is per file and summed across the corpus into one
`entity_type_histogram.json`. This is the same field the schema's truth-gate
description calls out (`entities_by_type` sums to `entity_count`); the
aggregation stage does not recompute per-entity type tallies independently
— it trusts and sums the extractor's own self-reported histogram, and
separately flags mismatches (below).

**Anomaly flags.** Three classes, all derived from fields the schema and
`corpus_batch.py` already emit — none require new extraction logic:

1. **Extraction failure** — any case whose top-level `status` is `failed`
   or `timeout`, or whose `ops_run[i].status != "ok"` for any op. Carries the
   existing `error_class` taxonomy (`non-dwg`, `unreadable`,
   `password_or_proxy`, `timeout`, `extraction-crash`) straight through —
   aggregation groups by `error_class` to distinguish "one corrupt file" from
   "every file in this corpus is password-protected" (a policy issue, not a
   per-file bug).
2. **Entity-count outliers** — two sub-checks:
   - *Truth-gate mismatch* (hard failure, per file): `diagnostics.entity_count
     != diagnostics.realized_entity_count`. The schema defines this equality
     as the cross-engine truth gate; a mismatch means the extractor's own
     self-report disagrees with what it actually emitted, independent of
     any corpus-wide comparison.
   - *Corpus-relative outlier* (soft flag, statistical): files whose
     `diagnostics.entity_count` falls outside
     `median ± 3 * MAD` (median absolute deviation) of the corpus's own
     distribution. This repo's own fixtures already span
     21,747 to 291,706 modelspace entities (`reports/performance_latest.md`),
     so a fixed absolute threshold would be meaningless across a real
     414-file corpus of unknown provenance; the threshold must be computed
     from the corpus itself, not hard-coded.
3. **Unreadable layers** — group entities by `layer`, and within each layer
   group count entities where `source.decoded == false` (schema: "False =
   geometry kind 'unsupported'/proxy fallback, no-fake-success") or
   `geometry.kind == "unsupported"`. A layer where a large fraction of its
   entities are undecoded is flagged — this usually means a third-party
   ARX-dependent entity class living on that layer whose owning app was not
   loaded, which is a real, actionable extraction gap, not a soft-fail to
   paper over. `custom_objects[].decoded == false` entries are folded into
   the same tally via their `owner_handle`'s entity/layer when resolvable.

Aggregation output files (written by this plan's aggregation pass, not by
`corpus_batch.py` itself — this is a post-processing step over its outputs):

- `aggregate/layer_counts.json` — corpus-wide `{layer_name: {file_count,
  entity_count}}` plus per-file layer-table sizes.
- `aggregate/entity_type_histogram.json` — corpus-wide `{dxf_type: count}`.
- `aggregate/anomalies.json` — one record per flagged file/layer with its
  anomaly class(es) and the specific field values that triggered the flag.
- `aggregate/aggregate_summary.md` — human-readable rollup: total files,
  total entities, top-20 layers by entity count, top-20 entity types, and a
  table of every flagged anomaly.

This plan does not prescribe a specific aggregation script path (out of
scope for this design doc); any script consuming the documented
`result_envelope.json` and `result_ref` shapes satisfies the contract above.

## Failure isolation

Isolation is already structural in `corpus_batch.py`, at three layers:

1. **Process isolation per file.** `_run_entry_parent` spawns a brand-new
   `sys.executable` worker subprocess per file (`WORKER_REQUEST` /
   `--worker-request`), not a thread or in-process call. A native crash
   (access violation, unhandled ARX exception) inside one file's accoreconsole
   invocation cannot corrupt the parent process's state or any other file's
   run.
2. **Timeout + tree-kill.** `--timeout-sec` (default 240s) bounds each
   file's worker. On expiry, `_kill_process_tree` runs
   `taskkill /F /T /PID <pid>` (Windows) to kill the *entire* process tree —
   not just the Python worker, but any accoreconsole child it spawned — before
   recording a terminal `status=timeout` envelope and moving to the next
   file. A hung accoreconsole instance cannot stall the batch past its
   configured timeout.
3. **Incremental persistence survives partial failure.** `ops_run` is
   appended to and re-persisted after every op, not just at file end. If a
   worker times out mid-op-3, ops 1–2's records are recovered from the
   on-disk partial `result_envelope.json` and folded into the terminal
   timeout envelope (`_run_entry_parent`'s timeout branch reads back
   `partial.get("ops_run")`) — a timeout on op 3 does not discard evidence
   already gathered for ops 1–2.

At the batch level, `run_batch`'s `for entry in entries` loop has no
`try/except` around `_run_entry_parent` — by design, `_run_entry_parent`
itself never raises (every code path returns a `dict`); a single file's
failure is a data value (a `status=failed` envelope), not a control-flow
exception, so it cannot abort the loop. All 414 files are attempted
regardless of how many precede them fail. There are no silent drops:
`summary.json`'s `result_files` list has one entry per resolved input,
always.

## Limits

Stated plainly, with the one real measured data point this repo has, and no
invented numbers:

- **Serial throughput, one instance.** `run_batch`'s file loop
  (`for entry in entries: ... payload = _run_entry_parent(...)`) is strictly
  sequential — no thread pool, no multiprocessing pool, no concurrent worker
  dispatch. Only one accoreconsole instance runs at a time from this tool as
  written. A 414-file run is bounded below by
  `414 * (seconds for 3 ops on the slowest file in the corpus)`; there is no
  parallelism to shorten that with `corpus_batch.py` alone.
- **Wall-clock estimate — genuinely an estimate, not a benchmark.** This
  repo's closest real accoreconsole timing evidence is
  `reports/batch_latest.md`'s `golden_staging_dwg_readonly_inspect` case:
  **12,965.086 ms (~13.0s)** for a single inspect+validate pass over one DWG.
  That is one op, not three, and on one specific fixture, not this corpus.
  Scaling naively (×3 ops, ignoring per-op fixed accoreconsole startup cost
  which likely does not scale linearly) gives a floor estimate around
  **~40s/file → ~4.6 hours for 414 files**. This repo's own fixtures range
  from 21,747 to 291,706 modelspace entities
  (`reports/performance_latest.md`) — entity-count-heavy files in a real
  414-file corpus could run substantially longer per op, and there is no
  batch-level empirical baseline for `corpus_batch.py` specifically in this
  repo today (no prior `runs/corpus_batch_*` run exists in this worktree).
  **Do not schedule or promise a full-run completion time from this number
  alone** — run the 10-file calibration sub-batch (Operator commands, step 1)
  first and recompute the estimate from `summary.json.total_elapsed_sec / 10`
  before committing to a wall-clock window for the full 414.
- **Per-file timeout ceiling.** `--timeout-sec 240` (the default) caps any
  single file's worst case at 4 minutes before it is killed and marked
  `timeout`. Worst-case upper bound if every file in the corpus pathologically
  times out: `414 * 240s ≈ 27.6 hours`. This is a safety ceiling, not an
  expected outcome — most files should resolve well under it per the
  estimate above.
- **Read-only op set is a deliberate limit, not a gap.** This plan runs only
  the default `inspect.*` ops. It does not attempt `write.*`/`patch.*`
  operations, geometry diffing, or visual comparison — those are out of
  scope for a corpus-wide read sweep and would each multiply the per-file
  cost above.
- **No fake success.** Any aggregation number this plan's later
  implementation reports must trace back to a real `result_envelope.json` /
  `result_ref` value. A file that could not be read (`unreadable`,
  `password_or_proxy`, `extraction-crash`, `timeout`) contributes to the
  anomaly tally, never to the entity-type histogram or layer counts as if it
  had succeeded.
