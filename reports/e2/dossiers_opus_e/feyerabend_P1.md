# E2 방법론 심층 도시에 — feyerabend_P1

**제안**: P1 — 면(face)/포셰 유도 벽. 평행 LINE 쌍이라는 *관측 언어(observation language)* 를 폐기하고,
닫힌 면(face)을 먼저 세운 뒤 **두 면을 가르는 두께 있는 공유 경계(dual bridge)** 로 벽을 정의한다.
**좌석**: feyerabendian_dissenter (Phase A 블라인드석) · **패널 클러스터**: CL-J.
**한 줄 논지**: "LLM 고확신 ∧ n_pairs=0"은 탐지기의 실패가 아니라 *관측 언어의 실패* 다 — 벽을 평행쌍으로만
"볼 수 있게" 만든 게이트가 POLYLINE·블록·비평행 조각으로 그려진 벽 앞에서 구조적으로 0을 뱉는 것이다.

> **읽는 이를 위한 용어 약속** (이 문서에서 처음 쓰는 내가 지은 말은 등장 즉시 푼다):
> - **관측 언어(observation language)** = "무엇을 벽으로 *셀 수 있는가*"를 규정하는 측정 규칙. 지금 시스템의
>   관측 언어 = "평행한 두 LINE이 두께 대역 안에서 겹치면 벽 후보 1개".
> - **면(face)** = 선들이 서로 잘려 만든 *닫힌 다각형 셀*. 방(room)일 수도, 벽 사이의 빈 띠(cavity)일 수도, 잡음일 수도.
> - **dual bridge(쌍대 교량)** = 방-인접 그래프(dual graph)에서 두 방-면을 잇는 변(edge). 그 변에 두께를 입힌 것이
>   곧 벽. "방이 먼저, 벽은 방들 사이의 다리"라는 뒤집힌 정의의 핵심 대상.
> - **포셰(poché)** = 건축 도면에서 벽 *속을 칠해* 실(void)과 고체(mass)를 구분하는 관례. 도면에서는 HATCH/솔리드 채움으로 나타남.
> - **containment(포함율)** = LLM이 벽이라 지목한 핸들 집합이 face-bridge가 회수한 핸들 집합에 얼마나 담기는가(∩/LLM).

---

## 0. 이 도시에가 인용할 수 있는 사실의 출처 규율

계약상 **수치 인용은 이 패킷의 다이제스트(2026-07-18 세션 도구 출력)에서만** 한다. 문헌·소프트웨어·수학은
일반 지식으로 서술하되 확신이 낮은 인용은 `[요검증]`으로 표기한다. 아래 두 수치 불일치는 평균하지 않고 표면화한다(R9):

- **실측 도면 수**: 다이제스트 본문은 `1.dwg staged DXF, 도면정의 384개`라 한다. 반면 제안 원문·패널 큐는
  `실측 145장`을 반복한다(예: "합성 시드와 실측 145장 분리", "대량 145장 재측정"). **이 도시에는 다이제스트를
  권위값으로 삼아 384를 벽 과업 모집단 크기로 쓰고, 145는 벽-보유(또는 필터링된) 부분집합일 가능성으로 `[요검증]`
  표기**한다. 실행 전 이 둘의 관계(384 전체 vs 145 부분)를 CL-A 감사에서 확정해야 한다.

---

## 1. 이론적 근거·선행연구

### 1.1 메타 근거 — 관측의 이론적재성(theory-ladenness), 이 좌석의 존재 이유

이 제안의 뿌리는 기법이 아니라 인식론이다. **관측은 이론에 물든다**는 명제 — N.R. Hanson의
*Patterns of Discovery*(1958)와 Feyerabend *Against Method*(1975), Kuhn *The Structure of Scientific
Revolutions*(1962)의 공통 축 [일반 지식] — 는 "무엇을 데이터로 셀 수 있는가"가 이미 이론 선택이라고 말한다.
E2의 현행 관측 언어는 `n_pairs`(평행 이중선 개수)다. 그러면 "벽이 있다"는 곧 "평행쌍이 있다"로 정의되고,
평행쌍이 없는 벽은 관측 불가능해진다 — 데이터가 아니라 *측정 규칙*이 0을 만든다. 이것이 이 좌석의 핵심 반문이며,
다이제스트의 `dissolved_fact`("LLM 고확신 ∧ n_pairs=0"의 재해석)와 정확히 맞물린다.

이 제안은 그래서 "더 나은 탐지기"가 아니라 **경쟁하는 관측 언어**를 제시한다. 두 언어를 같은 시험지(divergent-20)에
올려 어느 쪽이 현상을 더 많이 *볼 수 있는가*를 판별하는 것이 목적이다(§6의 판별 실험).

### 1.2 기하 계보 — 평면 arrangement, DCEL, polygonize

핵심 자료구조는 **평면 arrangement(planar arrangement)** 와 그 저장 형식인 **DCEL(Doubly-Connected Edge
List)** 이다 [일반 지식 — de Berg 외, *Computational Geometry*; CGAL `Arrangement_2` `[요검증: 정확한 클래스명]`].
선분·곡선 집합을 서로 자르면 평면이 정점(vertex)·변(edge)·면(face)으로 분할되고, 각 변은 좌/우 두 면을
반쪽변(half-edge)으로 소유한다. **벽이 두 방을 가르는 변**이라는 정의는 이 half-edge 이중성 위에서 자연스럽다.

