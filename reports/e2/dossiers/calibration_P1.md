# P1 방법론 심층 도시에는 다음을 포함한다: 다중 증거 결정론적 constraint lattice

> 좌석: `calibration_P1`  
> 제안: P1 다중 증거 결정론적 constraint lattice  
> 주장 상태: `open`  
> forecast: `null` (`empty_reference_class`)  
> 점수형: `brier`

## 판정 요약과 증거 규율

P1의 핵심은 “평행한 두 선”을 벽의 정의로 삼는 대신, 서로 다른 실패 양상을 가진 증거 채널을 독립적으로 계산하고, 그 증거가 만든 벽 가설들의 충돌을 작은 공간 성분별 최적화로 푸는 것이다. 선택기는 벽 instance 집합을 만들고, 별도 calibration 단계는 각 원본 handle의 `p_wall(h)`를 만든다. 모든 산출에는 원 규칙 evidence, source handle, block transform lineage, 선택·탈락 사유를 함께 보존한다. layer나 source group은 약한 prior일 뿐, 후보 생성이나 판정의 hard oracle이 아니다.

이 문서에서 수치는 세 부류로 구분한다.

- **패킷 실측값**은 제공된 2026-07-18 다이제스트의 값만 재인용한다.
- **프리레지스트레이션 밴드**는 패킷이 지정한 판정 기준이다.
- **신규 설계값·예산값**은 아직 측정되지 않은 실행 계획이다. 실측 결과처럼 서술하지 않는다.

현재 알려진 바는 이 제안의 성공을 뒷받침하기보다 필요성을 설명한다. 기하 탐지기 v1은 CubiCasa5k val에서 `F1=0.2358`, `P=0.134`, `R=0.981`이고, 6특징 HistGradientBoosting은 `P=0.860`, `R=0.370`, `F1=0.517`, `AUC=0.9215`였다. 즉 기존 기하 후보기는 recall은 높지만 의미적 교란에 취약하고, 고전 ML은 precision을 크게 올렸지만 recall을 잃었다. P1은 topology·opening·hatch·lineage 증거와 전역 충돌 해소로 두 결과 사이의 빈 공간을 노린다. 그러나 이것은 아직 가설이다. 특히 벽 합성 생성기가 현재 없고, 합성팩 충실도가 `KS=0.5792`, `TV=0.265`로 실패했으며, scale 불변성도 `0.7624`로 실패했다. 이 세 선결 문제를 통과하지 못하면 최종 test를 열지 않는다.

또한 P1의 원 claim은 그대로 보존한다. **동결된 WSD-EVAL-v1에서 모든 prereg band를 동시에 통과할 때만 참**이다. 일부 지표의 개선, 평균 점수의 개선, 또는 보기 좋은 사례는 claim을 resolve하지 않는다.

---

## 1. 이론적 근거·선행연구

### 1.1 계산기하 계보: primitive 정규화에서 planar arrangement까지

CAD 벽 탐지는 먼저 “무엇을 하나의 기하 객체로 볼 것인가”를 정해야 한다. LINE만 직접 비교하면 LWPOLYLINE의 segment, ARC의 곡률, INSERT 내부 entity, 중첩 block transform이 관측 우주에서 사라진다. 따라서 P1은 원본 entity를 파괴적으로 평탄화하지 않고, 다음 두 표현을 동시에 유지한다.

1. **원본 표현**: handle, entity type, layer, block definition, INSERT 경로와 transform 행렬을 보존한다.
2. **월드 기하 표현**: 모든 primitive를 공통 좌표계에서 비교할 수 있게 펼친다. LWPOLYLINE은 직선·bulge arc primitive로 분해하고, ARC는 곡선 구간으로 유지하며, INSERT는 재귀 transform lineage를 붙여 world coordinate로 전개한다.

이후 공간 색인과 sweep-line 계열 알고리즘으로 근접·교차·평행·offset 관계를 만들고, 후보 중심선만 제한적으로 planar arrangement에 투영한다. 전체 도면의 모든 segment를 무차별 arrangement로 만들지 않는 이유는 실제 도면정의 하나가 최대 `412,775` 선분이라는 패킷 실측 때문이다. 교차 수가 많은 일반 arrangement는 출력 민감형으로 커질 수 있다. Bentley–Ottmann sweep line, DCEL(doubly connected edge list), R-tree/STRtree, robust orientation predicate가 이 단계의 방법론적 기반이다.

구체 선행은 Bentley와 Ottmann의 선분 교차 열거, de Berg 등의 *Computational Geometry*, Shewchuk의 adaptive exact predicates이다. GEOS/JTS의 noding·polygonization도 구현 참고 시스템이다. 단, GEOS/JTS가 이 데이터와 tolerance 정책에서 자동으로 정답을 준다는 뜻은 아니다. 특히 CAD의 near-coincident line, overshoot, 작은 gap은 exact topology와 drafting tolerance 사이에 정책층을 요구한다.

### 1.2 다중 증거: 독립 계산과 조건부 결합

P1의 “constraint lattice”는 널리 고정된 단일 표준 알고리즘명이 아니라 이 제안의 조립 구조다. 이 명칭 아래에서 실제 계산은 세 층으로 분리한다.

- **evidence extractor**는 offset mate, collinear continuity, junction, closed face, opening gap, hatch/poché, block repetition·lineage를 각각 계산한다.
- **hypothesis builder**는 evidence 원자를 벽 instance 후보로 조합한다.
- **resolver**는 공유 handle, 중복 중심선, 양립 불가능한 face 소유권 같은 충돌을 제약으로 풀어 일관된 부분집합을 선택한다.

증거 채널을 따로 계산한다고 통계적 독립성이 자동 확보되는 것은 아니다. offset mate와 hatch boundary가 같은 평행선 prior에서 파생될 수 있고, block 반복과 layer prior가 같은 설계 관례를 재표현할 수 있다. 따라서 “다중 증거”는 단순 표 합산이 아니라, 각 채널의 provenance와 상관을 보존한 log-linear score 또는 factor graph식 결합으로 구현한다. Dempster–Shafer식 독립 증거 결합은 독립성 가정이 충족되지 않으면 과신을 만들 수 있으므로 기본 결합기로 쓰지 않는다.

### 1.3 data association과 조합최적화

offset mate 두 개를 일대일로 짝짓는 제한된 문제는 최대가중 이분 matching으로 표현할 수 있다. Hungarian/Kuhn–Munkres 계열이 이 경우의 기준선이다. 그러나 하나의 polyline 조각이 여러 continuity chain에 들어가거나, hatch face와 opening gap이 둘 이상의 벽 가설을 연결하면 단순 matching이 표현력을 잃는다. 일반 P1은 maximum-weight set packing에 가까운 0–1 ILP로 쓴다.

중요한 설계 원칙은 큰 도면 전체를 하나의 ILP로 보내지 않는 것이다. 공간 색인으로 후보를 만든 뒤 conflict graph의 connected component를 구한다. 작은 component는 exact ILP로, 큰 component는 deterministic matching 또는 제한된 branch-and-bound로 푼다. 큰 component가 계속 생기는 현상 자체가 topology 붕괴 또는 후보 폭증의 진단 신호다.

### 1.4 calibration 계보와 Brier 분해

규칙 점수는 확률이 아니다. `0.8`이라는 규칙 합계가 실제 벽 빈도 `0.8`을 뜻하도록 하려면, 선택기와 분리된 held-out truth에서 calibration해야 한다. P1은 Platt scaling, isotonic regression, beta calibration을 후보로 두되, 표본이 충분하지 않은 세부 strata를 위해 복잡한 calibrator를 늘리지 않는다. 관련 계보는 Platt의 확률 출력, Zadrozny–Elkan의 score calibration, Niculescu-Mizil–Caruana의 확률 예측 비교, Guo 등의 calibration 분석, Kull 등의 beta calibration이다.

평가는 Brier score만 한 숫자로 보지 않고 Murphy 분해를 사용한다.

\[
BS = REL - RES + UNC
\]

여기서 `REL`은 예측확률 bin과 관측빈도의 불일치, `RES`는 base rate에서 유의미하게 떨어져 나간 정도, `UNC`는 outcome 자체의 불확실성이다. 패킷의 합격선 `REL≤0.03`, `RES≥0.02`는 “확률이 맞는가”와 “모두 같은 확률을 내는 무정보 모델이 아닌가”를 동시에 요구한다. bin 선택에 따른 흔들림을 막기 위해 resolver에는 고정 bin과 보조 adaptive-bin 결과를 모두 기록하되, 합격 판정은 프리레지스트레이션한 고정 방식 하나만 사용한다.

### 1.5 metamorphic testing과 leakage 방지

metamorphic testing은 정답 라벨을 새로 만들기 어려울 때, 의미를 보존하는 입력 변환 전후 출력 관계를 검사하는 방법이다. P1의 강체변환·반사·단위변환·scale·explode·layer rename은 벽 의미를 바꾸지 않아야 한다. 단, handle 자체는 변환 과정에서 바뀔 수 있으므로 단순 handle 문자열 동일성이 아니라 manifest의 lineage mapping으로 비교한다.

