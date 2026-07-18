# E2 Wave 1 independent adversarial verification

Date: 2026-07-18  
Contract: reports/e2/prereg_wave1.json, e2.wave1.v1  
Claims checked: reports/e2/RUN_STATE.md, section “E2 Wave 1 run state”  
Independent recomputation: reports/e2/verify/scratch/recompute_wave1.py

## Scope and method

I treated the preregistration wording as the metric contract and recomputed from the supplied JSON/XLSX artifacts. I read the one explicitly permitted external artifact, D:\dev\99_tools\autocad-sdk-router\runs\e2_b3_dxfout_20260717\1_export.dxf, only to check the B3 definition universe and selected scorer results. I did not use git or network access and did not modify evidence outside reports/e2/verify.

The primary recomputation script:

1. thresholds every scores.per_handle score at score >= 0.5;
2. pools TP/FP/FN across drawings before computing B2 micro precision/recall;
3. groups all non-error XLSX result rows by transform and takes the unweighted row mean used by the workbook;
4. computes B3 as count(n_wall == 0) / count(rows);
5. reconstructs the silver mean independently from all 60 top-tier raw shards and computes Pearson from first principles; and
6. computes B1 TV as 0.5 times the L1 distance between normalized category counts.

The script completed successfully and printed the final table reproduced at the end of this report.

## B1 — NOT_REPRODUCIBLE

Claim: fidelity FAIL with thickness KS 0.5792 and entity-mix TV 0.265.

### Entity-mix TV: confirmed from the preserved inputs

The calculation was:

    real_total = sum(real_mix.values())      # 28,121
    pack_total = sum(pack_mix.values())      # 377
    tv = 0.5 * fsum(
        abs(real_mix[k] / real_total - pack_mix[k] / pack_total)
        for k in union(real_mix, pack_mix)
    )

Result:

- exact TV = 0.26503324917321575;
- reported to three decimals = 0.265;
- sealed band = <= 0.25;
- TV component verdict = FAIL.

The sidecar’s real_mix exactly equals the entity-type counts independently flattened from real_stats.json/entity_mix_by_role. The sidecar contains pack counts LINE 217, LWPOLYLINE 140, and INSERT 20. The formula and totals are internally sound. The actual M DXFs that would prove those pack counts are the evaluated inputs are absent, so pack-count provenance cannot be checked against raw DXFs.

### Thickness KS: recorded and numerically regenerable, but not sealed by raw evaluated inputs

fidelity_M_v1.json records:

- distance = 0.5792384050353632;
- method = ks_hist_rebinned;
- n_pack = 1,326;
- n_real = 4,877.

The committed fidelity JSON is not sufficient by itself to reconstruct that number:

- neither pack_summary nor real_summary preserves thickness_samples;
- the pack summary has a different 20 mm histogram grid from the real histogram;
- 1,156 of 1,326 pack observations are clamped into the pack histogram’s final >=600 bin, losing the information needed to redistribute them across the real bins; and
- reports/e2/s2/packs/M contains 0 of the 20 manifest-referenced DXFs. The same is true for S and F.

As a diagnostic consistency check, I regenerated a candidate M pack using the committed manifest seeds 43 through 62, the current committed grammar/openings/noise code, and noise level 2. I then applied the comparator’s pair-offset and real-bin logic:

    for seed in range(43, 63):
        plan = grammar(seed)
        plan = openings(plan, seed)
        dxf, truth = render(plan)
        dxf, truth = noise_messify(dxf, seed, level=2, truth)
        offsets.extend(parallel_pair_offsets(modelspace_segments(dxf)))
    pack_counts = histogram(offsets, real_stats["thickness_hist"]["bin_edges"])
    KS = max(abs(cumsum(pack_counts)/1326 - cumsum(real_counts)/4877))

That reconstruction produced real-grid pack counts:

    [0, 0, 0, 1, 1, 0, 1, 1, 30, 1, 28, 0, 63,
     1, 31, 4, 17, 31, 60, 248, 539, 269, 0, 0, 0]

The maximum CDF gap occurs after the [1000,1500) bin:

- regenerated pack CDF = 0.20361990950226244;
- real CDF = 0.7828583145376257;
- absolute gap = 0.5792384050353632.

