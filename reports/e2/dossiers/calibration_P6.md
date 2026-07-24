# E2 방법론 심층 도시 — calibration_P6

**좌석**: calibration_P6  
**제안**: Verifier-guided active acquisition — contextual bandit 우선, RLVR 조건부  
**작성일**: 2026-07-18  
**수치 인용 범위**: 본 패킷 실측 다이제스트(2026-07-18)만. 그 외 수치는 문헌·일반 지식이며 `[요검증]` 또는 `[일반지식]`으로 표기.

---

## 0. 제안 한 줄 계약 (해독)

고정된 `entity→wall` 분류기(supervised)는 건드리지 않고, **불확실한 block에서 다음 획득/검증 행동만** 정책이 고른다. Horizon이 1이면 contextual bandit으로 충분하고, multi-step·지연 보상이 실증될 때만 RLVR로 승격한다. 보상은 held-out이 아닌 **training synthetic exact truth + 독립 metamorphic verifier**에서 Brier 개선·exact gate 통과로 계산하고 compute·latency 비용을 차감한다. LLM judge 보상은 금지.

**Claim**: verifier-guided action policy가 semantic 성능을 유지하면서 고정·supervised acquisition baseline보다 compute cost를 **≥20%** 줄인다.  
**Forecast**: `null` (수치 forecast abstain; `empty_reference_class`, RC-WALL-ZL `n=0` < `n_min=5`).  
**Resolution**: `wsd_eval_p6.json` 생성 시 — verifier soundness + AUPRC 비열등 + 비용 절감 band 동시 통과; full RL은 별도 `utility_RL/utility_bandit≥1.05`.

---

## 1. 이론적 근거·선행연구

### 1.1 문제 프레임: “분류”와 “획득”의 분리

P6의 핵심 설계 결정은 패널 CL-H와 4석 수렴과 같다: **per-handle 벽 멤버십 분류는 supervised로 고정**하고, 비용이 드는 **probe/라우팅/집합 조립만** 순차 의사결정으로 둔다. 이는 강화학습을 “더 좋은 분류기”가 아니라 “더 싼 증거 수집기”로 쓰는 전통(active learning / selective prediction / cascade)에 가깝다.

벽 과업에서 이미 관측된 사실:

- 기하 탐지기 v1 전이: val F1 **0.2358** (P≈기저율, R≈0.981) — 싼 전역 규칙으로는 재현율은 높으나 정밀도가 붕괴.
- HistGradientBoosting(6특징) → val F1 **0.517** / AUC **0.9215** — supervised가 semantic lift의 주원천.
- 프런티어 VLM·고해상도 render·graph 확장은 비용이 크고, DGX는 현재 unreachable, 프런티어 API는 미승인.

따라서 “전 구간에 VLM/RL”은 자원·게이트상 비합리적이다. **불확실한 소수 block에만 비싼 probe를 할당**하는 정책이 필요하며, 이것이 contextual bandit / RLVR의 자리이다.

### 1.2 Contextual bandit 계보

- **Contextual bandit (LinUCB, Thompson Sampling, EXP4 등)**: 상태(context)를 보고 행동(arm)을 하나 고르고, 즉시(또는 짧은 지연) 보상을 관측. Horizon≈1, 행동이 미래 상태 분포를 크게 바꾸지 않을 때 최적에 가깝다. `[일반지식]`
- **Cost-sensitive / budgeted bandit**: 보상에서 행동 비용을 차감하거나 예산 제약 하에서 누적 효용을 최대화. P6의 “Brier 개선 − λ·compute − μ·latency”와 직접 대응. `[일반지식]`
- **Offline / batch contextual bandit (IPS, DR, SNIPS)**: 로그 정책으로 수집한 (x,a,r)로 새 정책을 평가·학습. P6 cheapest probe(“합성 1,000 state × 네 행동 offline bandit”)가 이 경로. `[일반지식]`
- **Active learning / uncertainty sampling**: entropy·margin·BALD로 라벨/프로브 대상을 고름. P6의 supervised uncertainty acquisition baseline이 이에 해당. Bandit은 heuristic을 **데이터로 교정**하는 상위층. `[일반지식]`

### 1.3 RLVR·검증기 보상 계보

- **RL from Verifiable Rewards (RLVR)**: 수학·코드 등에서 LLM judge 대신 **실행 가능·결정론적 verifier**로 보상을 준다(예: 정답 매칭, 유닛테스트, 형식 검사). P6는 LLM judge 보상을 **명시 금지**하고, synthetic exact truth + metamorphic verifier만 허용 — RLVR 철학의 벽-CAD 이식. `[일반지식]`
- **Reward model Goodhart / overoptimization**: proxy 보상을 최적화하면 true metric이 붕괴(Amodei et al. 계열; Goodhart’s law). P6 kill: hidden family에서 reward/semantic 방향 반대, verifier false-accept > 0.01. `[일반지식]`
- **Metamorphic testing**: 입력 변환 후에도 관계가 보존되어야 한다는 성질로 oracle 부재를 우회. 패널 CL-D(강체·스케일·단위·explode·레이어개명)와 연결. 단, 다이제스트상 B4 scale 팔 FAIL(0.7624)이므로 metamorphic을 “무조건 통과 게이트”로 쓰면 탐지기 결함을 보상으로 고정할 위험이 있다 — verifier 설계에서 분리 필요(§2.4, §7).

### 1.4 Cascade·지연 예측·선택적 분류

