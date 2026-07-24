# calibration_P2 방법론 심층 도시어

## 문서 상태와 판정 범위

이 문서는 P2 「반복 구조 기반 weak supervision + PU 고전 ML」을 실제로 구현하고 동결 평가할 수 있게 만드는 사전등록 수준의 실행 계획이다. 새 실험을 수행했다거나 새 성능을 측정했다고 주장하지 않는다. 관측값은 패킷의 2026-07-18 실측 다이제스트에서만 가져왔고, 그 밖의 수치는 모두 이 도시어가 제안하는 하이퍼파라미터, 합격선, 시드 또는 계획 예산이다. 문헌명과 방법론 계보는 일반 지식에 근거하며, 실험 보고서에 넣기 전 서지 메타데이터를 다시 확인해야 한다.

현재 결론은 **OPEN**이다. 특히 합성팩 충실도 B1이 KS 0.5792, TV 0.265로 FAIL이고, FloorPlanCAD 자산은 래스터 5,308장과 bbox/segmask뿐이며 벡터 SVG가 없으므로, 현 상태의 FloorPlanCAD를 “exact per-handle line truth”라고 부를 수 없다. 따라서 아래 계획은 실행 가능하지만, P2 claim을 해결하는 최종 셀은 truth 계약과 라이선스 게이트가 닫힐 때까지 열 수 없다.

패킷 안에서 S/F/M이라는 표기가 “합성팩 S/F/M”과 “synthetic/FloorPlanCAD/metamorphic”의 약자로 겹칠 여지가 있다. 이를 없애기 위해 모든 manifest는 다음 이름을 쓴다.

- S_exact: 생성 과정에서 wall_member(handle)가 직접 기록된 합성 handle truth. 충실도 게이트를 통과한 버전만 최종 판정에 사용한다.
- F_exact: FloorPlanCAD의 독립 held-out line truth. 현재 보유한 raster mask 자체는 F_exact가 아니다. 원 벡터와 handle 대응표 또는 독립 line annotation이 확보되고 T24 역투영 검증을 통과해야만 이 이름을 부여한다.
- M_gate: rigid/unit/scale/explode/layer-rename 변환과 0벽/전벽 sentinel을 포함한 안정성 시험. semantic truth의 대체물이 아니다.
- C_train/C_val/C_test: CubiCasa5k SEG-IR의 제3자 Wall-class line truth. 현재 정확한 외부 벡터 평가축이지만 P2 원 claim의 F_exact를 자동 대체하지 않는다. 대체하려면 평가 전에 명시적 계약 개정과 새 artifact schema가 필요하다.

“precision at coverage”의 모호성도 사전에 제거한다. 최종 합격식의 coverage는 선택적으로 예측한 전체 entity 비율이 아니라 **wall truth coverage = recall = TP/(TP+FN)** 로 정의한다. 즉 합격식은 precision 0.92 이상인 threshold가 wall recall 0.50 이상을 동시에 달성한다는 뜻이다. selective abstention coverage는 별도 진단으로만 보고한다.

# 1. 이론적 근거·선행연구

## 1.1 문제를 다섯 층으로 분해하는 이유

P2는 “P1 점수에 분류기 하나를 얹는 것”이 아니다. 다음 다섯 층을 분리해야 P1 편향을 복제하는지, 반복 구조가 실제로 추가 정보를 주는지, calibration이 drawing shift에서 살아남는지를 판별할 수 있다.

1. **고정밀 anchor 생성**: P1의 서로 다른 증거 채널이 동시에 동의할 때만 positive anchor를 만든다. DIMENSION, TEXT, MTEXT, LEADER/MLEADER처럼 provenance가 명백한 annotation primitive만 negative anchor로 쓴다. 단순히 layer명이 낯설거나 길이가 짧다는 이유로 negative를 만들지 않는다.
2. **labeling function 결합**: 각 규칙은 positive, negative, abstain 중 하나와 confidence를 낸다. 서로 같은 P1 channel에서 파생된 규칙의 상관을 명시한 label model이 latent label posterior를 만든다.
3. **PU 학습**: positive anchor는 양성이지만, unlabeled에는 wall과 non-wall이 섞여 있다. 이를 일반 음성으로 오인하지 않고 positive-unlabeled risk와 sensitivity analysis로 학습한다.
4. **반복 구조 일반화**: 같은 block role과 transform-normalized geometry가 여러 instance에서 반복될 때의 일관성을 feature와 group key로 사용한다. 반복 빈도만으로 wall이라고 하지 않는다. 반복되는 door/window/direction symbol이 정확히 반례이기 때문이다.
5. **drawing-shift calibration**: ranker의 AUPRC와 probability의 신뢰도를 분리한다. 회사·style·drawing 분포가 바뀌어도 frozen calibrator가 REL/RES band를 만족하는지를 별도 outer split에서 검사한다.

## 1.2 방법론 계보

아래 문헌과 시스템명은 일반 지식 기반이며 서지사항은 최종 보고 전 요검증 대상이다.

| 계보 | 구체 방법 | P2에서의 역할 | 주의점 |
|---|---|---|---|
| Positive–Unlabeled learning | Elkan–Noto의 positive-only learning, du Plessis·Niu·Sugiyama의 unbiased PU risk, Kiryo 등의 non-negative PU, Mordelet–Vert의 BaggingPU, Bekker–Davis의 selected-at-random 논의 | P anchor와 U 혼합에서 logistic/boosted-tree ranker를 학습하고 class-prior 및 selection-bias 민감도를 노출 | 고전 SCAR 가정은 P1 anchor에 거의 확실히 강하다. 이를 숨기면 안 된다 |
| Data programming / weak supervision | Snorkel 계열의 labeling function과 correlation-aware label model, Dawid–Skene 계열 latent annotator model | P1, topology, repetition, annotation provenance, 선택적으로 E1.5를 서로 다른 LF로 결합 | 동일 근거를 복제한 LF를 독립 투표로 세면 확신만 부풀린다 |
| 확률 calibration | Platt scaling, isotonic regression, beta calibration, Murphy의 Brier decomposition | raw score를 probability로 바꾸고 REL, RES, Brier를 drawing-shift split에서 측정 | calibration set과 test drawing을 섞으면 성능 누출이다 |
| Covariate/domain shift | density-ratio/importance weighting 계열, group-wise validation, GroupDRO의 worst-group 관점 | unseen company/style의 calibrator 선택과 최악 subgroup 진단 | unlabeled target 통계로 보정할 수는 있어도 test label을 보정에 쓰면 안 된다 |
| 반복 및 graph fingerprint | Weisfeiler–Lehman 계열 graph fingerprint, transform-canonical shape matching, CAD block instance/role 분석 | 동일 block definition, geometry fingerprint, transform-equivalent role을 찾고 같은 fold로 묶음 | fingerprint 자체를 predictive ID로 넣으면 memorization이 된다 |
| 고전 tabular ML | regularized logistic regression, histogram gradient boosting | 선형 한계와 비선형 상호작용을 같은 feature contract에서 비교 | 현재 CubiCasa logistic F1 0.053과 HistGradientBoosting F1 0.517의 격차는 비선형성이 중요하다는 직접 근거다 |

## 1.3 이 제안이 성립하려면 필요한 가정

P2가 성공하려면 다음이 동시에 성립해야 한다.

- P1 positive anchor의 precision은 높되, 모든 주요 wall grammar에 최소한의 support가 있어야 한다.
- anchor에 없는 wall도 P anchor와 feature-space에서 일정한 overlap을 가져야 한다. 완전히 분리된 grammar는 PU가 발견할 수 없다.
- 반복 stability, face contribution, junction context가 CubiCasa에서 확인된 긴 평행 non-wall 구조를 wall과 구분하는 추가 정보를 가져야 한다.
- layer/text token이 도움이 되더라도 geometry-only 모델의 순위를 무너뜨릴 만큼 지배해서는 안 된다.
- label model이 상관 LF를 한 표씩 세지 않고 dependency를 흡수해야 한다.
- probability calibration이 source drawing의 class ratio만 외운 것이 아니어야 한다.

