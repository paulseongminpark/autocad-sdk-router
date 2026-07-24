# E2 다음 웨이브 수정 설계 — sol, 라운드 2

## 0. 수정 판정과 정직성 계약

상대 페이퍼를 읽고 내 라운드 1 설계의 다섯 부분을 철회하거나 축소한다.

1. 이미 전체 val에서 `0.705`와 반경을 선택한 뒤 그 내부를 `val-private`라고 부른 것은 틀렸다. 지금 만드는 격리면은 **W2의 전향적 피드백을 한 번 막는 pane**일 뿐, 과거에도 untouched였던 private set이 아니다.
2. D1–D5 `14 GB10-day`만 적고 trainer 구현·DGX preflight·checkpoint·CPU staging·전체 search 비용을 닫지 않은 것은 예산 설계가 아니었다.
3. private canary로 continue/kill한 뒤 같은 private에서 최종 채택하는 X7은 private를 두 번 쓴다. canary는 public에서만 하고 adjudication은 frozen cohort당 한 번만 해야 한다.
4. outer가 split·metric·bootstrap·guard를 고치면서 같은 evaluator로 자기 우월성을 판정하게 한 것은 reward hacking 표면이다. evaluator constitution은 outer 밖으로 뺀다.
5. randomized logging과 positivity를 증명하지 않은 X9의 IPS/DR 주장은 식별되지 않는다. 이번 wave의 RL 셀은 exact/enumerated diagnostic까지만 하고 학습은 별도 future prereg로 넘긴다.

상대에게서 흡수하는 것은 오류 해부 우선, 2-hop Occam gate, DGX qualification, full-vs-sampled diagnostic, residual filler, RL 무학습 진단, uncertainty ledger, 이번 wave test 소비 `0`이다. 흡수하지 않는 것은 근거 없는 `0.75±0.03` 천장, val-B의 “접지 기능 80%”, DGX `~100%` duty 보장, 계측 전 `≥2×` 처리율/full-graph 가능성 주장이다.

### 표기 규약

- `[M:T]`: `task.md`의 실측 프로그램 사실.
- `[M:S]`, `[M:F]`: 각 포지션이 산출 아티팩트와 함께 보고한 측정값. 이번 라운드에서 외부 아티팩트를 재열람하지 않았으므로 원천 독립 재검증은 아니다.
- `[P]`: 새 amendment에 봉인해야 하는 설계값. 관측값이나 예측치가 아니다.
- `[D]`: `[M]` 또는 `[P]`의 명시적 산술.
- `[U]`: 세 허용 문서로는 모르는 값. `U`가 지배하면 FAIL이 아니라 BLOCKED 또는 INCONCLUSIVE다.

모든 과학 주장은 아래에 kill 조건을 둔다. 데이터·권리·코드·계측기 선행조건은 `BLOCK`, 계약 위반은 `INVALID`, 예산 안에서 가설이 지면 `KILL`, 판별력이 부족한 회색구간은 `INCONCLUSIVE`로 닫는다. kill 없는 수치 예보는 쓰지 않는다.

---

## 1. 결과 재해석과 현재 천장

### 1.1 `0.236`: 절대 두께 규칙은 현 표현에서 의미 prior가 아니었다

val `F1=0.236`, `P=0.134`가 벽 기저율 `0.118`에 가깝고 축척 변화에도 판별력이 생기지 않았다.[M:T] 이 결과가 지지하는 좁은 명제는 “현재 CubiCasa SEG-IR에서 절대 두께대역+평행 규칙만으로 벽 의미를 분리하지 못했다”이다. 물리 두께가 모든 CAD 분포에서 무의미하다는 보편 명제는 아니다.

**킬:** 동일 split·동일 resolver replay에서 수치가 재현되지 않거나 label/layer/handle 누출이 발견되면 이 해석을 철회한다.

### 1.2 `0.517`: 국소 특징에 ranking signal은 있었지만 비선형 조합이 필요했다

지역 `6`특징의 GBDT가 `F1=0.517`, `AUC=0.9215`에 도달했다.[M:T] 내 라운드 1이 보고한 같은 행 universe의 선형 모델 실패가 맞다면, 신호는 단일 특징이나 고정 가중합보다 조건부 상호작용에 산다.[M:S]

**킬:** matched replay에서 비선형 모델의 lift가 사라지거나 shuffle/name/family leakage가 발견되면 “상호작용 신호” 주장을 kill한다.

### 1.3 `0.705`: 관계 집계의 유용성은 증명했지만 GNN의 필요성은 증명하지 않았다

문맥 `6`특징 추가 뒤 `F1=0.705`, `AUC=0.9671`, `R=0.617`, `P=0.824`가 됐고 정션 차수·평행 갭이 중요도 상위였다.[M:T] 이것은 fixed relational aggregates가 유용하다는 직접 증거다. message passing, SSL, full graph가 필요하거나 우월하다는 증거는 아직 `0`건이다.

**킬:** prospective family-disjoint development replay에서 context ablation의 paired lift CI 하한이 `0` 이하이거나 family/template guard가 실패하면 H3의 현재 증거를 약화 또는 철회한다.

### 1.4 내 “다음 병목은 recall” 표현은 우선순위 가설로 낮춘다

내 포지션은 `FN=15,624`, `FP=5,363`을 근거로 recall을 다음 병목이라고 단정했다.[M:S] 이 수는 recall 회수 실험을 먼저 볼 이유는 주지만 오류 비용, 도면별 집중, 현재 모델의 FP family, label ambiguity를 판정하지 않는다. fable의 ERROR-AUTOPSY가 먼저다.

**H-E1:** 잔여 오류는 partner-missing, 짧은 junction fragment, annotation-dense motif, drawing-style tail 같은 사전등록 구조군에 과집중한다.

**킬:** 모든 사전등록 구조군의 error lift가 `[P] 1.5×` 미만이면 “구조화된 관계 헤드룸이 주 병목” 주장을 kill한다. 허용된 독립 이미지 adjudicator가 없을 때 label-defect 비율은 산출하지 않는다.

### 1.5 수치 천장은 모른다

