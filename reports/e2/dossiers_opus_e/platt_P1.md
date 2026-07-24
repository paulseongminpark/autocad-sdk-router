# E2 방법론 심층 도시에 — platt_P1

**제안**: P1 — 커버리지-완전 결정론 탐지기 v1 (엔티티 정규화 + 정션 후필터 · 결정론)
**좌석(seat)**: platt_strong_inferencer (강한 추론가 좌석) · 제안 슬롯 P1
**가설**: H1(기하 충분 — "벽은 국소 기하만으로 인식 가능하다")의 **최강 형태**를 만들어 시험한다.
**한 줄 주장**: "v0 결정론 탐지기의 실패는 개념(concept)이 아니라 커버리지(coverage)다 — 탐지기가 기하를 못 본 것이지, 기하가 벽을 못 담은 것이 아니다."

---

## 0. 읽는 법 · 수치 출처 규율 (먼저 읽어주세요)

이 도시에(dossier = 하나의 제안을 실행 가능한 실험 계획으로 완전히 풀어낸 심층 조사 문서)는 두 종류의 수치만 씁니다.

- **실측(measured)**: 이 패킷 §"실측 다이제스트"에 적힌 숫자. 예: 전이 F1 0.2358, GBDT F1 0.517. 이 도시에 안에서 `[실측]`으로 표시하고 그 외 새 측정은 주장하지 않습니다.
- **문헌·일반지식(literature)**: 방법론 계보를 설명하려고 부르는 외부 시스템·논문. 확신이 낮은 인용은 `[요검증]`으로 표시합니다(패널이 반입 전 확인). 웹 검색은 사용하지 않았습니다.

**용어 사전(coined terms, 처음 나올 때 풀되 여기 모아둠)**:
- **커버리지(coverage)**: 탐지기가 실제로 "보는" 기하의 양. LWPOLYLINE을 세그먼트로 분해하지 않으면, 그 안에 든 벽은 탐지기 입장에서 존재하지 않는다 → 커버리지 0.
- **디스크리미네이션(discrimination)**: 본 기하 중 무엇이 벽인지 가르는 능력. 평행 이중선을 보긴 봤는데 그게 벽인지 문·창·치수선인지 못 가리면 디스크리미네이션 실패.
- **정규화 프런트엔드(normalization frontend)**: 어떤 엔티티 타입이 들어와도 "월드 좌표계의 원시 세그먼트 목록 + 공통 단위"로 펴주는(flatten) 전처리 계층. P1이 v0 앞에 새로 붙이는 것.
- **정션 그래프 후필터(junction-graph post-filter)**: 벽 쌍 후보들이 서로 끝점에서 만나 체인·교차로(L·T·X)로 이어지는가를 그래프로 판정해, "네트워크에 속한 쌍"만 살리고 "고립된 쌍"은 버리는 결정론적 비선형 판별기.
- **wall_member(h)**: 핸들(handle = 도면 안 개별 엔티티/세그먼트의 ID) h가 벽 부재인가 아닌가의 0/1 라벨. 이 프로그램의 공통 평가 단위(CL-C 계약).

**본 도시에의 핵심 결론 미리보기 (executive thesis)** — 뒤 절들이 이걸 논증합니다:

> P1의 가치는 **축(axis)에 따라 갈린다.** 실도면(1.dwg) 축에서 문제의 본질은 *커버리지*이고 P1이 정면으로 이긴다(벽-제로 도면을 회수). 반면 CubiCasa 벡터 축에서 문제의 본질은 이미 *디스크리미네이션*이며(SEG-IR로 이미 세그먼트화됨 → 정규화가 거의 no-op), 여기서 P1이 새로 거는 유일한 레버는 정션 후필터 하나다. 그래서 P1은 두 가지를 동시에 한다: (1) **모든 하위 방법(GBDT·GNN·VLM 포함)이 공유해야 하는 필수 전처리·커버리지 계층**을 제공하고, (2) 디스크리미네이션 축에서 **H1-강형을 정직하게 반증(falsify)하는 시험지**가 된다. 후자에서 P1이 죽을 확률은 낮지 않다 — 그리고 그 죽음은 "기하 지배" 주장을 깔끔히 강등시키는, 값싸고 결정적인 판별 정보다.

---

## 1. 이론적 근거 · 선행연구 (methodological lineage)

### 1.1 계보: "이중 평행선 = 벽"이라는 오래된 프라이어(prior)

건축 도면에서 벽을 **평행한 두 선(double-line / parallel-pair)** 으로 보는 것은 벡터 플로어플랜 파싱의 고전 프라이어다. 이 관점의 뿌리:

- **Dosch et al. (2000), "A complete system for the analysis of architectural drawings"** [요검증 — 저자/연도] — 벽을 평행선 쌍으로, 문·창을 그 사이의 심볼로 파싱하는 초기 완결 시스템. P1의 v0 휴리스틱이 정확히 이 계열이다.
- **Ahmed et al., "Automatic Room Detection and Room Labeling from Architectural Floor Plans"** [요검증] — 두께 임계로 벽/얇은 선을 분리하고 방을 닫힌 루프로 검출. P1의 "두께 대역 + 정션 후필터로 방-경계 네트워크 회수"와 직접 대응.
- **de las Heras et al., CVC-FP 데이터셋 / 벽 세분화 계열** [요검증] — 벽 세분화를 벤치마크로 세운 계열. 우리 프로그램의 "같은 시험지로 방법을 겨룬다"는 정신과 동형.

이 계보의 핵심 약점이 곧 P1의 시험 대상이다: **평행-쌍 프라이어는 커버리지(무엇을 세그먼트로 보느냐)와 디스크리미네이션(평행 쌍 중 무엇이 벽이냐) 두 실패원을 뭉뚱그린다.** P1은 커버리지를 완전화해서 이 둘을 **분리 계측**하는 것이 방법론적 기여다.

### 1.2 정규화·평탄화(flatten)의 계보 — 연구가 아니라 CAD 엔지니어링

정규화 프런트엔드가 하는 일은 새 연구가 아니라 CAD 처리의 표준 연산이다(그래서 오히려 "왜 v0가 이걸 안 했나"가 핵심 질문이 된다):

