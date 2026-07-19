# 독립 재검증 판정 — GNN 채택 아크

- 검증 좌석: `sol`
- 기준 패킷: `D:\runs\e2_program\build\PACKET_verify_adoption_arc.md`
- 검증 경계: 지정 repo/cell과 raw cell 산출물은 READ-ONLY. git 명령 및 서브에이전트 사용 없음.
- 판정 원칙: 수치 셀 PASS, `RSI_ADOPT`, full E6 PASS, E7 final resolution을 서로 바꾸어 부르지 않는다.

## 최종 verdict

패킷이 한 묶음으로 제시한 GNN 판정에는 서로 다른 명제가 섞여 있으므로, 잘못된 승격을 피하기 위해 좁은 셀 판정과 채택 판정을 분리했다.

| 판정 대상 | Verdict | 결론 |
|---|---|---|
| `gnn_formal`의 좁은 F-node DEV 수치 셀 PASS | **CONFIRM** | GNN-A의 강한 classical control 대비 ΔAUPRC는 `+0.10067721`, 보고 CI는 `[0.09539842, 0.10600993]`; F-node 구성요소와 cell-pass 수치 조건은 충족한다. |
| 위 결과를 GNN/P3의 `RSI_ADOPT` 또는 최종 채택으로 승격한 판정 | **REFUTE** | parent prereg가 `CELL_PASS ≠ RSI_ADOPT ≠ EFFICIENCY_PASS`를 명시하고, dossier E6/E7의 AND 조건 및 frozen held-out E7가 완료되지 않았다. |
| self-supervised P3/SSL 생존 판정이 아니라 **SSL KILL** 판정 | **CONFIRM** | SSL−no-pretrain ΔAUPRC `-0.00012668`, CI `[-0.00058097, 0.00034416]`; E4 §656의 CI 하한 `<=0` kill 조건을 그대로 충족한다. |
| G9 이후 bandit/RL ladder **KILL** 판정 | **CONFIRM** | sealed primary estimand에서 beam−greedy `+0.00279381`, certified optimum−beam `+0.00155039`, optimum−greedy 합계 `+0.00434419`; 모두 `0.01` 미만이다. |
| E6의 좁은 calibration sub-band (`REL<=0.03 AND RES>=0.03`) PASS | **CONFIRM** | temperature 후 GNN-A 3-seed mean `REL=0.00735972`, `RES=0.08587499`; 전 seed가 각각 두 경계를 통과한다. |
| 이를 full E6/OOD/formal-band PASS로 승격한 판정 | **REFUTE** | 실제 산출물은 스스로 “IID source-category slice, not held-out-style OOD”라고 명시하며 S-node, S-pair, known-relation recall, production p95 envelope, E6 family-bootstrap CI를 제공하지 않는다. |

따라서 현재 합법적 상태는 **`gnn_formal` narrow CELL_PASS + SSL KILL + G9 KILL + E6 calibration sub-band PASS + full E6 INCOMPLETE + E7 NOT RUN**이다. 최종 GNN/P3 채택은 성립하지 않는다.

## 1. 봉인 선행성 및 산출물 동일성

모든 시각은 UTC다. 파일시각만을 외부 공증으로 취급하지 않고, later artifact에 박힌 dual hash, JSON/CSV 구조, 코드의 overwrite 거부, checkpoint/output 순서를 함께 확인했다.

| Cell | 봉인/실행 순서 | hash·구조 확인 | 판정 |
|---|---|---|---|
| `gnn_formal` | prereg 최종 mtime `20:08:01` < preflight `21:03:48` < 첫 checkpoint `21:45:21` < complete `22:36:14` | `prereg.json` `53d10948...bcaca`, `PREREG.csv` `34dfdd6e...ce476`; actual/raw/repo/results/report가 동일. JSON↔CSV의 schema, sealed time, seeds, family crossing, bootstrap, graph hash를 교차 확인. | **CONFIRM (local evidence)** |
| `g9_rl_diag` | superseded seal `00:00:57` → code final mtime `00:02:37` → final seal `00:03:11` → scorer freeze `00:04:17` → complete `00:04:25` | final `prereg.json` `c85c2a13...8c23f`, CSV `c1a94401...0af47`; canonical frozen content hash를 독립 재계산해 `2f3fd80...8476` 일치, CSV 94개 flattened row도 JSON과 전건 일치. superseded→final 차이는 code hash와 seal/hash뿐이며, supersession 전 pack/hidden content read는 각각 `0/0`. | **CONFIRM (local evidence)** |
| `e6_calibration_ood` | prereg JSON/CSV final mtime `00:22:57/00:23:43` < code mtime `00:56:55` < preflight `01:01:42` < complete `01:04:28` | `prereg.json` `7cc94925...6083`, CSV `191fb4ad...928f`; runtime-start files는 두 prereg뿐이고, JSON↔CSV critical structure 및 inherited hashes가 일치. | **CONFIRM (local evidence)** |