실무 엔진은 **GEOS/JTS의 Polygonizer** 와 그 파이썬 래퍼 **Shapely `polygonize` / `polygonize_full`** 이다
[일반 지식]. `polygonize`는 *완전히 노딩된(noded, 모든 교차점에서 잘린)* 선망을 받아 닫힌 다각형 집합을
만든다. `polygonize_full`은 (polygons, dangles, cut edges, invalid rings) 4종을 돌려주어 **어디서 위상이
깨졌는지**를 그대로 노출한다 — 이 실패 노출이 §6 kill 조건 계측의 기반이다.

**라이선스 주의(패널 T27이 명시 요구)**: 엔진은 **GEOS(LGPL)** 계열을 쓴다. LGPL은 GPL과 달리 파생물 전체를
전염(viral)시키지 않으므로 라우터의 "LibreDWG는 GPL sidecar-only" 정책에 걸리지 않는다. Shapely는 BSD.
**GPL 계열(예: 일부 CGAL 상용 라이선스 조건)은 제품 탑재 경로에서 회피**한다 `[요검증: CGAL 라이선스 경로]`.

### 1.3 건축 표상 계보 — figure-ground(도-지), 포셰, 공간구문

"방이 먼저, 벽은 방 사이"라는 역전은 건축 표상의 오래된 관점이다. **Nolli map**(Giambattista Nolli, 로마,
1748) [일반 지식]은 고체(벽·건물)를 검게, 공(公)적 공(void)을 희게 칠한 **도-지(figure-ground)** 도면의 원형이다.
포셰(poché)는 바로 이 "고체를 칠하기" 관례다. 도면이 포셰를 쓰면 벽은 *채워진 띠 면(filled ribbon face)* 으로
직접 드러난다. **공간구문(space syntax)**(Hillier & Hanson, *The Social Logic of Space*, 1984 [일반 지식])의
방-인접 그래프는 이 제안의 dual graph와 동형이다 — 방이 노드, 공유 벽이 변.

### 1.4 인접 컴퓨팅 계보 — 방 분할·플로어플랜 벡터화

- **로보틱스의 방 분할(room segmentation)**: 점유격자(occupancy grid)에서 방을 나누는 문제. Voronoi·형태학
  ·거리변환 기반 기법 총설 — Bormann 외, "Room Segmentation: Survey, Implementation, and Analysis"
  `[요검증: ICRA 2016]`. "벽에서 방을 얻는다"의 역방향 지식이 풍부하고, 우리는 그 역(방↔벽 dual)을 활용한다.
- **플로어플랜 래스터→벡터**: "Raster-to-Vector: Revisiting Floorplan Transformation"(Liu 외) `[요검증: ICCV
  2017]` — junction 검출 + 정수계획으로 방·벽을 복원. **FloorPlanCAD**(Fan 외) `[요검증: ICCV 2021]` = 우리가
  가진 데이터셋의 원 논문(벡터 CAD panoptic symbol spotting). **CubiCasa5K**(Kalervo 외) `[요검증: SCIA 2019]`
  = 외부 진리셋의 원 논문.
- **중심선/골격**: 중심선 복원은 **medial axis transform** 또는 **straight skeleton**(Aichholzer & Aurenhammer)
  [일반 지식]으로 얻는다 — 단, 이 제안은 중심선을 *출력*으로 두고 방-면을 *입력*으로 두는 점에서 R16과 방향이 반대다.
- **면 형상 특징**: 면이 방인지 벽-띠인지 가르는 조밀도 지표로 **Polsby–Popper 조밀도**(4πA/P²) [일반 지식,
  정치 선거구 획정에서 유래 `[요검증: 이 도메인 표준성]`]를 쓴다.

### 1.5 이 계보가 E2에 주는 것 (반증 가능한 형태로)

위 계보의 공통 함의는 하나다: **"벽=평행쌍"은 벽의 한 *구현체* 일 뿐 정의가 아니다.** 벽의 위상적 정의는
"두 면(또는 면과 외부)을 가르는 경계"이고, 평행쌍은 그중 double-line 관례에서만 성립한다. 그러므로 POLYLINE·
블록·ARC·짧은 갭으로 그려진 벽도 *면 위상 안에서는* 벽으로 승격될 수 있다 — 이것이 반증 가능한 핵심 주장이며,
§6 C-J2가 divergent-20에서 참/거짓을 가른다.

---

## 2. 알고리즘 정확 스펙

### 2.1 입력·출력 계약

```
입력  D : 도면정의 IR
        entities = [ {handle, type ∈ {LINE,LWPOLYLINE,ARC,SPLINE,INSERT,HATCH,...},
                      geom(월드좌표), layer, block_ref?} , ... ]
        units : 도면 단위(mm/px/미상) — CubiCasa는 px(축척 미상)
출력  W : 벽 리본 집합
        [ {ribbon_id, geom(polygon 또는 centerline),
           member_handles ⊆ D.handles,   # 프로비넌스: 이 리본을 구성한 원 엔티티들
           width_est, width_rel,          # 절대/상대(치수 정박) 두께
           poche: bool, sep_faces: (fL,fR), score } , ... ]
```

`member_handles`는 이 방법의 사활이다. containment 지표(§6)와 CL-E 동일-def 불일치 감사가 전부
"어느 원 핸들이 벽인가"의 집합 비교이므로, 폴리곤이 아니라 **핸들 프로비넌스**를 1급 산출로 둔다.

### 2.2 파이프라인 (6단계 의사코드)

