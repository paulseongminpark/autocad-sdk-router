# E2 다음 웨이브 블라인드 포지션 페이퍼 — sol

## 판정 요약

내 입장은 세 문장이다.

1. `0.236 → 0.517 → 0.705`는 **두께 prior의 승리도, GNN의 사전 승리도 아니다.** 단일 선의 모양보다 비선형 조합이 중요했고, 그보다 이웃 관계의 압축 통계가 더 중요했다는 증거다. `0.705`에서 가장 큰 미해결 축은 재현율이며, 다음 판별 대상은 typed multi-hop 관계가 그 누락분을 실제로 회수하는지다.〔M:E1,E2〕
2. DGX는 즉시 work-conserving queue로 전환해 graph SSL, formal GNN, raster segmentation, Qwen domain pretraining, Qwen SFT/GRPO 비교의 다섯 셀을 연속 점유시켜야 한다. 다만 GPU를 바쁘게 만드는 것과 과학적 채택은 별개다. 각 셀은 고정 예산과 private-val 게이트를 못 넘으면 종료한다.〔M:E0,E5,E9; P:본 문서 §2〕
3. verifier는 RL의 출발 허가증이지 의미 정답이 아니다. 현재 `FAR=0/3024`, `FRR=0/504`는 훌륭한 계측기 자격 신호지만 LINE-only 팩과 layer-dependent 구성 판정 위의 결과다. 전체 다양성·name-blind·hidden-family 시험 전에는 verifier reward로 얻은 성능을 “벽 의미 학습”이라고 부르지 않는다.〔M:E4,A11〕

### 수치·증거 표기 규약

- `M`은 이미 측정된 수치다. 바로 뒤의 증거 아티팩트가 원천이다.
- `P`는 이 페이퍼가 제안해 봉인할 예산·밴드·시드다. 관측값이 아니며, 실행 전 prereg JSON과 evidence-xlsx schema에 복사되어야 효력이 생긴다. 이 파일 자체가 제안값의 원천 아티팩트다.
- test 수치는 이 문서에 없다. CubiCasa test는 방법별 동결 뒤 단발만 허용한다.〔M:E0,E8〕

### 증거 아티팩트 원장

- **E0 — 임무·프로그램 사실·AIDE² 계약:** `D:\runs\e2_program\duo\20260719_next_wave\task.md`
- **E1 — 문맥 GBDT 실측:** `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\cml_ctx\results.json`, `REPORT.md`, `evidence.xlsx`
- **E2 — 규칙/6특징 기준선과 오류 클래스:** `D:\dev\99_tools\autocad-sdk-router\reports\e2\ext\calibration_v1.json`, `ml_val_v1.json`, `cubicasa_ir_val.json`
- **E3 — gen2 및 반증 C0:** `D:\dev\99_tools\autocad-sdk-router\reports\e2\instruments\gen2_REPORT.md`, `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\feyerabend_c0\REPORT.md`, `coverage_numbers.json`
- **E4 — verifier 실측·구현:** `D:\dev\99_tools\autocad-sdk-router\reports\e2\instruments\REPORT_verifier.md`, `verifier_far_frr_numbers.json`, `D:\dev\99_tools\autocad-sdk-router\tools\e2\instruments\verifier.py`
- **E5 — GNN/formal·공통 프로그램 게이트:** `D:\dev\99_tools\autocad-sdk-router\reports\e2\dossiers\calibration_P3.md`, `D:\dev\99_tools\autocad-sdk-router\reports\e2\synthesis\FINAL_PROGRAM_PLAN.md`
- **E6 — 치수 정박 반증이론:** `D:\dev\99_tools\autocad-sdk-router\reports\e2\dossiers\feyerabend_P2.md`
- **E7 — PU 약지도 사다리:** `D:\dev\99_tools\autocad-sdk-router\reports\e2\dossiers\calibration_P2.md`
- **E8 — verifier/RL·봉인 규율:** `D:\dev\99_tools\autocad-sdk-router\reports\e2\dossiers\calibration_P6.md`, `D:\dev\99_tools\autocad-sdk-router\reports\e2\prereg_program_v1.json`
- **E9 — 로컬 ML 자산:** `D:\dev\99_tools\autocad-sdk-router\reports\e2\LOCAL_ML_ASSETS.md`
- **E10 — world-IR·CRS:** `D:\dev\99_tools\autocad-sdk-router\reports\e2\instruments\worldir_REPORT.md`, `crs_REPORT.md`
- **E11 — raster/bridge 세부 셀:** `D:\dev\99_tools\autocad-sdk-router\reports\e2\dossiers\CELLS_INDEX.md`
- **A11 — 현재 코드 실태:** `D:\dev\99_tools\autocad-sdk-router\tools\e2\cells\cml_ctx.py`, `feyerabend_c0.py`, `D:\dev\99_tools\autocad-sdk-router\tools\e2\detect\unit_anchor.py`, 그리고 E4의 verifier 코드. 허용된 `tools\e2` 인벤토리에는 아직 formal GNN·PU·raster·Qwen trainer가 착지하지 않았다. 따라서 이들은 READY가 아니라 구현/비행 중 또는 OPEN이다.

