# E2 방법론 심층 도시예 — `platt_P0`

**제안:** P0 — E1 불일치 법의학 감사 + 핸들-공간 계약  
**좌석:** platt · P0  
**연구 성격:** 학습·판정자·신규 LLM 호출이 없는 결정론적 계측 감사  
**증거 경계:** 이 문서의 실측 수치는 제공된 패킷 다이제스트만 재진술한다. 아래의 알고리즘 임계값은 패킷에서 이미 제시된 밴드이거나, 아직 측정되지 않은 **사전등록 제안값**이다. 문헌 언급은 일반 지식이며 웹 검색은 사용하지 않았다.

이 제안의 목적은 새 탐지기를 만드는 것이 아니다. 먼저 E1의 “탐지기와 LLM이 다른 벽을 본다”라는 문장이 실제 CAD 엔티티에 대한 올바른 계측에서 나온 것인지 판정한다. 핵심 산출은 벌거벗은 문자열 핸들을 증거로 취급하지 않고, `(도면, 정의, 인스턴스 경로, 소유권, 엔티티 타입, 좌표계, 변환, 원문 인용 위치)`를 함께 갖는 참조로 바꾸는 **핸들-공간 계약(handle-space contract)** 이다. 이 계약을 통과하지 못한 E1 인용은 탐지기 결함의 증거가 아니라 계측기 결함의 증거다.

증거 상태는 문서 전체에서 다음처럼 구분한다.

- `PACKET_OBSERVED`: 패킷 다이제스트에 명시된 기존 실측.
- `DETERMINISTIC_DERIVED`: 향후 동결된 스크립트가 입력 IR/JSONL에서 계산할 사실.
- `PREREG_PROPOSED`: 결과를 보기 전에 동결할 규칙·임계값·시드.
- `LITERATURE_BACKGROUND`: 방법론을 설명하는 일반 지식이며 본 프로그램의 실측이 아님.
- `UNKNOWN/BLOCKED`: 입력이나 계약이 없어 판정할 수 없음. PASS로 대체하지 않는다.

## 1. 이론적 근거·선행연구

### 1.1 강한 추론과 dissolver 우선순위

이 제안은 Platt의 *Strong Inference* 계보를 따른다(`LITERATURE_BACKGROUND`; 정확한 서지 세부는 출판 전 요검증). 경쟁 설명을 늘어놓는 대신, 가장 싼 실험으로 상위 전제를 먼저 죽인다. 여기서 경쟁 설명은 다음 둘이다.

- **H0-M(계측 아티팩트 가설):** E1 불일치의 상당 부분은 존재하지 않는 핸들, 기대 타입과 다른 엔티티, 잘못된 정의 소속, 중첩 INSERT의 좌표/소유권 누락, 단위 가정, 정렬 키, 또는 출력 나열 지시가 만든 것이다. 이 경우 “탐지기가 벽 개념을 놓친다”는 해석은 아직 성립하지 않는다.
- **H1-C(개념·커버리지 가설):** LLM 인용은 해당 정의의 실제 엔티티로 해소되고, 대부분 실제 LINE이며, 공통 좌표계에서 구조적으로 쌍가능하다. 이 경우 계측 아티팩트 H0-M은 죽고, 탐지기의 표현·커버리지 결함을 겨냥한 후속 실험이 정당화된다.

패킷의 O-A는 H0-M 생존 강화, O-B는 H0-M kill에 대응한다. 이는 통계적 “영가설을 채택”한다는 뜻이 아니다. 선택된 사례에 대해 어떤 설명이 결정론적 사실과 양립하는지를 판정하는 반증 규칙이다.

### 1.2 측정 이론: 구성개념 타당도보다 먼저 오는 참조 무결성

Cronbach–Meehl의 구성개념 타당도, Campbell–Fiske의 수렴·판별 타당도, 오류변수(errors-in-variables) 문제는 모두 관측값이 대상을 제대로 가리킨다는 전제를 둔다(`LITERATURE_BACKGROUND`; 서지 세부 요검증). E1에서 `"1A2B"` 같은 문자열이 “벽 선분”이라는 관측으로 쓰였다면, 먼저 다음이 참이어야 한다.

1. 문자열이 파싱 가능한 참조다.
2. 참조 대상이 Graph IR에 실제 존재한다.
3. 그 대상이 비교 중인 도면정의의 직접 구성원인지, 중첩 정의의 구성원인지 구별된다.
4. 기대 타입이 LINE이라면 실제 타입도 LINE인지 확인된다.
5. 중첩 엔티티라면 어떤 INSERT 인스턴스를 거쳐 어느 좌표계로 전개되었는지 결정된다.
6. 탐지기의 기하 밴드와 비교할 때 좌표 단위가 명시된다.

이 단계는 라벨 품질 논쟁이나 silver 판정자 신뢰도보다 선행한다. 엔티티의 실재·타입·소유권은 사람의 벽 의미 판단이 아니라 데이터베이스 참조 무결성에 가까운 결정론적 사실이다.

### 1.3 데이터베이스 참조 무결성, 데이터 계보, design by contract

핸들-공간 계약은 관계형 데이터베이스의 외래키 무결성, W3C PROV 계열의 데이터 계보, Meyer 계열의 design by contract와 같은 원리를 CAD 증거에 적용한다(`LITERATURE_BACKGROUND`; 정확한 판본 요검증).

- **외래키 관점:** 인용 핸들은 반드시 명시된 유일성 범위에서 한 엔티티로 해소되어야 한다.
- **계보 관점:** 원시 JSONL의 어느 행·어느 문자 범위가 어떤 정규화 과정을 거쳐 어떤 IR 엔티티에 연결되었는지 보존한다.
- **계약 관점:** 전제조건(도면 ID, 정의 ID, 좌표 프레임, 기대 타입)이 빠진 참조는 조용히 추정하지 않고 계약 위반으로 분류한다.
- **총함수 관점:** 모든 입력은 성공 또는 명시적 실패 코드로 끝난다. 예외·미해소·모호성을 누락 행으로 버리지 않는다.

DWG 핸들의 실제 유일성 범위와 Graph IR의 재키잉 방식은 패킷에 주어지지 않았다. 따라서 “핸들은 도면 전체에서 유일하다” 같은 외부 가정을 넣지 않는다. 스키마에서 실제 키 범위를 확인하여 `drawing_id + handle`, `definition_id + handle`, 또는 별도 `entity_id` 중 하나를 계약에 동결하며, 둘 이상이 같은 입력을 해소하면 `AMBIGUOUS_DUPLICATE`로 실패시킨다.

### 1.4 CAD 블록 그래프와 좌표 프레임

INSERT 중첩은 단순한 파일 폴더 구조가 아니라 인스턴스 그래프다. 하나의 정의가 여러 번 삽입될 수 있고, 동일한 내부 엔티티가 서로 다른 월드 좌표를 가질 수 있다. 따라서 “중첩 정의 안에 그 핸들이 있다”와 “현재 루트 정의의 특정 인스턴스에서 그 선이 어디에 있다”는 별도 사실이다.

각 INSERT 변환을 동차 affine 행렬 (T_e)로 나타내면, 인스턴스 경로 (p=(e_1,\ldots,e_k))의 공통 루트 좌표 변환은 다음과 같다.

\[
T_p = T_{e_1}T_{e_2}\cdots T_{e_k}, \qquad x_{root}=T_p x_{local}.
\]

행렬 곱 방향은 IR의 좌표 관례를 읽어 fixture로 검증한 뒤 동결한다. 경로가 없는 중첩 핸들은 엔티티 정의에는 해소될 수 있어도 인스턴스 기하에는 유일하게 해소되지 않는다. 이를 억지로 첫 INSERT에 붙이지 않고 `INSTANCE_PATH_REQUIRED`로 남기는 것이 계약의 핵심이다.

### 1.5 소프트웨어 오라클, differential testing, metamorphic relation

McKeeman 계열 differential testing과 metamorphic testing은 정답 라벨이 부족할 때 구현 간 불일치나 불변 관계로 버그를 찾는 방법이다(`LITERATURE_BACKGROUND`; 서지 세부 요검증). P0는 그보다 더 강한 오라클을 일부 갖는다. “이 핸들이 존재하는가”, “타입이 무엇인가”, “어느 정의가 소유하는가”는 Graph IR 자체를 직접 조회할 수 있다.

다만 “벽인가”와 “쌍가능한가”는 구분해야 한다. 벽 의미는 이 감사의 오라클이 아니다. 쌍가능성도 두 층으로 나눈다.

- **구조적 쌍가능성:** 같은 공통 좌표계에 놓인 두 유효 LINE이 각도·종방향 겹침 조건을 만족하는가.
- **mm 대역 적합성:** 구조적 쌍이 단위 계약이 유효할 때만 기존 두께 대역에 들어오는가.

이 분리는 단위 오류가 “쌍이 없음”으로 둔갑하는 순환 논리를 막는다.

### 1.6 극단 사례 + 무작위 음성 대조의 역할

top-20은 E1 불일치가 큰 극단 사례라서 결함 재현에는 효율적이지만 모집단 표본은 아니다. 특히 패킷이 경고한 익명 `*U###` 또는 xref-bound 정의 편중은 선택·정렬 설계가 만든 조건부 분포일 수 있다. 따라서 고정 시드의 무작위 대조 20개를 같은 코드 경로로 감사한다.

