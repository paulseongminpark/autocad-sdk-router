# 라운드 2 적대 비판 — sol이 fable에게

## 증거 경계와 판정 규약

이 비판은 `task.md`, `position_sol.md`, `position_fable.md`만을 근거로 한다. `M`은 세 문서가 측정치와 산출 아티팩트를 연결해 보고한 값, `P`는 실행 전 봉인이 필요한 제안값, `D`는 문서 안 숫자의 명시적 산술, `U`는 미측정이다. 외부 보고서의 실제 내용은 이번 라운드에서 재검증하지 않았으므로, 상대가 인용한 외부 수치는 여기서 독립 확인된 사실로 승격하지 않는다.

severity는 다음과 같다.

- **S0:** 이 상태로 발사하면 봉인·예산·주요 추론이 무효가 되는 launch blocker.
- **S1:** 발사는 가능해도 결론의 인과성·비교 가능성·재현성을 크게 훼손하는 결함.
- **S2:** 주장 범위, 회색지대, 운영 계약을 고쳐야 하는 중요 결함.

각 티켓의 `종결 조건`은 반론의 킬 조건이다. 조건을 만족하지 못하면 티켓이 살아 있고 관련 주장은 채택할 수 없다.

---

## 1. 먼저 steelman: fable의 가장 강한 점

### F-ST1 — 값싼 판별이 비싼 학습을 통제해야 한다

W2-01 오류 해부, W2-02 2-hop classical, W2-07 beam/greedy/oracle 진단을 GNN·raster·Qwen·RL보다 앞에 둔 순서는 AIDE²의 고정비용 선택압을 가장 잘 구현한 부분이다. 특히 RL을 훈련하지 않고 죽일 수 있으면 그것을 성공으로 기록한다는 태도는 옳다.

**생존 조건:** 값싼 판별기의 판정 대상과 truth source가 실제 고가 셀의 주장과 같고, 회색구간·예산·분기표가 사전에 봉인되어야 한다. 아래 S1-RSI-02와 S1-EVAL-02를 못 닫으면 방향만 옳고 판정기는 성립하지 않는다.

### F-ST2 — `0.705`를 최종 일반화 수치로 과장하지 않았다

상대는 반경이 val에서 선택됐고 formal primary인 AUPRC가 현 incumbent에 대해 미산출임을 명시했다. 현재 수치가 강한 개발 기준선이지 test 결과가 아니라는 제한은 정확하다. 이번 wave의 test 소비를 `0`으로 두자는 결론도 B*·resolver·verifier가 움직이는 현 상태와 양립한다.

**생존 조건:** 새 val 조각을 소급적으로 pristine-private라 부르지 않고, test를 RSI reward나 evaluator repair에 한 번도 되먹이지 않아야 한다.

### F-ST3 — DGX의 고유 가치를 처리율보다 메모리·전수 계산에서 찾았다

처리율이 미측정임을 고백하고 preflight를 첫 셀로 둔 점, local 16GB에서 생긴 sampling/sharding 타협을 GB10 128GB에서 직접 진단하려 한 점은 내 라운드 1 안보다 낫다. full-graph 대 sampled 비교는 feasibility가 먼저 증명된다면 높은 정보가치가 있다.

**생존 조건:** 작은 canary의 속도를 최대 그래프 적재 가능성으로 대체하지 말고, 동일 DGX 위에서 sampler만 바꾼 paired estimand를 만들어야 한다. S1-DGX-01과 S1-DGX-02가 지배한다.

### F-ST4 — 계획 변경과 불확실성을 숨기지 않았다

val 분할, R54 DGX 이관, wave 예산, full-graph arm이 재프리레그 대상임을 적었고, DGX 처리율·코퍼스 포맷·권리·verifier 전다양성·AUPRC를 `U`로 남겼다. 모르는 것을 READY로 위장하지 않은 태도는 유지해야 한다.

**생존 조건:** 변경 원장이 실제로 모든 신설 셀과 decision rule을 포함해야 한다. 현재 네 항목만으로는 불완전하다(S0-PREREG-01).