고정 스칼라 집계가 partner identity, typed configuration, multi-hop topology를 소실하는 것은 표현 한계다. 그러나 남은 오류 중 얼마가 그 정보에 의존하는지는 미측정이다. 따라서 현 가족의 F1 천장을 숫자로 예보하지 않는다.

남은 구조 가설은 다음 네 개로 좁힌다.

- **H-R1:** identity-preserving 2-hop 특징이 현재 집계가 잃은 일부 관계를 회수한다. **킬:** G3의 paired AUPRC gate 미달.
- **H-R2:** typed message passing이 2-hop classical 뒤에도 남는 configuration을 회수한다. **킬:** G5 formal 또는 NoMessage/edge-shuffle gate 미달.
- **H-R3:** raster/VLM은 vector가 모호한 subset에서만 상보적이다. **킬:** mask/output shuffle과 구분되지 않거나 common handle AUPRC gate 미달.
- **H-R4:** current lift 일부는 family/style shortcut이다. **킬:** prospective adjudication에서 paired lift CI 하한이 `0` 이하.

2-hop, GNN, raster/Qwen이 모두 같은 evaluator와 예산에서 죽으면 “소실 관계 정보가 실질 headroom”이라는 서사도 죽는다. 낮은 ceiling의 숫자는 그 뒤에도 발명하지 않는다.

---

## 2. Phase 0 — 어떤 score-bearing 셀보다 먼저 봉인할 것

### 2.1 새 amendment와 실행 금지선

기존 prereg를 덮어쓰지 않는다. 순환 봉인을 막기 위해 먼저 `qualification_protocol_r2`[P]에 **비라벨 inventory만 허용하는 G0-A**, 그 cap, 출력 schema, 그리고 qualification outcome→BLOCK/route decision table을 봉인한다. G0-A는 model score·feature 비교·threshold 선택을 금지하고 exact manifest와 기존 비용 원장만 만든다. 그 산출을 입력으로 parent hash를 가진 `prereg_r2_v1`[P]을 봉인한 뒤 G0-B DGX qualification과 나머지를 실행한다. G0 결과는 cap을 늘릴 수 없고, device factor 고정·full-graph arm kill·DGX BLOCK만 일으킬 수 있다.

`prereg_r2_v1`은 다음을 어떤 score-bearing 결과보다 먼저 봉인한다.

1. data provenance, rights, family/near-dedupe manifest와 split hash;
2. current `0.705`를 전체 val에 적응한 `LEGACY-DEVELOPMENT`로 표시하는 주석;
3. common handle universe, AUPRC primary, F1/P/R/calibration diagnostic 계약;
4. B*의 prospectively enumerated 후보 집합;
5. G0–G9의 arm, seed, candidate 수, budget vector, branch DAG, early-stop, gray-zone truth table;
6. method ID를 model/data/split/harness/resolver/calibration/evaluator hash의 튜플로 정의하는 규칙;
7. evaluator constitution과 evidence xlsx/JSON schema;
8. adjudication query `1회`[P], test contact `0`[P];
9. 기존 in-flight 셀의 실제 누적비용과 남은 sealed commitment 원장.

**INVALID 조건:** score-bearing W2 결과 timestamp가 이 hash보다 이르거나 outcome 뒤 arm·band·metric·budget·route를 추가하면 그 cohort는 formal/B*/test 자격을 잃는다. 기존 in-flight 산출은 가설 생성과 readiness 증거로 쓸 수 있지만 confirmatory 비교에는 post-seal matched replay가 필요하다.

### 2.2 val은 세 상태로 구분한다

- **LEGACY-SEEN:** 지금까지 전체 val. `0.705`와 반경 선택에 이미 사용됐으므로 pristine private가 아니다.
- **DEV:** W2 inner가 보는 prospective family-disjoint development pane.
- **ADJ:** deterministic family-hash로 만든 prospective adjudication pane. W2 lineage 전체가 동결될 때까지 row, label, prediction, aggregate를 evaluator service 밖으로 내보내지 않는다.

fable이 보고한 `400개 도면`과 `200/200`은 이번 라운드에서 원천을 재검하지 않았으므로 현재 cardinality는 `[U]`다. 비율·개수는 non-label census 후 amendment에 봉인한다. 중요한 점은 새 분할이 과거의 적응을 지우지 않는다는 것이다. ADJ는 W2의 추가 피드백만 한 번 차단하며 최종 일반화 증명이 아니다.

**KILL/INVALID:** ADJ 결과를 본 뒤 feature, threshold, model, harness, resolver를 고치면 pane은 consumed/public로 재분류되고 같은 lineage의 재시험을 금지한다. 같은 pane을 두 번째 outer decision에 쓰면 confirmatory status를 kill한다.

### 2.3 evaluator constitution은 outer가 수정할 수 없다

다음은 wave 안에서 immutable이다: split, primary metric, handle inclusion, threshold-selection data, bootstrap unit, guards, budget accounting, method ID, ADJ/test ACL. outer는 repair proposal만 제출한다.

defect가 발견되면 competitive tree를 멈추고 독립 governance가 새 evaluator version을 봉인한다. comparable cohort 전체를 새 version으로 replay하며 evaluator 변경 자체에는 improvement credit을 주지 않는다. 기존 행은 삭제하지 않고 `SUPERSEDED_EVAL_DEFECT`로 남긴다.

**KILL:** 후보 결과를 본 뒤 constitution이 바뀌면 이전/이후 점수 연결과 outer-improvement 주장을 kill한다.

### 2.4 test는 RSI 밖에 둔다

이번 wave test contact는 `[P] 0`이다. test는 private panel 중 하나가 아니라 방법당 단발인 비가역 자원이다.[M:T] 어떤 test 결과도 inner/outer reward, band 이동, same-method repair에 쓰지 않는다.

**재심 조건:** 독립 방법 가족이 각자의 모든 pre-test gate를 통과하고 최종 method ID가 동결되면 다음 wave에서 test 개방을 별도 심사한다. 이번 wave 도중 조건이 충족돼도 W2의 test contact는 `0`을 유지한다.

---

## 3. 고정 예산 장부

### 3.1 단위

