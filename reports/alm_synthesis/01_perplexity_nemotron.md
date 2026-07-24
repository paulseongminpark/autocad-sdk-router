# Perplexity Nemotron3 Ultra v1 → ALM 라운드트립 합성 노트

**소스:** `D:\dev\_ariadne\alm\docs\perplexity_nemotron3ultra_v1.md` (2026-06-17 Perplexity 리서치 export)  
**미션 맥락:** DWG extract→regenerate→diff 라운드트rip — modelspace **375/375**, block-INTERIOR **67.6%** (결손: hatch-like def-entity ~6,867종, anonymous dynamic-block def ~320)

---

## 1. 알고리즘 (그래프·GNN·제약·기하 재구성)

### 1.1 CGAL Arrangement_2 + B-Rep 위상 구성
**출처:** `## 2.2 위상 구성 알고리즘: Arrangement + B-Rep Construction`

L0 커브(Line/Arc/Polyline/Spline)를 XY 평면에 투영한 뒤 CGAL `Arrangement_2`(또는 Bentley-Ottmann 대체)로 DCEL을 만들고, 3D는 OpenCASCADE B-Rep로 쉘/솔리드를 구성한다. 하프에지 twin/next/prev와 L0 UID 역참조(`l0_to_l1_*`)로 기하-위상 추적성을 유지한다.

**라운드트rip 매핑:** hatch 경계·닫힌 polyline·block 내부 face를 “면 후보”로 승격해 def-entity 누락을 위상 레벨에서 검출·재생성할 수 있다. **실행가능성:** 중 — CGAL/OCC 의존은 무겁지만, 2D arrangement만으로도 INTERIOR block 내 hatch boundary 매칭에 직접 기여.

### 1.2 하프에지 DCEL (2D/3D 통합)
**출처:** `### 2.1 하프에지 기반 위상 데이터 구조 (2D/3D 통합)`

Vertex/Edge/Face/Loop/Shell/Solid를 하프에지 중심으로 통합 표현하고, 매니폴드·watertight 불변식(twin 존재, edge-face count=2)을 테스트로 고정한다.

**라운드트rip 매핑:** regenerate 시 “닫힌 loop 없음” hatch/region 오류를 L1 불변식 위반으로 조기 차단. **실행가능성:** 높 — 순수 데이터 구조+불변식; 기존 diff 파이프라인에 gate 추가만으로 적용 가능.

### 1.3 Rule → ML(GNN) → LLM 3단계 시맨틱 매핑
**출처:** `### 3.3`, `### 3.4`

규칙 후보 → L1 서브그래프 GNN/RT-DETR 앙상블 → 미달 confidence는 LLM 배치 해석.

**라운드트rip:** anonymous def·hatch-like entity를 애매 큐로 분리. **실행가능성:** 낮~중 — 라운드트rip엔 규칙+SHACL 우선.

### 1.4 R-tree + Octree 공간 인덱스
**출처:** `### 2.3`

bbox 기반 hatch↔polyline 매칭 O(N log N). **라운드트rip:** def-entity 6,867종 확장 매칭. **실행가능성:** 높음.

### 1.5 BoundaryAwareMerge + canonical_id dedupe
**출처:** `## 6.2`, `merge_strategy.py`

Block 분할 파싱 후 dedupe·boundary stitch. **라운드트rip:** nested/anonymous def 중복·누락 gate. **실행가능성:** 중.

### 1.6 Topology Agent + 4축 RCA
**출처:** `# 7`, `## 8`

proposal→validate→promote; metric slice로 Data/Label/Schema/Model 분해. **라운드트rip:** 67.6% INTERIOR 저하 축 분리. **실행가능성:** 높음(slice만).

---

## 2. 온톨로지·CAD-건축 시맨틱 표현

### 2.1 TBox: IFC4 + BOT + BRICK 정렬 AEC 코어
**출처:** `### 3.1 온톨로지 스택`, `# knowledge/ontology/aec_core.ttl`

Wall/Door/Window/Space 계층, `hasThickness`/`hostedBy`/`containsSpace` 등 객체·데이터 속성. BuildingElementProxy로 미분류 요소 수용.

**라운드트rip 매핑:** hatch-like def-entity를 우선 Proxy로 ingest 후 subtype refine — regenerate 시 타입 강제 오류 방지. **실행가능성:** 중 — TTL 일부만 차용 가능; DWG native type→Proxy 매핑 테이블이 핵심.

### 2.2 SHACL 한국 건축법 셰이프 + cross-layer 제약
**출처:** `### 3.2 SHACL 셰이프`, `## 5.2 SHACL shape 분리 전략`

`10_geometry_constraints.ttl`, `60_cross_layer_constraints.ttl` 등 레이어별 shape 분리. Door/Window는 topology host evidence 필수, Space는 closed loop evidence 필수.

**라운드트rip 매핑:** “semantic Door without block INSERT host”류 regenerate 결함을 Error급 SHACL로 차단. **실행가능성:** 높 — pySHACL gate를 diff 파이프라인 후단에 추가하기 쉬움.

