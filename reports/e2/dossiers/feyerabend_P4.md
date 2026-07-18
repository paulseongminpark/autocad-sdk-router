# DOSSIER — feyerabend_P4

**좌석/제안**: feyerabend · P4 — RLVR 도구-라우팅/가설검증 정책 (C07에 대한 counter-induction)  
**클러스터**: CL-H RL 자리 판별  
**route**: V2_human_gate  
**작성 기준일**: 2026-07-18  
**수치 출처**: 패킷 실측 다이제스트만 (신규 측정 주장 없음)

---

## 0. 한 줄 판결 초안 (실험 전)

C07의 좁은 판(“entity→category 직접 RL은 오용”)은 유지하되, **검사 획득·라우팅 정책**에는 contextual bandit / 단기 RLVR을 별도 prereg 트랙으로 연다. 학습 0의 greedy vs ε-greedy vs 고정 풀스캔 Pareto 프로브가 먼저이며, 여기서 비용 절감 <10% 또는 해킹 서명이면 **훈련 전에** 이 자리를 kill한다.

---

## 1. 이론적 근거·선행연구

### 1.1 Counter-induction의 위치

본 제안은 Feyerabend식 **counter-induction**: 지배 규칙(R26 C07을 프로그램 전면 RL 배제로 승격하는 읽기)을 전제하지 않고, 그 규칙이 **적용 범위 밖**인 자리를 명시적으로 구성한다. 목표는 C07을 “틀렸다”고 선언하는 것이 아니라, **고정라벨 RL ≠ 도구 라우팅 RL** 분리를 실험으로 강제하는 것이다. 동일 레포트가 이미 C04(RLVR)·C10(horizon≈1 bandit)으로 예외 자리를 열어 두었으므로, C07 전면 배제 읽기는 텍스트 내부에서도 비보편이다.

### 1.2 계보 1 — Contextual bandit / 비용민감 획득

- **Contextual bandit** (Auer et al. UCB 계열; Li et al. LinUCB — 요검증 연도): 상태(컨텍스트)마다 행동 1회 선택, 즉시 보상. Horizon≈1이면 full MDP/RL보다 분산·표본효율이 낫다. R26 C10과 정합.
- **Cost-sensitive / budgeted learning**: 특징·검사가 비용이 있을 때, 정확도와 비용의 trade-off를 직접 최적화 (Xu et al. cost-sensitive feature acquisition 계열 — 요검증). 본 과업의 “평행쌍/face-bridge/블록속성/DIM정박/VLM 크롭”은 바로 **이질 비용의 검사 도구**다.
- **Active learning / active acquisition**: 다음 라벨·다음 검사를 고르는 정책. 다만 본 제안은 **사람 라벨 질의**가 아니라 **결정론·기하·VLM 도구 호출**을 고른다 — doe P4의 active-acquisition과 메커니즘은 공유하되 행동 의미가 다르다.

### 1.3 계보 2 — RLVR / verifiable reward

- **RLVR (Reinforcement Learning from Verifiable Rewards)**: 수학·코드에서 단위테스트·정답 체커가 보상을 주는 패러다임(OpenAI o-series / DeepSeek-R1 계열 논의 — 요검증). 핵심은 **보상 오라클이 미분 불필요·위조 곤란**하다는 점. R26 C04의 home.
- **보상 해킹 문헌**: Amodei et al. Concrete Problems; Skalse et al. reward hacking taxonomies (요검증). LLM-judge를 보상으로 쓰면 C08 경로로 미끄러진다 — 본 제안은 **합성 IR 적중 + metamorphic 유지 − 검사비용**만 허용하고 silver/LLM 보상을 금지한다.
- **Tool-use / tool-routing RL**: ReAct, Toolformer, API-calling agents에서 “다음 도구 호출”을 정책으로 학습. 벽 탐지에서는 도구 = 기하 검사 채널.

### 1.4 계보 3 — 왜 supervised 헤드와 분리하는가

- **C07의 좁은 판**: 고정 특징→고정 카테고리(per-handle wall/non-wall)는 supervised(로지스틱·GBDT·신경망)가 저분산·표본효율. CubiCasa 실측이 이미 이를 지지: HistGradientBoosting val F1 **0.517** vs 기하 탐지기 전이 F1 **0.2358**, 로지스틱 F1 **0.053**.
- **분리 원칙**: 분류 파라미터 θ_clf 는 cross-entropy / ranking loss로만 학습. 정책 π_φ 는 **어떤 검사를 실행할지**만 고르고, 검사 결과를 supervised 헤드의 입력 특징·게이트에 주입한다. Policy gradient를 θ_clf 에 걸지 않는다 — 이것이 C07 금지 자리와 C04/C10 허용 자리의 경계.

### 1.5 계보 4 — CAD/도면·멀티증거 융합과의 접점

