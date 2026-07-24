# E2 방법론 심층 도시에 — platt_P6

**제안 ID**: P6 — 관례-prior 명시 모델 (고전 ML · H3의 계측화 + E1 재해석)  
**좌석**: platt_strong_inferencer · seat_id=`platt_P6`  
**클러스터**: CL-I (관례-prior 계측화; feyerabend P7과 병합 후보)  
**작성 기준일**: 2026-07-18 (패킷 실측 다이제스트만 수치 인용)

---

## 1. 이론적 근거·선행연구

### 1.1 핵심 주장 (H3)과 이 제안의 역할

E2 프로그램에서 **H3**는 “벽 멤버십의 지배 신호가 기하(평행 이중선·두께·정션)가 아니라 **도면 관례**(레이어명, 블록명, 해치, 선폭·색)”라는 가설이다. P6는 H3를 일화·사후합리화에서 **측정치**로 바꾼다.

- **이기기 위한 모델이 아니다.** 피처를 의도적으로 빈약하게(기하 배제) 두면, (a) 관례가 재사용 가능하면 cross-project AUC가 이상하게 높고, (b) 프로젝트-국소면 within↑·cross↓로 강등이 정량화되며, (c) chance 근방이면 H3 kill이다.
- **부수 산출**: LLM `wall_likelihood`와 관례 점수의 상관은 E1/E1.5 silver가 **이름-prior를 탔는지**를 감사한다. 다이제스트상 탐지기↔silver Pearson 0.2911이고 name-blind 팔과 full-vs-nb=1.0(탐지기는 레이어명 신호 0)이므로, “탐지기 축은 이름-독립”은 이미 부분 확인됐다. P6는 **판정자(silver) 축**이 이름/관례에 얼마나 기대는지 별도 축으로 닫는다.

### 1.2 방법론 계보

| 계보 | 대표 기법·시스템 (일반 지식) | P6에서의 역할 |
|------|------------------------------|---------------|
| 도면/CAD 의미 레이어 관례 | AEC 실무의 AIA layer guidelines, ISO 13567 계열 레이어 명명, 국내 업체별 사내 코딩 (문헌·표준 일반 지식; 본 프로그램 실측 아님) | “관례 신호”의 존재 증명 — 그러나 **업체·프로젝트 국소성**이 H3의 핵심 위험 |
| 텍스트/범주 피처 → 고전 분류 | bag-of-tokens, TF–IDF, hashing trick; logistic regression; gradient boosting (Friedman GBM; LightGBM/XGBoost/HistGradientBoosting) | 투명·감사 가능·로컬 CPU 적합. CubiCasa 기하 GBDT(val F1 0.517/AUC 0.9215)와 **피처 패밀리를 직교**시켜 Occam 사다리의 “고전 ML 커버”를 채움 |
| 누출·일반화 진단 | group/project-level CV; nested CV; ablation of tautological features; label leakage audits (ML 일반 지식) | 프로젝트 단위 스플릿·동어반복 토큰 분리 보고가 **성과를 위장하는 누수**를 차단 |
| 도메인 적응 / prior 재사용 | empirical Bayes / hierarchical shrinkage; “firm lexicon” as site-specific prior (통계 일반 지식; 특정 논문 인용은 요검증) | within≫cross면 prior는 **적응 캘리브레이션**으로만 강등 (kill이 아닌 demote) |
| 판정자 독립성 감사 | concordance / disagreement structure; correlation of scores across axes (계량·심리측정 일반) | corr(LLM likelihood, convention score) ≥0.7 → E1 silver 독립성 demote — CL-E/PR-2의 대리 독립성 축과 맞물림 |
| 이름·토큰 포렌식 | P0의 top-20 블록명 토큰 분석(패널: ‘평면도’ 포함)과 연동 | P6의 피처 사전·동어반복 목록의 시드 |

요검증으로 남길 인용(확신 낮은 특정 논문 포인터): “CAD layer name as weak supervision for semantic segmentation”류의 개별 아카이브 논문 제목·연도는 본 패킷에 없으므로 **인용하지 않음**. 메커니즘만 계보로 사용.

### 1.3 왜 “기하 배제”가 방법론적으로 필수인가

다이제스트의 기하 학습 1단(HistGradientBoosting 6특징: parallel/thickness/junction/log길이/sin2θ/cos2θ)은 val F1 0.517·AUC 0.9215로 이미 **강한 기하 prior**를 입증했다. 여기에 레이어/이름을 섞으면 “관례가 이겼다”와 “기하가 이겼다”를 분리할 수 없다. P6는 **의도적 피처 고립(feature isolation)**으로 H3만 묻는다. 스태킹(후속 CL-F)에서 한계 기여(marginal contribution)를 볼 때도, 단독 관례 모델의 cross-project 곡선이 먼저 봉인돼야 해석이 닫힌다.

