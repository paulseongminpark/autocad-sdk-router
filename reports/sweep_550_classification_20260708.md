# 550-Op Registry / 488-Op Live Reachability Sweep — Classification Report

**Date:** 2026-07-08
**Source of truth (recomputed, not copied):** `runs\sweep_20260707\reachable_matrix_merged.jsonl` (488 lines, one JSON object per line, sorted by `op_id`)
**Registry:** `config\operations.v2.json` — 550 total ops = 488 `status:implemented` + 62 `status:blocked`. This sweep covers **all 488 implemented ops**; the 62 `blocked` ops are policy-refused pre-dispatch and are out of scope for a live reachability probe (they never reach the native dispatcher).

All numbers below were recomputed directly from the merged matrix file with a Python one-off (`json.loads` per line, `collections.Counter` on the `class` field, encoding `utf-8-sig`), not transcribed from any prior report.

---

## 1. Headline

| Metric | Value |
|---|---|
| Total ops probed | **488** |
| `classification_source` | `live_probe` on **488/488** rows (100% — no `pending`/`plan`-only rows in the merged file) |
| Unique `op_id` values | 488 (no duplicates) |
| File sorted by `op_id` | Yes (verified `op_ids == sorted(op_ids)`) |

| Class | Count | Share |
|---|---:|---:|
| RUNNABLE | 270 | 55.3% |
| REACHABLE | 171 | 35.0% |
| RUNNABLE_BUT_DEGENERATE | 30 | 6.1% |
| ATTENDED_ONLY | 15 | 3.1% |
| CRASH | 2 | 0.4% |
| **Total** | **488** | **100.0%** |

Class definitions (verbatim from `tools\probe_reachability.py`, the classifier that produced every row — see `classify_probe_response()` / `classify_op_result()`, lines ~340-459):

- **RUNNABLE** — a deliberately-authored valid-arg fixture created a real, non-degenerate result.
- **REACHABLE** — the native dispatcher responded with a structured arg/precondition error (`MISSING_ARG` et al.) — reachable, zero roundtrip value on its own.
- **RUNNABLE_BUT_DEGENERATE** — the op "succeeds" (`created:true`) on empty/underspecified args — input-unvalidated; never trusted as RUNNABLE until it either arg-validates or passes a non-degeneracy assertion.
- **ATTENDED_ONLY** — the probe timed out (60s outer budget). **Caveat (post-sweep triage, see `crash_triage_20260707.md`):** all 15 ATTENDED_ONLY rows are assessed as *possible false positives* — the 60s budget covers BOTH probe legs (empty-arg + valid-arg) while the accoreconsole cold-start floor on this machine is ~50s/leg, and structurally only 5 registry ops (`execution_host_class==full_autocad`) can even route to an attended session, none of which are among these 15. Treat ATTENDED_ONLY here as "timed out under a starved budget", not proven attendedness; a re-probe at `--timeout-sec 180` is the settling experiment.
- **CRASH** — the isolated probe subprocess died abnormally, or the native job produced no parseable result (the engine died mid-run).

---

## 2. Method

