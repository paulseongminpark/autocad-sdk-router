# E2 벽 의미 탐지기 — 최종 통합 실험 프로그램 계획 (병합판)

작성: 2026-07-18. 병합 규칙: **기반 = PLAN_sol 구조** (F00→F06 topology, 소비자별 게이트, canonical world-IR 선결, UNIT→TAG DAG, vision/RL/convention 분리, kill ledger K01–K08, 역색인, blocked-자원 규율) + **접붙임 = PLAN_claude 우세 판정분** (admission 독립 셀, fey_P6 C4 정량 밴드, 밴드/발사상태 이원화, 단일점수 금지·contingency 공개) + **공동 결함 2건 수리** (doe_P5 GPU/DGX 어댑터 큐 배치, A61 이중 밴드 PAUL-DECISION 처리).

문서 우선순위: **본 문서 > PLAN_sol §1 행 명세 > 도시에 원문**. 본 문서에 "승계"로 표기된 셀의 지표·합격선·킬·예산 전문은 PLAN_sol §1의 해당 행이 정본이며, 본 문서의 변경분만 그것을 덮어쓴다. 수치는 전부 도시에 원문 제안값 또는 세션 실측(v1 F1 0.2358 · HGB F1 0.517/AUC 0.9215 · 셔플 AUC 0.375 · B3 zero_frac 0.2135 · B5 Pearson 0.2911 · 최대 def 412,775 seg)이다.

## 0. 밴드와 발사상태 — 이원화 (병합 결정)

두 비판이 합의한 수리: 밴드 하나로 "가치"와 "지금 발사 가능"을 겸하게 하지 않는다.

- **밴드 (가치 축, sol 배정 승계)**: TOP=공용 진실면·가장 싼 판별·최종 거버넌스 / VIABLE=조건부 / PARKED=전제 붕괴·자원 차단·더 싼 판별 대기.
- **발사상태 (스케줄러 정본, claude 접붙임)**: `READY`(선행 없음/충족) · `GATED(셀)`(선행 판정 대기) · `BLOCKED_RESOURCE`(DGX 불통) · `BLOCKED_APPROVAL`(API 미결재) · `BLOCKED_ASSET`(외부 자산 부재). 실행 스케줄러는 발사상태만 본다 — 미해결 게이트 셀은 절대 발사하지 않는다 (sol 운영규칙 승계).

## 1. 최종 셀 매트릭스 — 42셀

표기: 변경 없는 셀은 "승계" + 요지만. ★=신설/변경 셀 (전문 명세 포함).

### 1.1 공용 기반·거버넌스 (10)