### F-ST5 — RSI를 모델 탐색이 아니라 하네스 탐색으로 구체화했다

inner를 feature/model/threshold, outer를 grammar/search policy/guards/budget allocator로 나눈 것은 AIDE²를 단순 재명명하지 않고 구현 대상으로 번역한 부분이다. CPU 중심 inner loop와 자원 장부도 타당한 출발점이다.

**생존 조건:** outer가 자기 점수를 매기는 evaluator constitution까지 고칠 수 있어서는 안 되며, 전체 탐색비를 finalist 비용으로 숨겨서도 안 된다(S0-RSI-01, S1-BUD-02).

---

## 2. S0 — 발사 차단 티켓

### S0-BUD-01 — DGX 총 envelope가 자체 셀 cap의 합보다 작다

**증거:** `position_fable.md`의 W2 표는 W2-00 `0.5`, W2-03 `6`, W2-04 `3`, W2-05 `6`, W2-06 `7` DGX-day를 허용한다. 산술합은 `0.5+6+3+6+7=22.5 DGX-day`[D]인데 같은 절의 총 envelope는 `21 DGX-day`[P]다.

**공격:** early kill은 가능성이지 예산 보증이 아니다. 모든 팔이 gate를 통과하는 admissible branch가 봉투를 `1.5 DGX-day`[D] 초과한다. filler의 선점 가능성은 GPU-hour를 무료로 만들지 않는다. 따라서 현재 계획은 worst-case에서 실행 불가능하고 “고정 예산”이 아니다.

**필수 수정:** 모든 생존 분기의 cap 합을 기계 검사하고, W2-06을 명시적 residual cap으로 줄이거나 다른 셀 cap을 줄여야 한다. checkpoint·restore·staging 중 DGX가 점유된 시간도 청구한다.

**종결 조건:** `max_branch_sum ≤ sealed_envelope`가 manifest 검사에서 PASS하지 않으면 prereg 자체를 INVALID로 닫고 어떤 DGX 셀도 발사하지 않는다.

### S0-PREREG-01 — 재프리레그 변경 원장이 불완전하고 발사 순서가 모순된다

**증거:** §5는 변경 네 건만 열거하지만 W2-00/01/02/06/08/09는 모두 새 가설·metric·gate·budget을 가진 신설 셀이다. 동시에 W2-00은 “첫 발사”, W2-01/02는 READY라고 쓰고, wave envelope와 val split은 아직 봉인 대상이라고 쓴다.

**공격:** 새 셀은 기존 계획의 단순 실행이 아니다. 특히 W2-00 결과에 따라 나머지 DGX 역할을 바꾸려면, 사전에 outcome→route decision table을 봉인하거나 W2-00을 독립 qualification prereg로 실행한 뒤 본 wave를 새로 봉인해야 한다. 결과를 보고 예산·팔을 정하면 고정비용 비교가 사라진다.

**필수 수정:** parent-prereg hash를 가진 immutable amendment에 모든 신설 셀, feature grammar, split/dedupe hash, metric universe, candidate 수, seed, branch DAG, stop rule, budget vector, method ID, evidence schema를 넣는다. 기존 파일을 덮어쓰지 않는다.

**종결 조건:** score-bearing 결과 timestamp가 지배 prereg hash보다 이르거나, 결과를 본 뒤 후보·band·budget·route를 추가하면 그 cohort 전체를 `EXPLORATORY_ONLY`로 강등하고 B*/formal/test 자격을 박탈한다.

### S0-PREREG-02 — 이미 사용한 val을 나중에 나눠 pristine-private로 만들 수 없다

**증거:** 상대는 `0.705`가 전체 val에서 반경 선택을 거친 값임을 인정한다. 그런데 W2-09에서 같은 val을 `200/200`으로 나누고 B를 준-private 생존면으로 쓰려 한다. 더 직접적으로 W2-02는 “분할 전 착수 시 val 전체 사용”을 허용한다.

