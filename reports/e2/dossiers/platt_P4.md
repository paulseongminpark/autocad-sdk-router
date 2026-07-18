# platt_P4 — RLVR 벽-집합 조립 정책 방법론 도시예

## 판정 목표와 범위

이 제안의 목적은 “RL이 벽 탐지에 유용하다”를 전제하는 것이 아니라, **어떤 문제 정식화에서 RL이 정당화되는지를 가장 강한 비-RL 대조군과 동률 컴퓨트로 판정**하는 것이다. R26 C07은 원문 실험이 실행되지 않은 `NEEDS_WEB_VERIFY` 주장이고, 이 문서도 C07을 교리나 선행 사실로 사용하지 않는다. 특히 다음 네 문제를 분리한다.

1. 엔티티별 고정 라벨 `wall_member(h)`: 같은 입력 신호로 교차엔트로피 supervised 분류기를 항상 만들 수 있으므로 full RL의 자리가 아니다. RL arm은 음성 대조군이다.
2. pair→chain→network 집합 조립: 서로 충돌하거나 보완하는 후보를 순차 선택하고, 최종 집합에만 계산 가능한 비미분 검증 보상을 받는다. P4에서 RLVR 자격을 심사할 유일한 본선이다.
3. 비싼 판정/렌더의 획득 순서: 각 라운드의 효과가 사실상 한 번의 선택에 귀속되므로 contextual bandit으로 격리한다. 이것을 장기-horizon RL의 성과로 보고하지 않는다.
4. self-training: pseudo-label 갱신은 EM/자기증류 절차로 명명하고 P2의 훈련 옵션으로 돌린다. P4 성과에 합산하지 않는다.

본선 생존 규칙은 패킷의 프리레그 초안을 그대로 구체화한다. 동일한 동결 인코더·동결 보상·월클록 상한에서 RL 정책의 synthetic held-out per-handle F1이 beam보다 **0.05 이상** 높고, 숨긴 metamorphic 변환의 위반율이 beam보다 높지 않아야 한다. 두 조건을 모두 만족하면 HR1이 생존하며 “C07이 이 집합-조립 과업에도 적용된다”는 해석을 기각한다. 하나라도 미달하면 HR1의 RL 레인을 종료한다. 정책 보상 상승과 synthetic held-out F1 하락이 갈라지는 보상해킹 시그니처는 밴드 계산을 기다리지 않는 즉시 킬이다.

현재 실측상 합성팩은 B1 충실도에서 실패했다(KS 0.5792, TV 0.265). 더구나 패널이 확인한 기존 `synthetic_truth.py`에는 벽 생성 코드가 없다. 따라서 PR-1을 통과한 벽 합성 생성기와 WSD-EVAL-v1이 없으면 P4 본선 결과를 만들지 않는다. 이는 HR1의 과학적 패배가 아니라 **실험 자격 미충족**으로 기록한다.

## 1. 이론적 근거·선행연구

### 1.1 RLVR가 성립하는 최소 조건

REINFORCE(Williams, 1992)와 policy-gradient 계열은 최종 산출물에 대한 보상이 미분 불가능해도 표본 궤적의 로그확률 기울기로 정책을 갱신할 수 있다. PPO(Schulman 등, 2017)는 중요도 비율을 clipping하여 큰 정책 갱신을 제한한다. 최근 “reinforcement learning with verifiable rewards” 계열은 사람이 학습한 선호 보상 대신 정답 검사기, 실행 결과, 수학 답 검증기처럼 자동 판정 가능한 신호를 이용한다. DeepSeekMath의 GRPO와 DeepSeek-R1은 이 계보의 관련 시스템이지만, 정확한 서지·버전과 “RLVR” 명칭의 원출처는 이 문서에서 웹 검증하지 않았으므로 **요검증**으로 둔다. 이 문서의 알고리즘은 그 명칭의 권위가 아니라 다음 세 조건에만 의존한다.

- verifier가 학습 정책과 독립적으로 동결되어야 한다.
- 틀린 집합을 맞다고 받는 false-accept가 사전 게이트 이하이어야 한다.
- 보상이 개별 핸들의 독립 점수 합으로 완전히 분해되지 않고, 선택 간 충돌·연결·종료 결정이 최종 집합의 질을 바꾸어야 한다.

세 번째 조건이 없으면 RL은 불필요하다. 고정 특징 (x_h)에서 이진 라벨 (y_h)를 예측하는 문제는 BCE, calibrated boosting, CRF/structured loss 등 직접적인 supervised 목적함수를 가진다. 다이제스트의 HistGradientBoosting은 6개 특징으로 val F1 0.517을 얻어, 기하 탐지기 전이 F1 0.2358보다 이미 강한 비-RL 기준선을 제공한다. 이 수치는 RL의 가능성을 증명하지 않고 오히려 **단순 분류를 먼저 소진해야 한다**는 근거다.

### 1.2 조합최적화·구조예측 계보

집합 조립은 pointer network(Vinyals 등, 2015), neural combinatorial optimization(Bello 등, 2017), attention 기반 routing(Kool 등, 2019), learning-to-search/DAgger(Ross 등, 2011), structured prediction의 계보와 맞닿는다. Deep Sets(Zaheer 등, 2017)와 Set Transformer(Lee 등, 2019)는 순서가 없는 후보 집합을 표현하는 데 적합하다. 이 문헌은 RL이 언제나 우월하다고 말하지 않는다. 오히려 목적함수가 명시적이고 탐색 공간이 감당 가능하면 beam, branch-and-bound, ILP/CP-SAT가 더 직접적이며 최적성 gap까지 줄 수 있다.

P4에서 RL이 가질 수 있는 유일한 이점은 반복 도면에 대한 **탐색의 amortization**이다. verifier를 매 도면마다 넓게 호출하는 beam/ILP 대신, 정책이 여러 훈련 문제에서 좋은 조립 순서를 학습하여 적은 호출로 높은 보상 영역에 도달할 수 있다. 반대로 verifier가 거의 가산적이거나 greedy가 상한에 붙는다면 amortization할 탐색 난도가 없다. 이 때문에 학습 0의 reward-landscape probe가 본선보다 앞선다.

### 1.3 metamorphic testing과 보상해킹

