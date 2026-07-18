# lens2 — 공식 구조 · 희석 재공격 · 44건 상승 전수 판별 (fable 좌석 2)

먼저 `D:\runs\e2_program\chainverify_L1f\task.md`를 읽어라. 당신의 시야는 **감쇠 공식과 희석**이다.
4차에서 당신의 전신(lens2)이 T_A 희석 공격(깨끗한 handle 20개 추가로 LOW→HIGH)과 mean-분모
결함을 적중시켰다 — v5의 per-signal floor가 그 class를 정말 봉쇄했는지 깨뜨려 보라.

## 표적

1. **공식 구조 감사**: feyerabend_c1_v5.py의 감쇠 경로 전수 추적 — 후보-수 분모가 어떤 우회
   경로(정규화·가중평균·soft-max·클리핑)로도 재진입하지 않는지. REPORT의 공식 문자열과 실제
   코드가 일치하는지.
2. **희석 재공격**: 4차 T_A/T_A2/T_B/T_C/T_S 하니스(chainverify_L1e\lens2_work\)를 v5에 재실행.
   그 다음 봉인 스윕 밖으로: N∈{100, 400}, 이종 조합(깨끗한 증거를 ratio측/span측/GRID측으로
   나눠 주입), 의심 신호 2개 계층 혼합(Tier-A 잔존 + Tier-B 인접 경계값) 등 신규 희석 변주 ≥30종.
   per-signal floor의 N-불변을 수치로 확증하거나 깨라.
3. **44건 상승 전수 판별** (핵심): 실행자는 2,000-사냥에서 v5 상승 44건이 남는다고 보고했다.
   `fleet_probe_results.json`에서 44건 전부 추출해 각각 판별 — 봉인 조문 기준 (a) Tier-A
   정직-생산가능 잔존이며 floor 이내의 정당한 상승인가, (b) 하나라도 Tier-B 신호 잔존 상승
   (=violation, 봉인 위반)인가. 44건 각각에 대해 근거를 남겨라. 단 1건의 (b)도 REFUTE다.
4. **역방향 이동 창**: 4차 T_B(3.6τ→3.4τ 이동 무조건 인증)가 v5에서 막혔는지 + 경계 3.49τ/3.5τ/
   3.51τ 스캔.
5. **자유 사냥**: 위 회귀와 무관한 신규 공격 class 탐색 ≥1,000 케이스 (시드 명기, 결정적).

## 산출

`D:\runs\e2_program\chainverify_L1f\lens2_work\`에 프로브 코드·수치, 최종
`D:\runs\e2_program\chainverify_L1f\lens2_verdict.md` — 판정+class 구분+44건 판별표+재현 절차.
git 금지. 서브에이전트 금지.