---

## 1. 결과 해석: 무엇이 죽었고, 무엇이 아직 살아 있는가

### 1.1 `0.236`: 절대 두께 규칙은 의미 판별기가 아니었다

규칙 탐지기는 val에서 `F1=0.2358`, `P=0.134`, `R=0.9808`이었다. 벽 기저율은 약 `0.118`이다. 즉 재현율을 거의 다 얻는 대신 비벽을 대량으로 벽이라 불렀고, 정밀도는 기저율에서 거의 벗어나지 못했다. 축척 sweep에서도 최고 F1이 사실상 움직이지 않았다. 이는 “벽은 특정 물리 두께의 평행선”이 CubiCasa SEG-IR에서 분별적 의미 prior가 아니었다는 직접 반증이다.〔M:E0,E2〕

오탐의 상위 계열은 Direction, BoundaryPolygon, DimensionMark, Door, Window 등이다. 이들은 길고 평행하며 간격을 갖는다는 점에서 벽과 기하적으로 닮았다. 따라서 이 실패는 단순 threshold 미세조정 문제가 아니라 **동일한 국소 기하를 공유하는 서로 다른 의미 클래스**의 문제다.〔M:E2〕

### 1.2 `0.517`: 정보가 없었던 것이 아니라 조합식이 틀렸다

같은 벡터축의 지역 기하 `6`특징을 HistGBDT가 비선형으로 조합하자 val `F1=0.5173`, `AUC=0.9215`, `P=0.8596`, `R=0.3699`가 됐다. 선형 logistic은 `F1=0.0532`였고 label-shuffle AUC는 `0.3752`였다.〔M:E2〕

해석은 명확하다.

- 원시 특징 안에는 ranking signal이 이미 있었다. 높은 AUC가 그 증거다.
- 그러나 그 신호는 선형 가중합으로 회수되지 않았다. 길이·방향·평행·두께의 조건부 상호작용이 필요했다.
- `F1=0.517`의 병목은 정밀도가 아니라 재현율이었다. 모델은 “확실한 벽”만 좁게 골랐다.
- shuffle가 실패하지 않았으므로 현재 관측을 label leakage 하나로 설명할 근거는 없다. 다만 family/template 누수까지 모두 닫혔다는 뜻도 아니다.

### 1.3 `0.705`: H3는 지지됐지만 GNN은 아직 무죄추정 대상이 아니다

정션 차수, 최근접 평행 갭, 반경 밀도, 길이 백분위, 각도 엔트로피, 두께대역 평행 이웃 수를 추가하자 val `F1=0.705367`, `AUC=0.967050`, `P=0.824077`, `R=0.616551`이 됐다. 기준선 대비 F1 증가는 `+0.188106`이고, 핵심 변화는 재현율 `+0.246625`였다. label-shuffle AUC는 `0.332029`였다. permutation importance의 상위 두 특징은 정션 차수와 최근접 평행 갭이었다.〔M:E1〕

이 결과는 H3, 즉 “벽다움은 이웃 관계 패턴”이라는 명제를 직접 지지한다. 그러나 더 좁은 명제만 지지한다. **고정된 관계 집계가 유용하다**는 것이지, message passing이나 self-supervision이 필요하다는 증거는 아니다. 실제로 이 셀은 val에서 반경 후보 `20/40/80 px`를 비교해 `20 px`를 선택했고, test에는 접촉하지 않았다. 따라서 `0.705`는 강한 개발 기준선이지 held-out 최종치가 아니다.〔M:E1〕

고정 threshold의 오차 원장에는 `FN=15,624`, `FP=5,363`이 남아 있다. 잔여 오류가 오탐보다 미탐 쪽에 더 무겁다는 사실은 “더 보수적인 후필터”보다 “끊긴 벽 문맥을 회수하는 표현”을 우선 시험해야 한다는 근거다.〔M:E1〕

### 1.4 현재 접근의 천장

나는 현 접근의 최종 F1 천장을 숫자로 발명하지 않겠다. 다만 **현 표현의 운용 천장**은 분명하다.

1. **관계 손실:** 현재 모델은 이웃 관계를 카운트·최솟값·엔트로피로 접는다. 어느 선과 어느 선이 어떤 typed relation으로 연결됐는지, 관계가 몇 hop 이어지는지, 동일 component가 방 경계를 이루는지는 사라진다. GNN이 노릴 수 있는 정당한 잔여 정보는 바로 이 손실분이다.〔M:E1,E5,A11〕
2. **고정 반경·축척:** 선택 반경과 두께대역이 pixel/전역 scale에 묶여 있다. 현재 `unit_anchor.py`는 DIMENSION/TEXT와 INSUNITS를 결합하지만, in-flight C1이 요구하는 다중 anchor 합의·선택적 HIGH confidence·4-scale causal A/B까지는 구현하지 않는다. scale 문제는 죽지 않았지만, scale만 고쳐 `0.705`의 관계 이득을 대신할 근거도 없다.〔M:E6,A11〕
3. **국소 동형성:** 벽과 Door/Window/Direction/BoundaryPolygon/DimensionMark는 짧은 반경에서는 동형에 가깝다. 반복 symbol subgraph, component topology, room/raster context가 없으면 그 구분은 원리적으로 어렵다.〔M:E2,E5〕
4. **개발셋 적응:** 반경과 모델 선택이 val에 적응했다. drawing-family 단위 private-val과 style-OOD를 통과하기 전에는 `0.705`를 일반화 성능으로 말할 수 없다.〔M:E1,E5〕
5. **평가 단위의 한계:** line-level label은 벽 경계선과 벽 객체를 같다고 가정한다. 곡선, 개구부, poché, 끊긴 경계에서는 raster/room-level evidence가 상보적일 수 있으나, CRS bridge 없이 그것을 handle truth로 승격하면 과업을 바꿔치기한다.〔M:E10,E11〕

