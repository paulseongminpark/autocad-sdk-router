# E2 방법론 심층 도시에 — doe_P2

## 집행 요약

이 제안의 올바른 역할은 벽 의미 탐지기의 표현력을 늘리는 것이 아니라, 이미 존재하는 `wall_pairs.py` 결정 규칙의 네 연속 노브가 도면·firm·단위·밀도·레이어 관례 변화에 얼마나 흔들리는지를 가장 싸게 판정하는 것이다. 핵심 실험은 표준 Taguchi L9(3^4) inner array의 9개 설정을, 145장 아카이브에서 firm을 먼저 분리하고 층화한 개발용 40장에 동일하게 적용하는 360회 결정 평가다. 셀내 반복은 하지 않는다. 도면 자체가 outer noise population이며, IR과 코드·설정·도면이 고정된 한 셀은 순수 결정 함수여야 한다.

다만 원제안을 그대로 실행하면 네 가지 과장이 생긴다. 첫째, L9는 4개 3수준 주효과의 8 자유도를 모두 써서 포화되므로, 행별 S/N만으로는 순수오차를 추정할 수 없다. 둘째, 상호작용은 분리되지 않아 “clean main effect”라고 부를 수 없다. 셋째, R-META 위반율만 최소화하면 아무 벽도 내지 않는 탐지기가 이길 수 있다. 넷째, 절대 mm gap 대역은 unit/scale 관례와 엉킬 수 있으므로 패널 T16의 절대 대역 대 치수-정박 상대화 게이트가 L9보다 먼저 와야 한다. 따라서 본 도시에은 (a) baseline·단위 계약·sentinel 선행 게이트, (b) 5장 cheapest probe, (c) 40장 L9, (d) 활성 요인에 한한 상호작용 후속, (e) 완전히 분리한 hold-out firm 확인의 순서로 실행한다.

최종 채택은 평균만으로 고르지 않는다. R-META PASS 밴드, all-wall/zero-wall sentinel, 합성 recall 하한을 모두 만족한 설정 중, 평균 최적 수준의 인접 후보 집합에서 도면 간 분산이 가장 낮은 **실제로 관측한 L9 행**을 지명한다. 주효과를 합성해 만든 미관측 조합은 L9의 별칭 때문에 곧바로 채택하지 않고 별도 confirmation 설정으로만 다룬다. hold-out firm에서 R-META가 FAIL(`>0.10`)이면 즉시 kill한다. 전 그리드가 plateau이면 결정 휴리스틱의 천장으로 판정하고 학습 계열로 이관한다.

수치 출처 규칙: 성능·자산·규모에 관한 실측 수치는 모두 패킷의 2026-07-18 다이제스트에서만 가져왔다. 아래의 문헌 연도, 직교배열 성질, 수식은 방법론 일반 지식이며 이 프로그램의 새 실측이 아니다. “제안 임계값/계획값”으로 표시한 수치는 앞으로 봉인할 프리레지스트리 값이지 관측 결과가 아니다. 웹 검색은 사용하지 않았다.

---

## 1. 이론적 근거·선행연구

### 1.1 계보와 이 제안의 정확한 위치

이 설계는 Fisher식 실험계획의 요인·블록·교란 통제, Taguchi의 off-line quality control과 robust parameter design, 그리고 현대적인 반복측정/dual-response 해석을 결합한다.

- R. A. Fisher의 실험계획 계보는 처리 요인과 블록을 분리하고, 어떤 비교가 설계로 식별 가능한지를 먼저 묻게 한다. 여기서는 네 노브가 처리 요인이고, 동일 도면을 9개 설정에 모두 노출하는 paired block이며, source-firm은 상위 블록이다.
- Genichi Taguchi의 parameter design은 제품/알고리즘이 직접 통제할 수 있는 inner-array 요인과 운영 중 통제하기 어려운 outer-array 잡음을 분리한다. 이 제안에서 inner는 `angle_tol_rad`, `gap_lo/gap_hi`, `min_overlap_ratio`, `max_pairs_per_line`; outer는 source-firm, unit/scale, plan density, layer-naming 관례다.
- Madhav S. Phadke의 *Quality Engineering Using Robust Design*는 직교배열과 S/N 기반 강건설계를 공학적으로 체계화한 대표적 시스템이다. 서지 세부는 일반 지식에 따른 것이며 최종 인용 전 요검증이다.
- V. N. Nair가 정리한 1992년 *Taguchi's Parameter Design: A Panel Discussion*은 S/N을 만능 목적함수로 쓰는 것, 상호작용을 무시하는 것, 위치와 산포를 한 수치로 합치는 것의 위험을 논의한 대표 문헌이다. 권·호·쪽은 요검증이다.
- Vining과 Myers의 dual-response 접근은 평균 반응과 분산 반응을 별도로 모델링한 뒤 함께 선택하는 방향을 제시했다. 본 도시에이 S/N 외에 평균 R-META와 도면 간 분산을 별도 열로 유지하는 이유다. 정확한 서지 세부는 요검증이다.
- Shoemaker–Tsui–Wu 계열의 combined-array/경제적 robust design 논의는 inner×outer 전부를 기계적으로 늘리는 대신, 동일한 noise cases를 처리 설정 사이에 공유해 control×noise 민감도를 추정하는 관점을 준다. 정확한 논문 식별자는 요검증이다.

### 1.2 왜 L9가 맞고, 어디까지밖에 말할 수 없는가

L9(3^4)는 9행에서 3수준 요인 4개의 주효과를 서로 균형 있게 배치하는 strength-2 직교배열이다. 각 3수준 주효과는 2 자유도를 쓰므로 네 주효과가 8 자유도를 전부 소비한다. 따라서 이 설계의 장점은 3^4 완전요인의 81설정보다 훨씬 적은 9설정으로 각 수준의 평균 방향을 싸게 보는 데 있다. 단점은 다음과 같다.

1. **포화**: 9개 행의 S/N만 분석하면 총 8 자유도가 네 주효과에 모두 배정되어 독립적인 순수오차 자유도가 없다. 유의확률을 만들어 내면 가짜 정밀도다.
2. **상호작용 별칭**: 2요인 이상 상호작용을 독립적으로 추정하지 않는다. 예컨대 angle 허용이 넓어질 때 gap 대역 효과가 달라져도 이를 angle 주효과와 깨끗이 나눌 수 없다.
3. **outer 40장은 실험적 반복이 아니라 유한 모집단 표본**: 동일한 결정 함수에 서로 다른 도면을 넣어 noise sensitivity를 관측하는 것이다. 알고리즘 난수분산 추정이 아니다.
4. **S/N은 원인을 설명하지 않는다**: 높은 S/N이 낮은 평균 위반에서 왔는지, 낮은 분산에서 왔는지 분리 보고해야 한다.

패킷의 “resolution III 상당” 표현은 실무적 경고로 유지한다. 다만 3수준 OA의 별칭은 2수준 정규 분수요인처럼 한 문장짜리 defining relation으로 단순화해서는 안 된다. 본 실험의 안전한 해석은 오직 “주효과 스크리닝은 가능하되 모든 상호작용은 미식별”이다. L27 승격도 행만 늘린다고 자동 해소되는 것이 아니다. 상호작용용 열과 자유도를 명시적으로 배정해야 한다. 가장 안전하고 싼 후속은 활성 노브가 두 개일 때 그 둘의 3×3 완전요인이다.

### 1.3 왜 이 사례가 robust design인가

