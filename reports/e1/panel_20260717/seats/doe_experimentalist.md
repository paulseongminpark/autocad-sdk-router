# SEAT: doe_experimentalist — 벽 의미 탐지기 방법론 (Phase A, BLIND)

## 이 좌석이 무엇을 기여하는가 (STANCE, 먼저 읽기)

이 좌석은 **새 탐지기 아키텍처를 발명하지 않는다.** 그것은 abduction/가설생성 좌석의 몫이다. 이
좌석의 유일한 무기는 **요인 스크리닝(factor screening)과 상호작용(interaction) 추정**이다. 즉 "GNN을
만들어보고, 다음에 VLM을 만들어보고, 다음에 휴리스틱을 손보자"는 **한-번에-한-요인(OFAT,
one-factor-at-a-time)** 진행 — 지금 이 프로그램이 사실상 그렇게 굴러가고 있다 — 은 설계상 **요인들
사이의 결합(interaction)을 구조적으로 놓친다**. 표현(representation)·정답원(truth source)·모델
계열(family)·라벨잡음 처리·자기학습(self-training)·누수 분리 입도(leakage granularity)는 서로
**독립적으로 설정 가능하고 서로 간섭한다.** 이 좌석이 내는 6개 제안은 각각 하나의 **사전등록된 요인
배터리(pre-registered designed battery)** 다 — 개별 아키텍처가 아니라, "어떤 요인이 실제로 검출
품질을 움직이는가, 그리고 그 요인들이 서로 어떻게 간섭하는가"를 한 번의 직교 배치로 추정하는 실험
설계다. 순위표(effects table)는 지목만 하고 죽이지 않는다 — **지명된 최적 설정은 반드시 별도
confirmation run을 통과해야 주장이 된다** (미확인 최적 = `PASS_WITH_DEFERRAL`, 결코 `PASS` 아님).

**Phase A 정직 고지**: 이 패널은 조사·설계만 하고 코드 실행이 없다(제약 6). 따라서 아래 모든
제안의 `effects_table`·`interactions_found`·`confirmation_run`은 **미실행(UNRUN)**이며, 채워야 할
슬롯 + 사전(prior) 가설 + 확정 프로토콜로 제시한다. 어떤 수치도 실측이 아니다. 상태는 전부
`PASS_WITH_DEFERRAL`.

---

## SHARED APPARATUS (6개 제안이 ID로 참조하는 공용 어휘)

정의를 한 번만 두고 제안들이 이름으로 인용한다("이름 = 정의" 규율). 실측 근거: E1 role 일치 54.9%,
벽 핸들 Jaccard 평균 0.13, LLM(ornith)–결정탐지기 상관 0.28 (`reports/e1/calibration_v0.json`,
`wall_crosscheck_v0.md`). v0 탐지기 노브: `angle_tol_rad=0.005`, `gap_range=(30,500)`,
`min_overlap_ratio=0.5`, `max_pairs_per_line=4`, conf=0.7·overlap+0.3·recip-gap
(`tools/semantic/wall_pairs.py` 실측).

**반응 카탈로그(Response catalog) — 무엇을 측정하나:**
- `R-SYN` = 합성 정답 F1. `synthetic_truth.py`의 "correct-by-construction + 정확히 1개 seeded
  violation" 패턴을 벽판(wall)으로 확장(현행은 dimension용)한 도큐먼트에 대한 wall-pair F1. 타입=결정
  게이트. 방향=↑. 합성은 쉬움 → 낮으면 곧 적신호.
- `R-META` = metamorphic 위반율. 변환 불변/등변 관계를 깨는 비율. 타입=결정 게이트. 방향=↓.
  **라벨 0개로 산출** — 가장 싼 신호.
- `R-SILVER` = E1.5 판정자 앙상블 silver(`annot_v1/prereg_e15.json`) 대비 벽 핸들 Jaccard/F1.
  타입=잡음 measure(silver 잡음 상속). 방향=↑. 현재 baseline≈0.13.
- `R-EXT` = 외부 NC 데이터셋(FloorPlanCAD 선단위 의미, CubiCasa5K) 라인단위 F1. **라이선스=방법개발
  전용, 가중치 제품탑재 불가**(R23). 타입=measure. 방향=↑.
- `R-DOWN` = 다운스트림 정합. 검출된 벽 centerline로 planar arrangement가 닫는 방(room) 수 /
  opening host 성공률(R16 C04/C07). 타입=결정-준게이트. 방향=↑. 검출 품질의 간접 게이트.

**정답원(Truth source) T:** `T-SYN`=합성 생성기(결정, seed-offset 有) · `T-META`=metamorphic
게이트(무라벨) · `T-SILVER`=E1.5 앙상블 silver(rationale 포함) · `T-EXT`=외부 NC 라벨셋.

**누수 정책(Leakage) L:** `L-DWG`=도면 단위 split(같은 도면 엔티티 train/test 분리; 최소) ·
`L-FIRM`=소스 설계사/템플릿 단위 split(규약 누수 차단; 일반화 주장 강도) · `L-SEED`=합성 seed-disjoint
split(산술 생성기 암기 차단; `synthetic_truth.make_dim_ir(seed_offset=)` 실측 지원).

**은닉상태/캐시 정책(공통, card rule 6):** ① DWG Graph IR은 1회 산출→freeze, 고정 입력으로 취급해
은닉 요인 제거. ② 학습 arm의 training seed는 고정+기록; seed 민감도가 의심되면 seed를 outer-array
**명시 반복**으로 승격(은밀한 잡음 금지). ③ `T-SILVER`는 LLM 비결정 → 그 반응만 잡음 상속하므로
silver **생성 반복**이 유의미(다른 결정 반응과 대칭 아님). ④ 실행 순서: 순수 결정 arm은 순서
무관(그 사실을 기록); 학습/캐시 arm만 셀 순서 무작위화.

**유효효과 판정 규칙(공통 prereg, card rule 3):** 미반복(unreplicated) 분수요인 + 결정 반응 → 셀내
오차 추정 불가 → **Lenth PSE**(작은 효과들의 median 기반 pseudo-standard-error)로 유효효과 판정,
임계 = |effect| > ME(α=0.05 margin of error), sparsity-of-effects 가정 명시. outer-array가 있는 robust
design은 **drawing-to-drawing 잔차 std의 2배** 초과를 active 요인으로 본다.