반대로, P1가 놓친 grammar가 positive anchor와 feature overlap을 전혀 갖지 않거나, 반복 feature가 symbol 반복을 wall 반복보다 더 강하게 포착하거나, no-layer arm이 붕괴하면 P2의 이론적 근거는 무너진다. PU는 “라벨이 없는 새 의미”를 마술처럼 복원하는 장치가 아니다.

# 2. 알고리즘 정확 스펙

## 2.1 입력, 출력, 평가 단위

한 drawing d의 정규화된 SEG-IR entity instance를 i라 하며 입력 record는 다음 필드를 갖는다.

- drawing_id, source_kind, source_split
- source_handle과 instance_key
- block_definition_fingerprint, geometry_fingerprint, role_fingerprint
- transform_class와 transform-normalized geometry
- entity_type, layer/text provenance
- points 또는 curve primitive, parent block 관계

source_handle, path, vendor ID는 lineage와 감사 로그에만 남기고 feature matrix에는 넣지 않는다. instance_key는 repeated INSERT의 stability를 계산하기 위한 내부 key다. 최종 semantic 평가 단위는 packet 계약대로 source_handle이다. 같은 source_handle이 여러 instance에 나타나면 instance prediction을 사전등록된 max aggregation으로 접어 현재 fast_score의 per-handle 의미와 맞춘다. mean과 noisy-or는 진단 arm일 뿐 최종 합격식에는 쓰지 않는다.

모델 출력은 handle별 다음 record다.

- p_raw: uncalibrated wall score
- p_cal: frozen drawing-shift calibrator를 지난 probability
- pred_at_operating_point
- model_variant: logistic 또는 boosted_tree, layer-on/off
- feature_schema_hash, LF_schema_hash, split_manifest_hash, model_hash, calibrator_hash
- evidence: LF vote, anchor 상태, 주요 feature contribution, aggregation provenance

## 2.2 leakage-safe group 만들기

개별 row를 임의 분할하지 않는다. 먼저 아래 equivalence edge를 만든 뒤 connected component 전체를 하나의 group으로 묶는다.

- 동일 source drawing의 동일 block definition
- 동일 transform-normalized geometry fingerprint
- 동일 block role fingerprint
- 중첩 INSERT를 따라 같은 원 정의로 환원되는 instance
- 서로 다른 path에 있어도 canonical geometry가 동일한 vendor/template duplicate

group_id는 canonical content의 salt된 hash로 만들되 feature에는 넣지 않는다. hash 전 canonicalization은 translation, rotation, reflection, unit scale을 제거하고, non-uniform scale/shear는 별도 transform_class로 보존한다. fold assignment는 group_id와 drawing_id의 양쪽 제약을 만족하는 connected-component 단위 greedy bin packing으로 고정한다. 한 component가 여러 drawing에 걸치면 그 drawing들도 같은 fold로 결박한다. 이로 인해 특정 split 크기가 불균형해져도 leakage 방지가 우선이다.

split audit는 다음을 모두 0으로 요구한다.

- train–val, train–test, val–test 사이 block_definition_fingerprint 교집합
- 세 split 사이 geometry_fingerprint 교집합
- raw handle/path/vendor token이 feature column이나 vocabulary에 포함된 수
- test manifest를 model-selection process가 연 횟수

## 2.3 feature 정의

모든 연속 feature는 train fold에서만 fit한 median/IQR 또는 quantile transform으로 정규화한다. drawing-relative feature는 해당 drawing의 unlabeled geometry만 사용하므로 test에서도 계산 가능하다. 절대 x/y 좌표는 쓰지 않는다.

| family | 정확한 feature | 정의 |
|---|---|---|
| primitive | type one-hot, segment_count, is_closed | LINE/LWPOLYLINE/ARC/SPLINE 등 normalize 이후 provenance를 보존 |
| 길이 | log_length_rel | log(1 + length / median_nondegenerate_length_d). truth와 무관하게 drawing 전체 nondegenerate entity length median만 사용 |
| 방향 | sin2theta, cos2theta | 벽의 무방향성을 반영해 각도를 2배 주기로 표현 |
| 곡률 | total_turn, mean_abs_curvature, max_abs_curvature, arc_sweep, curvature_bins | polyline turn과 ARC/SPLINE sampling에서 얻되 sampling tolerance는 schema에 동결 |
| 평행 mate | parallel_count_q, best_overlap, offset_rel_q, mate_angle_error_q | angle bucket과 spatial index로 후보를 만들고 drawing-relative offset/length ratio로 표현 |
| 교차·정션 | endpoint_degree_1/2, T_degree, X_cross_count, snapped_component_size | snap graph에서 endpoint와 interior crossing을 구분 |
| 폐면 기여 | bounded_face_count_delta, min_face_area_rel, face_bridge_flag | planar graph G에서 edge 제거 전후 bounded face 수 변화와 인접 face 면적을 계산 |
| P1 증거 | parallel, thickness, junction, layer 및 P1 score/name-blind score | evidence_grid/fast_score와 같은 channel contract. layer-off arm에서는 layer와 name-derived column을 완전히 제거 |
| block 반복 | log1p_block_instances, log1p_role_instances, fingerprint_frequency | training/test 각 drawing 내부 빈도만 사용. corpus-wide fingerprint lookup count는 feature로 쓰지 않음 |
| transform stability | valid_transform_fraction, role_score_MAD, geometry_residual_q, P1_vote_agreement | 같은 role을 inverse-transform한 뒤 geometry와 P1 증거의 dispersion을 계산 |
| local context | neighbor_type_hist, neighbor_length_quantiles, face/junction neighborhood summary | 고정 hop의 topology summary. graph ID 자체는 넣지 않음 |
| token arm | normalized layer token, adjacent text token, entity-type token | train-only vocabulary, digit/path/vendor-like token 제거, rare token은 OOV로 접음 |

반복 feature의 핵심 안전장치는 “빈도 단독 positive LF 금지”다. 높은 fingerprint_frequency는 wall일 수도, door/window/direction symbol일 수도 있다. positive 방향으로 작동하려면 wall-like mate/face/junction 조건과 결합되어야 한다.

## 2.4 anchor와 labeling function

각 LF는 -1, 0, +1과 confidence를 반환한다. 0은 음성이 아니라 abstain이다.

| LF | vote | 조건과 독립성 처리 |
|---|---|---|
| LF_P1_INTERSECTION | +1 | name-blind P1의 서로 다른 geometry channel이 strict threshold에서 동시에 동의하고 M rigid/unit/scale transform에서 유지될 때. threshold는 S/C 개발 fold에서만 선택 후 동결 |
| LF_PAIR_FACE | +1 | 유효 평행 mate와 bounded-face 기여가 함께 있고 annotation provenance가 아닐 때 |
| LF_REPEAT_STABLE | +1 | 여러 instance의 role geometry와 P1 vote가 안정적이며 LF_PAIR_FACE 또는 wall-like junction이 함께 있을 때 |
| LF_DIMENSION | -1 | 원 entity provenance가 DIMENSION 계열일 때만. explode 뒤 선분 모양만 보고 dimension이라 추정하지 않음 |
| LF_TEXT | -1 | TEXT/MTEXT 및 그 명시적 leader child일 때 |
| LF_ANNOTATION | -1 | LEADER/MLEADER 등 명백한 annotation primitive. HATCH는 wall 표현일 가능성이 있어 단독 negative 금지 |
| LF_TOKEN_WALL | +1 또는 -1 | layer/text arm에서만 사용. train vocabulary와 사전등록 lexicon으로 제한하고 별도 dependency family로 묶음 |
| LF_E15 | +1 또는 -1 | E1.5 B1 0.70 이상이면서 B4 Pearson 0.70 이상일 때만 활성. 다섯 judge를 다섯 LF로 만들지 않고 한 correlated family LF로만 추가 |

