# ALM 단계 사다리 종합 — 10개 설계 노트가 규정하는 것과 현재 위치

> 1~5단계 설계 노트 + sjh_V5후 결정노트 + SCRIBE 2편을 원문 근거로 종합. 결론: 현재 E2E 왕복(375/375 modelspace diff0)은 **1단계(IR) 게이트를 modelspace 해상도에서만 충족**한 상태이고, block-interior 67.6%는 1단계 노트가 명시한 "블록 2단 구조" 검증이 아직 LOCK에 못 미쳤다는 뜻이다. 2단계 이후(분류·관계·규칙)는 근거 문서상 착수 전이다.

**약어**: P1=1단계Probe노트 · IR1=1단계IR생성기노트 · S2=2단계의미복원노트 · S2d=2단계심화노트 · S3=3단계변경반응노트 · S4=4단계규칙성장공장노트 · S5=5단계확장노트 · SJH=sjh_V5후결정노트 · SCRIBE=ALM_V5_SCRIBE_DESIGN · GAPS=ALM_V5_SCRIBE_DATA_GAPS

## 0. 미션 컨텍스트 대비 왜 이 종합이 필요한가

10개 노트는 두 개의 서로 다른 ALM 트랙을 담고 있다 — (a) **P1/IR1/S2/S2d/S3/S4/S5**: 도면 IR→의미→변경반응→규칙성장→확장으로 이어지는 "공장" 사다리, (b) **SJH/SCRIBE/GAPS**: 평면도→중심선도 생성(SCRIBE)이라는 별도 하위과제의 실측·판정. 이번 미션(E2E 왕복 375/375 diff0, block-interior 67.6%)은 (a) 트랙의 1단계에 해당하는 실험이므로, 판정의 본체는 (a) 5개 노트이고 (b) 3개 노트는 주로 §4(미활용 힌트)와 "n=1 과적합 경계" 원칙(§1.4)의 근거로만 인용한다.

---

## 1. 각 노트가 무엇을 입법하는가 (5개 개념 축)

### 1.1 rebuild-sufficiency gate (재생성 충분성 게이트)
- **P1 §5**: "Probe로 카탈로그 뽑음 → 스키마 확정 → 추출기 → JSONL만으로 복원 → 원본과 diff → 의미적 손실 0 → `cad_object` DRAFT→LOCK". LOCK 조건은 diff=0이지 근사치가 아니다.
- **IR1**: "복원(C#) = **원본 안 봄**, JSONL만. 그래야 누락이 드러남(**커닝 금지**)." rebuild가 원본을 참조하면 게이트 자체가 무력화된다는 원리.
- **IR1 하단 경고 (결정적)**: "라운드트립은 **generic IR(기하 복원) 검증엔 강력**, **domain IR(관계·의미) 검증엔 무력**." — 이 게이트는 1단계 전용이지, 2단계 이후를 증명하지 못한다.

### 1.2 naive-foil discipline (naive 대조군 규율)
- **S3 §3.5**: `R_ANCHOR_2000`(naive foil, after만 보고 절대거리) vs `R_INPANEL_FOLLOWS`(smart, before/after 불변성) 코드 대조. "둘을 동시에 돌리면 RUN-002에서 **naive PASS(73개 다 통과) + smart FAIL(73개 다 위반)**이 나옴." 규칙이 naive보다 실제로 나은지 코드 레벨로 증명하라는 요구.
- **S4 §2·§9**: `FailurePattern.contrast_sharpness`(naive PASS & smart FAIL이 깨끗이 갈리는 정도)가 통계 게이트의 임계값. "naive-foil 대조 재현: RUN-002 데이터 → naive PASS & smart FAIL 73개가 패턴으로 묶이고 게이트 통과하는지"가 검증 항목.

### 1.3 VACUOUS != PASS
- **S3 §3.8 (H6)**: `ValidationResult(passed, violations, vacuous)` — "vacuous는 PASS가 아니다. **'이 규칙은 이 변경에서 시험 안 됨'** — 별도 분류." vacuous를 4단계가 "아직 실데이터로 시험 안 된 규칙" 신호로 소비.
- **S4 §1**: "공장 1 가동 → validation_event(**위반/vacuous**) 쌓임"이 공장2 원료 — vacuous가 조용히 버려지지 않고 별도 트랙으로 흐름.
- 이 규율은 이미 코드베이스에 일부 선반영됨 — 커밋 `0d99c04 census vacuous-extraction guard: fail-closed + retry (VACUOUS != PASS)` (본 세션 시작 git 로그, 별도 파일 열람 없이 확인).

