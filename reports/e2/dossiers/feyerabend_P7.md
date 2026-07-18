# P7 방법론 심층 도시에는: 텍스트·레이어 관례를 1등 시민으로

**좌석:** `feyerabend_P7`  
**제안:** 레이어명·블록명·TEXT/MTEXT·선종을 프로젝트 내부의 벽 prior로 계측하고, 기하는 통과 여부만 결정하는 확인 게이트로 둔다.  
**문서 지위:** 실행 계획이며 채택 판정이 아니다. 아래의 수치 중 현재 성능·자산을 묘사하는 값은 패킷의 2026-07-18 실측 다이제스트만 인용했다. 그 밖의 수치는 모두 앞으로 봉인할 실험 설계값 또는 하이퍼파라미터 후보이고, 측정 결과가 아니다.

핵심 주장은 “레이어가 벽의 보편 오라클이다”가 아니다. 더 좁고 반증 가능한 주장은 다음과 같다.

> 한 프로젝트 안에서 작성 관례와 벽 의미 사이에 재현 가능한 상호정보가 있을 수 있다. 그 정보는 프로젝트 경계를 넘겨 재학습하거나 보편 사전으로 승격하지 않고, 기하 확인 게이트를 통과한 후보끼리의 순위에만 사용할 때 가치가 있을 수 있다.

따라서 P7은 이름이 기하를 이기는 분류기가 아니라 `관례 prior → 기하 확인 → 게이트 내부 재순위화` 파이프라인이다. `G(h)=0`인 핸들은 이름이 `WALL`이어도 절대 벽으로 출력하지 않는다. 이 불변식이 깨지면 성능과 무관하게 P7은 즉시 죽는다.

---

## 1. 이론적 근거·선행연구

### 1.1 기하-only 서사가 놓치는 것

CAD 객체에는 좌표 외에도 제작 과정의 흔적이 남는다. 레이어, 블록 경로, 선종, 인접 주석은 설계자가 무엇을 그리려 했는지에 관한 약한 관측이다. 같은 평행 이중선이 벽, 문, 창, 치수선, 경계 다각형 또는 방향 화살표일 수 있다는 패킷의 CubiCasa 오류 분석은 기하만으로 의미가 식별되지 않는 구간이 실제로 있음을 보여 준다. 반대로 작성 관례는 회사, 프로젝트, 언어, 템플릿에 따라 바뀐다. 이 두 사실을 동시에 받아들이면 적절한 모델은 “레이어를 믿는다/버린다”의 이분법이 아니라 다음의 조건부 모델이다.

\[
P(Y=1\mid X_g,C,P) \propto
\underbrace{\mathbf 1[G(X_g)=1]}_{\text{필수 기하 확인}}
\cdot
\underbrace{P(Y=1\mid X_g)}_{\text{기하 기준점}}
\cdot
\underbrace{R(C;P)}_{\text{프로젝트별 관례 우도비}}
\]

여기서 `Y`는 per-handle 벽 소속, `X_g`는 기하 특징, `C`는 관례 묶음, `P`는 프로젝트다. `R(C;P)`는 프로젝트 내부에서만 적합하고 동결한다. 프로젝트가 바뀌면 미등록 토큰의 우도비는 중립값 1로 돌아간다.

패킷 실측에서 기하 탐지기 v1은 CubiCasa val에서 F1 0.2358, 정밀도 0.134, 재현율 0.981이었고, 6개 기하 특징의 HistGradientBoosting은 val F1 0.517, 정밀도 0.860, 재현율 0.370, AUC 0.9215였다. 이는 비선형 기하 학습이 큰 개선을 이미 가져왔음을 뜻하지만, “관례 채널이 쓸모없다”를 뜻하지는 않는다. 특히 전자의 높은 재현율과 낮은 정밀도는 게이트 안의 의미적 혼동을 재순위화할 여지를 남긴다. 다만 CubiCasa SEG-IR에는 레이어 신호가 없으므로 P7이 그 수치 자체를 올릴 수 있다고 주장해서는 안 된다.

### 1.2 방법론 계보

1. **약한 감독(weak supervision)과 데이터 프로그래밍.** Ratner 등의 Data Programming/Snorkel 계열은 여러 불완전한 labeling function이 내는 표와 기권을 결합하고, 그 상관과 신뢰도를 따로 추정한다. P7의 정규식, 레이어 버킷, 블록명, TEXT/MTEXT, 선종은 각각 하나의 약한 함수다. 차이는 P7이 이들을 최종 진리로 결합하지 않고 기하 게이트 내부 순위에만 쓴다는 점이다.
2. **원격 감독(distant supervision).** Mintz 등의 관계 추출 원격 감독은 데이터베이스 정렬을 noisy label로 쓴다. 여기서도 “이름에 WALL이 있다”는 것은 정답이 아니라 정답과 상관될 수 있는 원격 표식이다. 레이어 도용과 복사된 템플릿은 전형적인 표식 오류다.
3. **범주형 target/mean encoding과 경험적 베이즈 수축.** Micci-Barreca의 고카디널리티 범주형 인코딩 계보와 일반적인 empirical-Bayes smoothing은 드문 레이어명 하나가 극단적 확률을 얻는 일을 막는다. P7은 사람 라벨 대신 적합 전용 도면의 고신뢰 기하 앵커를 사용하며, 평가 도면을 배제한 cross-fitting으로 누수를 막는다.
4. **상호정보와 순열 검정.** Shannon 상호정보는 관례 버킷 `C`와 앵커 `Z`의 의존성을 비모수적으로 요약한다. Fisher식 randomization test의 논리를 따라 관례 묶음을 도면 안에서 셔플한 귀무분포와 비교한다. 단순히 관측 MI가 양수라는 이유만으로 가중치를 주지 않는다.
5. **문자 n-gram과 feature hashing.** 다국어·약어·구분자 변형이 많은 레이어명에는 단어 사전보다 Unicode 정규화 후 문자 n-gram이 견고하다. Weinberger 등의 feature hashing 계보는 평가 데이터에서 어휘 목록을 새로 만드는 누수를 피하면서 고정 차원의 희소 표현을 제공한다.
6. **도메인 이동과 그룹 단위 평가.** Ben-David 등의 domain adaptation 이론, GroupDRO를 포함한 domain generalization 계보는 동일 분포 내부 성능과 새 도메인 성능이 다르다는 점을 분명히 한다. P7에서 도메인은 프로젝트 또는 firm이다. 엔티티 랜덤 분할은 같은 레이어명을 양쪽에 복제하므로 허용하지 않는다.
7. **shortcut learning과 Goodhart 위험.** Geirhos 등의 shortcut learning 논의는 예측력이 높은 표면 신호가 환경이 바뀌면 실패할 수 있음을 보여 준다. P7은 이름 shortcut을 숨기지 않고 별도 채널로 노출하고, 셔플·누락·프로젝트 전이로 의존량을 측정한다. 이 계보가 요구하는 결론은 이름을 금지하는 것이 아니라 shortcut의 범위를 봉인하는 것이다.
8. **CAD 레이어 표준화 관행.** ISO 13567 계열과 AIA CAD Layer Guidelines 같은 명명 체계는 분야·작성주체·표현단계를 이름에 부호화하려는 실무 관행이 존재함을 뒷받침한다. 그러나 특정 토큰이 모든 프로젝트에서 벽을 뜻한다는 근거는 아니다. 표준의 정확한 판·연도와 프로젝트별 채택 여부는 구현 전 문헌·계약 문서에서 **요검증**이다.

