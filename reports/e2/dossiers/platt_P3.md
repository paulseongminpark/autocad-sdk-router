# platt_P3 방법론 심층 도시에 — Metamorphic/불변식 게이트 배터리

## 제안 판정 요약

이 제안의 산출물은 새 벽 분류기가 아니라, P1/P2/P4/P5 후보가 동일한 입력 의미를 보존하는 변환과 명백한 비벽 교란에 대해 일관된 출력을 내는지를 **사람 라벨 없이 판정하는 공통 심판기**다. 심판기 자신도 무오류로 가정하지 않는다. 각 metamorphic relation(MR)은 (a) correct-by-construction 합성 IR에서 기준 구현 위반 0%, (b) 비동치 시딩 뮤턴트 적발률 95% 이상을 모두 만족해야만 정식 배터리에 들어간다. 관계·역치·적용 가능성 규칙·뮤턴트 목록·시드는 어떤 후보의 실코퍼스 결과도 보기 전에 동결한다.

현재 즉시 가능한 것은 회전 불변과 distractor 주입의 20 도면정의 엔지니어링 프로브다. 그러나 패킷이 밝힌 현 합성팩은 충실도 B1에서 실패했고 벽 생성 코드도 없으므로, 이 프로브를 통과해도 정식 배터리 admission이나 후보 승격을 선언할 수 없다. PR-1의 벽 합성 생성기와 fidelity gate, 그리고 0벽/전벽 퇴행을 죽이는 sentinel이 먼저 닫혀야 한다. 이 경계가 이 제안의 가장 중요한 정직성 조건이다.

수치의 상태는 다음처럼 구분한다.

- `실측`: 이 패킷의 2026-07-18 다이제스트에 명시된 값만 사용한다.
- `프리레그 제안`: 아래 실험 전에 봉인할 역치·시드·예산이다. 관측값이 아니다.
- `문헌 일반 지식`: 방법론 계보 설명이며 이 프로그램에서 재현됐다는 뜻이 아니다.

---

## 1. 이론적 근거·선행연구

### 1.1 Test-oracle problem과 metamorphic testing

Metamorphic testing은 정답 라벨을 직접 알기 어려운 프로그램에서 source input `x`와 의미 보존 변환 `T(x)`를 만들고, 두 출력 사이에 반드시 성립해야 할 관계 `R(f(x), f(T(x)))`를 검사한다. 이 계보는 T. Y. Chen 등의 metamorphic testing 연구와 후속 survey에 의해 정리됐고, 과학 계산·최적화·기계학습처럼 단일 입력의 정답 oracle이 비싸거나 부재한 경우에 널리 적용돼 왔다. 구체 선행으로 다음을 사용한다.

- T. Y. Chen, S. C. Cheung, S. M. Yiu의 초기 metamorphic testing 논문과 Chen 등, *Metamorphic Testing: A Review of Challenges and Opportunities*를 관계 설계와 oracle 문제의 근거로 삼는다. 초기 논문의 정확한 판본·연도는 구현 전 서지 확인이 필요한 `요검증` 항목이다.
- C. Murphy 등의 *Properties of Machine Learning Applications for Use in Metamorphic Testing*은 학습 시스템의 예측 관계를 테스트 oracle로 바꾸는 선행이다. 정확한 학회 판본은 `요검증`한다.
- DeepXplore는 여러 딥러닝 시스템의 differential behavior를 이용한 테스트 생성 시스템이다. 본 제안은 여러 모델의 다수결을 진리로 쓰지 않고, 사전에 논증·합성 검증된 단일 관계를 쓴다는 점에서 다르다.
- METTLE 계열 연구는 ML 시스템의 metamorphic relation을 체계적으로 정의·검사한 선행으로 참고한다. 정확한 서지와 대상 시스템은 `요검증`한다.

벽 과업에서 “회전 뒤에도 같은 원 핸들이 벽이어야 한다”는 것은 출력 클래스의 **invariance**이고, “변환된 좌표계에서 같은 벽 중심선·정션이 함께 변해야 한다”는 것은 **equivariance**다. 이를 혼동하면 좌표는 달라졌는데 원시 좌표의 완전 일치를 요구하거나, 반대로 클래스 membership 변화까지 허용하는 오류가 생긴다. 따라서 본 배터리는 클래스 membership 불변과 기하 산출물의 공변을 분리해 채점한다.

### 1.2 군 작용과 기하 불변성

평면 강체변환은 회전·이동·반사의 합성으로 표현할 수 있다. 입력 기하에 변환 `g`를 적용했을 때 membership 분류기 `m`에는 `m(g·x)=m(x)`가, 좌표 산출기 `z`에는 `z(g·x)=g·z(x)`가 기대된다. Cohen과 Welling의 group-equivariant convolution 연구는 학습 표현에서 대칭을 다루는 대표 선행이지만, 본 제안은 특정 신경망 구조를 강제하지 않고 최종 시스템의 관찰 가능한 계약을 시험한다.

단위 재스케일은 일반적인 “도면을 확대해도 같은 결과인가”와 구분한다. 단위 변환에서는 좌표뿐 아니라 50~400mm 두께 밴드, 6mm snap 등 길이 차원의 설정값도 같은 물리량을 유지하도록 바뀌어야 한다. 반면 기하만 확대하고 설정을 고정하는 scale arm은 분포 밖 일반화 시험이다. 다이제스트의 강체·단위 1.0 PASS와 scale arm 0.7624 FAIL은 이 구분이 실제 하네스에서 중요함을 보여 주는 실측이다. 본 제안은 단위 불변을 하드 관계로, 설정 고정 기하 확대를 별도 강건성 진단으로 기록한다.

### 1.3 Mutation testing: 게이트의 게이트

Mutation testing은 DeMillo–Lipton–Sayward의 test-data selection 논의와 이후 Offutt, Jia와 Harman 등의 mutation analysis 계보에 기대며, 테스트가 의도적으로 삽입한 결함을 실제로 적발하는지 본다. 정확한 초기 논문 서지사항은 `요검증`한다. 본 제안에서 뮤턴트는 후보를 벌주기 위한 임의 훼손이 아니라 **관계의 판별력**을 시험하는 장치다.

관계 `r`의 conviction은 비동치 뮤턴트 집합 `M_r` 중 관계가 죽인 수의 비율이다.

`conviction(r) = |{μ ∈ M_r : r가 μ를 위반시킴}| / |M_r|`

correct-by-construction 기준 구현이 관계를 한 번이라도 위반하면 relation soundness가 깨진다. 반대로 기준 구현은 모두 통과하지만 결함 뮤턴트를 거의 죽이지 못하면 relation sensitivity가 없다. 그래서 `기준 위반 0% AND conviction ≥ 95%`를 동시에 admission에 쓴다. 동치 뮤턴트는 결과를 본 뒤 편의상 제외하지 않고, 합성 truth 전수 비교로 사전에 동치임을 증명한 경우에만 분모에서 제외한다.

### 1.4 Arrangement·topology 일관성

