# feyerabend P5 심층 도시에 — 래스터 표현 학습 + 벡터 결정론 게이트

## 판정 전제와 현재 상태

이 문서는 P5를 곧바로 제품 채택하자는 문서가 아니다. 현재 패널 판정대로 P5의 “래스터 본선” 주장은 **PARKED**이며, CL-B의 커버리지 보강 뒤에도 래스터 후보가 추가 회수를 보이는지 시험하기 위한 실행 계약이다. 현 시점에는 학습·평가가 실행되지 않았으므로 이 문서가 새 PASS나 새 성능을 주장하지 않는다.

이하에서 수치의 출처를 구분한다.

- **관측값**은 전부 패킷의 2026-07-18 실측 다이제스트에서 가져온다.
- **패킷 밴드**는 P5 원안에 이미 적힌 합격선이다.
- **제안값**은 앞으로 프리레지스트레이션할 하이퍼파라미터·허용오차·예산이며 측정 결과가 아니다.
- 논문명과 방법론 계보는 웹 검색 없이 일반 지식으로 정리했다. 구현 착수 전에 서지와 라이선스를 다시 확인하며, 확신이 낮은 항목은 `요검증`으로 표시한다.

핵심 경계는 다음 한 문장이다.

> 래스터 모델은 “어디를 검사할지”만 제안하고, 어떤 핸들이 벽으로 합격하는지는 래스터 확률·VLM 문장·silver 표 없이 동작하는 고정된 벡터 게이트가 결정한다.

연구 결과 상태는 네 단계로 분리한다.

1. `BLOCKED`: 권리, split, 체크섬, CRS 중 하나라도 봉인되지 않음.
2. `PARK`: 값싼 프로브 또는 학습 밴드 미달.
3. `RESEARCH_VIABLE`: NC 격리 연구 arm이 P5 밴드와 CL-B 비교를 통과함. 제품 탑재를 뜻하지 않음.
4. `PRODUCT_CANDIDATE`: 권리상 허용된 데이터로 만든 가중치만으로 이득이 재현되고 제품 트리 격리 검사까지 통과함.

---

## 1. 이론적 근거·선행연구

### 1.1 공격 대상의 정확한 층위

“vision-as-SoT 기각”은 관측을 판정으로 승격하지 말라는 규칙이지, 관측 표현을 학습하지 말라는 규칙은 아니다. P5는 다음 세 층을 분리한다.

- **표현층**: 래스터의 국소·중거리 문맥으로 벽처럼 보이는 영역을 찾는다.
- **제안층**: 그 영역을 원래 CAD의 기존 핸들·선분 집합으로 귀속해 제한된 후보 목록을 만든다.
- **판정층**: 후보 순위나 픽셀 확률을 보지 않고, 벡터 기하·CRS 무결성·metamorphic·sentinel·라이선스 규칙으로 합격시킨다.

이 구분은 통계 모델을 증거 수집기에 두되 최종 계약은 결정론 검증기가 집행하는 generate-and-test, proposal-and-verification, neuro-symbolic 파이프라인의 계보다. Faster R-CNN의 proposal/head 분리와 개념적으로 닮았지만, P5에서는 두 번째 단계가 또 다른 학습 분류기가 아니라 **독립적으로 봉인된 결정론 게이트**라는 차이가 있다.

### 1.2 왜 래스터 표현이 별도 정보를 가질 수 있는가

실측에서 벡터 v1은 CubiCasa5k val에서 재현율 0.981이지만 정밀도 0.134, F1 0.2358이었다. FP의 주범은 Direction 화살표, BoundaryPolygon, Door, Window, DimensionMark였다. 길이 필터도 F1 0.335에서 천장이 생겼다. 이는 “평행하고 두께 대역에 든다”는 국소 기하만으로는 긴 비벽 구조를 분리하기 어렵다는 증거다.

같은 여섯 벡터 특징에 HistGradientBoosting을 적용하자 val F1 0.517, AUC 0.9215로 올라갔고 로지스틱은 F1 0.053이었다. 즉 비선형 학습 자체는 이미 가치가 있지만, GBDT 역시 parallel/thickness/junction/log-length/orientation이라는 벡터 특징만 본다. 래스터 분할기는 문·창의 반복 모양, 치수선의 화살촉과 문자 주변, 방 경계의 더 넓은 배치, 벽 리본 내부의 연속성 같은 **주변 문맥**을 추가로 볼 수 있다. P5가 검증할 것은 바로 이 추가 조건부 정보이며, “딥러닝이므로 더 낫다”가 아니다.

반대로 이 가설이 틀릴 이유도 강하다. 래스터화는 선 굵기·해상도·안티앨리어싱이라는 새 작성 관례를 만들며, FloorPlanCAD의 벽 mask가 실제 DWG의 곡선·블록·해치 분포를 대표한다는 보장은 없다. 현재 합성팩은 LINE/LWPOLYLINE/INSERT만 포함해 B1 충실도 KS 0.5792, TV 0.265로 FAIL했고, 실제 도면에는 SPLINE 3,973개, ARC 2,198개, HATCH 264개가 섞여 있다. 따라서 래스터 arm도 CL-B와 CL-C를 우회할 수 없다.

### 1.3 방법론 계보

다음은 구현 후보를 정하는 문헌 계보다. 연도와 서지 세부는 일반 지식이며 릴리스 전 재확인한다.

| 계보 | 구체 방법·논문·시스템 | P5에서의 역할 | 주의점 |
|---|---|---|---|
| Dense semantic segmentation | Long et al., *Fully Convolutional Networks for Semantic Segmentation*; Ronneberger et al., *U-Net* | 픽셀별 wall probability의 가장 단순한 학습 기준선 | 자연영상 사전학습의 편향과 작은 배치 정규화 |
| 다중 스케일 문맥 | Chen et al., *DeepLabv3+* | 치수선·가구와 벽을 주변 문맥으로 분리하는 비교 arm | 고해상도 도면에서 메모리 비용 증가 |
| 경량 transformer segmentation | Xie et al., *SegFormer* | 16GB GPU에서 우선 시험할 주 모델 계열 | 위치·해상도 변화가 실제 scale 불변성을 보장하지 않음 |
| 범용 mask proposal | Kirillov et al., *Segment Anything*; SAM 2 계열 | 파인튜닝 전 값싼 자동 mask 후보 프로브 | “벽” 의미를 모르므로 zero-shot 성능을 가정하지 않음 |
| 통합 mask classification | Cheng et al., *Mask2Former* | 자원이 허용될 때만 비교할 상한 arm | P5의 값싼 1차 경로로는 과함 |
| 도면 특화 raster 해석 | Kalervo et al., *CubiCasa5K: A Dataset and an Improved Multi-task Model for Floorplan Image Analysis*; Zeng et al., *Deep Floor Plan Recognition Using a Multi-task Network with Room-boundary-Guided Attention* | 방/경계/아이콘 문맥이 벽 분할에 도움을 줄 수 있다는 선행 사례 | 패킷의 CubiCasa SEG-IR 계약과 논문 원 데이터 계약을 혼동하지 않음 |
| raster-to-vector 보조 | Hough transform, Line Segment Detector, marching squares, skeletonization, Douglas–Peucker | mask component를 기존 CAD 핸들에 조회하기 위한 진단·색인 보조 | 새 선을 만들어 SoT로 쓰지 않음 |
| 구조 복원 transformer | HEAT 계열 structured reconstruction (`요검증`) | 장기 비교 후보 | 서지·코드·라이선스·출력 좌표 계약 모두 요검증 |

