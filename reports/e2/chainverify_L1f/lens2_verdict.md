# lens2 verdict — 공식 구조 · 희석 재공격 · 44건 상승 전수 판별 (fable 좌석 2, 5차 함대 L1f Phase B)

## VERDICT: REFUTE

봉인 조문 `sealed_bands.ratio_absent_handle_neutrality` (gate:true, `no_loss_rule.allowed_downgrade_count:0`)가
일반적으로 위반됨을 실증했다. **정직한 비율-부재(ratio-absent) GRID 앵커 1개를 추가**하면 — 기존 증거 바이트 불변 —
중간대(0.5τ~2.159τ) 비율 잔차가 있는 장면에서 reference 신뢰가 파괴되고 status가 HIGH→NONE으로 강등된다.
봉인 계약이 하나라도 위반되면 REFUTE이며(과업 문서 §판정 어휘), 부분 확인은 CONFIRM이 아니다.

### 결함 class 구분 (에스컬레이션 판단용)

**(a) 기존 class의 회귀/변주 — 신규 class 아님.** 이 결함의 *관측 class*는 4차 함대 lens2가 이미 적중한
**"GRID 과차단(over-block) / 비율-부재 handle 비중립성"**(기존 결함 목록 4번 "GRID 과차단", 4차 P4:
"정직 증거 추가가 reference 신뢰를 파괴")과 동일하며, 위반되는 봉인 조문도 동일(`ratio_absent_handle_neutrality`)하다.
- **v5는 4차의 원래 기제는 닫았다**: 4차 P4의 "비율-부재 handle이 ratio 평균에 기본 페널티 1.0으로 진입" 경로는
  제거됐고, 깨끗한-베이스 P4(3 clean DIM + 5 GRID)는 이제 무손실이다(probe6 control: neutral=True).
- **그러나 v5가 도입한 새 코드 경로가 같은 class를 재개방·악화시켰다**: 새 2계층 분류기의
  `grid_present` 판별자가 *다른* 비율-보유 handle의 Tier 분류를 뒤집는다. 잔차 반경이 (0.5τ, 2.159τ]인 경우
  GRID 부재 시 Tier-A(감쇠)였던 것이 GRID 추가 시 Tier-B(경성 차단)로 바뀐다. 4차의 연성 강등(HIGH→LOW)이
  **경성 차단(HIGH→NONE)으로 악화**됐다.
- 새로운 것은 *내부 기제*(맥락 의존 봉투 축소)일 뿐, class·조문·관측은 기존 것이다 — **"신규 class" 주장은
  과장이므로 하지 않는다**(과업 문서 §"과장 금지").

**에스컬레이션 함의**: 이는 "v5 수리가 자기 P4 중립성 축에서 회귀·불완전하다"는 신호다. 구현 반복을 계속해
neutrality 조문을 (깨끗한-베이스 인스턴스가 아니라) *일반적으로* 닫아야 함을 뜻하며, 그 자체로 Paul 결재를
요구하는 완전 신규 전선은 아니다. 단 봉인 gate 위반이므로 루프 종결(PASS)은 불가하다.

---

## 0. 봉인 확인 (선결)

- `prereg.json` SHA-256 = `76AC2A58D74C644A3BF7897325818F1E12151596DC3316BA7CA488BDEB207861` — 과업/REPORT 명시값과 일치
  (명령: `Get-FileHash D:\runs\e2_program\cells\loop_l1f\prereg.json -Algorithm SHA256`).
