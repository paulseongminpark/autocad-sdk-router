# E2 방법론 심층 도시에 — platt_P0

**제안**: P0 — E1 불일치 법의학 감사 + 핸들-공간 계약 (E1 discrepancy forensic audit + handle-space contract)
**좌석**: platt_strong_inferencer (강한 추론 / strong inference)
**성격**: dissolver(문제 해소기) · 결정론(deterministic) · 학습 없음 · 판정자 없음
**한 줄 요지**: "탐지기가 약하다"는 전제를 떠받치는 E1 불일치(divergence)가 **실재 현상인지 계측 제조물(instrumentation artifact)인지**를, 학습·판정자 없이 IR(중간표현)의 결정론적 사실만으로 판별한다. 아티팩트로 판명되면 그 위에 세운 고가 실험 전체가 불필요해진다.

---

## 용어 사전 (본문에서 처음 쓰기 전 1줄 풀이 — 이후 코드네임은 이 정의로만 사용)

- **E1 불일치(E1 divergence)** = 앞선 E1 실험에서 결정론 탐지기와 LLM 판정자(ornith)가 "이 도면정의에 벽이 있는가"를 놓고 크게 엇갈린 사건. 그 엇갈림이 큰 상위 20개 도면정의가 "divergent-20".
- **IR(Graph IR)** = DWG 도면을 엔티티(선·폴리라인·블록…)와 그 관계의 그래프로 옮긴 중간표현. **엔티티가 IR 안에 실재하는가는 논쟁 불가능한 결정론적 사실**이다 — 이 제안의 진리원(truth source).
- **핸들(handle)** = DWG 안에서 한 엔티티에 붙는 영구 식별자(16진 문자열). 데이터베이스의 기본키(primary key)와 같은 역할.
- **def(도면정의, drawing definition)** = 한 장의 도면 또는 블록 정의 단위. 이 프로그램의 채점·감사 단위.
- **INSERT** = 다른 블록 정의를 좌표변환(이동·회전·축척)하여 끼워 넣는 참조 엔티티. 중첩되면 "def 안의 def"가 생긴다.
- **ornith / n_h_ornith=10** = E1에서 클러스터별로 벽 후보 핸들을 **정확히 10개 나열하라**고 지시받은 LLM 산출(`reports/e1/` JSONL). "10개 채워라"는 지시가 없는 벽까지 지어내게 만드는 아티팩트를 유발할 수 있다.
- **dissolver** = 문제를 "푸는" 대신 "그 문제가 성립하지 않음을 보여 해소하는" 실험. 강한 추론 규칙 3(값싼 배제 먼저)의 구현체.
- **H0 / H1 / H3** = 프로그램 가설들. **패킷이 정식 정의를 주지 않아 아래 §6 서두에서 조작적 정의(operational definition)를 명시하고 [해석]으로 표기**한다.
- **핸들-공간 계약(handle-space contract)** = "LLM이 인용한 모든 핸들은 IR에서 실재 엔티티로 해소(resolve)되어야 하고, 그 엔티티의 소속·타입·쌍가능성이 기록되어야 한다"는 검증 스키마. 데이터베이스의 외래키 무결성 검사(referential integrity)에 해당.

> **수치 인용 규약**: E2 고유 측정치는 전부 이 패킷의 실측 다이제스트(2026-07-18 세션 도구 출력)에서만 인용한다. 문헌·기법의 연도/저자 등 일반 지식 인용은 확신이 낮으면 `[요검증]`으로 표기했다. 새 측정 주장은 하지 않는다.

---

## 1. 이론적 근거·선행연구 — 이 제안이 기대는 방법론 계보

이 제안은 새 탐지기를 만들지 않는다. 따라서 그 계보는 벽 탐지 DL 문헌이 아니라 **"현상이 실재하는지 먼저 의심하는" 과학철학·데이터공학 계보**에 있다. 네 갈래다.

### 1.1 강한 추론과 결정적 실험 (핵심 계보)

- **Platt의 강한 추론(Strong Inference, J. R. Platt, *Science*, 1964)** `[요검증: 권/페이지]`. 좌석 이름 자체가 여기서 왔다. 절차는 ① 복수의 대립 가설을 세우고 ② 그중 하나를 **배제**할 결정적 실험을 설계하고 ③ 실행하고 ④ 살아남은 가설로 재귀한다. P0는 이 사슬의 ②에 해당하는 "결정적 실험"이다 — "탐지기 개념 결함이 실재한다"는 가설을 **가장 값싸게 배제 가능한** 실험.
- **다중 작업가설(Method of Multiple Working Hypotheses, T. C. Chamberlin, 1890)** `[요검증]`. 하나의 애착 가설(여기서는 "탐지기가 약하다")에 매몰되지 않도록, 경쟁 가설(불일치=아티팩트)을 동등하게 계측한다.
- **experimentum crucis / 반증(Popper)** — 결정적 실험은 확증이 아니라 **배제**로 정보를 얻는다. P0의 prereg 밴드가 "어느 관측이 어느 가설을 죽이는가"를 결과 보기 전에 못 박는 것이 이 원리의 구현이다.
- **문제 해소(dissolution) vs 문제 해결(solution)** — 후기 Wittgenstein 계열의 "그 물음이 잘못된 전제 위에 서 있으면 답이 아니라 전제를 검사하라". P0는 "왜 탐지기가 이 20개 def에서 벽을 놓치는가?"에 답하는 대신 "그 20개에 놓칠 실재 벽이 있긴 한가?"를 먼저 묻는다.

