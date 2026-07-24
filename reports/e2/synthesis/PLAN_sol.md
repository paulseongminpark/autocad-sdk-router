# E2 벽 의미 탐지기 통합 실험 프로그램 계획 — sol

## 0. 종합 상태와 불변 계약

- 읽은 입력: 지정된 26개 원문 도시에 전부. `CELLS_INDEX.md`와 `manifest.json`은 26부에 포함하지 않았다.
- 읽지 않은 도시에: **없음**.
- 아래 수치는 패킷의 고정 사실 또는 각 도시에가 제안한 프리레지스트레이션·예산값이다. 새 측정이나 새 PASS를 주장하지 않는다.
- 현재 기준점은 기하 탐지기 v1 CubiCasa val `F1 0.2358 / P 0.134 / R 0.981`, HistGBDT 6특징 val `F1 0.517 / AUC 0.9215 / P 0.860 / R 0.370`, 셔플 `AUC 0.375 PASS`다.
- 데이터 계약은 CubiCasa5k SEG-IR `train 386만 / val 35.4만 / test 37.5만` 선분, 레이어 중립, `wall_frac ~11.8%`; FloorPlanCAD `5,308` raster+wall mask; `1.dwg` `384 defs`, `B3 zero_frac 0.2135`; 현 S/F/M 합성팩 `B1 FAIL`이다.
- 자원 계약은 RTX 5070 Ti 16GB, RAM 64GB, DGX Spark 승인·현재 unreachable, 프런티어 API 미결재다.
- 모든 방법은 `val=개발`, `test=방법당 단발`, threshold·seed·split·artifact 사전 봉인, 셔플 대조군, per-handle evidence xlsx를 공유한다. test metric을 본 뒤 재실행·재튜닝하지 않는다.

표기: `C`=CubiCasa 벡터, `F`=FloorPlanCAD 래스터, `R`=`1.dwg` 실도면, `S`=자격을 통과한 합성, `M`=metamorphic. 현 합성팩은 `S*`로 표기하며 F02를 통과하기 전에는 engineering fixture일 뿐 confirmatory truth가 아니다. 자원 트랙은 각 셀의 **주 트랙**이며, 보조 전처리는 설명에 병기한다.

밴드는 총순위가 아니다.

- **TOP**: 즉시 착수할 공용 계측기·가장 싼 판별·최종 거버넌스.
- **VIABLE**: 명시된 선행 게이트가 닫힌 뒤 발사할 조건부 셀.
- **PARKED**: 전제 붕괴, DGX 불통, API 미결재, 또는 더 싼 판별 미완료 때문에 계산을 쓰지 않을 셀.

## 1. 통합 셀 매트릭스

### 1.1 공용 기반·거버넌스

| 셀 ID | 밴드 | 출처 제안(전부) | 가설 | 방법 요약 | 데이터 축 | 주 자원 트랙 | 지표 | 제안 합격선 | 킬 조건 | 예산 추정 | 선행 의존성 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F00 CONTRACT-FREEZE | TOP | `calibration_P1` C0; `calibration_P2` C0; `calibration_P3` E0; `calibration_P4` P4-0; `doe_P1` Phase 0; `doe_P3` 공통 규칙; `feyerabend_P5` P5-00; `platt_P1` G0; `platt_P2` G0; `platt_P5` G0 | 권리·lineage·split·baseline·evaluator를 먼저 봉인하면 후속 lift가 누수나 표본 교체가 아닌 방법 효과로 귀속된다. | 자산 해시, family/project split, val/test ACL, baseline replay, metric schema, shuffle 및 xlsx writer를 한 immutable run contract로 만든다. | C/F/R/S/M | CPU-PAR | 권리 상태, split overlap, baseline parity, test ledger, forbidden-field canary, xlsx completeness | 권리 필요한 축은 서면 허용; group overlap 0; baseline·resolver 재현; test ledger empty; 셔플·증거 스키마 준비 | 권리 미해결 축 사용, test 선열람, handle/path/vendor leakage, baseline 불재현이면 해당 run 무효 | 로컬 CPU 수시간(`calibration_P1` C0); API/GPU 0 | 없음 |
| F01 E1-HANDLE-FORENSICS | TOP | `platt_P0` C0–C6 | E1 top-20 현상이 실제 handle-space 의미 실패인지 선택·bbox·INSERT·단위 artifact인지 먼저 판별할 수 있다. | 선택 lineage 재생, handle 실재/ownership, entity/INSERT 구조, bbox·unit, block token, `n_h_ornith` 원시 계보를 한 결정 lattice로 감사한다. | R + E1 원시 산출 | CPU-PAR | selection hash, `O-A/O-B`, `r_pair`, unit factor, token association, artifact lower bound | 원문 분기: `O-A≥0.50`, `O-B≤0.10`, `r_pair>0.50`; unit factor `≥10`이 `≥30%`; `n_h_ornith=10` artifact lower `≥50%`는 각기 독립 판결 | lineage 재현 실패나 handle universe 불일치면 고가 셀 전체 정지; 서로 다른 원인을 평균내지 않음 | 실행 CPU `<1시간`, 단일 진입 스크립트 반나절, GPU/LLM 0 | F00 |
| F02 WALL-GENERATOR-QUAL | TOP | `calibration_P1` C1; `calibration_P2` C1; `calibration_P3` E0; `feyerabend_P1` E0; `feyerabend_P2` C0; `feyerabend_P3` C1; `platt_P1` G2; `platt_P3` C0; `platt_P4` E0 | correct-by-construction wall/negative/divergent 생성기와 fidelity 자격이 있어야 합성 truth, verifier reward, hidden family 판정이 유효하다. | primitive·INSERT·gap·overshoot·distractor family, exact handle truth, negative prevalence, sentinel, frozen train/hidden generator를 만든다. 각 소비자는 모순 원장의 자기 gate를 적용한다. | S/R 진단 | CPU-PAR | truth round-trip, family coverage, negative prevalence, KS/TV, sentinel, hidden-family separation | exact truth 일치와 required family coverage 100%; fidelity는 C01에서 보존한 소비자별 gate를 각각 충족해야 함 | 벽 생성 코드 부재, negative 0, truth round-trip 실패, B1 미달, hidden을 보며 generator fitting | 구현 `1–2인주`+검증 수시간(`calibration_P1` C1); face-generator 제안 `2–3인일` | F00; F01이 확정한 artifact strata |
| F03 CANONICAL-WORLD-IR | TOP | `calibration_P1` C3; `feyerabend_P6` P6-C0–C6; `platt_P1` G1/E0/E1/E2/E4; `feyerabend_P5` P5-01 | world-coordinate INSERT 전개, curve/polyline segment provenance, unit abstention을 고치면 zero-pair가 단순 parser/표현 누락인지 분리된다. | nested transform oracle, handle-only rename parity, folded/unfolded split-wall, canonical lineage, no-INSERT identity, downstream non-regression을 구현한다. | C/R/S/M | CPU-PAR | transform deviation, lineage mismatch, candidate recall, split-wall P/R, name parity, no-INSERT identity | exact transform 일치; split-wall folded recall `≤0.20`, unfolded recall `≥0.90`, precision `≥0.90`; zero-wall sentinel; no-INSERT byte/decision identity | unresolved transform, arbitrary-mm coercion, name dependence, unfolded candidate가 없거나 phantom 생성, quadratic materialization | microcells `10분–8시간`; 전체 제안 `6–10 engineer-days`, RAM gates는 원문별 유지 | F00; F02 fixture schema |
| F04 COMMON-METAMORPHIC-JUDGE | TOP | `calibration_P1` C7; `calibration_P2` C6; `calibration_P3` E6; `calibration_P4` P4-5; `doe_P5` 자격/Q0–Q2/F01–F28/confirmation; `feyerabend_P1` E2; `feyerabend_P2` C3; `feyerabend_P5` P5-06; `feyerabend_P7` E3; `platt_P1` E7; `platt_P2` C7; `platt_P3` C1–C5 | sound relation과 sentinel을 공용 judge로 만들면 empty predictor와 transform shortcut을 모든 방법에서 같은 방식으로 죽일 수 있다. | relation registry, identity/oracle, clean/mutant conviction, handle mapping certificate, seven-transform×method-family runner, failure witness를 공유한다. | C/R/S/M; F는 bridge 후 | CPU-PAR | oracle violation, mutant conviction, mapping collision, flip/R-META/relation violation, sentinel recall/FP, coverage | clean oracle 0 위반; mutant conviction `≥95%`; mapping collision 0; 각 방법의 gate는 C11처럼 별도 유지 | relation 자체가 unsound, clean fixture 위반, mutant를 못 죽임, empty/all predictor가 sentinel 통과, mapping ambiguity 은폐 | cheapest `1일`; 전체 battery `7–10개발일`; GPU adapter는 artifact 준비 뒤 별도 | F02; F03; R50 for raster |
| F05 SCALE-RESOURCE-GATE | TOP | `calibration_P1` C8; `calibration_P2` C6; `calibration_P3` E1/E6; `feyerabend_P6` P6-C5; `platt_P1` E6; `platt_P2` C7 | 작은 샘플 성능과 최대 definition 운용 가능성을 분리 계측하면 O(n²) 또는 메모리 숨김을 조기에 죽일 수 있다. | shard/streaming, candidate-cap audit, cache equivalence, max-def stress, p95/RSS/VRAM ledger를 method-specific envelope로 실행한다. | R 최대 def + C/S stress | CPU-PAR | edge/entity slope, candidate count, p95, timeout, RSS/RAM/VRAM, shard parity | P1 `p95≤60초/도면`, RAM `≤32GB`; P6 stress 각 단계 timeout `2시간`, RAM `48 GiB`; GNN RAM `≤48GB` 등 원문별 gate를 각각 적용 | quadratic slope, silent drawing drop, cap이 recall을 훼손, shard parity 실패, watchdog abort | P1 CPU `1–2일`; P6 stress 총 `8시간`; GNN/Raster profile은 해당 queue에 포함 | F03; G40 for graph methods |
| F06 FROZEN-TEST-ONCE | TOP | `calibration_P1` C9; `calibration_P2` C7; `calibration_P3` E7; `calibration_P4` P4-6; `calibration_P6` E; `doe_P1` confirmation; `doe_P2` C6; `doe_P3` confirmation; `doe_P4` confirmation; `doe_P5` confirmation; `doe_P6` confirmation; `feyerabend_P1` E6; `feyerabend_P3` C6; `feyerabend_P5` P5-08; `feyerabend_P6` P6-C7; `feyerabend_P7` E5; `platt_P1` E8; `platt_P2` T1; `platt_P3` C6; `platt_P4` E5; `platt_P5` V6 | 살아남은 각 방법을 봉인 artifact로 한 번만 열면 선택 편향 없는 최종 판결을 얻는다. | method별 prereg SHA, threshold, resolver, split, dependency report를 검증하고 test inference·xlsx 생성 후 ACL을 다시 닫는다. | method별 C test; 권리·truth가 있는 외부축만 | TEST-ONCE | 각 method의 prereg primary metric, CI, sentinel/meta, runtime, complete xlsx | 모든 upstream AND gate와 독립 resolver 통과; 방법당 test 1회; 추가 tuning 0 | metric을 본 뒤 재실행, 누락 row/실패 run 은폐, method별 gate 교체 | method당 inference batch 1회; 재학습 0 | 해당 method 전 셀; F00; F04; F05 |

