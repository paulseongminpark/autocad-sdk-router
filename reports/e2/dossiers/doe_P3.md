# doe_P3 도시예 — TRUTH-SOURCE VALIDITY CROSS-FACTORIAL

> 상태: **설계 완료 / 실험 UNRUN**  
> 표적: 학습 정답원과 평가 정답원의 교차 상호작용으로 “벽 의미”가 아니라 정답원 고유의 버릇을 학습했는지 판별  
> 확인 실행: **PASS_WITH_DEFERRAL** — 최적 전이쌍은 hold-out firm에서 재실행하되, firm 식별 메타데이터와 라이선스 게이트가 확인되기 전에는 실행 완료로 승격하지 않는다.  
> 수치 규율: 아래의 관측 수치는 패킷의 2026-07-18 실측 다이제스트에서만 가져왔다. 그 밖의 숫자는 산술적으로 설계에서 따라 나오거나, 명시적으로 “도시예 제안값(실측 아님)”이라고 표시한 프리레지스트레이션·예산 값이다.

## 1. 이론적 근거·선행연구

### 1.1 이 실험이 실제로 추정하려는 것

사람 라벨을 새로 만들지 않는 조건에서 합성 진리, 외부 제3자 진리, silver 진리는 모두 “참” 자체가 아니라 서로 다른 측정 장치다. 동일한 모델이 어느 장치로 학습했는지에 따라 어느 장치에서만 잘 보인다면, 관측된 성능은 벽 의미의 일반화와 정답원 특이적 적합을 합친 값이다. 따라서 이 도시예의 일차 추정량은 개별 셀의 최고 점수가 아니라 다음 두 양이다.

1. **운영 전이 효과**: 정답원 번들(라벨 규칙 + 도면 모집단 + IR 변환기) A로 맞춘 모델이 정답원 번들 B에서 얼마나 손실되는가.
2. **동일 항목 정답원 효과**: 같은 canonical entity에 여러 정답원을 겹쳐 적용했을 때도 불일치가 남는가. 이것이 있어야 운영 전이 효과를 단순 도메인 이동이 아니라 정답원 습관과 연결할 수 있다.

완전교차 `train_truth × eval_truth`의 `A×B` 상호작용은 첫 번째 양을 추정한다. 별도의 same-item bridge는 두 번째 양을 추정한다. 둘 중 하나만으로 “어느 정답원이 진짜인가”를 판정하지 않는다. 특히 T-SYN, T-EXT, T-SILVER가 원래 서로 다른 항목 집합에만 존재하면 `A×B`는 정답원과 모집단을 분리하지 못한다. 이 점을 숨기지 않고, 공통 canonical drawing에서 네 평가 계약을 파생시키는 paired bridge를 필수 구성으로 둔다.

### 1.2 방법론 계보

- **요인실험과 추정가능한 상호작용**: Fisher/Yates 계열의 factorial design, Box–Hunter–Hunter의 효과·상호작용 해석, Montgomery의 완전요인 설계가 직접적인 통계적 계보다. 이 도시예는 fraction을 쓰지 않으므로 A main, B main, `A×B`가 alias 없이 추정된다. C까지 두 수준으로 모두 실행하면 `A×B×C`도 별도로 추정된다. 이 문헌은 설계 원리의 일반 지식이며 E2에 대한 실측 근거가 아니다.
- **dataset bias와 shortcut learning**: Torralba & Efros의 *Unbiased Look at Dataset Bias*, Geirhos 등 저자의 *Shortcut Learning in Deep Neural Networks*, WILDS 벤치마크(Koh 등)는 in-domain 성능이 의미 개념의 일반화를 보장하지 않는다는 계보다. 여기서 합성 생성기의 산술적 tell, silver 판정자의 어휘·판정 습관, 외부셋 변환기의 클래스 규칙이 shortcut 후보가 된다.
- **domain generalization의 정직한 비교**: Gulrajani & Lopez-Paz의 *In Search of Lost Domain Generalization*은 모델 선택·공정한 프로토콜이 알고리즘 이름만큼 중요하다는 계보다. 이 도시예가 동일 IR, 동일 feature contract, 동일 튜닝 예산, 고정 threshold를 강제하는 이유다.
- **weak supervision과 annotator dependence**: Dawid–Skene의 관찰자 오류 모형과 Snorkel(Ratner 등)의 labeling-function 결합은 여러 약한 정답원을 독립 투표로 세지 말고 상관 구조를 모형화해야 한다는 계보다. 실측에서 silver 판정자 다섯 기가 약 두 어휘 가문으로 갈렸으므로, 다섯 표를 다섯 독립 반복으로 취급하지 않는다.
- **metamorphic testing**: 명시적 정답이 부족할 때 입력 변환과 출력 관계를 시험하는 metamorphic testing 계보를 따른다. Chen 등의 초기 metamorphic testing 서지 세부는 **요검증**이다. E2에서는 강체변환, 단위, scale, explode, 레이어 개명과 sentinel을 평가 전용 T-META 계약으로 만든다.
- **construct validity와 measurement invariance**: 하나의 proxy가 표적 개념을 완전히 대표하지 않는다는 측정이론의 원리를 적용한다. 여러 proxy의 합의가 유효하려면 공통된 prior 때문에 생긴 상관이 아니라 조건부 독립 또는 적어도 측정 가능한 불일치 구조가 있어야 한다.

이 문헌들은 왜 교차검증이 필요한지를 설명할 뿐, E2 성능 수치를 제공하지 않는다. 웹 검색은 사용하지 않았고, 확신이 낮은 서지 세부는 위와 같이 요검증으로 남겼다.

### 1.3 현재 관측이 요구하는 질문

패킷의 관측상 CubiCasa5k에서 기하 탐지기 v1은 validation F1 `0.2358`이고, 같은 여섯 특징의 HistGradientBoosting은 validation F1 `0.517`, AUC `0.9215`다. 이 향상은 유망하지만 T-EXT의 Wall 정의에 맞춘 향상인지, 벽 의미로 전이되는 향상인지는 아직 모른다. 반대로 합성팩은 충실도 게이트 B1이 `KS 0.5792`, `TV 0.265`로 FAIL이고, scale 불변성 팔은 `0.7624`로 FAIL이다. 따라서 대각 성능만 다시 재는 것은 이 제안의 성공이 아니다. `T-EXT→T-EXT`의 높은 값과 함께 `T-EXT→T-SYN`, `T-EXT→T-SILVER`, `T-EXT→T-META`를 같은 계약으로 보아야 한다.

silver 축도 독립 진리로 가정하지 않는다. 탐지기와 AI 판정자의 Pearson은 `0.2911`이고 name-blind 팔과 full 팔은 `1.0`으로 같았지만, 이것은 두 축이 다르다는 신호이지 silver의 정확성 증명은 아니다. 더욱이 다섯 판정자가 약 두 가문이므로 family-blocked 반복이 필요하다.

### 1.4 반증 가능한 주장

