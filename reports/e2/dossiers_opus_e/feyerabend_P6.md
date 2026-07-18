# E2 방법론 심층 도시에 — feyerabend_P6

## 제안: Cross-def / INSERT 조립 단위 — “def 스코프 = 벽 단위”를 깨뜨린다

> **도시에(dossier)** = 한 제안 하나를 “실행 가능한 실험 계획”이 될 때까지 끝까지 파고든 심층 조사 문서. 이 문서는 feyerabend 좌석의 P6 제안 1건만을 대상으로 한다.

이 제안을 한 문장으로: **현재 탐지기가 블록 정의(block definition, 이하 def) 하나하나를 닫힌 세계로 보고 그 안에서만 벽을 찾는데, 그 “한 def = 한 벽 판단 단위”라는 전제 자체를 버리고, 도면을 배치된 월드 좌표(world coordinate, 도면에 실제로 그려진 최종 위치)로 먼저 펼친 뒤 거기서만 벽을 찾자**는 것이다.

이 제안의 프로그램 내 지위(패널 보고서 기준): P6은 독립 클러스터가 아니라 **CL-B(커버리지-완전 결정론 v1)** 의 핵심 부품으로 병합되어 있고, 패널은 P6을 “**코드 확정 결함 정타**(코드에 실재하는 결함을 정확히 때린다)”로 표기했다. 즉 P6은 추측이 아니라, 이미 존재가 의심되는 구체적 버그(“per_def 스코프가 def를 가로지르는 벽 쌍을 구조적으로 못 본다”)를 겨냥한다. 다음 프로브 큐 3번(“CL-B divergent-20 재실행: … INSERT folded/unfolded 10 def …”)이 곧 P6의 최저비용 실험이다.

---

## 0. 핵심 주장 한 눈에 (용어 먼저 풀기)

- **per_def 스코프** = 탐지기 함수 `propose_for_ir`가 도면을 def 단위로 쪼개, 각 def 내부의 선분들끼리만 벽 후보를 만드는 현재 동작. “def 안에서만 짝을 찾는다.”
- **월드좌표 전개(assembly / flatten)** = 블록 참조(INSERT)를 재귀적으로 펼쳐, 모든 선분을 도면 최종 좌표계로 변환해 한 평면에 모으는 것. CAD의 “explode(폭파)”와 같은 기하 결과를 얻되, 원본은 건드리지 않는다.
- **익명 블록 `*U###`** = AutoCAD가 자동 생성하는 이름 없는 블록. 사용자가 이름 붙인 블록이 아니라, 해치·치수·동적 블록 전개 등에서 시스템이 만들어낸 조각 묶음. 여기 벽의 “한쪽 선”만 담기고 그 짝(평행한 반대쪽 선)이 다른 def나 모델스페이스에 있으면, per_def 탐지기는 영원히 짝을 못 맞춘다.
- **mechanism(메커니즘)**: def 경계를 무시하고 월드좌표에서만 벽 리본(ribbon, 두 평행선 사이의 벽 몸통)/쌍(pair, 벽의 양쪽 선)을 찾는다.
- **counter_theory(반대 이론)**: 벽의 의미는 “누가 저작했나(어느 블록에 담겼나)”가 아니라 “배치된 기하들이 서로 어떤 관계인가”에 있다. E1이 쓰는 def 단위 likelihood(가능도)는 **잘못된 quotient(몫/등분 기준)**.
- **dissolved_fact(해체될 사실)**: “def 안 n_pairs=0 ⇒ 그 역할 단위에 벽 없음”이라는 현재의 ‘사실’은, 전개 후 쌍이 생기면 유물(artifact)로 판명된다.
- **kill(죽는 조건)**: 전개 후 후보가 제곱 복잡도로 폭발해 실용 불가이거나, 실측 발산 def에서 이득이 0이면 이 제안은 죽는다.

---

## 1. 이론적 근거·선행연구

### 1.1 방법론 계보 — “관계적 의미” 대 “저작 청크 의미”

P6의 뿌리는 **의미가 개체 내부에 있지 않고 개체 간 관계에 있다**는 구조주의(relational/structural semantics)적 입장이다. 벽은 “벽이라고 태그된 하나의 사물”이 아니라 “두 개의 평행선이 일정 간격을 유지하며 함께 달리는 관계”로만 존재한다 — 이 관계가 성립하는 좌표계는 저작 단위(블록 def)가 아니라 최종 배치 평면(월드좌표)이다. 이 관점에서 “벽은 어느 블록에 담겼는가”는 우연적 저작 사정(authoring accident)일 뿐, 의미의 담지자가 아니다.

이 계보에서 P6이 직접 기대는 기술적 선행 개념은 셋이다.

