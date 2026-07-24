# 방법론 심층 도시 — feyerabend 좌석 P2

## 제안명

**단위·치수 정박 후 상대 두께 대역: 절대 좌표 gap 관측의 단위-관례 의존성 분해**

이 문서는 P2 하나만 판별하기 위한 실행 명세다. 핵심 주장은 “평행한 두 선 사이의 절대 좌표 거리”가 아니라 “같은 도면 안의 치수·격자 기준 span에 대한 무차원 거리”가 벽 쌍 검출에 더 가까운 불변량이라는 것이다. 이 주장은 전역 평균 상승이 아니라 다음의 선택적 예측으로만 살아남는다.

1. 치수 정박 신뢰도가 높은 도면정의(def)에서는 상대 대역이 절대 대역보다 나아져야 한다.
2. 정박이 없거나 신뢰도가 낮은 def에서는 안전 폴백 때문에 결과가 기존 절대 대역과 같아야 한다.
3. 좌표 스케일만 바꾼 합성 장면에서는 상대 대역의 예측 쌍이 handle 대응 아래 불변이어야 한다.
4. 실측의 DIM-기하 일관성은 단위 추정만 검증한다. 벽 정답을 대신하지 않는다.

문헌명과 시스템명은 방법론 계보를 밝히기 위한 일반 지식이다. 문헌 성능 수치는 인용하지 않는다. 본문에서 “관측”이라고 부르는 수치는 패킷 다이제스트에만 근거한다. “제안값”, “봉인값”, “예산 상한”은 아직 관측되지 않은 사전등록 설계값이다. 웹 검색은 사용하지 않았다.

---

# 1. 이론적 근거·선행연구

## 1.1 측정이론과 차원해석

P2의 가장 직접적인 계보는 Buckingham의 차원해석과 물리적 상사성이다. 단위가 바뀌어 좌표가 양의 상수 \(\kappa\)만큼 확대되면 길이 \(g\) 자체는 바뀌지만 같은 차원의 두 길이의 비 \(g/S\)는 바뀌지 않는다. 이 원칙은 벽 검출을 물리량 추정 문제로 다시 쓴다.

- 절대 보조가설: \(30 \le g_{\mathrm{raw}} \le 500\).
- 상대 보조가설: \(\alpha_L \le g_{\mathrm{raw}}/S_{\mathrm{ref}}(x) \le \alpha_U\).

장면 스케일 변환을 \(T_\kappa:x\mapsto \kappa x\)라 하고, 같은 규칙으로 기준 span도 \(S\mapsto\kappa S\)가 되면

\[
\frac{\kappa g}{\kappa S}=\frac{g}{S}
\]

이다. 반면 절대 predicate는 \(\mathbf 1[30\le \kappa g\le500]\)이므로 \(\kappa\)에 따라 참·거짓이 바뀐다. P2의 스케일 sweep은 이 차이를 관찰하는 장치이지, 단순한 파라미터 튜닝이 아니다.

관련 계보:

- E. Buckingham, 차원 방정식과 물리적 상사성에 관한 고전 논문: 차원이 같은 양의 비로 단위 의존성을 제거한다.
- David Lowe의 SIFT: 영상에서 좌표 스케일을 nuisance transformation으로 다루고 정규화된 표현을 만든 대표적 선례다.
- Cohen과 Welling의 Group Equivariant Convolutional Networks: 변환군에 대한 equivariance/invariance를 모델 설계에 내장한다는 일반 원리를 제공한다.
- buildingSMART IFC의 IfcUnitAssignment/IfcSIUnit, Autodesk DXF/DWG의 INSUNITS·DIMSTYLE·DIMLFAC·DIMENSION 체계: CAD에서 “좌표 숫자”, “표시 치수”, “물리 단위”가 서로 다른 층이라는 시스템 선례다. 특정 필드의 버전별 세부 의미는 구현 전에 공식 문서로 재확인해야 한다.

마지막 항목은 중요하다. DIMENSION에 보이는 문자열을 곧바로 mm라고 간주하면 P2 자체가 공격하는 오류를 반복한다. 좌표 거리, 치수 기하, 표시 숫자, suffix, style factor, block transform을 분리해 기록해야 한다.

## 1.2 강건한 자기보정

도면에는 stale dimension, text override, 복제된 치수, 잘못된 block transform이 섞일 수 있다. 따라서 단위 추정은 단일 치수 하나를 신뢰하는 lookup이 아니라 여러 독립 anchor의 합의 문제다.

- Fischler와 Bolles의 RANSAC은 소수의 잘못된 대응이 있는 상태에서 최대 합의 모델을 찾는 계보를 제공한다.
- Huber의 robust location estimation은 log-scale 잔차의 극단값 영향을 제한한다.
- weighted median과 median absolute deviation(MAD)은 작은 표본에서도 단일 거대 outlier가 추정을 지배하지 않게 한다.
- mixture model은 한 도면에 서로 다른 dimension style이나 nested block scale이 공존하는 경우를 탐지하는 데 쓸 수 있다. 다만 P2 본시험에서는 불확실한 혼합을 억지로 하나로 합치지 않고 LOW_CONFIDENCE로 내리는 쪽을 택한다.

이 문서의 estimator는 RANSAC 합의군을 고른 뒤 log-ratio Huber loss를 최소화한다. 벽 쌍 라벨과 LLM 판정은 estimator 입력에 들어가지 않는다.

## 1.3 CAD 도면의 단위는 메타데이터 하나가 아니다

AutoCAD 계열에서는 model-space 좌표가 unitless 숫자로 저장될 수 있고, INSUNITS는 삽입 시 해석을 돕는 메타데이터일 뿐 실제 작성 관례와 어긋날 수 있다. DIMENSION 역시 다음 층을 구분해야 한다.

1. extension-line 또는 definition point 사이의 raw world-coordinate 거리
2. dimension entity가 계산한 measurement
3. DIMLFAC 등 style 적용 후의 표시값
4. text override 안의 숫자와 단위 suffix
5. nested INSERT가 적용한 world transform

따라서 “도면 단위 추정”의 출력은 단일 문자열(mm/m/inch)이 아니라 다음의 구조체여야 한다.

- display-unit-per-raw-unit 연속 scale
- 명시 suffix가 있을 때만 가능한 physical-unit 후보
- 합의 잔차와 provenance
- 독립 anchor 수
- HIGH/LOW/NONE 상태

물리 단위명이 UNKNOWN이어도 같은 def 안의 \(g/S\)는 계산할 수 있다. 이것은 실패를 숨기는 편법이 아니라 “단위 이름 식별”과 “스케일 불변 상대 측정”을 분리하는 것이다.

## 1.4 방법론적 위치: 보조가설 교체의 엄격한 판별

이 제안은 Lakatos의 연구프로그램 언어로 보면 “평행쌍이 벽 의미의 유용한 기하 증거”라는 hard core를 유지하면서, “유효 gap은 절대 mm 범위”라는 protective belt를 교체한다. Duhem–Quine 문제 때문에 전체 탐지기 점수가 올랐다는 사실만으로 어느 보조가설이 맞았는지 알 수 없다. 그래서 동일 후보 우주에 절대 predicate와 상대 predicate만 교대로 적용해야 한다.

진보적 belt라면 사전에 말한 곳에서만 개선되어야 한다. 즉 높은 anchor confidence에서 상승하고 낮은 confidence에서는 폴백으로 불변이어야 한다. 전체 평균만 오르고 이 상호작용이 없으면 post-hoc 튜닝 또는 다른 nuisance의 효과일 수 있으므로 P2의 지지가 아니다.

## 1.5 이 계보가 해결하지 않는 것

상대 gap은 scale nuisance를 제거할 뿐 “긴 평행 구조가 벽인가”라는 의미 판별을 해결하지 않는다. 패킷의 CubiCasa 관측에서 v1은 val F1 0.2358, P 0.134, R 0.981이고 Direction·BoundaryPolygon·Door·Window·DimensionMark가 주요 FP였다. 최소길이 필터 천장도 F1 0.335였다. 반면 6특징 HistGradientBoosting은 val F1 0.517, AUC 0.9215였다. 따라서 P2가 가져올 수 있는 것은 다음으로 한정된다.

- 단위 불일치 때문에 후보 단계에서 사라진 진짜 평행쌍의 회수
- thickness feature를 \(g\)에서 \(\log(g/S)\)로 바꾸어 학습기에 더 안정적인 입력 제공
- anchor confidence를 이용한 선택적 적용과 실패 감지