선분 배치에서 교차·접촉을 노드로 만들고 edge가 face 경계를 구성하는 planar arrangement 관점은 계산기하의 표준 도구이며, de Berg 등의 *Computational Geometry: Algorithms and Applications*가 대표 교과서 계보다. R16 계열의 centerline→room 논리는 검출된 벽이 고립된 평행선 쌍 목록이 아니라 chain·junction·공간 분할에 참여해야 한다는 구조적 prior를 준다.

그러나 이는 모든 평면에서 보편적인 불변식이 아니다. 오픈플랜, 부분 철거도, 파단된 스캔, 외곽이 잘린 뷰포트는 올바른 벽도 닫힌 face를 만들지 않을 수 있다. 따라서 arrangement 관계는 `closed_partition` 적용 스코프가 합성 construction 또는 후보와 독립적인 사전 메타데이터로 확정된 셀에서만 하드 관계가 된다. 그 외에는 soft diagnostic이며 후보 kill에 쓰지 않는다.

### 1.5 Anti-relation, sentinel, leakage 방지

Anti-relation은 의미 보존 변환의 반대편을 시험한다. 비벽임을 construction으로 아는 치수선·그리드 모양을 빈 영역에 주입했을 때 주입 핸들이 벽으로 늘어나면 위반이다. CubiCasa 전이에서 Direction 화살표, BoundaryPolygon, Door, Window, DimensionMark가 주요 FP였고 최소길이 필터의 천장도 F1 0.335였다는 실측 때문에, 단순 짧은 아이콘 대신 긴 평행 구조와 tick/leader를 포함한 교란이 필요하다.

“0벽 출력”은 모든 equality 관계를 공허하게 통과할 수 있고, “전벽 출력”도 특정 변환에서는 완전 일관될 수 있다. 그러므로 양성 wall fixture의 recall sentinel과 순수 교란 fixture의 false-positive sentinel을 relation equality와 별도 하드 게이트로 둔다. 이는 패널 공격 F/T7의 직접 수정이다.

마지막으로 relation 목록을 실코퍼스에서 조정하면 심판기가 후보의 오류 패턴에 적응해 leakage가 생긴다. 합성 admission → manifest 봉인 → 실코퍼스 후보 채점의 단방향 흐름을 지키며, 실코퍼스에서 관계가 부당해 보이면 기존 결과를 다시 튜닝하지 않고 relation 또는 synthetic↔real 보조가정을 kill한다. 수정 관계는 새 버전과 새 미접촉 후보 집합이 있어야 평가할 수 있다.

---

## 2. 알고리즘 정확 스펙

### 2.1 공통 입력·출력 계약

도면 IR을 `D=(H,G,A,U)`로 둔다.

- `H`: 안정적인 entity/segment handle 집합. 파생 segment는 `(source_handle, part_index)`를 갖는다.
- `G(h)`: 좌표, entity type, polyline/arc 근사 provenance, bbox 등 기하.
- `A(h)`: 레이어·색·블록 경로 같은 비기하 속성. name-blind arm에서는 이름 토큰을 마스킹한다.
- `U`: 좌표 단위와 물리 단위 변환 정보. 알 수 없으면 `unknown`으로 명시하고 mm 관계를 적용하지 않는다.

후보 adapter의 정규 출력은 `Y=(q,m,P,Z,trace)`다.

- `q(h)∈[0,1]`: 벽 membership score. 점수가 없는 후보는 `0/1`로 승격한다.
- `m(h)=1[q(h)≥τ]`: 프리레그된 threshold의 이진 membership.
- `P`: 벽으로 검출한 평행 쌍과 해당 centerline. pair를 내지 않는 후보는 공통 기하 postprocessor가 `m=1` 핸들에서 생성하며, 이 사실을 adapter id에 기록한다.
- `Z`: snap된 centerline graph와 junction/face 산출물.
- `trace`: 후보 버전, 설정, seed, runtime, 경고, 변환 provenance.

변환 `T_r`는 follow-up IR `D'`와 원본 대응 `π_r: H_eligible→H'`를 함께 반환한다. 주입 객체는 `H_injected`로 별도 표식하되 후보에게 이 표식은 전달하지 않는다. 핸들 대응을 좌표 nearest-neighbor로 사후 추정하지 않으며, 생성 시 provenance로 보존한다.

### 2.2 관계 카탈로그

#### MR-R: 강체·미러 불변/공변

프리레그 변환 집합은 정수 직각 회전, 한 개의 비직각 회전, 두 방향 이동, x/y 반사 및 제한된 합성으로 둔다. 구체 각도·이동량은 synthetic admission 전에 JSON manifest에 고정한다. 이동량은 도면 bbox로부터 결정론적으로 만들되 좌표 overflow를 만들지 않아야 한다.

membership assertion:

`∀h∈E_r(D): m_D(h) = m_T(π_r(h))`

score diagnostic:

`Δq_r(D)=max_{h∈E_r(D)} |q_D(h)-q_T(π_r(h))|`

geometry assertion:

`Hausdorff(T_r(P_D), π_r^{-1}(P_T)) ≤ ε_geo`

이진 membership 완전 일치가 primary다. `ε_geo`와 score tolerance는 synthetic의 수치 정밀도 실험으로만 정하고 봉인한다. **유효한 회전 trial에서 membership 한 건이라도 바뀌면 후보 즉사**다. silver 점수나 외부 라벨 F1로 구조할 수 없다. 반사·이동은 전체 invariant 관계 위반율 1% 이하 초안을 적용하되 numerator/denominator를 함께 보고한다.

#### MR-U: 단위 재스케일 불변

길이 단위 배수 `s>0`에 대해 좌표와 모든 길이 차원 설정을 함께 변환한다.

`G' = sG`, `band' = s·band`, `snap' = s·snap`, `tolerance' = s·tolerance`

무차원 값인 각도 허용, overlap 비율, 확률 threshold는 바꾸지 않는다. 출력 좌표는 `1/s`로 원좌표계에 되돌린 뒤 MR-R과 같은 assertion을 쓴다. `U=unknown`인 도면에서는 unit relation을 억지로 적용하지 않고 `NA_UNIT_UNKNOWN`을 기록한다. 기하만 `s`배하고 설정을 고정한 시험은 `ROB-SCALE` 진단 셀로 분리하며 MR-U pass/fail에 섞지 않는다.

#### MR-B: 두께 밴드 내 섭동 equivariance

적용 가능한 평행 쌍 후보 `c=(a,b)`를 후보 예측이 아니라 입력 기하 인덱스에서 생성한다. 다음을 모두 만족해야 eligible이다: 평행각 허용 내, overlap 최소 이상, 두 rail 주변에 충돌 없는 clearance 존재, 변형 후 두께가 프리레그 밴드 내부, endpoint/junction topology 보존. 쌍의 centerline은 고정하고 두 rail을 법선 방향으로 `±δ/2` 이동한다.

`δ`는 밴드 내부의 하·중·상 stratum에서 manifest seed로 뽑되 경계와 정확히 같은 값은 별도 boundary cell로 둔다. 요구 관계는 두 rail membership과 pair membership의 유지, centerline의 허용오차 내 유지다. 두께가 밴드를 넘거나 다른 entity와 충돌한 trial은 실패가 아니라 `INVALID_TRANSFORM`으로 제외하며 제외율을 반드시 보고한다. 이 exclusion이 후보별로 달라지지 않도록 eligibility는 후보 실행 전에 계산한다.