- **Classifier cascades (Viola–Jones 정신)**: 싼 단계로 다수를 처리하고 비싼 단계를 소수에만. P6 행동 집합{neighborhood 확장, hi-res render, deterministic gate, VLM jury, abstain}이 cascade의 stage에 대응. `[일반지식]`
- **Selective classification / abstention**: 거부 옵션으로 risk–coverage 트레이드오프. `abstain` arm이 명시. `[일반지식]`

### 1.5 그래프·공간 획득

- **Graph neighborhood expansion as action**: GNN/메시지패싱 전에 “어느 부분그래프를 펼칠지”를 고르는 문제는 budgeted subgraph acquisition과 유사. CubiCasa SEG-IR·실도면 Graph IR에서 junction/parallel 증거가 국소적일 때, 전역 explode는 비용 대비 이득이 불확실 — bandit이 “언제 펼칠지”를 학습. `[일반지식]`

### 1.6 본 제안에 대한 이론적 기대·한계 (정직)

**기대**: supervised가 이미 AUC 0.92급 신호를 줄 때, 한계 이득은 “틀린 경계를 싸게 고치는 것”이 아니라 “비싼 검증을 필요한 곳에만 쓰는 것”이다. Bandit은 그 할당 문제를 풀기 위한 최소 충분 도구다.

**한계**:

1. **Verifier가 없으면 RL/bandit 전체가 무효** — T26/CL-H 사활 게이트(FAR≤0.01). 현재 합성팩 B1 충실도 FAIL, PR-1 미완 → P6는 START HERE §5상 **아직 실행 단계가 아님**.
2. **Horizon 오진**: 실제가 H=1인데 full RL을 쓰면 off-policy 분산·시뮬레이터 과적합만 산다(제안서 Expected failure modes).
3. **Proxy reward**: training synthetic Brier↑가 CubiCasa/FloorPlanCAD semantic과 어긋날 수 있음(B1 fidelity gap, TV 0.265).
4. **Reference class 공허**: RC-WALL-ZL n=0 → 수치 forecast abstain이 올바름. 본 도시는 실험 설계이지 확률 예언이 아니다.

---

## 2. 알고리즘 정확 스펙

### 2.1 기호·객체

| 기호 | 의미 |
|------|------|
| \(h\) | 핸들(entity id). 평가 원자 단위는 per-handle `wall_member(h)∈{0,1}` (CL-C 계약). |
| \(b\) | block = 정책 의사결정 단위. 예: 공간적으로 인접한 handle 집합, 또는 uncertainty로 묶인 candidate cluster. |
| \(x_t\) | block \(b\)의 context 벡터(정책 관측). **truth label, mutation ID, test split flag 금지**. |
| \(\mathcal{A}\) | 행동 집합(아래). |
| \(a_t∈\mathcal{A}\) | 선택 행동. |
| \(r_t\) | 스칼라 보상(§2.5). |
| \(f_θ\) | 고정 supervised wall scorer (학습 중 freeze). 예: 탐지기 v1 가중합 또는 GBDT 확률. |
| \(V\) | verifier family (exact synthetic + metamorphic). LLM-as-judge ∉ \(V\). |

### 2.2 행동 집합 \(\mathcal{A}\) (네 행동 + abstain — cheapest probe 기준)

제안 Mechanism의 행동을 실행 가능하게 이산 arm으로 고정한다. Cheapest probe(§6 Cell-B)에서는 다음 **4+1**:

1. **`expand_graph`**: block 주변 Graph IR neighborhood를 1-hop(또는 예산 \(k\) hop) 확장 후 특징 재계산·\(f_θ\) 재점수.
2. **`render_hires`**: block bbox 고해상도 래스터화(로컬). VLM 호출 없이 기하/픽셀 특징만 추가하거나, FloorPlanCAD축에서는 crop 해상도만 상승. (프런티어 VLM은 별 arm)
3. **`run_det_gate`**: 결정론 metamorphic/exact gate 서브셋 실행(저비용 CPU). 예: 강체 불변 검사, 센티널 0벽/전벽, parallel-pair 일관성.
4. **`call_vlm_jury`**: VLM(로컬 qwen2.5-VL-3B 또는 승인 시 프런티어)에 block crop+벡터 요약을 보내 wall/nonwall 배심. **보상 계산에는 jury 점수를 쓰지 않음** — jury는 상태/특징만 바꿈. 최종 라벨 보상은 synthetic truth/verifier.
5. **`abstain`**: 추가 probe 없이 현재 \(f_θ\) 출력·기본 라우팅으로 확정(비용 0에 가깝고, 오교정 위험은 Brier로 반영).

> 구현 시 arm 수를 늘릴 수 있으나, **첫 offline bandit은 위 5개로 잠금**. Arm 추가는 새 prereg·새 시드 계획.

### 2.3 Context \(x\) (누출 방지 스키마)

허용 특징(예시, 모두 policy-visible):

- Supervised 불확실성: \(p=f_θ(h)\), margin \(|p-0.5|\), entropy, block 내 분산.
- 기하: parallel score, thickness, junction, log-length, \(\sin 2θ,\cos 2θ\) (다이제스트 GBDT 6특징과 정합).
- 그래프: degree, 1-hop 미전개 여부, INSERT depth(실도면), 레이어-해시(이름 문자열 원문 금지 권장 — CL-I/이름 prior 오염 방지).
- 비용 prior: 예상 latency/flops proxy(사전 측정 테이블 lookup).
- Cascade 단계: 이미 실행한 arm 비트마스크.

