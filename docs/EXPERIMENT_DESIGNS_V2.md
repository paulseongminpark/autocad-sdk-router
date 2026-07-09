# EXPERIMENT_DESIGNS_V2 — 미진행 실험 설계·강화 (원문 직독 기반)

> 작성: 2026-07-09, Paul 지시 "처음부터 끝까지 원문 직독하고, 지금 진행중이지 않은 실험들에 대한 실험 설계 및 강화" 집행.
> 전신: `docs/ROUNDTRIP_100_PLAN_TREE.md` (P1~P10 트리). 이 문서는 그 중 **미진행 가지(P4·P5·P7잔여·P9·P10)** 를 원문 근거로 재설계하고, 원문이 실제로 말하는 **신규 분기 5개(N1~N5)** 를 추가한다.
> 규율: 모든 주장에 원문 출처 병기(FM9). 설계는 v1 초안 → 자기비판 → v2 재설계 2회전, 회전 흔적을 §2에 남긴다.

---

## 0. 원문 직독 범위 (읽은 것, 정직하게)

증류본(reports/alm_synthesis/01~05)이 아니라 아래 **원문**을 직독했다:

| 원문 | 분량 | 직독 범위 |
|---|---|---|
| `D:\dev\_ariadne\alm\docs\perplexity_nemotron3ultra_v1.md` | 682KB / 17,524줄 | 전체 헤딩 구조 + 개념 밀도 구간 전문: §11 설계결정 10 (L2617~), 구현원칙 (L2650~), SHACL 한국건축법 셰이프 (L1131~1264), 4축 진단 (L2180~), 3-Graph 패턴·이벤트소싱·동기화 정책 (L3363~3435), SHACL 파이프라인·auto-fix 경계 (L3438~3496), Validation-First 철학 (L5606~), 계층별 검증 매트릭스 V-L0~V-PL (L6023~6058), 골든셋 3축 설계·카테고리 최소케이스 (L7555~7607), 골든셋 성장 루프 (L8312~), 섭동 분류체계 (L8368~8394), 커널 드리프트 매트릭스 (L9719~9736), 에지케이스 분류학 (L10516~10550), 드리프트 메트릭 분류 (L12601~12626), 3단계 복구 아키텍처 (L11665~11701). 코드 스켈레톤 본문(전체의 ~70%)은 구조만 확인 |
| `1단계 - Probe(탐사) 설계 설명.md` | 6.5KB | 전문 |
| `1단계 - IR 생성기 (C# 하이브리드) 설계 노트.md` | 5.7KB | 전문 |
| `2단계 - 의미 복원 (입법·분류·관계·보정) 설계 노트.md` | 9.6KB | 전문 |
| `2단계 심화 - 번역기·부트스트랩·golden 설계 노트.md` | 9.5KB | 전문 |
| `3단계 - 변경 반응 (…) 심화 설계 노트.md` | 39.5KB | 전문 |
| `4단계 - 규칙 성장 공장(공장2) 하이브리드 심화 설계 노트.md` | 22.5KB | 전문 |
| `5단계 - 확장 (profile·객체종류·라이브러리화) 심화 설계 노트.md` | 13.3KB | 전문 |
| `ALM_V5_SCRIBE_DESIGN.md` + `ALM_V5_SCRIBE_DATA_GAPS.md` | 17.7KB | 전문 |
| `probe-findings.md`, `p1-findings.md`, `p3-findings.md`, `p6-findings.md`, `EXPERIMENT_CONCLUSION.md` | 17.4KB | 전문 |
| `ALM_v0.3_y_VALIDATION_ORACLES_METRICS_CALIBRATION.md` | 85.6KB / 2,313줄 | 전체 헤딩 + Thesis·Research Anchors·Internal Basis (L31~124), unknown_rate/fail_loud_rate/evidence_adequacy (L225~248), yc 크로스SDK·yd 캘리브레이션 (L344~435), Oracle Ladder O0~O8 전문 (L529~612), Y-004 OOD·Y-005 Change Oracle (L812~863) |
| 룰팩 `centerline_rulepack_v1_1` (원문 디렉토리) | 51규칙+스키마 | `ontology.yaml`·`CENTERLINE_DRAWING_RULES_v1_1.md`·`xdata_schema.yaml`·`scoring/confidence_score.yaml`·`V-002` 전문 + 4팩 전체 파일트리 (`centerline_rulepack_v1_bygpt`·`clear_dimension_rulepack_v1`·`CLEAR_DIMENSION_DRAWING_RULES_v1` 구조 확인) |
| GPT-web `CAD_AI_READY_INFRA...0617_PKG` (97파일) | — | `methodology/00_EXPERIMENT_METHOD`·`01_GOLD_CANARY_SET_DESIGN`·`03_ABLATION_STUDY_PLAN`·`configs/quality_gates.yaml`·`docs/04_VALIDATION_DESIGN`·`docs/02_BUILDING_EVIDENCE_GRAPH_IR`·`packets/routes/dwg_truth_autocad.md` 전문 |