Metamorphic testing(Chen 계열의 초기 연구; 정확한 초기 서지는 **요검증**)은 정답 라벨이 없는 입력에서도 변환 전후 출력이 만족해야 할 관계를 시험한다. 벽 탐지에서는 강체변환·단위변환·스케일·explode·레이어 개명에 대한 equivariance/invariance를 정의할 수 있다. 그러나 위반율만 최소화하면 항상 빈 집합을 내는 정책이 완벽해진다. 패널의 T7에 따라 P3에서 검증·동결된 0벽/전벽 sentinel과 recall 최저선을 함께 적용하지 않은 metamorphic 점수는 보상으로 사용할 수 없다.

보상해킹은 Goodhart류 문제와 specification gaming의 구체 사례다. Amodei 등(2016)의 “Concrete Problems in AI Safety”와 AI Safety Gridworlds(Leike 등, 2017)는 대리 목적 최적화가 의도와 갈라질 수 있음을 체계화했다. P4는 이를 추상 경고로만 두지 않고, reward 상승과 독립 synthetic F1 하락의 시계열 괴리를 즉시 중단 조건으로 만든다.

### 1.4 C07에 대한 증거 규칙

C07 자체는 draft 레인의 `NEEDS_WEB_VERIFY`이고, 그 인용 레인도 `experiment_executed:false`이므로 이중으로 교리 자격이 없다. P4는 C07의 보편 명제를 검증하지 않는다. 고정 라벨 셀과 집합 조립 셀을 같은 하네스에서 분리하여 **E2 과업에 대한 적용 범위**만 판정한다. 고정 라벨에서 supervised가 우세하고 조립에서도 beam이 우세하면 C07의 E2 적용을 잠정 유지한다. 조립에서만 RLVR이 프리레그 밴드를 넘으면 C07을 엔티티 분류에는 유지하되 집합 조립에는 기각한다.

## 2. 알고리즘 정확 스펙

### 2.1 입력, 상태, 행동, 출력

도면 정의 (d)의 정규화된 SEG-IR을 (G_d=(H,E,X))라 한다. (H)는 원본 핸들, (X_h)는 P2와 동일 checkpoint의 동결 임베딩 및 동결 unary score, (E)는 공간 근접·평행·교차·끝점 접속·공유 후보 관계다. P4는 원시 (O(|H|^2)) 쌍을 만들지 않는다. 공간 인덱스와 동결된 후보 규칙으로 다음을 만든다.

- (Q={q_j}): 하나 이상의 핸들로 구성된 벽 pair/primitive 후보
- (Lsubseteq Q\times Q): 끝점 연속, 교차, 평행 보완, 방/경계 연계 등의 chain link 후보
- (Csubseteq Q\times Q): 동일 핸들 중복, 기하 상충, 상호배타 설명을 나타내는 conflict

환경 상태는 (s_t=(S_t,L_t,F_t,U_t))다. (S_t\subseteq Q)는 선택 후보, (L_t\subseteq L)은 채택한 연결, (F_t)는 확장 가능한 frontier, (U_t)는 아직 결정하지 않은 국소 후보다. 행동은 마스크된 다음 집합이다.

- `START(q)`: 새 component를 시작한다.
- `EXTEND(k,q,l)`: component (k)에 후보 (q)와 link (l)을 붙인다.
- `MERGE(k1,k2,l)`: 두 component를 연결한다.
- `PRUNE(q)`: 이미 선택한 국소 후보를 제거한다. 한 후보당 한 번만 허용하여 순환을 막는다.
- `CLOSE(k)`: component를 닫는다.
- `STOP`: 전체 조립을 종료한다.

충돌 후보의 동시 선택, 이미 처리된 link 재사용, 동결 step cap 초과 행동은 mask한다. 서로 다른 행동 순서가 같은 집합을 만드는 중복을 줄이기 위해 상태의 component와 handle ID를 canonical sort하고, 최종 보상은 행동 순서가 아닌 canonical set에만 준다. 출력은 두 갈래로 버전 분리한다.

1. 공용 평가 출력: 모든 원본 핸들에 대한 `wall_member(h)∈{0,1}`과 score
2. P4 전용 구조 출력: 선택된 (Q), chain/component ID, link, action trace

따라서 집합 조립을 연구하면서도 프로그램 공용 per-handle 시험지와 평가 단위를 바꾸지 않는다.

### 2.2 동결 verifier와 보상

Synthetic train에서 생성기는 원본 핸들 truth (Y_d), pair truth (P_d), link/component truth (K_d)를 낸다. 보상 코드와 아래 가중치·threshold는 학습 전에 설정 파일과 함께 SHA-256으로 봉인한다. 가중치 선택은 PR-1/PR-2/T26 감사 구간에서 끝내며 RL run을 본 뒤 바꾸지 않는다.

Synthetic terminal score의 기본형은 다음이다.

\[
V_{syn}(A_d,Y_d)=
w_h F1_h(A_d,Y_d)+
w_p F1_{pair}(A_d,P_d)+
w_k F1_{link}(A_d,K_d)-
w_c\,ConflictRate(A_d)-
w_b\,BudgetOverrun(A_d).
\]

(F1_h)가 공용 1차 지표다. pair/link truth가 PR-1에서 신뢰 가능하게 생성되지 않으면 해당 항을 0으로 “간주”하지 않고 verifier 자격 실패로 처리한다. 모든 항은 ([0,1]) 또는 봉인된 동일 범위로 정규화한다. 정책이 다수 핸들 도면에서 긴 episode만 선호하지 않도록 도면별 score를 먼저 계산한 뒤 평균한다.

라벨 없는 실도면의 metamorphic 위반은 변환 τ에 대해 다음처럼 계산한다.

\[
v_{\tau}(d)=
\frac{|f(\tau d)\triangle \tau f(d)|}
{|f(\tau d)\cup \tau f(d)|+\epsilon}.
\]

빈 집합 회피를 위해 P3에서 별도 검증된 sentinel/recall floor를 어기면 (v_{\tau}(d)=1)로 강제한다. 그 floor의 값을 P4에서 새로 고르지 않는다. transformation train family와 hidden eval family를 분리하고, 원도면 ID 단위로도 격리한다. 실코퍼스 보상은 (V_{meta}=1-mean(v_\tau))로 정의하되, T1 독립성 감사가 두 proxy의 결합을 허용하기 전에는 (V_{syn})과 하나의 숫자로 섞지 않고 **별도 batch·별도 로그**로 최적화한다.