group leakage 방지는 일반 random row split보다 강해야 한다. 같은 wall grammar, 같은 opening style, 같은 unit family, 같은 block definition의 변형이 train과 held-out에 나뉘면 모델이 형식을 외운다. P1은 `unit_family × grammar_family × opening_style_family × source_project`를 group key로 삼고, 그 group을 통째로 분리한다. resolver는 candidate generator의 geometry 함수나 threshold를 import하지 않고, 동결된 prediction/evidence 파일과 truth manifest만 읽는다. 이 분리는 코드 수준 leakage와 평가 수준 leakage를 함께 겨냥한다.

### 1.6 floor-plan 선행 시스템과 P1의 위치

CubiCasa5K, FloorNet, Raster-to-Vector 계열, room/edge graph를 직접 예측하는 후속 floor-plan reconstruction 시스템은 벽·room·opening을 독립 pixel이 아니라 구조화된 객체로 다루는 계보를 보여준다. 이 문서에서 이들은 **방법론 참고**이지 본 세션의 새 실측 근거가 아니다. 정확한 서지 제목·판본이 확실하지 않은 FloorPlanCAD 계열 논문과 일부 room-graph 후속 시스템은 구현 착수 전 `요검증` 대상으로 둔다.

P1의 차별점은 대규모 learned representation을 먼저 쓰지 않고, CAD-native provenance와 구조 제약을 해석 가능한 evidence로 보존한다는 데 있다. CubiCasa5k의 GBDT 성적은 고전 ML의 강한 기준선이다. P1이 그 기준선을 이기지 못하거나, P1 evidence를 GBDT feature로 넣었을 때 같은 결과를 더 싸게 얻는다면 lattice의 독립 가치는 약해진다.

### 1.7 서지 메모

아래는 일반 지식에 기반한 구현 전 확인 목록이며, 이 문서에서 성능 수치를 인용하지 않는다.

- Bentley, J. L. & Ottmann, T. A., 선분 교차의 sweep-line 알고리즘.
- de Berg et al., *Computational Geometry: Algorithms and Applications*.
- Shewchuk, J. R., *Adaptive Precision Floating-Point Arithmetic and Fast Robust Predicates for Computational Geometry*.
- Kuhn의 Hungarian method 및 Munkres의 assignment algorithm 정식화.
- Platt, J., *Probabilistic Outputs for Support Vector Machines and Comparisons to Regularized Likelihood Methods*.
- Zadrozny, B. & Elkan, C., classifier score를 확률로 변환하는 연구.
- Niculescu-Mizil, A. & Caruana, R., supervised learning의 확률 예측 비교.
- Guo et al., *On Calibration of Modern Neural Networks*.
- Kull et al., beta calibration.
- Kalervo et al., CubiCasa5K 데이터셋 논문.
- Chen 등 metamorphic testing 계보: 최초 논문·연도는 구현 문서 인용 전 `요검증`.

---

## 2. 알고리즘 정확 스펙

### 2.1 입력, 출력, 평가 단위

입력 도면 `D`는 다음 스키마를 가진다.

```text
EntityRecord {
  drawing_id, source_handle, entity_type,
  layer_id, source_group_id,
  local_geometry,
  block_definition_id?, insert_path[],
  world_transform_3x3, style_attributes,
  unit_metadata?, provenance
}
```

기본 평가 단위는 **원본 source handle**이다. 분해된 polyline segment나 INSERT instance primitive는 내부 계산 단위일 뿐, truth와 `p_wall(h)`는 manifest가 지정한 원본 handle/instance lineage에 다시 모은다. 하나의 block definition handle이 여러 INSERT에서 서로 다른 문맥을 가질 수 있으므로 출력 key는 필요하면 `(source_handle, insert_path)`이다. 이를 숨기고 handle 하나로 합치지 않는다.

출력은 네 묶음이다.

1. `WallHypothesis`: 중심선 또는 wall band, 지지 primitive, opening, face, lineage, raw evidence.
2. `SelectedWallInstance`: 선택 여부, component id, objective contribution, 충돌·탈락 사유.
3. `HandlePrediction`: `p_wall(h)`, raw rule score, abstain reason, selected instance ids.
4. `RunEvidence`: manifest hash, implementation hash, threshold set, telemetry, calibration artifact hash, resolver verdict.

### 2.2 좌표·primitive 정규화

정규화 함수 `N(D)`는 다음 불변조건을 지켜야 한다.

- LINE은 방향과 무관한 canonical endpoint ordering을 갖는다.
- LWPOLYLINE은 segment로 분해하되 closed flag, bulge, parent handle, segment index를 잃지 않는다.
- ARC는 중심·반지름·시작/끝각의 canonical 표현을 유지한다. 공간 색인용 chord approximation은 별도 필드이며, 최종 거리·교차 판정은 analytic arc 또는 명시한 오차 한계로 수행한다.
- INSERT는 중첩 transform을 행렬곱으로 전개한다. determinant 부호로 reflection을 기록하고, non-uniform scale·shear는 별도 위험 flag로 둔다.
- HATCH는 boundary loop와 style을 분리한다. hatch 존재 자체를 벽 truth로 쓰지 않는다.
- 중복 기하는 지우지 않고 `coincident_group_id`로 묶는다. 중복 삭제가 truth handle을 사라지게 해서는 안 된다.
- unit은 명시 metadata가 있으면 검증 후 사용하고, 없으면 여러 anchor 후보와 confidence를 낸다. confidence가 낮을 때 절대 mm threshold를 사실처럼 적용하지 않는다.

단위 anchor `a_D`는 dimension annotation, 명시 scale, 반복 opening 폭 등 **서로 provenance가 다른 후보**에서 추정한다. 한 종류만 존재할 때는 `unit_ambiguous=true`로 남긴다. CubiCasa SEG-IR처럼 px 좌표이고 도면별 물리축척이 모르는 축에서는 `a_D`를 물리 mm로 변환하지 않고, 도면 내부 robust scale에 대한 무차원 비율만 사용한다.

### 2.3 evidence 채널

각 채널 `c`는 `E_c(hypothesis) = {value, validity, support_ids, diagnostics}`를 반환한다. missing evidence를 0점 evidence와 구분한다.

#### A. `offset_mate`

두 curve의 접선 방향 일치, 법선 거리, 투영 overlap, 곡률 양립성을 계산한다. 직선–직선뿐 아니라 arc–arc의 동심 offset, polyline chain 간 piecewise offset을 허용한다. v1의 `2°`, overlap `0.5`, 두께 `50–400mm`는 재현 기준선으로 보존하되 P1의 유일한 값으로 고정하지 않는다.

#### B. `collinear_continuity`

gap과 overshoot를 포함해 동일 지지선/곡률 위 primitive를 chain으로 묶는다. 작은 gap을 무조건 봉합하지 않고, opening 후보가 gap을 설명하는지와 junction이 gap 양끝을 지지하는지를 함께 기록한다.

#### C. `junction`

T/X/L junction, wall endpoint, crossing을 분류한다. 단순 교차는 wall junction이 아닐 수 있으므로 접속 각도, 연결된 mate, face incidence를 본다. overshoot trimming은 원본 기하를 수정하지 않고 가상 noded geometry로만 수행한다.

#### D. `closed_face`

후보 중심선 또는 wall boundary 주변의 국소 arrangement에서 bounded face를 찾는다. face는 room-first truth가 아니라 P1의 보조 evidence다. CL-J의 face-first 제안과 혼동하지 않는다.

#### E. `opening_gap`

continuity chain의 gap이 door/window block, 반복 opening 폭, 양쪽 jamb junction으로 설명되는지 계산한다. opening을 발견하지 못했다는 이유만으로 벽을 제거하지 않는다.

#### F. `hatch_poche`

wall band 내부 또는 boundary 주변의 hatch/poché 일치도를 계산한다. hatch convention이 프로젝트마다 다르므로 source-project group 밖으로 일반화되는지 별도 평가하며, hard positive로 쓰지 않는다.

#### G. `block_repeat_lineage`

같은 block definition이 여러 transform으로 반복될 때, local geometry 대응과 world context를 모두 보존한다. 동일 block 내부 primitive라는 이유만으로 같은 label을 강제하지 않고, lineage-consistency bonus와 transform 오류 진단을 분리한다.

#### H. `single_line_support`

offset mate가 없는 single-line wall을 위한 탈출구다. room-face incidence, junction 연속성, opening, 반복 lineage가 충분할 때 후보를 만들되 낮은 prior에서 시작한다. 이 채널이 없으면 P1도 “평행쌍 detector”의 recall ceiling을 벗어나지 못한다.

#### I. `source_prior`

layer, source group, style은 마지막 약한 prior로만 들어간다. name-blind arm에서는 완전히 mask한다. 패킷 실측에서 기존 탐지기의 full-vs-name-blind가 `1.0`으로 같았다는 사실은 기존 탐지기가 layer 이름 신호를 쓰지 않았음을 뜻할 뿐, P1의 새 prior가 안전하다는 뜻은 아니다.