### 1.5 남은 오류의 구조 가설과 반증

- **H-R1 — 끊긴 관계 미탐:** 개구부·곡선·분절 때문에 직접 parallel mate가 약한 진짜 벽은 두세 hop의 junction/collinearity chain으로만 회수된다. **킬:** typed edge를 넣은 모델의 NoMessage 대비 이득이 없거나, 이득이 직접 이웃 카운트만으로 재현되면 kill.
- **H-R2 — symbol subgraph 오탐:** 긴 평행 비벽은 국소 gap은 벽과 같지만 반복 motif와 component 종결 방식이 다르다. **킬:** class-slice에서 Direction/BoundaryPolygon/Door/Window/DimensionMark 오탐이 줄지 않고 전체 점수만 오르면 size/style shortcut으로 판정.〔M:E2,E5〕
- **H-R3 — 선택적 scale nuisance:** DIM/TEXT/GRID anchor가 HIGH인 도면에서만 상대 gap이 absolute gap보다 좋아진다. **킬:** HIGH scale 정확도·coverage 또는 4-scale 상대 F1 게이트 중 하나라도 실패하면 scale counter-theory kill.〔P:E6〕
- **H-R4 — family/style shortcut:** random line split이 아니라 drawing/template family를 갈라 놓으면 현재 lift 일부가 소멸한다. **킬:** family-disjoint private-val에서 incumbent와 challenger의 paired lift CI 하한이 `0` 이하이면 challenger kill.〔P:E5〕
- **H-R5 — raster의 조건부 상보성:** 벡터 관계가 모호한 subset에서만 mask/visual context가 recall을 올린다. **킬:** mask-shuffle과 실제 mask가 구분되지 않거나, bridge 후 handle 성능이 incumbent를 못 이기면 raster complement claim kill.〔P:E11〕

---

## 2. 다음 웨이브 실험 목록

공통 계약은 원본 CAD READ-ONLY, train/val만 개발, test 방법당 단발, label shuffle, family split, evidence xlsx, 실패행 보존이다. 모든 budget은 **상한**이며 태울 quota가 아니다. early kill로 남은 계산은 다음 READY 셀로 넘긴다.〔M:E0,E8〕

### X1 — gen2 전량 + verifier 전체다양성 soundness

- **가설:** LINE-only에서 얻은 verifier 자격이 `13` entity type과 `8` hard-negative class, zero/all sentinel, hidden mutation family에서도 유지된다.〔M:E0,E3,E4〕
- **데이터:** gen2 v2 S/F/M 전량, reward-visible mutation family와 완전히 분리한 hidden family, label-poisoned twin.
- **지표:** mutation·topology family별 FAR/FRR, true/false claim count, name-blind delta, sentinel, byte/hash replay, reward-family/hidden-family 교집합.
- **채택/킬:** `FAR≤0.01 ∧ FRR≤0.05`; 어느 family든 FAR가 상한을 넘거나 FRR가 상한을 넘으면 RL·verifier reward 전부 중단한다. label 변화가 verdict를 바꾸거나 hidden ID가 학습 로그에 한 번이라도 나오면 run 무효다.〔P:E5,E8〕
- **고정 예산·배정:** local CPU `1일`, soundness seeds `{0,1,2}`; DGX `0`.〔P:E8〕

### X2 — 치수 정박 scale counter-theory C1→C4

- **가설:** 벽 label을 보지 않는 DIM/TEXT/GRID consensus가 HIGH-confidence scale을 만들고, 그 subset에서 상대 gap만 absolute gap보다 개선된다.
- **데이터:** C0가 byte-reproducible하게 만든 base scene `50개 × 4 scale = 200 IR`, deterministic corruption, 이후 DIM-rich real def `30개`.〔M:E0,E3; P:E6〕
- **지표:** HIGH subset scale 상대오차, scale별 coverage, pair-label permutation digest, scale별 pair P/R/F1, mapped Jaccard, real selective `Δr`와 clustered CI.
- **채택/킬:** HIGH의 `95%` 이상이 true scale 대비 `5%` 이내이고 scale별 HIGH coverage가 `0.60` 이상이어야 한다. 상대 pair F1은 네 scale 모두 `0.85` 이상, mapped Jaccard는 `0.95` 이상이어야 한다. real HIGH subset `Δr<+0.05`면 합성 결과와 평균내지 않고 이론을 kill한다.〔P:E6〕
- **고정 예산·배정:** C1 `1 CPU-h` + C2 `2 CPU-h` + C3 `1 CPU-h` + C4 `4 CPU-h`; local CPU만, DGX `0`.〔P:E6〕