| 셀 | 밴드 | 발사상태 | 큐 | 내용 | 의존 |
|---|---|---|---|---|---|
| F00 CONTRACT-FREEZE | TOP | READY | CPU-PAR | 승계 — 권리·lineage·split·baseline·evaluator·test ledger·xlsx schema 봉인 | 없음 |
| F01 E1-HANDLE-FORENSICS | TOP | GATED(F00) | CPU-PAR | 승계 — O-A/O-B/r_pair/unit factor 결정 lattice, CPU `<1h` | F00 |
| ★S07 SILVER-ADMISSION | TOP | GATED(F00) | CPU-PAR | **신설 (claude SIL-G 접붙임)**: 기존 E1.5 아티팩트에서 `E15_B1`/`E15_B4`를 정확 재산출하는 독립 CPU 셀 (`<2h`, API 호출 0). 합격선: `B1≥0.70 ∧ B4 Pearson≥0.70` (AND). 원장 C09 준수 — B5 `0.2911`에서 B4를 추정하지 않으며, 재산출 전 admission은 OPEN/BLOCKED이지 PASS도 FAIL도 아니다. 산출은 T20 silver축·T21·R53·R55의 개폐 판정. R53(PARKED) 내부에서 분리한 이유: CPU-싼 판정이 VIABLE 셀 다수를 개폐하므로 조기 독립 실행이 맞다 (양 비판 합치) | F00; E1.5 아티팩트 |
| ★F02 WALL-GENERATOR-QUAL | TOP | GATED(F00,F01) | CPU-PAR | 승계 + 명시: fidelity는 **소비자별 3단 게이트 동시 산출** (calibration core `KS≤0.10/TV≤0.10` · CL-B `KS≤0.2/TV≤0.1` · face exploratory `KS_max≤0.30/TV≤0.20`), 단일 수치 봉인 금지, face-only 통과는 상위 두 claim의 자격이 아님 (원장 C01 판결 그대로) | F00; F01 strata |
| ★F03 CANONICAL-WORLD-IR | TOP | GATED(F00,F02) | CPU-PAR | 승계 + 2건 수정: ① **fey_P6 C4 정량 밴드 복원 (claude 접붙임)** — 1.dwg 실도면 프로브: "INSERT 전개가 적격 def 중 **≥30%에서 신규 cross-scope pair를 생성 (최소 3/10)**"을 F03의 실도면 판별 밴드로 추가; 0건이면 현 코퍼스에서 world-assembly 이득 주장 금지 (인프라 PASS와 별도 판정). ② 출처열을 역색인과 정합화 — platt_P1은 G1만 F03 (E0/E1→D11, E2/E3→D12, E4→D10) | F00; F02 fixture |
| F04 COMMON-METAMORPHIC-JUDGE | TOP | GATED(F02,F03) | CPU-PAR | 승계 — 공용 relation registry/judge + 방법별 게이트 분리(C11). doe_P5의 **effects/confirmation(발견 기능)을 명시 산출물로 복원**: transform×family 상호작용 표는 F04의 필수 보고서다 (판정 기능에 흡수 금지). CPU part = doe_P5 F01–F14(결정론+고전ML) | F02; F03; R50(래스터축) |
| ★F04G META-GNN-FAMILY | VIABLE | GATED(F04,G41) | **GPU-LOCAL-SERIAL** | **신설 (공동 결함 ① 수리)**: doe_P5 F15–F21 — GNN family 7 transform 셀, 도시에 원문 캡 **RTX 4h/셀**. 발사 시점: 해당 GNN 체크포인트 동결 직후·그 family의 F06 진입 전 (부동 슬롯). G41이 발사되지 않으면(M30 Occam gate 닫힘) 자동 소멸 | F04; G41 체크포인트 |
| ★F04V META-VLM-FAMILY | PARKED | BLOCKED_RESOURCE | **DGX-QUEUE** | **신설 (공동 결함 ① 수리)**: doe_P5 F22–F28 — VLM family 7 transform 셀, 도시에 원문 캡 **DGX 4h/셀**. VLM 계열(R53/R54/R55)의 F06 진입 전 필수. DGX 소생 전 BLOCKED — 로컬 대체 PASS 금지 | F04; R53/R54 모델 |
| F05 SCALE-RESOURCE-GATE | TOP | GATED(F03) | CPU-PAR | 승계 — p95/RSS/VRAM envelope 방법별 유지 (P1 `p95≤60s`/`RAM≤32GB`, P6 stress `48GiB`, GNN `≤48GB`). CPU lane 전면 병렬 금지 — immutable shard·RAM watchdog·동시성 cap (sol 운영규칙 1) | F03; G40(그래프) |
| F06 FROZEN-TEST-ONCE | TOP | GATED(방법별 전 셀) | TEST-ONCE | 승계 — 방법별 frozen resolver·prereg SHA·단발·xlsx·failure witness. 중앙 test ledger(F00)와 방법별 계약 이중 유지. fey_P2 방법은 test 미소비 유지 (원장 C14) | 방법별 전 셀; F00; F04(+family 어댑터); F05 |

### 1.2 결정론·truth·고전 ML (10)