### 2.3 Property Graph + RDF/OWL 하이브리드
**출처:** `## 11. 요약 #2`, `## 6. Graph DB 스키마`

Kuzu/Neo4j로 순회·OLAP, RDF로 추론·SHACL. Element 노드에 ifc_type/aec_type/layer bbox mirror.

**라운드트rip 매핑:** block def namespace(anonymous `*U`)를 graph node로 유지하면 diff 시 def-entity kind 집계(6,867) 자동화. **실행가능性:** 중 — Neo4j/Kuzu 전체 도입 없이 SQLite+JSON mirror로 축소 가능.

### 2.4 4-ID 전략 (source/canonical/content_hash/versioned)
**출처:** `# 2. Multi-Layer Canonical Graph IR`, `## 2.2 핵심 ID 전략`

`UUIDv5(file_hash, source_path+source_id)`, content SHA256, revision append-only. overwrite 금지.

**라운드트rip 매핑:** anonymous dynamic block def 재생성 시 handle 불안정 → canonical_id로 roundtrip equality 정규화(§10 TestL0RoundTrip). **실행가능성:** 높 — diff normalizer에 즉시 적용 가능한 패턴.

### 2.5 L0↔L5 레이어 분리 (Raw→Geo→Topo→Semantic→Evidence→TaskView)
**출처:** `## 2.1 레이어 정의`, `## 0. 전체 시스템 개요`

L0 append-heavy 원본 보존, L1 recomputable 기하, L2 derivable topology, L3 validated semantic, L4 provenance, L5 materialized views.

**라운드트rip 매핑:** modelspace 100%는 L0/L1, block-INTERIOR gap은 L0 block namespace + L2 hosting 관계에서 추적. **실행가능성:** 높 — 레이어 경계가 extract/regenerate 책임 분리에 그대로 맞음.

---

## 3. 모델링 기법 (IR·검증 게이트·평가 지표)

### 3.1 L0 Property Graph — 정보 손실 제로 ingest
**출처:** `### 1.1 데이터 모델`, `## 2.3 L0 Raw Source Graph`

`raw_attributes` 전체 덤프, `parse_warnings`, `byte_offset`, geometry checksum, `block_ref_chain`, `INSTANCE_OF_BLOCK` edge.

**라운드트rip 매핑:** hatch pattern/scale/angle/solid_fill, INSERT scale/rotation/attribs 보존 → regenerate fidelity 하한 보장. **실행가능성:** 높 — 현재 extract JSON schema 대비 gap checklist로 사용.

### 3.2 Content-Addressable IR Versioning (L4)
**출처:** `## 5. L4: Delta & Versioning`, `IRRepository.diff`

Layer별 ChangeSet(added/modified/deleted), commit author(`parser:v1.2`), `diff(commit_a, commit_b)`.

**라운드트rip 매핑:** extract vs regenerate를 두 commit으로 diff — block-INTERIOR 67.6%를 layer=L0 block_context slice로 출력. **실행가능성:** 높 — git-like diff UX 재사용; CAS 저장소는 파일 hash로 경량화 가능.

### 3.3 proposal → validation → trust promote
**출처:** `# 1. 구현 원칙 재정의`, `## 5.1 파이프라인 단계`

LLM/agent 출력은 proposal graph만, conform graph만 trusted. Auto-fix vs human review queue 분리.

**라운드트rip 매핑:** regenerate 파이프라인에 “미검증 serializer patch” 경로 차단 — silent hatch drop 방지. **실행가능성:** 높 — 정책·상태머신만 도입, ML 불필요.

### 3.4 ConsistencyManager · Shape slice validation
**출처:** `## 3.7`, `## 5.1`, `## 5.3`

evidence 필수·geometry conflict recompute; 변경 subgraph만 SHACL, hatch drop은 auto-fix 금지.

**라운드트rip:** incremental CI + silent drop 방지. **실행가능성:** 높음.

---

## 4. Hatch·Annotation·Dynamic Block 처리

### 4.1 HATCH boundary_paths + pattern 메타
**출처:** `#### 1.2.1 DWG/DXF Parser`, `L0Geometry` Hatch 필드

`_extract_hatch_boundaries`, pattern_name/scale/angle/solid_fill, TOPOLOGICAL edge `boundary_of_hatch`.

**라운드트rip 매핑:** 6,867 hatch-like def-entity kind — boundary path 직렬화·역직렬화 parity가 1순위 결손 후보. **실행가능성:** 높 — parser/serializer 대칭 구현 범위 명확.

### 4.2 Block table 2-pass ingest (modelspace + block def namespace)
**출처:** `#### 1.2.1` parse loop §4-1/4-2

modelspace 엔티티 + `block_table` 각 layout을 `block_context`로 별도 vertex 생성; INSERT→BLOCK_INSTANCE edge.

**라운드트rip 매핑:** INTERIOR block fidelity = def namespace completeness + INSERT transform chain. anonymous `*U` def ~320는 block_table key 보존이 관건. **실행가능성:** 높 — 현재 67.6% gap과 직접 정렬된 설계.

### 4.3 block_ref_chain + 누적 transform
**출처:** `### 1.1 L0Vertex.block_ref_chain`, `_compute_transform`