위 문헌명은 일반 지식에 근거한 방법론 표지다. 이 도시에는 웹 검색을 사용하지 않았으며, 성능 수치나 외부 논문의 정량 결과를 근거로 삼지 않는다. 배포 문서에서 정식 서지정보를 싣기 전에는 제목·판본을 재확인한다.

### 1.3 P7이 실제로 반증하는 두 이론

- **현 기하 우선 이론:** 이름을 보지 않아도 충분하며, 이름은 일반화 실패만 늘린다.
- **P7 반대이론:** 의미의 최대가능도 단서는 프로젝트 작성 관례에 있고, 기하는 noisy하지만 필수적인 확인자다.

정렬 합성에서 게이트 내부 이름 prior가 F1을 0.15 이상 올리고, 동일 기하의 오정렬 합성에서는 prior를 제거해도 F1이 변하지 않으며, 별도 프로젝트로 동결 전이했을 때도 이득이 양수면 반대이론이 살아남는다. 정렬 합성에서 신호가 없거나 프로젝트 전이 이득이 0 이하이면 반대이론을 죽이고 관례 채널을 PARK한다. 합성에서만 성공하고 실프로젝트 전이에 실패한 경우는 “메커니즘은 존재하지만 제품 가치는 없음”으로 기록한다.

---

## 2. 알고리즘 정확 스펙

### 2.1 입력, 출력, 평가 단위

입력은 다음 스키마를 갖는 불변 레코드다.

```text
EntityRecord:
  project_id, drawing_id, handle_id
  entity_type, geometry, bbox
  layer_raw, linetype_raw
  block_path_raw[]
  nearby_text_raw[]   # TEXT/MTEXT, 거리와 containment 포함
  geometry_features  # parallel, thickness, junction, log_length, sin2θ, cos2θ 등

CandidateRecord:
  candidate_id, member_handles[]
  geometry_score, geometry_gate
  candidate_geometry_features
```

`project_id`는 파일명에서 추측하지 않고 실험 manifest에 사전 등록한다. 여러 도면정의가 하나의 1.dwg 안에 있더라도 같은 작성 관례를 공유한다고 확인되기 전에는 프로젝트 경계를 합치지 않는다. 최종 출력은 `handle_id → {wall_score, wall_pred, gate_pass, evidence}`다. 채점 우주는 패킷의 공통 계약대로 per-handle이며, 후보나 도면 단위 수치는 진단용으로만 둔다.

### 2.2 관례 문자열의 결정론적 정규화

정규화 함수 `N(s)`는 학습하지 않으며 버전과 해시를 봉인한다.

1. null과 빈 문자열을 명시적 `<MISSING>`으로 바꾼다.
2. Unicode NFKC를 적용하고 영문은 case-fold한다.
3. 경로 구분자와 `-`, `_`, `.`, 공백, 괄호를 공통 경계 토큰으로 바꾼다.
4. 영문↔숫자, 한글↔영문 전환점에도 경계를 넣는다.
5. 순수 일련번호는 `<NUM>`으로 치환하되 원래 숫자 길이 bucket은 보존한다.
6. 원문, 정규화문, 토큰, 문자 n-gram을 모두 분리 저장한다. 원문은 모델 선택에 직접 사용하지 않는다.

사전 등록 정규식 `R0`는 토큰 경계를 갖는 `wall`, `walls`, `벽`, 단독 `w`만 양성 표식으로 삼는다. `w`는 반드시 단독 토큰이어야 하며 `window`의 일부와 매칭하지 않는다. 한·영 혼합, `A-WALL`, `벽_외부`는 경계 분리 후 잡힌다. 이 목록은 최초 hidden 평가 전에 변경할 수 없다. 새 토큰은 오류 분석에는 기록할 수 있지만 같은 평가 라운드의 사전에 추가하지 않는다.

동어반복 위험 때문에 결과는 항상 다음 두 열로 분리한다.

- `direct_token`: `wall|walls|벽|w`처럼 정답 이름을 직접 말하는 표식
- `indirect_convention`: 직접 토큰을 제거한 레이어/블록/선종/문자 n-gram 표식

간접 채널이 0인데 직접 토큰만 성능을 올리면 “고정 정규식 lookup”의 가치만 인정하고 “프로젝트 관례 상호정보 모델”의 승리로 보고하지 않는다.

### 2.3 TEXT/MTEXT와 블록 문맥의 핸들 귀속

관례는 엔티티 하나에 다음 우선순위로 귀속한다.

1. 엔티티 자체의 layer와 linetype
2. 엔티티를 포함하는 INSERT의 effective block path(안쪽부터 바깥쪽까지)
3. 같은 블록 내부 TEXT/MTEXT
4. 블록 밖에서는 엔티티 bbox와 겹치거나, 도면별 정규화 반경 안에 있는 TEXT/MTEXT

텍스트 반경은 절대 mm를 쓰지 않는다. 적합 분할에서 구한 후보 길이 중앙값 또는 도면 bbox 대각선에 대한 비율 중 하나를 val에서 선택하고 동결한다. 이는 scale 팔이 0.7624로 실패한 현재 상태에서 또 하나의 절대 축척 prior를 몰래 들이지 않기 위함이다. 후보가 두 핸들로 이루어지면 직접 토큰은 `max`, 경험적 관례 점수는 support 가중 평균으로 결합한다. 최종 per-handle 점수는 그 핸들이 속한 gate-pass 후보 점수의 최대값이다.

### 2.4 사람 라벨 없는 프로젝트 내부 prior 적합

기하 점수 `q_g(i)∈[0,1]`는 이름·레이어 가중치를 0으로 만든 `fast_score` 또는 동결된 `cubicasa_ml` 기하 모델에서 받는다. v1의 4채널 점수에서 layer 0.20을 제거할 때에는 남은 parallel/thickness/junction 가중치를 합 1로 재정규화한다. 기존 v0의 overlap/gap 점수를 사용할 경우에도 문자열을 읽는 코드 경로가 없음을 테스트한다.

적합 전용 도면에서만 두 앵커를 만든다.

\[
Z_i=
\begin{cases}
1 & q_g(i)\ge \tau_+\\
0 & q_g(i)\le \tau_-\\
\varnothing & \text{otherwise}
\end{cases}
\]

`τ+`, `τ-`는 val 이전에 후보 격자에서 고르고 freeze한다. 회색 구간은 관례 적합에 쓰지 않는다. 음성 앵커는 길이·각도·도면별로 양성 앵커와 층화 샘플링하여, 특정 레이어의 단순 개수나 짧은 아이콘 비율이 관례 점수가 되지 않게 한다. 이 `Z`는 벽 정답이 아니라 기하 proxy다. 따라서 이 prior는 기하와 독립된 진리원이라고 부르지 않는다.

관례 feature `t`마다 support를 도면 단위로 집계하고 beta-binomial 방식으로 수축한다.

\[
\tilde p_t=\frac{n_{t,+}+\alpha p_0}{n_t+\alpha},\qquad
a_t=\operatorname{logit}(\tilde p_t)-\operatorname{logit}(p_0)
\]