추가 연결 검증:

- parent dossier SHA-256 `6641dd63044ad22b94d6c2a61baf85f86ca4c9191745659171e8a806864c294d`와 parent prereg SHA-256 `fc93dad9232cfd877802c1d53996357eccc710daff8cfb2cf7c865bf7f78bcd2`는 cell prereg에 봉인된 값과 현재 파일이 일치한다.
- 세 cell의 repo copy와 `D:\runs\e2_program\cells\<cell>` 공통 파일은 전부 byte-identical이다.
- `gnn_formal`의 12개 checkpoint는 `results.json.models[*].sha256`와 전부 일치하며, E6가 소비한 GNN-A/control checkpoint hash도 같은 값이다.
- 절대적인 제3자 timestamp/notary는 제공되지 않았다. 따라서 위 결론은 “현재 로컬 증거 사슬 안에서의 선행성”이며, 외부 공증 수준의 시간 증명은 아니다.

## 2. 조문 대조

### GNN cell PASS와 채택은 다른 상태다

`reports/e2/prereg_r2_v1.json`은 다음을 동시에 봉인한다.

- `cell_pass`: `ΔAUPRC(DEV) >= +0.01 AND family-paired CI low > 0 AND all guards PASS`
- `gnn_formal_band`: F lift 외에 S-node, S-pair, style-OOD, REL, RES를 함께 요구
- `outer_harness`: val-B non-degradation 및 ADJ 단발 확인을 추가 요구
- `rsi_status_layers`: `CELL_PASS ≠ RSI_ADOPT ≠ EFFICIENCY_PASS`
- `test_policy.wave_test_contact = 0`

`calibration_P3.md` §6은 E6에서 formal band 전부를 rehearsal하고, E7에서 frozen held-out을 한 번 열어 모든 predicate를 AND로 해소하라고 한다(§6.1 lines 594–607, E6 lines 670–678, E7 lines 680–688). 따라서 val-A F-node 숫자 하나를 채택으로 승격하는 해석은 parent contract와 정면 충돌한다.

또한 현재 승자 GNN-A는 `no_pretrain` node-only arm이다. E4 line 656은 SSL이 기여하지 않고 supervised arm만 이기면 **self-supervised P3 실패**로 기록하고 별도 제안으로 재-preregister하라고 명시한다. GNN-A의 수치 성공은 SSL P3를 살리는 근거가 아니며, 별도 supervised-GNN 제안의 가능성만 남긴다.

### G9 band

parent prereg의 RL ladder는 G9 exact/beam gap이 `>=0.01`일 때만 다음 bandit probe로 진행한다. G9 prereg는 primary delta estimand를 “75 hidden drawings의 drawing-level set-F1 차이 평균”으로 봉인했다. 따라서 terminal-objective, verifier acceptance, pooled F1로 사후 metric을 바꾸는 것은 금지된다.

### E6 band

calibration 수식 자체는 dossier 문언과 동일하다: temperature 전후 `REL<=0.03 AND RES>=0.03`, threshold search 금지. 이 좁은 sub-band는 정직하게 통과했다. 그러나 E6 prereg/report가 명시한 IID category slice는 dossier의 held-out style-OOD를 대체하지 못한다. 이는 결과 후 band 이동은 아니지만 parent E6를 해소하지 못하는 **pre-measurement scope contraction**이다.

## 3. `results.json` 독립 재계산

### 3.1 GNN formal

per-seed AUPRC 및 confusion count로 mean/population-SD, precision, recall, F1, ECE-10을 다시 계산했다. 전건 stored 값과 수치 허용오차 내 일치했다.

| Arm | AUPRC mean | SD(pop) | F1 mean | SD(pop) |
|---|---:|---:|---:|---:|
| GNN-A no-pretrain | `0.97475955` | `0.00074004` | `0.86999471` | `0.00311698` |
| GNN-B SSL | `0.97463287` | `0.00065792` | `0.86617804` | `0.00629735` |
| 2-hop HistGBDT control | `0.87408233` | `0.00021342` | `0.76064814` | `0.00083117` |

