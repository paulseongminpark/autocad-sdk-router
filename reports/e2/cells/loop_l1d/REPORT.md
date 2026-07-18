# E2 Loop L1d — consensus redesign and cohort replay

PREREG_JSON_SHA256: `474cf61bb8d8856d62e161444b091bd0f501e8fda30d116612608974db6524c1`
EVIDENCE_SEALED_XLSX_SHA256: `0d1f30762546ece2a2b0233f46410f78edb8f69c99b6512d251cc519ba2d4cf4`
PREREG_JSON_BYTES: 4314
EVIDENCE_SEALED_XLSX_BYTES: 10957
PREREG_JSON_MODIFIED_UTC: `2026-07-18T18:43:31.3680429Z`
EVIDENCE_SEALED_XLSX_MODIFIED_UTC: `2026-07-18T18:44:15.6467503Z`

## 봉인 관측

| observation | value |
| --- | --- |
| prereg_hash_equal | 1 |
| sealed_workbook_hash_equal | 1 |
| sheet_name_equal | 1 |
| canonical_content_equal | 1 |
| leaf_count_equal | 1 |
| leaf_mismatch_count_zero | 1 |
| prereg_precedes_estimator | 1 |
| sealed_workbook_precedes_estimator | 1 |
| prereg_filesystem_readonly | 1 |
| sealed_workbook_filesystem_readonly | 1 |
| report_records_prereg_hash | 1 |
| report_records_sealed_workbook_hash | 1 |

- PREREG leaf rows: 98
- PREREG leaf mismatches: 0

## 합의 구조와 단조성 논증

ratio 후보는 명시 suffix가 있으면 mode 선택 전에 `z_mm = log(v * unit_to_mm / d)`로 변환한다. 따라서 1000 MM과 1 M은 같은 mode에 들어간다. 독립성은 record 수가 아니라 고유 source handle 수다. reference 위치 추정은 display label을 쓰지 않고 raw geometric span만 쓴다.

각 공간 s의 전체 후보 multiset을 D_s, 선택 mode의 지지 집합을 I_s라 두고, 모든 spatial bin은 D_s의 동일 bbox frame에서 계산한다.

`C_s = 1_coherent * (sum_I w / sum_D w) * exp(-MAD_I/tau) * (|H_support| / |H_D|) * (|B_I(D-frame)| / |B_D|)`

- D_s는 분류 뒤 어떤 경로에서도 줄이지 않는다. annotation 후보, handle conflict, ratio missing/outlier는 분모에 남는다.
- ratio 지지 handle은 unique source handle로 한 번만 센다. 동일 handle의 충돌 record는 분모에는 남고 지지 handle에는 들지 않는다.
- reference span mode 자체는 label-free다. 다만 ratio-bearing span이 ratio outlier이면 span 위치 적합에는 남되 confidence의 독립 지지 handle에는 들지 않는다. O2의 네 span은 모두 span inlier이고 세 고유 ratio-consistent handle로 HIGH를 유지한다.
- 네 비율은 [0,1]이고 candidate-frame bin을 공유한다. 의심 record가 후보를 보강하지 못하면 분모만 커지며, mode가 부분집합이면 1_coherent가 0이 된다. 내부 제거로 4/5가 4/4가 되는 경로는 없다.
- display 제거와 type 변경은 coherence ceiling을 넘지 못하고, handle 충돌은 unique-handle 지지와 coherence를 낮춘다. 지정 시험에서 tracked field 상승은 아래 수치와 같다.

## selftest 전문

```text
SELFTEST exact_scale observed=1 detail={"estimate": 2.5}
SELFTEST exact_unit_high observed=1 detail={"confidence": 1.0, "unit_status_rank": 2}
SELFTEST empty_honest observed=1 detail={"estimate_is_none": 1, "status_rank": 0, "unit_status_rank": 0}
SELFTEST truth_key_access observed=1 detail={"accessed_keys": 1}
SELFTEST corruption_reproducibility observed=1 detail={"corruption_count": 4}
SELFTEST fleet_gated_upward_zero observed=1 detail={"confidence_score": 0, "reference_confidence_score": 0, "reference_status": 0, "status": 0, "unit_status": 0}
SELFTEST denominator_cleanup_54_upward_zero observed=1 detail={"case_count": 54, "upward_total": 0}
SELFTEST mixed_unit_no_status_loss observed=1 detail={"status_downgrade_count": 0}
SELFTEST stale_label_no_status_loss observed=1 detail={"status_downgrade_count": 0}
SELFTEST z_mm_pre_mode_normalization observed=1 detail={"mm_per_raw": 2.5, "n_independent": 5, "unit_status_rank": 2}
SELFTEST unique_handle_independence observed=1 detail={"n_candidate_handles": 3, "n_independent": 2}
SELFTEST reference_span_label_free observed=1 detail={"reference_n_independent": 3, "reference_span_inlier_count": 4, "reference_status_rank": 2}
SELFTEST seeded_property_600_upward_zero observed=1 detail={"case_count": 600, "seed": 20260719, "upward_total": 0}
SELFTEST_SUMMARY observed_count=13 total=13
```

