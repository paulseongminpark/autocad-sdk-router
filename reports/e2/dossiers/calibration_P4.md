# calibration_P4 방법론 심층 도시: Raster–vector dual-view DL과 결정적 back-projection

## 문서 경계와 판정 원칙

이 문서는 P4를 곧바로 실행 가능한 실험 계약으로 바꾼다. 아래의 현재 성적·자산·장애 상태는 패킷의 2026-07-18 실측 다이제스트만 인용한다. 문헌 절의 설명은 정량 성적을 끌어오지 않은 일반 방법론 지식이며, 서지 세부가 확실하지 않은 항목은 `요검증`으로 표시한다. 이 문서 작성 중 새 측정, 웹 검색, 코드 실행에 의한 성능 주장은 하지 않았다.

P4의 핵심 불변식은 다음 다섯 가지다.

1. 신경망은 linework raster만 본다. entity-ID buffer, handle, 정답 handle, fold ID는 입력 채널이 아니다.
2. 픽셀 예측은 기존 IR entity에 점수를 돌려주는 데만 쓰며, 최종 handle과 geometry는 항상 원본 IR에서 복사한다.
3. pixel metric과 handle metric을 분리하고, 최종 판정은 handle metric으로만 한다.
4. 합성 exact mapping이 결정적 back-projection을 검증한다. CubiCasa5K와 FloorPlanCAD의 raster truth 또는 attention map이 native-DWG handle truth를 대신하지 않는다.
5. `best_vector`와 P4의 manifest·CRS contract·모델 hash·합격선을 test 접근 전에 동결한다. test는 방법 버전당 한 번만 연다.

현재 `forecast=null`, `reference_class=RC-WALL-ZL, n=0`, `abstain_flag=empty_reference_class`, `resolution_verdict=open`을 유지한다. 이 문서는 성공을 예측하지 않고, 무엇을 관찰하면 성공 또는 사망으로 판정할지를 고정한다.

---

## 1. 이론적 근거·선행연구

### 1.1 Raster context가 줄 수 있는 정보

현재 기하 탐지기 v1은 CubiCasa5K val에서 F1 0.2358, 정밀도 0.134, 재현율 0.981이며, HistGradientBoosting은 같은 val에서 F1 0.517, 정밀도 0.860, 재현율 0.370, AUC 0.9215다. 전자는 대부분의 벽을 포함하지만 긴 평행 비벽 구조까지 받아들이고, 후자는 높은 정밀도를 얻는 대신 많은 벽을 놓친다. 특히 Direction 화살표, BoundaryPolygon, Door, Window, DimensionMark가 평행 구조 prior를 공유하며, 최소길이 필터만으로 얻을 수 있는 F1 천장도 0.335에 그쳤다. 따라서 P4가 노리는 추가 정보는 “두 선이 평행한가”가 아니라 다음과 같은 넓은 문맥이다.

- 선이 방의 연속 경계를 구성하는가, 아니면 치수·기호·창호의 국소 패턴인가.
- 후보 전후에 벽의 연속성, 코너, 개구부, 반복 모듈이 존재하는가.
- 곡선·HATCH·single-line처럼 vector feature가 불완전한 표현도 주변 공간구조와 함께 벽처럼 보이는가.
- 여러 scale에서 국소 stroke와 전역 room topology가 동시에 일관적인가.

이것은 raster가 진리라는 주장이 아니다. raster encoder는 context feature extractor이고, 기존 handle에 대한 확률을 제안할 뿐이다.

### 1.2 Semantic segmentation 계보

- **U-Net**(Ronneberger 등, *U-Net: Convolutional Networks for Biomedical Image Segmentation*)은 encoder–decoder와 skip connection으로 얇은 경계의 위치 정보와 큰 receptive field를 결합한다. 작은 로컬 probe의 기본 구조로 적합하다.
- **Feature Pyramid Network**(Lin 등, *Feature Pyramid Networks for Object Detection*)와 **DeepLabv3+**(Chen 등, *Encoder-Decoder with Atrous Separable Convolution for Semantic Image Segmentation*)는 다중 scale 문맥과 경계 복원을 체계화한다. P4의 multi-scale linework 입력과 직접 연결된다.
- **SegFormer**(Xie 등, *SegFormer: Simple and Efficient Design for Semantic Segmentation with Transformers*)는 계층형 encoder와 가벼운 decoder의 대안이다. 다만 로컬 16GB probe에서 필수는 아니며, 큰 encoder 비교는 DGX arm으로 격리한다.
- **anti-aliased pooling / BlurPool**(Zhang, *Making Convolutional Networks Shift-Invariant Again*)은 downsampling이 얇은 선과 1-pixel 이동에 민감해지는 문제를 줄이는 방법론적 근거다. P4에서는 모델 기법만 믿지 않고, supersampled coverage render와 metamorphic 검사를 함께 둔다.

위 논문명과 기법 설명은 문헌 일반 지식이다. 문헌 정량 성적은 본 계획의 기대값이나 합격선에 사용하지 않는다.

### 1.3 Floorplan 구조 복원 계보

- **CubiCasa5K**(Kalervo 등, *CubiCasa5K: A Dataset and an Improved Multi-Task Model for Floorplan Image Analysis*)는 raster floorplan에서 room/icon 경계를 함께 학습하는 다중과제 계보를 제공한다. P4에서는 이미 변환된 SEG-IR의 Wall edge를 line-support 학습 신호로 쓰되, native DWG handle의 진리로 승격하지 않는다.
- **Raster-to-Vector: Revisiting Floorplan Transformation**의 raster feature와 구조화된 vector 복원 결합, **Floor-SP**의 room-wise 구조 복원, **HEAT: Holistic Edge Attention Transformer for Structured Reconstruction**의 edge/corner 관계 모델링은 “픽셀 문맥을 구조화된 출력에 연결한다”는 인접 계보다. 정확한 서지 판·연도는 `요검증`이다.
- **Polygon-RNN++**처럼 raster feature에서 순차 vector geometry를 생성하는 계열도 인접하지만, P4는 새 선이나 polygon을 생성하지 않는다. 생성 모델의 좌표 오차를 피하고 기존 IR handle로만 귀환하는 것이 차별점이다.

### 1.4 결정적 ID buffer와 back-projection 계보

GPU graphics의 object picking, deferred rendering의 G-buffer, instance/semantic rendering은 각 pixel에 object ID 또는 primitive ID를 기록한다. P4는 이를 학습 가능한 attention 대신 감사 가능한 sparse relation으로 사용한다. 한 pixel에 여러 entity가 겹칠 수 있으므로 단일 RGB 색상 ID가 아니라 `(pixel, handle, coverage)`의 **multi-hit coverage buffer**를 정식 표현으로 삼는다. 이 relation은 renderer가 만들고, 모델 추론이 끝난 뒤 확률 집계에만 사용한다.

Soft Rasterizer나 Neural Mesh Renderer 같은 differentiable rendering 계열은 `요검증` 대상의 인접 기술이지만 P4의 필수 구성요소가 아니다. geometry를 gradient로 갱신하지 않기 때문에, 결정적 CPU/GPU rasterizer와 독립 oracle을 두는 편이 진리 경계를 더 선명하게 한다.

