# platt_P1 방법론 심층 도시에

## 제안 판정 요약

이 제안의 강한 가설 H1은 다음처럼 분해해야 검증 가능하다.

1. **표현 커버리지 가설 H1-R**: 현재의 zero-pair 및 누락은 LINE 이외 엔티티, 중첩 INSERT, 단위, 곡선 처리 누락에서 주로 생긴다.
2. **국소 기하 식별 가설 H1-G**: 모든 관련 엔티티를 같은 월드좌표의 canonical primitive로 바꾸면 평행쌍과 정션 토폴로지만으로 벽과 비벽을 충분히 구별할 수 있다.
3. **외부 전이 가설 H1-X**: 합성에서 정한 결정론 규칙이 제3자 라벨 도면에도 그대로 전이된다.

P1은 H1-R에는 강한 처방이다. 그러나 현재 다이제스트의 CubiCasa5k 결과는 H1-G와 H1-X에 이미 불리한 사전 증거다. SEG-IR로 이미 선분화된 데이터에서 기하 탐지기는 val recall 0.981이지만 precision 0.134, F1 0.2358이다. 즉 누락보다 Direction, BoundaryPolygon, Door, Window, DimensionMark 같은 긴 평행 구조의 오탐이 본질적이다. 최소길이 필터의 val F1 천장도 0.335인 반면, 같은 데이터의 6특징 HistGradientBoosting은 val F1 0.517이다. 따라서 P1의 외부 도메인 기여는 엔티티 전개가 아니라 **정션 그래프가 0.134의 정밀도를 얼마나 회복하는가**에 달려 있다.

반대로 실제 1.dwg 축에서는 도면정의별 벽-제로율이 0.682에서 0.2135로 줄었고, scale 불변성은 0.7624로 strict FAIL이다. 이 축에는 표현 커버리지와 단위 처리의 미해결 문제가 실제로 남아 있다. 가장 싼 divergent-20 probe는 H1-R의 방향성을 빠르게 확인하지만, 진리가 없으므로 H1-G의 PASS 증거로 쓰지 않는다.

또 하나의 하드 경계가 있다. 제안문은 FloorPlanCAD의 “선-단위 의미 라벨”을 말하지만, 제공된 자산 다이제스트는 FloorPlanCAD가 래스터 5,308장과 벽 bbox/segmask만 있고 벡터 SVG는 없다고 명시한다. 등록된 CAD 벡터 원본이 없는 한 FloorPlanCAD wall-line F1은 계산할 수 없다. 래스터 에지 벡터화 후의 F1은 P1이 아니라 별도 vision/vectorization frontend까지 함께 시험한다. 그러므로 원래 FloorPlanCAD 밴드는 **벡터-래스터 정합 자산 조달 전 BLOCKED**로 기록하고, 실행 가능한 외부 선-진리 축은 CubiCasa SEG-IR로 별도 프리레그 개정을 봉인한다. 둘을 몰래 대체하지 않는다.

이 문서의 관측 수치는 모두 패킷 다이제스트에서 왔다. 아래의 시간, 메모리 cap, seed, 탐색 격자 등은 **새 실측값이 아니라 실행을 위한 프리레그 제안값**이다. 이번 도시에 작성에는 웹 검색을 사용하지 않았다.

## 1. 이론적 근거·선행연구

### 1.1 방법론 계보

P1은 학습기가 아니라 “표현 정규화 → 기하 후보 생성 → 위상 검증 → 결정론 판정”의 계산기하 파이프라인이다. 기대는 계보는 다음과 같다.

| 계보 | P1에서의 역할 | 서지 상태 |
|---|---|---|
| Autodesk DXF/DWG의 OCS-WCS, BLOCK/INSERT, LWPOLYLINE bulge, MLINE style 의미론 | 엔티티를 월드좌표 canonical primitive로 전개 | 표준 일반 지식. 구현 전 사용 중인 DXF/DWG writer 버전의 공식 명세를 핀하고 세부 순서를 재검증해야 한다. |
| Guttman의 R-tree, Bentley-Ottmann의 선분 교차 탐색 | 모든 쌍의 O(n²) 비교를 피하고 근접 평행쌍·교차를 찾음 | 문헌 일반 지식 |
| Shewchuk의 adaptive robust predicates | 거의 평행, 거의 접함, 미러·큰 좌표에서 orientation/intersection 부호 오류 방지 | 문헌 일반 지식 |
| Blum의 medial axis와 straight-skeleton 계열 | 두 경계선의 중간축을 벽 축으로 해석하고 축 그래프를 구성 | 문헌 일반 지식. P1은 완전한 skeleton을 구하지 않고 이미 찾은 쌍의 중간축만 쓴다. |
| 그래프 기반 line grouping 및 perceptual organization | 고립된 이중선과 연속 벽망을 connected component, degree, 교차 일관성으로 구별 | 일반 방법론; 특정 논문 귀속은 요검증 |
| correct-by-construction procedural generation 및 domain randomization(Tobin 등) | 중심선 그래프에서 벽 경계를 생성하고 표현·교란·변이를 독립적으로 주입 | 문헌 일반 지식 |
| metamorphic testing(Chen 계열) | 라벨 없이 회전·이동·반사·단위·explode 후 예측 동치성을 검증 | 정확한 최초 서지사항은 요검증 |
| CubiCasa5K(Kalervo 등) | 외부 floorplan 진리와 도면 단위 split | 데이터셋/논문명은 일반 지식이나 배포판별 라이선스 문구와 정확 서지는 counsel 검토 시 재확인 |
| FloorPlanCAD | 외부 래스터 벽 bbox/segmask 교차 | 정확 논문·배포 조건·벡터 대응물 존재 여부 모두 요검증 |

이 계보의 핵심은 “기하 규칙이 맞느냐”와 “그 규칙이 볼 수 있는 표현으로 입력이 바뀌었느냐”를 분리하는 것이다. 정규화 오류가 남은 채 낮은 recall을 보면 H1-G를 잘못 죽인다. 반대로 correct-by-construction 합성만 통과하면 생성기와 탐지기가 같은 평행쌍 prior를 공유한 Goodhart일 수 있다. 그래서 transform oracle, 합성 진리, 외부 진리, metamorphic relation을 서로 다른 심판으로 둔다.

### 1.2 P1이 검증하는 것과 검증하지 않는 것

P1이 직접 검증하는 명제는 “지원 대상으로 선언한 CAD 표현을 손실 없이 canonical geometry로 바꾸고, 국소 쌍과 정션 토폴로지만으로 wall_member를 판정할 수 있다”이다. 여기서 **coverage-complete**는 DWG 전체 엔티티에 대한 절대 표현이 아니다. v1의 의무 범위는 LINE, 2D POLYLINE/LWPOLYLINE의 직선·bulge 구간, MLINE, ARC, 그리고 이들을 포함하는 중첩 INSERT이다. 실제 도면에는 SPLINE 3,973개, ARC 2,198개, HATCH 264개가 혼재한다. SPLINE과 HATCH 경계가 v1 범위 밖이면 반드시 unsupported 수와 길이를 보고해야 하며, “완전”이라는 이름으로 누락을 숨기지 않는다.

P1은 room/face semantics, door/window object role, firm 관례, 문자·치수 의미를 모델링하지 않는다. CubiCasa에서 긴 비벽 평행 구조가 주 오탐인 사실 때문에, 정션 후필터까지 실패하면 이는 구현 미완이 아니라 국소 기하 식별력의 한계일 수 있다. 그때 H2의 고전 ML 또는 CL-J의 face/room-first 표현으로 승계한다.

### 1.3 증거의 우선순위

증거는 다음 순서로 강해진다.

1. **transform/normalization oracle**: 입력 표현을 바꿔도 월드 기하가 보존되는가.
2. **합성 held-out 진리**: 알려진 벽쌍과 distractor에서 pair 및 wall_member를 맞히는가.
3. **동일 도면 metamorphic relation**: 회전·이동·반사·scale·unit·explode에서 예측이 동치인가.
4. **외부 벡터 진리**: CubiCasa SEG-IR 또는 정합이 검증된 FloorPlanCAD 벡터 대응물에서 전이되는가.
5. **무진리 실제 CAD probe**: divergent-20과 1.dwg에서 zero-pair가 줄고 정상화 경로가 설명 가능한가.

