# 도시에 — calibration_P4

**제안**: P4. Raster–vector dual-view DL과 결정적 back-projection
**좌석**: calibration_forecaster (예측·보정 관점)
**작성 규율**: 수치 인용은 패킷 다이제스트에 한정. 그 외 방법론·논문 언급은 문헌 일반 지식이며, 확신이 낮은 인용은 `요검증` 표기. 웹 검색 미사용.

---

## 0. 예측 계약 요약 (calibration 좌석의 입장 고정)

이 좌석의 산출은 "P4가 좋다/나쁘다"의 단정이 아니라 **봉인된 예측(prereg forecast)** 이다. 즉 실험 전에 합격선을 봉투에 봉해 두고(prereg band), 실험 후 그 봉투를 열어 채점한다. 제안 원문의 계약을 그대로 승계한다:

- **claim** = P4가 (a) raster가 이득을 주는 지층(stratum, "같은 성질을 가진 벽 부분집합")에서 vector baseline을 개선하고, **동시에** (b) 전체 비열등성(non-inferiority)·(c) back-projection 정합성·(d) calibration(REL/RES) 게이트를 **모두** 통과한다.
- **forecast** = `null` (수치 확률 abstain). 이유는 아래 abstain_flag.
- **score_type** = `brier`. 벽/비벽 이진 확률예측의 정확도를 Brier score(예측확률과 실제 0/1의 제곱오차 평균, 낮을수록 좋음)로 채점한다.
- **reference_class** = `RC-WALL-ZL`, 현재 표본수 `n=0`, 최소요건 `n_min=5`. 즉 "native-DWG 공유 holdout에서 dual-view(래스터+벡터 이중 시야)가 해결된 사례"가 아직 하나도 없다.
- **base_rate** = `none`. 참조 사례가 0이므로 밑변 확률을 줄 수 없다.
- **abstain_flag** = `empty_reference_class`. **수치 forecast를 내지 않는 이유는 게으름이 아니라 규율이다**: 근거로 삼을 유사 해결 사례가 0건이면, 어떤 점 확률도 날조(FM9 출처 없는 수치)가 된다. 그래서 이 좌석은 "밴드는 봉인하되 점 예측은 유보"한다.
- **uncertainty_type** = `epistemic`(인식적 — 지식 부족에서 오는 불확실성, 측정하면 줄어든다). style/CRS-층화 평가로 감소시킨다.
- **resolution_verdict** = `open`.
- **resolution_trigger** = render manifest·CRS contract·model hash가 **동결(freeze)** 된 뒤 `wsd_eval_p4.json`이 생성될 때. 이 세 가지를 얼리기 전의 어떤 숫자도 "결과"로 인용하지 않는다.
- **update_log 약정**: style-held-out subgroup lift는 상향 증거, back-projection mismatch나 vector-only 대비 전체 열화는 하향 증거로 **사전** 약정한다(사후에 유리한 쪽만 고르는 것 금지).

이 계약이 이 도시에 전체를 지배한다. 아래 8절은 이 계약을 실행 가능한 실험으로 번역한 것이다.

---

## 1. 이론적 근거·선행연구

### 1.1 P4가 기대는 세 갈래 계보

P4는 세 개의 독립된 방법론 갈래를 한 파이프라인으로 접합한다. 각 갈래를 이름과 함께 풀어 쓴다.

**(A) 도면 래스터↔벡터 상호변환 계보 (floor-plan raster↔vector).**
- **CubiCasa5K** (Kalervo et al., 2019, 요검증 — WACV/SCIA 계열): 5,000장 핀란드 주거 도면에 사람 라벨(room/wall/icon)을 붙인 셋. 멀티태스크 CNN으로 래스터 도면을 파싱. 우리 다이제스트의 외부셋이 바로 이것이다.
- **Raster-to-Vector** (Liu, Wu 등, ICCV 2017, 요검증): 도면 래스터를 CNN으로 접합점·선을 예측한 뒤 정수계획법으로 벡터 구조로 복원. "래스터에서 학습하고 벡터로 되돌린다"는 P4의 골격과 직접 닮았다.
- **FloorPlanCAD** (Fan et al., ICCV 2021, 요검증) + **CADTransformer/GAT-CADNet** (CVPR 2022 계열, 요검증): CAD 프리미티브 위 panoptic symbol spotting. 여기서 배울 점은 "벡터 프리미티브가 진리 좌표이고 래스터는 인식 보조"라는 역할 분담 — P4의 "최종 handle·geometry는 항상 IR에서" 원칙과 같다.