**Goodhart 방어(공통):** 모든 게이트 반응(R-SYN/R-META)에는 **hold-out 벌점 쌍**을 붙인다 — 게이트
통과율↑ 이면서 hold-out F1↓ 이면 reward-hacking(R26 C08)의 서명이며, 이는 "패러다임×지표"
상호작용으로 검출된다. 라이선스-비가역 golden set 금지(R28 kill risk) → 외부 NC는 eval 참조로만,
가중치에 굽지 않음.

---

## PROPOSALS

### P1 · MASTER FACTOR SCREEN — 탐지기 설계공간 전체의 분수요인 스크린 (flagship)

**Mechanism (1문단).** 지금 프로그램은 계열별 탐지기를 하나씩 만들어 비교하는 OFAT다. P1은 그 대신
설계 선택 6개를 2수준 요인으로 놓고 **한 번의 직교 배치**로 전부의 main effect와 핵심 2요인
상호작용을 동시 추정한다. "학습이 결정론을 이기나"를 단독으로 묻지 않고 "학습의 우위가 표현(그래프
vs 래스터)·정답원(합성 vs silver)과 **간섭하는가**"를 묻는다 — 예컨대 "학습은 래스터+silver에서만
이기고 그래프+합성에서는 결정론과 동률"이라면 이는 model-family×representation 상호작용이며, 계열을
단독 비교한 어떤 OFAT 결론도 반증된다(card rule 4). 활성으로 드러난 소수 요인만 P의 후속(3~4수준
세분·response surface)으로 넘긴다. 이것이 "여러 계열을 고루 커버"(평가기준 5)를 낭비 없이 달성하는
방식이다: 계열이 **요인의 한 수준**이므로 스크린 자체가 전 계열을 관통한다.

**factors** (name | levels | settable | rationale):
- `A representation` | {graph-IR, raster} | Y | 입력 기질 선택. Graph IR은 결정 핸들그래프(R23 실측),
  래스터는 render 파이프.
- `B model_family` | {deterministic, learned} | Y | 스크린 1차는 이 2분. 활성이면 후속에서 learned를
  {GNN, VLM}로 분해.
- `C truth_source` | {T-SYN, T-SILVER} | Y | 학습·튜닝 신호원.
- `D label_noise_handling` | {hard, soft/confidence-weighted} | Y | silver 잡음을 하드 라벨로 쓰나
  soft로 쓰나.
- `E self_training` | {off, on} | Y | 자기라벨 재학습 루프 on/off(P4와 연결).
- `F leakage_granularity` | {L-DWG, L-FIRM} | Y | 분리 입도 자체를 요인화 — 성능이 입도에 민감하면
  그 자체가 "규약 암기" 진단.

**response.** metric=`R-SYN`(1차) + `R-SILVER`(2차, 교차확인). type=결정 게이트(R-SYN) + 잡음
measure(R-SILVER). source=`T-SYN`/`T-SILVER`. direction=↑.

**design.** 2수준 6요인 분수요인 `2^(6-2)` = **16 runs** (Res IV). 각 run = 1개 탐지기 설정을 도면
population 위에서 학습·평가.

**resolution_alias.** Resolution **IV**. 생성자 E=ABC, F=BCD. → main effect는 2FI와 비교리(unaliased),
그러나 **2FI끼리 별칭 사슬로 묶임**: 예 AB=CE, AC=BE, AD=?, ... 이 설계는 **별칭된 2FI 쌍을 분리하지
못한다**(예: representation×truth 를 family×self-training 과 못 가른다). 이 값이 청구서에 반드시 찍힌다.
분리가 필요하면 fold-over 8런 추가로 Res V 승격.

**prereg_model (=prereg 밴드 초안).** 추정 대상: A~F 6 main effect + 별칭 사슬 대표 2FI. 결정 임계:
Lenth PSE, |effect|>ME(α=0.05)면 active. 반응 밴드(사전 봉인): R-SYN — PASS≥0.90 / INCONCLUSIVE
0.75–0.90 / FAIL<0.75(합성은 쉬우므로 하한이 높다). R-SILVER — PASS≥0.50 / INCONCLUSIVE 0.30–0.50 /
FAIL<0.30(현 0.13 대비). 사후 요인 추가는 version-bump된 새 prereg(exploratory 라벨).

**noise_factors.** 이 설계에서 도면 population은 반복 축이자 잔차원. 40장 층화표본(source-firm 층
+plan density 층)을 **각 셀에 동일 적용**(crossed). 도면 밀도·단위·layer-naming 유무는 **비설정
관측 변수 → outer 잡음/블록**으로만 취급(설정 요인 아님; card 금지수 "비설정 변수의 요인화" 회피).

**run_matrix.** 16행 = 표준 `2^(6-2)` 직교표(±1 배정), E=ABC·F=BCD로 채움. 각 행에 40장 population
평가. 순서: learned arm 포함 셀만 무작위화(seed 누적 방지), 순수 결정 셀은 순서 무관(기록). 캐시: IR
freeze, seed 고정+기록.

**effects_table (UNRUN — 슬롯+사전순위).** 채울 열 = {A,B,C,D,E,F, 대표2FI}의 effect·rank·active여부.
사전 기대 순위(가설, 실측 아님): C(truth_source) > B(family) > A(representation) > F(leakage) >
D(noise_handling) > E(self_training). **null/small 효과도 1급 결과로 전부 보고** — "이 요인은 반응을
안 움직인다"가 승리다(예: E가 null이면 자기학습 무익 근거). status=UNRUN.

**interactions_found (UNRUN — 사전 가설).** 이 16런이 **검출하도록 설계된**(별칭 안 걸린) 주요 후보:
B×C(학습의 우위가 정답원에 의존), A×B(계열 우위가 표현에 의존), C×F(정답원 효과가 누수입도에
의존=규약 암기 서명). 사전 가설: B×C 크다(합성에서 학습이 과적합) → "학습이 낫다/못하다"의 단독
스토리 반증 예상. status=UNRUN.

**confirmation_run.** 프로토콜: 스크린이 지명한 최적 셀을, **미사용 firm의 hold-out 도면군**에서 단독
재실행하여 밴드 재확인 + Goodhart 쌍(게이트↑ & hold-out↓?) 점검. status=`PASS_WITH_DEFERRAL`(미실행).

