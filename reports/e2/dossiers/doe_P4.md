# DOE P4 심층 도시에 — RLVR-EARNS-ITS-SEAT FACTORIAL

**seat_id**: `doe_P4`  
**제안**: R26 C07을 교리가 아닌 효과로 판정 — 패러다임×라벨예산×정답원품질 완전요인  
**클러스터**: CL-H (RL 자리 판별)  
**상태**: UNRUN (설계·프리레그만; 수치 주장은 패킷 다이제스트에 한함)

---

## 0. 한 줄 판결 계약

C07("고정라벨 분류에 RL은 오용, supervised가 저분산·표본효율")을 prior로 받거나 기각하지 않는다.  
`A paradigm × C label_budget` 상호작용을 **사전등록 표적**으로 추정하고, (i) A×C 유효 → 맥락없는 C07 반증, (ii) A×C null ∧ A_main(RL계)≤0 → C07 지지(정직한 kill), (iii) RLVR이 low-truth에서 gate↑ & hold-out↓ → reward-hacking(C08) 확정.  
미확인 RL 우위를 PASS로 올리지 않는다 (`confirmation_run = PASS_WITH_DEFERRAL`).

---

## 1. 이론적 근거·선행연구

### 1.1 왜 “교리”가 아니라 “요인”인가

R26 C07은 표본효율·분산 측면에서 supervised가 RL보다 유리하다는 **맥락 없는 단정**으로 적혀 있다. 발주자 이의(제약 4)와 패널 CL-H 수렴은 같은 분할을 요구한다: **per-handle 고정 분류 = supervised 본선**, **획득·라우팅·검증가능 보상 = RLVR/bandit 후보**. Doe P4의 기여는 이 분할을 말만으로 두지 않고, 패러다임을 요인 수준으로 놓고 main effect와 상호작용을 측정하는 **완전요인 설계**로 옮기는 것이다.

C07의 예측을 통계적으로 쓰면:

- main effect of RL paradigm ≤ 0 (동일 예산·동일 평가에서 supervised ≥ RL계)
- **상호작용 없음** (특히 A×C = 0)

따라서 “라벨 희소에서 active/RLVR이 이기고, 라벨 풍부에서 supervised가 이긴다”는 패턴이 Lenth ME를 넘으면 C07의 **맥락없는** 판은 반증된다. 좁은 판(terminal 벽/비벽 라벨 자체에 RL)은 이 설계도 지지하지 않으며, 그 수준에서는 C07이 옳을 것으로 예상한다(§8 abstention과 정합).

### 1.2 방법론 계보 (기법·시스템 이름)

| 계보 | 이 좌석에서의 역할 | 대표 이름 (일반 지식; 요검증 표기) |
|------|-------------------|-----------------------------------|
| 고전 실험계획 | A×B×C 완전요인, 별칭 없는 2FI/3FI | Fisher factorial; Box–Hunter–Hunter; Lenth PSE / margin of error (요검증: 정확한 Lenth 임계 상수) |
| Active learning | 다음 라벨할 도면 질의 정책 (horizon>1) | Uncertainty sampling; BALD; Expected Error Reduction (Settles survey — 요검증) |
| Contextual bandit / RL | horizon≈1이면 bandit, >1이면 진짜 RL-shaped | LinUCB/Thompson; PPO/GRPO; RLVR (verifiable reward) |
| Reward hacking 방어 | gate-only vs gate+hold-out 벌점 | Goodhart; Amodei et al. reward hacking 논의(요검증); R26 C08 |
| Verifier-gated RL | 보상을 검증가능 신호로 제한 | RLVR / process·outcome verifier; U02·CON02를 **효과(B축)**로 대리 |
| Occam 사다리 | supervised baseline 먼저 | HistGradientBoosting 이미 val F1 0.517 — RL은 이 상한을 **다른 산출물**에서만 도전 |

### 1.3 CL-H와의 이론적 정합

패널은 4석이 같은 분할에 수렴했다고 기록한다. Doe P4는 그중 **“효과 추정·상호작용·킬 조건의 실험계획자 축**이다.

- Platt P4: 집합-조립 vs beam/ILP, 학습 0 greedy≈beam이면 훈련 전 kill  
- Calibration P6: verifier-guided acquisition, bandit 우선·RLVR 조건부  
- Feyerabend P4: C07의 교리적 독해 해체(counter-induction)  
- Doe P4: **12셀 완전요인 + hacking 프로브**로 C07을 증거로 종결