E1.5 silver는 reward 함수, policy observation, replay buffer, early stopping, hyperparameter 선택에 절대 들어가지 않는다. 학습 프로세스에는 silver 파일 경로를 전달하지 않고, 발견하면 hard error로 종료한다. Silver는 모든 선택을 봉인한 뒤 held-out 일치 표를 만드는 데만 쓰며, 5개 판정자를 독립 5표가 아니라 약 2개 어휘 가문으로 층화 보고한다.

### 2.3 정책과 학습 목적

동결 P2 임베딩 위에 작은 set/graph policy head를 둔다. 각 state에서 후보 임베딩, component pooled embedding, conflict/link feature, 남은 budget을 attention으로 결합해 πθ(a|s,d)를 낸다. critic 메모리를 피하기 위해 group-relative policy-gradient를 기본으로 한다. 한 도면에서 (G)개 궤적을 표본화하고,

\[
A_g=\frac{R_g-mean(R_{1:G})}{std(R_{1:G})+\epsilon}
\]

로 advantage를 만든다. 이전 정책 πold와의 비율 (r_t(θ))에 PPO-style clip을 적용하고 supervised reference πref와의 KL을 더한다.

\[
L_{RL}=-E\left[\min(r_tA_g,clip(r_t,1-\eta,1+\eta)A_g)\right]
+\beta KL(\pi_\theta||\pi_{ref})-\alpha H(\pi_\theta).
\]

초기 πref는 synthetic truth에서 oracle canonical action trace를 모방한 정책이다.

\[
L_{IL}=-\sum_t\log\pi_{ref}(a_t^*|s_t^*,d).
\]

모든 본선 arm이 이 checkpoint에서 시작한다. `supervised+greedy`는 그대로 greedy decode, `beam`은 같은 logits와 같은 verifier로 탐색, RLVR은 (L_{RL})로 추가 학습 후 greedy decode한다. 이 공유 prefix로 약한 supervised baseline이 RL 승리를 만드는 것을 막는다.

설계 단계의 하이퍼파라미터 공간은 다음으로 제한한다. 이는 관측값이 아니라 **사전 탐색 범위**다.

- group rollout (G\in\{4,8\}), clip η∈{0.1, 0.2}
- learning rate (10^{-5}\)~(3\times10^{-4}), KL β∈{0, (10^{-3}), (10^{-2})}
- entropy α∈{0, (10^{-3}), (10^{-2})}
- beam width (B\in\{1,4,16,64\}); (B=1)은 greedy
- frontier top-k와 최대 step은 후보 수의 함수로 정하고 verifier freeze manifest에 기록
- reward weight는 T26 통과 전 소규모 verifier audit에서만 고르고 이후 탐색 금지

Step cap에 닿은 episode는 자동 연장하지 않고 현재 집합으로 채점하며 cap-hit rate를 실패 지표로 남긴다.

### 2.4 강한 탐색 대조군

Beam은 cumulative policy logit만 보지 않고, 완성 집합에는 RL과 같은 동결 verifier를 호출한다. 부분 상태에는 admissible bound가 있을 때만 그 bound를 쓰고, 없으면 길이 정규화된 reference-policy score로 정렬하되 최종 순위는 verifier로 결정한다. Beam width별 reward/F1/호출 수/월클록 곡선을 전부 보존한다.

ILP/CP-SAT는 verifier 중 unary·pairwise·conflict로 분해 가능한 항을 이진 변수 (z_q,z_l)로 옮긴 보조 통제다. 비분해 metamorphic 항은 ILP 목적에 억지로 넣지 않는다. tractable stratum에서는 optimum 또는 solver bound를, 큰 도면에서는 timeout 당시 incumbent와 gap을 기록한다. ILP가 RL을 이기면 그것은 구현상의 불편이 아니라 P4의 정당한 kill 증거다.

### 2.5 실행 의사코드

```text
PREREQUISITES:
  require PR-1 fidelity-qualified wall generator and frozen WSD-EVAL-v1
  require PR-2 proxy-independence audit
  require P3 sentinel + recall-floor validation
  require verifier false_accept_rate <= 0.01
  freeze reward code/config SHA, generator SHA, split IDs, encoder SHA

BUILD(d):
  ir <- normalize_with_cubicasa_ir_or_real_dwg_adapter(d)
  unary <- frozen_P2_encoder(ir)
  Q, L, C <- deterministic_candidate_builder(ir, unary)
  return AssemblyInstance(ir, unary, Q, L, C)

ZERO_LEARNING_PROBE(instances):
  for d in instances:
    run random, greedy, beam widths, and tractable ILP under one ledger
  if greedy ~= best_beam ~= certified/empirical upper bound:
    kill RL before training

TRAIN_RL(train_instances):
  pi_ref <- frozen supervised imitation checkpoint shared by all arms
  pi <- copy(pi_ref)
  repeat until preregistered wallclock/step cap:
    sample drawings
    sample G masked assembly trajectories per drawing
    R <- frozen synthetic verifier OR separated metamorphic batch score
    update pi with clipped group-relative objective + KL(pi, pi_ref)
    audit reward/F1 divergence; stop immediately on hacking signature
  return frozen pi

EVALUATE(pi, beam, supervised_greedy):
  compute per-handle synthetic held-out F1 and hidden metamorphic violations
  report pair/chain/network metrics separately
  apply exact survival band against equal-compute beam
  only after survival: one-shot CubiCasa test and held-out silver agreement
```

## 3. 벽 과업 적응 설계

### 3.1 CubiCasa5k SEG-IR 벡터축

CubiCasa5k는 전량 SEG-IR 변환에 성공했고, 분할은 train 4,200/val 400/test 400, 선분은 각각 약 386만/35.4만/37.5만이며 벽 선분율은 약 11.8%다. P4는 이 축에서 다음 계약을 지킨다.

- P2가 선택한 encoder checkpoint와 6특징 adapter를 그대로 동결한다. P4가 CubiCasa 라벨로 encoder를 다시 맞추지 않는다.
- `Wall` 요소의 모서리 truth는 per-handle **평가**와 supervised reference trace 생성에만 사용한다. P4 RL reward의 truth source는 PR-1 synthetic과 metamorphic으로 제한한다.
- val은 후보 규칙·정책 하이퍼파라미터·프리레그 봉인에만 사용하고 test는 생존 판정 뒤 방법당 한 번만 연다.
- split은 도면 단위이며 한 원도면에서 파생한 변환, candidate cache, trace가 다른 split으로 넘어가지 않는다.

