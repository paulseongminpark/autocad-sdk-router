# E2 Loop L1b — 혼합 모집단 C0/C1 재평가

## 설계 및 실행 경계

- base 50은 seed-derived rank로 anchor-rich 40, single-span 10에 배정했다.
- anchor-rich 장면은 L1의 5~8 independent-span DIM builder를 그대로 재사용했고, single-span 장면은 한 region의 동일 reference span DIM 2개를 사용했다.
- C0 구조 생성, 4-scale 복제, fidelity, truth validator와 C1 estimator, 네 corruption, pair-label permutation은 read-only import로 실행했다.
- 쓰기는 `D:\runs\e2_program\cells\loop_l1b` 아래에만 수행했고 source CAD/test split 접근 수는 각각 0이다.
- 아래에는 측정값과 selftest 기록만 수록한다.

## feyerabend_P2 지정 mutation family 1:1 대조

원문 위치: `D:\dev\99_tools\autocad-sdk-router\reports\e2\dossiers\feyerabend_P2.md` lines 550-561. 결합 표기된 단일·다중 reference span 항목은 두 manifest family로 분리했다.

| dossier family | manifest family | v1 | L1 | v3 | v3-v1 | v3-L1 |
| --- | --- | --- | --- | --- | --- | --- |
| 순수 LINE 평행쌍 | pure_line_parallel_pair | 21 | 21 | 21 | 0 | 0 |
| LWPOLYLINE 분절 | lwpolyline_segmentation | 25 | 25 | 25 | 0 | 0 |
| ARC/SPLINE 인접 또는 교란 | arc_spline_adjacent_or_distractor | 50 | 50 | 50 | 0 | 0 |
| HATCH boundary 교란 | hatch_boundary_distractor | 50 | 50 | 50 | 0 | 0 |
| nested INSERT와 non-uniform/누적 transform | nested_insert_nonuniform_accumulated_transform | 50 | 50 | 50 | 0 | 0 |
| 부분 overlap과 거의 평행한 조각 | partial_overlap_near_parallel_fragment | 50 | 50 | 50 | 0 | 0 |
| door/window/dimension-like 긴 평행 distractor | door_window_dimension_long_parallel_distractor | 49 | 49 | 49 | 0 | 0 |
| zero-wall sentinel | zero_wall_sentinel | 1 | 1 | 1 | 0 | 0 |
| all-wall sentinel | all_wall_sentinel | 1 | 1 | 1 | 0 | 0 |
| 단일 reference span 영역 | single_reference_span_region | 25 | 0 | 10 | -15 | 10 |
| 다중 reference span 영역 | multiple_reference_span_regions | 25 | 50 | 40 | 15 | -10 |

## 혼합 모집단 실측

| metric | value |
| --- | --- |
| base_population_counts | {"anchor_rich": 40, "single_span": 10} |
| ir_population_counts | {"anchor_rich": 160, "single_span": 40} |
| single_span_indices | [0, 2, 7, 19, 21, 23, 30, 35, 36, 41] |
| population_assignment_digest | 985342caf26bdbbf19a27862a1d72d272b3db81aa2c1d18494e322a41435a6c5 |
| base_anchor_count_distribution | {"2": 10, "5": 12, "6": 11, "7": 5, "8": 12} |
| base_unit_status_counts | {"HIGH": 40, "LOW": 10} |
| base_unit_status_counts_by_population | {"anchor_rich": {"HIGH": 40}, "single_span": {"LOW": 10}} |
| single_span_unit_HIGH_scene_count | 0 |
| single_span_unit_LOW_or_NONE_scene_count | 10 |
| anchor_rich_unit_HIGH_scene_count | 40 |
| anchor_count_rule_mismatch_scene_count | 0 |
| distinct_span_rule_mismatch_scene_count | 0 |
| mutation_population_role_mismatch_scene_count | 0 |

## Selftest 전문

```text
=== loop_l1b mixed-population selftest ===
SELFTEST dossier_family_mapping_one_to_one: PASS | dossier_rows=11 c0_families=11
SELFTEST population_cardinality: PASS | anchor_rich=40 single_span=10
SELFTEST population_assignment_seed_deterministic: PASS | single_indices=[0, 2, 7, 19, 21, 23, 30, 35, 36, 41] digest=9594d33c8cfee09de24a58fad32b1eb4726e129282e132a4fc79612bf4307f71
SELFTEST single_span_same_j_same_sha: PASS | j=0 sha256=a5ada097be258a83a2fbe36826bd8facc9f29fac987b299f02f649c7b8ee4943
SELFTEST anchor_rich_same_j_same_sha: PASS | j=1 sha256=0d60cc82d5e80695ca5f810d4d599946425c155efb249af8a25dd16df9b3cac3
SELFTEST single_span_structure: PASS | anchors=2 regions=1 distinct_spans=1
SELFTEST single_span_canonical_low_representation: PASS | canonical=2 unit_status=LOW confidence=0.266666666667
SELFTEST anchor_rich_l1_rule: PASS | anchors=8 canonical=8 duplicates=0
SELFTEST anchor_rich_independent_spans_bins: PASS | distinct_spans=8 bins=8
SELFTEST anchor_rich_scale_estimate: PASS | estimate=1.0 unit_status=HIGH confidence=1
SELFTEST single_span_four_scale_topology: PASS | topology_unique=1 normalized_geometry_unique=1
SELFTEST single_span_single_outlier_no_reverse_transition: PASS | four_scale_reverse_transition_count=0
SELFTEST truth_validator_positive_cases: PASS | scene_count=4 error_count=0
SELFTEST truth_validator_negative_case_honest_fail: PASS | error_count=5
SELFTEST all_base_population_rules: PASS | distribution={2: 10, 5: 12, 6: 11, 7: 5, 8: 12} role_errors=0 rich_bin_errors=0
SELFTEST permitted_gen2_synthetic_fixture: PASS | wall_records=2 entity_types=['ARC', 'CIRCLE', 'HATCH', 'LINE', 'LWPOLYLINE', 'MTEXT', 'SPLINE', 'TEXT']
=== imported sealed C1 selftests ===
SELFTEST exact_anchor_exact_scale: PASS | estimate=2.5 expected=2.5 unit_status=HIGH
SELFTEST exact_anchor_high_confidence: PASS | unit_status=HIGH confidence=1
SELFTEST no_anchor_honest_no_estimate: PASS | estimate=None unit_status=NONE status=NONE
SELFTEST corruption_reproducibility: PASS | duplicate=b7eafb24bff4 stale_override=4587fb707ef7 suffix_removal=d5721ef40250 single_outlier=802397c8b4a3
SELFTEST single_outlier_mode_or_downgrade: PASS | estimate=2.5 unit_status=HIGH
SELFTEST truth_key_access_guard: PASS | accessed_keys=['anchors']
SELFTEST SUMMARY: 6/6 passed
SELFTEST sealed_c1_selftests: PASS | passed=6 total=6
SELFTEST SUMMARY: 17/17 passed
SELFTEST_RESULT: PASS
```

## C0 v1 / L1 / L1b-v3 델타

| metric | v1 | L1 | L1b-v3 | v3-v1 | v3-L1 |
| --- | --- | --- | --- | --- | --- |
| scene_counts.base_scene_count | 50 | 50 | 50 | 0 | 0 |
| scene_counts.ir_scene_count | 200 | 200 | 200 | 0 | 0 |
| truth_pair_numbers.ir_truth_pair_count | 204 | 204 | 204 | 0 | 0 |
| truth_validator.error_count | 0 | 0 | 0 | 0 | 0 |
| fidelity_numbers_kappa_1.entity_mix_tv | 0.000211914583407 | 0.000211914583407 | 0.000211914583407 | 0 | 0 |
| fidelity_numbers_kappa_1.thickness_histogram_ks | 0.0402878554373 | 0.0402878554373 | 0.0402878554373 | 0 | 0 |
| determinism_and_scale_numbers.four_scale_topology_mismatch_base_scene_count | 0 | 0 | 0 | 0 | 0 |
| determinism_and_scale_numbers.four_scale_normalized_geometry_mismatch_base_scene_count | 0 | 0 | 0 | 0 | 0 |
| determinism_and_scale_numbers.four_scale_source_handle_mismatch_base_scene_count | 0 | 0 | 0 | 0 | 0 |
| mutation_family_coverage.pure_line_parallel_pair.scene_count | 21 | 21 | 21 | 0 | 0 |
| mutation_family_coverage.lwpolyline_segmentation.scene_count | 25 | 25 | 25 | 0 | 0 |
| mutation_family_coverage.arc_spline_adjacent_or_distractor.scene_count | 50 | 50 | 50 | 0 | 0 |
| mutation_family_coverage.hatch_boundary_distractor.scene_count | 50 | 50 | 50 | 0 | 0 |
| mutation_family_coverage.nested_insert_nonuniform_accumulated_transform.scene_count | 50 | 50 | 50 | 0 | 0 |
| mutation_family_coverage.partial_overlap_near_parallel_fragment.scene_count | 50 | 50 | 50 | 0 | 0 |
| mutation_family_coverage.door_window_dimension_long_parallel_distractor.scene_count | 49 | 49 | 49 | 0 | 0 |
| mutation_family_coverage.zero_wall_sentinel.scene_count | 1 | 1 | 1 | 0 | 0 |
| mutation_family_coverage.all_wall_sentinel.scene_count | 1 | 1 | 1 | 0 | 0 |
| mutation_family_coverage.single_reference_span_region.scene_count | 25 | 0 | 10 | -15 | 10 |
| mutation_family_coverage.multiple_reference_span_regions.scene_count | 25 | 50 | 40 | 15 | -10 |

## C1 v1 / L1 / L1b-v3 델타

| metric | v1 | L1 | L1b-v3 | v3-v1 | v3-L1 |
| --- | --- | --- | --- | --- | --- |
| estimate_count | 200 | 200 | 200 | 0 | 0 |
| estimate_coverage | 1 | 1 | 1 | 0 | 0 |
| accuracy_within_5pct | 1 | 1 | 1 | 0 | 0 |
| HIGH_scene_count | 0 | 200 | 160 | 160 | -40 |
| HIGH_coverage | 0 | 1 | 0.8 | 0.8 | -0.2 |
| HIGH_accuracy_within_5pct | null | 1 | 1 | null | 0 |
| pair_label_mismatch_scene_count | 0 | 0 | 0 | 0 | 0 |
| single_outlier_LOW_to_HIGH_status_count | 26 | 0 | 0 | -26 | 0 |
| single_outlier_scale_estimate_unchanged_count | 200 | 200 | 200 | 0 | 0 |
| single_outlier_confidence_or_status_increased_count | null | 0 | 0 | null | 0 |

## C0v3 fidelity·truth·4-scale topology 수치 전문

