# E2 Wave 0 run state (disk-first, octorun discipline)

Updated: 2026-07-17 (launch)

## Order (Paul)

S1~S6 전부 진행, Wave 0 = S1 법의학 + S2 합성 생성기 + S3 외부셋 + S4 탐지기 모듈 + S5 배터리 골격.
Fleet: octoloop octavius CLI (fresh-config), worktree-parallel, **main aclaude quota untouched**.
Lanes: sonnet_b/c=opus x3each (sunapse/sunapse-kdw) · sonnet_d/e=opus x5each (junhyuk8987/paulparkhere)
· codex_56terra x4 · grok x5 (pool 3 — starvation precedent). Total 25 packets.

## Canary (before fleet)

- 1 packet, lane sonnet_b + env dial OCTOLOOP_SONNET_B_MODEL=opus → receipt ran_model="opus",
  worker self-identified "claude-opus-4-8", diff = exactly the declared file. **Dial VERIFIED.**
- Known nuisance: worktree cleanup can fail with Windows Permission-denied AFTER the receipt seals
  (exit 1 from octavius run) — receipts are the truth, stale .wt dirs are disk noise (gc later).
- Canary run: LOOP-20260717114809-117wq6v (not merged; canary file lives only in its diff).

## Fleet

- Packets file: reports/e2/wave0_packets.json (25; fileset-disjoint machine-checked by
  reports/e2/wave0_build_packets.py; contracts inlined per delegation rule).
- Assignment: sonnet_d=S1-A..E (forensic) · sonnet_e=S4-A..E (detector modules) ·
  sonnet_b=S2-B/C/D (generator core) · sonnet_c=S2-A/E/F (stats/pack/fidelity) ·
  codex_56terra=S3-B/C/D/E (extset parsers/features) · grok=S5-A/B/C/D + S3-A (battery + fetch tooling).
