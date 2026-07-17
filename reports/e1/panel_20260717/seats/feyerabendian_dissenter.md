# Seat: feyerabendian_dissenter (Phase A, BLIND)

## CONVERGENCE_SIGNAL

발화 트리거 = (c) 합의·관측 언어 수렴이 정확도 정체와 동행. E1에서 LLM 역할 일치 0.549·핸들 Jaccard 0.132인데도 관측 단위는 `wall_pairs.v0`의 “평행+근접 LINE 쌍”으로 고정되어 있고, top-20 발산은 전부 “LLM 고확신 + 탐지기 0쌍”(상관 0.28). R12/R16은 double-line→centerline→arrangement를 기본 파이프라인으로, R23은 vision-as-SoT 기각·VLM=배심원, R26 C07은 고정라벨에 RL 오용을 “가드레일”로 서술한다. 살아 있는 판별 실험이 이 관측 언어 자체를 깨뜨리는 큐에 없으므로 counter-induction 발화. (좌석 간 산출은 블라인드라 보지 않음 — 증거 수렴만으로 트리거.)

## reigning_frame

**벽 의미 = 블록 정의(또는 modelspace) 내부의 근사-평행·근접 LINE 쌍 후보**이며, 사람 라벨 부재 시 부트스트랩은 (합성 dim-게이트 + NC 외부셋 + metamorphic + LLM 앙상블 silver)로 닫힌다. 학습 경로는 supervised/결정론·그래프가 본선이고, VLM은 판정자·SoT가 아니며, 고정 범주 분류에 RL은 오용이다.

## natural_interpretations

1. **(heuristic | gate)** “벽의 원자 증거 = LINE 엔티티의 평행쌍” — `propose_wall_pairs`가 세는 것만이 벽 후보; LWPOLYLINE/ARC/SOLID/HATCH/블록 INSERT는 비가시.
2. **(diff | quotient)** “def 단위 집계가 벽 존재의 비교 단위” — E1 crosscheck의 `n_pairs` vs `wall_likelihood`가 같은 대상을 잰다고 가정.
3. **(gate)** “gap∈[30,500]·overlap≥0.5·angle_tol=0.005rad는 단위·유형에 중립인 관측” — mm 주거 이중선 두께를 raw fact로 취급.
4. **(heuristic)** “LLM silver 합의는 탐지기 교정용 soft truth로 승격 가능” — prereg_e15 B4가 Pearson≥0.70이면 SILVER 자격.
5. **(rule)** “고정 라벨 분류에 RL은 오용”(R26 C07) — 보상 가능한 순차 구조가 없다는 전제.
6. **(rule)** “vision-as-SoT 기각 ⇒ 래스터/VLM은 학습 본선이 될 수 없다”(R23) — 판정 역할과 표현 학습 역할을 동일시.

## abstain_if

(a) 이미 관측 언어(LINE-쌍 vs 면/공간-유도 vs 래스터-역투영)를 갈라 죽이는 prereg 실험이 큐에 살아 있거나, (b) “벽”의 제품 enum(IfcWall vs CurtainWall vs 마감선)을 입법하는 질문만 남고 기하 사실이 아닐 때, (c) 보호된 레프리 구성(사람 라벨 금지·원본 CAD READ-ONLY)을 루프 안에서 개정하려 할 때 — 이 좌석은 침묵하고 V2로 올린다. 본 과업은 방법론 후보 생성이므로 생성은 진행하되, **어떤 제안도 게이트 통과 전 “채택/기각”을 선언하지 않는다**.

---

## PROPOSALS

### P1 — 면(face)/포셰 유도 벽: LINE-쌍 관측 언어를 깨뜨린다