**공격:** 과거의 radius·feature·model·하네스 선택에 B family가 이미 기여했다면, 행별 오류를 앞으로 숨겨도 과거 적응은 지워지지 않는다. A/B 차이가 CI 안이라는 결과도 “오염이 작다”는 등가성 증명이 아니라 단지 차이를 검출하지 못했을 수 있다.

**필수 수정:** 전체 현 val을 `LEGACY-SEEN`으로 표기한다. 새 family-hash pane은 W2의 전향적 피드백을 한 번 막는 `prospective adjudication`으로만 부르고, 과거 비오염·독립 일반화 주장을 금지한다. 분할은 어떤 W2 feature/score 계산보다 먼저 봉인한다.

**종결 조건:** 미래 adjudication family의 label, prediction, aggregate, membership이 W2 candidate/harness 동결 전에 노출되면 그 pane의 private/quarantine 주장과 해당 cohort의 confirmatory 주장을 kill한다. 과거 미접촉 접근 원장을 증명하지 못하면 retrospective decontamination 주장은 영구 kill이다.

### S0-PREREG-03 — 같은 val-B를 wave마다 쓰면 outer loop가 B에 적응한다

**증거:** §3.2는 harness 채택에 val-B 비열화 조건을 쓰고, §3.4/3.5는 wave 경계마다 B를 연다. pass/fail 한 비트도 후속 설계에 정보다.

**공격:** 같은 B를 반복 사용하면 B는 지연 공개된 public benchmark가 된다. row-level label을 숨기는 것만으로 적응적 과적합을 막지 못한다.

**필수 수정:** frozen cohort에 adjudication reveal을 한 번만 허용하고 그 pane을 burn/retire한다. 실패 뒤 같은 B를 보고 challenger를 고치지 않는다. 다음 outer 채택에는 사전에 봉인된 비중첩 pane이 필요하며, 없으면 다음 confirmatory cycle은 BLOCKED다.

**종결 조건:** 같은 method/harness lineage의 결정에 두 번째 B-derived verdict가 영향을 주면 B의 private status를 kill하고 test 승격을 막는다.

### S0-RSI-01 — outer가 자기 평가기를 고치면서 그 평가기로 자기 우월성을 판정한다

**증거:** §3.2의 outer 대상에는 guard, 평가 driver, budget 정책이 포함되고 §3.5는 eval repair 뒤 재평가를 허용한다.

**공격:** search policy 개선과 측정자 변경을 한 reward로 접으면 “평가 수리”라는 이름으로 유리한 metric·split·aggregation·inclusion rule을 선택할 수 있다. evaluator defect는 exploitation 대상이 아니듯 RSI credit 대상도 아니다.

**필수 수정:** metric, handle universe, split, inclusion rule, bootstrap unit, guard threshold, budget accounting, test ACL을 immutable `evaluator constitution`으로 outer 밖에 둔다. outer는 repair를 제안만 할 수 있다. 독립 governance가 새 evaluator version을 봉인하고 comparable cohort 전체를 replay하며, evaluator 변경 자체에는 improvement credit을 주지 않는다.

**종결 조건:** 후보 결과를 본 뒤 constitution 항목이 바뀌면 이전/이후 점수 연결과 outer-improvement 주장을 kill한다. cohort 전체 replay가 없으면 repair 후 점수는 INCOMPARABLE이다.

### S0-BUD-02 — SSL/DAPT의 “같은 비용 승리”가 성립하지 않는다

**증거:** W2-06은 pretrained/no-pretrain을 같은 fine-tune budget으로 비교하지만 pretrained arm에만 최대 `7 DGX-day`의 사전학습을 추가한다.

**공격:** 이것은 pretraining의 효과를 측정할 수는 있어도 AIDE²의 같은 총비용 효율 개선을 증명하지 못한다. opportunistic filler라는 운영 이름도 추가 compute를 없애지 않는다.