**(B) 렌더→분할→프리미티브 back-projection 계보 (multi-view label back-projection).**
P4의 핵심 트릭 — 픽셀 점수를 원래 엔티티 handle로 되돌리는 것 — 은 3D 의미분할에서 잘 정립된 패턴의 2D 판이다.
- **SnapNet** (Boulch et al., 2017, 요검증), **Deep Projective 3D Semantic Segmentation** (Lawin et al., 2017, 요검증): 3D 점군을 여러 시점에서 렌더 → 2D CNN으로 분할 → 픽셀 라벨을 다시 3D 점으로 back-project. P4는 시점이 하나(평면도)일 뿐 구조가 동일하다.
- 그래픽스의 **G-buffer / object-ID pass (deferred rendering)**: 각 픽셀에 "어느 오브젝트가 그려졌는가"의 정수 ID를 저장하는 렌더 패스. P4의 **entity-ID buffer**가 정확히 이것이다. ID buffer는 학습 입력이 아니라 좌표 역매핑 테이블로만 쓰인다.

**(C) 이확률 융합·보정 계보 (calibration & late fusion).** — 이 좌석의 홈그라운드.
- **Platt scaling** (Platt, 1999, 요검증), **isotonic regression** (Zadrozny & Elkan, 2002, 요검증), **temperature scaling** (Guo et al., 2017 "On Calibration of Modern Neural Networks", 요검증): 모델 출력 점수를 "진짜 확률"로 교정. P4는 vector branch와 raster branch 두 확률을 held-out calibration으로 융합하므로 이 계보가 필수.
- **Murphy(1973) Brier 분해** (요검증): Brier = **REL** − **RES** + **UNC**. REL(reliability, 신뢰도오차, 낮을수록 좋음)·RES(resolution, 분해능/변별력, 높을수록 좋음)·UNC(uncertainty, 밑변 불확실성, 고정). 좌석의 prereg `REL≤0.04, RES≥0.02`가 바로 이 분해의 두 항이다. UNC는 우리 밑변에서 산술로 고정된다(§2.6에서 계산).

**(D) 얇은 구조 분할 손실 계보.** 벽은 가늘고 길다.
- **Dice/Tversky loss**, **focal loss** (Lin et al., 2017, 요검증), **clDice**(topology-preserving, Shit et al., 2021, 요검증): 클래스 불균형(CubiCasa 벽 선분율 ~11.8%)과 얇은 선 소실에 대응. P4의 "얇은 선 소실" 실패모드의 직접 대응책.

### 1.2 왜 하필 지금 이 방법인가 (우리 실측이 만든 논거)

- 기하 탐지기 v1 전이 성적 **val F1 0.2358 (P 0.134 ≈ 기저율 0.118, R 0.981)**. 정밀도가 기저율과 사실상 같다 = "긴 평행 구조면 다 벽"이라 외치는 수준. FP 주범이 **Direction 화살표·BoundaryPolygon·Door·Window·DimensionMark** — 전부 "대역 내 평행 구조"다.
- GBDT(HistGradientBoosting, 6특징) **val P 0.860 / R 0.370 / F1 0.517 / AUC 0.9215**. 정밀도는 살렸으나(0.13→0.86) **재현율 0.37** — 즉 벽의 63%를 놓친다.

두 벡터 방법의 공통 한계는 **per-handle(엔티티 하나 단위) 지역 특징**(parallel/thickness/junction/log길이/sin2θ/cos2θ)만 본다는 것이다. 이 특징들은 "이 평행쌍이 방을 두르는 고리의 일부인가, 아니면 치수 보조선인가"라는 **2D 배치 맥락**을 볼 수 없다. 사람이 도면을 볼 때 벽을 아는 것은 두께 때문만이 아니라 **전체 그림에서 벽이 이루는 형상(방 경계 루프)** 때문이다. 이 "형상 맥락"은 수용장(receptive field)을 가진 분할 CNN이 자연히 포착하는 정보다. **P4의 존재 이유는 GBDT를 전면 대체하는 것이 아니라, GBDT가 구조적으로 못 보는 맥락을 raster branch로 보태 재현율 갭을 특정 지층에서만 회수하는 것**이다. 이것이 §3에서 정량화된다.

---

## 2. 알고리즘 정확 스펙

표기: IR = DWG/DXF 중간표현(엔티티 집합), `h` = 엔티티 handle, `M` = 픽셀 점수맵, `B` = ID buffer.

### 2.1 입력·출력

- **입력(학습/추론)**: (i) IR — SEG-IR(cubicasa_ir 산출) 또는 1.dwg staged DXF의 엔티티+geometry+layer. (ii) render config — 스케일 집합 S(px/unit), 패치크기 P∈{512,1024}, render style family φ∈Φ(선굵기·색맵·DPI·AA on/off).
- **출력**: 각 handle의 융합 벽 확률 `p_fused(h)∈[0,1]`, prereg 임계로 이진화. + `wsd_eval_p4.json`(handle별 점수·지층·지표, resolution trigger 산출물).
- **truth(학습·평가 분리)**: pixel metric은 CubiCasa pixel mask / synthetic exact wall mask, handle metric은 synthetic exact handle mapping / CubiCasa Wall-class 요소 모서리. **원본 래스터·모델 attention은 truth가 아니다.**