The regenerated 20 mm histogram exactly matches the one in fidelity_M_v1.json, and all 20 regenerated truth ledgers match the committed truth content after excluding allocated handle values. This makes 0.5792384050 numerically consistent with the current generator and manifest. It does not prove that the regenerated DXFs are the exact evaluated files: no evaluated DXFs, hashes, raw samples, or source revision pin survive. Under the requested strict raw-artifact standard, the KS claim is therefore NOT_REPRODUCIBLE.

The B1 band outcome is nevertheless logically FAIL because the independently recomputed TV alone violates the AND pass condition.

### Metric-definition audit

The two sides of the thickness comparison are not generated with the same extraction statistic:

- pack side: all modelspace LINE/LWPOLYLINE/POLYLINE segments, angle tolerance 1 degree, minimum overlap fraction 0.10;
- real side: within-definition LINE pairs, angle tolerance 2 degrees, minimum overlap 0.30, as recorded in real_stats.json.

Entity populations also differ: the pack mix counts modelspace entities, while the real mix is a per-definition entity histogram. Counting each regenerated named block once changes the candidate pack TV from 0.2650332492 to 0.2600192027. It remains a FAIL, but the reported value depends on a population mismatch.

There is also an artifact-state inconsistency. fidelity_M_v1.json still says draft_pending_prereg=true, entity_mix_tv=NO_DATA, and overall_verdict=INCONCLUSIVE_DRAFT. RUN_STATE obtains the final TV from the later fidelity_M_v1_tv.json sidecar. The standard comparator looked for real_stats["entity_mix"], but real_stats stores entity_mix_by_role, so the sealed TV required a manual sidecar repair.

## B2 — DISCREPANCY(0.9091 vs 0.8669 for M full precision)

The banded S-tier PASS is confirmed. The claimed M report-only precision is not the sealed per-handle threshold metric.

### Direct micro recomputation

For each drawing and arm:

    truth = {upper(h) for h in truth_json["wall_handles_flat"]}
    pred = {
        upper(h)
        for h, rec in pred_json["scores"]["per_handle"].items()
        if float(rec["score"]) >= 0.5
    }
    tp += len(pred & truth)
    fp += len(pred - truth)
    fn += len(truth - pred)

No committed score is exactly 0.5, so there is no threshold-boundary ambiguity.

| Tier / arm | TP | FP | FN | Recomputed precision | Recomputed recall | Committed summary |
|---|---:|---:|---:|---:|---:|---|
| S full | 272 | 0 | 0 | 1.0000000000 | 1.0 | exact match |
| S name-blind | 272 | 0 | 0 | 1.0000000000 | 1.0 | exact match |
| F full | 272 | 20 | 0 | 0.9315068493 | 1.0 | exact match |
| F name-blind | 272 | 20 | 0 | 0.9315068493 | 1.0 | exact match |
| M full | 280 | 28 | 0 | 0.9090909091 | 1.0 | 0.8668730650 |
| M name-blind | 280 | 31 | 0 | 0.9003215434 | 1.0 | 0.8668730650 |

Consequences:

- S satisfies the sealed >=0.80 precision and recall bands: B2 functional PASS is confirmed.
- F report-only 0.9315/1.0 is confirmed.
- M full report-only is 0.9091/1.0, not 0.8669/1.0.
- M name-blind report-only is 0.9003/1.0, not the identical 0.8669/1.0 shown by the committed summaries.

### Which artifact is wrong, and why

All 120 committed per-drawing eval files identify baseline.source as walls. tools/e2/detect/cli.py/run_eval first unions the handles in scores.walls and thresholds per_handle.score only if the walls union is empty. Every prediction emitted walls, so the supplied threshold was unused. tools/e2/w1_eval_driver.py then recursively takes the first TP/FP/FN mapping in each eval, which is this baseline, and pools it.

The M per-drawing evals therefore consistently produce:

    TP = 280
    FP = 43
    FN = 0
    precision = 280 / 323 = 0.8668730650154799

The M tier summary faithfully aggregates those per-drawing eval files, so it is internally consistent. The defect is that both layers measure the scores.walls geometry-pair union instead of the sealed scores.per_handle >= 0.5 set.

For M full, direct threshold counts differ from the committed baseline in 15/20 drawings:

    0000, 0001, 0002, 0003, 0005, 0007, 0008, 0009,
    0010, 0012, 0015, 0016, 0017, 0018, 0019

Each baseline has one additional false positive. For M name-blind, prediction sets differ in 15/20 drawings and count triples differ in 14/20. S and F happen to have identical threshold and walls sets, so their correct numbers do not validate the evaluator’s implementation.