### 1.2 결정론·truth·고전 ML

| 셀 ID | 밴드 | 출처 제안(전부) | 가설 | 방법 요약 | 데이터 축 | 주 자원 트랙 | 지표 | 제안 합격선 | 킬 조건 | 예산 추정 | 선행 의존성 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D10 RELATIVE-UNIT-A/B | TOP | `calibration_P1` C3; `calibration_P2` C4/C6; `doe_P2` C0; `feyerabend_P2` C1–C5; `platt_P1` E4 | absolute gap 실패가 unit convention 때문이면 dimension-anchored/drawing-relative 표현은 scale-paired 후보 우주를 보존한다. | anchor confidence를 label 없이 동결하고 absolute 대 relative predicate만 바꾼 4-scale paired A/B와 DIM-rich real probe를 먼저 수행한다. | S/R; C는 no-anchor identity | CPU-PAR | anchor accuracy/coverage, scale-wise pair F1, mapped Jaccard, real paired delta, permutation identity | HIGH anchor `≥95%` within `5%`, coverage `≥0.60`; relative F1 `≥0.85` at all four scales; Jaccard `≥0.95`; real `N_R-N_A>0`, Pearson delta `≥+0.05`, bootstrap lower `>0` | 어느 scale이든 relative F1 `<0.85`, label/name dependence, no-anchor가 baseline과 다름; real kill은 synthetic 지지와 평균내지 않음 | 로컬 CPU `<1일`: 제안 분배 `2h+2h+1h+4h+1h` | F00; F02; F03 |
| D11 DETERMINISTIC-LATTICE-PROBE | TOP | `calibration_P1` C2/C4; `platt_P1` E0/E1 | 다증거 lattice가 v0 recall을 유지하면서 false merge·metamorphic flip을 줄일 수 있다. | 같은 후보 우주에서 v0, offset-only, topology/face/opening/hatch/lineage 채널을 paired 비교하고 name/layer masked arm을 둔다. | S/R top-20; C dev; F는 보조만 | CPU-PAR | candidate recall, handle F1, false merge, flip, edge/entity, channel ablation | S candidate recall `≥0.98`, false merge `≤0.05`, probe F1 비열화 없음, flip kill band `0.02` 이하 | hidden S F1 `<0.85`, false merge `>0.05`, flip `>0.02`, layer/source hard oracle만 이득, quadratic edges | cheapest `≤1일`; channel batch `1–2일` | F01; F02; F03; F04 |
| D12 RESOLVER-MATCH-ILP-CAL | TOP | `calibration_P1` C5/C6; `platt_P1` E2/E3 | calibrated evidence와 capped global resolver가 greedy/matching보다 충돌 component를 잘 풀고 정보 해상도를 보존한다. | greedy, maximum-weight matching, small-component ILP, capped hybrid를 비교하고 Platt/isotonic/조건부 beta calibration을 family-held-out에서 봉인한다. | S/C val; F exact contract 후 | CPU-PAR | F1, false merge, objective/timeout, AUPRC, Brier, REL/RES, precision at coverage | ILP/hybrid non-inferior and local envelope; `REL≤0.03`, `RES≥0.02`, `AUPRC−v0≥0.15`, `precision≥0.90` at `coverage≥0.50` | ILP 이득 0/대부분 cap 초과/timeout incumbent 의존; calibration leakage 또는 constant-probability collapse | solver `1일`; calibration 수시간 | D11; F05; T20-qualified truth |
| D13 TAGUCHI-ROBUST-KNOBS | VIABLE | `doe_P2` C0–C6 | 선택된 unit representation 안에서 angle/gap/overlap/fan-out 주효과를 싸게 강건화할 수 있다. | v1 reference를 별도 캐시하고 L9×5 probe, L9×40 outer-noise 평가, collapse gate, 활성 두 요인 3×3, hold-out firm을 순서대로 실행한다. | R/M/S; 선택적으로 C | CPU-PAR | R-META, sentinel/recall, robust row, S/N·variance, hold-out transfer | aggregate·hold-out `R-META≤0.02`; `0.02–0.10` INCONCLUSIVE; hold-out `>0.10` kill; sentinel/recall hard gate | D10 미완, rad/mm 불명, firm split 불가, all-grid plateau 또는 compute abort 반복 | probe 목표 `30분`; main `9×40=360` deterministic evaluations; GPU/DGX 0 | D10이 representation을 선택·봉인; F03/F04 |
| D14 FACE-POCHE-BRIDGE | VIABLE | `feyerabend_P1` E1–E5; `feyerabend_P5`의 region-proposal 인접 설계 | wall-pair 중심이 놓치는 face/ribbon/poché 구조가 zero-pair/divergent에서 별도 회수 신호를 제공한다. | planar face/ribbon 후보, rigid bridge, messy top-20, CubiCasa face feature, F raster exploratory transfer를 단계화한다. | S/R/C; F는 탐구 | CPU-PAR | ribbon recall/IoU, transform Jaccard, top-20 containment, HGB face lift, zero-candidate conditional precision | S ribbon recall `≥0.90`; bridge Jaccard `1.0`, ribbon IoU `≥0.99`; real containment median `≥0.40`; HGB lift `≥0.03` 또는 conditional precision `≥0.50` | containment `<0.15`, bridge 비용 `>10×`, no-face sentinel/phantom, 이득이 이름/합성 tell에만 존재 | generator `2–4h`+`2–3인일`; cheap S `≤1h`; real hard cap `8h` | F02; F03; F04; F01 strata |
| T20 TRUTH-SOURCE-CROSS | TOP | `calibration_P2` C6; `calibration_P3` E5/E6; `doe_P3` 24-cell matrix; `feyerabend_P1` E4; `feyerabend_P3` C3–C5; `feyerabend_P5` P5-05; `feyerabend_P7` E2/E4; `platt_P1` E7; `platt_P2` C5; `platt_P3` C7; `platt_P5` V3 | SYN/EXT/SILVER/META가 같은 오류를 공유하는지 off-diagonal로 보면 proxy를 독립 truth로 잘못 합산하지 않을 수 있다. | 동일 IR·동일 threshold에서 train truth `{SYN,EXT,SILVER}` × eval `{SYN,EXT,SILVER,META}` × deterministic/learned를 paired same-item로 기록하고 normalized Brier skill을 쓴다. | S/F/C/R/M; silver는 자격 시 | CPU-PAR | diagonal response, off-diagonal Drop, normalized Brier skill, disagreement/error correlation, chain closure | off-diagonal `Drop≤0.20`; chain closure는 CI upper `≤0.20`; source qualification·shuffle·CRS gates 모두 AND | source 미자격, split overlap, eval-source별 retune, same proxy family를 독립 표로 합산 | 셀별 scoring `1 CPU-hour`, 30 drawings; fit 비용은 공유하고 중복 청구 금지 | F00; F02; F04; R50; R53 admission for silver |
| T21 ANTI-SILVER-ABLATION | VIABLE | `calibration_P5` P5-E; `feyerabend_P3` C0–C6; `platt_P2` C6 | gate-only 학습이 silver distillation과 동등하거나 우월하면 현재 silver shortcut을 학습 truth로 쓸 이유가 없다. | byte-identical firewall, same init·same handles의 gate-only 대 silver-distill, source ablation, CubiCasa/real conflict, frozen final을 실행한다. | S/C/R; silver | GPU-LOCAL-SERIAL | meta advantage, S F1, CubiCasa val, real meta, detector/silver Pearson, firewall hash | gate-only meta advantage `≥0.10`, S non-inferiority `−0.02`; final S F1 `≥0.80`, meta `≥0.90`, CubiCasa `≥0.517`; Pearson `≤0.35`는 독립성 보조이지 단독 PASS 아님 | firewall byte mismatch, 현 B1/sentinel 미자격, silver가 gate를 읽음, human/off-diagonal 이득 없음 | cheapest local RTX 반나절; full은 야간 단위 | F02; F04; F00; eligible silver only |
| M30 CLASSICAL-OCCAM-LADDER | TOP | `calibration_P2` C3; `calibration_P3` E3; `feyerabend_P1` E4; `platt_P2` C1 | frozen HGB/logistic/graph-stat classical model이 충분하면 GNN·RL보다 싸고 해석 가능한 주 경로다. | v1과 고정 HistGBDT를 replay하고 geometry/topology/face/graph-stat feature를 동일 split에서 단계적으로 추가하며 shuffle·name mask를 건다. | C val; S/F qualified; R diagnostic | CPU-PAR | per-handle P/R/F1/AUPRC, seed variance, calibration, error taxonomy, shuffle | 기존 HGB `F1 0.517/AUC 0.9215`를 기준으로 graph-stat classical이 frozen deterministic 대비 `+0.10`이면 GNN을 정지하는 Occam gate; shuffle는 별도 PASS 필요 | improvement가 ID/name 누수, source-specific shortcut, unstable seeds에만 존재 | CPU `1일` classical gate; cached feature 재사용 | F00; F03; T20 |
| M31 PU-ANCHOR-LF | VIABLE | `calibration_P2` C1/C2 | 반복·face·transform-stable LF의 P/N/U anchor가 label scarcity에서 식별 가능한 weak supervision을 만든다. | 500 S와 조건부 F probe, correlated LF family folding, positive/negative anchors, LF dependence·coverage 감사를 수행한다. | S/C; F exact contract 후 | CPU-PAR | LF coverage/conflict, anchor purity, S AUPRC, precision at recall, F diagnostic | 합성 fidelity PASS; F exact가 있을 때만 F metric; grammar recall `≥0.60` 등 원문 Cell 1/2 gate | raster mask를 exact handle truth로 승격해야만 성립, token-only anchor, LF family 중복 투표 | C1 `1 CPU-day`; C2 `0.5 CPU-day`, RAM `≤32GB` | F02; F00; R50 for F |
| M32 PU-MODEL-CAL-FINAL | VIABLE | `calibration_P2` C3–C8; `calibration_P5` P5-F | classical→PU→self-training 사다리와 repeat/face/transform ablation이 exact-label 없이도 안정적 lift를 낼 수 있다. | shared feature cache로 model ladder, ablation, leave-style-out calibration, meta/sentinel/proxy audit, shuffle, frozen final을 실행한다. | S/C/R; F exact contract 후; qualified silver feature optional | CPU-PAR | AUPRC/F1, precision at recall, OOD drop, REL/RES, CI, ablation, shuffle | F lift `≥0.05`, S lift `≥0.03`, precision `≥0.92` at recall `0.50`, OOD drop `≤0.10`, `REL≤0.03`, `RES≥0.02`, CI low `>0` | token/layer 제거 시 붕괴, scale/metamorphic/sentinel fail, shuffled LF가 유지, test 재시도 | cached model `1–2 CPU-days`; ablation `1일`; calibration `0.5–1일`; final `1일` | M31; M30; F04; T20 |