기하 탐지기의 높은 재현율과 낮은 정밀도(P 0.134, R 0.981, F1 0.2358)는 후보를 넓게 만들 수는 있으나 FP가 구조적으로 어렵다는 뜻이다. Direction, BoundaryPolygon, Door, Window, DimensionMark처럼 길고 평행한 교란은 unary 두께/평행성만으로 사라지지 않는다. GBDT의 P 0.860/R 0.370/F1 0.517은 반대로 개별 선분 정밀도를 크게 올렸지만 많은 벽을 놓친다. P4가 추가로 노리는 것은 새 로컬 특징이 아니라 다음의 **상호의존 회수**다.

- 단독으로 약한 후보도 이미 선택된 wall chain을 연장하면 채택한다.
- 문/창 교란이 국소적으로 벽과 비슷해도 네트워크 연결과 conflict에서 배제한다.
- 여러 pair가 한 핸들을 경쟁할 때 전체 component 보상으로 하나를 고른다.
- 정밀도 높은 GBDT seed를 중심으로 낮은 unary score의 연결 후보를 제한적으로 복구한다.

이 상호작용이 실제로 beam보다 어려운지는 가정하지 않는다. zero-learning probe와 ILP가 먼저 답한다.

### 3.2 1.dwg 실도면축

1.dwg의 384개 도면 정의는 라벨 없는 metamorphic reward/eval 축이다. 정의 ID를 train-reward pool과 hidden-eval pool로 먼저 봉인하고, 한 정의의 원본과 모든 변환을 같은 쪽에 둔다. 기존 `fast_score`의 후보 점수와 P2 임베딩을 읽되, P4가 이를 truth로 취급하지는 않는다. 최대 정의가 412,775 선분이므로 다음 확장성 안전장치를 둔다.

- R-tree/격자 공간 인덱스로 relation proposal을 국소화한다.
- tile 경계 후보는 overlap halo에서 중복 생성한 뒤 handle ID로 합친다.
- frontier top-k pruning 전후에 deterministic candidate recall ceiling을 별도 보고한다.
- 메모리와 action 수가 cap을 넘으면 도면을 조용히 제외하지 않고 `RESOURCE_CAP` 실패 행으로 evidence xlsx에 남긴다.

다이제스트에서 벽-제로 도면율은 v0의 0.682에서 0.2135로 개선되었지만, 이것은 P4의 정답 라벨이 아니다. 기존 metamorphic은 강체·단위에서 1.0이었으나 scale 팔이 0.7624이고 strict sentinel 조문상 FAIL이므로, scale·explode·레이어 개명 hidden family를 특히 분리한다. 실제 보상은 P3의 0벽/전벽 sentinel과 recall floor가 검증된 뒤에만 활성화한다.

E1.5 silver와의 Pearson 0.2911, full-vs-name-blind 1.0은 참고할 독립성 단서지만 reward에는 쓰지 않는다. 최종 일치 보고에서도 5판정자를 5개 독립 관측처럼 평균하지 않고 2개 어휘 가문 층으로 제시한다.

### 3.3 FloorPlanCAD 래스터축

FloorPlanCAD는 5,308개 래스터와 wall bbox/segmask를 갖지만 벡터 SVG가 없으므로, 현재 상태에서 `wall_member(h)` 행동 공간에 정확히 접속할 수 없다. 이를 억지로 벡터 truth로 변환하면 P4가 아니라 새 vectorization 방법을 시험하게 된다. 따라서 본선 reward와 생존 밴드에서는 제외한다.

CL-G/T24의 pixel→handle 역투영 하네스가 synthetic에서 exact 검증되고 PR-3의 권리 검토가 끝난 경우에만, 선택 벽을 rasterize한 mask IoU와 실패 예시를 **비보상 보조 진단**으로 추가한다. 그 결과는 정책 선택, early stopping, C07 판정에 사용하지 않는다. 이 제한은 래스터 자산을 무시하는 것이 아니라 평가 단위 누출을 막는 조치다.

### 3.4 synthetic 축과 proxy 분리

PR-1 생성기는 LINE/LWPOLYLINE/INSERT만 반복해서는 안 된다. 현재 실도면에 관측된 SPLINE 3,973, ARC 2,198, HATCH 264의 혼재와 divergent-20의 POLYLINE/블록/비평행 조각을 fidelity gate의 대상으로 포함해야 한다. 생성기 train/eval은 seed만 다른 복제가 아니라 mutation family, block template, topology template를 분리한다. hidden family는 학습자가 접근할 수 없는 manifest에 둔다.

PR-2는 synthetic truth·CubiCasa 사람 라벨·metamorphic·silver가 같은 “평행 이중선” prior를 공유하는지 동일 definition 단위의 불일치 텐서로 감사한다. 상관 하나로 독립성을 선언하지 않고, source별 false-positive 교집합, 조건부 오류, name-blind 변화, 구조 유형별 불일치를 기록한다. proxy가 붕괴하면 여러 점수를 더해 “확증”이라 부르지 않으며, synthetic과 metamorphic을 별도 목적/별도 표로 유지한다.

## 4. 데이터·컴퓨트 요구

### 4.1 데이터 산출물과 봉인 단위

필수 입력은 다음이다.

- fidelity-qualified synthetic train/val/held-out와 per-handle·pair·link truth
- P3가 검증한 metamorphic transform 구현, sentinel, recall floor
- 동결 P2 encoder checkpoint와 candidate-feature schema
- CubiCasa 도면 단위 split manifest와 SEG-IR
- 1.dwg definition 단위 train/eval manifest
- verifier adversarial audit set: empty/all-wall, 중복 pair, 끊긴 chain, 긴 평행 distractor, 단위/scale 교란, 상충 후보

학습 전에 `reward_sha`, `generator_sha`, `encoder_sha`, `split_sha`, dependency lock, random seed 목록을 하나의 run manifest에 기록한다. Synthetic 생성기 eval split과 hidden metamorphic family는 정책 프로세스에서 읽기 불가능하게 분리한다. Silver adapter는 학습 dependency graph에서 제거한다.

### 4.2 로컬 실행 계획

