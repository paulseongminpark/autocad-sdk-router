# E2 방법론 심층 도시에 — platt_P5

**좌석(seat)**: `platt_P5` · **제안**: P5 — VLM 이중 트랙(프런티어 배심원 vs 로컬 래스터 분할), vision 레인 · 가설 H4
**작성 원칙**: 수치는 패킷 다이제스트(2026-07-18 세션 도구 출력)만 인용. 문헌 일반지식 수치는 `(문헌·요검증)`으로 표기. 웹 검색 미사용. git·서브에이전트 미사용.

---

## 요약 — 이 도시에가 내리는 5개의 날 선 판단 (먼저 읽어야 할 결론)

이 절은 뒤 8절의 결론을 앞으로 당겨, 결재자가 사슬 없이 요지만 봐도 방향을 잡게 한다. 각 판단의 "왜"는 해당 절에서 푼다.

1. **P5의 사활은 vision 품질이 아니라 브리지다.** "래스터→벡터 역투영(back-projection: 그림 픽셀을 다시 CAD 선분 핸들로 되돌리는 사상)"이 안 되면 아무리 잘 보는 모델도 무용지물이다. 그래서 **가장 먼저·가장 싸게 검증할 것은 vision이 아니라 브리지**이며, 그 시험대는 합성 렌더(pixel↔handle 맵을 우리가 쥔 유일한 자료)다. 킬 게이트: 합성 역투영 핸들 F1 < 0.4 → 양 트랙 동시 종료.

2. **로컬 qwen2.5-VL-3B(플로어플랜 SFT/GRPO 파인튜닝 모델, 로컬 실존)가 5a의 프런티어-API 게이트를 우회시킨다.** 다이제스트 자산 목록상 프런티어 VLM API는 "유일 결재 게이트(미승인)"지만, 5a의 핵심 실험(cheapest probe·브리지 검증·이름-맹 배심)은 **전량 로컬**로 돌릴 수 있다. 최대 블로커가 실은 선택지다.

3. **세 축의 역할이 서로 다르다 — 혼동이 곧 오설계.** CubiCasa SEG-IR = **벡터** 축(진리=Wall 클래스 모서리, px 좌표), FloorPlanCAD = **래스터+segmask**축(벡터 SVG 없음 → 5b 픽셀 모델 훈련 전용, 역투영 불가), 합성팩 = **브리지 검증** 축(pixel↔handle 맵 보유). 즉 5b는 FPC로 배우고, 브리지는 합성에서 검증하고, 벡터 성적은 CubiCasa를 렌더링해 채점한다.