### X3 — B* 동결과 cheap graph-stat Occam 공격

- **가설:** component·two-hop·motif를 결정론 집계한 강한 비-GNN이 typed GNN의 기대 이득 상당 부분을 더 싸게 회수할 수 있다.
- **데이터:** CubiCasa train/val SEG-IR, gen2 v2, family-disjoint split; test와 FloorPlanCAD mask는 닫는다.
- **지표:** 동일 handle universe의 AUPRC/F1/P/R, drawing-macro, style slice, runtime/RSS, name/id allowlist, label shuffle, family collision. 현재 `0.705` 모델의 AUPRC도 같은 evaluator로 새로 계산하며 F1을 AUPRC처럼 복사하지 않는다.〔M:E1; P:E5〕
- **채택/킬:** baseline universe·split hash가 하나라도 다르거나 shuffle가 봉인 null 밖 신호를 반복하면 B* 동결 실패다. graph-stat classical이 기존 B* 대비 `+0.10`을 내면 GNN production 경로를 Occam kill한다.〔P:E5〕
- **고정 예산·배정:** local CPU `2일` 상한, local GPU diagnostic `1회`, DGX `0`.〔P:E5〕

### X4 — PU 약지도 사다리

- **가설:** 고정밀 geometry/topology anchor와 correlation-aware LF, PU risk가 exact train label 없이도 P/N-only 및 P1보다 벽 grammar coverage를 늘린다.
- **데이터:** gen2 exact truth는 anchor 감사용, CubiCasa train truth는 trainer에서 방화벽으로 격리하고 val에서만 평가, `1.dwg`는 unlabeled drift/coverage 진단. silver는 기본 OFF다.〔M:E7〕
- **지표:** anchor positive/negative precision, grammar별 support, LF conflict/dependency, AUPRC, `P@R=0.50`, seed 분산, class-prior sensitivity, calibration REL/RES, shuffle.
- **채택/킬:** positive anchor precision `≥0.98`, negative anchor precision `≥0.995`, 지원 대상으로 prereg한 모든 wall grammar에 anchor가 있어야 한다. main PU가 P/N-only를 못 이기거나, 허용 class-prior 구간에서 결론이 뒤집히거나, 다수 seed에서 P1 이하이면 kill한다.〔P:E7〕
- **고정 예산·배정:** feature cache 후 local CPU `2일`, RAM soft cap `32GB`, seed `{7,17,29,43,71}`; DGX `0`.〔P:E7〕

### X5 — typed GNN: E1/E2 screen → DGX formal

- **가설:** 정확한 typed adjacency 위의 multi-hop message passing과 train-family SSL이 B*가 잃은 관계 정보를 회수한다.
- **데이터:** gen2 node/pair truth, CubiCasa SEG-IR, mask-blind 조건에서만 생성한 FloorPlanCAD candidate graph, label 없는 real train-family graph. silver와 test geometry는 pretrain에서도 금지한다.〔P:E5〕
- **지표:** relation type별 candidate recall, edge/node fanout, peak RAM, E2 no-pretrain 대비 SSL, F/C development AUPRC, S node/pair F1, style-OOD drop, calibration REL/RES, B* paired lift CI, NoMessage·edge-type-shuffle ablation.
- **screen 킬:** known relation recall `<0.98`, RAM `>48GB`, unresolved required reference, 최소 sampled config의 local `16GB` OOM 반복, 또는 seed `17`에서 SSL이 no-pretrain과 P2 모두보다 나쁘고 구현 결함이 없으면 DGX escalation을 중단한다.〔P:E5〕
- **formal 채택/킬:** `AUPRC_F≥B*+0.05`, lift CI lower `>0`, S node `F1≥0.92`, S pair `F1≥0.80`, style-OOD drop `≤0.10`, `REL≤0.03`, `RES≥0.03`를 모두 만족해야 한다. 하나라도 실패하면 GNN 경로 kill; test는 열지 않는다.〔P:E5〕
- **고정 예산·배정:** E1 local CPU `1일`; E2 RTX `1 GPU-day`, seed `17`; **DGX-D1** full graph SSL `3 GB10-GPU-days`; **DGX-D2** formal fine-tune/ablation `3 seeds × 1 GB10-GPU-day`, seeds `{17,29,43}`. D1/D2 모두 shard checkpoint와 local hash/parity replay가 필수다.〔P:E5〕

### X6 — FloorPlanCAD raster segmenter + exact bridge