5번만 좋아져서는 semantic PASS가 아니다. 2번만 좋아져서도 외부 전이를 주장할 수 없다. H2·H3·H4의 “지배” 주장을 demote하려면 1~4를 모두 통과해야 한다.

## 2. 알고리즘 정확 스펙

### 2.1 명명, 입력, 출력

패킷 안에서 “v1”이라는 이름이 제안 구현과 현재 4채널 탐지기에 동시에 쓰여 혼동 가능하다. 실행 시 다음 run ID를 고정한다.

- D_cur: 실행 직전에 SHA-256으로 봉인한 현재 fast_score 기반 탐지기와 설정. 제안문의 v0 비교항이다.
- D_p1_norm: P1 canonicalization과 기존 평행쌍 규칙만 적용.
- D_p1_graph: D_p1_norm 뒤에 정션 그래프 후필터를 적용한 최종 P1.
- D_hgb_ref: 다이제스트의 6특징 HistGradientBoosting 참조선. 재학습 결과와 기존 val 0.517을 섞지 않는다.

입력은 한 도면정의 d의 엔티티 집합 E_d, BLOCK table, MLINE style table, INSUNITS 및 P0의 per-def 단위 감사 결과다. canonical primitive q는 다음 필드를 가진다.

- drawing_id, definition_id
- source_handle, source_entity_type
- instance_path: 루트부터 중첩 INSERT handle과 array index의 순서열
- subpath_index: polyline/curve 내부 구간 번호
- geometry_kind: line, circular_arc, elliptical_arc 또는 tessellated_curve
- geometry_world와 geometry_normalized
- source_parameter_interval
- 누적 affine matrix와 determinant sign
- unit_scale, unit_source, unit_confidence, unit_reason
- approximation_error_bound
- normalization_status와 failure_code

출력은 다음 네 층이다.

1. canonical primitive JSONL
2. pair candidate와 reject reason JSONL
3. wall-axis junction graph
4. 평가 단위별 wall_member, score, provenance, 판정 이유

원본 handle 하나가 여러 구간으로 갈라질 수 있으므로 내부 평가 키는 (source_handle, instance_path, subpath_index)다. 공용 per-handle 계약에는 길이 가중 집계를 함께 내되, 혼합 의미 handle은 segment 결과를 버리지 않는다. 어떤 집계가 primary인지 truth manifest에 미리 고정한다.

### 2.2 정규화

#### 2.2.1 좌표계와 INSERT

각 엔티티의 local/OCS 좌표 p에 대해 월드좌표는 다음으로 계산한다.

\[
p_{\mathrm{world}} =
M_{\mathrm{parent}}
\,T(p_{\mathrm{insert}})
\,R_z(\theta)
\,S(s_x,s_y,s_z)
\,T(-p_{\mathrm{blockbase}})
\,M_{\mathrm{OCS}}
\,p.
\]

실제 구현은 동차좌표의 행렬곱이다. 행렬 적용 순서는 핀한 parser의 convention으로 oracle fixture에서 확인하며, 위 식을 라이브러리 convention에 무비판적으로 복사하지 않는다. 중첩 INSERT는 부모에서 자식 순으로 행렬을 누적한다. row/column array INSERT는 각 cell offset을 별도 instance_path로 전개한다.

필수 처리 규칙은 다음과 같다.

- 음수 scale 또는 음의 determinant는 mirror로 기록한다. 곡선 orientation은 뒤집힐 수 있지만 기하 집합은 보존되어야 한다.
- 비등방 scale 뒤의 ARC/CIRCLE을 원으로 유지하지 않는다. 정확한 ellipse parameterization으로 바꾸거나, 설정된 Hausdorff/chord 오차 이하로 adaptive tessellation한다.
- block base point, OCS extrusion normal, elevation을 반드시 포함한다.
- 순환 block reference는 CYCLE_REFERENCE로 종료하며 무한 재귀하지 않는다.
- max depth와 primitive cap은 자원 안전장치다. 넘으면 조용히 자르지 않고 RESOURCE_EXCEEDED로 도면정의 전체를 미채점 처리한다.
- source_handle만으로 instance를 합치지 않는다. 같은 block handle의 여러 INSERT는 instance_path로 구분한다.

transform oracle은 “직접 월드좌표로 만든 합성 fixture”와 “동일 fixture를 중첩 block/local 좌표로 인코딩한 뒤 flatten한 결과”를 양방향 최근접 및 source correspondence로 비교한다. 이동, 회전, 균일·비등방 scale, 한 축 mirror, 두 축 mirror, 중첩, array를 독립 fixture로 둔다.

#### 2.2.2 POLYLINE/LWPOLYLINE

- 연속 vertex 쌍을 subpath로 분해하고 closed flag이면 마지막-첫 vertex 구간을 추가한다.
- bulge가 0이면 line, 0이 아니면 부호와 chord로 circular arc를 복원한다.
- OCS elevation/extrusion을 월드좌표로 바꾼 다음 부모 INSERT transform을 적용한다.
- constant/variable width는 wall truth로 곧바로 쓰지 않고 provenance 속성으로만 보존한다. 폭 자체를 라벨로 쓰면 생성기 누출이 된다.
- classic 2D POLYLINE은 divergent 현상과의 일치를 위해 LWPOLYLINE과 같은 canonical contract로 받는다. 3D POLYLINE은 평면성 허용오차를 통과할 때만 2D 투영하고, 아니면 OUT_OF_PLANE으로 격리한다.

#### 2.2.3 MLINE

MLINE은 중심 path만 선분화해서는 안 된다. 참조한 MLINESTYLE의 모든 element offset, justification, entity scale, vertex별 direction/miter 정보를 사용해 실제 rail을 전개한다. 두 개보다 많은 rail이면 임의의 “바깥 두 선”을 truth로 가정하지 않고 모든 인접 rail pair를 후보로 내보낸 뒤 두께·중첩 규칙에서 거른다. cap과 join geometry도 canonical primitive로 보존하되, wall pair 평가는 longitudinal rail에만 적용한다. style 정의가 없거나 parser가 의미를 제공하지 못하면 MLINE_STYLE_MISSING으로 실패시키며 LINE으로 가장하지 않는다.

#### 2.2.4 ARC 및 곡선

두 circular arc i,j는 다음을 모두 만족할 때 동심 offset pair 후보다.

\[
\|c_i-c_j\| \le \epsilon_c,\quad
w_{\min}\le |r_i-r_j|\le w_{\max},\quad
\rho_{\mathrm{angular}}(i,j)\ge \rho_{\min}.
\]

각도 interval은 0/2π wrap을 정규화한 뒤 교집합 길이를 짧은 arc 길이로 나눈다. 후보의 중심축은 공통 각도 interval과 평균 반지름으로 만든다. affine transform 때문에 ellipse가 된 두 곡선은 중심·축 벡터의 affine correspondence가 같을 때 exact offset 계열로 비교하고, 그렇지 않으면 adaptive sample의 tangent 평행도와 법선 거리 분포로 평가한다. sampling 오차 상한은 pair gap 허용오차보다 엄격해야 한다.

SPLINE은 v1 의무 범위가 아니다. 다만 tessellated fallback을 켠 실험 arm과 끈 arm을 분리하고, fallback 사용량과 오차 상한을 보고한다. HATCH는 boundary loop를 parser가 신뢰성 있게 제공하는 경우에도 별도 exploratory arm으로만 다룬다.

#### 2.2.5 단위 정규화

단위 상태는 DECLARED, P0_ANCHORED, BBOX_INFERRED, RELATIVE_ONLY, UNRESOLVED 중 하나다.

1. 유효한 INSUNITS와 P0 감사 결과가 일치하면 선언 단위를 사용한다.
2. 불일치하면 P0가 제공한 dimension anchor 또는 검증된 scale evidence를 우선한다.
3. anchor가 없으면 후보 단위 scale마다 log-bbox, robust segment length, 후보 gap 분포를 **synthetic train에서 미리 동결한 참조분포**와 비교한다. 최상 후보와 차상 후보의 margin이 프리레그 기준 이상일 때만 BBOX_INFERRED로 채택한다.
4. margin이 작으면 임의로 mm를 선언하지 않는다. RELATIVE_ONLY arm으로 보내거나 UNRESOLVED로 미채점한다.