- 탐지기 v1은 이미 4증거 채널 가중합(parallel 0.35 / thickness 0.25 / junction 0.20 / layer 0.20). 본 제안은 가중치를 RL로 학습하는 것이 **아니라**, 채널별 **실행 여부·순서·예산**을 정책화한다. 고정 가중합은 “항상 전부 계산”하는 풀스캔 베이스라인이다.
- FP 주범(Direction 화살표 / BoundaryPolygon / Door / Window / DimensionMark)은 **검사 종류를 바꿔야** 갈리는 실패 모드다. 예: DimensionMark는 DIM정박으로, Door/Window는 face-bridge·개구 휴리스틱으로, INSERT 블록은 블록속성으로. 단일 parallel 스캔으로는 천장 F1 0.335(80px 최소길이)에 막힌다.

### 1.6 해체 대상 (“dissolved_fact”)

“RL은 이 프로그램에서 서지 못한다”는 교리적 독해는, (a) C07 오용 패턴과 (b) RLVR/bandit 자리를 분리하지 않은 채 C07을 프로그램 kill로 읽는 해석이다. Paul 이의(제약 4)와 정합하게, **오용은 kill하되 자리는 실험으로 판별**한다.

---

## 2. 알고리즘 정확 스펙

### 2.1 기호

| 기호 | 의미 |
|------|------|
| `d` | 도면(또는 def / block) |
| `h ∈ H(d)` | 핸들(선분·폴리선 세그먼트 등) |
| `x_h` | 핸들 기본 특징(길이, θ, 레이어 해시 등) — **라벨 비의존** |
| `s_t` | 시점 t의 컨텍스트(상태) |
| `a_t ∈ A` | 검사 행동 |
| `o_t = Exec(a_t; d)` | 검사 관측(특징 증분·게이트 통과 비트) |
| `ŷ = f_θ(x, o_{1:T})` | supervised 헤드의 per-handle 예측 |
| `y*` | 합성 IR 진리 `wall_member(h)` |
| `C(a)` | 행동 비용(정규화 스칼라) |
| `B` | 도면당 예산(비용 합 상한) |

### 2.2 행동 집합 A (v0 수동 4행동 — cheapest probe와 동일)

패킷 지정 최소 집합. 이후 확장 가능하나 **학습 0 프로브는 이 4개로 고정**.

1. **`PARALLEL_PAIR`** — 평행쌍/두께 대역 검사 (탐지기 v1 parallel+thickness 채널; `fast_score` 경로). 상대비용 `c=1.0`.
2. **`FACE_BRIDGE`** — face/room dual에서 브리지·개구 인접 검사 (CL-J 역전 관측의 경량 대리; GEOS 비GPL 가정 시 폴리곤 인접). 상대비용 `c=2.5`.
3. **`BLOCK_ATTR`** — INSERT/블록 속성·월드좌표 전개 후 멤버십 (feyerabend P6 결함 정타와 접속). 상대비용 `c=2.0`.
4. **`DIM_ANCHOR`** — 치수(DIM) 정박으로 상대 두께 대역 재추정 (feyerabend P2 상대대역). 상대비용 `c=1.5`.

**확장 행동(학습 단계 이후, prereg 별도)**:

5. **`RASTER_VLM_CROP`** — 후보 bbox 래스터 크롭 → 로컬 qwen2.5-VL-3B 질의. 상대비용 `c=8.0`. 프런티어 API는 **미승인**이므로 v0에 넣지 않음.
6. **`ABSTAIN_STOP`** — 추가 검사 중단, 현재 관측으로 supervised 헤드만 채점. `c=0`.

**금지 행동**: `PREDICT_LABEL_VIA_RL` — 엔티티에 직접 카테고리 분포를 policy로 출력하는 행동. 구현 시 타입체크로 차단.

### 2.3 상태 s_t (컨텍스트 특징 — truth/라벨 누출 금지)

도면·후보 집합 요약만. **금지 피처**: 진리 비트, mutation family ID, silver 점수, test 분할 플래그, 레이어명 원문(이름-prior 통제 시 해시/마스크 암).

권장 벡터 φ(s) ∈ ℝ^{k}, k≈20–40:

- 후보 수 `|Cand|`, 평균/분산 길이, 각도 히스토그램 엔트로피
- 현재까지 실행한 행동 원-핫 및 누적 비용 `Σ C`
- supervised 헤드의 **불확실성 요약**(entropy, margin) — 단, 헤드는 **정책 업데이트와 stop-grad**로 분리
- INSERT 비율, DIM 엔티티 존재 여부, 래스터 가용 플래그
- 예산 잔여 `B − Σ C`

### 2.4 Episode / 의사코드

```
Input: drawing d, budget B, supervised head f_θ (frozen during policy update),
       policy π_φ (or ε-greedy table), action set A, cost C, oracle y* (train synth only)

s ← InitState(d)          # no labels
O ← ∅                     # accumulated observations
cost ← 0
while cost < B:
    a ∼ π_φ(·|s)          # or ε-greedy / UCB
    if a == ABSTAIN_STOP: break
    o ← Exec(a, d)        # deterministic or local VLM
    O ← O ∪ {o}
    cost ← cost + C(a)
    s ← UpdateState(s, a, o, cost)
ŷ ← f_θ(Features(d), O)  # per-handle scores → threshold τ

# Reward (TRAIN SYNTH ONLY; never silver/LLM)
R_hit  ← F1(ŷ, y*)                    # or ΔF1 vs no-extra-check baseline
R_meta ← 1[metamorphic_battery(d, ŷ) passes sentinels]
R_cost ← cost / B
R ← α R_hit + β R_meta − γ R_cost

# Hacking monitors (logged every episode)
empty_pred_rate ← mean(ŷ == ∅ or all-negative)
if empty_pred_rate > κ: flag HACK_EMPTY
if R_hit_proxy ↑ while holdout_F1 ↓: flag HACK_PROXY   # when holdout available

Update π_φ with advantage of R   # bandit: only last action; short RL: full trajectory
# NEVER update θ with policy gradient
```