문·창·화살표 같은 의미적 FP 제거, room topology 이해, raster-to-vector 의미 복원은 P2의 주장이 아니다.

---

# 2. 알고리즘 정확 스펙

## 2.1 입력과 출력 계약

### 입력 DefIR

각 def마다 다음 필드를 읽는다.

| 필드 | 의미 |
|---|---|
| def_id | 안정적인 도면정의 식별자 |
| segments | world 좌표로 전개된 선분; 각 선분은 source handle과 geometry type provenance를 보존 |
| dimensions | linear/aligned DIMENSION의 definition points, measurement, displayed text, style id, DIMLFAC 계열 값, handle |
| texts | TEXT/MTEXT의 내용, 삽입점, 회전, text height, handle |
| grids | 명시 grid가 있으면 그 geometry; 없으면 반복 평행 축선 후보 |
| transforms | 원본 INSERT 경로와 누적 affine transform |
| metadata | INSUNITS 등 단위 힌트; 정답이 아니라 약한 증거 |

ARC/SPLINE/HATCH/MLINE을 선분화한 경우 원 geometry handle과 tessellation provenance를 잃지 않는다. P2 전에 world-coordinate 전개가 끝나야 한다. local block 좌표와 world 좌표를 섞으면 unit estimator와 pair gap 양쪽이 동시에 오염된다.

### 출력 AnchorModel

| 필드 | 의미 |
|---|---|
| status | 상대 대역 적용 상태 HIGH, LOW, NONE |
| unit_status | 표시/물리 단위 추정 상태 HIGH, LOW, NONE |
| reference_status | 위치별 reference span 상태 HIGH, LOW, NONE |
| display_per_raw | 표시 치수 단위 / raw 좌표 단위의 강건 추정 |
| physical_unit | MM, CM, M, IN, FT, MIXED, UNKNOWN |
| mm_per_raw | 명시 suffix 또는 강한 메타데이터 합의가 있을 때만 값 존재 |
| consensus_weight | 최대 합의군의 가중치 비율 |
| log_mad | 합의군 log-ratio MAD |
| n_independent | 공간·handle 중복을 제거한 독립 anchor 수 |
| source_diversity | DIM, matched TEXT, GRID 중 사용된 종류 |
| ref_scale_model | 위치 \(x\)에서 \(S_{\mathrm{ref}}(x)\)와 그 confidence를 반환 |
| provenance | 채택·제외된 anchor별 사유 |

### 출력 PairPrediction

각 unordered handle pair에 대해 다음을 기록한다.

- angle difference
- overlap ratio
- raw perpendicular gap \(g\)
- local reference span \(S_{\mathrm{ref}}\)
- dimensionless gap \(\rho=g/S_{\mathrm{ref}}\)
- absolute-30-500 판정
- 현행-v1 판정
- relative 판정
- anchor status/confidence
- fallback 여부와 사유

중복 tessellation segment가 같은 원 handle pair를 여러 번 만들면 최대 overlap의 한 pair로 canonicalize한다. 주 평가는 unordered pair 단위이고, 공용 WSD-EVAL-v1용 보조 출력은 예측 pair 양 끝 handle의 합집합인 wall_member(h)다. pair F1과 per-handle F1을 섞어 쓰지 않는다.

## 2.2 Anchor 추출

### 2.2.1 DIMENSION anchor

linear 또는 aligned DIMENSION \(j\)에 대해 world 좌표에서 실제 치수 방향으로 투영한 span을

\[
d_j=\left|\langle p_{2j}-p_{1j},\,u_j\rangle\right|
\]

로 계산한다. \(d_j\le\epsilon\), angular/radial dimension, definition point 누락, non-finite transform은 제외한다.

표시값 \(v_j\)는 다음 우선순위로 분리 파싱한다.

1. text override에 명시 숫자와 suffix가 있으면 override 값
2. placeholder가 있으면 entity measurement와 style factor로 재구성
3. entity measurement만 있으면 display-unit 후보로 사용하되 physical unit은 UNKNOWN

feet-inch, decimal comma, thousands separator, prefix/suffix, 공차 표기는 parser가 별도 token으로 보존한다. 숫자 두 개가 공차로 나타나면 nominal 값과 tolerance를 분리한다. 해석이 하나로 결정되지 않으면 anchor를 버리지 말고 AMBIGUOUS로 기록하되 fitting weight는 0으로 둔다.

각 사용 가능한 anchor의 log ratio는

\[
z_j=\log(v_j/d_j)
\]

다. 명시 suffix가 있으면 \(v_j\)를 mm로도 변환하여 \(z^{mm}_j=\log(v^{mm}_j/d_j)\)를 별도 계산한다. bare number를 임의로 mm로 바꾸지 않는다.

### 2.2.2 측정 TEXT anchor

독립 TEXT/MTEXT는 다음 기하 조건을 모두 만족할 때만 약한 anchor가 된다.

- 숫자 또는 길이 suffix가 parse됨
- text baseline과 나란한 두 witness/extension line 후보가 존재
- witness 사이의 투영 span이 유일함
- 동일 숫자를 설명하는 DIMENSION과 중복되지 않음

DIMENSION anchor의 제안 base weight는 1.0, matched TEXT는 0.6이다. 이 값은 관측값이 아닌 구현 제안값이다.

### 2.2.3 격자 anchor

GRID는 물리 단위명을 주지 않지만 위치별 기준 span을 제공한다. 세 개 이상의 거의 평행한 장축선에서 인접 간격의 반복 합의가 있거나 명시 grid entity가 있을 때 median adjacent spacing을 span 후보로 만든다. 제안 base weight는 0.4다. 격자만 있는 def는 physical_unit=UNKNOWN일 수 있으나 상대 정박은 가능하다.

### 2.2.4 독립성 축약

같은 handle, 같은 definition points, 같은 text가 복제된 anchor는 하나의 cluster로 접는다. 독립 anchor는 서로 다른 source handle을 가지고, bbox가 완전히 겹치지 않거나 방향·위치가 달라야 한다. 복제 치수 열 개를 독립 증거 열 개로 세지 않는다.

## 2.3 강건 scale fitting

먼저 \(z_j\) 공간에서 제안 tolerance \(\tau_u=\log(1.05)\)인 최대 가중 합의군을 찾는다. 합의군 \(I\)가 정해지면

\[
\hat\mu=\arg\min_\mu\sum_{j\in I}w_j
H_{1.5}\left(\frac{z_j-\mu}{\max(\mathrm{MAD}(z_I),\epsilon)}\right)
\]

를 푼다. \(H_{1.5}\)는 제안 전환점 1.5인 Huber loss다. 최종 display_per_raw는 \(\exp(\hat\mu)\)다.

physical unit은 명시 suffix anchor의 \(z^{mm}\) 합의가 있을 때만 MM/CM/M/IN/FT 후보를 출력한다. INSUNITS는 tie-break와 disagreement flag에만 쓰고 단독으로 HIGH를 만들지 못한다.

단위 ratio의 제안 confidence는 다음과 같다.

\[
C_a=c_{\mathrm{consensus}}\,
\exp(-\mathrm{MAD}_{\log}/\tau_u)\,
\min(1,n_{\mathrm{ind}}/5)\,
\min(1,n_{\mathrm{regions}}/3)
\]

여기서 \(n_{\mathrm{regions}}\)는 def bbox를 3×3으로 나눈 공간 bin 중 anchor가 있는 bin 수다. 방향 다양성은 별도 audit field로 남긴다.

reference span에는 같은 형태의 합의율·log MAD·독립 span 수 confidence \(C_r\)를 별도로 계산한다. DIM/TEXT ratio가 없어도 반복 GRID span이 세 개 이상이고 \(C_r\) gate를 통과하면 unit_status=NONE, reference_status=HIGH가 될 수 있다. 이때 physical unit을 추정했다고 말하지 않지만 무차원 \(g/S_{\mathrm{ref}}\)는 사용할 수 있다.

봉인 상태 규칙:

- unit_status=HIGH: 독립 ratio anchor가 3개 이상, 합의 가중치 비율이 0.80 이상, log MAD가 \(\log(1.05)\) 이하, \(C_a\ge0.75\).
- reference_status=HIGH: 독립 reference span이 3개 이상이고 같은 합의·잔차·confidence gate를 통과함.
- status=HIGH: reference_status=HIGH이며, DIM/TEXT ratio 또는 반복 GRID 중 어느 provenance가 이를 만들었는지 명시됨.
- LOW: 유효 anchor는 있으나 HIGH 조건을 만족하지 못함.
- NONE: 유효 DIM/TEXT/GRID span을 만들 수 없음.
- MIXED_UNIT: 두 개 이상의 강한 mode가 있고 하나가 가중치 0.80을 차지하지 못함. 본시험에서는 LOW로 내려 폴백한다.

모든 숫자는 P2용 제안 봉인값이며 문헌 성능 인용이 아니다.

## 2.4 위치별 reference span

P2가 쓰는 “typical span”은 벽 라벨로 학습한 벽 두께가 아니다. anchor-only architectural reference span이다.

1. 유효 DIM/TEXT의 raw geometric span \(d_j\)와 GRID adjacent spacing을 모은다.
2. text height가 있는 anchor는 \(d_j/h_{\mathrm{text}}\)가 제안 하한 10 미만이면 annotation-scale 후보로 제외한다.
3. 동일 span 복제를 축약한다.
4. log span을 최대 3개 mode로 clustering하되, BIC가 단일 mode보다 낫지 않으면 하나로 둔다.
5. pair midpoint \(x\)에서 거리 가중치
   \[
   q_j(x)=w_j\exp\{-\operatorname{dist}(x,\mathrm{bbox}_j)/(2S_{\mathrm{global}})\}
   \]
   를 계산한다.
6. local support가 가장 큰 mode의 weighted log-median을 \(S_{\mathrm{ref}}(x)\)로 쓴다.
7. 최다 mode posterior가 제안값 0.60 미만이면 그 위치는 LOW로 내려 폴백한다.

이 방식은 def 전체에 하나의 span을 강제하지 않아 wing별 scale 또는 detail inset을 일부 견딘다. 그러나 같은 위치에 curtain wall과 이중 외피가 공존해 thickness가 다봉이면 단일 \([\alpha_L,\alpha_U]\)가 여전히 실패할 수 있다. 그 경우 본시험 결과를 사후 mixture band로 구제하지 않는다. 별도 후속 제안으로 분리한다.

## 2.5 Pair 후보와 두 팔

공통 기하 predicate는 패킷의 v1 구조를 따라 다음을 고정한다.

- 방향차: modulo \(\pi\) 기준 2° 이하
- 투영 overlap ratio: 0.5 이상
- 동일 원 handle의 자기쌍 제외
- world-coordinate transform 적용

Primary synthetic A/B의 두께 predicate만 다르다.

\[
A_{30}(g)=\mathbf 1[30\le g_{\mathrm{raw}}\le500]
\]

\[
R(g,x)=\mathbf 1[0.05\le g_{\mathrm{raw}}/S_{\mathrm{ref}}(x)\le0.40]
\]

여기서 0.05와 0.40은 패킷 예시를 본시험 봉인값으로 승격한 것이다. 본시험 결과를 본 뒤 바꾸지 않는다.

패킷 mechanism의 30–500 raw 대역과 다이제스트의 현행 v1 50–400mm 대역은 같은 baseline으로 뭉개지 않는다.

- A30: P2의 이론 판별용 primary absolute arm
- A50: 현행 fast_score 생산 설정을 그대로 재현하는 shadow arm
- R05-40: 상대 대역 arm

A50의 실제 코드가 raw 좌표를 mm로 가정하는지, 앞단에서 단위 변환하는지는 T9/T21 baseline freeze 단계에서 설정·입출력을 있는 그대로 기록한다. 확인 전에는 재해석하지 않는다.

실측 def에서 R arm은 다음 선택적 정책을 쓴다.

\[
\operatorname{P2}(g,x)=
\begin{cases}
R(g,x),&\text{anchor status=HIGH and local span confidence pass}\\
A_{\mathrm{frozen}}(g),&\text{otherwise}
\end{cases}
\]

따라서 LOW/NONE에서 결과가 달라지면 구현 버그다. “정박 실패에서 악화할 수 있다”는 원 제안보다 더 보수적인 안전 정책이며, 선택적 개선 가설을 더 명료하게 만든다. 별도 diagnostic arm에서는 폴백 없이 relative-only를 실행해 실패 양상을 관찰하되 합격 판정에는 쓰지 않는다.

## 2.6 후보 폭발 방지

합성 장면에서는 orientation bin과 interval sweep으로 모든 공통 predicate 후보를 열거한 뒤 두 gap predicate를 offline 적용한다. 이로써 A/R 차이는 gap 하나뿐이다.

실측에서는 각 orientation bin에 interval tree와 spatial index를 만들고, A와 R 어느 쪽이든 통과할 수 있는 union search envelope를 사용한다. 다음을 사전등록한다.

- def별 candidate comparison 상한: 제안값 20,000,000
- segment별 반환 이웃 상한: 제안값 128
- 상한 도달 시 silent truncation 금지
- 해당 def 상태를 RESOURCE_ABORT로 기록하고 상관 계산에서 임의 제외하지 않음
- 30-def 표본에서 RESOURCE_ABORT가 하나라도 생기면 production readiness는 FAIL; 알고리즘 판별은 별도 “자원 한계로 불완전” 상태

이 상한은 관측 성능 수치가 아니라 RAM 64GB 로컬 실행을 위한 예산 제안이다. 최대 def에 선분 412,775개가 있다는 패킷 관측 때문에 \(O(n^2)\) 열거는 허용하지 않는다.

## 2.7 정확 의사코드

~~~text
function FIT_ANCHOR_MODEL(def_ir):
    dims  = extract_linear_dimension_anchors(def_ir.dimensions,
                                             def_ir.transforms)
    texts = match_measurement_text_anchors(def_ir.texts, def_ir.segments)
    grids = extract_grid_spans(def_ir.grids, def_ir.segments)

    anchors = canonicalize_duplicates(dims + texts + grids)
    ratio_anchors = [a for a in anchors if a.display_value is unambiguous
                     and a.raw_span > epsilon]

    if ratio_anchors is empty and grids is empty:
        return AnchorModel(status=NONE, provenance=all_rejections)

    if ratio_anchors is empty:
        best, mu = NONE, NA
        unit_stats = confidence_none()
    else:
        modes = ransac_log_ratio_modes(ratio_anchors, tolerance=log(1.05))
        best  = maximum_weight_mode(modes)
        mu    = huber_location(best.log_ratios, best.weights, delta=1.5)
        unit_stats = confidence_stats(best, ratio_anchors)

    ref_model = fit_spatial_reference_spans(
        spans=valid_raw_spans(anchors),
        max_modes=3,
        annotation_ratio_min=10,
        local_mode_posterior_min=0.60
    )

    unit_status = gate_unit(unit_stats,
                            n_independent_min=3,
                            consensus_min=0.80,
                            log_mad_max=log(1.05),
                            confidence_min=0.75)
    reference_status = gate_reference(ref_model,
                                      n_independent_min=3,
                                      consensus_min=0.80,
                                      log_mad_max=log(1.05),
                                      confidence_min=0.75)
    status = HIGH if reference_status == HIGH else
             (LOW if anchors is nonempty else NONE)

    return AnchorModel(status, unit_status, reference_status,
                       display_per_raw=(exp(mu) if mu is not NA else NA),
                       physical_unit=infer_physical_unit(best),
                       ref_model, provenance=anchors)


function SCORE_DEF(def_ir, frozen_absolute_config):
    anchor = FIT_ANCHOR_MODEL(def_ir)
    candidates = enumerate_parallel_overlap_candidates(
        def_ir.segments, angle_max=2deg, overlap_min=0.5,
        union_search_envelope=(absolute_band, anchor.relative_band),
        resource_caps=FROZEN_CAPS
    )

    rows = []
    for c in candidates:
        g = perpendicular_gap(c)
        abs30 = (30 <= g <= 500)
        absv1 = frozen_absolute_config.accept_gap(g)

        if anchor.status == HIGH:
            S, local_conf = anchor.ref_scale_model(c.midpoint)
        else:
            S, local_conf = NA, LOW

        rel_diag = (local_conf == HIGH
                    and 0.05 <= g / S <= 0.40)
        rel_safe = rel_diag if local_conf == HIGH else absv1

        rows.append(canonical_pair_row(c, g, S,
                                      abs30, absv1, rel_diag, rel_safe,
                                      anchor.status))

    return deduplicate_by_source_handle_pair(rows)