FloorPlanCAD의 정확한 원 논문·공식 split·NC 조항은 패킷만으로 확정할 수 없으므로 모두 `요검증`이다. 이 데이터에 관한 확정 사실은 “로컬에 5,308장과 벽 bbox/segmask가 있고 벡터 SVG는 없다”는 다이제스트뿐이다.

### 1.4 P5가 증명해야 할 반사실

P5의 counter-theory는 다음 비교에서만 살아남는다.

\[
I(Y;R\mid X_{geom},G_{CLB}) > 0
\]

여기서 \(Y\)는 사람 라벨이 있는 축의 벽 핸들 진리, \(R\)은 래스터 표현, \(X_{geom}\)은 기존 벡터 특징, \(G_{CLB}\)는 CL-B가 복구한 정규화·INSERT 전개·단위 정박 정보다. 즉 CL-B와 GBDT를 조건으로 둔 뒤에도 래스터가 고유한 true positive를 더해야 한다. 이 조건부 정보가 0이면 “vision을 학습에 열자”는 명제는 이 과업에서 실익이 없으며 P5는 죽는다.

---

## 2. 알고리즘 정확 스펙

### 2.1 입력·출력 계약

도면 \(d\)의 입력을 다음으로 고정한다.

\[
D_d=(I_d,V_d,A_d,H_d,Y_d,L_d,S_d)
\]

- \(I_d\): 모델에 입력할 래스터. CAD 축에서는 모든 엔티티를 클래스·레이어명 없이 같은 스타일로 렌더한다.
- \(V_d\): CL-B 정규화 이후의 읽기 전용 벡터 기하.
- \(A_d\in\mathbb{R}^{3\times3}\): world 좌표에서 pixel 좌표로 가는 명시적 2D affine 행렬.
- \(H_d\): 원본 핸들과 정규화 선분 사이의 역참조 테이블. INSERT라면 중첩 transform chain까지 보존한다.
- \(Y_d\): 존재할 때만 쓰는 사람/데이터셋 벽 라벨. 실도면에서는 `None`이다.
- \(L_d\): 라이선스·출처·체크섬·split group.
- \(S_d\): 렌더러 버전, viewport, crop, padding, y-axis 방향, antialias, line width를 포함한 스타일 manifest.

래스터 후보기는 다음 레코드만 출력한다.

```text
CandidateRecord {
  drawing_id,
  rank,
  source_component_id,
  original_handles[],
  normalized_segments[],
  nomination_score,
  raster_bbox,
  world_bbox,
  transform_hash,
  model_hash,
  license_class,
  unmatched_reason | null
}
```

최종 출력은 `AcceptedWallRecord`이며, `original_handles[]`, 게이트 버전, 각 결정론 조항의 pass/fail, 변환·입력 체크섬만 남긴다. `nomination_score`는 감사 로그에는 남지만 판정 함수 인자로 전달하지 않는다.

### 2.2 렌더 CRS와 역투영

2D 정사영만 허용한다.

\[
\begin{bmatrix}u\\v\\1\end{bmatrix}
=A_d
\begin{bmatrix}x\\y\\1\end{bmatrix},\qquad
\begin{bmatrix}x\\y\\1\end{bmatrix}
=A_d^{-1}
\begin{bmatrix}u\\v\\1\end{bmatrix}
\]

행렬에 perspective 성분이 있거나 역행렬 조건이 나쁘거나, clip/padding을 manifest로 재현할 수 없으면 그 도면은 `CRS_REJECT`다. 추정한 viewport나 이미지 EXIF에 기대지 않는다.

CAD 렌더 때 색상 영상과 **handle-ID buffer**를 같은 draw call 순서·같은 \(A_d\)로 함께 만든다. 얇은 선의 aliasing 때문에 ID buffer는 픽셀 하나에 여러 핸들이 겹칠 수 있는 set-valued buffer로 저장한다. model mask를 world 선으로 새로 벡터화하는 대신, 먼저 ID buffer와 겹친 기존 핸들을 얻고, 빈 영역만 \(A_d^{-1}\)로 world polygon에 바꿔 R-tree로 주변 원본 선분을 조회한다. 주변 선분을 못 찾은 component는 `UNMATCHED_RASTER_COMPONENT`로 격리하며 새 CAD 선을 생성하지 않는다.

FloorPlanCAD에는 벡터 SVG가 없으므로 이 데이터만으로 handle 역투영 정확도를 측정하지 않는다. FloorPlanCAD는 mask 학습·IoU 축이고, 역투영은 synthetic CRS microfixture와 CubiCasa SEG-IR, 실도면 staged DXF 축에서 검증한다.

### 2.3 래스터 모델과 손실

주 모델은 경량 semantic segmenter다. 우선순위는 `SegFormer-B0/B2 → U-Net 계열 → 자원 여유가 있을 때 DeepLabv3+`로 제한한다. 로컬 qwen2.5-VL-3B floorplan SFT/GRPO 모델은 출처 데이터 오염 가능성을 먼저 감사한 뒤 별도 `open_vlm_feature` arm으로만 둔다. 주 segmentation 결과와 섞어 ensemble하지 않는다.

모델은 \(P_d=f_\theta(I_d)\in[0,1]^{H\times W}\)를 출력한다. 기본 손실은 다음이다.

\[
\mathcal{L}=lambda_b\,\mathrm{BCE}_{balanced}(P,Y)
+\lambda_d\left(1-\frac{2\sum PY+\epsilon}{\sum P+\sum Y+\epsilon}\right)
+\lambda_e\,\mathrm{BCE}(\nabla P,\nabla Y)
\]

- 첫 항은 벽/비벽 불균형을 다룬다.
- 둘째 항은 mask 겹침을 직접 최적화한다.
- 셋째 항은 얇은 벽 경계의 번짐을 억제하는 선택 항이다.
- 경계 손실을 넣고 뺀 비교는 val에서만 하며 test를 열어 고르지 않는다.

제안 하이퍼파라미터 공간은 다음처럼 작은 격자로 봉인한다. 이는 관측값이 아니다.

| 항목 | 제안 공간 |
|---|---|
| 입력 긴 변 | 768, 1024, 1536 px; 큰 도면은 overlap tile |
| optimizer | AdamW |
| learning rate | \(10^{-5},3\times10^{-5},10^{-4}\) |
| weight decay | 0.01, 0.05 |
| batch | 물리 1, 2, 4; gradient accumulation으로 유효 batch 8 |
| loss weight | \(\lambda_b=1\), \(\lambda_d\in\{0.5,1\}\), \(\lambda_e\in\{0,0.25\}\) |
| mask threshold \(\tau\) | 0.3, 0.5, 0.7; val에서 하나 봉인 |
| optimizer stop | 최대 50 epoch, val primary metric 7 epoch 무개선 시 중단 |
| augmentation | 90도 배수 회전, 반사, 기록된 crop/pad, 제한된 stroke/contrast jitter |

비선형 warp처럼 world↔pixel 대응을 설명할 수 없는 증강은 금지한다. 학습 증강에는 image와 mask에 같은 transform을 적용하고 transform을 seed log에 남긴다.

### 2.4 후보 생성

핸들 \(h\)의 렌더 지지 영역을 \(R_r(h)\)라 하고 반경 \(r\)은 제안 격자 \(\{1,2,4,8\}\) pixel에서 val로 봉인한다. nomination score는 다음처럼 정의한다.

