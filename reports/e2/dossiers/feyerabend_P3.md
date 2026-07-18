# E2 벽 의미 탐지기 방법론 심층 도시어 — feyerabend_P3

## 연구 판정 요약

P3의 검증 대상은 “LLM silver와 낮은 상관” 자체가 아니다. 검증 대상은 **silver를 feature·loss·선택 기준에서 완전히 격리한 게이트-가산 탐지기**가 합성 정답, metamorphic 불변성, 공간폐쇄라는 서로 다른 시험에서 살아남고, 같은 초기조건의 silver-distill 복제 모델보다 강건한가이다. LLM과의 Pearson은 학습 목적이 아니라 사후 독립성 진단이다. 이를 일부러 낮추는 loss는 또 다른 Goodhart이므로 금지한다.

현재 상태에서 anti-silver 경로를 VIABLE로 선언할 수는 없다. 패킷의 실측상 합성팩은 B1 충실도 FAIL(KS 0.5792, TV 0.265)이고, S팩 채점우주에는 음성이 없다. 따라서 현재 합성팩으로 배관 시험은 할 수 있어도 최종 방법론 판결은 할 수 없다. 아래 계획은 PR-1 충실도 게이트와 음성 sentinel을 하드 선결로 두며, 실패 시 “실험 미성립”으로 기록한다.

이 문서에서 “실측”이라고 쓰는 값은 패킷 다이제스트의 값뿐이다. 새로 제시하는 모델 폭, seed 수, 허용차, 시간과 합격선은 모두 **사전등록 제안값 또는 계획 추정값**이며 새 측정 주장이 아니다. 선행연구 명칭과 계보는 웹 검색 없이 작성한 일반 지식이다. 서지 세부가 불확실한 항목은 “요검증”으로 표시한다.

## 1. 이론적 근거·선행연구

### 1.1 인식론적 핵심

P3는 LLM 판정을 “약한 진실”로 격상하는 대신 하나의 관측 장치가 만든 이론-의존적 산출로 취급한다. 벽이라는 대상은 CAD 기하, 레이어 관례, 렌더링 투영, 프롬프트 어휘, 모델 사전학습 분포 중 어느 언어로 관찰하느냐에 따라 다른 표상으로 나타난다. 패킷에서 silver 판정자 5기가 실제로는 2어휘 가문으로 갈렸다는 사실은 다수결 표수가 독립 증거 수와 같지 않음을 보여준다.

이 입장은 다음 계보에 기대고 있다.

- N. R. Hanson의 theory-laden observation, Thomas Kuhn의 패러다임 의존적 관찰, Paul Feyerabend의 방법론적 다원주의는 관측 언어를 진리와 동일시하지 말아야 한다는 배경을 준다. 대표 저작명은 일반 지식이며 정확한 판본·쪽수는 요검증이다.
- Goodhart의 법칙과 Campbell의 법칙은 대리 지표를 최적화 목표로 삼는 순간 지표가 대상의 좋은 측정치가 아니게 될 수 있음을 설명한다. 여기서 detector–LLM 상관을 직접 최적화하면 “벽 기하” 대신 “LLM이 벽이라고 부르는 방식”을 학습할 위험이 있다.
- Dawid–Skene류의 다중 판정자 모형과 weak supervision/Data Programming·Snorkel 계열은 판정자 간 의존성과 정확도를 모델링해야 함을 보여준다. P3는 한 단계 더 보수적이다. 판정자 의존성을 추정해 합성 label로 만드는 대신, silver를 주 학습 경로 밖에 둔다.
- Hinton 등의 knowledge distillation은 teacher의 soft target을 학생 모델에 전달하는 표준 대조 이론이다. P3의 silver-distill arm은 이 이론을 악역으로 가정하지 않고, 동일 아키텍처·동일 초기화로 정당한 경쟁자로 둔다.
- Chen 등의 metamorphic testing 계보와 consistency regularization은 정답이 부족해도 의미 보존 변환 전후의 관계를 시험할 수 있게 한다. 회전·이동·반사·단위변환·scale·레이어 셔플은 “출력 값이 같아야 한다”가 아니라 handle 대응으로 복원한 벽 쌍 집합이 안정해야 한다는 관계식이다. 정확한 최초 논문 서지는 요검증이다.
- Domain randomization과 sim-to-real 계보는 합성 다양성이 실제 nuisance를 충분히 덮을 때만 합성 정답이 유효함을 강조한다. 현 합성팩의 B1 FAIL은 사소한 품질 문제가 아니라 P3의 정답원 자격을 정지시키는 결과다.
- planar arrangement, Euler characteristic, polygonization에 기반한 위상 검사는 선분의 국소 모양이 아니라 공간 분할에 미치는 영향을 측정한다. 벽 후보를 제거했을 때 bounded face 수가 크게 바뀌는지는 LLM 어휘와 다른 관측 축이다. 다만 치수선·창호·기호도 폐곡면을 만들 수 있으므로 closure는 단독 정답이 아니라 합성·metamorphic과 함께 쓰는 가산 gate다.
- negative control과 leakage audit의 실험설계 전통은 “silver를 쓰지 않았다”는 선언을 코드 수준 반증 가능 명제로 바꾼다. silver 파일을 삭제·셔플·상수화해도 gate-only 모델의 학습 산출이 같아야 한다.

### 1.2 P3가 주장하는 것과 주장하지 않는 것

주장은 세 가지다.

1. 합성 정답이 충실도 게이트를 통과한 뒤, geometry-only gate model은 silver 없이도 합성 F1과 metamorphic 안정성을 동시에 만족할 수 있다.
2. silver-distill은 LLM 관측 언어에 대한 적합도를 높일 수 있지만, 그것이 합성 기하·변환 안정성·공간폐쇄의 우월성을 보장하지 않는다.
3. “LLM high likelihood ∧ 결정론 0” 셀은 자동 positive label이 아니라 관측언어 충돌 셀이다. 이 셀은 오류 분석과 독립성 계량에만 사용한다.

반대로 다음은 주장하지 않는다.

- Pearson이 낮으면 탐지기가 옳다는 주장을 하지 않는다. 빈 탐지기와 무작위 탐지기도 낮은 상관을 만들 수 있다.
- LLM이 항상 틀리다고 주장하지 않는다. 실제 기하와 LLM 관례가 맞는 도면군에서는 silver가 유용할 수 있으며, 이것이 바로 복제 모델의 kill test가 필요한 이유다.
- 합성팩이 현재 truth source 자격을 갖췄다고 주장하지 않는다. 실측 B1 FAIL과 S 음성 0개가 해소되기 전에는 최종 판정을 봉인한다.
- CubiCasa 사람 라벨을 무가치하다고 주장하지 않는다. P3의 주 학습 신호에서 제외하되, 권리와 분할 계약이 정리되면 독립 외부 평가축으로 사용한다.

### 1.3 반증 구조

