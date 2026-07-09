# 잔여 클러스터 조치 계획 (RESIDUE_ACTION_PLAN)

> ## 집행 현황 (2026-07-09 갱신 — 아래 원분석은 R4h 기준 사료로 보존)
>
> - **조치 1 (*D 측정 계약) — 집행 완료.** `blockdef_diff.py` `exclude_derived_caches=True` 기본값
>   (`^\*D\d+$` 제외 + `totals.derived_cache_excluded` 정직 계정, `--include-derived-caches` 옵트아웃).
>   R4l 재폴드 실측 26779/27130=0.987062, 래칫 0.948→**0.985** 인상. 커밋 "*D measurement contract".
> - **조치 2 (HATCH) — 대부분 집행 완료.** `.pat` 합성 4결함 사슬 수리(과학표기·스케일 베이킹·line-local
>   좌표·appendLoop 소유권)로 R4l에서 해치 249 실재. 잔여 표현차(스케일 베이킹 표현·pattern_type
>   1↔2·%.10g 노이즈)는 `_canonical_hatch_geometry`로 정준화(+8, 0.987357). **실잔여**: 경계-쌍 22쌍 중
>   per-hatch pattern origin 위상차 21건(재생측 setOriginPoint 재현 실험 대기) + is_associative 5건(정직 잔차).
> - **조치 4 (WIPEOUT) — 집행 완료, 보류 철회.** "증명된 경로 없음"은 반전된 `loadModule bool==eOk`
>   게이트의 가짜 실패였음(acismobj26.dbx는 정상 로드). 라이브 인증: append→appended:true, census
>   재추출 기하 완전 일치(clip 11점/u/v/origin). `blocks.py` 방출 복원 — R4m부터 유예 31→0 기대.
> - **조치 3 (mismatch_decomposition) — 부분 대체.** 경계-쌍 매칭 분석이 해치 잔여를 필드 수준까지 분해
>   완료. 범용 도구는 잔여가 실질 소진된 뒤 가성비 재평가.
> - **신규**: L5 게이트 2종 라이브(치수 113/113=1.0 + block topology 290/290 defs·711/711 edges) +
>   IPSS 유죄 스위트(5 변조: naive PASS ∧ 의미게이트 유죄 5/5).

> 근거: `reports/interior100/residue_clusters_R4h.md`(랭킹 클러스터) · `reports/interior100/blockdef_diff_R4h.json`(per_def 원자료, 520 rows) · `docs/EXPERIMENT_DESIGNS_V2.md` §3 P7잔여(L91~100) · 코드 직독(`tools/blockdef_diff.py`, `tools/residue_cluster.py`, `tools/ir_to_patch.py`, `tools/patch_ops/blocks.py`, `tools/patch_ops/entities.py`, `src/Ariadne.AcadNative/AriadneNativeJob.cpp` 경유 `docs/ANON_DEF_CAPTURE_DESIGN.md`, `docs/HATCH_APPEND_DESIGN.md`) + 기존 유닛테스트(`tests/unit/test_anon_remap.py`).
> 원칙: 모든 수치는 `reports/interior100/blockdef_diff_R4h.json`의 `totals`/`per_def`를 재계산한 값이거나 인용 코드 라인에서 직접 도출. 인용 없는 추정은 UNKNOWN으로 표기.

## 0. 총계 (원문 인용)

`blockdef_diff_R4h.json.totals`: `a_def_count=407, b_def_count=403, a_entity_total=28183, b_entity_total=27952, diff0_total=26775, interior_diff0_fraction=0.9500408047404464`.
`residue_clusters_R4h.md`: `residual_defs=268, residual_entities=2538` (7개 클러스터, `tools/residue_cluster.py`의 `classify_family`+`count_bucket` 서명으로 그룹화).

검증: 7개 클러스터 defs/entities 합 = 131+95+12+13+1+13+3=268 / 1328+855+250+41+33+26+5=2538 — `residue_clusters_R4h.md` 표와 정확히 일치 (재계산 명령: 위 파이썬 합산, 본 세션에서 직접 실행·확인).

