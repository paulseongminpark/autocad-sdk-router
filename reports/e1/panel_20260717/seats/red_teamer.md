# SEAT — red_teamer · 벽 의미 탐지기 방법론 (Phase B)

STANCE 준수: 나는 판사도 생성자도 아니다. 살아있는 top-ranked 주장을 최강으로 재서술한 뒤 그 **논증의 전건(grounds·warrant)**을 친다. 어떤 제안도 죽이지 않고 REJECTED를 쓰지 않는다 — severity + gate-checkable ticket만 남긴다. kill은 게이트가 친다. independence_check: 나는 Phase A 어느 제안의 저자·공저자도 아니다 → 전 표적에 대해 true.

## 0. 검증 로그 (공격의 grounds — 내가 실제로 연 것)

전건 공격이므로 인용을 원문에서 확인했다. 확인 사실(모두 이번 세션 도구 출력):

- `wall_pairs.py:46` — `entity.get("dxf_name") != "LINE"` → **LINE-only 입력** 확정. `:143-144` `angle_tol_rad=0.005, gap_range=(30.0,500.0), min_overlap_ratio=0.5, max_pairs_per_line=4` 확정. `:106` conf=0.7·overlap+0.3·gap_score 확정. `:218-239` `propose_for_ir`는 `block_definitions→def_entities`만 순회, **중첩 INSERT transform 전개 없음** 확정.
- `e1_crosscheck.py:113-117` `_score_divergence` — `high_likelihood_zero_pairs`는 kind **0**, `many_pairs_low_likelihood`는 kind **1**. `:183-186` `_top_divergent`는 이 키로 정렬 후 `[:20]`. → **top-20 전건 단일종은 정렬 설계가 보증한다**(zero-pair def가 20개 이상이면 강제) 확정.
- `wall_crosscheck_v0.md` — Pearson 0.2842, n_h_ornith가 20행 중 17행=**정확히 10**, 2행=8, 1행=5. n_pairs·n_h_det 전건 0. def 전건 익명 `*U###`/`X-평면도…$…` xref-바운드 확정.
- `calibration_v0.json` — role 0.5491(n=377), likelihood **Pearson 0.4866**·bucket 0.6233, **handle Jaccard mean 0.1319·zero_frac 0.682 (단 n=239, 377 아님)** 확정.
- `prereg_e15.json` — **B1**=상위3자 role agreement well-posedness 게이트; **B4**=likelihood Pearson≥0.70이면 SILVER 자격; 0.50–0.70은 미정의 공백대. 확정.
- `synthetic_truth.py` — `make_dim_ir`는 **DIMENSION-vs-anchor-line**만 생성, 4 뮤테이션 전부 dimension용(`MUTATION_KINDS`). **벽·이중선·두께·방 관련 코드 0** 확정.
- `R26_FINAL_REPORT.md` — `status: draft`, `experiment_executed: false`, "all external sources carry NEEDS_WEB_VERIFY". C07은 "Top supported claims"의 misuse guardrail, C04(RLVR)·C10(bandit) 예외 명시 확정.
- `R23_FINAL_REPORT.md` — `status: draft`, `experiment_executed: false`. FloorPlanCAD/CubiCasa = CC-BY-NC 확정. **"Counsel clearance for NC research use" = Top unknown**, **"CAD Graph IR as ready GNN substrate without adjacency completeness proof" = disputed** 확정.
- `R16_FINAL_REPORT.md` — `status: draft`. C04/C05: arrangement은 **double-line→centerline 이후** 프리미티브. **KR2(오픈플랜 recall 붕괴)·KR4(messy geometry brittle)=top kill risk, U01(실무 DWG room-recovery 정확도)=미측정** 확정.
- `R28_FINAL_REPORT.md` — `status: draft`. **U28-002 "Valid CAD metamorphic relation catalog"=UNKNOWN**, kill risk "Leaky splits→false progress", "License-irreversible golden sets" 확정.
- `R12_FINAL_REPORT.md` — `status: complete`(단 "no architecture chosen", `experiment_executed: false`). "Layer equality is not a universal oracle", "**FloorPlanCAD … disclaims ownership of underlying drawings**", "Quadratic candidate graphs … infeasible or silently lose recall"=kill risk 확정.
- `R14_FINAL_REPORT.md` — `status: draft`. "Local factory already exceeds six headline classes (e.g. CurtainWall)", kill risk "Closed-6 enum ignoring CurtainWall/Opening" 확정.

**메타 사실(전 패널 관통)**: 인용된 R-레인 6개 중 5개가 `draft`, 6개 전부 `experiment_executed: false`, 외부 주장 전부 `NEEDS_WEB_VERIFY`, 모두 2026-07-13 R0. 패널의 모든 제안은 이 미검증 스캐폴드 위에 서 있다.

---

## 1. 수렴점 STEELMAN (좌석들이 공유하는 것 — 최강으로 재서술)

블라인드였음에도 네 좌석이 독립 수렴한 지점을, 반증하기 가장 어려운 형태로 세운다.