낮은 LLM 상관은 필요조건 중 하나일 뿐 충분조건이 아니다. P3의 충분조건은 패킷에 명시된 결합 밴드, 즉 합성 F1≥0.80, metamorphic pass rate≥0.90, LLM-Pearson≤0.35의 동시 충족이다. 합성 F1≥0.80인데 metamorphic pass rate<0.50이면 합성 과적합으로 판정한다. 같은 초기조건의 silver-distill 모델이 합성·metamorphic에서 동등하거나 우월하면 anti-silver의 강한 주장은 약화되며, 모든 핵심 gate에서 우월하면 counter-theory가 죽는다.

## 2. 알고리즘 정확 스펙

### 2.1 입력·출력과 허용 데이터

도면 d의 입력을 다음과 같이 둔다.

- H_d: 안정적인 handle ID를 가진 선분·폴리라인 원시 요소 집합
- X_d: geometry-only 특징 행렬
- G_d=(V_d,E_d): snap된 끝점과 선분/후보 관계로 만든 도면 그래프
- R_d={r_j}: 평행 쌍 또는 리본 후보 집합
- Y_syn: 충실도 게이트를 통과한 합성 데이터에만 존재하는 per-handle wall_member 정답
- Π_T: 변환 T 전후 handle/후보의 전단사 대응표
- C_d: 후보 제거 전후 face 변화에서 만든 closure evidence

gate-only 학습 함수의 허용 입력은 {H, X, G, R, Y_syn, Π_T, C}뿐이다. 다음은 금지한다.

- LLM wall_likelihood, rationale, 추천 handle, 판정자 ID, 프롬프트, 모델명
- silver와 결합해 만든 pseudo label, sample weight, hard-negative 선택표
- silver 성능을 보고 선택한 threshold·epoch·checkpoint
- 원문 layer name 또는 파일명처럼 프로젝트 관례를 직접 드러내는 문자열

주 출력은 per-handle 확률 p_h, 이진 벽 집합 W_d, 후보별 gate contribution, closure contribution, 변환별 pass/fail, provenance manifest다. evidence workbook에는 모델·split·seed·gate·실패 이유를 기록하되 silver 분석 시트와 gate-only 학습 시트를 분리한다.

### 2.2 후보와 특징

기존 fast_score와 CubiCasa ML의 여섯 특징을 접점으로 삼되, 물리 단위가 없는 CubiCasa에서 절대 mm 대역을 재사용하지 않는다.

각 후보 r_j에 대해 다음 특징군을 만든다.

1. parallel gate: 각도 차이의 주기적 표현과 평행 overlap
2. gap gate: 후보 간격을 도면 또는 국소 이웃의 robust scale로 나눈 상대 간격
3. junction gate: 끝점 snap 후 T/L/X junction 구성과 연결도
4. extent gate: log length와 이웃 대비 상대 길이
5. orientation gate: sin(2θ), cos(2θ)
6. closure gate: 후보 제거에 따른 bounded-face 변화

layer 문자열은 주 모델에 넣지 않는다. 레이어 셔플 metamorphic에서 보존되어야 할 것은 geometry와 handle 대응이다. 기존 v1의 layer channel은 별도 ablation으로만 남기고 주 결과와 섞지 않는다. 이 선택은 실도면 full-vs-name-blind가 1.0으로 완전히 같고 탐지기가 레이어명 신호를 쓰지 않았다는 패킷 실측과도 정합한다.

### 2.3 공간폐쇄 점수

도면을 허용오차 ε로 snap한 planar arrangement A_d로 변환한다. ε는 절대 mm가 아니라 도면별 국소 길이 통계에 대한 상대값으로 사전등록한다. 후보 리본 r_j가 구성하는 선분을 제거한 arrangement를 A_d\ r_j라 하고 bounded face 수를 F(·)라 한다.

원시 변화량은 다음과 같다.

ΔF_j = max(0, F(A_d) - F(A_d \ r_j))

도면 크기에 대한 의존을 줄이기 위해 같은 도면 내 ΔF의 rank percentile을 c_j∈[0,1]로 사용한다. 모든 ΔF가 같으면 closure 신호는 “정보 없음”으로 표시하고 loss 가중치를 0으로 둔다. 얼굴 수 계산 실패, self-intersection, 비정상 geometry는 0으로 대체하지 않고 unknown으로 기록한다.

closure ranking loss는 서로 다른 closure score를 가진 후보 쌍에 대해 다음과 같다.

L_closure = mean_{i,j} |c_i-c_j| · log(1 + exp(-s_ij(p_i-p_j)))

여기서 s_ij=sign(c_i-c_j)다. 이 loss는 높은 closure 후보를 상대적으로 위에 두지만, 합성 정답을 덮어쓰지 않는다. 치수선이나 boundary가 만든 가짜 face에 대한 방어는 합성 음성, CubiCasa 클래스별 오류표, 0-wall/all-wall sentinel이 담당한다.

### 2.4 게이트-가산 모델

후보별 K개 증거 채널의 작은 encoder를 g_k(x_j,G_d)∈[0,1]로 두고, 음이 아닌 가중치로 합한다.

z_j = b + Σ_{k=1..K} softplus(a_k) · g_k(x_j,G_d)

p_j = sigmoid(z_j)

handle h가 여러 후보에 속하면 noisy-OR로 결합한다.

p_h = 1 - Π_{j:h∈r_j}(1-p_j)

후보가 없는 handle은 p_h=0으로 두되, 후보 생성 recall을 별도 보고한다. 모델의 설명 가능성을 유지하기 위해 각 g_k는 한 특징군만 읽는다. 주 모델은 작은 MLP gate들의 합이며, graph message passing은 adjacency audit를 통과한 경우에만 선택 가능한 확장으로 둔다.

### 2.5 손실

합성 supervised loss:

L_syn = mean_h BCE(p_h, y_h)

metamorphic consistency loss:

L_meta = mean_{T,h} JSD(Bern(p_h), Bern(p_{Π_T(h)}^T))

집합 수준 hard pass는 변환 후 예측 집합을 Π_T^{-1}로 되돌렸을 때 원 집합과 정확히 같은지로 정의한다. 부동소수 좌표 비교가 아니라 handle 대응을 사용한다. pass rate는 적용 가능한 변환 중 exact-set pass의 비율이다. 대응표가 완전하지 않은 변환은 실패로 덮지 않고 alignment-unknown으로 별도 집계한다.

주 loss:

L_gate = λ_syn L_syn + λ_meta L_meta + λ_closure L_closure + λ_reg ||θ||²

LLM-Pearson 항은 없다. 낮은 상관을 유도하는 음의 distillation loss도 없다.

silver-distill 복제 모델의 loss는 다음과 같다.

L_distill = L_gate + λ_silver mean_h BCE(p_h, q_h)

