# E2 실험 프로그램 통합 계획 — 독립 종합자 B (claude)

작성: 2026-07-18. 입력: 26부 도시에 전부 (§6 전문 CELLS_INDEX 정독 + 셀 내 예산·킬·의존성 명세 — 각 셀이 §4 컴퓨트·§8 킬 조건을 자체 포함하도록 작성돼 있어 셀 단위 판단의 1차 근거로 충분함을 확인).
읽지 못한 부: 없음 (26/26). 단, 원문 §1~§5·§7의 세부는 셀 채택에 필요한 범위(예산·의존·킬)가 §6에 병기된 경우 §6을 근거로 했다.

**설계 원칙**: ① 26개 제안이 각자 요구하는 "공유 선결 게이트"가 대량 중복된다 — 이를 공유 셀로 승격해 1회만 실행 ② 오컴 사다리(싼 단이 비싼 단의 개폐를 결정) ③ test 400은 프로그램 공유 소모성 자원 — 중앙 원장으로 통제 ④ 어떤 셀도 평균으로 구제하지 않음(전부 AND형 밴드).

---

## 1. 통합 셀 매트릭스

### 1.1 공유 게이트 셀 (중복 병합 — 여러 제안이 동일 선결을 요구)

| 셀 ID | 출처 제안 | 가설/기능 | 자원 | 지표·제안 합격선 | 킬 조건 | 예산 | 의존 |
|---|---|---|---|---|---|---|---|
| **GEN-1** 생성기 v2 + 충실도 게이트 | cal_P1(C1)·cal_P2(Cell0)·cal_P3(E0)·fey_P1(E0)·fey_P2(C0)·fey_P3(C1)·platt_P1(G2)·platt_P3(C0)·platt_P5(V1 데이터)·doe_P1(K-SYN)·doe_P4 | 벽 truth+음성(distractor)+ARC/SPLINE/HATCH/nested 다양성을 가진 합성팩을 만들고 fidelity 게이트 통과 | CPU (구현은 함대 위임 가능) | 음성 실재(mixed pack), truth self-check 무오류, 0벽/전벽/혼합 센티널, KS/TV 게이트(§4 모순 1 — 단일 수치로 프로그램 프리레그에서 봉인) | 벽 truth 부재·음성 0 지속·fidelity FAIL 지속 → 합성 의존 전 셀 BLOCKED | 구현 1–2주 상당(함대 분담 시 수일) + 검증 수시간 | 없음 (최우선) |
| **CRS-0** 래스터↔핸들 정합 오라클 | cal_P4(P4-1)·fey_P5(P5-01)·platt_P5(V1) | 픽셀↔핸들 역투영이 model-free로 exact | CPU+GPU 스모크 | MAPACC≥0.995, CRS 오차≤0.5%, phantom=0, handle Jaccard=1.0 | 역투영 모호성 제거 불가·비결정성 재현 | 1일 | 없음 |
| **GRAPH-0** Graph IR 인접성 감사 | cal_P3(E1)·platt_P2(G1) | 후보 그래프가 relation을 ≥0.98/0.995 회수하며 폭증 없음 | CPU | relation recall≥0.98(cal)~0.995(platt — 더 엄격한 쪽 봉인), cap truncation 0, name-rename parity 1.0 | recall 미달·envelope 초과 시 그래프 계열 학습 금지 | 1일 | GEN-1(합성 relation truth) |
| **VER-1** 검증기 건전성 (RL 사활) | cal_P6(Cell-0)·fey_P4(V1)·platt_P4(E0) | mutation pack에서 verifier FAR≤0.01, FRR≤0.05 | CPU | FAR≤0.01 ∧ FRR≤0.05 | FAR>0.01 → **RL 계열 전체 중단** (3제안 공통 조문) | 1일 | GEN-1 |
| **RL-0** greedy vs beam 보상지형 (학습 0) | cal_P6(Cell-C)·fey_P4(S0b)·platt_P4(E1) | greedy≈beam≈상한이면 훈련 전 RL kill | CPU | beam−greedy 이득 존재(각 제안 밴드: ≥1.05 utility / δ≥0.02 / F1≥0.01 — 셀별 병기, 최엄격=platt 판정식 우선) | greedy≈beam → full-RL kill, bandit만 잔류 | 1일 | VER-1 |
| **SIL-G** silver 배심 자격 게이트 | cal_P5(P5-A)·platt_P2(G0)·doe_P6(§6.2) | E1.5 B1≥0.70 ∧ B4≥0.70 충족 여부 판정 | CPU <2h | 두 밴드 AND | 미달 → silver 학습·배심 경로 전체 비활성 (기존 실측 B5 r=0.29는 부정적 신호) | 0.5일 | 기존 E1.5 아티팩트 |
| **LEX-0** 관례 lexicon 동결 | platt_P6(Cell-LEX)·fey_P7(E0) | firm 벽레이어·토큰 목록+동어반복 목록 사전 봉인 | CPU | 해시 고정, tautology 목록 비공집합 | 동결 없이 본실험 → 절차 kill | 0.5–1일 | 없음 |
| **AUD-0** E1 법의학 감사 | platt_P0(C0–C6 전체) | E1 top-20 불일치가 계측 아티팩트인지 판별 | CPU <1h | C1: r_bad≥0.50=O-A / ≤0.10∧r_pair>0.50=O-B | O-B→H0-M kill; O-A→E1 서사 재계측 | 1h | 없음 |
| **TESTLEDGER** test 접근 중앙 원장 | 전 제안 공통 (fey_P2 §6.1의 "P2용 소비 금지" 정신 일반화) | CubiCasa test 400 접근을 방법당 1회, 프로그램 승인 하에만 | – | 접근 카운터 공개, 개봉 전 봉인 해시 확인 | 무단 개봉=해당 방법 무효 | – | – |