- `CPU-h`: 예약 logical core 수 × elapsed hour. multi-core와 실패/debug run도 합산한다.[P]
- `RTX-h`, `GB10-h`: 해당 장치를 배타 점유한 elapsed hour. loader stall, checkpoint, restore, preemption도 포함한다.[P]
- search 비용에는 candidate 생성, cache, 실패 leaf, evaluation, private query가 포함된다.
- CPU/RTX/GB10 사이 환율은 만들지 않는다. `same-budget`은 **사전에 배정한 총 cap vector와 search/query cap이 동일**하다는 뜻이다. 싼 incumbent가 미사용 GPU 시간을 억지로 태우지는 않으며 그 잔여분은 재배분하지 않는다. 실제 사용 vector는 별도로 보고해 Pareto 효율을 판정한다.

기존 in-flight 작업의 과거 사용량은 세 문서에서 `[U]`다. G0가 그 원장을 복구하기 전에는 프로그램 전체 누적비용을 주장하지 않는다. 아래 표는 **새 seal 이후의 incremental cap**이다.[P]

기존 in-flight 중 verifier, PU, graph builder, B*는 각각 G1/G4/G5/G3의 post-seal replay로 흡수한다. C1 scale counter-theory처럼 아래 G0–G9에 흡수되지 않은 legacy cell은 G0 원장이 남은 cap을 확정할 때까지 새 compute를 `PAUSED`한다. 남은 commitment가 `0`이 아니면 그 정확한 resource vector를 amendment total에 더하거나 legacy cell을 닫기 전에는 새 wave의 “총 고정예산”을 선언하지 않는다. 과거 sunk compute는 보존하지만 same-budget 승리의 분자로 쓰지 않는다.

| 셀 | CPU-h cap | RTX-h cap | GB10-h cap | ADJ/test contacts |
|---|---:|---:|---:|---:|
| G0 ledger+DGX qualification | 36 | 12 | 12 | 0/0 |
| G1 verifier soundness | 24 | 0 | 0 | 0/0 |
| G2 error autopsy | 8 | 0 | 0 | 0/0 |
| G3 2-hop classical/B* | 48 | 0 | 0 | cohort에 포함/0 |
| G4 PU+disagreement | 72 | 0 | 0 | cohort에 포함/0 |
| G5 typed GNN | 24 | 24 | 144 | cohort에 포함/0 |
| G6 raster+bridge | 16 | 0 | 72 | cohort에 포함/0 |
| G7 Qwen matched arms | 16 | 0 | 72 | cohort에 포함/0 |
| G8 single-target DAPT | 24 | 0 | 48 | cohort에 포함/0 |
| G9 RL diagnostic | 72 | 0 | 0 | cohort에 포함/0 |
| **incremental 합** | **340** | **36** | **348** | **ADJ reveal 1 / test 0** |

`340 CPU-h`, `36 RTX-h`, `348 GB10-h = 14.5 GB10-day`는 관측 소요가 아니라 위 cap의 합이다.[D] 모든 팔이 생존해도 이 합을 넘지 않는다. fable의 `22.5` 대 `21 DGX-day` 모순은 반복하지 않는다.

cell 결과의 상태를 세 층으로 분리한다.

- `CELL_PASS`: 그 cell의 고정 cap 안에서 mechanism 가설이 이겼다는 과학적 판정. CPU B*와 GPU challenger의 actual cost가 다르면 이것만으로 production/RSI 교체를 뜻하지 않는다.
- `RSI_ADOPT`: incumbent/challenger harness가 같은 **ex-ante 전체 cap vector**, starting frontier, 후보·query 수를 받고 §6.2의 DEV+ADJ AND gate를 통과한 경우.
- `EFFICIENCY_PASS`: 위에 더해 challenger의 actual resource vector가 incumbent를 Pareto-dominate하거나 사전 봉인된 performance-versus-total-compute curve에서 우세한 경우. 자원 환산으로 사후 정당화하지 않는다.

### 3.2 예산 kill 규칙

1. cell이 cap 안에 완료되지 않으면 cap을 늘리지 않고 `BUDGET_KILL` 또는 `INCONCLUSIVE`로 닫는다.
2. early kill의 잔여분은 다음 READY 셀을 일찍 시작하는 데만 쓰며 다른 셀 cap을 늘리지 않는다.
3. shared cache는 incumbent/challenger에 같은 charge rule로 배분한다. lineage 비용이 unknown인 기존 checkpoint는 same-total-compute 승리를 주장할 수 없다.
4. outer harness 비교는 finalist 한 번이 아니라 같은 starting frontier, candidate count, generation seed, **ex-ante 총 cap vector**, ADJ-query count로 replay한다. actual vector가 더 큰 승자는 `RSI_ADOPT`일 수 있어도 별도 Pareto 증거 없이는 `EFFICIENCY_PASS`가 아니다.
5. implementation, rights, lineage, disk projection이 미완이면 예산 FAIL이 아니라 BLOCKED다. READY가 아닌 job으로 DGX를 바쁘게 만들지 않는다.

**전체 예산 claim의 킬:** machine-check한 admissible branch가 표의 합을 넘거나 uncharged compute가 발견되면 fixed-budget PASS를 철회한다.

---

## 4. 다음 wave 실험 10개

### G0 — readiness ledger와 DGX qualification