- **C-1 부트스트랩 폐합 (전원)**: 사람 라벨이 없어도 {합성 정답 + 외부 NC 라벨 + metamorphic 불변식 + E1.5 상위합의 silver}의 네 대리(proxy)는 **서로 충분히 독립적**이어서, 한 방법이 네 개에 동시 합치하면 그 방법은 벽을 배운 것이지 대리의 버릇을 배운 것이 아니다.
- **C-2 합성이 1차 판별기 (전원)**: `synthetic_truth.py`의 correct-by-construction + 1-seeded-violation + mutant-conviction 골격을 벽으로 확장하면, **라벨 비용 0·정확 핸들**을 가진 유일 truth로서 synthetic F1(≥0.90/0.95)이 정당한 admission·1차 판별 게이트가 된다.
- **C-3 metamorphic = 공용 라벨-프리 심판 (전원)**: 강체변환·균일스케일·단위변환 불변은 **정답 벽 탐지기의 필요 성질**이며 라벨 0으로 145 실코퍼스에 적용 가능하므로, 전 계열을 실데이터에서 비교하는 유일한 공용 심판이자 RLVR 보상원이다.
- **C-4 E1 불일치는 진단 중심·주로 커버리지 문제 (전원, 강도차)**: "LLM 고확신+탐지기 0쌍"은 v0의 구조적 입력 배제(LINE-only·INSERT 미전개·mm gap·per-def scope)로 대체로 설명되며, 커버리지를 고치면 불일치 대부분이 해소된다.
- **C-5 RL은 집합-조립/획득/라우팅에만 정당, terminal 라벨링엔 부적격; C07은 교리 아닌 증거 (전원 P4)**: per-handle 분류는 supervised 우위(C07 성립)지만, 부분집합 선택·다음-질의-선택·도구 라우팅은 검증가능 보상+순차 구조를 가져 RLVR/bandit이 탐색을 이길 수 있고, 이 분할 자체가 판별 가능한 예측이다.
- **C-6 VLM=배심원/후보생성기지 SoT 아님; 래스터 학습은 결정론 게이트로 역투영하면 허용 (VLM 다루는 전원)**: 프런티어 프롬프트=silver 배심원, 로컬 파인튜닝=후보 탐지기, 최종 합격은 항상 결정론 벡터 게이트 → R23 vision-as-SoT 기각을 지키며 표현 학습만 취한다.
- **C-7 prereg 밴드+동결 스플릿+firm-level 누수통제 = 신뢰의 근거 (전원)**: 보기 전에 밴드·스플릿을 동결하고 firm 단위로 누수를 막으면 Goodhart·false progress가 차단되므로, 동결 밴드를 통과한 방법은 주장을 얻는다.

카드 규칙 6("무엇이 이걸 반증하나?")을 이 생존자들에게 물었다 — C-2/C-3/C-5/C-6은 저자들이 **자기 kill condition을 명시**했다(강도 증거, 좌석에 유리). C-1/C-4/C-7은 명시적 자기-반증 테스트가 **약하다** → 아래 A·C·D 공격의 표적.

---

## 2. 수렴에 대한 최강 공격 (카드 REQUIRED OUTPUT FIELDS 완비)

### 공격 A — 대리 4종은 독립이 아니다: 합치는 확증이 아니라 공유편향 증폭
- **target_hypothesis_id**: C-1 (부트스트랩 폐합, 4-proxy 삼각측량)
- **target_steelman**: §1 C-1.
- **target_author**: 전원 (platt P2 "3원 삼각측량 ≥2원 concordance", doe P3, calibration WSD-EVAL-v1 S/F/M, feyerabend gate 배터리)
- **independence_check**: true
- **attack_type**: warrant_undercut
- **targets_component**: warrant
- **attack**: 네 대리는 공통 조상 — "벽=두께 밴드 안 평행 이중선" 기하 prior — 를 공유한다. 합성 생성기(C-2)는 **그 prior로 저자가 만들고**, metamorphic 관계(C-3)는 **그 합성 위 mutant-conviction으로 admit**되며, silver(E1.5)는 `calibration_v0.json`에서 likelihood Pearson **0.4866**(중간 동의)인데 handle Jaccard **0.13/zero_frac 0.682**(접지 불일치) — 즉 **이름/게슈탈트 prior엔 동의, 접지엔 불일치**라는 서명이다. 세 대리가 같은 prior를 인코딩하면, 셋에 합치한 방법은 "그 prior를 학습했다"만 증명한다 — 정확히 다투는 대상. "concordance=confirmation" warrant가 무너진다.
- **severity**: 0.75
- **severity_argument**: 대리 독립성은 **측정하지 않으면 성립하지 않는 것이 기본값**이다. 어느 좌석도 synthetic-pass ↔ metamorphic-pass ↔ silver 사이의 상호정보/불일치 구조를 측정하지 않는다. doe P3가 가장 근접하나 train×eval **전이(transfer)**를 재지 독립을 재지 않는다 — 공유편향 쌍은 전이가 **잘** 되어 거짓 안심을 준다. 편향이 공유되면 이 공격은 거의 확실히 landed였을 것.
- **outcome**: pending (독립성 감사 미실행)
- **kill_vector (예정 게이트)**: 동일 def 집합에서 (synthetic-truth 통과 여부, metamorphic 통과 여부, top-tier silver 벽핸들)의 3원 불일치 구조를 산출 → 예측 killing result: synthetic-pass와 metamorphic-pass가 r>0.7로 상관하면 "≥2원 concordance" 승격 규칙은 확증이 아니라 동어반복 (T1).
- **routing**: gate hardening

