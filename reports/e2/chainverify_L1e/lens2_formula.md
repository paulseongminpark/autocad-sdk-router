# lens2 — 신규 공식 적대 탐색 (chainverify_L1e, 4차 함대)

- 좌석: lens2 (공개 공식 구조 공격 — 희석·A_severe 창·reference 결합·9-family 밖 자유 교란 + 코드 대조)
- 검증 대상: L1e REPORT.md 9행의 공개 수리 공식과 그 구현 `feyerabend_c1_v4.py`(c1v6), 그리고 이 공식 위에서 "Feyerabend C1 루프 종결" 주장이 성립하는지
- 방법: 전 산출물 READ-ONLY. 재계산·프로브는 전부 `lens2_work\`(lens2_probe.py → probe_results.json · sweep_rises.json · T_A_classifier_record.json). git 조회·커밋 없음, 서브에이전트 없음, 원본 CAD·test 접근 없음.
- 실행 환경: Python 3.12, `loop_l1e.py`를 read-only import하여 함대 자신의 추정기(V4)와 자동 증인 분류기(`classify_upward`)를 그대로 사용.

## 0. 용어 한 줄 사전

- **τ (tau)** = `RANSAC_LOG_TOLERANCE` = ln(1.05) ≈ 0.04879. 로그 비율 공간의 허용 오차 단위.
- **handle** = 도면 개체의 고유 식별자. 독립성 판정의 단위(D1 수리).
- **ratio 측** = display 값/기하 span의 비율로 단위 배율을 추정하는 경로 → `confidence_score`·`unit_status`.
- **reference 측** = 기하 span 합의로 기준 span을 추정하는 경로 → `reference_confidence_score`·`reference_status`. 최상위 `status`는 reference_status와 동일.
- **공개 공식** (REPORT 9행 = 코드 상수 `CONTINUOUS_FORMULA`, 바이트 동일 확인): `p_h=min(1,(|z_h−z*|/τ)²)`; `A_handle=1−mean_h(p_h)`; `A_space=mean_bins(max_h_in_bin(1−p_h))`; `A_severe`=1 (dmax≤2.5τ) / smoothstep (2.5τ<dmax<3.5τ) / 0 (dmax≥3.5τ 또는 structural mixed/conflict/missing evidence); `ratio_score=A_handle·exp(−logMAD/τ)·A_space·A_severe`; `reference_score=span_score·mean_h(1−p_ratio,h)·A_severe`.
- **희석(dilution)** = 의심 handle은 그대로 두고 깨끗한 handle을 다수 추가해, 후보-수 평균으로 계산되는 페널티 항(mean 계열)의 분모를 키워 의심의 효과를 1/N로 무력화하는 공격.
- **증인 원리(봉인 prereg §perturbation_monotonicity)** = 상승 허용 ⇔ 교란 후 표면과 관측-동치이고 도시가 의미론상 정당하게 받는 정직 증인 장면 제시 가능. 판정 절차 6항: "residual ratio outliers, **handle collisions**, mixed-space traces, or other surviving suspicious signals are **explicit violation evidence**."

## 1. 코드-공식 대조 (좌석 의무 항목) — 일치 확인, 단 A_severe의 적용 범위에 유보

라이브 검증 (lens2_work\probe_results.json → P0):

- **해석적 재계산 일치**: 깨끗한 3-handle 합의 + 단일 outlier(d·τ) 구성 13점(d=1.5…10, 2.5τ·3.5τ 양측 ±1e-7 포함)에서 공식 손계산값과 `confidence_score`가 최대 오차 1.5e-15로 일치.
- **인자 항등식**: 모든 프로브·스윕 장면(2,000회 스윕 양측 포함)에서 `score == coherence·residual·spatial·severity` (ratio) 및 `score == span_score_before_ratio_attenuation·ratio_suspicion_attenuation·ratio_severe_residual_attenuation` (reference)이 오차 **0.0**으로 성립.
- **smoothstep**: 코드 `1−(3t²−2t³)`와 공식 표기 `smoothstep(3.5−dmax)`는 항등(대칭성 최대 편차 4.6e-16). 경계 연속성: τ에서 7.5e-10, 2.5τ·3.5τ에서 0. 창 내 단조 비증가 확인.
- **structural 0**: mixed-space·ratio 충돌·display 결손 각각 score 0 확인.
- selftest 4종 재실행: exit 0, 전건 observed true.

**유보 1건**: 공개 공식의 A_severe 정의는 "structural mixed/**conflict**/missing evidence"에서 0이라고 무제한으로 서술하고 그 A_severe를 `reference_score`에도 곱한다. 그러나 구현의 structural 집합은 **ratio 측 신호만** 포함하며, reference(span) 측 충돌·이탈에는 어떤 severe 봉투도 존재하지 않는다(P0 reference_identity: `keys_with_span_severity: []`, span 10τ outlier에서도 `ratio_severity_used: 1.0`). 즉 (i) 공식을 "A_severe는 ratio 유래 단일 항"으로 좁게 읽으면 코드=공식이나 공식이 §3의 위반 경로를 구조적으로 허용하고, (ii) 평문대로 "conflict evidence면 0"으로 읽으면 span 충돌에서 0이 되지 않는 구현은 공식과 불일치. 어느 독해로도 아래 §3의 결함이 소거되지 않는다.

## 2. A_severe smoothstep 창(2.5τ~3.5τ) — 창 자체는 건전, 역방향 이동 상승은 분류기 통과

- 창 경계 조작 가능성: 연속(0)·단조 확인, 3.5τ 문턱과 hard-suspicion 문턱(≥3.5τ)이 동일 지점이라 문턱 직하 조작의 이득은 severity≈0으로 수렴 — 창 자체의 착취 경로 없음.
- 역방향 이동(T_B): outlier 3.6τ→3.4τ 이동 시 NONE→LOW + score 0→0.01575 상승. 사후 표면에 3.4τ ratio outlier가 그대로 남지만 함대 분류기는 information_limit_record로 수용(잔존 의심 집계가 ≥3.5τ/structural만 계수). prereg 6항의 평문("residual ratio outliers … explicit violation evidence")과의 긴장 — **lens1 관할로 교차 플래그**, 본 좌석의 반증 근거로는 쓰지 않음.

## 3. 핵심 발견 — span 충돌 + 희석 = 함대 자신의 분류기가 violation으로 판정하는 상승 (T_A)

**구성** (26개 anchor, 인위 조작 없음 — 전부 `_make_anchor` 규격):

- HB: 같은 handle의 GRID 레코드 2개, 기하 span 1000 vs 3000 (ln3 ≈ 22.5τ 충돌) → `source_handle_span_conflict`, 봉인 prereg의 handle_collision 계열("conflicting records sharing source handles") 의심 신호.
- A·B·C: 깨끗한 DIM 3개 (span 1000, display 2500 MM).
- 교란: 깨끗한 DIM D00..D19 20개 추가(전부 상이한 handle·위치, ratio·span 완전 정합). **HB는 손대지 않는다.**

**실측 (lens2_work\probe_results.json → P3.T_A, 분류 레코드 전문 T_A_classifier_record.json)**:

| 추가 N | reference_confidence_score | status / reference_status |
| --- | --- | --- |
| 0 | 0.421875 | LOW / LOW |
| 3 | 0.587755 | LOW / LOW |
| 10 | 0.718537 | LOW / LOW |
| 20 | **0.918403** | **HIGH / HIGH** |
| 40 | 0.955062 | HIGH / HIGH |

- 상승 필드: `reference_confidence_score`(0.4219→0.9184), `status`(LOW→HIGH), `reference_status`(LOW→HIGH). 전 구간에서 HB는 `reference_outlier_handles=["HB"]`로 표면에 잔존.
- **함대 자신의 `classify_upward` 판정**: `residual_suspicion_count=1 (span_conflict_handles=["HB"])` → `city_semantic_legitimacy=false` → 증인 후보 기각(`REJECTED::d8f6f036…`) → **`automated_classification_result = "violation"`**.

**왜 이 구멍이 열려 있는가 (수리 비대칭)**: ratio 측 충돌은 structural→A_severe=0으로 경성 차단되어 동일 공격이 완전 무효(T_A2 대조: 전 필드 무상승, score 0 고정). 그러나 span 충돌은 (i) A_severe의 structural 집합에 들어가지 않고, (ii) 남은 관련 항이 전부 후보-수 평균(`A_handle`의 mean, trust의 mean, bin 평균)이라 깨끗한 추가 N→∞에서 페널티가 1/N로 소멸한다. max 기반 undilutable 항은 ratio 측 A_severe뿐이다(P2: severe 5τ·mixed·ratio 충돌은 N=0/10/40 전부 score 0 고정 — 이 통제는 건전).

**자유 교란 사냥 (P5)**: seed 20260719, 의심 기반 9종 × 교란 11종 2,000회 → 상승 265건, 분류: information_limit_record 215 · **violation 50**. 위반 50건 전부가 동일 구멍(`span_collision` 기반 × 깨끗한 handle 추가)이며 그중 26건은 status LOW→HIGH 포함. 다른 어떤 조합에서도 위반 등급 상승 없음 — 구멍은 특정적이고 재현적이다.

**증인 불가 판정 근거** (좌석 계약: "증인 가능=한계 기록, 불가=위반"):

1. 봉인 prereg 판정 절차 6항이 "handle collisions"를 명시적 위반 증거로 지정.
2. 함대 자신의 운영화(`suspicion_analysis`)가 span_conflict를 잔존 의심으로 계수하고, 그 위에서 자동 분류기가 이 상승을 violation으로 출력(위 실측).
3. 함대 자신의 분류 체계가 handle_collision을 "수리 가능(=정직 증인 불가) class"로 놓고 0-상승 폐쇄를 주장(검증 대상 주장 ①) — 충돌 잔존 표면의 상승에 증인을 부여하면 자기 분류 체계와 모순.

## 4. 보조 발견

- **T_C (ratio 중간대 희석)**: 2.4τ outlier 잔존 상태에서 깨끗한 추가만으로 unit_status LOW→HIGH(0.5625→0.9583), outlier는 전 구간 `ratio_attenuated_handles=["X"]`로 가시 잔존. 함대 분류기는 info-limit로 수용. CE-B2 봉인 문언은 "숨기는 경로"만 금지하므로 문언 위반은 아니나, 6항 평문("residual ratio outliers")과의 긴장 재확인 — lens1 교차 플래그. 감쇠가 1/N로 점근 소멸하는 것 자체는 공개 공식의 구조적 귀결.
- **T_S (severe span outlier 희석)**: 10τ span outlier 잔존+희석 → reference LOW→HIGH. span 측에는 severe 봉투가 아예 없음을 실증. 분류기 info-limit(스팬 단독 outlier는 정직 증인 구성이 그럴듯 — 위반 주장 안 함).
- **P4 (과차단 경로, 좌석 ③)**: 정직한 GRID 5개를 깨끗한 DIM 3개 장면에 추가하면 `mean_h(1−p_ratio)`의 ratio-부재 handle 기본 페널티 1.0 때문에 trust 0.375, reference_score 1.0→0.375, reference_status HIGH→LOW. **정직 증거 추가가 reference 신뢰를 파괴**하는 무조건 과차단. 봉인 코호트 밴드는 GRID-희박 코퍼스라 걸리지 않았을 뿐이며, 공개 공식은 이 기본값(ratio-부재 handle→p_ratio=1)을 공시하지 않는다.

## 5. 판정 논리

검증 대상 주장은 "L1e로 루프가 **종결**됐다"이다: 수리 가능 class 폐쇄(①) + 잔존 상승 전건 정직 증인(②)이 그 근거다. 본 좌석은 ①·②의 **실행 범위 내 수치 자체는 다투지 않는다** (72,396 전이·361 증인·violation 0은 그들의 전이 우주에서 참일 수 있음 — lens3·seat4 관할). 반증 지점은 종결 주장의 성립 조건이다:

- 9-family는 어느 것도 "상이한 깨끗한 handle 추가"를 포함하지 않으므로, mean-분모 구조의 희석 취약성은 그들의 전이 우주에서 구조적으로 시험된 적이 없다.
- 그 우주 밖 최소 구성(26 anchor)에서, 봉인 계약이 명시적 위반 증거로 지정한 의심 신호(handle collision)가 잔존하는 채로 status LOW→HIGH 상승이 발생하고, **함대 자신의 자동 분류기가 이를 violation으로 판정**한다. 무작위 사냥 2,000회에서 동일 구멍으로 위반 50건.
- 따라서 "위반 0 = 의미론 수리 완성"이 아니라 "위반 0 = 시험 우주가 이 구멍을 밟지 않음"이다. 수리 4항은 ratio 측 충돌만 경성 봉투(A_severe)로 닫았고, 동형의 span 측 신호는 희석 가능한 연성 평균에 남았다(T_A2 대조로 비대칭 실증). 루프 종결 주장은 이 반례 앞에서 유지되지 않는다.

예상 반론과 응답: "깨끗한 증거 추가는 교란이 아니다" — 봉인 판정 절차는 원인 아닌 **사후 표면**을 심판하며, 함대 분류기 스스로 이 표면의 증인 후보를 기각했다. "주장 스코프는 9-family다" — 좌석 계약 ④가 명시적으로 9-family 밖 탐색과 위반 분류를 요구하며, 종결 주장은 시험 집합이 아니라 추정기의 의미론에 대한 주장이다.

## 6. 검증하지 못한 것

- 361건 증인 레코드의 개별 타당성(lens1)·replay/코호트 수치 재계산(lens3)·봉인 사슬(seat4)은 본 좌석 범위 밖 — 본 판정은 그것들의 성부와 독립.
- T_A의 witness-불가 판정은 봉인 prereg 6항 + 함대 자신의 운영화에 의거한다. 오케스트레이터가 span 충돌 표면의 정직 증인 가능성을 새로 주장하려면 자기 분류기(§3 실측)와 수리 class 분류(①)를 먼저 뒤집어야 한다.

## 7. 재현

```
C:\Users\PAUL\AppData\Local\Programs\Python\Python312\python.exe D:\runs\e2_program\chainverify_L1e\lens2_work\lens2_probe.py
```

산출: `lens2_work\probe_results.json`(P0~P5 전 수치) · `lens2_work\sweep_rises.json`(상승 265건 전건) · `lens2_work\T_A_classifier_record.json`(함대 분류기의 violation 레코드 전문, 표면 직렬화·digest 포함). 결정적 seed 20260719, 원본 산출물 무변경.

VERDICT: REFUTE