### 1.2 계측 제조물 회의주의 (measurement-artifact skepticism)

- **병적 과학(pathological science, Langmuir)·N선(Blondlot)** `[요검증]` — 관측된 "효과"가 장비·기대·선택의 산물이었던 고전 사례. 교훈: 블라인드 대조군과 결정론적 재계측 없이 미세 효과를 믿지 말라. P0의 무작위 대조 20 def와 정렬키 재계산(C7)이 이 교훈의 직접 이식.
- **선택 편향(selection bias)** — top-20은 `_score_divergence` 정렬의 **상위 꼬리**다. 정렬키가 특정 엔티티 종류(익명 `*U###`/xref-바운드 블록)를 위로 밀어 올렸다면, "상위 20이 죄다 한 종류"는 발견이 아니라 정렬 설계의 그림자다(공격 C). 이는 통계학의 "극단 순위는 잡음으로도 만들어진다"(regression-to-the-mean, 순위 통계) 논점과 같다.

### 1.3 참조 무결성·데이터 계보 (referential integrity / provenance)

- **외래키 무결성·엔티티 해소(record linkage)** — 핸들-공간 계약은 본질적으로 "인용된 외래키가 실재 행(row)으로 해소되는가"의 검사다. LLM이 인용한 핸들 `h`가 IR 엔티티 테이블에 **존재하지 않으면**, 그것은 벽 논쟁이 아니라 **댕글링 참조(dangling reference)**다.
- **데이터 계보/출처(provenance, W3C PROV 계열)** `[요검증]` — "이 인용은 어느 산출 run에서 왔고 그 run이 실제로 실행되었는가"(T34: 인용 R-레인 6개 전부 `experiment_executed:false`)를 추적하는 규율. P0의 C0 게이트가 이 규율을 감사 착수 조건으로 승격시킨다.

### 1.4 강제 나열 하 LLM 환각 (일반 지식)

- 모델에게 "정확히 N개를 나열하라"고 강제하면 실재 항목이 N개 미만일 때 **정족수를 채우려 없는 항목을 지어내는** 경향이 있다(confabulation under forced enumeration) — 일반적으로 보고되는 LLM 실패 양식. `n_h_ornith=10`은 정확히 이 압력을 건다. C6이 이 아티팩트(중복 핸들·실재 엔티티 수 초과·단조 증가 핸들열)를 결정론적으로 검출한다.

### 1.5 CAD 도메인 지식 (일반 지식)

- **DWG/DXF 객체 모델**: 핸들은 영구 식별자, INSERT는 블록 참조(좌표변환 포함), **MLINE(multiline)은 AutoCAD의 사실상 "벽" 원생 엔티티**, LWPOLYLINE·ARC·SPLINE·HATCH가 실도면을 채운다. 헤더 변수 `$INSUNITS`/`$MEASUREMENT`가 단위를 선언한다(설정 안 되면 unitless).
- 이 도메인 사실이 P0의 감사 항목을 규정한다: 인용 핸들이 MLINE/HATCH면 "쌍가능 LINE 벽"이라는 탐지기의 세계관 밖이고, 좌표가 mm가 아니면 두께 대역(50~400mm) 자체가 무의미하다.

### 1.6 벽 탐지 선행 시스템 (맥락용 — P0는 사용하지 않음)

P0는 아래 어느 것도 실행하지 않지만, "탐지기가 약하다"는 서사가 암묵적으로 겨루는 상대들이다: CubiCasa5k 데이터셋/CNN(Kalervo et al.) `[요검증: 2019 WACV]`, Raster-to-Vector(Liu et al.) `[요검증: 2017 ICCV]`, FloorPlanCAD 벡터 패놉틱 심볼 스포팅(Fan et al.) `[요검증: 2021 CVPR]`, GAT-CADNet 계열 그래프 신경망 `[요검증]`. P0의 역할은 이들과 경쟁하는 것이 아니라, **이들을 부르기 전에 그 부름의 근거가 실재하는지 검사**하는 것이다.

---

## 2. 알고리즘 정확 스펙 — 의사코드·계약 수준

P0에는 **학습이 없다 → 손실함수·경사·에폭이 없다.** "알고리즘"은 결정론 감사 절차이고, "하이퍼파라미터 공간"은 **결과를 보기 전에 봉인하는 prereg 결정 상수들**이다. 아래에 (a) 핸들-공간 계약, (b) prereg 상수, (c) 전체 감사 의사코드를 명시한다.

### 2.1 핸들-공간 계약 (형식 정의)

def `d`의 클러스터 `c`에서 LLM이 인용한 핸들 `h`에 대해:

```
C1 (구문)     : h가 DWG 핸들 문법(16진 문자열)에 부합
C2 (실재)     : ∃ 엔티티 e ∈ IR(d의 문서 전체)  s.t. handle(e) = h
C3 (소속)     : membership(e) ∈ { IN_DEF(d), IN_NESTED(d의 INSERT 사슬 하위), FOREIGN(다른 def), ABSENT(없음) }
C4 (타입)     : type(e) ∈ { LINE, LWPOLYLINE, MLINE, ARC, INSERT, HATCH, SPLINE, OTHER }
C5 (쌍가능)   : type(e)=LINE 이고, 두께 대역(50~400mm[가정]) 안에서 평행 파트너가 존재 → PAIRABLE
```