### 1.3 그래프·래스터/VLM

| 셀 ID | 밴드 | 출처 제안(전부) | 가설 | 방법 요약 | 데이터 축 | 주 자원 트랙 | 지표 | 제안 합격선 | 킬 조건 | 예산 추정 | 선행 의존성 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| G40 GRAPH-ADJACENCY-AUDIT | TOP | `calibration_P3` E1; `platt_P2` P2-G1; `feyerabend_P6` world-expansion prerequisite | 완전하고 name-independent한 adjacency만이 GNN 효과를 해석 가능하게 한다. | exhaustive small-reference, cap truncation, transform/name parity, unresolved reference, large-def shard 감사를 수행한다. | S/C/R | CPU-PAR | per-relation/micro recall, cap truncation, build hash, rename/transform parity, RAM | 모순 원장 C02대로 calibration 경로 `≥0.98`, platt 경로 `≥0.995`; shared builder가 양쪽 자격을 모두 얻으려면 `≥0.995` | 해당 gate 미달, cap을 풀어야만 recall 확보, unresolved required ref, shard가 truth context를 잃음 | CPU `1일`, RAM 64GB 안; GPU 0 | F03; F05 fixture |
| G41 CHEAP-GRAPHSAGE | VIABLE | `calibration_P3` E2/E3; `platt_P2` C2–C4 | classical ladder가 남긴 문맥 잔차를 small GNN이 name leakage 없이 회수할 수 있다. | 3-layer/local GraphSAGE, raw/graph-stat baselines, context and name-mask ablation을 동일 graph artifact에서 실행한다. | C/S; F exact bridge 후 | GPU-LOCAL-SERIAL | AUPRC/F1 lift, context delta, name-mask delta, seed stability, OOD/meta | platt main lift `≥+0.10`; context CI lower `>0`; name contribution `<0.05`; calibration path S node `≥0.92`, S pair `≥0.80`는 해당 head에 적용 | M30이 Occam gate를 닫으면 불필요; lift `<0`, seed 방향 불일치, 18 GPU-hour cap 초과, adjacency 미자격 | RTX 최대 `18 GPU-hours`; context `12`, mask `6` GPU-hours는 생존 시 직렬 | G40; M30; F04; T20 |
| G42 SSL-GNN-FULL | PARKED | `calibration_P3` E4–E6; `platt_P2` C5–C7 | SSL과 multi-source joint training이 cheap GNN보다 OOD·calibration을 추가 개선할 수 있다. | masked/contrastive ablation, limited HPO, S node/pair joint head, F/C transfer, multi-seed rehearsal을 수행한다. | S/C/F/R/M | DGX-QUEUE | AUPRC lift, S node/pair F1, OOD drop, REL/RES, CI, RAM | `AUPRC_F≥B*+0.05`, S node `≥0.92`, S pair `≥0.80`, OOD drop `≤0.10`, `REL≤0.03`, `RES≥0.03`, CI low `>0`, RAM `≤48GB` | DGX 불통, G41/M30 무이득, source qualification 실패, transductive held-out geometry leakage | full HPO 수 GPU-day; DGX unreachable이면 BLOCKED, local small run만 진단 | G41; T20; F02; R50; DGX reachable |
| R50 RASTER-RIGHTS-BRIDGE | TOP | `calibration_P4` P4-0/P4-1; `calibration_P5` projection prerequisite; `doe_P6` preflight; `feyerabend_P1` E2; `feyerabend_P5` P5-00/P5-01; `platt_P5` G0/V1 | pixel evidence가 의미 있으려면 권리와 pixel↔original-handle CRS bridge가 모델보다 먼저 정확해야 한다. | counsel gate, renderer/crop/affine/INSERT provenance, oracle mask, unique-color handle render, ambiguity/coverage record를 만든다. | S/C/R; F는 mask 학습만 | CPU-PAR | round-trip Jaccard/F1, phantom/miss, map accuracy, collision, coverage, provenance hash | exact fixture Jaccard `1.0`, phantom 0, miss 0; P4 MAPACC `≥0.995`, error `≤0.5%`; platt oracle bridge F1 `≥0.6` 목표, `<0.4` common kill | counsel 미해결 상태의 F 실행/파생물, affine ambiguity, oracle F1 `<0.4`, mask를 먼저 보고 line candidate 생성 | CPU `1일`; renderer/provenance implementation `2–3개발일`; API 0 | F00; F03; F02 fixtures |
| R51 LOCAL-RASTER-SEGMENTER | VIABLE | `calibration_P4` P4-2/P4-3; `feyerabend_P5` P5-02/P5-03; `platt_P5` V2 | FloorPlanCAD mask로 배운 small segmenter가 vector rule이 보지 못한 pixel context를 제안 신호로 낼 수 있다. | frozen pretrain probe, F mask training, CubiCasa render representation screen을 small backbone과 three-seed 제한 탐색으로 수행한다. | F train/holdout; S/C diagnostic | GPU-LOCAL-SERIAL | pixel IoU, raster robustness, candidate lift, shuffle, sentinel | source별 gate 유지: FPC IoU `≥0.60`(feyerabend) 또는 `≥0.70`(platt track); 200-block positive lift; shuffle/sentinel PASS | rights/lineage fail, R50 fail, all prereg strata lift `≤0`, checkpoint fishing, NC artifact의 제품 혼입 | RTX local: probe `≤1일`; 5b 제한 탐색 `2–3 GPU일` | R50; F00; GPU queue slot |
| R52 RASTER-VECTOR-COMPLEMENT | VIABLE | `calibration_P4` P4-4/P4-5; `feyerabend_P1` E5; `feyerabend_P5` P5-04–P5-09; `platt_P3` C6; `platt_P5` V3/V5/V6 | raster proposal이 deterministic/GBDT가 놓친 original handles를 같은 vector gate 아래에서 비상관적으로 회수할 수 있다. | inverse-map, fixed top-20, CL-B/GBDT/raster union, style/meta, same-definition disagreement, real operational, product isolation과 one-shot transfer를 실행한다. | C/F/R/S/M | GPU-LOCAL-SERIAL | handle F1, Recall@20, unique TP/FP, union P/R, AUPRC lift, style drop, error correlation, relation violation | feyerabend: v0 대비 recall delta `≥0.25`, CL-B paired lower `>0`, precision 비열화 없이 recall lower `>0`; platt end-to-end handle F1 `≥0.60`; calibration styles each AUPRC lift `≥0.08`, overall NI lower `≥−0.02`, style drop `≤0.10` | unmatched mask를 wall로 승인, CL-B/GBDT unique lift 0, mapping/meta fail, raster error가 vector와 완전 중복, NC product leak | bridge/error analysis `1–2일`; local inference/eval `1일`; 재학습은 R51 예산에만 | R51; D12/CL-B frozen; F04; T20 |
| R53 FRONTIER-VLM-JURY | PARKED | `calibration_P5` P5-A/B/C; `doe_P6` cheapest+frontier 6 cells; `platt_P5` V4/V5 | 승인된 frontier VLM이 strict schema와 abstention 아래에서 vector families와 다른 한 표를 제공할 수 있다. | 먼저 E1.5 admission 재산출, 그 뒤 name-blind crop screen, family-aware consensus, JURY-META를 수행한다. VLM은 truth/resolver가 아니다. | S/F/C/R images; qualified truth로만 평가 | FRONTIER-API | B1/B4, parse/hallucination, handle Jaccard, coverage, resolved disagreements, Δκ, metamorphic | admission `B1≥0.70 AND B4 Pearson≥0.70`; calibration probe HallRate `≤0.01`, Jaccard `≥0.50`; platt value `≥6/20` strict resolutions 또는 `Δκ>0` with α `0.05` | API 미결재, B1/B4 중 하나 미달, R50 fail, correlated-family 중복 투표, schema/hallucination/sentinel fail | admission CPU `<2h`, API 0; 승인 시 대안 envelope는 `20` valid responses/`1일` 또는 `150 calls`—합산 금지 | F01; F00; R50; API approval; admission result |
| R54 LOCAL-OPEN-VISION-NO-SILVER | VIABLE | `doe_P6` open-finetune 6 cells; `platt_P5` V2/V3의 open local branch | silver 없이 사람 mask/exact truth로 학습한 open model이 raster/vector modality 차이를 공정하게 시험할 수 있다. | raster-only/vector-only/both modality의 local LoRA/segmentation screen을 동일 bridge·split·budget에서 수행하고 frontier 결과와 분리한다. | F/C/S qualified | GPU-LOCAL-SERIAL | val F1/AUPRC, handle F1, R-SYN/R-META, modality interaction, shuffle | DOE gate: val F1이 GBDT `0.517` 이상 또는 robust v0보다 R-SYN과 R-META 모두 우세; bridge/sentinel AND | R50 fail, rights fail, silver를 몰래 학습 label로 사용, local signal 없음, full factorial을 DGX 없이 강행 | 셀당 LoRA 1 epoch `0.5–2일`; subsample first | R50; F02/F04; M30; GPU queue |
| R55 SILVER-STUDENT-EXPANSION | PARKED | `calibration_P5` P5-D/E/F/G | 자격 있는 jury silver만 제한 evidence로 쓰면 local 3B student/weak feature가 독립 truth 평가에서 lift를 낼 수 있다. | student LoRA, anti-silver control, P2/P3 weak-feature injection, 생존 시 DGX full FT를 별도 단계로 둔다. | qualified silver + S/F independent eval | DGX-QUEUE | AUPRC lift, REL/RES, CI, anti-silver delta, weak-feature lift | admission B1∧B4 후 student AUPRC lift `≥0.03`, `REL≤0.04`, `RES≥0.02`, CI low `>0`; final truth는 S/F resolver뿐 | admission 미달/미측정, silver가 resolver가 됨, anti-silver에서 이득 소멸, DGX 불통 상태의 full claim | local probe RTX `1–2일`; DGX full은 reachable 후 예약 야간 | R53 admission only; T21; R50; DGX reachable for full |

