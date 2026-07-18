# P6 방법론 심층 도시(圖示): Cross-def / INSERT 조립 단위

- 좌석: feyerabend
- 제안: P6
- 대상: E2 벽 의미 탐지기
- 문서 성격: 실행 가능한 프리레지스터드 실험·구현 계획
- 근거 경계: 이 문서의 프로그램 수치와 현황은 패킷의 실측 다이제스트만 사용했다. 아래에서 새로 정한 반복 수, 시간·메모리 한도, 허용오차와 합격선은 모두 **측정 결과가 아니라 사전등록 제안값**이다.
- 조사 경계: 웹 검색을 사용하지 않았다. 선행연구는 일반 지식으로 정리했으며, 구현을 시작하기 전에 정확한 판본·API 의미를 확인해야 하는 항목은 **요검증**으로 표시했다.
- 현재 판정: 실험 전. 어떤 셀도 PASS로 간주하지 않는다.

## 1. 이론적 근거·선행연구

### 1.1 깨뜨리려는 몫(quotient)

현재 per_def 방식은 도면의 선분 집합을 작성 단위인 block definition별 동치류로 먼저 나눈 뒤, 각 동치류 안에서만 평행 이중선 후보를 찾는다. 이를 형식화하면 다음과 같다.

- D: block definition과 modelspace root의 집합
- E_d: 정의 d가 직접 소유한 정규화 선분 집합
- I: INSERT 간선 집합
- p: modelspace root에서 어떤 정의까지 가는 INSERT 경로
- T_p: 경로 p의 누적 affine transform
- W_p: T_p를 적용해 월드 좌표에 놓인 선분 인스턴스 집합
- R(a, b): 두 월드 선분이 각도, 간격, 겹침 등 고정된 벽-리본 후보 조건을 만족한다는 관계

folded 후보 집합은 대략 C_fold = union over d of pairs(a, b in E_d such that R(a, b))이다. 반면 실제 배치 문맥에서 필요한 집합은 C_world = pairs(a, b in union over p of W_p such that R(a, b))이다. 참 벽의 양쪽 변 a와 b가 서로 다른 정의에 있거나 하나는 modelspace에 있고 다른 하나는 INSERT 자식에 있으면, R(a, b)가 참이어도 C_fold에는 그 증인이 존재할 수 없다. 즉 벽-쌍 관계는 정의별 분할에 대해 보존되는 성질이 아니다.

P6의 핵심 반론은 단순하다. block definition은 작성·재사용을 위한 저장 단위이지 벽 의미의 자연 단위라는 보장이 없다. 따라서 “한 def 안에서 n_pairs=0”이라는 관측은 “배치된 도면에서 벽이 없다”를 함의하지 않는다. INSERT를 펼친 후에만 생기는 쌍이 하나라도 검증되면, 전자의 사실은 표현 선택에 종속된 유물이 된다.

### 1.2 방법론 계보

1. **Feyerabend식 방법론적 다원주의.** 이 제안은 기존 관측 언어인 def 단위를 중립적인 사실로 취급하지 않는다. Paul Feyerabend의 Against Method 계보에서 가져오는 것은 특정 알고리즘이 아니라, 지배적인 분할 규칙 자체를 경쟁 이론의 시험 대상으로 올리는 태도다. 서지 연도와 판본은 일반 지식이며 정확 인용 전 요검증이다.

2. **CAD scene graph와 instancing.** DXF/DWG의 BLOCK/INSERT, 그래픽스의 scene graph, Open CASCADE의 shape location, IFC의 mapped representation은 “정의된 기하 + 배치 변환”을 분리한다. 충돌, 가시성, 공간관계 같은 질의는 대개 인스턴스 변환을 누적한 좌표계에서 평가한다. E2의 벽-쌍도 같은 종류의 관계 질의다. 다만 DXF INSERT의 OCS/WCS, extrusion, 비균일 scale, array 배치의 정확한 변환 순서와 현재 IR parser의 의미는 구현 전에 공식 문서와 고정 parser 버전으로 요검증해야 한다.

3. **assembly flattening과 provenance-preserving expansion.** 렌더러와 B-rep/IFC 처리기는 정의를 무작정 복사하는 대신 원본 객체와 placement path를 함께 보존한다. P6도 source handle을 버리지 않고 placed-instance key를 추가한다. 이것은 결과를 원본 CAD 객체로 되돌릴 수 있게 하며, 동일 정의의 여러 배치를 서로 다른 문맥으로 평가할 수 있게 한다.

4. **공간 색인 기반 관계 탐색.** 모든 선분 쌍을 비교하면 최악의 경우 제곱 복잡도다. Guttman의 R-tree와 이후 STRtree 계열은 bounding-box 교차 후보를 먼저 줄이는 전형적인 방법이다. Shapely/GEOS의 STRtree 또는 동등한 로컬 구현을 사용할 수 있으나, 라이브러리 버전별 반환 형식과 thread-safety는 요검증이다. 여기서 색인은 근사 판정기가 아니라 완전 후보 생성기이며, 최종 각도·두께·겹침 검사는 정확 predicate가 담당한다.

5. **metamorphic testing.** 정답 라벨이 부족한 프로그램에서 입력 표현을 바꾸되 의미가 보존될 때 출력 관계도 보존되어야 한다는 metamorphic testing 계보가 직접 적용된다. Chen 등의 초기 metamorphic testing 문헌은 일반 지식으로 언급하며 정확한 기술보고서 제목·연도는 요검증이다. 본 제안의 핵심 변환은 “같은 월드 기하를 한 def, 여러 def, nested INSERT, explode 표현으로 바꾸기”다.

6. **content-addressed provenance와 누수 통제.** 실행 그래프의 노드 식별은 block name, layer name, silver 판정, 사람 라벨이 아니라 handle과 INSERT 경로의 안정 해시만 사용한다. 암호학적 해시를 보안 주장에 쓰는 것이 아니라, 이름 신호가 traversal·join·dedup에 스며들지 않게 하는 데이터 계보 장치로 쓴다.

### 1.3 경쟁 이론이 내는 서로 다른 예측

- 지배 이론 H_def: 벽 의미의 충분한 단위는 def다. 올바른 정규화와 점수화가 있으면 펼침은 후보를 거의 추가하지 않거나, 추가분은 중복·오탐이다.
- 반대 이론 H_world: 벽 의미는 배치된 월드 기하의 관계다. 의도적으로 벽 양변을 서로 다른 scope에 둔 합성에서는 folded가 놓치고 unfolded만 회수한다. 실제 INSERT-rich 발산 정의에서도 새 cross-scope 쌍이 반복적으로 생긴다.
- 판별 결과 A: 변환 oracle과 누수 검사가 통과한 상태에서 unfolded만 합성 정답을 회수하고 실제 프로브에서도 사전등록 비율 이상의 새 cross-scope 쌍을 만든다. 이 경우 def quotient를 기각한다.
- 판별 결과 B: 유효한 펼침 뒤에도 합성 정답을 놓치거나, 실제 적격 표본에서 새 cross-scope 쌍이 전혀 없다. 이 경우 P6의 반대 이론 또는 그 E2 실용성을 기각한다.
- 중간 결과: 실제 표본에서 일부 새 쌍은 있으나 사전등록 비율에 못 미치면 NO-GO/불충분이다. 이를 임의로 PASS로 올리지 않는다.

### 1.4 이 제안이 설명하지 않는 것

P6는 “어디에서 후보 관계를 계산할 것인가”를 바꾼다. 평행 구조가 벽인지 Door, Window, Direction 화살표, BoundaryPolygon, DimensionMark인지 가르는 의미 분류기는 아니다. 따라서 CubiCasa5k에서 기하 탐지기 v1이 val F1 0.2358이었던 이유와, 6특징 HistGradientBoosting이 val F1 0.517까지 올린 이유를 대체하지 않는다. P6는 CAD block 조립 때문에 아예 보이지 않던 후보를 복원할 수 있지만, 새 후보의 정밀도를 보장하지 않는다. 이 구분을 흐리면 “후보 수 증가”를 “벽 인식 향상”으로 오인하게 된다.