**금지(정책 상태에서 삭제)**:

- `y_true`, mutation family id, `split∈{train,val,test}` 중 test 표시, hidden generator seed, reward에 쓰인 verifier raw accept 플래그의 test-only variant id.

Train/val에서만 보상 계산기가 truth를 보며, 정책 네트워크 입력 텐서와는 물리적으로 분리된 채널이어야 한다(코드 레벨에서 `RewardBundle` ≠ `PolicyObs`).

### 2.4 Verifier \(V\) 스펙

**V1 — Exact synthetic truth (training reward primary)**  
생성기 \(G_{\mathrm{train}}\)이 handle마다 `wall_member`를 방출. 보상은  
\[
\Delta\mathrm{Brier} = \mathrm{Brier}(p_{\mathrm{before}}, y) - \mathrm{Brier}(p_{\mathrm{after}}, y)
\]  
단, \(y\)는 **reward-visible train family**에서만.

**V2 — Independent metamorphic verifier**  
변환 \(T∈\mathcal{T}\) (강체 회전·이동·반사, 단위 환산 등)에 대해  
\[
\mathrm{agree}(f_θ(x), f_θ(T(x))) \quad\text{또는}\quad \mathrm{rank\_invariant}
\]  
를 exact gate로 사용. **Scale 팔은 다이제스트상 FAIL(0.7624)** 이므로 초기 \(\mathcal{T}\)에서 scale을 **reward gate에서 제외**하거나 “soft penalty”로만 넣고, soundness audit의 mutation pack에만 둔다(탐지기 결함을 보상으로 학습하는 순환 방지).

**V3 — Hidden family (평가 전용, 정책·보상 학습 불가)**  
Hidden synthetic family + FloorPlanCAD truth(+ CubiCasa는 별도 전이 축). 최종 AUPRC/비용은 여기서만 보고.

**Soundness mutation pack**  
Verifier 자체의 FAR/FRR을 측정하는 별도 pack: 고의로 틀린 accept를 유도하는 adversarial mutation. Prereg:

- false-accept \(\le 0.01\)
- false-reject \(\le 0.05\)

### 2.5 보상 함수

한 에피소드(또는 horizon-1 결정)에서:

\[
r = \alpha\cdot\Delta\mathrm{Brier}_{\mathrm{train}} + \beta\cdot\mathbb{1}[\mathrm{exact\_gate\_pass}] - \lambda\cdot\widehat{C}_{\mathrm{compute}}(a) - \mu\cdot\widehat{C}_{\mathrm{latency}}(a)
\]

- \(\alpha,\beta,\lambda,\mu \ge 0\)은 prereg 그리드(소규모)로 val에서만 튜닝.  
- \(\widehat{C}\)는 사전 벤치 테이블(로컬 CPU/GPU 실측 median).  
- **금지**: LLM judge 점수, silver E1.5 합의, held-out/hidden label을 \(r\)에 넣기.

Multi-step RLVR일 때만 할인 반환 \(R=\sum_{t=0}^{H-1}\gamma^t r_t\). Bandit은 \(H=1\), \(\gamma\) 무의미.

### 2.6 정책 클래스

**Bandit (기본 경로)**  
- 입력 \(x\), 출력 \(\pi(a|x)\).  
- 후보: (i) multinomial logistic over arms on frozen features, (ii) LinUCB / linear Thompson on featurized \((x,a)\), (iii) small MLP policy with entropy bonus.  
- Offline: IPS/DR로 fixed router·uncertainty heuristic 대비 평가 후, 필요 시 on-policy 소량 fine-tune(합성 simulator).

**RLVR (조건부)**  
- 상태전이: \(a\)가 graph/render/VLM 결과를 병합해 \(x'\) 생성.  
- 알고리즘 후보: REINFORCE with baseline, PPO(클립), 또는 DQN-style Q over discrete arms.  
- **승격 조건(하드)**: 동일 시뮬레이터·동일 예산에서 \(\mathrm{utility}_{RL}/\mathrm{utility}_{bandit} \ge 1.05\). 미달 시 RL 경로 kill.

### 2.7 고정 라우터·불확실성 baseline (대조군)

1. **Fixed router**: 규칙 예) margin<τ₁ → `run_det_gate`; 그래도 불확실 → `expand_graph`; 최후 → `call_vlm_jury` 또는 `abstain`.  
2. **Supervised uncertainty acquisition**: \(H(p)\) 상위 \(q\%\) block에만 고정 순서 probe.  
3. **No-op**: 항상 `abstain`(순수 \(f_θ\)).

비열등·비용 절감은 1·2 대비로 측정.

### 2.8 의사코드