### 1.4 합성 truth가 왜 쓰이지 않는가

패킷 명시: **synthetic은 불가 — 합성물엔 관례가 없다.** B1 충실도 FAIL(KS 0.5792, TV 0.265)과 “벽 코드 0”인 생성기 공백(PR-1)은 별 이슈다. P6는 그 공백과 무관하게 **관례 부재**라는 더 근본적 이유로 합성을 truth/train에서 배제한다.

---

## 2. 알고리즘 정확 스펙

### 2.1 문제 정의

- **단위**: 핸들/세그먼트/도면정의 멤버 `i` (평가 단위는 프로그램 고정 per-handle `wall_member(h)`와 정렬; 도면정의 수준 집계는 보고용 보조).
- **라벨** `y_i ∈ {0,1}`: truth source §2.5 중 하나로 정의. 학습에 쓰는 source와 검증에 쓰는 source는 **순환 차단**을 위해 분리.
- **피처** `x_i`: 기하 좌표·길이·각도·평행·두께·정션 **일절 배제**. 관례 채널만.

### 2.2 관례 피처 채널 (의도적 빈약 집합)

각 엔티티/핸들에서 추출:

1. **레이어명 토큰**  
   - 원문 레이어 문자열 `L` → 정규화 `norm(L)`: NFKC, lower, 공백·`_-./` 분리, 한글/영문/숫자 토큰화.  
   - **cp949/UTF-8 함정**: 바이트→유니코드 실패 시 해당 토큰을 `�`/`REPLACEMENT`로 두지 말고 **드롭 + 카운터** (`n_decode_fail`). `PYTHONUTF8=1` 가정 하에 코드포인트 감사 로그.  
   - 토큰 집합 → multi-hot 또는 hashed bag (해시 차원 `D_h`, 기본 2^14).  
   - 문자 n-gram (2–4) 옵션 암: 한영 혼용·약어(`WAL`, `W-`, `벽체`) 포착.

2. **블록명 / INSERT 이름 토큰**  
   - INSERT의 블록 정의명, xref 논리명(가능 시). P0 top-20에 ‘평면도’ 등이 보인다는 패널 관찰을 **시드 사전**으로만 사용(학습 라벨로 쓰지 않음).

3. **해치 패턴**  
   - 패턴 이름(ANSI31 등), scale 구간 bin(로그 bin), 각도 bin(0–180°/15°).  
   - 패턴 미상·SOLID는 별도 범주.

4. **선폭·색 통계**  
   - lineweight 코드 또는 mm 환산 bin; ACI/truecolor 양자화(예: 16-bin hue + ByLayer/ByBlock 플래그).  
   - **도면 내 상대 빈도** 피처: 같은 레이어에서 해당 선폭이 차지하는 비율(전역 절대 선폭보다 관례에 가까움).

5. **명시적 배제**  
   - 좌표, 길이, 방향, 평행 쌍, 두께 gap, 정션 차수, bbox, 그래프 인접 — **전부 금지**.  
   - “레이어가 WALL이므로 평행일 확률” 같은 파생 기하도 금지.

### 2.3 동어반복(tautology) 토큰 분리

라벨어와 거의 동의인 토큰은 **주 모델에서 제거한 채** 별도 리포트:

- 영문: `wall`, `walls`, `w-wall`, `a-wall`, `s-wall` 등 (lexicon 동결본에 등재)  
- 한글: `벽`, `벽체`, `내벽`, `외벽`, `조적벽` 등  
- 레이어 가이드 잔여: `a-wall-*` 패턴 전체

**보고 의무**:  
- Model-A: tautology-stripped  
- Model-B: tautology-only  
- Model-C: full (참고용, 합격선 판정에 사용 금지)

합격선·kill은 **Model-A(및 필요 시 A vs B 대비)** 만으로 판정한다. Model-C가 강해도 “학습 성과”로 인용 금지.

### 2.4 모델

#### 2.4.1 Logistic regression (투명 baseline)

$$
p_i = \sigma(w^\top x_i + b), \quad
\mathcal{L} = -\sum_i \big[y_i\log p_i + (1-y_i)\log(1-p_i)\big] + \lambda \|w\|_2^2
$$