미직독(정직): `cad_gnn_production_experiment_pack_PKG`·`ALM_V4_PRODUCTION_DESIGN_PACKAGE_PKG` 내부, `안목치수` 리서치 4편(85+50+36+34KB), v0.3_y의 메트릭 구현 상세·체크리스트 58개, 퍼플렉시티 코드 스켈레톤 본문. 이들은 본 설계의 2차 입력으로 남긴다.

---

## 1. 원문이 입법하는 것 — 이번 미션에 직접 구속되는 법칙 12

1. **rebuild-sufficiency**: 복원은 원본을 안 본다(커닝 금지); diff=0이 LOCK 조건. 라운드트립은 generic IR엔 강력, **domain IR(의미·관계)엔 무력** — 의미 검증은 별도 오라클 필수. `[1단계 IR노트 §복원원리·§주의]`
2. **Probe 우선**: "안 보여서 못 적는" 누락은 스키마 확정 전 전수 카탈로그로 예방. RotatedDimension이 default bucket으로 빠졌던 실사례. `[Probe노트 §1, probe-findings §5]`
3. **VACUOUS ≠ PASS**: 적용 0건 규칙은 별도 분류, 4단계의 원료. `[3단계 §3.8, 4단계 §9]`
4. **naive-foil**: 규칙이 naive 대조군보다 실제로 나은지 코드로 증명 (naive PASS & smart FAIL 대조). `[3단계 §3.5]`
5. **통제 4장치**: 순환차단(calibrated conf 필터) · 통계게이트(빈도·일관성·대조선명도) · 통합심사(merge/absorb/escalate/generalize) · 교차도면검증(발견≠검증, FP율>0.1 reject). `[4단계 §1~5]`
6. **confidence는 주장**: calibration으로만 정직화; raw LLM confidence로 게이트 금지. `[4단계 §6, v0.3_yd]`
7. **Oracle Ladder O0~O8**: 후보는 증거가 쌓일수록 사다리를 오르고, auto-accept는 계약별 최소 오라클 레벨 필요, 미달이면 **Unknown** (강제 라벨 금지). `[v0.3_y L529~612, Y-004]`
8. **3-Graph 승격**: proposal(Working) → validation → trusted 승격만 허용; LLM/에이전트가 trusted를 직접 오염 금지. `[perplexity L3363~3386]`
9. **골든셋 3축 성장**: production failure(무제한 영구추가) + coverage-driven(카테고리별 최소) + adversarial. 실패 1건 = 골든 1건 = 영원한 회귀 방지. `[perplexity L7557~7607, L8312~8334]`
10. **금지 목록도 게이트다**: 구조정보 없이 내력벽·법적경계·안목치수 확정 금지 — 게이트는 "한 것"뿐 아니라 "주장하지 말아야 할 것을 주장 안 했는지"도 검사. `[CENTERLINE_RULES_v1_1 §9, SCRIBE §7]`
11. **provenance 의무**: 생성 산출물은 source_rule_ids·confidence·review_status를 XDATA로 지참. `[rulepack xdata_schema.yaml, CENTERLINE_RULES_v1_1 §8]`
12. **n=1 경계**: 같은 도면·같은 프로젝트 반복은 수확체감; 결과는 single-case existence proof로 표기. `[SCRIBE §7, EXPERIMENT_CONCLUSION §4~5]`