**abstentions.** ① 별칭된 2FI 쌍(AB=CE 등)은 **증명적으로 분리 불가** — fold-over 없이는 못 가른다.
② learned를 {GNN,VLM}로 못 나눔(1차는 2수준). ③ 요인 목록에 없는 벽-정의 신호(예: 해치 poché,
텍스트 라벨)는 이 스크린이 **발명 못 함** — 전 그리드 plateau면 abduction 좌석으로 hand-off. ④ 비설정
관측변수(밀도 등)에 대한 인과 주장 불가.

**deterministic_note.** B=deterministic 셀은 (config,도면) 고정 시 순수 함수 → **셀내 반복 무의미**,
반복은 population(outer)로만. B=learned 셀은 training seed가 은닉상태 → seed 고정+기록(또는 seed를
명시 반복 요인화). `T-SILVER` 반응만 LLM 비결정 상속 → 그 축은 randomization이 실제로 방어함. 순수
결정 축엔 잡음모형 통계 수입 금지(card rule 7).

**Verification design 5요소.** truth source=`T-SYN`+`T-SILVER` · leakage=`L-DWG` 기본, `F`로 `L-FIRM`
대조 · prereg 밴드=위 R-SYN/R-SILVER 밴드+Lenth ME · kill_condition=아래 · cheapest_probe=아래.

**compute_plan.** 로컬(64GB/5070Ti): 결정 arm 16셀 전부 + 소형 GNN 학습 + IR 처리. RAM 상시 계측 후
사용. DGX Spark: learned 셀 중 VLM/대형 GNN 학습만 오프로드(vLLM 호스트 겸용 고려해 야간 배치).
첫 신호: 결정 arm만 먼저 돌리면 며칠 내(사실상 시간 단위).

**kill_condition.** 전 16셀에서 R-SYN이 전부 FAIL 밴드(<0.75)면 → 표현/정답원 문제이지 모델 문제
아님(계열 스크린 무효, 정답원 재설계로). 또는 어떤 셀도 R-SILVER를 0.30 위로 못 올리면 → silver
자체가 신호 없음(P3로 이관).

**cheapest_probe.** 16런의 **결정 arm 8셀만** 먼저(학습 0). 반나절 내 A/C/F main effect 초벌 → 학습
투자 전에 "표현·정답원·누수가 애초에 반응을 움직이나" 확인.

**expected_failure_modes.** ① Res IV 별칭을 잊고 2FI를 clean kill로 오독(card 금지수). ② 합성이 너무
쉬워 전 셀 R-SYN 천장→요인 무차별(밴드 하한을 합성 난이도에 맞춰 올려 방어). ③ learned 셀 seed
잡음을 상호작용으로 오인(seed 블록화로 방어).

---

### P2 · TAGUCHI ROBUST DESIGN — 145 아카이브를 잡음 population으로 (가장 싼 실측 신호)

**Mechanism (1문단).** `wall_pairs.py`가 실제로 노출하는 연속 노브 4개(내가 코드에서 읽음)는 완벽한
**inner array(제어 요인)**이고, 145장 실무 DWG 아카이브는 완벽한 **outer array(잡음 population)**다.
지금 위험은 누구든 이 노브를 `1.dwg` 한 장에 맞춰 튜닝하고 "좋아졌다"고 선언하는 것 — 이는 프록시
최적화이자 과적합(card rule 5). Taguchi robust design은 **평균 성능이 좋으면서 도면 간 분산이 가장
낮은** 노브 설정을 고른다. 반응을 신호대잡음비(S/N)로 요약해, "어떤 도면에서도 흔들리지 않는 결정
탐지기 설정"을 찾는다. 이건 학습 0, 라벨 0(R-META 사용 시)으로 **며칠이 아니라 시간 단위**에 첫 신호가
나오는, 프로그램에서 가장 값싼 실측이다.

**factors** (inner array, 전부 코드 실측 노브):
- `angle_tol_rad` | {0.002, 0.005, 0.010} | Y | 평행 허용각.
- `gap_lo/gap_hi` | {(20,300),(30,500),(50,800)} | Y | 벽 두께 밴드(mm).
- `min_overlap_ratio` | {0.3, 0.5, 0.7} | Y | 겹침 하한.
- `max_pairs_per_line` | {2, 4, 8} | Y | fan-out 상한.

**response.** metric=`R-META` 위반율(1차, 무라벨) + `R-SYN` F1(2차) → **S/N 비**(smaller-the-better는
R-META, larger-the-better는 R-SYN). type=결정 게이트. source=`T-META`+`T-SYN`. direction: S/N ↑.

**design.** **Taguchi L9(3^4)** inner(9 runs) × outer(도면 표본). outer=source-firm 층화 40장. 총
9×40=**360 결정 평가**(값쌈).

**resolution_alias.** L9는 resolution III 상당 — **main effect는 추정, 그러나 3요인 이하 상호작용을
main과 별칭**한다. 즉 L9는 노브 간 상호작용(예 angle×gap)을 **분리 못 함**; 이 청구서를 명시.
상호작용이 의심되면 L27로 승격하거나, 활성 노브 2개만 3^2 완전요인으로 후속.

**prereg_model.** 추정: 4 노브의 main effect(S/N). 임계: **drawing-to-drawing 잔차 std의 2×** 초과가
active(공통 규칙). 밴드: R-META PASS≤0.02 / INCONCLUSIVE 0.02–0.10 / FAIL>0.10. 강건 설정 채택 조건:
평균 최적 ±1 수준 내에서 **분산 최소 셀** 선택(평균만 보고 뽑지 않음).

**noise_factors.** **이것이 robustness 사례** — outer array = {source-firm, unit/scale(mm/m), plan
density(엔티티/면적 3분위), layer-naming 규약 유무}. 표집=145 아카이브 층화 40장, 블록=firm.
샘플링 정책: firm당 상한을 둬 대형 firm 지배 방지.

**run_matrix.** L9 표준 직교표 9행 × 40 도면. 순서 무관(순수 결정; 기록). 캐시: IR freeze. 각 셀에서
도면별 반응 → S/N 집계.

**effects_table (UNRUN).** 슬롯 = 4노브 S/N main effect·rank·active. 사전순위(가설): gap_range >
min_overlap > angle_tol > max_pairs. null도 보고(예: max_pairs가 null이면 fan-out 상한 무의미).