## 2. 알고리즘 정확 스펙

### 2.1 입력 계약

입력 IR은 최소한 다음 정보를 제공해야 한다.

- root modelspace identifier
- definition별 안정 handle과 직접 소유 entity 목록
- primitive별 source handle, geometry kind, 좌표
- INSERT별 source handle, target definition handle, insertion/rotation/scale/extrusion 및 array 정보
- drawing unit을 mm로 바꾸는 검증된 계수 unit_mm
- 현재 propose_for_ir가 지원하는 primitive를 선분으로 정규화하는 동일 adapter

block name, layer name, 사람 라벨, silver 점수는 traversal key나 placement hash에 들어갈 수 없다. layer 등 기존 fast_score 입력은 후보 생성 뒤의 별도 downstream 회귀 셀에서만 원래 방식 그대로 전달할 수 있다. 실제축에서 unit_mm가 UNKNOWN이면 50–400 mm 대역을 사용한 결과를 내지 않고 그 셀을 BLOCKED 처리한다.

지원하지 않는 dynamic block state, unresolved xref, proxy entity, 비평면 기하는 조용히 버리지 않는다. entity handle, 이유, 영향받은 placement 수를 failure ledger에 기록한다. cycle, missing target definition, 비가역 또는 비유한 transform은 해당 도면을 FAIL-CLOSED로 만든다.

### 2.2 출력 계약

핵심 함수의 제안 인터페이스는 다음과 같다.

~~~text
propose_for_ir(ir, scope_mode, frozen_config)
  -> ProposalResult {
       placed_segments,
       candidate_pairs,
       proposed_placed_handles,
       source_projection,
       diagnostics,
       provenance_manifest
     }
~~~

각 placed segment는 다음 필드를 가진다.

~~~text
PlacedSegment {
  placed_uid: SHA-256 hex,
  source_entity_handle: string,
  source_def_handle: string,
  placement_path_uid: SHA-256 hex,
  subentity_ordinal: integer,
  p0_world: float64[2],
  p1_world: float64[2],
  unit_mm: float64,
  transform_flags: {mirrored, nonuniform_scaled, array_member}
}
~~~

각 candidate pair는 endpoint 두 개, 각도차, 월드 간격, overlap ratio, cross_scope 여부, cross_placement 여부, fast_score용 feature와 deterministic pair_uid를 가진다. pair_uid는 정렬한 두 placed_uid의 해시다.

출력 단위는 의도적으로 둘로 분리한다.

- **assembly 산출물:** placed_uid 단위. 같은 source handle이라도 서로 다른 INSERT 경로의 배치는 서로 다른 예측 단위다.
- **기존 평가 호환 projection:** source_entity_handle 단위의 집계. any-positive, all-positive, placement-count-weighted 세 집계를 모두 보고하되 하나를 몰래 선택하지 않는다.

P6의 1차 판별은 assembly 산출물에서 한다. source handle로 투영한 수치는 호환성 보고일 뿐이다. 배치마다 의미가 달라질 수 있으므로 이를 기존 per-handle 성능 향상으로 바로 주장하지 않는다.

### 2.3 안정 경로 해시

이름 누수를 막기 위한 경로 식별은 다음과 같다.

~~~text
root_uid = H("MODELSPACE_ROOT" || root_def_handle)
child_path_uid =
  H(parent_path_uid
    || insert_entity_handle
    || target_def_handle
    || array_row_index
    || array_col_index)
placed_uid =
  H(child_path_uid || source_entity_handle || subentity_ordinal)
~~~

H는 SHA-256으로 고정한다. 문자열 직렬화는 길이-prefix가 있는 UTF-8 byte sequence로 고정해 연결 모호성을 없앤다. 배열이 아닌 INSERT는 row=0, col=0이다. 동일 handle topology에서 block/layer 이름만 바꾸면 모든 uid가 같아야 한다. explode처럼 handle topology가 바뀌는 metamorphism에서는 uid 동일성을 요구하지 않고, 월드 기하와 truth mapping의 동일성을 비교한다.

### 2.4 변환 전개

각 INSERT의 local transform은 고정 parser adapter resolve_insert_transform가 반환한다. P6 코드가 DXF 변환 순서를 별도로 추측해 중복 구현하지 않는다. 누적 변환은 column-vector 규약에서 다음과 같이 고정한다.

T_child_world = T_parent_world × T_insert_local × T_array_cell

primitive가 OCS에 있으면 parser adapter가 먼저 WCS primitive로 만든다. 이후 root 평면으로 투영 가능한 2D geometry만 받는다. 반사 변환은 determinant 부호로 기록하되 endpoint canonicalization이 방향 반전을 흡수한다. 비균일 scale도 실제 월드 endpoint에 적용하고, 각도와 간격은 변환 후 다시 계산한다.

path-local ancestor set으로 recursion cycle을 검출한다. 같은 definition을 서로 다른 정상 placement에서 재사용하는 것은 허용하지만, 현재 경로에서 동일 INSERT edge가 순환하면 실패다. proposed max_depth를 넘거나 proposed max_instances를 넘으면 부분 결과를 PASS로 저장하지 않고 ABORTED_RESOURCE로 기록한다.

### 2.5 선분 정규화

scope 효과만 판별하기 위해 folded와 unfolded는 완전히 같은 primitive normalizer를 쓴다.

1. LINE은 한 선분이다.
2. LWPOLYLINE/POLYLINE은 현재 E2 normalizer가 정한 동일한 vertex segment로 분해한다.
3. ARC/SPLINE/MLINE 지원은 CL-B의 별도 coverage 작업이다. 현재 normalizer가 지원하지 않으면 양 arm에서 동일하게 unsupported로 기록한다.
4. zero-length, NaN, infinite endpoint는 handle과 이유를 기록하고 제외한다.
5. endpoint는 월드 좌표에서 lexicographic order로 canonicalize한다.
6. source entity가 여러 선분으로 분해되면 subentity_ordinal을 안정적으로 부여한다.

단순 LINE만으로 만든 micro-synthetic는 transform/scope의 단위 oracle일 뿐, PR-1 fidelity gate를 통과한 벽 합성팩을 대신하지 않는다.

### 2.6 정확 pair predicate

두 월드 선분 a와 b에 대해 방향 unit vector의 부호를 맞춘 뒤 다음을 계산한다.

- delta_theta = arccos(clamp(abs(dot(u_a, u_b)), 0, 1))
- u = normalize(u_a + sign(dot(u_a, u_b)) × u_b)
- n = perpendicular(u)
- I_a, I_b = 각 선분 endpoint를 u축에 투영한 폐구간
- overlap = max(0, min(high_a, high_b) - max(low_a, low_b))
- overlap_ratio = overlap / min(length_a, length_b)
- thickness_mm = abs(dot(midpoint_b - midpoint_a, n)) × unit_mm

후보 조건은 기존 v1의 고정 파라미터를 그대로 사용한다.

- delta_theta ≤ 2°
- 50 mm ≤ thickness_mm ≤ 400 mm
- overlap_ratio ≥ 0.5
- junction 계산의 snap = 6 mm

위 값은 패킷 다이제스트의 기존 탐지기 설정이며 P6에서 튜닝하지 않는다. scope 효과를 격리하기 위해 P6 v0의 1차 pair-recovery 판정은 parallel/thickness/overlap predicate까지로 고정한다. junction과 기존 4채널 가중합은 그 뒤 downstream score에 적용한다. 기존 가중치는 parallel 0.35, thickness 0.25, junction 0.20, layer 0.20으로 동결한다. 이름/레이어가 없는 geometry-only arm도 별도로 보고하되, primary scope 판정과 섞지 않는다.

near-parallel 수치 안정성을 위해 delta_theta 비교는 실제 구현에서 cosine threshold 비교로 바꾸되, 수학적으로 같은 경계를 써야 한다. 경계값 바로 아래·같음·바로 위의 synthetic case를 포함한다.

### 2.7 후보 색인과 복잡도 방어