- 대각은 높고 비대각은 크게 낮다는 `A×B`가 관측되면 “단일 proxy로 충분하다”는 주장을 반증한다.
- 대각과 비대각의 차이가 프리레지 임계 이내이며 T-META와 hold-out firm에서도 유지되면, 적어도 “정답원 번들 하나에만 갇힌 모델”이라는 강한 반론은 약해진다.
- 대각 자체가 null보다 낫지 않으면 그 정답원은 학습 가능한 신호로 자격이 없다.
- 모든 비대각이 무너지면 어느 단일 정답원도 부트스트랩 사슬을 닫지 못한다. 이 경우 결론은 최고 정답원을 억지로 고르는 것이 아니라 새 정답원 또는 사람 라벨 조달이다.
- 이 실험은 정답원 간 전이와 불일치를 재지만 외부 절대 진리 없이 “누가 참인지”는 답하지 않는다.

## 2. 알고리즘 정확 스펙

### 2.1 기호와 고정 요인

- `A=train_truth ∈ {T-SYN, T-EXT, T-SILVER}`.
- `B=eval_truth ∈ {T-SYN, T-EXT, T-SILVER, T-META}`.
- `C=model_family ∈ {deterministic-tuned, learned}`.
- 완전교차 core는 `3×4×2 = 24` 논리 셀이다. 동일 A·C 모델을 네 B에 재사용하므로 unique fit은 기본적으로 여섯 종류지만, learned seed와 silver 반복은 fit 내부 반복으로 중첩된다.
- 평가의 독립 단위는 handle 수가 아니라 **drawing**이다. handle은 drawing 안에 중첩된다. firm 식별자가 실제로 확인되면 firm을 최상위 block으로 쓴다. 확인되지 않은 firm 이름을 추정하거나 파일명으로 꾸미지 않는다.
- 모든 셀은 동일한 frozen SEG-IR schema와 동일 canonical entity key를 사용한다. 좌표계, 단위, handle mapping, source label, source version, document group, generator seed, silver family·repeat를 manifest 필드로 요구한다.

### 2.2 정답원 어댑터

**T-SYN.** 생성 시점의 construction intent에서 `wall_member(h)∈{0,1}`를 낸다. 학습과 평가는 generator seed family를 분리한다(`L-SEED`). 현재 합성팩은 B1 FAIL이며 S팩 채점 우주에는 음성이 없으므로, S팩 단독 F1은 일차 응답으로 금지한다. 양성과 음성이 함께 있고 real entity-type/fragmentation 분포에 대한 충실도 게이트를 통과한 확장팩만 confirmatory T-SYN이 된다. 그 전 실행은 `PREQUALIFICATION_ONLY`다.

**T-EXT.** CubiCasa SEG-IR의 Wall 클래스 요소 모서리를 canonical segment/handle로 변환한 제3자 라벨이다. 원본 floorplan id 기준으로 train/validation/test를 고정하고, coordinate/axis/scale round-trip을 먼저 검사한다. 도면별 축척이 미상인 px 좌표를 mm로 가장하지 않는다. 라이선스상 T-EXT 학습 산출물은 방법 검증용이며 제품 weight로 반출하지 않는다.

**T-SILVER.** 판정자 출력을 hard majority 한 표로 축약하지 않는다. 먼저 같은 canonical handle에 대한 각 판정자의 확률 또는 이진 출력을 모은 뒤 어휘 가문 안에서 평균하고, 두 family mean을 동등 가중한다. 즉 판정자 수가 아니라 family가 독립 단위다. 학습 silver와 평가 silver는 prompt template, sampling repeat, document split을 분리한다. 세 번의 silver 생성 반복은 내재 잡음 반복이며, 세 번을 서로 다른 도면처럼 세지 않는다. silver 자격 게이트가 실패하면 해당 `R-SILVER`는 수치 0이 아니라 `UNQUALIFIED`다.

**T-META.** 평가 전용이며 train diagonal을 만들지 않는다. 변환 `g` 뒤의 예측을 inverse map으로 원 canonical handle에 되돌려 원예측과 비교한다. 강체변환, 단위, scale, explode, 레이어 개명을 포함하되, 변환별 mapping loss 자체를 모델 오류와 분리한다. zero-wall/all-wall sentinel과 recall 최저선 계약을 먼저 통과해야 consistency measure를 공개한다. 상수 0 예측처럼 변환에는 완벽히 일관되지만 벽을 찾지 않는 모델은 gate에서 탈락한다.

### 2.3 공통 입력·출력 계약

입력 drawing `d`의 handle `h`마다 다음 feature vector를 만든다.

`x(d,h) = [parallel, thickness_or_normalized_gap, junction, log_length, sin(2θ), cos(2θ), optional_layer]`

learned family의 본선 비교는 기존 CubiCasa ML과 맞춘 여섯 기하 특징만 사용하며 `optional_layer`는 항상 mask한다. deterministic family는 기존 네 증거 채널을 쓰되 layer 채널을 별도 ablation으로 봉인한다. 이는 external IR의 레이어 중립성과 내부 도면의 layer naming 차이가 정답원 효과로 섞이는 것을 막는다. 출력은 모든 family에서 `p(d,h)∈[0,1]`과 frozen threshold `τ_A,C`에 의한 `ŷ(d,h)`다.

거대 drawing 하나가 목적함수를 지배하지 않도록 각 drawing의 총 sample weight를 동일하게 하고, 그 안에서 양·음 class weight를 계산한다. 최대 도면정의가 `412,775` 선분인 관측을 고려해 feature extraction과 scoring은 drawing 단위 chunk로 스트리밍한다.

### 2.4 두 모델 계열

**deterministic-tuned.** 기존 v1의 `fast_score`를 순수 함수로 유지하고, A의 development split에서만 노브를 선택한다. 현재 중심값은 패킷의 v1 설정인 채널 가중치 `0.35/0.25/0.20/0.20`, 두께 `50–400 mm`, 각도 `2°`, overlap `0.5`, snap `6 mm`다. 아래 탐색 범위는 모두 **도시예 제안값(실측 아님)**이다.

- 비음수 네 채널 가중치의 합을 1로 제한하고 `0.05` 격자에서 탐색한다.
- 각도 허용 `{1°, 2°, 4°}`, overlap `{0.25, 0.50, 0.75}`, snap `{3, 6, 12 mm}`를 후보로 둔다.
- 두께 표현은 `{현재 절대 mm 대역, 도면 치수에 정박한 상대 대역}` 두 팔로 둔다. px-only drawing에서는 절대 mm 팔을 강제로 비활성화한다.
- threshold `τ`는 `{0.30, 0.40, 0.50, 0.60, 0.70}`에서 A-development만으로 선택한다.
- 목적함수는 아래 drawing-macro Brier skill이며, 동률이면 파라미터 수가 적고 현재 v1 중심값에 가까운 후보를 택한다.

**learned.** 기존 `cubicasa_ml`의 HistGradientBoosting 여섯 특징을 공통 최소 계열로 사용한다. weighted binary log-loss를 최소화하며 T-SILVER에서는 soft target의 expected log-loss를 쓴다. 아래 공간과 seed 수는 모두 **도시예 제안값(실측 아님)**이다.