function SCALE_SCENE(base_scene, kappa):
    scaled_geometry = multiply_all_world_coordinates(base_scene, kappa)
    displayed_dimensions = keep_physical_display_values_consistent(base_scene)
    scaled_styles = transform_annotation_geometry_consistently(base_scene, kappa)
    truth_pairs = preserve_source_handle_pairs(base_scene)
    return IR(scaled_geometry, displayed_dimensions, truth_pairs,
              truth_unit_scale=base_scene.truth_unit_scale / kappa)
~~~

## 2.8 손실, 지표, 하이퍼파라미터 공간

### Anchor loss

주 손실은 앞의 weighted Huber log-ratio loss다. pair label은 이 loss에 등장하지 않는다. confidence calibration용 synthetic truth에는 다음을 쓴다.

\[
e_s=|\log(\hat s/s_{\mathrm{true}})|
\]

### Pair metrics

\[
P=\frac{TP}{TP+FP},\quad
R=\frac{TP}{TP+FN},\quad
F1=\frac{2PR}{P+R}
\]

정답은 unordered source-handle pair다. 한 벽의 tessellation 조각 수가 점수를 부풀리지 못하게 한다.

### 봉인 설정과 비결정 탐색

| 항목 | 본시험 봉인값 | 개발 sensitivity 공간 | 규칙 |
|---|---:|---:|---|
| relative lower \(\alpha_L\) | 0.05 | {0.03, 0.05, 0.08} | 본시험 후 교체 금지 |
| relative upper \(\alpha_U\) | 0.40 | {0.20, 0.30, 0.40} | \(\alpha_L<\alpha_U\) |
| angle tolerance | 2° | 고정 | gap 효과 격리 |
| overlap minimum | 0.5 | 고정 | gap 효과 격리 |
| RANSAC log tolerance | log(1.05) | {log(1.02), log(1.05), log(1.10)} | anchor-only dev에서만 |
| HIGH confidence | 0.75 | {0.65, 0.75, 0.85} | real 30을 보기 전에 동결 |
| local mode posterior | 0.60 | {0.50, 0.60, 0.75} | 불확실하면 폴백 |
| max span modes | 3 | {1, 2, 3} | label-free BIC 선택 |

Sensitivity 결과는 robustness 설명용이며 prereg verdict를 대체하지 않는다. best-cell 보고만 하는 것을 금지하고 전체 grid를 evidence xlsx에 남긴다.

## 2.9 불변식과 누수 금지 규칙

1. FIT_ANCHOR_MODEL 호출 그래프에는 truth_pairs, wall_member, LLM likelihood, layer-name wall token이 없어야 한다.
2. pair label 파일을 순열화해도 anchor와 prediction bytes가 같아야 한다.
3. 동일 base scene의 네 scale은 handle mapping이 같아야 한다.
4. anchor confidence threshold는 실측 pair count나 Pearson을 본 뒤 바꾸지 않는다.
5. 실측 LLM likelihood는 frozen E1 산출물만 읽고 재질의하지 않는다.
6. A와 R은 같은 normalized geometry와 같은 후보 우주를 쓴다.
7. INVALID, RESOURCE_ABORT, NO_VARIANCE를 0점이나 PASS로 바꾸지 않는다.

---

# 3. 벽 과업 적응 설계

## 3.1 1.dwg 실도면축

패킷에는 staged DXF에서 384개 def가 있고, v0의 벽-제로 도면율이 0.682에서 0.2135로 내려간 관측, 탐지기와 silver 판정자의 Pearson 0.2911 관측이 있다. P2는 이 전역 수치를 재인용해 성공을 주장하지 않는다. 새 A/B는 다음과 같이 제한한다.

1. pair 결과와 LLM likelihood를 보지 않고 valid DIM anchor 수로 def를 정렬한다.
2. tie는 def_id lexical order로 고정한다.
3. 상위 30개를 manifest에 봉인한다.
4. 각 def에 대해 A30, frozen A50, R-diagnostic, R-safe를 같은 candidate table에서 계산한다.
5. anchor confidence HIGH/LOW/NONE를 pair 결과 전에 저장한다.
6. DIM-geometry residual로 단위 추정 내부 일관성만 평가한다.
7. frozen silver likelihood와 pair count의 Pearson을 A와 R에서 각각 계산한다.

실측에는 사람 pair 정답이 없으므로 “recall 상승”이라고 쓰지 않는다. 관찰 가능한 것은 pair count 변화, DIM-기하 consistency, frozen LLM likelihood와의 상관 변화다. Pearson은 독립 truth가 아니라 보조 판별자다.

선택적 예측의 실측 operationalization:

- HIGH subset: median pair-count difference \(N_R-N_A>0\)이고, Pearson 차이 \(\delta r=r_R-r_A\ge+0.05\)여야 한다.
- LOW/NONE subset: R-safe와 frozen absolute prediction이 pair-id 수준에서 완전히 같아야 한다.
- HIGH def가 10개 미만이거나 어느 arm의 pair count/likelihood 분산이 0이면 verdict는 INCONCLUSIVE다. PASS로 간주하지 않는다.

패킷 kill condition에 따라 치수 정박 가능한 subset에서도 \(\delta r<+0.05\)이면 이 belt는 퇴행적이다. 신뢰구간이 넓더라도 point estimate가 문턱 아래면 kill을 유예하지 않는다. point estimate가 문턱을 넘더라도 def bootstrap의 95% interval 하한이 0 이하이면 “방향성은 맞지만 불확실”로 기록하고 production 채택은 보류한다. 이 interval 규칙은 추가 보수 규칙이다.

## 3.2 CubiCasa SEG-IR 벡터축

CubiCasa5k는 5,000도면이 SEG-IR로 변환되었고 실패는 0이며, 좌표는 px이고 도면별 축척은 미상이다. 벽두께 px p50=22라는 관측이 있지만 이는 개별 도면의 DIM anchor가 아니다. 따라서 p50을 모든 도면의 \(S_{\mathrm{ref}}\)로 넣는 것은 P2가 공격하는 전역 관례 prior를 px로 되풀이하는 것이다.

적응 원칙:

- CubiCasa SEG-IR에 실제 DIM/TEXT/GRID anchor가 없으면 status=NONE.
- R-safe는 v1의 frozen gap 결과와 bitwise-equivalent해야 한다.
- CubiCasa val 400은 폴백 회귀검사에만 사용한다.
- test 400은 P2 cheapest probe에서 열지 않는다.
- synthetic DIM을 CubiCasa에 덧붙인 실험은 합성 진리 축으로만 표시하고 외부 사람라벨 실측 증거라고 부르지 않는다.

P2가 향후 anchor-bearing vector dataset에 연결되면 cubicasa_ir의 segment schema와 동일한 pair feature row를 만들 수 있다. 그러나 현재 자산만으로 P2가 CubiCasa val F1 0.2358 또는 GBDT val F1 0.517을 넘는다고 주장할 수 없다.

GBDT와의 접속은 후보가 누락되지 않은 이후의 조건부 단계다. 기존 6특징에 다음을 추가할 수 있다.

- log_relative_gap
- anchor_confidence
- unit_consensus_residual
- local_scale_mode_id
- fallback_flag

이 추가 feature의 유용성은 anchor가 실제로 있는, 사람 라벨된 vector val이 생겼을 때만 평가한다. 기존 CubiCasa에 가짜 anchor를 넣어 얻은 상승은 production evidence가 아니다.

## 3.3 FloorPlanCAD 래스터축

FloorPlanCAD는 래스터 5,308장과 wall bbox/segmask가 있으나 vector SVG가 없다는 것이 패킷 사실이다. P2의 estimator는 extension points와 source handle을 요구하므로 바로 접속할 수 없다.

가능한 후속 bridge는 OCR로 측정 text를 읽고 line detector로 witness/grid span을 복원하는 것이다. 하지만 이 bridge에는 OCR 오류, pixel-to-geometry correspondence, raster scale이라는 별도 nuisance가 생긴다. P2 cheapest probe에는 포함하지 않는다. 현 단계의 FloorPlanCAD 역할은 다음뿐이다.

- anchor_unavailable을 명시적으로 반환하는 schema test
- raster 자산이 있다는 이유만으로 상대 gap 실측 증거가 생긴 것처럼 쓰지 않는 negative scope check

## 3.4 fast_score 및 4증거 채널