### Name-blind twin audit

The twin is a genuine measurement, not a copied file:

- S: all 272/272 stored scores differ between full and name-blind;
- F: all 408/408 scores differ;
- M: 429/460 scores differ;
- all 20 prediction-file pairs in each tier differ byte-for-byte.

Threshold decisions change only in M, on three false handles:

| Drawing | Handle | Full score | Name-blind score | Decision |
|---|---|---:|---:|---|
| M/0001 | 59 | 0.422110 | 0.527637 | negative -> positive |
| M/0004 | 59 | 0.450000 | 0.562500 | negative -> positive |
| M/0018 | 5B | 0.450000 | 0.562500 | negative -> positive |

However, scores.walls is identical between full and name-blind for all 60 drawings. That is why the committed summaries are identical and fail to reflect the three real M threshold flips. The preregistration’s structural “alongside” requirement is met; its intended per-handle threshold reporting is not.

### Metric and design audit

The sealed B2 wording explicitly says per-handle precision/recall at threshold 0.5. The direct calculation implements it; the committed evaluator does not.

The S pack has no scored negatives: 272 scored handles equal exactly 272 truth handles, and all 272 are positive. S precision is therefore vacuous on its scored universe. F has 136 scored negatives and M has 180, but those tiers are report-only.

The prediction arithmetic is reproducible from committed prediction/truth files. Detector generation is not rerunnable from this worktree because all 60 manifest-referenced synthetic DXFs are absent.

## B3 — CONFIRMED

Claim: zero_frac_v1 0.2161, PASS against <=0.40, with 384/384 definitions present.

### Coverage recomputation

real_defs_v1.json contains 384 rows and 384 unique definition names:

    n_zero = sum(row["n_wall"] == 0 for row in rows) = 83
    zero_frac_v1 = 83 / 384 = 0.21614583333333334

Rounded to four decimals this is 0.2161, so the implemented metric passes <=0.40.

For contrast, only two rows have n_scored == 0:

    2 / 384 = 0.005208333333333333

Those definitions are X-FORM_청주$0$Block_5 and X-FORM_청주$0$dA로고.

The JSON and XLSX contain the same 384 rows and agree on n_segments, n_scored, n_wall, max_score, and silver_mean_wall_likelihood with zero mismatches.

### Independent staged-DXF coverage check

The permitted staged DXF is 15,305,576 bytes with SHA-256:

    5a6035721630cddc6d753b1b97b898e7a4ce4d5988342ce85e2c465cdb81deff

Fresh ezdxf parsing found 410 block definitions. All 384 real_defs row names are present; missing = 0. This independently confirms the claimed 384/384 definition substrate.

### Semantic plausibility spot checks

Fresh block expansion/scoring of selected definitions matched the preserved rows.

| Definition | Silver mean | n_segments | n_scored | n_wall | max_score | Interpretation |
|---|---:|---:|---:|---:|---:|---|
| X-평면도(기본형)$0$111a | 0.9667 | 10,046 | 4,737 | 3,411 | 0.8 | large plan with dense W1/W2 wall geometry |
| X-평면도(기본형)$0$111b | 0.9667 | 9,610 | 4,550 | 3,210 | large wall-rich plan |
| X-평면도(기본형)$0$130a | 0.9633 | 9,678 | 4,174 | 2,911 | large wall-rich plan |
| *D295 | 0.0200 | 9 | 6 | 0 | 0.378572 | DIM/DEFPOINTS dimension cache; sensible zero |
| *D299 | 0.0233 | 9 | 6 | 0 | 0.378572 | overall dimension cache; sensible zero |
| *D300 | 0.0200 | 7 | 6 | 2 | 0.8 | AA-AXIS-DIM7 cache; likely two false positives |

The high-silver examples behave plausibly. The dimension-cache sample exposes a limitation: among 113 *D definitions, 79 have n_wall=0 and 34 have n_wall=2. The B3 metric rewards any positive as “coverage,” including obvious dimension-cache false positives.

### Metric-definition audit

The preregistration says “scores zero handles” but does not state threshold 0.5 or say “zero positive/wall handles.” The implementation and the user-specified checklist interpret it as no score >=0.5, represented by n_wall == 0. A literal “no handles scored” interpretation is n_scored == 0 and gives 0.0052, not 0.2161. The claim is CONFIRMED under the implemented/checklist interpretation, with this wording gap recorded.