\[
q(h)=\frac{\sum_{p\in R_r(h)}P_d(p)}{|R_r(h)|+\epsilon}
\]

mask connected component \(C_j=\{p:P_d(p)\ge\tau\}\)마다 다음 두 경로를 합친다.

1. **ID-overlap 경로**: \(C_j\)와 겹치는 handle-ID buffer의 핸들을 가져온다.
2. **world-query 경로**: component contour를 \(A_d^{-1}\)로 옮겨 spatial index에서 근접 원본 선분을 조회한다.

후보는 component별 중복을 원본 handle 집합으로 합치고 \(q\)로 정렬한다. 평가 budget은 패킷 밴드와 맞춰 도면정의당 top-20으로 고정한다. 같은 handle이 여러 component에 걸리면 가장 높은 score만 순위에 쓰되 모든 provenance는 보존한다.

중요한 불변조건은 다음과 같다.

- rank를 만들 때 레이어명, silver 답, gate pass/fail, test 라벨을 쓰지 않는다.
- 모델이 그린 contour 자체를 벽 geometry로 저장하지 않는다.
- 기존 핸들로 귀속되지 않은 mask는 진단 출력일 뿐 벽 후보가 아니다.
- top-20 밖을 게이트에 몰래 넘기지 않는다. baseline도 같은 후보 budget을 쓴다.

### 2.5 결정론 벡터 게이트

후보 \(c\)의 온라인 판정은 다음이다.

\[
G_v(c;V,\phi)=G_{crs}\land G_{exists}\land G_{ribbon}
\land G_{continuity}\land G_{unit}\land G_{contract}
\]

- `G_crs`: transform hash, inverse round-trip, viewport, handle-ID buffer가 일치한다.
- `G_exists`: 모든 결과가 staged vector의 실제 원본 핸들로 역참조된다.
- `G_ribbon`: CL-B가 정규화한 line/polyline/arc/INSERT world geometry에서 반대 경계 지지, 접선 정렬, overlap, 폭 일관성을 계산한다. pair mode와 closed-band mode를 둘 다 허용하되 규칙 버전을 고정한다.
- `G_continuity`: junction과 끝점 연결이 고정된 snap 계약을 만족한다.
- `G_unit`: 절대 50–400mm 대역만 고집하지 않고, CL-B의 검증된 단위·치수 정박이 있으면 그 상대 대역을 사용한다. 정박이 없으면 기존 v1 대역 arm과 `UNKNOWN_UNIT` arm을 분리 보고한다.
- `G_contract`: 읽기 전용 입력, 핸들 평가 단위, candidate budget, 로그 스키마를 지킨다.

\(\phi\)에는 각도·overlap·snap·폭 대역이 들어가지만 래스터 실도면 결과를 보기 전에 CL-B/CL-C 개발 축에서 봉인한다. 기존 v1의 2도, overlap 0.5, snap 6mm, 50–400mm는 반드시 replay baseline으로 남긴다. 새 gate 설정은 이 값을 조용히 덮어쓰지 않는다.

도면 \(d\)의 최종 연구 출력은 다음뿐이다.

\[
\widehat{W}_d=\{c\in\operatorname{Top20}(q):G_v(c;V_d,\phi)=1\}
\]

release-level 판정은 별도다.

\[
G_{release}=G_v\land G_{metamorphic}\land G_{sentinel}
\land G_{synthetic\_fidelity}\land G_{license}\land G_{artifact\_isolation}
\]

현재 합성팩은 B1 FAIL이고 scale arm 일치율은 0.7624로 strict FAIL이므로 `G_synthetic_fidelity`와 `G_metamorphic`은 현재 PASS로 간주할 수 없다.

### 2.6 학습·추론 의사코드

```python
def train_research_segmenter(manifest, config):
    assert manifest.counsel_status == "CLEARED_FOR_RESEARCH"
    assert manifest.floorplancad_license_class == "NC_RESEARCH_ONLY"
    assert grouped_split_is_frozen(manifest)
    assert no_prompt_silver_in(manifest.labels, manifest.sample_weights)
    assert no_test_ids_in(manifest.train_ids, manifest.val_ids)

    model = build_segmenter(config.arch)
    for seed in PREREGISTERED_SEEDS:
        seed_everything(seed)
        for batch in grouped_train_loader(manifest.train_ids):
            image, wall_mask, recorded_transform = augment(batch)
            prob = model(image)
            loss = balanced_bce(prob, wall_mask)
            loss += config.lambda_dice * dice_loss(prob, wall_mask)
            loss += config.lambda_edge * edge_loss(prob, wall_mask)
            optimize(loss)
        save_checkpoint_with_lineage(model, seed, manifest, config)
    return sealed_checkpoint_set()


def infer_candidates(vector_doc, checkpoint, render_config):
    bundle = render_with_id_buffer(vector_doc, render_config)
    assert affine_roundtrip_ok(bundle.world_to_pixel)
    prob = checkpoint.predict(bundle.image)
    components = threshold_and_components(prob)
    candidates = attribute_only_to_existing_handles(
        components, bundle.id_buffer, bundle.world_to_pixel.inverse,
        spatial_index(vector_doc)
    )
    return rank_and_cap(candidates, k=20)  # nomination only


def accept_candidates(vector_doc, candidates, frozen_gate):
    # Deliberately receives neither probability map nor nomination score.
    accepted = []
    for candidate in candidates:
        decision = frozen_gate.evaluate(
            handles=candidate.original_handles,
            normalized_geometry=vector_doc.geometry,
            transform_hash=candidate.transform_hash,
        )
        audit(decision)
        if decision.all_clauses_pass:
            accepted.append(decision.accepted_wall_record)
    return accepted


def product_pack(checkpoints, allowlist):
    assert all(c.license_class != "NC_RESEARCH_ONLY" for c in checkpoints)
    assert checksum_set(checkpoints) <= allowlist
    assert no_research_path_imports()
    return reproducible_product_artifact()
```

### 2.7 frontier VLM silver와의 물리적 분리

프런티어 VLM API는 현재 유일 결재 게이트가 미승인이다. 또한 현 silver Pearson은 0.2911이고, 다섯 판정자는 약 두 어휘 가문으로 갈려 다섯 독립표가 아니다. 따라서 silver는 현재 자격 미달이며 다음 방화벽을 둔다.

- `raster_train` 큐는 FloorPlanCAD/CubiCasa 사람 라벨과 합법적으로 허용된 mask만 읽는다.
- `silver_jury` 큐는 API 승인과 E1.5 B1≥0.70 **및** B4 Pearson≥0.70을 모두 통과한 뒤에만 열린다.
- silver 산출은 loss, pseudo-label, sample weight, hard-negative mining, checkpoint 선택에 들어가지 않는다.
- silver는 봉인된 결과를 사후 비교하는 독립 열로만 evidence xlsx에 들어간다.
- local qwen feature arm도 기존 floorplan SFT/GRPO 데이터 계보를 확인하기 전에는 FloorPlanCAD 주 arm과 합치지 않는다.

---

## 3. 벽 과업 적응 설계

### 3.1 FloorPlanCAD 래스터축

패킷 자산은 5,308장과 벽 bbox/segmask이며 vector SVG가 없다. 역할을 다음으로 제한한다.

