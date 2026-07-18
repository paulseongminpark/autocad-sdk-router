# 방법론 심층 도시에 — doe_P3

**제안**: P3 · TRUTH-SOURCE VALIDITY CROSS-FACTORIAL (정답원 타당성 교차요인 설계)
**좌석**: doe_experimentalist (실험설계 좌석)
**status 규율**: 이 문서의 모든 실험 결과 슬롯은 `UNRUN`(아직 실행 안 함)이다. 인용 수치는 전부 패킷 다이제스트(2026-07-18 세션 도구 출력)에서만 왔고, 문헌 지식은 별도 표기한다. 새 측정 주장은 없다.

---

## 0. 용어 정의 (먼저 읽을 것 — 이 문서 전체가 이 약어들로 말한다)

이 제안은 "정답원(truth source)"이라는 개념 위에 서 있다. 정답원 = **탐지기가 옳은지 틀린지를 판정할 때 기준으로 삼는 라벨의 출처**. 사람 라벨이 없는(또는 최소인) 이 프로그램에서는 정답원 자체가 의심 대상이다. 네 개를 구별한다.

- **T-SYN = 합성 정답원(synthetic truth)**: 우리가 직접 만든 생성기가 뽑은 도면과 그 도면의 "정답 벽". 장점은 정답이 구성상 완벽히 안다는 것, 약점은 실도면과 안 닮았다는 것(다이제스트: B1 충실도 FAIL, KS 0.5792 / TV 0.265).
- **T-EXT = 외부 정답원(external truth)**: 제3자(핀란드 주거 도면셋 CubiCasa5k)가 사람 손으로 붙인 벽 라벨. 장점은 진짜 사람 판단, 약점은 (i) 도메인이 핀란드 주거로 편향, (ii) 비상업(NC) 라이선스라 학습가중치 탑재 불가·참조만(R23).
- **T-SILVER = 은 정답원(silver truth)**: AI 판정자(LLM 배심 5기)가 도면을 읽고 매긴 벽 판정. "금(gold)"이 아니라 "은(silver)" — 사람만큼 못 믿는다는 뜻. 다이제스트: 탐지기와의 상관 Pearson 0.2911, 배심 5기는 2어휘 가문(fable+sol vs opus+sonnet+grok).
- **T-META = 변형 정답원(metamorphic truth)**: 라벨이 아니라 **성질**을 정답으로 삼는다. "도면을 회전·이동·반사·축척·단위변환·explode 해도 벽 판정은 그에 맞게 변해야 한다"는 불변식(invariant)의 위반 여부. 라벨 0으로 아무 도면에나 걸 수 있는 유일한 심판. 절대 진리를 주지 않고 "일관성"만 잰다.

**R-EXT / R-SYN / R-SILVER / R-META** = 각 평가원에서 쓰는 응답 지표(무엇으로 점수 매기나). 평가원마다 척도가 다르다는 점이 이 설계의 핵심 난점이며 §2에서 정면으로 다룬다.

**model_family(C, 보조 요인) 두 수준**:
- **deterministic-tuned = 결정론 탐지기**: 손으로 정한 규칙의 가중합. 다이제스트의 v1 = 4증거 채널(parallel 0.35 / thickness 0.25 / junction 0.20 / layer 0.20), 두께 대역 50~400mm, 각도 허용 2°, overlap 0.5, snap 6mm. "학습"이란 게 없고 노브(knob) 튜닝만 있다.
- **learned = 학습 탐지기**: 데이터로 파라미터를 맞춘다. 다이제스트의 1단 = HistGradientBoosting(GBDT, 6특징) → val F1 0.517.

**대각/비대각(diagonal / off-diagonal)**: 학습 정답원과 평가 정답원이 같은 셀(예: T-EXT로 배우고 T-EXT로 채점)이 **대각**, 다른 셀(T-SYN로 배우고 T-EXT로 채점)이 **비대각**. 이 제안의 표적은 대각과 비대각의 낙폭이다.

---

## 요지 (executive summary)

P3는 탐지기 성능을 겨루는 실험이 아니라 **정답원끼리 서로를 믿을 수 있는지**를 겨루는 메타실험이다. 방법은 하나의 통계량 — 학습정답원(A) × 평가정답원(B)의 **상호작용 효과** — 에 전부를 건다. 대각(같은 원)만 높고 비대각(다른 원)이 급락하면, 탐지기는 "벽"이 아니라 "그 정답원의 버릇"을 배운 것이고, 부트스트랩 사슬(합성→은→외부로 신뢰를 물려주는 사슬)이 닫히지 않았다는 계량 증거가 된다. 이는 red team T1(대리 독립성)·R28(leaky split→false progress)을 **추정 가능한 수치**로 바꾼다.

핵심 강점은 다이제스트에 **이미 두 셀의 앵커가 존재**한다는 것이다: GBDT가 CubiCasa로 배우고 CubiCasa로 평가한 (T-EXT→T-EXT) 대각이 F1 0.517, 결정론 탐지기가 CubiCasa로 전이한 (비-EXT→T-EXT) 비대각이 F1 0.2358. 두 값의 간극(≈54% 상대 낙폭)이 이 실험의 사전 동기다. 단, 두 값은 model_family가 섞여(결정론 vs 학습) 깨끗한 교차 셀이 아니므로 앵커일 뿐 결과가 아니다(status=UNRUN).

핵심 위험은 세 가지이며 §7·§8에서 정직하게 다룬다: (1) T-SYN 축은 벽 합성 생성기(PR-1)가 아직 없어 **BLOCKED**, (2) 좌표계·축척 불일치(px 대 mm)가 진짜 낙폭을 가장하는 **CRS 교란**, (3) 정답원과 도면 도메인이 얽혀 상호작용을 도메인 이동으로 오귀속하는 **교란(confounding)** — 셋 중 어느 것도 못 풀면 P3는 죽어야 한다.

---

## 1. 이론적 근거·선행연구

이 제안은 세 갈래 방법론 계보 위에 서 있다. 순서대로 "왜 이 설계가 정당한가"를 쌓는다.

### 1.1 데이터셋 편향 진단 — 교차평가 행렬의 직계 조상