- **가설:** raster mask는 vector 관계가 놓치는 벽 영역을 제공하고, CRS bridge 뒤 특정 ambiguous subset의 handle recall을 보완한다.
- **데이터:** FloorPlanCAD raster `5,308장`과 wall bbox/segmask, gen2 render, CubiCasa val; mask를 닫은 상태에서 line candidate/graph를 먼저 hash한다.〔M:E0,E9〕
- **지표:** pixel IoU, mask-shuffle control, bridge-oracle F1, mapping accuracy/phantom count, handle AUPRC/F1, vector-only 대비 paired recall delta, ambiguity coverage.
- **채택/킬:** bridge oracle F1 `<0.4`면 raster→handle claim 전체 kill; `0.4–0.6`은 bounded redesign 한 번만 허용; synthetic wall-pixel IoU `<0.70` 또는 drawing-mask shuffle과 구분 불가면 segmenter kill. mask를 보고 candidate line을 만들거나 ambiguous line을 분모에서 삭제하면 run 무효다.〔P:E11〕
- **고정 예산·배정:** **DGX-D3** `3 GB10-GPU-days`, seeds `{1701,1702,1703}`; local CPU는 bridge/evidence replay만 한다.〔P:E11〕

### X7 — 대규모 domain-adaptive pretraining(DAPT) 가치 판별

- **가설:** task label 없이 로컬 평면도·CAD 코퍼스의 구조를 먼저 학습하면 같은 downstream fine-tune 예산에서 graph/raster 표현이 개선된다.
- **데이터:** provenance 허용된 train-only FloorPlanCAD, pseudo-floor-plan-12k, ArchCAD, Zenodo10K와 CubiCasa train; test와 wall mask는 pretraining target에서 제외한다. 로컬 자산의 실재·형태는 E9가 근거다.〔M:E9〕
- **팔:** scratch/frozen pretrained 대비 동일 architecture·동일 fine-tune steps의 DAPT. masked geometry와 transform consistency만 허용하고 dataset/path ID는 feature에서 금지한다.
- **지표:** private-val AUPRC/IoU, source-classifier accuracy, transform consistency, duplicate leakage, downstream gain per GB10-hour.
- **채택/킬:** 첫 고정 canary 뒤 private downstream 개선 방향이 없거나 source ID 제거 시 이득이 사라지면 남은 pretraining을 kill한다. 전체 예산 뒤 RSI 채택 gate를 못 넘으면 checkpoint는 연구 아티팩트로만 보존한다.
- **고정 예산·배정:** **DGX-D4** `2 GB10-GPU-days`, canary `1 GB10-GPU-day` 뒤 단 한 번의 continue/kill; 별도 HPO 없음.〔P:본 문서〕

### X8 — 기존 Qwen floorplan SFT/GRPO의 동등예산 비교와 제한적 계속학습

- **가설:** 기존 Qwen2.5-VL-3B floorplan SFT 또는 GRPO가 generic vision 시작점보다 유용할 수 있지만, verifier-only GRPO는 semantic reward hacking 위험이 있다. 기존 SFT/GRPO 자산은 실제로 로컬에 있다.〔M:E0,E9〕
- **데이터:** X6의 train/val raster와 gen2 hidden render; CRS로 연결된 handle sidecar. grok 이미지 배심은 계속 유보하고 qwen 출력은 mask/polygon schema로만 기계 채점한다.〔M:E0,E10〕
- **팔:** frozen SFT, frozen GRPO, matched SFT continuation, verifier-GRPO continuation, verifier+exact-train 혼합, DAPT→SFT. 동일 image/handle batch와 decode budget을 쓴다.
- **지표:** schema-valid rate, pixel IoU, bridge 후 handle AUPRC/F1, metamorphic consistency, verifier reward–hidden semantic rank correlation, empty/all output, compute.
- **채택/킬:** frozen 또는 계속학습 arm이 X6 segmenter/현 B*의 해당 축을 RSI private gate로 못 이기면 VLM production 승격을 kill한다. reward가 오르는데 hidden exact F1/IoU가 내리거나 sentinel exploit가 발생하면 GRPO arm을 즉시 kill하고 최초 exploit checkpoint를 보존한다. X1 미통과 시 verifier-GRPO arm은 BLOCKED다.
- **고정 예산·배정:** **DGX-D5** `6 arms × 0.5 GB10-GPU-day` cap; 동일 checkpoint interval, best-seed 선택 금지. 기존 계획의 local open-finetune `6셀 × 0.5–2 GPU-day` 범위 중 최소 동일예산 screen을 DGX로 옮긴다.〔P:E5〕

### X9 — verifier reward: bandit 먼저, RLVR은 조건부

- **가설:** 비싼 evidence action의 선택은 짧은 horizon이면 contextual bandit으로 충분하고, full RL은 multi-step 가치가 입증될 때만 이긴다.
- **데이터:** X1을 통과한 verifier, gen2 reward-visible/hidden family, 동결 B*, 행동별 실측 compute table. silver/LLM score는 reward에서 금지한다.〔P:E8〕
- **지표:** hidden AUPRC/F1, compute saving, Brier, IPS/DR utility, arm mix, reward–semantic 동향, sentinel, verifier FAR 재확인.
- **채택/킬:** 프로그램 채택은 compute saving `≥30%`이면서 F1 drop `≤0.02`; saving `<10%`면 routing 자체 kill. full RL은 bandit 대비 utility ratio `≥1.05`일 때만 생존한다. hidden에서 reward가 오르며 semantic이 내리면 정책을 즉시 폐기한다.〔P:E5,E8〕
- **고정 예산·배정:** offline bandit local CPU `1일`, horizon enumeration local CPU `1일`; RLVR 생존 시 RTX에서 arm/seed당 `24h` cap, seeds `{17,29,43}` 순차. DGX `0`—DGX 다섯 셀과 자원 경합시키지 않는다.〔P:E5,E8〕

