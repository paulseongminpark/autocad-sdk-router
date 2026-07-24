# E2 방법론 심층 도시에 — calibration_P3

**제안 ID**: P3 — DWG Graph IR용 self-supervised heterogeneous GNN (자기지도 이종 그래프 신경망)  
**좌석**: calibration_forecaster · seat_id=`calibration_P3`  
**클러스터**: CL-F (학습 사다리 고전ML→PU→GNN의 **GNN 정점**; VIABLE 밴드 · 조건부)  
**작성 기준일**: 2026-07-18 (패킷 실측 다이제스트 및 패널 보고서 서술만 수치 인용)

> **좌석 정체성 메모.** 이 좌석은 calibration_forecaster다. 따라서 이 도시에의 축은 "GNN이 멋지다"가 아니라 **"P3의 주장(claim)이 사전등록 밴드로 언제 참/거짓으로 해결(resolve)되는가, 그리고 그 예보(forecast)를 지금 낼 자격이 있는가"** 이다. 패킷 calibration 블록은 `forecast=null`(수치 abstain), `abstain_flag=empty_reference_class`, `reference_class=RC-WALL-ZL (n=0, n_min=5)`로 이미 **"독립 해결 사례 없음 → 지금은 수치 예보를 봉인"** 을 선언했다. 본 도시에는 그 abstain을 **어떤 관측이 도착하면 풀리는가**로 조작화(operationalize)하는 것을 최우선으로 삼는다.

---

## 0. 한 문단 요약 (먼저 결론)

P3는 DWG를 **이종 그래프**(node = {엔티티, 블록정의, 블록참조, 레이어, 텍스트앵커}, typed edge = {containment, instancing, intersection, proximity, parallelism, collinearity})로 표현하고, **라벨 없는 도면으로 자기지도 사전학습**(masked-attribute 복원 + transform-contrastive)한 뒤 **합성/FloorPlanCAD truth로 node 벽멤버십과 wall-pair 관계를 공동 파인튜닝**한다. 출력은 결정론 topology gate를 **대체하지 않는** soft evidence다. 이 방법의 유일한 존재 이유는 — 고전 ML(GBDT)이 이미 val F1 0.517/AUC 0.9215를 냈음을 아는 상태에서 — **"국소 피처로는 안 보이지만 이웃 위상(topology)으로는 보이는" 벽/비벽 구분**(예: 화살표·문·창·치수·경계선처럼 대역 내 평행이지만 벽이 아닌 구조)을 message passing으로 회수하고, **좌표 px·축척 미상**이라 물리 두께 prior가 무력화된 전이 실패(val F1 0.2358)를 **스케일-불변 관계 피처**로 우회하는 것이다. 그러나 P3는 **Occam 사다리의 가장 위 칸**이므로, GBDT(P2) 위에서 사전등록 lift를 **동결 held-out에서** 내지 못하면 죽어야 한다. 그리고 그 판정에 앞서 **adjacency 감사(synthetic relation recall ≥0.98)** 와 **생성기 실존(PR-1) + 충실도 게이트(B1 현재 FAIL KS 0.5792)** 가 하드 선결이다.

---

## 1. 이론적 근거·선행연구

### 1.1 핵심 주장(claim)과 이 제안의 계보상 위치

패킷의 `claim`: **"P3가 최선의 비-GNN baseline보다 동결 held-out에서 사전등록 lift를 내면서 compute·calibration gate를 통과한다."** 이 주장의 구조를 분해하면:

1. **비교 대상이 명시적**이다 — "최선의 비-GNN baseline". 다이제스트상 이는 CubiCasa 기하 GBDT(HistGradientBoosting, val F1 0.517/AUC 0.9215)다. 즉 P3는 절대 성능이 아니라 **GBDT 대비 증분(lift)** 으로 심판받는다. 이것이 P3를 CL-F 사다리의 정점에 놓는 이유이자 Occam 게이트다: "로지스틱/GBDT가 먼저 뛰면 GNN 불요"(패널 CL-F 조건).
2. **이중 게이트**다 — 성능 lift **와** compute·calibration gate를 **동시에** 통과해야 한다. compute(peak RAM ≤48GB, edge/메모리 production p95 봉투)와 calibration(REL≤0.03, RES≥0.03)이 성능과 별개의 kill 축이다.
3. **soft evidence 계약** — "모델 출력은 soft evidence이며 deterministic topology gate를 대체하지 않는다". P3는 결정론 판별기를 **이기려는** 것이 아니라 그 판별기가 못 보는 축을 **보완**하는 5번째 증거 채널(CL-B evidence_grid의 신규 행)로 설계된다.

### 1.2 방법론 계보 (구체 기법·시스템 — 일반 지식, 불확실 인용은 요검증)

| 계보 축 | 대표 기법·시스템 (일반 지식) | P3에서의 역할 |
|---|---|---|
| **이종 그래프 신경망(heterogeneous GNN)** | R-GCN(관계별 weight 행렬; Schlichtkrull et al. 2018, 요검증 연도) · HAN(meta-path attention; Wang et al. 2019, 요검증) · **HGT**(Heterogeneous Graph Transformer, type-aware mutual attention; Hu et al. 2020, 요검증) · R-GAT | typed edge 6종·node 5종을 관계별 파라미터로 처리. 특히 instancing(참조→정의)은 homogeneous로 뭉개면 소실 |
| **귀납적·샘플링 GNN** | GraphSAGE(neighbor sampling, inductive; Hamilton et al. 2017, 요검증) · Cluster-GCN · GraphSAINT(subgraph sampling) | 412,775 선분 규모 단일 도면을 16GB GPU에 올리기 위한 **미니배치·서브그래프 샘플링**의 근거 |
| **메시지 패싱 일반** | MPNN 프레임워크(Gilmer et al. 2017, 요검증) | node 피처 + typed edge → 이웃 집계의 수식 골격 |
| **자기지도: 속성 마스킹** | attribute masking(Hu et al. "Strategies for Pre-training GNNs", 2020, 요검증) · **GraphMAE**(masked autoencoder; Hou et al. 2022, 요검증) | 라벨 없는 145장 + 384-def에서 node 속성 복원으로 표현 사전학습 |
| **자기지도: 대조학습** | DGI(Deep Graph Infomax; Veličković et al. 2019, 요검증) · GRACE · GraphCL(augmentation contrastive; You et al. 2020, 요검증) · **BGRL**(Bootstrapped Graph Latents, negative-free; Thakoor et al. 2021, 요검증) | transform-contrastive의 이론적 모체. **BGRL의 음성쌍 불요 특성**은 16GB 메모리 예산에 직접 유리 |
| **불변성으로서의 augmentation** | SimCLR/InfoNCE 계열의 "의미보존 변형에 불변"(비전 일반 지식) | transform-contrastive의 view = **B4 불변성 시험의 변환군**(강체·스케일·단위). 즉 우리 하네스가 이미 정의한 불변군을 SSL 목표로 재사용 |
| **CAD/평면도 그래프 이해** | FloorPlanCAD(panoptic symbol spotting on CAD; Fan et al. 2021, 요검증) · GAT-CADNet(CAD를 그래프로, 상대 공간 인코딩; Zheng et al. 2022, 요검증) · CADTransformer(2022, 요검증) · SymPoint(CAD primitive를 point로; 2023~2024, 요검증) | 도메인 선례. **개별 논문의 수치 성적은 본 패킷에 없으므로 인용하지 않음**; 메커니즘만 계보로 사용 |
| **soft evidence 융합** | mixture-of-experts · stacking · calibrated evidence fusion(ML 일반) | P3 출력을 결정론 4채널(parallel/thickness/junction/layer) 위에 얹는 방식 |