- 솔버: LBFGS 또는 SAGA (희소 multi-hot).  
- 하이퍼: `C ∈ {0.01, 0.1, 1, 10}`, class_weight `{None, balanced}`.  
- 출력: `p_i` = convention score; 계수 상위 토큰 표(해석 가능성).

#### 2.4.2 HistGradientBoosting / GBDT (주력)

CubiCasa 기하 암과 동일 계열로 비교 공정성 확보 (패킷: HistGradientBoosting 사용 실적).

- 손실: binary log-loss.  
- 하이퍼 공간(사전등록 그리드, val만):  
  - `max_depth ∈ {3,5,7}`  
  - `learning_rate ∈ {0.05,0.1}`  
  - `max_iter ∈ {100,200,400}`  
  - `min_samples_leaf ∈ {20,50,100}`  
  - `l2_regularization ∈ {0, 0.1, 1}`  
- **조기 종료**: val AUC 기준.  
- 피처 중요도: permutation importance (토큰 해시 충돌 보정 위해 원본 토큰 그룹 단위 중요도 보조).

로지스틱이 기하 암에서 F1 0.053으로 선형 불충분했던 것과 달리, 관례는 토큰 지시가 **거의 선형**일 수 있다. 따라서 로지스틱이 GBDT에 근접하면 “관례=사전에 가까운 규칙” 해석이 강화된다.

### 2.5 Truth sources (순환 차단)

| ID | Source | 사용 | 금지 |
|----|--------|------|------|
| T-a | FloorPlanCAD 레이어/메타(가용 시) | 보조 사전학습·lexicon 시드 | CubiCasa 벡터 라벨과 혼용 시 프로젝트 키 공유 금지 |
| T-b | Concordance: P1/P3 기하-검증 벽과의 일치 | **검증·held-out** | 동일 핸들을 스태킹 훈련 라벨로 재사용 금지 — **셋 분리** |
| T-c | Cross-project held-out 곡선 자체 | 일반화 판정(주 지표) | within만으로 H3 “지지” 선언 금지 |

**스태킹 훈련셋**과 **concordance 검증셋**은 핸들·도면·프로젝트 교집합이 0이어야 한다. 의사코드:

```
projects = infer_project_id(drawings)   # 보조가정 — 규칙 감사 대상
folds = GroupKFold(groups=projects)

for train_proj, test_proj in folds:
    assert set(train_proj).isdisjoint(test_proj)
    X_tr, y_tr = build_convention_features(train_proj, truth=T_train)
    X_te, y_te = build_convention_features(test_proj, truth=T_eval)
    # T_train ∩ concordance_for_stacking_labels = ∅
    fit(Model-A on train); evaluate AUC/F1 on test
```

### 2.6 프로젝트 단위 스플릿 (누수 방지의 핵심)

도면 단위 랜덤 스플릿은 **같은 프로젝트의 레이어 코딩 관례가 구조적으로 누수**한다. 필수:

- `project_id` 유도 규칙(파일명 접두, 디렉터리, xref 트리, 메타 JSON)을 **보조가정으로 문서화**하고, 오유도율 감사 셀을 둔다(§6 Cell-PID).  
- GroupKFold / leave-one-project-out.  
- 보고: **within-project AUC**와 **cross-project AUC**를 항상 쌍으로.

### 2.7 E1 상관 통계

엔티티/def 단위로:

- `s_conv = Model-A.predict_proba`  
- `s_llm = wall_likelihood` (E1/E1.5 silver; name-blind·full 각각)  
- 지표: Pearson / Spearman / point-biserial(`s_conv` vs 이진 truth)

프리레그 밴드(패킷 초안, 봉인 대상):

- `corr(s_llm, s_conv) ≥ 0.7` → E1 silver 독립성 **demote** (E1.5 해석 테이블 주입)

### 2.8 Cheapest probe (수 시간, 로컬)

전체 GBDT 전에:

1. 384-def 벤치(1.dwg staged DXF 축)에서 레이어/블록 토큰 빈도표.  
2. 현행 v0 쌍-밀도(또는 wall score)와의 **point-biserial**.  
3. 동어반복 토큰 유무 ablation 한 방.

이 probe가 chance 근방이면 본실험 예산을 축소하고 H3 kill 후보로 조기 에스컬레이션.

### 2.9 입·출력 계약

**입력**

- DXF/IR 엔티티 스트림: layer, block name, hatch, lineweight, color, handle, `project_id`  
- truth 조인 키: handle 또는 SEG-IR edge id  
- (선택) E1 likelihood 테이블

**출력**