#### MR-C: chain·junction·arrangement 일관성

검출 pair의 centerline endpoint를 snap하고 무방향 그래프 `Z=(V,E)`를 만든다. 각 edge에 다음 구조 지표를 계산한다.

- `chain_support(e)`: collinear continuation 또는 유효 junction으로 이어지는 endpoint 수.
- `junction_support(e)`: degree가 2가 아닌 접속 노드 참여 여부와 접속 각도.
- `face_support(e)`: planarized graph에서 유효 face 경계에 참여하는지.
- `dangling_length(e)`: 지지되지 않은 말단 길이.

`closed_partition` 합성 family에서는 true wall edge가 적어도 chain/junction 또는 face support 중 프리레그된 하나를 가져야 하며, 전체 검출이 공간분할에 전혀 참여하지 않는 퇴행을 위반으로 잡는다. 오픈플랜·잘린 뷰에서는 지표만 보고 하드 판정하지 않는다. self-intersection, near-touch, arc tessellation에 따른 불안정을 피하기 위해 planarization tolerance는 IR 단위에 연동하고 synthetic boundary fixture로 검증한다.

#### MR-D: dimension/grid distractor 주입 anti-relation

도면의 기존 bbox 안에서 entity가 없는 안전 patch를 결정론적으로 찾는다. 없으면 `NA_NO_SAFE_PATCH`다. 주입 template은 다음 family를 가진다.

- 두 평행선 + endpoint ticks + extension lines의 dimension-chain형.
- 긴 평행선 + 반복 직교 tick의 grid형.
- 화살촉/leader + 장선분의 direction/dimension-mark형.
- 같은 형상을 중립 layer명, 무작위 opaque layer명, 기존 name-blind 마스크 아래에서 반복하는 attribute arm.

주입 시 construction metadata는 runner만 보유하고 후보에는 평범한 IR entity로 전달한다. primary assertion은 `Σ_{h∈H_injected} m'(h)=0`이다. secondary assertion은 원 핸들의 membership이 유지되는지다. “총 벽 수가 늘지 않음”만 쓰면 원벽 하나를 잃고 교란 하나를 얻는 상쇄가 가능하므로, injected false positive와 original stability를 따로 채점한다.

#### S-Z/S-A: 0벽·전벽 sentinel

- `S-Z`: 최소 하나 이상의 correct-by-construction wall chain을 포함한 fixture에서 wall membership recall이 프리레그 최저선 이상이어야 한다. 항상 0을 출력하는 adapter는 kill한다.
- `S-A`: 벽이 전혀 없고 dimension/grid/door/window 유사 구조만 있는 fixture에서 false-positive membership이 프리레그 상한 이하여야 한다. 항상 1을 출력하는 adapter는 kill한다.

sentinel의 구체 recall/FP 역치는 PR-1 generator의 hidden family를 보기 전에 synthetic development family에서 고정한다. relation violation이 낮아도 sentinel 실패 후보는 랭킹에서 제외한다.

### 2.3 관계별 위반량과 후보 판정

관계 인스턴스 `i`의 binary failure를 `b_{r,i}∈{0,1}`로 두고,

`V_r = Σ_i b_{r,i} / N_r_valid`

로 계산한다. 모든 `NA/INVALID` 사유와 `N_r_valid`를 관계별로 공개한다. 전체 핸들을 분모로 삼는 micro-average는 큰 도면의 true negative가 위반을 희석하므로 primary로 쓰지 않는다. 도면×변환 인스턴스 단위 macro rate가 primary이고, handle symmetric difference는 secondary다.

145개 실코퍼스에서 관계당 도면별 한 개의 대표 assertion을 쓰면 1건 실패는 약 0.69%, 2건은 약 1.38%이므로 “≤1%”는 사실상 최대 1건을 허용한다. 변환을 여러 개 쓰는 경우에는 분모를 임의로 늘려 역치를 쉽게 만들지 않도록, 한 도면의 어느 변환에서든 실패하면 그 도면의 relation failure를 1로 집계한다. 회전은 예외적으로 0건만 허용한다. 유효 도면 coverage도 함께 보고하며, 낮은 coverage로 얻은 pass는 `INSUFFICIENT_COVERAGE`다.

후보 결과는 단일 평균점수보다 다음 lexicographic gate로 판정한다.

1. 배터리 자체가 admitted 상태인가.
2. S-Z와 S-A를 모두 통과했는가.
3. 회전 hard gate가 0 위반인가.
4. 나머지 admitted invariant의 `V_r≤0.01`인가.
5. anti-relation과 scoped arrangement의 위반 profile은 어떤가.
6. 동률일 때만 위반 관계 수, macro rate, coverage를 순서대로 비교한다.

정의가 필요한 보조 penalty는 `L_gate=Σ_r w_r V_r + λ_Z I[S-Z fail] + λ_A I[S-A fail]`로 기록할 수 있지만, 하드 게이트를 평균으로 상쇄하지 않도록 랭킹 primary로 쓰지 않는다. `w_r`는 synthetic admission 전에 동결하고 실코퍼스 결과로 조정하지 않는다.

### 2.4 Relation admission과 `mutate()` 패턴

각 relation은 공개 development mutants와 미공개 admission mutants를 분리한다. 뮤턴트 family는 다음과 같다.

- 회전: x/y 축 교환 누락, 각도 feature를 절대 방향에 결박, inverse transform 부호 오류, bbox origin 회전 누락.
- 반사: determinant sign 처리 오류, winding/order 의존, 좌우 layer prior 주입.
- 단위: 좌표만 배수 적용, snap만 미변환, 두께 band 이중 변환, mm↔px 잘못된 경로.
- 두께: 경계 포함 부호 오류, 한 rail만 이동, centerline drift, overlap 재계산 누락.
- arrangement: snap 누락, T-junction 소실, edge 중복, face polygonization 전 교차 분할 누락.
- distractor: 새 entity를 모두 wall로 승격, 긴 평행선 우선, DimensionMark family 우선, layer명 shortcut.
- sentinel: constant-zero, constant-one, score threshold 극단화.

기존 L5 `mutate()` 패턴에는 `mutate(base, family, seed) -> mutant_id, callable, expected_non_equivalent` adapter로 접속한다. 실제 함수 signature는 저장소 확인 전 가정하지 않으며 구현 시 얇은 wrapper로 맞춘다.

admission 절차는 다음과 같다.

```text
build synthetic_dev, synthetic_hidden using disjoint generator seeds/families
freeze relation definitions, applicability predicates, tolerances, thresholds
for each relation r:
    assert violations(reference_oracle, synthetic_dev ∪ synthetic_hidden, r) == 0
    dev_kills = run(r, public_mutants)
    hidden_kills = run(r, hidden_mutants)
    remove only mutants proven equivalent by full synthetic truth comparison
    conviction = hidden_kills / valid_hidden_mutants
    admit r iff reference violations == 0 and conviction >= 0.95
    if r kills no relevant mutant family: discard r under card rule 2
freeze battery manifest and content hashes
only then run candidate adapters on real/cross-domain corpora
```

