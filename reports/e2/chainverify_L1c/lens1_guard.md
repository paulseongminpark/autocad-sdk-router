# lens1 — 가드 정합성·과차단 검증 (chainverify_L1c)

- 좌석: lens1 (가드 정합성·과차단 시야) · 대상 주장: L1c 루프 종결 (task.md)
- 방법: 모든 기존 산출물 READ-ONLY. 재계산·프로브는 `D:\runs\e2_program\chainverify_L1c\lens1_work\` 에서만 수행.
  하니스 `lens1_work\probe_guard.py`, 원시 결과 `lens1_work\probe_results.json`.
  재현: `python lens1_work\probe_guard.py` (Python 3.12.10, numpy 있음). git 미사용, 서브에이전트 미사용.
- 판정 기준: 검증 대상 주장 문언 + **L1c 자신의 봉인 밴드** `prereg.json` `perturbation_monotonicity`
  (`scope: "any perturbation"`, `allowed_upward_transition_count: 0`, fields = confidence_score·status·unit_status).

## 0. 사슬 무결성 스팟체크 (내 몫) — PASS

- 원본 추정기 두 사본 sha256 동일 (v2가 import하는 runs 사본 ↔ repo 봉인 사본):
  `D:\runs\e2_program\cells\feyerabend_c1\feyerabend_c1.py` = `D:\dev\99_tools\autocad-sdk-router\tools\e2\cells\feyerabend_c1.py`
  = `633c5ee154eb3b869dba8361de2cbee9808627e0f192f8c2d29a4b05df2c4d51` — 1차 함대 lens2_stats.md 47행이 인용한 봉인 sha와 일치. L1c는 원본 소스를 건드리지 않았다.
- `feyerabend_c1_v2.py` sha `5f6f2eee4810ad59863ce1c3e6b206d0a9d1818c0c0a32684194820b1aa73a0f`, `prereg.json` sha `30f6d0f7db9c5a9531183ec317936d4c5d3dda98139299d8ff43aeee68183fa8` — L1c REPORT.md 126·128행 기재값과 일치.

## 1. 가드 설계 정독 (feyerabend_c1_v2.py 164–197행)

가드 술어: anchor가 `carries_ratio`(anchor_type ∈ {DIM, TEXT} ∧ display_value > 0)이고 그 **handle 문자열**이
`ratio_inlier_handles` 집합에 없으면 reference 합의에서 격리(`reason: ratio_space_outlier_guard`). GRID와
ratio 없는 anchor는 봉인 경로 유지. 정합성 소견:

- **G1 (구조): 가드의 identity 키는 handle 문자열이다** (185행 `str(anchor["handle"]) not in ratio_inlier_handles`).
  `prepare_anchors`는 handle 유일성을 강제하지 않는다(중복 제거 키는 기하+표시값 `canonical_anchor_key`, 170–184행;
  handle 미포함). 따라서 ratio-outlier가 inlier와 handle을 공유하면 가드를 통과한다 — §4 B3에서 실측 성립.
  도시에 §2.2.4는 "독립 anchor는 서로 다른 source handle"을 봉인했으나 구현의 `n_independent`는 record 수를
  세므로(원본 315–330행, v2 재사용) 동일-handle 2건이 독립 2로 계산된다(B3 실측 ref_n 3→4).
- **G2 (사소): `ratio_class: "no_selected_ratio_mode"` 분기(190–194행)는 도달 불능.** `maximum_consensus`는
  비어있지 않은 입력에서 항상 mode를 반환하고(원본 275–312행: `if not records: return None` 외 반환 경로 전부 mode),
  `carries_ratio` 술어는 ratio_records 편입 조건과 동일하므로, carries_ratio anchor가 존재하면 합의도 존재한다.
  전 프로브 런타임 스캔에서도 해당 ratio_class 0건. 무해하나 가드 술어가 완전 분석되지 않았다는 신호.
- **G3 (설계 충돌): 가드는 도시에 §2.4의 reference span 수집 규칙에 새 제외를 추가한다.** §2.4 1단계는 "유효
  DIM/TEXT의 raw geometric span"을 label-free 기하 증거로 수집하고 제외는 annotation-scale(2단계)·복제(3단계)뿐이다.
  §2.3 218행은 ratio 없이도 span만으로 reference_status=HIGH가 될 수 있음을 명시한다(즉 span 증거는 라벨 신뢰성과
  독립). 가드는 span 채택을 라벨(ratio) 정합에 결합시킨다. L1c REPORT 19행 "2.4의 … 규칙을 유지했다"는 문언과
  달리 이는 §2.4 수집 규칙의 변경이다(수리 루프이므로 변경 자체는 허용 사안이나, "유지" 서술은 부정확).

## 2. 통제 프로브 P0 — 하니스 유효성 (L1c 표 재현)

봉인 corruption `single_outlier`를 반례 장면 `scene_001_k1000.json`(DIM 3개: span 1e6, display 1000 MM,
span/text_height=10.0, ref_n=3·bins=3·ref_conf=0.6)에 적용:

| 추정기 | phase | conf | status | unit | ref | ref_conf | ref_n | ref_bins | guarded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| original | before | 0.6 | LOW | LOW | LOW | 0.6 | 3 | 3 | – |
| original | after | 0.45 | **HIGH** | LOW | **HIGH** | 0.8 | 4 | 4 | – |
| C1v4 | before | 0.6 | LOW | LOW | LOW | 0.6 | 3 | 3 | 0 |
| C1v4 | after | 0.45 | LOW | LOW | LOW | 0.6 | 3 | 3 | 1 |

L1c REPORT 34–42행의 라이브 반례 회귀 표와 **전 수치 일치** — 주장 ①의 후반부(원본 상승 재현·C1v4 상승 0,
그 corruption에 한해)와 ② ③의 기록 자체는 내 시야에서 진본이다. 이하 프로브는 이 유효한 하니스로 실행됐다.

## 3. 과차단 실측 — 정당한 앵커의 격리와 coverage 손실

L1b replay 불변(주장 ③)은 그 모집단의 무해 증거일 뿐이다. 모집단 밖 정당 입력 3종 실측:

| 프로브 | 입력 성격 | original | C1v4 | 격리 수 |
| --- | --- | --- | --- | --- |
| O1 혼합 단위 | **무교란** 정직 DIM 5개, span 동일, 표기만 250 MM×3 / 0.25 M×2 (이중 치수) | status **HIGH** (ref_n=5, ref_conf=1.0) | status **LOW** (ref_n=3, ref_conf=0.6) | 2 |
| O2 stale 라벨 | 정직한 기하 4개, 라벨 1개만 낡음(225 vs 참 250) | status **HIGH** (ref_n=4, 0.8) | status **LOW** (ref_n=3, 0.6) | 1 |
| O3 mode 탈취 | 진짜 3 + 위조(×10) 4 | ref HIGH (진짜+위조 7 inlier) | ref HIGH — **inlier가 위조 4개뿐**, 진짜 3개 전원 격리 | 3 |

- O1: corruption이 전혀 없는 장면에서 v2가 원본이 주던 status=HIGH를 잃는다. 물리적으로 동일한 치수의 단위별
  병기(dual dimensioning)는 raw-ratio 공간에서 두 mode로 갈라지고, 진 mode 아닌 쪽 앵커의 **정직한 span**이
  격리된다. 도시에 §2.3 205행의 z^mm(단위 정규화) 합의 의도와 달리 구현 ratio 공간은 단위 미정규화라 이 균열이
  구조적이다.
- O2: span 증거를 라벨 정합에 결합시킨 대가 — 낡은 라벨 하나가 정직한 기하 1개분의 reference 지지를 삭제해
  장면 status가 강등된다(원본 설계는 label-free span으로 이를 견뎠다 — §2.4 §2.3 218행).
- O3: ratio mode가 위조에 탈취되면(가중 4>3) 가드는 **진짜 앵커를 격리하고 위조만으로 reference HIGH를 구성**한다
  (`reference_inlier_handles = [FAKE_0..3]`, guarded=3). scale 오답(25.0 vs 참 2.5)은 양쪽 공통이지만, v2의
  provenance는 위조 전용 지지라는 질적으로 더 나쁜 상태가 된다.

## 4. 가드 우회 실측 — v2에서의 상승 재현 (좌석 계약의 핵심)

전부 반례 장면 + 봉인 `single_outlier` 클론의 **최소 변형**이다. 4종 모두 C1v4에서 상승 실측:

| 프로브 | 봉인 corruption 대비 변형 | original after | C1v4 after | C1v4 상승 필드 | guarded |
| --- | --- | --- | --- | --- | --- |
| B2 display 제거 | 클론의 display_value=None (**정보가 더 적음**) | status HIGH, ref 0.8/n4/bins4 | **status HIGH, ref 0.8/n4/bins4** | **status** (LOW→HIGH) | 0 |
| B3 handle 충돌 | 클론 handle 재명명 생략(원 handle 유지), display ×10 그대로 | status HIGH | **status HIGH** — ratio-outlier인데 통과 (G1) | **status** | 0 |
| B1 GRID 위장 | 클론 type=GRID, display 제거 (유령 그리드선) | status HIGH | **status HIGH** | **status** | 0 |
| B4 ratio 일치 클론 | 클론 display를 원값으로(위치만 위조) | conf 0.8, unit HIGH, status HIGH | **conf 0.6→0.8, unit LOW→HIGH, status LOW→HIGH** | **confidence_score·status·unit_status 전부** | 0 |

수치 전문(각 프로브 C1v4 before는 P0와 동일: conf 0.6, status/unit/ref 전부 LOW, ref 0.6/n3/bins3):

- B2: C1v4 after conf 0.6(불변), status LOW→**HIGH**, ref LOW→**HIGH**, ref_conf 0.6→0.8, ref_n 3→4, ref_bins 3→4, guarded 0. 봉인 corruption에서 위조 앵커의 display만 지운 — 엄격히 더 열화된 — 입력이 원본과 **동일한 결함 발현**을 v2에서 일으킨다. 심지어 봉인판(conf 0.45)과 달리 ratio 흔적도 안 남긴다(conf 0.6 유지).
- B3: display ×10 ratio-outlier 그 자체가 handle 문자열 충돌만으로 가드를 통과(guarded=0), ref 0.6→0.8, status LOW→HIGH.
- B1: GRID 경로는 가드 면제 설계라 span-inlier 위조 지지가 그대로 유입, status LOW→HIGH.
- B4: 위치만 위조한 ratio-일치 클론이 **prereg 봉인 필드 3종 전부**를 올린다(0.6→0.8, LOW→HIGH ×2). 양 추정기 공통이지만 봉인 밴드는 추정기 v4의 수리 완결 기준이다.

**대조 — v2 자체 300종 속성 시험이 이를 못 본 이유**: 시험의 교란 문법(feyerabend_c1_v2.py 551–609행) 6 family는
display 제거·handle 충돌·type 변경을 생성하지 않고, outlier_clone은 항상 display를 1.25–25배로 곱하며 handle을
재명명한다(578–579행). exact_duplicate는 기하 동일 클론이라 `prepare_anchors` dedupe로 무효화된다. 즉 속성 시험의
생성 문법 사각이 가드의 사각과 정확히 겹친다. 300/300 PASS(REPORT 44–49행)는 진본이나 위 경로들을 표본화한 적이 없다.

## 5. 판정 논거

1. 검증 대상 주장 ①은 결함을 "**span-inlier outlier의 reference 합의 부양**"으로 정의하고 이것이 "신규 가드로
   수리됐다"고 한다. B1·B2·B3의 위조 앵커는 전부 span-inlier outlier이고, 전부 reference 합의(n_independent·
   spatial bins)를 부양해 C1v4의 status를 LOW→HIGH로 올렸다(§4 실측). 수리된 것은 "ratio 보유 + handle 유일"
   부분집합뿐이며, 그중 B2·B3은 봉인 corruption에서 필드 하나를 지우거나 재명명 한 줄을 생략한 최소 변형이다.
   주장 문언의 결함은 수리되지 않았다.
2. L1c의 봉인 기준 자체가 위반된다: prereg.json `perturbation_monotonicity`는 scope **"any perturbation"**,
   허용 상승 **0**을 봉인했다(fields: confidence_score·status·unit_status). B1·B2·B3은 status 상승 각 1건,
   B4는 세 필드 전부 상승 — 라이브 실측. "루프 종결"은 루프 자신의 봉인 수용 기준에 반한다.
3. 과차단 방향도 실재한다: 무교란 정직 장면(O1)에서 원본 대비 status HIGH→LOW의 coverage 손실, 낡은 라벨
   1개로 인한 강등(O2), mode 탈취 시 진짜 격리·위조 전용 지지(O3). L1b replay 불변(③)은 이 형태의 입력이
   모집단에 없어서 성립하는 무해 증거일 뿐임이 실측으로 확정됐다.
4. 내 시야에서 진본으로 확인된 것: 라이브 회귀 표(① 후반)·원본 소스 무수정·기재 sha 일치(§0·§2). ②·④는
   타 좌석 시야이며 내 증거와 모순되지 않는다. 그러나 종결 주장은 ①의 문언과 봉인 밴드에서 무너진다.
5. REPORT 133행 미해결 항목("ratio 신호가 없는 GRID/reference-only anchor …")은 셀의 정직한 한계 고지이나,
   B2·B3이 보이듯 잔존 경로는 "식별 불능의 인식론적 잔여"가 아니라 봉인 corruption의 한 글자 변형으로 재개방되는
   동일 결함이다. 종결 선언은 이 고지 범위를 넘는다.

## 6. 산출물

- 본 보고서: `D:\runs\e2_program\chainverify_L1c\lens1_guard.md`
- 프로브 하니스·원시 수치: `lens1_work\probe_guard.py` · `lens1_work\probe_results.json`

VERDICT: REFUTE
