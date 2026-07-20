# F02 잔여축 실물-대-합성 face-consumer 측정 보고서

PREREG SHA-256: `11e6c5cade83954246c0849cdf61d114e5e8907d878b779a0e450404bae7ef33`

- 측정 시각: `2026-07-20T02:37:25.899759Z`
- 측정 완결 상태: `COMPLETE`
- face exploratory 게이트: `FAIL`
- 검증기 우주 INSERT/HATCH 포함 상태: `NOT_COVERED` (관측 source가 있는 모든 해당 분모에서 emitted=0)
- 해석 경계: face-only 결과는 calibration core 또는 CL-B claim의 자격을 만들지 않는다.

## 입력 봉인과 전건 무결성

수치 산출 전에 `D:\runs\e2_program\cells\f02_real_axis\PREREG_local.json`을 봉인했다. 계획서 F02 행의 문언은 다음과 같이 고정했다.

> calibration core `KS≤0.10/TV≤0.10` · CL-B `KS≤0.2/TV≤0.1` · face exploratory `KS_max≤0.30/TV≤0.20`; face-only 통과는 상위 두 claim의 자격이 아님.

봉인 뒤 입력을 재검증한 결과:

| 검사 | 결과 |
|---|---:|
| critical file SHA-256 | 8/8 일치 |
| annotation/fidelity/family tree seal | 3/3 일치 |
| synthetic DXF/truth manifest pair SHA-256 | 350/350 일치 |
| 독립 재계산·집계 검증 | 51/51 PASS |

근거: `D:\runs\e2_program\cells\f02_real_axis\input_hash_verification.json`, `manifest_hash_verification.csv`, `verification.json`.

## 사전등록된 모집단과 UNKNOWN 처리

실물의 키는 `(block definition, source entity handle)`이다. 다섯 annotation arm 가운데 3개 이상이 `wall_line_handles`에 명시한 키만 `CONFIRMED_POSITIVE`로 primary에 포함했다. 1–2표는 `UNKNOWN_DISPUTED`, 명시되지 않은 referenced supported handle은 `UNKNOWN_UNOBSERVED`로 보존했다. 어느 UNKNOWN도 primary 분포에 대치하지 않았다.

| 항목 | 관측 |
|---|---:|
| annotation definitions | 384 |
| explicit handle keys | 502 |
| CONFIRMED_POSITIVE keys | 206 |
| UNKNOWN_DISPUTED keys | 296 |
| UNKNOWN_UNOBSERVED referenced supported keys | 24,964 |
| confirmed world primitives | 1,280 |
| disputed world primitives | 13,448 |
| annotated but uninstantiated keys | 7 |

실물 기하는 modelspace INSERT chain을 재귀 전개하고 모든 enclosing transform을 적용한 world 좌표에서 측정했다. 합성은 각 truth JSON의 `wall_handles_flat` handle을 paired DXF modelspace에서 정확 조회했다. LINE, LWPOLYLINE/POLYLINE, ARC, CIRCLE, SPLINE만 사전등록한 chord 정책으로 변환했다. 각 도면의 선택된 유효 wall-face chord 길이 중앙값으로 길이와 끝점갭을 정규화했다.

근거: `real_label_votes.csv`, `real_handle_status.csv`, `primitive_observations.csv`, `unknowns.csv`.

## Primary face-consumer 대조

Primary는 실물 `CONFIRMED_POSITIVE`와 `fidelity_full` 150장 + `gen2_families` 200장을 합친 합성 350장의 pooled 관측을 비교한다.

| 지표 | 실물 n | 합성 n | 관측 | 밴드 | 결과 |
|---|---:|---:|---:|---:|---|
| normalized primitive length KS | 1,280 | 16,552 | 0.364915493596 | ≤0.30 | FAIL |
| normalized endpoint gap KS | 2,560 | 33,104 | 0.442732751329 | ≤0.30 | FAIL |
| KS_max | — | — | 0.442732751329 | ≤0.30 | FAIL |
| endpoint-graph degree TV | 2,437 nodes | 24,250 nodes | 0.314641510392 | ≤0.20 | FAIL |

게이트는 `KS_max≤0.30 AND degree_TV≤0.20`이다. 두 조건이 모두 밴드를 넘었으므로 결과는 `FAIL`이다. 이는 측정 실패가 아니라 품질 밴드 불충족이다.

### 분포 요약

| 모집단 | length n | length median | length mean | length p95 | gap n | gap median | gap mean | degree counts |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| real confirmed | 1,280 | 1.000000 | 1.288573 | 4.081633 | 2,560 | 0.092416 | 0.449163 | d1=2,314; d2=123 |
| synthetic pooled | 16,552 | 1.000000 | 11.867600 | 55.673297 | 33,104 | 0.000000 | 0.418429 | d1=15,396; d2=8,854 |

근거: `drawing_distribution_summary.csv`, `degree_counts.csv`, `measurement_results.json`.

### 민감도 대조 — 판정 대체 금지

| 대조 | KS_max | degree TV | 표기 |
|---|---:|---:|---|
| real confirmed vs fidelity_full | 0.492427884615 | 0.362571586591 | DESCRIPTIVE_ONLY |
| real confirmed vs gen2_families | 0.410598015320 | 0.285342061818 | DESCRIPTIVE_ONLY |
| real confirmed vs tier S | 0.509166488452 | 0.050471891670 | DESCRIPTIVE_ONLY |
| real confirmed vs tier F | 0.540785165148 | 0.412556644052 | DESCRIPTIVE_ONLY |
| real confirmed vs tier M | 0.520886213491 | 0.391565813906 | DESCRIPTIVE_ONLY |
| real confirmed+disputed vs pooled | 0.286125250031 | 0.308355985693 | DESCRIPTIVE_ONLY_UNKNOWN_INCLUDED |