> **요검증 정책.** 위 표의 저자·연도는 일반 지식에서 회상한 것이며 본 패킷에 근거가 없다. 특정 논문의 **성능 수치는 일절 인용하지 않는다**(패킷 계약: 수치는 다이제스트에서만). 방법의 **메커니즘·이름**만 계보로 사용한다.

### 1.3 왜 heterogeneous인가 — homogeneous로 뭉개면 죽는 정보

CAD 도면의 구조는 **본질적으로 타입이 있다**: INSERT(블록참조)는 BLOCK 정의(block def)의 인스턴스이고, 엔티티는 레이어에 소속되며, 블록정의는 자식 엔티티를 **포함(containment)** 한다. 이 타입 구조를 homogeneous 그래프로 평탄화하면:

- **instancing 소실**: "이 300개 선분은 같은 가구 블록의 복제"라는 정보가 사라진다 → 같은 비벽 블록이 도면 곳곳에서 독립적으로 오탐될 여지(다이제스트 FP 주범: Door/Window는 전형적 블록 인스턴스).
- **proximity edge 폭증의 원인 제공**: 타입 구분 없이 근접만으로 엣지를 깔면 텍스트·치수·해치가 벽 선분과 무차별 연결되어 엣지 수가 폭발한다(패킷 명시 실패모드: "proximity edge 폭증"). 타입 인지 엣지 규칙이 폭증 제어의 1차 방어선.

### 1.4 왜 self-supervised인가 — 라벨 예산의 냉정한 회계

- 라벨 있는 진리원은 **합성(S/F/M, 아직 벽 코드 0 — PR-1 미구축)** 과 **외부셋(CubiCasa NC 라벨, FloorPlanCAD 래스터 bbox)** 뿐이고, 실도면(1.dwg, 145장)은 **라벨이 없다**.
- 자기지도는 **라벨 없는 145장 + 384-def**의 기하·위상 구조 자체를 학습 신호로 삼아, 희소한 truth를 파인튜닝에만 아끼는 표준 처방이다.
- transform-contrastive의 view를 **B4 불변군(강체 1.0 PASS / scale 0.7624 FAIL / 단위 1.0 PASS)** 으로 잡는 것은 우연이 아니다: 우리 프로그램이 이미 "이 변환에 불변이어야 한다"고 선언한 축을 SSL 목표로 승격하면, **scale 팔이 FAIL(0.7624)** 인 현행 결정론 판별기의 약점을 학습으로 메울 여지가 생긴다(§3.4).

### 1.5 계보가 예고하는 위험 (패킷 Expected failure modes와 정합)

| 위험 (패킷 명시) | 계보상 알려진 병리 | 본 도시에의 방어 위치 |
|---|---|---|
| Graph IR adjacency 누락 | 잘못된 인접 = garbage-in; GNN은 그래프가 틀리면 무력 | Cell-ADJ 선결 감사(§6), kill: synth relation recall <0.98 |
| proximity edge 폭증 | dense graph OOM·oversmoothing 가속 | §2.6 radius+k-cap+degree-cap, Cell-MEM |
| oversmoothing | 깊은 GNN에서 노드 표현 동질화 | §2.5 JK/residual·DropEdge·PairNorm·얕은 깊이 |
| block-family leakage | 같은 블록가문이 train/val 양쪽 → 낙관 편향 | §2.2 handle·순번·파일명 제거 + family fold(§6 Cell-FAM) |
| synthetic topology shortcut | 합성이 재현 못 한 단순 위상에 과적합 | Cell-OOD(style-OOD), B1 충실도(KS 0.5792) 선결 |
| NC 데이터 학습 weight 제품 혼입 | 라이선스 오염 | §4.4 NC weight 연구 격리, PR-3 게이트 |

---

## 2. 알고리즘 정확 스펙

### 2.1 그래프 정의 $G=(V, E, \tau_v, \tau_e)$

**노드 타입** $\tau_v \in$ {`entity`, `block_def`, `block_ref`, `layer`, `text_anchor`} (5종).  
패킷은 "block definition/reference"를 한 묶음으로 적었으나, 본 스펙은 **정의(def)와 참조(ref)를 분리 노드**로 둔다 — 그래야 instancing 엣지가 `block_ref → block_def`로 명시되어 "같은 정의의 여러 인스턴스"가 파라미터 공유로 묶인다(§1.3의 instancing 소실 방지).

**엣지 타입** $\tau_e \in$ {`containment`, `instancing`, `intersection`, `proximity`, `parallelism`, `collinearity`} (6종, 유향/무향 혼재):

| 엣지 | 방향 | 구성 규칙 (결정론) |
|---|---|---|
| containment | 유향 | `layer → entity`, `block_def → child_entity` |
| instancing | 유향 | `block_ref → block_def` (INSERT의 참조) |
| intersection | 무향 | 두 엔티티 기하 교차 (segment-segment intersect) |
| proximity | 무향 | 두 엔티티 최단거리 ≤ `r_prox` **AND** §2.6의 cap 통과 |
| parallelism | 무향 | 각도차 ≤ `θ_tol`(현행 결정론 2° 준용 후보) 그리고 수직 오프셋 ∈ 두께대역 |
| collinearity | 무향 | 각도차 ≤ `θ_tol` **AND** 수직 오프셋 ≈ 0 |

parallelism/collinearity/intersection은 **탐지기 v1의 기하 로직을 그대로 재사용**(각도 2°·overlap 0.5·snap 6mm)해 결정론적으로 깐다. 즉 그래프 구성은 학습이 아니라 **감사 가능한 결정론 스크립트**이며(Cell-ADJ의 대상), 이 점이 P3의 검증 가능성 핵심이다.

### 2.2 노드 피처 $x_v$ (타입별, 누출 제거)

**누출 제거 불변식(패킷 Leakage protection)**: 모든 노드에서 **handle·순번·파일명 제거**. 레이어명·텍스트 내용은 **기본 팔에서 사용하지 않는다**(name-blind by default) — 다이제스트에서 탐지기가 이미 "레이어명 신호 0, full-vs-nb=1.0"이므로 기본 팔을 name-blind로 두어야 B5 독립성 축과 정합. 관례(레이어명) 팔은 **별도 arm**으로만 격리(→ platt/feyerabend CL-I와 접속, §8).

| 노드 타입 | 피처 (기본 팔) |
|---|---|
| `entity` | **cubicasa_ml의 6특징 재사용**: parallel / thickness / junction / log길이 / sin2θ / cos2θ + 엔티티 종류 one-hot(LINE/LWPOLYLINE/ARC/SPLINE/HATCH/INSERT) + 정규화 bbox(도면정규화, 스케일 제거) |
| `block_ref` | 인스턴스 bbox aspect · 자식 수 · 회전/스케일 flag(값 아닌 유무) |
| `block_def` | 자식 엔티티 히스토그램(종류별 개수) · 자식 수 |
| `layer` | (기본 팔) **이름 토큰 없음**; 소속 엔티티 수·종류 분포만. 관례 팔에서만 hashed 토큰 |
| `text_anchor` | 위치(정규화)만; **내용 텍스트 없음**(기본 팔). 관례 팔에서만 토큰 |