- **LWPOLYLINE 폭발(explode)**: 연속 정점쌍을 LINE 세그먼트로, bulge(호 세그먼트)를 ARC로 분해 — DXF/DWG 처리의 기본기. 우리 라우터 스택의 `ezdxf` 계열이 제공하는 원시 연산에 해당[일반지식].
- **INSERT/블록 평탄화**: 블록 참조를 그 정의로 치환하고 변환행렬(이동·회전·스케일·미러)을 합성해 자식 엔티티를 월드 좌표로 전개, 중첩(nested) 블록은 재귀. 이것이 feyerabend P6가 "코드 확정 결함 정타"라 부른 지점 — v0가 월드 좌표 전개를 빼먹었다는 주장.
- **MLINE 전개**: MLINE(AutoCAD의 다중선 엔티티)은 **정의상 평행선 묶음**이다. 스타일의 오프셋대로 전개하면 그 자리에서 벽-쌍 후보가 나온다. 벽이 MLINE으로 그려진 도면에서 v0가 벽을 0개 찾았다면, 그건 개념 실패가 아니라 MLINE을 안 편 커버리지 실패다.
- **단위 정규화(INSUNITS/bbox)**: 헤더의 INSUNITS로 단위를 읽고, 없으면 bbox 휴리스틱으로 축척 추정(P0 산출 소비) 후 캐노니컬 단위(mm)로 변환. 이것이 B4 scale 팔 FAIL(0.7624 [실측])을 직접 겨눈다(§6 C6).

### 1.3 정션 그래프 · 위상(topology) 계보

"벽은 서로 만나 방을 닫는 연결 구조를 이룬다; 치수선·가구 조각은 고립돼 있다"는 통찰은 위상 기반 플로어플랜 복원의 핵심이다:

- **Liu et al. (2017, ICCV) "Raster-to-Vector: Revisiting Floorplan Transformation"** [요검증 — 정확한 제목/venue] — 접합점(junction) 검출 후 정수계획으로 벽 그래프를 복원. P1의 정션 후필터는 이 아이디어의 **학습-0 결정론 버전**이다.
- **Chen et al., "Floor-SP" (2019, ICCV) / "HEAT" (2022, CVPR)** [요검증] — 방 루프 최단경로 / 엣지-어텐션으로 구조를 복원. 이들은 DL이지만, 공통 전제("벽=평면 그래프의 엣지, 방=면(face)")는 P1의 후필터와 calibration P1(centerline→arrangement), feyerabend P1(room-first)이 공유한다.
- **계산기하 뿌리**: 선분 배열(line arrangement), 오프셋 폴리곤, 중심선/메디얼 축(medial axis, 복도의 중심선으로서의 벽). CL-J가 지목한 GEOS(비-GPL 로버스트 폴리곤 엔진)가 이 연산의 표준 구현[일반지식].

### 1.4 "커버리지 vs 개념"이라는 ML 인식론적 프레이밍

P1의 주장은 ML의 고전적 오차 분해와 동형이다: **표현 오차(representation error, 입력이 신호를 안 담음) vs 모델 오차(model error, 담긴 신호를 못 씀).** 전이 F1 0.2358 [실측]이라는 낮은 성적을, P1은 "표현(커버리지) 오차"로 귀속하려 하고, GBDT 0.517 [실측]은 "모델 오차가 크다(비선형 학습이 필요하다)"는 반대 증거다. **이 둘 중 어느 쪽이 지배적인지를 분리 계측하는 것이 P1의 존재 이유다.** (§3·§6 C8 ablation이 이 분해를 실행한다.)

한 가지 인식론적 못박기: **결정론 ≠ 선형(linear).** 다이제스트에서 로지스틱(선형)은 F1 0.053, GBDT(비선형)는 0.517 [실측]이다. 즉 6-특징 공간에서 벽/비벽 경계는 **비선형**이다. 그런데 v0의 탐지기는 4채널 *가중합*(parallel 0.35/thickness 0.25/junction 0.20/layer 0.20 [실측]) — 사실상 선형 결합이라 0.053 로지스틱과 같은 선형 천장에 갇힌다. **정션 그래프 후필터는 결정론적이지만 본질적으로 비선형·조합적(combinatorial)** 이다(연결성분·체인·루프는 특징의 임계·논리곱). 그래서 P1의 진짜 과학적 질문은:

> **벽/비벽을 가르는 그 비선형이 "위상적(topological)"인가 — 즉 정션 그래프로 결정론적으로 인코딩 가능한가 — 아니면 "통계적(statistical)"이어서 학습이 있어야만 잡히는가?**

P1이 위상적이라면 GBDT의 우위는 "특징 표현의 문제"였고 결정론으로 회수된다. 통계적이라면 H1-강형은 죽고 H2(학습)가 승계한다. 이건 값싸게 판별된다.

---

## 2. 알고리즘 정확 스펙 (exact algorithm spec)

P1은 **경사·손실이 없는 결정론 파이프라인**이다. "손실"은 없고, 하이퍼파라미터 선택 시에만 목적함수(F1)를 쓴다. 3-스테이지.

### 2.1 입력 / 출력 계약

```
입력  : DrawingIR — 엔티티 목록. 각 엔티티 e = {
            type ∈ {LINE, LWPOLYLINE, MLINE, ARC, INSERT, SPLINE, HATCH, ...},
            geom,                 # 타입별 원시 좌표
            layer,                # (P1은 사용하지 않음 — 레이어-중립, §3.4)
            xform_ctx             # 부모 INSERT로부터 누적된 변환(있으면)
          }
          + header: {INSUNITS?, extmin/extmax(bbox), ...}
          + P0_unit_hint         # CL-A/P0 산출: bbox 기반 단위 판정 근거
출력  : {h → wall_member(h) ∈ {0,1}} for every primitive handle h
          + 프로버넌스(provenance): h가 어느 정규화 경로/어느 쌍/어느 정션-성분에서 왔는지
          + per-def 감사 레코드: 단위 판정 근거(INSUNITS vs bbox-heuristic), 후보 수, 성분 크기 분포
```

`wall_member(h)`를 최종 단위로 고정하는 이유: CL-C의 공통 평가 계약이며, "집합-조립(assembly)"과 분리해야 red team 공격 E(T6, 평가 단위 혼동)를 피한다(§7).

### 2.2 Stage 0 — 정규화 프런트엔드 (P1의 신규 코어)

의사코드:

```
def normalize(DrawingIR) -> list[Segment]:
    segs = []
    scale = resolve_unit(header.INSUNITS, header.bbox, P0_unit_hint)   # → mm 환산 계수
    for e in DrawingIR.entities:
        for prim in expand_entity(e, xform=identity):                 # 재귀 평탄화
            segs.append( to_mm(prim, scale) )
    return dedup_collinear(segs)      # 완전 중복·공선 병합(후보 폭발 억제, R12)

def expand_entity(e, xform):
    if e.type == LINE:        yield apply(xform, e.as_segment())
    elif e.type == LWPOLYLINE:
        for (v_i, v_{i+1}, bulge) in e.vertex_pairs():
            if bulge == 0: yield apply(xform, Segment(v_i, v_{i+1}))
            else:          yield apply(xform, Arc.from_bulge(v_i, v_{i+1}, bulge))
    elif e.type == MLINE:
        for line_el in e.style.offsets():          # 다중선 → 평행 라인 원소들
            yield apply(xform, line_el.as_segment())   # ← 즉석 벽-쌍 후보
    elif e.type == ARC:
        yield apply(xform, e.as_arc())             # 동심 오프셋쌍은 Stage 1에서 매칭
    elif e.type == INSERT:
        M = compose(xform, e.transform)            # 이동·회전·스케일·미러 합성
        if depth(M) > DEPTH_CAP: emit_audit("insert_depth_exceeded"); return
        for child in blockdef(e.name).entities:    # 블록 정의 재귀 전개
            yield from expand_entity(child, xform=M)
    elif e.type in {SPLINE}:
        yield from tessellate(e, chord_tol=TESS_TOL)   # 호/스플라인 → 폴리라인
    elif e.type in {HATCH, TEXT, DIMENSION}:
        continue    # 벽 후보 아님 — 단, DIMENSION은 §3.5의 '치수-정박' 단위 힌트로만 소비
```

**변환 합성의 정확성**(expected failure mode 정타): `compose`는 3×3 동차 아핀(2D)로 미러(음의 스케일 det<0)와 비등방 스케일(sx≠sy)을 포함해야 한다. 왕복 검증(§6 C7)이 이 부분을 봉인한다.

**단위 해상(resolve_unit)**:
```
def resolve_unit(insunits, bbox, p0_hint):
    if insunits is set and insunits != 0: return to_mm_factor(insunits)   # 1순위: 명시 단위
    else:  return bbox_heuristic(bbox, p0_hint)                            # 2순위: bbox 추정
    # 판정 근거(어느 분기였는지)를 per-def 감사에 반드시 기록 → 오판 추적(expected failure mode)
```

### 2.3 Stage 1 — 평행-쌍 휴리스틱 (기존 v0/v1 코어 재사용, 공간 인덱스 추가)

```
def pair_candidates(segs):
    idx = SpatialIndex(segs, key=midpoint, bucket=angle_bucket(θ_tol))  # ← 필수: O(n²) 회피
    for s_i in segs:
        for s_j in idx.near(s_i, radius=t_max):        # 근접·근평행만 후보로
            if abs(angle(s_i) - angle(s_j)) <= θ_tol   # 평행: 각 허용 2°
               and t_min <= perp_dist(s_i, s_j) <= t_max      # 두께 대역(절대 or 상대, §3.5)
               and proj_overlap(s_i, s_j) >= overlap_min      # 투영 겹침 ≥ 0.5
               and endpoint_gap(s_i, s_j) <= snap_tol:        # 스냅 6mm
                yield Pair(s_i, s_j, centerline=mid(s_i, s_j))
    # 동심 ARC 쌍: 같은 center, |r_i - r_j| ∈ [t_min,t_max], 각도 구간 겹침 → 곡선 벽-쌍
```

**계산 병목 못박기(R12)**: 최대 도면정의 412,775 세그먼트 [실측]. 나이브 O(n²)는 ~1.7×10¹¹ 쌍 → 불가. 공간 해싱 그리드(셀 크기 ≈ t_max) + 각도 버킷으로 후보를 O(n·k)로 상한. **후보 수 상한(candidate cap)을 사전등록**하고, 초과 시 스트리밍 타일링으로 분할 처리(§4). 후보 수를 per-def 감사에 기록.

### 2.4 Stage 2 — 정션 그래프 후필터 (P1의 신규 판별기)

```
def junction_filter(pairs):
    # 노드 = 벽-쌍(그 centerline), 엣지 = 두 쌍이 끝점에서 만남(L/T/X 정션)
    G = Graph()
    for p in pairs: G.add_node(p)
    for (p, q) in pairs_meeting_within(pairs, snap=junction_radius):
        G.add_edge(p, q, kind=junction_type(p, q))   # L / T / X / colinear-extend
    keep = set()
    for comp in connected_components(G):
        if size(comp) >= k_min or has_cycle(comp):    # 네트워크 = 체인/루프
            keep |= members(comp)                     # 고립 쌍(치수선·가구 단독변)은 탈락
    return keep

def label_handles(kept_pairs):
    return { h: 1 if h in members(kept_pairs) else 0 for h in all_handles }
```

**정직한 한계(§3·§8에서 재론)**: 문·창(Door/Window)은 **벽 네트워크에 위상적으로 연결**돼 있다 → 정션 필터가 이들을 제거하지 못할 가능성이 높다. 반면 치수선·독립 가구변·방향 화살표는 고립돼 제거된다. 이 비대칭이 P1의 예측 성적 상한을 결정한다(§6 C4 사전 예측).

### 2.5 하이퍼파라미터 공간 (전부 결정론 · 튜닝은 synthetic train split에서만)