모든 placed segment의 월드 bounding box를 최대 두께만큼 확장한 envelope로 STRtree를 만든다. 방향은 180° 주기의 2° bin과 인접 bin으로 나눈다. 각 선분은 다음 조건을 만족하는 index hit만 exact predicate에 보낸다.

- 상대 placed index가 더 커서 pair를 한 번만 생성
- 확장 bbox가 교차
- 방향 bin이 허용 이웃

이 방식은 후보를 줄일 뿐 pair predicate를 근사하지 않는다. 최종 결과에 lossy top-k나 임의 sampling을 쓰지 않는다. candidate count가 proposed hard ceiling에 닿으면 실행을 중단하고 복잡도 kill로 판정한다. “처음 일부만 계산한 PASS”는 금지한다.

관측량은 N placed segments, Q bbox hits, C exact predicate calls, P accepted pairs, peak RSS, wall time, index build time, traversal time다. 실측 크기 증가에 따른 log(time) 대 log(N)의 기울기도 기록하지만, 하나의 지수만으로 복잡도를 증명하지 않고 Q/N과 C/N을 함께 공개한다.

### 2.8 folded와 unfolded의 공정한 비교

- folded: primitive를 해당 source def의 local 좌표에 둔 채, 동일 def 내부에서만 2.6 predicate를 적용한다. INSERT entity 자체는 geometry endpoint가 아니며 자식 geometry를 부모와 합치지 않는다.
- unfolded: root에서 도달 가능한 모든 primitive instance를 월드로 배치한 뒤, source def와 무관하게 2.6 predicate를 적용한다.
- 두 arm은 같은 parser version, normalizer, float dtype, unit metadata, threshold, candidate predicate, scoring code를 쓴다.
- wall-clock 비교를 제외한 정확도 비교에서는 candidate index의 순서가 결과를 바꾸지 않게 pair_uid로 정렬한다.
- unfolded의 새 쌍은 단순히 반복 배치 수가 늘어난 것으로 세지 않는다. new_cross_scope_pair는 양 endpoint의 source_def_handle이 다르고, 동일한 source-scope 조합의 folded 결과에는 없으며, exact predicate를 통과해야 한다.

### 2.9 의사코드

~~~text
function EXPAND_TO_WORLD(ir, cfg):
    assert cfg contains no label-derived traversal rule
    assert verified unit_mm or return BLOCKED_UNIT

    root = ir.modelspace_root
    out = []
    failures = []

    procedure visit(def_handle, T_parent, path_uid, active_edges, depth):
        if depth > cfg.max_depth:
            raise ResourceAbort("max_depth")

        for entity in stable_handle_order(ir.entities(def_handle)):
            if entity.kind == INSERT:
                target = ir.resolve_target(entity)
                if target is missing:
                    raise IntegrityFailure(entity.handle, "missing_target")

                for cell in stable_array_order(entity):
                    edge_key = (def_handle, entity.handle, target, cell)
                    if edge_key in active_edges:
                        raise IntegrityFailure(entity.handle, "cycle")

                    T_local = resolve_insert_transform(entity, cell)
                    assert finite(T_local)
                    child_uid = path_hash(path_uid, entity.handle,
                                          target.handle, cell.row, cell.col)
                    visit(target.handle,
                          T_parent * T_local,
                          child_uid,
                          active_edges union {edge_key},
                          depth + 1)
            else:
                segments = normalize_with_existing_adapter(entity)
                if unsupported:
                    failures.append(entity.handle, reason)
                    continue
                for ordinal, segment in enumerate(segments):
                    world_segment = apply(T_parent, segment)
                    validate_finite_and_planar(world_segment)
                    out.append(make_placed_segment(
                        source=entity.handle,
                        source_def=def_handle,
                        path=path_uid,
                        ordinal=ordinal,
                        geometry=world_segment))

            if len(out) > cfg.max_instances:
                raise ResourceAbort("max_instances")

    visit(root.handle, Identity, root_uid, empty_set, 0)
    assert unique(placed_uid for out)
    return stable_sort(out), failures


function WORLD_PAIRS(placed_segments, cfg):
    index = build_orientation_partitioned_STRtree(placed_segments,
                                                   halo=cfg.thickness_max)
    pairs = []
    counters = zero

    for i, a in enumerate(placed_segments):
        for j in exact_index_hits(index, a, j_greater_than=i):
            counters.Q += 1
            b = placed_segments[j]
            counters.C += 1
            features = exact_pair_features(a, b)
            if passes_frozen_predicate(features, cfg):
                pairs.append(make_pair(a, b, features))
            if counters.C > cfg.max_exact_candidates:
                raise ResourceAbort("candidate_ceiling")

    return stable_sort(unique_by_pair_uid(pairs)), counters


function RUN_P6(ir, cfg):
    folded = pairs_within_each_source_def(ir, cfg)
    placed, traversal_failures = EXPAND_TO_WORLD(ir, cfg)
    unfolded, counters = WORLD_PAIRS(placed, cfg)
    new_cross = select pair in unfolded where
                pair.cross_scope and not folded_equivalent(pair)
    return folded, unfolded, new_cross, counters, traversal_failures
~~~

### 2.10 손실, 지표와 하이퍼파라미터 공간

P6 v0는 학습기가 아니므로 최적화 loss는 없다. loss를 억지로 도입하지 않고 다음 평가량을 사전등록한다.

- synthetic placed-instance recall = 회수한 참 placed endpoints / 전체 참 placed endpoints
- synthetic placed-instance precision = 참으로 매핑되는 proposed endpoints / 전체 proposed endpoints
- pair recall = 회수한 참 wall pairs / 전체 참 wall pairs
- zero-wall false proposal rate
- real new-cross creation rate = 새 cross-scope pair가 하나 이상 생긴 적격 def 수 / 적격 def 수
- metamorphic pair-set agreement
- peak RSS, wall time, Q/N, C/N

프리레그의 주 하이퍼파라미터는 다음처럼 세 층으로 봉인한다.

| 층 | 파라미터 | v0 값/공간 | 정책 |
|---|---|---:|---|
| 기존 탐지기 | angle, thickness, overlap, snap | 2°, 50–400 mm, 0.5, 6 mm | 패킷 값 그대로 고정 |
| 전개 | max_depth | 32 | 제안값, 넘으면 실패 |
| 전개 | max_instances | 2,000,000 | 제안값, lossy truncation 금지 |
| 색인 | orientation bin | 2° 및 인접 bin | 제안값, exact predicate가 최종 판정 |
| 자원 | max_exact_candidates | 50,000,000 | 제안값, 도달 시 kill |
| 자원 | peak RSS gate | 48 GiB 이하 | 64GB 머신의 여유를 남기는 제안값 |
| 자원 | full-probe wall time | 2시간 이하 | 로컬 CPU 실용성 제안값 |
| 수치 | geometry epsilon | 1e-9 × max(1, drawing extent) | transform oracle용 제안값 |

어떤 자원 ceiling도 정확도 향상을 위해 사후 변경하지 않는다. ceiling이 너무 낮아 정상 도면이 중단되면 그 자체가 v0의 실용성 FAIL이다. 후속 v1에서 바꾸려면 새 prereg와 새 method id가 필요하다.

## 3. 벽 과업 적응 설계

### 3.1 1.dwg 실도면축

패킷 다이제스트의 실도면은 staged DXF 1장, 도면정의 384개이며 최대 도면정의는 412,775 선분으로 연산 병목이 실증되어 있다. P6의 직접 타깃은 이 축이다.

실행 순서는 다음과 같다.

1. CL-A가 정렬-키 아티팩트를 제거해 다시 계산한 top-20 manifest를 입력으로 받는다. 이전 top-20을 사실로 재사용하지 않는다.
2. manifest에서 INSERT 자식이 있는 def를 topology만으로 판정한다. block name은 선택에 쓰지 않는다.
3. 적격 def를 기존 divergence rank, 동률이면 handle byte order로 정렬해 앞의 10개를 cheapest probe로 봉인한다. 10개 미만이면 대체 표본을 임의 추가하지 않고 BLOCKED_SAMPLE로 기록한다.
4. 각 def가 실제 modelspace placement로 도달 가능한지 검사한다. 도달 불가능한 orphan definition은 월드 조립 가설의 실측 분모에 넣지 않고 별도 보고한다.
5. 동일 config에서 folded와 unfolded를 실행하고, def별 new_cross_scope_pair 존재 여부를 기록한다.
6. block name의 anonymous 패턴 여부는 결과 계산 뒤 reporting-only join으로 붙일 수 있다. traversal, pair 생성, 합격 판정의 topology-only 표본 선택에는 사용하지 않는다.

