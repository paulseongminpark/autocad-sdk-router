# Lens 1 — DATA/LEAKAGE 독립검증 보고 (L1b 사슬 주장)

- 검증관 시야: 추정기의 진리-맹목성(라벨 접촉 가능 코드 경로), pair-label 순열 digest의 유효성, 장면 모집단 무결성, 도시에 원문 대비 mutation family 커버리지, 진리→추정/신뢰도로 가는 모든 정보 경로.
- 방법: 전 소스 코드 정독(C0·C1·L1·L1b) + 산출물 전량 독립 재계산(재실행 산출물은 `chainverify_L1b\rerun\`에만 기록). 원본 산출물 무수정. git·서브에이전트·CAD/test 접근 0.
- 재계산 스크립트/증거: `rerun\verify_lens1.py`, `rerun\verify_lens1_details.json`, `rerun\selftest_rerun.txt`.

## 결론 요약

시야 내 반박 소견 0건. 주장 ①②③⑤⑥ 및 모집단 무결성·가족 커버리지·봉인 불변성은 전량 독립 재계산으로 재현되었다. 관찰(주장을 깨지 않으나 봉인의 증명 범위를 한정하는 사실) 4건을 심각도순으로 기록한다.

---

## 발견 사항 (심각도순)

### F-1 [관찰·중간] pair-label 순열 digest 게이트는 구조적으로 실패할 수 없는 시험이다 — 진리 무접촉의 실질 근거는 별도 장치에 있다

- 순열 함수 `permute_pair_labels`는 `truth_pairs`만 변형한다 (`feyerabend_c1.py:572-593`). 추정기 진입점은 `anchor_artifact_from_scene`이며 scene에서 `anchors` 한 키만 읽는다 (`feyerabend_c1.py:497-503`, 주석 "reads one key only"). 순열이 건드리는 키와 추정기가 읽는 키가 서로소이므로, bridge가 온전한 한 digest 동일성은 **동어반복적으로 보장**된다. 즉 이 게이트는 "추정기가 라벨을 쓰는가"의 행동 시험이 아니라 bridge 무결성 회귀 시험이다.
- 또한 pair-label 순열은 `truth_unit_scale`(진짜 정답 스케일)을 건드리지 않으므로, 추정기가 그 키를 훔쳐 읽는 시나리오는 이 게이트로 검출 불가능하다.
- 그러나 무접촉 주장의 실질 근거는 다음 세 겹으로 존재하며 전부 확인했다:
  1. `fit_anchor_model(raw_anchors)`는 anchors 시퀀스만 받는 시그니처이고 (`feyerabend_c1.py:347-494`), 내부에서 쓰는 필드는 anchor_type/display_value/p0/p1(기하 span 재계산, `:203,223`)/display_unit/text_height/weight뿐 — 진리 필드 접근 코드 경로 부재 (정독 확인).
  2. `GuardedScene`은 `anchors` 외 키 접근 시 즉시 AssertionError (`feyerabend_c1.py:596-611`); selftest `truth_key_access_guard`가 이를 기계 검증 (`:697-703`). 재실행 확인: `rerun\selftest_rerun.txt` — `truth_key_access_guard: PASS | accessed_keys=['anchors']`, 총 17/17 PASS(봉인 C1 selftest 6/6 포함), exit=0.
  3. **내 독립 강화 시험**: 200 장면 전부에 대해 (T1) scene 객체를 버리고 anchors만으로 `fit_anchor_model` 재계산 → 기록된 `anchor_model`과 canonical sha256 **200/200 완전 일치**; (T2) `truth_unit_scale`을 7배로 조작 + truth_pairs 재라벨 후 bridge 재실행 → artifact digest **200/200 불변**; (T3) GuardedScene을 fixture가 아닌 **전 200 장면**에 확장 → 위반 0, 접근 키 전부 `['anchors']`. (`rerun\verify_lens1_details.json`의 T1/T2/T3 = 0 mismatches)
- 판정: 주장 ⑤의 문구는 "접근 키 = anchors 단독"과 "순열 digest 동일"을 병기하고 있고, 도시에 봉인 조문도 digest 동일만 요구하므로(`feyerabend_P2.md:783` "pair-label permutation 전후 anchor artifact digest", `:789` "pair-label permutation 전후 anchor digest 완전 동일") 주장 위반이 아니다. 단, digest 동일성 **단독으로는** 무접촉 증명이 아님을 기록한다 — 증명력은 GuardedScene+코드 경로+본 재계산이 담당한다.

### F-2 [관찰·저] 진리는 anchors에 무잡음으로 인코딩되어 있어, HIGH 게이트 수치는 모집단 설계의 결정론적 귀결이다

- 전 200 장면의 ratio anchor 1,108개에서 display_value/raw_span 대 truth_unit_scale의 최대 상대편차 = **1.421e-16** (부동소수점 반올림 수준; `rerun` T5). 이는 도시에가 스스로 봉인한 설계다: `feyerabend_P2.md:563` "표시 치수값은 canonical physical geometry와 일관되게 유지하고 raw 좌표만 κ배 한다. 따라서 truth unit scale은 1/κ 방향으로 바뀌며 pair label은 그대로다." 구현 일치: `feyerabend_c0.py:889-911`(`scale_scene` — `:893` truth=1/κ, `:900-905` anchors 좌표·raw_span만 κ배, display 불변).
- 결과적으로 anchor-rich 40 장면은 신뢰점수 정확히 ≈1.0(HIGH), single-span 10 장면은 정확히 0.2667(LOW)의 **2점 퇴화 분포**다 (기록치 재확인: HIGH 점수 집합 {1.0±5e-14}, 비-HIGH 집합 {0.266667}). HIGH coverage 0.80 = 40/50, HIGH accuracy 1.0(HIGH 상대오차 최대 3.11e-15)은 설계에서 그대로 따라 나온다. 도시에 지표 "confidence bin별 accuracy"(`feyerabend_P2.md:781`)의 중간 bin은 무인구다.
- 판정: 게이트 위반 아님(주장은 게이트 충족의 측정 사실을 말하고, 측정은 정확하다). 다만 이 봉인이 증명하는 것은 "이 합성 모집단 위에서의 게이트 충족"이지 잡음 있는 실데이터에서의 판별력이 아니라는 한계를 기록한다.

### F-3 [정보] 순열 시험의 공허(vacuous) 표본은 4/200뿐이며 산출물에 정직하게 기록되어 있다

- zero-wall sentinel base 장면 1개 × 4 스케일 = truth_pairs가 빈 4 장면에서는 순열이 라벨을 바꿀 수 없다 (`permute_pair_labels`의 빈-리스트 조기 반환, `feyerabend_c1.py:575-577`). 나머지 196 장면은 라벨이 실제로 변경됨 — 기록치 `pair_label_changed_scene_count: 196`과 내 재계산(장면별 truth_pairs 유무 대조, P3 불일치 0) 일치. 1쌍뿐인 장면도 `PERMUTED::` prefix로 변경이 보장된다 (`:591`).
- digest 재계산: before/after digest 전 장면 재계산 → 기록치와 불일치 0 (P2). 전역 digest 동일 (`357de452…` == `357de452…`).

### F-4 [정보] 가족 커버리지는 게이트 최솟값( sentinel 2종 각 1 장면)으로 충족되며, v1→L1→L1b 사슬 수치가 루프 서사를 정확히 재현한다

- L1b 재계산(κ=1 장면 50개의 mutation_families에서 독립 집계) == 산출물 `c0v3_numbers.json.mutation_family_coverage`, 11/11 가족 전부 ≥1: pure_line 21 · lwpolyline 25 · arc_spline 50 · hatch 50 · nested_insert 50 · partial_overlap 50 · door_window 49 · zero_wall **1** · all_wall **1** · single_span **10** · multiple_span **40**.
- 사슬: v1 = single 25 / multiple 25 → L1 = single **0** / multiple 50 (가족 소멸 — 기각 사유의 수치 실체, `loop_l1\c0v2_numbers.json`) → L1b = 10 / 40 (복원). 주장 ③의 "단일-스팬 10 장면 복원"과 일치.
- sentinel 2종이 각 1 장면인 것은 v1부터 동일(설계 상수)이며 게이트 조문은 "각각 최소 한 scene"(`feyerabend_P2.md:758`)이므로 충족.

---

## 도시에 원문 대조 (지정 mutation family — 정확 인용)

`D:\dev\99_tools\autocad-sdk-router\reports\e2\dossiers\feyerabend_P2.md`:

- `:550` "각 scene은 최소한 다음 mutation family를 manifest에 가진다."
- `:552-561` (불릿 10개 원문) "순수 LINE 평행쌍" / "LWPOLYLINE 분절" / "ARC/SPLINE 인접 또는 교란" / "HATCH boundary 교란" / "nested INSERT와 non-uniform/누적 transform" / "부분 overlap과 거의 평행한 조각" / "door/window/dimension-like 긴 평행 distractor" / "zero-wall sentinel" / "all-wall sentinel" / "단일·다중 reference span 영역"
- `:758` (C0 합격선) "지정 mutation family가 각각 최소 한 scene에 존재"
- `:772` (C1 가설) "벽 pair label 없이 DIM/TEXT/GRID만으로 raw-unit scale을 추정하며…"
- `:794` (C1 킬 조건) "…label permutation이 anchor output을 바꾸거나…"

해석 검증 — "11/11"의 근거: 도시에 불릿은 10개이고 마지막 불릿 "단일·다중 reference span 영역"이 결합 표기다. 봉인 구현 C0의 `MUTATION_FAMILIES`(`feyerabend_c0.py:48-60`)는 이를 `single_reference_span_region`/`multiple_reference_span_regions` 2개로 분리해 **11개**로 고정했고, L1b는 이 매핑의 1:1 일치를 런타임 assert로 강제한다 (`loop_l1b.py:76-99`). 이 분리 해석은 루프 이전에 봉인되었다는 증거:

1. v1 산출물(`reports\e2\cells\feyerabend_c0\coverage_numbers.json`, L1·L1b 두 run manifest에 sha256 `f5c17b60…`으로 동결)이 이미 11-가족 집계(single 25/multiple 25)를 담고 있다.
2. v1 C0 빌더 자체가 홀·짝 index로 single/multiple을 나눠 태깅한다 (`feyerabend_c0.py:513-552`).
3. 참고: 결합 해석(1가족)이었다면 multiple 50이 존재한 L1은 가족 게이트를 **통과**했을 것 — 분리 해석은 L1 기각을 낳은 더 엄격한 쪽이며, 사후 완화가 아니라 사전 봉인된 엄격화다.
- 부기: `:550`의 "각 scene은 … 가진다"를 장면-단위 전칭으로 읽는 해석은 zero-wall/all-wall·단일/다중이 상호배타라 비정합하며, 운용 게이트는 `:758`의 코퍼스-단위 조문이다. v1부터 L1b까지 전부 이 해석으로 일관 집계되었다.

## 모집단 무결성 재계산 (전 항목 일치)

- 장면 수: scenes_v3 파일 200 = base 50 × κ{0.001,0.01,1,1000} 각 50. base_scene_id 고유 50.
- seed 공식 독립 재계산: SHA-256("feyerabend_P2:"+j) 상위 32bit == `C0.seed_for_index` 전 50 index 일치 (도시에 `:768` 봉인 조문 그대로).
- 배정 규칙 독립 재계산: sha256(str(seed)+":loop_l1b_population") 순위 상위 10 = single_span → 산출물 indices {0,2,7,19,21,23,30,35,36,41} 및 각 장면의 `population_role` 200/200 일치, 불일치 0. assignment digest 재계산 `bd49797b…` == 산출물.
- 구조 규칙: single-span 10×4 장면 = anchors 2·단일 region·단일 span, anchor-rich 40×4 = anchors 5+(seed mod 4)∈[5,8]·전 span 상이·공간 bin ≥3 — 위반 0. single-span 장면 HIGH 0건 (설계 의도대로 LOW 고정).
- 스케일별 HIGH: 각 κ에서 40/50 = **0.80** (4스케일 전부; 게이트 0.60), HIGH accuracy 각 1.0 (게이트 0.95) — 기록 aggregates와 내 행 단위 재집계 일치.
- anchors 키 전수 조사(200 장면 전체 union): {anchor_factory_revision, anchor_type, display_unit, display_value, handle, p0, p1, raw_span, region, source_span_id, text_height, weight} — 진리성 키 부재. anchor handle과 truth_pairs handle의 교집합 0 (라벨-앵커 식별자 격리).

## 교란 4종 — 진리→신뢰도 역류 부재 (주장 ⑥)

- 200 장면 × 4 교란 = 800개 corrupted 모델을 전량 재계산 → 기록된 `artifact_digest`와 불일치 **0** (결정성 + 산출물 무결성 동시 확인).
- status/unit_status/reference_status 상승 전이 0건, confidence_score 상승(>1e-15) 0건 — 기록치·재계산 일치. `ticket_single_outlier.v2_confidence_or_status_increased_count = 0`.

## 봉인 불변 사슬 (밴드 이동 없음)

- L1 run manifest ↔ L1b run manifest ↔ 현재 디스크: `feyerabend_c0.py` sha256 `dfc8957f…`, `feyerabend_c1.py` `633c5ee1…`, 도시에 `3ae87588…`, v1 numbers `f5c17b60…`, v1 C1 REPORT `90956fa1…` — 전부 3자 일치 (경로 단위 대조; 두 run 모두 실행 전/후 manifest mismatch 0).
- `sealed_configuration` L1 == L1b: HIGH 문턱 0.75, consensus 0.80, min_independent 3, tol log(1.05)=0.04879…, 정확도 0.05 — 문턱 이동 없음.
- mtime 시계열(보조 증거): 도시에 07-18 20:02 → c0.py 07-19 00:47 → c1.py 01:09 → loop_l1.py 01:32 → L1 결과 01:35 → loop_l1b.py 01:57 → L1b 결과 02:05 — 주장된 순서와 정합.
- 주장 ④ 수치 대조(저장값): KS `0.040287855437306064`(≈0.0403), TV `0.00021191458340744963`(≈0.000212), truth_validator error 0 — 주장 표기와 일치. (KS/TV의 산식 재계산은 fidelity lens 소관으로 미수행.)
- 루프 경로 수치: v1 HIGH coverage **0**(추정은 전 장면 정확하나 신뢰 상한 0.6<0.75) → L1 HIGH coverage **1.0**·single 가족 0(기각) → L1b **0.8**·11/11 — 주장 서사와 전 구간 일치.

## 검증하지 못한 것 (정밀 한정)

- 주장 ⑦(전체 재실행 바이트 동일)은 시야 밖으로 전량 재실행-비교를 하지 않았다. 단 본 검증의 1,000회 재계산(모델 200 + 교란 800) 전부가 기록 digest와 일치했고 selftest의 same-j-same-sha 검사가 통과했으므로 결정성의 부분 증거는 축적되어 있다.
- evidence.xlsx 내부 시트 무결성, KS/TV 산식 재계산: 각각 타 lens 소관, 미수행.

VERDICT: CONFIRM — 추정기는 코드 경로·가드·전 장면 독립 재계산(진리 조작 불변 포함)에서 anchors 외 무접촉으로 확인되고, 모집단 40+10·가족 11/11·스케일별 HIGH 0.80/정확도 1.0·교란 상승 0건·봉인 해시/문턱 불변이 전량 재계산으로 재현되었다 (단 F-1: 순열 digest 게이트 단독은 동어반복적 시험이며 무접촉 증명력은 가드+재계산이 담당).
