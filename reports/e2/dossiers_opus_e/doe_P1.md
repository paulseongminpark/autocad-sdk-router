# 도시에(dossier) — doe_P1 · MASTER FACTOR SCREEN

> **좌석(seat)**: doe_experimentalist · **제안 ID**: P1 · **flagship**
> **한 줄 정의**: 탐지기 설계 선택 6개를 2수준 요인(2-level factor)으로 놓고, 64개 전조합 대신
> **16번의 직교 실행(orthogonal run)** 한 배치로 6개 main effect와 핵심 2요인 상호작용(2-factor
> interaction, 이하 2FI)을 동시에 추정하는 분수요인 스크린(fractional-factorial screen)이다.
> **핵심 질문**: "학습이 결정론을 이기나?"를 단독으로 묻지 않고, "학습의 우위가 표현(representation)·
> 정답원(truth source)과 **간섭하는가?**"를 묻는다.

**노력 모드 로그(R8)**: 본 도시에는 패킷이 "깊이 우선·분량 무제한, 8절 전부 채움"을 명시 요청했으므로
전면(thorough) 모드로 작성한다 — 신호 ①(명시 요청)에 근거. 실측 신규 측정은 하지 않으며(패킷 계약),
모든 수치는 패킷 다이제스트 인용 또는 방법론 일반지식(문헌)임을 구분 표기한다.

---

## 0. 이 문서를 읽는 법 (용어 봉투 열기)

이 스크린을 처음 보는 사람을 위해 세 개의 코어 용어를 먼저 일상어로 푼다. 이후 본문은 이 정의를
전제한다.

- **OFAT(one-factor-at-a-time, 한 번에 한 요인)**: 지금 프로그램이 쓰는 방식. "결정론 탐지기 만들어
  점수 → 그래프 탐지기 만들어 점수 → …" 식으로 **한 선택지만 바꿔가며** 비교한다. 문제는 선택지들이
  서로 **간섭할 때**다. 예컨대 "학습은 래스터에서만 이기고 그래프에서는 결정론과 동률"이라면, 그래프
  위에서만 비교한 OFAT는 "학습 무익"이라는 **틀린 일반화**를 내놓는다.
- **요인 스크린(factorial screen)**: 여러 선택지(요인)를 **동시에** 켜고 끄며 한 배치로 돌려, 각 요인이
  반응(response)을 얼마나 움직이는지(main effect)와 요인들이 **서로 간섭하는지**(interaction)를 한꺼번에
  추정한다. 계열(family)이 **요인의 한 수준**이 되므로, 스크린 하나가 전 계열을 관통한다("여러 계열을
  고루 커버"를 낭비 없이 달성 — 평가기준 5).
- **별칭(alias / confounding, 교락)**: 실행 수를 64→16으로 줄이면 공짜가 아니다. 일부 효과가 서로
  **구별 불가능하게 겹친다**. 이 겹침의 지도가 "resolution·별칭 사슬(alias chain)"이며, 이 스크린의
  청구서(bill)에 반드시 찍혀야 하는 항목이다. 잊으면 "겹친 두 효과 중 하나를 깨끗한 결론으로 오독"하는
  대표적 실패(card 금지수)에 빠진다.

본 스크린이 **답하도록 설계된 것**과 **원리적으로 못 답하는 것**을 미리 못박는다:

- **답한다**: 6개 요인 각각의 main effect(반응을 움직이나/안 움직이나), main effect가 2FI와 뒤섞이지
  않음(Res IV의 보장), 그리고 **어느 2FI 사슬이 활성인가**.
- **못 답한다**(§부록 abstentions): 별칭된 2FI 쌍을 서로 분리(예 `A×C`를 `B×E`에서 못 가름), learned를
  `{GNN, VLM}`로 세분, 요인 목록에 없는 벽-정의 신호(해치 poché·텍스트 라벨 등)의 발명, 비설정
  관측변수(도면 밀도 등)에 대한 인과 주장.

---

## 1. 이론적 근거·선행연구 (methodological lineage)

### 1.1 계보 — 산업통계 실험계획의 정통 라인

이 제안은 새 방법이 아니라 **실험계획법(Design of Experiments, DOE)의 정통(canonical) 도구**를 ML 설계
공간에 적용한 것이다. 계보는 다음과 같다(연도·귀속은 방법론 일반지식이며, 세부 연도는 '요검증' 표기).

- **완전요인·요인배치의 기원**: R. A. Fisher, *The Design of Experiments*(1935 근처, 요검증) — 농업
  시험에서 "한 번에 하나"의 비효율을 지적하고 **요인을 동시에 교차**하는 배치를 정립. "OFAT는
  상호작용을 구조적으로 못 본다"는 본 제안의 출발점이 여기다.
- **분수요인설계(fractional factorial)**: Finney(1945 근처, 요검증)가 완전요인의 일부만 골라 도는
  분수설계를 형식화. 실행수를 지수적으로 줄이되, 그 대가로 별칭이 생긴다는 트레이드오프를 명시.
- **해상도(Resolution) 개념**: Box & Hunter(1961 근처, 요검증). Resolution **R**은 "가장 짧은 정의어
  (defining word)의 길이"로, main effect가 얼마나 낮은 차수의 상호작용과 별칭되는지를 한 글자로 요약한다.
  Res III=main이 2FI와 별칭, Res IV=main은 2FI와 안 겹치나 2FI끼리 겹침, Res V=2FI도 서로 안 겹침. **본
  설계는 Res IV** — 정확히 "main은 깨끗, 2FI는 사슬로 묶임"의 지점이다.
- **표준교재**: Box·Hunter·Hunter, *Statistics for Experimenters*(요검증) — 분수요인·fold-over의 실무
  바이블. Montgomery, *Design and Analysis of Experiments*(요검증) — 표준 강의교재. Wu & Hamada,
  *Experiments: Planning, Analysis, and Optimization*(요검증) — effect sparsity/hierarchy/heredity 원칙의
  현대적 정리.
- **스크리닝 전용설계**: Plackett–Burman(1946, 요검증) — Res III로 극소 실행에 다수 요인. 본 제안은
  PB보다 한 급 위(Res IV)를 택했다 — 2FI가 main을 오염하지 않게 하려는 의도적 선택.
- **비복제 요인분석(unreplicated factorial analysis)**: 16런은 셀당 1반복이라 고전적 잔차분산 추정이
  약하다. 이를 다루는 두 축이 본 제안의 통계 심장이다 — (a) **Daniel(1959, 요검증)의 half-normal plot**
  으로 활성 효과를 눈으로 가려내고, (b) **Lenth(1989, 요검증)의 PSE(pseudo standard error)**로 잔차분산
  없이 margin of error(ME)를 계산한다. 패킷 prereg_model이 명시 인용한 "Lenth PSE, |effect|>ME"가 바로 이것.
- **효과 희소성·계층 원칙(sparsity / hierarchy / heredity)**: "활성 효과는 소수이고(sparsity), 저차가
  고차보다 크며(hierarchy), 상호작용은 그 부모 main이 활성일 때 잘 활성(heredity)"이라는 경험칙. 본
  스크린이 "활성으로 드러난 소수 요인만 후속으로 넘긴다"는 전략의 이론적 정당화다.
- **강건설계(robust parameter design)**: Taguchi(요검증)의 inner/outer array·crossed array. 본 제안의
  noise_factors 절 — "도면 population을 각 셀에 동일 적용(crossed), 밀도·단위·layer-naming을 outer 잡음
  으로만" — 은 정확히 Taguchi식 교차배치의 사고다(단, S/N비 통계는 **순수 결정 축에 수입 금지**, card
  rule 7 — 1.4 참조).
