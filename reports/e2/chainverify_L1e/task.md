# 사슬 검증 과업 — L1e 루프 종결 주장 (4차 함대)

## 검증 대상 주장 (오케스트레이터)

"Feyerabend C1 루프는 L1e로 종결됐다: ① 의미론 수리 4항(CE-B2 지속 감쇠·CE-D 공집합/단독→NONE·
D1 handle-집합 판정·D3 연속 감쇠)이 구현됐고 수리 가능 class(outlier_clone·handle_collision·
display_removal·geometry_ratio_break·exact_duplicate·reference_support_drop)의 상승이 72,396 전이
전수에서 0이며 ② 잔존 상승(stale 36·suffix 66·type_to_grid 210 + 속성/함대 계열, 필드 이벤트 총
1,767)은 전건 자동 증인 분류로 관측-동치 정직 증인이 제시된 information_limit_record이고 violation
0·미분류 0이며 ③ selftest 술어 9종 전부 반례 실행으로 false 관측(항진식 사멸) ④ 봉인은 추정기
부재 시점의 git 커밋 @3a390e8이 외부 증인이고 ⑤ 코호트 밴드(L1b 0.8/1.0·C1 1.0/1.0)·O1/O2
무손실·replay 전문 공개(101,828행, 0-델타 포함)가 성립한다."

## 전제 (재검증 불요)

1~3차 함대 평결은 repo `reports\e2\chainverify_L1b\`·`_L1c\`·`_L1d\`. 이번 함대는 **v4(L1e)
증분**을 겨눈다. 봉인 계약 원문 = repo `reports\e2\cells\loop_l1e\prereg.json` (@3a390e8).

## 증거 경로 (READ-ONLY)

- L1e 산출: `D:\runs\e2_program\cells\loop_l1e\` (REPORT.md·feyerabend_c1_v4.py·loop_l1e.py·
  c1v6_results.json·replay_delta.json(92MB)·fleet_probe_results.json(28MB)·
  witness_classifications.json·predicate_registry.json·evidence.xlsx + Phase A 봉인 3파일)
- 이전 추정기: repo `tools\e2\cells\feyerabend_c1{,_v2,_v3}.py` · 이전 함대 프로브 하니스:
  `D:\runs\e2_program\chainverify_L1c\lens1_work\`·`chainverify_L1d\lens1_work\`·`seat4_work\`
- 도시에: repo `reports\e2\dossiers\feyerabend_P2.md` §2.2~2.4
- 코호트: `D:\runs\e2_program\cells\loop_l1b\`·`cells\feyerabend_c1\`

## 검증 계약 (전 좌석 공통)

- 모든 것 READ-ONLY — 재계산·프로브는 자기 작업 폴더 `chainverify_L1e\<seat>_work\` 에만.
  git 커밋 금지(읽기 조회는 seat4 §① 검증에 한해 허용). 서브에이전트 금지. 원본 CAD·test 금지.
  불확실하면 REFUTE. 산출: 자기 파일 하나, 마지막 줄 `VERDICT: CONFIRM` 또는 `VERDICT: REFUTE`.

## 좌석별 시야

- **lens1 (증인 분류기 적대 검증)** → `lens1_witness.md`: 분류기가 하중을 받는 유일한 요소다.
  ① witness_classifications.json의 361건에서 동결된 사후 표면을 독립 재검 — 잔존 의심 신호(가시
  ratio outlier·handle 충돌·혼합 공간 흔적·display-잔존 등)가 하나라도 있는 표면이
  information_limit_record로 분류된 사례를 수색하라(발견=위반 은폐). ② v4 의미론에서 의심이
  잔존하는 상승 장면(CE-B2·CE-D 변형 + 자유 변형)을 새로 구성해 분류기에 넣고 violation으로
  분류되는지 라이브 확인 — 분류기가 violation을 실제로 낼 수 있는지. ③ "정직 증인" 정의의 순환성
  검사: 증인이 교란 이력의 재서술이 아니라 독립 정당성을 갖는지 표본 판정.
- **lens2 (신규 공식 적대 탐색)** → `lens2_formula.md`: 공개 공식(REPORT 9행)의 구조를 겨눠라 —
  ① 희석 공격: 깨끗한 handle 다수 추가로 mean_h(p_h)를 희석해 의심 페널티를 무력화하는 경로
  ② A_severe smoothstep 창(2.5τ~3.5τ) 경계의 조작 가능성 ③ reference_score의 mean_h(1-p_ratio)
  결합이 만드는 새 상승/과차단 경로 ④ 9-family 밖 자유 교란으로 LOW-시작 상승 탐색 — 발견 시
  각각을 증인 기준으로 분류(증인 가능=한계 기록, 불가=위반)해 보고. 구현이 공개 공식과 일치하는지
  코드 대조 포함.
- **lens3 (공개·술어 실행 무결)** → `lens3_disclosure.md`: ① replay_delta.json의 101,828행
  완전성 — 독립 재실행으로 행 수·0-델타 포함·필드 커버리지 대조(표본+전수 카운트) ② 코호트
  밴드·O1/O2 수치 재계산 ③ predicate_registry.json의 "반례 실행 false 관측" 주장을 전 술어
  독립 재실행으로 검증 ④ 26→0 등 이전 티켓의 유지 확인.
- **seat4 (전면 감사·교차 벤더)** → `seat4_sol.md`: ① 봉인 증인 사슬 — repo git 이력에서
  @3a390e8의 내용·시점·추정기 부재를 검증(git log/show 읽기 조회 허용), Phase A 파일 3종의
  불변성 ② 속성 시험 641 case·pool 계층 5종 의무·1,548-탐색 72,396 전이의 독립 재구성 ③ 361
  증인 레코드의 증거 5종(prereg 요구) 전건 완전성 감사 ④ v4 신규 이상 경로 전면 수색(제한 없는
  회의론). 불확실하면 REFUTE.
