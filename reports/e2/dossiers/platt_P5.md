# E2 벽 의미 탐지기 방법론 심층 도시계획 — platt_P5

이 문서는 P5의 **실행 전 설계·프리레지스트레이션 초안**이다. 새 실험을 수행했거나 새 수치를 측정했다는 주장은 하지 않는다. 현재 확인된 실측치는 패킷의 2026-07-18 다이제스트에 있는 값만 사용한다. 아래의 임계값·시드·시간·탐색 격자는 모두 **제안값**이며, 시험 전 봉인할 운영 규칙이다. 논문명과 발표 연도는 웹 검색 없이 정리한 일반 지식 기반 서지이며 성능 수치의 근거로 사용하지 않는다. 확신이 낮은 서지는 `요검증`으로 표시한다.

P5의 결론부터 말하면, 이 레인은 하나의 모델 실험이 아니라 다음 두 트랙과 하나의 공통 병목으로 구성된다.

1. **5a 프런티어 VLM 트랙**: 이름과 메타데이터를 제거한 definition crop을 보고 벽 영역 polygon을 내는 비학습 배심원.
2. **5b 로컬 분할 트랙**: FloorPlanCAD 래스터·마스크로 학습하는 소형 semantic segmentation 배심원.
3. **공통 bridge**: raster mask/polygon을 원래 vector handle 집합으로 되돌리는 provenance-aware back-projection.

두 트랙 모두 진리원(source of truth)이 아니다. 합성 exact truth, 허가된 외부 사람 라벨, metamorphic relation이 심판이고, VLM/분할 모델은 고정된 앙상블에 **각각 최대 한 표**만 낸다. 공통 bridge를 oracle mask로 시험했을 때 handle F1이 0.4 미만이면 두 트랙을 동시에 죽인다. 반대로 특정 vision 모델의 end-to-end 실패는 그 모델 트랙만 죽인다. 이 구분이 없으면 분할 오류를 bridge 오류로 오인해 잘못된 공통 kill을 내릴 수 있다.

---

## 1. 이론적 근거·선행연구

### 1.1 문제를 두 트랙과 한 bridge로 분해해야 하는 이유

CAD 벽 의미 탐지는 벡터 기하만으로는 어려운 두 종류의 정보가 섞인 문제다.

- 선분 수준의 국소 기하: 평행성, 간격, 길이, junction, block transform.
- 래스터에서 생기는 중간 규모의 시각 문맥: poché, 닫힌 띠, 방 경계의 연속성, 문·창과의 배치, 끊긴 선을 하나의 벽 덩어리로 보는 gestalt.

현재 벡터 탐지기 v1은 CubiCasa5k val에서 F1 0.2358이고, 긴 평행 구조인 Direction/BoundaryPolygon/Door/Window/DimensionMark가 주된 false positive다. 여섯 특징의 HistGradientBoosting은 val F1 0.517까지 올라갔으나 recall 0.370이다. 따라서 P5가 가져와야 할 것은 “또 다른 평행선 탐지”가 아니라 다음 중 적어도 하나다.

- 픽셀 문맥으로 긴 비벽 구조를 배제해 GBDT의 남은 오류와 다른 오류 분포를 보인다.
- 벡터 정규화가 놓친 poché·끊긴 경계·복합 block을 시각적으로 회수한다.
- 이름을 물리적으로 받지 않는 배심원으로서 H3의 layer/block-name 관례 신호와 독립적인 반증을 제공한다.

이 가설의 인과 경로는 `vector geometry → neutral raster → wall probability/polygon → provenance bridge → handle vote`다. layer name, block name, 원본 파일명, 모델별 silver 문구는 이 경로에 들어갈 수 없다. bridge와 renderer가 이 절단을 실제로 보장해야 “name-blind”라는 말이 성립한다.

### 1.2 5b: semantic segmentation 계보

5b는 픽셀별 이진 분할 문제로 둔다. U-Net(Ronneberger 등, 2015)은 encoder-decoder와 skip connection으로 세부 경계를 복원하는 전형적인 소형 분할 계보이고, SegFormer(Xie 등, 2021)는 계층형 transformer encoder와 가벼운 decoder를 결합해 다중 스케일 문맥을 다룬다. P5의 1차 모델은 **SegFormer-B0급**으로 고정하고, U-Net급 모델은 구현·학습 파이프라인의 sanity baseline으로만 둔다. 둘을 무제한 비교해 test를 고르는 모델 경연으로 만들지 않는다.

FloorNet(Liu 등, 2018), CubiCasa5K/Kalervo 등 계열, DeepFloorplan 계열(`정확 서지 요검증`)은 floor-plan parsing에서 방·아이콘·벽을 래스터 문맥으로 함께 다루는 선행 계보다. 그러나 P5는 room polygon을 최종 산출하지 않고, **벽 픽셀을 vector handle vote로 되돌리는 bridge**를 필수 산출로 삼는다는 점이 다르다. FloorPlanCAD는 벽 bbox/segmask는 있으나 SVG가 없으므로 segmentation 학습에는 쓸 수 있어도 handle back-projection의 정답을 직접 제공하지 못한다. 이 공백은 synthetic provenance와 CubiCasa SEG-IR 축으로 메워야 한다.

### 1.3 5a: prompted visual grounding 계보

프런티어 VLM의 역할은 이미지에 대해 자연어 지시를 따르고 공간 영역을 polygon으로 반환하는 **selective juror**다. CLIP류의 image-text alignment, Grounding DINO류의 open-vocabulary grounding, Segment Anything(Kirillov 등, 2023)의 promptable mask, LISA류의 reasoning segmentation(`정확 서지 요검증`)이 인접 계보다. P5는 이 시스템들을 제품 진리원으로 채택하지 않는다. 고정 prompt와 고정 endpoint가 반환한 polygon을 strict schema로 검사하고, 모호하면 abstain시키며, synthetic exact truth와 metamorphic relation이 그 배심원의 발언권을 결정한다.

프런티어 VLM이 내부적으로 어떤 사전학습 데이터를 썼는지 완전히 알 수 없고 같은 도면 양식을 본 적이 있을 가능성도 배제할 수 없다. 따라서 5a의 장점은 “독립적인 인간 수준 진리”가 아니라, E2의 vector feature와 layer/block metadata를 직접 받지 않는 **다른 관측 양식의 한 표**라는 데만 둔다.

### 1.4 bridge: rasterization provenance와 역투영

일반적인 object-ID buffer는 한 픽셀에 하나의 객체만 저장하므로 겹친 선, block instance, hatch 경계에서 정보가 사라진다. P5는 보이는 grayscale render와 별도로 sparse provenance buffer `A[p,h]`를 만든다. `A[p,h]`는 픽셀 `p`에 source handle `h`가 기여한 coverage다. block 내부 leaf는 `(definition_id, insert_path, leaf_handle)`로 식별해 instance transform을 잃지 않는다. anti-aliasing이 켜진 보이는 이미지와 달리 provenance는 결정론적 coverage 누적으로 생성한다.

역투영은 polygon 꼭짓점을 단순히 world coordinate로 바꾸는 것만으로 끝나지 않는다. 벽 영역 내부와 벽을 구성하는 가는 경계선 사이에 공간적 간격이 있을 수 있기 때문이다. P5는 예측 mask의 고정 pixel halo와 각 handle의 rasterized support를 교차시킨다. 이 방식은 평행선·layer명 같은 벽 prior를 bridge에 다시 주입하지 않으면서, 영역 polygon과 경계 handle 사이의 작은 rasterization 차이를 흡수한다. 두꺼운 poché처럼 여러 handle이 같은 영역을 설명할 때는 하나를 억지로 고르지 않고 다중 후보와 ambiguity를 내며, ambiguity가 높으면 abstain한다.

### 1.5 배심 이론, 상관된 판정자, metamorphic testing

앙상블의 이득은 판정자 수 자체가 아니라 **오류의 비상관성**에서 온다. E1.5의 판정자 5기는 실제로 약 2개 어휘 가문으로 갈렸으므로 5표로 세지 않는다. P5의 primary 분석은 각 어휘 가문을 한 표로 접은 뒤 raster juror 한 표를 더한다. raw 5기 분석은 참고치만 낸다. Fleiss κ는 합의 구조의 변화는 보여주지만 truth accuracy를 보장하지 않으므로, κ 상승만으로 제품 정확도 향상을 주장하지 않는다. Dawid–Skene류의 잠재 truth 집계 역시 판정자 독립성 가정이 깨질 수 있어 exploratory 분석으로만 허용한다.

Metamorphic testing은 정답 라벨이 없는 real drawing에서도 강체변환, 반사, 단위표현, layer rename, geometry-preserving explode 같은 관계가 출력에 어떻게 보존돼야 하는지 정의한다. 단, “항상 빈 집합”도 불변성을 만족하므로 0-wall/all-wall sentinel과 synthetic recall floor를 함께 적용한다. P5에서 real divergent를 “해소”했다고 부르는 조건은 단순 다수결이 아니라 다음을 모두 만족하는 경우뿐이다.