대조군의 목적은 “정상” 라벨을 제공하는 것이 아니다. 동일한 해소 실패가 E1 극단에서만 농축되는지, Graph IR 전반의 일반 계약 문제인지 구별한다. top-20과 대조 20의 차이는 설명 보조이며, 패킷의 O-A/O-B 기본 밴드를 사후에 바꾸는 용도로 쓰지 않는다.

### 1.7 이름 토큰과 나열 지시 아티팩트

블록명 토큰과 `wall_likelihood`의 상관은 벽 진리의 검증이 아니다. LLM이 이름 prior에 탑승했는지 보는 H3 방향 증거다. 패킷에서 탐지기 full-vs-name-blind가 완전히 동일하고 레이어명 신호가 0이었다는 사실과 결합하면, 이름 상관은 두 증거 축의 독립성에 직접 영향을 준다. 그러나 한 도면 안 정의들은 독립 표본이 아니므로 모집단 인과 효과로 과장하지 않는다.

`n_h_ornith=10` 클러스터도 “정확히 열 개의 벽이 있다”는 사실과 “열 개를 나열하라는 프롬프트/파서 cap”을 분리해야 한다. 원시 응답, 원시 프롬프트, 파서 전후 토큰 수가 함께 있어야만 결정론적 판정이 가능하다. 원문이 없으면 `UNKNOWN/BLOCKED`이며, 후처리 JSON만으로 모델 아티팩트라고 단정하지 않는다.

### 1.8 문헌 사용의 한계

이 연구의 load-bearing evidence는 문헌이 아니라 로컬 Graph IR과 E1 원시 JSONL이다. 위 문헌명은 설계 계보를 설명하는 `LITERATURE_BACKGROUND`이며 어떤 프로그램 수치도 뒷받침하지 않는다. 외부 검색을 하지 않았으므로 정확한 판본·연도·페이지가 필요한 인용은 출판 전에 요검증한다. 실험 실행 여부도 모두 `PLANNED`로 유지하며, 이 도시예 자체를 실행 결과로 표시하지 않는다.

## 2. 알고리즘 정확 스펙

### 2.1 입력 계약

감사기는 다음 논리 입력을 받는다. 실제 파일명·필드명은 schema-only 단계에서 매핑하되 의미가 맞지 않으면 중단한다.

1. **Graph IR 정의 테이블**
   - 필수: `drawing_id`, 안정적인 `def_id`, 원문 `def_name`.
   - 선택이지만 존재 시 보존: xref/anonymous 플래그, source unit metadata.
2. **Graph IR 엔티티 테이블**
   - 필수: 안정적인 `entity_id` 또는 해소 가능한 raw handle, `owner_def_id`, raw entity type.
   - 기하 타입 필수 필드: LINE 끝점, 각 타입의 bbox 계산에 필요한 유한 좌표.
   - INSERT 필수 필드: 참조 `child_def_id`, affine transform 또는 이를 정확히 구성할 원시 파라미터.
3. **E1 원시 JSONL (`reports/e1/`의 ornith 산출)**
   - 필수: 대상 정의 키, detector/E1 divergence의 원시 구성값 또는 정확한 `_score_divergence` 재현 정보, `wall_likelihood`, LLM 인용 핸들 원문, 원시 응답.
   - `n_h_ornith=10` 아티팩트 판정을 위해 원시 프롬프트 또는 프롬프트 템플릿 식별자가 필요하다.
4. **실행 manifest**
   - 입력 경로·바이트 해시, IR schema version, E1 parser version, Python/NumPy 버전, 정렬 규칙, prereg 해시를 기록한다.

필수 필드가 없을 때는 유사한 이름의 필드를 추측하지 않는다. `SCHEMA_MISSING`, `JOIN_KEY_MISSING`, `RAW_PROMPT_MISSING`, `RAW_RESPONSE_MISSING`, `DIVERGENCE_REPRO_MISSING`처럼 원인별로 중단 또는 부분 차단한다.

### 2.2 결과 보기 전 동결할 prereg 객체

향후 실행 시 결과 파일을 읽기 전에 다음 내용을 직렬화하고 해시한다. 여기의 숫자는 패킷 밴드 또는 `PREREG_PROPOSED` 값이지 새 실측이 아니다.

```yaml
audit_id: platt_P0
cohort:
  divergent_k: 20                  # 패킷 고정
  random_control_n: 20             # 패킷 고정
  control_seed: "platt_P0/control/20260718/v1"  # 사전등록 제안값
  control_sampler: sha256_rank_without_replacement
types_primary: [LINE, LWPOLYLINE, MLINE, ARC, INSERT, HATCH]
handle_normalization: raw_plus_trimmed_upper_hex_v1
name_normalization: unicode_nfc_casefold_whitespace_v1
pairability:
  angle_tolerance_deg: 2           # 기존 탐지기 v1 값
  overlap_min: 0.5                 # 기존 탐지기 v1 값
  gap_mm_min: 50                   # 기존 탐지기 v1 값; 단위 계약 유효 시만
  gap_mm_max: 400                  # 기존 탐지기 v1 값; 단위 계약 유효 시만
decision:
  oa_bad_rate_ge: 0.50             # 패킷 고정
  ob_bad_rate_le: 0.10             # 패킷 고정
  ob_pairable_rate_gt: 0.50        # '다수'의 사전등록 연산화
  unit_factor_ge: 10               # 패킷 고정
  unit_def_rate_ge: 0.30           # 패킷 고정
name_test:
  primary_token: "평면도"
  alpha: 0.05                      # 사전등록 제안값; 탐색 결과가 아님
ornith_artifact:
  cluster_value: 10                # 패킷 지정
  majority_ge: 0.50                # 사전등록 제안값
```

prereg 변경은 허용하되 기존 파일을 덮지 않고 새 버전과 사유를 남긴다. 실제 결과를 한 번이라도 비맹검으로 본 뒤 바뀐 규칙은 확인적 결과가 아니라 탐색적 결과로 강등한다.

### 2.3 핸들 정규화와 해소

원문 보존이 우선이다. `raw_handle`을 절대 덮어쓰지 않고, 다음 파생값을 별도 필드에 둔다.

```text
normalize_handle(raw):
    if raw is null: return MISSING
    s0 = exact_unicode_string(raw)
    codepoints = [U+....] for every character
    s1 = trim_unicode_edge_whitespace(s0)
    if s1 starts with ASCII "0x": s2 = s1 without that prefix
    else: s2 = s1
    reject internal whitespace
    reject empty or non-ASCII-hex characters
    return uppercase(s2), while preserving s0 and codepoints
```

NFKC로 핸들을 호환 정규화하지 않는다. 전각 문자나 유사 글리프가 ASCII 핸들로 합쳐지는 것을 막기 위해, 허용하지 않은 문자는 `PARSE_INVALID`로 둔다. 공백 변형은 선행·후행 공백만 제거하고 내부 공백은 실패시킨다. cp949 콘솔 렌더링은 데이터 판정에 쓰지 않으며 UTF-8 파일 바이트와 Unicode codepoint를 기준으로 비교한다.

해소 함수는 다음 총함수다.

```text
resolve(target_def_id, normalized_handle, optional_instance_path):
    candidates = handle_index.lookup(actual_schema_key_scope, normalized_handle)
    if candidates is empty: ABSENT_GLOBAL
    if candidates has more than one after the schema key is applied:
        AMBIGUOUS_DUPLICATE(candidates)

    e = the unique candidate
    if e.owner_def_id == target_def_id:
        ownership = DIRECT
    else if owner is reachable from target_def_id through one or more INSERT edges:
        ownership = NESTED
        paths = all acyclic instance paths that reach owner
        if optional_instance_path selects exactly one path: bind it
        else if len(paths) == 1: bind the sole path
        else: INSTANCE_PATH_REQUIRED(paths)
    else:
        ownership = OTHER_DEF

    return entity_id, raw_type, ownership, bound_path_or_failure
```

핸들별 1차 분류는 서로 배타적이다.

- `DIRECT_LINE`
- `DIRECT_NONLINE_<TYPE>`
- `NESTED_LINE_RESOLVED`
- `NESTED_LINE_INSTANCE_AMBIGUOUS`
- `NESTED_NONLINE_<TYPE>`
- `OTHER_DEF_LINE` / `OTHER_DEF_NONLINE_<TYPE>`
- `ABSENT_GLOBAL`
- `AMBIGUOUS_DUPLICATE`
- `PARSE_INVALID`
- `MISSING_CITATION`

이 분류와 별도로 `citation_scope_ok`, `entity_exists`, `type_is_line`, `instance_resolved` 불리언을 둔다. 하나의 거친 “invalid” 열만 두면 부재·비-LINE·중첩 계약 실패를 구별할 수 없기 때문이다.

### 2.4 핸들-공간 계약

향후 E1 인용 한 건의 최소 증거 레코드는 다음 형태다.