**interactions_found (UNRUN).** L9는 상호작용 별칭 → **이 설계로는 검출 대상 아님**(정직 고지). 만약
활성 main이 2개면 그 둘만 3^2 완전요인 후속으로 angle×gap 등 확인. status=UNRUN.

**confirmation_run.** 지명된 강건 설정을 **outer에 안 쓴 hold-out firm 도면군**에서 단독 재실행,
S/N·분산 재확인. status=`PASS_WITH_DEFERRAL`.

**abstentions.** ① 노브 간 상호작용 분리 불가(Res III). ② 결정 휴리스틱의 **천장** 자체는 못 넘음 —
전 L9 그리드가 plateau면 "튜닝으로 안 됨"이 확정되고(card rule 4) 이는 P1/P6의 학습 계열로 hand-off.
③ 벽인데 평행선쌍이 아닌 표현(단선 벽, 폴리라인 벽, 해치 벽)은 이 요인공간 **밖** → 탐지 불가, 발명
불가.

**deterministic_note.** 완전 결정: (노브,도면) 고정 시 순수 함수 → **셀내 반복 절대 무의미**, 반복=outer
population로만(정확히 card rule 7의 교과서 사례). randomization 방어 대상 없음(은닉상태 없음, IR freeze).
잡음통계 수입 금지 — S/N은 **도면 간** 산포에서만 나온다.

**Verification design 5요소.** truth=`T-META`(무라벨)+`T-SYN` · leakage=`L-FIRM`(outer가 firm 블록) ·
prereg=R-META 밴드+2×std 규칙 · kill=아래 · cheapest_probe=아래.

**compute_plan.** **전부 로컬**(결정·경량). DGX 불필요. RAM: IR freeze 후 스트리밍 평가로 낮음. 첫
신호=시간 단위.

**kill_condition.** L9 최적 셀의 R-META가 hold-out firm에서 FAIL(>0.10)로 붕괴 → 강건 설정이 firm
규약에 과적합(일반 벽 아님). 또는 전 그리드 plateau → 결정 휴리스틱 천장 확정, 계열 이관.

**cheapest_probe.** L9 9행을 **단일 5장 표본**에만 먼저 → 30분 내 노브 민감도 방향 확인 후 40장 확장.

**expected_failure_modes.** ① 평균 최적을 강건 최적으로 착각(분산 무시)—Taguchi S/N이 바로 이걸
방어. ② mm/m 단위 혼재가 gap 밴드를 깨 거짓 분산 유발(unit을 outer 층으로 명시해 흡수). ③ L9
상호작용 별칭을 잊고 main을 clean으로 오독.

---

### P3 · TRUTH-SOURCE VALIDITY CROSS-FACTORIAL — 부트스트랩 사슬이 실제로 닫히나

**Mechanism (1문단).** 사람 라벨 0 제약(제약 1) 하에서 프로그램 전체의 생사는 **정답원이 믿을 만한가**
하나에 달렸다. 이 좌석의 signature를 정답원 검증에 직접 겨눈다: 학습-정답원과 평가-정답원을
**교차(crossed)** 시킨 설계. train {T-SYN, T-EXT, T-SILVER} × eval {T-SYN, T-EXT, T-SILVER, T-META}.
관심 신호는 **train×eval 상호작용**이다. 대각(같은 원으로 학습·평가)은 높고 비대각(다른 원으로 평가)이
급락하면, 그 탐지기는 벽이 아니라 **그 정답원의 버릇(합성 생성기의 산술 tell, silver 판정자의 편향)**을
학습한 것 — 부트스트랩 사슬이 안 닫힌다는 증거다(R28 "leaky split→false progress" kill risk를 상호작용
효과로 계량). 이는 평가기준 2(사슬이 실제로 닫히는가)를 **추정 가능한 상호작용**으로 바꾼, 이 좌석만
할 수 있는 메타실험이다.

**factors:**
- `A train_truth` | {T-SYN, T-EXT, T-SILVER} | Y | 학습 신호원.
- `B eval_truth` | {T-SYN, T-EXT, T-SILVER, T-META} | Y | 평가 신호원(교차).
- (보조) `C model_family` | {deterministic-tuned, learned} | Y | 사슬 폐합이 계열에 의존하나 부수 확인.

**response.** metric=`R-EXT`/`R-SYN`/`R-SILVER`/`R-META`(평가원에 따라) → **정규화 대각-대비-비대각
낙폭**. type=혼합(게이트+measure). source=B가 지정. direction: 낙폭 ↓(작을수록 사슬 폐합).

**design.** **crossed 3×4 = 12 셀**(×C 2수준 = 24). 각 셀 = A로 학습→B로 평가.

**resolution_alias.** 완전교차(full crossed)라 train·eval **main과 train×eval 상호작용을 완전 분리**(별칭
없음) — 이 상호작용이 정확히 표적이므로 fraction 쓰지 않는다. C를 넣으면 3원 상호작용 A×B×C가
2원과 부분 별칭될 수 있음을 명시(C는 보조라 24셀 여유되면 완전, 아니면 A×B만 clean 유지).

**prereg_model.** 추정: A·B main + **A×B 상호작용(표적)**. 임계: 비대각 평균 낙폭이 대각 대비 상대
20%p 초과면 "정답원 특이 과적합"으로 판정(사전 봉인). 특히 train=T-SYN→eval=T-EXT 낙폭이 벽:
합성으로 배운 게 실무로 안 감.

**noise_factors.** 도면 population은 반복축; L-FIRM 블록. 비robustness 표적이라 outer array는 최소
(층화 30장). 정답원 잡음 자체(silver 비결정)는 T-SILVER 축의 내재 잡음으로 명시.

**run_matrix.** 12(또는24) 셀 매트릭스, 각 30장 평가. 순서: learned 셀만 무작위화. 캐시 IR freeze.
T-SILVER 관여 셀은 silver 생성 3회 반복(잡음 상속 반영).

**effects_table (UNRUN).** 슬롯 = A·B main + 12셀 대각/비대각 낙폭 행렬. 사전 가설: 대각 전부 높고,
T-SYN→T-EXT·T-SILVER→T-EXT 비대각이 최대 낙폭. null도 보고(어떤 정답원이 서로 잘 전이되면 그 쌍은
호환).