### 1.2 트랙 A — 결정론·계측 (CPU 병렬, 학습 0)

| 셀 ID | 출처 | 핵심 내용 | 자원 | 밴드 요지 | 킬 요지 | 예산 |
|---|---|---|---|---|---|---|
| DET-1 | platt_P1 G0–E3 | 커버리지-완전 결정론 탐지기: 정규화 오라클(G1)→divergent-20 probe(E0)→합성 confirmatory(E1: pair R≥0.9/P≥0.8)→junction ablation(E2)→CubiCasa val 전이(E3: F1≥0.4 및 v1+0.2) | CPU | E3 F1<0.4 → H1 kill | 정규화 실패 family는 E1 진입 금지 | 5–7일 |
| DET-2 | cal_P1 C0–C8 | constraint lattice: 계약봉인(C0)→v0 대비 probe(C2)→transform 정규화(C3)→다증거·false-merge(C4: ≤0.05)→ILP(C5)→calibration(C6: REL≤0.03/RES≥0.02)→M 배터리(C7: flip≤0.01)→스케일링(C8: p95≤60s, RAM≤32GB) | CPU | C9 최종 동결·단발은 전 셀 PASS 후 | flip>0.02·quadratic 폭증·48GB abort | 5–8일 |
| UNIT-1 | fey_P2 C0–C5 + platt_P1 E4 + doe_P2 C0(A/B) | 단위 정박 판별: 4-scale 완전요인(relative F1≥0.85 전 스케일, absolute≤0.40 극단), anchor 신뢰도(C1), 실측 DIM-rich 30 def(C4: δr≥+0.05), no-anchor 폴백 동일성(C5) | CPU | 통합 판정 함수 조문 그대로 | anchor 미사용 판명·폴백 회귀 | 3–5일 |
| SCOPE-1 | fey_P6 C0–C7 | INSERT/scope: transform oracle(C0)→누수 감사(C1)→split-wall 판별(C2: folded≤0.2/unfolded≥0.9)→metamorphic(C3)→1.dwg 10-def probe(C4: ≥30% 신규 cross-scope)→복잡도(C5: 2h/48GB)→비회귀(C6) | CPU | 종합 판정 함수 조문 | C4 rate 0 → 현 코퍼스에서 counter kill | 3–5일 |
| TAG-1 | doe_P2 C0–C5 | Taguchi 강건화: L9×5 probe→L9×40 본선(R-META≤0.02)→collapse 게이트(recall≥0.95)→3×3 후속→hold-out firm 확인 | CPU | R-META>0.10 전 행이면 kill | 145 아카이브 사용, 시드 없음 | 3–4일 |
| META-1 | doe_P5 Q0–Q2, F01–F14 + P-R/P-U probe | 불변성 배터리 재설계: oracle 자격(Q0)→family sentinel(Q1)→28셀 중 CPU 14셀(결정론+고전ML) | CPU | 셀별 PASS≤0.02/FAIL>0.10 | Q0 실패 시 detector 실행 금지 | 3–4일 |
| CONV-1 | platt_P6 전체 + fey_P7 E1–E4 | 관례-prior: lexicon(LEX-0)→PID 감사→384-def probe→cross-project 본실험(XP: cross AUC≥0.75 지지/≤0.55 kill)→동어반복 분리(TAU)→E1 상관(E1C)→스태킹(STK)→fey_P7의 aligned/misaligned 합성 2×2(E1: ΔF1≥+0.15/불변)·MI 증분(E2)·metamorphic(E3)·1.dwg fit/freeze(E4) | CPU | 셔플 실패 시 해석 금지 | gate 우회 1건=즉시 kill (fey_P7 조문) | 4–6일 |
| XFAC-1 | doe_P3 24셀 | truth-source 교차요인: {SYN,EXT,SILVER}×{SYN,EXT,SILVER,META} × {deterministic,learned}. 대각↑/비대각 낙폭≤0.20 판정 | CPU | 낙폭>0.20=사슬 미폐합 계량 증거 | source 자격 실패 셀은 BLOCKED로 명시 | 4–6일 (소스 자격 의존) |
| IND-1 | cal_P2 Cell6·cal_P4 P4-5·fey_P1 E4·platt_P1 E7·platt_P3 C7·platt_P5 V3 (병합) | 대리 독립성 상설 감사: 동일 def에서 {human, synthetic, meta, silver(2가문), 각 방법} disagreement tensor 상설 산출 | CPU | 단일 "독립성 점수" 발명 금지 — contingency 공개 의무 | 전 대리 동일 prior 복제 판명 시 "합의=확증" 주장 전면 demote | 상설 (러너 1회 구축 2일) |
| MRB-1 | platt_P3 C0–C7 | metamorphic 관계 자격·mutation conviction: relation soundness(위반 0%)→conviction≥95%→145 코퍼스 후보 게이트(V_r≤1%)→scope 셀 | CPU | 회전 1건 위반=후보 즉시 kill | 판별력 0이면 배터리 큐 제거 | 4–5일 |