`p0`는 적합 분할의 층화된 앵커 기저율, `α`는 수축 강도다. 동일 INSERT의 복제 엔티티는 한 cluster로 가중하여 블록 복사가 support를 부풀리지 못하게 한다. 드문 feature는 `min_support` 아래에서 `a_t=0`으로 기권한다.

관례 전체의 의존성은 다음 plug-in MI로 계측한다.

\[
\widehat I(T;Z)=\sum_{t,z}\hat p(t,z)\log\frac{\hat p(t,z)}{\hat p(t)\hat p(z)}
\]

귀무분포는 각 적합 도면 안에서 `T` 묶음을 handle cluster 단위로 셔플해 만든다. 관측 MI가 사전 등록한 순열 상위 밴드를 넘지 못하면 그 채널의 신뢰도 `ρ_c=0`으로 둔다. 넘으면 초과량을 귀무분포 폭으로 정규화해 `[0,1]`에 clip한다. 이 on/off 신뢰도 게이트 덕분에 의도적 오정렬 합성에서는 이름 prior가 자동 기권하고 geometry-only와 예측 해시가 같아야 한다.

평가 도면은 비지도 적합에도 절대 쓰지 않는다. 순서는 `fit drawing IDs → prior artifact 저장·해시 → val/test drawing IDs 로드 → lookup only`다. 새 프로젝트에서는 원칙적으로 모든 학습 feature가 OOV 중립값이다. “전이 시 현지 비지도 재적합”은 별도 방법이며 P7의 freeze 전이 성적으로 세지 않는다.

### 2.5 선택적 문자 모델

정규식 probe가 살아남은 뒤에만 고정 hash의 문자 2–5-gram 희소 벡터를 쓴 logistic 모델을 추가한다. 목적함수는 기하 앵커에 대한 가중 교차엔트로피와 L2 규제다.

\[
\mathcal L(\theta)=
-\sum_{i:Z_i\ne\varnothing}w_i[Z_i\log\sigma(\theta^\top\phi_i)+(1-Z_i)\log(1-\sigma(\theta^\top\phi_i))]
+\lambda\lVert\theta\rVert_2^2
\]

`w_i`는 도면·블록 cluster 균형 가중치다. vocabulary는 평가 도면에서 만들지 않고 고정 hashing을 사용한다. 이 모델의 출력도 프로젝트별 MI 신뢰도 게이트를 통과해야 하며, 직접 토큰을 포함한 모델과 제거한 모델을 별도 보고한다. 소형 문자열 임베딩은 문자 모델이 명확히 이긴 후의 확장일 뿐 P7의 필수 조건이 아니다.

### 2.6 기하 확인 게이트와 최종 재순위화

이름을 전혀 보지 않는 기하 게이트를 `G_i`라 한다. 게이트 하이퍼파라미터는 geometry-only val에서 먼저 봉인하고 P7 arm 사이에서 바꾸지 않는다.

\[
G_i=\mathbf1[q_g(i)\ge\tau_G]\land \mathbf1[\text{필수 기하 제약 통과}]
\]

게이트 통과 후보의 최종 점수는 다음과 같다.

\[
s_i=\operatorname{logit}(\operatorname{clip}(q_g(i)))
+\beta_R\rho_R a_R R_i
+\sum_c\beta_c\rho_c A_{ic}
\]

여기서 `R_i`는 직접 정규식, `A_ic`는 layer/block/text/linetype/간접 n-gram 점수다. `β`는 synthetic-train/real-val에서만 고른다. 출력은

\[
\hat Y_i=G_i\cdot\mathbf1[s_i\ge\tau_{out}]
\]

이다. 구현에서는 `G_i=0`이면 `s_i=-∞`로 강제하고 assertion을 건다. 따라서 prior가 게이트를 우회할 경로가 없다. cheapest probe는 도면마다 `G=1`인 후보 중 geometry-only 상위 20개를 동일 집합으로 고정한 뒤 정규식 prior로 순서만 바꾼다. 후보 집합이나 게이트 통과 수가 arm 사이에서 달라지면 실험 무효다.

### 2.7 제안 하이퍼파라미터 공간과 동결 순서

아래 값은 측정치가 아니라 사전등록할 탐색 공간이다.

| 구분 | 후보 공간 | 선택 규칙 |
|---|---|---|
| 앵커 | `τ-`, `τ+`의 적합분할 quantile 조합 | 회색 구간을 유지하며 val proxy 안정성 최대 |
| 수축 | `min_support ∈ {10,20,50}`, `α ∈ {10,50,100}` | 합성 val과 fit-fold 안정성 |
| prior 세기 | `β ∈ {0,0.25,0.5,1,2}` | per-handle val F1, 동률이면 작은 값 |
| 정규식 | 사전등록 `R0` 대 무규칙 | 변경 금지, 직접 토큰 별도 보고 |
| 문자 표현 | hash 차원, 2–5-gram, L2 강도 | 정규식 성공 후에만 탐색 |
| 텍스트 귀속 | bbox overlap 또는 정규화 반경 후보 | 절대 mm 금지, val에서 하나 동결 |
| 출력 | `τout` | geometry-only와 같은 val 프로토콜 |
| top-k probe | `k=20` | cheapest probe 고정값, 성능 튜닝에 사용 금지 |

동결 순서는 `데이터 분할 → 정규화/정규식 → 기하 게이트 → 앵커 규칙 → prior 하이퍼파라미터 → 출력 임계값 → hidden test`다. test는 방법당 한 번만 실행한다.

### 2.8 참조 의사코드

```python
def fit_project_prior(fit_drawings, frozen_geometry, prereg):
    rows = extract_entities(fit_drawings)
    qg, gate = frozen_geometry.score_without_names(rows)
    assert geometry_code_did_not_read_convention_fields()

    z = make_anchor_labels(qg, prereg.tau_minus, prereg.tau_plus)
    features = convention_features(rows, prereg.normalizer, prereg.regex)
    features = cluster_weight_insert_copies(features)

    maps = {}
    for channel in prereg.channels:
        mi_obs = mutual_information(features[channel], z)
        mi_null = within_drawing_cluster_permutations(features[channel], z)
        rho = prereg.reliability_gate(mi_obs, mi_null)
        maps[channel] = smoothed_log_odds(features[channel], z, rho)

    return FrozenPrior(
        project_id=prereg.project_id,
        maps=maps,
        regex_hash=hash(prereg.regex),
        fit_drawing_ids=sorted(ids(fit_drawings)),
        forbidden_eval_ids=prereg.eval_ids,
    ).seal()


def predict(eval_drawing, frozen_geometry, frozen_prior, prereg):
    assert eval_drawing.id not in frozen_prior.fit_drawing_ids
    rows = extract_entities(eval_drawing)
    qg, gate = frozen_geometry.score_without_names(rows)
    sem = frozen_prior.lookup_only(convention_features(rows))
    score = logit(qg) + prereg.beta @ sem
    score[~gate] = -inf
    pred = gate & (score >= prereg.output_threshold)
    assert not any(pred & ~gate)
    return aggregate_candidates_to_handles(pred, score, gate)
```

---

## 3. 벽 과업 적응 설계