- **가설:** G0-A의 비라벨 inventory 뒤 봉인된 G0-B에서 현재 코드·데이터·컨테이너로 최소 재현 run, checkpoint/restore, representative throughput, 최대 규모 memory dry-run을 cap 안에 측정할 수 있다. “DGX가 빠르다”나 “full graph가 들어간다”는 사전 결론은 없다.
- **데이터:** score 선택에 쓰지 않는 fixed small GNN/U-Net canary, 최대 graph의 shape/allocation-only estimate, 그리고 **full-training 자격을 주장하려면** 같은 최대 규모에서 실제 forward/backward/optimizer step과 training-state checkpoint/restore를 수행하는 arm, 고정 hash input.[P] allocation-only 결과는 적재 추정일 뿐 training-fit PASS를 낼 수 없다.
- **지표:** launch command 존재, selftest, data/config/image hash, rows/s·samples/s, peak host/unified memory, completed step, checkpoint/restore latency, disk projection, local↔DGX numerical drift.
- **PASS/KILL:** environment/hash/restart가 실패하면 모든 DGX training은 BLOCKED. 최대 규모의 optimizer step+checkpoint/restore를 완료하지 못하면 allocation estimate와 무관하게 full-graph arm만 KILL. device가 ranking을 바꾸면 결과를 pool하지 않고 device를 factor로 고정한다.
- **예산·배정:** G0-A inventory/ledger `[P]12 CPU-h`, G0-B system/DGX qualification `[P]12 CPU-h+12 RTX-h+12 GB10-h`, G0-C planted-leak guard qualification `[P]12 CPU-h`; 합계 local `36 CPU-h + 12 RTX-h`, DGX `12 GB10-h`.[D/P] G0-C는 ID leak, family duplicate, verifier exploit challenge node의 생성·평가·clean replay를 모두 이 cap에 청구한다. 이 qualification은 총 `348 GB10-h` 안에 포함된다.

### G1 — verifier full-diversity soundness

- **가설:** LINE-only 자격이 `13` entity type, `8` hard-negative class, hidden mutation family, zero/all sentinel, label-poison twin에서도 유지된다.[M:T]
- **데이터:** gen2 v2의 전다양성 eligible pack, reward-visible family와 분리한 hidden mutation family, zero/all sentinel, label-poisoned twin. exact family counts는 G0-A inventory가 산출하고 G1 전에 seal한다.
- **지표:** family별 FAR/FRR, exact-binomial upper bound, name-blind delta, sentinel, reward-visible/hidden family 교집합, byte/hash replay.
- **sample-size seal:** 각 독립 gate family의 applicable positive/negative **고정 `n`과 같은 값의 hard max `n`**을 G0-A 뒤, 어떤 G1 verdict도 보기 전에 봉인한다. failure가 `0`일 때 `[P]95%` one-sided exact bound로 FAR `≤0.01`을 주장하려면 negative `n≥299`, FRR `≤0.05`를 주장하려면 positive `n≥59`가 필요하다.[D: `1-0.05^(1/n)≤threshold`] 실제 failure 수가 생겨도 `n`을 늘리거나 다시 봉인하지 않고 그 고정 표본의 exact bound로 PASS/KILL한다. family pooling으로 부족분을 숨기지 않는다.
- **PASS:** 각 family에서 point estimate와 `[P]95%` one-sided upper bound가 모두 `FAR≤0.01`, `FRR≤0.05`를 만족하고 모든 hard guard가 PASS.[P]
- **KILL/INCONCLUSIVE/INVALID:** 충분한 `n`에서 한 family라도 gate 미달이면 verifier-reward GRPO와 RL을 KILL. cap 안에 prereg `n`을 못 채우면 verifier 자격은 INCONCLUSIVE이고 reward arm은 BLOCK. label 변화가 verdict를 바꾸거나 hidden ID가 학습 log에 나타나면 run INVALID.
- **예산·배정:** seeds `{0,1,2}` 각각 `[P] 8 CPU-h`, local CPU 합계 `24 h`; DGX `0`.[P]

### G2 — `0.705` ERROR-AUTOPSY

- **가설:** FN/FP가 partner-missing, short-fragment, annotation-density, style-tail strata 중 적어도 하나에 `[P] 1.5×` 이상 과집중한다.
- **데이터:** frozen incumbent의 DEV prediction 전량과 SEG-IR vector geometry. 이미지 확정은 grok 유보가 풀릴 때까지 DEFERRED.[M:T]
- **지표:** stratum별 error lift와 family-bootstrap CI, drawing-macro tail, partner-NaN FN, FP/FN absolute share. 자동 label anomaly는 `flag`로만 기록한다.
- **PASS/KILL/gray:** 적어도 한 prereg stratum의 lift CI lower가 `≥[P]1.5×`이면 structured-concentration PASS. 모든 stratum의 point lift가 `<[P]1.5×`이면 주장을 KILL하고 G6 raster complement를 G5 GNN보다 먼저 해석한다. 그 밖에는 INCONCLUSIVE이며 후속 GPU cell을 이 결과 하나로 재배정하지 않는다. 독립 judge 없이 label-defect 비율을 주장하면 해당 결론 INVALID.
- **예산·배정:** local CPU `8 h`; DGX `0`.[P]

### G3 — prospectively enumerated 2-hop classical + B* freeze

- **가설:** partner identity, reciprocity, junction chain, collinear run, opening-adjacency, component motif를 담은 최대 `[P] 3개` mechanistic recipe bundle 중 하나가 current B*를 같은 evaluator에서 이긴다. feature 정의는 결과 전에 완전히 열거한다.
- **데이터:** DEV train/val family split; test·ADJ·FPC mask는 닫는다.
- **지표:** common-handle AUPRC primary, F1/P/R diagnostic, family-paired CI, shuffle, name-blind, runtime/RSS, total-search cost.
- **PASS:** `ΔAUPRC≥[P]+0.01`이고 paired CI lower `>0`, guards PASS.
- **KILL:** gate 미달이면 2-hop branch를 KILL. `ΔAUPRC≥[P]+0.10`이면 production GNN을 Occam-KILL하되 G5의 diagnostic은 관계가설 판정용으로만 남긴다.
- **INVALID:** 결과 뒤 recipe를 추가하거나 ADJ에서 threshold/feature를 고르면 INVALID.
- **예산·배정:** incumbent replay와 최대 세 challenger에 각각 동일한 `[P] 12 CPU-h` cap을 주어 local CPU 총 `48 h`; DGX `0`.[P] 한 recipe가 조기 종료해도 그 잔여분을 다른 recipe에 더하지 않는다.

### G4 — PU ladder + conditional disagreement miner

