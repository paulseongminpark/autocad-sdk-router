# 루프 패킷 L1c — 추정기 잠복 결함 수리 + 이중 봉인 + 코호트 replay

당신은 E2 프로그램의 계측기 수리 실행자다. 사슬 검증단이 C1 추정기의 **잠복 결함**을 라이브 반례로
증명했다: single-outlier 교란 앵커가 ratio 공간에선 outlier지만 span 공간에선 inlier여서 reference
합의의 n_independent·spatial bin을 불리고, 점수 공식 consensus×exp(−mad/τ)×min(1,n/5)×min(1,bins/3)
이 0.60→0.80으로 올라 0.75 문턱을 넘어 보조 reference_status가 LOW→HIGH로 상승한다 (근거:
`D:\runs\e2_program\chainverify_L1b\lens2_stats.md` F1 — 반드시 읽을 것. 기전 행번호 포함).
L1b에서 0건이었던 것은 수리가 아니라 모집단이 그 입력 형태를 제거했기 때문이다.

## 수리 계약 (eval-repair 거버넌스 — 개선 크레딧 없음)

1. **이중 봉인 선행**: 수리 실행 전에 `prereg.json`(C1 봉인 밴드 전문: HIGH coverage ≥0.60/scale ·
   HIGH 정확도 ≥0.95 · 교란 단조성 = 어떤 교란도 confidence/status/unit_status를 올릴 수 없음) +
   `evidence.xlsx`의 `PREREG` 시트(동일 내용)를 **먼저 생성**하고 그 SHA를 REPORT 서두에 기록
   (도시에 feyerabend_P2.md 738~740행 계약 — L1b까지 누락됐던 절차의 복원).
2. **추정기 수리**: `feyerabend_c1.py`를 수정하지 말고(READ-ONLY) 신규 `feyerabend_c1_v2.py`로 —
   reference 합의 경로에 **교란 단조성 가드**를 구조적으로 도입 (예: reference 합의에 참여하는
   앵커의 ratio-공간 정합 검증 — span-공간 inlier라도 ratio-공간 outlier면 n·bins 계수에서 제외.
   구체 설계는 도시에 §2.3~2.4 조문과 lens2 F1 기전을 근거로 당신이 판단하되, 수리 원칙 명시).
3. **회귀 시험**: lens2의 라이브 반례 입력(lens2_stats.md F1의 재현 절차)을 selftest에 영구 편입 —
   수리 후 그 입력에서 상승 0이어야 한다.
4. **코호트 replay**: 수리된 추정기로 ① L1b 200 IR 전량 재평가(C1v4) ② C1 원본 200 IR(v1 장면)
   재평가 — 수리 전 대비 델타 표. 정상 케이스 수치(HIGH coverage/정확도/추정 오차)가 변하면 그
   변화를 숨기지 말고 전문 기록.
5. `--selftest`: 기존 17종 + 반례 회귀 + 단조성 속성 시험(교란 300종 무작위 생성 — 시드 고정 —
   에서 confidence/status 상승 0 전수 확인).

## 산출물 (전부 아래 디렉토리에만 — repo 수정 금지)

`D:\runs\e2_program\cells\loop_l1c\` 에: `prereg.json`(선행 봉인) · `feyerabend_c1_v2.py` ·
`loop_l1c.py` · `c1v4_results.json` · `replay_delta.json` · `evidence.xlsx`(PREREG 시트 포함) ·
`REPORT.md`(봉인 SHA 서두 기록·수리 설계·반례 회귀 전문·replay 델타 전문·미해결, 마지막 줄
`LOOP_COMPLETE: L1c`)

수치만 — 게이트 판정 출력 금지. git 금지. 서브에이전트 금지. stdlib+numpy(+openpyxl). 원본 CAD·
test 접근 금지. 기존 산출물(c1/l1/l1b) 수정 금지. "바이트 동일" 유의 주장 금지 — 재현 주장은
"휘발 필드(runtime·타임스탬프) 제외 수치 전 필드 동일"로만.