### 3.1 1.dwg 실도면축: P7의 주된 실제 접속점

1.dwg staged DXF에는 384개 도면정의와 layer/block/TEXT/MTEXT/linetype을 보존할 가능성이 있어 P7의 주 전장이다. 그러나 사람 라벨이 없다. 따라서 이 축에서는 다음만 허용한다.

- 도면정의를 fit/calibration/analysis로 그룹 분할하고, fit에서만 프로젝트 prior를 적합한다.
- geometry-only와 P7이 공유하는 gate-pass 후보 집합을 저장한다.
- 각 도면의 top-20 순위 변화, direct/indirect 토큰 기여, OOV율, MI와 순열 귀무분포, 게이트 위반 수를 분석한다.
- v0의 벽-제로 도면율이 0.682에서 0.2135로 바뀐 실측을 문맥으로 사용하되, P7이 다시 낮춘 zero-hit 비율을 곧바로 recall 개선이라 부르지 않는다.
- silver 판정자와의 일치는 분석 열일 뿐 정답 열이 아니다. 5개 판정자를 5개의 독립 표로 세지 않고 패킷대로 약 2개 어휘 가문으로 집계한다.

“zero-pair 회복”이라는 말도 제한한다. 이전의 엄격한 pair 생성기에서는 0개였지만 새 기하 게이트에는 통과 후보가 있는 도면에서만 P7이 순위를 바꿀 수 있다. 기하 후보 자체가 0개면 P7의 회복 가능성도 0이다. 그 경우는 P1/P6/CL-B의 후보 커버리지 문제이지 P7 성과가 아니다.

실도면에서 이름 prior가 silver와 더 잘 맞더라도 사람 라벨이 없으므로 채택 근거가 되지 않는다. 오히려 detector와 silver가 같은 이름 shortcut을 공유하는지 보는 독립성 감사 자료로 쓴다. 패킷 실측상 detector의 full-vs-name-blind가 1.0으로 동일하여 현재 detector의 layer 신호가 0이라는 점은 P7의 출발점이지 성공 증거가 아니다.

### 3.2 CubiCasa5k SEG-IR 벡터축: 라벨 있는 기하 기준점이자 missing-channel 대조군

CubiCasa5k는 train 4,200, val 400, test 400의 사람 라벨 벡터 평가축이며 변환의 레이어 누출이 0이다. 이 장점 때문에 geometry-only 기준점에는 적합하지만, 원래 layer/block/TEXT/linetype 관례가 SEG-IR에 없다. 사용 원칙은 다음과 같다.

1. P7 입력을 전부 `<MISSING>`으로 넣었을 때 geometry-only와 점수·예측 해시가 같아야 한다. 차이가 나면 누수 또는 missingness 버그다.
2. Wall 클래스 이름이나 변환 과정의 label을 가짜 layer명으로 넣지 않는다. 그것은 답을 feature로 복사하는 직접 누출이다.
3. 기하 기준점은 v1 val F1 0.2358과 HistGradientBoosting val F1 0.517을 그대로 비교 대상으로 둔다. P7이 metadata가 없는 이 축에서 이를 넘는다고 약속하지 않는다.
4. 합성 관례를 CubiCasa geometry에 덧씌운 실험은 메커니즘 스트레스 테스트로만 표시하고 실제 CAD 관례 전이로 보고하지 않는다.
5. 패널의 PR-3 counsel 서면 확인 전에는 새 학습 arm을 시작하지 않는다. test 400은 모든 선택이 끝난 뒤 단발로만 연다.

P7이 가져올 수 있는 추가 가치는 CubiCasa에서 이미 학습한 비선형 기하 점수 `q_g`를 폐기하는 것이 아니라, metadata가 실제로 있는 별도 CAD 프로젝트에서 그 점수의 gate-pass 후보를 재순위화하는 것이다. 따라서 `GBDT 0.517 대 P7`이 아니라 `동결 GBDT 대 동결 GBDT+P7`의 paired 비교가 올바르다.

### 3.3 FloorPlanCAD 래스터축: 핵심 평가축이 아님

FloorPlanCAD 자산은 5,308개 래스터와 벽 bbox/segmask가 있으나 벡터 SVG가 없다. 래스터에는 원본 layer/block/linetype이 없으므로 P7의 핵심 관례를 복원할 수 없다. OCR로 화면에 보이는 TEXT를 읽는 확장은 가능하지만, 이는 “CAD 작성 관례”가 아니라 별도의 vision-text 채널이며 현재 cheapest probe에 넣지 않는다.

따라서 이 축은 다음 두 용도로만 둔다.

- metadata가 없는 경우 P7이 기하/래스터 기준점을 정확히 통과시키는 missing-channel 테스트
- 장래에 권리와 좌표 역투영이 해결된 경우, OCR 텍스트 ablation의 별도 연구축

FloorPlanCAD bbox/segmask를 P7 학습에 쓰는 것은 PR-3와 CL-G의 좌표 역투영 게이트를 통과한 뒤의 일이다. 현재 도시에는 이를 전제로 한 성능 약속을 넣지 않는다.

### 3.4 합성축: 인과 메커니즘의 주 truth source

동일한 geometry/handle/label을 가진 쌍을 만들고 관례 bundle만 바꾼다.

- **Aligned:** 벽 label과 `R0` 직접 토큰 및 프로젝트별 간접 토큰이 상관된다.
- **Misaligned:** 같은 관례 bundle의 주변분포와 빈도를 보존한 채 handle cluster 단위로 층화 셔플한다.
- **Adversarial misuse:** 일부 비벽에 `WALL`을 붙이고 일부 벽은 generic layer에 둔다.
- **Multilingual:** 영어, 한국어, 혼합 구분자와 약어를 같은 비율 설계 안에서 교차한다.
- **Stolen layer:** 블록 복사로 비벽 엔티티가 벽 레이어를 상속하는 경우를 둔다.

쌍 사이의 geometry feature 행렬, gate mask, handle universe 해시가 완전히 같아야 한다. 차이는 즉시 생성기 오류다. 다만 현재 합성팩의 충실도 B1은 KS 0.5792, TV 0.265로 FAIL이고 entity type도 실도면의 SPLINE/ARC/HATCH 혼재를 재현하지 못한다. 따라서 현 합성은 P7 코드의 인과 단위시험에는 쓸 수 있지만 실전 유효성 판결에는 쓸 수 없다. PR-1/CL-C의 벽 합성 생성기와 fidelity gate가 먼저 완성되어야 한다.

### 3.5 silver와 이름 prior의 관계

silver는 학습 target으로 사용하지 않는다. 실도면에서는 다음 세 축의 불일치만 기록한다.

1. geometry-only gate/score
2. P7 convention score와 재순위
3. silver 2어휘 가문의 판정

P7과 silver의 일치 상승은 “두 shortcut이 같아졌다”일 수도 있다. 이름을 가린 silver, 관례를 셔플한 P7, geometry를 고정한 paired 비교로 이를 분해한다. silver가 직접 이름 토큰에 반응하고 P7도 같은 토큰에 반응하면 독립 증거 두 개로 세지 않는다. 이 원칙은 CL-K anti-silver control arm과 일치한다.

---

## 4. 데이터·컴퓨트 요구

### 4.1 필요한 데이터와 lineage

