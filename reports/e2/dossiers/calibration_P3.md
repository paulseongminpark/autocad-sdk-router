# calibration_P3 — DWG Graph IR용 self-supervised heterogeneous GNN 방법론 심층 도시에

- 제안: **P3. DWG Graph IR용 self-supervised heterogeneous GNN**
- 현재 판정: **OPEN / 수치 forecast abstain**
- `forecast`: `null`
- `score_type`: `brier`
- `reference_class`: `RC-WALL-ZL`, `n=0`, `n_min=5`
- `base_rate`: `none`
- `abstain_flag`: `empty_reference_class`
- `uncertainty_type`: `epistemic` — adjacency audit와 family-held-out probe로 줄인다.
- `resolution_verdict`: `open`
- `update_log`: `2026-07-17 KST` 최초 abstain. Self-supervised ablation의 OOD lift는 상향 증거, adjacency audit 실패 또는 family/template dedupe 뒤 lift 소멸은 하향 증거로 미리 약정한다.
- 주장: P3가 동일한 동결 held-out에서 최선의 비-GNN baseline보다 사전등록 lift를 내고 node/relation/OOD/calibration/compute gate를 모두 통과한다.
- 해소 조건: `P3_lift_CI_low>0`이고 이 문서에 고정한 모든 필수 band가 참이다.
- 해소 트리거: graph manifest, split manifest, calibration rule, model bundle hash를 동결한 뒤 test를 한 번만 열어 `wsd_eval_p3.json`을 생성할 때다.

> **증거 경계.** 이 문서는 웹 검색을 사용하지 않았다. 아래의 프로그램·자산·성능 수치는 전부 패킷의 2026-07-18 실측 다이제스트에서만 가져왔다. 논문·시스템 계보는 일반 문헌 지식이며 성능 수치를 인용하지 않는다. 구체 서지정보와 구현 라이선스는 실제 개발 착수 전에 재확인한다. 이 문서의 하이퍼파라미터, seed, 시간, 허용치 중 패킷 band가 아닌 값은 모두 **실측 결과가 아니라 사전등록을 위한 제안 설계값**이다.

## 1. 이론적 근거·선행연구

### 1.1 이 제안이 필요한 이유

현재 관측은 “국소 평행 이중선”만으로 벽 의미를 충분히 분리할 수 없음을 보여 준다. CubiCasa5k 전이에서 기하 탐지기 v1은 val `F1=0.2358`이었고, Direction 화살표, BoundaryPolygon, Door, Window, DimensionMark가 주된 false positive였다. 최소길이 필터의 천장도 `F1=0.335`여서 긴 평행 구조 자체가 교란원이다. 반면 동일한 벡터축에서 여섯 기하 특징을 사용한 HistGradientBoosting은 val `P=0.860`, `R=0.370`, `F1=0.517`, `AUC=0.9215`까지 올라갔다. 즉 비선형 조합은 이미 큰 이득을 냈지만, 회수율과 구조적 문맥에는 여지가 있다.

P3의 가설은 한 선분의 길이·각도·간격만 보지 않고 다음 문맥을 함께 보면 그 남은 여지를 회수할 수 있다는 것이다.

- 같은 block definition에 속해 반복 배치되는 선들은 문·창·기호 같은 “반복 심볼”일 가능성이 있다.
- 실제 벽 후보는 단일 선이 아니라 평행·공선·교차·정션 관계가 연결된 국소 subgraph를 이룬다.
- block reference의 transform과 definition containment를 따라가면 world-space에서는 만나는 선과 definition-space에서는 떨어진 선을 구분할 수 있다.
- layer 이름 자체를 쓰지 않더라도 한 layer에 속한 엔티티의 구조 통계는 약한 문맥이 될 수 있다.
- text 내용 자체를 읽지 않더라도 dimension text의 위치·방향·근접 패턴은 도면 주석 구조를 식별하는 데 도움이 될 수 있다.

단, 이것은 “그래프면 의미가 생긴다”는 주장이 아니다. Graph IR adjacency가 빠졌거나 잘못 생성되면 GNN은 오류를 증폭한다. 자기지도 target도 semantic truth가 아니며, 단지 입력의 구조적 규칙성을 학습한다. 따라서 P3의 출력은 확률형 soft evidence이고, deterministic topology gate의 veto를 절대 대체하지 않는다.

### 1.2 방법론 계보

아래 명칭은 일반 문헌 지식에 기반하며, 정확한 판본·저자 순서·라이선스는 구현 전 재확인한다.

1. **관계형·이종 그래프 신경망**
   - R-GCN은 edge relation마다 다른 변환을 두는 기본 계보를 제공한다.
   - Heterogeneous Graph Transformer(HGT)는 node type, edge type, attention을 결합해 entity, block definition/reference, layer, text anchor를 한 모델에서 다루는 직접적인 출발점이다.
   - HAN과 metapath 계열은 이종 관계를 요약하지만, 본 과업에서는 미리 정한 metapath가 DWG의 깊은 INSERT 구조를 누락할 수 있으므로 주 모델보다는 비교 대상으로 적합하다.
   - GraphSAGE와 GAT는 sampled neighborhood 및 attention의 기본 구성요소다. production p95 그래프가 매우 클 수 있으므로 full-batch보다 neighborhood sampling 계보가 중요하다.

2. **그래프 자기지도 사전학습**
   - GraphMAE와 attribute masking 계열은 node attribute 일부를 가린 뒤 주변 구조에서 복원한다. 본 제안의 masked-attribute 복원과 직접 대응한다.
   - Deep Graph Infomax, GraphCL, GRACE, BGRL은 서로 다른 view의 표현을 일치시키는 계보다. 본 과업에서는 rigid transform, reflection, unit conversion, node-order permutation, layer rename을 label-preserving view로 사용한다.
   - 동일 도면 안의 서로 다른 선을 무조건 negative로 두면 실제 한 벽의 두 면이나 연결 벽을 밀어내는 false-negative 문제가 생긴다. 따라서 contrastive negative는 다른 family에서만 취하고, 동일 node correspondence를 positive로 삼는다.

3. **CAD·구조 그래프 학습**
   - SketchGraphs는 CAD sketch의 entity/constraint graph를 학습 대상으로 삼는 계보다.
   - BRepNet과 UV-Net은 경계표현의 face/edge topology에 message passing을 적용하는 CAD 계보다.
   - Graph2Plan, House-GAN류의 floor-plan graph 연구는 공간·방 관계가 유용함을 보여 주는 인접 계보지만, 생성 과업이고 DWG per-handle wall membership과 동일한 truth를 갖지 않는다. 직접 성능 근거로 인용하지 않는다.
   - 이 계보의 핵심 교훈은 “기하 primitive + 명시적 topology”의 결합이지, Graph IR 자체가 semantic label이라는 뜻이 아니다.

4. **관계 예측과 다중과업**
   - DistMult/ComplEx류의 relation scoring과 symmetric pair MLP는 두 entity가 같은 물리 벽의 pair인지 예측하는 출발점이다.
   - node wall membership과 pair relation을 함께 학습하면 node head가 독립적인 점 분류에 머무르지 않고, 양쪽 면의 일관성을 보게 할 수 있다. 반대로 pair candidate universe가 잘못되면 node head까지 오염되므로 두 loss와 두 truth를 분리 보고해야 한다.

5. **확률 보정**
   - temperature scaling은 validation에서 logit scale만 보정하고 ranking을 바꾸지 않는 단순한 후처리다.
   - Brier decomposition의 reliability(`REL`)와 resolution(`RES`)을 사용하면 “정확도는 높지만 확률은 과신”인 모델과 실제로 사건을 구분하는 모델을 분리할 수 있다.
   - 제안 단위의 `forecast=null`과 모델 출력 확률의 calibration은 별개다. 빈 reference class 때문에 제안 성공확률은 계속 abstain하지만, node probability는 `REL`/`RES`로 평가한다.

### 1.3 반증 가능한 핵심 가설

P3가 가져와야 하는 것은 단순한 model capacity가 아니라 **family-held-out에서 유지되는 관계 문맥 이득**이다. 다음 중 하나라도 관측되면 이론적 설명은 약해진다.

- 이름·handle·파일명·순번을 제거하고 동일 block/template family를 묶자 lift가 사라진다.
- adjacency audit 뒤 잘못된 proximity edge를 제거하자 lift가 사라진다.
- masked 복원은 잘하지만 wall membership에는 이득이 없다.
- IID에서는 오르지만 style-OOD에서 하락 폭이 band를 넘는다.
- HistGradientBoosting과 P1/P2가 동일 truth universe에서 이미 같은 정보를 회수한다.

따라서 “GNN이 복잡하니 더 좋을 것”은 가설이 아니며, **최선 비-GNN baseline 대비 paired lift의 CI 하한**만 최종 주장을 해소한다.

## 2. 알고리즘 정확 스펙

### 2.1 입력·출력·평가 단위