이 축에는 사람 라벨이 주어지지 않았다. 따라서 “새 cross-scope 쌍 생성”은 def quotient가 관계를 가렸다는 메커니즘 증거이지, 그 쌍이 참 벽이라는 semantic truth가 아니다. 실측 결과를 “벽 회수”라고 부르려면 독립 라벨 또는 사람이 블라인드로 검토한 후속 셀이 필요하다.

### 3.2 합성축

패널이 지적했듯 기존 synthetic_truth.py에는 벽 코드가 없으므로, P6는 기존 합성 truth가 있다고 가정하지 않는다. 합성은 두 단계다.

- **T0 micro-synthetic:** 두 평행 선을 서로 다른 block definitions 또는 child/modelspace에 두고, INSERT 변환 뒤에만 월드에서 정확한 벽 리본이 되게 만든다. 이것은 변환과 scope의 단위 oracle다.
- **PR-1 fidelity synthetic:** divergent 실제현상의 POLYLINE, block nesting, 비평행 조각, distractor를 포함하는 프로그램 공용 벽 생성기다. T2 fidelity gate를 통과해야 P6의 합성 결과를 프로그램 수준 증거로 승격한다.

truth는 source handle이 아니라 placed_uid endpoint pair로 생성 시점에 기록한다. 같은 정의를 여러 곳에 배치해 한 placement에서만 벽 쌍이 되는 사례를 반드시 포함한다. 그래야 source-handle any-positive 투영이 문맥 차이를 숨기는지 드러난다.

### 3.3 CubiCasa5k SEG-IR 벡터축

CubiCasa5k는 전량 SEG-IR 변환에 성공했고 train 4,200, val 400, test 400으로 고정되어 있다. 벽 선분율은 약 11.8%다. 그러나 이 데이터가 INSERT/definition graph를 보존한다는 정보는 패킷에 없다.

따라서 먼저 schema-only audit를 한다.

- INSERT graph가 없다면 unfolded는 identity여야 한다. 이 경우 CubiCasa val은 P6의 효과 검증셋이 아니라 비회귀 대조군이다.
- INSERT graph가 있다면 해당 graph의 source와 transform 완전성을 먼저 감사하고, val에서만 scope ablation을 수행한다.
- test 400은 P6 v0에서 건드리지 않는다. 방법과 합격선이 봉인되고, 실제로 INSERT가 있어 비동일 결과가 예상될 때만 방법당 단발 원칙에 따라 한 번 실행한다.

기하 탐지기 v1은 val에서 P 0.134, R 0.981, F1 0.2358이었고, HistGradientBoosting은 P 0.860, R 0.370, F1 0.517, AUC 0.9215였다. 이 관측은 P6에 두 가지 제한을 준다.

1. 후보를 더 많이 만드는 것만으로는 긴 평행 비벽 구조의 오탐을 해결하지 못한다.
2. GBDT의 6특징 분류는 후보 의미를 가르는 downstream 단계이고, P6는 candidate coverage/placement 단계다. 둘은 경쟁 방법이 아니라 직렬 조합 후보다.

P6가 만든 CAD 새 후보에 CubiCasa 학습 GBDT를 바로 적용해 성능 향상을 주장하지 않는다. CAD와 픽셀 SEG-IR의 domain shift 및 scale 의미가 다르기 때문이다. 먼저 synthetic placed truth와 향후 라벨된 CAD validation에서 feature distribution과 calibration을 확인해야 한다.

### 3.4 FloorPlanCAD 래스터축

FloorPlanCAD 자산은 래스터 5,308장과 wall bbox/segmask이며 벡터 SVG가 없다. block definition, INSERT handle, transform path가 없으므로 P6의 직접 truth source가 아니다. 다음 용도만 허용한다.

- 월드 전개 전후 CAD를 동일 renderer로 rasterize했을 때 픽셀이 같아야 한다는 시각적 metamorphic checksum
- 향후 정확한 CAD↔pixel 대응이 별도 검증된 경우의 보조 semantic audit

래스터 mask와 임의로 가까운 선분을 연결해 P6 정답이라고 만들지 않는다. pixel-to-handle exact harness가 없는 상태에서는 FloorPlanCAD를 primary gate에서 제외한다.

### 3.5 기존 E2 harness 접속

- cubicasa_ir: IR schema audit와 identity-control adapter
- fast_score: unfolded가 만든 candidate pair에 기존 4채널 점수를 동일하게 계산
- cubicasa_ml: frozen HistGradientBoosting을 optional downstream diagnostic으로만 호출; P6 v0 중 재학습 금지
- evidence_grid: folded/unfolded, provenance, failure, resource metric을 필수 xlsx로 기록

P6의 성공 주장은 두 층으로 분리한다.

- **scope success:** 합성 truth에서 사전등록 회수 밴드 통과 + 실측 topology probe에서 사전등록 비율 이상의 새 cross-scope relation 생성
- **wall-system success:** 별도 라벨된 CAD validation에서 per-placed-instance 또는 명시된 projection 기준으로 precision/recall utility가 개선됨

v0는 첫 층만 판정한다. 둘째 층의 증거 없이 프로덕션 벽 탐지기 개선을 선언하지 않는다.

## 4. 데이터·컴퓨트 요구

### 4.1 필요한 데이터와 역할

| 데이터 | 패킷상 상태 | P6에서의 역할 | 허용 주장 |
|---|---|---|---|
| T0 split-wall micro-synthetic | 아직 구현 필요 | transform/scope oracle | 구현 정확성만 |
| PR-1 fidelity wall synthetic | 벽 생성기 부재가 선결 문제 | primary synthetic discrimination | fidelity gate 통과 뒤에만 프로그램 증거 |
| 1.dwg staged DXF | 384 defs, 최대 412,775 선분 | 실제 cheapest probe와 stress | 새 relation 생성; 사람 truth 아님 |
| CubiCasa5k SEG-IR | train/val/test 고정, 외부 사람 라벨 | schema identity-control, 조건부 val | INSERT가 없으면 비회귀만 |
| FloorPlanCAD raster | 5,308장, vector SVG 없음 | optional raster checksum | 직접 INSERT 효과 주장 금지 |

PR-1 synthetic generator에는 최소한 다음 family가 있어야 한다.

- 한 wall pair의 두 변을 서로 다른 defs에 둔 family
- 한 변은 modelspace, 다른 변은 child def에 둔 family
- nested INSERT 깊이를 바꾼 family
- 동일 def를 여러 배치하되 특정 배치에서만 상대 선과 맞는 family
- reflection, rotation, translation, unit-rescale family
- no-wall sentinel, single-line sentinel, 전벽 sentinel
- Door/Window/DimensionMark와 유사한 긴 평행 distractor family
- POLYLINE과 비평행 조각을 포함한 fidelity family

각 생성 사례는 geometry와 독립적으로 placed truth pair manifest를 함께 쓴다. truth를 탐지기의 pair predicate로 다시 계산해 만들면 자기확증이 되므로 금지한다.

### 4.2 로컬 실행 계획

주 실행 환경은 로컬 CPU와 RAM 64GB다. RTX 5070 Ti 16GB는 필요하지 않다.

1. parser와 transform oracle은 단일 프로세스 float64로 실행한다.
2. 전개 결과는 struct-of-arrays 또는 memory-mapped batch로 보관하되, provenance uid와 endpoint를 잃지 않는다.
3. STRtree는 global index를 만들고 query result를 batch 소비한다.
4. peak RSS는 외부 process sampler와 내부 단계별 counter 양쪽에서 기록한다.
5. 한 도면 내 결과 순서는 handle/path hash로 결정해 thread scheduling과 무관하게 만든다.
6. 병렬화는 정확성 oracle을 통과한 뒤 성능 셀에서만 허용한다. primary correctness run은 worker count 1로 고정한다.