1. **Scene graph flattening / transform 전개** — 컴퓨터 그래픽스에서 계층적 변환 트리(scene graph)를 최종 월드 변환으로 접어 내리는 표준 연산. CAD의 블록/INSERT 중첩은 정확히 이 scene graph이며, “explode”는 그 flatten이다. P6은 “의미 분석 전에 scene graph를 flatten한다”는, 그래픽스에선 당연하지만 이 탐지기 파이프라인에선 생략된 단계를 복원한다.
2. **벡터 도면 double-line wall 탐지** — 건축 도면에서 벽을 “평행 이중선(double line)”으로 검출하는 계열. 래스터·벡터 도면 분석의 고전 주제다. 대표적으로 Ah-Soon & Tombre, Dosch 등의 건축도면 벡터화 프레임워크(요검증 — 저자·연도 정확 인용 필요), 그리고 CubiCasa5k(Kalervo 등, 2019, 요검증)·Raster-to-Vector floorplan(Liu 등, ICCV 2017, 요검증)·FloorPlanCAD panoptic symbol spotting(Fan 등, 2021, 요검증) 계열. **핵심 공통점**: 이들 대부분은 이미 flatten된(래스터거나, 벡터라도 심볼 참조가 펼쳐진) 입력을 전제한다. 즉 문헌은 “먼저 펼친다”를 암묵 전제로 깔고 있고, 우리 파이프라인은 그 전제를 어겼다. P6은 문헌의 암묵 전제를 우리 코드에 명시적으로 이식하는 것에 가깝다.
3. **Metamorphic testing(변형 관계 검사)** — 정답 라벨 없이도 “입력을 이렇게 바꾸면 출력은 이렇게 변해야 한다”는 불변 관계로 검증하는 기법(Chen 등의 metamorphic testing 계보, 요검증). P6의 실측 정답원은 사람 라벨이 아니라 **explode 불변(MR_explode)**: “블록에 담겨 있든 모델스페이스로 폭파했든, 벽 판단은 같아야 한다.” per_def 탐지기가 이 불변을 어긴다면 그것이 곧 버그의 증거다.

### 1.2 CAD 블록·INSERT·transform 스택의 형식

DXF/DWG의 기하는 두 층으로 산다. **BLOCK(정의)** 은 로컬 좌표계에 그려진 재사용 가능한 도형 묶음(base point = 삽입 기준점을 가짐)이고, **INSERT(참조/삽입)** 는 그 정의를 특정 위치·회전·스케일로 도면에 배치한다. INSERT는 삽입점(insertion point), X/Y/Z 스케일, 회전각을 가지며, OCS(Object Coordinate System, 압출 방향 group code 210으로 정의되는 개체 좌표계)를 통해 3D 지향까지 표현한다. INSERT 안에 또 INSERT가 있을 수 있어(중첩 블록) 전체가 하나의 **변환 트리(transform tree)** 를 이룬다. MINSERT(배열 삽입)는 행/열 개수·간격으로 격자 복제를 표현한다.

한 def 내부 좌표의 점을 월드좌표로 보내는 변환은, 대략

```
M_world(child)  =  M_parent  ·  T(insert_point) · R(rotation) · S(sx,sy,sz) · T(-base_point)
```

의 합성으로 주어진다(순서·base point 처리·OCS 보정은 라이브러리 구현에 위임 — §2.3). per_def 탐지기는 이 트리를 **펼치지 않고**, 각 BLOCK 정의를 그 자체 로컬 좌표에서 독립적으로 채점한다. 그래서 “벽의 왼쪽 선은 def A에, 오른쪽 선은 def B(또는 modelspace)에” 있는 배치는, 두 선이 월드에서는 나란히 붙어 있어도 탐지기 눈에는 서로 다른 우주에 있는 무관한 선이 된다.

### 1.3 익명 블록 `*U###` 의 실체 — 왜 이게 “정타” 표적인가

`*U###`(그리고 `*D###`, `*X###`)은 AutoCAD가 자동 명명하는 익명 블록으로, 사용자가 의도해서 만든 논리 단위가 아니라 시스템이 기계적으로 잘라 담은 조각이다. 이런 블록은 “벽”이라는 사람 개념과 경계가 어긋나기 쉽다 — 한 벽이 여러 익명 블록에 흩어지거나, 벽 조각 하나만 익명 블록에 들어가고 짝은 밖에 남는다. 실측 다이제스트가 지목한 **최대 도면정의 412,775 선분(연산 병목 실증)** 같은 거대 def, 그리고 B5의 발산 도면들이 이런 구조를 품고 있을 개연성이 P6의 표적이다. 패널이 P6을 “코드 확정 결함 정타”라 부른 이유가 여기 있다: 이건 “있을지도 모를” 문제가 아니라, 익명 블록이 존재하는 한 per_def 스코프가 **원리적으로** 놓치는 사례가 존재한다는 구조적 주장이다.

### 1.4 Feyerabend적 근거 — 관측 언어의 이론적재성과 counter-induction

이 좌석의 정신적 뿌리는 Feyerabend의 『반방법(Against Method)』이다(요검증 — 개념 귀속만, 특정 페이지 인용 아님). 두 도구를 빌린다.

- **관측의 이론적재성(theory-ladenness of observation)**: “def 안 n_pairs=0 ⇒ 벽 없음”은 중립적 관측이 아니다. 그것은 “저작 청크 = 의미 단위”라는 **이론적 약속**을 이미 관측 언어에 심어 놓은 결과다. 우리는 벽을 세다가 실은 우리의 스코프 가정을 재확인하고 있었던 것일 수 있다.
- **역귀납(counter-induction)**: 잘 확립된 ‘사실’과 모순되는 가설을 일부러 채택해 그 ‘사실’이 실은 이론의 산물임을 드러내는 전략. dissolved_fact를 정면으로 부정하는 가설(“전개하면 쌍이 생긴다”)을 세우고, 그것이 참이면 원래의 ‘사실’은 계측 아티팩트로 해체된다.

이 좌석의 미덕이자 위험은 같다: 지배 방법을 “틀렸다”가 아니라 “**우연한 관례의 산물**”로 재서술한다. 그래서 P6의 성패는 수사가 아니라 §6의 밴드가 판정해야 한다 — Feyerabendian 반문이 자기 자신에게도 적용되어야 정직하다.

### 1.5 “잘못된 quotient” 의 수학적 의미