- `convention_score.parquet`: handle, project_id, p_A, p_B, p_C, fold_id  
- `metrics.json`: within/cross AUC·F1·P·R, shuffle control AUC  
- `token_report.md`: 상위 계수/중요도, tautology 분리표, decode fail 카운트  
- `e1_corr.json`: LLM↔convention 상관 + name-blind 대비

---

## 3. 벽 과업 적응 설계

### 3.1 세 축 접속

#### (1) CubiCasa5k SEG-IR 벡터축

- 변환은 **레이어 중립**(라벨 누출 0) — 즉 CubiCasa IR에는 CAD 관례 레이어가 **없다**.  
- 함의: CubiCasa는 P6의 **주 훈련장이 될 수 없다.** 기하 GBDT(val P 0.860/R 0.370/F1 0.517/AUC 0.9215)와 직교하는 관례 암을 여기에 붙이면 피처가 공허하다.  
- 허용 사용: (i) 기하 모델과의 **스태킹 한계 기여**를 측정할 때 “관례 피처=0” 통제 셀, (ii) “관례 없는 분포에서의 chance floor” 확인.

#### (2) FloorPlanCAD 래스터축

- 래스터 5,308장+벽 bbox/segmask, **벡터 SVG 없음**.  
- 레이어 메타가 **가용한 서브셋**만 T-a. 메타 없으면 P6 학습 제외(래스터 픽셀은 관례 토큰이 아님; CL-G 영역).  
- FPC에서 레이어 문자열이 있으면: 프로젝트/출처 단위 스플릿으로 lexicon·Model-A 예비 훈련.

#### (3) 1.dwg 실도면축 (도면정의 384 / 최대 412,965 선분)

- **관례 신호의 본진.** 레이어·블록·해치·선폭·색이 실존.  
- B3 벽-제로율 v0 0.682→0.2135 PASS, B5 Pearson 0.2911, 탐지기 레이어 신호 0 — P6는 탐지기가 안 쓰는 채널을 **명시 모델**로 올린다.  
- 아카이브 145장(패킷 mechanism)으로 cross-project 곡선을 그리는 것이 주 실험. 384-def는 cheapest probe·E1 상관의 1차 무대.

### 3.2 전이 실패 0.236과 기하 GBDT 0.517을 아는 상태에서 P6가 가져오는 것

| 기존 결과 | 함의 | P6 추가분 |
|-----------|------|-----------|
| 기하 탐지기 전이 val F1 0.2358 (P≈기저율) | 물리 두께 prior 무력, FP=화살표/문/창/치수 등 평행 구조 | 관례 점수로 **평행 비벽**을 이름·해치·선폭으로 걸러낼 수 있는지**를 기하와 독립 측정 |
| 기하 GBDT F1 0.517 / AUC 0.9215 | 기하만으로도 강함 | 스태킹 시 관례의 **한계 기여≈0**이면 타이브레이커로 demote (패킷 kill/demote) |
| 탐지기 layer 가중 0.20 but name-blind 동일 | v0 구현상 레이어 채널이 실질 0 | P6는 “가중치 슬롯”이 아니라 **학습된 관례 prior**로 H3를 재시험 |
| silver Pearson 0.2911, 5기≈2가문 | 판정자 독립성 취약 | corr(LLM, convention)로 **이름-prior 탑승** 정량화 → E1.5 해석 테이블 |

P6가 **CubiCasa F1을 올리는 방법**이 아님을 명확히 한다. 가져오는 것은 (1) H3 생사, (2) silver 독립성 감사, (3) 고전 ML 사다리의 관례 칸 채움이다.

### 3.3 CL-I 조건과의 정합

패널: CL-I 조건 = firm-특유 벽레이어 lexicon 구축·동결(T14/T33) + 프로젝트 단위 스플릿 + 동어반복 분리 보고.  
본 도시에 스펙은 그 조건을 **알고리즘 전제**로 내장한다. lexicon 미동결 시 본실험(Cell-XP) 착수 금지.

---

## 4. 데이터·컴퓨트 요구

### 4.1 자산 매핑 (실행 가능성)

| 자산 | P6 역할 | 비고 |
|------|---------|------|
| 145 아카이브 DWG/DXF | 주 학습·cross-project | 관례 존재 |
| 1.dwg / 384-def | probe + E1 상관 | 선분 최대 412,965 → 피처는 엔티티 메타라 CPU 충분 |
| CubiCasa SEG-IR | 관례=0 통제·스태킹 대조 | 레이어 중립 |
| FloorPlanCAD | T-a 메타 가용 시만 | 벡터 없음 |
| qwen2.5-VL / 프런티어 VLM | **불사용** | P6 범위 외 |
| RTX 5070 Ti 16GB | **불필요**(옵션: 미사용) | 패킷: GPU/DGX 불사용 |
| RAM 64GB | 토큰 행렬·해시 피처 | 충분 |
| DGX Spark (unreachable) | **계획만 분리, 실행 0** | 아래 4.3 |

