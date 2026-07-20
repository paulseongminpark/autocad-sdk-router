# TAXONOMY — E2 failure ledger root_class 사전

harvest 중 관측된 root_class 자유 태그, 각 정의 1줄과 관측 빈도(LEDGER.jsonl 기준).

| root_class | 정의 | 빈도 |
|---|---|---:|
| `UNKNOWN` | harvest 시점에 root_class를 확정할 근거가 부족 (요약 수준 인용만 확보, 원본 상세 미발견) | 2 |
| `insufficient_population` | 측정에 필요한 최소 표본/자산 수가 확보되지 않아 판정 불가 | 2 |
| `kill_band` | 사전 봉인한 킬 밴드(임계) 조건이 충족되어 해당 트랙(RL/SSL 등)을 훈련/채택 전에 종료 | 2 |
| `missing_frozen_artifact` | 측정에 필요한 사전 동결 산출물(모델/매니페스트)이 실제로 존재하지 않음 | 2 |
| `silent_drift_risk` | 명시적 파킹/처분이 없어 조용히 범위가 넓어지거나 흐려질 위험 | 2 |
| `witness_tautology` | 증인/근거 제시 방식이 검사 대상 표면을 그대로 복사한 것이라 독립적 증거력이 없음 | 2 |
| `approval_bypass_wording` | 미결재 상태를 완료된 것처럼 표현해 승인 절차를 우회할 위험이 있는 문언 | 1 |
| `completeness_rule_gap` | 선언된 필드의 값/다중도/자료형 중 일부 축을 심판 규칙이 다루지 않아 반례가 통과함 | 1 |
| `cross_device_equivalence_fail` | 서로 다른 장치(로컬/DGX) 간 수치 동등성이 허용 오차를 초과 | 1 |
| `data_leakage` | 평가에 쓰이는 모델이나 데이터가 학습 단계에서 이미 평가셋을 봤음(오염) | 1 |
| `detector_coverage_gap` | 탐지기가 커버해야 할 신호 공간의 일부를 구조적으로 보지 못함 | 1 |
| `dilution_attack` | 깨끗한 증거를 다량 추가해 평균 기반 지표를 희석시켜 의심 신호를 숨기는 공격 | 1 |
| `escalation_halt` | 반복 수리에도 신규 결함 클래스가 계속 발견되어, 성문화된 규칙에 따라 반복을 중단하고 상위 결재로 이관 | 1 |
| `false_readiness_claim` | 패킷/계획서가 선행조건 미충족인데 즉시 실행 가능하다고 잘못 기재 | 1 |
| `family_collision` | 학습/검증 분할 간 동일 grouping 단위(family)가 중복 배정되어 누출 위험 | 1 |
| `guard_bypass` | 판정 가드의 조건(predicate) 여집합이 열려 있어 우회 입력으로 오탐/오판정 유발 | 1 |
| `hash_transcription` | 해시값 등 식별자를 옮겨적는 과정에서 오류가 발생(기계검증이 포착) | 1 |
| `independent_support_forgery` | 독립적 증거로 인정되는 계수 방식이 실제로는 중복 계수를 허용해 위조 지지를 생성 | 1 |
| `insufficient_population_diversity` | 합성팩의 템플릿 가족이 하나뿐이라 train/eval 분리 등 실험 설계가 불가능 | 1 |
| `latent_defect_masked_by_population` | 결함이 실제로 고쳐진 게 아니라 모집단 변화가 우연히 결함 발현 조건을 제거해 숨김 | 1 |
| `metric_relabeling_backdoor` | 실패 지표를 재명명하여 승격/완화의 통로로 쓰일 위험 | 1 |
| `missing_autopsy_clause` | 실패 시 사후분석(부검) 절차·예산이 사전에 마련되지 않음 | 1 |
| `missing_dual_seal` | 사전 봉인 산출물(prereg+evidence) 이중화 절차가 실행되지 않음 | 1 |
| `missing_failclosed_clause` | 의무 조항은 있으나 미이행 시 처분(fail-closed)이 없어 강제력 없음 | 1 |
| `missing_kill_conditions` | 실패 시 처분(중단/강등) 규칙 자체가 계획에 없음 | 1 |
| `missing_prerequisite_cell` | 후보 실행에 필요한 선행 산출물/셀이 계획에서 누락 | 1 |
| `neutrality_violation` | 중립적이어야 할 입력 추가가 판정을 부당하게 악화/개선시킴 | 1 |
| `over_blocking` | 정상적인(정당한) 입력까지 과도하게 차단하는 판정 로직 결함 | 1 |
| `overclaim_wording` | 실제 결과보다 강한 문구로 서술된 주장(예: 완전 동일)이 반증됨 | 1 |
| `population_masking` | 한 게이트를 채우려다 모집단 구성이 바뀌어 다른 요구사항이 조용히 사라짐 | 1 |
| `post_hoc_band_relaxation` | 결과를 관측한 뒤 성공 밴드를 낮춰 실패를 우회하려는 시도(amendment_rule 위반) | 1 |
| `production_wiring_gap` | 실전 운용 코드(배치 러너 등)에 잠금/기록/재실행 방지 등 필수 배선이 누락 | 1 |
| `property_test_population_masking` | 속성 기반 시험이 전체 모집단을 표집하지 못하고 일부 고정 사례만 순환 | 1 |
| `repair_induced_regression` | 이전 결함을 고친 수리 코드가 새로운 역전이/결함을 도입 | 1 |
| `resource_miscalibration` | 작업 난이도 대비 배정된 모델/추론 등급이 과잉 또는 과소 | 1 |
| `reward_hacking_surface` | 분할/정의가 정확히 고정되지 않아 사후에 유리하게 재정의될 수 있는 경로 | 1 |
| `scale_invariance_violation` | 스케일 변환에 대해 불변이어야 할 지표가 실제로는 밴드를 벗어남 | 1 |
| `scope_conflation` | 서로 다른 두 절차 단계(예: 권리 해소 vs 코드 구축)를 하나로 뭉뚱그려 혼동 | 1 |
| `scope_mislabeling` | 측정 결과가 어떤 데이터 우주에서 나온 것인지 잘못 표기됨 | 1 |
| `sealed_band_violation` | 사전 봉인한 밴드/문법 그대로도 금지된 결과(상승 등)가 실측으로 재현됨 | 1 |
| `synthetic_fidelity_gap` | 합성 생성기가 실물 도면의 엔티티 다양성/분포를 재현하지 못함(fidelity gate FAIL) | 1 |
| `synthetic_real_distribution_mismatch` | 합성 데이터와 실물 데이터의 분포가 통계적으로 달라 밴드 실패 | 1 |
| `tautological_checker` | 선행성/무결성 등을 검사해야 할 검사기가 상수를 반환하거나 항상 참이 되어 실질 검증력이 없음 | 1 |
| `tautological_predicate` | 자기 자신을 증명하는 방식이 순환적이라 실질적으로 아무것도 검출하지 못하는 술어 | 1 |
| `tautological_test_pool` | 검증에 쓰이는 표본 집합 자체가 이미 만점/포화 상태라 판별력을 상실 | 1 |
| `undefined_scope` | 측정 범위(어디까지 실행하는지)가 예산/캡과 함께 한정되지 않음 | 1 |
| `undefined_threshold` | 판정 임계값이나 단위 환산이 정의되지 않아 해석 차이/우회가 가능 | 1 |
| `unsealed_scoring_rule` | 채점 규칙(스코어러/문턱)이 사전 봉인되지 않은 채로 판정이 시도됨 | 1 |
| `write_ownership_gap` | 두 병렬 작업 간 쓰기 소유권·게이트 순서가 불명확해 미봉인 자원을 변형할 위험 | 1 |

총 root_class 태그 수: 49종 / 총 행 수: 55행

UNKNOWN 태그(2행)는 근거가 요약 수준 문서(RSI_SYSTEM_DESIGN.md, RSI_METHODOLOGY_MAP.md)에만 있고 harvest 범위(reports\e2\) 내에서 원본 상세 리포트를 찾지 못한 경우로, 발명하지 않고 UNKNOWN으로 보존했다.