- 두 E1.5 어휘 가문이 다르게 투표한 handle에 raster juror가 non-abstain 표를 낸다.
- raster 표를 더했을 때 고정된 family-level 투표 규칙으로 유일한 다수가 생긴다.
- 등록된 변환을 역매핑한 handle 집합이 metamorphic relation을 만족한다.
- 0-wall/all-wall sentinel과 crop-edge 검사를 통과한다.

### 1.6 이론이 틀렸음을 보여줄 관측

다음 관측은 P5의 핵심 인과 설명을 반박한다.

- oracle wall mask조차 provenance bridge에서 handle로 돌아오지 못한다.
- layer/block name을 제거했는데도 render payload나 API metadata에 이름이 남는다.
- raster와 vector의 오류가 같은 “긴 평행 구조”에 집중돼 배심 다양성이 생기지 않는다.
- renderer style만 바꾸면 handle vote가 크게 바뀌고 hidden style family에서 무너진다.
- κ만 오르고 synthetic/external truth의 정확도 또는 metamorphic consistency는 떨어진다.
- CL-B의 coverage-complete vector 방법이 같은 divergent를 더 싸고 안정적으로 모두 회수한다.

---

## 2. 알고리즘 정확 스펙

### 2.1 입력, 출력, 표준 단위

한 사례를 다음처럼 둔다.

- 입력 definition `D = (H, G, X, M)`: handle 집합 `H`, handle별 기하 `G_h`, block instance path/transform `X_h`, 표시 속성 `M_h`.
- 학습 시 픽셀 정답 `Y ∈ {0,1}^{W×H}`. synthetic/CubiCasa 평가 시 handle 정답 `y_h ∈ {0,1}`.
- 중립 render `I`, crop/world affine transform `T_D`, sparse provenance `A[p,h]`, crop-edge mask `E`.
- vision 출력 확률 mask `Q[p] ∈ [0,1]`. 5a polygon은 rasterize하여 `Q`로 바꾼다.
- 최종 연구 출력 `J_h ∈ {-1,0,+1}`: non-wall, abstain, wall. 연속 score `s_h`, ambiguity `a_h`, crop risk `e_h`, provenance를 함께 보존한다.

모든 좌표 변환은 다음 형태의 affine matrix를 manifest에 저장한다.

`[u, v, 1]^T = T_D [x, y, 1]^T`

`u,v`는 full render pixel 좌표이고, tile 좌표는 별도 translation matrix `T_tile`로 표현한다. polygon을 world로 되돌릴 때는 `(T_tile T_D)^{-1}`을 사용한다. 단, **handle 선택은 근사 world-intersection이 아니라 `A[p,h]`로 수행**한다. world polygon은 감사·시각화용 산출이다.

### 2.2 중립 renderer와 provenance buffer

렌더 입력에서 다음 정보는 제거한다.

- layer name, block name, 파일명, 경로, handle 문자열의 화면 표시.
- layer별 color mapping과 UI selection/highlight.
- TEXT, MTEXT, ATTRIB의 문자 glyph. 텍스트 entity의 bbox를 빈칸으로 남기고 내용은 보내지 않는다.
- E1.5 silver 설명, detector score, 기존 벽 예측 overlay.

기하 자체의 선폭, dash, hatch/poché는 “시각 정보”일 수 있으므로 style family에서 통제한다. primary neutral style은 색을 단색으로 만들고 renderer가 정한 pixel 선폭을 쓴다. appearance-preserving style은 robustness arm일 뿐 primary가 아니다.

```text
render_with_provenance(D, style_id, crop_spec):
    assert style_id in sealed_style_manifest
    D_world = expand_insert_transforms(D)
    bbox = robust_bbox(D_world, excluding_hidden_and_text_glyphs)
    T_D = fit_bbox_to_canvas(bbox, crop_spec.padding, preserve_aspect=True)
    I = blank_grayscale_canvas()
    A = sparse_coverage_map(pixel -> list[(canonical_handle, coverage)])

    for instance_path, leaf_handle, primitive in stable_geometric_order(D_world):
        primitive_px = transform(T_D, primitive)
        draw_visible(I, primitive_px, style_id)
        accumulate_coverage(A, primitive_px, key=(D.id, instance_path, leaf_handle))

    tiles = make_overlap_tiles(I, crop_spec.tile_size, crop_spec.overlap)
    assert round_trip_error(T_D, inverse(T_D)) <= sealed_pixel_tolerance
    return I, A, T_D, tiles, content_hash(I), metadata_leak_audit(I, request_payload)
```

겹친 primitive는 `A`에 모두 남긴다. visible render의 drawing order는 stable geometric key로 고정하되, 그 key나 handle 값이 API payload에 노출되지 않는다. 렌더 style은 synthetic train에서 다양화한 뒤 `style_manifest`의 hash를 프리레지스트리에 기록한다. hidden mutation style은 threshold 선택에 사용하지 않는다.

### 2.3 5a 프런티어 VLM의 고정 prompt와 schema

프런티어 endpoint는 착수 전 capability probe에서 image input과 polygon JSON 출력을 지원함을 확인해야 한다. endpoint, model revision, system prompt, decoding 설정, image hash를 봉인한다. temperature는 제안값 0이고, endpoint가 seed를 지원하면 단일 고정 seed를 쓴다. 유효 응답을 받은 뒤 “더 좋은 답”을 얻기 위한 재호출은 금지한다. transport failure는 응답 본문이 생성되지 않았음이 로그로 입증될 때만 같은 request hash로 한 번 재전송하고, 두 응답이 생기면 둘 다 시험에서 제외해 cherry-pick을 막는다.

고정 prompt의 의미 계약은 다음과 같다.

```text
ROLE: You are one fallible visual juror, not the source of truth.
INPUT: A metadata-free raster crop of CAD geometry.
TASK: Mark only regions that visually function as walls.
RULES:
  - Use pixels only. No layer names, block names, filenames, prior detector scores, or hidden metadata exist.
  - Return polygons in image pixel coordinates and a wall/non-wall/uncertain decision.
  - Include visible wall mass; do not label doors, windows, dimensions, arrows, or generic long parallel lines merely for being parallel.
  - If the crop boundary prevents a reliable decision, abstain.
OUTPUT: Strict JSON matching schema version e2.wall_juror.v1. No prose.
```

Schema:

```json
{
  "schema": "e2.wall_juror.v1",
  "image_sha256": "<echoed hash>",
  "global_decision": "wall_present|no_wall|uncertain",
  "regions": [
    {
      "polygon_px": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]],
      "decision": "wall|non_wall|uncertain",
      "confidence": 0.0,
      "reason_code": "continuous_boundary|poche|room_separator|ambiguous_thick_region|crop_cut|other"
    }
  ]
}
```

위 숫자는 실제 좌표 예시일 뿐 측정치가 아니다. polygon은 최소 유효 꼭짓점, self-intersection, canvas 범위, image hash를 검사한다. schema 불일치, hash 불일치, 자연어 부가 출력, 전역 결정과 region 모순은 `invalid/abstain`이다. 모델 self-confidence는 calibration truth로 취급하지 않고, 사전등록한 abstention rule의 보조 입력으로만 쓴다.

5a polygon `P_k`는 confidence를 곱한 binary raster로 합친다.

`Q_5a(p) = max_k 1[p ∈ P_k] · c_k`, 단 `decision_k = wall`인 region만 포함한다.

`uncertain` polygon은 positive로 바꾸지 않고 ambiguity audit에만 남긴다.

### 2.4 5b 소형 분할 모델

Primary는 SegFormer-B0급 binary head, sanity baseline은 U-Net급이다. 사전학습 checkpoint를 쓸 경우 checkpoint license와 hash가 counsel/firewall manifest에 있어야 한다. 허가되지 않으면 random initialization U-Net sanity run만 허용하고, 그 결과로 SegFormer를 대체했다고 주장하지 않는다.

입력은 grayscale을 3채널 복제하거나 학습 가능한 1→3 stem을 사용한다. 어느 쪽인지 train 전에 고정한다. 출력 logit `z_p`, 확률 `Q_5b(p)=sigmoid(z_p)`다. loss는 다음 제안 family에서 val로 하나를 선택한 뒤 봉인한다.

`L = λ_bce L_weighted-BCE + λ_dice (1 - Dice(Q,Y)) + λ_boundary L_boundary`

허용 탐색 공간은 다음으로 제한한다.

| 항목 | 시험 전 허용 제안 공간 | 선택 규칙 |
|---|---|---|
| 입력 tile | 512, 768, 1024 px | 16GB에서 OOM 없는 가장 큰 두 후보만 val 비교 |
| overlap | 64, 128 px | crop-edge recall과 처리량을 함께 보고 val에서 고정 |
| optimizer | AdamW | 다른 optimizer 추가 금지 |
| learning rate | `1e-5`, `3e-5`, `1e-4` | FPC val pixel IoU primary |
| weight decay | `1e-4`, `1e-2` | 위 learning-rate 격자 안에서만 선택 |
| loss weight | `(λ_bce,λ_dice)={(0.5,0.5),(0.3,0.7)}` | train/val만 사용 |
| boundary term | `λ_boundary={0,0.1}` | synthetic boundary val이 악화되면 0 |
| mask threshold | 0.4, 0.5, 0.6 | FPC val에서 고정, CubiCasa test에서 재선택 금지 |
| epoch cap | 제안값 40 | val early stop, patience 제안값 5 |
| seed | 1701, 1702, 1703 | 세 seed 모두 보고, best-seed만 보고 금지 |

