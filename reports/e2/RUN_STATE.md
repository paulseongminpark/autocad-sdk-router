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

## Wave-1 verification (2026-07-18, Paul-ordered; self + blind sol56-ultra cross-check)

Independent adversarial recompute of every banded number from raw committed artifacts
(scratchpad w1_verify.py; fresh code, no fold-logic reuse):

- **CONFIRMED**: B2 S 1.0/1.0 (PASS stands) · B4 all five arms to 4 decimals (rotate/translate/
  mirror/units 1.0, scale 0.8795) · B3 zero_frac 0.2161 (83/384; spot checks semantic: *D295
  dimension cache 0 walls, X-평면도(기본형) 16,816 walls; 0 defs with silver wl≥0.8 scored zero)
  · B5 Pearson 0.2991 · B1 TV 0.265 · fast-scorer equivalence re-proven on 6 FRESH defs (dev 0.0).
- **VERIFY-1 (defect found, corrected)**: the v1 B2 tier summaries (eval_{S,F,M}.json) folded the
  per-drawing `baseline` block whose predicted set is WALL-PAIR membership (`source:"walls"`), not
  the sealed per-handle≥0.5 metric; and since walls records ignore the layer channel, the
  name-blind summary was a vacuous duplicate of full on every tier. Corrected fold
  (w1_eval_fold_v2.py → eval_fold_v2.json) from `ablation[channel_removed=none]` per arm:
  S 1.0/1.0 · F P 0.9315/R 1.0 · **M P 0.9091/R 1.0** (v1-quoted 0.8669 was the walls-pair
  artifact; correction is upward). Name-blind arm decisions identical to full at threshold 0.5 on
  all three tiers (now a real measurement). Band verdicts unchanged (B2 banded only on S).
- **VERIFY-2 (reproducibility gap, closed)**: committed fidelity_M_v1.json carried an empty real
  side; KS 0.5792 was quoted but not reproducible from it. Re-ran s2_fidelity with real_stats →
  fidelity_M_v2.json reproduces **KS 0.5792 FAIL_DRAFT** (B1 verdict unchanged; real_summary.source
  display field still null — cosmetic ticket; entity-mix NO_DATA remains supplemented by
  fidelity_M_v1_tv.json TV 0.265).
- Blind cross-check: gpt-5.6-sol effort=ultra launched in worktree @de72da4 (pre-correction
  state, no access to the corrections above) → report lands at reports/e2/verify/.

### Joint adjudication (self × sol56-ultra, 2026-07-18 — reports/e2/verify/sol56_wave1_verify.md)

Sol independently re-derived every number, re-found VERIFY-1 (M 0.9091 vs 0.8669), CONFIRMED
B3/B5 exactly, and found what self-verification missed:

- **Finding 10 (fixed)**: per-handle store was traversal-order dependent (shared handles
  overwritten). Repair: max-aggregation in evidence_grid + fast path; selftests + equivalence
  re-proven (max_dev 0.00e+00).
- **Finding 11 (fixed)**: run_detect merged parse_modelspace with insert_expand, which ALREADY
  emits top-level entities → every top-level segment duplicated. The 0-offset clone hijacked the
  thickness channel — root cause of the long-open fixed-0.714286 anomaly — and inflated junction
  counts. Repair: geometry from insert_expand alone (units from header parse).
- **Sentinel letter (accepted)**: sealed B4 text says any sentinel trip = automatic FAIL; all 100
  rows trip sentinel_all (S scored universe is 100% wall). The v1 fold's 3 arm-PASS labels were a
  post-hoc waiver → **B4 strict-contract verdict: FAIL on all banded arms**. The composition
  analysis stands as diagnosis only; battery redesign (mixed-content pack, scoped sentinel) goes
  through W2 prereg, not retroactive waiver.
- Also logged from sol: my fold_v2's name-blind numbers were themselves wrong (read the eval
  ablation block = unweighted channel mean, not the weighted arm) — superseded by fold v3.

**B2 final (repaired pipeline @eval2_*, sealed per-handle metric, fold v3):**
S full 1.0/1.0 **PASS** · nb 1.0/1.0 — F full P 0.9315 / nb 0.9252 — M full P 0.8669 / nb 0.8615
(all recalls 1.0). Note: fixing the duplication LOWERED M precision vs the buggy pipeline's 0.9091 —
true in-band neighbours now win the thickness channel for near-wall opening/noise segments; the
numeric equality of M full 0.8669 with the old walls-fold value is coincidence (verified 280/43/0
by independent recount). S6-1 re-run on eval2 (classical_v2): W2-B1 still PASS (GBDT 1.0 vs
detector 0.967/0.9263), name-blind gap 0.0, anti-perm AUC 0.2322/0.4156 PASS.
Remaining sol findings → tickets: B1 population/params mismatch (8), split artifacts (9), B3
FP-rewarding coverage metric + v0 comparator apples-to-oranges (12/13), version pinning (15),
B4 recall floor in-runner (6) & arm governance (7). B3/B5 re-measure (max-agg, dual-arm) running as real_defs_v3.

**B4 re-measure on repaired pipeline (battery_S_v3, b4_fold_v2)**: rotate/translate/mirror/units
mean invariance 1.0; **scale 0.7624** (was 0.8795 — with the 0-offset clone gone, thickness relies
on true partners, so ×2 scale's band exit shows honestly). sentinel_all 100/100 (pack composition),
sentinel_zero 0, errors 0. **Strict-contract verdict: FAIL on all banded arms** (sealed
any-sentinel-trip rule; v1 arm-PASSes withdrawn). Battery redesign (mixed pack, scoped sentinel)
→ W2 prereg amendment.

## Assets

- CubiCasa5k canonical (Zenodo 2613548): `_ariadne\alm\datasets\cubicasa5k.zip` 5,469,495,706 bytes,
  22,349 entries, full-CRC testzip clean. Extracting to `_ariadne\huggingface\datasets\cubicasa5k\`.
  Contains F1_original.png + model.svg (vector labels) per plan + train/val/test splits.