per-def 기록에는 원 INSUNITS, P0 판정, bbox, 후보 scale별 score, 선택 이유, confidence, 최종 scale이 들어간다. 145 archive 결과를 보고 이 규칙이나 참조분포를 바꾸지 않는다. bbox 추론이 synthetic prior와 동형이 될 위험을 줄이기 위해 absolute-mm arm과 dimension/robust-gap 상대 arm을 나란히 실행한다.

### 2.3 평행쌍 후보 생성

직선 primitive i의 단위방향을 u_i, 법선을 n_i, 해당 방향 투영 interval을 I_i라 한다. 후보 j에 대해

\[
\delta_\theta(i,j)=\arccos(|u_i\cdot u_j|),
\]

\[
d_\perp(i,j)=\operatorname{median}_{x\in Q_j}|(x-p_i)\cdot n_i|,
\]

\[
\rho_{\mathrm{overlap}}(i,j)=
\frac{|I_i\cap I_j|}{\min(|I_i|,|I_j|)}.
\]

현재 고정 규칙의 출발점은 다이제스트에 있는 각도 2°, 두께 50~400mm, overlap 0.5, snap 6mm다. P1은 이 값을 결과를 본 뒤 손으로 움직이지 않는다. synthetic train에서만 사전 선언된 격자를 탐색하고, 선택된 tuple을 SHA-256과 함께 봉인한다.

전체 쌍을 비교하지 않는다. orientation bucket과 expanded bounding box의 spatial index를 결합한다. 최대 gap만큼 halo를 둔 타일에서 이웃을 찾고, tile 경계의 중복 후보는 canonical pair key로 제거한다. 412,775 선분인 최대 도면정의가 이미 관측되었으므로 다음은 correctness 조건이다.

- 후보 수와 primitive당 이웃 수에 hard cap을 둔다.
- cap 초과 시 낮은 score 후보를 몰래 버리지 않고 해당 정의를 RESOURCE_EXCEEDED로 표시한다.
- 타일별 처리 후 provenance와 후보를 streaming 저장하고, graph 연결에 필요한 경계 노드만 유지한다.
- 정렬키는 geometry score 뒤에 drawing_id, instance_path, source_handle, subpath_index를 사용해 완전 결정론 tie-break를 보장한다.

현재 4채널 가중치 parallel 0.35, thickness 0.25, junction 0.20, layer 0.20은 D_cur 재현 arm에서 그대로 유지한다. 그러나 H1의 primary confirmatory arm은 layer를 0으로 마스크한다. layer명이 없어도 같은 판정이 나와야 “기하 충분”을 검증한 것이기 때문이다. 호환 arm은 기존 네 채널을 유지하되 secondary로만 보고한다.

### 2.4 정션 그래프 후필터

각 pair p의 두 rail 중간에 wall-axis curve a_p를 만든다. axis endpoint와 실제 교차점을 snap tolerance로 cluster하고, 교차점에서 axis를 split해 multigraph G=(V,A)를 만든다. 연결은 다음 세 종류를 구별한다.

- CHAIN: 두 axis endpoint가 가까우며 tangent가 연속적이다.
- CORNER/T: axis의 finite interval 또는 허용된 짧은 endpoint extension이 교차한다.
- CROSS: 두 axis 내부가 교차한다.

단순히 degree가 크다고 벽으로 보지 않는다. grid도 큰 연결 그래프를 만들 수 있다. edge p의 network evidence는 다음 결정론 feature로 구성한다.

- component edge 수와 총 axis length
- endpoint degree multiset
- junction 전후 두께 비의 일관성
- rail이 junction까지 양쪽에서 지속되는 paired-boundary continuity
- 닫힌 작은 symbol loop 여부
- isolated 여부

최종 primary 규칙은 “pair hard gate 통과 AND network-supported”다. network-supported는 연결 component 최소 크기 또는 유효 junction 존재, 두께 일관성, paired-boundary continuity를 모두 요구한다. 고립쌍은 삭제하지 않고 ISOLATED_REVIEW 채널로 분리한다. 실제로 단독 벽이 존재할 수 있으므로 synthetic에 single-wall sentinel을 넣고, D_p1_norm과 D_p1_graph의 recall 차이를 필수 보고한다. 그래프가 precision을 올리지만 진짜 단독벽을 과도하게 지우면 후필터는 실패다.

한 primitive가 여러 pair에 들어가면 score 내림차순, 안정 tie-break 순으로 처리하되 corner에서 합법적인 다중 연결은 허용한다. 서로 같은 두 rail 영역을 중복 주장하는 후보는 maximum-overlap conflict group에서 하나만 선택한다. 선택 전 후보와 선택 후 결과를 모두 저장해 evaluator가 중복 제거를 감사할 수 있게 한다.

### 2.5 의사코드

    function P1_DETECT(drawing_definition d, sealed_config H, p0_unit_record U):
        assert sha256(H) == preregistered_config_hash
        primitives = []
        for entity in deterministic_entity_order(d):
            for instance in expand_insert_tree(entity, identity_matrix):
                result = canonicalize(instance, H.curve_error)
                if result.failed:
                    emit_normalization_failure(result)
                else:
                    primitives.extend(result.primitives)

        unit_decision = resolve_units(d, primitives, U, H.unit_model)
        if unit_decision == UNRESOLVED and not H.relative_arm:
            return UNRESOLVED_UNITS
        primitives = apply_unit_or_relative_scale(primitives, unit_decision)

        spatial_index = build_orientation_spatial_index(primitives)
        candidates = []
        for q in deterministic_primitive_order(primitives):
            neighbors = bounded_neighbor_query(spatial_index, q, H)
            if resource_cap_exceeded(neighbors):
                return RESOURCE_EXCEEDED
            for r in neighbors where canonical_id(q) < canonical_id(r):
                evidence = pair_evidence(q, r, H)
                emit_candidate_with_reason(q, r, evidence)
                if evidence.passes_hard_gates:
                    candidates.append(make_axis_pair(q, r, evidence))

        graph = build_split_snapped_axis_graph(candidates, H.snap)
        for p in candidates:
            p.graph_evidence = evaluate_component_and_junctions(graph, p, H)

        selected = deterministic_conflict_resolution(candidates, H)
        wall_pairs = [p for p in selected if p.graph_evidence.network_supported]
        isolated_review = [p for p in selected if not p.graph_evidence.network_supported]
        wall_members = provenance_union(wall_pairs)
        return primitives, candidates, graph, wall_pairs, isolated_review, wall_members

### 2.6 평가 단위, 매칭, 목적함수

합성 pair truth와 prediction은 허용된 거리·각도·overlap 안에서 bipartite maximum matching한다. 하나의 truth를 여러 prediction이 맞혔다고 중복 TP로 세지 않는다. pair precision/recall은 이 matching에서 계산한다.

wall_member 평가는 다음을 함께 낸다.

- canonical segment micro P/R/F1
- source handle 길이 가중 P/R/F1
- drawing macro F1
- zero-wall 및 all-wall sentinel 결과
- 엔티티 family, transform family, distractor family별 slice

결정론 탐지기에는 학습 loss가 없다. hyperparameter 선택은 synthetic train에서만 다음 lexicographic 규칙으로 한다.

1. transform oracle와 resource gate를 모두 통과한 설정만 남긴다.
2. synthetic train pair recall 0.9와 precision 0.8을 동시에 만족한 설정만 feasible로 둔다.
3. feasible 중 drawing-macro F1이 큰 것을 고른다.
4. 동률이면 더 적은 candidate, 더 작은 tolerance, parameter tuple 사전식 순으로 고른다.
5. feasible 설정이 없으면 가장 좋은 설정을 억지로 validation에 보내지 않고 NO_FEASIBLE_CONFIG로 기록한다.