### 2.2 렌더링 (결정적)

```
for s in S, φ in Φ:
    R[s,φ] = rasterize_linework(IR, scale=s, style=φ)      # H×W×C, 모델 입력
    B[s]   = rasterize_id(IR, scale=s)                     # H×W int, 픽셀→topmost handle-id
불변식(invariant):
  (1) R[s,φ]와 B[s]는 동일 변환행렬 T(s)로 렌더 → 픽셀 p의 R값과 B[s][p]의 handle이 정확히 대응.
  (2) B는 절대 모델 입력이 아니다 (leakage 방지). back-projection에만.
  (3) B는 hard assignment(nearest, AA 없음); R은 AA 허용. 경계 픽셀의 handle 모호성은
      back-projection 샘플링을 B의 hard 픽셀에서만 하도록 강제해 제거.
```

**충돌 처리(핵심 실패모드)**: 한 픽셀에 여러 handle이 겹치면 B는 z/draw-order 최상위 하나만 저장 → 항상 가려지는 handle은 픽셀 0개 → raster_score=0. 대응: (a) 항상 vector branch가 병존하므로 가려진 handle도 vector_score를 받는다; (b) mapping-accuracy 게이트(§2.5)가 "픽셀 0개 handle 비율"을 직접 측정해 back-projection 하네스 자체를 채점한다.

### 2.3 raster branch 모델

```
f_θ : R[s,φ]  →  M ∈ [0,1]^{H×W}          # per-pixel 벽 확률
backbone: U-Net / SegFormer(B0~) / DeepLabv3+  (§4에서 크기 선택)
loss:  L = λ_bce·BCE(M, mask) + λ_dice·Dice(M, mask) + λ_cl·clDice(M, mask)
       클래스 불균형(벽 ~11.8%) → focal γ 또는 class weight
multi-scale: 공유 encoder + scale별 head, 또는 scale별 M을 back-projection 후 융합
```

### 2.4 back-projection (결정적, 학습 없음)

```
for each handle h:
    pix(h) = { p : B[s][p] == h }
    raster_score(h) = AGG_{p in pix(h)} M[p]     # AGG ∈ {mean, area-weighted mean, trimmed-mean, max}
    if pix(h) == ∅:  raster_score(h) = NA  (→ 융합에서 vector-only로 폴백)
handle geometry = IR에서 그대로 (M에서 절대 유도 금지)
```

AGG 선택은 calibration set에서 결정(하이퍼파라미터).

### 2.5 mapping-accuracy / CRS 정합성 자기검사 (게이트, 학습 이전)

```
synthetic: 각 벽 픽셀이 정답 handle로 back-project되는 비율 = mapping_accuracy
CRS round-trip: T(s) 적용 후 역변환 좌표와 원 좌표의 오차율 = crs_err
prereg: mapping_accuracy ≥ 0.995,  crs_err ≤ 0.5%
```
이 검사는 **학습 성능과 무관한 하네스의 결정적 속성**이다. 통과 못 하면 학습 결과는 해석 불가 → 즉시 중단.

### 2.6 융합·보정

```
vector_score(h) = GBDT 확률 (cubicasa_ml, 6특징)          # 이미 존재: val F1 0.517/AUC 0.9215
raster_score(h) = §2.4 back-projected aggregate
calibrator g (held-out calibration slice에서만 fit):
    옵션1 stacking:   p_fused = σ(w0 + w1·logit(vec) + w2·logit(ras))
    옵션2 branch별 온도/isotonic 교정 후 가중평균 (weight도 calibration set에서)
calibration slice = val의 분리된 조각 (train·test 아님)
채점: Brier(p_fused, y);  Murphy 분해 BS = REL − RES + UNC
```

**UNC 산술(다이제스트 밑변에서 유도)**: 기저율 0.118 → UNC = 0.118×(1−0.118) = **0.1041**. 따라서 prereg `RES≥0.02`는 밑변 불확실성의 약 19%를 변별로 설명하라는 요구, `REL≤0.04`와 합치면 **함의 Brier 상한 ≈ 0.1041 − 0.02 + 0.04 = 0.124**(이 숫자는 다이제스트 밑변에서의 산술 유도이지 측정치 아님).

### 2.7 하이퍼파라미터 공간

backbone 크기 · P∈{512,1024} · 스케일 집합 S · AGG 함수 · calibrator family · loss 가중(λ_bce/λ_dice/λ_cl, focal γ) · augmentation(회전/반사 — metamorphic 일관). 로컬 탐색은 좁게(§4), 넓은 sweep은 DGX 대기.