**mechanism.** 평행 LINE 쌍을 벽의 정의로 쓰지 않는다. 대신 평면 arrangement(또는 GEOS polygonize)로 닫힌 face를 먼저 추출하고, **두 face를 가르는 공유 경계 리본**(이중 경계·고정 폭 대역·포셰/HATCH 존재)을 벽으로 정의한다. LINE은 경계 조각일 뿐이며, LWPOLYLINE·ARC 분할·짧은 갭도 face 위상 안에서 벽으로 승격된다. R16의 “centerline→room”을 **역전**: room/face가 먼저이고 벽은 dual의 bridge.

**counter_theory.** 벽 = face-adjacency dual의 두께 있는 경계; 평행쌍은 그 경계의 한 구현체일 뿐.

**dissolved_fact.** E1 top-20의 “LLM 고확신 + n_pairs=0”은 탐지기 실패가 아니라 **관측 언어 실패**로 재해석된다 — 벽이 POLYLINE/블록/비평행 조각으로만 그려진 def에서 LINE-쌍 게이트는 구조적으로 0을 출력한다.

**truth source.** (1) 합성: 닫힌 방+알려진 벽 리본 폭을 가진 IR을 `synthetic_truth` 계열로 확장(현재 dim-전용 생성기를 wall-face 생성기로 분기). (2) metamorphic: 전역 강체 변환·균일 스케일 후 face-bridge 집합 불변. (3) FloorPlanCAD 선단위 wall 라벨은 **연구용 전이 프로브만**(NC — 가중치 제품 탑재 금지).

**verification design.**
- 정답원: 합성 face-wall IR의 bridge 집합; metamorphic 불변; (탐구) FloorPlanCAD holdout 선분→리본 IoU.
- 누수 방지: 도면/프로젝트 단위 split; 합성 생성 시드와 실측 145장 분리; FloorPlanCAD로 맞춘 하이퍼는 실측 DWG에 재튜닝 금지(전이만 보고).
- prereg 밴드 초안: 합성 recall@벽리본 ≥0.90 이고 LINE-쌍 v0 대비 실측 def에서 “LLM high ∧ n_pairs=0” 구간의 containment(LLM 핸들⊂face-bridge 핸들) 중앙값 ≥0.40 → VIABLE; <0.15면 이 관측 언어 교체 가설 약화.
- kill condition: 합성에서는 높은데 실측 20장 프로브에서 face 추출이 개방형/노이즈로 붕괴해 bridge 수가 폭발(def당 median bridges > 10× LLM 핸들 수)하면 **기각 후보**(게이트가 죽임 — 좌석이 죽이지 않음).
- cheapest probe: 합성 10장 + E1 divergence top-20 def에 arrangement 1회 → n_pairs=0 구간에서 bridge 회수율만 측정(로컬, GPU 불요).

**discrimination_experiment.**
- outcomes:
  - A: top-20 zero-pair def에서 face-bridge가 LLM 핸들을 유의미 회수 ∧ LINE-쌍은 계속 0 → `kills: reigning` (LINE-쌍 관측 언어)
  - B: face-bridge도 거의 0 또는 과다 분할로 Jaccard/containment 무의미 → `kills: counter` (면-유도 벽)
- cost_to_test: 로컬 CPU 수 시간(합성+top-20)
- v0_gate: 사전 등록 containment/과다분할 임계 + 합성 recall 동시 만족 여부

**compute plan.** 로컬 64GB: Shapely/GEOS polygonize·IR 순회. DGX: 불필요(초기). 대량 145장 재측정만 배치 시 로컬 야간.

**expected failure modes.** 개방형 평면·갭/오버슈트에 arrangement 붕괴; 포셰 없는 도면에서 두께 추정 불가; dual bridge가 가구·치수선까지 벽으로 승격(Goodhart).

---

### P2 — 단위·치수 정박 후 두께 대역: “30–500mm 중립 관측”을 깨뜨린다

**mechanism.** `gap_range=(30,500)`을 raw로 쓰지 않는다. 같은 def/도면의 DIMENSION·측정 텍스트·격자 간격으로 **도면 단위와 전형 벽厚 스케일**을 먼저 추정한 뒤, gap 대역을 상대 스케일(예: 추정 단위의 0.05–0.4× typical span)로 재설정한다. 평행쌍 휴리스틱은 유지하되 auxiliary를 “절대 mm”에서 “치수-정박 상대 두께”로 교체한다.