q_h는 정렬이 검증된 silver likelihood다. C2 cheapest probe에서는 두 arm이 **정확히 같은 합성 drawing·handle 우주**를 보며, silver-distill만 그 동일 handle에 대한 q_h를 추가 target으로 받는다. 동일 합성 handle에 정렬된 q_h가 없으면 다른 실도면 silver를 섞어 대체하지 않고 C2를 BLOCKED로 둔다. 패킷의 5판정자를 5개의 독립표로 세지 않고, 먼저 각 어휘 가문 안에서 집계한 뒤 두 가문을 같은 무게로 평균한다. silver-distill은 gate-only와 parameter를 공유하지 않는 복제 네트워크다. 같은 초기 weight를 복사하지만 optimizer state와 gradient graph를 분리한다. 그렇지 않으면 silver gradient가 공유 encoder를 통해 gate-only에 누수된다.

### 2.6 관측언어 충돌 셀

결정론 v1 출력이 0이고 family-balanced silver likelihood q_h가 높은 handle을 contamination/disagreement cell로 표시한다. “high”의 운용 기준은 새 사전등록 제안값 τ_high=0.80이며 측정값이 아니다. 이 mask는 analysis namespace에만 존재한다.

M_conflict = {h | deterministic_v1(h)=0 ∧ q_h≥τ_high}

이 셀에서는 gate-only·distill의 합성 대응 성능, metamorphic 안정성, closure rank, CubiCasa 사람 라벨이 사용 가능할 때의 정합을 비교한다. M_conflict 자체를 positive나 negative target으로 사용하지 않는다.

### 2.7 추론 threshold와 sentinel

이진 threshold τ_pred는 합성 validation에서만 선택하고 이후 동결한다. 목표함수는 합성 F1이며, 동률이면 더 높은 metamorphic pass, 다시 동률이면 더 단순한 gate 수를 택한다. silver 상관은 동률 해소에도 쓰지 않는다.

빈 탐지기와 전벽 탐지기를 막기 위해 다음을 의무화한다.

- 0-wall synthetic sentinel: 예측 벽 수가 0이어야 한다.
- all-wall synthetic sentinel: per-handle recall 최저선을 만족해야 한다.
- mixed synthetic sentinel: positive·negative가 모두 있어 precision과 recall이 정의되어야 한다.
- candidate recall audit: 후보 생성 단계에서 놓친 true wall은 classifier recall과 분리한다.

all-wall recall의 구체 최저선은 PR-1 팩과 함께 평가 전에 봉인해야 한다. 패킷에 해당 수치가 없으므로 여기서 실측값처럼 발명하지 않는다.

### 2.8 제안 하이퍼파라미터 공간

다음은 로컬 16GB GPU에 맞춘 사전등록 후보이며 실측 결과가 아니다.

- gate MLP: hidden width {32, 64}, hidden layer {1, 2}, GELU 또는 ReLU
- λ_syn=1 고정
- λ_meta∈{0.1, 0.3, 1.0}
- λ_closure∈{0.1, 0.3, 1.0}
- λ_silver∈{0.1, 0.3, 1.0}; negative-control arm에서만 허용
- learning rate∈{1e-4, 3e-4, 1e-3}
- weight decay∈{1e-6, 1e-5, 1e-4}
- batch는 도면 단위 또는 도면 내부 후보 chunk로 구성하며 서로 다른 split의 도면을 섞지 않는다.

선택은 합성 validation과 metamorphic validation만 사용한다. CubiCasa val은 외부 전이 판정에 사용하되 주 모델의 epoch·threshold 선택에 역류시키지 않는다. test는 모든 선택 후 한 번만 연다.

### 2.9 의사코드

~~~text
assert fidelity_gate(synthetic_pack) == PASS
assert has_zero_wall_all_wall_and_mixed_sentinels(synthetic_pack)
manifest = freeze_drawing_splits_and_transform_maps()

gate_model, distill_model = clone_same_initialization()

for seed in preregistered_seeds:
    for batch in synthetic_and_unlabeled_geometry_batches:
        x, graph, y_syn, transform_map, closure = allowed_inputs(batch)

        p_gate = gate_model(x, graph)
        loss_gate = supervised_if_synthetic(p_gate, y_syn)
        loss_gate += meta_consistency(gate_model, batch, transform_map)
        loss_gate += closure_ranking(p_gate, closure)
        update(gate_model, loss_gate)

        p_distill = distill_model(x, graph)
        loss_distill = same_gate_losses(p_distill)
        if cell_is_C2:
            assert batch_is_same_synthetic_handle_universe_for_both_arms()
            assert aligned_silver_exists_for_every_scored_synthetic_handle(batch)
            q = load_family_balanced_silver_from_isolated_sidecar()
            loss_distill += silver_distillation(p_distill, q)
        elif aligned_silver_exists(batch):
            q = load_family_balanced_silver_from_isolated_sidecar()
            loss_distill += silver_distillation(p_distill, q)
        update(distill_model, loss_distill)

    assert gate_model_artifact_is_invariant_to_silver_delete_shuffle_constantize()
    evaluate_synthetic_and_metamorphic_without_opening_test()
    analyze_llm_pearson_and_conflict_cells_after_checkpoint_freeze()

if preregistration_gate_passes_on_validation:
    freeze_one_checkpoint_and_threshold()
    open_external_test_once()
else:
    record_BLOCKED_or_KILLED_with_reason()
~~~

### 2.10 R23 정합의 최소 운용화

패킷은 R23의 원문을 제공하지 않으므로 내용을 발명하지 않는다. 이 연구에서 LLM에도 적용할 최소 정합 계약은 다음과 같다.

- drawing ID, handle ID, 좌표계, transform ID, prompt version, model family, timestamp stem을 보존한다.
- join은 stable ID로만 하고 좌표 근접·행 순서·파일 정렬 순서로 묵시 결합하지 않는다.
- 두 어휘 가문을 독립성 단위로 보며 5표 다수결을 독립 5표로 해석하지 않는다.
- 정렬 실패는 0 likelihood가 아니라 unknown이다.
- 원시 likelihood와 family aggregation을 모두 보존하고, 사람이 읽을 수 있는 rationale은 feature로 파싱하지 않는다.
- 이 최소 계약보다 강한 R23 원문 요구가 나중에 확인되면 원문이 우선한다.

## 3. 벽 과업 적응 설계

### 3.1 CubiCasa5k SEG-IR 벡터축

CubiCasa5k는 5,000도면 전량이 SEG-IR로 변환되어 있고 변환 실패가 0이며, train/val/test가 도면 단위로 나뉘어 있다. 벽 선분율은 약 11.8%다. 기존 geometry v1은 val F1 0.2358(P 0.134, R 0.981)이고, HistGradientBoosting은 여섯 특징으로 val P 0.860/R 0.370/F1 0.517/AUC 0.9215를 냈다. 로지스틱 F1 0.053과 shuffle AUC 0.375는 비선형 구조의 필요성과 누출 대조의 중요성을 각각 보여준다.

P3는 CubiCasa 사람 라벨을 주 학습 target으로 쓰지 않는다. 다음 세 역할만 허용한다.

1. train split의 geometry는 권리 확인 후 label을 가린 채 metamorphic·closure 입력으로 사용할 수 있다.
2. val label은 동결된 gate-only와 silver-distill의 외부 전이 진단에 사용한다.
3. test label은 합격선·모델·threshold·seed 처리 방식이 봉인된 뒤 방법당 단 한 번 사용한다.