### 1.4 corpus anti-overfitting (코퍼스 과적합 방지)
- **S4 §5 (통제장치4)**: `cross_validation.py` — "발견 도면(train)과 검증 도면(test)을 분리. **자기 데이터로 자기 규칙 검증 = 검증 아님**." FP율 > 0.1 → reject.
- **S2d §3.5**: golden 선정 원칙 — "**많이가 아니라 골고루**. 여러 타입·class 골고루 나오는 1장 > 단조로운 10장."
- **S5 §2.3**: "새 객체로 기존 분류 정확도 하락 → golden에 새 객체 포함시켜 **재측정, 회귀 감지**."
- **SJH §7**: "V5도 **n=1 프로젝트**(한 시트 7타일) — single-case existence proof... cross-project = 유일한 길." 같은 프로젝트 반복은 "수확체감"이라고 명시.
- **SCRIBE §5 통제**: "룰=외부 법규(**절대 GT에 튜닝 금지**) · GT는 생성 동결 후에만 열람 · **NULL 재실행**: 모든 허용오차 확대마다 1000-trial value-shuffle NULL 재계산."

### 1.5 validator-validation (검증기 자체를 검증)
- **S2 §3**: calibration — "**'confidence 0.7이라 말한 것들이 실제로 70% 맞는가?'** 측정하고 어긋나면 고침." 분류기(검증기)의 자기 신뢰도 주장 자체를 별도 ground-truth로 검증.
- **S4 §6**: "confidence는 **측정이 아니라 주장**이고, 맞는지는 calibration으로만 검증된다." + "장치1의 min_conf=0.9는 반드시 **calibration된 값**" — raw LLM confidence로 게이트를 걸면 과신 때문에 순환 차단(장치1) 자체가 무력화된다는, 검증기의 검증기 논리.
- **S2d §3.6**: golden 자체도 사람이 틀릴 수 있음 → "**2인 교차 검수** 또는 애매건 표시" — ground truth(다른 모든 검증의 기준)조차 검증 대상.
- **SCRIBE §5**: NULL-trial(1000회 shuffle) 재계산 = 측정 방법론 자체가 우연(chance)이 아닌지 검증하는 메타 레이어. 실제로 SJH에서 "EXP-4 dim_recall 0.83~0.86 → NULL 1000회 후 **5/6 fold 비유의**"로 방법론 자체를 기각시킨 실례.

---

## 2. 현재 프로그램이 만족한 사다리 단은 어디까지인가

| 단계 | 요구 증거 형태 (노트 근거) | 현재 실측 | 판정 |
|---|---|---|---|
| 1단계 IR (modelspace) | diff=0, JSONL-only rebuild (P1 §5, IR1) | 375/375 modelspace diff0 완전일치 | **LOCK 충족** (해당 해상도에서) |
| 1단계 IR (block-interior) | 블록 정의/인스턴스 2단 구조 각각 diff=0 (IR1 "블록 처리" 절) | 67.6% (1.dwg) | **PARTIAL** — LOCK 미달 |
| 2단계 의미복원 (입법·분류·관계·calibration) | semantic_class 온톨로지 선언 + golden 대조 (S2, S2d) | 근거 문서상 미언급/미착수 | **미평가 대상** |
| 3단계 변경반응 (detect/impact/evaluate/regenerate, naive-foil) | before/after 합성+실데이터 시나리오 (S3) | 근거 없음 | **미착수** |
| 4단계 규칙성장공장 | validation_event(위반/vacuous) 축적 후 4장치 가동 (S4) | vacuous 개념만 census guard에 선반영, 규칙발명 파이프라인 없음 | **미착수** (개념만 선취) |
| 5단계 확장 | profile 1파일로 신규 회사 온보딩 드라이런 (S5) | 근거 없음 | **미착수** |