The v0 baseline 0.682 is present in reports/e1/calibration_v0.json as handle_jaccard.zero_frac over n=239. It is not the same denominator or semantic event as “no >=0.5 detector positives” over 384 definitions. The preregistration hard-codes the comparison, but calling it coverage recovery is scientifically apples-to-oranges.

Finally, scorer per-handle storage is traversal-order dependent when several expanded segments share a DXF handle. One current zero definition, X-평면도(기본형)$0$씽크$0$59C$0$gasdfasdfs$0$COK3, has committed max_score 0.392857 and n_wall 0, while another segment under a shared handle scores 0.742857. Max-per-handle aggregation would produce n_wall 1 and change the zero fraction to 82/384 = 0.2135416667. Both values pass, but the sealed per-handle concept is not robustly implemented.

## B4 — DISCREPANCY(0 contract-valid PASS arms vs 3 claimed PASS arms)

The numerical XLSX means and the sentinel_zero claim are confirmed. The claimed rotate/translate/mirror PASS verdicts violate the sealed automatic-sentinel rule.

### Workbook recomputation

battery_S_v2.xlsx has 80 result rows: 20 each for rotate, mirror, scale, and units. battery_S_v2_translate.xlsx has 20 translate rows. The workbooks have only results and summary sheets, no hidden rows/columns/sheets, no formulas, and no filters. All five arms cover 0000.dxf through 0019.dxf exactly once. Every result has numeric invariance and blank error; no row was omitted.

The calculation was:

    values = [float(row["invariance"]) for row in rows_for_transform]
    mean_invariance = fsum(values) / len(values)

| Arm | n | Recomputed mean | Minimum | Errors | sentinel_zero rows | sentinel_all rows | Claimed numeric |
|---|---:|---:|---:|---:|---:|---:|---|
| rotate | 20 | 1.0000000000 | 1.0 | 0 | 0 | 20 | 1.0 |
| translate | 20 | 1.0000000000 | 1.0 | 0 | 0 | 20 | 1.0 |
| mirror | 20 | 1.0000000000 | 1.0 | 0 | 0 | 20 | 1.0 |
| scale | 20 | 0.8794841270 | 0.7 | 0 | 0 | 20 | 0.8795 |
| units | 20 | 1.0000000000 | 1.0 | 0 | 0 | 20 | 1.0 |

Scale’s exact unweighted macro mean is:

    22163 / 25200 = 0.879484126984126984...

Thus 0.8795 is correct four-decimal rounding and fails >=0.90. Scale has 32 flips over 272 before-wall handles: 11 drawings are below 0.90, two equal 0.90, and seven exceed it. A pooled alternative is 240/272 = 0.8823529412, also FAIL.

The workbook summary sheets agree exactly with these calculations. b4_fold_v1.json also agrees on means, minima, error counts, and sentinel counts. The superseded battery_S_v1.xlsx has 20/20 rotate errors from the angle_deg/angle mismatch; v2 has zero rotate errors, confirming that those errors are not hidden in the reported run.

### Sentinel contract discrepancy

The sealed note says any sentinel trip is an automatic FAIL regardless of invariance. Every one of the 100 result rows has sentinel_all=true. Therefore:

- rotate, translate, and mirror are automatic FAIL, not PASS;
- scale fails both invariance and the sentinel rule;
- units also trips the sentinel, although its band status was not sealed.

b4_fold_v1.json records all 20 sentinel_all rows per arm, then waives them post hoc as an S-pack composition artifact and labels rotate/translate/mirror PASS. RUN_STATE repeats that waiver. The waiver is absent from the preregistration. The overall B4 label remains FAIL, but “FAIL (scale arm)” is incomplete and the three claimed arm PASS verdicts are invalid under the contract.

The underlying reason is independently visible in B2: for each S drawing, the scored handle universe equals the truth wall-handle universe, so the before prediction is 100% wall. The sentinel correctly identifies this degenerate all-positive battery. Waiving it defeats the preregistered safeguard.

### Recall-floor and arm-definition audit

Each S truth count equals the workbook wall_count_before. The count proxy wall_count_after / truth_count gives:

- rotate/translate/mirror/units mean and minimum 1.0;
- scale mean 0.8794841270 and minimum 0.7;
- zero rows below the 0.5 floor.