### 공격 B — "synthetic_truth.py를 벽으로 확장"은 확장이 아니라 무(無)에서 만드는 생성기이고, 그 충실도는 미측정
- **target_hypothesis_id**: C-2 (합성이 1차 판별기)
- **target_steelman**: §1 C-2.
- **target_author**: platt P1, doe P5, feyerabend P1 ("확장하면 된다"류). calibration P1은 예외("패턴만 재사용, truth로 안 셈").
- **independence_check**: true
- **attack_type**: premise_defeat
- **targets_component**: grounds
- **attack**: `synthetic_truth.py`를 읽었다 — `make_dim_ir`는 DIMENSION-앵커선 IR만 만들고 4 뮤테이션 전부 dimension용, **벽·이중선·두께·방 코드가 0**이다. 전이되는 "패턴"은 correct-by-construction+1-mutation+conviction **골격뿐**, 벽 현상학은 0. 벽 생성기의 실벽 충실도가 프로그램 사활인데 아직 존재하지 않는다. 그런데 synthetic F1 ≥0.90/0.95가 모두의 **1차 게이트**다.
- **severity**: 0.70
- **severity_argument**: 합성이 구성상 쉬우면 1차 게이트는 자명 통과 → 실벽에 대해 아무것도 인증 못 한다. doe P1이 실패모드 #2로 "합성 천장→요인 무차별"을 자인한다. 생성기 충실도가 미검증인 한 첫 판별 신호가 유령이다.
- **outcome**: lands (코드 사실: 현 파일 벽 콘텐츠 0 — 확정)
- **kill_vector**: 벽 생성기 초안이 나오면, 그 synthetic-F1 ≥0.95가 **divergent-20 실recall 불변**과 동시 발생하는지 검사 → 동시 발생이면 합성 게이트는 무인증 (T2). 선결: 생성기가 divergent-20의 실현상(POLYLINE/블록/비평행 조각)을 재현하는지 fidelity 게이트.
- **routing**: gate hardening + claim weakening

### 공격 C — E1 불일치의 핵심 통계가 정렬-키 아티팩트다: "puzzle" 프레임의 전건 붕괴
- **target_hypothesis_id**: C-4 (E1 불일치 진단 중심)
- **target_steelman**: §1 C-4.
- **target_author**: 전원(과업 배경 상속). platt P0만 이미 이 결함을 자기 표적으로 삼음.
- **independence_check**: true
- **attack_type**: premise_defeat
- **targets_component**: grounds
- **attack**: `e1_crosscheck.py:113-117`+`:183-186` 확인 — `high_likelihood_zero_pairs`는 kind 0, 다른 종은 kind 1, 정렬 후 `[:20]`. **"top-20 전건 고확신+0쌍"은 zero-pair def가 20개 이상이면 정렬이 보증**한다 — 세계의 발견이 아니라 정렬 설계의 산물. `many_pairs_low_likelihood` 종의 규모는 완전 미보고. Pearson 0.2842는 "무상관"이 아니라 약양(弱陽)이고, Jaccard는 LINE-only 배제가 zero_frac 0.682를 지배한다. platt만 이를 봤고 나머지 셋은 과업의 "0.28 상관·전건 divergent" 프레임을 액면 상속.
- **severity**: 0.60
- **severity_argument**: 이 통계가 "커버리지가 불일치를 고친다"(C-4)의 동기다. 정렬 아티팩트를 제거하고 재계산하기 전엔 불일치의 **크기**가 미지수다. 결함이 실재하므로(코드로 확정) landed.
- **outcome**: lands
- **kill_vector**: kind 혼합 재정렬 + `many_pairs_low_likelihood` 카운트 보고 → 예측: mono-species top-20이 정렬만으로 재현됨. platt P0-forensic이 이 재계산이며 **다른 모든 제안의 하드 선결**로 승격되어야 한다 (T3). 부속: n_h_ornith=10이 접지 출력인지 "최대 10개 나열" 지시 아티팩트인지 원시 판정.
- **routing**: gate test + claim weakening

