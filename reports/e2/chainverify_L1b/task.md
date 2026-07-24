# 사슬 독립검증 — 반증이론 C0→C1→L1→L1b 루프의 목표 도달 주장

당신은 E2 프로그램의 독립 검증관이다. 오케스트레이터가 아래 주장을 내렸고, 당신의 임무는 이 주장을
**깨뜨리려 시도**하는 것이다 (스틸맨 후 최강 공격 — 확인편향 금지, 불확실하면 REFUTE 쪽으로).

## 검증 대상 주장 (오케스트레이터 판정)

"반증이론 트랙의 축척 추정 셀(C1)이 두 번의 루프 반복 끝에 봉인 게이트를 전부 충족했다:
① HIGH 신뢰 커버리지 4스케일 각각 0.80 (봉인 게이트 ≥0.60) ② HIGH 정확도 1.0 (게이트 ≥0.95,
상대오차 5% 이내) ③ 지정 mutation family 11/11 커버(단일-스팬 10 장면 복원) ④ 충실도 KS 0.0403/
TV 0.000212 (게이트 0.20/0.10) ⑤ 진리 무접촉(추정기 접근 키 = anchors 단독, pair-label 순열 전후
digest 동일) ⑥ 교란 4종에서 신뢰도·상태 상승 0건(역방향 전이 티켓 수리 확인) ⑦ 결정적 재현(재실행
바이트 동일). 루프 경로는 정직했다: L1(전 장면 앵커 5~8)은 HIGH 게이트를 채웠으나 단일-스팬 가족
소멸(도시에 봉인 요구 위반)로 오케스트레이터가 목표 도달 주장을 기각했고, L1b(혼합 모집단 40+10)로
수리했다. 봉인 밴드는 어느 반복에서도 이동하지 않았다."

## 증거 사슬 (전부 READ-ONLY)

- 도시에 원문(봉인 조문의 SoT): `D:\dev\99_tools\autocad-sdk-router\reports\e2\dossiers\feyerabend_P2.md`
- C0: `D:\dev\99_tools\autocad-sdk-router\tools\e2\cells\feyerabend_c0.py` + `reports\e2\cells\feyerabend_c0\`
- C1: `tools\e2\cells\feyerabend_c1.py` + `reports\e2\cells\feyerabend_c1\`
- L1(기각된 반복): `tools\e2\cells\loop_l1.py` + `reports\e2\cells\loop_l1\`
- L1b(주장 대상): `D:\runs\e2_program\cells\loop_l1b\` (loop_l1b.py · c0v3_numbers.json ·
  c1v3_results.json · REPORT.md · evidence.xlsx)
- 프로그램 저널(맥락): `reports\e2\PROGRAM_JOURNAL.md` 6.5장

## 공통 규칙

- 재실행 허용(권장): python으로 selftest·전량 재실행·수치 재계산 자유. 단 산출물 수정 금지 —
  재실행 출력은 당신의 산출 디렉토리에만.
- 지정된 당신의 시야(발사 프롬프트에 명시)에 집중하되, 시야 밖 치명 결함도 발견하면 기록.
- 산출: 지정된 출력 파일에 — 발견 사항(심각도순, 각각 근거 경로·행번호·재계산 수치) + 마지막 줄
  `VERDICT: CONFIRM` 또는 `VERDICT: REFUTE` (+ 한 줄 사유). 근거 없는 CONFIRM 금지.
- git 금지. 서브에이전트 금지. 원본 CAD·CubiCasa test 접근 금지.
