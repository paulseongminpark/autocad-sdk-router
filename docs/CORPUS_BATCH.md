# Corpus Batch Envelope

`tools/corpus_batch.py` runs a read-only, multi-DWG corpus sweep on top of the existing `cadctl` Python surface. It never opens originals for write. Every file gets its own worker process, its own run directory, and its own result envelope.

## CLI

Run from the repo root with `PYTHONUTF8=1`.

Manifest input:

```powershell
python -X utf8 tools/corpus_batch.py --manifest path\to\manifest.json
```

Glob input:

```powershell
python -X utf8 tools/corpus_batch.py --glob "D:\dev\_ariadne\alm\**\*.dwg"
```

Optional flags:

- `--out-dir <path>`: reuse an existing run directory or choose a fixed output location. Without this flag the tool writes `runs/corpus_batch_<stamp>/`.
- `--force`: ignore any existing terminal `result_envelope.json` files and rerun those inputs.
- `--timeout-sec <int>`: per-file worker timeout in seconds. On timeout the parent kills the full worker tree and records `status=timeout`.
- `--ops <op_a,op_b,...>`: override the default read op set.
- `--ops-file <path>`: JSON list of op ids or `{ "id": ..., "args": { ... } }` objects.

Default ops:

```json
[
  { "id": "inspect.database.summary", "args": {} },
  { "id": "inspect.layers", "args": {} },
  { "id": "inspect.entities", "args": {} }
]
```

Manifest rules:

- The manifest payload must be a JSON list.
- Each row must be `{ "path": "<dwg path>", "sha256": "<optional lowercase or uppercase hex>" }`.
- Relative manifest paths resolve relative to the manifest file. If that path does not exist but the same relative path exists under the repo root, the repo-root path is used.

## Run Layout

Top-level run directory:

```text
runs/
  corpus_batch_<stamp>/
    0000_<name>/
    0001_<name>/
    ...
    summary.json
    summary.md
```

Per-file directory:

```text
<idx>_<name>/
  worker_request.json
  worker_stdout.txt
  worker_stderr.txt
  source_staged.dwg
  result_envelope.json
  op_00_<op>/
  op_01_<op>/
  ...
```

Notes:

- `<idx>` is a zero-padded ordinal from the resolved input order.
- Manifest order is preserved exactly.
- Glob inputs are sorted by case-insensitive absolute path for deterministic replay.
- `source_staged.dwg` is the batch-level copy of the original. `cadctl` then makes its own internal staged copy per op, preserving the batch-level copy as a stable provenance artifact.

## Per-File Envelope

Path: `<run_dir>/<idx>_<name>/result_envelope.json`

Schema id:

```json
"schema": "ariadne.corpus_batch.result.v1"
```

Example shape:

```json
{
  "schema": "ariadne.corpus_batch.result.v1",
  "ordinal": 0,
  "source_path": "D:\\dev\\_ariadne\\alm\\build\\input0616.dwg",
  "source_sha256": "27dbf6b95ff...",
  "source_sha256_expected": null,
  "source_sha256_match": null,
  "staged_path": "runs\\corpus_batch_20260706_123456\\0000_input0616\\source_staged.dwg",
  "ops_run": [
    {
      "operation": "inspect.database.summary",
      "args": {},
      "status": "ok|partial|error|blocked|not_implemented|unavailable",
      "error_class": null,
      "reason": null,
      "elapsed_sec": 12.344,
      "result_ref": "D:\\...\\native_cad_job_result.json",
      "stdout": "runs\\...\\stdout.txt",
      "stderr": "runs\\...\\stderr.txt"
    }
  ],
  "status": "ok|failed|timeout",
  "error_class": "non-dwg|unreadable|password_or_proxy|timeout|extraction-crash|null",
  "run_dir": "runs\\corpus_batch_20260706_123456\\0000_input0616",
  "timings": {
    "started_at": "2026-07-06T08:33:23.094791+00:00",
    "finished_at": "2026-07-06T08:35:31.618135+00:00",
    "elapsed_sec": 128.531
  },
  "reason": "top-level failure summary when present",
  "worker_exit_code": 0
}
```

Contract:

- `status=ok`: every requested op finished with `status=ok`.
- `status=failed`: the file completed but at least one op or source precondition failed.
- `status=timeout`: the parent hit `--timeout-sec`, killed the worker process tree, and wrote a terminal timeout envelope.
- `ops_run` is incremental. If a worker times out on op 3, completed op records from ops 1-2 remain in the envelope.
- `source_sha256_expected` and `source_sha256_match` are populated when the manifest row includes a `sha256`.
- `worker_exit_code` is the worker Python process exit code when known.

## Error Taxonomy

Top-level `error_class` is the first terminal failure class for the file:

- `non-dwg`: the input path does not end in `.dwg`.
- `unreadable`: missing file, read failure, permission failure, or manifest sha mismatch.
- `password_or_proxy`: failure text mentions password, encryption, or proxy-object issues.
- `timeout`: the parent killed the worker tree after the configured timeout.
- `extraction-crash`: everything else that failed during extraction or native dispatch.

Every resolved input appears in `summary.json` and `summary.md`. There are no silent drops.

## Summary Files

Top-level `summary.json` schema:

```json
{
  "schema": "ariadne.corpus_batch.summary.v1",
  "started_at": "...",
  "finished_at": "...",
  "total_inputs": 5,
  "counts_by_status": { "failed": 5 },
  "counts_by_error_class": { "extraction-crash": 5 },
  "total_elapsed_sec": 642.155,
  "run_dir": "runs\\corpus_batch_20260706_123456",
  "manifest_path": ".tmp\\w6_real_corpus_manifest.json",
  "glob_pattern": null,
  "ops": [
    { "id": "inspect.database.summary", "args": {} },
    { "id": "inspect.layers", "args": {} },
    { "id": "inspect.entities", "args": {} }
  ],
  "result_files": [
    "runs\\corpus_batch_20260706_123456\\0000_input0616\\result_envelope.json"
  ]
}
```

`summary.md` contains:

- The same top-level counts as `summary.json`.
- One markdown table row per input file with ordinal, terminal status, terminal error class, elapsed seconds, and source path.

## Resume Semantics

- Resume is run-directory based. Re-run the same command with the same `--out-dir`.
- A file is skipped only when `<case_dir>/result_envelope.json` exists and its `status` is terminal: `ok`, `failed`, or `timeout`.
- `--force` clears existing per-file case directories before re-running them.

## Subprocess Model

- Parent process responsibilities: input ordering, resume/skip decisions, timeout enforcement, tree kill, and summary generation.
- Worker process responsibilities: one DWG only, source sha verification, batch-level staging copy, op execution through `cadctl.Cad.run_operation`, and incremental envelope persistence.
- `worker_stdout.txt` and `worker_stderr.txt` are file-backed on purpose. The runner does not use inherited stdout/stderr pipes for long native jobs.