```json
{
  "anchor_richness": {
    "anchor_count_rule": "single_span=2 repeated-span DIM anchors in one region; anchor_rich=5+(uint32_seed mod 4) independent-span DIM anchors",
    "anchor_rich_indices": [
      1,
      3,
      4,
      5,
      6,
      8,
      9,
      10,
      11,
      12,
      13,
      14,
      15,
      16,
      17,
      18,
      20,
      22,
      24,
      25,
      26,
      27,
      28,
      29,
      31,
      32,
      33,
      34,
      37,
      38,
      39,
      40,
      42,
      43,
      44,
      45,
      46,
      47,
      48,
      49
    ],
    "anchor_rich_unit_HIGH_scene_count": 40,
    "assignment_rows": [
      {
        "anchor_count": 2,
        "assignment_rank": 6,
        "assignment_sha256": "3b11386b2a500520f1ac5c75ca1498e99d7197b8dc919a04a90f5c29553b3040",
        "base_scene_index": 0,
        "canonical_anchor_count": 2,
        "confidence_score": 0.26666666666666666,
        "distinct_span_count": 1,
        "duplicate_count": 0,
        "population": "single_span",
        "reference_status": "LOW",
        "region_count": 1,
        "seed": 2579264387,
        "spatial_bin_count": 2,
        "status": "LOW",
        "unit_status": "LOW"
      },
      {
        "anchor_count": 8,
        "assignment_rank": 39,
        "assignment_sha256": "d8f791bded82a1a9e8be13100011977d5adeb06901993f09f2e6ed8114fc1832",
        "base_scene_index": 1,
        "canonical_anchor_count": 8,
        "confidence_score": 1.0,
        "distinct_span_count": 8,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 8,
        "seed": 2175310079,
        "spatial_bin_count": 8,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 2,
        "assignment_rank": 5,
        "assignment_sha256": "31b0e6efb5c4b2fbb9f09db7c9d8f0c515fcd0ff3d12b4a4ac9a203269042be4",
        "base_scene_index": 2,
        "canonical_anchor_count": 2,
        "confidence_score": 0.26666666666666666,
        "distinct_span_count": 1,
        "duplicate_count": 0,
        "population": "single_span",
        "reference_status": "LOW",
        "region_count": 1,
        "seed": 1238512056,
        "spatial_bin_count": 2,
        "status": "LOW",
        "unit_status": "LOW"
      },
      {
        "anchor_count": 8,
        "assignment_rank": 41,
        "assignment_sha256": "e35c32bdbf8364117bd5bd7a0a4e592a67b159a25d2a8b9d799717d88c9b73d8",
        "base_scene_index": 3,
        "canonical_anchor_count": 8,
        "confidence_score": 1.0,
        "distinct_span_count": 8,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 8,
        "seed": 3623221751,
        "spatial_bin_count": 8,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 6,
        "assignment_rank": 42,
        "assignment_sha256": "ee38850e723c5415e1cf0a3c8db8287f1752d45bba9bb661181b0af67296c222",
        "base_scene_index": 4,
        "canonical_anchor_count": 6,
        "confidence_score": 1.0,
        "distinct_span_count": 6,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 6,
        "seed": 1164026453,
        "spatial_bin_count": 6,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 6,
        "assignment_rank": 18,
        "assignment_sha256": "69fb71afad2ad46f3d78036b13d30307eb32e83a46edbb40f8c6bbc225c4e498",
        "base_scene_index": 5,
        "canonical_anchor_count": 6,
        "confidence_score": 1.0,
        "distinct_span_count": 6,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 6,
        "seed": 2322356813,
        "spatial_bin_count": 6,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 5,
        "assignment_rank": 33,
        "assignment_sha256": "b0ae5a42bdc753ba60def7bc6d8c7414bc6ecac6189afe74925ad90dc83fe132",
        "base_scene_index": 6,
        "canonical_anchor_count": 5,
        "confidence_score": 1.0,
        "distinct_span_count": 5,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 5,
        "seed": 3614728296,
        "spatial_bin_count": 5,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 2,
        "assignment_rank": 1,
        "assignment_sha256": "0709b3b4a096446a4dc2c1d13b40576eaa7343c28da6b0f1d9dd1e1d034f0eb2",
        "base_scene_index": 7,
        "canonical_anchor_count": 2,
        "confidence_score": 0.26666666666666666,
        "distinct_span_count": 1,
        "duplicate_count": 0,
        "population": "single_span",
        "reference_status": "LOW",
        "region_count": 1,
        "seed": 1680878578,
        "spatial_bin_count": 2,
        "status": "LOW",
        "unit_status": "LOW"
      },
      {
        "anchor_count": 8,
        "assignment_rank": 36,
        "assignment_sha256": "c64677e4c18d2b2fe43b220e862e42435d6e8f8df4365ffb055742a3bb9fb7bc",
        "base_scene_index": 8,
        "canonical_anchor_count": 8,
        "confidence_score": 1.0,
        "distinct_span_count": 8,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 8,
        "seed": 655892663,
        "spatial_bin_count": 8,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 7,
        "assignment_rank": 43,
        "assignment_sha256": "f213fb516157682654894e91c6c6d5b3cf9be0fa3ad3875972804da0b665ce5b",
        "base_scene_index": 9,
        "canonical_anchor_count": 7,
        "confidence_score": 1.0,
        "distinct_span_count": 7,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 7,
        "seed": 2688489590,
        "spatial_bin_count": 7,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 5,
        "assignment_rank": 28,
        "assignment_sha256": "9fb9a370d60f1036504cb943e2c1e8c1bd24f60344969c70d1ce0e618bdeb46d",
        "base_scene_index": 10,
        "canonical_anchor_count": 5,
        "confidence_score": 1.0,
        "distinct_span_count": 5,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 5,
        "seed": 1637753000,
        "spatial_bin_count": 5,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 5,
        "assignment_rank": 10,
        "assignment_sha256": "499ecc08f9a50c622bcaeb74473fb239603e759c39c79037fedd8cbcd94c9360",
        "base_scene_index": 11,
        "canonical_anchor_count": 5,
        "confidence_score": 1.0,
        "distinct_span_count": 5,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 5,
        "seed": 775223852,
        "spatial_bin_count": 5,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 6,
        "assignment_rank": 16,
        "assignment_sha256": "5cca9ce93495fad961ffd5d22258d24cceed9cb60f56b5a71a09037f38b37623",
        "base_scene_index": 12,
        "canonical_anchor_count": 6,
        "confidence_score": 1.0,
        "distinct_span_count": 6,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 6,
        "seed": 1345536637,
        "spatial_bin_count": 6,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 8,
        "assignment_rank": 47,
        "assignment_sha256": "f956d23aea01ee6879c3ee384d7cf8a32940399b4879f582100dc32e223bae69",
        "base_scene_index": 13,
        "canonical_anchor_count": 8,
        "confidence_score": 1.0,
        "distinct_span_count": 8,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 8,
        "seed": 43528507,
        "spatial_bin_count": 8,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 5,
        "assignment_rank": 26,
        "assignment_sha256": "9bc399124efac9ea5f417f129928f3e7adb370a3be6a778427efa9728fd02ea2",
        "base_scene_index": 14,
        "canonical_anchor_count": 5,
        "confidence_score": 1.0,
        "distinct_span_count": 5,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 5,
        "seed": 4026241112,
        "spatial_bin_count": 5,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 8,
        "assignment_rank": 40,
        "assignment_sha256": "de4f7c9bdf9538a7c0c2e0f9941f9e060192cc30e6ad3ab209fc558a5d02a06d",
        "base_scene_index": 15,
        "canonical_anchor_count": 8,
        "confidence_score": 1.0,
        "distinct_span_count": 8,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 8,
        "seed": 3140045299,
        "spatial_bin_count": 8,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 6,
        "assignment_rank": 49,
        "assignment_sha256": "fa1cd2247927a27da2958b03b044ab17025220f9f88885f67893c5da0c9dfb75",
        "base_scene_index": 16,
        "canonical_anchor_count": 6,
        "confidence_score": 1.0,
        "distinct_span_count": 6,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 6,
        "seed": 452683653,
        "spatial_bin_count": 6,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 7,
        "assignment_rank": 27,
        "assignment_sha256": "9be29e8a13f700fab73040fc9c279e4c8234744918539fdf5212c4505267145d",
        "base_scene_index": 17,
        "canonical_anchor_count": 7,
        "confidence_score": 1.0,
        "distinct_span_count": 7,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 7,
        "seed": 3960550950,
        "spatial_bin_count": 7,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 8,
        "assignment_rank": 37,
        "assignment_sha256": "cfbe9e90e852e34fdcac7d88d444def39f45d6c9af41cb717c9ab469c26bf23a",
        "base_scene_index": 18,
        "canonical_anchor_count": 8,
        "confidence_score": 1.0,
        "distinct_span_count": 8,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 8,
        "seed": 1176518943,
        "spatial_bin_count": 8,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 2,
        "assignment_rank": 3,
        "assignment_sha256": "1fc07f8a61dd6b45e6e071afb4ebbfc050c1a0552a378e068263986b63620e42",
        "base_scene_index": 19,
        "canonical_anchor_count": 2,
        "confidence_score": 0.26666666666666666,
        "distinct_span_count": 1,
        "duplicate_count": 0,
        "population": "single_span",
        "reference_status": "LOW",
        "region_count": 1,
        "seed": 3195681529,
        "spatial_bin_count": 2,
        "status": "LOW",
        "unit_status": "LOW"
      },
      {
        "anchor_count": 5,
        "assignment_rank": 23,
        "assignment_sha256": "8a793f63ae2dcf90a9b2d2f5a255de72b252fe618930bf19452e49addfdcfd45",
        "base_scene_index": 20,
        "canonical_anchor_count": 5,
        "confidence_score": 1.0,
        "distinct_span_count": 5,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 5,
        "seed": 2533520920,
        "spatial_bin_count": 5,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 2,
        "assignment_rank": 8,
        "assignment_sha256": "4745f016b24ecdc57ac3a87ccacb077ca473ffb7b329ce5ce171d9cc698676cb",
        "base_scene_index": 21,
        "canonical_anchor_count": 2,
        "confidence_score": 0.26666666666666666,
        "distinct_span_count": 1,
        "duplicate_count": 0,
        "population": "single_span",
        "reference_status": "LOW",
        "region_count": 1,
        "seed": 771590475,
        "spatial_bin_count": 2,
        "status": "LOW",
        "unit_status": "LOW"
      },
      {
        "anchor_count": 7,
        "assignment_rank": 11,
        "assignment_sha256": "49d317f460a2a1afcefa063666d5e40e002099e8a5b2a6111d5bc2094843d136",
        "base_scene_index": 22,
        "canonical_anchor_count": 7,
        "confidence_score": 1.0,
        "distinct_span_count": 7,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 7,
        "seed": 1579898858,
        "spatial_bin_count": 7,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 2,
        "assignment_rank": 7,
        "assignment_sha256": "3cf5d6225d92b8a5c9d6d909debb2db643c63c4cfd54d9e6b667dbdb22b475a2",
        "base_scene_index": 23,
        "canonical_anchor_count": 2,
        "confidence_score": 0.26666666666666666,
        "distinct_span_count": 1,
        "duplicate_count": 0,
        "population": "single_span",
        "reference_status": "LOW",
        "region_count": 1,
        "seed": 2258398904,
        "spatial_bin_count": 2,
        "status": "LOW",
        "unit_status": "LOW"
      },
      {
        "anchor_count": 6,
        "assignment_rank": 19,
        "assignment_sha256": "726a14f36ee78eeaf5b90e18917649896a56ebf2594c314c66bf4af08000d94a",
        "base_scene_index": 24,
        "canonical_anchor_count": 6,
        "confidence_score": 1.0,
        "distinct_span_count": 6,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 6,
        "seed": 121987957,
        "spatial_bin_count": 6,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 6,
        "assignment_rank": 32,
        "assignment_sha256": "abf6ceb6bf586ba0169fd5ea42791f2f0501e64dee9b5a5cf2c4e15807de9331",
        "base_scene_index": 25,
        "canonical_anchor_count": 6,
        "confidence_score": 1.0,
        "distinct_span_count": 6,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 6,
        "seed": 4289599885,
        "spatial_bin_count": 6,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 8,
        "assignment_rank": 30,
        "assignment_sha256": "a5fa652b4142e768a1bf352455b49025b6eb1e70ec37b6a8043b025183da7673",
        "base_scene_index": 26,
        "canonical_anchor_count": 8,
        "confidence_score": 1.0,
        "distinct_span_count": 8,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 8,
        "seed": 1313174351,
        "spatial_bin_count": 8,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 6,
        "assignment_rank": 20,
        "assignment_sha256": "78fe1589b39953df23fbbc5ba35a814aedaa2da58f29b8da983e64ea16f0072a",
        "base_scene_index": 27,
        "canonical_anchor_count": 6,
        "confidence_score": 1.0,
        "distinct_span_count": 6,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 6,
        "seed": 614866957,
        "spatial_bin_count": 6,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 5,
        "assignment_rank": 22,
        "assignment_sha256": "7f35c1e87ac0b21081b133594f3e3f2fd8cfbab1a312b0ddefd5a7fe8a9b8538",
        "base_scene_index": 28,
        "canonical_anchor_count": 5,
        "confidence_score": 1.0,
        "distinct_span_count": 5,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 5,
        "seed": 210433964,
        "spatial_bin_count": 5,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 5,
        "assignment_rank": 25,
        "assignment_sha256": "9933ee2958c6a79f1187fce97f06368e85ed76c263a3a72ed679c28f9da7984d",
        "base_scene_index": 29,
        "canonical_anchor_count": 5,
        "confidence_score": 1.0,
        "distinct_span_count": 5,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 5,
        "seed": 3083102844,
        "spatial_bin_count": 5,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 2,
        "assignment_rank": 2,
        "assignment_sha256": "103d64355cf44c72fe62fe4cf4c854e761276cf87defcf0daf975d8e10deff51",
        "base_scene_index": 30,
        "canonical_anchor_count": 2,
        "confidence_score": 0.26666666666666666,
        "distinct_span_count": 1,
        "duplicate_count": 0,
        "population": "single_span",
        "reference_status": "LOW",
        "region_count": 1,
        "seed": 187924334,
        "spatial_bin_count": 2,
        "status": "LOW",
        "unit_status": "LOW"
      },
      {
        "anchor_count": 8,
        "assignment_rank": 15,
        "assignment_sha256": "54fa000f1e2988670e57ccd9d3109d4b6e2a3c3f5652dc41c177140a009f6e0c",
        "base_scene_index": 31,
        "canonical_anchor_count": 8,
        "confidence_score": 1.0,
        "distinct_span_count": 8,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 8,
        "seed": 2970730807,
        "spatial_bin_count": 8,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 6,
        "assignment_rank": 34,
        "assignment_sha256": "ba424c1f68b3abe74be7f9f1b6347e5fb9f371727c6153160e9c5859210f1eae",
        "base_scene_index": 32,
        "canonical_anchor_count": 6,
        "confidence_score": 1.0,
        "distinct_span_count": 6,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 6,
        "seed": 2627106601,
        "spatial_bin_count": 6,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 6,
        "assignment_rank": 29,
        "assignment_sha256": "a3b943f7000192e5e7e5f5af858109d4fb865c2290eb92b07c51fe7f92135f2c",
        "base_scene_index": 33,
        "canonical_anchor_count": 6,
        "confidence_score": 1.0,
        "distinct_span_count": 6,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 6,
        "seed": 969260173,
        "spatial_bin_count": 6,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 5,
        "assignment_rank": 46,
        "assignment_sha256": "f638df6a13662285d5bde6b76ba7ad13cb6acddf8883f9768b9bf44a80061b25",
        "base_scene_index": 34,
        "canonical_anchor_count": 5,
        "confidence_score": 1.0,
        "distinct_span_count": 5,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 5,
        "seed": 2086638528,
        "spatial_bin_count": 5,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 2,
        "assignment_rank": 4,
        "assignment_sha256": "2e2aee754c0852677587b7ea63df71301a1ca7ba934de6bd6cdbd50a7cf9059d",
        "base_scene_index": 35,
        "canonical_anchor_count": 2,
        "confidence_score": 0.26666666666666666,
        "distinct_span_count": 1,
        "duplicate_count": 0,
        "population": "single_span",
        "reference_status": "LOW",
        "region_count": 1,
        "seed": 139154719,
        "spatial_bin_count": 2,
        "status": "LOW",
        "unit_status": "LOW"
      },
      {
        "anchor_count": 2,
        "assignment_rank": 0,
        "assignment_sha256": "0598c4d7c1659f28ed351d7af8b7a948a380d12c8e16948be9ca7ef9f2e9aa3f",
        "base_scene_index": 36,
        "canonical_anchor_count": 2,
        "confidence_score": 0.26666666666666666,
        "distinct_span_count": 1,
        "duplicate_count": 0,
        "population": "single_span",
        "reference_status": "LOW",
        "region_count": 1,
        "seed": 4248228759,
        "spatial_bin_count": 2,
        "status": "LOW",
        "unit_status": "LOW"
      },
      {
        "anchor_count": 5,
        "assignment_rank": 24,
        "assignment_sha256": "8fa87725cef5a5744fcc04a6043492b28ef4bb32b4b6619039e74b3dfcd03ecd",
        "base_scene_index": 37,
        "canonical_anchor_count": 5,
        "confidence_score": 1.0,
        "distinct_span_count": 5,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 5,
        "seed": 2124629432,
        "spatial_bin_count": 5,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 5,
        "assignment_rank": 45,
        "assignment_sha256": "f4292fb2750234c48648a92085513e779f7e41117feceb57b6cfe8c6e722f56b",
        "base_scene_index": 38,
        "canonical_anchor_count": 5,
        "confidence_score": 1.0,
        "distinct_span_count": 5,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 5,
        "seed": 2700756000,
        "spatial_bin_count": 5,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 5,
        "assignment_rank": 31,
        "assignment_sha256": "ab8f0dda835a408744c3fe84ed0293cafc8548f79f8cb6a6f4292b69cf20386d",
        "base_scene_index": 39,
        "canonical_anchor_count": 5,
        "confidence_score": 1.0,
        "distinct_span_count": 5,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 5,
        "seed": 1233866156,
        "spatial_bin_count": 5,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 8,
        "assignment_rank": 13,
        "assignment_sha256": "4e3b19590a4f9267ed5afa58fa359f993ce73f5837f9e054e0fe3ee1506e87f2",
        "base_scene_index": 40,
        "canonical_anchor_count": 8,
        "confidence_score": 1.0,
        "distinct_span_count": 8,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 8,
        "seed": 237711395,
        "spatial_bin_count": 8,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 2,
        "assignment_rank": 9,
        "assignment_sha256": "4790c2ee4cabeb89f7855ecb86f3ea92d887c5b1a5fa82aaced108c5528488a0",
        "base_scene_index": 41,
        "canonical_anchor_count": 2,
        "confidence_score": 0.26666666666666666,
        "distinct_span_count": 1,
        "duplicate_count": 0,
        "population": "single_span",
        "reference_status": "LOW",
        "region_count": 1,
        "seed": 249731958,
        "spatial_bin_count": 2,
        "status": "LOW",
        "unit_status": "LOW"
      },
      {
        "anchor_count": 6,
        "assignment_rank": 48,
        "assignment_sha256": "f9d12fb4e8e73c38de3e9364011ae31b94b4faacbde16d1b4d10857ed1b2d936",
        "base_scene_index": 42,
        "canonical_anchor_count": 6,
        "confidence_score": 1.0,
        "distinct_span_count": 6,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 6,
        "seed": 2082259161,
        "spatial_bin_count": 6,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 7,
        "assignment_rank": 14,
        "assignment_sha256": "539a4b07158c4537069dd78c1b96f069d0cab7b21c8dccb520596b22bd90debb",
        "base_scene_index": 43,
        "canonical_anchor_count": 7,
        "confidence_score": 1.0,
        "distinct_span_count": 7,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 7,
        "seed": 955414310,
        "spatial_bin_count": 7,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 8,
        "assignment_rank": 44,
        "assignment_sha256": "f34d115c4d2d7006ba4da8359a3a13217404dba9029fc7f10ac940142b6c4ad9",
        "base_scene_index": 44,
        "canonical_anchor_count": 8,
        "confidence_score": 1.0,
        "distinct_span_count": 8,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 8,
        "seed": 3325442431,
        "spatial_bin_count": 8,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 5,
        "assignment_rank": 21,
        "assignment_sha256": "7ca732e9e152b769b2b94031e3cbca6c0e7172dd87799b87ad1590cd3a729427",
        "base_scene_index": 45,
        "canonical_anchor_count": 5,
        "confidence_score": 1.0,
        "distinct_span_count": 5,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 5,
        "seed": 2412349944,
        "spatial_bin_count": 5,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 8,
        "assignment_rank": 17,
        "assignment_sha256": "606ebff6b4674e84de96afa809c23c60cc52e479a8b151d410c19e58345cad43",
        "base_scene_index": 46,
        "canonical_anchor_count": 8,
        "confidence_score": 1.0,
        "distinct_span_count": 8,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 8,
        "seed": 264789263,
        "spatial_bin_count": 8,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 8,
        "assignment_rank": 38,
        "assignment_sha256": "d49e824c02a8c3fac804b9673232b59dc046dc0610c4c4b4ee1b21a3d15031fd",
        "base_scene_index": 47,
        "canonical_anchor_count": 8,
        "confidence_score": 1.0,
        "distinct_span_count": 8,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 8,
        "seed": 2954027451,
        "spatial_bin_count": 8,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 6,
        "assignment_rank": 35,
        "assignment_sha256": "bee37599b15d34bff11ab9afd9e415c5a22ac02983a3ecde68f7e99fa3fa6a8a",
        "base_scene_index": 48,
        "canonical_anchor_count": 6,
        "confidence_score": 1.0,
        "distinct_span_count": 6,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 6,
        "seed": 1376904385,
        "spatial_bin_count": 6,
        "status": "LOW",
        "unit_status": "HIGH"
      },
      {
        "anchor_count": 7,
        "assignment_rank": 12,
        "assignment_sha256": "49de27fc633feb2f9b607461701ba050be30dea67496e1dc33133bf5bdffdc8b",
        "base_scene_index": 49,
        "canonical_anchor_count": 7,
        "confidence_score": 1.0,
        "distinct_span_count": 7,
        "duplicate_count": 0,
        "population": "anchor_rich",
        "reference_status": "LOW",
        "region_count": 7,
        "seed": 481507058,
        "spatial_bin_count": 7,
        "status": "LOW",
        "unit_status": "HIGH"
      }
    ],
    "base_anchor_count_distribution": {
      "2": 10,
      "5": 12,
      "6": 11,
      "7": 5,
      "8": 12
    },
    "base_anchor_count_max": 8,
    "base_anchor_count_mean": 5.54,
    "base_anchor_count_median": 6.0,
    "base_anchor_count_min": 2,
    "base_anchor_count_rule_mismatch_scene_count": 0,
    "base_anchor_rich_minimum_adjacent_log_span_separation": 0.07318377144696049,
    "base_anchor_rich_spatial_bin_below_3_scene_count": 0,
    "base_canonical_anchor_count_distribution": {
      "2": 10,
      "5": 12,
      "6": 11,
      "7": 5,
      "8": 12
    },
    "base_canonical_anchor_count_mismatch_scene_count": 0,
    "base_distinct_span_count_distribution": {
      "1": 10,
      "5": 12,
      "6": 11,
      "7": 5,
      "8": 12
    },
    "base_distinct_span_mismatch_scene_count": 0,
    "base_distinct_span_rule_mismatch_scene_count": 0,
    "base_minimum_adjacent_log_span_separation": 0.07318377144696049,
    "base_mutation_population_role_mismatch_scene_count": 0,
    "base_non_dim_text_ratio_anchor_count": 0,
    "base_population_counts": {
      "anchor_rich": 40,
      "single_span": 10
    },
    "base_reference_status_counts": {
      "LOW": 50
    },
    "base_reference_status_counts_by_population": {
      "anchor_rich": {
        "LOW": 40
      },
      "single_span": {
        "LOW": 10
      }
    },
    "base_spatial_bin_below_3_scene_count": 10,
    "base_spatial_bin_count_distribution": {
      "2": 10,
      "5": 12,
      "6": 11,
      "7": 5,
      "8": 12
    },
    "base_spatial_bin_count_min": 2,
    "base_status_counts_by_population": {
      "anchor_rich": {
        "LOW": 40
      },
      "single_span": {
        "LOW": 10
      }
    },
    "base_unit_confidence_score": {
      "count": 50,
      "max": 1.0,
      "mean": 0.8533333333333334,
      "median": 1.0,
      "min": 0.26666666666666666,
      "p05": 0.26666666666666666,
      "p25": 1.0,
      "p75": 1.0,
      "p95": 1.0
    },
    "base_unit_status_counts": {
      "HIGH": 40,
      "LOW": 10
    },
    "base_unit_status_counts_by_population": {
      "anchor_rich": {
        "HIGH": 40
      },
      "single_span": {
        "LOW": 10
      }
    },
    "c1_ransac_log_tolerance": 0.04879016416943204,
    "ir_anchor_count_distribution": {
      "2": 40,
      "5": 48,
      "6": 44,
      "7": 20,
      "8": 48
    },
    "ir_display_raw_truth_ratio_mismatch_count": 0,
    "ir_population_counts": {
      "anchor_rich": 160,
      "single_span": 40
    },
    "population_assignment_digest": "985342caf26bdbbf19a27862a1d72d272b3db81aa2c1d18494e322a41435a6c5",
    "population_assignment_rule": "rank base indices by sha256(str(seed)+':loop_l1b_population'); first 10 single_span, remaining 40 anchor_rich",
    "single_span_indices": [
      0,
      2,
      7,
      19,
      21,
      23,
      30,
      35,
      36,
      41
    ],
    "single_span_unit_HIGH_scene_count": 0,
    "single_span_unit_LOW_or_NONE_scene_count": 10
  },
  "build_numbers": {
    "entity_profile_filler_count": 5100,
    "entity_profile_target_total": 8000,
    "fidelity_gap_sample_target": 1200,
    "population_assignment": {
      "anchor_rich_base_scene_count": 40,
      "assignment_digest": "bd49797b0aec11a4341a1de3e6d2c8bdf734267505dd9d2d4bc780407ee266c0",
      "single_span_base_scene_count": 10,
      "single_span_indices": [
        0,
        2,
        7,
        19,
        21,
        23,
        30,
        35,
        36,
        41
      ]
    }
  },
  "contract": {
    "c0_import": "D:\\dev\\99_tools\\autocad-sdk-router\\tools\\e2\\cells\\feyerabend_c0.py",
    "c1_import": "D:\\dev\\99_tools\\autocad-sdk-router\\tools\\e2\\cells\\feyerabend_c1.py",
    "gate_verdict_emitted": false,
    "random_search_count": 0,
    "source_cad_access_count": 0,
    "source_dossier": "D:\\dev\\99_tools\\autocad-sdk-router\\reports\\e2\\dossiers\\feyerabend_P2.md",
    "source_packet": "D:\\runs\\e2_program\\build\\PACKET_loop_L1b_mixed_population.md",
    "test_split_access_count": 0,
    "write_root": "D:\\runs\\e2_program\\cells\\loop_l1b"
  },
  "determinism_and_scale_numbers": {
    "four_scale_normalized_geometry_mismatch_base_scene_count": 0,
    "four_scale_source_handle_mismatch_base_scene_count": 0,
    "four_scale_topology_mismatch_base_scene_count": 0,
    "seed_collision_count": 0,
    "unique_seed_count": 50
  },
  "fidelity_numbers_kappa_1": {
    "entity_mix_tv": 0.00021191458340744963,
    "histogram_bin_count": 25,
    "histogram_edges": [
      0,
      1,
      2,
      5,
      10,
      25,
      50,
      75,
      100,
      125,
      150,
      175,
      200,
      250,
      300,
      400,
      500,
      750,
      1000,
      1500,
      2500,
      5000,
      10000,
      20000,
      50000,
      300000
    ],
    "reference_entity_mix": {
      "3DFACE": 34,
      "ARC": 2198,
      "CIRCLE": 141,
      "ELLIPSE": 201,
      "HATCH": 264,
      "INSERT": 1158,
      "LINE": 12110,
      "LWPOLYLINE": 7400,
      "MTEXT": 113,
      "POINT": 341,
      "POLYLINE": 1,
      "SPLINE": 3973,
      "TEXT": 154,
      "WIPEOUT": 33
    },
    "reference_entity_total": 28121,
    "reference_parallel_pair_offset_count": 4877,
    "reference_thickness_histogram_counts": [
      39,
      75,
      144,
      140,
      535,
      226,
      318,
      193,
      155,
      208,
      97,
      77,
      88,
      183,
      233,
      146,
      298,
      347,
      316,
      264,
      289,
      298,
      178,
      9,
      21
    ],
    "synthetic_entity_mix": {
      "3DFACE": 10,
      "ARC": 625,
      "CIRCLE": 40,
      "ELLIPSE": 57,
      "HATCH": 75,
      "INSERT": 330,
      "LINE": 3445,
      "LWPOLYLINE": 2105,
      "MTEXT": 32,
      "POINT": 97,
      "SPLINE": 1130,
      "TEXT": 44,
      "WIPEOUT": 10
    },
    "synthetic_entity_total": 8000,
    "synthetic_parallel_pair_offset_count": 1333,
    "synthetic_parallel_pair_offsets_in_histogram_count": 1333,
    "synthetic_thickness_histogram_counts": [
      10,
      19,
      35,
      34,
      132,
      56,
      78,
      51,
      65,
      71,
      43,
      37,
      35,
      65,
      62,
      36,
      73,
      85,
      78,
      73,
      71,
      73,
      44,
      2,
      5
    ],
    "thickness_histogram_ks": 0.040287855437306064
  },
  "mutation_family_coverage": {
    "all_wall_sentinel": {
      "scene_count": 1,
      "scene_ratio": 0.02
    },
    "arc_spline_adjacent_or_distractor": {
      "scene_count": 50,
      "scene_ratio": 1.0
    },
    "door_window_dimension_long_parallel_distractor": {
      "scene_count": 49,
      "scene_ratio": 0.98
    },
    "hatch_boundary_distractor": {
      "scene_count": 50,
      "scene_ratio": 1.0
    },
    "lwpolyline_segmentation": {
      "scene_count": 25,
      "scene_ratio": 0.5
    },
    "multiple_reference_span_regions": {
      "scene_count": 40,
      "scene_ratio": 0.8
    },
    "nested_insert_nonuniform_accumulated_transform": {
      "scene_count": 50,
      "scene_ratio": 1.0
    },
    "partial_overlap_near_parallel_fragment": {
      "scene_count": 50,
      "scene_ratio": 1.0
    },
    "pure_line_parallel_pair": {
      "scene_count": 21,
      "scene_ratio": 0.42
    },
    "single_reference_span_region": {
      "scene_count": 10,
      "scene_ratio": 0.2
    },
    "zero_wall_sentinel": {
      "scene_count": 1,
      "scene_ratio": 0.02
    }
  },
  "phenomenon_coverage": {
    "ARC": {
      "scene_count": 50,
      "scene_ratio": 1.0
    },
    "HATCH": {
      "scene_count": 50,
      "scene_ratio": 1.0
    },
    "SPLINE": {
      "scene_count": 50,
      "scene_ratio": 1.0
    },
    "nested_block": {
      "scene_count": 50,
      "scene_ratio": 1.0
    },
    "nonparallel_fragment": {
      "scene_count": 50,
      "scene_ratio": 1.0
    }
  },
  "reference_sha256": {
    "entity_mix_json": "cc95a55852932cc41eb5dfdc5fc9df560f6ada94625969e9284c581e809608ea",
    "fidelity_histogram_json": "afec84ebf141d8bc29ef6b0ee8fe615c7e6c2bf19b1e4df10c64d11951691ae3",
    "fidelity_stats_py": "00acec150c65d05a82641d1ab0ac0466cd68e4a424670dd849c3211b2f3c96df",
    "gen2_py": "a8c2468b696b9271610e38bd87cec1402e9153bc464a5d9cf1429595f26dab55"
  },
  "scene_counts": {
    "base_scene_count": 50,
    "ir_scene_count": 200,
    "kappa_1_scene_count": 50,
    "positive_base_scene_count": 49,
    "positive_ir_scene_count": 196,
    "scale_count": 4
  },
  "schema": "ariadne.e2.loop_l1b.c0v3_numbers.v1",
  "selftest": {
    "passed": 17,
    "sealed_c1": {
      "passed": 6,
      "tests": [
        {
          "detail": "estimate=2.5 expected=2.5 unit_status=HIGH",
          "name": "exact_anchor_exact_scale",
          "passed": true
        },
        {
          "detail": "unit_status=HIGH confidence=1",
          "name": "exact_anchor_high_confidence",
          "passed": true
        },
        {
          "detail": "estimate=None unit_status=NONE status=NONE",
          "name": "no_anchor_honest_no_estimate",
          "passed": true
        },
        {
          "detail": "duplicate=b7eafb24bff4 stale_override=4587fb707ef7 suffix_removal=d5721ef40250 single_outlier=802397c8b4a3",
          "name": "corruption_reproducibility",
          "passed": true
        },
        {
          "detail": "estimate=2.5 unit_status=HIGH",
          "name": "single_outlier_mode_or_downgrade",
          "passed": true
        },
        {
          "detail": "accessed_keys=['anchors']",
          "name": "truth_key_access_guard",
          "passed": true
        }
      ],
      "total": 6
    },
    "tests": [
      {
        "detail": "dossier_rows=11 c0_families=11",
        "name": "dossier_family_mapping_one_to_one",
        "passed": true
      },
      {
        "detail": "anchor_rich=40 single_span=10",
        "name": "population_cardinality",
        "passed": true
      },
      {
        "detail": "single_indices=[0, 2, 7, 19, 21, 23, 30, 35, 36, 41] digest=9594d33c8cfee09de24a58fad32b1eb4726e129282e132a4fc79612bf4307f71",
        "name": "population_assignment_seed_deterministic",
        "passed": true
      },
      {
        "detail": "j=0 sha256=a5ada097be258a83a2fbe36826bd8facc9f29fac987b299f02f649c7b8ee4943",
        "name": "single_span_same_j_same_sha",
        "passed": true
      },
      {
        "detail": "j=1 sha256=0d60cc82d5e80695ca5f810d4d599946425c155efb249af8a25dd16df9b3cac3",
        "name": "anchor_rich_same_j_same_sha",
        "passed": true
      },
      {
        "detail": "anchors=2 regions=1 distinct_spans=1",
        "name": "single_span_structure",
        "passed": true
      },
      {
        "detail": "canonical=2 unit_status=LOW confidence=0.266666666667",
        "name": "single_span_canonical_low_representation",
        "passed": true
      },
      {
        "detail": "anchors=8 canonical=8 duplicates=0",
        "name": "anchor_rich_l1_rule",
        "passed": true
      },
      {
        "detail": "distinct_spans=8 bins=8",
        "name": "anchor_rich_independent_spans_bins",
        "passed": true
      },
      {
        "detail": "estimate=1.0 unit_status=HIGH confidence=1",
        "name": "anchor_rich_scale_estimate",
        "passed": true
      },
      {
        "detail": "topology_unique=1 normalized_geometry_unique=1",
        "name": "single_span_four_scale_topology",
        "passed": true
      },
      {
        "detail": "four_scale_reverse_transition_count=0",
        "name": "single_span_single_outlier_no_reverse_transition",
        "passed": true
      },
      {
        "detail": "scene_count=4 error_count=0",
        "name": "truth_validator_positive_cases",
        "passed": true
      },
      {
        "detail": "error_count=5",
        "name": "truth_validator_negative_case_honest_fail",
        "passed": true
      },
      {
        "detail": "distribution={2: 10, 5: 12, 6: 11, 7: 5, 8: 12} role_errors=0 rich_bin_errors=0",
        "name": "all_base_population_rules",
        "passed": true
      },
      {
        "detail": "wall_records=2 entity_types=['ARC', 'CIRCLE', 'HATCH', 'LINE', 'LWPOLYLINE', 'MTEXT', 'SPLINE', 'TEXT']",
        "name": "permitted_gen2_synthetic_fixture",
        "passed": true
      },
      {
        "detail": "passed=6 total=6",
        "name": "sealed_c1_selftests",
        "passed": true
      }
    ],
    "total": 17,
    "transcript": "=== loop_l1b mixed-population selftest ===\nSELFTEST dossier_family_mapping_one_to_one: PASS | dossier_rows=11 c0_families=11\nSELFTEST population_cardinality: PASS | anchor_rich=40 single_span=10\nSELFTEST population_assignment_seed_deterministic: PASS | single_indices=[0, 2, 7, 19, 21, 23, 30, 35, 36, 41] digest=9594d33c8cfee09de24a58fad32b1eb4726e129282e132a4fc79612bf4307f71\nSELFTEST single_span_same_j_same_sha: PASS | j=0 sha256=a5ada097be258a83a2fbe36826bd8facc9f29fac987b299f02f649c7b8ee4943\nSELFTEST anchor_rich_same_j_same_sha: PASS | j=1 sha256=0d60cc82d5e80695ca5f810d4d599946425c155efb249af8a25dd16df9b3cac3\nSELFTEST single_span_structure: PASS | anchors=2 regions=1 distinct_spans=1\nSELFTEST single_span_canonical_low_representation: PASS | canonical=2 unit_status=LOW confidence=0.266666666667\nSELFTEST anchor_rich_l1_rule: PASS | anchors=8 canonical=8 duplicates=0\nSELFTEST anchor_rich_independent_spans_bins: PASS | distinct_spans=8 bins=8\nSELFTEST anchor_rich_scale_estimate: PASS | estimate=1.0 unit_status=HIGH confidence=1\nSELFTEST single_span_four_scale_topology: PASS | topology_unique=1 normalized_geometry_unique=1\nSELFTEST single_span_single_outlier_no_reverse_transition: PASS | four_scale_reverse_transition_count=0\nSELFTEST truth_validator_positive_cases: PASS | scene_count=4 error_count=0\nSELFTEST truth_validator_negative_case_honest_fail: PASS | error_count=5\nSELFTEST all_base_population_rules: PASS | distribution={2: 10, 5: 12, 6: 11, 7: 5, 8: 12} role_errors=0 rich_bin_errors=0\nSELFTEST permitted_gen2_synthetic_fixture: PASS | wall_records=2 entity_types=['ARC', 'CIRCLE', 'HATCH', 'LINE', 'LWPOLYLINE', 'MTEXT', 'SPLINE', 'TEXT']\n=== imported sealed C1 selftests ===\nSELFTEST exact_anchor_exact_scale: PASS | estimate=2.5 expected=2.5 unit_status=HIGH\nSELFTEST exact_anchor_high_confidence: PASS | unit_status=HIGH confidence=1\nSELFTEST no_anchor_honest_no_estimate: PASS | estimate=None unit_status=NONE status=NONE\nSELFTEST corruption_reproducibility: PASS | duplicate=b7eafb24bff4 stale_override=4587fb707ef7 suffix_removal=d5721ef40250 single_outlier=802397c8b4a3\nSELFTEST single_outlier_mode_or_downgrade: PASS | estimate=2.5 unit_status=HIGH\nSELFTEST truth_key_access_guard: PASS | accessed_keys=['anchors']\nSELFTEST SUMMARY: 6/6 passed\nSELFTEST sealed_c1_selftests: PASS | passed=6 total=6\nSELFTEST SUMMARY: 17/17 passed\nSELFTEST_RESULT: PASS\n"
  },
  "sentinel_truth_integrity": {
    "all_wall_candidate_pair_count": 3,
    "all_wall_candidate_truth_coverage_ratio": 1.0,
    "all_wall_candidate_truth_intersection_count": 3,
    "all_wall_scene_count": 1,
    "all_wall_truth_pair_count": 3,
    "all_wall_validation_error_count": 0,
    "zero_wall_candidate_pair_count": 2,
    "zero_wall_scene_count": 1,
    "zero_wall_truth_pair_count": 0,
    "zero_wall_validation_error_count": 0,
    "zero_wall_wall_face_handle_count": 0
  },
  "truth_pair_numbers": {
    "base_scene_truth_pair_ratio": 0.98,
    "base_scenes_with_truth_pair_count": 49,
    "base_truth_pair_count": 51,
    "ir_scene_truth_pair_ratio": 0.98,
    "ir_scenes_with_truth_pair_count": 196,
    "ir_truth_pair_count": 204,
    "positive_base_scene_truth_pair_ratio": 1.0,
    "positive_base_scenes_with_truth_pair_count": 49,
    "positive_ir_scene_truth_pair_ratio": 1.0,
    "positive_ir_scenes_with_truth_pair_count": 196
  },
  "truth_validator": {
    "error_count": 0,
    "validated_ir_scene_count": 200
  },
  "v1_baseline": {
    "bytes": 5867,
    "path": "D:\\dev\\99_tools\\autocad-sdk-router\\reports\\e2\\cells\\feyerabend_c0\\coverage_numbers.json",
    "schema": "ariadne.e2.feyerabend_c0.coverage_numbers.v1",
    "sha256": "f5c17b6094d741bffb64a35c17f35a58243c23720ad3446e86c962299b183723"
  },
  "v1_comparison_rows": [
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 50,
      "metric": "scene_counts.base_scene_count",
      "v1": 50,
      "v2": 50,
      "v3": 50
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 200,
      "metric": "scene_counts.ir_scene_count",
      "v1": 200,
      "v2": 200,
      "v3": 200
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 204,
      "metric": "truth_pair_numbers.ir_truth_pair_count",
      "v1": 204,
      "v2": 204,
      "v3": 204
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 0,
      "metric": "truth_validator.error_count",
      "v1": 0,
      "v2": 0,
      "v3": 0
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 0.00021191458340744963,
      "metric": "fidelity_numbers_kappa_1.entity_mix_tv",
      "v1": 0.00021191458340744963,
      "v2": 0.00021191458340744963,
      "v3": 0.00021191458340744963
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 0.040287855437306064,
      "metric": "fidelity_numbers_kappa_1.thickness_histogram_ks",
      "v1": 0.040287855437306064,
      "v2": 0.040287855437306064,
      "v3": 0.040287855437306064
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 0,
      "metric": "determinism_and_scale_numbers.four_scale_topology_mismatch_base_scene_count",
      "v1": 0,
      "v2": 0,
      "v3": 0
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 0,
      "metric": "determinism_and_scale_numbers.four_scale_normalized_geometry_mismatch_base_scene_count",
      "v1": 0,
      "v2": 0,
      "v3": 0
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 0,
      "metric": "determinism_and_scale_numbers.four_scale_source_handle_mismatch_base_scene_count",
      "v1": 0,
      "v2": 0,
      "v3": 0
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 21,
      "metric": "mutation_family_coverage.pure_line_parallel_pair.scene_count",
      "v1": 21,
      "v2": 21,
      "v3": 21
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 25,
      "metric": "mutation_family_coverage.lwpolyline_segmentation.scene_count",
      "v1": 25,
      "v2": 25,
      "v3": 25
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 50,
      "metric": "mutation_family_coverage.arc_spline_adjacent_or_distractor.scene_count",
      "v1": 50,
      "v2": 50,
      "v3": 50
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 50,
      "metric": "mutation_family_coverage.hatch_boundary_distractor.scene_count",
      "v1": 50,
      "v2": 50,
      "v3": 50
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 50,
      "metric": "mutation_family_coverage.nested_insert_nonuniform_accumulated_transform.scene_count",
      "v1": 50,
      "v2": 50,
      "v3": 50
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 50,
      "metric": "mutation_family_coverage.partial_overlap_near_parallel_fragment.scene_count",
      "v1": 50,
      "v2": 50,
      "v3": 50
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 49,
      "metric": "mutation_family_coverage.door_window_dimension_long_parallel_distractor.scene_count",
      "v1": 49,
      "v2": 49,
      "v3": 49
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 1,
      "metric": "mutation_family_coverage.zero_wall_sentinel.scene_count",
      "v1": 1,
      "v2": 1,
      "v3": 1
    },
    {
      "delta": 0.0,
      "delta_v3_minus_l1": 0.0,
      "delta_v3_minus_v1": 0.0,
      "l1": 1,
      "metric": "mutation_family_coverage.all_wall_sentinel.scene_count",
      "v1": 1,
      "v2": 1,
      "v3": 1
    },
    {
      "delta": -15.0,
      "delta_v3_minus_l1": 10.0,
      "delta_v3_minus_v1": -15.0,
      "l1": 0,
      "metric": "mutation_family_coverage.single_reference_span_region.scene_count",
      "v1": 25,
      "v2": 10,
      "v3": 10
    },
    {
      "delta": 15.0,
      "delta_v3_minus_l1": -10.0,
      "delta_v3_minus_v1": 15.0,
      "l1": 50,
      "metric": "mutation_family_coverage.multiple_reference_span_regions.scene_count",
      "v1": 25,
      "v2": 40,
      "v3": 40
    }
  ]
}
```