**counter_theory.** 벽 쌍 검출의 불변량은 절대 gap이 아니라 **치수 정박 상대 두께**; v0 대역은 특정 단위 관례의 유물.

**dissolved_fact.** “상관 0.28·zero-pair 다수”가 전부 표현 실패라는 해석을 약화/분열시킨다 — 일부는 **단위 불일치로 인한 체계적 miss**일 수 있다(큰 좌표·m 단위·커튼월 두께).

**belt_adjustment.**
- auxiliary_changed: `gap_range` 절대 mm → DIM/격자 정박 상대 대역
- progressive_prediction: 단위 추정 신뢰가 높은 def 부분집합에서만 v0 대비 pair recall이 **단방향** 상승하고, 단위 추정 실패 def에서는 변화가 없거나 악화한다(선택적 개선 — 전역 평균 개선만으로는 부족).

**truth source.** 합성 IR에 고의로 unit-scale∈{0.001,0.01,1,1000}을 심고 정답 쌍을 스케일 불변으로 유지; 실측은 DIM-기하 일관성 게이트(`synthetic_truth`/`dim_geometry` 계약)로 단위 추정만 검증.

**verification design.**
- 정답원: 다스케일 합성 쌍 집합; (보조) DIM-일관 def에서만 상대 대역 vs 절대 대역 A/B.
- 누수 방지: 스케일 추정기는 쌍 라벨을 보지 않음(치수·텍스트만); 도면 단위 split.
- prereg 밴드: 합성 전 스케일에서 relative-gap F1 ≥ 0.85 ∧ absolute-gap F1이 스케일≤0.01 또는 ≥100에서 ≤0.40 → 단위-유물 가설 지지.
- kill condition: 실측 치수 정박 가능 def에서도 relative가 absolute 대비 pair-count vs LLM-likelihood Pearson 개선 < +0.05이면 이 belt는 퇴행적.
- cheapest probe: 합성 4 스케일 × 50 IR + E1에서 DIM 많은 def 30개 A/B.

**discrimination_experiment.**
- outcomes:
  - A: 스케일 Sweep에서 absolute만 붕괴·relative 유지 → `kills: reigning` (절대 gap 관측)
  - B: relative도 동반 붕괴 또는 실측 Pearson 무개선 → `kills: counter`
- cost_to_test: 로컬 <1일
- v0_gate: 합성 F1 밴드 + 실측 Pearson δ

**compute plan.** 로컬 only. DGX 불요.

**expected failure modes.** DIM 없는 도면; 잘못된 치수 앵커; 커튼월·이중외피가 multimodal thickness → 단일 대역 실패.

**rule_under_attack.** 해당 없음(방법 규칙이 아니라 휴리스틱 auxiliary).

---

### P3 — Anti-silver 교정: LLM 고확신을 유물이라 가정한다

**mechanism.** E1.5 silver를 탐지기 학습 타깃으로 쓰지 않는다. 반대로 **“LLM high likelihood ∧ 결정론 0” 셀을 오염/관측언어 충돌 셀**로 표시하고, 학습 신호는 metamorphic·공간폐쇄·합성만 사용한다. 탐지기는 LLM과 상관을 최대화하는 것이 목표가 아니라, **게이트-가산 벽 가설을 유지한 채 LLM과 체계적으로 불일치해도 살아남는 것**을 목표로 한다. Silver는 오류 분석용 배심원으로만 남긴다(R23 정합을 LLM에도 적용).

**counter_theory.** LLM wall_likelihood/핸들은 투영·프롬프트 이론에  Bundled된 판정이지 벽 기하의 soft truth가 아니다; 탐지기–LLM 상관 최대화는 Goodhart.