```json
{
  "drawing_id": "...",
  "target_def_id": "...",
  "target_def_name_raw": "...",
  "citation_source": {"jsonl_sha256": "...", "line_no": 0, "span": [0, 0]},
  "raw_handle": "...",
  "raw_codepoints": ["U+...."],
  "normalized_handle": "...",
  "resolved_entity_id": "... or null",
  "owner_def_id": "... or null",
  "ownership_class": "DIRECT|NESTED|OTHER_DEF|ABSENT|AMBIGUOUS",
  "entity_type_raw": "... or null",
  "entity_type_canonical": "... or null",
  "instance_path": ["insert_entity_id", "..."],
  "coordinate_frame": "def-local|root-expanded|unresolved",
  "transform_chain": ["..."],
  "unit_status": "VERIFIED|SUSPECT|UNKNOWN",
  "resolution_status": "...",
  "pairability_status": "..."
}
```

계약 불변식은 다음과 같다.

- `resolved_entity_id`가 있으면 그 원시 레코드와 입력 해시를 역추적할 수 있어야 한다.
- `NESTED` 엔티티의 root-expanded 좌표는 유일한 instance path 없이는 생성하지 않는다.
- `type_is_line=false`를 LINE으로 선형화하여 1차 감사 결과를 바꾸지 않는다. LWPOLYLINE/MLINE/ARC 정규화는 후속 CL-B의 몫이다.
- 단위가 `UNKNOWN`이면 mm 대역 적합성을 `false`로 쓰지 않고 `NOT_EVALUABLE`로 쓴다.
- 모든 실패는 행으로 남고 분모에서 조용히 빠지지 않는다.

### 2.5 top-20 재구성과 정렬 키 감사

선택 단계 자체가 감사 대상이다.

1. E1의 저장된 cohort/order를 읽어 `legacy_rank`로 보존한다.
2. `_score_divergence`의 정확한 구현 또는 원시 구성값을 찾는다. 패킷에 수식이 없으므로 차이의 절댓값 같은 임의 공식을 만들지 않는다.
3. 동일 구현을 별도 함수로 재계산하고 숫자 파싱을 명시적으로 고정한다. NaN·무한대·문자열 숫자는 별도 오류로 분류한다.
4. 1차 정렬 키는 재계산된 divergence 내림차순, 동률 키는 `drawing_id`, 안정적 `def_id`의 UTF-8 바이트 순으로 고정한다. 이름·엔티티 수·원시 행 순서를 동률 키로 쓰지 않는다.
5. 재계산 top-20과 legacy top-20의 집합·순서·동률 블록을 모두 비교한다.
6. exact 구현 또는 구성값이 없으면 `DIVERGENCE_REPRO_MISSING`으로 C0를 차단한다. 저장된 top-20은 참고 cohort로 감사할 수 있지만 “진짜 top-20”이라고 부르지 않는다.

대조군은 재계산 top-20을 제외한 E1-join 가능 정의에서 뽑는다. 각 정의의 선택 키를

\[
h_i=\mathrm{SHA256}(\text{seed}\,||\,\text{drawing\_id}\,||\,\text{def\_id})
\]

로 만들고 가장 작은 20개를 무복원 선택한다. 이는 런타임 RNG 구현 차이를 피하는 고정 시드 의사무작위 표본이다. 적격 정의가 부족하면 수를 채우려고 top-20을 재사용하지 않고 `CONTROL_UNDERSIZED`를 보고한다.

### 2.6 정의별 엔티티 히스토그램

각 선택 정의 (d)에 대해 두 히스토그램을 만든다.

\[
H^{direct}_{d,t}=\sum_{e}\mathbf{1}[owner(e)=d \land type(e)=t]
\]

\[
H^{expanded}_{d,t}=\sum_{(p,e)}\mathbf{1}[p\text{가 }d\text{에서 도달 가능한 acyclic instance path}\land type(e)=t].
\]

타입 (t)의 기본 열은 LINE, LWPOLYLINE, MLINE, ARC, INSERT, HATCH이며 나머지는 `OTHER_<RAW_TYPE>`로 보존한다. `direct`는 정의 레코드를 한 번 세고, `expanded`는 INSERT 인스턴스 multiplicity를 반영한다. 이 둘과 별도로 `unique_descendant_def`/`unique_descendant_entity` 수를 기록하여 같은 child definition의 반복 삽입과 실제 다양성을 구별한다.

재귀는 임의 depth cap으로 자르지 않는다. 현재 경로의 `def_id` 재방문을 cycle로 검출하고 `INSERT_CYCLE` 행을 남긴다. cycle 이후의 expanded count는 `LOWER_BOUND`로 표시하며 완전한 수처럼 보고하지 않는다.

### 2.7 중첩 깊이, 내부 기하량, bbox

루트 정의의 depth는 0, 루트가 직접 가진 INSERT가 참조하는 child definition은 depth 1로 둔다. 정의별로 다음을 산출한다.

- `max_acyclic_insert_depth`
- depth별 INSERT 인스턴스 수
- direct primitive 수
- instance-expanded primitive 수
- unique descendant primitive 수
- cycle 수와 미해소 child reference 수
- direct-local bbox와 root-expanded bbox

유한한 기하 bbox (B_e=(x^-_e,y^-_e,x^+_e,y^+_e))를 공통 좌표계에서 합집합하여

\[
B_d=\left(\min x^-_e,\min y^-_e,\max x^+_e,\max y^+_e\right),
\quad
D_d=\sqrt{(x^+-x^-)^2+(y^+-y^-)^2}
\]

를 얻는다. NaN, 무한대, 빈 정의, 0-area bbox는 각각 별도 상태다. INSERT 자체의 placeholder bbox와 child geometry bbox를 중복 합산하지 않는다. 어떤 것을 채택했는지 `bbox_basis`에 기록한다.

### 2.8 단위 계약과 10배 이탈 판정

좌표 크기만 보고 “미터 같다”라고 추측하는 것은 금지한다. 다음 세 레인을 분리한다.

1. **명시 unit metadata 레인:** 도면/IR의 선언 단위를 표준 unit-to-mm 표로 변환한다. detector가 raw coordinate를 mm로 가정했다면 변환 계수 (u_d)와 1의 차이를
   \[
   F_d=\max(u_d,1/u_d)
   \]
   로 둔다. (F_d\ge 10)이면 packet band에 따라 `UNIT_ASSUMPTION_VIOLATION`이다.
2. **INSERT scale 레인:** affine 선형부의 singular value를 기록하여 단위 변환과 인스턴스 확대/축소를 분리한다. 비균일 scale은 `NONUNIFORM_INSERT_SCALE`이며 자동으로 source unit 오류라고 부르지 않는다.
3. **bbox 분포 레인:** raw-assumed-mm와 metadata-converted-mm의 width/height/diagonal을 나란히 보고, top-20과 대조의 분포를 기술한다. metadata가 없으면 bbox만으로 단위 판정하지 않고 `UNIT_UNKNOWN`으로 둔다.

top-20의 단위 위반 비율은 unknown을 숨기지 않기 위해 구간으로 보고한다.

\[
p_{lower}=N_{flag}/20,\qquad
p_{upper}=(N_{flag}+N_{unknown})/20.
\]

`p_lower >= 0.30`이면 단위 보조가정 위반을 확정 플래그하여 P1에 주입한다. `p_upper < 0.30`이면 이 밴드에서는 위반 증거가 부족하다. 그 사이면 `INCONCLUSIVE_UNIT_COVERAGE`다. 이는 PASS/FAIL을 unknown 처리 방식으로 조작하지 않게 한다.

### 2.9 구조적 LINE 쌍가능성

해소된 LINE을 같은 root coordinate frame에 놓고, 서로 다른 LINE (i,j)에 대해 방향각을 π 주기로 정규화한다.

\[
\Delta\theta_{ij}=\min(|\theta_i-\theta_j|,\pi-|\theta_i-\theta_j|).
\]

종방향 투영 구간의 교집합 길이를 짧은 선 길이로 나눈 값을 (o_{ij}), 두 지지선의 수직거리를 (g_{ij})라 한다.

- `STRUCTURALLY_PAIRABLE`: Δθ가 기존 2° 허용 이내이고 (o_{ij}\ge0.5)이며 (g_{ij})가 유한하고 0보다 크다.
- `PAIRABLE_IN_MM_BAND`: 위 조건에 더해 unit status가 `VERIFIED`이고 변환된 (g_{ij})가 기존 50–400 mm 대역 안이다.
- `PAIRABLE_BUT_UNIT_UNKNOWN`: 구조 조건은 맞지만 mm 판정은 불가능하다.
- `NOT_PAIRABLE`: 완전한 후보 검색 후 구조 조건을 만족하는 peer가 없다.
- `NOT_EVALUABLE`: 인스턴스 경로, 좌표, cycle 때문에 완전 검색이 불가능하다.

최대 정의가 412,775 선분이라는 패킷 실측 때문에 모든 LINE 쌍의 이차 비교는 금지한다. 방향 bucket과 공간 index로 후보를 제한하되, 작은 fixture에서는 brute-force와 결과가 정확히 같은지 검증한다. fast_score를 후보 생성 가속에 쓸 수 있지만, 최종 판정 행에는 peer handle, 각도차, overlap, gap, unit status를 직접 남긴다.

### 2.10 1차 불일치 지표와 판정 격자