### 2.4 후보 생성과 폭증 방지

primitive 수를 `n`, spatial query로 생긴 근접 edge 수를 `m`, 실제 arrangement 교차 수를 `k`라 한다. 목표는 전체 pair `O(n²)` 열거를 금지하고 `m`과 `k`에 비례해 streaming하는 것이다.

1. 도면을 adaptive spatial tile로 나눈다.
2. 각 primitive의 expanded bounding box를 STRtree/R-tree에 넣는다.
3. orientation bucket과 curvature bucket으로 명백히 양립 불가능한 pair를 제거한다.
4. 같은 tile과 인접 tile에서만 offset·junction query를 수행한다.
5. entity별 최대 후보 수를 초과하면 점수로 조용히 prune하지 않고 `candidate_overflow`를 기록하여 해당 component를 실패 처리한다.
6. 후보 중심선의 국소 buffer 안에서만 noding·face 추출을 한다.

성장 검사는 여러 `n` 구간에서 `log(m)=α log(n)+b`를 적합하고, `m/n`, component 크기, wall time, peak RAM도 함께 기록한다. 패킷의 kill condition인 “entity 수에 대해 실측상 quadratic 폭증”은 단지 느렸다는 인상으로 판정하지 않고, 사전 봉인한 도면 순서와 계측 스크립트로 판정한다. `candidate_overflow`나 48GB 이전 hard stop은 실패를 감추는 pruning이 아니라 명시적 abort다.

### 2.5 벽 가설과 raw score

가설 `q`는 다음을 가진다.

\[
q=(G_q, C_q, F_q, O_q, L_q, x_q)
\]

- `G_q`: 지지 source handle/instance 집합
- `C_q`: 중심선 또는 center arc
- `F_q`: 관련 face 집합
- `O_q`: opening 설명 집합
- `L_q`: block transform lineage
- `x_q`: 채널별 raw evidence vector

규칙 score는 누락과 음성을 구분하는 masked log-linear 형태로 둔다.

\[
s_q = b + \sum_c M_{qc} w_c f_c(x_{qc})
      + \sum_{(c,d)\in I} M_{qc}M_{qd}w_{cd}f_c(x_{qc})f_d(x_{qd})
      - \lambda_r R_q
\]

`M_qc`는 채널 validity, `R_q`는 transform 이상·단위 모호·과도한 gap·장식 반복 같은 risk penalty다. interaction `I`는 프리레지스트레이션한 소수만 허용한다. evidence channel을 많이 추가한 뒤 val 성적에 따라 임의 조합을 고르는 것은 leakage로 간주한다.

초기 weight는 기하 의미에 따른 고정값으로 시작하고, 튜닝이 필요하면 train 내부 group split에서만 제한된 설계 실험으로 고른다. test나 hidden synthetic family에서 weight를 바꾸지 않는다.

### 2.6 conflict graph와 선택 최적화

두 가설 `q,r`가 다음 중 하나면 conflict edge를 만든다.

- 동일 source primitive를 양립 불가능한 두 wall instance가 독점한다.
- 중심선이 tolerance 내 중복인데 서로 다른 벽으로 제안됐다.
- 동일 opening이 양립 불가능한 wall pair에 소유된다.
- local face incidence가 기하적으로 동시에 성립할 수 없다.
- transform lineage가 같은 instance를 중복 세었다.

각 connected component `K`에서 0–1 변수 `z_q`를 풀어 선택한다.

\[
\max_z \sum_{q\in K} u_q z_q + \sum_{(q,r)\in A_K}\psi_{qr}y_{qr}
\]

subject to

\[
z_q+z_r\le1 \quad \forall(q,r)\in Conflict_K
\]

\[
y_{qr}\le z_q,\quad y_{qr}\le z_r,\quad
y_{qr}\ge z_q+z_r-1
\]

`u_q`는 raw score와 coverage bonus·risk penalty의 합, `A_K`는 양립 가능한 continuity/opening 관계다. 단순 pair-only component는 maximum-weight matching으로 풀고, 일반 component는 ILP로 푼다. 동점은 `(drawing_id, min source_handle, hypothesis_type)` canonical order로 깨서 실행 순서에 따른 비결정성을 없앤다.

ILP time limit에 걸렸을 때 incumbent를 몰래 정답으로 쓰지 않는다. `solver_timeout`과 optimality gap을 기록하고, 최종 밴드 평가에서 해당 도면을 성공으로 포함하지 않는다. 큰 component fallback도 별도 arm으로 평가한 뒤에만 사용할 수 있다.

### 2.7 handle score와 probability calibration

선택 전후의 가설 score를 원본 handle로 모은다.

\[
r_h = \max_{q:h\in G_q}\left(s_q + \delta\,z_q + \mu\,margin_q\right)
\]

후보가 전혀 없는 handle은 삭제하지 않고 `r_h=-∞`, `candidate_missing=1`로 남긴다. 이 sentinel까지 포함해 candidate recall을 계산한다. 여러 가설 확률을 독립으로 가정하여 곱하지 않는다.

calibrator `g`는 family-grouped held-out calibration fold에서 학습한다.

\[
p_{wall}(h)=g(r_h, candidate\_missing, unit\_ambiguous)
\]

기본 후보는 단조 isotonic과 1차원 Platt scaling이다. beta calibration은 calibration sample과 class support가 충분하다는 사전 조건을 만족할 때만 비교한다. 선택은 calibration fold의 Brier score와 REL을 기준으로 하고, 선택된 방식과 knot/parameter를 hash하여 동결한다. 다차원 GBDT를 calibrator로 쓰지 않는다. 그렇게 하면 “결정론 규칙의 별도 calibration”이 아니라 새 learned classifier가 되기 때문이다.

`precision_F≥0.90 at coverage≥0.50`의 모호성을 제거하기 위해 P1 resolver에서 `coverage`는 **F truth의 positive handle 중 threshold 이상으로 회수된 비율**, 즉 해당 operating point의 wall recall로 정의한다. calibration fold에서 precision이 목표를 만족하는 threshold를 하나 선택해 동결하고, val/test에서 threshold를 다시 움직이지 않는다. 이 정의가 공용 WSD-EVAL-v1 계약과 다르면 manifest를 봉인하기 전에 새 버전으로 합의해야 하며, 실행 후 해석으로 바꾸면 안 된다.

### 2.8 resolver 격리와 최종 판정

resolver 입력은 다음 파일뿐이다.

```text
frozen_manifest.json
truth_handles.parquet
predicted_handles.parquet
selected_instances.jsonl
metamorphic_lineage.parquet
telemetry.jsonl
calibrator.json
```

resolver 저장소/패키지는 candidate generator의 threshold 상수, geometry 함수, feature extractor를 import하지 않는다. geometry 재계산도 하지 않는다. exact handle equality와 manifest lineage만 사용한다. 출력 `wsd_eval_p1.json`에는 모든 밴드의 numerator, denominator, exclusions, hash, verdict를 기록한다.

```text
P1_all_bands_pass =
    (F1_S >= 0.95)
and (AUPRC_F - AUPRC_v0 >= 0.15)
and (precision_F_at_frozen_threshold >= 0.90)
and (coverage_F_at_frozen_threshold >= 0.50)
and (metamorphic_handle_flip_rate <= 0.01)
and (REL <= 0.03)
and (RES >= 0.02)
and (local_p95_seconds_per_drawing <= 60)
and (peak_RAM_GB <= 32)
and all_hashes_frozen
and no_forbidden_leakage
and no_required_cell_missing
```

한 항이라도 false, missing, invalid이면 전체 verdict는 false다. 실무 도면은 M relation 결과만 truth로 인정하고, silver나 보기 좋은 rendering은 wall label truth로 승격하지 않는다.

### 2.9 하이퍼파라미터 공간

아래 값은 **신규 설계 공간**이며 실측 성능이 아니다. 대규모 sweep를 피하기 위해 먼저 소수의 space-filling/Taguchi형 조합을 train 내부에서 비교하고, 한 번 선택한 값은 val 확인 전에 동결한다.

| 계층 | 파라미터 | 설계 공간 | 규율 |
|---|---|---:|---|
| 정규화 | angular tolerance | `0.5°, 1°, 2°, 4°` | `2°` v1 재현 arm 포함 |
| 정규화 | projected overlap | `0.3, 0.5, 0.7` | `0.5` v1 재현 arm 포함 |
| 단위 | absolute thickness | v1의 `50–400mm` arm | unit 확정 도면에서만 |
| 단위 | relative thickness | anchor 대비 log-ratio 구간 3수준 | px/단위 불명 축 기본 |
| continuity | gap tolerance | local anchor 대비 3수준 | opening 설명과 결합 |
| continuity | overshoot tolerance | local anchor 대비 3수준 | 원본 기하 불변 |
| 증거 | channel weights | simplex 위 제한 설계 | layer/source 최대 weight 제한 |
| 최적화 | exact ILP component cap | 3개 크기 수준 | cap 초과를 숨기지 않음 |
| calibration | method | Platt/isotonic, 조건부 beta | family-held-out에서만 선택 |
| 출력 | operating threshold | calibration fold에서 1회 선택 | val/test 재선택 금지 |