관계별 최소 20개의 비동치 hidden mutant를 프리레그 제안으로 둔다. 이 경우 95%는 적어도 19개 kill을 뜻한다. 단, 뮤턴트 수를 맞추기 위한 사소한 복제는 금지하고 failure mechanism family별 균형을 함께 공개한다. seed 반복은 stochastic 후보 출력 변동을 분리하기 위한 것이지 같은 뮤턴트를 여러 표본처럼 세는 용도가 아니다.

### 2.5 확률적 후보, 상관, abstain

확률적 후보는 고정 seed 반복에서 각 관계의 실패 확률을 구하고, primary gate에는 프리레그된 canonical seed의 재현 가능한 결과를 사용하되 반복 결과를 함께 보고한다. 반복 간 분산이 크면 `NONDETERMINISTIC` 경고를 내며 best-seed 선택을 금지한다.

관계 간 독립성을 가정하지 않는다. 후보×도면별 binary violation vector에 대해 φ 상관, Jaccard overlap, hierarchical clustering을 보고한다. 완전히 중복되는 관계가 많으면 “여러 증거”로 세지 않고 하나의 failure family로 묶는다. 모든 후보가 같은 gate vector로 동률이면 승자를 만들지 않고 패널의 `abstain_condition A1` 입력으로 전달한다.

---

## 3. 벽 과업 적응 설계

### 3.1 공통 adapter와 두 층의 시험

관계 실패가 탐지기 로직인지 DXF 입출력인지 분리하기 위해 두 층으로 실행한다.

- `IR-level`: `cubicasa_ir` 또는 공통 staged IR을 직접 변환해 `fast_score`/후보 scorer에 넣는다. 알고리즘 불변성을 싸게 격리한다.
- `E2E-level`: 원본과 변환 IR을 각각 후보의 실제 serialize→parse→normalize→score 경로로 통과시킨다. 단위·INSERT transform·entity normalization 같은 plumbing 결함까지 포함한다.

IR-level만 통과하고 E2E가 실패하면 후보 의미 모델 자체보다 ingest/normalization 계층의 결함으로 분류하지만, 배포 후보의 gate는 여전히 실패다. 두 결과를 평균하지 않는다.

### 3.2 1.dwg 실도면축

실측으로 staged DXF에는 384개 도면정의가 있고 최대 정의는 412,775 선분이다. P3가 명시한 145 실코퍼스의 정확한 구성 목록은 이 패킷에 없으므로, 실행 전 별도의 content-addressed manifest가 존재해야 한다. 그 목록을 성능으로 선택하거나 누락 도면을 결과를 본 뒤 교체하지 않는다. manifest가 없으면 145 채점은 `BLOCKED_MANIFEST_MISSING`이며 표본 구성을 발명하지 않는다.

cheapest probe는 사전 지정된 20개 definition에 v0와 비교 후보를 적용한다. 회전과 distractor 주입, S-Z/S-A runner plumbing만 하루 로컬 예산으로 검증한다. 이 단계의 목적은 handle provenance, transform round-trip, evidence xlsx, failure localization을 확인하는 것이며 정식 battery pass가 아니다. 145 실행에서는 admitted 관계만 사용하고, 도면별 원본/변환 쌍과 failure witness handle을 저장한다.

실도면의 SPLINE 3,973, ARC 2,198, HATCH 264 혼재라는 실측은 합성 LINE-only 관계가 충분하지 않음을 뜻한다. 관계별 eligibility와 transform은 ARC/SPLINE의 analytic transform 또는 명시적 tessellation provenance를 지원해야 하고, HATCH/INSERT는 경계·블록 transform 경로를 보존해야 한다. 지원하지 못한 entity를 조용히 버리지 않고 coverage 손실로 기록한다.

### 3.3 CubiCasa5k SEG-IR 벡터축

CubiCasa5k는 5,000 도면이 모두 SEG-IR로 변환됐고 실패가 0이며, train/val/test가 각각 4,200/400/400으로 나뉜 실측 자산이다. 본 배터리는 Wall label을 relation 정의나 threshold 조정에 쓰지 않는다. train split은 synthetic distractor template의 실제 geometry를 베끼는 원천으로도 쓰지 않고, 후보 학습은 각 제안의 별도 계약에 맡긴다.

- `val`: 후보 개발 중 relation profile을 볼 수 있으나, **배터리 관계와 gate threshold는 이미 synthetic-only로 동결**돼 있어야 한다. 후보가 val MR에 맞춰 튜닝된다면 그 사실을 기록하고 최종 test 단발의 독립성을 보존한다.
- `test`: 방법당 최종 후보 한 번만 실행한다. MR, 사람 Wall label metric, shuffle control을 같은 증거 묶음에 내되 test 결과로 후보를 재튜닝하지 않는다.
- 좌표가 px이고 도면별 축척을 알 수 없으므로 mm 기반 MR-U/MR-B는 적용하지 않는다. px geometry에 임의의 mm 의미를 부여하지 않는다. 순수 강체·미러와 dimension distractor, px-space topology만 적용한다.

기하 탐지기 v1의 val F1은 0.2358(P 0.134, R 0.981), HistGradientBoosting은 val F1 0.517(P 0.860, R 0.370, AUC 0.9215)이라는 실측이다. P3는 이 F1을 직접 올리는 학습법이 아니다. 대신 다음의 추가 정보를 준다.

- 방향 feature `sin2θ/cos2θ`를 쓰는 GBDT가 우연히 val 방향 분포에 기대는지 회전 gate로 적발한다.
- 긴 평행 비벽 구조가 본질 교란이라는 관측을 distractor injection으로 후보별 인과 시험으로 바꾼다.
- 높은 F1 후보가 단위/ingest/transform에 취약한지 외부 라벨과 독립된 축으로 거른다.
- v1의 높은 recall과 GBDT의 높은 precision처럼 다른 operating point를 단일 F1만으로 비교할 때 숨는 constant-like 퇴행을 sentinels로 차단한다.

따라서 “GBDT 0.517보다 높은 F1”은 P3의 자체 성공조건이 아니다. P3의 기여는 그 모델을 포함한 후보의 의미 보존성과 교란 저항을 재현 가능한 gate로 추가하는 것이다.

### 3.4 FloorPlanCAD 래스터축

FloorPlanCAD는 5,308 raster와 wall bbox/segmask가 있으나 vector SVG가 없다. 따라서 vector handle equality를 그대로 요구할 수 없다. raster adapter는 변환 행렬을 기록하고 예측 mask/bbox를 원 pixel frame으로 inverse-warp한 뒤 mask IoU, connected-component 대응, wall-pixel mass drift를 진단한다. 보간·anti-aliasing이 relation failure로 오인되지 않도록 nearest-neighbor mask transform과 content padding 규칙을 synthetic raster fixture에서 먼저 고정한다.