| 셀 | 밴드 | 발사상태 | 큐 | 내용 | 의존 |
|---|---|---|---|---|---|
| ★D10 RELATIVE-UNIT-A/B | TOP | GATED(F00,F02,F03) | CPU-PAR | 승계 + 출처열 정정: `calibration_P2` C4/C6 제거 (역색인 정본: C3–C5→M32, C6→F04/T20). 4-scale paired A/B: relative F1 `≥0.85` 전 스케일, anchor HIGH `≥95%` within `5%`/coverage `≥0.60`, real `Pearson delta ≥+0.05` bootstrap lower `>0` | F00; F02; F03 |
| D11 DETERMINISTIC-LATTICE-PROBE | TOP | GATED(F01–F04) | CPU-PAR | 승계 — S candidate recall `≥0.98`, false merge `≤0.05`, hidden S F1 `<0.85` kill | F01–F04 |
| D12 RESOLVER-MATCH-ILP-CAL | TOP | GATED(D11,F05,T20) | CPU-PAR | 승계 — `REL≤0.03`/`RES≥0.02`(P1 고유), `AUPRC−v0≥0.15`, `P≥0.90@cov≥0.50` | D11; F05; T20 자격 truth |
| D13 TAGUCHI-ROBUST-KNOBS | VIABLE | GATED(D10) | CPU-PAR | 승계 — **UNIT→TAG DAG 확정** (fey_P2 금지 조문; K04). D10이 representation 봉인 후 L9×5→L9×40(360 평가)→3×3→hold-out firm | D10; F03; F04 |
| D14 FACE-POCHE-BRIDGE | VIABLE | GATED(F02–F04) | CPU-PAR | 승계 — face-first 반대가설 독립 트랙: real containment median `≥0.40`, HGB face lift `≥0.03` 또는 conditional precision `≥0.50`, `<0.15` 약화 | F02; F03; F04; F01 strata |
| ★T20 TRUTH-SOURCE-CROSS | TOP | GATED(F00,F02,F04,R50; silver축 GATED(S07)) | CPU-PAR | 승계 + 접붙임 2건 (sol 비판 자인 사항): ① **단일 "독립성 점수" 발명 금지** ② **same-item disagreement contingency 전표 공개 의무** — 요약 통계로 대체 불가, T20의 필수 산출물. off-diagonal `Drop≤0.20`, chain closure CI upper `≤0.20`. silver축 개폐는 S07 | F00; F02; F04; R50; S07(silver) |
| T21 ANTI-SILVER-ABLATION | VIABLE | GATED(F02,F04,S07) | GPU-LOCAL-SERIAL | 승계 — gate-only meta advantage `≥0.10`, S NI `−0.02`, CubiCasa `≥0.517`, Pearson `≤0.35` 보조. fey_P3 C5 REAL-384은 명시 산출 행으로 보존 | F02; F04; F00; S07 |
| M30 CLASSICAL-OCCAM-LADDER | TOP | GATED(F00,F03,T20) | CPU-PAR | 승계 — graph-stat classical `+0.10`이면 GNN 정지 (Occam gate; 원장 C12) | F00; F03; T20 |
| M31 PU-ANCHOR-LF | VIABLE | GATED(F02,R50(F축)) | CPU-PAR | 승계 — anchor purity, LF family folding; F metric은 R50 exact contract 후만 | F02; F00; R50(F) |
| M32 PU-MODEL-CAL-FINAL | VIABLE | GATED(M31,M30,F04,T20) | CPU-PAR | 승계 — `P≥0.92@R0.50`, OOD drop `≤0.10`, `REL≤0.03/RES≥0.02`, CI low `>0` | M31; M30; F04; T20 |

### 1.3 그래프·래스터/VLM (9)