입력은 한 root drawing과 재귀적으로 도달 가능한 block/Xref family를 canonicalize한 typed graph다.

\[
G=(V, E, X, A),\qquad
V=V_E\cup V_D\cup V_R\cup V_L\cup V_T
\]

- `E`: CAD entity node. 평가 대상은 원본 source handle 하나당 하나의 canonical entity node다.
- `D`: block definition node.
- `R`: block reference node.
- `L`: layer node.
- `T`: text anchor node. primary arm은 문자열을 보지 않고 위치·bbox·방향·문자종류의 거친 구조만 본다.
- `X`: node-type별 feature tensor.
- `A`: edge attribute tensor.

모델 입력 feature에는 handle, entity 생성 순번, filename/path, synthetic sequence index, block/layer 이름 문자열, 원문 text, split/family ID를 넣지 않는다. 이 값들은 audit 및 결과를 원래 handle에 돌려주는 sidecar mapping에만 존재한다.

모델 출력은 다음 두 종류다.

\[
p_h=P(y_h^{wall}=1\mid G),\qquad
q_{h,k}=P(z_{h,k}^{pair}=1\mid G),\ (h,k)\in C_G
\]

- `p_h`: source handle의 wall membership soft evidence.
- `q_{h,k}`: deterministic candidate universe `C_G` 안에서 두 handle이 한 wall-pair 관계라는 soft evidence.
- F/FloorPlanCAD에는 node truth만 사용하고 pair truth를 만들지 않는다.
- S/synthetic에는 generator가 직접 낸 node truth와 unordered wall-pair truth를 각각 사용한다.

block definition entity가 여러 reference로 나타나는 경우 world-space spatial event는 occurrence별로 계산하되, 학습 node는 source handle로 다시 접는다. 같은 source handle에 대한 occurrence message는 합이 1이 되는 attention pooling으로 canonical entity에 모은다. synthetic generator가 동일 handle에 상충하는 occurrence label을 만들면 해당 graph를 “모호”로 제외하지 않고 **generator 오류로 FAIL**시킨다. 이렇게 해야 어려운 사례를 조용히 버리는 선택편향을 막을 수 있다.

### 2.2 Graph IR 구축 규칙

#### Node feature

- `E/entity`: geometry type, 정규화 길이·bbox·중점, `sin(2θ)`, `cos(2θ)`, curvature/closed 여부, endpoint degree, local junction count, parallel/collinear 후보 수, block depth, fast-score의 **원시 기하 evidence channel**. 최종 detector score/판정은 primary feature로 넣지 않는다.
- `D/block definition`: entity type histogram, entity 수의 log transform, bbox aspect, nested-reference 통계. definition 이름은 제외한다.
- `R/block reference`: 선형 transform의 rotation/reflection/anisotropy 요약, translation의 drawing-relative 좌표, nesting depth. reference handle과 block 이름은 제외한다.
- `L/layer`: entity type histogram, 길이·방향·degree 통계, visible/frozen 같은 비문자 상태가 합법적으로 제공될 때만 사용. layer 이름과 색상-이름의 파생 proxy는 primary arm에서 제외한다.
- `T/text anchor`: bbox, 위치, 방향, 높이의 drawing-relative 값과 `digit/alpha/mixed` 같은 coarse class. 원문 token, OCR embedding, dimension value는 primary arm에서 제외한다.

좌표와 거리는 absolute mm band에만 의존하지 않는다. 우선 명시 unit/dimension anchor가 있으면 그 scale을 별도 feature로 보존하고, 주 feature는 drawing의 robust geometric scale로 정규화한다. anchor가 없으면 fallback 사실을 flag로 남긴다. 이 설계는 기존 scale 불변성 arm이 `0.7624`로 FAIL했고 CubiCasa의 미상 축척에서 물리 두께 prior가 무력했던 관측을 직접 반영한다.

#### Typed edge inventory

모든 directed relation에는 reverse relation을 따로 두고, 서로 다른 relation은 동일 node pair에도 공존할 수 있다.

1. `contains_def`: `D -> E|R|T` 및 reverse. block definition의 직접 자식을 나타낸다.
2. `contains_layer`: `L -> E|R|T` 및 reverse. layer 소속을 containment family로 표현한다.
3. `instantiates`: `R -> D` 및 reverse. edge attribute에 정규화 transform 요약을 둔다.
4. `intersects`: `E <-> E`. world-space occurrence에서 실제 교차한 경우이며 교차형, 교차각, endpoint/interior 여부를 attribute로 둔다.
5. `proximity`: `E|T <-> E`. spatial index로 후보를 찾고 정규화 거리와 방향을 둔다.
6. `parallel`: `E <-> E`. 방향차와 projected overlap을 둔다.
7. `collinear`: `E <-> E`. 방향차, normal offset, along-axis gap을 둔다.

curve는 가능한 경우 native intersection을 사용하고, tessellation이 필요한 경우 tolerance를 config와 manifest에 기록한다. Xref가 누락되었거나 transform cycle을 해결하지 못하면 조용히 edge를 생략하지 않고 graph를 `invalid_unresolved_reference`로 표시한다.

proximity·parallel·collinear 폭증은 다음 방식으로 막는다.

- spatial index로 radius 후보를 만든다.
- 각 relation별로 node당 가까운 순서의 top-`k_r`만 보존한다.
- `k_r`과 정규화 radius는 synthetic train graph에서만 선택하고 freeze한다.
- cap 때문에 누락된 known synthetic positive relation은 adjacency recall의 false negative로 계산한다.
- production p95 edge envelope와 peak RAM envelope를 넘기면 더 큰 모델로 우회하지 않고 graph path를 kill한다.

family 분리는 graph 구축보다 먼저 고정한다. Xref 연결요소, canonical block-structure fingerprint, synthetic template lineage와 모든 parameter variant를 하나의 `family_id`로 묶는다. fingerprint와 `family_id`는 split 도구만 보고 모델 feature에는 들어가지 않는다. 모든 node ID는 shard 안에서 재번호화하고 node-order permutation test를 통과해야 한다.

### 2.3 Heterogeneous encoder

주 모델은 edge attribute를 받는 얕은 HGT 계열이다. node type별 입력 projection 뒤 relation별 attention/message를 계산한다.

\[
h_v^{(0)}=W_{\tau(v)}x_v+e_{\tau(v)}
\]

\[
\alpha_{uv}^{r,l}=\operatorname{softmax}_{u\in N_r(v)}
\left(\frac{(W_Q^{\tau(v),l}h_v)^T(W_K^{r,l}h_u+\phi_K^r(a_{uv}))}{\sqrt d}
+b_r\right)
\]

\[
m_v^{(l)}=\sum_r\sum_{u\in N_r(v)}\alpha_{uv}^{r,l}
\left(W_V^{r,l}h_u+\phi_V^r(a_{uv})\right)
\]

\[
h_v^{(l+1)}=\operatorname{LayerNorm}
\left(h_v^{(l)}+\operatorname{Dropout}(W_O^{\tau(v),l}m_v^{(l)})\right)
\]

기본 probe는 패킷대로 3-layer다. full study에서는 2–4 layer만 허용하고 residual, LayerNorm, relation dropout을 사용한다. 더 깊은 모델은 oversmoothing 진단 없이 허용하지 않는다. R-GCN은 “attention이 실제 이득인지”를 확인하는 architecture ablation일 뿐 별도 제안으로 승격하지 않는다.

### 2.4 자기지도 사전학습

#### Masked-attribute 복원

node type별로 일부 attribute를 가리고 같은 type 전용 decoder로 복원한다.

\[
L_{mask}=\sum_t\left(
\lambda_{t,c}\operatorname{CE}(\hat x_{t,c},x_{t,c})+
\lambda_{t,b}\operatorname{BCE}(\hat x_{t,b},x_{t,b})+
\lambda_{t,n}\operatorname{Huber}(\hat x_{t,n},x_{t,n})
\right)
\]

식별자·이름·문자열은 mask target에도 포함하지 않는다. 그렇지 않으면 model이 file/block naming convention을 암기하게 된다. mask는 feature column과 node를 함께 섞어 적용하되, 한 node의 모든 좌표와 geometry type이 동시에 사라져 target이 불가능해지는 패턴은 금지한다.

#### Transform-contrastive 학습

같은 graph에서 두 view `T1(G)`, `T2(G)`를 만든다. 허용 transform은 rigid rotation/translation, reflection, 올바른 unit conversion, node-order permutation, layer rename이다. arbitrary geometric scale은 현재 strict invariance가 실패했으므로 처음부터 positive로 간주하지 않는다. unit metadata와 모든 거리 attribute까지 일관되게 변환되는 **단위 동치 변환**만 positive다.

동일 canonical node의 두 embedding을 positive로, 다른 family의 node만 negative로 둔다.

\[
L_{con}=-\frac{1}{|M|}\sum_{i\in M}
\log\frac{\exp(\operatorname{sim}(z_i^1,z_i^2)/\tau)}
{\exp(\operatorname{sim}(z_i^1,z_i^2)/\tau)+
\sum_{j:\,family(j)\ne family(i)}\exp(\operatorname{sim}(z_i^1,z_j^2)/\tau)}
\]

