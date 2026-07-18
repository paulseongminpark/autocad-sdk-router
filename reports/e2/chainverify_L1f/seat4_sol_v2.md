# seat4 — L1f Phase B 전면 독립 재검증 (sol ultra) — v2

당신은 통계 추정기 검증 좌석이다. 대상은 CAD 치수-앵커 합성 장면에 대한 신뢰도 추정기
(`feyerabend_c1_v5.py`)이며, 과업은 **봉인된 사전등록 계약과 실행 보고의 일치 여부를 독립적으로
재검증**하는 것이다. 이것은 소프트웨어 품질 감사다 — 서술과 산출물은 계측 검증 용어(반례 탐색,
교란 사례, 계약 위반 여부 판별)로 작성하라.

## 대상과 계약

- 구현: `D:\runs\e2_program\cells\loop_l1f\feyerabend_c1_v5.py` · 하니스 `loop_l1f.py` ·
  보고 `REPORT.md` (전부 READ-ONLY)
- 봉인 계약: 같은 폴더 `prereg.json`
  (SHA-256 `76AC2A58D74C644A3BF7897325818F1E12151596DC3316BA7CA488BDEB207861`) —
  git 커밋 `c896068`에 봉인됨 (구현 코드 작성 이전).
- 데이터: `c1v7_results.json` · `fleet_probe_results.json` · `replay_delta.json` ·
  `witness_classifications.json` · `honest_envelope.json` · `predicate_registry.json`
- 참고(READ-ONLY): 4차 검증 자료 `D:\runs\e2_program\chainverify_L1e\seat4_sol.md` +
  `seat4_work\`(당신의 이전 프로브 하니스 — 재사용 가능), 이전 판 추정기
  repo `tools\e2\cells\feyerabend_c1{,_v2,_v3,_v4}.py`.

## 실행 보고가 주장하는 수치 (검증 표적)

- 정직 코퍼스 실측 봉투: 400장면/2008앵커, ratio 편차 최대 1.46e-13τ, raw-span↔기하 불일치 0.
- 표적 회귀 5케이스 + 1494-창(그중 747 v4 양성): v5 신뢰도 상승 0.
- 2,000 무작위 교란 사냥: v4 위반 재현 50건 전부 v5에서 차단, 전체 상승 44건 잔존.
- P4(GRID 중립) 무손실 0 · info-limit 분류 0 · 비희석 스윕 11케이스×N∈{0,3,10,20,40}.
- replay 400장면 218,469행, HIGH 360/360이 5% 이내, 최소 coverage 0.800.
- 상승 분류 90건·위반 0·미분류 필드 0·18규칙 전사/건 · 술어 15/15 반례 실행.

## 임무

1. **봉인 선행 증인 (git read-only — 이 좌석만 허용)**: repo
   `D:\dev\99_tools\autocad-sdk-router`에서 커밋 `c896068`의 tree/blob을 검사 — 봉인 3파일이
   그 커밋에 존재하고 현재 파일과 byte-identical한지, 그 시점에 feyerabend_c1_v5.py가
   부재했는지, 시각 순서가 정합한지. (git 읽기 명령만: show/cat-file/log. 쓰기 명령 금지.)
2. **계약↔구현 축조 대조**: prereg.json의 전 조문(2계층 신호 분류 경계 · per-signal 감쇠 하한 ·
   span측 max-봉투 · GRID 중립 · 동결 표면 전 필드 심판 · info-limit 금지 · 회귀 의무 목록)이
   코드에 실제로 그 문언대로 구현됐는지 1:1 검토.
3. **독립 재실행**: 당신의 4차 프로브 하니스(5케이스+747-창)를 v5에 재실행해 "상승 0"을 재현
   또는 반증.
4. **반례 탐색**: 결정적 시드로 ≥2,000 교란 사례를 생성해 봉인 조문 위반 사례(정직-생산불가
   신호 잔존 상태의 신뢰도 상승, 희석에 의한 하한 붕괴, 커버리지/정확도 밴드 이탈)를 탐색.
5. **44건 잔존 상승 판별**: fleet_probe_results.json의 44건을 각각 — 봉인 분류상 (a) 정직-
   생산가능 잔존이며 하한 이내의 정당한 상승인지 (b) 계약 위반인지 — 근거와 함께 판별.

## 판정 어휘 (엄수)

- 최종 = **CONFIRM**(계약 준수 실증) 또는 **REFUTE**(위반 실증) + 재현 절차·수치·조문 인용.
- REFUTE 시 결함이 (a) 1~4차 검증에서 이미 알려진 결함 유형의 회귀인지 (b) 새로운 결함
  유형인지 명시 — 이 구분이 프로그램의 다음 단계 결정(설계 재검토 상신 여부)을 좌우한다.
- 알려진 유형 목록: 모집단 마스킹 · 승인가드 우회/분모 정화 · 포화 마스킹/타임스탬프 소급 ·
  탐지 창 공백((τ,3.5τ)) · 선언↔기하 불일치 비검출 · 평균-분모 희석 · 증인 논거 항진 ·
  GRID 과차단 · 역방향 이동 인증 창.

## 산출

`D:\runs\e2_program\chainverify_L1f\seat4_work\`에 프로브 코드·수치(디스크-first),
최종 `D:\runs\e2_program\chainverify_L1f\seat4_verdict.md`. 원본 CAD·test 접근 금지.
repo·기존 산출물 수정 금지. 서브에이전트 금지. 수치 전건에 산출 명령 병기.