AMP를 쓰고 per-device batch는 OOM probe로 정하되 effective batch는 gradient accumulation으로 manifest에 기록한다. augmentation은 geometry와 mask에 동일하게 적용한다. 허용 family는 직각 회전/반사, 제한적 translation, crop, line-width morphology, poché on/off simulation, blur, contrast, additive raster noise다. 각 범위는 synthetic/FPC train에서만 결정하고 시험 전에 동결한다. 임의 perspective warp처럼 CAD relation을 바꾸는 augmentation은 금지한다.

FloorPlanCAD split은 source drawing의 canonical ID를 hash한 **drawing-level** split로 만든다. 제안 비율은 train/val/internal-holdout = 80/10/10이고, 같은 원도면의 crop은 한 split에만 존재한다. 데이터 중복 hash를 먼저 검사하고, duplicate group은 한 drawing unit으로 묶는다.

### 2.5 공통 raster→handle bridge

`A[p,h]`의 handle support에 예측 mask의 pixel halo를 결합한다. halo 반경 `δ`는 synthetic dev에서 `{2,4,8,16}` px 중 하나만 고르고 봉인한다.

`Q^δ(p) = max_{||r-p||∞≤δ} Q(r)`

`s_h = (Σ_p A[p,h] Q^δ(p)) / (Σ_p A[p,h] + ε)`

예측 connected component `C`에 대해 후보 handle score를 정규화한 분포 `π_{h|C}`를 만들고 entropy 기반 ambiguity를 둔다.

`a_C = -Σ_h π_{h|C} log π_{h|C} / log(max(2, |H_C|))`

handle이 속한 component들의 coverage-weighted ambiguity를 `a_h`로 둔다. 겹친 tile에서 같은 handle이 일치하지 않거나 handle support가 crop boundary에 닿고 이웃 tile 확인이 없으면 `e_h=1`이다.

제안된 tri-state rule은 다음과 같다.

```text
backproject(Q, A, sealed_bridge_params):
    Q_halo = max_pool(Q, radius=delta)
    components = connected_components(Q >= tau_mask)
    for h in all_rendered_handles:
        s[h] = coverage_mean(Q_halo, A[:, h])
        a[h] = component_candidate_entropy(h, components, A)
        e[h] = crop_edge_disagreement(h)

        if e[h] or a[h] > tau_ambiguity:
            vote[h] = 0                # abstain
        elif s[h] >= tau_positive:
            vote[h] = +1
        elif s[h] <= tau_negative:
            vote[h] = -1
        else:
            vote[h] = 0

    return vote, s, a, e, world_polygons, provenance_refs
```

허용 bridge threshold 격자는 `tau_positive ∈ {0.6,0.7,0.8}`, `tau_negative ∈ {0.2,0.3}`, `tau_ambiguity ∈ {0.25,0.5}`이며 항상 `tau_negative < tau_positive`를 만족해야 한다. synthetic dev에서 micro handle F1을 primary로 선택하되, macro-per-drawing F1과 sentinel 실패를 제약으로 둔다. test에서 threshold를 다시 맞추지 않는다.

두꺼운 poché로 여러 handle이 같은 mask를 설명하면 candidate set 전체를 결과에 보존한다. 단일 handle로 강제 축약하지 않는다. 평가에서는 exact wall-member handle truth와 비교하고, 제품 경로에서는 이 결과를 쓰지 않는다.

### 2.6 bridge와 vision을 분리하는 authoritative gate

공통 bridge kill metric은 **vision prediction이 아닌 synthetic oracle wall mask**를 `Q`로 넣어 측정한다.

- `F1_bridge_oracle < 0.4`: bridge 병목이므로 5a와 5b 동시 kill.
- `0.4 ≤ F1_bridge_oracle < 0.6`: 두 트랙 모두 발언권 없음. 한 번의 bounded bridge 수정 후 새 prereg로 재시험할 수 있으나 같은 결과를 PASS로 해석하지 않는다.
- `F1_bridge_oracle ≥ 0.6`: bridge 최소 발언권 통과. 이는 vision 품질 통과가 아니다.

그 뒤 5b end-to-end `Q_5b`의 handle F1과 5a `Q_5a`의 handle F1을 별도로 잰다. oracle bridge가 통과했는데 5b end-to-end가 실패하면 5b만 죽는다. 이 원인 분리는 모든 report에 `bridge_oracle`, `vision_mask`, `end_to_end` 세 행으로 강제한다.

### 2.7 metamorphic 비교와 handle 정규화

변환 `g`가 handle ID를 보존하면 다음 strict relation을 쓴다.

`M_strict(g,D) = 1[g^{-1}(Ĥ(gD)) = Ĥ(D)]`

explode처럼 raw handle이 바뀌면 `(entity type, quantized world geometry, instance lineage)`로 canonical geometry key를 만들고 그 집합을 비교한다. 보조 지표는 Jaccard지만 “metamorphic-정합 해소”의 primary 판정은 strict set equality다. scale/unit 변환에서는 pixel normalization과 world inverse가 함께 적용돼야 하며, layer rename은 render image hash 자체가 같아야 한다. image hash가 달라지면 모델이 아니라 renderer의 name-blind 계약 실패다.

0-wall sentinel에는 empty handle set, all-wall sentinel에는 full wall-member set을 넣는다. empty predictor가 불변성만으로 살아남지 못하도록 synthetic recall floor를 동시에 확인한다.

### 2.8 배심 편입 규칙과 가치 측정

5a가 E1.5 계열에 들어가려면 패널의 모순 원장을 수정한 정확한 gate, 즉 **B1 ≥ 0.70 그리고 B4 Pearson ≥ 0.70**을 E1.5 silver 자격 조건으로 적용한다. 어느 하나라도 미달이면 VLM 판정은 연구용 관찰로 남고 silver 배심 편입은 금지한다. VLM이 이 gate의 평가자 자신이 되면 순환이므로 별도 sealed evidence를 사용한다.

투표는 per-handle tri-state다.

1. fable+sol 계열을 한 family vote로 접는다.
2. opus+sonnet+grok 계열을 한 family vote로 접는다.
3. 살아남은 raster track은 최대 한 vote를 더한다. 5a와 5b를 동시에 넣는 확장 분석은 두 raster 오류 상관을 먼저 보고 secondary로만 허용한다.
4. family 내부 tie/불일치는 abstain이다.
5. deterministic vector 결과는 기준선·candidate universe·안전 gate이지 raster가 덮어쓸 진리표가 아니다.

Primary 배심 가치 지표는 다음 둘이다.

- `resolution_rate = metamorphic-consistent unique-majority resolutions / 20 divergent definitions`.
- `Δκ = κ_family+raster - κ_family`, prevalence를 보존한 permutation null과 함께 보고.

생존 band는 패킷 초안을 그대로 operationalize한다. divergent-20의 30% 이상, 즉 최소 6개 definition을 위 strict 조건으로 해소하거나, `Δκ > 0`이고 봉인한 one-sided permutation test를 통과하면 juror 생존이다. 둘 다 미달이면 tie-breaker/diagnostic으로 demote한다. κ 상승이 truth accuracy 향상을 뜻한다는 주장은 금지한다.

---

## 3. 벽 과업 적응 설계

### 3.1 세 데이터 축의 역할을 섞지 않는다

| 축 | P5 입력 | 허용 truth | 역할 | 금지 |
|---|---|---|---|---|
| 합성 wall IR | 합성 기하의 neutral render + exact provenance | generator의 `wall_member(h)`와 exact pixel mask | bridge oracle gate, prompt 개발, style robustness, sentinel | PR-1/CL-C fidelity 통과 전 “실전 유효” 주장 |
| FloorPlanCAD 5,308장 | 원 래스터 + 벽 segmask | 제공 mask, counsel 허용 범위 | 5b pixel segmentation 학습/내부 val | SVG/handle truth가 있다고 가정, 제품 weight 반입 |
| CubiCasa5k SEG-IR | 모든 element를 중립 렌더한 이미지 + provenance | Wall 클래스 edge handle, 제공 raster mask | 외부 transfer val 및 test 단발 | P5 primary 모델을 CubiCasa label로 재학습해 독립 평가 훼손 |
| 1.dwg staged DXF | CL-A가 확정한 definition crop 20개 | metamorphic relation, family disagreement, P0 법의학 | 5a cheapest probe와 H4/H3 배심 가치 | 사람이 확인한 truth처럼 보고, 정렬 artifact 미해소 상태에서 표본 고정 |

합성축은 현재 준비 완료 자산으로 취급하지 않는다. 패널은 `synthetic_truth.py`에 벽 코드가 없다고 명시했다. 따라서 PR-1 생성기와 CL-C WSD-EVAL-v1이 실제로 만들어지고 fidelity gate를 통과하기 전까지 P5의 bridge PASS는 **BLOCKED**다. 최소 toy geometry로 unit test를 할 수는 있지만 그것을 synthetic gate 결과로 승격하지 않는다.

