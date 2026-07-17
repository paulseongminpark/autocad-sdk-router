# PANEL_REPORT — 벽 의미 탐지기 방법론 (2026-07-17)

Phase A 블라인드 4석 (platt_strong_inferencer=Fable max · doe_experimentalist=Opus 4.8 max · calibration_forecaster=GPT-5.6-sol xhigh · feyerabendian_dissenter=Grok 4.5) + Phase B red_teamer(Opus 4.8 max). 제안 26건 → 클러스터 11개. **전 항목 candidate — 채택은 Paul.** red team 티켓 34건 전량 OPEN.

## 프로그램 선결 3건 (어느 밴드보다 먼저)

1. **PR-1 벽 합성 생성기 실구축 + 충실도 게이트** — red team 공격 B(lands): `synthetic_truth.py`는 dimension 전용, **벽 코드 0**. 전 좌석이 1차 게이트로 삼은 synthetic truth가 아직 존재하지 않는다. 생성기를 만들되, divergent-20의 실현상(POLYLINE/블록/비평행 조각)을 재현하는 fidelity 게이트(T2)를 통과해야 1차 판별기 자격.
2. **PR-2 대리(truth proxy) 독립성 감사** — red team 공격 A(sev 0.75, 최우선 T1): {합성·외부셋·metamorphic·silver} 4대리가 같은 "평행 이중선" prior를 공유하면 합치는 확증이 아니라 편향 증폭. 동일 def에서 3원 불일치 구조를 측정 (doe P3와 병합).
3. **PR-3 counsel 서면 확인** — 공격 D(lands, T5): FloorPlanCAD/CubiCasa **NC 라벨 + 원 도면 권리 자체가 미해결**(R23 top unknown, R12 kill risk). 외부셋 학습 arm 착수 전 서면 클리어. + T34: 인용 R-레인 6개 전부 experiment_executed:false — load-bearing 인용 재-status.

## TOP (즉시 추진 후보)

- **CL-A E1 법의학 감사 (dissolver)** [platt P0 · red team T3/T4/T8이 하드 선결로 승격] — top-20+대조 20 def에 결정론 스크립트 1개: 인용 핸들 실재성·엔티티 히스토그램·INSERT 깊이·bbox 단위 감사·n_h_ornith=10 나열-지시 아티팩트 판정 + **정렬-키 아티팩트 재계산**(공격 C lands: top-20 단일종은 `_score_divergence` 정렬 설계의 산물). 로컬 CPU <1h. E1 불일치가 계측 아티팩트면 고가 실험 전체가 불필요해진다.
- **CL-B 커버리지-완전 결정론 v1** [platt P1 + calibration P1(다증거 격자) + feyerabend P6(INSERT 월드좌표 전개 — 코드 확정 결함 정타) + feyerabend P2(mm 절대대역→치수-정박 상대대역) + doe P2(Taguchi 노브 강건화)] — LWPOLYLINE/MLINE/ARC 정규화 + transform 전개 + 단위 정박 + 정션 후필터 + 다증거 격자. 대부분 로컬 CPU. 티켓: v0 베이스라인 선계측(T9/T21), quadratic 후보 폭발 상한 사전등록(R12).
- **CL-C 벽 합성 truth + WSD-EVAL-v1 팩 동결** [calibration COMMON RESOLUTION CONTRACT + S/F/M 팩 + platt/doe 생성기 확장] — per-handle `wall_member(h)` 평가 단위 고정, 도면/firm 단위 분리, hidden mutation family 시험 전용. = PR-1의 실행체.
- **CL-D metamorphic 배터리** [platt P3 + doe P5 + calibration M] — 강체변환·스케일·단위·explode·레이어개명 불변. 라벨 0으로 145장 전체에 적용 가능한 유일 공용 심판. **의무 수정**(공격 F lands): 0벽/전벽 sentinel + recall 최저선을 랭킹 사용 전 탑재(T7) — 위반율-only 밴드는 "0벽 탐지기"를 통과시킨다.
- **CL-E truth-source 교차요인 메타실험** [doe P3 + T1/T17] — train{합성,외부,silver}×eval{합성,외부,silver,metamorphic}. 대각↑/비대각↓ = 부트스트랩 사슬 미폐합의 계량 증거. 전이만이 아니라 **동일 def 불일치 구조**(독립성)까지.

## VIABLE (조건부 — 명기된 게이트 통과 시)