인용 `h`가 **계약을 만족(SATISFY)** ⟺ `C1 ∧ C2 ∧ (C3 ∈ {IN_DEF, IN_NESTED}) ∧ (C4 = LINE) ∧ C5`.
그 외에는 **위반(VIOLATION)**이며, 위반은 **타입이 붙는다**:
`SYNTACTIC`(C1 실패) · `ABSENT`(C2 실패) · `FOREIGN`(C3=FOREIGN) · `NESTED_ONLY`(C3=IN_NESTED — 위반 아님, 별도 표식) · `NON_LINE`(C4≠LINE) · `UNPAIRABLE`(C5 실패).

> **왜 이 계약이 진리원 논쟁을 없애는가**: C1~C4는 IR을 조회하면 나오는 **결정론적 사실**이다. "이 핸들이 벽인가"는 논쟁적이지만 "이 핸들이 IR에 LINE으로 실재하는가"는 논쟁의 여지가 없다. P0는 후자만 판정한다.

### 2.2 prereg 결정 상수 (봉인 대상 — 학습 파라미터의 자리를 대체)

| 상수 | 의미 | 봉인값(초안, C0에서 동결) |
|---|---|---|
| `τ_hi` | 부재+비-LINE 비율 상한 밴드 | **0.50** (top-20에서 인용 핸들의 ≥50%가 def 내 부재 또는 비-LINE → H0 생존 강화) |
| `τ_lo` | 부재 비율 하한 밴드 | **0.10** (≤10% 부재 & 대다수 쌍가능 LINE → H0 kill) |
| `κ_unit` | 단위 이탈 배율 | **10×** (bbox 스케일이 mm 가정과 ≥10× 이탈) |
| `ρ_unit` | 단위 위반 def 비율 문턱 | **0.30** (그런 def 비율 ≥30% → 단위-보조가정 위반 플래그, P1 주입) |
| `n_ctrl` | 대조군 def 수 | **20** (무작위, 시드 고정) |
| `seed` | 대조군 추출 시드 | **고정값(예: 20260718)** — C0에서 동결, 이후 변경 금지 |

이 표는 **결과를 보기 전에 봉인**한다(§6 C0). 봉인 후 문턱을 결과에 맞춰 조정하는 행위(p-hacking)가 이 실험의 유일한 부정행위 경로이며, 봉인이 그것을 차단한다.

### 2.3 전체 감사 의사코드

```
INPUT:
  IR         : DWG Graph IR (defs, entities, INSERT 사슬)   # 진리원, 결정론
  ORNITH     : reports/e1/ JSONL (def→cluster→인용 핸들 리스트, n_h=10)
  DIV20      : divergent-20 def 목록 + _score_divergence 원점수
  PREREG     : §2.2 봉인 상수

OUTPUT:
  per_def_table.xlsx        # def×감사항목 결정론 표 (evidence 의무)
  aggregate_stats.json      # 밴드 판정 입력 집계
  verdict.md                # O-A / O-B / 무결정 + H0 생사

# ── C0 게이트: 데이터 실재 + prereg 봉인 ──────────────
assert exists(ORNITH) and nonempty_per_def(ORNITH, DIV20)   # BOUNCED/EMPTY def 목록화
CONTROL := sample_without_replacement(all_defs \ DIV20, n=20, seed=PREREG.seed)
freeze(PREREG); log_hash(PREREG)                            # 봉인 해시 기록
DEFS := DIV20 ∪ CONTROL

# ── 엔티티 인덱스 구축 (INSERT 전개 포함) ─────────────
for d in DEFS:
    idx[d] := { handle(e): e for e in entities(d) }         # C2용 해시
    nested[d] := expand_inserts(d, max_depth=∞)             # C3=IN_NESTED, mechanism (iii)

# ── def별 감사 ───────────────────────────────────────
for d in DEFS:
    # (i) 엔티티 타입 히스토그램  → C1 셀
    hist[d] := count_by_type(entities(d) ∪ nested[d])

    # (ii) 핸들-공간 계약  → C2 셀 (H0 핵심)
    for h in cited_handles(ORNITH, d):
        e := resolve(h, idx[d], nested[d])                 # C1..C4
        rec[d,h] := classify(e)  ∈ {SATISFY, ABSENT, FOREIGN, NESTED_ONLY, NON_LINE, UNPAIRABLE, SYNTACTIC}
        if type(e)=LINE: rec[d,h].pairable := has_parallel_partner(e, band=[50,400]mm)   # C5

    # (iii) 중첩 INSERT 깊이·내부 기하  → C3 셀
    depth[d] := max_insert_depth(d); inner_geo[d] := |nested[d]|

    # (iv) bbox 스케일·단위 법의학  → C4 셀
    bbox[d] := aabb(entities(d)); scale[d] := diag(bbox[d])
    unit_flag[d] := (scale[d] / mm_expectation(d)) ≥ κ_unit

    # (v) 블록명 토큰 ↔ likelihood  → C5 셀
    tok[d] := tokenize(block_name(d))                       # '평면도','WALL','W-' 등
    # 상관은 집계 단계에서 (아래)

    # (vi) 나열-지시 아티팩트  → C6 셀
    for c in clusters(ORNITH, d):
        enum_art[d,c] := (len(cited(c)) > real_entity_count(c))
                         ∨ has_duplicates(cited(c))
                         ∨ is_monotone_handle_run(cited(c))

# ── 집계·상관 ────────────────────────────────────────
absent_or_nonline_rate := agg_over(DIV20, rec, {ABSENT,FOREIGN,NON_LINE,SYNTACTIC})
pairable_line_rate      := agg_over(DIV20, rec, SATISFY)
unit_violation_ratio    := mean_over(DIV20, unit_flag)
name_corr               := association(tok, wall_likelihood)   # H3, 예: point-biserial / rank
# vs CONTROL: 위 모든 지표를 대조군에서도 계산 → 편향 상쇄 기준선

# ── T3: 정렬키 아티팩트 재계산 ───────────────────────
recomputed_score := _score_divergence_reimpl(DIV20)          # 원 정렬 재구현
top20_stability  := jaccard(argtop20(recomputed_score), DIV20)
single_type_frac := fraction_single_entity_kind(DIV20)

# ── 밴드 판정 (prereg 대조) ──────────────────────────
if absent_or_nonline_rate ≥ τ_hi:  verdict := "O-A: H0 생존 강화 + crosscheck v0 RETRACT 후보"
elif absent_rate ≤ τ_lo and majority(pairable_line): verdict := "O-B: H0 kill"
else: verdict := "중간대(indeterminate) — 재측정/추가 def 필요"
if unit_violation_ratio ≥ ρ_unit: emit_flag("UNIT_AUX_VIOLATION → P1")
```