> **계측 정박 주의(FM6 회피).** 레이어/텍스트 토큰을 쓰는 관례 팔을 켤 때 cp949/UTF-8 디코드 실패는 손상으로 오진하지 말고 코드포인트로 판정·드롭+카운터(platt_P6 §2.2와 동일 규율). 기본 팔은 애초 토큰을 안 써 이 함정에 노출되지 않는다.

### 2.3 사전학습 목표 (두 손실)

**목표 A — masked-attribute 복원.** 노드 부분집합 $M$(비율 $\rho$)의 연속 속성을 마스킹→복원(MSE), 범주 속성(엔티티 종류)은 CE:

$$
\mathcal{L}_{\text{mask}} = \frac{1}{|M|}\sum_{v\in M}\Big[\underbrace{\|\hat{x}^{\text{cont}}_v - x^{\text{cont}}_v\|_2^2}_{\text{연속}} + \lambda_{\text{cat}}\,\text{CE}(\hat{c}_v, c_v)\Big]
$$

**목표 B — transform-contrastive.** 같은 그래프에 **의미보존 변환** $t_1, t_2 \sim \mathcal{T}$(강체 회전·이동·반사, 균일 스케일, 단위 환산)를 적용해 두 view를 만들고, 대응 노드 임베딩을 일치시킨다. 메모리 예산(16GB)을 고려해 **음성쌍 불요 BGRL 부트스트랩**을 1순위로, InfoNCE는 대안:

$$
\mathcal{L}_{\text{contrast}}^{\text{BGRL}} = \sum_{v} \Big(2 - 2\cdot\frac{\langle q(z^{(1)}_v),\, \bar{z}^{(2)}_v\rangle}{\|q(z^{(1)}_v)\|\,\|\bar{z}^{(2)}_v\|}\Big),\quad \bar{z}^{(2)}=\text{stop-grad}(\text{target-encoder})
$$

$$
\boxed{\;\mathcal{L}_{\text{pretrain}} = \mathcal{L}_{\text{mask}} + \alpha\,\mathcal{L}_{\text{contrast}}\;}
$$

$\mathcal{T}$를 **B4 불변군과 동일**하게 잡는 것이 설계의 요체다(§1.4·§3.4). scale 변환을 view로 포함하면, scale 팔 FAIL(0.7624)을 표현 수준에서 완화하려는 **명시적 압력**을 학습에 넣는 것이다.

**의사코드 (사전학습):**
```
for step in pretrain_steps:
    G_sub = subgraph_sample(corpus_145+384, fanout, batch_nodes)   # GraphSAINT/neighbor
    t1, t2 = sample_transforms(T_invariance)                       # rigid, scale, unit
    V1, V2 = augment(G_sub, t1), augment(G_sub, t2)
    Z1 = online_encoder(V1);  Z2 = target_encoder(V2).detach()
    # masking branch on V1
    Vm, mask = mask_attributes(V1, rho)
    Xhat = decoder(online_encoder(Vm))
    L = L_mask(Xhat, V1, mask) + alpha * L_bgrl(project(Z1), Z2)
    L.backward(); opt.step()
    ema_update(target_encoder, online_encoder)                     # BGRL EMA
```

### 2.4 파인튜닝 (node + edge 공동)

두 헤드를 **공동 학습**:

- **node head**: 엔티티 노드별 벽 멤버십 $\hat{y}^{\text{node}}_v = \sigma(\text{MLP}(h_v))$.
- **edge head**: 후보 엣지(parallelism/proximity 엣지)별 wall-pair 관계 $\hat{y}^{\text{pair}}_{uv} = \sigma(\text{MLP}([h_u; h_v; e_{uv}]))$ — "이 두 선분이 벽 이중선을 이루는가".

$$
\mathcal{L}_{\text{ft}} = \lambda_1\,\text{BCE}(\hat{y}^{\text{node}}, y^{\text{node}}) + \lambda_2\,\text{BCE}(\hat{y}^{\text{pair}}, y^{\text{pair}}) + \beta\,\mathcal{L}_{\text{pretrain}}(\text{continued SSL 정규화, 선택})
$$

edge head가 **핵심 차별점**이다: 결정론 판별기의 손튜닝 `parallel` 스칼라(가중 0.35)를 **학습된 쌍-판정**으로 대체 시도한다. 단 §7 T1에서 논하듯 이는 "평행 이중선 prior 증폭" 위험의 진원이기도 하다.

### 2.5 아키텍처·하이퍼파라미터 공간

| 항목 | 공간 (val에서만 탐색) | 비고 |
|---|---|---|
| backbone | {R-GCN, HGT} | HGT는 type-attention, 파라미터 多; R-GCN 경량 |
| 레이어 수 $L$ | {2, 3, 4} | probe는 3 고정(패킷: 3-layer) |
| hidden dim | {64, 128, 256} | 16GB 상한 고려 |
| heads(HGT) | {2, 4} | |
| anti-oversmoothing | {JK-concat, residual} × {DropEdge $p\in\{0,0.1,0.2\}$} × {PairNorm on/off} | oversmoothing 방어 |
| mask ratio $\rho$ | {0.15, 0.3, 0.5} | GraphMAE류 |
| $\alpha$(contrast weight) | {0.5, 1, 2} | |
| $r_{\text{prox}}$, k-cap, degree-cap | §2.6 | 엣지 폭증 제어 |
| sampling fanout | {[10,10], [15,10,5]} | 메모리·수용영역 tradeoff |
| lr / wd | {1e-3, 3e-4} / {0, 1e-4} | |
| $\lambda_1:\lambda_2$ | {1:1, 2:1} | node/edge 균형 |

### 2.6 proximity 엣지 폭증 제어 (설계 필수)

proximity 엣지는 순진하게 깔면 $O(n^2)$ 또는 dense $k$로 폭발한다(412,775 선분 도면에서 치명적). 3중 상한:

1. **radius cap**: 최단거리 ≤ $r_{\text{prox}}$ (두께대역 50~400mm의 상수배로 정박, 스케일 미상 도면은 도면 대각선 정규화 후 상대 반경).
2. **k-NN cap**: 각 노드 proximity 차수 ≤ $k$ (기본 $k=8$ 후보).
3. **degree cap + 로그**: 잔여 초과 노드는 절단하고 **절단율을 로그**(silent 절단 금지 — FM 회피). Cell-MEM에서 엣지 수 분포·p95를 **production 봉투와 대조**(패킷 kill: edge/메모리 production p95 초과 시 GNN 경로 중단).

### 2.7 입·출력 계약