필수 shuffle control은 truth label을 도면 단위로 permutation한 뒤 동일 score를 평가한다. 이는 학습 누출 검사는 아니지만, evaluator나 ID join이 truth를 새게 하는지 확인한다. permutation 결과를 성능 개선으로 해석하지 않으며, 원 label 결과가 permutation null과 분리되지 않으면 파이프라인을 무효화한다.

### 2.7 프리레그 하이퍼파라미터 공간

아래 숫자는 실측 인용이 아니라 봉인 전 사용할 **제안 격자**다.

| 그룹 | 제안 공간 | 동결 규칙 |
|---|---|---|
| angle tolerance | 1°, 2°, 3°, 5° | synthetic train only |
| absolute thickness | 현재 50~400mm 고정 arm과 P0가 허용한 이웃 band arm | 145/FPC/CubiCasa 결과로 수정 금지 |
| overlap | 0.3, 0.5, 0.7 | synthetic train only |
| absolute snap | 3, 6, 12mm | synthetic train only |
| relative thickness | per-def robust candidate-gap anchor의 0.5~2.0배 범위 | anchor 산식부터 먼저 봉인 |
| relative snap | thickness anchor의 0.01, 0.02, 0.05배 | absolute/relative A/B로 별도 보고 |
| component 최소 edge | 2, 3, 4 | graph ablation train only |
| junction width ratio tolerance | log-ratio 0.1, 0.2, 0.4 | graph ablation train only |
| curve chord error | snap의 0.05 또는 thickness 하한의 0.01 중 작은 값 | correctness parameter; 성능 튜닝 금지 |
| primitive당 candidate cap | 32 | 자원 dry-run 후 validation 전 단 한 번 봉인 |
| 정의당 candidate cap | 5,000,000 | 초과 시 FAIL, truncation 금지 |
| process RSS cap | 48GB | 64GB RAM 로컬 안전 여유를 둔 계획값 |

격자가 너무 넓어 synthetic generator와 동형 최적화를 만들지 않도록, 실제 confirmatory comparison은 D_cur, D_p1_norm, D_p1_graph, relative-scale arm의 네 개로 제한한다. 모든 탐색 행은 evidence xlsx에 남긴다.

## 3. 벽 과업 적응 설계

### 3.1 합성 wall truth 축

기존 tools/semantic_gates/synthetic_truth.py의 correct-by-construction + mutate 패턴을 재사용하되 벽 코드는 새 모듈로 격리한다. 생성 순서는 “의미 → 기하 → CAD 표현”이다.

1. 중심선 graph에서 single wall, chain, L/T/X junction, closed room, curved wall을 만든다.
2. 각 edge에 width를 주고 양쪽 boundary를 생성하며 junction join/cap을 명시한다.
3. wall_member와 true pair/axis를 이 단계에서 확정한다.
4. 같은 기하를 LINE, POLYLINE/LWPOLYLINE, MLINE, ARC, nested INSERT 표현으로 encode한다.
5. dimension line, grid, furniture block, direction symbol, door/window 유사 평행 구조를 negative로 넣는다.
6. 한쪽 rail 삭제, gap 이탈, angle 이탈, 짧은 overlap, fragmentation, 작은 좌표 noise를 mutation으로 넣는다.
7. 이동·회전·반사·균일/비등방 scale·unit rewrite·explode를 metamorphic twin으로 만든다.

표현 encode 전의 analytic geometry가 oracle이고, CAD parser 출력은 진리가 아니다. source handle과 wall truth를 manifest에 함께 저장한다. S팩처럼 음성이 0개여서 precision이 공허해지는 일을 막기 위해 각 split에 negative-only, all-wall, mixed sentinel을 강제한다.

기존 합성팩은 LINE/LWPOLYLINE/INSERT 세 종류뿐이고 B1이 KS 0.5792, TV 0.265로 FAIL했다. 새 생성기는 패킷이 이미 공개한 divergent 현상인 POLYLINE, block nesting, 비평행 조각을 포함하되, 145 archive의 결과를 본 뒤 분포를 맞추지 않는다. fidelity gate가 실패하면 그 버전은 방법론 판별에 쓰지 않고 generator 개발 실패로 기록한다.

### 3.2 CubiCasa SEG-IR 벡터축

CubiCasa는 5,000도면 전량이 SEG-IR로 변환되었고 실패가 0이며, train 4,200/val 400/test 400의 도면 단위 split이 이미 있다. 좌표는 도면별 축척 미상의 pixel이고 wall segment 비율은 약 11.8%다. 이 축에서는 INSERT/MLINE/INSUNITS 정규화가 기여할 여지가 거의 없다. 따라서 다음 질문만 정직하게 시험한다.

- 정션 graph가 current geometry detector의 val P 0.134/R 0.981/F1 0.2358에서 precision을 올리는가.
- absolute-mm prior를 제거한 relative-scale arm이 2~15mm/px 전 구간 무감 현상을 우회하는가.
- Direction, BoundaryPolygon, Door, Window, DimensionMark별 FP가 실제로 줄어드는가.
- 같은 6특징으로 val F1 0.517인 HGB보다 결정론 규칙이 간결성과 전이성으로 경쟁할 수 있는가.

primary 비교는 동일 SEG-IR과 동일 evaluator에서 D_cur 대 D_p1_graph다. 기존 val F1 0.2358에 원 제안의 절대 +0.2 band를 적용하면 개발 목표는 0.4358 이상이다. 이는 다이제스트 수치의 산술적 귀결이지 새 측정이 아니다. F1 0.4 미만이면 H1-G/X kill로 본다. D_hgb_ref 0.517은 학습 사다리의 참조선이며 P1 PASS 조건 자체로 쓰지는 않지만, P1이 지속적으로 크게 뒤처지면 “후속 방법 demote” 주장은 금지한다.

val은 개발과 진단에 쓰되 test는 설정·코드·evaluator·환경 hash와 band를 봉인한 뒤 방법당 한 번만 연다. test 도중 metric을 보고 재실행하지 않는다. 인프라 오류는 prediction 공개 전 checksum 실패처럼 사전 정의된 경우에만 incident로 판정하고, 재실행 승인 규칙도 prereg에 적는다.

### 3.3 FloorPlanCAD 래스터축

현재 자산으로 가능한 arm과 불가능한 arm을 구분한다.

- **FPC-V confirmatory line arm**: 등록된 원 CAD/SEG-IR과 raster-to-vector 변환행렬, line truth가 있을 때만 실행한다. v0의 FPC 값을 먼저 계측·봉인하고 D_p1_graph−D_cur wall-line F1 ≥ +0.2, 최종 F1 ≥ 0.4를 적용한다.
- **FPC-R exploratory raster arm**: P1이 다른 vector source에서 만든 wall axis/boundary를 같은 raster에 정확히 투영할 수 있을 때 segmask와 pixel metric을 낸다. bbox만으로 line F1을 만들지 않는다.
- **raster-edge-vectorization arm**: FloorPlanCAD 이미지에서 선을 추출해 P1에 넣는 방법은 별도 frontend의 오차가 섞이므로 P1 confirmatory 결과에서 제외한다.

벡터 대응물이 없으면 FPC-V는 BLOCKED다. 이 상태에서 FPC F1을 0으로 간주해 H1을 죽이지도, 합성 성공으로 대신 PASS시키지도 않는다. 대신 CubiCasa를 외부 vector truth의 실행 가능한 대체축으로 쓰는 amendment를 test 공개 전에 서면 봉인한다.

FloorPlanCAD는 CC BY-NC 방법 개발 전용 격리구역에 둔다. 데이터, 라벨, FPC로 튜닝한 threshold/config, 파생 feature cache를 제품 경로로 복사하지 않는다. deterministic threshold도 NC 데이터로 선택되면 제품 반입 가능한 “코드만”과 분리하기 어렵다고 보고 quarantine한다. counsel이 허용 범위를 서면 확인하기 전에는 학습·배포 arm을 시작하지 않는다.

### 3.4 1.dwg, divergent-20, 145 archive

P0가 확정한 definition ID와 단위 근거를 소비해 다음 A/B를 같은 입력에서 수행한다.

- folded: 기존 parser가 본 엔티티 표현
- unfolded: P1 canonicalization
- norm-only: unfolded 뒤 기존 pair rule
- graph: unfolded 뒤 graph postfilter

