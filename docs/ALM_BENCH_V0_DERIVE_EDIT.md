# ALM-Bench v0 — DERIVE / EDIT / CHECK task-family spec

이 문서는 `docs/ALM_BENCH_V0.md`(READ task bank)를 확장하는 세 개의 task family를
정의한다: **DERIVE**(IR로부터 파생 수치/구조를 계산), **EDIT**(IR을 스크립트로
변형한 뒤 재렌더링), **CHECK**(의도적으로 오염된 IR에 대해 게이트 판정을
재현). 세 family 모두 round-trip-verified DWG IR을 기반으로 하며, gold는 항상
생성기 또는 게이트가 계산한다 — 손으로 입력한 gold는 없다.

본 문서는 스펙(설계)만 다룬다. generator/코드는 범위 밖이다.

## Grading principles

- **Machine-gradable by gates.** 모든 task는 L0–L3 중 최소 하나의 게이트로
  자동 채점된다. 채점 임계값은 exact — L1 기하는 canonicalize 후 1e-6 수치
  동등성, L2/L3는 게이트가 반환하는 `ok|blocked` 판정이다.
- **Gold is computed or gate-derived, never hand-typed.** DERIVE gold는 검증된
  derivation pair(입력 IR → 출력 수치)에서, EDIT gold는 스크립트 IR-edit를
  적용한 뒤 재렌더링한 산출물에서, CHECK gold는 오염된 IR에 게이트를 돌려 나온
  판정(`ok`/`blocked` + 원인)에서 나온다.
- **Success is a function of search budget.** 각 task는 두 조건에서 성공률을
  보고한다: single-shot baseline(1회 시도) vs. breadth `b`의 deliberate search
  (`b`회 후보 생성 + 게이트로 선택). `## Budget axes`에서 축을 고정한다.
- **Adversarial variants are mandatory.** 각 family는 naive grader(카운트만
  보는 채점기)는 통과시키지만 semantic gate(L2/L3)는 걸러내는
  count-preserving corruption 변형을 최소 1개 포함해야 한다. 근거:
  `tools/semantic_gates/ipss.py`의 IPSS suite — 5개 등록된 mutation
  (`dim_measurement_swap`, `dim_xline_shift`, `insert_retarget`,
  `def_entity_reparent`, `rotation_sign_flip`) 전부 naive gate는 `ok`를
  반환하지만 dim-geometry 또는 block-topology 게이트가 5/5 걸러낸다
  (**IPSS 5/5**, `tests/unit/test_ipss.py`).

## Family: DERIVE

**Task template** — input: round-trip-verified IR(또는 IR 서브그래프) 하나.
instruction shape: "이 IR에서 [파생 수치/구조]를 계산하라" (예: bounding box,
누적 길이, 엔티티 카운트 histogram, block-reference reachable subgraph 크기).
expected artifact: 스칼라 또는 소구조 JSON (단위/좌표계 명시).

**Gold construction rule** — 기존에 확보된 verified derivation pair(입력 IR →
파생 산출물, 이미 L1/L2로 검증된 쌍)에서 gold를 가져온다. 신규 계산을 gold로
쓰지 않는다 — pair가 없으면 task를 만들지 않는다.

**Grading gates** — L0(스키마: 반환 타입/필드 존재) + L1(수치 동등성,
canonicalize 후 1e-6) 필수, 구조적 파생(예: reachable subgraph)이면 L2
(block-reference topology equality) 추가.

**Success metric** — L1 수치 오차 ≤ 1e-6 비율(single-shot) 및 breadth `b`
내 최소 1개 후보가 L1 통과하는 비율(search).

**Example task sketches**

- `DERIVE-001` — 이 도면의 전체 bounding box(min/max XYZ)는 얼마인가?
- `DERIVE-002` — 이 block definition이 참조하는 모든 하위 block의 reachable
  set 크기는 몇 개인가?
- `DERIVE-003` — 이 IR에 있는 dimension 엔티티들의 측정값 합계는 얼마인가?

## Family: EDIT

