# E2 방법론 심층 도시에 — platt_P2

## 제안 판정 요약

이 제안의 검증 대상은 “GNN이 벽을 잘 맞히는가”가 아니다. 검증 대상은 **동일한 truth, 동일한 도면 단위 split, 동일한 Graph IR에서 학습된 다중-hop 문맥이 동결된 P1 및 고전 ML보다 재현 가능한 추가 정보를 주는가**이다. 따라서 다음 세 차이를 분리한다.

- 주효과: Δ_main = F1(GraphSAGE, name-masked) − F1(frozen P1)
- 문맥 귀속효과: Δ_context = F1(GraphSAGE, 실제 edge) − F1(동일 모델, message passing 차단)
- 이름 의존효과: Δ_name = F1(GraphSAGE, layer/name 사용) − F1(GraphSAGE, layer/name mask)

패킷의 고정 밴드에 따라 Δ_main ≥ +0.10이면 H2 지지 후보, 0 ≤ Δ_main < +0.10이면 H2 demote, Δ_main < 0이면 현 계측기 아래에서 H2 kill이다. 다만 H2를 “그래프 문맥”으로 귀속하려면 Δ_context의 도면/def 단위 bootstrap 신뢰구간 하한도 0을 넘어야 한다. 반대로 동일 Graph IR에서 만든 고정 길이 집계 피처의 HistGradientBoosting이 GNN과 사실상 동률이면 비용 사다리 원칙에 따라 GNN을 승격하지 않는다.

현재 상태는 **조건부 HOLD**다. 그 이유는 (1) CL-B의 동결 P1이 아직 하드 선결이고, (2) Graph IR adjacency 완전성이 미증명이며, (3) synthetic wall truth가 충실도 게이트를 통과하지 못했고, (4) 외부셋 권리 확인이 미해결이며, (5) E1.5 silver는 정정된 게이트인 B1 ≥ 0.70 **및** B4 ≥ 0.70을 모두 통과한 증거가 패킷에 없기 때문이다. 이 조건들을 건너뛴 GNN 학습은 P2 실행이 아니라 누수 가능성이 있는 데모다.

이 문서의 측정값은 전부 제공된 2026-07-18 다이제스트에서만 가져왔다. 그 밖의 수치는 모두 앞으로 봉인할 설계값, 탐색 범위 또는 자원 예산이며 관측 결과가 아니다.

---

## 1. 이론적 근거·선행연구

### 1.1 문제를 그래프로 바꾸는 이유

단일 선분의 길이, 각도, 두께 후보만으로는 벽과 긴 비벽 평행 구조를 구별하기 어렵다. 제공된 CubiCasa5k 결과가 이를 직접 보여 준다. 결정론 기하 탐지기 v1은 val F1 0.2358, precision 0.134, recall 0.981이었고, FP의 주범은 Direction 화살표, BoundaryPolygon, Door, Window, DimensionMark였다. 최소길이 필터도 F1 0.335에서 막혔다. 즉 “짧은 아이콘을 지우면 된다”가 아니라, 길고 평행한 비벽 구조가 벽과 같은 국소 기하를 갖는 것이 핵심 교란이다.

반면 6개 피처를 쓴 HistGradientBoosting은 같은 CubiCasa val에서 precision 0.860, recall 0.370, F1 0.517, AUC 0.9215를 냈다. 로지스틱 회귀 F1은 0.053이었다. 이는 두 가지를 동시에 말한다.

1. 비선형 기하 조합에는 이미 큰 정보가 있다.
2. GNN은 단순 비선형성만으로는 정당화되지 않는다. 0.517의 고전 ML을 넘어서는 **고차 관계 구조**를 입증해야 한다.

벽 선분은 흔히 평행 counterpart, 연속된 junction, 코너의 폐합, 이웃 벽과의 일관된 간격처럼 여러 관계가 함께 나타난다. Door나 DimensionMark도 일부 관계를 모방하지만, 2-hop 또는 3-hop 수준에서 방 경계의 연속성, 반복 두께, junction 패턴이 다를 수 있다. 이 가설이 H2다. Graph IR은 이 관계를 명시적 edge로 만들고, message passing은 한 entity의 판정을 주변 entity의 증거와 함께 갱신한다.

### 1.2 방법론 계보

다음 문헌은 일반 지식에 기반한 방법론적 계보다. 이 도시에에서는 문헌의 수치 결과를 인용하지 않으며, 서지 세부가 불확실한 항목은 요검증으로 표시한다.

| 계보 | 대표 연구·시스템 | P2에 가져오는 요소 | 한계 또는 주의 |
|---|---|---|---|
| Graph Convolutional Network | Kipf & Welling, Semi-Supervised Classification with Graph Convolutional Networks, ICLR 2017 | 이웃 표현을 반복 집계하는 기본 원리 | 전 그래프 정규화와 transductive 성격이 대형 CAD/새 도면 전이에 불편 |
| Message Passing Neural Network | Gilmer et al., Neural Message Passing for Quantum Chemistry, ICML 2017 | node와 edge 피처를 분리해 메시지 함수로 결합 | edge 정의가 틀리면 학습기가 그 오류를 증폭 |
| GraphSAGE | Hamilton, Ying & Leskovec, Inductive Representation Learning on Large Graphs, NeurIPS 2017 | 새 도면에 적용 가능한 inductive encoder, neighbor sampling | 고차 이웃을 늘리면 후보 폭발과 oversmoothing 가능 |
| Graph Attention Network | Veličković et al., Graph Attention Networks, ICLR 2018 | 여러 관계 중 중요한 이웃에 가중치를 주는 조건부 2차 모델 | attention이 곧 설명은 아니며 고차수 graph에서 메모리 비용 증가 |
| Edge-conditioned convolution | Simonovsky & Komodakis, Dynamic Edge-Conditioned Filters in Convolutional Neural Networks on Graphs, CVPR 2017 | parallel, gap, overlap, endpoint relation을 메시지에 직접 반영 | 연속 edge 피처의 scale 정규화가 필수 |
| GIN과 표현력 분석 | Xu et al., How Powerful are Graph Neural Networks?, ICLR 2019 | 단순 평균 집계가 놓치는 multiset 구조에 대한 경고 | 더 강한 집계가 반드시 더 좋은 일반화를 뜻하지 않음 |
| 관계적 귀납 편향 | Battaglia et al., Relational Inductive Biases, Deep Learning, and Graph Networks, 2018 | object–relation–global 분해의 이론적 틀 | CAD graph의 관계가 실제 의미를 포착하는지는 별도 실험 대상 |
| Deep Sets | Zaheer et al., Deep Sets, NeurIPS 2017 | entity를 구성하는 primitive의 순서 불변 pooling | pooling 전에 primitive가 올바르게 정규화되어야 함 |
| Gradient Boosting | Friedman, Greedy Function Approximation: A Gradient Boosting Machine, 2001 | 고전 ML 사다리와 비선형 피처 조합 | 명시적 다중-hop 관계를 고정 집계로 압축해야 함 |
| 불균형 분류의 PR 평가 | Davis & Goadrich, The Relationship Between Precision-Recall and ROC Curves, ICML 2006 | 벽 선분율이 낮은 데이터에서 F1/PR 계열을 중심에 둠 | threshold 선택은 val에서만 해야 함 |
| CubiCasa5k | Kalervo et al., CubiCasa5K floorplan dataset 논문, 서지 세부 요검증 | 사람 라벨 기반 외부 raster/SEG-IR 축 | px 좌표와 미상 축척, CAD handle이 아닌 raster 유래 truth |

### 1.3 P2가 기대하는 귀납 편향

P2의 graph는 일반적인 “가까운 점끼리 연결” graph가 아니다. P1이 찾는 wall-pair 후보와 endpoint/junction 후보를 관계로 삼는 **attributed candidate graph**다. 귀납 편향은 다음과 같다.

- 벽 entity는 고립된 평행쌍보다 연속된 벽-멤버 subgraph에 속할 가능성이 높다.
- 동일한 국소 gap과 overlap이라도 코너 연결, 반복 간격, 이웃의 wall likelihood가 다르면 의미가 달라진다.
- 학습기는 raw 좌표가 아니라 회전·이동에 안정적인 상대 기하를 보아야 한다.
- 도면 이름이나 layer token은 H3 관례 prior를 담을 수 있지만 H2 기하 문맥과 섞지 않는다.