divergent-20에서는 각 definition별 n_pairs의 0→양수 전환, 어떤 entity/transform/unit 단계가 회복했는지, 새 candidate의 provenance를 낸다. 이 count는 cheapest probe의 GO/STOP 신호이지 wall accuracy가 아니다. top-20 정렬 산물 가능성이 있으므로 CL-A의 정렬키 재계산과 원시 정의 감사가 끝나기 전 “대표 20개”라고 부르지 않는다.

1.dwg 전체에서는 384개 도면정의의 zero-pair율, unsupported coverage, per-def unit decision, runtime/RSS를 낸다. 최대 정의가 412,775 선분이므로 resource cap과 streaming correctness도 이 축에서 검증한다. 사람 진리가 없으므로 zero율 감소를 recall 증가라고 쓰지 않는다.

145 archive는 완전한 순수 추론 대상이다. 어떤 threshold, unit model, generator 분포, graph rule도 145 결과로 수정하지 않는다. 실패 도면은 원인코드와 함께 남기고 다음 버전 개발 목록으로만 넘긴다.

### 3.5 다이제스트의 기존 결과 위에서 P1이 더 가져올 수 있는 것

P1이 현실적으로 더할 수 있는 것은 세 가지다.

1. 실제 CAD에서 LWPOLYLINE/MLINE/ARC/INSERT 때문에 pair 자체가 0이던 경우의 회수와 설명 가능한 provenance.
2. scale 불변성 0.7624 FAIL을 unit/relative arm으로 교정.
3. CubiCasa에서 높은 recall 0.981을 유지하면서 graph로 precision 0.134를 올리는 것.

반면 6특징 HGB의 val F1 0.517은 국소 특징에 비선형 경계가 필요하다는 신호다. P1 graph가 그 비선형성을 hand-coded topology로 일부 회수할 수는 있지만, SEG-IR에는 엔티티 커버리지 문제가 없으므로 normalization이 0.2358→0.517의 차이를 설명할 수 없다. P1이 외부 vector truth에서 0.4를 넘지 못하면 “v0 실패는 개념이 아니라 coverage”라는 최강형은 죽는다.

## 4. 데이터·컴퓨트 요구

### 4.1 데이터와 방화벽

| 데이터 | 역할 | tuning 허용 | 진리/제약 |
|---|---|---|---|
| 새 wall synthetic train | 파라미터 선택 | 허용 | analytic correct-by-construction |
| synthetic held-out/hidden mutation | confirmatory | 금지 | manifest 봉인 |
| CubiCasa train/val | 외부 진단 및 amendment의 개발 | val까지 허용하되 primary P1-core는 synthetic-frozen도 함께 보고 | SEG-IR line truth, 도면 단위 split |
| CubiCasa test 400 | 단발 판정 | 절대 금지 | unopened one-shot |
| FloorPlanCAD 5,308 raster | 방법 개발/외부 교차 | counsel 후 개발 전용 | bbox/segmask, vector truth 없음 |
| divergent-20 | cheapest representation probe | 판정 후 수정 금지 | semantic truth 없음 |
| 1.dwg 384 definitions | inference/runtime | 금지 | semantic truth 없음 |
| 145 archive | 순수 추론 | 금지 | parameter tuning 금지 |

FPC와 CubiCasa의 NC 및 원 도면 권리는 counsel 문서가 우선한다. attribution, 원본 license snapshot hash, 접근 위치, 생성된 cache, config lineage를 evidence workbook에 기록한다. FPC/CubiCasa로 선택한 parameter를 제품 기본값으로 승격하지 않는다. 외부셋 없는 synthetic-only config와 NC-derived config를 별도 이름과 디렉터리로 유지한다.

### 4.2 로컬 CPU 실행

P1 본선은 CPU only다. RTX 5070 Ti 16GB는 사용하지 않는다. RAM 64GB에서 도면정의 단위 streaming을 사용하고, 제안 RSS cap은 48GB다. 프로세스는 다음 메모리 층만 유지한다.

- 현재 definition의 canonical primitive와 spatial index
- 현재 tile과 max-gap halo의 candidate
- graph 경계 node 및 component accumulator
- append-only provenance/evidence writer buffer

도면 전체 pair matrix나 전체 145 archive IR을 메모리에 올리지 않는다. 동일 입력과 config에서 thread 수와 정렬 규칙을 고정해 byte-identical prediction hash를 요구한다. 성능 최적화를 위한 병렬 tile 처리도 최종 merge 순서를 canonical key로 정렬한다.

계획용 자원 상한은 definition당 candidate 5,000,000, primitive당 32, RSS 48GB다. 이 값은 측정치가 아니라 validation 전 dry-run에서 안전성을 확인할 프리레그 제안이다. 초과는 해당 definition FAIL이며 표본에서 제외해 성능을 좋게 만들지 않는다.

### 4.3 GPU와 DGX 계획 분리

- **로컬 GPU**: P1에는 불필요하다. FloorPlanCAD raster-edge-vectorization 탐색을 한다면 별도 CL-G/vision arm으로 분리하며 P1 결과에 합치지 않는다.
- **DGX Spark**: 현재 unreachable이고 P1은 DGX를 사용하지 않는다. DGX 복구를 P1 일정의 선결로 두지 않는다.
- **VLM/silver**: 학습이나 truth로 쓰지 않는다. 필요하면 T1의 proxy independence 표에서 별도 판정축으로만 비교한다. 현재 silver 다섯 판정자는 약 두 어휘 가문으로 취급하며 다섯 독립표로 세지 않는다.

### 4.4 실행 산출물

각 미래 run은 다음을 만들어야 하나, 현재 패킷 실행 자체에서는 이 도시에 파일 하나만 작성한다.

- run_manifest.json: 입력 hash, config hash, executable/module hash, 환경, split, license lane
- normalization.jsonl: primitive와 failure/provenance
- candidates.jsonl: accept/reject reason
- wall_graph.json 또는 streaming equivalent
- predictions.jsonl
- metrics.json
- evidence.xlsx: 필수 증거 workbook
- failures.jsonl

evidence.xlsx에는 summary, per_drawing, per_entity_family, per_transform, per_distractor, unit_decisions, resource_usage, shuffle_control, test_seal, license_ledger sheet를 둔다. 실패 행을 삭제하지 않는다.

## 5. 구현 계획

### 5.1 제안 파일 골격

아래는 실제 저장소 구조를 확인한 뒤 맞출 **제안 골격**이며, 현재 존재한다고 주장하지 않는다.

    tools/wall_detector/
      contracts.py              # canonical primitive, provenance, status enum
      transforms.py             # OCS/WCS, INSERT tree, affine curve handling
      normalize_entities.py     # LINE/POLYLINE/LWPOLYLINE/MLINE/ARC
      units.py                  # INSUNITS, P0 adapter, bbox/relative decision
      spatial_candidates.py     # orientation bucket, tile/halo, resource cap
      pair_geometry.py          # line/arc pair evidence
      junction_graph.py         # snap, split, component, continuity
      deterministic_select.py   # conflict resolution and stable tie-break
      evaluator.py              # pair matching, wall_member, slices
      schemas/

    tools/semantic_gates/
      wall_synthetic_truth.py
      wall_mutations.py
      wall_oracles.py

    tools/e2_p1/
      run_probe.py
      run_synthetic.py
      run_cubicasa.py
      run_real_archive.py
      write_evidence_xlsx.py

    tests/wall_detector/
      test_transform_oracle.py
      test_entity_normalization.py
      test_arc_pairs.py
      test_units.py
      test_junction_graph.py
      test_determinism.py
      fixtures/

### 5.2 기존 도구 접속점