**interactions_found (UNRUN).** 표적 A×B. 사전 가설: 크다(정답원 특이성 존재) → "합성 정답이면
충분"·"silver면 충분" 단독 주장 반증 예상(card rule 4). status=UNRUN.

**confirmation_run.** 가장 잘 전이된 (train,eval) 쌍을 hold-out firm에서 재실행해 전이 안정성 확인.
status=`PASS_WITH_DEFERRAL`.

**abstentions.** ① **어느 정답원이 진짜 참인지**는 못 답함 — 상호 전이만 잰다(외부 절대 진리 없음이 이
과업의 근본 제약). 전 쌍이 서로 낮게 전이되면 "믿을 정답원이 없다"가 결론이고 이는 사람라벨/새
정답원 조달 결정(abduction/조달 좌석)으로 hand-off. ② T-EXT는 NC 라이선스라 **참조만**, 학습가중치
탑재 불가(R23) — 그래서 T-EXT-train arm의 산출물은 방법검증용이지 제품 아님.

**deterministic_note.** 결정 탐지기 셀은 순수 함수, 반복=population. T-SILVER 관여 셀만 비결정 → silver
생성 반복 유의미(비대칭). T-SYN/T-META/T-EXT는 결정.

**Verification design 5요소.** truth=4원 교차 자체가 검증장치 · leakage=`L-FIRM`+`L-SEED`(합성
seed-disjoint) · prereg=20%p 낙폭 임계 · kill=아래 · cheapest_probe=아래.

**compute_plan.** 로컬: 결정 arm 전 셀 + 소형 학습. DGX: learned×T-EXT 대형 학습만. 첫 신호: 결정
arm 대각/비대각만 며칠 내.

**kill_condition.** 대각조차 FAIL 밴드면 정답원이 애초에 학습가능 신호 없음 → 프로그램 근본 재검토.
비대각이 전부 붕괴면 어떤 단일 정답원도 일반화 못 함 → 다원 앙상블 정답 또는 사람라벨 조달 필요.

**cheapest_probe.** T-SYN↔T-META 2×2 소각(4셀)만 먼저 — 합성으로 배운 게 무라벨 metamorphic
게이트라도 통과하나? 반나절.

**expected_failure_modes.** ① 대각을 성공으로 오독(비대각 낙폭이 진짜 지표). ② T-EXT 좌표계/축척이
자기 IR과 안 맞아 거짓 낙폭(CRS 정합 선행 필요, R23 kill). ③ silver 잡음을 상호작용으로 오인(silver
반복으로 분리).

---

### P4 · RLVR-EARNS-ITS-SEAT FACTORIAL — R26 C07을 교리 아닌 효과로 판정 (제약 4 정면)

**Mechanism (1문단).** R26 C07("고정라벨 분류에 RL은 오용, supervised가 저분산·표본효율")은 **맥락
없는 단정**으로 적혀 있다. 발주자가 이의를 제기했다(제약 4). 이 좌석의 정직한 처리법은 C07을
prior로 받거나 기각하는 게 아니라 **효과로 추정**하는 것이다. 패러다임을 요인 수준으로 놓고 그
main effect **와 상호작용**을 잰다. C07의 예측은 명확하다: RL의 main effect ≤ 0 이며 **상호작용
없음**. P4는 패러다임이 라벨예산·정답원품질과 **간섭하는가**를 시험한다. 만약 "패러다임×예산"
상호작용이 크면(라벨 희소일 때 active-acquisition/RLVR가 이기고, 라벨 풍부일 때 supervised가 이김),
C07의 맥락없는 교리는 반증된다(card rule 4). 동시에 RLVR의 생사는 verifier 건전성(R26 U02, CON02)에
달렸으므로 그 축을 요인에 포함해 **reward-hacking을 상호작용으로 검출**한다.

**factors:**
- `A paradigm` | {supervised-silver, RLVR-verifiable-reward, active-acquisition-policy} | Y | 핵심 축.
  RLVR 보상 = R-META 게이트통과 + R-SYN F1(검증가능 보상, R26 C04의 home). active = 다음 라벨할
  도면 질의 정책(horizon>1, 진짜 RL-shaped).
- `B truth_quality` | {high(T-SYN clean), low(noisy T-SILVER)} | Y | verifier 건전성 대리(U02).
- `C label_budget` | {scarce, abundant} | Y | C07의 "표본효율" 주장이 사는 축.
- (내장) reward-hacking 프로브: 보상 {gate-only} vs {gate+hold-out 벌점} 대조.

**response.** metric=hold-out `R-SYN`/`R-SILVER` F1 + **라벨당 밴드도달비용**(active용). type=혼합.
source=`T-SYN`/`T-SILVER`, 보상은 `T-META`. direction: F1 ↑, 비용 ↓.

**design.** `A(3)×B(2)×C(2)` = **12셀 완전요인** + reward-hacking 프로브 2셀. 패러다임이 3수준이라
분수 안 씀(상호작용이 표적).

**resolution_alias.** 완전요인 → 모든 main·2FI·3FI 분리(별칭 없음). 이 좌석이 상호작용을 표적하므로
값을 치르고 완전요인 채택. 청구서: 12셀 학습비용이 비쌈(그래서 cheapest_probe로 축소 경로 둠).

**prereg_model.** 추정: A·B·C main + **A×C(표적: 패러다임×예산)** + A×B(패러다임×verifier품질). 사전
봉인 판정: (i) A×C 유효(Lenth ME 초과)면 C07 맥락없는 판 **반증**; (ii) A×C null이고 A main≤0이면
C07 **지지**(정직하게); (iii) RLVR-verifiable가 low truth_quality에서 gate↑ & hold-out↓면
reward-hacking 확정(C08). 밴드=R-SYN/R-SILVER 공통 밴드.

**noise_factors.** 도면 population 반복, L-FIRM 블록. active-acquisition은 순차라 **run-order가
실질적**(카드 rule 6): 질의순서를 정책이 정하되 seed 고정+기록.

**run_matrix.** 12셀 + 2 프로브. 각 hold-out firm 평가. 순서: 전 셀 학습 포함 → 무작위화, seed
기록. 캐시 IR freeze. RLVR/active는 rollout 로그 보존.

