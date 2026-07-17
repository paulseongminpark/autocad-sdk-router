# calibration_forecaster — 벽 의미 탐지기 방법론

## EVIDENCE BASIS

- 현행 `wall_pairs.py`는 `LINE`만 받아 평행도·30–500 간격·겹침률로 후보를 만들고 선당 최대 4쌍으로 제한한다(`evidence/wall_pairs.py:46,140-146,204-207`). 이는 벽 판정기가 아니라 결정적 candidate generator다(`evidence/R12_FINAL_REPORT.md:35-36`).
- E1에서 역할 일치율은 0.5491, handle Jaccard 평균은 0.1319, 완전 불일치 비율은 0.682였다(`evidence/calibration_v0.json:4-20`). LLM likelihood와 v0 후보 수 상관도 0.284였고, top divergence에는 likelihood 0.95인데 후보가 0개인 사례가 있다(`evidence/wall_crosscheck_v0.md:7-12`). 어느 쪽도 truth로 승격할 수 없다.
- `synthetic_truth.py`는 dimension 관계와 단일 mutation만 생성한다(`evidence/synthetic_truth.py:3-7,33,92`). 현재 상태를 벽 합성 정답으로 인용하면 안 되며, 독립적인 wall-specific generator와 resolver가 필요하다.
- DWG Graph IR은 구현된 handle graph 기질이지만 learned GNN이나 완전한 adjacency의 증거는 아니다(`evidence/R23_FINAL_REPORT.md:31`). Planar arrangement는 유력한 공간 복원 primitive지만 messy geometry에 취약하다(`evidence/R16_FINAL_REPORT.md:35,57`).
- FloorPlanCAD의 선 단위 라벨과 CubiCasa5K의 raster 라벨은 연구 truth로 쓸 수 있으나 NC 격리 대상이다(`evidence/R23_FINAL_REPORT.md:21`). 해당 데이터로 학습한 가중치는 제품 후보로 이동하지 않는다.
- E1.5 합의는 silver일 뿐 truth가 아니다. top-tier 역할 일치가 0.70 이상이고 likelihood Pearson이 0.70 이상일 때만 제한적으로 사용한다(`evidence/prereg_e15.json:6,32-34`).
- RL은 고정 라벨 분류기를 대신하지 않는다. Sound verifier가 있는 RLVR, 순차 probe 선택, active acquisition, horizon≈1 contextual bandit만 후보로 둔다(`evidence/R26_FINAL_REPORT.md:29-43`).

## COMMON RESOLUTION CONTRACT

- **평가 단위:** 원본 drawing/block definition에 속한 각 entity handle의 이진 사건 `wall_member(h)`. 벽 instance/pair 복원은 보조 지표이며 handle 분류와 섞지 않는다.
- **RC-WALL-ZL:** 사람 라벨 없이 학습하고, 동결된 합성 OOD·외부 라벨 held-out·metamorphic gate로 독립 해결된 CAD 벽 탐지 방법. 현재 독립 해결 사례 `n=0`; 수치 forecast를 허용할 최소 표본은 `n_min=5`다. E1 LLM과 v0는 truth-resolved가 아니므로 포함하지 않는다.
- **WSD-EVAL-v1 truth pack:** (S) 서로 다른 벽 grammar·단위·곡률·opening을 갖는 wall-specific 합성 IR, (F) FloorPlanCAD 선 라벨의 license-quarantined test, (M) 145장 실무 아카이브의 translation/rotation/reflection/uniform-scale/unit-change 및 handle-mapped split/merge metamorph. CubiCasa5K는 raster 제안에서만 pixel truth로 쓴다.
- **누수 통제:** 원본 도면, 중첩 block/Xref, 동일 geometry fingerprint를 하나의 group으로 묶어 split한다. 모든 metamorphic 파생본은 원본 fold를 상속한다. handle, 파일 경로, source ID는 feature에서 제거한다. 외부 데이터 ontology mapping과 제외 class는 결과를 보기 전에 동결한다.
- **Scoring:** 제안 성공 여부는 binary이므로 `brier`; entity 예측에는 AUPRC, risk-coverage와 Brier의 `REL/RES/UNC` 분해를 모두 보고한다. ECE나 평균 F1만으로 통과시키지 않는다.
- **Goodhart 방어:** generator와 resolver는 구현을 공유하지 않고, hidden mutation family를 test 전용으로 둔다. Silver·metamorphic consistency만으로 semantic accuracy를 주장하지 않는다.