기존 S/F/M 합성팩 자체도 B1 fidelity가 KS 0.5792, TV 0.265로 FAIL이다. 실도면에는 SPLINE 3,973, ARC 2,198, HATCH 264가 섞여 있지만 기존 합성팩은 LINE/LWPOLYLINE/INSERT 세 종류뿐이다. P5는 선폭·노이즈 augmentation으로 이 기하 누락을 해결했다고 주장하지 않는다. PR-1/CL-C가 divergent 현상의 primitive·block·비평행 조각을 재현하고 fidelity gate를 닫은 뒤에만 hidden synthetic 결과에 의미를 부여한다.

FloorPlanCAD는 raster-only이므로 5b의 pixel IoU를 가르치고 재는 축이다. handle F1은 이 데이터만으로 닫히지 않는다. CubiCasa는 5,000도면 전체가 SEG-IR로 변환됐고 train/val/test는 4,200/400/400으로 고정돼 있다. P5 primary 5b는 FloorPlanCAD에서 학습하고 CubiCasa val로 domain transfer와 bridge를 개발 확인한 뒤, 모든 gate가 잠겼을 때만 CubiCasa test 400을 한 번 연다.

### 3.2 CubiCasa SEG-IR 접속

`cubicasa_ir`에서 element geometry를 읽되 Wall label은 renderer 입력에서 제거한다. 모든 class를 동일한 중립 style로 렌더하고, provenance key에는 원 element ID만 남긴다. Wall 클래스 edge는 평가 시에만 `y_h=1`로 join한다. renderer가 label에 따라 draw order, color, width를 바꾸지 않는지 image hash 대조로 검사한다.

CubiCasa 좌표는 px이고 도면별 물리 축척이 알려져 있지 않으며 벽 두께 px p50은 22다. 기존 탐지기는 2–15 mm/px 전 구간에서 무감했고 scale arm도 0.7624로 FAIL했으므로, P5는 px를 mm로 추정해 절대 벽두께 prior를 되살리지 않는다. 입력은 pixel tile과 multi-scale augmentation으로 다루고, world/unit 변환은 bridge affine audit와 metamorphic relation에서만 사용한다.

현재 val에서 vector v1 F1은 0.2358, HistGradientBoosting F1은 0.517이다. P5는 다음 세 비교를 같은 handle universe에서 낸다.

- locked GBDT 단독.
- raster juror 단독.
- locked GBDT + raster juror의 고정 결합.

P5의 성공은 raster 단독 F1만 높다는 데 있지 않다. GBDT가 정밀도 0.860·재현율 0.370인 상태이므로, raster가 놓친 positive를 보완하는지, 또는 Direction/BoundaryPolygon/Door/Window/DimensionMark false positive를 줄이는지 class별 error overlap으로 보여야 한다. 기존 수치는 val 측정치이고, test 결과를 암시하지 않는다.

### 3.3 FloorPlanCAD 접속

FloorPlanCAD loader는 원 image, mask, source drawing ID, license lineage만 반환한다. bbox는 crop sampler에 쓸 수 있지만 bbox 자체를 별도 input channel로 넣지 않는다. 그러면 정답 위치를 입력으로 주는 누출이 된다. mask와 bbox가 서로 모순되는 샘플은 자동 수정하지 않고 quarantine 목록에 둔다.

학습은 다음 순서다.

1. counsel 승인과 dataset manifest hash 확인.
2. drawing-level duplicate group 및 split 생성.
3. U-Net sanity run으로 loader/loss/mask alignment 확인.
4. SegFormer-B0급 primary의 제한 격자 탐색.
5. 세 seed 재학습, val 결과 전체 보고.
6. chosen config와 internal holdout 봉인.

FPC internal holdout은 개발 중 열지 않는다. 다만 P5의 외부 일반화 주장은 CubiCasa test 단발이 담당하고, FPC holdout은 학습 파이프라인 자체의 in-domain 확인으로 구분한다.

### 3.4 1.dwg와 divergent-20 접속

1.dwg에는 384개 definition이 있고, 기존 P0/패널의 divergent 정렬이 artifact일 가능성이 열려 있다. P5는 기존 top-20을 그대로 받아 쓰지 않는다. CL-A가 `_score_divergence` 정렬 키를 재계산하고, 인용 handle 실재성·entity histogram·INSERT depth·bbox 단위를 확인한 뒤 sealed `divergent20_manifest`를 내야 한다. definition별 render는 router의 `visual_report/render` 경로를 재사용하되, 위 중립화 wrapper와 provenance buffer를 추가한다.

5a cheapest probe는 정확히 20개 primary image, endpoint당 1회 유효 응답으로 제한한다. 이 1차 probe는 “이름 없이 벽을 보는가”와 실제 비용/invalid rate를 보는 screen이지 최종 metamorphic PASS가 아니다. provisional resolution이 생기고 API envelope가 남은 경우에만 등록된 변형 image를 추가 호출해 H4 확인 셀로 간다.

5b는 API 비용이 없으므로 같은 divergent-20과 모든 등록 변형을 로컬에서 실행한다. 하지만 real truth가 없으므로 그 결과를 accuracy로 부르지 않고 family disagreement resolution과 invariance로만 해석한다.

### 3.5 H4와 H3를 동시에 판별하는 설계

H4 질문은 “vector가 못 푸는 divergent를 raster가 relation-preserving 방식으로 푸는가”다. 이를 위해 raster가 기존 vector 결과와 단순히 같아지는 비율이 아니라 다음을 본다.

- vector 두 family가 갈리는 handle에서 raster가 어느 쪽을 택하는가.
- synthetic/external truth가 있는 동일 유형에서는 그 선택이 맞는가.
- real drawing 변형 후에도 같은 canonical handle 선택을 유지하는가.
- 빈 출력·전부 출력으로 relation을 속이지 않는가.

H3 교차검증은 name-ablation을 renderer 수준에서 물리적으로 보장한다. layer rename 전후 중립 render hash가 달라지면 H3 결과를 내지 않는다. raster가 layer-name-heavy vector/silver 판정과 일치한다면 시각적 관례가 실제 기하와 함께 있었을 가능성이 있고, 불일치한다면 이름 prior가 지배했을 가능성이 있다. 어느 경우도 raster를 truth로 승격하지 않고 “이름을 못 본 관측축”으로만 해석한다.

기존 실도면 측정에서 detector의 full-vs-name-blind 출력은 1.0으로 같았고 detector↔AI silver Pearson은 0.2911이었다. 따라서 P5의 H3 가치는 현재 detector에 이미 없는 layer-name 신호를 또 제거하는 데 있지 않다. 이름을 사용할 수 있는 E1.5/silver 가문과 이름을 물리적으로 못 받는 raster 표의 disagreement를 같은 handle에서 비교하는 데 있다.

### 3.6 누출·도메인 갭 방지

- split은 crop이 아니라 source drawing 단위다.
- renderer style seed는 source drawing hash에서 결정하되 split 이후 생성하고, hidden style family는 threshold 선택에서 숨긴다.
- FPC bbox는 sampler용이며 input feature로 금지한다.
- CubiCasa Wall label은 render가 끝난 뒤 평가 join에만 사용한다.
- VLM prompt는 synthetic dev에서만 다듬고 divergent-20을 본 뒤 문구를 바꾸지 않는다.
- model endpoint나 revision이 바뀌면 같은 method의 retry가 아니라 새 prereg cell이다.
- 원본 layer/block/file 문자열이 request JSON, image metadata, filename에 없는지 byte-level audit한다.
- crop overlap을 사용하고 경계 handle은 이웃 tile 동의가 없으면 abstain한다.
- synthetic style은 선폭, poché, noise를 다양화한 뒤 동결하며, 너무 깨끗한 style 하나로만 PASS하지 않는다.
- proxy 네 종류의 같은 prior 공유 가능성을 error-overlap과 same-definition disagreement로 따로 측정한다.
- 기존 B4 scale 팔이 0.7624이고 센티널 조문상 strict FAIL이므로, P5는 rigid relation 일부만 통과한 것을 “metamorphic PASS”로 축약하지 않는다.

---

## 4. 데이터·컴퓨트 요구

### 4.1 착수 전 필수 자산과 권한