**필수 수정:** total CPU/RTX/DGX vector를 맞춘 scratch control, 또는 performance-versus-total-compute curve를 둔다. residual filler step 수와 평가 checkpoint도 outcome 전에 봉인한다.

**종결 조건:** 추가 pretraining 비용을 포함한 matched-total-compute 비교에서 이득이 사라지면 RSI 채택 claim을 kill한다. checkpoint는 higher-resource research artifact로만 보존한다.

### S0-HON-01 — 두 개의 핵심 수치가 산출 근거 없이 만들어졌다

**증거:** §1.3의 천장 `0.75±0.03`은 계산·모형·산출 아티팩트가 없고, §4 주장 5의 “val-B가 접지 기능의 `80%`를 제공”도 근거·정의·킬 조건이 없다. `duty cycle ~100%` 역시 측정치가 아니라 목표인데 관측처럼 쓰였다.

**공격:** “예보”라는 표지와 사후 킬 조건은 임의 uncertainty band를 정당화하지 않는다. 특히 `80%`는 무엇의 80%인지 estimand조차 없다. 이는 이번 임무의 no-invented-numbers 계약을 직접 위반한다.

**필수 수정:** 세 숫자를 삭제한다. 천장은 ordinal representation hypothesis로, val pane은 prospective feedback brake로, DGX utilization은 scheduler log에서 산출할 운영 metric으로 바꾼다.

**종결 조건:** 사전 봉인된 산출 방법과 실제 아티팩트가 없으면 위 수치 주장은 RETRACTED다.

---

## 3. S1 — 주요 타당성 티켓

### S1-BUD-01 — 자원 단위와 누락 비용 때문에 동일예산 비교가 재현되지 않는다

**증거:** CPU `d`, CPU `h`, local GPU-h, DGX-day를 혼용한다. graph construction, raster bridge/fusion, staging, evaluation, checkpoint/replay 일부는 cap이 없고, W2-00의 local RTX 비교 cap도 없다. 조건부 A65는 wave cap 밖이다.

**공격:** wall-day와 core-hour, device reservation과 active kernel time을 혼용하면 같은 비용을 재현할 수 없다. 누락된 preprocessing/cache 비용은 복잡한 harness의 brute force를 숨긴다.

**필수 수정:** CPU-core-hour, exclusive RTX-hour, exclusive GB10-hour, private-query count, candidate-launch count를 정의하고 shared cache를 모든 비교 arm에 같은 규칙으로 배분한다. A65는 별도 future prereg로 이동한다.

**종결 조건:** unaccounted resource가 있거나 admissible branch가 envelope를 넘으면 adoption을 INVALID로 한다.

### S1-BUD-02 — finalist 비용만 같고 전체 search 비용은 같지 않다

**증거:** inner loop는 레시피를 계속 만들 수 있지만 후보 수, debug 실패, cache 생성, private verdict 수의 cap이 없다. “CPU의 한계비용 0”이라는 표현은 §3.3에서 CPU-h를 통화로 센다는 사실과도 충돌한다.

**공격:** AIDE²의 비교 단위는 최종 모델 한 번이 아니라 그 모델을 찾은 하네스 전체다. 더 많은 후보를 보고 같은 finalist cost로 이기는 것은 효율 개선이 아니다.

**필수 수정:** 같은 시작 frontier, candidate-generation seed, 총 search envelope, candidate count, private-query cap에서 incumbent/challenger harness를 paired replay한다.

**종결 조건:** challenger가 후보·private query·공유 전처리 중 어느 하나라도 더 쓰고도 equal-budget credit을 받으면 claim을 kill한다.

### S1-BUD-03 — Qwen 여섯 팔의 cap·seed·선택 규칙이 실행 가능하게 닫히지 않았다

**증거:** 원 envelope `0.5–2일×6`은 `3–12 DGX-day` 범위인데 W2-05 cap은 `≤6 DGX-day`다. per-arm allocation, seed, halving rung, tie rule, multiplicity, independent confirmation이 없다.