node-level loss와 type-aware graph-pool loss를 함께 쓰며, total pretraining loss는 다음과 같다.

\[
L_{pre}=\lambda_mL_{mask}+\lambda_cL_{con}
\]

사전학습 corpus에는 split상 train family인 라벨 없는 graph만 들어간다. final held-out family의 label을 보지 않았더라도 그 geometry를 pretrain에 넣는 transductive 방식은 금지한다. Graph IR, transform correspondence, masked target은 semantic truth count에 포함하지 않는다.

### 2.5 Joint fine-tuning

node head는 entity embedding을 받고, pair head는 순서에 무관한 조합을 받는다.

\[
p_h=\sigma(MLP_n(h_h))
\]

\[
q_{h,k}=\sigma\left(MLP_p\left[
h_h+h_k,\ |h_h-h_k|,\ h_h\odot h_k,\ a_{h,k}^{summary}
\right]\right)
\]

pair candidate set `C_G`는 deterministic graph builder가 만든다. synthetic truth pair가 `C_G` 밖에 있으면 이를 쉬운 negative로 숨기지 않고 adjacency-audit false negative로 센다. 학습 negative는 `C_G \ R_wall`에서 drawing 내부 hard negative로 뽑는다. 모든 가능한 handle pair를 negative로 두는 방식은 class imbalance와 메모리를 동시에 왜곡하므로 쓰지 않는다.

\[
L_{ft}=L_{node}^{S}+\lambda_F L_{node}^{F}+\lambda_P L_{pair}^{S}
\]

- 각 BCE weight는 train split prevalence에서만 계산한다.
- S node, S pair, F node loss를 별도 log한다.
- F에는 pair loss를 만들지 않는다.
- CubiCasa(`C`)를 쓰는 arm은 별도 adapter/metric namespace로 유지하고 F로 합치지 않는다.
- silver/AI 판정자는 weight target으로 쓰지 않는다.
- NC source를 사용한 checkpoint는 연구 격리하고 제품 export 대상에서 제외한다.

### 2.6 Calibration과 deterministic topology gate

development가 끝난 뒤 calibration split에서 node logit의 scalar temperature `T_n`만 맞춘다. pair head는 S calibration split에서 별도의 `T_p`를 맞춘다. test에서 threshold나 temperature를 다시 선택하지 않는다.

고정된 10개 equal-width probability bin을 사용하는 제안 설계는 다음과 같다.

\[
REL=\sum_b\frac{n_b}{N}(\bar p_b-\bar y_b)^2,
\qquad
RES=\sum_b\frac{n_b}{N}(\bar y_b-\bar y)^2
\]

bin 수는 문헌 성능 인용이 아니라 본 실험의 사전등록 설계값이다. primary calibration band는 F node prediction의 `REL<=0.03`, `RES>=0.03`이다. S pair calibration은 별도 보고하지만 새 합격선을 사후 추가하지 않는다.

downstream에서는 다음 규칙을 지킨다.

\[
accepted(h,k)=gate_{det}(h,k)\land [q_{h,k}\ge t_p]
\]

GNN은 deterministic gate 밖의 topology를 생성하거나 승인할 수 없다. `p_h`, `q_hk`는 rank/soft evidence와 검토 우선순위를 제공한다. gate가 후보를 누락한 경우 그 사실은 candidate recall에 남고, GNN이 우회해서 “정답”을 만드는 것으로 채점하지 않는다.

### 2.7 실행 의사코드

```text
INPUT
  DWG/SEG-IR graphs, S node+pair truth, F node truth
  frozen family split manifest, frozen graph config

BUILD
  for each root drawing:
      resolve Xref/block family; fail closed on missing reference
      canonicalize units and transforms
      create typed nodes without identifier/name features
      compute occurrence-level spatial events with a spatial index
      collapse events to canonical source handles
      cap proximity/parallel/collinear neighbors by frozen top-k
      audit known S relations and write immutable graph manifest
      shard by connected neighborhood without cutting truth pairs silently

PRETRAIN
  for each train-family shard:
      view_a, view_b = two allowed semantic-preserving transforms
      mask only permitted non-identifier attributes
      h_a, h_b = hetero_encoder(view_a), hetero_encoder(view_b)
      update encoder on L_mask + L_con
      checkpoint at graph-shard boundary

FINE_TUNE
  sample entity neighborhoods and S pair candidates
  compute p_handle and q_pair
  update on separate S-node, S-pair, F-node losses
  log every source contribution; never mix truth namespaces

CALIBRATE
  freeze encoder and heads
  fit T_n on F calibration families and T_p on S calibration families
  freeze thresholds, transforms, and model bundle hash

TEST_ONCE
  open held-out S/F/style-OOD manifests once
  compute paired baseline and P3 metrics on identical universes
  compute family-clustered lift CI, calibration, graph and compute bands
  emit evidence workbook and wsd_eval_p3.json
  never retune or rerun test
```

### 2.8 하이퍼파라미터 공간과 선택 규칙

아래 값은 전부 제안 설계값이며 측정 결과가 아니다.

- cheapest probe 고정값: HGT 3 layer, hidden width 128, 4 attention heads, dropout 0.2, relation top-`k=16`, mask rate 0.35, AdamW learning rate `3e-4`.
- full search: layer `{2,3,4}`, width `{96,128,192}`, heads `{4,8}`, dropout `{0.1,0.2}`, mask rate `{0.2,0.35,0.5}`, contrastive temperature `{0.1,0.2,0.5}`, relation top-k `{8,16,32}`, pair-loss weight `{0.5,1,2}`, learning rate `{1e-4,3e-4,1e-3}`.
- local probe는 위 한 config만 쓰며 HPO를 하지 않는다.
- full search는 DGX가 다시 reachable이고 PR-1/2/3 및 adjacency gate가 통과한 뒤에만 수행한다. 모든 조합의 완전격자가 아니라 사전 고정된 budget 내 successive-halving을 사용한다.
- objective는 F development `AUPRC`가 1순위이고 S node/pair gate 위반, style-OOD 악화, RAM envelope 위반은 feasibility constraint다.
- seed는 screening용 `17` 한 번, 본 실험 robustness용 `{17,29,43}`으로 동결한다. 최종 모델은 세 checkpoint의 logit 평균인 bundle이며, bundle 내 파일 목록과 SHA-256을 하나의 model bundle hash로 고정한다.
- baseline learned model에도 같은 split과 seed 정책을 적용한다. deterministic P1은 seed가 없음을 명시한다.

## 3. 벽 과업 적응 설계

### 3.1 Truth namespace를 섞지 않는 연결표

| 축 | 입력 graph | 허용 truth | 역할 | 금지 사항 |
|---|---|---|---|---|
| S / synthetic | DWG-like entity·block·layer graph | generator의 node membership와 wall-pair relation | graph audit, joint fine-tune, node/pair band | detector 규칙으로 label을 역생성하지 않음 |
| F / FloorPlanCAD | 원 raster에서 mask 비접근 상태로 추출한 line graph | 제3자 wall segmask를 사후 투영한 node label | formal `AUPRC_F`, calibration, style-OOD | mask로 line을 먼저 만들지 않음; pair truth 생성 금지 |
| C / CubiCasa5k | 기존 SEG-IR line graph | Wall 클래스 요소의 모서리 node label | 실행 가능한 외부 sanity/transfer 및 baseline 비교 | F로 이름을 바꾸거나 S pair truth와 합치지 않음 |
| R / 1.dwg·라벨 없는 145장 | full DWG heterogeneous graph | semantic truth 없음 | SSL, adjacency/메모리 stress, drift 관찰 | silver나 Graph IR를 truth로 사용하지 않음 |
| M / metamorphic | 변환 전후 graph | node correspondence와 불변성 계약 | transform consistency gate | 0벽 모델을 semantic PASS로 간주하지 않음 |

### 3.2 CubiCasa SEG-IR 벡터축

CubiCasa5k는 전량 SEG-IR 변환이 끝났고 실패가 없으며, 고정 split은 train 4,200 / val 400 / test 400, wall segment 비율은 약 11.8%다. test는 P3 개발 중 열지 않는다. val 400 안에서 family hash로 development와 calibration subset을 먼저 고정한다. 이 분할은 기존 test 정의를 바꾸지 않는다.

`cubicasa_ir` adapter는 각 segment를 entity node로 만들고 intersection, proximity, parallel, collinearity edge를 계산한다. 원 데이터에 block/layer/reference가 없으면 가짜 block 이름이나 dataset ID를 만들지 않고 해당 node type을 empty로 둔다. 이를 통해 “spatial-relation-only HGT”가 기존 여섯-feature HistGradientBoosting보다 무엇을 추가하는지 빠르게 볼 수 있다.

`cubicasa_ml`의 동일한 six-feature universe에서 다음을 재현한다.