- **가설 A:** label-blind high-precision anchors, correlation-aware LF, PU risk가 P/N-only baseline보다 grammar coverage와 AUPRC를 개선한다.
- **데이터 A:** gen2 exact truth는 anchor audit에만 사용하고, CubiCasa train label은 PU trainer와 분리한 audit/evaluation namespace에 둔다. DEV로 model selection하며 silver·ADJ·test는 닫는다. miner는 G3/G6/G7의 frozen DEV outputs만 쓴다.
- **지표 A/B:** anchor positive/negative precision, grammar support, LF conflict/dependency, common-handle AUPRC와 family CI, class-prior sensitivity, seed별 sign; miner error-yield ratio와 stratum composition.
- **seal A:** 지원 grammar의 완전 열거, class-prior interval의 양 끝, LF dependency 처리, seeds `{7,17,29,43,71}`를 outcome 전에 고정한다.[P] 하나라도 미봉인이면 G4-A는 BLOCKED.
- **PASS A:** positive anchor precision `≥[P]0.98`, negative precision `≥[P]0.995`, 열거 grammar coverage 충족, aggregate `ΔAUPRC≥[P]+0.01`과 paired CI lower `>0`, sealed prior interval 전역에서 결론 유지, seeds 중 적어도 `[P]3/5`가 P/N-only보다 우세.[P]
- **KILL/gray A:** precision 또는 grammar coverage 실패, prior interval에서 sign reversal, 또는 seeds 중 적어도 `3/5`가 P/N-only 이하이면 PU branch KILL. 그 밖에 aggregate delta가 `+0.01` 미만이거나 CI가 `0`을 포함하면 INCONCLUSIVE이며 채택하지 않는다.
- **가설 B:** G3/G6/G7의 frozen axis가 모두 존재할 때 disagreement sample의 error yield가 random보다 높다.
- **PASS/KILL B:** yield `≥[P]3×` PASS, `<[P]2×` KILL, 그 사이는 INCONCLUSIVE. miner 결과는 truth가 아니라 audit queue다.
- **예산·배정:** PU `[P] 48 CPU-h`, conditional miner `[P] 24 CPU-h`, 합계 local CPU `72 h`; DGX `0`.[P] 선행 axis가 없으면 miner 몫은 미사용으로 남기며 PU로 이관하지 않는다.

### G5 — typed GNN screen → DGX formal

- **가설:** 정확한 typed adjacency의 multi-hop message passing과 train-family SSL이 frozen B*가 잃은 configuration을 회수한다.
- **데이터:** gen2 exact node/pair truth와 CubiCasa DEV의 common-handle universe. 이 cell의 formal primary는 **CubiCasa prospective family-holdout common-handle AUPRC**다.[P] FPC projection은 G6 rights/bridge와 섞지 않으며, ADJ/test geometry와 silver는 pretraining에서도 금지한다.
- **screen truth table:** relation recall `≥[P]0.98`, local seed `17`, NoMessage·edge-type-shuffle 각각에 대한 DEV `ΔAUPRC` CI lower `>0`, 구현 selftest PASS를 모두 만족하면 PASS. selftest/loader/required-data가 실행 전 미완이면 BLOCK; cap을 쓴 뒤 recall 또는 ablation gate가 실패하면 GNN screen KILL; label/name/family guard 실패는 INVALID.
- **formal PASS:** task가 준 seeds `{17,29,43}`와 `B*+[P]0.05 AUPRC` band를 유지하고, 내 라운드 1의 추가 제안 gate인 lift CI lower `>0`, S-node `F1≥[P]0.92`, S-pair `F1≥[P]0.80`, style-OOD drop `≤[P]0.10`, `REL≤[P]0.03`, `RES≥[P]0.03`를 모두 요구한다.[M:T/P:S] 이 판정은 `CELL_PASS`이며 §6.2 없이는 자동 `RSI_ADOPT`가 아니다.
- **full-vs-sampled diagnostic:** 같은 DGX·architecture·seed·data exposure/update에서 sampler만 바꾼다. 동일-update와 동일-wall-clock 결과를 별도 보고한다. full arm OOM, step/checkpoint cap 초과, paired 이득 부재면 full arm만 KILL.
- **KILL:** formal AND gate 하나라도 실패하면 production GNN KILL; test는 열지 않는다.
- **예산·배정:** graph build CPU `24 h`, local RTX `24 h`, DGX `144 h`.[P] D1은 sampled SSL과 full diagnostic에 각각 최대 `[P] 36 GB10-h`, D2 formal은 seeds `{17,29,43}` 각각 `[P] 24 GB10-h`를 배정한다(`2×36+3×24=144`[D]). full arm이 BLOCK/KILL돼도 그 잔여분을 sampled나 formal에 더하지 않는다.

### G6 — raster segmentation + exact bridge

- **전제:** FloorPlanCAD rights/provenance PASS. 미통과는 BLOCKED.[U]
- **가설:** raster wall mask가 mask-blind vector candidate의 ambiguous subset에서 상보적 handle evidence를 준다.
- **데이터:** reported FloorPlanCAD raster/mask `5,308장`[M:S/F], gen2 render, CubiCasa DEV. candidate universe는 mask를 보기 전에 hash한다.
- **지표:** FPC pixel IoU, gen2 synthetic IoU, drawing-mask shuffle, bridge-oracle F1, phantom/missing handles, common-handle AUPRC와 paired recall.
- **PASS:** FPC IoU `≥[P]0.60`, synthetic IoU `≥[P]0.70`, bridge oracle `≥[P]0.60`, handle `ΔAUPRC≥[P]+0.02`와 CI lower `>0`.[P]
- **KILL/gray:** FPC IoU `<0.60`, synthetic IoU `<0.70`, mask shuffle과 구분 불가, 또는 최종 handle `ΔAUPRC<+0.02`/CI lower `≤0`이면 해당 raster complement claim을 KILL. bridge `<0.40`이면 raster→handle claim 즉시 KILL; `[0.40,0.60)`은 bounded redesign `[P]1회` 동안 INCONCLUSIVE이고 재검 뒤에도 `<0.60`이면 KILL. rights/provenance 미완은 BLOCKED다.
- **INVALID:** mask를 본 뒤 candidate를 만들거나 ambiguous line을 분모에서 삭제하면 INVALID.
- **예산·배정:** local CPU `16 h`, DGX `72 h`.[P] prospectively named architecture 두 개를 DEV seed `1701`에서 각각 `[P] 12 GB10-h` screen하고, frozen winner 하나를 seeds `{1701,1702,1703}`에서 각 `[P] 16 GB10-h`로 확인한다(`2×12+3×16=72`[D]). tie rule은 seal하며 best-seed 선택은 금지한다. aggregate winner 하나만 ADJ cohort에 들어간다.