**공격:** six-arm best-of 선택을 같은 노출 panel에서 평가하면 winner's curse가 생긴다. “최량 팔”은 arm search budget과 확인 평가가 고정되지 않으면 confirmatory 결과가 아니다.

**필수 수정:** 각 팔 cap, seed, public-only halving, tie rule, 최종 primary contrasts를 prereg한다. frozen winner만 prospective pane을 한 번 본다. 기존 checkpoint lineage가 불명확하면 UNSCORABLE로 격리한다.

**종결 조건:** 모든 eligible arm이 cell cap에 들어오지 않거나 winner가 선택과 확인에 같은 exposed panel을 쓰면 best-arm claim을 kill한다.

### S1-DGX-01 — 작은 preflight는 full-graph 적재·학습 가능성을 증명하지 않는다

**증거:** W2-00은 소형 GNN/U-Net을 재지만 §4 주장은 `412,775` segment 그래프의 무샘플링 처리를 128GB가 가능하게 한다고 쓴다. edge 수, feature width, activation, gradient, optimizer, checkpoint memory는 미측정이다.

**공격:** node count와 unified-memory 용량만으로 training fit을 결론 낼 수 없다. CPU offload/oversubscription으로 “적재”는 되더라도 step throughput이 붕괴할 수 있다.

**필수 수정:** 최대 규모 dry-run에서 전체 memory breakdown, completed optimizer step, checkpoint/restore, disk projection을 재고 full arm을 diagnostic으로만 둔다.

**종결 조건:** cap 안에 한 training step과 checkpoint를 완료하지 못하면 full-graph arm만 kill한다. 이를 GNN 전체 실패나 성공으로 확대하지 않는다.

### S1-DGX-02 — sampled/local 대 full/DGX는 sampler의 인과효과를 식별하지 못한다

**증거:** 제안 비교는 sampler, hardware, batch, optimizer update 수, wall-clock을 동시에 바꿀 수 있다.

**공격:** 이 상태의 차이는 “sampling bias”로 귀속할 수 없다.

**필수 수정:** 같은 DGX, 같은 architecture·seed·data exposure·update rule에서 sampled/full만 바꾼 비교를 하고, 동일 update와 동일 wall-clock estimand를 별도 보고한다.

**종결 조건:** sampler 외 요인이 함께 바뀌면 sampling-bias claim을 kill하고 단순 system comparison으로 강등한다.

### S1-DGX-03 — filler와 `~100%` utilization은 공짜가 아니다

**증거:** W2-06은 P0를 “한 시간도” 늦추지 않는다고 하지만 preemption latency, checkpoint cadence, loader teardown, restore loss가 미측정이다.

**공격:** 단일 GPU에서 filler는 스케줄링 overhead와 가변 training steps를 만든다. GPU utilization과 useful scientific compute도 다르다.

**필수 수정:** READY 구간의 useful-compute busy fraction, P0 dispatch latency, lost/replayed steps, checkpoint overhead를 scheduler xlsx에 기록한다. preemption은 checkpoint boundary에서만 하고 filler 총 cap은 고정한다.

**종결 조건:** filler가 no-filler schedule보다 P0 시작을 늦추거나 비교 arm의 compute를 불균등하게 만들면 filler policy와 utilization claim을 kill한다.

### S1-EVAL-01 — metric과 handle universe가 트랙 사이에서 정합하지 않는다

**증거:** W2-02는 F1, formal GNN은 AUPRC, raster는 IoU와 AUPRC, Qwen R54는 `F1≥0.517 OR` synthetic/meta 우세, outer는 AUPRC `+0.005`를 쓴다. 혼성 panel의 가중·AND 규칙도 없다.

**공격:** endpoint를 결과에 따라 고르면 band 이동이다. pixel 승리와 line-semantic 승리, F1 operating point와 ranking 성능을 같은 scoreboard에 놓을 수 없다.

**필수 수정:** 각 cell의 native diagnostic과 최종 공통 handle-universe AUPRC를 분리하고, primary endpoint·threshold-selection data·mixed-panel AND/lexicographic rule을 봉인한다.