- `learning_rate ∈ {0.03, 0.10}`
- `max_leaf_nodes ∈ {15, 31, 63}`
- `max_depth ∈ {None, 6, 12}`
- `min_samples_leaf ∈ {20, 100, 500}`
- `l2_regularization ∈ {0, 1, 10}`
- `max_iter ∈ {100, 300}`
- 미리 고정한 Sobol 순서의 앞 `48`개 configuration만 모든 A에 똑같이 허용한다. 모델 seed는 `{17, 43, 89}`를 쓰며 셀 실행 순서만 무작위화한다.

로지스틱은 패킷에서 F1 `0.053`으로 선형 불충분이 관측되었으므로 본선 C 수준으로 추가하지 않고, learned pipeline sanity baseline으로만 같은 manifest에 남긴다. GNN·DL을 추가하면 C의 의미가 바뀌므로 이 도시예의 confirmatory core에는 넣지 않는다.

### 2.5 학습·평가 의사코드

```text
freeze(schema, IR_cache, split_manifest, source_versions, transforms)
assert no_overlap_by(document_id, firm_id_if_present, generator_seed_family)

for A in [T-SYN, T-EXT, T-SILVER]:
    qualify_train_source(A) or mark all cells with this A as UNQUALIFIED
    for C in [deterministic-tuned, learned]:
        for train_repeat in repeats_required_by(A, C):
            train_data = load(A, split="fit", repeat=train_repeat)
            dev_data   = load(A, split="development", disjoint=True)
            model, threshold = fit_or_tune(C, train_data, dev_data)
            freeze(model, threshold)

            for B in randomized_eval_order_if_learned([SYN, EXT, SILVER, META]):
                qualify_eval_source(B) or emit UNQUALIFIED
                audit = load_locked_30_drawing_bridge(B)
                pred  = score_in_chunks(model, audit)
                result = evaluate_with_source_contract(B, pred, threshold)
                write_cell_evidence(result, drawing_clusters, repeat_ids)

fit preregistered A * B * C model on drawing-level responses
compute diagonal/off-diagonal contrasts only for B in [SYN, EXT, SILVER]
report T-META as evaluation-only interaction arm with no invented diagonal
run the single frozen confirmation pair on hold-out firm if metadata gate passes
```

### 2.6 응답, 정규화, 게이트

라벨형 평가원 `B∈{SYN,EXT,SILVER}`에서 drawing `d`의 Brier loss를

`BS_d = (1/|H_d|) Σ_h (p_dh - y_dh)^2`

로 둔다. silver의 `y`는 family-blocked soft target이다. B의 development population에서 미리 고정한 prevalence-only predictor의 loss를 `BS_null,B`라 하고, 평가 응답을

`R_B(a,b,c) = 1 - mean_d(BS_d) / BS_null,B`

로 둔다. 이것은 source별 null을 0, 완전 예측을 1로 맞춘 skill score이며 음수도 그대로 보존한다. 추론 단계에서는 clip하지 않는다. thresholded precision, recall, F1, AUC는 패킷의 기존 결과와 연결하기 위한 보조 지표이고, threshold를 B에 맞춰 다시 조정하지 않는다. drawing에 양성이 없을 때 F1을 임의로 1로 만들지 않으며 Brier와 별도의 sentinel 표에 기록한다.

T-META에서는

`R_META = 1 - weighted_mean_{d,g,h} |p(d,h) - inverse_g(p(g(d),g(h)))|`

를 measure로 쓰되, mapping completeness, zero/all-wall sentinel, recall-floor gate가 전부 PASS일 때만 유효하다. trivial constant prediction이 sentinel에 걸리면 `R_META`를 순위에 넣지 않는다.

각 응답은 반드시 `{gate_status, measure, source_version, drawing_n, repeat_structure}`를 함께 가진다. gate 실패를 낮은 점수로 숫자화하지 않는다. 이는 “계측 불능”과 “모델 실패”를 분리하기 위해서다.

### 2.7 표적 대비와 판정 규칙

T-META에는 train source가 없으므로 대각 대비는 라벨형 세 평가원에서만 정의한다. 평가원 `b`의 대각은 `R_b(b,b,c)`이고, 다른 학습원 `a`의 전이 낙폭은

`Drop_{a→b,c} = R_b(b,b,c) - R_b(a,b,c)`.

계열별 평균 낙폭은

`Δ_c = (1/3) Σ_{b∈{SYN,EXT,SILVER}} [R_b(b,b,c) - (1/2)Σ_{a≠b}R_b(a,b,c)]`

이고, 두 계열을 동등 가중한 `Δ=(Δ_det+Δ_learned)/2`가 일차 대비다. 산술 계수는 factor 수준 수에서 직접 따라온다. 프리레지 임계는 패킷대로 **정규화 skill score의 절대 20 percentage-point**, 즉 `0.20`이다. “상대 20%”로 사후 재해석하지 않는다.

- `Δ > 0.20`: `TRUTH_SOURCE_SPECIFIC_OVERFIT`.
- 특히 `Drop_{T-SYN→T-EXT,c} > 0.20`: 합성 학습이 실무 외부 진리로 이어지지 않는 핵심 벽.
- 대각 `R_b(b,b,c) ≤ 0`: 해당 정답원·계열은 frozen null보다 낫지 않으므로 `DIAGONAL_FAIL`.
- 모든 source qualification과 leakage gate가 PASS이고, `Δ` 및 핵심 `T-SYN→T-EXT` 낙폭의 drawing/firm cluster-bootstrap 상한이 `0.20` 이하이며, T-META strict gate와 confirmation이 유지될 때만 `CHAIN_CLOSURE_SUPPORTED`.
- 점추정이 임계 아래지만 불확실성 상한이 임계를 넘으면 `INCONCLUSIVE`, PASS로 올리지 않는다.

bootstrap 신뢰구간은 firm이 있으면 firm, 없으면 drawing을 재표집한다. handle bootstrap은 금지한다. 신뢰수준과 반복수는 **도시예 제안값(실측 아님)**으로 `95%`, `2,000`회에 봉인한다. p-value보다 효과량과 임계 대비 불확실성을 우선한다.

### 2.8 요인모형과 alias

drawing-level 응답에 다음 fixed-effect model을 맞춘다.

`R = μ + A + B + C + A:B + A:C + B:C + A:B:C + block + ε`.

firm metadata가 검증되면 `block`에 firm random intercept를 넣고 drawing을 그 아래 반복축으로 둔다. silver repeat는 source-noise random effect, learned seed는 model-noise random effect로 중첩한다. 24셀을 모두 실행하므로 A·B·C main, 모든 2원 상호작용, `A×B×C`는 alias 없이 추정된다. C를 일부만 실행하는 축소안은 exploratory로만 허용하며 confirmatory `A×B` 표에서는 C를 평균내지 않는다. fraction은 사용하지 않는다.

## 3. 벽 과업 적응 설계

### 3.1 paired 30-drawing bridge