### 1.4 획득·집합 조립·관례·확장 DOE

| 셀 ID | 밴드 | 출처 제안(전부) | 가설 | 방법 요약 | 데이터 축 | 주 자원 트랙 | 지표 | 제안 합격선 | 킬 조건 | 예산 추정 | 선행 의존성 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A60 VERIFIER-REWARD-SOUNDNESS | TOP | `calibration_P6` Cell-0/A; `doe_P4` verifier/hacking gates; `feyerabend_P4` V1/H; `platt_P4` E0/E4 | RL/bandit 결과보다 먼저 verifier false accept와 reward/hidden-family 분리를 검증하면 reward hacking을 실제 lift와 구분한다. | adversarial wrong-set, reward-family/hidden-family firewall, exact/meta/sentinel reward, no-LLM-judge assertion, hacking signature를 봉인한다. | S/M; C held-out | CPU-PAR | FAR/FRR, family overlap, reward-vs-held-out divergence, sentinel, verifier hash | FAR `≤0.01`; calibration verifier FRR `≤0.05`; reward family와 hidden family 분리 | FAR 초과, current B1-fail S를 reward로 사용, silver/LLM judge reward, reward 상승·held-out 하락 | CPU `1일` after F02; family audit `0.5일`; GPU 0 | F02; F04; F00 |
| A61 FIXED-ROUTING-BANDIT | VIABLE | `calibration_P6` B; `doe_P4` cheapest active cells; `feyerabend_P4` S0/B1/B1-shuf/X; `platt_P4` E6 | full scan 대신 fixed policy/offline contextual bandit이 품질을 거의 유지하며 evidence acquisition 비용을 줄일 수 있다. | FULL_SCAN, static/greedy/random, offline bandit, shuffled logs를 same frozen classifier와 action-cost ledger에서 비교한다. | R/C/S qualified | CPU-PAR | compute/cost saving, F1/AUPRC drop, utility, regret, shuffle, Pareto | calibration: saving `≥20%` and AUPRC drop `≤0.01`; feyerabend: saving `≥30%` and F1 drop `≤0.02`; saving `<10%`이면 bandit kill | outcome leakage in logs, shuffled policy 유지, fixed classifier 변경, full-scan 비용 누락 | offline `1일`; tabular/linear `1–2일`; GPU optional only for VLM action | A60; M30 frozen classifier; F05 |
| A62 HORIZON-ONPOLICY-PROBE | VIABLE | `calibration_P6` C/D/G; `feyerabend_P4` S0b의 routing branch | horizon>1의 실제 가치가 있을 때만 on-policy adaptation/short RL로 승격할 이유가 있다. | learning-zero greedy/beam depth-H utility, small simulator adaptation, unlabeled real Pareto diagnostic을 순서대로 실행한다. | S qualified; R/C diagnostic | GPU-LOCAL-SERIAL | utility ratio, beam-greedy delta, adaptation stability, cost/quality Pareto | `utility_RL/utility_bandit≥1.05`; routing dossier의 beam-greedy 제안 `≥0.02`가 있을 때만 short RL 검토 | multi-step lift `<5%`, hidden feedback 사용, bandit보다 비용/품질 열등 | learning-zero `1일`; adaptation `1–2일`; local small H only | A61; A60; F02 |
| A63 SET-ASSEMBLY-ZERO-LEARNING | VIABLE | `platt_P4` E1; `doe_P4` learning-zero gate; `feyerabend_P4` S0b | greedy/beam/ILP의 reward landscape가 자명하면 set-assembly RL을 훈련 전에 죽일 수 있다. | 동일 candidate·verifier에서 random, greedy, beam widths, tractable ILP/upper bound를 한 ledger로 sweep한다. | S/C dev | CPU-PAR | best-beam−greedy F1, upper−greedy, verifier calls, wallclock | beam이 greedy보다 개선하고 greedy가 upper bound에 붙지 않아야 다음 셀; `<0.01` and upper gap `≤0.01`이면 RL kill | upper bound 없는 상태에서 상한 근접을 주장, candidate/verifier 불공정, reward unsound | 로컬 CPU `1일`, learning 0 | A60; F03/G40 candidate graph; M30 checkpoint |
| A64 SET-ASSEMBLY-RLVR | PARKED | `platt_P4` E3/E4; `doe_P4` set-assembly branch | 비가산 verifier 아래 sequential set policy가 beam보다 충분히 좋고 invariance를 해치지 않을 때만 RLVR 자리가 있다. | common imitation prefix 후 supervised+greedy, beam, ILP, RLVR을 동일 추가 cap과 three-seed trace로 비교한다. | S/C/M | GPU-LOCAL-SERIAL | RL−beam F1, violation delta, reward hacking, calls/latency | `mean_seed(F1_RL)−F1_beam≥+0.05` AND violation delta `≤0` | A63 kill, verifier FAR fail, reward-hacking, 어느 AND 조건 미달 | arm/seed 추가 `24시간 cap`, RL 3 seed; local serial | A63; A60; G40; T20 |
| A65 FULL-RL-FACTORIAL | PARKED | `calibration_P6` F; `doe_P4` 12 cells+2 hacking probes; `feyerabend_P4` R2/H | paradigm×truth quality×label budget interaction이 cheap probes를 넘을 때만 broad RL/active factorial이 정당하다. | supervised/RLVR/active × high/low truth × scarce/abundant를 hacking probes와 함께 실행한다. terminal label RL은 제외한다. | S/C/M; F only after rights | DGX-QUEUE | A×C, A×B, F1/cost, hacking signature, seed variance | cheap active/RL cell이 supervised 대비 lift `≥0.03` 또는 cost `≤0.85×`; verifier FAR `≤0.01`; RLVR only after A62/A63 survival | cheap 4-cell no signal, A×C null and supervised dominates all budgets, hacking-only win, DGX unreachable | local signal까지 약 `1주`; full DGX after gates 추가 `1–2주` | A60–A63; F02; DGX reachable |
| C70 LEXICON-PROJECT-PROBE | VIABLE | `platt_P6` LEX/PID/CP | 이름·레이어·블록 관례가 실제 project grouping과 연결되는지 geometry 없이 싸게 판별할 수 있다. | lexicon freeze, project_id provenance audit, 384-def convention-only cheapest probe를 실행한다. | R only; C missing-control | CPU-PAR | token support, project purity, convention-only AUC, shuffle | LEX/PID gates 통과; CP가 chance 근방이면 XP 예산 축소; 본 셀은 정확도 채택 셀이 아님 | project_id가 경로 누수, token normalization이 label을 읽음, CubiCasa missing-control에서 비중립 | LEX `0.5–1일`, PID `0.5일`, CP 수시간 | F00; F01 |
| C71 CONVENTION-ONLY-H3 | VIABLE | `platt_P6` XP/TAU/E1C/STK/SHUF; `platt_P2` C4의 H3 경보 | geometry를 의도적으로 배제한 관례 모델의 within/cross-project 차이가 H3의 재사용성과 silver 이름-prior를 계측한다. | leave-project-out logistic/HGB, tautology split, silver correlation, frozen geometry stack marginal, label shuffle를 수행한다. | R; C는 all-missing control | CPU-PAR | within/cross AUC, support, E1 correlation, stack ΔAUC, shuffle | cross-project AUC `≥0.75`이면 support; within `≥0.90` and cross `≤0.60`이면 local-only demote; cross `≤0.55` kill; E1 corr `≥0.70`이면 silver 독립성 demote | project leakage, geometry feature 유입, shuffle 비붕괴, CubiCasa에서 non-missing effect | XP `1–2 CPU일`; E1C `0.5일`; STK `1일` | C70; F00; M30 frozen for STK |
| C72 GATE-CONSTRAINED-CONVENTION | VIABLE | `feyerabend_P7` E0/E1 | 관례 prior가 geometry gate 안에서만 재순위화하면 aligned convention은 돕고 misaligned/all-missing에서는 완전히 기권한다. | frozen geometry candidate/gate 위에서 aligned/misaligned paired synthetic 2×2와 regex prior를 실행하고 geometry/prediction hashes를 비교한다. | S qualified; C all-missing | CPU-PAR | ΔF1, gate/candidate/geometry hash, misaligned delta, missing identity | aligned ΔF1 `≥+0.15`; misaligned weight 0, delta 0, prediction hash identity; `G(h)=0` 밖 positive 0 | gate 우회 한 건, geometry hash 변화, aligned lift `<0.15`, missing convention에서 geometry-only와 다름 | E0 `≤1h`; E1 수시간 | F02; F03; M30/D12 frozen geometry gate |
| C73 INDIRECT-PRIOR-TRANSFER | VIABLE | `feyerabend_P7` E2–E5 | direct token을 제거해도 indirect convention이 project 내부·cross-project freeze에서 양의 한계 정보를 줄 수 있다. | EB/MI reliability, convention shuffle/sentinels, real 384 fit/freeze analysis, independent project transfer one-shot을 수행한다. | R; C missing-control; S mechanism only | CPU-PAR | incremental MI, shuffle delta, disagreement, cross-project ΔF1, gate identity | E3 all gate/candidate hashes identical; final fully frozen project-transfer ΔF1 `>0`; aligned C72 gate도 함께 만족 | transfer ΔF1 `≤0`, target 재적합 의존, direct token 제거 시 전부 붕괴, metadata+label project 부재면 PARK | core probe `3–5개발일`; full harness `6–9개발일`; per-project sparse prior 수시간 | C72; C70/C71 results; independent labeled project/right |
| P80 BROAD-2POWER-SCREEN | PARKED | `doe_P1` Phase 0, deterministic 8, learned 8×3, effects/augmentation, confirmation | representation×model×truth×noise×self-training×leakage의 큰 interaction이 좁은 셀에서 놓친 효과를 찾을 수 있다. | Resolution-IV 16-run fractional screen, deterministic 8 first, learned cells, Lenth effects, targeted de-alias augmentation, holdout confirmation을 실행한다. | S/F/C/M | DGX-QUEUE | main/aliased 2FI effects, R-SYN/R-SILVER, sentinel, confirmation | R-SYN `≥0.90`, R-SILVER `≥0.50`, S0 `≥0.99`, macro recall `≥0.30`; alias를 clean interaction으로 부르지 않음 | F02/R50/source gates 미완, deterministic probe 무신호, seed confound, 8-row augmentation을 Res-V로 오표기 | deterministic 8 cells cache 후 반나절; learned cell each 3 fits; full expansion conditional | F02; R50; T20; M30/G41; DGX reachable |
| P81 FULL-VLM-FACTORIAL | PARKED | `doe_P6` cheapest/frontier 6/open-finetune 6/effects/confirmation | mode×modality×supervision interaction이 R53/R54의 좁은 화면을 넘어설 때만 12-cell vision DOE가 가치 있다. | frontier raster/vector/both와 local open fine-tune를 같은 T24 bridge·truth contract에서 완전 셀로 확장한다. | F/C/S/R images | FRONTIER-API | handle F1/AUPRC, modality/supervision effects, R-SYN/R-META, juror admission | frontier는 B1∧B4; open은 `F1≥0.517` 또는 robust-v0 대비 R-SYN/R-META 모두 우세; confirmation one-shot | API 미결재, R50 fail, cheapest no signal, frontier와 open budget/role 혼합 | cheapest `0.5일`; open cell `0.5–2일`; full 12는 DGX; API envelope prereg | R50; R53 and R54 cheap results; API approval; DGX reachable for full |