이 편향이 틀릴 가능성도 크다. 후보 graph가 과밀하면 non-wall 평행 구조가 거대한 homophilic cluster를 만들 수 있고, 누락된 INSERT transform이나 곡선 정규화 오류는 실제 벽의 연결을 끊는다. 또한 message passing은 고차 문맥을 배우는 대신 degree, layer 동일성, 데이터셋 고유 raster artifact를 외울 수 있다. 따라서 graph 구조 자체를 label join 전에 감사하고, edge 차단·edge shuffle·name mask를 별도 arm으로 둔다.

### 1.4 인과적 질문과 판정 단위

평가 단위는 처음부터 끝까지 원본 source handle 또는 SEG-IR segment의 **per-handle wall_member(h)**다. 집합 조립이나 room reconstruction은 P2의 primary output이 아니다.

동일 source s와 held-out split d에 대해 다음을 정의한다.

\[
F(M;s,d)=\text{per-handle micro F1 of model }M
\]

\[
\Delta_{\text{main}}=F(M_{\text{SAGE-mask}};s,d)-F(P1_{\text{frozen}};s,d)
\]

\[
\Delta_{\text{context}}=F(M_{\text{SAGE-mask}};s,d)-F(M_{\text{NoMessage-mask}};s,d)
\]

\[
\Delta_{\text{name}}=F(M_{\text{SAGE-full}};s,d)-F(M_{\text{SAGE-mask}};s,d)
\]

NoMessage는 학습 파라미터 수와 node encoder를 유지하되 이웃 메시지를 0으로 만들어 자기 node만 보는 arm이다. 따라서 Δ_context는 “신경망이어서”가 아니라 실제 graph edge를 사용해서 생긴 차이에 가깝다. 추가로 degree-preserving edge shuffle arm을 두어 단순 degree 신호와 관계 배치를 분리한다.

H2 승격은 단일 source의 좋은 숫자로 하지 않는다. 적격 truth source 중 최소 2개에서 방향이 일치하고, proxy 독립성 감사에서 같은 가족으로 합쳐지지 않아야 한다. 다섯 E1.5 판정자는 두 어휘 가족이므로 다섯 독립표로 세지 않는다.

---

## 2. 알고리즘 정확 스펙

### 2.1 입력과 출력 계약

입력 Graph IR record는 다음 필드를 가진다.

**Drawing/definition record**

- drawing_id, def_id, source_id, split_id
- unit metadata와 bbox
- graph_builder_version, P1_normalizer_version
- label_join_version
- raw artifact hash와 name-blind artifact hash

**Node record**

- node_id와 source_handle_id
- 원본 entity type
- P1 정규화로 얻은 primitive 목록
- intrinsic geometry feature
- 선택적 layer/name feature
- train source에서만 결합되는 wall_member label과 label provenance

**Edge record**

- src, dst
- relation type bitset: parallel_candidate, endpoint_snap, intersection, continuation
- relation geometry: angle difference, perpendicular gap, projected overlap, endpoint distances
- graph-builder reason code와 후보 검색 rank

출력은 각 source_handle_id에 대해 다음을 기록한다.

- wall_probability
- frozen val threshold로 얻은 wall_member prediction
- model_version, feature_mask_id, graph_version
- source별 metric 집계에 연결되는 drawing_id/def_id
- 오류 감사용으로 top relation evidence와 ablation arm id

node를 원본 handle 단위로 두는 이유는 평가 universe를 바꾸지 않기 위해서다. LWPOLYLINE, MLINE, ARC, SPLINE, exploded INSERT에서 생기는 여러 primitive는 handle 내부에서 순서 불변으로 pooling한다. INSERT의 child handle은 world transform을 적용한 뒤 parent provenance를 보존한다. 하나의 원본 handle이 여러 의미를 섞는 예외는 오류표에 남기되, test 시점에 평가 단위를 재정의하지 않는다.

### 2.2 결정적 Graph IR 빌더

#### 2.2.1 정규화

1. CL-B P1 normalizer로 INSERT transform을 world 좌표까지 전개한다.
2. LINE은 한 primitive, LWPOLYLINE/MLINE은 segment primitive 집합으로 만든다.
3. ARC와 SPLINE은 prereg에 봉인한 chord-error 규칙으로 piecewise primitive를 만들되 source_handle_id를 유지한다.
4. primitive endpoint, tangent orientation, length, bbox를 계산한다.
5. 동일 입력과 동일 config에서 node/edge 정렬 및 hash가 완전히 같아야 한다.

이 단계는 이름과 label을 보지 않는다. graph adjacency를 layer equality로 만들면 이후 name mask를 해도 구조에 이름이 남기 때문에 금지한다.

#### 2.2.2 graph node

handle h의 primitive 집합을 P(h)라 할 때 intrinsic node feature는 다음과 같다.

- entity type one-hot
- total length와 log length
- primitive count
- bbox aspect ratio와 bbox diagonal 대비 길이
- 길이 가중 orientation moment: 평균 sin(2θ), cos(2θ)
- endpoint 수, self-intersection 수, 곡률 요약
- P1의 이름 비사용 기하 채널 점수와 해당 score의 missing bit

도면별 scale 기준 s_d는 train/test에서 같은 결정식으로 구한다. 기본 후보는 유효 primitive length의 median과 bbox diagonal이며, 어떤 조합을 쓸지는 Graph IR audit 전에 봉인한다. 공통 model에는 gap/s_d, length/s_d와 같은 상대량을 사용하고, 실제 단위가 신뢰되는 CAD arm의 mm 값은 별도 optional feature group으로 둔다. CubiCasa는 px 축척 미상이므로 mm feature를 0과 missing bit로 처리한다.

primitive pooling은 길이 가중 평균, max, count를 이어 붙인 결정적 Deep Sets형 요약이다. 학습 가능한 primitive encoder는 v1에서 쓰지 않는다. node 정의 자체가 달라지는 추가 자유도를 막기 위해서다.

#### 2.2.3 candidate edge

두 handle i, j의 primitive pair에 대해 다음을 계산한다.

\[
p_{ij}=\cos(2(\theta_i-\theta_j))
\]

\[
o_{ij}=\frac{\text{projected overlap length}}{\min(\ell_i,\ell_j)+\epsilon}
\]

\[
g_{ij}=\frac{\text{perpendicular distance}}{s_d+\epsilon}
\]

\[
e_{ij}=\frac{\min\text{ endpoint distance}}{s_d+\epsilon}
\]

undirected line의 방향은 θ와 θ+π가 같으므로 double-angle 표현을 쓴다. candidate 생성은 spatial grid 또는 R-tree에서 bbox halo와 endpoint k-nearest를 합집합한 뒤, prereg된 느슨한 각도·gap·overlap 조건으로 거른다. edge feature에는 다음을 넣는다.

- cos(2Δθ), sin(2Δθ)
- normalized gap
- overlap ratio
- 네 endpoint 거리의 min/mean/max
- 교차 여부와 continuation 여부
- 관계를 만든 primitive-pair 수
- P1 candidate score
- 선택적 same-layer bit

여러 primitive pair가 같은 handle pair를 만들면 min gap, max overlap, mean angle, count를 집계해 하나의 양방향 edge로 만든다. self-edge는 model layer가 별도로 처리하며 IR에 저장하지 않는다.

대형 def에서 k-nearest cap이 relation을 버리지 않았는지 별도 cap_truncation_count로 기록한다. candidate 폭발을 막기 위한 cap이 audit recall을 떨어뜨리면 모델을 돌리지 않는다. 작은 audit def에서는 모든 primitive pair를 exhaustive하게 계산한 reference adjacency와 비교한다.

### 2.3 피처 군과 ablation 계약

| 피처 군 | 내용 | local/graph | name-masked arm |
|---|---|---|---|
| X_intrinsic | type, 길이, 각도 moment, bbox, 곡률 | local | 유지 |
| X_p1geom | 이름 비사용 P1 기하 채널 | local summary | 유지 |
| X_edgegeom | parallel, gap, overlap, endpoint, junction | edge | 유지 |
| X_graphstat | degree, relation-type count, gap/overlap quantile | 고전 ML용 고정 집계 | 유지 |
| X_name | train-only layer token embedding, same-layer bit | node/edge | 전부 0과 MASK id |
| X_abs | raw 좌표, 파일 순번, handle 문자열, labeler id | 누수 위험 | 모든 arm에서 금지 |

layer vocabulary는 train split에서만 만든다. held-out의 새 token은 UNK로 간다. token frequency, target encoding, 전체 corpus vocabulary는 사용하지 않는다. name-only 진단 arm은 X_name만 쓰되 승격 후보가 아니다.

### 2.4 모델

#### 2.4.1 고전 ML 사다리

동일 X_intrinsic + X_p1geom + X_graphstat에 대해 다음 순서로 실행한다.

1. class-weighted logistic regression
2. HistGradientBoosting