단위 재스케일은 pixel resize와 같지 않으므로 FloorPlanCAD에서 MR-U로 부르지 않는다. raster scale은 `ROB-RASTER-SCALE` 진단이다. distractor는 vector template을 rasterize한 synthetic overlay로만 주입하고, 원 이미지의 의미를 훼손하지 않는 빈 patch eligibility를 먼저 확인한다. 정확한 pixel→SEG-IR handle 역투영이 없는 후보는 raster consistency 결과를 vector membership gate와 합치지 않는다.

FloorPlanCAD/CubiCasa의 NC·원도면 권리 문제가 서면으로 해소되지 않았다는 패널 T5/PR-3가 열려 있으므로, 외부셋 학습 arm과 배포성 주장에는 counsel 확인이 선행한다. P3가 label-free라고 해서 파일 사용권 문제가 사라지지 않는다.

### 3.5 후보 계열별 공정성

- P1 결정론: 실제 설정을 길이 단위와 함께 변환하고, normalization 전후 실패를 분리한다.
- P2 고전ML/PU/GNN: feature extraction부터 재실행한다. 원본 feature를 회전 후 재사용하면 시험이 아니다.
- P4 RL/집합 조립: per-handle `q,m`과 별도 assembly graph를 모두 내게 한다. RL reward를 MR 결과로 학습했다면 평가 leakage로 표시하고 미접촉 test battery를 사용한다.
- P5 raster/VLM: inverse transform 가능한 mask/bbox 계약을 요구한다. 텍스트 설명만 내는 모델은 이 공통 membership gate의 비교 대상이 아니며 별도 adapter 검증 전 `NOT_COMPARABLE`이다.

silver 점수는 gate의 진리나 tie-break 구조수단이 아니다. 특히 다이제스트에서 silver 5기가 약 2개 어휘 가문으로 갈리고 detector↔silver Pearson이 0.2911이므로, 이를 5개 독립 증거로 세지 않는다. 회전 hard gate 실패는 silver 성적과 무관하게 후보 kill이다.

---

## 4. 데이터·컴퓨트 요구

### 4.1 필요한 데이터 묶음

1. PR-1의 correct-by-construction wall IR generator: wall/non-wall handle truth, chain/T/L/X junction, open/closed plan scope, mixed entity와 INSERT transform, 단위 metadata를 생성해야 한다.
2. `synthetic_dev`와 seed/family가 분리된 `synthetic_hidden`: relation 설계와 admission을 분리한다.
3. public/hidden mutation catalog: relation별 결함 mechanism과 비동치 증명 기록.
4. frozen 20-def probe manifest와 frozen 145 real-corpus manifest.
5. CubiCasa split manifest와 FloorPlanCAD 사용권 상태.
6. 후보 adapter manifest: threshold, config, model hash, stochastic seed, 출력 단위.

현 S/F/M 합성팩은 B1 KS 0.5792, TV 0.265로 FAIL했고 LINE/LWPOLYLINE/INSERT 3종뿐이라는 실측이므로, 이를 정식 admission truth로 그대로 쓰지 않는다. S팩은 음성이 없어 precision이 공허하다는 실측도 S-A sentinel이 별도 음성 family를 가져야 하는 이유다.

### 4.2 로컬 CPU 계획

기본 실행은 로컬 CPU이며 definition 단위 embarrassingly parallel이다. `fast_score`를 원본·follow-up 모두에 쓰고, 각 worker는 도면 하나의 spatial index와 후보 출력을 소유한다. 64GB RAM에서 최대 412,775 선분 정의를 동시에 여러 개 복제하면 메모리 압박과 quadratic pair 폭발이 날 수 있으므로 다음을 지킨다.

- worker 수는 고정 상수가 아니라 preflight에서 단일 최대 도면 peak RSS를 측정한 뒤 메모리 상한으로 결정한다.
- spatial bin/R-tree 또는 기존 fast candidate index를 재사용하고 전 선분쌍 `O(n²)` 열거를 금지한다.
- 대형 도면은 별도 large-job queue에서 단독 또는 저동시성으로 실행한다.
- 변환 IR 전체 복제 대신 immutable geometry와 transformed view를 우선한다.
- timeout/OOM은 relation fail로 위장하지 않고 `EXECUTION_FAILURE`로 분리하되 후보 승격은 차단한다.

cheapest probe 예산은 패킷대로 1일, 로컬 CPU, GPU 0이다. 전체 battery 구현 예산은 프리레그 추정으로 7~10 개발일, admitted 관계의 145 도면 실행은 preflight 후 wall-clock 상한을 봉인한다. 이는 관측 완료시간 주장이 아니라 계획값이다.

### 4.3 GPU와 DGX 분리

벡터 관계 생성·fast_score·arrangement·mutation admission은 GPU를 쓰지 않는다. FloorPlanCAD/VLM 후보 자체 추론이 필요할 때만 RTX 5070 Ti 16GB를 후보 adapter 자원으로 사용하며, judge 계산과 모델 계산 시간을 분리 보고한다.

DGX Spark는 현재 unreachable이라는 실측 상태이고 P3에 필요하지 않다. 따라서 DGX 불통은 본 제안의 blocker가 아니다. 향후 DGX가 복구돼도 관계 정의·threshold를 바꾸지 않고, 단지 후보 추론 worker로만 추가한다. DGX 결과만 다른 tolerance를 받지 않는다.

### 4.4 증거 산출물 계약

실제 구현 시 각 run은 다음을 남겨야 한다: frozen prereg manifest, 원본/follow-up provenance, 후보 config, relation numerator/denominator/NA, witness handles, sentinel 결과, mutant kill matrix, relation correlation matrix, runtime/resource log, 실패 사유. 프로그램 원칙에 따라 요약 xlsx는 의무이며 `evidence_grid`에 relation별 sheet와 raw witness link를 붙인다. 본 도시에 작성 단계에서는 패킷 계약상 지정 markdown 한 파일 외 다른 파일을 만들지 않는다.

---

## 5. 구현 계획

### 5.1 제안 파일 골격

아래는 후속 구현의 제안 골격이며 실제 저장소 경로는 repo 확인 후 맞춘다.

```text
e2_eval/metamorphic/
  schema.py          # CanonicalPrediction, TransformMap, RelationResult
  adapters.py        # v0/P1/P2/P4/P5 출력 정규화
  transforms.py      # rigid, mirror, unit, band perturbation
  injectors.py       # dimension/grid/leader synthetic distractors
  eligibility.py     # 후보 독립 적용 가능성 판정
  arrangement.py     # snap, planarize, chain/junction/face metrics
  relations.py       # MR-R/U/B/C/D assertion
  sentinels.py       # S-Z, S-A
  mutate_adapter.py  # 기존 L5 mutate() bridge
  admission.py       # reference-zero + hidden conviction gate
  runner.py          # def-level parallel execution and resume
  aggregate.py       # macro rates, coverage, correlation, abstain
  evidence.py        # evidence_grid/xlsx writer
configs/metamorphic/
  battery_v1.prereg.json
  mutants_public.json
  mutants_hidden.ref.json
tests/metamorphic/
  test_transform_roundtrip.py
  test_handle_provenance.py
  test_relation_soundness.py
  test_sentinel_kills.py
  test_invalid_transform_accounting.py
```