This supports “no floor breach” only indirectly. tools/e2/meta/battery_cli.py never loads truth, never calls invariance.recall_floor or invariance.verdict, and writes no recall column. No raw battery before/after predictions are committed. b4_fold_v1.json’s recall values are a downstream count-derived proxy, not a metric emitted or enforced by the battery.

The preregistration calls the battery “per rigid transform” but bands scale, which is not rigid and, by RUN_STATE’s own explanation, is not semantics-preserving under the physical-thickness prior. It explicitly names explode/rename as report-only; neither is present. Instead, units is reported as an unsealed report-only arm. The sealed wording also does not specify unweighted macro versus pooled aggregation.

## B5 — CONFIRMED

Claim: Pearson(per-definition max score, top-tier mean wall_likelihood) = 0.2991.

### Independent raw-shard reconstruction

I parsed all 60 JSON shards under opus48_max, fable5_high, and sol56_xhigh:

- each judge has 384 unique definitions;
- the three exact-name sets are identical;
- there are 1,152 usable wall_likelihood values;
- there are no duplicate definition records, missing judges, non-finite values, or row/shard vocabulary mismatches;
- all 384 embedded means equal the three raw judge values averaged and rounded to four decimals.

The first-principles calculation was:

    mean_x = fsum(max_scores) / 384
    mean_y = fsum(raw_silver_means) / 384
    r = fsum((x-mean_x)*(y-mean_y)) / sqrt(
        fsum((x-mean_x)**2) * fsum((y-mean_y)**2)
    )

Results:

- raw, unrounded judge means: r = 0.2991079704431685 -> 0.2991;
- embedded four-decimal means: r = 0.29911976248236477 -> 0.2991;
- embedded nonempty rows only: r = 0.2953662915857507 -> 0.2954, n=382.

The all-definition claim is confirmed under both raw and embedded means.

### Silver cross-check samples

| Definition | opus48 | fable5 | sol56 | Raw mean | Embedded mean | max_score |
|---|---:|---:|---:|---:|---:|---:|
| X-평면도(기본형)$0$111a | 0.96 | 0.95 | 0.99 | 0.9666667 | 0.9667 | 0.8 |
| X-평면도(기본형)$0$130a | 0.95 | 0.95 | 0.99 | 0.9633333 | 0.9633 | 0.8 |
| *D295 | 0.03 | 0.02 | 0.01 | 0.0200000 | 0.0200 | 0.378572 |
| *D299 | 0.04 | 0.02 | 0.01 | 0.0233333 | 0.0233 | 0.378572 |
| *D300 | 0.02 | 0.03 | 0.01 | 0.0200000 | 0.0200 | 0.8 |

Merged-vocabulary handling has no effect here because all three judges and real_defs_v1.json use the same 384 exact keys.

### Metric-definition audit

The driver rounds each silver mean to four decimals before the preserved Pearson calculation. The literal sealed wording says “mean,” for which the raw result is 0.2991079704; premature rounding moves r by about 1.1792e-5, but not the four-decimal claim.

The detector max_score values are themselves preserved only to six decimals and inherit the shared-handle last-write defect described under B3. As an illustration, changing only the demonstrated COK3 max_score from 0.392857 to the observed max-over-shared-segments value 0.742857 changes embedded-mean Pearson to 0.2961430691. That is not a complete corrected metric, but it demonstrates that 0.2991 is traversal-order dependent.

## Internal artifact consistency

- B1: the main fidelity artifact is stale/draft and says entity TV NO_DATA; the sidecar and RUN_STATE provide the final TV. The exact KS result is recorded but its raw evaluated inputs are not preserved.
- B2: each tier summary correctly aggregates its per-drawing baseline files. M prose and summaries are wrong only relative to the sealed per-handle metric. The name-blind predictions are real, but scores.walls makes both M summaries identical and hides three threshold flips.
- B3/B5: real_defs_v1.json and its XLSX agree exactly. RUN_STATE’s 83/384, 2/384, 0.2991, and 0.2954 values agree with those artifacts.
- B4: both workbook summary sheets and b4_fold_v1.json agree numerically. The fold’s PASS labels conflict with its own sentinel counts and the preregistration.
- The evidence map says the synthetic packs contain DXFs, but the worktree contains zero DXFs in S, F, and M.

## Measurement-pipeline defects

