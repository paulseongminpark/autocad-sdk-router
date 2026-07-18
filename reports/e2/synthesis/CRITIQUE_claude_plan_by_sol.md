# `PLAN_claude.md` 교차 비판 — sol

## 0. 총판정

**판정: `MAJOR_REVISION_REQUIRED`.** B의 계획은 공유 생성기·CRS·verifier, 고전 ML 우선의 Occam gate, 단일 GPU 직렬화, DGX/API 차단, 방법당 test 단발이라는 큰 골격은 맞다. 그러나 현재 문안 그대로는 실행 안전하지 않다. 서로 다른 가설과 판정 단위를 한 셀에 합친 곳이 있고, 원문이 강제한 선후관계를 거꾸로 병렬화했으며, 권리·봉인·대조군·방법별 confirmation 계약이 `TESTLEDGER` 하나로 축약됐다. 특히 face-first 반대가설과 API와 무관한 local open-finetune 갈래가 소실됐다.

- 감사 범위: 지정된 26부의 §6 실험 셀을 전부 역대조했다. `CELLS_INDEX.md`는 26부에 포함하지 않았다.
- 수치 취급: 아래 수치는 모두 해당 도시에의 문장을 직접 인용한 것이다. 새 측정값·새 예산·새 PASS를 만들지 않았다.
- 판정 원칙: 더 엄격한 수치를 무조건 공용화하는 것은 보수성이 아니다. 서로 다른 claim의 자격선을 한 값으로 덮어 한 갈래의 생존 정보를 지우면 잘못된 병합이다.

## 1. 판정 표

