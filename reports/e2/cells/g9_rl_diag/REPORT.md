# G9/A63 set-assembly enumeration diagnostic

PREREG_JSON_SHA256: c85c2a1381042f4c1edb5e7d0d13bee189d26605a9447254c5e86eb64518c23f
PREREG_CSV_SHA256: c1a94401d684aaa21e0f0b0cf5c50f1b706d0d159243a73cd37d843a3800af47
PREREG_CONTENT_HASH: 2f3fd80f89ea94fd79372a76f97ec3f7fc876c20b7389bbb693540065db08476

This report contains numeric measurement and search-accounting output only. It emits no RL kill or survival judgment.

## Sealed scope and scorer freeze

- synthetic drawings: 200 across 8 families; reward fit 125, hidden evaluation 75
- family split SHA-256: 0c06b83b44bdf8b3aa5123b910a6a47f4d9ddfbd725523eff5fea132ed814b6d
- pack inventory: 404 files; SHA-256 14ffd7bc07f52552824d59f723c22cce7ff1c0ad54cf58bbdb6cf72771dc3aea
- verifier SHA-256: 72e33ab0e87e96defd00f74c5a22ae6c5cb001c69b740e627edeedaf2a80b690
- verifier configuration: angle 5.0 degrees; overlap 0.65; thickness 50-400 mm
- scorer features: 30 W2-02 full two-hop columns
- reward handle rows: 9350
- reward positive rows: 3400
- scorer ensemble fingerprint: 0c46c2d0a48b1c6f9ae333371b0630e2db34f3192f10722bd2a6773e725c504d
- hidden content opened only after freeze: True
- original CAD reads: 0; repository test reads: 0; val-B reads: 0; CubiCasa reads: 0
- training updates after scorer freeze: 0; GNN use: 0; subagents used: 0

## Sealed policy definitions

- terminal objective: 0.5 * set_F1(candidate_subset, synthetic_truth) + 0.5 * verifier_accepted
- greedy: sort handles by descending frozen ensemble probability with natural handle tie-break; include the prefix while p>=0.5 and stop at the first p<0.5
- beam: widths 4,16,64; traverse the same sorted include/exclude decision tree; at each equal-depth frontier retain highest cumulative frozen Bernoulli log-likelihood, then canonical bitmask; at completion choose highest terminal objective, then log-likelihood, then canonical set
- exact: if handle_count<=18, exhaustively enumerate all 2^n terminal subsets subject to 262144 subsets and 8 CPU-seconds per drawing
- deterministic upper-bound replacement: otherwise use deterministic best-bound branch-and-bound; admissible F1 bound includes every remaining true handle and no remaining false handle, verifier bonus remains possible only while processed decisions match the verifier-expected set; branch order follows frozen p>=0.5; cap 100000 nodes and 8 CPU-seconds; report incumbent, bound, gap, and certification per drawing

## Hidden pooled measurements

| policy | TP | FP | FN | precision | recall | pooled set-F1 | drawing mean set-F1 | verifier accepted | acceptance rate | terminal objective mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| greedy | 1588 | 5 | 10 | 0.996861268 | 0.993742178 | 0.995299279 | 0.995655806 | 65/75 | 0.866666667 | 0.931161236 |
| beam_4 | 1593 | 0 | 5 | 1.000000000 | 0.996871089 | 0.998433093 | 0.998449612 | 70/75 | 0.933333333 | 0.965891473 |
| beam_16 | 1593 | 0 | 5 | 1.000000000 | 0.996871089 | 0.998433093 | 0.998449612 | 70/75 | 0.933333333 | 0.965891473 |
| beam_64 | 1593 | 0 | 5 | 1.000000000 | 0.996871089 | 0.998433093 | 0.998449612 | 70/75 | 0.933333333 | 0.965891473 |
| exact_or_bound_incumbent | 1598 | 0 | 0 | 1.000000000 | 1.000000000 | 1.000000000 | 1.000000000 | 75/75 | 1.000000000 | 1.000000000 |

## Hidden family measurements

| family | policy | TP | FP | FN | pooled set-F1 | drawing mean set-F1 | verifier acceptance rate |
|---|---|---:|---:|---:|---:|---:|---:|
| F01 | greedy | 448 | 0 | 0 | 1.000000000 | 1.000000000 | 1.000000000 |
| F01 | beam_4 | 448 | 0 | 0 | 1.000000000 | 1.000000000 | 1.000000000 |
| F01 | beam_16 | 448 | 0 | 0 | 1.000000000 | 1.000000000 | 1.000000000 |
| F01 | beam_64 | 448 | 0 | 0 | 1.000000000 | 1.000000000 | 1.000000000 |
| F01 | exact_or_bound_incumbent | 448 | 0 | 0 | 1.000000000 | 1.000000000 | 1.000000000 |
| F02 | greedy | 490 | 0 | 10 | 0.989898990 | 0.990476190 | 0.800000000 |
| F02 | beam_4 | 495 | 0 | 5 | 0.994974874 | 0.995348837 | 0.800000000 |
| F02 | beam_16 | 495 | 0 | 5 | 0.994974874 | 0.995348837 | 0.800000000 |
| F02 | beam_64 | 495 | 0 | 5 | 0.994974874 | 0.995348837 | 0.800000000 |
| F02 | exact_or_bound_incumbent | 500 | 0 | 0 | 1.000000000 | 1.000000000 | 1.000000000 |
| F05 | greedy | 650 | 5 | 0 | 0.996168582 | 0.996491228 | 0.800000000 |
| F05 | beam_4 | 650 | 0 | 0 | 1.000000000 | 1.000000000 | 1.000000000 |
| F05 | beam_16 | 650 | 0 | 0 | 1.000000000 | 1.000000000 | 1.000000000 |
| F05 | beam_64 | 650 | 0 | 0 | 1.000000000 | 1.000000000 | 1.000000000 |
| F05 | exact_or_bound_incumbent | 650 | 0 | 0 | 1.000000000 | 1.000000000 | 1.000000000 |