- 독립 point delta: `0.9747595486 - 0.8740823342 = +0.1006772143`.
- 더 강한 현 control을 B*로 써도 `B*+0.05 = 0.9240823342`; GNN-A margin은 `+0.0506772143`. 약한 `0.8315` B*를 골라 유리하게 만들 필요가 없다.
- stored paired-family CI: `[0.0953984245, 0.1060099263]`, lower `>0`.
- bootstrap RNG seed/family-count로 10,000×198 multinomial count matrix를 재생성했고 SHA-256 `bd9b90a2...2c890`가 stored 값과 일치했다. 다만 GNN 결과에는 prediction vector/replicate delta vector가 없어 CI 값 자체는 `results.json`만으로 fresh 재-bootstrap할 수 없다.
- SSL−A AUPRC point `-0.0001266792`, stored CI `[-0.0005809655, 0.0003441609]`.
- SSL−A F1 point `-0.0038166631`, stored CI `[-0.0053118462, -0.0023534757]`.

E4 kill은 “CI가 0을 포함하면 살린다”가 아니라 CI **하한이 양수여야 생존**한다. 하한이 음수이므로 SSL KILL은 문언 그대로다.

### 3.2 G9

75개 drawing record에서 policy confusion count, pooled F1, drawing-mean F1, verifier acceptance, terminal objective를 전부 다시 합산했다. 이어 family IDs `{F01,F02,F05}`, seed `20260719`로 10,000 bootstrap replicate를 다시 생성했으며 stored replicate vector와 bit-for-bit 동일했다.

| 비교 (sealed drawing-mean set-F1) | Point | 95% family-bootstrap CI |
|---|---:|---:|
| beam64 − greedy | `+0.0027938062` | `[0, 0.0048726467]` |
| certified optimum − beam64 | `+0.0015503876` | `[0, 0.0046511628]` |
| certified optimum − greedy | `+0.0043441938` | `[0, 0.0095238095]` |

- 75/75 drawing에서 B&B optimum이 certified, `max objective_gap=0`, `max remaining_frontier=0`이다. 따라서 `+0.00155039`는 느슨한 미해결 상계가 아니라 이 산출물에서는 certified residual improvement다.
- 합성된 optimum−greedy bootstrap 10,000개 중 `>=0.01` replicate는 `0`; 최대도 `0.0095238095`다.
- `<0.01` 대 `<=0.01` 경계 해석은 결과를 바꾸지 않는다.
- 반례 시도: terminal-objective mean은 beam `0.96589147` 대 greedy `0.93116124`로 차이가 `+0.03473024`라서 이 metric으로 바꾸면 RL이 살아난다. 그러나 이는 sealed primary estimand가 아니며 사후 metric switch다. pooled set-F1 차이 `+0.00313381`도 여전히 `0.01` 미만이다.

### 3.3 E6 calibration

각 seed/state의 10-bin `count`, `mean_probability`, `positive_rate`로 REL/RES/ECE를 원식에서 다시 계산하고 confusion count로 F1을 재계산했다. 전건 stored 값과 일치했다.

| GNN-A state | REL mean | seed range | RES mean | seed range |
|---|---:|---:|---:|---:|
| before temperature | `0.0081902862` | `[0.0074014598, 0.0092013420]` | `0.0842170279` | `[0.0835863309, 0.0846987683]` |
| after temperature | `0.0073597243` | `[0.0062545907, 0.0085582844]` | `0.0858749875` | `[0.0857074817, 0.0861280092]` |

평균으로도, seed별로도 `REL<=0.03 AND RES>=0.03`이다. threshold는 `0.5`, threshold-search count는 `0`; positive scalar temperature 때문에 AUPRC/F1 decision mismatch도 `0`이다.

부가 재계산:

- cal-eval GNN-A mean AUPRC `0.9762654014`; control `0.8778790204`; point lift `+0.0983863810`.
- cal-fit/cal-eval assignment serialization SHA-256을 다시 계산해 `a3f40d2c...a96e` 일치.
- 99/99 family, 교집합 `0`.
- IID category에서 pooled-minus-category AUPRC의 최대 양의 gap은 `0.0024748646`. 그러나 이것은 held-out style-OOD drop이 아니므로 `<=0.10` OOD gate의 증거로 사용할 수 없다.

## 4. 누출·경계 가드