현 위치 대응(실측): capstone 게이트 체인 = O0(census 앵커) + O1(라운드트립 diff) + O2 부분(ezdxf 카운트 교차) + O4 부분(GEN3 고정점). **O5(그래프 제약)·O3(합성 의미 진리)·O6(변경 오라클)·O7(골든 홀드아웃)이 비어 있다** — 아래 설계가 이 빈칸을 채운다.

---

## 2. 설계 회전 흔적 (v1 초안 → 자기비판 → v2)

**v1 초안 요지**: P4=xdata blob 복사+diff, P5=테이블 레코드 전사, P7=수동 눈검사 연장, P9=글로벌 래칫 유지+도면 추가, P10=룰팩 51규칙 전부 실행해 분류 정확도 게이트.

**자기비판 (원문 대조로 발견한 결함 5)**:
- **C1**: P10 v1은 과설계+불가능. 구조도·마감두께 부재로 S5 확정과 auto 밴드(≥80)는 구조적 공집합 `[GAPS §B, SCRIBE §7]`. 분류 *정확도*는 golden 없이는 측정 불가 `[2단계 §2 "라운드트립 안 통함"]`. → v2: 게이트를 "분류가 맞는가"에서 "**재구축이 의미 추출 결과를 보존하는가**"(metamorphic, O4)로 재정의. golden 불필요, 결정론.
- **C2**: P4 v1은 xdata를 불투명 blob으로 취급 — **1005 그룹코드는 핸들 참조**라 재구축 도면에서 전부 dangling이 된다. 익명블록 name_map 교훈(정준화에 리맵 주입)의 정확한 일반화가 필요. `[BEG-IR raw_entity handle 계약, v0.3_yc failure mode "handle identity mismatch"]`
- **C3**: P5 v1은 linetype **정의 로딩**을 누락 — 빈 시드 DWG엔 CENTER/HIDDEN 대시 패턴이 없다. R4f의 H3 `.pat` 사건과 동형(`setPattern es=3`) → `.lin` 합성/로딩 + fail-loud가 필요. `[rulepack linetype_standard.yaml + R4f 실측]`
- **C4**: P9 v1의 글로벌 래칫 바닥 하나(0.948)는 도면이 늘면 즉시 깨진다 — 바닥은 **canary별**로 귀속되어야 하고, 레지스트리는 버전드·CI-게이트드. `[perplexity 골든 레지스트리 L7730~, gold canary "never silently modified"]`
- **C5**: P7 v1(눈검사)은 공장2가 금지하는 방식 — 실패는 **서명 클러스터링(빈도·일관성·대조선명도)** 을 거쳐야 패턴이고, 1~2건은 우연으로 버린다. `[4단계 §2.1~2.2]`

v2는 아래 §3~§4. 각 실험: 목적 · 상태함수(L1~L5 어느 층) · 성공기준(실측) · 구현 경로 · 백트래킹 트리거 · 비용(T-shirt).

---

## 3. 미진행 실험 재설계 (P4·P5·P7잔여·P9·P10)

### P4 — XDATA 재생 (provenance 채널 왕복)

**재프레임**: xdata는 부가 충실도가 아니라 **ALM이 입법한 provenance 운반 채널**이다 — 룰팩이 생성 중심선에 XDATA(app=CENTERLINE_RULEPACK, source_rule_ids, confidence, review_status)를 의무화한다 `[xdata_schema.yaml]`. 왕복이 xdata를 보존 못 하면 미래의 모든 의미 계층 산출물이 왕복에서 증발한다.