top-20 각 정의 안에서 인용 occurrence와 `(target_def_id, normalized_handle)` unique 단위를 모두 보고한다. 같은 핸들을 반복 나열하여 분모를 부풀릴 수 있으므로 **1차 밴드는 unique 단위**다.

1차 불량 집합 (B)는 다음이다.

- `ABSENT_GLOBAL`
- `OTHER_DEF_*`
- 모든 `*_NONLINE_*`
- `PARSE_INVALID`
- `AMBIGUOUS_DUPLICATE`
- `MISSING_CITATION`

`NESTED_LINE_RESOLVED`는 엔티티 실재/LINE 조건에는 성공하지만 direct handle-space 계약과는 별도로 `scope_mismatch`를 기록한다. `NESTED_LINE_INSTANCE_AMBIGUOUS`는 실재성에는 성공해도 쌍가능성에는 실패가 아니라 `NOT_EVALUABLE`이다.

\[
r_{bad}=|B|/|U_{top}|,
\qquad
r_{pair}=|\{u\in U_{top}:STRUCTURALLY\_PAIRABLE\}|/|U_{top}|.
\]

분모가 0이면 비율을 0으로 만들지 않고 `UNDEFINED_NO_CITATIONS`로 둔다.

- **O-A:** (r_{bad}\ge0.50). H0-M 생존 강화. crosscheck v0 해석은 자동 철회가 아니라 `RETRACT_CANDIDATE`가 되며 계약 기반 재계측 전에는 E1 서사를 사용하지 않는다.
- **O-B:** (r_{bad}\le0.10)이고 (r_{pair}>0.50). H0-M kill. 실재·타입·구조 면에서 E1 불일치는 계측 아티팩트만으로 설명되지 않는다.
- **O-MIXED:** 위 둘 다 아니다. 10–50% 사이를 사후 서사로 채우지 않는다. 실패 유형과 대조군을 보고한 뒤 계약 기반 재계측 1회만 허용한다.
- **O-BLOCKED:** selection lineage, 원시 JSONL, IR join, 또는 좌표 계약이 1차 분모를 신뢰할 수 없게 한다. 어느 가설도 살리거나 죽이지 않는다.

여기서 50%, 10%, 10배, 30%는 패킷의 prereg band다. `r_pair>0.50`은 패킷의 “다수”를 결과 전 연산화한 `PREREG_PROPOSED` 규칙이다.

### 2.11 블록명 토큰 상관

이름은 raw Unicode와 codepoint를 보존한 뒤 NFC, Latin casefold, 연속 공백 축약만 수행한다. 호환 정규화로 `*U###` 같은 CAD 이름을 다른 토큰과 합치지 않는다.

- 확인적 1차 토큰: 패킷에 명시된 `평면도`의 substring 존재 여부.
- 설명용 구조 토큰: anonymous-name 패턴, xref 표식. 이는 선택 편향을 설명하지만 벽 의미 양성 토큰으로 합치지 않는다.
- `벽`, `WALL`, `PLAN`, `FLOOR PLAN`, `평면` 등 확장 사전은 결과 전 별도 version으로 동결할 수 있으나 다중 비교 보정 후에도 탐색적으로 구분한다.

E1에 join 가능한 전체 정의를 1차 분석 우주로 사용하고, top-20+대조 20 결과를 선택 조건부 민감도 표로 별도 제시한다. 전체 E1 행이 없으면 40개만으로 모집단 상관을 주장하지 않는다.

토큰 (z_i\in\{0,1\}), wall likelihood (w_i)에 대해 median difference, rank-biserial effect, Spearman 계열 순위 연관을 기술하고, 정의 ID에 고정 hash seed를 적용한 label permutation으로 귀무분포를 만든다. 제안 α=0.05는 `PREREG_PROPOSED`이며 효과 방향·크기와 함께 보고한다. 한 도면의 정의 간 의존성 때문에 p-value를 외부 도면 일반화의 증거로 쓰지 않는다.

### 2.12 `n_h_ornith=10` 원시 출력 대조

후처리 전 원문을 대상으로 각 행에 다음을 기록한다.

- 프롬프트에 정확한 개수, 최대 개수, 예시 개수, JSON schema max-items 지시가 있는가.
- raw response의 handle-shaped token occurrence와 unique 수.
- 목록 번호의 최댓값, 문장 종료/코드펜스 종료 여부, 잘림 표식.
- 파서 전후 unique handle 수와 버려진 토큰 및 이유.
- 최종 `n_h_ornith`와 원시 수가 어떻게 연결되는가.

결정론적 분류는 다음과 같다.

- `INSTRUCTION_BOUND`: 프롬프트/schema가 열 개 또는 최대 열 개를 요구하고 출력이 그 경계를 따른다.
- `PARSER_CAP`: raw에는 열 개보다 많은 유효 토큰이 있으나 parser가 정확히 열 개만 보존한다.
- `TRANSPORT_TRUNCATION`: raw payload가 잘렸다는 직접 증거가 있다.
- `MODEL_ENUMERATION_ONLY`: 명시 cap 없이 raw가 정상 종료하며 정확히 열 개를 나열한다. 이것만으로 실제 벽 수가 열 개라는 뜻도, 아티팩트라는 뜻도 아니다.
- `NOT_TEN`, `RAW_MISSING`, `PROMPT_MISSING`, `AMBIGUOUS`.

정확히 열 개인 클러스터 중 `INSTRUCTION_BOUND ∪ PARSER_CAP ∪ TRANSPORT_TRUNCATION`이 제안 밴드 50% 이상이면 “나열/계측 아티팩트가 클러스터를 지배”한다고 판정한다. 원문이나 프롬프트가 없으면 이 비율의 unknown 구간을 함께 보고하고, 하한이 밴드를 넘지 않으면 확정하지 않는다.

### 2.13 전체 의사코드

```text
main(prereg, graph_ir, e1_jsonl):
    assert prereg.audit_id == "platt_P0"
    manifest = hash_and_describe_inputs(graph_ir, e1_jsonl, prereg)

    schema = validate_schema_without_outcome_aggregation()
    if required join/divergence fields missing:
        emit_blocked_reason_in_memory(); stop_before_claims

    defs, entities, inserts = stream_graph_ir(schema)
    handle_index = build_index_using_observed_key_scope(entities)
    insert_graph = build_definition_instance_graph(inserts)
    e1 = parse_raw_jsonl_preserving_line_and_span()

    legacy = recover_legacy_selection(e1)
    recomputed = recompute_exact_divergence_or_block(e1)
    top = stable_top_k(recomputed, 20)
    controls = sha256_sample(eligible_minus(top), 20, fixed_seed)

    for d in stable_sort(top + controls):
        direct_hist = count_direct_types(d)
        expanded = traverse_instances_acyclic(d)
        bbox = compute_local_and_expanded_bbox(d, expanded)
        unit = audit_units_without_magnitude_guess(d, bbox)

        for cited_handle in e1.citations(d):
            resolution = resolve(d, cited_handle, optional_path)
            pair = audit_pairability_if_evaluable(resolution, d)
            append_citation_evidence(resolution, pair)

        append_definition_evidence(d, direct_hist, expanded, bbox, unit)

    selection_result = compare_legacy_and_recomputed_rank()
    name_result = audit_name_tokens(all_joinable_e1_rows)
    ornith_result = audit_raw_ten_cluster(e1)
    outcome = apply_frozen_decision_lattice_only_if_gates_complete()

    workbook = render_evidence_grid_with_status_and_provenance()
    assert every_input_citation_has_exactly_one_terminal_status
    assert rerun_semantic_hash(workbook_without_run_timestamp) is identical
    return workbook, machine_readable_summary, decision_record
```

### 2.14 출력 스키마와 결정론

실제 감사 실행의 증거 xlsx는 평가 원칙에 따라 필수다. 최소 sheet는 `RUN_MANIFEST`, `PREREG`, `SELECTION_LINEAGE`, `DEF_SUMMARY`, `ENTITY_HIST`, `CITATION_RESOLUTION`, `INSERT_PATHS`, `BBOX_UNITS`, `PAIRABILITY`, `NAME_TOKEN`, `ORNITH_RAW`, `DECISION`, `ERRORS`다. 각 결론은 원시 행과 양방향으로 연결되어야 한다.

정렬은 모든 sheet에서 안정적 키로 고정하고, floating point 출력 precision을 고정하며, 현재 시각 같은 비결정적 필드는 semantic hash에서 제외한다. 같은 입력·prereg로 두 번 실행했을 때 행 내용, 분류, decision, semantic hash가 정확히 같지 않으면 감사기는 실패다.

## 3. 벽 과업 적응 설계

### 3.1 `1.dwg` 실도면축: P0의 1차 시험지

P0의 직접 대상은 384개 도면정의를 가진 `1.dwg` staged DXF의 Graph IR과 `reports/e1/` 원시 산출이다(`PACKET_OBSERVED`). 다음 연결을 만든다.

- E1 정의 키를 Graph IR의 안정적 `def_id`에 join한다. 이름은 join key가 아니라 진단 필드다.
- top-20과 고정 무작위 대조 20개에 동일한 entity/handle/INSERT/bbox 코드를 적용한다.
- 최대 정의가 412,775 선분이라는 병목 실측을 반영하여 streaming index와 후보 제한을 사용한다.
- v0 벽-제로 도면율이 0.682에서 0.2135로 바뀌었다는 기존 결과는 탐지기 출력의 변화일 뿐 핸들 참조의 정당성을 보장하지 않는다. 이 감사에서 재측정하지도, 새로운 수치로 갱신했다고 주장하지도 않는다.