### 1.5 확률 calibration과 fusion 계보

- **Platt scaling**, **isotonic regression**, **temperature scaling**(Guo 등, *On Calibration of Modern Neural Networks*), **beta calibration**(Kull 등)은 분류 점수를 관측 빈도와 맞추는 대표 방법이다.
- **Brier score**는 확률과 이진 정답의 제곱오차다. Murphy decomposition의 reliability(REL), resolution(RES), uncertainty 분해를 쓰면 “확률이 맞는가”와 “사례를 구분하는가”를 분리할 수 있다.
- P4는 자유도가 큰 meta-model 대신 비음수 convex logit fusion을 기본으로 한다. raster가 약할 때 vector를 뒤집어 해치는 음의 계수를 막고, 동률이면 raster weight가 작은 모델을 선택하는 Occam 규칙을 둔다.

이 계보가 보장하는 것은 calibration 절차의 형태이지, P4의 성공이 아니다. reference class가 비어 있으므로 수치 forecast abstain을 유지하는 이유가 여기에 있다.

---

## 2. 알고리즘 정확 스펙

### 2.1 입력·출력과 표기

한 drawing의 IR을

\[
D=(E, M),\qquad E=\{e_h=(h,g_h,x_h)\}
\]

로 둔다. `h`는 불변 handle, `g_h`는 IR geometry, `x_h`는 vector branch feature, `M`은 unit·sheet·view metadata다. 출력은

\[
O(D)=\{(h, p_v(h), p_r(h), p_f(h), \hat y_h, g_h, audit_h)\}
\]

다. 출력 `h`와 `g_h`는 입력 IR에서 byte-identical reference 또는 canonical serialization hash로 확인한다. 모델은 handle을 생성·수정·병합하지 않는다.

`best_vector`는 test 공개 전에 선택·동결된 가장 강한 vector-only 방법이다. 최소 후보는 `fast_score` 기반 v1과 현재 6-feature HistGradientBoosting이며, P2/P3가 그 전에 완료되면 동일 fold·동일 handle universe에서 더 강한 쪽을 포함한다. F1과 AUPRC를 혼용하지 않으며, P4의 lift baseline은 다시 계산한 **handle AUPRC**다.

### 2.2 좌표계 계약

각 scale/view `s`에 대해 world coordinate에서 network pixel center로 가는 변환을 homogeneous matrix 곱으로 고정한다.

\[
u_{s}=A_{aug}\,C_{crop}\,P_{pad}\,S_{scale}\,V_{sheet}\,U_{unit}\,[x,y,1]^T
\]

계약에는 다음을 모두 기록한다.

- 원본 unit과 canonical unit 변환, 축 방향, sheet origin, pixel-center convention.
- crop origin·size, padding, resize 방식, line width, supersampling factor.
- 회전·반사·이동 augmentation의 정방향·역방향 행렬.
- renderer version, float precision, clipping rule, curve tessellation tolerance.
- base drawing ID, building ID, fold, style family, crop parent ID.

ID buffer를 image interpolation으로 resize하지 않는다. geometry를 최종 view 좌표로 변환한 뒤 그 해상도에서 다시 rasterize한다. linework와 ID coverage는 같은 transformed primitive stream에서 생성한다. 역변환은 저장된 행렬의 역행렬로만 수행하며, bbox를 보고 추정하지 않는다.

### 2.3 Dual-view render

handle을 fold 내부에서만 의미 있는 dense integer `k(h)`에 매핑하고, 별도 manifest에 `k↔h`를 저장한다. raster input은 multi-scale grayscale coverage다.

\[
X_s(p)=\operatorname{RenderCoverage}(\{g_h\},T_s,style_s)
\]

back-projection buffer는 다음 sparse relation이다.

\[
B_s=\{(p,h,a_{sph}):a_{sph}>0\},
\]

여기서 `a_sph`는 pixel `p`에 대한 handle `h`의 exact 또는 supersampled fractional coverage다. 교차선·겹친 INSERT·동일 pixel 충돌에서는 여러 tuple을 보존한다. z-order 하나만 남기는 단일-ID render는 금지한다. 저장 형식은 dense primary-ID plane과 collision sidecar 또는 CSR sparse matrix 중 하나일 수 있으나, 두 형식 모두 같은 relation을 round-trip해야 한다.

모델 입력 channel manifest에는 오직 다음만 허용한다.

- 여러 scale의 linework coverage.
- 사전등록한 style-neutral 파생 채널(예: occupancy distance transform)을 쓰는 arm이라면 linework만으로 계산된 것.

금지 채널은 ID 색상, handle hash, truth mask, fold/style label, layer-name token, 원본 class color다. ID buffer를 무작위 치환해도 model logits가 bitwise 또는 정해진 수치 tolerance 안에서 동일하다는 입력-격리 test를 둔다.

### 2.4 Pixel target와 segmentation loss

합성에서는 exact wall handles를 동일 rasterizer로 별도 렌더하되, 구현 오류의 자기확증을 막기 위해 평가 oracle은 독립 analytic segment/curve–pixel intersection 코드로 만든다. CubiCasa5K에서는 사람 라벨 Wall class에서 변환된 SEG-IR edge를 target으로 쓰고, off-line 빈 공간은 주 손실에서 제외한다. FloorPlanCAD는 제공된 wall bbox/segmask의 pixel/line 진리만 쓸 수 있으며 현재 자산 설명상 native handle target이 아니다.

network `f_θ`는 pixel logit `z_s(p)`를 출력한다. 기본 손실은 line-support weighted BCE와 soft Dice의 합이다.

\[
L_{seg}=\lambda_b L_{BCE}(z,y;m)+\lambda_d L_{Dice}(\sigma(z),y;m),
\]

여기서 `m`은 유효 line-support mask다. class weight는 fit split에서만 계산하고 고정한다. crop 간 positive 수 차이는 drawing이 많은 crop을 만들어 평가를 지배하지 않도록 training sampler에서만 보정한다. 평가 단위는 crop이 아니라 원 drawing/handle이다.

로컬 기본 후보는 작은 U-Net 또는 ResNet-18-FPN이다. **제안 hyperparameter 공간**은 다음과 같고, 이는 관측 결과가 아니라 사전 탐색 범위다.

- patch: 512을 기본으로 하며 768·1024는 메모리 probe 통과 시만 비교.
- linework scale: 원해상도, 2배 넓은 문맥, 4배 넓은 문맥의 세 pyramid level.
- optimizer: AdamW, learning rate `{1e-4, 3e-4}`, weight decay `{1e-5, 1e-4}`.
- loss weight: `λ_b∈{0.5,0.75}`, `λ_d=1-λ_b`.
- batch: VRAM에 맞는 micro-batch와 gradient accumulation으로 effective batch 8을 목표로 한다.
- early stopping: fit split 학습, calibration split은 학습 중 보지 않고, val pixel AUPRC가 아니라 사전등록한 handle AUPRC로 선택한다.
- augmentation: 좌표계 계약으로 정확히 추적되는 rigid transform·reflection·crop만 기본 허용. blur, scan noise, line-width 변화는 별도 style arm이며 primary training과 혼합 여부를 manifest에 고정한다.

