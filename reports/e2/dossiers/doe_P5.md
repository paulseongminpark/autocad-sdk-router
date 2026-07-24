# doe_P5 — METAMORPHIC INVARIANCE BATTERY 심층 도시에

> 제안 상태: **UNRUN**. 이 문서는 실행 계획이며 새 측정을 주장하지 않는다. 아래에서 “실측”이라고 부르는 값은 패킷의 2026-07-18 다이제스트에 있는 값뿐이다. 그 밖의 임계값·시드·시간 상한은 모두 **새 프리레그 제안값**이고 관측값이 아니다.

P5의 산출물은 벽 정확도를 대신하는 점수가 아니라, 정확도를 주장하기 전에 통과해야 하는 무라벨 필요조건 `R-META`이다. 같은 논리 엔티티의 벽/비벽 판정이 의미보존 CAD 변환 후 뒤집히면 그 탐지기는 자기 입력 표현에 의존한다. 반대로 위반이 없다는 사실은 정확성을 보장하지 않는다. 따라서 P5의 정당한 위치는 `R-SYN`/`R-SILVER` 및 외부 사람 라벨 평가 앞의 **선별 게이트**이며, 독립 정확도 표처럼 합산하거나 “투표”해서는 안 된다.

## 1. 이론적 근거·선행연구

### 1.1 방법론 계보

1. **Metamorphic Testing(MT).** 정답 오라클을 직접 만들기 어려운 프로그램에서 원 입력 `x`와 변환 입력 `T(x)`의 출력 사이에 미리 아는 관계 `M(f(x), f(T(x)))`를 둔다. T. Y. Chen 계열의 초기 metamorphic testing 연구와 Segura et al.의 survey가 이 계보다. 정확한 초판 연도·서지 페이지는 구현 PR에서 **요검증**하되, 여기서 차용하는 원리는 명확하다: 개별 정답 대신 입력-출력 관계를 오라클로 쓴다.
2. **Property-based testing.** QuickCheck(Claessen & Hughes)처럼 입력 생성기와 반드시 성립할 성질을 분리한다. P5에서는 `{변환 카탈로그, 파라미터 생성기, 유효성 인증기}`가 generator이고, logical entity 판정 보존이 property다. 단순 무작위 fuzzing과 달리 각 변환의 기대 관계가 봉인된다.
3. **Mutation testing.** DeMillo–Lipton–Sayward의 program mutation 계보와 후속 mutation-testing survey가 제공하는 핵심은 “검사기가 실제 결함을 죽이는가”를 결함 주입으로 확인하는 것이다. 현재 `synthetic_truth.py`의 correct-by-construction 문서에 정확히 한 위반을 주입하는 패턴을 벽 관계에 옮긴다. 깨끗한 쌍은 위반 0, 한 엔티티를 뒤집은 mutant는 정확히 그 엔티티를 검출해야 한다.
4. **불변성·등변성.** 군 작용 관점에서 분류 라벨은 변환에 불변이고, 좌표를 가진 축·두께 출력은 변환에 등변이어야 한다. Cohen & Welling의 group-equivariant CNN 계보는 모델 설계 쪽의 대표 예지만, P5는 모델이 그러한 구조를 가졌다고 가정하지 않고 외부 행동으로 검사한다.
5. **ML behavioral testing.** DeepXplore/DeepTest와 CheckList(Ribeiro et al.) 계열은 모델의 평균 정확도만 보지 않고 행동 기대조건을 시험한다. P5는 특히 CAD의 단위, 블록, 레이어, 좌표 표현이라는 도메인 고유 행동 조건을 고정한다. 세부 서지정보는 **요검증**이며, 해당 연구의 성능 수치를 이 문서의 근거로 사용하지 않는다.

### 1.2 왜 벽 탐지에 필요한가

벽 의미는 원점, 도면 방위, mm와 m 중 어느 단위를 썼는지, 블록을 유지했는지 explode했는지, 레이어 문자열이 무엇인지와 동일하지 않다. 따라서 이 표현 변경만으로 같은 논리 선분의 벽 판정이 바뀐다면 모델은 벽 의미가 아니라 표현 우연성을 사용한다. 다이제스트의 부분 실측에서 강체·단위 팔은 1.0이었지만 scale 팔은 0.7624로 FAIL이었다. 이것은 P5 전체가 이미 실행됐다는 뜻이 아니다. 당시 결과는 7변환×4계열 완전요인, logical-entity mapping, detector-family 상호작용, sentinel 자격요건을 갖춘 28셀 결과가 아니므로 **동기 부여용 부분 증거**로만 쓴다.

P5가 잡는 오류는 두 층이다.

- 파이프라인 오류: `$INSUNITS`와 좌표를 불일치하게 읽기, INSERT transform을 누락하기, explode 뒤 handle correspondence를 잃기, 큰 절대좌표에서 부동소수점이 흔들리기.
- 모델 오류: absolute coordinate, layer token, raster crop, 고정 mm gap band 등에 과의존하기.

그러나 상수 0벽 탐지기, 전벽 탐지기, 또는 일정하지만 엉뚱한 비상수 탐지기도 관계를 만족할 수 있다. panel attack F가 정확히 이 점을 지적했다. 0벽/전벽 sentinel과 truth-bearing recall floor는 자명한 해를 제외할 뿐이며, 여전히 충분조건을 만들지는 못한다.

## 2. 알고리즘 정확 스펙

### 2.1 입출력 계약과 논리 엔티티

입력은 다음 네 묶음이다.

- `D`: 원본 DXF 또는 동결된 `SEG-IR` 도면.
- `b`: detector family와 동결 artifact/config를 가리키는 `DetectorManifest`.
- `k`: 7개 변환 중 하나.
- `p`: 그 변환의 사전등록 파라미터.

출력은 drawing×transform×parameter×detector 단위의 원시 행과 28셀 집계다. 각 탐지기 adapter는 공통 형식으로 정규화한다.