### 2.8 leakage protection (알고리즘에 내장)

building/drawing 단위 split · render style family holdout · **ID buffer 입력 금지** · 모든 crop은 원본 fold 상속. 이 넷은 옵션이 아니라 자기검사로 강제(§6 Cell E).

---

## 3. 벽 과업 적응 설계 — 실제 하네스 접속

세 축에 어떻게 붙는가, 그리고 **전이 0.2358·GBDT 0.517을 아는 상태에서 무엇을 더 가져오는가**.

### 3.1 CubiCasa SEG-IR 벡터축 (raster representation 연구축)

- 접속: cubicasa_ir이 만든 SEG-IR(5,000 도면 전량 변환, 실패 0, 레이어 중립, 진리=Wall 클래스 모서리)을 **§2.2로 래스터+ID buffer 렌더**. train 4,200(선분 386만)/val 400/test 400, 벽 선분율 ~11.8%. 좌표는 px(도면별 축척 미상, 벽두께 px p50=22).
- 역할: 여기가 유일한 대규모 라벨 벡터축이므로 **raster branch 학습의 본진**이다. 벽두께 p50=22px는 512~1024px 패치에서 충분히 보이는 두께(얇은 선 소실 위험이 낮은 구간)라 rasterization 실현성 근거가 된다.

### 3.2 FloorPlanCAD 래스터축 — **설계 정정(정직 고지)**

- 다이제스트 사실: FloorPlanCAD는 **래스터 5,308장 + 벽 bbox/segmask, 벡터 SVG 없음.**
- 제안 원문은 "FloorPlanCAD를 handle 평가에 사용"이라 했으나, **벡터 프리미티브(handle)가 없으면 handle metric의 진리를 줄 수 없다.** 따라서 이 좌석은 설계를 정정한다: **FloorPlanCAD = pixel/segmask metric의 도메인 일반화 점검용(정보성)에 한정**, handle metric의 resolution source는 **synthetic exact mapping + CubiCasa Wall-edge**로만 한다. 이 정정은 §6 Cell F, §8 사망조건에 반영된다. (이것을 숨기면 vision을 슬그머니 SoT로 올리는 것 — 제안 취지에 정면 위배.)

### 3.3 1.dwg 실도면축 (native-DWG) — abstain의 근거지

- 다이제스트 사실: 1.dwg staged DXF 도면정의 384개, B5 탐지기↔silver Pearson 0.2911, full-vs-nb 1.0(레이어명 신호 0), 최대 도면정의 412,775 선분. B3 벽-제로 도면율 0.2135 PASS.
- **여기가 reference_class가 비어 있는 곳**이다(n=0, n_min=5). native-DWG에는 gold handle truth가 없고 silver(Pearson 0.29)뿐이다. 그래서 이 축에서 P4는 **해결 셀이 아니라 관찰 셀**로만 쓴다(§6 Cell F-native). silver를 gold로 승격하는 순간 FM1(Fake PASS)이다.

### 3.4 무엇을 더 가져오는가 (정량 논거)

벡터 방법의 사각(死角)은 **per-handle 지역성**이다. P4가 노리는 것은 **정확히 그 사각의 세 지층**이고, 제안의 prereg가 이 지층을 명시한다: **curved / hatch / single-line**에서 `AUPRC ≥ best_vector + 0.08`.

- **curved(SPLINE/ARC)**: GBDT의 sin2θ/cos2θ 각도특징은 직선을 가정. 실도면은 SPLINE 3,973/ARC 2,198 혼재(B1) — 곡선 벽에서 벡터 각도특징이 무너진다. raster는 곡률과 무관하게 형상으로 본다.
- **hatch**: HATCH 264(B1)는 선쌍이 아니라 채움. "평행 이중선" prior(parallel 가중 0.35, 최대)가 hatch 경계 벽에서 헛돈다. raster는 채움 패턴을 픽셀로 본다.
- **single-line**: 평행 짝이 없는 단선 벽 → parallel 특징=0 → 기하탐지기·GBDT 모두 실명. raster는 단선도 맥락(방 경계 루프)으로 회수 가능.

**핵심 규율(비열등성)**: P4는 이 세 지층에서 +0.08을 노리되 **전체 AUPRC 하락 ≤0.02**를 동시에 지켜야 한다. 즉 "잘하는 곳에서 크게, 전체로는 안 깎이게." handle·geometry를 항상 IR에서 가져오므로 **정밀도(GBDT의 강점 0.86)를 훼손하지 않고** 재현율 갭만 특정 지층에서 메우는 것이 설계 목표다. 이것이 GBDT를 대체하지 않고 **보완**하는 이유다.