---

## 3. 벽 과업 적응 설계

### 3.1 S/F/M truth contract를 먼저 고정한다

패킷은 S/F/M 세 pack을 모두 요구하지만, 이름만 보고 세부 스키마를 추정해서는 안 된다. 이 문서의 실행 계약은 truth provenance에 따라 다음처럼 고정한다.

- **S 축**: 독립 wall grammar 생성기가 원본 handle 단위 `wall_member(h)`를 직접 기록하는 synthetic pack. 5개 grammar × 20개 block의 100-case cheapest probe와 hidden mutation family를 포함한다. 기존 `synthetic_truth.py`는 dimension 전용이므로 코드 패턴만 참고하고 truth로 세지 않는다.
- **F 축**: 제3자 human label에서 온 외부 truth 축. 패킷에서 실제 line-class truth가 확인된 것은 CubiCasa5k SEG-IR의 Wall 클래스 요소 모서리다. 기존 train `4,200`, val `400`, test `400` split을 그대로 보존한다.
- **M 축**: 의미 보존 변환 전후의 lineage relation. 실무 145장은 wall label truth로 사용하지 않고 오직 M relation 충족 여부만 truth로 인정한다.

여기에는 중요한 충돌이 있다. 제안 본문은 “FloorPlanCAD 선 라벨”을 truth source로 적었지만, 자산 다이제스트는 FloorPlanCAD가 래스터 5,308장과 wall bbox/segmask를 가지며 벡터 SVG는 없다고 명시한다. 따라서 FloorPlanCAD mask를 exact handle truth라고 부를 수 없다. 이 dossier는 이를 다음 중 하나가 해결될 때까지 provenance blocker로 둔다.

1. 독립적으로 검증된 vector-to-raster 대응과 ambiguity mask를 가진 adapter를 만들고, 그 출력은 `projected_raster_truth`로 별도 표기한다.
2. F의 exact per-handle 주 truth를 CubiCasa SEG-IR로 명시하고 FloorPlanCAD는 raster 보조축으로 남기도록 WSD-EVAL manifest의 새 버전을 봉인한다.

사후에 더 편한 쪽을 고르지 않는다. counsel과 데이터 권리 확인도 F 학습·최종 판정 전에 끝나야 한다.

### 3.2 CubiCasa SEG-IR 벡터축

CubiCasa5k는 5,000도면이 모두 SEG-IR로 변환됐고 실패가 0이며, wall line 비율은 약 `11.8%`다. 좌표는 px이고 도면별 물리 축척이 알려지지 않았으며 벽 두께 px 중앙값은 `22`다. 따라서 P1은 다음처럼 접속한다.

- `cubicasa_ir`가 내는 line/edge와 Wall class lineage를 source handle surrogate key로 고정한다.
- 물리 `50–400mm` band는 이 축의 주 규칙으로 쓰지 않는다. 도면 내부 길이·offset 분포의 무차원 비율을 사용한다.
- BoundaryPolygon, Direction 화살표, Door, Window, DimensionMark는 negative subtype으로 보존한다. 이들은 기존 기하 탐지기의 주요 false positive이므로 단순 “비벽” 합계뿐 아니라 subtype별 precision을 낸다.
- train 내부를 family/group 단위로 rule weight 학습 fold와 calibration fold로 나눈다. val은 설계 확인에만 쓰고, test 400은 모든 hash와 band가 동결된 뒤 방법당 한 번만 연다.
- `cubicasa_ml`의 6특징 HistGradientBoosting을 강한 비교군으로 재현한다. P1 claim의 공식 차이는 v0 AUPRC이지만, GBDT `F1=0.517`보다 구조 evidence가 실제 이득을 주는지도 별도 보고한다.

기존 v1의 val `R=0.981`은 candidate generator가 넓게 잡는 장점이 있음을 시사하지만 `P=0.134`는 평행 구조만으로 의미를 가르기 어렵다는 뜻이다. 반대로 GBDT의 `P=0.860`, `R=0.370`은 비선형 feature 결합이 강하지만 많은 wall을 버렸음을 보여준다. P1의 목표는 candidate stage에서 v1의 recall 성격을 보존하고, arrangement·junction·opening·face·lineage 충돌 해소로 precision을 올리는 것이다. 그 결과가 실제로 나오지 않으면 “다중 evidence”라는 설명은 성공 근거가 아니다.

### 3.3 FloorPlanCAD 래스터축

FloorPlanCAD는 벡터 SVG가 없으므로 P1의 handle-level primary truth가 될 수 없다. 대신 다음 보조 실험을 한다.

1. P1 wall instance를 raster canvas로 렌더한다.
2. 제공 wall bbox/segmask와 정렬한다.
3. antialiasing·선폭으로 생긴 경계 ambiguity band를 평가에서 분리한다.
4. mask overlap과 instance coverage를 보고하되 이를 exact handle F1과 합치지 않는다.
5. raster projection이 uncertain한 도면은 실패 사유와 함께 남기고, 좋은 사례만 선별하지 않는다.

이 축의 용도는 vector evidence가 raster wall 영역과 구조적으로 맞는지 확인하고, CubiCasa라는 한 데이터 관례에 과적합됐는지를 보는 것이다. counsel 확인 전에는 학습 arm을 시작하지 않는다.

### 3.4 1.dwg 실도면축

staged DXF에는 도면정의 384개가 있고, v0 벽-제로 도면율은 `0.682`에서 `0.2135`로 개선되어 패킷 밴드 `≤0.40`을 통과했다. 그러나 벽-제로 감소는 벽 정확도 증명이 아니다. P1은 이 축을 다음 세 용도로 제한한다.

- block definition/INSERT transform 전개의 실전 검증
- top-20 divergence와 대조군에서 후보 recall proxy·evidence 해석·false merge 검토
- 최대 규모 도면에서 runtime, component size, edge growth, RAM telemetry 측정

E1 top-20은 `_score_divergence` 정렬 키 artifact 가능성이 패널에 지적됐다. CL-A가 정렬 artifact를 재계산하기 전에는 top-20을 대표 표본이나 truth로 부르지 않는다. 또한 패킷의 “실무 145장 M truth”와 “1.dwg 384개 정의”가 같은 집합이라고 가정하지 않는다. manifest가 실제 대응을 명시해야 한다.

### 3.5 M metamorphic 축

변환 집합은 강체 회전, 이동, 반사, 단위 표현 변경, uniform scale, block explode/fold, layer rename이다. 각 변환은 source-to-derived lineage map과 expected relation을 낸다.

- 강체·반사: 선택 wall instance와 `p_wall`가 lineage 아래 동일해야 한다.
- scale·unit: 무차원 evidence와 최종 판정이 동일해야 한다. 현재 scale arm `0.7624` 실패를 반드시 재현한 뒤 수정한다.
- explode/fold: block local/world transform 차이에도 instance 결과가 대응해야 한다.
- layer rename: hard oracle가 없음을 검증한다.
- 0-wall sentinel: 모든 변환에서 0벽을 유지해야 한다.
- all-wall/known-wall sentinel: “아무것도 탐지하지 않는 모델”이 낮은 flip rate로 통과하지 못하도록 recall floor를 함께 본다.

flip은 단순 set equality가 아니라 lineage에 대응된 handle의 binary verdict와 확률 변화 둘 다 기록한다. claim의 공식 band는 handle flip rate `≤0.01`, kill은 `>0.02`다. 그 사이 구간은 실패지만 즉시 프로그램 kill은 아닌 상태로 남긴다.

### 3.6 evidence_grid·fast_score 접속

- `evidence_grid`는 실험 cell, 데이터 manifest, metric, band, hash, failure reason을 행 단위로 기록하는 control plane으로 사용한다. 후보 evidence의 상세 대용으로 xlsx 한 칸에 JSON을 밀어 넣지 않는다.
- `fast_score`는 v0의 NumPy 동치 baseline을 고정 재현하는 데 사용한다. P1의 topology score를 몰래 `fast_score`의 새 버전으로 덮어쓰지 않고 baseline과 P1을 병렬 산출한다.
- `cubicasa_ir`는 F축 entity/truth adapter다. split과 source key를 변경하지 않는다.
- `cubicasa_ml`은 GBDT 비교군과 shuffle control을 재현한다. shuffle AUC `0.375` PASS는 기존 결과이며, P1 run에서도 동일한 누출 방지 control을 새 run artifact로 다시 남겨야 한다. 기존 숫자를 새 실행의 증거로 재사용하지 않는다.

---

## 4. 데이터·컴퓨트 요구

### 4.1 필수 데이터 산출물

실행 전 다음 manifest를 먼저 만든다.