이 축에서만 O-A/O-B 결정을 내린다. 엔티티 실재는 Graph IR이 truth source이고, 벽 의미 ground truth는 주장하지 않는다.

### 3.2 CubiCasa5k SEG-IR 벡터축: 독립 성적표를 오염시키지 않는 연결

패킷의 CubiCasa5k 성적은 외부 사람 라벨 기반의 별도 축이다. 5,000도면 전량 변환, train 4,200/val 400/test 400, 벽 선분율 약 11.8%, 탐지기 v1 val F1 0.2358, HistGradientBoosting val F1 0.517/AUC 0.9215는 모두 `PACKET_OBSERVED`다. P0는 이 값을 재평가하거나 개선하는 방법이 아니다.

연결 원칙은 다음과 같다.

- CubiCasa `segment_id`를 `(source_plan_id, element_id, edge_id, transform, label_provenance)` 형태의 참조 계약으로 표현할 수 있지만, 이를 DWG handle과 동일하다고 부르지 않는다.
- `cubicasa_ir`/`cubicasa_ml`은 P0의 primary import가 아니다. 공통 evidence schema와 ID invariant를 재사용하는 adapter만 둔다.
- val은 향후 계약 회귀검사에 사용할 수 있어도 test 400은 P0 때문에 열지 않는다. P0는 모델 선택을 하지 않으며 단발 test 원칙을 소비할 이유가 없다.
- O-A가 나오더라도 CubiCasa의 낮은 기하 탐지기 F1이나 GBDT 향상은 독립 실측으로 남는다. 죽는 것은 E1에 근거한 “실도면 의미 불일치” 서사이지 외부셋 성적이 아니다.
- O-B가 나오면 외부셋에서 이미 확인된 긴 평행 구조 FP와는 다른, 실도면 표현 커버리지 문제를 CL-B/CL-F에서 다룰 근거가 생긴다. P0 자체는 어떤 학습법도 선택하지 않는다.

### 3.3 FloorPlanCAD 래스터축: 직접 연결 불가를 명시

FloorPlanCAD는 래스터 5,308장과 벽 bbox/segmask가 있으나 벡터 SVG가 없다(`PACKET_OBSERVED`). 따라서 raw pixel에는 DWG handle의 실재성·소유권·중첩 정의라는 오라클이 없다.

- P0 결과를 FloorPlanCAD에 직접 “검증”했다고 주장하지 않는다.
- 향후 CL-G가 pixel-to-handle 역투영 exact harness를 통과한 경우에만 `raster_region_id ↔ vector_entity_instance_id` crosswalk를 같은 provenance 형식에 넣는다.
- 역투영 전에는 raster mask가 LINE handle을 증명하지 못하고, DWG handle이 raster 벽 의미를 증명하지도 못한다.
- 라이선스/권리 선결(PR-3)이 해결되기 전에는 이 축을 학습 arm으로 끌어오지 않는다.

### 3.4 합성 S/F/M 팩: 진리원이 아니라 코드 fixture

합성팩은 B1 충실도 FAIL이며 실도면 타입 혼재를 재현하지 못한다는 패킷 실측이 있다. 따라서 합성팩을 “실제 E1 정의의 벽 truth”로 쓰지 않는다. 다만 아주 작은 인공 Graph IR fixture는 다음 결정론적 코드 경로를 테스트하는 데 쓸 수 있다.

- 직접 LINE, 직접 LWPOLYLINE, 전역 부재 핸들.
- 한 단계/다단계 INSERT와 동일 child의 반복 인스턴스.
- cycle, 누락 child, 비균일 scale.
- 앞뒤 공백, 내부 공백, 전각 유사문자, cp949 콘솔 깨짐.
- 같은 이름의 서로 다른 `def_id`, 같은 raw handle의 스키마 범위 충돌.

이 fixture 성공은 감사 코드 정확성 증거이지 벽 탐지기 성능 증거가 아니다. PR-1 합성 벽 생성기 충실도 게이트와 분리한다.

### 3.5 E1.5 silver와 두 어휘 가문

E1.5 판정자 5기가 약 2개 어휘 가문으로 갈린다는 패킷 실측 때문에, ornith 한 계열의 반복 출력은 독립 표 다섯 개로 세지 않는다. P0는 판정자 다수결을 사용하지 않고 각 raw response를 계보별로 보존한다. 동일 prompt template/parser를 공유하는 행은 같은 instrumentation family로 표시한다.

`n_h_ornith=10`이 prompt/parser cap으로 판정되면 이는 silver 정확도 수치가 아니라 계측 독립성 위반이다. 반대로 cap 증거가 없더라도 Ornith의 벽 의미가 참이라는 결론은 나오지 않는다. 오직 “정확히 열 개” 클러스터의 생성 메커니즘 한 가지를 배제하거나 남긴다.

### 3.6 기존 0.236과 0.517 이후 P0가 추가하는 것

탐지기 v1의 CubiCasa val F1 0.2358과 GBDT val F1 0.517은 “학습이 기하 규칙보다 낫다”는 외부셋 개발 결과다. P0의 추가 가치는 성능 lift가 아니라 다음 네 가지다.

1. E1 실도면 서사의 측정 단위를 문자열에서 해소 가능한 entity instance로 바꾼다.
2. 비-LINE/중첩/단위 문제를 분리하여 CL-B의 정규화 범위를 실제 결함 유형에 맞춘다.
3. 이름 토큰을 통해 silver가 탐지기와 독립인 증거인지, 이름 prior를 쓰는 다른 계측기인지 진단한다.
4. O-A라면 고가 VLM/GNN/RL 실험을 E1 근거로 정당화하지 못하게 하고, O-B라면 계측 아티팩트 논쟁을 끝내 후속 실험을 좁힌다.

즉 P0의 성공 지표는 F1 상승이 아니라 잘못된 연구 분기를 조기에 제거하는 것이다.

## 4. 데이터·컴퓨트 요구

### 4.1 필요한 로컬 데이터

필수 데이터는 두 truth surface뿐이다.

- DWG Graph IR: 정의, 엔티티, INSERT 참조/변환, 좌표/bbox 구성 필드, 가능한 경우 source unit metadata.
- `reports/e1/`: 원시 JSONL, 원시 프롬프트 또는 template 식별자, raw response, 인용 handle, wall likelihood, divergence 재현 필드, 원래 선택 순서.

추가로 입력 파일 해시와 parser/code version을 얻을 수 있어야 한다. source unit metadata, raw prompt, exact divergence lineage가 없을 때의 결과는 각각 `UNKNOWN` 또는 해당 cell `BLOCKED`다. 빈칸을 외부 상식으로 채우지 않는다.

### 4.2 로컬 실행 계획

패킷의 compute plan은 로컬 CPU 1시간 미만, 스크립트 작성 반나절, GPU/LLM 0이다. 이를 hard budget으로 유지한다.

- **CPU:** JSONL streaming parse, entity index, INSERT graph traversal, bbox, handle join, permutation/요약.
- **RAM 64GB:** 전체 좌표를 복제하지 않는다. columnar/streaming index와 definition partition을 사용한다. 큰 정의의 pairability는 방향·공간 index로 후보만 materialize한다.
- **RTX 5070 Ti 16GB:** 사용하지 않는다. GPU가 결과를 바꿀 이유가 없고 결정론 검증 표면만 늘어난다.
- **LLM/API:** 사용하지 않는다. 기존 raw output만 읽는다.
- **병렬성:** 결과 재현을 위해 stable partition/reduction을 구현하기 전에는 단일 process가 기준이다. 최적화하더라도 최종 정렬과 reduction은 결정론적으로 고정한다.

실행이 budget을 넘으면 먼저 pairability 후보 생성과 expanded multiplicity 계산을 profile한다. 완전성을 버리고 PASS를 내지 말고, 미완 범위를 `LOWER_BOUND`/`NOT_EVALUABLE`로 표시한다.

### 4.3 DGX 계획

DGX Spark는 현재 unreachable이지만, reachable 여부와 무관하게 P0에는 사용하지 않는다. Ornith-35B 재질의, 임베딩, VLM 판정, GPU 가속은 모두 실험 정의 밖이다. DGX 계획은 명시적으로 **없음**이다. 원시 응답이 없다고 DGX에서 재생성하면 prompt/model/version 차이로 T4의 원본 계보를 대체하게 되므로 금지한다.

### 4.4 데이터 분할과 누출 방지

학습은 없지만 결과-기반 규칙 튜닝 누출은 가능하다. 따라서 다음 순서를 고정한다.

1. synthetic micro-fixture로 parser/graph/transform을 개발한다.
2. 실제 입력에는 schema-only 모드만 실행한다. 키 이름, 데이터 타입, 필수 필드 존재 여부만 보고 값·히스토그램·top cohort를 출력하지 않는다.
3. prereg와 코드 semantic hash를 동결한다.
4. top-20+대조 20을 한 번 실행한다.
5. 규칙 변경이 필요하면 원 실행을 보존하고 새 version은 탐색적으로 표시한다.