- **후속 단계의 이론**: 활성 요인이 소수로 좁혀지면 **반응표면법(Response Surface Methodology, RSM;
  Box–Wilson 1951 근처, 요검증)**으로 3~4수준 세분·곡률 추정으로 넘어간다. 본 스크린은 RSM의 **1단계
  (screening)** 이다. 순서가 뒤집히면(세분부터) 낭비다.

### 1.2 왜 "정통 DOE"가 ML/딥러닝 설계공간에 맞는가

ML 실무의 "ablation study"는 사실상 OFAT다 — 한 컴포넌트씩 빼며 성능을 본다. 이는 컴포넌트 간
**상호작용을 놓친다**. 요인설계를 하이퍼파라미터/아키텍처 선택에 적용하려는 시도는 문헌에 존재하지만
(예: 신경망 하이퍼파라미터 튜닝에 fractional factorial·Taguchi를 쓴 사례들, 구체 논문명은 확신 없어
'요검증'), 본 프로그램에서의 참신함은 **계열(model family) 자체를 요인의 한 수준으로 승격**한 점이다.
즉 "결정론 vs 학습"을 별도 실험이 아니라 스크린의 한 축(B)으로 넣어, "학습의 우위"가 다른 설계선택과
간섭하는지를 **직접 추정 가능한 파라미터**로 만든다.

### 1.3 대안 설계와의 비교 (왜 하필 2^(6-2) Res IV인가)

- **완전요인 2^6=64런**: 모든 2FI·고차까지 깨끗. 그러나 학습 셀 포함 시 비용 4배. 스크리닝 목적엔 과잉.
- **Plackett–Burman N=12 (Res III)**: 더 싸지만 main이 2FI와 별칭 → "학습 우위"가 어떤 2FI와 뒤섞여
  main 해석 자체가 위험. 본 프로그램의 핵심 질문(간섭 여부)과 상충.
- **Definitive Screening Design(DSD; Jones & Nachtsheim 2011 근처, 요검증)**: 3수준, main이 2FI와
  전혀 별칭 안 되고 일부 2FI·곡률도 추정. 요인이 연속형일 때 매력적. **그러나 본 6요인은 전부 범주형
  2수준(그래프/래스터, 결정/학습 등)** 이라 3수준·곡률의 의미가 없다 → DSD 이점 소멸. 그래서 2수준
  분수요인이 정답.
- **2^(6-2) Res IV (채택)**: 16런. main 깨끗, 2FI는 7개 사슬로 묶임. 분리가 필요하면 **fold-over 8런
  추가로 Res V 승격**(1.3의 확장 경로). 스크리닝 목적·범주형·후속 확장성의 균형점.

### 1.4 이 계보가 강제하는 규율 (card rules)

- **card rule 4 (상호작용 우선)**: "학습이 낫다"의 단독 스토리는, model-family×representation 상호작용이
  활성이면 반증된다. 본 스크린은 이 반증을 **검출하도록** 설계됐다.
- **card rule 7 (결정 축에 잡음통계 금지)**: B=deterministic 셀은 (config, 도면) 고정 시 순수 함수 →
  셀내 반복·분산추정 무의미. S/N비·반복분산을 순수 결정 축에 수입하지 않는다. 잡음모형은 오직 학습
  seed 축과 `T-SILVER`(LLM 비결정) 축에만.
- **금지수(비설정 변수의 요인화)**: 도면 밀도·단위·layer-naming은 **설정 불가 관측변수** → 요인이 아니라
  outer 잡음/블록으로만 취급. 이를 요인으로 올리면 인과 주장이 불가능한 것에 인과 라벨을 붙이는 오류.

---

## 2. 알고리즘 정확 스펙 (exact spec)

### 2.1 요인·수준 (factors & levels)

| 코드 | 요인(factor) | 수준 −1 | 수준 +1 | settable | 근거 |
|---|---|---|---|---|---|
| A | representation | graph-IR | raster | Y | 입력 기질. graph-IR=핸들그래프(R23 실측), raster=render 파이프 |
| B | model_family | deterministic | learned | Y | 1차 2분. 활성이면 후속서 learned를 {GNN,VLM}로 분해 |
| C | truth_source | T-SYN | T-SILVER | Y | 학습·튜닝 신호원 |
| D | label_noise_handling | hard | soft(신뢰가중) | Y | silver 잡음을 하드 라벨 vs soft로 |
| E | self_training | off | on | Y | 자기라벨 재학습 루프(P4 연결) |
| F | leakage_granularity | L-DWG | L-FIRM | Y | 분리 입도 자체를 요인화 → 규약 암기 진단 |

**반응(response)**: `R-SYN`(1차, 결정 게이트) + `R-SILVER`(2차, 교차확인·잡음 measure). direction=↑.
`R-SYN`은 합성 정답 대비 per-handle 점수, `R-SILVER`는 silver(AI판정자) 대비 점수.

### 2.2 설계행렬 생성 (design matrix construction) — 결정론적, 코드로 확정