## C1v3 전체 scale 추정 수치

| metric | value |
| --- | --- |
| scene_count | 200 |
| estimate_count | 200 |
| estimate_coverage | 1 |
| accuracy_within_5pct | 1 |
| HIGH_scene_count | 160 |
| HIGH_coverage | 0.8 |
| HIGH_accuracy_within_5pct | 1 |
| e_s_min | 0 |
| e_s_median | 2.22044604925e-16 |
| e_s_p95 | 1.3433698598e-15 |
| e_s_max | 3.10862446895e-15 |
| relative_error_min | 0 |
| relative_error_median | 2.22044604925e-16 |
| relative_error_p95 | 1.3433698598e-15 |
| relative_error_max | 3.10862446895e-15 |

## Scale × confidence 전 행

| kappa | unit_status | n | fraction | n_est | accuracy_5pct | e_s_med | e_s_p95 | relerr_med | relerr_p95 | conf_med |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.001 | HIGH | 40 | 0.8 | 40 | 1 | 6.66133814775e-16 | 1.99840144433e-15 | 6.66133814775e-16 | 1.99840144433e-15 | 1 |
| 0.001 | LOW | 10 | 0.2 | 10 | 1 | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 | 0.266666666667 |
| 0.001 | NONE | 0 | 0 | 0 | null | null | null | null | null | null |
| 0.01 | HIGH | 40 | 0.8 | 40 | 1 | 4.4408920985e-16 | 2.22044604925e-15 | 4.4408920985e-16 | 2.22044604925e-15 | 1 |
| 0.01 | LOW | 10 | 0.2 | 10 | 1 | 4.4408920985e-16 | 4.4408920985e-16 | 4.4408920985e-16 | 4.4408920985e-16 | 0.266666666667 |
| 0.01 | NONE | 0 | 0 | 0 | null | null | null | null | null | null |
| 1 | HIGH | 40 | 0.8 | 40 | 1 | 0 | 0 | 0 | 0 | 1 |
| 1 | LOW | 10 | 0.2 | 10 | 1 | 0 | 0 | 0 | 0 | 0.266666666667 |
| 1 | NONE | 0 | 0 | 0 | null | null | null | null | null | null |
| 1000 | HIGH | 40 | 0.8 | 40 | 1 | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 | 1 |
| 1000 | LOW | 10 | 0.2 | 10 | 1 | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 | 0.266666666667 |
| 1000 | NONE | 0 | 0 | 0 | null | null | null | null | null | null |

