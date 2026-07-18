# P1 · MASTER FACTOR SCREEN — E2 벽 의미 탐지기 설계공간 분수요인 스크린 심층 도시에

- `seat_id`: `doe_P1`
- 제안 상태: `UNRUN`
- 패널 상태의 승계: `PARKED`
- 확인 실험 상태: `PASS_WITH_DEFERRAL` — 프로토콜만 완성되었고 실행되지 않음
- 작성 근거: 이 패킷의 제안문, 2026-07-18 실측 다이제스트, 패널 보고서만 사용
- 외부 웹 검색: 사용하지 않음
- 증거 경계: 아래의 측정값은 모두 패킷의 실측 다이제스트에서 온다. 나머지 숫자는 설계용 **제안값** 또는 문헌의 서지 정보이며, 새 측정 결과가 아니다.

## 실행 판정 요약

P1의 핵심 아이디어, 즉 여러 탐지기 계열을 OFAT로 하나씩 비교하지 않고 표현·모델·정답원·잡음 처리·자기학습·누수 입도를 한 직교 설계에서 함께 흔드는 발상은 타당하다. 다만 현재 제안문 그대로는 “즉시 실행 가능한 6요인 인과 스크린”이 아니다. 다음 네 가지를 고치거나 통과시켜야 한다.

1. 현재 합성팩은 충실도 게이트 B1에서 `KS 0.5792`, `TV 0.265`로 FAIL이다. 따라서 `T-SYN`을 현실 전이의 1차 판별 진리로 쓰는 본 스크린은 아직 재개할 수 없다. 합성팩 위의 실행은 배관 점검 또는 탐색 실행일 뿐, P1의 확인적 결과가 아니다.
2. `representation`을 추정하려면 graph-IR와 raster가 **같은 도면, 같은 후보 handle, 같은 정답, 같은 split**을 보아야 한다. CubiCasa SEG-IR을 쌍으로 렌더링한 축과 staged DXF를 쌍으로 렌더링한 축은 가능하지만, 벡터 SVG가 없는 FloorPlanCAD를 graph-IR 셀의 다른 데이터셋과 직접 비교하면 표현 효과가 데이터셋 효과와 합쳐진다.
3. `model_family={deterministic, learned}`는 추상 범주라서 그 자체로 설정 가능한 처치가 아니다. P1-v1에서는 이를 `fast_score` 계열의 고정 함수형 규칙 탐지기 대 `cubicasa_ml`의 **동결된 HistGradientBoosting 구현 한 종**으로 좁힌다. 그러므로 B 효과는 “모든 학습법의 효과”가 아니라 이 두 구현 패키지의 평균 차이다. GNN과 VLM은 B가 활성일 때 여는 새 prereg의 후속 수준이다.
4. 제안문의 “주요 2FI는 별칭 안 걸림”과 “8-run fold-over이면 Res V”라는 문장은 수학적으로 보장되지 않는다. 이 설계에서 모든 2요인 상호작용은 다른 2요인 상호작용과 별칭이다. 8개 추가점은 선택된 별칭 사슬을 풀 수는 있지만, 후보점으로 만든 증강 설계의 rank를 직접 확인하지 않고 전역적인 Resolution V라고 부르면 안 된다.

따라서 본 도시에는 P1을 폐기하지 않고 **순차 설계**로 복구한다. Phase 0에서 정답원·쌍표현·split·법무·seed 계약을 봉인하고, Phase 1에서 결정론 8셀 cheapest probe를 실행하며, 그 probe가 신호를 보일 때만 Phase 2의 16셀 전체를 실행한다. 활성 2FI 별칭 사슬은 Phase 3의 표적 증강 설계로 분리하고, 최종 선택 셀은 미사용 firm hold-out에서 단 한 번 확인한다. 현재는 어느 phase도 실행한 것으로 기록하지 않는다.

---

## 1. 이론적 근거·선행연구

### 1.1 OFAT 대신 요인실험을 쓰는 이유

OFAT(one-factor-at-a-time)는 한 번에 하나의 선택만 바꾸므로 “학습법의 우위가 raster에서만 나타나는가”, “silver가 L-DWG에서만 좋아 보이는가” 같은 조건부 효과를 직접 추정하지 못한다. 두 수준 요인실험은 각 셀을 독립적인 제품 후보로만 보는 대신, 응답을 요인의 부호화된 대비로 분해한다. 이 계보의 표준 참고문헌은 Box, Hunter & Hunter의 *Statistics for Experimenters*, Montgomery의 *Design and Analysis of Experiments*, Wu & Hamada의 *Experiments: Planning, Analysis, and Optimization*이다. 판·쪽수는 이 도시에 작성 시 외부 확인하지 않았으므로 실제 인용문에 넣기 전 요검증이다.

6요인 완전요인은 64개 조합을 요구하지만, P1은 16개 조합만 택한 정규(regular) `2^(6-2)` 1/4 fraction이다. 효과 희소성(effect sparsity), 효과 위계(effect hierarchy), 효과 유전성(effect heredity)을 작업 가정으로 두면 적은 실행으로 main effect와 몇 개의 중요한 상호작용 사슬을 찾을 수 있다. 이 가정은 법칙이 아니다. 많은 효과가 동시에 크거나 3요인 상호작용이 크면 Lenth 분석과 2FI 해석 모두 실패하며, 그 자체가 “스크린이 부적합”이라는 결과다.

Plackett–Burman 설계도 고차원 스크리닝 계보에 속하지만, P1은 생성자를 명시한 정규 2수준 fraction이라서 별칭 구조를 정확히 대수적으로 계산할 수 있다는 장점이 있다. 반대로 정규 fraction은 별칭이 완전하므로, 한 사슬 안의 효과를 데이터만으로 분리할 수 없다는 단점이 있다.

### 1.2 이 설계의 정확한 정의관계와 resolution

독립 열을 A, B, C, D로 두고 다음처럼 파생한다.

\[
E=ABC,\qquad F=BCD
\]

따라서 정의대조군(defining contrast subgroup)은 다음과 같다.

\[
I=ABCE=BCDF=ADEF
\]

가장 짧은 비항등 정의단어의 길이가 4이므로 Resolution IV이다. 그 결과 main effect는 어떤 2FI와도 별칭이 아니지만, 3FI와는 별칭이다. “main effect가 2FI와 분리된다”는 말만 맞고, “2FI가 서로 분리된다”는 말은 틀리다.

main-effect 별칭은 다음과 같다.

| 추정 열 | 완전 별칭 사슬 |
|---|---|
| A | `A = BCE = DEF = ABCDF` |
| B | `B = ACE = CDF = ABDEF` |
| C | `C = ABE = BDF = ACDEF` |
| D | `D = BCF = AEF = ABCDE` |
| E | `E = ABC = ADF = BCDEF` |
| F | `F = BCD = ADE = ABCEF` |

2FI 열은 정확히 일곱 사슬이다.

| 사슬 ID | 서로 분리 불가능한 2FI | 함께 별칭인 고차항 |
|---|---|---|
| G1 | `AB = CE` | `ACDF`, `BDEF` |
| G2 | `AC = BE` | `ABDF`, `CDEF` |
| G3 | `AD = EF` | `ABCF`, `BCDE` |
| G4 | `AE = BC = DF` | `ABCDEF` |
| G5 | `AF = DE` | `BCEF`, `ABCD` |
| G6 | `BD = CF` | `ACDE`, `ABEF` |
| G7 | `BF = CD` | `ACEF`, `ABDE` |

나머지 두 직교 열은 순수 3FI 진단 사슬이다.

- H1: `ABD = CDE = ACF = BEF`
- H2: `ACD = BDE = ABF = CEF`

따라서 패킷의 사전 관심 상호작용은 다음처럼 다시 읽어야 한다.

- `A×B`는 단독으로 추정되지 않는다. 관측되는 것은 `AB + CE` 계열의 한 대비다. 즉 representation×family와 truth×self-training을 데이터만으로 가를 수 없다.
- `B×C`는 `AE + BC + DF` 사슬에 들어간다. family×truth, representation×self-training, noise-handling×leakage 중 무엇이 원인인지 16런만으로는 판정할 수 없다.
- `C×F`는 `BD + CF` 사슬에 들어간다. truth×leakage와 family×noise-handling을 가를 수 없다.
- 제안문 예시의 `representation×truth` 대 `family×self-training`은 정확히 `AC=BE`라서 실제 별칭 예가 맞다.

효과 위계나 도메인 지식으로 한 항을 더 그럴듯하다고 **해석**할 수는 있지만, 그것을 식별 또는 증명이라고 쓰면 안 된다. 활성 판정의 단위는 개별 2FI가 아니라 위의 G1–G7 사슬이다.

### 1.3 무반복 요인실험과 Lenth PSE

P1은 셀 수준에서 무반복 설계다. 전통적인 ANOVA의 pure error를 얻지 못하므로 Lenth의 pseudo standard error(PSE)를 사용한다. Lenth의 “Quick and Easy Analysis of Unreplicated Factorials”(1989, *Technometrics*)가 직접 계보다. 서지 제목과 연도는 일반 문헌 지식이며, 최종 참고문헌 형식은 요검증이다.

효과 추정치 집합을 \(e_j\)라 할 때 본 계획의 구현식은 다음과 같다.

\[
s_0=1.5\,\operatorname{median}(|e_j|)
\]

\[
PSE=1.5\,\operatorname{median}\{ |e_j|:|e_j|<2.5s_0\}
\]

P1 prereg의 활성 규칙은 `|effect| > ME(α=0.05)`이다. effect pool 크기를 \(m=15\), Lenth의 pseudo 자유도를 \(\nu=m/3=5\)로 고정하고

\[
ME=t_{0.975,\nu}\,PSE
\]

로 계산한다. 실제 코드에서는 이 식과 Lenth 원 논문 또는 검증된 구현의 critical value를 서로 검산하고, 구현 버전·함수·fixture를 prereg에 해시한다. 개별 margin인 ME를 넘은 항은 `screen-active`일 뿐 확인된 인과효과가 아니다. 동시에 많은 대비를 주장하려면 simultaneous margin 또는 별도 확인 실험이 필요하다.