각 논리 셀의 평가 cohort는 패킷대로 30 drawing이다. 이 숫자는 실측 표본수가 아니라 패킷에 봉인된 설계 크기다. 정답원과 모집단을 가능한 한 분리하기 위해 다음과 같이 동일 canonical base id를 공유한다.

1. CubiCasa validation에서 development에 사용하지 않은 30 drawing id를 먼저 잠근다. test 400은 이 단계에서 열지 않는다.
2. 같은 30개에 대해 T-EXT는 frozen Wall-edge label을 제공한다.
3. 외부 label을 판정자 입력에서 완전히 가린 뒤 동일 drawing을 silver 판정자 두 family가 세 반복으로 판정해 T-SILVER를 만든다.
4. 동일 SEG-IR에 변환 battery를 적용해 T-META를 만든다.
5. canonical geometry와 entity provenance를 보존한 paired synthetic rendering/perturbation을 만들어 T-SYN label을 construction intent에서 얻는다. 외부 Wall label의 단순 복사를 T-SYN이라고 부르지 않는다. 생성기가 독립 distractor와 wall/non-wall construction을 실제로 만들고 B1 fidelity gate를 통과해야 한다.

이 bridge는 완전한 인과 분리를 보장하지 않는다. 특히 synthetic rendering은 여전히 domain intervention이다. 따라서 결과를 두 층으로 보고한다.

- 원 도메인별 24셀: 실제 배포 관점의 **source-bundle transfer**.
- paired canonical id subset: 모집단을 맞춘 **same-item disagreement/transfer**.

두 층이 같은 방향일 때만 “정답원 습관” 해석을 강화한다. 서로 다르면 domain/adapter confounding으로 결론을 낮춘다.

### 3.2 CubiCasa SEG-IR 벡터축

CubiCasa5k는 5,000도면이 전량 변환되었고 train `4,200`, validation `400`, test `400`, 벽 선분율이 약 `11.8%`인 유일한 제3자 사람 라벨 축이다. 기존 split을 바꾸지 않는다.

- T-EXT fit은 train에서만, 하이퍼파라미터와 threshold는 validation development 부분에서만 선택한다.
- locked bridge 30개는 validation에서 먼저 격리하고 어떤 A의 튜닝에도 쓰지 않는다.
- test는 방법별 frozen artifact의 단발 confirmation에만 쓴다. 셀 표를 보고 threshold를 고친 뒤 test를 재채점하지 않는다.
- coordinate px를 mm로 변환하지 않는다. 벽두께 px 중앙값 `22`는 기술 통계로만 보존하고 물리 prior로 쓰지 않는다. 실제로 v1 성능이 축척 `2–15 mm/px` 구간에서 무감했고 최소길이 필터의 천장 F1이 `0.335`였으므로, P3에서는 length/thickness 노브 개선을 truth-source validity와 혼합하지 않는다.
- T-EXT train arm weight는 NC 조건의 방법 검증 산출물이다. counsel 확인 없이는 제품 후보 registry로 복사하지 않는다.

v1 `0.2358`과 HGB `0.517`의 차이는 이 도시예의 출발점이지 새 결과가 아니다. P3가 가져오는 추가 가치는 HGB의 이득이 T-EXT 대각에만 존재하는지, 다른 진리와 metamorphic 계약으로도 이동하는지를 판별하는 것이다. P3 자체는 F1을 더 높이는 모델 제안이 아니다.

### 3.3 합성 벡터축

현재 합성팩의 per-handle 결과만 보면 F·M precision이 각각 `0.9315`, `0.8669`, recall은 모두 `1.0`이지만 B1 fidelity는 FAIL이고 S팩에는 음성이 없다. 그러므로 이 수치로 T-SYN 자격을 선언하지 않는다.

- generator는 LINE/LWPOLYLINE/INSERT에 갇힌 현재 분포를 넘어 실도면의 SPLINE/ARC/HATCH 혼재, block transform, 비평행 조각, long parallel distractor를 포함해야 한다.
- train generator seed와 bridge/eval seed는 disjoint family로 관리한다.
- 생성 산술에서 직접 드러나는 entity order, exact gap, layer name, handle range, insertion order는 모델 feature에서 mask하고 별도 tell audit를 낸다.
- S팩은 positive sentinel, F/M과 확장팩은 측정 cohort로 역할을 분리한다.
- B1이 통과하기 전 cheap probe는 파이프라인·상호작용 코드의 소각이지 진리 유효성 판결이 아니다.

### 3.4 1.dwg 실도면축과 T-SILVER/T-META

1.dwg staged DXF에는 도면정의 384개가 있지만 이것은 384개의 독립 firm/drawing population이 아니다. 따라서 블록 정의를 독립 drawing처럼 부풀리지 않는다. 이 축은 다음 용도로만 쓴다.

- source-qualified 모델의 real-CAD stress probe.
- T-SILVER family disagreement와 세 생성 반복의 variance 확인.
- T-META에서 handle-preserving 변환과 mapping 정확성 확인.
- document-level descriptive result. firm-level 일반화 추론은 금지.

실도면에서 벽-제로 도면율이 `0.682`에서 `0.2135`로 개선되어 밴드를 통과한 관측과, silver와 탐지기의 Pearson `0.2911`은 context로 보고하되 이 한 문서에서 30-drawing confirmatory cohort를 만들었다고 주장하지 않는다.

### 3.5 FloorPlanCAD 래스터축

FloorPlanCAD는 래스터 5,308장과 wall bbox/segmask가 있지만 벡터 SVG가 없다. 따라서 pixel mask를 임의의 CAD handle 정답으로 투영하면 source effect와 projection error가 섞인다.

- core 24셀에는 바로 넣지 않는다.
- 먼저 synthetic exact harness에서 rasterize→predict→inverse project가 canonical wall entity를 보존하는지 검사한다.
- exact projection gate가 통과하면 동일 모델 출력의 raster-side secondary evaluation으로만 추가한다. factor 수준을 사후에 하나 더 늘리지 않는다.
- 실패하면 FloorPlanCAD는 T-EXT 대체물이 아니라 별도 CL-G 입력으로 hand-off한다.

### 3.6 leakage 방지

- `L-FIRM`: 실제 firm/project origin 필드가 있는 경우 그 단위로 split한다. 필드가 없으면 `FIRM_UNKNOWN`을 기록하고 hold-out firm 확인을 실행 완료로 부르지 않는다.
- `L-SEED`: 합성 generator seed family, template ancestry, mutation family를 train/eval 사이에서 분리한다.
- `L-DOC`: CubiCasa original floorplan id와 1.dwg document id가 split을 넘지 않는다.
- `L-LABELER`: silver train/eval prompt, sampling repeat, family role을 분리한다. 같은 raw silver 응답을 학습과 평가에 재사용하지 않는다.
- `L-IR`: cache IR과 adapter version을 freeze하고 hash를 evidence에 기록한다. eval B를 보고 재변환하지 않는다.
- `L-THRESHOLD`: threshold는 A-development에서 한 번 고정하며 B별 최적 threshold를 허용하지 않는다.
- `L-TEST`: test는 frozen method당 단발이다. 오류 수정 후 같은 결과를 덮어쓰지 않고 해당 method를 실패로 기록한다.
- label shuffle control을 A·C마다 동일 budget으로 실행한다. real과 shuffled가 drawing-cluster uncertainty 안에서 구분되지 않으면 leakage/learnability gate를 FAIL한다.