| 항목 | 동의/이의/누락 | 근거(도시에 원문 인용 포함) | 심각도 |
|---|---|---|---|
| 공유 생성기·CRS·verifier를 선결 계측기로 승격 | 동의 | B의 `GEN-1`, `CRS-0`, `VER-1` 방향은 타당하다. `calibration_P4.md:482-489`는 CRS를 “model과 무관”한 자격 셀로 두고 “이 셀 PASS는 성능 증거가 아니라 측정기 자격”이라고 한다. `calibration_P6.md:396-400`도 verifier의 `FAR≤0.01 ∧ FRR≤0.05`와 실패 시 정책 학습 중단을 명시한다. 단, 아래 행들처럼 소비자별 gate와 firewall을 보존해야 한다. | LOW |
| 고전 ML Occam gate 뒤에 GNN을 둠 | 동의 | `platt_P2.md:678-681`: “`Δ_main ≥ +0.10`이면” 저비용 해법으로 보고 “HistGradientBoosting이 support band를 충족하면 production ladder에서 GNN을 중단한다.” B의 `CML-1→GNN` 개폐는 원문과 정합한다. | LOW |
| DGX 불통·API 미결재를 local PASS로 대체하지 않음 | 동의 | `doe_P6.md:250-254`는 DGX를 `unreachable`, 프런티어 API를 미승인으로 적고 승인 전 frontier 갈래를 차단한다. B가 DGX/API queue를 별도로 둔 것은 맞다. 다만 같은 원문은 “승인 없으면 frontier 갈래 `BLOCKED`로 기록하고 open만”이라고 하므로 open 갈래까지 API에 묶은 것은 별도 HIGH 이의다. | LOW |
| `doe_P1` broad screen PARK | 동의 | `doe_P1.md:13-20`은 현 설계를 즉시 실행 가능한 인과 스크린이 아니라고 판정하고, 합성 자격·paired representation·처치 정의·alias 해소 뒤에만 순차 재개하도록 한다. B의 PARK 자체는 맞다. | LOW |
| 프로그램 공통 계약 셀 부재 | 누락 | B의 `TESTLEDGER`는 test 접근 횟수만 다룬다. 그러나 `calibration_P1.md:590-595`는 family 단위 split, manifest-derived seed, `val=개발`, `test=방법당 단발`, raw artifact와 evidence xlsx를 **모든 셀**에 요구한다. 같은 문서 `597-604`는 S/F/M identity, split, band, import boundary, resolver 격리를 test 전에 봉인하는 C0를 별도 셀로 둔다. `calibration_P2` Cell 0·`calibration_P3` E0·`calibration_P4` P4-0·`platt_P2` G0의 계약 책임도 B의 `GEN-1` 또는 개별 사다리 안에 흩어졌다. 공통 `CONTRACT-FREEZE`가 필요하다. | HIGH |
| 방법별 final confirmation을 `TESTLEDGER`로 일반화 | 이의 | 중앙 원장은 필요하지만 충분하지 않다. `platt_P2.md:438-448`은 test 전에 builder/version, split, feature mask, model/seed, threshold, Occam band, failure rule을 한 manifest에 봉인하고 test 후 변경 시 기존 test 재사용을 금지한다. `calibration_P4.md:537-552`와 `platt_P5.md:630-639`는 각 방법의 고유 진입조건·primary AND band·xlsx schema까지 요구한다. B는 `SCOPE-1 C0–C7`, `MRB-1 C0–C7`, `ASV-1 C0–C6`, `GNN-3 E3–E7`처럼 one-shot 셀을 앞 페이즈의 사다리 범위에 넣으면서 Phase 4와의 경계를 명확히 끊지 않았다. 공통 원장과 방법별 frozen resolver를 둘 다 유지해야 한다. | HIGH |
| `GEN-1`에서 fidelity 수치 하나를 봉인 | 이의 | B는 `PLAN_claude.md:124`에서 하나의 공용 수치를 고르려 한다. 원문은 서로 다른 claim을 판정한다. `calibration_P1.md:612`: “`KS≤0.10`, ... `TV≤0.10`”; `platt_P1.md:522`: “KS≤0.2, ... TV≤0.1”; `feyerabend_P1.md:544`: “`KS_max≤0.30` 및 `TV≤0.20`.” 한 번의 통계 산출은 공유할 수 있지만, 각 소비자의 자격선은 별도로 출력해야 한다. face exploratory 통과가 deterministic 또는 CL-B의 자격이 될 수 없고, 반대로 더 엄격한 gate 실패가 face 가설의 정보까지 지워서도 안 된다. | HIGH |
| `GRAPH-0`에서 `0.995`를 모든 경로의 단일 gate로 사용 | 이의 | `calibration_P3.md:624`는 required relation별·micro recall 각각 `>=0.98`; `platt_P2.md:669`는 exhaustive positive relation recall `≥0.995`를 제안한다. 공용 builder가 전 경로 자격을 얻으려면 후자를 만족해야 하지만, 그 사이 결과에서는 calibration-GNN만 생존할 수 있다. B의 “더 엄격한 쪽 봉인”은 부분 생존 판정을 지운다. | MED |
| Graph/CRS 앞의 canonical world-IR 의존성 | 누락 | B의 `GRAPH-0` 의존은 `GEN-1`뿐이고 `CRS-0`도 canonical INSERT/world expansion과 명시적으로 연결되지 않는다. `feyerabend_P6.md:549-554`는 nested/array/reflection까지의 transform oracle에서 정상 transform 하나라도 틀리거나 silent drop이 있으면 kill이라고 한다. `platt_P2.md:669-670`도 transform/name parity 실패 시 학습 금지다. parser·world transform·lineage 자격을 공유 선결로 올려 Graph/Raster/RL-set이 같은 IR을 보게 해야 한다. | HIGH |
| `UNIT-1`과 `TAG-1`을 Phase 1에서 병렬 실행 | 이의 | `feyerabend_P2.md:997-1001`의 직접 명령은 “C2가 ... 선행 판별”이며 “이 셀이 끝나기 전 doe P2의 절대 band robust optimization이나 다중 knob Taguchi를 실행하지 않는다”이다. 이유도 “절대 band가 나쁜가, 튜닝이 나쁜가”의 confound 방지로 명시돼 있다. B의 Phase 1 병렬화는 과학적 식별성과 자원을 동시에 해친다. `UNIT→TAG` DAG로 고쳐야 한다. | HIGH |
| face/ribbon/poché 반대가설 전체 | 누락 | `feyerabend_P1`의 E1–E5가 독립 트랙으로 보존되지 않았다. `feyerabend_P1.md:549-556`은 parallel 가중치가 없어도 face-first가 known bridge를 회수하는지를 묻고, `569-579`는 LINE-pair v0가 계속 0인 messy divergent 사례에서 face bridge가 의미 있는 일부를 회수하는지를 핵심 판별로 둔다. `582-586`은 기존 geometry feature와 다른 조건부 정보와 proxy 오류구조를 묻는다. B의 `GEN-1`에 E0만, `IND-1`에 E4만 귀속하면 detector/counter-theory 자체가 사라진다. | HIGH |
| `CONV-1`에 convention-only와 geometry-gated prior를 병합 | 이의 | 두 도시는 반대 질문을 한다. `platt_P6.md:14-16,32-34`는 H3를 측정하기 위해 “피처를 의도적으로 빈약하게(기하 배제)” 둔 **측정기**다. `feyerabend_P7.md:9-11`은 `관례 prior → 기하 확인 → 게이트 내부 재순위화`이며 `G(h)=0`이면 이름이 WALL이어도 출력 금지인 **배포 후보**다. B의 한 셀은 기하 배제를 요구하면서 동시에 기하 gate를 요구하므로 가설·kill·출력 의미를 소거한다. 둘을 분리해야 한다. | HIGH |
| `RL-0`에 acquisition horizon과 set-assembly landscape를 병합 | 이의 | `calibration_P6.md:426-434`의 질문은 추가 probe의 정보가치가 horizon-one bandit에 흡수되는지이며 지표는 planning utility다. `platt_P4.md:317-324`의 질문은 같은 candidate/verifier에서 beam·greedy·ILP의 **집합 조립 F1/상한 gap**이다. `platt_P4.md:7-10`은 fixed-label, set assembly, acquisition routing, self-training 네 문제를 명시적으로 분리한다. B가 “최엄격=platt 판정식 우선”으로 하나를 다른 하나의 gate로 쓰면 routing RL과 assembly RL이 서로 잘못 죽는다. | HIGH |
| fixed-label RL의 지위 | 이의 | B의 `RLVR-1`은 `platt_P4 E2–E4`를 묶고 E2를 성능 경쟁처럼 남긴다. 원문 `platt_P4.md:7-8`은 fixed-label full RL에는 자리가 없고 RL arm은 음성 대조군이며, set assembly만 본선이라고 한다. `326-333`은 E2에 “HR1 생존권이 없다”고 명시하고, 이상 결과도 supervised 누락을 red-team할 이슈일 뿐 집합 조립 승리로 합산하지 않는다. fixed-label RL은 채택 셀이 아니라 명시적 negative control이어야 한다. | HIGH |
| `doe_P6` local open-finetune 6셀 | 누락 | B는 `doe_P6 전체`를 `VLM-F`에 넣어 API 결재 대기로 묶었다. 그러나 `doe_P6.md:250-254`는 로컬 qwen 모델과 RTX를 가용으로 적고 “승인 없으면 frontier 갈래 `BLOCKED`로 기록하고 open만”이라고 한다. `364-375`는 Open-finetune 6셀을 별도 detector 후보로 정의하고 셀당 local LoRA 예산을 둔다. API가 막혀도 silver 없는 local open screen은 살아 있다. 이는 자원 배정과 밴딩의 동시 오류다. | HIGH |
| `VLM-L`에 raster segmenter·bridge와 silver-student를 병합 | 이의 | `platt_P5.md:7-11`은 frontier VLM, local segmentation, 공통 bridge를 분리하며 두 vision 모델은 truth가 아니라 각각 최대 한 표라고 한다. `calibration_P5.md:309-313`의 local student는 **admission을 통과한 silver**로 학습하는 별도 가설이다. B의 `VLM-L`은 bridge/segmentation과 silver-student를 한 budget·한 band로 묶고, 의존에 `SIL-G`를 적지 않았다. bridge, no-silver open model, silver student를 분리해야 한다. | HIGH |
| E1.5 family-aware consensus | 누락 | B의 `VLM-F`에는 `calibration_P5` P5-C가 없다. `calibration_P5.md:112-116`: “E1.5 5기 = 2 family. 단순 5/5 다수는 family-correlated error를 과소평가한다.” `platt_P5.md:258-264`도 두 어휘 가문을 각각 한 family vote로 접고 raster를 최대 한 표로 둔다. 이 보정 없이 VLM jury를 병합하면 상관된 표를 독립 증거로 과대계수할 수 있다. | HIGH |
| B5를 B4 admission의 부정 증거로 해석 | 이의(부분) | B는 `SIL-G`에서 기존 B5를 부정적 신호로 적었다. `calibration_P5.md:66-78`은 admission을 `E15_B1`과 `E15_B4`의 AND로 정하고 B5는 “게이트 입력이지 통과 증거가 아님”이라고 명시한다. 따라서 exact B1/B4 재산출 전 상태는 OPEN/BLOCKED다. B가 실제 FAIL을 선언한 것은 아니어서 오류는 제한적이지만, 모순 원장에 이 식별자 차이를 명시해야 한다. | MED |
| 권리·lineage·제품 격리와 “API가 유일 잔여 결재” | 이의/누락 | `feyerabend_P5.md:499-506`은 counsel 허용, unknown parent, cross-split, silver 유입을 먼저 감사하고 판단 불명은 `BLOCKED`라고 한다. `582-587`은 NC/unknown 파생물의 product dependency를 별도 셀로 차단한다. `platt_P5.md:561-567`도 counsel 거부·API 미승인·합성팩 부재를 서로 다른 상태로 둔다. 그러므로 B의 “API 결재 — 유일 잔여 결재”는 권리 상태가 확인됐다는 근거가 없는 한 과장이다. 권리 gate는 `RAS-1` 안의 암묵 항목이 아니라 raster/VLM 전 경로의 공통 선결이어야 한다. | HIGH |
| `feyerabend_P4`의 학습 0 S0와 실측 Pareto X | 누락 | B는 S0b·B1·B1-shuf를 가져왔지만 S0와 X를 출처·셀로 보존하지 않았다. `feyerabend_P4.md:303-314`는 S0에서 val/test 규율과 셔플 의무 아래 FULL_SCAN·정적 탐욕을 학습 없이 비교하며, `382-391`의 X는 PR-1 전에도 합성 F1을 주장하지 않고 실도면 비용·metamorphic·recall-floor Pareto만 진단한다. bandit/RL보다 싼 대조군이자 합성 blocker 동안 가능한 제한적 관측이므로 살려야 한다. | MED |
| `calibration_P6` Cell-A와 Cell-G | 누락 | B의 `VER-1`은 Cell-0만, `BAND-1`은 B/D만, `RL-0`은 C만 담는다. `calibration_P6.md:403-412`의 Cell-A는 reward-family와 hidden-family 교차가 0인지 감사하고 교차 시 학습 로그를 폐기한다. `472-480`의 Cell-G는 실도면에서 arm 비용·abstain 방향이 맞는지 보고 불일치 시 “실환경 절감” 주장을 금지한다. 전자는 누출 방화벽, 후자는 simulator-to-real claim 범위이므로 살릴 가치가 있다. | HIGH |
| Phase 1 CPU “전면 병렬”, 병목 없음 | 이의 | B는 RAM 64GB를 근거로 전면 병렬과 “없음”을 썼다. 하지만 `calibration_P1.md:411-418`은 streaming을 전제로 peak RAM `32GB` band와 watchdog을 두고, `feyerabend_P6.md:404-413`은 correctness run을 worker count one으로 고정하고 stress가 `48 GiB`까지 간다고 한다. 각 작업의 상한이 공유 머신 예산에 근접하므로 immutable shard·read-only cache·RAM watchdog·동시성 제한 없는 “전면 병렬”은 자원 계획이 아니다. | HIGH |
| `RLVR-1` GPU 예산 | 이의 | B는 “GPU 24h cap/arm”만 적었다. `platt_P4.md:239-245`는 본선 **각 arm/seed**가 동일 cap이고 세 seed를 로컬 순차 실행한다고 한다. `335-342`도 공통 prefix 뒤 각 arm/seed cap과 RL 세 seed를 반복한다. seed 축과 순차성을 누락한 budget은 단일 16GB GPU queue의 점유를 과소표현한다. | MED |
| 집계 wall-clock과 “함대 분담 시 수일” | 이의 | `calibration_P1.md:612-614`의 원문은 generator를 “구현 1–2인주와 검증 수시간”으로 제안한다. 이는 인력량이지 자동으로 압축되는 wall-clock이 아니다. B의 Phase별 총 주수와 “함대 분담 시 수일”은 원문 인용이나 명시된 staffing/capacity model 없이 새로 만든 일정값이다. 원문 envelope를 queue별로 보존하고, 실제 병렬도 미확정 상태에서는 총 완료시각을 단정하지 말아야 한다. | MED |
| `GNN-3` local E3의 발사 위치 | 누락 | B의 밴딩에는 `GNN-3 로컬부(E3)`가 VIABLE로 있으나 Phase 2 GPU queue와 CPU phase 어디에도 없다. `calibration_P3.md:640-644`의 E3은 비-GNN baseline, leakage, name/layer 진단, shuffle을 동결하는 셀로 E4 이전의 기준면이다. 이를 `CML-1`과 명시적으로 합치든 별도 발사하든 역색인이 필요하다. 현재는 밴드에만 있고 실행되지 않는다. | MED |
| `TAG-1` TOP | 이의 | 원문 선후관계상 `UNIT-1` 결과가 factor definition을 결정하므로 즉시 독립 착수할 TOP가 아니다. `feyerabend_P2.md:1001`의 금지 조문 때문에 `TAG-1`은 unit 판정 뒤의 VIABLE이 맞다. | HIGH |
| `VLM-L`, `CONV-1`, `MRB-1`, `RLVR-1`에 단일 밴드 부여 | 이의 | 각 행이 서로 다른 현재 상태의 하위 셀을 포함한다. 예컨대 `VLM-L`의 no-silver local branch는 실행 가능하지만 silver-student는 admission 의존, `MRB-1 C0–C7`에는 공용 relation 자격과 method/test confirmation이 함께 있고, `RLVR-1`에는 negative-control E2와 gated mainline E3가 함께 있다. 병합 셀에 TOP/VIABLE 하나를 붙이지 말고 instrument/probe/confirmation으로 분할해야 한다. | HIGH |
| 모순 원장: calibration resolution | 누락 | `calibration_P1.md:665`는 `RES≥0.02`; `calibration_P3.md:685`는 GNN final에 `RES>=0.03`을 요구한다. B의 모순 원장에는 없고 일부 통합 행은 calibration을 일반화한다. method-specific calibration gate로 보존해야 한다. | MED |
| 모순 원장: raster 본선·한 표·native handle truth | 누락 | `feyerabend_P5.md:31-35`는 raster를 표현→제안→독립 결정론 판정으로 제한한다. `platt_P5.md:11`은 vision track마다 최대 한 표라고 한다. `calibration_P3.md:346`과 `feyerabend_P5.md:132`는 FloorPlanCAD에 native vector handle truth가 없으며 mask 학습/IoU 축이라고 명시한다. B는 `RAS-2`를 “래스터 본선”으로 쓰면서 이 역할 충돌과 handle metric 정의 조건을 원장에 올리지 않았다. | HIGH |
| 모순 원장: 최대 definition 선분 수 | 누락 | `calibration_P3.md:363`은 최대 definition `412,775 segment`; `platt_P6.md:204`는 `412,965 선분`이라고 적는다. B는 resource plan에서 어느 상수를 쓰는지와 불일치를 기록하지 않았다. 다수 원문·패킷 고정 사실을 쓰고 다른 표기는 오기로 보존해야 한다. | LOW |
| 모순 원장: metamorphic 허용률 | 누락 | `calibration_P1.md:382`의 lineage handle flip은 공식 `≤0.01`, kill `>0.02`; `doe_P2.md:124-128`의 aggregate `R-META`는 별도 PASS/INCONCLUSIVE/FAIL 구간; `platt_P3.md:414-417`의 relation-wise gate는 회전 0 위반과 다른 relation `V_r≤1%`다. B가 셀별 일부 수치는 남겼지만 왜 서로 대체 불가한지를 원장에 기록하지 않았다. 공용 judge는 계산만 공유하고 세 집계단위를 각각 판정해야 한다. | MED |
| 26부 원문 셀의 역색인 | 누락 | B는 읽은 부 수를 선언하지만 원문 셀→통합 셀 교차표가 없다. 실제로 `calibration_P5` P5-C, `calibration_P6` Cell-A/G, `doe_P6` open-finetune, `feyerabend_P1` E1–E5, `feyerabend_P4` S0/X, `feyerabend_P5` P5-00/P5-09, `platt_P1` E6가 소실되거나 다른 역할에 흡수됐다. 실행 전에 전 셀 역색인을 추가해야 “26/26”이 감사 가능한 주장이 된다. | MED |