### 2.5 결정적 pixel→handle 집계

각 handle의 raster logit은 support-weighted logit 평균으로 정의한다.

\[
\ell_r(h)=\frac{\sum_s\omega_s\sum_p a_{sph}q_{sp}z_s(p)}
{\sum_s\omega_s\sum_pa_{sph}q_{sp}},\qquad p_r(h)=\sigma(\ell_r(h)).
\]

`q_sp`는 padding·clipping을 제외하는 validity mask이고, `ω_s`는 calibration split에서 고른 scale weight다. primary operator는 평균 하나로 고정한다. max, top-quantile, noisy-OR는 ablation으로만 보고하며 test 뒤에 바꾸지 않는다.

coverage가 전혀 없는 handle은 `raster_missing=true`로 기록하고 vector-only 확률을 사용한다. 임의 0.5나 주변 pixel 점수를 대입하지 않는다. collision pixel은 각 handle의 coverage에 따라 두 handle 모두에 기여하며, 임의 winner를 선택하지 않는다.

독립 oracle relation `B_ref`와 구현 relation `B_impl`에 대해 mapping accuracy를

\[
MAPACC=\frac{|B_{ref}\cap B_{impl}|}{|B_{ref}\cup B_{impl}|}
\]

로 정의한다. tuple 비교에서 coverage는 사전등록 tolerance로 양자화한다. `CRS_error=1-MAPACC`다. 따라서 `MAPACC≥0.995`와 `CRS_error≤0.5%`는 같은 하드 게이트를 두 표현으로 감사한다.

### 2.6 Vector branch와 held-out fusion

vector score를 `p_v(h)`, raster score를 `p_r(h)`라 한다. train drawing을 geometry group 기준 `fit`, `cal-A`, `cal-B`로 다시 분리한다.

1. `fit`에서 raster model과 필요한 vector model을 학습한다.
2. `cal-A`에서 raster temperature scaling과 vector Platt/beta calibration 중 사전등록한 branch calibrator를 fit한다. calibrator 종류 선택은 `cal-A` 내부 cross-fitting만 쓴다.
3. `cal-B`에서 다음 convex logit fusion을 고른다.

\[
z_f(h)=b+\alpha z_r^c(h)+(1-\alpha)z_v^c(h),\quad 0\le\alpha\le1,
\qquad p_f(h)=\sigma(z_f(h)).
\]

`α`는 0.1 간격 grid, `b`와 선택적 final temperature는 Brier score 최소화로 정한다. 동률이면 더 작은 `α`, 더 단순한 calibrator를 택한다. `raster_missing`이면 `α=0`으로 강제한다. val은 이 전체 pipeline을 개발 평가하는 곳이며, val 결과로 다시 cal-A/B를 재분할하지 않는다.

binary threshold `τ`는 cal-B에서 F1 최대점으로 정하되 동률이면 정밀도가 높은 값을 택하고 동결한다. primary 판정은 threshold-free handle AUPRC와 Brier/REL/RES이며, `τ`는 sentinel·운영 confusion matrix용이다.

### 2.7 Calibration metric

handle별 Brier score는

\[
BS=N^{-1}\sum_h(p_f(h)-y_h)^2
\]

다. test 전에 고정한 10개 equal-width probability bin에서

\[
REL=\sum_b\frac{n_b}{N}(\bar p_b-\bar y_b)^2,
\qquad
RES=\sum_b\frac{n_b}{N}(\bar y_b-\bar y)^2
\]

를 계산한다. 빈 bin은 합에서 제외하되 bin 경계를 합치지 않는다. primary uncertainty interval은 drawing/building 단위 paired cluster bootstrap으로 구한다. crop·pixel bootstrap은 금지한다.

### 2.8 실행 의사코드

```text
assert counsel_gate.allows(dataset, purpose)
assert synthetic_generator.fidelity_status == PASS
folds = group_split(base_building_or_drawing_id)
assert every_crop_inherits_parent_fold(folds)

freeze(best_vector, fold_manifest, style_families)
for drawing in fit + cal_A + cal_B + val:
    ir = load_ir(drawing)
    for view in render_contract.views:
        X, B_impl, transform = render_linework_and_multihit_ids(ir, view)
        assert id_buffer_not_in_model_channels(X)
        save_manifest_only(X_hash, B_hash, transform, parent_fold, style_family)

theta = train_small_segmenter(X_fit, pixel_truth_fit)
z_pixel = infer(theta, X)
p_r = deterministic_backproject(z_pixel, B_impl)
p_v = frozen_vector_predict(ir)

branch_calibrators = fit_on(cal_A, p_r, p_v)
fusion = choose_convex_logit_fusion_on(cal_B, score=Brier)
val_report = evaluate_separately(pixel_metrics, handle_metrics, strata, OOD)

if and_only_if all_prereg_and_legal_gates_are_frozen:
    lock(render_manifest, crs_contract, model_hashes, code_hash, thresholds)
    test_once()
    write wsd_eval_p4.json and evidence xlsx
    verdict = PASS only if every conjunctive handle gate passes
```

---

## 3. 벽 과업 적응 설계

### 3.1 CubiCasa5K raster/SEG-IR 축

고정 분할 train 4,200, val 400, test 400을 보존한다. train의 386만 선분은 model fit과 cal-A/B로 drawing 단위 재분할하고, val의 35.4만 선분은 architecture·fusion 개발에만 사용한다. test 37.5만 선분은 최종 단발 이전에 어떠한 threshold·scale·weight 선택에도 쓰지 않는다. crop은 원 drawing fold를 상속하며, 같은 floorplan의 다른 crop이나 style render가 다른 fold로 이동할 수 없다.

CubiCasa의 주 역할은 다음 세 가지다.

- 실제 사람 라벨에서 얻은 Wall edge를 이용해 raster encoder가 평행 구조 이상의 context를 학습하는지 본다.
- 기존 geometry v1과 HistGradientBoosting이 혼동한 긴 평행 non-wall 구조에서 error taxonomy가 달라지는지 본다.
- 동일 SEG-IR entity에 대한 pixel score 집계를 통해 handle-like line metric을 개발하되, 이를 native-DWG handle 해결 사례로 세지 않는다.

벽 선분율이 약 11.8%이고 물리 축척이 미상이며, geometry v1은 2~15mm/px 전 구간에서 성적이 무감했다. 따라서 P4 입력에 물리 두께를 은밀히 복원해 넣지 않는다. pixel scale은 style/representation 변수로 취급하고, scale-held-out 결과를 OOD로 보고한다.

### 3.2 Synthetic exact-handle 축

현재 합성팩은 B1 충실도 FAIL(KS 0.5792, TV 0.265)이며 LINE/LWPOLYLINE/INSERT만 포함한다. 패널에 따르면 현재 `synthetic_truth.py`에는 벽 코드가 없다. 그러므로 현 합성팩으로 P4 성능 PASS를 선언하는 것은 금지한다.

CL-C/PR-1 생성기가 exact `wall_member(h)`와 다음 표현을 만들고 fidelity gate를 통과한 뒤에만 cheapest probe를 시작한다.