counter_theory의 “E1 def 단위 likelihood는 잘못된 quotient”를 정확히 풀면: 선분 집합 X 위에 등가관계 ~를 놓고 X/~(몫집합, 같은 부류끼리 묶은 것)로 벽 단위를 정의할 때, E1은 ~를 “같은 block def에 속함”으로 잡았다. P6의 주장은 **올바른 등가관계는 “월드좌표에서 기하적으로 인접·평행함”**이라는 것이다. 잘못된 등가관계로 몫을 취하면, 벽을 구성하는 바로 그 관계(def를 가로지르는 쌍)가 서로 다른 부류로 찢겨 사라진다. likelihood를 def 단위로 정규화(quotient)하는 순간, 분모(집계 단위)가 틀렸으므로 그 위에서 계산된 어떤 수치도 “역할 단위에 벽이 없다”는 결론을 **정의상** 재생산한다. 이것은 모델의 부정확이 아니라 **집계 대수(aggregation algebra)의 오류**다 — 그래서 학습을 아무리 잘 해도 복구되지 않고(§3.3), 스코프를 고쳐야만 복구된다.

---

## 2. 알고리즘 정확 스펙

P6은 학습 방법이 아니라 **표현/스코프 변환**이다. 스펙의 대부분은 결정론적 기하 전개와, 전개 후의 후보 생성·복잡도 제어다.

### 2.1 입출력 계약

- **입력**: DXF/DWG staged 사본에서 만든 SEG-IR(선분 중간표현). modelspace 엔티티 목록 + BLOCK 테이블 + INSERT 트리. (원본은 READ-ONLY, 파생은 staging 사본에서 — 프로젝트 불변식.)
- **출력**: `WorldSegmentSet` — 월드좌표로 변환된 선분 리스트. 각 선분은 `(p0, p1, provenance_key)`를 갖는다. `provenance_key`는 “어느 def 체인에서 왔는가”를 라벨 없이 식별하는 핸들 안정 해시(§2.5).
- **파생 출력**: `PairSet` — 월드좌표에서 검출된 벽 쌍/리본 후보. 각 쌍은 `(seg_i, seg_j, thickness, overlap, angle_residual, cross_def_flag)`. `cross_def_flag`는 두 선분의 provenance def 체인이 다를 때 참 — **P6의 핵심 관측량**.
- **판별 산출**: def별 `folded_pairs`(per_def 스코프에서 나온 쌍 수)와 `unfolded_pairs`(월드 전개 후 쌍 수), 그리고 그 차이.

### 2.2 월드좌표 조립 — 전개 드라이버 의사코드

```
function assemble_world(layout, blocks, max_depth):
    stack = [(entity, IDENTITY, [], 0) for entity in layout.modelspace]
    world = []
    unsupported = []
    while stack not empty:
        (e, M, def_chain, depth) in stack.pop()
        if e is INSERT:
            if depth >= max_depth:            # 무한/과심 중첩 방어
                unsupported.append((e, "depth_cap")); continue
            if e is DYNAMIC or e.name not in blocks:   # 예상 실패모드: 동적/미지원
                unsupported.append((e, "dynamic_or_missing")); continue
            for cell in minsert_cells(e):     # 행/열 배열 전개 (단일 INSERT면 1칸)
                Mi = M · cell.offset · insert_matrix(e, blocks[e.name].base_point)
                child_chain = def_chain + [stable_block_id(e)]
                for child in blocks[e.name].entities:
                    stack.push((child, Mi, child_chain, depth+1))
        elif e is drawable (LINE/LWPOLYLINE/POLYLINE/ARC/…):
            for seg in segments_of(e):        # 폴리라인·호는 선분열로 정규화(뒤 참조)
                world.append(Segment(M·seg.p0, M·seg.p1,
                                     provenance = hash_chain(def_chain, stable_entity_id(e), seg.idx)))
        else:
            unsupported.append((e, "unhandled_type"))
    return world, unsupported
```

- **ARC/SPLINE 정규화**: 실도면은 SPLINE 3,973 / ARC 2,198 / HATCH 264가 혼재(B1 근거). 전개 단계에서 ARC/SPLINE은 sagitta(현-호 최대편차) 허용오차 기반 폴리라인 근사로 선분열화하고, HATCH는 경계 폴리라인만 취한다. 이 정규화는 CL-B의 “LWPOLYLINE/MLINE/ARC 정규화” 부품과 공유한다(§8.1).
- **xref 미포함**: 외부참조(xref)는 전개하지 않는다(예상 실패모드). 커버리지 갭으로 명시 기록.

### 2.3 INSERT 변환 행렬 — 직접 재구현 금지(정확성 위임)

`insert_matrix(e, base_point)`(삽입점·회전·스케일·base point·OCS 압출 보정의 합성)와 MINSERT 배열 전개는 **직접 구현하지 않는다**. ezdxf의 `Insert.matrix44()` / `Insert.virtual_entities()`에 위임한다(요검증 — 정확한 API 표면·중첩 재귀 반환형은 설치된 ezdxf 버전에 대해 확인). 근거(R7·R2): 변환 순서·base point 부호·OCS(group 210) 처리·mirror(음수 스케일) 케이스는 손으로 재유도하면 조용한 좌표 버그를 낳기 쉽고, 이 라이브러리는 이미 이 라우터의 DXF 진리원(truth)이다. 우리 드라이버(§2.2)는 “재귀·provenance 부착·미지원 격리”만 책임지고, 픽셀 단위 정확한 변환은 라이브러리에 맡긴다. **손코딩 직행 금지** 원칙과도 정합.

### 2.4 조립 후 벽 쌍/리본 탐지

전개된 `WorldSegmentSet` 위에서 기존 탐지기의 쌍 판정을 그대로 재사용한다(재발명 금지). 다이제스트가 준 탐지기 v1 파라미터를 월드좌표에 적용:

- **평행성(parallel)**: 각도차 허용 2° 이내.
- **두께 대역(thickness band)**: 두 평행선 간 수직거리 ∈ [50mm, 400mm]. (feyerabend P2가 이 절대 mm 대역을 치수-정박 상대대역으로 바꾸자 제안 — §8.1; P6은 대역 정의와 직교하므로 어느 쪽이든 접속.)
- **중첩(overlap)**: 투영 겹침 비율 ≥ 0.5.
- **스냅(snap)**: 6mm 이내 끝점 병합.

핵심 차이는 단 하나: **후보 짝 (i, j)를 만들 때 i, j가 같은 def에 속하는지 묻지 않는다.** 그래서 `cross_def_flag=참`인 쌍이 처음으로 검출 가능해진다.

### 2.5 핸들 안정 해시 — 누수 방지

전개 그래프의 노드/엣지는 **라벨(레이어명·블록명 문자열·사람 태그)을 일절 담지 않는다.** provenance_key는 `hash(def_chain의 안정 블록 ID들, 엔티티 핸들, 세그먼트 인덱스)`로만 만든다. “안정(stable)”은 도면을 다시 열거나 staging 복사해도 같은 개체엔 같은 키가 나온다는 뜻(핸들 기반). 이렇게 하면:

1. cross_def 판정이 “이름이 같은 벽 레이어라서”가 아니라 순수 기하·구조에서 나온다 → 라벨 누수 0.
2. B5의 실측(“탐지기는 레이어명 신호 0, full-vs-nb 1.0”)과 정합 — P6은 이 name-blind 성질을 **유지**하며, 오히려 강화한다(T1 대응, §7).

### 2.6 후보 폭발 제어 — 공간 인덱스 (R12의 방어선)

전개 후 순진한 O(n²) 짝 탐색은 412,775 선분에서 즉사한다. 그래서:

- **공간 인덱스**: 세그먼트 bbox를 최대 두께대역(400mm)만큼 팽창시켜 균일 격자(uniform grid) 또는 R-tree에 넣고, 같은 셀/이웃 셀 안에서만 후보를 만든다. 이러면 후보 수는 대략 O(n·k)(k=국소 이웃 밀도)로 억제된다.
- **사전등록 상한(R12)**: 실험 전에 “후보쌍 ≤ C·n(예: C=20), 피크 RAM ≤ 64GB”를 봉인한다. 초과하면 kill(§6 Cell D). 이 상한을 안 정하면 “전개하니 다 검출됨(사실은 폭발)”을 성공으로 오독할 위험.

### 2.7 하이퍼파라미터 공간

P6은 학습 파라미터가 없다. 노브는 전부 결정론:

| 노브 | 기본 | 탐색 범위 | 역할 |
|---|---|---|---|
| angle_tol | 2° | 1–3° | 평행 허용 |
| thickness_band | 50–400mm | (P2 상대대역 대안) | 벽 몸통 폭 |
| overlap_min | 0.5 | 0.3–0.7 | 겹침 하한 |
| snap | 6mm | 3–10mm | 끝점 병합 |
| sagitta_tol | (정규화) | — | ARC/SPLINE 근사 정밀도 |
| max_depth | 8 | 4–16 | 중첩 전개 상한 |
| grid_cell | 400mm | ×1–×4 대역 | 공간 인덱스 셀 |
| cand_ceiling C | 20 | 사전봉인 | R12 kill 상한 |

이 노브들은 val(1.dwg·합성)에서만 튜닝하고, test는 봉인된 값으로 단발.

### 2.8 folded vs unfolded 판별 함수 — P6의 심장

```
function discriminate(def):
    folded   = detect_pairs(scope=per_def(def))          # 현재 코드 경로
    unfolded = detect_pairs(scope=world(assemble(def)))  # P6 경로
    recovered = unfolded.pairs - folded.pairs            # 전개로 새로 생긴 쌍
    cross_def = { p in recovered : p.cross_def_flag }
    return {folded_n: |folded|, unfolded_n: |unfolded|,
            recovered_n: |recovered|, cross_def_n: |cross_def|}
```

합성 정답이 있는 경우 recall로, 실측(라벨 없음)에서는 “recovered_n>0인 def의 비율”과 “metamorphic 불변 위반이 사라졌는가”로 읽는다.

---

## 3. 벽 과업 적응 설계

### 3.1 세 실측 축과의 접속 — 정직한 지도

다이제스트의 하네스는 세 축이다. P6이 각 축에 어떻게 붙는지, 그리고 **어디엔 안 붙는지**를 먼저 정직하게 못 박는다. FM(거짓 PASS/과대주장) 방지의 핵심이다.

| 축 | 성격 | P6 접속 | 판정 |
|---|---|---|---|
| **1.dwg 실도면(384 def)** | DWG/DXF, 익명 블록 실재 | **정면 접속** — P6의 본진 | 여기서 수치가 산다 |
| **CubiCasa5k SEG-IR(벡터)** | 핀란드 주거, SVG 유래(요검증) | **대체로 이미 flatten됨** — cross-def 패턴 희소 가능 | P6의 F1 기여 불확실 |
| **FloorPlanCAD(래스터 5,308)** | 픽셀, 벡터 SVG 없음 | **비접속** — P6은 벡터/IR 방법 | 직교, 무관 |