가장 직접적인 조상은 **데이터셋 편향(dataset bias)** 진단이다. Torralba & Efros, "Unbiased Look at Dataset Bias"(CVPR 2011, 확신)가 두 가지를 했다: ① "Name That Dataset" 게임 — 이미지가 어느 데이터셋에서 왔는지 맞히는 분류기를 학습시켜, 데이터셋마다 고유한 "지문(signature)"이 있음을 증명. ② **교차 데이터셋 일반화 행렬** — A로 학습→B로 평가한 성능을 행렬로 깔고, 대각(같은 셋)이 높고 비대각(다른 셋)이 급락하는 정도로 "이 성능이 개념을 배운 것인가 셋을 외운 것인가"를 판정. **P3의 train×eval 행렬은 이 교차 일반화 행렬을 정답원 축으로 옮긴 것과 정확히 동형(isomorphic)이다.** 차이는 우리 축이 "데이터셋"이 아니라 "라벨을 만든 방식(정답원)"이라는 것 — 즉 우리는 입력 분포 편향이 아니라 **감독 신호(supervision)의 편향**을 잰다.

관련: Khosla et al., "Undoing the Damage of Dataset Bias"(ECCV 2012, 요검증) — 편향을 분리해 모델링하는 후속. P3에서는 §2의 혼합모형이 이 역할을 한다.

### 1.2 분포 이동·지름길 학습 — "버릇을 배운다"의 메커니즘

두 번째 갈래는 **왜** 대각만 높아지는가의 메커니즘이다.

- **분포 이동(dataset shift / covariate shift)**: Quiñonero-Candela et al., "Dataset Shift in Machine Learning"(MIT Press, 2009, 확신). 학습 분포와 평가 분포가 다르면 성능이 무너진다는 일반 이론. P3의 비대각 낙폭은 정답원이 만든 라벨 분포의 이동으로 해석된다.
- **지름길 학습(shortcut learning)**: Geirhos et al., "Shortcut Learning in Deep Neural Networks"(Nature Machine Intelligence, 2020, 확신). 모델은 "의도한 개념" 대신 데이터에 우연히 상관된 **손쉬운 단서**를 배운다. 합성 생성기가 벽을 항상 "정확히 평행한 이중선 + 고정 두께"로 그리면, 탐지기는 "벽"이 아니라 "그 산술 규칙"을 배운다 — 이것이 패킷이 말하는 "합성 생성기의 산술 tell"이다.
- **Clever Hans 효과**: Lapuschkin et al., "Unmasking Clever Hans predictors"(Nature Communications, 2019, 요검증). 겉으론 맞히지만 엉뚱한 근거로 맞히는 예측기. 은 정답원(silver)의 편향을 배운 탐지기가 실도면에서 무너지는 것이 이 사례다.
- **자기학습의 확증 편향(confirmation bias in self-training)**: Arazo et al., "Pseudo-Labeling and Confirmation Bias in Deep Semi-Supervised Learning"(IJCNN 2020, 요검증). 모델이 자기 예측을 라벨로 되먹이면 편향이 증폭된다. red team 공격 A(PR-2)의 "합치는 확증이 아니라 편향 증폭"이 바로 이 현상이며, P3는 그 증폭을 상호작용 효과로 계측한다.

### 1.3 실험설계·측정이론 — 이 좌석의 정당성

세 번째 갈래가 이 좌석(doe)만이 가져오는 것이다.

- **완전요인설계·상호작용(full factorial, interaction effects)**: Fisher, "The Design of Experiments"(1935); Box, Hunter & Hunter, "Statistics for Experimenters"; Montgomery, "Design and Analysis of Experiments"(전부 확신). 완전교차(3×4)에서 main 효과와 2원 상호작용은 별칭(aliasing) 없이 완전 분리된다. P3의 표적이 정확히 A×B 상호작용이므로 **fraction(부분요인)을 쓰지 않는 것이 옳다** — 표적을 흐리지 않기 위해.
- **강건설계·잡음요인(robust design, noise factors)**: Taguchi의 inner/outer array 개념(확신). P3에서 도면 population과 firm(L-FIRM)은 outer array(잡음), 정답원은 inner array(제어). 단 P3는 강건성 최적화가 아니라 **상호작용 계측**이 목표라 outer array를 최소(층화 30장)로 잡는다 — 잡음을 평균해 없애는 게 아니라 신호를 깨끗이 보는 게 목적.
- **일반화가능도 이론(Generalizability theory, G-theory)**: Cronbach et al., "The Dependability of Behavioral Measurements"(1972, 개념 확신·서지 요검증). 측정 신뢰도를 여러 **facet(국면)**으로 분해한다. P3를 G-theory로 다시 쓰면: 정답원은 하나의 facet이고, **전체 분산 중 정답원 facet에 귀속되는 비율 = 정답원 특이성(source specificity)**. 상호작용이 크다 = 정답원 facet 분산이 크다 = 측정이 정답원에 의존한다. 이 관점은 §2에서 상호작용을 분산성분으로 보는 근거를 준다.
- **평정자 간 신뢰도(inter-rater reliability)**: Cohen's kappa(1960), Krippendorff's alpha, Fleiss' kappa(확신). 은 배심 5기의 상호 일치도를 이 지표로 잰다. 다이제스트가 "2어휘 가문"이라 한 것 = 배심이 5독립이 아니라 ~2 클러스터로 뭉친다 = kappa가 가문 내에선 높고 가문 간엔 낮으리라는 가설.

### 1.4 라벨 없는 검증 — 정답이 없을 때 무엇을 할 수 있나

- **변형 검사(metamorphic testing)**: Chen et al.의 metamorphic testing(개념 확신·서지 요검증). "정답을 몰라도, 입력을 변형했을 때 출력이 따라야 할 관계"로 검증한다. oracle(정답 신탁)이 없는 시스템 검증의 표준 기법. T-META가 이 계보이며, 라벨 0 제약 하에서 유일하게 전 도면에 걸 수 있는 심판이라는 특권을 가진다.
- **약한 감독·데이터 프로그래밍(weak supervision, data programming)**: Ratner et al., Snorkel(NeurIPS 2016 / VLDB 2017, 개념 확신·venue 요검증). 여러 잡음 라벨 함수의 **일치·의존 구조를 모델링**해 라벨을 합성. P3의 다원 정답원은 곧 다원 라벨 함수이며, PR-2와 병합하면 "이들이 독립인가 상관인가"가 Snorkel의 의존 구조 추정과 같은 질문이 된다.
- **sim-to-real 격차·도메인 무작위화**: Tobin et al.(IROS 2017, 요검증). 합성으로 배운 게 실물로 안 간다는 문제와 그 완화(무작위화). B1 충실도 FAIL은 곧 sim-to-real 격차의 정량이며, P3의 T-SYN→T-EXT 비대각이 이 격차를 직접 측정한다.