### 공격 D — 라이선스·증거 기반이 draft·counsel-pending·NEEDS_WEB_VERIFY인데 hard 제약으로 취급됨
- **target_hypothesis_id**: C-1의 외부-데이터 다리 + C-7의 증거 기반
- **target_steelman**: "NC=연구가능·제품차단은 확정된 제약이고, R-레인 evidence는 신뢰 가능한 기반이다."
- **target_author**: 전원 (FPC/CubiCasa로 학습·평가하는 모든 arm)
- **independence_check**: true
- **attack_type**: premise_defeat
- **targets_component**: grounds
- **attack**: R23는 FPC/CubiCasa NC를 인용하지만 **"Counsel clearance for NC research use"를 Top unknown**으로, R12는 **"FloorPlanCAD가 원 도면 소유권을 disclaim"**을 kill risk로 명시한다 — 즉 라벨의 NC와 **별개로 원 도면 권리 자체가 미해결**. R23·R26·R16·R28·R14 전부 `draft`, 6개 전부 `experiment_executed:false`, 외부 전부 `NEEDS_WEB_VERIFY`. 제품 go/no-go를 가르는 라이선스 사실이 counsel-pending·web-미검증인데 모두 확정으로 소비한다.
- **severity**: 0.65
- **severity_argument**: 외부 데이터로 실제 학습하는 arm(platt P1/P2/P5, doe 전, calibration P1-P5, feyerabend P1/P5)은 이 미검증 전제에 사활이 걸린다. 비가역(가중치·파생물 계보 오염)이라 사후 발견이 사전 확인보다 비싸다.
- **outcome**: lands (R23 unknown·R12 kill risk 문서 확정)
- **kill_vector**: 외부-데이터 arm 착수 전 counsel가 (a) FPC/CubiCasa 라벨 라이선스 (b) **원 도면 권리** (c) 방법개발 사용 적법성을 서면 확인 → 예측 killing result: 원 도면 권리 불명 → 외부 arm 소급 차단 (T5).
- **routing**: gate hardening (human/counsel)

### 공격 E — RL의 "정당한 자리"(집합-조립)는 평가 단위와 다른 목적을 최적화한다
- **target_hypothesis_id**: C-5 (RL 정당 자리 = 집합-조립)
- **target_steelman**: §1 C-5.
- **target_author**: platt P4, doe P4, calibration P6, feyerabend P4
- **independence_check**: true
- **attack_type**: scope_overreach
- **targets_component**: scope
- **attack**: calibration COMMON RESOLUTION CONTRACT는 평가 단위를 **per-handle 이진 wall_member(h)**로 고정하고 "벽 instance/pair 복원은 보조지표, handle 분류와 **섞지 않는다**"고 명시한다. 그러나 모든 P4의 RLVR은 집합-조립(쌍→체인→네트워크 부분집합 선택)에 산다. beam/ILP를 이긴 P4(platt HR1, doe A×C, feyerabend Pareto)는 **contract가 명시적으로 분리한 보조지표**를 개선할 뿐 — "더 나은 집합-조립 ⇒ 더 나은 per-handle F1" warrant는 가정된다.
- **severity**: 0.60
- **severity_argument**: 이건 실재하는 cross-seat 불일치다 — calibration의 평가 단위 vs 나머지의 P4 목적. 다리가 없으면 승리한 RL도 최종 산출물로 전이 안 된다.
- **outcome**: lands (contract 텍스트 vs P4 목적 — 문서 대조로 확정)
- **kill_vector**: 각 P4가 보상·평가를 프로그램 primary와 **동일 per-handle 단위**로 사전선언하거나, 집합-조립을 별도 산출물로 그 자체 가치 케이스와 함께 격리 → 미선언 시 P4 승패는 primary와 무관 (T6).
- **routing**: scope condition

### 공격 F — metamorphic은 필요조건이지 충분조건이 아니고, 위반율-only 밴드는 퇴행 탐지기를 통과시킨다
- **target_hypothesis_id**: C-3 (metamorphic = 공용 1차 심판)
- **target_steelman**: §1 C-3.
- **target_author**: doe P5(위반율-only 밴드), 그리고 "cheapest first"로 metamorphic을 큐 선두에 두는 전원.
- **independence_check**: true
- **attack_type**: spurious_pass
- **targets_component**: gate_path
- **attack**: "0벽 항상 출력" 탐지기는 완벽 불변(위반 0)이다 — degenerate pass. doe P5 prereg는 위반율-only(PASS≤0.02)이고 recall 짝을 "R-SYN과 반드시 짝지어야"로 **후단 연기**한다. cheapest-first 큐에서 metamorphic이 먼저 돌면 퇴행 탐지기가 1차 게이트를 통과해 판별력을 낭비한다. R28 U28-002가 **유효 CAD metamorphic 카탈로그를 UNKNOWN**으로 두므로 심판 자체의 유효성도 미증명 — 공용 심판이 단일 실패점.
- **severity**: 0.50
- **severity_argument**: 좌석들의 자각(platt P3·calibration은 recall 강제항 추가)이 완화하나, doe P5의 위반율-only 밴드와 "가장 먼저" 배치는 실재 노출. 수학적으로 0벽⇒0위반은 확정.
- **outcome**: lands (수학 사실)
- **kill_vector**: doe P5 밴드에 0벽 탐지기 주입 → PASS≤0.02 통과 확인. 배터리는 **recall/coverage 최저선 + 0벽/전벽 sentinel**을 랭킹 게이트 사용 **전에** 탑재해야 함 (T7).
- **routing**: gate hardening