### 2.5 학습 목표 (단계별)

**Stage 0 — 학습 0 시뮬레이션 (의무, cheapest probe)**  
행동 가치 Q(s,a)를 오라클 롤아웃으로 추정하지 않고, top-20 divergence def에서 **고정 정책 4종**을 비교:

- `FULL_SCAN`: 매 def에 A의 전 행동 실행(또는 탐지기 v1 풀채널)
- `GREEDY_STATIC`: 사전 고정 우선순위 (예: PARALLEL→DIM→BLOCK→FACE)
- `EPS_GREEDY_SIM`: ε=0.2로 무작위 탐색, 가치는 **사후** F1−λcost로만 기록(파라미터 업데이트 없음)
- `RANDOM`

판정: FULL_SCAN 대비 비용 절감과 F1 델타.

**Stage 1 — Tabular / linear contextual bandit (로컬)**  
- 알고리즘: LinUCB 또는 logistic Thompson sampling (요검증 구현 디테일).  
- Horizon=1 근사: 각 def에서 **한 번** “추가 검사 묶음”을 고르거나, 다스텝이어도 **상태전이 없는 독립 암**으로 취급 가능한지 Stage 0에서 검증.  
- 손실: 대역it regret; 보고 지표는 Pareto (F1, cost).

**Stage 2 — 단기 RLVR (조건부)**  
Stage 1에서 horizon>1이 필요하고(검사 결과가 다음 유용 행동을 바꿈), bandit 대비 utility ≥ 사전등록 하한일 때만.  
- 알고리즘: REINFORCE / PPO-clip 소형 MLP 정책, γ≈0.9, T≤4.  
- Critic: 보상 분산 감소용 value head (선택).  
- **금지**: LLM-as-reward; silver in reward; θ_clf 에 policy gradient.

### 2.6 보상 하이퍼파라미터 공간 (prereg 봉인)

| 심볼 | 역할 | 탐색 격자 (val만) | 기본 제안 |
|------|------|-------------------|-----------|
| α | F1 적중 가중 | {0.5, 1.0} | 1.0 |
| β | metamorphic 통과 | {0.0, 0.25, 0.5} | 0.25 |
| γ | 비용 벌점 | {0.25, 0.5, 1.0} | 0.5 |
| B | 도면당 예산 | {3, 5, 8} (상대비용 단위) | 5 |
| τ | 분류 임계 | supervised 캘리브레이션에서 고정 | GBDT/탐지기 기존 |
| ε | 탐구율 (Stage 0/1) | {0.1, 0.2} | 0.2 |
| κ | 빈 예측 해킹 임계 | {0.05, 0.10} | 0.05 |

**보상 동결**: α,β,γ,B,κ의 sha를 학습 시작 전 파일에 봉인. 변경 시 새 실험 ID.

### 2.7 Supervised 헤드 (비-RL)

- 기본: CubiCasa에서 이미 검증된 **HistGradientBoosting** 6특징 (parallel/thickness/junction/log길이/sin2θ/cos2θ) — val F1 0.517, AUC 0.9215, 셔플 AUC 0.375 PASS.
- 검사 관측 o는 **추가 특징 열**로만 결합 (예: `dim_anchored_thickness`, `block_exploded`, `face_bridge_score`).  
- 헤드 재학습은 CL-F 사다리 규칙 따름; 본 도서는 **라우팅 정책**만 소유권.

### 2.8 평가 단위 격리 (T6 / 공격 E)

- **Primary unit**: per-handle `wall_member(h)` F1 / P / R.  
- **Routing unit**: 도면당 `Σ C(a)`, 검사 횟수, latency.  
- 집합-조립(쌍→체인) 점수는 platt P4 산출물로 **별도 파일/메트릭 네임스페이스** — 본 정책의 F1과 섞어 평균하지 않음.

---

## 3. 벽 과업 적응 설계

### 3.1 세 축 하네스 접속

