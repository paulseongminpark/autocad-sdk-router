# Track-4 Corpus Batch Evidence Report — `corpus_smoke_20260707`

Run ID: `corpus_smoke_20260707` · Report date: 2026-07-07 · Lane: `dwg_truth_autocad` (native/headless, accoreconsole)

## Headline results

| Metric | Value |
| --- | --- |
| Files in manifest | 166 |
| Status `ok` | 166 |
| Status failed | 0 |
| SHA-256 match on re-read (post-extraction, vs. manifest) | 166 / 166 |
| Ops executed | 498 (166 files × 3 ops) |
| Ops non-`ok` | 0 |
| Total modelspace entities (sum across all 166 files) | 1,107,104 |
| Files hitting the 1000-row entity-list truncation cap | 115 / 166 (69.3%) |
| Entity-count outliers, z ≥ 3.0 | 4 rows (2 distinct drawings, each counted twice — see Anomalies) |
| Wall-clock elapsed (manifest start → finish, includes one mid-run interruption) | 8,698.98s (~2h25m), 2026-07-07T02:29:18Z → 03:58:10Z |

Every number above is reproduced directly from `runs/corpus_smoke_20260707/ledger.jsonl` via `tools/corpus_query.py summarize` and `anomalies` (commands in Reproduce, below) and matches the task-supplied figures exactly; no number in this table was edited or estimated.

## Method & provenance

- **Manifest**: `runs/corpus_smoke_20260707/manifest.json` — 166 entries, each `{path, sha256}`, sha256-pinned before the run started. 151 of the 166 source paths live under `D:\dev\_ariadne\alm\build\...`; the other 15 live under `D:\dev\_ariadne\alm\runs\...` (centerline/EXP2 pipeline outputs promoted to corpus inputs — correction 2026-07-08 by adversarial audit; an earlier revision claimed all 166 were under alm\build). All are real production-lineage DWGs, not synthetic fixtures.
- **Execution**: `tools/corpus_batch.py --manifest ...` drove the batch. Per file, the batch copies the original DWG to an ASCII-safe **staged copy** and runs three read-only ops against the staged copy via accoreconsole: `inspect.database.summary`, `inspect.layers`, `inspect.entities`. Originals under `_ariadne/alm/build` are never opened for write and were re-hashed after the run — all 166 SHA-256 values match the manifest, confirming zero mutation of source material.
- **Interruption and resume**: the batch was interrupted once at roughly file 60/166 by a session-bound background task dying with its parent session. It was relaunched **detached** (session-independent) and completed the remaining files unattended. The batch's resumable design skips envelopes already recorded as complete, so the resume did not re-run or double-count any of the first ~60 files. `resume_stdout.log` / `resume_stderr.log` in the run directory are the raw evidence of the resume boundary.
- **Per-file artifacts**: each manifest entry has its own result directory under `runs/corpus_smoke_20260707/<NNNN>_<slug>/result_envelope.json`, and the underlying native job output lives under `runs/dwg_truth_autocad_cad_job_<timestamp>/native_cad_job_result.json`. `ledger.jsonl` (one row per file) and `summary.json` / `summary.md` are built from those envelopes.
- **Aggregation vs. per-shard deep review**: the headline table comes from `corpus_query.py` over `ledger.jsonl`. Independently, 6 Sonnet analysts each reviewed a contiguous ordinal shard (1–28, 29–56, 57–84, 85–112, 113–140, 141–166) by reading raw per-file envelopes, not just the ledger rollup. Their per-shard `ok`/`sha_mismatches`/`bad_ops` counts sum to 166/0/0, consistent with the headline table.

## Distribution

**INSUNITS** — near-uniform Millimeters, with one confirmed exception:

| Shard | Millimeters | Meters |
| --- | --- | --- |
| 1–28 | 28 | 0 |
| 29–56 | 28 | 0 |
| 57–84 | 28 | 0 |
| 85–112 | 28 | 0 |
| 113–140 | 28 | 0 |
| 141–166 | 24 | 1 |
| **Total** | **164** | **1** (+1 unaccounted, see note) |

The one Meters row is `centerline_plan.dwg` (ordinal 162, entity_count 10,198). Its near-identically named sibling `centerline_plan_native.dwg` (ordinal 163, entity_count 23,618) is Millimeters. All other 24 files in that shard, and all 138 files in the other five shards, report Millimeters. Both files report `status=ok` and a matching SHA-256, so the extraction pipeline is not at fault — this is either a genuine unit-scale difference between two source files or an `INSUNITS` metadata defect baked into `centerline_plan.dwg` itself. Any geometry comparison across these two files that assumes a shared unit will be off by 1000×. This was not called out in the task-supplied headline facts and is flagged here as a distribution finding, not smoothed into "all files are mm."