**복잡도·수치 안정성**: 각 def는 엔티티 수 `N_d`에 선형(해시 조회 O(1), 평행 파트너 탐색은 각도 버킷팅으로 근사 O(N_d)). 최대 def가 412,775 선분(실측 다이제스트, 연산 병목 실증)이므로 이 한 def만 벡터화(NumPy)로 처리하고 나머지는 자명하다. 부동소수 bbox는 배정밀도. 문자열 정규화(def명 공백 변형)는 C8에서 결정론 회귀로 고정.

---

## 3. 벽 과업 적응 설계 — 실제 하네스에 어떻게 접속하는가

실측 다이제스트의 세 축과 P0의 관계를 정직하게 구분한다.

### 3.1 세 하네스 축과의 접속

- **1.dwg 실도면 축 (주 접속점)**: divergent-20과 E1 원시 JSONL(`reports/e1/`)이 사는 곳. B3(벽-제로 도면율 0.682→0.2135 PASS, 384 도면정의)·B5(탐지기↔silver Pearson 0.2911, full-vs-nb 1.0 → 탐지기 레이어명 신호 0)가 나온 축. **P0의 6개 감사 항목 전부가 이 축에서만 돈다.** E1 불일치라는 현상 자체가 이 축의 산물이기 때문.
- **CubiCasa5k 벡터 축 (간접 접속 — 방법론적 동형)**: P0는 여기서 직접 돌지 않는다. 그러나 P0의 **단위 법의학(C4)이 겨누는 병리와 CubiCasa 전이 실패의 병리는 동일**하다. CubiCasa 좌표는 px, **도면별 축척 미상**, 벽두께 px p50=22이고, 기하 탐지기 전이는 "축척 2~15mm/px 전 구간에서 성적 무감(물리 두께 prior 무력)"이었다. 이는 정확히 "mm 절대 두께 대역(50~400mm)이 단위가 미상인 좌표계에서 무의미해진다"는 C4의 가설이다. **P0가 1.dwg에서 단위-보조가정 위반을 실증하면, CubiCasa의 mm-band 무감은 우연이 아니라 같은 뿌리의 두 증상으로 통합된다.**
- **FloorPlanCAD 래스터 축**: P0와 무접속. 래스터에는 핸들·IR이 없어 핸들-공간 계약이 성립하지 않는다. 정직하게 범위 밖.

### 3.2 전이 실패 0.236·GBDT 0.517을 아는 상태에서 P0가 더 가져오는 것

P0는 **F1을 올리지 않는다.** 그것이 이 제안의 정체다. P0가 가져오는 것은 성능이 아니라 **증거의 재정초(epistemic re-basing)**다. 구체적으로:

1. **"학습 사다리를 올라야 한다"는 서사의 1.dwg측 근거를 검증한다.** 현재 서사는 "탐지기가 개념적으로 약하다(E1 불일치) → 그러니 고전ML·그래프·DL로 올라가야 한다"이다. 만약 E1 불일치가 아티팩트(H0 생존)라면, 이 서사의 **1.dwg 증거 축이 무너진다.** 그러면 탐지기 한계의 유일한 실증은 **CubiCasa 전이(F1 0.236)와 GBDT lift(0.517)** 뿐인데, 이것은 "같은 도메인의 개념 결함"이 아니라 **"핀란드 주거 외부셋으로의 도메인 전이 결함"**이다 — 전혀 다른 병이고 다른 처방을 부른다.
2. **GBDT 0.517의 해석을 재정초한다.** GBDT가 6특징으로 정밀도를 0.13→0.86으로 끌어올렸다는 사실은 "기하 특징이 충분히 벽을 판별한다"는 강한 증거다. 그렇다면 1.dwg에서 탐지기가 놓친 것이 **실재 쌍가능 LINE**(H0 kill)인지, 아니면 **애초에 벽이 아닌 것**(H0 생존)인지가 GBDT 결과와 교차 검증된다. C2가 O-B(핸들 실재·쌍가능)를 내면 GBDT의 성공과 정합(진짜 벽을 특징이 잡아낸다), O-A를 내면 "GBDT는 CubiCasa 벽은 잡지만 1.dwg divergent-20의 인용은 애초에 벽이 아니었다"는 **비대칭**을 드러낸다.
3. **P1(CL-B)에 단위-보조가정을 주입한다.** C4가 mm-이탈 def ≥30%를 실증하면, 절대 mm 대역(50~400mm)을 쓰는 모든 실험(탐지기 v1, CubiCasa 전이)이 **단위-정박 상대 대역**으로 재설계되어야 한다는 하드 신호가 된다(feyerabend P2 근거).
4. **silver 독립성의 계량 근거를 준다.** B5는 탐지기가 레이어명 신호 0(full-vs-nb 1.0)임을 이미 보였다. C5(블록명 토큰↔likelihood 상관)가 **판정자 측**에서 이름 prior 탑승을 검출하면, "탐지기 vs silver 두 축이 대체로 독립(Pearson 0.2911)"이라는 관측이 **왜** 그런지(한쪽만 이름을 본다)를 설명한다.

한 줄로: **P0는 사다리를 오르지 않는다. 사다리가 어느 벽에 걸쳐 있는지, 그 벽이 실재하는지를 본다.**

---

## 4. 데이터·컴퓨트 요구 — 우리 자산 기준 실행 가능성

P0는 자원 관점에서 **프로그램 전체의 최저가 프로브**다.

### 4.1 로컬 실행 계획 (유일한 계획)

- **입력 데이터**: `reports/e1/` JSONL(ornith 원시), 1.dwg staged DXF의 Graph IR JSON, divergent-20 목록 + `_score_divergence` 원점수. **모두 이미 로컬에 존재하는 산출물** — 새 계측 0.
- **연산**: 로컬 CPU **<1h**(실측 다이제스트의 compute plan). GPU 0, LLM 0, DGX 불사용.
- **메모리**: RAM 64GB로 충분. 병목은 최대 def의 412,775 선분 한 건 — 이 def만 NumPy 벡터화로 평행 파트너 탐색(각도 버킷). 나머지 383개 def는 자명. 전체를 스트리밍하면 상시 메모리는 수백 MB급.
- **디스크 산출**: `per_def_table.xlsx`(40 def × 감사항목), `aggregate_stats.json`, `verdict.md`. 증거 xlsx 의무 충족.
- **개발 규모**: 스크립트 작성 **반나절**(실측 다이제스트). 아래 §5 모듈 골격 기준 ~400–700 LOC 추정(일반 지식 기준의 규모감이며 측정치 아님).

### 4.2 DGX 계획 — 없음 (그리고 그것이 강점)

DGX Spark(Ornith-35B)는 현재 unreachable(승인은 됨). **P0는 DGX가 영영 안 뚫려도 완주한다.** 프런티어 VLM API(유일 결재 게이트, 미승인)도 불필요. 즉 P0는 **프로그램에서 유일하게 "막힌 자원에 인질 잡히지 않은" 판별 실험**이다. 이 자원 독립성이 dissolver를 프로브 큐 최상단에 두는 실무적 근거다: 다른 모든 실험이 자원·승인 대기 중일 때, P0는 오늘 돌 수 있다.

---

## 5. 구현 계획 — 모듈·파일 골격, 기존 도구 접속점

P0는 **새 독립 스크립트 1개**(패킷: "결정론 감사 스크립트 1개")다. 기존 파이프라인을 수정하지 않는다 — 읽기 전용으로 접속한다.

### 5.1 모듈 골격 (신규, 예상 배치 `tools/e2/dossier/`)

```
tools/e2/dossier/
  e1_forensic_audit.py     # 오케스트레이터: C0..C8 순서 실행, verdict 산출
  ir_loader.py             # Graph IR JSON 로드, handle→entity 인덱스, expand_inserts()
  handle_contract.py       # §2.1 계약 검증기 (classify: SATISFY/ABSENT/.../UNPAIRABLE)
  ornith_parse.py          # reports/e1 JSONL 파서, cited_handles(), enum-artifact 검출(C6)
  unit_forensics.py        # bbox 스케일 분포, κ_unit 이탈 플래그 (C4)
  sortkey_recompute.py     # _score_divergence 재구현 + top-20 안정성 (C7, T3)
  prereg.json              # §2.2 봉인 상수 + seed + 봉인 해시 (C0에서 write-once)
  emit_evidence.py         # xlsx/json 산출 (evidence_grid 규약 준수)
```

### 5.2 기존 도구 접속점 (읽기 전용 재사용 — 수정 금지)

- **`cubicasa_ir`**: IR 로딩·엔티티 순회 패턴을 `ir_loader.py`가 차용(동일 스키마 가정). CubiCasa 전용 로직은 쓰지 않고 "IR→엔티티 인덱스" 관용구만 재사용.
- **`fast_score`**: NumPy 동치 고속 채점기. C5(쌍가능성)의 평행 파트너 탐색을 `fast_score`의 각도·overlap·snap 접근(각도 허용 2°, overlap 0.5, snap 6mm — 탐지기 v1 파라미터)과 **동일 규약**으로 구현해, "탐지기가 쌍으로 볼 수 있었는가"를 탐지기와 같은 렌즈로 판정. **이때 탐지기를 재실행하지 않고 그 기하 술어만 빌린다.**
- **`evidence_grid`**: xlsx 증거 산출 규약을 `emit_evidence.py`가 따른다(평가 원칙: 증거 xlsx 의무).
- **`cubicasa_ml`**: 무접속(학습 계열, P0는 학습 없음).

