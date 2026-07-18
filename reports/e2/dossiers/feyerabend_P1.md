# E2 방법론 심층 도시（Dossier）— feyerabend_P1

## 제안 P1: 면(face)/포셰(poché) 유도 벽 — LINE-쌍 관측 언어의 반증

- **연구 질문:** 벽을 평행 LINE 쌍으로 먼저 찾지 않고, 평면 arrangement에서 방/공간 face와 그 사이의 두께 있는 물질 face를 먼저 만든 뒤 face-adjacency dual의 bridge로 정의하면, E1의 `LLM high ∧ n_pairs=0` 구간을 회수할 수 있는가?
- **핵심 산출:** wall-ribbon polygon 집합, face dual의 bridge 집합, 원 CAD handle별 벽 점수, 그리고 face 추출 실패를 숨기지 않는 품질 상태.
- **주 엔진:** Shapely를 통한 GEOS noding/`polygonize_full`. GEOS는 GPL이 아닌 계열의 엔진으로 채택하되, 실제 배포 전 사용 버전과 정확한 라이선스 문구는 counsel이 재확인한다.
- **현재 증거 상태:** 이 문서는 실행 계획이다. 여기서 새 실험 결과를 주장하지 않는다. 수치로 인용하는 현황은 패킷의 2026-07-18 다이제스트뿐이며, 아래의 새 임계값·시간·시드 수는 모두 **사전등록 제안값**이다.
- **판정 위치:** 전 항목은 candidate이고 채택권은 Paul에게 있다. 이 제안은 PR-1 합성 벽 생성기, CL-A E1 법의학 감사, T27 messy divergent-20 게이트를 통과하기 전에는 `VIABLE`을 주장하지 않는다.

---

## 1. 이론적 근거·선행연구

### 1.1 관측 언어를 바꾸는 이유

기존 LINE-쌍 관측 언어는 “벽이면 두 개의 충분히 길고 거의 평행한 선분이 일정 거리로 떨어져 있다”는 구현 관례를 벽의 정의로 끌어올린다. 그 언어에서는 LWPOLYLINE, ARC가 섞인 윤곽, INSERT 안의 변환된 조각, 짧은 갭, 비평행 테이퍼, 닫힌 HATCH 포셰가 실제로 같은 벽을 표현해도 후보 생성 단계에서 사라질 수 있다. 패킷의 E1 `LLM high ∧ n_pairs=0`은 곧바로 LLM의 승리나 탐지기의 실패를 뜻하지 않는다. 우선 “관측기가 그 표현을 말할 수 있었는가”를 시험해야 한다.

P1은 다음과 같이 존재론을 역전한다.

1. 선은 벽 객체가 아니라 평면을 분할하는 경계 조각이다.
2. 방/외부/포셰/잡물의 atomic face를 먼저 만든다.
3. 두 개의 공간 face 사이에 놓인 두께 있는 face 또는 face 묶음만 wall-ribbon 후보가 된다.
4. 벽은 `(space_i, ribbon, space_j)`라는 dual bridge이고, LINE 쌍은 그 bridge를 지지할 수 있는 여러 증거 중 하나일 뿐이다.

이 정의는 “가구 안의 작은 닫힌 사각형”과 “두 방을 가르는 좁고 긴 물질 대역”을 길이·평행성만으로 구분하지 않는다. 후보가 실제로 서로 다른 두 macroscopic space에 접하는지, arrangement를 가르는지, 포셰/고정 폭/경계 연속성이 있는지를 함께 본다. 따라서 Direction 화살표, DimensionMark, Door/Window 기호처럼 대역 내 평행 구조를 갖는 CubiCasa의 주된 false positive에 대해 새로운 식별 축을 제공한다.

### 1.2 방법론 계보

이 제안은 다음 계보를 결합한다. 아래 문헌은 알고리즘 계보를 설명하기 위한 일반 지식이며, 문헌의 실험 수치를 본 제안의 근거로 사용하지 않는다. 정확한 판본·연도·URL은 구현 PR에서 **요검증**한다.

- **평면 arrangement와 DCEL:** 계산기하학의 line/curve arrangement, intersection noding, half-edge/DCEL 표현은 평면을 vertex-edge-face로 분해하고 face 인접성을 명시한다. de Berg 등의 `Computational Geometry` 교과서 계열과 Bentley–Ottmann sweep-line 계열이 이 기반이다.
- **OGC Simple Features, JTS/GEOS Polygonizer:** 완전히 noded된 linework에서 유효 ring, polygon, dangle, cut edge, invalid ring을 분리하는 polygonization 계열이다. 본 계획은 `polygonize`만 호출해 성공처럼 보이지 않고 `polygonize_full`의 잔여물을 품질 신호로 보존한다. 정확한 GEOS/Shapely API 버전은 요검증한다.
- **Region Adjacency Graph와 planar dual:** 영상분할 및 지도 일반화에서 영역을 node, 공유 경계를 edge로 바꾸는 전통이다. P1은 여기에 두께 있는 포셰 face를 중간 node로 남겨 `space–wall–space` 삼항 bridge를 만든다.
- **형태학적 skeleton/medial axis:** Blum의 medial-axis 계열과 straight-skeleton 계열은 좁고 긴 polygon의 국소 폭과 중심 구조를 추정하는 도구다. P1에서는 wall 여부를 정의하는 단독 신호가 아니라 ribbon 폭의 일관성과 T/L 접합 분해를 위한 보조 신호다. straight-skeleton의 정확한 서지사항은 요검증한다.
- **room-first floor-plan reconstruction:** Floor-SP, MonteFloor, RoomFormer처럼 방 polygon이나 room layout을 먼저 복원하는 연구 계열은 “선분 분류 후 방 조립”이 유일한 순서가 아님을 보여준다. 이 이름들의 정확한 저자·학회·연도는 요검증한다. P1은 래스터 신경망을 그대로 채택하는 것이 아니라 room-first의 표현 순서를 CAD arrangement에 옮긴다.
- **CAD boundary representation과 poché 관례:** 건축 도면에서 벽은 두 경계 사이의 재료 영역, HATCH된 포셰, MLINE, 닫힌 polyline 등으로 표현될 수 있다. 이 관례는 `LINE 두 개`보다 `공간 사이의 물질 대역`이라는 정의에 직접 대응한다.
- **Feyerabend식 방법론적 다원주의:** 지배 이론의 평가 언어가 반대 이론의 현상을 구조적으로 0으로 만드는 경우, 같은 점수기 안에서 가중치만 조절할 것이 아니라 관측 언어 자체를 바꾸어 판별 실험을 해야 한다. `Against Method`의 정확한 판본은 요검증하며, 이는 역사적 권위 인용이 아니라 실험 설계 원칙으로만 사용한다.

### 1.3 반증 가능한 주장

P1은 세 개의 독립된 주장을 한다.

- **C1 — 표현 회수:** LINE-쌍이 0이어도 닫힌 face 위상과 provenance가 남아 있으면 wall bridge를 회수할 수 있다.
- **C2 — 교란 억제:** 길고 평행한 기호라도 서로 다른 두 space face를 가르는 ribbon이 아니면 탈락하므로, 기존 v1이 혼동한 비벽 구조를 일부 제거할 수 있다.
- **C3 — 변환 등변성:** 모든 길이 임계가 도면에서 동차적으로 계산되는 scale anchor에 상대적이면, 강체 변환과 균일 scale 뒤에도 provenance 기준 bridge 집합이 같아야 한다.

다음은 주장하지 않는다.

- 모든 open plan을 자동으로 닫을 수 있다고 주장하지 않는다.
- 포셰나 두께 단서가 전혀 없는 centerline-only 도면에서 물리 벽 두께를 식별할 수 있다고 주장하지 않는다.
- LLM handle을 사람 진리로 취급하지 않는다.
- FloorPlanCAD raster mask를 CAD line-handle 라벨로 둔갑시키지 않는다.
- face-first가 기존 GBDT val F1 0.517을 반드시 넘는다고 예고하지 않는다. 그것은 별도 비교 셀이 결정한다.

