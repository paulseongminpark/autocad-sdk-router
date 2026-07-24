# Feyerabend C0 실행 보고서

## 설계

- canonical base scene 50개를 만들고 κ={0.001, 0.01, 1.0, 1000.0}로 복제해 JSON IR 200개를 생성했다.
- seed는 각 j에 대해 SHA-256(`feyerabend_P2:`+j)의 첫 32 bit를 big-endian uint32로 해석했다. 별도 RNG나 random search는 사용하지 않았다.
- 모든 scale copy는 같은 source handle, unordered truth pair, block/anchor topology를 보존한다. 좌표와 annotation geometry는 κ배이고 표시 치수는 canonical physical 값으로 유지되어 truth unit scale은 1/κ다.
- truth는 실제 scene entity의 두 source handle을 가리킨다. zero-wall sentinel만 정의상 truth pair가 0개이며, 그 외 positive scene은 모두 1개 이상이다.
- ARC/SPLINE/HATCH, LWPOLYLINE 분절, nested INSERT의 누적 비균일 transform, 비평행 조각, door/window/dimension형 hard negative를 IR에 명시했다.
- gen2.py는 read-only import/call로 사용했고, fidelity_stats.py의 TV·histogram KS 정의를 κ=1 scene에 그대로 적용했다. 원본 CAD와 test split은 열지 않았다.
- coverage_numbers.json과 아래 수치에는 KS/TV threshold 또는 C0 gate 판정을 넣지 않았다.

## Selftest 전문

```text
=== feyerabend_c0 selftest ===
python=3.12.10 numpy=1.26.4 ezdxf=1.4.3
[PASS] seed_rule: j=7 seed=1680878578 sha256_prefix=1680878578
[PASS] same_j_same_sha: j=7 sha256=7397efad1a9161cfce3bb74c7ac03e1ad6634a8b79ef144d13057319326b12b6
[PASS] same_j_four_scale_topology: kappas=[0.001, 0.01, 1.0, 1000.0] unique_topology_sha=1
[PASS] same_j_four_scale_normalized_geometry: unique_normalized_geometry_sha=1
[PASS] truth_validator_positive_cases: scene_count=4 error_count=0
[PASS] truth_validator_negative_case_honest_fail: validator_status=FAIL error_count=4
[PASS] permitted_gen2_synthetic_fixture: wall_records=2 entity_types=['ARC', 'CIRCLE', 'HATCH', 'LINE', 'LWPOLYLINE', 'MTEXT', 'SPLINE', 'TEXT']
SELFTEST_RESULT: PASS
```

## 커버리지·정합 수치 전문

```json
{
  "build_numbers": {
    "entity_profile_filler_count": 5100,
    "entity_profile_target_total": 8000,
    "fidelity_gap_sample_target": 1200
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
      "scene_count": 25,
      "scene_ratio": 0.5
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
      "scene_count": 25,
      "scene_ratio": 0.5
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
  "schema": "ariadne.e2.feyerabend_c0.coverage_numbers.v1",
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
  }
}
```

## 미해결

- zero-wall sentinel과 ‘각 scene truth pair ≥1’ 문구는 동시에 문자 그대로 만족할 수 없다. dossier의 ‘positive scene’ 조건을 따라 zero-wall 한 scene만 명시적 예외로 두었다.
- entity TV와 thickness-histogram KS는 허용된 aggregate reference 통계를 직접 profile한 수치다. 낮은 거리는 분포 정합을 뜻하지만 CAD 의미 현실성이나 후속 C1/C2 판정을 대신하지 않는다.
- nested transform과 nonparallel fragment는 synthetic IR 계약에서 검증했다. 원본 CAD에 대한 외적 검증은 packet의 접근 금지 범위 때문에 수행하지 않았다.
- 실행 경계 메모: packet을 처음 읽은 진단 명령에 read-only `git rev-parse` 점검이 함께 들어갔고 `not a git repository`로 종료했다. Git 상태나 파일은 바뀌지 않았으며 이후 git 명령은 실행하지 않았다.
- 이 셀은 C0 factory와 numeric qualification evidence만 산출한다. 봉인된 prereg threshold의 판정과 P2 이론 판별은 출력하지 않았다.

CELL_COMPLETE: feyerabend_c0