현재 다이제스트에서 detector–silver Pearson은 0.2911이고 judge 다섯 기가 약 두 어휘 가문으로 갈리므로 LF_E15 gate는 닫혀 있다. 따라서 cheapest probe와 주 실험의 기본값은 silver-off다. E1.5를 truth나 평가 label로 사용하는 경로는 코드 수준에서 금지한다.

positive anchor P는 LF_P1_INTERSECTION과 최소 하나의 비동일계열 geometry/topology LF가 +1이고 어떤 hard-negative LF도 -1이 아닌 row다. negative anchor N은 명백한 annotation provenance LF가 -1인 row다. 나머지는 U다. token LF만으로 P/N anchor를 만들지 않는다.

## 2.5 correlation-aware label model

LF matrix를 Lambda, latent wall label을 y라 한다. 독립 투표 수 세기를 피하기 위해 LF를 다음 dependency family로 묶는다.

- P1 geometry family
- face/junction family
- repetition family
- annotation provenance family
- token family
- gated E1.5 family

학습 objective는 family별 accuracy parameter와 명시된 pairwise dependency parameter를 가진 generative model의 regularized marginal likelihood다.

    theta_hat = argmax_theta sum_i log sum_y P_theta(Lambda_i, y) - lambda_dep ||theta_dep||_1
    q_L(i) = P_theta(y_i = 1 | Lambda_i)

P와 N은 posterior의 boundary condition으로만 사용해 각각 q_L=1, q_L=0으로 clamp한다. U의 posterior는 epsilon과 1-epsilon 사이로 clip한다. LF accuracy와 dependency는 outer train의 inner folds에서 cross-fit하여, 한 row의 posterior를 그 row를 포함해 fit한 label model이 만들지 않게 한다.

식별성 감사로 LF family 하나씩 제거한 posterior 변화, family 간 mutual information, 동일-def 불일치 표를 저장한다. 한 family 제거만으로 posterior 대부분이 뒤집히면 label model은 “다중 증거”가 아니라 단일 규칙의 복제이므로 main arm에서 제외한다.

## 2.6 PU logistic

z_i=1은 positive anchor에 선택되었음을 뜻한다. 고전 SCAR baseline은 anchor-vs-unlabeled classifier g(x)=P(z=1|x)를 fit하고, held-out positive anchor에서 selection propensity c를 추정해 p_PU=min(g/c,1)로 보정한다. 이 arm은 비교 기준이지 기본 신뢰 모델이 아니다.

주 logistic arm은 class prior pi에 대한 non-negative PU risk와 label-model soft loss를 결합한다. f_beta(x)=beta^T x이고 logistic loss를 ell이라 할 때,

    R_pos = pi * mean_P ell(f(x), 1)
    R_neg_raw = mean_U ell(f(x), 0) - pi * mean_P ell(f(x), 0)
    R_nnPU = R_pos + max(0, R_neg_raw)
    R_soft = mean_i w_i[-q_L(i) log p_i - (1-q_L(i)) log(1-p_i)]
    L_log = eta R_nnPU + (1-eta) R_soft + lambda_2 ||beta||_2^2

w_i는 anchor에서 1, U에서는 2|q_L-0.5|로 두어 애매한 pseudo-label의 영향만 줄인다. pi는 mixture-proportion estimator 두 종류와 exact-label 개발 fold의 허용 범위로 만든 preregistered interval에서 탐색한다. 선택한 pi 하나의 결과뿐 아니라 interval 양끝의 lift, subgroup recall, calibration도 함께 보고한다. 어느 허용 pi에서 결론이 뒤집히면 PASS가 아니라 SENSITIVE다.

SCAR 위반은 개발 truth의 true positive 안에서 anchor-selected 여부를 x로 예측하는 audit와 grammar별 selection rate로 확인한다. 예측 가능성이 높다고 SCAR arm만 폐기할 수는 있지만, 어떤 grammar의 positive anchor support가 0이면 SAR 보정도 식별 불가능하므로 P2 전체 kill 후보가 된다.

## 2.7 boosted-tree PU

HistGradientBoosting 계열은 현재 CubiCasa 6-feature 학습 경로와 직접 비교하기 위해 유지한다. 비분해 nnPU risk를 억지로 classifier API에 넣지 않고 다음 bagged posterior-imputation 절차를 쓴다.

1. cross-fitted PU logistic p_PU와 label posterior q_L의 clipped log-odds를 preregistered weight alpha로 합쳐 q_star를 만든다.
2. 각 seed b에서 P는 1, N은 0으로 고정하고 U label은 Bernoulli(q_star)로 한 번 추출한다.
3. sample weight는 anchor 1, U는 2|q_star-0.5|로 둔다.
4. drawing/group bootstrap sample에 HistGradientBoosting을 fit한다.
5. out-of-fold probability를 seed 평균해 raw boosted-tree score로 쓴다.

이 방식은 label imputation의 Monte Carlo 변동을 seed 분산으로 드러낸다. 비교 arm으로 P-vs-U BaggingPU tree와 P/N-only tree도 남긴다. 최종 boosted-tree가 단일 seed에서만 band를 통과하면 실패다.

## 2.8 calibration과 Brier 분해

ranker 선택과 calibration 선택을 분리한다. ranker hyperparameter는 inner train/val AUPRC와 worst-grammar recall로 고른다. 그 뒤 outer calibration fold에서 다음 후보를 비교한다.

- global Platt
- isotonic
- beta calibration
- shift-aware beta: raw score의 beta terms에 unlabeled drawing summary z_d를 더한 logistic recalibration
- density-ratio-weighted beta: train-vs-target-style classifier로 얻은 capped weight 사용

z_d에는 label을 쓰지 않고 length/type/repetition/junction 분포의 train-fitted summary만 넣는다. final test drawing의 label 또는 prevalence는 calibration 입력이 될 수 없다.

calibration bin은 outer val에서 만든 equal-frequency 경계를 freeze한다. entity weight를 w_i라 하고 bin k의 평균 예측과 평균 truth를 p_bar_k, y_bar_k, 전체 prevalence를 y_bar라 하면,

    REL = sum_k W_k (p_bar_k - y_bar_k)^2
    RES = sum_k W_k (y_bar_k - y_bar)^2
    Brier = sum_i w_i (p_i-y_i)^2

primary는 per-handle pooled weight이고 drawing-equal weight 결과를 함께 보고한다. 합격식은 REL 0.03 이하, RES 0.02 이상이다. bin 수와 경계, empty-bin 처리, clip epsilon은 preregistration JSON에 봉인한다.

## 2.9 학습·추론 의사코드

    build_manifests():
        canonicalize every source without using labels
        compute block/geometry/role fingerprints
        union all leakage-equivalent rows
        assign connected components to train/val/test groups
        assert zero fingerprint overlap and freeze hashes

    fit_p2(train_manifest, val_manifest):
        extract/cache geometry, topology, repetition, P1 and optional token features
        run M transforms needed for stability features
        emit LF matrix; derive P, N, U
        cross-fit dependency-aware label model -> q_L
        estimate class-prior interval and SCAR/SAR diagnostics
        for each model/hyperparameter/seed:
            fit PU logistic or bagged posterior-imputation boosted tree
            produce group-held-out raw predictions
        select ranker using val only
        fit and select frozen shift calibrator using nested drawing/company/style folds
        freeze feature/LF/model/calibrator hashes and operating threshold

    evaluate_once(test_manifest):
        reject if any frozen hash differs or test-contact ledger is nonempty
        extract features with frozen schema and vocabulary
        infer p_raw, p_cal; aggregate instance -> source_handle by frozen max rule
        compare only with S_exact/F_exact/C_test truth appropriate to artifact contract
        compute paired drawing-cluster bootstrap against frozen P1
        run M_gate, leakage audit, layer ablation, subgroup and OOD audits
        write wsd_eval_p2.json and mandatory evidence workbook atomically