- **1.dwg 축(본진)**: B3(벽-제로 도면율)이 사는 곳. per_def에서 n_pairs=0으로 “벽 제로”로 잡힌 def 중, 짝이 다른 def에 있어 놓친 것들을 P6이 회수한다. 실측 프로브(top-20 `*U*` 발산 def)가 여기서 돈다.
- **CubiCasa 축(주의)**: CubiCasa는 SVG/벡터에서 SEG-IR로 변환되며(변환 실패 0), SVG의 `<use>`(심볼 재사용, INSERT의 SVG 등가물)가 **변환 시 이미 펼쳐졌을** 개연성이 크다(요검증 — `cubicasa_ir`의 `<use>` 처리 방식 확인 필요). 그렇다면 CubiCasa엔 cross-def 패턴이 거의 없고, P6은 val F1 0.2358/GBDT F1 0.517 같은 **CubiCasa 리더보드 숫자를 직접 못 움직인다.** 이걸 숨기지 않는다(§3.4).
- **FloorPlanCAD 축(비접속)**: 래스터+bbox/segmask만 있고 벡터 SVG 없음. P6은 선분·블록 위에서 도는 방법이라 이 축과 만나지 않는다.

### 3.2 전이 실패 0.236 · GBDT 0.517을 아는 상태에서 P6이 더 가져오는 것

두 숫자를 정확히 재인용: **CubiCasa 전이 val F1 0.2358(P 0.134≈기저율 0.118, R 0.981)**, **HistGradientBoosting val F1 0.517(P 0.860/R 0.370/AUC 0.9215)**(둘 다 실측 다이제스트, 2026-07-18). 이 둘이 말하는 병목은 서로 다르다:

- 전이 0.236의 병목은 **정밀도(precision)**: 탐지기가 화살표/경계폴리곤/문/창/치수선 같은 “대역 내 평행 구조”를 벽으로 오검(FP). 재현율은 0.981로 이미 높다.
- GBDT 0.517은 그 정밀도 문제를 특징+학습으로 상당히 고쳤다(P 0.13→0.86). 대신 **재현율이 0.370으로 낮다** — 놓치는 벽이 많아졌다.

P6은 이 둘 중 **재현율 축**에 개입한다. 정밀도 문제(FP 억제)는 P6이 손대는 곳이 아니다. P6이 겨냥하는 건 “후보 자체가 만들어지지 않아서 어떤 특징·어떤 학습으로도 복구 불가능한 벽”이다. 짝이 def를 가로질러 찢겨 **후보 쌍이 애초에 존재하지 않으면**, parallel/thickness/junction 특징을 아무리 계산해도 그 행(row)이 없다. P6은 학습 이전 단계에서 **후보 집합을 바로잡아 재현율 천장 자체를 올린다.**

### 3.3 recall 천장 상향 논증 (왜 학습으로는 안 되고 스코프로만 되나)

GBDT의 6특징(parallel/thickness/junction/log길이/sin2θ/cos2θ)은 전부 **후보 쌍이 이미 존재해야** 계산되는 관계 특징이다. cross-def로 찢긴 벽은 후보 쌍이 없으니 특징 벡터가 생성되지 않고, 따라서:

- 어떤 분류기도 그 벽을 양성으로 예측할 기회를 못 얻는다(그 행이 데이터셋에 없음).
- 재현율의 상한은 “후보 생성기가 만들어 준 진짜 벽의 비율”로 **하드 캡**된다.

P6은 이 캡을 올린다. 즉 P6의 기여는 “F1을 얼마 올린다”가 아니라 “**후보 생성기의 recall 천장을 얼마나 올리는가**”로 측정되어야 정직하다. 이 값이 곧 §6 Cell A/B/C가 재는 것이다. 만약 cross-def 찢김이 실제로 드물다면(합성 folded recall이 이미 높다면) 천장은 이미 충분하고 P6은 불필요 — 그 경우 P6은 스스로 죽는다(outcome B, §6·§8.5).

### 3.4 정직한 경계 — P6가 못 움직이는 숫자

- P6은 **CubiCasa val F1 0.2358도, GBDT 0.517도 직접 못 올릴 수** 있다(CubiCasa가 이미 flatten이면). 이 숫자들로 P6을 정당화하면 안 된다.
- P6의 정당한 수치는 **1.dwg의 B3(벽-제로 도면율) 추가 감소분**과 **합성 분할팩의 folded↔unfolded recall 격차**다. 이 둘만이 P6의 실측 근거다.
- P6은 정밀도(FP)를 안 고친다. 전이의 FP 주범(화살표/문/창/치수선)은 P6 사정권 밖 — 그건 CL-B의 정션 후필터·다증거 격자(calibration P1)나 학습(CL-F)의 몫.

---

## 4. 데이터·컴퓨트 요구

### 4.1 로컬 실행 계획 (기본)

P6은 **로컬 CPU 전용**이다. GPU도 DGX도 불요(제안 compute plan과 일치). 필요 자산:

- 1.dwg staged DXF(이미 보유), 합성 분할팩(PR-1 생성기의 분할 확장 — §7 T2), ezdxf(전개), NumPy(fast_score 재사용).
- RAM 64GB 안에서 전개. 병목은 최대 412,775 선분 def.

### 4.2 메모리 계측 & 412,775 선분 병목 — 선(先)계측 의무

“전개하면 다 된다”는 조용한 폭발을 감춘다(FM2/FM8: rc=0 ≠ 성공). 그래서 전개는 **계측 우선**:

- def를 선분 수로 정렬해, 작은 것부터 전개하며 (a) 전개 후 선분 수, (b) 후보쌍 수, (c) 피크 RSS(상주 메모리)를 로그.
- 412,775 선분 def는 격자 인덱스(§2.6)로 스트리밍 처리 — 전체 후보를 메모리에 물지 않고 셀 단위로 소진.
- 사전등록 상한(C·n, 64GB) 초과 시 그 def는 “feasibility BLOCKED”로 기록하고 kill 신호로 집계(§6 Cell D).

### 4.3 DGX 계획 (분리 — 그리고 불요 논증)