세 좌석이 “어디서 RL이 사는가”를 말하고, 이 좌석은 “그 자리의 **효과 크기와 조건성**”을 잰다.

### 1.4 확률 반응으로서의 특수성

패킷 `deterministic_note`가 강조하듯, supervised 셀은 (데이터, seed) 고정 시 준결정적이지만 RLVR/active는 탐색 확률성이 내재한다. 따라서 P4는 다른 doe 제안과 대칭이 아니다: **잡음 통계·seed 반복(≥5)이 정당한 유일한 제안**이다. 결정 반응에 확률 통계를 들이는 오류와, 확률 반응에 결정 통계만 쓰는 오류를 둘 다 경계한다(§expected_failure_modes ④).

---

## 2. 알고리즘 정확 스펙

### 2.1 기호·단위

- 도면(def) \(d\), 선분/핸들 \(h\), 이진 벽 멤버십 \(y(h)\in\{0,1\}\)
- 평가 단위: **per-handle** `wall_member(h)` (CL-C 계약과 정합; 집합-조립은 별도 산출물로 격리 — T6)
- 라벨 예산 \(B\in\{\text{scarce},\text{abundant}\}\) — 도면 수 또는 핸들 라벨 수로 사전봉인
- 정답원 \(T\in\{\text{T-SYN clean},\text{T-SILVER noisy}\}\)
- 보상 오라클 \(R_{\text{META}}\) (게이트) + hold-out \(R_{\text{SYN}}\) / \(R_{\text{SILVER}}\) F1

### 2.2 요인 수준 정의

#### A — paradigm (3)

**A1 `supervised-silver`**

```
입력: 특징행렬 X (6특징 이상; 최소: parallel, thickness, junction, log_len, sin2θ, cos2θ)
      라벨 y from T (B 수준에 따른 표본)
출력: 분류기 f_θ: x → p(wall)
손실: 이진 cross-entropy 또는 HistGradientBoosting 기본 손실
하이퍼: learning_rate, max_depth/max_leaf_nodes, min_samples_leaf, l2
시드: 데이터 subsample seed + 모델 seed
결정성: 준결정 → seed 반복으로 분산 추정
```

베이스라인 앵커(다이제스트): CubiCasa val에서 HGB F1 **0.517**, AUC **0.9215**, 셔플 AUC **0.375** PASS.

**A2 `RLVR-verifiable-reward`**

```
상태 s_t: 현재 부분 예측·미결 후보·게이트 통과 이력 (은닉상태 기록 의무)
행동 a_t: 도구/가설 갱신 — 예: 임계 조정, 이웃 확장, 재점수, abstain
         (terminal per-handle 라벨을 직접 RL로 찍는 것은 범위 밖 — §abstention ①)
전이: 환경이 IR·스코어러를 갱신; L-FIRM으로 같은 firm 재질의 금지
보상 r_t = α·1[R-META gate pass] + β·F1_batch(R-SYN) - γ·cost
       프로브팔: r'_t = r_t - δ·penalty(hold-out divergence)
정책: π_φ(a|s); 갱신 = GRPO/PPO류 (로컬 자산: qwen2.5-VL-3B의 GRPO 파인튜닝 실존을
       정책 백본 후보로만 기록 — 벡터축은 HGB/소형 정책 헤드가 1차)
하이퍼: α,β,γ,δ; clip/ε; rollout_len; entropy_coef; seed ≥5
로그: 전 step (s,a,r,gate,holdout_proxy) 보존
```

**A3 `active-acquisition-policy`**

```
풀: 미라벨 도면 집합 U (firm 블록 L-FIRM)
정책 π_acq: U → d*  (다음 라벨 질의)
획득 후: A1과 동일 supervised 재학습 또는 증분 적합
보상/효용: ΔF1_holdout / label_cost  (라벨당 밴드도달비용)
horizon > 1: 질의 순서가 상태 → run-order가 실질적 노이즈 (seed 고정+기록)
획득 점수 후보(프리레그 중 하나 봉인):
  score(d) = uncertainty(d) + λ·diversity(d) - μ·dup_firm_penalty(d)
```

#### B — truth_quality (2)

| 수준 | 정의 | 역할 |
|------|------|------|
| high | T-SYN clean (충실도 게이트 통과 후; 현재 B1 FAIL이므로 **PR-1/CL-C 선결**) | verifier 건전 대리 |
| low | T-SILVER noisy (E1.5 silver; 가문≈2로 취급, Pearson 탐지기↔silver 0.2911) | U02 불건전 대리 |