### DGX 극한 활용 운영안

DGX Spark는 GB10, 통합메모리 `128GB`, `nvcr pytorch:25.04-py3`, 디스크 여유 `461GB`, 현재 GPU 사용률 `0%`, LAN ssh 직결 상태다.〔M:E0〕 따라서 D1→D5를 단일 work-conserving queue로 운용한다.

- READY 셀이 있으면 DGX는 놀지 않는다. gate 대기 셀은 건너뛰고 다음 READY 셀을 실행한다.
- D1/D2가 graph gate로 막히는 동안 D3 raster 또는 D4 DAPT를 실행한다. X1이 막히면 D5의 verifier-GRPO arm만 닫고 SFT/DAPT arms는 계속한다.
- 모든 job은 shard checkpoint, optimizer step, data/config/model hash, GPU-hour를 기록한다. 재개는 같은 shard/step에서만 한다.
- “예산을 다 썼다”는 채택 근거가 아니다. private gate를 못 넘으면 checkpoint를 보존하고 다음 셀로 이동한다.
- D1–D5를 다 완료하거나 정직하게 kill/block한 뒤의 유휴는 낭비가 아니라 증거에 따른 종료다. 허위 busywork를 만들지 않는다.

---

## 3. E2용 AIDE² RSI 실장안

### 3.1 상태와 평가면

각 candidate node는 `(parent_hash, solution_spec, harness_version, code/config/data hashes, budget_vector, seed, public metrics, private verdict, shuffle/sentinel, xlsx, failure witness)`를 갖는다. node의 해는 모델만이 아니라 feature procedure, graph relation, calibration, resolver, data-source arm의 조합이다.

- **public:** CubiCasa train과 family-hash로 고정한 `val-public`; inner agent가 상세 오류를 볼 수 있다.
- **private:** 같은 val 안에서 격리한 `val-private`; evaluator는 primary score와 사전등록 failure code만 반환하고 row-level label/오류는 inner에 주지 않는다. 정확한 family 목록과 split hash는 F00 manifest에 봉인한다.
- **test:** 별도 ACL과 access ledger를 가진다. inner/outer 모두 접근하지 못하며 방법이 완전히 동결된 뒤 F06 job 하나만 연다.〔P:E5,E8〕

`0.705`는 F1이고 formal GNN primary는 AUPRC다. 따라서 RSI 시작 전에 현 문맥 GBDT를 동일 private universe에서 다시 평가해 B* AUPRC를 만든다. 서로 다른 metric이나 handle universe 사이의 숫자 비교를 금지한다.〔M:E1; P:E5〕

### 3.2 inner loop — 해 최적화

inner가 바꿀 수 있는 것은 한 node의 model/feature/config다. 각 iteration은 다음 연산자 하나를 명시한다.

- **draft:** 메커니즘이 다른 복수안—cheap graph-stat, typed GNN, raster complement, PU—을 만든다. 같은 아키텍처의 미세 knob만 여러 개 내는 것은 draft가 아니다.
- **debug:** failing leaf의 재현 witness를 고치되, score 개선을 위한 feature/HPO를 섞지 않는다. evaluator bug라면 model node가 아니라 harness repair 제안으로 outer에 올린다.
- **improve:** 전체 tree의 현재 incumbent 하나를 선택해 한 가지 메커니즘만 추가한다. parent 대비 ablation이 없는 조합 개선은 채택하지 않는다.

inner는 public만 본다. 각 node는 실험별 budget cap과 test-contact `0`을 하드 제한으로 받고, budget을 넘기거나 xlsx/failure sheet가 없으면 점수와 무관하게 INVALID다.〔P:E0,E8〕

### 3.3 outer loop — 하네스 자체 최적화

outer가 고칠 수 있는 대상은 다음이다.

- draft/debug/improve 선택 확률과 후보 다양성 정책
- feature 생성 절차, graph top-k/radius 선정법, candidate pruning
- family split/dedupe, metric aggregation, calibration, bootstrap unit
- budget allocator와 early-stop, CPU/local-GPU/DGX queue routing
- verifier mutation family, shuffle/sentinel, suspicious-result quarantine
- evidence xlsx/JSON 직렬화와 재현 replay

outer는 private label 자체를 보지 않고 evaluator verdict만 본다. harness를 고치면 `harness_version`을 올리고, **incumbent와 challenger를 모두 새 harness·같은 예산으로 재평가**한다. universe나 metric이 바뀌었는데 옛 점수와 새 점수를 이어 붙이는 것을 금지한다.