DGX Spark(Ornith-35B)는 현재 unreachable이고, P6은 **DGX가 필요 없다.** P6은 신경망 추론이 아니라 결정론적 기하 전개이므로 DGX가 살아나도 쓰지 않는다. 만약 후보 폭발이 로컬 상한을 넘으면, 답은 “DGX로 옮기기”가 아니라 “공간 인덱스 강화 / def 배치 스트리밍 / kill”이다. DGX는 이 제안의 어떤 셀에도 등장하지 않는다 — 이는 P6이 저비용·저의존이라는 미덕의 이면이다.

---

## 5. 구현 계획

### 5.1 모듈·파일 골격 (신규는 최소, 재사용 최대)

```
wsd/expand/
  world_assemble.py     # §2.2 전개 드라이버 (ezdxf virtual_entities 위임)
  provenance.py         # §2.5 핸들 안정 해시, def_chain 키
  normalize_curves.py   # ARC/SPLINE→선분열, HATCH 경계 (CL-B와 공유)
wsd/pairs/
  world_pairs.py        # §2.4 전개 후 쌍 탐지 = fast_score 재사용 래퍼 + cross_def_flag
  spatial_index.py      # §2.6 격자/R-tree, 후보 상한 계측
wsd/probe/
  folded_unfolded.py    # §2.8 판별 함수, def별 folded/unfolded/recovered/cross_def
  explosion_bench.py    # §4.2 메모리·후보수 계측 하네스 (R12)
```

신규 코드의 무게중심은 `world_assemble.py`(전개 재귀·provenance·미지원 격리)와 `spatial_index.py`(폭발 방어)이며, 변환 수학과 쌍 채점은 **기존 자산 위임**이다.

### 5.2 기존 도구 접속점

- **`cubicasa_ir`**(SEG-IR 빌더): 전개 입력 IR을 여기서 받는다. 단, CubiCasa 경로는 이미 flatten일 수 있으므로(§3.1), P6의 전개는 **1.dwg 경로에서 우선 배선**. `cubicasa_ir`의 `<use>`/블록 처리 방식을 먼저 감사(요검증)해 “CubiCasa에 cross-def 패턴이 실재하는가”를 확인.
- **`fast_score`**(NumPy 동치 고속 채점기): `world_pairs.py`는 fast_score를 **그대로** 부른다. 입력만 “per_def 세그먼트” 대신 “월드 전개 세그먼트”로 바꾼다. 채점 로직 재발명 없음 → 결과 비교가 스코프 변화 단일 변인이 됨.
- **`evidence_grid`**: folded/unfolded/recovered/cross_def를 def별 셀로 적재해 증거 xlsx로 봉인(평가 원칙: 증거 xlsx 의무).
- **`cubicasa_ml`**(GBDT 파이프라인): P6이 recall 천장을 올리면, 그 위에서 GBDT 재현율이 오르는지 **하류 확인**용으로만 접속(P6 자체 셀 아님 — §8.1의 CL-F 접점).

### 5.3 예상 개발 규모

- `world_assemble.py` + `provenance.py`: 소~중(전개 재귀·해시·미지원 격리). ezdxf 위임 덕에 변환 수학은 얇다.
- `spatial_index.py` + `explosion_bench.py`: 중(격자·계측·상한 로직).
- `folded_unfolded.py`: 소(기존 탐지기 두 번 호출 후 차집합).
- 총량은 “새 알고리즘”이 아니라 “배관+계측” 규모. 최저비용 프로브(§6 Cell C)는 며칠 내 도달 가능(프로브 큐 3번의 1–2일과 정합).

---

## 6. 실험 셀 정의

원칙 고정: **val=개발·튜닝, test=방법당 단발, 합격선은 실행 전 봉인(prereg), 셔플/센티널 대조 의무, 증거 xlsx 의무, 실패도 사유와 함께 기록.** 합성 생성 셀만 시드가 있고, 실도면 셀은 고정 자산이라 시드 없음. 셀은 5개 — 방법이 요구하는 최소(과소·과잉 금지): 베이스라인(A)·합성 판별(B)·실측 프로브(C)·폭발 상한(D)·metamorphic(E).

### Cell A — v0 per_def 베이스라인 선계측 (T9/T21·T34)
- **가설**: 현재 per_def 탐지기는 분할된 벽 쌍을 놓친다(“코드 확정 결함”의 실측 status화).
- **지표**: 분할-합성 픽스처에서 per_def(folded) 벽 쌍 recall.
- **제안 합격선(봉인)**: folded recall ≤ 0.2 (제안의 “의도적 miss” 밴드).
- **킬 조건**: folded recall ≥ 0.9 → 분할 손실 전제가 거짓 → **P6 전제 붕괴**, 중단.
- **예산**: 로컬 CPU, 수 시간. **시드**: 합성 생성 시드 기록.
- **역할**: T34(“인용된 결함이 experiment_executed:false”)를 해소하는 재-status 실험. P6의 나머지가 서는 토대.

### Cell B — 분할-합성 folded vs unfolded 판별 (핵심 discrimination)
- **가설**: 벽을 두 블록에 쪼갠 IR에서, 전개 후에만 쌍이 회수된다.
- **지표**: 동일 픽스처에서 folded recall, unfolded recall.
- **제안 합격선(봉인)**: **folded recall ≤ 0.2 ∧ unfolded recall ≥ 0.9** → 스코프 가설 지지(outcome A: `kills: reigning` = def quotient가 틀렸다).
- **킬 조건**: unfolded도 < 0.9(둘 다 miss) → outcome B: `kills: counter`(전개해도 못 잡으면 스코프가 원인이 아님) → P6 반증.
- **예산**: 로컬 CPU. **시드**: 분할 배치·기하 다양성 시드 다수, 기록.
- **의존**: PR-1 생성기의 “벽 2블록 분할” 확장 필요(§7 T2).