B는 “절대 건전성 판정”이 아니라 **상호작용 검출용 대리**다(abstention ②).

#### C — label_budget (2)

사전봉인 초안(실행 전 Paul 확정 가능; 여기서는 설계값):

| 수준 | CubiCasa 벡터축 초안 | 의도 |
|------|---------------------|------|
| scarce | train 도면 ≤ 200 또는 라벨 핸들 ≤ 5e4 | C07 표본효율 주장의 생존 구간 |
| abundant | train 도면 ≥ 2000 (상한 4200) 또는 핸들 ≥ 1e6 | supervised가 이기는지 확인 |

동일 C 수준에서 A1/A2/A3가 **같은 라벨 수**를 쓰도록 맞춘다(active는 질의로 채운 라벨 수가 scarce/abundant 캡에 도달할 때까지).

### 2.3 Reward-hacking 프로브 (내장 2셀)

완전요인 12셀과 직교하는 대조:

| 프로브 | 보상 | 기대 서명 |
|--------|------|-----------|
| RH0 | gate-only (`R-META`) | hacking 시 gate↑ & hold-out F1↓ |
| RH1 | gate + hold-out 벌점 | hacking 억제; 진성 개선만 생존 |

판정 (사전봉인):  
`Δgate > +τ_g` AND `ΔF1_holdout < −τ_f` → **C08 reward-hacking 확정** (RLVR 가짜 승리).

### 2.4 반응(response) 및 추정 모델

**1차 반응**

- \(Y_1 =\) hold-out F1 on `R-SYN` 및/또는 `R-SILVER` (밴드 공통)
- \(Y_2 =\) 라벨당 밴드도달비용 \(= B_{\text{labels}} / \max(\varepsilon, F1 - F1_{\text{floor}})\) (active용; ↓ 선호)

**프리레그 모델**

\[
Y = \mu + A_i + B_j + C_k + (A\times C)_{ik} + (A\times B)_{ij} + \epsilon
\]

- 표적: \((A\times C)\)  
- 보조: \((A\times B)\) — RLVR 가치가 verifier 품질에 조건부인가  
- 효과 유의: Lenth ME 초과 (또는 사전봉인 bootstrap CI가 0 제외)  
- 3FI는 완전요인이라 추정 가능하나 **판정에 사용하지 않음**(검정력·해석 부담; 보고만)

### 2.5 의사코드 — 한 셀 실행

```
procedure RUN_CELL(A, B, C, seed, reward_mode):
  freeze IR cache for split(C)
  T ← truth_source(B)          # T-SYN or T-SILVER
  assert L_FIRM: no re-query same firm in active
  if A == supervised:
    D ← sample_labeled(T, budget=C, seed)
    f ← fit_HGB_or_equiv(D, seed)
    Y ← eval_holdout(f, R_SYN, R_SILVER)
  elif A == active:
    U ← unlabeled_pool(seed); L ← ∅
    while |L| < budget(C):
      d* ← π_acq(U, L, seed); record order
      L ← L ∪ label(d*, T); U ← U \ {d*}
      f ← refit(L)
    Y ← eval_holdout(f); cost ← |L| / lift(Y)
  elif A == RLVR:
    for episode in rollouts(seed):
      traj ← collect(π_φ, env, reward_mode)
      update π_φ (GRPO/PPO)
      log traj
    Y ← eval_holdout(π_φ); gate ← R_META stats
  write xlsx row + seeds + IR hash
  return Y, gate, cost
```

### 2.6 하이퍼파라미터 공간 (탐색 상한 — val만)

| 블록 | 탐색 | 금지 |
|------|------|------|
| HGB | lr∈{0.05,0.1}, max_leaf∈{31,63}, subsample | test 튜닝 |
| active | λ,μ ∈ {0,0.3,1.0}; acquisition ∈ {entropy, margin} | firm 재질의 |
| RLVR | α,β,γ 격자 소형(≤8); entropy_coef; 5 seeds | silver를 보상으로 사용( Platt와 정합: silver는 hold-out 보고만 — 단 A1 학습 라벨로서의 silver는 B=low 정의상 허용, **보상 오라클로는 금지**) |

---

## 3. 벽 과업 적응 설계

### 3.1 세 축 하네스 접속

