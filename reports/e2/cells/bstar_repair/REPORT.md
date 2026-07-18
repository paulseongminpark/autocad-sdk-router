# B* Geometry-Family Repair — Numeric Remeasurement

- Completed: 2026-07-19T01:43:44+09:00
- Rows: train 3,862,317; val v1 353,953; val v2 349,100
- Drawings: train 4,200; val v1 400; val v2 396
- Removed val rows: 4,853
- Test-split reads: 0
- Peak sampled RSS: 1.805 GiB

## Family measurements

- v1 family collision count: 4
- v2 family collision count: 0
- v2 geometry-family collision count: 0
- v2 drawing-ID collision count: 0

## Arm deltas (three-seed mean)

| Arm | AUPRC v1 | AUPRC v2 | Δ v2-v1 | F1 v1 | F1 v2 | Δ v2-v1 |
|---|---:|---:|---:|---:|---:|---:|
| fast_score_p1 | 0.1086355919 | 0.1086751102 | +0.0000395183 | 0.1791472663 | 0.1793171980 | +0.0001699317 |
| logistic_local6 | 0.3408373444 | 0.3409797636 | +0.0001424192 | 0.0531932131 | 0.0528849541 | -0.0003082590 |
| hist_gbdt_local6_p2a | 0.6785054622 | 0.6786520327 | +0.0001465704 | 0.5158741717 | 0.5158473151 | -0.0000268565 |
| hist_gbdt_context12_p2b | 0.8311985694 | 0.8314550965 | +0.0002565271 | 0.7063773452 | 0.7063360838 | -0.0000412614 |
| hist_gbdt_context_layer_name_diagnostic | 0.8311985694 | 0.8314550965 | +0.0002565271 | 0.7063773452 | 0.7063360838 | -0.0000412614 |

## Shuffle null (64 seeds)

| Measure | v1 | v2 | Δ v2-v1 |
|---|---:|---:|---:|
| Mean AUPRC | 0.1357061755 | 0.1357112120 | +0.0000050365 |
| Mean F1 | 0.0000000000 | 0.0000000000 | +0.0000000000 |

## B* reassignment

- v1 arm: `hist_gbdt_context12_p2b`
- v2 arm: `hist_gbdt_context12_p2b`
- v2 mean val AUPRC: 0.8314550965
- v2 mean val F1@0.5: 0.7063360838
- Model changed: 0
- Model artifact SHA-256: `04c0515f0253b1d1979b5a5ca4a1f6ad6801c8e6b17a74734978f14717749f21`
- Repaired split hash: `7e34d7301d888c822861cf1dfa1c5ee13e95b451824175cae563fd2a7c215db5`
- Manifest content hash: `21a839c6467f121d45c280091bbf538e04978943c5ea53f7c5b6f27bbd61c8bc`

## Excluded val drawings

- `high_quality_3750`: gid 99; rows 756; family `34aba6e680c2b74b4d826e28b15282f4347a53a671c8ffdf624386b7c31abb09`
- `high_quality_architectural_1186`: gid 165; rows 1258; family `006fb2efe92d10b62641a861353c0ace658240c78c7c931c14a0a7faad9d364d`
- `high_quality_architectural_575`: gid 276; rows 1382; family `1f89e7784c3937f1cbc94e2d985f7203b15bb68be122c3fddc1bf75b34038113`
- `high_quality_architectural_642`: gid 305; rows 1457; family `11ec5147b24b7cfbd5ed13893efda9abaf2708859f372b2882ce9a074d2ef8d2`

## Selftest

```text
SELFTEST_BEGIN
deterministic_exclusion_repeat_count=2
deterministic_exclusion_mismatch_count=0
excluded_val_drawing_count=4
excluded_val_drawing_sha256=780041ed6e2f21fd2c8e052e772733e52942fff44045417c5d6d26ba7f96cfd3
original_val_drawing_count=400
repaired_val_drawing_count=396
removed_val_row_count=4853
repaired_val_row_count=349100
post_repair_family_collision_count=0
design_cache_mismatch_count=0
v1_arm_metric_comparison_count=15
v1_arm_metric_mismatch_count=0
v1_arm_metric_max_abs_delta=0
v1_shuffle_metric_comparison_count=64
v1_shuffle_metric_mismatch_count=0
v1_shuffle_metric_max_abs_delta=0
manifest_content_hash_match=1
model_artifact_hash_match=1
peak_rss_under_48gib=1
test_split_reads=0
subagents_used=0
SELFTEST_END
structural_mismatch_count=0
recorded_selftest_output_mismatch_count=0
selftest_mismatch_count=0
```

## Artifact hashes

- bstar_repair.py: `235ff4bea7fdb78bbf1776d16f3dfe361ab46cd79657aab61b939ec31455a0ca`
- results_v2.json: `e6f8d17cfa94346ca0443649f1b327bd6982893522fc3f5b50e95bbad8f38643`
- bstar_manifest_v2.json: `eb7446537d9477aca636815ab9a4add660c487af772455cb355143bff8eae312`
- bstar_model.joblib: `04c0515f0253b1d1979b5a5ca4a1f6ad6801c8e6b17a74734978f14717749f21`
- results_v1.json: `7a696ff08c0a78c8b9db5f85ef5b5ece4dcc5ded40a664efe6564af36d65eab7`
- bstar_model_v1.joblib: `04c0515f0253b1d1979b5a5ca4a1f6ad6801c8e6b17a74734978f14717749f21`

## Unresolved

- Count: 0

CELL_COMPLETE: bstar_repair