## Family-cluster bootstrap deltas

- replicates: 10000; seed: 20260719; hidden family clusters: 3

| delta | point | bootstrap mean | bootstrap population SD | 95% percentile CI |
|---|---:|---:|---:|---:|
| beam64 minus greedy | 0.002793806 | 0.002782716 | 0.001179215 | [0.000000000, 0.004872647] |
| exact or upper minus beam64 | 0.001550388 | 0.001536899 | 0.001247869 | [0.000000000, 0.004651163] |

## Exact and upper-bound accounting

- exhaustive-exact drawing count: 0
- deterministic B&B replacement drawing count: 75
- certified optimum count: 75
- greedy selected set equals certified optimum: 65/75

| drawing | family | handles | method | certified | objective upper | gap | stop | CPU-s |
|---|---|---:|---|---|---:|---:|---|---:|
| f01_000 | F01 | 61 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_001 | F01 | 65 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_002 | F01 | 67 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_003 | F01 | 60 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_004 | F01 | 65 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_005 | F01 | 68 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_006 | F01 | 61 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_007 | F01 | 65 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_008 | F01 | 67 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_009 | F01 | 61 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_010 | F01 | 65 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_011 | F01 | 68 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_012 | F01 | 61 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_013 | F01 | 64 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_014 | F01 | 68 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_015 | F01 | 61 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_016 | F01 | 65 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_017 | F01 | 68 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_018 | F01 | 61 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_019 | F01 | 65 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_020 | F01 | 68 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_021 | F01 | 60 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_022 | F01 | 65 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_023 | F01 | 68 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f01_024 | F01 | 61 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_000 | F02 | 67 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_001 | F02 | 72 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_002 | F02 | 63 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_003 | F02 | 66 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_004 | F02 | 71 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_005 | F02 | 62 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_006 | F02 | 67 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_007 | F02 | 71 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_008 | F02 | 63 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_009 | F02 | 67 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_010 | F02 | 72 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_011 | F02 | 63 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_012 | F02 | 67 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_013 | F02 | 72 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_014 | F02 | 63 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_015 | F02 | 66 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_016 | F02 | 72 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_017 | F02 | 63 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_018 | F02 | 67 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_019 | F02 | 71 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_020 | F02 | 63 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_021 | F02 | 67 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_022 | F02 | 72 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_023 | F02 | 63 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f02_024 | F02 | 66 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_000 | F05 | 73 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_001 | F05 | 78 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_002 | F05 | 69 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_003 | F05 | 72 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_004 | F05 | 78 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_005 | F05 | 69 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_006 | F05 | 72 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_007 | F05 | 77 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_008 | F05 | 68 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_009 | F05 | 73 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_010 | F05 | 78 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_011 | F05 | 67 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_012 | F05 | 73 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_013 | F05 | 78 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_014 | F05 | 69 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_015 | F05 | 73 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_016 | F05 | 77 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_017 | F05 | 69 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_018 | F05 | 73 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_019 | F05 | 77 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_020 | F05 | 69 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_021 | F05 | 73 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_022 | F05 | 77 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_023 | F05 | 69 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |
| f05_024 | F05 | 73 | branch_and_bound_upper_bound_replacement | true | 1.000000000 | 0.000000000 | heap_exhausted | 0.000000 |

## CPU and deterministic checks

- cumulative CPU-h: 0.009266493 / 72.0
- measurement wall-s: 22.118283
- selftest_ok: true
- search signature SHA-256: 7c54bdfaa3169987cb8ed8b105eddd7a33e58e6d56c282c8d15ab19b18842d81
- scorer repeat fingerprint equal: true
- boundary denials: {"cubicasa":true,"original_cad":true,"repository_test":true,"val_b":true}
- reproducibility wording: 휘발 필드 제외 수치 전 필드 동일

## Artifact hashes

| artifact | SHA-256 |
|---|---|
| g9_rl_diag.py | d4537fbd93f0c27ff5e8e5a2662bd1f25b85d210f33386423e3b84ff0e7a0650 |
| prereg.json | c85c2a1381042f4c1edb5e7d0d13bee189d26605a9447254c5e86eb64518c23f |
| PREREG.csv | c1a94401d684aaa21e0f0b0cf5c50f1b706d0d159243a73cd37d843a3800af47 |
| results.json | 3e926ca36e3ff443804cf69dc3c355152dad7c0e375eb60eef9e3033ba751752 |
| evidence.xlsx | 3bf3128b13e293bf10a5848dab9a5f4b72d2b81bab26e8e8f213e97178b492db |

## Unresolved and disclosures

- All hidden drawings exceeded the exhaustive handle cap if listed above; their deterministic B&B incumbent/bound records are not relabeled as exhaustive enumeration.
- Feature rows use the sealed first-valid-segment handle adapter; duplicate curved/polyline segment records remain present in full verifier IR and are counted per drawing in results.json.
- Process exception initial_git_probe: repository grounding invoked read-only Git status probes before/while the packet text was first loaded. No Git mutation occurred; no later Git command was used.
- Process exception superseded_pre_measurement_seal: the first dual seal was preserved and superseded before any pack-content read because its validator used a different JSON key order from G1's published configuration seal text.
- No subagent was created or used.
- No RL track judgment is emitted here; the orchestrator owns the sealed band comparison.

CELL_COMPLETE: g9_rl_diag