proposed resource budget은 개발 전체 6–10 engineer-days, correctness/probe 실행 1 local CPU-day 이내, 최대 실도면 stress 2시간/48 GiB 이하다. 이는 새 실측치가 아니라 계획값이다.

### 4.3 DGX 계획

DGX Spark는 현재 unreachable이며 P6에 필요하지 않다. DGX를 기다리거나 결과의 선결조건으로 삼지 않는다.

- v0: DGX 호출 0, GPU 학습 0
- 후속: 대규모 여러 도면을 처리할 때도 우선 CPU spatial index의 도면별 병렬 배치로 확장한다.
- DGX가 복구되어도 transformer/VLM을 INSERT 전개에 도입하지 않는다. 의미 분류의 별도 downstream 연구가 승인될 때만 독립 method id로 사용한다.

### 4.4 저장·증거 예산

실험 실행 시 필수 산출물은 다음과 같다. 이 문서 작성 자체에서는 생성하지 않는다.

- prereg_p6.yaml: config와 합격선
- p6_manifest.json: 입력 파일 content hash, parser/config file content hash, eligible sample handles
- p6_provenance.parquet: placed_uid↔source handle↔path uid
- p6_pairs.parquet: folded/unfolded candidate와 features
- p6_evidence.xlsx: evidence_grid가 만드는 필수 증거 workbook
- p6_failures.jsonl: unsupported/cycle/resource abort 전량

xlsx에는 최소 manifest, prereg, transform_oracle, leakage, synthetic, real_probe, metamorphic, complexity, downstream, failures 시트가 있어야 한다. 실패 행을 삭제하거나 성공 행만 내보내면 dossier 계약 위반으로 본다.

## 5. 구현 계획

### 5.1 제안 파일 골격

실제 repository root와 현재 파일 배치는 패킷에 없으므로 다음은 **제안 상대경로**다. 구현 전 repository의 기존 구조에 맞게 이름만 매핑하되 책임 분리는 유지한다.

~~~text
e2/
  ir/
    insert_graph.py             # handle-only graph, integrity audit
    insert_unfold.py            # DFS expansion, placement provenance
    affine_adapter.py           # pinned parser transform adapter
  geometry/
    placed_segment.py           # canonical world segment schema
    world_pair_index.py         # STRtree/orientation query
    pair_predicate.py           # frozen exact geometry predicate
  detector/
    propose_for_ir.py           # scope_mode=per_def|world dispatch
  experiments/
    p6_split_synthetic.py       # T0 + PR-1 adapter
    p6_scope_probe.py           # frozen top-20/eligible-10 probe
    p6_metamorphic.py           # factorization and transform battery
    p6_complexity.py            # RSS/time/candidate counters
  metrics/
    p6_scope_metrics.py         # placed/source projections
  configs/
    prereg_p6.yaml
  tests/
    test_insert_transform_oracle.py
    test_path_hash_leakage.py
    test_world_pair_exactness.py
    test_p6_metamorphic.py
~~~

### 5.2 기존 도구별 접속점

**propose_for_ir**

- 기존 per_def branch를 삭제하지 않고 scope_mode=per_def를 대조군으로 보존한다.
- 새 scope_mode=world는 insert_unfold 결과만 candidate generator로 넘긴다.
- 두 branch의 normalizer와 pair_predicate 함수 object가 동일한지 runtime assertion으로 확인한다.

**fast_score**

- candidate pair features를 기존 vectorized schema로 변환한다.
- scope primary metric은 fast_score threshold와 독립적으로 pair predicate 회수를 보고한다.
- downstream 셀에서는 동일 candidate에 기존 weight를 적용하고, score 차이를 candidate-set 차이와 분리한다.

**evidence_grid**

- run 시작 시 prereg/config/content hash를 첫 시트에 봉인한다.
- handle과 path uid는 문자열로 써 Excel의 숫자 변환을 막는다.
- 각 PASS/FAIL/BLOCKED cell에 evidence row와 reason code를 필수화한다.

**cubicasa_ir / cubicasa_ml**

- cubicasa_ir adapter는 INSERT node count와 transform field presence만 schema audit한다. 결과를 보기 전 method config를 바꾸지 않는다.
- graph가 비어 있으면 folded/unfolded canonical pair set이 완전히 같은지 assert한다.
- cubicasa_ml 모델은 frozen artifact만 읽고 예측한다. P6 실험 중 fit 호출이 발생하면 실행을 실패시킨다.

### 5.3 개발 단계와 종료 조건

1. **M0 계약 봉인:** parser version, coordinate convention, unit policy, config, cell thresholds, sample selection rule를 prereg에 기록한다.
2. **M1 graph integrity:** missing target, cycle, array, nested path, orphan def를 감사한다. 완전성 gate가 실패하면 실측 실행 금지.
3. **M2 transform oracle:** hand-computed synthetic endpoint와 parser 결과를 대조한다.
4. **M3 exact pair equivalence:** 같은 한 scope 입력에서 기존 per_def와 새 index predicate가 동일 pair set을 내야 한다.
5. **M4 split synthetic:** primary discrimination을 실행한다.
6. **M5 metamorphic/leakage:** 이름 변화와 표현 factorization에 대한 invariance를 실행한다.
7. **M6 actual cheapest probe:** CL-A manifest가 있을 때만 10개 적격 def를 실행한다.
8. **M7 stress/downstream:** 자원 gate와 identity-control을 실행한다.
9. **M8 freeze:** evidence xlsx와 failure ledger를 완성한 뒤 decision rule을 기계적으로 적용한다.

각 단계는 이전 단계 PASS를 요구한다. BLOCKED를 PASS로 취급하지 않는다.

### 5.4 예상 개발 규모

제안 추정치는 다음과 같다.

- graph/transform/provenance: 2–3 engineer-days
- exact index와 folded equivalence: 1–2 engineer-days
- synthetic/metamorphic generator: 2–3 engineer-days
- evidence_grid, resource sampler, xlsx 검증: 1 engineer-day
- actual probe와 failure triage: 1 engineer-day

총 6–10 engineer-days를 제안 예산으로 잡는다. PR-1 공용 fidelity generator를 P6가 전부 소유하면 상한을 넘을 수 있으므로, micro-synthetic와 공용 generator 책임을 분리한다.

### 5.5 실패 처리 규약

- UNKNOWN_UNIT: 실제 pair threshold 결과 금지
- UNRESOLVED_XREF: 해당 도면 incomplete; partial PASS 금지
- DYNAMIC_BLOCK_UNSUPPORTED: 영향 placement 비율 공개; primary sample이면 BLOCKED
- GRAPH_CYCLE/MISSING_TARGET: integrity FAIL
- RESOURCE_ABORT: complexity FAIL
- SAMPLE_LT_10: actual cheapest probe BLOCKED
- LABEL_OR_NAME_IN_HASH: leakage FAIL
- TEST_SPLIT_TOUCHED_EARLY: protocol FAIL
- EVIDENCE_XLSX_MISSING: 전체 방법 FAIL

## 6. 실험 셀 정의

### 6.1 공통 프리레그

모든 셀에 다음 규칙을 적용한다.

- 결과를 보기 전에 config, code content hash, input content hash, selection manifest, threshold를 기록한다.
- deterministic algorithm에는 “seed 평균”을 만들지 않는다. 생성기나 순서 교란에만 seed를 쓴다.
- val은 개발·튜닝에 허용하지만 test는 방법 동결 뒤 단발이다.
- shuffle/rename 대조군과 zero-wall sentinel을 의무화한다.
- 셀 상태는 PASS, FAIL, BLOCKED, INCONCLUSIVE 네 값만 허용한다.
- 아래 반복 수와 gate는 제안값이며 아직 실행 결과가 아니다.

### 6.2 셀 P6-C0 — INSERT transform oracle

