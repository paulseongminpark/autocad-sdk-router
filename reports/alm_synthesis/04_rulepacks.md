# 규칙팩/온톨로지 통합 분석 보고서 (04)

목표는 DWG roundtrip fidelity 100%에 맞춰 4개 pack의 규칙을 `rules-as-data` 관점으로 정규화하고,  
modelspace 375/375 완료 이후 block interiors + semantic layer까지 안전하게 확장하는 것이다.

---

## 공통 전처리/검증 원칙

1. `rule_id` + `source_entity_ids` + `source_rule_ids` + `review_status`를 데이터 객체 단위 불변식으로 둔다.  
2. 값과 표시를 분리한다. 특히 안목치수는 계산값과 치수선 위치를 혼동하지 않는다.  
3. geometry-only 정보는 candidate/보조 도면 생성까지만 허용하고, 법적/구조 확정은 authority or review로 봉쇄한다.  
4. 게이트는 좌표 diff에서 geometry 정확도만 보지 않는다. 생성 방식, 규범 강도, 리뷰 상태까지 함께 검사한다.

---

## 1) centerline_rulepack_v1_1

### 1-1. 대상 파일
- [rulepack/manifest.yaml](runs/alm_extract/d4/centerline_rulepack_v1_1/centerline_rulepack_v1_1/rulepack/manifest.yaml)
- [rulepack/ontology.yaml](runs/alm_extract/d4/centerline_rulepack_v1_1/centerline_rulepack_v1_1/rulepack/ontology.yaml)
- [rulepack/ruleset_index.yaml](runs/alm_extract/d4/centerline_rulepack_v1_1/centerline_rulepack_v1_1/rulepack/ruleset_index.yaml)
- [docs/CENTERLINE_DRAWING_RULES_v1_1.md](runs/alm_extract/d4/centerline_rulepack_v1_1/centerline_rulepack_v1_1/docs/CENTERLINE_DRAWING_RULES_v1_1.md)
- [docs/rulebook_v1_1_summary.md](runs/alm_extract/d4/centerline_rulepack_v1_1/centerline_rulepack_v1_1/docs/rulebook_v1_1_summary.md)
- [rules 폴더](runs/alm_extract/d4/centerline_rulepack_v1_1/centerline_rulepack_v1_1/rulepack/rules)
- [policies](runs/alm_extract/d4/centerline_rulepack_v1_1/centerline_rulepack_v1_1/rulepack/policies)

### 1-2. RULE ONTOLOGY 요약
- 스키마 중심: `objects + semantic_levels`
- 주요 객체: `RawEntity`, `NormalizedGeometry`, `EvidenceGraph`, `WallCandidate`, `WallRoleScores`, `Wall`, `Centerline`, `Room`
- `S0`~`S5` semantic 레벨에서 wall 후보 생성부터 role 확정까지 상태가 명시됨.
- `WallCandidate`는 geometry 기반으로 생성되나 `S5`는 authority 필요.
- 경로 근거: [ontology.yaml](runs/alm_extract/d4/centerline_rulepack_v1_1/centerline_rulepack_v1_1/rulepack/ontology.yaml)

### 1-3. 규칙 카테고리와 바인딩
- 총 51개 규칙.
- 카테고리: `semantic_extraction(6), wall_candidate(8), wall_role(5), legal(5), module(4), geometry(10), dimension(2), modular(4), validation(4), output(3)`
- `ruleset_index.yaml`에서 카테고리별 rule id 목록을 제공.
- 핵심 규칙:
  - `WCD-001` : 평행선 pair 기반 벽체후보 생성.
    - 경로: [WCD-001_parallel_line_pair_wall_candidate.yaml](runs/alm_extract/d4/centerline_rulepack_v1_1/centerline_rulepack_v1_1/rulepack/rules/wall_candidate/WCD-001_parallel_line_pair_wall_candidate.yaml)
  - `C-001` : WallCandidate로부터 centerline candidate 생성, confidence 단계별 layer routing.
    - 경로: [C-001_wall_double_line_center.yaml](runs/alm_extract/d4/centerline_rulepack_v1_1/centerline_rulepack_v1_1/rulepack/rules/geometry/C-001_wall_double_line_center.yaml)
  - `D-001` : 안목치수 계산식
    - 경로: [D-001_clear_dimension_calculation.yaml](runs/alm_extract/d4/centerline_rulepack_v1_1/centerline_rulepack_v1_1/rulepack/rules/dimension/D-001_clear_dimension_calculation.yaml)
  - `V-001` : 50mm 규격 검증(MUST)
    - 경로: [V-001_50mm_check.yaml](runs/alm_extract/d4/centerline_rulepack_v1_1/centerline_rulepack_v1_1/rulepack/rules/validation/V-001_50mm_check.yaml)
  - `O-002` : CAD layer 표준으로 출력 라우팅
    - 경로: [O-002_cad_layers.yaml](runs/alm_extract/d4/centerline_rulepack_v1_1/centerline_rulepack_v1_1/rulepack/rules/output/O-002_cad_layers.yaml)