| 축 | 자산 | P4 접속 | 비고 |
|----|------|---------|------|
| CubiCasa SEG-IR 벡터 | train 4,200 / val 400 / test 400; 벽율 ~11.8%; 라벨 누출 0 | **주 실험 무대** (A1·A3·부분 A2) | test 단발; val만 튜닝 |
| FloorPlanCAD 래스터 | 5,308 + bbox/segmask; SVG 없음 | A2 백본이 VL이면 보조; **본 요인 반응은 벡터 F1** | NC counsel(PR-3) 전 학습 arm 보류 |
| 1.dwg 실도면 | 384 def; B3 0.2135 PASS; 최대 412k 선분 | confirmation / L-FIRM 블록; 전이·비용 스트레스 | 연산 병목 실증됨 |

### 3.2 이미 아는 천장과 P4가 가져와야 하는 것

다이제스트 고정 사실:

- 기하 탐지기 v1 → CubiCasa val F1 **0.2358** (P≈기저율, R 높음)  
- HGB 6특징 → val F1 **0.517** (탐지기 대비 2.2배)  
- FP 주범: Direction/BoundaryPolygon/Door/Window/DimensionMark  
- 축척 2~15mm/px에서 성적 무감 → 물리 두께 prior 무력  

P4가 **더 가져올 수 있는 것**(과대주장 금지):

1. **표본효율 곡선**: scarce에서 active가 같은 라벨 수로 HGB 랜덤샘플을 넘는지 → C07 맥락판 흔들기  
2. **조건부 RLVR**: 고정 분류 F1을 직접 올리는 게 아니라, 검증가능 게이트·획득·라우팅에서만 lift — terminal RL 금지는 유지  
3. **hacking 검출**: gate↑/hold-out↓ 서명을 요인으로 노출 (B=low에서 특히)  
4. **가져오지 못하는 것**: B1 FAIL인 현 합성팩만으로는 high-truth 셀 불가 → PR-1/CL-C 없이 B=high는 **블로커**

### 3.3 Leakage·평가 계약

- `L-FIRM`: active가 동일 firm 재질의 금지; 스플릿은 도면/firm 단위  
- IR freeze + 캐시 해시 기록  
- val 개발 / test 방법당 단발 / 셔플 대조군 의무 / 증거 xlsx  
- 합격선 평가 전 봉인  
- metamorphic(CL-D)은 공용 심판으로 confirmation에 병행 가능하나, P4 1차 반응은 R-SYN/R-SILVER F1

### 3.4 탐지기 v1·fast_score 역할

4채널 가중합(parallel 0.35 / thickness 0.25 / junction 0.20 / layer 0.20)과 `fast_score`는:

- A1/A3의 **특징 생성기** (이미 HGB 파이프와 동형)  
- A2의 **환경 스코어러** (롤아웃 중 저비용 재점수)  
- RL 보상 자체로 쓰지 않음(보상은 R-META+R-SYN; 탐지기 점수는 상태 특징)

layer 채널: 탐지기는 name-blind와 동일(레이어명 신호 0)이므로 CubiCasa 레이어 중립 변환과 정합. Silver 쪽 name-prior는 B=low 노이즈 구조의 일부로만 취급.

---

## 4. 데이터·컴퓨트 요구

### 4.1 선결 게이트 (실행 예산 소진 전)

| ID | 내용 | P4 영향 |
|----|------|---------|
| PR-1 / CL-C / T2 | 벽 합성 생성기 + 충실도 (현재 B1 KS 0.5792, TV 0.265 FAIL) | B=high 셀 자격 |
| T26 | verifier false-accept ≤ 0.01 선계측 | RLVR 사활 |
| T6 | per-handle vs 집합-조립 산출물 격리 | 평가 단위 오염 방지 |
| PR-3 / T5 | CubiCasa/FloorPlanCAD NC counsel | 외부셋 학습 arm |
| CL-H cheapest | 학습 0 greedy vs beam 보상지형 | RL 훈련 전 kill 가능 |

### 4.2 로컬 실행 계획 (RTX 5070 Ti 16GB · RAM 64GB · DGX unreachable)

**1차 (며칠, C07 핵심부터)** — `cheapest_probe`:

- {supervised, active} × {scarce, abundant} = **4셀**  
- RLVR 제외  
- CubiCasa val만; HGB + 단순 불확실성 샘플링  
- CPU/RAM 주력, GPU 불필요에 가깝음  
- 질문: scarce에서 active의 라벨당 F1이 supervised 랜덤/층화 샘플을 올리는가?

**2차 (로컬)**  

- supervised 전 예산·seed 반복 (≥3; 준결정)  
- active seed ≥5 (확률 반응)  
- hacking 프로브는 RLVR 도입 시점에 붙임  