## 2. 죽인 셀·경로

아래는 밴드가 아니다. 이미 전제가 무너졌거나 더 우월한 통제로 대체되어 **현재 프로그램에서 실행·승격하지 않는 경로**다.

| Kill ID | 죽이는 셀/경로 | 출처 맥락 | 이유 | 남기는 것 |
|---|---|---|---|---|
| K01 | 현 B1-fail S/F/M 팩을 confirmatory truth·RL reward로 사용 | `calibration_P1` C1; `feyerabend_P3` C1; `feyerabend_P4` reward; `platt_P3` C0 | 현 합성팩은 B1 FAIL이고 벽 생성 코드/strict sentinel 자격이 없다. 이 전제로 만든 PASS는 가짜다. | engineering fixture와 failure reproduction만; F02 통과 버전은 새 artifact ID로 시작 |
| K02 | raster mask/polygon/auto-traced line을 CAD SoT 또는 exact handle truth로 승격 | `calibration_P2` C0/C1; `calibration_P3` E0; `feyerabend_P5` P5-01/P5-04; `platt_P5` V1–V3 | FloorPlanCAD에는 native vector handle truth가 없다. unmatched mask를 벽으로 승인하면 평가 단위가 바뀐다. | mask IoU와 proposal/juror 한 표; 최종 판정은 R50을 통과한 original handles+deterministic gate |
| K03 | E1.5 모델 5기를 5개 독립 표로 합산 | `calibration_P5` C; `doe_P6` frontier; `platt_P5` V5 | 약 2개 어휘 가문이므로 독립성 가정이 깨진다. | family당 한 표와 raw-5 참고표만 |
| K04 | D10 전에 absolute-mm grid/Taguchi 최적화 | `doe_P2` C0–C5; `feyerabend_P2` C2/C4 | absolute-vs-relative와 tuning 효과가 confound된다. 평균 최적값은 unit 가설을 판결하지 못한다. | D10이 absolute를 유지할 때만 원 grid; relative가 이기면 factor definition을 새로 봉인 |
| K05 | per-handle fixed-label RL을 본선으로 실행 | `platt_P4` E2; `doe_P4` terminal branch; `calibration_P6` scope | 같은 입력의 binary label은 supervised 목적이 직접적이며 HGB 기준선도 있다. | `platt_P4` E2는 동일 cap의 음성 대조군으로만 한 번 허용; 주장은 A61/A64의 routing/set assembly로 제한 |
| K06 | raw handle/path/vendor/project ID 또는 답을 드러내는 layer/token을 primary feature로 사용 | `calibration_P2` C8; `platt_P2` C4; `feyerabend_P7` E0 | split memorization과 name-prior가 semantic lift로 위장한다. | masked ablation, convention-only C71, gate-constrained C72로 분리 계측 |
| K07 | test 재실행·test 기반 threshold/calibrator/model 선택 | 모든 confirmation 셀 | 방법당 단발 계약과 독립 검증을 깨뜨린다. | cryptographically evidenced infra failure는 결과 없는 invalid run으로만 기록 |
| K08 | 최대 definition에서 all-pairs/O(n²) 후보 전개 | `calibration_P1` C8; `calibration_P2` C6; `feyerabend_P6` C5; `platt_P2` C7 | `1.dwg` 최대 definition 규모에서 메모리·시간을 숨기는 열등 구현이다. | angle/spatial index, chunked streaming, shard parity, F05 stress |