```text
Prediction := {
  drawing_id,
  detector_id,
  threshold_id,
  per_entity: {
    logical_entity_id: {
      score: float | null,
      wall: bool,
      axis: [[x,y],[x,y]] | null,
      thickness: float | null
    }
  },
  runtime_manifest,
  stderr_digest
}
```

원시 DXF handle은 논리 엔티티 ID가 아니다. 같은 block definition을 여러 번 INSERT하면 동일 source handle이 여러 world-space occurrence를 가리킬 수 있고, polyline 한 handle에서 여러 edge가 나온다. 다음 키를 변환 전에 봉인한다.

```text
LID = SHA256(drawing_id, source_handle_or_sid, insert_path, edge_index, occurrence_index)
```

`insert_path`는 최상위 INSERT부터 leaf까지의 occurrence 경로다. translate/rotate/scale/unit/layer-rename/coord-jitter는 LID를 보존한다. explode는 `LID -> exploded_handle`의 occurrence-level 전단사 mapping을 낸다. 하나의 source handle을 하나의 new handle에만 연결하는 현재 방식은 반복 INSERT에서 마지막 occurrence로 덮어쓸 수 있으므로 본 실험의 identity oracle로 사용할 수 없다. mapping 누락·중복·추가 엔티티는 판정 flip과 별도의 transform-integrity 오류로 기록하고, 탐지기 비교에서는 누락 LID를 위반 1로 센다.

### 2.2 변환 카탈로그 `T-META v1`

아래 값들은 전부 **프리레그 제안값**이다. `D`는 원 도면 bbox diagonal, `c`는 bbox centroid다. 파라미터는 실행 전에 JSON으로 봉인하고 결과를 본 뒤 바꾸지 않는다.

| A: transform | 파라미터 표본 | binary wall 관계 | 구조/치수 관계 | 변환 유효성 인증 |
|---|---|---|---|---|
| `translate` | `(0.1D,-0.2D)`, `(10D,10D)`, `(-10D,3D)` | invariant | axis에 같은 벡터를 더함; thickness 동일 | 역변환 뒤 endpoint·topology 동일 |
| `rotate` | `17°`, `90°`, `173°`, 중심 `c` | invariant | axis=`Rθ(axis)`; thickness 동일 | 역회전 뒤 endpoint·topology 동일 |
| `uniform-scale` | `0.5`, `2`, `10`, 중심 `c` | invariant | axis=`S_s(axis)`, thickness=`|s|t` | 역축척 뒤 geometry 동일, 0/음수 금지 |
| `unit-change` | `mm→m`, `m→mm` | invariant | raw 좌표·raw thickness는 각각 `0.001` 또는 `1000` 배; canonical mm 값 동일 | 좌표·`$INSUNITS`·`scale_mm_per_unit`의 물리량 일치 |
| `block-explode` | full recursive explode 1종 | invariant | world geometry 동일, occurrence-level LID mapping | INSERT fixpoint, mapping 전단사, world topology 동일 |
| `layer-rename` | anonymize 1회, bijective shuffle seed `11`, `47` | invariant | geometry·LID 동일, layer map만 전단사 | layer map 전단사, geometry hash 동일 |
| `coord-jitter` | normalized quantization `q/D ∈ {1e-9,1e-7,1e-5}`, seed `101`,`211`,`307`을 일대일 배정 | invariant | certified tolerance 안에서 topology 동일 | shared-vertex equivalence class를 함께 이동; topology·band-margin 인증 |

mirror는 기존 모듈에 구현되어 있어도 이 카탈로그에 넣지 않는다. 패킷이 허용한 7개 밖의 관계를 발명하지 않는다는 abstention을 지킨다.

`coord-jitter`는 임의 endpoint noise가 아니다. 먼저 snap으로 같은 논리 vertex인 점들을 equivalence class로 묶고, LID와 seed의 해시로 정한 같은 deterministic dither를 class 전체에 적용한 뒤 정규화 좌표를 양자화한다. 다음 중 하나라도 깨지면 그 pair는 `INVALID_TRANSFORM`이고 R-META 분모에 넣지 않는다: segment가 0길이가 됨, 교차/접속 incidence가 바뀜, 평행쌍의 변위가 허용 인증 경계를 넘음, detector decision boundary와의 feature margin이 jitter 상한보다 작음. 마지막 조건은 detector 결과가 아니라 입력 feature와 동결 config만으로 판정한다. 따라서 relation을 통과시키기 위해 결과를 보고 표본을 제거하지 않는다.

scale과 unit은 **binary 판정에는 불변**, 좌표가 있는 출력에는 **등변**이다. “등변이므로 label flip을 허용”하지 않는다. 비교기가 after 출력에 역변환을 적용한 뒤 canonical 좌표계에서 비교한다.

### 2.3 반응, 손실, 집계

탐지기 `b`, 도면 `d`, 변환 `k`, 파라미터 `p`에 대해 base LID 집합을 `L_d`라 하자. 동결된 family별 threshold `τ_b`로 `ŷ=1[score≥τ_b]`를 만든다.

```math
v_{d,k,p,b}=\frac{1}{|L_d|}\sum_{\ell\in L_d}
  1\left[\hat y_b(D_d,\ell)\ne
  \hat y_b(T_{k,p}(D_d),m_{k,p}(\ell))\right].
```

after에서 mapping된 LID가 사라지면 해당 항은 1이다. extra LID는 transform-integrity 오류로 별도 계수하며, clean mapping을 고칠 때까지 셀을 해석하지 않는다. 원 도면에 엔티티가 하나도 없으면 vacuous pass로 처리하지 않고 invalid drawing으로 격리한다.

셀의 주 반응 `R-META_{k,b}`는 도면별 위반율을 먼저 parameter 표본에 대해 동일 가중 평균하고, 다시 40개 도면에 동일 가중 평균한 **drawing-macro violation rate**다. 최대 정의가 412,775 선분이라는 실측 때문에 entity-micro 평균만 쓰면 한 도면이 전체 셀을 지배한다. `micro_violation`, drawing별 min/median/max, flip LID 목록은 진단으로 함께 내지만 게이트는 macro에만 적용한다.