## 4. 데이터·컴퓨트 요구

### 4.1 필수 데이터와 선결 게이트

| 자산 | 사용 | 현재 알려진 상태 | 실행 전 조건 |
|---|---|---|---|
| CubiCasa SEG-IR | T-EXT train/eval, paired bridge canonical base | 전량 변환 성공, 고정 train/val/test 존재 | NC counsel 서면, coordinate round-trip, locked validation 30, test 봉인 |
| 합성 S/F/M 및 확장 generator | T-SYN train/eval | per-handle 일부 강하나 B1 fidelity FAIL, S 음성 없음 | B1 자격, 양·음 공존, seed ancestry 분리, arithmetic tell audit |
| silver 판정자 | T-SILVER train/eval | 다섯 기가 약 두 family | family-blocked aggregation, 세 독립 생성 반복, train/eval raw response 분리, silver 자격 게이트 |
| metamorphic battery | T-META eval | 강체·단위는 PASS, scale 팔 FAIL, strict sentinel FAIL 기록 | mapping oracle, scale 원인 분리, zero/all-wall sentinel, recall-floor 계약 |
| 1.dwg staged DXF | real CAD stress probe | 단일 문서, 큰 definition 존재 | 독립 population으로 과대계수 금지, descriptive block 처리 |
| FloorPlanCAD | raster secondary | mask/bbox는 있으나 vector SVG 없음 | exact pixel↔entity projection harness 전에는 core 제외 |

어느 source gate든 실패하면 관련 셀은 `UNQUALIFIED`이며 결측을 평균 0으로 넣지 않는다. 세 라벨형 source가 모두 qualified되지 않으면 일차 `Δ`를 계산하지 않는다.

### 4.2 로컬 실행 계획

현재 RTX 5070 Ti 16GB, RAM 64GB에서 core는 완주 가능하도록 설계한다.

- deterministic-tuned 12셀은 CPU `fast_score`와 `evidence_grid`로 실행한다. 모델 fit은 사실상 노브 탐색이고 반복은 drawing population이다.
- learned 12셀은 기존 여섯 특징 HistGradientBoosting을 CPU/RAM으로 학습한다. 386만 train segment를 한꺼번에 복제하지 않고 memory-mapped feature block과 drawing-balanced sample weight를 쓴다.
- `412,775` segment급 definition은 chunk scoring하며 cell 결과는 drawing aggregate가 끝난 뒤만 메모리에 둔다.
- silver 생성만 비결정 반복을 갖는다. T-SILVER가 A이면 세 train label draw로 각각 fit/tune하고, B도 T-SILVER이면 세 eval draw와 전부 교차해 source-noise를 분리한다. 다만 이 아홉 조합을 아홉 독립 drawing으로 세지 않는다.
- learned model seed 세 개는 model-noise 반복이다. 셀의 논리 수는 24로 유지한다.

도시예의 로컬 계획 상한(모두 **실측 아님**)은 deterministic source별 튜닝 `2 CPU-hour`, learned source·seed별 fit `8 CPU-hour`, 30-drawing cell scoring `1 CPU-hour`, feature/cache 임시 저장 `200 GB` 이하다. 상한을 넘기면 데이터를 몰래 축소하지 않고 `RESOURCE_EXCEEDED`로 기록한다. 첫 신호는 패킷대로 deterministic 대각/비대각이며 며칠 내 산출을 목표로 하지만, 이는 일정 목표이지 완료 주장이나 실측 소요시간이 아니다.

### 4.3 DGX 계획

DGX Spark는 현재 unreachable이므로 core 성공 조건에서 제외한다. 로컬 HGB core가 끝난 뒤 learned×T-EXT의 대형 모델 확장만 DGX 후보로 둔다.

- DGX가 복구되어도 core의 모델 family 정의를 사후 교체하지 않는다.
- 대형 learned 모델은 별도 exploratory suffix로 기록하고 24셀 confirmatory 표에 섞지 않는다.
- 외부 NC label로 학습한 weight는 DGX나 제품 registry에 영구 탑재하지 않는다.
- DGX가 끝까지 불통이어도 core는 `BLOCKED`가 아니다. 반대로 로컬 core가 source gate에서 실패하면 DGX scale-up으로 구제하지 않는다.

### 4.4 증거 산출 계약

실행 시 각 셀은 evidence xlsx의 최소 열로 `cell_id, A, B, C, document_id, firm_id_status, handle_count, source_version, model_hash, IR_hash, train_seed, generator_seed_family, silver_family, silver_repeat, gate_status, R_B, P, R, F1, AUC, failure_reason`을 남긴다. 이 도시예 문서는 실행 계획이며 xlsx가 생성되었다고 주장하지 않는다. 실패도 동일 schema로 보존한다.

## 5. 구현 계획

### 5.1 제안 모듈·파일 골격

아래는 향후 구현 골격이며 이 도시예 작성 시 실제 파일을 만들었다는 뜻이 아니다.

```text
truth_crossfactorial/
  configs/doe_p3.yaml                # factor, split, threshold, seed 봉인
  schema.py                          # canonical entity/source/evidence schema
  source_adapters.py                 # SYN/EXT/SILVER label adapters
  paired_bridge.py                   # 동일 canonical id의 네 eval contract
  split_guard.py                     # L-FIRM/L-SEED/L-DOC/L-LABELER/L-TEST
  qualify_sources.py                 # B1, CRS, silver, META/sentinel gates
  train_deterministic.py             # evidence_grid + fast_score tuning
  train_learned.py                   # cubicasa_ml HGB, soft-label loss
  eval_labeled.py                    # Brier skill + frozen-threshold 보조지표
  eval_meta.py                       # inverse-map equivariance + sentinel
  analyze_interaction.py             # A*B*C model, prereg contrasts, bootstrap
  run_matrix.py                      # 24 logical cells, learned-only random order
  export_evidence.py                 # mandatory xlsx + markdown summaries
  tests/
    test_split_guard.py
    test_coordinate_roundtrip.py
    test_no_eval_threshold_tuning.py
    test_silver_family_blocking.py
    test_meta_constant_predictor_killed.py
    test_contrast_coefficients.py
```

### 5.2 기존 도구 접속점

- `evidence_grid`: deterministic candidate를 같은 budget으로 열거하고 선택 이력을 남긴다. B별 사후 탐색을 금지한다.
- `fast_score`: v1의 순수 함수 scoring backend. canonical feature order와 threshold를 wrapper에서 고정한다.
- `cubicasa_ir`: T-EXT canonical segment와 document split의 단일 진입점. px↔IR round-trip 감사도 여기에 연결한다.
- `cubicasa_ml`: 기존 여섯 특징 HGB를 learned 최소 계열로 재사용한다. drawing-balanced weight, soft silver target, frozen seed manifest만 얇은 adapter로 추가한다.