## PROPOSALS

### P1. 다중 증거 결정론적 constraint lattice

**Mechanism.** LINE 평행쌍 하나에 의존하지 않고 LINE/LWPOLYLINE/ARC, collinear continuity, offset mate, junction, 폐곡면, opening gap, hatch/poché, block 반복·transform lineage를 각각 독립 evidence로 만든다. 후보 중심선을 planar arrangement에 투영한 뒤 최대가중 matching 또는 작은 connected component별 ILP로 상충하는 벽 instance를 선택하며, source group/layer는 prior일 뿐 hard oracle로 쓰지 않는다. 규칙 점수는 held-out truth에서 별도로 calibration하여 `p_wall(h)`로 내보내고 원 규칙 evidence도 보존한다.

**Truth source.** 독립 wall grammar로 생성한 exact handle truth, FloorPlanCAD 선 라벨, 의미 보존 metamorphic relation. 기존 dimension 전용 `synthetic_truth.py`는 구현 패턴만 재사용하고 truth로 세지 않는다.

**Verification design.**

- **Truth source:** S/F/M 세 pack을 모두 사용하며 실무 145장은 M 결과만 truth로 인정한다.
- **Leakage protection:** unit·grammar·opening style을 family 단위로 분리하고, resolver는 candidate generator의 threshold나 geometry 함수를 import하지 않는다.
- **Prereg band draft:** `F1_S≥0.95`, `AUPRC_F−AUPRC_v0≥0.15`, `precision_F≥0.90 at coverage≥0.50`, metamorphic handle flip rate `≤0.01`, `REL≤0.03`, `RES≥0.02`, local p95 `≤60초/도면`, peak RAM `≤32GB`를 모두 통과.
- **Kill condition:** hidden synthetic family F1이 0.85 미만이거나 false merge rate가 0.05 초과, metamorphic flip이 0.02 초과, 또는 후보 edge가 entity 수에 대해 실측상 quadratic으로 폭증하면 중단한다.
- **Cheapest probe:** 5개 wall grammar×20개 block의 100-case 합성 pack과 E1 top-20 divergence에 v0 및 lattice를 적용해 candidate recall·metamorphic flip·메모리를 비교한다.

**Compute plan.** 로컬 CPU에서 component별 streaming으로 실행하고 RAM telemetry가 48GB를 넘기 전에 중단한다. DGX는 필요 없으며 대규모 threshold sweep도 CPU batch로 보내되 vLLM 자원을 점유하지 않는다.

**Expected failure modes.** 단위 추정 오류, single-line wall 누락, 장식 평행선 false positive, gap/overshoot로 arrangement 붕괴, hatch 관습 차이, aggressive pruning에 의한 조용한 recall 손실.

- `claim`: P1이 동결된 WSD-EVAL-v1에서 위 prereg band를 모두 통과한다.
- `forecast`: `null` — 수치 forecast abstain.
- `score_type`: `brier`
- `reference_class`: RC-WALL-ZL, `n=0`, `n_min=5`.
- `base_rate`: `none`
- `resolution_criterion`: resolver의 `P1_all_bands_pass == true`일 때만 참.
- `resolution_trigger`: S/F/M manifest hash와 구현 hash를 동결한 뒤 독립 resolver가 `wsd_eval_p1.json`을 생성할 때.
- `update_log`: `2026-07-17 KST` 최초 등록—empty reference class로 abstain. Cheapest probe 전 band 통과는 이후 확률을 상향, false merge·누수·hidden-family 실패는 하향하도록 사전 약정하며 수정은 새 버전으로만 남긴다.
- `uncertainty_type`: `epistemic` — wall 합성 truth와 외부 held-out 측정으로 감소.
- `resolution_verdict`: `open`
- `abstain_flag`: `empty_reference_class` — truth-resolved 유사 방법이 없다.