---

## 2. 알고리즘 정확 스펙

### 2.1 입력, 출력, 단위

입력 도면 `D`는 다음 record의 집합이다.

```text
Entity {
  source_handle: string
  parent_insert_chain: [handle]
  kind: LINE | LWPOLYLINE | POLYLINE | ARC | CIRCLE | SPLINE |
        HATCH_BOUNDARY | INSERT_EXPANDED_FRAGMENT | OTHER
  geometry_local
  world_transform
  layer_id               # 기록만 하며 primary score 가중치는 0
  closed_flag
}
```

정규화 후 모든 조각은 `CurveFragment(geometry_world, source_handle, t0, t1)`가 된다. ARC/SPLINE 근사는 원 handle과 매개변수 구간을 잃지 않는다. INSERT는 중첩 변환을 순서대로 합성해 world 좌표로 전개한다. 원 handle이 없는 가상 gap repair edge에는 `virtual_repair_id`만 부여하며, 이를 벽 handle 정답 또는 예측으로 내보내지 않는다.

도면 scale anchor `s(D)`는 유효 curve 길이의 절사 중앙값과 전체 bbox 대각선으로 구성한 동차 함수로 둔다. 둘 중 하나가 퇴화하면 다른 하나로 fallback하고, 둘 다 퇴화하면 `DEGENERATE_SCALE`로 중단한다. 중요한 조건은 모든 좌표를 `c·D`로 scale했을 때 `s(c·D)=c·s(D)`가 되는 것이다. 물리 mm나 CubiCasa px의 절대 대역을 primary arm에서 사용하지 않는다.

출력은 다음 네 묶음이다.

1. `FaceRecord`: polygon, 면적/둘레/폭 통계, 인접 face, 경계 provenance, 분류 `SPACE/WALL_MASS/NUISANCE/OUTSIDE`.
2. `BridgeRecord`: `bridge_id`, 양 끝 space id, ribbon polygon, wall-mass id, supporting handles, virtual-repair 목록, confidence 구성요소.
3. `HandleRecord`: source handle별 `wall_member∈{0,1}` 또는 연속 score, 어떤 bridge가 지지했는지, geometry coverage.
4. `QualityRecord`: dangle/cut/invalid ring, repair 수, face 수, bridge 수, provenance 손실률, 상태 `OK/OPEN_PLAN_INSUFFICIENT/EXPLOSION/PROVENANCE_LOSS/INVALID`.

`QualityRecord`가 실패 상태면 빈 예측을 성공으로 점수화하지 않는다. 그 도면은 명시적인 abstention/failure로 기록한다.

### 2.2 정규화와 arrangement

#### A. 엔티티 전개

1. INSERT를 재귀 전개하고 world transform을 적용한다.
2. LWPOLYLINE/POLYLINE의 bulge와 closed flag를 보존한다.
3. ARC/CIRCLE/SPLINE은 chord error `ε_arc=α_arc·s(D)` 이하의 조각으로 근사하되 원 curve provenance를 보존한다.
4. zero-length, NaN, 중복 조각은 제거하되 제거 사유와 handle을 기록한다.
5. 레이어명과 block명은 primary arm에서 feature로 쓰지 않는다. name-aware arm은 독립성 감사용 ablation으로만 둔다.

#### B. noding

GEOS unary noding으로 모든 교차점을 분할한다. snap은 `ε_snap=α_snap·s(D)` 이내 endpoint에만 적용하며, 합치기 전후의 component 수, 교차 생성 수, 원 handle coverage를 기록한다. snap으로 서로 다른 층위의 선이 무조건 합쳐지는 것을 막기 위해 다음 조건을 모두 요구한다.

- 두 endpoint 사이 연결선이 기존 선을 가로지르지 않는다.
- 연결 뒤 비정상적으로 작은 sliver face가 생기지 않는다.
- tangent 조건 또는 closure-gain 조건 중 하나가 성립한다.
- 결정 tie-break는 좌표 양자화 키와 source handle의 사전식 순서로 고정한다.

#### C. strict polygonization

먼저 repair 없이 `polygonize_full`을 실행한다. polygon뿐 아니라 dangle, cut edge, invalid ring을 모두 보존한다. 이 결과가 `strict arm`이다. strict arm이 충분하면 repaired arm을 선택하지 않는다.

#### D. 기록 가능한 gap repair

strict arm이 `OPEN_PLAN_INSUFFICIENT`일 때만 endpoint pair 후보를 공간 index로 만든다. 후보 `g=(u,v)`의 점수는 다음 lexicographic tuple이다.

```text
repair_key(g) = (
  creates_valid_face,          # 우선
  decreases_dangle_length,
  tangent_compatibility,
  local_width_consistency,
  -gap_length,
  stable_tie_break
)
```

교차를 만들거나 invalid ring을 늘리거나, synthetic truth에서 명시된 door void를 물질로 채우는 후보는 금지한다. repair edge는 topology closure에만 사용한다. 최종 ribbon mask에서는 repair edge 자체와 알려진 opening void를 빼며, source handle 예측에도 포함하지 않는다. `strict`와 `repaired` 결과를 모두 evidence에 남겨 repair가 성능을 만든 정도를 보이게 한다.

### 2.3 atomic face에서 space와 wall mass로

polygonized atomic face 집합을 `F`, 외부를 `f∞`라 한다. 두 face가 길이 0보다 큰 경계를 공유하면 dual adjacency `A(f_i,f_j)`를 만든다. 공유 경계 길이는 정규화된 절대값과 각 face 둘레 대비 비율을 함께 기록한다.

각 face `f`에 대해 다음 feature를 계산한다.

- `area(f), perimeter(f), compactness(f)`
- medial-axis 표본에서의 국소 폭 중앙값 `w50(f)`와 robust dispersion `wMAD(f)`
- 장축 대비 길이, 폭의 일관성, sliver 여부
- HATCH boundary/region과의 overlap
- boundary를 구성한 entity kind와 parent handle 다양성
- 접한 이웃 face의 수와 공유 경계 비율
- 제거했을 때 macroscopic space component가 어떻게 갈라지는지 나타내는 separator score
- containment depth와 “한 개의 큰 face 내부에만 붙은 작은 기호” 여부
- virtual repair 의존 비율

초기 `SPACE` seed는 상대적으로 큰 비-sliver face 중 외부가 아니며, boundary 대부분이 단일 작은 기호에 종속되지 않은 face다. 초기 `WALL_MASS` seed는 다음 증거 중 둘 이상을 만족하되, 반드시 두 개 이상의 서로 다른 `SPACE/OUTSIDE` contact를 가져야 한다.

1. 폭이 좁고 국소 폭 dispersion이 낮다.
2. HATCH/닫힌 포셰 region과 겹친다.
3. 서로 다른 macroscopic space 사이의 separator다.
4. 양쪽 경계 provenance가 서로 다른 curve chain에서 온다.
5. 고정 폭 대역으로 설명된다.

“평행 경계”는 5번의 약한 구성요소일 수 있지만 hard gate가 아니다. primary face-only arm에서는 그 가중치를 0으로 고정한다. 이 arm이 실패하고 parallel 보조 arm만 성공하면 “관측 언어 교체”가 아니라 기존 prior의 재포장으로 판정한다.

분류는 두 번의 deterministic fixed-point로 한다.

1. seed로부터 `SPACE/WALL_MASS/NUISANCE`를 초기화한다.
2. 한 space에만 붙은 작은 closed face는 `NUISANCE` 후보로 내리고, 그 주변 space component를 합친다.
3. 두 space 사이 contact를 가진 narrow/poché face를 `WALL_MASS`로 올린다.
4. wall mass를 제거했을 때의 component와 contact를 재계산한다.
5. label이 안정될 때까지 반복하되 사전등록된 최대 반복 수에서 멈추고 미수렴이면 `INVALID`로 둔다.

### 2.4 wall mass를 bridge ribbon으로 분해