**공격 D-보조 (증거팩 결손)**: 이번 패널에 주어진 evidence/에는 **ornith 원시 JSONL도 프롬프트도 없다**(디렉토리 확인). 가장 많이 인용되는 수 n_h_ornith를 패널 내부에서 감사할 수 없다. outcome=lands, severity 0.55, routing=gate hardening → 원시 출력·프롬프트를 조달하기 전엔 불일치 크기 주장 불가 (T4).

---

## 3. Per-proposal 공격 (26개 전 제안 · severity + concrete ticket)

severity 판정 기준: **HIGH**=핵심 전제가 현재 거짓/미검증이고 1차 게이트가 그것 없이 판별 불가 · **MED**=실재 warrant 갭 또는 미측정 baseline이라 닫아야 하나 구조는 생존 · **LOW**=자기방어된 실패모드, 티켓은 "말한 대로 했는지 확인".

### platt_strong_inferencer

| 제안 | 표적 전건 | attack_type | sev | ticket |
|---|---|---|---|---|
| P0 법의학 감사 | 최강-접지 dissolver | premise_defeat | LOW | **T8/T4**: ornith 원시 JSONL+프롬프트가 evidence팩에 없음 → n_h_ornith=10 "나열 지시" 가설을 P0가 테스트하려면 원시 출력을 먼저 조달. 조달 전 P0는 히스토그램(입력 배제)만 판정 가능. |
| P1 커버리지-완전 v1 | "v0 실패=커버리지" (H1) | warrant_undercut | MED | **T9**: (a) v0의 FPC F1이 **미계측**인데 밴드가 "v1−v0≥+0.2"—먼저 v0 baseline 계측·동결. (b) INSERT transform 전개의 mirror·비등방 스케일 왕복 검증을 합성 중첩 케이스로 통과시킨 뒤에만 "flatten 정확" 주장. |
| P2 GNN Δ-문맥 | 문맥 피처 기여 (H2) | premise_defeat | MED | **T10**: R23가 **Graph IR adjacency completeness를 disputed/미증명**으로 명시 → adjacency 감사(P1 정규화 산출)를 훈련 **전** 선결. 부수: "silver 암 활성=B1≥0.70" 오인용 — B1은 well-posedness, silver 자격은 B4(likelihood)/role-agreement. 게이트 식별자 수정. |
| P3 metamorphic 배터리 | 공용 심판 유효성 | spurious_pass | MED | **T11=T7+T1**: 0벽/전벽 sentinel + recall 최저선 탑재 후 랭킹 사용; 관계 간 상관 행렬(platt 자인)을 실제 산출해 독립성 착시 배제. R28 U28-002(카탈로그 UNKNOWN) 상속. |
| P4 RLVR 집합-조립 | HR1 생존 자리 | scope_overreach | MED | **T12=T6**: 평가/보상을 per-handle 단위로 선언(calibration contract와 정합) 또는 집합-조립을 별도 산출물로 격리. 부수: "C07=draft NEEDS_WEB_VERIFY 주장" 약간 과장 — R26은 SOURCES에 태그, C07은 Top supported claim(draft status). 특성화 정정. |
| P5 VLM 이중트랙 | 브리지+배심 (H4) | premise_defeat | MED | **T13**: platt 자신이 플래그한 "DGX Ornith-35B **vision 지원 미확인**"을 5b 착수 전 확정; 미지원이면 5a=외부 API 전용(비용 kill 밴드 재계산). NC firewall=T5. |
| P6 관례-prior 모델 | H3 계측화 | warrant_undercut | LOW-MED | **T14**: cross-project split의 anti-tautology holdout이 exact "WALL"/"벽"만이 아니라 **firm-특유 벽레이어 코드**(A-WALL, CD-WALL…)를 벗겨야 하는데 그 firm-레이어 lexicon이 없음 → 먼저 구축·동결. |

### doe_experimentalist

| 제안 | 표적 전건 | attack_type | sev | ticket |
|---|---|---|---|---|
| P1 마스터 스크린 (flagship) | "직교 1샷이 전 계열 관통" | scope_overreach | MED | **T15**: Res IV alias 산술 **검증했고 옳다**(E=ABC,F=BCD → AB=CE,AC=BE 확인). 그러나 그래서 **representation×truth가 family×self-training과 confounded** — flagship 서사가 16런의 분리력을 오버셀. 또 learned 셀 family 효과가 **단일 시드**로 seed-confounded. 선결: learned 셀 seed 반복 예산 명시 or B 효과를 seed-confounded로 표기; 미해결로 수용할 aliased 2FI 쌍을 사전 커밋. |
| P2 Taguchi robust | "강건한 **절대** gap 밴드 존재" | premise_defeat | MED | **T16**: feyerabend P2가 절대 mm 밴드를 단위-유물로 반박. 절대 밴드를 robust-최적화하면 **아티팩트를 최적화**할 위험 → 단위-앵커 상대 vs 절대 A/B를 **먼저** 돌려 단위가 은닉 요인인지 확인 후 L9. |
| P3 정답원 교차요인 | train×eval 전이=사슬폐합 | warrant_undercut | LOW | **T17=T1 보완**: 이 제안이 공격 A의 최선 답이나 **전이(transfer)를 재지 독립을 안 잰다** — 공유편향 쌍은 전이가 잘 돼 거짓 안심. 대각/비대각 낙폭 외에 **동일 def에서 대리 불일치 구조** 판독을 추가. |
| P4 RLVR 요인 | A×C(패러다임×예산) | scope_overreach | MED | **T18=T6**: per-handle 평가 단위 선언. 부수: active-acquisition 보상이 **training synthetic truth**에서 계산(calibration P6은 training-truth 보상의 누수 위험 경고) → reward-truth와 eval-truth family 분리. |
| P5 metamorphic 배터리 | A×B 계열별 취약변환 | spurious_pass | MED | **T19=T7**: 밴드가 위반율-only → 0벽 통과. recall 최저선+sentinel을 랭킹 사용 전 탑재. 공격 F의 1차 표적. |
| P6 VLM×융합 | A×B 융합이득 조건성 | premise_defeat | MED | **T20**: 최고가 DGX arm. 융합이득 주장이 **render CRS 역투영**에 의존하는데 R23 "CRS-misaligned fusion inventing geometry"=kill risk → CRS 왕복 exact 게이트를 어떤 융합이득 주장 전에 통과. NC=T5. |