| 축 | 자산 | 본 제안 역할 | 제약 |
|----|------|--------------|------|
| **CubiCasa SEG-IR 벡터** | train 4,200 / val 400 / test 400; 벽 선분율 ~11.8%; 라벨 누출 0 | supervised 헤드 학습·캘리브레이션; **라우팅 정책의 오프라인 로그 시뮬** (검사 비용을 특징 계산 proxy로) | test 단발·무접촉; NC counsel(PR-3) 전 외부셋 **학습 arm** 확대는 보류 가능하나, 이미 GO된 사용 범위 내에서 val만 튜닝 |
| **FloorPlanCAD 래스터** | 5,308장 + bbox/segmask; 벡터 SVG 없음 | `RASTER_VLM_CROP` 확장 암 전용; 픽셀→핸들 역투영은 T24 미해결 → **v0 라우팅에서 제외** | PR-3 NC; 역투영 exact 하네스 선검증 |
| **1.dwg 실도면** | staged DXF, 도면정의 384; 최대 def 412,775 선분 | top-20 divergence def에서 Stage 0 프로브; B3 벽-제로율 0.2135 PASS 맥락의 messy 분포 | 연산 병목 → def 단위 예산·후보 상한 의무 |

합성팩 S/F/M: B1 충실도 FAIL(KS 0.5792, TV 0.265) — **보상 오라클 자격 미달**. PR-1/CL-C 벽 생성기 + fidelity 게이트 통과 전에는 “합성 F1”을 RLVR 보상으로 쓰지 말고, Stage 0은 **실도면 + metamorphic + (가능 시) CubiCasa val의 비용 proxy**로만 판정한다. 패킷 문구의 “합성 정답”은 **CL-C 동결 후**에야 Stage 1+ 보상으로 승격.

### 3.2 현재 성적 위에서 이 방법이 “더 가져올” 수 있는 것

1. **전이 실패 F1 0.2358의 본질**: P≈기저율, R≈1 — 평행 구조 과검출. 풀스캔 parallel은 FP를 줄이지 못하고 비용만 만든다. 라우팅이 Door/Window/DIM 등 **실패 모드별 검사**를 선택적으로 켜면, 동일 supervised 헤드에서도 FP 감소 여지.
2. **GBDT F1 0.517의 병목**: R 0.370으로 재현율 희생. 추가 검사(FACE_BRIDGE, BLOCK_ATTR)는 **저재현 구간의 후보 회수**에 쓰일 수 있다. 즉 라우팅의 uplift는 “분류기 교체”가 아니라 **특징 획득 스케줄**.
3. **스케일 무감 (2–15mm/px)**: 물리 두께 prior 무력 → `DIM_ANCHOR`·상대대역이 풀스캔 thickness보다 정보적일 가능성 — P2와 병합 가치.
4. **412k 선분 def**: 풀채널 `fast_score`도 비싸다. ≥30% 비용 절감 밴드는 **실무 병목**에서 정당화된다. 절감 <10%면 bandit 가치 없음(패킷 prereg).

### 3.3 정답원·누수 방지 (과업 특화)

| 규칙 | 적용 |
|------|------|
| 보상에서 silver/LLM 배제 | B5 Pearson 0.2911인 silver를 보상으로 쓰면 해킹·가문 편향(2어휘) 유입 |
| 도면 split | CubiCasa train/val/test 유지; 정책 학습 시드 ≠ eval 시드 |
| 합성 generator family | reward-visible vs hidden mutation 분리 (CL-C/CL-D) |
| 이름-blind | 탐지기 full-vs-nb 1.0(레이어명 신호 0) — 정책 상태에도 레이어 원문 미투입이 기본 |

### 3.4 Metamorphic 연동 (CL-D)

보상항 `R_meta`는 강체·단위 PASS, scale 팔 FAIL(0.7624) 실측을 알고 설계: scale 위반을 “통과”로 위조하지 않도록 **센티널(0벽/전벽)+recall 최저선(T7)** 을 켠 뒤에만 β>0 허용. 위반율-only는 0벽 탐지기를 통과시킨다 — 해킹 경로 #1.

---

## 4. 데이터·컴퓨트 요구

### 4.1 로컬 실행 계획 (기본 — DGX unreachable 전제)

| 자원 | 용도 |
|------|------|
| CPU + RAM 64GB | Stage 0 롤아웃; LinUCB 테이블; CubiCasa 특징 행렬(386만행은 **미리 추출된 캐시**만 사용, 재추출 최소화) |
| RTX 5070 Ti 16GB | 선택: 소형 정책 MLP; 로컬 qwen2.5-VL-3B 크롭 암(확장 단계). vLLM 서빙과 **동시 점유 금지** — 시분할 |
| 디스크 | IR 캐시, 롤아웃 로그(parquet), 보상 sha, 증거 xlsx |

**Stage 0 예산**: top-20 divergence def × 4 정책 × (행동 시뮬) — 목표 벽시계 **≤1일**, 학습 없음.  
**Stage 1 예산**: 로컬 1–2일 tabular/linear bandit.  
딥 정책·대량 시드 반복은 DGX 복구 후로 미룸.

### 4.2 DGX Spark 계획 (승인됨·현재 unreachable)

- 사용 조건: Stage 0에서 horizon>1 신호 + Stage 1 bandit이 FULL_SCAN 대비 비용≥30% 절감·F1 저하≤0.02를 **로컬에서** 재현.  
- 작업: 단기 PPO 시드≥3, 병렬 env; Ornith-35B와 **GPU 큐 분리**(패킷: vLLM과 분리).  
- unreachable 동안: DGX 없이도 판결 가능한 범위(Stage 0–1)만 “CL-H 진행”으로 간주. Stage 2 미실행은 실패가 아니라 **차단(blocked)**.