사전 봉인 밴드는 패킷 그대로다.

- `PASS`: `R-META ≤ 0.02`
- `INCONCLUSIVE`: `0.02 < R-META ≤ 0.10`
- `FAIL`: `R-META > 0.10`

경계 0.02가 중복되지 않게 위와 같이 해석을 고정한다. deterministic response에 p-value, 표준오차, 임의효과 모델, “seed 간 분산”을 붙이지 않는다. 이는 40개 도면과 봉인된 파라미터 population에 대한 정확한 기술통계다.

보조 진단은 다음과 같다.

- `score_drift = mean |s_before-s_after|`: label이 유지돼도 margin이 불안정한지 본다. 게이트 아님.
- `geom_residual`: after axis를 역변환한 뒤 base axis와의 endpoint/Hausdorff 잔차 및 thickness residual. 출력이 없는 family에는 `NA`.
- `coverage_loss`, `extra_entity_rate`, `mapping_collision_count`: transform/parser 오류와 detector omission을 분리한다.
- `zero_flag`, `all_flag`: 자명한 탐지기 경고.
- `repeat_checksum_mismatch`: 같은 입력을 같은 artifact로 두 번 실행했을 때 bytes 또는 정규화 prediction checksum이 다른 실행 무결성 실패.

4개 family의 sentinel 자격조건은 full battery 전에 별도 truth-bearing val 자료에서 평가한다. **새 프리레그 제안값**으로 positive sentinel recall `≥0.20`을 요구한다. 이는 정확도 합격선이 아니라 항상-negative 해를 죽이기 위한 낮은 위생선이며, 다이제스트의 classical-ML recall 0.370보다 낮게 두어 P5가 정확도 랭킹을 대신하지 않도록 한 것이다. near-all prediction과 zero prediction fixture도 반드시 잡아야 한다. sentinel 불합격 family는 28셀 원시 R-META는 계산해도 “가장 자기일관적 family” 랭킹에서 제외한다.

### 2.4 완전요인 효과와 상호작용

`A(7)×B(4)`의 28셀을 모두 실행한다. 결측 셀을 0이나 PASS로 대체하지 않는다. 모든 셀이 유효할 때만 다음 기술적 분해를 낸다.

```math
A_a=\bar r_{a\cdot}-\bar r_{\cdot\cdot},\quad
B_b=\bar r_{\cdot b}-\bar r_{\cdot\cdot},\quad
(AB)_{ab}=r_{ab}-\bar r_{a\cdot}-\bar r_{\cdot b}+\bar r_{\cdot\cdot}.
```

fraction을 쓰지 않으므로 A, B, A×B에 alias가 없다. interaction이 크면 “어느 family가 낫다”는 main-effect 문장을 금지하고, 취약 transform별로만 결론낸다. family 전체 verdict는 sentinel 자격을 얻은 뒤 7셀 모두 PASS여야 `PASS`, 하나라도 FAIL이면 `FAIL`, FAIL은 없지만 INCONCLUSIVE가 있으면 `INCONCLUSIVE`다.

### 2.5 의사코드

```python
catalog = seal_catalog("T-META.v1.json")
drawings = stratified_sample(archive_145, n=40, seed=20260718,
                             block="L-FIRM", label_blind=True)
manifests = freeze_detector_manifests(
    ["deterministic_v0", "classical_ml", "gnn", "vlm"]
)

for d in drawings:
    base_cad, base_ir, lid_ledger = canonicalize_and_freeze(d)
    for relation in catalog:
        for p in relation.parameters:
            after_cad = relation.apply(base_cad, p, staging_only=True)
            pair = parse_pair_and_map(base_cad, after_cad, lid_ledger)
            cert = relation.validate(pair, p)
            if not cert.valid:
                emit("INVALID_TRANSFORM", cert)
                continue
            freeze_pair_ir_and_hashes(pair)

for b in manifests:
    assert sentinel_qualification(b) or mark_ineligible(b)
    for d in drawings:
        pred0 = cache_once(b, frozen_base_ir[d])
        assert_deterministic_checksum_or_fail(b, d, pred0)
        for k, p, pair in valid_pairs[d]:
            pred1 = infer(b, pair.after_ir, temperature=0_if_vlm)
            row = compare_on_lid(pred0, inverse_output(pred1, k, p), pair.map)
            emit_raw_row(row)

aggregate_macro_without_noise_model()
write_evidence_xlsx_and_machine_readable_manifest()
```

threshold, preprocessing, model weights, renderer, prompt, raster resolution, Graph-IR adjacency, feature scaler는 family manifest에 들어가며 P5 결과를 본 뒤 바꿀 수 없다. 바꾸면 새 method ID와 새 val cycle이다.

## 3. 벽 과업 적응 설계

### 3.1 공통 “시험지”와 family adapter

1. **deterministic(v0).** `evidence_grid.score`/`w1_real_defs.fast_score` 경로를 `DetectorAdapter`로 감싼다. 현재 `fast_score`는 reference loop의 per-handle 의미와 채널을 NumPy로 복제하는 접속점이다. proposal의 arm 이름 `deterministic(v0)`와 실제 파일의 detector 버전 표기가 섞이지 않도록 manifest에 `method_id`, Python 파일 SHA-256, config SHA-256, threshold를 넣는다. v0 artifact가 없으면 현재 v1을 몰래 대신 넣지 않고 `BLOCKED_ARTIFACT`로 기록한다.
2. **classical-ML.** `cubicasa_ml.py`가 만든 6특징 `(parallel, thickness, junction, log length, sin2θ, cos2θ)`을 동일한 frozen pair IR에서 추출한다. 현재 학습 코드가 val report는 쓰지만 inference용 model artifact를 영속화하지 않으므로 train split으로 fit한 HistGradientBoosting artifact와 feature schema를 저장하는 접속점이 추가돼야 한다. threshold는 val에서 한 번 봉인하며 R-META를 보고 조정하지 않는다.
3. **GNN.** SEG-IR를 node=LID segment, edge={endpoint adjacency, near-parallel candidate, block co-membership}인 Graph-IR로 변환한다. 모든 좌표 feature는 manifest가 정한 canonical normalization을 거치고 layer-name arm은 mask/encode 여부를 명시한다. base/after graph가 같은 LID 순서로 재정렬되지 않으면 비교를 중단한다. Graph adjacency 완전성 감사를 통과한 frozen model만 들어간다.
4. **VLM.** production rasterizer와 고정 prompt를 model artifact의 일부로 본다. wall mask/probability를 얻은 뒤 각 LID segment가 차지하는 canonical raster samples의 median을 per-entity score로 투영한다. after mask는 transform을 역적용해 같은 LID sample에 정렬한다. temperature 0, greedy decoding, 고정 renderer/crop/padding을 강제한다. 같은 입력 checksum이 달라지면 여러 번 평균하지 않고 `NONDETERMINISTIC_FAIL`로 낸다.