## 2.10 하이퍼파라미터 공간

아래 값은 측정 결과가 아니라 제안 탐색공간이다. 최종 값은 test를 열기 전에 preregistration에 봉인한다.

- logistic: L2 strength {1e-4, 1e-3, 1e-2, 1e-1, 1}; eta {0.25, 0.5, 0.75, 1.0}
- class-prior: estimator 교집합 안의 low/mid/high 세 점; 교집합이 없으면 kill 또는 별도 sensitivity-only 판정
- label dependency regularization: {1e-3, 1e-2, 1e-1}
- tree: max_leaf_nodes {15, 31, 63}, learning_rate {0.03, 0.06, 0.1}, max_iter {100, 250, 500}, min_samples_leaf {20, 100, 500}, L2 {0, 1, 10}
- posterior pool alpha {0.25, 0.5, 0.75}
- token arm: train frequency cutoff와 vocabulary cap을 preregister하고 OOV 처리 고정
- operating threshold: val에서 precision 0.92를 만족하는 threshold 중 recall 최대. 없으면 해당 arm FAIL
- seed set: {7, 17, 29, 43, 71}. split은 seed와 무관하게 한 번만 고정하고 seed는 model/bagging/imputation에만 사용

# 3. 벽 과업 적응 설계

## 3.1 현재 관측이 요구하는 설계 변화

CubiCasa의 geometry detector v1은 val에서 precision 0.134, recall 0.981, F1 0.2358이었고, 최소길이 필터의 ceiling도 F1 0.335였다. FP 주범은 Direction, BoundaryPolygon, Door, Window, DimensionMark로 모두 평행 구조를 가질 수 있었다. 따라서 P2의 추가 가치는 더 넓은 두께 grid가 아니라 다음 세 가지여야 한다.

- 반복되는 block role이 wall-like face/junction 문맥 안에서 안정적인지 구분
- 같은 긴 평행 구조라도 face를 경계 짓는 wall과 symbol/boundary/annotation을 topology와 provenance로 분리
- drawing/style가 바뀔 때 probability와 operating threshold가 유지되는지 calibration으로 검증

반면 CubiCasa에서 6-feature HistGradientBoosting은 val precision 0.860, recall 0.370, F1 0.517, AUC 0.9215였고 logistic F1은 0.053이었다. 이는 두 가지를 뜻한다. 첫째, P2의 logistic은 필요한 비선형 상호작용을 설명하는 sanity baseline이지 승리를 기대하는 유일 모델이 아니다. 둘째, P2 boosted-tree는 “tree를 썼다”만으로 새 방법이 아니다. 반복/face/transform feature와 weak/PU supervision, leakage-safe grouping, shift calibration이 각각 독립 ablation에서 추가 가치를 보여야 한다. supervised 6-feature HGB는 truth를 학습에 쓴 참고 arm으로 남기되, weakly supervised P2와 같은 자격의 contender로 섞지 않는다.

## 3.2 CubiCasa SEG-IR 축

기존 cubicasa_ir 산출물의 drawing_id, segment handle, Wall-class truth를 그대로 소비한다. cubicasa_ml의 현재 6-feature extraction과 drawing gid를 확장하되 다음 원칙을 지킨다.

- C_train에서는 exact truth를 P2 ranker label로 쓰지 않고, anchor audit와 supervised reference arm에만 사용한다.
- C_val truth는 hyperparameter, LF threshold, calibrator, operating point 개발에 쓸 수 있다.
- C_test 400장은 dedicated evaluator에서 방법당 단 한 번만 연다.
- 현재 split train 4,200 / val 400 / test 400과 선분 규모를 유지하되 fingerprint duplicate가 split을 가로지르면 원 split을 그대로 신뢰하지 않고 충돌을 보고한다. test를 재배치해서는 안 되므로 충돌이 발견되면 test 접촉 전에 dataset contract를 다시 봉인해야 한다.
- CubiCasa는 layer neutral이므로 layer-off가 자연 primary다. class_of_handle은 평가와 FP taxonomy에만 쓰고 feature/LF에는 절대 넣지 않는다.
- 픽셀 좌표의 도면별 축척이 미상이므로 절대 mm feature를 primary에서 제거한다. drawing-relative length/offset와 transform stability를 사용한다.

## 3.3 FloorPlanCAD 래스터 축

현재 FloorPlanCAD는 raster+bbox/segmask이고 vector SVG가 없다. 따라서 raster edge를 자동 tracing해 만든 선분을 “exact handle truth”라고 부르면 안 된다. 가능한 경로는 둘뿐이다.

1. 원 vector/source handle과 mask의 provenance mapping을 합법적으로 확보한다.
2. 독립 annotator가 fixed vectorization 위에서 line membership을 라벨하고, pixel-to-line ambiguity와 inter-annotator adjudication을 별도 truth artifact로 남긴다.

어느 경로든 synthetic exact rendering에서 handle별 unique-color render와 mask projection round trip을 검증하고, ambiguous crossing/occlusion/line-width 사례를 제외 규칙이 아니라 explicit uncertain label로 기록해야 한다. T24를 통과하기 전 FloorPlanCAD 20장 cheapest probe는 raster-level 진단일 뿐 P2 semantic metric이나 F_exact band를 해결하지 못한다. 또한 “license-quarantined” 상태이므로 PR-3 counsel 서면 확인 전에는 학습·파생물 생성·배포를 시작하지 않는다.

## 3.4 1.dwg 실도면 축

1.dwg에는 도면정의 384개가 있고 최대 정의가 412,775 선분이어서 all-pairs feature는 현실적이지 않다. 이 축은 exact semantic truth가 없으므로 다음으로 제한한다.

- block definition과 nested INSERT를 normalize/insert_expand 경로로 전개
- instance_key를 보존한 반복 role과 transform stability 산출
- fast_score의 P1 evidence를 cache하고 name-blind/full arm 동시 생성
- M rigid/unit/scale/explode/layer-rename consistency와 0벽/전벽 sentinel 실행
- definition별 positive rate, repeated-role disagreement, runtime/memory, E1.5와의 진단 상관 보고

실도면 반복 일관성이나 E1.5는 학습 신호·진단일 뿐 semantic truth가 아니다. real drawing의 반복 일관성이 좋아도 S_exact/F_exact 성능이 나쁘면 P2는 실패다.

성능을 위해 angle bucket + projected interval index + spatial hash로 parallel/intersection candidate를 만들고, 작은 definition에서 evidence_grid와 bit/metric equivalence를 먼저 증명한다. 412,775 선분 정의를 무조건 materialize하지 않고 drawing shard별 columnar cache와 memory map을 사용한다.

## 3.5 S_exact와 M_gate 축

합성 truth는 wall_member(handle)가 생성 단계에서 직접 기록되므로 label 자체는 exact할 수 있다. 그러나 현재 합성팩은 LINE/LWPOLYLINE/INSERT 세 종류뿐이고 실도면에는 SPLINE, ARC, HATCH가 혼재하며 B1 fidelity가 FAIL이다. 따라서 현재 팩은 unit test와 개발에는 쓸 수 있어도 최종 real-world 일반화 판정 자격이 없다.

S_exact 생성기는 다음 grammar를 manifest에 명시해야 한다.

- straight double-line, single-line, thick polyline, arc/curved wall, fragmented/nonparallel wall
- nested block/INSERT, reflection, rotation, unit/scale variation
- door/window opening, T/X/L junction, open-plan/partial enclosure
- repeated non-wall symbol, dimension/text/leader, long boundary polygon
- 0벽 sentinel, 전벽 sentinel