필수 필드는 `project_id`, `drawing_id`, `handle_id`, geometry, layer, linetype, effective block path, TEXT/MTEXT, 후보 membership다. 각 run에는 다음 lineage를 남긴다.

- 원본 파일/변환 산출물의 불변 해시
- split manifest와 project/firm 경계의 근거
- normalizer/regex/prior artifact/geometry model의 해시
- fit에 사용된 drawing ID와 금지된 val/test ID
- 관례 채널별 missing/OOV/support
- direct-token과 indirect-convention 결과 분리
- gate mask와 candidate universe 해시

프로젝트 경계가 불명확하면 엔티티를 임의 분할하지 않고 해당 자료를 전이 평가에서 제외한다. 사전등록 lexicon은 train/fitting split을 보기 전에 저장한다. 평가 도면에서 새로 발견한 이름은 다음 버전 후보로만 기록한다.

### 4.2 로컬 실행 계획

P7의 핵심은 문자열 정규화, 해시 희소특징, 범주 집계, 순열 검정, 재순위화이므로 CPU/RAM 작업이다. RTX 5070 Ti 16GB나 DGX가 없어도 실행 가능하다.

- 412,775 선분의 최대 도면정의를 고려해 엔티티를 chunk 단위로 읽고, category 통계는 streaming count로 모은다.
- 후보 쌍의 전수 이중 루프를 새로 만들지 않는다. `fast_score`가 생성한 후보와 geometry feature를 재사용해 P7의 추가 비용을 대략 `O(N + nnz)`로 제한한다.
- 원문 문자열 전체를 dense one-hot으로 만들지 않고 hash sparse matrix와 dictionary counts를 쓴다.
- 순열은 entity 행이 아니라 drawing×block cluster의 집계표를 재배열하여 RAM 64GB 안에서 수행한다.
- 각 셀은 우선 소수 도면 smoke test, 그 다음 전체 val 순서로 실행한다. 예상 예산은 셀별 수십 분에서 수 시간 범위의 계획값이며 실측이 아니다.

### 4.3 GPU와 DGX 계획

- **16GB 로컬 GPU:** 고정 소형 문자열 encoder 또는 OCR 확장을 승인했을 때만 사용한다. 정규식/target encoding/문자 n-gram에는 쓰지 않는다.
- **DGX Spark:** 현재 unreachable이므로 어떤 필수 셀도 DGX에 의존하지 않는다. 다프로젝트 대량 embedding sweep이 CPU 병목으로 확인되고 regex/희소모델이 이미 통과했을 때만 선택적 가속기로 쓴다.
- **프런티어 VLM API:** 결재가 없고 P7 판정에 필요하지 않다. silver 분석을 위해 새 호출을 요구하지 않는다.

### 4.4 권리와 데이터 거버넌스

CubiCasa와 FloorPlanCAD의 NC 및 원도면 권리 문제는 패널의 PR-3가 미해결이다. counsel 서면 확인 전에는 기존 실측을 인용하는 것 외에 새 학습·배포용 파생물 생성을 시작하지 않는다. 1.dwg의 layer/text 원문에는 업체명이나 도면 메모가 포함될 수 있으므로 증거 xlsx에는 기본적으로 해시·정규화 토큰·집계만 싣고, 원문은 접근통제된 오류 분석 산출물에 둔다.

---

## 5. 구현 계획

패킷에 명시된 기존 도구 이름 외의 실제 저장소 구조는 주어지지 않았다. 아래는 프로그램 저장소 안에 만들 **제안 골격**이며, 현재 파일이 존재한다고 주장하지 않는다.

```text
p7_convention/
  schema.py                 # EntityRecord/CandidateRecord와 project boundary
  normalize.py              # Unicode·token·n-gram 결정론적 정규화
  prereg_regex.yaml         # R0, 해시, 변경 이력
  context_join.py           # layer/block/TEXT/MTEXT/linetype의 handle 귀속
  anchors.py                # 이름-맹 geometry anchor와 cluster weighting
  fit_prior.py              # MI, permutation null, EB-smoothed log odds
  rerank.py                 # hard geometry gate와 top-20/per-handle 집계
  metamorphic.py            # layer/text/block shuffle와 geometry identity 검사
  synth_conventions.py      # aligned/misaligned/adversarial convention overlay
  split_guard.py            # fit/val/test/project/firm 누수 assertion
  run_p7.py                 # 셀 실행기
  evidence_writer.py        # evidence_grid 접속
tests/
  test_normalize.py
  test_no_gate_bypass.py
  test_eval_lookup_only.py
  test_missing_metadata_identity.py
  test_geometry_invariant_shuffle.py
  test_block_copy_weighting.py
configs/
  p7_prereg.yaml
```

### 5.1 기존 도구 접속점

- **`fast_score`:** 이름·레이어 채널을 비활성화한 geometry score, gate mask, 후보 membership을 읽는다. v1의 layer 0.20이 실제로 0인지 runtime assertion과 ablation hash로 검증한다.
- **`cubicasa_ir`:** per-handle universe와 Wall label을 읽되 convention 필드는 항상 `<MISSING>`으로 둔다. Wall label이 feature join에 들어오지 못하도록 schema 레벨에서 분리한다.
- **`cubicasa_ml`:** 동결 HistGradientBoosting의 geometry probability를 `q_g`로 노출한다. 모델 재학습과 P7 prior 적합을 한 함수에서 하지 않는다.
- **`evidence_grid`:** 모든 셀의 prereg, run, per-project, direct/indirect ablation, metamorphic, leakage, failure reason을 xlsx로 쓴다.

권장 evidence workbook sheet는 `PREREG`, `SPLITS`, `RUNS`, `PER_PROJECT`, `TOKENS_DIRECT`, `CONVENTIONS_INDIRECT`, `METAMORPHIC`, `SENTINELS`, `LEAKAGE`, `ERRORS`, `LINEAGE`다. 실패 run도 삭제하지 않고 `failure_reason`과 함께 남긴다.

### 5.2 구현 순서와 완료 조건

1. schema·split guard·normalizer와 단위시험
2. geometry-only adapter와 hard-gate invariant
3. 정규식 `R0` cheapest probe와 top-20 report
4. 합성 convention overlay와 aligned/misaligned paired hash 검사
5. MI/순열/EB prior와 fit/freeze artifact
6. metamorphic·sentinel·missingness battery
7. 1.dwg 분석 arm
8. counsel과 PR-1 통과 후 labeled multi-project val/test arm

예상 개발 규모는 기존 parser와 `fast_score` 출력 스키마가 안정적이라는 조건에서 핵심 probe 약 3–5 개발일, 누수·증거·metamorphic 하네스까지 약 6–9 개발일의 **계획 추정**이다. DXF의 nested INSERT effective layer와 TEXT bbox가 보존되지 않았다면 adapter 작업이 별도 증가한다.

### 5.3 필수 assertion

```text
pred => geometry_gate
eval_drawing_id not in prior.fit_ids
eval_tokens never mutate prior.vocabulary_or_maps
candidate_universe_hash(G) == candidate_universe_hash(G+P7)
geometry_feature_hash(original) == geometry_feature_hash(layer_shuffle)
all_missing_conventions => score_hash(P7) == score_hash(geometry_only)
wall_label_column not reachable from convention feature builder
test_open_count <= 1 per frozen method
```

