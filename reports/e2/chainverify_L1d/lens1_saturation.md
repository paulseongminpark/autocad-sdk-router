# lens1 — 포화-은폐 적대 탐색 (chainverify_L1d)

- 좌석: lens1 (포화-은폐 적대 탐색) · 대상 주장: L1d 루프 종결 (task.md)
- 방법: 모든 기존 산출물 READ-ONLY. 재계산·프로브는 `D:\runs\e2_program\chainverify_L1d\lens1_work\` 에서만.
  하니스 `lens1_work\probe_saturation.py`, 원시 수치 `lens1_work\probe_results.json`.
  재현: `python lens1_work\probe_saturation.py` (Python 3.12.10). git 미사용, 서브에이전트 미사용, CAD·test 미접근.
- 판정 기준: 주장 문언 ①③ + **L1d 자신의 봉인 밴드** `prereg.json` `perturbation_monotonicity`
  (scope: designated 6 families + fleet-discovered classes, `allowed_upward_transition_count: 0`,
  fields = 추적 5종, status_order NONE<LOW<HIGH, 면제는 B4 단 하나).

## 0. 무결성·재현 확인

- import 소스 sha256: v3 `ba7adddb508f…` = REPORT 369행 기재값, 원본 `633c5ee154eb…`·v2 `5f6f2eee4810…`
  = 2차 함대 lens1_guard.md §0 기재값. 소스 무수정 상태에서 프로브했다.
- 600종 속성 시험을 동일 시드로 in-process 재실행: upward 전 필드 0, cases digest
  `f03048a56f3f…` = REPORT 72행과 **일치**. 내 계측 루프(동일 rng 스트림 복제)도 동일 digest 재현
  → 이하의 표본 해부는 실제 봉인 런과 케이스 단위로 동일하다. [B1/B2, probe_results.json]

## 1. 포화 실측 — 공식 프로브 전 계열은 v3에서 천장에서 시작한다

`fleet_probe_results.json`에서 직접 재확인한 v3 before 상태:

| probe | conf | ref_conf | status | unit | ref |
| --- | --- | --- | --- | --- | --- |
| P0·B1·B2·B3·B4(각각) | 1.0 | 1.0 | HIGH | HIGH | HIGH |
| 분모청소 스윕 54종 전부 | 1.0 | 0.0 | LOW | HIGH | LOW |

- P0·B1~B4: **추적 5필드 전부가 절대 최대값에서 시작** — `_increases`는 어떤 after에 대해서도
  참이 될 수 없다. 이 프로브들에서 "상승 0"(주장 ①)은 v3의 성질과 무관하게 산술적으로 보장된
  결과다. 2차 함대에서 B1~B3가 v2를 REFUTE한 힘은 before가 LOW(conf 0.6, 전 status LOW)였다는
  데서 나왔다(lens1_guard.md §4). v3는 같은 장면을 만점 처리하므로 같은 프로브의 판별력이 0이 됐다.
- 54-스윕: ratio 측(conf·unit)은 천장, reference 측은 0.0/LOW로 시작하나 스윕의 교란(display
  ×factor)은 span을 건드리지 않아 span multi-mode로 0이 된 ref 게이트를 들어올릴 수 없는 형태 —
  어느 방향으로도 판별력 없음.
- 유일하게 천장 아래에서 시작한 공식 프로브는 B4_information_limit_two_to_three(conf 1.0,
  status/unit LOW)뿐이고, 그것은 실제로 **3필드가 올랐으며**(LOW→HIGH ×3) prereg가 면제한 유일한
  class다. 즉 공식 계열 중 headroom이 있던 단 하나의 시작점에서는 상승이 실측됐다.

## 2. 600종 속성 시험 — pool×문법이 구조적으로 상승-불능임을 전수로 확인

400 replay 장면의 v3 census [A]:

| cohort | all5 천장 | conf<1 | ref_conf<1 | status≠H | unit≠H | ref≠H | ratio outlier 보유 장면 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| l1b 200 | 0 | 0 | 160 | 200 | 40 | 200 | **0** |
| c1_original 200 | 100 | 0 | 100 | 100 | 0 | 100 | **0** |

- 실제 600 추첨 중 before가 5필드 전-천장인 케이스 164, headroom 보유 436 [B2] — 그러나 그
  headroom은 전부 **봉인 문법이 닿을 수 없는 형태**다: (i) span multi-mode로 ref 게이트가 0인
  장면(160+α)은 ratio-측 단일 record 변이로 복구 불능, (ii) n=2 장면의 unit/ref LOW는 "일관된
  새 handle 추가"로만 오르는데 9-family 중 그런 변이는 없다(그건 정확히 B4-면제 경로다),
  (iii) **pool 400장면에 ratio outlier·혼합 공간·handle 충돌·intra-tolerance spread가 단 하나도
  없어** 청소·수리형 상승 메커니즘의 표적 자체가 부재하다.
- 확인 실측: 봉인 문법의 이산 추첨 공간을 pool 전 장면에 전수 적용(**19,028 draw**: family별
  index 전수 × geometry 4-factor 전수 × stale 수리-윈도 해석적 탐색 포함) → 상승 **0**.
  stale 수리-윈도는 pool 전체에서 **0개 존재**(outlier가 없으니 [1.25,25]와 교차하는 윈도 자체가
  없다). 신선한 10개 시드 × 600 = 6,000 재추첨 → 상승 **0** [B3/B4].
- 따라서 ③의 "600종 상승 0"은 시드 운이 아니라 **pool-조건부 구조적 항진**이다. 진본이지만,
  LOW-시작 단조성에 대한 증거력이 없다. 2차 함대가 v2에서 확정한 실패 형태 — "속성 시험의 생성
  문법 사각이 결함의 사각과 정확히 겹친다"(lens1_guard.md §4 대조) — 가 L1d에서는 **표본 pool의
  사각**으로 자리만 옮겨 재현됐다.

## 3. LOW-시작 반례 실측 — 봉인 family 그대로, 합법 장면에서 상승한다

전부 `randomized_corruption`(봉인 문법 코드 그대로)을 실제 `random.Random(seed)`로 구동, 장면은
셀 자신의 프로브 생성기 `_make_anchor`로 구성(O1·O2·B4 장면과 동일한 합법성). [C, probe_results.json]

| 반례 | family (봉인 class) | draw당 상승 확률 (실측) | 상승 필드 |
| --- | --- | --- | --- |
| CE-A: 3×MM(250/100)+2×무단위(250/100) | suffix_removal | **1.0** (결정론, n=100) | **5필드 전부**: conf 0→1.0 · ref_conf 0.6→1.0 · status/unit/ref 전부 LOW→HIGH |
| CE-B: 3 정상 + ×10 outlier 1 | type_to_grid | 0.254 (n=4000) | conf 0→1.0 · unit LOW→HIGH · ref_conf 0.75→1.0 |
| CE-B2: 3 정상 + outlier 2, 하나만 재타입 | type_to_grid | 0.406 (n=4000) | ref_conf 0.6→0.8 · **status LOW→HIGH** · ref LOW→HIGH |
| CE-C: outlier ratio를 mode×3으로 설계 | geometry_ratio_break (g=3.0 봉인값) | 0.064 (n=4000) | conf 0→1.0 · unit LOW→HIGH |
| CE-D: 전 handle 내부 충돌(eligible 공집합) | outlier_clone | **1.0** (n=1000) | unit **NONE→LOW** |
| CE-E: outlier=mode/2.5, factor 윈도 수리 | stale_override | 0.0025 (n=20000, 50건) | conf 0→1.0 · unit LOW→HIGH · ref_conf 0.75→1.0 |
| CE-F: 일관·산포 클러스터 {0, .5τ, τ} | type_to_grid | **1.0** (n=4000) | conf 0.6065→1.0 |
| FV-1: display 없는 정직 DIM 재타입 | 자유 변형 (2차 함대 B1-class) | — | conf 0→1.0 · unit LOW→HIGH · ref_conf 0.75→1.0 |

재현 시드는 probe_results.json에 기재(CE-B seed 0, CE-B2 seed 5, CE-C seed 9, CE-E seed 384,
CE-F seed 5). 특기 사항:

- **CE-A는 봉인 5필드 전부를 한 번의 결정론적 family 적용으로 올린다.** 장면 형태는 셀 자신이
  "정당 장면"으로 봉인한 O1(이중 치수)과 동형 — 두 번째 치수의 라벨만 없는 dual dimensioning이다.
  v3는 이를 space 분열(z_mm vs z_raw)로 conf 0 처리하고, 라벨을 **지우는** 교란이 분열을 병합해
  만점을 만든다.
- **CE-B2는 정보-한계 방어가 불가능한 질적 결함**: after 장면에 ratio outlier(CB2_O1)가 **여전히
  살아 있는데** reference HIGH가 복원된다(`ratio_outlier_handles=['CB2_O1']`, ref HIGH — 실측).
  REPORT 40행의 조항("ratio-bearing span이 ratio outlier이면 confidence의 독립 지지 handle에서
  제외")은 재타입이 ratio-bearing 성질 자체를 지우는 순간 우회된다.
- **CE-D는 "의심 증거는 분모에만"(prereg `suspicious_evidence_role: denominator only`)의 위반**:
  위조 outlier 클론이 유일한 eligible handle이 되어 **numerator 전체를 구성**하고, 추정값
  `display_per_raw`가 None → 78.93(위조 ratio)으로 바뀌며 unit_status가 NONE→LOW로 오른다.
  100% 재현.
- REPORT 42행의 구조 논증 "display 제거와 type 변경은 coherence ceiling을 넘지 못하고"는 문언
  그대로 천장-조건부다 — 천장 **아래**에서 type 변경은 천장**까지** 올라간다(CE-B·B2·F).
  41행 "내부 제거로 4/5가 4/4가 되는 경로는 없다"는 참이지만, 봉인 class의 입력-레벨 제거
  (type_to_grid)가 정확히 4/5를 4/4로 만든다.

## 4. 1_coherent 게이트 경계 거동 (mode 부분집합 판정) [D]

- **D1**: 같은 handle에 두 번째 **일관** record(정직한 반복 라벨) 추가 → conf 1.0→0.0.
  부분집합 판정이 handle-집합이 아니라 **record 수**(`len(inliers)==len(all_candidates)`,
  inlier는 handle당 대표 1)라서, 정직한 중복 라벨 하나로 만점이 0이 된다.
- **D2**: 수치 동일·공간 분리(MM vs 무단위) 2:2 동률 → 병합 없이 conf 0, mode는 space 우선순위로
  z_mm. CE-A 상승의 전제 구조.
- **D3**: 편차 정확히 τ → conf 1.0(가중 중앙값 MAD가 0), τ×(1+1e-9) → conf 0.0.
  **1e-9 log-편차에 걸린 1.0↔0 절벽.**
- **D4**: 전 handle 충돌 시 eligible 공집합 → unit NONE. 이 모서리에서 어떤 단독 clean-handle
  record든(위조 클론 포함) 그대로 numerator가 된다(CE-D).
- 종합: v3의 ratio confidence는 coherent이면 residual factor만 남고(합의·독립·공간 인자는 게이트
  통과 시 항등적으로 1) 가중 중앙값 MAD의 강건성 때문에 실질 분포가 **{0} ∪ {≈1} 절벽**이다.
  깨끗한 pool이 전부 1.0에 몰리는 포화는 우연이 아니라 **재설계에 내재된 구조**이고, 따라서
  천장-시작 프로브의 "상승 0"은 체계적으로 무정보다.

## 5. 판정 논거

1. 좌석 전제 확인: 1·2차 함대 프로브 전 계열(P0·B1~B4·54종)은 v3 의미론에서 5필드 만점에서
   시작한다(§1, 아티팩트 직접 재확인). 주장 ①의 "상승 0이 됐고"는 수리의 증거가 아니라 포화의
   산술이다. 같은 계열 중 headroom이 있던 유일한 지점(B4 2→3)에서는 상승이 실측·기록됐다.
2. 주장 ③의 600종은 재현 digest까지 진본이나(§0), pool 400장면에 상승 메커니즘의 표적이 0개
   존재해(§2 census) 전수 19,028 draw·6,000 재추첨에서도 상승이 **불가능**했다. 속성 시험은
   자신이 검증한다고 봉인한 성질(perturbation_monotonicity, allowed 0)을 표본화하지 못했다.
3. 그 봉인 성질은 **거짓이다**: 봉인 문법 그대로, 합법 LOW-시작 장면에서 5개 family가 추적
   필드를 올린다 — suffix_removal은 5필드 전부·결정론(CE-A), type_to_grid는 draw당 25~41%
   (CE-B/B2), geometry_ratio_break 6.4%(CE-C), stale_override 0.25%(CE-E), outlier_clone은
   NONE 경계에서 100%(CE-D). prereg는 B4 하나만 정보-한계로 면제했고 이 class들은 전부 gated
   side에 있다. L1c가 같은 구조(봉인 밴드 위반 실측)로 REFUTE된 선례와 정확히 대칭이다.
4. 정보-한계 방어(교란 후 장면이 정직 장면과 구별 불능이므로 상승이 강제된다)는 (a) prereg가
   그 논리로 면제한 것은 B4뿐이고, (b) CE-B2(의심이 잔존한 채 HIGH 복원 — REPORT 40행 조항
   우회)와 CE-D(의심 record가 numerator+추정값이 됨 — "denominator only" 위반)는 그 방어로도
   설명되지 않는 수리 가능한 의미론 결함이므로, 기각한다.
5. REPORT 379행은 600종 결과를 pool-scope로 정직하게 한정했고 B4 한계도 수치로 남겼다(미해결
   §). 그러나 검증 대상 주장은 그 한정을 넘어 "프로브 전 계열 상승 0·600종 상승 0"을 루프
   **종결**의 근거 ①③으로 제시한다. 2차 함대가 결함을 실측한 도구(LOW-시작 B1~B3)를 v3에
   다시 겨누면 같은 형태의 상승(status LOW→HIGH 포함)이 재현되므로, 분모-청소 취약 class는
   닫힌 것이 아니라 **천장 뒤로 숨은 것**이다. 종결 주장은 성립하지 않는다.
6. 내 시야에서 진본으로 확인된 것: 600종 digest·upward 0 재현(§0), 코호트 수치(⑤의 coverage
   1.0/정확도 1.0·L1b 분포)의 재계산 일치(§2 census), B4 한계의 정직 기록. ②④⑤의 자체 검증은
   타 좌석 시야이며 내 증거와 모순되지 않는다 — 그러나 ①③이 종결을 지지하지 못하고 봉인
   밴드가 위반되는 이상, 주장 전체는 내 시야에서 기각된다.

## 6. 산출물

- 본 보고서: `D:\runs\e2_program\chainverify_L1d\lens1_saturation.md`
- 프로브 하니스·원시 수치: `lens1_work\probe_saturation.py` · `lens1_work\probe_results.json`

VERDICT: REFUTE