```python
def face_wall(D, H):   # H = 하이퍼파라미터
    # --- Step 0. 정규화 & 노딩 (CL-B 프론트엔드와 공유; feyerabend P6 INSERT 전개 의존) ---
    segs = []
    for e in D.entities:
        if e.type == "INSERT":         segs += unfold_block_to_world(e)     # P6: 월드좌표 전개
        elif e.type == "LWPOLYLINE":   segs += explode_polyline(e)
        elif e.type in ("ARC","SPLINE","CIRCLE","ELLIPSE"):
                                        segs += tessellate(e, chord_tol=H.eps_arc)
        elif e.type == "LINE":         segs += [e]
        # HATCH는 경계로 쓰지 않고 §Step2 포셰 신호로만 보관
    prov = build_provenance_index(segs)         # seg → 원 handle 역참조 (STRtree)
    lw   = snap_and_close_gaps(segs, snap=H.snap, gap=H.gap_close)  # 갭/오버슈트 봉합
    noded = unary_union(MultiLineString(lw))    # GEOS 노딩: 모든 교차에서 분할

    # --- Step 1. 면 추출 (polygonize) ---
    faces, dangles, cuts, invalid = polygonize_full(noded)   # 실패도 반환
    if len(faces) > H.max_faces: return DEGENERATE("face explosion")  # 폭발 가드

    # --- Step 2. 면 분류: room / wall-cavity / noise ---
    for f in faces:
        A, P = area(f), perimeter(f)
        f.compact   = 4*pi*A / (P*P)                    # Polsby-Popper
        f.aspect    = min_rot_rect_aspect(f)
        f.width     = 2 * neg_buffer_depth(f)           # 침식 깊이 = 국소 폭(중심선 대용)
        f.poche     = overlaps_any_hatch_or_solid(f, D) # 포셰 신호
        f.cls = classify_face(f, H)                     # v0=규칙 / v1=GBDT (§Step2b)

    # --- Step 3. 면-인접 dual & 벽 승격 ---
    Gd = adjacency_dual(faces)   # 노드=room-face(+외부), 변=공유경계
    W = []
    for f in faces:
        if f.cls == "wall_cavity":              # (a) double-line/포셰: 벽 = 얇은 띠 면 자체
            W.append(ribbon_from_cavity(f, prov))
    for (fa, fb, shared) in Gd.shared_edges():  # (c) single-line: 벽 = 두 방의 공유 변
        if is_room(fa) and is_room(fb) and no_cavity_between(fa,fb):
            W.append(ribbon_from_edge(shared, prov, width=infer_width(fa,fb,H)))

    # --- Step 4. 핸들 프로비넌스 매핑 ---
    for w in W:
        w.member_handles = prov.handles_covering(w.geom, tol=H.snap)

    # --- Step 5. 과다분할·상대두께 정리 ---
    W = merge_collinear_ribbons(W, H)           # 조각난 리본 병합
    for w in W: w.width_rel = w.width_est / local_dim_scale(w, D)  # feyerabend P2 정박
    return W
```

`classify_face`(Step 2b)의 두 버전:
- **v0 규칙**: `wall_cavity ⇐ (aspect ≥ τ_aspect) ∧ (w_min ≤ width ≤ w_max) ∧ ¬(A ≥ τ_room_area ∧ compact ≥ τ_compact)`;
  `room ⇐ (A ≥ τ_room_area) ∧ (compact ≥ τ_compact)`; 그 외 noise.
- **v1 학습**: 면 특징 벡터 → 이진분류(벽-띠 여부), 손실 = 가중 BCE. 단 **면-특징은 CubiCasa GBDT에 열로 주입**하는
  경로(§3.1, C-J4)가 더 싸고 직접적이라, 초기엔 v0 규칙 + GBDT-열-주입을 우선한다.

### 2.3 하이퍼파라미터 공간

| 이름 | 의미 | 초기 탐색역 | 비고 |
|---|---|---|---|
| `eps_arc` | ARC/SPLINE 현 허용오차 | 도면 대각의 1e-4~1e-3 | 상대값(축척 미상 대응) |
| `snap` | 끝점 스냅 | 실측 6mm(다이제스트 값) / px는 상대 | 탐지기 v1의 snap 6mm 승계 |
| `gap_close` | 갭/오버슈트 봉합 | 0 ~ 2·snap | **messy 붕괴의 최대 노브** |
| `w_min,w_max` | 벽-띠 폭 대역 | **상대(치수정박)** 우선 | 절대 mm는 scale FAIL 재유입 위험(§3.3) |
| `τ_aspect` | 세장비 임계 | 3 ~ 8 | 벽-띠 vs 방 |
| `τ_compact` | 방 조밀도 임계 | 0.15 ~ 0.4 | 방 판정 |
| `τ_room_area` | 최소 방 면적 | 상대(도면면적 비) | noise 컷 |
| `max_faces` | 면 폭발 상한 | 사전등록 | quadratic 폭발 가드(R12) |
| `poche_ov` | 포셰 겹침 임계 | 0.5 | HATCH 존재 신호 |

**손실/목적함수**: v0은 손실 없음(규칙). v1 면분류는 가중 BCE. metamorphic 셀은 손실이 아니라 *불변 위반율*.
전이/lift 셀은 F1/AUC. RL·정책 학습 없음(이 제안은 표상 교체이지 정책 학습이 아니다).

### 2.4 계산 복잡도

노딩은 GEOS의 STR-tree 공간색인으로 평균 O(n log n)이나, 조밀 교차(개방형·잡음)에서는 교차점 수 k가 커져
O((n+k) log n)로 팽창한다. **max def 412,775 선분**(다이제스트)이 최악 사례다 → §4의 배치·상한 계획으로 방어.