**중대한 접속 조건**: P4의 lift 기준선 `best_vector`는 **깨진 v0 기하탐지기(0.2358)가 아니라 개선된 벡터 최선**(GBDT 0.517, 또는 CL-B 커버리지-완전 결정론 v1)이어야 한다. v0 대비 개선은 착시다(§8 참조).

---

## 4. 데이터·컴퓨트 요구

전제: **RTX 5070 Ti 16GB · RAM 64GB · DGX Spark(Ornith-35B) 현재 unreachable(승인됨) · 프런티어 VLM API 미승인.**

### 4.1 로컬 실행 계획 (16GB로 서는 경로 — 게이트/프로브 전담)

- backbone: **SegFormer-B0/B1 또는 U-Net(경량)**, 패치 **512px**, **gradient accumulation**으로 유효 배치 확보(16GB 상한 대응). 512에서 부족하면 1024는 accumulation 확대.
- 데이터: CubiCasa 386만 선분을 **patch-on-the-fly 렌더**(전체 래스터 코퍼스를 디스크에 저장하지 않음 — 저장폭발 회피). RAM 64GB로 fold 인덱스·ID buffer 캐시 수용.
- back-projection·fusion·calibration·mapping 검사는 **CPU-경량**(점수맵·ID buffer만 있으면 산술). Cell A/B/D 전부 로컬 완결 설계.
- **로컬만으로 서는 셀**: Cell A(하네스), Cell B(최저가 프로브), Cell C(경량 backbone 학습), Cell D(융합·보정), Cell E(style holdout, C 재사용). 즉 **결정 게이트 전부가 DGX 없이 돈다.** DGX 불통이 P4의 진행을 막지 않도록 설계한 것이 핵심.

### 4.2 DGX 계획 (승인·도달 후로 격리)

- 대형 image encoder(SegFormer-B4/B5·Mask2Former-Swin 급, 요검증) · **다중 scale sweep** · local open vision encoder fine-tune만 DGX.
- **선결 확인**: DGX Ornith-35B는 LLM이며 **vision backbone 지원 여부 미확인(T13)**. 확인 전 DGX arm 착수 금지. 미확인이면 로컬 경량 결과가 최종 판정선.
- **NC 격리**: NC 라이선스로 학습된 checkpoint는 **별도 registry**에 격리, 제품 weight 경로와 물리 분리(kill condition). DGX 여부와 무관하게 강제.

### 4.3 자산 활용·주의

- qwen2.5-VL-3B floorplan SFT/GRPO(로컬 실존)는 **VLM 경로(P5)** 자산 — P4의 코어는 분할 encoder이지 VLM이 아니므로 라인 혼선 방지 위해 P4에서는 쓰지 않는다(차별점 §8).
- Zenodo10K/Text2CAD/ArchCAD/pseudo-floor-plan-12k(로컬)는 raster 사전학습 보강 후보이나 **라이선스·도메인갭 사전 확인 전 미사용**.

---

## 5. 구현 계획

### 5.1 기존 도구 접속점 (다이제스트가 규정한 기능 역할 기준)

- **cubicasa_ir** — SEG-IR 변환기. P4는 이걸 읽어 (a) 래스터+ID buffer 렌더 입력, (b) handle 집합·Wall 진리 라벨 획득.
- **cubicasa_ml** — HistGradientBoosting 학습기(6특징 386만행 → val P0.86/R0.37/F1 0.517/AUC 0.9215). P4의 **vector branch**. 산출 per-handle 확률을 `vector_score`로 그대로 소비(재학습 불필요).
- **fast_score** — NumPy 동치 고속 채점기(기하탐지기). `best_vector` 기준선·지층 라벨 산출 보조.
- **evidence_grid** — 다증거 격자(CL-B). `raster_score`를 **추가 증거 채널**로 격자에 삽입하거나, 격자의 결정적 산출을 P4가 넘어야 할 CL-B 기준선으로 사용.

### 5.2 신규 모듈 골격 (제안)

```
render_ir.py        IR → (multi-scale linework raster, ID buffer). CRS contract 내장. cubicasa_ir 기하 재사용.
backproject.py      (M, B) → handle별 raster_score. 결정적. mapping/CRS 자기검사 포함(Cell A 하네스).
seg_model.py        분할 학습/추론(SegFormer/U-Net, PyTorch). loss·augmentation.
fuse_calibrate.py   held-out 융합(vec⊕ras), Brier·REL/RES·reliability diagram.
wsd_eval_p4.py      render manifest·CRS contract·model hash 동결 → wsd_eval_p4.json 방출(resolution trigger).
```

### 5.3 예상 개발 규모·위험 집중점