조건부 kill은 각 매트릭스 행의 kill 조건이 권위다. 특히 G41은 M30 Occam gate가 닫히면, R51/R53은 R50 common bridge가 죽으면, A64/A65는 A60/A63이 죽으면 계산을 쓰지 않는다.

## 3. 원문 §6 → 통합 셀 교차표

이 표는 26부 §6 제안의 소실 여부를 감사하기 위한 역색인이다. 한 원문 셀이 둘 이상의 책임을 가졌으면 복수 통합 셀에 귀속했다.

| 원문 도시에 | 원문 §6 셀 → 통합 귀속 |
|---|---|
| `calibration_P1` | C0→F00; C1→F02; C2→D11; C3→F03/D10; C4→D11; C5–C6→D12; C7→F04; C8→F05; C9→F06 |
| `calibration_P2` | C0→F00; C1–C2→M31; C3–C5→M32; C6→F04/T20; C7→F06; C8→M32/F00 |
| `calibration_P3` | E0→F00/F02; E1→G40/F05; E2→G41; E3→M30/G41; E4→G42; E5→G42/T20; E6→F04/F05; E7→F06 |
| `calibration_P4` | P4-0→F00/R50; P4-1→R50; P4-2–P4-3→R51; P4-4→R52; P4-5→F04/R52; P4-6→F06 |
| `calibration_P5` | P5-A–P5-C→R53; P5-D→R55; P5-E→T21/R55; P5-F→M32/R55; P5-G→R55 |
| `calibration_P6` | Cell-0/A→A60; B→A61; C/D/G→A62; E→F06; F→A65 |
| `doe_P1` | Phase 0→F00; 16 cells·deterministic 8·learned 8×3·effects/augmentation→P80; confirmation→P80/F06 |
| `doe_P2` | C0→D10; C1–C5→D13; C6→D13/F06 |
| `doe_P3` | 공통+24 cells→T20; confirmation→T20/F06 |
| `doe_P4` | cheapest 4→A61/A63; 본실험 12→A65; hacking 2→A60/A65; confirmation→F06 |
| `doe_P5` | 자격 셀·최저비용 2·본실험 F01–F28→F04; confirmation→F04/F06 |
| `doe_P6` | cheapest/frontier 6→R53/P81; open-finetune 6→R54/P81; confirmation/effects→P81/F06 |
| `feyerabend_P1` | E0→F02; E1→D14; E2→D14/F04; E3→D14; E4→D14/T20; E5→R52; E6→F06 |
| `feyerabend_P2` | C0→F02; C1–C2/C4–C5→D10; C3→F04; conditional one-shot→F06 |
| `feyerabend_P3` | C0→T21; C1→F02; C2–C5→T21/T20; C6→F06 |
| `feyerabend_P4` | S0→A61; S0b→A62/A63; V1→A60; B1/B1-shuf/X→A61; R2→A65; H→A60/A65 |
| `feyerabend_P5` | P5-00/P5-01→R50; P5-02/P5-03→R51; P5-04/P5-05→R52/T20; P5-06→F04/R52; P5-07/P5-09→R52; P5-08→F06 |
| `feyerabend_P6` | P6-C0–C2/C4/C6→F03; C3→F03/F04; C5→F05; C7→F06 |
| `feyerabend_P7` | E0/E1→C72; E2/E4→C73; E3→C73/F04; E5→C73/F06 |
| `platt_P0` | C0–C6→F01 |
| `platt_P1` | G0→F00; G1→F03; G2→F02; E0/E1→D11; E2/E3→D12; E4→D10; E5→R52; E6→F05; E7→F04/T20; E8→F06 |
| `platt_P2` | G0→F00; G1→G40; C1→M30; C2–C4→G41; C5→G42/T20; C6→T21; C7→F04/F05; T1→F06 |
| `platt_P3` | C0→F02; C1–C5→F04; C6→R52/F06; C7→T20 |
| `platt_P4` | E0→A60; E1→A63; E2→K05 음성 대조; E3→A64; E4→A60/A64; E5→F06; E6→A61 |
| `platt_P5` | G0/V1→R50; V2→R51; V3→R52/T20; V4→R53; V5→R53/R52; V6→R52/F06 |
| `platt_P6` | LEX/PID/CP→C70; XP/TAU/E1C/STK/SHUF→C71 |