```
입력: 없음(순수 함수). 생성자 E=ABC, F=BCD.
1. A,B,C,D에 대해 표준 2^4 완전요인 16행을 ±1로 생성(Yates 순서).
2. 각 행에 대해 E := sign(A·B·C),  F := sign(B·C·D)  로 채운다.
3. 결과 16×6 ±1 행렬이 run_matrix. (열 A..F, 행 run 1..16)
출력: 16런 직교표. (부록 A에 전개표)
```

이 단계는 **모델 없음·난수 없음** — `design_matrix.py`가 항상 동일 표를 낸다(재현성 100%). 시드가
등장하는 곳은 오직 학습 셀의 **훈련 시드**와 `T-SILVER`의 LLM 비결정성뿐(§2.6).

### 2.3 반응모형 (response model)

각 run i(i=1..16)에서 40장 population 위 반응 y_i(별도로 R-SYN_i, R-SILVER_i)를 측정. 요인효과는
직교대비(orthogonal contrast)로:

```
효과_j = (1/8) · Σ_i (x_{ij} · y_i)        # x_{ij}∈{−1,+1}, 16런에서 8양-8음
```

(관례상 "effect = 고수준평균 − 저수준평균". 회귀계수 β_j = 효과_j / 2.) 16런은 평균 포함 16개 직교
대비를 낳고, 그중 **비평균 15개**가 추정 가능 대비다: **6개 main + 7개 2FI-사슬 대표 + 2개 순수 3FI+
사슬**(후자는 잔차/오차 df 역할). 활성 여부 판정은 아래 Lenth 절차.

### 2.4 별칭 구조 (alias structure) — 청구서, 반드시 명시

생성자 E=ABC, F=BCD로부터 **정의관계(defining relation)**:

```
I = ABCE = BCDF = ADEF          (세 정의어, 최단 길이 4 → Resolution IV)
```

(유도: E=ABC ⇒ I=ABCE; F=BCD ⇒ I=BCDF; 둘의 곱 ABCE·BCDF = AD EF·B²C² = ADEF.)

**Main effect**: 전부 3FI 이상과만 별칭(2FI와 안 겹침 = Res IV 보장). 예 A=BCE=DEF=ABCDF.

**2FI 사슬(estimable 7개)** — 이 스크린이 **분리 못 하는** 쌍/삼중:

| 사슬(추정 가능한 한 대비) | 물리 의미(대표) |
|---|---|
| **AB = CE** | (rep×family) = (truth×self_train) |
| **AC = BE** | (rep×truth) = **(family×self_train)** ← red team T15 confound |
| **AD = EF** | (rep×noise) = (self_train×leakage) |
| **AE = BC = DF** | (rep×self_train) = **(family×truth)** = (noise×leakage) ← 삼중 사슬 |
| **BD = CF** | (family×noise) = (truth×leakage) |
| **BF = CD** | (family×leakage) = (truth×noise) |
| **AF = DE** | (rep×leakage) = (self_train×noise) |

핵심 3가지 짚기(패킷 interactions_found의 정확한 재서술):
- **B×C(family×truth)** 는 사슬 `AE=BC=DF`의 한 성분. "검출된다"의 정확한 뜻 = **main effect와 안
  겹침**(Res IV) → 이 사슬이 크면 "어떤 2FI가 활성"임은 확실. 그러나 **B×C를 A×E·D×F에서 분리 못 함**.
  계층·이질(heredity) 원칙 + 도메인 지식으로 B×C에 귀속하는 것이지, 산술적 분리가 아니다. 이 미세한
  구분을 놓치면 expected_failure_mode ①(2FI를 clean kill로 오독)에 빠진다.
- **A×B(rep×family)** = 사슬 `AB=CE`. C×E(truth×self_train)와 별칭.
- **C×F(truth×leakage, 규약암기 서명)** = 사슬 `BD=CF`. B×D(family×noise)와 별칭.

즉 패킷 abstentions ①("별칭된 2FI 쌍은 증명적 분리 불가")과 interactions_found("검출 설계됨")은
모순이 아니다 — **"main에서 깨끗(검출)"이지 "서로에게서 깨끗(분리)"이 아니다**.

### 2.5 활성 판정 — Lenth PSE 절차 (정확 스펙)

비복제 설계라 잔차 df가 빈약 → 효과 크기 분포 자체에서 잡음규모를 추정한다(효과 희소성 가정 활용).

```
입력: 비평균 대비 효과 집합 {c_j}, j=1..m  (여기 m≤15)
1. s0  := 1.5 · median_j( |c_j| )
2. PSE := 1.5 · median{ |c_j| : |c_j| < 2.5·s0 }          # 활성 효과를 배제한 잡음규모
3. d   := m/3                                             # Lenth 권장 자유도
4. ME  := t_{0.975, d} · PSE                              # 개별 margin of error (α=0.05)
5. SME := t_{γ, d}     · PSE,  γ=(1+0.95^{1/m})/2         # 동시(simultaneous) margin
6. 판정: |c_j| > ME  ⇒ active(개별),  |c_j| > SME ⇒ active(다중비교 보수적)
출력: effects_table의 active 열
```

패킷 prereg_model은 "|effect|>ME(α=0.05)"를 결정임계로 봉인. 상수 1.5·2.5·d=m/3는 Lenth 방법의
고정 상수(문헌 표준). half-normal plot은 이 판정의 **시각 교차검증**으로 병행(Daniel 1959).

### 2.6 시드·잡음 처리 (deterministic_note의 코드화)

- **B=deterministic 셀**: (config, 도면) 고정 → 순수 함수. **셀내 반복 무의미**; 반복은 오직
  population(outer 40장)으로. 잡음통계 수입 금지(card rule 7).
- **B=learned 셀**: training seed가 은닉상태를 결정 → **seed 고정+기록**(재현), 또는 seed를 명시
  반복요인으로 승격(예산 있으면). seed 변동을 상호작용으로 오인 방지 = expected_failure_mode ③
  → **seed 블록화(blocking)**.
- **`T-SILVER` 반응만** LLM 비결정 상속 → 그 축은 randomization이 실제로 방어. 순수 결정 축엔 방어할
  잡음이 없다.

### 2.7 하이퍼파라미터 공간 (셀별로 요인이 지정)

이 스크린은 하이퍼파라미터 튜닝이 아니라 **설계선택 스크린**이다. 각 셀 내부의 하이퍼파라미터는
**요인이 고정하는 것 외에는 표준값 동결**(예: learned=HistGradientBoosting 계열 기본, 특징 6종 고정 —
digest의 parallel/thickness/junction/log길이/sin2θ/cos2θ). 셀 내부 튜닝은 스크린 오염원이므로 금지;
튜닝은 활성 요인 확정 후 후속(RSM) 단계로 이연.