### 1-4. 규칙 거버넌스 패턴
- `manifest`에서 rulebook id/version/status/purpose, prohibited_claims, provenance 필수항목을 설정.
- `no_structural_info_policy`에서 geometry-only일 때 structural 확정을 금지하고, authority 기반만 최종확정 허용.
  - 경로: [no_structural_info_policy.yaml](runs/alm_extract/d4/centerline_rulepack_v1_1/centerline_rulepack_v1_1/rulepack/policies/no_structural_info_policy.yaml)
- `source` 태깅과 `review layer` 정책이 같이 존재하여 감사 자동화 쉬움.
- 규칙 메타, 규범 근거가 `rule_id`, `source`, `normative_strength`로 표현됨.

### 1-5. centerline pack를 통한 roundtrip 게이트 후보
1. S3/S4/S5 전이 준수 여부 (구조 역할 확정 유효성)
2. `V-001` 통과율이 낮을 때 geometry diff 통과라도 의미 정합 실패 판정
3. `C-001` confidence 기반 layer 강제(`A-WALL-CENTER-CONFIRMED`/`INFERRED`/`REVIEW`/`WARN`)
4. `CD-018` 대응형 메타필드와 유사한 중심선 객체 필드 저장 여부
5. Block interior 귀속 시 Room 후보와 WallCandidate 증빙 동시 존재

---

## 2) clear_dimension_rulepack_v1

### 2-1. 대상 파일
- [rulepack/manifest.yaml](runs/alm_extract/d4/clear_dimension_rulepack_v1/clear_dimension_rulepack_v1/rulepack/manifest.yaml)
- [rulepack/ontology.yaml](runs/alm_extract/d4/clear_dimension_rulepack_v1/clear_dimension_rulepack_v1/rulepack/ontology.yaml)
- [rulepack/ruleset_index.yaml](runs/alm_extract/d4/clear_dimension_rulepack_v1/clear_dimension_rulepack_v1/rulepack/ruleset_index.yaml)
- [docs/CLEAR_DIMENSION_DRAWING_RULES_v1.md](runs/alm_extract/d4/clear_dimension_rulepack_v1/clear_dimension_rulepack_v1/docs/CLEAR_DIMENSION_DRAWING_RULES_v1.md)
- [docs/rulebook_v1_summary.md](runs/alm_extract/d4/clear_dimension_rulepack_v1/clear_dimension_rulepack_v1/docs/rulebook_v1_summary.md)
- [rules/calculation/drawing/validation](runs/alm_extract/d4/clear_dimension_rulepack_v1/clear_dimension_rulepack_v1/rulepack/rules)
- [policies](runs/alm_extract/d4/clear_dimension_rulepack_v1/clear_dimension_rulepack_v1/rulepack/policies)

### 2-2. RULE ONTOLOGY 요약
- 핵심 객체: `ClearDimension`, `ReferenceFace`, `DimensionObject`, `RoomCandidate`, `AreaBoundary`.
- 값 객체와 표시 객체 분리:
  - 값: `dimension_value`, `dimension_basis`
  - 표시: `definition_points`, `dimension_line_location`, `extension_origins`
- `basis_enums`가 계산 근거를 강하게 제한.
- 경로: [ontology.yaml](runs/alm_extract/d4/clear_dimension_rulepack_v1/clear_dimension_rulepack_v1/rulepack/ontology.yaml)

### 2-3. 규칙 바인딩
- 총 18개 규칙.
- 예시:
  - `CD-004` 중심선거리 기반 안목치수 생성(자동 생성식)
    - [CD-004_centerline_to_clear_dimension.yaml](runs/alm_extract/d4/clear_dimension_rulepack_v1/clear_dimension_rulepack_v1/rulepack/rules/calculation/CD-004_centerline_to_clear_dimension.yaml)
  - `CD-010` 10mm 그래픽 오프셋은 법규값으로 처리하지 않음
    - [CD-010_ten_mm_offset_hypothesis.yaml](runs/alm_extract/d4/clear_dimension_rulepack_v1/clear_dimension_rulepack_v1/rulepack/rules/drawing/CD-010_ten_mm_offset_hypothesis.yaml)
  - `CD-018` metadata 필수, CAD XData 보존
    - [CD-018_metadata_required.yaml](runs/alm_extract/d4/clear_dimension_rulepack_v1/clear_dimension_rulepack_v1/rulepack/rules/validation/CD-018_metadata_required.yaml)