- 기하 탐지기 v1: packet 기준 val `F1=0.2358`.
- HistGradientBoosting: packet 기준 val `F1=0.517`; 다만 formal band는 `AUPRC`이므로 이 F1을 AUPRC로 오인하지 않고 같은 동결 split에서 AUPRC를 새로 산출한다.
- logistic의 packet 기준 val `F1=0.053`은 선형 baseline으로만 남긴다.
- shuffle control은 새 split/파이프라인에서 다시 수행한다. 기존 `AUC=0.375` PASS를 새 결과로 복사하지 않는다.

CubiCasa의 false positive class가 Direction/BoundaryPolygon/Door/Window/DimensionMark였다는 관측을 활용해 class별 error slice를 만들되, class 이름 자체를 GNN feature로 주지 않는다. P3의 기대 이득은 반복 기호 subgraph, 교차 패턴, 주변 정션, 긴 평행 구조의 전체 문맥에서 나온다. 이 slice 개선이 없고 전체 lift만 있다면 size/style shortcut 가능성을 우선 의심한다.

### 3.3 FloorPlanCAD 래스터축과 “line truth”의 정직한 정의

패킷 자산은 FloorPlanCAD raster 5,308장과 wall bbox/segmask이며 vector SVG는 없다. 그러므로 현재 **native CAD handle line truth는 존재하지 않는다**. 이를 숨긴 채 `AUPRC_F`를 계산하면 P3 해소 조건이 무효다.

실행 가능한 F adapter는 다음 순서를 고정한다.

1. 원 floor-plan raster만 읽고, wall mask와 bbox 파일 descriptor를 닫은 상태에서 line/curve candidate를 추출한다.
2. 추출 parameter는 synthetic vector를 rasterize한 별도 calibration set에서만 고정한다.
3. candidate와 graph manifest를 hash한 뒤에만 wall segmask를 열어 line을 label한다.
4. 한 line의 rasterized support 중 wall mask 안에 있는 비율과 boundary-distance를 이용해 positive/negative/ambiguous를 정한다. threshold는 synthetic projection calibration에서 freeze하고 F label을 보며 조정하지 않는다.
5. mask에서 직접 contour를 뽑아 입력 line으로 쓰는 arm은 truth-derived input이므로 금지한다.
6. ambiguous line은 primary metric에서 조용히 버리지 않는다. coverage, ambiguous rate, positive rate를 evidence workbook에 함께 기록하고, 사전등록 projection gate를 통과하지 못하면 `AUPRC_F=undefined`로 둔다.

이 F graph는 entity/spatial relation 중심이며 full DWG block/layer topology를 시험하지 못한다. 따라서 F는 **external node-truth 축**, S는 **full heterogeneous node/relation truth 축**으로 분리한다. F projection gate가 통과하지 못하거나 counsel이 허용하지 않으면 CubiCasa를 F로 몰래 대체하지 않는다. 필요한 경우 test를 열기 전에 resolution contract 자체를 명시적으로 재프리레그해야 하며, 그렇지 않으면 P3 verdict는 OPEN 상태로 남는다.

projection gate는 구현 전에 수치 threshold를 별도 preregistration manifest에 동결한다. 이 패킷에는 그 gate의 정답 threshold가 없으므로 임의 수치를 이미 검증된 기준처럼 쓰지 않는다. 최소한 synthetic known-vector에 대한 candidate coverage, label agreement, ambiguous rate, 그리고 mask 비접근 extraction 보장이 모두 포함되어야 한다.

### 3.4 1.dwg와 라벨 없는 실도면축

1.dwg staged DXF에는 384개 drawing definition이 있고 최대 definition은 412,775 segment다. 이 축은 다음 목적으로만 쓴다.

- recursion/INSERT/world-transform을 포함한 Graph IR stress test.
- production p95 edge 수, shard 크기, peak RAM envelope의 근거 수집.
- 제안에 명시된 라벨 없는 145장 중 train-family 부분의 SSL pretraining.
- cheapest probe에서 family가 겹치지 않는 실무 20장 비라벨 graph 제공.

이 축의 B3 wall-zero drawing rate나 detector↔AI silver 상관은 semantic GNN truth가 아니다. 특히 silver 5기가 약 2개 어휘 family로 갈린 관측과 detector↔silver Pearson `0.2911`을 고려해, silver label은 pretraining/fine-tuning target에서 완전히 제외한다. text/layer 이름을 지운 primary arm과 구조 feature까지 제거한 ablation을 같이 보고한다.

### 3.5 P3가 GBDT 이후에 추가로 가져와야 할 것

HistGradientBoosting의 여섯 feature는 각 segment 주변의 요약 통계는 볼 수 있지만, 다음을 직접 표현하지 못한다.

- 어느 block definition이 여러 reference로 반복되는지.
- 두세 hop 떨어진 junction/parallel chain이 방 경계로 이어지는지.
- 같은 후보 간격을 가진 구조가 door/window symbol subgraph 안에 있는지, 긴 wall chain 안에 있는지.
- entity-node 판단과 wall-pair 관계가 서로 일관되는지.
- 라벨 없는 실제 도면의 구조적 분포를 transform-invariant representation으로 먼저 학습했는지.

이 항목 중 어느 것도 name-blind, family-held-out ablation에서 확인되지 않으면 P3의 복잡도는 정당화되지 않는다. 단순히 recall을 올리고 precision을 잃는 것은 기존 기하 탐지기 패턴의 반복이므로 합격이 아니다.

## 4. 데이터·컴퓨트 요구

### 4.1 데이터 readiness

| 데이터 | 현재 패킷 상태 | P3 사용 조건 |
|---|---|---|
| synthetic wall graph | 패널상 실제 wall generator 부재, 기존 synthetic fidelity B1 FAIL (`KS 0.5792`, `TV 0.265`) | PR-1 generator 구축, CL-C/WSD-EVAL-v1 truth contract, T2 fidelity gate PASS 전에는 full fine-tune 금지 |
| FloorPlanCAD | raster 5,308장 + bbox/segmask, vector SVG 없음 | PR-3 counsel 서면 확인 + mask 비접근 line extraction/projection gate PASS |
| CubiCasa5k | SEG-IR 5,000장, 변환 실패 0, 고정 train/val/test | counsel 범위 확인, 고정 split 준수, C namespace로만 사용 |
| 실도면 | 1.dwg 384 definitions, 최대 412,775 segments; 라벨 없는 145장 제안 | family grouping, ID/name 제거, held-out family를 SSL에서 제외 |
| silver | 5 판정자지만 약 2 어휘 family | 모델 weight에 사용 금지, proxy-independence audit용 비교만 허용 |

PR-1/PR-2/PR-3은 선택적 개선이 아니라 학습 시작 전 gate다. 특히 synthetic generator가 detector의 평행 이중선 규칙으로 label을 만들면 P3가 그 규칙을 복원해도 semantic 성능으로 인정할 수 없다.

### 4.2 로컬 RTX 5070 Ti 16GB / RAM 64GB 계획

로컬에서는 cheapest probe와 graph audit만 확실한 범위로 잡는다.

- graph extraction과 spatial index는 CPU에서 수행하고 Arrow/Parquet형 shard로 저장한다.
- RAM hard band는 패킷대로 peak `<=48GB`다. 64GB 전체를 목표로 잡지 않고 OS/worker 여유를 남긴다.
- GPU에는 full graph를 올리지 않는다. typed neighbor sampling, mixed precision, gradient accumulation, activation checkpointing을 사용한다.
- batch 크기는 고정 node 수가 아니라 `(sampled nodes + sampled edges)` token cap으로 정한다. training-family dry run에서 GPU peak가 16GB 물리 한계를 넘지 않는 최대 cap을 정하고 freeze한다.
- 최대 definition을 한 shard에 강제로 넣지 않는다. root handle과 truth pair가 어느 shard에 배치됐는지 mapping을 보존한 neighborhood shard를 사용한다.
- shard boundary로 잘린 positive pair에는 두 endpoint의 필요한 context를 halo로 복제하되, metric에서는 source handle 하나로 deduplicate한다.
- OOM 발생 시 조용히 작은 그래프만 남기지 않는다. offending graph, node/edge count, relation별 fanout을 failure sheet에 기록한다.
- local probe는 synthetic 1,000 block과 실무 20장 비라벨 graph에 대해 no-pretrain/pretrain 각 1회만 수행한다. 이는 screening이지 최종 CI 근거가 아니다.

### 4.3 DGX Spark 계획과 현재 blocker

full-corpus pretraining과 hyperparameter search는 패킷대로 DGX Spark의 vLLM 비사용 시간대에만 배치한다. 현재 DGX가 unreachable이므로 다음을 명확히 분리한다.