**요약**: P3 = (교차 데이터셋 일반화 행렬 §1.1) × (정답원을 facet으로 보는 G-theory §1.3) 를 결합해, 지름길·확증편향(§1.2)이 정답원 축에서 일어났는지를 완전요인 상호작용으로 계량하는 설계다. 어느 한 계보도 새 발명이 아니며, 새로운 것은 **"정답원"을 요인으로 승격시켜 교차한 것** 하나다.

---

## 2. 알고리즘 정확 스펙

### 2.1 대상·기호

- 학습 정답원 $A \in \{\text{SYN, EXT, SILVER}\}$ (3수준). T-META는 라벨이 없어 **학습 불가 → 평가전용**, 그래서 A에는 없다.
- 평가 정답원 $B \in \{\text{SYN, EXT, SILVER, META}\}$ (4수준).
- 모델 계열 $C \in \{\text{det, learned}\}$ (2수준, 보조).
- firm 블록 $f$ (L-FIRM), 도면 $d$ (셀당 층화 30장), 은 생성 반복 $r$ (T-SILVER 관여 셀만 $r=1..3$).

전체 셀 = $3 \times 4 = 12$ (×C = 24). 대각 셀 = {SYN→SYN, EXT→EXT, SILVER→SILVER} 3개. 비대각 9개 중 META 열 3개(SYN→META, EXT→META, SILVER→META)는 **구조상 대각이 존재할 수 없는** 특수 비대각(META로는 학습 못 하므로).

### 2.2 셀 파이프라인 (단일 셀 (A,B,C)의 정확한 절차)

```
FUNCTION run_cell(A, B, C, seed):
    # --- 학습(train on A) ---
    IF C == learned:
        L_A  = load_labels(source=A)              # A 정답원의 per-handle 벽 라벨
        Xtr  = features(drawings_of(A))           # 6특징: parallel, thickness, junction,
                                                  #        log(length), sin2θ, cos2θ
        model = HistGradientBoosting.fit(Xtr, L_A, random_state=seed)
    ELSE:  # C == det, "학습"=노브 보정(calibration)
        model = calibrate_knobs(                   # 4채널 가중 + 대역을 A에 맞춤
                    objective = maximize_agreement_with(source=A),
                    grid = {w_parallel, w_thick, w_junction, w_layer,
                            thick_band, angle_tol, overlap, snap},
                    seed = seed)                   # 격자탐색: 무작위 X, seed는 tie-break만
    # --- 평가(eval on B) ---
    E_B  = eval_drawings(source=B, n=30, stratified_by=firm)   # L-FIRM 블록, IR freeze
    yhat = model.predict(features(E_B))            # per-handle 벽 점수
    IF B == SILVER:                                # 비결정 → 3반복
        scores = [ metric_B(yhat, silver_labels(E_B, rep=r)) for r in 1..3 ]
        Y = mean(scores);  s2_silver = var(scores)
    ELSE:                                          # SYN/EXT/META 결정 → 1회
        Y = metric_B(yhat, truth_B(E_B));  s2_silver = 0
    RETURN Y, s2_silver
```

핵심 규약:
- **캐시 IR freeze**: 각 도면의 중간표현(IR)을 한 번 만들고 동결. 셀 간 IR 재계산 금지(비교의 공정성).
- **run 순서**: learned 셀만 무작위화(적합의 순서 효과 제거). 결정론 셀은 순수 함수라 순서 무의미.
- **noise 상속**: T-SILVER 관여 셀만 은 생성 3반복(은 판정의 비결정성을 분산에 반영). T-SYN/T-EXT/T-META는 결정론이므로 반복=population(도면만 늘리면 됨).

### 2.3 평가원별 지표 $\text{metric}_B$

평가 단위는 **per-handle(핸들=선분 하나)** 로 고정한다(red team T6 대응 — 집합-조립 지표와 섞지 않음).

- **B=EXT → R-EXT**: per-handle F1 (CubiCasa Wall 클래스 모서리 대비). 다이제스트 앵커: GBDT val F1 0.517, 기저율 0.118.
- **B=SYN → R-SYN**: per-handle F1 (합성 구성 정답 대비). **주의**: 다이제스트가 "S팩 채점우주에 음성 0개 = 정밀도 공허"라 경고 → S-only는 정밀도가 무의미하므로 **채점우주에 음성 핸들을 반드시 포함**(F/M 팩 또는 음성 주입)해 F1을 well-posed로 만든다. 안 하면 SYN 대각이 가짜로 1.0(다이제스트 B2 S 1.0/1.0).
- **B=SILVER → R-SILVER**: 탐지기 per-handle 벽점수와 은 판정의 상관(다이제스트 B5는 도면수준 Pearson 0.2911 사용). per-handle 일치(kappa)와 도면수준 Pearson을 **둘 다** 보고(집계수준 민감도).
- **B=META → R-META**: 변형 불변식 만족률. **필수(red team T7)**: 0벽/전벽 sentinel(센티널=함정 도면) + recall 최저선을 랭킹 사용 **전에** 탑재. 위반율만 보면 "0벽 탐지기"가 만점을 받는다. 다이제스트 앵커: 강체·단위 1.0 PASS, scale 0.7624 FAIL(strict FAIL 기록).

### 2.4 정규화 낙폭 — 척도가 다른 열을 비교 가능하게

문제: 열마다 지표가 달라(F1 vs Pearson vs 불변율) 12셀을 한 ANOVA에 그냥 넣으면 **비교 불가능한 단위를 섞는다**. 해법: 원점수 $Y_{ijc}$를 **평가 열 안에서** 정규화한 **낙폭 $D$**를 응답으로 쓴다.