---

## 3. 벽 과업 적응 설계 (harness 접속)

### 3.1 세 하네스 축 ↔ 요인 매핑

digest가 준 실측 하네스 세 축이 요인의 수준으로 직결된다:

- **CubiCasa SEG-IR(벡터축, 제3자 사람 라벨)** — A=graph-IR의 실체. 5,000도면 SEG-IR 변환(실패 0),
  train 4,200(선분 386만)/val 400(35.4만)/test 400(37.5만), 벽 선분율 ~11.8%, 레이어 중립(라벨 누출 0).
  F(leakage_granularity)의 L-DWG/L-FIRM 분리가 여기서 도면/프로젝트 단위 스플릿으로 구현.
- **FloorPlanCAD 래스터(5,308장 + 벽 bbox/segmask)** — A=raster의 실체. 벡터 SVG 없음 → raster 셀은
  이 자산 또는 CubiCasa 렌더로.
- **1.dwg 실도면(384 도면정의)** — C=T-SILVER의 실체(E1.5 silver 5판정자). B5 detector↔silver Pearson
  0.2911.

### 3.2 이미 아는 두 앵커 점 — 스크린이 무엇을 **더** 가져오나

digest는 이 설계공간의 **두 점을 이미 실측**했다. 이게 스크린의 출발 좌표다:

- **결정론 arm(B=−1) on CubiCasa 벡터**: geometric detector v1 전이 = **val F1 0.2358**(P 0.134 ≈ 기저율
  0.118, R 0.981). 즉 "거의 다 벽이라 부르는" 저정밀 탐지기.
- **학습 arm(B=+1) on CubiCasa 벡터**: HistGradientBoosting(6특징, 386만행) = **val F1 0.517**(P 0.860 /
  R 0.370 / AUC 0.9215). 정밀도 0.13→0.86, 탐지기 대비 2.2배. (로지스틱 F1 0.053 = 선형 불충분; 셔플
  대조군 AUC 0.375 PASS = 누출 없음; test 분할 무접촉.)

**따라서 B(family)의 main effect는 CubiCasa 벡터축에서 이미 큰 신호로 예고돼 있다**(F1 척도로 대략
0.517−0.236=0.281 폭 — 이 뺄셈은 두 digest 점의 차이지 스크린 실측이 아님; 스크린이 다른 반응척도
R-SYN/R-SILVER에서 재확인해야 함). **OFAT가 준 것은 고립된 두 점뿐**이다. 스크린이 **더** 가져오는 것:

1. **그 0.28 간극이 순수 main인가 상호작용인가.** digest는 이미 힌트를 준다 — 합성 per-handle에서
   결정론 arm이 이미 천장(S 1.0/1.0, F P 0.9315, M P 0.8669, recall 전부 1.0)이라, **합성(T-SYN) 위에선
   학습이 더 올릴 여지가 작다**. 반면 벡터 실도면/silver에선 학습이 크게 이긴다. 이것이 정확히 패킷의
   사전가설 **B×C 크다(합성에서 학습 과적합/무익)** — "학습이 낫다"의 단독 스토리를 반증할 신호다.
   OFAT로는 이 간섭을 **구조적으로 못 본다**; 스크린은 `AE=BC=DF` 사슬 대비로 **직접 추정**한다.
2. **A(representation)가 그 판을 뒤집나.** 전이 실패(F1 0.236)는 벡터 그래프-IR 위 결정론의 성적이다.
   래스터축(FloorPlanCAD/qwen2.5-VL-3B)에서 같은 계열비교가 뒤집히는지 = A×B 상호작용(사슬 `AB=CE`).
3. **F(leakage)가 학습에서만 반응을 움직이나 = 규약암기 진단.** 결정론은 암기할 게 없어 F-null이 기대.
   학습 셀에서 L-DWG→L-FIRM(도면→firm 단위 분리)로 성능이 떨어지면 = 규약 암기 서명. 이는 B×F
   상호작용(사슬 `BF=CD`)으로 잡힌다.
4. **null도 1급 결과.** 예 E(self_training)가 null이면 "자기학습 무익"이 승리 — digest엔 self-training
   실측이 없으므로 이건 스크린이 **처음으로** 판정하는 축이다.

### 3.3 전이 실패 0.236·GBDT 0.517을 알고 **설계에 반영**한 것

- **밴드 하한을 합성 난이도에 맞춰 높임**: 합성 per-handle이 이미 천장이라 R-SYN는 쉽다 → 그래서
  prereg R-SYN 하한을 **0.90**(PASS)로 높게 봉인. 안 그러면 전 셀이 R-SYN 천장을 쳐 요인 무차별
  (expected_failure_mode ②). 반면 R-SILVER는 현 0.13 대비 **0.50/0.30** 밴드 — 실도면은 어렵다는 실측
  반영.
- **정밀도 병목을 반응에 반영**: 결정론의 FP 주범(Direction 화살표/BoundaryPolygon/Door/Window/
  DimensionMark)과 최소길이 필터 천장(F1 0.335 @80px)은 "아이콘 아닌 긴 평행구조가 본질 교란"임을
  말한다. 이는 A(그래프 vs 래스터)와 D(라벨잡음처리)가 왜 반응을 움직일 수 있는지의 물리적 근거다.
- **선형 불충분(로지스틱 F1 0.053) → 학습 셀은 비선형(GBDT/GNN 계열)로 고정**: 요인 B의 +1 수준을
  "선형학습"으로 잡으면 무의미하므로 비선형 앵커(HistGradientBoosting)로 정의.

### 3.4 반응 정의의 벽-과업 구체화

- **R-SYN**: 합성 벽 정답(CL-C/WSD-EVAL-v1 팩) 대비 per-handle `wall_member(h)` 점수. **단, 이 팩은
  아직 미존재**(B1 fidelity FAIL: KS 0.5792, TV 0.265; 합성팩 LINE/LWPOLYLINE/INSERT 3종뿐, 실도면
  SPLINE 3,973/ARC 2,198/HATCH 264 혼재) → §7 T2에서 하드 선결로 처리.
- **R-SILVER**: 1.dwg 실도면군 위 silver(AI판정자) 대비 Pearson/일치. digest B5 = 0.2911, full-vs-nb
  1.0(레이어명 신호 0). E1.5 silver는 ~2어휘 가문(fable+sol vs opus+sonnet+grok) → 5독립 아님, 잡음
  구조를 D(soft/hard)·randomization으로 다뤄야 함.