도면은 측정 반복이 아니라 실제 배포 환경의 변동원이다. source-firm은 도면 관례와 작성 문화, unit/scale은 수치 해석, density는 후보 폭발과 구조적 혼잡, layer-naming은 메타데이터 관례를 대표한다. 이들을 없애거나 평균 도면 하나로 환원하는 대신 같은 9설정을 모든 outer drawing에 걸어, 평균 실패와 도면 간 흔들림을 동시에 최소화한다. 목표 estimand는 “145장 파일 빈도에 비례한 평균”이 아니라, 대형 firm이 결과를 지배하지 않는 **equal-firm 강건성**이다. 따라서 firm당 총 가중치를 같게 주고 그 안에서 도면 가중치를 나눈다.

이 설계가 학습법과 다른 점도 분명하다. 파라미터를 데이터에 맞추지만 모델 가중치를 학습하지 않고, 레이블 없이 T-META로 1차 판정을 낸다. 그러므로 신호가 싸고 빠르지만 표현력 천장은 넘지 못한다. CubiCasa5k에서 기하 탐지기 v1의 val F1이 `0.2358`이고, 같은 SEG-IR의 6특징 HistGradientBoosting이 `0.517`이었다는 실측은 의미 교란이 단순 knob 조정보다 큰 문제일 가능성을 이미 보여 준다. 특히 Direction, BoundaryPolygon, Door, Window, DimensionMark 같은 긴 평행 구조가 FP의 본질 교란이므로, P2의 성공 정의는 “GBDT를 이긴다”가 아니라 “현재 결정 규칙이 어디까지 강건화될 수 있는지 싸게 판결한다”다.

---

## 2. 알고리즘 정확 스펙

### 2.1 입력, 출력, 고정물

입력은 다음 다섯 묶음이다.

1. 콘텐츠 해시가 고정된 도면 IR. primary outer는 145장 아카이브에서 firm 분리 후 뽑은 개발용 40장이다.
2. 각 도면의 noise metadata: `source_firm`, `unit_scale`(mm/m/unknown), `density_tertile`, `layer_naming_convention`(yes/no/unknown).
3. 고정된 T-META 변환과 대응 맵. 다이제스트에 있는 강체변환, scale, unit, 센티널을 포함하되 실제 T-META manifest에 존재하는 관계만 사용한다.
4. 고정된 T-SYN 팩과 per-handle truth. 현재 B1 충실도는 FAIL이므로 2차 가드레일로만 사용한다.
5. `wall_pairs.py` 코드 버전과 네 노브 외의 모든 상수. 탐지기 v1의 4증거 가중치, snap, 후보 생성 순서 등은 이번 실험에서 변경하지 않는다.

행별 출력은 도면별 R-META loss, firm별/전체 평균과 분산, R-META S/N, T-SYN의 family별 precision/recall/F1과 S/N, sentinel 결과, 계산량 계기, 그리고 네 요인의 수준별 main-effect 표다. 최종 산출은 설정 하나를 억지로 고르는 것이 아니라 `ROBUST_SETTING_NAMED`, `PLATEAU_KILL`, `HOLDOUT_FAIL`, `BLOCKED_PRECONDITION` 중 하나의 판정과 근거다.

평가 단위는 기본적으로 원본 도면의 canonical segment/handle membership이다. pair 수나 room 조립 성공을 per-handle F1에 섞지 않는다. explode 등으로 handle이 바뀌는 T-META 관계는 좌표 정규화 후 canonical geometry 대응표를 사용한다. 대응표를 만들 수 없는 변환은 해당 assertion에서 `NOT_APPLICABLE`로 남기며 실패를 0으로 발명하지 않는다.

### 2.2 inner array

요인과 수준은 패킷대로 고정한다.

| 요인 | L1 | L2 | L3 | 해석 |
|---|---:|---:|---:|---|
| A `angle_tol_rad` | 0.002 | 0.005 | 0.010 | 평행 허용각 |
| B `gap_lo/gap_hi` | (20,300) | (30,500) | (50,800) | 벽 두께 후보 대역(mm) |
| C `min_overlap_ratio` | 0.3 | 0.5 | 0.7 | 겹침 하한 |
| D `max_pairs_per_line` | 2 | 4 | 8 | 한 선의 pair fan-out 상한 |

표준 L9 배치는 다음과 같다.

| run | A | B | C | D |
|---:|---:|---:|---:|---:|
| 1 | 1 | 1 | 1 | 1 |
| 2 | 1 | 2 | 2 | 2 |
| 3 | 1 | 3 | 3 | 3 |
| 4 | 2 | 1 | 2 | 3 |
| 5 | 2 | 2 | 3 | 1 |
| 6 | 2 | 3 | 1 | 2 |
| 7 | 3 | 1 | 3 | 2 |
| 8 | 3 | 2 | 1 | 3 |
| 9 | 3 | 3 | 2 | 1 |

다이제스트의 v1 angle 허용은 `2°`인데 L9의 세 rad 수준은 환산하면 모두 그보다 작다. 따라서 “L9가 v1 주변의 국소 탐색”이라고 가정해서는 안 된다. 실행 전 단위 계약 테스트로 `wall_pairs.py`가 정말 rad를 받는지, `fast_score`와 같은 정의인지 확인하고 v1 baseline을 별도 reference row로 캐시해야 한다. 이 reference는 L9의 360회에 섞지 않으며 주효과 계산에도 넣지 않는다. 단위가 다르면 `BLOCKED_PRECONDITION`이다.

### 2.3 outer population과 표집

firm leakage를 막기 위해 그림을 먼저 뽑고 firm을 나중에 나누지 않는다.

1. 145장 전체에서 firm id의 출처와 결측을 감사한다. 파일명으로 임의 추정하지 않는다.
2. firm 집합을 development firms와 hold-out firms로 먼저 분리한다. 한 firm의 도면은 양쪽에 동시에 들어갈 수 없다.
3. development firms 안에서 `(unit_scale, density_tertile, layer_naming_convention)` 셀을 만든다. density는 엔티티/면적을 frozen IR에서 계산해 development pool만으로 3분위 경계를 고정한다. 면적이 유효하지 않으면 unknown 층으로 남긴다.
4. firm을 round-robin하며 희소 층부터 한 장씩 선택한다. 각 firm의 상한은 `ceil(40 / 사용 가능한 development firm 수)`를 원칙으로 하되, 그 상한으로 40장을 채울 수 없으면 부족 사유와 재분배를 manifest에 기록한다. 특정 firm의 상한 완화는 결과를 보기 전에 끝내야 한다.
5. 동일 firm 안에서 후보가 겹치면 경로가 아니라 콘텐츠 해시의 사전순으로 결정한다. 따라서 별도 RNG seed가 없다.
6. cheapest probe의 5장은 이 40장의 부분집합으로, 가능한 한 서로 다른 firm과 noise strata를 우선한다. 5장 결과를 본 뒤 40장 membership을 바꾸지 않는다.

firm metadata가 없거나 서로 다른 firm을 development/hold-out으로 나눌 수 없으면 L-FIRM 확인 주장을 할 수 없으므로 실험은 `BLOCKED_PRECONDITION`이다. 40장이 균형 잡힌 factorial outer array라고 주장하지도 않는다. 이것은 층화한 empirical outer population이며, 희소 조합의 불확실성은 그대로 보고한다.

### 2.4 R-META loss와 S/N

설정 `r`, 도면 `d`, 적용 가능한 metamorphic assertion `q`에 대해 원본 예측 집합을 `P(r,d)`, 변환 후 역매핑한 집합을 `P⁻¹_q(r,T_q(d))`라 하자. assertion 위반은 다음과 같이 정의한다.