기존 6-feature 결과를 재사용해 결론을 내리지 않고, 새 Graph IR split과 동결 P1에서 다시 측정한다. 기존 val F1 0.517은 사전 정보일 뿐이다.

#### 2.4.2 기본 GraphSAGE

초기 node state는 다음과 같다.

\[
h_i^{(0)}=\phi_n([X_{\text{intrinsic},i},X_{\text{p1geom},i},X_{\text{name},i}])
\]

layer l에서 edge-conditioned message와 update는 다음과 같다.

\[
m_{ij}^{(l)}=\phi_e^{(l)}([h_j^{(l)},E_{ij}])
\]

\[
\bar m_i^{(l)}=\operatorname{mean}_{j\in N(i)}m_{ij}^{(l)}
\]

\[
h_i^{(l+1)}=\operatorname{LayerNorm}\left(h_i^{(l)}+
\phi_u^{(l)}([h_i^{(l)},\bar m_i^{(l)}])\right)
\]

최종 logit은 z_i = wᵀh_i + b다. 기본 구조는 2-layer, hidden width 128, edge MLP width 64, GELU, residual, LayerNorm, dropout 0.10으로 prereg 후보를 정한다. 이는 관측된 최적값이 아니라 첫 실행 기본값이다.

작은 탐색 공간은 다음으로 제한한다.

- message-passing layer: {2, 3}
- hidden width: {64, 128}
- dropout: {0.0, 0.1, 0.3}
- learning rate: {3e-4, 1e-3, 3e-3}
- weight decay: {1e-6, 1e-4, 1e-3}
- neighbor fanout per layer: {(10, 10), (20, 10), (20, 20)}
- loss: weighted BCE 또는 focal loss의 γ {1, 2}

모든 조합을 전수 탐색하지 않는다. 기본값, 한 변수씩 제한된 val 탐색, 최종 1개 config 순으로 진행한다. architecture search를 test에 흘리지 않는다.

#### 2.4.3 GAT 조건부 arm

GraphSAGE에서 Δ_context가 양수지만 relation 종류가 섞인 high-degree node에서 오류가 집중될 때만 4-head edge-aware GAT를 한 번 비교한다. GraphSAGE가 밴드를 못 넘었거나 고전 ML과 동률이면 GAT로 재시도하지 않는다. GAT는 구조 실패를 compute로 덮는 구조가 아니라 제한된 진단 arm이다.

### 2.5 손실, sampling, calibration

primary loss는 per-handle binary classification이다.

\[
\mathcal L_{\text{node}}=-\frac{1}{|B|}\sum_{i\in B}
w_{y_i}\left[y_i\log\sigma(z_i)+(1-y_i)\log(1-\sigma(z_i))\right]
\]

class weight는 train split의 prevalence에서만 계산하고 config에 기록한다. source를 섞는 최종 arm에서는 entity 수가 많은 source가 loss를 독점하지 않도록 source-balanced batch와 source별 loss 평균을 사용한다.

neighbor sampling은 target handle을 먼저 뽑고 2-hop 이웃을 확장한다. 벽 양성 oversampling은 train에서만 허용하며 metric 계산에는 원래 prevalence를 유지한다. validation과 test는 가능한 경우 full connected component inference를 하고, 너무 큰 component는 2-hop halo를 포함한 deterministic chunk로 나눈 뒤 target node 예측만 합친다.

optimizer는 AdamW, 최대 100 epoch, val PR-AUC에 대한 patience 10을 기본 설계값으로 둔다. checkpoint 선택 기준은 val PR-AUC, 최종 threshold 선택 기준은 val per-handle F1이다. threshold를 선택한 뒤 해당 source test에는 손대지 않는다. 여러 source를 평가할 때는 각 train-source val에서 봉인한 threshold를 target source에 그대로 적용해 전이 성적을 낸다.

신경망 seed는 {20260718, 20260719, 20260720} 세 개로 고정한다. val에는 seed별 값과 평균·표준편차를 모두 기록한다. 최종 test는 prereg대로 세 seed logit 평균을 쓰는 ensemble 1개를 한 번 평가한다. seed 결과를 본 뒤 가장 좋은 seed만 고르는 행위는 금지한다.

### 2.6 알고리즘 의사코드

    INPUT:
      frozen P1 normalizer
      eligible source artifacts
      drawing/def split manifest
      feature-mask config
      prereg config

    FOR each drawing or definition d:
      assert d belongs to exactly one split
      primitives = P1_NORMALIZE(d, expand_insert=true, preserve_handle=true)
      nodes = POOL_PRIMITIVES_BY_HANDLE(primitives)
      edges = BUILD_NAME_BLIND_CANDIDATE_EDGES(nodes, prereg.graph_rules)
      graph_hash = HASH_CANONICAL(nodes_without_labels, edges_without_labels)
      labels = JOIN_LABELS_AFTER_GRAPH_FREEZE(d, source_policy)
      WRITE_GRAPH_SHARD(nodes, edges, labels, graph_hash)

    AUDIT:
      compare candidate edges with exhaustive reference on audit defs
      verify transform/unit/name-rename invariance
      verify zero-wall and all-wall sentinels
      stop if any hard gate fails

    BASELINES:
      score frozen P1 on held-out val
      train logistic on train only
      train HistGradientBoosting on train only
      if classical model satisfies Occam stop rule:
          do not escalate to GNN

    GNN:
      for seed in fixed_seeds:
          train name-masked GraphSAGE on train
          select checkpoint and threshold using val only
          evaluate full, no-message, edge-shuffle, and name-full arms on same val
      aggregate by handle and drawing/def
      apply prereg Δ bands

    MULTI-SOURCE:
      run train-source × eval-source matrix without retuning target threshold
      run same-instance proxy-dependence audit
      require at least two eligible, non-duplicate sources for promotion

    TEST:
      only after config, threshold, seeds, and bands are sealed
      score each method exactly once
      write predictions, metrics, failures, and evidence workbook

### 2.7 metric와 evidence 계약

primary metric은 전체 held-out handle을 합친 per-handle micro F1이다. 함께 기록할 secondary metric은 precision, recall, PR-AUC, ROC-AUC, drawing/def macro F1, zero-wall false-positive rate, calibration curve, runtime, peak RAM/VRAM이다. 대형 def 하나가 결론을 독점하는지 보기 위해 drawing/def 단위 결과와 cluster bootstrap interval을 함께 낸다. bootstrap resampling unit은 handle이 아니라 drawing/def다.

mandatory shuffle control은 train label을 각 train drawing/def 내부에서 class count를 보존하며 permutation하고 같은 pipeline을 학습한다. proposed alarm band는 shuffled val ROC-AUC > 0.55 또는 실제 label arm에 근접한 F1이다. 이는 앞으로 봉인할 누수 경보선이며 현재 측정 주장이 아니다.

evidence xlsx에는 최소 다음 sheet가 필요하다.

- prereg: config hash, split hash, P1 version, graph version
- source_manifest: rights status, truth provenance, eligibility
- per_handle: truth, prediction, probability, arm
- per_drawing: P/R/F1, zero-wall sentinel
- deltas: Δ_main, Δ_context, Δ_name와 cluster bootstrap
- transfer_matrix: train source × eval source
- proxy_audit: family-aware disagreement 및 error dependence
- failures: OOM, cap truncation, missing transform, ambiguous raster label
- runtime: CPU/GPU/RAM/VRAM

---

## 3. 벽 과업 적응 설계

### 3.1 공통 표현과 세 truth 축

세 source를 억지로 같은 품질의 truth로 취급하지 않는다. 각 source는 다른 질문을 담당한다.

| source | graph node | truth | 주 역할 | 현재 자격 |
|---|---|---|---|---|
| synthetic S/F/M | 생성 DWG의 원본 handle | generator의 explicit wall_member | 기하 메커니즘과 hidden mutation 일반화 | B1 충실도 FAIL, wall generator 선결 미충족으로 비활성 |
| CubiCasa5k SEG-IR | 변환된 segment | Wall 클래스 요소의 모서리 | 사람 라벨 외부 전이의 주 개발축 | 변환 실패 0, split 존재. 단, counsel 서면 확인 전 학습 HOLD |
| FloorPlanCAD | raw raster에서 독립 추출한 segment | wall mask와의 raster overlap으로 만든 weak label | raster→graph representation transfer | SVG 없음, exact handle truth 아님. counsel과 projection audit 전 비적격 |
| 1.dwg의 384 def | P1-normalized source handle | E1.5 family-aware silver | 실제 messy CAD의 조건부 교차검증 | B1 및 B4 모두 통과하기 전 비활성 |