### Cell C — 실측 1.dwg 최저비용 프로브 (cheapest probe)
- **가설**: 실측 발산 `*U*` def의 상당수가 전개 후 쌍을 만든다(분할 패턴이 실재).
- **지표**: top-20 발산 def 중 INSERT 자식 있는 10개에서 def별 folded vs unfolded 쌍 수, 그리고 recovered_n>0인 def 비율.
- **제안 합격선(봉인)**: 실측 `*U*` top 발산 중 **≥ 30%** 가 전개 후 쌍 생성.
- **킬 조건**: < 30% 또는 이득 0 → **실측 축에서 P6 사망**(진실하지만 무관).
- **예산**: 로컬 CPU, 프로브 큐 3번의 1–2일 내. **시드**: 없음(고정 실도면).
- **필수 선결(§7)**: 발산 def 집합은 **CL-A 재계산본**을 쓴다(원 `_score_divergence` 정렬 아티팩트 금지, 공격 C). dev는 10 def, 확정은 **disjoint 20 def에서 단발**(봉인 후 1회) — 프로브 과적합 방지.

### Cell D — 후보 폭발 상한·복잡도 계측 (R12)
- **가설**: 공간 인덱스로 후보 수·메모리가 선형 근처로 억제된다.
- **지표**: def 선분 수 n 대 후보쌍 수, 피크 RSS(최대 412,775 선분 def 포함).
- **제안 합격선(봉인)**: 후보쌍 ≤ C·n (C=20 사전봉인) ∧ 피크 RAM ≤ 64GB.
- **킬 조건**: 상한 초과(초선형 폭발/OOM) → **실용 불가로 P6 사망**(제안 kill 조건 그대로).
- **예산**: 로컬 CPU + 메모리 계측. **시드**: 없음.

### Cell E — metamorphic explode 불변 (CL-D 공유·센티널 의무)
- **가설**: P6 전개 탐지기는 explode 불변(블록에 담기든 폭파하든 같은 판정), per_def는 불변 위반.
- **지표**: (조립 판정) vs (모델스페이스로 완전 explode한 판정)의 쌍집합 Jaccard 일치도.
- **제안 합격선(봉인)**: 전개 경로 일치도 ≥ 0.95, per_def 경로는 유의하게 낮음. **+ 0벽/전벽 센티널 + recall 최저선을 랭킹 사용 전 탑재**(공격 F/T7 의무 수정).
- **킬 조건**: 전개 경로도 explode 불변을 어김 → 전개 구현 결함 의심, 파이프라인 수리 우선.
- **예산**: 로컬. **시드**: 없음.

> **test 단발 처리**: 합성(B) test 패밀리와 실측(C) 확정 disjoint 셋은 각 1회만 소비. val 튜닝은 §2.7 노브에 한정하고, 봉인된 값으로만 test 실행.

---

## 7. red team 티켓 응답

패널 OPEN 티켓 34건 중 P6에 걸리는 것과 대응(해소/수용):

- **T1 — 대리(truth proxy) 독립성(sev 0.75, 최우선)**: {합성·외부셋·metamorphic·silver}가 같은 “평행 이중선” prior를 공유. **P6도 이 prior 위에서 쌍을 찾으므로 여기서 자유롭지 않다 — 수용(인정).** 다만 P6이 더하는 것: cross-def 쌍은 **라벨·이름 신호가 원리상 개입할 수 없는 순수 구조 관측**(핸들 안정 해시, §2.5)이라, silver/레이어 prior와 **독립인 축**을 하나 보탠다. 그리고 P6은 silver를 학습·평가 어디에도 안 쓴다(silver-독립). → PR-2/CL-E의 동일-def 3원 불일치 감사에 P6의 folded/unfolded 축을 제공.
- **T2 — 생성기 부재(sev 0.70)**: 벽 합성 생성기가 아직 없음(PR-1). **P6의 합성 arm(Cell A/B)은 “벽을 2블록에 분할 배치” 확장을 요구하므로 PR-1이 하드 선결 — 수용.** 완화: PR-1 도착 전에는 **실측 arm(Cell C, 1.dwg)만** 돌린다(생성기 불요). 즉 P6은 생성기 부재에도 부분 착수 가능.
- **T3·T4·T8 / CL-A 법의학(공격 C, sev 0.60)**: top-20 발산 def가 `_score_divergence` **정렬 설계의 산물**일 수 있음 + 인용 핸들 실재성·INSERT 깊이 미검증. **P6의 Cell C가 바로 이 발산 집합에 의존하므로 CL-A가 하드 선결 — 해소 배선.** Cell C는 원 정렬본이 아니라 CL-A **재계산 발산 집합**을 입력으로 못박고, CL-A의 “INSERT 깊이·핸들 실재성” 감사가 “cross-def 벽 조각이 실재한다”를 먼저 확인해 준다. CL-A가 “발산은 아티팩트”라 판정하면 Cell C는 미실행·P6 실측 arm 보류.
- **T5 — 라이선스(sev 0.65)**: 외부셋 권리 미해결. **P6 본진은 1.dwg(자사 도면)+자체 생성 합성이라 상대적으로 청정 — 부분 수용.** CubiCasa 접속은 P6의 부차 경로이며 counsel(PR-3) 전엔 CubiCasa arm 미착수. 즉 P6은 라이선스 게이트에 덜 묶이는 저위험 경로.
- **R12 — quadratic 후보 폭발 상한 사전등록**: **P6 자신의 kill 조건. 해소 = Cell D**로 상한(C·n, 64GB)을 봉인하고 초과 시 kill. 조용한 폭발을 성공으로 오독하지 않게 계측 우선(§4.2).
- **T9/T21 — v0 베이스라인 선계측**: **해소 = Cell A.** 어떤 이득 주장도 per_def v0 대비로만 말한다.
- **T34 — 인용 R-레인 status화**: “per_def가 cross-def 벽을 놓친다”는 인용이 experiment_executed가 되도록 **Cell A/B가 그 실험 자체**. 수사 인용을 실측으로 승격.