| 셀 | 밴드 | 발사상태 | 큐 | 내용 | 의존 |
|---|---|---|---|---|---|
| G40 GRAPH-ADJACENCY-AUDIT | TOP | GATED(F03,F05) | CPU-PAR | 승계 — **이중 판정 출력** (원장 C02): `0.98≤recall<0.995`면 calibration-GNN만 자격, 전 경로 자격은 `≥0.995`. 부분 생존 정보 보존 | F03; F05 fixture |
| G41 CHEAP-GRAPHSAGE | VIABLE | GATED(G40,M30,F04,T20) | GPU-LOCAL-SERIAL | 승계 — lift `≥+0.10`, context CI lower `>0`, name `<0.05`; 캡 18/12/6 GPU-h; M30 gate 닫히면 소멸 | G40; M30; F04; T20 |
| G42 SSL-GNN-FULL | PARKED | BLOCKED_RESOURCE | DGX-QUEUE | 승계 — `AUPRC_F≥B*+0.05`, `RES≥0.03`(GNN 고유; 원장 C03), node `≥0.92`/pair `≥0.80` | G41; T20; F02; R50; DGX |
| R50 RASTER-RIGHTS-BRIDGE | TOP | GATED(F00,F02,F03) | CPU-PAR | 승계 — counsel/권리 gate는 래스터·VLM 전 경로 공통 선결 (OPEN/BLOCKED/FAIL 구분); exact Jaccard `1.0`/phantom 0, MAPACC `≥0.995`, oracle F1 `<0.4` common kill | F00; F03; F02 |
| R51 LOCAL-RASTER-SEGMENTER | VIABLE | GATED(R50) | GPU-LOCAL-SERIAL | 승계 — FPC IoU `≥0.60`(fey)/`≥0.70`(platt) 소스별 게이트 유지; probe `≤1일`+`2–3 GPU일` | R50; F00; GPU slot |
| R52 RASTER-VECTOR-COMPLEMENT | VIABLE | GATED(R51,D12,F04,T20) | GPU-LOCAL-SERIAL | 승계 — recall delta `≥0.25`, CL-B paired lower `>0`, NC 제품 격리 checksum 0 | R51; D12; F04; T20 |
| R53 FRONTIER-VLM-JURY | PARKED | BLOCKED_APPROVAL + GATED(S07) | FRONTIER-API | 승계 — admission 산출은 S07로 이관, R53은 승인 후 frontier screen만 (family-aware consensus P5-C 포함, 원장 K03). envelope `20 valid/1일` 또는 `150 calls` 중 사전 승인 1개 | S07; F01; F00; R50; API 결재 |
| R54 LOCAL-OPEN-VISION-NO-SILVER | VIABLE | GATED(R50,F02,F04,M30) | GPU-LOCAL-SERIAL | 승계 — API와 무관한 local open-finetune 6셀 (silver 금지): val F1 `≥0.517` 또는 R-SYN·R-META 동시 우세; LoRA **셀당** `0.5–2일` (6셀 = 3–12 GPU일 전개 표기) | R50; F02/F04; M30; GPU queue |
| R55 SILVER-STUDENT-EXPANSION | PARKED | GATED(S07)+BLOCKED_RESOURCE(full) | DGX-QUEUE (로컬 probe는 GPU 큐) | 승계 — S07 admission PASS 후에만; student AUPRC lift `≥0.03`, anti-silver delta 생존 | S07; T21; R50; DGX(full) |

### 1.4 획득·집합 조립·관례·확장 (13)

