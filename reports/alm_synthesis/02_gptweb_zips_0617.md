# GPT-Web 설계 패키지 합성 (2026-06-17 근접)

> **미션**: modelspace 375/375 roundtrip 달성, block-interior fidelity 67.6% → **100%**  
> **소스**: `CAD_AI_READY_INFRA_EXPERIMENT_DESIGN_PROD_READY_20260617.zip`, `cad_gnn_production_experiment_pack.zip`, `ALM_V4_PRODUCTION_DESIGN_PACKAGE.zip` (내부 `ALM_V4_RESULTS_20260615.source.zip` 67KB는 스킵)  
> **추출**: `runs/alm_extract/d2/{infra_0617,gnn_pack,alm_v4}/`

---

## 1. CAD_AI_READY_INFRA (infra_0617) — 97 text files

### 1.1 목차 인벤토리 (요약)

| 경로 | 한줄 |
|------|------|
| `README.md` | Run ID `CAD_AI_READY_IR_PROD_EXPERIMENT_20260617`, BEG-IR 프로덕션 실험 패키지 진입점 |
| `docs/00_EXECUTIVE_PROPOSAL.md` | CAD/BIM → AI-ready Building Evidence Graph IR 변환 제안 |
| `docs/02_BUILDING_EVIDENCE_GRAPH_IR.md` | 8계층 BEG-IR; `BlockDefinition`/`BlockInstance` raw 타입 명시 |
| `docs/04_VALIDATION_DESIGN.md` | geometry×topology×semantic×route_agreement 신뢰도 식; block/swing arc 문 증거 |
| `methodology/00_EXPERIMENT_METHOD.md` | E0~E10 실험 사다리 + route/feature/threshold ablation 매트릭스 |
| `methodology/03_ABLATION_STUDY_PLAN.md` | `F1_no_layer_block` 등 feature/route/validator ablation |
| `configs/quality_gates.yaml` | G0~G8 게이트; canary F1·schema·lineage 임계 |
| `configs/experiment_matrix.yaml` | E0~E7 패킷 매핑 실험 매트릭스 |
| `packets/routes/dwg_truth_autocad.md` | block_table·layout·xdata 최고 fidelity DWG 추출 EXECUTE 패킷 |
| `schemas/ontology_building_elements.yaml` | Wall/Door/Window/Opening/Space 온톨로지·관계 제약 |
| `schemas/building_evidence_graph.schema.yaml` | BEG-IR 전체 스키마 계약 |
| `source/SOURCE_ANSWER_UNABRIDGED.md` | 원천 설계 답변 무단축 보존 (28KB) |

| `docs/03_ROUTE_MATRIX_AND_ROUTING.md` | 11-route 매트릭스; DWG primary = `dwg_truth_autocad`, block_table 출력 |
| `docs/05_AI_READY_DATA_INFRASTRUCTURE.md` | block_library_signature, entity type·block pattern feature store |
| `docs/07_FAILURE_DIAGNOSIS_PLAYBOOK.md` | 성능 저하 시 model 우선 변경 금지; data→label→schema 순 진단 |
| `methodology/01_GOLD_CANARY_SET_DESIGN.md` | 회귀용 gold canary; block-heavy 도면 fold 포함 권장 |
| `configs/router_routes.yaml` | route별 required_outputs에 block_table·layout_table |
| `schemas/metrics.schema.yaml` | precision/recall/F1·geometry error 메트릭 계약 |

*(추가: `checklists/` 3, `packets/routes/` 11, `packets/yaml/` 22, `runbooks/` 3, `templates/` 7)*

### 1.2 합성

**실험 설계**: `methodology/00_EXPERIMENT_METHOD.md`의 E0(환경) → E2(route 추출) → E3(IR 정규화) → E4~E6(후보·그래프·검증) → E7(cross-route agreement) → E10(export) 사다리가 표준 골격. `configs/experiment_matrix.yaml`이 패킷 단위 실험 ID를 고정. ablation은 route(A0~A5)·feature(F0~F5)·threshold sweep으로 실패 원인을 data/label/schema/model/postprocess로 분리 (`methodology/03_ABLATION_STUDY_PLAN.md`, `docs/07_FAILURE_DIAGNOSIS_PLAYBOOK.md`).

**알고리즘·온톨로지**: BEG-IR은 정답 객체가 아닌 evidence·hypothesis·validation 보존 (`docs/02_BUILDING_EVIDENCE_GRAPH_IR.md`). Raw layer에 `BlockDefinition`/`BlockInstance` 분리; normalized layer에서 `block_hint`·transform_chain 유지. 건물 온톨로지는 Wall–Opening–Door–Window–Space 관계(voids/fills/hosted_by) (`schemas/ontology_building_elements.yaml`).