---

## 4. 데이터·컴퓨트 요구 (실행 가능성)

### 4.1 자산 전제 (digest 고정)

RTX 5070 Ti **16GB** · RAM **64GB** · DGX Spark(Ornith-35B) **현재 unreachable**(승인만 됨) · 프런티어
VLM API = **유일 결재 게이트(미승인)** · qwen2.5-VL-3B floorplan SFT/GRPO 로컬 실존 · Zenodo10K/
Text2CAD/ArchCAD/pseudo-floor-plan-12k 로컬.

### 4.2 로컬 실행 계획 (지금 가능한 것)

- **결정 arm 16셀 전부**: 순수 함수 스코어링. digest의 fast_score(NumPy 동치 고속 채점기)로 로컬 CPU/
  GPU. 최대 도면정의 412,775 선분이 연산 병목 실증이므로 **RAM 상시 계측** 후 배치.
- **학습 arm(1차 = 비선형 고전ML)**: **HistGradientBoosting on 386만행이 이미 로컬에서 돌았다**(digest)
  → 1차 스크린의 learned 수준은 **전량 로컬 실행 가능**. 소형 GNN도 16GB 안에서 시도 가능(digest
  compute_plan).
- **첫 신호**: cheapest_probe(결정 arm 8셀, §6.4)만 먼저 = **반나절 내** A/C main effect 초벌. 학습 투자
  전에 "표현·정답원이 애초 반응을 움직이나" 확인.

### 4.3 DGX/API 분리 계획 (지연·이연)

- **learned→{GNN,VLM} 세분(후속)**: 대형 GNN/VLM 파인튜닝만 DGX Spark로 오프로드(야간 배치, vLLM
  호스트 겸용). **DGX unreachable인 지금은 이 세분을 이연** — 단, 1차 스크린은 로컬 완결이므로 **P1의
  1차 결론은 DGX 없이도 난다**.
- **raster+VLM 셀**: qwen2.5-VL-3B는 16GB에서 tight하게 로컬 가능(추론). 프런티어 VLM은 API 미승인
  이라 배심(silver) 확장은 결재 게이트 통과 전까지 1.dwg 기존 silver로 한정.
- **T-SILVER 신규 생성**: 프런티어 API 미승인 → 신규 대량 silver 라벨은 불가. 기존 E1.5 5판정자 산출
  재사용으로 스코프 한정.

### 4.4 예산 요약 (시간·자원, digest 근거 추정)

| 배치 | 자원 | 예상 시간 | 근거 |
|---|---|---|---|
| cheapest_probe 8 결정셀 | 로컬 CPU | 반나절 | packet compute_plan |
| 결정 arm 16셀 | 로컬 CPU/fast_score | 시간~1일 | "결정 arm만 먼저 며칠 내(사실상 시간)" |
| learned 8셀(고전ML) | 로컬 GPU 16GB | 1~수일 | GBDT 386만행 로컬 선례 |
| learned→{GNN,VLM} 세분 | **DGX(이연)** | 미정 | DGX unreachable |
| confirmation_run 1셀 | 로컬 | 반일 | hold-out 단독 재실행 |

---

## 5. 구현 계획 (모듈·파일 골격·접속점)

### 5.1 기존 도구 접속점 (digest·패킷 명시)

- **evidence_grid**: 결정 arm(B=−1)의 4증거 채널 가중합(parallel 0.35/thickness 0.25/junction 0.20/
  layer 0.20, 두께대역 50~400mm, 각도 2°, overlap 0.5, snap 6mm). → cell_runner의 deterministic 경로.
- **fast_score**: per-handle 반응 R-SYN/R-SILVER 산출(NumPy 고속 채점). → response 측정 공용.
- **cubicasa_ir**: SEG-IR 변환(A=graph-IR 기질). → representation=graph-IR 경로.
- **cubicasa_ml**: HistGradientBoosting 파이프(6특징, 386만행). → learned arm(B=+1) 경로.

### 5.2 신규 모듈 골격 (**계획일 뿐 — 본 도시에는 이 파일들을 생성하지 않음**)

```
screen/
  design_matrix.py    # §2.2 결정론 생성. 2^4 완전요인 + E=ABC,F=BCD. 출력 16×6 ±1 표. (~40줄)
  prereg_seal.py      # 반응 밴드+Lenth ME를 실행 전 해시+타임스탬프로 봉인(평가 원칙 준수). (~30줄)
  cell_runner.py      # 한 행(A..F 수준)→탐지기 1설정 구성·실행. 6요인을 위 4도구로 라우팅. (핵심, ~300줄)
                      #   A: cubicasa_ir(graph) | render(raster)
                      #   B: evidence_grid(det) | cubicasa_ml(learned)
                      #   C: 채점 정답을 T-SYN(합성팩) | T-SILVER(1.dwg silver)로
                      #   D: 라벨을 hard | soft(신뢰가중)
                      #   E: self_training off | on(자기라벨 1루프)
                      #   F: 스플릿을 L-DWG | L-FIRM
  population.py       # 40장 층화표본(source-firm 층 + plan density 층) 고정·crossed 적용. (~80줄)
  response_collect.py # 16런 × 40장 → R-SYN/R-SILVER 반응표. seed 기록. (~60줄)
  effects_analysis.py # 직교대비 효과 + Lenth PSE/ME/SME + half-normal plot + effects_table. (~150줄)
  report_xlsx.py      # 증거 xlsx 의무 산출(평가 원칙). (~60줄)
```

의존: numpy/scipy(Lenth·대비), 기존 evidence_grid/fast_score/cubicasa_ir/cubicasa_ml. **신규 무거운
의존 없음**(R7 — stdlib+기존 도구로 충분).

### 5.3 개발 규모 추정

- **분석부(design_matrix+effects_analysis+prereg_seal)**: 순수 파이썬, Lenth ~30줄. **1~2일**.
- **하네스부(cell_runner+population)**: 6요인을 4도구에 배선하는 접착코드가 진짜 노동. **3~5일**.
- **최대 난점**: (a) 40장 층화 population 픽스처 구축(source-firm × plan-density 층), (b) `T-SYN` 경로가
  CL-C 팩 존재에 의존(미존재 → §7), (c) self_training(E) 1루프의 결정론적 재현(seed 기록).