- **가설:** parser adapter의 누적 transform이 hand-authored 월드 endpoint와 일치한다.
- **입력:** identity, translation, rotation, uniform/nonuniform scale, reflection, nested depth, array cell, child/modelspace 조합을 포함한 고정 24 case.
- **지표:** endpoint max normalized error, placed_uid uniqueness, expected instance count, cycle/missing-target 검출률.
- **합격선:** 모든 정상 case의 endpoint error ≤ 1e-9 × max(1, extent), expected instance count 100% 일치, malformed case 100% fail-closed.
- **킬 조건:** 정상 transform 하나라도 틀림, cycle이 무한 전개됨, silent drop 발생.
- **예산:** 로컬 CPU 10분 이내, RAM 1 GiB 이내의 제안 budget.
- **시드:** 없음. case manifest 고정.

### 6.3 셀 P6-C1 — handle-only 누수·동치 감사

- **가설:** block/layer 이름과 외부 라벨을 바꿔도 traversal, placed_uid, pair set이 변하지 않는다.
- **입력:** C0 정상 case의 block name, layer name, entity order, truth column을 독립 shuffle한 5개 mutation seed.
- **지표:** path uid equality, placed geometry equality, pair uid equality, serialized graph field allowlist, forbidden token scan.
- **합격선:** 이름/라벨 mutation에서 세 equality 1.0, graph serialization의 forbidden field 0개.
- **킬 조건:** 이름이나 라벨이 hash, candidate selection, dedup에 사용됨; truth shuffle에 출력이 반응함.
- **예산:** 로컬 CPU 15분, RAM 1 GiB.
- **시드:** P6L-01부터 P6L-05까지 사전 기록.

### 6.4 셀 P6-C2 — split-wall 합성 판별

- **가설:** 참 wall ribbon의 양변이 scope를 가로지를 때 folded는 의도적으로 놓치고 unfolded는 회수한다.
- **입력:** 5 generator seeds × 20 case의 제안 설계. 각 seed는 cross-def, child/modelspace, nested, repeated-placement-context, same-def control, no-wall/distractor를 균형 있게 포함한다.
- **primary metric:** split family의 placed-instance pair recall.
- **보조 metric:** placed-handle precision, same-def non-regression, zero-wall false proposal rate.
- **합격선:** 패킷의 핵심 밴드인 folded recall ≤ 0.2이고 unfolded recall ≥ 0.9. 추가 안전 gate로 unfolded placed-handle precision ≥ 0.9, zero-wall sentinel proposed handle 0개, same-def control의 folded/unfolded pair set agreement 1.0.
- **킬 조건:** 검증된 transform에서도 unfolded recall < 0.9, folded recall > 0.2라서 생성기가 판별을 만들지 못함, 또는 sentinel 오탐으로 recall이 무의미해짐.
- **예산:** 로컬 CPU 1시간, RAM 4 GiB.
- **시드:** P6S-01부터 P6S-05. seed별 결과와 pooled 결과를 모두 기록하고 평균만 보고하지 않는다.
- **해석 제한:** PR-1 fidelity gate가 FAIL이면 이 셀은 구현 oracle PASS일 수는 있어도 프로그램 수준 H_world 지지로 승격하지 않는다.

### 6.5 셀 P6-C3 — 표현·변환 metamorphic battery

- **가설:** 동일한 월드 벽을 modelspace, 한 def, 두 defs, nested INSERT, explode로 표현해도 unfolded canonical geometry pair set은 같다.
- **입력:** 20개 base layout에 representation factorization, entity reorder, block/layer rename, rigid rotation/translation/reflection, unit metadata 보상 rescale을 적용한다.
- **지표:** geometry-mapped pair-set agreement, placed truth recall difference, source-projection disagreement, unsupported count.
- **합격선:** geometry-mapped pair-set agreement 1.0, placed truth recall difference 0, representation별 unsupported count 0.
- **킬 조건:** def 분할만 바꿨는데 pair가 달라짐; 이름 변경에 결과가 달라짐; unit metadata를 함께 보상한 rescale에서 결과가 달라짐.
- **예산:** 로컬 CPU 2시간, RAM 8 GiB.
- **시드:** base generator P6M-01부터 P6M-04, 각 seed 5 layout. transform 목록은 고정.
- **주의:** 좌표만 scale하고 물리 단위 metadata를 보상하지 않는 변환은 P2의 절대/상대 대역 논쟁이므로 P6 invariance gate에 넣지 않는다. 기존 scale 팔 0.7624 FAIL과 scope 효과를 혼동하지 않는다.

### 6.6 셀 P6-C4 — 1.dwg cheapest actual probe

- **가설:** CL-A 재계산 top-20 중 실제로 배치 가능한 INSERT-child def에서 unfolded가 folded에 없던 cross-scope pair를 만든다.
- **표본:** 3.1의 규칙으로 고정한 적격 10개 def. 10개 미만이면 BLOCKED.
- **지표:** def별 folded pair count, unfolded pair count, new_cross_scope_pair count, cross-placement-only count, unsupported fraction, resource counter. primary는 new_cross_scope_pair가 하나 이상인 def의 비율이다.
- **합격선:** 적격 10개 중 최소 3개, 즉 ≥30%에서 new_cross_scope_pair 생성. anonymous-name reporting cohort가 별도로 충분하면 같은 ≥30%를 기술하되 primary topology cohort를 대체하지 않는다.
- **킬 조건:** graph/unit audit가 통과했는데 10개 모두 0개; 추가분이 모두 같은 scope의 반복 복제 또는 duplicate artifact; unsupported 때문에 denominator를 사후 축소.
- **중간 판정:** 1–2개면 INCONCLUSIVE/NO-GO이며 PASS가 아니다.
- **예산:** 로컬 CPU 4시간, peak RSS 48 GiB 이내.
- **시드:** 없음. rank와 handle tie-break로 결정.
- **해석 제한:** 사람 truth가 없으므로 이는 scope relation 생성 gate다. “실제 벽 정답 회수율”로 쓰지 않는다.

### 6.7 셀 P6-C5 — 복잡도·메모리 kill test

- **가설:** exact world pairing이 제곱 후보 폭발 없이 64GB 로컬 머신에서 실용적으로 끝난다.
- **입력:** synthetic density ladder 25k, 50k, 100k, 200k, 400k placed segments와 1.dwg 최대 규모 경로. synthetic 수치는 제안 stress 크기다.
- **지표:** traversal/index/query wall time, peak RSS, N/Q/C/P, Q/N, C/N, log-log empirical slope, abort reason.
- **합격선:** 1.dwg 최대 경로가 lossy cap 없이 2시간 이하, peak RSS 48 GiB 이하, max_exact_candidates 50,000,000 미만에서 완료. density ladder의 마지막 두 점 empirical time slope ≤ 1.5를 보조 gate로 둔다.
- **킬 조건:** 실제 경로가 ceiling에 닿음, RSS/시간 gate 초과, 결과를 얻으려면 top-k/sampling이 필요함, 또는 pair materialization이 사실상 제곱으로 증가.
- **예산:** 로컬 CPU 총 8시간, 각 단계 timeout 2시간, RAM 48 GiB gate.
- **시드:** 구조 seed P6X-01부터 P6X-03. worst-case parallel dense와 typical sparse를 분리 보고.

### 6.8 셀 P6-C6 — downstream 비회귀와 평가단위 감사

- **가설:** INSERT graph가 없는 IR에서는 world mode가 identity이고, INSERT graph가 있는 경우 placed/source projection의 차이가 명시적으로 드러난다.
- **입력:** CubiCasa val의 schema audit 결과에 따른 전량 val identity check 또는 조건부 scope run; 합성 repeated-placement-context family; frozen fast_score와 frozen GBDT.
- **지표:** canonical candidate pair equality, fast_score equality, frozen model prediction equality, placed-vs-source confusion table, fit-call count.
- **합격선:** INSERT가 없는 IR에서는 세 equality 1.0과 fit-call 0. INSERT가 있으면 결과를 개발용 val diagnostic으로 보고하고 C2/C4 gate를 사후 변경하지 않는다.
- **킬 조건:** graph가 없는데 예측이 변함; source projection만으로 placement 오차가 숨겨짐; P6 실행 중 모델 재학습이 발생함.
- **예산:** val 400만 사용, 로컬 CPU 4시간, RAM 32 GiB. test 400 접근 0회.
- **시드:** deterministic. GBDT artifact 고정.