다이제스트에서 기하 v1의 CubiCasa val F1은 0.2358, GBDT는 0.517이었다. P5가 제공할 추가 가치는 F1의 직접 상승이 아니다. 높은 precision/낮은 recall의 classical model이 scale·unit·좌표표현에 일관적인지, 높은 recall/낮은 precision의 기하 detector가 긴 비벽 평행 구조를 일관되게 오판할 뿐인지 분리한다. 즉 “성능이 오른 모델”에 deployment hygiene를 추가하고, 어느 표현에서 그 향상이 붕괴하는지를 A×B로 찾는다.

### 3.2 세 데이터 축의 역할

**CubiCasa SEG-IR 벡터축.** `cubicasa_ir.py`의 train/val/test 분할을 보존한다. train은 학습, val은 threshold·sentinel 자격·adapter 개발에만 쓴다. test 400장은 method별 단발 때까지 읽지 않는다. CubiCasa는 layer가 중립이고 좌표가 px이며 도면별 물리축척이 미상이다. 따라서 translate/rotate/uniform-scale/coord-jitter의 SEG-IR 관계와 truth-bearing sentinel에는 쓸 수 있지만, `$INSUNITS`, block explode, 의미 있는 layer rename의 주 시험지가 아니다. 이 네 관계만으로 P5의 7관계 결과를 대체하지 않는다.

**FloorPlanCAD 래스터축.** 5,308장과 wall bbox/segmask는 VLM renderer·inverse-warp·mask comparator의 smoke/qualification에 쓴다. 벡터 SVG가 없으므로 exact logical CAD handle을 발명하지 않는다. block explode와 layer rename은 `NA`이고, 래스터만으로 얻은 결과는 28셀 R-META에 합치지 않는다. pixel→handle 역투영 exact harness를 합성에서 통과한 후에만 보조 자료로 쓴다.

**1.dwg 실도면축 및 145 아카이브.** primary 28셀은 145 아카이브에서 label-blind로 40장을 고른다. 선택은 segment-count 사분위×INSERT 존재 여부×unit metadata known/unknown을 가능한 한 균형화하고, firm을 `L-FIRM` 반복축으로 둔다. strata가 비면 임의 대체하지 않고 manifest에 부족을 기록한다. 1.dwg의 384개 도면정의는 CAD parser와 block mapping의 별도 real-world stress frame이다. 최대 412,775 선분 정의는 gate 평균에 몰래 넣어 지배시키지 않고 성능/메모리 stress cell로 따로 보고한다.

학습 family의 train 자료와 P5 평가 도면은 firm 단위로 분리한다. 변환된 같은 도면의 여러 parameter 표본은 새로운 독립 도면이 아니다. base prediction을 한 번 cache하고 모두 같은 block 안의 repeated conditions로 기록한다.

### 3.3 파이프라인과 detector를 분리한 두 판독값

block explode와 unit change는 parser까지 시험해야 의미가 있다. 그래서 한 transform pair에서 두 결과를 낸다.

- `R-META-PIPELINE`: 원 CAD→normalize/insert_expand/unit_anchor→family inference 전체를 재실행한 결과. 실제 배치 게이트의 primary다.
- `R-META-DETECTOR`: T-META oracle이 만든 base/after frozen SEG-IR를 family에 직접 넣은 결과. parser 실패인지 model 실패인지 국소화하는 진단이다.

두 값을 섞어 평균하지 않는다. pipeline이 FAIL하고 detector가 PASS면 normalize/unit/block mapping을 먼저 고친다. 둘 다 FAIL이면 표현 또는 model을 고친다. IR freeze는 변환 전에 parser를 생략한다는 뜻이 아니라, 변환·파싱·LID mapping이 인증된 pair를 모든 family가 동일하게 받도록 SHA-256으로 고정한다는 뜻이다.

## 4. 데이터·컴퓨트 요구

### 4.1 로컬 실행 계획

RTX 5070 Ti 16GB, RAM 64GB에서 다음은 전부 로컬이다.

- DXF/SEG-IR 변환, 유효성 인증, LID ledger, SHA-256, xlsx 집계: CPU.
- deterministic와 classical inference: CPU, `fast_score` 캐시 사용.
- GNN inference: 16GB에 맞춘 drawing별 또는 subgraph별 순차 batch. 결과 결합 규칙을 model manifest에 봉인한다.
- FloorPlanCAD/VLM adapter smoke: 로컬 qwen2.5-VL-3B artifact로 interface만 검증할 수 있으나, 이를 본선 VLM family 결과로 대체하지 않는다.

40도면×도면당 18개 parameter instance×4 family이므로 transformed inference는 **계획상** 2,880회이고, family×drawing base 160회를 cache하면 총 detector invocation은 3,040회다. 이는 실측 처리량이 아니라 설계 산술이다. transform artifact는 family 간 공유한다. family를 순차 실행하고 drawing 하나의 IR만 메모리에 올려 412,775 선분 병목에서 RAM 폭주를 피한다. timeout은 결과 flip으로 세지 않고 `EXECUTION_ERROR`; 해당 셀이 결측이므로 전체 28셀 결론을 막는다.