| scope | count | observed | upward |
| --- | --- | --- | --- |
| selftest | 13 | 13 | 0 |
| fixed-seed property | 600 | 600 | 0 |
| denominator cleanup sweep | 54 | 54 | 0 |

- property seed: 20260719
- property family counts: `{"display_removal": 66, "exact_duplicate": 67, "geometry_ratio_break": 67, "handle_collision": 66, "outlier_clone": 67, "reference_support_drop": 67, "stale_override": 67, "suffix_removal": 67, "type_to_grid": 66}`
- property upward counts: `{"confidence_score": 0, "reference_confidence_score": 0, "reference_status": 0, "status": 0, "unit_status": 0}`
- property cases digest: `f03048a56f3f289e0660461e77ffa03e8da6eef5bb69f7c5af79538eb3b6a207`

## 함대 probe 수치

### P0_first_fleet_live_counterexample

| version | phase | confidence | reference confidence | status | unit | reference | n | reference n | upward total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1 | before | 0.6 | 0.6 | LOW | LOW | LOW | 3 | 3 | 0 |
| v1 | after | 0.45 | 0.8 | HIGH | LOW | HIGH | 3 | 4 | 3 |
| v2 | before | 0.6 | 0.6 | LOW | LOW | LOW | 3 | 3 | 0 |
| v2 | after | 0.45 | 0.6 | LOW | LOW | LOW | 3 | 3 | 0 |
| v3 | before | 1 | 1 | HIGH | HIGH | HIGH | 3 | 3 | 0 |
| v3 | after | 0 | 0.75 | HIGH | LOW | HIGH | 3 | 3 | 0 |

### B1_type_to_grid

| version | phase | confidence | reference confidence | status | unit | reference | n | reference n | upward total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1 | before | 0.6 | 0.6 | LOW | LOW | LOW | 3 | 3 | 0 |
| v1 | after | 0.6 | 0.8 | HIGH | LOW | HIGH | 3 | 4 | 3 |
| v2 | before | 0.6 | 0.6 | LOW | LOW | LOW | 3 | 3 | 0 |
| v2 | after | 0.6 | 0.8 | HIGH | LOW | HIGH | 3 | 4 | 3 |
| v3 | before | 1 | 1 | HIGH | HIGH | HIGH | 3 | 3 | 0 |
| v3 | after | 1 | 1 | HIGH | HIGH | HIGH | 3 | 4 | 0 |

### B2_display_removal

| version | phase | confidence | reference confidence | status | unit | reference | n | reference n | upward total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1 | before | 0.6 | 0.6 | LOW | LOW | LOW | 3 | 3 | 0 |
| v1 | after | 0.6 | 0.8 | HIGH | LOW | HIGH | 3 | 4 | 3 |
| v2 | before | 0.6 | 0.6 | LOW | LOW | LOW | 3 | 3 | 0 |
| v2 | after | 0.6 | 0.8 | HIGH | LOW | HIGH | 3 | 4 | 3 |
| v3 | before | 1 | 1 | HIGH | HIGH | HIGH | 3 | 3 | 0 |
| v3 | after | 0 | 0.75 | HIGH | LOW | HIGH | 3 | 3 | 0 |

### B3_handle_collision

| version | phase | confidence | reference confidence | status | unit | reference | n | reference n | upward total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1 | before | 0.6 | 0.6 | LOW | LOW | LOW | 3 | 3 | 0 |
| v1 | after | 0.45 | 0.8 | HIGH | LOW | HIGH | 3 | 4 | 3 |
| v2 | before | 0.6 | 0.6 | LOW | LOW | LOW | 3 | 3 | 0 |
| v2 | after | 0.45 | 0.8 | HIGH | LOW | HIGH | 3 | 4 | 3 |
| v3 | before | 1 | 1 | HIGH | HIGH | HIGH | 3 | 3 | 0 |
| v3 | after | 0 | 0 | LOW | LOW | LOW | 2 | 2 | 0 |

