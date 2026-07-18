# 루프 패킷 L1e — Phase A: 봉인만 산출하고 정지 (외부 증인 절차)

당신은 E2 프로그램의 계측기 수리 실행자다. L1d는 3차 사슬 검증단에 의해 기각됐다 — **먼저 읽어라
(READ-ONLY)**: `D:\runs\e2_program\chainverify_L1d\SYNTHESIS.md` · `lens1_saturation.md` ·
`seat4_sol.md`. 이번 루프 반복(L1e)은 봉인 선행을 외부 증인으로 입증하기 위해 **2단계**로 실행된다.
이 패킷은 Phase A다: **봉인 산출물만 만들고 정지하라. 추정기 코드를 한 줄도 작성하지 마라.**

## 임무 (이것만)

`D:\runs\e2_program\cells\loop_l1e\` 에 다음 2개 파일만 생성:

1. `prereg.json` — L1e 봉인. 반드시 포함:
   - 기존 유지 밴드: scale별 HIGH coverage ≥0.60 · HIGH 정확도 ≥0.95(상대오차 ≤0.05) ·
     정당 장면 무손실(O1/O2 하락 0) · L1b/C1 코호트 replay 델타 전문 공개 의무.
   - **단조성 밴드 (증인 기준 — SYNTHESIS의 문언대로)**: scope = 지정 9-family + 3차 함대 발견
     class(CE-A~F·D1~D4). 상승 발생 시: 교란 후 장면과 관측-동치이고 그 상태를 도시에 의미론상
     정당하게 받는 정직 증인 장면을 제시할 수 있으면 "정보 한계 기록"(게이트 아님), 증인 불가
     (의심 신호 잔존 — 잔존 ratio-outlier·handle 충돌·혼합 공간 흔적 등)면 **위반(허용 0)**.
     증인 판정 절차(관측-동치 정의: 추정기 입력 표면의 전 필드 동일)를 조문으로.
   - 의미론 수리 4항: CE-B2(잔존 의심의 지속 감쇠) · CE-D(단독/공집합 eligible → NONE, 최소 독립
     지지) · D1(handle-집합 기반 부분집합 판정) · D3(연속 감쇠 — 이진 절벽 제거).
   - 속성 시험 pool 의무 구성: 0-절벽 시작·ratio outlier·혼합 공간·handle 충돌·근접-τ 산포 포함,
     시드 고정, 상승의 증인 분류 자동화.
   - selftest 술어 무결 조항: 항진식 금지 — 모든 성공 술어는 반례 입력에서 실패 가능해야 하며
     그 반례를 주석으로 병기.
2. `evidence_sealed.xlsx`의 `PREREG` 시트 (동일 내용; 스프레드시트 런타임 부재 시
   `PREREG_SEALED.csv` + 사유 1줄).

그 다음 두 파일의 SHA-256을 `SEAL_MANIFEST.txt`(3번째 파일, 허용)에 기록하고 **정지**. 다른
파일·코드·실행 일절 금지. REPORT 없음. 마지막 stdout 줄: `PHASE_A_COMPLETE: loop_l1e_seal`

## 금지

추정기 구현·수리 코드·replay·시험 실행 전부 Phase B의 몫이다 (오케스트레이터가 이 봉인을 git
커밋해 외부 증인을 만든 후 별도 패킷으로 발사한다). git 금지. 서브에이전트 금지. repo 수정 금지.
기존 산출물 수정 금지.