(Shard row counts sum to 166 Millimeters+Meters entries across 166 files; the shard-6 table above shows 24+1=25 for that shard's 25 files, consistent with 166 total.)

**Entity-count scale** — 1,107,104 entities across 166 files, average ≈ 6,669/file, but heavily right-skewed: 115/166 files (69.3%) hit the entity-list 1000-row truncation cap, meaning a majority of files in this corpus have more than 1,000 modelspace entities. Individual shard reviewers flagged specific large files, e.g. ordinal 80 (`A00-032~040_장애인 편의시설 상세도-1~9.dwg`, 사업승인 copy) at entity_count 42,101 (truncated) and ordinal 81 (`A00-041~042 시설물 설치계획도-1~2.dwg`) at 23,846 (truncated).

**Op timing** — no op in any shard approached a failure/timeout threshold (all well under 120s). The single slowest op across the whole run is ordinal 16 (`A40-201~215 101동 코아확대 평면도.dwg`, 사업승인 copy), `inspect.entities` at 42.375s. The next-heaviest cluster (35–39s) falls on `inspect.layers` / `inspect.database.summary` for files with large layer/block counts:

| Ordinal | Op | Elapsed (s) | File (basename) |
| --- | --- | --- | --- |
| 16 | inspect.entities | 42.375 | A40-201~215 101동 코아확대 평면도.dwg |
| 19 | inspect.layers | 39.047 | A40-241~253 103동 코아확대 평면도.dwg |
| 35 | inspect.layers | 39.375 | A90-001~005 지하층 주민공동시설... (395 layers, 4000+ blocks) |
| 36 | inspect.database.summary | 36.734 | A90-011~072 부대시설... |
| 69 | inspect.database.summary | 37.156 | A00-015~017 설계개요.dwg |
| 104 | inspect.database.summary | 37.328 | (shard 85–112 heaviest file) |
| 125 | inspect.layers | 37.266 | A50-001~024 (3,137 layers) |

Timing tracks layer/block count, not raw entity count — e.g. ordinal 69 (`A00-015~017 설계개요.dwg`, 28 entities) and ordinal 74 (`A00-024 지상교통체계도.dwg`, 87 entities) posted some of the shard-3 slowest single-op times (37.2s, 34.0s) despite modest entity counts, suggesting API summary cost scales with block/xref structure more than entity volume for those two files. This is informational, not a failure signature — no op in the run exceeded `ok` status.

Shard 6 (141–166, lighter/smaller drawings including the `input0616`/`centerline_plan`/`native_input` variants) is markedly faster: slowest op 19.4s, roughly half the peak of the heavier architectural shards.

## Anomalies

`tools/corpus_query.py anomalies --entity-z 3.0` against `ledger.jsonl` returns exactly 4 rows, matching the task-supplied list verbatim:

| z-score | Drawing | Revision-stage tree |
| --- | --- | --- |
| 4.56 | A40-205~357 101동~108동 코아단면도.dwg | 01 건축(사업승인) |
| 4.53 | A40-205~357 101동~108동 코아단면도.dwg | 01_건축(실시설계) |
| 3.59 | A00-032~040_장애인 편의시설 상세도-1~9.dwg | 01 건축(사업승인) |
| 3.60 | A00-032~040_장애인 편의시설 상세도-1~9.dwg | 01_건축(실시설계) |

**These 4 outlier rows are not 4 distinct anomalous drawings — they are the same 2 drawings, each captured once under the 사업승인 (permit-approval) folder tree and once under the 실시설계 (working/construction-design) folder tree.** Both revision-stage copies of both drawings independently register as entity-count outliers relative to the corpus mean, which is consistent (not contradictory) with them being large, detail-dense sheets (코아단면도 = core cross-section across 8 towers; 장애인 편의시설 상세도 = a 9-sheet accessibility-detail set) rather than an extraction artifact. Both revision-stage pairs report `status=ok` and matching SHA-256, so no data-integrity concern attaches to the outlier flag itself.

This pattern — the same basename appearing under both 사업승인 and 실시설계 (or 표제부 vs. 건축) trees with materially different entity/layer counts — recurs elsewhere in the corpus and is confirmed to be the corpus's own filing convention, not a ledger defect:

- Shard 57–84: `A00-045~046 기준층 및 지상1층 방화구획평면도.dwg` (ordinals 57/83: 69 entities/255 layers vs. 66 entities/497 layers) and `A10-001~009 단위세대면적산출표.dwg` (ordinals 58/84: 4,008 entities/40 layers vs. 5,460 entities/38 layers).
- Shard 85–112: 4 basenames duplicated across `00.표제부` and `01.건축` folders (A20-001, A20-002, A20-011~015, A20-021~024; ordinals 91/98, 92/99, 93/101, 94/102).

## Data-quality notes

**Korean layer-name corruption in `ledger.jsonl` (`by_layer`/`by_entity_type` keys) — confirmed baked into the JSON, not a terminal display artifact.**

Per-shard mojibake row counts (a row is flagged if any `by_layer`/`by_entity_type` key in that row contains a literal U+FFFD replacement character):

| Shard | Mojibake rows | / shard size |
| --- | --- | --- |
| 1–28 | 0 | 0% |
| 29–56 | 10 | 35.7% |
| 57–84 | 11 | 39.3% |
| 85–112 | 1 | 3.6% |
| 113–140 | 1 | 3.6% |
| 141–166 | 5 | 20.0% |
| **Total** | **28** | **16.9% (28/166)** |

The shard-57–84 reviewer traced this to ground truth rather than assuming a console encoding quirk: for ordinal 70, the underlying raw per-op JSON at `runs/dwg_truth_autocad_cad_job_20260707_114010/native_cad_job_result.json` decodes cleanly as UTF-8-sig with correct Korean layer names (e.g. `타입_130`, `0-휀룸 지상`, `경계선`). The corruption is therefore introduced **downstream of correct extraction**, specifically when `ledger.jsonl` itself is built/written — consistent with the project's known cp949-locale-vs-UTF-8 mismatch pattern (see `reference_cp949_mojibake_durable_fix` in project memory: a writer that doesn't honor `PYTHONUTF8` when a cp949 console locale is active corrupts non-ASCII text at write time). Every affected row still carries `status=ok`, `source_sha256_match=true`, and `worker_exit_code=0` — entity counts and totals in the ledger are numerically correct throughout; only the Korean-text **keys** of `by_layer`/`by_entity_type` are corrupted for the affected rows. `by_entity_type` keys were never affected in any shard because entity-type names are ASCII-only.