- **지금 로컬에서 가능한 것:** schema, graph builder, family splitter, adjacency audit, smallest 3-layer probe, evidence writer dry run.
- **DGX 복구 후 가능한 것:** train-family 전체 145장 SSL, multi-seed ablation, successive-halving HPO, 최종 three-seed model bundle.
- DGX job은 graph shard 단위 checkpoint를 남기고, preemption 뒤 같은 shard/optimizer step에서 재개한다.
- vLLM/Ornith process와 GPU 자원을 공유하지 않는다. P3는 language-model serving을 요구하지 않는다.
- DGX에서 만든 checkpoint도 로컬에서 content hash, config hash, sample inference parity를 확인해야 freeze할 수 있다.

DGX 불통 상태에서 local 작은 probe 결과를 full-corpus 결과로 외삽하지 않는다. DGX가 끝내 복구되지 않으면 P3는 cheapest-probe 수준에서 멈추며 resolution test를 열지 않는다.

### 4.4 저장·재현성·권리 격리

각 graph shard는 node table, edge table, truth sidecar, source/license tag, canonical graph-config hash를 가진다. hash는 Git에 의존하지 않고 파일 내용 SHA-256으로 계산한다. 모델 artifact에는 다음 provenance가 필요하다.

- graph manifest hash와 split manifest hash.
- encoder/head/calibration config hash.
- seed와 checkpoint shard sequence.
- S/F/C/R source별 sample count 및 loss contribution.
- NC/cleared/research-only license tag.

NC source가 하나라도 loss에 기여한 checkpoint와 그 descendant는 `research_nc` registry에 두고 product export denylist에 넣는다. 제품 후보는 counsel이 명시적으로 허용한 data 또는 synthetic-only clean-room run으로 다시 학습해야 하며, NC weight의 fine-tune descendant를 “깨끗한 모델”로 간주하지 않는다.

### 4.5 계획 예산

다음은 실측이 아닌 공학 계획 추정치다.

- graph schema/builder/audit: 중간~대형 작업, 약 1–2 engineer-weeks.
- adapter·SSL·joint head·calibration·evidence pipeline: 약 1–2 engineer-weeks.
- local cheapest probe: graph가 준비된 뒤 약 1 GPU-day 이내 목표.
- DGX full study: connectivity와 queue가 확보된 뒤 수 GPU-day budget으로 사전 고정.

일정의 critical path는 model coding보다 PR-1 truth generator, F projection, family split, adjacency recall, counsel이다.

## 5. 구현 계획

### 5.1 제안 파일 골격

실제 repository root와 기존 함수 signature는 이 자기완결 패킷에 없으므로 아래는 **논리적 골격**이다. 구현자는 존재를 가정하지 말고 먼저 실제 경로/API를 읽은 뒤 adapter만 맞춘다.

```text
<repo>/
  p3/
    config/
      graph_schema.yaml          # node/edge type, tolerance, fanout, feature allowlist
      probe.yaml                 # 고정 3-layer local probe
      full_search.yaml           # DGX search space와 budget
      resolution_bands.yaml      # test 전 봉인할 predicate
    graph/
      schema.py                  # typed node/edge schema와 validation
      canonicalize.py            # unit/transform/curve normalization
      build_dwg_graph.py         # block/Xref recursion과 spatial relations
      occurrence_pool.py         # occurrence event -> source handle aggregation
      shard.py                   # neighborhood/halo shard
      audit_adjacency.py         # known relation recall, edge envelope, unresolved refs
    data/
      family_split.py            # Xref/block/template family grouping
      manifest.py                # canonical JSON + SHA-256
      synthetic_adapter.py       # S node/pair truth
      floorplancad_adapter.py     # mask-blind extraction 후 label projection
      cubicasa_adapter.py        # SEG-IR adapter
      real_unlabeled_adapter.py  # 145장/1.dwg SSL input
    model/
      hetero_encoder.py          # HGT/R-GCN ablation
      ssl_heads.py               # masked reconstruction + contrastive projection
      task_heads.py              # node + symmetric pair heads
      losses.py                  # source-separated weighted losses
    train/
      pretrain.py
      finetune.py
      sampler.py
      checkpoint.py
    eval/
      metrics.py                 # AUPRC/F1/paired family bootstrap
      calibration.py             # temperature, REL, RES
      ood.py                     # style slices and drop
      resolution.py              # band predicates와 wsd_eval_p3.json
      evidence_writer.py         # evidence_grid bridge
    tests/
      test_no_identifier_features.py
      test_family_disjoint.py
      test_transform_equivariance.py
      test_block_world_transform.py
      test_relation_recall.py
      test_pair_universe.py
      test_shard_dedup.py
      test_calibration_freeze.py
      test_resolution_schema.py
```

### 5.2 기존 도구 접속점

1. **`fast_score`**
   - 최종 wall 판정을 teacher label로 쓰지 않는다.
   - parallel/thickness/junction 같은 원시 evidence channel을 entity feature adapter로 받을 수 있다.
   - raw geometry-only arm, raw channel arm, channel+GNN arm을 분리해 GNN의 독립 기여를 확인한다.

2. **`cubicasa_ir`**
   - 기존 SEG-IR line과 Wall truth mapping을 source-of-record로 사용한다.
   - segment key를 model feature에서 제거하고 result sidecar에만 유지한다.
   - train/val/test split을 새로 섞지 않는다.

3. **`cubicasa_ml`**
   - six-feature HistGradientBoosting과 logistic baseline을 동일 node universe에서 재실행한다.
   - P3와 같은 exclusion, family grouping, metric implementation을 사용한다.
   - packet의 기존 F1을 복사해 formal AUPRC baseline으로 쓰지 않는다.

4. **`evidence_grid`**
   - 기존 writer API를 확인한 뒤 아래 workbook schema를 채운다.
   - workbook이 없으면 최종 `wsd_eval_p3.json`을 PASS로 만들 수 없다.

### 5.3 Evidence workbook 계약

필수 sheet는 다음과 같다.

- `manifest`: data/config/split/model/calibration SHA-256, license tag, test access count.
- `graph_audit`: graph별 node/edge 수, relation별 recall, unresolved Xref, cap drop, build RAM/time.
- `family_split`: family ID의 salted digest, fold, Xref/template membership, cross-fold collision count.
- `truth_provenance`: S/F/C별 truth origin과 금지 proxy, projection coverage/ambiguity.
- `baselines`: P1/P2/fast_score/logistic/HGBDT의 동일-universe metric.
- `ssl_ablation`: no-pretrain/mask/contrastive/both와 seed.
- `node_metrics`: S와 F를 분리한 AUPRC/F1/P/R 및 drawing macro.
- `pair_metrics`: S candidate recall, pair F1/P/R; F 행은 `not_applicable`.
- `ood`: style cluster, IID/OOD AUPRC, drop.
- `calibration`: pre/post temperature Brier, REL, RES, bin count.
- `leakage_controls`: name/layer/text/identifier ablation, template dedupe, label shuffle.
- `compute`: CPU RAM, GPU memory, sampled node/edge count, shard/checkpoint 상태.
- `failures`: OOM, invalid graph, ambiguous projection, skipped/blocked reason. 빈 sheet로 숨기지 않는다.

모든 metric row는 `truth_namespace`, `split`, `family_count`, `drawing_count`, `entity_count`, `seed_or_bundle`, `model_hash`, `graph_hash`를 가진다. 큰 drawing이 pooled metric을 지배하지 않도록 pooled handle metric과 drawing-macro metric을 같이 둔다.

### 5.4 `wsd_eval_p3.json` 최소 schema

```json
{
  "seat_id": "calibration_P3",
  "claim": "P3 beats the best frozen non-GNN baseline and passes all gates",
  "forecast": null,
  "abstain_flag": "empty_reference_class",
  "reference_class": {"id": "RC-WALL-ZL", "n": 0, "n_min": 5},
  "graph_manifest_sha256": "...",
  "split_manifest_sha256": "...",
  "model_bundle_sha256": "...",
  "calibration_manifest_sha256": "...",
  "test_access_count": 1,
  "metrics": {
    "F_node_auprc": null,
    "best_non_gnn_F_node_auprc": null,
    "lift": null,
    "lift_ci_low": null,
    "S_node_f1": null,
    "S_pair_f1": null,
    "style_ood_auprc_drop": null,
    "REL": null,
    "RES": null,
    "known_relation_recall": null,
    "peak_ram_gb": null
  },
  "bands": [],
  "resolution_criterion": "P3_lift_CI_low>0 and all required bands pass",
  "resolution_verdict": "open|true|false|invalid"
}
```

`null`은 실패한 metric을 0으로 바꾸라는 뜻이 아니라 미측정/invalid를 명시하라는 뜻이다. F projection이 invalid이면 verdict를 성능 FAIL로 꾸미지 않고 `invalid` 또는 아직 trigger 전이면 `open`으로 둔다.

### 5.5 개발 순서와 검증