## Scale별 HIGH coverage·accuracy

| kappa | HIGH_n | HIGH_coverage | HIGH_accuracy_5pct | HIGH_relerr_p95 |
| --- | --- | --- | --- | --- |
| 0.001 | 40 | 0.8 | 1 | 1.99840144433e-15 |
| 0.01 | 40 | 0.8 | 1 | 2.22044604925e-15 |
| 1 | 40 | 0.8 | 1 | 0 |
| 1000 | 40 | 0.8 | 1 | 2.22044604925e-16 |

## Numeric confidence-score bin별 accuracy

| scale | score_bin | n | n_est | accuracy_5pct | relerr_med | relerr_p95 |
| --- | --- | --- | --- | --- | --- | --- |
| ALL | [0.00,0.25) | 0 | 0 | null | null | null |
| ALL | [0.25,0.50) | 40 | 40 | 1 | 2.22044604925e-16 | 4.4408920985e-16 |
| ALL | [0.50,0.75) | 0 | 0 | null | null | null |
| ALL | [0.75,1.00] | 160 | 160 | 1 | 2.22044604925e-16 | 1.55431223448e-15 |
| 0.001 | [0.00,0.25) | 0 | 0 | null | null | null |
| 0.001 | [0.25,0.50) | 10 | 10 | 1 | 2.22044604925e-16 | 2.22044604925e-16 |
| 0.001 | [0.50,0.75) | 0 | 0 | null | null | null |
| 0.001 | [0.75,1.00] | 40 | 40 | 1 | 6.66133814775e-16 | 1.99840144433e-15 |
| 0.01 | [0.00,0.25) | 0 | 0 | null | null | null |
| 0.01 | [0.25,0.50) | 10 | 10 | 1 | 4.4408920985e-16 | 4.4408920985e-16 |
| 0.01 | [0.50,0.75) | 0 | 0 | null | null | null |
| 0.01 | [0.75,1.00] | 40 | 40 | 1 | 4.4408920985e-16 | 2.22044604925e-15 |
| 1 | [0.00,0.25) | 0 | 0 | null | null | null |
| 1 | [0.25,0.50) | 10 | 10 | 1 | 0 | 0 |
| 1 | [0.50,0.75) | 0 | 0 | null | null | null |
| 1 | [0.75,1.00] | 40 | 40 | 1 | 0 | 0 |
| 1000 | [0.00,0.25) | 0 | 0 | null | null | null |
| 1000 | [0.25,0.50) | 10 | 10 | 1 | 2.22044604925e-16 | 2.22044604925e-16 |
| 1000 | [0.50,0.75) | 0 | 0 | null | null | null |
| 1000 | [0.75,1.00] | 40 | 40 | 1 | 2.22044604925e-16 | 2.22044604925e-16 |