| 산출물 | 필수 내용 | 차단 조건 |
|---|---|---|
| `s_manifest` | grammar family, opening style, unit family, exact handle truth, seed | wall generator 부재 또는 lineage 누락 |
| `f_manifest` | dataset license status, project group, split, SEG-IR source id, wall label provenance | counsel 미확인 또는 test 접촉 |
| `m_manifest` | source drawing hash, transform, lineage map, expected relation | lineage ambiguity |
| `implementation_manifest` | generator, candidate, solver, calibrator, resolver hash | 실행 중 변경 |
| `band_manifest` | 지표 정의, threshold, exclusion, kill 조건 | 미정의 denominator |

`S/F/M manifest hash + implementation hash`가 모두 고정된 후에만 독립 resolver가 최종 JSON을 만든다. raw CAD·IR·truth·prediction은 immutable input/output 구역으로 분리하고, 실패한 run도 삭제하지 않는다.

### 4.2 로컬 CPU 실행 계획

P1은 GPU가 필수인 방법이 아니다. 주 실행은 로컬 CPU, RAM 64GB 환경에서 한다.

- drawing 단위 streaming을 기본으로 하고, 한 drawing 안에서도 spatial component별로 처리한다.
- primitive와 candidate edge는 columnar/on-disk batch로 spill할 수 있게 한다.
- ILP는 component별 process isolation을 사용해 timeout·peak RSS를 정확히 기록한다.
- telemetry sampler는 candidate count, edge count, component size, noding intersection, elapsed wall/CPU time, RSS를 기록한다.
- peak RAM이 32GB를 넘으면 최종 prereg band 실패다. 48GB에 닿기 전에 watchdog이 해당 run을 중단한다. 32–48GB 구간은 “성공하지만 다소 큼”이 아니라 실패·진단 구간이다.
- local p95는 `≤60초/도면`이어야 한다. cache warm/cold, parser time 포함 여부를 manifest에서 고정한다. 기본 판정은 end-to-end cold input read부터 prediction flush까지다.

최대 `412,775` 선분 도면은 평균 성능과 따로 stress cell에 넣는다. 이 도면에서 hard stop이 걸리면 작은 도면 평균으로 숨기지 않는다.

### 4.3 GPU와 DGX 계획 분리

RTX 5070 Ti 16GB는 P1 본체에 필요하지 않다. 선택적으로 FloorPlanCAD raster render 또는 비교용 raster model 추론에만 쓰며, 그 결과가 P1 deterministic claim의 필수 evidence가 되지 않게 한다.

DGX Spark는 현재 unreachable이고 P1 compute plan에도 필요 없다. Ornith-35B, vLLM, frontier VLM을 이 실험의 resolver나 truth source로 사용하지 않는다. DGX 연결 복구를 기다려 P1 실행을 지연시키지 않으며, 대규모 threshold sweep도 vLLM 자원을 점유하지 않고 로컬 CPU batch로 수행한다.

### 4.4 저장·증거 요구

패킷의 평가 원칙에 따라 evidence xlsx는 의무다. 최소 sheet는 다음과 같다.

- `RUNS`: run id, hashes, status, failure reason
- `CELLS`: hypothesis, data split, seed, metric, band, verdict
- `METRICS`: numerator, denominator, estimate, interval, exclusion
- `EVIDENCE_CHANNELS`: 채널 availability·ablation·subtype 오류
- `METAMORPHIC`: relation, lineage count, flips, sentinel result
- `PERFORMANCE`: n, candidate edges, component size, time, RAM
- `LEAKAGE_AUDIT`: group overlap, import audit, shuffle control
- `TEST_TOUCH`: test open 시각, hash, 단발 실행자, resolver hash

xlsx는 요약·감사 표면이고 raw JSONL/Parquet가 원증거다. 셀 실패도 reason code와 함께 행을 남긴다.

### 4.5 예상 실행 가능성과 병목

실행 가능성은 높지만 성공 가능성은 아직 수치화하지 않는다. CPU-friendly한 부분은 spatial query, analytic geometry, small-component matching/ILP, 1차원 calibration이다. 주요 병목은 다음이다.

- near-coincident noding이 만든 큰 conflict component
- 중첩 INSERT의 world-coordinate 전개와 중복 instance
- hatch boundary 관례 차이
- px 축과 mm 축 사이의 잘못된 anchor 공유
- aggressive pruning으로 candidate recall이 조용히 떨어지는 현상
- FloorPlanCAD raster mask를 exact handle truth로 오인하는 provenance 오류

개발 예산은 신규 설계 추정으로, core normalization·evidence·solver·resolver에 약 2–3인주, generator·fidelity gate에 별도 1–2인주, 증거·stress·재현성 정리에 약 1인주를 둔다. 이는 성능 실측이 아니라 일정 계획이며, PR-1 generator가 이미 있다고 가정하지 않는다.

---

## 5. 구현 계획

### 5.1 모듈·파일 골격

아래는 예정 골격이다. 이 dossier 작성 단계에서 파일을 만들었다는 뜻이 아니다.

```text
e2_wall_lattice/
  schemas.py                  # Entity/Evidence/Hypothesis/Prediction 스키마
  ingest.py                   # DXF·SEG-IR adapter 공통 경계
  normalize/
    primitives.py             # LINE/LWPOLYLINE/ARC canonicalization
    block_lineage.py          # INSERT 재귀 transform
    units.py                  # absolute/relative anchor와 ambiguity
  spatial/
    index.py                  # STRtree/tile/orientation bucket
    robust_predicates.py      # 교차·거리·곡률 판정
  evidence/
    offset_mate.py
    continuity.py
    junction.py
    faces.py
    openings.py
    hatch_poche.py
    block_repeat.py
    single_line.py
    source_prior.py
  hypotheses.py
  conflicts.py
  solve_matching.py
  solve_ilp.py
  calibrate.py
  predict.py
  telemetry.py
  cli.py

e2_wall_truth/
  wall_grammar.py             # synthetic_truth.py와 별도인 실제 벽 생성기
  mutations.py
  exact_handles.py
  fidelity_gate.py

e2_wall_resolver/             # generator 패키지 import 금지
  schemas.py
  leakage_audit.py
  score_handles.py
  score_metamorphic.py
  brier_decomposition.py
  bands.py
  emit_wsd_eval_p1.py

adapters/
  evidence_grid_adapter.py
  fast_score_v0_adapter.py
  cubicasa_ir_adapter.py
  cubicasa_ml_adapter.py
  floorplancad_raster_adapter.py

tests/
  unit/
  property/
  golden/
  sentinels/
  scaling/
```

resolver는 별도 dependency lock을 사용한다. 정적 import audit에서 `e2_wall_lattice`, `fast_score`, candidate threshold module을 발견하면 final verdict를 invalid로 만든다.

### 5.2 구현 순서와 완료 조건

#### 단계 A — 계약과 generator

1. `wall_member(h)`와 `(handle, insert_path)` identity 규칙을 schema로 고정한다.
2. 5 grammar × 20 block 100-case generator를 구현한다.
3. negative entity, single-line wall, opening, hatch, ARC, polyline, nested INSERT를 생성한다.
4. 실도면 divergence 현상과 entity-type 분포의 fidelity gate를 통과시킨다.

완료 조건은 exact handle truth와 mutation lineage가 재생성 가능하고, 기존 dimension 전용 파일을 truth로 세지 않는 것이다.

#### 단계 B — normalization과 evidence

각 채널을 독립 pure function으로 구현한다. 채널 간 helper 공유는 primitive geometry까지 허용하되, 한 채널의 판정값을 다른 채널의 입력으로 몰래 쓰지 않는다. property test는 회전·반사·scale·explode에서 canonical geometry가 lineage 아래 일치하는지 본다.

#### 단계 C — candidate와 solver

먼저 matching baseline을 만들고, 표현 불가능한 conflict가 있는 component만 ILP로 보낸다. 각 component에는 원인별 edge count와 solve trace를 남긴다. exact/timeout/fallback 상태를 구분한다.

#### 단계 D — calibration과 resolver

train group split에서 calibrator를 고르고 동결한다. resolver는 생성 코드와 분리한 뒤, synthetic exact truth·F external truth·M lineage를 각기 다른 scorer로 읽고 마지막에 band conjunction만 계산한다.

#### 단계 E — 증거와 재현성

모든 실험은 동일 run id 아래 raw evidence, xlsx, hashes, stdout/stderr, telemetry를 연결한다. 실패 run에도 `FAILED_<reason>` 상태를 준다. “파일이 생겼다”를 PASS로 보지 않는다.

### 5.3 기존 도구 접속 세부

#### `fast_score`

고정 v0 adapter는 입력 entity schema만 P1 공통 schema로 변환하고, v0 weights `parallel 0.35 / thickness 0.25 / junction 0.20 / layer 0.20`, angle `2°`, overlap `0.5`, snap `6mm`, thickness `50–400mm`를 baseline manifest에 기록한다. P1의 개선을 위해 이 값을 소급 수정하지 않는다.

#### `cubicasa_ir`