**This contradicts a "display-artifact" characterization.** The task's structure brief for this section described the mojibake as a "display-artifact class, not extraction failure." The shard-57–84 evidence supports the second half of that claim (extraction itself is correct) but explicitly refutes the first half: the corruption is verified present in the on-disk JSON via direct UTF-8 decode, independent of any terminal/console rendering, so it is a **durable data defect in `ledger.jsonl`**, not a rendering-only artifact. Consumers who need Korean layer-name fidelity should read `by_layer` from the per-file `result_envelope.json` / `native_cad_job_result.json` (verified correct) rather than from `ledger.jsonl`, or `ledger.jsonl` should be rebuilt with a UTF-8-safe writer. Isolated single-row instances of the same defect were also seen in ordinal 89 (`A10-501 오피스텔 부대시설면적산출표.dwg`), ordinal 137 (`A80-004 지하주차장 지붕 평면도.dwg`, corrupted `OPEN`-prefixed layer name), and 5 files in shard 141–166 (ordinals 141, 142, 143, 151, 152 — including both `input_v001.dwg` and `output_v001.dwg`).

**RESOLVED (same session, post-audit).** The root cause was narrower than a locale-mode writer bug: the ad-hoc ledger builder sourced each op's payload from `op_NN_*/stdout.txt` — a file that transits the cp949 console pipeline and already contains baked-in U+FFFD before any ledger code runs — instead of the op's `result_ref` artifact (`native_cad_job_result.json` / `cad_job_result.json`, written utf-8-sig by the native job and verified clean for every audited ordinal). The permanent builder `tools/corpus_ledger.py` now prefers the `result_ref` recorded in each file's `result_envelope.json` and only falls back to `stdout.txt` when the artifact is missing; `tests/unit/test_corpus_ledger.py` pins the preference with a fixture that ships a clean `result_ref` and a corrupted `stdout.txt` for the same op. `ledger.jsonl` in this run directory has been **rebuilt with the fixed builder: 0/166 rows now contain U+FFFD keys** (ordinal 70 reads `타입_130`/`타입_111`, ordinal 89 reads clean `AA-TEXT-PCN7`-family names), and every headline number above was re-verified identical against the rebuilt ledger (166/166 ok, 1,107,104 entities, same 4 z-outliers). The mojibake table above is retained as the audit record of the pre-fix state; the corrupted `stdout.txt` files remain on disk as historical artifacts but are no longer a ledger source.