대각이 존재하는 열($j \in$ {SYN, EXT, SILVER})의 비대각 셀 $(i \neq j)$:
$$
D_{ijc} \;=\; \frac{Y_{jjc} - Y_{ijc}}{\max(Y_{jjc},\ \tau_j)}
$$
- $Y_{jjc}$ = 열 $j$의 대각(천장). $\tau_j$ = 그 지표의 FAIL 밴드(0 나눗셈·소분모 폭주 방지 바닥값).
- **대각이 바닥 이하면**($Y_{jjc} < \tau_j$) 상대낙폭을 계산하지 않고 **"정답원 $j$에 학습가능 신호 없음"** 플래그(→ kill 조건). 다이제스트가 은 대각을 Pearson 0.2911로 시사하므로, SILVER 열은 실제로 이 분기에 걸릴 가능성이 사전적으로 높다 — 이는 P3의 중요한 사전 예측이다.

META 열(대각 없음): 상대낙폭 대신 **절대 밴드**를 직접 쓴다. 셀 통과 = (불변식 만족률 ≥ prereg 밴드) AND (sentinel이 올바르게 실패) AND (recall ≥ 최저선).

### 2.5 프리레그 판정 규칙 (평가 전 봉인)

- **셀 판정**: $D_{ijc} > 0.20$ (대각 대비 상대 20%p 초과 낙폭) → 해당 (i→j) 쌍은 **"정답원 특이 과적합"**.
- **프로그램 판정**: $\overline{D} = \text{mean}_{i\neq j} D_{ijc} > 0.20$ → **부트스트랩 사슬 미폐합**(사슬이 안 닫힘).
- **표적 벽**: train=SYN → eval=EXT 셀의 낙폭. 이 셀이 크면 "합성으로 배운 게 실무로 안 간다"가 확정.
- 방향: 낙폭 **작을수록** 사슬 폐합(정답원끼리 호환). null(어떤 쌍이 서로 잘 전이)도 반드시 보고 — 그 쌍은 "호환 정답원"으로 등록.

### 2.6 상호작용 추정 모형 (혼합모형)

응답은 **낙폭 $D$** (또는 유계지표는 logit 변환한 $g(Y)$). 완전교차라 별칭 없이 다음을 적합:
$$
g(Y_{ijcf}) = \mu + \alpha_i + \beta_j + (\alpha\beta)_{ij} + \gamma_c + (\alpha\gamma)_{ic} + (\beta\gamma)_{jc} + u_f + \varepsilon_{ijcf}
$$
- $\alpha_i$ = train_truth main, $\beta_j$ = eval_truth main, $(\alpha\beta)_{ij}$ = **표적 상호작용**.
- $\gamma_c$ = model_family main; $(\alpha\beta\gamma)$ 3원은 **24셀 완전판에서만** 별칭 없이 추정, 12셀로 축소 시 C를 빼고 $(\alpha\beta)$만 clean 유지(resolution_alias 계약과 일치).
- $u_f \sim N(0,\sigma^2_{\text{firm}})$ = L-FIRM 랜덤 블록.
- **오차 구조의 비대칭(deterministic_note)**: 결정론 셀은 순수 함수 → $\varepsilon$ 분산 = 도면 population 분산뿐. 은 관여 셀만 은생성 분산성분 $\sigma^2_{\text{silver}}$ 추가(3반복에서 추정). 따라서 이분산(heteroscedastic) 혼합모형 — 은 셀에 별도 분산성분을 명시적으로 넣는다(안 넣으면 은 잡음을 상호작용으로 오인, 예상실패 ③).
- **G-theory 독법**: $\text{Var}[(\alpha\beta)]$ 가 전체 분산에서 차지하는 비중 = 정답원 특이성. 이 비중이 크면 "측정이 정답원에 의존".

### 2.7 통계 검정력·다중비교

- 셀당 30장·firm 블록. 결정론 셀은 측정잡음 0이라 도면 30장이 곧 검정력. 은 셀은 3반복×30장.
- 다중비교: 9개 비대각 셀 판정에 Holm 또는 BH(Benjamini-Hochberg) 보정(문헌 일반, 확신). 단 표적은 **개별 셀 유의성**이 아니라 **상호작용 크기(effect size)** 이므로, p값보다 $\overline{D}$의 신뢰구간을 1급으로 보고.

---

## 3. 벽 과업 적응 설계 — 실제 하네스에 어떻게 접속하나

### 3.1 세 좌표우주와 그 사이의 함정

다이제스트의 하네스는 **서로 다른 좌표우주 3개**로 흩어져 있다. 이게 P3의 가장 큰 설계 난제다.

| 축 | 정답원 | 좌표 | 특징(다이제스트) |
|---|---|---|---|
| CubiCasa SEG-IR 벡터축 | T-EXT | **px**(축척 미상) | 4,200/400/400, 3.86M 선분, 벽 11.8%, 두께 p50=22px |
| 1.dwg 실도면축 | T-SILVER | **mm** | 도면정의 384, 최대 412,775 선분, 은 Pearson 0.2911 |
| 합성팩축 | T-SYN | **mm** | LINE/LWPOLYLINE/INSERT 3종, B1 FAIL |
| (라벨무관) | T-META | 임의 | 145장 전체 적용 가능 |

**함정 A — 단위 불일치(CRS 교란, 예상실패 ②)**: T-EXT는 px, 나머지는 mm. 두께 대역 특징(50~400mm)을 px에 그대로 못 쓴다. train=SYN(mm)→eval=EXT(px) 비대각의 낙폭이 **정답원 특이성 때문인지 단위 불일치 때문인지 구별 불가**. 대응: (i) 축척 불변 특징만 교차 셀에 허용(sin2θ/cos2θ/log길이/parallel/junction — GBDT가 이미 쓴 6특징이 대체로 축척 불변), (ii) 두께는 상대화(도면 중앙값 두께로 정규화, feyerabend P2의 치수-정박 상대대역과 정합), (iii) CubiCasa 축척을 도면별로 추정(벽두께 px→물리두께 prior 역산)해 mm로 환산 — 단 다이제스트가 "축척 2~15mm/px 전 구간 성적 무감"이라 했으므로 이 환산의 효과는 사전적으로 작다. **CRS 정합은 EXT 관여 셀의 하드 선결(못 풀면 §8 사망조건 2).**

