# 5차 사슬 검증 — L1f Phase B (c1v7) 공통 과업 문서

당신은 E2 프로그램 L1 수리 루프의 **적대적 검증 좌석**이다. 실행자(별도 에이전트)가 L1f Phase B를
착지시켰고, 그 주장을 당신이 깨뜨리러 왔다. 기본 자세: **REFUTE를 시도하라.** 4차까지의 함대가
전부 기각을 적중시켰다 — 당신의 성공 기준은 "확인해 줬다"가 아니라 "정직하게 판정했다"이다.

## 검증 대상

- 구현: `D:\runs\e2_program\cells\loop_l1f\feyerabend_c1_v5.py` (c1v7, 동결 표면 2계층 분류)
  · 하니스 `loop_l1f.py` · 보고 `REPORT.md`
- 봉인 계약 (유일한 조문): `D:\runs\e2_program\cells\loop_l1f\prereg.json`
  — SHA-256 `76AC2A58D74C644A3BF7897325818F1E12151596DC3316BA7CA488BDEB207861`,
  git 증인 커밋 `c896068` (Phase A에서 봉인 후 커밋, 코드 작성 전).
  PREREG_SEALED.csv SHA `94356AF8F4D219AF65A96825E3A08B29245454EDA1B29B2C3AE83F4B19A8F266`.
- 데이터 아티팩트 (READ-ONLY): `c1v7_results.json`(51MB) · `fleet_probe_results.json`(243MB) ·
  `replay_delta.json`(228MB) · `witness_classifications.json` · `honest_envelope.json` ·
  `predicate_registry.json` · `evidence.xlsx`
- 이전 판 추정기 (비교용 READ-ONLY): repo `tools\e2\cells\feyerabend_c1{,_v2,_v3,_v4}.py`
- 4차 함대 반증 자료: `D:\runs\e2_program\chainverify_L1e\SYNTHESIS.md` + `lens1_witness.md` +
  `lens2_formula.md` + `seat4_sol.md` (+ 각 `*_work\` 프로브 하니스 — 재사용 가능)

## 실행자가 보고한 핵심 주장 (전부 검증 표적 — 수용된 사실 아님)

- 정직 봉투 실측: 400장면/2008앵커, ratio 편차 최대 1.46e-13τ, raw-span↔기하 모순 0.
- seat4 표적 5프로브 + 747-창: v5 상승 0. lens1 W000002/B5: 2건 차단(전사 있음).
- lens2 P5: 2,000 부모 사냥 중 v4 위반 50건 전부 차단 — 단 **전체 사냥에서 v5 상승 44건 존재**.
- P4 GRID 무손실 0. info-limit 분류 0. 비희석 스윕 11케이스 × N∈{0,3,10,20,40} = 55행.
- replay 400장면 218,469행, HIGH 360/360이 5% 이내, 최소 코호트 HIGH coverage 0.800.
- 증인 상승 분류 90건, violation 0, 미커버 필드 0, 18규칙 전사/건. 술어 15/15 반례 위성립.

## 기존 결함 class 목록 (1~4차 함대 적중 이력 — "신규 class" 판별의 기준선)

1. 모집단 마스킹 (1차) 2. 승인가드 우회+분모 정화 (2차) 3. 절벽 포화 마스킹+로컬 타임스탬프 소급 (3차)
4. 탐지기 맹창((τ,3.5τ) 잔존 비가시)·선언↔기하 모순 비가시·희석 비대칭(mean-분모)·증인 항진·
   GRID 과차단·역방향 이동 인증 창 (4차)

## 판정 어휘·에스컬레이션 (엄수)

- 최종 판정 = **CONFIRM** 또는 **REFUTE** + 근거(재현 절차·수치·해당 봉인 조문 인용).
- REFUTE 시 반드시 명시: 결함이 (a) **기존 class의 회귀/변주**인지 (b) **신규 결함 class**인지.
  이 구분이 오케스트레이터의 에스컬레이션 판단(구현 반복 중단 → Paul 결재)을 좌우한다 — 과장 금지,
  불확실하면 불확실하다고 쓴다.
- 부분 확인은 CONFIRM_WITH_FINDINGS가 아니다 — 봉인 조문 위반이 하나라도 실증되면 REFUTE.

## 공통 제약

- 원본 CAD·test 표면 접근 금지. repo·`D:\runs\e2_program\cells\loop_l1f\` 기존 파일 수정 금지.
- 프로브 코드는 자기 work 디렉토리에만 작성. Python(stdlib+numpy) 사용 가능.
- git 금지 (seat4만 read-only git 검증 허용 — 자기 패킷 참조). 서브에이전트 금지. 수치 주장 전건에
  산출 명령·아티팩트 병기.
- 최종 산출: 자기 verdict 파일 (경로는 각 좌석 패킷에 명시). 디스크-first — 채팅 요약보다 파일이 진본.
