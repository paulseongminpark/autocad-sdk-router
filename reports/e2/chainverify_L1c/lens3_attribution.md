# lens3 — 26→0 귀속 검증 (사슬 검증단 L1c, 2차 함대)

- 좌석: lens3 (26→0 귀속 시야)
- 검증 대상: 오케스트레이터 주장 ② — "C1 원본 코호트에서 그 결함이 낳던 역전이 26건이 replay에서 0건이 됐으며", 그리고 그 소멸의 원인이 정확히 `ratio_space_outlier_guard`인지.
- 방법: 모든 기존 산출물 READ-ONLY. 재계산·변형 실행은 전부 `D:\runs\e2_program\chainverify_L1c\lens3_work\` 안에서 수행 (스크립트 `fn_diff.py`·`verify_lens3.py`, 산출 `out\*.json`·`out\fn_diff.txt`, 변형 모듈 `feyerabend_c1_v2_guardoff.py`). git 미사용, 서브에이전트 미사용, CAD·test 표면 미접근. 실행 환경 Python 3.12.10 — L1c 저장 실행의 기록(`c1v4_results.json` → `runtime.python` = 3.12.10)과 동일.

여기서 "역전(upward)"의 정의는 L1c와 동일 공식을 썼다(loop_l1c.py:425–443 `monotonic_counts`): 한 추정기 실행 안에서 교란 전(before) 대비 교란 후(after)에 status류가 NONE<LOW<HIGH 서열로 상승하거나 confidence_score가 1e-15 초과로 상승하는 장면 수.

## 0. 사슬 무결성 스팟체크 (전 좌석 공통 항목)

전부 일치. 근거: `lens3_work\out\integrity.json`.

| 대조 항목 | 결과 |
| --- | --- |
| repo 원본 `tools\e2\cells\feyerabend_c1.py` vs 아티팩트 사본 `cells\feyerabend_c1\feyerabend_c1.py` | **bytes 동일** |
| `feyerabend_c1_v2.py` sha256 `5f6f2eee…` | c1v4_results.json `estimator.sha256`·REPORT.md 126행 기재값과 일치 |
| 원본 추정기 sha256 | c1v4_results.json `estimator.original_sha256`과 일치 |
| baseline `feyerabend_c1\results.json` sha256 | c1v4_results.json `inputs.v1_baseline.sha256`과 일치 |
| `c1v4_results.json` sha256 `53c7c453…` / `replay_delta.json` `038791da…` | REPORT.md 124·129행 기재값과 일치 |
| 장면 디렉토리 `feyerabend_c0\scenes` (200파일) digest 재계산 | c1v4_results.json `inputs.v1_scene_dir.digest`와 일치 |
| baseline 자체 입력 manifest (`results.json` → `inputs.manifest_before`, per-file sha256 200건) | 현재 장면 파일 재해싱과 (name, sha256) 집합 **200/200 일치**, `manifest_mismatch_count=0` |

즉 원본 C1 실행(2026-07 이전 저장분), L1c의 v4 replay, 그리고 본 검증의 재실행 3종은 전부 **byte-동일한 200개 장면 입력**을 소비했고, L1c는 기존 산출물·소스를 건드리지 않았다.

## 1. 코드 차이 전수 조사 — "다른 코드 차이"의 목록화

v2는 원본 모듈을 read-only로 동적 import한 뒤(feyerabend_c1_v2.py:50) 헬퍼·상수 43종(`apply_corruption`·`prepare_anchors`·`maximum_consensus`·`confidence_from_consensus` 등)을 **원본 함수 객체 그대로** 재수출한다(53–98행). 런타임 동일성 검사: 43종 전부 `getattr(V2, name) is getattr(V2.ORIGINAL, name)` == True (`out\rerun_v2.json` → `reexport_identity_all_43: true`). 따라서 **교란 생성 코드는 양쪽 실행에서 문자 그대로 같은 코드**다.

AST 함수 단위 diff (`out\fn_diff.txt`) 결과, v2가 새로 정의한 것 전부:

| 함수 | 차이 | 상태값(status·confidence) 영향 |
| --- | --- | --- |
| `fit_anchor_model` | **가드 분기 추가** (v2 168–197행: ratio 보유 DIM/TEXT가 선택된 ratio mode inlier가 아니면 reference 후보에서 제외, 사유 `ratio_space_outlier_guard`) + provenance `reference_guard` 기록(276–284행) + docstring·줄바꿈 | **있음 — 유일한 행동 차이** |
| `_status` | `ORIGINAL._status` 위임 (원문 로직 동일) | 없음 |
| `anchor_artifact_from_scene` | 스키마 라벨 v1→v2 (digest 문자열에만 반영) | 없음 |
| `evaluate_scene` | 관측 필드 6종(reference_confidence/n_independent/n_spatial_bins before·after)+`reference_guarded_rejection_count` 추가, `_input_file` 접근 방식, 줄바꿈 | 없음 (판정에 쓰는 before/after 필드 계산식 동일) |
| `run_selftests`·`run_legacy_selftests`·`counterexample_regression`·`monotonicity_property_test`·`randomized_corruption`·`_ratio_indices`·`_model_snapshot`·`_load_module`·`main` | selftest 하니스 계열 | 없음 (평가 경로 아님) |

정적 결론: 평가 결과에 영향을 줄 수 있는 코드 차이는 가드 분기 하나다. 이 정적 결론을 아래 3절의 가드-무력화 실측으로 재확인했다.

## 2. 26건의 실재와 소멸 — 저장 산출물 추출 + 독립 재실행

### 2.1 저장 산출물에서의 추출 (`out\stored_extract.json`)

- baseline(`cells\feyerabend_c1\results.json`, 원본 추정기 실행 저장분) single_outlier 역전: **status 26 · reference_status 26 · confidence 0 · unit_status 0**. status 역전 26건과 reference 역전 26건은 **동일한 장면 집합**(이하 집합 A). REPORT.md 113행의 표와 일치.
- c1v4(`loop_l1c\c1v4_results.json` → `v1_replay.scenes`) single_outlier 역전: **전 필드 0**.
- 두 저장 실행 사이에 single_outlier의 교란 후 값이 달라진 장면: `status_after` 26건 = `reference_status_after` 26건 = **정확히 집합 A**; `confidence_score_after`·`unit_status_after` 변화 **0건**. replay_delta.json의 `changed_after_field_scene_counts` 기재값과 일치.
- 비교란(unperturbed) 평가에서 가드 발화 장면: **0/200** (c1v4 각 scene의 `anchor_model.provenance.reference_guard.guarded_rejection_count` 전수 확인) — 정상 수치 불변(REPORT `changed_unperturbed_scene_count=0`)과 정합.

### 2.2 독립 재실행 (본 좌석, 저장분 신뢰하지 않고 라이브 재계산)

세 실행 모두 동일한 200장면(`feyerabend_c0\scenes`)에 대해 `evaluate_scene`를 전수 수행:

| 실행 | 모듈 | single_outlier 역전 (conf/status/unit/ref) | 저장분과의 대조 |
| --- | --- | --- | --- |
| C1 원본 재실행 | `cells\feyerabend_c1\feyerabend_c1.py` (READ-ONLY import) | 0 / **26** / 0 / **26** — status·ref ids 모두 **집합 A와 일치** | 200개 row 전부 stored baseline과 canonical JSON sha256 **불일치 0** (`out\rerun_original.json`) |
| C1v4 재실행 | `loop_l1c\feyerabend_c1_v2.py` (READ-ONLY import) | 0 / **0** / 0 / **0** | 200개 row 전부 stored c1v4 `v1_replay.scenes`와 canonical sha256 **불일치 0** (`out\rerun_v2.json`) |
| 가드-무력화 v2 | `lens3_work\feyerabend_c1_v2_guardoff.py` (아래 3절) | 0 / **26** / 0 / **26** — ids **집합 A와 일치** | 3절 참조 |

①의 판정: 26건은 저장 파일 속 숫자가 아니라 **원본 추정기를 오늘 다시 돌려도 같은 26개 장면에서 재현되는 라이브 현상**이다. ②의 판정: v2 재실행도 0건이며, L1c가 저장한 replay 산출물은 재실행과 canonical 수준까지 동일하다.

## 3. 인과 격리 — 가드만 무력화한 변형 실행

변형은 단 한 줄: v2 사본의 가드 분기 조건(원문 v2 185행)

```
if carries_ratio and str(anchor["handle"]) not in ratio_inlier_handles:
```

을 `if False and carries_ratio and …`로 치환(치환 횟수 1 확인). 그 외 모든 바이트 동일. 결과 (`out\rerun_guardoff.json`):

- 가드 발화 0건(무력화 확인, 전 장면 `reference_guarded_rejection_count=0`).
- single_outlier 역전: **status 26 · reference 26, 장면 id 목록이 집합 A와 정확히 일치** — 26건이 그대로 되돌아온다.
- 원본 baseline과의 의미 필드 전수 대조: 200장면 × (anchor_model 스칼라 17필드 + 교란 4종 × 진단 스칼라 16필드) 비교에서 **불일치 0** (v2가 추가한 신규 관측 필드·provenance·digest는 원본 스키마에 없어 비교 대상에서 제외 — canonical 동일성은 스키마 확장 때문에 정의상 불가).

즉: **v2 − 가드 ≡ 원본** (이 코호트·이 교란 4종의 전 의미 필드에서 실측 동치), **v2 + 가드 = 역전 0**. 1절의 정적 전수 조사와 합치며, 26→0의 원인은 가드 하나로 격리된다. 다른 코드 차이의 수치 기여는 0이다.

## 4. 장면 단위 기전 추적 (표본 3건, `out\trace_samples.json`)

세 장면 모두 동일 패턴 (F1 기전 — chainverify_L1b/lens2_stats.md §2 F1 — 과 합치):

| 장면 | 주입 outlier 핸들 | 가드가 격리한 핸들 | 원본 교란 후 (ref_status / ref_n) | v2 교란 후 (ref_status / ref_n) |
| --- | --- | --- | --- | --- |
| feyerabend_c0_001:k1000 | F001_ANCHOR_DIM_A_1__OUT_ac85e338 | **동일 핸들** (ratio_class=outlier) | HIGH / 4 | LOW / 3 |
| feyerabend_c0_003:k1000 | F003_ANCHOR_DIM_A_2__OUT_84d6645d | **동일 핸들** | HIGH / 4 | LOW / 3 |
| feyerabend_c0_005:k1000 | F005_ANCHOR_DIM_A_2__OUT_264779e8 | **동일 핸들** | HIGH / 4 | LOW / 3 |

기전 사슬: `apply_corruption`(feyerabend_c1.py:550–568)이 display_value×10인 복제 anchor를 주입 → ratio 공간에서는 outlier지만 span은 복제라 span 공간 inlier → 원본에서는 reference 합의의 n_independent·spatial bins가 3→4로 부양되어 점수가 0.75 문턱을 넘고 reference LOW→HIGH, `status = reference_status`(원본 440행)로 status도 HIGH → 가드는 그 outlier의 span을 reference 후보에서 격리(주입 핸들==격리 핸들)해 n=3·LOW를 유지한다. 가드-무력화 실행에서는 같은 장면이 다시 HIGH로 역전.

부가 관찰: 가드는 교란 장면 200건 전부에서 발화한다(주입 outlier는 항상 ratio-공간 outlier이므로). 그중 26건에서만 역전이 억제되고, 나머지 174건에서는 교차-비교 가능한 필드 변화가 0건(2.1의 changed 카운트)이다. 비교란 장면에서는 발화 0건. 즉 이 코호트에서 가드의 관측 가능한 효과는 정확히 "26건의 역전 억제"뿐이다.

## 5. 26건 장면 id 목록 (집합 A — 저장 baseline·원본 재실행·가드-무력화 실행 3자 일치)

k1000에서 25건 + k1에서 1건 (`feyerabend_c0_041:k1`):

```
feyerabend_c0_001:k1000  feyerabend_c0_003:k1000  feyerabend_c0_005:k1000
feyerabend_c0_007:k1000  feyerabend_c0_009:k1000  feyerabend_c0_011:k1000
feyerabend_c0_013:k1000  feyerabend_c0_015:k1000  feyerabend_c0_017:k1000
feyerabend_c0_019:k1000  feyerabend_c0_021:k1000  feyerabend_c0_023:k1000
feyerabend_c0_025:k1000  feyerabend_c0_027:k1000  feyerabend_c0_029:k1000
feyerabend_c0_031:k1000  feyerabend_c0_033:k1000  feyerabend_c0_035:k1000
feyerabend_c0_037:k1000  feyerabend_c0_039:k1000  feyerabend_c0_041:k1
feyerabend_c0_041:k1000  feyerabend_c0_043:k1000  feyerabend_c0_045:k1000
feyerabend_c0_047:k1000  feyerabend_c0_049:k1000
```

## 6. 한계 (검증하지 않은 것)

- 가드-무력화 동치성(3절)은 이 코호트 200장면 × 결정론 교란 4종 범위의 실측이다. 임의 입력에 대한 형식적 동치 증명이 아니다 (단, 1절의 정적 전수 조사가 그 간극을 보강한다).
- 가드의 과차단(정당한 앵커 격리로 인한 coverage 손실) 가능성은 본 좌석 시야 밖 — lens1 소관.
- live counterexample의 F1 충실도는 lens2, 이중 봉인·300종 속성 시험의 실질은 seat4 소관.

## 판정

주장 ②의 세 요소 — ① 역전 26건이 원본 추정기에서 실재(저장분과 라이브 재실행 양쪽, 장면 id까지 일치) ② v2에서 0건으로 소멸(라이브 재실행이 저장 replay와 canonical 동일) ③ 소멸 원인이 정확히 `ratio_space_outlier_guard`(한 줄 무력화로 26건이 동일 id로 복귀, 가드 외 코드 차이의 수치 기여 0 실측) — 전부 독립 재현으로 성립한다.

VERDICT: CONFIRM