```
# Horizon-1 contextual bandit episode (training reward-visible only)
function EPISODE_BANDIT(block_b, f_θ, π, V_train):
  x ← OBSERVE(block_b)                    # no truth / no mutation-id / no test flag
  p0 ← f_θ.score(block_b)
  a  ← SAMPLE(π(.|x))                     # or ARGMAX for eval
  cost ← COST_TABLE[a]
  block_b', features' ← EXECUTE(a, block_b)
  p1 ← f_θ.score(block_b')                # f_θ weights frozen
  y  ← TRAIN_TRUTH(block_b)               # reward channel only
  r  ← α*(Brier(p0,y)-Brier(p1,y))
       + β*EXACT_GATE(V_train, block_b, block_b')
       - λ*cost.compute - μ*cost.latency
  UPDATE_POLICY(π, x, a, r)               # offline batch or online
  return r, cost, p1

# RLVR only if Cell-C lift gate passed
function EPISODE_RLVR(block_b, f_θ, π, H, γ):
  x ← OBSERVE(block_b); G ← 0; p ← f_θ.score(block_b)
  for t in 0..H-1:
    a ← SAMPLE(π(.|x)); x', p', c ← EXECUTE_AND_RESCORE(a, x, f_θ)
    r ← REWARD_DELTA(p, p', TRAIN_TRUTH, V_train, c)
    G ← G + γ^t * r
    STORE(x,a,r,x'); x,p ← x',p'
    if a == abstain: break
  UPDATE_RL(π, STORE)
  return G
```

### 2.9 하이퍼파라미터 공간 (prereg 후보, val만)

| 심볼 | 범위(제안) | 비고 |
|------|------------|------|
| \(α\) | {1.0} 고정 권장 | Brier 스케일 기준 |
| \(β\) | {0, 0.1, 0.5} | gate 항 |
| \(λ\) | log-grid on compute | 비용 민감도 |
| \(μ\) | {0} or small | latency; 로컬에선 \(λ\)에 흡수 가능 |
| margin τ / top-q | uncertainty baseline용 | 정책 외부 |
| \(H\) | {1} bandit; RL만 {2,3,4} | H>4 금지(초기) |
| \(γ\) | {0.9, 0.99} | RL only |
| learning rate | 소규모 | |
| seed | §6 | |

### 2.10 출력 아티팩트 계약

최종 해상 트리거 파일 `wsd_eval_p6.json` (스키마 초안):

```json
{
  "seat": "calibration_P6",
  "verifier_soundness": {"far": 0.0, "frr": 0.0, "n": 0, "pass": false},
  "auprc": {"policy": null, "fixed_router": null, "uncertainty": null, "delta_max_drop": null},
  "compute_cost_mean": {"policy": null, "baselines": {}, "saving_vs_best_baseline": null},
  "bandit_utility": null,
  "rl_utility": null,
  "rl_lift": null,
  "hidden_family_id": "REDACTED_UNTIL_EVAL",
  "splits": {"reward_train": "...", "val": "...", "hidden_test": "..."},
  "kill_flags": [],
  "resolution_verdict": "open"
}
```

---

## 3. 벽 과업 적응 설계

### 3.1 세 평가 축 접속

| 축 | 자산 | P6 역할 |
|----|------|---------|
| **CubiCasa5k SEG-IR** | train 4,200 / val 400 / test 400; 벽 선분율 ~11.8%; 레이어 중립 | Supervised \(f_θ\)의 주 전이 축. **정책 학습 보상에는 사람 라벨을 직접 쓰지 않는 것**을 기본으로 한다(외부셋은 최종 semantic 평가·전이 진단). test는 방법당 단발. |
| **FloorPlanCAD** | 래스터 5,308 + wall bbox/segmask (벡터 SVG 없음) | `render_hires`·로컬 VLM 배심의 시각 축. Hidden/final 성능의 한 축(제안 Truth source). 픽셀→핸들 역투영은 CL-G/T24 선결 — P6가 벡터 handle과 정렬해야 할 때는 합성 exact 또는 CubiCasa IR을 우선. |
| **1.dwg 실도면** | staged DXF, 도면정의 384; 최대 412,万亩 선분 | 시뮬레이터-to-real gap 진단. B3 벽-제로율 0.2135 PASS. 정책 비용 테이블의 latency 실측 소스. 학습 truth로는 부적합(라벨 희소·라이선스 PR-3). |

### 3.2 \(f_θ\)를 무엇을 쓰나

P6는 분류기를 재훈련하지 않는다. 실무 선택지:

1. **탐지기 v1 4채널 가중합** (parallel 0.35 / thickness 0.25 / junction 0.20 / layer 0.20) — 해석 가능, fast_score 존재. 전이 F1 0.236으로 **낮음** → bandit이 “어디서 추가 증거를 살지”를 배울 여지는 크지만, 천장 자체가 낮으면 획득만으로 AUPRC 비열등이 어려울 수 있다.
2. **HistGradientBoosting 확률** (F1 0.517, AUC 0.9215) — **권장 기본 \(f_θ\)**. 이미 정밀도 0.86급; 잔여 오류는 Direction 화살표/BoundaryPolygon/Door/Window/DimensionMark 등 **대역 내 평행 구조**. 이 FP 유형이 block context에 나타나면 `run_det_gate` 또는 `expand_graph`가 VLM보다 싸게 깨질 가능성이 높다.
3. 향후 CL-F의 GNN/PU — P1–P3 lift 후 교체. P6 인터페이스는 `score(block)->p`만 유지.

**이 방법이 더 가져올 수 있는 것**: GBDT가 놓치는 FP/FN **국소 클러스터**에만 추가 연산(그래프 전개·게이트·선택적 VLM)을 집중해, **전 도면 균일 고비용 파이프라인 대비 평균 compute ≥20% 절감**하면서 AUPRC 감소 ≤0.01. Semantic “마법”이 아니라 **자원 배분**이 가치.

### 3.3 START HERE 사다리와의 정합 (강제 순서)