현재 `battery_cli.py`는 transform마다 base detector를 다시 실행한다. P5에서는 `(detector_manifest_hash,drawing_hash)` cache key로 한 번만 실행한다. cache hit는 원 prediction hash와 완전히 일치해야 한다.

### 4.2 DGX 계획과 불통 시 처리

VLM 7셀 본선은 패킷 지시대로 DGX inference, temperature 0으로 분리한다. DGX Spark가 현재 unreachable이므로 VLM full cell은 `DEFERRED_RESOURCE`, 0, PASS 또는 로컬 대체값으로 채우지 않는다. 먼저 다음 preflight만 로컬에서 끝낸다: prompt freeze, renderer hash, pixel↔LID projection 합성 exact test, 5도면 serialization, expected output schema.

DGX가 복구되면 모델·CUDA/container digest, deterministic flags, prompt, rasterizer를 봉인하고 identical-input checksum check를 먼저 한다. Ornith-35B의 vision 지원 여부가 확인되지 않으면 VLM family artifact 자체가 성립하지 않으므로 T13에 따라 중단한다. 28셀 완전요인 결론은 VLM 7셀이 채워질 때까지 `PASS_WITH_DEFERRAL`이 아니라 단순히 **UNRUN/INCOMPLETE**다.

### 4.3 저장 산출물과 증거 보존

실행 시 생성할 증거는 다음이며, 본 도시에는 계획만 쓴다.

- immutable `catalog.json`, `sample_manifest.json`, `detector_manifests/*.json`
- base/after SEG-IR와 transform certificate의 content-addressed cache
- 원시 entity 비교 JSONL
- 의무 xlsx: `prereg`, `drawings`, `detectors`, `transform_params`, `runs`, `cell_summary`, `A_by_B`, `sentinels`, `mapping_errors`, `confirmation` sheet
- 실패의 stack/timeout/config hash와 `experiment_executed` 상태

원본 CAD는 read-only이고 모든 변형은 explicit staging 아래에만 쓴다. test artifact와 holdout-firm manifest는 freeze 이후 한 번만 연다.

## 5. 구현 계획

### 5.1 현재 코드와 정확한 접속점

읽은 현재 구현을 기준으로 재사용한다.

- `tools/e2/meta/transforms_rigid.py`: rotate/translate/scale/unit 변환. mirror도 있으나 P5 catalog에서는 등록하지 않는다.
- `tools/e2/meta/transforms_struct.py`: recursive explode와 layer rename. occurrence-level LID map으로 확장한다.
- `tools/e2/meta/invariance.py`: binary compare, zero/all sentinel, recall floor의 골격. 현재 before handle만을 분모로 삼는 비교를 LID coverage-aware comparator로 교체한다.
- `tools/e2/meta/battery_cli.py`: staging-only 실행, detector subprocess, xlsx의 골격. 현재 single default parameter, detector family 부재, coord-jitter 부재, transform-only summary를 확장한다.
- `tools/e2/detect/evidence_grid.py` 및 `w1_real_defs.fast_score`: deterministic adapter.
- `tools/e2/ext/cubicasa_ir.py`: SEG-IR/truth conversion과 split 보존.
- `tools/e2/ext/cubicasa_ml.py`: 6-feature classical training 접속점. model persistence/inference entry point를 추가한다.
- `tools/semantic_gates/synthetic_truth.py`: correct-by-construction + exactly-one-seeded-violation 패턴을 재사용하되, dimension truth 코드를 벽 truth로 오인하지 않는다.

### 5.2 제안 파일 골격

```text
tools/e2/meta/
  catalog.py                 # 정확히 7관계, expected_relation, sealed params
  coord_jitter.py            # topology-certified deterministic precision jitter
  logical_identity.py        # occurrence-level LID ledger와 handle maps
  transform_oracle.py        # clean-pair geometry/unit/topology certificate
  relation_compare.py        # label flip, coverage, equivariant geometry residual
  sentinels.py               # zero/all, truth recall qualification
  runner.py                  # 7×4 orchestration, base cache, resume, errors
  report_xlsx.py             # evidence workbook와 28-cell matrix
  adapters/
    base.py
    deterministic.py
    classical_ml.py
    gnn.py
    vlm.py
tests/e2/meta/
  test_catalog_exact_seven.py
  test_each_relation_clean_and_one_mutant.py
  test_repeated_insert_lid_mapping.py
  test_unit_equivariance.py
  test_jitter_certificate.py
  test_sentinel_trivial_detectors.py
  test_battery_28cell_schema.py
```

기존 파일을 대규모로 갈아엎기보다 `battery_cli.py`는 새 runner의 얇은 CLI가 되게 한다. detector command 문자열을 shell로 해석하는 현재 경로는 quoting과 재현성 위험이 있으므로, main execution은 argv list 또는 Python adapter를 사용하고 legacy subprocess template은 compatibility mode로만 둔다.

### 5.3 구현 순서와 규모

1. **identity/oracle(약 2 개발일, 계획값):** LID, repeated INSERT, poly-edge, transform certificate, seven clean/mutant fixtures.
2. **runner/report(약 1–2 개발일, 계획값):** family factor, multi-parameter expansion, base cache, resumable JSONL, evidence xlsx.
3. **deterministic/classical adapters(약 1 개발일, 계획값):** prediction schema wrapping, HGBDT persistence, frozen threshold.
4. **GNN/VLM adapters(각 약 1–2 개발일, 계획값, artifact 준비 제외):** Graph-IR reindexing, raster inverse projection, deterministic preflight.
5. **cheapest probe 후 full run:** probe가 harness/단위 문제를 드러내면 full 28셀 전에 수정하고 catalog version을 새로 봉인한다.

각 단계의 숫자는 staffing 예측이지 실측 개발시간이 아니다. 완료 조건은 코드 줄 수가 아니라 clean relation 0위반, single mutant 검출, repeated INSERT 전단사, xlsx schema 검증이다.

## 6. 실험 셀 정의