- 결정적 부분(render_ir + backproject + 하네스)이 **위험의 90%**. 여기가 exact하지 않으면 학습은 의미 없음 → 최우선·테스트-우선 개발.
- seg_model은 표준 학습 루프(위험 낮음). fuse_calibrate는 소규모. wsd_eval_p4는 동결·해시 규율(계약 산출물).
- 규모 감각: 신규 5모듈, 그중 render_ir/backproject가 무겁고 나머지 3은 경량. 전체는 "한 명이 며칠~1~2주"급(정확 산정은 실착수 시).

---

## 6. 실험 셀 정의

원칙 준수: **val=개발·튜닝 허용, test=방법당 단발, 합격선 사전 봉인(prereg), 셔플 대조군 의무, 증거 xlsx 의무, 실패도 사유와 함께 기록.** 셀은 **최저가→고가의 게이트 사다리**로 배열하고, 앞 셀의 kill이 뒷 셀을 차단한다(FM5 spawn storm 방지: 하나 통과해야 다음).

### Cell A — 역투영·CRS 정합성 하네스 (결정적, 학습 이전 게이트)
- **가설**: §2.2 렌더+ID buffer가 픽셀↔handle을 exact하게 왕복한다.
- **지표**: mapping_accuracy, crs_err, "픽셀 0개 handle 비율".
- **합격선(prereg)**: mapping_accuracy ≥ **0.995**, crs_err ≤ **0.5%**.
- **킬**: 미달 시 즉시 중단 — back-projection 전제 붕괴(P4 사망조건 1). T24 직결.
- **예산**: 로컬 CPU, <반나절. **시드**: 데이터 시드 고정, 학습 없음(결정적).

### Cell B — 최저가 프로브 (200 synthetic block × 4 render style)
- **가설**: 작은 분할모델이 **curved·single-line subset**에서 P2/P3(벡터)가 놓친 것을 회수한다.
- **지표**: 해당 subset의 handle AUPRC(P4) vs best_vector, + Cell A 지표 재확인.
- **합격선(prereg)**: curved·single-line subset AUPRC ≥ **best_vector + 0.08**(제안 밴드).
- **킬**: 이 최저가 지층에서도 lift 없으면 → raster 이득 가설 기각, 상위 셀 중단.
- **예산**: 로컬 GPU 경량, ~1일. **시드**: model init 3시드 × 고정 데이터 split.
- **선결 의존**: 200 synthetic block과 4 style은 **PR-1 생성기(T2)** 산출물. 현재 합성팩은 LINE/LWPOLYLINE/INSERT 3종·B1 충실도 FAIL(KS 0.5792)이라 **curved/hatch를 담지 못한다** → Cell B는 PR-1이 SPLINE/ARC/HATCH를 담고 T2 fidelity 게이트를 통과할 때까지 **BLOCKED**.

### Cell C — CubiCasa raster→handle 학습·평가 (본진, 벡터축 handle metric)
- **가설**: CubiCasa train(4,200)에서 학습한 raster branch를 back-project하면 val(400)에서 지층별 lift가 재현된다.
- **지표**: val handle AUPRC/F1, **지층 층화**(curved/hatch/single-line/straight), pixel metric 병기.
- **합격선(prereg)**: 전체 val AUPRC 비열등(vs best_vector **하락 ≤0.02**) **AND** curved/hatch/single-line 각 지층 **≥ best_vector+0.08**. 셔플 대조군 AUC ≈ 밑변(누출 0) 동반 필수.
- **킬**: 전체 하락 >0.02, 또는 back-projection err >0.5%, 또는 셔플 대조군이 신호를 보이면(누출).
- **예산**: 로컬 SegFormer-B0/B1 512px+accum; 대형은 DGX 대기. **시드**: model 3시드, building-unit split(CubiCasa fold 상속), **test 400 무접촉(단발)**.

### Cell D — vector⊕raster 융합·보정 (Brier / REL·RES)
- **가설**: held-out calibration 융합이 두 branch 중 최선보다 지층 AUPRC를 올리고 잘 보정된다.
- **지표**: 융합 val AUPRC, **Brier**, Murphy **REL/RES**, reliability diagram, ECE.
- **합격선(prereg)**: **REL ≤ 0.04**, **RES ≥ 0.02**, 융합 AUPRC ≥ max(GBDT, raster)(목표 지층), 전체 비열등 유지.
- **킬**: 융합이 전체를 vs GBDT >0.02 악화, 또는 REL >0.04(보정 실패).
- **예산**: CPU-경량(branch 확률 캐시 후). **시드**: calibration-split 5-fold 리샘플(점 추정 아닌 분포로).