1. P1: 독립 wall-specific synthetic generator/resolver + WSD-EVAL-v1 split manifest **동결**.  
2. 100-case P1 probe로 v0 candidate-recall 천장 측정.  
3. 동일 truth/split으로 P2→P3 incremental lift.  
4. Vector가 놓치는 prereg subgroup에서만 P4.  
5. P5는 E1.5 admission 후; **P6는 verifier FAR≤1% 확인 후에만**.

→ 본 도시는 **설계·셀·킬조건 동결**이 목적이다. 현재 시점(합성 B1 FAIL, PR-1 미구축, T26 미계측)에서는 **실행 착수 금지**. Cell-0이 그 게이트.

### 3.4 Block 정의 (벽 특화)

권장 초기 정의(구현 단순·누출 적음):

- CubiCasa IR: 같은 방에서 유래하거나, 거리 ≤ δ(px)이며 평행 후보로 묶인 segment 집합. δ는 val에서만 선택하되 test 전 봉인.
- 대안: uncertainty top-k handles를 union-find로 클러스터.

평가 단위는 여전히 per-handle. Block 정책이 handle 점수를 갱신해도 **집계 지표는 handle AUPRC/Brier**.

### 3.5 Simulator-to-real

합성 1,000 state offline bandit이 통과해도, CubiCasa val·1.dwg 샘플에서 **비용 절감이 재현되지 않으면** full 경로 kill(제안 failure: simulator-to-real gap). 실도면은 보상 truth가 없으므로 “동일 정책으로 평균 arm cost·abstain율·게이트 통과율”만 추적하는 **배포 진단**으로 쓴다.

---

## 4. 데이터·컴퓨트 요구

### 4.1 데이터

| 필요 | 상태(다이제스트) | P6 함의 |
|------|------------------|---------|
| Wall synthetic generator + exact truth | **부재/FAIL** (B1 KS 0.5792, TV 0.265; PR-1) | Cell-0 블록. Reward 불가. |
| WSD-EVAL-v1 split manifest | 동결 전제 | train reward family ≠ hidden family |
| Metamorphic battery + sentinel | CL-D; scale FAIL | reward \(\mathcal{T}\)에서 scale 제외 권고 |
| CubiCasa SEG-IR | 완료(실패 0) | \(f_θ\)·최종 전이 평가 |
| FloorPlanCAD raster | 로컬 보유 | render/VLM; 최종 축 |
| Verifier soundness mutation pack | 미구축 가정 | T26 계측 필수 |
| 외부셋 학습 arm | PR-3 counsel 미해결 | P6 기본은 합성 reward; CubiCasa 라벨로 정책 보상 학습은 counsel 전 금지 권고 |

### 4.2 로컬 실행 계획 (RTX 5070 Ti 16GB · RAM 64GB · DGX unreachable)

**가능·우선**:

- 합성 state 시뮬레이터 + offline gate + offline bandit offline(CPU 중심, 1,000 states).  
- GBDT/`fast_score` 재점수, graph 1-hop 확장.  
- 로컬 qwen2.5-VL-3B로 `call_vlm_jury` 소량(16GB에서 batch=1 crop). 프런티어 API **미사용**(미승인).

**비권장/연기**:

- 대규모 parallel env PPO, Ornith-35B 배심 — DGX unreachable.  
- 전 도면 hi-res + VLM — 비용 폭발; bandit이 줄이는 대상이지 기본값이 아님.

### 4.3 DGX 계획 (조건부, 승격 후)

사용 조건(모두 충족):

1. Cell-0 verifier FAR≤0.01.  
2. Cell-B bandit이 fixed/uncertainty 대비 비용 절감≥20% with AUPRC 비열등(val).  
3. Cell-C에서 multi-step 필요성 입증(탐욕≈상한 아님, H>1 value of information).  
4. DGX reachable + vLLM 자원 시간 **분리 청구**.

용도: parallel environment rollouts, policy training. **시뮬레이터·bandit probe는 로컬에 잔류**.

### 4.4 예산 감각 (설계치, 새 실측 아님)

- Cell-0 verifier audit: 로컬 CPU 수 시간.  
- Cell-B 1,000×5 arms offline: 로컬 1일 규모(패널 CL-H probe 큐와 동일 계급).  
- Cell-C greedy vs beam 보상지형(학습 0): 1일.  
- RL full: DGX 수일 — 승격 시에만.

---

## 5. 구현 계획

### 5.1 모듈·파일 골격 (신규 코드는 본 도시 작성 범위 밖 — 설계만)

```
wsd_p6/
  obs.py              # PolicyObs 스키마; leakage assert
  actions.py          # expand_graph, render_hires, run_det_gate, call_vlm_jury, abstain
  cost_table.py       # median compute/latency proxies
  verifier/
    exact_synthetic.py
    metamorphic.py    # scale excluded from reward gates by default
    soundness_pack.py # FAR/FRR
  reward.py           # ΔBrier + gate - cost; no LLM judge
  policies/
    baselines.py      # fixed router, uncertainty
    bandit_offline.py # IPS/DR + LinUCB/logistic
    rlvr.py           # gated
  sim/
    state_gen.py      # 1,000 training states from G_train
  eval/
    wsd_eval_p6.py    # writes wsd_eval_p6.json
  configs/
    prereg_p6.yaml    # bands, seeds, arm set freeze
```

### 5.2 기존 도구 접속점