- grouped train/val/research-holdout으로 mask predictor를 학습·선택·봉인한다.
- 공식 건물/도면 group id가 있으면 그것을 사용한다. 없으면 파일명에 기대지 않고 perceptual hash와 annotation fingerprint로 근접 중복 cluster를 만든 뒤 cluster 단위로 split한다.
- bbox는 보조 crop sampler에만 쓰고 최종 진리는 segmask다.
- 연구-holdout은 val 튜닝이 끝난 뒤 한 번만 연다.
- 직접 핸들 recall이나 CRS 성공을 주장하지 않는다. 벡터가 없기 때문이다.

P5 패킷 밴드인 wall IoU≥0.60은 이 research-holdout에 적용한다. 해당 수치는 아직 달성값이 아니다.

### 3.2 CubiCasa SEG-IR 벡터축

CubiCasa5k는 5,000도면 모두 SEG-IR 변환에 성공했고, train 4,200/val 400/test 400이며 벽 선분율은 약 11.8%다. 이 축은 사람 라벨을 가진 유일한 handle-level 전이 심판으로 쓴다.

1. 입력은 SEG-IR의 모든 엔티티를 클래스 중립 스타일로 렌더한 영상이다. `Wall` 클래스는 정답 생성에만 쓰며 입력 색, 레이어, draw order에 새지 않게 한다.
2. 원래 split을 유지하고 도면 단위로만 처리한다. test 400은 모든 architecture·threshold·gate가 봉인될 때까지 경로 자체를 막는다.
3. FloorPlanCAD-only 모델을 먼저 평가해 진짜 cross-dataset transfer를 본다.
4. CubiCasa train으로 미세조정한 arm은 “동일 도메인 상한”으로 별도 표기한다. 이를 FloorPlanCAD 전이라고 부르지 않는다.
5. wall edge를 원본 handle에 귀속해 per-handle precision/recall/F1, candidate Recall@20, gate-qualified Recall@20을 계산한다.

비교기는 같은 split·같은 handle universe에서 다음을 재실행한다.

- v1 geometry detector: val F1 0.2358의 동결 설정.
- HistGradientBoosting: val F1 0.517/AUC 0.9215의 동결 artifact.
- CL-B coverage-complete deterministic baseline: 정규화·INSERT 전개·단위 정박이 끝난 최신 봉인본.
- raster-only nomination, GBDT-only nomination, 두 후보 집합의 union을 **같은 벡터 게이트와 같은 top-20 budget**으로 비교한다.

래스터가 가져와야 할 것은 단순 F1 상승만이 아니다. GBDT가 놓친 Door/Window/DimensionMark 주변의 실제 wall handle을 추가로 회수하되, 같은 gate-qualified precision을 유지해야 한다. GBDT와 raster의 union이 GBDT 단독보다 좋아지지 않으면 래스터 표현의 실용적 조건부 정보는 입증되지 않는다.

### 3.3 1.dwg 실도면축

staged DXF의 도면정의는 384개이고 최대 도면정의는 412,775 선분이다. 사람 라벨이 없으므로 여기서 precision, recall, IoU, semantic correctness를 계산하지 않는다.

실도면 평가는 다음으로 제한한다.

- CL-A가 정렬-키 아티팩트를 재계산한 뒤 확정한 zero-pair/대조 definition 목록을 사용한다.
- 벡터를 tile 렌더하되 각 tile의 affine, padding, 중복 영역을 기록하고 원본 handle로 합친다.
- `gate-qualified operational yield@20`: top-20 후보 중 봉인된 벡터 게이트를 통과하고 baseline에는 없던 원본 handle 집합의 비율을 센다.
- v0의 벽-제로 도면율 개선 0.682→0.2135는 기존 관측으로만 둔다. P5가 이를 자기 성능으로 재인용하지 않는다.
- full-vs-name-blind가 1.0이었다는 관측은 레이어명 누출이 없었던 기존 탐지기 성질이지 새 래스터 모델의 누출 없음 증명이 아니다. 새 렌더 입력을 별도로 audit한다.
- silver는 사후 disagreement 열일 뿐 진리가 아니다.

“실도면 회수”는 위 operational yield의 약칭으로만 쓴다. 사람 라벨 없는 실도면 결과를 semantic recall이라고 부르면 계약 위반이다.

### 3.4 synthetic·metamorphic축

두 종류를 분리한다.

- **CRS microfixture**: 좌표와 핸들을 정확히 아는 아주 작은 도형으로 affine round-trip과 phantom-handle 0을 검증한다. 이는 의미 충실도 주장을 하지 않으므로 현 B1 FAIL과 모순되지 않는다.
- **WSD-EVAL-v1 semantic synthetic pack**: CL-C/PR-1이 실제 SPLINE/ARC/HATCH/블록/비평행 조각 분포를 반영해 fidelity gate를 통과한 뒤에만 release 판정에 쓴다. 현재 팩은 진단용뿐이다.

metamorphic은 원본 handle 정답을 transform 전후로 추적한다. 강체·단위 arm의 기존 1.0 PASS를 보존하고, 기존 scale 0.7624 FAIL을 새 경로가 가리지 못하게 별도 열로 남긴다. 0벽과 전벽 sentinel을 반드시 포함한다.

### 3.5 누수 방지

- split은 image가 아니라 building/drawing/duplicate-cluster 단위다.
- 동일 원본의 crop, resize, annotation export는 한 group에 묶는다.
- frontier/local VLM prompt 산출은 target, pseudo-label, sample weight에 쓰지 않는다.
- test manifest는 read-once runner 외 코드에서 열 수 없다.
- gate hyperparameter는 raster 실도면 결과를 보기 전에 봉인한다.
- model threshold는 val에서만 고르고 holdout/test에 재조정하지 않는다.
- label-shuffle control을 같은 pipeline·같은 budget으로 실행하고, 그 null 분포를 넘지 못하는 모델은 학습 효과로 인정하지 않는다.
- 모든 checkpoint와 dataset shard는 SHA-256, license class, parent hash를 갖는다.

---

## 4. 데이터·컴퓨트 요구

### 4.1 자산별 사용 허용표

| 자산 | 현재 알려진 상태 | P5 사용 | 제품 반입 |
|---|---|---|---|
| FloorPlanCAD | 5,308 raster+bbox+segmask, SVG 없음, NC | counsel 서면 허용 뒤 연구 학습/holdout | NC checkpoint·파생 weight 모두 금지 |
| CubiCasa5k SEG-IR | 전량 변환, 고정 split, 사람 wall label | counsel 범위 확인 뒤 전이 평가·별도 adaptation | 라이선스 서면 범위가 허용할 때만 |
| 1.dwg staged DXF | 384 definitions, 무사람라벨 | 렌더·역투영·게이트 operational 평가 | 원본 권리와 내부 사용 계약 준수 |
| qwen2.5-VL-3B floorplan SFT/GRPO | 로컬 실존 | provenance audit 뒤 별도 feature arm | 학습 계보가 모두 허용될 때만 |
| RTX 5070 Ti | 16GB | 주 학습·배치 추론 | 해당 없음 |
| RAM | 64GB | SEG-IR index, tile cache, xlsx 집계 | 해당 없음 |
| DGX Spark | 승인됐으나 현재 unreachable | 도달 후 선택적 가속 | 필수 경로 아님 |
| frontier VLM API | 결재 미승인 | 현재 사용 안 함 | silver도 자격 게이트 전 사용 안 함 |

### 4.2 로컬 실행 계획

로컬 경로가 완결 경로다.