| 클러스터 | defs | entities | entities/28183 |
|---|---|---|---|
| anon_dimension/10-99 | 131 | 1328 | 4.712% |
| anon_dimension/1-9 | 95 | 855 | 3.034% |
| dynamic_instance/10-99 | 12 | 250 | 0.887% |
| dynamic_instance/1-9 | 13 | 41 | 0.145% |
| named/10-99 | 1 | 33 | 0.117% |
| anon_other/1-9 | 13 | 26 | 0.092% |
| named/1-9 | 3 | 5 | 0.018% |

---

## 조치 1 (최우선) — `anon_dimension` 클러스터 통합 (2183 entities = 7.746%, 잔여의 86%)

### 근거가 되는 per_def 행 (원문 인용)

- a_only shape (95+18=113 defs, `missing_side="b"`, `b_name` 필드 존재): 예) `{"name":"*D295","a_total":9,"b_total":0,"removed":9,"missing_side":"b","b_name":"ARIADNE_ANON_D295"}`. 즉 name_map이 `*D295→ARIADNE_ANON_D295`로 정확히 매핑됐지만, b측 IR의 `block_definitions`에 `ARIADNE_ANON_D295`라는 이름의 def가 **전혀 존재하지 않음**.
- b_only shape (113 defs, `missing_side="a"`, `b_name` 없음): 예) `{"name":"*D287","a_total":0,"b_total":10,"added":10,"missing_side":"a"}`. a측에 대응 없이 b측에서만 `*D287`(원시 `*`-prefix, 리맵 안 된 이름)로 새로 나타남.
- 두 그룹 모두 113개로 **정확히 같은 개수** — a-only 113 + b-only 113 = 226개 def가 실제로는 같은 113개 dimension 객체의 두 얼굴일 가능성.

### 기계적 원인 (코드 직독으로 확인)

1. `src/Ariadne.AcadNative/AriadneNativeJob.cpp`의 `blockTableRecordsJson(...)` — `pBTR->isAnonymous()`는 "dynamic-block snapshots (`*U###`)와 dimension defs (`*D###`)"를 **동일하게** 취급 (`docs/ANON_DEF_CAPTURE_DESIGN.md` L25 원문 인용). 즉 파이프라인이 `*D`를 `*U`와 구분 없이 "클론 가능한 익명 블록"으로 분류.
2. `tools/ir_to_patch.py:build_patch_from_ir()` L219-238 — 블록 정의 합성(`_emit_block_def`)은 **오직** `ir.get("entities")`에 `geometry.kind=="block_reference"`인 최상위 엔티티가 그 이름을 참조할 때만 트리거된다 (L224 `if kind == "block_reference":`). DIMENSION 엔티티는 `geometry.kind=="dimension"`이며 `*D<n>` 블록을 이런 방식으로 참조하지 않는다(그 참조는 DIMENSION 엔티티 자신의 내부 필드이고, IR에는 별도 block_reference로 노출되지 않음).
   → 결론: `ARIADNE_ANON_D<n>` create_block op은 **애초에 생성 코드 경로 자체를 타지 않는다**(디퍼된 것도 아니고, 시도됐다가 실패한 것도 아님 — 트리거 조건이 성립하지 않음).
3. b측에서 나타나는 113개 raw `*D<n>` 신규 def(각 평균 10 entities)는 우리가 만든 것이 아니라, DIMENSION 엔티티를 재생성할 때 AutoCAD가 **자체적으로** 생성하는 내부 캐시 블록이다. 그 근거: 같은 R4h 런의 최상위 census verdict(`reports/interior100/R4h_summary.json.verdict.rows`, `dxf_name=DIMENSION`)에서 `regen_attempted_count=113, diff0_count=113, removed=0, added=0, modified=0` — **실제 DIMENSION 엔티티 자체는 100% 완전 일치**. 즉 치수 형상은 이미 온전히 복원됐고, `*D` def-이름 비교만 구조적으로 성립하지 않는 것.
4. `by_kind_gap.solid = {a_count:0, b_count:226}` — b측에만 나타나는 226개 SOLID(226/113≈2개/블록, 화살표 쐐기 전형적 개수)는 AutoCAD가 자동 생성한 `*D<n>` 블록 내부의 화살표 형상으로 해석된다(원본 a측 `*D` 블록에는 SOLID가 0개 — 원본 dimstyle의 화살표 표현 방식이 다름을 시사, `docs/EXPERIMENT_DESIGNS_V2.md` P5 "dimstyle이 왕" L87과 정합).