## 2. 구조적 차이와 판정

| 구조적 갈림 | A(`PLAN_sol`) | B(`PLAN_claude`) | 판정 |
|---|---|---|---|
| 계약 topology | `F00`에서 권리·lineage·split·baseline·seed·evidence를 봉인하고 `F06`에서 방법별 one-shot을 집행 | `TESTLEDGER`와 각 사다리에 분산 | **A가 옳다.** 중앙 접근 원장은 유지하되 그것이 frozen method contract를 대체할 수 없다. |
| 공유 gate의 의미 | 구현·통계 산출을 공유하고 소비자별 threshold를 별도 판정 | fidelity와 graph에서 하나의 가장 엄격한 threshold를 공용 판정 | **A가 옳다.** B 방식은 부분 생존 정보를 지운다. |
| canonical IR | `F03`을 graph·raster·scope·unit의 공통 world-coordinate/lineage 선결로 둠 | `DET`, `UNIT`, `SCOPE`, `GRAPH`, `CRS`에 흩어지고 `GRAPH-0` 의존은 generator뿐 | **A가 옳다.** 공통 IR hash가 없으면 서로 같은 handle universe를 비교한다는 보장이 없다. |
| metamorphic 구조 | `F04` 공용 judge와 method-specific gate를 분리 | `META-1`, `MRB-1`, 각 방법의 metamorphic을 중복 실행 | **A가 옳다.** 단 B의 “단일 독립성 점수 금지”와 원문별 threshold 보존은 A 구현에 반드시 남겨야 한다. |
| unit→robust tuning | `D10→D13` | `UNIT-1 ∥ TAG-1` | **A가 옳다.** 원문이 선행을 직접 명령한다. |
| face-first counter-theory | `D14`로 독립 보존 | detector 셀 없음 | **A가 옳다.** 생성기와 독립성 감사만으로 face detector 가설을 대신할 수 없다. |
| truth-source/independence | `T20`에서 train×eval off-diagonal과 same-item disagreement를 공용 진실면으로 사용 | `XFAC-1`과 `IND-1`로 분리, `IND-1`은 단일 점수 금지 | **A 구조가 더 낫다.** 다만 B의 contingency 공개·단일 점수 금지 조항은 T20의 필수 산출로 승계해야 한다. |
| vision topology | bridge `R50`, local segmenter `R51/R52`, frontier jury `R53`, no-silver open `R54`, silver student `R55` 분리 | `RAS-1/2`, `VLM-L`, `VLM-F`로 역할·truth·자원 혼합 | **A가 옳다.** 특히 API 미승인은 `R53`만 막고 `R54`를 막지 않는다. |
| RL topology | routing `A61/A62`, set assembly `A63/A64`, broad factorial `A65`, fixed-label RL kill 분리 | 공용 `RL-0`이 routing과 assembly를 먼저 병합한 뒤 downstream에서 다시 분리 | **A가 옳다.** 서로 다른 목적함수의 공용 kill을 만들면 안 된다. |
| convention topology | convention-only H3 측정 `C71`과 geometry-gated prior `C72/C73` 분리 | `CONV-1` 하나 | **A가 옳다.** 측정기와 배포 후보는 반대 feature contract를 가진다. |
| 현재-state 밴드 | 미결 gate·DGX·API·broad compute가 남은 셀은 PARKED | gate를 적어 둔 미래 후보를 VIABLE로 넓게 표시 | **결정 필요.** 밴드를 “현재 발사 상태”로 정의하면 A가 맞고, “조건부 과학 가치”로 정의하면 B 표현도 가능하다. 다만 실행 scheduler에서는 미해결 gate 셀을 `BLOCKED/PARKED`로 두어야 한다. |
| CPU/GPU 운영 | GPU one-train queue, CPU immutable shard/cache, RAM watchdog, DGX/API blocked state | GPU 직렬은 명시했지만 CPU는 전면 병렬·병목 없음 | **A가 옳다.** 64GB는 무제한 병렬 허가가 아니다. |
| kill ledger | fixed-label RL, raster-as-SoT, correlated jury, unit-before-Taguchi, quadratic expansion을 명시적 kill로 둠 | 일부는 행의 kill 또는 모순 원장에 암묵적으로만 존재 | **A가 옳다.** 실행자는 암묵 규칙을 안정적으로 집행할 수 없다. |
| 원문 coverage 감사 | 26부 §6의 원문 셀→통합 셀 역색인 제공 | 출처 범위만 적고 역색인 없음 | **A가 옳다.** B의 실제 누락이 이 차이에서 드러났다. |
| 총예산 표현 | 원문 queue envelope를 보존하고 blocked 자원의 완료시각을 미산정 | 페이즈별 총 주수와 인력 압축을 별도 근거 없이 제시 | **A가 옳다.** 원문 수치와 queue 상태만으로 총 wall-clock을 새로 만들지 말아야 한다. |