CubiCasa val/test, FloorPlanCAD 라벨, 합성팩 성능값은 P0 선택에 사용하지 않는다. 특히 CubiCasa test 400 단발 원칙을 소비하지 않는다.

### 4.5 저장·증거 요구

향후 실험 실행은 machine-readable summary와 증거 xlsx를 함께 내야 한다. 원시 DWG/JSONL을 복사해 새 truth source를 만들지 않고 hash/line span으로 참조한다. workbook의 각 집계 셀은 source rows로 drill-down 가능해야 한다. 실패 행도 `ERRORS` 및 해당 본표에 남긴다.

현재 패킷의 산출 계약은 이 Markdown 한 파일만 허용하므로, 이 도시예 작성 단계에서는 위 실행 산출물을 생성하지 않는다. 그것들은 별도 승인된 P0 실행의 계획 산출물이다.

## 5. 구현 계획

### 5.1 제안 파일 골격

아래는 향후 구현 시의 골격이며, 현재 도시예 실행에서 생성하는 파일 목록이 아니다.

```text
tools/
  e1_forensic_audit.py          # 단일 CLI, orchestration만
e1_forensics/
  schema_adapter.py             # IR/E1 명시적 필드 매핑, fail-closed
  provenance.py                 # byte hash, line/span, status vocabulary
  handle_contract.py            # normalize/resolve/classify
  insert_graph.py               # cycle-safe path와 transform chain
  geometry.py                   # bbox, common-frame LINE features
  pairability.py                # indexed candidates + brute-force oracle
  selection.py                  # exact divergence, stable top-k, hash control
  units.py                      # metadata conversion과 unknown interval
  name_tokens.py                # Unicode-safe token audit
  ornith_raw.py                 # prompt/raw/parser 대조
  decision.py                   # 동결된 O-A/O-B/O-MIXED/O-BLOCKED 격자
  evidence_writer.py            # evidence_grid/xlsx + JSON summary
prereg/
  platt_P0_v1.yaml
tests/
  fixtures/e1_forensics/*.jsonl
  test_handle_contract.py
  test_insert_graph.py
  test_pairability_equivalence.py
  test_selection_determinism.py
  test_unicode_and_encoding.py
  test_decision_boundaries.py
```

패킷의 “파이썬 스크립트 1개”는 사용자 진입점 하나를 뜻하게 유지한다. 내부 모듈은 테스트 가능성과 책임 분리를 위한 구현 세부다. 반나절 개발 예산을 지키기 위해 첫 버전은 위 책임을 한 패키지 안의 순수 함수로 구현하고, 필요 없는 프레임워크를 추가하지 않는다.

### 5.2 기존 도구 접속점

- **`evidence_grid`:** workbook sheet, provenance link, status, prereg/decision 표를 쓰는 유일한 보고 경로로 사용한다. evidence_grid가 실패하면 JSON만으로 PASS를 내지 않는다.
- **`fast_score`:** 구조적 pairability 후보 생성과 기존 2°/0.5/50–400 설정 재현에만 사용한다. 작은 정의에서 독립 brute-force oracle과 정확히 일치해야 한다. fast_score의 wall score를 entity truth로 쓰지 않는다.
- **`cubicasa_ir`:** stable segment identity와 좌표 provenance 설계를 참고하는 adapter boundary다. P0 primary run에서 CubiCasa 데이터를 읽지 않는다.
- **`cubicasa_ml`:** 학습/예측 코드는 호출하지 않는다. 향후 동일 evidence contract를 모델 오류 분석에 전달할 수 있도록 schema 이름만 호환한다.

실제 함수 signature와 필드 mapping은 repository surface를 확인한 뒤 정하되, 패킷에 없는 API를 이미 존재한다고 주장하지 않는다.

### 5.3 구현 순서

1. 상태 vocabulary, prereg schema, manifest/hash를 먼저 만든다.
2. synthetic fixture로 handle normalization과 실제 key scope 검증 인터페이스를 만든다.
3. INSERT graph, cycle, instance path, transform composition을 구현한다.
4. direct/expanded histogram과 bbox를 구현한다.
5. exact divergence selection과 고정 hash control을 구현한다.
6. citation resolution과 pairability를 연결한다.
7. unit/name/ornith 보조 감사를 연결한다.
8. decision lattice와 evidence workbook을 연결한다.
9. 같은 입력 두 번 실행의 semantic hash equality를 검증한다.

selection을 먼저 실행해 결과를 들여다본 뒤 분류 규칙을 만드는 순서는 금지한다.

### 5.4 결정론 테스트 매트릭스

최소 fixture는 다음 계약 위반을 각각 단독으로 재현해야 한다.

- 직접 LINE 존재/부재/비-LINE.
- 같은 raw handle이 실제 key scope에 따라 유일 또는 모호해지는 경우.
- 선행·후행 공백은 해소되지만 내부 공백은 실패하는 경우.
- 한글 블록명과 `*U###`가 콘솔 인코딩과 무관하게 같은 codepoint로 판정되는 경우.
- 직접 child, 다중 child, 동일 child 반복, 두 경로가 같은 nested entity에 닿는 경우.
- INSERT cycle과 누락 child.
- 회전·이동·uniform/nonuniform scale의 transform composition.
- unit metadata 있음/없음/상충.
- raw 12개인데 parser 10개, prompt가 최대 10개를 지시, raw 자체가 없는 경우.
- (r_{bad}=0.50), (r_{bad}=0.10), (r_{pair}=0.50), unit rate 0.30의 경계값.

여기서 fixture의 숫자는 알고리즘 경계 테스트용 `PREREG_PROPOSED` 예시이며 프로그램 실측이 아니다.

### 5.5 오류 처리와 관측 가능성

CLI exit status는 최소 `COMPLETE_DECISION`, `COMPLETE_INCONCLUSIVE`, `BLOCKED_INPUT_CONTRACT`, `FAILED_IMPLEMENTATION`을 구분한다. 다음을 금지한다.

- 누락 row를 drop하고 남은 행만 분모로 쓰기.
- Unicode decode replacement character를 원문으로 간주하기.
- 중첩 경로가 여러 개인데 첫 경로 선택하기.
- unknown unit을 mm로 가정하기.
- cycle에서 임의 depth까지 센 값을 완전 count로 표시하기.
- workbook 쓰기 실패 후 콘솔 요약을 최종 증거로 승격하기.

로그는 처리량보다 `def_id`, source line, failure code, affected decision cell을 우선 기록한다. 대용량 정의의 원시 엔티티 전체를 콘솔에 덤프하지 않는다.

### 5.6 예상 개발 규모와 완료 정의

패킷의 반나절 스크립트 작성 규모를 유지한다. 완료는 코드가 존재한다는 뜻이 아니라 다음이 모두 참인 상태다.

- prereg가 결과 전에 hash로 동결됨.
- exact top-20 lineage 또는 명시적 block가 있음.
- top-20+대조 20의 모든 인용이 terminal status를 가짐.
- direct/expanded hist, INSERT, bbox/unit, name, ornith sheet가 있음.
- evidence xlsx가 생성되고 source trace가 연결됨.
- 동일 입력 재실행 semantic hash가 동일함.
- decision은 O-A/O-B/O-MIXED/O-BLOCKED 중 정확히 하나임.

## 6. 실험 셀 정의

이 방법은 학습 셀이 아니라 계측 감사 셀이다. 개발은 synthetic micro-fixture에서만 하고, 실제 E1/IR은 prereg 동결 후 한 번 읽는다. 전체 로컬 실행 예산은 패킷대로 CPU 1시간 미만, GPU/LLM 0이다. 개별 셀 예산은 이 총량 안의 몫이며 독립적으로 합산해 새 예산을 만들지 않는다.

### C0 — 선택 lineage와 재현성 게이트

- **가설:** 저장된 E1 top-20이 exact `_score_divergence`의 안정 정렬 top-20과 일치하며, 이름/엔티티 수/원시 행 순서가 숨은 선택 키가 아니다.
- **지표:** legacy-vs-recomputed set/order, tie block, nonfinite/parse error, input/prereg/code hash, 2회 semantic hash.
- **제안 합격선:** top-20 집합 exact 일치, divergence 값 재현, 두 실행 decision/semantic hash exact 일치. 이는 확률 밴드가 아니라 결정론 계약이다.
- **킬 조건:** exact divergence를 재현할 수 없거나 cohort가 달라지면 legacy top-20 기반 확인적 해석을 kill한다. 새 cohort 감사는 가능하지만 prereg version과 별도 결과로 분리한다.
- **예산:** streaming sort와 hash; 총 CPU 예산의 작은 부분, GPU/LLM 0.
- **시드:** top-20에는 시드 없음. 대조군 seed 문자열은 `platt_P0/control/20260718/v1`로 고정.

### C1 — 핸들 실재·타입·소유권 감사(주 판별 셀)