**입력**: (a) CubiCasa `cubicasa_ir`의 SEG-IR(레이어 중립, 라벨 누출 0) → 그래프, (b) 1.dwg staged DXF → 그래프. 조인 키 = SEG-IR edge id 또는 handle(단 handle은 피처에서 제거, 조인에만).  
**출력**:
- `wsd_eval_p3.json` — node/edge soft score, 셀별 지표, **resolution_trigger 산출물**(패킷: 이 파일 생성 = 해결 트리거).
- `graph_manifest.json` + `model_hash` — **동결 대상**(패킷 resolution_trigger: manifest·hash 동결 후 eval).
- soft score → `fast_score`(NumPy 채점기)·`evidence_grid`(신규 증거 채널)로 전달.

---

## 3. 벽 과업 적응 설계 — 세 하네스 축 접속

### 3.1 CubiCasa5k SEG-IR 벡터축 (P3 주 훈련장)

- 전량 SEG-IR 변환(실패 0), train 4,200(386만 선분)/val 400(35.4만)/test 400(37.5만), 벽 선분율 ~11.8%, **레이어 중립(라벨 누출 0)**.
- **적합성**: SEG-IR은 벡터 primitive 스트림이라 그래프로 직행 가능. 레이어 중립이므로 기본 name-blind 팔과 완벽 정합.
- **비적합성(정직)**: 좌표 px·**축척 미상**(벽두께 px p50=22), 그리고 다이제스트가 못박은 사실 — 기하 탐지기 전이가 **축척 2~15mm/px 전 구간 무감**, val F1 0.2358(P 0.134 ≈ 기저율 0.118, R 0.981). 즉 **물리 두께 prior가 무력**한 데이터셋. P3는 이 축을 **주 학습·val 튜닝장**으로 쓰고 test 400은 **단발**(무접촉 유지, 다이제스트 원칙).

### 3.2 FloorPlanCAD 래스터축 (P3의 비-native 축)

- 래스터 5,308장 + 벽 bbox/segmask, **벡터 SVG 없음**.
- **정직한 한계**: 그래프는 벡터 primitive를 요구한다. 래스터 픽셀은 P3 그래프에 **직접 못 들어간다**. 따라서 FloorPlanCAD는 P3의 native 축이 아니다. 접속은 두 경로뿐: (i) 래스터→벡터화가 별도 선검증되면 노드 소스(범위 밖, CL-G 영역), (ii) **래스터 축은 CL-G(VLM/래스터)에 위임**하고 P3는 벡터축(CubiCasa)·실도면축(1.dwg)만 담당. 본 도시에는 (ii)를 채택 — P3가 FloorPlanCAD 래스터를 truth로 억지 접속하지 않는다.
- 패킷 "Truth source"는 "FloorPlanCAD line truth"를 언급하나, 다이제스트 자산은 "래스터+bbox/segmask(벡터 SVG 없음)". 이 **불일치는 열린 티켓**으로 §7에 노출(FloorPlanCAD line truth의 벡터 실재성 미확인 → 요검증·PR 조달 대상).

### 3.3 1.dwg 실도면축 (사전학습 코퍼스 + 독립성 기준)

- 도면정의 384개, **최대 도면정의 412,775 선분**(연산 병목 실증치). 145장 아카이브 = 사전학습 비라벨 코퍼스(패킷 mechanism).
- 블록/INSERT/레이어가 **실존** → instancing·containment 엣지가 의미를 갖는 유일한 축.
- B3 벽-제로 도면율 0.682(v0)→0.2135 PASS(밴드 ≤0.40), B5 탐지기↔silver Pearson 0.2911, full-vs-nb 1.0(탐지기 레이어 신호 0). P3의 node soft score를 이 축에서 silver와 상관 감사 → **독립성 축**(§7 T1).

### 3.4 GBDT 0.517·전이 0.236을 아는 상태에서 P3의 추가분 (핵심 정당화)

| 기존 실측 | 함의 | P3가 가져오는 것 (가설) |
|---|---|---|
| 기하 GBDT val P 0.860 / R 0.370 / F1 0.517 / AUC 0.9215 (6 국소 피처) | 국소 피처만으로 **정밀도는 이미 높다**(0.86). 여백은 **재현율 0.370**에 있다 | topology message passing으로 **연결된 부분벽 회수** → R 상승 여지. GBDT는 이웃의 벽-여부를 못 본다 |
| 전이 val F1 0.2358, 축척 2~15mm/px **무감** | 물리 두께 prior 무력 | 관계 피처는 **스케일-자유**; transform-contrastive가 scale 불변을 **명시 학습**(scale 팔 0.7624 FAIL 완화 압력) |
| FP 주범 = Direction 화살표/BoundaryPolygon/Door/Window/DimensionMark (전부 대역 내 평행) | 국소적으론 벽과 **구분 불가**한 평행 구조 | 이들은 **문맥이 다르다**(블록 인스턴스, 텍스트 앵커 근접, 폐곡선 경계). GNN 이웃 집계가 국소 동일·문맥 상이를 분리 가능 — **GBDT가 원리적으로 못 하는 것** |
| min-length 필터 천장 F1 0.335(80px) | 길이 필터로는 긴 평행 비벽 못 거름 | edge head가 "이 평행쌍이 벽 이중선인가"를 **학습** (길이 무관 관계 판정) |
| 로지스틱 F1 0.053 | 선형 불충분 → 비선형 필요 | GBDT가 비선형을 이미 잡음. GNN의 추가 가치는 **관계**여야지 단순 비선형이면 GBDT로 충분 → **Occam kill 신호** |

**calibration 좌석의 냉정한 단서 (밴드 앵커 문제).** 패킷 prereg: `AUPRC_F ≥ max(P1,P2)+0.05`. 그런데 다이제스트가 주는 GBDT 수치는 **ROC-AUC 0.9215**와 **F1 0.517**이지 **AUPRC가 아니다**. 벽 선분율 ~11.8%의 불균형에서 ROC-AUC와 AUPRC는 **크게 다르다**(ROC-AUC는 다수 음성에 낙관적). 따라서:

> **밴드 조작화 선결**: P3 판정 전에 **P2(GBDT)의 AUPRC_F를 동결 split에서 먼저 측정**해 `max(P1,P2)`의 실제 앵커 수치를 봉인해야 한다. 그 전엔 "F1 0.517을 이겼다"가 밴드 통과를 뜻하지 않는다. 이것이 T22(P1/P2 lift 밴드는 P1/P2 선측정이 하드 선결)의 P3판 조작화다.

---

## 4. 데이터·컴퓨트 요구

### 4.1 자산 매핑 (실행 가능성)

| 자산 | P3 역할 | 제약 |
|---|---|---|
| 145 아카이브 DWG/DXF + 384-def | **사전학습 비라벨 코퍼스** | 라벨 없음 → SSL 전용 |
| 1.dwg / 최대 412,775 선분 | 실도면 그래프 · silver 상관 감사 | 연산 병목 실증 → 샘플링 필수 |
| CubiCasa SEG-IR (386만/35.4만/37.5만) | **파인튜닝 truth(주)** · val 튜닝 · test 단발 | NC 라이선스(PR-3) · 축척 미상 |
| 합성 S/F/M | synthetic node/pair truth | **아직 벽 코드 0(PR-1 미구축)** · B1 충실도 FAIL(KS 0.5792) |
| FloorPlanCAD 5,308 래스터 | **P3 비접속**(CL-G 위임) | 벡터 없음; line truth 실재성 요검증 |
| RTX 5070 Ti 16GB | 로컬 probe·파인튜닝(샘플링+mixed precision) | 412k 노드 full-graph 불가 → 서브그래프 |
| RAM 64GB | 그래프·피처 CPU 상주 | prereg peak RAM **≤48GB** 밴드 |
| DGX Spark (Ornith-35B) | full-corpus pretrain·HP sweep | **unreachable(승인됨)** → 계획만, 실행 0 |
| 프런티어 VLM API | **P3 비사용** | 미승인 게이트 |
| qwen2.5-VL-3B / Zenodo10K / Text2CAD / ArchCAD / pseudo-floor-plan-12k | **P3 비사용**(CL-G/타 좌석) | — |