`mutants_hidden.ref.json`에는 실제 hidden 내용을 넣지 않고 접근 제어된 artifact id/hash만 둔다. relation 작성자가 hidden expected output을 본다면 conviction이 오염된다.

### 5.2 기존 도구 접속점

- `fast_score`: 모든 transform 뒤 feature를 새로 계산하는 scorer entrypoint로 감싼다. cached 원본 feature 재사용을 막는 assertion을 둔다.
- `cubicasa_ir`: 원 `segment_id/source_element_id`를 TransformMap provenance로 보존하고 px 축에서는 mm relation을 비활성화한다.
- `cubicasa_ml`: GBDT 등 모델의 score/threshold adapter, model/config hash, split guard를 제공한다.
- `evidence_grid`: 관계별 요약, mutant kill matrix, 145×relation binary matrix, witness entity를 xlsx에 쓴다.
- 기존 L5 `mutate()`: 함수 구현을 복제하지 않고 adapter로 호출하며 family·seed·expected mechanism을 manifest에 저장한다.

실제 signature나 디렉터리 구조는 패킷에 제시되지 않았으므로 위 이름이 이미 존재한다고 가정하지 않는다. 구현 첫 반나절에 entrypoint contract를 읽고 adapter boundary만 확정한다.

### 5.3 구현 순서와 예상 규모

1. canonical schema, handle provenance, rigid round-trip, v0 adapter.
2. MR-R과 MR-D, S-Z/S-A, 20-def runner, raw evidence.
3. PR-1 generator 연결 및 relation soundness tests.
4. mutate adapter와 public/hidden conviction pipeline.
5. MR-U/MR-B, applicability accounting.
6. MR-C arrangement와 scope tagging.
7. CubiCasa/raster adapters, correlation/abstain, evidence xlsx.
8. prereg freeze rehearsal 후 실제 후보 채점.

프리레그 개발량은 핵심 probe 약 1일, 정식 vector battery 추가 4~6일, raster adapter·evidence hardening 2~3일로 추정한다. 기존 entrypoint 상태에 따라 달라지는 계획값이며 완료 실측이 아니다. 코드량보다 provenance와 invalid/NA 회계, hidden mutation 분리가 더 큰 위험이다.

### 5.4 필수 자동검사

- 변환 후 inverse-transform하면 원 IR과 허용오차 내 동일하다.
- handle map은 one-to-one이며 삭제/분할은 명시적 multimap이다.
- 후보 결과와 무관하게 eligibility가 동일하다.
- invalid transform을 pass로 세지 않는다.
- constant-zero와 constant-one 뮤턴트를 sentinel이 반드시 죽인다.
- reference oracle은 모든 admitted relation에서 정확히 0 위반이다.
- hidden mutant 결과를 보기 전 manifest hash가 고정된다.
- test split은 run token 한 번만 발급되고 재실행은 인프라 실패 사유가 있는 동일 artifact replay만 허용한다.
- xlsx summary와 raw JSON numerator/denominator가 일치한다.

---

## 6. 실험 셀 정의

아래 합격선은 모두 **실행 전 봉인할 제안값**이다. 실측값처럼 읽어서는 안 된다. seed는 generator seed, mutation seed, 후보 seed를 서로 다른 namespace로 관리한다.

### C0 — PR-1 생성기·truth 자격 셀

- **가설**: wall/non-wall membership, mixed entities, chain/junction, open/closed scope를 construction으로 아는 합성 IR을 만들 수 있고, fidelity gate를 통과한다.
- **지표**: generator schema completeness, truth self-consistency, S/F/M 현상 coverage, B1 fidelity 지표, hidden family 분리 여부.
- **제안 합격선**: 패널 PR-1/T2가 요구한 fidelity gate 통과와 truth self-consistency 오류 0. 구체 B1 threshold는 PR-1 프리레그에서 정하며 P3 결과로 조정하지 않는다.
- **킬 조건**: 벽 생성 truth가 없거나 fidelity FAIL이 지속되면 정식 P3 admission·후보 랭킹을 중단한다. micro-fixture smoke test만 남긴다.
- **예산**: P3 자체 예산 밖의 프로그램 선결. 로컬 CPU.
- **시드 계획**: dev/hidden generator seed와 phenomenon family를 완전 분리; hidden은 relation author가 보지 않는다.

### C1 — Relation soundness 셀

- **가설**: MR-R/U/B/C/D의 applicability 조건 안에서는 correct-by-construction reference oracle이 위반하지 않는다.
- **지표**: relation별 reference violation numerator/denominator, invalid/NA 사유, geometry round-trip 오차.
- **제안 합격선**: 각 관계 reference 위반 0%. invalid가 특정 family에 집중되면 coverage 결함으로 별도 실패 처리한다.
- **킬 조건**: 의미 보존을 논증할 수 없거나 reference가 한 번이라도 위반한 관계는 배터리에서 제거한다. 제거 후 관계가 2개 미만이면 P3 전체를 판별기 후보로 보류한다.
- **예산**: 로컬 CPU 0.5일 제안.
- **시드 계획**: 고정 dev seed + 미접촉 hidden seed. 경계값은 random과 별도 deterministic fixture로 전수한다.

### C2 — Mutation conviction admission 셀

- **가설**: sound relation은 자신이 겨냥한 실제 결함 mechanism의 비동치 뮤턴트를 높은 비율로 죽인다.
- **지표**: relation×mutant kill matrix, hidden conviction, equivalent/invalid 사유, mechanism-family coverage.
- **제안 합격선**: 관계별 hidden conviction ≥95%, reference 위반 0%, hidden 비동치 mutant 최소 20개 제안.
- **킬 조건**: 95% 미만인 관계는 불합격. 아무 뮤턴트도 죽이지 못하는 관계는 카드 규칙 2에 따라 즉시 폐기한다. 뮤턴트 복제로 비율을 올린 흔적이 있으면 admission 전체 무효다.
- **예산**: 로컬 CPU 0.5~1일 제안.
- **시드 계획**: family별 균형 seed, public/hidden 분리. stochastic 후보 seed는 conviction 분모와 별개다.

### C3 — Cheapest probe: 회전 + distractor + sentinels

- **가설**: 현 v0와 비교 후보에서 회전 plumbing 오류 또는 wall-like distractor 민감도를 하루 안에 관찰할 수 있고, 0/전벽 adapter를 확실히 죽일 수 있다.
- **지표**: 20 def의 rotation macro failures, injected-handle FP, original-stability failures, S-Z/S-A, runtime, provenance 오류.
- **제안 합격선**: runner/handle map 오류 0, sentinels가 constant-zero/one을 모두 kill, reference fixture 위반 0. 후보 승격선은 이 smoke cell에서 선언하지 않는다.
- **킬 조건**: transform provenance가 불안정하거나 distractor safe patch를 만들 수 없어 유효 trial이 거의 없으면 probe 설계를 폐기·수정한다. 후보의 회전 위반은 engineering finding이지만 C0~C2 전에는 프로그램급 후보 kill로 승격하지 않는다.
- **예산**: 패킷대로 1일, 로컬 CPU, GPU 0.
- **시드 계획**: 20-def manifest와 transform/injection seed를 실행 전 고정; 결과를 보고 definition 교체 금지.