### 5.3 산출 위치·규율

- 산출: `reports/e2/s4/`(기존 evidence 디렉토리 관용) 아래 `platt_p0_forensic_*`. 원본 IR·DWG·JSONL은 **읽기 전용**(PROTECTED — 원본 CAD 불변 규약).
- 실행은 1회. 재실행 시 `prereg.json` 해시가 봉인값과 불일치하면 **중단**(문턱 변조 방지 가드).

> 주: 위 골격은 **계획**이다. 이 도시에 과업의 계약상 나는 이 스크립트를 **생성하지 않는다**(산출물은 본 MD 하나뿐). 파일 존재·정확한 함수 시그니처는 착수 시점에 실측으로 확인해야 하며 `[요검증]`이다.

---

## 6. 실험 셀 정의

> **가설 조작적 정의 [해석]** — 패킷이 H0/H1/H3의 정식 문구를 주지 않아, 패킷의 kill/prereg 서술로부터 아래처럼 조작적으로 정의한다. 다른 좌석 원문과 충돌하면 원문이 우선.
> - **H0 (귀무)** = "E1 불일치는 **탐지기의 실제 결함이 아니라 계측 제조물**이다(인용 핸들이 부재/비-LINE/중첩-only/단위미상/정렬편향/나열아티팩트에서 나온다)." — 인용이 **부재·비-LINE**일수록 H0 **생존**, 인용이 **실재·쌍가능 LINE**일수록 H0 **kill**.
> - **H1** = "탐지기에 **실재 기하 위의 진짜 커버리지 갭**이 있다(놓친 것이 실재 쌍가능 LINE 벽이다)." — H0 kill 방향의 정밀화.
> - **H3** = "블록명/이름 토큰이 wall_likelihood와 상관한다(판별이 기하가 아니라 **이름 prior**를 탄다)."

> **val/test 원칙 적용 [정직한 매핑]**: P0에는 학습이 없어 train/val/test 분할이 없다. 대응물은 ① **prereg 봉인**(밴드·시드를 결과 전 동결) ② **단발 실행**(문턱을 결과에 맞춰 재조정 금지) ③ **무작위 대조 20 def**(기준선). 이 셋이 "test 단발"의 무학습 등가물이다. 셔플/대조군 의무는 C7의 무작위 대조와 C2/대조군 병렬 계산으로 충족.

셀은 메커니즘 (i)~(vi) + T3 재계산 + 데이터/봉인 게이트 + 정규화 가드 = **9셀**. 전부 **한 번의 결정론 패스**에서 같은 데이터 위에 돈다(별도 컴퓨트 잡 아님). 과잉 분해 아님 — 각 셀은 패킷이 명시적으로 지목한 항목이다.