```text
e[r,d,q] = | P(r,d) XOR P⁻¹_q(r,T_q(d)) |
             / | P(r,d) UNION P⁻¹_q(r,T_q(d)) |
```

합집합이 공집합이면 해당 invariance assertion만 0으로 둘 수 있지만, 이 값은 sentinel을 통과한 설정에서만 유효하다. 도면 loss는 적용 가능한 assertion의 고정 가중 평균이다.

```text
L_META[r,d] = sum_q w_q * e[r,d,q] / sum_q w_q
```

가중치는 결과를 보기 전에 T-META manifest에 봉인하며, 근거가 없으면 동일 가중치를 쓴다. primary estimand는 equal-firm weighted smaller-the-better S/N이다. firm 수를 `F`, firm `f`의 선택 도면 수를 `n_f`라 하면 도면 가중치는 `w_d = 1/(F*n_f)`다.

```text
eta_META[r] = -10 * log10( sum_d w_d * L_META[r,d]^2 )
```

모든 loss가 0이면 `+infinity`로 기록하되 sentinel/recall gate가 실패한 행은 순위에서 제외한다. 임의 epsilon을 넣어 유한한 우승자를 만들지 않는다. R-META 위반율은 별도로 equal-firm weighted mean으로 계산하고 패킷의 밴드를 그대로 적용한다.

- PASS: `R-META <= 0.02`
- INCONCLUSIVE: `0.02 < R-META <= 0.10`
- FAIL: `R-META > 0.10`

분산은 같은 가중치로 계산한 도면 간 분산과 firm 평균 간 분산을 모두 낸다. S/N 하나로 평균과 산포를 숨기지 않는다.

### 2.5 collapse 방지와 R-SYN

각 L9 행은 S/N 계산 전에 다음 hard gate를 통과해야 한다.

1. zero-wall sentinel에서 양성을 만들지 않는다.
2. all-wall sentinel에서 알려진 wall-member를 회수한다.
3. T-SYN family별 recall이 제안 프리레지스트리 하한 `0.95` 이상이다. 이 `0.95`는 새 실측이 아니라 collapse 방지용 제안 임계값이며 실행 전에 봉인한다.
4. 출력 수가 0인데 R-META만 완벽한 행은 자동 탈락한다.

T-SYN의 secondary larger-the-better S/N은 truth가 있는 독립 합성 항목 `j`의 F1으로 계산한다.

```text
eta_SYN[r] = -10 * log10( mean_j( 1 / F1[r,j]^2 ) )
```

하나라도 F1이 0이면 `eta_SYN=-infinity`다. S팩은 채점 우주에 음성이 0개여서 precision이 공허하므로 S의 F1을 pooled S/N에 넣지 않고 recall sentinel로만 쓴다. F와 M의 per-handle F1은 분리해서 보고한다. 현재 B1 fidelity가 `KS 0.5792`, `TV 0.265`로 FAIL이고 실도면의 SPLINE/ARC/HATCH 혼재를 합성팩이 담지 못하므로, R-SYN은 어떤 경우에도 R-META/hold-out firm을 덮어쓰지 못한다.

### 2.6 주효과, active 판정, 강건 설정 선택

S/N 수준효과는 다음과 같다.

```text
E_SN[k,l] = mean( eta_META[r] for runs r where factor k is at level l )
Delta_SN[k] = max_l E_SN[k,l] - min_l E_SN[k,l]
```

`Delta_SN`으로 rank를 매기되, active 판정에 행별 S/N의 가짜 잔차를 쓰지 않는다. 9×40 long-form loss에 다음 additive descriptive model을 적합한다.

```text
L_META[r,d] = mu
              + drawing_block[d]
              + alpha_A[level_A(r)]
              + alpha_B[level_B(r)]
              + alpha_C[level_C(r)]
              + alpha_D[level_D(r)]
              + epsilon[r,d]
```

도면은 모든 run에 반복 노출되므로 paired block으로 취급한다. drawing block이 그 도면이 속한 firm의 고정 차이까지 흡수하므로 같은 식에 firm 고정효과를 중복 투입하지 않는다. firm별 평균·분산은 별도 집계한다. p-value나 독립 반복 수를 보고하지 않는다. `sigma_resid = std(epsilon)`는 설정에 대한 도면별 민감도, 즉 control×drawing 잔차를 같은 loss 척도에서 요약한다. 패킷의 공통 규칙은 다음처럼 차원 일치하게 적용한다.

```text
active(k) iff max_l alpha_k[l] - min_l alpha_k[l] > 2 * sigma_resid
```

사전 가설 rank는 `gap_range > min_overlap > angle_tol > max_pairs`다. 결과표에는 가설 일치 여부와 null을 모두 기록한다. `max_pairs`가 null이면 실제 fan-out cap hit rate도 같이 봐서 “상한이 높아 무의미한 것”과 “fan-out 자체가 무의미한 것”을 구분한다.

강건 설정은 다음의 결정순서로 고른다.

1. sentinel과 synthetic recall gate를 통과하고 R-META PASS인 **관측 L9 행**만 후보로 둔다.
2. 평균 loss가 최소인 행의 factor-level vector를 `l*`로 둔다.
3. 각 요인의 ordinal level이 `l*`와 같거나 한 단계 인접한 관측 행을 near-optimal 후보로 둔다. 이것이 패킷의 “평균 최적 ±1 수준”의 실행 정의다.
4. 후보 중 equal-firm weighted drawing variance가 최소인 행을 고른다. 동률이면 firm-mean variance, 그다음 mean loss, 그다음 run id 사전순이다.
5. 주효과 합성으로 예측한 미관측 조합은 `predicted_optimum`으로만 기록한다. 관측 robust row보다 먼저 채택하지 않는다.

후보가 하나도 없으면 setting을 지명하지 않는다. 전 행의 `Delta_SN`과 mean/variance 차이가 active 기준 아래면 `PLATEAU_KILL`이다.

### 2.7 정확한 의사코드

```text
preflight():
    assert packet factor names map one-to-one to wall_pairs.py parameters
    assert angle unit is rad and gap unit conversion is explicit
    assert fast_score and reference scorer agree on a frozen parity fixture
    freeze code/config/IR/T-META/T-SYN hashes
    build firm-first dev40, pilot5, holdout-firm manifests without outcomes
    run zero-wall and all-wall sentinels for every candidate setting

absolute_vs_relative_gate():
    compare declared-unit absolute gap interpretation with the preregistered
    dimension-anchored scale interpretation on development-only probe data
    if the interpretation changes eligibility/rank materially:
        freeze the winning parameterization before L9
    if no reliable dimension anchor exists and units are unresolved:
        return BLOCKED_PRECONDITION

evaluate(run r, drawing d):
    ir = frozen_ir[d]
    pred0 = wall_pairs(ir, factors[r], fixed_nuisance)
    for relation q in frozen_T_META:
        predq = wall_pairs(transform(ir,q), factors[r], fixed_nuisance)
        e[q] = canonical_membership_disagreement(pred0, inverse_map(predq,q))
    return weighted_applicable_mean(e), process_counters

pilot():
    for r in L9:
        for d in pilot5:
            evaluate(r,d)             # exactly one deterministic evaluation
    report direction only
    do not change dev40 membership, metrics, thresholds, or L9

main():
    for r in L9:
        for d in dev40:
            evaluate(r,d)             # 9 * 40 = 360
        score frozen T-SYN once per item
        apply sentinel/recall eligibility gate
        compute equal-firm mean, variance, eta_META, eta_SYN
    fit additive descriptive model on long-form losses
    rank main effects; apply 2*sigma_resid active rule
    choose observed robust row by eligibility -> near-optimal -> min variance

interaction_followup():
    if exactly two factors are active:
        run their 3x3 full factorial with other factors frozen
        on development drawings only
    elif interaction risk remains material:
        preregister an L27 with explicit interaction columns or kill interpretation

confirm():
    run one named robust setting on drawings from hold-out firms only
    recompute S/N, mean, drawing variance, firm variance, sentinels
    if R_META > 0.10: return HOLDOUT_FAIL
    else return PASS_WITH_DEFERRAL with interval/variance evidence
```