M_gate는 rigid와 unit만이 아니라 현재 실패한 scale arm을 반드시 포함한다. scale invariance를 feature contract가 보장하지 못하면 S/F lift가 나와도 PASS가 아니다.

# 4. 데이터·컴퓨트 요구

## 4.1 필요한 데이터 artifact

- immutable source manifest: source_kind, license_state, split, drawing hash
- SEG-IR와 exact truth를 분리한 파일: model process에는 truth path를 주지 않음
- fingerprint/group manifest와 overlap audit
- instance-level feature shards와 handle aggregation map
- LF sparse matrix, dependency-family manifest, P/N/U assignment
- model OOF prediction, calibration fold prediction, seed별 prediction
- M transform pair manifest와 sentinel truth
- 최종 JSON 및 증거 XLSX

truth 파일과 feature extractor는 별도 process 권한으로 분리한다. evaluator만 truth를 읽고, training log에 handle label이 노출되지 않게 한다.

## 4.2 로컬 CPU 실행

다이제스트상 feature extraction과 고전 ML은 RAM 64GB 로컬 CPU에서 충분하며 32GB soft cap을 둔다. 실행 설계는 다음과 같다.

- float32 columnar shard와 categorical code 사용
- drawing 또는 block component 단위 streaming extraction
- sparse LF matrix와 token matrix 분리
- geometry/topology cache 재사용; seed마다 feature를 다시 계산하지 않음
- HistGradientBoosting은 모든 grid를 동시에 메모리에 올리지 않고 successive-halving 방식으로 val에서 줄임
- process worker마다 큰 geometry array를 복사하지 않도록 memory map 또는 shared read-only array 사용
- peak RSS가 32GB를 넘으면 해당 run을 중단하고 shard/feature schema를 줄인다. 64GB를 쓸 수 있다는 이유로 soft cap을 완화하지 않는다.

계획 예산은 개발 smoke 1 CPU-day 이내, full CubiCasa feature extraction 1–2 CPU-days, model/seed sweep 1–2 CPU-days, final frozen evaluation 1 CPU-day 이내다. 이는 제안 예산이지 측정된 runtime이 아니다. 가장 큰 1.dwg definition은 별도 stress cell로 격리하며 전체 sweep의 성공 조건으로 무리하게 묶지 않는다.

## 4.3 GPU와 DGX

P2 main path는 GPU를 요구하지 않는다. RTX 5070 Ti 16GB는 선택적으로 raster projection QA나 tree library의 비결정적 가속을 시험할 수 있지만 primary result는 CPU 재현본이어야 한다. DGX Spark는 현재 unreachable이므로 계획과 critical path에서 제외한다. DGX가 복구되어도 P2 pass를 위해 재실행할 이유가 없고, 고전 ML CPU artifact와 bit/metric equivalence를 깨는 가속 결과는 진단으로만 둔다.

# 5. 구현 계획

## 5.1 제안 파일 골격

아래는 후속 구현 시 만들 모듈이다. 이 도시어 작성 단계에서는 생성하지 않는다.

- tools/e2/p2/schema.py: row schema, feature schema hash, source namespace
- tools/e2/p2/fingerprint.py: block/geometry/role canonical fingerprint와 union-find group
- tools/e2/p2/features.py: geometry/topology/repetition/transform feature
- tools/e2/p2/labeling.py: LF registry, family dependency, P/N/U assignment
- tools/e2/p2/label_model.py: correlation-aware generative label model와 cross-fitting
- tools/e2/p2/pu_logistic.py: nnPU/SCAR/SAR sensitivity logistic
- tools/e2/p2/pu_tree.py: BaggingPU와 posterior-imputation HistGradientBoosting
- tools/e2/p2/calibration.py: Platt/isotonic/beta/shift-aware calibration
- tools/e2/p2/evaluate.py: paired metrics, bootstrap, subgroup/OOD/M/leakage gate
- tools/e2/p2/evidence_xlsx.py: mandatory workbook
- tools/e2/p2/run.py: extract, fit, freeze, eval의 명시적 state machine
- tests/e2/p2/: fingerprint invariance, split leakage, LF abstain, PU risk, calibration, aggregation, test-contact guard
- reports/e2/p2/prereg_p2.json: frozen contract
- reports/e2/p2/wsd_eval_p2.json 및 wsd_eval_p2.xlsx: 최종 산출

## 5.2 기존 접속점

- detect/normalize.py: LINE 외 LWPOLYLINE/ARC/SPLINE normalization과 provenance를 받는다.
- detect/insert_expand.py: nested INSERT world transform을 받되 source role과 instance path를 잃지 않도록 adapter를 둔다.
- detect/evidence_grid.py: P1 channel reference implementation.
- w1_real_defs.fast_score: 대형 definition의 현재 NumPy scorer. per_handle의 parallel/thickness/junction/layer evidence를 cache한다.
- ext/cubicasa_ir.py: C split의 SEG-IR/truth contract.
- ext/cubicasa_ml.py: 현재 6-feature train/val extraction과 logistic/HistGradientBoosting 비교를 P2 feature store adapter로 확장한다.
- ext/cubicasa_eval.py: val-only calibration과 dedicated test single-shot 패턴, JSON/XLSX output 방식을 재사용한다.

fast_score는 shared handle record를 max score로 접으므로, transform stability 계산 전 instance가 소실될 수 있다. P2 adapter는 normalize 직후 instance table을 별도로 만들고, P1 evidence만 instance에 다시 join한 뒤 마지막 평가 단계에서 max-fold한다. 이 차이를 equivalence test 없이 fast_score 내부에 바로 섞지 않는다.

P1의 절대 thickness channel은 현재 scale 불변성 실패를 상속할 수 있다. 따라서 primary feature/anchor schema는 drawing-relative offset feature를 쓰고, P1 thickness 값은 entity가 scale-paired M check를 통과할 때만 anchor 동의에 기여하게 한다. 절대-band P1 channel을 그대로 넣는 arm은 진단 ablation이며, 이것이 없으면 성능이 무너질 경우 Cell 4/6에서 shortcut 실패로 판정한다.

## 5.3 state machine과 test 단발 보호

run.py는 다음 상태만 허용한다.

    EXTRACT_TRAIN -> FIT_LF -> FIT_MODEL -> CALIBRATE_VAL -> FREEZE
    FREEZE -> AUDIT_PRETEST -> EVAL_TEST_ONCE -> SEALED

EVAL_TEST_ONCE는 prereg hash, source manifest hash, model hash, calibrator hash, empty test-contact ledger를 확인한다. 성공 또는 실패와 무관하게 ledger에 timestamp와 artifact hash를 쓰고 SEALED로 전환한다. test 성능을 보고 threshold를 바꾼 새 run은 같은 method version으로 허용하지 않는다.

## 5.4 증거 XLSX와 JSON contract

XLSX에는 최소 다음 sheet가 있어야 한다.

- summary: 모든 band와 verdict
- per_model_split: P1/logistic/tree, layer-on/off, raw/calibrated
- per_drawing: TP/FP/FN/AUPRC/Brier/REL/RES
- grammar_subgroups
- ood_company_style
- calibration_bins
- bootstrap_paired
- leakage_audit
- lf_audit
- anchor_selection
- seed_stability
- M_gate
- fp_taxonomy
- failures_and_exclusions

wsd_eval_p2.json은 최소 다음 top-level field를 갖는다.

- schema, created_at_kst, method_version
- claim
- forecast: null
- score_type: brier
- reference_class: id RC-WALL-ZL, n 0, n_min 5
- base_rate: none
- abstain_flag: empty_reference_class
- uncertainty_type: epistemic
- truth_contract와 source/license states
- manifests와 모든 hash
- models와 calibrators
- metrics_S, metrics_F, metrics_C_diagnostic, M_gate
- paired_lift_CI, layer_ablation, grammar_recall, ood_drop
- leakage_audit, test_contact_ledger
- resolution_criterion, resolution_trigger, update_log
- resolution_verdict: open/pass/fail