### calibration_forecaster

| 제안 | 표적 전건 | attack_type | sev | ticket |
|---|---|---|---|---|
| P1 constraint lattice | 다증거 결정 격자 우위 | premise_defeat | MED | **T21**: 밴드가 `AUPRC_F−AUPRC_v0≥0.15`인데 **AUPRC_v0(FPC)가 미계측** → baseline을 pack별로 계측·동결. R12 "quadratic candidate graph" kill risk → ILP 포기하는 component-size 상한을 사전 등록(kill condition의 quadratic 검출을 정량 임계로). |
| P2 PU + 고전 ML | P1 대비 lift | warrant_undercut | MED | **T22**: 밴드가 `AUPRC_F≥AUPRC_P1+0.05`—**미증명 P1에 사슬**. 검증 안 된 앵커 위 lift는 무의미 → P1 통과를 하드 선결로. PU의 **SCAR 가정**은 positive가 P1 기하편향에서 오면 정확히 위반 → SCAR을 P1 앵커 편향 대비 감사. |
| P3 self-sup hetero GNN | pretrain→OOD lift | premise_defeat | MED | **T23=T10**: adjacency completeness(R23) 선결. 145 실코퍼스 pretrain이 **같은 이중선 prior를 인코딩**할 위험(공격 A) → pretrain 표현 독립성 체크(mask-ablation을 pretrain arm에도). |
| P4 raster-vector dual-view | subgroup lift+비열등 | premise_defeat | MED | **T24**: `pixel→handle mapping ≥0.995` 강주장 + R23 CRS kill → 합성에서 CRS/역투영 exact 하네스를 실데이터 전 통과. NC=T5. |
| P5 VLM jury/student | admission→student lift | warrant_undercut | MED | **T25**: silver 게이트를 **B1≥0.70 AND B4≥0.70**로 인용 — 좌석 중 가장 정확(platt와의 대조점). 그러나 student lift가 "best non-VLM"에 사슬(미증명 baseline) → non-VLM baseline 먼저 동결; **judge-error 상관**을 합의 신뢰 전에 측정(상관 오류가 합의를 거짓 강화). |
| P6 verifier-guided acquisition | FAR≤0.01 게이트 | premise_defeat | MED | **T26**: verifier false-accept≤0.01이 **RL/획득 계열 전체의 사활 게이트**(R26 U02)인데 미측정 → hidden mutant에서 FAR를 **먼저** 계측(이게 모든 P4를 프로그램 차원에서 게이트). "20% 비용 절감"의 fixed-scan baseline 비용이 미정의 → baseline 정의. |

### feyerabendian_dissenter