중첩 INSERT마다 4×4 행렬 누적; raw_attrs에 DXF tags 전량.

**라운드트rip 매핑:** dynamic block parameter 변형 regenerate 시 chain 끊김 → def mismatch. **실행가능성:** 높 — transform stack 테스트 케이스 추가로 검증 가능.

### 4.4 DIMENSION · hatch vs space 질의
**출처:** `§1.2.1 _build_l0_edges` §4, `## 7.3`

DIMENSION-측정대상 link(스켈레톤); face가 hatch annotation vs space boundary인지 ontology+rule 분류.

**라운드트rip:** block 내 annotation drop·타입 오분류 교정. **실행가능성:** 중 — layer/pattern 규칙으로 LLM 대체 가능.

---

## 5. 평가 방법론

### 5.1 L0 normalize roundtrip equality
**출처:** `class TestL0RoundTrip`

원본→L0→native serialize→re-parse→`l0_normalize` equality (UID/순서 무시). geometry checksum per vertex.

**라운드트rip 매핑:** global 375/375의 정식 정의; block slice는 normalize key에 `block_context` 포함. **실행가능성:** 높 — 현재 diff 도구의 golden standard.

### 5.2 Entity count · topology edge · SHACL violation parity
**출처:** `## 6.3 병렬 파싱 검증`, `### 검증 항목`

single vs partitioned: entity count 동일, topology edge 허용 오차, semantic class distribution, SHACL violation count 동일, deterministic hash stability.

**라운드트rip 매핑:** hatch-like kind 6,867 추적을 “entity count by raw_type × block_context” dashboard로. **실행가능성:** 높 — 집계 SQL/JSON diff로 즉시.

### 5.3 Metric slice + 4-axis RCA
**출처:** `## 8. 4축 진단`, `_compute_metric_slices`

domain/class/split별 mAP 등; schema 축 SHACL violation vs metric 상관.

**라운드트rip 매핑:** fidelity를 modelspace vs block-INTERIOR vs hatch-only vs anonymous-def slice로 분해 — 67.6% blind spot 제거. **실행가능성:** 높 — RCA 프레임만 차용.

### 5.4 Golden pipeline · partition equivalence
**출처:** `TestPipelineIntegration`, `## 6.3`

L3 mAP/quantity/code check; partition vs monolithic entity·SHACL parity.

**라운드트rip:** L0/L1 통과 후 semantic regression; block partition 회귀. **실행가능성:** 중.

---

## Top 10 — 훔칠 만한 아이디어 (우선순위)

| Rank | 아이디어 | 핵심 출처 | 라운드트rip 100% 기여 | 실행가능성 |
|------|----------|-----------|------------------------|------------|
| **1** | L0 block 2-pass ingest + `BLOCK_INSTANCE` edge + `block_ref_chain` | `#### 1.2.1`, `### 1.1` | INTERIOR 67.6%·anonymous def 320 직격 | **높음** |
| **2** | HATCH `boundary_paths`/pattern/solid_fill 대칭 serialize | `#### 1.2.1`, `L0Geometry` | hatch-like 6,867 kind parity | **높음** |
| **3** | 4-ID + `l0_normalize` roundtrip equality gate | `## 2.2`, `TestL0RoundTrip` | 375/375 정의·block slice normalize | **높음** |
| **4** | fidelity metric slice (modelspace / block / hatch / anonymous-def) | `## 8`, `## 6.3` | 67.6% 원인 분해 자동화 | **높음** |
| **5** | Layer별 IR diff (`IRRepository.diff`) | `## 5. L4` | regenerate regression per layer | **높음** |
| **6** | SHACL cross-layer gate (host/loop evidence) | `## 5.2`, `### 3.2` | 잘못된 door/hatch/space regenerate 차단 | **높음** |
| **7** | proposal→validate→promote (trusted graph) | `# 1. 구현 원칙` | serializer silent drop 방지 | **높음** |
| **8** | hatch↔polyline spatial match (`boundary_of_hatch`) | `§1.2.1 _build_l0_edges` | boundary 재구성·누락 탐지 | **중** |
| **9** | Arrangement/DCEL L1 + closed-loop invariant | `## 2.2`, `TestL1TopologyInvariants` | hatch loop 유효성 검증 | **중** |
| **10** | Block-partition merge + canonical dedupe | `## 6.1–6.3`, `merge_strategy` | 대형 DWG scale-up; equivalence proof | **중** |

---

## 한 줄 결론

Nemotron3 Ultra v1은 **“L0 lossless block/hatch ingest + layer diff + SHACL gate + slice metric”** 조합이 ALM 라운드트rip 100%에 가장 직접적이며, GNN/GraphRAG/분산 파싱은 **block-INTERIOR·hatch gap 해소 후** scale·semantic refinement 단계에서 가치가 있다. Dynamic block anonymous def는 문서상 explicit handler는 없으나 **block_table 2-pass + canonical_id + transform chain**이 사실상의 해법 골격이다.

*합성 범위: 미션 관련 섹션만 추출. MCP·배포·KServe·Docker 등 운영 레이어는 의도적으로 제외.*