독립 evaluator가 이 JSON을 생성하기 전까지 resolution_verdict는 open이다. truth gate가 미완이면 성능 숫자가 좋아도 open 또는 blocked_by_truth로 남기며 pass를 쓰지 않는다.

## 5.5 예상 개발 규모

계획상 핵심 구현은 약 8–12개 모듈, unit/integration test 약 25–40개, CPU 실행 driver와 evidence writer 각 1개다. 이는 제안 규모이며 측정된 작업량이 아니다. 가장 위험한 부분은 classifier 자체가 아니라 fingerprint group, instance 보존, planar face feature, single-shot guard다. 따라서 구현 순서도 이 네 가지를 모델 grid보다 앞에 둔다.

# 6. 실험 셀 정의

공통 원칙은 val 개발 허용, test 방법당 단발, 평가 전 band 봉인, shuffle control 의무, 증거 XLSX 의무다. 모든 시드는 제안 seed set {7, 17, 29, 43, 71}을 쓰고 split은 시드로 바꾸지 않는다. 95% CI는 drawing/block group을 resampling unit으로 한 paired cluster bootstrap으로 계산한다. bootstrap 반복 수는 제안값 10,000으로 봉인하며, P1과 P2의 동일 drawing 차이를 같은 resample에서 계산한다.

## Cell 0 — truth·license·split 선결 게이트

- 가설: S_exact와 F_exact의 truth provenance, license, leakage-free group split을 test 접촉 전에 고정할 수 있다.
- 지표: B1 fidelity verdict, truth provenance completeness, license_state, fingerprint overlap count, unresolved/ambiguous handle rate, test ledger.
- 합격선: 합성 fidelity PASS; F_exact가 vector-handle 또는 독립 line annotation으로 성립; counsel 서면 확인; split 간 block/geometry overlap 0; test ledger empty.
- 킬 조건: raster mask를 exact handle truth로 승격해야만 진행 가능한 경우, license 미해결, split dedupe 실패, truth/feature process 분리 실패.
- 예산: CPU 0.5–1 day와 counsel 대기. counsel 시간은 compute budget 밖이다.
- 시드: 없음. canonicalization은 결정적이어야 한다.

Cell 0가 FAIL이면 Cell 1의 synthetic-only 개발과 구현 unit test는 가능하지만 최종 claim resolution은 금지한다.

## Cell 1 — cheapest probe

- 가설: 500 synthetic block에서 P2 logistic 또는 boosted tree가 P1보다 ranking/precision–coverage를 개선할 최소 신호가 있고, 20 FloorPlanCAD drawing에서도 같은 방향이 관찰된다.
- 지표: S 개발 AUPRC, precision at wall recall 0.50, seed 분산, runtime/RSS. F 20은 F_exact가 성립할 때만 같은 지표를 사용하고, 그렇지 않으면 raster diagnostic으로 명확히 격하한다.
- 비교: frozen P1, P2 logistic, P2 boosted tree의 정확히 세 contender. supervised truth model은 이 셀에 넣지 않는다.
- 제안 합격선: 두 P2 중 하나가 S에서 P1보다 높은 point AUPRC를 보이고, seed 다수에서 방향이 같으며, memory soft cap을 지킨다. 이 셀은 최종 prereg lift band를 주장하지 않는다.
- 킬 조건: 두 P2 모두 P1 이하, positive anchor가 한 grammar에만 존재, 20 F 사용에 license/truth gate가 열리지 않음. 마지막 경우 F arm만 blocked이며 synthetic 결과로 F를 대체하지 않는다.
- 예산: local CPU 1 day, RAM peak 32GB 이하.
- 시드: 전체 seed set; P1은 결정적.

## Cell 2 — anchor와 LF 식별성 감사

- 가설: positive anchor는 고정밀이고, negative anchor는 명백한 annotation에 국한되며, LF family가 하나의 P1 prior를 중복 투표하지 않는다.
- 지표: anchor precision/recall, grammar별 anchor selection rate, P-vs-unanchored-true-positive 구분도, LF coverage/conflict, family mutual information, leave-one-family-out posterior 변화.
- 제안 합격선: positive anchor precision 0.98 이상, negative anchor precision 0.995 이상, 모든 preregistered supported wall grammar에 positive anchor가 존재, 단일 LF family 제거로 전체 U posterior의 25% 이상이 decision boundary를 넘지 않음.
- 킬 조건: 어떤 supported wall grammar의 anchor support 0, anchor precision band 미달, dependency를 모델링해도 한 LF family가 posterior를 사실상 독점.
- 예산: CPU 0.5 day, 32GB 이하.
- 시드: label-model initialization에 전체 seed set. family audit 결론이 seed에 따라 바뀌면 FAIL.

위 숫자는 제안 gate이며 실측 주장이 아니다. support가 너무 적은 grammar는 임의로 합치지 않고 unsupported로 표시한다. 최종 subgroup 판정 대상이 되려면 제안 기준 최소 30 wall handle과 5 drawing을 가져야 하며, 미달이면 해소 불가로 기록한다.

## Cell 3 — 모델 사다리와 weak-supervision 기여

- 가설: 반복/topology feature와 PU+label model을 결합한 P2가 P1 및 단순 P/N supervision보다 향상된다.
- 비교 arm:
  - P1 frozen
  - logistic P/N-only
  - logistic SCAR-PU
  - logistic nnPU+label model
  - tree P/N-only
  - tree BaggingPU
  - tree posterior-imputation P2
  - CubiCasa supervised 6-feature HGB reference
- 지표: val AUPRC, precision–recall curve, precision at wall recall 0.50, grammar recall, seed variance, class-prior sensitivity, runtime/RSS.
- 제안 합격선: main logistic/tree 중 적어도 하나가 P1 대비 S val 0.03, F val 0.03 이상의 point lift를 보이고 precision/coverage band를 달성; 모든 pi sensitivity point에서 lift 방향 동일.
- 킬 조건: main arm이 P/N-only arm을 못 이김, 결론이 class-prior interval에서 뒤집힘, logistic/tree 모두 seed 다수에서 P1 이하, 32GB soft cap 반복 위반.
- 예산: feature cache 후 CPU 1–2 days.
- 시드: 전체 seed set. hyperparameter 선택은 seed 평균과 최악 seed를 함께 고려.

Cell 3의 val lift는 모델 선택용 제안 기준이고 최종 claim의 0.05/0.03 band를 대신하지 않는다.

## Cell 4 — repetition·face·token ablation

- 가설: P2의 추가 lift는 raw layer shortcut이 아니라 repetition stability와 face/junction context에서 온다.
- arm: full geometry, minus-repeat, minus-face, minus-transform-stability, geometry-only no-token/no-layer, normalized-token, raw-layer diagnostic.
- 지표: AUPRC delta, long-parallel FP taxonomy, grammar recall, company/style OOD delta, feature permutation importance와 logistic coefficient stability.
- 제안 합격선: no-layer primary가 P1 대비 양의 lift를 유지; repeat 또는 face/stability family 제거 중 적어도 하나가 lift를 유의하게 줄이되, 그 family 단독 모델은 main보다 낮음.
- 킬 조건: raw layer 제거 시 AUPRC가 0.15 이상 하락, corpus-wide fingerprint ID를 넣어야만 lift 발생, repeated non-wall symbol subgroup recall/precision이 붕괴.
- 예산: cached feature로 CPU 1 day.
- 시드: 전체 seed set, 동일 split과 동일 sampled-row budget.

## Cell 5 — drawing/company/style shift calibration