4. **정직한 게이트 정정(반대의견 #1 수용).** 프런티어 VLM을 "silver 배심원"으로 편입하는 게이트는 platt(=나)가 앞서 인용한 "E1.5 B1≥0.70"이 아니라 calibration의 **"B1(well-posed)≥0.70 AND silver-Pearson≥0.70"**이 원문(prereg_e15.json) 기준 정확하다. 현재 가시적 수치(현행 wave의 B5 탐지기↔silver Pearson 0.2911)는 0.70에 한참 못 미치고 합성 충실도 B1은 KS 0.5792로 FAIL이다. **따라서 5a는 지금 silver 배심원 자격이 없다** — 진입한다면 "이름-맹 타이브레이커"로만 가능. 나는 platt의 종전 인용을 수정 대상으로 인정한다(T10 부수).

5. **P5의 고유 가치는 '제3의 직교 증거축'이다 — 단, 조건부.** 탐지기(순수 기하)와 silver(이름-의미) 두 축은 이미 대체로 독립(B5 Pearson 0.2911, full-vs-nb 1.0)임이 실측됐다. P5는 여기에 **시각적 외형(appearance)**이라는 셋째 축을 더한다. 이게 성립하려면 (a) 브리지가 돌고 (b) vision 오류가 "평행 이중선 prior"와 실제로 탈상관이어야 한다. (b)는 공짜가 아니다 — 벽은 시각적으로도 평행 이중선이라 prior가 새어들 수 있다. 이 정직한 한계가 T1(대리 독립성)에 대한 P5의 부분적 응답이다.

**한 줄 결론**: P5는 "싸고 로컬인 브리지 검증"을 먼저 통과하면 프로그램에 유일하게 없는 직교 증거축과 H3(관례 지배)의 공짜 교차검증기를 준다. 통과 못 하면 vision 품질과 무관하게 죽어야 한다.

---

## 1. 이론적 근거·선행연구

P5는 세 갈래의 방법론 계보에 기댄다. 각 계보에서 P5가 빌리는 정확한 구성요소를 명시한다.

### 1.1 래스터 의미 분할(semantic segmentation) 계보 — 5b의 뿌리

- **FCN / U-Net / DeepLab 계열**: 픽셀 단위 분류. U-Net(Ronneberger et al., 2015, 의료영상 — 문헌 일반지식)의 인코더-디코더 + skip-connection 구조는 얇은 경계(벽 윤곽처럼 가는 구조)를 살리는 데 강해, 벽-픽셀처럼 "가늘고 길고 희소한(다이제스트: CubiCasa 벽 선분율 ~11.8%)" 타깃에 적합하다. DeepLab의 atrous/dilated conv(문헌 일반지식)는 poché(벽 속을 검게 채운 표현)처럼 넓은 채움 영역과 가는 선을 동시에 봐야 할 때의 수용장(receptive field) 조정에 쓰인다.
- **SegFormer(Xie et al., 2021, 계층적 트랜스포머 인코더 + 경량 MLP 디코더 — 문헌·요검증)**: 제안이 지명한 "SegFormer-B0급" 소형 백본. B0은 파라미터가 작아(대략 수백만 급 — 문헌·요검증) 16GB GPU에서 학습 가능하고, 멀티스케일 특징이 도면의 다양한 축척(다이제스트: CubiCasa는 도면별 축척 미상, 2~15mm/px)에 견고할 여지를 준다.
- **왜 이 계보인가**: 다이제스트가 보여준 실패의 핵심은 "순수 기하 prior의 무력"이다. 기하 탐지기 v1은 CubiCasa 전이에서 val F1 0.2358(P 0.134 ≈ 기저율 0.118, R 0.981), 물리 두께 prior가 축척 전 구간에서 무감, FP 주범이 Direction 화살표/BoundaryPolygon/Door/Window/DimensionMark(전부 "대역 내 평행 구조"). 이들은 **기하적으로는 벽 같지만 의미적으로 아닌 것들**이다. 분할 모델은 두께·평행뿐 아니라 **연결성·둘러쌈(enclosure)·외형·문맥**을 보므로, 순수 기하가 못 거르는 평행-비벽을 외형으로 기각할 잠재력이 있다. 이것이 GBDT의 P 0.860/R 0.370(F1 0.517)가 남긴 재현율 여백을 공략할 이론적 근거다.

### 1.2 플로어플랜 특화 파싱 & 래스터→벡터 계보 — 브리지의 뿌리

- **CubiCasa5k(Kalervo et al., 2019 — 문헌·요검증)**: 우리가 외부셋으로 보유·SEG-IR 변환한 바로 그 데이터셋. 다중과업 분할로 벽/방/아이콘을 파싱한 계보. 진리=Wall 클래스 요소.
- **FloorPlanCAD(Fan et al., 2021, CAD 도면 위 panoptic symbol spotting — 문헌·요검증)**: 우리가 래스터 5,308장+벽 bbox/segmask로 보유한 데이터셋. CAD 벡터 위 심볼 스포팅 계보(PanCADNet/CADTransformer류 — 문헌·요검증)는 "벡터 엔티티에 의미 라벨 붙이기"라는 P5의 최종 목표와 정확히 같은 문제다.
- **Raster-to-Vector(Liu et al., 2017, "Raster-to-Vector: Revisiting Floorplan Transformation" — 문헌·요검증)**: 래스터 도면에서 벽 벡터를 복원하는 계보. **역투영(브리지)의 직접적 선행연구.** 다만 P5의 브리지는 "새 벡터를 생성"하는 게 아니라 "기존 CAD 핸들에 벽/비벽 라벨을 되돌려 붙이는" 사상이라 더 쉽다(생성이 아니라 분류·정합).
- **Segment Anything(SAM, Kirillov et al., 2023 — 문헌·요검증)**: 프롬프트형(promptable) 분할. 5a에서 VLM이 낸 대략적 벽 영역을 SAM류로 정밀화하거나, 제로샷 마스크 제안기로 쓸 후보. (필수 아님 — 옵션.)

### 1.3 VLM 판정·앙상블·불변성 계보 — 5a와 배심 편입의 뿌리

- **VLM 그라운딩/판정(LLM/VLM-as-judge — 문헌 일반지식)**: 프런티어 VLM에 렌더 이미지를 주고 "벽 영역 polygon+판정"을 받는 것. 우리 로컬 자산 qwen2.5-VL-3B는 이미 플로어플랜 SFT/GRPO로 파인튜닝돼 이 과업에 특화돼 있다(다이제스트 자산).
- **관찰자 간 신뢰도 · 앙상블**: Fleiss' κ(다수 평정자 일치도 — 문헌 일반지식)로 배심 편입 전후 앙상블 일치도 변화를 측정. E1.5 silver 판정자 5기가 **2어휘 가문(fable+sol vs opus+sonnet+grok)**으로 갈려 "5독립 아님, ~2가문"이라는 다이제스트 실측이 있으므로, P5가 더할 vision 배심원이 **기존 어휘 가문과 독립인지**(즉 셋째 가문인지)가 κ 상승의 진짜 원천인지 순열 검정(permutation test — 문헌 일반지식)으로 걸러야 한다.
- **변형 검사(metamorphic testing, Chen et al. 계열 — 문헌·요검증)**: 라벨 없이 "입력을 규칙대로 바꾸면 출력도 규칙대로 바뀌어야 한다"는 관계로 정답 없이 검증. P5의 배심 가치 밴드가 "divergent를 metamorphic-정합으로 해소"를 요구하는 근거. CL-D 배터리에 접속.
- **render-and-compare / analysis-by-synthesis(문헌 일반지식)**: 우리가 생성기로 렌더를 만들면 pixel↔handle 대응을 우리가 쥐게 되어 **사람 라벨 0으로 진리 사슬이 닫힌다**. 이것이 브리지를 합성에서 선검증하는 이론적 정당화다.
- **내부 판례 R23**: "vision-as-SoT 기각, VLM은 배심원(진리원 아님)". P5의 설계 불변식 — vision은 결코 진리원이 되지 않고 결정론 게이트가 SoT다.

---

## 2. 알고리즘 정확 스펙

P5는 **공통 브리지** 하나 위에 **두 프런트엔드(5a 프롬프팅, 5b 학습)**를 얹는다. 브리지가 공통 병목이자 킬 게이트이므로 먼저 스펙한다.

### 2.0 공통 브리지 — 픽셀→핸들 역투영 `backproject`

렌더는 우리가 만든 아핀 사상 `T: world(모델좌표) → pixel`이다. 우리가 렌더하므로 `T`(및 그 역 `T⁻¹`)를 안다. 이것이 브리지가 원리상 풀리는 이유다.

```
입력:
  entities E = {(h_i, geom_i)}      # 후보 벡터 엔티티(핸들 h_i, 선분/폴리라인 geom_i)
  T                                 # world→pixel 아핀(렌더 시 확정)
  W                                 # 벽 신호맵. 5b면 per-pixel 확률맵 mask∈[0,1]^{H×W};
                                    #             5a면 벽 polygon 합집합의 지시맵 poly∈{0,1}^{H×W}
  lw_px, τ, min_px                  # 렌더 선폭(px), 벽 판정 임계, 최소 footprint 픽셀 수
출력:
  {(h_i, wall_score s_i, wall_member m_i, conf c_i)}

for each entity (h_i, geom_i):
    footprint P_i = rasterize_stroke(T(geom_i), width=lw_px)   # 이 엔티티가 렌더에서 차지하는 픽셀 집합
    if |P_i| < min_px:  continue                                # 렌더에 안 잡힌 미세 엔티티 스킵(로그)
    s_i = mean_{p in P_i} W[p]                                  # footprint 위 벽 신호 평균
    # poché 다의성 완화: footprint가 채움영역과 겹치면 후보 다중화 + 신뢰도 하향
    overlap_fill = fraction(P_i inside filled_region(W))
    c_i = 1 - overlap_fill                                      # 채움 겹침이 클수록 신뢰↓
    m_i = 1[s_i ≥ τ]
```

- **합성에서의 진리**: 생성기가 emit한 pixel↔handle 맵으로 각 `h_i`의 진짜 벽/비벽을 알므로, 위 `m_i`와 대조해 **역투영 핸들 F1**을 직접 측정한다. 이 F1이 킬 게이트(<0.4)와 통과선(≥0.6)의 대상.
- **실도면에서의 적용**: `T`는 우리가 def 크롭을 렌더할 때 확정. CubiCasa/1.dwg는 진짜 진리가 (CubiCasa=Wall 클래스, 1.dwg=silver/탐지기 대조)로 온다.
- **크롭 경계 벽 절단 완화**: 오버랩 타일링(overlap 0.5 — 탐지기 기존 overlap 0.5와 정합), 타일 경계 핸들은 인접 타일 신호를 합산.

### 2.1 5b — 래스터 분할 학습

**모델**: SegFormer-B0 또는 U-Net(ResNet18 인코더) — 둘 다 16GB에 적합(문헌·요검증). 이진 분할(벽 vs 배경).

```
입력 x: 렌더/FPC 래스터 타일 (예: 512×512, 채널=1 grayscale 또는 3 RGB)
출력 ŷ: per-pixel 벽 확률 mask ∈ [0,1]^{512×512}
손실 L = Dice(ŷ, y) + λ · wBCE(ŷ, y)
   # 벽 픽셀 ~11.8%(다이제스트) → 클래스 불균형. wBCE 양성가중 또는 focal loss로 대체(ablation).
```

**하이퍼파라미터 공간**:
- backbone ∈ {SegFormer-B0, U-Net-R18}; 대형(SegFormer-B5)은 5b 생존 후 DGX에서만.
- 입력 해상도 ∈ {512, 1024, 타일512-overlap0.5}
- lr ∈ [1e-4, 1e-3], optimizer=AdamW, epochs 튜닝, batch=16GB에 맞춤(8~16)
- loss λ ∈ {0.5,1,2}, {Dice+wBCE vs focal}
- augmentation: 회전·이동·반사·스케일(B4 불변성 의도 정합) + 렌더 스타일 노이즈(선폭·poché 유무·노이즈 — 다이제스트 leakage 방지 항)
- 역투영: lw_px, τ, min_px, poché 처리

**추론→역투영**: `mask = seg(x)` → §2.0 `backproject(E, T, mask, ...)` → 핸들 집합.

### 2.2 5a — 프롬프팅 배심원

```
render = visual_report/render(def_crop)         # 라우터 render 경로 재사용
resp   = VLM(render, prompt="벽 영역을 polygon으로, 각 영역에 벽 확신도")
polys  = parse_polygons(resp)                   # 실패 시 재프롬프트 1회 후 abstain
W_poly = rasterize_union(polys)
handles = backproject(E, T, W_poly, ...)        # §2.0 공통 브리지
```

- **VLM 선택 순서**: (1) 로컬 qwen2.5-VL-3B(무과금·데이터 반출 0) → (2) DGX Ornith-35B(vision 지원 확인 시 — **가정 플래그**) → (3) 프런티어 API(승인 시). temperature=0(결정성).
- **프롬프트**: 렌더에 레이어명·블록명 텍스트를 넣지 않는다(이름-맹 보장 — H3 교차검증의 원천).

### 2.3 배심 편입 — 1석만(R23 정합)

```
jury_vote(h) = m(h) from 5a and/or 5b          # 벽/비벽 + 신뢰도
ensemble = E1.5_silver_ensemble ∪ {vision_seat(weight=1)}   # 정확히 1석
Δκ = FleissKappa(ensemble) - FleissKappa(E1.5_silver_ensemble)
p  = permutation_test(Δκ, shuffles=1000)        # κ 상승이 우연인지
divergent_resolved = |{d in divergent20 : vision이 metamorphic-정합으로 해소}| / 20
```

**출력·손실 요약**: 5b는 픽셀 분할손실(Dice+wBCE), 5a는 학습 없음(프롬프트+파싱). 공통 산출은 **per-handle `wall_member(h)`**(T6/CL-C 평가단위 정합) + 신뢰도 + 배심표.

---

## 3. 벽 과업 적응 설계 — 실제 하네스 3축 접속

전이 실패 **F1 0.236**과 GBDT **F1 0.517**을 아는 상태에서, P5가 "더 가져오는 것"을 축별로 명시한다.

### 3.1 CubiCasa SEG-IR (벡터 축) — "무엇을 더 가져오나"의 정량 시험대

- **접속**: `ext/cubicasa_ir.py`가 만든 벡터 IR(레이어 중립, 라벨 누출 0, 진리=Wall 클래스 모서리, px 좌표)을 **렌더**해 5b/5a에 통과 → `backproject` → 핸들 F1을 **CubiCasa val(400도면, 35.4만 선분)**에서 채점. test(400도면)는 단발 원칙으로 봉인.
- **더 가져오는 것(구체)**: 기하 탐지기·GBDT의 FP 주범은 전부 "대역 내 평행 구조"(Direction 화살표/BoundaryPolygon/Door/Window/DimensionMark). 이들은 **외형·문맥으로는 벽과 다르다**(화살표는 열린 획, 문/창은 특유 심볼, 치수선은 텍스트·틱 동반). vision은 이 외형 차이를 보므로 **평행-비벽 FP를 기각**해 GBDT가 남긴 재현율 여백(R 0.370)을 회수할 잠재력이 있다.
- **축척 무감 문제와의 관계**: 기하 탐지기의 물리 두께 prior가 2~15mm/px 전 구간 무감이었다. vision은 **상대 두께(픽셀 비율)**를 보므로, 정규화 DPI로 렌더하면 절대 축척 미상에 덜 휘둘릴 여지가 있다(가설 — Cell 4에서 검정).
- **정직한 리스크**: CubiCasa엔 벡터가 있으나 **우리가 렌더해서 다시 역투영**하는 왕복이 필요하다 → `T`는 우리가 쥐지만, 렌더 스타일이 CubiCasa 원 표현과 다르면 도메인 갭. 그래서 브리지는 **합성에서 선검증**(Cell 2)한 뒤에만 CubiCasa에 발언권.

### 3.2 FloorPlanCAD (래스터+segmask 축) — 5b의 유일한 지도학습 연료

- **접속**: FPC 래스터 5,308장 + 벽 bbox/segmask로 5b 픽셀 모델을 **지도학습**(`vision/seg_train.py`). 
- **결정적 제약**: FPC는 **벡터 SVG가 없다**(다이제스트 자산). 따라서 FPC에서는 **역투영이 불가능**하다(되돌릴 벡터 핸들이 없음). FPC의 역할은 오직 **픽셀 모델 학습**과 **wall-pixel IoU 측정**까지다. 브리지 검증은 반드시 합성에서, 벡터 성적은 CubiCasa 렌더에서.
- **더 가져오는 것**: 사람 라벨(제3자) 기반이라 **silver(LLM)와 독립인 학습 신호**다. feyerabend의 anti-silver 우려(반대의견 #2)와 정합 — 5b는 silver를 타깃으로 쓰지 않는다.
- **NC 방화벽**: FPC 라벨은 NC(비상업) → 5b 가중치는 **연구 계측기 전용, 제품 반입 금지**. 레인 승리 시 클린 데이터 재훈련을 별도 결재로. PR-3(counsel) 클리어 전 5b 착수 금지.

### 3.3 1.dwg 실도면 (384 도면정의 축) — 최종 배심 가치 시험대

- **접속**: def 크롭을 라우터 `cad_visual_report`/render로 렌더 → 5a/5b → `backproject` → **탐지기/silver와 대조**(B5 상관 프레임 재사용). divergent-20이 핵심 표적.
- **더 가져오는 것 — 두 가지**:
  1. **H4(vision 생사)**: 벡터 측이 못 푸는 divergent를 래스터가 metamorphic-정합으로 푸는가.
  2. **H3(관례 지배)의 공짜 교차검증**: 탐지기는 이미 이름-맹(B5 full-vs-nb 1.0, 레이어명 신호 0). 그러나 **silver(LLM)는 레이어명·블록명을 읽는다**. P5의 래스터 배심원은 **물리적으로 이름을 못 본다** → 이름-맹 배심(vision) vs 이름-읽는 배심(text silver)의 델타가 곧 silver의 이름-prior 탑승량. 이건 P6(관례 계측)와 독립인 둘째 측정.
- **연산 병목 인지**: 최대 도면정의 412,775 선분(다이제스트). 거대 def는 타일링 렌더로 분할. 역투영은 `fast_score`식 NumPy 벡터화 재사용.

### 3.4 "제3의 직교축" 주장의 정직한 경계

두 기존 축(탐지기 기하 vs silver 의미)은 실측상 대체로 독립(B5 Pearson 0.2911). P5가 셋째 축(외형)이 되려면 vision 오류가 **평행-이중선 prior와 탈상관**이어야 하는데, 벽은 시각적으로도 평행 이중선이라 **prior가 부분적으로 샌다**. 그러므로 P5의 독립성 주장은 **이름축(H3)에서는 강하고(구조적으로 이름을 못 봄), 기하축에서는 부분적**이다. 이 경계를 Cell 5에서 오류-상관으로 정량한다.

---

## 4. 데이터·컴퓨트 요구 — 로컬/DGX 분리

전제(다이제스트): RTX 5070 Ti 16GB · RAM 64GB · DGX Spark(Ornith-35B) 현재 unreachable(승인됨) · 프런티어 VLM API 미승인.

### 4.1 로컬 실행 계획 (16GB/64GB — P5 핵심 전부 로컬 가능)

| 작업 | 자원 | 근거 |
|---|---|---|
| 합성/실도면 렌더 | CPU | 라우터 render 경로, 병렬 IO |
| 5b 소형 분할 학습(B0/U-Net-R18, 512res) | 5070 Ti 16GB | 소형 백본, batch 8~16, 타일링으로 메모리 관리 |
| 로컬 qwen2.5-VL-3B 추론(5a) | 5070 Ti 16GB | 3B급은 16GB에 적재 가능(정밀도 조정 시 — 요검증) |
| 역투영·채점 | CPU/NumPy(RAM 64GB) | `fast_score` 벡터화 재사용; 412,775 선분은 타일 |
| FPC 5,308장 로딩·CubiCasa 렌더 | RAM 64GB | 타일 스트리밍 |

**핵심**: cheapest probe(Cell 1)·브리지 검증(Cell 2)·5b 학습(Cell 3)·CubiCasa 벡터 채점(Cell 4)·배심 가치(Cell 5)가 **전부 로컬**. 프런티어 API 미승인이 P5 코어를 막지 않는다.

### 4.2 DGX 계획 (승인됐으나 unreachable — "생존 후 확장" 자원)

- **대형 백본(SegFormer-B5, 고해상도)**: 5b가 로컬 소형으로 생존(Cell 3 IoU 통과)한 뒤에만 DGX 야간.
- **Ornith-35B vision**: **가정 플래그** — vision 지원 여부 미확인. P5 착수 전 확인(T13). 미지원이면 5a 대형-VLM은 프런티어 API 전용(승인 게이트에 종속).
- DGX는 **게이트 통과의 선결이 아니다** — 킬 게이트(브리지 F1)는 전부 로컬에서 판정된다.

### 4.3 데이터 계보·누출 방지

- 렌더 스타일 파라미터(선폭·poché·노이즈) **다양화 후 동결**; FPC **도면 단위 스플릿**; CubiCasa는 이미 **도면 단위 train4200/val400/test400** 분리(다이제스트). test는 단발 봉인.
- 역투영 코드는 **합성 선검증 통과 후에만** 실코퍼스 발언권(다이제스트 leakage 방지 항 준수).

---

## 5. 구현 계획 — 모듈 골격·접속점·규모

기존 실측 파일 레이아웃(`tools/e2/` 스캔 확인)에 신설 `tools/e2/vision/` 패키지를 얹는다.

### 5.1 신설 모듈 (제안 경로 — 착수 시 확정)

| 파일 | 책임 | 접속점(기존) |
|---|---|---|
| `tools/e2/vision/render.py` | 합성/실도면 렌더 + 합성 pixel↔handle 맵 emit | 라우터 `cad_visual_report`/render; `synth/{grammar,noise,openings}.py` |
| `tools/e2/vision/backproject.py` | §2.0 공통 브리지(픽셀→핸들) | `detect/evidence_grid.py`, `detect`의 `fast_score` 벡터화 |
| `tools/e2/vision/seg_train.py` | 5b SegFormer/U-Net 학습(FPC) | `ext/features.py`(불필요 시 생략), FPC 래스터·segmask 로더 |
| `tools/e2/vision/seg_infer.py` | 5b 마스크 추론 | `render.py` |
| `tools/e2/vision/vlm_jury.py` | 5a: 로컬 qwen → (DGX/프런티어) 프롬프트→polygon | `render.py`, 로컬 qwen2.5-VL-3B |
| `tools/e2/vision/jury_fold.py` | 배심 1석 편입·Fleiss κ·순열검정·divergent 해소율 | E1.5 silver 앙상블, `w1_eval_fold_v3.py` |
| `tools/e2/vision/NC_FIREWALL.md` | 5b 가중치 계보·방화벽 문서(제품 반입 금지 기록) | — |

### 5.2 기존 도구 접속점(패킷 지명)

- **`fast_score`**(detect 계열 NumPy 고속 채점기): 역투영의 footprint 신호 평균·집계를 벡터화로 재사용 → 412,775 선분 규모 대응.
- **`evidence_grid`**(`detect/evidence_grid.py`): P5 vision 채널을 **다증거 격자의 한 채널**로 붙일 수 있으나, R23상 vision은 배심원(SoT 아님)이므로 기본은 **격자 밖 배심 1석**. (격자 편입은 선택·후속.)
- **`ext/cubicasa_ir.py` / `ext/cubicasa_eval.py`**: CubiCasa 벡터 IR 렌더·핸들 채점(Cell 4).
- **`ext/cubicasa_ml.py`**: GBDT(F1 0.517) 기준선 — P5가 넘어야 할 벽. 동일 val에서 비교.
- **`meta/battery_cli.py`**: metamorphic 배터리 — 역투영 핸들을 CL-D 배터리에 통과(배심 가치의 metamorphic-정합 측정 + 0벽 sentinel).
- **`w1_eval_fold_v3.py`**: 실도면 폴드 평가 드라이버 — 배심 편입 후 앙상블 재평가.

### 5.3 예상 개발 규모 (추정 — 요검증)

- `render.py`(+합성 맵 emit): 중간(합성 생성기 PR-1 의존). ~2~3 person-day.
- `backproject.py`: **최고 위험·최고 가치** 모듈. 킬 게이트가 여기 달림. ~2~4 person-day + 합성 선검증.
- `seg_train.py`/`seg_infer.py`: 표준 분할 파이프라인. ~2~3 person-day.
- `vlm_jury.py`: 프롬프트·파싱·재시도·abstain. ~1~2 person-day(로컬 qwen 기준).
- `jury_fold.py`: κ·순열검정·해소율. ~1~2 person-day.
- 총 코어 ~8~14 person-day 추정(합성 생성기 PR-1·counsel PR-3는 별도 선결).

---

## 6. 실험 셀 정의

원칙: val=개발·튜닝, test=방법당 단발, 합격선 프리레그 봉인, 셔플/순열 대조 의무, 증거 xlsx 의무, 실패도 사유 기록. 셀은 두 트랙×(합성검증·실eval)+브리지 게이트+배심 가치+조건부 silver로 필요한 만큼(6셀 + 선결 게이트).

### Cell 0 — 선결 게이트 (계측 아님, 착수 전 확인)

- **확인 항목**: (a) PR-1 합성 벽 생성기 존재·충실도 게이트, (b) PR-3 counsel(FPC/CubiCasa NC·원도면 권리) 서면 클리어, (c) DGX Ornith vision 지원 여부(T13), (d) 로컬 qwen2.5-VL-3B vision sanity.
- **게이트**: (a)(b) 미충족이면 5b·실코퍼스 발언권 **차단**. (c) 미지원이면 5a 대형-VLM은 프런티어 전용. 
- **예산**: <1일(확인·문서).

### Cell 1 — 5a cheapest probe (이름-맹 vision, divergent-20)

- **가설**: 레이어/블록명 없이 순수 시각(로컬 qwen 우선)으로도 벡터 탐지기가 놓친 divergent-20의 벽이 보인다.
- **지표**: 역투영 핸들의 탐지기/silver 일치도, "이름 없이 벽 보임" 정성율. **P0 법의학과 교차 대조.**
- **합격선(프리레그)**: divergent-20 중 ≥30%에서 vision이 탐지기와 다른 판정을 metamorphic-정합으로 낸다(신호 존재).
- **킬**: 20장 전부에서 vision이 무의미(핸들 F1 ≈ 기저율) → 5a 신호 없음.
- **예산**: 1일, 렌더 20장 + VLM 1패스(로컬 무과금 / 프런티어 시 소액). **시드**: divergent-20 고정.

### Cell 2 — 브리지 검증 (합성, THE 킬 게이트)

- **가설**: render→(seg/VLM)→backproject가 합성 렌더에서 핸들을 정확히 복원한다(pixel↔handle 맵 보유).
- **지표**: 5b wall-pixel IoU; **역투영 핸들 F1**.
- **합격선(프리레그)**: wall-pixel IoU ≥0.7 **AND** 역투영 핸들 F1 ≥0.6.
- **킬**: **역투영 핸들 F1 <0.4 → 양 트랙 동시 kill**(vision 품질 무관, 브리지 병목).
- **예산**: 로컬 CPU 렌더 + 5070Ti seg, ~2~4일. **시드**: 렌더 스타일(선폭·poché·노이즈) 다양화 후 동결, 합성 시드 ≥3.

### Cell 3 — 5b 분할 학습 (FPC 래스터)

- **가설**: 소형 분할(B0/U-Net-R18)이 FPC에서 유효한 wall-pixel IoU 도달.
- **지표**: FPC val wall-pixel IoU(도면 단위 스플릿).
- **합격선(프리레그)**: FPC val IoU ≥0.7.
- **킬**: 튜닝 후 IoU <0.5 → 5b 픽셀 모델 자격 상실.
- **예산**: 5070Ti 16GB, 소형 백본, ~1~2일. **시드**: FPC 도면 단위 스플릿, 3시드. **주의**: FPC 벡터 없음 → 역투영 없음(브리지는 Cell 2).

### Cell 4 — 5b 벡터 eval (CubiCasa 렌더 — GBDT를 넘는가)

- **가설**: CubiCasa 벡터를 렌더→seg→backproject한 핸들 F1이 기하 탐지기 0.236을 넘고, GBDT 0.517 대비 신호를 더한다.
- **지표**: CubiCasa **val** 역투영 핸들 F1; GBDT와의 오류-상관.
- **합격선(프리레그)**: F1 > 0.517(GBDT 초과) **OR** F1 > 0.40이면서 GBDT와 오류 저상관(독립 신호 기여).
- **킬**: F1 ≤ 0.236(기하 탐지기 미달) → 5b 벡터-eval 자격 상실(Occam — 더 싼 GBDT가 있음).
- **예산**: 로컬, ~1일(Cell 2/3 후). **시드**: val(400) 튜닝, **test(400) 단발 봉인**.

### Cell 5 — 배심 가치 (실도면 divergent-20, H4+H3)

- **가설**: 이름-맹 vision 배심이 divergent를 metamorphic-정합으로 해소하거나 앙상블 κ를 올리고, 오류가 이름-신호와 탈상관(H3 교차검증).
- **지표**: divergent 해소율; Fleiss κ 변화(순열검정); vision-오류 vs 탐지기/silver 오류 상관.
- **합격선(프리레그, 배심 생존)**: divergent-20의 ≥30%를 metamorphic-정합 출력으로 해소 **OR** 앙상블 Fleiss κ 상승(순열 p<0.05). 미달 → **타이브레이커로 demote**.
- **킬**: 해소 0% AND κ 하락 → 배심 가치 없음.
- **예산**: 로컬+소액, ~2일. **시드**: divergent-20 고정, 순열 1000 셔플.

### Cell 6 — 5a 프런티어-silver 게이트 (조건부·현재 BLOCKED)

- **가설**: E1.5 well-posed 게이트 AND silver-Pearson 게이트가 열리면 프런티어 VLM이 silver급 배심 자격.
- **지표**: 게이트 상태(E1.5 B1≥0.70 AND silver-Pearson≥0.70 — calibration 정정 기준).
- **합격선**: 두 게이트 개방.
- **현재 상태(정직)**: 합성 충실도 B1=KS 0.5792 FAIL, 가시적 silver 상관 B5=0.2911(≪0.70) → **게이트 미개방**. E1.5 B1/B4 정식 판정은 **비행 중**(패널). **∴ 5a는 지금 silver 배심 자격 없음 — 이름-맹 타이브레이커로만 진입**. 프런티어 API 승인도 별도 게이트.
- **예산**: E1.5 완료 + API 승인에 종속(자체 계측 없음).

---

## 7. red team 티켓 응답

패널 OPEN 티켓 34건 중 P5에 걸린 것을 지목하고 해소/수용을 명시한다.

### 수렴급 (T1–T7)

- **T1 — 대리 독립성 (sev 0.75, 최우선)**: {합성·외부·metamorphic·silver}가 같은 "평행 이중선" prior 공유 시 확증 아닌 편향 증폭. **부분 해소 + 정직한 수용**: P5의 이름-맹 배심은 **이름축에서 확실히 독립**(구조적으로 이름 불가시) → T1의 이름 부분을 강하게 공략. 그러나 **기하축에서는 부분 독립**(벽은 시각적으로도 평행 이중선) → prior 누출을 Cell 5의 오류-상관으로 **정량 노출**하고, 저상관일 때만 독립 기여로 인정. 완전 독립 주장 안 함.
- **T2 — 생성기 부재 (sev 0.70)**: `synthetic_truth.py`는 dimension 전용, 벽 코드 0. **의존성 수용(BLOCKED-on-PR-1)**: P5의 진리 사슬·킬 게이트가 합성 렌더에 달림 → **PR-1 없이는 Cell 2가 불가**. 또 B1 충실도 FAIL(KS 0.5792, 실도면의 SPLINE/ARC/HATCH 부재)은 브리지 검증 분포의 비현실성 리스크 → 스타일 노이즈 주입으로 완화하되, 생성기 fidelity 게이트 통과가 하드 선결임을 인정.
- **T5 — 라이선스 (sev 0.65)**: FPC/CubiCasa NC 라벨·원도면 권리 미해결. **해소안 + 수용**: 5b NC 방화벽(가중치 연구 계측기 전용·제품 반입 금지·계보 기록 `NC_FIREWALL.md`) 설계 + **PR-3 counsel 서면 클리어 전 5b 착수 금지**. 5a 프런티어 API는 도면 외부 반출 우려 → **로컬 qwen 경로로 반출 0 회피**(단 qwen 학습데이터 계보는 요검증).
- **T3=T6 (sev 0.60) — 평가 단위**: 공격 E(집합-조립 격리). **해소**: P5 산출을 **per-handle `wall_member(h)`로 선언**(CL-C 계약 정합), 집합-조립은 별도 산출물로 격리.
- **T4 (sev 0.55) — ornith 원시 조달**: P5 특화판은 **T13(DGX Ornith vision 지원 확인)**. **수용**: Cell 0에서 선확인, 미지원이면 5a 프런티어 전용.
- **T7 (sev 0.50) — 0벽/전벽 sentinel + recall 최저선**: 공격 F. **해소**: P5가 기여하는 어떤 랭킹도 CL-D의 **0벽 sentinel + recall 최저선을 랭킹 전 탑재**(위반율-only 밴드 금지). Cell 5 metamorphic은 CL-D 배터리 경유.

### P5 특화 (CL-G 조건)

- **T24 — 픽셀→핸들 역투영 exact 하네스 합성 선검증 (R23 CRS kill risk)**: **P5의 척추.** Cell 2가 정확히 이 게이트다. 합성 pixel↔handle 맵으로 역투영 F1을 직접 측정, <0.4면 양 트랙 kill.
- **반대의견 #1 (silver 게이트 식별자)**: **정직한 정정 수용.** 정확한 게이트는 calibration의 "B1(well-posed)≥0.70 AND silver-Pearson≥0.70"(prereg_e15.json 원문 기준). platt 종전 인용("B1만")은 수정. 단 **네임스페이스 주의(요검증)**: 현행 wave의 B1(충실도)·B4(불변성)·B5(silver Pearson 0.2911)는 E1.5 prereg의 B1(well-posed)·B4(silver 자격)와 **다른 지표 색인**일 수 있음 → 정확 매핑은 prereg_e15.json 대조로 확정. 방향은 명확: 가시 수치상 게이트 미개방.
- **T34 — 인용 R-레인 experiment_executed:false**: **수용.** 이 도시에는 새 측정 주장 0(다이제스트 수치만 인용). load-bearing 인용의 status는 실험 실행으로만 승격.

---

## 8. 인접 제안과의 관계 — 병합·차별·죽음 조건

### 8.1 병합 가능 지점

- **CL-A / platt P0 (E1 법의학)**: Cell 1(cheapest probe)의 "이름 없이 벽 보임"을 P0 법의학과 **교차 대조**. 이름-맹 vision(P5) + 이름-법의학(P0) = 상보. (패널 프로브 큐 #6이 이 교차를 명시.)
- **CL-D / platt P3 (metamorphic 배터리)**: P5 역투영 핸들을 CL-D 배터리에 통과(배심 가치의 metamorphic-정합). **P5는 CL-D에 의존**(공용 심판·0벽 sentinel).
- **CL-I / platt P6 (관례 계측)**: P5 이름-맹 배심 = silver 이름-prior의 **둘째 독립 측정**. P6 lexicon 측정과 교차.
- **CL-K / feyerabend P3 (anti-silver 통제)**: 5b는 **silver 아닌 사람 라벨(FPC)**로 학습 → feyerabend 우려와 정합. 5b는 anti-silver 통제 arm의 자연스런 실증.

### 8.2 차별점

- **vs CL-F 학습 사다리(platt P2)**: CL-F는 **벡터 특징** 학습(로지스틱→GBDT→GNN, Occam 사다리). P5는 **래스터 외형** 학습. 겹치지 않는 특징공간. 단 GBDT 0.517이 이미 강해 P5는 이를 **넘거나 독립 신호를 더해야** 정당(Cell 4).
- **vs 3석의 VLM 프레임 vs feyerabend P5(반대의견 #4)**: 다수는 "프런티어=배심원, 결정론=SoT"(R23). feyerabend는 "래스터 본선 학습 + 벡터 게이트". P5는 **다수 프레임 채택**(vision=배심원 1석, 진리원 아님) — "래스터 본선" 주장은 PARK(T31: zero-pair 넘는 회수 실증 전까지).

### 8.3 이 제안이 죽어야 하는 조건 (정직하게)

1. **브리지 킬**: 합성 역투영 핸들 F1 <0.4(Cell 2) → vision 품질 무관, 양 트랙 즉사. **P5의 1순위 사인(死因).**
2. **Occam 킬(5b)**: CubiCasa 역투영 F1 ≤ GBDT 0.517 **AND** 독립 신호 없음(오류 고상관) → 더 싼 GBDT가 있으므로 5b 죽음.
3. **게이트 영구 폐쇄(5a-silver)**: E1.5 B1≥0.70 AND silver-Pearson≥0.70이 끝내 안 열리면 5a는 silver 배심 자격 영구 상실 → 타이브레이커로만 또는 죽음.
4. **counsel 부정(PR-3)**: FPC 가중치를 계측기로도 못 쓴다는 서면이면 5b 전면 종료.
5. **생성기 미충실(PR-1)**: 합성 생성기가 fidelity 게이트를 끝내 못 넘으면 브리지 진리 사슬이 닫히지 않아 Cell 2 불가 → P5 PARK/사망.
6. **독립성 소멸**: 이름-맹 배심 오류가 탐지기 평행-이중선 FP와 고상관(Cell 5)이고 브리지 F1도 평범하면 → 셋째 축도 H3 교차검증도 무의미 → demote 후 소멸.

**죽음의 우선순위**: 1(브리지)이 가장 싸고 빠른 판결이므로 가장 먼저 시험한다. 나머지는 브리지 생존 후에만 의미가 있다.

---

DOSSIER_COMPLETE: platt_P5