### 2.8 절대 gap 대 치수-정박 상대화 선행 게이트

T16을 무시하고 absolute-mm L9를 먼저 돌리면 unit convention을 knob 효과로 잘못 읽을 수 있다. 따라서 gap 계산은 다음 두 해석을 개발 자료에서만 대조한다.

- **A: declared-unit absolute** — CAD unit metadata를 통해 좌표 gap을 mm로 변환하고 패킷의 세 대역을 적용한다.
- **B: dimension-anchored relative** — 도면의 신뢰 가능한 dimension entity에서 표시 길이와 기하 길이의 대응을 검증하고, 검증된 표시 길이의 robust median을 도면별 anchor `a_d`로 둔다. development drawings의 equal-firm weighted median anchor를 `a_ref`로 한 번 고정한다. level `l`의 원래 경계 `(lo_l, hi_l)`를 도면 `d`에서는 `(lo_l*a_d/a_ref, hi_l*a_d/a_ref)`로 바꾼다. 즉 큰 치수 관례의 도면에서는 band도 비례 이동한다. dimension이 없거나 서로 모순되면 `anchor_unavailable`로 남긴다.

B의 anchor와 `a_ref`는 벽 truth나 detector 결과를 보지 않고 고정해야 한다. A/B 판정은 5장 development probe에서 A/C/D를 frozen baseline에 두고 세 gap level을 양쪽 해석으로 평가하는 30개 결정 비교다. scale/unit R-META band가 달라지거나, sentinel eligibility가 달라지거나, A/B paired loss 차이가 `2*sigma_drawing`을 넘으면 material difference로 정의한다. B가 A보다 낮은 loss 방향으로 material하고 sentinel을 악화시키지 않으면 원래 absolute-grid 청구는 죽고 B로 factor definition을 다시 봉인한 뒤 L9를 시작한다. material difference가 없으면 더 단순한 A를 유지한다. synthetic F1로 A/B를 고르지 않는다. 정확한 anchor parser와 결측 정책이 구현되지 않으면 “relative가 좋다”는 새 주장을 만들지 않는다.

---

## 3. 벽 과업 적응 설계

### 3.1 145 아카이브와 `1.dwg` 실도면축

P2의 본선은 145장 아카이브다. `1.dwg` 한 장은 연결 smoke fixture로만 쓴다. 그 한 장에서 최고인 노브를 선택하거나, 40장 결과가 나쁜데 `1.dwg` 그림이 좋아 보인다는 이유로 살리지 않는다. 1.dwg staged DXF에는 도면정의가 `384`개이고, 실측 최대 도면정의는 `412,775` 선분이므로 다음 process counters를 모든 셀에 남긴다.

- 입력 선분 수, orientation/spatial bucket 수
- 생성 전 후보 수와 필터 단계별 잔존 수
- `max_pairs_per_line` cap hit 수
- peak working-set 추정과 wall-clock
- `not_applicable` metamorphic assertion 수

`max_pairs_per_line`은 출력 fan-out만 제한할 뿐 후보 열거의 quadratic 폭발을 막는다고 가정하지 않는다. 구현은 각도 bucket과 spatial index로 `gap_hi` 밖 후보를 만들지 않고, chunked streaming을 사용해야 한다. 5장 pilot에서 후보 수와 메모리를 측정해 **40장 실행 전에** per-drawing candidate/time hard cap을 봉인한다. cap 초과 도면을 조용히 제외하지 않고 `COMPUTE_ABORT` 반응으로 기록한다. 대형 도면이 반복해서 cap을 넘으면 “값싼 실측” 가정이 죽는다.

### 3.2 T-META와 sentinel

다이제스트에서 강체(회전·이동·반사)와 unit은 `1.0 PASS`, scale 팔은 `0.7624 FAIL`, 센티널은 strict FAIL이었다. 따라서 P2가 가장 먼저 회수해야 할 신호는 이미 통과한 관계를 다시 축하하는 것이 아니라, scale/unit/gap 상호작용과 sentinel collapse다. R-META는 다음처럼 사용한다.

- 강체 관계는 회귀 방지 control이다. 어느 L9 행이라도 이를 깨면 구현/대응맵 오류를 우선 의심한다.
- scale과 unit 관계는 gap parameterization의 1차 판별자다.
- layer rename은 v1 탐지기의 full-vs-name-blind가 `1.0`으로 동일했던 사실과 정합되는 negative control이다. 이 관계만 좋아져도 의미 개선으로 세지 않는다.
- zero-wall/all-wall sentinel은 eligibility gate다. 위반율의 한 항으로 평균내어 숨기지 않는다.

T-META와 T-SYN이 모두 평행 이중선 prior를 공유할 수 있으므로 두 점수를 합쳐 하나의 “truth score”로 만들지 않는다. 같은 definition에서 disagreement table을 만들어 `META pass / SYN fail`, `META fail / SYN pass`, `both pass`, `both fail`을 보고한다. 이 표가 T1/T17 대리 독립성 감사에 연결된다.

### 3.3 CubiCasa5k SEG-IR 벡터축

CubiCasa5k는 5,000도면 전량이 SEG-IR로 변환됐고 실패가 0이며, train/val/test가 각각 4,200/400/400으로 분리되어 있다. P2는 학습이 없지만 노브 선택은 튜닝이므로 **val만 개발에 사용하고 test는 최종 설정 동결 전까지 열지 않는다**.

직접 접속은 `cubicasa_ir`이 만든 segment fields를 `wall_pairs.py`/`fast_score` 입력 adapter로 보내는 방식이다. 그러나 CubiCasa 좌표는 px이고 도면별 scale이 미상이며 벽 두께 px p50은 `22`다. 그러므로 mm gap 세 수준을 px에 임의 대입해서는 안 된다. 다음 중 하나가 충족될 때만 external transfer arm을 연다.

1. val에서 outcome label을 보지 않고 계산하는 scale-free gap parameterization을 봉인했거나,
2. dimension/metadata 기반의 정확한 px↔물리 scale mapping이 존재하고 leakage audit를 통과했거나,
3. gap 요인을 고정한 채 angle/overlap/fan-out의 제한적 transportability만 별도 주장한다.

이 선결 없이 P2가 CubiCasa val F1 `0.2358`을 개선했다고 주장하는 것은 허용하지 않는다. 합법적인 val diagnostic에서도 R-META 강건성과 per-handle F1을 분리한다. v1은 recall `0.981`, precision `0.134`였고 물리 축척 prior가 무력했으며 최소길이 필터 천장도 F1 `0.335`였다. 따라서 P2가 기대할 수 있는 것은 주로 FP fan-out과 scale 불변성 안정화이지, 긴 평행 의미 교란을 제거하는 새 표현력은 아니다. `cubicasa_ml`의 HistGradientBoosting val F1 `0.517`, AUC `0.9215`는 후속 학습 계열의 empirical comparator로 유지한다. P2가 test에 진입한다면 모든 임계와 설정을 봉인한 뒤 방법당 단 한 번 실행하고, 실패도 xlsx에 기록한다.