- **fast_score**: D_cur를 재현하는 frozen adapter와 P1 canonical primitives를 받는 adapter를 분리한다. 기존 NumPy score 수식은 바꾸지 않고 입력 표현 변화의 효과를 먼저 측정한다.
- **evidence_grid**: cell ID, hypothesis, split, config hash, status, metric, threshold, failure reason을 등록한다. PASS는 metric 파일과 evidence.xlsx row가 모두 있을 때만 생성한다.
- **cubicasa_ir**: 기존 train/val/test drawing ID와 line truth를 그대로 소비한다. converter를 재실행해 split이나 line ID를 바꾸지 않으며 manifest hash를 검사한다.
- **cubicasa_ml**: HGB를 P1 안에 넣지 않는다. 동일 evaluator의 D_hgb_ref 출력만 비교표에 연결한다.
- **P0 output**: per-def unit/handle/entity audit를 typed adapter로 읽고, 누락 필드가 있으면 추측하지 않고 PRECONDITION_MISSING을 낸다.
- **synthetic_truth.py**: mutate/manifest 패턴을 재사용하되 dimension truth와 wall truth schema를 혼합하지 않는다.

### 5.3 구현 순서와 규모

1. contract, provenance, transform oracle
2. entity normalizers
3. unit decision과 P0 adapter
4. spatial candidate와 기존 score adapter
5. graph 후필터
6. synthetic wall generator와 evaluator
7. CubiCasa/real archive runners
8. evidence workbook와 one-shot seal

계획 추정은 약 7~10 로컬 개발일, 신규·수정 코드 약 2,000~3,000줄과 fixture/manifest다. 이는 실측이 아니라 staffing 제안이며, MLINE parser가 style/vertex semantics를 노출하지 않거나 nonuniform affine curve가 별도 구현을 요구하면 늘어난다. cheapest divergent-20 probe는 transform, polyline, unit의 최소 vertical slice가 완성되는 첫 1일 목표다.

### 5.4 테스트 전략

- pure unit tests: 행렬 순서, mirror orientation, bulge arc, angle wrap, closed polyline, missing style
- property tests: flatten(explode(x))와 world geometry 동치, transform composition associativity의 허용오차 내 동치
- golden fixtures: nested INSERT와 nonuniform scale, MLINE junction, concentric arc pair
- metamorphic tests: rigid/reflection/unit/explode는 wall membership exact 동치; scale은 canonical unit 변환 후 동치
- determinism tests: 반복 실행 prediction 파일 SHA-256 동일
- stress test: 합성으로 largest-definition 규모까지 늘려 cap 전후 상태 확인
- evaluator tests: duplicate prediction, mixed handle, empty-negative, all-positive, shuffled IDs

## 6. 실험 셀 정의

### 6.1 공통 seed와 봉인 규칙

다음 seed는 실행을 위한 제안값이며 측정치가 아니다.

- synthetic train root: 1103, 2207, 3301
- synthetic validation root: 4409, 5519
- hidden mutation/test root: 6637, 7741
- shuffle/permutation root: 8803, 9901

generator version, seed list, parameter distribution, mutation-family split, detector config space를 하나의 prereg manifest로 hash한다. deterministic detector 자체에는 seed가 없고 stable tie-break를 쓴다. 각 stochastic generator seed를 독립 복제로 보고 seed별 metric과 pooled metric을 모두 낸다.

### 6.2 셀 표

| 셀 | 가설 | 주요 지표 | 제안 합격선 | 킬/중단 조건 | 예산·시드 |
|---|---|---|---|---|---|
| G0 baseline/evaluator 봉인 | D_cur와 evaluator가 재현 가능하다 | prediction hash, val metric 재현, ID join 감사 | 반복 hash 동일, 기존 공개 metric과 반올림 허용범위 내 일치 | 불일치면 모든 비교 BLOCKED | 로컬 CPU 0.5일, detector seed 없음 |
| G1 normalization oracle | 지원 엔티티와 transform이 기하를 보존한다 | family별 Hausdorff/parameter 오차, 누락률, metamorphic equality | 모든 의무 family가 tolerance 내 PASS, silent drop 0 | mirror/비등방/nested 중 하나라도 systematic fail이면 detector 평가 중단 | 로컬 CPU 1일, 모든 synthetic seed |
| G2 wall generator fidelity | generator가 negative와 divergent 표현을 포함하며 truth가 correct-by-construction이다 | entity/transform/mutation coverage, negative prevalence, KS/TV gate, sentinel | 사전 봉인한 fidelity gate와 모든 sentinel PASS | 벽 코드 부재, negative 0, truth round-trip fail이면 PR-1 미완 | 로컬 CPU 1~2일, train/val roots |
| E0 divergent-20 cheapest probe | zero-pair의 일부는 representation coverage 때문이다 | definition별 n_pairs 0→양수 전환 수, 단계별 provenance, unit status | 하나 이상 설명 가능한 전환이면 full experiment GO; 정확도 PASS로는 세지 않음 | 전환 0이면 P1 vertical slice STOP 및 원인 감사 | 로컬 CPU 1일, seed 없음 |
| E1 synthetic confirmatory | 완전 정규화 후 geometry가 wall pair를 찾는다 | held-out pair P/R, wall_member F1, family slices | pair R≥0.9 및 P≥0.8 | 완전 정규화 후 pair R<0.7이면 H1 kill | 로컬 CPU 1일, val/hidden roots; train tuning 금지 |
| E2 junction ablation | graph가 isolated distractor를 줄이고 진짜 network를 보존한다 | D_p1_norm 대비 ΔP, ΔR, ΔF1, single-wall recall, distractor별 FP | ΔP>0, ΔF1>0, ΔR≥−0.05의 제안 band | precision 이득 없음 또는 recall 붕괴면 graph arm kill | 로컬 CPU 1일, val roots |
| E3 CubiCasa val transfer | topology가 SEG-IR 외부축의 긴 평행 distractor를 구별한다 | micro/macro P/R/F1, five FP family, runtime | D_p1_graph−D_cur F1≥+0.2 및 F1≥0.4; 기존 val 기준 목표 0.4358 이상 | 최종 F1<0.4면 H1-G/X kill | 로컬 CPU 1~2일, 고정 split, detector seed 없음 |
| E4 absolute-vs-relative unit | absolute mm artifact보다 dimension/robust-gap anchor가 scale 전이에 강하다 | scale slice F1, metamorphic scale equality, unit unresolved rate | relative arm이 scale equality strict PASS하고 외부 F1 비열등 | 둘 다 scale strict FAIL이면 unit normalizer 재설계; 성능 숫자로 bbox 규칙 retune 금지 | 로컬 CPU 1일 |
| E5 FloorPlanCAD external | 정합된 외부 vector truth에서도 전이한다 | wall-line F1, v1−v0, registration error | vector 정합 전 BLOCKED; 조달 후 ΔF1≥+0.2 및 F1≥0.4 | F1<0.4면 H1 kill; raster-only면 결론 금지 | counsel/asset 의존, 로컬 CPU; drawing split |
| E6 real-CAD scale/resource | 1.dwg/145에서 설명 가능한 coverage 회수와 bounded execution이 가능하다 | zero-pair율, unsupported율, cap fail, wall time/RSS, determinism hash | silent truncation 0, 반복 hash 동일, cap 실패 전부 보고 | O(n²) 폭발·무기록 drop이면 implementation FAIL | 로컬 CPU 1~2일, seed 없음; 145 tuning 금지 |
| E7 proxy/metamorphic independence | 여러 proxy의 합의가 같은 prior의 복제가 아니다 | 동일-def 3원 contingency, disagreement strata, rigid/scale/unit/explode equality, sentinels | lossless relation exact membership 동치, scale strict PASS, sentinel PASS | 0-wall detector가 통과하거나 proxy가 사실상 동일하면 합의 증거 demote | 로컬 CPU 1일, permutation roots |
| E8 one-shot external test | 봉인된 P1이 unopened test에 전이한다 | CubiCasa test P/R/F1와 CI, per-drawing macro, failures | test 전 봉인한 E3 band 동일 적용 | band 미달이면 H1 kill; test 재튜닝 금지 | 로컬 CPU 1회, test 400, seed 없음 |

### 6.3 셀별 실행·판정 세부

#### G0 — baseline과 evaluator

D_cur의 module/config/input/evaluator hash를 기록한다. val 0.2358이 재현되지 않으면 이름 충돌, converter drift, threshold drift, evaluator drift 중 하나이므로 비교를 시작하지 않는다. 이 셀은 새 성능을 주장하기 위한 것이 아니라 기준선을 고정하는 셀이다. git hash는 사용하지 않고 파일 SHA-256 manifest로 봉인한다.