PSE pool에는 6개 main-effect 열, 7개 2FI 사슬 열, H1/H2의 두 고차 진단 열, 즉 15개 비절편 직교대비를 모두 넣는다. H1/H2는 해석 대상이 아니라 PSE와 “고차 구조가 작다”는 가정을 점검하는 진단이다. H1 또는 H2가 크거나 활성 대비가 너무 많아 작은 효과 집합이 사라지면 Lenth sparsity 가정 실패로 `INCONCLUSIVE` 처리한다.

### 1.4 표현, soft label, self-training, group leakage의 방법론 계보

- **graph-IR 대 raster**: 벡터 그래프는 handle, 인접, 평행, 교차 같은 관계를 명시적으로 보존한다. raster는 선폭·색·문자·국소 텍스처를 보존하지만 좌표 양자화와 역투영 오차를 만든다. CubiCasa5K는 floorplan 분석의 대표 공개 연구축이며, 데이터셋 논문의 정확한 저자열·학회 표기는 요검증이다.
- **confidence-weighted label**: hard consensus가 불확실성을 버리는 문제를 줄이기 위해 label confidence를 sample weight로 보존한다. 지식증류와 soft-target 학습(Hinton, Vinyals & Dean 계보), 약지도 학습의 일반 원리와 닿지만, P1에서는 더 좁게 “고정된 이진 표적 + 고정된 confidence weight”로 구현한다.
- **self-training**: 초기 모델의 고신뢰 예측을 pseudo-label로 다시 학습하는 고전적 반지도 패턴이다. Yarowsky식 bootstrapping과 pseudo-label 계보가 배경이지만, 확인편향이 증폭될 수 있다. 그래서 E는 한 번의 고정 라운드만 허용하며, silver 오염을 독립 진리처럼 재사용하지 않는다.
- **L-DWG 대 L-FIRM**: 같은 firm의 도면 관례가 train과 evaluation에 함께 있으면 레이어명, 치수 관례, 블록 라이브러리, 선폭 관례를 외운 모델이 일반화한 것처럼 보일 수 있다. F는 단순한 cross-validation 옵션이 아니라 convention memorization을 드러내는 처치다. 단, 평가 도면 자체는 두 F 수준에서 동일하게 두고 학습 pool의 firm 포함 여부만 바꿔야 효과를 읽을 수 있다.

### 1.5 P1이 실제로 검증하는 명제

P1-v1의 확인 가능한 명제는 다음으로 제한한다.

> 동일한 per-handle 후보 우주, 동일한 평가 도면, 동일한 label budget에서, 고정된 규칙 탐지기와 고정된 HGB exemplar의 성능 차이가 입력 증거의 표현 방식, 학습·튜닝 정답원, confidence weighting, 한 라운드 self-training, firm leakage 정책에 따라 달라지는가?

이는 “학습은 결정론보다 보편적으로 우월하다”, “graph가 raster보다 본질적으로 낫다”, “silver는 진리다”를 검증하지 않는다. 이 좁은 명제의 범위를 effects table과 결론 첫 문장에 반복해야 한다.

---

## 2. 알고리즘 정확 스펙

### 2.1 입력, 출력, 평가 단위

기본 평가 단위는 패킷 원칙대로 `per-handle wall_member(h)`이다.

- 도면 \(d\)의 후보 handle 집합: \(H_d\)
- 후보 handle: \(h\in H_d\)
- 고정 진리 또는 proxy confidence: \(q_{dh}^{(t)}\in[0,1]\), \(t\in\{SYN,SILVER\}\)
- 모델 점수: \(p_{rdh}\in[0,1]\), 셀 \(r\in\{1,\ldots,16\}\)
- 이진 예측: \(\hat y_{rdh}=1[p_{rdh}\ge \tau_r]\)
- 산출: 셀별 per-handle score/prediction, 도면별 confusion counts, `R-SYN`, `R-SILVER`, sentinel 지표, 자원 로그, seed 로그, effect 대비

모든 표현 수준은 같은 \(H_d\)를 사용한다. raster 수준도 “픽셀 segmentation의 임의 객체”를 평가하지 않고, handle provenance buffer를 통해 같은 후보 handle로 되돌린다. 이 제약을 만족하지 못하는 FloorPlanCAD는 primary A 대비에 들어가지 않는다.

### 2.2 요인의 실행 정의

부호는 아래처럼 고정한다. 효과의 양수는 `+1` 수준이 `-1` 수준보다 응답을 올렸다는 뜻이다.

| 요인 | `-1` 수준 | `+1` 수준 | 실행 가능성 계약 |
|---|---|---|---|
| A representation | graph-IR | raster | 같은 도면·후보 handle·split·정답을 사용. raster↔handle round-trip exactness gate 통과 |
| B model_family | deterministic `fast_score` family | learned frozen HGB exemplar | 두 수준 모두 같은 6-slot feature schema와 같은 label budget을 사용. B의 외삽 범위는 두 구현으로 제한 |
| C truth_source | T-SYN | T-SILVER | **학습·튜닝 source만** 바꿈. 두 응답의 evaluation panel은 모든 셀에서 고정·분리 |
| D label_noise_handling | hard | confidence-weighted | silver 및 pseudo-label의 confidence 처리만 바꿈. evaluation scoring 규칙은 D와 무관하게 고정 |
| E self_training | off | on | on은 정확히 한 번의 pseudo-label refit. 같은 unlabeled pool과 동일한 pseudo-weight cap 사용 |
| F leakage_granularity | L-DWG | L-FIRM | evaluation panel은 동일. train에 같은 firm의 다른 도면을 허용하느냐만 바꿈. 학습량은 매칭 |

어느 수준이 특정 B 또는 C에서 무의미해져도 숨기지 않는다. 예를 들어 T-SYN의 원 라벨은 0/1이므로 E=off일 때 D의 hard와 confidence-weighted가 동일하게 작동할 수 있다. 이것은 구현 버그가 아니라 예상되는 `C×D` 또는 `D×E` 구조다. 반대로 deterministic 수준에서 E=on을 구현하지 못하면 E는 전 설계에서 설정 가능한 요인이 아니므로 전체 6요인 분석을 중지한다.

### 2.3 공통 feature contract

알려진 HGB의 6특징 계약을 P1의 공통 최소 표현으로 사용한다.

\[
\phi(d,h)=[parallel,\ thickness,\ junction,\ \log(length),\ \sin(2\theta),\ \cos(2\theta)]
\]

- `graph-IR`: SEG-IR 또는 staged DXF의 world-coordinate handle graph에서 직접 계산한다. INSERT/world transform은 전개한 좌표를 사용하고, 단위·축척 값과 source/firm 이름은 feature에서 제거한다.
- `raster`: 같은 도면을 동결된 renderer로 렌더하고, handle의 투영 궤적을 query anchor로만 사용한다. 주위 oriented strip, skeleton/edge response, 평행 stroke 간격, 교차 픽셀 구조에서 위 6개 동형 feature를 계산한다. handle-ID buffer와 vector truth는 feature extractor의 입력이 아니라 정렬·평가에만 쓴다.
- 이름, 파일경로, layer 문자열, source firm ID는 양쪽 표현 모두에서 금지한다. firm ID는 splitter만 읽는다.
- raster가 graph와 다른 후보 생성기를 쓰는 end-to-end 비교는 CL-G 후속이며 P1-v1 A 효과에 포함하지 않는다. 따라서 A의 정확한 뜻은 “동일 handle 후보에 대한 graph-context 증거 대 raster-conditioned 증거”다.

### 2.4 모델 수준

#### B = deterministic

기존 `fast_score`의 고정 함수형을 adapter로 감싼다. 기본 형태는 다음이다.

\[
s_\theta(h)=w_p s_p(h)+w_t s_t(h)+w_j s_j(h)+w_l s_l(h)
\]

이름 누수 방지를 위해 primary screen에서는 `s_l=0`, `w_l=0`으로 고정하고 나머지 weight를 합 1로 정규화한다. 기존 v1의 `parallel 0.35 / thickness 0.25 / junction 0.20 / layer 0.20`, 두께 `50–400mm`, 각도 `2°`, overlap `0.5`, snap `6mm`는 동결된 **참조점**이다. B4 scale 팔이 `0.7624`로 FAIL했고 CubiCasa의 도면별 축척이 미상이므로, P1의 tuning bank에서는 절대 mm threshold를 primary 선택 규칙으로 쓰지 않고 도면 내부 무라벨 scale anchor 또는 quantile로 정규화한 후보를 함께 둔다.

도면별 무라벨 scale anchor는 후보 segment endpoint마다 가장 가까운 다른 endpoint까지의 양의 거리 중 중앙값 \(s_d\)로 정의한다. 규칙 후보 bank `Θ_rule`은 다음 Cartesian product와 두 reference 후보의 합집합으로 완전 정의한다.

- \((w_p,w_t,w_j)\): `{(0.4375,0.3125,0.25),(1/3,1/3,1/3),(0.5,0.3,0.2),(0.3,0.5,0.2),(0.3,0.2,0.5),(0.4,0.3,0.3)}`
- angle tolerance: `{1°,2°,4°}`
- overlap minimum: `{0.50,0.75}`
- snap distance: `{0.50,1.00} × s_d`
- relative thickness band: `{[0.5,4],[1,8]} × s_d`
- decision threshold \(\tau\): `{0.30,0.50,0.70}`
- reference 후보: 기존 v1 설정 1개와 layer weight를 0으로 두고 나머지를 합 1로 재정규화한 v1 설정 1개

모든 수는 설계용 제안값이며 측정값이 아니다. Cartesian product는 432개이고 reference 2개를 더해 총 434개 후보가 된다. 후보 순서는 위 tuple의 기재 순서에 따른 사전식 순서이고 validation objective가 동률이면 먼저 나온 후보를 택한다. 모든 셀에서 동일한 bank와 tie-break를 사용한다. `Θ_rule`을 이 정의로 생성한 파일과 hash가 없으면 run을 시작하지 않는다. C는 어떤 labeled validation manifest로 \(\theta\)를 고를지를 바꾸고, D는 validation objective의 sample weight를 바꾼다.

#### B = learned