“3원”은 투표 평균이 아니다. 각 축에서 독립적으로 Δ band를 계산하고, 최소 두 적격 source의 방향 일치가 있어야 승격한다. proxy 감사에서 두 source가 같은 error family로 판정되면 둘을 한 표로 센다.

### 3.2 CubiCasa5k SEG-IR 축

제공된 고정 split인 train 4,200 / val 400 / test 400 도면을 그대로 사용한다. 행 수가 아니라 floorplan_id로 graph를 격리한다. train 386만, val 35.4만, test 37.5만 선분이라는 제공 수치를 manifest에서 검증하되, test는 최종 전까지 feature 분포 요약도 다시 보지 않는다.

SEG-IR segment가 평가 node다. Wall 클래스 요소의 모서리를 positive로 둔 기존 truth를 그대로 쓴다. graph edge는 px 좌표에서 만들지만 도면별 scale이 미상이므로 gap은 도면 scale 기준으로 정규화한다. 제공 결과에서 2–15 mm/px 전 구간에 결정론 성적이 무감했던 사실 때문에 물리 두께 prior를 공통 feature로 삼지 않는다.

첫 질문은 새 Graph IR의 HGBDT가 기존 6-feature F1 0.517을 재현 또는 개선하는지가 아니라, **동결 P1과 같은 split에서 GNN까지 갈 필요가 있는지**다. 기존 수치는 서로 다른 실행 계약일 수 있으므로 새 prereg 비교의 baseline으로 직접 대체하지 않는다.

GNN이 가져올 수 있는 추가 정보는 다음으로 제한한다.

- 긴 평행 non-wall 구조가 주변에서 끊기는지 또는 벽 network로 이어지는지
- 일정 gap이 여러 edge에 반복되는지
- endpoint/junction motif가 door/window/dimension과 벽에서 달라지는지
- 2-hop neighborhood에서 wall likelihood가 구조적으로 지지되는지

이 네 가지를 넘어 “딥러닝이 자동으로 의미를 안다”고 주장하지 않는다.

### 3.3 FloorPlanCAD raster 축

FloorPlanCAD에는 5,308 raster와 wall bbox/segmask가 있지만 vector SVG가 없다. 따라서 mask contour를 그대로 graph input으로 쓰면 label에서 input을 재생성하는 순환 누수가 된다. 다음 bridge만 허용한다.

1. raw floorplan raster에서, wall mask를 보지 않고 deterministic line segment detector로 segment를 추출한다.
2. 추출 parameter는 FloorPlanCAD train subset에서만 봉인한다.
3. graph input은 raw raster 유래 segment와 그 기하 관계만 사용한다.
4. label은 segment를 rasterize했을 때 wall mask와 겹치는 비율로 정한다. proposed τ_pos 이상은 positive, τ_neg 이하는 negative, 중간은 ambiguous로 제외한다. τ_pos와 τ_neg는 train에서 정하고 val/test 전에 봉인한다.
5. graph/feature artifact hash를 먼저 고정한 뒤 mask label을 join한다.
6. bbox만 있고 mask가 없는 sample은 per-segment truth로 승격하지 않는다.

이 arm은 CAD handle 성능이 아니라 representation transfer를 시험한다. synthetic-trained GNN이 이 FloorPlanCAD graph에서 frozen deterministic baseline보다 낮으면 “synthetic 분포가 transfer에 충분하다”는 보조가정을 kill한다. 그 결과만으로 H2 본체를 kill하지는 않는다.

pixel→segment alignment는 CL-G의 pixel→handle exact harness와 같은 위험을 가진다. synthetic render에서 알려진 segment를 rasterize한 뒤 round-trip label 오차를 먼저 계측한다. 이 audit를 통과하지 못하면 FloorPlanCAD는 학습 truth가 아니라 qualitative error source로만 남긴다.

### 3.4 1.dwg, 384 def, E1.5 silver 축

384개 def는 def_id 단위로 split한다. 같은 block definition의 instance가 여러 곳에 있더라도 한 split에만 둔다. INSERT instance transform은 Graph IR에서 world 좌표로 전개하지만, 동일 def 계보가 train과 eval에 중복되지 않도록 lineage_id를 둔다.

silver 활성 조건은 패널의 정정안을 따른다.

- E1.5 B1 ≥ 0.70
- E1.5 B4 ≥ 0.70
- 두 조건 모두 충족

제안 원문의 “B1만 통과하면 silver arm 활성”은 사용하지 않는다. 다섯 판정자는 두 어휘 가족이므로 5표 majority를 독립 합의로 보지 않는다. positive 또는 negative silver는 두 가족이 모두 같은 결론을 내고, rationale evidence class가 허용 목록에 있으며, name-blind 판정에서도 유지되는 handle/def만 사용한다. 나머지는 unlabeled로 둔다.

silver train def와 eval def는 완전 분리한다. layer vocabulary도 silver train def에서만 만든다. name/layer mask arm이 full arm보다 크게 떨어지면 두 가능성을 동시에 기록한다.

1. H3: 실제 CAD 관례 이름 prior가 강하다.
2. 누수 경보: E1 판정자가 이름을 사용해 만든 silver를 모델이 되받아 외웠다.

두 가능성을 데이터만으로 자동 분리하지 않는다. name-blind silver subset과 rationale evidence class 감사를 함께 보아야 한다.

silver gate가 열리지 않으면 1.dwg graph는 adjacency audit, runtime stress, metamorphic consistency에만 쓴다. label metric을 만들거나 pseudo-label을 사실처럼 쓰지 않는다.

### 3.5 synthetic 축

현재 synthetic pack은 KS 0.5792, TV 0.265로 B1 충실도 FAIL이며, 실제 도면에 SPLINE 3,973, ARC 2,198, HATCH 264가 섞인 데 비해 합성팩은 LINE/LWPOLYLINE/INSERT 세 종류뿐이다. 또한 패널은 synthetic_truth.py에 벽 생성 코드가 없다는 선결 결함을 지적했다. 그러므로 현재 synthetic label을 GNN train truth로 사용하지 않는다.

CL-C가 explicit per-handle wall truth와 hidden mutation family를 갖춘 뒤 다음 분리를 적용한다.

- generator template family 단위 train/val/test 격리
- mutation family 단위 격리
- 같은 base plan의 회전·scale·layer rename 파생본을 한 split에 묶음
- hidden mutation family는 test 전용
- zero-wall와 all-wall sentinel 포함

B2에서 S pack은 P/R 1.0/1.0이었지만 negative가 0개라 precision이 공허했다. 이 때문에 양성 전용 synthetic split은 P2 truth로 인정하지 않는다.

### 3.6 proxy 독립성 bridge

서로 다른 데이터셋의 단순 cross-source 성적만으로는 T1의 “동일 def 불일치 구조”를 충족하지 못한다. 동일 instance에서 세 proxy를 비교하는 bridge set을 별도로 만든다.

- 적격 synthetic DWG를 rasterize하고, generator truth, 외부 raster-trained predictor의 역투영 prediction, E1.5 name-blind family consensus를 같은 source handle에 매핑한다.
- 실 def에서는 P1 prediction, 외부 raster-trained predictor의 역투영 prediction, E1.5 name-blind consensus를 같은 handle에 매핑한다. 여기서 P1 prediction은 truth가 아니라 proxy다.
- pairwise agreement만 보지 않고, 명시 truth가 있는 synthetic subset에서는 error indicator의 상관, 조건부 confusion, 오류 handle overlap을 측정한다.
- 한 proxy의 error가 다른 proxy와 강하게 결박되면 두 source의 concordance를 두 표로 세지 않는다.

proposed family-collapse rule은 pairwise error-correlation의 drawing/def bootstrap 하한이 0.50을 넘거나, 한 proxy가 다른 proxy의 prediction을 geometry controls 이후에도 ROC-AUC 0.90 이상으로 예측하는 경우다. 이 값들은 관측값이 아니라 prereg 제안선이며 T1 audit 전에 봉인한다.

### 3.7 test 단발 원칙

모든 개발은 val에서 끝낸다. test 접근 전 다음을 한 manifest에 봉인한다.

- graph builder와 P1 version
- split hash
- feature mask
- model config와 seed ensemble 규칙
- threshold
- Δ band와 Occam band
- 실패 처리 규칙

그 뒤 frozen P1, selected classical baseline, selected P2 model을 각각 한 번 score한다. test 결과를 본 뒤 model, threshold, graph edge, source inclusion을 바꾸면 새 방법으로 취급하며 기존 test는 재사용하지 않는다. 두 source concordance가 val에서 성립하지 않으면 test를 소비하지 않는다.