기존 train/val/test row와 Wall label을 그대로 매핑하고, derived segment가 어느 source element에서 왔는지 역참조 가능하게 한다. 변환 실패 0이라는 기존 실측과 별개로, P1 adapter의 row-count·hash 검사를 새로 실행한다.

#### `cubicasa_ml`

기존 6특징 GBDT와 logistic, shuffle control을 비교군으로 보존한다. P1 evidence를 추가한 hybrid GBDT는 인접 proposal arm으로 분리하며 P1 deterministic 결과와 합치지 않는다.

#### `evidence_grid`

cell 상태는 `PLANNED/RUNNING/PASS/FAIL/KILLED/INVALID`로 제한한다. band 미정·truth provenance 미정 상태는 PASS가 아니라 INVALID다. test 단발을 열기 전 모든 prerequisite cell의 hash를 확인한다.

### 5.4 테스트 전략

- **unit**: 거리, offset, arc, transform, reflection determinant, handle aggregation.
- **property**: rotation/translation/reflection/scale/explode의 relation.
- **golden**: 사람이 읽을 수 있는 소형 wall/opening/junction 예제의 exact evidence.
- **sentinel**: 0-wall, all-wall, 장식 평행선, 긴 BoundaryPolygon, Direction arrow, Door/Window, DimensionMark.
- **scaling**: entity 수를 늘리는 grammar와 실 maximum drawing에서 edge growth·RAM·runtime.
- **resolver isolation**: forbidden import, truth/prediction row mismatch, duplicate handle, missing denominator, hash mismatch를 모두 실패시킨다.

### 5.5 예상 개발 규모와 중단 가능한 경계

가장 작은 유효 산출은 “generator + normalization + offset/continuity/junction + matching + resolver”다. 그 다음 face/opening/hatch/lineage를 채널별로 추가한다. 각 단계는 ablation이 가능해야 한다. ILP가 필요 없다는 결과가 나오면 solver 계층을 matching으로 축소할 수 있고, evidence가 GBDT feature로만 유효하면 P1 전체를 CL-F에 흡수할 수 있다. 이미 투자했다는 이유로 lattice를 유지하지 않는다.

---

## 6. 실험 셀 정의

### 공통 실행 규칙

- split은 project·unit·grammar·opening style family 단위다.
- random seed는 임의 수기 선택 대신 `uint64(SHA256(manifest_hash || cell_id || family_id || replicate_id))`로 생성해 manifest에 기록한다.
- deterministic geometry와 solver는 canonical ordering을 사용한다. solver가 내부 random seed를 요구하면 위 seed를 고정하고 thread 수를 기록한다.
- val은 개발·튜닝 허용, test는 방법당 단발이다. test를 연 뒤 파라미터·코드·band를 바꾸면 새 proposal version으로 돌아가며 기존 test는 소모된 것으로 기록한다.
- confidence interval과 subtype 표는 진단용이다. prereg band의 point rule을 사후에 interval rule로 바꾸지 않는다.
- 모든 셀은 raw artifact와 evidence xlsx row가 없으면 PASS가 아니다.

### C0. 계약·누수·resolver 격리 셀

- **가설**: S/F/M identity, split, band, import boundary를 test 접촉 전에 완전히 봉인할 수 있다.
- **데이터**: 세 manifest와 implementation dependency graph.
- **지표**: group overlap count, duplicate truth key, missing lineage, forbidden import count, unresolved metric definition count.
- **제안 합격선**: 모든 count `0`, 모든 필수 hash 존재, `coverage`와 false merge denominator 고정.
- **킬 조건**: test row가 train/calibration에 나타남, resolver가 generator geometry/threshold를 import함, FloorPlanCAD projected mask를 exact handle truth로 허위 표기함.
- **예산**: 로컬 CPU 수시간, GPU/DGX 없음.
- **시드**: 비확률적; canonical sort만 사용.

### C1. PR-1 wall generator·fidelity 셀

- **가설**: 실제 벽 primitive 다양성과 divergent 현상을 가진 독립 generator를 만들 수 있다.
- **데이터**: 5 grammar × 20 block의 100-case S probe, hidden mutation families, CL-A가 감사한 real divergence summary.
- **지표**: entity-type support, block depth, opening/gap/overshoot strata coverage, real-vs-S histogram KS/TV, exact-handle self-consistency.
- **제안 합격선**: 모든 요구 primitive family가 manifest에 존재하고 exact truth self-check가 완전 일치한다. fidelity의 신규 설계 gate는 주요 연속분포 `KS≤0.10`, 주요 범주분포 `TV≤0.10`으로 제안하며 WSD-EVAL 봉인 전에 승인한다.
- **킬 조건**: 기존 dimension 전용 `synthetic_truth.py`를 wall truth로 재사용, hidden truth가 generator logic과 동일 predicate로 생성, fidelity gate 반복 실패.
- **예산**: 로컬 CPU, 구현 1–2인주와 검증 수시간(설계 추정).
- **시드**: grammar/case별 hash seed; hidden family seed list는 resolver 보관, candidate 개발자에게 비공개.

### C2. cheapest probe: v0 대 lattice

- **가설**: 100-case S와 E1 top-20 divergence에서 P1이 v0 candidate recall을 유지하면서 false merge·flip·메모리를 악화시키지 않는다.
- **데이터**: C1 100-case, CL-A 정렬 artifact 감사를 통과한 E1 top-20과 사전 지정 대조군.
- **지표**: candidate recall, handle F1, false merge rate, candidate edge/entity ratio, component size, metamorphic flip, peak RAM, 도면별 시간.
- **제안 합격선**: S candidate recall `≥0.98`, false merge `≤0.05`, hidden이 아닌 probe F1이 v0보다 낮지 않고, M flip이 kill band `0.02`를 넘지 않음. 수치는 신규 probe gate이며 final claim band를 대체하지 않는다.
- **킬 조건**: hidden synthetic F1 `<0.85`, false merge `>0.05`, flip `>0.02`, quadratic edge 폭증, 48GB 이전 watchdog abort.
- **예산**: 로컬 CPU 1일 이내 목표, GPU/DGX 없음.
- **시드**: C1 seed 고정; solver tie-break 고정; 반복은 환경 variance 측정용으로 동일 입력 순서를 순환한다.

### C3. transform·unit·scale 정규화 셀

- **가설**: INSERT folded/unfolded, rigid transform, reflection, unit/scale 변환에서 world geometry와 prediction lineage가 보존된다.
- **데이터**: nested block synthetic, 1.dwg의 manifest 지정 INSERT 표본, M relations.
- **지표**: world-coordinate deviation, lineage mismatch, handle flip, scale arm invariance, unit-anchor abstention.
- **제안 합격선**: exact synthetic transform은 schema tolerance 안에서 전부 일치하고, 공식 M flip `≤0.01`; scale arm도 같은 relation band를 통과.
- **킬 조건**: determinant/reflection 처리로 wall orientation이 바뀜, ambiguous unit을 임의 mm로 확정, flip `>0.02`.
- **예산**: 로컬 CPU 1일, GPU/DGX 없음.
- **시드**: transform parameter는 hash-derived space-filling set; identity transform을 항상 포함.

### C4. evidence 채널·false merge 셀

- **가설**: offset 단일 증거에 continuity, junction, face, opening, hatch, lineage, single-line을 더하면 장식·기호 false positive를 줄이면서 wall recall을 보존한다.
- **데이터**: CubiCasa train 내부 개발 fold, S negative/sentinel, FloorPlanCAD raster 보조축.
- **arm**: v0, offset-only, `+continuity/junction`, `+face/opening`, `+hatch/lineage`, full P1, name/layer-masked full P1.
- **지표**: subtype precision/recall, candidate recall, false merge, single-line recall, per-channel availability, ablation delta.
- **제안 합격선**: full P1 false merge `≤0.05`, name-masked arm이 공식 band 가능성을 잃지 않고, 어떤 채널의 추가도 사전 지정 recall floor를 조용히 깨지 않음.
- **킬 조건**: 개선이 layer/source hard oracle에서만 나옴, single-line 채널이 장식 false positive를 통제하지 못함, aggressive pruning으로 candidate recall이 C2 gate 아래로 떨어짐.
- **예산**: 로컬 CPU batch 1–2일 목표, 제한된 설계 조합만 사용.
- **시드**: split group seed 고정; arm은 동일 후보·동일 순서로 paired 비교.

### C5. matching 대 component ILP 셀

- **가설**: ILP가 실제 다자 충돌 component에서 matching/greedy보다 false merge를 줄이며 비용 band 안에 든다.
- **데이터**: C2/C4에서 conflict가 있는 S/F components와 real stress components.
- **arm**: deterministic greedy, maximum-weight matching, small-component ILP, capped hybrid.
- **지표**: objective, exact handle F1, false merge, optimality status, component solve time, timeout rate, peak RAM.
- **제안 합격선**: ILP 또는 hybrid가 matching보다 truth metric을 악화시키지 않고, 전체 local p95/RAM band를 만족할 경로가 있음.
- **킬 조건**: ILP 이득이 없거나, 대부분 component가 cap을 넘어가거나, timeout incumbent를 사용해야만 성능이 나옴.
- **예산**: 로컬 CPU 1일; component 병렬도는 RAM watchdog 아래로 제한.
- **시드**: canonical tie-break; solver seed와 thread 수 고정.