### 4.2 로컬 GPU 계획 (실행 본선, RTX 5070 Ti 16GB)

- **샘플링 불가피**: 412,775 선분 단일 도면을 full-graph로 16GB에 못 올린다. GraphSAINT/Cluster-GCN 서브그래프 미니배치 + neighbor sampling(fanout 상한).
- **mixed precision(AMP)** + **BGRL(음성쌍 불요)** 으로 메모리 절감(패킷 compute plan: "sampled subgraph와 mixed precision으로 probe").
- **peak RAM ≤48GB 밴드**: 386만 엣지 + 피처를 sparse CSR로 CPU 상주(수 GB급), GPU는 서브그래프만. Cell-MEM이 이 밴드를 계측·kill 판정.
- probe(패킷 cheapest): 합성 1,000 block + 실무 20장 비라벨 그래프, 3-layer GNN **pretrain 없이/있이 각 1회**, P2와 비교. 로컬 수 시간.

### 4.3 DGX 계획 (비활성 — unreachable)

- full-corpus pretraining + hyperparameter sweep **만** DGX Spark vLLM 비사용 시간대에 배치, **graph shard 단위 checkpoint**(패킷 compute plan).
- 현재 **unreachable → 대기 큐에 실행 0**. 로컬 probe·핵심 셀은 **DGX에 의존하지 않게** 설계(로컬 완결). DGX는 "스케일업 시 재개" 조건부.

### 4.4 라이선스·NC 격리 (하드 게이트)

- CubiCasa/FloorPlanCAD는 **NC 라벨 + 원 도면 권리 미해결**(패널 PR-3, R12 kill risk, R23 top unknown).
- 패킷 Leakage protection: **"NC 학습 weight는 연구 격리한다."** → NC 데이터로 학습한 체크포인트는 **제품 경로에 혼입 금지**, 연구 아티팩트로만 태깅·격리(패킷 실패모드: "NC 데이터로 학습한 weight의 제품 혼입").
- **PR-3 counsel 서면 클리어가 외부셋 학습 arm 착수의 선결**. 그 전까지 P3의 CubiCasa 파인튜닝은 **연구 격리 상태로만** 진행, 밴드 주장에 제품 자격 부여 금지.

---

## 5. 구현 계획

### 5.1 모듈·파일 골격 (신규 — 본 패킷은 도시에만 작성; 아래는 실행 시 CHANGE 후보 설계)

```
graph_gnn/
  ir/
    build_hetero_graph.py    # SEG-IR / DXF → HeteroData (node5·edge6)
    edge_rules.py            # 결정론 엣지 규칙 (탐지기 v1 기하 재사용: 2°/overlap0.5/snap6mm)
    prox_capping.py          # radius + kNN + degree cap + 절단 로그
    adjacency_audit.py       # Cell-ADJ: known synthetic relation recall
  features/
    node_features.py         # cubicasa_ml 6특징 재사용 + type onehot; handle/순번/파일명 제거
  ssl/
    pretrain_bgrl_mae.py     # masked-attr 복원 + transform-contrastive(BGRL)
    transforms.py            # B4 불변군: rigid/scale/unit view
  model/
    hetero_gnn.py            # R-GCN / HGT backbone, JK·DropEdge·PairNorm
    heads.py                 # node head + edge(pair) head
  finetune/
    joint_finetune.py        # L = λ1 L_node + λ2 L_pair (+ β SSL)
  eval/
    write_wsd_eval_p3.py     # resolution_trigger 산출물 + graph_manifest + model_hash 동결
    calibration.py           # Brier 분해 REL/RES, reliability diagram
  evidence/
    to_evidence_grid.py      # soft score → evidence_grid 신규 채널
```

### 5.2 기존 도구 접속점

| 기존 도구 (다이제스트) | 접속 방식 |
|---|---|
| `cubicasa_ir` (SEG-IR 변환기, 레이어 중립) | **그래프 노드 소스**. SEG-IR edge id를 노드·조인 키로. 라벨 누출 0 성질을 그대로 상속 |
| `cubicasa_ml` (HistGradientBoosting 6특징 파이프라인) | 6특징을 **node 초기 피처**로 재사용; **셔플 대조군 패턴**(AUC 0.375 PASS) 재사용; GBDT는 P3의 **baseline(P2)** 로 동일 split에서 병주 |
| `fast_score` (NumPy 고속 채점기) | P3 soft score를 **동일 채점 하네스**로 평가 — 방법 간 공정 비교 |
| `evidence_grid` (다증거 격자, CL-B) | P3 node/edge score를 **신규 증거 행**으로 기입 (결정론 4채널 위에 얹음) |
| 탐지기 v1 (parallel 0.35/thickness 0.25/junction 0.20/layer 0.20) | 기하 로직(2°/overlap0.5/snap6mm)을 **엣지 구성 규칙**으로 재사용; soft evidence는 layer 슬롯 대체 후보이나 **밴드 통과 전 v1 변조 금지** |

### 5.3 예상 개발 규모

| 작업 | 규모 (엔지니어-일) |
|---|---|
| 그래프 IR 빌더 + 엣지 규칙 + prox capping | 2–3 |
| adjacency 감사(Cell-ADJ) | 1 |
| SSL 사전학습(BGRL+MAE) + transform view | 2–3 |
| hetero GNN 모델 + 두 헤드 + 파인튜닝 | 2–3 |
| eval/calibration/evidence 접속 | 1–2 |
| **소계(로컬 probe 도달까지)** | **~8–12 엔지니어-일** |
| DGX full pretrain·sweep 배선(unreachable 해제 후) | +2–3 (조건부) |

### 5.4 의존성 (R7 — 영구 코드로 취급)

- **PyTorch Geometric(PyG) 또는 DGL** 신규 도입 필요. stdlib·현행 도구엔 이종 GNN 없음 → 정당(R7 test 통과: NumPy만으론 message passing·서브그래프 샘플링 재구현 비용 과다). **DGL이 heterogeneous 1급 지원**이라 1순위 후보, PyG `HeteroData`가 대안. 도입 시 이유·버전 고정을 명시하고 **로컬 CPU/16GB에서 재현 가능한 최소 설치**로 한정.

---

## 6. 실험 셀 정의

공통 원칙(다이제스트 평가 원칙 고정): **val = 개발·튜닝 허용, test = 방법당 단발, 합격선 프리레그 봉인, 셔플 대조군 의무, 증거 xlsx 의무, 실패도 사유와 함께 기록.** 수치 합격선은 패킷 prereg band를 봉인 후보로 사용(**Paul 확정 전 candidate**). 학습 셀은 **다중 시드**(seed-confound 방지, 패널 PARKED 경고 T15).

