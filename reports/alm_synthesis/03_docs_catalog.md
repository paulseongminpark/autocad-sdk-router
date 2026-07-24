# ALM Docs Catalog for DWG roundtrip 정밀 분석

## 범위
- 대상: `D:\dev\_ariadne\alm\docs`의 최상위 `*.md`
- 제외: `perplexity_nemotron3ultra_v1.md`
- 목적: DWG 추출-재생성-차등 비교(ROUNDTRIP) 미션 대비 375/375 modelspace fidelity, block-internal 결손(6,867), anonymous *U 동적블록 누락(약 320) 정리
- 목표: 누락 종류별 재현 원인과 재현률 상향 아이디어를 빠르게 찾기 위한 1차 카탈로그

## 문서 카탈로그
| 파일명 | 날짜 | 한 줄 요약 | 미션 relevance(0-3) |
|---|---|---|---|
| 1단계 - IR 생성기 (C# 하이브리드) 설계 노트.md | 2026-05-26 | C# 추출/재생성 + Python emit·검증의 경계 분리, 블록 인스턴스-정의 분리를 통한 라운드트립 정합 체계를 정의 | 3 |
| 1단계 - Probe(탐사) 설계 설명.md | 2026-05-26 | 도면 1회 정찰로 스키마를 결정하기 위한 속성 빈도/분포 수집 절차를 정의 | 3 |
| 2026-06-04-cad-derivation-transform-learning-design.md | N/A | 파생도면 변환 실험을 5단계 로드맵과 정렬하며 7-폴드 교차검증, 6축 평가, 변형 대비 실험 설계를 제시 | 3 |
| 2026-06-04-plan1-python-foundation.md | N/A | Python 기반 IR 스키마, 훈련/평가 split, diff 도구의 기본 토대와 P2 준비 태스크 정리 | 2 |
| 2026-06-04-plan2-p1-ir-probe.md | N/A | Probe 자동화 실행 래퍼(스크립트, DWG 배치, 산출 검증)까지 포함해 1단계 시작점 고정 | 2 |
| 2026-06-04-plan3-p1-extract-filter.md | N/A | 추출기 보강, IR 필터링, 라운드트립 경량 검증으로 P1 완결을 목표로 함 | 3 |
| 2026-06-04-plan4-p2-semantics.md | N/A | 의미복원 파이프라인으로 semantic_class 선언, ontology 규칙, 관계 복원, 3개 IR 재적용 절차를 다룸 | 2 |
| 2026-06-04-plan5-p3-alignment.md | N/A | input/output 객체 대응 스키마, registration, 매칭 전략을 통한 P3 정렬 알고리즘 설계 | 3 |
| 2026-06-04-plan6-p4-dataset-and-rules.md | N/A | 다종 데이터셋 구성과 P4 규칙 학습의 실험 단계 분할, 이후 단계 연결 고리를 제시 | 2 |
| 2단계 - 의미 복원 (입법·분류·관계·보정) 설계 노트.md | 2026-05-26 | semantic_class 입법, 분류·관계·보정·calibration까지 포함한 의미 계층 설계를 제공 | 2 |
| 2단계 심화 - 번역기·부트스트랩·golden 설계 노트.md | 2026-05-26 | 기하->텍스트 번역기, 부트스트랩 분류 루프, golden 제작/검수 전략으로 라벨 품질 안정화를 다룸 | 2 |
| 3단계 - 변경반응 (detect·impact·validate·regenerate) 심화 설계 노트.md | 2026-05-26 | identity 매칭 기반 변경탐지, 관계전파(Neo4j), validate/regenerate 절차를 포함한 규칙 성장형 폐루프를 기술 | 1 |
| 4단계 - 규칙 성장 공장(공장2) 하이브리드 심화 설계 노트.md | 2026-05-26 | 통제4장치, decision tree, 통계 게이트, 통합 심사, 교차도면 검증까지 상세한 규칙 성장 패턴 제시 | 2 |
| 5단계 - 확장 (profile·객체종류·라이브러리화) 심화 설계 노트.md | 2026-05-26 | profile/객체종류/라이브러리 확장 전략으로 코드 변경 최소화와 설정화 정책을 정의 | 1 |
| 도면 자동화 공장 - 팀 공유용 로드맵.md | 2026-05-26 | 5단계 전체 로드맵과 역할, 우선순위, 병목 정리를 한 눈에 정리한 팀 운영용 합의 문서 | 1 |
| ALM_Architectural_World_Model_Data_Ontology_Architecture_v0.2.md | N/A | ALM 기본 아키텍처와 canonical ID, ontology, named graph 모델의 v0.2 버전 개념을 정리 | 2 |
| ALM_Architectural_World_Model_Data_Ontology_Architecture_v0.3.md | N/A | v0.2→v0.3 전환, P0~P11 단계, 테스트 오라클 매트릭스까지 포함한 본체 아키텍처 문서 | 2 |
| ALM_v0.3_EXECUTION_PACKETS.md | N/A | ALM 실행 패킷군(Observation/Geometry/Candidate/Classifer/Relation/Oracle 등)과 테스트 매트릭스를 모듈 단위로 지정 | 1 |
| ALM_v0.3_SCOPE_MAP_RISK_REGISTER.md | N/A | scope 분리와 critical risk 등록부로 실패위험과 대응 우선순위를 정량적으로 관리 | 1 |
| ALM_v0.3_x_PRIMITIVE_TO_SEMANTIC_FACTORY.md | N/A | Observation canonicalization에서 relation 추론까지 primitive→semantic 변환 공장을 정의하고 측정 계약·메트릭을 제시 | 2 |
| ALM_v0.3_y_VALIDATION_ORACLES_METRICS_CALIBRATION.md | N/A | Golden, synthetic truth, cross-SDK agreement, calibration, 회귀/드리프트 대응을 포함한 검증 오라클 체계 | 3 |
| ALM_v0.3_z_PRODUCTION_DATA_ONTOLOGY_MVP.md | N/A | production storage, assertion schema, SDK router, MVP PoC 실행계획을 다루는 운영 전환 문서 | 1 |
| ALM_V5_SCRIBE_DATA_GAPS.md | 2026-06-16 | 현재 IR/파이프라인이 막히는 구간을 목록화하고, 누락 입력 보강 우선순위를 제시해 천장 상향 포인트를 제안 | 3 |
| ALM_V5_SCRIBE_DESIGN.md | 2026-06-16 | SCRIBE로의 전략 전환(descriptive→generative), adversarial 반례 기반 학습/보정 및 초기 실험의 한계를 정리 | 3 |
| ALM-EXPERIMENT-PLAN.md | N/A | 실험의 가설·절차·메트릭·안전 규칙을 표준화해 증거 중심 실행을 강제하는 시험 설계서 | 2 |
| ALM-REFRAME.md | N/A | ALM 사고를 재정렬해 파이프라인 충돌, 미결, 운영 원칙을 다시 압축 정리 | 1 |
| ALM-v1-HANDOFF.md | N/A | 세션 이력, 승인 상태, 미결 과제, 다음 액션을 압축한 handoff 문서 | 1 |
| ALM-v1-OPENINGS-RESULTS.md | N/A | opening/delivery 결과 및 오버메르지/seed-kill 같은 정밀 교정 사례를 통해 정밀도 향상 전략을 제시 | 2 |
| ALM-v1-PLAN-proposal.md | N/A | v1 제안서로 6-Tier 아키텍처 보강, 데이터 통합, 미결사항을 승인 전제로 정리 | 1 |
| ALM-v1-RESULTS.md | N/A | RUN 결과, 오버스펙/오버메르지 개선 및 게이트, 오라클 ladder를 통한 정직한 결과 정리 | 1 |
| ALM-v1-ROOMS-RESULTS.md | N/A | room/space 결과와 wall promotion 한계 해제 핵심 포인트를 공유한 성과 문서 | 2 |
| ALM-v4-PLAN-proposal.md | N/A | v4 통합 계획으로 아키텍처 원칙 충돌 조정 및 검증 스택의 실행 순서를 고정 | 1 |
| ALM.md | N/A | 건축 도면의 다중 위계 개념과 이를 처리하기 위한 ALM 최소 world model의 철학적 프레임 | 1 |
| ALM2.md | N/A | ALM2 확장판으로 그래프 모델, 추론 모드, 충돌·변경 아키텍처까지 확대한 실무 레퍼런스 | 1 |
| CAD_OS_LAYER_BUILD_PLAN.md | N/A | CAD_OS 계층의 빌드 단계와 의존성, P0~P2 우선 순서를 정의한 실행 계획 | 1 |
| CAD_OS_LAYER_DESIGN.md | N/A | DWG Graph IR, operation registry, job protocol, security/semantics를 포함한 CAD OS 계층 설계 | 2 |
| CAD_OS_LAYER_EXECUTION_PLAN.md | N/A | 단계별 triage→execution까지 실행형 태스크로 분해한 작업 진행표 | 1 |
| CADOS_M07B_ATTENDED_GUI_VERIFICATION_AND_NATIVE_DEPLOY.md | N/A | GUI 검증 및 네이티브 배포 계획으로 다단 채널 QA 인프라 연동 전략을 다룸 | 1 |
| DAEDALUS_SUPERSTRUCTURE_MASTER_DESIGN.md | N/A | Daedalus OS 15-wave 슈퍼스트럭처와 빌드전략을 상세 정리한 대규모 운영 설계서 | 0 |
| DAEDALUS_V1_FINAL_PLANNING.md | N/A | v1 최종 생산 계획의 10개 구성요소와 버전 전략을 정리 | 0 |
| EXPERIMENT_CONCLUSION.md | N/A | MC중심선도 실험 최종 결론과 자동화 경계(keep/drop/regenerate) 함의를 정리한 핵심 결론 | 3 |
| p1-findings.md | N/A | P1 IR 생성 정량 결과(엔티티 필터링, 라운드트립, 정합성)와 다음 단계 입력을 확정 | 3 |
| p2-findings.md | N/A | P2 의미복원의 분류/관계 결과 및 P2→P4 연동 포맷 확정을 정리 | 2 |
| p3-findings.md | N/A | 정합 residual=0 및 객체 대응 집계가 reveal 되는 P3 결과로 규칙학습 입력을 고정 | 3 |
| p4a-dataset-findings.md | N/A | 다종 데이터셋 정렬 성능, 종간 규칙 일반화 근거, LOO 입력 정합 결과 요약 | 2 |
| p6-findings.md | N/A | 7-fold object LOO 성능 및 정직 해석으로 진짜 자동화영역(keep/regen) 경계를 제시 | 3 |
| probe-findings.md | N/A | Probe 분석으로 IR 스키마 확정 근거가 되는 레이아웃 분해와 속성 결함 지점을 정리 | 3 |
| README.md | N/A | manifest 성격으로 버전/구성 인덱스를 참조용으로 제공 | 0 |
| research-catalog.md | N/A | 외부 연구백본과 데이터셋/모델 카탈로그를 정리한 참조 디렉터리 | 1 |
| SESSION_RECORD_20260613.md | N/A | 세션 로그형 가설 판정표로 과학적 게이트와 미해결 항목을 기록 | 1 |
| SESSION_RECORD_20260616.md | N/A | 재측정/SDK 라우터 로컬화 진행상태와 워크플로우를 시간순으로 정리한 실무 기록 | 1 |
| sjh_V5후_다음단계_결정노트.md | 2026-06-17 | V5 직후 액션 우선순위와 DIM 트랙 분리, 중심선도-파생물 관계 정리를 통해 다음 스텝을 선택 | 2 |
| transcribe-findings.md | N/A | 방향-선택적 치수 전사 규칙 발견, false-win 통제, transcribe 성능/재현 한계 정리 | 3 |
| VERIFICATION_WALKTHROUGH.md | N/A | verify_pipeline 기반 파이프라인 재현 명령과 각 단계 산출물 점검표를 제공하여 회귀 증거 확인이 즉시 가능 | 3 |
| wall-stations-findings.md | N/A | 벽 station 기반 기하 힌트의 한계(negative result)를 density 통제로 검증해 자동화 한계를 명확화 | 2 |
| wall-verification.md | N/A | 2독립 경로 검증(교차소스+시각)으로 wall 추출 결함을 포착하고 재현 단계까지 제시 | 2 |
| window-schedule-findings.md | N/A | 창호일람표는 입력 인코딩 기반이라 100% cover가 가능한 구조임을 증명하고 척도 간 비교 함정을 경고 | 3 |

## 미션 relevance 상위 15개 문서 다이제스트 (각 3-6문장)
### 1단계 - IR 생성기 (C# 하이브리드) 설계 노트.md
이 문서는 추출/재생성의 연산을 C#으로 고정하고 durable/검증은 Python으로 집중시키는 강한 경계를 세우고 있다. 핵심은 `extract→emit_durably→rebuild`의 순수함수형 데이터 플로우로, 스키마 변경과 계약 위반을 줄이기 위한 설계이다. 블록은 `Definition`과 `InstanceRef`를 외래키로 분리해 유지관리하고, `def_id` 기반 중첩 변환을 explicit하게 다뤄 익명 동적블록 누락 분석에 직접 연결된다. 현재 미션의 375/375 모델스페이스 적합도 실패에서, 이 문서의 “JSONL 단순 전달 + check_scope/scrub/L0” 계층은 어떤 정보가 누락되었는지 회귀적으로 추적할 수 있는 기준점이다. 특히 block interior 누락 패턴(해부 대상 `Hatch`/`anonymous *U`)를 detect하려면 여기서 제시한 단일 durable 지점이 로그 정합성에 유리하다.

### 1단계 - Probe(탐사) 설계 설명.md
이 문서는 IR 스키마 확정 전에 속성 후보를 잔차 없이 캐치하기 위한 1회성 정찰 프로세스를 다룬다. 무엇보다 “재생성 필요 vs 관계 보존 vs 버림”을 확률 빈도로 판별하는 규칙이 핵심으로, 누락 필드가 생기는 블록 내부 결함 후보를 빠르게 걸러낸다. 속성 분포/유니크 값/샘플링을 이용한 규칙은 `anonymous block`, `hatch`처럼 빈도는 낮더라도 치환/재생성에 결정적일 수 있는 엔티티를 놓치기 어렵게 만든다. 미션 목표 달성 관점에서 첫 단계로 매우 직접적이다.

### 2026-06-04-plan3-p1-extract-filter.md
P1 완료 문서로, 추출기 보강과 IR 필터(예: 84A X밴드), 라운드트립 경량 검증이 핵심이다. 실험용 pipeline에서 입력에서 추출까지의 “정형화/손실 최소화” 지점이 여기서 고정되어 있어, missing entity class를 찾는 기본 baseline이 된다. 특히 block definition/instance 경로가 깨질 때 어떤 단계에서 증분 손실이 생기는지 추적 가능하게 task를 나눈 점이 mission diagnosis에 유용하다.

### 2026-06-04-plan5-p3-alignment.md
정합 단계에서 registration, identity 매칭, matched/drop/regenerate 산출을 체계화한다. 이 문서의 alignment map 개념은 회귀 후 diff에서 어떤 객체가 원인인지 분리해 내는 데 핵심이다. 미션의 모델스페이스 fidelity 375/375와 `anonymous` block 누락은 단순 렌더 비교만으로는 설명되기 어려운데, 이 문서가 제시한 correspondence 스키마로 치환 객체군과 정의군을 분해하면 진짜 원인 분리가 가능하다.

### VERIFICATION_WALKTHROUGH.md
실제 산출물 경로와 pytest/verify 명령을 포함한 엔드-투-엔드 재현 매뉴얼이다. P1~P6 산출을 하나의 명령으로 확인하고, 주요 지표(남은 residual, KEEP/DROP/REGEN, transcribe 성능)를 실제 계산값으로 제시한다. 미션에서 필요한 것은 “측정 가능한 회귀 진단”인데, 이 문서는 그 기준선을 제공한다. 또한 false-win 방지보다 정답과의 차이를 구조적으로 추적하는 방식이 강점이다.

### p1-findings.md
P1 IR 생성 실측 결과를 정량적으로 정리하고, 정합과 필터가 pipeline에 미치는 영향(엔티티 수, 출력 품질, 라운드트립 지표)을 정리한다. 익스퍼트급 가치가 높은 이유는 실험값을 바탕으로 무엇을 보강할지 바로 연결 가능하기 때문이다. 블록/치수/텍스트 필드 보강이 어느 정도 효과가 있었는지 판단하며, 누락군 재채굴 우선순위를 정할 근거를 제공한다.

### p3-findings.md
P3 정렬 결과의 registration residual이 0에 근접한 지점을 명확히 보여주며, matched/drop/regen 분해를 제공한다. 이 분해는 모델스페이스 fidelity가 높아도 객체 내부 누락이 남는 상황에서 root cause를 찾는 핵심 입력값이다. 즉 기하 정합은 되는데 object 내부가 깨지는 문제가 있을 때, 정렬 단계를 통해 어떤 유형에서 regen이 과도하게 발생했는지 분류 가능하다.

### p4a-dataset-findings.md
7종 데이터셋 정렬 residual 0 및 종 불변성 결과는 일반화 가능성 점검에 유용하다. 미션처럼 특이 누락이 있는 경우, 단일 도면 특이성인지 공통 결함인지 구분해야 하는데 본 문서가 해당 판별 프레임을 제공한다. 특히 규칙학습 단계 이전의 데이터 건전성을 점검해 block interior 결측이 도메인 고유 결함인지 pipeline 고유 결함인지 분리한다.

### p6-findings.md
P5/P6 성능(precision/recall)과 정직 해석을 중심으로 baseline 전사율의 본질을 정리한다. 특히 “모델이 잘 맞는 것처럼 보일 수 있는 착시”를 제어하는 방식은 방향-선택 전사 규칙의 실제 기여도를 가려내는 데 유효하다. 미션의 100% 목표에서 67.6% 현재치로 갔을 때 어디까지 자동화 가능한지 판단하는 계량 기준이 된다.

### transcribe-findings.md
이 문서는 방향별(수직·수평) 치수 전사 규칙을 추출했고, random baseline 및 정렬 보정 통제를 통해 spurious hit를 배제했다. 알고리즘적으로는 입력-출력 짝짓기를 통해 `learned rule`의 신호 대 baseline uplift를 직접 보여준다. block interior처럼 치수/서식이 사라지는 경우에 대해, 전사 규칙만으로는 보완이 어렵고 생성 규칙이 필요한지 가늠하게 해준다.

### wall-stations-findings.md
구조벽 station 기반 station recall를 시도했으나 lift가 음수에 가까워 한계가 드러난 실험 기록이다. `geometry만으로 치수 자동화가 안 됨`을 정량적으로 입증한 보기 좋은 반례다. 이 결론은 미션에서 hatch-like entity나 dynamic block의 내부 구조 결함을 geometry만으로 회복하려 할 때의 한계를 경계선처럼 제공한다.

### wall-verification.md
검증 규율(교차소스 + 밀도 통제 + 육안)으로 순환논증을 제거한 사례다. wall 추출 버그(개구부 over-merge)처럼 내부 geometry 연산에서의 결함을 실제 지표와 시각증거로 재현한다. 미션에서 block 내부 결손의 진원인 추적에도 동일한 방식(독립 경로 + 통제 + 시각 증빙)을 적용할 수 있다.

### window-schedule-findings.md
이 문서는 input plane에서 이미 결정된 마크 정보가 출력 창호일람표로 재조직되는 양상을 보여주며, 자동화율 비교 척도의 함정을 강조한다. “같은 미션이라도 척도 불일치” 때문에 100%와 20%를 혼동하면 안 된다는 점이 강한 메시지다. 미션에서도 modelspace fidelity와 object class cover율을 같은 스케일로 비교하지 않도록 하는 지침으로 쓰기 좋다.

### ALM_V5_SCRIBE_DESIGN.md
V5 전략 전환 문서는 adversarial 보정과 데이터 갭 재해석을 통해 10% 남는 천장을 분해한다. 여기서 제시한 SCRIBE 중심의 generative pivot는 단순 rule-only에서 벗어나 재생성 실패 구간을 줄이는 방향이며, 특히 블록 내부 누락이 단순 추출 누락인지 표현능력 부족인지 구분하는 시야를 준다.

### ALM_V5_SCRIBE_DATA_GAPS.md
실제 병목이 되는 데이터 갭을 정성/정량으로 분리해 “무엇을 주면 천장이 열리는지”를 제시한다. 미션용으로는 `익명 동적블록(definition, insert internals)`과 같은 결손을 보완할 외부 입력 항목 후보를 뽑는 데 직접 활용 가능하다. 즉 어디서 측정 로그를 강화할지, 어디에서 모델링 가정을 바꿀지 우선순위를 제시한다.

### EXPERIMENT_CONCLUSION.md
MC중심선도 실험 최종 결론으로, 치수 자동화 한계를 설계 의도/기하 정보로 나누어 정리한다. 익스펜더블한 점은 keep/drop/regenerate 분해를 통해 “왜 못 그리는가”를 정량적으로 설명한다는 점이다. 미션의 목표 숫자(375/375)를 향한 판단도 이 문서에서 말하는 자동화 경계 프레임을 그대로 가져가야 정확하다.

## Top-10 Read-deeper (ranked)
1) 1단계 - IR 생성기 (C# 하이브리드) 설계 노트.md — block-definition/instance 분리와 durable 단일지점 덕분에 누락 유형 추적의 기본 인프라가 됨.
2) 2026-06-04-plan3-p1-extract-filter.md — 추출기 보강이 미션 성능 한계 직접 변경점이므로 수정 우선순위 산정에 핵심.
3) VERIFICATION_WALKTHROUGH.md — 지표·산출물을 기준으로 재현 가능한 원인 규명 루틴이 정형화되어 있음.
4) p1-findings.md — P1 단계 실측 수치로 블록 내부 누락의 원점(추출/필터/IR 결정)을 빠르게 찾을 수 있음.
5) p3-findings.md — 정렬 residual/매핑 결과가 regen 폭발 구간을 분리해 줌.
6) p6-findings.md — 정직한 성능 판독으로 true-improvement인지 착시인지 필터링 가능.
7) transcribe-findings.md — 통제된 전사 규칙의 증거 구조를 통해 규칙 기반 보완 여지를 정밀하게 검증.
8) 1단계 - Probe(탐사) 설계 설명.md — schema blindspot을 없애는 1회성 정찰로 누락 필드 탐지에 직접 도움.
9) ALM_v0.3_y_VALIDATION_ORACLES_METRICS_CALIBRATION.md — 오라클/캘리브레이션 설계로 미션 지표 신뢰도와 재현성 보강.
10) ALM_V5_SCRIBE_DATA_GAPS.md — 익명 블록/hatch류 누락처럼 데이터 보강이 필요한 병목의 우선순위를 정해 수정 범위를 줄임.