### 6.1 사전 자격 셀 — 28셀에 섞지 않음

| 셀 | 가설 | 지표 | 제안 합격선 | 킬 조건 | 예산 | 시드 계획 |
|---|---|---|---|---|---|---|
| `Q0 T-META oracle` | 7 clean relation은 0위반이고 각 exactly-one mutant는 정확히 검출된다 | clean false violation, mutant kill, mapping coverage | clean 전부 0; mutant 전부 kill; mapping collision 0 | 하나라도 clean을 위반 또는 mutant 생존 시 detector 실행 금지 | 로컬 CPU ≤1시간(상한 제안) | catalog seed `20260718`; rename/jitter는 표의 고정 seed |
| `Q1 family sentinels` ×4 | 각 family는 constant-zero/all 해가 아니며 positive fixture를 일부 회수한다 | zero/all flag, labeled recall | sentinel fixture 전부 탐지; recall≥0.20(새 제안) | 자명한 해 미검출 또는 recall 미달 시 family 랭킹 제외 | family당 로컬 ≤1시간; VLM은 DGX preflight | 학습 seed는 upstream artifact에 고정; P5 재학습 없음 |
| `Q2 repeat checksum` ×4 | 동일 입력·artifact는 동일 prediction을 낸다 | normalized prediction SHA-256 | checksum 완전 일치 | 불일치 시 평균하지 않고 family 실행 실패 | family당 5도면 duplicate run | 변환 seed 없음; VLM temperature 0 |

`Q1`의 labeled 자료는 CubiCasa val 또는 PR-1 wall truth pack이다. CubiCasa test는 열지 않는다. sentinel은 R-META 본 반응이 label-free라는 사실을 바꾸지 않고, 자명한 통과자를 랭킹에서 배제하는 자격검사다.

### 6.2 최저비용 프로브 — 먼저 실행할 2셀

5도면은 145 아카이브에서 label 없이 `{작은/큰 segment count, unit known, INSERT 있음}`을 가능한 범위에서 포괄하도록 deterministic하게 선택한다.

| 셀 | 가설 | 지표 | 합격선 | 킬/분기 | 예산 | 시드 |
|---|---|---|---|---|---|---|
| `P-R: deterministic(v0)×rotate` | frozen v0의 wall label은 90° 회전에 불변 | R-META macro, mapping errors, sentinels | PASS≤0.02 | transform oracle 오류면 harness 수정; R-META>0.10이면 rotation normalization 선조사 | 패킷 계약상 두 probe 합계 30분 | 무시드, angle 90° |
| `P-U: deterministic(v0)×unit-change` | mm↔m 물리 동치 뒤 wall label은 불변 | 같은 지표 + unit certificate | PASS≤0.02 | R-META>0.10이면 gap/unit normalization을 P2에서 먼저 수리 | 위와 합산 | 무시드, metadata가 허용하는 반대 단위 1회 |

probe는 원인 가설을 빠르게 고르는 위생검사다. 여기서 PASS해도 나머지 26셀을 통과한 것이 아니다. unit metadata가 없는 도면에 임의 단위를 부여하지 않으며, unit-known 도면을 선택할 수 없으면 `P-U BLOCKED_DATA`다.

### 6.3 본 실험 28셀

모든 셀의 평가 population은 동일한 40도면이고, transform별 parameter 수만 2.2절 표대로 다르다. 다음 표의 시간은 **셀별 실행 중단 상한 제안**이지 처리시간 실측이 아니다.

| 셀군 | 셀 ID | 셀별 가설 | 지표/합격선 | 셀별 킬 조건 | 셀별 예산 | 시드 |
|---|---|---|---|---|---|---|
| deterministic(v0) | `F01` translate, `F02` rotate, `F03` scale, `F04` unit, `F05` explode, `F06` rename, `F07` jitter | v0 label이 해당 relation에 불변이며 scale/unit geometry는 등변 | R-META; PASS≤0.02, INC≤0.10, FAIL>0.10 | 해당 셀 >0.10이면 relation-specific FAIL; 7셀 전부 FAIL이면 P2/CL-B의 unit·표현 정규화 전까지 프로그램 사다리 중단 | 셀당 CPU 2시간 상한 | 공통 catalog seed; 결정 실행을 replicate로 부르지 않음 |
| classical-ML | `F08`–`F14`, 위와 같은 순서 | frozen HGBDT가 val 성능을 얻은 표현 우연성이 아니라 같은 벽 의미를 보존 | 동일 | 7셀 전부 FAIL이면 representation normalization 없이는 부적격; sentinel 미달이면 랭킹 제외 | 셀당 CPU 2시간 상한 | training seed는 artifact manifest의 고정 1개; 변환 seed만 catalog |
| GNN | `F15`–`F21` | graph topology와 canonical geometry를 쓰는 frozen GNN이 transform별 자기일관성을 보존 | 동일 + graph LID coverage | adjacency audit 실패면 셀 실행 전 kill; 7셀 전부 FAIL이면 absolute coordinate/feature normalization 전 부적격 | 셀당 RTX 5070 Ti 4 GPU시간 상한 | upstream training seed 고정; seed 효과를 P5 interaction과 혼동하지 않음 |
| VLM | `F22`–`F28` | frozen render/prompt/model pipeline이 동일 벽을 같은 LID에 투영 | 동일 + inverse-warp residual + checksum | vision 미지원, pixel↔LID exact test 실패, checksum 불일치면 실행 kill; 7셀 전부 FAIL이면 crop/absolute-position 과적합으로 부적격 | 셀당 DGX 4 GPU시간 상한 | temperature 0, greedy; renderer/catalog seed 고정 |

각 transform의 구체 파라미터 표본은 다음과 같이 셀 안에 nested된다: translate 3, rotate 3, scale 3, unit 2, explode 1, rename 3, jitter 3. 이들을 18개의 독립 replicate라고 부르지 않는다. 불변이면 parameter 값에 무관해야 하므로 같은 셀의 사전등록 population이다.

본 실험의 선결 및 판정 순서는 고정한다.