- **Tool:** `tools\probe_reachability.py --live`, which calls `cad_run_operation` for real (as opposed to its `--plan` mode, which only emits registry-derived facts with no CAD runtime touched).
- **Isolation:** every op's probe (empty-arg control probe, plus a valid-arg probe where a fixture has been authored) runs in its **own isolated child process** (`_spawn_worker` / `_run_isolated`) — one hard crash or hang can never poison the sweep or its exit code, and a hung/interactive op is killed on a bounded timeout instead of stalling the whole matrix.
- **Timeout:** the sweep was run with a **60-second** per-op timeout (confirmed from the live artifacts — every `ATTENDED_ONLY` reason string reads `"probe exceeded 60.0s (no headless UI to answer it)"`; the script's own hard-coded default, `DEFAULT_TIMEOUT_SEC`, is 120.0s, so this run explicitly passed `--timeout-sec 60`).
- **Fixture:** `tests\fixtures\native_sample.dwg` (the script's `DEFAULT_DWG`). Each probe stages a fresh copy of this DWG per op; `original_sha256_before`/`original_sha256_after`/`staged_copy_matches_original`/`original_unchanged` fields are recorded per probe artifact. **The original DWG fixture was never touched** — per-op `original_unchanged: true` was directly observed on every artifact opened during verification (see §4), and no probe ever calls `SAVE` against the original.
- **Two-run structure (parent-process death at op 70):** the sweep died partway through and was restarted, then merged:
  - **Part 1** — `runs\sweep_20260707\reachable_matrix.jsonl` — **70 rows**, all `classification_source: live_probe`. These are the first 70 ops probed before the parent process died.
  - **Part 2** — `runs\sweep_20260707\reachable_matrix_part2.jsonl` — **488 rows total**, but only **418** carry `classification_source: live_probe` (per `runs\sweep_20260707\sweep2_log.txt`: `by_classification_source: {"pending": 70, "live_probe": 418}`); the other 70 are `class: null` placeholders standing in for the ops part 1 already covered.
  - **Merged** — `runs\sweep_20260707\reachable_matrix_merged.jsonl` — the union: part 1's 70 real probes + part 2's 418 real probes = **488 distinct `op_id` rows**, all `live_probe`. No op is double-counted (verified: 488 unique `op_id`s).
  - **Work-dir footnote (minor, does not affect the 488 count):** `runs\sweep_20260707\work\` (part 1) contains **71** per-op directories, one more than part 1's 70 rows — the extra directory, `inspect_edge_curve_as_nurb`, has a complete `probe_result.json` (status `error`/`MISSING_ARG`) but its op was **not** in part 1's 70-row output; it was the op in flight when the parent process died. `inspect.edge.curve_as_nurb`'s authoritative row in the merged matrix (class `REACHABLE`) instead comes from its clean part-2 re-probe (`runs\sweep_20260707\work2\inspect_edge_curve_as_nurb\`), and the two independent probes agree (`MISSING_ARG` → `REACHABLE`) on the same result. `runs\sweep_20260707\work2\` (part 2) contains 418 directories, matching part 2's 418 live rows exactly.

---

## 3. Verification — 16-shard artifact audit

Sixteen independent shards partitioned the 488-row merged matrix (15 shards of 31 rows + 1 shard of 23 rows = 488) and, for each row, opened the corresponding `probe_result.json` under `work\<name>\` or `work2\<name>\` and confirmed the recorded `class` matches `classify_probe_response()`'s output on that artifact, and that the sha256/`original_unchanged` fields are present and consistent.

| Shard | Checked | Clean | Notes |
|---|---:|---:|---|
| 1 | 31 | 31 | — |
| 2 | 31 | 31 | — |
| 3 | 31 | 31 | — |
| 4 | 31 | 31 | — |
| 5 | 31 | **30** | 1 anomaly — see §4 (`extend.customobject.create`) |
| 6 (rows [155,186)) | 31 | 31 | Class distribution `{RUNNABLE:31}`. All 31 op_ids resolved to `work2\<name>\probe_result.json`. Every `empty_env` showed `executed=true, status='ok', exit_code=0`, matching `classify_probe_response()` (`status=='ok'`, no `result.created==True` → RUNNABLE). sha fields (`original_sha256_before==original_sha256_after`, `staged_copy_matches_original=true`, `original_unchanged=true`, `staged_copy_unchanged=true`) verified present and consistent on every row. Confirmed against classifier source directly that RUNNABLE for `input.get.*` ops despite `result.attended_editor_required=true` is by-design — that field is not consulted by `classify_probe_response`; only `_probe_crash`/`_probe_timeout`/`status`/`result.created` are. |
| 7 (rows [186,217)) | 31 | 31 | Class distribution `{RUNNABLE:13, REACHABLE:18}`. |
| 8 | 31 | 31 | — |
| 9 | 31 | 31 | — |
| 10 | 31 | 31 | — |
| 11 | 31 | 31 | — |
| 12 | 31 | 31 | — |
| 13 | 31 | 31 | — |
| 14 | 31 | 31 | — |
| 15 (rows [434,465)) | 31 | 31 | Class distribution `{RUNNABLE:6, REACHABLE:12, RUNNABLE_BUT_DEGENERATE:13}`. |
| 16 | 23 | 23 | — |
| **Total** | **488** | **487** | **1 anomaly found, in shard 5** |

**487/488 rows (99.8%) verified clean against their probe artifacts.**

---

## 4. Anomalies

Exactly **one** anomaly survived the 16-shard audit (reported verbatim from the shard finding):

### `extend.customobject.create` — broken artifact (severity: `broken_artifact`)

- Work dir `runs\sweep_20260707\work\extend_customobject_create` exists but contains **no `probe_result.json`** (only `empty\stdout.txt` [4443 bytes], `empty\stderr.txt` [empty], `valid\job_args.json`). The standard probe artifact needed to directly confirm the recorded class (`ATTENDED_ONLY`) or check sha fields is not present.
- **Corroborating-but-unverifiable evidence:** the merged matrix row's own `empty_arg_probe.reason` field reads `"probe exceeded 60.0s (no headless UI to answer it)"` (`probed_at: 2026-07-07T07:13:24Z`); `empty\stdout.txt` (mtime 16:13:01 local, ~23s earlier) contains a fully-formed `ariadne.autocad_router_run.v2` JSON showing `engine_exit_code=0, status=ok, created=true` — i.e., the `accoreconsole` engine appears to have produced a complete result before the wrapper/process failed to return within the 60s probe budget, which is plausible for an attended-exit dialog.
- **This cannot be confirmed** against a standard `probe_result.json` envelope, and **no sha256 fields appear anywhere** in the fallback artifacts, so original-file-unchanged cannot be verified for this op from work-dir evidence alone (it can only be inferred from the sweep-wide guarantee that `_run_isolated` never lets a probe subprocess mutate the shared original — see §2).
- **Net effect on the headline numbers:** none. The row's recorded class (`ATTENDED_ONLY`) is internally consistent with the merged matrix's own `empty_arg_probe.reason`, and it is one of the 15 `ATTENDED_ONLY` rows already counted in §1. The anomaly is an audit-trail gap (missing canonical artifact), not evidence that the class is wrong.

No other anomalies were found. The 16-shard artifact audit found no discrepancies on the remaining 487 rows.

---

## 5. Comparison vs. wave-6 (`crash34_host_eligibility_crosscheck`)

The prior live-reachability pass (`measure\reachable_matrix.jsonl`, **465** ops — a smaller, earlier registry snapshot, not the current 488) recorded **34 CRASH** rows. `reports\crash34_host_eligibility_crosscheck.md` cross-checked all 34 against a router fix and found:

- **33 → `resolved_by_router_fix`** — Lane I's fix to the router's `live_edit` dispatch bug (`tools\autocad-router.ps1`, commit `b3f456d`) made these ops re-classify as RUNNABLE/REACHABLE/RUNNABLE_BUT_DEGENERATE on re-probe; they were CRASH only as an artifact of the *old, pre-fix* router.
- **1 → `expected_crash`** — `live.jig.point_probe`: the registry's own summary/notes already document that CoreConsole cannot execute this op; a durable, expected crash, not an open question.

**Caveat carried forward from commit `a1fedc6`** ("registry policy hygiene: embedded policy blocks now mirror top-level status"): that commit's message states explicitly that *"the wave-6 crash34_host_crosscheck expected/anomalous split was computed against the stale annotations; the live 550-op sweep supersedes it."* At the time crash34 ran, 416/550 rows' embedded `policy.status_policy` blocks had drifted out of sync with the registry's real top-level `status` (fixed by `tools\policy_hygiene.py` in that same commit). So the wave-6 33/1 resolved/expected split should be read as a **historical** cross-check against a since-corrected registry snapshot, not as independently re-validated ground truth for the current sweep.

**This sweep (2026-07-07/08, 488 ops, live):**

- **CRASH: 2** — down from wave-6's 34.
  - `live.jig.point_probe` — still CRASH. Consistent with wave-6's own `expected_crash` verdict for this op (durable, documented CoreConsole limitation, not a regression).
  - `live.status` — CRASH in this sweep, with reason `"native job produced no parseable result JSON"`. **This is a new finding, not accounted for by the wave-6 crosscheck**: in the older 465-op matrix (`measure\reachable_matrix.jsonl`), `live.status` was classified **REACHABLE**, not CRASH, and it was not among wave-6's 34 CRASH rows at all. This op's status therefore regressed (REACHABLE → CRASH) between the two sweeps and was not resolved by the `b3f456d` router fix that cleared the other 33 wave-6 CRASH rows. It should be triaged separately — this report does not investigate the root cause, only flags the discrepancy honestly.
- Net: 33 of wave-6's 34 CRASH rows are gone (32 confirmed as router-bug artifacts already fixed pre-sweep, 1 — `live.jig.point_probe` — remains an expected crash, both under the a1fedc6 caveat above), and this sweep surfaces one CRASH (`live.status`) that wave-6's matrix did not have flagged as CRASH.

---

## 6. Reproduce

```powershell
# Re-run the full 488-op live sweep (long — one isolated subprocess per op, 60s timeout each):
python tools\probe_reachability.py --live --dwg tests\fixtures\native_sample.dwg `
  --timeout-sec 60 --out runs\sweep_<new_stamp>\reachable_matrix.jsonl

# Recompute the headline class distribution from the existing merged matrix (no CAD runtime needed):
python -c "
import json, collections
with open(r'runs\sweep_20260707\reachable_matrix_merged.jsonl', encoding='utf-8-sig') as f:
    rows = [json.loads(l) for l in f if l.strip()]
print('total:', len(rows))
print(collections.Counter(r['class'] for r in rows))
print('classification_source:', collections.Counter(r.get('classification_source') for r in rows))
"

# Router-level live status/select/run entrypoint (engine-level fallback, not the probe harness):
& 'D:\dev\99_tools\autocad-sdk-router\tools\autocad-router.ps1' -Action status
```

**Inputs used for this report** (read-only, none modified):

- `runs\sweep_20260707\reachable_matrix_merged.jsonl` — 488-row merged matrix (headline + §5 comparison)
- `runs\sweep_20260707\reachable_matrix.jsonl` — part 1, 70 rows (§2 method)
- `runs\sweep_20260707\reachable_matrix_part2.jsonl` — part 2, 488 rows / 418 `live_probe` (§2 method)
- `runs\sweep_20260707\sweep2_log.txt` — part-2 run summary (§2 method)
- `runs\sweep_20260707\work\` / `runs\sweep_20260707\work2\` — per-op probe artifacts (§2 footnote, §3 verification, §4 anomaly)
- `tools\probe_reachability.py` — classifier source (§1 definitions, §2 method, §3 shard-6 note)
- `config\operations.v2.json` — registry (550 = 488 implemented + 62 blocked)
- `measure\reachable_matrix.jsonl` — wave-6, 465-op matrix (§5 comparison baseline)
- `reports\crash34_host_eligibility_crosscheck.md` — wave-6 crash cross-check (§5 comparison)
- commit `a1fedc61e55021e9c6e5d4938352cc77f446f8e6` — policy-annotation hygiene fix + staleness caveat (§5 comparison)
- 16-shard verification results supplied by the overnight verification pass (§3, §4 — quoted verbatim where the shard included prose notes; shards without notes are reported as checked/clean counts only)