### G7 — Qwen provenance gate + matched SFT/GRPO arms

- **역할:** Qwen은 피시험 predictor다. 이미지 judge, silver source, truth oracle로 쓰지 않는다.[M:T]
- **가설:** provenance-qualified Qwen continuation 중 적어도 한 family가 자신의 frozen starting checkpoint와 current non-Qwen common-handle incumbent 중 더 강한 baseline을 넘어 상보적 line-semantic signal을 낸다.
- **데이터:** rights/provenance를 통과한 FloorPlanCAD train tiles, gen2 train renders, CubiCasa DEV의 CRS-linked handle sidecar. ADJ/test와 silver는 training·selection에서 금지한다. FPC rights가 막히면 FPC-dependent arm은 BLOCK하고 다른 source로 몰래 대체하지 않는다.
- **전제:** 기존 SFT/GRPO checkpoint별 training-data manifest, hash/near-dedupe, CubiCasa/FPC holdout 접촉 여부가 확인돼야 한다. lineage unknown arm은 `QUARANTINED/UNSCORABLE`.
- **trainable arms:** `[P] 3개` family—matched SFT continuation, G1을 통과한 verifier-GRPO, G8이 생존한 경우 DAPT→SFT—각 seeds `{17,29}`[P]. frozen SFT/GRPO는 별도 diagnostic이며 total cap에 inference를 청구한다.
- **지표:** schema-validity, pixel IoU, bridge 후 common-handle AUPRC/F1, metamorphic consistency, empty/all sentinel, verifier reward와 hidden semantic의 방향.
- **PASS:** 두 seed가 같은 방향이고 aggregate `ΔAUPRC≥[P]+0.01`, paired CI lower `>0`, 모든 guards PASS인 family가 적어도 하나 있으면 Qwen `CELL_PASS`.
- **KILL/BLOCK:** 모든 eligible family가 delta gate를 못 넘거나 seed 방향이 갈리면 production Qwen claim KILL. 충분한 표본에서 G1이 실행 후 실패하면 verifier-GRPO route KILL, G1이 표본/선행조건 부족으로 INCONCLUSIVE면 BLOCK. G8이 실행 후 실패하면 DAPT→SFT route KILL, G8이 rights/lineage 미확인으로 미실행이면 BLOCK. reward가 오르며 hidden exact semantic이 내리거나 sentinel exploit가 생기면 해당 GRPO arm 즉시 KILL하고 최초 exploit checkpoint를 보존한다. lineage/rights unknown은 UNSCORABLE/BLOCK이며 pixel-only 승리는 line-semantic 승리로 부르지 않는다.
- **lineage 비용:** DAPT→SFT의 same-total-compute contrast는 G8 DAPT `24 GB10-h`+G7의 두 seed `2×12=24`, 합계 `48 GB10-h`[D]를 청구한다. matched scratch/SFT도 G8 scratch `24`+G7 matched-SFT 두 seed `24`, 합계 `48 GB10-h`[D]다. 이 paired lineage가 없으면 DAPT arm은 효과 diagnostic일 뿐 same-budget PASS가 아니다.
- **예산·배정:** local CPU `16 h`, DGX `72 h` total search cap.[P] 세 trainable family × 두 seed의 각 run은 baseline/frozen inference와 checkpoint를 포함해 동일한 `[P] 12 GB10-h` cap을 받는다(`3×2×12=72`[D]). G8의 `48 GB10-h`는 위 lineage 비교에서 별도 명시해 총 wave 장부에 이미 포함한다. BLOCK된 arm의 잔여분은 다른 arm에 주지 않는다. best-seed 선택 금지; primary contrasts와 tie rule을 seal하고 selection은 DEV, ADJ는 frozen cohort 한 번뿐이다.

### G8 — single-target DAPT as residual filler

- **전제:** corpus format census, license/provenance, train/ADJ/test family exclusion, near-dedupe PASS. target은 masked geometry 또는 transform consistency 중 하나를 outcome 전에 봉인한다.
- **가설:** 추가 pretraining을 포함한 **같은 총 GB10-hour**에서 DAPT→fine-tune이 scratch/control보다 common-handle AUPRC를 개선한다.
- **데이터:** 양 포지션이 보고한 local unlabeled CAD/floorplan corpus 중 census·rights·near-dedupe를 통과한 train-only subset.[M:S/F] source/path ID는 feature에서 금지하고 DEV/ADJ/test family와 근접중복은 제외한다.
- **지표:** common-handle AUPRC, family CI, performance-versus-total-compute curve, source-ID probe, transform consistency, representation collapse, checkpoint별 actual resource vector.
- **비교:** DAPT arm과 scratch arm에 같은 total resource vector를 준 performance-versus-compute curve를 만든다. 같은 fine-tune budget만 맞춘 결과는 효과 진단일 뿐 RSI adoption 증거가 아니다.
- **PASS:** final `ΔAUPRC≥[P]+0.01`, family CI lower `>0`, source-ID 제거 뒤에도 방향 유지.[P]
- **KILL/INCONCLUSIVE/RETRACT:** DEV canary `ΔAUPRC≤0`, representation collapse, source shortcut, 또는 완료된 final의 `ΔAUPRC<+0.01`/CI lower `≤0`이면 DAPT claim KILL. cap 안에 matched curve를 완료하지 못하면 BUDGET_KILL/INCONCLUSIVE이며 cap을 늘리지 않는다. holdout duplicate가 발견되면 결과 전체 RETRACTED.
- **예산·배정:** corpus census local CPU `24 h`, DGX `48 h`.[P] DAPT→fine-tune과 scratch/control에 각각 같은 `[P] 24 GB10-h` total cap을 주며 pretraining·fine-tuning·evaluation을 모두 그 안에 청구한다. READY gate-bearing job이 없을 때만 checkpoint-boundary filler로 실행한다. cap은 queue 공백에 따라 늘어나지 않는다.