1. CPU/RAM에서 manifest, grouped split, render CRS, handle-ID buffer를 만든다.
2. 16GB GPU에서는 mixed precision, gradient accumulation, gradient checkpointing, overlap tile로 SegFormer-B0 또는 U-Net을 순차 학습한다.
3. 5,308장 전체를 한 tensor로 올리지 않고 shard loader를 쓴다.
4. 412,775 선분 도면정의는 R-tree와 tile별 handle-ID buffer로 처리하고, 겹침 tile 결과를 원본 handle key로 merge한다.
5. 역투영·gate·metamorphic·xlsx 집계는 로컬 CPU에서 한다.
6. out-of-memory가 나면 해상도 격자 내 낮은 단계로만 이동한다. 결과를 본 뒤 임의 crop이나 데이터 제외로 회피하지 않는다.

제안 로컬 예산은 값싼 프로브 1일 이내, 주 모델의 3-seed 개발은 architecture당 수일 범위다. 이는 실행 전 추정이며 실제 처리량 주장이 아니다.

### 4.3 DGX 계획

패킷의 DGX fine-tuning·batch inference 예산은 1–3일이지만 장비는 현재 unreachable이다. 따라서 DGX는 성공 조건이 아니다.

- 연결 회복 뒤 먼저 Ornith-35B가 vision 입력·dense mask 출력을 실제로 지원하는지 확인한다. 지원하지 않으면 T13은 “부적합”으로 닫고 text 모델을 억지로 segmentation에 쓰지 않는다.
- generic CUDA segmenter 학습이 가능하면 로컬과 같은 container digest·seed·data manifest로 속도만 옮긴다.
- DGX 결과가 로컬 결과와 다른 경우 두 hardware arm을 합치지 않고 numerical reproducibility 차이로 보고한다.
- frontier silver API 큐와 DGX 학습 큐는 credential, artifact path, budget ledger를 분리한다.

### 4.4 라이선스·artifact 격리

권리 계약은 모델 품질보다 선행한다.

- `NC_RESEARCH_ONLY`, `CLEARED_RESEARCH`, `CLEARED_PRODUCT`, `UNKNOWN` 네 license class를 둔다.
- `UNKNOWN`은 허용이 아니라 차단 상태다.
- checkpoint의 license class는 모든 parent dataset 중 가장 제한적인 등급을 상속한다.
- NC checkpoint의 quantization, LoRA merge, distillation, embedding cache도 NC 파생물로 취급한다.
- product build는 allowlist checksum과 dependency closure를 검사한다. 파일명이나 디렉터리명만으로 판정하지 않는다.
- 연구에서 성능이 나와도 권리상 허용된 데이터로 재학습한 checkpoint가 같은 gate 이득을 재현하기 전에는 제품 후보가 아니다.

---

## 5. 구현 계획

### 5.1 제안 파일 골격

다음은 향후 구현 골격이며 이 도시에 작성 과정에서 해당 파일을 생성했다는 뜻이 아니다. 실제 repository root와 기존 API signature를 먼저 확인한 뒤 맞춘다.

```text
src/e2/raster_candidate/
  contracts.py              # RenderBundle/CandidateRecord/lineage schema
  render_crs.py             # affine + tile + handle-ID buffer
  floorplancad_dataset.py   # grouped split, mask loader, duplicate cluster
  cubicasa_adapter.py       # SEG-IR neutral render + handle truth
  models.py                 # SegFormer/U-Net bounded registry
  train.py                  # seed, shuffle control, checkpoint lineage
  propose.py                # mask component -> existing handles -> top-20
  vector_gate_adapter.py    # score-free deterministic gate call
  metamorphic.py            # transform/inverse-map/sentinel battery
  license_guard.py          # ancestry + checksum + product deny
  evaluate.py               # val/holdout/read-once test runner

configs/feyerabend_p5/
  prereg_probe.yaml
  prereg_train.yaml
  prereg_gate.yaml
  prereg_test.yaml

tests/feyerabend_p5/
  test_affine_roundtrip.py
  test_nested_insert_handle_identity.py
  test_unmatched_mask_creates_no_geometry.py
  test_gate_cannot_read_raster_score.py
  test_split_group_exclusion.py
  test_nc_artifact_denied.py
  test_zero_all_wall_sentinels.py

reports/feyerabend_p5/
  evidence.xlsx
  prereg_hashes.json
  failure_ledger.jsonl
  test_once_receipt.json
```

### 5.2 기존 도구 접속점

| 기존 도구 | 접속 방식 | 금지 사항 |
|---|---|---|
| `evidence_grid` | cell id, hypothesis, manifest hash, seed, metric, failure reason을 evidence.xlsx 행으로 기록 | 여러 seed를 평균 하나로 숨기기 |
| `fast_score` | v1/CL-B/GBDT 후보의 동결 replay와 vector gate feature 계산 | raster score를 새 geometry feature처럼 최종 판정에 넣기 |
| `cubicasa_ir` | class-neutral raster, affine, handle truth adapter를 제공 | Wall class를 입력 스타일이나 draw order에 노출하기 |
| `cubicasa_ml` | 고정 split, 여섯 특징 GBDT artifact, per-handle metric을 재사용 | test를 hyperparameter 탐색에 사용하기 |

실제 함수명이 다를 수 있으므로 adapter가 기존 모듈을 감싸고, 기존 baseline 코드를 복제해 조용히 달라지게 하지 않는다. 각 baseline executable/config/hash를 evidence에 고정한다.

### 5.3 증거 xlsx 계약

필수 workbook은 최소 다음 sheet를 가진다.

- `RUN_MANIFEST`: 코드/config/data/checkpoint/render/gate hash.
- `SPLITS`: drawing/building/duplicate-cluster와 train/val/holdout/test 배정.
- `CELLS`: 가설, 상태, 시작·종료, prereg hash, kill reason.
- `METRICS_BY_SEED`: 모든 seed의 IoU, P/R/F1, Recall@20, runtime, memory.
- `CANDIDATE_AUDIT`: rank, 기존 handle, gate 각 조항, baseline membership.
- `CRS_ROUNDTRIP`: transform, 좌표 오차, handle Jaccard, phantom count.
- `METAMORPHIC`: arm별 inverse-mapped accepted-handle set과 sentinel 결과.
- `PROXY_DISAGREEMENT`: human/synthetic/metamorphic/gate/silver의 동일-def 불일치.
- `LICENSE_LINEAGE`: 모든 parent checksum, counsel status, inherited class.
- `TEST_ONCE`: unlock hash, 실행 영수증, 단일 결과, 재실행 여부.
- `FAILURES`: OOM, parse, CRS reject, empty mask, unmatched component까지 포함.

### 5.4 구현 순서와 규모

제안 순서는 `contract/lineage → CRS microfixture → baseline replay → frozen probe → 학습 → val 역투영 → metamorphic/독립성 → 봉인 test → product isolation`이다. 예상 규모는 중간 수준이다. 새 모델 자체보다 렌더/ID buffer/lineage/read-once harness가 작업의 중심이며, 이 세 부분을 생략한 “노트북 데모”는 P5 구현으로 인정하지 않는다.

---

## 6. 실험 셀 정의

### 6.1 공통 프리레지스트레이션