1. **Evaluated raw inputs are missing.** All 60 manifest-referenced synthetic DXFs are absent, as are raw B4 before/after predictions. B1 KS input provenance and detector/battery reruns are therefore not sealed.
2. **B2 evaluates the wrong prediction set.** run_eval prefers scores.walls and operationally ignores the sealed per_handle threshold in every supplied baseline eval.
3. **Name-blind summary loss.** The full and name-blind walls arrays are identical, so the M summaries conceal three real threshold decision changes.
4. **Banded S precision and B4 are all-positive.** There are no scored negatives in S. Precision is unchallenged, and the invariance battery degenerates to recall.
5. **B4 sentinel waiver is post hoc.** All 100 rows trip sentinel_all, but the fold marks three banded arms PASS despite the automatic-fail contract.
6. **B4 does not implement its recall floor.** The runner does not load truth or call recall_floor/verdict; fold recall is an external proxy.
7. **B4 arm governance drift.** Units is treated as report-only although only explode/rename are sealed that way; explode/rename are absent; scale is called rigid despite not preserving the detector’s physical semantics.
8. **B1 compares different populations and parameters.** Pack and real thickness/entity distributions are not extracted with like-for-like geometry universes or tolerances.
9. **B1 finalization is split across inconsistent artifacts.** The main report remains draft/inconclusive/NO_DATA and a sidecar supplies the final TV.
10. **Per-handle scoring is last-write/order dependent.** Multiple expanded segments can share one DXF handle, but evidence_grid and the fast path overwrite per_handle[key] rather than aggregate. Reversing segment order changes M direct precision from 0.9091 to 0.869565 in a fresh rescore. In a real high-silver definition with 669 segments and 290 handles, reversing order changes n_wall from 209 to 217; max-per-handle aggregation gives 232.
11. **Same-handle wall pairs and duplicate parsing exist.** M includes wall records such as ["4D","4D"] while handle 4D’s stored score is 0.2. Top-level geometry is also parsed through two paths and concatenated without deduplication. These defects help explain the walls/per_handle divergence.
12. **B3 wording and v0 comparator are not like-for-like.** “Zero handles” omits the 0.5 threshold, and v0 0.682 is handle-Jaccard zero over 239 cases rather than no detector positives over 384 definitions.
13. **B3 coverage rewards false positives.** Thirty-four of 113 obvious *D dimension caches have two predicted wall handles and therefore count as recovered coverage.
14. **B5 rounds before correlation and inherits scorer order dependence.** The reported rounding is stable, but the exact statistic is not tied to an order-independent per-handle aggregation.
15. **Source/output version pinning is incomplete.** The committed real_defs rows omit fields emitted by the current w1_real_defs.py (including name-blind fields), and artifacts do not pin the precise scorer source hash that created them.

Strict assessment: the primary S-tier B2 PASS, B3 PASS, B1 FAIL outcome, and B5 reported value survive arithmetic checking. The result set as written is not fully verified because the M B2 number is wrong under the contract, B4 arm PASS labels violate the sentinel rule, and B1’s evaluated KS inputs were not preserved.

## Overall verdict table

| Band | Exact independent result | Claimed result | Final verifier verdict |
|---|---|---|---|
| B1 | TV 0.2650332492 -> 0.265 FAIL; KS 0.5792384050 recorded and regenerable, but evaluated M DXFs/raw samples absent | KS 0.5792 and TV 0.265; FAIL | **NOT_REPRODUCIBLE** (TV independently confirms the band FAIL) |
| B2 | S full P/R 1.0/1.0 PASS; F 0.9315068493/1.0; M full 0.9090909091/1.0; M name-blind 0.9003215434/1.0 | S 1.0/1.0; F 0.9315/1.0; M 0.8669/1.0 | **DISCREPANCY(0.9091 vs 0.8669 for M full precision)** |
| B3 | 83/384 = 0.2161458333 -> 0.2161; external DXF has 384/384 defs | 0.2161; 384/384; PASS | **CONFIRMED** under n_wall == 0 interpretation |
| B4 | rotate/translate/mirror/units mean 1.0; scale 0.8794841270; errors 0; sentinel_zero 0; sentinel_all 100/100 rows | three transform PASSes, scale FAIL, units report-only, sentinel_zero 0 | **DISCREPANCY(0 contract-valid PASS arms vs 3 claimed PASS arms)** |
| B5 | raw-mean r 0.2991079704; embedded-mean r 0.2991197625; both -> 0.2991 | 0.2991 exploratory | **CONFIRMED** |