- 가설: frozen shift-aware calibrator가 unseen group에서 global raw score보다 REL을 낮추면서 RES와 ranking을 보존한다.
- split: company metadata가 있으면 leave-one-company-out. 없으면 train geometry-only summary로 style cluster를 만들고 leave-one-cluster-out. cluster 생성에 label/token/vendor/path를 쓰지 않는다.
- 지표: Brier, REL, RES, calibration curve, AUPRC, ID 대비 OOD AUPRC drop, drawing-equal 결과.
- 제안 합격선: REL 0.03 이하, RES 0.02 이상, OOD AUPRC drop 0.10 이하, calibration 뒤 AUPRC ranking이 수치 오차 외에는 변하지 않음.
- 킬 조건: unseen group에서 REL band 실패, target label/prevalence를 알아야만 보정 가능, OOD drop 0.10 초과, style definition이 vendor/path shortcut에 의존.
- 예산: CPU 0.5–1 day.
- 시드: style clustering과 calibrator에 전체 seed set. cluster instability가 verdict를 바꾸면 FAIL.

## Cell 6 — M 안정성·sentinel·대리 독립성

- 가설: P2가 rigid/unit/scale/explode/layer rename에서 semantic prediction을 유지하고, 0벽/전벽 sentinel을 통과하며, proxy들이 같은 prior 하나를 반복하지 않는다.
- 지표: per-handle prediction agreement, probability deviation, sentinel precision/recall, S/F/C/E1.5/P1 간 동일-def disagreement tensor, LF family correlation.
- 제안 합격선: packet의 frozen M gate를 모두 PASS하고 0벽 sentinel FP=0, 전벽 sentinel recall 1.0. proxy independence는 대각선 우위/비대각선 붕괴와 동일-def 불일치가 보고 가능해야 한다.
- 킬 조건: 현재처럼 scale arm이 FAIL 상태로 남음, strict sentinel FAIL, 0벽 predictor가 안정성 점수만으로 통과, proxy independence audit가 산출되지 않음.
- 예산: CPU 1 day. 1.dwg 대형 definition stress는 별도 로그.
- 시드: model seed 전체; transform 자체는 deterministic paired manifest.

sentinel 합격선은 제안값이며, 현재 관측은 scale 0.7624 FAIL과 strict FAIL이므로 이 셀은 아직 통과하지 않았다.

## Cell 7 — frozen 최종 평가와 resolution

- 가설: 최종 no-layer P2가 frozen S_exact/F_exact에서 P1보다 사전등록 lift와 calibration/shift/leakage band를 모두 만족한다.
- 입력: SEALED model과 calibrator, immutable S_exact/F_exact test manifest, empty test-contact ledger. C_test는 외부 일반화 진단으로 한 번 함께 평가하되 F_exact 대체는 금지.
- primary 지표:
  - AUPRC_F(P2)가 AUPRC_F(P1)보다 0.05 이상 높음
  - AUPRC_S(P2)가 AUPRC_S(P1)보다 0.03 이상 높음
  - S_exact와 F_exact 각각에서 precision 0.92 이상인 operating point가 wall recall 0.50 이상
  - company/style OOD AUPRC drop 0.10 이하
  - S_exact와 F_exact 각각에서 REL 0.03 이하, RES 0.02 이상
  - 각 S/F lift의 paired 95% bootstrap CI lower bound가 0 초과
  - leakage audit PASS, M gate PASS
- subgroup 지표: preregistered wall grammar별 recall, repeated non-wall FP, curved/fragmented/nested-block recall.
- 킬 조건: deterministic P1 대비 lift CI lower가 0 이하, raw layer 제거 시 AUPRC 0.15 이상 붕괴, positive-anchor selection bias로 어느 supported wall grammar recall이 0.60 미만, 어느 필수 performance/shift/calibration/leakage/M band라도 실패.
- 예산: local CPU 1 day, 32GB 이하. 재시도 없음.
- 시드: frozen ensemble. seed별 결과도 공개하지만 ensemble 하나만 final contender.

최종 verdict는 모든 AND 조건을 통과할 때만 pass다. truth 또는 license gate가 열리지 않았으면 open, test를 열고 band를 실패했으면 fail이다. 부분 통과를 평균내 candidate pass로 만들지 않는다.

## Cell 8 — shuffle·shortcut 음성 대조

- 가설: pipeline이 split/handle/layer leakage만으로 높은 점수를 만들지 않는다.
- arm: train label permutation, LF-row permutation within drawing, geometry fingerprint randomized across groups, token-only, group-id-only forbidden-feature canary.
- 지표: AUC/AUPRC 대비 prevalence, calibration, forbidden feature detector, split overlap.
- 제안 합격선: permutation과 canary arm이 chance-compatible하고 forbidden ID column count 0.
- 킬 조건: shuffle control이 유의한 ranking을 보임, group-id/token-only가 main lift 대부분을 재현, canary가 feature matrix에 남음.
- 예산: CPU 0.5 day.
- 시드: 전체 seed set.

Cell 8은 test 전 val에서 의무 통과하고, final evaluator가 schema/column audit을 다시 수행한다. 다이제스트의 기존 shuffle AUC 0.375 PASS는 현재 6-feature 경로의 증거일 뿐 새 P2 feature와 split의 면책이 아니다.

# 7. red team 티켓 응답

패널 보고서에 번호와 설명이 함께 나온 티켓 중 P2에 직접 또는 선결적으로 걸리는 항목을 다음처럼 처리한다. 보고서 안에서 T10처럼 문맥별 설명이 겹치는 번호는 번호만 믿지 않고 두 payload를 모두 수용한다.

| 티켓/공격 | P2 응답 | 상태 |
|---|---|---|
| T1 / 공격 A: truth proxy 독립성 | Cell 6에서 동일-def disagreement tensor와 train-source × eval-source 교차요인을 산출한다. S/F/M/silver를 합산 점수로 평균하지 않는다 | OPEN, 선결 |
| T2 / PR-1: 벽 합성 생성기와 fidelity | S_exact는 generator wall_member provenance와 B1 fidelity PASS가 있어야 final truth가 된다. 현재 B1 FAIL이므로 final 평가 금지 | OPEN, hard gate |
| T5 / PR-3: FloorPlanCAD/CubiCasa 권리 | source별 license_state를 manifest에 넣고 counsel 서면 전 FloorPlanCAD 학습/파생물 생성을 금지한다. 패킷의 외부 제3자 라벨 사용 GO가 어느 자산에 적용되는지도 source별로 문서화한다 | OPEN, hard gate |
| T6 / 공격 E: 평가 단위 혼선 | semantic primary를 source_handle로 고정하고 instance는 반복 feature용 내부 단위로만 쓴다. aggregation은 max로 freeze한다 | 설계상 해소 가능 |
| T7 / 공격 F: 0벽 탐지기 안정성 통과 | 0벽과 전벽 sentinel, 전벽 recall floor를 Cell 6에 AND gate로 추가했다 | 구현 필요 |
| T9/T21: deterministic baseline 선계측·후보 폭발 | frozen P1을 모든 paired cell의 동일 manifest baseline으로 재실행하고 runtime/RSS/candidate count를 기록한다. spatial index equivalence와 32GB cap을 둔다 | 구현 필요 |
| T10의 silver gate 식별자 문제 | calibration 원문대로 B1과 B4를 모두 요구한다. 현재 Pearson 0.2911이므로 LF_E15는 비활성이다 | 현재 gate closed |
| T10/T23: Graph IR adjacency 완전성 | face/junction feature 전에 normalize·INSERT·snap graph의 entity coverage, orphan edge, transform round-trip을 감사한다. 불완전하면 graph feature arm을 죽이고 P2 final 진입을 막는다 | OPEN |
| T14/T33: layer lexicon 동결·project split | train-only vocabulary, rare/OOV 규칙, company/project outer split, no-layer primary를 강제한다 | 설계 반영 |
| T15: learned cell seed confound | split은 한 번 고정하고 동일 seed set을 모든 learned arm에 적용한다. seed 평균과 최악 seed를 같이 보고한다 | 설계 반영 |
| T16: 절대 gap band 대 상대 band | drawing-relative offset/length를 primary로 하고 절대 P1 thickness는 진단 arm으로 격리한다. scale M check를 통과하지 못한 entity의 thickness channel은 anchor 동의에 쓰지 않는다 | Cell 4/6에서 판별 |
| T17 / CL-E: truth-source 교차요인 | train source와 eval source를 교차한 matrix 및 동일-def disagreement를 evidence workbook에 저장한다 | OPEN |
| T22: P1 통과가 P2 lift의 선결 | P1 hash와 prereg band가 없는 run에서는 P2-P1 lift를 계산하지 않는다. P1 자체가 coverage/normalization gate를 못 통과하면 P2 claim도 open으로 유지한다 | hard prerequisite |
| T24: raster→handle exact harness | FloorPlanCAD raster mask를 line truth로 부르지 않는다. vector provenance 또는 독립 line annotation과 synthetic round-trip이 없으면 F_exact arm은 blocked다 | OPEN, hard gate |
| T31의 raster 본선 초과 증명 맥락 | P2는 raster 본선 주장을 하지 않는다. FloorPlanCAD는 exact line contract가 생길 때만 평가축이며, CubiCasa SEG-IR와 CAD vector가 주 경로다 | 수용 |
| T34: 인용 experiment_executed:false | 이 도시어는 문헌을 실험 증거로 승격하지 않는다. 모든 문헌은 method rationale이며, 실행 여부와 artifact hash는 별도 evidence ledger에만 기록한다 | 수용 |
| 공격 C / T3 정렬-key artifact의 간접 영향 | P1가 산출하는 anchor가 E1 정렬 artifact에 의존하지 않는지 CL-A 결과를 확인한다. anchor feature에 rank/order key를 넣지 않는다 | CL-A 의존 |
| T4 ornith 원시자료의 간접 영향 | P2 primary는 Ornith/E1.5에 의존하지 않는다. silver gate가 열리더라도 LF 하나로만 사용하고 원시 lineage 없으면 비활성 | 수용 |