| 파라미터 | v0 기본값 [실측] | P1 스윕 | 겨누는 실패 |
|---|---|---|---|
| θ_tol (각 허용) | 2° | {1,2,3,5}° | 회전 어긋난 벽 |
| [t_min,t_max] 두께 | 50–400 mm | 절대 vs **치수-정박 상대**(A/B) | 단위-관례 유물(반대의견 #5, T16) |
| overlap_min | 0.5 | {0.3,0.5,0.7} | 부분 겹침 벽 |
| snap_tol | 6 mm | {3,6,12} | 끝점 gap |
| **k_min** (정션 성분 최소크기) | (신규) | {1,2,3,4} | 고립 distractor 제거 강도 |
| junction_radius | (신규) | {snap_tol×{1,2,3}} | 정션 판정 민감도 |
| ARC 동심 tol | (신규) | radius-diff 대역 | 곡선 벽 |
| DEPTH_CAP | (신규) | {8,16,∞-guard} | 중첩 INSERT 폭발 |
| candidate_cap | (신규·R12) | 사전등록 | 후보 폭발 상한 |

**목적함수(선택용, 학습 아님)**: synthetic train split에서 `F_β(wall_member)` 그리드/Taguchi 탐색(doe P2 접속). β는 재현/정밀 트레이드오프(기본 β=1). **경사하강 없음.** 선택된 파라미터는 동결 후 CubiCasa val·145 아카이브에 **순수 추론**으로만 적용(누출 방지 규율 §6).

---

## 3. 벽 과업 적응 설계 (어떻게 실제 하네스에 접속하는가)

세 축이 있고, **P1의 값어치는 축마다 다르다.** 이 절이 도시에의 심장이다.

### 3.1 실도면 축 (1.dwg staged DXF, 도면정의 384개) — P1이 정면으로 이기는 곳

여기서 문제의 본질은 **커버리지**다. 근거:
- B3 벽-제로 도면율 0.682(v0) → 0.2135 PASS [실측]. v0가 도면의 68.2%에서 벽을 **0개** 찾았다는 것은 개념 실패가 아니라 "기하를 못 봄"의 전형적 서명이다. 이미 어떤 수정으로 21.35%까지 내려온 것 자체가 커버리지 가설에 유리한 사전 증거다.
- B1 충실도 FAIL(KS 0.5792, TV 0.265 [실측]): 실도면은 SPLINE 3,973/ARC 2,198/HATCH 264 혼재인데 [실측] v0 파이프라인·합성팩이 LINE/LWPOLYLINE/INSERT 3종만 다룬다 [실측]. **벽이 SPLINE·ARC·MLINE·중첩 INSERT로 그려진 도면에서 v0는 구조적으로 벽을 못 본다.**

P1 접속: 정규화 프런트엔드가 SPLINE 테셀레이션 + ARC 동심쌍 + MLINE 전개 + INSERT 월드전개를 하면, **벽-제로 도면의 n_pairs가 0→>0으로 전환**된다. 이게 cheapest probe(§6 C0)의 직접 계측 대상이며 최대비용 1일·로컬이다.

### 3.2 CubiCasa 벡터 축 (SEG-IR, val 400/35.4만 세그먼트) — P1의 정규화가 거의 no-op인 곳 (정직한 축소)

**여기가 P1의 약한 축이고, 반드시 정직해야 한다.** CubiCasa는 5,000도면 전량 SEG-IR 변환(실패 0), 진리=Wall 클래스 요소의 모서리, 좌표 px [실측]. **즉 이미 선-단위로 평탄화돼 있다** → P1의 정규화 프런트엔드(LWPOLYLINE 분해·INSERT 전개 등)는 여기서 대부분 **할 일이 없다**. CubiCasa에서 P1이 v0 대비 새로 거는 레버는 사실상 **정션 후필터 하나**뿐이다.

그럼 전이 실패 0.2358 [실측]의 정체는? **디스크리미네이션 실패**다:
- P 0.134 ≈ 기저율 0.118, R 0.981 [실측] → "거의 전부를 벽이라 부르는" 탐지기. 정밀도가 기저율과 같다 = 벽/비벽을 사실상 못 가린다.
- FP 주범: Direction 화살표/BoundaryPolygon/Door/Window/DimensionMark — **전부 대역 내 평행 구조** [실측]. 최소길이 필터 천장 F1 0.335(80px) [실측] — 아이콘이 아닌 "긴 평행 구조"가 본질 교란.

**전이 0.236과 GBDT 0.517을 아는 상태에서 P1이 CubiCasa에 더 가져올 수 있는 것(핵심 질문에 대한 정직한 답)**:
1. **정션 위상 신호** — v0의 스칼라 junction 특징(GBDT의 6특징 중 하나)은 국소 접합 카운트일 뿐이다. P1의 정션 *그래프*는 **전역 네트워크 소속**(체인/루프 멤버십)이라는 다른 정보다. 이 전역 신호가 GBDT의 국소 스칼라와 **직교**하면, 정션 필터는 (a) 결정론만으로 치수선·화살표·독립 BoundaryPolygon 같은 **고립 FP를 제거**해 정밀도를 올린다. 예측: F1이 0.2358에서 위로 이동하되, **문·창은 네트워크에 붙어 있어 살아남으므로** GBDT의 0.517까지 닿지는 못할 가능성이 높다(§6 C4의 사전 예측).
2. **비선형 판별의 위상적 몫 계측** — §1.4의 질문에 답한다. 정션 필터가 F1을 0.2358→(예: 0.35~0.45)로 올리고 거기서 멈추면, "GBDT가 학습으로 잡은 비선형의 일부는 위상적(결정론 회수 가능), 나머지(문/창 분리 등)는 통계적(학습 필요)"임이 정량화된다. 이건 CL-F(학습 사다리)의 필수 베이스라인이다.

### 3.3 FloorPlanCAD 래스터 축 — **제안 원문과 자산 현실의 충돌 (반드시 표면화)**

제안 원문의 truth source (b)는 "FloorPlanCAD 선-단위 의미 라벨(외부 교차)"이다. 그러나 자산 다이제스트는 **"FloorPlanCAD 래스터 5,308장 + 벽 bbox/segmask(벡터 SVG 없음)"** [실측]이라고 못박는다. 즉 **우리 로컬 자산의 FPC에는 P1이 요구하는 벡터 선-단위 라벨이 없다.** (원본 FloorPlanCAD 데이터셋은 프리미티브 단위 의미 라벨을 가진 벡터 CAD로 알려져 있으나[요검증], 그 벡터본을 우리가 보유했다는 근거가 다이제스트에 없다.)

**해소 방안(정직)**:
- (i) **권장·실행 가능**: FPC 벡터 외부-교차를 **CubiCasa SEG-IR로 대체**한다. CubiCasa는 우리가 보유한 유일한 "제3자 사람 라벨 × 벡터 선-단위" 자산이며, prereg 밴드의 "외부 벽-선 F1"을 CubiCasa val로 재표현한다(§6). 이러면 P1은 벡터 외부 교차를 확보하면서 자산 현실과 정합한다.
- (ii) **조건부·차단**: 원본 벡터 FPC를 조달하려면 라이선스(PR-3, T5)와 자산 획득이 선결. 래스터 bbox/segmask만으로는 "선-단위 F1"을 정의할 수 없다(픽셀→핸들 역투영 하네스가 없으면; 그건 CL-G의 T24 사안). → **P1에서 FPC 래스터 축은 제외**하고 CL-G로 이관.

이 충돌을 숨기지 않는 것이 red team T34(load-bearing 인용 재-status)와 제안 §truth source의 정직성 계약이다.

### 3.4 레이어-중립 규율 (누출 방지, 증거 축 독립성)

v0/v1 탐지기는 layer 채널 가중 0.20 [실측]이지만, B5에서 **name-blind 팔과 full 팔이 완전 동일(full-vs-nb 1.0), 탐지기 레이어명 신호 0** [실측]으로 실측됐다. CubiCasa 변환도 레이어-중립(누출 0) [실측]. **P1은 레이어명을 판별에 쓰지 않는다** — 이는 (a) CubiCasa의 "라벨 누출 0" 계약을 지키고, (b) B5가 보인 "탐지기↔silver 두 증거축의 대체적 독립"(Pearson 0.2911 [실측])을 보존하기 위함이다. layer 채널은 P1에서 **비활성(가중 0)** 으로 두고, 관례-prior 계측은 CL-I로 격리.

### 3.5 두께 대역: 절대 vs 치수-정박 (반대의견 #5, T16)

CubiCasa는 "축척 미상, 벽두께 px p50=22" [실측]이고, 전이 성적은 "축척 2~15mm/px 전 구간에서 무감"[실측] — 즉 **절대 mm 대역(50–400mm)이 px 좌표계에서 물리적 의미를 잃는다.** P1은 두께 대역을 (A) 절대 mm, (B) 치수-정박 상대(도면 내 치수 엔티티/전형 벽두께 분포로 정규화, feyerabend P2)의 **A/B로 사전 배치**하고, synthetic train에서 선택 후 동결. 이는 §2.5 하이퍼파라미터의 최우선 스윕이다.

---

## 4. 데이터 · 컴퓨트 요구 (우리 자산 기준 실행 가능성)

### 4.1 로컬 실행 계획 (P1은 CPU-only · GPU 불요 · DGX 불요)

P1은 기하 연산 + 그래프 후필터 → **순수 CPU**. RTX 5070 Ti 16GB는 P1에 불필요(선택 C9의 GBDT graft조차 CPU HGB). RAM 64GB [실측] 하에서:

- **병목**: 최대 도면정의 412,775 세그먼트 [실측]의 O(n²) 쌍. 공간 인덱스로 O(n·k) 상한, 후보 cap 사전등록(R12). 단일 도면을 **IR 스트리밍 파싱**으로 처리해 피크 RAM을 세그먼트 배열 + 공간 그리드 수준으로 억제. 145장/384정의 배치는 도면 단위 순차 처리(도면 간 상태 공유 없음) → RAM은 최대 도면 하나에 지배됨.
- **CubiCasa 규모**: train 386만 / val 35.4만 / test 37.5만 세그먼트 [실측]. 도면 단위 스트리밍이면 CPU·64GB로 여유. 정션 그래프는 도면 내부에서만 닫히므로 전역 메모리 폭발 없음.
- **합성 생성기(CL-C)**: CPU. 파라미터 동결 후 held-out 생성.
- **예상 벽시계(wall-clock, 추정 — 실측 아님)**: cheapest probe(20 def) 1일; CubiCasa val 전량 정규화+후필터 1~2일; 145/384 순수추론 수 시간~1일. 전부 로컬.

### 4.2 DGX 계획 (분리) — **P1은 DGX를 쓰지 않는다**

DGX Spark(Ornith-35B)는 현재 unreachable(승인은 됨) [실측]. **P1은 DGX 의존 0**이 설계 불변식이다(제안 원문 "DGX 불사용"). VLM·대형모델은 CL-G 소관이며 P1 범위 밖. 따라서 DGX 복구 여부가 P1의 크리티컬 패스에 없다 — 이것이 P1을 "지금 당장, 로컬에서, 값싸게" 돌릴 수 있는 최저비용 후보로 만드는 요인이다.

### 4.3 데이터 준비 의존성

- **synthetic 벽 truth 생성기**: 아직 부재(T2, 벽 코드 0) → C1이 구축 + 충실도 게이트. **P1의 하드 선결.**
- **CubiCasa SEG-IR**: 이미 존재(전량 변환 실패 0) [실측] → 즉시 접속.
- **1.dwg staged DXF**: 이미 존재(384 정의) [실측] → 즉시 접속. 원본 DWG는 READ-ONLY, 파생은 staging(계약 준수).
- **P0 단위 힌트**: CL-A/P0의 bbox 감사 산출 소비 → P0가 P1의 상류 의존(§8).

---

## 5. 구현 계획 (모듈 골격 · 기존 도구 접속점 · 개발 규모)

> **주의**: 아래 모듈 경로는 **제안 골격(proposed skeleton)** 이다. 이 세션에서 저장소를 광역 스캔하지 못해(트리 과대·검색 타임아웃) 기존 파일 구조를 직접 확인하지 않았다. 다이제스트가 명명한 도구(fast_score/cubicasa_ir/cubicasa_ml/evidence_grid/synthetic_truth.py)에 그 **문서화된 거동 수준에서** 접속하는 계획으로 읽어야 한다. 실제 배선은 착수 시 CL-A 산출·기존 트리 확인 후 확정.

### 5.1 신규/확장 모듈 골격

```
e2/normalize/
  frontend.py          # normalize(DrawingIR)->list[Segment]: 오케스트레이션 + resolve_unit
  insert_flatten.py    # 변환 합성(미러/비등방/중첩) + DEPTH_CAP + 왕복검증 훅
  entity_expand.py     # LWPOLYLINE explode / MLINE expand / ARC / SPLINE tessellate
  units.py             # INSUNITS + bbox 휴리스틱(P0 소비) + per-def 판정근거 기록
e2/detect/
  parallel_pairs.py    # 공간인덱스 + 평행-쌍(θ/두께/overlap/snap) — fast_score 내부루프 재사용
  junction_graph.py    # union-find/그래프 성분 + k_min/cycle 필터
e2/eval/
  wall_member.py       # per-handle 0/1 라벨 + 증거 xlsx emit(평가원칙 준수)
  metamorphic.py       # 강체/스케일/단위/explode/rename 불변 + 0벽/전벽 sentinel + recall 최저선(CL-D)
tools/semantic_gates/
  synthetic_truth.py   # (기존, dimension 전용) → 벽 생성기로 확장(CL-C): 쌍/체인/교차 + distractor + mutation
```

### 5.2 기존 도구 접속점 (다이제스트 명명 도구)

- **`fast_score` (NumPy 동치 고속 채점기)** [실측 존재]: Stage 1 평행-쌍 스코어링의 내부 루프로 **그대로 재사용**. 앞단에 공간 인덱스만 신설해 412,775-정의의 O(n²)를 상한. → P1은 fast_score를 **감싸는(wrap)** 것이지 대체하지 않는다.
- **`cubicasa_ir` (SEG-IR 변환기)** [실측 존재]: CubiCasa 세그먼트 IR의 소스. P1 정규화는 여기서 거의 no-op(이미 세그먼트) → `units.py`의 px 단위-프레임 처리(§3.5)와 정션 필터만 접속.
- **`cubicasa_ml` (HistGradientBoosting 하네스)** [실측 존재]: 선택 셀 C9의 graft 지점 — P1의 **전역 정션-네트워크 소속**을 7번째 특징으로 6-특징 행렬(386만행)에 추가해 val F1이 0.517을 넘는지 시험. CL-F로의 다리.
- **`evidence_grid` (다증거 격자)** [실측 존재]: 정션-네트워크 신호를 하나의 증거 채널로 편입(calibration P1과의 병합점). P1 후필터 → evidence_grid 피드.
- **`synthetic_truth.py`** [실측 존재, dimension 전용]: correct-by-construction + mutate 패턴을 벽으로 확장(§6 C1 = CL-C). 이 확장이 T2(생성기 부재)의 실행체.

### 5.3 개발 규모 (추정 — 실측 아님)

| 모듈 | 난이도 | 리스크 핵심 |
|---|---|---|
| entity_expand / units | 중 | MLINE 스타일·bulge·bbox 휴리스틱 엣지케이스 |
| insert_flatten | **중상** | 미러·비등방·중첩 변환 정확성(C7 왕복검증 필수) |
| parallel_pairs(공간인덱스) | 중 | 412,775-정의 성능 상한(R12) |
| junction_graph | 하 | union-find + 성분 필터(작음) |
| synthetic 생성기 확장 | 중 | 충실도 게이트 T2 통과가 진짜 난제 |
| eval/metamorphic | 하 | 대부분 기존 하네스 재사용 |

가장 위험한 두 지점: **insert_flatten의 변환 정확성**(결함이 조용히 FP/FN을 낳음)과 **생성기 충실도 게이트**(못 넘으면 synthetic 1차 판별기 자격 상실).

---

## 6. 실험 셀 정의 (셀별 계약)

**공통 규율**: 튜닝은 **synthetic train split에서만**. CubiCasa val은 파라미터 동결 후 **순수 추론 held-out**(제안 누출규율이 프로그램 "val=튜닝 허용"보다 엄격 — R9로 더 엄격한 쪽 채택, §7-T tuning). 145/384 실도면·CubiCasa test는 **단발**. 합격선은 계측 전 봉인(prereg). 셔플 대조군·증거 xlsx 의무. 결정론이라 대부분 시드 무관(생성기 시드만 관리).

**밴드 재표현 못박기**: 제안 원문 "FPC 벽-선 F1 v1−v0 ≥ +0.2"는 FPC 벡터 부재(§3.3)로 **CubiCasa val로 이관**. v0 CubiCasa val F1 = **0.2358** [실측]을 베이스라인으로 동결 → P1 목표 F1 ≥ **0.436**, kill < **0.40**. GBDT **0.517** [실측]을 학습 상한 참조선으로 병기.

---

**C0 — cheapest probe: divergent-20 정규화 재실행**
- 가설: 커버리지 완전화가 n_pairs 0→>0을 전환시킨다(파스 수준 검증).
- 지표: 20 def 중 n_pairs 0→>0 전환 계수; INSERT folded vs unfolded 델타.
- 합격(prereg): 전환 def 비율 ≥ (봉인값, 예 ≥0.5) 그리고 INSERT unfold가 새 쌍을 낳음.
- 킬: 전환 0 → 커버리지 가설이 파스 층에서 거짓 → 즉시 재검토(정규화가 아무것도 안 바꿈).
- 예산: 1일·로컬 CPU. 시드: 무관(결정론).

**C1 — 합성 벽 생성기 구축 + 충실도 게이트 (= CL-C / PR-1 실행체, 하드 선결)**
- 가설: 생성기가 divergent-20 실현상(POLYLINE/블록/비평행 조각/SPLINE·ARC 혼재)을 재현한다.
- 지표: 엔티티 히스토그램 KS/TV(= B1 게이트 지표, v0 합성팩은 KS 0.5792 FAIL [실측]) + 엔티티 타입 커버리지(SPLINE/ARC/HATCH 포함 여부).
- 합격(prereg, T2): 충실도 게이트 통과(KS 봉인 임계 하회 + 3종 초과 타입 포함). 통과해야 synthetic이 1차 판별기 자격.
- 킬: 게이트 실패 → synthetic 판별기 강등, P1은 CubiCasa 외부셋에만 의존.
- 예산: 2~3일·로컬. 시드: **생성기 파라미터(두께 분포·distractor 밀도) 동결** 후 평가.

**C2 — synthetic held-out 쌍 recall/precision**
- 가설: 완전 정규화된 입력에서 P1이 합성 벽 쌍을 회수한다.
- 지표: held-out 쌍 recall·precision (평가 단위 wall_member).
- 합격(prereg, 원문 유지): recall ≥ 0.9 그리고 precision ≥ 0.8.
- 킬: **recall < 0.7 → H1 kill(국소 기하 불충분) → H2 승계.**
- 예산: 로컬·수 시간. 시드: mutation family 시드; held-out은 train과 도면·firm 단위 분리.

**C3 — v0 외부 베이스라인 동결 (선결 계측)**
- 목적: prereg 델타의 기준선 고정. CubiCasa val v0 = 0.2358 [실측] 채택·동결. (FPC는 벡터 부재로 제외, §3.3.)
- 산출: 동결 레코드 1건(재측정 금지, 인용만).
- 예산: 0(다이제스트 인용). 킬: 없음(장부 단계).

**C4 — CubiCasa val 전이 (정규화 + 정션 후필터, 두께 A/B)**
- 가설: 정션 후필터가 정밀도를 결정론적으로 올린다(전역 위상 신호).
- 지표: CubiCasa val wall-line F1(및 P/R 분해). 두께 절대 vs 상대 A/B(T16).
- 합격(prereg): F1 ≥ 0.436 (v0 0.2358 + 0.2). 참조: GBDT 0.517.
- 킬: **F1 < 0.40 → H1 kill(디스크리미네이션이 학습을 요구) → H2 승계.**
- **사전 예측(정직)**: 문·창이 네트워크 연결이라 살아남음 → F1은 0.2358과 0.517 **사이**, 밴드(0.436)를 **아슬하게 놓칠 가능성**이 높다. 이 예측이 맞으면 그 자체가 H1-강형의 깔끔한 반증.
- 예산: 1~2일·로컬 스트리밍. 시드: 무관; val은 순수 추론(파라미터는 synthetic서 동결).

**C5 — 145/384 실도면 순수 추론: 벽-제로 도면율**
- 가설: 완전 정규화가 벽-제로 도면율을 현재 0.2135 [실측] 아래로 더 내린다.
- 지표: 벽-제로 도면율(B3 지표, 밴드 ≤0.40 [실측]).
- 합격(prereg): 0.2135 대비 유의 감소(봉인 델타).
- 킬: 개선 0 → 실도면 커버리지 여지 소진(정규화가 이미 다 됨) → P1의 실도면 축 가치 종료.
- 예산: 로컬·스트리밍(412,775-정의 RAM 계측). 시드: 무관. **파라미터 튜닝 금지(145 순수 추론)**.

**C6 — metamorphic 불변 (= CL-D, 스케일 FIX 예측 포함)**
- 가설: 단위 정규화가 B4 scale 팔 FAIL(0.7624 [실측])을 PASS로 되돌린다(P1의 직접·falsifiable 예측).
- 지표: 강체·단위·스케일·explode·rename 불변 위반율 + **0벽/전벽 sentinel + recall 최저선**(공격 F/T7 의무 수정).
- 합격(prereg): scale 불변 회복(강체·단위는 이미 1.0 PASS [실측]) 그리고 sentinel 통과.
- 킬: 단위 정규화 후에도 scale-variant → units.py 결함(전개 버그).
- 예산: 로컬. 시드: 변환 파라미터 격자.

**C7 — INSERT 변환 왕복 검증**
- 가설: insert_flatten이 미러·비등방·중첩을 정확히 전개한다.
- 지표: 왕복 기하 동치 오차(전개→역전개).
- 합격(prereg): 허용오차 내 exact.
- 킬: 미러/비등방 버그 → 전개 로직 수정 전 하류 셀 차단.
- 예산: 로컬·수 시간. 시드: 합성 중첩 케이스.

**C8 — ablation: 커버리지 vs 정션 (가장 정보량 큰 셀)**
- 가설: F1 이득을 (a) v0, (b) +정규화만, (c) +정규화+정션으로 분해하면 어느 레버가 구속 조건인지 드러난다.
- 지표: 세 조건의 F1/P/R(CubiCasa val + synthetic).
- 판정: (b)−(a)=커버리지 몫(주로 recall), (c)−(b)=정션 몫(주로 precision). §1.4 "위상적 vs 통계적" 분해의 계량.
- 킬: (b)−(a)≈0 **그리고** (c)−(b)≈0 → 전이 격차가 커버리지도 위상도 아님 = 학습 필수 → **H1-강형 사망, H2 승계**(가장 정직한 죽음).
- 예산: 로컬. 시드: 무관.

**C9 — (선택·CL-F 다리) 정션-네트워크 특징 GBDT graft**
- 가설: P1의 전역 정션 소속이 GBDT의 스칼라 junction 특징과 직교해 val F1 > 0.517.
- 지표: 7-특징 HGB val F1/AUC vs 6-특징 0.517/0.9215 [실측]. 셔플 대조군 의무.
- 합격(prereg): F1 유의 상승. 킬: 상승 0 → 정션 위상은 이미 스칼라로 포화 → P1의 CubiCasa 기여는 고립-FP 제거로 한정.
- 예산: 로컬 CPU(HGB, 386만행, 64GB 여유). test 무접촉(단발 원칙). 시드: HGB 시드 3개 평균.

**test 단발 봉인**: CubiCasa test 400(37.5만) [실측]은 방법 확정 후 **단 1회**. 그 전 어떤 셀도 test를 만지지 않는다.

---

## 7. red team 티켓 응답 (이 제안에 걸린 OPEN 티켓)

| 티켓 (sev) | 걸리는 지점 | P1 입장 |
|---|---|---|
| **T1 대리 독립성 (0.75, 최우선)** | P1의 평행-쌍 휴리스틱 = 문제의 "평행 이중선 prior" 그 자체. synthetic·metamorphic·silver가 같은 prior면 합치는 확증 아니라 편향 증폭. | **부분 수용 + 완화.** 정션 *그래프*(전역 위상)는 평행-쌍 prior와 다른 신호축임을 C8/C9로 계량. **CubiCasa 사람 라벨**(우리 prior와 무관 생성)을 독립 교차로 씀. CL-E의 동일-def 3원 불일치 구조 계측에 P1 산출을 제공. 잔여 위험(정션도 결국 기하)은 인정하고, VLM/래스터(CL-G) 같은 **비-기하 축**과의 교차는 P1 밖 과제로 명시. |
| **T2 생성기 부재 (0.70)** | truth source (a)가 아직 없음(벽 코드 0). | **하드 선결로 수용.** C1이 생성기+충실도 게이트(T2) 구축. 통과 전엔 P1의 1차 판별을 CubiCasa 외부셋으로 이동. |
| **T5 라이선스 (0.65)** | FPC/CubiCasa NC + 원도면 권리 미해결(PR-3, R23). | **수용·차단.** 외부셋 학습 arm 전 서면 클리어 선결. FPC는 벡터 부재(§3.3)로 P1에서 애초 제외 → 남는 외부 의존은 CubiCasa뿐, 방화벽 문서화(방법개발 전용·가중치/파생물 제품 반입 금지, R23). |
| **T7 metamorphic sentinel/recall 최저선 (0.50)** | 위반율-only 밴드는 "0벽 탐지기"를 통과시킴. | **전면 수용.** C6에 0벽/전벽 sentinel + recall 최저선을 랭킹 사용 전 탑재. |
| **T9/T21 v0 베이스라인 선계측** | prereg 델타의 기준선 미고정(특히 외부셋). | **수용.** C3가 CubiCasa val v0=0.2358 [실측] 동결. FPC는 벡터 부재로 제외(재측정 아님, 인용). |
| **R12 quadratic 후보 폭발** | 412,775-정의 O(n²). | **수용·사전등록.** 공간 인덱스 + candidate_cap prereg + 후보 수 per-def 감사 로깅(§2.3). |
| **T10 silver 게이트 식별자 (platt 인용 오류)** | 반대의견 #1: platt는 "B1≥0.70"만, 정확은 "B1≥0.70 **및** B4 Pearson≥0.70"(calibration). | **좌석 오류 인정·정정.** P1은 silver를 직접 쓰지 않으나, 좌석 인용을 정정해 채택. (P1의 판별은 silver 독립 — §3.4.) |
| **T16 상대 vs 절대 두께 밴드** | 절대 mm가 px·단위관례에서 무의미(전이 축척 무감 [실측]). | **수용.** C4에 절대 vs 치수-정박 상대 A/B를 Taguchi 선행(§3.5). |
| **(비번호) FPC 벡터 부재** | 제안 truth source (b)와 자산 현실 충돌(§3.3). | **표면화·재설계.** FPC 벡터 축 제외, CubiCasa로 외부 벡터 교차 대체. 원본 벡터 FPC 조달은 PR-3 뒤로. |
| **T34 load-bearing 인용 재-status** | 인용 R-레인 experiment_executed:false. | **수용.** P1의 모든 실측 인용은 이 패킷 다이제스트 한정(§0). 미실행 인용에 성적을 싣지 않음. |

---

## 8. 인접 제안과의 관계 · 이 제안이 죽어야 하는 조건

### 8.1 병합점 (merge)

- **CL-B의 척추**: CL-B = platt P1 + calibration P1(다증거 격자) + feyerabend P6(INSERT 월드전개) + feyerabend P2(치수-정박 상대대역) + doe P2(Taguchi 강건화). **P1이 이 클러스터의 중심 골격**이다. feyerabend P6은 P1의 insert_flatten이 흡수, feyerabend P2는 §3.5 A/B로 흡수, doe P2는 §2.5 파라미터 탐색으로 흡수, calibration P1은 evidence_grid 접속(§5.2)으로 병합.
- **CL-C = P1의 truth source (a)**: 생성기 확장(C1)이 곧 CL-C. wall_member(h) 평가 단위 공유.
- **CL-D = P1의 C6**: metamorphic 배터리를 P1이 sentinel/recall 최저선 포함해 실행.
- **CL-A(P0) = P1의 상류**: 단위 정규화가 P0의 bbox 감사(§4.3)를 소비. cheapest probe C0는 P0가 감사한 divergent-20에서 돈다.

### 8.2 차별점 (differentiation)

- **vs calibration P1(다증거 격자)**: calibration은 증거 채널을 늘려 확률적으로 결합(Bayesian). **P1은 채널을 늘리지 않고 위상(정션 그래프) 한 축을 결정론적으로 추가**한다. P1이 먼저 뛰고, 남는 격차를 격자가 메우는 순서(Occam).
- **vs CL-F(학습 사다리 GBDT→GNN)**: **P1은 CL-F가 반드시 넘어야 할 결정론 베이스라인**이다. 만약 P1의 정션 필터가 CubiCasa F1을 GBDT 0.517 [실측] 근처까지 결정론으로 올리면 **GNN은 불요**(Occam 사다리 — 로지스틱/GBDT/GNN 순 하드 선결). C9가 P1→GBDT 특징 이식으로 이 경계를 계측.
- **vs feyerabend P1(room-first 역전, CL-J)**: P1은 "centerline→network→rooms"(정공법). feyerabend는 "rooms/faces 먼저, 벽은 dual의 bridge"(역전). **CL-J 프로브가 둘을 판별**하며, P1의 정션-네트워크가 오픈플랜(R16 KR2)·messy(KR4)에서 무너지면 CL-J가 승계(§8.3-5).

### 8.3 이 제안이 죽어야 하는 조건 (정직하게)

P1(및 H1-강형)은 다음 중 하나면 **죽어야 한다** — 그리고 그 죽음은 실패가 아니라 값싼 판별 정보다:

1. **synthetic held-out recall < 0.7** (C2 킬) → 완전 정규화 후에도 국소 기하가 벽 쌍을 못 회수 = H1 개념 사망.
2. **CubiCasa val F1 < 0.40** (C4 킬) → 디스크리미네이션이 결정론을 넘어선다 = H1-강형 사망, H2(학습) 승계.
3. **C8 ablation에서 커버리지 몫≈0 그리고 정션 몫≈0** → 전이 격차가 커버리지도 위상도 아님 = 학습 필수. **가장 정직하고 가장 가능성 있는 죽음**(문·창이 네트워크 연결이라 정션 필터를 통과한다는 §2.4·§3.2 예측이 맞을 때).
4. **CL-A가 E1 불일치를 계측 아티팩트로 판정** → P1의 동기(v0가 커버리지로 실패)가 부분 해소 → P1은 가설 시험에서 **위생(hygiene) 전처리 단계로 강등**(그래도 하위 방법의 필수 커버리지 계층으로는 생존).
5. **synthetic PASS(recall≥0.9) & CubiCasa FAIL(F1<0.4)의 갈림** → Goodhart 서명(합성 분포가 휴리스틱 가정과 동형이 되어 자기실현). 실도면 전이 0.2358 [실측] + FP 주범이 전부 실 평행구조 [실측]인 현 증거에 비추면 **이 시나리오가 가장 그럴듯하다.** 이 경우 H1은 실데이터에서 죽고, 그 죽음이 곧 §8.2의 "CL-F가 왜 필요한가"의 실험적 근거가 된다.

**죽어도 남는 것(생존 조건의 정직한 분리)**: 위 2·3·5로 H1-강형이 죽어도, **P1의 정규화 프런트엔드는 죽지 않는다.** 그것은 GBDT·GNN·VLM 포함 모든 하위 방법이 공유해야 하는 커버리지 계층이며(실도면 축 C0/C5가 그 가치를 독립 입증), B4 scale FAIL을 고치는 유일한 결정론 수단(C6)이다. **즉 "H1 지배 가설"은 죽을 수 있어도, "P1 정규화 계층"은 프로그램의 공용 인프라로 남는다** — 이 분리가 P1을 최저비용·최고 레버리지 후보로 만든다.

---

**요약(이 도시에가 남기는 한 문장)**: P1은 실도면 커버리지 축에서 이기고 CubiCasa 디스크리미네이션 축에서 정직하게 죽을 수 있는, 값싸고 결정적인 H1-강형 시험지다 — 그리고 어느 쪽이든 그 결과는 하위 사다리 전체의 방향을 결정한다.

DOSSIER_COMPLETE: platt_P1