### 결론

`*D`(익명 dimension 블록) def-이름 비교는 **반증 가능하지 않은 불변식**이다 — AutoCAD가 파일을 열 때마다 `*D` 번호를 새로 배정하므로 a/b가 같은 이름으로 매칭될 수 없다. 이미 `docs/EXPERIMENT_DESIGNS_V2.md` N5(치수-기하 정합 게이트, L159-161)가 올바른 오라클로 설계되어 있음 — "카운트 diff가 못 잡는 조용한 기하 드리프트를 의미층에서 잡는 가장 싼 게이트"이자 def-이름이 아닌 DIMENSION 엔티티 값 vs defpoint 실거리로 비교.

### 구체적 수정 (file:function)

- `tools/blockdef_diff.py:diff_block_definitions()` (L111) — L125 `for name in sorted(defs_a):` 루프와 L174 b_only 트레일링 루프 진입 전에 `*D`-family(정규식 `^\*D\d+$` 및 그 name_map 타깃 `^ARIADNE_ANON_D\d+$`) 필터를 추가해 두 쪽 모두에서 스킵. 대신 `totals`에 새 필드 `anon_dimension_excluded: {"defs": N, "a_entities": M}` 추가 — VACUOUS≠PASS 원칙(`EXPERIMENT_DESIGNS_V2.md` 법칙 3) 준수, 조용히 사라지지 않고 명시적으로 보고.
- `tests/unit/test_blockdef_diff.py`에 회귀 테스트 추가: `*D1`/`ARIADNE_ANON_D1` 조합이 `diff_block_definitions(..., name_map=...)` 결과의 `per_def`에서 제외되고 `totals.anon_dimension_excluded`에 집계되는지 확인 (기존 `test_blockdef_diff_without_name_map_stays_name_sensitive` 패턴 재사용).
- `tools/residue_cluster.py`는 코드 변경 불필요 — 입력 JSON에서 `*D` 행이 사라지므로 `anon_dimension` 클러스터는 자연히 소멸. `render_markdown()`에 `anon_dimension_excluded` 안내 줄만 추가(선택, S).

### 기대 게인 (산술)

- 요청된 단순 산식: `2183 / 28183 = 0.07746` (7.746 pp) — 이 클러스터가 현재 잔여 계산에서 차지하는 몫.
- 정밀 재계산(측정 교정, 콘텐츠 복구 아님을 명시): `a_entity_total`에서 a-only 113개 행의 `a_total` 합(855+198=1053)만 제외 — `diff0_total`은 불변(26775, 이 행들은 원래 diff0=0이었으므로). 새 분수 = `26775 / (28183-1053) = 26775 / 27130 = 0.986915` → 현재 0.950041 대비 **+0.0369** (측정 교정, 실측 재현: 본 세션 파이썬 재계산).
- 주의: 이것은 "복원된 엔티티"가 아니라 "비교 불가능한 항을 분모/분자에서 제거"하는 정직한 교정이다 — DIMENSION 엔티티 자체는 이미 diff0=113으로 완전 일치했으므로 실질적 형상 손실은 0이다.

### 디스패치 패킷 스펙