---

## 4. 데이터·컴퓨트 요구

### 4.1 자산별 준비 상태

| 자산 | 필요한 준비 | 로컬 실행성 | 하드 blocker |
|---|---|---|---|
| CubiCasa SEG-IR | 기존 split manifest와 graph shard | CPU build + RTX 학습 가능 | NC/원도면 counsel 서면 확인 |
| FloorPlanCAD | raw-raster segment extractor, mask join, projection audit | CPU build + RTX 학습 가능 | counsel, vector truth 부재, projection 정확도 |
| synthetic | 실제 wall generator, per-handle truth, fidelity gate | 생성·build는 CPU, 학습은 RTX | PR-1/CL-C 미완료와 B1 FAIL |
| 1.dwg 384 def | P1 normalizer, def split, silver gate | 작은 def CPU build, RTX 학습 | CL-B, adjacency audit, E1.5 B1/B4 |
| 145 modelspace | component/chunk inference | local 우선, 필요 시 DGX | 최대 graph 규모와 DGX 현재 unreachable |

외부셋 사용이 프로그램 차원에서 GO되었다는 사실과 license/counsel clearance는 별개다. 패널 PR-3가 해결되기 전에는 외부 데이터 학습을 시작하지 않는다.

### 4.2 로컬 CPU feature build

RAM 64GB에서 386만 train segment를 Python object graph로 한꺼번에 올리지 않는다. columnar shard를 drawing 단위로 만들고, node float feature와 int index를 memory-map한다. 권장 shard 계약은 다음과 같다.

- node feature: float32 또는 검증된 float16 cache
- edge index: int32, relation feature: float32
- drawing/def offset index
- label과 provenance는 별도 column
- graph hash와 builder config sidecar

spatial index build는 drawing 단위 multiprocessing을 쓰되, 출력 정렬은 drawing_id/node_id로 canonicalize한다. worker 수는 RAM peak를 측정해 정한다. max 412,775 선분 def는 별도 large-graph path로 보내고, graph build 중 edge cap, component size, peak memory를 기록한다.

계획 예산은 다음과 같다. 모두 사전 추정이며 실측이 아니다.

- Graph IR schema와 audit set: 엔지니어 2일
- CubiCasa 전체 feature build: 로컬 CPU 8–16시간
- FloorPlanCAD segment bridge와 round-trip audit: 엔지니어 2–3일
- 384 def normalizer 연결과 large-graph chunking: 엔지니어 2–3일
- evidence workbook 및 regression test: 엔지니어 1–2일

### 4.3 RTX 5070 Ti 16GB 학습

GraphSAGE는 full-batch가 아니라 target-node mini-batch와 bounded neighbor sampling을 쓴다. 기본 target batch는 4,096 node로 시작하고 OOM이면 2,048, 1,024 순으로 낮춘다. hidden width 또는 layer 수를 늘리기 전에 batch와 fanout을 봉인한다. mixed precision은 동일 seed에서 finite-loss와 metric parity smoke test를 통과할 때만 사용한다.

계획상 1 config × 3 seed를 기본 단위로 하고, 고전 ML gate를 통과하지 못했을 때만 GNN을 실행한다. 한 seed의 계획 상한은 6 GPU-hours, 전체 기본 GraphSAGE는 18 GPU-hours다. 이 상한은 실제 속도 주장이 아니라 queue와 kill decision을 위한 예산이다. 상한을 넘으면 profile evidence 없이 더 큰 architecture로 확장하지 않는다.

### 4.4 대형 graph inference

최대 def 412,775 선분이라는 제공 관측 때문에 component-wise inference가 필수다.

1. graph connected component를 구한다.
2. 작은 component는 그대로 inference한다.
3. 큰 component는 spatial tile로 자르고 message-passing depth만큼 halo를 붙인다.
4. halo prediction은 버리고 tile core prediction만 합친다.
5. full graph가 가능한 작은 표본에서 chunked/full parity를 확인한다.

proposed parity gate는 probability 최대 절대오차 ≤ 1e-5, threshold prediction 일치율 ≥ 0.9999다. 이 값들은 구현 수용선이며 측정 결과가 아니다. parity를 못 맞추면 chunk inference 결과를 primary evidence로 쓰지 않는다.

### 4.5 DGX 계획

DGX Spark의 Ornith-35B endpoint는 현재 unreachable이므로 P2 critical path에서 제외한다. 로컬 RTX와 CPU만으로 CubiCasa와 384 def 개발이 끝나도록 설계한다.

DGX는 다음 조건을 모두 만족할 때만 optional 야간 확장에 쓴다.

- endpoint와 GPU job path가 다시 reachable
- Ornith vLLM serving owner와 시간분할 합의
- checkpoint/resume smoke test 통과
- local config와 동일한 container/environment hash
- 145 modelspace 전체 graph inference 또는 source-balanced 대규모 sweep가 local 예산을 넘음

DGX 장애는 P2 실행 실패 사유가 될 수 없고, 단지 optional scale arm을 보류하는 사유다.

### 4.6 저장·재현 요구

계획 저장 예산은 graph shard, checkpoint, prediction, evidence를 합쳐 20–40GB를 먼저 예약한다. 이는 실제 사용량이 아니라 운영 상한이다. 모든 실행은 다음을 기록한다.

- raw input hash
- split manifest hash
- P1 및 graph builder version
- feature schema hash
- model config/seed/checkpoint hash
- command line과 environment lock
- 실패한 run도 failure reason과 마지막 정상 checkpoint

---

## 5. 구현 계획

### 5.1 제안 파일 골격

아래는 향후 repo 구현 골격이며, 이 도시에 작성 시 실제 파일을 생성한다는 뜻이 아니다.

| 모듈 | 책임 | 기존 접속점 |
|---|---|---|
| e2/graph_ir/schema.py | node/edge/source/split schema와 version | evidence_grid run manifest |
| e2/graph_ir/normalize.py | P1 primitive와 source handle pooling | fast_score, P1 normalizer |
| e2/graph_ir/adjacency.py | name-blind candidate edge와 spatial index | fast_score wall_pairs 후보 |
| e2/graph_ir/audit.py | exhaustive adjacency, determinism, cap, invariance | evidence_grid |
| e2/graph_ir/shard.py | drawing/def columnar shard, memory map | cubicasa_ir |
| e2/data/cubicasa_graph.py | 고정 split SEG-IR→Graph IR | cubicasa_ir |
| e2/data/fpc_graph.py | raw raster segment→mask weak label bridge | FloorPlanCAD assets |
| e2/data/silver_graph.py | family-aware silver gate와 def split | prereg_e15.json |
| e2/models/classical.py | logistic/HGBDT 동일-feature baseline | cubicasa_ml |
| e2/models/graphsage.py | edge-conditioned GraphSAGE | 새 구현 |
| e2/models/gat.py | 조건부 GAT arm | 새 구현 |
| e2/train/train_p2.py | seed, sampling, early stop, checkpoint | cubicasa_ml run convention |
| e2/eval/p2_metrics.py | per-handle/drawing metric와 Δ | evidence_grid |
| e2/eval/proxy_audit.py | 동일-instance proxy dependence | CL-E 출력 |
| e2/reports/p2_xlsx.py | 필수 evidence workbook | evidence_grid |
| configs/prereg_p2.json | bands, split, feature, seeds, test lock | prereg_e15.json은 read-only gate input |

### 5.2 기존 도구와의 연결

**fast_score**

- frozen P1 prediction과 이름 비사용 channel score를 node feature로 제공한다.
- P1 output schema를 바꾸지 않고 adapter를 둔다.
- GNN candidate edge를 만들 때 fast_score의 후보 생성 결과와 새 name-blind adjacency를 비교한다.

**cubicasa_ir**

- 기존 floorplan_id와 train/val/test split을 authoritative key로 쓴다.
- segment label과 좌표를 Graph IR node로 변환한다.
- test artifact는 prereg lock 전 loader가 접근하지 못하게 별도 path guard를 둔다.

**cubicasa_ml**

- 기존 logistic/HGBDT pipeline의 preprocessing과 metric writer를 재사용한다.
- 6-feature 결과와 새 graph-stat feature 결과를 서로 다른 experiment_id로 보존한다.
- GNN과 고전 ML의 train universe가 같은지 row/node manifest hash로 검증한다.

**evidence_grid**

- run folder completeness, config hash, per-handle prediction, xlsx export를 연결한다.
- failed run도 삭제하지 않고 reason code를 남긴다.
- PASS는 metric만이 아니라 prereg, split, shuffle, evidence workbook의 완전성을 함께 요구한다.