- **핵심 판정**: IR1이 명시한 "복원(C#) = 원본 안 봄" 게이트 자체는 modelspace에서 강하게 충족됐다(375/375). 그러나 IR1은 블록을 "정의 테이블 + 인스턴스" 2단으로 분리해 각각 검증하라고 못박았고(IR1 "블록 처리" 절), 67.6%는 이 2단 중 최소 한쪽(대개 정의 내부 재귀)이 아직 손실을 낸다는 뜻 — **1단계는 PARTIAL_PASS**, 스키마 DRAFT 유지.
- **경계 조건 재확인**: IR1 스스로 "라운드트립은 domain IR 검증엔 무력"이라 명시하므로, block-interior가 100%가 되어도 그것은 **오직 1단계를 닫을 뿐** 미션 컨텍스트가 말하는 "시맨틱 검증 레이어"(2단계)는 자동으로 안 열린다. 별도의 golden/calibration 트랙이 필요(S2, S2d).
- **VACUOUS != PASS**는 3단계 노트가 정의한 개념이지만, 이미 census/추출 게이트(커밋 0d99c04)에 선반영되어 있다는 점에서 "정식 evaluate.py 없이도 철학은 앞서 채택됨" — 좋은 신호지만 아직 3단계 본류(규칙 위반 평가)에는 적용된 적이 없다.

---

## 3. 남은 단 + interior-100%가 구체적으로 요구하는 것

### 3.1 block-interior 100%를 위한 직접 요구사항 (IR1, P1 근거)
1. **정의-인스턴스 외래키 완전성** — "매칭: 인스턴스 `def_id` = 정의 `def_id` 외래키. RUN-002의 446 parent_idef 누락 = 이 외래키 끊김." 남은 32.4% 손실의 유력 후보로 정확히 지목된 패턴(IR1 "블록 처리" 절).
2. **중첩 블록 재귀 검증** — "중첩이면 재귀(transform 누적)." P1 예시 카탈로그가 "InstanceDefinition 240종, 그중 **중첩(블록 속 블록) 18종**"을 명시 — 중첩 깊이가 얕은 재귀 컷오프(P1 §6 "1~2 depth까지만") 때문에 잘렸는지 확인 필요.
3. **원본-불참조 원칙을 정의 레벨에도 적용** — 전체 문서 diff0가 나와도, 그 안에 "정의 자체는 안 쓰이거나 얕게만 쓰인" 사각지대가 있으면 안 됨. IR1의 "커닝 금지" 원칙을 block_definitions.jsonl 단위로 별도 diff해야 함(정의별 독립 diff, 인스턴스 diff와 분리).
4. **패턴별 유해/무해 판정 루프 재가동** — P1 §5 step5: "차이 목록(패턴 5~15줄) → 유해면 스키마 필드 추가 → 재실행." 67.6%의 잔여 손실을 패턴으로 묶어 어떤 속성이 빠졌는지(제어점·knot·회전·중첩 transform 등) 다시 캐야 함 — 이번에는 block-interior 전용 diff 채널로.
5. **tolerance 파라미터의 도메인 재확정** — IR1 "미해결" §4.3: "tolerance 값은 도면 단위·정밀도 보고 확정." SCRIBE의 M-002(50mm 그리드, tol 25mm) 사례처럼, block-interior 좌표계가 modelspace와 다른 정밀도/스케일을 가질 수 있음 — 별도 tolerance 프로파일 필요할 수 있음.
6. **"필수 vs 잡주머니" 재분류를 block-interior 속성에도 적용** — P1 §4가 제시한 3분류(필수/잡주머니/버림) 잣대(재생성에 쓰나·분류 단서인가)를 modelspace 스키마에서만 확정했을 가능성이 있음. 정의 내부 객체(중첩 블록 로컬 속성)가 같은 잣대로 재검토됐는지가 32.4% 잔여 손실 중 "애매해서 잡주머니로 눌러둔" 속성이 있는지의 근거가 된다.

### 3.2 100% 이후 "시맨틱 검증 레이어"를 위한 요구사항 (S2, S2d 근거)
- 라운드트립으로 못 닫음(IR1 경계 조건) → **입법(semantic_class 선언, S2 §0)**을 먼저 해야 함: "칸은 발견되는 게 아니라 선언된다."
- golden set은 "**검수(review)**" 방식으로 제작(S2d §3.2): 시스템이 먼저 추론 → 사람이 ✓/✗/+ 검수. 백지 라벨링보다 5~10배 쌈.
- golden 선정은 "**다양성 우선**"(S2d §3.5), 놓침(거짓음성) 노출용 UI 필요(S2d §3.3).
- 분류는 2층(rule 우선, LLM 잔여물, S2 §1), 관계는 3층(명시적 연결 → 기하추론 → LLM, S2 §2) 구조를 그대로 채택해야 confidence·evidence 계약이 유지됨.