현행 v1은 parallel 0.35, thickness 0.25, junction 0.20, layer 0.20 가중합이다. P2는 parallel/junction/layer를 재튜닝하지 않는다.

1차 판별에서는 binary gap predicate만 A/R로 바꿔 pair F1을 측정한다. 2차 통합에서는 thickness channel의 입력을 raw gap membership에서 relative-gap membership 또는 smooth score로 바꾼다.

제안 smooth score:

\[
e_t(\rho)=
\begin{cases}
1,&0.05\le\rho\le0.40\\
\max(0,1-|\log(\rho/0.05)|/\log2),&\rho<0.05\\
\max(0,1-|\log(\rho/0.40)|/\log2),&\rho>0.40
\end{cases}
\]

가중치 0.25와 최종 decision threshold는 frozen v1 값을 유지한다. smooth score는 binary primary verdict를 통과한 뒤에만 shadow 평가한다. 이를 먼저 튜닝하면 gap 표현과 score calibration 효과가 섞인다.

## 3.5 예상되는 이득과 정직한 상한

가능한 이득:

- raw 좌표가 m, cm 또는 비표준 block scale인 def의 systematic zero-pair 감소
- 단위 변환 metamorphic failure의 원인 분해
- GBDT가 scale에 따라 다른 raw thickness를 다시 학습해야 하는 부담 감소
- anchor confidence를 이용한 abstention

불가능하거나 아직 증명되지 않은 이득:

- semantic FP의 근본 제거
- 사람 라벨 기준 실도면 pair F1 상승
- CubiCasa test 상승
- silver를 truth로 승격
- B1 fidelity FAIL을 무시한 합성 결과의 일반화

---

# 4. 데이터·컴퓨트 요구

## 4.1 필요한 데이터

### A. 다스케일 벽 합성 IR

PR-1의 지적대로 현재 synthetic_truth.py는 dimension 전용이고 벽 코드가 0이라는 것이 패널 사실이다. 그러므로 먼저 실제 wall-pair generator를 구현해야 한다. canonical base scene 50개 각각에

\[
\kappa\in\{0.001,0.01,1,1000\}
\]

을 적용하여 총 200 IR을 만든다. 같은 base scene의 네 버전은 source handles와 truth pair를 공유한다.

각 scene은 최소한 다음 mutation family를 manifest에 가진다.

- 순수 LINE 평행쌍
- LWPOLYLINE 분절
- ARC/SPLINE 인접 또는 교란
- HATCH boundary 교란
- nested INSERT와 non-uniform/누적 transform
- 부분 overlap과 거의 평행한 조각
- door/window/dimension-like 긴 평행 distractor
- zero-wall sentinel
- all-wall sentinel
- 단일·다중 reference span 영역

표시 치수값은 canonical physical geometry와 일관되게 유지하고 raw 좌표만 \(\kappa\)배 한다. 따라서 truth unit scale은 \(1/\kappa\) 방향으로 바뀌며 pair label은 그대로다.

### B. 1.dwg의 DIM-rich 30 def

선정에 pair 결과, layer-name wall token, LLM likelihood를 사용하지 않는다. 추출할 데이터:

- DIM/TEXT/GRID anchor table
- 누적 transform provenance
- A/R 공통 candidate table
- frozen LLM likelihood
- def-level pair counts

### C. 폴백 회귀 데이터

- CubiCasa val 400 SEG-IR
- DIM 없는 최소 synthetic fixtures
- FloorPlanCAD adapter의 anchor_unavailable schema fixture

CubiCasa test 400은 열지 않는다.

## 4.2 저장 산출물

실제 실험 실행 시 하나의 run directory에 다음을 남긴다.

- manifest.json: split, seed, \(\kappa\), config digest, 입력 artifact digest
- anchors.parquet: 모든 채택·제외 anchor와 사유
- pair_candidates.parquet: 공통 후보 및 양 arm 판정
- metrics.json: scale별 pair P/R/F1, metamorphic consistency, correlation
- evidence.xlsx: 필수 심사 표
- failures.jsonl: INVALID/RESOURCE_ABORT/NO_VARIANCE 포함
- prereg.json: 실행 전에 봉인한 threshold

evidence.xlsx의 권장 sheet:

1. README
2. PREREG
3. SYNTHETIC_SCENES
4. ANCHOR_AUDIT
5. PAIR_METRICS
6. REAL_30_AB
7. CONTROLS
8. FAILURES

실패 행을 삭제하지 않고 reason code와 분모 포함 여부를 기록한다.

## 4.3 로컬 컴퓨트 계획

패킷 자산인 RAM 64GB와 로컬 CPU를 기준으로 한다. RTX 5070 Ti 16GB는 필요하지 않다.

- anchor parsing/fitting: CPU, def 단위 streaming
- pair enumeration: NumPy fast_score 접속, orientation bin별 batch
- xlsx: 메트릭 집계 후 작성하여 candidate 전체를 workbook에 중복 적재하지 않음
- 30 real def: 한 번에 한 def를 처리하고 parquet를 flush
- candidate cap 도달 시 메모리 증설로 숨기지 않고 RESOURCE_ABORT

Cheapest probe의 운영 예산은 패킷대로 로컬 1일 미만을 목표로 한다. 이는 완료 관측이 아니라 계획 상한이다. 제안 분배는 generator/fidelity 준비 2시간, synthetic anchor 및 A/B 2시간, 통제 1시간, real 30 A/B 4시간, 증거 패키징 1시간이다. 어느 단계든 선결 gate가 실패하면 뒤 단계를 PASS 생산 목적으로 강행하지 않는다.

## 4.4 DGX 계획

DGX Spark가 현재 unreachable이라는 패킷 사실과 무관하게 P2는 DGX를 요구하지 않는다.

- DGX 필수 작업: 없음
- DGX가 복구되어도 이동할 작업: 없음
- VLM 재질의: 없음
- frontier API 결재: 없음

DGX를 사용하면 좋아진다는 서술도 하지 않는다. 이 실험의 병목은 모델 추론이 아니라 후보 열거와 증거 규율이다.

---

# 5. 구현 계획

아래는 향후 구현할 파일 골격이다. 이 dossier 작성 시에는 이 산출물 파일 외 다른 파일을 만들지 않는다.

## 5.1 모듈 골격

~~~text
e2/
  unit_anchor/
    schema.py                 # Anchor, AnchorModel, reason code
    dimension_parser.py       # DIMENSION/style/override/suffix parsing
    text_anchor.py            # TEXT/MTEXT measurement matching
    grid_anchor.py            # repeated grid span extraction
    robust_scale.py           # RANSAC + Huber + confidence
    local_reference.py        # S_ref(x), mode/fallback
  detector/
    relative_gap.py           # A30/A50/R predicates
    pair_universe.py          # shared orientation/interval candidate universe
  synthetic/
    wall_synthetic_truth.py   # actual wall pairs, distractors, scale transform
    fidelity_gate.py          # divergent-20 phenomenon coverage
  experiments/
    p2_prereg.py
    run_p2_synthetic.py
    run_p2_real30.py
    run_p2_controls.py
    export_p2_evidence.py
  tests/
    test_dimension_parser.py
    test_anchor_label_blindness.py
    test_scale_invariance.py
    test_fallback_identity.py
    test_candidate_caps.py
~~~

## 5.2 기존 도구 접속점

패킷에 이름만 주어진 도구의 내부 API는 가정하지 않는다. 다음 adapter boundary로 접속한다.

### evidence_grid

- 입력: long-form metric rows
- 추가 key: proposal_id, arm, def_id, base_scene_id, scale, seed, anchor_status, failure_code
- 출력: evidence.xlsx와 machine-readable metrics
- 요구: 실패 행과 분모를 보존

### fast_score

- 기존 parallel/overlap/junction/layer 계산은 동결
- gap predicate를 함수 인자로 받는 얇은 adapter 추가
- A와 R이 같은 candidate IDs를 받는지 assertion
- 현행 50–400 설정을 config snapshot으로 먼저 저장

### cubicasa_ir

- SEG-IR segment를 DefIR adapter로 변환
- dimension/text/grid가 없으면 명시적 빈 collection
- px p50을 anchor로 주입하지 않음

### cubicasa_ml

- 본 P2 probe에서는 재학습하지 않음
- 후속 조건부 실험에서 relative feature columns만 추가
- 기존 6특징 arm과 동일 split·row order·label mask 유지
- shuffle control을 동일하게 재실행