| 셀 | 밴드 | 발사상태 | 큐 | 내용 | 의존 |
|---|---|---|---|---|---|
| A60 VERIFIER-REWARD-SOUNDNESS | TOP | GATED(F02,F04) | CPU-PAR | 승계 — FAR `≤0.01`/FRR `≤0.05`, reward-family/hidden-family 방화벽 (Cell-A 포함) | F02; F04; F00 |
| ★A61 FIXED-ROUTING-BANDIT | VIABLE | GATED(A60,M30,F05) | CPU-PAR | 승계 + **공동 결함 ② 수리**: 두 합격선(calibration `saving≥20% ∧ AUPRC drop≤0.01` / feyerabend `saving≥30% ∧ F1 drop≤0.02`)은 **per-claim 귀속** — 각 도시에 claim은 자기 밴드로만 판정하고 교차 인용·합산 금지. **프로그램의 bandit "채택" 기준선은 `PAUL-DECISION-1`** (실행 전 봉인, §5). 공용 킬(`saving<10%`)은 유지. fey_P4 S0(학습 0 대조)·X(실측 Pareto 진단)는 본 셀의 명시 선행/부속 산출로 보존 | A60; M30 frozen classifier; F05 |
| A62 HORIZON-ONPOLICY-PROBE | VIABLE | GATED(A61,A60,F02) | GPU-LOCAL-SERIAL | 승계 — `utility_RL/utility_bandit≥1.05`; Cell-G 실도면 진단 포함 (불일치 시 "실환경 절감" 주장 금지) | A61; A60; F02 |
| A63 SET-ASSEMBLY-ZERO-LEARNING | VIABLE | GATED(A60,F03/G40,M30) | CPU-PAR | 승계 — beam−greedy `<0.01` ∧ upper gap `≤0.01`이면 RL kill (훈련 전) | A60; F03/G40; M30 |
| A64 SET-ASSEMBLY-RLVR | PARKED | GATED(A63 생존) | GPU-LOCAL-SERIAL | 승계 — `mean_seed(F1_RL)−F1_beam≥+0.05 ∧ violation Δ≤0`; **arm×seed 축 명시**: arm/seed당 `24h cap`, 3 seed 로컬 순차 | A63; A60; G40; T20 |
| A65 FULL-RL-FACTORIAL | PARKED | BLOCKED_RESOURCE | DGX-QUEUE | 승계 — terminal-label RL 제외(K05), A×C null ∧ supervised 지배면 C07 지지·RL 하차 | A60–A63; F02; DGX |
| C70 LEXICON-PROJECT-PROBE | VIABLE | GATED(F00,F01) | CPU-PAR | 승계 — lexicon freeze·PID 감사·convention-only cheapest probe (정확도 채택 셀 아님) | F00; F01 |
| C71 CONVENTION-ONLY-H3 | VIABLE | GATED(C70) | CPU-PAR | 승계 — 측정기 (기하 의도 배제): cross AUC `≥0.75` 지지 / `≤0.55` kill; E1 corr `≥0.70`이면 silver 독립성 강등 | C70; F00; M30(STK) |
| C72 GATE-CONSTRAINED-CONVENTION | VIABLE | GATED(F02,F03,M30/D12) | CPU-PAR | 승계 — 배포 후보 (gate 내부 재순위화만): aligned ΔF1 `≥+0.15`, misaligned delta 0, gate 우회 1건 즉시 kill | F02; F03; frozen gate |
| ★C73 INDIRECT-PRIOR-LOCAL | VIABLE | GATED(C72) | CPU-PAR | **분할 (claude 비판 반영)**: fey_P7 E2–E4 로컬부만 — EB/MI reliability, convention 셔플, 384 fit/freeze. 로컬 자산으로 완결 가능 | C72; C70/C71 |
| ★C74 PROJECT-TRANSFER-ONESHOT | PARKED | **BLOCKED_ASSET** | CPU-PAR | **분할 신설**: fey_P7 E5 — fully-frozen cross-project ΔF1 `>0` 단발. 독립 라벨 프로젝트(≥2) 부재가 기지 사실이므로 자산 확보 전 PARKED (원문 자체 조문: "metadata+label project 부재면 PARK") | C73; 외부 라벨 프로젝트 |
| P80 BROAD-2POWER-SCREEN | PARKED | BLOCKED_RESOURCE + GATED(F02,R50,T20) | DGX-QUEUE | 승계 — doe_P1 16셀: confound 해소·소스 자격 후 deterministic 8 prefix부터 | F02; R50; T20; M30/G41; DGX |
| P81 FULL-VLM-FACTORIAL | PARKED | BLOCKED_APPROVAL | FRONTIER-API | 승계 — R53/R54 신호 후에만; frontier는 B1∧B4 | R50; R53/R54 결과; API; DGX(full) |

## 2. Kill ledger — K01–K08 전량 승계

PLAN_sol §2 원문 그대로 유효: K01 B1-fail 팩의 truth/reward 사용 금지 · K02 raster mask의 truth 승격 금지 · K03 E1.5 5기의 5-독립표 합산 금지 · K04 D10 전 절대-mm Taguchi 금지 · K05 fixed-label RL 본선 금지(음성 대조군 1회만) · K06 handle/path/vendor/누설 토큰 primary feature 금지 · K07 test 재실행·test 기반 선택 금지 · K08 최대 def all-pairs O(n²) 금지.

## 3. 실행 페이즈·DAG (sol §4 승계 + 삽입 3건)

Phase 0 (F00 ∥ F01 ∥ **S07**) → Phase 1A 구현 (F02·F03·F04·F05·G40·R50·A60 병렬, 학습 0) → Phase 1B 자격 ("구현 완료는 PASS가 아님") → Phase 2 값싼 판별 (D10→D13 · D11→D12 · D14 · T20 · M30→M31→M32 · A61·A63 · C70→C71 ∥ C72→C73) → Phase 3 GPU 직렬 큐 → Phase 4 조건부 확장 (DGX/API) → Phase 5 확인 (F06).