| 자산/권한 | 현재 패킷 상태 | P5에 필요한 확인 | 실패 시 |
|---|---|---|---|
| PR-1/CL-C 벽 합성 생성기 | 벽 코드 부재, fidelity 미통과 | exact pixel mask, `wall_member(h)`, provenance, hidden mutation family | bridge gate BLOCKED |
| FloorPlanCAD 5,308장 | 로컬 실존, 권리 미해결 | counsel 서면, source/label/weight 사용 범위 | 5b 학습 kill 또는 보류 |
| CubiCasa5k SEG-IR | 5,000 변환, test 무접촉 | counsel 서면, split hash, label/render 분리 | 외부 transfer 주장 금지 |
| RTX 5070 Ti 16GB / RAM 64GB | 사용 가능 | driver·framework smoke test, OOM profile | tile 축소 또는 U-Net sanity만 |
| DGX Spark | unreachable, 승인됨 | endpoint reachability와 Ornith-35B vision capability | primary에는 영향 없음; 대형 확장 금지 |
| 프런티어 VLM API | 유일 결재 gate, 미승인 | 데이터 반출·비용 envelope·endpoint 승인 | 5a BLOCKED, 실패로 위장 금지 |
| 로컬 qwen2.5-VL-3B floorplan SFT/GRPO | 로컬 실존 | base/finetune 데이터 계보, license, image·polygon schema capability | 5a frontier 대체로 간주하지 않음 |
| router visual_report/render | 재사용 대상 | neutral style hook, affine/provenance export | bridge 구현 선행 필요 |

### 4.2 로컬 실행 계획

렌더와 bridge는 CPU primary다. RAM 64GB에서 전체 drawing의 dense `pixels × handles` 행렬을 만들지 않고, tile별 sparse COO/CSR coverage를 디스크에 순차 기록한다. definition 하나가 최대 412,775 선분까지 갈 수 있다는 실측이 있으므로 다음 상한을 prereg manifest에 둔다.

- tile별 primitive spatial index 사용.
- provenance nonzero 수와 render time을 기록.
- 메모리 상한을 넘으면 resolution을 몰래 줄이지 않고 `resource_abstain`으로 표시.
- 같은 definition을 더 작은 crop으로 분할할 때 overlap과 inverse transform을 보존.

5b는 5070 Ti 16GB에서 small backbone, AMP, gradient accumulation으로 실행한다. primary 개발은 로컬에서 끝나야 하며 DGX availability를 전제로 삼지 않는다. U-Net sanity와 단일 SegFormer-B0급 search를 동시에 무한 확장하지 않고 제한 격자와 세 seed만 허용한다.

제안 시간 예산은 다음과 같다. 이는 측정치가 아니라 실행 계획이다.

- renderer/provenance/bridge 구현 및 unit fixture: 2–3 개발일.
- synthetic oracle gate와 style robustness: 1 개발일.
- FPC loader/firewall/sanity: 1 개발일.
- 5b 제한 탐색과 세 seed: 2–3 GPU일.
- CubiCasa val bridge/오류 분석: 1 개발일.
- 5a divergent-20 cheapest probe: 1일, 유효 API 응답 20개.
- 배심·metamorphic·xlsx 정리: 1–2 개발일.

### 4.3 DGX와 대형 모델 계획

DGX는 P5의 critical path가 아니다. 착수 전 `capability` 문서로 Ornith-35B가 image input을 실제 지원하는지 확인한다. 지원하지 않으면 텍스트 판정자로만 남기고 5a를 외부 프런티어 API 전용으로 둔다. 지원하더라도 기존 텍스트 점유와 모델 revision을 고려해 별도 실험 ID를 부여하며, 프런티어 VLM의 값싼 screen을 대체했다고 보지 않는다.

로컬 qwen2.5-VL-3B floorplan SFT/GRPO 모델도 primary 5a와 구분한다. 계보와 license가 허용되면 API 비용 없이 request/schema/bridge plumbing을 확인하는 **secondary smoke comparator**로는 쓸 수 있다. 그러나 floorplan 특화 학습 데이터가 P5 truth proxy와 겹칠 수 있고 “frontier juror”라는 5a 질문에도 답하지 않으므로, 그 결과로 V4를 PASS시키거나 외부 API 결과를 대체하지 않는다. Zenodo10K, Text2CAD, ArchCAD, pseudo-floor-plan-12k는 이 패킷에 label·권리·vector provenance 계약이 제시되지 않았으므로 primary cell에 추가하지 않는다.

대형 segmentation backbone은 다음을 모두 만족한 뒤에만 DGX 야간 후보가 된다.

- 5b pixel IoU gate 통과.
- oracle bridge와 end-to-end handle gate 통과.
- small backbone이 H4 또는 배심 complementarity에서 생존.
- counsel이 weight 산출과 compute 이동을 허용.

그 전에는 대형 backbone으로 scale을 올리는 것이 bridge 병목이나 proxy dependence를 숨길 수 있으므로 금지한다.

### 4.4 API 비용·반출 통제

owner가 통화 단위, 총액, endpoint당 단가, 최대 image 수를 적은 `B_API` envelope를 호출 전에 서명해야 한다. P5 문서가 임의 금액을 정하지 않는다.

- 예상 20개 primary 호출 비용이 `B_API`를 넘으면 5a 비용 kill.
- 20개 screen 뒤 metamorphic confirmation 예상비가 잔여 envelope를 넘으면 5a는 screen 결과만 기록하고 juror 생존 주장을 금지한다.
- crop에는 원본 경로, 고객명, 텍스트 glyph, layer/block name, handle ID를 넣지 않는다.
- API provider의 retention/training policy가 승인되지 않으면 업로드 금지.
- request/response hash, latency, billed units를 기록하되 민감 payload는 승인된 로컬 evidence store에만 둔다.

### 4.5 NC 방화벽

FloorPlanCAD/CubiCasa의 NC 및 원도면 권리가 미해결이므로 counsel 서면이 첫 gate다. 허용된 연구 arm은 다음 기술적 방화벽을 갖춘다.

1. dataset root는 read-only mount, manifest에 license/source hash 기록.
2. training run에 `RESEARCH_ONLY_NC=true`, dataset IDs, code hash, base checkpoint license를 기록.
3. weight filename과 metadata에 `NC_RESEARCH_INSTRUMENT_DO_NOT_SHIP` 표식.
4. product package/build path에서 이 weight와 loader import를 CI deny-list로 차단.
5. API나 DGX로 원본을 이동하려면 별도 반출 승인.
6. 결과가 이겨도 제품 반입은 하지 않고, clean licensed data를 새로 승인받아 **초기화부터 재훈련**한다.
7. clean retraining은 별도 proposal·budget·test이며 NC weight의 distillation, pseudo-label, feature cache를 재사용하지 않는다.

Counsel이 “평가만 허용, 학습 금지”라고 판단하면 5b는 죽고 5a/bridge의 synthetic arm만 남는다. “둘 다 금지”면 외부셋 결과를 만들지 않는다. 권한 부재는 모델 실패가 아니라 명시적 BLOCKED다.

---

## 5. 구현 계획

### 5.1 제안 모듈 골격

아래는 후속 구현의 파일 골격이며, 이 패킷 실행에서 실제로 생성하는 파일 목록이 아니다. 현재 산출 계약은 본 dossier 한 파일뿐이다.

```text
e2_vision/
  render_bridge.py          # visual_report/render adapter, T_D, sparse A[p,h]
  render_styles.py          # sealed neutral/style families and hash
  neutralize_metadata.py    # text/name/color stripping + byte audit
  tiler.py                  # overlap tile and crop-edge reconciliation
  vlm_juror.py              # fixed prompt, request envelope, strict schema
  fpc_dataset.py            # drawing-level split, mask/bbox separation
  seg_model.py              # SegFormer-B0 primary, U-Net sanity baseline
  seg_train.py              # limited grid, seed runner, checkpoint lineage
  backproject.py            # Q→tri-state handles, ambiguity, world polygons
  metamorphic_vision.py     # transform/canonical-handle relation checks
  jury_value.py             # family collapse, resolution rate, κ/permutation
  nc_firewall.py            # research-only manifest and product deny checks
  eval_vision.py            # synthetic/FPC/CubiCasa/real cell orchestrator
tests/
  test_affine_roundtrip.py
  test_insert_provenance.py
  test_polygon_schema.py
  test_bridge_oracle.py
  test_empty_all_wall_sentinels.py
  test_metadata_blind_render.py
  test_crop_overlap.py
```

### 5.2 기존 도구 접속점

- `visual_report/render`: 중립 raster 생성은 재사용하되 `T_D`, stable crop spec, provenance hook을 추가한다. 기존 render가 metadata를 burn-in하면 P5 wrapper에서 차단한다.
- `evidence_grid`: cell별 hypothesis, prereg band, input hash, seed, metric, verdict, failure reason을 행으로 적재한다.
- `fast_score`: handle score/threshold baseline과 같은 universe를 공유하고, P5 vote를 별도 channel로 넣는다. 기존 detector score를 vision image에 overlay하지 않는다.
- `cubicasa_ir`: element geometry와 source split을 읽고 neutral render/provenance로 변환한다. Wall label join은 평가 단계까지 지연한다.
- `cubicasa_ml`: locked GBDT prediction과 P5 raster prediction의 per-handle join, error category, paired comparison을 담당한다.

Interface는 다음처럼 최소화한다.

```python
RenderBundle = {
  "image_path": str,
  "image_sha256": str,
  "affine_world_to_px": list[list[float]],
  "provenance_path": str,
  "canonical_handle_index": str,
  "style_manifest_sha256": str,
  "metadata_audit": "pass|fail"
}

JurorRecord = {
  "def_id": str,
  "track": "5a|5b",
  "model_revision": str,
  "image_sha256": str,
  "handle_scores": list,
  "handle_votes": list,
  "abstain_reasons": list,
  "provenance_refs": list
}
```