### Cell E — render-style OOD holdout (leakage·과적합 시험)
- **가설**: 한 style family를 통째 hold out해도 성능이 크게 안 무너진다(= 렌더러가 아니라 벽을 학습).
- **지표**: unseen-style AUPRC 하락. + **0벽/전벽 sentinel**과 recall 최저선(T7 의무).
- **합격선(prereg)**: unseen render-style AUPRC 하락 ≤ **0.10**. sentinel 통과.
- **킬**: 하락 >0.10(style 탐지기로 전락) → OOD 사망조건.
- **예산**: 로컬, Cell C 학습 재사용. **시드**: leave-one-style-out(style 수만큼 회전).

### Cell F — 외부 일반화 관찰 (FloorPlanCAD 픽셀 · native-DWG abstain, **비해결 셀**)
- **F-pixel**: FloorPlanCAD 5,308장에서 **pixel/segmask AUPRC만** 보고(벡터 SVG 없음 → handle metric 불가, §3.2). **게이트 아님, 정보성.** vision을 SoT로 올리지 않기 위해 명시적으로 non-resolving.
- **F-native**: 1.dwg 몇 개 def에서 silver(Pearson 0.29)와 정성 교차만. **resolution 셀 아님** — reference_class n=0<n_min=5이므로 claim 판정 불가, abstain 유지(FM1 방지).
- **예산**: eval-only 로컬. **시드**: N/A(비해결).

**셀 수 판단**: 결정적 하네스(A)·최저가 프로브(B)·본진 학습(C)·융합보정(D)·OOD(E)·외부관찰(F) = 6셀. 제안의 5개 prereg 조건(지층 lift/전체 비열등/mapping/OOD/REL·RES)이 각각 A·B·C·D·E에 1:1로 매핑되어 과소도 과잉도 아니다. resolution_criterion("다섯 조건 모두 참")은 A∧C∧D∧E가 전부 PASS이고 mapping(A)이 성립할 때만 충족.

---

## 7. red team 티켓 응답

P4(=CL-G 래스터/VLM 이중 트랙, 조건부 VIABLE)에 걸리는 OPEN 티켓과 이 좌석의 입장. (전체 34건 중 이 제안에 결속된 것만; 상세 per-proposal 원문은 `seats/red_teamer.md` §2–3에 있고 이 패킷엔 요약만 실려 있어, 식별 가능한 것에 한해 응답한다.)

- **T24 — 픽셀→핸들 역투영 exact 하네스 (CRS kill risk, R23).** **[해소]** Cell A를 **학습 이전의 무조건 게이트**로 승격(mapping≥0.995, crs_err≤0.5%). 통과 못 하면 P4 전체 중단. 제안의 kill condition과 일치.
- **T2 — 합성 생성기 부재(0.70, 공격 B).** **[의존 수용]** Cell B의 200 synthetic block × 4 style은 **PR-1 생성기 + T2 fidelity 게이트** 산출물에 의존. 현재 합성팩은 3종 엔티티·B1 FAIL(KS 0.5792)이라 curved/hatch를 못 담음. → Cell B는 **BLOCKED on PR-1**로 명시(날조된 진행 금지).
- **T1 — 대리(proxy) 독립성(0.75, 최우선, 공격 A).** **[부분 해소 + 위험 인정]** raster branch(픽셀 맥락 학습)는 벡터의 "평행 이중선" prior를 **명시적으로 인코딩하지 않으므로** 대리 독립성을 오히려 높이는 방향이다. **그러나** CubiCasa Wall 라벨이 사람의 "두꺼운 평행구조=벽" 관례로 그려졌다면 raster proxy가 상관된 prior를 상속할 수 있다. → 독립성은 **CL-E(train{합성/외부/silver}×eval) 대각/비대각 구조**로 계량 측정. 완전 독립 주장은 하지 않고 측정으로 회부(정직).
- **T5 — 라이선스/NC(0.65, 공격 D, PR-3).** **[수용·차단조건]** FloorPlanCAD/CubiCasa NC 라벨+원도면 권리 미해결. **NC-trained checkpoint 별도 registry 격리·제품 weight 경로 분리(kill)**. **PR-3 counsel 서면 클리어 전 제품경로 학습 arm 착수 금지.** 연구-only 격리 학습은 가능하나 제품 승격은 서면 후.
- **T6 — 평가 단위 per-handle vs 집합조립(0.60, 공격 E).** **[해소]** P4의 최종 resolution은 **handle metric(per-handle)** 으로 선언(제안 원문 일치). back-project가 픽셀을 handle로 되돌리므로 평가 단위가 handle로 고정 — 공격 E의 안전한 쪽.
- **T7 — metamorphic sentinel(0.50, 공격 F).** **[해소]** Cell E에 **0벽/전벽 sentinel + recall 최저선**을 랭킹 사용 전 탑재. 위반율-only 밴드가 "0벽 탐지기"를 통과시키는 구멍을 막음.
- **T13 — DGX Ornith vision 지원 확인.** **[수용·격리]** DGX arm은 vision 지원 확인 후로 격리. 로컬 경량 경로가 모든 결정 게이트를 독립 수행하도록 설계(§4.1)해 미확인이 진행을 막지 않게 함.
- **T34 — load-bearing 인용 experiment_executed:false 재-status.** **[준수]** 이 도시에의 수치 주장은 전부 패킷 다이제스트 산출 또는 다이제스트 밑변 산술(§2.6)뿐이며, R-레인 인용에 의존하지 않는다. 문헌 방법론은 §1에서 `요검증` 표기.
- **모순 #1(silver 게이트 식별자).** **[부수 무관]** P4는 silver를 **학습 타깃으로 쓰지 않는다**(handle/pixel truth로 학습). 따라서 "B1≥0.70 AND B4≥0.70" silver 자격 논쟁(P5 소관)에 P4의 학습은 걸리지 않는다. 이 점에서 feyerabend P3/CL-K의 anti-silver 취지와 정합.