- ARC/SPLINE 곡선 벽, HATCH와 경계 entity, single-line 벽.
- block/INSERT 중첩 transform, 끊긴 조각, 비평행 표현, 교차·중첩 handle.
- zero-wall, all-wall sentinel과 hard-negative 기호·치수·창호.
- base geometry와 render style을 독립 요인으로 생성하는 manifest.

패킷의 cheapest probe는 **base synthetic block 200개를 각 네 render style로 렌더**하는 것으로 해석한다. 이는 200개의 geometry group을 유지한 채 style 일반화를 평가하게 한다. 모든 style 복제본은 같은 geometry fold에 묶고, OOD style 평가는 학습에서 완전히 빠진 style family와 학습에 없던 geometry의 조합에서 한다.

synthetic은 두 역할만 갖는다. 첫째, analytic oracle로 CRS·crop·collision mapping을 검증한다. 둘째, exact wall handle truth로 P4의 최종 handle gate를 판정한다. fidelity gate를 통과해도 real-DWG 외적 타당성을 자동 보장하지 않는다.

### 3.3 FloorPlanCAD raster 축의 제한

자산 설명상 FloorPlanCAD는 raster 5,308장과 wall bbox/segmask는 있으나 vector SVG가 없다. 따라서 현재 상태에서 raster mask를 어떤 자동 선 추출 결과와 연결해 “원래 CAD handle”이라고 부를 수 없다. 그것은 vision output을 truth로 되먹이는 순환이다.

이에 따라 FloorPlanCAD arm은 다음처럼 제한한다.

- counsel이 NC 라벨과 원 도면 사용 목적을 서면 허용하기 전에는 학습·평가 모두 시작하지 않는다.
- 허용 후에도 pixel AUPRC, line-support AUPRC, domain-shift 진단만 할 수 있다.
- 원 CAD/IR과 독립적으로 검증된 handle mapping이 추가 조달되기 전에는 최종 `resolution_criterion`에 포함하지 않는다.
- 제안 원문의 “FloorPlanCAD handle 평가”는 현재 자산으로 실행 불가능하므로 **OPEN dependency**로 기록한다. 이를 숨기지 않는 것이 P4의 truth-source 원칙과 일치한다.

### 3.4 1.dwg 실도면 축

1.dwg staged DXF의 384개 도면정의에는 패킷상 gold wall handle이 없다. 이 축에서는 성능 정답을 만들지 않고 다음만 확인한다.

- renderer와 back-projector가 최대 412,775 선분 도면정의에서도 bounded-memory streaming으로 완료되는가.
- 기존 handle·geometry를 바꾸지 않고 score sidecar만 생성하는가.
- rigid transform, layer rename, unit/scale 변환에서 handle 대응과 score가 계약대로 유지되는가.
- zero-wall rate나 silver와의 상관을 gold 정확도처럼 해석하지 않는가.

현재 v0→v1 벽-제로 도면율 0.682→0.2135 PASS와 silver Pearson 0.2911은 기존 시스템의 관측이지 P4 성능 증거가 아니다. 특히 name-blind arm과 full arm이 1.0으로 같았다는 사실은 현재 탐지기가 layer-name 신호를 쓰지 않았음을 뜻할 뿐, P4가 독립 진리를 얻었다는 뜻은 아니다.

### 3.5 P4가 기존 0.236/0.517을 넘어 가져올 수 있는 것

P4의 가능한 이득은 HistGradientBoosting의 높은 정밀도 후보를 vector prior로 보존하면서, raster context로 놓친 curved/HATCH/single-line wall의 재현을 회수하는 것이다. 동시에 raster가 Door/Window/DimensionMark의 전체 기호 문맥을 보면 geometry v1의 긴 평행 hard negative를 억제할 수 있다. 그러나 다음 세 경우에는 이 논리가 무너진다.

1. raster encoder도 결국 평행 이중선 prior만 학습해 proxy 편향을 반복한다.
2. scan/vector 또는 render-style domain gap이 문맥 이득보다 크다.
3. CL-B의 vector normalization·INSERT 전개·상대 단위 정박이 같은 zero-pair를 더 싸고 안정적으로 회수한다.

따라서 기존 F1 수치를 P4의 예상 AUPRC로 변환하지 않고, 같은 handle universe에서 `best_vector`, `raster-only`, `fusion` 세 arm을 paired 비교한다.

---

## 4. 데이터·컴퓨트 요구

### 4.1 데이터 manifest

모든 sample은 최소한 다음 필드를 가진다.

`drawing_id, building_id, base_geometry_id, parent_fold, crop_id, style_family, source_dataset, license_tag, ir_hash, truth_hash, render_contract_hash, crs_hash, input_channel_hash, id_buffer_hash`.

split 우선순위는 `building_id`가 있으면 building, 없으면 base drawing이다. 동일 base geometry의 모든 style·crop·augmentation은 parent fold를 상속한다. style OOD용 family는 모델 선택 전에 이름과 render parameter 범위를 동결한다.

진리별 허용 용도는 다음과 같다.

| 진리 | 허용 역할 | 금지 역할 |
|---|---|---|
| synthetic exact wall mask/handle mapping | mapping oracle, decisive handle metric, sentinel | fidelity FAIL 상태의 real 성능 대리 |
| CubiCasa5K human Wall mask/SEG-IR edge | raster representation 학습, pixel·line diagnostic | native-DWG handle 해결 사례 |
| FloorPlanCAD bbox/segmask | counsel 후 pixel/line OOD 진단 | 독립 IR mapping 없는 handle truth |
| 1.dwg IR | 처리량·불변성·geometry 보존 | gold 없는 성능 판정 |
| model attention/activation | debugging visualization | truth 또는 back-projection relation |

### 4.2 로컬 실행 계획

사용 가능 자원은 RTX 5070 Ti 16GB와 RAM 64GB다. 로컬 경로가 cheapest probe와 작은 본 실험을 독립적으로 끝낼 수 있어야 한다.

- raster는 전체 도면을 VRAM에 넣지 않고 512 기본 patch로 streaming한다.
- mixed precision, activation checkpointing은 필요 시 사용하고, gradient accumulation으로 effective batch를 맞춘다.
- ID coverage는 GPU 입력에 올리지 않고 CPU sparse CSR 또는 memory-mapped sidecar로 보관한다. back-projection은 drawing 단위 streaming reduction으로 수행한다.
- 최대 선분 정의에 대비해 `fast_score`와 vector feature는 chunk 단위로 읽고, fusion은 handle key sort-merge로 한다. 전체 N×N 후보 행렬은 만들지 않는다.
- local screen은 작은 U-Net/ResNet-18-FPN만 사용한다. 큰 vision encoder나 광범위 scale sweep가 없더라도 P4의 핵심 claim을 반증할 수 있어야 한다.

제안 예산은 관측값이 아닌 계획값이다. mapping harness는 CPU 1일 이내, 200-block probe는 render 포함 로컬 1일과 GPU 수 시간 범위, CubiCasa local screen은 단일 seed 후보 선별 후 선택 구성 3-seed 재학습으로 GPU 1~2일 범위를 목표로 한다. 실제 wall-clock은 evidence xlsx에 기록하되 사후 합격선으로 쓰지 않는다.

### 4.3 DGX 계획과 불통 처리

