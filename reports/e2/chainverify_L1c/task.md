# 사슬 검증 과업 — L1c 루프 종결 주장 (2차 함대)

## 검증 대상 주장 (오케스트레이터)

"Feyerabend C1 루프(C1→L1→L1b→L1c)는 L1c로 종결됐다: ① 추정기 잠복 결함(span-inlier
outlier의 reference 합의 부양)이 신규 가드로 수리됐고 — 라이브 반례 회귀에서 원본은 상승 재현,
C1v4는 상승 0 — ② C1 원본 코호트에서 그 결함이 낳던 역전이 26건이 replay에서 0건이 됐으며,
③ L1b 코호트의 정상 수치는 전 필드 불변이고, ④ 이중 사전봉인(prereg.json+PREREG 시트, 수리
코드 생성 전)이 최초로 절차대로 수행됐다."

## 전제 (재검증 불요 — 1차 함대가 이미 확정)

C0→L1b의 수치 실질은 1차 함대 4석이 독립 재현 완료 — 평결은
`D:\dev\99_tools\autocad-sdk-router\reports\e2\chainverify_L1b\` (repo @af4d367) 참조.
이번 함대는 **L1c 증분**을 겨눈다. 단, 사슬 무결성 스팟체크(L1c가 기존 산출물·소스를 건드리지
않았는가)는 포함한다.

## 증거 경로 (READ-ONLY)

- L1c 산출: `D:\runs\e2_program\cells\loop_l1c\` (REPORT.md·prereg.json·feyerabend_c1_v2.py·
  loop_l1c.py·c1v4_results.json·replay_delta.json·evidence.xlsx)
- 원본 추정기: `D:\dev\99_tools\autocad-sdk-router\tools\e2\cells\feyerabend_c1.py` (READ-ONLY)
- 1차 함대 반례 기전: `D:\dev\99_tools\autocad-sdk-router\reports\e2\chainverify_L1b\lens2_stats.md` F1
- 코호트: `D:\runs\e2_program\cells\loop_l1b\`·`D:\runs\e2_program\cells\feyerabend_c1\` (READ-ONLY)
- 도시에: `D:\dev\99_tools\autocad-sdk-router\reports\e2\dossiers\feyerabend_P2.md` §2.3~2.4·738-740행

## 검증 계약 (전 좌석 공통)

- 모든 것 READ-ONLY — 재실행·재계산 산출물은 자기 작업 폴더
  `D:\runs\e2_program\chainverify_L1c\<seat>_work\` 에만. 기존 산출물·repo 수정 금지. git 커밋 금지.
- 서브에이전트 금지. 원본 CAD·test 접근 금지.
- 불확실하면 REFUTE. 판정 근거는 전부 파일·수치 인용으로.
- 산출: 지정된 자기 파일 하나. 마지막 줄 `VERDICT: CONFIRM` 또는 `VERDICT: REFUTE`.

## 좌석별 시야

- **lens1 (가드 정합성·과차단)** → `lens1_guard.md`: `ratio_space_outlier_guard`의 설계를 코드로
  정독하고, 반대 방향 오류 — 정당한 앵커를 잘못 격리해 coverage를 잃는 경로 — 를 적대적으로
  탐색하라. L1b replay 불변은 그 모집단에서의 무해 증거일 뿐이다. 가드 조건을 우회하는 새로운
  섭동 입력(span-inlier가 아닌 다른 잠입 경로)을 최소 3종 구성해 원본과 v2 양쪽에 실행, 상승
  여부를 실측하라.
- **lens2 (회귀 충실도)** → `lens2_regression.md`: selftest에 편입된 live counterexample이 1차
  함대 lens2_stats.md F1의 기전과 충실히 일치하는지 — 축약·스트로맨화되지 않았는지 — F1 문서의
  재현 절차로부터 반례를 독립 재구성해 원본·v2 양쪽에 실행, L1c의 회귀 표(before/after 4행)와
  수치 대조하라.
- **lens3 (26→0 귀속)** → `lens3_attribution.md`: C1 원본 코호트의 single_outlier 역전이 26건이
  ① 원본 추정기에서 실재하고 ② v2에서 소멸하며 ③ 소멸의 원인이 정확히 가드인지(다른 코드 차이가
  아니라)를 장면 단위로 추적하라. 26건의 장면 id 목록을 양쪽 실행에서 뽑아 대조하고, 가능하면
  가드만 무력화한 변형 실행으로 인과를 격리하라 (변형 코드는 자기 작업 폴더에만).
- **seat4 (전면 감사·교차 벤더)** → `seat4_sol.md`: ① 이중 봉인 실질 — prereg.json과 PREREG
  시트의 내용 일치, 봉인이 수리 코드보다 선행했는지의 증거(파일 시스템·xlsx 내부 타임스탬프·
  REPORT 기록 교차), 봉인 수치가 도시에 밴드와 일치하는지 ② 소스 무수정 — manifest digest 재계산
  ③ 300종 속성 시험의 실질 — family 분포·시드 재현·상승 0의 독립 재확인 ④ v2가 새로 도입한
  퇴행·이상 경로 유무 전면 수색. 불확실하면 REFUTE.