### C4 — 145 실코퍼스 공통 후보 gate

- **가설**: admitted battery가 P1/P2/P4/P5의 label-free failure profile을 분리한다.
- **지표**: 관계별 `V_r`, exact numerator/denominator, coverage, hard rotation failures, sentinel status, runtime, 후보×관계 violation matrix.
- **제안 합격선**: sentinels 통과, 회전 0 위반, 나머지 admitted invariant 관계 `V_r≤1%`. 145개가 모두 유효한 관계는 도면 단위 최대 1건 실패만 허용된다. anti/arrangement는 relation별 prereg scope에 따라 hard 또는 diagnostic으로 분리한다.
- **킬 조건**: 후보는 회전 한 건 위반 시 silver와 무관하게 kill. 반대로 전 후보가 같은 관계를 대량 위반하지만 synthetic C1/C2를 통과했다면 후보들을 일괄 kill하지 않고 relation validity 또는 domain-gap 보조가정을 kill한다. 전체 배터리가 아무 후보도 구분하지 못하면 판별력 0으로 큐에서 제거한다.
- **예산**: 로컬 CPU, definition 병렬. wall-clock 상한은 최대 도면 preflight 뒤 봉인. GPU/DGX 0.
- **시드 계획**: 후보별 동일 transform seed. stochastic 후보는 canonical seed + 사전 지정 반복 seed를 모두 보고하며 best-seed 선택 금지.

### C5 — Thickness·arrangement scope 셀

- **가설**: 두께 band 내부 perturbation은 membership을 보존하고, closed-partition scope의 올바른 wall set은 chain/junction/face 구조에 참여한다.
- **지표**: band stratum별 MR-B violation, invalid collision rate, chain/junction/face support, open-vs-closed scope 차이.
- **제안 합격선**: MR-B reference 0 위반과 conviction ≥95%. MR-C는 `closed_partition`에서만 같은 admission 기준을 만족해야 hard relation이 된다.
- **킬 조건**: open-plan에서 과강하거나 scope tag가 후보 출력에 의존하면 MR-C hard gate를 kill하고 soft diagnostic만 유지한다. MR-B eligibility가 실제 도면에서 지나치게 낮으면 전체 후보 pass로 오인하지 않고 relation을 보류한다.
- **예산**: 로컬 CPU 1~2일 구현·실행 제안.
- **시드 계획**: band 하/중/상과 경계 fixture를 층화, open/closed family 분리.

### C6 — CubiCasa val 개발·test 단발 / raster 전이 셀

- **가설**: SEG-IR와 raster 후보에서도 라벨 점수와 MR robustness가 서로 다른 정보를 주며, adapter 자체의 좌표계 오류를 잡을 수 있다.
- **지표**: val/test F1 등 기존 공식 metric, relation profile, label error×MR violation 교차표, raster inverse-warp consistency, shuffle control.
- **제안 합격선**: 배터리 threshold는 synthetic-only로 이미 봉인; test는 최종 후보·threshold당 한 번. test 실행 성공 전 결과 미열람 정책과 xlsx 증거 완비.
- **킬 조건**: raster interpolation artifact가 mutant보다 더 많이 relation을 죽이거나 exact projection이 없으면 raster 결과를 vector gate에서 분리한다. counsel 미확인 시 외부셋 학습/배포성 주장은 보류한다.
- **예산**: vector는 로컬 CPU; raster/VLM 후보 추론에만 RTX 5070 Ti 16GB. DGX 0.
- **시드 계획**: val 개발 seed와 test canonical seed 분리. test 재튜닝·두 번째 선택 실행 금지.

### C7 — 대리 독립성·관계 상관·abstain 셀

- **가설**: metamorphic 위반은 synthetic/external-label/silver와 완전히 같은 prior의 복제가 아니며, 관계별 실패 pattern도 적어도 일부 비중복 정보를 가진다.
- **지표**: 동일 def에서 synthetic/external/silver/MR의 3원·4원 불일치 구조, φ/Jaccard correlation, violation clustering, silver 어휘가문별 결과.
- **제안 합격선**: 단일 “독립성 점수”를 사후 발명하지 않는다. 관계별 contingency table과 cluster를 의무 공개하고, 완전 중복 관계는 한 증거 family로 축약한다.
- **킬 조건**: MR이 외부/silver와 사실상 같은 평행이중선 prior만 복제하고 추가 disagreement를 설명하지 못하면 “독립 공용 심판” 주장을 kill한다. 모든 후보가 동률이면 A1 abstain을 발동한다.
- **예산**: 기존 후보 출력 재사용, 로컬 CPU 반나절 제안.
- **시드 계획**: C4/C6 frozen 결과만 사용하며 새 seed로 유리한 불일치 사례를 탐색하지 않는다.

---

## 7. Red team 티켓 응답

패널 전문에 세부 설명이 실제로 드러난 티켓만 해소 대상으로 삼는다. 번호만 있고 내용이 없는 T8~T33의 세부를 추측하지 않는다.

| 티켓/공격 | P3에 대한 영향 | 응답과 잔여 위험 |
|---|---|---|
| **T1 / 공격 A — 4대리 독립성** | metamorphic도 평행 이중선 prior를 공유하면 독립 증거가 아니다. | C7에서 동일 def의 disagreement와 관계 상관을 보고하고 CL-E와 병합한다. 독립성을 전제하지 않으며 완전 중복이면 증거 family를 축약한다. 아직 실측 전이므로 OPEN 수용이다. |
| **T2 / PR-1 — 벽 합성 생성기 부재·충실도** | relation admission의 truth source가 현재 없다. 현 합성팩 B1 FAIL도 명시돼 있다. | C0를 하드 선결로 둔다. 20-def probe는 smoke test일 뿐 admission/pass 근거가 아니다. PR-1이 닫히지 않으면 P3 정식 랭킹을 중단한다. OPEN 수용이며 가장 직접적인 blocker다. |
| **T7 / 공격 F — 0벽/전벽 퇴행** | violation-rate-only gate가 constant predictor를 통과시킨다. | S-Z 양성 recall sentinel, S-A 음성 FP sentinel을 relation equality와 별도 하드 게이트로 추가했다. hidden constant-zero/one mutants를 반드시 kill해야 admission된다. 설계상 해소, 구현 증거 전까지 OPEN이다. |
| **T5 / PR-3 — 외부셋 권리** | label-free 평가도 자산 사용권 문제를 자동 해소하지 않는다. | CubiCasa/FloorPlanCAD 학습·배포성 주장은 counsel 서면 확인 전 보류한다. 로컬 설계와 synthetic admission은 분리 가능하다. OPEN 수용이다. |
| **T6 / 공격 E — 평가 단위 혼선** | pair/assembly를 per-handle 분류와 섞으면 후보 계열 비교가 왜곡된다. | primary를 `wall_member(h)`로 고정하고 pair와 arrangement를 별도 산출물/관계로 격리했다. P4 assembly는 두 출력을 모두 내야 한다. 구현 schema 확인 전까지 OPEN이다. |
| **T17 / CL-E — 동일-def 불일치 구조** | 전이 성능만으로 대리 독립성을 주장할 수 없다. | C7에서 동일 def contingency와 violation vector를 산출해 CL-E 입력으로 넘긴다. P3 단독으로 인과 독립성을 증명하지 않는다. |
| **T3/T4/T8 / CL-A 선결** | 패널은 E1 정렬 artifact·Ornith 원시 증거 등을 고가 실험 전 선결로 올렸다. T8의 상세는 패킷에 없다. | P3는 CL-A를 해결했다고 주장하지 않는다. 20-def engineering probe는 병행 가능하지만 프로그램급 후보 랭킹 해석은 CL-A 결과와 대조한다. 미제공 T8 내용을 발명하지 않고 OPEN으로 유지한다. |
| **T34 — 인용 R-lane 미실행** | 문헌 이름이 실제 프로그램 증거처럼 오용될 위험이 있다. | 1절 문헌은 방법론 계보일 뿐 `experiment_executed`가 아니다. 정확 판본이 불확실한 것은 `요검증`으로 표시했다. load-bearing prereg에는 서지 검증 후 넣고, 프로그램 수치는 다이제스트만 인용한다. |