---

## 8. 인접 제안과의 관계 (병합·차별·사망 조건)

### 8.1 병합 지점

- **CL-B(커버리지-완전 결정론 v1)**: `raster_score`를 evidence_grid의 **추가 증거 채널**로 삽입 가능 → P4를 독립 파이프라인이 아니라 CL-B 격자의 한 채널로 흡수하는 경량 병합. **단, 그러면 P4의 기준선이 CL-B가 되어 넘기 더 어려워진다(정직).**
- **CL-F(학습 사다리 GBDT→GNN)**: P4의 vector branch가 곧 CL-F의 GBDT(0.517). fusion에서 두 제안이 만난다.
- **CL-E(truth-source 교차요인)**: P4 raster proxy의 독립성을 CL-E가 계량. T1 응답의 측정 위탁처.

### 8.2 차별점

- **vs P5(프런티어 VLM 배심/silver)**: P4=**학습된 경량 분할 encoder + 결정적 back-projection**, SoT는 벡터. P5=프런티어 VLM 프롬프트·silver. P4는 silver·VLM·API 결재에 **의존하지 않는다**(로컬 완결). 이것이 P4를 P5보다 먼저·싸게 돌릴 수 있는 이유.
- **vs feyerabend P5("래스터 본선")**: P4는 래스터를 **본선이 아니라 보조 증거**로 둔다(handle/geometry는 항상 IR). "본선" 프레임은 PARKED(T31).

### 8.3 이 제안이 죽어야 하는 조건 (정직하게)

1. **하네스 붕괴**: Cell A에서 mapping<0.995 또는 crs_err>0.5%를 고칠 수 없으면 → "결정적 back-projection" 전제가 무너져 **P4 사망**(load-bearing 가정).
2. **CL-B에 흡수됨**: CL-B 커버리지-완전 결정론 v1이 curved/hatch/single-line 지층을 이미 P4의 +0.08 이내로 회수하면 → P4의 한계이득 소멸 → **PARK/사망**(T31 — 래스터는 결정론이 못 넘는 회수를 실증할 때만 산다).
3. **비열등성 실패**: 전체 AUPRC 하락 >0.02면 → 융합이 득보다 실 → **사망**.
4. **style 과적합**: unseen render-style 하락 >0.10이면 → raster branch가 벽이 아니라 렌더러를 학습 → **사망**(Cell E kill).
5. **라이선스 영구 차단**: PR-3가 끝내 NC를 못 풀면 → CubiCasa 의존 raster-representation이 **제품경로로 못 감** → 제품 P4 사망(연구-only 격리로만 잔존).
6. **empty reference class 미충족**: PR-1 생성기가 fidelity 게이트를 끝내 못 넘으면 → exact handle truth 부재 → resolution trigger(`wsd_eval_p4.json`) 생성 불가 → claim은 **영구 abstain**(참조 사례 0이 채워지지 않음). 이 경우 P4는 "기각"이 아니라 "**판정 불능**"으로 남는다 — calibration 좌석은 이 구분을 끝까지 지킨다.

### 8.4 좌석 최종 입장

P4는 **GBDT를 대체하는 야심작이 아니라, 벡터가 구조적으로 실명하는 세 지층(curved/hatch/single-line)을 결정적 back-projection으로 안전하게 보완하는 좁은 수술**이다. 그 수술이 정당화되려면 (i) 하네스가 exact하고(A), (ii) 최저가 프로브에서 지층 lift가 실재하며(B), (iii) 전체 비열등·OOD·보정 게이트를 동시에 통과(C·D·E)해야 한다. 이 좌석은 **점 확률을 유보(abstain)** 하되 밴드는 봉인했고, 상향/하향 증거를 사전 약정했다. 참조 사례가 n_min=5에 도달하기 전에는 어떤 PASS도 선언하지 않는다.

DOSSIER_COMPLETE: calibration_P4