### 5.3 구현 순서

1. **계약 고정**: per-handle schema, split key, feature partition, silver gate 정정, counsel status field.
2. **Graph IR MVP**: CubiCasa train 일부와 작은 synthetic sentinel에서 node/edge 생성.
3. **adjacency 감사**: exhaustive reference, transform/name-rename determinism, cap 통계.
4. **고전 ML 사다리**: logistic와 HGBDT를 동일 graph-stat feature로 실행.
5. **GraphSAGE MVP**: 한 작은 train shard에서 overfit smoke test, label shuffle smoke test.
6. **전체 val**: 3 seeds, NoMessage, edge-shuffle, name mask.
7. **source bridge**: FloorPlanCAD, synthetic, silver는 각 gate가 열린 순서로 추가.
8. **evidence와 lock**: xlsx, prereg hash, test access approval.
9. **test 단발**: 두 source concordance가 확보된 경우에만.

### 5.4 테스트 설계

**unit test**

- undirected orientation의 θ와 θ+π 동일성
- 회전/이동/반사 후 graph relation parity
- 단위 변환 후 normalized feature parity
- layer rename 후 name-masked graph hash 동일
- INSERT nested transform world 좌표
- zero-wall/all-wall metric sentinel
- handle pooling과 label join

**property test**

- node 순서를 shuffle해도 canonical graph hash 동일
- worker 수를 바꿔도 output 동일
- chunk/full inference parity
- label column을 제거해도 graph artifact hash 동일

**leakage test**

- split 간 drawing_id, def_id, lineage_id 교집합 0
- val/test token이 layer vocabulary에 없음
- label join 전후 node/edge feature hash 동일
- shuffled control alarm band
- name-only arm과 dataset-id-only arm 별도 보고

### 5.5 개발 규모와 완료 정의

핵심 구현은 약 1,500–2,500 LOC, 테스트·report 약 800–1,200 LOC의 계획 규모다. 이는 관측된 코드량이 아니라 범위 관리용 추정이다. 한 명 기준으로 gate가 이미 열려 있다는 가정하에 8–12 엔지니어일을 잡는다. synthetic generator, counsel, E1.5 재평가는 이 추정에 포함하지 않는다.

“구현 완료”는 model checkpoint 존재가 아니다. 다음이 모두 있어야 한다.

- 동결 Graph IR schema와 adjacency audit PASS
- 동일 split의 frozen P1/logistic/HGBDT/GNN prediction
- 3 seed 및 ablation 결과
- shuffle control
- source eligibility와 rights 기록
- evidence xlsx
- 실패 run 포함 completeness report
- test를 썼다면 one-shot access log

---

## 6. 실험 셀 정의

### 6.1 공통 실행 규칙

- split unit: floorplan, drawing, def, generator family
- primary metric: per-handle micro F1
- uncertainty unit: drawing/def cluster
- 개발: val만 사용
- test: 방법당 단발
- seed: 고전 ML은 {20260718, 20260719, 20260720}, GNN도 같은 세 seed
- promotion: 적격이며 proxy-family가 다른 최소 2 source에서 방향 concordance
- 모든 합격선은 해당 cell 실행 전에 prereg_p2.json에 hash로 봉인

### 6.2 셀 목록

#### P2-G0 — 선결 게이트와 P1 동결

- **가설**: P2가 비교할 P1과 truth source가 재현 가능하고 법적·방법론적으로 적격이다.
- **입력**: CL-B P1, CL-C synthetic status, counsel memo, prereg_e15.json.
- **지표**: P1 version/hash, source eligibility, split collision count, silver B1/B4.
- **합격선**: split collision 0; P1 baseline evidence 완전; external counsel clear; 사용하는 source의 gate 모두 PASS. silver는 B1 ≥ 0.70 및 B4 ≥ 0.70.
- **킬/정지**: 하나라도 실패한 source는 비활성. P1이 동결되지 않으면 전체 P2 primary 실험 정지.
- **예산**: 로컬 CPU 0.5일, GPU 0.
- **시드**: 결정적, seed 없음.

#### P2-G1 — Graph IR adjacency 완전성

- **가설**: 느슨한 candidate graph가 exhaustive reference의 의미 있는 relation을 거의 모두 보존하고 이름에 독립적이다.
- **입력**: 작은 def audit set, divergent/messy 사례, sentinel.
- **지표**: candidate-relation recall, cap truncation, graph hash determinism, transform/name-rename parity, edge/node ratio.
- **제안 합격선**: exhaustive positive relation recall ≥ 0.995; audit case cap truncation 0; 반복 build hash 일치 1.0; name-masked graph rename parity 1.0.
- **킬/정지**: recall 또는 transform parity 실패 시 학습 금지. edge 수가 예산 상한을 넘으면 adjacency rule을 고친 뒤 새 version으로 재감사하며 model tuning으로 우회하지 않음.
- **예산**: CPU 1일, RAM 64GB 내, GPU 0.
- **시드**: 결정적.

#### P2-C1 — 최저비용 고전 ML 사다리

- **가설**: 고정 graph-stat 피처만으로 P1 대비 필요한 lift를 얻을 수 있다.
- **모델**: logistic, HistGradientBoosting.
- **지표**: Δ_main 대 frozen P1, F1/P/R/PR-AUC, train/inference 시간, shuffle control.
- **합격선**: 패킷 밴드와 동일하게 Δ_main ≥ +0.10이면 고전 ML이 H2 관련 정보의 저비용 해법을 이미 포착한 것.
- **킬/정지**: HistGradientBoosting이 support band를 충족하면 production ladder에서 GNN을 중단한다. logistic이 충족하면 tree도 생략 가능하다. shuffle ROC-AUC > 0.55면 해당 pipeline은 누수 의심으로 무효.
- **예산**: CPU 1일, GPU 0.
- **시드**: 세 seed; deterministic 설정이면 동일 결과 여부를 증거로 기록.

#### P2-C2 — GraphSAGE 주효과

- **가설**: 고정 aggregate로 충분하지 않은 다중-hop 관계가 P1 대비 F1을 높인다.
- **모델**: name-masked edge-conditioned GraphSAGE.
- **지표**: Δ_main, seed 분산, per-drawing F1, PR-AUC, recall/precision, runtime.
- **합격선**: Δ_main ≥ +0.10은 H2 지지 후보; 0 ≤ Δ_main < +0.10은 demote; Δ_main < 0은 현 계측기 아래 H2 kill.
- **킬 조건**: 패킷 밴드 그대로. GPU 18시간 기본 예산을 넘거나 seed 방향이 불일치하면 승격하지 않고 불안정으로 기록.
- **예산**: RTX 5070 Ti 최대 18 GPU-hours, CPU shard 준비 별도.
- **시드**: 고정 세 seed, test는 세 seed logit 평균.

#### P2-C3 — 문맥 귀속 ablation

- **가설**: C2의 lift는 node encoder가 아니라 실제 relation topology에서 온다.
- **arm**: FullEdge, NoMessage, degree-preserving EdgeShuffle. node feature와 parameter budget은 동일하게 유지.
- **지표**: Δ_context, FullEdge−EdgeShuffle, drawing/def bootstrap interval.
- **합격선**: Δ_context의 95% cluster-bootstrap interval 하한 > 0이며 FullEdge가 EdgeShuffle보다 높아야 함. 동시에 C2의 Δ_main band를 충족해야 함.
- **킬 조건**: Δ_main은 좋아도 Δ_context 하한 ≤ 0이면 “GNN 문맥” 주장을 kill한다. 이 경우 feature encoder 효과로 재분류하며 classical/MLP 사다리로 돌린다.
- **예산**: C2 checkpoint 재사용 포함 최대 12 GPU-hours.
- **시드**: 고정 세 seed, 같은 minibatch order manifest.

#### P2-C4 — 이름/레이어 mask와 H3 경보

- **가설**: H2의 기하 문맥 lift는 layer/name 없이 유지된다.
- **arm**: FullName, NameMask, NameOnly, layer-token permutation.
- **지표**: Δ_name, mask 후 Δ_main band, name-only F1, silver rationale evidence class별 drop.
- **제안 합격선**: NameMask arm 자체가 Δ_main ≥ +0.10을 유지하고, Δ_name < 0.05.
- **경보/킬**: Δ_name ≥ 0.05이거나 mask로 support band에서 demote/kill band로 떨어지면 누수/H3 경보. name-blind arm이 P1을 넘지 못하면 H2 승격 금지. 이것은 H3 증거일 수 있으나 silver 학습의 안전성을 보장하지 않는다.
- **예산**: RTX 최대 6 GPU-hours. embedding을 제외한 arm은 checkpoint 구조를 공유하지 않고 독립 train.
- **시드**: 고정 세 seed.