---

## 3. 벽 과업 적응 설계 — 세 축과의 접속, 그리고 "무엇을 더 가져오는가"

우리는 이미 두 개의 강한 기준선을 안다(다이제스트): **기하 탐지기 전이 val F1 0.2358**(P 0.134 ≈ 기저율
0.118, R 0.981), **6특징 HistGradientBoosting val F1 0.517**(P 0.860 / R 0.370 / AUC 0.9215). 이 방법이
정직하게 *추가*로 가져올 것은 무엇인가를 축별로 반증 가능하게 적는다.

### 3.1 CubiCasa SEG-IR 벡터축 (val=개발, test=단발 — 다이제스트 원칙)

**접속**: `cubicasa_ir`의 세그먼트를 Step 0 노딩→polygonize에 넣어 면을 얻는다. 진리=Wall 클래스 요소의
모서리(다이제스트). 도면당 평균 약 919선분(3.86M/4,200 [산술])으로 폴리곤화는 CPU에서 수월하다.

**무엇을 더 가져오는가 (반증 가능한 가설 H3.1)**: 기하 탐지기의 FP 주범은 Direction 화살표·BoundaryPolygon·
Door·Window·DimensionMark — *전부 대역 내 평행 구조* 다(다이제스트). 6특징 GBDT는 parallel/thickness/junction/
log길이/sin2θ/cos2θ로, **면 위상 특징이 0개** 다. 화살표·치수마크는 방을 *닫지 않는다* — 자유부유(free-floating)한다.
그러므로 "이 세그먼트가 어떤 방-면의 경계인가"라는 **면-소속 신호는 parallel/thickness와 직교(orthogonal)** 하고,
정밀도를 올릴 여지가 있다. 이를 **GBDT에 열로 주입**해 검증한다(C-J4):

```
추가 특징(핸들 단위):  is_face_boundary,  shared_edge_between_two_rooms,
                     incident_area_ratio = min(A_L,A_R)/max(A_L,A_R),
                     dual_degree(변이 가르는 면 수),  poche_overlap,
                     incident_compact = max(compact_L, compact_R)
```

기저 F1 0.517을 **사전등록 밴드**로 초과하면 VIABLE, 셔플-대조군 잡음(AUC 0.375 근방) 안이면 기각. 이 실험은
CL-F(학습 사다리)에 대한 *기여*이지 경쟁이 아니다(§8).

**주의 — BoundaryPolygon**: 이것은 스스로 닫힌 경계이므로 방-면으로 승격될 수 있다. 즉 면-게이트가
자동으로 걸러주지 못하는 유일한 FP 부류일 수 있다 → C-J5 부분석에서 별도 계측.

### 3.2 FloorPlanCAD 래스터축 (연구용 전이 프로브 only, NC)

**한계 명시**: 다이제스트상 FloorPlanCAD 자산은 **래스터 5,308장 + 벽 bbox/segmask, 벡터 SVG 없음**.
면 추출은 벡터를 요구한다. 따라서 이 축은 P1의 홈그라운드가 아니다. 래스터→선 벡터화는 별도 난제이며,
설령 하더라도 **NC(비상업) 라벨 → 연구용 전이 프로브만, 가중치 제품 탑재 금지**(제안 원문 truth source (3)).
결론: **FloorPlanCAD는 P1에서 보조 정성 관찰용**으로만 두고, 정량 밴드는 CubiCasa·합성·실측에서만 건다.

### 3.3 1.dwg 실측축 (도면정의 384개, divergent-20이 본진)

**접속**: staged DXF IR → Step 0(P6 INSERT 전개 포함) → polygonize. **핵심 실험은 divergent-20**
— "LLM 고확신 ∧ n_pairs=0" 상위 20 def에서 face-bridge가 LLM 핸들을 회수하는가(containment).

**무엇을 더 가져오는가**: 두 축의 독립성을 다이제스트가 이미 시사한다 — B5에서 탐지기↔silver Pearson
**0.2911**, full-vs-nb **1.0**(탐지기는 레이어명 신호 0). 즉 현행 탐지기는 이름 신호 없이 기하만 본다.
face-bridge는 *기하이되 다른 기하*(위상)를 보므로, n_pairs=0 구간에서 LLM(의미)과 탐지기(평행쌍) 사이의
**제3의 관측 언어**로 기능할 수 있다. 이것이 dissolved_fact의 검증 경로다.

**scale 불변성 — 이 방법의 가장 강한 차별점(반증 가능)**: 다이제스트 B4에서 현행 탐지기는 **scale 팔 FAIL(0.7624,
strict FAIL 기록)**. 원인은 두께 대역이 절대 mm(50~400mm)라 균일 스케일에 깨지기 때문이다. **면 위상은 스케일에
불변** 이다(polygonize는 절대 크기를 모른다). 따라서 **P1은 현행 탐지기가 실패한 scale 팔을 통과할 수 있다** —
*단, 면 분류의 폭 대역을 절대 mm로 다시 넣으면 그 불변성을 스스로 파괴한다.* 그래서 §2.3의 `w_min,w_max`를
**치수-정박 상대대역(feyerabend P2)** 으로 두는 것이 선택이 아니라 필수다. CubiCasa가 축척 미상(px, 벽두께
p50=22px)이고 물리 두께 prior가 2~15mm/px 전 구간에서 무력했다는 다이제스트 사실이, 상대·위상 접근의 필요를
독립적으로 뒷받침한다.

---

## 4. 데이터·컴퓨트 요구