- **목적**: (증명) 1.dwg의 xdata 전 종을 IR→재구축 왕복에서 보존. (반증가능) 1005 핸들 참조가 리맵 불가능한 고아를 갖는가.
- **상태함수**: L3에 새 축 `xdata_diff0_fraction` 추가 (섹션 커버리지의 형제).
- **P4a 센서스 (Probe 규율)**: 추출기에 RegApp 테이블 + per-entity resbuf 체인 열거 추가. 그룹코드 분류(1000 str/1001 app/1002 brace/1003 layer참조/1004 bin/1005 **handle참조**/1010~1013 pt/1040~ real/1070~ int). 산출: `reports/interior100/xdata_census.json` — app별·코드별·엔티티종별 빈도. **성공기준**: 미지 그룹코드 0, 전 엔티티 스캔 (Probe §2 "존재 신호 전수").
- **P4b 재생**: ① 시드에 RegAppTableRecord 등록 ② patch job entity에 `xdata` 필드 verbatim 전달 ③ native append 후 `setXData` ④ **1005는 old→new 핸들맵으로 리맵** (anon name_map과 동열의 정준화 주입; 맵 부재 핸들은 fail-loud defer, 조용한 드롭 금지) ⑤ blockdef_diff `_canonical_entity`에 xdata 비교 추가(1005는 리맵 인지).
- **백트래킹**: setXData가 특정 kind에서 eNotApplicable → kind별 격리 후 정직 defer; 1005 고아율 >5% → 원본 자체의 dangling 여부를 먼저 census로 판정(데이터→스키마→코드 순 진단 `[07_FAILURE_DIAGNOSIS: model 우선 변경 금지]`).
- **비용**: M (census S + replay M). 게이트 편입: interior_gate와 동형 래칫(`xdata_gate`), 초기 바닥은 P4a 실측 후 설정 (수치 선하드코딩 금지).

### P5 — 심볼테이블 완성 (layers·linetypes·textstyles·dimstyles + 참조 무결성)

**재프레임**: dwg_truth 라우트의 요구 산출물이 원래 `layer_table.json`·`block_table.json`·`layout_table.json` `[dwg_truth_autocad.md BUNDLE]` — 블록만 하고 나머지 테이블을 안 한 상태. 그리고 룰팩 출력 계약(CENTER linetype, A-WALL-CENTER-* 레이어)은 **테이블 레코드가 실존해야** 성립한다 `[layer_standard.yaml, linetype_standard.yaml]`.

- **목적**: (증명) 시드 재구축이 원본의 심볼테이블(레이어 속성 포함)을 재생하고, 모든 엔티티→테이블 참조가 해소됨. (반증가능) dimstyle ~70 변수 중 재생 불가 변수 존재 여부.
- **상태함수**: L3 (`table_diff0` per-table) + **L1' 참조 무결성** (엔티티 layer/linetype/style 이름 → 테이블 존재 = 그래프 제약의 최소형, P10a와 공유).
- **경로**: ① 테이블 센서스(레이어: color/linetype/lineweight/plot/frozen/locked; linetype: 대시 패턴 배열; textstyle: font/oblique; dimstyle: 전 DIMVAR) ② 시드에 레코드 생성 op (`write.table.*` 계열 — cad.run_operation allow-list 경유) ③ **`.lin` 합성**: 커스텀 linetype은 `.pat`와 동일 패턴(배치 dir 합성→로드→실패 시 `LTYPE_UNRESOLVED` fail-loud, CONTINUOUS 폴백 금지) ④ 테이블 단위 canonical diff.
- **우선순위 내부 순서**: dimstyle이 왕(중심선도의 70%가 DIMENSION `[probe-findings §2, p1-findings §1]` — 치수 외형·값 표기가 dimstyle에 의존) → layer → linetype → textstyle.
- **백트래킹**: DIMVAR 중 headless 미지원 발견 → 해당 변수만 정직 주석 defer; 참조 무결성 위반이 원본에 이미 존재(원본 dangling) → 게이트 기준을 "원본과 동률"로 (원본보다 나빠지지 않음).
- **비용**: M~L (dimstyle이 L 요인).