| 셀 | 가설/목적 | 지표 | 제안 합격선(prereg) | 킬 조건 | 예산 | 시드/대조 |
|---|---|---|---|---|---|---|
| **C0** 데이터·봉인 게이트 | 감사 입력이 실재하고 밴드가 봉인됨 | ornith JSONL 실재·비어있지 않은 def 수; 봉인 해시 | DIV20의 ≥80% def에 비-empty ornith 존재 | <80%면 **감사 무결정 → "E1 재실행" 신호로 축소**(§8 death #1) | 즉시 | seed 동결(20260718) |
| **C1** 엔티티 타입 히스토그램 (i) | def가 무슨 엔티티로 이뤄졌나 | LINE/LWPOLYLINE/MLINE/ARC/INSERT/HATCH/SPLINE 분포 | (기술셀 — 합격선 없음, 다른 셀 입력) | — | 포함 | DIV20 vs 대조20 |
| **C2** 핸들-공간 계약 (ii) **[H0 핵심]** | 인용 핸들이 실재·쌍가능 LINE인가 | 부재+비-LINE 비율; 쌍가능 LINE 비율 | ≥`τ_hi`(0.50) 부재/비-LINE → **H0 생존↑** + crosscheck v0 RETRACT 후보 | ≤`τ_lo`(0.10) 부재 & 다수 쌍가능 → **H0 kill** | 포함 | 대조20 병렬 계산 |
| **C3** 중첩 INSERT (iii) | 인용이 전개 안 된 중첩 안에 사나 | NESTED_ONLY 비율; max depth; 내부 기하량 | (H1/feyP6 입력 — 합격선 없음) | NESTED_ONLY 다수면 "개념결함 아닌 전개버그" 방향 | 포함 | DIV20 vs 대조20 |
| **C4** 단위 법의학 (iv) **[P1 주입]** | 좌표가 mm 가정과 어긋나나 | `κ_unit`(10×) 이탈 def 비율 | ≥`ρ_unit`(0.30) → **단위-보조가정 위반 플래그 → P1** | (플래그 생성 셀 — 자체 kill 없음) | 포함 | DIV20 vs 대조20 |
| **C5** 이름토큰 상관 (v) **[H3]** | 이름이 likelihood를 예측하나 | 토큰 유무 ↔ wall_likelihood 연관(point-biserial/순위) | (방향 증거 — 사전 임계 없음, 부호·크기 보고) | 강한 양의 상관 → 판정자 이름-prior 탑승(CL-I 씨앗) | 포함 | 대조20이 영가설 기준선 |
| **C6** 나열 아티팩트 (vi) **[T4]** | n_h=10이 없는 벽을 지어냈나 | 실재수 초과·중복·단조열 비율 | 높은 아티팩트율 → H0 생존 지지 | (지지 증거 — 단독 kill 아님) | 포함 | DIV20 vs 대조20 |
| **C7** 정렬키 재계산 **[T3/공격C]** | top-20이 정렬 설계의 그림자인가 | `_score_divergence` 재구현 후 top-20 Jaccard 안정성; 단일종 비율 | 안정성 높고 단일종 낮음 → 선택편향 아님 | 낮은 안정성/높은 단일종 → **top-20은 아티팩트**, 대조20으로 상쇄 보고 | 포함 | 무작위 대조 = 편향 기준선 |
| **C8** 정규화 결정론 가드 | def명 정규화 버그가 아티팩트 재제조? | 공백 변형 케이스 결정론 재현 테스트 | 변형 무관 동일 판정(재현율 100%) | 비결정 발견 → 감사 **자체 신뢰 상실**, 정규화 수정 후 재봉인 | 포함 | 고정 테스트 벡터 |

**최종 판정 규칙(prereg)**: `verdict = O-A(H0 생존 강화 + crosscheck v0 RETRACT 후보)` if C2 부재/비-LINE ≥ 0.50; `= O-B(H0 kill)` if C2 부재 ≤ 0.10 & 다수 쌍가능; 그 외 **중간대(무결정)** — 정직하게 "추가 def/재측정 필요"로 기록(FM1 상태 부풀리기 금지).

---

## 7. red team 티켓 응답

패널 보고서에서 P0(=CL-A)에 걸린 OPEN 티켓을 지목하고 각각 **해소/수용** 입장을 명시한다. `seats/red_teamer.md` 원문은 이 패킷에 포함되지 않아, 티켓 정확 문구가 패킷 본문에 없는 항목은 `[문구 요검증]`으로 표기하고 패킷이 드러낸 수준에서 응답한다.

- **T1 — 대리(truth proxy) 독립성 (sev 0.75, 최우선) → 구성적 해소(RESOLVE by construction)**
  공격 A: {합성·외부셋·metamorphic·silver} 4대리가 같은 "평행 이중선" prior를 공유하면 합치는 확증이 아니라 편향 증폭. **P0의 진리원은 이 4대리 어디에도 속하지 않는 DWG Graph IR의 결정론적 엔티티 실재**다. "핸들이 IR에 LINE으로 존재하는가"는 어떤 prior도 공유하지 않는다. **P0는 T1이 지목한 편향 클러스터 밖의 유일한 정박점**이며, 오히려 다른 대리들의 독립성을 재는 자(尺)가 된다. → **해소.**

- **T3 — 정렬키 아티팩트 (sev 0.60, 하드 선결로 승격) → 직접 계측(C7)으로 해소**
  공격 C: top-20 단일종은 `_score_divergence` 정렬 설계의 산물. C7이 정렬키를 재구현해 top-20의 섭동 안정성(Jaccard)과 단일종 비율을 측정하고, **무작위 대조 20으로 편향을 상쇄**한다. **잔여 위험(정직)**: 만약 divergence 신호 자체가 정렬키 하나뿐이면 top-20은 정의상 그 키로 선택된 것이라 "선택편향 없음"을 완전히 증명할 수는 없다 — 이 경우 대조군 대비 **상대적** 편중만 보고하고 절대 무편향은 주장하지 않는다. → **대체로 해소, 한계 명시.**

- **T4 — ornith 원시 조달·나열 아티팩트 (sev 0.55) → C0+C6으로 대응, 부분 수용**
  C0이 `reports/e1/` JSONL의 def별 실재·비어있음을 먼저 감사하고, C6이 n_h=10 나열 아티팩트를 결정론 검출한다. **수용(위험 인정)**: 일부 def의 ornith 원시가 BOUNCED/EMPTY면 그 def의 (vi)는 판정 불가다. 이때 **결측을 상상으로 메우지 않고**(imputation 금지) 커버리지를 보고하고 사유와 함께 제외한다(평가 원칙: 실패도 사유와 함께 기록). → **부분 해소 + 잔여 위험 수용.**

- **T8 — P0 개별 티켓 `[문구 요검증]` → 스탠스 명시**
  T8은 red team이 CL-A에 건 per-proposal 티켓으로, T3와 함께 **하드 선결로 승격**되었다(패킷). 정확 문구는 이 패킷에 없다. 승격 맥락과 프로브 큐("T4 ornith 원시 조달")로 보아 T8은 **ornith 원시 데이터의 실재·출처(provenance)** 계열로 판단한다. 스탠스: C0을 **감사 착수의 하드 게이트**로 삼아, 원시가 없으면 감사를 진행하지 않고 "E1 재실행 필요"로 정직하게 축소한다(§8). 만약 착수 시 확인한 T8 실제 문구가 이 해석과 다르면 그 문구가 우선하며 게이트를 재설계한다. → **조건부 해소(문구 확인 대기).**

- **T6 — 평가 단위(집합-조립 vs per-handle) (sev 0.60) → 경미, 명료화로 해소**
  공격 E는 "집합-조립을 per-handle 채점에 섞으면 평가 단위가 모호"를 지적한다. **P0의 평가 단위는 per-cited-handle(계약 만족/위반)과 per-def(비율 집계)로 명시**되며 집합-조립 산출이 없다. → **해소(범위상 무해).**

- **T34 — load-bearing 인용 재-status (프로그램급) → 기여로 해소 지원**
  인용 R-레인 6개가 전부 `experiment_executed:false`. P0는 **원시 IR+JSONL에서 재도출**하므로, E1 기반 load-bearing 인용이 실제 산출로 뒷받침되는지(또는 아티팩트인지)를 재-status하는 **직접 증거**를 만든다. → **프로그램급 해소에 기여.**

> **수용(미해소) 정직 고지**: T2(생성기 부재)·T5(라이선스)는 P0 범위 밖이다. P0는 합성 생성기도, 외부셋 학습도 쓰지 않으므로 이 둘에 **노출되지 않는다** — 회피가 아니라 구조적 무관. 단 P0의 결과가 다른 제안(CL-C/CL-F/CL-G)을 살리면 그때 T2/T5가 활성화된다.

---

## 8. 인접 제안과의 관계 — 병합·차별점·죽어야 하는 조건

### 8.1 병합 가능 지점 (P0가 먹이는 하류)

- **→ CL-B (platt P1: 커버리지-완전 결정론 v1)**: C4의 단위-보조가정 플래그가 **feyerabend P2(mm 절대대역→치수-정박 상대대역)**의 하드 근거가 되고, C3의 중첩 INSERT 실증이 **feyerabend P6(INSERT 월드좌표 전개 — 코드 확정 결함)**의 정타 지점을 특정한다. C2가 H1(커버리지 갭) 방향을 주면 CL-B의 정규화(LWPOLYLINE/MLINE/ARC) 우선순위가 정해진다.
- **→ CL-I (platt P6: 관례-prior 계측화)**: C5(이름토큰↔likelihood)가 CL-I의 씨앗. B5가 보인 "탐지기 레이어 신호 0"과 결합해 **판정자 측** 이름-prior를 분리 계량 → silver 독립성 감사 겸용.
- **→ CL-E (doe P3: truth-source 교차요인) / PR-2(대리 독립성 감사)**: P0의 결정론 IR 진리원이 두 실험의 **독립 정박점**. C2의 in-def/nested/absent 구조가 곧 "동일 def 3원 불일치 구조"의 한 축을 결정론적으로 제공.

### 8.2 차별점 (P0만이 하는 것)

P0는 **유일한 dissolver**다. 다른 모든 후보(CL-B 결정론 개선, CL-C 합성 truth, CL-F 학습 사다리, CL-G 래스터/VLM, CL-H RL)는 **무언가를 짓는다(constructive)**. P0만이 **아무것도 짓지 않고, 짓는 행위의 근거가 실재하는지 검사**한다. 그래서 프로브 큐 최상단이고(자원 독립·<1h), 유일하게 **하류 실험 전체를 불필요하게 만들 수 있는** 실험이다. 이것이 강한 추론 규칙 3(값싼 배제 먼저)의 정확한 구현이다.

### 8.3 이 제안이 죽어야 하는 조건 (정직하게)

강한 추론의 규율상, 내 제안의 사망 조건을 남의 것보다 먼저·엄격히 적는다.

1. **데이터 부재로 인한 무결정 (C0 실패)**: `reports/e1/` ornith 원시가 DIV20의 다수에서 BOUNCED/EMPTY면, P0는 dissolver가 아니라 **"E1을 provenance 로깅과 함께 재실행하라"는 신호로 축소**된다. 이 경우 "기존 E1 감사"라는 P0는 죽고, "E1 재실행"이라는 다른 실험이 그 자리를 잇는다. (T4/T8 위험의 실현.)
2. **이미 killed된 H0**: 만약 별도 경로에서 인용 핸들이 실재 쌍가능 LINE임이 이미 확립되면(H0 이미 kill), P0는 중복이고 프로그램은 CL-B로 직행한다.
3. **감사 대상 인용의 소멸 (가장 정직한 사망 조건)**: 프로그램이 **1.dwg E1 불일치를 더 이상 load-bearing 증거로 인용하지 않게 되면**(예: CubiCasa 외부셋 학습으로 완전 피벗해 GBDT 0.517·전이 0.236만이 근거가 되고 1.dwg E1 서사를 폐기), P0가 감사할 **대상 자체가 죽은 인용**이 된다. 죽은 인용을 감사하는 것은 낭비이므로 **P0도 함께 죽는다.** dissolver는 "해소할 문제가 인용되고 있을 때"만 살아 있다.
4. **자기-종결(self-terminating)**: 위 어느 것도 아니어도 P0는 **1회성**이다. 한 번 돌아 O-A/O-B/무결정을 내면 완결된다. 재현·반복 method가 아니므로, "성공"의 정의가 곧 "종료"다 — 살아남아 반복되는 종류의 제안이 아니라는 점을 정직하게 명시한다.

---

DOSSIER_COMPLETE: platt_P0