절대 두께 prior는 사용하지 않는다. CubiCasa 좌표는 px이고 도면별 축척이 미상이며, 기존 v1은 2~15mm/px 전 구간에서 성적이 무감했다. gap gate는 도면/국소 상대 scale을 사용한다. Direction 화살표, BoundaryPolygon, Door, Window, DimensionMark는 클래스별 false-positive 표를 의무 생성한다. 최소길이 80px 필터의 천장이 F1 0.335였으므로 길이 gate 단독으로 해결했다고 주장하지 않는다.

GBDT 0.517은 강한 외부 기준선이다. P3가 가져와야 할 추가 가치는 단순 val F1 한 점이 아니라 다음 조합이다.

- 합성 정답에서 F1 0.80 이상
- scale을 포함한 metamorphic pass rate 0.90 이상
- CubiCasa val에서 GBDT와 비교 가능한 precision–recall 운용점
- 기존 GBDT의 낮은 recall 0.370을 회복하면서 긴 평행 비벽 구조의 FP를 closure/junction으로 억제
- silver 상관을 학습에 넣지 않았다는 재현 가능한 leakage proof

외부 val F1이 0.517에 미치지 못하면 anti-silver의 철학이 틀렸다고 즉시 결론내리지는 않지만, E2 생산 후보로 승격하지 않는다. 합성·metamorphic만 잘하고 사람 라벨 전이가 약하면 “내부 gate에는 강하나 실용 전이는 미확인”으로 남긴다.

### 3.2 FloorPlanCAD 래스터축

FloorPlanCAD는 5,308장과 wall bbox/segmask가 있으나 벡터 SVG가 없다. 따라서 per-handle wall_member를 직접 채점할 수 없고, raster mask를 벡터 정답인 것처럼 역투영하면 별도의 오류원이 생긴다.

P3의 1차 실험에서 FloorPlanCAD는 학습 target으로 쓰지 않는다. 사용 가능한 역할은 다음뿐이다.

- 동결 모델이 만든 벡터 예측을 같은 rasterizer로 렌더한 뒤 mask와 이미지 공간의 보조 overlap을 측정
- 회전·반사·scale의 raster-level metamorphic 확인
- qwen2.5-VL-3B 또는 다른 VLM의 판정을 silver jury로 수집하되 analysis sidecar에만 저장

픽셀↔handle exact 하네스가 합성에서 먼저 검증되지 않으면 결과는 “projection-unknown”으로 기록한다. bbox/segmask나 VLM 출력을 gate-only feature·loss·hard-negative mining에 넣지 않는다. 라이선스·원도면 권리의 서면 확인 전에는 새 학습 arm을 시작하지 않는다.

### 3.3 1.dwg staged DXF 실도면축

실도면 축은 도면정의 384개이며, 최대 도면정의는 412,775 선분으로 연산 병목이 실증되어 있다. 기존 B3 벽-제로 도면율은 0.682에서 0.2135로 낮아져 밴드 ≤0.40을 통과했고, detector–silver Pearson은 0.2911이었다. 이 낮은 상관은 P3의 결론이 아니라 출발 관찰이다.

접속 방법은 다음과 같다.

- drawing definition을 split의 원자 단위로 삼아 같은 정의의 변환본이 서로 다른 split에 들어가지 않게 한다.
- fast_score의 NumPy 동치 채점기로 후보와 기존 v1 출력을 만들고, 새 gate의 geometry feature adapter를 붙인다.
- 412,775 선분 도면은 spatial tiling으로 후보를 만들되, 타일 경계의 후보 쌍은 halo로 복원한다. closure는 전체 arrangement가 가능하면 전체로, 불가능하면 연결성분 단위로 계산하고 서로 다른 방식을 같은 지표로 섞지 않는다.
- 회전·이동·반사·단위·scale·레이어 셔플을 적용하고 handle map으로 집합을 되돌린다.
- 실도면에는 사람 정답이 없으므로 합성 F1을 대신 주장하지 않는다. metamorphic, closure 분포, zero/all-wall sentinel, silver disagreement 구조만 보고한다.
- “LLM high ∧ 결정론 0”은 오염 셀로 표지하되 gate-only 학습 batch sampler에는 전달하지 않는다.

현재 B4에서 강체·단위는 1.0이지만 scale 팔은 0.7624로 FAIL했고 센티널 조문도 strict FAIL이다. 따라서 P3의 첫 실도면 기여는 새 모델의 정확도 주장이 아니라 scale-equivariant feature와 sentinel 계약을 통해 이 실패를 닫는 것이다.

### 3.4 세 축의 역할 분리

| 축 | 학습 허용 | 개발 평가 | 최종 역할 |
|---|---|---|---|
| 충실도 통과 합성 S/F/M | per-handle 정답, metamorphic, closure | 예 | 주 truth 및 threshold 선택 |
| CubiCasa SEG-IR | 주 arm에서는 label 금지; geometry-only self-supervision만 조건부 허용 | val label로 독립 전이 평가 | test 단발 외부 사람 라벨 판결 |
| FloorPlanCAD raster | 주 arm 학습 금지 | projection이 검증된 경우 보조 평가 | raster-axis OOD 및 VLM jury |
| 1.dwg staged DXF | 정답 학습 금지 | metamorphic·closure만 | 실제 복잡도·불일치·연산성 검증 |
| E1.5 silver | gate-only에서 전면 금지 | checkpoint 동결 후 jury | negative control과 오류 분석 |

## 4. 데이터·컴퓨트 요구

### 4.1 필수 데이터 계약

필수 데이터는 다음과 같다.

- PR-1을 통과한 합성 wall pair/ribbon 팩
- 0-wall, all-wall, mixed positive/negative sentinel
- 각 변환의 stable handle map
- drawing-definition 단위 split manifest
- closure 계산을 위한 snap/arrangement 입력
- gate-only와 완전히 분리된 silver sidecar
- CubiCasa·FloorPlanCAD 사용 권리에 대한 counsel 기록

현 합성팩은 LINE/LWPOLYLINE/INSERT 3종뿐이고 실도면에는 SPLINE 3,973, ARC 2,198, HATCH 264가 혼재한다. 이 차이를 해소하지 않은 채 합성 F1 0.80을 달성해도 실도면 벽 의미의 증거가 아니다. 생성기는 curved/fragmented/block-transformed hard negative와 실제 비벽 장형 평행 구조를 포함해야 하며, B1 기존 계약을 통과해야 한다.

### 4.2 로컬 실행 계획

RTX 5070 Ti 16GB와 RAM 64GB를 기본 환경으로 삼는다.