- **가설:** H0-M 대 H1-C.
- **지표:** unique citation 기준 `r_bad`, occurrence 민감도, direct/nested/other/absent/ambiguous 분포, 타입별 분포, `r_pair`.
- **제안 합격선:** O-A는 `r_bad >= 0.50`; O-B는 `r_bad <= 0.10 AND r_pair > 0.50`; 그 외 O-MIXED. 패킷 밴드를 사후 변경하지 않는다.
- **킬 조건:** O-B면 H0-M kill. O-A면 “불일치는 실재하며 탐지기 개념 결함”이라는 E1 기반 전제를 kill하고 crosscheck v0를 `RETRACT_CANDIDATE`로 보낸다. join/분모가 불완전하면 양쪽 모두 kill하지 않고 O-BLOCKED.
- **예산:** 40개 정의의 handle index lookup 및 indexed pairability; 총 CPU 1시간 미만 안, GPU/LLM 0.
- **시드:** top-20 없음; 대조 20은 C0 고정 seed. 모든 tie는 stable key.

### C2 — 엔티티 표현·INSERT 구조 설명 셀

- **가설:** E1 극단의 불일치는 LINE-only 관측이 놓친 비-LINE 또는 nested geometry 농축으로 설명될 수 있다.
- **지표:** direct/expanded 타입 hist, max acyclic depth, direct/expanded/unique 내부 기하량, cycle, instance-path ambiguity, top-vs-control 차이.
- **제안 합격선:** 선택된 모든 정의가 완전 histogram 또는 명시적 lower-bound/error 상태를 가져야 한다. 메커니즘은 단일 사전 밴드로 억지 이분화하지 않고 C1 실패 유형을 설명할 때만 채택한다.
- **킬 조건:** top-20이 direct LINE 중심이고 nested/non-LINE 농축이 대조보다 설명력을 갖지 못하면 “표현 타입/중첩이 주원인” 설명을 kill한다. cycle/누락 참조가 결과 범위를 가리면 해당 메커니즘 판정은 blocked다.
- **예산:** definition graph 선형 순회와 instance-expanded count; multiplicity 폭발 시 symbolic count 사용, GPU 0.
- **시드:** 없음. traversal order는 `def_id`/INSERT entity stable key.

### C3 — bbox·단위 보조가정 셀

- **가설:** 기존 50–400 mm gap band가 Graph IR 좌표와 같은 단위라는 보조가정이 top-20에서 유지된다.
- **지표:** raw/converted bbox width-height-diagonal, explicit unit factor, INSERT scale singular values, `p_lower/p_upper` 단위 위반 구간.
- **제안 합격선:** `p_upper < 0.30`이면 패킷 밴드상 단위 위반 증거 부족. `p_lower >= 0.30`이면 위반 플래그. 사이 구간은 inconclusive.
- **킬 조건:** 하한이 30% 이상이면 mm 보조가정을 kill하고 P1의 상대/정박 단위 arm에 주입한다. metadata가 없어 bbox 크기만 있는 경우에는 가설을 살리지도 죽이지도 않는다.
- **예산:** bbox union과 metadata lookup, GPU/LLM 0.
- **시드:** 없음.

### C4 — 블록명 토큰 ↔ `wall_likelihood` 셀

- **가설:** H3 — `평면도` 토큰이 있는 정의에서 LLM wall likelihood의 순위/위치가 달라진다.
- **지표:** token prevalence, median difference, rank-biserial effect, Spearman 계열 연관, fixed permutation p, 전체 join 우주와 선택 cohort의 차이.
- **제안 합격선:** 1차 토큰은 방향이 일치하고 제안 α=0.05를 통과해야 이름-prior 방향 증거로 표시한다. 효과 크기와 원시 분포를 반드시 함께 보고한다.
- **킬 조건:** join 가능한 전체 우주에서 효과 방향이 없거나 permutation 기준을 통과하지 못하면 `평면도` 1차 H3를 kill한다. 이는 다른 미등록 토큰을 자동 승인하지 않는다.
- **예산:** scalar/vector 연산; CPU 예산 내, GPU/LLM 0.
- **시드:** 정의 ID hash 기반 permutation seed를 prereg에 고정. 추가 토큰은 Holm 계열 보정 또는 탐색 표시.

### C5 — `n_h_ornith=10` 원시 계보 셀

- **가설:** 정확히 열 개인 클러스터가 도면 내용보다 prompt/schema/parser/transport 제약에 의해 만들어졌다.
- **지표:** prompt cap, raw occurrence/unique count, parser 전후 차이, 목록 종료, truncation, instrumentation family, unknown interval.
- **제안 합격선:** exact-ten cluster에서 직접 입증된 `INSTRUCTION_BOUND ∪ PARSER_CAP ∪ TRANSPORT_TRUNCATION` 하한이 제안 50% 이상이면 나열 아티팩트 지배로 판정.
- **킬 조건:** raw와 prompt가 완전하고 직접 아티팩트 비율 상한도 50% 미만이면 “열 개 클러스터는 주로 나열 지시 산물” 가설을 kill한다. raw/prompt가 없으면 blocked이며 후처리 수만으로 통과시키지 않는다.
- **예산:** 기존 JSONL 원문 parse만, 신규 LLM 호출 0.
- **시드:** 없음.

### C6 — 통합 결정·재계측 라우팅 셀

- **가설:** C0–C5를 평균내지 않고도 선결 질문의 다음 행동을 단일 decision lattice로 정할 수 있다.
- **지표:** gate completeness, C1 O outcome, C3 unit flag, C4/C5 보조 설명, control contrast.
- **제안 합격선:** 정확히 하나의 terminal outcome과 근거 row link가 있고, unknown이 분모에서 빠지지 않으며, evidence xlsx가 존재한다.
- **킬 조건:** C0 또는 C1이 blocked면 통합 PASS/FAIL을 kill한다. O-A면 E1 서사 재계측으로, O-B면 CL-B 계열 커버리지 실험으로, O-MIXED면 계약 기반 재계측 1회로만 라우팅한다.
- **예산:** 규칙 평가와 workbook 생성, GPU/LLM 0.
- **시드:** 없음; C0–C5의 동결된 결과만 소비.

### val 개발 / test 단발 원칙의 적용

- **개발/val 역할:** synthetic micro-fixture와 작은 brute-force equivalence fixture만 사용한다. 실제 wall label이나 E1 outcome은 튜닝에 쓰지 않는다.
- **실제 감사 단발:** prereg hash 후 real top-20+control20을 한 번 실행한다. schema mismatch로 중단된 run은 결과를 보지 않았다는 log가 있을 때만 prereg 수정 후 재시도한다.
- **CubiCasa test:** 전혀 접촉하지 않는다. P0는 모델 비교 방법이 아니므로 test budget을 소비하지 않는다.
- **셔플 대조:** 학습 leakage shuffle 대신 C4의 token permutation과 고정 무작위 control cohort가 해당 역할을 한다. 기존 CubiCasa 셔플 AUC 0.375 PASS는 패킷의 별도 실측이며 P0가 재실행했다고 주장하지 않는다.
- **증거 xlsx:** 실제 P0 실행의 완료 조건이다. 실패도 사유와 함께 기록한다.

## 7. red team 티켓 응답

패널 보고서는 34개 티켓 전량이 OPEN이라고 명시한다. 이 도시예는 설계 응답을 제공할 뿐 티켓을 실행 완료로 닫지 않는다. 특히 패킷에 원문이 없는 티켓은 추측하지 않는다.

### T3 — `_score_divergence` 정렬 키 아티팩트 재계산

**응답: 설계상 직접 해소, 실행 전까지 OPEN.** C0에서 legacy order와 exact 함수 재계산 order를 분리하고, divergence 이외의 이름·크기·행 순서를 tie-break에서 제거한다. exact 함수/원시 구성값이 없으면 block한다. cohort가 달라지면 기존 top-20 해석을 무효화하고 새 cohort를 별도 prereg version으로만 감사한다. `*U###`/xref-bound 편중은 cohort metadata로 명시하여 선택이 만든 조건부 분포를 모집단처럼 말하지 않는다.

### T4 — ornith 원시 출력 조달과 `n_h_ornith=10` 아티팩트

**응답: 설계상 직접 해소, 원문 없으면 수용 불가/blocked.** raw prompt, raw response, parser 전후 token을 연결하는 C5를 둔다. 신규 Ornith 호출은 원시 증거를 대체하지 못하므로 금지한다. 원문이 없으면 “아티팩트 아님”도 “아티팩트임”도 판정하지 않는다.

### T8 — platt P0 개별 티켓

**응답: 원문 부재를 명시하고 OPEN 유지.** 패널은 T8–T33이 per-proposal 티켓이라고만 쓰며 T8의 문구를 이 패킷에 싣지 않았다. 자기완결 계약상 T8의 내용을 발명할 수 없다. P0 본문에 명시된 handle 실재성, entity hist, INSERT, bbox/unit, name token, ornith raw, selection 편향은 모두 설계에 반영했지만 이것을 T8의 공식 closure라고 부르지 않는다. 실제 티켓 원문이 제공될 때 현재 crosswalk에 추가하고, 현재 prereg와 충돌하면 새 version으로 명시해야 한다.

### T1 — truth proxy 독립성 감사

**응답: 부분 기여, OPEN 유지.** P0는 Graph IR의 결정론 사실과 silver 원시 인용 사이의 계측 의존성을 드러내고, 이름 prior와 shared prompt/parser family를 표시한다. 그러나 패널이 요구한 합성·외부셋·silver·metamorphic 간 동일-def 3원 불일치 구조 전체를 수행하지 않는다. 그 closure는 CL-E의 몫이다. P0 결과를 “proxy 독립성 입증”으로 과장하지 않는다.