## Corruption 4종 전이 수치

| corruption | n | unit_transition | status_transition | reference_transition | scale_same | scale_changed | relerr_med | relerr_p95 | conf_after_med |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| duplicate | 200 | {"HIGH->HIGH": 160, "LOW->LOW": 40} | {"LOW->LOW": 200} | {"LOW->LOW": 200} | 200 | 0 | 2.22044604925e-16 | 1.3433698598e-15 | 1 |
| stale_override | 200 | {"HIGH->HIGH": 112, "HIGH->LOW": 48, "LOW->LOW": 40} | {"LOW->LOW": 200} | {"LOW->LOW": 200} | 200 | 0 | 2.22044604925e-16 | 1.55431223448e-15 | 0.833333333333 |
| suffix_removal | 200 | {"HIGH->HIGH": 160, "LOW->LOW": 40} | {"LOW->LOW": 200} | {"LOW->LOW": 200} | 200 | 0 | 2.22044604925e-16 | 1.3433698598e-15 | 1 |
| single_outlier | 200 | {"HIGH->HIGH": 160, "LOW->LOW": 40} | {"LOW->LOW": 200} | {"LOW->LOW": 200} | 200 | 0 | 2.22044604925e-16 | 1.3433698598e-15 | 0.857142857143 |

## Single-outlier 역방향 전이 수치

| metric | value |
| --- | --- |
| scene_count | 200 |
| v1_status_transitions | {"LOW->HIGH": 26, "LOW->LOW": 174} |
| v3_status_transitions | {"LOW->LOW": 200} |
| v1_unit_status_transitions | {"LOW->LOW": 200} |
| v3_unit_status_transitions | {"HIGH->HIGH": 160, "LOW->LOW": 40} |
| v3_reference_status_transitions | {"LOW->LOW": 200} |
| v1_low_to_high_status_count | 26 |
| v3_low_to_high_status_count | 0 |
| v3_confidence_score_increased_count | 0 |
| v3_confidence_score_unchanged_count | 0 |
| v3_confidence_score_decreased_count | 200 |
| v3_status_rank_increased_count | 0 |
| v3_unit_status_rank_increased_count | 0 |
| v3_reference_status_rank_increased_count | 0 |
| v3_confidence_or_status_increased_count | 0 |
| v3_scale_estimate_unchanged_count | 200 |
| v3_scale_estimate_changed_count | 0 |

## Pair-label permutation digest 수치

| metric | value |
| --- | --- |
| scene_count | 200 |
| pair_label_changed_scene_count | 196 |
| matching_anchor_artifact_scene_count | 200 |
| mismatching_anchor_artifact_scene_count | 0 |
| anchor_artifact_match_rate | 1 |
| global_anchor_artifact_digest_before | 357de452732649b1f4a0fe51268fbc6841cec83bb135de8769e60ba6cec51e9d |
| global_anchor_artifact_digest_after | 357de452732649b1f4a0fe51268fbc6841cec83bb135de8769e60ba6cec51e9d |

## C1v3 aggregate 수치 전문