- SEG-IR와 feature matrix는 메모리맵 또는 drawing chunk 단위로 읽는다.
- 후보 생성과 closure는 CPU 병렬 처리가 가능하지만, 재현 seed와 drawing 순서를 고정한다.
- 작은 gate MLP는 mixed precision 없이도 충분한 규모로 제한한다. mixed precision을 쓰면 gate-only/silver-distill의 수치 차이를 모델 차이와 혼동하지 않도록 두 arm에 동일 적용한다.
- 412,775 선분 도면은 전체 pairwise 비교를 금지하고 spatial index·각도 bucket·거리 상한으로 후보를 제한한다.
- 가장 싼 1-epoch paired probe를 먼저 실행해 방향성이 없으면 full sweep을 중단한다.
- evidence xlsx, JSON manifest, checkpoint, transform 결과를 run ID로 연결한다. 실패도 누락하지 않는다.

계획 추정으로 cheapest probe는 로컬 GPU 반나절 이내를 목표로 한다. 이는 패킷이 제시한 예산 범위를 그대로 따른 것이며 완료시간 측정 주장이 아니다. full multi-seed 실행은 야간 단위로 나누고 test는 자동 job에서 접근 불가능하게 별도 경로로 잠근다.

### 4.3 DGX 계획

DGX Spark Ornith-35B는 현재 unreachable이므로 critical path에서 제외한다.

- gate-only 학습과 closure, CubiCasa val, 실도면 metamorphic은 모두 로컬에서 완결한다.
- DGX가 복구되면 E1.5 재판정 또는 silver-distill negative-control의 q 생성에만 야간 슬롯을 사용할 수 있다.
- DGX 결과가 없다는 이유로 gate-only가 멈추면 silver 독립 설계가 아니다.
- DGX 결과는 R23 정합과 두 어휘 가문 집계를 통과한 뒤 analysis sidecar 또는 distill arm으로만 들어간다.
- 로컬과 DGX에서 같은 model hash·prompt hash·drawing manifest를 기록하지 못하면 비교를 수행하지 않는다.

### 4.4 자원 중단 조건

- PR-1 fidelity가 FAIL이면 full training 금지
- candidate generator recall이 sentinel에서 실패하면 classifier tuning 금지
- closure가 최대 도면에서 자원 상한을 넘으면 연결성분 근사와 exact subset을 분리 검증하기 전 전체 적용 금지
- counsel 미확인 상태에서는 CubiCasa/FloorPlanCAD 신규 학습 금지
- silver alignment가 불완전하면 distill arm과 Pearson 계산을 unknown으로 남기고 임의 매칭 금지

## 5. 구현 계획

### 5.1 제안 모듈 골격

아래는 향후 구현 골격이며, 본 도시어 작성 과정에서는 이 파일들을 생성하지 않는다.

~~~text
e2_wall/
  anti_silver/
    contracts.py              # 허용/금지 필드, taint 검사, split 계약
    candidates.py             # fast_score 후보 adapter
    geometry_features.py      # 상대 gap, junction, extent, orientation
    closure.py                # arrangement, face delta, unknown 처리
    metamorphic.py            # 변환 생성과 handle bijection 검사
    additive_gates.py         # 비음수 gate-additive model
    train_gate_only.py        # silver import 자체가 없는 주 trainer
    evaluate.py               # synthetic/meta/external 평가
    disagreement_analysis.py  # 동결 후 Pearson·conflict cell
    evidence_writer.py        # xlsx/JSON provenance
  negative_controls/
    train_silver_distill.py   # 격리된 복제 모델
    silver_family_aggregate.py
  configs/
    anti_silver_prereg.yaml
  tests/
    test_no_silver_dependency.py
    test_transform_bijection.py
    test_zero_all_wall_sentinels.py
    test_closure_unknown.py
    test_split_by_drawing.py
~~~

### 5.2 기존 도구 접속점

- evidence_grid: cell ID, hypothesis, gate, metric, seed, split, status, failure_reason를 쓰는 공통 증거 표로 사용한다. silver 분석은 별도 sheet와 provenance로 격리한다.
- fast_score: 기존 NumPy 동치 후보·v1 출력을 baseline과 deterministic=0 정의에 사용한다. 새 모델의 feature 계산이 fast_score 출력을 덮어쓰지 않게 adapter를 둔다.
- cubicasa_ir: SEG-IR handle, Wall 클래스 정답, drawing split을 읽는다. train label mask를 강제하는 view를 별도로 제공한다.
- cubicasa_ml: 기존 HistGradientBoosting과 logistic 결과를 재현하는 baseline runner에 접속한다. 주 gate model의 checkpoint 선택에는 silver를 넣지 않는다.

### 5.3 누수 방지 코드 계약

1. contracts.py는 silver/llm/judge/rationale/prompt 계열 필드가 gate-only batch에 있으면 즉시 실패한다.
2. train_gate_only.py의 import graph에는 disagreement_analysis와 negative_controls가 없어야 한다.
3. gate-only checkpoint를 만든 뒤 silver sidecar를 삭제, 행 셔플, 상수화한 세 실행에서 deterministic CPU smoke artifact가 byte-identical이어야 한다.
4. GPU full run은 비결정성이 있을 수 있으므로 사전등록한 수치 허용차와 동일 seed를 사용한다. 허용차는 smoke test 통과 후 평가 전에 봉인한다.
5. checkpoint 선택 로그에는 합성·metamorphic·closure 지표만 허용한다. Pearson은 checkpoint가 봉인된 뒤 계산한다.
6. silver-distill은 별도 output namespace와 run ID를 사용한다. 같은 encoder object나 optimizer를 공유하지 않는다.
7. drawing split hash가 다르면 비교를 실패 처리한다.

### 5.4 구현 순서와 규모

계획 추정상 1인 기준 6~9 작업일의 소형 연구 구현으로 본다. 이는 개발 견적이며 실측이 아니다.

1. 1~2일: schema contract, split guard, transform bijection, sentinel test
2. 2~3일: relative geometry gate와 closure exact subset
3. 1일: gate-only trainer와 isolated distill clone
4. 1일: evidence workbook·disagreement analyzer
5. 1~2일: CubiCasa/1.dwg adapter, 성능·메모리 보정

PR-1 합성 생성기 확장은 별도 선결 작업이며 위 견적에 포함하지 않는다. GNN 확장, raster inverse projection, DGX serving도 v0 범위 밖이다.

### 5.5 완료 정의

구현 완료는 코드가 실행된다는 뜻이 아니라 다음 증거가 모두 존재한다는 뜻이다.

- fidelity PASS 기록과 sentinel 결과
- split·transform·feature schema hash
- gate-only silver perturbation 불변성 시험
- paired seed별 gate-only/distill 결과
- synthetic F1, metamorphic pass, closure ablation, LLM-Pearson
- CubiCasa val 전이와 오류 클래스 표
- test 미접촉 증거 또는 단발 개봉 기록
- 실패 셀의 reason과 BLOCKED/KILLED 상태
- 필수 evidence xlsx

## 6. 실험 셀 정의