DGX Spark와 Ornith-35B는 현재 unreachable이다. 따라서 DGX는 hard dependency가 아니다.

DGX가 복구되고 vision 지원·license가 확인된 뒤에만 다음 확장 arm을 연다.

- 큰 open vision encoder fine-tune.
- 512–1024의 더 넓은 multi-scale sweep와 seed ensemble 확장.
- 더 많은 style family와 high-resolution full-sheet inference.

DGX arm은 로컬 prereg와 별도 method version/hash를 가진다. DGX 결과를 본 뒤 로컬 P4 test threshold를 바꾸지 않는다. Ornith의 vision 지원 여부가 확인되지 않으면 해당 arm만 `NOT_RUN`으로 남기며, 로컬 P4 판정을 지연시키지 않는다.

### 4.4 NC checkpoint 격리

CubiCasa5K/FloorPlanCAD 관련 counsel 서면 확인 전에는 외부셋 training을 시작하지 않는다. 허용되더라도 모든 checkpoint와 derived feature cache에는 `license_tag=NC_OR_RESEARCH_ONLY`를 강제하고, product registry와 물리·논리 namespace를 분리한다.

- product loader는 allowlist license tag만 읽는다.
- NC checkpoint 경로를 product config에 넣으면 startup이 실패한다.
- model hash뿐 아니라 training dataset manifest hash를 registry에 기록한다.
- synthetic-only 또는 권리-cleared checkpoint와 NC checkpoint를 ensemble하지 않는다.

이 격리 test가 실패하면 성능과 무관하게 P4를 중단한다.

---

## 5. 구현 계획

아래는 **구현 예정 골격**이며 이 도시 작성 시 생성한 파일 목록이 아니다. 기존 도구의 함수 signature는 패킷에 없으므로 추측하지 않고 adapter boundary로만 지정한다.

```text
p4/
  contracts/
    render_contract.yaml          # pixel center, unit, transform, style, scale
    split_manifest.jsonl          # building/drawing group와 crop 상속
    channel_allowlist.yaml        # 모델 입력 허용 채널
  render/
    ir_dual_view.py               # linework와 multi-hit coverage 동시 생성
    coverage_buffer.py            # CSR/sidecar serialization
    crs_chain.py                  # 정·역 homogeneous transform
    analytic_oracle.py            # 독립 mapping oracle
  data/
    cubicasa_adapter.py            # cubicasa_ir 출력→P4 sample
    synthetic_adapter.py          # CL-C exact wall_member→P4 sample
    floorplancad_adapter.py        # pixel/line diagnostic only
    grouped_sampler.py             # parent fold 보존
  models/
    raster_segmenter.py           # small U-Net/FPN
    vector_adapter.py             # fast_score/cubicasa_ml 결과 key join
    backproject.py                # pixel logit→handle logit
    calibrate_fusion.py           # cal-A/B calibration과 convex fusion
  eval/
    metrics_pixel.py
    metrics_handle.py
    strata.py
    wsd_eval_p4.py
    evidence_export.py
  tests/
    test_crs_roundtrip.py
    test_collision_multihit.py
    test_crop_fold_inheritance.py
    test_id_channel_isolation.py
    test_ir_geometry_immutable.py
    test_nc_registry_guard.py
```

### 5.1 기존 도구 접속점

- `cubicasa_ir`: drawing·element·Wall edge와 원 split ID를 읽는 source adapter. 기존 transform을 신뢰만 하지 않고 P4 CRS contract에 canonical matrix와 hash를 기록한다.
- `cubicasa_ml`: 현재 6-feature HistGradientBoosting의 handle/line key와 probability를 읽는 vector adapter. P4가 내부 model을 몰라도 `(drawing_id, handle_or_line_id, p_v)` 계약으로 결합한다.
- `fast_score`: v1 deterministic score와 feature를 chunk inference로 공급한다. score 계산을 raster 학습 코드에 복제하지 않는다.
- `evidence_grid`: cell·fold·seed·arm·metric·CI·gate·hash·runtime·failure_reason을 행 단위로 기록하고 필수 xlsx를 export한다.

join 전후에 handle universe hash와 positive/negative count가 같아야 한다. 누락·중복 handle은 0으로 채우지 않고 `JOIN_CONTRACT_FAIL`로 중단한다.

### 5.2 구현 순서

1. **계약부터 구현**: split, coordinate, input channel, license registry schema를 먼저 고정한다.
2. **oracle과 renderer 이중 구현**: 작은 analytic scene에서 독립 oracle과 production renderer relation을 비교한다.
3. **back-projection 단위검사**: crop, flip, rotate, scale, clipping, collision, nested INSERT, curve tessellation을 모두 통과시킨다.
4. **dataset adapter**: synthetic와 CubiCasa를 먼저 연결하고 FloorPlanCAD는 counsel·handle bridge 상태를 명시한다.
5. **작은 raster baseline**: seed 하나로 데이터 흐름과 shuffle control을 검증한다.
6. **calibration/fusion**: cal-A/B를 분리해 branch calibrator와 convex fusion을 동결한다.
7. **평가·증거**: pixel/handle sheet를 분리한 xlsx와 기계판독 JSON을 만든다.
8. **sealed test runner**: manifest·CRS·model hash가 모두 맞을 때만 test token을 소비한다.

### 5.3 예상 개발 규모와 검수 기준

제안 추정치는 renderer/CRS 2~3 개발일, data/model adapter 2~3일, training/fusion 2일, eval/evidence/guard 2~3일 정도다. 이는 일정 계획값이며 측정 주장이 아니다. 핵심 검수는 코드량이 아니라 다음 contract coverage다.

- 모든 transform type에 oracle test가 존재한다.
- ID input isolation과 NC registry guard가 negative test까지 가진다.
- 동일 manifest로 재실행하면 mapping relation·model input hash·handle output order가 재현된다.
- 실패도 xlsx/JSON에 원인과 최초 실패 gate를 남긴다.

### 5.4 `wsd_eval_p4.json` 최소 schema

```json
{
  "method_id": "calibration_P4",
  "status": "PASS|FAIL|OPEN|NOT_RUN",
  "frozen": {
    "render_manifest_hash": "...",
    "crs_contract_hash": "...",
    "model_hashes": ["..."],
    "best_vector_hash": "...",
    "prereg_hash": "..."
  },
  "metrics": {
    "pixel_diagnostic": {},
    "handle_primary": {},
    "calibration": {},
    "mapping": {},
    "ood_style": {}
  },
  "gates": [],
  "first_failed_gate": null,
  "test_access_count": 1,
  "artifacts": {"evidence_xlsx": "..."}
}
```

`status=PASS`는 아래 결합 gate가 전부 참일 때만 가능하다. artifact 누락, test 재접근, hash 불일치는 성능 숫자와 무관하게 FAIL이다.

---

## 6. 실험 셀 정의

### 공통 평가 규칙