**dissolved_fact.** prereg_e15 B4(“Pearson≥0.70 ⇒ SILVER for detector crosscheck”)가  implicit로 심는 “합의=교정 타깃” 사실을 해체 — 합의는 과제 well-posedness 지표일 뿐 기하 진리가 아니다.

**truth source.** 합성 wall 쌍/리본; metamorphic(회전·스케일·레이어 셔플 후 쌍 집합 안정); 공간폐쇄 점수(벽 가설 제거 시 face 수 급변).

**verification design.**
- 정답원: 합성+metamorphic+closure; silver는 금지 타깃(명시적 negative control).
- 누수 방지: 판정자 산출을 feature/loss에 넣지 않는 코드 계약; 도면 split.
- prereg 밴드: 합성 F1≥0.80 ∧ LLM-Pearson **의도적으로** ≤0.35 유지해도 metamorphic pass rate≥0.90 → anti-silver 경로 VIABLE; 합성 F1≥0.80인데 metamorphic<0.5면 과적합.
- kill condition: silver를 타깃에 넣은 복제 모델이 합성·metamorphic에서 동등·우월하면 anti-silver 주장 약화(게이트가 silver-유용 프레임을 살림).
- cheapest probe: 동일 합성으로 “silver-distill” vs “gate-only” 두 헤드 학습 1 epoch 비교.

**discrimination_experiment.**
- outcomes:
  - A: gate-only가 silver-distill 대비 metamorphic≥+0.10 ∧ 합성 동등 → `kills: reigning` (silver-as-truth)
  - B: silver-distill이 전 게이트 우월 → `kills: counter`
- cost_to_test: 로컬 GPU 반나절(소형) 또는 DGX 소형 배치
- v0_gate: metamorphic pass + 합성 F1 동시

**compute plan.** 로컬 RTX 5070 Ti로 소형 그래프/MLP. DGX는 E1.5 재판정 서빙과 충돌 시 야간 슬롯만.

**expected failure modes.** 게이트가 너무 약해 빈 탐지기도 pass; LLM이 실제 기하와 맞는 도면군에서 과도한 불신.

---

### P4 — RLVR 도구-라우팅/가설검증 정책 (C07에 대한 counter-induction)

**mechanism.** “엔티티→고정 벽 라벨”에 policy gradient를 걸지 않는다. 대신 **행동 = 어떤 기하 검사를 어떤 순서·예산으로 실행할지**(평행쌍 / face-bridge / 블록속성 / DIM정박 / 래스터 크롭 VLM 질의)를 고르는 contextual bandit·단기 RL. 보상 = 합성 정답 적중 + metamorphic 유지 − 검사비용. 분류 자체는 supervised 헤드가 수행하고, RL은 **획득·라우팅**에만 존재한다 — C07이 금지한 자리와 C04/C10이 허용한 자리를 분리한다.

**counter_theory.** 벽 탐지의 학습 가능한 순차 구조는 라벨이 아니라 **검사 정책**; C07의 “고정라벨 RL 오용”은 참이어도 이 자리에는 적용되지 않거나, 적용을 전 과업으로 일반화한 것이 유물이다.

**dissolved_fact.** “RL은 이 프로그램에서 서지 못한다”는 교리적 독해 — Paul 이의와 정합하게, 오용 패턴과 RLVR/bandit 자리를 분리하지 않은 채 C07을 프로그램 킬로 읽는 해석을 해체.

**rule_under_attack.**
- rule: R26 C07을 wall-detector 프로그램 전체에 대한 RL 배제 규칙으로 승격하는 읽기
- non_universality: 동일 레포트 C04(RLVR)·C10(horizon≈1 bandit)이 이미 예외 자리를 명시; 고정라벨≠도구 라우팅
- proposed_amendment: “C07은 entity→category 직접 RL에만 적용; 검증가능 보상의 획득/라우팅 정책은 C04/C10 트랙으로 별도 prereg”
- route: V2_human_gate