### 1.3 트랙 B — 고전 ML·약지도 (CPU, train 386만 활용)

| 셀 ID | 출처 | 핵심 내용 | 밴드 요지 | 킬 요지 | 예산 |
|---|---|---|---|---|---|
| CML-1 | platt_P2 P2-C1 | 그래프-stat 피처 고전 사다리 (오컴 게이트): logistic·HistGBDT, Δ_main≥+0.10이면 **GNN 생산 중단** | 셔플 AUC>0.55=무효 | – | 1일 |
| PU-1 | cal_P2 Cell1–5, 8 | weak supervision+PU: anchor 감사(precision≥0.98)→모델 사다리(SCAR/nnPU/BaggingPU, lift≥0.03)→ablation(레이어 제거 −0.15 이상 붕괴=kill)→shift calibration(REL≤0.03, OOD drop≤0.10)→셔플 | class-prior 민감도에서 방향 역전=kill | main이 P/N-only 못 이김=kill | 3–5일 |
| SSL-P | cal_P3 E2 (로컬 프로브만) | 3-layer SSL GNN 프로브 (seed 17 1회, RTX): B(pretrain)>A(no-pretrain)>P2 방향성 | 단일 seed — formal claim 금지 조문 유지 | 16GB 지속 OOM=중단 | 1 GPU-일 |

### 1.4 트랙 C — GNN (GPU 로컬 직렬 큐; CML-1 오컴 게이트 뒤에서만)

| 셀 ID | 출처 | 핵심 내용 | 밴드 요지 | 킬 요지 | 예산 |
|---|---|---|---|---|---|
| GNN-1 | platt_P2 C2–C4 | GraphSAGE 주효과(Δ_main≥+0.10)→문맥 귀속 ablation(EdgeShuffle 대비 하한>0)→이름 mask(Δ_name<0.05) | C3 실패=“그래프 문맥” kill(인코더 효과로 재분류) | 18/12/6 GPU-h 상한 | 합계 ≤36 GPU-h |
| GNN-2 | platt_P2 C5–C7 | truth-source 전이(2 source concordance)·silver 통제(C6)·안정성(C7) | 한 source만 적격=승격 불가·test 미소비 | zero/all-wall 센티널 악용=무효 | 소스당 ≤18 GPU-h |
| GNN-3 | cal_P3 E3–E7 | 이종 GNN formal (E3 baseline 동결→E4 SSL ablation→E5 joint→E6 rehearsal→E7 단발) — **E4 이후 DGX 의존** | AUPRC_F≥B*+0.05, lift CI low>0 | SSL lift CI≤0 = “self-supervised P3 실패” 기록 | 로컬 E3까지, E4+는 DGX 큐 |