단순한 직사각형 wall face는 하나의 bridge가 된다. T/L 교차처럼 연결된 포셰가 여러 방에 접하면 wall-mass `w`의 boundary contact arc를 space별로 묶고 medial axis를 따라 서로 마주 보는 contact arc를 pairing한다.

space contact를 `C(w,r) = ∂w ∩ ∂r`라 하자. 후보 bridge `b=(r_i,w,r_j)`는 다음을 만족한다.

```text
r_i != r_j
contact_length(C(w,r_i)) >= τ_contact
contact_length(C(w,r_j)) >= τ_contact
there exists a connected corridor through w between both contacts
local corridor widths fall inside the learned-from-synthetic relative band
the corridor is not explained by a one-space-contained nuisance face
```

외벽은 `r_j=OUTSIDE`를 허용한다. 한쪽만 공간에 접하고 다른 쪽 contact를 확인할 수 없는 포셰는 wall 후보로 보존할 수 있지만 `bridge_unresolved`로 내며, main bridge recall/containment에는 성공으로 세지 않는다.

T/L 교차에서는 contact pair별 최단 내부 경로 주변의 Voronoi/medial cells를 합쳐 pairwise ribbon `R_b`를 만든다. 여러 bridge ribbon이 junction에서 겹칠 수 있으며, union mask는 중복 면적을 한 번만 센다. 이 분해는 LINE pair를 만들지 않는다.

### 2.5 원 handle로 역투영

bridge `b`의 supporting handle 집합은 다음으로 정의한다.

```text
H(b) = {
  h |
  boundary fragments carrying h overlap ∂R_b above τ_handle
  OR a closed/HATCH entity carrying h overlaps interior(R_b) above τ_hatch
}
```

ARC/SPLINE tessellation 조각은 parent source handle로 합친다. INSERT 내부 조각은 leaf handle과 parent chain을 모두 기록하되, 평가 키는 하네스가 요구하는 원 source handle 하나로 사전 고정한다. 매핑이 일대일이 아니면 임의 선택하지 않고 `PROVENANCE_LOSS`로 기록한다.

LLM containment는 def별로 다음처럼 계산한다.

```text
containment_d = |H_LLM,d ∩ H_face,d| / |H_LLM,d|
```

`|H_LLM,d|=0`인 def는 1로 채우지 않고 `undefined`로 보고한다. ribbon IoU와 handle containment는 서로 다른 지표이며 혼합하지 않는다.

### 2.6 목적함수와 모델 선택

이 방법의 core는 학습 모델이 아니라 deterministic geometry pipeline이다. 하이퍼파라미터는 synthetic development seed에서만 선택하고, 다음 lexicographic loss를 최소화한다.

1. provenance 손실, invalid geometry, 0-wall/all-wall sentinel 실패 수
2. `1 - bridge_recall`
3. false bridge 수와 ribbon false-positive 면적
4. metamorphic bridge-set violation
5. virtual repair 수와 총 repair 길이
6. runtime과 peak RAM

단일 가중합으로 첫 번째 안전 조건을 보상하지 않는다. 예를 들어 recall이 높아도 sentinel 또는 provenance가 실패하면 탈락이다.

### 2.7 하이퍼파라미터 공간

아래 값은 모두 **사전등록 제안 grid**이며 측정 결과가 아니다. 길이는 `s(D)`에 상대적이다.

| 그룹 | 기호 | 제안 공간 | 선택 원칙 |
|---|---:|---|---|
| curve 근사 | `α_arc` | `{1e-5, 3e-5, 1e-4}` | topology가 같으면 가장 거친 값 |
| endpoint snap | `α_snap` | `{1e-5, 3e-5, 1e-4, 3e-4}` | repair와 bridge 수가 작은 값 |
| gap repair | `ε_gap/ε_snap` | `{0, 1, 2, 4}` | strict 성공 시 0 우선 |
| room seed 면적 분위 | `q_room` | `{0.60, 0.70, 0.80}` | synthetic hidden seed recall 우선 |
| 폭 dispersion 상한 | `CV_width` | `{0.25, 0.50, 0.75}` | 낮은 복잡도 우선 |
| 양쪽 contact 최소비 | `ρ_contact` | `{0.15, 0.25, 0.35}` | false bridge가 작은 값 |
| HATCH overlap | `ρ_hatch` | `{0, 0.25, 0.50}` | HATCH 없는 도면도 작동해야 함 |
| handle coverage | `ρ_handle` | `{0.25, 0.50, 0.75}` | per-handle val에서만 선택 |
| parallel 보조 가중치 | `β_parallel` | primary `0`, ablation `0.10` | primary는 반드시 0 |
| layer/name 가중치 | `β_name` | primary `0`, audit-only `0.10` | 제품 후보는 0 |
| fixed-point 반복 | `K` | `{2, 4, 8}` | 안정되는 최소값 |

grid 전체를 실도면 top-20에 돌려 좋은 값만 고르는 행위는 금지한다. synthetic development에서 하나의 config를 고르고 config hash를 봉인한 뒤 top-20을 한 번 실행한다.

### 2.8 의사코드

```python
def infer_face_bridges(drawing, cfg):
    fragments, provenance = normalize_and_expand(drawing, cfg)
    scale = homogeneous_scale_anchor(fragments)
    if scale.is_degenerate:
        return abstain("DEGENERATE_SCALE")

    noded = geos_node(fragments, cfg.alpha_snap * scale)
    strict = polygonize_full_with_diagnostics(noded)

    if quality_sufficient(strict, cfg):
        chosen = strict
        repairs = []
    else:
        repairs = propose_repairs(strict, noded, scale, cfg)
        repaired = apply_virtual_repairs_lexicographically(
            noded, repairs, forbid_crossing=True
        )
        chosen = polygonize_full_with_diagnostics(repaired)

    if provenance_coverage(chosen, provenance) < cfg.min_provenance:
        return abstain("PROVENANCE_LOSS", diagnostics=chosen)

    faces = build_atomic_faces(chosen)
    dual = build_face_adjacency(faces, include_outside=True)
    features = compute_face_and_separator_features(faces, dual)

    labels = fixed_point_label(
        faces=faces,
        dual=dual,
        features=features,
        parallel_weight=0.0,
        name_weight=0.0,
        max_iter=cfg.max_iter,
    )
    if not labels.converged:
        return abstain("INVALID", diagnostics=chosen)

    wall_masses = select_wall_masses(labels, require_two_contacts=True)
    bridges = []
    for wall_mass in wall_masses:
        contacts = contact_arcs(wall_mass, labels.space_or_outside)
        bridges.extend(
            decompose_by_medial_corridors(wall_mass, contacts, cfg)
        )

    bridges = subtract_virtual_closures_and_openings(bridges, repairs)
    handles = map_ribbons_to_source_handles(bridges, provenance, cfg)
    quality = make_quality_record(chosen, repairs, bridges, handles)

    if quality.bridge_explosion:
        return abstain("EXPLOSION", diagnostics=quality)
    return faces, bridges, handles, quality
```

---

## 3. 벽 과업 적응 설계

### 3.1 공통 평가 단위

P1은 polygon/bridge를 직접 출력하지만, 프로그램의 공통 평가는 per-handle `wall_member(h)`다. 따라서 산출물을 두 층으로 분리한다.

- **표현 층:** face, wall-mass, bridge ribbon. P1의 고유 주장과 topology 오류를 평가한다.
- **호환 층:** ribbon 경계를 구성하거나 interior HATCH를 제공한 원 handle을 `wall_member`로 투영한다. 기존 `fast_score`, CubiCasa SEG-IR, evidence xlsx와 비교할 때만 쓴다.

bridge 집합이 좋아도 handle mapping이 깨지면 제품 호환 성공으로 세지 않는다. 반대로 handle F1이 좋아도 실제 bridge topology가 틀리면 P1의 이론 성공으로 세지 않는다. 이는 T6의 평가 단위 혼동을 피한다.

### 3.2 CubiCasa SEG-IR 벡터축