- **arm**: `best_vector`, `raster_only`, `fusion`, `shuffle_raster`. 필요한 ablation은 개발용이며 최종 claim arm을 바꾸지 않는다.
- **primary unit**: 원 drawing에 속한 IR handle 1개. pixel metric은 진단용 별도 sheet다.
- **strata**: `curved`, `hatch`, `single_line`을 generator metadata/IR type로 outcome 이전에 정의한다. 세 stratum을 합쳐 평균내지 않고 각각 통과시킨다. 겹치는 handle은 각 해당 stratum에 보고하되 전체 metric에는 한 번만 센다.
- **uncertainty**: building/drawing cluster paired bootstrap. crop이나 pixel을 독립 표본으로 세지 않는다.
- **seed 계획**: 제안 seed `{17,29,43}`. hyperparameter screen은 17만 쓰고, 동결 구성은 세 seed 평균을 하나의 ensemble method로 정의한다. test 후 seed 선택은 금지한다.
- **test 단발**: 모든 최종 데이터 source의 test evaluation을 한 orchestrated run으로 열고 access count를 1로 남긴다. 실패 후 재학습은 새 method version과 새 prereg가 필요하다.

아래 시간·자원 수치는 제안 예산이다.

### Cell P4-0 — 법률·진리·baseline 선결 gate

- **가설**: P4가 사용할 truth와 `best_vector`가 평가 전에 독립적으로 동결 가능하다.
- **입력**: CL-C generator status, counsel 문서, vector 후보의 val-only 결과, split manifest.
- **지표**: generator fidelity status, exact `wall_member(h)` 존재율, license decision, handle-universe hash 일치, test access count.
- **제안 합격선**: CL-C/PR-1 fidelity `PASS`; counsel이 각 외부셋의 training/eval/weight 보관을 서면 허용하거나 해당 arm을 제거; `best_vector` hash와 handle universe 동결; test access 0.
- **킬 조건**: fidelity FAIL/미실행, 벽 handle truth 부재, NC product-path 격리 불가, baseline이 test를 이미 본 경우.
- **예산**: CPU·문서 감사 반나절~1일, GPU 0.
- **시드**: 없음.
- **산출**: `PRECONDITION_PASS` 또는 구체적 `OPEN/FAIL`. OPEN 상태에서는 P4-1의 순수 geometry unit test 외 성능 셀을 실행하지 않는다.

### Cell P4-1 — CRS·crop·collision 결정성 harness

- **가설**: model과 무관하게 pixel↔handle relation을 exact하게 복원할 수 있다.
- **입력**: analytic micro-scenes와, fidelity 판정에는 쓰지 않는 최소 geometry fixtures. straight/curve, clipping, scale/unit, rotate/reflect/translate, nested INSERT, 한 pixel 다중 handle, subpixel thin line을 포함한다.
- **지표**: `MAPACC`, `CRS_error`, round-trip point error, collision tuple recall/precision, IR geometry hash 보존, ID-randomization logits equality.
- **제안 합격선**: 전체와 각 transform/collision stratum에서 `MAPACC≥0.995`; `CRS_error≤0.5%`; handle/geometry hash 변화 0; ID buffer permutation 전후 logits 불변.
- **킬 조건**: CRS/back-projection 오류 0.5% 초과, 단일-ID winner로 collision 소실, crop 역변환이 원 fold/handle을 바꿈, ID가 network tensor에 들어감.
- **예산**: 로컬 CPU 1일, 작은 GPU smoke test 1시간 이내.
- **시드**: deterministic; rasterization stochasticity가 있으면 오류로 처리한다.
- **주의**: 이 셀 PASS는 성능 증거가 아니라 측정기 자격이다.

### Cell P4-2 — 200-block cheapest probe

- **가설**: 작은 raster branch가 P2/P3 또는 현재 최강 vector가 놓친 curved·hatch·single-line handle에서 독립 lift 신호를 보인다.
- **입력**: fidelity-PASS base block 200개×render style 4개. geometry group split과 style-family holdout을 동시에 적용한다.
- **arm**: frozen `best_vector`, small U-Net raster, convex fusion, label-shuffled raster.
- **지표**: stratum별 handle AUPRC difference, 전체 handle AUPRC difference, Brier, REL/RES, MAPACC, unseen-style drop, zero/all-wall sentinel confusion.
- **제안 합격선**: full claim band를 조기 확인하되 표본 부족 시 PASS가 아니라 `INCONCLUSIVE_CONTINUE`만 허용한다. 즉 각 stratum point lift `≥0.08`, 전체 non-inferiority lower bound `≥-0.02`, MAPACC `≥0.995`, style drop `≤0.10`, REL `≤0.04`, RES `≥0.02`이면 확대한다. 각 유리 stratum의 paired CI 하한은 0보다 커야 한다.
- **킬 조건**: mapping 오류 초과, fusion 전체 하락이 0.02 초과, 세 stratum 모두 lift CI 하한이 0 이하, shuffle arm이 일관된 신호를 보임, NC 격리 실패.
- **예산**: local render+GPU 1일, 작은 모델만; DGX 0.
- **시드**: 17로 smoke/screen, 동결 구성 17·29·43. style split 자체 seed는 manifest에 하나로 고정한다.
- **결정**: 한 stratum만 유리하면 그 stratum을 사후 재정의해 claim을 축소하지 않는다. 새 claim은 별도 prereg다.

### Cell P4-3 — CubiCasa representation 개발

- **가설**: 실제 사람 라벨 raster context가 긴 평행 hard negative와 wall edge를 vector feature와 다른 방식으로 분리한다.
- **입력**: 고정 train 4,200에서 fit/cal-A/cal-B, val 400; test 400은 닫아 둔다. 386만 train 선분은 drawing group으로만 분할한다.
- **arm**: U-Net과 ResNet-18-FPN screen, `best_vector`, raster-only, fusion, shuffle control. 큰 encoder는 제외한다.
- **지표**: pixel AUPRC(진단), SEG-IR line/handle-like AUPRC, hard-negative class별 error, Brier/REL/RES, drawing-macro와 pooled metric, runtime/VRAM.
- **제안 합격선**: val에서 fusion이 전체 handle-like AUPRC `best_vector-0.02` 이상이고, 사전 benefit strata에 방향성 lift가 있으며, REL/RES band를 통과해야 P4-4로 간다. shuffle arm은 constant prevalence 대비 의미 있는 lift가 없어야 하고 AUROC는 chance와 양립해야 한다.
- **킬 조건**: architecture를 바꿔도 raster-only와 fusion이 vector error를 복제하고 전체가 0.02 초과 하락; crop leakage 발견; shuffle control 이상; memory가 512 patch에서도 로컬 계획을 불가능하게 함.
- **예산**: 로컬 GPU screen 1일, 선택 구성 3-seed 재학습 1일, RAM 64GB 내 streaming.
- **시드**: 17 screen, 17·29·43 locked rerun. seed별 성적을 숨기지 않고 ensemble과 함께 보고한다.
- **해석 제한**: CubiCasa PASS만으로 native-DWG handle claim을 해결하지 않는다.

### Cell P4-4 — Held-out calibration·fusion