RTX 5070 Ti 16GB와 RAM 64GB가 본선의 기준 환경이다. CPU worker는 immutable instance를 memory-map하여 rollout과 verifier 호출을 병렬화하고, GPU에는 동결 encoder의 캐시 또는 소형 policy head만 올린다. 전체 도면 임베딩을 한 번에 GPU에 싣지 않고 component/frontier mini-batch를 사용한다. Candidate graph와 action trace는 압축 sparse 형식으로 저장한다.

월클록 공정성은 공통 supervised checkpoint 생성 비용을 공유 prefix로 한 번 계상한 뒤, 각 arm의 **추가** 시간 상한을 동일하게 둔다. RL에는 update+rollout+최종 greedy decode, beam에는 width sweep+verifier 호출, ILP에는 solve+bound 계산을 모두 포함한다. `supervised+greedy`가 시간을 덜 쓰면 남은 시간을 억지 튜닝에 쓰지 않고 미사용량을 로그한다. 품질뿐 아니라 verifier 호출 수, CPU/GPU 시간, peak RAM/VRAM, 도면당 latency를 함께 보고해 amortization 손익을 드러낸다.

설계 예산은 관측 결과가 아니라 상한이다. 학습 0 probe는 로컬 CPU 기준 1일, 본선 각 arm/seed는 동일 24시간 cap, 3개 seed는 로컬 순차 실행을 기본으로 한다. cap 도달 시 연장하지 않고 프리레그 밴드로 판정한다. 실제 wallclock은 evidence xlsx에 기록한다.

### 4.3 DGX 계획과 부재 시 동작

DGX Spark/Ornith-35B는 현재 unreachable이므로 P4의 선결이나 본선 자원으로 두지 않는다. 로컬에서 한 seed만 끝난 상태로 결론을 내리지 않고, 3 seed를 순차 완료할 때까지 판정을 보류한다. DGX가 나중에 복구되면 동일 container·동일 SHA로 **3-seed ablation 재현**만 야간 슬롯에서 수행하며, DGX 결과로 로컬 프리레그나 reward를 다시 고르지 않는다. P4는 vision serving을 요구하지 않으므로 Ornith와 GPU 경합이 없다.

### 4.4 라이선스와 외부 결재

PR-3 counsel 서면 확인 전에는 CubiCasa/FloorPlanCAD를 이용한 새 학습 arm을 시작하지 않는다. 이미 허용된 범위가 불명확하면 synthetic과 권리 정리된 1.dwg 변환 probe만 준비하고 외부셋 셀은 `BLOCKED_LICENSE`로 둔다. 프런티어 VLM API와 DGX 승인 여부는 P4의 생존 조건이 아니다.

## 5. 구현 계획

아래는 구현 시 만들 파일 골격이며, 모듈명은 기존 저장소 레이아웃에 맞춰 조정한다.

```text
rlvr_wall/
  schema.py                 # AssemblyInstance/State/Action/Trace 계약
  candidate_builder.py      # cubicasa_ir, 실DWG adapter, 공간 인덱스
  assembly_env.py           # action mask, canonicalization, step cap
  frozen_verifier.py        # synthetic/meta 점수; silver import 금지
  reward_freeze.py          # SHA manifest와 변경 감지
  policy.py                 # frozen P2 encoder adapter + small set/graph head
  imitation.py              # oracle trace와 supervised+greedy 기준선
  policy_gradient.py        # group-relative clipped update
  beam_search.py            # width/budget sweep, 동일 verifier
  ilp_baseline.py           # 분해 가능 목적의 CP-SAT/ILP 통제
  acquisition_bandit.py     # 부속 horizon≈1 절차
  reward_audit.py           # T26 false-accept와 hacking monitor
  evaluate.py               # per-handle/structure/meta/test 단발 평가
  evidence_export.py        # evidence_grid xlsx 접속
configs/
  platt_p4_prereg.yaml
  split_manifest.json
tests/
  test_action_mask.py
  test_set_canonicalization.py
  test_reward_freeze.py
  test_no_silver_import.py
  test_transform_equivariance.py
  test_beam_budget_accounting.py
```

접속점은 다음처럼 제한한다.

- `cubicasa_ir`: SEG-IR와 handle/source element mapping을 읽는다. P4가 별도 변환 truth를 만들지 않는다.
- `cubicasa_ml`: P2가 선정한 checkpoint, 6특징 schema, split manifest를 읽는다. 학습 코드를 복제하지 않는다.
- `fast_score`: deterministic unary/pruning feature와 기존 하네스 속도 비교에 쓰되 truth나 reward로 승격하지 않는다.
- `evidence_grid`: 셀·arm·seed·split별 metric, SHA, runtime, cap-hit, 실패 사유, beam/ILP budget sweep을 xlsx로 내보낸다.

핵심 테스트는 동일 최종 set의 행동 순서가 reward를 바꾸지 않는지, transform 뒤 handle mapping이 보존되는지, reward 파일 한 바이트 변경이 run을 막는지, 학습 프로세스에서 silver 모듈 import가 실패하는지 검증한다. 후보 생성의 quadratic 폭발은 synthetic 최대치가 아니라 실도면의 큰 definition을 대상으로 stress test한다.

개발 규모의 사전 추정은 핵심 모듈 약 1,500~2,500 LOC와 테스트·하네스 약 800~1,200 LOC다. 이는 측정치가 아닌 계획 추정이며, PR-1/P3/P2 모듈 재사용 정도에 따라 바뀐다. 구현 순서는 (a) schema·후보 cache, (b) verifier freeze/audit, (c) greedy/beam/ILP, (d) 학습 0 판정, (e) 그때까지 살아 있으면 imitation/policy-gradient, (f) evidence export다. RL 코드를 먼저 만드는 순서를 금지한다.

## 6. 실험 셀 정의

### 6.1 공통 프리레그와 집계

평가 단위는 원본 handle이다. 1차 synthetic F1은 held-out 전체의 pooled per-handle F1, 보조로 도면별 macro F1과 pair/link/component 지표를 보고한다. RL의 3 seed 결과는 사전 봉인한 산술평균으로 집계하고 seed별 원값을 숨기지 않는다. Metamorphic 1차 지표는 hidden transform family의 도면별 위반율 평균이며 낮을수록 좋다. 동일 도면·동일 후보 cache를 arm 간 paired 비교한다.