```json
{
  "by_scale": {
    "0.001": {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 50,
        "max": 1.0,
        "mean": 0.8533333333333156,
        "median": 0.9999999999999818,
        "min": 0.26666666666666666,
        "p05": 0.26666666666666666,
        "p25": 0.9999999999999636,
        "p75": 0.9999999999999818,
        "p95": 0.9999999999999918
      },
      "e_s": {
        "count": 50,
        "max": 1.9984014443252837e-15,
        "mean": 6.483702463810915e-16,
        "median": 2.2204460492503136e-16,
        "min": 2.2204460492503136e-16,
        "p05": 2.2204460492503136e-16,
        "p25": 2.2204460492503136e-16,
        "p75": 1.1102230246251571e-15,
        "p95": 1.7985612998927527e-15
      },
      "estimate_count": 50,
      "estimate_coverage": 1.0,
      "high_accuracy_within_5pct": 1.0,
      "high_coverage": 0.8,
      "high_relative_error": {
        "count": 40,
        "max": 1.9984014443252818e-15,
        "mean": 7.549516567451064e-16,
        "median": 6.661338147750939e-16,
        "min": 2.220446049250313e-16,
        "p05": 2.220446049250313e-16,
        "p25": 2.220446049250313e-16,
        "p75": 1.1102230246251565e-15,
        "p95": 1.9984014443252818e-15
      },
      "high_scene_count": 40,
      "relative_error": {
        "count": 50,
        "max": 1.9984014443252818e-15,
        "mean": 6.483702463810914e-16,
        "median": 2.220446049250313e-16,
        "min": 2.220446049250313e-16,
        "p05": 2.220446049250313e-16,
        "p25": 2.220446049250313e-16,
        "p75": 1.1102230246251565e-15,
        "p95": 1.7985612998927523e-15
      },
      "scene_count": 50,
      "unit_status_counts": {
        "HIGH": 40,
        "LOW": 10
      }
    },
    "0.01": {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 50,
        "max": 1.0,
        "mean": 0.8533333333333161,
        "median": 0.9999999999999818,
        "min": 0.26666666666666666,
        "p05": 0.26666666666666666,
        "p25": 0.9999999999999636,
        "p75": 0.9999999999999818,
        "p95": 1.0
      },
      "e_s": {
        "count": 50,
        "max": 3.108624468950443e-15,
        "mean": 6.927791673660978e-16,
        "median": 4.440892098500626e-16,
        "min": 4.440892098500625e-16,
        "p05": 4.440892098500625e-16,
        "p25": 4.440892098500625e-16,
        "p75": 4.440892098500627e-16,
        "p95": 1.8207657603852534e-15
      },
      "estimate_count": 50,
      "estimate_coverage": 1.0,
      "high_accuracy_within_5pct": 1.0,
      "high_coverage": 0.8,
      "high_relative_error": {
        "count": 40,
        "max": 3.1086244689504383e-15,
        "mean": 7.549516567451064e-16,
        "median": 4.440892098500626e-16,
        "min": 4.440892098500626e-16,
        "p05": 4.440892098500626e-16,
        "p25": 4.440892098500626e-16,
        "p75": 6.661338147750939e-16,
        "p95": 2.220446049250313e-15
      },
      "high_scene_count": 40,
      "relative_error": {
        "count": 50,
        "max": 3.1086244689504383e-15,
        "mean": 6.927791673660977e-16,
        "median": 4.440892098500626e-16,
        "min": 4.440892098500626e-16,
        "p05": 4.440892098500626e-16,
        "p25": 4.440892098500626e-16,
        "p75": 4.440892098500626e-16,
        "p95": 1.8207657603852542e-15
      },
      "scene_count": 50,
      "unit_status_counts": {
        "HIGH": 40,
        "LOW": 10
      }
    },
    "1": {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 50,
        "max": 1.0,
        "mean": 0.8533333333333334,
        "median": 1.0,
        "min": 0.26666666666666666,
        "p05": 0.26666666666666666,
        "p25": 1.0,
        "p75": 1.0,
        "p95": 1.0
      },
      "e_s": {
        "count": 50,
        "max": 0.0,
        "mean": 0.0,
        "median": 0.0,
        "min": 0.0,
        "p05": 0.0,
        "p25": 0.0,
        "p75": 0.0,
        "p95": 0.0
      },
      "estimate_count": 50,
      "estimate_coverage": 1.0,
      "high_accuracy_within_5pct": 1.0,
      "high_coverage": 0.8,
      "high_relative_error": {
        "count": 40,
        "max": 0.0,
        "mean": 0.0,
        "median": 0.0,
        "min": 0.0,
        "p05": 0.0,
        "p25": 0.0,
        "p75": 0.0,
        "p95": 0.0
      },
      "high_scene_count": 40,
      "relative_error": {
        "count": 50,
        "max": 0.0,
        "mean": 0.0,
        "median": 0.0,
        "min": 0.0,
        "p05": 0.0,
        "p25": 0.0,
        "p75": 0.0,
        "p95": 0.0
      },
      "scene_count": 50,
      "unit_status_counts": {
        "HIGH": 40,
        "LOW": 10
      }
    },
    "1000": {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 50,
        "max": 1.0,
        "mean": 0.8533333333333334,
        "median": 1.0,
        "min": 0.26666666666666666,
        "p05": 0.26666666666666666,
        "p25": 1.0,
        "p75": 1.0,
        "p95": 1.0
      },
      "e_s": {
        "count": 50,
        "max": 2.2204460492503128e-16,
        "mean": 2.2204460492503128e-16,
        "median": 2.2204460492503128e-16,
        "min": 2.2204460492503128e-16,
        "p05": 2.2204460492503128e-16,
        "p25": 2.2204460492503128e-16,
        "p75": 2.2204460492503128e-16,
        "p95": 2.2204460492503128e-16
      },
      "estimate_count": 50,
      "estimate_coverage": 1.0,
      "high_accuracy_within_5pct": 1.0,
      "high_coverage": 0.8,
      "high_relative_error": {
        "count": 40,
        "max": 2.220446049250313e-16,
        "mean": 2.220446049250313e-16,
        "median": 2.220446049250313e-16,
        "min": 2.220446049250313e-16,
        "p05": 2.220446049250313e-16,
        "p25": 2.220446049250313e-16,
        "p75": 2.220446049250313e-16,
        "p95": 2.220446049250313e-16
      },
      "high_scene_count": 40,
      "relative_error": {
        "count": 50,
        "max": 2.220446049250313e-16,
        "mean": 2.220446049250313e-16,
        "median": 2.220446049250313e-16,
        "min": 2.220446049250313e-16,
        "p05": 2.220446049250313e-16,
        "p25": 2.220446049250313e-16,
        "p75": 2.220446049250313e-16,
        "p95": 2.220446049250313e-16
      },
      "scene_count": 50,
      "unit_status_counts": {
        "HIGH": 40,
        "LOW": 10
      }
    }
  },
  "confidence_grade_bins": {
    "HIGH": {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 160,
        "max": 1.0,
        "mean": 0.9999999999999891,
        "median": 1.0,
        "min": 0.9999999999999454,
        "p05": 0.9999999999999636,
        "p25": 0.9999999999999818,
        "p75": 1.0,
        "p95": 1.0
      },
      "e_s": {
        "count": 160,
        "max": 3.108624468950443e-15,
        "mean": 4.329869796038112e-16,
        "median": 2.220446049250313e-16,
        "min": 0.0,
        "p05": 0.0,
        "p25": 1.6653345369377346e-16,
        "p75": 4.440892098500627e-16,
        "p95": 1.554312234475218e-15
      },
      "estimate_count": 160,
      "estimate_coverage": 1.0,
      "relative_error": {
        "count": 160,
        "max": 3.1086244689504383e-15,
        "mean": 4.3298697960381104e-16,
        "median": 2.220446049250313e-16,
        "min": 0.0,
        "p05": 0.0,
        "p25": 1.6653345369377348e-16,
        "p75": 4.440892098500626e-16,
        "p95": 1.5543122344752192e-15
      },
      "scene_count": 160
    },
    "LOW": {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 40,
        "max": 0.26666666666666666,
        "mean": 0.26666666666666666,
        "median": 0.26666666666666666,
        "min": 0.26666666666666666,
        "p05": 0.26666666666666666,
        "p25": 0.26666666666666666,
        "p75": 0.26666666666666666,
        "p95": 0.26666666666666666
      },
      "e_s": {
        "count": 40,
        "max": 4.440892098500625e-16,
        "mean": 2.220446049250313e-16,
        "median": 2.220446049250313e-16,
        "min": 0.0,
        "p05": 0.0,
        "p25": 1.6653345369377346e-16,
        "p75": 2.7755575615628914e-16,
        "p95": 4.440892098500625e-16
      },
      "estimate_count": 40,
      "estimate_coverage": 1.0,
      "relative_error": {
        "count": 40,
        "max": 4.440892098500626e-16,
        "mean": 2.220446049250313e-16,
        "median": 2.220446049250313e-16,
        "min": 0.0,
        "p05": 0.0,
        "p25": 1.6653345369377348e-16,
        "p75": 2.7755575615628914e-16,
        "p95": 4.440892098500626e-16
      },
      "scene_count": 40
    },
    "NONE": {
      "accuracy_within_5pct": null,
      "confidence_score": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "e_s": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "estimate_count": 0,
      "estimate_coverage": null,
      "relative_error": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "scene_count": 0
    }
  },
  "corruption": {
    "all_four_applied": {
      "duplicate": {
        "confidence_score_after": {
          "count": 200,
          "max": 1.0,
          "mean": 0.8533333333333247,
          "median": 0.9999999999999818,
          "min": 0.26666666666666666,
          "p05": 0.26666666666666666,
          "p25": 0.9999999999999636,
          "p75": 1.0,
          "p95": 1.0
        },
        "e_s_after": {
          "count": 200,
          "max": 3.108624468950443e-15,
          "mean": 3.907985046680551e-16,
          "median": 2.220446049250313e-16,
          "min": 0.0,
          "p05": 0.0,
          "p25": 1.6653345369377346e-16,
          "p75": 4.440892098500625e-16,
          "p95": 1.3433698597964364e-15
        },
        "physical_unit_transitions": {
          "MM->MM": 200
        },
        "reference_status_transitions": {
          "LOW->LOW": 200
        },
        "relative_error_after": {
          "count": 200,
          "max": 3.1086244689504383e-15,
          "mean": 3.907985046680551e-16,
          "median": 2.220446049250313e-16,
          "min": 0.0,
          "p05": 0.0,
          "p25": 1.6653345369377348e-16,
          "p75": 4.440892098500626e-16,
          "p95": 1.3433698597964356e-15
        },
        "scale_estimate_changed_count": 0,
        "scale_estimate_unchanged_count": 200,
        "scene_count": 200,
        "status_transitions": {
          "LOW->LOW": 200
        },
        "unit_status_transitions": {
          "HIGH->HIGH": 160,
          "LOW->LOW": 40
        }
      },
      "single_outlier": {
        "confidence_score_after": {
          "count": 200,
          "max": 0.8888888888888888,
          "mean": 0.7249603174603101,
          "median": 0.8571428571428414,
          "min": 0.17777777777777776,
          "p05": 0.17777777777777776,
          "p25": 0.8333333333333182,
          "p75": 0.875,
          "p95": 0.8888888888888888
        },
        "e_s_after": {
          "count": 200,
          "max": 3.108624468950443e-15,
          "mean": 3.907985046680551e-16,
          "median": 2.220446049250313e-16,
          "min": 0.0,
          "p05": 0.0,
          "p25": 1.6653345369377346e-16,
          "p75": 4.440892098500625e-16,
          "p95": 1.3433698597964364e-15
        },
        "physical_unit_transitions": {
          "MM->MM": 200
        },
        "reference_status_transitions": {
          "LOW->LOW": 200
        },
        "relative_error_after": {
          "count": 200,
          "max": 3.1086244689504383e-15,
          "mean": 3.907985046680551e-16,
          "median": 2.220446049250313e-16,
          "min": 0.0,
          "p05": 0.0,
          "p25": 1.6653345369377348e-16,
          "p75": 4.440892098500626e-16,
          "p95": 1.3433698597964356e-15
        },
        "scale_estimate_changed_count": 0,
        "scale_estimate_unchanged_count": 200,
        "scene_count": 200,
        "status_transitions": {
          "LOW->LOW": 200
        },
        "unit_status_transitions": {
          "HIGH->HIGH": 160,
          "LOW->LOW": 40
        }
      },
      "stale_override": {
        "confidence_score_after": {
          "count": 200,
          "max": 0.875,
          "mean": 0.6393142857142792,
          "median": 0.8333333333333182,
          "min": 0.03333333333333333,
          "p05": 0.03333333333333333,
          "p25": 0.6399999999999885,
          "p75": 0.8571428571428571,
          "p95": 0.875
        },
        "e_s_after": {
          "count": 200,
          "max": 3.108624468950443e-15,
          "mean": 4.1799896877137155e-16,
          "median": 2.2204460492503136e-16,
          "min": 0.0,
          "p05": 0.0,
          "p25": 2.2204460492503128e-16,
          "p75": 4.440892098500625e-16,
          "p95": 1.554312234475218e-15
        },
        "physical_unit_transitions": {
          "MM->MM": 200
        },
        "reference_status_transitions": {
          "LOW->LOW": 200
        },
        "relative_error_after": {
          "count": 200,
          "max": 3.1086244689504383e-15,
          "mean": 4.1799896877137145e-16,
          "median": 2.220446049250313e-16,
          "min": 0.0,
          "p05": 0.0,
          "p25": 2.220446049250313e-16,
          "p75": 4.440892098500626e-16,
          "p95": 1.5543122344752192e-15
        },
        "scale_estimate_changed_count": 0,
        "scale_estimate_unchanged_count": 200,
        "scene_count": 200,
        "status_transitions": {
          "LOW->LOW": 200
        },
        "unit_status_transitions": {
          "HIGH->HIGH": 112,
          "HIGH->LOW": 48,
          "LOW->LOW": 40
        }
      },
      "suffix_removal": {
        "confidence_score_after": {
          "count": 200,
          "max": 1.0,
          "mean": 0.8533333333333247,
          "median": 0.9999999999999818,
          "min": 0.26666666666666666,
          "p05": 0.26666666666666666,
          "p25": 0.9999999999999636,
          "p75": 1.0,
          "p95": 1.0
        },
        "e_s_after": {
          "count": 200,
          "max": 3.108624468950443e-15,
          "mean": 3.907985046680551e-16,
          "median": 2.220446049250313e-16,
          "min": 0.0,
          "p05": 0.0,
          "p25": 1.6653345369377346e-16,
          "p75": 4.440892098500625e-16,
          "p95": 1.3433698597964364e-15
        },
        "physical_unit_transitions": {
          "MM->UNKNOWN": 200
        },
        "reference_status_transitions": {
          "LOW->LOW": 200
        },
        "relative_error_after": {
          "count": 200,
          "max": 3.1086244689504383e-15,
          "mean": 3.907985046680551e-16,
          "median": 2.220446049250313e-16,
          "min": 0.0,
          "p05": 0.0,
          "p25": 1.6653345369377348e-16,
          "p75": 4.440892098500626e-16,
          "p95": 1.3433698597964356e-15
        },
        "scale_estimate_changed_count": 0,
        "scale_estimate_unchanged_count": 200,
        "scene_count": 200,
        "status_transitions": {
          "LOW->LOW": 200
        },
        "unit_status_transitions": {
          "HIGH->HIGH": 160,
          "LOW->LOW": 40
        }
      }
    },
    "hash_assigned_primary": {
      "duplicate": {
        "base_scene_count": 11,
        "scene_count": 44,
        "unit_status_transitions": {
          "HIGH->HIGH": 36,
          "LOW->LOW": 8
        }
      },
      "single_outlier": {
        "base_scene_count": 12,
        "scene_count": 48,
        "unit_status_transitions": {
          "HIGH->HIGH": 36,
          "LOW->LOW": 12
        }
      },
      "stale_override": {
        "base_scene_count": 14,
        "scene_count": 56,
        "unit_status_transitions": {
          "HIGH->HIGH": 28,
          "HIGH->LOW": 20,
          "LOW->LOW": 8
        }
      },
      "suffix_removal": {
        "base_scene_count": 13,
        "scene_count": 52,
        "unit_status_transitions": {
          "HIGH->HIGH": 40,
          "LOW->LOW": 12
        }
      }
    }
  },
  "overall": {
    "accuracy_within_5pct": 1.0,
    "confidence_score": {
      "count": 200,
      "max": 1.0,
      "mean": 0.8533333333333247,
      "median": 0.9999999999999818,
      "min": 0.26666666666666666,
      "p05": 0.26666666666666666,
      "p25": 0.9999999999999636,
      "p75": 1.0,
      "p95": 1.0
    },
    "e_s": {
      "count": 200,
      "max": 3.108624468950443e-15,
      "mean": 3.907985046680551e-16,
      "median": 2.220446049250313e-16,
      "min": 0.0,
      "p05": 0.0,
      "p25": 1.6653345369377346e-16,
      "p75": 4.440892098500625e-16,
      "p95": 1.3433698597964364e-15
    },
    "estimate_count": 200,
    "estimate_coverage": 1.0,
    "high_accuracy_within_5pct": 1.0,
    "high_coverage": 0.8,
    "high_e_s": {
      "count": 160,
      "max": 3.108624468950443e-15,
      "mean": 4.329869796038112e-16,
      "median": 2.220446049250313e-16,
      "min": 0.0,
      "p05": 0.0,
      "p25": 1.6653345369377346e-16,
      "p75": 4.440892098500627e-16,
      "p95": 1.554312234475218e-15
    },
    "high_relative_error": {
      "count": 160,
      "max": 3.1086244689504383e-15,
      "mean": 4.3298697960381104e-16,
      "median": 2.220446049250313e-16,
      "min": 0.0,
      "p05": 0.0,
      "p25": 1.6653345369377348e-16,
      "p75": 4.440892098500626e-16,
      "p95": 1.5543122344752192e-15
    },
    "high_scene_count": 160,
    "relative_error": {
      "count": 200,
      "max": 3.1086244689504383e-15,
      "mean": 3.907985046680551e-16,
      "median": 2.220446049250313e-16,
      "min": 0.0,
      "p05": 0.0,
      "p25": 1.6653345369377348e-16,
      "p75": 4.440892098500626e-16,
      "p95": 1.3433698597964356e-15
    },
    "scene_count": 200,
    "status_counts": {
      "LOW": 200
    },
    "unit_status_counts": {
      "HIGH": 160,
      "LOW": 40
    }
  },
  "pair_label_permutation": {
    "anchor_artifact_match_rate": 1.0,
    "global_anchor_artifact_digest_after": "357de452732649b1f4a0fe51268fbc6841cec83bb135de8769e60ba6cec51e9d",
    "global_anchor_artifact_digest_before": "357de452732649b1f4a0fe51268fbc6841cec83bb135de8769e60ba6cec51e9d",
    "matching_anchor_artifact_scene_count": 200,
    "mismatching_anchor_artifact_scene_count": 0,
    "pair_label_changed_scene_count": 196,
    "scene_count": 200
  },
  "scale_confidence_rows": [
    {
      "accuracy_within_5pct": 1.0,
      "confidence": "HIGH",
      "confidence_score": {
        "count": 40,
        "max": 1.0,
        "mean": 0.9999999999999781,
        "median": 0.9999999999999818,
        "min": 0.9999999999999454,
        "p05": 0.9999999999999636,
        "p25": 0.9999999999999772,
        "p75": 0.9999999999999818,
        "p95": 1.0
      },
      "e_s": {
        "count": 40,
        "max": 1.9984014443252837e-15,
        "mean": 7.549516567451064e-16,
        "median": 6.661338147750937e-16,
        "min": 2.2204460492503136e-16,
        "p05": 2.2204460492503136e-16,
        "p25": 2.2204460492503136e-16,
        "p75": 1.1102230246251571e-15,
        "p95": 1.9984014443252837e-15
      },
      "estimate_count": 40,
      "estimate_coverage": 1.0,
      "fraction_of_scale": 0.8,
      "relative_error": {
        "count": 40,
        "max": 1.9984014443252818e-15,
        "mean": 7.549516567451064e-16,
        "median": 6.661338147750939e-16,
        "min": 2.220446049250313e-16,
        "p05": 2.220446049250313e-16,
        "p25": 2.220446049250313e-16,
        "p75": 1.1102230246251565e-15,
        "p95": 1.9984014443252818e-15
      },
      "scale_kappa": 0.001,
      "scene_count": 40
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence": "LOW",
      "confidence_score": {
        "count": 10,
        "max": 0.26666666666666666,
        "mean": 0.26666666666666666,
        "median": 0.26666666666666666,
        "min": 0.26666666666666666,
        "p05": 0.26666666666666666,
        "p25": 0.26666666666666666,
        "p75": 0.26666666666666666,
        "p95": 0.26666666666666666
      },
      "e_s": {
        "count": 10,
        "max": 2.2204460492503136e-16,
        "mean": 2.2204460492503136e-16,
        "median": 2.2204460492503136e-16,
        "min": 2.2204460492503136e-16,
        "p05": 2.2204460492503136e-16,
        "p25": 2.2204460492503136e-16,
        "p75": 2.2204460492503136e-16,
        "p95": 2.2204460492503136e-16
      },
      "estimate_count": 10,
      "estimate_coverage": 1.0,
      "fraction_of_scale": 0.2,
      "relative_error": {
        "count": 10,
        "max": 2.220446049250313e-16,
        "mean": 2.220446049250313e-16,
        "median": 2.220446049250313e-16,
        "min": 2.220446049250313e-16,
        "p05": 2.220446049250313e-16,
        "p25": 2.220446049250313e-16,
        "p75": 2.220446049250313e-16,
        "p95": 2.220446049250313e-16
      },
      "scale_kappa": 0.001,
      "scene_count": 10
    },
    {
      "accuracy_within_5pct": null,
      "confidence": "NONE",
      "confidence_score": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "e_s": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "estimate_count": 0,
      "estimate_coverage": null,
      "fraction_of_scale": 0.0,
      "relative_error": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "scale_kappa": 0.001,
      "scene_count": 0
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence": "HIGH",
      "confidence_score": {
        "count": 40,
        "max": 1.0,
        "mean": 0.9999999999999787,
        "median": 0.9999999999999818,
        "min": 0.9999999999999636,
        "p05": 0.9999999999999636,
        "p25": 0.9999999999999636,
        "p75": 0.9999999999999818,
        "p95": 1.0
      },
      "e_s": {
        "count": 40,
        "max": 3.108624468950443e-15,
        "mean": 7.549516567451067e-16,
        "median": 4.440892098500627e-16,
        "min": 4.440892098500625e-16,
        "p05": 4.440892098500625e-16,
        "p25": 4.440892098500625e-16,
        "p75": 6.661338147750938e-16,
        "p95": 2.220446049250311e-15
      },
      "estimate_count": 40,
      "estimate_coverage": 1.0,
      "fraction_of_scale": 0.8,
      "relative_error": {
        "count": 40,
        "max": 3.1086244689504383e-15,
        "mean": 7.549516567451064e-16,
        "median": 4.440892098500626e-16,
        "min": 4.440892098500626e-16,
        "p05": 4.440892098500626e-16,
        "p25": 4.440892098500626e-16,
        "p75": 6.661338147750939e-16,
        "p95": 2.220446049250313e-15
      },
      "scale_kappa": 0.01,
      "scene_count": 40
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence": "LOW",
      "confidence_score": {
        "count": 10,
        "max": 0.26666666666666666,
        "mean": 0.26666666666666666,
        "median": 0.26666666666666666,
        "min": 0.26666666666666666,
        "p05": 0.26666666666666666,
        "p25": 0.26666666666666666,
        "p75": 0.26666666666666666,
        "p95": 0.26666666666666666
      },
      "e_s": {
        "count": 10,
        "max": 4.440892098500625e-16,
        "mean": 4.440892098500625e-16,
        "median": 4.440892098500625e-16,
        "min": 4.440892098500625e-16,
        "p05": 4.440892098500625e-16,
        "p25": 4.440892098500625e-16,
        "p75": 4.440892098500625e-16,
        "p95": 4.440892098500625e-16
      },
      "estimate_count": 10,
      "estimate_coverage": 1.0,
      "fraction_of_scale": 0.2,
      "relative_error": {
        "count": 10,
        "max": 4.440892098500626e-16,
        "mean": 4.440892098500626e-16,
        "median": 4.440892098500626e-16,
        "min": 4.440892098500626e-16,
        "p05": 4.440892098500626e-16,
        "p25": 4.440892098500626e-16,
        "p75": 4.440892098500626e-16,
        "p95": 4.440892098500626e-16
      },
      "scale_kappa": 0.01,
      "scene_count": 10
    },
    {
      "accuracy_within_5pct": null,
      "confidence": "NONE",
      "confidence_score": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "e_s": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "estimate_count": 0,
      "estimate_coverage": null,
      "fraction_of_scale": 0.0,
      "relative_error": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "scale_kappa": 0.01,
      "scene_count": 0
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence": "HIGH",
      "confidence_score": {
        "count": 40,
        "max": 1.0,
        "mean": 1.0,
        "median": 1.0,
        "min": 1.0,
        "p05": 1.0,
        "p25": 1.0,
        "p75": 1.0,
        "p95": 1.0
      },
      "e_s": {
        "count": 40,
        "max": 0.0,
        "mean": 0.0,
        "median": 0.0,
        "min": 0.0,
        "p05": 0.0,
        "p25": 0.0,
        "p75": 0.0,
        "p95": 0.0
      },
      "estimate_count": 40,
      "estimate_coverage": 1.0,
      "fraction_of_scale": 0.8,
      "relative_error": {
        "count": 40,
        "max": 0.0,
        "mean": 0.0,
        "median": 0.0,
        "min": 0.0,
        "p05": 0.0,
        "p25": 0.0,
        "p75": 0.0,
        "p95": 0.0
      },
      "scale_kappa": 1.0,
      "scene_count": 40
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence": "LOW",
      "confidence_score": {
        "count": 10,
        "max": 0.26666666666666666,
        "mean": 0.26666666666666666,
        "median": 0.26666666666666666,
        "min": 0.26666666666666666,
        "p05": 0.26666666666666666,
        "p25": 0.26666666666666666,
        "p75": 0.26666666666666666,
        "p95": 0.26666666666666666
      },
      "e_s": {
        "count": 10,
        "max": 0.0,
        "mean": 0.0,
        "median": 0.0,
        "min": 0.0,
        "p05": 0.0,
        "p25": 0.0,
        "p75": 0.0,
        "p95": 0.0
      },
      "estimate_count": 10,
      "estimate_coverage": 1.0,
      "fraction_of_scale": 0.2,
      "relative_error": {
        "count": 10,
        "max": 0.0,
        "mean": 0.0,
        "median": 0.0,
        "min": 0.0,
        "p05": 0.0,
        "p25": 0.0,
        "p75": 0.0,
        "p95": 0.0
      },
      "scale_kappa": 1.0,
      "scene_count": 10
    },
    {
      "accuracy_within_5pct": null,
      "confidence": "NONE",
      "confidence_score": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "e_s": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "estimate_count": 0,
      "estimate_coverage": null,
      "fraction_of_scale": 0.0,
      "relative_error": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "scale_kappa": 1.0,
      "scene_count": 0
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence": "HIGH",
      "confidence_score": {
        "count": 40,
        "max": 1.0,
        "mean": 1.0,
        "median": 1.0,
        "min": 1.0,
        "p05": 1.0,
        "p25": 1.0,
        "p75": 1.0,
        "p95": 1.0
      },
      "e_s": {
        "count": 40,
        "max": 2.2204460492503128e-16,
        "mean": 2.2204460492503126e-16,
        "median": 2.2204460492503128e-16,
        "min": 2.2204460492503128e-16,
        "p05": 2.2204460492503128e-16,
        "p25": 2.2204460492503128e-16,
        "p75": 2.2204460492503128e-16,
        "p95": 2.2204460492503128e-16
      },
      "estimate_count": 40,
      "estimate_coverage": 1.0,
      "fraction_of_scale": 0.8,
      "relative_error": {
        "count": 40,
        "max": 2.220446049250313e-16,
        "mean": 2.220446049250313e-16,
        "median": 2.220446049250313e-16,
        "min": 2.220446049250313e-16,
        "p05": 2.220446049250313e-16,
        "p25": 2.220446049250313e-16,
        "p75": 2.220446049250313e-16,
        "p95": 2.220446049250313e-16
      },
      "scale_kappa": 1000.0,
      "scene_count": 40
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence": "LOW",
      "confidence_score": {
        "count": 10,
        "max": 0.26666666666666666,
        "mean": 0.26666666666666666,
        "median": 0.26666666666666666,
        "min": 0.26666666666666666,
        "p05": 0.26666666666666666,
        "p25": 0.26666666666666666,
        "p75": 0.26666666666666666,
        "p95": 0.26666666666666666
      },
      "e_s": {
        "count": 10,
        "max": 2.2204460492503128e-16,
        "mean": 2.2204460492503126e-16,
        "median": 2.2204460492503128e-16,
        "min": 2.2204460492503128e-16,
        "p05": 2.2204460492503128e-16,
        "p25": 2.2204460492503128e-16,
        "p75": 2.2204460492503128e-16,
        "p95": 2.2204460492503128e-16
      },
      "estimate_count": 10,
      "estimate_coverage": 1.0,
      "fraction_of_scale": 0.2,
      "relative_error": {
        "count": 10,
        "max": 2.220446049250313e-16,
        "mean": 2.220446049250313e-16,
        "median": 2.220446049250313e-16,
        "min": 2.220446049250313e-16,
        "p05": 2.220446049250313e-16,
        "p25": 2.220446049250313e-16,
        "p75": 2.220446049250313e-16,
        "p95": 2.220446049250313e-16
      },
      "scale_kappa": 1000.0,
      "scene_count": 10
    },
    {
      "accuracy_within_5pct": null,
      "confidence": "NONE",
      "confidence_score": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "e_s": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "estimate_count": 0,
      "estimate_coverage": null,
      "fraction_of_scale": 0.0,
      "relative_error": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "scale_kappa": 1000.0,
      "scene_count": 0
    }
  ],
  "score_calibration_rows": [
    {
      "accuracy_within_5pct": null,
      "confidence_score": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "e_s": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "estimate_count": 0,
      "estimate_coverage": null,
      "lower": 0.0,
      "relative_error": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "scale_kappa": "ALL",
      "scene_count": 0,
      "score_bin": "[0.00,0.25)",
      "upper": 0.25,
      "upper_inclusive": false
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 40,
        "max": 0.26666666666666666,
        "mean": 0.26666666666666666,
        "median": 0.26666666666666666,
        "min": 0.26666666666666666,
        "p05": 0.26666666666666666,
        "p25": 0.26666666666666666,
        "p75": 0.26666666666666666,
        "p95": 0.26666666666666666
      },
      "e_s": {
        "count": 40,
        "max": 4.440892098500625e-16,
        "mean": 2.220446049250313e-16,
        "median": 2.220446049250313e-16,
        "min": 0.0,
        "p05": 0.0,
        "p25": 1.6653345369377346e-16,
        "p75": 2.7755575615628914e-16,
        "p95": 4.440892098500625e-16
      },
      "estimate_count": 40,
      "estimate_coverage": 1.0,
      "lower": 0.25,
      "relative_error": {
        "count": 40,
        "max": 4.440892098500626e-16,
        "mean": 2.220446049250313e-16,
        "median": 2.220446049250313e-16,
        "min": 0.0,
        "p05": 0.0,
        "p25": 1.6653345369377348e-16,
        "p75": 2.7755575615628914e-16,
        "p95": 4.440892098500626e-16
      },
      "scale_kappa": "ALL",
      "scene_count": 40,
      "score_bin": "[0.25,0.50)",
      "upper": 0.5,
      "upper_inclusive": false
    },
    {
      "accuracy_within_5pct": null,
      "confidence_score": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "e_s": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "estimate_count": 0,
      "estimate_coverage": null,
      "lower": 0.5,
      "relative_error": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "scale_kappa": "ALL",
      "scene_count": 0,
      "score_bin": "[0.50,0.75)",
      "upper": 0.75,
      "upper_inclusive": false
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 160,
        "max": 1.0,
        "mean": 0.9999999999999891,
        "median": 1.0,
        "min": 0.9999999999999454,
        "p05": 0.9999999999999636,
        "p25": 0.9999999999999818,
        "p75": 1.0,
        "p95": 1.0
      },
      "e_s": {
        "count": 160,
        "max": 3.108624468950443e-15,
        "mean": 4.329869796038112e-16,
        "median": 2.220446049250313e-16,
        "min": 0.0,
        "p05": 0.0,
        "p25": 1.6653345369377346e-16,
        "p75": 4.440892098500627e-16,
        "p95": 1.554312234475218e-15
      },
      "estimate_count": 160,
      "estimate_coverage": 1.0,
      "lower": 0.75,
      "relative_error": {
        "count": 160,
        "max": 3.1086244689504383e-15,
        "mean": 4.3298697960381104e-16,
        "median": 2.220446049250313e-16,
        "min": 0.0,
        "p05": 0.0,
        "p25": 1.6653345369377348e-16,
        "p75": 4.440892098500626e-16,
        "p95": 1.5543122344752192e-15
      },
      "scale_kappa": "ALL",
      "scene_count": 160,
      "score_bin": "[0.75,1.00]",
      "upper": 1.0,
      "upper_inclusive": true
    },
    {
      "accuracy_within_5pct": null,
      "confidence_score": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "e_s": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "estimate_count": 0,
      "estimate_coverage": null,
      "lower": 0.0,
      "relative_error": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "scale_kappa": "0.001",
      "scene_count": 0,
      "score_bin": "[0.00,0.25)",
      "upper": 0.25,
      "upper_inclusive": false
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 10,
        "max": 0.26666666666666666,
        "mean": 0.26666666666666666,
        "median": 0.26666666666666666,
        "min": 0.26666666666666666,
        "p05": 0.26666666666666666,
        "p25": 0.26666666666666666,
        "p75": 0.26666666666666666,
        "p95": 0.26666666666666666
      },
      "e_s": {
        "count": 10,
        "max": 2.2204460492503136e-16,
        "mean": 2.2204460492503136e-16,
        "median": 2.2204460492503136e-16,
        "min": 2.2204460492503136e-16,
        "p05": 2.2204460492503136e-16,
        "p25": 2.2204460492503136e-16,
        "p75": 2.2204460492503136e-16,
        "p95": 2.2204460492503136e-16
      },
      "estimate_count": 10,
      "estimate_coverage": 1.0,
      "lower": 0.25,
      "relative_error": {
        "count": 10,
        "max": 2.220446049250313e-16,
        "mean": 2.220446049250313e-16,
        "median": 2.220446049250313e-16,
        "min": 2.220446049250313e-16,
        "p05": 2.220446049250313e-16,
        "p25": 2.220446049250313e-16,
        "p75": 2.220446049250313e-16,
        "p95": 2.220446049250313e-16
      },
      "scale_kappa": "0.001",
      "scene_count": 10,
      "score_bin": "[0.25,0.50)",
      "upper": 0.5,
      "upper_inclusive": false
    },
    {
      "accuracy_within_5pct": null,
      "confidence_score": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "e_s": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "estimate_count": 0,
      "estimate_coverage": null,
      "lower": 0.5,
      "relative_error": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "scale_kappa": "0.001",
      "scene_count": 0,
      "score_bin": "[0.50,0.75)",
      "upper": 0.75,
      "upper_inclusive": false
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 40,
        "max": 1.0,
        "mean": 0.9999999999999781,
        "median": 0.9999999999999818,
        "min": 0.9999999999999454,
        "p05": 0.9999999999999636,
        "p25": 0.9999999999999772,
        "p75": 0.9999999999999818,
        "p95": 1.0
      },
      "e_s": {
        "count": 40,
        "max": 1.9984014443252837e-15,
        "mean": 7.549516567451064e-16,
        "median": 6.661338147750937e-16,
        "min": 2.2204460492503136e-16,
        "p05": 2.2204460492503136e-16,
        "p25": 2.2204460492503136e-16,
        "p75": 1.1102230246251571e-15,
        "p95": 1.9984014443252837e-15
      },
      "estimate_count": 40,
      "estimate_coverage": 1.0,
      "lower": 0.75,
      "relative_error": {
        "count": 40,
        "max": 1.9984014443252818e-15,
        "mean": 7.549516567451064e-16,
        "median": 6.661338147750939e-16,
        "min": 2.220446049250313e-16,
        "p05": 2.220446049250313e-16,
        "p25": 2.220446049250313e-16,
        "p75": 1.1102230246251565e-15,
        "p95": 1.9984014443252818e-15
      },
      "scale_kappa": "0.001",
      "scene_count": 40,
      "score_bin": "[0.75,1.00]",
      "upper": 1.0,
      "upper_inclusive": true
    },
    {
      "accuracy_within_5pct": null,
      "confidence_score": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "e_s": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "estimate_count": 0,
      "estimate_coverage": null,
      "lower": 0.0,
      "relative_error": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "scale_kappa": "0.01",
      "scene_count": 0,
      "score_bin": "[0.00,0.25)",
      "upper": 0.25,
      "upper_inclusive": false
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 10,
        "max": 0.26666666666666666,
        "mean": 0.26666666666666666,
        "median": 0.26666666666666666,
        "min": 0.26666666666666666,
        "p05": 0.26666666666666666,
        "p25": 0.26666666666666666,
        "p75": 0.26666666666666666,
        "p95": 0.26666666666666666
      },
      "e_s": {
        "count": 10,
        "max": 4.440892098500625e-16,
        "mean": 4.440892098500625e-16,
        "median": 4.440892098500625e-16,
        "min": 4.440892098500625e-16,
        "p05": 4.440892098500625e-16,
        "p25": 4.440892098500625e-16,
        "p75": 4.440892098500625e-16,
        "p95": 4.440892098500625e-16
      },
      "estimate_count": 10,
      "estimate_coverage": 1.0,
      "lower": 0.25,
      "relative_error": {
        "count": 10,
        "max": 4.440892098500626e-16,
        "mean": 4.440892098500626e-16,
        "median": 4.440892098500626e-16,
        "min": 4.440892098500626e-16,
        "p05": 4.440892098500626e-16,
        "p25": 4.440892098500626e-16,
        "p75": 4.440892098500626e-16,
        "p95": 4.440892098500626e-16
      },
      "scale_kappa": "0.01",
      "scene_count": 10,
      "score_bin": "[0.25,0.50)",
      "upper": 0.5,
      "upper_inclusive": false
    },
    {
      "accuracy_within_5pct": null,
      "confidence_score": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "e_s": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "estimate_count": 0,
      "estimate_coverage": null,
      "lower": 0.5,
      "relative_error": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "scale_kappa": "0.01",
      "scene_count": 0,
      "score_bin": "[0.50,0.75)",
      "upper": 0.75,
      "upper_inclusive": false
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 40,
        "max": 1.0,
        "mean": 0.9999999999999787,
        "median": 0.9999999999999818,
        "min": 0.9999999999999636,
        "p05": 0.9999999999999636,
        "p25": 0.9999999999999636,
        "p75": 0.9999999999999818,
        "p95": 1.0
      },
      "e_s": {
        "count": 40,
        "max": 3.108624468950443e-15,
        "mean": 7.549516567451067e-16,
        "median": 4.440892098500627e-16,
        "min": 4.440892098500625e-16,
        "p05": 4.440892098500625e-16,
        "p25": 4.440892098500625e-16,
        "p75": 6.661338147750938e-16,
        "p95": 2.220446049250311e-15
      },
      "estimate_count": 40,
      "estimate_coverage": 1.0,
      "lower": 0.75,
      "relative_error": {
        "count": 40,
        "max": 3.1086244689504383e-15,
        "mean": 7.549516567451064e-16,
        "median": 4.440892098500626e-16,
        "min": 4.440892098500626e-16,
        "p05": 4.440892098500626e-16,
        "p25": 4.440892098500626e-16,
        "p75": 6.661338147750939e-16,
        "p95": 2.220446049250313e-15
      },
      "scale_kappa": "0.01",
      "scene_count": 40,
      "score_bin": "[0.75,1.00]",
      "upper": 1.0,
      "upper_inclusive": true
    },
    {
      "accuracy_within_5pct": null,
      "confidence_score": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "e_s": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "estimate_count": 0,
      "estimate_coverage": null,
      "lower": 0.0,
      "relative_error": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "scale_kappa": "1",
      "scene_count": 0,
      "score_bin": "[0.00,0.25)",
      "upper": 0.25,
      "upper_inclusive": false
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 10,
        "max": 0.26666666666666666,
        "mean": 0.26666666666666666,
        "median": 0.26666666666666666,
        "min": 0.26666666666666666,
        "p05": 0.26666666666666666,
        "p25": 0.26666666666666666,
        "p75": 0.26666666666666666,
        "p95": 0.26666666666666666
      },
      "e_s": {
        "count": 10,
        "max": 0.0,
        "mean": 0.0,
        "median": 0.0,
        "min": 0.0,
        "p05": 0.0,
        "p25": 0.0,
        "p75": 0.0,
        "p95": 0.0
      },
      "estimate_count": 10,
      "estimate_coverage": 1.0,
      "lower": 0.25,
      "relative_error": {
        "count": 10,
        "max": 0.0,
        "mean": 0.0,
        "median": 0.0,
        "min": 0.0,
        "p05": 0.0,
        "p25": 0.0,
        "p75": 0.0,
        "p95": 0.0
      },
      "scale_kappa": "1",
      "scene_count": 10,
      "score_bin": "[0.25,0.50)",
      "upper": 0.5,
      "upper_inclusive": false
    },
    {
      "accuracy_within_5pct": null,
      "confidence_score": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "e_s": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "estimate_count": 0,
      "estimate_coverage": null,
      "lower": 0.5,
      "relative_error": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "scale_kappa": "1",
      "scene_count": 0,
      "score_bin": "[0.50,0.75)",
      "upper": 0.75,
      "upper_inclusive": false
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 40,
        "max": 1.0,
        "mean": 1.0,
        "median": 1.0,
        "min": 1.0,
        "p05": 1.0,
        "p25": 1.0,
        "p75": 1.0,
        "p95": 1.0
      },
      "e_s": {
        "count": 40,
        "max": 0.0,
        "mean": 0.0,
        "median": 0.0,
        "min": 0.0,
        "p05": 0.0,
        "p25": 0.0,
        "p75": 0.0,
        "p95": 0.0
      },
      "estimate_count": 40,
      "estimate_coverage": 1.0,
      "lower": 0.75,
      "relative_error": {
        "count": 40,
        "max": 0.0,
        "mean": 0.0,
        "median": 0.0,
        "min": 0.0,
        "p05": 0.0,
        "p25": 0.0,
        "p75": 0.0,
        "p95": 0.0
      },
      "scale_kappa": "1",
      "scene_count": 40,
      "score_bin": "[0.75,1.00]",
      "upper": 1.0,
      "upper_inclusive": true
    },
    {
      "accuracy_within_5pct": null,
      "confidence_score": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "e_s": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "estimate_count": 0,
      "estimate_coverage": null,
      "lower": 0.0,
      "relative_error": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "scale_kappa": "1000",
      "scene_count": 0,
      "score_bin": "[0.00,0.25)",
      "upper": 0.25,
      "upper_inclusive": false
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 10,
        "max": 0.26666666666666666,
        "mean": 0.26666666666666666,
        "median": 0.26666666666666666,
        "min": 0.26666666666666666,
        "p05": 0.26666666666666666,
        "p25": 0.26666666666666666,
        "p75": 0.26666666666666666,
        "p95": 0.26666666666666666
      },
      "e_s": {
        "count": 10,
        "max": 2.2204460492503128e-16,
        "mean": 2.2204460492503126e-16,
        "median": 2.2204460492503128e-16,
        "min": 2.2204460492503128e-16,
        "p05": 2.2204460492503128e-16,
        "p25": 2.2204460492503128e-16,
        "p75": 2.2204460492503128e-16,
        "p95": 2.2204460492503128e-16
      },
      "estimate_count": 10,
      "estimate_coverage": 1.0,
      "lower": 0.25,
      "relative_error": {
        "count": 10,
        "max": 2.220446049250313e-16,
        "mean": 2.220446049250313e-16,
        "median": 2.220446049250313e-16,
        "min": 2.220446049250313e-16,
        "p05": 2.220446049250313e-16,
        "p25": 2.220446049250313e-16,
        "p75": 2.220446049250313e-16,
        "p95": 2.220446049250313e-16
      },
      "scale_kappa": "1000",
      "scene_count": 10,
      "score_bin": "[0.25,0.50)",
      "upper": 0.5,
      "upper_inclusive": false
    },
    {
      "accuracy_within_5pct": null,
      "confidence_score": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "e_s": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "estimate_count": 0,
      "estimate_coverage": null,
      "lower": 0.5,
      "relative_error": {
        "count": 0,
        "max": null,
        "mean": null,
        "median": null,
        "min": null,
        "p05": null,
        "p25": null,
        "p75": null,
        "p95": null
      },
      "scale_kappa": "1000",
      "scene_count": 0,
      "score_bin": "[0.50,0.75)",
      "upper": 0.75,
      "upper_inclusive": false
    },
    {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 40,
        "max": 1.0,
        "mean": 1.0,
        "median": 1.0,
        "min": 1.0,
        "p05": 1.0,
        "p25": 1.0,
        "p75": 1.0,
        "p95": 1.0
      },
      "e_s": {
        "count": 40,
        "max": 2.2204460492503128e-16,
        "mean": 2.2204460492503126e-16,
        "median": 2.2204460492503128e-16,
        "min": 2.2204460492503128e-16,
        "p05": 2.2204460492503128e-16,
        "p25": 2.2204460492503128e-16,
        "p75": 2.2204460492503128e-16,
        "p95": 2.2204460492503128e-16
      },
      "estimate_count": 40,
      "estimate_coverage": 1.0,
      "lower": 0.75,
      "relative_error": {
        "count": 40,
        "max": 2.220446049250313e-16,
        "mean": 2.220446049250313e-16,
        "median": 2.220446049250313e-16,
        "min": 2.220446049250313e-16,
        "p05": 2.220446049250313e-16,
        "p25": 2.220446049250313e-16,
        "p75": 2.220446049250313e-16,
        "p95": 2.220446049250313e-16
      },
      "scale_kappa": "1000",
      "scene_count": 40,
      "score_bin": "[0.75,1.00]",
      "upper": 1.0,
      "upper_inclusive": true
    }
  ]
}
```

