# lens1_witness.md — 증인 분류기 적대 검증 (4차 함대, L1e)

- 좌석: lens1 (증인 분류기 적대 검증 시야)
- 검증 대상: 오케스트레이터 주장 중 ② "잔존 상승(stale 36·suffix 66·type_to_grid 210 + 속성/함대
  계열, 필드 이벤트 총 1,767)은 전건 자동 증인 분류로 관측-동치 정직 증인이 제시된
  information_limit_record이고 violation 0·미분류 0"
- 방법: 모든 기존 산출물 READ-ONLY. 재계산·프로브는 전부 `chainverify_L1e\lens1_work\` 안에서만
  수행. git·서브에이전트 미사용. 분류기 코드(`loop_l1e.py:454 classify_upward`,
  `feyerabend_c1_v4.py:782 suspicion_analysis`)를 정독한 뒤, (a) 361건 동결 표면을 **추정기
  코드에 기대지 않는 자체 검출기**로 전수 재검, (b) 정직 코퍼스 400장면으로 "정직 도시가 생산
  가능한 표면"의 실측 봉투를 캘리브레이션, (c) 진짜 `classify_upward`를 임포트해 라이브 반례를
  주입했다.

## 검증 자산 (전부 lens1_work\, 재실행 가능)

| 파일 | 역할 |
|---|---|
| `probe_a_reexam.py` → `lens1_probe_a_results.json` | 361건 전수: 무결성 재계산 + 독립 의심 검출기 |
| `probe_a2_honest_envelope.py` → `lens1_probe_a2_results.json` | 정직 코퍼스 400장면(l1b 200 + c0 200) 봉투 실측 + W000002 원문 덤프 |
| `probe_b_live.py` → `lens1_probe_b_results.json` | 라이브 분류기 프로브 B0~B7 |
| `probe_b8_violation_reachability.py` → `lens1_probe_b8_results.json` | violation 분기 도달 가능성 B8 |

실행: `python probe_a_reexam.py` 등 (Python 3.12, numpy/openpyxl 필요 — loop_l1e 임포트용).

## ① 361건 동결 사후 표면 독립 재검

**무결성 (전수 PASS)** — 361건 각각에 대해: post/witness 직렬화의 sha256 재계산이 저장값과
일치, witness 직렬화 == post 직렬화 (byte-equal, 361/361), 동결 표면을 파싱해
`V4.suspicion_analysis`를 재실행한 결과가 저장된 `residual_suspicion`과 일치(카운트·다이제스트),
파일 전체 `classifications_digest` 재계산 일치. `manual_suppression_used` 전건 false, 미분류 0.
수치 주장도 성립: 361건 = search 312(stale **36**·suffix **66**·type_to_grid **210**) +
property 43 + third_fleet 5 + fleet_core 1, 필드 이벤트 합 **1,767**.

**독립 검출기 (자체 구현: 가시 ratio outlier·핸들 충돌·혼합 공간·display-잔존·선언 span↔기하
불일치·GRID-display 잔존·중복)** — 361건 중:

- 359건: 잔존 신호 완전 0. 표면 내부 비율 이탈 0 (stale ×1.25는 상태 격자 {2.0, 2.5, 3.125}의
  이웃 값에 **정확히 착지**하는 산술 — 2.0×1.25=2.5, 2.5×1.25=3.125 — 임이 표면에서 확인됨).
- 2건(W000003 CE-E stale 0.93τ, W000004 CE-F t2g 0.5τ): 1τ 미만의 비율 잔차. **봉인된 정직
  예시 O2**(`loop_l1e.py` `O2_stale_label`: 250·250·250·225 = 내장 2.16τ stale, prereg
  `legitimate_scene_no_loss`가 강등 금지로 보호)가 이보다 큰 이탈을 정직으로 봉인했으므로, 이 2건의
  정직 증인 주장은 독립 선례가 있다. 이의 없음.
- 1τ~3.5τ 창(window)의 가시 outlier가 잔존한 표면: **0건** (이 잠재 맹점은 실제 361건에서는
  발현되지 않았다).
- **1건 발견 — W000002 (third_fleet, CE-C, geometry_ratio_break)**: 아래 상술.

### 발견 F1 — W000002: 잔존 의심 신호를 가진 표면이 information_limit_record로 분류됨

동결 표면 원문(4앵커, `lens1_probe_a2_results.json`에 전문 보존):

```
CEC_G0/G1/G2: DIM, display 250.0 MM, p0→p1 길이 100, raw_span 100.0   (ratio 2.5)
CEC_OUT:      DIM, display 750.0 MM, p0 [10000,10000] p1 [10300,10000] (기하 길이 300),
              raw_span 100.0   ← 선언 span이 기하와 3× 불일치