- **files**: `tools/blockdef_diff.py`, `tests/unit/test_blockdef_diff.py`, `reports/interior100/blockdef_diff_R4i.json`(재생성 산출물), `reports/interior100/residue_clusters_R4i.md`(재생성 산출물).
- **CHANGE_ONLY**: 위 2개 소스 파일 + 신규 리포트 산출물 경로.
- **PROTECTED_PATHS**: `*.dwg` 원본, `src/Ariadne.AcadNative/**`(이 패킷은 native 미변경).
- **testCmd**: `python -m pytest tests/unit/test_blockdef_diff.py tests/unit/test_residue_cluster.py -q`
- **재생성 검증**: `python tools/blockdef_diff.py <census_ir> <post_ir> --out-json reports/interior100/blockdef_diff_R4i.json` → `python tools/residue_cluster.py reports/interior100/blockdef_diff_R4i.json --out reports/interior100/residue_clusters_R4i.md` → `anon_dimension` 클러스터 부재 + `totals.anon_dimension_excluded.defs==113` 확인.
- **비용**: S (순수 파이썬 측정 로직, DWG 쓰기 경로 무변경 — 리스크 최저).

---

## 조치 2 — HATCH 커스텀 패턴 잔여 (교차-클러스터, `dynamic_instance`/`named`/`anon_other`에 분산 추정)

### 근거

- `by_kind_gap.hatch = {a_count:265, b_count:16}` — 249개 HATCH가 a→b에서 소실.
- `tools/patch_ops/blocks.py` L304 `_def_entity_append_reason()`, L398-408 (entities.py 대응 분기) — `_is_custom_hatch_pattern()`(L269) 참인 패턴 이름에 `pattern_definitions`가 없으면 `_CUSTOM_HATCH_DEFER_REASON`("custom hatch pattern replay pending .pat synthesis")으로 디퍼. 코드 주석이 명시적으로 인용: "measured: H3 x181, H1 x1 on 1.dwg (R4f b157)" — **이 파일**에서 커스텀 패턴 `H3`(181회) · `H1`(1회) = 182건이 R4f 시점에 실측됨.
- `docs/HATCH_APPEND_DESIGN.md` "패턴 정의선 추출" 절 — `.pat` 합성·`setPattern(kCustomDefined,...)` 재생 경로는 **이미 구현되어 있음**(`tools/patch_engine.py`가 배치당 `.pat` 파일 합성). 디퍼 조건은 오직 `pattern_definitions`가 비어있을 때만 발동(`_has_hatch_pattern_definitions()` L274).

### UNKNOWN (추측 금지)

- R4f 실측(H3×181, H1×1=182)이 R4h의 현재 249 손실을 정확히 설명하는지 미확인 — R4h용 census/post IR에서 hatch별 `pattern_name`·`pattern_definitions` 유무를 직접 재집계해야 함(본 세션에서 미실행: JSON에 kind별 breakdown이 per_def에 없어 `blockdef_diff_R4h.json`만으로는 판별 불가).
- `pattern_definitions`가 애초에 비는 이유가 (a) native 추출 누락(`numPatternDefinitions()==0`으로 보고되는 극단 케이스) 인지 (b) 이미 있는데 python 게이팅 로직이 놓치는 코드 버그인지 미확정 — 조치 전 반드시 확인.

### 구체적 수정 (조사 우선, file:function)

1. **조사 패킷** (코드 변경 없음): R4h `post_ir`(재구축측 dwg_graph_ir.json)에서 `pattern_name in {"H3","H1"}`인 hatch 항목을 열거해 `pattern_definitions` 유무·`is_gradient`·loop edge type을 집계 → `reports/interior100/hatch_census_R4h.json`.
2. 조사 결과가 (a) native 미캡처면 → `src/Ariadne.AcadNative/AriadneNativeJob.cpp`의 hatch 추출 지점(`docs/HATCH_APPEND_DESIGN.md` "Native extract contract" 절이 지목하는 `numPatternDefinitions()`/`getPatternDefinitionAt` 호출부) 확인·보강.
3. 조사 결과가 (b) python 게이팅 버그면 → `tools/patch_ops/blocks.py:_is_custom_hatch_pattern()`(L269) / `_has_hatch_pattern_definitions()`(L274) 수정.

### 기대 게인 (산술)

- 상한 추정: `249 / 28183 = 0.00883` (0.883 pp) — 모든 249개 HATCH가 매칭 가능해질 경우(diff0_total만 증가, denominator 불변이므로 anon_dimension 교정과 달리 순수 "회복"형 게인).
- R4f 실측 기준 하한 추정: `182 / 28183 = 0.00646` (0.646 pp, H3+H1만).