패킷이 허용한 현황은 5,000도면 전량 변환, train 4,200/val 400/test 400, 벽 선분율 약 11.8%이다. 좌표는 px이고 도면별 축척을 모르므로 50~400mm 같은 절대 prior는 금지한다.

접속 순서는 다음과 같다.

1. `cubicasa_ir`의 line/curve record를 P1 adapter로 읽고 drawing id와 원 element/handle id를 보존한다.
2. Wall 클래스 요소의 모서리를 per-handle truth로 사용한다. room/bridge truth가 직접 주어진다고 가정하지 않는다.
3. 예측 ribbon에 닿는 source handle을 `wall_member`로 역투영해 기존 val PR/F1과 같은 시험지에 올린다.
4. face-only score를 기존 6-feature GBDT에 추가한 `GBDT+face` arm을 별도로 만든다. 추가 feature는 bridge membership, two-space contact, wall-mass width dispersion, separator score, repair dependence다.
5. 레이어/클래스 이름은 feature에서 제거한다. Wall truth는 label로만 사용한다.

기존 다이제스트에서 기하 v1은 val F1 0.2358(P 0.134, R 0.981), HistGradientBoosting은 val P 0.860/R 0.370/F1 0.517/AUC 0.9215, logistic은 F1 0.053이었다. P1이 가져올 수 있는 추가 정보는 “평행한가”가 아니라 “서로 다른 두 공간을 실제로 가르는가”이다. 기대 이득은 두 갈래다.

- v1/GBDT의 false positive인 긴 BoundaryPolygon, Direction, Door/Window, DimensionMark가 한 space 내부 nuisance face라면 제거한다.
- Wall edge가 polyline/arc/fragment로 표현되어 pair feature가 약해도 닫힌 wall-mass topology가 남아 있으면 회수한다.

그러나 Wall 클래스 edge가 room layout을 닫지 않거나 raster-derived SEG-IR의 topology가 불완전하면 P1이 오히려 abstain할 수 있다. 따라서 CubiCasa 성적은 P1의 main E1 판별과 별도로 보고한다.

split은 기존 drawing 단위 train/val/test를 그대로 쓴다. val에서는 개발과 config 선택을 허용하지만, core face config는 먼저 synthetic에서 봉인한다. `GBDT+face`의 학습은 train에서만 하고, test는 방법 선택과 임계값을 모두 봉인한 뒤 단 한 번 실행한다.

### 3.3 FloorPlanCAD 래스터축

패킷 다이제스트상 자산은 5,308장 raster와 wall bbox/segmask이며 vector SVG가 없다. 따라서 “FloorPlanCAD 선단위 wall 라벨”이라는 초기 문구를 그대로 구현할 수 없다. 이 축에서 허용되는 것은 다음 **연구용 전이 프로브**뿐이다.

1. raster linework를 고정된 contour-vectorization adapter로 변환한다.
2. vectorized contour에 P1을 적용한다.
3. 예측 wall ribbon을 원 raster 좌표로 다시 렌더한다.
4. 제공된 wall segmask와 pixel IoU/precision/recall을 계산한다.

handle containment나 CAD line-label 성적을 주장하지 않는다. vectorization 오차와 face 알고리즘 오차를 분리하기 위해 synthetic polygon→raster→vector→polygon round-trip 셀을 먼저 통과해야 한다. bbox는 localization 진단에만 쓰고 pixel mask truth로 대체하지 않는다.

FloorPlanCAD는 NC이고 원 도면 권리도 미해결이라는 패널의 PR-3/T5를 따른다. counsel 서면 확인 전에는 학습, 제품 가중치 탑재, 외부 배포를 하지 않는다. 허가되더라도 이 데이터로 맞춘 hyperparameter를 1.dwg나 실측 145장에 재튜닝하지 않고 전이 결과만 본다.

### 3.4 1.dwg staged DXF 실도면축

실도면에는 도면정의 384개가 있고 E1 divergence top-20이 P1의 cheapest discrimination set이다. 실행 전 CL-A가 다음을 확정해야 한다.

- top-20 선정이 `_score_divergence` 정렬 키의 산물인지 재계산
- LLM이 인용한 handle이 실제 def에 존재하는지
- entity histogram, INSERT 깊이, bbox/단위 상태
- `n_h_ornith=10` 같은 나열 지시 artifact 여부
- 각 def에서 frozen LINE-pair v0의 `n_pairs=0` 재확인

이 감사가 실패하면 P1을 실행해도 지배 이론과 반대 이론을 판별한 것이 아니므로 main cell은 `BLOCKED_UPSTREAM`이다.

감사가 통과하면 synthetic에서 봉인한 face config 하나로 messy top-20을 한 번 실행한다. primary metric은 def별 LLM-handle containment 중앙값이다. LLM은 truth가 아니라 “기존 관측 언어가 보지 못한 후보 위치”를 제공하는 probe다. bridge 수, face 수, dangle, repair 의존, handle provenance를 함께 내며, LLM과 겹치지 않는 bridge를 자동 false positive로 부르지 않는다.

가능하면 entity count, INSERT depth, bbox scale을 맞춘 non-divergent control 20개를 CL-A에서 함께 봉인한다. control은 threshold tuning에 쓰지 않고 “P1이 모든 def에서 무차별 폭발하는가”를 확인한다.

### 3.5 실측 145장과 metamorphic 축

145장은 label-free metamorphic/품질 감사에만 사용한다. top-20 결과를 보고 snap/gap band를 바꾼 뒤 145장에 적용하는 것은 금지한다. top-20 main gate 통과 후 frozen config로 야간 batch를 돌리고 다음만 측정한다.

- rigid/reflect/scale 뒤 provenance bridge-set 불변
- `OPEN_PLAN_INSUFFICIENT`와 `EXPLOSION` 비율
- def당 segment 수에 따른 runtime/peak RAM
- 0-wall sentinel과 all-wall sentinel의 비정상 통과 여부

이는 제품 정확도 주장이 아니라 운영 가능성과 Goodhart 방지 증거다.

### 3.6 누수 방지

- synthetic generator seed는 development/hidden-test로 분리하고 seed manifest를 먼저 봉인한다.
- CubiCasa는 drawing 단위 기존 split을 유지한다. test는 방법당 단발이다.
- 실도면과 synthetic seed를 섞어 threshold를 맞추지 않는다.
- FloorPlanCAD는 가능한 project/원본 group 단위 split을 쓴다. group metadata가 없으면 임의 image split으로 대체하지 않고 `BLOCKED_SPLIT`로 둔다.
- top-20은 divergence로 선택된 forensic set이므로 전체 384개 또는 145장 일반화 성적으로 표현하지 않는다.
- LLM, synthetic, CubiCasa human label, FloorPlanCAD mask를 하나의 “합의 truth”로 평균하지 않는다. proxy별 오류 구조를 별도 보존한다.

---

## 4. 데이터·컴퓨트 요구

### 4.1 필요한 데이터

| 축 | 필요한 입력 | 진리/역할 | 금지 |
|---|---|---|---|
| synthetic wall-face | room polygon, wall-mass polygon, opening, source handle provenance, mutation family | bridge/ribbon/handle 직접 truth | 기존 dimension-only 생성기를 wall truth처럼 사용 |
| 1.dwg top-20 | audited staged DXF def, LLM cited handles, frozen v0 result | main discrimination probe | LLM handle을 사람 truth로 명명 |
| CubiCasa | 기존 SEG-IR train/val/test와 Wall edge label | 외부 per-handle 비교, proxy 독립성 | test 반복 튜닝 |
| FloorPlanCAD | raster, bbox, segmask, group metadata | NC exploratory pixel-mask transfer | CAD handle label 주장, 제품 학습 |
| 실측 145장 | frozen-config geometry와 transform copy | label-free metamorphic/운영 감사 | threshold 재튜닝 |

### 4.2 합성 wall-face generator 요구

현재 `synthetic_truth.py`는 dimension 전용이고 벽 코드가 0이라는 PR-1을 출발점으로 삼는다. 새 generator는 최소한 다음 latent truth를 직접 생성해야 한다.