#### G1 — normalization oracle

detector를 전혀 실행하지 않고 canonical geometry만 검사한다. 특히 nested INSERT의 transform 순서, mirror determinant, nonuniform ARC→ellipse, MLINE style, LWPOLYLINE bulge를 독립 fixture로 테스트한다. 여기서 실패한 family는 synthetic recall 저하와 혼동될 수 있으므로 E1로 넘기지 않는다.

#### G2 — generator fidelity

train distribution을 먼저 동결하고 validation/hidden family를 생성한다. 기존 B1 FAIL 수치 KS 0.5792, TV 0.265를 단순히 더 좋은 숫자로 만들기 위해 145를 모사하지 않는다. 제안 gate는 주요 scalar feature별 KS≤0.2, categorical entity-family TV≤0.1, 공개된 필수 family coverage 100%다. 이 숫자는 실측이 아닌 prereg 제안이며, 패널 승인 전에 봉인한다. divergent-20은 분포 fitting source가 아니라 blind gate로만 사용한다.

#### E0 — cheapest probe

20개 정의 각각에 folded/unfolded를 실행한다. 전환마다 “어떤 원본 handle이 어떤 instance_path와 unit decision을 거쳐 어떤 pair가 되었는지”를 사람이 재현할 수 있어야 한다. n_pairs가 늘어도 dimension/grid/furniture 가능성이 있으므로 semantic precision을 부여하지 않는다. 0→양수 전환이 0이면 full 145 run보다 먼저 transform/unit coverage 가정을 재검토한다.

#### E1/E2 — 합성과 graph

E1은 원 제안 band인 pair recall 0.9와 precision 0.8을 그대로 쓴다. recall 0.7 미만은 H1 kill이다. E2는 같은 prediction에서 graph 전후를 비교하므로 paired comparison이다. single-wall, network-wall, grid, dimension, furniture slice를 따로 내야 평균이 단독벽 삭제를 숨기지 않는다.

#### E3 — CubiCasa val

네 arm을 같은 val에서 한 번에 비교한다: D_cur, D_p1_norm, D_p1_graph, D_p1_graph_relative. D_hgb_ref는 별도 참조 열이다. 현재 geometry detector는 거의 전부를 positive로 잡아 P가 기저율 0.118에 가까운 0.134이고 R은 0.981이다. 그러므로 주 성공지표는 recall을 더 올리는 것이 아니라 FP family별 precision 회복이다. graph가 grid/BoundaryPolygon까지 network로 오인하면 H1-G가 직접 반증된다.

val에서 config를 고친 경우 반드시 새 config hash를 만들고, 이전 결과와 선택 과정을 evidence.xlsx에 남긴다. synthetic-frozen arm과 CubiCasa-val-adapted arm을 분리해 외부 라벨 tuning 효과를 드러낸다. test에는 사전에 지정한 하나만 보낸다.

#### E4 — 단위

absolute 50~400mm arm, P0 dimension anchor arm, bbox-inferred arm, relative-gap arm을 분리한다. 현재 scale 팔 0.7624 FAIL을 strict 동치로 고치는 것이 correctness 목표다. CubiCasa는 px 좌표이고 2~15mm/px 범위에서 기존 성적이 무감했으므로 physical band를 억지 적용하지 않는다. bbox arm이 scale을 잘못 고른 정의는 per-def 근거와 함께 UNRESOLVED로 돌리는 것이 거짓 정규화보다 낫다.

#### E5 — FloorPlanCAD

등록된 vector source가 조달되면 도면 단위 split, raster-vector transform oracle, dual label parser 합치 검사를 먼저 통과한다. bbox와 segmask를 line label로 환원할 때의 boundary thickness/skeleton 선택이 결과를 바꿀 수 있으므로, 그 선택은 evaluator 일부로 hash한다. vector source가 없으면 E5는 BLOCKED이고 raster exploratory 숫자로 원 prereg를 판정하지 않는다.

#### E6 — 실제 CAD와 자원

최대 412,775 선분 정의를 포함해 wall time, peak RSS, 후보 수, tile 수, cap 상태를 definition별 기록한다. resource fail 정의를 성능 denominator에서 몰래 빼지 않는다. 145 archive에서는 오직 inference하고, 관측된 failure family를 다음 버전 backlog로 복사할 수는 있지만 현재 결과를 다시 돌려 PASS로 바꾸지 않는다.

#### E7 — proxy 독립성과 metamorphic

동일 def에서 deterministic P1, 외부 truth, synthetic/metamorphic 판정, 가능한 경우 silver의 wall 여부를 contingency table로 만든다. silver 다섯 모델은 두 어휘 가문 정도로 묶어 family vote를 별도 표시한다. 일치율 하나로 독립성을 주장하지 않고, “모두 평행쌍에 동의하고 같은 Door/DimensionMark에서 틀리는가”를 disagreement stratum으로 본다.

0-wall과 all-wall sentinel을 포함해 예측량 보존까지 확인한다. rigid/reflection/explode/unit rewrite는 source correspondence가 유지되는 한 wall_member가 exact 동치여야 한다. scale arm도 unit normalization 뒤 strict PASS가 목표다.

#### E8 — test 단발

G0~G2, E1~E4, E7이 PASS하고 config/evaluator/container/input manifest를 봉인한 뒤만 test 400을 연다. 실행이 끝날 때까지 aggregate metric을 표시하지 않는 blind runner를 사용한다. test 결과가 band 미달이면 실패 이유와 함께 기록하고 재튜닝하지 않는다. H1이 죽으면 같은 test를 H2용 개발셋처럼 재사용하지 않는다.

## 7. red team 티켓 응답

패널 요약이 ticket 상세 원문 전체를 제공하지 않으므로, 아래는 패킷이 P1 또는 프로그램 선결로 직접 연결한 ticket만 확정적으로 지목한다. ID가 명시되지 않은 위험을 임의 ticket 번호에 붙이지 않는다.

| 티켓/위험 | P1 응답 | 상태 |
|---|---|---|
| **T1 대리 독립성** | E7에서 동일-def contingency와 오류 family 겹침을 측정한다. 합성·metamorphic·외부·silver를 단순 다수결로 합치지 않는다. | P1 단독 완전 해소 불가; CL-E와 공동 OPEN |
| **T2 생성기 부재** | wall_synthetic_truth를 실제 구현하고 analytic truth, negative, mutation, transform oracle, fidelity gate를 G2에서 요구한다. 기존 dimension-only 파일을 wall truth 존재 증거로 쓰지 않는다. | 하드 선결, 구현 전 OPEN |
| **T3/T4/T8, CL-A 법의학 선결** | P0의 real definition, unit, entity, 정렬키 감사 결과를 typed input으로 요구한다. top/divergent 표본을 대표 표본이라 가정하지 않는다. Ornith 원시는 P1 truth로 사용하지 않는다. | CL-A 완료 전 E0 해석 제한 |
| **T5 라이선스/counsel** | FPC/CubiCasa 원본·라벨·NC 조건을 서면 확인하고 별도 license lane, cache, config lineage를 둔다. NC 데이터로 고른 parameter와 파생물의 제품 반입을 금지한다. | counsel 전 외부 학습/배포 BLOCKED |
| **T6 평가 단위 불일치** | canonical segment와 source handle을 둘 다 내고, primary wall_member aggregation을 truth manifest에 사전 고정한다. pair count를 per-handle accuracy로 대체하지 않는다. | 설계상 해소 가능, evaluator test 필요 |
| **T7 sentinel 부재/0벽 탐지기** | negative-only, all-wall, mixed, single-wall sentinel과 recall floor를 G2/E7에 넣는다. violation-only metric으로 랭킹하지 않는다. | 구현 후 close 가능 |
| **T9/T21 v0 baseline 선계측** | D_cur의 파일/config/evaluator hash와 CubiCasa/FPC 각 축 baseline을 먼저 봉인한다. FloorPlanCAD vector truth가 없으면 baseline도 BLOCKED로 명시한다. | G0 및 E5 선결 |
| **T16 절대 vs 상대 gap band** | absolute-mm, P0 dimension anchor, bbox, relative-gap을 E4의 사전 A/B로 분리한다. 한 arm 결과로 다른 arm parameter를 고치지 않는다. | E4로 직접 응답 |
| **T17 동일-def 대리 불일치** | T1과 함께 E7 contingency 및 오류 family matrix를 산출한다. 공통 def 정합이 안 되면 비교 불능으로 기록한다. | CL-E와 공동 OPEN |
| **T23 Graph IR adjacency 완전성** | P1은 입력 adjacency를 믿지 않고 canonical axis 교차/endpoint에서 graph를 재구성한다. 원 provenance와 split/snap 결과를 내고 작은 analytic graph oracle로 완전성을 검사한다. | junction 구현 후 검증 |
| **T34 인용 experiment_executed:false** | 본 문서의 선행연구는 권위 증거가 아니라 설계 계보로만 사용한다. load-bearing 성능 주장은 다이제스트와 새 실행 artifact만 사용하고, 정확 서지는 구현 prereg 전 재검증한다. | 문헌 재-status 전 OPEN |
| **R12 quadratic 후보 폭발 상한** | spatial index, tile halo, primitive/definition cap, RSS cap을 validation 전에 봉인한다. cap 초과를 truncation하지 않고 실패로 센다. | stress test 필요 |
| **FloorPlanCAD label-schema 불일치** | raster bbox/segmask를 line truth라고 부르지 않는다. vector-raster registration과 dual parser 합치가 없으면 E5 BLOCKED다. | 자산 조달 전 수용 위험 |
| **INSERT mirror/비등방 오류** | transform oracle와 ellipse/tessellation contract를 G1 hard gate로 둔다. | 구현 후 close 가능 |
| **Goodhart: synthetic와 휴리스틱 동형** | hidden mutation, 외부 SEG-IR, distractor slice, proxy disagreement를 요구한다. synthetic PASS만으로 H1을 살리지 않는다. | 구조적으로 완화, 완전 제거 불가 |