**종결 조건:** metric 간 결론이 갈릴 때 유리한 endpoint를 택하면 INVALID; 사전 truth table이 없으면 INCONCLUSIVE로 닫는다.

### S1-EVAL-02 — 여러 gate의 회색구간과 논리식이 미봉인이다

**증거:** GNN recall `0.98/0.995` 중 kill은 `<0.98`만 정의하고, raster IoU `0.60/0.70` 중 kill은 `<0.60`만 정의한다. RL gap은 한 절에서 단일 `≥0.01`, 다른 절에서 beam과 oracle의 AND다. disagreement 가설은 `≥3×`, kill은 `<2×`라 `2–3×`가 비어 있다.

**공격:** 빈 구간은 결과를 본 뒤 PASS/FAIL 의미를 이동시킬 공간이다.

**필수 수정:** 모든 interval과 conjunction에 PASS/FAIL/BLOCKED/INVALID/INCONCLUSIVE를 배정한 truth table을 봉인한다.

**종결 조건:** evaluator가 output 뒤 band·endpoint·AND/OR를 선택하면 run을 무효화한다.

### S1-RSI-02 — A63은 verifier reward의 탐색 갭이지 벽 의미의 RL 상한이 아니다

**증거:** W2-07은 gen2 결정론 candidate universe에서 beam−greedy와 oracle gap으로 full RL을 살리거나 죽인다. verifier는 LINE-only 한계가 있고 의미 label oracle이 아니다.

**공격:** 작은 gap은 “현재 candidate generator와 현재 verifier reward에서” 정책 headroom이 작다는 뜻뿐이다. candidate universe가 약하거나 reward가 의미와 어긋나면 RL 일반 가능성을 판정하지 못한다. 큰 gap도 RL이 semantic metric을 올릴 증거가 아니다.

**필수 수정:** state/action/horizon/reward, candidate coverage, real-data diagnostic, hidden semantic evaluator를 봉인한다. verifier 전다양성 PASS와 real/synthetic 동방향 없이 RL은 BLOCKED다.

**종결 조건:** 사전등록된 upper CI가 margin 아래이고 real diagnostic도 같은 방향일 때만 “현재 action-space RL”을 kill한다. 그 밖에는 RL 일반론이 아니라 현재 probe만 FAIL/INCONCLUSIVE다.

### S1-RSI-03 — 통계층이 누출 탐지기로 교정되지 않았다

**증거:** P99는 후보 수가 작으면 불안정하고, AUC `>0.995`/F1 `>0.95` 절대선은 미측정 천장에 의존한다.

**공격:** 통계적 극단성은 audit trigger일 뿐 leakage 판정이 아니다. 중간 크기의 family shortcut은 통과하고 진짜 돌파는 격리할 수 있다.

**필수 수정:** 의도적으로 삽입한 ID leak, family duplicate, reward exploit challenge node에 대한 탐지 민감도를 prereg하고, 모든 prospective winner에 invariant audit를 적용한다.

**종결 조건:** challenge node를 격리하지 못하면 “3층 방어 가동” claim을 kill한다. 통계층 단독으로 PASS를 내리는 것도 금지한다.

### S1-DATA-01 — 기존 Qwen checkpoint와 pretrain corpus의 lineage가 평가 자격보다 뒤에 있다

**증거:** checkpoint와 corpus의 실존은 보고됐지만 CubiCasa/FPC val·mask·근접중복을 봤는지, 각 license/provenance가 허용되는지는 미확인이다. contamination은 사후 검출 시 retract한다고만 썼다.

**공격:** holdout 유입은 학습 뒤 찾을 문제가 아니라 학습 전 차단할 문제다. lineage unknown checkpoint의 우세는 transfer가 아니라 기억일 수 있다.

**필수 수정:** checkpoint별 training manifest와 hash/near-dedupe, corpus license tag, family exclusion을 점수 계산 전에 완료한다.