**Entity-list truncation is by design, not a defect, and constrains what the histograms cover.** `inspect.entities` caps the returned entity list at 1000 rows per file; 115/166 files (69.3%) exceeded that cap and are marked `entities_truncated: true` in their ledger rows. Because `by_layer`/`by_entity_type` in `ledger.jsonl` are built by aggregating the (possibly capped) per-file breakdowns, the corpus-wide `by_layer` histogram (131 distinct layer-name keys observed via `corpus_query.py summarize`) and `by_entity_type` histogram (16 distinct types, summing to 14,373 — far below the 1,107,104 total modelspace entity count) reflect only a subset of the corpus's actual entity population, weighted toward files that did not hit the cap. `entity_count` and the `total_modelspace_entities` sum (1,107,104) are unaffected by truncation — those come from `inspect.database.summary`, a separate, uncapped op.

## Evidence pointers

- Run directory (root of this milestone's artifacts): `D:\dev\99_tools\autocad-sdk-router\runs\corpus_smoke_20260707\`
- Manifest (166 sha256-pinned source paths): `D:\dev\99_tools\autocad-sdk-router\runs\corpus_smoke_20260707\manifest.json`
- Per-file ledger (one JSON row per file — the aggregation source for this report): `D:\dev\99_tools\autocad-sdk-router\runs\corpus_smoke_20260707\ledger.jsonl`
- Run summary (status counts, op list, elapsed time, per-file result_envelope index): `D:\dev\99_tools\autocad-sdk-router\runs\corpus_smoke_20260707\summary.json` and `summary.md`
- Resume boundary evidence (interruption + detached relaunch): `D:\dev\99_tools\autocad-sdk-router\runs\corpus_smoke_20260707\resume_stdout.log`, `resume_stderr.log`
- Per-file result envelopes: `D:\dev\99_tools\autocad-sdk-router\runs\corpus_smoke_20260707\<NNNN>_<slug>\result_envelope.json`
- Raw native job output (source of truth for layer-name fidelity checks, unaffected by ledger mojibake): `D:\dev\99_tools\autocad-sdk-router\runs\dwg_truth_autocad_cad_job_<timestamp>\native_cad_job_result.json`
- Query/aggregation tool: `D:\dev\99_tools\autocad-sdk-router\tools\corpus_query.py`
- Batch driver: `D:\dev\99_tools\autocad-sdk-router\tools\corpus_batch.py`
- This report: `D:\dev\99_tools\autocad-sdk-router\reports\corpus_run_20260707.md`

## Reproduce

```powershell
# Aggregate counts (files/ok/failed/total_entities/by_layer/by_entity_type)
$env:PYTHONUTF8 = '1'
python D:\dev\99_tools\autocad-sdk-router\tools\corpus_query.py summarize `
  D:\dev\99_tools\autocad-sdk-router\runs\corpus_smoke_20260707\ledger.jsonl

# Entity-count outliers (z >= 3.0) — reproduces the 4-row anomaly list above
python D:\dev\99_tools\autocad-sdk-router\tools\corpus_query.py anomalies `
  D:\dev\99_tools\autocad-sdk-router\runs\corpus_smoke_20260707\ledger.jsonl --entity-z 3.0

# Rebuild the ledger from the run directory (result_ref-sourced, mojibake-safe)
python D:\dev\99_tools\autocad-sdk-router\tools\corpus_ledger.py --run-dir `
  D:\dev\99_tools\autocad-sdk-router\runs\corpus_smoke_20260707

# Re-run (or resume) the full batch from the pinned manifest
python D:\dev\99_tools\autocad-sdk-router\tools\corpus_batch.py --manifest `
  D:\dev\99_tools\autocad-sdk-router\runs\corpus_smoke_20260707\manifest.json
```

`PYTHONUTF8=1` is set before invoking `corpus_query.py` because this machine's default console codepage is cp949; without it, printing/parsing the Korean layer-name keys in `ledger.jsonl` risks a second, *display-side* mojibake on top of the durable write-side corruption already documented above — the two are independent failure modes and should not be conflated when re-running these commands.