### 5.3 구현 순서와 stop rule

1. **Preflight**: counsel, API, model/image capability, PR-1/CL-C, CL-A divergent manifest를 확인한다.
2. **Renderer contract**: metadata neutralization, affine round-trip, insert expansion, sparse provenance unit test.
3. **Bridge oracle**: synthetic oracle mask로만 gate. 미통과 시 여기서 두 트랙 종료.
4. **5b local**: FPC sanity→SegFormer limited grid→synthetic/CubiCasa val bridge.
5. **5a screen**: 승인된 endpoint에 sealed divergent-20 image를 한 번씩 호출.
6. **Metamorphic/jury**: 살아남은 track만 confirmation과 family-level vote에 편입.
7. **Test once**: prereg와 xlsx schema를 봉인한 뒤 CubiCasa test를 한 번 연다.

앞 단계가 BLOCKED/FAIL이면 뒤 단계를 실행해 expensive result로 선결 gate를 덮지 않는다.

### 5.4 필수 unit/integration test

- affine world→tile→world round-trip이 봉인 tolerance 안에 있는가.
- nested INSERT와 reflection/non-uniform transform에서 instance path가 충돌하지 않는가.
- 겹친 handle이 sparse provenance에 모두 남는가.
- polygon clip/self-intersection/schema error가 abstain으로 가는가.
- tile 경계 handle이 이웃 tile 합의 없이 positive가 되지 않는가.
- layer/block rename 전후 neutral image hash가 동일한가.
- TEXT/MTEXT/ATTRIB 문자열이 image metadata와 API payload에 없는가.
- empty/all-wall sentinel을 각각 정확히 처리하는가.
- oracle mask에 line-width/poché/noise style을 바꿔도 bridge가 relation을 보존하는가.
- 5a response retry가 cherry-pick을 만들지 않는가.
- test split을 train/val code path에서 열 수 없는가.
- NC weight를 product import path가 거부하는가.

### 5.5 증거 산출 계약

후속 run은 최소한 다음 evidence를 남겨야 한다.

- prereg JSON: split hashes, style hash, thresholds, seeds, endpoint revision, cost envelope ID.
- render manifest: image hash, affine, provenance hash, metadata audit.
- raw prediction JSONL: 재가공 전 5a/5b 출력과 abstain.
- bridge audit: oracle/vision/end-to-end를 분리한 metric 표.
- mandatory xlsx: cell, drawing, handle, truth source, prediction, transform, error category, cost, failure reason.
- jury report: raw-rater와 family-collapsed 결과를 분리한 κ, resolution, permutation 결과.
- NC lineage: dataset/checkpoint/weight와 제품 차단 증거.
- 실패 report: `PASS/FAIL/BLOCKED/DEMOTED` 중 하나와 정확한 stop rule.

`evidence_grid`의 PASS는 위 파일이 실제 존재하고 hash가 맞을 때만 허용한다. API 미승인, counsel 미결, synthetic generator 부재를 PASS나 모델 성능 FAIL로 바꾸지 않는다.

### 5.6 예상 개발 규모와 유지보수 경계

제안 규모는 핵심 Python 모듈 약 8–12개, unit/integration test 약 10개 내외, 8–12 개발일이다. 이는 계획 추정치이며 실측이 아니다. 가장 위험한 코드는 model head가 아니라 renderer provenance, nested INSERT canonicalization, crop overlap merge다. 따라서 model 종류를 늘리기보다 bridge test에 개발 시간을 우선 배정한다.

---

## 6. 실험 셀 정의

### 6.1 공통 프리레지스트레이션 규칙

- val은 개발·threshold 선택에 허용한다. test는 방법당 한 번만 연다.
- split, renderer style, prompt, model revision, seed, bridge threshold, metric code hash를 시험 전에 봉인한다.
- 셔플 대조군과 0-wall/all-wall sentinel은 의무다.
- 세 seed 결과는 평균·분산·각 seed를 모두 보이고 best seed만 선택하지 않는다.
- 5a는 유효 응답 한 번이 한 trial이다. stochastic repeat 평균으로 신뢰도를 꾸미지 않는다.
- primary metric과 kill condition을 바꾼 재실행은 같은 셀의 재시도가 아니라 새 version이다.
- 모든 셀은 mandatory xlsx에 실패 사유까지 쓴다.

### 6.2 Gate G0 — 권한·자산·capability preflight (과학 셀 아님)

- **가설**: 없음. 실험 자격 확인이다.
- **필수 확인**: PR-1/CL-C synthetic wall pack, counsel 서면, API 승인/retention/cost envelope, CL-A sealed divergent-20, endpoint image+polygon capability, Ornith vision 지원 여부.
- **통과선**: 각 후속 셀이 요구하는 항목이 문서와 hash로 존재.
- **킬/정지**: counsel 거부는 해당 외부 데이터 arm kill; API 미승인은 5a BLOCKED; synthetic pack 부재는 bridge 이후 전 셀 BLOCKED; Ornith vision 미지원은 DGX 확장만 kill.
- **예산**: 제안 0.5 개발일, API 유료 호출 없음.
- **시드**: 해당 없음.

### 6.3 Cell V1 — BRIDGE-ORACLE: vision 독립 bridge gate

- **가설**: exact wall mask와 exact provenance가 주어지면 raster wall region을 wall-member handle로 되돌릴 수 있다.
- **데이터**: CL-C synthetic train/dev/hidden-mutation, 0-wall/all-wall sentinel, nested INSERT/poché/crop-cut fixture.
- **조작**: style family, halo `δ`, positive/negative/ambiguity threshold. 선택은 synthetic dev만 사용하고 hidden mutation은 마지막에 한 번 실행.
- **primary 지표**: oracle-mask micro handle F1. 보조는 precision, recall, macro drawing F1, ambiguity/abstain, strict metamorphic pass, affine error.
- **제안 합격선**: hidden-mutation 포함 `F1_bridge_oracle ≥ 0.6`, sentinel 전부 PASS, metadata audit PASS. 높은 점수 하나로 sentinel 실패를 상쇄할 수 없다.
- **킬 조건**: `F1_bridge_oracle < 0.4`면 5a/5b 동시 kill. 0.4–0.6은 발언권 보류와 bounded redesign 1회; PASS로 반올림 금지.
- **셔플 대조군**: provenance handle mapping을 drawing 내부에서 shuffle했을 때 진짜 mapping과 같은 성능이면 bridge truth chain FAIL.
- **예산**: 제안 1 CPU일, 유료 API 없음.
- **시드**: renderer/style seed 1701/1702/1703; hidden family seed는 prereg 파일에 봉인하고 개발자에게 비공개.

### 6.4 Cell V2 — SEG-FPC: 5b pixel segmentation

- **가설**: 소형 raster segmenter가 FPC 벽 mask를 학습해 synthetic render에서도 벽 픽셀 구조를 회수한다.
- **데이터**: counsel 허용 FPC drawing-level train/val/internal holdout; CL-C synthetic dev는 domain-transfer 진단.
- **조작**: 제한된 SegFormer-B0급 hyperparameter grid. U-Net은 loader/loss sanity baseline이며 model zoo 경쟁자가 아니다.
- **primary 지표**: FPC val wall-pixel IoU. 보조는 Dice, boundary F1, crop-edge recall, calibration/abstain, style-family별 IoU.
- **제안 합격선**: synthetic render에서 5b wall-pixel IoU ≥ 0.7. FPC val은 선택 곡선과 오류 유형을 보고하되 synthetic gate를 대신하지 않는다.
- **킬 조건**: counsel 불허, duplicate/split 누출, mask alignment 실패, 또는 synthetic IoU 0.7 미달이면 5b kill/demote. 이는 oracle bridge가 통과했다면 5a를 죽이지 않는다.
- **셔플 대조군**: drawing 단위로 mask를 shuffle한 동일 학습 budget. 정상 model과 구분되지 않으면 누출/학습 파이프라인 FAIL.
- **예산**: 제안 2–3 GPU일, RTX 5070 Ti 16GB, RAM 64GB. DGX 없음.
- **시드**: 1701/1702/1703 전부 실행·보고.

### 6.5 Cell V3 — SEG-BRIDGE-XFER: 5b end-to-end와 proxy 독립성