- room graph와 exterior
- wall-mass polygon 및 pairwise bridge id
- door/window opening void
- T/L/X junction
- taper/arc wall, 불균일하지만 허용되는 폭
- LINE, LWPOLYLINE, ARC, HATCH, nested INSERT로의 표현 변환
- 짧은 gap, overshoot, duplicate, non-wall furniture/dimension/arrow distractor
- 원 latent edge에서 emitted CAD handle로의 provenance map

같은 latent plan을 여러 표현 family로 내보내야 한다. 그래야 “정답 자체가 평행 이중선 prior를 공유한다”는 T1을 검사할 수 있다. hidden mutation family는 config 선택 후에만 공개한다.

### 4.3 로컬 실행 계획

초기 probe는 GPU가 필요 없다.

- **CPU/RAM:** Shapely/GEOS, NumPy, spatial index, 선택적으로 OpenCV raster contour. RAM 64GB 안에서 def/component 단위 streaming.
- **병렬화 단위:** 도면 또는 def 단위 process 병렬. 한 def 내부 GEOS 객체는 process 사이에서 공유하지 않는다.
- **대형 def:** 패킷에는 최대 412,775 선분 병목이 기록되어 있다. connected component 우선 분리, bbox tile+halo, tile boundary provenance stitching을 사용한다. tile 결과가 untiled small-case와 같다는 검증 전에는 대형 결과를 채택하지 않는다.
- **복잡도 감시:** noding은 intersection 수에 민감하고, naive endpoint/gap pairing은 이차 폭발할 수 있다. R-tree radius query로 후보를 제한하고 `candidate_pairs / input_fragments`를 기록한다.
- **cache:** normalized fragment와 noded linework만 content hash로 cache한다. threshold가 face labeling에만 영향을 주면 noding을 재사용한다. 원본을 수정하지 않는다.
- **예상 시간:** cheap synthetic 10장+top-20은 로컬 CPU 수 시간이라는 패킷 예산을 따른다. 아래 셀의 더 세분화된 시간은 제안 예산이며 결과가 아니다.

RTX 5070 Ti 16GB는 core에 불필요하다. FloorPlanCAD contour vectorization을 신경망 기반으로 바꾸는 후속 arm이 생길 때만 별도 승인·실험으로 쓴다.

### 4.4 DGX 계획

DGX Spark/Ornith-35B는 현재 unreachable이고 core에 필요 없다. 초기 P1, CubiCasa face feature 생성, synthetic/metamorphic은 전부 로컬로 끝낸다. DGX가 복구되어도 다음 용도로만 선택적으로 쓴다.

- LLM/VLM 해석 결과의 추가 비교
- 대량 raster vectorization의 후속 배치

DGX 불통은 P1 main probe의 blocker가 아니다. DGX 결과를 face truth나 threshold tuning에 합치지 않는다.

### 4.5 라이선스와 재현성

- geometry engine은 GEOS/Shapely로 고정하고 실행 evidence에 정확한 version, build, license notice를 기록한다. 법률 판단은 counsel 서면으로 닫는다.
- FloorPlanCAD와 CubiCasa 원 도면/label 사용범위는 PR-3에서 별도 확인한다.
- 모든 실행은 config hash, code hash, dataset manifest, engine version, seed, split, 시작/종료 시각, peak RAM을 남긴다.
- 실패도 evidence xlsx에 한 행으로 남긴다. `n_pred=0`을 성공적인 precision으로 해석하지 않는다.

---

## 5. 구현 계획

### 5.1 논리 모듈 골격

패킷은 실제 repository root를 제공하지 않으므로 아래는 **논리적 파일 골격**이다. 구현 시작 시 저장소와 기존 모듈의 실제 경로를 먼저 확인하고, 이름만 보고 존재를 가정하지 않는다.

```text
wall_face/
  schema.py                 # Entity/Face/Bridge/Quality record
  normalize.py              # curve normalization, INSERT world transform
  scale_anchor.py           # homogeneous drawing scale
  noding.py                 # GEOS noding and provenance transfer
  polygonize.py             # polygonize_full + diagnostics
  gap_repair.py             # virtual, auditable closure candidates
  face_features.py          # width, hatch, containment, separator features
  face_label.py             # deterministic fixed-point labels
  bridge_dual.py            # wall-mass contact and pairwise ribbon decomposition
  handle_projection.py      # ribbon -> source handle
  quality.py                # abstention and explosion gates
  metrics.py                # bridge/ribbon/handle/metamorphic metrics
  prereg.py                 # sealed config/split/threshold reader
  cli.py                    # per-drawing/def runner

synthetic_wall_face/
  latent_plan.py            # room graph, wall mass, openings
  emit_entities.py          # LINE/LWPOLYLINE/ARC/HATCH/INSERT variants
  mutations.py              # gaps, overshoots, distractors
  truth_export.py           # bridge/ribbon/handle provenance truth

adapters/
  cubicasa_face_adapter.py
  floorplancad_raster_adapter.py
  staged_dxf_face_adapter.py

tests/
  test_insert_world_transform.py
  test_arc_provenance.py
  test_polygonize_diagnostics.py
  test_virtual_repair_not_a_wall.py
  test_t_junction_bridge_split.py
  test_rigid_scale_equivariance.py
  test_zero_all_wall_sentinels.py
  test_raster_roundtrip.py
  test_tiled_equals_untiled.py
```

### 5.2 기존 하네스 접속점

- **`evidence_grid`:** 각 config×dataset×seed×arm을 한 row로 등록한다. primary/secondary metric, gate status, failure reason, artifact path를 함께 쓴다.
- **`fast_score`:** v1의 frozen baseline을 재현하는 데만 쓴다. P1 face score에 v1 결과를 몰래 feature로 넣지 않는다. `GBDT+face` arm은 명시적인 별도 arm이다.
- **`cubicasa_ir`:** drawing id, entity id, geometry, Wall label을 adapter input으로 쓴다. 좌표를 mm로 해석하지 않는다.
- **`cubicasa_ml`:** 기존 6-feature GBDT와 동일 split/평가기를 재사용하고 face feature 추가 arm만 비교한다. 기존 baseline을 재학습했다면 seed/config 차이를 기록한다.
- **staged DXF:** def와 handle provenance가 보존되는 read-only adapter를 둔다. 원 DWG/DXF를 수정하지 않는다.

### 5.3 구현 단계와 규모

아래는 **개발 추정치**다.

1. **P0 — 계약/fixture(0.5~1 인일):** schema, provenance, sentinel, prereg record.
2. **P1 — generator(2~3 인일):** latent room/wall truth와 representation mutation. PR-1/T2 fidelity gate까지.
3. **P2 — strict arrangement(2~3 인일):** normalization, noding, polygonize diagnostics, simple bridge.
4. **P3 — repair/junction(2~4 인일):** virtual gap repair, T/L bridge decomposition, abstention.
5. **P4 — adapters/evidence(1~2 인일):** CubiCasa, staged DXF, evidence xlsx.
6. **P5 — raster exploratory(1~2 인일, counsel 후):** FloorPlanCAD round-trip과 mask metric.

가장 큰 불확실성은 geometry 자체보다 provenance 보존과 connected poché의 bridge 분해다. 이 둘이 테스트로 닫히기 전에는 top-20을 실행하지 않는다.

### 5.4 증거 산출 계약

실험을 실제 수행할 때는 다이제스트의 “증거 xlsx 의무”를 따른다. workbook은 최소 다음 sheet를 가져야 한다.

- `prereg`: config, threshold, seed, split, freeze timestamp
- `runs`: arm별 aggregate metric과 gate
- `per_drawing`: face/bridge/handle metric, quality status
- `per_bridge`: truth-pred match, ribbon IoU, endpoint match
- `failures`: dangle/cut/invalid/provenance/explosion과 원인
- `metamorphic`: transform별 set equality와 inverse-warp IoU
- `licenses`: dataset/engine clearance 상태