### 2-4. rule-as-data 거버넌스
- manifest는 active_draft이나 규칙 강도(MUST/SHOULD/PRACTICE/REVIEW)를 명시.
- `prohibited_claims`로 잘못된 확정 로직 억제.
- review 정책에서 결측·충돌·면적경계 갈등 시 레이어를 강제.
  - [review_policy.yaml](runs/alm_extract/d4/clear_dimension_rulepack_v1/clear_dimension_rulepack_v1/rulepack/policies/review_policy.yaml)
- 기준/표시 분리를 강제하는 정책이 있어 block interior의 annotation semantics 복원에 핵심적.

### 2-5. roundtrip 검증 게이트
1. `CD-018` 메타데이터 완결성
2. `CD-010` 10mm 오해 방지
3. `CD-007/CD-013` 계열 두께 누락 시 confirmed 금지
4. `CD-012/CD-014`의 간격/영역 경계 정합성
5. `definition_points`와 `dimension_line_location` 일치성

---

## 3) CLEAR_DIMENSION_DRAWING_RULES_v1.zip

### 3-1. 대상 파일
- [CLEAR_DIMENSION_DRAWING_RULES_v1.md](runs/alm_extract/d4/CLEAR_DIMENSION_DRAWING_RULES_v1/CLEAR_DIMENSION_DRAWING_RULES_v1.md)

### 3-2. 요약
- 이 패키지는 규칙 문서 중심으로 value/graphic 분리 개념을 독립적으로 유지.
- `A-DIM-CLEAR`, `A-DIM-CLEAR-REVIEW`, `A-DIM-CLEAR-PROVISIONAL`, `A-WARN-CLEAR` 레이어 체계를 제시.
- clear_dimension_rulepack의 실행 규칙으로 연결되는 사전 정의 문서로 활용 가치가 크다.

---

## 4) sjh_select_packet_v1

### 4-1. 대상 파일
- [packet.manifest.yaml](runs/alm_extract/d4/sjh_select_packet_v1/sjh_select_packet_v1/packet.manifest.yaml)
- [config/layer_profile.yaml](runs/alm_extract/d4/sjh_select_packet_v1/sjh_select_packet_v1/config/layer_profile.yaml)
- [config/feature_config.yaml](runs/alm_extract/d4/sjh_select_packet_v1/sjh_select_packet_v1/config/feature_config.yaml)
- [config/experiment_config.yaml](runs/alm_extract/d4/sjh_select_packet_v1/sjh_select_packet_v1/config/experiment_config.yaml)
- [docs/00_METHOD.md](runs/alm_extract/d4/sjh_select_packet_v1/sjh_select_packet_v1/docs/00_METHOD.md)
- [docs/01_DATA_CONTRACT.md](runs/alm_extract/d4/sjh_select_packet_v1/sjh_select_packet_v1/docs/01_DATA_CONTRACT.md)
- [docs/02_DECISION_GATES.md](runs/alm_extract/d4/sjh_select_packet_v1/sjh_select_packet_v1/docs/02_DECISION_GATES.md)
- [docs/example_outputs_SYNTHETIC/verdict_select.json](runs/alm_extract/d4/sjh_select_packet_v1/sjh_select_packet_v1/docs/example_outputs_SYNTHETIC/verdict_select.json)

### 4-2. RULE ONTOLOGY/실행 계층
- 명시적 ontology 파일은 없고 `stage + gates + features`가 규칙 온톨로지 역할.
- 스테이지: layer_profile → wall_extract → label_extract → features → selector → eval → dim.
- `layer_profile.yaml`에서 pairing 파트너와 금지 파트너를 구분하여 후보 폭발을 제어.
- `feature_config.yaml`에서 CLF/GEN 태깅으로 생성 시점 출력 참조 규율 적용.

### 4-3. governance 패턴
- manifest에 lifecycle owner, human gate, seed, determinism, fold/입력 설계가 구조화.
- G0~G8 게이트를 통해 재현성, 누출, null/collapse까지 정량 관리.
- `verdict_select.json`에 ablation별 성능, null correction, perm collapse, role decomposition 결과가 남아 반복시험의 합의증거로 사용 가능.

### 4-4. roundtrip 기여
- topology 신호와 layer profile 결합으로 block edges/구조 선택을 안정적으로 추적.
- centerline/clear에서 약한 규칙을 보완하고, 실험형 지표를 production gate로 승격할 수 있는 기반 제공.

---

## 패킷 간 합성 분석 (공통 규약)

