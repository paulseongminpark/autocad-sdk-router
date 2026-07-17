# E1.5 run state (disk-first, octorun discipline)

Updated: 2026-07-17 (fleet launch)

## Prereg

- Sealed at commit a78eeaa (`prereg_e15.json`) BEFORE any binding run.
- Canary (shard_01 × 5 live judges) quarantined under `raw_canary/` — excluded from analysis.
- Canary verdict: harness viable. Defects found and countermeasured:
  - grok45: prepends prose → harvest uses bracket extraction (recovered 20/20 rationale-complete).
  - sonnet5 oneshot: missing closing brace mid-array → sonnet switched to AGENTIC mode with self-validation loop.
  - sol56, opus48, fable5: clean on first try.

## Waves in flight

| wave | surface | packets | state |
|---|---|---|---|
| opus48_max + fable5_high (20 shards each) | Workflow wf_b5d4057b-ae0 (session task wmf0n09x9) | 40 agents | RUNNING |
| sol56_xhigh ×20 + grok45_xhigh ×20 (oneshot) | octoloop LOOP-20260717091358-53w0jz | 40 packets | **DONE — harvested 40/40, failed 0** (grok 19/20 needed bracket extraction; sol 20/20 direct) |
| sonnet5_xhigh ×20 (agentic) | octoloop loop_run re-fire (session task kcx2zei5m) | 20 packets | RUNNING |

Incident: first 60-packet call REFUSED the agentic packets (INV-14 default-closed — agentic requires a declared `files` fileset); the 40 oneshot packets executed and sealed receipts anyway. Sonnet re-fired with per-packet `files` declarations. Nothing double-ran.

- Liveness fact (payload-truth): files appearing under `reports/e1/annot_v1/raw/<judge>/shard_NN.json` (opus/fable/sonnet write directly; sol/grok harvested from octoloop runDir receipts via `tools/e15_harvest_lane.py`).
- Terminal-state vocabulary applies: any judge below the B3 gate after one re-run is PARTIAL, never silently dropped.

## Next obligations

1. On loop_run completion: `python tools/e15_harvest_lane.py --run-dir <runDir>` → re-run failed shards once (B3).
2. On Workflow completion: validate raw/opus48_max + raw/fable5_high file counts (20 each).
3. `python tools/e15_collect.py` → calibration_v1.{json,md} + e15_evidence.xlsx → report with prereg verdicts.
4. LYKEION panel 20260717_wall-detector-methodology: Phase A claude seats may start anytime; codex/grok seats AFTER E1.5 lanes drain (starvation guard).