수용(위험 인정)으로 남기는 것: T1의 “같은 이중선 prior” 공유는 P6이 완전히 해소 못 한다 — P6은 이중선 패러다임 **안에서** 스코프를 고칠 뿐, 패러다임 자체를 벗어나지 않는다(그 탈출은 CL-J의 몫, §8.4).

---

## 8. 인접 제안과의 관계

### 8.1 CL-B 내부 — P6은 이미 병합된 부품
CL-B(커버리지-완전 결정론 v1)는 [platt P1 + calibration P1(다증거 격자) + **feyerabend P6(INSERT 월드좌표 전개)** + feyerabend P2(치수-정박 상대대역) + doe P2(Taguchi 강건화)]의 합본이다. 분업:
- **P6 = “transform 전개(스코프 수정)”** — 어떤 후보가 **존재하는가**를 바꾼다.
- **calibration P1 = 다증거 격자** — 존재하는 후보를 **더 잘 채점**한다. → P6과 직교(P6이 후보를 만들고 P1이 점수화). 병합 마찰 없음.
- **feyerabend P2 = 상대대역** — 두께 대역의 **정의**를 바꾼다. P6의 §2.4 대역 노브에 꽂으면 됨. 직교.
- **doe P2 = Taguchi** — 노브 강건화. P6 노브(§2.7)를 그 실험 설계에 태울 수 있음.
- **정규화(LWPOLYLINE/MLINE/ARC)** 부품은 P6의 §2.2 곡선 정규화와 **공유 코드**.

### 8.2 CL-A — 하드 선결(순서 의존)
CL-A(E1 법의학 감사)는 P6 실측 arm의 **입력 정당성**을 준다(§7 T3). CL-A가 먼저 돌아 “발산 def가 실재 구조지 정렬 아티팩트가 아니다 + INSERT 자식·핸들이 실재한다”를 확인해야 Cell C가 의미를 가진다. **P6은 CL-A 없이 실측 주장 불가.**

### 8.3 CL-D — metamorphic 공유
Cell E(explode 불변)는 CL-D(metamorphic 배터리)의 explode 관계와 같은 심판이다. CL-D의 의무 수정(0벽/전벽 센티널 + recall 최저선, T7)을 P6 Cell E가 그대로 상속한다. P6은 CL-D에 “per_def의 explode-불변 위반”이라는 구체 사례를 공급.

### 8.4 CL-J(feyerabend P1, room-first)와의 긴장 — 같은 좌석의 더 급진적 형제
CL-J는 “centerline→room을 **역전**: room/face가 먼저, 벽은 dual의 bridge”라는 관측 언어 자체를 깨는 최강 반문이다. P6과의 관계:
- **P6은 덜 급진적**: 이중선 쌍 패러다임을 **유지**하며 스코프만 고친다.
- **긴장이 아니라 층위 차**: room-first조차 “먼저 월드좌표로 조립”이 선행되어야 face를 만든다. 즉 P6의 전개는 CL-J의 **전처리로도 재사용**된다. CL-J가 이겨도 P6의 조립 단계는 살아남는다.
- **차별점**: CL-J가 벽을 dual로 재정의하면 “쌍 검출” 자체가 불필요해질 수 있다 — 그 경우 P6의 **쌍 부분**은 CL-J에 흡수되고, P6의 고유 기여는 “조립” 하나로 축소된다.

### 8.5 이 제안이 죽어야 하는 조건 (정직하게)
P6이 죽어야 하는 조건을 숨기지 않는다. 하나라도 참이면 밀어붙이지 않는다.

1. **전제 붕괴**: Cell A에서 folded recall이 이미 ≥0.9 — per_def가 사실은 안 놓친다. 그러면 dissolved_fact가 애초에 견고했고 P6은 허수아비를 때린 것 → **사망**.
2. **counter가 죽음(outcome B)**: Cell B에서 unfolded도 <0.9 — 전개해도 못 잡는다. 스코프가 원인이 아니라 다른 데 문제 → **P6 반증**.
3. **실측 무관**: Cell C에서 <30%, 이득 0 — 합성에선 되는데 실도면엔 cross-def 분할이 거의 없다. “참이지만 무관(true but irrelevant)” → **실측 축 사망**.
4. **폭발**: Cell D에서 후보가 상한(C·n, 64GB) 초과로 폭발 — 이론상 옳아도 412,775 선분에서 실용 불가 → **feasibility 사망**.
5. **CL-A가 표적을 지움**: CL-A가 “발산은 정렬 아티팩트, `*U*`에 cross-def 벽 조각 없음”으로 판정 → P6 실측 표적 소멸.
6. **CubiCasa 무접속 + 1.dwg 희소**: 라벨/숫자가 사는 CubiCasa엔 패턴이 없고(이미 flatten) 1.dwg에도 희소하면, P6은 “고칠 데는 있지만 잴 데가 없다” → 프로그램 우선순위에서 자연 탈락(PARK 후 재검토).

정직한 요약: **P6의 최선의 결말은 Cell A/B가 outcome A(kills: reigning)를 주고 Cell C가 ≥30%를 주고 Cell D가 상한을 지키는 것**이다. 이 중 하나라도 무너지면 P6은 CL-B에서 조용히 “조립 전처리” 역할로 축소되거나, 완전히 죽는다 — 그리고 그 판정은 이 도시에가 아니라 봉인된 밴드가 내린다.

---

DOSSIER_COMPLETE: feyerabend_P6