### P2. 반복 구조 기반 weak supervision + PU 고전 ML

**Mechanism.** 각 entity에 길이·각도·곡률·평행 mate 수·교차 차수·폐면 기여·block 반복 빈도·transform 안정성·text/layer token 등의 tabular feature를 만들고, P1의 고정밀 교집합을 positive anchor, 명백한 dimension/text/annotation primitive를 negative anchor, 나머지를 unlabeled로 두어 PU-learning과 label-model로 결합한다. Logistic/boosted-tree baseline을 모두 학습하고 drawing-shift calibration을 별도 수행하며, E1.5 silver는 gate 통과 시 하나의 상관된 labeling function으로만 추가한다.

**Truth source.** 학습 anchor와 독립된 synthetic handle truth 및 FloorPlanCAD held-out line truth. 실무 반복 일관성과 E1.5는 진단·학습 신호이지 평가 truth가 아니다.

**Verification design.**

- **Truth source:** S/F exact labels로만 semantic metric을 해결하고 M은 안정성 gate로 쓴다.
- **Leakage protection:** 동일 block definition과 geometry fingerprint를 동일 fold로 묶고 raw handle/path/vendor ID를 제거한다. Layer token 사용 모델과 제거 모델을 함께 보고한다.
- **Prereg band draft:** `AUPRC_F≥AUPRC_P1+0.05`, `AUPRC_S≥AUPRC_P1+0.03`, `precision≥0.92 at coverage≥0.50`, company/style OOD AUPRC 하락 `≤0.10`, `REL≤0.03`, `RES≥0.02`; 95% bootstrap CI 하한도 각 lift에서 0 초과.
- **Kill condition:** deterministic baseline 대비 lift CI 하한이 0 이하, raw layer 제거 시 AUPRC가 0.15 이상 붕괴, 또는 positive-anchor recall 편향으로 특정 wall grammar recall이 0.60 미만이면 중단한다.
- **Cheapest probe:** 합성 500 block과 license-quarantined FloorPlanCAD 20장으로 logistic, boosted tree, P1 세 모델만 비교한다.

**Compute plan.** feature extraction과 고전 ML은 로컬 CPU/64GB RAM에서 충분하며 32GB soft cap을 둔다. DGX는 사용하지 않는다.

**Expected failure modes.** PU의 selected-completely-at-random 가정 위반, P1 편향 복제, dataset-specific layer shortcut, 반복되는 비벽 symbol 오인, project shift에서 calibration 붕괴.

- `claim`: P2가 P1보다 동결된 S/F 평가에서 사전등록 lift와 calibration band를 모두 만족한다.
- `forecast`: `null` — 수치 forecast abstain.
- `score_type`: `brier`
- `reference_class`: RC-WALL-ZL, `n=0`, `n_min=5`.
- `base_rate`: `none`
- `resolution_criterion`: `P2_lift_CI_low>0`, 모든 성능·shift·calibration band 통과, leakage audit 통과.
- `resolution_trigger`: 고정 split에서 P1/P2 비교 artifact `wsd_eval_p2.json`이 독립 생성될 때.
- `update_log`: `2026-07-17 KST` 최초 abstain. Layer-ablation 후 유지되는 lift는 상향 증거, anchor-only subgroup 붕괴나 split dedupe 실패는 하향 증거로 사전 약정.
- `uncertainty_type`: `epistemic` — anchor bias와 drawing shift 측정으로 감소.
- `resolution_verdict`: `open`
- `abstain_flag`: `empty_reference_class` — 비교 가능한 해결 이력이 없다.