- 학습 seed 제안값은 `1729, 2718, 3141` 세 개다. 모든 architecture를 같은 seed로 실행한다.
- deterministic fixture는 seed 0과 미리 생성해 hash를 봉인한 transform 목록을 쓴다.
- architecture 선택은 val의 세 seed 중앙값으로 하고, 최악 seed와 seed별 원자료도 함께 보고한다.
- 최종 방식이 세-checkpoint 평균이라면 그 ensemble 정의 자체를 test 전에 봉인한다. test 400은 runner 호출 한 번에서만 읽는다.
- paired 비교의 제안 통계 규칙은 drawing/building 단위 bootstrap 95% interval이다. 선분을 독립 표본처럼 부풀리지 않는다.
- primary endpoint 순서는 `CRS 무결성 → FPCAD IoU → CubiCasa gate-qualified Recall@20 lift → CL-B/GBDT 대비 조건부 lift → metamorphic/sentinel → 라이선스 격리`다.
- 아래 제안 합격선은 결과를 보기 전에 machine-readable prereg로 봉인한다.

### Cell P5-00 — 권리·계보·split 봉인

- **가설**: 모든 학습 데이터와 checkpoint의 사용 범위, parent hash, group split을 결정할 수 있다.
- **지표**: counsel 문서 상태, unknown parent 수, cross-split duplicate-cluster 수, prompt/silver target 유입 수.
- **제안 합격선**: counsel이 해당 arm을 명시적으로 허용하고, unknown parent=0, cross-split cluster=0, silver 유입=0.
- **킬/정지 조건**: FloorPlanCAD 원 도면·라벨·파생 weight의 연구 사용이 허용되지 않으면 NC arm 중단. 제품 사용이 불허되면 연구는 가능해도 `PRODUCT_CANDIDATE` 금지. 판단 불명은 `BLOCKED`다.
- **예산**: 로컬 manifest 작업 반나절 제안; counsel 회신 시간은 별도이며 실험자가 임의 추정하지 않는다.
- **시드 계획**: 없음. manifest와 문서 checksum으로 재현한다.

### Cell P5-01 — exact CRS/handle round-trip

- **가설**: render mask 위치를 새 geometry 없이 원본 handle로 정확히 되돌릴 수 있다.
- **지표**: inverse-mapped handle-set Jaccard, 최대 world 좌표 오차, phantom handle 수, nested INSERT identity mismatch, clipped tile duplicate/miss 수.
- **제안 합격선**: handle Jaccard=1.0, phantom=0, miss=0. 좌표는 `max(1e-6 world unit, 해당 렌더의 0.5 pixel을 world로 환산한 값)` 이내.
- **킬 조건**: affine/viewport/INSERT chain의 모호성을 manifest로 제거할 수 없거나 동일 fixture에서 비결정적 handle 결과가 한 번이라도 재현되면 역투영 설계를 폐기한다.
- **예산**: 로컬 CPU 1일 제안.
- **시드 계획**: seed 0의 고정 fixture + 세 학습 seed 번호를 재사용한 무작위 transform fixture; 모두 개별 보고.

### Cell P5-02 — 파인튜닝 전 값싼 20-definition 프로브

- **가설**: 동결 open segmenter의 mask proposal만으로도 v0 wall_pairs가 놓친 definition에서 새 gate-qualified handle을 찾을 수 있다.
- **지표**: `operational_yield@20`, v0 대비 paired lift, unmatched component 비율, CRS reject, definition당 wall-clock.
- **제안 합격선**: CL-A가 확정한 20 definitions에서 lift가 양수이고, CRS phantom=0. 이 셀은 방향성 screen일 뿐 `RESEARCH_VIABLE` 판정은 하지 않는다.
- **킬 조건**: 모든 prereg stratum에서 lift≤0이거나, 이득이 unmatched raster geometry를 벽으로 허용해야만 생기면 학습 전 `PARK`.
- **예산**: 로컬 RTX/CPU 1일 이내 제안. 새 API 호출 없음.
- **시드 계획**: checkpoint·automatic prompt grid·threshold hash를 하나로 고정한 deterministic inference. 여러 checkpoint를 보고 고르지 않는다.

### Cell P5-03 — FloorPlanCAD mask 학습

- **가설**: 사람/데이터셋 wall mask로 학습한 경량 segmenter가 frozen probe와 shuffle null을 넘어 벽 외형을 학습한다.
- **지표**: val wall IoU, Dice, pixel P/R, boundary F-score, seed 분산, label-shuffle null percentile.
- **제안 합격선**: 세 seed로 선택한 봉인 방식의 val wall IoU≥0.60이며, permutation null의 95th percentile을 초과한다. 같은 기준을 research-holdout에서도 다시 만족해야 최종 통과한다.
- **킬 조건**: bounded model/hyperparameter 공간 전체가 밴드 미달, shuffle control이 비정상적으로 높음, duplicate 제거 뒤 이득 소실, 또는 NC counsel 불허.
- **예산**: 로컬 architecture당 수일 제안; DGX가 복구되면 패킷의 1–3일 배치 계획을 별도 arm으로 사용.
- **시드 계획**: 1729/2718/3141 전부. OOM seed를 조용히 버리지 않고 실패로 기록한다.

### Cell P5-04 — CubiCasa val 역투영·조건부 이득

- **가설**: FPCAD-only raster 후보가 v0뿐 아니라 CL-B와 GBDT가 놓친 사람-labeled wall handle을 같은 벡터 게이트 아래에서 추가 회수한다.
- **지표**: candidate Recall@20, gate-qualified P/R/F1, zero-pair drawing recall, v0/CL-B/GBDT 대비 paired delta, GBDT∪raster union의 unique true positives.
- **제안 합격선**: (a) v0 대비 top-20 gate-qualified recall 절대 delta≥0.25라는 패킷 밴드, (b) CL-B 대비 paired bootstrap 하한>0, (c) GBDT∪raster가 GBDT 단독보다 gate-qualified precision을 낮추지 않으면서 recall 차이 하한>0.
- **킬 조건**: CL-B 뒤 delta가 0 이하, 이득이 Wall-class 렌더 누출에서만 발생, 또는 GBDT union에 고유 true positive가 없음.
- **예산**: 로컬 render/index/inference 1–2일 제안.
- **시드 계획**: 세 checkpoint를 모두 평가하고 사전 정의 ensemble 결과를 primary로, seed별 결과를 secondary로 기록.

### Cell P5-05 — 대리 독립성·ablation

- **가설**: raster의 이득은 합성·gate·parallel prior를 되풀이한 것이 아니라 사람 라벨 축에서 고유한 오류 보완이다.
- **지표**: 동일 definition에서 `{human, v0, CL-B, GBDT, raster, synthetic, metamorphic, silver(자격 시)}`의 pairwise disagreement, error correlation, unique-TP/FP, train-source×eval-source 행렬.
- **제안 합격선**: human-labeled val에서 raster unique-TP의 paired interval 하한>0이고, 그 이득이 gate pass를 학습 target으로 쓴 arm 없이 재현된다. silver 없는 arm이 primary다.
- **킬 조건**: raster 이득이 평행 이중선 prior와 완전히 같은 표본에만 나타남, synthetic 대각 성능만 높고 human 비대각 전이가 없음, 또는 gate 결과를 sample weight로 넣어야만 이득이 남음.
- **예산**: 기존 prediction을 재사용하는 로컬 분석 1일 제안.
- **시드 계획**: P5-03의 세 seed; shuffle-label 세 seed를 대조로 동일 집계.

### Cell P5-06 — metamorphic·sentinel 배터리