**3차 (DGX 복구 후)**  

- RLVR rollout·다 seed  
- vLLM 호스트와 시분할 야간 배치  
- Ornith-35B는 승인됐으나 **현재 unreachable** — 계획만 분리, 의존하지 않음  

### 4.3 자산 매핑

| 자산 | 사용 |
|------|------|
| CubiCasa SEG-IR | 주 라벨·스플릿 |
| qwen2.5-VL-3B SFT/GRPO 로컬 | A2 정책 백본 후보(래스터/도구 라우팅); 벡터 전용 셀과 혼동 금지 |
| FloorPlanCAD | counsel 후 보조; 본 요인 Y는 벡터 F1 |
| Zenodo10K/Text2CAD/ArchCAD/pseudo-12k | P4 비본선 (범위 밖 확장) |
| 프런티어 VLM API | 미승인 → silver 재생·배심 호출 금지 |

### 4.4 비용 청구서 (정직)

완전요인 12셀 + 2 프로브는 RLVR/active 반복 때문에 **비싸다**. 그래서 경로를 강제한다:

1. cheapest 4셀 → 신호 없으면 RLVR 예산 소진 금지  
2. A×C null ∧ RL계 ≤ supervised → **프로그램 하차** (패킷 kill)  
3. confirmation은 scarce 승자만 새 hold-out firm에서 1회 (`PASS_WITH_DEFERRAL`)

---

## 5. 구현 계획

### 5.1 모듈·파일 골격 (신규 허용 범위는 실행 시 별도 패킷; 여기선 설계만)

```
wsd_rl_seat/                    # CL-H / doe_P4
  prereg/
    p4_factorial.yaml           # A,B,C 수준·밴드·Lenth·seed
    kill_rules.json
  data/
    split_firm.py               # L-FIRM
    budget_sampler.py           # scarce/abundant
  paradigms/
    supervised_fit.py           # → cubicasa_ml / HGB
    active_policy.py
    rlvr_env.py                 # R-META + R-SYN reward
    hacking_probe.py            # gate-only vs gate+holdout
  eval/
    holdout_f1.py               # fast_score 연동
    cost_per_band.py
    effects_table.py            # A,B,C,A×C,A×B
  runners/
    cheapest_probe_2x2.py
    full_factorial_12.py
    confirmation_run.py
  evidence/
    p4_cells.xlsx               # 의무
```

### 5.2 기존 도구 접속점

| 기존 | 접속 |
|------|------|
| `cubicasa_ir` | SEG-IR 로드, 레이어 중립 가정 유지, train/val/test 경계 |
| `cubicasa_ml` | HGB 6특징 파이프 재사용; F1 0.517을 supervised abundant 앵커로 |
| `evidence_grid` / 탐지기 특징 | parallel/thickness/junction/… 특징 추출 |
| `fast_score` | 롤아웃·hold-out 고속 F1; NumPy 동치 채점 |
| metamorphic (CL-D) | confirmation 병행 심판(센티널·recall floor T7 반영 후) |

### 5.3 개발 규모 추정

| 단계 | 공수(대략) | 산출 |
|------|------------|------|
| prereg YAML + xlsx 스키마 | 0.5일 | 봉인 가능 산출물 |
| cheapest 2×2 runner | 1–2일 | C07 최소 실험 |
| active 정책 + L-FIRM | 2일 | A3 |
| RLVR env + hacking probe | 3–5일 | A2; DGX 대기 가능 |
| effects_table + Lenth | 1일 | 판정 자동화 |
| confirmation harness | 1일 | PASS_WITH_DEFERRAL |

총: 로컬 신호까지 **약 1주**, RLVR 포함 풀팩터는 DGX·verifier 게이트 후 **추가 1–2주**.

### 5.4 실행 순서 (tweak-likelihood)

1. T26 verifier FA 계측 + greedy vs beam (학습 0) — 여기서 죽으면 구현 대부분 폐기  
2. cheapest 2×2 (supervised×active × budget)  
3. B=low only로 A×B 예비 신호 (합성 없이도 가능)  
4. PR-1 통과 후 B=high 셀 채움  
5. RLVR 12셀·프로브  
6. confirmation  

---

## 6. 실험 셀 정의

### 6.0 공통 규칙