learned exemplar는 패킷에서 실재가 확인된 `cubicasa_ml`의 HistGradientBoosting 6특징 구현으로 고정한다. 그 구현의 정확한 hyperparameter, library version, feature ordering, missing-value 처리, class weight, early-stopping 규칙을 기존 run artifact에서 회수해 하나의 singleton `Φ_HGB`로 해시한다. 회수가 안 되면 임의의 HGB를 발명하지 않고 P1을 `BLOCKED_CONFIG_PROVENANCE`로 둔다.

P1 안에서는 HGB hyperparameter search를 하지 않는다. C, D, E, F가 이미 데이터·학습 절차를 흔들므로, 각 셀이 다른 hyperparameter search freedom까지 갖게 하면 B 효과가 tuning budget 효과와 섞인다. HGB의 알려진 `val P 0.860 / R 0.370 / F1 0.517 / AUC 0.9215`는 이 exemplar를 택할 근거이지만, P1 응답이나 새 셀의 결과로 재사용하지 않는다. 알려진 logistic `F1 0.053`은 선형 모델이 충분치 않았다는 prior일 뿐 별도 셀을 추가하지 않는다.

#### D = hard 대 confidence-weighted

각 training label confidence \(q_i\)에 대해 다음처럼 구현한다.

- hard: \(y_i=1[q_i\ge0.5],\;w_i=1\)
- confidence-weighted: \(y_i=1[q_i\ge0.5],\;w_i=|2q_i-1|\)

HGB에는 `sample_weight=w_i`를 전달한다. deterministic 후보 선택에는 weighted confusion counts로 만든 weighted F1을 사용한다. T-SYN exact label이면 \(q_i\in\{0,1\}\)이므로 두 방식이 같아진다. silver confidence는 5개 판정자를 5개의 독립표로 세지 않는다. 다이제스트의 두 어휘 가문 `fable+sol`과 `opus+sonnet+grok` 안에서 먼저 평균한 뒤 두 가문을 같은 비중으로 평균해 \(q_i\)를 만든다. 이 family-balanced q 생성 규칙을 matrix 실행 전에 동결한다.

#### E = self-training off 대 on

on은 정확히 한 라운드다.

1. 원 labeled set \(L_C\)로 \(f_0\)를 fit 또는 tune한다.
2. 모든 셀에 공통인 unlabeled pool \(U\)에 \(f_0\)를 적용한다.
3. hard에서는 `p≤0.1` 또는 `p≥0.9`인 표본만 pseudo-label로 채택하고 weight 1을 준다.
4. confidence-weighted에서는 U의 모든 표본에 이진 pseudo-label `1[p≥0.5]`를 주되 weight를 `|2p-1|`로 둔다. `p=0.5`인 표본은 weight 0이므로 학습에 기여하지 않는다.
5. pseudo-label 총 weight가 원 labeled weight의 0.5배를 넘지 않도록 전체를 같은 비율로 축소한다.
6. 같은 모델 family와 같은 hyperparameter로 한 번만 refit하여 \(f_1\)을 얻는다.

0.1, 0.9, 0.5는 모두 실행 전 봉인할 **제안값**이지 측정 결과가 아니다. 이 값을 바꾸려면 matrix 결과를 보기 전에 prereg version을 올려야 한다. deterministic on 셀은 채널 합으로 `[0,1]`에 놓인 \(f_0\) score \(s\)와 선택 threshold \(\tau\)로 `p=σ((s-τ)/0.1)`을 계산한 뒤 같은 절차로 `Θ_rule`을 다시 선택한다. 여기의 0.1도 calibration temperature 제안값이다. 이 단계가 구현되지 않으면 deterministic-on 4셀이 가짜 수준이 되므로 전체 design을 실행하지 않는다.

#### F = leakage granularity

두 F 수준의 evaluation 도면은 완전히 같다.

- L-DWG: evaluation drawing 자체와 handle은 train에서 제외하지만, evaluation firm의 다른 도면은 train에 있을 수 있다.
- L-FIRM: evaluation firm의 모든 도면을 train, tuning, pseudo-label pool에서 제외한다.

두 수준의 labeled handle 수, positive 비율, source stratum을 작은 쪽에 맞춰 deterministic하게 subsample한다. 그래야 F가 “더 적은 학습량”이 아니라 “firm 공유 여부”를 뜻한다. synthetic source에는 명시적인 style/firm profile ID가 필요하다. 그런 ID가 없거나 실제 관례 변이를 흉내 내지 못하면 `C=T-SYN, F=L-FIRM`은 설정 불능이며 전체 P1은 중지한다.

### 2.5 16-run 직교표

표준순서는 A가 가장 느리게, D가 가장 빠르게 부호를 바꾸며 E와 F는 생성자로 계산한다. 실제 실행 순서는 별도의 randomization list로 바꾸되 `design_row`는 보존한다.

| design row | A | B | C | D | E=`ABC` | F=`BCD` |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | -1 | -1 | -1 | -1 | -1 | -1 |
| 2 | -1 | -1 | -1 | +1 | -1 | +1 |
| 3 | -1 | -1 | +1 | -1 | +1 | +1 |
| 4 | -1 | -1 | +1 | +1 | +1 | -1 |
| 5 | -1 | +1 | -1 | -1 | +1 | +1 |
| 6 | -1 | +1 | -1 | +1 | +1 | -1 |
| 7 | -1 | +1 | +1 | -1 | -1 | -1 |
| 8 | -1 | +1 | +1 | +1 | -1 | +1 |
| 9 | +1 | -1 | -1 | -1 | +1 | -1 |
| 10 | +1 | -1 | -1 | +1 | +1 | +1 |
| 11 | +1 | -1 | +1 | -1 | -1 | +1 |
| 12 | +1 | -1 | +1 | +1 | -1 | -1 |
| 13 | +1 | +1 | -1 | -1 | -1 | +1 |
| 14 | +1 | +1 | -1 | +1 | -1 | -1 |
| 15 | +1 | +1 | +1 | -1 | +1 | -1 |
| 16 | +1 | +1 | +1 | +1 | +1 | +1 |

직교성 검산은 `X'X=16I`, 각 비절편 열의 합 0, `E==A*B*C`, `F==B*C*D`를 확인한다. 한 행이라도 실패하면 실행하지 않는다.

### 2.6 두 평가 panel과 응답 정의

각 셀은 학습 source C와 무관하게 두 개의 고정 evaluation panel을 모두 평가한다.

- `P_SYN`: fidelity gate를 통과한 합성 도면 40장. generator style/firm 층과 density 층으로 균형화한다.
- `P_SILVER`: 학습에 쓰지 않은 실제 도면 40장. source-firm 층과 density 층으로 균형화한다.

40은 원 제안의 설계값이다. 두 panel은 모든 16셀에 crossed로 적용한다. C가 T-SILVER인 셀도 `P_SILVER`의 handle 또는 같은 firm을 tuning에서 보지 못하도록 F별 manifest를 따로 만든다.

도면 \(d\)에서 T-SYN hard truth가 하나 이상 양성일 때

\[
F1_d=\frac{2TP_d}{2TP_d+FP_d+FN_d}
\]

를 계산한다. T-SILVER에서는 family-balanced confidence \(q_{dh}\)를 threshold하지 않고 다음 expected confusion counts를 고정 사용한다.

\[
TP_d=\sum_h \hat y_{dh}q_{dh},\quad
FP_d=\sum_h \hat y_{dh}(1-q_{dh}),\quad
FN_d=\sum_h (1-\hat y_{dh})q_{dh}
\]

이 세 값을 같은 F1 식에 넣은 값을 silver의 도면 응답으로 쓴다. 큰 도면 하나가 전체를 지배하지 않도록 primary response는 source-firm×density stratum에 같은 비중을 준 macro-F1이다.

\[
R_t=\sum_s \omega_s\frac{1}{|D^+_{t,s}|}\sum_{d\in D^+_{t,s}}F1_d,\qquad \sum_s\omega_s=1
\]

`R-SYN=R_SYN`, `R-SILVER=R_SILVER`로 둔다. R-SYN은 exact hard truth F1, R-SILVER는 위의 family-balanced expected-count F1이 유일한 primary 정의다. silver를 0.5에서 threshold한 hard F1은 보조열로만 병기한다. D 수준에 따라 evaluation metric을 바꾸는 것은 금지한다.

truth-positive가 0인 도면은 primary macro-F1에서 빼되 숨기지 않고 별도 zero-wall sentinel로 평가한다.

\[
S0_t=1-\frac{\sum_{d\in D^0_t}FP_d}{\sum_{d\in D^0_t}|H_d|}
\]

제안 guardrail은 `S0_t≥0.99`, positive-truth 도면의 macro recall은 `≥0.30`이다. 두 숫자는 새 측정값이 아니라 zero-detector와 all-wall-detector를 막기 위한 prereg 제안값이다. 하나라도 실패하면 높은 F1이 있어도 셀은 합격하지 않는다. pooled per-handle P/R/F1, 도면별 분포, firm별 분포도 증거 xlsx에 보조로 남긴다.

응답 band는 패킷 값을 그대로 봉인한다.

| 응답 | PASS | INCONCLUSIVE | FAIL |
|---|---:|---:|---:|
| R-SYN | `≥0.90` | `0.75–<0.90` | `<0.75` |
| R-SILVER | `≥0.50` | `0.30–<0.50` | `<0.30` |

경계값은 위 표처럼 위쪽 band에 포함한다. R-SYN이 primary effect-screen response이고 R-SILVER는 교차확인 response다. 두 response에서 각각 p-value를 골라 주장하지 않는다. primary 활성 판정은 R-SYN에만 적용하고, R-SILVER에서는 effect sign, band, hold-out consistency를 보고한다.

### 2.7 effect 추정과 판정

부호화 열 \(x_{rj}\in\{-1,+1\}\), 셀 평균 응답 \(Y_r\)에 대해 효과는

\[
\hat e_j=\bar Y_{j+}-\bar Y_{j-}=\frac{1}{8}\sum_{r=1}^{16}x_{rj}Y_r
\]