- **가설**: raster nomination을 거쳐도 inverse-mapped 최종 accepted handle 집합은 의미 보존 transform에 불변이고 퇴행 sentinel을 통과한다.
- **지표**: transform 전후 accepted-handle Jaccard, candidate-rank 변화, gate-clause 변화, 0벽 FP, 전벽 recall, scale arm 최저 일치율.
- **제안 합격선**: 강체·반사·이동·단위·scale의 의미 보존 fixture에서 inverse-mapped accepted-handle Jaccard=1.0, 0벽 sentinel FP=0, 전벽 sentinel recall=1.0. 후보 순위 변화는 허용하지만 최종 합격 집합 변화는 허용하지 않는다.
- **킬 조건**: scale FAIL을 threshold 조정으로 숨김, 0벽에서 하나라도 합격, 전벽을 빈 출력으로 통과, 또는 transform마다 gate 설정을 바꿔야 함.
- **예산**: 로컬 CPU/GPU 1일 제안.
- **시드 계획**: 고정 transform manifest를 세 checkpoint에 동일 적용.

### Cell P5-07 — 1.dwg real-axis 및 NC 제거 ablation

- **가설**: CL-A가 확정한 실도면 zero-pair 구간에서 raster가 CL-B 이후에도 새 gate-qualified 기존 핸들을 제안하며, 그 이득은 권리상 허용된 checkpoint로 재현 가능하다.
- **지표**: operational_yield@20, v0/CL-B 대비 delta, definition별 latency/peak memory, unmatched/CRS reject, NC checkpoint 제거 전후 delta.
- **제안 합격선**: v0 대비 절대 delta≥0.25, CL-B 대비 paired interval 하한>0, phantom=0. 제품 후보의 경우 허용 checkpoint도 같은 방향의 유의한 lift를 보여야 한다.
- **킬 조건**: CL-B 보강이 같은 handle을 전부 회수함, 이득이 NC checkpoint에서만 보이고 허용 checkpoint의 delta가 제안 equivalence band `[-0.05,+0.05]` 안에 머묾, 또는 모델 출력을 gate 없이 채택해야 이득이 생김.
- **예산**: 최대 412,775 선분 definition을 고려한 tile/R-tree 로컬 실행 1–2일 제안.
- **시드 계획**: 세 checkpoint의 봉인 ensemble 1회 추론; 실도면을 보고 seed를 선택하지 않는다.

실도면에는 사람 라벨이 없으므로 이 셀 합격만으로 semantic precision/recall을 주장하지 않는다. `RESEARCH_VIABLE`의 의미도 labeled 축의 P5-04/P5-08과 결합할 때만 성립한다.

### Cell P5-08 — 봉인 holdout/test 단발

- **가설**: val에서 고른 P5 방식이 FPCAD research-holdout과 CubiCasa test에 한 번의 봉인 실행으로 전이된다.
- **지표**: FPCAD wall IoU, CubiCasa per-handle P/R/F1와 Recall@20, v0/CL-B/frozen GBDT와의 paired delta, 모든 gate/reject count.
- **제안 합격선**: FPCAD wall IoU≥0.60; v0 대비 gate-qualified Recall@20 delta≥0.25; 같은 test에서 replay한 CL-B 대비 interval 하한>0; GBDT∪raster가 GBDT 단독보다 precision 비열화 없이 recall 하한>0; P5-01/P5-06 hard gate 유지.
- **킬 조건**: read-once 전에 hash가 달라짐, test를 두 번 열어 선택함, 어떤 hard gate도 실패, 또는 val lift가 test에서 재현되지 않음. test 실패 뒤 같은 test로 재튜닝하지 않고 방법을 kill/park한 뒤 새 세대로 넘긴다.
- **예산**: 체크포인트가 봉인된 뒤 로컬 단일 batch 평가 1일 제안.
- **시드 계획**: prereg된 세-checkpoint ensemble을 한 test runner invocation에서 평가. seed별 test 탐색 금지.

### Cell P5-09 — 제품 artifact 격리

- **가설**: 연구 결과와 독립적으로 product build가 NC/unknown 데이터 파생물을 완전히 거부하며, 허용 weight만으로 후보 이득을 재현할 수 있다.
- **지표**: product dependency closure의 금지 checksum 수, research import 수, reproducible build hash, 허용 checkpoint의 P5-04/P5-07 delta.
- **제안 합격선**: 금지 checksum=0, research import=0, 동일 입력 두 build hash 일치, 허용 checkpoint가 앞선 성능 조건을 만족.
- **킬/판정 조건**: NC weight·LoRA·distillation·cache 중 하나라도 제품 트리에 들어가면 제품 arm 즉시 FAIL. NC를 뺀 이득이 ≈0이면 P5는 연구 결과로만 보존하고 제품 제안은 죽인다.
- **예산**: 로컬 lineage scanner/clean-room build 1일 제안.
- **시드 계획**: 없음. byte-level artifact 검사와 두 번의 deterministic build.

### 6.2 최종 판정 논리

```text
if P5-00 or P5-01 is not PASS:
    status = BLOCKED
elif P5-02 fails or P5-03 misses IoU band:
    status = PARK
elif any of P5-04, P5-05, P5-06, P5-08 fails:
    status = KILL_COUNTER_THEORY
elif NC research arm passes but P5-09 does not:
    status = RESEARCH_VIABLE_PRODUCT_BLOCKED
elif P5-07 beats v0 but not CL-B:
    status = KILL_RASTER_MAINLINE_CLAIM
else:
    status = PRODUCT_CANDIDATE_REQUIRES_HUMAN_V2_GATE
```

어떤 상태에서도 VLM/raster mask가 곧 제품 SoT가 되지 않는다. 최종 채택은 route에 명시된 `V2_human_gate`의 Paul 승인 대상이다.

---

## 7. red team 티켓 응답

패널 본문에서 P5/CL-G에 직접 연결됐거나 이 설계가 의존하는 OPEN 티켓만 다룬다. 티켓 원문의 미제공 세부는 추정하지 않는다.