### 5.3 구현 순서와 완료 정의

1. schema·split manifest·source qualification을 먼저 구현한다.
2. paired bridge와 exact entity correspondence를 검증한다.
3. metric/contrast를 synthetic toy table로 단위검사한다. toy 값은 코드검사용이며 E2 실측 표에 섞지 않는다.
4. deterministic cheap probe를 실행한다.
5. 24셀 core와 nested repeat를 실행한다.
6. interaction/effects table과 mandatory xlsx를 한 번에 생성한다.
7. 가장 잘 전이된 frozen pair를 hold-out firm에서 단발 확인한다.

예상 개발 규모는 **도시예 계획값(실측 아님)**으로 중간 규모, 구현·단위검사 `4–6 engineer-day`, source qualification/bridge 감사 `2–4 engineer-day`, core orchestration·보고 `2–3 engineer-day`다. 데이터 조달과 counsel 대기시간은 포함하지 않는다.

완료는 “스크립트가 돈다”가 아니라 다음 전부다: 24셀 상태가 PASS/FAIL/UNQUALIFIED 중 하나로 닫힘, shuffle 및 sentinel 결과 존재, xlsx 존재, 대비 계수 검증, test 단발 로그, failure reason 비어 있지 않음, confirmation 상태가 사실대로 기록됨.

### 5.4 cheapest probe의 정확한 해석

패킷의 `T-SYN↔T-META 2×2 소각(4셀)`은 T-META를 학습 정답원으로 추가한다는 뜻으로 해석하지 않는다. factor 계약을 보존해 `A=T-SYN × B∈{T-SYN,T-META} × C∈{deterministic-tuned,learned}`의 네 셀로 실행한다. 각 셀은 locked 30-drawing이 아니라 개발용 소형 cohort로 plumbing만 확인할 수 있다. 현재 B1과 scale/sentinel이 FAIL이므로 결과 상태는 최대 `PREQUALIFICATION_ONLY`; 반나절 목표는 패킷의 계획값이지 이미 달성한 시간이 아니다.

## 6. 실험 셀 정의

### 6.1 공통 실행 규칙

- 각 논리 셀은 locked 30 drawing을 평가한다.
- deterministic 모델에는 model seed가 없다. T-SYN generator와 T-SILVER label generation의 seed/repeat만 기록한다.
- learned 모델은 제안 seed `{17,43,89}`를 모두 실행하고 셀 순서를 master seed `20260718`로 무작위화한다. 숫자는 프리레지 제안값이며 실측이 아니다.
- T-SILVER가 A 또는 B에 들어가면 세 생성 반복을 유지한다. train/eval silver raw draw는 분리한다.
- 라벨형 diagonal의 제안 합격선은 source gate PASS와 `R_b>0`. off-diagonal의 실질 합격선은 대응 대각 대비 낙폭 `≤0.20`; 불확실성 상한까지 `≤0.20`이어야 chain closure를 지지한다.
- T-META 셀에는 diagonal이 없다. strict gate PASS 후 `R_META`를 보고하고, transform별 최악 팔을 숨기지 않는다.
- 공통 kill은 source qualification 실패, split overlap, threshold의 B별 재튜닝, shuffle와 real의 미분리, evidence 누락이다.
- 셀별 시간은 계획 상한(실측 아님)으로 deterministic scoring `1 CPU-hour`, learned scoring `1 CPU-hour`; fit 비용은 A·C 공용이므로 셀에 중복 청구하지 않는다.

### 6.2 24셀 매트릭스

| Cell | C | A→B | 사전 가설 | 일차 지표·제안 합격선 | 셀 kill 조건 | 예산·시드 |
|---|---|---|---|---|---|---|
| D-SS | deterministic | SYN→SYN | 대각은 높을 수 있음 | `R_SYN>0`, gate PASS | B1/양음 gate 실패 또는 null 이하 | 30장, population; L-SEED |
| D-SE | deterministic | SYN→EXT | **핵심 벽**, 큰 낙폭 예상 | `Drop_SYN→EXT≤0.20` | 낙폭 `>0.20`, CRS/NC gate 실패 | 30장, population; L-SEED |
| D-SV | deterministic | SYN→SILVER | 합성 tell이면 낙폭 | `Drop_SYN→SILVER≤0.20` | 낙폭 `>0.20` 또는 silver 미자격 | 30장 × silver 3회 |
| D-SM | deterministic | SYN→META | 기하 규칙이면 불변성 유지 | META strict gate PASS, `R_META` 보고 | sentinel/mapping/scale strict FAIL | 30장, transform 반복 |
| D-ES | deterministic | EXT→SYN | 외부 정의의 역전이 확인 | `Drop_EXT→SYN≤0.20` | 낙폭 `>0.20` 또는 SYN 미자격 | 30장, population; L-SEED |
| D-EE | deterministic | EXT→EXT | 대각 학습가능성 확인 | `R_EXT>0`, gate PASS | null 이하, CRS/NC gate 실패 | 30장, population |
| D-EV | deterministic | EXT→SILVER | 두 real-domain proxy의 호환성 | `Drop_EXT→SILVER≤0.20` | 낙폭 `>0.20` 또는 silver 미자격 | 30장 × silver 3회 |
| D-EM | deterministic | EXT→META | 외부 최적화가 invariant인지 | META strict gate PASS, `R_META` 보고 | sentinel/mapping strict FAIL | 30장, transform 반복 |
| D-VS | deterministic | SILVER→SYN | silver 습관의 합성 전이 시험 | `Drop_SILVER→SYN≤0.20` | 낙폭 `>0.20` 또는 source gate 실패 | 30장 × train silver 3회 |
| D-VE | deterministic | SILVER→EXT | 큰 낙폭 예상, 두 번째 핵심 벽 | `Drop_SILVER→EXT≤0.20` | 낙폭 `>0.20`, NC/CRS gate 실패 | 30장 × train silver 3회 |
| D-VV | deterministic | SILVER→SILVER | 대각 높음 예상, family leakage 경계 | `R_SILVER>0`, disjoint-family gate | 같은 raw/family role 재사용 또는 null 이하 | 30장; train 3 × eval 3 |
| D-VM | deterministic | SILVER→META | silver distill이 기하 일관성 보존? | META strict gate PASS, `R_META` 보고 | sentinel/mapping strict FAIL | 30장 × train silver 3회 |
| L-SS | learned | SYN→SYN | 학습계열 대각 높음 예상 | `R_SYN>0`, gate PASS | B1/양음 gate 실패, shuffle 미분리 | 30장 × model seed 3; L-SEED |
| L-SE | learned | SYN→EXT | **핵심 벽**, shortcut이면 최대 낙폭 | `Drop_SYN→EXT≤0.20` | 낙폭 `>0.20`, shuffle/CRS/NC FAIL | 30장 × model seed 3 |
| L-SV | learned | SYN→SILVER | 합성 tell의 silver 전이 시험 | `Drop_SYN→SILVER≤0.20` | 낙폭 `>0.20` 또는 silver 미자격 | 30장 × model seed 3 × eval silver 3 |
| L-SM | learned | SYN→META | learned shortcut의 metamorphic 노출 | META strict gate PASS, `R_META` 보고 | sentinel/mapping/scale strict FAIL | 30장 × model seed 3 |
| L-ES | learned | EXT→SYN | HGB 이득의 역전이 확인 | `Drop_EXT→SYN≤0.20` | 낙폭 `>0.20`, SYN/shuffle FAIL | 30장 × model seed 3 |
| L-EE | learned | EXT→EXT | 기존 HGB 향상의 재현 대각 | `R_EXT>0`, gate PASS | null 이하, shuffle/CRS/NC FAIL | 30장 × model seed 3 |
| L-EV | learned | EXT→SILVER | T-EXT 학습이 silver와 호환? | `Drop_EXT→SILVER≤0.20` | 낙폭 `>0.20`, silver/shuffle FAIL | 30장 × model seed 3 × eval silver 3 |
| L-EM | learned | EXT→META | 높은 T-EXT 점수가 invariant인가 | META strict gate PASS, `R_META` 보고 | sentinel/mapping strict FAIL | 30장 × model seed 3 |
| L-VS | learned | SILVER→SYN | silver shortcut의 합성 전이 | `Drop_SILVER→SYN≤0.20` | 낙폭 `>0.20`, SYN/silver/shuffle FAIL | 30장 × train silver 3 × seed 3 |
| L-VE | learned | SILVER→EXT | 큰 낙폭 예상, 제품 위험 직결 | `Drop_SILVER→EXT≤0.20` | 낙폭 `>0.20`, NC/CRS/shuffle FAIL | 30장 × train silver 3 × seed 3 |
| L-VV | learned | SILVER→SILVER | 대각 높음 예상, 자기복제 위험 최대 | `R_SILVER>0`, disjoint-family gate | raw/family leakage 또는 null 이하 | 30장; train 3 × eval 3 × seed 3 |
| L-VM | learned | SILVER→META | silver 학습의 invariant 여부 | META strict gate PASS, `R_META` 보고 | sentinel/mapping strict FAIL | 30장 × train silver 3 × seed 3 |