#### P2-C5 — truth-source 전이와 proxy 독립성

- **가설**: 학습된 관계가 source 고유 prior가 아니라 다른 표현에도 전이된다.
- **설계**: train {eligible synthetic, FloorPlanCAD, CubiCasa, eligible silver} × eval {동일 source와 타 source}; target threshold 재튜닝 금지.
- **지표**: transfer F1/PR-AUC, diagonal/off-diagonal gap, 동일-instance error correlation, prediction-family collapse.
- **합격선**: H2 승격에는 최소 두 적격·비중복 source에서 Δ_main 방향 일치가 필요. proxy family-collapse rule에 걸린 둘은 한 source family로 셈.
- **보조 kill**: synthetic-trained GNN이 FloorPlanCAD에서 frozen deterministic baseline보다 낮으면 “synthetic 분포 충분” 보조가정 kill. H2 본체와 분리 기록.
- **본체 정지**: 한 source만 적격이거나 off-diagonal이 모두 baseline 이하이면 H2 승격 불가; test 미소비.
- **예산**: source당 CPU build 0.5–1일, 적격 train-source당 RTX 최대 18 GPU-hours.
- **시드**: 고정 세 seed.

#### P2-C6 — silver gate-only 대 distillation 통제

- **가설**: silver를 train target으로 넣는 것이 단순 gate-only 사용보다 실제 일반화를 높이며 판정자 버릇을 복제하지 않는다.
- **arm**: NoSilver, SilverGateOnly, SilverDistill-1epoch. 세 arm 모두 같은 non-silver train과 split 사용.
- **지표**: non-silver val Δ_main, name-mask drop, family별 error, rationale evidence distribution.
- **합격선**: SilverDistill이 NoSilver와 GateOnly보다 non-silver val에서 개선되고 name-masked arm에서도 방향이 유지되어야 함.
- **킬 조건**: silver 내부에서만 상승하거나 name mask 후 소실되면 distillation arm kill. silver B1/B4 미통과 시 cell 자체 비활성.
- **예산**: RTX 최대 9 GPU-hours.
- **시드**: 고정 세 seed.

#### P2-C7 — scale·metamorphic·대형 graph 안정성

- **가설**: 선택 model이 graph chunking과 허용 변환에서 의미 없는 예측 변화를 만들지 않는다.
- **입력**: 145장 modelspace와 sentinel, label 없어도 실행 가능.
- **지표**: 강체/단위/scale/name-rename prediction consistency, zero-wall FP, all-wall recall, chunk/full parity, peak RAM/VRAM, latency.
- **합격선**: 기존 배터리의 강체·단위 불변성을 후퇴시키지 않고, proposed chunk parity gate를 충족하며 zero/all-wall sentinel을 통과.
- **킬/정지**: zero-wall detector나 all-wall detector가 metric 허점을 이용하면 무효. max def에서 cap truncation 또는 OOM으로 handle을 누락하면 전체 scale claim 금지. 기존 scale arm FAIL 0.7624를 숨기지 않고 별도 보고.
- **예산**: CPU 1일, RTX inference 최대 6시간. DGX 사용 안 함이 기본.
- **시드**: 선택 ensemble 1개, 변환 생성 seed 고정.

#### P2-T1 — 최종 test 단발

- **가설**: val에서 봉인한 선택 규칙이 untouched test에 유지된다.
- **진입 조건**: G0/G1 PASS, C1 Occam gate가 GNN을 중단시키지 않음, C2–C4 PASS, C5에서 두 source concordance, evidence completeness PASS.
- **지표**: frozen P1, selected classical, selected GNN의 per-handle F1/P/R/PR-AUC와 drawing-level 분포.
- **합격선/킬**: 패킷의 Δ_main band를 그대로 적용. test에서 Δ_main < 0이면 H2 kill, 0 이상 0.10 미만이면 demote, 0.10 이상이면 지지. 단, context/name/source 조건을 모두 만족해야 최종 승격.
- **예산**: inference 1회, 재실행 금지. 인프라 실패는 prediction file이 생성되기 전이면 failure log 후 동일 immutable checkpoint로 재개할 수 있으나, metric을 본 뒤 재실행하지 않음.
- **시드**: 세 seed logit ensemble으로 사전 봉인.

### 6.3 의사결정 순서

1. G0 또는 G1 실패 → P2 학습 금지.
2. C1의 logistic/GBDT가 support band 충족 → GNN production 후보 kill, 고전 ML 승격 검토.
3. C1이 부족 → C2 GraphSAGE.
4. C2가 support band 미달 → H2 demote/kill, GAT 재탐색 금지.
5. C2 통과하나 C3 실패 → “딥 모델 효과”일 수는 있으나 “그래프 문맥 효과” kill.
6. C3 통과하나 C4 실패 → 이름 누수/H3 경보, H2 승격 금지.
7. C5에서 두 독립 source 미확보 → H2 unresolved, test 미소비.
8. 모두 통과 → C7 안정성 후 T1 단발.

---

## 7. red team 티켓 응답

패널 본문이 P2 또는 CL-F에 직접 연결한 티켓과, P2 실행에 교차 적용되는 프로그램 티켓을 구분한다. 상세 티켓 원문 전체가 패킷에 실리지 않은 경우에는 패널이 제공한 범위를 넘어 내용을 상상하지 않는다.

| 티켓 | P2 관련성 | 응답 | 현재 판정 |
|---|---|---|---|
| T1 — truth proxy 독립성 | synthetic/FPC/silver concordance가 같은 평행 이중선 prior의 중복 확증일 위험 | 동일-instance bridge에서 prediction뿐 아니라 error dependence를 측정하고, 강하게 결박된 proxy는 한 family로 센다. 단순 cross-dataset transfer로 T1을 닫지 않는다. | OPEN, P2 승격 하드 게이트 |
| T2 — wall synthetic generator 부재/충실도 | synthetic train arm의 토대 | explicit per-handle wall truth와 negative/sentinel을 가진 CL-C 생성기가 B1 fidelity gate를 통과하기 전 arm 비활성. 현재 KS 0.5792, TV 0.265 FAIL을 그대로 수용한다. | BLOCKED |
| T5 — 외부셋 license/counsel | CubiCasa/FloorPlanCAD 학습 적법성 | 프로그램 GO와 권리 clearance를 분리한다. counsel memo가 dataset, 원 도면, 파생 SEG-IR, model weight 사용 범위를 서면으로 clear할 때까지 학습하지 않는다. | BLOCKED |
| T6 — 평가 단위 혼동 | GNN node 분류와 집합 조립 혼합 위험 | primary를 per-handle wall_member로 고정한다. room/집합 조립은 별 proposal/output으로 격리하고 P2 reward나 metric에 섞지 않는다. | 설계상 수용, evidence 필요 |
| T7 — zero-wall detector 허점 | metamorphic violation-only metric의 허점이 C7에도 적용 | zero-wall/all-wall sentinel과 recall floor를 C7에 필수화한다. 일관되게 아무것도 탐지하지 않는 모델을 PASS시키지 않는다. | 구현 전 OPEN |
| T9/T21 — baseline 선계측 | 새 P1과 기존 v1/GBDT 수치 혼용 위험 | CL-B P1을 version/hash와 함께 동일 split에서 먼저 재측정한다. 기존 v1 0.2358과 GBDT 0.517은 사전 정보이며 새 Δ의 분모로 대체하지 않는다. | P1 동결 전 BLOCKED |
| T10 — P2 silver 식별자 및 Graph IR 선결 | 원 제안의 B1-only 조건 오류와 adjacency 문제 | silver gate를 B1 ≥ 0.70 AND B4 ≥ 0.70으로 정정했다. G1 adjacency audit를 학습 전 하드 게이트로 둔다. | 정정 반영, 실측 OPEN |
| T14/T33 — firm/layer lexicon | layer embedding이 관례 prior와 누수를 섞을 위험 | train-only vocabulary, UNK, NameMask/NameOnly/token permutation을 사용한다. firm/project lineage split 없이는 layer feature를 승격 model에 넣지 않는다. | OPEN |
| T15 — seed confounding | learned cell을 한 seed로 비교할 위험 | 모든 learned arm에 동일 세 seed를 사용하고 seed별 결과를 모두 보고한다. 최종은 사전 봉인한 logit ensemble이다. | 설계상 반영 |
| T17 — truth-source 교차요인 | train/eval source 대각만 좋아지는 bootstrap chain 위험 | C5의 train-source × eval-source matrix와 동일-instance proxy audit로 CL-E에 병합한다. target threshold 재튜닝을 금지한다. | 실행 전 OPEN |
| T22 — P1 hard prerequisite | P1이 완성되지 않은 상태의 lift 주장은 무의미 | G0에서 frozen CL-B P1과 evidence completeness 없이는 C1 이후를 실행하지 않는다. | BLOCKED |
| T23/R23 — adjacency 완전성 disputed | Graph IR이 실제 relation을 누락하면 H2 측정기가 불완전 | exhaustive reference recall, cap truncation, transform parity, large-def stress를 G1에 둔다. 실패 시 architecture가 아니라 IR을 수정하고 version을 올린다. | BLOCKED |
| T24 유사 위험 — pixel→handle/segment 역투영 | 원래 CL-G 티켓이지만 FPC raster bridge에도 같은 CRS/정합 위험이 적용 | synthetic render round-trip에서 segment-label mapping을 먼저 검증한다. 실패 시 FPC는 per-handle truth가 아니다. | 교차 적용, OPEN |
| T34 — load-bearing citation status | 일반 문헌을 실행 증거처럼 쓰는 위험 | 문헌은 mechanism 계보로만 사용하며 실험 실행 증거로 쓰지 않는다. 서지 불확실 CubiCasa 항목은 요검증 표시. 모든 성능 수치는 패킷 다이제스트만 사용했다. | 문헌 검증은 OPEN, 실험 주장 없음 |