### 4.3 데이터 의존성 게이트

| 게이트 | 상태(패킷 기준) | 본 제안 영향 |
|--------|-----------------|--------------|
| PR-1 벽 합성 생성기 | 미구축; B1 FAIL | Stage 1+ 합성 보상 **차단** |
| PR-2 대리 독립성 | OPEN T1 | 다중 대리 합산 보상 금지; metamorphic·합성·외부를 섞어 평균하지 않음 |
| PR-3 counsel | OPEN T5 | CubiCasa/FloorPlanCAD 학습 확대 전 서면; 기존 다이제스트 수치 인용 실험은 문서화만 |
| T26 verifier FAR≤0.01 | OPEN | RL 계열 사활 — Stage 1 학습 시작 전 측정 의무 |
| CL-D sentinel | OPEN T7 | β>0 전 필수 |

---

## 5. 구현 계획

### 5.1 모듈·파일 골격 (신규 코드는 본 도서 범위 밖 — 설계만)

```
wsd_rlvr_routing/
  actions.py          # A, C(a), Exec() 어댑터
  state.py            # φ(s), 누출 가드 단언
  reward.py           # R_hit, R_meta, R_cost, sha freeze, hack monitors
  policies/
    baselines.py      # FULL_SCAN, GREEDY_STATIC, RANDOM
    eps_greedy.py     # Stage 0 시뮬
    linucb.py         # Stage 1
    short_ppo.py      # Stage 2 (optional)
  envs/
    drawing_env.py    # episode loop
  eval/
    pareto.py         # cost-quality curves
    hacking.py        # empty_pred_rate, proxy gap
  scripts/
    stage0_top20.py   # cheapest probe entry
    stage1_bandit.py
  conf/
    reward_freeze.json
    prereg_bands.json
```

### 5.2 기존 도구 접속점

| 기존 자산 | 접속 |
|-----------|------|
| `fast_score` | `PARALLEL_PAIR` Exec 백엔드; FULL_SCAN 비용 측정 기준 |
| `evidence_grid` | 다증거 채널 on/off를 행동과 정렬; 격자 셀 = 라우팅 로그 스키마 |
| `cubicasa_ir` | SEG-IR 로드·핸들 이터레이터; split manifest |
| `cubicasa_ml` | GBDT 헤드 freeze/load; 추가 열 결합; val 메트릭 리포터 |

### 5.3 개발 규모 추정

| 단계 | 공수(엔지니어-일) | 산출 |
|------|-------------------|------|
| Stage 0 프로브 | 1–2 | top-20 Pareto 표 + xlsx + kill/survive 메모 |
| Exec 어댑터 4행동 | 2–4 | DIM/BLOCK은 CL-B/P2/P6 진척에 의존 — 스텁 허용하되 스텁은 비용만 차고 관측 0 |
| Stage 1 LinUCB | 2–3 | 로컬 학습 스크립트 + seed 분리 |
| Stage 2 PPO | 3–5 (+DGX) | 조건부; Stage 0–1 kill 시 0 |

**의존으로 인한 스텁 규칙**: Exec가 NotImplemented이면 해당 행동은 Stage 0에서 **비활성**으로 표시하고, 활성 행동 부분집합으로만 밴드를 재선언(숨은 축소 금지 — 로그에 명시).

### 5.4 산출물·증거

- 매 셀: `evidence/*.xlsx` (평가 원칙), 시드, 보상 sha, split ID.  
- 실패도 사유와 함께 기록.  
- 최종 판정 문장: `kills: reigning` | `kills: counter` | `blocked: <gate>`.

---

## 6. 실험 셀 정의

원칙: val=개발·튜닝, test=방법당 단발, 합격선 사전 봉인, 셔플 대조군 의무(정책 입력 셔플 — 컨텍스트 φ를 순열해도 비용↑F1동일이면 누출/상수정책 의심).

### Cell S0 — Cheapest probe (학습 0, top-20 divergence def)

| 항목 | 내용 |
|------|------|
| **가설** | 고정 풀스캔 대비, 탐구 ε-greedy/정적 탐욕이 F1 저하 ≤0.02로 비용을 유의미히 줄인다. |
| **지표** | (1) 상대 비용 `cost/cost_FULL` (2) per-handle F1 (실도면은 metamorphic+수동/은 proxy 병행 시 명시) (3) 빈 예측률 (4) 행동 선택 히스토그램 |
| **합격선 (prereg)** | 비용 절감 ≥30% ∧ F1 저하 ≤0.02 → Stage 1 **VIABLE 진입**; 절감 <10% → **bandit 가치 없음, Stage 1+ kill** |
| **킬 조건** | 빈 예측으로 F1 붕괴; 또는 GREEDY≈FULL≈상한(비용만 다르고 F1 동일 천장)이 **아니면서**도 절감 <10%; 또는 해킹 모니터 κ 초과 |
| **예산** | ≤1일, 로컬 CPU, GPU 불요 |
| **시드** | 시뮬 난수 seed ∈ {0,1,2}; def 목록 고정 시드와 분리 기록 |