### 디스패치 패킷 스펙

- **files (조사 단계)**: 신규 `tools/hatch_census.py`(census_ir/post_ir 비교 스크립트, 소규모) 또는 기존 `tools/xdata_census.py` 패턴 재사용, 출력 `reports/interior100/hatch_census_R4h.json`.
- **files (수정 단계, 조사 결과 의존)**: `src/Ariadne.AcadNative/AriadneNativeJob.cpp` 또는 `tools/patch_ops/blocks.py` — 조사 결과 나오기 전 확정 불가.
- **testCmd**: `python -m pytest tests/unit/test_hatch_append.py tests/unit/test_hatch_patdef_extract.py tests/unit/test_hatch_edge_loops.py -q` (기존 3개 hatch 테스트 스위트 — 회귀 없음 확인 후 신규 케이스 추가).
- **비용**: 조사 S, 수정 S(python 게이팅)~M(native 추출 보강 시 재빌드 필요).

---

## 조치 3 — `mismatch_decomposition` 도구 신규 구축 (P7잔여, 사전 필요 인프라)

### 근거

`docs/EXPERIMENT_DESIGNS_V2.md` §3 "P7 잔여 — 불일치 분해" (L91-100)에 이미 설계되어 있음: `tools/mismatch_decomposition.py` — modified 행을 `(kind × 최초불일치필드 × delta-bin × anon여부)`로 클러스터링(min_freq=5, consistency, contrast_sharpness 통계 게이트), naive-foil 내장. §5 실행 순서표(L170)에서 우선순위 2위로 이미 랭크됨("잔여 anon 1.1k 소진의 엔진").

### 왜 지금 필요한가 (조치 1·2로 안 닫히는 잔여)

- `dynamic_instance/10-99`(250 entities, 예: `X-평면도(기본형)$0$111a` a_total=639/b_total=616/removed=23)와 `dynamic_instance/1-9`의 `mutated` 4건(예: `X-평면도(기본형)$0$hd1050` modified=5) — 이들은 이름이 정상 매칭(`missing_side=null`)되는 **진짜 콘텐츠 차이**이나, `blockdef_diff.py`의 per_def 행에는 kind breakdown이 없어(`residue_cluster.py:dominant_kind()`의 docstring이 이를 명시: "현재 generator는 kind breakdown을 emit하지 않음") 어떤 entity kind가 빠졌는지 이 리포트만으로 확정 불가.
- `by_kind_gap.block_reference = {a:1183, b:956}`(227개 net 손실) — `tools/ir_to_patch.py` L195-206 "nested block_reference append skipped: target ... not synthesized (anonymous/missing/cycle)" 디퍼 경로가 후보 메커니즘이나, 어떤 부모 def에 몇 건씩 귀속되는지는 UNKNOWN — 현재 산출물로는 추적 불가.
- `named/10-99`(`X-평면도(기본형)` 자체, removed=5/modified=28) — 부모 다이나믹 블록의 원본 정의 자체에 28개 modified가 있으나 원인 kind 미상.

### 구체적 구축 (file:function, 신규)

- 신규 `tools/mismatch_decomposition.py` — 입력: `blockdef_diff_R4h.json` 대신 **kind-aware** per-entity diff(즉 `cad_diff.compute_diff`가 이미 내부적으로 갖고 있는 entity-level modified/added/removed 목록, `tools/blockdef_diff.py:diff_block_definitions()` L144 `cad_diff.compute_diff(...)` 호출 결과의 `diff["details"]`류 — 현재는 `summary`만 per_def에 반영되고 세부 목록은 버려짐)를 **보존**하도록 `blockdef_diff.py`에 옵션 `--emit-entity-diff`를 추가해 세부 kind/필드 목록을 사이드카 JSON으로 남기는 선행 변경이 필요.
- 이후 `mismatch_decomposition.py`가 그 사이드카를 `(kind, first_mismatch_field, delta_bin, is_anon)` 서명으로 클러스터링 → `reports/interior100/mismatch_clusters.json`.

### 기대 게인