평가 결함은 exploitation 대상이 아니라 repair 대상이다. 예컨대 이전 B4 sentinel 사후면제나 per-handle fold 오류 같은 defect가 발견되면, 그 defect로 높은 점수를 낸 node를 승자로 두지 않는다. defect를 최소 witness로 봉인하고, 전체 comparable cohort를 새 evaluator로 재생한 뒤에만 tree를 재개한다.〔M:E0의 프로그램 교훈; M:E4〕

### 3.4 수치 채택 게이트와 고정 비용

비용은 서로 환산하지 않는 vector로 기록한다: `(CPU-h, RTX-h, GB10-h, peak RAM, disk read/write, private evaluations, test contacts)`. 같은 실험의 challenger는 incumbent와 같은 상한 vector를 받는다. 남은 quota를 다른 자원으로 몰래 바꾸지 않는다.

공통 outer 채택은 다음을 모두 만족해야 한다.

1. private `ΔAUPRC ≥ +0.01`이고 drawing/family paired bootstrap CI lower `>0`;〔P:본 문서〕
2. experiment-specific hard gates—shuffle, sentinel, calibration, relation recall, bridge, verifier—전부 PASS;
3. budget vector 초과 없음, private evaluation은 candidate당 `1회`, test contact `0`;
4. evidence xlsx/JSON과 failure witness 완전;
5. 더 엄격한 기존 gate가 있으면 그것이 우선한다. GNN은 `B*+0.05 AUPRC`, routing은 saving `≥30% ∧ F1 drop≤0.02`, RL은 utility ratio `≥1.05`를 그대로 쓴다.〔P:E5,E8〕

`+0.01`은 범용 RSI node의 최소 실용 개선 제안값이지 GNN formal band를 낮추는 장치가 아니다. private 점수가 좋아도 계산비가 늘었다면 같은 budget에서 다시 비교하고, 같은 budget으로 실행할 수 없으면 채택이 아니라 별도 resource-class 제안이다.

### 3.5 보상해킹 3층 방어의 E2 구현

**층 1 — 지시·계약.** 모든 agent/node prompt에 금지 필드, test 금지, truth namespace, fixed budget, 실패 보고, kill 조건, 원본 READ-ONLY, xlsx 의무를 넣는다. “점수를 최대화하라”가 아니라 “계약 안에서 private metric을 개선하라”로 쓴다.

**층 2 — 하드 가드.** world-IR `26/26`, CRS 역투영 오차 `0.0`, gen2 exact ledger, verifier, family split, name/id allowlist, label shuffle, zero/all sentinel, hidden mutation, test ACL/access counter를 실행 전후 검사한다.〔M:E0,E3,E4,E10〕 의심 출력은 자동 채택하지 않고 clean evaluator로 재생한다. verifier가 현재 layer metadata를 쓰므로 name-blind reward arm은 X1의 별도 soundness가 없으면 열지 않는다.〔M:E4,A11〕

**층 3 — 통계 격리.** seed·drawing family·style·truth source별 분포를 보존하고 pooled 평균 하나로 접지 않는다. peer 대비 improvement/runtime/calibration의 MAD-based robust-z 절댓값이 `3`을 넘는 node는 “breakthrough”가 아니라 quarantine으로 보낸다.〔P:본 문서〕 reward 상승–hidden semantic 하락, 한 seed만의 승리, shuffle 이상, unrealistically 낮은 compute가 있으면 독립 재계산 전까지 tree의 parent가 될 수 없다. silver `5`판정자는 약 `2`개 어휘 family로 접어야 하며 독립표처럼 더하지 않는다.〔M:E0〕

### 3.6 test 봉인과 양립

RSI의 private는 test가 아니라 val 내부 격리면이다. outer가 몇 번 개선되어도 test access counter는 계속 `0`이다. 방법별 graph/model/calibration/baseline/harness hash와 evidence schema가 동결되고 모든 upstream gate가 PASS일 때만 test job을 한 번 연다. 결과는 tree에 reward로 되먹이지 않는다.〔P:E5,E8〕

test 뒤 defect가 발견되면 점수 band를 이동하거나 같은 method ID로 재실행하지 않는다. 결과를 `INVALID_EVAL_DEFECT` 또는 원 판정으로 보존하고, repair된 evaluator는 새 prereg·새 method/harness version의 별도 거버넌스 대상이 된다. 이것이 AIDE²의 eval repair 정직성과 E2 단발 봉인을 동시에 지키는 유일한 방식이다.

---

## 4. 강주장과 나 자신의 킬 조건

### 강주장 A — “관계가 핵심”은 맞지만 “그러므로 GNN”은 아직 틀린 추론이다

**근거:** 고정 문맥 집계만으로 F1이 `0.517→0.705`로 상승했고, 정션 차수와 평행 갭이 중요도 상위였다. 복잡한 message passing 없이 이미 큰 이득이 났다.〔M:E1〕

**내 주장:** 다음 승자는 GNN일 수도 있지만, GNN의 승리 근거는 아키텍처가 아니라 **B*가 잃은 typed multi-hop 정보의 paired private lift**여야 한다.