## 4. 실행 페이즈와 의존성

### 4.1 발사 순서

| 페이즈 | CPU 병렬 lane | GPU local 직렬 lane | DGX 대기열 | API 결재 대기열 | 종료/발사 조건 |
|---|---|---|---|---|---|
| Phase 0 — 증거 봉인 | F00와 F01 동시 착수 | idle | queue definition only | approval request·예산 envelope만 작성, 호출 0 | F00 run contract와 F01 artifact 판결이 있어야 데이터/표본을 고정 |
| Phase 1A — 공용 계측기 구현 | F02, F03, F04, F05, G40, R50, A60을 구현 단위로 병렬화 | bridge smoke만, 학습 0 | G42/R55/A65/P80 job manifest만 준비 | R53/P81 prompt/schema만 준비, 호출 0 | 구현 완료는 PASS가 아님. Phase 1B에서 상호 gate를 실제 fixture로 닫음 |
| Phase 1B — 계측기 자격 | F02→F04; F03→G40/R50; F05 stress; A60 verifier audit | R50의 작은 smoke가 필요할 때만 단일 slot | 여전히 실행 0 | 여전히 실행 0 | F02/F03/F04가 닫히지 않으면 S/M 기반 방법 중단; R50 fail이면 모든 raster/VLM handle claim 중단; G40 fail이면 GNN/RL-set graph 중단 |
| Phase 2 — 값싼 판별 wave | 병렬 branch A: D10→D13; B: D11→D12; C: D14; D: T20; E: M30→M31→M32; F: A61와 A63; G: C70→C71 및 C72→C73 | T21을 첫 GPU job으로 예약; CPU 전처리는 병렬 | gate 결과를 queue metadata에 반영 | admission CPU 재산출은 가능하지만 API 호출 0 | D10이 D13 parameterization 결정; M30이 G41 발사 여부 결정; A63이 A64를 결정; C72가 C73을 결정 |
| Phase 3 — 로컬 GPU 생존 큐 | GPU job별 shard/eval/xlsx를 CPU workers가 병렬 준비하되 RAM watchdog 공유 | **직렬 순서:** T21 → G41 → R51 → R52 → R54 → A62 → A64. 각 kill 즉시 뒤의 종속 job 취소 | 실행 0 unless reachable and upstream gates closed | approval 시에도 R53만 먼저; P81은 R53/R54 신호 후 | 한 RTX에서 동시 train 금지. inference-only CPU/GPU overlap은 VRAM 침범이 없을 때만 허용 |
| Phase 4 — 조건부 확장 | surviving-cell 분석, prereg freeze, P80 deterministic prefix | local fallback은 dossier cap 안에서만 | reachable 후 G42 → R55 → A65 → P80; 각각 앞 cell 생존 필요 | approval 후 R53; admission+value 신호 후 P81 | DGX/API 결과가 없어도 TOP/VIABLE local program은 완료 가능; blocked를 PASS로 바꾸지 않음 |
| Phase 5 — 확인 | method별 immutable dependency report와 resolver 확인 | 학습 0; inference만 | frozen checkpoint inference only | frozen endpoint/prompt only if method survived | F06에서 방법당 test 단발, xlsx·failure witness·runtime ledger 완료 후 종료 |

### 4.2 핵심 DAG

```text
F00 ─┬─> F01 ───────────────┐
     ├─> F02 ─> F04 ────────┼─> D11 -> D12 ─┐
     ├─> F03 ─> G40 ────────┼─> M30 -> G41 -> G42
     │       └─> R50 ───────┼─> R51 -> R52
     ├─> F05 ───────────────┤         ├-> R54
     └─> A60 -> A61 -> A62  │         └-> R53 -> R55
                  └-> A63 -> A64 -> A65

F02 + F03 -> D10 -> D13
F02 + F03 + F04 -> D14
qualified sources + R50 -> T20 -> T21 / G42 / R52
F01 -> C70 -> C71
F02 + frozen geometry gate -> C72 -> C73
all surviving method gates + prereg freeze -> F06
```

운영 규칙:

1. CPU lane은 immutable input shard와 per-process read-only cache를 사용한다. F05 RAM watchdog 때문에 대형 arrays를 worker마다 복사하지 않는다.
2. GPU lane은 한 job만 train한다. 다음 job은 predecessor의 kill report와 released VRAM을 확인한 뒤 시작한다.
3. DGX는 현재 unreachable이므로 queue item 상태를 `BLOCKED_RESOURCE`로 둔다. local result를 DGX full-study PASS로 대체하지 않는다.
4. API는 미결재이므로 `BLOCKED_APPROVAL`; 결재 전 paid call 0. approval이 와도 R53 screen을 P81 confirmation으로 포장하지 않는다.
5. 모든 branch는 실패도 xlsx row로 남긴다. 조용한 row/drop, timeout 제외, metric cherry-pick은 run 무효다.

## 5. 밴딩 요약

밴드 안의 나열은 순위가 아니라 실행 묶음이다.

| 밴드 | 셀 | 조건/사유 |
|---|---|---|
| TOP | F00, F01, F02, F03, F04, F05, F06, D10, D11, D12, T20, M30, G40, R50, A60 | 공용 진실면·가장 싼 root-cause 판별·test 거버넌스. 후속 모든 비용을 줄이는 선결 셀 |
| VIABLE | D13, D14, T21, M31, M32, G41, R51, R52, R54, A61, A62, A63, C70, C71, C72, C73 | 각 행의 explicit prerequisite를 통과한 뒤 실행. local CPU/GPU로 판결 가능하고 DGX/API가 성공 조건이 아님 |
| PARKED | G42, R53, R55, A64, A65, P80, P81 | DGX 불통, API 미결재, silver admission 미확정, verifier/greedy/Occam/cheap-screen 미완료, 또는 broad factorial의 비용 때문에 대기 |

## 6. 모순 원장 — 원문 보존, 평균 금지

### C01. 생성기 fidelity gate 세 벌

> `calibration_P1.md:612` — “fidelity의 신규 설계 gate는 주요 연속분포 `KS≤0.10`, 주요 범주분포 `TV≤0.10`으로 제안하며 WSD-EVAL 봉인 전에 승인한다.”

> `platt_P1.md:522` — “제안 gate는 주요 scalar feature별 KS≤0.2, categorical entity-family TV≤0.1, 공개된 필수 family coverage 100%다.”

> `feyerabend_P1.md:544` — “사전 지정 핵심 분포의 `KS_max≤0.30` 및 `TV≤0.20`.”

판결: 평균값을 만들지 않는다. F02는 모든 통계를 한 번 산출하되 calibration-P1 core claim은 `0.10/0.10`, CL-B는 `0.20/0.10`, face exploratory admission은 `0.30/0.20`을 각각 적용한다. face-only 통과가 더 엄격한 두 claim의 자격이 되지 않는다.

### C02. Graph adjacency completeness `0.98` 대 `0.995`

> `calibration_P3.md:624` — “support가 있는 모든 required relation type과 micro known-relation recall이 각각 `>=0.98`”

> `platt_P2.md:669` — “exhaustive positive relation recall ≥ 0.995”

판결: G40은 두 판정을 모두 출력한다. `0.98≤recall<0.995`이면 calibration-GNN만 자격 후보이고 platt-GNN은 blocked다. shared builder를 “전 경로 자격”으로 부르려면 `0.995`를 충족해야 한다.

### C03. Calibration resolution `0.02` 대 `0.03`

> `calibration_P1.md:665` — “`REL≤0.03`, `RES≥0.02`”

> `calibration_P3.md:685` — “`REL<=0.03`; `RES>=0.03`”

판결: D12는 deterministic P1의 `RES≥0.02`, G42는 GNN의 `RES≥0.03`을 유지한다. 하나의 pooled calibration PASS로 합치지 않는다.

### C04. Absolute grid 대 relative-first

> `doe_P2.md:70` — “`gap_lo/gap_hi` | (20,300) | (30,500) | (50,800) | 벽 두께 후보 대역(mm)”

> `feyerabend_P2.md:1001` — “이 셀이 끝나기 전 doe P2의 절대 band robust optimization이나 다중 knob Taguchi를 실행하지 않는다.”