**effects_table (UNRUN).** 슬롯 = A(3수준 대비)·B·C main + A×C·A×B. 사전 가설: supervised가 abundant에서
최고, RLVR/active가 scarce에서 최고, RLVR가 low-truth에서 hacking. null도 보고(예: high-truth에서
패러다임 무차별이면 "정답원이 좋으면 방법 무관"이 승리).

**interactions_found (UNRUN — 이 제안의 핵심).** 표적 A×C. 사전: 크다 → C07 맥락없는 단정 반증
예상. A×B: RLVR의 가치가 verifier 건전성에 조건부(CON02를 효과로). status=UNRUN.

**confirmation_run.** scarce-budget에서 이긴 패러다임(가설상 active/RLVR)을 새 hold-out firm에서 단독
재실행 + hacking 재점검. status=`PASS_WITH_DEFERRAL`. **미확인 RL 우위를 PASS로 올려 부르지 않는다.**

**abstentions.** ① **terminal 벽/비벽 라벨링 그 자체**(고정 특징→고정 카테고리)에 RL을 쓰는 것은 이
설계도 지지 안 함 — 그 수준(RLVR-terminal)은 지고, C07의 **핵심(좁은 판)**은 옳다고 예상. 이 좌석은
C07을 통째 부정하지 않고 **적용범위를 갈라준다**: 오용 자리(terminal 분류)와 정당한 자리(active
acquisition·tool-routing bandit·RLVR-with-sound-verifier)를. ② verifier가 실제로 건전한지의 절대
판정은 U02 별도 lane 몫 — 여기선 대리(B)로만. ③ bounded-RSI 안전성(R26 C11)은 범위 밖.

**deterministic_note.** supervised 셀은 (데이터,seed) 고정 시 준결정 → seed 반복으로 분산 추정.
RLVR/active는 **탐색 확률성 내재** → 이 축은 진짜 반복(≥5 seed)이 유의미 — card rule 7의 "은닉상태/
확률성 있으면 반복·무작위화가 방어한다"의 정당한 적용. 즉 P4는 결정 반응이 아니라 **확률 반응**이며,
그래서 잡음통계가 정당하게 들어오는 유일한 제안(다른 제안과 대칭 아님을 명시).

**Verification design 5요소.** truth=`T-SYN`/`T-SILVER`+보상 `T-META` · leakage=`L-FIRM`(active가 같은
firm 재질의 못 하게) · prereg=A×C 판정 규칙+hacking 서명 · kill=아래 · cheapest_probe=아래.

**compute_plan.** DGX 주력: RLVR rollout·active 반복학습은 GPU·반복이 커 DGX Spark 배치(vLLM 호스트와
시분할, 야간). 로컬: supervised baseline·소형 seed 반복. 첫 신호: supervised×예산 2×2만 로컬 며칠 내로
C07 핵심부터.

**kill_condition.** A×C null + RLVR/active가 어느 예산에서도 supervised 못 이김 → C07 지지, RL 계열
프로그램에서 하차(정직한 kill). 또는 RLVR가 이겼는데 전부 hacking 서명 → 가짜 승리, verifier 수리
선행.

**cheapest_probe.** {supervised, active} × {scarce, abundant} 2×2 (4셀)만 먼저, RLVR 제외 — active가
scarce에서 라벨당 F1을 supervised보다 올리나? 이 하나가 C07 맥락없는 판을 흔드는 최소 실험.

**expected_failure_modes.** ① proxy(게이트) 보상 hacking을 승리로 오독 — hold-out 벌점 쌍이 방어(R26
C08). ② verifier 불건전이 RLVR 천장을 은밀히 덮음(U02) — B 축이 노출. ③ active 정책의 질의순서
은닉상태를 상호작용으로 오인(seed 기록으로 분리). ④ 확률 반응에 결정 통계 적용(반대 오류도) 경계.

---

### P5 · METAMORPHIC INVARIANCE BATTERY — 무라벨 반응 엔진 + 최저비용 프로브

**Mechanism (1문단).** 참인 벽 탐지기는 **라벨 없이도** 반드시 만족해야 하는 관계가 있다: 도면을
평행이동·회전·균일축척·단위변환(mm↔m)·블록분해(explode)·레이어개명·좌표정밀도 흔들기 해도 **같은
엔티티에 대한 벽 판정은 불변(또는 등변)**이어야 한다. P5는 이 metamorphic 관계들을 요인화한
배터리다: {변환종류} × {탐지기계열}, 반응 = 위반율(불변이어야 할 판정이 바뀐 비율). 이는 정답
라벨을 **한 개도** 요구하지 않으므로 프로그램에서 가장 싼 신호이자, 다른 모든 제안의 **게이트
반응(R-META)을 만들어내는 엔진**이다. 부수 효과로 R28이 UNKNOWN으로 남긴 "유효한 CAD metamorphic
관계 카탈로그"(U28-002)를 실제로 구축한다. `synthetic_truth.py`의 "correct-by-construction + 1 seeded
violation" 패턴(내가 코드에서 읽음)이 정확히 이 mutation-testing 골격이며 벽으로 확장하면 된다.

**factors:**
- `A transform` | {translate, rotate, uniform-scale, unit-change, block-explode, layer-rename,
  coord-jitter} | Y | 7 metamorphic 관계. 전부 결정 변환.
- `B detector_family` | {deterministic(v0), classical-ML, GNN, VLM} | Y | 어느 계열이 애초에
  자기일관적인가.
- (내장) `expected_relation` | {invariant, equivariant} | Y | scale/unit은 등변(치수 스케일), 나머지
  불변 — 관계별 정답 봉인.

**response.** metric=`R-META` 위반율. type=**결정 게이트**(무라벨). source=`T-META`. direction=↓.

**design.** `A(7)×B(4)` = **28셀** 완전요인, 각 셀 145 아카이브(또는 층화 40장) 위 위반율 집계.
mutation 변형은 도면당 여러 seed로.

**resolution_alias.** 완전요인 → A·B·A×B 완전 분리(별칭 없음). 값 쌈(결정)이라 fraction 불필요.
청구서: A×B 완전 추정 가능이 이 설계의 강점.

**prereg_model.** 추정: A main(어느 변환이 잘 깨지나)·B main(어느 계열이 자기일관)·**A×B**(계열별
취약 변환). 임계: 위반율 밴드 PASS≤0.02 / INCONCLUSIVE 0.02–0.10 / FAIL>0.10(사전 봉인). 등변 관계는
스케일 보정 후 위반 판정.

