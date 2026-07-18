# 루프 패킷 L1f — Phase A: 봉인만 산출하고 정지 (2계층 의심 분류·비희석 속성)

당신은 E2 프로그램의 계측기 수리 실행자다. L1e는 4차 사슬 검증단에 의해 기각됐다 — **먼저 읽어라
(READ-ONLY)**: `D:\runs\e2_program\chainverify_L1e\SYNTHESIS.md` · `lens1_witness.md` ·
`lens2_formula.md` · `seat4_sol.md`. 이 패킷은 Phase A다: **봉인 산출물만 만들고 정지. 추정기
코드 금지.** (L1e Phase A와 동일 절차 — 착지 후 오케스트레이터가 git 커밋해 외부 증인 생성.)

## 임무 — `D:\runs\e2_program\cells\loop_l1f\` 에 봉인 3파일만

1. `prereg.json` — L1e 봉인(@3a390e8)의 전 밴드를 승계하되 다음을 **추가 봉인**:
   - **의심 신호 2계층 분류** (SYNTHESIS 골격 1항): (a) 정직-생산가능 잔존 — 실측 봉투(정직 코퍼스
     400장면 + 봉인 정직 예시 O1/O2에서 관측되는 신호 종류·크기 한계를 수치로 봉인; O2-class
     온건 display-stale 등) 내의 잔존은 상승 허용하되 희석-불가 감쇠 하한 이내에서만. (b) 정직-
     생산불가 신호 — 선언 필드↔기하 모순(raw_span≠|p1−p0| 등 동결 표면의 전 선언 필드)·source
     handle 충돌(ratio·span 양측)·혼합 공간 흔적·거리 ≥3.5τ severe — 잔존 시 상승 = violation
     (허용 0), 추정기 경성 차단(스코어 하한 0/NONE).
   - **비희석 단조성 속성** (신설 밴드): 고정 의심 집합 S에 대해, S와 무관한 깨끗한 증거를 몇 개
     추가해도(N→∞) S가 유발하는 감쇠 페널티의 하한이 불변이어야 한다 — 후보-수 평균 기반 페널티
     금지, per-suspicious-signal floor 의무. 속성 시험에 "S 고정 + 깨끗한 N∈{0,3,10,20,40} 추가"
     스윕 조항.
   - **탐지 표면 = 동결 직렬화 전체**: suspicion_analysis는 canonicalize 이전의 동결 표면 전
     선언 필드를 심판한다는 조항 (lens1 W000002의 근본 원인 차단).
   - **과차단 수리**: ratio-부재 handle(GRID 등)은 ratio-신뢰 평균에서 중립(제외) — 정직 GRID
     추가가 reference를 강등시키지 않아야 한다는 무손실 조항(lens2 P4를 회귀로).
   - **증인 실질화**: 정당성 논거는 장면-특정(실행 탐지 규칙 전 목록+각 0 카운트+정직 생성 서사)
     — boilerplate 금지 조항.
   - **회귀 의무 목록**: seat4 표적 5프로브+747-창 스윕 · lens1 W000002/B5(선언↔기하 위조) ·
     lens2 T_A(span충돌+희석)/T_C/T_S/P4/P5-위반50 — 전부 상승-차단 또는 violation-검출로
     통과해야 함을 명기.
   - 도달 불능 조항 정리: L1e에서 유지된 밴드(coverage·정확도·O1/O2 무손실·replay 전문 공개·
     술어 무결)는 문언 그대로 승계.
2. `PREREG_SEALED.csv` (스프레드시트 런타임 부재 시 — 사유 1줄 포함, L1e와 동일 형식).
3. `SEAL_MANIFEST.txt` — 두 파일 SHA-256.

마지막 stdout 줄: `PHASE_A_COMPLETE: loop_l1f_seal`

## 금지

추정기·수리 코드·시험 실행 전부 Phase B의 몫. git 금지. 서브에이전트 금지. repo·기존 산출물
수정 금지. 원본 CAD·test 접근 금지.