## 5.3 구현 순서와 stop rule

1. prereg.json schema와 판정 함수를 먼저 작성한다.
2. A30과 frozen A50 baseline을 재현하고 prediction digest를 봉인한다.
3. wall synthetic generator를 실제 구현한다.
4. fidelity gate를 통과시킨다.
5. anchor parser와 label-blindness test를 통과시킨다.
6. 200 synthetic IR을 한 번 생성하고 manifest를 봉인한다.
7. synthetic scale sweep을 단발 실행한다.
8. 통제가 통과한 경우에만 real 30을 실행한다.
9. evidence.xlsx와 verdict를 생성한다.

다음 경우 즉시 중단한다.

- wall generator가 없는 dimension-only truth를 발견
- truth pair가 anchor fitter에 전달됨
- A/R candidate universe가 다름
- scale transform 뒤 handle 대응이 깨짐
- candidate cap을 silent truncation하는 코드 경로가 있음

## 5.4 예상 개발 규모

Cheapest discriminating probe는 parser의 제한된 DIM subset, wall generator, 세 실행기, 증거 exporter로 구성되는 중간 규모 로컬 작업이다. 계획 추정은 한 명 기준 probe 구현·실행 1일, production hardening 3–5일이다. 후자의 범위에는 feet-inch parser, nested block, mixed styles, detailed xlsx QA가 포함된다. 이는 관측 생산성이 아니라 일정 제안값이다.

## 5.5 검증 체크리스트

- UTF-8로 모든 def/text ID round-trip
- NaN/Inf dimension 거부
- reflection과 negative scale에서 방향 canonicalization
- non-uniform INSERT는 dimension direction 투영으로 처리
- DIM override와 entity measurement를 별도 열로 보존
- pair-id 정렬 안정성
- 같은 seed/manifest 재실행 시 metrics digest 동일
- LOW/NONE fallback의 pair set 완전 동일
- empty-positive scene에서 F1을 임의 1로 만들지 않음
- zero variance Pearson을 0으로 치환하지 않음

---

# 6. 실험 셀 정의

모든 threshold는 실행 전 prereg.json과 evidence.xlsx PREREG sheet에 동시에 봉인한다. primary 설정을 본 뒤 sensitivity 설정으로 판정을 교체하지 않는다.

## 셀 C0 — 실제 벽 합성기 및 fidelity 자격

**가설.** 새 generator가 dimension-only stub이 아니라 source-handle pair truth를 만들며, 기존 합성팩의 표현 결손을 줄인다.

**데이터.** canonical base scene 50개와 divergent-20에서 추출한 phenomenon checklist. scale copy 전 \(\kappa=1\) 장면으로 fidelity를 본다.

**지표.**

- wall truth pair가 실제 존재하는 scene 비율
- LINE/LWPOLYLINE/INSERT 외 ARC/SPLINE/HATCH와 nested block/nonparallel fragment coverage
- real-vs-synthetic entity/geometry distribution KS와 TV
- zero-wall/all-wall sentinel의 truth integrity

**제안 합격선.**

- positive scene에는 하나 이상의 source-handle truth pair
- 지정 mutation family가 각각 최소 한 scene에 존재
- 제안 fidelity gate: KS ≤ 0.20, TV ≤ 0.10
- truth validator 오류 0

KS/TV 문턱은 문헌 인용이 아니라 사전등록 제안값이다. 패킷의 기존 B1 관측 KS 0.5792, TV 0.265보다 엄격한 자격을 요구한다.

**킬/중단 조건.** wall code가 없거나 fidelity gate가 실패하면 synthetic 결과는 plumbing diagnostic만 가능하며 P2 이론 판별 PASS를 금지한다. PR-1/T2 BLOCKED로 종료한다.

**예산.** 로컬 CPU와 운영자 2시간 상한.

**시드.** base scene \(j=0,\ldots,49\)의 seed는 SHA-256("feyerabend_P2:"+j)의 앞 32bit로 결정한다. 동일 \(j\)의 네 scale은 같은 seed와 topology를 쓴다.

## 셀 C1 — Anchor scale 추정과 confidence calibration

**가설.** 벽 pair label 없이 DIM/TEXT/GRID만으로 raw-unit scale을 추정하며, HIGH confidence가 실제 정답 scale과 일치하는 선택적 subset을 만든다.

**데이터.** C0를 통과한 200 IR. anchor corruption diagnostic에는 복제, stale override, suffix 제거, 한 개 outlier를 deterministic mutation으로 추가한다.

**지표.**

- \(e_s=|\log(\hat s/s_{\mathrm{true}})|\)
- HIGH subset의 scale-factor relative error
- HIGH coverage
- confidence bin별 accuracy
- corruption 전후 status transition
- pair-label permutation 전후 anchor artifact digest

**제안 합격선.**

- HIGH subset의 95% 이상이 true scale 대비 상대오차 5% 이하
- 네 scale 각각 HIGH coverage 0.60 이상
- pair-label permutation 전후 anchor digest 완전 동일
- 단일 강한 outlier가 들어가도 scale mode가 바뀌지 않거나 status가 LOW로 내려감

모두 제안값이다.

**킬 조건.** HIGH가 틀린 scale을 자신 있게 내거나, label permutation이 anchor output을 바꾸거나, scale별 confidence coverage가 한 방향으로 붕괴하면 counter theory의 실행체를 kill한다.

**예산.** 로컬 CPU 1시간 상한.

**시드.** C0의 paired 50 seeds 재사용. corruption 종류는 base_scene_id hash로 고정하며 추가 random search는 하지 않는다.

## 셀 C2 — Primary 4-scale absolute 대 relative 판별

**가설.** 좌표 스케일만 바뀌면 A30은 극단 scale에서 붕괴하고 R05-40은 모든 scale에서 유지된다.

**데이터.** 4 scale × 50 IR = 200, 동일 handle truth. C0/C1 통과 후 한 번만 판정한다.

**지표.**

- scale별 unordered pair precision, recall, F1
- base scene별 paired \(F1_R-F1_A\)
- mapped pair-set Jaccard across scales
- per-handle wall_member F1은 보조
- A50 shadow 결과는 별도 열

**제안 합격선.**

- 모든 \(\kappa\in\{0.001,0.01,1,1000\}\)에서 relative-gap pair F1 ≥ 0.85
- \(\kappa\le0.01\) 또는 \(\kappa\ge100\)인 평가점에서 absolute-gap pair F1 ≤ 0.40
- relative mapped pair-set Jaccard ≥ 0.95

앞의 두 문턱은 패킷 prereg band다. Jaccard 문턱은 추가 제안값이다.

**판별.**

- A: absolute만 붕괴하고 relative가 유지되면 kills: reigning, 즉 절대 gap 관측을 기각한다.
- B: relative도 동반 붕괴하면 kills: counter.
- absolute가 극단에서도 유지되면 P2가 상정한 단위-유물 메커니즘이 이 harness에서 작동하지 않은 것이므로 reigning을 죽이지 못한다.

**예산.** 로컬 CPU 2시간 상한.

**시드와 도면-단위 split.** paired 50 seeds를 쓴다. scale은 seed가 아니라 완전요인이다. parser와 threshold 개발은 이 200 IR에 포함되지 않는 손계산 \(\kappa=1\) fixture에서 끝내고, 네 scale의 200 IR은 모두 config 봉인 뒤 한 번 여는 평가 split으로 둔다. scale별 별도 tuning, 한 scale 결과를 본 뒤 다른 scale 설정 변경, 같은 base scene의 다른 scale label을 estimator 입력으로 전달하는 것을 금지한다.

## 셀 C3 — 누수·sentinel·metamorphic 통제

**가설.** C2의 승패는 라벨 누수나 “모두 벽” 예측이 아니라 scale normalization에서 온다.

**데이터.** C2의 200 IR에 포함된 zero-wall/all-wall 및 distractor scenes, pair-label permutation, dimension-table def permutation.

**지표.**

- label permutation 전후 prediction artifact digest
- zero-wall false-positive pair rate
- all-wall recall
- rigid transform/translation/reflection 뒤 mapped pair Jaccard
- dimension-table permutation 뒤 confidence와 scale error

**제안 합격선.**