**Task template** — input: round-trip-verified IR + 자연어 편집 지시(예: "이
insert의 block 참조를 X로 바꿔라", "이 dimension의 xline을 Y만큼 이동하라").
instruction shape: "[대상 엔티티/구조]를 [변형]하라". expected artifact: 편집된
IR(또는 그로부터 재렌더링된 DWG/DXF).

**Gold construction rule** — 스크립트로 작성된 IR-edit(결정적 변환 함수, 예:
`ipss.py`의 mutation 함수와 동일한 형태)를 원본 IR에 적용한 뒤 재렌더링한
산출물이 gold다. 편집 스크립트 자체가 gold 생성기이며, task 채점 시
후보 산출물을 gold와 canonicalize 후 비교한다.

**Grading gates** — L1(편집 대상 외 나머지 geometry가 원본과 수치 동일 —
scoped diff) + L2(편집이 의미적으로 일관 — 예: dimension 편집이면 measurement-
geometry concordance, block 편집이면 topology equality) + 편집이 도면 규약을
건드리면 L3.

**Success metric** — "편집 대상만 변경, 나머지는 불변"을 만족하는 후보 비율
(single-shot) 및 breadth `b` 내 그 조건을 만족하는 후보가 나오는 비율
(search). 대상 외 변경(collateral damage)은 실패로 카운트.

**Example task sketches**

- `EDIT-001` — 이 insert 엔티티가 참조하는 block을 다른 block으로
  재지정하라(나머지는 불변).
- `EDIT-002` — 이 dimension의 xline을 지정된 오프셋만큼 이동하라(측정값은
  기하와 일치해야 함).
- `EDIT-003` — 이 block definition 안의 지정된 엔티티를 다른 부모 def로
  reparent하라(참조 그래프 무결성 유지).

## Family: CHECK

**Task template** — input: 의도적으로 오염된 IR(count-preserving corruption
적용됨) + "이 IR에 결함이 있는가? 있다면 어디인가?" 형태 instruction. expected
artifact: 판정(`ok`/`blocked`) + (blocked면) 원인 엔티티/게이트 이름.

**Gold construction rule** — 오염된 IR에 실제 게이트(L2/L3)를 돌려 나온
판정이 gold다. 오염 스크립트(mutation 함수)와 게이트 실행 결과가 함께 gold를
구성 — naive(L0) 채점만으로는 gold를 만들 수 없다(정의상 naive는 통과시킨다).

**Grading gates** — L0(naive count 비교, 참고용 — 통과해도 무효화 안 됨) +
L2(dim-geometry concordance 또는 block-topology equality, 최소 하나가
`blocked`를 반환해야 정답) + 판정 사유가 도면 규약 위반이면 L3.

**Success metric** — 후보의 판정이 게이트 gold 판정과 일치하는 비율
(single-shot) 및 breadth `b` 내 일치하는 후보 비율(search). "naive가 ok라고
했으니 ok"라고 답하면 항상 오답 처리(어드버서리얼 목적).

**Example task sketches**

- `CHECK-001` — 이 IR의 dimension 측정값들이 실제 기하와 일치하는가?
- `CHECK-002` — 이 IR의 insert 참조가 존재하는 block def를 가리키는가?
- `CHECK-003` — 이 block definition의 엔티티 소속(부모 def)이 원본과
  일치하는가?

## Adversarial variants

다음은 IPSS suite에 이미 등록되어 count-preserving하면서 naive grader는
통과시키지만 semantic gate가 걸러내는 corruption들이다 — **IPSS 5/5**
(`tools/semantic_gates/ipss.py`, `MUTATIONS` 5건 전부 dim-geometry 또는
block-topology 게이트에 걸림, `tests/unit/test_ipss.py`에서 확인됨):

- **Dimension measurement swap** (`dim_measurement_swap`) — 두 dimension
  엔티티의 measurement 값을 서로 바꿔친다. 엔티티 카운트/타입 히스토그램은
  불변이지만 measurement-geometry concordance가 깨진다 → L2 dim-geometry
  게이트가 `blocked`.
- **Insert retarget** (`insert_retarget`) — insert 엔티티의 block 참조를 다른
  기존 block으로 바꾼다. 엔티티 카운트는 불변이지만 참조 그래프의 reachable
  subgraph가 달라진다 → L2 block-topology 게이트가 `blocked`.
- **Def entity reparent** (`def_entity_reparent`) — block definition 소속
  엔티티를 다른 def로 옮긴다. 전체 엔티티 카운트는 불변이지만 def별 구성이
  달라진다 → L2 block-topology 게이트가 `blocked`.
- (suite에 추가로 `dim_xline_shift`, `rotation_sign_flip` 포함, 동일하게
  naive-pass/semantic-blocked)

CHECK family의 모든 task는 이 5개 중 최소 하나의 corruption 클래스를
포함해야 한다. DERIVE/EDIT family도 스코프가 맞으면(파생/편집 대상이
dimension 또는 block topology와 관련) 동일 corruption을 negative-control로
재사용할 수 있다.

## Budget axes

- **Single-shot baseline** — breadth `b=1`, 재시도 없음. 성공 = 첫 후보가
  해당 family의 게이트를 통과.
- **Deliberate search, breadth `b`** — `b`개 후보를 생성하고 게이트로 선택
  (게이트 통과 후보 중 첫 번째, 또는 전부 실패 시 실패). `b ∈ {1, 4, 8, 16}`을
  기본 스윕으로 본다.
- 두 축 모두 family × corruption class 별로 별도 보고 — 축을 합쳐 평균내지
  않는다(헌법 R9: 충돌/변량을 뭉개지 않음).

## Open items

- DERIVE gold pair 소스 카탈로그(어느 verified derivation pair들이 재사용
  가능한지) 미정 — generator 단계에서 확정 필요.
- EDIT의 "편집 대상 외 불변" 스코프 정의(scoped diff의 정확한 경계) 미정 —
  L1 스코프 정책을 CHECK/EDIT 공통으로 만들지 별도로 만들지 미결.
- L4(human acceptance/golden review) 연동 방식은 이 스펙에서 다루지 않음 —
  v0는 L0–L3만 자동 채점.
- IPSS 5개 mutation 외 추가 corruption class(예: handle collision, layer
  reparent) 도입 여부는 후속 스펙에서 결정.
