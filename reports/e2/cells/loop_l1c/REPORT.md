# E2 Loop L1c — estimator repair and cohort replay

PREREG_JSON_SHA256: `30f6d0f7db9c5a9531183ec317936d4c5d3dda98139299d8ff43aeee68183fa8`
PREREG_CANONICAL_SHA256: `a6c4a6d7a86b59b054df939c44e1744d958772381bc73d852f90c297d7a1989d`
EVIDENCE_XLSX_PRE_REPAIR_SHA256: `3013a276aa1c1dd0a4f8869cb4a83eff8ce31e980f49a7a7690cdda2b2f87041`
EVIDENCE_XLSX_FINAL_SHA256: `70f3001fc4a23948fd83aaa52809df04c468ea41d5c635ea0beaa0a50705fbfe`

## 이중 봉인 기록

- prereg.json과 evidence.xlsx PREREG 시트 내용 일치: 1
- 수리 코드 생성 전 두 파일 생성: 1
- PREREG 시트 크기: 47 rows × 6 columns
- 봉인 수치: scale별 HIGH coverage minimum 0.60; HIGH accuracy minimum 0.95; perturbation confidence/status/unit_status upward count 0.
- 개선 크레딧: 0.

## 수리 설계

- 도시에 2.3(194–229행)의 ratio log-space 최대 합의와 reference confidence 공식을 유지했다.
- 도시에 2.4(231–247행)의 reference span 및 annotation-scale 제외 규칙을 유지했다.
- 신규 구조 가드: 유효 ratio를 가진 DIM/TEXT anchor는 선택된 ratio mode의 inlier일 때만 reference 합의의 n_independent 및 spatial-bin support에 참여한다.
- ratio-space outlier는 span-space inlier여도 `ratio_space_outlier_guard`로 격리한다. GRID 및 ratio가 없는 reference-only anchor 경로는 유지한다.
- 원본 feyerabend_c1.py 수정 수: 0 files.

## selftest 수치

| scope | count | passed | failed |
| --- | --- | --- | --- |
| 기존 L1b 17종 | 17 | 17 | 0 |
| live counterexample regression | 1 | 1 | 0 |
| seeded random perturbations | 300 | 300 | 0 |

### live 반례 회귀 전문

| estimator | phase | confidence | status | unit_status | reference_status | ref_conf | ref_n | ref_bins | guarded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| original | before | 0.6 | LOW | LOW | LOW | 0.6 | 3 | 3 | 0 |
| original | after | 0.45 | HIGH | LOW | HIGH | 0.8 | 4 | 4 | 0 |
| C1v4 | before | 0.6 | LOW | LOW | LOW | 0.6 | 3 | 3 | 0 |
| C1v4 | after | 0.45 | LOW | LOW | LOW | 0.6 | 3 | 3 | 1 |

- original status upward count: 1
- C1v4 upward counts: {"confidence_score": 0, "reference_status": 0, "status": 0, "unit_status": 0}

### 300종 고정 시드 단조성

- seed: 20260719
- family counts: `{"exact_duplicate": 48, "geometry_ratio_break": 42, "outlier_clone": 57, "reference_support_drop": 46, "stale_override": 50, "suffix_removal": 57}`
- upward counts: `{"confidence_score": 0, "reference_status": 0, "status": 0, "unit_status": 0}`
- cases digest: `5dabc8d8bb4ae60c265ec1c5a29f34675f45dcc31c6cbd2ac1dd386add7e29bf`

## 코호트 replay 델타 전문

### l1b_200

| metric | before | after | delta |
| --- | --- | --- | --- |
| scene_count | 200 | 200 | 0 |
| HIGH coverage | 0.8 | 0.8 | 0 |
| HIGH accuracy within 5% | 1 | 1 | 0 |
| relative error median | 2.22044604925e-16 | 2.22044604925e-16 | 0 |
| relative error max | 3.10862446895e-15 | 3.10862446895e-15 | 0 |
| unperturbed changed scenes | 0 | 0 | 0 |

Per-scale:

| scale | coverage before | coverage after | accuracy before | accuracy after | relerr med before | relerr med after | relerr max before | relerr max after |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.001 | 0.8 | 0.8 | 1 | 1 | 2.22044604925e-16 | 2.22044604925e-16 | 1.99840144433e-15 | 1.99840144433e-15 |
| 0.01 | 0.8 | 0.8 | 1 | 1 | 4.4408920985e-16 | 4.4408920985e-16 | 3.10862446895e-15 | 3.10862446895e-15 |
| 1 | 0.8 | 0.8 | 1 | 1 | 0 | 0 | 0 | 0 |
| 1000 | 0.8 | 0.8 | 1 | 1 | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 |

Corruption upward counts:

| corruption | conf before | conf after | status before | status after | unit before | unit after | ref before | ref after | status-after changed scenes | ref-after changed scenes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| duplicate | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| stale_override | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| suffix_removal | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| single_outlier | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

- common unperturbed numeric fields: 20
- common numeric digest equal: 1
- 재현 기술: 휘발 필드(runtime·타임스탬프) 제외 수치 전 필드 동일 (공통 정상 평가 수치 필드 범위).

### c1_v1_200

| metric | before | after | delta |
| --- | --- | --- | --- |
| scene_count | 200 | 200 | 0 |
| HIGH coverage | 0 | 0 | 0 |
| HIGH accuracy within 5% | null | null | null |
| relative error median | 2.22044604925e-16 | 2.22044604925e-16 | 0 |
| relative error max | 4.4408920985e-16 | 4.4408920985e-16 | 0 |
| unperturbed changed scenes | 0 | 0 | 0 |

Per-scale:

| scale | coverage before | coverage after | accuracy before | accuracy after | relerr med before | relerr med after | relerr max before | relerr max after |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.001 | 0 | 0 | null | null | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 |
| 0.01 | 0 | 0 | null | null | 4.4408920985e-16 | 4.4408920985e-16 | 4.4408920985e-16 | 4.4408920985e-16 |
| 1 | 0 | 0 | null | null | 0 | 0 | 0 | 0 |
| 1000 | 0 | 0 | null | null | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 |

Corruption upward counts:

| corruption | conf before | conf after | status before | status after | unit before | unit after | ref before | ref after | status-after changed scenes | ref-after changed scenes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| duplicate | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| stale_override | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| suffix_removal | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| single_outlier | 0 | 0 | 26 | 0 | 0 | 0 | 26 | 0 | 26 | 26 |

- common unperturbed numeric fields: 20
- common numeric digest equal: 1
- 재현 기술: 휘발 필드(runtime·타임스탬프) 제외 수치 전 필드 동일 (공통 정상 평가 수치 필드 범위).

## 원본 무수정 및 산출물 SHA

- source manifest mismatch count: 0
- source manifest before digest: `65a16f6f0881810e6f2e1586d099d241418e11ea94ae16a8cebeb88d9563346c`
- source manifest after digest: `65a16f6f0881810e6f2e1586d099d241418e11ea94ae16a8cebeb88d9563346c`
- c1v4_results.json: `53c7c45325d103ff4950af2d5978e3c63ca6a7a6836cc11d874387580cfa4988`
- evidence.xlsx: `70f3001fc4a23948fd83aaa52809df04c468ea41d5c635ea0beaa0a50705fbfe`
- feyerabend_c1_v2.py: `5f6f2eee4810ad59863ce1c3e6b206d0a9d1818c0c0a32684194820b1aa73a0f`
- loop_l1c.py: `f92b7f272887ae3939aaa538ea712b982942e160b8b72beba85cb22037d57876`
- prereg.json: `30f6d0f7db9c5a9531183ec317936d4c5d3dda98139299d8ff43aeee68183fa8`
- replay_delta.json: `038791dadda65d749860765c7d21f5f49741af60f13e42207c811fbf556754a8`

## 미해결

- ratio 신호가 없는 GRID/reference-only anchor가 교란인지 진짜 증거인지 단일 관측만으로 식별하는 문제는 남는다.
- 300종 속성 시험은 두 200-IR 코호트와 여섯 교란 생성 family, 고정 seed 범위의 전수 결과다. 가능한 모든 입력 변형에 대한 형식 증명은 아니다.
- 이 보고서는 수치와 변화량만 기록하며 평가 게이트 판정을 출력하지 않는다.

LOOP_COMPLETE: L1c