**전제(다이제스트)**: RTX 5070 Ti **16GB**, RAM **64GB**, DGX Spark(Ornith-35B) **현재 unreachable(승인됨)**,
프런티어 VLM API=유일 결재 게이트(미승인).

### 4.1 로컬 계획 (GPU 불요 — 이 방법의 장점)

- **면 추출·dual·채점**: 전부 Shapely/GEOS + NumPy CPU. GPU 0. `fast_score`의 기하 프리미티브 재사용.
- **CubiCasa 3.86M행 GBDT 재적합(+면 특징)**: HistGradientBoosting은 CPU 수 분~십수 분 규모(다이제스트가
  이미 6특징으로 학습 완료). 면 특징 6열 추가는 색인 1회 선계산 후 열 concat.
- **divergent-20 폴리곤화**: def당 초 단위. 합성 10 + 실측 20 = cheapest probe, 로컬 CPU 수 시간(제안 원문 부합).

### 4.2 최악 사례·배치

- **412,775 선분 def**: 단일 노딩에서 메모리·시간 팽창. 대응 (a) `max_faces` 사전등록 상한 초과 시 즉시
  `DEGENERATE` 반환(면 폭발을 *성공으로 위장하지 않음*), (b) 도면 bbox 타일링 후 경계 스티칭, (c) 야간 배치.
- **384(또는 145 `[요검증]`) 전량 재측정**: 로컬 야간 배치로 충분. **DGX 불필요** — DGX는 초기에도, 이 방법
  전체에서도 필수 경로가 아니다. VLM API도 P1엔 불요(정성 교차대조는 CL-G 소관).

### 4.3 DGX 계획 (조건부, 낮은 우선순위)

DGX가 열리면 유일한 용도는 **대량 arrangement 병렬 배치**(임베어러싱 병렬, 도면 독립)뿐이다. 모델 추론이 아니라
CPU 병렬이라 DGX의 GPU 이점은 제한적 → **DGX 대기 이유 없음**. P1은 로컬-완결 방법으로 설계한다.

---

## 5. 구현 계획

### 5.1 모듈 골격 (신규 `face_wall/` 패키지)

```
face_wall/
  arrangement.py     # Step0-1: 정규화·노딩·polygonize_full 래퍼(+DEGENERATE 가드)
                     #   ← P6 unfold_block_to_world, CL-B 정규화 프론트엔드와 공유
  face_features.py   # Step2: area/compact/aspect/width(neg-buffer)/poche 특징
  dual_graph.py      # Step3: 면-인접 dual, wall_cavity·shared_edge 추출
  provenance.py      # Step4: seg→handle 역참조(STRtree), handles_covering()
  face_wall_score.py # Step5: 리본 병합·상대두께·containment/overshoot 지표
  cells/             # §6 실험 셀 러너 (C-J1..C-J6), 각 셀 = 결정론 스크립트 1개
```

### 5.2 기존 도구 접속점

- **`evidence_grid`**: 셀 결과를 기존 증거 격자/xlsx 하네스로 방출(다이제스트 "증거 xlsx 의무"). 신규 포맷 발명 금지.
- **`fast_score`**: 각도·겹침·스냅 등 기하 프리미티브 재사용. 리본 채점의 NumPy 고속 경로 승계.
- **`cubicasa_ir`**: 벡터축 세그먼트 소스. Step0 입력.
- **`cubicasa_ml`**: 6특징 GBDT 파이프라인. **면 특징 6열을 여기에 주입**(C-J4) — 새 학습기 만들지 않음(Occam).
- **`synthetic_truth`(현 dim-only)**: **분기하여 wall-face 생성기 추가**(C-J1 = PR-1 실행체). 원 dim 경로 불변,
  벽 경로 신설.

### 5.3 개발 규모(대략, 정직한 추정)

- 위험 낮음: `provenance.py`, `dual_graph.py`, `face_wall_score.py`, 셀 러너 — 표준 Shapely 조합.
- **위험 높음(개발 대부분)**: `arrangement.py`의 **robust 노딩·갭봉합**. messy 도면의 갭/오버슈트/자기교차가
  polygonize를 침묵 실패(면 누락)시키는 지점이 이 방법의 실질 난도다. 여기에 개발·검증 예산을 집중한다.
- 합성 wall-face 생성기(C-J1)는 별도 덩어리 — B1 충실도 게이트(§7 T2)를 통과해야 하므로 SPLINE/ARC/HATCH·
  비평행 벽까지 생성해야 한다(단순 double-line 생성기로는 부족).

---

## 6. 실험 셀 정의

원칙(다이제스트 고정): **val=개발·튜닝, test=방법당 단발, 합격선은 평가 전 봉인(prereg), 셔플 대조군 의무,
증거 xlsx 의무, 실패도 사유와 함께 기록**. 아래 6셀은 이 방법이 요구하는 최소이자 충분 집합이다(과소·과잉 금지).
공통 시드 규율: **합성 생성 시드 ⟂ 실측 def**(제안 원문 누수방지), 도면/프로젝트 단위 split, FloorPlanCAD로
맞춘 하이퍼는 실측에 재튜닝 금지(전이만 보고).

### C-J1 — 벽-면 합성 생성기 + 충실도 게이트 (= PR-1 실행체, T2 응답)

- **가설**: 닫힌 방 + 알려진 벽 리본 폭의 IR을 생성할 수 있고, 그 실현상 다양성이 실도면에 근접한다.
- **지표**: (a) 자기회수 recall@ribbon(생성한 진리 리본을 face_wall이 되찾는가), (b) B1식 충실도 KS/TV.
- **prereg 합격선**: recall@ribbon ≥ **0.90**(제안 밴드) **AND** 충실도가 현 합성팩의 B1 FAIL(KS **0.5792**,
  TV **0.265**)을 유의하게 개선(SPLINE/ARC/HATCH·비평행 벽 포함).