### 4.2 로컬 CPU 계획 (실행 본선)

1. Lexicon 동결 스크립트 + 토큰 빈도표 (≤2h)  
2. Cheapest probe on 384-def (수 시간)  
3. 145장 피처 추출 → scipy/sklearn CSR 또는 row-wise hashing (반나절~1일)  
4. GroupKFold × {LogReg, HGB} × {A,B,C} (1–2일 CPU)  
5. E1 상관·셔플 대조군·xlsx 증거 패키징 (반나절)

메모리: hashed `D_h=2^14`, 엔티티 N≈O(10^6)이어도 CSR로 수 GB 내. 412,965 선분 단일 도면도 스트리밍 추출 가능.

### 4.3 DGX 계획 (비활성)

- Ornith-35B/VLM 파인튜닝·대량 silver 재생성은 P6에 **불필요**.  
- DGX unreachable이므로 “대기 큐에 올리지 않음”.  
- 추후 145≫스케일 아카이브가 생기면 동일 CPU 파이프라인을 스케일아웃; GPU 이식 없음.

### 4.4 라이선스·권리 전제

외부셋 학습 arm 일반 원칙(PR-3)은 CubiCasa/FPC **학습**에 적용. P6 주 데이터가 사내/아카이브 145라면 counsel 범위는 해당 아카이브 이용 조건으로 한정하되, FPC 메타를 T-a로 쓰는 순간 **PR-3 클리어가 하드 게이트**.

---

## 5. 구현 계획

### 5.1 모듈·파일 골격 (신규 — 본 패킷은 도시에만 작성; 아래는 실행 시 CHANGE 후보 설계)

```
convention_prior/
  lexicon/
    freeze_lexicon.py      # T14/T33: firm wall-layer lexicon 동결
    tautology_list.yaml    # 동어반복 토큰 봉인
  features/
    extract_convention.py  # layer/block/hatch/lw/color → hashed X
    normalize_tokens.py    # NFKC, UTF-8 audit, cp949 trap counters
    project_id.py          # 유도 규칙 + 감사 로그
  models/
    train_logreg.py
    train_hgb.py
    eval_group_kfold.py
  probes/
    cheapest_probe_384.py  # 빈도표 + point-biserial vs v0
    e1_correlation.py
  evidence/
    write_xlsx.py          # 평가 원칙: 증거 xlsx 의무
```

### 5.2 기존 도구 접속점

| 기존 | 접속 방식 |
|------|-----------|
| `cubicasa_ir` | 스태킹/통제 셀에서 edge id 조인; 관례 피처는 비어 있음 명시 |
| `cubicasa_ml` | HistGradientBoosting 파이프라인·셔플 대조군 패턴 재사용; **피처 빌더만 교체** |
| `fast_score` / 탐지기 v1 | 기하 점수와 convention score의 상관·스태킹 한계 기여; layer 채널 가중 0.20 슬롯을 P6 점수로 치환하는 ablation은 별 셀 |
| `evidence_grid` | within/cross·Model-A/B/C·shuffle을 그리드 행으로 기록 |

탐지기 v1 구조(parallel 0.35/thickness 0.25/junction 0.20/layer 0.20)와의 관계: P6 점수는 `layer` 항의 **학습된 대체재** 후보이지, v1을 즉시 변조하지 않는다. 변조는 H3 지지 밴드 통과 후 CL-B/CL-F 쪽에서.

### 5.3 예상 개발 규모

- Lexicon+추출+정규화: ~1.5–2.5 엔지니어-일  
- 학습·GroupKFold·증거: ~1–2 엔지니어-일  
- E1 상관·문서화: ~0.5 일  
- **총칼**: 약 3–5 엔지니어-일 (본실험; cheapest probe는 그 전 0.5일)

의존: T14/T33 lexicon 동결, project_id 규칙 감사, (FPC 사용 시) PR-3.

---

## 6. 실험 셀 정의

공통 원칙: val=개발·튜닝 허용, test=방법당 단발, 합격선 프리레그 봉인, 셔플 대조군 의무, 증거 xlsx, 실패도 기록.  
수치 합격선은 패킷 **prereg band 초안**을 그대로 봉인 후보로 사용(Paul 확정 전 candidate).

### Cell-LEX — Lexicon 동결 (선결)