- 지표: hold-out F1 (`R-SYN`/`R-SILVER` 공통 밴드) + (active) 라벨당 비용  
- val 튜닝 / test 단발  
- 셔플 대조군: supervised·특징 파이프에 의무 (앵커 AUC 0.375 PASS 패턴)  
- 증거: 셀당 xlsx 행 (seed, IR hash, paradigm, B, C, F1, gate, cost, hacking_flag)  
- **제안 합격선(프리레그 초안, 평가 전 봉인 대상)**  
  - scarce에서 승자 paradigm의 val F1 ≥ supervised_scarce + 0.03 **또는** 라벨당 비용 ≤ 0.85×supervised  
  - abundant에서 supervised가 RL계 대비 비열등 (ΔF1 ≥ −0.01)  
  - hacking: RH 서명 0건이어야 “진성 우위” 주장 가능  

### 6.1 Cheapest probe (4셀) — 최우선

| Cell | A | C | 가설 | 합격선 | 킬 | 예산 | 시드 |
|------|---|---|------|--------|-----|------|------|
| CP1 | supervised | scarce | C07: 희소에서도 supervised가 안정 | 기준선 확정 | — | 로컬 0.5–1일 | 3 |
| CP2 | supervised | abundant | HGB≈0.517 재현 밴드 | val F1 ∈ [0.49,0.54] 재현(앵커 근처; 봉인 시 확정) | 재현 실패 시 파이프 버그 | 1일 | 3 |
| CP3 | active | scarce | **표적**: 라벨당 F1 > CP1 | ΔF1≥+0.03 또는 비용↓ | 둘 다 실패 → C07 맥락판 유지 쪽 신호 | 1–2일 | ≥5 |
| CP4 | active | abundant | supervised와 비슷하거나 열위 | abundant에서 active 필수 lift 없음이 정상 | active가 비용만 늘리면 A3 abundant 비추천 | 1–2일 | ≥5 |

**Cheapest 킬**: CP3가 CP1을 못 이김 → 풀팩터 RLVR 투자 보류, C07 지지 쪽으로 기울임(아직 최종 판결 아님).

### 6.2 본실험 12셀 (A×B×C)

표기: S=supervised, R=RLVR, Ac=active; H=high T-SYN, L=low T-SILVER; sc=scarce, ab=abundant.

| Cell | A | B | C | 가설 | 지표 | 합격선 | 킬(셀/축) | 예산 | 시드 |
|------|---|---|---|------|------|--------|-----------|------|------|
| 01 | S | H | sc | clean truth·희소: S 안정 | F1 | 기준 | — | 로컬 | ≥3 |
| 02 | S | H | ab | clean·풍부: S 최고 후보 | F1 | ≥ 다른 A | — | 로컬 | ≥3 |
| 03 | S | L | sc | noisy: S 성능↓ but 분산↓ | F1 | 보고 | — | 로컬 | ≥3 |
| 04 | S | L | ab | noisy·풍부 | F1 | 보고 | — | 로컬 | ≥3 |
| 05 | R | H | sc | **가설**: scarce에서 R/Ac ≥ S | F1,gate | scarce 승자 후보 | hacking이면 무효 | DGX | ≥5 |
| 06 | R | H | ab | C07: S ≥ R | F1 | R이 ab에서 S 미상회가 정상 | R만 이기고 Ac/S 전부 패면 이상 징후 | DGX | ≥5 |
| 07 | R | L | sc | **hacking 위험 구간** | F1,gate | hold-out 유지 | gate↑ F1↓ → C08 | DGX | ≥5 |
| 08 | R | L | ab | 동 | F1,gate | 동 | 동 | DGX | ≥5 |
| 09 | Ac | H | sc | **표적 A×C**: scarce Ac 승 | F1,cost | CP3 강화 | Ac 전 예산 패배 | 로컬→DGX | ≥5 |
| 10 | Ac | H | ab | S와 비슷 | F1,cost | lift 불요 | — | 로컬 | ≥5 |
| 11 | Ac | L | sc | noisy+active: 질의 오염 | F1,cost | 보고 | 순서 아티팩트면 seed 재분리 | 로컬 | ≥5 |
| 12 | Ac | L | ab | 동 | F1,cost | 보고 | 동 | 로컬 | ≥5 |

### 6.3 Reward-hacking 프로브 2셀

| Cell | 설정 | 가설 | 합격선 | 킬 |
|------|------|------|--------|-----|
| RH0 | RLVR + gate-only | hacking 유도 가능 | 서명 검출 가능해야 프로브 유효 | 서명 불가능한 보상 설계면 재설계 |
| RH1 | RLVR + gate+holdout 벌점 | 진성만 생존 | RH0 대비 hold-out 회복 | 벌점에도 hacking이면 verifier 수리 선행 |