- pair-label permutation 전후 prediction digest 동일
- zero-wall distractor 후보 중 false-positive rate ≤ 0.10
- all-wall pair recall ≥ 0.85
- 강체변환 mapped Jaccard = 1.0
- 잘못된 def의 dimension table을 주입하면 HIGH를 유지한 채 정답 scale로 우연히 맞는 현상이 반복되지 않음

**킬 조건.** label permutation이 예측을 바꾸거나, sentinel floor를 못 넘거나, 강체변환이 깨지면 C2 결과를 INVALID 처리한다. dimension permutation에서도 성능이 유지되면 anchor가 실제로 사용되지 않았을 가능성이 있으므로 메커니즘 주장을 kill한다.

**예산.** 로컬 CPU 1시간 상한.

**시드.** def permutation은 SHA-256 manifest 순서의 cyclic shift 하나로 봉인한다. 여러 permutation 중 유리한 것만 고르지 않는다.

## 셀 C4 — 실측 DIM-rich 30 def 선택적 A/B

**가설.** HIGH anchor subset에서 R-safe가 frozen absolute arm보다 frozen LLM likelihood와의 pair-count 상관을 단방향으로 높이고, LOW/NONE에서는 정확히 불변이다.

**데이터.** 1.dwg staged DXF의 384 def 중 pair/LLM 결과를 보지 않고 valid DIM 수 상위 30개. 동률은 def_id 순서. LLM likelihood는 기존 frozen artifact만 사용한다.

**지표.**

- anchor status와 DIM-geometry log residual
- def별 \(N_A,N_R,N_R-N_A\)
- HIGH subset의 Pearson \(r_A,r_R,\delta r\)
- paired def bootstrap 95% interval
- LOW/NONE pair-id exact equality
- RESOURCE_ABORT 수

**제안 합격선.**

- HIGH def가 최소 10개
- HIGH subset median \(N_R-N_A>0\)
- \(\delta r\ge+0.05\)
- bootstrap interval 하한 > 0이면 production-adoption eligible
- LOW/NONE에서 pair-id equality = 1.0
- RESOURCE_ABORT = 0

**킬 조건.** 패킷 규칙대로 anchor 가능한 subset에서 \(\delta r<+0.05\)이면 belt는 퇴행적이며 kills: counter다. HIGH가 10개 미만, Pearson 입력이 무분산, 또는 frozen likelihood를 찾지 못하면 INCONCLUSIVE이며 PASS 금지다. 전체 30 평균이 올라도 HIGH 상호작용이 없으면 실패다.

**예산.** 로컬 CPU 4시간과 candidate comparison 상한. 초과 시 자원 실패를 기록한다.

**시드.** detector와 anchor fitter는 결정론적이다. bootstrap만 SHA-256("feyerabend_P2:real30")에서 파생한 단일 seed로 10,000 resample을 고정한다. 이는 제안 계산값이다.

## 셀 C5 — no-anchor 폴백 회귀와 기존 사다리 접속

**가설.** DIM 정박이 불가능한 데이터에서는 P2가 거짓 개선이나 회귀를 만들지 않는다.

**데이터.** CubiCasa val 400 SEG-IR, DIM 없는 synthetic fixtures, FloorPlanCAD adapter fixture. CubiCasa test는 사용하지 않는다.

**지표.**

- frozen v1과 R-safe의 predicted handle/pair digest equality
- val P/R/F1 delta
- fallback reason coverage
- cubicasa_ml row count/order equality

**제안 합격선.**

- prediction digest equality = 1.0
- 모든 metric delta = 0
- 모든 no-anchor item에 explicit NONE reason

패킷의 기존 CubiCasa v1 val F1 0.2358을 재측정 결과처럼 새로 주장하지 않는다. 이 셀의 요구는 수치 개선이 아니라 동일성이다.

**킬 조건.** anchor가 없는데 결과가 달라지면 안전 폴백 구현을 kill한다. 우연한 val 상승도 P2 지지로 세지 않는다.

**예산.** 로컬 CPU 1시간 상한.

**시드.** 없음. byte-level 결정론 비교.

## 6.1 조건부 단발 test 정책(현재 실험 셀 아님)

현재 자산에는 DIM-bearing real vector human pair-label test가 명시되어 있지 않다. 따라서 P2만을 위해 CubiCasa test 400을 소비하지 않는다.

향후 독립적인 DIM-bearing human-labelled vector test가 확보될 때만 다음 조건으로 단발 실행한다.

- C0–C5가 모두 유효
- \(\alpha\), confidence, candidate cap, parser version 동결
- test 접근 1회
- 주 지표 pair F1, 보조 per-handle F1
- scale/firm 단위 split
- 실패도 evidence.xlsx에 유지

그 전까지 “test PASS” 상태는 존재하지 않는다.

## 6.2 통합 판정 함수

~~~text
if C0 fails:
    verdict = BLOCKED_PR1_T2
elif C1 or C3 fails:
    verdict = INVALID_MECHANISM
elif any(relative_F1_by_scale < 0.85):
    verdict = KILLS_COUNTER_SYNTHETIC
elif not extreme_absolute_F1_all_required <= 0.40:
    verdict = DOES_NOT_KILL_REIGNING
else:
    synthetic_verdict = KILLS_REIGNING

if C4 is INCONCLUSIVE:
    overall = SYNTHETIC_SUPPORT_ONLY_NOT_ADOPTABLE
elif real_delta_pearson < 0.05:
    overall = KILLS_COUNTER_REAL
elif selective_high_confidence_pattern is absent:
    overall = NON_PROGRESSIVE_GLOBAL_GAIN
elif C5 identity fails:
    overall = UNSAFE_FALLBACK
else:
    overall = PROGRESSIVE_BELT_CANDIDATE
~~~

합성 지지와 실측 kill이 충돌하면 평균내지 않는다. 실측 kill condition이 belt 채택을 막고, 합성 결과는 “절대 raw gap이 scale-variant”라는 제한된 사실로만 남는다.

---

# 7. Red team 티켓 응답

패널 보고서가 P2/CL-B에 직접 또는 공통 선결로 연결한 티켓만 다룬다. 번호의 세부 원문이 패킷에 없는 부분은 새 내용을 발명하지 않는다.

## T1 — truth proxy 독립성 감사

**응답: 부분 해소, 합산 금지.**

- synthetic pair truth는 기하 생성기에서 온다.
- DIM-geometry는 unit estimator만 검증한다.
- real Pearson은 frozen LLM likelihood와 pair count의 관계일 뿐 벽 truth가 아니다.
- CubiCasa는 no-anchor fallback 회귀에만 쓴다.
- 이 세 결과를 하나의 평균 점수로 합치지 않는다.
- same-def disagreement row를 evidence.xlsx에 내보내 CL-E의 3원 불일치 감사가 소비할 수 있게 한다.

잔여 위험: synthetic generator와 parallel detector가 같은 평행쌍 prior를 공유한다. 그래서 C0 fidelity와 real selective prediction을 모두 요구하지만, 사람 pair label 없이 완전 해소되지는 않는다.

## T2 — 벽 합성 생성기 부재

**응답: 하드 선결 수용.**

현재 synthetic_truth.py의 dimension-only 상태로 P2 PASS를 내지 않는다. C0에서 실제 source-handle wall pair generator와 fidelity gate를 요구한다. 실패 시 BLOCKED_PR1_T2다.

## T7 — zero-wall/전벽 sentinel과 recall floor

**응답: 해소 설계.**

C3에 zero-wall distractor FP rate, all-wall recall, 강체변환 Jaccard를 넣었다. violation-rate 하나만으로 “0벽 탐지기”가 통과하지 못한다. empty-positive F1을 1로 정의하는 구현을 금지한다.

## T9/T21 — v0 baseline 선계측·동결

**응답: 해소 설계.**

P2 packet의 A30(30–500 raw)과 digest 현행 A50(50–400mm)을 별도 arm으로 기록한다. fast_score 설정, candidate IDs, 입력 단위 가정을 P2 코드 적용 전에 봉인한다. 어느 하나를 사후에 “진짜 baseline”으로 바꾸지 않는다.

## T16 — 상대 대 절대 A/B를 Taguchi보다 선행

**응답: 직접 해소.**

C2가 같은 후보 우주에서 gap predicate 하나만 바꾸는 선행 판별이다. 이 셀이 끝나기 전 doe P2의 절대 band robust optimization이나 다중 knob Taguchi를 실행하지 않는다. 그렇지 않으면 “절대 band가 나쁜가, 튜닝이 나쁜가”가 다시 confound된다.