### Cell-ADJ — Graph IR adjacency 완전성 감사 (**하드 선결**)

| 항목 | 내용 |
|---|---|
| 가설 | 결정론 엣지 규칙이 **알려진 합성 관계**를 충분히 회수한다 |
| 지표 | known synthetic relation recall; 엣지 종류별 누락률 |
| 합격선 | recall ≥ 0.98 |
| **킬** | **synthetic relation recall < 0.98 → GNN 경로 전면 중단**(패킷 kill 조건) — garbage-in 방지 |
| 예산 | 0.5–1일, 로컬 CPU |
| 시드 | 결정론(시드 무관); 합성 template 목록 동결 |

### Cell-CP — Cheapest probe (patch: pretrain ± 비교)

| 항목 | 내용 |
|---|---|
| 가설 | 합성 1,000 block + 실무 20장 비라벨 그래프에서 3-layer GNN이 P2(GBDT)와 비교 가능한 신호를 낸다; pretrain이 도움된다 |
| 지표 | val AUPRC / F1; pretrain-有 vs 無 Δ |
| 합격선 | 탐색적 go/no-go — pretrain Δ 효과크기 기록; P2 근접 시 본실험 go |
| 킬 | pretrain 無·有 모두 P2에 크게 못 미치고 개선 궤적 없음 → 조기 축소 |
| 예산 | 수 시간, 로컬 GPU |
| 시드 | {0,1,2} 3시드 |

### Cell-SSL — 사전학습 ablation

| 항목 | 내용 |
|---|---|
| 가설 | masked-attr + transform-contrastive 사전학습이 scratch보다 전이·OOD를 개선 |
| 지표 | CubiCasa val AUPRC; style-OOD AUPRC(Cell-OOD와 공유) |
| 합격선 | pretrain ≥ scratch (val) **AND** OOD 하락 완화(패킷 update_log: "SSL ablation OOD lift는 상향 증거") |
| 킬 | pretrain이 scratch 대비 무이득이면 SSL 가지 제거(방법 단순화) |
| 예산 | 1–2일 GPU (DGX 없이 로컬 샘플링) |
| 시드 | {0,1,2} |

### Cell-NODE — node 벽멤버십 파인튜닝

| 항목 | 내용 |
|---|---|
| 가설 | node head가 GBDT를 이긴다 (특히 재현율) |
| 지표 | synthetic node F1; CubiCasa val P/R/F1/AUPRC (vs GBDT 0.517) |
| 합격선 | **synthetic node F1 ≥ 0.92**(패킷); CubiCasa val에서 GBDT 대비 개선(밴드는 Cell-TEST) |
| 킬 | synthetic node F1 < 0.92 지속 또는 CubiCasa val이 GBDT 미달 |
| 예산 | 1–2일 GPU |
| 시드 | {0,1,2,3,4} (학습 셀 5시드) |

### Cell-PAIR — wall-pair 관계 파인튜닝

| 항목 | 내용 |
|---|---|
| 가설 | edge head가 평행 이중선 쌍을 손튜닝 스칼라보다 잘 판정 |
| 지표 | synthetic pair F1 |
| 합격선 | **synthetic pair F1 ≥ 0.80**(패킷) |
| 킬 | pair F1 < 0.80 지속 |
| 예산 | Cell-NODE와 공동(공동 손실) |
| 시드 | {0,1,2,3,4} |

### Cell-OOD — style-OOD 강건성

| 항목 | 내용 |
|---|---|
| 가설 | 다른 도면 스타일에서 성능이 붕괴하지 않는다 |
| 지표 | style-OOD AUPRC 하락폭 |
| 합격선 | **AUPRC 하락 ≤ 0.10**(패킷) |
| 킬 | 하락 > 0.10 → synthetic topology shortcut 의심, 일반화 실패 |
| 예산 | 0.5–1일 |
| 시드 | {0,1,2} |

### Cell-CAL — calibration (좌석 서명 셀)

| 항목 | 내용 |
|---|---|
| 가설 | soft score가 **잘 보정**되어 evidence 융합에 안전 |
| 지표 | Brier score; **분해 REL(reliability)·RES(resolution)**; reliability diagram |
| 합격선 | **REL ≤ 0.03 AND RES ≥ 0.03**(패킷) |
| 킬 | REL > 0.03(과신) 또는 RES < 0.03(무정보) → soft evidence로 부적격, temperature/isotonic 재보정 후 재시험 |
| 예산 | 0.5일 (평가 파이프라인 내) |
| 시드 | 파인튜닝 시드 상속 |

### Cell-MEM — compute 봉투

| 항목 | 내용 |
|---|---|
| 가설 | 엣지 수·메모리가 production 봉투 안 |
| 지표 | peak RAM; 엣지 수 분포·**p95**; GPU peak mem |
| 합격선 | **peak RAM ≤ 48GB**(패킷) |
| **킬** | **edge 수/메모리가 production p95 봉투 초과 → GNN 경로 중단**(패킷 kill) |
| 예산 | Cell 전반에 계측 상주 |
| 시드 | N/A (계측) |

### Cell-FAM — family-held-out 누출 프로브

| 항목 | 내용 |
|---|---|
| 가설 | 블록가문·Xref·합성 template 변형을 **한 fold에 묶으면** 낙관 편향이 사라진다 |
| 지표 | family-fold vs 순진 random-fold 성능 격차 |
| 합격선 | family-fold 성능이 random-fold와 큰 붕괴 없이 유지(붕괴 크면 누출이 순진 split을 부풀렸다는 증거) |
| 킬 | family-fold에서 성능이 chance로 붕괴 → 이전 성적은 block-family leakage 산물 |
| 예산 | 1일 |
| 시드 | fold seed {0,1,2} |

### Cell-TEST — 동결 held-out 단발 (**resolution**)

| 항목 | 내용 |
|---|---|
| 가설 | P3가 최선 비-GNN baseline 대비 **사전등록 lift**를 낸다 |
| 지표 | AUPRC_F; **lift = AUPRC_F(P3) − max(P1,P2)**; lift CI (부트스트랩) |
| 합격선 | **AUPRC_F ≥ max(P1,P2)+0.05 AND lift CI 하한 > 0**(패킷 resolution_criterion: `P3_lift_CI_low>0` + node/relation/OOD/calibration/compute 밴드 전부 참) |
| **킬** | **lift CI 하한 ≤ 0**(패킷 kill) |
| 예산 | 단발 — graph_manifest·model_hash 동결 후 `wsd_eval_p3.json` 생성(resolution_trigger) |
| 시드 | test는 방법당 **1회**; 모델은 val에서 고정된 단일 체크포인트 |

**셀 수 정당화.** 과소 금지: adjacency(ADJ)·probe(CP)·SSL 가치(SSL)·node(NODE)·pair(PAIR)·OOD·calibration(CAL)·compute(MEM)·누출(FAM)·resolution(TEST)이 **각기 다른 kill 축**을 닫는다(패킷이 명시한 5개 밴드 + 3개 kill 조건을 1:1로 커버). 과잉 금지: VLM·래스터·RL 셀 없음(각 CL-G/CL-H 소관), 아키텍처 대탐색은 val HP 공간(§2.5)으로 제한.