**킬:** X5 formal이 `AUPRC_F≥B*+0.05`, CI lower `>0` 및 모든 구조·OOD·calibration gate를 통과하면 “GNN 불필요 가능성이 높다”는 내 사전 회의론은 죽는다. 반대로 X3가 `+0.10`을 내면 GNN을 죽여야 한다.〔P:E5〕

### 강주장 B — 현재 `0.705`의 다음 병목은 precision이 아니라 끊긴 벽의 recall이다

**근거:** 문맥 모델은 `P=0.824`, `R=0.617`이고, 남은 `FN=15,624`가 `FP=5,363`보다 많다. 문맥 추가의 주 이득도 recall이었다.〔M:E1〕

**내 주장:** 다음 wave가 precision-only verifier/postfilter에 집중하면 F1 천장을 잘못 공격한다. typed chains, raster complement, PU grammar coverage가 우선이다.

**킬:** family-disjoint 오류 분석에서 대부분의 손실이 소수 FP family의 고비용 오탐으로 재분류되거나, recall 상승 arm이 calibration·OOD에서 일관되게 무너지면 이 우선순위를 철회한다.

### 강주장 C — verifier-only RL은 현재 의미 학습이 아니라 규칙 복제일 가능성이 더 높다

**근거:** verifier는 label을 읽지 않지만 layer metadata, 평행쌍, 절대 두께, 집합 완전성을 사용한다. 현재 완전한 FAR/FRR 실측은 LINE-only와 제한된 topology family 위에 있다.〔M:E4,A11〕

**내 주장:** X1 전의 GRPO/RLVR은 벽 의미를 배우는 것이 아니라 verifier의 관측 가능한 문법을 최적화할 위험이 크다. full RL보다 verifier soundness와 hidden-family divergence가 먼저다.

**킬:** 전체 다양성·name-blind hidden family에서 FAR/FRR gate를 통과하고, verifier reward 상승이 독립 exact/human val·metamorphic에서 같은 방향을 보이며, Qwen GRPO가 matched SFT를 private gate로 이기면 이 주장은 죽는다.

### 강주장 D — full RL은 기본 계획이 아니라 제거 대상이다

**근거:** 이 과업의 RL 제안은 분류기 자체보다 evidence acquisition/set assembly를 푼다. 이미 고정 router, uncertainty, greedy, beam이라는 더 싼 반증자가 있고 verifier도 아직 최종 자격 전이다.〔M:E8〕

**내 주장:** horizon 학습 `0`인 greedy/beam probe가 먼저이며, multi-step 가치가 없으면 RL의 사망은 실패가 아니라 Occam 성공이다.

**킬:** 같은 비용에서 horizon utility가 bandit 대비 `≥1.05`로 재현되고, 이후 RLVR이 hidden semantic 비열등과 verifier soundness를 유지하며 다시 `≥1.05`를 내면 이 회의론은 죽는다.〔P:E8〕

### 강주장 E — DGX는 포화시켜야 하지만 HPO 복권으로 쓰면 안 된다

**근거:** DGX는 현재 사용률 `0%`이고, full graph SSL·multi-seed formal·raster·Qwen 자산이 모두 대기 중이다. 동시에 AIDE²의 프로그램 교훈은 고정 예산에서 화려한 다수 아이디어가 탈락하고 단순 메커니즘 조합이 이겼다는 것이다.〔M:E0〕

**내 주장:** DGX의 최선 용도는 D1–D5의 **재현 가능한 full-corpus와 matched-arm 비교**이지 무제한 architecture/HPO sweep이 아니다.

**킬:** 동일 GB10-hour에서 제한 HPO가 DAPT/단순 baseline보다 private `ΔAUPRC≥+0.01`, CI lower `>0`를 반복해서 내고 OOD·calibration을 보존하면 search budget을 늘릴 수 있다. 그 전에는 breadth가 아니라 판별력이 우선이다.〔P:본 문서〕

### 강주장 F — raster/Qwen은 주심이 아니라 상보적 증인이다

**근거:** FloorPlanCAD에는 raster와 wall mask가 있지만 native CAD handle truth가 없고, bridge 없이는 pixel mask를 line 의미로 바로 바꿀 수 없다. CRS 계측기는 역투영 오차 `0.0`을 보였지만 실제 mask→candidate projection의 semantic gate는 별도다.〔M:E0,E5,E9,E10〕

**내 주장:** X6/X8은 vector B*를 대체하는 독립 truth가 아니라 ambiguous subset의 recall을 보완할 때만 채택해야 한다.

**킬:** mask-blind candidate 생성, exact bridge, shuffle, cross-domain handle evaluation을 모두 통과한 raster/Qwen arm이 같은 예산에서 B*를 private gate로 이기면 “상보 전용” 제한을 철회하고 주 모델 후보로 승격한다.

---

최종적으로 내가 사고 싶은 것은 더 큰 모델이 아니라 더 강한 반증이다. 다음 wave의 성공은 최고 val 숫자 하나가 아니라, 같은 비용·같은 handle universe·같은 private evaluator에서 살아남은 단순한 메커니즘 조합과, 죽은 가지를 다시 살리지 않는 원장으로 정의해야 한다.

POSITION_COMPLETE: sol