### 3.4 FloorPlanCAD 래스터축

FloorPlanCAD는 래스터 5,308장과 wall bbox/segmask이며 벡터 SVG가 없다. `wall_pairs.py`는 segment-pair 결정기이므로 직접 접속점이 없다. 래스터를 임의 vectorize해 생긴 선분을 “원래 handle truth”라고 부르면 평가 단위가 바뀐다. 따라서 본 P2 core에는 FloorPlanCAD를 넣지 않는다.

향후 CL-G의 exact pixel→handle 또는 vectorization correspondence harness가 합성에서 검증되면, P2 설정을 고정한 채 raster-derived segment에서 외부 강건성만 확인할 수 있다. 그 전에는 FloorPlanCAD가 필요한 셀을 `NOT_APPLICABLE`로 두며 결과를 발명하지 않는다. NC/원 도면 권리에 대한 PR-3 counsel 확인도 선행 조건이다.

### 3.5 합성축과 기존 B1 실패

T-SYN은 knob가 recall을 버리는지, mutation family에 취약한지를 값싸게 감시하는 가드레일이다. 그러나 현 합성팩은 LINE/LWPOLYLINE/INSERT 세 종류뿐이며 B1 fidelity FAIL이다. 따라서 다음 제한을 둔다.

- S/F/M 결과는 family별로 분리한다.
- S팩의 precision/F1은 음성 0 때문에 우승 기준에서 제외한다.
- synthetic S/N이 좋아도 outer R-META가 INCONCLUSIVE/FAIL이면 채택하지 않는다.
- CL-C/PR-1이 SPLINE, ARC, HATCH, 비평행 조각 등 실현상을 포함한 충실도 게이트를 통과하면 그때 R-SYN을 confirmation의 정식 2차 축으로 승격한다.

### 3.6 이 방법이 실제로 더 가져올 수 있는 것

가능한 기여는 세 가지다.

1. 현재 네 knob 중 어떤 것이 도면 간 흔들림을 실제로 지배하는지, 혹은 모두 null/plateau인지 판정한다.
2. 평균 성능이 비슷한 설정 중 firm·단위·밀도 변화에 덜 민감한 설정을 선택한다.
3. 절대 gap, unit conversion, scale metamorphic 실패가 같은 문제인지 분리하는 가장 싼 실측을 준다.

가져올 수 없는 것은 새로운 wall semantics다. 단선 벽, polyline wall, hatch wall, 평행선쌍이 아닌 표현은 요인공간 밖이다. 모든 knob가 긴 Door/Window/DimensionMark를 벽처럼 보는 공통 오류도 튜닝으로 제거되지 않는다. 그 경우 plateau 자체가 유용한 음성 결과이며 CL-F의 고전 ML 또는 P1/P6 학습 계열로 이관한다.

---

## 4. 데이터·컴퓨트 요구

### 4.1 필수 데이터와 메타데이터

| 자산 | 역할 | 필수 조건 | 실패 시 |
|---|---|---|---|
| 145장 실무 DWG 아카이브의 frozen IR | primary outer population | content hash, source-firm, unit/scale, density 계산 가능 | firm/scale claim 차단 |
| development 40장 manifest | 360회 main run | firm-first split, strata coverage, 결과 독립 선택 | 실험 무효 |
| hold-out firm manifest | confirmation | development와 firm 완전 분리 | `PASS_WITH_DEFERRAL` 불가 |
| T-META manifest | primary truth proxy | 변환, inverse map, applicability, weight 고정 | R-META 계산 차단 |
| T-SYN S/F/M | collapse/secondary | per-handle truth, family id | secondary만 제외 |
| CubiCasa SEG-IR val/test | optional transport | px-gap 계약과 counsel | P2 core는 계속 가능 |
| FloorPlanCAD raster | 현재 비사용 | exact correspondence와 counsel | `NOT_APPLICABLE` |

noise metadata는 모델 결과를 보고 손으로 고치지 않는다. layer convention 판정 규칙이 아직 없다면 token vocabulary와 outcome을 보지 않는 결정 규칙을 먼저 문서화하고 `unknown`을 허용한다. density 3분위 경계는 development pool에서 한 번 계산해 hold-out에 그대로 적용한다.

### 4.2 로컬 실행

이 방법은 전부 결정·경량이며 RTX 5070 Ti 16GB를 요구하지 않는다. 64GB RAM에서 IR 전체를 동시에 복제하지 않고 도면 하나씩 stream한다.

- IR freeze는 도면별 immutable artifact와 content hash를 사용한다.
- 각 run은 같은 IR을 재사용하고 knob만 바꾼다.
- orientation/spatial index 중 factor-independent 부분만 캐시한다. `gap_hi`나 angle에 의존하는 후보 집합을 잘못 공유하지 않는다.
- 결과 cache key는 `(code_hash, ir_hash, factor_vector, fixed_config_hash, tmeta_hash)` 전체다.
- xlsx evidence에는 run×drawing 원자료, factor map, process counters, errors, exclusions, manifest hash를 포함한다.
- 5장×9행 cheapest probe는 패킷상 30분 내 방향 확인용이며, main은 9×40=360 평가다. 이 시간은 목표 예산이지 완료 실측이 아니다.

GPU는 CubiCasa 기존 SEG-IR을 다시 만들지 않는 한 사용하지 않는다. ML 재학습, qwen2.5-VL-3B, frontier VLM API는 P2 범위 밖이다.

### 4.3 DGX 계획

DGX Spark의 Ornith-35B가 unreachable이어도 P2에는 영향이 없어야 한다. DGX를 “나중에 쓰면 빨라질 것”이라고 종속성으로 만들지 않는다. DGX 사용 계획은 없음이 정답이다. 향후 VLM이나 learned follow-up으로 이관될 때 별도 제안에서 다룬다. P2의 로컬 CPU 실행이 성립하지 않으면 compute_plan 가정 자체가 실패한 것이다.

### 4.4 결정성, 시드, 순서

모든 셀의 seed는 `NONE`이다. 같은 `(knob, drawing)`을 여러 번 실행해 표준편차를 만드는 것은 금지한다. 도면 선택 동률은 content hash 사전순으로 해소하고, run/drawing 실행 순서는 기록하되 response 추정에 사용하지 않는다. purity preflight에서 같은 cache key가 다른 digest를 내면 hidden state가 있다는 뜻이므로 main run을 중단한다. 이 경우 반복을 늘리는 것이 아니라 hidden state를 제거하고 IR을 다시 freeze해야 한다.

---

## 5. 구현 계획

아래는 후속 구현 때 만들 제안 골격이며, 본 도시에 작성 단계에서는 실제 파일을 생성하지 않는다.

```text
e2/
  doe/
    taguchi_l9.py              # 표준 L9 생성·검증, factor mapping
    outer_manifest.py          # firm-first split, strata, weights, hashes
    gap_parameterization.py    # declared-unit vs dimension-anchored gate
    run_taguchi.py             # streaming orchestration, cache key, abort policy
    robust_select.py           # eligibility, S/N, variance, active rule, selection
    confirmation.py            # hold-out firm one-setting confirmation
  metrics/
    metamorphic_loss.py        # canonical correspondence와 R-META
    taguchi_sn.py              # STB/LTB S/N, infinity 규칙
    sentinels.py               # zero-wall/all-wall/collapse gate
  adapters/
    wall_pairs_adapter.py      # 네 knob와 고정 nuisance 전달
    cubicasa_taguchi.py        # optional SEG-IR val adapter
  schemas/
    taguchi_run.schema.json
    outer_manifest.schema.json
tests/
  test_l9_orthogonality.py
  test_factor_units.py
  test_fast_score_parity.py
  test_cache_key_completeness.py
  test_meta_inverse_map.py
  test_zero_all_wall_sentinels.py
  test_no_within_cell_repetition.py
```