1. Q0 transform oracle PASS.
2. Q1/Q2 family qualification.
3. cheapest probe.
4. 40도면 28셀 full factorial; 실행 순서는 cache locality를 위해 drawing→transform→family여도 되지만 logical run order를 기록한다.
5. A, B, A×B exact matrix와 status 작성.
6. 결과를 본 뒤 detector/config를 바꾸면 기존 결과를 덮어쓰지 않고 새 method ID로 val부터 다시 시작한다.

### 6.4 val/test 및 confirmation

classical/GNN/VLM의 학습과 threshold 선택은 train/val에서 끝낸다. P5 개발 중 CubiCasa test를 metamorphic 용도로도 읽지 않는다. label을 보지 않더라도 test 반응으로 preprocessing을 고칠 수 있기 때문이다. 최종 method별 test는 accuracy metric과 지원되는 metamorphic subset을 한 job manifest로 묶어 **단발** 실행한다.

confirmation은 sentinel-qualified family 중 7셀 worst-case R-META가 가장 낮은 family를 선택해, 학습/개발에 없던 holdout firm에서 한 번 실행한다. selection metric은 mean이 아니라 worst relation으로 봉인한다. known 7관계에는 새 parameter 값을 사용하되 catalog type은 늘리지 않는다. 합격은 7셀 모두 `≤0.02`, mapping/integrity 오류 0이다.

원 제안의 “새 변환 1종 추가”와 “명시된 7개 밖 관계는 발명하지 않음”은 동시에 완수할 수 없다. 본 패킷의 더 엄격한 abstention을 따른다. 여덟 번째 transform은 governance가 카탈로그를 개정하기 전까지 **deferred**이며 confirmation status는 `PASS_WITH_DEFERRAL`이다. 허용되는 확인은 기존 7관계의 held-out parameter뿐이다.

## 7. red team 티켓 응답

| 티켓/공격 | P5에 걸리는 이유 | 해소 또는 수용 입장 |
|---|---|---|
| **T1 / attack A — proxy 독립성** | metamorphic, 합성, 외부셋, silver가 같은 평행 이중선 prior를 공유할 수 있다 | R-META를 정확도 증거의 한 표로 합산하지 않는다. same-def에서 `R-META fail/pass × R-SYN/R-SILVER correct/incorrect` 불일치표를 CL-E에 넘기고, “필요조건 gate”로만 사용한다. 위험은 완전 해소가 아니라 명시적 제한으로 수용한다. |
| **T2 / PR-1 — 벽 합성 generator 부재** | 현재 `synthetic_truth.py`는 dimension용이며 wall truth가 아니다 | Q0은 relation/mapping mutant라 자체 구축 가능하다. 그러나 labeled recall sentinel과 정확성 pairing은 PR-1 wall generator 또는 CubiCasa val을 요구한다. dimension generator를 벽 truth로 재명명하지 않는다. PR-1 미완료 시 synthetic sentinel은 deferred다. |
| **T5 / PR-3 — 외부셋 권리** | CubiCasa/FloorPlanCAD를 sentinel·학습·VLM smoke에 쓰면 권리 문제가 다시 생긴다 | label-free 145 CAD battery는 계속 가능하다. 외부셋을 학습/배포 근거로 쓰는 arm은 counsel 서면 확인 전 중단한다. license 불명 자료의 수치로 결측 VLM/GNN 셀을 채우지 않는다. |
| **T6 / attack E — 평가 단위** | wall assembly와 per-handle 분류가 섞이면 flip 의미가 바뀐다 | primary unit을 occurrence-level `LID segment`로 고정한다. wall pair/room assembly는 보조 geometry output이고 R-META 분모에 혼합하지 않는다. |
| **T7 / attack F — 0벽 탐지기 통과** | violation-rate only는 constant detector를 완벽하게 통과시킨다 | Q1 zero/all fixtures, positive recall≥0.20, near-all flag를 랭킹 선결로 둔다. sentinel 불합격 family는 R-META가 0이어도 winner가 될 수 없다. 그래도 일관되게 틀린 비상수 detector 가능성은 R-SYN/R-SILVER pairing으로만 다룬다. |
| **T9/T21 — v0 baseline 선계측·동결** | proposal arm 이름과 현재 detector code/version이 혼동될 수 있다 | git에 의존하지 않고 file/config/model SHA-256 manifest를 만든다. v0 artifact가 없으면 v1 결과를 v0로 표기하지 않고 cell을 blocked 처리한다. cheapest probe가 첫 선계측이다. |
| **T10/T23 — Graph-IR adjacency 완전성** | GNN의 explode/transform 실패가 model이 아니라 graph builder 결함일 수 있다 | endpoint·parallel·block edge를 LID 기준으로 transform 전후 inverse-map해 exact equality audit한다. audit 미통과 시 F15–F21 실행 금지. |
| **T13 — DGX/Ornith vision 지원** | VLM 7셀의 실행자원이 현재 불통이고 vision 지원도 미확인 | schema/renderer smoke만 로컬에서 하고, DGX 접속과 vision support 확인 전 F22–F28을 `DEFERRED_RESOURCE`로 둔다. local 3B 결과를 본선 Ornith 결과로 대체하지 않는다. |
| **T15 — learned cell seed confounding** | model training seed와 transform parameter seed를 섞으면 family 취약성인지 학습 우연인지 모른다 | P5는 각 family의 frozen artifact 하나를 비교하며 재학습 seed를 noise replicate로 사용하지 않는다. seed robustness는 별도 upstream 실험이다. transform seed는 입력 population으로만 기록한다. |
| **T17 / CL-E — same-def truth-source 구조** | P5가 독립 proxy인 척할 위험 | same-def key와 LID를 보존해 CL-E가 정확히 join할 수 있게 raw rows를 낸다. P5 안에서 독립성 인과를 주장하지 않는다. |
| **T24 — pixel→handle exact harness** | VLM mask를 잘못 역투영하면 거짓 flip이 생긴다 | 합성 vector wall을 rasterize해 transform/inverse projection 후 LID score가 exact하게 복원되는 Q0 fixture를 의무화한다. 실패하면 VLM family kill. |
| **T31 — raster 본선 주장** | VLM arm이 있다는 이유로 raster를 본선으로 승격할 수 있다 | P5는 family 비교 게이트일 뿐 본선 지위를 주지 않는다. vector gate를 넘고 정확도 이득을 별도 증명해야 한다. |
| **T34 — 인용 status** | 방법론 문헌 이름이 실행 증거처럼 읽힐 수 있다 | 1절 인용은 계보 설명이며 `experiment_executed:false`다. 본 문서의 proposal status도 UNRUN으로 유지한다. 문헌 서지 세부는 요검증하고, 문헌 성능 수치를 가져오지 않는다. |