**truth source.** 합성 벽 IR + 알려진 최적 검사 시퀀스(오라클 비용); metamorphic; (보상 해킹 감시) LLM-judge 보상 금지.

**verification design.**
- 정답원: 합성에서 동일 F1을 더 낮은 검사비용으로 달성하는가; 실측은 비용-품질 Pareto만.
- 누수 방지: 보상에서 silver/LLM 배제; 도면 split; 정책 학습 시드와 eval 시드 분리.
- prereg 밴드: 고정 풀 스캔 대비 ≥30% 비용 절감 ∧ 합성 F1 저하 ≤0.02 → VIABLE; 절감<10%면 bandit 가치 없음.
- kill condition: 보상을 검사 횟수 최소화만으로 핵해 빈 예측으로 F1 붕괴(해킹) 또는 supervised-only와 Pareto 동일.
- cheapest probe: 탐구 ε-greedy bandit을 top-20 divergence def에 수동 행동집합 4개로 돌리기(학습 없이 시뮬레이션).

**discrimination_experiment.**
- outcomes:
  - A: 비용↓·F1유지 → `kills: reigning` (C07 전면 배제 읽기)
  - B: 해킹 또는 무이득 → `kills: counter` (이 자리의 RLVR)
- cost_to_test: 로컬 1–2일; 정책 신경망 시 DGX 선택
- v0_gate: Pareto + 해킹 탐지(빈 예측률)

**compute plan.** 1차 로컬 tabular bandit. 딥 정책이면 DGX Spark 단기, vLLM과 GPU 큐 분리.

**expected failure modes.** 보상 해킹; 행동 공간이 실제 실패 모드를 미포함; C07 오용 패턴으로 미끄러져 라벨 RL을 재도입.

---

### P5 — 래스터 본선 학습 + 벡터 게이트 (vision 역할 분리 공격)

**mechanism.** R23의 “vision-as-SoT 기각”을 **판정 역할**에만 묶고, **표현 학습**은 연다. FloorPlanCAD(NC)로 오픈 VLM/세그멘터를 연구 파인튜닝해 래스터 벽 마스크를 얻은 뒤, 렌더 CRS로 핸들/선분에 역투영한다. 제품 SoT·최종 합격은 항상 결정론 게이트(두께 리본·metamorphic·합성)가 담당 — VLM은 후보 생성기. 프런티어 VLM 프롬프팅은 silver 배심원 갈래로 분리(학습 가중치와 혼선 금지).

**counter_theory.** 벽의 통계적 외형은 래스터 국소 패턴에 더 안정적이고, 벡터 휴리스틱은 작성 관례에 취약하다; SoT 거부가 학습 모달리티 거부로 확장된 것이 유물.

**dissolved_fact.** “VLM은 배심원만”을 “학습에 쓰지 말 것”으로 읽는 운영 해석을 해체 — 배심원≠피처 추출기.

**rule_under_attack.**
- rule: local epistemology “vision-as-SoT 기각”을 래스터 학습 경로 금지로 해석하는 운영 규칙
- non_universality: R23 자체도 assistive vs SoT 경계를 말하며, encoder-as-SoT 킬과 연구용 표현 학습은 층위가 다름; NC는 제품 탑재 금지지 연구 금지가 아님
- proposed_amendment: “VLM/래스터 출력은 후보 채널로만 진입 가능; 합격은 벡터 결정론 게이트; NC 가중치는 제품 아티팩트 트리 제외”
- route: V2_human_gate

**truth source.** FloorPlanCAD 연구 split(선 라벨); 역투영 후 합성·실측 metamorphic; 제품 경로에는 NC 가중치 미진입 선언.