### P3. DWG Graph IR용 self-supervised heterogeneous GNN

**Mechanism.** entity, block definition/reference, layer, text anchor를 node type으로 하고 containment, instancing, intersection, proximity, parallelism, collinearity를 typed edge로 갖는 heterogeneous graph를 구성한다. 먼저 masked-attribute 복원과 transform-contrastive 학습으로 라벨 없는 145장을 pretrain한 뒤 synthetic/FloorPlanCAD truth로 node wall membership과 wall-pair relation을 jointly fine-tune한다. 모델 출력은 soft evidence이며 deterministic topology gate를 대체하지 않는다.

**Truth source.** Synthetic entity·relation truth와 FloorPlanCAD line truth. Graph IR 자체나 자기지도 target은 semantic truth가 아니다.

**Verification design.**

- **Truth source:** S의 node/relation label과 F의 node label을 분리 보고한다.
- **Leakage protection:** 연결된 Xref/block family 전체를 한 fold에 두고 handle·순번·파일명을 제거한다. 동일 합성 template의 parameter 변형도 같은 family fold를 따른다. NC 학습 weight는 연구 격리한다.
- **Prereg band draft:** `AUPRC_F≥max(P1,P2)+0.05`, synthetic node `F1≥0.92`, synthetic pair `F1≥0.80`, style-OOD AUPRC 하락 `≤0.10`, `REL≤0.03`, `RES≥0.03`, peak RAM `≤48GB`.
- **Kill condition:** best classical model 대비 lift CI 하한이 0 이하, graph construction에서 known synthetic relation recall이 0.98 미만, 또는 edge 수/메모리가 production p95에서 봉투를 넘으면 GNN 경로를 중단한다.
- **Cheapest probe:** 합성 1,000 block과 실무 20장 비라벨 graph로 3-layer GNN을 pretrain 없이/있이 각각 한 번 학습해 P2와 비교한다.

**Compute plan.** 로컬 RTX 5070 Ti에서 sampled subgraph와 mixed precision으로 probe를 수행한다. full-corpus pretraining과 hyperparameter sweep만 DGX Spark의 vLLM 비사용 시간대에 배치하며 graph shard 단위로 checkpoint한다.

**Expected failure modes.** Graph IR adjacency 누락, proximity edge 폭증, oversmoothing, block-family leakage, synthetic topology shortcut, NC 데이터로 학습한 weight의 제품 혼입.

- `claim`: P3가 최선의 비-GNN baseline보다 동결 held-out에서 사전등록 lift를 내면서 compute·calibration gate를 통과한다.
- `forecast`: `null` — 수치 forecast abstain.
- `score_type`: `brier`
- `reference_class`: RC-WALL-ZL, `n=0`, `n_min=5`.
- `base_rate`: `none`
- `resolution_criterion`: `P3_lift_CI_low>0`이며 node/relation/OOD/calibration/compute band가 모두 참.
- `resolution_trigger`: graph manifest와 model hash를 동결한 뒤 `wsd_eval_p3.json`이 생성될 때.
- `update_log`: `2026-07-17 KST` 최초 abstain. Self-supervised ablation의 OOD lift는 상향, adjacency audit 실패나 dedupe 후 lift 소멸은 하향 증거로 사전 약정.
- `uncertainty_type`: `epistemic` — adjacency audit와 family-held-out probe로 감소.
- `resolution_verdict`: `open`
- `abstain_flag`: `empty_reference_class` — Graph IR 기반 벽 GNN의 독립 해결 사례가 없다.

### P4. Raster–vector dual-view DL과 결정적 back-projection