1. schema/feature allowlist와 family split부터 구현한다.
2. synthetic known relation을 갖는 unit graph로 transform과 adjacency를 검증한다.
3. 1.dwg stress graph를 만들고 edge/RAM envelope를 봉인한다.
4. CubiCasa adapter와 HGBDT baseline을 동일 universe에서 재현한다.
5. FloorPlanCAD projection harness를 mask-blind 순서로 검증한다.
6. local cheapest probe를 수행한다.
7. readiness gate가 모두 참일 때만 DGX SSL/HPO를 수행한다.
8. evidence workbook dry run과 JSON schema validation 후 model bundle을 freeze한다.
9. 마지막으로 test를 한 번만 연다.

필수 automated test는 identifier/name feature 부재, family 교집합 0, transform correspondence, block world-transform, relation recall, pair candidate 정의, shard dedup, calibration/test 분리, JSON predicate 재계산이다. metric 값은 workbook에서 JSON으로 손복사하지 않고 동일 immutable result table에서 두 형식으로 직렬화한다.

## 6. 실험 셀 정의

### 6.1 공통 split·metric·CI 규칙

- Xref 연결 family, canonical block family, synthetic template와 모든 parameter variant는 같은 fold다.
- near-duplicate geometry fingerprint 충돌도 같은 fold로 합친다.
- handle, 순번, filename, block/layer/text name은 feature에 없다.
- val은 tuning 가능하되 test는 최종 한 번만 접근한다.
- F formal primary는 pooled per-handle `AUPRC_F`; drawing-macro AUPRC는 보조다.
- S formal metric은 per-handle node F1과 candidate-universe pair F1이다.
- `B*`는 동일 F universe에서 동결된 `max(P1, P2, HistGradientBoosting, 기타 사전등록 비-GNN baseline)`이다. packet의 F1과 새 AUPRC를 서로 비교하지 않는다.
- lift는 `AUPRC_F(P3)-AUPRC_F(B*)`다.
- CI는 동일 drawing/family를 paired cluster로 재표본하는 고정 95% stratified bootstrap을 사용한다. 제안 설계값으로 10,000 replicate와 고정 bootstrap seed를 manifest에 봉인한다. 개별 line을 독립 표본처럼 bootstrap하지 않는다.
- style cluster는 label을 보기 전에 geometry/block 통계로 train에서 정의하고 family 전체를 한 cluster/fold에 둔다.
- formal band는 패킷대로 `AUPRC_F>=B*+0.05`, S node `F1>=0.92`, S pair `F1>=0.80`, style-OOD AUPRC drop `<=0.10`, `REL<=0.03`, `RES>=0.03`, peak RAM `<=48GB`, `P3_lift_CI_low>0`이다.
- 별도 hard gate는 known synthetic relation recall `>=0.98`과 production p95 edge/memory envelope 준수다.

### Cell E0 — 선결조건 및 truth readiness

- **가설:** P3가 학습하기 전에 S/F truth와 권리, proxy 독립성이 유효한 상태로 고정될 수 있다.
- **입력:** PR-1 wall generator, CL-C/WSD-EVAL-v1 contract, PR-2 동일-def proxy audit, PR-3 counsel 문서, P1/P2 baseline manifest.
- **지표:** T2 fidelity status, truth provenance completeness, proxy disagreement matrix completeness, counsel status, family collision count, baseline availability.
- **제안 합격선:** 프로그램이 별도로 봉인한 T2 fidelity gate가 PASS이고, `family_collision=0`, counsel이 F/C 학습과 derived weight 범위를 서면 허용하며, proxy audit와 P1/P2 artifact가 존재한다. 패킷에 없는 fidelity 수치를 이 문서가 임의로 “통과선”으로 만들지 않는다.
- **킬 조건:** generator label이 detector prior에서 파생됨, wall truth가 실제로 없음, counsel이 학습/derived weight를 허용하지 않음, proxy 독립성 감사를 수행할 수 없음. 이 경우 full P3를 중단한다.
- **예산:** 주로 local CPU/audit 및 외부 counsel 대기. 학습 GPU 0.
- **seed 계획:** 해당 없음. 모든 manifest는 content hash로 결정적이어야 한다.

### Cell E1 — Graph IR adjacency·폭증 감사

- **가설:** typed builder가 known synthetic containment/instancing/intersection/proximity/parallel/collinearity를 거의 완전하게 회수하면서 production graph envelope 안에 머문다.
- **입력:** train-family synthetic relation truth, held-out synthetic audit families, 1.dwg stress definitions.
- **지표:** relation type별 candidate recall, micro recall, unresolved Xref, edge/node ratio, node별 fanout quantile, build peak RAM, maximum-shard size, p95 envelope 초과율.
- **제안 합격선:** support가 있는 모든 required relation type과 micro known-relation recall이 각각 `>=0.98`; peak RAM `<=48GB`; frozen production p95 envelope 안; unresolved required reference 0.
- **킬 조건:** recall `<0.98`, relation cap을 풀어야만 recall이 나와 edge/RAM envelope를 넘음, 최대 graph를 shard해도 truth pair/context를 보존하지 못함.
- **예산:** local CPU/RAM 중심, 약 1일 목표(계획값). GPU 불필요.
- **seed 계획:** builder는 deterministic. 동률 top-k tie-break는 geometry hash를 사용하고 handle/order를 사용하지 않는다.

### Cell E2 — Cheapest 3-layer probe

- **가설:** 작은 동일 architecture에서 SSL initialization이 no-pretrain보다 낫고 P2 대비 상승 신호를 보인다.
- **입력:** synthetic 1,000 block의 node/pair truth, family-disjoint 실무 20장 비라벨 graph. generator가 준비되지 않으면 이 cell은 BLOCKED다.
- **팔:** `(A) no pretrain -> joint fine-tune`, `(B) masked+contrastive pretrain -> 동일 joint fine-tune`, 그리고 동결 P2 비교.
- **지표:** S development node F1, pair F1, AUPRC, P2 대비 delta, peak GPU/RAM, graph recall. 이 cell에서 test와 F formal held-out은 열지 않는다.
- **제안 합격선:** B가 A와 P2 모두보다 development AUPRC/F1에서 방향성 양의 이득을 보이고 compute envelope를 지킨다. 단일 seed이므로 formal claim이나 CI PASS로 사용하지 않는다.
- **킬/중단 조건:** adjacency gate 실패, 최소 sampled config도 16GB에서 지속 OOM, B가 A/P2보다 모두 나쁘고 오류 분석에서도 구현 결함이 없음. 후자의 경우 DGX escalation을 중단하되 formal claim은 “단일 seed로 해결”하지 않는다.
- **예산:** RTX 5070 Ti, pretrain 유/무 각 1회, 약 1 GPU-day 이내 목표(계획값).
- **seed 계획:** 패킷의 “각각 한 번”을 지켜 seed `17` 한 번.

### Cell E3 — 비-GNN baseline·leakage·shuffle 동결

- **가설:** P3 lift를 비교할 동일 truth universe의 강한 비-GNN baseline이 재현되고, identifier/family leakage가 제거된다.
- **팔:** fast_score, logistic, six-feature HistGradientBoosting, P1, P2; primary structural GNN; 이름/레이어/text content를 의도적으로 연 diagnostic arm; label shuffle arm.
- **지표:** 동일 F/C development AUPRC/F1, S metric, family collision, source classifier accuracy, leaky-vs-masked delta, permutation-null 위치.
- **제안 합격선:** 모든 baseline이 동일 exclusion과 split hash를 사용하고 `B*`가 freeze됨; family collision 0; primary feature allowlist에 식별자/이름 0; shuffle 결과가 사전 생성한 permutation null의 중앙 95% 범위 안.
- **킬 조건:** 이름을 가리면 baseline/P3 universe가 달라짐, near-duplicate/template가 fold를 가로지름, shuffle가 null 밖의 유의한 신호를 반복해서 보임, P1/P2를 동일 metric으로 실행할 수 없음. 이때 test 진입 금지다.
- **예산:** CPU baseline + local GPU diagnostic, 약 1–2일 목표(계획값).
- **seed 계획:** learned model `{17,29,43}`; permutation seed 목록은 label을 보기 전에 manifest에 봉인한다.

### Cell E4 — Self-supervised ablation과 제한 HPO

- **가설:** label 없는 train-family graph에서 배운 masked/transform representation이 family-held-out node 과업으로 전이되며, 단순 random initialization 이상의 이득을 낸다.
- **팔:** no-pretrain, mask-only, contrastive-only, mask+contrastive; HGT와 R-GCN architecture check.
- **지표:** F/C development AUPRC, S node/pair F1, family-bootstrap lift, seed variance, transform consistency, representation collapse/oversmoothing 진단.
- **제안 합격선:** mask+contrastive가 no-pretrain보다 seed-aggregate development lift의 CI 하한이 양수이고 S gate를 악화시키지 않음. transform consistency는 올라가되 all-node embedding variance가 붕괴하지 않아야 한다.
- **킬 조건:** family dedupe 후 SSL lift CI 하한 `<=0`, shuffled/renamed identifiers가 lift를 설명함, depth가 늘수록 embeddings가 붕괴하고 shallow model도 회복하지 못함. supervised HGT만 이기고 SSL이 기여하지 않으면 **self-supervised P3라는 제안은 실패**로 기록하고 별도 제안으로 재프리레그한다.
- **예산:** full-corpus pretraining/HPO이므로 DGX 비-vLLM 시간대만 사용. DGX unreachable이면 BLOCKED.
- **seed 계획:** screening 후 `{17,29,43}`. HPO cell마다 seed 하나로 줄이는 경우 최종 후보는 세 seed 전부 재학습한다.