### G9 — RL/verifier reward diagnostic; 학습은 이번 wave에서 금지

- **가설:** frozen candidate universe와 qualified reward에서 sequential policy가 greedy/bandit보다 벌 semantic headroom이 작다. 이 가설의 범위는 현재 action space에 한정한다.
- **전제:** G1 PASS. state, action, horizon, candidate coverage, verifier reward, exact semantic utility를 prereg한다. gen2 exact와 train-family real diagnostic을 둘 다 쓴다.
- **방법:** finite action space는 exact enumeration/beam으로 계산한다. randomized logging과 positivity가 없으면 IPS/DR을 쓰지 않는다.
- **지표:** oracle-minus-greedy와 beam-minus-greedy semantic utility, family CI, reward–semantic 방향, candidate coverage, compute saving. gen2와 real-family를 따로 보고 평균으로 불일치를 숨기지 않는다.
- **KILL current RL:** oracle-minus-greedy semantic utility의 family-bootstrap upper CI가 `[P]0.01` 이하이고 real/gen2가 동방향이면 현재 action-space RL을 KILL.
- **SURVIVE to future prereg:** lower CI가 `>[P]0.01`이고 beam도 greedy를 이기며 reward–semantic 방향이 일치할 때만 별도 RLVR proposal을 낸다. 나머지는 INCONCLUSIVE. 생존해도 이번 wave에는 학습하지 않는다.
- **KILL reward route:** verifier reward가 오르며 exact semantic이 내리면 verifier-policy route를 KILL.
- **예산·배정:** local CPU `72 h`; RTX/DGX `0`.[P]

---

## 5. DGX 극한 활용 — “유용한 READY job을 놀리지 않는다”로 정의

측정된 것은 GB10, unified memory `128GB`, image 존재, disk 여유 `461GB`, 당시 GPU utilization `0%`, LAN SSH뿐이다.[M:T] 실제 workload throughput, full-graph fit, checkpoint cost는 G0 전까지 `[U]`다.

queue 순서는 다음이다.[P]

1. **Q0 qualification:** G0.
2. **Q1 gate-bearing:** G5 graph SSL/formal, G6 raster, G7 Qwen 중 선행조건을 통과한 job.
3. **Q2 residual filler:** G8 DAPT. checkpoint boundary에서만 양보한다.

모든 job은 launch command, code/config/data/model hash, optimizer step, device-hour, checkpoint lineage, failure witness를 남긴다. trainer가 아직 구현·selftest되지 않았다면 READY가 아니다. READY가 없거나 rights/verifier가 BLOCKED인 idle은 허위 busywork로 채우지 않는다.

운영 metric은 전체 GPU `%`가 아니라 `READY job이 존재한 interval의 useful-compute busy fraction`, dispatch latency, lost/replayed steps다. 목표치를 수치로 발명하지 않는다.

**운영 claim의 킬:** READY interval과 idle이 겹치거나, preemption/staging 시간이 장부에서 빠지거나, actual cap 초과를 PASS로 처리하면 “work-conserving fixed-budget queue” 주장을 kill한다. filler가 Q1 시작을 no-filler schedule보다 늦추면 filler 정책을 kill한다.

---

## 6. 수정된 AIDE² RSI 실장

### 6.1 candidate node와 inner loop

node는 `(parent, operator, solution spec, code/config/data/evaluator hashes, resource vector, seed, DEV metrics, guards, failure witness, xlsx)`를 가진다.[P]

- **draft:** 서로 다른 mechanism을 만든다. 같은 architecture knob sweep은 draft가 아니다.
- **debug:** 최소 failing witness를 고치며 score feature/HPO를 섞지 않는다.
- **improve:** incumbent에 mechanism 하나만 추가하고 parent ablation을 동반한다.

inner는 DEV만 본다. candidate가 split, evaluator, guard, budget을 바꾸면 INVALID다. 이번 wave의 candidate 수는 G3/G6/G7 등 cell별 cap에 포함되고, 숨은 debug run도 모두 장부에 든다.

### 6.2 outer loop의 허용 범위

outer가 바꿀 수 있는 것은 search operator policy, feature grammar, scheduler, early-stop proposal, cache plan이다. evaluator constitution은 바꿀 수 없다. 이번 wave에는 incumbent harness와 challenger harness `[P]1개`만 paired replay한다.

outer adoption은 다음 AND gate다.[P]

1. 같은 starting frontier, candidate count, generation seed, **ex-ante total cap vector**, evaluator; 실제 사용 vector는 EFFICIENCY 판정용으로 별도 보존;
2. DEV common-handle `ΔAUPRC≥+0.01`, family-paired CI lower `>0`;
3. cell-specific guards 전부 PASS;
4. lineage 전체 동결 뒤 ADJ reveal `1회`;
5. ADJ에서도 `ΔAUPRC≥+0.01`, CI lower `>0`;
6. evidence xlsx/JSON, failure rows, budget ledger 완전.

ADJ는 prospectively 열거한 **전체 frozen finalist cohort를 한 batch로 한 번** 채점한다. batch 안 결과를 보고 finalist를 새로 고르거나 threshold를 바꾸지 않는다. ADJ 실패 시 rollback하고 같은 pane용 challenger를 만들지 않는다. ADJ가 역사적으로 pristine가 아니므로 통과는 W2의 prospective survival이지 최종 unbiased generalization proof가 아니다.

**outer claim의 킬:** 한 wave에서 두 번째 challenger, 두 번째 ADJ reveal, 더 많은 search/query, evaluator 변경 중 하나라도 있으면 same-budget RSI improvement claim을 kill한다.

### 6.3 과업 이질성

CubiCasa, gen2, FloorPlanCAD를 임의 가중합 하나로 만들지 않는다. common line-semantic claim의 primary는 CubiCasa common-handle AUPRC이고, gen2 exact soundness와 relevant FPC transfer는 별도 hard gate다. 한 substrate의 대승이 다른 substrate FAIL을 평균으로 지우지 못한다. data source가 unavailable이면 사전 truth table에 따라 BLOCKED 또는 narrower claim으로 강등한다.

