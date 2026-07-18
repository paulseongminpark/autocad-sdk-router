# E2 Loop L1 — 앵커-풍부 장면 재생성 및 C1 재평가

## 설계 및 실행 경계

- C0의 seed 규칙과 구조 생성·scale 복제·fidelity·truth validator를 read-only import했고, anchor builder만 scene당 seed 결정적 5~8 DIM ratio로 확장했다.
- 각 DIM ratio는 서로 다른 geometry span과 source handle을 가지며 midpoint는 C1의 상대 3×3 공간 bin 중 최소 3개 이상에 놓였다.
- C1의 estimator, 봉인 confidence 식, 네 corruption, pair-label permutation digest는 수정 없이 import·실행했다.
- 출력은 `D:\runs\e2_program\cells\loop_l1` 아래로 한정했다. 원본 CAD와 test split은 접근하지 않았고 repository 및 v1 산출물은 수정하지 않았다.
- 이 보고서는 수치와 selftest 상태만 기록하며 목표·게이트·이론 판정을 기록하지 않는다.

## Selftest 전문

```text
=== loop_l1 anchor-rich selftest ===
SELFTEST c0_seed_rule_unchanged: PASS | j=7 seed=1680878578 expected=1680878578
SELFTEST same_j_same_sha: PASS | j=7 sha256=a461d1d5c3b20b0f8f23f591befb5e7c24ee463233fbf7633556aab3233d061a
SELFTEST fixture_anchor_count_rule: PASS | observed=7 expected=7
SELFTEST fixture_independent_distinct_spans: PASS | span_count=7 distinct=7
SELFTEST fixture_canonical_independence: PASS | input=7 canonical=7 duplicates=0
SELFTEST fixture_spatial_bins: PASS | n_spatial_bins=7
SELFTEST fixture_ratio_estimate: PASS | estimate=1.0 unit_status=HIGH confidence=1
SELFTEST same_j_four_scale_topology: PASS | unique_topology_sha=1
SELFTEST same_j_four_scale_normalized_geometry: PASS | unique_normalized_geometry_sha=1
SELFTEST truth_validator_positive_cases: PASS | scene_count=4 error_count=0
SELFTEST truth_validator_negative_case_honest_fail: PASS | error_count=4
SELFTEST truth_key_access_guard: PASS | accessed_keys=['anchors']
SELFTEST anchor_count_distribution: PASS | distribution={5: 14, 6: 12, 7: 8, 8: 16} rule_mismatches=0
SELFTEST all_base_spatial_bins_ge_3: PASS | below_3_scene_count=0
SELFTEST all_base_spans_distinct: PASS | distinct_span_mismatch_scene_count=0
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

## 앵커 수·독립성 분포

| metric | value |
| --- | --- |
| base_anchor_count_distribution | {"5": 14, "6": 12, "7": 8, "8": 16} |
| ir_anchor_count_distribution | {"5": 56, "6": 48, "7": 32, "8": 64} |
| base_anchor_count_min | 5 |
| base_anchor_count_mean | 6.52 |
| base_anchor_count_max | 8 |
| base_spatial_bin_count_distribution | {"5": 14, "6": 12, "7": 8, "8": 16} |
| base_spatial_bin_count_min | 5 |
| base_spatial_bin_below_3_scene_count | 0 |
| base_distinct_span_mismatch_scene_count | 0 |
| base_canonical_anchor_count_mismatch_scene_count | 0 |
| ir_display_raw_truth_ratio_mismatch_count | 0 |

## v1 대비 C0v2 변화 수치

| metric | v1 | v2 | delta |
| --- | --- | --- | --- |
| scene_counts.base_scene_count | 50 | 50 | 0 |
| scene_counts.ir_scene_count | 200 | 200 | 0 |
| truth_pair_numbers.ir_truth_pair_count | 204 | 204 | 0 |
| truth_validator.error_count | 0 | 0 | 0 |
| fidelity_numbers_kappa_1.entity_mix_tv | 0.000211914583407 | 0.000211914583407 | 0 |
| fidelity_numbers_kappa_1.thickness_histogram_ks | 0.0402878554373 | 0.0402878554373 | 0 |
| mutation_family_coverage.single_reference_span_region.scene_count | 25 | 0 | -25 |
| mutation_family_coverage.multiple_reference_span_regions.scene_count | 25 | 50 | 25 |
| determinism_and_scale_numbers.four_scale_topology_mismatch_base_scene_count | 0 | 0 | 0 |
| determinism_and_scale_numbers.four_scale_normalized_geometry_mismatch_base_scene_count | 0 | 0 | 0 |
| determinism_and_scale_numbers.four_scale_source_handle_mismatch_base_scene_count | 0 | 0 | 0 |
| ratio_anchor_count_per_scene.min | 3 | 5 | 2 |
| ratio_anchor_count_per_scene.mean | 3 | 6.52 | 3.52 |
| ratio_anchor_count_per_scene.max | 3 | 8 | 5 |
| spatial_bin_count_per_scene.min | 3 | 5 | 2 |
| distinct_span_mismatch_scene_count | null | 0 | null |

## v1 대비 C1v2 변화 수치

| metric | v1 | v2 | delta |
| --- | --- | --- | --- |
| estimate_count | 200 | 200 | 0 |
| estimate_coverage | 1 | 1 | 0 |
| accuracy_within_5pct | 1 | 1 | 0 |
| HIGH_scene_count | 0 | 200 | 200 |
| HIGH_coverage | 0 | 1 | 1 |
| HIGH_accuracy_within_5pct | null | 1 | null |
| pair_label_mismatch_scene_count | 0 | 0 | 0 |
| single_outlier_LOW_to_HIGH_status_count | 26 | 0 | -26 |
| single_outlier_scale_estimate_unchanged_count | 200 | 200 | 0 |

## C0v2 커버리지·fidelity·truth 수치 전문

```json
{
  "anchor_richness": {
    "anchor_count_rule": "5 + (uint32_seed mod 4)",
    "base_anchor_count_distribution": {
      "5": 14,
      "6": 12,
      "7": 8,
      "8": 16
    },
    "base_anchor_count_max": 8,
    "base_anchor_count_mean": 6.52,
    "base_anchor_count_median": 6.0,
    "base_anchor_count_min": 5,
    "base_anchor_count_rule_mismatch_scene_count": 0,
    "base_canonical_anchor_count_distribution": {
      "5": 14,
      "6": 12,
      "7": 8,
      "8": 16
    },
    "base_canonical_anchor_count_mismatch_scene_count": 0,
    "base_distinct_span_count_distribution": {
      "5": 14,
      "6": 12,
      "7": 8,
      "8": 16
    },
    "base_distinct_span_mismatch_scene_count": 0,
    "base_minimum_adjacent_log_span_separation": 0.0679873409849328,
    "base_non_dim_text_ratio_anchor_count": 0,
    "base_reference_status_counts": {
      "LOW": 50
    },
    "base_spatial_bin_below_3_scene_count": 0,
    "base_spatial_bin_count_distribution": {
      "5": 14,
      "6": 12,
      "7": 8,
      "8": 16
    },
    "base_spatial_bin_count_min": 5,
    "base_unit_confidence_score": {
      "count": 50,
      "max": 1.0,
      "mean": 1.0,
      "median": 1.0,
      "min": 1.0,
      "p05": 1.0,
      "p25": 1.0,
      "p75": 1.0,
      "p95": 1.0
    },
    "base_unit_status_counts": {
      "HIGH": 50
    },
    "c1_ransac_log_tolerance": 0.04879016416943204,
    "ir_anchor_count_distribution": {
      "5": 56,
      "6": 48,
      "7": 32,
      "8": 64
    },
    "ir_display_raw_truth_ratio_mismatch_count": 0
  },
  "build_numbers": {
    "entity_profile_filler_count": 5100,
    "entity_profile_target_total": 8000,
    "fidelity_gap_sample_target": 1200
  },
  "contract": {
    "c0_import": "D:\\dev\\99_tools\\autocad-sdk-router\\tools\\e2\\cells\\feyerabend_c0.py",
    "c1_import": "D:\\dev\\99_tools\\autocad-sdk-router\\tools\\e2\\cells\\feyerabend_c1.py",
    "gate_verdict_emitted": false,
    "random_search_count": 0,
    "source_cad_access_count": 0,
    "source_dossier": "D:\\dev\\99_tools\\autocad-sdk-router\\reports\\e2\\dossiers\\feyerabend_P2.md",
    "source_packet": "D:\\runs\\e2_program\\build\\PACKET_loop_L1_anchor_rich.md",
    "test_split_access_count": 0,
    "write_root": "D:\\runs\\e2_program\\cells\\loop_l1"
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
      "scene_count": 50,
      "scene_ratio": 1.0
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
      "scene_count": 0,
      "scene_ratio": 0.0
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
  "schema": "ariadne.e2.loop_l1.c0v2_numbers.v1",
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
        "detail": "j=7 seed=1680878578 expected=1680878578",
        "name": "c0_seed_rule_unchanged",
        "passed": true
      },
      {
        "detail": "j=7 sha256=a461d1d5c3b20b0f8f23f591befb5e7c24ee463233fbf7633556aab3233d061a",
        "name": "same_j_same_sha",
        "passed": true
      },
      {
        "detail": "observed=7 expected=7",
        "name": "fixture_anchor_count_rule",
        "passed": true
      },
      {
        "detail": "span_count=7 distinct=7",
        "name": "fixture_independent_distinct_spans",
        "passed": true
      },
      {
        "detail": "input=7 canonical=7 duplicates=0",
        "name": "fixture_canonical_independence",
        "passed": true
      },
      {
        "detail": "n_spatial_bins=7",
        "name": "fixture_spatial_bins",
        "passed": true
      },
      {
        "detail": "estimate=1.0 unit_status=HIGH confidence=1",
        "name": "fixture_ratio_estimate",
        "passed": true
      },
      {
        "detail": "unique_topology_sha=1",
        "name": "same_j_four_scale_topology",
        "passed": true
      },
      {
        "detail": "unique_normalized_geometry_sha=1",
        "name": "same_j_four_scale_normalized_geometry",
        "passed": true
      },
      {
        "detail": "scene_count=4 error_count=0",
        "name": "truth_validator_positive_cases",
        "passed": true
      },
      {
        "detail": "error_count=4",
        "name": "truth_validator_negative_case_honest_fail",
        "passed": true
      },
      {
        "detail": "accessed_keys=['anchors']",
        "name": "truth_key_access_guard",
        "passed": true
      },
      {
        "detail": "distribution={5: 14, 6: 12, 7: 8, 8: 16} rule_mismatches=0",
        "name": "anchor_count_distribution",
        "passed": true
      },
      {
        "detail": "below_3_scene_count=0",
        "name": "all_base_spatial_bins_ge_3",
        "passed": true
      },
      {
        "detail": "distinct_span_mismatch_scene_count=0",
        "name": "all_base_spans_distinct",
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
    "transcript": "=== loop_l1 anchor-rich selftest ===\nSELFTEST c0_seed_rule_unchanged: PASS | j=7 seed=1680878578 expected=1680878578\nSELFTEST same_j_same_sha: PASS | j=7 sha256=a461d1d5c3b20b0f8f23f591befb5e7c24ee463233fbf7633556aab3233d061a\nSELFTEST fixture_anchor_count_rule: PASS | observed=7 expected=7\nSELFTEST fixture_independent_distinct_spans: PASS | span_count=7 distinct=7\nSELFTEST fixture_canonical_independence: PASS | input=7 canonical=7 duplicates=0\nSELFTEST fixture_spatial_bins: PASS | n_spatial_bins=7\nSELFTEST fixture_ratio_estimate: PASS | estimate=1.0 unit_status=HIGH confidence=1\nSELFTEST same_j_four_scale_topology: PASS | unique_topology_sha=1\nSELFTEST same_j_four_scale_normalized_geometry: PASS | unique_normalized_geometry_sha=1\nSELFTEST truth_validator_positive_cases: PASS | scene_count=4 error_count=0\nSELFTEST truth_validator_negative_case_honest_fail: PASS | error_count=4\nSELFTEST truth_key_access_guard: PASS | accessed_keys=['anchors']\nSELFTEST anchor_count_distribution: PASS | distribution={5: 14, 6: 12, 7: 8, 8: 16} rule_mismatches=0\nSELFTEST all_base_spatial_bins_ge_3: PASS | below_3_scene_count=0\nSELFTEST all_base_spans_distinct: PASS | distinct_span_mismatch_scene_count=0\nSELFTEST permitted_gen2_synthetic_fixture: PASS | wall_records=2 entity_types=['ARC', 'CIRCLE', 'HATCH', 'LINE', 'LWPOLYLINE', 'MTEXT', 'SPLINE', 'TEXT']\n=== imported sealed C1 selftests ===\nSELFTEST exact_anchor_exact_scale: PASS | estimate=2.5 expected=2.5 unit_status=HIGH\nSELFTEST exact_anchor_high_confidence: PASS | unit_status=HIGH confidence=1\nSELFTEST no_anchor_honest_no_estimate: PASS | estimate=None unit_status=NONE status=NONE\nSELFTEST corruption_reproducibility: PASS | duplicate=b7eafb24bff4 stale_override=4587fb707ef7 suffix_removal=d5721ef40250 single_outlier=802397c8b4a3\nSELFTEST single_outlier_mode_or_downgrade: PASS | estimate=2.5 unit_status=HIGH\nSELFTEST truth_key_access_guard: PASS | accessed_keys=['anchors']\nSELFTEST SUMMARY: 6/6 passed\nSELFTEST sealed_c1_selftests: PASS | passed=6 total=6\nSELFTEST SUMMARY: 17/17 passed\nSELFTEST_RESULT: PASS\n"
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
      "metric": "scene_counts.base_scene_count",
      "v1": 50,
      "v2": 50
    },
    {
      "delta": 0.0,
      "metric": "scene_counts.ir_scene_count",
      "v1": 200,
      "v2": 200
    },
    {
      "delta": 0.0,
      "metric": "truth_pair_numbers.ir_truth_pair_count",
      "v1": 204,
      "v2": 204
    },
    {
      "delta": 0.0,
      "metric": "truth_validator.error_count",
      "v1": 0,
      "v2": 0
    },
    {
      "delta": 0.0,
      "metric": "fidelity_numbers_kappa_1.entity_mix_tv",
      "v1": 0.00021191458340744963,
      "v2": 0.00021191458340744963
    },
    {
      "delta": 0.0,
      "metric": "fidelity_numbers_kappa_1.thickness_histogram_ks",
      "v1": 0.040287855437306064,
      "v2": 0.040287855437306064
    },
    {
      "delta": -25.0,
      "metric": "mutation_family_coverage.single_reference_span_region.scene_count",
      "v1": 25,
      "v2": 0
    },
    {
      "delta": 25.0,
      "metric": "mutation_family_coverage.multiple_reference_span_regions.scene_count",
      "v1": 25,
      "v2": 50
    },
    {
      "delta": 0.0,
      "metric": "determinism_and_scale_numbers.four_scale_topology_mismatch_base_scene_count",
      "v1": 0,
      "v2": 0
    },
    {
      "delta": 0.0,
      "metric": "determinism_and_scale_numbers.four_scale_normalized_geometry_mismatch_base_scene_count",
      "v1": 0,
      "v2": 0
    },
    {
      "delta": 0.0,
      "metric": "determinism_and_scale_numbers.four_scale_source_handle_mismatch_base_scene_count",
      "v1": 0,
      "v2": 0
    },
    {
      "delta": 2.0,
      "metric": "ratio_anchor_count_per_scene.min",
      "v1": 3,
      "v2": 5
    },
    {
      "delta": 3.5199999999999996,
      "metric": "ratio_anchor_count_per_scene.mean",
      "v1": 3,
      "v2": 6.52
    },
    {
      "delta": 5.0,
      "metric": "ratio_anchor_count_per_scene.max",
      "v1": 3,
      "v2": 8
    },
    {
      "delta": 2.0,
      "metric": "spatial_bin_count_per_scene.min",
      "v1": 3,
      "v2": 5
    },
    {
      "delta": null,
      "metric": "distinct_span_mismatch_scene_count",
      "v1": null,
      "v2": 0
    }
  ]
}
```

## C1v2 전체 scale 추정 수치

| metric | value |
| --- | --- |
| scene_count | 200 |
| estimate_count | 200 |
| estimate_coverage | 1 |
| accuracy_within_5pct | 1 |
| HIGH_scene_count | 200 |
| HIGH_coverage | 1 |
| HIGH_accuracy_within_5pct | 1 |
| e_s_min | 0 |
| e_s_median | 2.22044604925e-16 |
| e_s_p95 | 1.55431223448e-15 |
| e_s_max | 3.10862446895e-15 |
| relative_error_min | 0 |
| relative_error_median | 2.22044604925e-16 |
| relative_error_p95 | 1.55431223448e-15 |
| relative_error_max | 3.10862446895e-15 |

## Scale × confidence 전 행

| kappa | unit_status | n | fraction | n_est | accuracy_5pct | e_s_med | e_s_p95 | relerr_med | relerr_p95 | conf_med |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.001 | HIGH | 50 | 1 | 50 | 1 | 6.66133814775e-16 | 1.99840144433e-15 | 6.66133814775e-16 | 1.99840144433e-15 | 1 |
| 0.001 | LOW | 0 | 0 | 0 | null | null | null | null | null | null |
| 0.001 | NONE | 0 | 0 | 0 | null | null | null | null | null | null |
| 0.01 | HIGH | 50 | 1 | 50 | 1 | 4.4408920985e-16 | 1.82076576039e-15 | 4.4408920985e-16 | 1.82076576039e-15 | 1 |
| 0.01 | LOW | 0 | 0 | 0 | null | null | null | null | null | null |
| 0.01 | NONE | 0 | 0 | 0 | null | null | null | null | null | null |
| 1 | HIGH | 50 | 1 | 50 | 1 | 0 | 0 | 0 | 0 | 1 |
| 1 | LOW | 0 | 0 | 0 | null | null | null | null | null | null |
| 1 | NONE | 0 | 0 | 0 | null | null | null | null | null | null |
| 1000 | HIGH | 50 | 1 | 50 | 1 | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 | 1 |
| 1000 | LOW | 0 | 0 | 0 | null | null | null | null | null | null |
| 1000 | NONE | 0 | 0 | 0 | null | null | null | null | null | null |

## Numeric confidence-score bin별 accuracy

| scale | score_bin | n | n_est | accuracy_5pct | relerr_med | relerr_p95 |
| --- | --- | --- | --- | --- | --- | --- |
| ALL | [0.00,0.25) | 0 | 0 | null | null | null |
| ALL | [0.25,0.50) | 0 | 0 | null | null | null |
| ALL | [0.50,0.75) | 0 | 0 | null | null | null |
| ALL | [0.75,1.00] | 200 | 200 | 1 | 2.22044604925e-16 | 1.55431223448e-15 |
| 0.001 | [0.00,0.25) | 0 | 0 | null | null | null |
| 0.001 | [0.25,0.50) | 0 | 0 | null | null | null |
| 0.001 | [0.50,0.75) | 0 | 0 | null | null | null |
| 0.001 | [0.75,1.00] | 50 | 50 | 1 | 6.66133814775e-16 | 1.99840144433e-15 |
| 0.01 | [0.00,0.25) | 0 | 0 | null | null | null |
| 0.01 | [0.25,0.50) | 0 | 0 | null | null | null |
| 0.01 | [0.50,0.75) | 0 | 0 | null | null | null |
| 0.01 | [0.75,1.00] | 50 | 50 | 1 | 4.4408920985e-16 | 1.82076576039e-15 |
| 1 | [0.00,0.25) | 0 | 0 | null | null | null |
| 1 | [0.25,0.50) | 0 | 0 | null | null | null |
| 1 | [0.50,0.75) | 0 | 0 | null | null | null |
| 1 | [0.75,1.00] | 50 | 50 | 1 | 0 | 0 |
| 1000 | [0.00,0.25) | 0 | 0 | null | null | null |
| 1000 | [0.25,0.50) | 0 | 0 | null | null | null |
| 1000 | [0.50,0.75) | 0 | 0 | null | null | null |
| 1000 | [0.75,1.00] | 50 | 50 | 1 | 2.22044604925e-16 | 2.22044604925e-16 |

## Corruption 전이 수치

| corruption | n | unit_transition | status_transition | reference_transition | scale_same | scale_changed | relerr_med | relerr_p95 | conf_after_med |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| duplicate | 200 | {"HIGH->HIGH": 200} | {"LOW->LOW": 200} | {"LOW->LOW": 200} | 200 | 0 | 2.22044604925e-16 | 1.55431223448e-15 | 1 |
| stale_override | 200 | {"HIGH->HIGH": 144, "HIGH->LOW": 56} | {"LOW->LOW": 200} | {"LOW->LOW": 200} | 200 | 0 | 2.22044604925e-16 | 1.57651669497e-15 | 0.833333333333 |
| suffix_removal | 200 | {"HIGH->HIGH": 200} | {"LOW->LOW": 200} | {"LOW->LOW": 200} | 200 | 0 | 2.22044604925e-16 | 1.55431223448e-15 | 1 |
| single_outlier | 200 | {"HIGH->HIGH": 200} | {"LOW->LOW": 200} | {"LOW->LOW": 200} | 200 | 0 | 2.22044604925e-16 | 1.55431223448e-15 | 0.857142857143 |

## Single-outlier 티켓 수치

| metric | value |
| --- | --- |
| scene_count | 200 |
| v1_status_transitions | {"LOW->HIGH": 26, "LOW->LOW": 174} |
| v2_status_transitions | {"LOW->LOW": 200} |
| v1_unit_status_transitions | {"LOW->LOW": 200} |
| v2_unit_status_transitions | {"HIGH->HIGH": 200} |
| v2_reference_status_transitions | {"LOW->LOW": 200} |
| v1_low_to_high_status_count | 26 |
| v2_low_to_high_status_count | 0 |
| v2_confidence_score_increased_count | 0 |
| v2_confidence_score_unchanged_count | 0 |
| v2_confidence_score_decreased_count | 200 |
| v2_status_rank_increased_count | 0 |
| v2_unit_status_rank_increased_count | 0 |
| v2_reference_status_rank_increased_count | 0 |
| v2_confidence_or_status_increased_count | 0 |
| v2_scale_estimate_unchanged_count | 200 |
| v2_scale_estimate_changed_count | 0 |

## Pair-label permutation digest 수치

| metric | value |
| --- | --- |
| scene_count | 200 |
| pair_label_changed_scene_count | 196 |
| matching_anchor_artifact_scene_count | 200 |
| mismatching_anchor_artifact_scene_count | 0 |
| anchor_artifact_match_rate | 1 |
| global_anchor_artifact_digest_before | e6f40eb082c5ee3d3ad1acc93f304ef2b118d806a2ce1277ab1dec5d0fea6f57 |
| global_anchor_artifact_digest_after | e6f40eb082c5ee3d3ad1acc93f304ef2b118d806a2ce1277ab1dec5d0fea6f57 |

## C1v2 aggregate 수치 전문

```json
{
  "by_scale": {
    "0.001": {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 50,
        "max": 1.0,
        "mean": 0.9999999999999761,
        "median": 0.9999999999999818,
        "min": 0.9999999999999454,
        "p05": 0.9999999999999636,
        "p25": 0.9999999999999636,
        "p75": 0.9999999999999818,
        "p95": 0.9999999999999918
      },
      "e_s": {
        "count": 50,
        "max": 1.9984014443252837e-15,
        "mean": 7.727152251391092e-16,
        "median": 6.661338147750937e-16,
        "min": 2.2204460492503136e-16,
        "p05": 2.2204460492503136e-16,
        "p25": 2.2204460492503136e-16,
        "p75": 1.1102230246251571e-15,
        "p95": 1.9984014443252837e-15
      },
      "estimate_count": 50,
      "estimate_coverage": 1.0,
      "high_accuracy_within_5pct": 1.0,
      "high_coverage": 1.0,
      "high_relative_error": {
        "count": 50,
        "max": 1.9984014443252818e-15,
        "mean": 7.727152251391089e-16,
        "median": 6.661338147750939e-16,
        "min": 2.220446049250313e-16,
        "p05": 2.220446049250313e-16,
        "p25": 2.220446049250313e-16,
        "p75": 1.1102230246251565e-15,
        "p95": 1.9984014443252818e-15
      },
      "high_scene_count": 50,
      "relative_error": {
        "count": 50,
        "max": 1.9984014443252818e-15,
        "mean": 7.727152251391089e-16,
        "median": 6.661338147750939e-16,
        "min": 2.220446049250313e-16,
        "p05": 2.220446049250313e-16,
        "p25": 2.220446049250313e-16,
        "p75": 1.1102230246251565e-15,
        "p95": 1.9984014443252818e-15
      },
      "scene_count": 50,
      "unit_status_counts": {
        "HIGH": 50
      }
    },
    "0.01": {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 50,
        "max": 1.0,
        "mean": 0.9999999999999774,
        "median": 0.9999999999999818,
        "min": 0.9999999999999272,
        "p05": 0.9999999999999636,
        "p25": 0.9999999999999636,
        "p75": 0.9999999999999818,
        "p95": 1.0
      },
      "e_s": {
        "count": 50,
        "max": 3.108624468950443e-15,
        "mean": 6.927791673660978e-16,
        "median": 4.440892098500627e-16,
        "min": 4.440892098500625e-16,
        "p05": 4.440892098500625e-16,
        "p25": 4.440892098500625e-16,
        "p75": 4.440892098500627e-16,
        "p95": 1.8207657603852534e-15
      },
      "estimate_count": 50,
      "estimate_coverage": 1.0,
      "high_accuracy_within_5pct": 1.0,
      "high_coverage": 1.0,
      "high_relative_error": {
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
      "high_scene_count": 50,
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
        "HIGH": 50
      }
    },
    "1": {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 50,
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
      "high_coverage": 1.0,
      "high_relative_error": {
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
      "high_scene_count": 50,
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
        "HIGH": 50
      }
    },
    "1000": {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 50,
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
      "high_coverage": 1.0,
      "high_relative_error": {
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
      "high_scene_count": 50,
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
        "HIGH": 50
      }
    }
  },
  "confidence_grade_bins": {
    "HIGH": {
      "accuracy_within_5pct": 1.0,
      "confidence_score": {
        "count": 200,
        "max": 1.0,
        "mean": 0.9999999999999885,
        "median": 1.0,
        "min": 0.9999999999999272,
        "p05": 0.9999999999999636,
        "p25": 0.9999999999999818,
        "p75": 1.0,
        "p95": 1.0
      },
      "e_s": {
        "count": 200,
        "max": 3.108624468950443e-15,
        "mean": 4.2188474935755956e-16,
        "median": 2.220446049250313e-16,
        "min": 0.0,
        "p05": 0.0,
        "p25": 1.6653345369377346e-16,
        "p75": 4.440892098500627e-16,
        "p95": 1.554312234475218e-15
      },
      "estimate_count": 200,
      "estimate_coverage": 1.0,
      "relative_error": {
        "count": 200,
        "max": 3.1086244689504383e-15,
        "mean": 4.2188474935755947e-16,
        "median": 2.220446049250313e-16,
        "min": 0.0,
        "p05": 0.0,
        "p25": 1.6653345369377348e-16,
        "p75": 4.440892098500626e-16,
        "p95": 1.5543122344752192e-15
      },
      "scene_count": 200
    },
    "LOW": {
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
          "mean": 0.9999999999999885,
          "median": 1.0,
          "min": 0.9999999999999272,
          "p05": 0.9999999999999636,
          "p25": 0.9999999999999818,
          "p75": 1.0,
          "p95": 1.0
        },
        "e_s_after": {
          "count": 200,
          "max": 3.108624468950443e-15,
          "mean": 4.2188474935755956e-16,
          "median": 2.220446049250313e-16,
          "min": 0.0,
          "p05": 0.0,
          "p25": 1.6653345369377346e-16,
          "p75": 4.440892098500627e-16,
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
          "mean": 4.2188474935755947e-16,
          "median": 2.220446049250313e-16,
          "min": 0.0,
          "p05": 0.0,
          "p25": 1.6653345369377348e-16,
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
          "HIGH->HIGH": 200
        }
      },
      "single_outlier": {
        "confidence_score_after": {
          "count": 200,
          "max": 0.8888888888888888,
          "mean": 0.8634920634920534,
          "median": 0.8571428571428571,
          "min": 0.8333333333333031,
          "p05": 0.8333333333333031,
          "p25": 0.8333333333333334,
          "p75": 0.8888888888888726,
          "p95": 0.8888888888888888
        },
        "e_s_after": {
          "count": 200,
          "max": 3.108624468950443e-15,
          "mean": 4.2188474935755956e-16,
          "median": 2.220446049250313e-16,
          "min": 0.0,
          "p05": 0.0,
          "p25": 1.6653345369377346e-16,
          "p75": 4.440892098500627e-16,
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
          "mean": 4.2188474935755947e-16,
          "median": 2.220446049250313e-16,
          "min": 0.0,
          "p05": 0.0,
          "p25": 1.6653345369377348e-16,
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
          "HIGH->HIGH": 200
        }
      },
      "stale_override": {
        "confidence_score_after": {
          "count": 200,
          "max": 0.875,
          "mean": 0.796342857142848,
          "median": 0.8333333333333334,
          "min": 0.6399999999999768,
          "p05": 0.6399999999999885,
          "p25": 0.6400000000000001,
          "p75": 0.8749999999999681,
          "p95": 0.875
        },
        "e_s_after": {
          "count": 200,
          "max": 3.108624468950443e-15,
          "mean": 4.490852134608759e-16,
          "median": 2.2204460492503136e-16,
          "min": 0.0,
          "p05": 0.0,
          "p25": 2.2204460492503128e-16,
          "p75": 4.440892098500627e-16,
          "p95": 1.5765166949677137e-15
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
          "mean": 4.490852134608758e-16,
          "median": 2.220446049250313e-16,
          "min": 0.0,
          "p05": 0.0,
          "p25": 2.220446049250313e-16,
          "p75": 4.440892098500626e-16,
          "p95": 1.5765166949677147e-15
        },
        "scale_estimate_changed_count": 0,
        "scale_estimate_unchanged_count": 200,
        "scene_count": 200,
        "status_transitions": {
          "LOW->LOW": 200
        },
        "unit_status_transitions": {
          "HIGH->HIGH": 144,
          "HIGH->LOW": 56
        }
      },
      "suffix_removal": {
        "confidence_score_after": {
          "count": 200,
          "max": 1.0,
          "mean": 0.9999999999999885,
          "median": 1.0,
          "min": 0.9999999999999272,
          "p05": 0.9999999999999636,
          "p25": 0.9999999999999818,
          "p75": 1.0,
          "p95": 1.0
        },
        "e_s_after": {
          "count": 200,
          "max": 3.108624468950443e-15,
          "mean": 4.2188474935755956e-16,
          "median": 2.220446049250313e-16,
          "min": 0.0,
          "p05": 0.0,
          "p25": 1.6653345369377346e-16,
          "p75": 4.440892098500627e-16,
          "p95": 1.554312234475218e-15
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
          "mean": 4.2188474935755947e-16,
          "median": 2.220446049250313e-16,
          "min": 0.0,
          "p05": 0.0,
          "p25": 1.6653345369377348e-16,
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
          "HIGH->HIGH": 200
        }
      }
    },
    "hash_assigned_primary": {
      "duplicate": {
        "base_scene_count": 11,
        "scene_count": 44,
        "unit_status_transitions": {
          "HIGH->HIGH": 44
        }
      },
      "single_outlier": {
        "base_scene_count": 12,
        "scene_count": 48,
        "unit_status_transitions": {
          "HIGH->HIGH": 48
        }
      },
      "stale_override": {
        "base_scene_count": 14,
        "scene_count": 56,
        "unit_status_transitions": {
          "HIGH->HIGH": 36,
          "HIGH->LOW": 20
        }
      },
      "suffix_removal": {
        "base_scene_count": 13,
        "scene_count": 52,
        "unit_status_transitions": {
          "HIGH->HIGH": 52
        }
      }
    }
  },
  "overall": {
    "accuracy_within_5pct": 1.0,
    "confidence_score": {
      "count": 200,
      "max": 1.0,
      "mean": 0.9999999999999885,
      "median": 1.0,
      "min": 0.9999999999999272,
      "p05": 0.9999999999999636,
      "p25": 0.9999999999999818,
      "p75": 1.0,
      "p95": 1.0
    },
    "e_s": {
      "count": 200,
      "max": 3.108624468950443e-15,
      "mean": 4.2188474935755956e-16,
      "median": 2.220446049250313e-16,
      "min": 0.0,
      "p05": 0.0,
      "p25": 1.6653345369377346e-16,
      "p75": 4.440892098500627e-16,
      "p95": 1.554312234475218e-15
    },
    "estimate_count": 200,
    "estimate_coverage": 1.0,
    "high_accuracy_within_5pct": 1.0,
    "high_coverage": 1.0,
    "high_e_s": {
      "count": 200,
      "max": 3.108624468950443e-15,
      "mean": 4.2188474935755956e-16,
      "median": 2.220446049250313e-16,
      "min": 0.0,
      "p05": 0.0,
      "p25": 1.6653345369377346e-16,
      "p75": 4.440892098500627e-16,
      "p95": 1.554312234475218e-15
    },
    "high_relative_error": {
      "count": 200,
      "max": 3.1086244689504383e-15,
      "mean": 4.2188474935755947e-16,
      "median": 2.220446049250313e-16,
      "min": 0.0,
      "p05": 0.0,
      "p25": 1.6653345369377348e-16,
      "p75": 4.440892098500626e-16,
      "p95": 1.5543122344752192e-15
    },
    "high_scene_count": 200,
    "relative_error": {
      "count": 200,
      "max": 3.1086244689504383e-15,
      "mean": 4.2188474935755947e-16,
      "median": 2.220446049250313e-16,
      "min": 0.0,
      "p05": 0.0,
      "p25": 1.6653345369377348e-16,
      "p75": 4.440892098500626e-16,
      "p95": 1.5543122344752192e-15
    },
    "scene_count": 200,
    "status_counts": {
      "LOW": 200
    },
    "unit_status_counts": {
      "HIGH": 200
    }
  },
  "pair_label_permutation": {
    "anchor_artifact_match_rate": 1.0,
    "global_anchor_artifact_digest_after": "e6f40eb082c5ee3d3ad1acc93f304ef2b118d806a2ce1277ab1dec5d0fea6f57",
    "global_anchor_artifact_digest_before": "e6f40eb082c5ee3d3ad1acc93f304ef2b118d806a2ce1277ab1dec5d0fea6f57",
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
        "count": 50,
        "max": 1.0,
        "mean": 0.9999999999999761,
        "median": 0.9999999999999818,
        "min": 0.9999999999999454,
        "p05": 0.9999999999999636,
        "p25": 0.9999999999999636,
        "p75": 0.9999999999999818,
        "p95": 0.9999999999999918
      },
      "e_s": {
        "count": 50,
        "max": 1.9984014443252837e-15,
        "mean": 7.727152251391092e-16,
        "median": 6.661338147750937e-16,
        "min": 2.2204460492503136e-16,
        "p05": 2.2204460492503136e-16,
        "p25": 2.2204460492503136e-16,
        "p75": 1.1102230246251571e-15,
        "p95": 1.9984014443252837e-15
      },
      "estimate_count": 50,
      "estimate_coverage": 1.0,
      "fraction_of_scale": 1.0,
      "relative_error": {
        "count": 50,
        "max": 1.9984014443252818e-15,
        "mean": 7.727152251391089e-16,
        "median": 6.661338147750939e-16,
        "min": 2.220446049250313e-16,
        "p05": 2.220446049250313e-16,
        "p25": 2.220446049250313e-16,
        "p75": 1.1102230246251565e-15,
        "p95": 1.9984014443252818e-15
      },
      "scale_kappa": 0.001,
      "scene_count": 50
    },
    {
      "accuracy_within_5pct": null,
      "confidence": "LOW",
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
        "count": 50,
        "max": 1.0,
        "mean": 0.9999999999999774,
        "median": 0.9999999999999818,
        "min": 0.9999999999999272,
        "p05": 0.9999999999999636,
        "p25": 0.9999999999999636,
        "p75": 0.9999999999999818,
        "p95": 1.0
      },
      "e_s": {
        "count": 50,
        "max": 3.108624468950443e-15,
        "mean": 6.927791673660978e-16,
        "median": 4.440892098500627e-16,
        "min": 4.440892098500625e-16,
        "p05": 4.440892098500625e-16,
        "p25": 4.440892098500625e-16,
        "p75": 4.440892098500627e-16,
        "p95": 1.8207657603852534e-15
      },
      "estimate_count": 50,
      "estimate_coverage": 1.0,
      "fraction_of_scale": 1.0,
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
      "scale_kappa": 0.01,
      "scene_count": 50
    },
    {
      "accuracy_within_5pct": null,
      "confidence": "LOW",
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
        "count": 50,
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
      "fraction_of_scale": 1.0,
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
      "scale_kappa": 1.0,
      "scene_count": 50
    },
    {
      "accuracy_within_5pct": null,
      "confidence": "LOW",
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
        "count": 50,
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
      "fraction_of_scale": 1.0,
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
      "scale_kappa": 1000.0,
      "scene_count": 50
    },
    {
      "accuracy_within_5pct": null,
      "confidence": "LOW",
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
      "lower": 0.25,
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
        "count": 200,
        "max": 1.0,
        "mean": 0.9999999999999885,
        "median": 1.0,
        "min": 0.9999999999999272,
        "p05": 0.9999999999999636,
        "p25": 0.9999999999999818,
        "p75": 1.0,
        "p95": 1.0
      },
      "e_s": {
        "count": 200,
        "max": 3.108624468950443e-15,
        "mean": 4.2188474935755956e-16,
        "median": 2.220446049250313e-16,
        "min": 0.0,
        "p05": 0.0,
        "p25": 1.6653345369377346e-16,
        "p75": 4.440892098500627e-16,
        "p95": 1.554312234475218e-15
      },
      "estimate_count": 200,
      "estimate_coverage": 1.0,
      "lower": 0.75,
      "relative_error": {
        "count": 200,
        "max": 3.1086244689504383e-15,
        "mean": 4.2188474935755947e-16,
        "median": 2.220446049250313e-16,
        "min": 0.0,
        "p05": 0.0,
        "p25": 1.6653345369377348e-16,
        "p75": 4.440892098500626e-16,
        "p95": 1.5543122344752192e-15
      },
      "scale_kappa": "ALL",
      "scene_count": 200,
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
      "lower": 0.25,
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
        "count": 50,
        "max": 1.0,
        "mean": 0.9999999999999761,
        "median": 0.9999999999999818,
        "min": 0.9999999999999454,
        "p05": 0.9999999999999636,
        "p25": 0.9999999999999636,
        "p75": 0.9999999999999818,
        "p95": 0.9999999999999918
      },
      "e_s": {
        "count": 50,
        "max": 1.9984014443252837e-15,
        "mean": 7.727152251391092e-16,
        "median": 6.661338147750937e-16,
        "min": 2.2204460492503136e-16,
        "p05": 2.2204460492503136e-16,
        "p25": 2.2204460492503136e-16,
        "p75": 1.1102230246251571e-15,
        "p95": 1.9984014443252837e-15
      },
      "estimate_count": 50,
      "estimate_coverage": 1.0,
      "lower": 0.75,
      "relative_error": {
        "count": 50,
        "max": 1.9984014443252818e-15,
        "mean": 7.727152251391089e-16,
        "median": 6.661338147750939e-16,
        "min": 2.220446049250313e-16,
        "p05": 2.220446049250313e-16,
        "p25": 2.220446049250313e-16,
        "p75": 1.1102230246251565e-15,
        "p95": 1.9984014443252818e-15
      },
      "scale_kappa": "0.001",
      "scene_count": 50,
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
      "lower": 0.25,
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
        "count": 50,
        "max": 1.0,
        "mean": 0.9999999999999774,
        "median": 0.9999999999999818,
        "min": 0.9999999999999272,
        "p05": 0.9999999999999636,
        "p25": 0.9999999999999636,
        "p75": 0.9999999999999818,
        "p95": 1.0
      },
      "e_s": {
        "count": 50,
        "max": 3.108624468950443e-15,
        "mean": 6.927791673660978e-16,
        "median": 4.440892098500627e-16,
        "min": 4.440892098500625e-16,
        "p05": 4.440892098500625e-16,
        "p25": 4.440892098500625e-16,
        "p75": 4.440892098500627e-16,
        "p95": 1.8207657603852534e-15
      },
      "estimate_count": 50,
      "estimate_coverage": 1.0,
      "lower": 0.75,
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
      "scale_kappa": "0.01",
      "scene_count": 50,
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
      "lower": 0.25,
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
        "count": 50,
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
      "lower": 0.75,
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
      "scale_kappa": "1",
      "scene_count": 50,
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
      "lower": 0.25,
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
        "count": 50,
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
      "lower": 0.75,
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
      "scale_kappa": "1000",
      "scene_count": 50,
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
| loop_l1.py | GENERATED | 60409 | 61eafb479c714a12e2ddec1e67d164f7bf3f2eb72d44d9881d102e99c673e24f |
| scenes_v2 | GENERATED | 14668510 | 0ccedfcd7c7ef91a77ab924c7ed3dd88e6927b54f551c92137d52251b6f30b42 |
| c0v2_numbers.json | GENERATED | 15964 | 9f3cef1a30ec82596ef0a8d336d5a7aedc6c7bffa8b19b7f61511e374377ae24 |
| c1v2_results.json | GENERATED | 1386090 | a94400b9b2077913d193d70cf4fa223b882f48a8b6e49766ac15e74a7cdafb8b |
| evidence.xlsx | GENERATED | 18491 | be0864dead9a1ce8c70cc2043cee10dd6bfd4e2dc0557703def39c3c88b06c16 |

## 미해결

- 서로 다른 geometry span을 사용한 reference model의 v2 status 분포는 `{"LOW": 200}`이고 primary unit_status 분포는 `{"HIGH": 200}`다.
- evidence workbook은 openpyxl 구조 검증 11개 required sheet, formula error 0개로 기록했다. artifact-tool dependency loader가 제공되지 않아 raster render count는 0이다.
- 원본 CAD 및 test split 접근 수는 0이며, repository/v1 source manifest mismatch 수는 0이다.
- 목표·게이트·이론 판정은 오케스트레이터 비교 범위로 남겼다.

LOOP_COMPLETE: L1