로 계산한다. 회귀계수는 \(\hat\beta_j=\hat e_j/2\)다. G1–G7 열도 같은 식으로 계산하지만 이름은 단일 interaction이 아니라 alias chain으로 출력한다.

판정 순서는 다음과 같다.

1. manifest, mapping, leakage, sentinel, shuffle control, resource log의 validity를 먼저 판정한다.
2. 유효한 16개 셀의 R-SYN으로 15개 직교 effect를 계산한다.
3. Lenth PSE와 ME를 계산한다.
4. `|effect|>ME`면 `screen-active`, 아니면 `small/null-at-screen-resolution`로 보고한다.
5. R-SILVER에서 같은 대비의 부호와 band 이동을 교차확인한다. 부호가 반대면 `Goodhart/proxy-disagreement`로 표시한다.
6. crossed drawing 구조를 이용한 firm-stratified bootstrap 또는 drawing-block sensitivity를 보조로 계산한다. 이 보조분석은 prereg의 Lenth 판정을 바꾸지 않는다.
7. H1/H2가 크거나 PSE가 안정적으로 계산되지 않으면 모든 active 해석을 `INCONCLUSIVE_HIGH_ORDER`로 낮춘다.

null/small 효과는 삭제하지 않는다. 특히 E가 small이면 “이 조건과 이 한 라운드 self-training은 값이 없다”, F가 크면 “도면 split 성적은 firm 관례 공유에 민감하다”가 1급 결과다.

### 2.8 shuffle, 누수, seed, 캐시 규약

- `IR freeze`: graph IR, raster render, handle-ID buffer, feature cache의 content hash를 cell 실행 전에 봉인한다.
- `split freeze`: 각 C×F 조합의 train/tune/eval/unlabeled manifest와 firm hash를 봉인한다.
- `name blind`: filename, path, firm, layer 문자열을 feature cache에서 검색하고 발견 시 kill한다.
- `shuffle control`: 각 learned source/representation에서 label permutation 모델을 동일한 feature와 split로 실행한다. one-sided permutation 기준에서 chance보다 유의하게 높으면 누수 의심으로 learned 관련 셀을 무효화한다. 다이제스트의 기존 shuffle AUC `0.375 PASS`는 좋은 선례지만 새 screen의 control을 대체하지 않는다.
- `deterministic`: config, data hash가 같으면 한 번만 실행한다. 동일 셀 내부 seed 반복을 pure error처럼 세지 않는다.
- `learned`: 공통 seed block 제안값 `[2026071801, 2026071802, 2026071803]`을 모든 learned 셀에 동일 적용하고 셀 응답은 세 seed 평균으로 만든다. seed별 결과를 숨기지 않는다. 한 seed만 가능하면 B 또는 E가 포함된 active claim을 금지하고 pilot로 강등한다.
- `execution order`: learned 8셀×seed block 순서를 무작위화한다. deterministic 8셀은 수학적으로 순서 무관하지만 실제 order, cache hit, wall time, peak RSS를 기록한다.
- `LLM silver`: 5판정자의 원 출력, prompt, model ID, family grouping을 미리 materialize한다. matrix 도중 다시 호출하지 않는다. 그래야 응답의 run-order nondeterminism이 줄고 두 어휘 가문을 5독립 반복처럼 세지 않게 된다.

### 2.9 winner 선택과 confirmation 규칙

winner를 결과를 본 뒤 임의로 고르지 않기 위해 다음을 prereg한다.

1. validity 또는 sentinel이 실패한 셀은 제외한다.
2. R-SYN 또는 R-SILVER가 FAIL이면 confirmation 후보에서 제외한다.
3. 나머지 셀에 대해 band-normalized margin을 계산한다.

\[
g_{syn}=\frac{R_{SYN}-0.75}{0.90-0.75},\qquad
g_{silver}=\frac{R_{SILVER}-0.30}{0.50-0.30},\qquad
G=\min(g_{syn},g_{silver})
\]

4. `G`가 가장 큰 셀을 선택한다. 정확 동률이면 `L-FIRM > L-DWG`, `self-training off > on`, `deterministic > learned`, `graph-IR > raster` 순으로 더 보수적이고 단순한 셀을 택한다.
5. 미사용 firm hold-out에 선택 셀과 **동결된 참조 deterministic 셀**만 한 번 적용한다. screen보다 hold-out이 내려가고 선택 셀의 상대 이득 부호까지 뒤집히면 Goodhart failure다.
6. 두 band와 sentinel을 hold-out에서 다시 만족해야 confirmation `PASS`다. 지금은 미실행이므로 `PASS_WITH_DEFERRAL`을 유지한다.
7. CubiCasa test 400장은 이 선택·동결이 끝난 뒤 외부 사람 라벨 transfer audit로 방법당 단 한 번만 사용할 수 있다. firm metadata가 없으면 packet의 unused-firm confirmation을 대신하지 못한다.

---

## 3. 벽 과업 적응 설계

### 3.1 현재 실측이 주는 출발점

기하 탐지기 v1은 CubiCasa val에서 `F1 0.2358`, `P 0.134`, `R 0.981`이었다. 최소길이 필터의 천장도 `F1 0.335`였고, 긴 평행 구조인 Direction, BoundaryPolygon, Door, Window, DimensionMark가 false positive의 본질적 교란이었다. 반면 6특징 HGB는 같은 val 축에서 `P 0.860`, `R 0.370`, `F1 0.517`, `AUC 0.9215`를 냈다. 이것은 학습이 단순 기하 prior보다 가능성이 있음을 보이지만, 다음을 아직 말하지 못한다.

- HGB 이득이 graph representation 때문인지, truth source 때문인지
- 같은 firm 관례를 공유해서 생긴 이득인지
- silver confidence 처리나 self-training이 이득을 증폭 또는 훼손하는지
- raster-conditioned evidence에서도 같은 learned advantage가 남는지

P1은 바로 이 조건부 차이를 측정한다. 기존 `0.2358`과 `0.517`을 새 effect의 두 셀처럼 끼워 넣지 않고, 새 16셀을 같은 prereg·population·metric에서 다시 생성해야 한다.

### 3.2 CubiCasa SEG-IR 벡터축

CubiCasa5k의 5,000도면은 SEG-IR 변환 실패 0이고, 현재 split은 train 4,200 / val 400 / test 400, wall segment 비율 약 11.8%다. P1에서의 역할은 다음처럼 제한한다.

1. `cubicasa_ir`를 통해 동일 handle universe와 graph feature를 생성한다.
2. 같은 SEG-IR을 raster로 렌더하여 A의 paired representation adapter와 handle-ID round-trip을 검증한다.
3. train/val은 코드 배관, frozen HGB provenance 복원, representation parity 사전 점검에 사용할 수 있다.
4. CubiCasa human label을 P1의 C 수준에 몰래 섞지 않는다. C는 T-SYN 대 T-SILVER다.
5. test 400은 winner 결정 후 한 번만 연다. screen의 16셀을 test에서 비교하지 않는다.

좌표가 px이고 도면별 축척이 미상이며 벽두께 p50이 22px라는 실측 때문에, graph와 raster 양쪽의 thickness feature는 물리 mm 고정 대역 대신 도면 내부 scale-normalized 값으로 공통화한다. v1의 `50–400mm` prior를 그대로 CubiCasa에 투영하지 않는다.

### 3.3 FloorPlanCAD 래스터축

FloorPlanCAD는 5,308장과 wall bbox/segmask를 갖지만 벡터 SVG가 없다. 따라서 다음 역할만 허용한다.

- raster adapter의 외부 domain smoke test
- counsel 승인 후 raster-only pretraining 또는 후속 CL-G
- 선택 모델의 픽셀 segmentation 품질 보조 평가

P1-v1 A main effect에는 넣지 않는다. FloorPlanCAD raster 셀과 CubiCasa graph 셀을 비교하면 A가 representation뿐 아니라 국가·도면관례·annotation ontology·candidate universe·scale을 모두 품는다. 또한 패널 PR-3의 NC/원도면 권리 확인 전에는 학습에 쓰지 않는다.

### 3.4 `1.dwg` staged DXF 실도면축

`1.dwg` staged DXF에는 도면정의 384개가 있고 최대 정의는 412,775 선분까지 가서 실제 연산 병목을 보여 준다. 이 축은 다음에 유용하다.

- graph-IR과 실제 render의 paired 생성
- silver family-balanced q 부착
- name-blind, layer-neutral 실도면 stress
- density stratum의 상단과 out-of-memory/후보폭발 guardrail 검증

그러나 파일 하나 또는 firm provenance가 없는 정의 모음만으로는 L-FIRM을 설정할 수 없다. packet이 요구한 40장 source-firm×density panel을 만들 수 있는 canonical manifest와 미사용 firm이 실제로 존재함을 먼저 증명해야 한다. `1.dwg`의 정의들을 임의로 “40개 독립 도면” 또는 “여러 firm”으로 가정하지 않는다.

실도면 탐지기와 silver의 Pearson이 `0.2911`이고 full-vs-name-blind가 `1.0`이었다는 실측은 두 축이 동일하지 않음을 시사하지만 독립성 증명은 아니다. 특히 5판정자가 약 2가문이라는 사실 때문에 단순 다수결 confidence를 쓰지 않는다.

### 3.5 합성축

현재 합성팩은 LINE/LWPOLYLINE/INSERT 세 종류뿐인데 실도면에는 SPLINE 3,973, ARC 2,198, HATCH 264가 혼재하며 B1 fidelity가 FAIL이다. S팩은 채점 우주에 음성이 0이라 precision이 공허하고, scale 불변성도 `0.7624`로 FAIL했다. 그러므로 다음을 만족한 version-bumped generator만 `P_SYN` 자격을 갖는다.

- negative handle을 반드시 포함
- SPLINE/ARC/HATCH/블록/비평행 조각을 포함한 divergent 현상을 생성
- rigid/unit/explode/layer rename와 zero-wall/all-wall sentinel을 별도 hidden mutation family로 보유
- synthetic style/firm profile ID를 생성하되 ID 자체는 feature에 노출하지 않음
- fidelity gate를 P1 결과보다 먼저 봉인·판정

현재 S/F/M pack으로는 코드가 16행을 돌 수 있는지 확인하는 dry run만 가능하다. 그 결과를 main effect evidence로 승격하지 않는다.