- **kill**: 자기 합성에서도 recall<0.90 → 방법이 *자기 진리조차* 못 되찾음(설계 결함, 상위 실험 중단).
- **예산**: 로컬 CPU 1–2일(생성기 개발 포함). **시드**: 생성 시드 집합 S_gen 봉인, 실측과 분리.

### C-J2 — 최저가 판별 프로브: 합성 recall + divergent-20 containment (discrimination_experiment)

- **가설**: n_pairs=0 구간에서 face-bridge가 LLM 핸들을 유의미 회수하고, LINE-쌍은 계속 0.
- **지표**: def별 `containment = |H_LLM ∩ H_bridge| / |H_LLM|`의 **중앙값**; 동시에 `overshoot =
  median(n_bridge_handles / |H_LLM|)`.
- **prereg 밴드(제안 원문 승계)**: 합성 recall@ribbon ≥0.90 **이고** divergent-20 containment 중앙값 **≥0.40
  → VIABLE**; **<0.15 → 관측 언어 교체 가설 약화(counter 약화)**.
- **결과 라벨**: A = face-bridge가 LLM 핸들 유의 회수 ∧ LINE-쌍 계속 0 → `kills: reigning`(LINE-쌍 관측 언어);
  B = face-bridge도 거의 0 또는 과다분할로 무의미 → `kills: counter`(면-유도 벽).
- **kill(과다분할)**: `overshoot > 10×` (def당 median bridges > 10× LLM 핸들) → **기각 후보(게이트가 죽임,
  좌석이 죽이지 않음)**.
- **예산**: 로컬 CPU 수 시간(합성 10 + 실측 20). **시드**: 실측 20은 E1 divergence 상위 20 고정, 튜닝 금지(단발성).
- **누수방지**: divergent-20 하이퍼는 합성/CubiCasa에서 봉인된 값으로 *고정 적용*, 20장에 재튜닝 금지.

### C-J3 — metamorphic 불변 배터리 (scale 팔 = 차별점, T7 sentinel 의무)

- **가설**: 강체(회전·이동·반사)·단위·**균일 스케일** 변환 후 face-bridge 집합 불변.
- **지표**: bridge 집합 Jaccard(핸들 기준) pre/post; sentinel(0벽 도면/전벽 도면)에서의 거동.
- **prereg 합격선**: 강체·반사·단위 Jaccard ≈ **1.0**(수치오차 한도); **scale 팔에서도 불변**
  (현행 탐지기 scale FAIL **0.7624** 대비 통과가 이 셀의 존재 이유). **단, T7 의무: 0벽/전벽 sentinel +
  recall 최저선을 랭킹 사용 전 탑재** — 위반율만 보면 "0벽 탐지기"가 만점으로 통과하므로.
- **kill**: scale 팔에서 Jaccard가 유의 하락 → P1이 절대-mm 두께를 은닉 재유입한 것(§3.3 위반) → 상대대역
  재설계 없이는 scale 차별점 소멸.
- **예산**: 로컬 CPU 반나절. **적용 범위**: 라벨 0으로 384(또는 145 `[요검증]`) 전량 가능(CL-D 공용 심판과 정합).
- **시드**: 변환 파라미터 그리드 봉인.

### C-J4 — CubiCasa 면-특징 GBDT lift (vs F1 0.517)

- **가설**: 면-위상 6특징이 parallel/thickness와 직교해 GBDT를 개선.
- **지표**: val P/R/F1/AUC vs 기저 **F1 0.517 / AUC 0.9215**; 셔플 대조군 AUC.
- **prereg 합격선**: val F1가 사전등록 델타(예: **≥+0.03 절대** `[값 봉인 대상]`) 초과 **AND** 셔플-대조군
  AUC가 기저 셔플 수준(**0.375**)으로 유지(누수 없음).
- **kill**: lift가 셔플 잡음 안 → 면 특징이 무정보 → P1의 학습축 기여 소멸(단, 관측언어/불변 기여는 별개로 생존 가능).
- **예산**: 로컬 CPU 수십 분(재적합). **test 무접촉**(단발 원칙 준수). **시드**: 분할·부트스트랩 시드 고정.

### C-J5 — FP-주범 면-게이트 부분석 (C-J4 데이터 재사용, 신규 데이터 0)

- **가설**: Direction 화살표·Door·Window·DimensionMark는 방-면 경계가 아니므로 면-게이트가 정밀도를 올린다.
- **지표**: 다이제스트 FP 주범 클래스별 precision 변화; **BoundaryPolygon은 별도 추적**(스스로 닫힘 → 예외 위험).
- **prereg 합격선**: 화살표/치수마크/문/창 부분집합에서 precision 상승; BoundaryPolygon 오승격율 사전등록 상한 이하.
- **kill**: BoundaryPolygon·기타 닫힌 잡음이 방-면으로 대량 승격 → 면-게이트가 FP를 못 가름(Goodhart 발현).
- **예산**: C-J4 산출 재분석, 추가 비용 ~0. **시드**: C-J4 승계.

### C-J6 — 실 messy/open-plan 강건성 (T27 정면 시험, R16 KR2/KR4 충돌)