| 기존(패킷·패널 언급) | 접속 |
|---------------------|------|
| `fast_score` / 탐지기 v1 | `f_θ` 또는 특징 채널; EXECUTE 후 재호출 |
| `cubicasa_ir` | block 기하·그래프 neighborhood |
| `cubicasa_ml` | GBDT \(f_θ\) 확률, 6특징 |
| `evidence_grid` | 셀 결과 xlsx 의무 기록 |
| metamorphic / B4 하네스 | `run_det_gate`·V2 |
| FloorPlanCAD 로더 | `render_hires` |
| qwen2.5-VL-3B | `call_vlm_jury` 로컬 |

### 5.3 개발 규모 추정

| 단계 | 규모 | 의존 |
|------|------|------|
| Obs/action/reward 스키마 + leakage assert | S | 없음 |
| Cost table 벤치 | S | 로컬 |
| Exact+metamorphic verifier 래핑 | M | PR-1, CL-D |
| Offline bandit + baselines | M | simulator |
| Eval JSON + xlsx | S | |
| RLVR | L | Cell-C 승격, 가능 시 DGX |

**Occam**: RLVR 코드는 Cell-C 통과 전 stub만.

### 5.4 누출 테스트 (구현 의무)

단위 테스트: `PolicyObs` 직렬화 키 집합에 `y`, `mutation_id`, `is_hidden`, `test_flag`가 있으면 CI fail. Reward 모듈만 `TruthHandle` import 가능.

---

## 6. 실험 셀 정의

공통 원칙: **val=개발·튜닝 허용, test=방법당 단발, 합격선 프리레그 봉인, 셔플 대조군 의무, 증거 xlsx, 실패도 기록**.  
수치 band는 제안 prereg 초안을 동결한 것(새 측정 아님).

### Cell-0 — Verifier soundness gate (P6 착수 조건)

| 항목 | 내용 |
|------|------|
| **가설** | 독립 mutation pack에서 verifier FAR≤0.01, FRR≤0.05를 만족하는 \(V\)가 존재한다. |
| **지표** | FAR, FRR, n_mutations; exact gate 재현성(시드 고정). |
| **합격선** | FAR≤0.01 ∧ FRR≤0.05 ∧ PR-1/WSD-EVAL-v1 동결 완료. |
| **킬 조건** | FAR>0.01 → **verifier 경로·P6 전체 중단**(제안 kill). FRR>0.05는 verifier 재설계 없이 정책 학습 금지. |
| **예산** | 로컬 CPU; PR-1 완료 후 1일. |
| **시드** | soundness_pack seeds {0,1,2}. |

### Cell-A — Reward family ≠ Hidden family 분리 감사

| 항목 | 내용 |
|------|------|
| **가설** | 정책 학습에 노출된 generator family와 hidden family의 식별자가 파이프라인상 교차되지 않는다. |
| **지표** | manifest diff; 정책 로그에 hidden id 출현 횟수=0; train/hidden 특징 분포 TV(참고, B1 TV 0.265는 현 합성 한계). |
| **합격선** | 교차 0건; test gate variant 미노출. |
| **킬** | 교차 발견 시 학습 로그 폐기·재동결. |
| **예산** | 0.5일. |
| **시드** | n/a(감사). |

### Cell-B — Cheapest probe: offline contextual bandit (full RL 금지)

| 항목 | 내용 |
|------|------|
| **가설** | 합성 1,000 state·5 arms offline bandit이 fixed router 및 uncertainty heuristic 대비 **평균 compute ≥20% 절감**하고, 최종(또는 val proxy) AUPRC 감소 ≤0.01. |
| **지표** | mean compute cost, mean latency, AUPRC(handle), Brier(train reward-visible), arm 선택 분포, IPS/DR utility. |
| **합격선** | saving≥0.20 ∧ AUPRC drop≤0.01 vs 두 baseline 모두(또는 prereg에 “둘 다”로 명시한 대로). Verifier Cell-0 PASS 전제. |
| **킬** | saving<0.20 → **policy/acquisition 경로 중단**(제안). AUPRC drop>0.01 → 중단. FAR 회귀 시 중단. |
| **예산** | 로컬 1일; GPU는 VLM arm 소량만. |
| **시드** | state_gen {10,20,30}; policy {100,200}; 보고는 median±IQR. |
| **금지** | full RL, hidden family 튜닝, test 단발 소비. |

### Cell-C — Horizon 진단: greedy vs beam / value of multi-step (학습 0)

| 항목 | 내용 |
|------|------|
| **가설** | 추가 probe의 정보가치가 H=1에 거의 흡수되지 않는다(즉 multi-step가 필요). |
| **지표** | 동일 예산에서 greedy(단회 best arm) utility vs beam/depth-H planning utility; “greedy≈상한”이면 RL 불요(패널 CL-H). |
| **합격선(RL 존속)** | \(\mathrm{utility}_{multi}/\mathrm{utility}_{banditH1} \ge 1.05\) **또는** 동일 계산의 RL lift 사전 프록시 ≥1.05. |
| **킬** | lift<1.05 → **full-RL 경로 중단**, bandit에서 동결(제안). |
| **예산** | 로컬 1일; 학습 0(열거·시뮬). |
| **시드** | {11,22,33}. |

### Cell-D — Bandit on-policy 소량 적응 (합성 simulator)