## 3. B 계획을 살리는 최소 수정 명세

- `TESTLEDGER` 앞에 공통 계약 셀을 추가하고, 마지막에는 방법별 frozen resolver·evidence xlsx·failure witness를 검증하는 confirmation 셀을 둔다.
- `GEN-1`과 `GRAPH-0`은 구현을 공유하되 소비자별 gate 결과를 모두 출력한다. 하나의 “최엄격 PASS”로 축약하지 않는다.
- canonical world-IR/INSERT/lineage oracle을 `GRAPH`, `CRS`, raster, set assembly의 공통 선결로 올린다.
- 실행 DAG를 `UNIT-1→TAG-1`로 고치고, face-first detector를 독립 셀로 복구한다.
- `CONV-1`, `RL-0`, `VLM-L`, `VLM-F`를 각각 가설·truth·자원·kill이 같은 단위로 다시 분해한다.
- API queue에는 frontier 호출만 두고, no-silver local open-finetune은 rights·bridge·generator gate 뒤의 local GPU queue로 복구한다. silver student는 E1.5 admission과 family-aware consensus 뒤에만 둔다.
- 권리/counsel, lineage, NC product isolation을 raster/VLM의 공통 hard gate로 추가하고 `OPEN/BLOCKED/FAIL`을 구분한다.
- CPU lane에도 RAM watchdog과 동시성 cap을 두며, RL budget에는 arm뿐 아니라 seed 축과 로컬 순차성을 보존한다.
- 모순 원장에 graph threshold, calibration resolution, raster 역할/native truth, convention contract, B4/B5 식별자, 최대 definition 불일치, metamorphic 집계단위를 추가한다.
- 마지막으로 26부 §6 원문 셀의 역색인을 붙여 누락이 없는지 다시 감사한다.

CRITIQUE_COMPLETE: sol