`V`는 표 길이를 줄이기 위한 T-SILVER 약자다. 모든 off-diagonal의 `Drop`은 동일 C에서 해당 평가원 대각과 비교한다. 예를 들어 `SYN→EXT`는 `EXT→EXT`와 비교하며 `SYN→SYN`과 비교하지 않는다.

### 6.3 effects table 템플릿 — 현재 전부 UNRUN

**deterministic-tuned**

| train \ eval | T-SYN | T-EXT | T-SILVER | T-META |
|---|---|---|---|---|
| T-SYN | UNRUN (diagonal) | UNRUN (key off-diagonal) | UNRUN | UNRUN (no diagonal) |
| T-EXT | UNRUN | UNRUN (diagonal) | UNRUN | UNRUN (no diagonal) |
| T-SILVER | UNRUN | UNRUN (key off-diagonal) | UNRUN (diagonal) | UNRUN (no diagonal) |

**learned**

| train \ eval | T-SYN | T-EXT | T-SILVER | T-META |
|---|---|---|---|---|
| T-SYN | UNRUN (diagonal) | UNRUN (key off-diagonal) | UNRUN | UNRUN (no diagonal) |
| T-EXT | UNRUN | UNRUN (diagonal) | UNRUN | UNRUN (no diagonal) |
| T-SILVER | UNRUN | UNRUN (key off-diagonal) | UNRUN (diagonal) | UNRUN (no diagonal) |

사전 방향 가설은 세 라벨형 대각이 높고 `T-SYN→T-EXT`, `T-SILVER→T-EXT`가 가장 크게 떨어진다는 것이다. 그러나 null도 완전한 결과다. 특정 off-diagonal이 대각과 동등하면 그 source pair를 호환 후보로 올린다. 현재 `interactions_found=A×B, status=UNRUN`; 효과값, PASS, 호환쌍은 아직 없다.

### 6.4 confirmation run

core validation에서 모든 gate를 통과한 off-diagonal 중 worst-source skill을 최대화하는 `(A,C)`를 먼저 선택하고, 그 안에서 낙폭이 가장 작은 `(train,eval)` pair를 하나 봉인한다. threshold와 model artifact를 바꾸지 않고 hold-out firm에서 한 번 재실행한다. firm metadata가 없거나 counsel이 끝나지 않았으면 상태는 패킷대로 `PASS_WITH_DEFERRAL`; 이를 PASS로 바꾸지 않는다. test를 사용하는 경우 frozen method당 단 한 번만 읽고 재튜닝하지 않는다.

## 7. red team 티켓 응답

패킷이 이 제안과 직접 연결한 핵심은 T1과 T17이며, 프로그램 선결과 구현 경계를 통해 T2, T5, T7, T15, T24, T34도 걸린다. 패킷에 티켓 전문이 없는 항목은 번호에서 세부를 만들어내지 않고, 패널 보고서에 적힌 공격·맥락까지만 응답한다.

| 티켓 | 걸리는 이유 | 응답 | 잔여 판정 |
|---|---|---|---|
| **T1 대리 독립성** | 합성·외부·silver·meta가 같은 평행 이중선 prior를 공유하면 합의가 편향 증폭일 수 있음 | 24셀 `A×B`, paired canonical 30-drawing bridge, same-item source disagreement tensor를 함께 보고한다. silver는 다섯 표가 아닌 두 family block으로 계산한다. source-bundle 결과와 same-item 결과가 다르면 truth-source 해석을 낮춘다. | 설계상 해소 경로 있음, 실측 UNRUN |
| **T17 (CL-E 직접 연결)** | 패킷은 T17 전문을 싣지 않고 CL-E와의 연결만 명시함 | 추정 내용을 꾸미지 않는다. 이 도시예가 확실히 다룰 수 있는 동일-def 불일치, 대각/비대각 대비, hold-out confirmation, 상태 보존을 증거로 낸다. 실행 시 원 티켓 acceptance criterion을 확보하기 전 CLOSED로 바꾸지 않는다. | 위험 수용, 원문 확인 전 OPEN |
| **T2 합성 생성기/충실도** | 최신 다이제스트에는 합성팩이 있으나 B1이 FAIL이고 entity 종류가 빈약함 | “존재”와 “유효”를 분리한다. B1, 양·음 공존, seed-disjoint, arithmetic-tell audit가 통과하기 전 SYN 셀은 PREQUALIFICATION_ONLY/UNQUALIFIED다. | OPEN, hard gate |
| **T5 라이선스** | CubiCasa/FloorPlanCAD NC와 원 도면 권리, T-EXT weight의 제품 탑재 위험 | counsel 서면 전 T-EXT train artifact는 격리된 방법검증용. 제품 registry·배포·재배포 금지. 라이선스 실패 시 T-EXT train arm과 FloorPlanCAD 파생물을 kill한다. | OPEN, 외부 결정 필요 |
| **T7 0벽 sentinel** | 위반율만 보면 상수 0 탐지기가 META를 통과할 수 있음 | zero-wall/all-wall sentinel, recall-floor, mapping completeness를 measure 앞의 hard gate로 둔다. gate 실패 시 수치를 순위에 넣지 않는다. | 설계상 대응, 실측 UNRUN |
| **T15 learned seed confounding** | learned 셀 차이가 truth가 아니라 seed일 수 있음 | 동일 세 model seed, 동일 Sobol configuration budget, learned-only randomized order, seed random effect를 사용한다. deterministic에는 가짜 seed 반복을 만들지 않는다. | 설계상 대응, 실측 UNRUN |
| **T6 평가 단위 혼동** | handle·집합·drawing을 섞으면 큰 drawing이 결과를 지배함 | 표적은 per-handle wall membership이지만 loss는 drawing equal-weight로 집계하고 firm/drawing cluster로 추론한다. room assembly나 RL 보상은 별도 산출물로 격리한다. | 설계상 대응 |
| **T24 pixel→handle 역투영** | FloorPlanCAD를 core에 넣으면 projection 오류가 truth 효과로 보일 수 있음 | synthetic exact round-trip harness 통과 전 raster축을 core factor에서 제외한다. 실패 시 CL-G로 hand-off한다. | 조건부 OPEN |
| **T34 load-bearing 인용 미실행** | 패널의 R-lane 인용들이 experiment_executed:false라는 프로그램급 문제 | 본 도시예에서 문헌은 방법론 계보로만 쓰고 E2 효과의 증거로 쓰지 않는다. 모든 효과표와 interaction을 UNRUN으로 표시하며 xlsx와 run evidence 없이는 상태를 올리지 않는다. | 본 문서의 과대주장 방지 완료, 프로그램 티켓은 OPEN |