직접 게인 없음(진단 도구) — 이 도구가 밝히는 `dynamic_instance`+`named`+`anon_other`의 나머지 잔여 = `2538-2183(anon_dim)-249~182(hatch 상한~하한)` ≈ `106~173 / 28183` = `0.38%~0.61%`. 정확한 분해 없이는 이 구간을 더 좁힐 수 없음(UNKNOWN, 추측 금지).

### 디스패치 패킷 스펙

- **files**: `tools/blockdef_diff.py`(`--emit-entity-diff` 옵션 추가, 기존 함수 시그니처에 additive), 신규 `tools/mismatch_decomposition.py`, 신규 `tests/unit/test_mismatch_decomposition.py`.
- **testCmd**: `python -m pytest tests/unit/test_mismatch_decomposition.py tests/unit/test_blockdef_diff.py -q`
- **비용**: S(도구) — `EXPERIMENT_DESIGNS_V2.md`가 이미 "비용: 도구 S, 클러스터별 수리 S~M each"로 산정.

---

## 조치 4 (보류 권고) — WIPEOUT 33개 (0.117%)

`by_kind_gap.wipeout={a:33,b:0}` 전량 소실. `docs/HATCH_APPEND_DESIGN.md` L9,17: "No native append path wired for block definitions" — `AcDbWipeout::append(AcDbObjectId&)`에는 `AcDbBlockTableRecord*` 타깃 인자가 없어 블록 정의 내부에 headless로 구성하는 **증명된 경로가 없음**. 최근 커밋 `083e7e5`("wipeout emission reverted to honest deferral: native builder does not exist")로 이미 정직하게 디퍼됨 — 이는 버그가 아니라 현재 SDK 경계에서의 정직한 한계다.
**게인/비용**: 33/28183=0.117%에 대해 native ObjectARX 신규 구성 경로 필요(비용 L, 미증명) — **가성비 최저, 지금 착수 비권고**. `EXPERIMENT_DESIGNS_V2.md` 백트래킹 트리거("proven wipeout-in-block construction sequence 발견 시")가 성립할 때까지 현 상태(honest deferral) 유지가 정답.

---

## 랭킹 (gain/cost)

| 순위 | 조치 | entities | gain(pp) | 비용 | 근거 확실성 |
|---|---|---|---|---|---|
| 1 | anon_dimension 제외(측정 교정) | 2183 | +3.69pp(정밀) / 7.75pp(단순식) | S | 코드로 완전 확인 |
| 2 | HATCH 커스텀 패턴 | ≤249 | ≤0.88pp | S(조사)~M(수정) | R4f 실측 부분 인용, R4h 재확인 필요 |
| 3 | mismatch_decomposition 구축 | 진단 전용 | 0(직접), 106~173 잔여 해명 | S | 이미 설계됨(P7), 미구축 |
| 보류 | WIPEOUT | 33 | ≤0.12pp | L | 이미 정직 디퍼, 착수 비권고 |

---

## 3줄 요약

1. 잔여 2538 entities의 86%(2183, anon_dimension)는 실제 형상 손실이 아니라 `*D` 익명 dimension 블록을 이름으로 비교하는 것 자체가 성립할 수 없는 측정 오류다 — DIMENSION 엔티티 자체는 census verdict에서 이미 diff0=113/removed=0로 완전 일치했다.
2. `tools/blockdef_diff.py`에서 `*D`-family를 비교 대상에서 명시적으로 제외(VACUOUS로 보고)하면 interior fraction이 0.9500→0.9869로 즉시 정정되며, 이는 DWG 쓰기 경로를 전혀 건드리지 않는 최저 리스크·최고 게인 조치다.
3. 나머지 355 entities는 HATCH 커스텀 패턴(최대 249, 이미 절반 이상 구현된 `.pat` 재생 경로의 잔여 게이트 조건 문제)과 미분해 콘텐츠 차이(block_reference −227 등, kind breakdown 부재로 UNKNOWN)로 나뉘며, 후자는 이미 설계된 `P7잔여 mismatch_decomposition` 도구 구축이 선행되어야 정확히 귀속시킬 수 있다.