**noise_factors.** 도면 population = 반복축(L-FIRM 블록). 변환 파라미터(회전각·축척율)는 각 변환 내
**여러 값 샘플**(불변이면 값 무관해야 함 — 값에 의존하면 그 자체가 위반).

**run_matrix.** 28셀 × 40도면 × 변환파라미터 표본. 순서 무관(순수 결정; 기록). 캐시 IR freeze. VLM 셀만
추론 비결정 가능성 → 온도 0 고정.

**effects_table (UNRUN).** 슬롯 = 7 변환·4 계열 위반율 + A×B 행렬. 사전 가설: v0는
translate/rotate/unit엔 강하나(순수 기하) scale 밴드경계·layer-rename엔 취약(gap_range mm 하드코딩,
layer 미사용이라 개명엔 강함). GNN/VLM은 layer/좌표 절대값에 과의존해 translate/rename에 취약 예상.
null 보고(불변 완벽 계열=그 관계 통과).

**interactions_found (UNRUN).** 표적 A×B(계열별 취약 변환). 사전: 크다 — "이 계열이 낫다"는 단독
주장을, 특정 변환에서만 무너진다는 사실이 반증. status=UNRUN.

**confirmation_run.** 가장 자기일관적 계열을 hold-out firm에서 재실행해 위반율 재확인 + 새 변환 1종
추가시 유지되나. status=`PASS_WITH_DEFERRAL`.

**abstentions.** ① metamorphic 일관성은 **필요조건이지 충분조건 아님** — "모든 변환에 불변"이어도 그게
벽을 맞게 찍는단 보장 없다(완벽히 일관되게 **틀릴** 수 있음). 그래서 P5는 **선별 게이트**지 최종
판정이 아니며, 반드시 R-SYN/R-SILVER(P1/P3)와 짝지어야 한다. ② 목록 밖 변환(예: 미러링, 참조도면
병합)은 발명 못 함 — 카탈로그는 명시된 7개로 한정. ③ 어떤 계열이 **왜** 취약한지의 인과는 별도.

**deterministic_note.** 순수 결정(변환·도면·config 고정 시 함수), VLM 셀만 온도0로 결정화. 반복=도면
+변환파라미터 population로만; 은닉상태 없음(IR freeze). 이 제안이 card rule 7 "결정 반응엔 잡음통계
수입 금지"의 가장 순수한 사례.

**Verification design 5요소.** truth=`T-META`(무라벨, 자기생성) · leakage=변환은 같은 도면 내라 도면간
누수 없음; 계열 학습 arm은 `L-FIRM` · prereg=위반율 밴드 · kill=아래 · cheapest_probe=아래.

**compute_plan.** **전부 로컬**(결정 변환+집계). VLM 계열 셀만 DGX 추론(온도0). 첫 신호=시간 단위
(v0 계열은 즉시).

**kill_condition.** v0(결정)조차 위반율이 전 변환 FAIL(>0.10)이면 → 현 휴리스틱이 기하학적으로도
불안정(gap mm 하드코딩이 unit-change에서 붕괴 등) → 노브/단위정규화 선수리(P2로). 학습 계열이 전
변환 취약이면 그 계열은 절대좌표 과적합 — 표현 정규화 없이는 부적격.

**cheapest_probe.** v0 탐지기 × {rotate, unit-change} 2셀만 5장에 — 30분 내 "현 탐지기가 회전·단위에
불변인가"라는 가장 기본적 위생 점검. (unit-change는 `gap_range=(30,500)` mm 하드코딩 때문에 깨질
강한 사전 의심 — 이 프로브가 그걸 즉시 드러냄.)

**expected_failure_modes.** ① 일관성을 정확성으로 착각(필요≠충분) — R-SYN 짝으로 방어. ② 등변 관계를
불변으로 잘못 봉인해 scale에서 거짓 위반(관계별 정답 사전봉인으로 방어). ③ VLM 온도>0가 거짓 위반율
부풀림(온도0 강제).

---

### P6 · VLM-MODE × MODALITY-FUSION FACTORIAL — VLM 계열의 프로그램 편입 (제약 5)

**Mechanism (1문단).** 제약 5는 VLM을 배제하지 말되 두 갈래(로컬 오픈VLM **파인튜닝** vs 프런티어VLM
**프롬프팅**)를 나눠 다루고, R23 판례("vision-as-SoT 기각, VLM은 판정자 아닌 배심원")와 정합하라 한다.
DOE로 옮기면: VLM-모드는 요인의 두 수준이고, 배심원(프롬프트-silver)과 탐지기(파인튜닝) 역할은
**정답원 축이 아니라 산출 역할이 다른 별개 arm**이다. P6는 {VLM-모드}×{모달리티}×{감독원}을 요인화해,
핵심 질문 — **래스터+벡터 융합이 파인튜닝된 오픈VLM에서만 이득인가, 프롬프팅된 프런티어VLM에서도
이득인가**(모드×모달리티 상호작용) — 을 추정한다. 프런티어-프롬프트 arm의 산출은 **silver(배심원)**로만
쓰고 SoT로 굽지 않으며(R23), 오픈-파인튜닝 arm만 탐지기 후보다. 이로써 프로그램의 DL/VLM 커버리지가
채워진다(평가기준 5).

**factors:**
- `A vlm_mode` | {frontier-prompt(juror→silver), open-finetune(detector)} | Y | 두 갈래.
- `B modality` | {raster-only, vector-only, raster+vector-fused} | Y | 융합 이득의 조건성.
- `C supervision` | {T-SYN, T-SILVER} | Y | 파인튜닝 감독원(프롬프트 arm은 few-shot 예시원).

**response.** metric=`R-META` 게이트 + `R-SYN` F1(교차 `R-SILVER`). type=혼합. source=`T-SYN`/`T-SILVER`
+`T-META`. direction=↑(F1), ↓(위반율).

**design.** `A(2)×B(3)×C(2)` = **12셀 완전요인**. 각 셀 학습(또는 프롬프트 구성)→평가.

**resolution_alias.** 완전요인 → main·2FI·3FI 완전 분리. 청구서: VLM 파인튜닝 12셀은 **DGX 시간이
비쌈**(가장 무거운 제안) — 그래서 cheapest_probe에서 프롬프트 arm부터.