### 5.1 기존 도구 접속점

- `evidence_grid`: 각 run×drawing을 하나의 evidence row로 쓰고, PASS/INCONCLUSIVE/FAIL·sentinel·오류를 값으로 보존한다. 집계표만 남기지 않는다.
- `fast_score`: per-handle T-SYN과 optional CubiCasa scoring에 사용하되, reference scorer와 parity fixture가 일치해야 한다. parity 실패 시 빠른 점수만 믿지 않는다.
- `cubicasa_ir`: 기존 SEG-IR을 재생성하지 않고 frozen split/segment를 읽는 adapter다. train은 P2에서 사용하지 않는다.
- `cubicasa_ml`: P2 학습 모듈이 아니라 v1과 HistGradientBoosting comparator 결과를 같은 report schema에 연결하는 읽기 전용 접점이다.

### 5.2 구현 순서와 완료 정의

1. factor/unit contract와 L9 orthogonality test.
2. outer manifest builder와 firm leakage validator.
3. T-META canonical mapping·sentinel·S/N unit tests.
4. `wall_pairs.py`/`fast_score` parity 및 cache key.
5. 1.dwg smoke와 baseline reference.
6. 5장 pilot, hard compute cap 봉인.
7. 40장 main, xlsx 원자료와 markdown summary 생성.
8. 필요 시 3×3 interaction follow-up.
9. named setting freeze 후 hold-out firm confirmation.

예상 개발 규모는 소형 로컬 DOE harness다. 새 detector나 GPU pipeline을 만들지 않는다. 구현 완료는 “코드가 돈다”가 아니라, manifest hash·360개 main cell 상태·모든 exclusion/error·effects table·sentinel 결과·hold-out 판정이 evidence xlsx와 서로 대조 가능한 상태다. 실패 셀을 누락하거나 재실행 평균으로 덮으면 완료가 아니다.

### 5.3 결과 스키마

최소 row schema는 다음과 같다.

```text
run_id, drawing_id_hash, firm_id_hash, split,
unit_scale, density_tertile, layer_convention,
angle_tol_rad, gap_lo, gap_hi, min_overlap_ratio, max_pairs_per_line,
meta_relation, applicable, n_reference_members, n_predicted_members,
meta_loss, sentinel_zero_pass, sentinel_all_recall,
syn_family, precision, recall, f1,
n_segments, n_candidates, n_emitted_pairs, cap_hits,
runtime_status, error_code, cache_key
```

effects table에는 `factor`, `level`, `eta_mean`, `raw_loss_mean`, `raw_loss_variance`, `delta`, `rank`, `active_by_2sigma`, `alias_warning`을 둔다. interactions table은 main L9 단계에서 모든 항목을 `UNRUN / NOT_IDENTIFIABLE_IN_L9`로 기록한다. 빈 칸으로 두지 않는다.

---

## 6. 실험 셀 정의

모든 “제안 임계값”은 해당 셀 실행 전에 프리레지스트리에 봉인한다. val은 개발·튜닝에만 쓰고, CubiCasa test는 최종 방법당 단발이다. 결정 셀은 시드가 없고 셀내 반복도 없다.

### C0 — 계약·baseline·절대/상대 gap preflight

- **가설**: 네 factor가 실제 코드 경로에 연결되고, angle/gap 단위가 일관되며, declared-unit absolute와 dimension-anchored 해석 중 하나를 outcome leakage 없이 고정할 수 있다.
- **지표**: factor perturbation smoke, reference scorer↔`fast_score` parity, unit/scale metamorphic consistency, sentinel, v1 baseline cache, firm metadata 완전성, A/B gap 해석의 30개 paired probe.
- **합격선**: 전달 trace에서 factor 값이 exact하게 일치하고, 각 factor를 식별하도록 만든 fixture에서 해당 predicate/cap이 변하며, scorer parity가 exact하고 firm-first split과 hold-out이 가능해야 한다. A/B는 scale/unit R-META band·sentinel eligibility·`2*sigma_drawing` paired-loss 규칙으로 하나를 고정한다. 일반 R-META outcome 개선은 wiring 합격의 근거가 아니다.
- **킬 조건**: rad/mm 계약 불명, fast/reference 불일치, firm 분리 불가, dimension anchor가 필요한데 만들 수 없음, sentinel harness 부재.
- **예산**: 로컬 CPU smoke, manifest 작성, A/C/D frozen baseline에서 `2 parameterizations × 3 gap levels × 5 drawings = 30`개 선행 비교. main 360회에는 포함하지 않는다.
- **시드**: 없음; content hash 순서.

### C1 — cheapest probe: L9 × 5장

- **가설**: 최소 표본에서도 사전 rank `gap > overlap > angle > max_pairs`의 방향 또는 명백한 plateau/폭발 신호가 보인다.
- **지표**: 45개 `L_META`, row별 mean/variance/S/N, candidate count, cap hit, sentinel, 오류.
- **합격선**: 45개 셀이 모두 상태를 갖고, 적어도 한 요인의 level span이 측정 해상도보다 크거나 명시적 plateau로 판정 가능해야 한다. 이 셀만으로 setting을 채택하지 않는다.
- **킬 조건**: 동일 cache key 비결정성, 반복적 compute abort, sentinel collapse, factor가 실제 점수 경로에 무영향인 wiring 오류.
- **예산**: 패킷상 목표 30분, 로컬 CPU·streaming IR. 시간 초과는 실제값으로 보고한다.
- **시드**: 없음. 5장은 미리 고정한 40장의 부분집합.

### C2 — 본선: L9 × development outer 40장

- **가설**: 네 주효과 중 적어도 하나가 `2*sigma_resid`를 넘으며, 평균이 비슷한 행 사이에서 도면 간 분산 차이가 존재한다.
- **지표**: 360개 R-META, equal-firm mean/variance, firm variance, STB S/N, level effects/rank/active, noise stratum별 descriptive breakdown, process counters.
- **합격선**: sentinel·recall hard gate 통과, aggregate R-META `<=0.02`, 그리고 선택 규칙에 따라 관측 robust row를 지명할 수 있어야 한다. active가 없더라도 정직한 plateau 판정은 유효 결과다.
- **킬 조건**: 전 grid plateau, 전 행 R-META `>0.10`, compute cap 때문에 특정 noise stratum이 체계적으로 빠짐, 또는 absolute/relative parameterization의 미해결 혼입.
- **예산**: 9×40=360 결정 평가, 로컬 CPU, 64GB RAM 내 streaming. GPU/DGX 없음.
- **시드**: 없음; 동일한 40장을 모든 run에 paired 적용.

### C3 — T-SYN collapse/secondary gate