**종결 조건:** lineage나 rights가 unknown이면 성능 FAIL이 아니라 `QUARANTINED/UNSCORABLE`; production 비교와 RL 근거로 쓰지 않는다.

### S1-EVAL-03 — ERROR-AUTOPSY가 독립 judge 없이 라벨 결함률을 예산 gate로 쓴다

**증거:** W2-01의 시각 확정은 grok 유보로 DEFERRED인데 자동 “라벨 의심률”이 `30%` threshold로 후속 투자 방향을 바꾼다.

**공격:** 자동 anomaly flag는 label defect truth가 아니다. 같은 기하 규칙으로 라벨을 의심하면 모델의 약점을 라벨 오류로 재명명할 수 있다.

**필수 수정:** grok 또는 허용된 독립 adjudicator가 자격을 얻기 전에는 `flag rate`로만 보고하고, 구조 strata 탐색에는 쓰되 label-noise 인과결론과 GPU budget routing에는 쓰지 않는다.

**종결 조건:** independent qualification이 없으면 label-defect claim과 그 분기 권한만 kill한다. 오류 해부 전체는 유지한다.

---

## 4. S2 — 범위·운영 정리 티켓

### S2-CLAIM-01 — “2-hop이 남은 이득의 절반 이상 회수”는 분모가 없다

현재 가족의 진짜 천장도 GNN의 달성치도 없으므로 “남은 이득”을 계산할 수 없다. W2-02가 이길 수 있다는 ordinal claim으로 낮추고, 동일 AUPRC·동일 handle universe의 paired gate로만 판정해야 한다.

**종결 조건:** 분모와 counterfactual ceiling이 측정되기 전에는 “절반”을 RETRACT한다.

### S2-CLAIM-02 — R-sweep는 장거리 신호 부재와 집계 파괴를 구분하지 못한다

`20>40>80 px`는 현재 집계가 넓은 반경에서 나빠졌다는 증거다. 장거리 문맥이 없다는 증거도, GNN이 필요하다는 증거도 아니다.

**종결 조건:** identity-preserving multi-hop 대 radius-only 집계를 같은 예산에서 비교하기 전에는 원인을 특정하지 않는다.

### S2-TEST-01 — test는 “private panel 중 하나”가 아니라 RSI 밖의 비가역 자원이다

test 결과는 어떤 inner/outer node에도 reward로 돌아가면 안 된다. defect가 발견되어도 같은 method ID 재시도나 band 이동은 금지하고, 새 method는 별도 governance 대상이어야 한다.

**종결 조건:** test-derived 수정이 동일 lineage에 들어가면 그 method의 confirmatory claim을 kill한다.

### S2-OPS-01 — BLOCKED, FAIL, INCONCLUSIVE를 분리해야 한다

rights 미확인, verifier 미자격, lineage unknown은 성능 실패가 아니다. 반대로 예산 안에서 gate 미달은 BLOCKED로 미뤄서도 안 된다.

**종결 조건:** prereg truth table에 각 선행조건과 회색구간의 상태가 없으면 해당 셀을 launch하지 않는다.

---

## 5. 최종 판결

fable의 과학적 우선순위는 대체로 강하다. 내가 그대로 흡수할 것은 **오류 해부 우선, 2-hop Occam gate, DGX qualification, full-vs-sampled diagnostic, RL 무학습 선행, uncertainty ledger, 이번 wave test 0**이다.

그러나 현재 문서 그대로는 launch 불가다. 가장 치명적인 네 이유는 (1) `22.5>21`인 DGX 예산, (2) 전체 val 사용을 허용한 뒤 만드는 소급적 val-B, (3) outer가 자기 evaluator constitution을 변경하는 구조, (4) verifier reward gap을 semantic RL 상한으로 오인한 것이다. 이 네 S0/S1 핵심 티켓이 닫히기 전에는 “RSI가 같은 비용에서 일반화 개선을 선택한다”는 메타주장을 채택하지 않는다.

ROUND2_COMPLETE: sol