## 산출물 검증 수치

| artifact | status | bytes | sha256_or_digest |
| --- | --- | --- | --- |
| loop_l1b.py | GENERATED | 55489 | ac8a9c0aa1dc477db2badec22b42268941ad0c9d40a4e8c2a9ee9e7a3b489e00 |
| scenes_v2 | GENERATED | 14661779 | 841d22d6eecc455c8fba4b9268f19fe963faa46671ebeeab9f1b6f07aa305fac |
| c0v3_numbers.json | GENERATED | 49544 | 67344926babdc24c75a4620a7182a3e7472db748ecb2dff32ff1de8fde100659 |
| c1v3_results.json | GENERATED | 1380198 | 6e6f5a63d33b70fd19813481642b9af42aabf8ad36738402279b887873c9ae19 |
| evidence.xlsx | GENERATED | 29961 | cedaf098fa3d8ce4af68bc2a6c2cbdd9bd8f11eecdfd5baf74d1424f8776d34f |

## 미해결

- evidence workbook 구조 검증 required sheet 수는 11, formula error 수는 0, raster render 수는 0이다.
- source read-only manifest mismatch 수는 0, v3 scene input manifest mismatch 수는 0이다.
- reference_status 분포는 `{"LOW": 200}`, unit_status 분포는 `{"HIGH": 160, "LOW": 40}`다.
- 원본 CAD 접근 수와 test split 접근 수는 각각 0이다.

LOOP_COMPLETE: L1b