Val은 개발·튜닝·threshold 봉인에 사용한다. Test manifest는 생존 판정 전 접근하지 않고, 해시만 기록한다. 모든 셀에는 shuffled-label/action 대조군을 포함한다. Shuffle이 비정상적으로 높은 성능을 내면 누출 조사 전까지 해당 셀은 무효다. 실패와 timeout도 evidence xlsx의 행으로 남긴다.

아래 시간과 폭은 모두 **제안된 예산/판정값**이며 새 실측 주장이 아니다.

### 셀 P4-E0 — 선결·verifier 자격 감사

- **가설:** 동결 verifier는 명백히 틀린 집합을 통과시키지 않으며 synthetic·metamorphic proxy의 오류가 완전히 같은 prior로 붕괴하지 않는다.
- **arm:** truth set, empty, all-wall, random, GBDT-threshold, 구조 교란, scale/unit/explode 교란, 긴 평행 distractor; proxy disagreement audit.
- **지표:** verifier false-accept rate, false-reject rate, source별 오류 교집합/조건부 오류, sentinel 통과율, reward SHA 재현성.
- **합격선:** 패널 T26 그대로 false-accept ≤0.01. PR-1 fidelity gate, PR-2 독립성 결론, P3 sentinel/recall floor도 모두 PASS여야 한다.
- **킬/중단:** false-accept >0.01, reward hash 비재현, sentinel 미검증, proxy 붕괴를 독립 확증으로 오해해야만 보상이 성립하는 경우 P4 실행을 중단한다. 이는 HR1 성능 패배와 구분한다.
- **예산:** 로컬 CPU 1일 cap, GPU 불필요. seed가 아니라 봉인된 adversarial family 전수와 bootstrap을 사용한다.

### 셀 P4-E1 — 학습 0 reward-landscape probe

- **가설:** 집합 보상에 실제 탐색 난도가 있다면 beam이 greedy를 유의미하게 넘고, tractable subset에서 둘 다 ILP/열거 상한에 붙지 않는다.
- **arm:** random, greedy, beam width 4/16/64, tractable ILP/열거. 모두 동일 후보·동일 동결 verifier·동일 총 호출/월클록 ledger를 쓴다.
- **지표:** synthetic val F1, terminal reward, beam gain, ILP incumbent/bound gap, verifier 호출 수, action branching, wallclock.
- **합격선:** beam이 greedy보다 개선되고, greedy가 certified/empirical upper bound에 붙지 않아야 E2로 진행한다.
- **사전 킬 정의:** 전체 val에서 best-beam−greedy F1 <0.01이고, tractable stratum에서 상한−greedy F1 ≤0.01이면 `greedy≈beam≈upper bound`로 판정하여 학습 전에 HR1 RL 레인을 kill한다. 상한을 인증할 수 없으면 “상한 근접”을 주장하지 않고 다음 셀로 보수적으로 진행한다.
- **예산:** 로컬 1일, 학습 0, seed 대신 deterministic tie-breaking 1회와 random baseline 3 seed.

### 셀 P4-E2 — 엔티티 고정-라벨 음성 대조

- **가설:** 동일한 동결 특징에서 per-handle supervised BCE/GBDT가 one-step RL보다 같거나 낫다.
- **arm:** 기존 GBDT, 동일 policy head의 supervised BCE, 각 handle을 독립 행동으로 취급한 policy-gradient. Encoder, feature, tuning budget은 공유한다.
- **지표:** synthetic held-out 및 CubiCasa val의 per-handle P/R/F1, calibration, 학습 분산, wallclock.
- **합격선:** 이 셀에는 HR1 생존권이 없다. RL이 supervised를 0.05 F1 이상 넘지 못하면 고정-라벨 full RL을 명시적으로 kill하고 C07의 이 범위 적용을 유지한다.
- **이상 결과 처리:** RL이 0.05 이상 높아도 즉시 채택하지 않는다. supervised 목적·class weight·threshold·budget 누락을 red-team하고 재현된 차이만 별도 이슈로 남긴다. 집합 조립의 승리로 합산하지 않는다.
- **예산:** arm별 동일 8시간 cap, 3 seed, 로컬 GPU. Test는 열지 않는다.

### 셀 P4-E3 — 집합 조립 본선

- **가설:** 비분해 구조 보상에서 RLVR 정책은 동일 compute beam보다 높은 synthetic held-out handle F1을 내면서 metamorphic 위반을 늘리지 않는다.
- **arm:** supervised+greedy, beam budget sweep, ILP 보조 통제, RLVR greedy decode. 모두 같은 πref, P2 encoder, 후보 cache, reward SHA를 쓴다.
- **지표:** synthetic held-out per-handle F1(1차), P/R, pair/link/component F1, hidden metamorphic 위반율, reward, verifier 호출 수, wallclock, peak RAM/VRAM, cap-hit rate.
- **유일 생존 밴드:** `mean_seed(F1_RL) − F1_beam ≥ +0.05` **AND** `mean_seed(Violation_RL) − Violation_beam ≤ 0`. Paired bootstrap interval과 seed별 결과는 보고하지만 이 사전 판정식을 사후 교체하지 않는다.
- **킬:** 둘 중 하나라도 미달하면 HR1 RL 레인을 kill한다. supervised+greedy 또는 ILP가 RL보다 좋으면 그 결과도 그대로 kill 근거로 기록한다. 연장·추가 seed·reward 재가중으로 구조하지 않는다.
- **예산:** 공통 imitation prefix 후 각 arm/seed 추가 24시간 cap, RL 3 seed. Beam/ILP도 동일 ledger 상한. 로컬 우선, DGX는 사후 재현 ablation만.

### 셀 P4-E4 — 보상해킹·강건성 감사

- **가설:** 높은 동결 reward가 독립 truth F1 및 hidden metamorphic 성능과 같은 방향으로 움직인다.
- **arm:** E3 checkpoint 시계열, adversarial set perturbation, hidden generator family, hidden transformation family, reward항별 ablation.
- **지표:** checkpoint reward-F1 궤적, rank correlation, empty/all-wall 빈도, recall-floor hit, conflict/cap-hit, hidden-family regret.
- **즉시 킬:** 연속 평가에서 정책 reward가 상승하는데 synthetic held-out F1이 하락하는 괴리가 재현되거나, best-reward checkpoint가 empty/all-wall·sentinel exploit로 선택되면 즉시 중단하고 incident ID, 최초 checkpoint, exploit family, SHA를 기록한다. E3 평균으로 덮지 않는다.
- **추가 킬:** hidden family에서만 성능이 붕괴하여 E3 생존 밴드가 사라지면 HR1을 kill한다.
- **예산:** E3 실행 중 CPU audit + 종료 후 로컬 8시간 cap, 동일 3 seed trace; 새 정책 튜닝 없음.