하나라도 실패하면 해당 run은 성능표에 넣지 않고 infrastructure failure로 기록한다.

---

## 6. 실험 셀 정의

실행 순서는 패킷의 좌석 큐를 따른다. P1+P6, P2, P3의 더 싼 판별이 먼저이며 P7은 네 번째다. P7 안에서는 E0→E5 순서로 진행하고, 앞 셀의 kill을 통과하지 못하면 뒤 셀 예산을 쓰지 않는다.

### E0 — 게이트·누수·missingness 계약 셀

- **가설:** P7은 후보 집합을 만들거나 geometry gate를 바꾸지 않으며, 관례가 전부 누락되면 geometry-only와 완전히 같다.
- **데이터:** 소형 합성 smoke set, CubiCasa val의 사전등록 subset, 1.dwg fit subset. 라벨은 assertion에 필요하지 않다.
- **비교:** `G`, `G+R0`, `G+R0+U`의 candidate/gate mask; all-missing arm.
- **지표:** `pred & ~G` 수, candidate universe hash 동일성, all-missing score/pred hash 동일성, eval lookup 시 prior artifact hash 변화 수, label-column 접근 수.
- **합격선:** 모든 위반 수 0, 요구되는 해시 완전 동일.
- **킬 조건:** 단 한 건의 gate 우회, 평가 도면으로 vocabulary/map 갱신, Wall label feature 접근, missing arm 차이.
- **예산:** 로컬 CPU 약 1시간 이내의 계획값.
- **시드:** 결정론 셀이므로 1개; 순서 무작위화만 별도 고정 시드 1개.

### E1 — cheapest 정규식 prior: 정렬/오정렬 합성 2×2

- **가설:** 정렬 합성에서는 `G+R0`가 `G`보다 per-handle F1을 0.15 이상 높이지만, 관례 bundle만 셔플한 오정렬 합성에서는 MI 신뢰도 게이트가 `R0`를 기권시켜 F1과 예측이 변하지 않는다.
- **데이터:** 동일 geometry·label의 aligned/misaligned paired synthetic. 현재 fidelity FAIL 팩은 코드 단위시험용이며, 판결용 hidden family는 PR-1/CL-C 통과 후 동결한다.
- **비교:** `G` 대 `G+R0`. gate와 `τout`은 고정한다.
- **주 지표:** paired per-handle F1 차이. 보조로 precision, recall, gate coverage, direct-token coverage, 예측 hash, 프로젝트별 분산을 기록한다.
- **제안 합격선:** aligned hidden에서 `ΔF1≥+0.15`; misaligned hidden에서 prior weight 0, `ΔF1=0`, 예측 hash 동일. aligned의 개선이 gate-pass universe 안에서만 발생해야 한다.
- **킬 조건:** aligned 개선이 0.15 미만, misaligned에서 예측 변화, direct regex가 gate를 우회, 또는 geometry hash가 쌍 사이에서 다름.
- **예산:** 로컬 CPU 수 시간의 계획값.
- **시드:** 생성 시드 10개를 사전등록하고 paired 분석. 개발 시드는 val에만, hidden mutation family는 한 번만 연다.

E1의 `+0.15`는 패킷이 준 신호 존재 밴드다. 이를 달성해도 실제 프로젝트 일반화가 입증된 것은 아니다.

### E2 — 프로젝트 내부 상호정보와 간접 관례의 증분 셀

- **가설:** 직접 토큰을 제거한 layer/block/text/linetype 관례에도 기하 앵커와 순열 귀무를 넘는 프로젝트 내부 MI가 있고, `G+R0+U`가 `G+R0`보다 추가 이득을 낸다.
- **데이터:** E1 합성의 다국어·stolen-layer 변형과, 라벨을 보지 않는 1.dwg fit folds. 합성에는 truth metric, 1.dwg에는 stability metric만 쓴다.
- **비교:** `G`, `G+R0`, `G+R0+EB`, `G+R0+hashed-char`. 마지막 arm은 EB가 살아남은 뒤에만 연다.
- **주 지표:** 합성 per-handle ΔF1, direct 제거 후 ΔF1, `I_obs` 대 drawing-cluster permutation null, fold 간 score rank correlation, OOV율, block-copy effective sample size.
- **제안 합격선:** 합성 hidden에서 indirect-only 증분이 양수이고 모든 사전등록 seed 방향이 일치하며, MI가 순열 게이트를 통과한다. 정확한 최소 증분은 E1 결과를 보기 전에 별도 prereg에 봉인한다.
- **킬 조건:** 이득이 direct token에만 전부 귀속, 순열 귀무를 넘지 못함, 한 대형 block 복제 제거 후 신호 소멸, 또는 오정렬 arm에서 MI 채널이 기권하지 않음.
- **예산:** EB/MI는 로컬 CPU 수 시간, 문자 모델은 통과 시 추가 수 시간의 계획값.
- **시드:** E1과 같은 10개 paired seed; 순열 seed 목록을 별도 봉인. seed 평균만 보고하지 않고 전부 공개한다.

### E3 — 기하 불변 관례 metamorphic·sentinel 셀

- **가설:** geometry를 고정하고 layer assignment를 깨면 aligned 합성의 P7 성능은 예상 방향으로 하락하지만 geometry gate 자체는 완전히 불변이다. misaligned 합성, all-missing, 0-wall sentinel에서는 prior가 기권한다.
- **변형:** (a) layer bundle의 handle 간 셔플, (b) block path 셔플, (c) TEXT/MTEXT 셔플, (d) linetype 셔플, (e) opaque bijective rename, (f) 모든 convention 삭제. 각 변형은 geometry bytes를 건드리지 않는다.
- **지표:** `Δshuffle=F1(original)-F1(shuffled)`, gate mask hash, candidate hash, 채널별 prediction flip, 0-wall false positive, all-wall recall, direct/indirect 의존량.
- **제안 합격선:** 모든 변형에서 gate/candidate hash 동일; aligned에서 assignment-breaking shuffle의 `Δshuffle>0`; misaligned와 all-missing에서 prediction hash가 geometry-only와 동일. 0-wall sentinel에 prior발 false positive 0. all-wall sentinel의 recall은 geometry-only보다 낮아지지 않아야 한다.
- **킬 조건:** geometry 변화, 0-wall 탐지기로 퇴행, 이름 삭제가 gate를 약화, 또는 aligned와 misaligned의 의존량이 구분되지 않음.
- **예산:** 로컬 CPU 약 반나절의 계획값.
- **시드:** 각 변형×합성 seed 10개, paired. sentinel은 결정론.

opaque bijective rename과 assignment shuffle은 의미가 다르다. 전자는 철자 사전 의존성을, 후자는 엔티티-관례 결합 의존성을 측정한다. 둘을 “layer rename invariance” 하나로 합쳐 평균내지 않는다.

### E4 — 1.dwg fit/freeze 분석 셀