| 제안 | 표적 전건 | attack_type | sev | ticket |
|---|---|---|---|---|
| P1 면/포셰 유도 벽 | room-first dual bridge | premise_defeat | **MED-HIGH** | **T27**: R16을 역전(rooms-first)하나 R16 C04/C05는 arrangement가 **centerline 이후** 프리미티브라 명시하고 **KR2(오픈플랜)·KR4(messy)를 kill risk, U01(실무 room-recovery)을 미측정**으로 둔다. raw linework polygonize는 centerline arrangement보다 더 취약. 선결: cheapest-probe를 합성이 아니라 **실 messy divergent-20**에서 — 합성 recall≥0.90은 KR2/KR4에 대해 무언(無言). GEOS(non-GPL) vs CGAL(GPL, R16 KR3) 엔진 명시. |
| P2 단위-치수 정박 대역 | 상대 두께 불변량 | scope_overreach | MED | **T28**: v0 mm 하드코딩에 대한 가장 예리한 단일 비판, 직접 테스트 가능. 그러나 DIMENSION 엔티티 존재 요구 — divergent-20 다수가 익명 `*U###`로 **DIM이 없을 수 있음** → 정박 도달성을 divergent-20에서 먼저 계측한 뒤 상대-대역 주장. |
| P3 anti-silver | gate-only가 silver-distill 이김 | warrant_undercut | LOW-MED | **T29**: "LLM-Pearson 의도적 ≤0.35 유지" 밴드가 **LLM이 실제로 옳은 도면군**에서 진리와 반상관인 탐지기를 보상할 수 있음 → LLM이 synthetic과 합치하는 부분집합에 통제 추가. cross-seat 모순 #2의 한 축(보존). |
| P4 RLVR 도구-라우팅 | 검사정책 순차구조 | scope_overreach | MED | **T30=T6**: per-handle 평가 단위; "학습 없는 ε-greedy 시뮬" 프로브는 우수 — 이를 학습판의 하드 선결 게이트로. 보상해킹(빈 예측률) 감시 유지. |
| P5 래스터 **본선** 학습 | 래스터가 벡터보다 안정 | scope_overreach | MED | **T31**: 메커니즘은 벡터 게이트 경유라 "본선"은 수사적(모순 #4 보존). CRS exact+NC counsel(T5). 추가: 래스터가 **P1 커버리지 수정으로 이미 회수되는** zero-pair를 넘어서는 회수를 실증해야 — 아니면 래스터는 P1과 중복. |
| P6 cross-def INSERT 조립 | def-quotient 오류 | premise_defeat | MED | **T32**: **확정 코드 사실**을 정타(`propose_for_ir:224-239` per-def, INSERT 미전개 — 검증됨). 고가치. 그러나 월드좌표 조립 후 후보 폭발(R12 quadratic kill)이 위험 → 조립 그래프 후보 수 상한; **INSERT 자식 있는 divergent def 10개가 실제로 존재하는지 먼저 확인** 후 folded/unfolded 측정. |
| P7 관례 1등 시민 | 이름이 최대 가능도 | warrant_undercut | LOW-MED | **T33=T14**: firm-레이어 lexicon+cross-project freeze. R12 "layer≠universal oracle"+"source group=authoring evidence not identity proof" 상속 → 관례를 게이트 아닌 **re-ranker**로(feyerabend 이미 그렇게 말함) 유지 확인. |

**추가 프로그램-급 티켓 T34**: 인용된 R-레인 6개 전부 `experiment_executed:false`, 5/6 `draft`, 외부 전부 `NEEDS_WEB_VERIFY`. 어떤 load-bearing 인용(NC 라이선스·C07·adjacency·metamorphic 카탈로그·arrangement robustness)도 **결정을 게이트하기 전에 재-status** 필요 — draft 스캐폴드를 확정 사실로 소비 금지.

---

## 4. Cross-seat 모순 (verbatim 보존 — 섞지 말 것)

1. **Silver admission 게이트 식별자 불일치**
   - platt P2: "silver 암 활성 조건 = E1.5 **B1 ≥ 0.70**"
   - calibration P5: "E1.5 **B1≥0.70 및 B4 Pearson≥0.70**"
   - feyerabend natural_interp 4: "prereg_e15 **B4가 Pearson≥0.70**이면 SILVER 자격"
   - 원문 `prereg_e15.json`: B1=task well-posedness, **B4=likelihood silver 자격**. → platt가 well-posedness 게이트(B1)를 silver 자격 게이트로 오인용. calibration이 가장 정확.

2. **Silver = 신호 vs 오염원 (정면 대립)**
   - 다수(platt P2 3원 truth에 silver 포함, doe T-SILVER 요인, calibration P5 silver→student): silver는 게이트된 학습/크로스체크 신호.
   - feyerabend P3 (anti-silver): "E1.5 silver를 탐지기 학습 타깃으로 쓰지 않는다 … 탐지기는 LLM과 상관을 최대화하는 것이 목표가 아니라 … **체계적으로 불일치해도 살아남는 것**을 목표로." — silver를 교정 타깃으로 쓰는 것을 직접 반대.

3. **Arrangement 방향 (walls→rooms vs rooms→walls)**
   - R16-정합(calibration P1: "후보 중심선을 planar arrangement에 투영"): centerline 먼저 → arrangement → rooms.
   - feyerabend P1: "R16의 centerline→room을 **역전**: room/face가 먼저이고 벽은 dual의 bridge." — 원문 R16 C04/C05("arrangement는 double-line→centerline 이후")의 전제조건과 충돌.

4. **VLM/래스터 역할 프레이밍**
   - platt P5·doe P6·calibration P5: 프런티어=배심원→silver, 로컬 파인튜닝=후보, 결정론 게이트=SoT (보수, R23-정합).
   - feyerabend P5: "**래스터 본선 학습** + 벡터 게이트" — 래스터를 주 학습 트랙("본선")으로. 메커니즘은 동일(벡터 게이트 경유)이나 강조/프레임이 대립.

5. **gap 밴드 파라미터화**
   - doe P2: `gap_range`를 튜닝가능 inner-array 요인으로 robust-최적화 (좋은 **고정 절대** 밴드가 존재한다는 전제).
   - feyerabend P2: 절대 mm gap 밴드는 "**단위-관례 유물**"; DIM-정박 **상대** 대역으로 교체해야. — 절대 밴드 최적화 자체를 아티팩트 최적화로 반박.

---

## 5. Bounced attacks 원장 (실패한 공격 = 동급 rigor로 기록, 카드 규칙 5)

세워봤으나 전건이 버틴 공격 — 저자에게 유리한 확증. 저-severity bounce는 support로 세탁하지 않는다.

- **B1 (반등, 고severity 0.7)**: "prereg는 극장이다 — 같은 팀이 생성기와 게이트를 쓴다." → **반등**. calibration이 명시 "generator와 resolver는 구현을 공유하지 않고, hidden mutation family를 test 전용", doe "generator·resolver 구현 공유 금지", hidden mutant conviction. **고severity 반등 = 패널의 누수/Goodhart 규율이 실재한다는 1급 확증.** (단 공격 A의 대리-독립성은 이 규율이 커버하지 않는 별개 층 — 반등은 Goodhart-내-단일-대리에만.)
- **B2 (반등, 0.6)**: "doe P1의 Res IV alias 주장이 틀렸다." → **반등**. E=ABC,F=BCD로 defining relation I=ABCE=BCDF=ADEF, AB=CE·AC=BE 산술 확인 — doe의 DoE 역량 정확. (단 confounding의 **함의**를 flagship이 오버셀하는 건 별개, T15.)
- **B3 (반등, 0.4)**: "컴퓨트 봉투 비현실적." → **반등**. GPU 작업 대부분 5070 Ti 소형, DGX는 야간 vLLM 시분할로 연기, 첫 신호 프로브는 CPU/시간 단위. 저severity 반등=무(無), support 아님.
- **B4 (반등, 0.5)**: "calibration의 per-handle 단위가 R14 CurtainWall 다중클래스 현실과 충돌해 이진 wall_member가 ill-posed다." → **부분 반등**. feyerabend abstain_if(b)가 "IfcWall vs CurtainWall vs 마감선 입법"을 기하 밖으로 이미 격리, platt A2가 B1<0.60 시 projection 재설계로 라우팅. 단 이진 프레임의 under-specification은 잔존 → 저severity 노트(정식 티켓 아님, 판별 대상 승격은 라이벌 정의가 케이스-쌍을 다르게 분류할 때만 — platt 라우팅 규칙 정합).

---

## 6. REQUIRED OUTPUT FIELDS (카드 스키마 — 요약 매핑)

marquee 공격 A–F가 카드의 per-attack 필드 전량(target_hypothesis_id, target_steelman, target_author, independence_check, attack_type, targets_component, severity[float], severity_argument, outcome, kill_vector/severity_note, routing)을 §2에서 완비. 요약:

| id | target | attack_type | targets | sev | outcome | routing |
|---|---|---|---|---|---|---|
| A | C-1 4-proxy 삼각측량 | warrant_undercut | warrant | 0.75 | pending | gate hardening |
| B | C-2 합성 1차 판별 | premise_defeat | grounds | 0.70 | **lands** | gate hardening+claim weakening |
| C | C-4 E1 불일치 프레임 | premise_defeat | grounds | 0.60 | **lands** | gate test+claim weakening |
| D | C-1/C-7 외부데이터·증거기반 | premise_defeat | grounds | 0.65 | **lands** | gate hardening(counsel) |
| D-보조 | 증거팩 결손(ornith 원시) | premise_defeat | gate_path | 0.55 | **lands** | gate hardening |
| E | C-5 RL 집합-조립 자리 | scope_overreach | scope | 0.60 | **lands** | scope condition |
| F | C-3 metamorphic 공용심판 | spurious_pass | gate_path | 0.50 | **lands** | gate hardening |

- **independence_check**: 전 표적 true (나는 Phase A 무저자).
- **outcome=lands 5건**은 전부 **코드/문서 사실**로 확정(카드 규칙 4: gate-checkable kill_vector 병기). 어느 것도 "죽었다"·REJECTED로 선언하지 않음 — 게이트에 kill_vector를 넘길 뿐(카드 STANCE·과업 제약 준수).
- **abstain**: 실험 미실행(제약 6)이라 A는 pending; 나머지는 이미 확정된 전건이라 lands. 제조된 공격 0 — 전 공격이 §0에서 원문 확인한 grounds 위.

### 최우선 severity 랭킹 (SYNTHESIZE 입력, 내림차순)
A(0.75) > B(0.70) > D(0.65) > C=E(0.60) > D-보조(0.55) > F(0.50). 한 severe 공격(A: 대리 독립성)이 열 nitpick을 이긴다 — **가장 값싸게 프로그램을 무너뜨릴 수 있는 단일 미검증 전건은 "네 truth 대리가 독립이다"이며, 이는 어느 좌석도 측정하지 않았다.** T1이 최우선 gate-hardening.

**티켓 총계: 34 (T1–T34)** — 수렴급 7 (T1–T7, 공격 A–F) + per-proposal 26 (T8=platt P0, T9–T33=나머지 25제안) + 프로그램급 foundation 1 (T34). 26개 전 제안이 각자 티켓 보유(P0=T8, P0의 티켓은 T4 ornith-원시 조달과 내용 중첩). 전건 gate-checkable, 전 outcome은 게이트 소유(kill은 게이트가 친다).