## T17 — 동일-def 다중 proxy 불일치

**응답: 부분 해소, 소유권은 CL-E에 유지.**

real 30에서 DIM consistency, detector pair count, frozen LLM likelihood를 같은 def key로 export한다. 그러나 DIM consistency를 벽 truth로 승격하지 않으며, P2 한 셀로 proxy 독립성 프로그램 전체가 닫혔다고 주장하지 않는다.

## R12로 명시된 quadratic 후보 폭발 위험

**응답: 자원 gate로 해소 시도.**

orientation/interval index, union envelope, segment·def cap, silent truncation 금지, RESOURCE_ABORT=production FAIL을 사전등록했다. 상한을 자주 맞으면 P2의 정확도와 무관하게 구현은 채택 불가다.

## T34 — load-bearing 인용 재-status

**응답: 신규 경험적 인용에 의존하지 않음.**

이 dossier의 논문·시스템명은 차원해석, robust estimation, equivariance의 일반 계보만 설명하며 외부 성능 수치를 가져오지 않는다. 패널의 R-lane 6개를 실행된 실험으로 재분류하지 않는다. 실제 구현 전에 Autodesk/buildingSMART 필드 의미와 서지 표기를 공식 원문으로 확인해야 하지만, 그 확인이 C2의 수학적 판정식을 바꾸지는 않는다.

## 수용하는 잔여 위험

- stale DIM이 체계적으로 같은 잘못된 scale에 합의할 수 있다.
- DIM이 많은 def 선택은 전체 384 def의 대표 표본이 아니다.
- frozen LLM likelihood는 사람 truth가 아니다.
- top 30에서 HIGH가 충분히 나오지 않을 수 있다.
- curtain wall/이중 외피의 다봉 thickness는 단일 relative band를 깨뜨릴 수 있다.
- INSERT world transform 결함이 남아 있으면 P2와 P6 효과가 confound된다.

이 위험은 “향후 보완” 문구로 PASS를 보존하지 않는다. 해당 kill/INCONCLUSIVE 상태를 그대로 낸다.

---

# 8. 인접 제안과의 관계 및 죽어야 하는 조건

## 8.1 병합 가능한 지점

### CL-B coverage-complete deterministic v1

P2는 CL-B의 thickness auxiliary 모듈로 병합할 수 있다. LWPOLYLINE/MLINE/ARC 정규화, INSERT world transform, junction post-filter와 같은 pipeline을 공유하되 각 변화의 ablation을 유지한다.

### feyerabend P6 — INSERT world-coordinate 전개

P6는 P2의 선결에 가깝다. DIM definition points와 candidate segments가 같은 world frame에 있어야 한다. folded/unfolded 결과가 다르면 unit scale 문제로 오인할 수 있다. 따라서 transform audit를 통과한 geometry snapshot에서 A/R을 비교한다.

### doe P2 — Taguchi knob robustness

P2 C2가 먼저 절대 대 상대 표현을 고른 뒤, 살아남은 표현의 \(\alpha_L,\alpha_U\), angle, overlap에 Taguchi를 적용할 수 있다. 절대 band와 상대 band를 같은 factor level로 섞어 최적 평균만 보고하는 것은 금지한다.

### CL-C — wall synthetic truth와 WSD-EVAL-v1

source-handle pair truth를 wall_member(h)로 투영해 공용 계약과 연결한다. 다만 mechanistic primary는 pair F1로 남긴다. PR-1 fidelity를 통과하지 못하면 P2의 합성 증거도 자격이 없다.

### CL-D — metamorphic battery

scale/unit 변환은 P2의 핵심이고 rotation/translation/reflection은 공통 통제다. C3 artifact를 CL-D 형식으로 export할 수 있다. 0벽/전벽 sentinel도 공유한다.

### CL-E — truth-source 교차요인

P2의 real 30 same-def rows를 CL-E가 받아 synthetic/DIM/silver disagreement 구조를 볼 수 있다. 그러나 P2 verdict와 CL-E verdict를 평균내지 않는다.

### CL-F — 고전 ML 사다리

relative-gap과 anchor confidence는 GBDT의 추가 feature 후보다. 기존 GBDT val F1 0.517을 넘는지 여부는 anchor-bearing human-labelled val에서 별도 ablation해야 한다. P2 synthetic 성공만으로 학습 성능 상승을 선언하지 않는다.

### CL-G — raster/VLM

직접 병합하지 않는다. OCR dimension bridge가 별도 exact projection gate를 통과할 때만 raster track에 연결한다. 현재 FloorPlanCAD는 vector SVG가 없으므로 P2의 직접 truth source가 아니다.

### CL-I — 관례 prior 계측

firm별 unit/style 관례를 계측할 때 anchor failure mode를 공유할 수 있다. 그러나 firm 이름이나 layer lexicon을 unit estimator 입력으로 쓰면 P2의 geometry/dimension-only 약속이 깨진다.

## 8.2 차별점

P2는 “더 좋은 절대 band” 제안이 아니다. 핵심 차이는 다음 세 가지다.

1. 좌표 scale group 아래 invariant인 무차원 표현을 쓴다.
2. 적용 가능성을 anchor confidence로 사전 분할한다.
3. 높은 confidence subset에서만 단방향 개선한다는 상호작용을 예측한다.

따라서 전역 F1 grid search, 특정 dataset의 px p50 사용, 단위 메타데이터 lookup 하나, LLM이 좋아하는 pair count로 튜닝하는 방식은 P2가 아니다.

## 8.3 이 제안이 죽어야 하는 조건

다음 중 하나면 P2를 채택하지 않는다.

1. 실제 wall generator/fidelity gate가 준비되지 않아 synthetic truth 자격이 없음.
2. 어느 한 scale에서 relative pair F1이 0.85 미만.
3. extreme scale에서 absolute pair F1이 0.40 이하로 붕괴하지 않아 reigning 관측을 죽이지 못함.
4. anchor HIGH가 true unit scale을 자주 틀림.
5. label permutation이 anchor 또는 prediction을 바꿈.
6. zero-wall/all-wall sentinel 또는 강체변환 통제가 실패함.
7. 실측 HIGH subset Pearson 개선이 +0.05 미만.
8. 전역 평균은 올라도 HIGH에서만 오르는 선택적 패턴이 없음.
9. LOW/NONE safe fallback이 frozen baseline과 다름.
10. real 30에서 candidate cap을 맞아 결과가 truncation에 의존함.
11. mixed-unit/detail inset을 LOW로 감지하지 못하고 잘못된 단일 scale을 확신함.
12. 개선이 INSERT transform 수정에서만 오고 gap 표현 교체 ablation에서는 사라짐.

조건 2 또는 7은 counter theory를 직접 kill한다. 조건 3은 reigning을 kill하지 못한 것이다. 조건 1, 5, 6, 10은 판별 자체가 무효다. 조건 4, 8, 9, 11, 12는 실행체가 counter theory를 대표하지 못하거나 progressive prediction을 충족하지 못한 것이다.

## 8.4 성공하더라도 허용되는 결론의 최대 범위

C0–C5를 모두 통과해도 허용되는 결론은 다음뿐이다.

> DIM/격자 정박 신뢰가 높은 vector CAD def에서, 평행쌍 gap을 절대 raw 좌표 대역으로 관측하는 것보다 도면 내부 reference span에 대한 무차원 대역으로 관측하는 편이 unit-scale 변환에 강건하며, frozen 실측 proxy와의 정렬도 사전등록 방향으로 개선되었다.

다음 문장은 허용되지 않는다.

- “벽 의미가 해결되었다.”
- “CubiCasa test를 이겼다.”
- “LLM과 상관이 올랐으므로 사람 정답이다.”
- “모든 zero-pair가 단위 문제였다.”
- “DIM 없는 도면에도 일반화한다.”

P2의 가장 가치 있는 결과는 성공 자체가 아니라 실패를 둘로 분해하는 것이다. 상대 대역이 합성에서만 살아남고 실측에서 죽으면 scale invariance는 맞아도 wall semantics에는 무력한 것이다. 상대 대역이 anchor confidence와 함께 실측에서만 선택적으로 살아남으면 “zero-pair 다수는 전부 표현 실패”라는 단일 해석을 깨고, 그중 일부를 단위 불일치라는 계측 가능한 하위 원인으로 분리할 수 있다.

DOSSIER_COMPLETE: feyerabend_P2