- **가설**: raster와 vector의 상보성이 단순 convex fusion으로 보존되고, 확률 calibration gate를 만족한다.
- **입력**: P4-3에서 동결된 branch logits; cal-A/B와 val.
- **비교**: uncalibrated branches, branch-calibrated vector/raster, convex fusion. isotonic 등 고자유도 방식은 sample 부족 시 제외한다.
- **지표**: Brier(primary score type), REL, RES, handle AUPRC, Expected Calibration Error는 참고만, `α`, missing-raster 비율.
- **제안 합격선**: val fusion `REL≤0.04`, `RES≥0.02`; 전체 AUPRC non-inferiority; 어느 benefit stratum에서도 vector보다 방향이 뒤집히지 않음. 동률이면 더 작은 raster weight를 채택한다.
- **킬 조건**: calibration을 맞추면 resolution이 무너짐, `α=0`이 최선인데도 raster claim을 유지해야만 성능이 나옴, cal-A/B를 합쳐야 gate를 통과함, val을 calibrator fit에 재사용함.
- **예산**: CPU 수 시간, 추가 GPU inference 1회 이하.
- **시드**: branch 3-seed ensemble logits에 단일 calibrator; seed별 calibration도 보조 보고.

### Cell P4-5 — OOD style·metamorphic·proxy 독립성

- **가설**: lift가 특정 renderer의 stroke/alias artifact가 아니며, 다른 truth source와의 불일치가 측정 가능하다.
- **입력**: unseen synthetic style+unseen geometry, CubiCasa val, counsel-cleared FloorPlanCAD pixel arm, 1.dwg unlabeled operational arm.
- **지표**: seen→unseen style handle AUPRC drop, rigid/unit/scale transform score drift, MAPACC, source별 error overlap·3원 disagreement table, zero/all-wall sentinel, FloorPlanCAD pixel/line metric, 1.dwg runtime·peak memory·geometry hash.
- **제안 합격선**: unseen render-style AUPRC 하락 `≤0.10`; MAPACC/CRS gate 유지; rigid transform에서 handle ranking과 frozen-threshold label이 보존; zero-wall sentinel에서 양성 0, all-wall sentinel recall 제안선 0.95 이상; source별 결과를 평균 하나로 합치지 않음.
- **킬 조건**: style drop 초과, scale/crop에서 mapping 오류, sentinel collapse, 합성·CubiCasa·FloorPlanCAD가 같은 평행 prior 오류만 반복해 독립 이득이 없음, 1.dwg에서 geometry를 수정해야만 실행 가능.
- **예산**: 로컬 CPU/GPU 1일; FloorPlanCAD는 counsel 전 0실행; DGX 0.
- **시드**: 17·29·43 ensemble 고정. OOD style 선택은 결과를 보기 전에 고정한다.
- **주의**: packet에 FloorPlanCAD native handle mapping이 없으므로 해당 결과는 최종 handle gate가 아니다.

### Cell P4-6 — 봉인된 최종 단발 판정

- **가설/claim**: P4가 curved, hatch, single-line 각각에서 `best_vector`를 개선하고 전체 비열등성·mapping·OOD·calibration gate를 모두 통과한다.
- **선행 freeze**: render manifest, CRS contract, test handle universe, model hash-of-hashes, `best_vector` hash, calibrator/`α`/`τ`, strata, bootstrap code, JSON schema.
- **primary 지표와 합격선**:
  - curved, hatch, single-line **각각** handle AUPRC point lift `≥0.08` 및 paired CI 하한 `>0`.
  - 전체 handle AUPRC difference의 non-inferiority 하한 `≥-0.02`.
  - synthetic `MAPACC≥0.995`, 즉 CRS error `≤0.5%`.
  - unseen render-style AUPRC 하락 `≤0.10`.
  - handle probability `REL≤0.04`, `RES≥0.02`.
  - 최종 handle/geometry가 IR과 동일하고 NC artifact가 product weight path와 분리됨.
- **보조 지표**: pixel AUPRC/IoU, F1/precision/recall at frozen `τ`, drawing-macro metric, error taxonomy. 보조 지표는 실패한 primary gate를 구제하지 못한다.
- **킬 조건**: 위 결합조건 중 하나라도 거짓, 필요한 stratum에 positive/negative가 없어 AUPRC가 정의되지 않음, artifact/hash 누락, test access가 1을 초과함. 표본 부족은 PASS가 아니라 `OPEN`이다.
- **예산**: 모든 test source를 여는 orchestrated inference 1회와 report 생성; 재학습 0.
- **시드**: 동결 3-seed ensemble 하나. test 후 best seed 선택 금지.
- **산출**: `wsd_eval_p4.json`, evidence xlsx, model/render/CRS manifest. 실제 실행 전에는 생성하지 않으며, resolution trigger는 이 세 hash가 동결된 뒤 JSON이 생성되는 순간이다.

### 판정 논리

```text
PASS = preconditions
   AND every(curved, hatch, single_line lift point >= 0.08)
   AND every(benefit-stratum lift CI lower > 0)
   AND overall AUPRC NI lower >= -0.02
   AND MAPACC >= 0.995
   AND unseen_style_drop <= 0.10
   AND REL <= 0.04
   AND RES >= 0.02
   AND geometry_is_IR_original
   AND NC_registry_isolated
   AND test_access_count == 1
```

이 conjunctive 논리는 평균 점수나 좋은 pixel metric으로 한 gate의 실패를 상쇄하지 않는다.

---

## 7. Red team 티켓 응답

패널 보고서에 이 제안과 직접 연결되어 서술된 티켓만 번호와 문구를 대응한다. 패킷에 상세 원문이 없는 T8–T33의 나머지 번호는 내용을 추측하지 않는다.