### P7 잔여 — 불일치 분해 (공장2 통계 게이트 적용)

**재프레임**: 잔여 anon ~1.1k modified + (R4h 후 잔여) deferred를 눈검사가 아니라 **FailurePattern 클러스터링**으로 분해한다 `[4단계 §2.1: signature = rule×관계×변경종류×수치bin, min_freq=5·consistency·contrast_sharpness]`.

- **목적**: (증명) 모든 modified/deferred 행이 이름 있는 클러스터에 귀속. (반증) "기타" >5%면 서명 축이 부족한 것.
- **상태함수**: L2 (내부 재현율의 잔여를 소진하는 엔진).
- **경로**: `tools/mismatch_decomposition.py` — blockdef_diff 산출의 modified 행을 (kind × 최초불일치필드 × delta-bin[정확0/1e-9~1e-6/1e-6~1e-3/큼] × anon여부)로 클러스터 → 빈도·일관성 산출 → `reports/interior100/mismatch_clusters.json` + 상위 N 클러스터를 함대 패킷 1:1로 발사. **에지케이스 분류학을 bin 사전으로 재사용** (중복 제어점·노트 다중도 초과·근접 노트·극단 가중치·영길이 에지 `[perplexity L10516~10550]`) — spline 잔여가 NURBS 특이 bin에 떨어질 가능성 높음.
- **naive-foil 내장**: 카운트-only 비교(naive)와 정준 필드 비교(smart)를 같은 데이터에 동시 실행해 대조 선명도를 기록 — "카운트는 맞는데 내용이 틀린" 클래스를 상시 노출 `[3단계 §3.5]`.
- **백트래킹**: 클러스터가 측정층 버그로 판명(fit-표현 비대칭 같은) → 코드 수정은 측정층만, 인증 게이트(cad_diff) 불변 원칙 유지.
- **비용**: 도구 S, 클러스터별 수리 S~M each.

### P9 — 코퍼스 일반화 (설계 강화; 실행은 Paul 도면 대기)

**재프레임**: "다음 도면"을 임시 확장이 아니라 **골든 canary 레지스트리의 성장**으로 받는다 `[01_GOLD_CANARY, perplexity 골든 레지스트리]`.

- **목적**: (증명) 파이프라인이 1.dwg 특이 사항에 과적합되지 않음 — 발견 도면≠검증 도면 `[4단계 §5]`. (반증) 새 도면에서 재현율 급락 시 어느 축(추출/저작/측정) 붕괴인지 4축 진단으로 분리 `[perplexity §8]`.
- **상태함수**: 전 층 — canary별 L1~L5 스코어카드.
- **구조 (지금 만들 수 있는 것, 도면 불필요)**:
  1. `corpus/registry.json` — canary 케이스 스키마: {id, sha256, source(수령일·출처), category[coverage축], 기대 스코어카드, ratchet_floors{interior, xdata, table...}, never_silently_modified}. **래칫 바닥을 per-canary로 이관** (현 global 0.948은 1.dwg 케이스의 바닥으로 귀속).
  2. **coverage-driven 위시리스트** (Paul에게 다음 도면 요청 시 제시): xref 있는 DWG / paper space 레이아웃 사용 / 곡선벽 / proxy entity / 3D 솔리드 포함 / 다른 프로젝트(레이어 관행 상이 — n=1 탈출은 cross-project만 `[SCRIBE §7]`) / 유닛 상이(inch) `[01_GOLD_CANARY 포함케이스 목록]`.
  3. **adversarial 축은 도면 없이 지금 생성 가능**: 1.dwg IR에 통제 섭동(N1)·구조 변형(블록 중첩 깊이 증가, 빈 블록, 순환 참조 시도)을 가한 파생 canary — 원본 불변, IR 레벨에서만.
  4. 오염 방지: canary는 튜닝에 사용 금지, threshold 조정은 문서화된 경우만 `[01_GOLD_CANARY contamination]`.