- **CL-F 학습 사다리: 고전ML→PU→GNN** [platt P2 + calibration P2/P3 + doe P1] — 조건: CL-C 팩 존재 + Graph IR adjacency 완전성 감사 선행(T10/T23, R23 disputed) + 이름/레이어 mask-ablation 암 의무 + 로지스틱/GBDT가 먼저 뛰면 GNN 불요(Occam 사다리). calibration P2의 "P1 대비 lift" 밴드는 P1 통과가 하드 선결(T22).
- **CL-G 래스터/VLM 이중 트랙** [platt P5 + calibration P4/P5 + doe P6] — 조건: 픽셀→핸들 역투영 exact 하네스 합성 선검증(T24, R23 CRS kill risk) + NC counsel(PR-3) + 프런티어 배심 silver는 **E1.5 B1≥0.70 AND B4≥0.70** 통과 시에만(정확 인용은 calibration — 모순 #1 참조) + DGX Ornith vision 지원 여부 선확인(T13).
- **CL-H RL 자리 판별** [platt P4 + doe P4 + calibration P6 + feyerabend P4] — 4석 전원이 같은 분할에 수렴: per-handle 분류=supervised, **집합-조립/획득/라우팅=RLVR·bandit 후보**. 조건: ① verifier false-accept ≤0.01 선계측(T26 — RL 계열 전체의 사활 게이트) ② 평가 단위를 per-handle로 선언하거나 집합-조립을 별도 산출물로 격리(공격 E lands, T6) ③ **학습 0의 greedy vs beam 보상지형 프로브가 먼저** — greedy≈상한이면 훈련 전 RL kill(최저가 판결). C07은 이 실험이 증거로 종결한다.
- **CL-I 관례-prior 계측화** [platt P6 + feyerabend P7] — 조건: firm-특유 벽레이어 lexicon 구축·동결(T14/T33) + 프로젝트 단위 스플릿 + 동어반복 토큰 분리 보고. 산출: E1 판정자의 이름-prior 탑승 여부 정량화(silver 독립성 감사 겸용).
- **CL-J face/room-first 역전** [feyerabend P1] — 관측 언어 자체를 깨는 최강 반문. 조건(T27 MED-HIGH): cheapest probe를 합성이 아닌 **실 messy divergent-20에서** — R16 KR2(오픈플랜)·KR4(messy) 충돌을 정면 시험. GEOS(비GPL) 엔진 명시.
- **CL-K anti-silver 통제 arm** [feyerabend P3] — gate-only vs silver-distill 1-epoch 대조를 CL-F에 상설 통제로 편입. 반대의견(모순 #2)의 실험적 보존.

## PARKED (사유 명기)

- **doe P1 마스터 스크린 16런 풀버전** — Res IV alias 산술은 옳으나(red team B2 반등) representation×truth가 family×self-training과 confounded + learned 셀 seed-confounded(T15). CL-C 완성 + seed 예산 명시 후 재개.
- **feyerabend P5의 "래스터 본선" 프레임** — 메커니즘은 CL-G에 흡수. "본선" 주장 자체는 래스터가 CL-B 커버리지 수정으로 이미 회수되는 zero-pair를 **넘어서는** 회수를 실증할 때까지 PARK(T31).

## 반대의견 원장 (해소 안 됨 — 원문 보존, 평균 금지)

1. **silver 게이트 식별자**: platt P2 "silver 암 활성 조건 = E1.5 **B1 ≥ 0.70**" vs calibration P5 "**B1≥0.70 및 B4 Pearson≥0.70**" vs feyerabend "**B4가** Pearson≥0.70이면 SILVER 자격". 원문 prereg_e15.json 기준 **calibration이 정확** (B1=well-posed, B4=silver 자격). platt 인용은 게이트 식별자 수정 대상(T10 부수).
2. **silver = 신호 vs 오염원**: 다수(platt/doe/calibration) "게이트된 silver는 학습/크로스체크 신호" vs feyerabend P3 "E1.5 silver를 탐지기 학습 타깃으로 쓰지 않는다 … 탐지기는 LLM과 … **체계적으로 불일치해도 살아남는 것**을 목표로." → CL-K 통제 arm으로 실험적 보존.
3. **arrangement 방향**: calibration P1 "후보 중심선을 planar arrangement에 투영"(R16 정합: centerline→rooms) vs feyerabend P1 "R16의 centerline→room을 **역전**: room/face가 먼저이고 벽은 dual의 bridge." → CL-J 프로브가 판별.
4. **VLM 프레임**: 3석 "프런티어=배심원, 결정론 게이트=SoT" vs feyerabend P5 "**래스터 본선 학습** + 벡터 게이트". → PARKED 조건부.
5. **gap 밴드**: doe P2 "절대 밴드 robust-최적화" vs feyerabend P2 "절대 mm 밴드는 **단위-관례 유물**, 치수-정박 상대 대역으로". → 상대 vs 절대 A/B를 Taguchi에 선행(T16).

## 다음 프로브 큐 (좌석 kill_condition 승계, 최저비용 우선)

1. CL-A 법의학 스크립트 (로컬 CPU <1h) — T3 재계산 + T4 ornith 원시 조달 포함
2. CL-D 2관계 프로브 + 0벽 sentinel (1일, 로컬)
3. CL-B divergent-20 재실행: 정규화 + INSERT folded/unfolded 10 def + 단위 정박 30 def (1–2일, 로컬)
4. CL-E 동일-def 3원 불일치 구조 (로컬)
5. CL-H greedy vs beam 보상지형 (1일, 학습 0)
6. CL-G 5a: divergent-20 렌더 + 프런티어 VLM 1패스 (1일, 소액 API) — CL-A와 교차 대조(이름-맹 판정)
- 병행 조달: PR-1 생성기 구축 · PR-3 counsel · E1.5 B1/B4 판정(비행 중)

## OPEN 티켓 (red team 34건 전량 미해소)

수렴급 T1–T7(공격 A–F) · per-proposal T8–T33 · 프로그램급 T34. 최우선 severity: **T1(대리 독립성, 0.75)** > T2(생성기 부재, 0.70) > T5(라이선스, 0.65) > T3=T6(0.60) > T4(0.55) > T7(0.50). 상세: `seats/red_teamer.md` §2–3.

---
좌석 원문: `seats/{platt_strong_inferencer, doe_experimentalist, calibration_forecaster, feyerabendian_dissenter, red_teamer}.md` · 과업 계약: `task.md` · 증거 미러: `evidence/`