**verification design.**
- 정답원: FPCAD holdout IoU; 역투영 핸들의 게이트 pass; 실측는 게이트만(사람 라벨 없음).
- 누수 방지: 건물/도면 split; 프런티어 VLM 프롬프트 산출을 파인튜닝 타깃에 미사용; NC 체크섬 allowlist.
- prereg 밴드: FPCAD wall IoU≥0.60 ∧ 역투영 후보가 게이트 통과율에서 LINE-쌍 v0 대비 top-20 회수 +0.25 → 연구 경로 VIABLE; 제품 배송 밴드는 별도(가중치 격리) — 미달 시 학습 갈래 PARK.
- kill condition: 게이트 없이 VLM 출력을 SoT로 쓰는 설계가 필요해지거나, NC 가중치 없이 실측 게이트 이득≈0.
- cheapest probe: 렌더 20 def + 동결 오픈 seg(파인튜닝 전) 역투영 vs wall_pairs 회수 비교.

**discrimination_experiment.**
- outcomes:
  - A: 래스터 후보+게이트가 zero-pair 구간 회수에서 지배 → `kills: reigning` (벡터-휴리스틱 유일 본선)
  - B: 역투영 불능/CRS 실패/이득 없음 → `kills: counter`
- cost_to_test: 프로브 로컬; 파인튜닝 DGX 1–3일
- v0_gate: IoU+게이트 회수 δ; 라이선스 격리 체크

**compute plan.** 파인튜닝·배치 추론 DGX Spark; 역투영·게이트 로컬. 프런티어 VLM silver는 API/별도 예산, 학습과 큐 분리.

**expected failure modes.** CRS 어긋나 기하 날조(R23 kill); NC 오염; 래스터가 치수선·가구를 벽으로 흡수.

---

### P6 — Cross-def / INSERT 조립 단위: “def 스코프=벽 단위”를 깨뜨린다

**mechanism.** `propose_for_ir`의 per_def 스코프를 버리고, modelspace의 INSERT 트리·변환 스택으로 정의를 펼친 뒤 **조립된 월드 좌표**에서만 벽 리본/쌍을 찾는다. 익명 `*U###` 블록이 벽 조각만 갖고 이중선 상대방이 다른 def/modelspace에 있는 패턴을 정면 타깃으로 한다.

**counter_theory.** 벽 의미는 authoring chunk(block def)가 아니라 **배치된 월드 기하의 관계**; E1 def 단위 likelihood는 잘못된 quotient.

**dissolved_fact.** “def 안 n_pairs=0 ⇒ 그 역할 단위에 벽 없음” — INSERT 조립 후 쌍이 생기면 이 사실은 유물이 된다.

**truth source.** 합성: 벽을 두 블록에 쪼개 배치한 IR; 실측: INSERT 전개 후 metamorphic; (탐구) 동일 건물의 다른 블록 분할 버전.

**verification design.**
- 정답원: 분할-합성에서 전개 후에만 쌍 회수; 비전개 per_def는 의도적 miss.
- 누수 방지: 전개 그래프는 핸들 안정 해시로만; 라벨 없음.
- prereg 밴드: 분할-합성에서 folded recall≤0.2 ∧ unfolded≥0.9 → 스코프 가설 지지; 실측 `*U*` top 발산 중 ≥30%가 전개 후 쌍 생성.
- kill condition: 전개 후 후보 폭발(제곱 복잡도)로 실용 불가 또는 실측 발산 def에서 이득 없음.
- cheapest probe: top-20 중 INSERT 자식 있는 def 10개 folded vs unfolded pair count.

**discrimination_experiment.**
- outcomes:
  - A: unfolded만 정답 회수 → `kills: reigning` (def quotient)
  - B: 동일 miss → `kills: counter`
- cost_to_test: 로컬 CPU
- v0_gate: 합성 분할 회수 + 실측 10장 프로브

**compute plan.** 로컬. 대량 전개 시 메모리 계측 후 64GB 내에서 배치; DGX 불요.

**expected failure modes.** 동적 블록/미지원 IR; 전개 후 후보 폭증; xref 미포함.

---

### P7 — 텍스트/레이어 관례를 1등 시민으로: 기하 우선 서사를 깨뜨린다