**함정 B — 정답원 ⊗ 도면 도메인 교란**: 정답원마다 라벨이 **자기 도면 위에만** 존재한다(T-EXT 라벨은 CubiCasa 위에만, T-SILVER는 실도면 위에만, T-SYN은 합성 위에만). 그래서 train=SYN→eval=EXT는 정답원도 바꾸고 도면 population도 바꾼다 → 낙폭이 "정답원 특이성"인지 "도메인 이동"인지 얽힌다(confounded).

### 3.2 교란 B를 깨는 설계 — 공유 도면 다중라벨

해법은 **은과 변형은 어느 도면에나 걸 수 있다**는 특권을 쓰는 것이다. 같은 도면 위에 여러 정답원 라벨을 얹으면 도메인을 고정하고 정답원만 바꿀 수 있다.

- 합성 도면 위: {T-SYN(구성정답), T-SILVER(은이 합성을 채점), T-META} 동시 라벨 가능.
- CubiCasa 도면 위: {T-EXT(사람), T-SILVER(은이 CubiCasa를 채점), T-META} 동시.
- 실도면 위: {T-SILVER, T-META}만(SYN/EXT 정답 없음).

→ **동일-def 3원 불일치 구조**(PR-2 병합): 같은 도면에서 (SYN vs SILVER), (EXT vs SILVER), (SYN vs META), (EXT vs META)의 불일치를 직접 측정. 이는 전이(transfer)와 **독립적인** 증거축이며, 상호작용 낙폭에서 도메인 성분을 뺄 수 있게 한다. 다이제스트 B5의 "full-vs-nb 1.0(탐지기는 레이어명 신호 0)"은 탐지기 증거축과 은 증거축이 대체로 독립이라는 앵커 — 즉 은을 별도 정답원으로 취급하는 게 정당하다는 사전 증거.

### 3.3 전이 실패 0.236과 GBDT 0.517을 알고 있는 상태에서 P3가 더 가져오는 것

다이제스트는 이미 두 개의 부분 셀을 채워 놓았다:
- (learned, EXT→EXT) = GBDT val F1 **0.517**, AUC 0.9215 — EXT 열 학습계열 대각.
- (det, 비EXT→EXT) = 결정론 v1 CubiCasa 전이 F1 **0.2358** — EXT 열 결정론 비대각-격.

두 값의 간극(0.517 vs 0.2358 ≈ 54% 상대 낙폭)은 "무언가 전이가 안 된다"를 보여주지만 **무엇이 원인인지 말하지 못한다** — model_family(결정론 vs 학습)와 train_truth가 동시에 바뀌었기 때문. **P3가 추가로 주는 것 = 그 간극의 분해**:
1. **learned 계열 안에서** (SYN→EXT) vs (EXT→EXT) 비교 → model_family 고정, train_truth만 변화 → 순수 정답원 낙폭.
2. **train=EXT 고정**으로 (EXT→EXT) vs (EXT→SILVER) vs (EXT→META) → 같은 학습, 다른 심판 → 심판(정답원) 특이성.
3. 두 계열 교차(C)로 "사슬 폐합이 결정론에서만/학습에서만 되는가" 부수 확인.

즉 P3는 0.517과 0.2358 사이의 54% 간극이 (a) 정답원 탓인지 (b) 계열 탓인지 (c) 도메인 탓인지를 **분해 가능한 세 성분으로 쪼갠다**. 이것이 단일 성능 측정(0.517, 0.2358)이 못 하고 P3만 하는 일이다. GBDT가 "성능"을 말한다면, P3는 그 성능이 **믿을 만한 정답에서 나온 것인지**를 말한다.

---

## 4. 데이터·컴퓨트 요구

전제(다이제스트): RTX 5070 Ti 16GB · RAM 64GB · DGX Spark(Ornith-35B) **현재 unreachable**(승인은 됨) · 프런티어 VLM API=유일 결재 게이트(미승인).

### 4.1 로컬 실행 계획 (첫 신호 며칠 내)

- **결정론 arm 전 12셀**: 순수 CPU/NumPy(fast_score 동치 고속 채점기). 3.86M 행도 RAM 64GB에 적재 가능(다이제스트가 GBDT를 이미 로컬에서 돌렸으므로 메모리 실증됨). 최대 412,775 선분 도면이 연산 병목이나 per-drawing 채점은 셀당 30장 층화라 총량 관리됨.
- **소형 학습 arm(GBDT)**: HistGradientBoosting은 CPU 친화. 다이제스트 val F1 0.517이 이미 로컬 산출 → SYN/SILVER 라벨로의 재학습도 동급 비용.
- **T-META 열**: 라벨 0, 순수 변형+재채점 → 로컬 CPU. CL-D 배터리 재사용.
- **T-SILVER 캐시**: B5에서 이미 실도면에 은 라벨이 산출됨 → **캐시 동결분은 API 재호출 불요**. 단 은을 **새 population**(합성·CubiCasa)에 거는 셀은 신규 판정 필요 → API 게이트(§4.3).
- **cheapest_probe(SYN↔META 4셀)**: 반나절, 로컬. "합성으로 배운 게 무라벨 변형 게이트라도 통과하나".

### 4.2 DGX 계획 (분리·현재 BLOCKED)

- compute_plan: DGX는 **learned × T-EXT 대형 학습만**. 즉 GBDT를 넘어선 대형 학습 탐지기(예: GNN/DL)를 EXT로 학습하는 확장 arm.
- DGX가 unreachable인 지금 이 arm은 **BLOCKED / 이연**. **P3 코어(결정론 전셀 + GBDT 학습셀 + META열)는 전부 로컬 실행 가능** — DGX 없이 첫 신호와 프로그램 판정까지 도달한다. DGX arm은 "learned 계열의 상한을 더 밀어붙일 때"만 필요한 선택적 확장.

### 4.3 API 예산·게이트