추가로 패널의 kill 규칙을 다음처럼 명문화한다.

- synthetic 통과 뒤 전 후보가 실코퍼스에서 같은 관계를 대량 위반하면, 즉시 모든 후보를 죽이지 않는다. 먼저 변환이 실제 의미를 보존하는지, 합성 domain이 관계 적용조건을 빠뜨렸는지 본다. 관계 또는 synthetic↔real 보조가정의 kill이다.
- 후보 하나가 admitted 회전 hard relation을 위반하면 silver/label 점수와 무관하게 후보 kill이다.
- 아무 후보도 죽이지 못하고 violation profile도 동일한 relation row는 카드 규칙 2에 따라 폐기한다.
- invalid/NA를 pass로 세거나 coverage denominator를 숨기면 해당 run 전체가 무효다.

---

## 8. 인접 제안과의 관계 및 이 제안의 사망 조건

### 8.1 병합 가능 지점

- **CL-C / PR-1**: P3 admission에 필요한 correct-by-construction wall truth, hidden mutation family, scope tag를 공급한다. P3는 이를 대체하지 못한다.
- **CL-E**: P3의 후보×def×relation violation tensor를 synthetic/external/silver 교차요인 메타실험의 네 번째 평가축으로 넘긴다. 같은 코드로 T1/T17을 해소하는 것이 합리적이다.
- **doe P5·calibration M**: rigid/scale/unit/explode/layer-rename 관계 정의와 prereg manifest를 하나로 합칠 수 있다. 중복 구현을 별 증거로 세지 않는다.
- **CL-A**: 실제 divergent definition과 정렬 artifact를 먼저 정리해 C3/C4 manifest가 계측 산물이 되지 않게 한다.
- **CL-B/P1, CL-F/P2, CL-H/P4, CL-G/P5**: 모두 동일 adapter contract로 P3의 심판 대상이 된다. P3 결과를 각 후보의 학습 reward로 재사용하면 평가 leakage이므로, 학습용 relation과 미접촉 평가 relation/version을 분리한다.
- **R16 arrangement 계열/CL-J**: P3의 MR-C는 centerline→partition 일관성 진단이고, CL-J의 room/face-first 표현은 대안 생성 메커니즘이다. 같은 arrangement engine을 공유할 수 있으나 방향 가설은 평균내지 않고 별 셀로 유지한다.

### 8.2 차별점

P1/P2/P4/P5는 벽을 **어떻게 예측할지**에 대한 후보이고, P3는 그 예측이 의미 보존 변환과 construction-known anti-relation을 **얼마나 지키는지** 판정한다. 외부 라벨은 정답과의 일치를 보지만 P3는 counterfactual consistency를 본다. silver는 다른 판정자의 의견이지만 P3는 사전에 고정된 관계다. 합성 정확도는 생성 분포 안의 정답 일치지만 P3 admission은 관계 자체가 오류를 죽일 힘이 있는지까지 mutation으로 시험한다.

P3는 다음을 주장하지 않는다.

- metamorphic pass가 높은 wall F1을 보장한다.
- 여러 관계가 통계적으로 독립이다.
- 단위 불변 pass가 미지 px 축척의 물리 두께 일반화를 보장한다.
- arrangement closure가 모든 오픈플랜에서 참이다.
- label-free라는 이유로 licensing/counsel gate가 사라진다.

### 8.3 이 제안이 죽어야 하는 조건

다음 중 하나면 관계 일부가 아니라 P3의 “공용 심판기” 주장을 죽이거나 PARK한다.

1. PR-1 fidelity-qualified wall generator를 만들 수 없어 soundness/conviction을 자격 심사할 truth source가 끝내 없다.
2. reference 위반 0%와 hidden mutant conviction 95%를 동시에 만족하는 유용한 관계를 최소 2개 확보하지 못한다.
3. S-Z/S-A가 constant-zero/constant-one 또는 동등한 퇴행을 안정적으로 죽이지 못한다.
4. admitted 관계가 모든 후보에서 동률이고 어떤 후보·뮤턴트 failure family도 구분하지 못한다. 이때 판별력 0인 행/배터리는 카드 규칙 2에 따라 큐에서 제거한다.
5. 실도면에서 의미를 실제로 바꾸는 transform, raster interpolation, handle remapping 오류가 candidate defect보다 relation failure를 더 지배하고 이를 applicability로 객관적으로 분리할 수 없다.
6. 관계 결과가 synthetic/external/silver와 같은 평행이중선 prior의 완전한 복제여서 독립 공용 심판이라는 추가 가치가 없다.
7. 후보 실행 전에 freeze한 145 manifest, relation manifest, threshold, seed, mutant hiddenness를 증명할 수 없다.
8. 최대 도면에서 `O(n²)` 후보 폭발을 피하지 못해 프리레그된 로컬 실행 상한 안에 증거 완결 run을 만들 수 없다.
9. untouched CubiCasa test에서 MR pass 후보가 라벨상 반복적으로 열등하다는 결과가 나오고, MR이 유효한 robustness trade-off를 설명하지 못한다. 이 경우 MR을 truth 대체물로 쓰는 주장을 죽이고 secondary diagnostic으로 강등한다.

반대로 P3가 살아남기 위한 최소 증거는 간단하다. faithful synthetic truth 위에서 reference 0 위반과 hidden conviction 95%를 통과한 관계가 있고, sentinels가 공허한 예측을 죽이며, frozen 145 실코퍼스에서 적어도 하나의 후보 family를 재현 가능하게 구분하고, 그 차이가 relation/adapter artifact가 아님을 witness 수준으로 설명해야 한다. 그 전까지 상태는 `candidate`, `ready`나 `PASS`가 아니다.

DOSSIER_COMPLETE: platt_P3
