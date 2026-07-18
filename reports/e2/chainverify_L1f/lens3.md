# lens3 — 회계 · replay 완전성 · 술어 진본성 (fable 좌석 3)

먼저 `D:\runs\e2_program\chainverify_L1f\task.md`를 읽어라. 당신의 시야는 **장부**다. 4차에서
이 시야는 유일한 CONFIRM이었다 — 그러나 그것은 장부가 깨끗했다는 뜻이지 앞으로도 깨끗하다는
보증이 아니다. 이번 장부에서 숫자 하나라도 재구성에 실패하면 REFUTE다.

## 표적

1. **봉인 불변**: `cells\loop_l1f\` 봉인 3파일의 SHA-256을 직접 재계산해 task.md에 인용된 세 봉인
   해시와 대조 (Phase B가 봉인을 건드리지 않았다는 주장의 독립 확증).
2. **replay 완전성**: `replay_delta.json` — 400장면 × 전 필드 = 218,469행이 실제로 존재하고 산식이
   맞는지(장면×필드 전개를 독립 재구성), zero-delta 32,538행 회계, v1/v4/v5 3판 전 버전 델타가
   행마다 실려 있는지 표본 아닌 전수 카운트로.
3. **코호트 밴드 재계산**: HIGH 360/360이 5% 이내 · 최소 coverage 0.800을 raw 레코드에서 독립
   재계산. 봉인 prereg.json의 해당 밴드 조문과 문언 대조 (L1e 승계 밴드 — coverage·정확도·O1/O2
   무손실).
4. **회귀 회계**: REPORT의 모든 카운트(630/641/9/5/11 · 5프로브/747/1494 · 2000/50/44 · 90/0/0 ·
   15/15 · 55행)를 각 JSON 아티팩트에서 재구성. 하나라도 불일치 = REFUTE.
5. **술어 진본성**: `predicate_registry.json`의 15술어 반례를 **실제 재실행**해 15/15 위성립을
   재현 (기록만 믿지 말 것 — 4차 lens3 방법 그대로).
6. **아티팩트 SHA**: REPORT.md 표의 전 SHA 재계산 대조. `evidence.xlsx`의 수치가 JSON 원본과
   일치하는지 표본 ≥50셀.

## 산출

`D:\runs\e2_program\chainverify_L1f\lens3_work\`에 재계산 코드·수치, 최종
`D:\runs\e2_program\chainverify_L1f\lens3_verdict.md` — 판정+class 구분+불일치 목록(없으면 0 명기).
git 금지. 서브에이전트 금지. 대용량 JSON은 스트리밍 파싱으로 (메모리 주의).