### 5.4 실행 순서 (goal→loop→checkpoint)

1. prereg_seal 먼저 봉인(평가 전 합격선 봉인 — 프리레그 원칙). checkpoint: 봉인 해시 기록.
2. cheapest_probe 8 결정셀 → A/C main 초벌. checkpoint: A·C가 움직이나?(안 움직이면 kill 검토)
3. 결정 arm 16셀 완주 → 결정론 하위표면 확정. checkpoint: R-SYN 천장 여부(밴드 재점검).
4. learned 8셀(로컬 고전ML) → B main·B×C 사슬 추정. checkpoint: half-normal에서 활성 효과 가려짐.
5. effects_analysis → effects_table·interactions 채움. checkpoint: 별칭 사슬 라벨 정확히 병기.
6. confirmation_run(미사용 firm hold-out) → 밴드 재확인 + Goodhart 쌍 점검. status=PASS_WITH_DEFERRAL.

---

## 6. 실험 셀 정의 (cell definitions)

### 6.1 프레이밍 — 요인설계에서 "셀"과 "가설"의 층위

중요한 층위 구분(정직하게): **요인 스크린의 과학적 가설은 개별 셀(행)이 아니라 효과(열)에 붙는다.**
한 셀의 반응값은 단독으로 해석 불가 — **셀들 간 대비(contrast)**가 의미를 나른다. 따라서:
- **합격/킬 조건은 (a) 효과 수준(Lenth ME)과 (b) 전-스크린 수준(kill_condition)에 산다**, 셀당이 아니라.
- 아래는 (i) 16개 셀(행)의 요인배치 + 예상 반응밴드, (ii) 효과 수준 가설·판정, (iii) cheapest_probe
  8셀, (iv) confirmation_run 1셀로 나눠 제시한다.

### 6.2 16런 셀 표 (부록 A 전개, 요약 재수록)

각 행 = 1개 탐지기 설정을 40장 population 위에서 학습·평가. 수준 표기: A(graph−/raster+),
B(det−/learn+), C(SYN−/SILVER+), D(hard−/soft+), E(off−/on+), F(DWG−/FIRM+).

| run | A | B | C | D | E=ABC | F=BCD | 셀 성격 |
|---|---|---|---|---|---|---|---|
| 1 | − | − | − | − | − | − | 결정·graph·SYN (cheapest) |
| 2 | + | − | − | − | + | − | 결정·raster·SYN (cheapest) |
| 3 | − | + | − | − | + | + | 학습·graph·SYN |
| 4 | + | + | − | − | − | + | 학습·raster·SYN |
| 5 | − | − | + | − | + | + | 결정·graph·SILVER (cheapest) |
| 6 | + | − | + | − | − | + | 결정·raster·SILVER (cheapest) |
| 7 | − | + | + | − | − | − | 학습·graph·SILVER |
| 8 | + | + | + | − | + | − | 학습·raster·SILVER |
| 9 | − | − | − | + | − | + | 결정·graph·SYN·soft (cheapest) |
| 10 | + | − | − | + | + | + | 결정·raster·SYN·soft (cheapest) |
| 11 | − | + | − | + | + | − | 학습·graph·SYN·soft |
| 12 | + | + | − | + | − | − | 학습·raster·SYN·soft |
| 13 | − | − | + | + | + | − | 결정·graph·SILVER·soft (cheapest) |
| 14 | + | − | + | + | − | − | 결정·raster·SILVER·soft (cheapest) |
| 15 | − | + | + | + | − | + | 학습·graph·SILVER·soft |
| 16 | + | + | + | + | + | + | 학습·raster·SILVER·soft |

**결정 셀(B=−1) = 행 {1,2,5,6,9,10,13,14} 정확히 8개** = cheapest_probe 배치.
**공통 지표·밴드(프리레그 봉인)**: R-SYN — PASS≥0.90 / INCONCLUSIVE 0.75–0.90 / FAIL<0.75.
R-SILVER — PASS≥0.50 / INCONCLUSIVE 0.30–0.50 / FAIL<0.30. status(전 셀)=**UNRUN**.
**시드 계획**: 결정셀 seedless(순수함수); 학습셀 seed 고정+기록; SILVER 축만 randomization 방어.

### 6.3 효과 수준 가설·판정 (effects_table + interactions, UNRUN)

**사전 기대 순위(가설, 실측 아님)**: C(truth) > B(family) > A(rep) > F(leakage) > D(noise) >
E(self_train). (단 §3.2 앵커로 B도 크게 예상 — C와 B가 상위 다툼.)

| 효과 | 가설 | 지표 | active 임계 | 특기 |
|---|---|---|---|---|
| A rep | 반응 이동(그래프 vs 래스터) | R-SYN/SILVER 대비 | \|eff\|>ME | 앵커: 전이 F1 0.236은 graph·det |
| B family | **크게 활성 예상** | 상동 | \|eff\|>ME | 앵커: det 0.236 vs learn 0.517 |
| C truth | **최상위 예상** | 상동 | \|eff\|>ME | SYN 천장 vs SILVER 난이도 |
| D noise | 소~null 예상 | R-SILVER | \|eff\|>ME | soft가 silver 잡음 완화하나 |
| E self_train | **null이면 승리** | 상동 | \|eff\|>ME | "자기학습 무익" 근거 |
| F leakage | det=null / learn=활성 기대 | 상동 | \|eff\|>ME | 활성=규약암기 서명 |
| **B×C**(=AE=DF 사슬) | **크게 활성 예상** | 대비 | \|eff\|>ME | "학습 낫다" 단독 반증 |
| **A×B**(=CE 사슬) | 중간 | 대비 | \|eff\|>ME | 계열우위가 표현 의존 |
| **C×F**(=BD 사슬) | 중간 | 대비 | \|eff\|>ME | 정답원×누수=규약암기 |

**null/small 효과도 전부 1급 보고**(패킷 명령). "이 요인은 반응을 안 움직인다"가 승리다.

### 6.4 cheapest_probe (첫 실행 배치, 학습 0)