attack C의 정렬-key 아티팩트와 CL-A의 forensic audit는 P5 주 반응을 직접 정의하지 않지만, draw selection과 LID 정렬에서 같은 유형의 오류를 피해야 한다. 그래서 정렬 순서가 아니라 content-derived LID를 쓰고, 샘플 manifest를 결과 전에 봉인한다. attack D의 원 도면 권리는 145 아카이브에도 적용될 수 있으므로 원본을 외부 전송하지 않고 local transformation만 수행하며, VLM API 미승인 상태에서는 외부 API를 호출하지 않는다.

## 8. 인접 제안과의 관계 및 사망 조건

### 8.1 병합과 차별점

- **CL-D(platt P3 + calibration M)와 직접 병합:** transform 구현·sentinel·공통 xlsx는 공유한다. doe P5의 고유 기여는 7×4 완전요인, drawing block, parameter nesting, A×B interaction, deterministic gate 판정이다.
- **P1/P3 및 CL-C/CL-E와 결합:** P5는 무라벨 consistency를, R-SYN/R-SILVER/외부셋은 correctness를 준다. 같은 LID의 불일치 구조는 CL-E proxy 독립성 분석의 입력이 된다. 어느 것도 서로를 대체하지 않는다.
- **P2/CL-B와 feedback loop:** unit/scale FAIL은 gap band, unit anchor, coordinate normalization 수리의 직접 재현 testcase가 된다. 수리 전후 같은 catalog를 다시 실행하되 method version을 새로 낸다.
- **CL-F와 관계:** classical/GNN rung이 정확도에서 앞서도 P5 sentinel과 7관계 gate를 통과해야 배치 후보가 된다. GNN이 이기면 interaction matrix가 어떤 transform에서 이겼는지 보여준다.
- **CL-G와 관계:** VLM은 동일 시험지의 한 family일 뿐 silver judge와 동일하지 않다. E1.5의 5 판정자가 실질적으로 약 2 어휘 가문으로 갈린다는 실측 때문에 prompt/model 변형을 5독립 seed로 세지 않는다.
- **현재 B4와 차별:** 기존 partial B4는 scale 취약 신호를 냈지만, P5는 coord-jitter, explode, rename, four-family interaction, LID mapping, sentinel qualification을 포함한 완전한 공용 gate다.

### 8.2 kill condition과 정직한 축소 규칙

다음이면 P5 또는 해당 주장을 죽인다.

1. **transform oracle 사망:** 의미보존을 결과와 독립적으로 인증할 수 없거나 repeated INSERT/edge occurrence의 전단사 LID mapping을 만들 수 없으면 block-explode relation을 제거해 7관계 주장과 28셀 설계를 함께 철회한다. 결측을 PASS로 두지 않는다.
2. **harness mutation 사망:** clean fixture에서 거짓 위반이 나거나 exactly-one mutant가 살아남으면 detector를 평가하지 않는다. 먼저 comparator를 고친다.
3. **triviality 사망:** zero/all detector가 Q1을 통과하면 R-META winner ranking을 전면 금지한다. sentinel을 고치기 전 violation 결과는 진단 로그일 뿐이다.
4. **v0 전면 FAIL:** 패킷 kill대로 deterministic(v0)이 7변환 전부 `>0.10`이면 현 휴리스틱은 기하학적 위생도 없다. learned ladder 비교를 미루고 P2/CL-B의 unit·scale·coordinate normalization을 선수리한다. P5 자체는 그 결함을 발견한 것으로 살아 있지만 “family ranking”은 중단한다.
5. **learned family 전면 FAIL:** classical/GNN/VLM 중 한 family가 7변환 전부 `>0.10`이면 representation normalization 없이는 그 family를 부적격으로 판정한다. 더 많은 seed로 희석하지 않는다.
6. **무차별 gate:** sentinel-qualified 모든 family가 모든 셀에서 완전히 같은 PASS를 내고 R-SYN/외부 test correctness와도 아무 관계가 없다면 P5를 ranking 실험으로는 죽이고 저비용 regression test로만 축소한다.
7. **비용 역전:** exact LID mapping과 VLM projection 때문에 P5가 가장 싼 신호가 아니게 되고, cheap probe가 반복적으로 correctness 평가보다 비싸면 full census를 죽이고 deterministic 2관계 CI probe만 보존한다.
8. **필요조건 오독:** 조직이 R-META PASS를 “벽 정확” 승인으로 사용하려 한다면 이 제안의 deployment 승인 기능을 죽인다. P5는 R-SYN/R-SILVER 또는 외부 사람 라벨 결과와 쌍을 이루지 않는 한 최종 판정권이 없다.

최종 성공 정의는 “가장 낮은 위반율 모델을 찾음”이 아니다. (a) T-META v1의 7관계를 실행 가능한 oracle로 만들고, (b) 자명한 해를 차단하고, (c) 28셀 A×B를 결측 없이 채우며, (d) 어떤 family가 어떤 CAD 표현에서 깨지는지 exact raw evidence로 남기고, (e) holdout firm에서 같은 gate를 한 번 재현하는 것이다. 여덟 번째 transform은 승인 범위 밖이므로 confirmation은 명시적으로 `PASS_WITH_DEFERRAL`을 유지한다.

DOSSIER_COMPLETE: doe_P5