- 은을 **신규 population**에 거는 셀(예: 은이 CubiCasa/합성을 채점)은 프런티어 VLM/LLM 배심 호출 → **미승인 게이트**. 승인 전까지 이 셀들은 **캐시된 실도면 은 라벨로 제한**되며, 그 경우 §3.2의 "CubiCasa 위 은 라벨" 교란분리는 축소된다(부분 PARTIAL). 이는 정직하게 PASS_WITH_DEFERRAL로 표기.
- FloorPlanCAD(5,308 래스터)·qwen2.5-VL-3B·Zenodo10K/Text2CAD/ArchCAD/pseudo-floor-plan-12k는 P3 코어 벡터 매트릭스 **밖**(래스터/VLM은 CL-G 트랙). P3는 벡터 정답원 4개에 집중, 자산은 확장 예비로만 명시.

### 4.4 자원 요약표

| arm | 위치 | 상태 | 비용감(정성) |
|---|---|---|---|
| 결정론 12셀 | 로컬 CPU | 실행가능 | 낮음(며칠) |
| GBDT 학습셀(EXT/SILVER-캐시) | 로컬 CPU | 실행가능 | 낮음 |
| GBDT 학습셀(SYN) | 로컬 | **BLOCKED**(PR-1 생성기 부재) | — |
| META 열 | 로컬 CPU | 실행가능 | 매우 낮음 |
| 은 신규 population 셀 | API | **BLOCKED**(미승인) | 소액 API |
| learned×EXT 대형 | DGX | **BLOCKED**(unreachable) | 확장 선택 |

---

## 5. 구현 계획

### 5.1 모듈·파일 골격 (제안 — 실제 API는 기존 모듈 대조 필요)

기존 도구(evidence_grid / fast_score / cubicasa_ir / cubicasa_ml)를 **오케스트레이션 얇은 층**으로 감싼다. 정답원마다 동일 인터페이스 `label(drawing) -> per_handle_wall_labels`를 노출하는 어댑터를 두는 게 핵심 — 정답원을 요인으로 다루려면 정답원이 교체 가능한 부품이어야 한다.

```
cross_factorial/
  truth_sources/
    base.py         # TruthSource 인터페이스: labels(draw), eval_set(n, strat), is_deterministic
    t_syn.py        # PR-1 생성기 산출 벽 정답 (생성기 인도 전엔 stub → BLOCKED)
    t_ext.py        # CubiCasa Wall 모서리; cubicasa_ir 어댑터; 레이어중립(누출 0)
    t_silver.py     # 은 배심 라벨; B5 캐시 로더 + (승인 시) API 신규판정; 3반복
    t_meta.py       # 변형 배터리(CL-D 재사용) + sentinel/recall 최저선(T7)
  detectors/
    det_tuned.py    # evidence_grid/fast_score 감싼 4채널; calibrate_knobs(source)
    learned_gbdt.py # cubicasa_ml 감싼 HistGradientBoosting; fit(source_labels, seed)
  orchestrator/
    matrix.py       # 3×4(×2) 셀 정의, run 순서(learned만 무작위화), IR freeze
    normalize.py    # §2.4 낙폭 D, τ 바닥값, 대각-바닥 kill 플래그
    stats.py        # §2.6 혼합모형(A+B+A×B+C+firm), 이분산(은 분산성분), 20% prereg
    report.py       # effects_table/interactions_found(UNRUN) + 증거 xlsx(의무) + 셔플대조
```

### 5.2 기존 도구 접속점 (인터페이스 수준 — 실제 시그니처는 코드 대조 요망, 요검증)

- **cubicasa_ir** → `t_ext.py`: SEG-IR 변환(다이제스트: 5,000장 실패 0, 레이어중립 누출 0)을 정답원 어댑터로. 진리=Wall 클래스 요소 모서리.
- **cubicasa_ml** → `learned_gbdt.py`: 6특징 파이프라인·GBDT 적합/예측. 다이제스트 앵커(F1 0.517/AUC 0.9215)를 EXT→EXT 대각 회귀검정으로 재현(구현 정합성 확인용).
- **fast_score** → `det_tuned.py`: NumPy 동치 고속 채점기로 결정론 예측. calibrate_knobs는 이 위에 격자탐색만 얹음.
- **evidence_grid** → `det_tuned.py`: 다증거 격자(4채널) 구조 재사용.

### 5.3 예상 개발 규모 (추정 — 실측 아님)

- 어댑터 4종: t_ext/t_silver(캐시 로더)/t_meta는 기존 산출물 위 얇은 래퍼(소). t_syn은 PR-1 인도 후 착수(BLOCKED).
- detectors 2종: 기존 fast_score/cubicasa_ml 래핑(소~중).
- orchestrator 4파일: 신규 핵심(matrix/normalize/stats/report), 중간 규모. stats.py의 이분산 혼합모형이 난이도 최고점(문헌 표준이나 은 분산성분 명세 주의).
- 증거 의무: 셀별 xlsx·셔플 대조군·프리레그 봉인 파일. 평가원칙(고정)과 정합.

---

## 6. 실험 셀 정의

원칙: val=개발·튜닝 허용 / test=방법당 단발 / 합격선 평가 전 봉인 / 셔플 대조군 의무 / 증거 xlsx 의무 / 실패도 사유와 함께 기록. 모든 결과 슬롯 **UNRUN**. 합격선은 사전 봉인값(프리레그)이며 다이제스트 앵커로 근거를 댔다.

### 6.1 코어 매트릭스 (12셀, 각 ×C={det,learned}; 셀당 val 30장 층화, L-FIRM 블록)

대각선 3셀:

| 셀 | 가설 | 지표 | 프리레그 합격선 | 킬 조건 | 예산 | 시드 |
|---|---|---|---|---|---|---|
| **SYN→SYN** | 합성정답을 합성으로 재현=천장 | R-SYN F1(음성주입 후) | ≥0.90 (well-posed로 고친 뒤) | 대각조차 FAIL밴드<0.50면 합성에 학습신호 없음 | 로컬 소 | L-SEED seed-disjoint |
| **EXT→EXT** | 사람정답 재현=천장 | R-EXT F1 | ≥0.45 (앵커 0.517 근방) | <0.30이면 외부정답도 저신호 | 로컬(GBDT 재현) | seed 5개 평균 |
| **SILVER→SILVER** | 은정답 재현=천장 | R-SILVER Pearson | ≥0.50 | **≤0.30이면(앵커 0.2911) 은 대각이 이미 kill밴드** | 로컬(캐시) | 은 3반복 |

비대각 6셀(교차 정답원, non-META):