**mechanism.** 기하 이전·동등 단계로 레이어명·블록명·TEXT/MTEXT(“W”,“벽”,“WALL”)·선종을 벽 prior로 쓰고, 기하는 **확인 게이트**만 수행한다. 레이어 평등 신화(R12: layer equality not universal oracle)를 인정하되, “보편 오라클이 아니다” ≠ “신호 강도 0” — 프로젝트 내 레이어–벽 상호정보를 비지도로 추정한 뒤, 기하 후보를 re-rank한다.

**counter_theory.** 실무 DWG에서 벽 의미의 최대 가능도는 작성 관례(이름)에 있고 기하는 노이즈 많은 확인자; v0의 기하-only conf(0.7 overlap+0.3 gap)는 관례를 무시한 유물.

**dissolved_fact.** “레이어는 오라클이 아니므로 모델에 넣지 않는다”는 운영 휴리스틱 — non-universality가 zero-weight로 붕괴한 것.

**truth source.** 합성: 레이어명을 벽에 정렬/의도적 오정렬한 쌍; metamorphic: 기하 불변·레이어 셔플 시 성능 하락량으로 관례 의존도 측정; 외부셋 관례는 프로젝트 전이 금지.

**verification design.**
- 정답원: 합성 정렬 vs 오정렬; 실측는 게이트+이름 prior A/B(사람 라벨 없이 metamorphic·silver는 분석만).
- 누수 방지: 프로젝트 내 fit / 프로젝트 간 freeze; 이름 사전을 평가 도면에서 학습 금지(사전 등록 홀드아웃).
- prereg 밴드: 오정렬 합성에서 이름 prior 제거 시 F1 불변 ∧ 정렬 합성에서 +0.15 → 신호 존재; 프로젝트 전이 시 이득≤0이면 관례 채널 PARK.
- kill condition: 이름 prior가 기하 게이트를 우회해 오탐을 SoT화하려는 압력(규칙 위반) 또는 전이 이득 없음.
- cheapest probe: 레이어 문자열 간단 규칙(정규식) vs 무규칙, top-20 재점수.

**discrimination_experiment.**
- outcomes:
  - A: 관례 re-rank가 zero-pair·고LLM 구간에서 게이트 통과 후보를 유의미 회복 → `kills: reigning` (기하-only)
  - B: 무이득·전이 붕괴 → `kills: counter`
- cost_to_test: 로컬 수 시간
- v0_gate: 합성 정렬/오정렬 대비 + 전이 홀드아웃

**compute plan.** 로컬. 임베딩 사용 시 소형 모델 로컬, 대량 실험만 DGX.

**expected failure modes.** 영어/한국어 혼용; 레이어 도용; 관례 Goodhart로 게이트 약화.

---

## discrimination_experiment (좌석 큐 — 최저비용 우선)

1. P1 cheapest (top-20 face-bridge) + P6 folded/unfolded — 관측 언어·quotient 동시 타격, CPU only  
2. P2 합성 스케일 sweep — gap 절대주의  
3. P3 gate-only vs silver-distill 1 epoch  
4. P7 정규식 prior  
5. P4 bandit 시뮬레이션  
6. P5 동결 seg 역투영 프로브 → 통과 시에만 DGX 파인튜닝  

## rule_under_attack (집계)

- R26 C07의 전면 RL 배제 읽기 → V2 (P4)  
- R23 vision-as-SoT의 학습경로 금지 해석 → V2 (P5)  

## belt_adjustment (집계)

- P2만 progressive prediction 동반 auxiliary 조정; 두 번째 퇴행적 rescue 발생 시 gap 대역 자체가 용의자로 게이트 이관.

## 좌석 선언 (FORBIDDEN 준수)

본 문서는 경쟁 가설·판별 실험 큐일 뿐이며, 어떤 프레임도 이 좌석의 수사로 기각·채택되지 않는다. 킬은 `v0_gate` 결과만.