### Cell S0b — Greedy vs Beam 보상지형 (CL-H 공유 선결)

| 항목 | 내용 |
|------|------|
| **가설** | 동결 보상에서 greedy≈beam≈상한이면 순차 선택의 잔여 가치가 없어 **훈련 전 RL kill**. |
| **지표** | 동일 보상 함수 하 greedy/beam/random의 R 및 F1 |
| **합격선** | beam − greedy ≥ δ_pre (δ는 봉인; 제안 기본 0.02 R 단위) 일 때만 Stage 2 검토 |
| **킬 조건** | greedy≈beam → short RLVR 경로 kill (bandit만 잔류 가능) |
| **예산** | ≤1일, 학습 0 |
| **시드** | beam width {2,4,8} 기록 |

### Cell V1 — Verifier soundness (T26 사활)

| 항목 | 내용 |
|------|------|
| **가설** | metamorphic+합성(가용 시) verifier의 false-accept ≤0.01. |
| **지표** | FAR, FRR; 센티널 통과율 |
| **합격선** | FAR ≤ 0.01 (calibration P6와 정합) |
| **킬 조건** | FAR > 0.01 → **RL 계열 전체 중단** (보상 학습 금지) |
| **예산** | CL-D와 공유; 별도 1일 가능 |
| **시드** | mutation pack ID 고정 |

### Cell B1 — Tabular/linear contextual bandit (로컬)

| 항목 | 내용 |
|------|------|
| **가설** | 컨텍스트 조건화가 FULL_SCAN·정적 규칙 대비 Pareto를 지배한다. |
| **지표** | 합성(게이트 통과 후) F1; 비용; CubiCasa **val** F1/cost proxy; 해킹 서명 |
| **합격선** | FULL 대비 비용 ≥30% 절감 ∧ 합성 F1 저하 ≤0.02 → VIABLE; supervised-only(검사 없음/최소)와 Pareto 동일 → kill |
| **킬 조건** | 패킷: 해킹 또는 무이득; 또는 silver가 보상에 유입된 구현 발견 |
| **예산** | 로컬 1–2일; 5070 Ti optional |
| **시드** | train_policy seeds {10,20,30}; eval seed {99} 분리; CubiCasa test **미사용** |

### Cell B1-shuf — 셔플 대조군

| 항목 | 내용 |
|------|------|
| **가설** | φ(s) 셔플 시 정책이 비용을 못 줄이거나 F1이 붕괴 — 컨텍스트가 실제 신호. |
| **지표** | AUC-like: 비용 절감폭; F1 |
| **합격선** | 셔플 절감 ≪ 본실험 절감 ( qualitatively; 수치 밴드는 B1과 동시 봉인) |
| **킬 조건** | 셔플≈본실험 → 허위 적응/상수 정책 |
| **예산** | B1의 +20% |
| **시드** | shuffle seed {7} |

### Cell R2 — Short-horizon RLVR (조건부, DGX 또는 로컬 소형)

| 항목 | 내용 |
|------|------|
| **가설** | T≤4 다스텝이 bandit 대비 utility를 개선한다 (calibration: ≥5% 제안과 정합하되, 본 패킷 1차 밴드는 Pareto 30%/F1≤0.02가 우선). |
| **지표** | utility = αF1+βMeta−γCost; bandit 대비 비 |
| **합격선** | bandit 대비 utility 개선 ∧ 해킹 없음 ∧ FAR 유지 |
| **킬 조건** | bandit 동률/열위; 또는 C07 오용으로 θ_clf 에 gradient 유입 |
| **예산** | DGX 단기 또는 로컬 소형 2–3일; vLLM 큐 분리 |
| **시드** | ≥3; test 단발은 **최종 1회만** |

### Cell H — Reward hacking red team (상시 모니터 셀)

| 항목 | 내용 |
|------|------|
| **가설** | 비용 최소화 압력이 빈 예측·재현율 붕괴를 유도할 수 있다. |
| **지표** | empty_pred_rate; recall floor; R_proxy vs holdout F1 gap |
| **합격선** | empty_pred_rate ≤ κ; recall ≥ floor (T7과 공유 봉인) |
| **킬 조건** | 해킹 서명 확정 → 즉시 정책 학습 중단, 사건 기록 |
| **예산** | 매 셀에 내장 |
| **시드** | n/a |

### Cell X — 실측 Pareto only (합성 부재 시 대체)

| 항목 | 내용 |
|------|------|
| **가설** | PR-1 이전에도 Stage 0는 실도면 비용-품질 Pareto만으로 reigning 읽기를 흔들 수 있다. |
| **지표** | 비용, metamorphic 위반, (가능 시) 외부 val F1 — **합성 F1 주장 금지** |
| **합격선** | 절감 ≥30% ∧ metamorphic·recall floor 유지 → “라우팅 자리 실험 가치 VIABLE”; C07 **전면 배제 읽기**에 대한 soft kill 증거. 확정 `kills: reigning`은 합성 오라클 가용 후 B1에서만. |
| **킬 조건** | 절감 <10% |
| **예산** | S0에 포함 |
| **시드** | S0과 공유 |