| 티켓/위험 | P4에 미치는 공격 | 해소 또는 수용 입장 |
|---|---|---|
| **T1 / PR-2: truth proxy 독립성** | synthetic·CubiCasa·FloorPlanCAD가 모두 평행 이중선 prior를 공유하면 다중 증거가 아니라 편향 반복이다. | P4-5에서 동일 error taxonomy와 가능한 동일-def 3원 disagreement를 분리 보고한다. source 평균 금지, 대각 성능과 비대각 전이를 별도 표로 둔다. 독립성이 보이지 않으면 real 일반화 claim을 죽인다. |
| **T2 / PR-1: 벽 synthetic generator 부재와 fidelity** | exact handle 평가의 기반 자체가 아직 없다. 현재 B1은 FAIL이고 벽 코드도 없다. | P4-0 hard gate. CL-C generator가 `wall_member(h)`와 곡선/HATCH/single-line/INSERT를 만들고 외부 fidelity gate PASS 전에는 성능 probe를 하지 않는다. micro-scene은 측정기 unit test일 뿐 성능 증거가 아니다. |
| **T5 / PR-3: NC 및 원 도면 권리** | 외부셋 학습 checkpoint가 제품 weight로 섞일 수 있다. | counsel 서면 전 학습 0. 이후에도 NC registry, dataset manifest hash, product loader deny test를 강제한다. 분리 불가 시 즉시 kill한다. |
| **T6: 평가 단위 혼동** | pixel segmentation 성적이 좋아도 handle resolution은 틀릴 수 있다. | pixel/handle sheet, metric, CI를 완전히 분리하고 최종 PASS는 handle-only로 한다. geometry/handle은 IR에서만 가져온다. |
| **T7: zero-wall 탐지기와 recall floor** | 위반율이나 calibration만 최적화하면 전부 0인 모델이 통과할 수 있다. | zero-wall와 all-wall sentinel을 P4-2/P4-5에 넣고 frozen-threshold recall floor를 둔다. primary AUPRC와 RES gate도 constant predictor를 배제한다. |
| **T13: DGX Ornith vision 지원** | 승인된 DGX가 실제 vision encoder를 돌릴 수 있다는 보장이 없다. | DGX/Ornith는 optional expansion이다. reachability와 vision support를 먼저 확인하며, 실패하면 `NOT_RUN`; 로컬 small model 판정은 계속한다. |
| **T17: 동일-def 불일치 구조** | proxy 간 전이만 보면 동일 사례에서 왜 다른지 숨는다. | 가능한 공통 IR/line support key에서 per-handle disagreement cube를 만들고, 공통 key가 없는 FloorPlanCAD는 억지 join하지 않고 `NOT_IDENTIFIABLE`로 남긴다. |
| **T22: P2/P3 및 vector 선결** | 약한 baseline을 고르면 raster lift가 부풀려진다. | `best_vector`를 test 전에 fast_score, HGB, 완료된 P2/P3 중 val-only 최강으로 동결한다. P2/P3 미완료이면 claim resolution을 OPEN으로 유지하거나 명시한 현재 최강과만 제한 비교한다. |
| **T24: exact pixel→handle harness** | CRS·crop·collision 오류가 성능처럼 보일 수 있다. | P4-1을 학습보다 먼저 수행하고 독립 analytic oracle, set-valued collision buffer, MAPACC/CRS hard gate, ID-input isolation test를 둔다. 0.5% 초과면 중단한다. |
| **T31: raster가 CL-B zero-pair 회수를 넘어서는가** | coverage-complete vector가 같은 miss를 더 싸게 해결하면 raster 본선은 불필요하다. | 동일 frozen handle universe에서 CL-B/P2/P3와 curved/HATCH/single-line lift를 비교한다. vector가 full gate를 만족하거나 fusion의 `α=0`이 최선이면 P4를 죽인다. |
| **T34: 인용 experiment status** | 문헌이 load-bearing 실측처럼 오용될 수 있다. | 문헌은 방법론 계보에만 사용하고 본 계획의 수치 prior로 쓰지 않는다. 실행되지 않은 인용은 evidence grid에서 `experiment_executed=false`를 유지한다. 서지 불확실 항목은 `요검증`이다. |

추가로 패널의 R23 CRS kill risk는 T24로, R12 NC kill risk는 T5로 흡수해 응답했다. FloorPlanCAD의 handle bridge 부재는 “해결됨”으로 꾸미지 않고 accepted OPEN risk로 남긴다.

---

## 8. 인접 제안과의 관계 및 사망 조건

### 8.1 병합 가능한 지점

- **CL-C / PR-1**: exact `wall_member(h)`, fidelity-PASS generator, WSD-EVAL-v1 fold와 hidden mutation family를 그대로 소비한다. P4가 별도 synthetic truth를 만들지 않는다.
- **CL-B**: normalization·INSERT world transform·unit anchoring을 renderer 앞단 IR canonicalization으로 공유한다. 또한 CL-B가 `best_vector` 후보가 된다.
- **CL-D**: rigid transform·unit·scale·explode·layer rename battery와 zero/all-wall sentinel을 P4 OOD cell에 공유한다. 단, raster aliasing과 CRS relation을 별도 보고한다.
- **CL-E**: synthetic/CubiCasa/FloorPlanCAD의 source×eval matrix와 동일-def disagreement schema를 공유한다.
- **CL-F의 P2/P3**: vector feature branch와 strongest baseline을 공유한다. raster branch는 이 결과를 대체하지 않고 calibrated fusion한다.
- **CL-G의 P5/doe P6**: render manifest, CRS contract, ID buffer와 evidence export를 공용화할 수 있다. VLM은 별도 배심/silver arm이며 P4 network 입력이나 truth가 아니다.
- **CL-J room/face-first**: room/face feature가 deterministic IR에서 계산되어 truth leakage가 없다면 향후 vector branch feature가 될 수 있다. P4 primary에는 사후 추가하지 않는다.

### 8.2 차별점

P4는 pure vector classifier도, raster-only floorplan parser도, VLM silver judge도 아니다. 차별점은 다음 결합에 있다.

1. learned raster context와 deterministic vector feature를 별도 branch로 유지한다.
2. pixel score를 auditable multi-hit relation으로 기존 handle에 되돌린다.
3. fusion weight와 확률 calibration을 held-out drawing에서 고정한다.
4. geometry generation을 하지 않아 최종 geometry의 SoT를 IR에 남긴다.
5. pixel 성능과 handle 성공을 분리해 raster vision이 truth로 승격되는 경로를 차단한다.

### 8.3 이 제안이 죽어야 하는 조건

다음 중 하나면 P4를 PARK 또는 FAIL로 끝내며, architecture 확대나 DGX 투입으로 자동 연장하지 않는다.

- PR-1/CL-C generator가 fidelity gate를 통과하지 못하거나 exact wall handle을 제공하지 못한다.
- production renderer와 독립 oracle의 CRS/back-projection 오류가 0.5%를 초과한다.
- curved, hatch, single-line 중 하나라도 최종 point lift 0.08을 만족하지 못하거나 lift CI 하한이 0 이하이다.
- 전체 handle AUPRC가 `best_vector`보다 허용 0.02를 넘어 하락한다.
- unseen render style에서 AUPRC 하락이 0.10을 초과한다.
- REL 0.04 이하와 RES 0.02 이상을 동시에 만족하지 못한다.
- ID buffer 또는 handle-derived 정보가 model input으로 흘러간다.
- FloorPlanCAD raster mask를 독립 mapping 없이 handle truth로 써야만 claim이 성립한다.
- counsel이 외부셋 사용을 허용하지 않거나 NC checkpoint를 product weight 경로에서 격리할 수 없다.
- CL-B/P2/P3가 동일 benefit strata를 더 단순한 vector 방법으로 회수해 fusion 최적 weight가 `α=0`이 된다.
- OOD lift가 renderer alias·line width·crop signature에만 의존하거나 shuffle control이 신호를 보인다.
- test 단발, manifest/hash, evidence xlsx 계약을 지키지 못한다.

표본 부족으로 CI 또는 stratum AUPRC가 정의되지 않으면 성공도 실패도 꾸미지 않고 `resolution_verdict=open`과 `abstain_flag=empty_reference_class`를 유지한다. 새 데이터와 새 prereg 없이 subgroup을 합치거나 합격선을 낮추지 않는다.

### 8.4 최종 권고

P4의 가장 싼 정직한 경로는 “큰 encoder”가 아니라 **P4-0 → P4-1 → 200-block P4-2**다. 이 세 단계에서 generator·mapping·작은 raster context 중 하나라도 실패하면 DGX와 대형 모델 비용을 쓰지 않는다. 세 단계가 통과한 경우에만 CubiCasa representation 개발과 held-out calibration으로 확대한다. 최종 결론은 `wsd_eval_p4.json`이 생성되고 모든 결합 handle gate가 참일 때만 PASS다.

DOSSIER_COMPLETE: calibration_P4