**GPU-LOCAL-SERIAL 순서 (수정)**: T21 → G41 → **F04G**(G41 체크포인트 동결 직후 부동 슬롯) → R51 → R52 → R54 → A62 → A64. 한 job만 train, kill 즉시 후속 취소 (sol 운영규칙 2).
**DGX-QUEUE 순서 (수정)**: G42 → R55 → A65 → P80 → **F04V**(VLM family의 F06 전 필수). 전부 `BLOCKED_RESOURCE`, local 대체 PASS 금지 (운영규칙 3).
**DAG 추가 간선**: `S07 → T20(silver축)/T21/R53/R55` · `G41 → F04G → GNN-family F06` · `R53/R54 → F04V → VLM-family F06`.
운영규칙 1–5 (immutable shard·RAM watchdog·one-train·BLOCKED 상태·실패도 xlsx row) 전량 승계.

## 4. 모순 원장 — C01–C11 승계 + 3건 추가

C01 fidelity 3벌(소비자별 유지) · C02 adjacency 0.98/0.995(이중 판정) · C03 RES 0.02/0.03(방법별) · C04 absolute vs relative(D10 선행) · C05 raster 본선/한표(제안·표 분리) · C06 FPC mask vs handle truth(축 분리) · C07 RL 적용 범위(K05+분리) · C08 convention-only vs gated(측정기/배포 분리) · C09 B4≠B5(S07 재산출 전 OPEN) · C10 412,775 채택(412,965는 오기 보존) · C11 metamorphic 집계 3단위(각자 판정) — 전량 PLAN_sol §6 원문·판결 그대로.

### C12. GNN 프로그램의 존재 충돌 (Occam) — 추가

> `platt_P2` C1 (도시에 원문): "HistGradientBoosting이 support band를 충족하면 production ladder에서 GNN을 중단한다" (Δ_main `≥+0.10` 기준).

반면 `calibration_P3`는 E4–E7의 SSL GNN full 프로그램(DGX HPO 포함)을 완결 사다리로 제안한다. 이는 파라미터 차이가 아니라 **한 제안의 존재를 다른 제안이 부정하는 충돌**이다.
판결: M30 Occam gate가 개폐를 지배한다. G41/G42/F04G는 M30이 gate를 닫으면 실행하지 않으며, 이 소멸은 calibration_P3의 실패가 아니라 "classical 충분" 판정으로 기록한다. 평균 금지 — 두 제안의 밴드를 섞은 절충 GNN 프로그램을 만들지 않는다.

### C13. RL 생존 밴드의 목적함수 분기 — 추가

세 제안의 합격선이 다르다 (각 도시에 원문 제안값):
> `calibration_P6`: `utility_RL/utility_bandit ≥ 1.05` (획득 utility형) · A61 귀속분 `saving ≥20% ∧ AUPRC drop ≤0.01`
> `feyerabend_P4`: `saving ≥30% ∧ F1 drop ≤0.02` (Pareto형)
> `platt_P4`: `mean_seed(F1_RL) − F1_beam ≥ +0.05 ∧ violation Δ ≤ 0` (조립 성능형)

판결: 모순이 아니라 **서로 다른 질문** (라우팅/획득 vs 집합 조립) — 셀 분리(A61/A62 vs A63/A64)로 보존하고 승리 합산 금지(C07 연장). 단 A61 내부의 calibration/feyerabend 이중 밴드는 per-claim 귀속으로 판정하되, **프로그램 채택 기준선 선택은 PAUL-DECISION-1**이다. 한 런이 한 밴드만 통과했을 때 사후에 유리한 밴드를 고르는 것은 K07급 위반으로 간주한다.

### C14. test 소비 정책의 분기 — 추가

> `feyerabend_P2` (도시에 원문 요지): DIM-bearing 사람 라벨 벡터 test가 존재하지 않으므로 P2를 위해 CubiCasa test 400을 소비하지 않는다 — "test PASS 상태는 존재하지 않는다."

다수 제안은 방법당 단발 test를 계획한다.
판결: F06+K07이 운영을 통일하되, fey_P2 계열(D10/D13 unit 판정)은 **test 미소비를 유지** — 해당 방법의 최종 상태 어휘에 test-PASS가 없음을 F06 원장에 명기한다. test 400은 프로그램 공유 소모성 자원이며 접근은 F00 ledger가 통제한다.