**인프라**: G0~G8 quality gate (`configs/quality_gates.yaml`); `dwg_truth_autocad`가 block_table·entity count parity 요구 (`packets/routes/dwg_truth_autocad.md`). metrics 스키마·review loop·confidence calibration으로 평가 하네스 완성.

**block-interior 직결**: modelspace entity count는 G2 IR 게이트로 커버되나, **block 내부 primitive fidelity**는 별도 지표 없음 — 다만 `BlockDefinition`/`BlockInstance` 이중 표현, `block_hint` evidence, semantic validation의 block_name 증거, route agreement의 layer/block/layout compare (`docs/04_VALIDATION_DESIGN.md`)가 67.6%→100% 측정·개선 프레임을 제공. dynamic block은 명시 언급 없음; ObjectDBX truth route가 유일한 고신뢰 경로.

---

## 2. cad_gnn_production_experiment_pack (gnn_pack) — 55 text files

### 2.1 목차 인벤토리 (요약)

| 경로 | 한줄 |
|------|------|
| `README.md` | 8-stage + A~F 파이프라인; DWG→semantic graph→repair |
| `docs/04_stage_1_to_8_detailed_design.md` | Stage1 `raw_blocks.jsonl`·block transform audit·roundtrip smoke |
| `docs/06_knn_candidate_edges.md` | `same_block_context` edge → **block reconstruction fidelity** |
| `docs/07_validation_strategy.md` | block transform audit, entity_count parity |
| `schemas/cad_ir.schema.yaml` | `Entity.BLOCK_REFERENCE`, `context.block_path[]`, `context.transform` |
| `packets/03_stage1_truth_extraction.md` | raw_blocks·handles·transform 보존 EXECUTE |
| `packets/04_stage2_cad_ir_normalization.md` | block transform lineage 유지/확장, quarantine |
| `packets/17_f_repair_planner.md` | violation 기반 repair proposal (원본 불변) |
| `methodology/repair_methodology.md` | `normalize_block_transform` repair action |
| `validation/acceptance_gates.yaml` | extraction `critical_extraction_loss: 0`, KNN recall 게이트 |
| `experiments/knn_experiments.yaml` | `block_to_wall` k sweep, symbol/block embedding 실험 |

| `docs/03_a_to_f_design.md` | 벽 후보: block primitives·wall-layer groups·raster 병행 |
| `docs/05_ml_dl_rl_application_map.md` | odd block transform detection, block/symbol embedding |
| `methodology/ontology_methodology.md` | BlockRef/BlockDefinition, `sameBlock` relation, validation severity |
| `methodology/labeling_methodology.md` | `LF_door_block_name` — block name heuristic weak label |
| `packets/06_stage4_typed_knn_graph.md` | block_insertion index + typed edge 생성 EXECUTE |
| `router/sdk_router_routes.yaml` | block/layer/xdata fidelity, layout/modelspace audit 요구 |

*(추가: `packets/` 12~16 A~E 파이프라인, `experiments/ml_gnn_experiments.yaml`, `validation/benchmark_plan.md`)*

### 2.2 합성

**실험 설계**: PLAN→EXTRACT→NORMALIZE→INDEX→CANDIDATE→VALIDATE→LABEL→TRAIN→INFER→REPAIR→BENCHMARK→HANDOFF (`methodology/experiment_lifecycle.md`). Stage 1~8 + A~F(벽/문창/실/중심선/semantic/repair) 수직 슬라이스. K0~K6 KNN ablation (`docs/06_knn_candidate_edges.md`).

**알고리즘·모델링**: typed KNN으로 `block_insertion_index`·`same_block_context` edge 생성; block feature(nested_depth, primitive count) (`docs/04_stage_1_to_8_detailed_design.md`). door/window는 block/arc/opening evidence (`packets/13_b_door_window_pipeline.md`). repair ladder R0 rules → R1 CP-SAT/Z3 (`methodology/repair_methodology.md`).

**인프라**: `acceptance_gates.yaml`이 stage별 수치 게이트; `validation_matrix.yaml`·benchmark harness (`packets/18_benchmark_harness.md`). CAD_IR `block_path` 배열이 nested block lineage의 핵심 스키마.

**block-interior 직결**: Stage1 `raw_blocks.jsonl` + block transform audit + roundtrip visual smoke가 **내부 fidelity 검증 3종 세트**. `same_block_context` edge와 `block reconstruction fidelity` 메트릭이 67.6%를 직접 타깃. `normalize_block_transform` repair와 block/symbol embedding (`experiments/knn_experiments.yaml`)이 dynamic/깨진 심볼 복구 경로. entity kind coverage는 `cad_ir.schema.yaml` enum + `Entity.UNKNOWN` quarantine.

---

## 3. ALM_V4_PRODUCTION_DESIGN_PACKAGE (alm_v4) — 61 text files (+ source zip 스킵)