### 3.6 동일 시험지의 보장

표현, 모델, 정답원 효과를 읽으려면 아래가 셀마다 같아야 한다.

- evaluation handle universe와 label version
- labeled handle budget과 class-ratio 처리
- train/val/eval manifest 생성 알고리즘
- feature schema의 의미와 순서
- tuning 기회 수
- threshold 선택 규칙
- self-training unlabeled pool과 weight cap
- metric, zero-wall sentinel, evidence schema

달라도 되는 것은 A–F로 명시한 처치뿐이다. 예를 들어 learned raster 셀에만 FloorPlanCAD를 pretrain하거나 graph 셀에만 CubiCasa human label을 보태는 순간 직교표는 숫자상 직교여도 처치는 직교가 아니다.

### 3.7 P1이 추가로 가져올 수 있는 것

P1의 가치는 새 최고 F1 하나가 아니라 다음 판정들이다.

- B main이 크고 G1/G4/G6가 작으면, 이 HGB exemplar의 우위가 representation/truth/leakage에 비교적 강건하다는 후속 근거가 된다.
- G1이 활성이고 표적 증강에서 AB가 남으면 learned advantage가 raster 또는 graph 조건에 의존한다.
- G4가 활성이고 표적 증강에서 BC가 남으면 learned advantage가 truth source에 의존한다. “학습이 낫다”라는 단독 결론을 폐기해야 한다.
- G6가 활성이고 CF가 남으면 truth-source 성능이 firm leakage에 민감하다. 이는 convention memorization의 서명이다.
- F가 크면 L-DWG 점수를 일반화 성능으로 부르면 안 된다.
- E가 작으면 P4류 자기학습 투자를 중지할 근거가 된다.
- 전 셀이 R-SYN 천장에 붙으면 generator가 판별력이 없는 것이고, 전 셀이 R-SYN FAIL이면 표현/정답원 토대가 실패한 것이다.

---

## 4. 데이터·컴퓨트 요구

### 4.1 실행 전 필수 데이터 계약

| 자산 | 필수 필드·검증 | 현재 판정 |
|---|---|---|
| T-SYN labeled train/tune/eval | handle ID, exact wall label, generator version, style/firm profile, density stratum, hidden mutation family | generator는 있으나 fidelity FAIL; full screen blocker |
| T-SILVER labeled train/tune/eval | handle ID, 5 raw judge outputs, 2 family grouping, family-balanced confidence, source firm, density, prompt/model provenance | 독립성 감사와 family balancing 필요 |
| paired graph/raster | drawing hash, world→pixel transform, render config, handle-ID buffer, round-trip report | 구현 및 exactness gate 필요 |
| unlabeled pool U | C·F evaluation과 분리, A 양쪽에서 paired 사용 가능, firm exclusion 준수 | manifest 필요 |
| CubiCasa | 기존 train/val/test split hash, SEG-IR hash, test access log | 변환 성공 0 failure; test 무접촉 유지 |
| legal manifest | FloorPlanCAD/CubiCasa 학습·파생물 사용 허용 범위 | counsel 서면 전 blocker |

`N_label`은 두 truth source 중 작은 유효 pool에 맞춘 동일 budget으로 정하고 prereg에 기록한다. class balance를 억지로 같게 만드는 경우 원분포 metric과 balanced-training metric을 분리한다. split마다 firm overlap 0/허용, exact drawing overlap 0을 자동 검증한다.

### 4.2 로컬 실행 계획 — RAM 64GB, RTX 5070 Ti 16GB

로컬이 P1-v1의 기준 실행 환경이다. DGX가 없어도 끝나야 한다.

1. **전처리 단일화**: graph IR, paired raster, handle buffer, 6-slot features를 한 번 생성하고 content-addressed read-only cache로 동결한다.
2. **결정론 8셀 먼저**: `Θ_rule` 평가와 두 panel scoring은 CPU에서 실행한다. 패킷의 목표대로 캐시가 준비된 뒤 8셀 전체를 반나절 probe 예산으로 둔다. 이 시간은 제안 예산이지 실측 runtime이 아니다.
3. **HGB 8셀**: feature array는 float32/compact categorical-free 형식으로 memory-map하고, 셀을 순차 실행해 복제본을 줄인다. peak RSS를 계속 기록하며 OS와 renderer 여유를 남긴 hard cap을 prereg한다.
4. **RTX 사용**: raster strip/edge feature batch 생성 또는 후속 neural adapter smoke에만 쓴다. HGB 자체 때문에 GPU 의존성을 만들지 않는다.
5. **대형 도면 방어**: 최대 정의 412,775 선분이라는 실측을 기준으로 candidate explosion, temporary array multiplier, per-drawing timeout을 사전 점검한다. 실패 도면을 조용히 제외하지 말고 `invalid_resource`로 기록한다.
6. **병렬성 제한**: 여러 HGB 셀을 동시에 띄워 64GB를 소진하지 않는다. learned 셀은 seed block을 순차 또는 메모리 검증된 한도 안에서만 병렬화한다.

제안 자원 cap은 deterministic cell `<16GB RSS`, raster feature cell `<32GB RSS`, learned HGB cell `<56GB RSS`, GPU 작업 `<14GB VRAM`이다. 모두 계획값이며 첫 preflight에서 결과를 보기 전에 더 낮게 조정할 수 있다. cap 초과는 결과 누락이 아니라 해당 셀의 kill 사유다.

### 4.3 DGX 계획 — 현재 unreachable

DGX Spark와 Ornith-35B는 현재 unreachable이므로 16셀 P1-v1의 critical path에서 제거한다. 다음 경우에만 별도 prereg로 사용한다.

- B가 screen-active이고 learned family를 `{GNN,VLM}`으로 분해하는 Phase 3/후속
- 로컬 HGB가 아니라 대형 GNN 또는 VLM의 학습이 필요한 경우
- vLLM serving과 training의 자원 충돌을 피한 야간 batch window가 확보된 경우

DGX 재접속 전에는 vision 지원, CUDA/runtime, model license, data transfer 권한을 먼저 확인한다. DGX 실패 때문에 local screen을 대기시키거나, 서로 다른 host에서 나온 결과를 같은 seed block의 반복처럼 합치지 않는다.

### 4.4 데이터·실행 예산

| 단계 | 제안 예산 | 종료 산출 |
|---|---|---|
| Phase 0 prereg/preflight | 로컬 엔지니어링 3–5일 | frozen config, manifests, mapping exactness, legal/gate status |
| Phase 1 deterministic 8셀 | 캐시 후 반나절 목표 | A/C/F 조기 신호, validity report |
| Phase 2 learned 8셀×3 seed | 로컬 2–4일 목표 | 16 cell means, seed dispersion, shuffle controls |
| effects/evidence | 로컬 1일 | Lenth table, alias-chain table, xlsx, machine-readable report |
| targeted augmentation | 활성 사슬당 새 budget | rank-verified extra rows, 새 prereg |
| confirmation | 미사용 firm hold-out 1회 | frozen winner와 baseline의 paired report |

일수와 seed 수는 실행 예산 제안이며 측정 runtime이 아니다. Phase 0의 blocker가 남으면 계산 budget을 소모하지 않는다.

---

## 5. 구현 계획

### 5.1 제안 모듈·파일 골격

아래는 구현할 논리 골격이다. 이 도시에 계약상 실제로 생성한 파일은 본 markdown 하나뿐이며, 아래 파일들은 후속 구현 제안이다. 기존 도구의 실제 경로는 패킷에 없으므로 임의 경로를 사실처럼 쓰지 않고 import/adapter 이름으로만 지정한다.

```text
e2_p1/
  configs/
    p1_prereg.yaml
    rule_candidate_bank.yaml
    hgb_frozen_provenance.json
  design/
    generate_fraction.py
    validate_aliases.py
    select_augmentation.py
  manifests/
    build_group_splits.py
    validate_no_overlap.py
  representations/
    graph_ir_adapter.py
    paired_renderer.py
    handle_id_buffer.py
    raster_feature_adapter.py
  models/
    deterministic_adapter.py
    hgb_adapter.py
    confidence_labels.py
    self_training.py
  evaluation/
    per_handle_metrics.py
    zero_wall_sentinel.py
    lenth_pse.py
    effects.py
    confirmation.py
  runners/
    run_cell.py
    run_screen.py
  evidence/
    evidence_grid_adapter.py
    build_xlsx.py
    validate_run_contract.py
  tests/
    test_design_matrix.py
    test_alias_chains.py
    test_roundtrip_exactness.py
    test_split_leakage.py
    test_metric_edges.py
    test_determinism.py
```

### 5.2 기존 도구 접속점

- `evidence_grid`: 각 cell의 config hash, split hash, seed, prediction artifact, response, validity, resource log를 행 단위로 넣고 최종 xlsx를 생성한다. 실패도 삭제하지 않는다.
- `fast_score`: deterministic adapter가 기존 NumPy 동치 고속 scorer를 호출한다. layer channel mask와 relative-scale candidate bank가 명시적으로 인자로 들어가야 한다.
- `cubicasa_ir`: SEG-IR handle graph, transform, truth handle을 가져오되 기존 train/val/test split을 보존한다.
- `cubicasa_ml`: 알려진 HGB configuration과 feature ordering을 회수하고 frozen exemplar를 fit한다. 회수 실패 시 새 설정으로 몰래 대체하지 않는다.

접속 adapter는 upstream object를 복사해 재해석하지 않고 schema version과 hash를 보존한다. `fast_score`와 새 graph feature가 동일한 입력에서 같은 값을 내는 golden test를 둔다.

### 5.3 구현 단계

#### 단계 A — prereg compiler

`p1_prereg.yaml`에서 factor coding, 16행 matrix, response band, seed, split policy, candidate bank, kill rules를 읽어 immutable run manifest를 만든다. compiler는 다음을 거부한다.

- 16행이 아니거나 중복 treatment가 있음
- E/F 생성자 불일치
- A–F 열 비직교
- evaluation drawing이 cell마다 다름
- L-FIRM에 firm overlap이 있음
- learned config provenance 또는 rule bank hash가 없음
- T-SYN fidelity 또는 legal gate가 미해결인데 `mode=confirmatory`임