## 5. PAUL-DECISION — 결정 필요 3건 (실행 전 봉인 대상)

| ID | 결정 | 권고 (1줄) |
|---|---|---|
| **PAUL-DECISION-1** | A61 bandit "채택" 기준선: calibration 밴드(20%/0.01)와 feyerabend 밴드(30%/0.02) 중 프로그램의 획득정책 채택 결정을 지배할 기준 | 권고: per-claim 판정은 양쪽 다 수행하되, 채택 결정은 더 엄격한 feyerabend 밴드로 봉인 (채택은 비가역성이 크므로 보수 기준) |
| **PAUL-DECISION-2** | 밴드 의미론: "현재 발사 가능"(claude) vs "조건부 과학 가치"(sol) | 권고: 본 계획의 이원화(밴드=가치, 발사상태=스케줄러 정본) 채택 — 스케줄러는 발사상태만 보고 미해결 게이트 셀을 GATED/BLOCKED로 유지 (sol 규칙) |
| **PAUL-DECISION-3** | 단일 confirmatory 충실도 팩 신설 여부 (현행: C01 소비자별 3단 게이트) | 권고: 현행 3단 유지 — cross-method 성능 비교를 대외 주장할 필요가 생길 때만 단일팩을 별도 결재로 신설 |

## 6. 총예산 요약 (원문 envelope 보존 — 신규 wall-clock 총합 산정 금지)

| 큐 | 셀 수 | envelope (도시에 원문값) | 병목·중단 규칙 |
|---|---:|---|---|
| CPU-PAR | 26 | F01 `<1h` · D10 `<1일` · F03 `6–10 engineer-days` · F04 battery `7–10개발일` · generator `1–2인주` 등 원문값 유지; 병렬이므로 단순 합산 금지 | F02/F03/F04 critical path; RAM watchdog·동시성 cap 필수 (64GB ≠ 무제한 병렬) |
| GPU-LOCAL-SERIAL | 8 | T21 반나절 · G41 ≤18 GPU-h · F04G 4h/셀×7 · R51 `2–3 GPU일` · R54 셀당 `0.5–2일`×6 · A64 arm/seed `24h`×3 seed 순차 | RTX 5070 Ti 16GB 단일 큐 = 운영 병목; 생존 job만 직렬 합산 |
| DGX-QUEUE | 5 | G42 수 GPU-day · A65 `1–2주` · F04V 4h/셀×7 · R55/P80 manifest 보존; 완료시각 미산정 | 연결성 자체가 병목; `BLOCKED_RESOURCE`, local 대체 승격 금지 |
| FRONTIER-API | 2 | R53 `20 valid/1일` 또는 `150 calls` 중 사전 승인 1개; P81은 신호 후 | `BLOCKED_APPROVAL`; 결재 전 paid call 0 |
| TEST-ONCE | 1 | F06 방법당 inference 1회, 재학습 0 | F00 ledger + 방법별 frozen resolver 이중 통제 |

과학적 병목 = `F01/S07 → F02/F03/F04 → R50/G40/A60` 진실면 자격 (sol 판정 승계). 운영 병목 = GPU 직렬화·DGX 불통·API 결재 (독립 큐, 상쇄 금지).

## 7. 26부 §6 원문 셀 → 최종 셀 역색인 (전셀, 감사용 정본)

출처열과 이 표가 어긋나면 **이 표가 정본**이다 (sol판 드리프트 2건 수정 반영).