아래 seed 수와 동등성 margin은 모두 평가 전 봉인할 사전등록 제안이다. 기본 seed는 {11, 23, 37, 53, 71} 다섯 개로 하고, cheapest probe와 학습 arm에는 같은 초기 weight·batch 순서를 paired 적용한다. 한 seed가 자원 오류로 빠지면 다른 seed로 조용히 대체하지 않고 실패를 기록한 뒤 전체 cell을 incomplete로 둔다.

### C0 — SILVER-FIREWALL 계약 시험

- 가설: gate-only 산출은 silver 파일의 존재·내용·순서에 인과적으로 의존하지 않는다.
- 조작: silver sidecar 정상/삭제/행 셔플/전부 상수의 네 조건에서 deterministic CPU smoke train을 실행한다.
- 지표: 허용 입력 schema, import dependency, split hash, checkpoint byte hash, 예측 hash.
- 제안 합격선: 네 조건의 gate-only artifact가 byte-identical이고 금지 필드 접근이 0건.
- kill condition: 어떤 silver 변형이라도 gate-only batch, checkpoint, prediction을 바꾸면 P3 구현은 즉시 무효.
- 예산: 로컬 CPU 수십 분 이내 계획; GPU 불필요.
- seed 계획: 고정 seed 1개로 계약을 먼저 증명하고, full run 다섯 seed에서는 dependency manifest를 반복 저장한다.

### C1 — PR-1 FIDELITY·SENTINEL 자격 셀

- 가설: 확장 합성팩은 실제 도면 현상과 충분히 맞고 precision·recall이 모두 정의되는 채점우주를 제공한다.
- 지표: 기존 B1 fidelity gate, 엔티티 구성, positive/negative 수, candidate recall, 0-wall/all-wall/mixed sentinel.
- 제안 합격선: 기존 B1 계약 PASS, 세 sentinel PASS, mixed pack에서 positive와 negative 모두 존재. 패킷에 없는 B1 숫자를 새로 발명하지 않는다.
- kill condition: B1 FAIL, S 음성 0 지속, handle mapping 불완전 중 하나라도 있으면 C2 이후의 방법론 판결 금지.
- 예산: 생성기 구축은 PR-1 별도; 본 셀의 평가는 로컬 CPU.
- seed 계획: 생성 seed 다섯 개를 manifest로 고정하고 family별 결과를 합쳐 숨기지 않는다.

현재 증거 판정: B1은 KS 0.5792, TV 0.265로 FAIL이고 S 음성은 0개이므로 **현재 C1은 FAIL/BLOCKING**이다.

### C2 — CHEAPEST-PAIR 1 epoch 셀

- 가설: 같은 합성·초기화에서 gate-only가 silver-distill보다 metamorphic에 강하고 합성 F1은 비열등하다.
- arm: G=gate-only, S=silver-distill. 두 arm은 정확히 같은 합성 drawing·handle·batch 순서를 보고, S만 동일 합성 handle에 정렬된 family-balanced q를 추가 target으로 받는다. parameter는 공유하지 않고 초기 weight만 복제한다. 동일 합성 q가 없으면 실도면 silver로 대체하지 않고 BLOCKED다.
- 지표: 합성 F1, metamorphic pass rate, candidate recall, closure rank consistency, 학습 후 LLM-Pearson.
- 제안 합격선 A: median(meta_G-meta_S)≥0.10이고 F1_G≥F1_S-0.02. 이때 패킷 판정어는 kills: reigning이다.
- 판정 B: silver-distill이 합성·metamorphic·sentinel gate 모두에서 우월하면 kills: counter다.
- 동등성 운용: |차이|≤0.02를 제안상 동등으로 보고, silver-distill이 합성·metamorphic에서 동등 또는 우월하면 anti-silver 강한 주장을 약화한다.
- kill condition: gate-only가 sentinel을 악화시키거나, meta 우위가 단 한 seed/변환 family에만 존재하거나, silver가 shared encoder로 누수되면 cell 무효.
- 예산: 로컬 RTX 5070 Ti 반나절 또는 DGX 소형 배치라는 패킷 예산. DGX 불통이므로 로컬 우선.
- seed 계획: paired 다섯 seed. 1 epoch 결과로 방향이 없으면 full sweep 중단.

### C3 — SOURCE-ABLATION 최종 val 셀

- 가설: 합성+metamorphic+closure 조합이 어느 한 대리의 단일 prior가 아니라 상보적 신호를 제공한다.
- arm: synthetic-only, synthetic+meta, synthetic+closure, synthetic+meta+closure. 각 arm에 silver가 없는 gate-only를 사용한다.
- 지표: 합성 F1, 변환 family별 pass, closure holdout ranking, zero/all-wall sentinel, 후보 recall.
- 제안 합격선: 최종 arm이 합성 F1≥0.80과 metamorphic pass≥0.90을 동시에 만족. LLM-Pearson은 checkpoint 동결 후 ≤0.35.
- 과적합 판정: 합성 F1≥0.80인데 metamorphic<0.50이면 합성 과적합.
- kill condition: synthetic-only와 최종 arm이 모든 핵심 지표에서 동등하고 closure/meta가 오류만 추가하거나, final pass가 빈/전벽 sentinel에 의존하면 복합 메커니즘을 죽인다.
- 예산: 로컬 GPU 야간 실행과 CPU closure 전처리. exact closure가 불가능한 도면은 근사 결과와 분리한다.
- seed 계획: 다섯 seed, transformation seed는 model seed와 분리해 manifest에 고정.

### C4 — CUBICASA-VAL 외부 전이 셀

- 가설: anti-silver gate가 합성 내부 점수만 맞추지 않고 사람 라벨 벡터축으로 전이한다.
- 학습: CubiCasa label을 주 model loss에 넣지 않는다. 권리 확인 후 train geometry의 meta/closure만 조건부 사용한다.
- 지표: val P/R/F1/AUC, 클래스별 FP, scale 구간별 성능, candidate recall. v1 F1 0.2358과 GBDT F1 0.517을 고정 baseline으로 둔다.
- 제안 승격선: val F1이 최소 GBDT 0.517 이상이고, metamorphic≥0.90 및 sentinel을 유지해야 test 개봉 후보가 된다. 이 수치는 기존 측정 기준선을 승격선으로 재사용하는 제안이지 새 결과가 아니다.
- kill condition: val 향상이 silver 상관 상승에만 동반되고 meta/closure가 악화되거나, Direction/BoundaryPolygon/Door/Window/DimensionMark 중 특정 비벽군을 벽으로 흡수해 총 F1만 맞춘 경우 생산 승격을 죽인다.
- 예산: 이미 변환된 SEG-IR 사용, 로컬 GPU/CPU.
- seed 계획: C3의 다섯 frozen checkpoint를 그대로 평가하며 CubiCasa val을 보고 재학습하지 않는다.

### C5 — REAL-384 독립성·충돌 셀

