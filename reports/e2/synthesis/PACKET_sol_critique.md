# 교차 비판 패킷 (sol 5.6 ultra — 종합자 A의 상호검증 임무)

당신은 앞서 `PLAN_sol.md`를 작성한 독립 종합자 A다. 이제 종합자 B(Claude)의 계획을 **적대적으로 검증**하라.
목표는 흠집이 아니라 진실이다 — 동의할 것은 동의하고, 이의는 근거와 함께.

## 입력

- 검증 대상: `D:\runs\e2_dossier_wave\20260718\synthesis\PLAN_claude.md`
- 근거 원문: `D:\dev\99_tools\autocad-sdk-router\reports\e2\dossiers\*.md` (26부 — 필요 시 재확인)
- 당신의 계획: `D:\runs\e2_dossier_wave\20260718\synthesis\PLAN_sol.md` (대조용)

## 검증 관점 (전부 점검)

1. **누락** — B가 빠뜨린 도시에 셀 제안 중 살릴 가치가 있는 것.
2. **잘못된 병합** — 서로 다른 가설의 셀을 하나로 뭉갠 곳 (정보 소거).
3. **자원 오류** — GPU 16GB/RAM 64GB/DGX 불통 전제와 안 맞는 셀 배정·예산.
4. **밴딩 이견** — TOP/VIABLE/PARKED 배정 중 동의 못 하는 것 + 사유.
5. **원칙 위반** — val/test 규율, 사전 봉인, 대조군 의무, 결재 게이트 표기 누락.
6. **모순 원장 갭** — B가 놓친 도시에 간 충돌.
7. **당신 계획과의 구조적 차이** — 두 계획이 갈라지는 지점을 명시적으로 목록화 (어느 쪽이 옳은지 근거와 함께 판정하되, 판정 불가면 "결정 필요"로 표기).

## 산출물 — `D:\runs\e2_dossier_wave\20260718\synthesis\CRITIQUE_claude_plan_by_sol.md`

- 판정 표: {항목, 동의/이의/누락, 근거(도시에 원문 인용 포함), 심각도 HIGH/MED/LOW}
- 구조적 차이 목록 (관점 7)
- 마지막 줄: `CRITIQUE_COMPLETE: sol`

## 계약

git 금지 · 서브에이전트 금지 · 산출 파일 외 수정 금지 · 수치는 원문 인용만.