- **성공기준**: 신규 도면 1장을 레지스트리 등록→capstone 실행→스코어카드 산출까지 **코드 0줄 수정** (5단계 "확장은 분리의 배당금" 검증 `[5단계 §6.1]`). 코드 수정이 필요하면 그 지점이 분리 실패 지점.
- **비용**: 레지스트리 S, per-canary 실행 M.

### P10 — 의미 게이트 (L5) — 최우선 강화

**재프레임 (C1 반영)**: golden 없이 분류 정확도를 재려는 시도를 폐기. 대신 3-서브게이트:

**P10a — 그래프 제약 게이트 (O5, 결정론)**
- **목적**: "불가능한 승인 그래프"를 차단 `[v0.3_y O5]`. 왕복 산출 IR에 대해: ① 참조 무결성(INSERT→blockdef, entity→layer/linetype/style, dimension defpoint 존재) ② hatch 루프 폐합·자기교차 없음(하프에지 twin 불변식의 2D 최소형 `[perplexity §2.1: "닫힌 loop 없음 오류를 L1 불변식 위반으로 조기 차단"]`) ③ 치수 앵커율(defpoint가 기하 좌표에 tol 내 접촉하는 비율 — A와 B'에서 **동률**이어야; 절대 기준 아님).
- **상태함수**: L5 첫 셀. 산출: `graph_constraint_gate` {ok/blocked/**vacuous**} — 적용 0건 축은 vacuous로 별도 보고 `[3단계 H6]`.
- **성공기준**: A(원본 IR)와 B'(재구축 IR)의 제약 위반 집합이 동일(원본에 이미 있는 위반은 보존이 정답 — "원본보다 나빠지지 않음" 게이트).
- **백트래킹**: hatch 루프 검사가 대량 위반을 원본에서 검출 → 게이트 실패가 아니라 **발견**으로 보고(수치가 발견 `[SCRIBE §5]`).
- **비용**: M.

**P10b — 의미 보존 게이트 (O4 metamorphic, 결정론)**
- **목적**: 재구축이 **의미 추출기의 출력을 보존**하는가. 분류가 맞는지는 안 물음(golden 없음) — 같은 결정론 추출기 f에 대해 f(A) ≟ f(B')를 물음. 이는 metamorphic oracle의 정확한 적용 `[v0.3_y O4: "known transformations preserve semantics"; 왕복 = 항등변환]`.
- **추출기 사다리 (가벼운 것부터)**: ① per-layer×kind 분포 ② WCD-001-lite: 평행선쌍·두께범위·중첩길이 조건의 벽후보 수 `[CENTERLINE_RULES_v1_1 §5.1]` ③ evidence score 분포(±0 허용) `[동 §6]`. LLM 사용 0 (3단계 결정론 원칙).
- **성공기준**: 벽후보 수·score 히스토그램 f(A)=f(B') 정확 일치(결정론이므로 tol 불필요; 불일치 = 기하 드리프트의 의미적 증폭 검출).
- **naive-foil 의무**: count-only 게이트(naive)와 동시 실행 — "엔티티 수는 같은데 벽후보가 줄어드는" 변이를 합성해 smart만 잡음을 증명 `[3단계 §3.5, 4단계 §11-4]`.
- **게이트 자체의 검증 (O3 합성 진리)**: 우리는 write 경로가 있으므로 **알려진 의미의 합성 장면을 저작**할 수 있다 — 벽쌍 N개를 파라메트릭 저작 → f가 정확히 N 검출해야; 한 면 삭제 변이 → N-1 검출해야 `[v0.3_yb synthetic truth: "generator parameters가 곧 GT"]`. 이것이 게이트의 단위테스트다.
- **비용**: M.

**P10c — provenance 게이트 (P4 의존)**
- **목적**: 에이전트가 **쓴** 모든 엔티티가 xdata provenance(app·source_rule_ids·confidence·review_status)를 지참 `[xdata_schema.yaml]` + **금지 주장 부재 검사**: 구조정보 없이 confirmed 딱지 없음 (`A-WALL-CENTER-CONFIRMED` 레이어 산출 금지 등) `[CENTERLINE_RULES_v1_1 §9~10]`.
- **성공기준**: 쓰기 산출물 provenance 100% + 금지 위반 0. **비용**: S (P4b 후).

---

## 4. 신규 분기 (원문이 실제로 말하는 것만; 발명 없음)

### N1 — 섭동 강건성 스위트 (Perturbation Suite)
- **근거**: 섭동 분류체계 — Coordinate Jitter ±1e-9~1e-6(수치 불안정 탐지), Topology-Preserving(제어점/노트 ±1e-8 상대), Adversarial `[perplexity L8368~8394]`.
- **설계**: census IR 좌표에 통제 지터 주입 → 패치→재구축→측정 → (a) 파이프라인이 크래시 없이 완주 (b) 정준 diff가 지터 크기에 **비례**해 열화(절벽 없음 = tolerance cliff 부재) (c) GEN 고정점이 지터 하에서도 수렴. **왜 중요**: 우리 게이트들이 tolerance 경계의 운으로 PASS했을 가능성을 반증하는 유일한 방법. 상태함수: L4 확장(고정점의 강건성). **성공기준**: 지터 1e-9에서 diff0 유지, 1e-6에서 열화가 단조·유계. **백트래킹**: 절벽 발견 → 정준화 tol의 명시화·문서화(자동 확대 금지 — 허용오차 확대마다 NULL 재실행 규율 `[SCRIBE §5 통제]`). **비용**: S~M.

### N2 — 크로스엔진 기하 표본 합의 (O2 승격)
- **근거**: "기하 값의 진실은 SDK 하나가 아니라 상호 검증에서 온다"; 현 cross_verify는 카운트 비교 = O2의 최약형 `[v0.3_yc: canonical signature + sampled geometry 비교]`.
- **설계**: kind별 무작위 N 엔티티의 좌표 시그니처(quantized hash)를 accoreconsole 추출 vs ezdxf(DXF export)로 대조. 카운트 일치·좌표 불일치 클래스를 신설 검출. **성공기준**: kind별 표본 합의율 report + 불일치는 issue로 기록(조용한 덮어쓰기 금지 `[04_VALIDATION_DESIGN cross-source]`). **비용**: S.

### N3 — 실패→골든 자동 편입 루프
- **근거**: "모든 프로덕션 버그 = 골든 케이스, 무제한 영구 추가" + 성장 루프 `[perplexity L7594, L8312~8334]`.
- **설계**: 이번 아크의 결함 4종(spline knots 미전달·seed_line +1·jsonFindString "x"·fit 비대칭)+H3 패턴 사건을 각각 최소 재현 fixture로 `tests/golden/` 레지스트리화(이미 tests에 산재 — **인덱스 파일**로 승격: id·발견일·증상·수리 커밋·재현 테스트 경로). 이후 모든 신규 결함은 수리 커밋에 골든 등록을 동반(게이트: 골든 없는 결함 수리 커밋 금지). **비용**: S.

### N4 — Δ-라운드트립 (변경 오라클 O6의 최소형)
- **근거**: 3단계 detect 합성 4시나리오(무변경→changes=[] / 1개 이동 / 1개 삭제 / GUID 제거 후 지문 매칭) `[3단계 §1.5]` + Y-005 Change Oracle "synthetic before/after → 정확한 ChangeSet" `[v0.3_y L838~863]`.
- **설계**: 1.dwg IR에서 합성 after(블록 INSERT 1개를 +1500 이동)를 만들고 → 우리의 census diff가 **정확히 그 1건만** modified로 보고하는가(무변경 엔티티 0건 오염). 이는 diff 파이프라인의 특이도(specificity) 증명이자 3단계(변경반응)로 가는 첫 다리. handle 기반 identity가 있으므로 3단 매칭 중 1단이 공짜 — 지문 매칭(2단)은 handle 제거 변형으로 별도 시험. **성공기준**: 4시나리오 전부 정확 (detect 신뢰 기준선 `[3단계 §1.5 "이 4개가 PASS면 detect 기본 신뢰"]`). **비용**: M.

### N5 — 치수-기하 정합 게이트 (value_matches_geometry)
- **근거**: `R_DIMENSION_SPAN_PRESERVED` 패턴 — 치수 표기값 vs defpoint 실거리 tol% 비교 `[3단계 §3.6]`; 치수가 도면 의미의 최대 질량(중심선도 70% `[probe-findings]`).
- **설계**: 왕복 산출 B'의 모든 DIMENSION에 대해 measurement(표기) vs 정의점 실거리 비교 — **카운트 diff가 못 잡는 조용한 기하 드리프트**를 의미층에서 잡는 가장 싼 게이트. A에서의 위반 집합과 B'에서의 위반 집합 동일성으로 판정(원본 위반은 보존이 정답). override 텍스트(<> 아닌 강제 문자열)는 별도 분류(위반 아님 — 제도 의도 `[EXPERIMENT_CONCLUSION §3]`). **성공기준**: A/B' 위반 집합 일치 + vacuous 아님(적용 건수 보고). **비용**: S. **P10a보다 먼저 착수 가능한 최고 가성비.**

---

## 5. 실행 순서 제안 (R4h 수확 후)

| 순위 | 실험 | 이유 | 의존 |
|---|---|---|---|
| 1 | **N5** 치수-기하 게이트 | S비용·최고 신호(치수=의미 질량 70%) | 없음 |
| 2 | **P7잔여** mismatch_decomposition | 잔여 anon 1.1k 소진의 엔진; 함대 패킷 생성기 | 없음 |
| 3 | **P10a** 그래프 제약 게이트 | O5 빈칸; P5 참조무결성과 공유 | 없음 |
| 4 | **P4a** xdata 센서스 | Probe 규율(쓰기 전 정찰); P10c 전제 | 없음 |
| 5 | **P5** 테이블(dimstyle 우선) | dwg_truth 계약 완성; N5와 상승작용 | P4a 병행 가능 |
| 6 | **P10b** 의미 보존(metamorphic) + O3 합성 진리 | L5 본체 | P10a |
| 7 | **P4b** xdata 재생 + **P10c** | provenance 채널 폐합 | P4a |
| 8 | **N1/N2/N3** | 강건성·교차합의·골든 제도화 | 상시 병행 |
| 9 | **N4** Δ-라운드트립 | 3단계로 가는 다리 | diff 안정화 후 |
| 대기 | **P9** 실행 | Paul 도면 수령 시; 레지스트리·위시리스트는 선행 구축 가능 | Paul |

게이트 편입 원칙(공통): 모든 신규 게이트는 interior_gate와 동형 — {ok/blocked/vacuous} 3상태, 래칫 바닥은 실측 후 설정(선하드코딩 금지), `--no-<gate>` 옵트아웃, gate_statuses 체인 폴드. VACUOUS ≠ PASS.

---

## 6. 가장 가치 높은 신규 발견 1개

**"게이트의 다음 세대는 카운트가 아니라 보존(preservation)이다"** — 원문 3곳이 독립적으로 같은 구조를 말한다: 라운드트립은 domain IR에 무력하므로 `[1단계 IR노트]`, 의미는 golden이 필요하지만 `[2단계]`, **golden 없이도 "결정론 의미 추출기의 출력이 왕복에서 보존되는가"는 물을 수 있다** `[v0.3_y O4 metamorphic]`. 즉 f(A)=f(B') 게이트(P10b·N5·P10a의 공통 골격)는 분류 정확도 문제를 우회하면서 의미층 회귀를 잡는다 — 그리고 우리의 write 경로는 O3(합성 진리)로 그 게이트 자체를 검증할 수 있게 한다. 이 구조(추출기 사다리 × 왕복 보존 × 합성 진리 자가검증)가 L5로 가는, 원문이 승인하는 유일한 무-golden 경로다.