| 항목 | 내용 |
|------|------|
| **가설** | Offline에서 고른 π를 소량 on-policy로 다듬어도 val proxy에서 band 유지. |
| **지표** | Cell-B와 동일 + 정책 entropy, VLM arm 비율(편향 감시). |
| **합격선** | Cell-B band 유지; VLM arm 비율이 cost 테이블상 비합리적 쏠림(예: >사전 등록 상한)이면 λ 재조정 후 1회만 재시도. |
| **킬** | Goodhart: train Brier↑ & val AUPRC↓; 또는 VLM 편향 미해소. |
| **예산** | 로컬 1–2일. |
| **시드** | {40,41,42}. |

### Cell-E — Hidden synthetic + FloorPlanCAD 봉인 평가 (단발)

| 항목 | 내용 |
|------|------|
| **가설** | Claim 성립: semantic 비열등∧compute≥20% 절감. Hidden에서 reward/semantic 동향 일치. |
| **지표** | AUPRC, compute saving, verifier FAR 재확인, `utility` if RL; CubiCasa **test**는 별도 단발 슬롯(쓰면 소진). |
| **합격선** | prereg band 전부; RL 사용 시 lift≥1.05. |
| **킬** | hidden에서 reward↑ semantic↓ → 정책 폐기. FAR>0.01 → 폐기. |
| **예산** | 평가 패스 1회; 재실행 금지(단발). |
| **시드** | 평가 시드 봉인값 1개. |
| **산출** | `wsd_eval_p6.json` + evidence xlsx. |

### Cell-F — RLVR full (조건부)

| 항목 | 내용 |
|------|------|
| **가설** | Multi-step RLVR이 bandit utility를 ≥5% 개선. |
| **전제** | Cell-0·B·C PASS, DGX 필요 시 reachable. |
| **지표** | utility_RL / utility_bandit, hidden AUPRC, cost. |
| **합격선** | lift≥1.05 ∧ Cell-E band 동시. |
| **킬** | lift<1.05 → RL 폐기·bandit 채택. off-policy 불안정(분산 폭발) 시 early stop=실패 기록. |
| **예산** | DGX 수일 또는 로컬 소규모 H≤3만. |
| **시드** | {50–54}. |

### Cell-G — 실도면 배포 진단 (라벨 없음)

| 항목 | 내용 |
|------|------|
| **가설** | 1.dwg 샘플에서 arm 비용·abstain율이 합성 정책과 동일 방향. |
| **지표** | mean cost, arm mix, B3 정합(벽-제로율 유지), latency. |
| **합격선** | 방향 일치(사전 등록 허용 편차); 불일치 시 simulator-to-real gap 티켓 OPEN. |
| **킬** | P6 claim의 “실환경 절감” 주장을 금지(연구 주장 축소). 합성 claim은 Cell-E로 제한 가능. |
| **예산** | 0.5–1일. |
| **시드** | 도면정의 샘플 고정 리스트. |

### 셀 과소·과잉 검토

- 과소 방지: soundness / offline bandit / horizon / hidden / (조건부) RL을 분리.  
- 과잉 방지: Taguchi 대스크린·GNN 동시 학습·프런티어 배심 대량 호출은 본 제안 NON-GOAL.

---

## 7. Red team 티켓 응답

패널 OPEN 티켓 중 **P6/CL-H·verifier-guided acquisition에 걸린 것**을 지목한다. (전체 34건 원문은 `seats/red_teamer.md`; 여기서는 응답 입장.)

| 티켓/공격 | 관련성 | 입장 |
|-----------|--------|------|
| **T26** verifier FAR≤0.01 선계측 | **사활** | **수용+하드 게이트**. Cell-0 미통과 시 P6 실험 착수 자체를 하지 않는다. FAR>0.01 kill은 제안서와 동일. |
| **T6 / 공격 E** 평가 단위 per-handle vs 집합 조립 혼선 | 높음 | **해소 설계**: 지표는 per-handle AUPRC/Brier 고정; block 정책은 획득 계층으로 격리. 집합-조립을 별 산출물로 보고하지 않으면 claim 무효. |
| **T1 / 공격 A** 대리 독립성 (합성·외부·metamorphic·silver 동일 prior) | 높음 | **수용(위험 인정) + 완화**: 보상에서 silver/LLM 제외; metamorphic과 exact synthetic을 분리 audit; CubiCasa는 최종 전이만. CL-E 3원 불일치와 병행 전까지 “독립 verifier” 주장은 약하다. |
| **T2 / 공격 B** 벽 합성 생성기 부재 | 높음 | **선결 수용**. PR-1/CL-C 없이 P6 reward 불가. 도시만 작성·실행은 Cell-0에서 차단. |
| **T7 / 공격 F** 0벽 sentinel·recall 최저선 | 중–고 | **해소**: `run_det_gate`에 0벽/전벽 sentinel 의무. 위반율-only로 보상하지 않음(0벽 탐지기 Goodhart 방지). |
| **T10/T23** Graph IR adjacency 완전성 | 중 | `expand_graph` arm의 전제. 감사 전엔 arm을 no-op 처리하거나 Cell-B에서 제외 가능 — **미감사 상태면 expand arm 비활성**이 정직한 축소. |
| **T24** 픽셀→핸들 역투영 | 중(FloorPlanCAD) | 벡터 handle과 래스터 jury를 정렬할 때만 필요. 미검증 시 `call_vlm_jury`는 **래스터 전용 점수 → handle에 soft prior만**, exact reward는 합성 handle에 한정. |
| **T13** DGX Ornith vision | 중 | unreachable → 로컬 VLM만; DGX 계획 분리(§4.3). |
| **T5 / PR-3** 라이선스 | 중 | 외부 라벨로 정책 보상 학습 금지 권고; 평가는 counsel 정책 준수. |
| **T15** seed-confound | 중 | Cell-B/D 다중 시드·median 보고로 수용. |
| **C07** (패널: greedy vs beam으로 RL 자리 종결) | 핵심 | **Cell-C가 곧 응답**. 학습 0 프로브로 full RL 존속 여부를 증거 종결. |