보고서에는 `PASS`뿐 아니라 `FAIL/BLOCKED/INCONCLUSIVE`를 같은 수준으로 기록한다. xlsx와 raw JSONL의 row count/checksum을 검증하고, 요약 수치가 원 row에서 재계산되는 테스트를 둔다.

---

## 6. 실험 셀 정의

### 6.1 실행 순서

```text
E0 생성기·fidelity
        ↓
E1 synthetic 정확도 ──→ E2 metamorphic
        ↓                    ↓
CL-A 감사 완료 ───────→ E3 messy top-20 판별
        ↓
E4 CubiCasa val·proxy 감사 ──→ [모든 gate 봉인] ──→ E6 test 단발

T5 counsel + raster round-trip ──→ E5 FloorPlanCAD NC 탐구
```

E3이 P1의 핵심 판별 셀이다. E4/E5는 외부 전이와 독립성 감사이며 E3 실패를 구제하는 투표가 아니다.

### E0 — PR-1 wall-face 생성기와 T2 fidelity

- **가설:** latent wall/room graph에서 여러 CAD 표현을 내보낸 합성팩이 dimension-only 기존 합성팩보다 divergent-20의 표현 현상을 충실히 포함할 수 있다.
- **데이터:** cheap 단계 10장, 제안 seed `{1101,…,1110}`. 각 latent plan은 최소 두 representation mutation을 갖는다. development와 hidden mutation seed를 분리한다.
- **지표:** entity-family coverage, normalized primitive-length KS, entity-type TV, face-degree/endpoint-gap 분포, truth provenance 완전성, real-vs-synthetic two-sample discriminator(진단).
- **제안 합격선:** LINE/LWPOLYLINE/ARC/HATCH/INSERT와 gap/overshoot/distractor family가 모두 존재하고, truth provenance가 완전하며, 사전 지정 핵심 분포의 `KS_max≤0.30` 및 `TV≤0.20`. 이 값들은 제안 prereg band다. 기존 다이제스트의 B1 `KS 0.5792, TV 0.265`는 현 generator가 이 문턱을 통과했다는 증거가 아니다.
- **킬 조건:** truth가 emitted parallel double-line에서 역으로 만들어져 counter-theory와 독립적이지 않음, hidden mutation에서 provenance 손실, 또는 fidelity band 실패. 실패하면 E1 이후를 중단한다.
- **예산:** 로컬 CPU 2~4시간 생성/검사 + 구현 2~3 인일, GPU 없음.
- **시드 계획:** generator seed와 mutation seed를 별도 기록. hidden seed는 config freeze 전 결과를 보지 않는다.

### E1 — synthetic bridge/ribbon 정확도

- **가설:** parallel feature 가중치 0에서도 face-first가 known bridge를 회수한다.
- **arm:** strict face-only, repaired face-only, repaired+parallel-ablation, LINE-pair v0.
- **지표:** bridge endpoint exact match, ribbon IoU matching 후 bridge recall/precision, per-handle P/R/F1, virtual-repair 의존, bridge-count ratio, 0-wall/all-wall sentinel.
- **제안 합격선:** 패킷 prereg를 따라 synthetic recall@벽리본 `≥0.90`. 추가 안전 gate로 모든 sentinel 의미가 정확하고, 예측 bridge 수 중앙값이 truth의 두 배를 넘지 않으며, primary face-only arm이 합격해야 한다.
- **킬 조건:** face-only가 0.90 미만, all-wall 예측으로 recall을 얻음, repair edge가 wall handle로 유출, 또는 parallel-ablation만 합격.
- **예산:** cheap 10장은 CPU 1시간 이내 목표, full hidden pack은 야간 8시간 상한 제안. peak RAM 32GB soft cap, 48GB hard stop 제안.
- **시드 계획:** E0 development seed로 config 선택 후 hidden seed를 한 번 평가. 실패 후 hidden seed에 재튜닝하지 않고 새 prereg cycle로 간다.

### E2 — rigid/scale/metamorphic 불변

- **가설:** scale-homogeneous threshold와 provenance mapping 때문에 bridge 의미가 전역 변환 뒤 보존된다.
- **변환:** 원본, translation, rotation, reflection, uniform scale. 제안 scale factor는 `{0.1, 1, 10}`이며 단위 변경과 수치 안정성을 동시에 압박한다.
- **지표:** inverse-transform 뒤 bridge provenance-set Jaccard, endpoint pair equality, ribbon IoU, quality-status 전이, handle score 최대차.
- **제안 합격선:** provenance bridge set Jaccard `1.0`, endpoint pair exact equality, inverse-warp ribbon IoU `≥0.99`. 수치는 제안 gate다. 부동소수 tolerance는 config에 봉인한다.
- **킬 조건:** scale에서 systematic bridge 증감, transform에 따라 repair tie-break가 달라짐, 또는 0-wall sentinel이 변환 후 wall을 생성. 기존 다이제스트의 B4 scale arm 0.7624 strict FAIL은 P1이 특히 넘어야 할 선행 실패다.
- **예산:** synthetic 10장×변환 battery CPU 1~2시간. E3 통과 뒤 실측 145장은 로컬 야간 batch.
- **시드 계획:** geometry seed는 E1과 같고 transform parameter list는 prereg에 고정. transform별 새 random noise를 넣지 않는다.

### E3 — messy divergent-20 discrimination (T27, 핵심)

- **선결:** CL-A T3/T4/T8 감사 완료, handle 실재성 확인, sorting artifact 재계산, frozen v0에서 `n_pairs=0` 재확인.
- **가설:** LINE-pair v0가 계속 0인 def에서 face bridge가 LLM-cited handle의 의미 있는 부분을 회수한다.
- **arm:** frozen LINE-pair v0, strict face-only, repaired face-only. parallel/name 가중치 arm은 진단용이며 main 판정에서 제외.
- **지표:** def별 LLM-handle containment, 중앙값과 drawing-level bootstrap interval, bridge/LLM-handle count ratio, repair 비율, dangle/cut/invalid, abstention, matched control의 explosion.
- **VIABLE:** synthetic E1/E2를 동시에 통과하고, top-20 containment 중앙값 `≥0.40`이며, LINE-pair는 재확인 후 계속 0. 또한 중앙값 bridge 수가 LLM handle 수의 10배를 넘지 않는다.
- **약화/킬:** containment 중앙값 `<0.15`이면 관측 언어 교체 가설 약화. face 추출이 open/noisy linework에서 붕괴하고 def당 median bridges가 LLM handle 수의 `>10×`이면 기각 후보. `0.15~0.40`은 성공으로 올리지 않고 `INCONCLUSIVE`다.
- **outcome A:** face bridge가 회수하고 LINE-pair가 0 → `kills: reigning`.
- **outcome B:** face도 거의 0이거나 과다분할로 metric이 무의미 → `kills: counter`.
- **예산:** 로컬 CPU 수 시간, hard wall-clock 8시간 제안. 한 def가 60분을 넘으면 timeout failure로 기록하고 전체를 억지로 완료하지 않는다.
- **시드 계획:** deterministic. tie-break salt를 config에 고정하며 여러 salt 중 좋은 것을 고르지 않는다. bootstrap seed 하나를 봉인하고 raw per-def 값도 전부 공개한다.

### E4 — CubiCasa val 및 proxy 독립성 감사

