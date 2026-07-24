# 사슬 검증 과업 — L1d 루프 종결 주장 (3차 함대)

## 검증 대상 주장 (오케스트레이터)

"Feyerabend C1 루프(C1→L1→L1b→L1c→L1d)는 L1d로 종결됐다: ① 합의 계산 구조 재설계(z^mm 선행
정규화·독립성=고유 handle·span label-free·의심 증거는 분모에만)로 1·2차 함대의 프로브 전 계열
(1차 반례, B1~B3, 분모청소 54종)이 상승 0이 됐고 ② 정당 장면 무손실(O1/O2 하락 0) ③ 확장 9-family
600종 속성 시험 상승 0 ④ 이중 봉인이 실물·시각·읽기전용 관측으로 선행 입증되며 ⑤ C1 원본
코호트의 봉인 밴드(HIGH coverage ≥0.60·정확도 ≥0.95)가 coverage 1.0/정확도 1.0으로 충족되고
L1b 코호트 정상 수치는 불변이다."

## 전제 (재검증 불요)

C0→L1b 수치는 1차 함대, L1c 가드의 결함은 2차 함대가 확정 —
`D:\dev\99_tools\autocad-sdk-router\reports\e2\chainverify_L1b\` · `chainverify_L1c\` (repo) 참조.
이번 함대는 **v3(L1d) 증분**을 겨눈다.

## 증거 경로 (READ-ONLY)

- L1d 산출: `D:\runs\e2_program\cells\loop_l1d\` (REPORT.md·prereg.json·evidence_sealed.xlsx·
  feyerabend_c1_v3.py·loop_l1d.py·c1v5_results.json·replay_delta.json·fleet_probe_results.json)
- 이전 추정기: repo `tools\e2\cells\feyerabend_c1.py`(v1)·`feyerabend_c1_v2.py`(v2) (READ-ONLY)
- 이전 함대 평결: repo `reports\e2\chainverify_L1b\`·`chainverify_L1c\` (특히 lens1_guard.md의
  프로브 설계와 seat4_sol.md §5)
- 도시에: repo `reports\e2\dossiers\feyerabend_P2.md` §2.2~2.4·738-740행
- 코호트: `D:\runs\e2_program\cells\loop_l1b\`·`cells\feyerabend_c1\` (READ-ONLY)

## 검증 계약 (전 좌석 공통)

- 모든 것 READ-ONLY — 재계산·프로브는 자기 작업 폴더 `chainverify_L1d\<seat>_work\` 에만.
  git 커밋 금지. 서브에이전트 금지. 원본 CAD·test 접근 금지. 불확실하면 REFUTE.
- 산출: 지정된 자기 파일 하나. 마지막 줄 `VERDICT: CONFIRM` 또는 `VERDICT: REFUTE`.

## 좌석별 시야

- **lens1 (포화-은폐 적대 탐색)** → `lens1_saturation.md`: 2차 함대 프로브 장면들은 v3 의미론에선
  천장(HIGH/1.0)에서 시작해 상승이 포화로 불가능하다 — 이는 단조성의 증명이 아니다. **v3 의미론에서
  문턱 아래(LOW, confidence<0.75)에서 시작하는 장면**을 체계적으로 구성하고(coherence 부분 훼손·
  혼합 mode·희소 bin·경계 0.74 등), 그 위에서 교란(1·2차 함대 전 class + 자유 변형)이 추적 필드
  5종 중 하나라도 올리는 반례를 탐색하라. 1_coherent 게이트의 경계 거동(mode 부분집합 판정)도 검사.
- **lens2 (C1 coverage 0→1.0 정당성)** → `lens2_coverage.md`: v3의 공식 재설계가 도시에 §2.3의
  조문과 양립하는가(도시에가 공식 자체를 불변 조문으로 새겼는지, 아니면 밴드가 수용 기준이고 공식은
  수리 대상인지 — 원문 인용으로 판정), 3-anchor coherent 장면의 confidence 1.0이 "HIGH를 너무
  쉽게" 만드는가(HIGH 부분집합 정확도가 코호트 밖 입력에서도 유지될 구조인가 — 오염·저품질 장면을
  구성해 HIGH 오부여를 탐색), coverage 0→1.0이 게이트 게이밍이 아니라 원 구조적 불일치(min(1,n/5)
  캡)의 원리적 해소인지를 코드·수치로 판정하라.
- **lens3 (replay 3판 무결·공개 완전성)** → `lens3_replay.md`: v1/v2/v3 replay를 독립 재실행해
  REPORT의 델타 표(특히 v2의 L1b stale_override reference_confidence 상승 160 — L1c 시야 밖
  소급 발견)와 26→0→0·L1b 불변·정상 변화 공개의 완전성(replay_delta.json에 없는 은폐 변화 유무)을
  전수 대조하라. 소스 manifest 재계산 포함.
- **seat4 (전면 감사·교차 벤더)** → `seat4_sol.md`: ① 이중 봉인 — 이번엔 실물·시각·읽기전용
  관측이 제시됐다: 위조·역산 가능성까지 포함해 검증(sealed workbook과 prereg의 canonical 대조,
  파일시스템 시각의 신뢰성, 검사기 코드의 상수 반환 부재) ② 600종 속성 시험 독립 재구성(9-family
  문법·시드 재현·상승 0) ③ v3 신규 이상 경로 전면 수색(특히 strict coherence의 0-collapse가
  만드는 절벽 거동, reference_confidence 0.75 경계) ④ B4 정보 한계 측정의 정직성. 불확실하면
  REFUTE.