**Mechanism.** DWG IR을 여러 scale의 linework raster와 entity-ID buffer로 동시에 렌더링하고, segmentation encoder가 raster context를 예측하도록 학습한 뒤 ID buffer로 pixel score를 원래 handle에 back-project한다. Vector feature branch와 raster branch의 확률은 held-out calibration으로 fusion하며, 최종 handle·geometry는 항상 IR에서 가져온다. CubiCasa5K는 raster representation 연구에, FloorPlanCAD와 synthetic render는 handle 평가에만 사용하여 vision을 SoT로 만들지 않는다.

**Truth source.** Synthetic render의 exact wall mask/handle mapping, CubiCasa5K pixel mask, FloorPlanCAD line truth. 원본 raster나 모델 attention은 truth가 아니다.

**Verification design.**

- **Truth source:** pixel metric과 handle metric을 분리하며 최종 resolution은 handle metric으로 한다.
- **Leakage protection:** building/drawing 단위 split, render style family holdout, ID buffer는 입력 금지·back-projection에만 사용, 모든 crop은 원본 fold를 상속한다.
- **Prereg band draft:** curved/hatch/single-line stratum에서 `AUPRC≥best_vector+0.08`, 전체 AUPRC 감소 `≤0.02`, synthetic pixel→handle mapping accuracy `≥0.995`, unseen render-style AUPRC 하락 `≤0.10`, `REL≤0.04`, `RES≥0.02`.
- **Kill condition:** CRS/back-projection 오류가 0.5% 초과, 유리 subgroup의 lift CI 하한이 0 이하, 전체 성능이 0.02 초과 하락, 또는 NC artifact가 제품 weight 경로와 분리되지 않으면 중단한다.
- **Cheapest probe:** 200개 synthetic block을 네 render style로 만들고 작은 segmentation model을 학습하여 P2/P3가 놓친 curved·single-line subset만 비교한다.

**Compute plan.** 로컬 GPU에서 512–1024px patch와 gradient accumulation으로 probe한다. 대형 image encoder, 다중 scale sweep, local open vision encoder fine-tune만 DGX에서 수행하며 NC-trained checkpoint는 별도 registry에 격리한다.

**Expected failure modes.** rasterization aliasing, 얇은 선 소실, CRS·crop 역변환 오류, 여러 handle의 한 pixel 충돌, scan/vector domain gap, 시각적 벽 모양과 CAD 의미의 불일치.

- `claim`: P4가 raster-benefit stratum에서 vector baseline을 개선하고 전체 비열등성·back-projection·calibration gate를 모두 통과한다.
- `forecast`: `null` — 수치 forecast abstain.
- `score_type`: `brier`
- `reference_class`: RC-WALL-ZL, `n=0`, `n_min=5`.
- `base_rate`: `none`
- `resolution_criterion`: subgroup lift, 전체 non-inferiority, mapping, OOD, REL/RES 조건이 모두 참.
- `resolution_trigger`: render manifest·CRS contract·model hash가 동결된 뒤 `wsd_eval_p4.json`이 생성될 때.
- `update_log`: `2026-07-17 KST` 최초 abstain. Style-held-out subgroup lift는 상향, back-projection mismatch나 vector-only 대비 전체 열화는 하향 증거로 사전 약정.
- `uncertainty_type`: `epistemic` — style/CRS-stratified 평가로 감소.
- `resolution_verdict`: `open`
- `abstain_flag`: `empty_reference_class` — native-DWG 공유 holdout에서 해결된 dual-view 사례가 없다.

### P5. Frontier VLM jury silver와 local open VLM 학습의 분리

**Mechanism.** Frontier VLM들은 동결된 vector projection+raster와 rationale schema를 보고 독립 투표하며, 합의 결과는 silver로만 저장한다. E1.5 gate를 통과한 고합의 사례만 local open VLM의 LoRA/adapter 학습 또는 P2/P3의 weak feature로 사용한다. Prompting 경로는 silver acquisition, local fine-tuning 경로는 student learning으로 분리하고, 어떤 경우에도 VLM 출력이 resolver나 geometric SoT가 되지 않는다.