- `PREREG_SEALED.csv` SHA-256 = `94356AF8F4D219AF65A96825E3A08B29245454EDA1B29B2C3AE83F4B19A8F266` — 일치.
- 유일한 봉인 조문 파일로 `prereg.json`을 채택. 모든 수치 주장은 아래 `lens2_work\` 프로브 산출로 뒷받침한다.

용어 한 줄 사전:
- **τ (tau)** = `RANSAC_LOG_TOLERANCE` = ln(1.05) ≈ 0.048790. 로그 비율 공간 허용오차 단위.
- **ratio 측** = display/기하 비율로 단위배율 추정 → `confidence_score`·`unit_status`.
- **reference 측** = 기하 span 합의 → `reference_confidence_score`·`reference_status`(최상위 `status`=reference_status).
- **Tier-A** = 봉인 정직-봉투 안의 잔차(감쇠만, 상승 허용). **Tier-B** = 봉투 밖 신호(경성 차단, score 0/NONE).
- **ratio-absent GRID** = display 없는 GRID 앵커(비율 정보 없음). 봉인이 "ratio trust에 중립"이라 선언한 handle.

---

## 1. 표적1 — 공식 구조 감사: 후보-수 분모 재진입 없음 (CONFIRM)

`probe1_formula_audit.py` → `probe1_results.json`. 감쇠 경로를 전수 추적한 결과 후보-수(candidate-count) 분모가
정규화·가중평균·soft-max·클리핑 어떤 우회로도 **재진입하지 않는다**:

- **공식 문자열 = 코드 = REPORT (바이트)**: `NON_DILUTION_FORMULA` 상수가 REPORT 12행에 verbatim 존재
  (`report_contains_verbatim: True`). 공식: `q_ratio=Q_clean_support*∏_s(1-floor_s)`;
  `q_reference=Q_clean_span_support*∏_ratio_s(1-floor_s)*∏_span_s(1-floor_s)`; floor는 의심신호별이고 후보-수 분모 없음.
- **floor 법칙 일치**: `_tier_a_floor(d,L) = 0.05+0.20*(d/L)²` (클립 [0.05,0.25]) — 공시값과 전건 일치
  (`floor_law.all_match: True`). floor는 오직 (거리 d, 봉인 한도 L)의 함수 — **후보 수 N과 무관**.
- **점수 항등식**: `score == R_clean · ∏_s(1-floor_s)`가 clean·Tier-A(1·2·5 신호)·Tier-B·희석 혼합 10케이스에서
  1e-12 이내 일치(`score_identity.all_match: True`). 감쇠는 **곱(product)** 구조뿐 — 평균 항 없음.
- **후보-수 불변 (핵심)**: 고정 S(2.0τ 잔차)에 clean N∈{0,3,10,20,40,**100,400**} 주입 시
  `confidence_score`·`reference_confidence_score`가 **비트 단위 불변**(`*_bit_invariant: True`). 동시에
  `consensus_fraction`·`n_candidate_handles`는 N에 따라 변함(`consensus_fraction_varies: True`) — 즉 후보 수는
  **보고되지만 페널티에 미사용**. 4차 함대가 적중한 mean-분모 희석 경로는 구조적으로 소거됐다.
- **의심 행이 location/MAD에 미진입**: 잔차 handle은 `huber_location`·`log_mad` 채널에서 제외
  (`suspicious_rows_excluded_from_location.all_match: True`) — 추정치는 오염되지 않는다.
- **클램프 상한**: residual 1.0-스냅·score 0.75-스냅은 abs 1e-12 이내로만 작동(상승 여력 ≤1e-12) — 착취 불가.
- **연속성**: clean→Tier-A 경계 계단은 1→0.95(0.05 floor 진입, `clean_to_tierA_step=0.05`)로 1→0 절벽 아님;
  Tier-A→Tier-B 전이(O2 한도)는 봉인 폐쇄-세계 경계로 0.75 점프(공시된 `BOUNDARY_BEHAVIOR`와 일치).

---

## 2. 표적2 — 희석 재공격: 4차 회귀 봉쇄 확인 + 신규 변주에서 봉인 위반 적발

### 2a. 4차 명명 회귀 재실행 — 전부 봉쇄 (CONFIRM)

`probe2_regressions.py` → `probe2_results.json`. N∈{0,3,10,20,40,**100,400**} (봉인 스윕은 40에서 정지).

| 회귀 | 4차 결과(v4/c1v6) | v5 결과 (전 N) |
| --- | --- | --- |
| T_A (span 충돌 + 희석) | LOW→HIGH, 분류기 violation | reference score=0·status=NONE **고정**, 0 상승 |
| T_A2 (ratio 충돌, 대조) | 경성 차단 | ratio·reference 모두 0/NONE 고정 |
| T_C (2.4τ ratio 잔차 + 희석) | LOW→HIGH | ratio·reference 모두 0/NONE 고정 (2.4τ>2.159τ → Tier-B) |
| T_S (10τ severe span + 희석) | LOW→HIGH | reference 0/NONE 고정 |
| T_B (3.6τ→3.4τ 역방향 이동) | NONE→LOW 인증 | **차단**(3.4τ>2.159τ → Tier-B `unregistered_or_envelope_exceeding_ratio_residual`) |

4차 함대가 적중한 span-충돌×희석 위반, ratio 중간대 희석, severe span 희석, 역방향 이동 인증 창은 v5에서 전부
경성 차단된다. 어느 케이스도 N을 400까지 키워도 상승 쌍이 0(`any_pairwise_rise_v5: []`).

### 2b. 신규 희석 변주 35종 — per-signal floor N-불변 확증 + 2건 봉인 위반 (REFUTE 근거)

`probe3_dilution_variants.py` → `probe3_results.json` (V01–V35). N∈{0,3,10,20,40,100,400}, 매 N에 matched-clean
반사실 병행. 이종 조합(DIM/TEXT/CM 분할), 2계층 혼합(Tier-A 잔존 + Tier-B 인접), 가중치·위치·단위 변주 포함.

**N-불변 확증** (Tier-A 베이스 V01–V11,V15,V16,V19–V23,V35): confidence가 N에 걸쳐 **drift 0.0**, 신호 집합 불변,
matched-clean 페널티 ≥ 집계 floor(min_penalty_minus_floor ≥ 0). **Tier-B 베이스**(V05,V12–V14,V17,V18,V24–V28,V30,V31):
해당 score 0·status NONE 전 N 고정. per-signal floor의 N-불변은 수치로 확증된다.

**그러나 2건이 봉인 조문을 위반한다** (아래 §3에서 심층 실증):

- **V07** (Tier-A 1.0τ 잔차 + 정직 GRID 추가): reference 0.907 HIGH → **0.0 NONE**. status·unit_status·reference_status
  모두 HIGH→NONE. — `ratio_absent_handle_neutrality.no_loss_rule` (allowed_downgrade_count:0) 위반.
- **V34** (Tier-A 0.3τ 잔차 + 정직 GRID 추가): reference 0.946 → **0.878** (감소). — `reference_confidence_score_must_not_decrease:true` 위반.

(V11 "5개 Tier-A 신호 + 희석"의 drift는 **프로브 아티팩트**로 판정: N=0에서 5개 잔차가 3개 clean의 합의를
교란해 합의가 미형성(ratio_clean=[], conf=0)이었고, clean 추가가 올바른 합의를 *복원*해 conf 0→0.526로 상승한 것.
S 고정 전제가 N=0에서 성립하지 않음 — 위반 아님. N≥3(합의 안정) 이후는 비트 불변. `probe3b_results.json` 참조.)

---

## 3. 핵심 실증 — 정직 GRID는 "ratio trust에 중립"이 아니다 (봉인 gate 위반)

`probe6_grid_neutrality_break.py` → `probe6_results.json`; `probe3b_inspect.py` → `probe3b_results.json`.

### 3.1 봉인 조문 (인용)

`prereg.json` `sealed_bands.ratio_absent_handle_neutrality` (line 360–375, gate:true):
- title: **"ratio-absent honest handles are neutral to ratio trust"**
- `ratio_path_rule`: 비율-부재 handle은 "excluded from both numerator and denominator of every ratio-trust
  mean or aggregate. It contributes neither a default ratio penalty nor manufactured ratio support."
- `no_loss_rule.operation`: **"Add honest ratio-absent GRID handles while leaving all existing evidence unchanged."**
  → `reference_confidence_score_must_not_decrease: true`, `reference_status_must_not_downgrade: true`,
  `status_must_not_downgrade: true`, **`allowed_downgrade_count: 0`**.
- 조문의 `operation`은 *일반*이며, `mandatory_regression`("lens2 P4")은 최소 인스턴스일 뿐 범위 상한이 아니다.

### 3.2 근본 기제 (코드)

`feyerabend_c1_v5.py`:
- line 514: `grid_present = bool(ratio_absent_grids)` — 비율-부재 GRID 존재 여부가 불리언 스위치.
- line 541–576: ratio 잔차 분류 분기. `grid_present`가 참이면 Tier-A 허용 봉투를
  `O2_class_moderate_display_stale`(한도 **2.159τ**, line 559)에서 `O2_class_type_to_grid_display_residual`
  (한도 **0.5τ**, line 541)로 *교체*한다. 잔차 반경이 (0.5τ, 2.159τ]이면:
  - GRID 부재 → Tier-A(감쇠, 상승/HIGH 허용)
  - GRID 존재 → Tier-B `unregistered_or_envelope_exceeding_ratio_residual` → ratio·reference 경성 차단(0/NONE)

즉 비율-부재 GRID의 *단순 존재*가 **다른** 비율-보유 handle(X)의 Tier 분류를 뒤집는다. 봉인 `ratio_path_rule`이
"비율-부재 handle은 ratio-trust에 default penalty도 manufactured support도 기여하지 않는다"고 못박은 것과 정면 충돌.

### 3.3 실측 (Case A — 경성 형태)

| 상태 | 장면 | reference_score | status | unit_status | X 분류 |
| --- | --- | --- | --- | --- | --- |
| before | A,B,C(clean) + X@1.0τ | **0.9071** | HIGH | HIGH | Tier-A `O2_class_moderate_display_stale` (1.0≤2.159) |
| after | 위 + 정직 GRID 1개 | **0.0** | **NONE** | **NONE** | Tier-B `...residual_above_W000004_limit` |

- **기존 증거 바이트 불변**: `digest(existing) == digest(after[:len(existing)])` → `existing_unchanged: True`.
  추가된 것은 오직 정직한 비율-부재 GRID(display=None, 기하 정합) 1개.
- reference 감소량 = **0.9071** (전량 소실). reference_status·status·unit_status 3중 강등 HIGH→NONE.
- **봉인 위반**: `no_loss_rule` `allowed_downgrade_count:0` 대비 3개 필드 강등 + reference 감소.

Case B (완만 형태, X@0.3τ): reference 0.946 → 0.878 (감소, status 유지). `reference_confidence_score_must_not_decrease:true` 위반.

### 3.4 결함 대역과 대조군

- **결함 대역**: 잔차 d∈(0.5τ, 2.159τ]에서 GRID 추가 시 status 강등 — d∈{0.51,0.7,1.0,1.5,2.0,2.159}τ 전부
  HIGH→NONE (`defect_band_summary.d_tau_with_status_downgrade_on_grid_add`).
- **대조군 (봉인 P4, 깨끗한 베이스)**: 3 clean DIM + 5 GRID는 중립(`control_P4_clean_base.neutral: True`).
  실행자의 P4 게이트("reference-confidence loss: 0")와 v5 selftest `ratio_absent_grid_neutral`은 **오직 이
  깨끗한-베이스만** 시험한다(`exact_fixture()` = 잔차 없는 5 clean DIM). 잔차와 GRID가 공존하는 구멍은 밟지 않는다.
- **내부 모순**: v5가 상승까지 허용하며 정직 Tier-A로 인정한 바로 그 `O2_class_moderate_display_stale` 잔차(§4 44-표의
  1·2·3·4·10·11번 등)가, 정직 GRID를 추가하는 순간 Tier-B 경성 차단으로 뒤집힌다. 동일 잔차, 정반대 판정 —
  차이는 오직 "봉인이 중립이라 선언한" GRID의 존재.

### 3.5 자유 사냥에서의 계통성 (표적5, 아래 §6)

1,500 무작위 케이스(seed 20260719)에서 정직-추가만으로 손실/강등이 **32건** 발생(add_grid_to_residual 12,
add_grid 12, grid_plus_clean 8; GRID-only 24건). 일회성 아님 — 계통적 봉인 위반.

---

## 4. 표적3 — 44건 상승 전수 판별 (상승 축에서는 위반 없음, CONFIRM)

`probe4_rise_adjudication.py`·`probe4b_validate_and_stream.py` → `probe4_44_table.json`·`probe4_44_table.md`.

**독립 판정기 검증(필수 선결)**: 본 좌석은 실행자 분류기를 재실행하는 데 그치지 않고, `prereg.json`의 봉인 한도에서
직접 Tier 신호를 재유도하는 **독립 판정기**(`lens2_common.independent_adjudication`)를 만들었다. 이 판정기는
알려진 Tier-B 표면 6종(span 충돌, 2.4τ, severe 5τ, mixed space, 기하 모순, ratio 충돌)에서 전부 Tier-B를
발화하고, clean/Tier-A 3종에서 전부 통과한다(`adjudicator_validation.all_tier_b_fired: True`,
`all_clean_clean: True`). 즉 "위반 0"은 공허하지 않다.

**44건 추출·판별**: 243MB `fleet_probe_results.json`을 샌드박스에서 스트리밍 → P5 2,000 케이스 중 v4 상승 265건,
**v5 상승 정확히 44건**(`confirms_44: True`), 전부 실행자 라벨 information_limit_record. 44건 각각에 대해
(a) 독립 판정기 + (b) live v5 재실행으로 사후 표면을 심판한 결과:

- **독립 Tier-B 위반 = 0 / 44** (`independent_violation_count: 0`).
- **실행자 라벨 vs 독립 판정 불일치 = 0** (`disagreements: 0`).

44건 op 분포: remove_one 25, toward_consensus 9, unit_flip 7, retype_grid 2, collide 1. 전부 정당한 상승이다:
- remove_one(25) = 의심 앵커 *제거* → 잔차 소멸(사후 표면 clean).
- toward_consensus(9) = display를 합의로 이동 → 잔차가 O2 한도(2.159τ) 이내로 진입, 정직 stale 서사 성립(Tier-A).
- unit_flip(7) = 정합 단위로 변환(z_raw→z_mm) → clean.
- retype_grid(2) = 의심 DIM을 GRID로 재유형 → ratio 잔차 소멸.
- collide(1) = handle 병합 후 잔차가 O2 한도 이내.

전수 판별표(요약, 전문은 `lens2_work\probe4_44_table.md`/`.json`):

<details><summary>44건 판별표 (case_id · op · 상승필드 · 실행자라벨 · 독립판정 · v5 Tier-A/B)</summary>

cs=confidence_score, rcs=reference_confidence_score, st=status, us=unit_status, rst=reference_status

| # | case_id | op | 상승필드 | 독립판정 | v5 Tier-A(사후) | v5 Tier-B(사후) |
|---|---------|----|---------|---------|-----------------|-----------------|
| 1 | P5_0047_severe_toward_consensus | toward_consensus | cs+rcs+st+us+rst | a-정당 | O2_stale | - |
| 2 | P5_0064_midband_toward_consensus | toward_consensus | cs+rcs+st+us+rst | a-정당 | O2_stale | - |
| 3 | P5_0082_midband_toward_consensus | toward_consensus | cs+rcs+st+us+rst | a-정당 | O2_stale | - |
| 4 | P5_0190_midband_toward_consensus | toward_consensus | cs+rcs | a-정당 | O2_stale | - |
| 5 | P5_0208_midband_remove_one | remove_one | cs+rcs | a-정당 | - | - |
| 6 | P5_0209_severe_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |
| 7 | P5_0235_midband_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |
| 8 | P5_0379_midband_remove_one | remove_one | cs+rcs | a-정당 | - | - |
| 9 | P5_0437_missing_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |
| 10 | P5_0463_ratio_collision_collide | collide | cs+rcs+st+us+rst | a-정당 | O2_stale | - |
| 11 | P5_0623_severe_toward_consensus | toward_consensus | cs+rcs+st+us+rst | a-정당 | O2_stale | - |
| 12 | P5_0627_mixed_unit_flip | unit_flip | cs+rcs+st+us+rst | a-정당 | - | - |
| 13 | P5_0658_midband_remove_one | remove_one | cs+rcs | a-정당 | - | - |
| 14 | P5_0685_midband_toward_consensus | toward_consensus | cs+rcs | a-정당 | O2_stale | - |
| 15 | P5_0866_severe_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |
| 16 | P5_0978_mixed_unit_flip | unit_flip | cs+rcs+st+us+rst | a-정당 | - | - |
| 17 | P5_0991_midband_remove_one | remove_one | cs+rcs | a-정당 | - | - |
| 18 | P5_1010_severe_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |
| 19 | P5_1040_missing_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |
| 20 | P5_1050_mixed_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |
| 21 | P5_1068_mixed_unit_flip | unit_flip | cs+rcs+st+us+rst | a-정당 | - | - |
| 22 | P5_1172_severe_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |
| 23 | P5_1177_span_outlier_remove_one | remove_one | rcs+st+rst | a-정당 | - | - |
| 24 | P5_1184_missing_retype_grid | retype_grid | cs+rcs+st+us+rst | a-정당 | - | - |
| 25 | P5_1221_mixed_unit_flip | unit_flip | cs+rcs+st+us+rst | a-정당 | - | - |
| 26 | P5_1235_severe_toward_consensus | toward_consensus | cs+rcs+st+us+rst | a-정당 | O2_stale | - |
| 27 | P5_1246_ratio_collision_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |
| 28 | P5_1442_severe_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |
| 29 | P5_1501_span_outlier_remove_one | remove_one | rcs+st+rst | a-정당 | - | - |
| 30 | P5_1553_missing_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |
| 31 | P5_1585_midband_toward_consensus | toward_consensus | cs+rcs | a-정당 | O2_stale | - |
| 32 | P5_1590_mixed_unit_flip | unit_flip | cs+rcs+st+us+rst | a-정당 | - | - |
| 33 | P5_1604_severe_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |
| 34 | P5_1675_midband_remove_one | remove_one | cs+rcs | a-정당 | - | - |
| 35 | P5_1720_midband_remove_one | remove_one | cs+rcs | a-정당 | - | - |
| 36 | P5_1729_midband_toward_consensus | toward_consensus | cs+rcs+st+us+rst | a-정당 | O2_stale | - |
| 37 | P5_1733_missing_retype_grid | retype_grid | cs+rcs+st+us+rst | a-정당 | - | - |
| 38 | P5_1748_severe_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |
| 39 | P5_1752_mixed_unit_flip | unit_flip | cs+rcs+st+us+rst | a-정당 | - | - |
| 40 | P5_1823_missing_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |
| 41 | P5_1932_mixed_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |
| 42 | P5_1967_missing_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |
| 43 | P5_1968_mixed_unit_flip | unit_flip | cs+rcs+st+us+rst | a-정당 | - | - |
| 44 | P5_1973_severe_remove_one | remove_one | cs+rcs+st+us+rst | a-정당 | - | - |

독립 Tier-B 위반 합계: **0 / 44**. 실행자 라벨 vs 독립판정 불일치: **0**.
</details>

**결론(표적3)**: 실행자의 "44건 상승, violation 0" 주장은 **상승 축(false certification)에서는 성립**한다.
독립 판정기·live 재실행·243MB 원본 스트리밍 3중으로 교차 확증했다. 44건 어느 것도 Tier-B 잔존 상승(위반)이 아니다.
→ 본 REFUTE는 상승 축이 아니라 §3의 **과차단(손실) 축**에 근거한다.

---

## 5. 표적4 — 역방향 이동 창 (CONFIRM)

`probe5_reverse_window.py` → `probe5_results.json`.

- **severe 경계 3.5τ 포함성**: 3.5τ에서 Tier-B `severe_distance_ratio` 발화(`severe_inclusive_at_3.5: True`).
  ±1e-9, ±1e-13 미세 오프셋 스캔 정상.
- **밀집 대역 스캔 3.30τ~3.70τ (step 0.002, 201행)**: confidence 전부 **정확히 0**, unit_status 전부 NONE
  (`dense_band.all_zero: True`). 문턱 직하 조작 이득 없음.
- **4차 T_B(3.6τ→3.4τ 무조건 인증)**: v5에서 **차단**. 3.4τ가 O2 stale 한도(2.159τ)를 초과 → Tier-B.
- **역방향 이동 행렬**: 상승이 발생한 이동은 전부 사후 잔차가 **≤2.159τ**(Tier-A 대역)로 착지한 경우뿐
  (2.2→2.1, 2.16→2.15, 3.6→2.0, 3.49→2.0, 2.4→2.0 등). **Tier-B 표면에 착지한 상승은 0건**
  (`tierB_landing_rise_count: 0`). 즉 상승은 잔차가 봉인 정직-봉투 안으로 실제 이동했을 때만 허용된다 — 정당.

---

## 6. 표적5 — 자유 사냥 ≥1,000 (신규 공격 class 탐색)

`probe7_free_hunt.py` → `probe7_results.json`·`probe7_overblock_examples.json`. **1,500 케이스, seed 20260719,
결정적**. 실행자 P5에 없는 신규 교란 9종 추가(add_grid_to_residual, split_handle, weight_storm, region_scramble,
text_height_shrink, unit_downgrade, p_swap, grid_plus_clean 등). 두 축을 동시 추적:

- **AXIS-1 (false certification / 상승)**: v5 상승의 사후 표면에 독립 Tier-B가 남는가 → **0건**. 상승 10건 전부
  정당(remove_one 8, toward_consensus 2), 전부 information_limit_record. v5의 상승 축은 견고.
- **AXIS-2 (정직-추가 과차단 / 손실)**: 정직 앵커만 추가(기존 바이트 불변)했는데 손실/강등 발생 → **32건**
  (add_grid_to_residual 12, add_grid 12, grid_plus_clean 8; GRID-only 24). 대표: `tierA_ratio` 장면 + GRID 추가 →
  reference 0.771→0.0, status HIGH→NONE. §3 결함의 계통성 재확인.

신규 공격 class 탐색 결과: **상승 축의 신규 위반 class는 발견되지 않음**. 발견된 위반은 §3의 과차단 축 하나이며,
이는 §"결함 class 구분"대로 기존 4차 "GRID 과차단" class의 회귀/변주다.

---

## 7. 판정 논리 종합

- 실행자가 4차 함대의 상승 축 공격(span 충돌 희석, 중간대 희석, severe 희석, 역방향 인증)을 전부 경성 차단했고,
  44건 상승 전수·1,500 자유 사냥에서 false certification 0을 독립 확증했다 — **상승 축은 진짜로 수리됐다**(CONFIRM).
- 그러나 그 수리가 도입한 새 코드 경로(`grid_present` 봉투 판별자)가 봉인 `ratio_absent_handle_neutrality`
  (gate:true, allowed_downgrade_count:0)를 **일반적으로 위반**한다: 정직한 비율-부재 GRID 1개 추가만으로
  중간대 잔차 장면의 reference·status가 HIGH→NONE 붕괴(§3, 단일 GRID 실증·바이트 불변 증명). 1,500 사냥에서 32건 계통 발생.
- 실행자 게이트("P4 loss 0")·selftest는 잔차 없는 깨끗한-베이스만 시험해 이 구멍을 밟지 않았다 — 4차 함대의
  교훈("위반 0 = 시험 우주가 구멍을 안 밟음")이 과차단 축에서 재현된다.
- 봉인 조문 1건이라도 위반되면 REFUTE. → **REFUTE**, 결함 class = **(a) 기존 "GRID 과차단" class의 회귀/변주**
  (신규 기제, 연성→경성 악화, 신규 class 아님).

예상 반론과 응답:
- "no_loss_rule은 P4(깨끗한 베이스)만의 규칙이다" — 조문 `operation`은 일반이고 title은 "GRID handles are neutral
  to ratio trust"로 무제한이다. `mandatory_regression`은 최소 인스턴스 명시일 뿐 범위 상한 아님. `ratio_path_rule`
  ("비율-부재 handle은 ratio-trust에 아무 기여도 안 함")과도 정면 충돌.
- "GRID가 있으면 중간대 잔차는 type-to-grid 위조라 더 의심스러우니 경성 차단이 옳다" — 봉인 Tier-A 정의는
  O2_stale(≤2.159τ) 허용을 GRID 부재로 조건화하지 **않는다**(closed_world_rule + O2_stale 봉투 항목 어디에도 GRID 조건 없음).
  GRID 존재가 봉투를 축소한다는 규칙은 봉인되지 않은 구현 선택이며, 그 부작용이 neutrality gate 위반이다. 실제로 v5는
  같은 잔차를 GRID 없으면 정직 Tier-A로 상승까지 허용(§4 44-표)하므로, GRID 유무로 정반대 판정을 내리는 것은 자기 모순.

---

## 8. 검증하지 못한 것 (범위 명시)

- 400장면 replay/코호트 수치 재계산·증인 레코드 개별 서사 타당성·봉인 사슬 git 증인은 본 좌석(공식·희석·44상승) 범위 밖
  — lens1/lens3/seat4 관할. 본 판정은 그것들의 성부와 독립.
- §3 위반의 심각도 등급(연성→경성 악화)은 실증했으나, 오케스트레이터가 neutrality 조문을 "P4 인스턴스로 축소 해석"할
  여지를 원천 봉쇄하려면 조문 문언 자체를 다투어야 한다 — 본 좌석은 문언 일반성 + 코드 기제 + 자기모순 3중으로 뒷받침했다.
- 44건 상승의 개별 honest-witness 서사 문자열 심사는 lens1 관할. 본 좌석은 사후 표면의 Tier-B 부재만 독립 심판했다.

---

## 9. 재현 절차

Python 3.12 (stdlib+numpy). 전부 결정적(seed 20260719), 원본 산출물 무변경, git 미사용, 서브에이전트 미사용.

```
set PY=C:\Users\PAUL\AppData\Local\Programs\Python\Python312\python.exe
%PY% D:\runs\e2_program\chainverify_L1f\lens2_work\probe0_introspect.py         # 상속 기계 실사
%PY% D:\runs\e2_program\chainverify_L1f\lens2_work\probe1_formula_audit.py       # 표적1 공식 감사
%PY% D:\runs\e2_program\chainverify_L1f\lens2_work\probe2_regressions.py         # 표적2a 4차 회귀 (N≤400)
%PY% D:\runs\e2_program\chainverify_L1f\lens2_work\probe3_dilution_variants.py   # 표적2b 신규 35변주
%PY% D:\runs\e2_program\chainverify_L1f\lens2_work\probe3b_inspect.py            # V07/V11/V34 포렌식
%PY% D:\runs\e2_program\chainverify_L1f\lens2_work\probe6_grid_neutrality_break.py  # §3 핵심 위반 실증
%PY% D:\runs\e2_program\chainverify_L1f\lens2_work\probe5_reverse_window.py      # 표적4 역방향 창
%PY% D:\runs\e2_program\chainverify_L1f\lens2_work\probe4_rise_adjudication.py   # 표적3 44+90 판별
%PY% D:\runs\e2_program\chainverify_L1f\lens2_work\probe4b_validate_and_stream.py  # 판정기 검증 + 243MB 스트림
%PY% D:\runs\e2_program\chainverify_L1f\lens2_work\probe7_free_hunt.py           # 표적5 자유 사냥 1500
%PY% D:\runs\e2_program\chainverify_L1f\lens2_work\probe8_make_44_md.py          # 44표 렌더
```

산출물 (`lens2_work\`): probe1_results.json · probe2_results.json · probe3_results.json · probe3b_results.json ·
probe4_results.json · probe4_44_table.json · probe4_44_table.md · probe4b_results.json · probe5_results.json ·
probe6_results.json · probe7_results.json · probe7_overblock_examples.json · probe0_introspect.out.txt.

핵심 위반 재현 최소 코드 (probe6 Case A):
```
A,B,C = clean DIM (span 1000, display 2500, MM);  X = DIM span 1000 display 2500·exp(1.0·τ)  # 1.0τ ratio 잔차
before = [A,B,C,X]                       -> reference 0.9071, status HIGH  (X = Tier-A O2_stale)
after  = [A,B,C,X, GRID(span 1000, display=None)]  -> reference 0.0, status NONE  (X = Tier-B, 기존 4개 바이트 불변)
```

VERDICT: **REFUTE** — 결함 class = 기존 4차 "GRID 과차단(ratio_absent_handle_neutrality)" class의 회귀/변주
(신규 내부 기제, 연성→경성 악화). 봉인 gate 위반 실증으로 루프 종결(PASS) 불가.