- 가설: 실도면에서 gate-only는 LLM과 낮은 상관을 억지로 최적화하지 않고도 변환 안정성과 공간폐쇄를 유지한다.
- 데이터: 1.dwg staged DXF의 도면정의 384개. 정의 단위 고정 split과 handle map 사용.
- 지표: 변환 family별 exact-set pass, zero-wall 도면율, closure score 분포, Pearson, M_conflict 크기와 구성, full-vs-name-blind.
- 제안 합격선: 전체 metamorphic pass≥0.90, LLM-Pearson≤0.35, sentinel PASS. 실도면 정답 F1은 보고하지 않는다.
- kill condition: 낮은 Pearson이 빈 탐지기, 후보 recall 붕괴, alignment unknown의 제외로 만들어졌으면 무효. scale pass가 현재 0.7624에서 개선되지 않으면 scale-equivariant 주장을 죽인다.
- 예산: 로컬 CPU candidate/closure + GPU scoring. 최대 412,775 선분 정의는 chunk/tiling.
- seed 계획: C3 checkpoint 다섯 개. LLM sidecar는 모델별 seed가 아니라 고정 jury evidence로 취급하고 두 어휘 가문 단위로 bootstrap한다.

### C6 — FROZEN-TEST 단발 셀

- 가설: C0~C5를 통과한 단일 frozen 구성은 미접촉 CubiCasa test에서도 외부 전이를 유지한다.
- 개봉 조건: C0 PASS, C1 PASS, C3 최종 band PASS, C4 승격선 PASS, config/checkpoint/threshold/evidence schema hash 봉인.
- 지표: preregistered test P/R/F1/AUC와 클래스별 FP. 어떤 지표도 개봉 후 threshold 선택에 쓰지 않는다.
- 제안 합격선: 개봉 전에 evidence_grid에 수치와 판정식을 기록한다. 최소한 val에서 정한 GBDT 기준선과 비열등성 margin을 사전 봉인하되, 현 packet만으로 test 기대값을 발명하지 않는다.
- kill condition: test 개봉 후 재학습·threshold 변경·seed 선택을 하면 단발 원칙 위반으로 방법 전체를 무효화한다.
- 예산: 추론 1회와 보고서 생성.
- seed 계획: 다섯 seed를 보고 가장 좋은 seed를 고르지 않는다. 사전등록한 ensemble 또는 고정 대표 seed 한 방식만 택해 봉인한다.

### 6.1 종합 판정표

| 결과 | 판정 |
|---|---|
| 합성 F1≥0.80, meta≥0.90, Pearson≤0.35, gate-only가 distill 대비 meta≥+0.10이고 합성 비열등 | anti-silver VIABLE, kills: reigning |
| 합성 F1≥0.80, meta<0.50 | 합성 과적합, anti-silver 실패 |
| silver-distill이 모든 핵심 gate에서 우월 | kills: counter |
| silver-distill이 합성·meta에서 동등 또는 우월 | anti-silver 강한 주장 약화 |
| 낮은 Pearson만 달성 | 무판정; 성공으로 세지 않음 |
| PR-1 fidelity 또는 sentinel FAIL | 실험 미성립/BLOCKED |
| 양쪽 arm 모두 합성·meta 실패 | 두 이론 모두 무판정, 표현/후보 생성 문제로 환원 |

## 7. red team 티켓 응답

패널은 T8~T33의 전체 상세 원문을 제공하지 않는다. 따라서 아래에서는 보고서가 명시적으로 P3 또는 인접 실행체에 연결한 티켓만 다루고, 번호의 미제공 세부를 발명하지 않는다.

| 티켓 | P3 관련성 | 해소 방안 또는 수용 |
|---|---|---|
| T1 / PR-2 | 합성·외부·metamorphic·silver가 같은 평행 이중선 prior를 공유하면 독립 증거가 아니다. P3 최우선 위협이다. | 같은 drawing definition에서 네 truth source의 per-handle 불일치 행렬을 만든다. 판정자 5기가 아니라 두 어휘 가문으로 집계한다. source ablation C3와 real conflict C5를 결합하고, 비대각 전이가 무너지면 “독립” 주장을 철회한다. |
| T17 | CL-E의 동일-def 3원 불일치 구조와 연결된다. | 합성 대응이 가능한 정의에서 synthetic, closure/meta, silver의 pairwise·3-way disagreement를 보고한다. 사람 라벨이 있는 CubiCasa는 외부 네 번째 축으로만 둔다. |
| T2 / PR-1 | synthetic_truth가 실제 벽 생성기가 아니고 현재 B1 FAIL이라는 직접 공격이다. | C1을 하드 선결로 둔다. 현재 상태는 BLOCKED다. LINE/LWPOLYLINE/INSERT만으로 최종 판정하지 않고 SPLINE/ARC/HATCH, block transform, fragmented/비평행 조각, 장형 비벽 음성을 생성기에 반영한다. |
| T3 / T4 | E1 top-20 정렬 아티팩트와 ornith 원시 판정의 실재성은 “LLM high ∧ 결정론 0” 셀의 신뢰도에 영향을 준다. | CL-A가 끝나기 전 conflict cell을 오염의 증거로 단정하지 않는다. stable ID와 raw provenance가 없으면 unknown으로 둔다. 이 티켓은 gate-only 학습을 막지는 않지만 silver 비교 판결을 막는다. |
| T5 / PR-3 | CubiCasa/FloorPlanCAD NC label과 원 도면 권리 문제다. | counsel 서면 확인 전 신규 학습 arm 금지. 기존 다이제스트 수치는 배경 기준으로만 인용한다. 권리 미해결이면 외부축은 평가도 중지하고 합성·1.dwg 실험만 보고한다. 위험 수용이 아니라 하드 중단이다. |
| T6 | 평가 단위가 per-handle인지 집합 조립인지 혼동될 수 있다. | 주 단위를 per-handle wall_member로 고정한다. 후보 리본과 face는 설명/보조 단위다. set-level metamorphic은 별도 지표이며 per-handle F1과 평균하지 않는다. |
| T7 | 위반율-only metamorphic은 0벽 탐지기를 통과시킨다. | 0-wall, all-wall, mixed sentinel과 candidate recall을 C1/C3/C5에 의무화한다. alignment unknown을 pass 분모에서 조용히 빼지 않는다. |
| T10 / T23 | Graph IR adjacency 완전성 감사가 GNN 선결이다. | v0는 명시적 geometry gate와 snap graph만 쓴다. message passing은 adjacency audit PASS 후 옵션으로만 연다. 감사 실패 시 GNN 확장을 포기해도 P3 핵심 실험은 수행 가능하다. |
| T15 | learned cell이 seed-confounded될 위험이다. | gate-only/distill을 같은 초기화·batch 순서로 paired하고 다섯 seed를 모두 보고한다. 최고 seed 선택을 금지한다. seed 누락은 incomplete다. |
| T22 | 기존 방법 P1 통과 전 lift를 주장하는 문제다. | P3는 v1 0.2358과 GBDT 0.517을 고정 baseline으로 비교하되, CL-B/P1이 통과하지 않으면 “P1 대비 lift”라는 표현을 쓰지 않는다. 결과를 서로 다른 baseline 열로 분리한다. |
| T24 | raster 픽셀→handle 역투영이 부정확하면 FloorPlanCAD/VLM 결과가 오염된다. | exact synthetic projection harness PASS 전에는 raster 결과를 projection-unknown으로 둔다. raster mask나 VLM을 gate-only target으로 넣지 않는다. |
| T14 / T33 | firm-specific layer lexicon과 동어반복 위험이다. | 주 모델에서 원문 layer name을 제외하고 layer shuffle을 필수 변환으로 둔다. lexical arm은 CL-I 별도 실험으로 격리한다. |
| T34 | load-bearing 인용이 experiment_executed:false인 문제다. | 본 문서의 선행연구는 방법론 계보일 뿐 현 E2에서 실행됐다는 증거로 쓰지 않는다. 모든 실험 주장은 evidence_grid에서 executed/status를 별도 기록하고, 문헌 서지는 구현 전 재검증한다. |