- Liveness fact (payload-truth): receipts/*.receipt.json count under the runDir printed at launch;
  per-packet diffs under evidence/. NOT the wrapper exit code (see canary nuisance above).
- Terminal vocabulary: success | clean_no_op | blocked | approval_required | exhausted | no_progress.
  Any packet below its card contract after one re-fire = reported PARTIAL, never silently dropped.

## Next obligations

1. On fleet completion: octavius collect --run <id> → verify 25 receipts, review diffs.
2. Merge eligible diffs into main (single-writer: orchestrator session), run selftests post-merge.
3. S1 verdicts (A..E) fold into reports/e2/s1/ — these gate S4 calibration and prereg sealing.
4. Real-data steps deferred by cards: extset real-data validation, staged 1.dwg DXF run of detector v1
   — orchestrator, after merge.

## HARVEST (2026-07-17, runs LOOP-20260717120806-17xckkd + refire LOOP-20260717122756-1exo0ma)

- Fleet run_finished: dispatched 25, runner-failed 0. Receipts: 20 DONE_WITH_CONCERNS + 5 BLOCKED.
- BLOCKED forensics (payload-truth): s1a/s1c/s1d = adapter misclassification (claude CLI stderr
  "no stdin data received in 3s" warning read as error; all declared files delivered — merged).
  s2c-openings = genuine no-output; s5b-transforms-struct = cursor cli-config.json rename race
  (3 simultaneous grok starts — "grok 다중동시 기아" precedent root-caused).
- Merge: 23 diffs @d6e1133 + refire 2 @aac35d0, all `git apply` clean (filesets disjoint by design).
- Spot selftests PASS 6/6: detect/cli (end-to-end), synth/grammar, synth/openings, meta/transforms_rigid,
  meta/transforms_struct, extset/fpc_parse. ezdxf 1.4.3.
- S1 verdicts (reports/e2/s1/*.json): handle_audit CLEAN · entity_census BLINDNESS_CONFIRMED
  (divergent median LINE-share 0.0 vs uniform 0.333) · bbox_units table delivered · sortkey MIXED
  (top-20 Jaccard 0.4–0.7) · censoring: ornith_v0 CAP_CENSORED, live top-tier judges NOT_CENSORED.
- Kernel observability ticket: detached-runner packet errors are returned in-memory only — never
  ledgered (first fleet's 25 instant failures left zero per-node reasons on disk).

## TERMINAL (2026-07-17)

- Fold: **success** — 25/25 cards delivered (23 first pass + 2 refire), spot selftests PASS.
- S3-A REVISED by discovery (Paul correction: "이거 다 내 로컬에 깔려있어"): FloorPlanCAD already local —
  FiftyOne raster export, 5,308 PNG + per-object wall bbox/segmask (samples.json 60MB) at
  `D:\dev\_ariadne\huggingface\datasets\floorplancad` (= `_ariadne\alm\datasets\FloorPlanCAD`).
  cubicasa5k local copy = card stub (no data). Prior fine-tuned models exist:
  `_ariadne\huggingface\models\qwen25_vl_3b_floorplan_{sft,grpo}`. Download step CANCELLED;
  the vector (SVG line-label) variant is the only non-local artifact — acquisition decision = Paul.
- `D:\datasets` junction dangles (pre-Catalog target `_ariadne\harness\runs\alm\datasets`) — repair
  pending approval (drive-root change).

# E2 Wave 1 run state (2026-07-17, prereg e2.wave1.v1 sealed @fcbe0c7)

## Band results (evidence in reports/e2/{s2,s4,s5})

- **B1 fidelity: FAIL** — thickness KS 0.5792 (band ≤0.20) AND entity-mix TV 0.265 (band ≤0.25,
  fidelity_M_v1_tv.json; NO_DATA resolved). Real mix has SPLINE 3,973 / ARC 2,198 / HATCH 264 etc.;
  M pack emits only LINE/LWPOLYLINE/INSERT. Generator revision ticket open; M-tier PROVISIONAL.
- **B2 detector functional: PASS** — S pack per-handle P 1.0 / R 1.0 (threshold 0.5) after two root-cause
  repairs (unit-anchor conf gate ≥0.5 kills INSUNITS-only scale=1000 poisoning; name-blind wired to
  use_layer=False). Report-only: F 0.9315/1.0 · M 0.8669/1.0. Name-blind twin alongside (eval_* dirs).
- **B4 invariance: FAIL (scale arm)** — rotate 1.0 · translate 1.0 · mirror 1.0 PASS; scale 0.8795 FAIL
  (banded ≥0.90). Forensics: scale ×2 keeps INSUNITS so physical wall thickness genuinely doubles —
  not semantics-preserving under a physical thickness prior; recorded as measured, no post-hoc band
  move (redesign ticket for W2: unit-compensated scale). units 1.0 report-only. recall-floor 0.5 never
  breached. sentinel_zero 0/100; sentinel_all vacuous on S pack (truth wall_frac 1.0 on 20/20 —
  composition artifact, documented in s5/b4_fold_v1.json). v1 xlsx rotate rows were a harness key
  mismatch (angle_deg vs angle) — battery_cli repaired, v2 re-run.
- **B3 real coverage: PASS** — zero_frac_v1 **0.2161** (band ≤0.40; v0 baseline 0.682). 384/384 defs
  found in staged DXF (missing 0), zero-scoreable defs 2 (0.52%). Evidence: s4/real_defs_v1.{json,xlsx}.
- **B5 silver alignment (exploratory, no band)**: Pearson(per-def max-score, top-tier mean
  wall_likelihood) = **0.2991** all-defs / 0.2954 nonempty (n=382). Weak — metric-mapping mismatch
  (max-score = "any wall-ish segment" vs likelihood = "def is substantially wall") is the W2 hypothesis;
  feeds the surrogate-independence audit.
- **B3/B5 substrate**: staged DXF via cad_run_operation transform.database.dxf_out (write_copy;
  original sha unchanged 14eb65eb…). Driver tools/e2/w1_real_defs.py.
- **Scorer scale incident (07-18)**: `X-평면도(기본형)` expands to 412,775 segments → reference
  O(n²) Python scorer = measured 0.55M pairs/s → 86 h for that one def; two duplicate runs burned
  ~12 h each before ETA was measured (guard-loop false negative "process exited" caused the duplicate
  relaunch). Repair: NumPy-vectorized + 10-worker MP fast path in the driver (reference module
  untouched; defs ≤4,000 segs still use it). Equivalence proven twice: ref-vs-fast 8 defs max_dev
  0.00e+00; seq-vs-MP 20k-sample max_dev 0.00e+00. Wall clock 86 h → 2 h 40 m (memory-bandwidth
  bound at 10 workers — 35-min ideal-scaling ETA was wrong; see ETA discipline memory).

## Assets

- CubiCasa5k canonical (Zenodo 2613548): `_ariadne\alm\datasets\cubicasa5k.zip` 5,469,495,706 bytes,
  22,349 entries, full-CRC testzip clean. Extracting to `_ariadne\huggingface\datasets\cubicasa5k\`.
  Contains F1_original.png + model.svg (vector labels) per plan + train/val/test splits.