### B4_ratio_consistent_complete_forgery

| version | phase | confidence | reference confidence | status | unit | reference | n | reference n | upward total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1 | before | 0.6 | 0.6 | LOW | LOW | LOW | 3 | 3 | 0 |
| v1 | after | 0.8 | 0.8 | HIGH | HIGH | HIGH | 4 | 4 | 5 |
| v2 | before | 0.6 | 0.6 | LOW | LOW | LOW | 3 | 3 | 0 |
| v2 | after | 0.8 | 0.8 | HIGH | HIGH | HIGH | 4 | 4 | 5 |
| v3 | before | 1 | 1 | HIGH | HIGH | HIGH | 3 | 3 | 0 |
| v3 | after | 1 | 1 | HIGH | HIGH | HIGH | 4 | 4 | 0 |

### O1/O2 무손실

| scene | version | confidence | reference confidence | status | unit | reference | ratio n | span inliers | confidence n |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| O1_honest_mixed_unit | v1 | 0.36 | 1 | HIGH | LOW | HIGH | 3 | 5 | 5 |
| O1_honest_mixed_unit | v2 | 0.36 | 0.6 | LOW | LOW | LOW | 3 | 3 | 3 |
| O1_honest_mixed_unit | v3 | 1 | 1 | HIGH | HIGH | HIGH | 5 | 5 | 5 |
| O2_stale_label | v1 | 0.45 | 0.8 | HIGH | LOW | HIGH | 3 | 4 | 4 |
| O2_stale_label | v2 | 0.45 | 0.6 | LOW | LOW | LOW | 3 | 3 | 3 |
| O2_stale_label | v3 | 0 | 0.75 | HIGH | LOW | HIGH | 3 | 4 | 3 |

- O1 status downgrade count: 0
- O2 status downgrade count: 0
- denominator cleanup sweep: 54 cases; v3 upward `{"confidence_score": 0, "reference_confidence_score": 0, "reference_status": 0, "status": 0, "unit_status": 0}`

## B4 정보 한계 측정

B4는 판정 밴드에 포함하지 않았다. 세 개의 이미 coherent한 handle 장면에서는 score/status 상승이 0이지만, 두 handle에서 완전 위조가 세 번째 구별 불가능한 지지로 들어오는 측정은 아래처럼 남는다.

| probe | version | confidence before | confidence after | unit before | unit after | status before | status after | upward fields |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B4_information_limit_two_to_three | v1 | 0.266666666667 | 0.6 | LOW | LOW | LOW | LOW | 2 |
| B4_information_limit_two_to_three | v2 | 0.266666666667 | 0.6 | LOW | LOW | LOW | LOW | 2 |
| B4_information_limit_two_to_three | v3 | 1 | 1 | LOW | HIGH | LOW | HIGH | 3 |

## 코호트 replay 델타 전문

### l1b_200

| version | scenes | HIGH coverage | HIGH accuracy | relative error median | relative error max | unit status counts | status counts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v1 | 200 | 0.8 | 1 | 2.22044604925e-16 | 3.10862446895e-15 | {"HIGH": 160, "LOW": 40} | {"LOW": 200} |
| v2 | 200 | 0.8 | 1 | 2.22044604925e-16 | 3.10862446895e-15 | {"HIGH": 160, "LOW": 40} | {"LOW": 200} |
| v3 | 200 | 0.8 | 1 | 2.22044604925e-16 | 3.10862446895e-15 | {"HIGH": 160, "LOW": 40} | {"LOW": 200} |

Per-scale:

| version | scale | scenes | HIGH count | coverage | accuracy | relerr median | relerr max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v1 | 0.001 | 50 | 40 | 0.8 | 1 | 2.22044604925e-16 | 1.99840144433e-15 |
| v1 | 0.01 | 50 | 40 | 0.8 | 1 | 4.4408920985e-16 | 3.10862446895e-15 |
| v1 | 1 | 50 | 40 | 0.8 | 1 | 0 | 0 |
| v1 | 1000 | 50 | 40 | 0.8 | 1 | 2.22044604925e-16 | 2.22044604925e-16 |
| v2 | 0.001 | 50 | 40 | 0.8 | 1 | 2.22044604925e-16 | 1.99840144433e-15 |
| v2 | 0.01 | 50 | 40 | 0.8 | 1 | 4.4408920985e-16 | 3.10862446895e-15 |
| v2 | 1 | 50 | 40 | 0.8 | 1 | 0 | 0 |
| v2 | 1000 | 50 | 40 | 0.8 | 1 | 2.22044604925e-16 | 2.22044604925e-16 |
| v3 | 0.001 | 50 | 40 | 0.8 | 1 | 2.22044604925e-16 | 1.99840144433e-15 |
| v3 | 0.01 | 50 | 40 | 0.8 | 1 | 4.4408920985e-16 | 3.10862446895e-15 |
| v3 | 1 | 50 | 40 | 0.8 | 1 | 0 | 0 |
| v3 | 1000 | 50 | 40 | 0.8 | 1 | 2.22044604925e-16 | 2.22044604925e-16 |

Corruption upward counts:

| version | corruption | confidence_score | reference_confidence_score | status | unit_status | reference_status |
| --- | --- | --- | --- | --- | --- | --- |
| v1 | duplicate | 0 | null | 0 | 0 | 0 |
| v1 | stale_override | 0 | null | 0 | 0 | 0 |
| v1 | suffix_removal | 0 | null | 0 | 0 | 0 |
| v1 | single_outlier | 0 | null | 0 | 0 | 0 |
| v2 | duplicate | 0 | 0 | 0 | 0 | 0 |
| v2 | stale_override | 0 | 160 | 0 | 0 | 0 |
| v2 | suffix_removal | 0 | 0 | 0 | 0 | 0 |
| v2 | single_outlier | 0 | 0 | 0 | 0 | 0 |
| v3 | duplicate | 0 | 0 | 0 | 0 | 0 |
| v3 | stale_override | 0 | 0 | 0 | 0 | 0 |
| v3 | suffix_removal | 0 | 0 | 0 | 0 | 0 |
| v3 | single_outlier | 0 | 0 | 0 | 0 | 0 |

Common-field changes:

| comparison | field | changed scenes | before median/counts | after median/counts |
| --- | --- | --- | --- | --- |
| v1_to_v3 | input_anchor_count | 0 | 6 | 6 |
| v1_to_v3 | scale_kappa | 0 | 0.505 | 0.505 |
| v1_to_v3 | truth_unit_scale | 0 | 50.5 | 50.5 |
| v1_to_v3 | scale_estimate | 0 | 50.5 | 50.5 |
| v1_to_v3 | e_s | 0 | 2.22044604925e-16 | 2.22044604925e-16 |
| v1_to_v3 | relative_error | 0 | 2.22044604925e-16 | 2.22044604925e-16 |
| v1_to_v3 | confidence_score | 40 | 1 | 1 |
| v1_to_v3 | anchor_model.display_per_raw | 0 | 50.5 | 50.5 |
| v1_to_v3 | anchor_model.mm_per_raw | 0 | 50.5 | 50.5 |
| v1_to_v3 | anchor_model.consensus_weight | 0 | 1 | 1 |
| v1_to_v3 | anchor_model.log_mad | 0 | 0 | 0 |
| v1_to_v3 | anchor_model.n_independent | 0 | 6 | 6 |
| v1_to_v3 | anchor_model.n_spatial_bins | 0 | 6 | 6 |
| v1_to_v3 | anchor_model.confidence_score | 40 | 1 | 1 |
| v1_to_v3 | anchor_model.reference_span | 0 | 405 | 405 |
| v1_to_v3 | anchor_model.reference_consensus_weight | 0 | 0.166666666667 | 0.166666666667 |
| v1_to_v3 | anchor_model.reference_log_mad | 0 | 0 | 0 |
| v1_to_v3 | anchor_model.reference_n_independent | 0 | 1 | 1 |
| v1_to_v3 | anchor_model.reference_n_spatial_bins | 0 | 1 | 1 |
| v1_to_v3 | anchor_model.reference_confidence_score | 200 | 0.0111111111111 | 0 |
| v2_to_v3 | input_anchor_count | 0 | 6 | 6 |
| v2_to_v3 | scale_kappa | 0 | 0.505 | 0.505 |
| v2_to_v3 | truth_unit_scale | 0 | 50.5 | 50.5 |
| v2_to_v3 | scale_estimate | 0 | 50.5 | 50.5 |
| v2_to_v3 | e_s | 0 | 2.22044604925e-16 | 2.22044604925e-16 |
| v2_to_v3 | relative_error | 0 | 2.22044604925e-16 | 2.22044604925e-16 |
| v2_to_v3 | confidence_score | 40 | 1 | 1 |
| v2_to_v3 | anchor_model.display_per_raw | 0 | 50.5 | 50.5 |
| v2_to_v3 | anchor_model.mm_per_raw | 0 | 50.5 | 50.5 |
| v2_to_v3 | anchor_model.consensus_weight | 0 | 1 | 1 |
| v2_to_v3 | anchor_model.log_mad | 0 | 0 | 0 |
| v2_to_v3 | anchor_model.n_independent | 0 | 6 | 6 |
| v2_to_v3 | anchor_model.n_spatial_bins | 0 | 6 | 6 |
| v2_to_v3 | anchor_model.confidence_score | 40 | 1 | 1 |
| v2_to_v3 | anchor_model.reference_span | 0 | 405 | 405 |
| v2_to_v3 | anchor_model.reference_consensus_weight | 0 | 0.166666666667 | 0.166666666667 |
| v2_to_v3 | anchor_model.reference_log_mad | 0 | 0 | 0 |
| v2_to_v3 | anchor_model.reference_n_independent | 0 | 1 | 1 |
| v2_to_v3 | anchor_model.reference_n_spatial_bins | 0 | 1 | 1 |
| v2_to_v3 | anchor_model.reference_confidence_score | 200 | 0.0111111111111 | 0 |
| v1_to_v3 | status | 0 | {"LOW": 200} | {"LOW": 200} |
| v1_to_v3 | unit_status | 0 | {"HIGH": 160, "LOW": 40} | {"HIGH": 160, "LOW": 40} |
| v1_to_v3 | reference_status | 0 | {"LOW": 200} | {"LOW": 200} |
| v1_to_v3 | physical_unit | 0 | {"MM": 200} | {"MM": 200} |
| v2_to_v3 | status | 0 | {"LOW": 200} | {"LOW": 200} |
| v2_to_v3 | unit_status | 0 | {"HIGH": 160, "LOW": 40} | {"HIGH": 160, "LOW": 40} |
| v2_to_v3 | reference_status | 0 | {"LOW": 200} | {"LOW": 200} |
| v2_to_v3 | physical_unit | 0 | {"MM": 200} | {"MM": 200} |

휘발 필드 제외 수치 전 필드 동일

### c1_original_200

| version | scenes | HIGH coverage | HIGH accuracy | relative error median | relative error max | unit status counts | status counts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v1 | 200 | 0 | null | 2.22044604925e-16 | 4.4408920985e-16 | {"LOW": 200} | {"LOW": 200} |
| v2 | 200 | 0 | null | 2.22044604925e-16 | 4.4408920985e-16 | {"LOW": 200} | {"LOW": 200} |
| v3 | 200 | 1 | 1 | 2.22044604925e-16 | 4.4408920985e-16 | {"HIGH": 200} | {"HIGH": 100, "LOW": 100} |

Per-scale:

| version | scale | scenes | HIGH count | coverage | accuracy | relerr median | relerr max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v1 | 0.001 | 50 | 0 | 0 | null | 2.22044604925e-16 | 2.22044604925e-16 |
| v1 | 0.01 | 50 | 0 | 0 | null | 4.4408920985e-16 | 4.4408920985e-16 |
| v1 | 1 | 50 | 0 | 0 | null | 0 | 0 |
| v1 | 1000 | 50 | 0 | 0 | null | 2.22044604925e-16 | 2.22044604925e-16 |
| v2 | 0.001 | 50 | 0 | 0 | null | 2.22044604925e-16 | 2.22044604925e-16 |
| v2 | 0.01 | 50 | 0 | 0 | null | 4.4408920985e-16 | 4.4408920985e-16 |
| v2 | 1 | 50 | 0 | 0 | null | 0 | 0 |
| v2 | 1000 | 50 | 0 | 0 | null | 2.22044604925e-16 | 2.22044604925e-16 |
| v3 | 0.001 | 50 | 50 | 1 | 1 | 2.22044604925e-16 | 2.22044604925e-16 |
| v3 | 0.01 | 50 | 50 | 1 | 1 | 4.4408920985e-16 | 4.4408920985e-16 |
| v3 | 1 | 50 | 50 | 1 | 1 | 0 | 0 |
| v3 | 1000 | 50 | 50 | 1 | 1 | 2.22044604925e-16 | 2.22044604925e-16 |