| Surface | val-B | test | family crossing/intersection | 추가 확인 |
|---|---:|---:|---:|---|
| GNN formal | `0` reads | `0` reads | train↔val-A geometry-family collision `0` | identifier/name/layer/text/label feature count `0`; guard probe가 filesystem call 전 차단 |
| G9 | `0` reads | repository-test `0` | reward∩hidden family `[]` 재계산 | hidden content는 scorer freeze 후에만 열림; freeze 후 training update `0` |
| E6 | `0` reads | `0` reads | cal-fit∩cal-eval `0` 재계산 | 두 forbidden probe 모두 path-construction delta `0`, filesystem-read delta `0`; threshold search `0` |

이 카운터는 각 runner가 방출한 감사값이므로 OS-level I/O trace와 동일하지는 않다. 대신 guard 구현, pre-path denial selftest, sealed input/hash, assignment 구조를 함께 대조했다. 제공 증거 안에서 누출 반례는 찾지 못했다.

## 5. 판정을 뒤집기 위한 반례 시도 결과

1. **약한 baseline 선택 의혹:** 기각. `0.8315` 대신 더 강한 fresh 2-hop control `0.87408233`을 사용해도 GNN-A는 `B*+0.05`를 `0.05067721` 초과한다.
2. **SSL이 사실상 동률이므로 살릴 수 있다는 해석:** 기각. E4는 point 동률이 아니라 CI lower `>0`를 요구하며, 실제 lower는 `-0.00058097`이다. F1은 CI 전체가 음수다.
3. **G9 terminal objective/acceptance로 metric 변경:** 기각. 수치는 RL에 유리하지만 sealed primary delta가 drawing set-F1이므로 metric substitution이다.
4. **G9 beam gain과 upper gap을 다른 방식으로 합산:** 기각. 가장 유리한 certified optimum−greedy도 point `0.00434419`, bootstrap max `0.00952381`이다.
5. **E6 mean aggregate가 나쁜 seed를 숨겼다는 해석:** 기각. before/after 모든 seed가 REL/RES band를 개별 통과한다.
6. **IID category를 style-OOD로 간주:** 기각. prereg/report/results가 모두 명시적으로 true OOD가 아니라고 기록한다.
7. **F-node F1 `0.87`을 S-node `0.92` gate 실패로 간주:** 기각. 서로 다른 truth universe/metric이다. 올바른 상태는 S-node/S-pair가 이 cell에서 **미측정**, 즉 full E6 미완료다.
8. **E6 calibration PASS로 E7를 생략:** 기각. parent dossier는 E7 frozen held-out 단발 AND gate를 별도로 요구하며 현재 test contact는 `0`이다.

## 6. 증거 한계

- `gnn_formal/results.json`은 bootstrap count-matrix hash와 summary만 남기고 prediction/replicate delta vector를 남기지 않았다. 따라서 point/confusion/ECE와 sampling matrix는 독립 재계산했지만 GNN CI endpoints는 raw checkpoint replay 없이 완전 독립 재생산하지 못했다.
- G9 `evidence.xlsx`의 actual SHA-256 `3bf3128b...92db`는 results/report와 일치하고 `results.json`상 formula cell 수는 `0`이다. 다만 이 런타임에는 spreadsheet skill이 요구하는 `@oai/artifact-tool` dependency loader가 없어 workbook 내부 range/visual inspection은 BLOCKED였다. 결정 수치는 75 drawing JSON과 10,000 raw replicate vector에서 독립 재계산했으므로 G9 verdict에는 영향이 없다.
- 위 두 한계는 narrow numeric CONFIRM의 독립성 수준을 제한하지만, **최종 채택 REFUTE**는 parent AND-contract의 미완료만으로도 성립한다.

## 증거 위치

- `D:\dev\99_tools\autocad-sdk-router\reports\e2\prereg_r2_v1.json`
- `D:\dev\99_tools\autocad-sdk-router\reports\e2\dossiers\calibration_P3.md` §6
- `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\gnn_formal\{prereg.json,PREREG.csv,REPORT.md,results.json}`
- `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\g9_rl_diag\{prereg.json,PREREG.csv,REPORT.md,results.json}`
- `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\e6_calibration_ood\{prereg.json,PREREG.csv,REPORT.md,results.json}`
- raw mirrors/checkpoints/evidence: `D:\runs\e2_program\cells\<동명>\`

**FINAL: GNN/P3 ADOPTION REFUTED; SSL KILL CONFIRMED; G9 KILL CONFIRMED; E6 CALIBRATION SUB-BAND CONFIRMED; FULL E6/E7 RESOLUTION NOT ESTABLISHED.**