### 6.9 셀 P6-C7 — 동결 후 confirmatory one-shot

- **실행 조건:** C0–C6의 필수 gate가 모두 PASS이고 PR-1 fidelity gate가 통과하며 code/config/input family가 content hash로 동결된 뒤에만 연다.
- **입력:** 결과를 보지 않은 hidden synthetic mutation family. 별도의 insert-bearing 라벨 CAD test가 제공되면 그 데이터는 방법당 단발로 추가할 수 있으나, 현재 패킷에는 그런 자산이 명시되지 않았으므로 있다고 가정하지 않는다.
- **가설/합격선:** C2의 folded ≤ 0.2, unfolded ≥ 0.9 밴드와 precision/sentinel gate를 그대로 재사용한다.
- **킬 조건:** hidden family에서 band 실패, 재실행 요구, threshold 수정 요구.
- **예산:** 로컬 CPU 2시간, 1회.
- **시드:** prereg 때 봉인한 P6H-01 하나. 결과 확인 뒤 seed 교체 금지.
- **CubiCasa test 정책:** schema audit상 world mode가 identity면 test를 소비하지 않는다. 비동일 효과가 있고 P6 방법이 완전히 동결된 경우에만 기존 test 400을 한 번 쓴다.

### 6.10 종합 판정 함수

~~~text
if any of C0, C1 is FAIL:
    verdict = INVALID_IMPLEMENTATION
elif C2 misses its primary band:
    verdict = KILL_COUNTER_OR_GENERATOR
elif C3 is FAIL:
    verdict = KILL_IMPLEMENTATION
elif C4 is BLOCKED:
    verdict = BLOCKED_REAL_EVIDENCE
elif C4 rate == 0:
    verdict = KILLS_COUNTER_FOR_CURRENT_E2_CORPUS
elif C4 rate < 0.30:
    verdict = INCONCLUSIVE_NO_GO
elif C5 is FAIL:
    verdict = KILL_PRACTICALITY
elif required evidence xlsx is missing:
    verdict = PROTOCOL_FAIL
else:
    verdict = SUPPORTS_WORLD_SCOPE_AND_KILLS_DEF_QUOTIENT
~~~

C6는 회귀·평가단위 안전 gate다. C7은 confirmatory gate다. 어떤 상태에서도 새 pair count만으로 semantic wall-system PASS를 선언하지 않는다.

## 7. red team 티켓 응답

패널 보고서가 티켓 34건의 상세 원문을 모두 싣지는 않았으므로, 아래는 패킷 안에서 의미가 식별되는 티켓만 다룬다. 의미가 제공되지 않은 티켓을 임의로 해소했다고 쓰지 않는다. 모든 티켓은 실제 증거가 생길 때까지 OPEN이다.

| 티켓/공격 | P6 관련성 | 응답과 close 조건 |
|---|---|---|
| T1 / 공격 A: truth proxy 독립성 | 합성·metamorphic·actual pair count가 같은 평행 prior를 공유할 수 있다. | 세 출처를 평균해 하나의 confidence로 만들지 않는다. 합성은 placed truth, metamorphic은 표현 불변성, actual은 relation 생성으로 서로 다른 주장만 담당한다. 동일 사례에 대해 세 축의 일치/불일치 contingency를 evidence_grid에 기록한다. 독립 사람 CAD 라벨 없이는 semantic close 금지. |
| T2 / PR-1: 벽 합성 생성기 부재 | P6 primary synthetic gate의 직접 선결이다. | micro-synthetic를 transform oracle로만 제한하고, divergent 현상을 포함한 공용 generator와 fidelity gate를 별도로 요구한다. fidelity FAIL이면 C2를 프로그램 증거로 승격하지 않는다. |
| T3 / 공격 C: divergence 정렬-키 아티팩트 | actual top-20 표본 자체가 오염될 수 있다. | CL-A가 정렬을 재계산한 frozen manifest가 C4의 입력 선결이다. 이전 top-20을 재사용하지 않는다. 재계산 전에는 C4=BLOCKED다. |
| T4: ornith 원시 조달 | P6가 직접 고칠 항목은 아니지만 CL-A 표본의 완전성에 영향을 줄 수 있다. | P6는 Ornith 판단을 truth로 사용하지 않는다. CL-A manifest가 T4 때문에 미완성이면 C4를 보류한다. 상세 close는 CL-A 소유다. |
| T5 / 공격 D: 외부셋 권리 | CubiCasa/FloorPlanCAD를 새 학습에 쓰면 걸린다. | P6 v0는 1.dwg와 자체 synthetic가 주축이며 외부셋 재학습을 하지 않는다. CubiCasa는 승인 범위의 schema/val 비회귀만 계획하되, counsel이 이를 허용하지 않으면 C6 외부 arm을 BLOCKED 처리한다. 라이선스 위험을 기술 해결로 우회하지 않는다. |
| T6 / 공격 E: 평가 단위 | source handle과 placed instance가 다르다. | assembly output을 placed_uid로 격리하고, source handle projection 3종을 별도 보고한다. 프로그램 공용 per-handle 점수와 직접 합치지 않는다. 향후 공용 계약이 placed-instance를 채택하거나 명시 aggregation을 승인해야 wall-system claim이 가능하다. |
| T7 / 공격 F: 0벽 탐지기 통과 | recall/위반율만 보면 퇴행을 숨길 수 있다. | no-wall, single-line, all-wall sentinel과 precision gate를 C2/C3에 의무화한다. zero proposal만으로 recall gate를 통과할 수 없다. |
| T8 | 패널은 CL-A의 hard prerequisite로만 언급하고 상세 의미를 주지 않았다. | 의미를 발명하지 않는다. CL-A 완료 manifest의 required-ticket list에 T8 close evidence가 없으면 C4를 BLOCKED 처리한다. |
| T9/T21: v0 baseline 선계측 | folded baseline을 사후 재구성하면 비교가 오염된다. | 동일 commit 대신 동일 **content hash**의 parser/normalizer/predicate로 folded를 먼저 실행하고 evidence에 봉인한다. unfolded 결과를 보기 전에 baseline row를 닫는다. |
| T10/T23: Graph IR adjacency 완전성 | 누락 INSERT edge는 P6를 거짓 음성으로 만든다. | M1 integrity audit에서 root reachability, target resolution, cycle, orphan, array, nesting, unsupported를 전량 계수한다. primary sample의 unresolved edge는 FAIL/BLOCKED이며 silent skip 금지. |
| T16: 절대 vs 상대 gap band | P2 논쟁이 P6 scope 효과와 섞일 수 있다. | P6에서는 기존 50–400 mm 대역을 양 arm에 고정한다. unit metadata 보상 rescale만 invariance로 본다. 상대 대역 비교는 별도 method id/요인으로 수행한다. |
| T24: pixel↔handle exact harness | FloorPlanCAD를 truth로 쓰려 할 때 걸린다. | exact harness가 없으므로 raster를 primary gate에서 제외한다. optional raster checksum은 semantic mapping 주장을 하지 않는다. |
| T31: raster가 coverage 수정보다 낫다는 주장 | P6가 회수하는 zero-pair와 raster 본선의 효용 경계다. | P6를 먼저 실행해 vector coverage 회수량을 분리한다. raster 우월성은 이 결과를 넘어서는 독립 회수와 exact mapping이 있을 때만 평가한다. |
| T34: 인용 R-lane experiment_executed:false | 문헌과 패널 인용을 실행 증거처럼 쓸 위험이다. | 본 문서의 선행연구는 전부 literature/general-knowledge 상태이며 experiment_executed:false다. 실제 실행 주장에는 p6_evidence.xlsx row만 허용한다. |
| R12 kill risk: quadratic 후보 폭발 | P6의 명시적 kill condition이다. | C5에서 candidate ceiling, RSS, time, scaling을 사전등록한다. lossy sampling으로 PASS를 만들지 않는다. |