- **가설**: 5b mask가 bridge를 거쳐 synthetic handle truth를 회수하고, CubiCasa val에서 locked GBDT와 다른 오류를 낸다.
- **데이터**: synthetic hidden mutation, CubiCasa val 400, registered metamorphic variants. CubiCasa test는 닫힌 상태 유지.
- **primary 지표**: synthetic end-to-end handle F1. 보조는 CubiCasa val handle F1, GBDT+raster 고정 결합 F1, per-drawing macro F1, error-overlap Jaccard, class별 FP, strict metamorphic pass, proxy pairwise disagreement.
- **제안 합격선**: synthetic `F1_handle ≥ 0.6`; 5b pixel IoU ≥ 0.7 유지; zero/all sentinel PASS. CubiCasa에서는 GBDT와 오류가 완전히 중복되지 않고 fixed ensemble에 양의 기여가 있어야 H4 외부전이 후보가 된다.
- **킬 조건**: end-to-end F1 < 0.4이면 5b kill. 단 V1 oracle bridge가 ≥0.6이면 공통 bridge kill로 기록하지 않는다. metadata/render label 누출은 셀 무효.
- **proxy 감사**: 같은 synthetic/CubiCasa definition에서 exact/human label, metamorphic relation, raster vote, 허가된 silver vote의 disagreement tensor를 만든다. 세 proxy가 같은 handle에서 같은 오류를 반복하면 독립 증거로 합산하지 않는다.
- **셔플 대조군**: CubiCasa handle truth를 drawing 내부 prevalence-preserving shuffle하여 complementarity가 우연히 생기는지 확인.
- **예산**: 제안 1 CPU/GPU일, 외부 API 없음.
- **시드**: V2의 3개 checkpoint 전부; permutation seed 1701 고정.

### 6.6 Cell V4 — VLM-CHEAP20: 5a 최저가 screen

- **가설**: 이름·메타데이터가 없는 20개 divergent definition crop만으로 프런티어 VLM이 non-degenerate wall region을 제시한다.
- **데이터**: CL-A가 정렬 artifact를 제거하고 봉인한 divergent-20, definition당 primary neutral render 1장.
- **조작**: 없음. prompt, endpoint, model revision, decoding은 synthetic dev에서 이미 봉인.
- **primary 지표**: schema-valid non-abstain rate와 provisional family-disagreement resolution count. 보조는 polygon validity, bridge ambiguity, crop-edge abstain, per-def billed cost, P0 forensic category와의 교차표.
- **제안 합격선**: 이 셀 단독으로 최종 PASS를 주지 않는다. 적어도 하나의 provisional resolution과 유효한 bridge output이 있어야 V5 비용을 정당화한다.
- **킬 조건**: 예상 또는 누적 비용이 `B_API` envelope를 넘음, API/retention 미승인, repeated invalid schema, 모든 사례 non-informative abstain이면 5a 비용/효용 kill.
- **셔플 대조군**: image와 response 연결을 shuffle한 분석에서 동일한 handle resolution이 나오면 join pipeline FAIL. 추가 API 호출은 하지 않는다.
- **예산**: 패킷 기준 1일, image 20장, 유효 응답 20개 이하, 소액 API envelope 내부.
- **시드**: temperature 제안값 0; endpoint seed 지원 시 1701 하나. 유효 응답 재표본화 금지.

### 6.7 Cell V5 — JURY-META: H4/H3 배심 가치 확인

- **가설**: V1–V4를 통과한 raster juror가 vector family disagreement를 strict metamorphic relation을 지키며 해소하거나 family-level Fleiss κ를 유의하게 높인다.
- **데이터**: divergent-20 primary와 봉인된 강체회전/반사/translation-crop/layer-rename/unit/explode 관계 중 renderer가 지원하는 등록 battery. 5a는 cost envelope가 허용하는 최소 변형만, 5b는 전체 battery.
- **primary 지표**: strict metamorphic-consistent `resolution_rate`. 공동 primary 대안은 family-collapsed `Δκ`와 prevalence-preserving one-sided permutation test다.
- **제안 합격선**: 20개 중 최소 6개를 strict 조건으로 해소 **또는** `Δκ > 0`이고 봉인한 α=0.05 permutation gate 통과. E1.5 편입에는 별도로 B1 ≥0.70 및 B4 Pearson ≥0.70이 모두 필요.
- **킬/강등 조건**: 두 가치 band 모두 미달이면 tie-breaker/diagnostic으로 demote. sentinel 실패, layer rename 후 image hash 변화, transform inverse 실패는 셀 무효. κ 상승과 truth/invariance 하락이 함께 나타나면 juror kill.
- **비교**: 5a, 5b를 각각 한 표로 평가한다. 둘을 함께 넣는 분석은 their error correlation이 낮다는 V3 증거가 있을 때만 secondary.
- **셔플 대조군**: raster vote를 definition·prevalence strata 안에서 permutation해 resolution/Δκ null을 만든다.
- **예산**: 5b 로컬 1일. 5a는 V4 이후 잔여 `B_API` 이내; 부족하면 BLOCKED이며 screen을 최종 PASS로 승격하지 않는다.
- **시드**: model seed는 V2 세 개 전부; permutation seed 1701; VLM은 V4의 고정 endpoint/seed.

### 6.8 Cell V6 — CUBICASA-TEST-ONCE: 외부 단발 확인

- **가설**: FPC에서 학습하고 synthetic/CubiCasa val에서 잠근 5b가 CubiCasa test 400에서도 locked GBDT에 상보적인 handle signal을 낸다.
- **개방 조건**: counsel 승인, V1/V2/V3 통과, config·threshold·metric code·xlsx schema hash 봉인, test 접근 로그가 비어 있음.
- **primary 지표**: locked `GBDT+raster`와 `GBDT-only`의 per-handle F1 차이. 보조는 raster-only F1/precision/recall, macro drawing F1, error categories, abstain, strict relation subset.
- **제안 합격선**: fixed ensemble의 F1 차이에 대한 paired drawing-level confidence interval 하한이 0보다 크고, synthetic bridge/IoU gate가 유지된 config일 것. 이 조건은 새 test threshold 선택을 허용하지 않는다.
- **킬 조건**: test에서 config를 변경하거나 두 번 열면 confirmatory claim 무효. 양의 상보성이 없으면 CubiCasa external-generalization claim kill; real divergent jury 결과가 있더라도 별도 제한적 관찰로만 남긴다.
- **셔플 대조군**: test를 본 뒤 새 shuffle 설계를 만들지 않고 V3에서 봉인한 procedure를 그대로 한 번 적용.
- **예산**: 제안 반나절 로컬 inference/채점, 학습 없음, API 없음.
- **시드**: V2 세 seed ensemble 규칙을 val에서 고정. test에서 seed 선택 금지.

### 6.9 셀 간 판정 행렬

| 결과 | 5a | 5b | 공통 lane |
|---|---|---|---|
| V1 oracle bridge <0.4 | KILL | KILL | KILL |
| V1 0.4–0.6 | 발언권 없음 | 발언권 없음 | bridge redesign 1회만 |
| V2 IoU <0.7, V1 통과 | 영향 없음 | KILL/DEMOTE | 5a만 가능 |
| V4 API 미승인 | BLOCKED | 영향 없음 | 5b만 가능 |
| V4 비용 초과 | 비용 KILL | 영향 없음 | 5b만 가능 |
| V5 가치 band 미달 | DEMOTE | DEMOTE | tie-breaker만 |
| V6 외부 상보성 없음 | real screen 관찰만 | external claim KILL | 제품 승격 금지 |

---

## 7. red team 티켓 응답

패킷은 red-team 원문 전체가 아니라 패널 보고서에 노출된 티켓 번호와 요지를 제공한다. 아래는 그 안에서 P5/CL-G에 직접 연결되거나 선결 의존성이 있는 티켓만 다룬다. 원문에 없는 세부 문구를 만들어내지 않는다.

| 티켓/선결 | P5에 걸리는 공격 | 응답 | 판정 전 필요한 증거 |
|---|---|---|---|
| **T1 / PR-2** | synthetic·external·metamorphic·silver가 같은 평행 이중선 prior를 공유하면 다중 증거가 아니라 편향 증폭 | V3에서 same-definition disagreement tensor, error-overlap, prevalence-preserving shuffle을 의무화한다. 독립성이 확인되지 않은 proxy는 합산하지 않는다. | proxy별 per-handle raw prediction과 disagreement xlsx |
| **T2 / PR-1** | 현재 synthetic truth에 벽 코드가 없어 bridge truth chain이 시작되지 않음 | CL-C의 exact mask/handle/provenance와 fidelity gate를 hard dependency로 둔다. toy unit fixture를 PASS로 승격하지 않는다. | generator hash, fidelity report, hidden mutation manifest |
| **T3** | divergent-20이 `_score_divergence` 정렬 설계 artifact일 수 있음 | V4 전에 CL-A 재계산 결과로 표본을 다시 봉인한다. 기존 top-20을 관성적으로 쓰지 않는다. | sorted candidate table, selection rule hash |
| **T4** | P0의 Ornith 나열/지시 artifact와 raw 판정 근거가 미확정 | 5a 교차대조는 T4 raw evidence가 있는 사례만 사용한다. 없으면 “P0와 일치” 주장을 하지 않는다. | raw response IDs와 artifact adjudication |
| **T5 / PR-3** | FloorPlanCAD/CubiCasa NC 라벨과 원도면 권리 미해결 | 학습·외부 평가 전 counsel 서면, NC 기술 방화벽, clean retraining 분리를 적용한다. 권한 없음은 BLOCKED/KILL로 기록한다. | counsel 문서 ID, dataset/weight lineage, product deny test |
| **T7** | violation-only metamorphic band가 empty detector를 통과시킴 | V1/V3/V5 모두 0-wall/all-wall sentinel과 recall floor를 같이 요구한다. strict invariance 단독 PASS를 금지한다. | sentinel별 prediction과 confusion table |
| **T10의 gate 식별자 부수 수정** | silver 자격의 B1/B4 식별자가 좌석 간 모순 | P5는 패널 결론대로 `B1 ≥0.70 AND B4 Pearson ≥0.70`을 사용한다. 한 조건만 인용하지 않는다. | sealed E1.5 prereg/result, metric field names |
| **T13** | DGX Ornith-35B의 vision 지원 여부 미확인 | capability preflight로 확인하고, 미지원이면 외부 API 전용으로 둔다. DGX를 primary dependency로 삼지 않는다. | endpoint capability response와 model revision |
| **T17 / CL-E** | truth source 간 전이뿐 아니라 같은 definition 불일치 구조가 필요 | V3의 proxy 독립성 arm을 CL-E evidence schema와 병합한다. 평균 accuracy로 disagreement를 숨기지 않는다. | same-def proxy tensor와 conditional error overlap |
| **T24** | pixel→handle 역투영 exact harness가 없으면 CRS/bridge kill risk | sparse coverage provenance, affine inverse, INSERT instance path, oracle-mask gate를 먼저 구현한다. `F1_bridge_oracle<0.4`면 양 트랙 kill한다. | round-trip tests, `A[p,h]` audit, oracle bridge report |
| **T31** | raster를 근거 없이 “본선”으로 승격 | P5는 raster를 한 표로만 둔다. CL-B가 놓친 zero-pair/divergent를 넘어서는 회수와 외부 상보성이 입증되기 전 본선 주장을 PARK한다. | CL-B 대비 error recovery와 V5/V6 결과 |
| **T34** | load-bearing 인용이 `experiment_executed:false`인데 사실처럼 쓰일 위험 | 본 문서의 논문은 방법 계보만 설명한다. 모든 실측 판정은 local run evidence에 연결하고 executed flag를 재확인한다. | citation status ledger와 run evidence hash |