### 7.1 남는 위험

- closure가 parallel-pair prior와 독립이라고 아직 증명되지 않았다. 벽 후보 생성 자체가 평행 쌍에 의존하면 closure도 같은 후보 우주에 갇힌다.
- 합성 fidelity를 통과해도 실제 firm 관례와 외부 국가 주거 분포의 차이는 남는다.
- LLM-Pearson≤0.35 밴드는 기존 0.2911 근처이므로 쉽게 만족될 수 있다. 그래서 성능·sentinel과 결합하지 않은 Pearson은 증거 가치가 없다.
- 두 어휘 가문 집계도 진정한 독립 두 표를 보장하지 않는다. 공통 사전학습·프롬프트 계보는 남을 수 있다.
- closure exact 계산의 자원 부담 때문에 근사를 쓰면 근사 오차가 새 관측 언어가 된다. exact subset과의 오차 감사를 별도로 해야 한다.

## 8. 인접 제안과의 관계

### 8.1 병합 가능한 지점

- CL-C / PR-1: P3의 합성 truth와 sentinel을 제공하는 필수 선결이다. P3는 자체적으로 낮은 fidelity 팩을 정당화하지 않는다.
- CL-D: metamorphic battery와 0벽/전벽 sentinel을 그대로 공용 심판으로 사용한다. P3는 scale·layer shuffle의 strict set 대응을 추가로 요구한다.
- CL-E: train-source×eval-source 교차요인과 동일-def disagreement를 공유한다. P3는 그 안의 silver-free arm과 silver-distill negative control을 명시적으로 분리한다.
- CL-F: gate-only vs silver-distill 1-epoch 대조를 고전ML→PU→GNN 사다리의 상설 통제 arm으로 편입할 수 있다. 각 rung에서 silver firewall을 반복한다.
- CL-B: fast_score, 후보 정규화, INSERT 전개, 단위 정박은 P3의 geometry 입력 품질을 높인다. 다만 CL-B의 성능 향상을 P3 효과로 잘못 귀속하지 않도록 frozen 후보 집합으로 paired 비교한다.
- CL-I: layer/이름 관례를 별도 prior로 계측하는 arm은 P3 주 모델에서 제외한 lexical 신호가 실제로 언제 유용한지 설명할 수 있다.
- CL-G: VLM은 배심원과 negative control로만 연결한다. raster 본선이나 silver 학습으로 합치지 않는다.
- CL-J: room/face-first는 closure가 유의미하다는 결과가 나온 뒤 별도 구조 가설로 확장할 수 있다. P3 v0에서 wall detector의 평가 단위를 face로 바꾸지는 않는다.

### 8.2 차별점

다수 제안은 잘 게이트된 silver라면 학습 또는 crosscheck 신호로 쓸 수 있다고 본다. P3의 차별점은 silver의 질을 더 잘 추정하는 것이 아니라 **주 학습 그래프에서 silver를 제거한 상태를 반증 가능하게 보존**하는 데 있다. silver는 checkpoint 동결 뒤 배심원으로 등장하고, 유일한 학습 사용은 분리된 negative-control 복제 모델이다.

또한 P3는 “LLM과 다르면 성공”이라는 단순 반대주의가 아니다. 합성·metamorphic·closure가 동시에 통과하지 않으면 불일치는 무지나 붕괴로 판정한다. 이 결합 gate가 Feyerabend식 다원주의를 무제약 상대주의와 구분한다.

### 8.3 이 제안이 죽어야 하는 조건

다음 중 하나가 재현되면 P3의 강한 주장은 죽어야 한다.

1. 같은 초기화·후보·split·seed에서 silver-distill이 합성 F1, metamorphic, sentinel, 외부 전이 모두 동등하거나 우월하다. 특히 전 gate에서 우월하면 kills: counter다.
2. gate-only의 낮은 Pearson이 빈 탐지기, 낮은 candidate recall, 과도한 threshold, alignment 제외로 생긴다.
3. PR-1 fidelity를 통과한 팩에서 합성 F1≥0.80을 얻어도 metamorphic<0.50이다. 이는 anti-silver가 아니라 합성 과적합이다.
4. closure와 metamorphic가 독립 evidence가 아니라 동일한 평행 이중선 후보 prior의 재표현임이 T1/T17에서 드러난다.
5. gate-only가 CubiCasa val에서 기존 GBDT F1 0.517에 도달하지 못하고, 오류 분석에서도 recall·FP 구조의 보완을 보이지 못한다. 철학적 가능성은 남아도 E2 실용 경로로서는 죽는다.
6. silver를 제거·셔플했을 때 gate-only checkpoint가 바뀐다. 이는 구현 누수이므로 결과 전체가 무효다.
7. silver가 실제로 유용한 도면군을 사전 정의된 geometry 조건으로 안정적으로 식별하고, 해당 조건부 distillation이 합성·meta·외부 사람 라벨 모두를 개선한다. 이 경우 전면 anti-silver보다 조건부 silver 사용이 더 좋은 이론이다.
8. 합성팩 충실도와 권리·정합 선결을 끝내 닫지 못한다. 이 경우 P3는 반증된 것이 아니라 시험 불가능 상태로 폐기해야 한다.

### 8.4 최종 실행 권고

현재 즉시 허용되는 것은 C0 누수 계약과 C2의 배관 smoke test뿐이다. C2 결과를 방법론 승패로 해석해서는 안 된다. 우선순위는 C1의 합성 fidelity와 sentinel을 닫고, 이어 같은 초기화의 1-epoch paired probe를 실행하는 것이다. A 결과가 나오면 C3~C5로 확장하고, B 결과가 나오면 anti-silver를 방어하기 위한 추가 튜닝 대신 counter-theory 승리를 기록한다. 어느 쪽도 아니면 비용을 늘리기 전에 후보 생성과 truth-source 독립성을 재감사한다.

현재 도시어 판정은 **DESIGN COMPLETE / EXECUTION BLOCKED BY PR-1 FIDELITY**다. 이는 fake PASS가 아니며, 패킷의 실측 B1 FAIL과 S 음성 부재를 그대로 보존한 판정이다.

DOSSIER_COMPLETE: feyerabend_P3