| 항목 | 내용 |
|------|------|
| 가설 | firm-특유 벽레이어·블록 토큰 목록을 시험 전에 봉인하면 사후 피팅을 차단한다 |
| 지표 | lexicon 버전 해시, 토큰 수, tautology 목록 크기, inter-annotator(가능 시) |
| 합격선 | 해시 고정 + tautology_list 비공집합 + 변경 시 새 실험 ID |
| 킬 | 동결 없이 본실험 착수 → 절차 kill (결과 무효) |
| 예산 | 0.5–1일, 로컬 |
| 시드 | N/A (규칙 동결); 목록 작성자·일자 기록 |

### Cell-PID — project_id 유도 감사 (보조가정)

| 항목 | 내용 |
|------|------|
| 가설 | 파일명/xref 기반 project_id가 실제 관례 클러스터와 일치한다 |
| 지표 | 수동 표본 일치율(예: 30도면), 동일 레이어코딩이 다른 project_id로 쪼개진 비율 |
| 합격선 | 사전등록 일치율 하한(예: ≥0.9 — **요검증·Paul 봉인**); 미달 시 규칙 수정 후 재동결 |
| 킬 | 일치율 낮음에도 GroupKFold 강행 → cross 지표 해석 불가 (실험 무효) |
| 예산 | 0.5일 |
| 시드 | 표본 추출 seed=20260718 |

### Cell-CP — Cheapest probe (384-def)

| 항목 | 내용 |
|------|------|
| 가설 | 관례 토큰 빈도만으로도 v0 쌍-밀도와 유의미한 point-biserial이 나온다 |
| 지표 | point-biserial r, 상위 토큰 표, tautology-stripped vs full |
| 합격선 | 탐색적 — \|r\| 효과크기 기록; 본실험 go/no-go는 운영 판단 |
| 킬 | 조기 경고: tautology-stripped에서 chance 수준이면 Cell-XP 축소 |
| 예산 | 수 시간, CPU |
| 시드 | 토큰 해시 seed=42 |

### Cell-XP — Cross-project 주 실험 (H3 판정)

| 항목 | 내용 |
|------|------|
| 가설 | 기하 없는 관례 모델이 cross-project로 일반화되면 H3(재사용 prior) 지지 |
| 지표 | AUC, F1, P, R — **within vs cross** 쌍; Model-A 기준; 셔플 AUC |
| 제안 합격선 (prereg 초안) | cross AUC ≥0.75 → 재사용 prior로 H3 지지; within ≥0.9 & cross ≤0.6 → H3 demote(프로젝트-국소) |
| 킬 조건 | cross AUC ≤0.55 → **H3 kill**; 셔플 AUC가 본 AUC에 근접하면 누수/버그 kill |
| 예산 | 1–2일 CPU; GPU 0 |
| 시드 | GroupKFold shuffle seed ∈ {0,1,2} 보고; 모델 seed=0 고정 1회 + 민감도 2회 |

### Cell-TAU — 동어반복 분리 보고

| 항목 | 내용 |
|------|------|
| 가설 | 성능의 상당 부분이 WALL/벽 토큰 누수다 |
| 지표 | AUC_A, AUC_B, AUC_C; Δ(C−A) |
| 합격선 | 판정은 A만; Δ(C−A) 크면 누수 경고 플래그 |
| 킬 | C만 인용한 H3 지지 주장 → 보고서 무효 |
| 예산 | Cell-XP에 포함 |
| 시드 | 동일 |

### Cell-E1C — LLM likelihood ↔ 관례 점수

| 항목 | 내용 |
|------|------|
| 가설 | E1/E1.5 silver가 이름-prior를 탄다 |
| 지표 | Pearson/Spearman(s_llm, s_conv); name-blind vs full 각각; 가문별(fable+sol vs opus+sonnet+grok) |
| 합격선 | corr ≥0.7 → E1 silver 독립성 demote (해석 테이블 주입) |
| 킬 | 해당 없음(감사 셀); 단 s_llm 미조달 시 deferred |
| 예산 | 0.5일 + E1 아티팩트 존재 전제 |
| 시드 | 상관은 결정론 |

### Cell-STK — 스태킹 한계 기여 (기하 대비)

| 항목 | 내용 |
|------|------|
| 가설 | 기하 GBDT/탐지기에 관례 점수를 더해도 한계 이득이 있다 |
| 지표 | ΔF1/ΔAUC on val; concordance 검증셋은 훈련과 분리 |
| 합격선 | 사전등록 Δ 하한(예: ΔAUC≥0.02 — Paul 봉인); 미달 ≈0 → 타이브레이커 demote |
| 킬 | 한계 기여 ≈0 → 지배 메커니즘 아닌 보조로 demote (H3 kill과 별개 조항) |
| 예산 | 1일; CubiCasa에서는 관례=0 통제만 |
| 시드 | 기하 모델 고정 체크포인트 + convention seed=0 |