**킬:** outcome 뒤 mixture weight를 선택하거나 unavailable source를 분모에서 지우면 heterogeneous-generalization claim을 kill한다.

### 6.4 보상해킹 3층

1. **지시층:** truth namespace, test 금지, READ-ONLY, fixed budget, failure 보존, xlsx 의무, 금지 field를 node contract에 넣는다.
2. **하드층:** world-IR `26/26`, CRS 역투영 `0.0`, gen2 ledger, G1 verifier, family/near-dedupe, name/id allowlist, label shuffle, zero/all sentinel, hidden mutation, ADJ/test ACL을 실행 전후 검사한다.[M:T]
3. **통계층:** seed/family/style/source별 분포를 보존하고, peer extreme·one-seed-only win·reward/semantic divergence·비현실적 compute를 `audit trigger`로 쓴다. 미측정 천장에 기대는 절대 AUC/F1 선은 쓰지 않는다. 후보 수가 작으면 모든 winner를 audit한다.

통계층은 누출 판정기가 아니다. qualification suite에 의도적으로 심은 ID leak, family duplicate, verifier exploit node를 넣고, 생성·평가·clean replay를 G0-C의 `[P]12 CPU-h`에 청구한다. 하나라도 quarantine하지 못하면 “3층 방어 READY” 주장을 KILL한다. 어떤 quarantine node도 clean replay 전에 parent가 될 수 없다.

### 6.5 eval repair와 test 봉인

eval defect는 outer improve가 아니라 governance interrupt다. 새 evaluator에서 comparable cohort 전체를 replay한 뒤 tree를 재개한다. test 뒤 defect가 발견돼도 same method ID로 다시 열지 않으며, 새 evaluator/method는 새 prereg와 별도 test 권리 심사를 거친다.

**킬:** test-derived 정보가 동일 lineage의 model, threshold, resolver, harness에 들어가면 해당 confirmatory claim을 kill한다.

---

## 7. 수정된 강주장

### 강주장 A — 관계 evidence는 강하지만 “그러므로 GNN”은 아직 무근거다

**근거:** fixed context aggregates만으로 `0.517→0.705`가 측정됐고 message passing의 paired lift는 아직 없다.[M:T]

**킬:** G5가 formal AND gate를 모두 통과하면 GNN 회의론을 철회한다. G3가 B* 대비 `[P]+0.10 AUPRC`를 내면 production GNN은 Occam-KILL한다.

### 강주장 B — 지금 가장 먼저 사야 할 것은 `0.705` 오류의 구조 원장이다

**근거:** aggregate FN/FP는 있지만 current model의 prereg strata별 전수 해부는 보고되지 않았다.[M:S/F]

**킬:** G2의 모든 strata가 `[P]1.5×` 미만이고 그 결과가 G5/G6 우선순위나 해석을 바꾸지 못하면 “error autopsy first” 주장을 철회한다.

### 강주장 C — DGX의 첫 가치는 속도 주장이 아니라 속도·메모리 주장을 반증할 계측권이다

**근거:** `128GB`, `461GB`, 당시 `0%`는 실측이지만 workload throughput/full-graph fit은 미측정이다.[M:T]

**킬:** G0가 어떤 route도 바꾸지 못하고 G5 full-vs-sampled도 같은 비용에서 차이를 만들지 못하면 DGX qualification 우선 주장을 철회한다. 이는 DGX 전체의 무가치 주장이 아니다.

### 강주장 D — verifier-only RL을 아직 벽 의미 학습이라고 부를 수 없다

**근거:** `FAR=0/3024`, `FRR=0/504`는 LINE-only 제한이 있고 verifier는 구성 문법을 본다.[M:T]

**킬:** G1 full-diversity/name-blind qualification을 통과하고 G7/G9에서 reward 상승이 hidden exact semantic과 동방향이며 matched SFT/current policy를 same-budget gate로 이기면 이 제한을 철회한다.

### 강주장 E — 이번 wave test 소비 `0`이 정보 효율적이다

**근거:** B* AUPRC, verifier diversity, GNN/raster/Qwen method ID가 아직 동결되지 않았다.[M:T/S/F]

**재심/킬:** 모든 upstream gate와 최종 method ID가 동결되면 다음 wave 단발 개방을 심사한다. 그 상태가 되었는데도 추가 개발 이득 없이 test를 무기한 미루면 “0이 효율적”이라는 주장을 철회한다. W2 안에서는 prereg대로 `0`을 유지한다.

### 강주장 F — prospective ADJ는 유용하지만 private의 소급 복원은 아니다

**근거:** current `0.705`와 radius가 전체 val에 적응했다는 양측의 인정.[M:S/F]

**킬:** 과거 접근 원장이 ADJ에 들어갈 모든 family의 label·prediction·aggregate가 어떤 선택에도 영향을 주지 않았음을 증명하면 “소급 복원 불가” 판정을 재심한다. 그 증거가 없으면 ADJ 통과를 unbiased generalization estimate로 부르지 않는다.

---

## 8. 성공과 종결의 정의

이번 wave의 성공은 DGX 사용시간이나 최고 DEV 숫자가 아니다. 다음 중 하나가 증거 xlsx, hashes, budget ledger, failure witness와 함께 성립할 때 성공이다.

- 같은 resource vector·handle universe·evaluator에서 mechanism이 gate를 통과한다.
- expensive branch가 cheap gate에서 정직하게 죽는다.
- BLOCKED/FAIL/INCONCLUSIVE/INVALID를 구분하고 outcome 뒤 split·band·budget을 이동하지 않는다.
- ADJ와 test를 reward loop에 되먹이지 않는다.
- READY job만 DGX에서 실행하고, 과학적으로 닫힌 뒤의 idle을 busywork로 채우지 않는다.

**이 종결 정의의 킬:** 필수 artifact 하나라도 없거나 failure row를 삭제하면 해당 PASS와 성공 주장을 무효로 한다.

ROUND2_COMPLETE: sol