### C6. calibration·F 개발 셀

- **가설**: raw rule score를 family-held-out truth에서 calibration하면 정보 해상도를 유지하면서 신뢰도를 맞출 수 있다.
- **데이터**: CubiCasa train 내부 rule-fit/calibration group split; val은 마지막 개발 확인.
- **arm**: uncalibrated score, Platt, isotonic, 조건부 beta; v0와 GBDT 비교군.
- **지표**: Brier, `REL`, `RES`, AUPRC, precision at frozen coverage threshold, reliability table.
- **제안 합격선**: `REL≤0.03`, `RES≥0.02`; F에서 `AUPRC_P1−AUPRC_v0≥0.15`; frozen operating point에서 `precision≥0.90`, `coverage≥0.50`.
- **킬 조건**: calibration group leakage, test로 calibrator 선택, 모든 method가 낮은 REL을 위해 거의 상수 확률만 출력하여 RES 미달.
- **예산**: 로컬 CPU 수시간; 대규모 threshold sweep 금지.
- **시드**: group split hash 고정; bootstrap 진단 seed는 manifest 파생, band 자체는 point estimate 규칙.

### C7. M metamorphic·sentinel 셀

- **가설**: 의미 보존 변환에서 wall verdict가 lineage 아래 안정적이며, 0-wall trivial detector가 통과하지 못한다.
- **데이터**: S metamorphic pack과 manifest가 지정한 실무 145장 M pack. 후자는 relation만 truth다.
- **지표**: relation별 handle flip, probability drift, 0-wall false positive, all/known-wall recall, transform lineage failure.
- **제안 합격선**: 전체 metamorphic handle flip `≤0.01`, 모든 sentinel 계약 충족.
- **킬 조건**: flip `>0.02`, 0-wall detector가 metric 정의상 PASS 가능, scale arm만 예외 처리해야 통과.
- **예산**: 로컬 CPU 1일; drawing streaming.
- **시드**: transform set·순서는 manifest hash로 고정; identity relation 포함.

### C8. scaling·resource 셀

- **가설**: spatial filtering과 component streaming으로 후보 edge가 실측상 quadratic으로 폭증하지 않고 resource band를 지킨다.
- **데이터**: entity 수가 단계적으로 증가하는 S scaling family, 1.dwg 정의 전량, 최대 `412,775` 선분 정의.
- **지표**: `n,m,k`, `m/n`, log-log 성장계수, largest component, p50/p95/end-to-end time, peak RSS, spill량.
- **제안 합격선**: local p95 `≤60초/도면`, peak RAM `≤32GB`, quadratic-growth 판정 없음.
- **킬 조건**: 후보 edge가 entity 수에 대해 실측상 quadratic 폭증, candidate overflow, 48GB 이전 watchdog abort. prune으로 숫자를 낮추고 recall을 잃으면 역시 실패.
- **예산**: 로컬 CPU 1–2일 예약; GPU/DGX 없음.
- **시드**: synthetic size family seed 고정; real drawing 순서는 manifest에 봉인.

### C9. 최종 동결·test 단발·독립 resolver 셀

- **가설**: 동결된 P1이 WSD-EVAL-v1의 모든 band를 동시에 통과한다.
- **선결**: C0–C8이 PASS이고 counsel, fidelity, leakage, hash gate가 닫힘.
- **데이터**: hidden S family, 동결 F test 400, 동결 M pack.
- **지표·합격선**: `F1_S≥0.95`, `AUPRC_F−AUPRC_v0≥0.15`, `precision_F≥0.90 at coverage≥0.50`, flip `≤0.01`, `REL≤0.03`, `RES≥0.02`, p95 `≤60초/도면`, RAM `≤32GB` 전부.
- **킬 조건**: hidden synthetic F1 `<0.85`, false merge `>0.05`, flip `>0.02`, quadratic edge 폭증. kill에 이르지 않은 단일 band 실패도 claim은 false다.
- **예산**: test 단발 로컬 CPU batch; 재실행은 infra failure가 cryptographic evidence로 확인될 때만 별도 invalid run으로 허용하고 결과 선택은 금지.
- **시드**: 모든 seed와 입력 순서 사전 봉인. resolver는 독립 환경에서 `wsd_eval_p1.json`을 한 번 생성한다.

---

## 7. red team 티켓 응답

이 절은 패널 보고서에 P1과 직접 연결된 내용만 다룬다. 티켓 전문이 패킷에 없는 번호의 세부를 임의 복원하지 않는다. 아래 조치는 **해소 계획**이지, 실행 전인 현재 티켓을 CLOSED로 선언하는 것이 아니다.

| 티켓/위험 | P1에 걸리는 이유 | 응답 | 닫힘 증거 |
|---|---|---|---|
| **T1 / PR-2 대리 독립성** | synthetic, external, metamorphic, silver가 같은 평행쌍 prior를 공유하면 증거 수만 늘고 편향은 그대로다. | 채널 provenance를 보존하고, 동일 definition에서 S/F/M 및 보조 silver의 불일치 구조를 측정한다. silver는 truth나 resolver 입력에서 제외한다. train-source × eval-source 교차표를 CL-E와 공유한다. | proxy별 오류 교차표, 조건부 상관, disagreement 사례, 독립성 판정이 xlsx에 존재. |
| **T2 / PR-1 생성기 부재** | 기존 `synthetic_truth.py`는 dimension 전용이며 벽 코드가 없다. | C1에서 독립 wall grammar와 exact handle truth를 실제 구현한다. 기존 파일은 패턴 참고만 허용한다. fidelity gate 전에는 S 성적을 주장하지 않는다. | generator hash, exact truth self-check, real divergence fidelity report. |
| **T3 및 T8 관련 CL-A 선결** | E1 top-20이 `_score_divergence` 정렬 artifact면 cheapest probe 표본이 왜곡된다. | CL-A의 재계산·대조군 봉인 전에는 top-20을 대표 표본이나 truth로 사용하지 않는다. probe에는 원 정렬표와 재계산표를 분리 기록한다. | 정렬 키 감사 결과와 고정 sample manifest. |
| **T5 / PR-3 counsel** | FloorPlanCAD/CubiCasa NC 라벨과 원 도면 권리 문제가 외부 truth·학습을 막을 수 있다. | 서면 확인 전 외부셋 학습·배포 arm을 시작하지 않는다. 허용 범위가 평가만인지 학습까지인지 구분한다. | counsel 문서 id와 허용범위가 F manifest에 기록. |
| **T6 평가 단위** | P1은 instance를 조립하지만 공용 계약은 per-handle `wall_member(h)`다. | primary metric은 원본 handle/instance-lineage로 고정하고, wall-instance/room topology는 secondary로 분리한다. | resolver schema와 denominator audit. |
| **T7 sentinel/recall** | flip 위반율만 보면 0벽 detector가 통과한다. | 0-wall과 all/known-wall sentinel을 C7에 의무화하고, candidate recall·F coverage를 conjunction에 둔다. | sentinel raw predictions와 recall denominator. |
| **T9 / T21 v0 baseline 선계측** | P1 lift는 정확히 같은 입력·평가 우주의 v0가 있어야 해석된다. | `fast_score`를 고정 adapter로 재현하고 P1과 같은 manifest·split·resolver로 채점한다. 패킷의 과거 수치를 새 run 증거로 대신하지 않는다. | v0 implementation hash, paired predictions, AUPRC difference 계산. |
| **T16 절대 대 상대 band** | unit 추정 실패와 CubiCasa px 축 때문에 절대 mm band가 관례 artifact일 수 있다. | v1 absolute `50–400mm` arm과 dimension/도면-anchor relative arm을 C3/C4에서 먼저 A/B한다. unit ambiguous이면 relative/abstain을 명시한다. | unit stratum별 결과와 anchor provenance. |
| **T17 proxy 교차요인** | 동일 definition에서 proxy 불일치가 감춰질 수 있다. | T1과 병합해 train truth source × eval truth source를 분리하고 diagonal/non-diagonal 성능과 오류 교집합을 보고한다. 평균 한 숫자로 합치지 않는다. | CL-E 호환 교차표와 definition-level disagreement ledger. |
| **T34 인용 재-status** | load-bearing 인용의 실험 실행 여부가 false로 남아 있다. | 본 문서의 문헌은 방법론 계보로만 사용하고 본 프로그램의 실행 증거로 세지 않는다. 구현 전 정확한 서지를 검증하며 `요검증` 표기를 제거하려면 별도 citation audit가 필요하다. | bibliography verification log; 모든 성능 주장은 본 run artifact에 연결. |
| **R12 quadratic 후보 폭증 위험** | 최대 정의가 `412,775` 선분이고 arrangement가 폭증할 수 있다. | 전체 pair 금지, spatial index, component streaming, edge-growth telemetry, 32GB band와 48GB hard abort를 C8에서 봉인한다. | n–m scaling 표, 성장계수, component/RAM/time trace. |