**test 분할**: CubiCasa test 400은 **방법당 단발**. B1에서 우승한 설정 1개만, 인간 게이트(V2) 승인 후 집행. 그 전 수치를 test로 보고하지 않음.

---

## 7. red team 티켓 응답

CL-H / 본 제안에 직접 걸린 OPEN 티켓을 지목한다. (34건 전량 OPEN — 상세는 `seats/red_teamer.md` 참조가 패널에 명시.)

### T6 (공격 E, sev 0.60) — 평가 단위 혼선

- **내용**: 집합-조립과 per-handle 분류를 한 메트릭으로 섞으면 RL이 가짜 우위를 얻는다.  
- **응답**: **수용+격리**. Primary = per-handle F1. 라우팅 비용은 별도 축. 집합-조립은 platt P4 네임스페이스. 구현 PR에서 메트릭 레지스트리 키를 분리하지 않으면 merge 거부.

### T26 — verifier false-accept ≤0.01 (RL 사활)

- **내용**: 불건전 verifier 위 RL은 해킹.  
- **응답**: **하드 게이트**. Cell V1 통과 전 Stage 1+ 학습 금지. FAR>0.01이면 본 제안 `blocked`, 교리 승리가 아니라 **측정 실패**.

### T7 (공격 F, sev 0.50) — 0벽/전벽 sentinel · recall floor

- **내용**: 위반율-only metamorphic은 0벽 탐지기 통과.  
- **응답**: **수용**. β>0 및 비용 벌점 γ 활성 전 sentinel 의무. Cell H와 연동.

### T1 (공격 A, sev 0.75) — 대리 독립성

- **내용**: 합성·외부·metamorphic·silver가 동일 parallel prior면 확증 편향.  
- **응답**: **위험 인정**. 보상은 합성(자격 후)+metamorphic만; silver 보상 금지로 한 축 제거. 다중 대리 평균으로 VIABLE 선언 금지. CL-E 불일치 구조와 교차.

### T2 (공격 B, sev 0.70) — 벽 합성 생성기 부재

- **내용**: `synthetic_truth.py` 벽 코드 0; B1 FAIL.  
- **응답**: **수용·차단**. Stage 1 합성 보상 = PR-1/CL-C 후. 그 전은 Cell X/S0만.

### T5 (공격 D, sev 0.65) — NC 라이선스

- **내용**: FloorPlanCAD/CubiCasa 권리 미해결.  
- **응답**: **위험 인정**. 외부셋 학습 arm 확대는 PR-3 서면 후. 라우팅 실험이 CubiCasa 특징 캐시를 쓰면 사용 범위를 counsel 메모에 기록.

### T3/T4/T8 — E1 법의학·정렬 아티팩트

- **응답**: **선결 위임(CL-A)**. top-20이 정렬 유물이면 S0 표본이 편향. CL-A 재계산 목록을 S0 def 리스트로 채택.

### T10/T23 등 Graph IR · CL-F 선결

- **응답**: FACE_BRIDGE가 Graph adjacency에 의존하면 T10 감사 전 스텁. 스텁 시 행동 집합 축소 선언.

### T24 — 픽셀→핸들 역투영

- **응답**: `RASTER_VLM_CROP`는 T24 통과 전 **비활성**. 로컬 VLM이 있어도 벡터 핸들 점수에 합산하지 않음.

### T34 — 인용 R-레인 experiment_executed:false

- **응답**: C04/C10/C07 인용은 **draft/NEEDS_WEB_VERIFY** 가능성 명시(platt P4와 동일). 본 실험이 C07 적용범위의 **과제-로컬 증거**를 생산한다 — 문헌 메타 주장은 V2 게이트.

### 프로그램급 수용 문장

C07 “전면 RL 배제” 읽기에 대한 counter-induction은, 위 게이트를 건너뛰는 면죄부가 **아니다**. 게이트 실패 시 정직한 출력은 `kills: counter` 또는 `blocked`, 위조 VIABLE 아님.

---

## 8. 인접 제안과의 관계

### 8.1 CL-H 내부 역할 분담

| 제안 | 자리 | 본 P4와의 관계 |
|------|------|----------------|
| **platt P4** | 집합-조립 RLVR vs beam/ILP | **병합 금지(메트릭)**. 선결 공유: 학습 0 보상지형, silver 보상 금지. platt가 조립에서 kill돼도 라우팅 bandit은 생존 가능(역도 성립). |
| **doe P4** | 패러다임×예산×truth_quality 요인 | **보완**. doe는 C07을 효과로 추정; 본 P4는 행동 공간을 **도구 라우팅**으로 고정한 메커니즘 실험. doe cheapest 2×2(active×budget) 결과가 scarce에서 무이득이면 본 B1 우선순위 하락. |
| **calibration P6** | verifier-guided acquisition, bandit-first | **가장 가까운 병합 후보**. 행동 이름만 다름(graph expand/VLM jury vs PARALLEL/DIM/…). 공유: FAR≤0.01, LLM 보상 금지, bandit→RLVR 조건부. 차이: 본 P4는 C07 **counter-induction·교리 해체** 서사가 주목표; calibration은 utility/Brier 예보 프레임. **실구현은 단일 `wsd_rlvr_routing` 코드베이스 + 보고서 섹션 분리 권장.** |