---

## 4. 아직 활용되지 않은 알고리즘·온톨로지·모델링 힌트

| 힌트 | 출처 | 내용 |
|---|---|---|
| 정성적 공간 술어 번역기 | S2d §1 | 절대좌표 대신 "북 50mm / bbox 안 / 평행" 같은 LLM 친화 술어로 이웃 관계를 번역. 적응적 반경(median spacing×배수 + 상위 K 컷). |
| 확실성 순서 부트스트랩 | S2d §2 | rule(Pass0, 결정론) → 0.9+만 발판 승격 → LLM(Pass1..N) 점진 확산. "불확실한 것은 발판이 못 된다"는 오류전파 차단 원칙. |
| decision tree 규칙 발견(2세대 엔진) | S4 §3 | `DecisionTreeClassifier(max_depth=4, min_samples_leaf=20)`로 위반/통과를 학습 → 순수 경로를 규칙 후보로 컴파일, leaf 순도=데이터기반 confidence. "ML이 발견, 사람이 입법." |
| identity 3단 매칭 | S3 §1.2 | GUID → shape_hash+layer+거리 기반 지문 매칭(score≥0.7) → 삭제/생성. export로 GUID 깨져도 변경 추적 가능. |
| 관계 전파 온톨로지 | S3 §2.2 | `(change_kind × relation_type) → propagate?/action/max_hop/condition`을 yaml로 입법, 감쇠(×0.9)+visited로 무한전파 차단, 안전 기본값 propagate:false. |
| 규칙 라이브러리 통합(subtractive) | S4 §4 | merge/absorb/escalate/generalize 4분기 — "mcp-memory 52→15 타입 축소로 NDCG 0.057→0.624" 유사사례 인용, "추가 아니라 통합으로 자람." |
| 약/강 하이브리드 라우터 | S4 §8 | contrast_sharpness로 선명(제안+승인)/애매(질문생성+답변) 분기. "최적 공장2 = 좋은 질문 생성기." |
| profile 상속 구조 | S5 §1 | `inherits: sunapse_default` + 차이만 오버라이드. 신규 회사 온보딩이 "코드 0줄, yaml 1파일." |
| 위상/하중경로 피처(구조벽 일반화 후보) | SJH §4 P0.5 | `wall_continuity`, `connectivity_degree`, `spans_full_bay`, `aligned_chain_length`, `is_envelope`, `closed_loop_membership` — 구조도 없이 평면도만으로 구조벽 추론하는 유일한 미검증 경로. |
| 그리드 스냅 + raw/snap 이중기록 | SCRIBE STEP5 (M-002) | 50mm 그리드에 tol 25mm 스냅, 원본·스냅 값 둘 다 보존 — 도면 좌표 tolerance 처리의 재사용 가능한 패턴. |
| 값-기하 정합 규칙 패턴 | S3 §3.6 (`value_matches_geometry`) / SCRIBE D-001 | 치수 텍스트 값과 실제 기하 거리를 대조하는 패턴 — 시맨틱 검증 레이어에서 "표기값이 기하와 맞는가" 규칙으로 재사용 가능. |
| 순환차단 clean-filter | S4 §1 | 위반에 연루된 모든 객체·관계의 calibration된 confidence가 min_conf 이상일 때만 "규칙 재료"로 인정, 미달은 2단계 리뷰 큐로 환류(`is_clean_failure`). 분류/관계가 아직 없어 미적용. |
| decision_failure_ontology (FailureEvent→RootCause→Mitigation) | S4 §10 | 위반 패턴·규칙후보를 담는 3단 온톨로지 구조. 규칙성장 이력을 그래프로 추적하는 스키마이나 아직 어떤 데이터도 안 들어감. |
| golden 검수 Rhino 플러그인(재사용 자산) | S2d §3.4 | 시스템 추론 관계를 Rhino에 시각화→클릭 수정/추가→export. "3·4단계 범용 검수 도구의 첫 버전"으로 설계됐으나 미착수. |
| 라이브러리 부패 점검 도구 | S5 §5 | `library_health.py`(모순/중복 자동 탐지) · `profile_diff.py`(회사 간 drift 점검) — 규칙 수가 늘어날 때를 대비한 정기 점검기, 아직 규칙 자체가 없어 미적용. |
| calibration bin 재매핑 | S2 §3 / S4 §6 | confidence 구간별 실제 정답률을 측정해 "모델 0.9 → 실제 0.82"로 환산하는 매핑 테이블. 분류 confidence 자체가 아직 없어 적용 대상이 없음 — 시맨틱 레이어 착수 시 1순위로 활성화될 도구. |