### 1.5 트랙 D — 래스터·VLM (GPU 로컬 직렬 큐 + API 결재 대기)

| 셀 ID | 출처 | 핵심 내용 | 밴드 요지 | 킬 요지 | 예산 |
|---|---|---|---|---|---|
| RAS-1 | cal_P4 P4-0~P4-5 | 이중뷰: 선결(P4-0)→CRS(공유 CRS-0)→200-block probe(P4-2: stratum lift≥0.08)→CubiCasa 표현(P4-3)→fusion calibration(P4-4: REL≤0.04)→OOD·독립성(P4-5) | 전체 non-inferiority 하한≥−0.02 | 셔플 이상·crop 누출=무효 | GPU 3–5일 |
| RAS-2 | fey_P5 P5-02~P5-07 | 래스터 본선: 20-def probe→FPCAD mask 학습(IoU≥0.60)→CubiCasa 역투영 조건부 이득(Recall@20 delta≥0.25)→독립성→metamorphic→1.dwg | CL-B 대비 하한>0 못 넘으면 mainline kill | NC 격리 실패=제품 arm FAIL | GPU 4–6일 |
| VLM-L | cal_P5 P5-D·P5-E·P5-F + platt_P5 V1–V3 | 로컬 VLM: bridge oracle(V1: F1≥0.6)→FPC seg(V2: IoU≥0.7)→전이·독립성(V3)→qwen 3B LoRA(P5-D: AUPRC≥best_nonVLM+0.03)→**anti-silver 통제(P5-E)**→GBDT 특징 주입(P5-F) | P5-E에서 Δ≤0이면 silver 오염 판정 가중 | V1<0.4=5a/5b 동시 kill | GPU 3–5일 |
| VLM-F | doe_P6 전체 + platt_P5 V4–V5 + cal_P5 P5-B | 프런티어 배심: capability probe→6셀 자격(B1≥0.70∧B4≥0.70)→JURY-META(Δκ>0) | **API 결재 게이트 — 유일 잔여 결재** | 능력 0=frontier 종료 | API 소액~중간 |

### 1.6 트랙 E — RL (VER-1·RL-0 생존 후에만)

| 셀 ID | 출처 | 핵심 내용 | 밴드 요지 | 킬 요지 | 예산 |
|---|---|---|---|---|---|
| BAND-1 | cal_P6 Cell-B/D + fey_P4 B1/B1-shuf + platt_P4 E6 | contextual bandit(획득/라우팅): offline(절감≥20~30% ∧ 품질 저하≤0.01~0.02 — 두 제안 밴드 병기 봉인)→소량 on-policy→셔플 대조 | supervised와 Pareto 동일=kill | Goodhart 서명=중단 | CPU~GPU 2–4일 |
| RLVR-1 | platt_P4 E2–E4 | 고정라벨 음성대조(E2: RL이 supervised+0.05 못 넘으면 C07 유지)→집합 조립 본선(E3: F1_RL−F1_beam≥+0.05 ∧ 위반 비증가)→보상해킹 감사(E4) | E3 유일 생존 밴드 사후 교체 금지 | reward↑F1↓ 괴리=즉시 중단 | GPU 24h cap/arm |
| RLVR-2 | doe_P4 본실험 12셀 + cal_P6 Cell-F | RLVR 요인(A×B×C)·full RL — **scarce 축은 로컬, R 셀은 DGX 큐** | A×C null ∧ A_main≤0 → C07 지지·RL 하차 | 전부 hacking 서명=가짜 승리 | DGX 대기 |
| ASV-1 | fey_P3 C0–C6 | anti-silver 판별: firewall 계약(C0)→cheapest pair(C2: meta_G−meta_S≥0.10)→source ablation(C3)→CubiCasa 전이(C4: ≥0.517)→실도면 384(C5)→단발(C6) | 종합 판정표 조문 | C1(=GEN-1) FAIL 동안 BLOCKING 명시 | GPU 2–4일 |

### 1.7 기각·통합으로 소멸한 셀 (사유)