| 셀 | 가설 | 지표(정규화) | 합격선(낙폭) | 킬 | 예산 | 시드 |
|---|---|---|---|---|---|---|
| **SYN→EXT** | **표적 벽**: 합성→실무 안 감 | $D$ vs EXT대각 | 낙폭 ≤0.20 통과 / >0.20 "합성 과적합" | 붕괴(≈앵커 54%)면 합성 정답원 실무부적격 | 로컬 | seed-disjoint |
| SYN→SILVER | 합성→은 전이 | $D$ vs SILVER대각 | ≤0.20 | — | 로컬 | 은 3반복 |
| EXT→SYN | 사람→합성 역전이 | $D$ vs SYN대각 | ≤0.20 | — | 로컬(NC 플래그) | — |
| EXT→SILVER | 사람→은 전이 | $D$ vs SILVER대각 | ≤0.20 | — | 로컬(NC 플래그) | 은 3반복 |
| SILVER→SYN | 은→합성 전이 | $D$ vs SYN대각 | ≤0.20 | — | 로컬 | — |
| SILVER→EXT | 은→실무 전이 | $D$ vs EXT대각 | ≤0.20 | 붕괴면 은은 실무 일반화 실패 | 로컬 | 은 3반복 |

META 열 3셀(평가전용, 대각 없음 → 절대 밴드):

| 셀 | 가설 | 지표 | 합격선(절대) | 킬 | 예산 | 시드 |
|---|---|---|---|---|---|---|
| SYN→META | 합성학습이 불변식 지키나 | 불변식 만족률+sentinel+recall최저선 | 만족률 ≥0.80 AND sentinel 정상실패 AND recall≥floor | sentinel 통과(0벽탐지기)면 지표 무효 | 로컬 소 | — |
| EXT→META | 사람학습이 불변식 지키나 | 동상 | 동상 | 동상 | 로컬 | — |
| SILVER→META | 은학습이 불변식 지키나 | 동상 | 동상 | 동상 | 로컬(캐시) | 은 3반복 |

주: **SYN 관여 4셀(SYN→\*, \*→SYN)은 PR-1 생성기 인도 전 BLOCKED**. **EXT 학습행(EXT→\*)은 NC 라이선스라 산출물이 방법검증용, 제품 아님**(R23).

### 6.2 cheapest_probe (선행 4셀, 반나절)

train=SYN × C={det,learned} × eval={SYN, META} = 4셀. "합성으로 배운 게 무라벨 변형 게이트라도 통과하나". PR-1 stub이라도 최소 생성기가 있으면 즉시. 통과 못 하면 SYN 정답원 전체가 조기 의심 → 비싼 셀 절약.

### 6.3 confirmation_run (이연, status=PASS_WITH_DEFERRAL)

메인 매트릭스에서 **가장 잘 전이된 (train,eval) 쌍**을 hold-out firm(L-FIRM 미사용 회사)에서 재실행 → 전이 안정성 확인. 코어 판정 후 착수하므로 PASS_WITH_DEFERRAL.

### 6.4 셀 수 정당화

12(또는 24)는 방법이 요구하는 정확한 수: 상호작용을 별칭 없이 추정하려면 완전교차가 필요하고(§2.6), 3원 A×B×C까지 clean하려면 24가 필요하나 예산 압박 시 C를 접어 12로 축소하며 A×B는 여전히 clean. 과소(대각만 보면 상호작용 추정 불가)도 과잉(fraction 쓰면 표적 상호작용이 흐려짐)도 아니다.

### 6.5 사전 효과표 가설 (UNRUN — 앵커 기반 기대, 결과 아님)

- 대각: SYN 높음(단 음성주입 전엔 공허), EXT 중간(앵커 0.517), **SILVER 낮음(앵커 0.2911 → kill밴드 근접)**.
- 비대각 최대 낙폭: **SYN→EXT**, 그리고 SILVER→EXT(합성·은 → 실무가 벽). 앵커(결정론 0.2358 vs GBDT 0.517)가 큰 낙폭을 시사하나 계열 교란이라 clean 셀은 UNRUN.
- 상호작용 A×B: 사전 가설 **크다**(정답원 특이성 존재) → "합성이면 충분"·"은이면 충분" 단독 주장 반증 예상(card rule 4). status=UNRUN.

---

## 7. red team 티켓 응답

패널 보고서 OPEN 34건 중 P3에 걸리는 것을 지목하고 각각 해소/수용 입장을 밝힌다.

- **T1 대리 독립성 (sev 0.75, 최우선)** — **P3가 곧 이 티켓의 실행체(부분)**. 4대리가 같은 "평행 이중선" prior를 공유하면 합치는 편향 증폭. **해소**: PR-2와 병합해 (a) 전이 매트릭스(P3 본체) + (b) §3.2 동일-def 3원 불일치 구조를 함께 산출. 상호작용이 크면 정답원 특이성=독립, 서로 잘 전이하면 공유 prior=상관. 둘을 계량 분리한다. 단 절대 독립성 증명은 불가(abstention ①) — 상호 일치/불일치 구조만 준다.
- **T2 생성기 부재 (0.70)** — **수용(위험 인정) + 의존 선언**. T-SYN은 벽 코드 0인 현재 정답원 자격 없음(PR-1 선결). **P3의 SYN 관여 셀은 PR-1 인도까지 BLOCKED**로 명시(§6.1). PR-1 미인도 시 P3는 2×3(EXT,SILVER)로 축소(→§8 사망조건 1).
- **T5 라이선스 (0.65)** — **수용 + 격리**. T-EXT는 NC → EXT 학습행 산출물은 **방법검증용, 제품 아님**(abstention ②, R23). 전이 측정(방법론)은 참조사용으로 진행 가능하나, 제품 가중치 배포는 PR-3 counsel 서면 클리어까지 금지. 이 경계를 셀 표에 NC 플래그로 못박음.
- **T6 평가 단위** — **해소**. P3는 §2.3에서 **per-handle**로 평가 단위를 명시 선언, 집합-조립 지표와 분리.
- **T7 metamorphic sentinel/recall 최저선** — **채택**. META 열은 위반율-only 금지, CL-D의 sentinel(0벽/전벽)+recall 최저선을 랭킹 전 탑재(§2.3, §6.1 META 셀 합격선에 AND 조건).
- **T15 learned 셀 seed-confounded** — **해소**. 학습 셀은 seed 5개 평균+분산 보고, 합성은 **L-SEED seed-disjoint**(학습/평가 seed 분리, 누출 0). 셔플 대조군 의무(앵커: GBDT 셔플 AUC 0.375 PASS=누출 없음)로 seed 누출 감지.
- **T17** (CL-E에서 doe P3와 함께 인용) — 이 패킷에 **원문 미포함**이라 정확 텍스트는 요검증. 클러스터(truth-source 교차요인) 소속으로 보아, 전이+독립성 이중 증거로 대응(T1과 동일 처방). 정확 텍스트 확인 전 이 응답은 잠정.
- **T34 load-bearing 인용 experiment_executed:false** — **준수**. P3의 effects_table·interactions_found·confirmation_run 전부 UNRUN/DEFERRAL로 정직 표기(이 문서 status 규율). 실행 전 어떤 셀도 PASS로 인용하지 않음.
- **R28 leaky split→false progress** — **P3의 존재 이유**. 이 kill risk를 상호작용 효과로 계량(대각↑/비대각↓ = leak). **R23 CRS/라이선스 kill** — CRS 정합 선결(§3.1 함정 A) + NC 격리로 대응. **card rule 4** — 상호작용으로 단독-정답원 충분 주장 반증.