- **가설 1:** face topology는 기존 6 geometry feature에 없는 조건부 정보를 준다.
- **가설 2:** synthetic/LINE-pair/face가 같은 평행 prior의 복제물이 아니라, human Wall label에 대해 서로 다른 오류 구조를 보인다.
- **arm:** v1 `fast_score`, 기존 6-feature GBDT, deterministic face-only, GBDT+face, shuffled-label control.
- **지표:** val per-handle P/R/F1/AUC, drawing-bootstrap ΔF1, v1/GBDT false-negative에서 face의 conditional precision/recall, 오류 Jaccard/phi, representation family별 성적, name-mask ablation.
- **제안 합격선:** GBDT+face가 기존 GBDT val F1 0.517 대비 absolute `≥0.03` 개선하고 paired bootstrap lower bound가 0보다 크거나, 개선폭이 작아도 v1/GBDT zero-candidate 구간에서 사전등록한 conditional precision `≥0.50`로 고유 정답을 회수한다. 이 두 수치는 제안 band다.
- **독립성 gate:** face와 LINE-pair prediction Jaccard가 `≥0.90`이고 error phi도 `≥0.90`이면 독립 proxy로 합산하지 않는다. 단, 상관이 낮다는 사실만으로 face가 정확하다고 말하지 않고 human label metric을 함께 요구한다.
- **킬 조건:** shuffled control이 비정상 성능, layer/class leakage, drawing split 위반, 또는 face feature가 val 개선 없이 기존 오류를 그대로 복제.
- **예산:** feature 생성 로컬 야간 8~16시간 제안, GBDT 학습은 기존 64GB 경로 재사용, GPU/DGX 없음.
- **시드 계획:** 기존 split 고정. GBDT seed `{17, 29, 43}`을 prereg하고 평균과 최악 seed를 보고한다. val을 본 뒤 seed를 추가하지 않는다.

### E5 — FloorPlanCAD raster transfer (NC, 탐구)

- **선결:** T5 counsel 서면, project/group split 확보, synthetic raster round-trip 통과.
- **가설:** raster contour로 변환된 경우에도 face ribbon이 wall segmask와 공간적으로 겹친다.
- **arm:** 고정 contour-vectorizer+face-only, contour-vectorizer+LINE-pair. bbox는 진단만.
- **지표:** pixel ribbon IoU/P/R, connected component over/under-segmentation, vectorization 실패율, raster round-trip 오차.
- **제안 합격선:** 제품 gate로 쓰지 않는다. 탐구 보고 조건은 round-trip IoU `≥0.95`와 provenance에 해당하는 contour mapping 완전성이다. 이 수치는 제안된 계측 신뢰성 gate다.
- **킬/중단:** counsel 미해결, group split 부재, SVG/handle label이 없는데 line-level 성적을 요구, 또는 vectorizer 오차가 face 오차보다 커 분리가 불가능.
- **예산:** 허가 후 소규모 holdout CPU 4~8시간. 전체 5,308장 batch는 탐구 결과가 해석 가능할 때만 별도 승인.
- **시드 계획:** deterministic contour parameters를 synthetic에서 봉인. FloorPlanCAD 결과로 1.dwg hyperparameter를 변경하지 않는다.

### E6 — CubiCasa test 단발

- **선결:** E0~E4 prereg gate, license clearance, 선택 arm·threshold·seed aggregation·xlsx schema 봉인. E5는 main test의 선결이 아니다.
- **가설:** val에서 선택된 하나의 face arm이 untouched test에서도 baseline 대비 이득을 유지한다.
- **실행:** 기존 GBDT baseline과 선택한 face arm을 test 400장에 각각 한 번 평가한다. 실패한 run을 고쳐 같은 방법 이름으로 재실행하지 않는다. 코드/환경 장애면 `VOID_TECHNICAL` 근거를 남기고 Paul의 새 prereg 승인 후 별도 run id로만 재개한다.
- **지표:** per-handle P/R/F1/AUC, drawing-paired ΔF1, representation family error, abstention, runtime/RAM.
- **제안 합격선:** 선택 face arm의 test ΔF1이 baseline 대비 `≥0.03`이고 paired interval 하한이 0보다 크며, shuffled control은 사전등록된 chance 진단을 벗어나지 않아야 한다. 수치는 test 열람 전 봉인할 제안값이다.
- **킬 조건:** ΔF1 gate 실패, recall을 bridge explosion으로 산 경우, test 후 threshold 변경 필요, 또는 split/leakage 발견.
- **예산:** 로컬 야간 1회, DGX 없음.
- **시드 계획:** 학습 seed는 E4에서 미리 정한 집계 규칙으로 하나의 model artifact를 선택한다. test seed shopping 금지.

### 6.2 공통 통계·판정 규칙

- bootstrap 단위는 handle이 아니라 drawing/def다.
- undefined containment, abstention, timeout을 0이나 1로 몰래 치환하지 않는다. 분모와 실패 수를 별도 보고한다.
- 모든 threshold는 해당 평가 set을 보기 전에 prereg sheet에 봉인한다.
- multiple arm 결과는 primary/secondary를 미리 구분한다. primary가 실패했는데 secondary 하나가 좋아도 `PASS`로 바꾸지 않는다.
- 실패한 synthetic fidelity, counsel, CL-A audit는 downstream cell을 `BLOCKED`로 만들며, 빈 결과를 counter-theory kill로 세지 않는다.

---

## 7. red team 티켓 응답

패킷에는 티켓 34건의 전문이 아니라 번호와 일부 맥락만 있다. 따라서 아래는 제공된 맥락에 걸리는 티켓만 지목하며, 전문이 없는 항목의 세부 요구를 만들어내지 않는다.

| 티켓/리스크 | P1에 미치는 영향 | 응답 | 종료 조건 |
|---|---|---|---|
| **T1 — proxy 독립성(최우선)** | 합성·face·LINE-pair가 같은 double-line prior면 삼각측량이 아님 | 같은 CubiCasa drawing에서 human Wall label, LINE-pair, face의 오류 교차표를 E4로 측정. latent truth에서 여러 표현을 파생해 합성 truth가 emitted pair에 종속되지 않게 함 | per-drawing 오류 구조와 label metric이 evidence에 존재. 독립이 아니면 합산 주장 철회 |
| **T2 — 벽 생성기 부재/fidelity** | 현재 dimension-only generator로 synthetic recall을 말할 수 없음 | E0를 hard gate로 두고 generator부터 구현. divergent-20 표현 family와 분포 fidelity를 검사 | E0 pass 전 E1/E3 금지 |
| **T3 — divergence 재계산/sorting artifact** | top-20 자체가 정렬 키 산물이면 main probe가 오염 | CL-A가 top-20+control을 재계산하고 선택 manifest를 봉인 | 감사 보고와 frozen set id |
| **T4 — Ornith 원시 조달/나열 지시 artifact** | LLM handle containment 분자가 잘못될 수 있음 | raw cited handle의 실재성, 중복, 나열 지시 영향을 감사. 불명 handle은 제외가 아니라 invalid로 기록 | 모든 main def의 handle provenance가 확인되거나 E3 blocked |
| **T8 — CL-A 관련 hard prerequisite** | 패킷에 정확한 티켓 전문은 없음 | 전문을 추정하지 않는다. 패널이 CL-A의 hard prerequisite로 둔 범위가 닫혔다는 확인만 요구 | red-team 원문에서 T8 closed/accepted 표기 확인 |
| **T5 — FloorPlanCAD/CubiCasa 권리와 NC** | 외부 label 학습/배포의 법적 kill risk | counsel 서면 전 E5와 신규 외부학습 중단. engine license도 버전별 확인 | dataset별 허용 행위, 산출물 배포범위, attribution 서면 |
| **T6 — per-handle 대 집합-조립 단위** | bridge 성공과 handle F1을 섞으면 보상 해킹 | 표현 층과 호환 층을 별도 산출·별도 gate로 유지 | bridge endpoint/ribbon/handle sheet가 분리 |
| **T7 — metamorphic 0벽 탐지기 문제** | violation-only metric은 빈 탐지기를 통과시킴 | E1 recall과 0-wall/all-wall sentinel을 E2 불변성과 동시 gate | recall≥0.90 및 sentinel 의미 보존 |
| **T9/T21 — v0 baseline 선계측** | P1 gain을 오래된/다른 v0와 비교할 위험 | 같은 frozen top-20에서 `fast_score`/LINE-pair config hash와 `n_pairs` 재실행 | baseline config와 raw per-def 출력 봉인 |
| **T10/T23 — graph/adjacency 완전성(조건부 관련)** | P1도 dual adjacency를 쓰므로 누락된 기존 Graph IR을 재사용하면 오류 | 기존 Graph IR adjacency를 truth로 쓰지 않고 GEOS face에서 독립 재구성. synthetic known adjacency와 비교 | atomic face/dual unit test와 provenance coverage pass |
| **T16 — 절대 대 상대 gap band** | mm 대역은 CubiCasa px와 unit scale에서 깨짐 | 모든 primary 길이 knob를 `s(D)` 상대값으로 둠. absolute-mm arm은 비교 진단만 | E2 uniform-scale exact gate |
| **T24 — pixel↔handle 역투영** | FloorPlanCAD vectorization과 mask projection이 오차를 숨김 | synthetic polygon→raster→vector→polygon round-trip을 E5 선결로 둠. raster 축에서 handle 성적 주장 금지 | round-trip gate와 pixel coordinate manifest |
| **T27 — messy divergent-20에서 cheapest probe** | 합성 성공만으로 open/messy 실도면을 회피할 위험 | E3을 핵심 판별 셀로 두고 containment/10× explosion/abstention을 사전등록 | E3 A/B/INCONCLUSIVE 중 하나를 raw evidence로 판정 |
| **T34 — load-bearing 인용 미실행** | 문헌 이름이 실험 증거처럼 사용될 위험 | 모든 문헌은 lineage로만 사용하고 `experiment_executed:false` 취급. 본 셀 결과만 load-bearing evidence로 허용 | 인용별 evidence status와 실제 run id 구분 |
| **R12 — 후보 폭발/권리 kill risk** | 412,775 선분에서 noding/gap pair와 bridge가 폭발 가능 | R-tree, component/tile, candidate ratio, timeout, `>10×` kill을 적용. 권리는 T5로 분리 | runtime/RAM/explosion sheet와 counsel |
| **R16 KR2/KR4 — open plan/messy 충돌** | face가 닫히지 않으면 counter-theory가 구조적으로 실패 | strict/repaired/abstain을 분리하고 virtual repair를 벽으로 세지 않음. E3이 정면 판정 | open-plan 실패율과 repair dependence 공개 |