### Cell E5 — S node/relation joint 학습과 F/C 전이

- **가설:** pair supervision이 node membership을 안정화하고, S에서 학습한 구조가 F/C node truth로 전이된다.
- **팔:** node-only, pair-only diagnostic, joint node+pair; train source `{S only, F/C node only, S+F, S+C}`를 분리한다. silver arm은 없다.
- **지표:** S node F1, S candidate recall/pair F1, F/C AUPRC, source별 loss, cross-source train×eval matrix, node/pair prediction consistency.
- **제안 합격선:** development readiness에서 S node `F1>=0.92`, S pair `F1>=0.80`; joint가 node-only보다 F development AUPRC를 해치지 않고 relation error를 줄임; truth source별 metric을 별도 보고.
- **킬 조건:** pair candidate recall은 높지만 pair head가 band에 못 미침, pair loss가 node 성능을 악화, S 대각 성능만 높고 F/C 비대각 lift가 소멸, F projection invalid.
- **예산:** local small run 후 DGX full multi-seed, 약 1–2 GPU-day 목표(계획값).
- **seed 계획:** `{17,29,43}`, 최종은 고정 logit-mean bundle.

### Cell E6 — OOD·calibration·compute freeze rehearsal

- **가설:** P3의 lift가 style family 밖에서도 유지되고, 확률과 compute가 production gate를 만족한다.
- **입력:** development/style-OOD/calibration family만 사용하며 final test는 닫아 둔다.
- **지표:** IID와 style-OOD AUPRC 및 drop, temperature 전후 REL/RES, S node/pair band, peak CPU RAM/GPU memory, p95 edge envelope, family-bootstrap lift CI, name/layer/text ablation.
- **제안 합격선:** development rehearsal에서 formal band 전부 충족: lift `>=0.05`, lift CI low `>0`, style drop `<=0.10`, `REL<=0.03`, `RES>=0.03`, S node/pair band, graph recall, RAM band.
- **킬 조건:** best classical 대비 lift CI 하한 `<=0`, style drop 초과, calibration band 실패, production p95에서 edge/memory envelope 초과. calibration 실패를 threshold 재탐색으로 덮지 않는다.
- **예산:** local evaluation + DGX checkpoint inference, 약 1일 목표(계획값).
- **seed 계획:** frozen three-model bundle; calibration은 별도 seed 없이 deterministic optimizer와 manifest로 고정.

### Cell E7 — Frozen held-out 단발 해소

- **가설:** 모든 pretest gate를 통과한 P3가 실제 frozen held-out에서 전체 resolution contract를 만족한다.
- **진입 조건:** E0–E6 PASS, graph/split/model/calibration/baseline/evidence schema hash 동결, test access counter 0.
- **절차:** S held-out, F held-out, style-OOD held-out을 한 job manifest에서 한 번만 열고 P3와 `B*`를 같은 handle universe에서 paired 평가한다.
- **최종 합격선:** `AUPRC_F>=B*+0.05`; S node `F1>=0.92`; S pair `F1>=0.80`; style-OOD drop `<=0.10`; `REL<=0.03`; `RES>=0.03`; known-relation recall `>=0.98`; peak RAM `<=48GB`; production p95 envelope 준수; `P3_lift_CI_low>0`. 모두 AND다.
- **킬 조건:** 하나라도 false, model/manifest hash 불일치, test access count가 1보다 큼, evidence workbook 누락. 결과를 보고 threshold나 graph를 바꿔 재실행하지 않는다.
- **예산:** frozen inference 1회와 paired bootstrap. 추가 tuning budget 0.
- **seed 계획:** E6에서 봉인한 model bundle과 bootstrap seed만 사용.

### 6.2 Sentinel과 실패 기록

0벽 graph와 전벽 graph를 S에 포함한다. 0벽에서는 false positive가, 전벽에서는 recall collapse가 직접 드러나야 한다. metamorphic 위반율만 낮은 “항상 0벽” 모델은 PASS가 아니다. graph construction 실패, projection ambiguity, OOM, missing Xref, license block은 표본에서 삭제하지 않고 denominator와 failure sheet에 남긴다.

## 7. Red team 티켓 응답

패킷에는 T8–T33의 전체 원문이 없으므로 번호를 추측해 폐쇄하지 않는다. 아래는 패널 보고서가 P3/CL-F 또는 P3의 직접 dependency에 명시적으로 연결한 티켓과 프로그램급 티켓만 다룬다.

### T1 — truth proxy 독립성 (`severity 0.75`)

- **입장:** 수용, hard prerequisite.
- **위험:** S/F/C/metamorphic/silver가 모두 평행 이중선 prior를 공유하면 cross-source 일치가 독립 확증이 아니다.
- **해소:** 동일 definition/line universe에서 S/F/C/silver/metamorphic의 가능한 label·score를 맞추고 3원 불일치 패턴, source별 오류 상관, train-source×eval-source matrix를 만든다. Graph IR/SSL target은 truth 열에서 제외한다.
- **폐쇄 조건:** PR-2 artifact와 evidence sheet가 존재하고, 특정 proxy 하나를 제거해도 P3 lift가 유지되는 leave-one-source-out 결과가 있어야 한다. 그 전에는 OPEN이다.

### T2 — wall synthetic generator 부재와 fidelity

- **입장:** 수용, P3 fine-tune 차단.
- **위험:** 패널은 `synthetic_truth.py`가 dimension 전용이고 wall code가 없다고 지적했다. 현재 synthetic B1도 `KS 0.5792`, `TV 0.265`로 FAIL이며 LINE/LWPOLYLINE/INSERT만 있어 실도면의 SPLINE/ARC/HATCH 혼재를 반영하지 못한다.
- **해소:** PR-1에서 entity와 wall-pair truth를 직접 내는 generator를 만들고, template lineage를 manifest에 넣고, divergent-20 현상에 대한 CL-C/T2 fidelity gate를 통과시킨다. detector score로 truth를 만들지 않는다.
- **폐쇄 조건:** frozen generator hash, truth schema, lineage split, fidelity PASS. 그 전에는 synthetic 1,000-block probe도 BLOCKED다.

### T3/T4 — E1 법의학·정렬/나열 artifact

- **입장:** P3의 직접 성능 티켓은 아니지만 sample-selection dependency로 수용.
- **위험:** divergent/top drawing 선택 자체가 정렬-key나 나열 지시 artifact면 P3의 “실무 20장” probe가 편향된다.
- **해소:** CL-A가 만든 재계산 artifact를 사용해 20장을 고르고, model feature에는 E1/silver ranking을 넣지 않는다.
- **폐쇄 조건:** CL-A selection manifest가 없으면 실무 20장 결과를 대표성 근거로 쓰지 않는다.

### T5 — FloorPlanCAD/CubiCasa 권리와 NC weight

- **입장:** 수용, 외부 truth arm hard prerequisite.
- **위험:** label뿐 아니라 원 도면, 변환물, derived weight 권리가 미해결이다.
- **해소:** counsel이 연구학습, artifact 보존, weight 배포, 제품 혼입 가능 범위를 source별로 서면 확인한다. NC arm은 별도 registry/checkpoint/cache로 격리하고 product export denylist를 둔다.
- **폐쇄 조건:** 서면 scope와 machine-readable license tag. 허가가 연구 전용이면 연구 평가는 가능해도 제품 checkpoint는 별도 clean run 전까지 금지한다.

### T6 — 평가 단위 혼동

- **입장:** 수용.
- **위험:** node 분류와 wall set assembly를 한 score로 섞으면 GNN이 다른 과업을 푼다.
- **해소:** primary unit은 source handle의 `wall_member(h)`, secondary는 S candidate pair의 unordered relation이다. downstream set assembly/topology gate 결과는 별도 산출물이며 node/pair band와 섞지 않는다.
- **폐쇄 조건:** truth schema, workbook, JSON 모두 node/pair/set namespace를 분리한다.

### T7 — 0벽 모델 sentinel

- **입장:** 수용.
- **위험:** metamorphic violation만 보면 항상 0을 내는 모델이 완벽해 보인다.
- **해소:** 0벽/전벽 sentinel, positive recall floor, class별 confusion을 E1/E5/E6에 의무화한다.
- **폐쇄 조건:** sentinel 결과가 workbook에 존재하고 formal F1/AUPRC gate와 함께 판정된다.

### T10/T23 — Graph IR adjacency 완전성