#### 단계 B — paired representation

graph IR에서 deterministic render를 만들고, 각 handle에 unique integer ID를 칠한 별도 provenance buffer를 만든다. 회전·이동·반사·unit scaling에 대해 handle identity가 유지되는지 synthetic exact test를 수행한다. mask overlap만 맞고 handle ID가 바뀌는 경우도 실패다.

#### 단계 C — label materialization

T-SYN exact labels와 T-SILVER의 raw 5-judge outputs를 immutable table로 만든다. silver는 두 family 내 평균 후 family 간 평균을 만든다. label q, hard y, confidence weight를 모두 저장해 D 처리가 재현 가능하게 한다.

#### 단계 D — cell runner

```text
for design_row r in randomized_schedule:
    cfg = decode(A..F)
    assert_all_gates(cfg)
    X_train, q_train = load_labeled_source(C, F, A)
    X_eval_syn, X_eval_silver = load_frozen_panels(A)
    y_train, w_train = encode_labels(q_train, D)

    if B == deterministic:
        model0 = deterministic_select(Theta_rule, X_train, y_train, w_train)
    else:
        model0 = fit_frozen_hgb(Phi_HGB, X_train, y_train, w_train, seed)

    if E == on:
        q_pseudo = model0.predict_proba(load_unlabeled(U, F, A))
        L_aug = build_one_round_pseudo_labels(q_pseudo, D, weight_cap=0.5)
        model = refit_same_family(model0, L_train + L_aug)
    else:
        model = model0

    for panel in [P_SYN, P_SILVER]:
        pred = predict_per_handle(model, panel)
        score_fixed_metrics(pred, panel.labels)
    write_atomic_evidence_row()
```

`write_atomic_evidence_row`는 결과 파일을 성공 상태로 먼저 만들지 않는다. predictions, metrics, resource log, hashes가 모두 존재하고 validator가 통과한 뒤에만 `valid=true`를 쓴다.

#### 단계 E — analysis

16개 valid cell mean이 모두 모였을 때만 effect table을 만든다. 누락 셀을 평균 대치하거나 orthogonality를 유지한다고 가정하지 않는다. 한 셀 실패 시 retry는 같은 config/hash로만 허용하고, 설정을 바꾸면 prereg version bump다.

### 5.4 테스트 계획

- design matrix와 alias chain의 symbolic golden test
- graph↔raster handle round-trip exact match
- empty-truth, all-positive, no-prediction, all-prediction metric edge case
- silver family-balanced q가 5독립 다수결로 퇴행하지 않는 test
- hard/weighted label의 q=0, 0.5, 1 boundary test
- deterministic rerun bitwise 또는 tolerance-equivalence test
- L-DWG exact drawing overlap 0, L-FIRM group overlap 0 test
- source/firm/layer string feature ban test
- seed block completeness 및 cell order log test
- 16개 응답을 넣은 Lenth implementation의 외부 검산 fixture
- evidence xlsx의 required columns와 실패행 보존 test

### 5.5 예상 개발 규모와 산출 artifact

제안 규모는 adapter·검증 중심 6–10 engineering day다. 가장 큰 위험은 모델 코드가 아니라 paired representation과 firm-aware manifest다. 실행 run folder에는 최소한 다음이 있어야 한다.

```text
prereg.yaml + hash
design_matrix.csv
randomization_order.csv
split_manifests/ + hashes
config_provenance/
cell_<01..16>/
  status.json
  predictions.parquet
  metrics.json
  resource.json
  seed_results.json
effects.json
effects.xlsx
confirmation/ (실행 전에는 status=DEFERRED만)
latest_status.json
```

`effects.xlsx`는 패킷의 “증거 xlsx 의무”를 만족해야 하며, main/alias effect뿐 아니라 모든 cell의 raw metric, sentinel, seed, failure reason을 포함한다.

---

## 6. 실험 셀 정의

### 6.1 공통 판정 코드

모든 셀의 primary metric은 `R-SYN`, secondary는 `R-SILVER`다. 합격은 두 response가 각각 PASS이고 `S0≥0.99`, macro recall `≥0.30`이며 validity gate가 모두 통과하는 경우다. 한 response가 INCONCLUSIVE이면 셀도 최대 INCONCLUSIVE다.

Kill code는 다음과 같다.

- `K-SYN`: T-SYN fidelity gate FAIL 또는 negative-handle/sentinel 결손
- `K-SIL`: silver 원출력·2-family balancing·train/eval 분리가 불완전
- `K-GRAPH`: Graph IR adjacency/transform/INSERT world-coordinate 검증 실패
- `K-RASTER`: raster↔handle exactness 또는 동일 후보우주 실패
- `K-FIRM`: group metadata 없음, F 수준 간 학습량 불일치, L-FIRM overlap 발견
- `K-ST`: pseudo-label pool이 evaluation과 겹침, weight cap 위반, 한 라운드 초과
- `K-SEED`: learned seed block 누락 또는 winner/effect sign이 단일 seed에만 의존
- `K-LEAK`: name/path/layer/firm feature 노출 또는 shuffle control 비정상
- `K-RESOURCE`: prereg resource cap 초과·도면 조용한 누락
- `K-GLOBAL-SYN`: 16셀 모두 `R-SYN<0.75`
- `K-GLOBAL-SIL`: 어떤 셀도 `R-SILVER>0.30`이 아님
- `K-CEILING`: 모든 셀이 합성 천장이고 effect가 판별되지 않음 — 실패라기보다 harder-generator version bump 후 재설계

Budget code는 다음과 같다.

- `BD-G`: graph deterministic, 로컬 CPU, seed 반복 없음
- `BD-R`: raster deterministic, frozen raster cache + 로컬 CPU, seed 반복 없음
- `BL-G`: graph HGB, 로컬 CPU/RAM, 공통 3-seed block
- `BL-R`: raster HGB, frozen raster cache + 로컬 CPU/RAM, 공통 3-seed block

결정론 8셀 합계는 cache 후 반나절 목표, learned cell은 셀당 3 fit을 허용한다. 시간은 제안 budget이다.

### 6.2 16개 셀

각 셀 가설은 “이 bundle이 두 band와 guardrail을 만족한다”는 viability 가설이며, 요인 효과 가설은 16셀 전체 대비로만 검정한다. 한 셀을 다른 셀과 임의 pairwise test하지 않는다.

| Run | 정확한 셀 설정 | 셀별 사전 가설 | 지표·제안 합격선 | 주요 kill | 예산·seed |
|---:|---|---|---|---|---|
| 1 | graph · deterministic · T-SYN · hard · ST off · L-DWG | 합성 튜닝을 쓴 가장 단순한 graph-rule 참조 셀이 두 band를 동시에 넘는지 본다. | 공통 dual PASS + guardrail | K-SYN, K-GRAPH, K-FIRM, K-LEAK | BD-G, deterministic hash 1회 |
| 2 | graph · deterministic · T-SYN · weighted · ST off · L-FIRM | exact synthetic label에서 D가 사실상 null이어도 firm 분리 후 viability가 남는지 본다. | 동일 | K-SYN, K-GRAPH, K-FIRM | BD-G, 반복 없음 |
| 3 | graph · deterministic · T-SILVER · hard · ST on · L-FIRM | silver hard label과 1회 pseudo-refit이 strict firm split에서도 규칙 scorer를 개선 가능한지 본다. | 동일 | K-SIL, K-GRAPH, K-FIRM, K-ST | BD-G, 반복 없음 |
| 4 | graph · deterministic · T-SILVER · weighted · ST on · L-DWG | confidence weighting이 shared-firm 환경의 겉보기 이득만 키우는지 포함해 viability를 본다. | 동일 | K-SIL, K-GRAPH, K-ST, K-LEAK | BD-G, 반복 없음 |
| 5 | graph · HGB · T-SYN · hard · ST on · L-FIRM | 합성 학습 HGB가 self-training 후에도 unseen-firm에 전이하는지 본다. | 동일 | K-SYN, K-GRAPH, K-FIRM, K-ST, K-SEED | BL-G, 공통 3 seed |
| 6 | graph · HGB · T-SYN · weighted · ST on · L-DWG | pseudo confidence weighting이 graph HGB의 합성→실도면 교차응답을 올리는지 본다. | 동일 | K-SYN, K-GRAPH, K-ST, K-SEED | BL-G, 공통 3 seed |
| 7 | graph · HGB · T-SILVER · hard · ST off · L-DWG | 알려진 HGB 축에 가까운 shared-firm silver 학습 bundle이 실제 band를 넘는지 본다. | 동일 | K-SIL, K-GRAPH, K-FIRM, K-SEED, K-LEAK | BL-G, 공통 3 seed |
| 8 | graph · HGB · T-SILVER · weighted · ST off · L-FIRM | confidence-weighted silver HGB가 자기학습 없이 firm holdout에 강건한지 본다. | 동일 | K-SIL, K-GRAPH, K-FIRM, K-SEED | BL-G, 공통 3 seed |
| 9 | raster · deterministic · T-SYN · hard · ST on · L-DWG | paired raster 증거만으로 rule scorer와 한 번의 pseudo-refit이 작동하는지 본다. | 동일 | K-SYN, K-RASTER, K-ST, K-FIRM | BD-R, 반복 없음 |
| 10 | raster · deterministic · T-SYN · weighted · ST on · L-FIRM | raster rule bundle이 strict firm split과 pseudo confidence 아래서 유지되는지 본다. | 동일 | K-SYN, K-RASTER, K-FIRM, K-ST | BD-R, 반복 없음 |
| 11 | raster · deterministic · T-SILVER · hard · ST off · L-FIRM | raster evidence와 silver tuning만으로 unseen-firm viability가 있는지 본다. | 동일 | K-SIL, K-RASTER, K-FIRM | BD-R, 반복 없음 |
| 12 | raster · deterministic · T-SILVER · weighted · ST off · L-DWG | confidence-weighted silver가 raster rule의 shared-firm 점수만 올리는지 함께 본다. | 동일 | K-SIL, K-RASTER, K-FIRM, K-LEAK | BD-R, 반복 없음 |
| 13 | raster · HGB · T-SYN · hard · ST off · L-FIRM | 학습 이득이 graph에 한정되지 않고 raster-conditioned feature에서도 strict split에 남는지 본다. | 동일 | K-SYN, K-RASTER, K-FIRM, K-SEED | BL-R, 공통 3 seed |
| 14 | raster · HGB · T-SYN · weighted · ST off · L-DWG | exact T-SYN에서 D의 null 가능성을 포함해 raster HGB의 baseline viability를 본다. | 동일 | K-SYN, K-RASTER, K-FIRM, K-SEED | BL-R, 공통 3 seed |
| 15 | raster · HGB · T-SILVER · hard · ST on · L-DWG | 가장 leakage·confirmation-bias 위험이 큰 bundle이 겉보기로만 좋아지는지 본다. | 동일 | K-SIL, K-RASTER, K-ST, K-SEED, K-LEAK | BL-R, 공통 3 seed |
| 16 | raster · HGB · T-SILVER · weighted · ST on · L-FIRM | 가장 복합적인 bundle이 strict split에서도 dual PASS를 달성하는지 본다. | 동일 | K-SIL, K-RASTER, K-FIRM, K-ST, K-SEED | BL-R, 공통 3 seed |