### T2 — 실벽 합성 생성기 부재/충실도

**응답: P0 실행 비의존, 프로그램 위험 수용.** P0는 기존 Graph IR의 entity truth를 쓰므로 벽 합성 생성기가 없어도 실행 가능하다. synthetic micro-fixture는 코드 계약 테스트일 뿐 PR-1을 통과한 벽 truth라고 부르지 않는다. 따라서 T2를 닫지 않되 P0 선행을 막지도 않는다.

### T5 — 외부셋 라이선스·권리

**응답: P0 범위 밖, OPEN 유지.** P0는 FloorPlanCAD/CubiCasa 학습·라벨 재배포·원도면 사용을 요구하지 않는다. 외부셋 연결은 schema 경계 설명뿐이다. 향후 학습 arm에는 counsel 서면 확인이 여전히 선결이다.

### T6 — 평가 단위 혼동

**응답: P0 내부 해소, RL 프로그램 티켓은 OPEN.** P0의 1차 단위는 `(target_def_id, unique normalized cited handle)`이며 occurrence와 def-macro는 보조로 분리한다. instance path까지 계약에 포함한다. 이는 per-handle 대 집합-조립 혼동을 피하지만 RL 산출물 평가 단위 T6 전체를 닫지는 않는다.

### T7 — 0벽 sentinel 없는 metamorphic 랭킹

**응답: 본 실험에는 비적용, OPEN 유지.** P0는 metamorphic 위반율로 탐지기를 랭킹하지 않는다. “인용 0개”는 좋은 결과로 통과시키지 않고 C1 분모를 `UNDEFINED_NO_CITATIONS`로 block한다. CL-D의 0벽/전벽 sentinel 요구는 그대로 남는다.

### T34 — load-bearing 인용의 실행 상태

**응답: 상태 분리로 대응, OPEN 유지.** 이 문서의 방법론 문헌은 `LITERATURE_BACKGROUND`, 패킷 실측은 `PACKET_OBSERVED`, 제안 셀은 `PLANNED/PREREG_PROPOSED`로 표시한다. 어떤 문헌도 `experiment_executed:true`로 승격하지 않는다. 실제 P0 실행 후에도 로컬 evidence row만 `DETERMINISTIC_DERIVED`가 된다.

### 패킷에 명시된 예상 실패 모드에 대한 추가 응답

- **top-20 선택 편향:** C0 정렬 재계산, anonymous/xref 표식, 고정 무작위 20개, 조건부 해석으로 완화한다.
- **def-name 정규화 버그:** 이름을 join key로 쓰지 않고 raw/codepoint/NFC 파생값을 함께 보존한다. 공백 변형 fixture를 둔다.
- **cp949 콘솔 깨짐:** 콘솔 glyph가 아니라 입력 바이트와 Unicode codepoint로 판정한다. replacement character가 생기면 decode 실패다.
- **큰 정의의 후보 폭발:** 이차 전수 비교를 금지하고 indexed candidate + 작은 fixture brute-force 동치 검사를 둔다. 미완전하면 lower-bound이지 PASS가 아니다.
- **중첩 cycle/다중 인스턴스:** cycle-safe traversal과 instance-path-required 상태로 처리한다.

## 8. 인접 제안과의 관계

### 8.1 병합 가능한 지점

- **CL-B 커버리지-완전 결정론 v1:** P0의 비-LINE hist, nested path, unit flag를 받아 LWPOLYLINE/MLINE/ARC 정규화, INSERT 월드좌표 전개, 상대/절대 단위 arm의 우선순위를 정한다. 단, P0는 타입을 LINE으로 변환하지 않는다. 관찰과 수정을 분리한다.
- **CL-C 합성 truth/WSD-EVAL-v1:** handle-space contract와 evidence row schema를 합성 per-handle truth에도 재사용할 수 있다. 그러나 P0의 entity truth가 CL-C fidelity PASS에 의존하지는 않는다.
- **CL-D metamorphic 배터리:** instance path와 transform provenance는 rotate/translate/reflect/scale 후 동일 엔티티 대응을 만드는 기반이다. P0는 불변성 성능을 측정하지 않는다.
- **CL-E truth-source 교차요인:** P0의 same-def citation resolution과 instrumentation-family 표가 3원 불일치 구조의 한 축이 된다. proxy 독립성 결론은 CL-E에서만 낸다.
- **CL-I 관례-prior:** C4의 `평면도` 확인적 토큰과 raw/codepoint pipeline을 firm lexicon 연구로 확장할 수 있다. P0는 한 도면 상관을 firm 관례로 일반화하지 않는다.
- **CL-G 래스터/VLM:** exact pixel-to-handle crosswalk가 생긴 뒤에만 P0 계약의 raster provenance 필드를 확장한다. 그 전에는 직접 병합 불가다.
- **CL-F/CL-K 학습 arm:** P0가 O-B이고 계측이 건전할 때만 E1 불일치를 학습/anti-silver 비교의 근거로 쓸 수 있다. O-A면 E1 target을 그대로 증류하는 arm은 재계측 전 중단한다.

### 8.2 차별점

P0는 벽 검출 성능 실험, 새로운 truth proxy, 다수결 판정, representation 개선이 아니다. 그 어떤 방법보다 앞에서 “비교한 대상이 실제 같은 handle space에 있었는가”를 판정한다. 다음을 의도적으로 하지 않는다.

- LWPOLYLINE/MLINE/ARC를 LINE으로 변환하지 않는다.
- wall label을 새로 만들지 않는다.
- CubiCasa val/test를 다시 채점하지 않는다.
- Ornith나 frontier VLM을 재호출하지 않는다.
- 이름 토큰 상관을 벽 truth로 쓰지 않는다.
- bbox 크기만으로 단위를 추측하지 않는다.

이 좁은 범위가 dissolver의 힘이다. 원인을 고치는 실험과 원인이 실제인지 확인하는 감사를 섞지 않는다.

### 8.3 이 제안이 죽어야 하는 조건

“P0가 성공하면 영구 프로그램이 된다”는 설계를 피한다. 다음 조건에서 P0 또는 그 설명은 명시적으로 끝난다.

1. **O-B:** `r_bad <= 0.10`이고 실제 인용의 다수가 구조적으로 쌍가능 LINE이면 H0-M이 죽는다. 같은 forensic audit를 확대 반복하지 말고 CL-B/CL-E 등 커버리지·독립성 실험으로 넘어간다.
2. **O-A:** `r_bad >= 0.50`이면 E1 기반 “탐지기 개념 결함” 전제가 죽는다. crosscheck v0는 `RETRACT_CANDIDATE`가 되고, handle-space contract로 E1을 재계측하기 전 E1 서사에 기대는 고가 실험을 중단한다. 이 결과가 CubiCasa 성적이나 탐지기 전체를 좋다고 증명하지는 않는다.
3. **selection lineage 실패:** exact divergence가 재현되지 않거나 top-20이 바뀌면 기존 extreme-cohort 확인적 해석이 죽는다. 저장 cohort의 기술 감사만 남고 새 cohort는 별도 prereg 후 실행한다.
4. **truth surface 부재:** Graph IR과 raw E1 JSONL을 신뢰성 있게 join할 수 없으면 P0의 판정 가능성이 죽고 O-BLOCKED다. 파일이 없다는 사실을 O-A로 세지 않는다.
5. **핸들 유일성/instance path가 원천적으로 부족:** 벌거벗은 핸들이 여러 엔티티/인스턴스에 영구적으로 모호하면 기존 E1 계측기는 부적격이다. 더 정교한 추측 resolver를 만들지 말고 E1 출력 스키마를 계약 기반으로 다시 생성한다.
6. **O-MIXED:** 10–50% 회색대에서 보조 셀을 가중평균해 억지 결론을 내리지 않는다. 계약 기반 재계측을 한 번 수행한 뒤에도 혼합이면 P0가 최종 판별자라는 주장을 죽이고 CL-E의 독립 truth-source 설계로 넘긴다.
7. **비결정성:** 같은 입력·prereg로 semantic hash/decision이 재현되지 않으면 감사기 자체가 죽는다. 성능 최적화보다 먼저 원인을 고친다.

### 8.4 정직한 종료 규칙

P0가 내릴 수 있는 최종 문장은 네 개뿐이다.

- `O-A — E1 계측 아티팩트 H0-M 생존 강화; E1 서사 재계측 필요.`
- `O-B — 계측 아티팩트 H0-M kill; 실제 LINE/구조 불일치에 대한 후속 실험 정당화.`
- `O-MIXED — prereg 회색대; 계약 기반 재계측 1회 후 인접 제안으로 이관.`
- `O-BLOCKED — 입력/lineage/좌표 계약 불충분; 증거 없음.`

어느 문장도 “탐지기가 강하다/약하다”를 직접 판정하지 않는다. P0는 그 문장을 말할 수 있는 계측 조건이 갖추어졌는지만 판정한다. 이것이 뒤의 고가 실험을 살리거나 죽일 수 있는 최저비용 dissolver라는 제안의 정확한 범위다.

DOSSIER_COMPLETE: platt_P0