- **입장:** 수용, P3의 핵심 kill gate.
- **위험:** missing INSERT/world transform, proximity cap, curve flattening이 진짜 relation을 누락하거나 edge를 폭증시킨다.
- **해소:** relation type별 synthetic oracle audit, unresolved-Xref fail-closed, occurrence-level event 기록, cap-drop accounting, production p95 stress test를 수행한다.
- **폐쇄 조건:** support가 있는 각 relation recall과 micro recall `>=0.98`, RAM/edge envelope PASS. 하나라도 실패하면 GNN 경로를 중단한다.

### T17 — truth-source 교차요인

- **입장:** 수용.
- **위험:** S에서만 잘하고 F/C로 전이하지 못하는 synthetic topology shortcut.
- **해소:** Cell E5의 train `{S,F,C}` × eval `{S,F,C,M}` matrix를 source namespace별로 보고한다. silver는 train에서 제외하고 audit 열로만 둔다.
- **폐쇄 조건:** 비대각 전이와 leave-one-source-out 결과가 evidence에 있어야 한다. 대각만 높으면 P3 claim은 지지되지 않는다.

### T22 — P1/P2 선행 baseline

- **입장:** 수용, final test 차단 조건.
- **위험:** 약한 baseline 대비 lift는 Occam 사다리를 위반한다.
- **해소:** P1, P2, six-feature HistGradientBoosting, fast_score를 동일 F handle universe와 AUPRC implementation으로 freeze하고 최댓값 `B*`를 사용한다.
- **폐쇄 조건:** baseline hash와 metric row가 없으면 E7에 진입하지 않는다.

### T24 — raster-to-line 역투영 하네스(인접 CL-G에서 상속)

- **입장:** FloorPlanCAD F arm을 쓰는 순간 P3에도 적용되는 것으로 수용.
- **위험:** wall mask로 입력 line을 생성하거나 잘못 투영하면 label leakage/CRS 오류가 생긴다.
- **해소:** mask descriptor를 닫은 상태의 extraction, synthetic known-vector projection calibration, graph hash 후 label join, coverage/ambiguity 보고를 강제한다.
- **폐쇄 조건:** projection prereg gate PASS. 불통과 시 `AUPRC_F`는 undefined이며 CubiCasa로 몰래 대체하지 않는다.

### 이름·layer mask-ablation 의무(패널 CL-F 조건)

- **입장:** 수용. 패킷은 이 의무의 개별 ticket 번호를 확정해 주지 않으므로 번호를 만들지 않는다.
- **해소:** primary arm에서 block/layer/text 이름을 제거하고, structural-only, layer-structure-off, text-anchor-off, deliberately-leaky diagnostic을 비교한다. leaky arm은 승자 선정이나 제품 weight에 쓰지 않는다.

### Seed confounding 지적(패널의 T15 맥락)

- **입장:** 직접 P3 번호로 지정되지는 않았지만 적용한다.
- **해소:** cheapest probe는 명시적으로 단일 seed screening, full 후보는 세 seed, HPO 선택과 seed robustness를 분리한다. 최종 bundle rule은 test 전에 봉인한다.

### T34 — 인용 experiment status

- **입장:** OPEN 수용.
- **위험:** 관련 citation이 실제 프로그램 실험을 대신하는 것처럼 보일 수 있다.
- **해소:** 본 문서의 논문명은 mechanism lineage일 뿐 `experiment_executed` 증거가 아니다. 웹 검색을 사용하지 않았고 수치 성능을 문헌에서 가져오지 않았다. 실제 구현 전 bibliography/license verification table을 별도 evidence에 만들고, 프로그램 결과는 오직 E0–E7 artifact로 판정한다.

## 8. 인접 제안과의 관계 및 사망 조건

### 8.1 병합 가능한 공통 기반

- **CL-C / WSD-EVAL-v1:** S/F/M truth namespace, per-handle 평가, hidden mutation family, split/hash 계약을 공유한다.
- **CL-D metamorphic:** rigid/reflection/unit/layer-rename transform을 SSL view와 inference audit 양쪽에서 공유한다. 다만 metamorphic correspondence는 semantic truth가 아니다.
- **CL-E truth-source 교차요인:** P3의 S/F/C transfer matrix와 proxy-independence 분석을 공통 evidence table로 병합한다.
- **P1/CL-B deterministic coverage:** Graph IR canonicalization, INSERT world transform, unit anchoring, deterministic topology gate를 공유한다. P3는 이 gate 위에서 rank/soft evidence만 제공한다.
- **P2/CL-F classical ladder:** fast_score, logistic, HistGradientBoosting, PU/고전 ML과 같은 split·feature provenance·AUPRC evaluator를 공유한다.
- **CL-K anti-silver:** P3 primary에는 silver weight가 없으므로 gate-only/anti-silver 통제 원칙과 양립한다.
- **evidence_grid/cubicasa_ir/cubicasa_ml:** data universe와 workbook을 공유해 수치 손복사와 evaluator drift를 막는다.

### 8.2 차별점

P1은 규칙과 topology gate를 완성하고, P2는 hand-engineered row feature의 비선형 결합을 학습한다. P3만의 추가 주장은 다음 세 가지의 결합이다.

1. block definition/reference/layer/text-anchor까지 포함한 typed multi-hop context.
2. label 없는 실제 graph의 masked/transform self-supervision.
3. node wall membership과 wall-pair relation의 joint head.

이 셋 중 self-supervision 또는 heterogeneous context가 ablation에서 기여하지 않으면 “P3라서 이겼다”는 설명은 성립하지 않는다. supervised MLP/GBDT가 같은 성능이면 더 단순한 방법을 채택해야 한다.

### 8.3 P3가 죽어야 하는 조건

다음은 개선 과제가 아니라 stop rule이다.

1. PR-1 wall generator 또는 T2 fidelity gate를 통과하지 못한다.
2. PR-2 proxy-independence audit 뒤 lift가 한 proxy의 공유 prior로 설명된다.
3. counsel이 F/C training 또는 derived weight를 허용하지 않고 대체 가능한 사전등록 truth가 없다.
4. known synthetic relation recall이 `0.98` 미만이다.
5. proximity/parallel edge를 충분히 보존하면 production p95 edge 수나 peak RAM `48GB` envelope를 넘고, cap을 적용하면 relation recall이 깨진다.
6. best frozen non-GNN baseline 대비 paired lift CI 하한이 0 이하이다.
7. formal `AUPRC_F` lift `0.05`, S node `F1=0.92`, S pair `F1=0.80`, style-OOD drop `0.10`, `REL/RES` band 중 하나라도 final에서 실패한다.
8. family/template dedupe 또는 name/layer/text masking 뒤 lift가 사라진다.
9. no-pretrain과 mask/contrastive/both ablation에서 self-supervision 기여가 재현되지 않는다.
10. FloorPlanCAD projection이 mask 비접근·coverage gate를 통과하지 못해 `AUPRC_F` 자체가 정의되지 않는다.
11. DGX 불통 때문에 full-corpus/multi-seed study를 수행할 수 없고 local probe만 남는다. 이 경우 과장된 FAIL이 아니라 BLOCKED/OPEN으로 종료하되 제품 경로에는 올리지 않는다.
12. NC checkpoint 또는 cache가 제품 artifact lineage에 섞인다.

### 8.4 단계별 의사결정

- **현재:** `OPEN / abstain`. packet 실측상 synthetic fidelity는 FAIL이고 wall generator, counsel, proxy audit, DGX connectivity가 준비되지 않았으므로 full P3 또는 최종 test를 시작할 근거가 없다.
- **SCHEMA_ONLY:** E0가 대기 중이어도 schema, feature allowlist, family splitter, unlabeled graph stress 도구는 구현할 수 있다. semantic 성능 claim은 금지한다.
- **GO_LOCAL_PROBE:** PR-1/2/3과 E1이 PASS일 때만 synthetic 1,000 block + 실무 20장 cheapest probe를 실행한다.
- **GO_DGX:** local probe에 양의 방향성 이득이 있고 DGX가 reachable일 때만 full SSL/HPO로 간다.
- **FREEZE_TEST:** E0–E6가 모두 PASS하고 evidence workbook dry run, baseline/model/graph/calibration hash가 고정됐을 때만 허용한다.
- **RESOLVE_TRUE:** E7의 모든 AND predicate와 `P3_lift_CI_low>0`가 참일 때만 가능하다.
- **RESOLVE_FALSE/KILL:** valid final run에서 하나라도 band가 거짓이거나 명시적 kill condition이 충족되면 GNN path를 중단한다. test를 다시 열어 구조나 threshold를 고치지 않는다.

이 설계가 권하는 현재 행동은 GNN training을 서두르는 것이 아니라 **Graph IR adjacency와 truth/provenance를 먼저 반증 가능하게 만드는 것**이다. P3가 살아남는다면 그것은 복잡한 모델이어서가 아니라, 같은 시험지·같은 handle universe·같은 family split에서 고전 baseline이 놓친 관계 문맥을 calibration과 compute까지 포함해 검증했기 때문이다.

DOSSIER_COMPLETE: calibration_P3