### 6.3 cheapest probe

먼저 B=deterministic인 run `1,2,3,4,9,10,11,12`만 실행한다. 이 8개는 6요인 fraction 전체가 아니므로 B main 또는 B가 포함된 interaction을 추정하지 않는다. 목적은 다음 세 가지다.

- paired A가 실제로 설정 가능한지
- C와 F 수준이 metric을 움직일 최소 신호가 있는지
- raster mapping, firm split, silver materialization, resource cap이 learned 투자 전에 견디는지

이 probe에서 graph/raster 후보우주가 달라지거나 T-SYN이 fidelity 자격을 못 얻으면 learned 8셀을 열지 않는다. 현재 fidelity FAIL 상태에서의 probe는 engineering dry run으로만 기록한다.

### 6.4 effects table — UNRUN

사전 main-effect 기대 **크기 순위**는 패킷대로 `C > B > A > F > D > E`다. 방향은 데이터 전에 단정하지 않는다. 모든 effect는 high-minus-low다.

| estimand | 의미 | 사전 순위/관심 | R-SYN effect | R-SILVER effect | rank | active | status |
|---|---|---|---|---|---|---|---|
| A | raster − graph | main 3위 | — | — | — | — | UNRUN |
| B | HGB − deterministic | main 2위 | — | — | — | — | UNRUN |
| C | T-SILVER − T-SYN | main 1위 | — | — | — | — | UNRUN |
| D | weighted − hard | main 5위 | — | — | — | — | UNRUN |
| E | ST on − off | main 6위 | — | — | — | — | UNRUN |
| F | L-FIRM − L-DWG | main 4위 | — | — | — | — | UNRUN |
| G1 | `AB = CE` | representation×family 후보이나 truth×ST와 불리 | — | — | — | — | UNRUN |
| G2 | `AC = BE` | representation×truth 대 family×ST | — | — | — | — | UNRUN |
| G3 | `AD = EF` | representation×noise 대 ST×leakage | — | — | — | — | UNRUN |
| G4 | `AE = BC = DF` | family×truth 사전 핵심이나 두 항과 불리 | — | — | — | — | UNRUN |
| G5 | `AF = DE` | representation×leakage 대 noise×ST | — | — | — | — | UNRUN |
| G6 | `BD = CF` | truth×leakage 사전 핵심이나 family×noise와 불리 | — | — | — | — | UNRUN |
| G7 | `BF = CD` | family×leakage 대 truth×noise | — | — | — | — | UNRUN |
| H1 | `ABD=CDE=ACF=BEF` | 고차 진단, 해석 금지 | — | — | — | — | UNRUN |
| H2 | `ACD=BDE=ABF=CEF` | 고차 진단, 해석 금지 | — | — | — | — | UNRUN |

### 6.5 interactions_found — UNRUN

현재 “found”된 interaction은 없다. 사전 후보만 있다.

| 사전 질문 | 실제 16런 estimand | 단독 식별 가능? | status |
|---|---|---|---|
| 계열 우위가 표현에 의존하는가? (`AB`) | G1=`AB=CE` | 아니오 | UNRUN |
| 학습 우위가 정답원에 의존하는가? (`BC`) | G4=`AE=BC=DF` | 아니오 | UNRUN |
| 정답원 효과가 누수 입도에 의존하는가? (`CF`) | G6=`BD=CF` | 아니오 | UNRUN |

활성 G1/G4/G6가 나오면 그것을 각각 AB/BC/CF로 이름 바꾸지 않는다. 먼저 해당 사슬의 후보 열들이 독립 rank를 갖도록 추가 treatment를 고른다. 8-run targeted augmentation은 가능한 선택이지만, 다음 조건을 만족할 때만 쓴다.

- 64개 전체 후보 중 기존 16개를 제외한 후보에서 선택
- 관심 main+2FI model matrix가 full column rank
- condition number와 prediction variance가 prereg 기준 이내
- 기존 main-effect 추정과의 연결이 유지됨
- 새 결과를 보기 전에 추가 행과 분석식을 봉인

이 증강은 선택한 interaction을 분리하는 **비정규 표적 증강**일 수 있다. 단지 8행을 더했다는 이유로 `Resolution V`라고 쓰지 않는다. 모든 2FI를 전역적으로 분리하려면 별도의 더 큰 설계를 새로 최적화하고 version-bump한다.

### 6.6 confirmation run

- 대상: 2.9의 고정 selection rule이 고른 단일 셀
- 비교: frozen graph-deterministic reference 1개
- population: screen과 어떤 firm도 공유하지 않는 hold-out
- 지표: 같은 R band, S0, recall, per-firm 분포
- Goodhart pair: screen 상대효과와 hold-out 상대효과의 부호 비교
- test 사용: val에서 설정을 바꾼 뒤 test를 다시 보지 않음
- 현재 판정: `PASS_WITH_DEFERRAL`, 실행 증거 없음

---

## 7. red team 티켓 응답

패널 보고서가 설명을 제공한 티켓만 아래에서 구체적으로 답한다. `seats/red_teamer.md`의 원문이 패킷 안에 없으므로 설명이 없는 T8–T33의 세부 내용을 발명하지 않는다. 그런 티켓은 canonical ledger를 읽기 전까지 계속 OPEN이다.

| 티켓/게이트 | P1에 걸리는 이유 | 대응 | 잔여 상태 |
|---|---|---|---|
| T1 / PR-2 proxy 독립성 | C와 두 response가 synthetic·silver proxy를 함께 사용한다. 같은 평행 이중선 prior를 공유하면 교차확인이 아니다. | screen 전에 동일 handle의 synthetic/silver/외부 human/metamorphic 불일치 구조를 CL-E와 공동 감사한다. R-SYN/R-SILVER 부호 불일치를 숨기지 않는다. | BLOCKER / OPEN |
| T2 / PR-1 synthetic generator | 패널 시점에는 벽 generator 부재가 공격이었고, 최신 다이제스트에서는 pack이 생겼지만 B1 fidelity가 FAIL이다. | 최신 상태를 “부재 해소, 자격 미달”로 정정한다. divergent entity와 negative/sentinel을 넣은 version bump가 fidelity를 통과해야 confirmatory 실행. | BLOCKER / OPEN |
| T3/T4 CL-A provenance | 실도면 divergence와 판정 artifact가 틀리면 A·C의 기초 population이 오염된다. | CL-A의 handle 실재성, transform, bbox/unit, 정렬 artifact 감사 결과 hash를 input provenance로 요구한다. | UPSTREAM OPEN |
| T5 / PR-3 counsel | CubiCasa/FloorPlanCAD의 NC 및 원도면 권리가 학습·파생물 사용을 막을 수 있다. | 서면 허용 범위가 오기 전 해당 자산은 코드 smoke 외 학습·confirmation에 사용하지 않는다. | BLOCKER / OPEN |
| T6 evaluation unit | 모델에 따라 pixel mask, handle, 집합 조립 점수를 섞으면 family effect가 metric 효과가 된다. | 모든 primary 응답을 `wall_member(h)`로 고정하고 raster도 handle로 exact back-project한다. 집합/room metric은 별도 후속. | DESIGN RESOLVED, 실행 검증 필요 |
| T7 zero-wall sentinel | F1만 보면 0벽 또는 전벽 탐지기가 유리할 수 있다. | zero-truth 도면을 별도 S0로 평가하고 macro recall floor를 동시에 요구한다. | DESIGN RESOLVED, threshold prereg 필요 |
| T9/T21 baseline | 기존 v0/v1 baseline이 다른 population이면 lift가 비교 불가다. | 16셀과 같은 panel에서 frozen v1을 reference로 평가하되 effect matrix의 추가 셀로 넣지 않는다. 기존 `0.2358`/`0.517`은 prior로만 사용. | OPEN UNTIL RUN |
| T10/T23 Graph IR adjacency·silver gate 문맥 | 패널은 이 번호들을 Graph IR 완전성과 silver gate 식별자 문맥에 함께 언급한다. canonical ticket 원문 없이 어느 해석도 닫을 수 없다. | adjacency/transform exactness와 silver B1/B4 명칭을 별도 gate로 구현하고, ticket ledger에서 번호 매핑을 확인한다. calibration의 “B1 well-posed + B4 Pearson gate” 해석을 보존한다. | OPEN / NUMBER MAPPING NEEDS SOURCE |
| T14/T33 name/firm convention | F 효과가 문자열 누수로 생길 수 있다. | layer/filename/path/firm string을 feature에서 금지하고 firm ID는 splitter에만 제공한다. 별도 name-enabled ablation은 CL-I로 보낸다. | DESIGN RESOLVED, scan evidence 필요 |
| T15 learned seed confounding | 한 learned seed가 treatment와 완전 confound될 수 있다. | 모든 learned 셀에 같은 3-seed block, cell mean primary, seed dispersion 공개. 1 seed면 pilot 강등. | DESIGN RESOLVED, budget 필요 |
| T16 absolute 대 relative band | scale 팔 실패 때문에 deterministic 설정 하나가 단위 관례를 외울 수 있다. | P1에서는 scale-normalized feature contract를 동결하고 절대-vs-상대 비교는 CL-B/Taguchi 선행 실험으로 분리한다. | ACCEPTED SCOPE LIMIT |
| T17 truth-source cross-factor | C의 train source와 response truth가 섞이면 대각 성능만 좋아지는 부트스트랩 폐합이 생긴다. | C는 train/tune source만 바꾸고 두 고정 eval panel을 모든 셀에 적용한다. proxy 불일치 감사와 합친다. | DESIGN RESOLVED, T1 remains |
| T22 lift gate | 다른 learned 제안이 frozen baseline 대비 lift를 요구한다. | P1은 자체 band와 effect를 먼저 보고하며, 타 제안의 P1 대비 lift를 달성한 척하지 않는다. 후속 GNN/VLM만 frozen P1 winner 대비 lift를 요구한다. | DEFERRED TO FOLLOW-UP |
| T24 pixel→handle projection | raster 셀의 성적이 실제 벽 handle에 귀속되지 않으면 A가 비교 불능이다. | paired renderer + integer handle buffer + synthetic exact round-trip을 hard gate로 둔다. FloorPlanCAD는 primary A에서 제외. | BLOCKER UNTIL IMPLEMENTED |
| T31 raster “본선” 주장 | raster가 graph보다 낫다는 결론을 미리 정하면 A가 장식 요인이다. | A는 양방향 효과로 분석하고 raster를 본선이라 부르지 않는다. zero-pair 초과 회수는 CL-G 후속 증거가 필요하다. | ACCEPTED |
| T34 citation status | 배경 문헌과 실행 증거가 섞이면 unrun proposal이 실행된 것처럼 보인다. | 모든 문헌은 이론 근거로만 쓰고 effects/interactions/confirmation을 UNRUN으로 명시한다. 외부 검색도 하지 않았다. | DESIGN RESOLVED |