---

## 8. 인접 제안과의 관계

### 8.1 병합 가능 지점

- **PR-2 (대리 독립성 감사)**: 패킷이 명시("doe P3와 병합"). P3=전이 매트릭스, PR-2=동일-def 불일치. **같은 공유-population 실행에서 한 번에 산출**하는 것이 최적(§3.2). 병합 시 중복 IR 계산 제거.
- **CL-E (truth-source 교차요인 메타실험)**: P3의 클러스터 그 자체([doe P3 + T1/T17]). CL-E는 "전이만이 아니라 동일-def 불일치까지"를 요구 → P3+PR-2 병합본이 CL-E 실행체.
- **CL-D (metamorphic 배터리)**: P3의 META 열이 CL-D 배터리를 **재사용**(sentinel/recall 포함). 개발 중복 없음.
- **CL-K (anti-silver 통제 arm)**: P3의 SILVER 학습행(train=SILVER)이 곧 "silver-distill" arm. CL-K의 gate-only vs silver-distill 대조를 P3 매트릭스 안에 상설 통제로 흡수 가능(반대의견 #2의 실험적 보존).

### 8.2 차별점

- vs **CL-F (학습 사다리 GBDT→GNN)**: CL-F는 "어떤 탐지기가 성능이 좋은가", P3는 "그 성능의 정답이 믿을 만한가". P3는 탐지기 순위를 매기지 않고 **정답원 신뢰도**만 판정. CL-F가 만든 모델을 P3가 심판한다.
- vs **doe P1 (마스터 스크린, PARKED)**: P1은 representation×truth가 family×self-training과 confounded + learned 셀 seed-confounded로 PARK. **P3는 정답원 축만 완전교차해 그 교란을 회피** — P1의 부분집합이자 clean 버전. P1 재개 전에 P3가 정답원 신뢰도 먼저 확정.
- vs 단일 성능 측정(0.517/0.2358): §3.3대로 P3는 그 간극을 정답원/계열/도메인 3성분으로 분해 — 성능수가 못 하는 일.

### 8.3 이 제안이 죽어야 하는 조건 (정직하게)

1. **PR-1 영구 미인도 + PR-3 EXT 차단**: 벽 합성 생성기가 끝내 충실도 게이트를 못 넘고(T2), counsel이 EXT마저 막으면(T5), P3는 SILVER 단독으로 쪼그라든다. 단일 정답원엔 train×eval 상호작용이 성립하지 않으므로 **P3는 죽는다**(교차할 축이 없다).
2. **CRS 교란 해소 불가**: px(EXT) 대 mm(SYN/SILVER) 단위 불일치를 축척불변 특징·상대두께·축척추정 어느 것으로도 못 걷어내면(함정 A), EXT 관여 비대각의 낙폭이 정답원 특이성인지 단위 유물인지 **식별 불가** → 표적 상호작용이 identifiable하지 않다 → **P3는 EXT 축에서 죽는다**(within-unit 비교로 후퇴하거나 폐기).
3. **도면 도메인 교란 분리 불가**: §3.2의 공유-population 다중라벨을 (은 API 미승인 등으로) 확보 못 하면, train×eval 상호작용이 도메인 이동과 완전 confounded → P3는 "정답원 실험"이 아니라 그냥 "도메인 이동 실험"이 됨(그건 CL-F/G 영역) → **정답원 실험으로서는 죽는다**.
4. **상류 붕괴**: CL-A 법의학 감사가 인용 기반 전체를 계측 아티팩트로 판정하면(공격 C), P3가 겨루는 정답원들 자체가 무의미 → **프로그램과 함께 moot**.
5. **역설적 성공에 의한 죽음(좋은 죽음)**: 전 비대각이 낙폭 ≤0.20으로 통과하면 정답원끼리 호환 = 부트스트랩 사슬 폐합 확정 → P3는 **소임을 다하고 은퇴**(더 돌릴 이유 없음). 이건 프로그램에 최선의 결과다.

### 8.4 abstention (P3가 답하지 못하는 것 — 못박음)

- **어느 정답원이 진짜 참인지**는 P3가 못 답한다. 외부 절대 진리가 없다는 게 이 과업의 근본 제약. 전 쌍이 서로 낮게 전이하면 결론은 "믿을 정답원이 없다"이고, 이는 사람라벨/새 정답원 조달 결정(abduction·조달 좌석)으로 hand-off. P3는 "어느 게 참"이 아니라 "서로 얼마나 일관되나"만 준다.

---

*작성 근거: 수치 인용은 전부 패킷 다이제스트(2026-07-18)에서만. 문헌은 §1에 일반지식으로 표기(불확실 인용 '요검증'). 웹 검색 미사용. 기존 모듈 API(§5.2)는 인터페이스 수준 제안이며 실제 코드 대조 필요.*

DOSSIER_COMPLETE: doe_P3