- **가설**: divergent-20 중 개방형(open-plan)·messy 하위집합에서 arrangement가 붕괴하지 않는다.
- **지표**: `polygonize_full`의 dangles/cuts/invalid 비율, 면 수, `overshoot`, DEGENERATE 발생율.
- **prereg 합격선**: DEGENERATE율·overshoot이 사전등록 상한 이하이며 C-J2의 containment가 open-plan
  하위집합에서도 유지.
- **kill(정직한 죽음)**: 개방형/노이즈에서 **면 추출이 붕괴해 bridge 수 폭발(def당 median bridges > 10× LLM
  핸들)** → **기각 후보**. 제안 원문 kill_condition 그대로 — *게이트가 죽이고 좌석은 죿이지 않는다.*
- **예산**: C-J2 실측 20의 하위 분석 + 갭봉합 노브 스윕(로컬 1일). **시드**: 노브 그리드 봉인.
- **주의**: **cheapest probe를 합성이 아닌 실 messy divergent-20에서** 돌리라는 T27 요구를 이 셀이 이행한다.

> **셀 간 단발성 회계**: test 접촉은 C-J4에서만(면-특징 lift의 최종 확인), 그 외는 val/divergent-20/합성.
> divergent-20은 "단발 시험지"로 취급 — 하이퍼는 합성·CubiCasa에서 봉인 후 고정 적용, 20장 재튜닝 금지.

---

## 7. red team 티켓 응답 (이 제안에 걸린 OPEN 티켓)

패널 보고서상 CL-J(=feyerabend P1)에 직접·간접으로 걸린 티켓을 지목하고 입장을 명시한다.

### T27 (MED-HIGH) — CL-J 착수 조건 [수용·이행]
"cheapest probe를 합성이 아닌 **실 messy divergent-20에서**, R16 KR2(오픈플랜)·KR4(messy)를 정면 시험,
GEOS(비GPL) 엔진 명시." **응답**: 전면 수용. **C-J6이 정확히 이 요구**이고, C-J2의 divergent-20 부분이
실측이며, 엔진은 **Shapely/GEOS(LGPL, 비-GPL-전염)**. R16 역전 주장은 C-J2가 실증으로 판별(합성이 아니라
실 messy에서).

### T1 (대리 독립성, sev 0.75, 최우선) — {합성·외부·metamorphic·silver} 공유 prior [부분 해소 + 잔여위험 수용]
**응답**: P1은 이 공격의 *부분 해독제* 다 — face 위상은 "평행 이중선" prior를 **공유하지 않는** 제4 대리를
도입한다(§3.3, B5 Pearson 0.2911이 시사하는 축 독립성과 정합). 따라서 P1을 바스켓에 넣으면 독립성이 *증가*.
**단 정직한 잔여위험**: (a) 합성 wall-face 생성기가 double-line 벽만 만들면 prior를 재공유 → C-J1에서
single-line·poché·블록·비평행 벽을 의무 생성. (b) double-line 도면에서는 face-cavity와 평행쌍이 구조적으로
상관 → 완전 독립 아님. **수용**: CL-E(동일-def 3원 불일치)에 P1을 제4 축으로 편입해 상관을 *계측*한다(숨기지 않음).

### T2 (생성기 부재, sev 0.70) — synthetic_truth.py 벽 코드 0 [수용·하드 선결]
**응답**: **C-J1이 곧 PR-1의 실행체**. 벽-면 생성기를 신설하고 **B1 충실도 게이트(현 KS 0.5792 / TV 0.265 FAIL)를
개선**해야 1차 판별기 자격. 이 게이트 미통과 시 C-J2 이후 전부 BLOCKED로 표시(FM1 회피 — 합성 통과를
PASS로 위장하지 않음).

### T5 (라이선스, sev 0.65) — FloorPlanCAD/CubiCasa NC + 원도면 권리 [수용·격리]
**응답**: (a) FloorPlanCAD는 **정성 프로브 only, 정량 밴드 미탑재**(§3.2). (b) **C-J4는 CubiCasa로 학습** →
그 GBDT 산출물은 **연구 전용, 제품 가중치 미탑재**로 격리. 제품 탐지기는 합성+실측(비-NC)에서 적합·검증.
최종 판단은 **PR-3 counsel 서면 클리어에 종속**(그 전까지 학습 arm은 연구 플래그).

### T7 (sentinel/recall 최저선, sev 0.50) — 위반율-only 밴드 취약 [수용·탑재]
**응답**: **C-J3에 0벽/전벽 sentinel + recall 최저선을 랭킹 사용 전 탑재**. "0개 bridge를 뱉는 탐지기"가
불변성 만점으로 통과하는 경로를 원천 차단. metamorphic 지표는 recall 게이트와 AND로만 사용.

### T34 (프로그램급) — 인용 R-레인 experiment_executed:false [해당·주의]
**응답**: 이 도시에는 divergent-20의 "LLM 고확신 ∧ n_pairs=0" 현상을 *가정이 아니라 재계측 대상*으로 둔다.
CL-A 법의학 감사(정렬-키 아티팩트 재계산 포함)가 이 현상을 계측 아티팩트로 판정하면 **C-J2의 divergent-20
표적 자체가 재정의**된다 — P1은 그 결과에 종속(§8 죽음 조건 2·3).

### (간접) T10/T23 — Graph IR adjacency 완전성
**응답**: dual_graph는 자체 arrangement에서 adjacency를 *생성* 하므로 기존 Graph IR adjacency 완전성 논쟁과
독립이다. 단 provenance 매핑 정확성이 새 취약점 → C-J1 자기회수 recall이 이 매핑을 간접 검증.

---