마지막 행은 UNKNOWN을 포함한 민감도일 뿐이다. 길이/갭 KS가 달라져도 degree TV가 0.20을 넘으며, 사전등록에 따라 primary 판정을 대체하지 않는다.

## 검증기 우주의 INSERT/HATCH 커버리지

현재 SEG-IR adapter는 modelspace의 LINE/LWPOLYLINE/POLYLINE/ARC/CIRCLE/SPLINE만 emit하고 HATCH와 INSERT를 생략하며 INSERT를 전개하지 않는다. 아래 source/emitted 카운트는 이 실제 정책을 그대로 계측한 값이다.

| cohort | source HATCH | emitted HATCH | top-level INSERT | emitted INSERT | INSERT-internal supported entities | emitted internal entities |
|---|---:|---:|---:|---:|---:|---:|
| real | 1,000 (top-level 0 + internal 1,000) | 0 | 50 | 0 | 288,092 | 0 |
| fidelity_full | 4,050 | 0 | 17,700 | 0 | 35,400 | 0 |
| gen2_families | 5,400 | 0 | 23,641 | 0 | 47,282 | 0 |
| synthetic pooled | 9,450 | 0 | 41,341 | 0 | 82,682 | 0 |

추가 관측:

- 실물 recursive INSERT occurrences: 3,736.
- 실물 INSERT-internal all entity occurrences: 298,657.
- 실물 INSERT-internal supported geometry가 전개되었다면 생기는 chord는 3,112,317개지만, 이는 counterfactual 설명값이며 실제 verifier emitted count는 0이다.
- 합성 pooled INSERT-internal supported geometry의 counterfactual chord는 1,364,253개이며 실제 emitted count는 0이다.
- geometry conversion errors: 0.
- cyclic/missing block references: 0.

따라서 source가 있는 분모에서 HATCH, top-level INSERT, INSERT-internal supported geometry의 현재 verifier coverage는 모두 `0.0`이다. 실물 top-level HATCH만 분모가 0이라 그 개별 ratio는 `UNKNOWN`; 내부 HATCH 1,000개를 포함한 실물 전체 HATCH 분모에서는 coverage가 0이다.

근거: `coverage_by_drawing.csv`, `coverage_aggregate.csv`.

## 독립 검증

`D:\runs\e2_program\cells\f02_real_axis\verify_f02_real_axis.py`가 raw CSV에서 scipy KS와 독립 TV를 재계산했다.

| 재계산 | 값 | 원 측정과 일치 |
|---|---:|---|
| length KS | 0.364915493596 | yes |
| endpoint-gap KS | 0.442732751329 | yes |
| KS_max | 0.442732751329 | yes |
| degree TV | 0.314641510392 | yes |
| face verdict | FAIL | yes |

전체 51개 검사에서 실패는 0개였다. 검증 PASS는 산출 무결성에 대한 상태이고, face 품질 결과 `FAIL`을 뒤집지 않는다.

## evidence.xlsx 대체 사유

이 executor에는 spreadsheet workflow가 요구하는 `load_workspace_dependencies` capability가 노출되지 않았다. 따라서 `@oai/artifact-tool`을 규정대로 로드할 수 없었고, 대체 Excel 라이브러리를 사용하지 않았다. 패킷의 허용 조문에 따라 같은 보고서 폴더에 `evidence.csv`를 생성했다.

- fallback: `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\f02_real_axis\evidence.csv`
- SHA-256: `b52e6e00f67cf4afc04b3f3b64e798e0a2aef69ea842138e4598a968a77b9bcc`

## 산출물과 경계 준수

주요 raw 산출물은 `D:\runs\e2_program\cells\f02_real_axis\` 아래에 있다.

- `measurement_results.json` — SHA-256 `020ed810e0f4c3369f16e139285cba17e35b6a2a5e28c06a3cf7c79852937956`
- `verification.json` — SHA-256 `49b716260d782b4d3f23c0fa83944525f0c4a037a4cdf469f716f85bc1e7258f`
- `comparison_metrics.csv` — SHA-256 `671d0251f3b8f22370eb3a15a17b2cc1e8e8fc517b78f1388564f9beddd8945e`
- `coverage_aggregate.csv` — SHA-256 `9e85a6183074924ca1528339e68753486c992e6e739e3308acad641dd1d3fd47`
- `artifact_manifest.json` — raw 산출물별 absolute path, byte size, SHA-256, CSV data-row 수.
- `primitive_observations.csv`, `endpoint_gap_observations.csv`, `endpoint_degree_nodes.csv`, `drawing_distribution_summary.csv`, `coverage_by_drawing.csv`, `real_label_votes.csv`, `real_handle_status.csv`, `manifest_hash_verification.csv`, `unknowns.csv`.

모델 API 호출, test-set 접근, 원본 CAD 쓰기, Git 명령, 서브에이전트 사용은 없었다. 원본 `1_export.dxf`는 read-only로만 열었다. 실행 전에 존재하던 잘못된 상대경로 기반 차단 표시는 삭제하지 않고 `preexisting_BLOCKED_INPUT_20260720_111013.txt`로 보존했다.

AXIS_MEASUREMENT_COMPLETE