- **가설**: R-META가 좋은 행이 wall recall을 버려 얻은 허위 최적은 아니며, F/M family에서 secondary F1이 치명적으로 붕괴하지 않는다.
- **지표**: family별 per-handle precision/recall/F1, LTB S/N, zero/all-wall sentinel, META×SYN disagreement table.
- **합격선**: 제안 recall floor `>=0.95`, sentinel 모두 통과. F/M F1은 행 비교의 2차 tie-break 정보지만 B1 FAIL 동안 독립 채택 근거가 아니다.
- **킬 조건**: R-META 우승 행의 collapse, S팩의 공허한 precision을 pooled F1로 사용, synthetic 결과로 outer FAIL을 덮음.
- **예산**: frozen synthetic pack의 결정 scoring, 로컬 CPU.
- **시드**: 없음.

### C4 — 활성 두 요인 3×3 완전요인 후속

- **가설**: L9에서 active인 두 요인의 효과 방향이 상호작용을 분리해도 유지된다.
- **지표**: 두 요인의 9조합별 R-META mean/variance/S/N, `drawing block + A + B + A×B` 모형의 interaction contrast, sentinel, 동일 outer breakdown.
- **합격선**: 최대 absolute interaction contrast가 C2의 `2*sigma_resid` 이내이고 주효과 방향이 역전되지 않으며, 선택 행이 C2 eligibility를 유지해야 한다. interaction이 `2*sigma_resid`를 넘더라도 새 관측 3×3 최적을 별도 설정으로 지명할 수는 있지만 L9 main-effect 청구는 폐기한다.
- **킬 조건**: interaction이 main effect를 뒤집음, 활성 요인이 둘보다 많아 3×3이 질문을 덮지 못함, L9가 가리킨 optimum이 interaction follow-up에서 사라짐.
- **예산**: 필요한 경우에만 9설정. C2와 같은 개발 drawings를 쓰며 test는 열지 않는다. L27은 명시적 열 배치가 승인된 경우의 대안이다.
- **시드**: 없음.

### C5 — hold-out firm confirmation

- **가설**: 지명된 한 설정의 낮은 R-META와 낮은 분산이 selection에 쓰지 않은 firm에도 유지된다.
- **지표**: hold-out R-META band, STB S/N, drawing/firm variance, sentinel/recall, development firm leave-one-firm-out jackknife 범위.
- **합격선**: hold-out R-META `<=0.02`, sentinel/recall gate 통과, `eta_hold >= eta_dev - 2*SE_JK(eta)` 및 `Var_hold <= Var_dev + 2*SE_JK(Var)`를 모두 만족해야 한다. `SE_JK`는 development firm을 하나씩 제외한 leave-one-firm-out 값으로 계산한다. development firm이 이 계산을 지탱하지 못하면 분산 재확인은 INCONCLUSIVE다. 상태는 패킷대로 `PASS_WITH_DEFERRAL`; 한 hold-out 집합으로 보편성을 확정하지 않는다.
- **킬 조건**: hold-out R-META `>0.10`, 미사용 firm에서 반복 compute abort, 또는 분산이 development 범위를 넘어 firm-specific 과적합을 보임. `0.02–0.10`은 INCONCLUSIVE이며 PASS로 반올림하지 않는다.
- **예산**: named setting 하나만 hold-out drawings에 단독 실행. selection 재튜닝 금지.
- **시드**: 없음; firm은 C0에서 미리 고정.

### C6 — optional CubiCasa transport와 test 단발

- **가설**: archive에서 선택한 robust setting 또는 gap을 제외한 transportable 부분이 CubiCasa SEG-IR에서도 v1의 고재현·저정밀 패턴을 악화시키지 않는다.
- **지표**: val per-handle P/R/F1, R-META, scale-bin descriptive 결과, 기존 v1 `0.2358` 및 GBDT `0.517` comparator.
- **합격선**: px↔gap 계약이 먼저 봉인되고, val에서 sentinel/recall을 통과하며, 개선 주장을 하려면 P/R/F1을 모두 보고해야 한다. 단순 recall 유지나 물리 scale bin 무감만으로 성공 처리하지 않는다.
- **킬 조건**: label을 사용해 px scale을 역추정, val을 보고 factor/threshold를 다시 변경, FloorPlanCAD raster를 handle truth로 둔갑, counsel 미확인.
- **예산**: 기존 SEG-IR의 로컬 scoring. GPU/DGX 없음.
- **시드**: 없음. test는 C0–C5와 val 규칙을 모두 봉인한 뒤 프로그램이 P2를 정식 후보로 승인한 경우에만 한 번 실행한다.

---

## 7. red team 티켓 응답

패킷에 상세 내용이 드러난 티켓만 식별한다. 번호만 있고 원문이 없는 티켓의 내용을 추측해 해소했다고 주장하지 않는다.

| 티켓/공격 | P2에 대한 위험 | 응답 | 잔여 상태 |
|---|---|---|---|
| T1 / 공격 A, 대리 독립성 | T-META와 T-SYN이 같은 평행 이중선 prior를 공유하면 두 점수를 합쳐도 독립 증거가 아니다. | 두 점수를 결합하지 않고 동일 definition의 2×2 disagreement를 보고한다. R-META는 primary, R-SYN은 fidelity 통과 전 secondary다. CL-E/T17로 hand-off한다. | 부분 해소; 독립성 자체는 별도 실험 필요 |
| T2 / 공격 B, synthetic truth 부재·충실도 | B1이 이미 FAIL이며 현 합성팩 표현이 제한된다. | S/F/M을 collapse guard로만 사용하고, CL-C/PR-1 fidelity 통과 전에는 synthetic 우승을 채택 근거로 쓰지 않는다. | 위험 수용, 승격 보류 |
| T3/T4, E1 법의학·원시 아티팩트 | P2가 E1/silver 산출을 truth로 끌어오면 계측 아티팩트가 전파된다. | P2 core는 silver와 E1 판정자에 의존하지 않는다. CL-A 완료 전 silver를 objective에 넣지 않는다. | core에는 비적용; 프로그램 선결은 OPEN |
| T5 / 공격 D, 라이선스 | CubiCasa/FloorPlanCAD의 NC와 원 도면 권리 문제가 열린 상태다. | 로컬 145장 T-META core와 외부 데이터 arm을 분리한다. external arm과 학습은 counsel 서면 확인 전 보류한다. | OPEN, PR-3 의존 |
| T6 / 공격 E, 평가 단위 | pair/room 집합 성과와 per-handle truth를 섞으면 방법 간 시험지가 달라진다. | canonical per-handle membership을 primary로 고정하고 pair 수는 process metric으로만 둔다. 집합 조립은 별도 산출물이다. | 설계상 해소 |
| T7 / 공격 F, 0벽 탐지기 | 위반율만 최소화하면 abstaining detector가 PASS할 수 있다. | zero-wall·all-wall sentinel과 family recall floor를 S/N 전 hard gate로 둔다. empty-union 0은 gate 통과 후에만 인정한다. | 설계상 해소, 실제 실행 필요 |
| T9/T21, v0 baseline 선계측 | 개선량과 regression 기준이 없으면 L9 우승만 보고 과장한다. | v1의 실제 factor-unit 계약과 baseline reference를 C0에서 freeze한다. digest의 v1 angle 2°와 L9 rad 수준 차이도 명시적으로 검사한다. | 실행 전 OPEN |
| T12, quadratic 후보 폭발 | 최대 412,775 선분에서 naive pair 열거가 값싼 실험을 무너뜨린다. | orientation/spatial pruning, streaming, process counters, pilot 후 사전봉인 hard cap, `COMPUTE_ABORT` 보존. `max_pairs_per_line`을 계산량 cap으로 오인하지 않는다. | 구현·실측 필요 |
| T16, 절대 대 상대 gap | absolute mm가 unit convention 유물이면 B 요인 효과가 거짓이다. | outcome-free declared-unit 대 dimension-anchor preflight를 L9보다 먼저 수행한다. 상대화가 순위를 뒤집으면 원 absolute P2를 kill/redefine한다. | 가장 중요한 선행 OPEN |
| T17, truth-source 교차 | META와 SYN의 비대각 전이가 약할 수 있다. | P2 내부에는 disagreement matrix만 포함하고, train/eval truth-source 교차요인은 CL-E로 넘긴다. | 별도 실험 OPEN |
| T34, 인용 experiment status | 패널 인용의 R-레인이 실행되지 않았는데 실행 증거처럼 쓰일 수 있다. | 본 도시에의 문헌은 이론 계보로만 쓰고 프로그램 실측을 주장하지 않는다. 결과표는 모든 셀을 `UNRUN`에서 시작하고 실제 artifact가 생겨야 갱신한다. | 문헌 서지 요검증, 실험 status 정직 고지 |