추가로 R23 kill risk에 해당하는 CRS/축척과 NC 문제를 각각 coordinate round-trip과 counsel gate로 분리했다. 현재 CubiCasa가 px 좌표이고 도면별 축척이 미상이라는 사실 때문에, mm prior 실패를 truth-source 상호작용으로 오인하지 않는다.

## 8. 인접 제안과의 관계

### 8.1 병합 가능한 지점

- **CL-C / PR-1 벽 합성 truth + WSD-EVAL-v1**: T-SYN source qualification, per-handle `wall_member(h)`, hidden mutation family, seed ancestry manifest를 그대로 소비한다. CL-C가 B1을 통과하지 못하면 P3의 SYN confirmatory arm은 죽는다.
- **CL-D metamorphic battery**: 강체·scale·단위·explode·레이어명 변환과 sentinel을 T-META adapter로 가져온다. P3는 배터리 자체를 발명하기보다 어느 train truth가 이 게이트로 전이되는지 묻는다.
- **CL-B deterministic v1 / doe P2 강건화**: `fast_score`, evidence channel, 상대·절대 gap 팔을 deterministic-tuned family의 공통 하네스로 재사용한다. 다만 노브 개선과 truth 상호작용을 같은 단계에서 바꾸지 않는다.
- **CL-F 학습 사다리**: HGB를 learned 최소 계열로 공유한다. P3가 T-EXT 대각 이득만 보여주면 GNN·DL로 확장하지 않고 source validity를 먼저 고친다.
- **CL-K anti-silver control**: silver-distill과 gate-only를 learned T-SILVER의 exploratory ablation으로 붙일 수 있다. confirmatory C 수준을 사후에 늘리지는 않는다.
- **CL-G raster/VLM**: FloorPlanCAD exact projection이 통과한 뒤 secondary evaluation을 공유한다. 벡터↔래스터 변환 오류가 P3 interaction에 들어오지 않게 core 밖에서 결합한다.
- **PR-3 counsel**: T-EXT train arm과 confirmation의 외부 hard gate다.

### 8.2 차별점

이 제안은 더 좋은 벽 탐지기 구조를 제안하는 자리가 아니다. 같은 deterministic/learned 계열을 고정한 채 **무엇을 정답으로 삼았는지가 평가 정답과 상호작용하는지**를 추정한다. CL-C는 정답원을 만들고, CL-D는 무라벨 계약을 만들며, CL-F는 학습기를 만든다. P3는 그 세 산출물이 서로 전이되는지를 판결한다. 대각 최고점이 아니라 비대각 낙폭과 same-item 불일치가 성패 지표라는 점이 고유하다.

### 8.3 이 제안이 죽어야 하는 조건

1. **source qualification 사망**: T-SYN B1, T-SILVER 자격, T-EXT CRS/counsel, T-META sentinel 중 필수 축이 끝내 닫히지 않아 3×4 교차를 정의할 수 없으면 P3 confirmatory claim은 죽는다. 축을 몰래 줄여 같은 이름의 PASS를 만들지 않는다.
2. **same-item bridge 사망**: canonical correspondence를 만들 수 없어 truth source와 population/adapter를 분리하지 못하면 “truth-source validity”라는 인과 해석은 죽는다. 남는 것은 source-bundle operational transfer 표뿐이다.
3. **대각 사망**: qualified source에서도 두 모델 family의 대각이 null을 넘지 못하면 그 source는 학습 신호가 아니다. 세 source가 모두 그러면 프로그램의 bootstrap 전제를 재검토한다.
4. **전 비대각 붕괴**: 모든 비대각 낙폭이 임계를 넘으면 단일 proxy 체인은 폐합하지 않는다. 다원 truth ensemble 또는 사람 라벨/새 정답원 조달로 hand-off한다.
5. **효과 부재**: 모든 gate와 불확실성 조건을 통과하면서 `A×B`와 `Δ`가 실질 임계 이내이고 hold-out에서도 안정적이면, source-specificity 위험을 계속 연구할 별도 이유가 사라진다. 이는 실험 실패가 아니라 이 제안을 종료해야 하는 반증 성공이다.
6. **C가 결론을 뒤집음**: `A×B×C`가 커서 deterministic과 learned가 반대 결론이면 계열 평균 PASS를 금지한다. 각 계열을 별도 체인으로 보고 더 넓은 “프로그램 전체 폐합” 주장을 죽인다.
7. **라이선스 사망**: counsel이 T-EXT 학습·파생 산출물을 허용하지 않으면 T-EXT-train arm은 방법론적 참고 결과로도 실행 범위를 재협의해야 하며, 제품 경로에서는 즉시 제거한다.

### 8.4 최종 실행 판정 계약

현재는 설계만 완료되었고 모든 effects와 interaction은 `UNRUN`이다. 실행 후 가능한 최종 상태는 `CHAIN_CLOSURE_SUPPORTED`, `TRUTH_SOURCE_SPECIFIC_OVERFIT`, `DIAGONAL_FAIL`, `UNQUALIFIED`, `INCONCLUSIVE` 중 하나다. “가장 높은 대각 F1”은 어떤 상태도 자동으로 PASS시키지 않는다. 가장 잘 전이된 pair의 hold-out firm 재실행은 `PASS_WITH_DEFERRAL`이며, firm 메타데이터·counsel·단발 증거가 실제로 닫힐 때만 갱신한다.

DOSSIER_COMPLETE: doe_P3