### 3.1 목차 인벤토리 (요약)

| 경로 | 한줄 |
|------|------|
| `README.md` | ALM v4 neuro-symbolic agentic ontology 패키지 v0.1.0 |
| `methodology/02_FIVE_STAGE_EXPERIMENT_PROGRAM.md` | Stage A~E: Candidate Universe→Ranker→Structured Selection→Unknown→Golden |
| `methodology/03_NEURO_SYMBOLIC_ONTOLOGY_METHOD.md` | Resource→Object→Claim→Evidence→Policy→Action→Decision 8타입 |
| `methodology/08_METRICS_GATES_AND_TRIAGE.md` | G0~G9 게이트, T0~T10 triage, no silent failure |
| `methodology/details/02_GRAPH_RELATION_RECOVERY.md` | `BlockInstance instance_of BlockDefinition` gate 0.999 precision |
| `methodology/07_TOOLCHAIN_AND_SDK_ROUTER_METHOD.md` | block/instance fidelity, trusted roundtrip = dwg_truth_autocad |
| `schemas/V4_META_ONTOLOGY.yaml` | BlockInstance·DimensionCandidate 등 domain object_types |
| `source/06_FINAL_EXPERIMENT_VERDICT.md` | H2 IR fidelity PASS, H4 relation DEFERRED/FAIL — 관계 복원이 병목 |
| `source/00_RESULTS.md` | 파생변환 ~53% InputDerivable; 정보 위치 한계 정직 보고 |
| `packets/P03_CANDIDATE_UNIVERSE_PACKET.md` | oracle_recall@candidate_space ≥0.95 게이트 |

| `methodology/04_ML_DL_RL_RESEARCH_DIRECTION.md` | block instance_of definition, block-instance link prediction |
| `methodology/05_DATA_ARCHITECTURE_AND_SPINE.md` | append-only spine; block 이벤트 lineage |
| `packets/P02_ROUTE_SMOKE_PACKET.md` | truth route + secondary cross-check smoke |
| `packets/P05_GRAPH_RANKER_PACKET.md` | GNN edge classifier for ambiguous relations |
| `proposal/ALM_V4_RESEARCH_PROPOSAL.md` | candidate-space→ranking→selection→unknown 프레임 |
| `source/07_derivation_registry.yaml` | fold별 sha256·probe JSON 동결 레지스트리 |

*(추가: `methodology/details/` 01~06, `packets/P04`~`P11`, `checklists/` 4, `diagrams/ALM_V4_PIPELINE.mmd`)*

### 3.2 합성

**실험 설계**: 5-stage program — **후보 우주(recall) 먼저, 랭킹 다음, 구조적 선택, unknown 처리, golden 검증** (`methodology/02_FIVE_STAGE_EXPERIMENT_PROGRAM.md`). 단계 건너뛰기 금지. P00~P11 패킷 시스템 (`methodology/10_PACKET_SYSTEM_GUIDE.md`).

**알고리즘·온톨로지**: 온톨로지는 실행 경계; fake generation 금지, unknown 필수 (`methodology/03_NEURO_SYMBOLIC_ONTOLOGY_METHOD.md`). 관계 복원은 별도 연구 슬라이스 — `instance_of` 0.999, measures/describes P/R 게이트 (`methodology/details/02_GRAPH_RELATION_RECOVERY.md`). 실측 H4 relation 실패가 block-instance 링크 약점을 시사 (`source/06_FINAL_EXPERIMENT_VERDICT.md`).

**인프라**: G2 generic IR + roundtrip, G3 candidate universe, spine event schema, triage T1 extraction → T4 candidate (`methodology/08_METRICS_GATES_AND_TRIAGE.md`). metric은 name/value/numerator/denominator/scope 필수.

**block-interior 직결**: `BlockInstance`를 first-class Object로; `instance_of BlockDefinition` 관계를 G4급 게이트로 분리 측정. modelspace 375/375는 extraction(T1) 통과, 67.6% interior는 **T4 Candidate/Transform** 또는 relation recovery 실패로 라우팅. dynamic block은 미명시; trusted roundtrip은 autocad route 전용 (`methodology/07_TOOLCHAIN_AND_SDK_ROUTER_METHOD.md`).

---

## 4. 교차 합성 — block-interior 100% 로드맵

세 패키지 공통 교훈:

1. **측정 분리**: modelspace entity count ≠ block interior fidelity. gnn_pack의 `block reconstruction fidelity` + alm_v4의 `instance_of` 0.999 + infra의 layer/block/layout compare를 **합성 지표**로 쓸 것.
2. **표현 이중화**: INSERT만 세지 말고 `BlockDefinition` 내부 primitive + `BlockInstance` transform + `block_path[]` lineage (BEG-IR + CAD_IR).
3. **실험 사다리**: E0/E1 추출 parity → Stage2 normalize/quarantine → KNN `same_block_context` → relation `instance_of` → repair `normalize_block_transform` → ablation `F1_no_layer_block`.
4. **게이트**: extraction loss 0 (`acceptance_gates.yaml`) → block transform audit → oracle recall@block_interior ≥0.95 (alm_v4 G-CANDIDATE-UNIVERSE 변형).
5. **실패 triage**: interior miss → T1(extraction) vs T4(transform/nested) vs T2(relation) 분기 (`methodology/08_METRICS_GATES_AND_TRIAGE.md`).

### 4.1 entity-kind coverage 확장

`cad_ir.schema.yaml`의 kind enum(LINE~DIMENSION) + `Entity.UNKNOWN` quarantine가 최소 커버리지. BEG-IR raw layer는 Hatch·Leader·Spline 등 추가 (`docs/02_BUILDING_EVIDENCE_GRAPH_IR.md`). block interior는 INSERT 자체보다 **definition 내부 primitive kind 분포**가 핵심 — definition별 primitive_count·kind_histogram을 extraction_report에 추가하면 67.6% 분모를 명확화.

### 4.2 dynamic block 공백

세 패키지 모두 "dynamic block parameter"를 명시하지 않음. 대체 전략: (a) `dwg_truth_autocad` ObjectDBX 전체 속성 추출, (b) xdata/attribs 보존 (`packets/03_stage1_truth_extraction.md`), (c) roundtrip 후 parameter drift를 `block transform audit`로 포착. dynamic block은 **T4 Candidate/Transform** 실패로 분류 후 전용 ablation 추가 권장.

### 4.3 권장 실험 ladder (block-interior 전용)

```text
L0  modelspace 375/375 parity (현재 달성)
L1  block_table row count + definition name hash parity
L2  per-definition primitive kind/count fidelity
L3  nested block_path depth + cumulative transform reproducibility
L4  instance_of + same_block_context relation F1
L5  roundtrip visual + block_interior_fidelity composite ≥1.0
```

---

## 5. Top-10 재사용 아이디어 (100% 목표 순위)

| # | 아이디어 | 근거 파일 | 100% 기여 |
|---|----------|-----------|-----------|
| 1 | **block-interior 전용 fidelity 지표** — definition primitive count/hash vs roundtrip | `gnn_pack/.../docs/06_knn_candidate_edges.md` (`block reconstruction fidelity`) | 67.6%를 직접 추적·회귀 방지 |
| 2 | **`raw_blocks.jsonl` + block transform audit + roundtrip smoke 3종 세트** | `gnn_pack/.../docs/04_stage_1_to_8_detailed_design.md`, `docs/07_validation_strategy.md` | 추출·재기록 단계 누락 차단 |
| 3 | **CAD_IR `block_path[]` + transform lineage** (nested depth 보존) | `gnn_pack/.../schemas/cad_ir.schema.yaml`, `packets/04_stage2_cad_ir_normalization.md` | 중첩 block 내부 entity kind 매핑 |
| 4 | **`BlockInstance instance_of BlockDefinition` 관계 게이트 (precision≥0.999)** | `alm_v4/.../methodology/details/02_GRAPH_RELATION_RECOVERY.md` | INSERT↔정의 연결 오류 제거 |
| 5 | **`same_block_context` typed KNN edge** | `gnn_pack/.../docs/06_knn_candidate_edges.md` | 깨진/분해 심볼 high-recall 후보 |
| 6 | **repair `normalize_block_transform`** (proposal-first) | `gnn_pack/.../methodology/repair_methodology.md` | transform 불일치 자동 수정안 |
| 7 | **BEG-IR BlockDefinition/BlockInstance 이중 raw layer** | `infra_0617/.../docs/02_BUILDING_EVIDENCE_GRAPH_IR.md` | interior를 modelspace와 분리 저장 |
| 8 | **cross-route block_table/layout compare** | `infra_0617/.../docs/04_VALIDATION_DESIGN.md`, `packets/routes/dwg_truth_autocad.md` | sidecar disagreement로 interior gap 진단 |
| 9 | **ablation `F1_no_layer_block`** — block feature 기여도 정량 | `infra_0617/.../methodology/03_ABLATION_STUDY_PLAN.md` | block_name 제거 시 fidelity 하락폭 측정 |
| 10 | **5-stage oracle recall gate를 block interior에 적용** (≥0.95) | `alm_v4/.../methodology/02_FIVE_STAGE_EXPERIMENT_PROGRAM.md` | ML 전에 후보 우주에 정답 primitive 존재 보장 |

---

*생성: 2026-07-09 | 추출 경로: `runs/alm_extract/d2/` | 단일 산출물, 다른 tracked 파일 미변경*