- **셀**: 결정 8셀 {1,2,5,6,9,10,13,14}. B=−1 고정이라 A,C,D가 2^3처럼 자유변동, E=−AC·F=−CD로 종속.
- **가설**: 학습 투자 **전에** A(표현)·C(정답원)가 결정론 반응을 움직이나. 결정론이라 F(누수)는 null 기대.
- **지표/합격선**: A·C main의 \|eff\|>ME(초벌). 밴드는 R-SYN/R-SILVER 프리레그 동일.
- **킬**: 8셀 전부 R-SYN FAIL(<0.75)이면 → 표현/정답원 문제이지 모델 문제 아님(전-스크린 kill로 승격).
- **예산**: 로컬 CPU 반나절. **시드**: seedless.
- **주의(정확성)**: 결정 서브셋 내에서 F는 CD와, E는 AC와 종속 → A·C main은 깨끗하나 F·E는 이 배치
  단독으론 분리 불가. 학습셀 합류 후 전체 별칭구조로 해소.

### 6.5 confirmation_run (1셀, 스크린 후)

- **프로토콜**: 스크린이 지명한 **최적 셀**을, **미사용 firm의 hold-out 도면군**에서 단독 재실행.
- **가설/점검**: 밴드 재확인 + **Goodhart 쌍**(게이트↑ & hold-out↓?) 진단.
- **status**: `PASS_WITH_DEFERRAL`(미실행 — 스크린 완료 후 실행).

### 6.6 val/test 원칙 준수 (평가 규율)

val=개발·튜닝(스크린 전 과정은 val에서), **test=방법당 단발**(CubiCasa test 400장 무접촉 유지 —
digest "test 분할은 무접촉, 단발 원칙"). 합격선은 실행 전 prereg_seal로 봉인. 셔플 대조군 의무(학습셀
누출 점검, digest 선례 AUC 0.375 PASS). 증거 xlsx 의무. 실패도 사유와 함께 기록.

---

## 7. red team 티켓 응답 (OPEN 티켓 중 P1에 걸린 것)

패널 보고서 기준, 본 제안(doe P1)에 직접 걸린 티켓과 입장:

### 7.1 T15 — learned 셀 seed-confounded + A×C가 B×E와 confounded (**P1 PARKED의 직접 사유**)
- **인정(부분)**: 패킷 PARKED가 명시 — "representation×truth가 family×self-training과 confounded".
  §2.4로 **정확히 확인**: 사슬 `AC = BE`. A×C(표현이 정답원과 간섭)를 물으면 B×E(계열이 자기학습과
  간섭)와 **산술적으로 분리 불가**.