### Cell-SHUF — 셔플 대조군

| 항목 | 내용 |
|------|------|
| 가설 | 라벨 셔플 시 AUC≈0.5 (CubiCasa 기하 암 셔플 0.375 PASS 패턴 준용) |
| 지표 | shuffle AUC |
| 합격선 | 본 AUC − shuffle AUC 간격 충분(사전등록); shuffle≫0.5면 버그 |
| 킬 | shuffle 실패 시 Cell-XP 해석 금지 |
| 예산 | Cell-XP의 20% |
| 시드 | permutation seeds={0,1,2,3,4} |

### 셀 수에 대한 정당화

과소 금지: H3 생사(XP)·누수(TAU)·E1(E1C)·스태킹(STK)·선결(LEX/PID)·probe(CP)·shuffle이 각기 다른 가설을 닫는다.  
과잉 금지: 아키텍처 탐색·GPU·VLM·합성 truth 셀은 두지 않는다.

---

## 7. red team 티켓 응답

패널: CL-I = platt P6 + feyerabend P7; 조건 T14/T33. 관련 OPEN 티켓을 지목한다(상세 원문 `seats/red_teamer.md` — 본 패킷에 severity만 요약됨).

### T14 / T33 — firm lexicon 구축·동결

- **입장**: **수용 + 선결 게이트**. Cell-LEX 통과 전 Cell-XP 착수 금지.  
- **해소**: tautology_list와 firm lexicon을 버전 해시로 봉인; 변경 시 실험 ID 갱신.

### T1 — 대리(truth proxy) 독립성 (sev 0.75, 최우선)

- **입장**: P6는 독립성 **감사 도구**로 기여한다(E1C). 동시에 concordance(T-b)를 라벨로 쓰면 기하 대리와 상관된 라벨을 관례 모델이 맞히는 순환 위험.  
- **해소**: 스태킹 훈련 라벨과 concordance 검증 셋 분리(§2.5); CL-E 3원 불일치와 지표 공유.  
- **잔여 위험**: 인정 — T-b만의 “성공”을 H3 지지로 과장하지 않음; cross-project(T-c)를 주 판정으로 유지.

### T5 / PR-3 — FloorPlanCAD·CubiCasa NC·권리

- **입장**: CubiCasa는 관례 공허로 **주 학습 제외** → T5 직접 노출 감소. FPC 메타(T-a) 사용 시에만 counsel 클리어 필수.  
- **해소**: T-a 암 go/no-go를 PR-3에 묶음.

### T3 / T4 / T8 — E1 법의학·정렬 아티팩트 (CL-A)

- **입장**: E1C는 CL-A 이후가 안전. 정렬-키 아티팩트가 likelihood를 왜곡하면 corr 해석이 붕괴.  
- **해소**: Cell-E1C를 CL-A PASS 이후로 스케줄; 미완 시 deferred로 기록(위조 상관 금지).

### T10 / T23 — Graph IR·인용 게이트 (CL-F 인접)

- **입장**: P6 단독에는 비필수. 스태킹(Cell-STK)이 GNN/Graph 경로와 맞닿을 때만 상속.  
- **해소**: STK를 고전 기하 GBDT/탐지기 v1에 한정해 T10을 우회 가능.

### T22 — P1 대비 lift 밴드

- **입장**: 관례 단독 셀은 P1 lift와 무관. STK demote 조항만 P1/기하 강도와 연동.  
- **해소**: XP의 H3 판정을 STK와 분리 보고.

### 공격 F / T7 — metamorphic sentinel (CL-D)

- **입장**: 관례 모델은 레이어개명 metamorphic에 **의도적으로 취약**할 수 있음(관례 파괴=신호 파괴).  
- **수용**: 레이어개명 팔에서 성능 하락은 H3 지지 증거로 전용 가능; “불변 실패”로 P6를 죽이지 않음. 대신 **개명 불변을 요구하는 산출물**에는 convention score를 단독 SoT로 쓰지 않음.

### 라이선스·합성 관련 T2

- **입장**: 합성 관례 부재로 PR-1과 비결합. T2는 P6 블로커 아님.

---

## 8. 인접 제안과의 관계

### 8.1 병합 가능 지점