**Truth source.** 최종 평가는 synthetic exact handles와 FloorPlanCAD held-out labels로만 한다. E1.5·frontier 합의·rationale는 truth source가 아니라 제한된 training evidence다.

**Verification design.**

- **Truth source:** S/F resolver만 semantic 성공을 판정하고 E1.5는 silver admission gate로 분리한다.
- **Leakage protection:** prompt·judge set·consensus rule을 test 전에 동결하고, test truth와 합성 mutation 이름을 judge에게 주지 않는다. 동일 drawing은 silver/train/test에 중복되지 않는다.
- **Prereg band draft:** E1.5 `B1≥0.70` 및 `B4 Pearson≥0.70`; handle silver에는 추가로 top-tier pairwise Jaccard `≥0.50`과 4/5 합의 coverage `≥0.30`; student는 `AUPRC_F≥best_nonVLM+0.03`, `REL≤0.04`, `RES≥0.02`.
- **Kill condition:** B1/B4 실패 시 likelihood silver를 중단하고, handle Jaccard 실패 시 handle 학습을 중단한다. 독립 truth에서 student lift CI 하한이 0 이하이거나 hallucinated handle rate가 0.01 초과하면 전체 handle 경로를 폐기한다.
- **Cheapest probe:** E1.5 산출만으로 admission gate를 먼저 계산한 뒤, 통과할 경우 100 synthetic+50 FloorPlanCAD projection에 고정 prompt를 적용해 hallucination과 truth-conditioned calibration을 측정한다.

**Compute plan.** Frontier 호출은 고합의 후보에만 제한한다. 로컬 RTX 5070 Ti에서는 quantized 3–7B open VLM inference와 작은 LoRA probe를 수행하고, 더 큰 local open VLM fine-tune만 DGX의 예약 시간대에 배치한다.

**Expected failure modes.** judge 간 상관된 오류, 그럴듯한 rationale의 사후 합리화, 존재하지 않는 handle 생성, prompt/style shift, silver confirmation loop, frontier API 의존, NC 학습 데이터 출처 혼입.

- `claim`: E1.5 admission gate를 통과한 VLM silver로 학습한 local student가 독립 S/F truth에서 비-VLM baseline을 개선한다.
- `forecast`: `null` — 수치 forecast abstain.
- `score_type`: `brier`
- `reference_class`: RC-WALL-ZL, `n=0`, `n_min=5`.
- `base_rate`: `none`
- `resolution_criterion`: admission·handle consensus·student lift·hallucination·calibration band가 모두 참.
- `resolution_trigger`: E1.5 binding 결과와 독립 student evaluation `wsd_eval_p5.json`이 모두 생성될 때.
- `update_log`: `2026-07-17 KST` 최초 abstain. E1.5 B1/B4/handle band 통과는 상향, 독립 truth 대비 합의 오류와 hallucination은 하향 증거로 사전 약정.
- `uncertainty_type`: `epistemic` — E1.5와 truth-conditioned VLM probe로 감소.
- `resolution_verdict`: `open`
- `abstain_flag`: `empty_reference_class` — 합의 silver에서 독립 truth로 해결된 이력이 없다.

### P6. Verifier-guided active acquisition: contextual bandit 우선, RLVR 조건부

**Mechanism.** 고정된 `entity→wall` 분류기는 supervised 모델로 유지하고, 정책은 불확실한 block에서 다음 행동—graph neighborhood 확장, 고해상도 render, deterministic gate 실행, VLM jury 호출, abstain—만 선택한다. Horizon 1이면 contextual bandit, 여러 probe가 상태를 바꾸고 지연 보상을 만들 때만 RLVR을 사용한다. 보상은 held-out이 아닌 training synthetic truth에서의 Brier 개선과 exact gate 통과에서 계산하고 compute·latency 비용을 차감한다.