red team 반대의견 “silver는 신호인가 오염원인가”는 CL-K 방식으로 보존한다. main은 gate-only/silver-off, gate가 실제로 열릴 때만 silver-one-LF arm을 추가하며, anti-silver 통제 arm과 같은 split에서 비교한다. silver가 lift를 만들더라도 no-silver arm이 필수 band를 못 통과하면 P2 자체 성공으로 해석하지 않는다.

# 8. 인접 제안과의 관계 및 사망 조건

## 8.1 병합 가능한 지점

- **CL-B / P1**: frozen deterministic scorer, strict positive intersection, P1 paired baseline을 제공한다. P2가 P1 구현을 바꾸어 baseline을 약하게 만들 수 없다.
- **CL-C**: S_exact/F_exact/M manifest와 common resolution contract를 제공한다. P2 final의 가장 강한 선결이다.
- **CL-D**: M transform, 0벽/전벽 sentinel, invariant comparison harness를 그대로 재사용한다.
- **CL-E**: truth-source cross-factor와 proxy independence audit를 P2 Cell 6에 합친다.
- **CL-F의 logistic→tree→GNN 사다리**: P2가 logistic/tree rung이다. 이 rung이 prereg band를 통과하면 GNN은 추가 복잡성의 필요를 먼저 증명해야 한다.
- **CL-I**: layer/text convention prior와 lexicon freeze를 token arm에 제공한다. no-layer primary는 유지한다.
- **CL-J**: room/face-first 제안의 planar face artifact를 feature family로 공유할 수 있다. 다만 P2는 face-first가 최종 관측 언어라고 주장하지 않고 tabular ablation으로만 사용한다.
- **CL-K**: silver-off 대조를 상설 arm으로 병합한다.

## 8.2 차별점

P1은 고정 규칙으로 wall evidence를 합치지만 P2는 anchor 불완전성과 unlabeled mixture를 명시적으로 모델링한다. GNN은 adjacency 위에서 representation을 학습하지만 P2는 graph를 검증 가능한 tabular summary로 제한해 leakage와 계산량을 낮춘다. raster/VLM은 pixel 의미를 직접 쓰지만 P2는 vector entity와 block repetition을 사용한다. supervised CubiCasa HGB는 exact training label을 쓰지만 P2의 핵심 claim은 exact training label 없이 P/N/U와 LF로 실제 CAD drawing에 옮길 수 있느냐이다.

P2가 가져와야 하는 새 증거는 단순 HGB 비선형성이 아니다. 다음 세 묶음이 각각 입증되어야 한다.

- repetition/face/transform feature의 독립 ablation lift
- P/N-only 대비 PU+label-model lift
- no-layer, unseen-style calibration에서 유지되는 lift

셋 중 하나라도 없으면 P2는 더 단순한 인접 제안으로 흡수된다.

## 8.3 이 제안이 죽어야 하는 조건

다음 중 하나면 P2를 중단하거나 더 단순한 rung으로 환원한다.

1. paired 95% bootstrap에서 P2-P1 lift CI lower bound가 0 이하이다.
2. S_exact 또는 F_exact point lift가 각각 prereg band를 못 넘거나, precision 0.92 at wall recall 0.50을 달성하지 못한다.
3. no-layer arm AUPRC가 raw-layer arm보다 0.15 이상 붕괴한다.
4. supported wall grammar 중 하나라도 recall 0.60 미만이며 원인이 positive-anchor selection bias다.
5. repeated symbol이 반복 wall보다 더 강한 positive signal이어서 repeat/face feature로 분리되지 않는다.
6. class-prior 또는 anchor propensity의 합리적 sensitivity interval에서 verdict가 뒤집힌다.
7. same block/geometry fingerprint가 split을 가로지르거나 raw handle/path/vendor ID가 feature에 들어간다.
8. FloorPlanCAD raster truth를 exact handle truth로 가장해야만 F band를 계산할 수 있다.
9. scale/sentinel M gate가 계속 실패한다.
10. unseen company/style AUPRC drop, REL, RES 중 어느 하나라도 band를 실패한다.
11. P/N-only 또는 frozen P1이 main P2와 동등하고, PU/label model/repetition ablation의 추가 이득이 없다.
12. 32GB soft cap 안에서 대형 definition을 처리할 수 없고 spatial-index/caching으로도 회복되지 않는다.

사망 뒤의 올바른 다음 단계는 자동으로 GNN/VLM으로 올라가는 것이 아니다. P1이 동등하면 CL-B로 환원하고, face feature만 유효하면 CL-J/CL-B에 병합하며, layer prior만 유효하면 CL-I 진단으로 격하한다. anchor grammar coverage가 근본 문제면 새 모델보다 truth/anchor 설계를 먼저 고친다.

## 최종 사전등록 문장

- claim: P2가 P1보다 동결된 S_exact/F_exact 평가에서 사전등록 lift와 calibration band를 모두 만족한다.
- forecast: null.
- score_type: brier.
- reference_class: RC-WALL-ZL, n=0, n_min=5.
- base_rate: none.
- resolution criterion: P2_lift_CI_low>0이며 모든 performance, shift, calibration, leakage, M, truth/license band가 통과.
- resolution trigger: 고정 split에서 P1/P2 비교 artifact wsd_eval_p2.json이 독립 생성될 때.
- update log: 2026-07-17 KST 최초 abstain을 유지한다. layer-ablation 후 lift 유지와 anchor-unseen grammar 회복은 상향 증거, anchor-only subgroup 붕괴·split dedupe 실패·F_exact 부재는 하향 증거다.
- uncertainty_type: epistemic. anchor bias, proxy dependence, drawing shift를 측정하면 줄일 수 있다.
- resolution_verdict: open.
- abstain_flag: empty_reference_class.

DOSSIER_COMPLETE: calibration_P2