| 원문 도시에 | 원문 §6 셀 → 최종 귀속 |
|---|---|
| calibration_P1 | C0→F00; C1→F02; C2→D11; C3→F03/D10; C4→D11; C5–C6→D12; C7→F04; C8→F05; C9→F06 |
| calibration_P2 | C0→F00; C1–C2→M31; C3–C5→M32; C6→F04/T20; C7→F06; C8→M32/F00 |
| calibration_P3 | E0→F00/F02; E1→G40/F05; E2→G41; E3→M30/G41; E4→G42; E5→G42/T20; E6→F04/F05; E7→F06 |
| calibration_P4 | P4-0→F00/R50; P4-1→R50; P4-2–P4-3→R51; P4-4→R52; P4-5→F04/R52; P4-6→F06 |
| calibration_P5 | P5-A→**S07**; P5-B/P5-C→R53; P5-D→R55; P5-E→T21/R55; P5-F→M32/R55; P5-G→R55 |
| calibration_P6 | Cell-0/A→A60; B→A61; C/D/G→A62; E→F06; F→A65 |
| doe_P1 | Phase 0→F00; 16 cells·effects/augmentation→P80; confirmation→P80/F06 |
| doe_P2 | C0→D10; C1–C5→D13; C6→D13/F06 |
| doe_P3 | 공통+24 cells→T20; confirmation→T20/F06 |
| doe_P4 | cheapest 4→A61/A63; 본실험 12→A65; hacking 2→A60/A65; confirmation→F06 |
| doe_P5 | 자격·Q0–Q2·F01–F14→F04; **F15–F21→F04G; F22–F28→F04V**; effects/confirmation→F04/F06 |
| doe_P6 | cheapest/frontier 6→R53/P81; open-finetune 6→R54/P81; confirmation/effects→P81/F06 |
| feyerabend_P1 | E0→F02; E1→D14; E2→D14/F04; E3→D14; E4→D14/T20; E5→R52; E6→F06 |
| feyerabend_P2 | C0→F02; C1–C2/C4–C5→D10; C3→F04; conditional one-shot→F06(미소비, C14) |
| feyerabend_P3 | C0→T21; C1→F02; C2–C5→T21/T20; C6→F06 |
| feyerabend_P4 | S0→A61; S0b→A62/A63; V1→A60; B1/B1-shuf/X→A61; R2→A65; H→A60/A65 |
| feyerabend_P5 | P5-00/P5-01→R50; P5-02/P5-03→R51; P5-04/P5-05→R52/T20; P5-06→F04/R52; P5-07/P5-09→R52; P5-08→F06 |
| feyerabend_P6 | P6-C0–C2/C6→F03; **C4→F03(정량 밴드 복원)**; C3→F03/F04; C5→F05; C7→F06 |
| feyerabend_P7 | E0/E1→C72; E2/E4→**C73**; E3→C73/F04; E5→**C74**/F06 |
| platt_P0 | C0–C6→F01 |
| platt_P1 | G0→F00; G1→F03; G2→F02; E0/E1→D11; E2/E3→D12; E4→D10; E5→R52; E6→F05; E7→F04/T20; E8→F06 |
| platt_P2 | G0→F00; G1→G40; C1→M30; C2–C4→G41; C5→G42/T20; C6→T21; C7→F04/F05; T1→F06 |
| platt_P3 | C0→F02; C1–C5→F04; C6→R52/F06; C7→T20 |
| platt_P4 | E0→A60; E1→A63; E2→K05 음성 대조(1회); E3→A64; E4→A60/A64; E5→F06; E6→A61 |
| platt_P5 | G0/V1→R50; V2→R51; V3→R52/T20; V4→R53; V5→R53/R52; V6→R52/F06 |
| platt_P6 | LEX/PID/CP→C70; XP/TAU/E1C/STK/SHUF→C71 |

커버리지: **26/26부 전셀 매핑** (소실 0 — F04G/F04V/S07/C74 신설로 sol판의 흡수 3건·claude판의 소실 다수 전부 명시 귀속).

## 8. 병합 이력 (감사용)

- 기반: `PLAN_sol.md` (판정: 양 비판 합치로 골격 우세) · 접붙임: `PLAN_claude.md` 우세 3건 + 조항 2건 · 수리: 공동 결함 2건 · 원장 +3건 (C12–C14).
- 근거 문서: `CRITIQUE_sol_plan_by_claude.md` (HIGH 2·MED 8) · `CRITIQUE_claude_plan_by_sol.md` (MAJOR_REVISION_REQUIRED; §3 최소 수정 명세는 본 문서의 sol 골격 채택으로 대부분 해소, 공동 결함분은 §1 ★행에 반영).
- 미해결: PAUL-DECISION 3건 (§5) — 봉인 전 해당 셀(A61 채택 판정) 발사 금지.

FINAL_PLAN_COMPLETE