---

## 7. red team 티켓 응답

패널 OPEN 티켓 34건 중 P3에 걸린 것을 지목하고, **해소 방안** 또는 **수용(위험 인정)** 을 명시한다. (severity 원문: `seats/red_teamer.md` §2–3; 본 패킷엔 요약만.)

### T2 — 생성기 부재 (sev 0.70) · PR-1

- **입장: 수용 + 하드 선결.** synthetic node F1 ≥ 0.92 / pair F1 ≥ 0.80 밴드는 **합성 벽 생성기가 실존하고 B1 충실도 게이트를 통과한 뒤에만** 의미가 있다. 현재 생성기는 벽 코드 0이고 B1은 FAIL(KS 0.5792, TV 0.265; 실도면 SPLINE 3,973/ARC 2,198/HATCH 264 혼재 vs 합성 LINE/LWPOLYLINE/INSERT 3종).
- **해소**: PR-1(생성기 + fidelity 게이트) 완료 전까지 **합성 truth 파인튜닝 밴드를 봉인**. 그 전엔 P3는 CubiCasa truth로만 진행하고, 합성 셀(NODE/PAIR 합성 팔)은 `BLOCKED(원인: PR-1 미구축·B1 FAIL)`로 표기.

### T1 — 대리(truth proxy) 독립성 (sev 0.75, 최우선)

- **입장: 진원지 인정 + 감사 편입.** edge head가 "평행 이중선"을 **학습**하는데, 4대리(합성·외부·metamorphic·silver)가 모두 같은 평행 이중선 prior를 공유하면 P3는 **확증이 아니라 편향 증폭**이 된다(공격 A).
- **해소**: (i) node head(넓은 문맥)와 edge head(쌍 prior) 성적을 **분리 보고** — node가 pair 없이도 lift를 내면 독립 신호. (ii) doe P3/CL-E와 병합해 **동일 def 3원 불일치 구조** 측정(합성 vs 외부 vs silver가 같은 도면에서 어디서 갈리는가). (iii) B5 축(탐지기 layer 신호 0, full-vs-nb 1.0)과의 상관으로 P3가 silver 이름-prior에 편승했는지 감사.
- **잔여 위험 인정**: edge head 단독 성적을 "독립 확증"으로 과장하지 않는다.

### T10 / T23 — Graph IR adjacency 완전성 (R23 disputed)

- **입장: 수용 + Cell-ADJ 하드 선결.** "adjacency 누락"은 패킷 1순위 실패모드이자 kill 조건(synth relation recall <0.98).
- **해소**: Cell-ADJ를 **모든 학습 셀 앞에** 배치. 미통과 시 GNN 경로 중단. 이는 감사 가능한 결정론 스크립트(§2.1)라 저가.

### T22 — P1/P2 대비 lift 밴드의 선결 (calibration 자매 티켓)

- **입장: 수용 + 밴드 앵커 조작화.** `max(P1,P2)+0.05` 밴드는 **P1·P2를 동결 split에서 먼저 측정**해야 앵커가 선다. 특히 §3.4에서 논했듯 다이제스트는 GBDT **ROC-AUC 0.9215**만 주고 **AUPRC_F는 안 준다** — 11.8% 불균형에서 둘은 다르다.
- **해소**: Cell-TEST 전에 **P2 AUPRC_F 봉인 측정**을 선행 산출물로 둔다. 그 수치가 밴드의 실제 임계.

### T5 — FloorPlanCAD/CubiCasa NC 라이선스·권리 (sev 0.65) · PR-3

- **입장: 수용 + PR-3 게이트.** 외부셋 학습 arm은 **counsel 서면 클리어 전 착수 금지**.
- **해소**: NC weight **연구 격리**(§4.4) — 제품 경로 혼입 금지, 아티팩트 태깅. PR-3 미해결 시 P3는 합성(있으면)·실도면 SSL로만 진행하고 CubiCasa 파인튜닝은 격리 연구 상태.

### T34 — 인용 R-레인 experiment_executed:false (프로그램급)

- **입장: 수용.** §1.2의 CAD 그래프 선례(FloorPlanCAD/GAT-CADNet 등)를 **load-bearing 인용으로 쓰지 않았다** — 메커니즘 계보로만. 개별 성적 인용 0.
- **해소**: 본 도시에의 어떤 밴드·수치도 외부 논문 성적에 기대지 않는다(패킷 계약 준수).

### T15 — learned 셀 seed-confounded (PARKED 경고)

- **입장: 수용.** 학습 셀(NODE/PAIR)은 **5시드**, 나머지 학습 셀 3시드(§6). 단일 시드 성적을 밴드 판정에 쓰지 않는다.

### Occam 게이트 (CL-F 조건, 티켓 아님이나 사활)

- **입장: 정면 수용.** "로지스틱/GBDT가 먼저 뛰면 GNN 불요." GBDT는 이미 F1 0.517. P3는 **GBDT에 관계 피처를 얹은 값싼 대안(예: 이웃 집계 피처를 GBDT에 추가)이 격차를 닫으면 죽어야 한다** → §8 death condition.

### 열린 불일치 — FloorPlanCAD "line truth" 실재성

- **입장: 요검증 노출.** 패킷 Truth source는 "FloorPlanCAD line truth"라 하나 다이제스트 자산은 "래스터+bbox/segmask(**벡터 SVG 없음**)". P3 그래프는 벡터를 요구 → **line truth의 벡터 실재성 미확인**. 조달·확인 전 P3는 FloorPlanCAD를 truth로 쓰지 않는다(§3.2).

---

## 8. 인접 제안과의 관계

### 8.1 병합 가능 지점

| 대상 | 관계 |
|---|---|
| **CL-F / platt P2 (고전 ML GBDT)** | P3의 **baseline이자 상위 관문**. 동일 split 병주; GBDT+이웃피처가 격차 닫으면 P3 death |
| **doe P3 / CL-E (truth-source 교차·독립성)** | **병합**: 동일 def 3원 불일치 구조를 P3 node/edge score를 제4 축으로 넣어 공동 측정 (T1 해소의 실행체) |
| **CL-B / evidence_grid** | P3 soft score = **신규 증거 채널**(결정론 4채널 위); 융합 전 Cell-CAL 보정 필수 |
| **CL-K / feyerabend P3 (anti-silver 통제)** | P3가 silver로 파인튜닝할 때 **gate-only 대조 arm 상설** — silver 증류가 실제로 돕는지 통제 |
| **P1 (결정론)** | P3는 topology gate를 **대체 안 함**; soft evidence로 **보완**. B3(0.2135 PASS)·B4(scale 0.7624 FAIL)의 결정론 축 위에 얹힘 |
| **CL-J / feyerabend P1 (face/room-first)** | **대안 그래프 프레임**: P1은 centerline→room, feyerabend는 room/face 먼저·벽은 dual bridge. P3 그래프에 **face/region 노드 추가**로 흡수 가능(미래 확장) |
| **CL-D / metamorphic (M 팔)** | transform-contrastive view = metamorphic 변환군. M 팩이 P3 SSL augmentation과 **공유 자산** |