### 셀 P4-E5 — 외부 전이와 test 단발

- **가설:** E3에서 살아남은 조립 이점이 synthetic generator에만 국한되지 않는다.
- **arm:** 봉인된 E3의 supervised+greedy, beam, RLVR checkpoint 그대로. CubiCasa test를 방법당 한 번 실행하고, 1.dwg hidden metamorphic 및 held-out silver 일치표를 생성한다.
- **지표:** CubiCasa test per-handle P/R/F1, 도면 macro F1, 1.dwg hidden metamorphic 위반, silver 2-family별 일치. FloorPlanCAD는 T24/PR-3 통과 시 비보상 mask 진단만.
- **합격선:** E3의 HR1 판정을 바꾸는 사후 합격선으로 쓰지 않는다. 다만 RL의 CubiCasa test F1이 beam보다 낮거나 hidden metamorphic 위반이 높으면 “synthetic 한정”으로 명시하고 배포를 kill한다.
- **킬:** test를 미리 보거나, checkpoint/threshold를 test 결과로 바꾸거나, silver를 독립 5표로 평균하면 셀 전체 무효다.
- **예산:** checkpoint당 test 1회, 추가 학습 0, deterministic decode + RL seed 3개 사전 집계. 외부 권리 미확인 시 실행하지 않는다.

### 셀 P4-E6 — 획득 순서 contextual bandit 부속 절차

- **가설:** definition context로 비싼 독립 판정/렌더의 한 단계 가치가 예측 가능하지만 장기 credit assignment는 필요 없다.
- **arm:** random, uncertainty, diversity-stratified heuristic, contextual bandit(LinUCB 또는 Thompson 계열 중 val에서 하나 봉인).
- **context/action/reward:** context는 후보 수, unary entropy, component fragmentation, transform disagreement, 예상 렌더 비용이다. action은 다음 definition 하나 선택, reward는 허용된 사람 truth 또는 synthetic oracle을 얻은 직후의 정보가치/오류감소다. E1.5 silver는 관측·reward·update에 사용하지 않는다.
- **지표:** 동일 비용에서 누적 발견 오류, coverage, 선택 편향, wallclock.
- **합격선:** random/heuristic보다 나아야 부속 도구로 유지한다. full RL과 비교하거나 HR1에 합산하지 않는다.
- **킬:** 효과가 다음 라운드 이후의 상태에 의존한다는 증거가 없는데 full RL로 포장하거나, silver feedback으로 bandit을 갱신하면 즉시 kill한다.
- **예산:** 로컬 CPU 1일 cap, offline replay 3 seed. PR-3가 필요한 사람 truth arm은 counsel 전 실행 금지.

Self-training은 별도 실험 셀을 만들지 않는다. 동일 모델의 pseudo-label E-step과 재학습 M-step으로 명시하고 P2 실험표에 귀속한다. P4가 그 개선을 RL reward나 policy improvement로 보고하는 것을 금지한다.

## 7. Red team 티켓 응답

### T1 / T17 — 대리 독립성 및 truth-source 교차요인

**수용, 하드 선결.** Synthetic·CubiCasa 사람 라벨·metamorphic·silver를 단순 평균하지 않는다. 동일 definition에서 source별 오류 교집합, 조건부 불일치, 구조 유형별 disagreement tensor를 먼저 만든다. 대각 성능만 높고 비대각 전이가 무너지면 proxy bootstrap 사슬이 닫히지 않은 것으로 기록한다. Silver는 이 감사에서도 학습 reward가 아니라 독립 관측 열이다. T1이 해소되지 않으면 여러 proxy를 “상호 확증”으로 표현하지 않는다.

### T2 — 실제 벽 합성 생성기 부재와 fidelity 실패

**수용, 하드 선결.** 현재 합성팩의 B1 FAIL(KS 0.5792, TV 0.265)과 벽 코드 부재를 우회하지 않는다. POLYLINE/블록/비평행 조각 및 실도면 entity 혼재를 포함한 PR-1 생성기가 fidelity gate를 통과하고 train/eval family가 분리되기 전에는 E0 이후 성능 셀을 실행하지 않는다. 기존 S/F/M 수치로 새 wall truth가 존재한다고 쓰지 않는다.

### T3 / T4 — E1 법의학 감사와 Ornith 원시 아티팩트

**부분 선결로 수용.** CL-A의 정렬-key 재계산과 raw artifact 감사가 끝나기 전에는 E1.5 silver의 최종 일치를 해석하지 않는다. P4 reward 자체는 silver를 사용하지 않으므로 Ornith 불통이 학습 0 probe를 막지는 않지만, 프로그램 큐 순서를 따라 CL-A 결과를 본선 전 provenance manifest에 연결한다.

### T5 / T34 — 권리 확인과 인용 재-status

**수용.** CubiCasa/FloorPlanCAD arm은 counsel 서면 확인 전 시작하지 않는다. R-레인 6개가 모두 `experiment_executed:false`라는 상태를 유지하고, C07 및 최신 RLVR 시스템 서지는 요검증으로 남긴다. 본 문서의 문헌 이름은 방법 계보이며 E2 성능 증거가 아니다.

### T6 — 평가 단위와 집합 조립 산출물 혼동

**해소 설계.** 공용 1차 출력과 지표는 per-handle `wall_member(h)`로 고정한다. Pair/chain/network는 별도 schema·별도 보조표다. 구조 점수만 올라 per-handle F1이 오르지 않으면 프리레그를 통과할 수 없다.

### T7 — 0벽 퇴행 정책

**수용, 하드 선결.** Metamorphic 위반율-only 보상을 금지한다. P3에서 검증된 0벽/전벽 sentinel과 recall 최저선을 reward wrapper에 넣고 SHA로 봉인한다. P3 검증 전에는 real-corpus reward를 활성화하지 않는다.

### T10 / T23 — Graph IR adjacency 완전성