추가로 P1의 패널 PARK 사유 두 개를 직접 수용한다.

1. `representation×truth`와 `family×self-training` confounding은 G2=`AC=BE`로 정확히 기록한다.
2. learned seed confounding은 공통 seed block으로 낮추되, seed 반복은 2FI 별칭을 풀어 주지 않는다는 점을 명시한다.

해결하지 못한 티켓을 PASS로 바꾸지 않는다. 특히 T1, T2, T5, T24가 닫히기 전에는 full 16-cell result를 confirmatory evidence로 만들 수 없다.

---

## 8. 인접 제안과의 관계 및 P1 사망 조건

### 8.1 병합 가능한 지점

- **CL-A 법의학 감사**: graph IR/transform/population provenance를 P1 Phase 0 gate로 직접 소비한다. CL-A가 measurement artifact를 찾으면 P1 dataset version을 올린다.
- **CL-B coverage-complete deterministic v1**: P1의 B=-1 exemplar와 `Θ_rule` 후보를 제공한다. 상대 scale anchor와 INSERT world transform 수정은 P1 전에 동결한다.
- **CL-C wall synthetic truth / WSD-EVAL-v1**: P1의 T-SYN과 `P_SYN`을 제공하는 하드 선결이다. 합성 fidelity FAIL 상태에서는 병합이 아니라 blocker다.
- **CL-D metamorphic battery**: rigid/unit/explode/layer rename와 zero/all-wall sentinel을 cell validity guardrail로 붙인다. metamorphic score를 일곱 번째 factor로 몰래 추가하지 않는다.
- **CL-E truth-source cross-factor metaexperiment**: P1의 C와 dual response가 2×2 일부를 제공한다. human truth와 metamorphic까지 포함한 proxy 독립성은 CL-E가 더 넓고, P1은 그 결과를 gate로 소비한다.
- **CL-F learned ladder**: P1-v1은 deterministic 대 frozen HGB의 스크린이다. B가 활성이고 robust하면 고전 ML→PU→GNN으로 세분한다. HGB가 이미 충분하면 GNN을 죽이는 Occam gate가 된다.
- **CL-G raster/VLM**: paired render와 pixel→handle exact harness를 공유한다. 다만 P1 raster는 동일 handle 후보의 raster evidence이고, CL-G는 end-to-end raster/VLM까지 갈 수 있다는 차이가 있다.
- **CL-I convention prior**: F가 강하면 firm lexicon/관례 실험으로 hand-off한다. P1 primary에서는 이름을 mask한다.
- **CL-K anti-silver arm**: silver를 학습 target으로 쓰지 않는 gate-only control은 P1의 별도 7번째 factor로 넣지 않는다. C 또는 G4가 활성일 때 version-bumped follow-up에 상설 control로 넣는다.
- **CL-H RL / CL-J face-room-first**: per-handle HGB와 모든 P1 셀이 plateau면 표현과 학습 family의 미세 조정보다 평가 단위 또는 관측 언어를 바꿔야 하므로 이 두 proposal로 hand-off한다.

### 8.2 차별점

P1은 새 detector architecture 제안이 아니라 **설계 선택의 조건부 효과를 찾는 판정기**다. CL-B는 deterministic coverage를 고치고, CL-F는 learned model을 깊게 만들며, CL-G는 raster/VLM을 전개한다. P1은 어느 쪽이 어떤 truth·representation·leakage 조건에서 살아남는지 최소 실행으로 분해한다. 따라서 P1이 성공해도 제품 detector가 자동 완성되는 것은 아니며, 활성 요인을 후속 세분화할 우선순위가 생길 뿐이다.

### 8.3 이 제안이 죽어야 하는 조건

다음 중 하나면 P1을 중지하거나 새 prereg로 갈아엎는다.

1. **요인 설정 불능**: 같은 도면·handle·truth에서 A 양 수준을 만들 수 없거나, deterministic E=on을 정의할 수 없거나, T-SYN에 firm/style group이 없어 F를 설정할 수 없다.
2. **합성 자격 실패 지속**: version-bumped generator도 fidelity gate를 통과하지 못한다. 이 경우 C=T-SYN과 R-SYN을 중심으로 한 master screen을 버리고 PR-1/CL-C로 되돌아간다.
3. **법무 kill**: counsel이 핵심 학습 또는 파생 평가를 허용하지 않는다. 허용된 자산만으로 새 population을 만들기 전에는 실행하지 않는다.
4. **projection kill**: raster→handle exact harness가 실패한다. 이 경우 A는 factor가 아니라 별도 트랙으로 분리한다.
5. **global synthetic kill**: 16셀 모두 `R-SYN<0.75`. 모델 family 비교가 아니라 표현·정답원 기반이 실패한 것이므로 learned 확대를 중지한다.
6. **global silver kill**: 어떤 셀도 `R-SILVER>0.30`이 아니다. silver가 판별 신호가 없으므로 P3/CL-E proxy 감사로 보낸다.
7. **합성 천장**: 전 셀이 R-SYN 천장이고 효과 대비가 ME보다 작다. “모든 방법이 좋다”가 아니라 generator가 구분하지 못한다고 판정하고 harder hidden mutations로 version-bump한다.
8. **seed 불안정**: learned 셀의 순위 또는 effect sign이 seed에 따라 뒤집히며 허용 budget 안에서 안정화되지 않는다. learned 관련 주장을 죽인다.
9. **고차·비희소 실패**: H1/H2가 크거나 Lenth PSE가 작은 효과 집합을 만들지 못한다. 16-run screen의 sparsity 가정이 깨졌으므로 replicated 또는 더 큰 design으로 바꾼다.
10. **별칭 해소 불가**: 활성 alias chain이 나왔으나 표적 증강 budget 또는 identifiability를 확보하지 못한다. 개별 2FI 인과 이야기를 포기한다.
11. **cheap winner**: B와 E가 small/null이고 deterministic·ST-off 셀이 dual PASS와 hold-out을 만족한다. 이때 학습·자기학습 확대를 죽이고 더 단순한 셀을 채택한다.
12. **Goodhart failure**: screen winner가 미사용 firm hold-out에서 frozen baseline보다 나빠지거나 R-SYN 상승과 hold-out 하락이 짝으로 나타난다. winner 선택과 downstream test를 중지한다.
13. **전 그리드 plateau**: representation/truth/model을 바꿔도 R-SILVER가 같은 낮은 plateau에 머문다. 요인 목록 밖의 poché, text, room/face signal이 필요하다는 abduction 좌석으로 hand-off한다.

### 8.4 최종 go/no-go 순서

```text
PR-2 proxy audit + PR-1 fidelity + PR-3 counsel
        ↓ 모두 통과
paired graph/raster exactness + firm manifests + config provenance
        ↓ 모두 통과
deterministic 8-cell cheapest probe
        ↓ A/C/F가 설정 가능하고 최소 신호 존재
learned 8-cell × common seed blocks
        ↓ 16 valid cells
Lenth main/alias-chain screen + dual-response/guardrail audit
        ↓ active chain이면
rank-verified targeted augmentation (새 prereg)
        ↓ winner가 있으면
unused-firm confirmation 1회 → CubiCasa test 외부감사 1회
```

이 순서에서 어떤 화살표도 자동 PASS가 아니다. 현재 최종 상태는 `UNRUN/PARKED`, confirmation은 `PASS_WITH_DEFERRAL`이다. 본 도시에는 실행 가능한 계약과 중단 규칙을 제공하지만, 효과·상호작용·winner를 측정했다고 주장하지 않는다.

### 8.5 명시적 abstentions

1. G1–G7 안의 개별 2FI는 증강 실행 전에는 분리됐다고 주장하지 않는다.
2. B는 frozen HGB exemplar이므로 learned 전체, GNN, VLM의 우열로 일반화하지 않는다.
3. poché, text label, room/face 같은 factor 목록 밖 신호를 P1 결과에서 발명하지 않는다. plateau면 인접 abduction 제안으로 넘긴다.
4. density, unit, layer-naming 유무는 관측 block/covariate일 뿐 설정 요인이 아니다. 연관을 보고할 수는 있어도 인과효과라고 쓰지 않는다.

DOSSIER_COMPLETE: doe_P1