layer channel과 관련된 firm lexicon ticket(T14/T33 맥락)은 primary H1 arm에서 layer를 0으로 마스크해 우회한다. 호환 arm이 layer를 쓸 경우에만 frozen lexicon과 project split이 필요하며, 그 결과는 geometry sufficiency 증거로 세지 않는다.

## 8. 인접 제안과의 관계 및 사망 조건

### 8.1 병합 지점

- **CL-A/P0 법의학 감사**: P1의 unit/definition/handle truth를 제공하는 하드 선결이다. P1이 자체 bbox 추정으로 P0의 불확실성을 덮어쓰지 않는다.
- **CL-C/WSD-EVAL-v1**: wall synthetic generator, per-handle wall_member contract, hidden mutation pack은 공용 자산으로 병합한다.
- **CL-D metamorphic battery**: transform/unit/explode 동치와 sentinel을 공용 evaluator로 병합한다. P1 전용 transform oracle는 그 아래 correctness 층이다.
- **CL-E truth-source 교차요인**: P1 prediction을 train=none/deterministic cell로 넣고 동일-def proxy disagreement를 공유한다.
- **doe Taguchi와 feyerabend relative-band**: full Taguchi 전에 absolute-vs-relative A/B를 E4에서 판별한다. 이 결과가 Taguchi knob 범위를 줄인다.
- **CL-F 고전 ML**: P1의 parallel/thickness/junction/log-length/direction feature와 provenance를 HGB/PU/GNN의 공통 입력으로 넘길 수 있다. 단, P1 test를 본 뒤 HGB를 같은 test에 튜닝하지 않는다.
- **CL-J face/room-first**: graph가 grid/door/window를 벽망으로 계속 오인하면 local pair graph가 아니라 face/room consistency가 필요한지 시험하는 승계안이다.
- **E-P2 Δ baseline**: D_cur, D_p1_norm, D_p1_graph의 동결 결과가 후속 learned method의 lift 기준이다.

### 8.2 차별점

P1의 고유 기여는 학습 없이 CAD 표현을 world-coordinate canonical geometry로 만드는 **감사 가능한 frontend**와, 각 wall 판정이 어떤 원 handle/INSERT path/unit 근거에서 왔는지 추적 가능한 provenance다. H1이 죽어도 이 frontend와 oracle은 H2/H3에 재사용 가치가 있다. 그러나 재사용 가치가 있다는 사실은 H1 PASS가 아니다.

CL-F와의 차이는 parameter fitting의 유무다. P1은 synthetic train에서 규칙 tuple만 고르고 외부 도메인에 고정 적용한다. HGB 0.517이 더 높더라도 P1이 충분한 band를 넘으면 간결한 baseline으로 남을 수 있다. 반대로 graph 규칙을 계속 추가해 사실상 손으로 만든 classifier가 되면 Occam 이점이 사라지므로 rule count와 config hash를 보고한다.

CL-J와의 차이는 방향이다. P1은 boundary pair에서 axis와 graph를 만든다. CL-J는 face/room을 먼저 만들고 그 사이 bridge를 wall로 해석한다. P1이 긴 비벽 평행 구조를 topology로 구별하지 못할 때 이 표현 전환이 필요하다.

### 8.3 정직한 사망 조건

다음 중 하나면 H1의 강한 형태를 죽인다.

1. G1이 통과한 완전 정규화 입력에서도 synthetic held-out pair recall이 0.7 미만이다.
2. 실행 가능한 외부 vector truth에서 최종 F1이 0.4 미만이다. FloorPlanCAD-V가 조달되면 원 조건을 적용하고, 그 전에는 사전 봉인한 CubiCasa amendment로 판정한다.
3. synthetic은 0.9/0.8 band를 통과하지만 CubiCasa에서 D_p1_graph−D_cur F1이 +0.2에 못 미치거나, graph가 Door/Window/DimensionMark/BoundaryPolygon FP를 줄이지 못한다. 이는 coverage가 아니라 semantics 부족이다.
4. 정션 filter가 precision을 올리는 대신 single-wall 또는 sparse-wall recall을 제안 허용폭보다 크게 떨어뜨린다.
5. unit/bbox 결정이 scale metamorphic strict FAIL을 고치지 못하고 per-def 근거로도 모호성을 분리하지 못한다.
6. 412,775-segment 정의에서 bounded 후보 생성이 불가능해 silent truncation이나 표본 제외가 필요하다.
7. 외부 proxy가 같은 평행쌍 prior를 공유해 synthetic 성공이 독립적으로 확인되지 않는다.

다음은 H1 kill이 아니라 구현/증거 BLOCKED다.

- FloorPlanCAD vector correspondence 부재
- counsel 미승인
- P0 definition/unit 감사 미완료
- baseline/evaluator 재현 실패
- transform oracle 실패

BLOCKED를 PASS나 FAIL로 바꾸지 않는다.

### 8.4 최종 의사결정 규칙

- **P1 GO**: G0~G2가 통과하고 E0에서 적어도 하나의 설명 가능한 0→양수 전환이 있다. 이후 confirmatory cell로 간다.
- **H1 PASS**: E1의 0.9/0.8 band, E2 graph 보존 band, E3/E8 외부 F1·lift band, E4/E7 불변성·sentinel을 모두 통과한다. 그때만 H2·H3·H4의 “지배” 주장을 demote한다.
- **H1 KILL**: 위 사망 조건 중 하나가 confirmatory artifact로 성립한다. H2의 고전 ML을 첫 승계로 하고, P1 canonical frontend는 입력층으로 재사용한다.
- **INCONCLUSIVE/BLOCKED**: FloorPlanCAD line truth 또는 counsel처럼 필요한 독립 증거가 없을 때다. 합성 성공이나 pair count로 빈칸을 채우지 않는다.

현재 다이제스트만으로는 H1 PASS를 선언할 수 없다. 오히려 CubiCasa val F1 0.2358 대 HGB 0.517은 “coverage만 고치면 충분하다”는 주장에 반대 방향이다. P1의 가치 있는 다음 행동은 cheapest divergent-20으로 H1-R을 확인하고, 동시에 synthetic oracle과 CubiCasa graph ablation으로 H1-G/X를 빠르게 죽이거나 살리는 것이다.

DOSSIER_COMPLETE: platt_P1