| 항목 | 처분 | 사유 |
|---|---|---|
| doe_P1 16셀 마스터 스크린 | **PARKED 유지** (패널 원판정 승계) | representation×truth confound + learned 셀 seed-confound 미해소. GEN-1·XFAC-1 완료 후 재설계 재개 조건부 |
| 각 제안의 개별 "생성기 셀" 9건 | GEN-1로 병합 | 동일 선결의 중복 실행 방지. 단 각 제안의 fidelity 수치 차이는 모순 원장 §4-1로 이관 |
| 각 제안의 개별 verifier/greedy-beam 셀 6건 | VER-1·RL-0로 병합 | 동일 실험의 3중 실행 방지. 밴드는 최엄격 판정식 우선, 셀 산출은 3제안에 공동 귀속 |
| platt_P5 V4/V5·doe_P6 frontier·cal_P5 P5-B | VLM-F로 병합, **API 결재 대기** | 프런티어 호출 중복 방지 — 배심 자격 실험은 한 번만 |
| fey_P7 E5 (프로젝트 간 전이 판결) | PARKED | 독립 2+ 프로젝트의 사람 per-handle 라벨 자산이 현재 없음 (도시에 자체 명시) |
| platt_P1 E5 (FloorPlanCAD vector) | BLOCKED 명시 | 로컬 FPC는 래스터+마스크뿐, 벡터 소스 부재 (자산 실측과 일치) |
| fey_P2 조건부 test | 원문대로 비실행 | DIM-bearing 사람 라벨 벡터 test 자산 부재 — "test PASS 상태는 존재하지 않는다" 조문 승계 |

---

## 2. 실행 페이즈 설계

```text
Phase 0 (공유 게이트, CPU 병렬, ~1주):
  GEN-1(함대구현+검증) ∥ CRS-0 ∥ LEX-0 ∥ AUD-0 ∥ SIL-G ∥ TESTLEDGER 설치
  GEN-1 완료 → GRAPH-0, VER-1 → RL-0

Phase 1 (결정론·고전 트랙 전면 병렬, CPU, ~1–2주):
  DET-1 ∥ DET-2 ∥ UNIT-1 ∥ SCOPE-1 ∥ TAG-1 ∥ META-1 ∥ CONV-1 ∥ MRB-1 ∥ CML-1 ∥ PU-1
  (각각 자체 probe→본선 사다리 내장; IND-1 러너 구축 병행)

Phase 2 (GPU 직렬 큐, CML-1 오컴 게이트 판정 후, ~2–4주):
  큐 순서(정보가치/선결순): SSL-P → GNN-1 → RAS-1 → VLM-L → RAS-2 → GNN-2 → BAND-1 → RLVR-1 → ASV-1
  (RL 셀은 VER-1·RL-0 생존 전제; GNN 셀은 CML-1이 band 미충족일 때만)

Phase 3 (교차·독립성 종합, CPU, Phase 1–2 산출 소비):
  XFAC-1(24셀) → IND-1 종합 보고 → 모순 원장 실증 갱신

Phase 4 (test 단발 웨이브, TESTLEDGER 통제):
  생존 방법별 단발을 소수의 orchestrated run으로 묶어 집행. 방법당 1회, 원장 기록.

DGX 큐 (박스 소생 시 즉시): GNN-3(E4+) → RLVR-2 → VLM full FT(cal_P5 P5-G, doe_P6 full)
API 큐 (결재 시): VLM-F (capability probe → 자격 6셀 → JURY-META)
```

의존성 요지: GEN-1이 최대 팬인(합성 의존 전 셀). VER-1→RL 전체. CML-1→GNN 개폐. CRS-0→래스터 전체. SIL-G→silver 사용 전 셀.

## 3. 밴딩

- **TOP (즉시, 로컬, 결재 불요)**: GEN-1 · AUD-0 · CRS-0 · LEX-0 · SIL-G · DET-1 · DET-2 · UNIT-1 · SCOPE-1 · TAG-1 · META-1 · CONV-1 · CML-1 · PU-1 · VER-1 · RL-0 · IND-1 · MRB-1
- **VIABLE (게이트 명기)**: GNN-1/2 (게이트: CML-1 미충족) · SSL-P · RAS-1/2 (게이트: GEN-1+CRS-0) · VLM-L (게이트: CRS-0+V1) · BAND-1·RLVR-1·ASV-1 (게이트: VER-1·RL-0·GEN-1) · XFAC-1 (게이트: 소스 자격) · GNN-3 로컬부(E3)
- **PARKED (사유)**: VLM-F(프런티어 API 결재 — 유일 잔여 결재) · GNN-3 E4+/RLVR-2 DGX부/P5-G(DGX 불통) · doe_P1 16셀(confound 재설계 대기) · fey_P7 E5(라벨 자산 부재) · platt_P1 E5(FPC 벡터 부재) · fey_P2 조건부 test(자산 부재)