- **해소책 2단**: (a) **fold-over 8런 추가 → Res V 승격**으로 AC/BE 분리(패킷 resolution_alias 명시
  경로). AC·BE 사슬이 활성일 때만 지불하는 조건부 예산. (b) seed-confound는 **seed 블록화**(§2.6) +
  seed를 명시 반복요인으로 승격(예산 있으면)으로 방어. 패킷 PARKED 조건("CL-C 완성 + seed 예산 명시
  후 재개")을 **수용** — 즉 P1 풀버전은 이 두 선결 충족 전엔 착수 안 함.

### 7.2 T2 — 벽 합성 생성기 부재(sev 0.70, PR-1)
- **인정(하드 선결)**: `synthetic_truth.py`는 dimension 전용, **벽 코드 0**. R-SYN 반응의 정답원(C=T-SYN)
  이 **아직 존재하지 않는다**. B1 fidelity FAIL(KS 0.5792) 상태.
- **해소책**: P1의 T-SYN arm은 **CL-C(WSD-EVAL-v1 팩)·PR-1 완료에 하드 의존**. 그 전까지는 **결정
  arm + R-SILVER 축만** 실행 가능(cheapest_probe·SILVER 셀). 즉 P1은 T-SYN 없이도 **부분 착수** 가능하나
  R-SYN 게이트는 이연. 이는 축소범위 실행이므로 결과는 PARTIAL로 보고.

### 7.3 T1 — 대리(truth proxy) 독립성(sev 0.75, 최우선)
- **부분 응답**: 4대리(합성·외부·metamorphic·silver)가 같은 "평행 이중선" prior를 공유하면 합치가
  확증 아니라 편향 증폭. **P1의 C main + B×C 상호작용이 이 독립성의 부분 계량**이다 — C(SYN vs SILVER)
  반응차와 B×C 사슬이 "정답원을 바꾸면 결론이 바뀌나"를 직접 측정. digest 앵커(B5 Pearson 0.2911,
  full-vs-nb 1.0 = 탐지기·레이어 두 축 대체로 독립)와 정합.
- **한계 인정**: P1은 **전 4대리의 3원 불일치 구조**까지는 못 잰다 — 그건 CL-E/doe P3의 몫. P1은 2대리
  (SYN/SILVER)만 요인화. **doe P3와 병합 권고**(§8).

### 7.4 T5 — 라이선스/counsel(sev 0.65, PR-3)
- **인정(하드 선결)**: FloorPlanCAD/CubiCasa NC 라벨 + 원도면 권리 미해결. **P1의 A=raster(FloorPlanCAD)
  및 CubiCasa 학습 arm은 서면 클리어 전 착수 금지**. graph-IR·1.dwg 축은 이 게이트 밖이므로 그쪽부터.

### 7.5 T3/T4/T8 — E1 법의학(상위 선결, CL-A)
- **인정(상류 의존)**: top-20 신호가 정렬-키 아티팩트/계측 아티팩트면 **P1이 스크린하는 설계공간 자체가
  무의미**해진다. P1은 CL-A(로컬 CPU <1h)가 "신호 실재" 판정을 **먼저** 내는 것에 의존. CL-A가 아티팩트
  판정이면 P1은 **죽는다**(§8.3).

### 7.6 expected_failure_modes (자기 방어책, 재확인)
- ① Res IV 별칭을 clean kill로 오독 → §2.4 별칭표를 effects_table에 **항상 병기**로 방어.
- ② 합성 천장 → 요인 무차별 → R-SYN 하한 0.90 상향 봉인으로 방어.
- ③ learned seed 잡음을 상호작용으로 오인 → seed 블록화로 방어.

---

## 8. 인접 제안과의 관계 (병합·차별·죽는 조건)

### 8.1 병합 가능 지점
- **CL-F(학습 사다리 고전ML→PU→GNN) [platt P2 + calibration P2/P3 + doe P1]**: P1은 이 클러스터의
  **스크린 앞단**이다. 사다리가 GNN에 투자하기 **전에**, P1이 "B(family)가 애초 활성인가, 어디서
  (어떤 A/C 조합에서) 이기는가"를 판정 → GNN 불요면 사다리 중단(Occam). 병합: P1의 B=learned 1차
  수준을 사다리 1단(고전ML)과 **공유**.
- **CL-E / doe P3(truth-source 교차요인 메타실험)**: P1의 C(truth_source)는 P3의 train{합성,외부,silver}×
  eval{...} 매트릭스의 **2수준 슬라이스**. **병합 권고** — P1이 스크린(어느 요인 활성), P3가 전체 교차
  (독립성 구조). T1(대리 독립성) 공동 대응.
- **doe P2(Taguchi 강건화)**: P1의 noise_factors(population outer 잡음, crossed)가 P2의 강건설계 사고와
  연속. 활성 요인 확정 후 P2로 노브 강건화.

### 8.2 차별점 (P1만의 것)
- P1은 **유일하게 상호작용을 1급 추정 대상**으로 놓는다. 다른 좌석·클러스터는 대개 OFAT/단일축.
  "학습 우위가 표현·정답원과 간섭하는가"는 P1 없이는 구조적으로 답 못 하는 질문.
- P1은 **계열을 요인의 한 수준으로 승격** → 전 계열을 한 배치로 관통(평가기준 5를 낭비 없이).

### 8.3 이 제안이 **죽어야 하는 조건** (정직하게)
1. **상류 무효화(CL-A)**: E1 법의학이 divergent-20 신호를 정렬-키/계측 아티팩트로 판정하면 → P1이
   스크린하는 설계공간이 허구 → **P1 폐기**. (P1은 CL-A 이후에만 착수.)
2. **양 정답원 무효**: 합성팩이 fidelity를 끝내 못 넘고(B1 이미 FAIL 0.5792) **동시에** 어떤 셀도
   R-SILVER를 0.30 위로 못 올리면(kill_condition) → **R-SYN·R-SILVER 둘 다 유효 반응이 아님** → P1은
   측정할 반응이 없어 **죽거나**, representation-only 축소 스크린으로 격하(그마저 CL-A 통과 시).
3. **설계공간이 1차원**: cheapest_probe + 결정 arm에서 A·C·F·D·E가 전부 null이고 **오직 B만** 반응을
   움직이면 → 질문이 "학습이 돕나" 단일축으로 붕괴 → 16런 스크린은 과설계, **2셀 비교로 격하**. (단
   "나머지가 null"임을 **증명한 것 자체가 스크린의 승리**이므로, 이는 "실패사"가 아니라 "1회로 끝난
   성공"에 가깝다 — 그래도 풀 16런 재실행은 정당화 못 함.)
4. **핵심 confound 분리 불가 + fold-over 거부**: 과학적으로 결정적인 질문이 하필 `AC=BE`(또는 다른
   활성 사슬)에 걸렸는데 fold-over 8런 예산이 거부되면 → P1은 그 질문에 **답할 수 없음**을 선언하고
   abduction/다른 좌석으로 hand-off. (부분 침묵이지 전면 폐기는 아님.)
5. **비죽음(명확화)**: DGX unreachable·프런티어 API 미승인은 P1을 **죽이지 않는다** — 1차 스크린은
   로컬 완결. 죽는 건 learned→{GNN,VLM} **세분**뿐이고, 그건 P1의 후속이지 P1 본체가 아니다.

---

## 부록 A — 16런 설계행렬 전개 (재현용)

생성: A,B,C,D 표준 2^4(Yates 순서) + E:=sign(A·B·C), F:=sign(B·C·D). (§6.2 표와 동일; 여기 ±1 원장.)

```
run  A   B   C   D   E   F
 1   -1  -1  -1  -1  -1  -1
 2   +1  -1  -1  -1  +1  -1
 3   -1  +1  -1  -1  +1  +1
 4   +1  +1  -1  -1  -1  +1
 5   -1  -1  +1  -1  +1  +1
 6   +1  -1  +1  -1  -1  +1
 7   -1  +1  +1  -1  -1  -1
 8   +1  +1  +1  -1  +1  -1
 9   -1  -1  -1  +1  -1  +1
10   +1  -1  -1  +1  +1  +1
11   -1  +1  -1  +1  +1  -1
12   +1  +1  -1  +1  -1  -1
13   -1  -1  +1  +1  +1  -1
14   +1  -1  +1  +1  -1  -1
15   -1  +1  +1  +1  -1  +1
16   +1  +1  +1  +1  +1  +1
```

**정의관계**: I = ABCE = BCDF = ADEF (Res IV). **2FI 사슬 7개**: AB=CE · AC=BE · AD=EF ·
AE=BC=DF · BD=CF · BF=CD · AF=DE.

## 부록 B — prereg 밴드 봉인 초안 (실행 전 봉인 대상)

- **추정 대상**: A~F 6 main effect + 별칭 사슬 대표 2FI 7개.
- **결정임계**: Lenth PSE, |effect|>ME(α=0.05) ⇒ active. (동시비교는 SME.)
- **반응 밴드**: R-SYN — PASS≥0.90 / INCONCLUSIVE 0.75–0.90 / FAIL<0.75. R-SILVER — PASS≥0.50 /
  INCONCLUSIVE 0.30–0.50 / FAIL<0.30(현 0.13 대비).
- **사후 요인 추가**: version-bump된 **새 prereg(exploratory 라벨)**로만. 봉인 후 밴드 이동 금지.

## 부록 C — abstentions (원리적 침묵, 요약)

① 별칭된 2FI 쌍(AB=CE, AC=BE 등)은 **fold-over 없이 증명적 분리 불가**. ② learned를 {GNN,VLM}로 못
나눔(1차 2수준). ③ 요인 목록에 없는 벽-정의 신호(해치 poché·텍스트 라벨)는 스크린이 **발명 못 함** —
전 그리드 plateau면 abduction 좌석 hand-off. ④ 비설정 관측변수(밀도·단위·layer-naming)에 **인과 주장
불가**(outer 잡음/블록으로만).

## 부록 D — 상태·검증 요약 (상태 어휘 계약 준수)

- 본 도시에의 모든 실험 항목: **status=UNRUN**(설계만, 미실행). 신규 측정 주장 없음(패킷 계약).
- confirmation_run: **PASS_WITH_DEFERRAL**(미실행).
- 인용 수치 출처: 전부 패킷 §다이제스트(2026-07-18 세션 도구 출력). 방법론 수치(Lenth 상수·resolution
  산술·2^(6-2)=16)는 문헌·산술 일반지식. 확신 없는 문헌 귀속은 본문에 '요검증' 표기.
- 웹 검색 미사용.

DOSSIER_COMPLETE: doe_P1