```

- 교란 내용: geometry_ratio_break가 CEC_OUT의 p1만 3배로 늘림. 비율은 750/300=2.5로 클러스터에
  착지(세탁)했지만, **선언 `raw_span` 필드는 100.0으로 남아 교란의 직접 흔적이 표면에 잔존**한다.
- 이 레코드는 5개 추적 필드 전부 상승(confidence 0→1.0, reference 0→0.5625, status NONE→LOW,
  unit_status NONE→**HIGH**, reference NONE→LOW)한 최대급 상승이며,
  `HONEST::60bdb26c…` 증인 제시 + `information_limit_record`로 분류·집계됐다.
- **정직 생산 불가능성 (실측)**: 정직 코퍼스 400장면(앵커 2,008개)과 봉인 정직 예시(O1·O2) 및 전
  픽스처 생성기에서 선언 raw_span ≠ 기하 span 불일치는 **0건** — 정직 도시 생성계는 항상
  raw_span == |p1−p0|를 만족한다(비율 내부 이탈도 정직 코퍼스 최대 1.46e-13τ). O2가 정직으로
  봉인한 것은 display 쪽 stale이지 기하-속성 내부 모순이 아니다.
- **계약 귀결**: prereg `observation_equivalence`는 "estimator input surface의 **모든 필드**
  동일"을 요구하고, `raw_span`은 Phase B가 스스로 선언한 표면 필드다(`ESTIMATOR_INPUT_FIELDS`,
  동결 직렬화에 포함). 따라서 이 표면과 관측-동치이면서 정직인 장면은 존재할 수 없다 — 정직
  장면이라면 raw_span=300이어야 하고 그러면 동치가 깨진다. prereg
  `witness_adjudication_procedure` 6항: "residual ratio outliers, handle collisions,
  mixed-space traces, **or other surviving suspicious signals are explicit violation
  evidence**" — 이 상승은 violation으로 분류됐어야 한다. violation 게이트는
  `allowed_count: 0`이다.
- **은폐성**: REPORT.md에서 `raw_span` 언급 0회, W000002는 증인 테이블의 한 행으로만 존재.
  rationale은 검사한 5종 레지스트리("no residual ratio, mixed-space, missing-ratio, or
  span-conflict signal remains")만 나열하며 미검사 신호의 부재를 함의한다.

원인은 구조적이다: `suspicion_analysis`는 `prepare_anchors`를 거치는데, prepare가 선언
raw_span을 **기하 재계산 값으로 대체**하므로(`feyerabend_c1.py:187` 계열) 선언↔기하 불일치는 5종
레지스트리 어디에도 잡히지 않는다. 동결 표면에는 선언 값이 그대로 실리므로 "표면에는 보이지만
분류기는 못 보는" 필드가 된다.

## ② 의심 잔존 상승 장면 라이브 주입 (진짜 classify_upward 사용)

- **B0 (재현)**: 기록된 CE-C 전이를 픽스처+시드로 라이브 재구성 — 표면 직렬화가 기록과
  byte-일치, info_limit 재현, 불일치(100 vs 300) 잔존 확인.
- **B1~B4 (canonical 의심 4종: severe outlier ≥3.5τ·핸들 충돌·혼합 공간·display 결측)**:
  4종 모두 **상승 자체가 발생하지 않음**. severe/구조 의심이 서면 v4가 점수 0·`n_independent`
  0으로 강제해 상태가 NONE으로 붕괴하므로(`feyerabend_c1_v4.py:330-337`) 상승이 분류기에 도달하기
  전에 소멸한다. 즉 이 계열에서 "violation 0"은 분류기의 판별 성과가 아니라 **도달 불가능성의
  산물**이다.
- **B8 (violation 도달 가능성)**: ratio 표면을 깨끗하게 유지한 채 span_conflict만 잔존시키면
  5필드 상승과 의심이 공존하고, 분류기가 실제로 `violation`을 산출했다(2변형 모두,
  `residual_suspicion_count=1`). **분류기는 항진식이 아니다** — violation 분기는 살아 있는
  코드다. (selftest 술어의 반례 실행 주장과 정합.)
- **B5 (맹점의 일반화 — 결정타)**: CE-C와 무관한 최소 구성 — 깨끗한 앵커 2개 + 위조 앵커
  1개(선언 raw_span 100, 기하 300, display 750 → 비율 2.5로 착지) — 를 주입하자 5필드 전부
  상승(**unit_status NONE→HIGH, confidence 0→1.0, 추정치 2.5 확정**)했고, suspicion 0으로
  `HONEST::` 증인과 함께 **information_limit_record** 인증을 받았다. 표면에 3× 기하-속성 모순이
  실린 위조 장면이 최고 신뢰 인증 + "정직 증인" 라벨을 동시에 획득한다. W000002는 고립 사고가
  아니라 재현 가능한 일반 경로다.
- **B6 (창 관찰)**: 2.6τ 가시 outlier가 잔존한 채 confidence 상승 → info_limit. O2 선례(2.16τ
  정직 stale 봉인) 때문에 이것 자체를 위반 은폐로 판정하지는 않는다. 다만 severe 경계(3.5τ)
  미만의 잔존 outlier 동반 상승이 무조건 정직 인증되는 창이 열려 있음을 기록한다 — 이번 361건에는
  미발현.

## ③ "정직 증인" 정의의 순환성 검사

- **구조적 사실**: 증인은 post 표면 직렬화의 JSON 왕복 복사본이다(`loop_l1e.py:473`). 361건
  전수에서 증인 직렬화 == post 직렬화 (byte-equal). 따라서 "관측-동치" 검사(`equivalence`)는
  구성상 항상 참인 자명식이고, 분류의 실질 하중은 전부 `suspicion_analysis == 0` 판정
  (`legitimate`)에 있다.
- **이력 독립성 (B7)**: 교란 이력 필드(diagnostic_mutation·text_override)를 넣고 빼도 표면
  다이제스트·라벨이 동일 — prereg의 "not justified by hidden perturbation history"는 기계적으로
  성립한다.
- **독립 정당성 판정**: 레지스트리 5종이 커버하는 신호에 대해서는 증인 주장이 독립 선례를
  갖는다 — 봉인 정직 예시 O1(혼합 단위 정직)·O2(stale 라벨 정직)가 suffix(단위 미상 정직
  도면)·stale 착지(균일 비율 정직 도면)·t2g(그리드 실존 도면) 증인 가족의 실존을 뒷받침하고, 내
  독립 검출기가 359건 표면의 청정성을 재확인했다. **그러나 W000002/B5 계열에서 순환성이
  실증된다**: 정직 생성계가 결코 만들지 않는 흔적(선언↔기하 3× 모순)이 표면에 남아 있는데도 "정직
  증인 제시"가 선언되며, 그 근거는 오직 "레지스트리가 그 필드를 검사하지 않는다"는 사실뿐이다. 이
  경우 증인의 정직성은 독립 정당성이 아니라 **분류기 맹점의 재서술**이다.

## 반론 검토

1. *"raw_span은 추정기가 실사용하지 않으므로(기하 재계산) 의심 신호가 아니다."* — 그 필드는
   Phase B 스스로 추정기 입력 표면으로 선언·동결·공개한 필드이고, prereg 동치 정의는 "모든 필드
   동일 + 어떤 비교 표면도 생략·정규화 금지"를 명시한다. 포함시켰으면 판정해야 한다. 또한 실측상
   정직 코퍼스에 불일치가 0건이므로 이 신호는 교란 이력의 유일 잔존 지표다.
2. *"W000002는 third_fleet 회귀라 '72,396 전이 전수 상승 0' 주장(①)과 무관하다."* — 맞다. ①은
   건드리지 않는다. 그러나 검증 대상 주장 ②는 "잔존 상승 **전건**"에 대한 것이고 W000002는 그
   361건에 포함되어 violation 0 집계의 일부다.
3. *"우연한 착지(시드 9의 ×3 선택)는 코너케이스다."* — 결정론적 시드로 이미 발생·기록·집계됐고,
   violation 게이트는 allowed_count 0이다. 그리고 B5가 이 경로의 일반 재현성을 보였다.

## 판정 근거 요약

- 성립: 수치 전부(361·1,767·36/66/210·미분류 0·수동 억제 0), 무결성 전수, 359/361 표면 청정,
  2건은 봉인 정직 예시 O2 선례 내, violation 분기 실행 가능(B8), 이력 독립성(B7).
- 불성립: **"전건에 관측-동치 정직 증인이 제시됐다"와 "violation 0"** — W000002는 잔존 의심
  신호(선언 raw_span↔기하 3× 불일치, 정직 생산 불가능·실측 0/400)를 가진 표면이
  information_limit_record로 분류된 사례다. 좌석 계약 ①의 발견 조건(발견=위반 은폐)에
  해당하며, prereg 판정절차 6항에 따라 violation으로 분류됐어야 하므로 violation 0 게이트
  (allowed_count 0)가 깨진다. 라이브 프로브 B5는 동일 맹점으로 위조 표면이 unit_status HIGH +
  "정직 증인" 인증을 동시 획득함을 보였다.

VERDICT: REFUTE