**명시적 비응답(다른 클러스터 주관)**: T3/T4 E1 법의학(CL-A), T14/T33 lexicon(CL-I), T27 face-first(CL-J), T31 래스터 본선(CL-G PARK) — P6가 직접 해소하지 않음.

---

## 8. 인접 제안과의 관계

### 8.1 병합 가능 지점

| 인접 | 관계 |
|------|------|
| **CL-H / platt P4 / doe P4 / feyerabend P4** | 동일 분할: 분류=supervised, 획득=bandit·RLVR. P6는 calibration 좌석의 **실행 스펙·prereg band·킬트리** 담당. |
| **CL-C / PR-1 / calibration 공통 resolution** | Reward truth·split 동결. P6의 부모 의존. |
| **CL-D metamorphic** | `run_det_gate`·V2 구현체. Sentinel 수정(T7) 공유. |
| **CL-F 학습 사다리** | \(f_θ\) 공급자. P6는 CL-F 모델을 freeze해 씀. |
| **CL-G VLM** | `call_vlm_jury` 공급. E1.5 B1≥0.70 AND B4≥0.70 전에는 프런티어 silver 배심 금지(패널 모순 #1 — calibration 게이트가 정본). 로컬 qwen은 별도. |
| **CL-E 교차요인** | Hidden vs train family 전이 갭을 P6 Goodhart 감시와 공유. |
| **CL-K anti-silver** | 보상에서 silver 배제로 이미 정합; silver-distill 암은 P6에 넣지 않음. |

### 8.2 차별점

- P1–P3: **재현율/표현 천장·지도학습 lift** — 점수를 올리는 쪽.  
- P4–P5: **서브그룹·VLM 본선/배심** — 표현 채널 확장.  
- **P6**: 점수를 올리는 것이 아니라 **이미 있는 \(f_θ\) 위에서 증거 구매 정책**을 푼다. 성공해도 F1 대폭 상승이 아니라 **동등 성능·절감된 compute**가 주 성과.

### 8.3 이 제안이 죽어야 하는 조건 (정직)

다음 중 **하나**면 P6(해당 하위경로)를 죽인다:

1. **Verifier FAR>0.01** (또는 soundness pack 구축 불가) → 전체 사망.  
2. **PR-1/B1 충실도 미달 지속**으로 exact train truth가 실세계와 체계적으로 불일치 → 보상 해독 불가 → 전체 사망 또는 “합성-only toy”로 강등(운영 claim 금지).  
3. **Offline bandit이 비용 절감<20%** 또는 **AUPRC 감소>0.01** vs fixed/uncertainty → acquisition policy 사망.  
4. **Hidden family에서 train reward와 semantic 지표 방향 반대** → 정책 사망(Goodhart).  
5. **Cell-C에서 multi-step lift<5%** → RLVR만 사망; bandit은 생존 가능.  
6. **실제 horizon≈1이 반복 재현**되면 full RL 유지 비용이 정당화되지 않음 → RL 사망이 올바른 결과(실패가 아니라 Occam 성공).  
7. **`expand_graph` 전제(T10) 붕괴**로 행동 집합이 `abstain`/`det_gate`만 남고 baseline과 동일 → 정책 가치 0 → 중단.  
8. **프런티어/VLM에 정책이 고착**이나 API 미승인·DGX 불통으로 그 arm이 비실행인데 시뮬레이터만 VLM 이득을 가정 → simulator-to-real 사망.

### 8.4 현재 시점 판정

- `resolution_verdict`: **open**  
- `abstain_flag`: **empty_reference_class** 유지가 올바름.  
- 실행  readiness: **NOT READY** — START HERE §5·Cell-0·PR-1 미충족.  
- 본 도시의 역할: 게이트·셀·알고리즘·킬트리를 **사전 봉인**해, 선결이 끝나는 즉시 최저가 경로(Cell-B)로 들어가게 함.

---

## 부록 A — Prereg band 요약 (동결 초안)

| Band | 값 |
|------|-----|
| Verifier FAR | ≤0.01 |
| Verifier FRR | ≤0.05 |
| AUPRC 비열등 | 감소 ≤0.01 vs fixed router **및** uncertainty acquisition |
| Compute saving | ≥20% mean |
| RL 존속 | utility_RL / utility_bandit ≥1.05 |
| Score type | brier (보상); 보고는 AUPRC+Brier+cost |
| LLM judge reward | 금지 |
| Forecast | null |

## 부록 B — Update log 사전 약정 (제안서 승계)

- 2026-07-17 KST: 최초 abstain.  
- Sound verifier + hidden-family 비용 절감 증거 → (미래) full-RL·policy 성공 확률 상향 갱신 허용.  
- Proxy hacking·FAR 초과·bandit 동률 → full-RL 확률 하향.  
- 본 작성(2026-07-18): 실행 전 설계 도시; 수치 forecast는 계속 null.

---

DOSSIER_COMPLETE: calibration_P6