**조건부 수용.** P4의 chain/network 행동은 P2/Graph IR adjacency에 의존한다. 후보 adjacency 감사에서 실제 연결을 누락하면 정책은 그 벽을 행동으로 선택할 수 없다. Candidate recall ceiling과 누락 유형을 E0에 보고하고, ceiling이 E3의 +0.05 밴드를 원천적으로 막으면 RL을 돌리기 전에 입력표현을 부적격 처리한다. P4가 adjacency 누락을 학습 실패로 오인하지 않는다.

### T24 — pixel→handle 역투영

**범위 제한으로 해소.** Exact synthetic 하네스가 없으므로 FloorPlanCAD를 본선에서 제외한다. T24가 통과한 뒤에만 비보상 보조 진단으로 연결한다.

### T26 — verifier false-accept

**최상위 사활 게이트로 수용.** Adversarial wrong-set audit에서 false-accept ≤0.01을 E0 합격선으로 둔다. 초과 시 reward weight를 RL 결과를 보며 고치지 않고 verifier를 재설계한 뒤 새 SHA·새 프리레그로 E0부터 다시 시작한다. 실패 verifier로 얻은 정책 성능은 폐기한다.

### 약한 기준선·분산·계산 폭발 관련 티켓의 승계

Beam width 1/4/16/64와 ILP budget/solver gap을 전부 로그하여 약한 beam 하나만 세우지 않는다. RL seed는 3개로 고정하고 step/wallclock cap 도달 시 연장하지 않는다. 최대 412,775 선분 정의에서 candidate explosion과 peak RAM을 기록하며 조용한 샘플 제외를 금지한다. 기존 deterministic baseline 계측 티켓(T9/T21)은 unary input provenance로 연결하되, 그 점수를 truth로 사용하지 않는다.

## 8. 인접 제안과의 관계 및 정직한 사망 조건

### 8.1 병합·접속 지점

- **P2 / CL-F:** 동결 encoder, 6특징 schema, supervised/GBDT 기준선, self-training을 제공한다. P4는 encoder를 다시 훈련해 승리를 만들지 않는다.
- **P3 / CL-D:** metamorphic transform, sentinel, recall floor, transform별 handle mapping을 제공한다. P3가 미검증이면 실도면 reward는 꺼진다.
- **CL-C / PR-1:** synthetic wall truth와 숨긴 mutation family를 제공한다. 이는 P4의 verifiable 자격 그 자체다.
- **CL-E:** proxy independence와 train-source×eval-source 표를 공유한다. P4는 그 결과를 결합 보상의 허가서로 사용한다.
- **P1 / CL-B:** coverage-complete 정규화와 INSERT world transform을 받아 candidate ceiling을 높인다. P4가 전처리 결함을 RL로 보상하지 않는다.
- **CL-G:** FloorPlanCAD pixel→handle exact 하네스가 통과할 때만 raster 보조 진단을 공유한다.
- **doe/calibration/feyerabend의 RL 자리 제안:** per-handle=supervised, set assembly=RLVR 후보, acquisition=bandit이라는 공통 분할을 동일 셀 이름과 evidence schema로 합칠 수 있다.

### 8.2 차별점

P4의 차별점은 RL 모델을 하나 더 추가하는 데 있지 않다. 첫째, C07을 증거 없는 권위가 아니라 반증 가능한 대상에 놓는다. 둘째, 프로그램 공용 per-handle 평가와 P4 전용 set structure를 동시에 보존한다. 셋째, 학습 전에 verifier false-accept와 greedy≈상한을 검사하여 가장 싼 지점에서 RL을 죽일 수 있다. 넷째, 동일 supervised initialization을 greedy·beam·RL이 공유하고 beam/ILP budget sweep을 의무화한다. 다섯째, silver를 reward에서 물리적으로 제거해 판정자-보상 해킹 경로를 닫는다.

### 8.3 이 제안이 죽어야 하는 조건

다음 중 하나면 변명 없이 해당 범위의 P4를 종료한다.

1. PR-1 생성기가 fidelity gate를 통과하지 못하거나 pair/link truth를 신뢰 가능하게 만들지 못한다. 이 경우 실험은 부적격이며 HR1의 과학적 승패를 주장하지 않는다.
2. T26 false-accept가 0.01을 넘거나 P3 sentinel/recall guard 없이만 metamorphic reward가 작동한다.
3. 학습 0에서 greedy와 beam이 사실상 같고 둘 다 인증/경험 상한에 프리레그 허용차 내로 붙는다. RL은 훈련 전에 kill한다.
4. 고정-라벨 셀에서 RL이 supervised보다 못하거나 같으면 엔티티 분류 RL을 kill한다. 예상된 결과이며 집합 조립으로 몰래 합산하지 않는다.
5. 본선에서 RL−beam synthetic held-out F1이 +0.05 미만이거나 RL의 metamorphic 위반 증가분이 0보다 크다. 둘 중 하나만으로 HR1 RL 레인을 kill한다.
6. 정책 reward는 오르는데 독립 synthetic F1이 내리는 괴리, empty/all-wall 퇴행, hidden-family exploit가 나타난다. 즉시 incident를 남기고 kill한다.
7. 충분한 width/시간의 beam 또는 tractable ILP가 RL을 이긴다. “탐색이 실무에서 이긴다”는 바로 이 제안이 찾도록 설계한 kill 후보다.
8. RL 이점이 action-order 중복, 더 큰 encoder, 더 많은 wallclock, test tuning, silver feedback, 약한 baseline에서만 나온다.
9. CubiCasa test/1.dwg hidden 변환에서 이점이 뒤집히면 synthetic 한정 결과로 낮추고 배포를 kill한다.
10. 획득 절차가 horizon≈1인데 full RL로 불러야만 성과를 주장할 수 있거나, self-training 개선을 RL 개선으로 재명명해야만 한다.

반대로 오직 E0·E1을 통과하고 E3의 두 조건을 동일 compute beam 대비 모두 만족하며 E4 보상해킹 감사를 견딘 경우에만 HR1을 생존시킨다. 그 결론도 “벽 탐지 전반에 RL이 우월”이 아니라, **동결 verifier가 있는 pair→chain→network 조립에서 정책 학습이 반복 탐색을 유의미하게 amortize했다**는 좁은 주장으로 제한한다.

DOSSIER_COMPLETE: platt_P4