추가 경계는 다음과 같다.

- **T10/T23 Graph IR adjacency 감사**는 패널상 CL-F의 learned Graph IR 선결이다. P1은 그 패키지를 전제하지 않는다. 다만 P1 arrangement IR에도 noding completeness와 incidence checksum을 넣어 유사 위험을 선제적으로 기록한다. 이것을 T10/T23의 공식 closure라고 부르지는 않는다.
- **T22**는 calibration P2가 P1 대비 lift를 주장할 때의 하드 선결이다. P1은 이후 방법이 비교할 수 있도록 동결 baseline과 resolver artifact를 제공하지만, P2 결과를 대신 주장하지 않는다.
- **T13 DGX/vision**은 P1 compute path에 직접 적용되지 않는다. DGX가 불통이어도 P1을 실행할 수 있어야 한다.
- 패널의 34개 티켓 전부가 OPEN이라는 상태를 보존한다. 이 dossier 하나가 실행·counsel·감사 증거 없이 티켓을 닫지 않는다.

---

## 8. 인접 제안과의 관계 및 사망 조건

### 8.1 병합 가능한 지점

#### CL-A E1 법의학 감사

P1의 cheapest probe가 사용할 divergence sample을 정화한다. handle 실재성, entity histogram, INSERT depth, bbox 단위, 정렬 키 artifact를 CL-A가 제공하면 P1은 그 manifest를 읽는다. CL-A 결과를 P1 wall truth로 승격하지 않는다.

#### CL-C wall synthetic truth + WSD-EVAL-v1

P1의 S pack과 resolver contract는 CL-C의 직접 소비자다. generator, hidden family, manifest hash, exact handle schema는 중복 구현하지 않고 공용화할 수 있다. 단 candidate generator와 truth generator의 predicate 공유는 금지한다.

#### CL-D metamorphic battery

transform generator, lineage schema, 0/all-wall sentinel을 공용화한다. P1은 scale·explode·layer rename까지 모두 소비한다. CL-D의 위반율만 가져오고 recall sentinel을 빠뜨리면 안 된다.

#### CL-E truth-source 교차요인

P1의 T1/T17 응답을 CL-E의 train×eval matrix에 그대로 제공한다. 이 결과는 proxy 독립성의 감사이며 P1 공식 per-handle band와 별도다.

#### CL-F 고전 ML→PU→GNN

P1 evidence vector와 selected component 특징은 GBDT/GNN feature로 재사용할 수 있다. 반대로 GBDT를 P1 calibrator로 숨겨 넣지는 않는다. P1은 결정론 baseline, CL-F는 learned lift라는 경계를 유지한다.

#### CL-I 관례 prior

layer/source prior audit와 name-mask arm을 공유한다. firm lexicon이 생겨도 P1에서 hard oracle로 쓰지 않고, project-held-out에서만 prior 가치를 평가한다.

### 8.2 차별점과 보존해야 할 반대의견

- **CL-J face/room-first**는 P1의 centerline→arrangement 방향을 역전한다. P1의 face evidence가 잘 작동해도 room-first가 더 낫다는 가능성은 남는다. messy divergence에서 두 방향을 비교해야 한다.
- **GBDT**는 feature-to-label mapping을 학습하지만 P1은 evidence와 조합 제약으로 instance 집합을 선택한다. P1이 GBDT보다 해석 가능하다는 이유만으로 낮은 성능을 면제받지 않는다.
- **raster/VLM**은 vector에 없는 visual context를 쓸 수 있으나, P1 truth/resolver가 되지 않는다. FloorPlanCAD는 보조 raster projection으로만 접속한다.
- **silver 판정자**는 기존 detector와 대체로 독립인 축일 수 있지만, 5기가 약 2어휘 가문으로 갈렸고 5독립으로 셀 수 없다. P1 학습 truth로 사용하지 않는다.
- **RL/집합 조립**은 향후 solver policy가 복잡해질 때 후보일 수 있으나, 작은 component ILP가 충분한지 먼저 확인한다.

### 8.3 P1이 죽어야 하는 조건

다음은 일부 모듈 수정이 아니라 proposal을 중단하거나 더 단순한 인접 방법으로 흡수해야 하는 조건이다.

1. **패킷 명시 kill**: hidden synthetic family F1 `<0.85`, false merge rate `>0.05`, metamorphic flip `>0.02`, 또는 후보 edge의 실측 quadratic 폭증.
2. **truth 기반 붕괴**: independent wall generator와 fidelity gate를 만들지 못하거나, truth generator가 detector와 같은 평행쌍 predicate를 공유해 self-confirmation이 됨.
3. **provenance 붕괴**: FloorPlanCAD raster mask를 exact per-handle label로 바꾸는 검증 가능한 adapter가 없는데도 원 claim이 이를 필수 F truth로 고집함. 이 경우 original version은 resolve 불가이며 새 manifest version이 필요하다.
4. **candidate ceiling**: single-line, ARC/polyline, nested INSERT를 넣어도 candidate recall이 final F1 가능 영역에 못 미침. resolver는 생성되지 않은 벽을 복구할 수 없다.
5. **layer oracle 의존**: name/layer를 mask하면 개선이 사라지고 project-held-out에서 무너짐.
6. **lattice 무효**: matching·ILP가 greedy보다 truth metric을 개선하지 않거나 비용만 늘림. 이 경우 solver를 죽이고 evidence를 GBDT/CL-F feature로 흡수한다.
7. **evidence 비독립**: 다중 채널의 개선이 실제로 같은 offset prior의 중복 계수에서만 발생하고 T1/T17 교차요인에서 비대각 일반화가 없음.
8. **calibration 무정보화**: `REL`을 맞추기 위해 거의 상수 확률을 내서 `RES<0.02`가 됨.
9. **운영 부적합**: p95 `>60초/도면` 또는 peak RAM `>32GB`; 48GB hard stop을 피하려고 recall을 조용히 prune해야 함.
10. **강한 단순 기준선 열세**: 같은 split과 test 단발에서 GBDT가 더 높은 성능·낮은 비용을 보이고, P1 evidence를 넣은 hybrid가 lattice 없이 같은 이득을 얻음. 공식 claim band를 우연히 일부 통과하더라도 P1 독립 방법으로서의 채택 근거는 약해진다.
11. **scale 실패 지속**: 현재 실패한 scale arm을 예외 처리하거나 특정 unit family를 제외해야만 metamorphic band를 맞춤.
12. **권리·재현성 실패**: counsel gate가 닫히지 않거나, S/F/M 및 구현 hash를 동결한 독립 resolver run을 만들 수 없음.

### 8.4 최종 claim·forecast·resolution 계약

- **claim**: P1이 동결된 WSD-EVAL-v1에서 지정된 모든 prereg band를 통과한다.
- **forecast**: `null`. reference class `RC-WALL-ZL`은 `n=0`, 요구 최소 `n_min=5`이므로 수치 확률을 만들지 않는다.
- **base rate**: `none`.
- **uncertainty type**: `epistemic`. 독립 synthetic truth, external held-out, metamorphic relation으로 줄일 수 있다.
- **resolution trigger**: S/F/M manifest hash와 implementation hash를 봉인한 뒤 독립 resolver가 `wsd_eval_p1.json`을 생성하는 때.
- **resolution criterion**: 오직 `P1_all_bands_pass == true`일 때 참.
- **현재 verdict**: `open`.

cheapest probe가 모든 초기 gate를 통과하면 이후 probability를 올리는 새 version을 남길 수 있고, false merge·leakage·hidden-family·scale 실패가 나오면 내리는 새 version을 남길 수 있다. 기존 entry를 덮어쓰지 않는다. empty reference class 상태에서 숫자를 꾸며 넣지 않는다.

### 8.5 실행 인계 체크리스트

최종 test를 여는 실행자는 다음 질문에 모두 “예”라고 답해야 한다.

- 실제 벽 generator가 존재하고 fidelity gate를 통과했는가?
- FloorPlanCAD와 CubiCasa truth provenance 및 counsel 범위가 명시됐는가?
- S/F/M group split과 hidden family가 hash로 봉인됐는가?
- v0, P1, GBDT 비교군이 같은 평가 우주를 쓰는가?
- resolver가 candidate code를 import하지 않는가?
- 0-wall/all-wall sentinel, name-mask, unit/scale, explode relation이 포함됐는가?
- candidate edge 성장·RAM·p95가 raw telemetry로 남는가?
- evidence xlsx가 실패 셀까지 포함하는가?
- test를 아직 열지 않았고, 모든 band와 operating threshold가 고정됐는가?

하나라도 아니면 C9를 실행하지 않는다. 실행하지 않은 상태는 FAIL을 숨긴 PASS가 아니라 `BLOCKED/INVALID`로 기록한다.

DOSSIER_COMPLETE: calibration_P1