추가로 패널의 VLM silver 조건을 그대로 수용한다. VLM이 polygon을 잘 그린다는 사실만으로 silver 자격이 생기지 않는다. E1.5 B1/B4 gate가 닫히지 않으면 5a는 independent diagnostic일 뿐 ensemble juror로 편입하지 않는다.

Red team 위험 중 완전히 해소할 수 없는 것도 남는다.

- 프런티어 VLM의 사전학습 출처와 데이터 중복은 완전 감사가 불가능하다. 이 때문에 5a를 truth로 쓰지 않는다.
- FPC와 CubiCasa의 시각 양식 차이는 augmentation으로 줄일 수 있을 뿐 제거를 보장하지 못한다.
- poché에서 한 영역이 여러 경계 handle을 설명하는 식별 불가능성은 단일 handle 정확도로 강제하지 않고 ambiguity/abstain으로 수용한다.
- divergent-20은 작고 선택된 표본이므로, V5 생존은 광범위한 실도면 일반화를 뜻하지 않는다. V6와 별도 실코퍼스 확장이 필요하다.
- Fleiss κ는 prevalence와 rater 구성에 민감하다. raw/가문접기 결과와 permutation null을 함께 내고 accuracy 대리로 해석하지 않는다.

---

## 8. 인접 제안과의 관계 및 정직한 종료 조건

### 8.1 병합해야 할 지점

| 인접 클러스터/제안 | 병합 지점 | P5가 가져오는 고유 부분 | 경계 |
|---|---|---|---|
| **CL-A / platt P0 법의학** | 정렬 artifact 제거, sealed divergent-20, P0 category | 같은 표본을 name-blind raster로 교차대조 | CL-A가 표본을 확정하기 전 VLM 호출 금지 |
| **CL-B coverage-complete vector** | 동일 handle universe와 기준선, recovered/missed error set | pixel context와 visual convention | CL-B가 싸게 전부 해결하면 P5 확장 불요 |
| **CL-C synthetic truth** | exact mask, `wall_member(h)`, hidden mutations | provenance bridge와 vision gate | 생성기 fidelity 미통과 시 P5 PASS 불가 |
| **CL-D metamorphic battery** | transform registry, canonical handle relation, sentinels | raster-specific image/hash/crop invariance | empty predictor 방지 규칙 공유 |
| **CL-E truth-source cross-factor** | same-definition proxy tensor와 independence audit | FPC→CubiCasa raster transfer 축 | proxy를 독립이라고 선가정하지 않음 |
| **CL-F GBDT 사다리** | CubiCasa locked baseline, per-handle xlsx, error categories | GBDT와 다른 pixel-context vote | raster가 GBDT를 복제하면 죽음 |
| **CL-I 관례 prior** | name mask/ablation, firm convention 분석 | layer/block name을 물리적으로 못 보는 반증축 | visual line style까지 “관례 없음”으로 오인 금지 |
| **calibration P4/P5, doe P6** | segmentation/VLM/bridge cell을 하나의 CL-G 실행체로 통합 | 두 트랙의 공통 bridge kill과 한 표 원칙 | 모델마다 별도 truth 기준을 만들지 않음 |
| **feyerabend P5** | raster mechanism은 공유 | 본선이 아니라 조건부 juror라는 보수적 역할 | T31 조건 전 “raster mainline” PARK |

### 8.2 차별점

P5의 차별점은 “VLM을 써 본다”거나 “SegFormer를 학습한다”가 아니다.

1. prompted frontier와 local learned segmentation을 분리해 비용·권리·실패 원인을 섞지 않는다.
2. 두 트랙이 공유하는 bridge를 oracle mask로 먼저 죽이거나 살린다.
3. vector handle로 돌아오지 못한 pixel 성능은 벽 탐지기 성능으로 인정하지 않는다.
4. raster juror는 이름을 못 보므로 H4뿐 아니라 H3의 관례 신호를 교차검증한다.
5. 상관된 5개 silver 판정자를 5독립 표로 세지 않고 약 2개 가문으로 접는다.
6. NC weight는 연구 계측기일 뿐 제품 후보가 아니며, 승리해도 clean retraining을 새로 결재한다.

### 8.3 이 제안이 죽어야 하는 조건

다음 중 하나면 미련 없이 정해진 범위에서 죽인다.

- **공통 kill**: synthetic oracle back-projection handle F1 <0.4.
- **공통 block→종료**: PR-1/CL-C fidelity pack이 없거나 exact provenance truth chain을 만들 수 없음.
- **5a 비용 kill**: 20개 primary 호출 예상/실비가 승인 `B_API`를 넘음.
- **5a 권한 kill/block**: API 반출·retention 승인이 없거나 strict polygon schema를 안정적으로 지원하지 않음.
- **5a 자격 박탈**: E1.5 B1≥0.70과 B4 Pearson≥0.70 중 하나라도 미달인데 silver로 편입하려 함.
- **5b 권리 kill**: counsel이 FPC 학습 또는 산출 weight를 허용하지 않음.
- **5b 성능 kill**: synthetic pixel IoU <0.7 또는 end-to-end handle F1 <0.4. oracle bridge가 통과했다면 5a는 별도 유지 가능.
- **배심 가치 kill/demote**: divergent-20의 30% 미만 해소이고 유의한 양의 Δκ도 없음.
- **정합성 kill**: layer rename image hash, affine inverse, strict metamorphic relation, sentinel 중 load-bearing 항목 실패.
- **독립성 kill**: raster 오류가 vector/GBDT와 사실상 동일하고 fixed ensemble에 양의 기여가 없음.
- **비교우위 소멸**: CL-B가 같은 divergent를 더 낮은 비용·더 높은 재현성으로 회수하고 raster만의 추가 회수가 없음.
- **외부 일반화 kill**: CubiCasa test 단발에서 locked GBDT+raster가 GBDT-only보다 상보적이지 않음. 이 경우 제품/일반화 주장은 종료한다.
- **계보 오염**: NC weight, pseudo-label, feature cache가 product 또는 clean-retraining 경로로 유입됨.

### 8.4 최종 의사결정 규칙

의사결정 순서는 `권한/자산 → oracle bridge → track별 vision → proxy 독립성 → jury value → test once → clean retraining 별도 결재`다. 뒤 단계의 좋은 숫자가 앞 단계 실패를 상쇄할 수 없다.

현재 패킷 근거만으로 내릴 수 있는 상태는 **CANDIDATE / EXECUTION-BLOCKED**다. 이유는 synthetic wall generator/fidelity gate, counsel 서면, 프런티어 API 승인, Ornith vision capability, CL-A의 정렬 artifact 해소가 아직 열려 있기 때문이다. 이는 P5가 실패했다는 뜻도, 준비됐다는 뜻도 아니다. 위 선결을 닫고 V1부터 순서대로 실행할 수 있는 수준의 계획이 완성됐다는 뜻뿐이다.

P5가 살아남으면 산출은 “벽 truth”가 아니라 `(handle vote, abstain, provenance, transform consistency, juror contribution)` 연구 증거다. 제품 반입은 clean licensed data 재훈련과 별도 test 승인을 거친 뒤에만 논의한다.

DOSSIER_COMPLETE: platt_P5