- **가설:** 평가 도면을 보지 않고 적합한 프로젝트 prior가 gate-pass 후보 중 geometry-only와 다른 안정된 top-20 순서를 만들며, 특히 이전 zero-pair 또는 silver-high 구간에서 분석 가치가 있다.
- **데이터:** 1.dwg의 384개 도면정의를 project/definition manifest에 따라 fit와 analysis로 그룹 분할. 사람 라벨 없음.
- **비교:** `G` 대 `G+R0` 대 `G+R0+U`; silver는 약 2개 어휘 가문으로만 병렬 분석.
- **지표:** top-20 rank change, 새 top-20 진입 수, direct/indirect 기여, OOV, MI/null, gate 위반, drawing-level zero-hit 변화, 두 silver 가문과의 disagreement matrix.
- **제안 합격선:** 정확도 합격선은 두지 않는다. infrastructure 합격은 gate 위반 0, eval 학습 0, prior artifact 불변, fold 방향 안정성이다. 사람이 없는 후보 회복 수나 silver 일치는 GO 근거가 아니다.
- **킬 조건:** gate 우회 압력이 생김, fit/analysis 경계 누수, 순위 변화가 direct token 한 종류나 단일 block 복제에 집중, 또는 2가문 silver를 5독립표처럼 세야만 좋아 보임.
- **예산:** 최대 도면정의의 412,775 선분을 streaming 처리하는 로컬 CPU 수 시간의 계획값.
- **시드:** split seed 5개로 안정성만 보되, 최종 project split은 한 개를 사전봉인한다. 성능 선택에는 쓰지 않는다.

### E5 — 프로젝트 간 freeze 전이와 단발 test 판결 셀

- **가설:** source 프로젝트의 lexicon·MI map·가중치를 완전히 동결하고 새 target 프로젝트에 적용해도 `G+P7`의 per-handle F1이 같은 `G`보다 높다.
- **선결:** 최소 두 개 이상의 독립 project/firm ID와 합법적으로 사용할 수 있는 사람 per-handle 라벨, PR-3 counsel, PR-1 fidelity, E0–E3 통과. 현재 패킷 자산만으로 실도면 labeled 전이 판결을 완료할 수 있다고 가정하지 않는다.
- **설계:** leave-one-project-out val로 방법과 하이퍼파라미터를 고른다. target에는 source prior lookup만 하며 현지 비지도 적합도 금지한다. 마지막 target test는 동결 후 한 번만 연다.
- **비교:** 동결 geometry-only(`fast_score` 또는 GBDT) 대 동일 geometry+동결 P7. source별, target별, direct 제거 arm을 모두 paired 평가한다.
- **지표:** 주 지표 per-handle ΔF1. precision/recall, 프로젝트별 ΔF1, OOV, calibration, gate coverage를 보조 보고한다. micro 평균과 project-macro를 함께 쓰고 firm별 결과를 숨기지 않는다.
- **제안 합격선:** 패킷 계약대로 프로젝트 전이 주 지표의 이득이 양수여야 한다. `ΔF1≤0`이면 convention 채널을 PARK한다. 합성 aligned의 0.15 밴드와 전이 양수 조건을 모두 만족해야 P7 전체가 산다.
- **킬 조건:** 전이 ΔF1≤0, 어느 target에서든 gate 우회, 이득이 평가 프로젝트 사전 재적합에 의존, direct 정답 토큰을 제거하면 전부 붕괴하면서 broader convention 모델로 포장, 또는 precision 손실을 감춘 micro 평균만 양수.
- **예산:** 희소 prior 자체는 로컬 CPU 수 시간/프로젝트의 계획값. 라벨 조달·권리 확인은 별도 외부 선결이며 DGX는 불필요하다.
- **시드:** 학습/val seed 5개를 사전등록하고 평균·최악을 모두 공개. test는 선택된 단일 artifact로 단발 실행하며 seed 재시도를 금지한다.

### 6.1 셀 판정표

| 결과 | 판정 |
|---|---|
| E1 aligned `+0.15` 이상, misaligned 불변, E5 전이 양수 | `kills: reigning` 후보. 기하-only 충분성 주장을 기각할 증거가 생김 |
| E1 무이득 또는 E5 전이 0 이하 | `kills: counter`; P7 convention 채널 PARK |
| E1 성공, E5 자료/권리 부재 | 메커니즘만 살아 있음. 제품 채택 보류 |
| E1 성공, direct token만 성공 | broader P7은 죽고 고정 regex 보조 규칙만 별도 후보 |
| 어떤 셀에서든 gate 우회 | 성능과 무관하게 P7 즉시 kill |

---

## 7. red team 티켓 응답

패킷이 제공한 OPEN 티켓의 상세 전문은 없으므로, 패널 보고서에서 P7/CL-I 또는 프로그램 선결과 연결이 명시된 범위만 응답한다. 번호의 숨은 세부사항을 추측하지 않는다.

| 티켓/선결 | P7에 대한 공격 | 응답과 봉합 증거 | 잔여 위험 |
|---|---|---|---|
| **T1 / PR-2 — 대리 독립성** | synthetic, external, metamorphic, silver가 같은 평행 이중선 prior를 공유하면 확증이 아니라 편향 증폭 | E2에서 관례 MI가 기하 앵커로 적합된다는 종속성을 명시한다. E4는 geometry/P7/silver 2가문 disagreement를 동일 definition에서 기록하고, E5만 사람 라벨 판결로 사용한다. 세 proxy의 표를 합산하지 않는다. | P7의 비지도 prior 자체는 기하 proxy에 종속된다. 독립 truth가 아니며 사람 라벨 전까지 채택 불가 |
| **T2 / PR-1 — 벽 합성 생성기·충실도** | 현재 합성팩이 실제 CAD 현상을 못 담고 벽 생성기 자격도 부족 | E1–E3의 현 팩 결과는 unit test로만 표시한다. SPLINE/ARC/HATCH, nested INSERT, 비평행 조각과 divergent 현상을 포함한 CL-C 팩이 fidelity gate를 통과한 뒤 hidden 판결을 실행한다. | 현재 B1 FAIL이므로 ecological validity는 미해소. P7이 자체적으로 해결하지 못함 |
| **T5 / PR-3 — 권리** | CubiCasa/FloorPlanCAD NC와 원도면 권리 | counsel 서면 전 새 학습/파생 arm을 중지한다. 기존 다이제스트 수치는 문맥 인용만 한다. | 외부 조정이 필요한 하드 선결. P7 코드로 해소 불가 |
| **T6 — 평가 단위** | 후보/집합 성과를 per-handle 성과로 둔갑시킬 위험 | 출력과 주 지표를 per-handle `wall_member(h)`로 고정하고, 후보/top-20/도면 zero-hit는 진단 열로 격리한다. 동일 handle이 여러 후보에 속하면 gate-pass 최대 점수 규칙을 사전등록한다. | 실도면 라벨 부재 때문에 E4는 정확도 판정 불가 |
| **T7 — metamorphic sentinel** | 변화 위반율만 보면 0벽 탐지기가 통과 | E3에 0-wall/all-wall sentinel, gate coverage, recall 비퇴행 조건을 넣는다. all-missing identity도 별도 검사한다. | 합성 sentinel의 fidelity는 PR-1에 의존 |
| **T14 / T33 — firm별 lexicon 구축·동결, 프로젝트 split, 동어반복 토큰** | 평가 도면에서 이름 사전을 학습하거나 같은 firm 이름을 양쪽 split에 복제할 수 있음 | `project_id`/`firm_id` 그룹 split, fit-only map, sealed artifact, eval lookup-only assertion, OOV 중립값을 구현한다. `wall|벽|w` 직접 토큰과 간접 관례를 분리 보고한다. | 독립 firm 수가 부족하면 E5를 실행할 수 없고 P7은 보류 |
| **T17 / CL-E — truth-source 교차요인** | 합성에서만 잘 되는 convention shortcut을 실전 신호로 오해 | E1 합성, E3 metamorphic, E4 unlabeled real analysis, E5 human-labeled project transfer를 별도 셀로 유지한다. 대각선 성공을 비대각 전이 성공으로 해석하지 않는다. | 현재 자산으로 E5를 채울 독립 metadata+label 프로젝트가 명시되지 않음 |
| **T9/T21 맥락 — baseline 선계측** | P7 arm이 후보나 gate를 함께 바꾸면 lift 귀속 불가 | geometry-only artifact, candidate universe, gate mask, output threshold를 먼저 봉인하고 paired hash를 저장한다. v1의 layer 0.20은 제거·재정규화한 이름-맹 baseline으로 만든다. | 기존 v0/v1 구현이 convention field를 간접 참조하면 adapter 감사 필요 |
| **T34 — load-bearing 인용 상태** | 미실행 R-레인 인용을 실증처럼 사용할 위험 | 본 도시는 패킷 실측만 현재 수치로 사용하고, 외부 방법론은 계보로만 언급한다. 각 실험은 `executed=false`에서 시작하며 evidence xlsx가 생기기 전 결과 문장을 쓰지 않는다. | 정식 배포 전 서지 판본 요검증 |