Corruption upward counts:

| version | corruption | confidence_score | reference_confidence_score | status | unit_status | reference_status |
| --- | --- | --- | --- | --- | --- | --- |
| v1 | duplicate | 0 | null | 0 | 0 | 0 |
| v1 | stale_override | 0 | null | 0 | 0 | 0 |
| v1 | suffix_removal | 0 | null | 0 | 0 | 0 |
| v1 | single_outlier | 0 | null | 26 | 0 | 26 |
| v2 | duplicate | 0 | 0 | 0 | 0 | 0 |
| v2 | stale_override | 0 | 0 | 0 | 0 | 0 |
| v2 | suffix_removal | 0 | 0 | 0 | 0 | 0 |
| v2 | single_outlier | 0 | 0 | 0 | 0 | 0 |
| v3 | duplicate | 0 | 0 | 0 | 0 | 0 |
| v3 | stale_override | 0 | 0 | 0 | 0 | 0 |
| v3 | suffix_removal | 0 | 0 | 0 | 0 | 0 |
| v3 | single_outlier | 0 | 0 | 0 | 0 | 0 |

Common-field changes:

| comparison | field | changed scenes | before median/counts | after median/counts |
| --- | --- | --- | --- | --- |
| v1_to_v3 | input_anchor_count | 0 | 4.5 | 4.5 |
| v1_to_v3 | scale_kappa | 0 | 0.505 | 0.505 |
| v1_to_v3 | truth_unit_scale | 0 | 50.5 | 50.5 |
| v1_to_v3 | scale_estimate | 0 | 50.5 | 50.5 |
| v1_to_v3 | e_s | 0 | 2.22044604925e-16 | 2.22044604925e-16 |
| v1_to_v3 | relative_error | 0 | 2.22044604925e-16 | 2.22044604925e-16 |
| v1_to_v3 | confidence_score | 200 | 0.6 | 1 |
| v1_to_v3 | anchor_model.display_per_raw | 0 | 50.5 | 50.5 |
| v1_to_v3 | anchor_model.mm_per_raw | 0 | 50.5 | 50.5 |
| v1_to_v3 | anchor_model.consensus_weight | 0 | 1 | 1 |
| v1_to_v3 | anchor_model.log_mad | 0 | 0 | 0 |
| v1_to_v3 | anchor_model.n_independent | 0 | 3 | 3 |
| v1_to_v3 | anchor_model.n_spatial_bins | 0 | 3 | 3 |
| v1_to_v3 | anchor_model.confidence_score | 200 | 0.6 | 1 |
| v1_to_v3 | anchor_model.reference_span | 0 | 505 | 505 |
| v1_to_v3 | anchor_model.reference_consensus_weight | 0 | 0.857142857143 | 0.857142857143 |
| v1_to_v3 | anchor_model.reference_log_mad | 0 | 0 | 0 |
| v1_to_v3 | anchor_model.reference_n_independent | 0 | 3 | 3 |
| v1_to_v3 | anchor_model.reference_n_spatial_bins | 0 | 3 | 3 |
| v1_to_v3 | anchor_model.reference_confidence_score | 200 | 0.514285714286 | 0.5 |
| v2_to_v3 | input_anchor_count | 0 | 4.5 | 4.5 |
| v2_to_v3 | scale_kappa | 0 | 0.505 | 0.505 |
| v2_to_v3 | truth_unit_scale | 0 | 50.5 | 50.5 |
| v2_to_v3 | scale_estimate | 0 | 50.5 | 50.5 |
| v2_to_v3 | e_s | 0 | 2.22044604925e-16 | 2.22044604925e-16 |
| v2_to_v3 | relative_error | 0 | 2.22044604925e-16 | 2.22044604925e-16 |
| v2_to_v3 | confidence_score | 200 | 0.6 | 1 |
| v2_to_v3 | anchor_model.display_per_raw | 0 | 50.5 | 50.5 |
| v2_to_v3 | anchor_model.mm_per_raw | 0 | 50.5 | 50.5 |
| v2_to_v3 | anchor_model.consensus_weight | 0 | 1 | 1 |
| v2_to_v3 | anchor_model.log_mad | 0 | 0 | 0 |
| v2_to_v3 | anchor_model.n_independent | 0 | 3 | 3 |
| v2_to_v3 | anchor_model.n_spatial_bins | 0 | 3 | 3 |
| v2_to_v3 | anchor_model.confidence_score | 200 | 0.6 | 1 |
| v2_to_v3 | anchor_model.reference_span | 0 | 505 | 505 |
| v2_to_v3 | anchor_model.reference_consensus_weight | 0 | 0.857142857143 | 0.857142857143 |
| v2_to_v3 | anchor_model.reference_log_mad | 0 | 0 | 0 |
| v2_to_v3 | anchor_model.reference_n_independent | 0 | 3 | 3 |
| v2_to_v3 | anchor_model.reference_n_spatial_bins | 0 | 3 | 3 |
| v2_to_v3 | anchor_model.reference_confidence_score | 200 | 0.514285714286 | 0.5 |
| v1_to_v3 | status | 100 | {"LOW": 200} | {"HIGH": 100, "LOW": 100} |
| v1_to_v3 | unit_status | 200 | {"LOW": 200} | {"HIGH": 200} |
| v1_to_v3 | reference_status | 100 | {"LOW": 200} | {"HIGH": 100, "LOW": 100} |
| v1_to_v3 | physical_unit | 0 | {"MM": 200} | {"MM": 200} |
| v2_to_v3 | status | 100 | {"LOW": 200} | {"HIGH": 100, "LOW": 100} |
| v2_to_v3 | unit_status | 200 | {"LOW": 200} | {"HIGH": 200} |
| v2_to_v3 | reference_status | 100 | {"LOW": 200} | {"HIGH": 100, "LOW": 100} |
| v2_to_v3 | physical_unit | 0 | {"MM": 200} | {"MM": 200} |