### 8.2 인접 비-RL 제안

| 제안 | 관계 |
|------|------|
| CL-B / P2 / P6 (결정론 커버리지·상대대역·INSERT) | Exec() 품질의 공급자. 라우팅은 빈 검사를 고를 수 없음. |
| CL-D metamorphic | 보상·해킹 방어의 공용 심판. |
| CL-C 합성 truth | 보상 오라클. 없으면 Cell X로 강등. |
| CL-F GBDT 사다리 | θ_clf 공급자. Occam: GBDT가 이미 0.517이면 라우팅 uplift만 추가 측정. |
| CL-G VLM | 확장 행동; T24·PR-3·API 미승인으로 후순위. |
| CL-J face-first | FACE_BRIDGE 행동의 이론적 원천; CL-J probe 실패 시 해당 암 약화. |
| CL-K anti-silver | 보상·증류에 silver 금지 원칙 공유. |

### 8.3 차별점 (한 문단)

doe는 요인 설계로 “언제 RL이 이기는가”를 묻고, platt는 “조립 조합이 RL을 요구하는가”를 물으며, calibration은 “verifier 건전 하 acquisition utility”를 예보한다. **feyerabend P4**는 같은 CL-H 수렴 위에서, C07을 프로그램 kill로 읽는 **교리적 독해를 해체**하는 것이 1순위 산출이다 — 실험적으로는 도구-라우팅 bandit의 Pareto 증거로 reigning 읽기를 kill하거나, 무이득/해킹으로 counter를 kill한다.

### 8.4 이 제안이 죽어야 하는 조건 (정직)

다음 중 **하나**면 본 제안(도구-라우팅 RLVR/bandit 자리)을 kill하거나 영구 PARK한다.

1. **S0 절감 <10%** — bandit 가치 없음 (패킷 명시).  
2. **해킹** — 비용 최소화→빈 예측·recall 붕괴, 또는 proxy↑/holdout↓.  
3. **Supervised-only와 Pareto 동일** — 추가 검사 정책이 경계를 못 움직임.  
4. **S0b greedy≈beam≈상한** — 다스텝 RLVR 불요; 이후 bandit마저 S0 실패면 전부 kill.  
5. **T26 FAR>0.01 미해결** — 학습형 보상 정책 금지 (blocked→장기 kill).  
6. **구현이 C07 오용으로 미끄러짐** — θ_clf 에 policy gradient / 라벨 직접 RL 재도입이 코드에 나타나면 즉시 kill.  
7. **행동 공간이 실실패 모드 미포함** — FP 주범(Door/Window/DIM/…)을 가르는 Exec가 전부 스텁으로 남고, PARALLEL만 활성인 채 VIABLE 선언은 금지; 그 상태는 **실험 실패**로 기록.  
8. **Paul V2 게이트 기각** — route가 V2_human_gate이므로, 증거와 무관하게 프로그램 우선순위에서 내릴 수 있음 (방법 kill이라기보다 채택 kill).

역으로 reigning(C07 전면 배제 읽기)이 죽는 조건: **합성 오라클 자격 하에** 비용↓·F1유지(≥30% 절감, F1 저하≤0.02)가 해킹 없이 재현되고, 평가 단위 격리·FAR 게이트를 통과할 때 — `kills: reigning`.

### 8.5 권고 집행 순서 (트위크 가능성 순)

1. CL-A로 top-20 목록 확정 → S0/S0b  
2. T26 + T7 → 보상 함수 봉인  
3. PR-1/CL-C 없으면 Cell X만으로 V2에 중간 보고  
4. 통과 시 B1 (+셔플)  
5. calibration P6와 코드 병합 여부 Paul 결정  
6. R2는 마지막 (DGX)

---

## 부록 A — Prereg 밴드 요약 (복붙용)

```
VIABLE_routing:
  cost_reduction_vs_full_scan >= 0.30
  AND delta_F1_synth >= -0.02
  AND empty_pred_rate <= kappa
  AND verifier_FAR <= 0.01
  AND no_silver_in_reward
  AND metric_namespace == per_handle_primary

KILL_routing:
  cost_reduction < 0.10
  OR hacking_signature
  OR pareto_equal_supervised_only
  OR policy_gradient_on_classifier_labels

KILL_reigning_C07_universal_read:
  VIABLE_routing evidenced on sealed split
```

## 부록 B — 제안 amendment 문장 (V2 제출용)

> C07은 entity→category 직접 RL에만 적용한다. 검증가능 보상의 획득/라우팅 정책은 C04/C10 트랙으로 별도 prereg한다. 전면 RL 배제 읽기는 이 프로그램의 규칙이 아니다.

---

DOSSIER_COMPLETE: feyerabend_P4