### 8.2 차별점

- **vs GBDT(P2)**: 국소 6피처가 아니라 **관계·위상**. 목표는 F1 최대가 아니라 **GBDT가 못 보는 문맥 분리**(FP 주범 = 대역 내 평행 비벽).
- **vs 탐지기 v1**: 손튜닝 4채널 가중이 아니라 **학습된 쌍-판정 + 이웃 집계**. 단 결정론 게이트 대체 아님.
- **vs VLM/CL-G**: 픽셀·API·DGX 불요(로컬 GPU 완결). FloorPlanCAD 래스터는 CL-G에 위임.
- **vs RL/CL-H**: per-handle·per-pair **지도 분류**이지 집합-조립·라우팅 아님.

### 8.3 이 제안이 죽어야 하는 조건 (정직)

1. **Occam kill**: GBDT(또는 GBDT+값싼 이웃 집계 피처)가 P3와 동등/우위 → GNN 복잡도 정당화 실패. **최우선 death.**
2. **adjacency kill (패킷)**: Cell-ADJ에서 synthetic relation recall < 0.98 → 그래프가 위상을 못 담음 → garbage-in.
3. **lift kill (패킷)**: Cell-TEST에서 lift CI 하한 ≤ 0 vs 최선 비-GNN baseline.
4. **독립성 kill (T1)**: 3원 불일치 감사에서 P3가 공유 평행 prior의 **증폭기**로 판명(node head도 독립 신호 無).
5. **compute kill (패킷)**: edge 수/메모리 production p95 봉투 초과 또는 peak RAM > 48GB.
6. **truth 고갈 kill**: PR-1 생성기가 fidelity(B1) 영영 미통과 **AND** PR-3 NC 클리어 실패 → 합성·외부 truth 모두 봉쇄 → 파인튜닝 진리원 소멸(SSL만 남으면 벽 판정 불가).
7. **OOD kill (패킷)**: style-OOD AUPRC 하락 > 0.10 → synthetic topology shortcut, 일반화 실패.

**Demote(죽음이 아닌 강등) 경로**: 위 3·7이 아슬하게 실패해도 P3 soft score가 **calibration(Cell-CAL)만 통과**하면, "독립 판별기"가 아니라 **evidence_grid의 보조 채널**로만 강등 생존 가능(단 "GBDT를 이겼다" 주장은 죽인다).

---

## 부록 A — calibration/forecast 해결 장치 (좌석 서명)

패킷 calibration 블록을 조작화한다:

| 항목 | 값 (패킷) | 조작화 |
|---|---|---|
| `claim` | P3가 비-GNN baseline 대비 동결 held-out 사전등록 lift + compute·calibration gate 통과 | Cell-TEST의 5밴드 AND 3-kill 부정 |
| `forecast` | `null` (수치 abstain) | **지금 수치 예보 없음** — 아래 abstain 해제 조건 전까지 |
| `score_type` | `brier` | Cell-CAL의 Brier + REL/RES 분해로 채점 |
| `reference_class` | RC-WALL-ZL, `n=0`, `n_min=5` | Graph IR 기반 벽 GNN **독립 해결 사례 0**, 최소 5 필요 |
| `base_rate` | `none` | 참조군 공허 → 기저율 미정 |
| `resolution_criterion` | `P3_lift_CI_low>0` AND node/relation/OOD/calibration/compute 밴드 전부 참 | Cell-TEST + NODE/PAIR/OOD/CAL/MEM 논리곱 |
| `resolution_trigger` | graph manifest·model hash 동결 후 `wsd_eval_p3.json` 생성 | §2.7·§5.1 산출물 |
| `update_log` | 2026-07-17 KST 최초 abstain; SSL ablation OOD lift ↑상향, adjacency audit 실패/dedupe 후 lift 소멸 ↓하향 (사전 약정) | Cell-SSL·Cell-ADJ·Cell-FAM이 갱신 증거 생산 |
| `uncertainty_type` | `epistemic` — adjacency audit·family-held-out probe로 감소 | Cell-ADJ·Cell-FAM이 불확실성 감축기 |
| `resolution_verdict` | `open` | 미해결 |
| `abstain_flag` | `empty_reference_class` | 참조군 비면 수치 예보 봉인 |

**abstain(수치 예보 봉인) 해제 조건 — 이 좌석의 핵심 산출.** `forecast=null`은 게으름이 아니라 **참조군이 비어(n=0<n_min=5)** 수치 예보의 근거가 없다는 정직한 선언이다. 다음이 갖춰지면 abstain을 풀고 첫 수치 예보를 낸다:

1. Cell-ADJ PASS (그래프가 위상을 담음 확인) — **epistemic 불확실성 1차 감축**.
2. P2 AUPRC_F 동결 측정(밴드 앵커 확정) — 목표 임계가 수치로 고정.
3. Cell-CP 3시드 궤적(pretrain Δ 방향성) — 첫 사전분포 형성.

그 전까지 어떤 "P3가 될 것 같다"류 낙관도 FM1(Fake PASS)·FM4(검증 전 전향)이며, 이 도시에는 그것을 내지 않는다.

## 부록 B — 수치 인용 출처

본문 수치(B1 KS 0.5792/TV 0.265·SPLINE 3,973/ARC 2,198/HATCH 264, B2 S 1.0·F P 0.9315·M P 0.8669, B3 0.682→0.2135, B4 scale 0.7624, B5 Pearson 0.2911·full-vs-nb 1.0·최대 412,775 선분, E1.5 5기·2가문, CubiCasa 5,000/4,200(386만)/400(35.4만)/400(37.5만)·벽율 11.8%·두께 px p50 22, 전이 F1 0.2358·P 0.134·기저율 0.118·R 0.981·축척 2~15mm/px, min-length F1 0.335(80px), GBDT P 0.860/R 0.370/F1 0.517/AUC 0.9215, 로지스틱 F1 0.053, 셔플 AUC 0.375, 탐지기 가중 0.35/0.25/0.20/0.20·두께 50~400mm·각도 2°·overlap 0.5·snap 6mm, prereg 밴드 AUPRC_F≥max(P1,P2)+0.05·synth node F1≥0.92·pair F1≥0.80·OOD≤0.10·REL≤0.03·RES≥0.03·RAM≤48GB, kill synth relation recall<0.98, 자산 목록)는 **전부 패킷 실측 다이제스트(2026-07-18) 및 패널 보고서 서술에서만** 인용했다.

그 외 알고리즘·시스템 이름(R-GCN/HGT/HAN/GraphSAGE/GraphSAINT/Cluster-GCN/MPNN/GraphMAE/DGI/GRACE/GraphCL/BGRL/FloorPlanCAD/GAT-CADNet/CADTransformer/SymPoint 등)은 **일반 지식**이며, 저자·연도는 **요검증**으로 표기하고 **개별 논문의 성능 수치는 일절 인용하지 않았다**. 웹 검색 미사용. 형제 도시에(platt_P6)가 "412,965 선분"으로 적은 것과 달리 본 도시에는 **본 패킷 다이제스트의 412,775 선분**을 인용했다(교차-좌석 수치 불일치는 요검증 대상으로 노출).

DOSSIER_COMPLETE: calibration_P3