**Truth source.** Training reward는 synthetic exact truth와 독립 metamorphic verifier, 최종 평가는 hidden synthetic family와 FloorPlanCAD truth. LLM judge 보상은 금지한다.

**Verification design.**

- **Truth source:** hidden S/F truth가 최종 성능을, 별도 mutation pack이 verifier soundness를 해결한다.
- **Leakage protection:** reward-visible generator family와 hidden family를 분리하고 test gate variant를 정책에 노출하지 않는다. Policy state에서 truth·mutation ID·test label을 제거한다.
- **Prereg band draft:** verifier false-accept `≤0.01`, false-reject `≤0.05`; fixed routing과 supervised uncertainty acquisition 모두에 대해 최종 AUPRC 비열등(`감소≤0.01`)이면서 평균 compute cost `≥20%` 절감. Multi-step RLVR은 bandit보다 utility를 `≥5%` 개선할 때만 존속한다.
- **Kill condition:** verifier false-accept가 0.01 초과, hidden family에서 reward/semantic metric 방향이 반대, 비용 절감이 20% 미만, 또는 RLVR이 bandit 대비 5% lift를 못 내면 각각 verifier/policy/full-RL 경로를 중단한다.
- **Cheapest probe:** 합성 1,000 state와 네 행동으로 offline contextual bandit을 학습해 fixed router 및 uncertainty heuristic과 비교한다. 이 단계에서는 full RL을 실행하지 않는다.

**Compute plan.** 로컬 CPU/GPU에서 simulator와 contextual bandit probe를 수행한다. DGX는 multi-step 필요성이 먼저 입증된 경우에만 parallel environment와 policy training에 사용하며 vLLM 서비스와 자원 시간을 분리한다.

**Expected failure modes.** verifier exploitation, proxy reward Goodhart, simulator-to-real gap, 비용 추정 오류, policy가 비싼 VLM 행동에 편향, off-policy 불안정, 실제 horizon이 1인데 full RL을 과도하게 사용하는 오류.

- `claim`: verifier-guided action policy가 semantic 성능을 유지하면서 고정·supervised acquisition baseline보다 compute cost를 20% 이상 줄인다.
- `forecast`: `null` — 수치 forecast abstain.
- `score_type`: `brier`
- `reference_class`: RC-WALL-ZL, `n=0`, `n_min=5`.
- `base_rate`: `none`
- `resolution_criterion`: verifier soundness, AUPRC 비열등성, 비용 절감 band를 모두 통과. Full RL 정당성은 별도로 `utility_RL/utility_bandit≥1.05`.
- `resolution_trigger`: hidden mutation 및 S/F 평가를 포함한 `wsd_eval_p6.json`이 생성될 때.
- `update_log`: `2026-07-17 KST` 최초 abstain. Sound verifier와 hidden-family 비용 절감은 상향, reward hacking·FAR 초과·bandit 동률은 full-RL 확률을 하향하도록 사전 약정.
- `uncertainty_type`: `epistemic` — verifier audit와 bandit-first probe로 감소.
- `resolution_verdict`: `open`
- `abstain_flag`: `empty_reference_class` — task-local verifier-guided 정책의 해결 이력이 없다.

## START HERE

1. P1에 필요한 독립 wall-specific synthetic generator/resolver와 WSD-EVAL-v1 split manifest를 먼저 동결한다.
2. 100-case P1 probe로 현재 v0의 candidate-recall 천장을 측정한다.
3. 같은 truth와 split을 유지한 채 P2, P3 순으로 incremental lift를 검증한다.
4. Vector 계열이 놓치는 사전등록 subgroup에서만 P4를 연다.
5. P5는 E1.5 admission gate 통과 후에만, P6은 verifier false-accept가 1% 이하임을 확인한 뒤에만 실행한다.