판결: D10이 먼저다. absolute가 유지되면 원 L9를 실행하고, relative가 이기면 K04대로 원 absolute 청구를 죽인 뒤 새 factor definition을 봉인한다.

### C05. Raster “본선” 대 “한 표”

> `feyerabend_P5.md:31` — “‘vision-as-SoT 기각’은 관측을 판정으로 승격하지 말라는 규칙이지, 관측 표현을 학습하지 말라는 규칙은 아니다. P5는 다음 세 층을 분리한다.”

> `feyerabend_P5.md:34-35` — “**제안층**: 그 영역을 원래 CAD의 기존 핸들·선분 집합으로 귀속해 제한된 후보 목록을 만든다.” / “**판정층**: 후보 순위나 픽셀 확률을 보지 않고, 벡터 기하·CRS 무결성·metamorphic·sentinel·라이선스 규칙으로 합격시킨다.”

> `platt_P5.md:11` — “두 트랙 모두 진리원(source of truth)이 아니다. … VLM/분할 모델은 고정된 앙상블에 **각각 최대 한 표**만 낸다.”

판결: R51/R52는 raster를 **proposal**로, R53은 **juror 한 표**로 시험한다. 둘 다 deterministic original-handle gate를 넘지 못한다. “mainline”이라는 제품 권위는 R52의 CL-B 상보성·독립 truth·clean artifact가 모두 닫히기 전 PARKED다.

### C06. FloorPlanCAD mask 학습 대 native handle truth 부재

> `feyerabend_P5.md:132` — “FloorPlanCAD에는 벡터 SVG가 없으므로 이 데이터만으로 handle 역투영 정확도를 측정하지 않는다. FloorPlanCAD는 mask 학습·IoU 축”

> `calibration_P3.md:346` — “현재 **native CAD handle line truth는 존재하지 않는다**.”

판결: 충돌을 데이터 축 분리로 보존한다. F는 R51의 pixel-IoU 학습축일 수 있지만 handle F1/AUPRC는 R50의 independent bridge와 별도 handle truth 없이는 정의하지 않는다.

### C07. RL 적용 범위

> `platt_P4.md:7` — “엔티티별 고정 라벨 `wall_member(h)`: 같은 입력 신호로 교차엔트로피 supervised 분류기를 항상 만들 수 있으므로 full RL의 자리가 아니다. RL arm은 음성 대조군이다.”

> `platt_P4.md:8` — “pair→chain→network 집합 조립: 서로 충돌하거나 보완하는 후보를 순차 선택하고, 최종 집합에만 계산 가능한 비미분 검증 보상을 받는다. P4에서 RLVR 자격을 심사할 유일한 본선이다.”

> `feyerabend_P4.md:13` — “C07의 좁은 판(‘entity→category 직접 RL은 오용’)은 유지하되, **검사 획득·라우팅 정책**에는 contextual bandit / 단기 RLVR을 별도 prereg 트랙으로 연다.”

판결: K05는 entity-label RL mainline을 죽인다. A61/A62는 evidence routing, A63/A64는 set assembly로 분리하며 서로의 승리를 합산하지 않는다.

### C08. Convention-only 대 geometry-gated convention

> `platt_P6.md:16` — “피처를 의도적으로 빈약하게(기하 배제)”

> `feyerabend_P7.md:11` — “`관례 prior → 기하 확인 → 게이트 내부 재순위화` … `G(h)=0`인 핸들은 이름이 `WALL`이어도 절대 벽으로 출력하지 않는다.”

판결: C71은 H3 **측정용 convention-only instrument**, C72/C73은 **배포 후보 gate-constrained reranker**다. 두 출력은 다른 가설이며 하나의 convention model score로 평균내지 않는다.

### C09. E1.5 admission의 B4와 관측 B5 혼동

> `platt_P5.md:258` — “**B1 ≥ 0.70 그리고 B4 Pearson ≥ 0.70**을 E1.5 silver 자격 조건으로 적용한다.”

> `calibration_P5.md:78` — “실측 참고(게이트 *입력*이지 통과 증거가 아님): B5 Pearson 0.2911 — 현재 축은 B4 밴드(0.70)에 미달 가능성이 크다.”

판결: B5 `0.2911`에서 B4 값을 추정하지 않는다. R53의 첫 작업은 정확한 `E15_B1/E15_B4` 재산출이며, 둘 중 하나가 미확인인 동안 admission은 OPEN/BLOCKED이지 PASS도 FAIL도 아니다.

### C10. 최대 definition 선분 수 불일치

> `calibration_P3.md:363` — “최대 definition은 412,775 segment다.”

> `platt_P6.md:204` — “도면정의 384 / 최대 412,965 선분”

판결: 패킷 고정 사실과 다수 dossier 표기인 `412,775`를 계획 상수로 쓴다. `412,965`는 원문 오기로 보존하며 예산·stress 산정에 사용하지 않는다.

### C11. Metamorphic 허용률 세 종류

> `calibration_P1.md:382` — “공식 band는 handle flip rate `≤0.01`, kill은 `>0.02`다.”

> `doe_P2.md:126` — “PASS: `R-META <= 0.02`”

> `platt_P3.md:416` — “회전 0 위반, 나머지 admitted invariant 관계 `V_r≤1%`.”

판결: 이들은 서로 다른 집계단위다. D12의 lineage flip, D13의 aggregate R-META, F04의 relation-wise conviction을 각자 유지한다. 한 지표 통과로 다른 지표를 면제하지 않는다.

## 7. 총예산 요약

셀 수는 통합 매트릭스의 **주 트랙 기준**이라 중복 계산이 없다. 시간은 원문 제안값이며 측정 완료시간이 아니다. 동일 구현 prefix와 중복 dossier 예산은 합산하지 않는다.

| 주 트랙 | 셀 수 | 제안 소요 envelope | 병목과 중단 규칙 |
|---|---:|---|---|
| CPU-PAR | 24 | 가장 짧은 F01은 CPU `<1시간`+반나절 script; D10은 `<1일`; F03은 `6–10 engineer-days`; F04 full battery는 `7–10개발일`. deterministic core의 상위 staffing envelope는 `2–3인주`, generator 별도 `1–2인주`, evidence/stress 약 `1인주`라는 `calibration_P1` 제안을 사용한다. 병렬이므로 이들을 단순 합계하지 않는다. | F02 generator, F03 canonical IR, F04 relation judge가 공용 critical path. RAM 64GB에서 worker 복사와 max-def stress가 병목. 실패한 공용 gate 뒤 종속 셀 즉시 취소 |
| GPU-LOCAL-SERIAL | 7 | T21 cheapest 반나절; G41 base 최대 `18 GPU-hours`; R51 `2–3 GPU일`; R54 cell `0.5–2일`; A64가 발사되면 arm/seed `24시간 cap`, 3 seed. 생존한 job만 직렬 합산하므로 사전 총합을 만들지 않는다. | RTX 5070 Ti 16GB 단일 큐. 가장 큰 예상 병목은 raster three-seed와 조건부 RL; M30/R50/A63 kill을 먼저 적용 |
| DGX-QUEUE | 4 | G42 수 GPU-day; A65 full은 local signal 뒤 추가 `1–2주`; R55/P80은 source cap을 queue manifest에 보존. 현재 unreachable이므로 실제 시작·완료시각은 미산정/blocked다. | 연결성 자체가 첫 병목. local smoke를 DGX full PASS로 승격 금지; G42→R55→A65→P80 순으로 더 싼 생존 증거 요구 |
| FRONTIER-API | 2 | approval wait는 미산정. 승인 뒤 R53 screen은 `1일/유효 응답 20개 이하` envelope 또는 calibration jury `150 calls` 대안 중 사전 승인된 하나만 사용; 두 예산을 합산하지 않는다. P81은 R53/R54 신호 후에만. | 미결재와 B1∧B4 admission. paid call 전에 F01/R50 완료; screen을 confirmation으로 재사용 금지 |
| TEST-ONCE | 1 | F06 orchestrated inference: 살아남은 방법당 1회, 재학습 0. | method별 prereg·resolver·rights·dependency report. 실패 row도 xlsx에 남기고 결과를 본 재실행 금지 |

전체 일정의 과학적 병목은 모델 학습이 아니라 `F01 → F02/F03/F04 → R50/G40/A60`의 진실면 자격이다. 운영 병목은 local GPU 직렬화, DGX 불통, API 결재다. 이 셋은 서로 독립 queue로 관리하며 blocked 자원을 local PASS로 상쇄하지 않는다.

PLAN_COMPLETE: sol