추가로, 패널이 상세 번호를 제공하지 않았지만 P2에 직접 닿는 세 위험을 명시한다.

- **상호작용 청구서**: C2 interactions table은 전부 `UNRUN / NOT_IDENTIFIABLE_IN_L9`다. main effect rank를 인과적으로 clean하다고 쓰지 않는다.
- **평균 최적 오독**: row mean, drawing variance, firm variance, S/N을 모두 내고 near-optimal 내 최소분산 규칙으로 고른다.
- **randomization 오독**: 순수 결정 함수에 셀내 반복을 추가하지 않는다. 반대로 비결정성이 발견되면 그 자체가 preflight 실패다.

---

## 8. 인접 제안과의 관계 및 사망 조건

### 8.1 병합 가능 지점

- **CL-A E1 법의학 감사**: P2의 truth에는 직접 쓰지 않지만, 프로그램 전체의 잘못된 top-20/정렬 artifact를 먼저 제거하는 선결 작업이다. P2는 이를 방해하지 않고 독립 로컬 트랙으로 병행 가능하다.
- **CL-B 커버리지-완전 결정론 v1**: P2의 자연스러운 집이다. LWPOLYLINE/MLINE/ARC 정규화, INSERT transform 전개, 단위 정박 같은 representation fix가 먼저 고정되어야 knob 강건화의 의미가 있다. representation을 L9 도중 바꾸면 360셀이 같은 실험이 아니다.
- **feyerabend P2의 치수-정박 상대대역**: 경쟁안이 아니라 T16 preflight의 A/B다. relative가 이기면 original absolute-gap P2는 살아남는 것이 아니라 factor definition을 다시 등록한 새 버전이 된다.
- **CL-C WSD-EVAL-v1 / PR-1**: T-SYN을 collapse guard에서 정식 secondary truth로 승격시키는 조건이다.
- **CL-D metamorphic battery**: P2의 primary response provider다. sentinel/recall이 없는 위반율-only 버전은 사용하지 않는다.
- **CL-E truth-source 교차요인**: P2의 META×SYN disagreement를 더 큰 proxy-independence 실험으로 확장한다.
- **CL-F 고전 ML→PU→GNN**: P2가 plateau이거나 hold-out에서 죽을 때 hand-off 대상이다. 이미 HistGradientBoosting이 v1 F1보다 높은 val 성적을 보였으므로, 결정 knob가 의미 교란을 회수하지 못하면 Occam 순서상 고전 ML이 먼저다.
- **CL-G 래스터/VLM**: 직접 병합하지 않는다. exact raster↔handle 대응과 counsel을 통과한 뒤 fixed P2 설정을 벡터 gate로 사용할 수 있다.
- **CL-H RL**: per-handle knob 튜닝에는 RL이 필요 없다. P2의 deterministic outer evaluation은 오히려 RL 이전의 값싼 baseline/kill probe다.

### 8.2 차별점

P2는 새 truth를 만들지 않고, 새 representation을 만들지 않으며, 학습도 하지 않는다. 대신 같은 결정기를 여러 실제 noise conditions에 노출해 평균과 산포를 함께 판정한다. 이 때문에 가장 싸고, 가장 빠르며, “한 장 튜닝” 과적합을 직접 공격한다. 반대로 이 범위를 넘는 회수율이나 semantic lift를 주장하지 않는 것이 차별점의 절반이다.

### 8.3 이 제안이 죽어야 하는 조건

다음 중 하나면 P2의 현재 버전은 종료한다.

1. **hold-out firm 붕괴**: 지명 설정의 R-META가 `>0.10`이면 firm 관례 과적합으로 kill.
2. **전 grid plateau**: 모든 factor span이 active 기준 아래이고 평균·분산 차이가 실질적으로 없으면 knob tuning ceiling으로 kill, P1/P6/CL-F로 이관.
3. **collapse optimum**: R-META 최적이 zero/all-wall 또는 recall gate를 실패하면 허위 최적으로 kill.
4. **상호작용 역전**: 두 활성 요인의 3×3 후속에서 main-effect 방향이나 지명 설정이 뒤집히면 L9 결론을 kill하고 후속 설계만 유지.
5. **단위 유물**: dimension-anchored 해석이 absolute-mm 결과를 뒤집으면 original absolute P2를 kill하고 factor space를 재정의.
6. **표현공간 밖**: 단선/polyline/hatch 벽과 긴 비벽 평행 구조가 모든 설정에서 같은 오류를 유지하면 튜닝 주장을 kill하고 representation/learning으로 이관.
7. **cheapness 상실**: spatial pruning과 streaming 후에도 대형 도면이 반복적으로 compute cap을 넘어 outer strata가 빠지면 “가장 싼 실측” 가정을 kill.
8. **firm leakage/metadata 부재**: source-firm 분리와 hold-out을 증명할 수 없으면 robustness 일반화 주장을 kill.
9. **test discipline 위반**: CubiCasa test를 설정 동결 전에 보거나 여러 번 사용하면 그 test claim을 폐기.
10. **proxy ceiling**: META와 SYN이 같은 prior만 재확인하고 제3자 per-handle truth에서 개선이 없으면 결합 증거 주장을 kill.

### 8.4 정직한 최종 상태 계약

현재 effects table과 interactions table의 상태는 모두 `UNRUN`이다. 사전 rank는 `gap_range > min_overlap > angle_tol > max_pairs`라는 가설일 뿐 결과가 아니다. 실행 뒤에도 다음 중 하나만 허용한다.

- `ROBUST_SETTING_NAMED`: 모든 hard gate 통과, 관측 L9 row 지명, hold-out은 별도 대기.
- `PASS_WITH_DEFERRAL`: hold-out firm에서 PASS 밴드와 분산 재확인, 그러나 더 넓은 firm 일반화는 유보.
- `INCONCLUSIVE`: R-META가 `0.02–0.10`, noise coverage 부족, 또는 variance confirmation 불충분.
- `PLATEAU_KILL`: 결정 knob가 실질적으로 무효.
- `HOLDOUT_FAIL`: hold-out firm에서 `>0.10`.
- `BLOCKED_PRECONDITION`: 단위·firm·truth mapping·sentinel·compute contract 중 하나를 증명하지 못함.

이 상태 계약이 P2의 실제 산출물이다. 어떤 경우에도 실행 전 effects/interaction을 채우거나, 실패를 PASS로 바꾸거나, `1.dwg` 한 장의 시각적 인상으로 outer population 결과를 덮지 않는다.

DOSSIER_COMPLETE: doe_P2