| 티켓 | 이 제안에 미치는 공격 | 응답·해소 기준 | 현재 입장 |
|---|---|---|---|
| T1 — 대리 독립성 | synthetic/external/metamorphic/silver가 같은 평행 prior를 공유할 수 있음 | P5-05의 동일-definition disagreement와 train-source×eval-source 행렬. human-labeled CubiCasa를 primary로 하고 silver는 제외 | **수용, 미해소**. 분석 실행 전 PASS 금지 |
| T2 — 생성기 부재/충실도 | 현재 벽 semantic synthetic truth가 release 심판이 될 수 없음 | CRS microfixture와 semantic synthetic pack을 분리. 후자는 CL-C가 fidelity gate를 통과하기 전 진단용 | **공격 lands 수용** |
| T3/T4 — E1 정렬 아티팩트·원시 근거 | zero-pair/divergent 표본 자체가 정렬 산물일 수 있음 | P5-02/P5-07 표본은 CL-A 재계산과 원시 조달 뒤 봉인. 표본 premise가 사라지면 real-axis 주장을 철회 | **간접 hard prerequisite** |
| T5 — FloorPlanCAD/CubiCasa 권리 | NC 라벨뿐 아니라 원 도면·파생 weight 권리 미해결 | P5-00 counsel, lineage 상속, P5-09 checksum deny. `UNKNOWN`은 차단 | **수용, 서면 전 BLOCKED** |
| T7 — 0벽/전벽 sentinel | violation-only metric이 빈 탐지기를 통과시킬 수 있음 | P5-06에서 0벽 FP=0과 전벽 recall=1.0을 별도 hard gate로 둠 | **설계상 해소, 실행 증거 대기** |
| T9/T21 — v0 baseline 선계측 | 새 방법이 움직이는 baseline을 이긴 척할 위험 | v1 config/executable/data hash와 CL-B 봉인본을 먼저 replay, 같은 handle universe/top-20/gate 사용 | **실행 전 필수** |
| T13 — DGX Ornith vision 지원 | text 중심 runtime을 vision 학습 자원으로 잘못 셀 수 있음 | 연결 회복 뒤 실제 image/dense-output capability probe. 부적합이면 generic CUDA만 사용; 로컬 경로는 독립 완결 | **현재 unreachable, 비임계 blocker** |
| T17 — truth-source 교차 | 한 truth에만 맞춘 성능을 일반화로 오인 | P5-05에서 FPCAD/CubiCasa/synthetic/metamorphic의 대각·비대각을 분리 | **수용** |
| T24 — pixel→handle exact harness | CRS 오차가 기하를 날조할 수 있음 | P5-01의 affine+ID buffer+nested INSERT strict round-trip. unmatched mask는 geometry 생성 금지 | **P5의 첫 기술 hard gate** |
| T31 — CL-B 이후 추가 회수 | “래스터 본선”이 CL-B가 이미 해결할 누락을 재포장할 수 있음 | P5-04/P5-07/P5-08 모두 CL-B를 같은 budget·gate로 직접 비교하고 paired 하한>0 요구 | **미달 시 본선 주장 kill** |
| T34 — 인용 status | load-bearing 인용이 실행된 실험처럼 쓰일 위험 | 본 문헌은 배경으로만 표시하고 모든 P5 cell을 `experiment_executed:false`로 시작. 서지·코드·라이선스 확인 전 구현 근거로 승격하지 않음 | **수용** |

추가로 panel의 silver 식별자 모순은 calibration 해석을 따른다. 즉 B1≥0.70과 B4 Pearson≥0.70이 모두 필요하다. 현재 제공 관측 Pearson 0.2911에서는 silver 학습 arm을 열 수 없다.

---

## 8. 인접 제안과의 관계 및 사망 조건

### 8.1 병합 가능 지점

| 인접 클러스터/제안 | 병합 지점 | 경계 |
|---|---|---|
| CL-A E1 법의학 감사 | real zero-pair/divergent 표본을 정화하고 정렬 아티팩트를 제거 | CL-A가 premise를 없애면 P5 real-axis 명분도 축소 |
| CL-B 결정론 v1 | 정규화, INSERT world transform, 단위 정박, 최종 vector gate와 가장 강한 baseline 제공 | P5가 CL-B 규칙을 자기 성능으로 세지 않음 |
| CL-C WSD-EVAL-v1 | semantic synthetic fidelity와 per-handle 평가 계약 | 현 B1 FAIL 팩은 release gate가 아님 |
| CL-D metamorphic | 동일 transform manifest, 0벽/전벽 sentinel, strict accepted-handle 비교 | candidate rank 변화와 final acceptance 변화를 구분 |
| CL-E truth-source 교차요인 | P5-05의 FPCAD×CubiCasa×synthetic×metamorphic 독립성 분석 | 서로 다른 proxy를 평균 하나로 합치지 않음 |
| CL-F 학습 사다리 | GBDT를 강한 벡터 학습 기준선으로 두고 raster union의 조건부 이득 측정 | GBDT가 충분하면 더 비싼 raster를 죽임 |
| CL-G raster/VLM 이중 트랙 | P5는 이 클러스터의 open segmenter 연구 arm | frontier silver는 별도 자격·예산·queue |
| CL-K anti-silver arm | gate-only/raster-human-label arm을 primary 통제로 유지 | silver distillation은 현재 비활성 |
| feyerabend P2 | 상대 두께·단위 정박을 `G_unit`에 공급 | raster가 scale 문제를 해결했다고 가정하지 않음 |
| feyerabend P6 | nested INSERT의 world 좌표와 handle 역참조를 공급 | transform 전개 실패 시 P5-01도 실패 |
| CL-J room/face-first | raster가 room region을 더 잘 잡을 경우 후속 후보 생성 대안 | 본 P5에서는 room mask를 wall truth로 대체하지 않음 |

### 8.2 P5의 고유 차별점

P5의 고유 주장은 “VLM을 믿자”가 아니다. **학습 모달리티와 판정 권위를 분리**해, 벡터 여섯 특징에 없는 래스터 문맥을 후보 recall에만 투입하는 것이다. 그래서 다음 세 결과를 동시에 요구한다.

1. FloorPlanCAD mask holdout에서 실제 분할을 배웠다.
2. 사람 라벨 CubiCasa에서 CL-B와 GBDT 이후에도 고유 wall handle을 찾았다.
3. 실도면에서는 새 geometry를 만들지 않고 기존 handle만 gate-qualified operational yield로 제시했다.

셋 중 하나라도 빠지면 “래스터 본선”이라는 표현은 과장이다.

### 8.3 이 제안이 죽어야 하는 조건

다음 중 하나면 정직하게 P5를 죽이거나 연구 기록으로만 보존한다.

1. world↔pixel↔original-handle round-trip을 strict하게 만들 수 없다.
2. CL-A 재감사 뒤 zero-pair/divergent 현상이 계측 아티팩트로 사라진다.
3. CL-B 정규화·INSERT·단위 정박 뒤 raster의 paired lift가 0 이하가 된다.
4. raster∪GBDT가 GBDT 단독에 고유 true positive를 더하지 못한다.
5. IoU≥0.60을 맞추더라도 handle 역투영·gate-qualified recall로 전이되지 않는다.
6. 이득이 FloorPlanCAD와 같은 proxy 안에서만 보이고 CubiCasa human-labeled 비대각 전이에서 사라진다.
7. dimension/door/window/boundary의 FP를 줄이지 못하거나 새로운 가구·문자 흡수 오류가 상쇄한다.
8. scale/단위/metamorphic 또는 0벽/전벽 sentinel을 엄격히 통과하지 못한다.
9. VLM/mask score를 최종 합격식에 넣어야만 성능이 난다. 이는 counter-theory 승리가 아니라 R23 kill 조건이다.
10. NC/unknown checkpoint를 제거하면 실측 gate 이득이 제안 equivalence band에서 ≈0이 된다.
11. counsel이 원 데이터·라벨·파생 weight 사용을 허용하지 않거나 product artifact 격리를 증명할 수 없다.
12. test 단발에서 val의 이득이 재현되지 않는다.
13. 같은 품질에서 로컬 latency·메모리·운영 복잡도가 GBDT/CL-B보다 정당화되지 않는다.
14. frontier silver를 섞지 않으면 성능이 나지 않거나, 약 두 판정자 가문을 다섯 독립표처럼 세야만 결론이 난다.

가장 싼 종료 순서는 `권리 → CRS → frozen 20-def → CL-B 비교 → 학습`이다. 비싼 fine-tuning을 먼저 돌리지 않는다. 이 순서에서 살아남아도 결과는 우선 `RESEARCH_VIABLE`일 뿐이며, NC-free 재학습·단발 test·artifact 격리·V2 human gate가 모두 끝나기 전에는 제품 배송으로 승격하지 않는다.

DOSSIER_COMPLETE: feyerabend_P5