| 대상 | 관계 |
|------|------|
| **feyerabend P7** | CL-I 공동 — lexicon·관례 감사; 본 도시에의 실험 셀 제공, P7은 반관례/남용 경계 강화에 사용 가능 |
| **platt P0** | 토큰 시드·‘평면도’ 등 top-20 관찰 → lexicon 시드; P0 법의학 후 E1C |
| **CL-A (E1 감사)** | E1C의 선결; 이름-prior 탑승의 공유 |
| **CL-E / doe P3** | 대리 교차·불일치; convention score를 제4 축으로 추가 가능 |
| **CL-F / platt P2** | Occam 사다리: 관례 LogReg/GBDT가 먼저; 한계 기여≈0이면 심층 관례 암 불요 |
| **CL-B / 탐지기 v1** | layer 0.20 슬롯의 학습 prior 후보; 단 H3 밴드 통과 전 병합 금지 |
| **CL-K / feyerabend P3** | silver 비학습 입장과 정합 — P6는 silver를 **타깃이 아니라 상관 감사 대상**으로만 사용 |

### 8.2 차별점

- **vs 기하 GBDT (CubiCasa 학습 1단)**: 피처 직교(관례 only). 목적 함수가 F1 최대화가 아니라 **H3 가설 판정**.  
- **vs 탐지기 v1 layer 가중**: 고정 가중이 아니라 데이터-적합 토큰 prior + 일반화 곡선.  
- **vs VLM/CL-G**: 픽셀·API·DGX 불필요; 실패해도 저가.  
- **vs RL/CL-H**: per-handle 지도 분류의 감사 암이지 집합-조립이 아님.

### 8.3 이 제안이 죽어야 하는 조건 (정직)

1. **H3 kill (패킷)**: cross-project AUC ≤0.55 (Model-A, 셔플 통과 전제) → 관례를 지배 메커니즘으로 주장 금지.  
2. **누수 폭로**: Model-A는 chance인데 Model-C만 강함 → “성과” 서사 kill; 재설계 없이는 부활 금지.  
3. **project_id 붕괴**: Cell-PID 실패로 cross/within 구분 불가 → 곡선 해석 kill.  
4. **Lexicon 미동결 본실험**: 절차적 무효.  
5. **스태킹 한계 기여 ≈0** (패킷): 지배가 아니라 타이브레이커로 **demote** — 연구선으로서의 P6 “본선”은 종료, 보조 채널만 잔존.  
6. **E1 아티팩트 미해소 상태에서 corr로 silver를 처형**: CL-A 전 demote 선언 금지 (잘못된 kill 방지).  
7. **권리 미클리어 FPC 학습**: T-a 암 삭제; 145 아카이브조차 권리 문제면 프로그램 레벨에서 P6 중단.

Demote( within≥0.9 & cross≤0.6 )는 **죽음이 아니라 강등**: 프로젝트-국소 적응 캘리브레이션으로만 생존. 이때도 “재사용 가능 H3 prior” 주장은 죽인다.

### 8.4 프로그램 선결과의 우선순위

P6/CL-I는 VIABLE 밴드다. TOP인 CL-A·CL-B·CL-D·CL-E·PR-1보다 앞설 필요는 없다. 다만 **cheapest probe(Cell-CP)** 와 **lexicon 동결(Cell-LEX)** 은 저가라서 CL-A와 병행 가능하고, silver를 소비하는 모든 실험에 대해 E1C는 **보조가정 통제**로 일찍 넣는 편이 싸다.

---

## 부록 A — 프리레그 밴드 요약 (봉인 후보)

| 조건 | 판정 |
|------|------|
| cross-project AUC ≥ 0.75 (Model-A) | H3 지지 (재사용 prior) |
| within ≥ 0.9 & cross ≤ 0.6 | H3 demote (프로젝트-국소) |
| cross ≤ 0.55 | **H3 kill** |
| corr(LLM, convention) ≥ 0.7 | E1 silver 독립성 demote |
| 스태킹 한계 기여 ≈ 0 | 타이브레이커 demote |
| shuffle 대조 실패 | 실험 무효 |

## 부록 B — 수치 인용 출처

본문 수치( B1 KS/TV, B2/B3/B4/B5, CubiCasa 분할·F1·GBDT, 탐지기 가중, 하드웨어, 384/412965 등)는 전부 패킷 **실측 다이제스트 (2026-07-18)** 및 패널 보고서 서술에서만 인용했다. 그 외 표준·알고리즘명은 일반 지식이며 개별 논문 페이지 인용은 요검증으로 표시하거나 생략했다.

DOSSIER_COMPLETE: platt_P6