**prereg_model.** 추정: A·B·C main + **A×B(모드×모달리티, 표적)** + B×C. 사전 봉인: A×B 유효면 "융합
이득이 모드에 조건부"(파인튜닝에서만) → "VLM은 좋다/나쁘다" 단독 주장 반증. 밴드 R-SYN/R-META 공통.

**noise_factors.** 도면 population 반복, L-FIRM 블록. 래스터 렌더 해상도·DPI는 **비설정 잡음이 아니라
설정**이므로 B의 일부로 고정(변동 금지). VLM 추론 비결정 → 온도0 + few-shot 순서 고정.

**run_matrix.** 12셀 × hold-out firm 평가. 순서: 학습 셀 무작위화, seed 기록. 프롬프트 arm은 few-shot
예시 집합 고정(은닉상태 제거). 캐시 IR/render freeze.

**effects_table (UNRUN).** 슬롯 = A·B·C main + A×B·B×C. 사전 가설: fused>vector>raster(파인튜닝),
프롬프트 arm은 raster에서만 쓸만(프런티어가 벡터 텍스트 약함). null 보고(융합이 무이득이면 벡터-only로
충분).

**interactions_found (UNRUN).** 표적 A×B. 사전: 크다 — 융합 이득이 파인튜닝 전용이라는 조건성 예상.
B×C: 융합의 감독원 민감도. status=UNRUN.

**confirmation_run.** 최적 (모드,모달리티,감독) 셀을 hold-out firm 재실행 + 프런티어 arm은 배심원
자격만(SoT 승격 금지) 재확인. status=`PASS_WITH_DEFERRAL`.

**abstentions.** ① 프런티어-프롬프트 arm은 **탐지기 후보가 아님**(배심원=silver 생성원) — 이 설계는
그것을 SoT로 승격하지 않는다(R23 판례 준수). ② 오픈VLM 가중치의 **제품 탑재**는 NC 데이터셋
오염(R23 kill)과 별개로, T-EXT로 학습 시 라이선스 제약 — 방법검증 산출일 뿐. ③ VLM이 벽을 왜 그렇게
보는지의 해석가능성은 범위 밖.

**deterministic_note.** VLM 추론은 온도0로 결정화하나 **파인튜닝 seed는 은닉상태** → seed 고정+기록,
민감도 의심 시 seed 반복. 프롬프트 arm은 few-shot 순서가 은닉상태 → 고정. 즉 P6는 순수 결정 아님 →
seed 축에서만 반복이 정당(전면 잡음통계 아님).

**Verification design 5요소.** truth=`T-SYN`/`T-SILVER`+`T-META` · leakage=`L-FIRM`+`L-SEED`(합성),
래스터 arm은 렌더 해상도 고정 · prereg=A×B 판정+밴드 · kill=아래 · cheapest_probe=아래.

**compute_plan.** **DGX 주력**: 오픈VLM 파인튜닝 12셀은 GPU 무거워 DGX Spark(vLLM 호스트와 야간
시분할). 로컬: 렌더·평가 집계·프롬프트 arm 오케스트레이션. 프런티어 프롬프트는 외부 접근(배심원). 첫
신호: 프롬프트 arm silver 대조(파인튜닝 0)로 며칠 내.

**kill_condition.** 파인튜닝 최적 셀이 v0 결정탐지기(P2 강건설정)를 R-SYN/R-META에서 **못 이기면** →
VLM 투자 대비 무이득, 계열 하차(정직한 kill). 프런티어 배심원 silver가 E1.5 대비 신호 0이면 juror
자격 미달.

**cheapest_probe.** frontier-prompt × raster-only 1셀만 5장에 — 프런티어VLM이 래스터 평면도에서 벽을
silver로 찍을 능력이 **있기라도 한가**를 반나절에. 없으면 파인튜닝 arm만 남기고 프롬프트 갈래 조기
종료.

**expected_failure_modes.** ① 프런티어 배심원을 SoT로 슬며시 승격(R23 위반) — arm 역할 사전분리로
방어. ② 래스터 렌더 축척/DPI 변동이 거짓 모달리티 효과(렌더 freeze로 방어). ③ 파인튜닝 seed 잡음을
모달리티 상호작용으로 오인(seed 기록). ④ NC 데이터로 튜닝한 가중치가 제품 경로 오염(방법검증 전용
격리).

---

## PROGRAM-LEVEL 정직 한계 (이 좌석이 못 하는 것)

- **이 좌석은 요인을 발명하지 못한다(card ABSTAIN).** 위 6개 배터리가 전부 plateau(전 그리드에서
  반응이 안 움직임)를 보이면, 그 신호의 의미는 "튜닝·계열선택으로 안 됨 = 천장이 그리드 밖"이며 이는
  **abduction/가설생성 좌석으로의 hand-off 신호**다 — 벽을 정의하는 아직 이름 안 붙은 신호(예: 해치
  poché, 텍스트 주기, 치수 참조, 다른 도면장 상호참조)가 있을 수 있고, 그건 다른 좌석이 내야 한다.
- **절대 진리는 이 과업에 없다.** P3가 정답원 상호 전이만 재고 "무엇이 참인가"는 못 답하듯, 사람라벨
  0 제약 하에서 모든 반응은 대리(합성/silver/metamorphic/외부NC)다. 이 좌석의 방어는 **여러 대리를
  교차**시켜 어느 하나에 사슬이 갇히지 않게 하는 것뿐이다.
- **모든 수치는 미실측(Phase A).** effects_table·interactions_found·confirmation_run은 전부 UNRUN
  슬롯+사전가설. 확정 실험 없이는 어떤 순위표도 판정이 아니다(card rule 3).

## 우선순위 권고 (SYNTHESIZE 참고, 순서는 평가기준 3·1)

1. **P5(metamorphic)** + **P2(Taguchi robust)** — 라벨 0·로컬·시간 단위, 다른 모든 제안의 게이트
   반응을 만든다. **가장 먼저.**
2. **P3(정답원 검증)** — 부트스트랩 사슬 폐합을 먼저 확인해야 P1/P4/P6 학습 투자가 헛되지 않음.
3. **P1(master screen)** — 활성 요인·계열을 값싸게 좁힘.
4. **P4(RLVR 판정)** + **P6(VLM)** — 활성 확인 후 DGX 무거운 투자, 제약 4·5 정면.