추가로 panel의 T13(DGX vision), T14/T33(layer lexicon), T22(P1 대비 lift), T26(RL verifier), T27(room-first), T31 외 raster 세부는 P6 core 실행의 직접 close 책임이 아니다. 관련 기능을 끌어와 범위를 넓히지 않는다.

## 8. 인접 제안과의 관계 및 사망 조건

### 8.1 병합 가능한 지점

**CL-A E1 법의학 감사**

- C4 표본 manifest와 unit audit의 선결 제공자다.
- CL-A가 divergence가 정렬 아티팩트였다고 밝히면 P6는 이전 top-20을 버리고 재계산 cohort로만 시험한다.
- CL-A가 모든 관련 divergence를 계측 아티팩트로 해소하면 P6 actual priority는 낮아지지만, synthetic scope 결함 자체는 별도로 남을 수 있다.

**CL-B coverage-complete deterministic v1**

- P6는 CL-B의 transform 전개 구성요소로 직접 병합 가능하다.
- LWPOLYLINE/MLINE/ARC normalization, unit anchoring, junction filter와 인터페이스를 공유한다.
- 그러나 scope, primitive coverage, unit band, semantic filter를 한 번에 바꾼 factorial cell을 primary 판별로 삼지 않는다. P6 단독 ablation이 먼저다.

**CL-C wall synthetic/WSD-EVAL-v1**

- placed_uid truth extension이 필요하다.
- 공용 계약이 source per-handle만 허용하면 P6 assembly 산출물을 별도 task로 격리한다.
- generator fidelity는 P6가 임의로 PASS할 수 없는 프로그램 선결이다.

**CL-D metamorphic battery**

- INSERT↔explode, one-def↔split-def 변환을 공용 battery에 추가할 수 있다.
- 기존 rigid/unit invariance와 같은 evidence format을 쓰되, 물리 단위 보상 없는 scale은 P2 요인으로 분리한다.

**CL-E truth-source 교차요인**

- P6 synthetic, actual relation, metamorphic 결과를 동일-def contingency에 한 축으로 공급할 수 있다.
- 세 proxy의 숫자를 평균해 독립 증거처럼 보이게 하지 않는다.

**CL-F GBDT/GNN 학습 사다리**

- P6는 학습기의 upstream candidate recall을 바꾼다.
- 새 CAD 후보에 대해 geometry feature를 만들 수 있지만, CubiCasa GBDT의 val F1 0.517을 P6 성과로 재포장하지 않는다.
- 후보 공간이 커진 뒤 classifier가 precision을 회복하는지는 별도 라벨 CAD validation 문제다.

**P2 상대 두께, P1 face-first, P3 anti-silver, P5 raster, P7 관례 prior**

- P2는 threshold coordinate system, P6는 relation scope이므로 2×2 후속 실험이 가능하다.
- P1은 관측 primitive 자체를 face/room으로 바꾸므로 P6와 더 근본적인 경쟁 관계다. P6가 죽어도 P1은 살아남을 수 있다.
- P3은 silver 오염 통제이며 P6 traversal에는 silver를 넣지 않는 것으로 자연스럽게 정렬된다.
- P5 raster는 INSERT graph가 없는 별도 representation이다. P6 vector coverage 결과를 먼저 넘어서야 한다.
- P7 layer/name prior는 P6 handle-only graph와 orthogonal하다. reporting join은 가능하지만 traversal selection에 합치지 않는다.

### 8.2 차별점

P6가 주장하는 유일한 새 메커니즘은 **관계 평가 전에 authoring partition을 제거하고 실제 placement context를 복원한다**는 것이다.

- primitive normalization 개선이 아니다.
- 두께 band 튜닝이 아니다.
- GBDT/GNN/VLM 분류기가 아니다.
- layer-name prior가 아니다.
- room topology 추론이 아니다.
- 더 많은 후보를 무조건 벽이라고 부르는 recall trick이 아니다.

따라서 folded와 unfolded 사이에 이 한 요인 외의 코드 경로 차이가 생기면 실험은 무효다.

### 8.3 이 제안이 죽어야 하는 조건

다음 중 하나면 정직하게 P6를 중단하거나 강등한다.

1. **transform 불성립:** C0가 통과하지 못하고 parser 공식 의미를 확인해도 고칠 수 없다.
2. **누수:** 이름, layer, silver, truth가 graph key나 candidate selection에 들어간다.
3. **합성 판별 실패:** 검증된 split truth에서 folded ≤0.2와 unfolded ≥0.9 밴드를 만들지 못한다.
4. **실측 무효:** CL-A 재계산 후 적격 10개를 만들 수 없거나 unit/graph completeness를 확인할 수 없다. 이 경우 PASS가 아니라 BLOCKED다.
5. **실측 반증:** 적격 10개 모두에서 new_cross_scope_pair가 0이다. 현재 E2 corpus에 대한 counter-theory를 죽인다.
6. **효과 부족:** 실제 생성률이 30% 미만이다. 1–2/10을 성공 사례로 포장하지 않는다.
7. **중복 착시:** 새 쌍이 모두 반복 배치의 count inflation, same-scope duplicate, geometry alias다.
8. **복잡도 사망:** 412,775 선분 규모에서 exact 결과가 2시간/48 GiB/candidate ceiling 안에 끝나지 않고, lossy cap 없이는 실용화할 수 없다.
9. **지원범위 사망:** target cohort의 이득이 unresolved dynamic block/xref에 의존해 현재 IR로 재현할 수 없다.
10. **평가단위 불일치:** placed-instance 문맥을 source handle로 투영할 때 상반된 의미가 지워지고, 프로그램이 assembly task 분리를 받아들이지 않는다.
11. **semantic 무익:** 후속 독립 라벨 CAD validation에서 새 후보가 벽 precision/utility를 회복하지 못한다. 이 경우 scope 메커니즘은 과학적으로 참이어도 제품 방법으로는 죽는다.
12. **더 싼 설명:** CL-A가 divergence를 정렬·handle·bbox 단위 아티팩트로 완전히 설명하고, 재계산 cohort에서 P6 actual 효과가 사라진다.
13. **증거 계약 실패:** prereg 이전 결과 열람, test 조기 접근, 누락된 xlsx, 실패 행 삭제, threshold 사후 변경이 발생한다.

### 8.4 최종 실행 체크리스트

- [ ] CL-A 재계산 top-20 manifest와 ticket close 상태를 받았다.
- [ ] unit_mm와 parser transform 의미를 문서·oracle로 확인했다.
- [ ] INSERT adjacency/root reachability/array/cycle/xref audit를 완료했다.
- [ ] prereg와 모든 content hash를 결과 열람 전에 봉인했다.
- [ ] folded baseline을 같은 normalizer/predicate로 먼저 기록했다.
- [ ] C0–C3을 순서대로 통과했다.
- [ ] actual 적격 표본 10개를 대체 없이 고정했다.
- [ ] C4 결과를 “새 relation”과 “벽 truth”로 구분해 썼다.
- [ ] C5에서 partial/truncated 결과를 PASS하지 않았다.
- [ ] CubiCasa test를 조기에 건드리지 않았다.
- [ ] placed-instance와 source-handle projection을 모두 기록했다.
- [ ] shuffle, no-wall, all-wall sentinel을 포함했다.
- [ ] evidence_grid xlsx와 failure ledger가 존재하고 서로 row count가 맞는다.
- [ ] 종합 판정 함수를 사람 재해석 없이 적용했다.

이 설계가 성공하면 “def 안 n_pairs=0”은 벽 부재 사실이 아니라 작성 단위에 의한 관측 손실로 재분류된다. 실패하면 per_def를 무조건 옹호하는 것이 아니라, 적어도 현재 E2 자산·IR·컴퓨트 안에서 world assembly가 추가 복잡도를 정당화하지 못한다는 구체적 반증을 남긴다.

DOSSIER_COMPLETE: feyerabend_P6