## 4. 모순 원장 (원문 인용 — 평균 금지)

1. **충실도 게이트 수치**: cal_P1 "KS≤0.10, TV≤0.10" vs fey_P1 "KS_max≤0.30 및 TV≤0.20" vs fey_P2 "KS ≤ 0.20, TV ≤ 0.10" vs platt_P1 "KS≤0.2, categorical TV≤0.1". → GEN-1 프리레그에서 **하나만** 봉인해야 한다. 권고: platt_P1/fey_P2 계열(KS≤0.20, TV≤0.10)을 기본 후보로 하되 Paul 봉인 결정 항목으로 상신.
2. **절대 mm 대역 vs 상대/치수 정박**: fey_P2 "극단 scale에서 absolute F1≤0.40 (붕괴 입증 목표)" vs cal_P1/DET 계열은 물리 대역 유지+scale 파라미터. platt_P1 E4는 양팔 병행. → UNIT-1이 실증 판정. 판정 전 어느 쪽도 기본값 승격 금지.
3. **silver = 신호 vs 오염원**: cal_P5 "E1.5+consensus 통과 silver로 학습한 student가 …lift CI_low>0" (활용) vs fey_P3 "gate-only ≥ silver-distill … 즉 silver가 오염" (배제 기본) vs platt_P2 C6 "SilverDistill이 …개선되어야" (조건부). → CL-K 통제팔(P5-E·C2·C6)이 전 학습 셀에 상설 — 실험으로 해소, 채택 기본값은 gate-only(보수) 유지.
4. **RL 생존 밴드의 목적함수 차이**: cal_P6 "utility lift≥1.05"(컴퓨트 절감형) vs platt_P4 "F1_RL−F1_beam≥+0.05 ∧ 위반 비증가"(조립 성능형) vs fey_P4 "절감≥30% ∧ F1 저하≤0.02"(Pareto형). → 모순이 아니라 **서로 다른 RL 질문** — BAND-1(라우팅/획득)과 RLVR-1(집합 조립)로 분리 유지, 각자 밴드 봉인.
5. **GNN 개폐**: platt_P2 "HistGradientBoosting이 support band를 충족하면 production ladder에서 GNN을 중단한다" vs cal_P3는 SSL GNN full 프로그램. → 오컴 조문 채택(CML-1이 게이트). cal_P3는 "CML-1 미충족" 조건부로 강등 — cal_P3 자신의 E3가 비-GNN baseline 동결을 요구하므로 정합.
6. **test 소비 정책**: fey_P2 "P2만을 위해 CubiCasa test 400을 소비하지 않는다" vs 다수 제안의 개별 단발 계획. → TESTLEDGER로 일반화: 방법당 1회 + 프로그램 승인 + 소수 orchestrated run으로 묶음.
7. **doe_P1 마스터 스크린의 지위**: 자체 §6은 16셀 실행 계획 완비 vs 패널 PARK("confounded"). → PARK 승계 (§1.7).

## 5. 총예산 요약

| 트랙 | 셀(사다리) 수 | 예상 소요 | 병목 |
|---|---|---|---|
| 공유 게이트 | 9 | ~1주 (GEN-1 구현이 지배) | 생성기 v2 구현 인력 → 함대 위임 권고 |
| CPU 결정론·고전 (Phase 1) | 12 사다리 (~60 유효 셀) | 1–2주, 전면 병렬 | 없음 (64GB 내 streaming) |
| GPU 로컬 큐 (Phase 2) | 9 사다리 | 2–4주 **직렬** | **RTX 5070 Ti 1장 = 프로그램 최대 병목** |
| 교차·독립성 (Phase 3) | 2 | 3–5일 | 소스 자격 |
| test 웨이브 (Phase 4) | 방법 수 만큼 단발 | 2–3일 | TESTLEDGER 통제 |
| DGX 큐 | 4 사다리 | 박스 소생 시 1–2주 | 물리 점검 (가치 큼) |
| API 큐 | 1 사다리 | 결재 시 3–5일 | Paul 결재 1건 |

핵심 병목 2개: ① GPU 1장 (DGX 소생이 최대 해방) ② GEN-1 구현 (함대 분담으로 수일 압축 가능).

PLAN_COMPLETE: claude