### 7.1 판정자 Goodhart 대응

silver rationale를 단순 텍스트 embedding으로 쓰지 않는다. rationale는 evidence class 감사에만 사용한다. 예를 들어 geometry, junction, name/layer, drawing convention 같은 사전 정의 class로 분류하고, 가족별 분포를 기록한다. 특정 가족이 name/layer class에 치우치고 그 silver로 학습한 model만 name-mask에서 붕괴하면 오염 증거다.

### 7.2 미해소 위험의 수용

- 현재 자산만으로는 synthetic/FPC/E1.5 세 source가 모두 적격이 아니다.
- 동일-def 3원 비교는 bridge를 새로 만들지 않으면 성립하지 않는다.
- 외부 raster truth를 CAD handle truth와 동일시할 수 없다.
- 384 def와 최대 412,775 선분 규모에서 adjacency 완전성과 compute 가능성은 아직 관측되지 않았다.
- 따라서 이 도시에 자체는 실행 계획을 완성하지만, P2 방법론이 PASS했다는 주장을 만들지 않는다.

---

## 8. 인접 제안과의 관계

### 8.1 병합해야 하는 지점

**CL-A E1 법의학 감사**

silver의 handle 실재성, INSERT 깊이, bbox 단위, 정렬 artifact가 틀리면 P2 silver arm도 오염된다. CL-A 결과를 silver eligibility manifest의 upstream evidence로 소비한다. P2가 같은 법의학을 중복 구현하지 않는다.

**CL-B coverage-complete P1**

P1은 P2의 normalizer, candidate relation seed, frozen 비교 baseline이다. INSERT world transform, LWPOLYLINE/MLINE/ARC/SPLINE normalization, 단위 정박이 P1에서 해결되어야 한다. P2가 자체 normalizer를 별도로 만들어 baseline을 바꾸면 공정 비교가 아니다.

**CL-C wall synthetic truth와 WSD-EVAL-v1**

synthetic graph label, hidden mutation, per-handle 평가 universe를 그대로 소비한다. fidelity FAIL 상태에서는 사용하지 않는다.

**CL-D metamorphic battery**

P2-C7의 강체, 단위, scale, explode, layer rename consistency를 공용 battery에 연결한다. zero/all-wall sentinel을 함께 사용한다.

**CL-E truth-source 교차요인**

C5의 train×eval matrix와 proxy family audit를 CL-E 산출물로 병합한다. P2 전용 표와 프로그램 공용 표가 다른 split을 쓰지 않게 한다.

**CL-I convention prior**

NameFull/NameMask/NameOnly 결과는 H3와 firm-specific lexicon 실험의 직접 입력이다. 이름이 유효하더라도 H2 score와 분리한다.

**CL-K anti-silver**

NoSilver/GateOnly/SilverDistill-1epoch arm을 P2-C6에 상설 통제로 넣는다. silver를 신호로 보는 입장과 오염원으로 보는 반대의견을 평균으로 지우지 않는다.

### 8.2 차별점

- CL-B는 결정 규칙과 coverage를 고친다. P2는 그 위에서 **학습된 다중-hop relation**의 추가 기여만 측정한다.
- CL-E는 source 간 불일치 구조가 주 대상이다. P2는 그 결과를 승격 조건으로 소비하면서 node classifier를 학습한다.
- CL-G raster/VLM은 pixel→handle 의미 추론이 중심이다. P2의 FloorPlanCAD arm은 raw raster에서 독립 추출한 기하 graph의 transfer 보조축일 뿐이다.
- CL-H RL은 집합 조립·획득·routing을 다룬다. P2는 supervised per-handle 분류이며 RL reward를 쓰지 않는다.
- CL-J room/face-first는 표현 방향을 뒤집는다. P2는 entity candidate graph를 유지한다. CL-J가 messy real에서 명백히 우세하면 P2 graph 표현 자체를 재검토해야 한다.

### 8.3 이 제안이 죽어야 하는 조건

다음은 정직한 종료 조건이다.

1. **Occam kill**: 동일 Graph IR의 logistic 또는 HistGradientBoosting이 frozen P1 대비 +0.10 band를 채우고 GNN이 proposed equivalence margin 0.02 F1 안에서 동률이면 GNN은 불필요하다. 더 비싼 architecture 탐색을 하지 않는다.
2. **primary H2 kill**: untouched held-out에서 Δ_main < 0.
3. **H2 demote**: 0 ≤ Δ_main < +0.10. 양수라는 이유만으로 승격하지 않는다.
4. **context attribution kill**: Δ_main이 좋아도 FullEdge−NoMessage의 cluster-bootstrap 하한이 0 이하이거나 EdgeShuffle과 차이가 없으면 “그래프 문맥” 주장을 폐기한다.
5. **name leakage kill**: NameMask arm이 P1을 넘지 못하고 FullName만 좋아지면 P2의 기하 문맥 주장은 죽는다. 결과는 H3/누수 조사로 넘긴다.
6. **source concordance failure**: 최소 두 적격·비중복 source에서 방향이 일치하지 않으면 일반 방법론 승격을 죽인다. 한 source 전용 model로만 남길 수 있다.
7. **synthetic auxiliary kill**: synthetic-trained GNN이 FloorPlanCAD의 적격 transfer eval에서 deterministic baseline보다 낮으면 “synthetic 분포 충분” 가정을 폐기한다. H2 본체와 혼동하지 않는다.
8. **instrument kill**: Graph IR adjacency recall, transform parity, chunk parity가 gate를 못 넘으면 현 계측기에서 P2를 중단한다. 이는 H2가 거짓이라는 증거가 아니라 실험 장치 부적격 판정이다.
9. **silver contamination kill**: silver benefit가 silver 내부와 NameFull에서만 나타나거나 두 판정자 가족의 버릇을 그대로 복제하면 silver distillation arm을 폐기한다.
10. **운영 kill**: 로컬 예산 안에서 max def의 모든 handle을 누락 없이 처리할 수 없고 DGX가 계속 불통이면 145장 scale claim을 철회한다. 작은 benchmark 결과를 전체 운영 가능성으로 확대하지 않는다.

### 8.4 최종 권고

지금 당장 실행할 순서는 G0의 권리·P1·silver status 확인, G1 Graph IR adjacency audit, C1 logistic/HGBDT다. 이 세 단계 중 어느 하나라도 GNN의 필요성을 없애거나 측정기를 부적격으로 만들면 중단한다. GraphSAGE는 이 관문을 모두 지난 뒤에만 실행한다.

기존 CubiCasa 결과만 놓고 보면 고전 ML은 이미 결정론 v1보다 훨씬 강한 경쟁자다. 그러나 v1 F1 0.2358과 GBDT F1 0.517의 차이를 새 P1 대비 P2의 확정 lift로 바꾸어 말해서는 안 된다. 새 P1, 동일 Graph IR, 동일 split, 이름 mask, source concordance가 맞물린 실험에서만 H2를 판정한다. 이 엄격한 조건에서 GNN이 살아남으면 “딥러닝이 좋았다”가 아니라 “학습된 관계 문맥이 실제로 추가 정보를 제공했다”는 좁고 검증 가능한 결론을 얻게 된다.

DOSSIER_COMPLETE: platt_P2