### 6.4 사전봉인 판정 규칙 (effects_table)

슬롯: A(3수준 대비), B, C main, A×C, A×B. status=UNRUN.

| 결과 | 판결 |
|------|------|
| A×C 유효 (Lenth ME 초과) | C07 **맥락없는 판 반증**; 적용범위 재작성 |
| A×C null ∧ A_main(R,Ac)≤0 | C07 **지지**; RL 계열 하차 |
| R이 L에서 gate↑ & hold-out↓ | reward-hacking 확정; 가짜 승리 폐기 |
| high-truth에서 A 무차별 | “정답원 좋으면 방법 무관” 보고 (null도 승리) |

### 6.5 Confirmation run

- 대상: scarce에서 이긴 paradigm (가설상 Ac 또는 R)  
- 새 hold-out firm / 미접촉 분할  
- hacking 재점검  
- status: **`PASS_WITH_DEFERRAL`** — 미확인 우위를 PASS로 부르지 않음  

### 6.6 프로그램급 kill_condition (패킷 원문 승계)

1. A×C null **그리고** RLVR/active가 어느 예산에서도 supervised를 못 이김 → C07 지지, RL 프로그램 하차  
2. RLVR가 “이겼는데” 전부 hacking 서명 → 가짜 승리, verifier 수리 선행 (훈련 재개 금지)

---

## 7. red team 티켓 응답

CL-H 및 doe P4에 직접 걸린 OPEN 티켓을 지목한다. (패널: T1–T7 수렴급, T8–T33 per-proposal, T34 프로그램급.)

| 티켓 | 요지 | 이 제안의 응답 |
|------|------|----------------|
| **T26** | verifier false-accept ≤0.01 선계측 — RL 사활 | **수용·하드 게이트**. 미계측 시 A2 셀 실행 금지. FA>0.01이면 RLVR arm 중단. |
| **T6 / 공격 E** | 평가 단위 혼동(per-handle vs 집합-조립) | **수용**. Y는 per-handle F1만. 집합-조립은 platt P4 산출물로 격리; doe P4 반응에 섞지 않음. |
| **T1 / 공격 A** | 4대리 독립성 (sev 0.75) | **부분 수용·의존**. B축이 독립성 실패를 증폭할 수 있음 → CL-E/PR-2 교차 불일치 구조를 P4 해석의 공변량으로 병기. 독립성 FAIL이면 A×B를 “verifier 효과”로 과대해석하지 않음. |
| **T2 / 공격 B** | 벽 합성 생성기 부재 (B1 FAIL) | **수용·블로커**. B=high 셀은 PR-1/CL-C 전까지 `BLOCKED`. cheapest 4셀은 CubiCasa 사람라벨로 진행 가능. |
| **T5 / PR-3** | NC 라벨·원 도면 권리 | **수용**. CubiCasa 학습 arm은 counsel 전 “내부 연구 프로토콜” 범위로만; 외부 공개·재배포 가정 금지. FloorPlanCAD 학습 보류. |
| **T7 / 공격 F** | 0벽/전벽 sentinel + recall floor | **수용**. confirmation·metamorphic 병행 시 T7 미탑재 밴드로 “0벽 정책” 통과를 승으로 치지 않음. |
| **T15** | seed-confound (doe P1 교훈) | **수용**. RLVR/active ≥5 seed; supervised ≥3; seed를 요인과 confound하지 않음(런 순서 무작위화+기록). |
| **T10/T23** | Graph IR / silver 게이트 식별자 | **간접**. P4는 GNN 비의존. Silver 자격은 calibration 기준(B1∧B4)을 B=low 사용 조건으로 인용; B4 Pearson 실측 0.2911은 **미달** → silver를 “자격 통과 학습 타깃”으로 과장하지 않고 noisy proxy로만 사용. |
| **T34** | 인용 R-레인 experiment_executed:false | **수용**. C07·C04·C08·U02·CON02는 이 실험으로 재-status; 인용만으로 load-bearing 금지. |
| **학습0 beam 프로브** (CL-H 조건 ③) | greedy≈상한 → 훈련 전 RL kill | **수용·선행**. Doe P4 풀예산 전 platt cheapest와 동일 게이트. |

해소하지 않고 **위험으로 인정**하는 항목: T1 독립성 미해소 상태에서 B축 해석의 인과 강도; DGX unreachable로 A2 일정 리스크; E1.5 5기≈2가문으로 silver 분산 과소추정.

---

## 8. 인접 제안과의 관계