추가로 패널의 red-team 예상 실패모드를 다음처럼 수용한다.

- **영어/한국어 혼용:** Unicode 정규화, token boundary, char n-gram, 언어별 ablation으로 해소를 시도하되 평가 어휘 추가는 금지한다.
- **레이어 도용:** adversarial/stolen-layer 합성, block-copy cluster weighting, hard geometry gate로 제한한다.
- **Goodhart로 게이트 약화:** gate artifact를 P7보다 먼저 동결하고 `pred⇒gate`를 코드 assertion으로 만든다. 성능 최적화가 gate threshold를 만지면 다른 방법으로 간주한다.
- **silver 공모:** 5표가 아닌 2가문, name-blind/셔플 대조, 사람 라벨 없는 일치를 판정에서 제외한다.

---

## 8. 인접 제안과의 관계 및 사망 조건

### 8.1 병합 가능한 지점

- **CL-I / platt P6:** firm-특유 lexicon의 구축·동결, 이름 mask ablation, 프로젝트 split을 한 구현으로 합칠 수 있다. P7의 고유 기여는 “zero-weight 금지”가 아니라 MI로 weight를 계측하고 geometry gate 내부에만 쓰는 운영 계약이다.
- **CL-B / feyerabend P6·P2:** INSERT world-coordinate 전개와 단위 정박이 먼저 후보 커버리지와 geometry gate를 고친다. P7은 그 결과 후보를 재순위화한다. geometry candidate가 없는 곳을 이름으로 생성하지 않는다.
- **CL-C / PR-1:** aligned/misaligned convention overlay를 WSD-EVAL-v1 합성팩의 한 factor로 넣을 수 있다. geometry family와 convention alignment를 교차하여 어느 축이 성능을 만들었는지 분리한다.
- **CL-D:** layer rename을 한 종류로 취급하지 않고 opaque rename, assignment shuffle, deletion으로 분해한 metamorphic battery를 제공한다. 0/all-wall sentinel도 공유한다.
- **CL-E:** `{synthetic, external-human, silver, metamorphic}` truth 축에서 P7의 불일치 구조를 한 셀로 보낼 수 있다. 단, P7의 기하 앵커와 geometry baseline은 독립 proxy로 세지 않는다.
- **CL-F:** 현재 강한 고전 ML 기준인 HistGradientBoosting 뒤에 P7 log-prior를 붙이는 것이 우선이다. GNN보다 싼 희소 관례 모델이 이기지 못하면 더 큰 문자/그래프 모델로 확대하지 않는다.
- **CL-G:** VLM/silver가 이름을 보고 판단하는지 name-blind arm으로 분석할 수 있다. 그러나 P7은 vision을 SoT나 학습 target으로 삼지 않는다.
- **CL-K / P3:** gate-only 대 silver-distill arm 옆에 gate+convention arm을 둬서 “이름 신호”와 “silver 모방”을 구분한다.

### 8.2 차별점

P7은 범용 벽 분류기를 하나 더 만드는 제안이 아니다. 다음 세 계약이 차별점이다.

1. **project-conditional:** 관례 통계는 프로젝트 내부에서만 적합하며 전이 때 freeze/OOV-neutral이다.
2. **gate-constrained:** 관례는 geometry gate 밖에서 어떤 양성도 만들지 못한다.
3. **dependence-measured:** layer shuffle로 성능 하락을 숨기지 않고 이름 의존량 자체를 산출물로 삼는다.

따라서 P7 성공은 “레이어가 오라클”의 부활이 아니다. “보편적이지 않은 신호도 범위와 실패모드를 계측하면 유한한 weight를 가질 수 있다”는 더 제한된 결론이다.

### 8.3 P7이 죽어야 하는 조건

다음 중 하나면 정직하게 죽인다.

1. 정렬 hidden synthetic에서 geometry-only 대비 per-handle F1 lift가 0.15 미만이다.
2. 오정렬 synthetic에서 prior 제거 전후 F1 또는 예측이 변해, 무신호 환경에서 자동 기권하지 못한다.
3. 프로젝트 간 완전 freeze 전이의 주 ΔF1이 0 이하이다. 이 경우 패킷 계약대로 convention 채널을 PARK한다.
4. 이름 prior가 geometry gate 밖 양성을 하나라도 만든다.
5. 성능 이득이 평가 도면의 사전/어휘 재학습, target 현지 적합, 또는 test 반복 개봉에 의존한다.
6. 이득이 `WALL|벽|W` 직접 토큰에만 있고 간접 관례 주장은 살아남지 못한다. 이 경우 broader counter-theory는 죽이고 고정 regex 보조 규칙만 별도 후보로 남긴다.
7. block 복제, 한 firm, 한 언어 또는 한 대형 도면을 제거하면 이득 방향이 뒤집힌다.
8. precision 손실이나 특정 프로젝트의 큰 악화를 micro 평균이 가린다.
9. CubiCasa/FloorPlanCAD처럼 metadata가 없는 축에서 geometry-only와 달라진다. 이는 개선이 아니라 누수다.
10. PR-1 fidelity, PR-2 독립성 감사, PR-3 권리 중 필요한 선결을 통과하지 못한 채 실전 승리를 주장해야만 제안이 유지된다.

반대로 E1의 합성 신호 존재와 E5의 실제 프로젝트 전이 양수를 모두 얻고, 모든 gate·누수·sentinel 계약을 지킨 경우에만 `kills: reigning`을 제안할 수 있다. 그 전까지 P7은 경쟁 가설이며 어떤 프레임도 이 문서만으로 기각·채택되지 않는다. 최종 킬은 봉인된 `v0_gate` 결과만 수행한다.

DOSSIER_COMPLETE: feyerabend_P7