### 공통 공학 패턴
- 모든 pack이 `stage`를 둬 규칙 실행 순서를 관리한다.
- centerline/clear는 객체 schema가 강하고, sjh는 게이트/실험 통제 프레임이 강하다.
- 따라서 `rule-as-data` 합성 시 다음 3축이 효율적이다:
  1) ontology binding(무슨 개체인지)
  2) policy binding(무슨 근거로 확정 가능한지)
  3) gate binding(무슨 조건에서 통과/재검토/차단되는지)

### 결합 합성 전략
- `WallCandidate`/`Centerline`은 centerline pack 기준
- `ClearDimension`/`DimensionObject`는 clear pack 기준
- `layer_profile`, `topology`, `determinism`은 sjh 기준
- 최종 ledger는 3 pack의 `rule_id`를 교차 저장(`source_rule_ids`)하여 증거 그래프를 완성

---

## 주석/치수 의미론(semantic) 복원 기법

1. **기준점/표시선 분리**
   - `dimension_basis`로 안목치수 값 저장, `dimension_line_location`은 CAD 표기 위치로 분리.
   - 관련 근거: [CD-018](runs/alm_extract/d4/clear_dimension_rulepack_v1/clear_dimension_rulepack_v1/rulepack/rules/validation/CD-018_metadata_required.yaml), [CD-004](runs/alm_extract/d4/clear_dimension_rulepack_v1/clear_dimension_rulepack_v1/rulepack/rules/calculation/CD-004_centerline_to_clear_dimension.yaml), [CLEAR_DIMENSION_DRAWING_RULES_v1.md](runs/alm_extract/d4/CLEAR_DIMENSION_DRAWING_RULES_v1/CLEAR_DIMENSION_DRAWING_RULES_v1.md)
2. **confidence-driven 레이어 라우팅**
   - centerline pack의 `C-001`과 no-structure 정책을 결합해 review 상태를 layer로 강제 매핑.
3. **evidence graph 필수화**
   - `source_entities`, `source_rules`, `review_status`, `normative_strength`, `confidence`를 매 객체 필수속성화.
4. **block interior 전용 레이어 가드**
   - wall 후보, room 후보, topology가 동시에 성립할 때만 내부 치수/벽체 중심선의 확정 상태로 이동.
5. **규범 우선순위 병합**
   - MUST > SHOULD > PRACTICE > REVIEW 순으로 충돌 해결.

---

## top-10 재사용 아이디어 (roundtrip 100% 매핑)

1. **메타데이터 불변식 게이트를 최우선 통과 조건화**  
   `CD-018` 타입의 항목을 centerline 객체에도 동일 적용.

2. **50mm 규격 + 간격 규정 동시 검증**  
   `V-001` + `CD-012` 결합.

3. **confidence 기반 레이어 강제 규칙화**  
   `C-001`의 confidence 분기를 모든 도형 재생성에 표준화.

4. **geometry-only 구조확정 금지**  
   `no_structural_info_policy`의 S4/S5 진입 조건을 block interior에도 상향 적용.

5. **pairing 파트너 엄격화**  
   `layer_profile.yaml`의 allowed/forbidden role 기준을 centerline 후보 단계로 이동.

6. **10mm 오해 필터 게이트**  
   `CD-010`을 기본 그래픽 정책으로 강제해 실제 치수값과 혼동 제거.

7. **데이터 계약 불일치 탐지 게이트**  
   입력 레이어 유무, 유효 geometry, alignment map 필수성 확인을 게이트로 고정.
   - 경로: [01_DATA_CONTRACT.md](runs/alm_extract/d4/sjh_select_packet_v1/sjh_select_packet_v1/docs/01_DATA_CONTRACT.md)

8. **재현성 게이트 통합**  
   seed 고정, byte-identical, determinism test를 매 파이프라인 시작 gate로 고정.

9. **누출·통계 허위방지 게이트**  
   `G6 output_leak` + `G7 perm`을 production gate로 상향.

10. **주석 semantics 다층 layer 정책**  
   A-DIM-CLEAR, A-DIM-CLEAR-REVIEW, A-DIM-CLEAR-PROVISIONAL, A-WARN-CLEAR 레이어를 block interior 재생성에서도 일관화.

---

## 결론

- 중심선/안목치수/선택 학습 패턴은 단독으로는 100% 의미 보존이 어렵다.
- 세 패킷을 합성하면 `규칙-근거-게이트`가 연결되고, block interiors에서만 잘 드러나는 누락(치수기준점, 구조 역할 오인, 레이어 과합성)을 통합적으로 탐지할 수 있다.
- 다음 액션: `manifest/ruleset index` 기준으로 규칙 목록을 실행 DAG로 정식 직렬화하고, 위 top-10 게이트를 라운드트립 품질 체크리스트의 상위 1차 항목으로 등록한다.