수용하는 잔여 위험도 있다. 완전히 열린 plan, elevation/단면이 섞인 def, 3D projection, self-intersecting spline, 포셰가 전혀 없는 centerline-only 표현은 E3에서 높은 abstention을 낼 수 있다. 이를 숨기지 않으며, 해당 분포가 실사용의 주류라면 P1은 본선이 아니라 특정 representation family용 보조 후보로 내려간다.

---

## 8. 인접 제안과의 관계 및 사망 조건

### 8.1 병합 가능한 지점

- **CL-A E1 법의학 감사:** P1 main set의 유효성을 보장하는 hard prerequisite다. 병합하되 P1 점수기는 감사 결과를 만들지 않는다.
- **CL-B 커버리지-완전 결정론 v1:** INSERT world transform, LWPOLYLINE/ARC 정규화, unit anchor는 공용 front-end로 병합 가능하다. 이후 후보 언어는 분리한다. CL-B는 선/쌍 후보, P1은 face/dual bridge다.
- **CL-C wall synthetic truth:** P1의 E0/E1과 사실상 같은 기반이다. generator는 공용으로 만들되 LINE-pair 친화 표현만 생성하지 않는다.
- **CL-D metamorphic battery:** transform 생성과 evidence schema를 그대로 공용화한다. P1은 bridge-set equality와 non-empty recall gate를 추가한다.
- **CL-E truth-source 교차요인:** CubiCasa human label×LINE-pair×face 오류 구조를 한 cell로 병합할 수 있다. proxy의 평균 점수 대신 off-diagonal error를 본다.
- **CL-F 고전ML 사다리:** `GBDT+face`로 face topology feature의 조건부 가치를 검사한다. deterministic face-only가 core이고 learned combination은 후속 arm이다.
- **CL-G raster/VLM:** FloorPlanCAD round-trip adapter와 ribbon mask를 공유할 수 있으나, P1은 VLM이나 frontier API에 의존하지 않는다.
- **CL-I 관례 prior:** layer/name feature는 audit-only ablation으로만 접속한다. primary P1 score는 0이다.
- **CL-K anti-silver:** P1은 silver를 학습 truth로 쓰지 않으므로 자연스러운 anti-silver arm이다. LLM handle은 E3 probe 분자이며 사람 label이 아니다.

### 8.2 차별점

CL-B가 “더 많은 entity를 선분 후보 언어로 정상화”하는 포괄성 개선이라면, P1은 후보 생성의 단위를 선분에서 face와 bridge로 바꾼다. 둘의 차이는 weight가 아니라 실패 모드다.

- CL-B는 open linework에서도 후보를 낼 수 있지만 긴 평행 비벽 구조에 계속 유혹될 수 있다.
- P1은 닫힌 topology와 두-space contact가 있을 때 강하지만 open plan에서 정직하게 abstain해야 한다.
- CL-B가 zero-pair를 회수하면 더 싼 reigning-language 확장이므로 P1의 필요성이 줄어든다.
- P1이 LINE normalization 뒤에도 남는 zero-pair를 회수하고 교란을 줄일 때만 독립 가치가 있다.

### 8.3 이 제안이 죽어야 하는 조건

다음 중 하나면 P1을 본선 후보에서 죽이거나 명시적으로 park한다.

1. **합성 실패:** fidelity를 통과한 synthetic wall-face에서 face-only recall@ribbon이 0.90 미만이다.
2. **관측 언어 위장:** `β_parallel=0` arm은 실패하고 parallel 보조 arm만 성공한다.
3. **변환 실패:** rigid/scale 뒤 provenance bridge 집합이 보존되지 않는다. 특히 기존 scale 실패를 재현한다.
4. **messy 현실 실패:** audited top-20 containment 중앙값이 0.15 미만이다.
5. **Goodhart 폭발:** top-20에서 def당 median bridges가 LLM handle 수의 10배를 넘거나 matched control에서도 무차별 폭발한다.
6. **과도한 repair 의존:** strict face가 거의 없고 가상 closure가 결과 대부분을 만들어 opening과 wall을 구분할 수 없다.
7. **provenance 실패:** ribbon은 보이지만 원 CAD handle로 안정적으로 역투영할 수 없어 공통 시험지에 오르지 못한다.
8. **운영 실패:** component/tile 전략 뒤에도 관측된 대형 def 규모에서 RAM/시간 hard stop을 반복한다.
9. **기존 방법에 흡수:** CL-B normalization 또는 기존 GBDT가 같은 zero-pair handle을 더 싸고 안정적으로 회수하며 face feature가 조건부 이득을 주지 않는다.
10. **권리/평가 불능:** 외부셋 권리가 닫히지 않고 synthetic와 1.dwg만으로도 proxy 독립성을 입증할 수 없다. 이 경우 제품 채택이 아니라 로컬 연구 프로브로만 남긴다.

### 8.4 최종 판정표

| 관측 | 판정 | 후속 |
|---|---|---|
| E0/E1/E2 pass, E3 containment ≥0.40, explosion 없음 | `kills: reigning` — LINE-쌍 관측 언어가 불충분 | CL-B와 dual-track, CubiCasa val/test로 제품 가치 확인 |
| E1 pass지만 E3 0.15~0.40 또는 abstention 다수 | `INCONCLUSIVE` | representation family별 실패를 분해하고 threshold 재튜닝 없이 새 prereg 제안 |
| E3 containment <0.15 또는 >10× explosion | `kills: counter` — face-first P1 기각 후보 | CL-B/GBDT 중심으로 복귀, 실패 evidence 보존 |
| CL-A/T2/T5 등 선결 미해결 | `BLOCKED` | 결과를 만들지 않고 해당 티켓 owner에게 반환 |

P1의 최소 승리는 “멋진 face 그림”이 아니다. synthetic truth에서 맞고, 변환에 흔들리지 않으며, audited messy zero-pair def에서 원 handle provenance를 가진 bridge를 제한된 수로 회수해야 한다. 그 세 조건을 동시에 만족하지 못하면 관측 언어 교체 주장은 폐기한다.

DOSSIER_COMPLETE: feyerabend_P1