---

## 5. 다음 단계 최우선 요구사항 10선 (순위)

1. **block 정의/인스턴스 외래키(parent_idef) 완전성 검사** — 67.6% 갭의 최유력 원인으로 명시 지목 (IR1, RUN-002 446건 선례).
2. **block-interior 전용 독립 diff 채널 구축** — 전체문서 diff0와 별개로 block_definitions.jsonl 단위 diff 필요 (P1 §5, IR1 커닝금지 원칙).
3. **중첩 블록(블록 속 블록) 재귀 깊이 재검토** — P1이 "1~2 depth 컷오프"를 명시, 실제 도면엔 다단 중첩 존재 가능 (P1 §2-4, §6).
4. **rebuild-sufficiency 게이트의 적용범위 재확인** — 100% 달성해도 "시맨틱 검증 레이어"는 자동으로 안 열림, 별도 트랙 필요 (IR1 "라운드트립 적용범위" 경고).
5. **semantic_class 온톨로지 입법을 분류 착수 전에 완료** — 칸은 선언이지 발견이 아님, 순서를 건너뛰면 안 됨 (S2 §0).
6. **golden set을 "검수" 방식 + 다양성 우선으로 제작** — 백지 라벨링 대신 시스템 추론→사람 검수, 놓침 후보 UI 필수 (S2d §3).
7. **VACUOUS != PASS 규율을 3단계 evaluate 본류까지 일관 확장** — 현재 census guard에만 선반영, 규칙평가 파이프라인 구축 시 처음부터 3분류(passed/violations/vacuous) 강제 (S3 §3.8, 기 커밋 0d99c04).
8. **confidence 게이트는 항상 calibration된 값만 사용** — raw LLM self-confidence로 임계값을 걸면 과신으로 무력화 (S2 §3, S4 §6).
9. **naive-foil 대조를 향후 모든 규칙에 의무화** — 새 규칙 도입 시 naive 버전과 병행 실행해 대조 선명도 확인 (S3 §3.5, S4 §2).
10. **교차 도면(train/test) 분리 없이는 어떤 규칙도 승격 금지** — 1.dwg 단일 도면 결과를 다른 도면에 일반화하기 전 홀드아웃 검증 필수, n=1 함정 회피 (S4 §5, SJH §7).

---

## 마무리

1~5단계 노트의 공통 골격은 "결정론이 앞뒤를 감싸고 LLM은 잔여물·번역·질문에만 쓰이며, 입법은 항상 사람"이라는 원칙(S3 §관통원리, S4 §13, S5 §4)이다. 현재 프로그램은 이 사다리의 **1단계 기하 게이트를 modelspace 해상도에서 증명**했지만, 같은 게이트를 block-interior 해상도로 밀어 넣는 작업이 남아 있고, 그 이후의 모든 단(2~5단계)은 노트가 요구하는 증거 형태(golden, calibration, naive-foil, cross-validation)가 아직 하나도 제시되지 않았다. 다음 실행 우선순위는 위 10선이며, 특히 1~4번은 지금 진행 중인 interior-fidelity 작업과 직접 겹친다.

노트 전체를 관통하는 마지막 경고 하나를 덧붙인다 — S5 §4는 "5단계의 성패는 1~4단계 설계 품질이 결정한다"고 못박는다. 즉 block-interior 100%를 서두르다 IR1의 "커닝 금지"·"블록 2단 구조" 원칙을 우회(예: 정의 대신 인스턴스 좌표만 보정)하면, 그 수치는 diff0을 보여도 진짜 LOCK이 아니라 FM1(Fake PASS)에 해당하는 결과가 될 위험이 있다.