## 8. 인접 제안과의 관계 — 병합·차별·죽음의 조건

### 8.1 병합 지점 (의존·흡수)

- **feyerabend P6 (INSERT 월드좌표 전개, 확정 결함 정타)**: P1의 Step 0이 **P6에 의존**. 블록 안에 그려진 벽이
  전개되지 않으면 면이 닫히지 않는다 → P6는 P1의 전제.
- **feyerabend P2 (절대 mm → 치수-정박 상대대역)**: P1의 폭 대역이 **P2를 채택해야** scale 불변 차별점(§3.3)이
  성립. P2 없는 P1은 scale FAIL(0.7624)을 재수입한다. → **P1 ⊃ P2 흡수**.
- **CL-B (커버리지-완전 결정론 v1)**: Step 0 정규화 프론트엔드(LWPOLYLINE/MLINE/ARC 정규화 + transform 전개)를
  **공유**. P1은 CL-B의 정규화 위에 면 위상을 얹는다.
- **CL-F (학습 사다리)**: C-J4의 면 특징은 CL-F GBDT에 대한 **기여(열 주입)** 이지 경쟁 아님. GNN 이전에 GBDT가
  뛰면 GNN 불요(Occam)라는 CL-F 조건과 정합.
- **CL-D/CL-E (metamorphic·truth-source 교차)**: C-J3은 CL-D 공용 심판에 편입, P1은 CL-E의 **제4 독립 축**.

### 8.2 차별점 (무엇이 고유한가)

- **calibration P1과의 방향 대립(반대의견 원장 #3)**: calibration P1 = "후보 중심선을 planar arrangement에
  투영"(centerline→rooms, R16 정합). P1 = "room/face 먼저, 벽은 dual bridge"(R16 역전). **둘은 같은 arrangement
  도구를 반대 방향으로 쓴다.** C-J2가 실 divergent-20에서 어느 방향이 현상을 더 회수하는지로 판별 — 이 판별이
  P1의 존재 이유이자 calibration P1과의 하드 차별.
- **관측 언어 교체 vs 게이트 보수**: CL-B는 *같은* LINE-쌍 언어의 커버리지를 넓히고, P1은 *다른* 언어(면 위상)로
  갈아탄다. 이 차이가 §8.3 죽음 조건 3의 핵심.

### 8.3 이 제안이 죽어야 하는 조건 (정직하게)

1. **과다분할 붕괴**: 실 messy/open-plan(C-J6)에서 def당 median bridges > **10× LLM 핸들** → 기각 후보.
   *게이트가 죽인다.*
2. **containment 붕괴**: divergent-20 containment 중앙값 **< 0.15**(C-J2) → 관측 언어 교체 가설 자체가 약화·기각.
   face-bridge가 LLM이 보는 것을 못 회수하면 P1의 근거(dissolved_fact)가 무너진다.
3. **CL-B가 먼저 회수**: CL-B 커버리지 정규화(POLYLINE/ARC를 LINE-쌍 게이트로 편입)만으로 n_pairs=0 def가
   회수되면 **P1은 잉여** — feyerabend P5가 "래스터 본선"을 PARK당한 논리와 동형(면 위상이 CL-B를 *넘어서는*
   회수를 실증할 때까지). 이 경우 P1은 관측언어 논쟁의 사고실험으로만 남고 실험 예산에서 하차.
4. **학습축 무기여**: C-J4 lift가 셔플 잡음(AUC 0.375 근방) 안 → 면 특징 무정보 → 최소한 학습축에서는 죽음
   (불변·판별축은 별개 생존 가능).
5. **자기 진리 실패**: C-J1 자기회수 recall < 0.90 → 방법이 자기 합성조차 못 되찾음 → 설계 결함, 전면 중단.
6. **포셰 부재 도면 우세**: 실측 다수가 포셰(HATCH)를 안 쓰면 두께 추정이 위상만 남아 약화 — 치명은 아니나
   (single-line dual로 강등) 차별점(포셰 신호) 소멸. C-J6에서 poché 존재율을 부수 계측.
7. **CL-A 아티팩트 판정**: E1 divergent-20이 정렬-키/나열-지시 계측 아티팩트로 판명되면 표적 소멸 → P1의
   실측 근거가 사라짐(죽음 조건 2와 연동).

### 8.4 잔여 불확실성·`[요검증]` 롤업

- 실측 도면 수 **384 vs 145** 관계 미확정(§0).
- provenance(seg→handle) 매핑의 정확성 — polygonize가 프로비넌스를 잃으므로 공간 재매칭 필요, 오차원 신규.
- 문헌 인용 연도·저자(`Raster-to-Vector`/`FloorPlanCAD`/`CubiCasa5K`/`Bormann room-seg`/CGAL 라이선스)는 `[요검증]`.
- C-J4의 lift 델타·C-J6의 DEGENERATE/overshoot 상한 등 **prereg 봉인값은 착수 전 별도 봉인**(이 도시에는
  밴드의 *형태*만 확정, 수치 봉인은 평가 직전).
- BoundaryPolygon의 면-게이트 통과 위험(C-J5)은 미해소 — 면-게이트가 만능 FP 필터가 아님을 인정.

---

*작성 규율 확인*: 산출은 이 파일 하나. git·서브에이전트·웹검색 미사용. 시스템 수치는 전부 패킷 다이제스트 인용,
문헌은 일반 지식(불확실분 `[요검증]`). 상태 어휘 준수 — 어떤 셀도 아직 PASS 아님(전부 계획·prereg 단계).

DOSSIER_COMPLETE: feyerabend_P1