휘발 필드 제외 수치 전 필드 동일

## 26→0 및 무수정 기록

| metric | v1 | v2 | v3 |
| --- | --- | --- | --- |
| C1 single_outlier status upward | 26 | 0 | 0 |
| C1 single_outlier reference upward | 26 | 0 | 0 |
| L1b all corruption tracked upward | 0 | 160 | 0 |

- source manifest mismatch count: 0
- source manifest before digest: `d3ec35395fffa168a9d0bf246ba9bbd07dcea4e4033117bd6b3dbba1286f0c16`
- source manifest after digest: `d3ec35395fffa168a9d0bf246ba9bbd07dcea4e4033117bd6b3dbba1286f0c16`

## 산출물 SHA

- c1v5_results.json: `3d882d6e35facbe5ce54c7d223cb3963b9910e9f71625acdcc4ba650b65fe9d8`
- evidence.xlsx: `855915d3f211adb1161ac1a6d491ca4d4b8f0f6dabcedbb09ac47a884366ad64`
- evidence_sealed.xlsx: `0d1f30762546ece2a2b0233f46410f78edb8f69c99b6512d251cc519ba2d4cf4`
- feyerabend_c1_v3.py: `ba7adddb508f1f52ed0e9f2e538a9de564ae70c876981cc09fbca6dd7ece555e`
- fleet_probe_results.json: `5397807743034328f550ebd3709f1534046c4f29eb29a06c819c6277fdc366de`
- loop_l1d.py: `9824251ca6223be7ac0bc9ab7a9008859e608291f59af3b16f8ecb0fa1dcf9c7`
- prereg.json: `474cf61bb8d8856d62e161444b091bd0f501e8fda30d116612608974db6524c1`
- replay_delta.json: `a60582c640b0c6cf7ba46ae50bd4984d1ba06713d356241059a5f356d29efc00`

## 미해결

- B4처럼 진짜 지지와 관측 분포가 같은 완전 위조는 식별할 수 없다. 두 handle→세 handle 측정에서 이 한계를 수치로 남겼다.
- strict coherence confidence는 multi-mode reference span의 정상 status를 보수적으로 유지한다. 두 코호트의 v1/v2/v3 정상 수치 변화는 위 표와 replay_delta.json에 모두 기록했다.
- 600종 결과는 봉인된 9-family 문법, seed 20260719, 두 200-scene pool에 대한 결과다. 지정 scope 밖 입력 전체에 대한 문언은 사용하지 않는다.
- 이 보고서는 수치와 구조 논증을 기록하며 별도의 게이트 판정 문자열을 출력하지 않는다.

LOOP_COMPLETE: L1d