### 8.1 병합·차별

| 제안 | 관계 | 병합 지점 | 차별점 |
|------|------|-----------|--------|
| **platt P4** | 동일 CL-H | 학습0 greedy/beam; 집합-조립은 platt, 요인효과는 doe | platt=조립 정책 vs beam; doe=A×C 완전요인 |
| **calibration P6** | 동일 CL-H | bandit 우선, verifier FA 밴드 | calib=라우팅 유틸리티; doe=C07 반증/지지 판결 계약 |
| **feyerabend P4** | 동일 CL-H | C07 교리 독해 해체 | fey=counter-induction 서사; doe=측정 가능한 상호작용 |
| **doe P3 / CL-E** | 선후 | truth 교차·독립성 | P3=대리 행렬; P4=패러다임 행렬 |
| **doe P1 / CL-F** | Occam | supervised HGB가 먼저 | P1 마스터 스크린 PARKED; P4는 RL 자리만 |
| **CL-C / PR-1** | 하드 선결 | T-SYN | 생성기 없으면 B=high 불가 |
| **CL-D** | 공용 심판 | confirmation | P4 1차 Y는 F1 |
| **CL-K** | silver 철학 | anti-silver 통제와 B=low 정합 | P4는 silver를 보상에 안 씀 |

### 8.2 Abstentions (패킷 승계)

1. **Terminal** 벽/비벽 고정라벨에 RL — 이 설계도 지지하지 않음. C07의 좁은 판은 옳을 것으로 예상. P4는 적용범위 분할: 오용(terminal) vs 정당(active·tool-routing·RLVR-with-sound-verifier).  
2. Verifier 절대 건전성 — U02 별도 lane; 여기서는 B 대리만.  
3. bounded-RSI 안전성(R26 C11) — 범위 밖.

### 8.3 이 제안이 죽어야 하는 조건 (정직)

다음 중 하나면 **doe_P4 / CL-H RL 훈련 레인을 닫는다**:

1. 학습 0에서 greedy≈beam≈상한 (탐색 구조 자명)  
2. cheapest 2×2에서 active가 scarce 라벨당 F1을 못 올림 **그리고** 이후 A×C null  
3. A×C null ∧ 전 예산에서 S ≥ R,Ac  
4. RLVR “승리”가 전부 hacking 서명  
5. T26 FA>0.01이 수리 불가  
6. PR-3 거절로 외부라벨 학습이 불법·불가 — 대체 truth 없이 요인 C를 정의 못할 때  

죽을 때 남겨야 할 산출물: effects_table(UNRUN→RUN), hacking 로그, “C07 좁은 판 지지/맥락판 반증” 한 줄 판결, xlsx.

### 8.4 성공 시에도 올리지 않는 말

- “RL이 벽 탐지기를 이겼다” (terminal 분류와 혼동 금지)  
- “C07이 틀렸다” (맥락없는 판만 반증 가능; 좁은 판은 별개)  
- confirmation 전 PASS  

---

## 부록 A — Verification design 5요소 (패킷 요약)

| 요소 | 내용 |
|------|------|
| truth | T-SYN / T-SILVER + 보상 T-META |
| leakage | L-FIRM; IR freeze; test 단발 |
| prereg | A×C 판정 + hacking 서명 |
| kill | §6.6 |
| cheapest_probe | {S,Ac}×{sc,ab} 4셀 |

## 부록 B — 다이제스트 수치 인용 목록 (이 파일에서 사용한 것만)

- 합성 B1 FAIL: KS 0.5792, TV 0.265; 엔티티 혼재 SPLINE/ARC/HATCH vs LINE/LWPOLYLINE/INSERT  
- B2: S 1.0/1.0(음성 0); F P 0.9315; M P 0.8669; R=1.0  
- B4: 강체·단위 1.0; scale 0.7624 FAIL  
- 실도면: B3 0.682→0.2135; B5 Pearson 0.2911; full-vs-nb 1.0; max def 412k 선분  
- CubiCasa: 5000, train/val/test 4200/400/400; 벽율 ~11.8%; 탐지기 F1 0.2358; HGB F1 0.517 AUC 0.9215; shuffle AUC 0.375; 로지스틱 F1 0.053  
- 하드웨어: 5070 Ti 16GB, RAM 64GB, DGX unreachable  

문헌·일반 지식 수치는 본문에 ‘요검증’ 또는 ‘초안 봉인 대상’으로 분리했다.

---

DOSSIER_COMPLETE: doe_P4
