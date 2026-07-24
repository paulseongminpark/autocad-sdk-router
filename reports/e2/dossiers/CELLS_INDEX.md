# CELLS_INDEX — 26 도시에의 실험 셀 섹션 원문 모음 (종합용)


---

## [calibration_P1] — ## 6. 실험 셀 정의 (115 lines)

## 6. 실험 셀 정의

### 공통 실행 규칙

- split은 project·unit·grammar·opening style family 단위다.
- random seed는 임의 수기 선택 대신 `uint64(SHA256(manifest_hash || cell_id || family_id || replicate_id))`로 생성해 manifest에 기록한다.
- deterministic geometry와 solver는 canonical ordering을 사용한다. solver가 내부 random seed를 요구하면 위 seed를 고정하고 thread 수를 기록한다.
- val은 개발·튜닝 허용, test는 방법당 단발이다. test를 연 뒤 파라미터·코드·band를 바꾸면 새 proposal version으로 돌아가며 기존 test는 소모된 것으로 기록한다.
- confidence interval과 subtype 표는 진단용이다. prereg band의 point rule을 사후에 interval rule로 바꾸지 않는다.
- 모든 셀은 raw artifact와 evidence xlsx row가 없으면 PASS가 아니다.

### C0. 계약·누수·resolver 격리 셀

- **가설**: S/F/M identity, split, band, import boundary를 test 접촉 전에 완전히 봉인할 수 있다.
- **데이터**: 세 manifest와 implementation dependency graph.
- **지표**: group overlap count, duplicate truth key, missing lineage, forbidden import count, unresolved metric definition count.
- **제안 합격선**: 모든 count `0`, 모든 필수 hash 존재, `coverage`와 false merge denominator 고정.
- **킬 조건**: test row가 train/calibration에 나타남, resolver가 generator geometry/threshold를 import함, FloorPlanCAD projected mask를 exact handle truth로 허위 표기함.
- **예산**: 로컬 CPU 수시간, GPU/DGX 없음.
- **시드**: 비확률적; canonical sort만 사용.

### C1. PR-1 wall generator·fidelity 셀

- **가설**: 실제 벽 primitive 다양성과 divergent 현상을 가진 독립 generator를 만들 수 있다.
- **데이터**: 5 grammar × 20 block의 100-case S probe, hidden mutation families, CL-A가 감사한 real divergence summary.
- **지표**: entity-type support, block depth, opening/gap/overshoot strata coverage, real-vs-S histogram KS/TV, exact-handle self-consistency.
- **제안 합격선**: 모든 요구 primitive family가 manifest에 존재하고 exact truth self-check가 완전 일치한다. fidelity의 신규 설계 gate는 주요 연속분포 `KS≤0.10`, 주요 범주분포 `TV≤0.10`으로 제안하며 WSD-EVAL 봉인 전에 승인한다.
- **킬 조건**: 기존 dimension 전용 `synthetic_truth.py`를 wall truth로 재사용, hidden truth가 generator logic과 동일 predicate로 생성, fidelity gate 반복 실패.
- **예산**: 로컬 CPU, 구현 1–2인주와 검증 수시간(설계 추정).
- **시드**: grammar/case별 hash seed; hidden family seed list는 resolver 보관, candidate 개발자에게 비공개.

### C2. cheapest probe: v0 대 lattice

- **가설**: 100-case S와 E1 top-20 divergence에서 P1이 v0 candidate recall을 유지하면서 false merge·flip·메모리를 악화시키지 않는다.
- **데이터**: C1 100-case, CL-A 정렬 artifact 감사를 통과한 E1 top-20과 사전 지정 대조군.
- **지표**: candidate recall, handle F1, false merge rate, candidate edge/entity ratio, component size, metamorphic flip, peak RAM, 도면별 시간.
- **제안 합격선**: S candidate recall `≥0.98`, false merge `≤0.05`, hidden이 아닌 probe F1이 v0보다 낮지 않고, M flip이 kill band `0.02`를 넘지 않음. 수치는 신규 probe gate이며 final claim band를 대체하지 않는다.
- **킬 조건**: hidden synthetic F1 `<0.85`, false merge `>0.05`, flip `>0.02`, quadratic edge 폭증, 48GB 이전 watchdog abort.
- **예산**: 로컬 CPU 1일 이내 목표, GPU/DGX 없음.
- **시드**: C1 seed 고정; solver tie-break 고정; 반복은 환경 variance 측정용으로 동일 입력 순서를 순환한다.

### C3. transform·unit·scale 정규화 셀

- **가설**: INSERT folded/unfolded, rigid transform, reflection, unit/scale 변환에서 world geometry와 prediction lineage가 보존된다.
- **데이터**: nested block synthetic, 1.dwg의 manifest 지정 INSERT 표본, M relations.
- **지표**: world-coordinate deviation, lineage mismatch, handle flip, scale arm invariance, unit-anchor abstention.
- **제안 합격선**: exact synthetic transform은 schema tolerance 안에서 전부 일치하고, 공식 M flip `≤0.01`; scale arm도 같은 relation band를 통과.
- **킬 조건**: determinant/reflection 처리로 wall orientation이 바뀜, ambiguous unit을 임의 mm로 확정, flip `>0.02`.
- **예산**: 로컬 CPU 1일, GPU/DGX 없음.
- **시드**: transform parameter는 hash-derived space-filling set; identity transform을 항상 포함.

### C4. evidence 채널·false merge 셀

- **가설**: offset 단일 증거에 continuity, junction, face, opening, hatch, lineage, single-line을 더하면 장식·기호 false positive를 줄이면서 wall recall을 보존한다.
- **데이터**: CubiCasa train 내부 개발 fold, S negative/sentinel, FloorPlanCAD raster 보조축.
- **arm**: v0, offset-only, `+continuity/junction`, `+face/opening`, `+hatch/lineage`, full P1, name/layer-masked full P1.
- **지표**: subtype precision/recall, candidate recall, false merge, single-line recall, per-channel availability, ablation delta.
- **제안 합격선**: full P1 false merge `≤0.05`, name-masked arm이 공식 band 가능성을 잃지 않고, 어떤 채널의 추가도 사전 지정 recall floor를 조용히 깨지 않음.
- **킬 조건**: 개선이 layer/source hard oracle에서만 나옴, single-line 채널이 장식 false positive를 통제하지 못함, aggressive pruning으로 candidate recall이 C2 gate 아래로 떨어짐.
- **예산**: 로컬 CPU batch 1–2일 목표, 제한된 설계 조합만 사용.
- **시드**: split group seed 고정; arm은 동일 후보·동일 순서로 paired 비교.

### C5. matching 대 component ILP 셀

- **가설**: ILP가 실제 다자 충돌 component에서 matching/greedy보다 false merge를 줄이며 비용 band 안에 든다.
- **데이터**: C2/C4에서 conflict가 있는 S/F components와 real stress components.
- **arm**: deterministic greedy, maximum-weight matching, small-component ILP, capped hybrid.
- **지표**: objective, exact handle F1, false merge, optimality status, component solve time, timeout rate, peak RAM.
- **제안 합격선**: ILP 또는 hybrid가 matching보다 truth metric을 악화시키지 않고, 전체 local p95/RAM band를 만족할 경로가 있음.
- **킬 조건**: ILP 이득이 없거나, 대부분 component가 cap을 넘어가거나, timeout incumbent를 사용해야만 성능이 나옴.
- **예산**: 로컬 CPU 1일; component 병렬도는 RAM watchdog 아래로 제한.
- **시드**: canonical tie-break; solver seed와 thread 수 고정.

### C6. calibration·F 개발 셀

- **가설**: raw rule score를 family-held-out truth에서 calibration하면 정보 해상도를 유지하면서 신뢰도를 맞출 수 있다.
- **데이터**: CubiCasa train 내부 rule-fit/calibration group split; val은 마지막 개발 확인.
- **arm**: uncalibrated score, Platt, isotonic, 조건부 beta; v0와 GBDT 비교군.
- **지표**: Brier, `REL`, `RES`, AUPRC, precision at frozen coverage threshold, reliability table.
- **제안 합격선**: `REL≤0.03`, `RES≥0.02`; F에서 `AUPRC_P1−AUPRC_v0≥0.15`; frozen operating point에서 `precision≥0.90`, `coverage≥0.50`.
- **킬 조건**: calibration group leakage, test로 calibrator 선택, 모든 method가 낮은 REL을 위해 거의 상수 확률만 출력하여 RES 미달.
- **예산**: 로컬 CPU 수시간; 대규모 threshold sweep 금지.
- **시드**: group split hash 고정; bootstrap 진단 seed는 manifest 파생, band 자체는 point estimate 규칙.

### C7. M metamorphic·sentinel 셀

- **가설**: 의미 보존 변환에서 wall verdict가 lineage 아래 안정적이며, 0-wall trivial detector가 통과하지 못한다.
- **데이터**: S metamorphic pack과 manifest가 지정한 실무 145장 M pack. 후자는 relation만 truth다.
- **지표**: relation별 handle flip, probability drift, 0-wall false positive, all/known-wall recall, transform lineage failure.
- **제안 합격선**: 전체 metamorphic handle flip `≤0.01`, 모든 sentinel 계약 충족.
- **킬 조건**: flip `>0.02`, 0-wall detector가 metric 정의상 PASS 가능, scale arm만 예외 처리해야 통과.
- **예산**: 로컬 CPU 1일; drawing streaming.
- **시드**: transform set·순서는 manifest hash로 고정; identity relation 포함.

### C8. scaling·resource 셀

- **가설**: spatial filtering과 component streaming으로 후보 edge가 실측상 quadratic으로 폭증하지 않고 resource band를 지킨다.
- **데이터**: entity 수가 단계적으로 증가하는 S scaling family, 1.dwg 정의 전량, 최대 `412,775` 선분 정의.
- **지표**: `n,m,k`, `m/n`, log-log 성장계수, largest component, p50/p95/end-to-end time, peak RSS, spill량.
- **제안 합격선**: local p95 `≤60초/도면`, peak RAM `≤32GB`, quadratic-growth 판정 없음.
- **킬 조건**: 후보 edge가 entity 수에 대해 실측상 quadratic 폭증, candidate overflow, 48GB 이전 watchdog abort. prune으로 숫자를 낮추고 recall을 잃으면 역시 실패.
- **예산**: 로컬 CPU 1–2일 예약; GPU/DGX 없음.
- **시드**: synthetic size family seed 고정; real drawing 순서는 manifest에 봉인.

### C9. 최종 동결·test 단발·독립 resolver 셀

- **가설**: 동결된 P1이 WSD-EVAL-v1의 모든 band를 동시에 통과한다.
- **선결**: C0–C8이 PASS이고 counsel, fidelity, leakage, hash gate가 닫힘.
- **데이터**: hidden S family, 동결 F test 400, 동결 M pack.
- **지표·합격선**: `F1_S≥0.95`, `AUPRC_F−AUPRC_v0≥0.15`, `precision_F≥0.90 at coverage≥0.50`, flip `≤0.01`, `REL≤0.03`, `RES≥0.02`, p95 `≤60초/도면`, RAM `≤32GB` 전부.
- **킬 조건**: hidden synthetic F1 `<0.85`, false merge `>0.05`, flip `>0.02`, quadratic edge 폭증. kill에 이르지 않은 단일 band 실패도 claim은 false다.
- **예산**: test 단발 로컬 CPU batch; 재실행은 infra failure가 cryptographic evidence로 확인될 때만 별도 invalid run으로 허용하고 결과 선택은 금지.
- **시드**: 모든 seed와 입력 순서 사전 봉인. resolver는 독립 환경에서 `wsd_eval_p1.json`을 한 번 생성한다.

---


---

## [calibration_P2] — # 6. 실험 셀 정의 (117 lines)

# 6. 실험 셀 정의

공통 원칙은 val 개발 허용, test 방법당 단발, 평가 전 band 봉인, shuffle control 의무, 증거 XLSX 의무다. 모든 시드는 제안 seed set {7, 17, 29, 43, 71}을 쓰고 split은 시드로 바꾸지 않는다. 95% CI는 drawing/block group을 resampling unit으로 한 paired cluster bootstrap으로 계산한다. bootstrap 반복 수는 제안값 10,000으로 봉인하며, P1과 P2의 동일 drawing 차이를 같은 resample에서 계산한다.

## Cell 0 — truth·license·split 선결 게이트

- 가설: S_exact와 F_exact의 truth provenance, license, leakage-free group split을 test 접촉 전에 고정할 수 있다.
- 지표: B1 fidelity verdict, truth provenance completeness, license_state, fingerprint overlap count, unresolved/ambiguous handle rate, test ledger.
- 합격선: 합성 fidelity PASS; F_exact가 vector-handle 또는 독립 line annotation으로 성립; counsel 서면 확인; split 간 block/geometry overlap 0; test ledger empty.
- 킬 조건: raster mask를 exact handle truth로 승격해야만 진행 가능한 경우, license 미해결, split dedupe 실패, truth/feature process 분리 실패.
- 예산: CPU 0.5–1 day와 counsel 대기. counsel 시간은 compute budget 밖이다.
- 시드: 없음. canonicalization은 결정적이어야 한다.

Cell 0가 FAIL이면 Cell 1의 synthetic-only 개발과 구현 unit test는 가능하지만 최종 claim resolution은 금지한다.

## Cell 1 — cheapest probe

- 가설: 500 synthetic block에서 P2 logistic 또는 boosted tree가 P1보다 ranking/precision–coverage를 개선할 최소 신호가 있고, 20 FloorPlanCAD drawing에서도 같은 방향이 관찰된다.
- 지표: S 개발 AUPRC, precision at wall recall 0.50, seed 분산, runtime/RSS. F 20은 F_exact가 성립할 때만 같은 지표를 사용하고, 그렇지 않으면 raster diagnostic으로 명확히 격하한다.
- 비교: frozen P1, P2 logistic, P2 boosted tree의 정확히 세 contender. supervised truth model은 이 셀에 넣지 않는다.
- 제안 합격선: 두 P2 중 하나가 S에서 P1보다 높은 point AUPRC를 보이고, seed 다수에서 방향이 같으며, memory soft cap을 지킨다. 이 셀은 최종 prereg lift band를 주장하지 않는다.
- 킬 조건: 두 P2 모두 P1 이하, positive anchor가 한 grammar에만 존재, 20 F 사용에 license/truth gate가 열리지 않음. 마지막 경우 F arm만 blocked이며 synthetic 결과로 F를 대체하지 않는다.
- 예산: local CPU 1 day, RAM peak 32GB 이하.
- 시드: 전체 seed set; P1은 결정적.

## Cell 2 — anchor와 LF 식별성 감사

- 가설: positive anchor는 고정밀이고, negative anchor는 명백한 annotation에 국한되며, LF family가 하나의 P1 prior를 중복 투표하지 않는다.
- 지표: anchor precision/recall, grammar별 anchor selection rate, P-vs-unanchored-true-positive 구분도, LF coverage/conflict, family mutual information, leave-one-family-out posterior 변화.
- 제안 합격선: positive anchor precision 0.98 이상, negative anchor precision 0.995 이상, 모든 preregistered supported wall grammar에 positive anchor가 존재, 단일 LF family 제거로 전체 U posterior의 25% 이상이 decision boundary를 넘지 않음.
- 킬 조건: 어떤 supported wall grammar의 anchor support 0, anchor precision band 미달, dependency를 모델링해도 한 LF family가 posterior를 사실상 독점.
- 예산: CPU 0.5 day, 32GB 이하.
- 시드: label-model initialization에 전체 seed set. family audit 결론이 seed에 따라 바뀌면 FAIL.

위 숫자는 제안 gate이며 실측 주장이 아니다. support가 너무 적은 grammar는 임의로 합치지 않고 unsupported로 표시한다. 최종 subgroup 판정 대상이 되려면 제안 기준 최소 30 wall handle과 5 drawing을 가져야 하며, 미달이면 해소 불가로 기록한다.

## Cell 3 — 모델 사다리와 weak-supervision 기여

- 가설: 반복/topology feature와 PU+label model을 결합한 P2가 P1 및 단순 P/N supervision보다 향상된다.
- 비교 arm:
  - P1 frozen
  - logistic P/N-only
  - logistic SCAR-PU
  - logistic nnPU+label model
  - tree P/N-only
  - tree BaggingPU
  - tree posterior-imputation P2
  - CubiCasa supervised 6-feature HGB reference
- 지표: val AUPRC, precision–recall curve, precision at wall recall 0.50, grammar recall, seed variance, class-prior sensitivity, runtime/RSS.
- 제안 합격선: main logistic/tree 중 적어도 하나가 P1 대비 S val 0.03, F val 0.03 이상의 point lift를 보이고 precision/coverage band를 달성; 모든 pi sensitivity point에서 lift 방향 동일.
- 킬 조건: main arm이 P/N-only arm을 못 이김, 결론이 class-prior interval에서 뒤집힘, logistic/tree 모두 seed 다수에서 P1 이하, 32GB soft cap 반복 위반.
- 예산: feature cache 후 CPU 1–2 days.
- 시드: 전체 seed set. hyperparameter 선택은 seed 평균과 최악 seed를 함께 고려.

Cell 3의 val lift는 모델 선택용 제안 기준이고 최종 claim의 0.05/0.03 band를 대신하지 않는다.

## Cell 4 — repetition·face·token ablation

- 가설: P2의 추가 lift는 raw layer shortcut이 아니라 repetition stability와 face/junction context에서 온다.
- arm: full geometry, minus-repeat, minus-face, minus-transform-stability, geometry-only no-token/no-layer, normalized-token, raw-layer diagnostic.
- 지표: AUPRC delta, long-parallel FP taxonomy, grammar recall, company/style OOD delta, feature permutation importance와 logistic coefficient stability.
- 제안 합격선: no-layer primary가 P1 대비 양의 lift를 유지; repeat 또는 face/stability family 제거 중 적어도 하나가 lift를 유의하게 줄이되, 그 family 단독 모델은 main보다 낮음.
- 킬 조건: raw layer 제거 시 AUPRC가 0.15 이상 하락, corpus-wide fingerprint ID를 넣어야만 lift 발생, repeated non-wall symbol subgroup recall/precision이 붕괴.
- 예산: cached feature로 CPU 1 day.
- 시드: 전체 seed set, 동일 split과 동일 sampled-row budget.

## Cell 5 — drawing/company/style shift calibration

- 가설: frozen shift-aware calibrator가 unseen group에서 global raw score보다 REL을 낮추면서 RES와 ranking을 보존한다.
- split: company metadata가 있으면 leave-one-company-out. 없으면 train geometry-only summary로 style cluster를 만들고 leave-one-cluster-out. cluster 생성에 label/token/vendor/path를 쓰지 않는다.
- 지표: Brier, REL, RES, calibration curve, AUPRC, ID 대비 OOD AUPRC drop, drawing-equal 결과.
- 제안 합격선: REL 0.03 이하, RES 0.02 이상, OOD AUPRC drop 0.10 이하, calibration 뒤 AUPRC ranking이 수치 오차 외에는 변하지 않음.
- 킬 조건: unseen group에서 REL band 실패, target label/prevalence를 알아야만 보정 가능, OOD drop 0.10 초과, style definition이 vendor/path shortcut에 의존.
- 예산: CPU 0.5–1 day.
- 시드: style clustering과 calibrator에 전체 seed set. cluster instability가 verdict를 바꾸면 FAIL.

## Cell 6 — M 안정성·sentinel·대리 독립성

- 가설: P2가 rigid/unit/scale/explode/layer rename에서 semantic prediction을 유지하고, 0벽/전벽 sentinel을 통과하며, proxy들이 같은 prior 하나를 반복하지 않는다.
- 지표: per-handle prediction agreement, probability deviation, sentinel precision/recall, S/F/C/E1.5/P1 간 동일-def disagreement tensor, LF family correlation.
- 제안 합격선: packet의 frozen M gate를 모두 PASS하고 0벽 sentinel FP=0, 전벽 sentinel recall 1.0. proxy independence는 대각선 우위/비대각선 붕괴와 동일-def 불일치가 보고 가능해야 한다.
- 킬 조건: 현재처럼 scale arm이 FAIL 상태로 남음, strict sentinel FAIL, 0벽 predictor가 안정성 점수만으로 통과, proxy independence audit가 산출되지 않음.
- 예산: CPU 1 day. 1.dwg 대형 definition stress는 별도 로그.
- 시드: model seed 전체; transform 자체는 deterministic paired manifest.

sentinel 합격선은 제안값이며, 현재 관측은 scale 0.7624 FAIL과 strict FAIL이므로 이 셀은 아직 통과하지 않았다.

## Cell 7 — frozen 최종 평가와 resolution

- 가설: 최종 no-layer P2가 frozen S_exact/F_exact에서 P1보다 사전등록 lift와 calibration/shift/leakage band를 모두 만족한다.
- 입력: SEALED model과 calibrator, immutable S_exact/F_exact test manifest, empty test-contact ledger. C_test는 외부 일반화 진단으로 한 번 함께 평가하되 F_exact 대체는 금지.
- primary 지표:
  - AUPRC_F(P2)가 AUPRC_F(P1)보다 0.05 이상 높음
  - AUPRC_S(P2)가 AUPRC_S(P1)보다 0.03 이상 높음
  - S_exact와 F_exact 각각에서 precision 0.92 이상인 operating point가 wall recall 0.50 이상
  - company/style OOD AUPRC drop 0.10 이하
  - S_exact와 F_exact 각각에서 REL 0.03 이하, RES 0.02 이상
  - 각 S/F lift의 paired 95% bootstrap CI lower bound가 0 초과
  - leakage audit PASS, M gate PASS
- subgroup 지표: preregistered wall grammar별 recall, repeated non-wall FP, curved/fragmented/nested-block recall.
- 킬 조건: deterministic P1 대비 lift CI lower가 0 이하, raw layer 제거 시 AUPRC 0.15 이상 붕괴, positive-anchor selection bias로 어느 supported wall grammar recall이 0.60 미만, 어느 필수 performance/shift/calibration/leakage/M band라도 실패.
- 예산: local CPU 1 day, 32GB 이하. 재시도 없음.
- 시드: frozen ensemble. seed별 결과도 공개하지만 ensemble 하나만 final contender.

최종 verdict는 모든 AND 조건을 통과할 때만 pass다. truth 또는 license gate가 열리지 않았으면 open, test를 열고 band를 실패했으면 fail이다. 부분 통과를 평균내 candidate pass로 만들지 않는다.

## Cell 8 — shuffle·shortcut 음성 대조

- 가설: pipeline이 split/handle/layer leakage만으로 높은 점수를 만들지 않는다.
- arm: train label permutation, LF-row permutation within drawing, geometry fingerprint randomized across groups, token-only, group-id-only forbidden-feature canary.
- 지표: AUC/AUPRC 대비 prevalence, calibration, forbidden feature detector, split overlap.
- 제안 합격선: permutation과 canary arm이 chance-compatible하고 forbidden ID column count 0.
- 킬 조건: shuffle control이 유의한 ranking을 보임, group-id/token-only가 main lift 대부분을 재현, canary가 feature matrix에 남음.
- 예산: CPU 0.5 day.
- 시드: 전체 seed set.

Cell 8은 test 전 val에서 의무 통과하고, final evaluator가 schema/column audit을 다시 수행한다. 다이제스트의 기존 shuffle AUC 0.375 PASS는 현재 6-feature 경로의 증거일 뿐 새 P2 feature와 split의 면책이 아니다.


---

## [calibration_P3] — ## 6. 실험 셀 정의 (101 lines)

## 6. 실험 셀 정의

### 6.1 공통 split·metric·CI 규칙

- Xref 연결 family, canonical block family, synthetic template와 모든 parameter variant는 같은 fold다.
- near-duplicate geometry fingerprint 충돌도 같은 fold로 합친다.
- handle, 순번, filename, block/layer/text name은 feature에 없다.
- val은 tuning 가능하되 test는 최종 한 번만 접근한다.
- F formal primary는 pooled per-handle `AUPRC_F`; drawing-macro AUPRC는 보조다.
- S formal metric은 per-handle node F1과 candidate-universe pair F1이다.
- `B*`는 동일 F universe에서 동결된 `max(P1, P2, HistGradientBoosting, 기타 사전등록 비-GNN baseline)`이다. packet의 F1과 새 AUPRC를 서로 비교하지 않는다.
- lift는 `AUPRC_F(P3)-AUPRC_F(B*)`다.
- CI는 동일 drawing/family를 paired cluster로 재표본하는 고정 95% stratified bootstrap을 사용한다. 제안 설계값으로 10,000 replicate와 고정 bootstrap seed를 manifest에 봉인한다. 개별 line을 독립 표본처럼 bootstrap하지 않는다.
- style cluster는 label을 보기 전에 geometry/block 통계로 train에서 정의하고 family 전체를 한 cluster/fold에 둔다.
- formal band는 패킷대로 `AUPRC_F>=B*+0.05`, S node `F1>=0.92`, S pair `F1>=0.80`, style-OOD AUPRC drop `<=0.10`, `REL<=0.03`, `RES>=0.03`, peak RAM `<=48GB`, `P3_lift_CI_low>0`이다.
- 별도 hard gate는 known synthetic relation recall `>=0.98`과 production p95 edge/memory envelope 준수다.

### Cell E0 — 선결조건 및 truth readiness

- **가설:** P3가 학습하기 전에 S/F truth와 권리, proxy 독립성이 유효한 상태로 고정될 수 있다.
- **입력:** PR-1 wall generator, CL-C/WSD-EVAL-v1 contract, PR-2 동일-def proxy audit, PR-3 counsel 문서, P1/P2 baseline manifest.
- **지표:** T2 fidelity status, truth provenance completeness, proxy disagreement matrix completeness, counsel status, family collision count, baseline availability.
- **제안 합격선:** 프로그램이 별도로 봉인한 T2 fidelity gate가 PASS이고, `family_collision=0`, counsel이 F/C 학습과 derived weight 범위를 서면 허용하며, proxy audit와 P1/P2 artifact가 존재한다. 패킷에 없는 fidelity 수치를 이 문서가 임의로 “통과선”으로 만들지 않는다.
- **킬 조건:** generator label이 detector prior에서 파생됨, wall truth가 실제로 없음, counsel이 학습/derived weight를 허용하지 않음, proxy 독립성 감사를 수행할 수 없음. 이 경우 full P3를 중단한다.
- **예산:** 주로 local CPU/audit 및 외부 counsel 대기. 학습 GPU 0.
- **seed 계획:** 해당 없음. 모든 manifest는 content hash로 결정적이어야 한다.

### Cell E1 — Graph IR adjacency·폭증 감사

- **가설:** typed builder가 known synthetic containment/instancing/intersection/proximity/parallel/collinearity를 거의 완전하게 회수하면서 production graph envelope 안에 머문다.
- **입력:** train-family synthetic relation truth, held-out synthetic audit families, 1.dwg stress definitions.
- **지표:** relation type별 candidate recall, micro recall, unresolved Xref, edge/node ratio, node별 fanout quantile, build peak RAM, maximum-shard size, p95 envelope 초과율.
- **제안 합격선:** support가 있는 모든 required relation type과 micro known-relation recall이 각각 `>=0.98`; peak RAM `<=48GB`; frozen production p95 envelope 안; unresolved required reference 0.
- **킬 조건:** recall `<0.98`, relation cap을 풀어야만 recall이 나와 edge/RAM envelope를 넘음, 최대 graph를 shard해도 truth pair/context를 보존하지 못함.
- **예산:** local CPU/RAM 중심, 약 1일 목표(계획값). GPU 불필요.
- **seed 계획:** builder는 deterministic. 동률 top-k tie-break는 geometry hash를 사용하고 handle/order를 사용하지 않는다.

### Cell E2 — Cheapest 3-layer probe

- **가설:** 작은 동일 architecture에서 SSL initialization이 no-pretrain보다 낫고 P2 대비 상승 신호를 보인다.
- **입력:** synthetic 1,000 block의 node/pair truth, family-disjoint 실무 20장 비라벨 graph. generator가 준비되지 않으면 이 cell은 BLOCKED다.
- **팔:** `(A) no pretrain -> joint fine-tune`, `(B) masked+contrastive pretrain -> 동일 joint fine-tune`, 그리고 동결 P2 비교.
- **지표:** S development node F1, pair F1, AUPRC, P2 대비 delta, peak GPU/RAM, graph recall. 이 cell에서 test와 F formal held-out은 열지 않는다.
- **제안 합격선:** B가 A와 P2 모두보다 development AUPRC/F1에서 방향성 양의 이득을 보이고 compute envelope를 지킨다. 단일 seed이므로 formal claim이나 CI PASS로 사용하지 않는다.
- **킬/중단 조건:** adjacency gate 실패, 최소 sampled config도 16GB에서 지속 OOM, B가 A/P2보다 모두 나쁘고 오류 분석에서도 구현 결함이 없음. 후자의 경우 DGX escalation을 중단하되 formal claim은 “단일 seed로 해결”하지 않는다.
- **예산:** RTX 5070 Ti, pretrain 유/무 각 1회, 약 1 GPU-day 이내 목표(계획값).
- **seed 계획:** 패킷의 “각각 한 번”을 지켜 seed `17` 한 번.

### Cell E3 — 비-GNN baseline·leakage·shuffle 동결

- **가설:** P3 lift를 비교할 동일 truth universe의 강한 비-GNN baseline이 재현되고, identifier/family leakage가 제거된다.
- **팔:** fast_score, logistic, six-feature HistGradientBoosting, P1, P2; primary structural GNN; 이름/레이어/text content를 의도적으로 연 diagnostic arm; label shuffle arm.
- **지표:** 동일 F/C development AUPRC/F1, S metric, family collision, source classifier accuracy, leaky-vs-masked delta, permutation-null 위치.
- **제안 합격선:** 모든 baseline이 동일 exclusion과 split hash를 사용하고 `B*`가 freeze됨; family collision 0; primary feature allowlist에 식별자/이름 0; shuffle 결과가 사전 생성한 permutation null의 중앙 95% 범위 안.
- **킬 조건:** 이름을 가리면 baseline/P3 universe가 달라짐, near-duplicate/template가 fold를 가로지름, shuffle가 null 밖의 유의한 신호를 반복해서 보임, P1/P2를 동일 metric으로 실행할 수 없음. 이때 test 진입 금지다.
- **예산:** CPU baseline + local GPU diagnostic, 약 1–2일 목표(계획값).
- **seed 계획:** learned model `{17,29,43}`; permutation seed 목록은 label을 보기 전에 manifest에 봉인한다.

### Cell E4 — Self-supervised ablation과 제한 HPO

- **가설:** label 없는 train-family graph에서 배운 masked/transform representation이 family-held-out node 과업으로 전이되며, 단순 random initialization 이상의 이득을 낸다.
- **팔:** no-pretrain, mask-only, contrastive-only, mask+contrastive; HGT와 R-GCN architecture check.
- **지표:** F/C development AUPRC, S node/pair F1, family-bootstrap lift, seed variance, transform consistency, representation collapse/oversmoothing 진단.
- **제안 합격선:** mask+contrastive가 no-pretrain보다 seed-aggregate development lift의 CI 하한이 양수이고 S gate를 악화시키지 않음. transform consistency는 올라가되 all-node embedding variance가 붕괴하지 않아야 한다.
- **킬 조건:** family dedupe 후 SSL lift CI 하한 `<=0`, shuffled/renamed identifiers가 lift를 설명함, depth가 늘수록 embeddings가 붕괴하고 shallow model도 회복하지 못함. supervised HGT만 이기고 SSL이 기여하지 않으면 **self-supervised P3라는 제안은 실패**로 기록하고 별도 제안으로 재프리레그한다.
- **예산:** full-corpus pretraining/HPO이므로 DGX 비-vLLM 시간대만 사용. DGX unreachable이면 BLOCKED.
- **seed 계획:** screening 후 `{17,29,43}`. HPO cell마다 seed 하나로 줄이는 경우 최종 후보는 세 seed 전부 재학습한다.

### Cell E5 — S node/relation joint 학습과 F/C 전이

- **가설:** pair supervision이 node membership을 안정화하고, S에서 학습한 구조가 F/C node truth로 전이된다.
- **팔:** node-only, pair-only diagnostic, joint node+pair; train source `{S only, F/C node only, S+F, S+C}`를 분리한다. silver arm은 없다.
- **지표:** S node F1, S candidate recall/pair F1, F/C AUPRC, source별 loss, cross-source train×eval matrix, node/pair prediction consistency.
- **제안 합격선:** development readiness에서 S node `F1>=0.92`, S pair `F1>=0.80`; joint가 node-only보다 F development AUPRC를 해치지 않고 relation error를 줄임; truth source별 metric을 별도 보고.
- **킬 조건:** pair candidate recall은 높지만 pair head가 band에 못 미침, pair loss가 node 성능을 악화, S 대각 성능만 높고 F/C 비대각 lift가 소멸, F projection invalid.
- **예산:** local small run 후 DGX full multi-seed, 약 1–2 GPU-day 목표(계획값).
- **seed 계획:** `{17,29,43}`, 최종은 고정 logit-mean bundle.

### Cell E6 — OOD·calibration·compute freeze rehearsal

- **가설:** P3의 lift가 style family 밖에서도 유지되고, 확률과 compute가 production gate를 만족한다.
- **입력:** development/style-OOD/calibration family만 사용하며 final test는 닫아 둔다.
- **지표:** IID와 style-OOD AUPRC 및 drop, temperature 전후 REL/RES, S node/pair band, peak CPU RAM/GPU memory, p95 edge envelope, family-bootstrap lift CI, name/layer/text ablation.
- **제안 합격선:** development rehearsal에서 formal band 전부 충족: lift `>=0.05`, lift CI low `>0`, style drop `<=0.10`, `REL<=0.03`, `RES>=0.03`, S node/pair band, graph recall, RAM band.
- **킬 조건:** best classical 대비 lift CI 하한 `<=0`, style drop 초과, calibration band 실패, production p95에서 edge/memory envelope 초과. calibration 실패를 threshold 재탐색으로 덮지 않는다.
- **예산:** local evaluation + DGX checkpoint inference, 약 1일 목표(계획값).
- **seed 계획:** frozen three-model bundle; calibration은 별도 seed 없이 deterministic optimizer와 manifest로 고정.

### Cell E7 — Frozen held-out 단발 해소

- **가설:** 모든 pretest gate를 통과한 P3가 실제 frozen held-out에서 전체 resolution contract를 만족한다.
- **진입 조건:** E0–E6 PASS, graph/split/model/calibration/baseline/evidence schema hash 동결, test access counter 0.
- **절차:** S held-out, F held-out, style-OOD held-out을 한 job manifest에서 한 번만 열고 P3와 `B*`를 같은 handle universe에서 paired 평가한다.
- **최종 합격선:** `AUPRC_F>=B*+0.05`; S node `F1>=0.92`; S pair `F1>=0.80`; style-OOD drop `<=0.10`; `REL<=0.03`; `RES>=0.03`; known-relation recall `>=0.98`; peak RAM `<=48GB`; production p95 envelope 준수; `P3_lift_CI_low>0`. 모두 AND다.
- **킬 조건:** 하나라도 false, model/manifest hash 불일치, test access count가 1보다 큼, evidence workbook 누락. 결과를 보고 threshold나 graph를 바꿔 재실행하지 않는다.
- **예산:** frozen inference 1회와 paired bootstrap. 추가 tuning budget 0.
- **seed 계획:** E6에서 봉인한 model bundle과 bootstrap seed만 사용.

### 6.2 Sentinel과 실패 기록

0벽 graph와 전벽 graph를 S에 포함한다. 0벽에서는 false positive가, 전벽에서는 recall collapse가 직접 드러나야 한다. metamorphic 위반율만 낮은 “항상 0벽” 모델은 PASS가 아니다. graph construction 실패, projection ambiguity, OOM, missing Xref, license block은 표본에서 삭제하지 않고 denominator와 failure sheet에 남긴다.


---

## [calibration_P4] — ## 6. 실험 셀 정의 (117 lines)

## 6. 실험 셀 정의

### 공통 평가 규칙

- **arm**: `best_vector`, `raster_only`, `fusion`, `shuffle_raster`. 필요한 ablation은 개발용이며 최종 claim arm을 바꾸지 않는다.
- **primary unit**: 원 drawing에 속한 IR handle 1개. pixel metric은 진단용 별도 sheet다.
- **strata**: `curved`, `hatch`, `single_line`을 generator metadata/IR type로 outcome 이전에 정의한다. 세 stratum을 합쳐 평균내지 않고 각각 통과시킨다. 겹치는 handle은 각 해당 stratum에 보고하되 전체 metric에는 한 번만 센다.
- **uncertainty**: building/drawing cluster paired bootstrap. crop이나 pixel을 독립 표본으로 세지 않는다.
- **seed 계획**: 제안 seed `{17,29,43}`. hyperparameter screen은 17만 쓰고, 동결 구성은 세 seed 평균을 하나의 ensemble method로 정의한다. test 후 seed 선택은 금지한다.
- **test 단발**: 모든 최종 데이터 source의 test evaluation을 한 orchestrated run으로 열고 access count를 1로 남긴다. 실패 후 재학습은 새 method version과 새 prereg가 필요하다.

아래 시간·자원 수치는 제안 예산이다.

### Cell P4-0 — 법률·진리·baseline 선결 gate

- **가설**: P4가 사용할 truth와 `best_vector`가 평가 전에 독립적으로 동결 가능하다.
- **입력**: CL-C generator status, counsel 문서, vector 후보의 val-only 결과, split manifest.
- **지표**: generator fidelity status, exact `wall_member(h)` 존재율, license decision, handle-universe hash 일치, test access count.
- **제안 합격선**: CL-C/PR-1 fidelity `PASS`; counsel이 각 외부셋의 training/eval/weight 보관을 서면 허용하거나 해당 arm을 제거; `best_vector` hash와 handle universe 동결; test access 0.
- **킬 조건**: fidelity FAIL/미실행, 벽 handle truth 부재, NC product-path 격리 불가, baseline이 test를 이미 본 경우.
- **예산**: CPU·문서 감사 반나절~1일, GPU 0.
- **시드**: 없음.
- **산출**: `PRECONDITION_PASS` 또는 구체적 `OPEN/FAIL`. OPEN 상태에서는 P4-1의 순수 geometry unit test 외 성능 셀을 실행하지 않는다.

### Cell P4-1 — CRS·crop·collision 결정성 harness

- **가설**: model과 무관하게 pixel↔handle relation을 exact하게 복원할 수 있다.
- **입력**: analytic micro-scenes와, fidelity 판정에는 쓰지 않는 최소 geometry fixtures. straight/curve, clipping, scale/unit, rotate/reflect/translate, nested INSERT, 한 pixel 다중 handle, subpixel thin line을 포함한다.
- **지표**: `MAPACC`, `CRS_error`, round-trip point error, collision tuple recall/precision, IR geometry hash 보존, ID-randomization logits equality.
- **제안 합격선**: 전체와 각 transform/collision stratum에서 `MAPACC≥0.995`; `CRS_error≤0.5%`; handle/geometry hash 변화 0; ID buffer permutation 전후 logits 불변.
- **킬 조건**: CRS/back-projection 오류 0.5% 초과, 단일-ID winner로 collision 소실, crop 역변환이 원 fold/handle을 바꿈, ID가 network tensor에 들어감.
- **예산**: 로컬 CPU 1일, 작은 GPU smoke test 1시간 이내.
- **시드**: deterministic; rasterization stochasticity가 있으면 오류로 처리한다.
- **주의**: 이 셀 PASS는 성능 증거가 아니라 측정기 자격이다.

### Cell P4-2 — 200-block cheapest probe

- **가설**: 작은 raster branch가 P2/P3 또는 현재 최강 vector가 놓친 curved·hatch·single-line handle에서 독립 lift 신호를 보인다.
- **입력**: fidelity-PASS base block 200개×render style 4개. geometry group split과 style-family holdout을 동시에 적용한다.
- **arm**: frozen `best_vector`, small U-Net raster, convex fusion, label-shuffled raster.
- **지표**: stratum별 handle AUPRC difference, 전체 handle AUPRC difference, Brier, REL/RES, MAPACC, unseen-style drop, zero/all-wall sentinel confusion.
- **제안 합격선**: full claim band를 조기 확인하되 표본 부족 시 PASS가 아니라 `INCONCLUSIVE_CONTINUE`만 허용한다. 즉 각 stratum point lift `≥0.08`, 전체 non-inferiority lower bound `≥-0.02`, MAPACC `≥0.995`, style drop `≤0.10`, REL `≤0.04`, RES `≥0.02`이면 확대한다. 각 유리 stratum의 paired CI 하한은 0보다 커야 한다.
- **킬 조건**: mapping 오류 초과, fusion 전체 하락이 0.02 초과, 세 stratum 모두 lift CI 하한이 0 이하, shuffle arm이 일관된 신호를 보임, NC 격리 실패.
- **예산**: local render+GPU 1일, 작은 모델만; DGX 0.
- **시드**: 17로 smoke/screen, 동결 구성 17·29·43. style split 자체 seed는 manifest에 하나로 고정한다.
- **결정**: 한 stratum만 유리하면 그 stratum을 사후 재정의해 claim을 축소하지 않는다. 새 claim은 별도 prereg다.

### Cell P4-3 — CubiCasa representation 개발

- **가설**: 실제 사람 라벨 raster context가 긴 평행 hard negative와 wall edge를 vector feature와 다른 방식으로 분리한다.
- **입력**: 고정 train 4,200에서 fit/cal-A/cal-B, val 400; test 400은 닫아 둔다. 386만 train 선분은 drawing group으로만 분할한다.
- **arm**: U-Net과 ResNet-18-FPN screen, `best_vector`, raster-only, fusion, shuffle control. 큰 encoder는 제외한다.
- **지표**: pixel AUPRC(진단), SEG-IR line/handle-like AUPRC, hard-negative class별 error, Brier/REL/RES, drawing-macro와 pooled metric, runtime/VRAM.
- **제안 합격선**: val에서 fusion이 전체 handle-like AUPRC `best_vector-0.02` 이상이고, 사전 benefit strata에 방향성 lift가 있으며, REL/RES band를 통과해야 P4-4로 간다. shuffle arm은 constant prevalence 대비 의미 있는 lift가 없어야 하고 AUROC는 chance와 양립해야 한다.
- **킬 조건**: architecture를 바꿔도 raster-only와 fusion이 vector error를 복제하고 전체가 0.02 초과 하락; crop leakage 발견; shuffle control 이상; memory가 512 patch에서도 로컬 계획을 불가능하게 함.
- **예산**: 로컬 GPU screen 1일, 선택 구성 3-seed 재학습 1일, RAM 64GB 내 streaming.
- **시드**: 17 screen, 17·29·43 locked rerun. seed별 성적을 숨기지 않고 ensemble과 함께 보고한다.
- **해석 제한**: CubiCasa PASS만으로 native-DWG handle claim을 해결하지 않는다.

### Cell P4-4 — Held-out calibration·fusion

- **가설**: raster와 vector의 상보성이 단순 convex fusion으로 보존되고, 확률 calibration gate를 만족한다.
- **입력**: P4-3에서 동결된 branch logits; cal-A/B와 val.
- **비교**: uncalibrated branches, branch-calibrated vector/raster, convex fusion. isotonic 등 고자유도 방식은 sample 부족 시 제외한다.
- **지표**: Brier(primary score type), REL, RES, handle AUPRC, Expected Calibration Error는 참고만, `α`, missing-raster 비율.
- **제안 합격선**: val fusion `REL≤0.04`, `RES≥0.02`; 전체 AUPRC non-inferiority; 어느 benefit stratum에서도 vector보다 방향이 뒤집히지 않음. 동률이면 더 작은 raster weight를 채택한다.
- **킬 조건**: calibration을 맞추면 resolution이 무너짐, `α=0`이 최선인데도 raster claim을 유지해야만 성능이 나옴, cal-A/B를 합쳐야 gate를 통과함, val을 calibrator fit에 재사용함.
- **예산**: CPU 수 시간, 추가 GPU inference 1회 이하.
- **시드**: branch 3-seed ensemble logits에 단일 calibrator; seed별 calibration도 보조 보고.

### Cell P4-5 — OOD style·metamorphic·proxy 독립성

- **가설**: lift가 특정 renderer의 stroke/alias artifact가 아니며, 다른 truth source와의 불일치가 측정 가능하다.
- **입력**: unseen synthetic style+unseen geometry, CubiCasa val, counsel-cleared FloorPlanCAD pixel arm, 1.dwg unlabeled operational arm.
- **지표**: seen→unseen style handle AUPRC drop, rigid/unit/scale transform score drift, MAPACC, source별 error overlap·3원 disagreement table, zero/all-wall sentinel, FloorPlanCAD pixel/line metric, 1.dwg runtime·peak memory·geometry hash.
- **제안 합격선**: unseen render-style AUPRC 하락 `≤0.10`; MAPACC/CRS gate 유지; rigid transform에서 handle ranking과 frozen-threshold label이 보존; zero-wall sentinel에서 양성 0, all-wall sentinel recall 제안선 0.95 이상; source별 결과를 평균 하나로 합치지 않음.
- **킬 조건**: style drop 초과, scale/crop에서 mapping 오류, sentinel collapse, 합성·CubiCasa·FloorPlanCAD가 같은 평행 prior 오류만 반복해 독립 이득이 없음, 1.dwg에서 geometry를 수정해야만 실행 가능.
- **예산**: 로컬 CPU/GPU 1일; FloorPlanCAD는 counsel 전 0실행; DGX 0.
- **시드**: 17·29·43 ensemble 고정. OOD style 선택은 결과를 보기 전에 고정한다.
- **주의**: packet에 FloorPlanCAD native handle mapping이 없으므로 해당 결과는 최종 handle gate가 아니다.

### Cell P4-6 — 봉인된 최종 단발 판정

- **가설/claim**: P4가 curved, hatch, single-line 각각에서 `best_vector`를 개선하고 전체 비열등성·mapping·OOD·calibration gate를 모두 통과한다.
- **선행 freeze**: render manifest, CRS contract, test handle universe, model hash-of-hashes, `best_vector` hash, calibrator/`α`/`τ`, strata, bootstrap code, JSON schema.
- **primary 지표와 합격선**:
  - curved, hatch, single-line **각각** handle AUPRC point lift `≥0.08` 및 paired CI 하한 `>0`.
  - 전체 handle AUPRC difference의 non-inferiority 하한 `≥-0.02`.
  - synthetic `MAPACC≥0.995`, 즉 CRS error `≤0.5%`.
  - unseen render-style AUPRC 하락 `≤0.10`.
  - handle probability `REL≤0.04`, `RES≥0.02`.
  - 최종 handle/geometry가 IR과 동일하고 NC artifact가 product weight path와 분리됨.
- **보조 지표**: pixel AUPRC/IoU, F1/precision/recall at frozen `τ`, drawing-macro metric, error taxonomy. 보조 지표는 실패한 primary gate를 구제하지 못한다.
- **킬 조건**: 위 결합조건 중 하나라도 거짓, 필요한 stratum에 positive/negative가 없어 AUPRC가 정의되지 않음, artifact/hash 누락, test access가 1을 초과함. 표본 부족은 PASS가 아니라 `OPEN`이다.
- **예산**: 모든 test source를 여는 orchestrated inference 1회와 report 생성; 재학습 0.
- **시드**: 동결 3-seed ensemble 하나. test 후 best seed 선택 금지.
- **산출**: `wsd_eval_p4.json`, evidence xlsx, model/render/CRS manifest. 실제 실행 전에는 생성하지 않으며, resolution trigger는 이 세 hash가 동결된 뒤 JSON이 생성되는 순간이다.

### 판정 논리

```text
PASS = preconditions
   AND every(curved, hatch, single_line lift point >= 0.08)
   AND every(benefit-stratum lift CI lower > 0)
   AND overall AUPRC NI lower >= -0.02
   AND MAPACC >= 0.995
   AND unseen_style_drop <= 0.10
   AND REL <= 0.04
   AND RES >= 0.02
   AND geometry_is_IR_original
   AND NC_registry_isolated
   AND test_access_count == 1
```

이 conjunctive 논리는 평균 점수나 좋은 pixel metric으로 한 gate의 실패를 상쇄하지 않는다.

---


---

## [calibration_P5] — ## 6. 실험 셀 정의 (65 lines)

## 6. 실험 셀 정의

공통 원칙: val=개발·튜닝 허용, test=방법당 단발, 셔플 대조군 의무, 실패도 사유 기록.

### Cell P5-A — Admission gate only

- **가설**: 현재 E1.5 산출이 `E15_B1≥0.70` ∧ `E15_B4≥0.70`을 만족한다 (또는 명시적 미달).
- **지표**: E15_B1, E15_B4; 참고로 다이제스트 B5 Pearson 0.2911은 B4 미달 정성 신호.
- **합격선**: 두 밴드 모두 통과 시에만 P5-B 오픈.
- **킬**: 어느 한쪽 실패 → likelihood silver 경로 중단 (제안 원문 kill).
- **예산**: CPU <2h · API 0.
- **시드**: n/a (결정론 집계).

### Cell P5-B — Cheapest truth-conditioned probe

- **가설**: Frozen prompt jury가 synthetic exact handles에서 HallRate≤0.01, 초벌 calibration이 REL/RES 방향성 후보를 보인다.
- **지표**: HallRate, top-tier Jaccard, 4/5 coverage, REL/RES (jury soft scores 있으면).
- **합격선**: HallRate≤0.01; Jaccard≥0.50; coverage≥0.30 (표본 150 내 예비).
- **킬**: HallRate>0.01 → 전체 handle 경로 폐기; Jaccard 실패 → handle 학습 중단.
- **예산**: 100 synth + 50 FPC render CPU; frontier 150 calls (승인 시) 또는 local open VLM을 *jury 대리*로 한 **비공식** sanity(공식 silver 아님).
- **시드**: render seed 0; judge temperature 0 동결.

### Cell P5-C — Family-aware vs naive consensus ablation

- **가설**: cross-family AND 규칙이 within-family echo를 줄여 HallRate를 낮춘다.
- **지표**: HallRate, jac_bar, student 후속 lift 차이.
- **합격선**: 예비 — 공식 승격 규칙은 A(cross-family)를 default로 채택할 근거(HallRate 개선 또는 동일·coverage 손실 ≤0.05).
- **킬**: 없음(정보 셀); 다만 A·B 모두 HallRate>0.01이면 P5-B kill 승계.
- **예산**: P5-B 산출 재집계 위주.
- **시드**: 동일 frozen outputs 재분석.

### Cell P5-D — Student LoRA probe (local 3B)

- **가설**: E1.5+consensus 통과 silver로 학습한 student가 독립 S/F·FPC holdout에서 `AUPRC_F≥best_nonVLM+0.03`, `REL≤0.04`, `RES≥0.02`, lift CI_low>0.
- **지표**: AUPRC_F, REL, RES, bootstrap CI, shuffle control AUC.
- **합격선**: prereg 밴드 전부.
- **킬**: lift CI_low≤0 또는 HallRate>0.01 → handle 경로 폐기; 1-epoch에서 already confirmation-only(셔플 대비 무의미)면 early stop.
- **예산**: 5070 Ti 1–2일; seeds {0,1,2}; epochs∈{1,3}.
- **시드**: 3 seeds; best on val only; **test single shot**.

### Cell P5-E — Anti-silver control (CL-K 정합)

- **가설**: gate-only(비-VLM) ≥ silver-distill student on independent truth — 즉 silver가 오염.
- **지표**: 동일 eval; ΔAUPRC(student − gate-only).
- **합격선**: student가 gate-only 대비 양의 lift CI_low>0일 때만 silver 학습 유지.
- **킬**: Δ≤0이면 "silver=오염" 쪽(feyerabend P3)에 증거 가중 → P5 student 경로 PARK, jury-as-audit만 잔존 가능.
- **예산**: P5-D와 공유 eval.
- **시드**: 동일.

### Cell P5-F — Weak-feature injection into P2/P3 (optional merge)

- **가설**: VLM vote/embedding을 GBDT 7번째 특징으로 넣으면 F1/AUPRC가 비-VLM 대비 +δ (δ prereg: AUPRC +0.03 동일).
- **지표**: AUPRC_F, F1; 누출 검사용 name-ablation.
- **합격선**: P5-D와 동일 lift 밴드; SoT 미사용.
- **킬**: ablation에서 이름/silver 순환만으로 성적 상승 시 특징 폐기.
- **예산**: CPU GBDT 재학습 (386만행급은 CubiCasa 경로; P5 silver 규모에 맞춰 축소 가능).
- **시드**: {0,1,2}.

### Cell P5-G — DGX full FT (PARK until reachable)

- **가설**: 대형 local VLM이 3B LoRA probe의 lift를 유의하게 확대.
- **합격선 / 킬**: P5-D 생존 후에만 오픈; DGX 미달이면 실행 안 함.
- **예산**: 예약 야간; Ornith vision 확인(T13) 선행.

---


---

## [calibration_P6] — ## 6. 실험 셀 정의 (102 lines)

## 6. 실험 셀 정의

공통 원칙: **val=개발·튜닝 허용, test=방법당 단발, 합격선 프리레그 봉인, 셔플 대조군 의무, 증거 xlsx, 실패도 기록**.  
수치 band는 제안 prereg 초안을 동결한 것(새 측정 아님).

### Cell-0 — Verifier soundness gate (P6 착수 조건)

| 항목 | 내용 |
|------|------|
| **가설** | 독립 mutation pack에서 verifier FAR≤0.01, FRR≤0.05를 만족하는 \(V\)가 존재한다. |
| **지표** | FAR, FRR, n_mutations; exact gate 재현성(시드 고정). |
| **합격선** | FAR≤0.01 ∧ FRR≤0.05 ∧ PR-1/WSD-EVAL-v1 동결 완료. |
| **킬 조건** | FAR>0.01 → **verifier 경로·P6 전체 중단**(제안 kill). FRR>0.05는 verifier 재설계 없이 정책 학습 금지. |
| **예산** | 로컬 CPU; PR-1 완료 후 1일. |
| **시드** | soundness_pack seeds {0,1,2}. |

### Cell-A — Reward family ≠ Hidden family 분리 감사

| 항목 | 내용 |
|------|------|
| **가설** | 정책 학습에 노출된 generator family와 hidden family의 식별자가 파이프라인상 교차되지 않는다. |
| **지표** | manifest diff; 정책 로그에 hidden id 출현 횟수=0; train/hidden 특징 분포 TV(참고, B1 TV 0.265는 현 합성 한계). |
| **합격선** | 교차 0건; test gate variant 미노출. |
| **킬** | 교차 발견 시 학습 로그 폐기·재동결. |
| **예산** | 0.5일. |
| **시드** | n/a(감사). |

### Cell-B — Cheapest probe: offline contextual bandit (full RL 금지)

| 항목 | 내용 |
|------|------|
| **가설** | 합성 1,000 state·5 arms offline bandit이 fixed router 및 uncertainty heuristic 대비 **평균 compute ≥20% 절감**하고, 최종(또는 val proxy) AUPRC 감소 ≤0.01. |
| **지표** | mean compute cost, mean latency, AUPRC(handle), Brier(train reward-visible), arm 선택 분포, IPS/DR utility. |
| **합격선** | saving≥0.20 ∧ AUPRC drop≤0.01 vs 두 baseline 모두(또는 prereg에 “둘 다”로 명시한 대로). Verifier Cell-0 PASS 전제. |
| **킬** | saving<0.20 → **policy/acquisition 경로 중단**(제안). AUPRC drop>0.01 → 중단. FAR 회귀 시 중단. |
| **예산** | 로컬 1일; GPU는 VLM arm 소량만. |
| **시드** | state_gen {10,20,30}; policy {100,200}; 보고는 median±IQR. |
| **금지** | full RL, hidden family 튜닝, test 단발 소비. |

### Cell-C — Horizon 진단: greedy vs beam / value of multi-step (학습 0)

| 항목 | 내용 |
|------|------|
| **가설** | 추가 probe의 정보가치가 H=1에 거의 흡수되지 않는다(즉 multi-step가 필요). |
| **지표** | 동일 예산에서 greedy(단회 best arm) utility vs beam/depth-H planning utility; “greedy≈상한”이면 RL 불요(패널 CL-H). |
| **합격선(RL 존속)** | \(\mathrm{utility}_{multi}/\mathrm{utility}_{banditH1} \ge 1.05\) **또는** 동일 계산의 RL lift 사전 프록시 ≥1.05. |
| **킬** | lift<1.05 → **full-RL 경로 중단**, bandit에서 동결(제안). |
| **예산** | 로컬 1일; 학습 0(열거·시뮬). |
| **시드** | {11,22,33}. |

### Cell-D — Bandit on-policy 소량 적응 (합성 simulator)

| 항목 | 내용 |
|------|------|
| **가설** | Offline에서 고른 π를 소량 on-policy로 다듬어도 val proxy에서 band 유지. |
| **지표** | Cell-B와 동일 + 정책 entropy, VLM arm 비율(편향 감시). |
| **합격선** | Cell-B band 유지; VLM arm 비율이 cost 테이블상 비합리적 쏠림(예: >사전 등록 상한)이면 λ 재조정 후 1회만 재시도. |
| **킬** | Goodhart: train Brier↑ & val AUPRC↓; 또는 VLM 편향 미해소. |
| **예산** | 로컬 1–2일. |
| **시드** | {40,41,42}. |

### Cell-E — Hidden synthetic + FloorPlanCAD 봉인 평가 (단발)

| 항목 | 내용 |
|------|------|
| **가설** | Claim 성립: semantic 비열등∧compute≥20% 절감. Hidden에서 reward/semantic 동향 일치. |
| **지표** | AUPRC, compute saving, verifier FAR 재확인, `utility` if RL; CubiCasa **test**는 별도 단발 슬롯(쓰면 소진). |
| **합격선** | prereg band 전부; RL 사용 시 lift≥1.05. |
| **킬** | hidden에서 reward↑ semantic↓ → 정책 폐기. FAR>0.01 → 폐기. |
| **예산** | 평가 패스 1회; 재실행 금지(단발). |
| **시드** | 평가 시드 봉인값 1개. |
| **산출** | `wsd_eval_p6.json` + evidence xlsx. |

### Cell-F — RLVR full (조건부)

| 항목 | 내용 |
|------|------|
| **가설** | Multi-step RLVR이 bandit utility를 ≥5% 개선. |
| **전제** | Cell-0·B·C PASS, DGX 필요 시 reachable. |
| **지표** | utility_RL / utility_bandit, hidden AUPRC, cost. |
| **합격선** | lift≥1.05 ∧ Cell-E band 동시. |
| **킬** | lift<1.05 → RL 폐기·bandit 채택. off-policy 불안정(분산 폭발) 시 early stop=실패 기록. |
| **예산** | DGX 수일 또는 로컬 소규모 H≤3만. |
| **시드** | {50–54}. |

### Cell-G — 실도면 배포 진단 (라벨 없음)

| 항목 | 내용 |
|------|------|
| **가설** | 1.dwg 샘플에서 arm 비용·abstain율이 합성 정책과 동일 방향. |
| **지표** | mean cost, arm mix, B3 정합(벽-제로율 유지), latency. |
| **합격선** | 방향 일치(사전 등록 허용 편차); 불일치 시 simulator-to-real gap 티켓 OPEN. |
| **킬** | P6 claim의 “실환경 절감” 주장을 금지(연구 주장 축소). 합성 claim은 Cell-E로 제한 가능. |
| **예산** | 0.5–1일. |
| **시드** | 도면정의 샘플 고정 리스트. |

### 셀 과소·과잉 검토

- 과소 방지: soundness / offline bandit / horizon / hidden / (조건부) RL을 분리.  
- 과잉 방지: Taguchi 대스크린·GNN 동시 학습·프런티어 배심 대량 호출은 본 제안 NON-GOAL.

---


---

## [doe_P1] — ## 6. 실험 셀 정의 (116 lines)

## 6. 실험 셀 정의

### 6.1 공통 판정 코드

모든 셀의 primary metric은 `R-SYN`, secondary는 `R-SILVER`다. 합격은 두 response가 각각 PASS이고 `S0≥0.99`, macro recall `≥0.30`이며 validity gate가 모두 통과하는 경우다. 한 response가 INCONCLUSIVE이면 셀도 최대 INCONCLUSIVE다.

Kill code는 다음과 같다.

- `K-SYN`: T-SYN fidelity gate FAIL 또는 negative-handle/sentinel 결손
- `K-SIL`: silver 원출력·2-family balancing·train/eval 분리가 불완전
- `K-GRAPH`: Graph IR adjacency/transform/INSERT world-coordinate 검증 실패
- `K-RASTER`: raster↔handle exactness 또는 동일 후보우주 실패
- `K-FIRM`: group metadata 없음, F 수준 간 학습량 불일치, L-FIRM overlap 발견
- `K-ST`: pseudo-label pool이 evaluation과 겹침, weight cap 위반, 한 라운드 초과
- `K-SEED`: learned seed block 누락 또는 winner/effect sign이 단일 seed에만 의존
- `K-LEAK`: name/path/layer/firm feature 노출 또는 shuffle control 비정상
- `K-RESOURCE`: prereg resource cap 초과·도면 조용한 누락
- `K-GLOBAL-SYN`: 16셀 모두 `R-SYN<0.75`
- `K-GLOBAL-SIL`: 어떤 셀도 `R-SILVER>0.30`이 아님
- `K-CEILING`: 모든 셀이 합성 천장이고 effect가 판별되지 않음 — 실패라기보다 harder-generator version bump 후 재설계

Budget code는 다음과 같다.

- `BD-G`: graph deterministic, 로컬 CPU, seed 반복 없음
- `BD-R`: raster deterministic, frozen raster cache + 로컬 CPU, seed 반복 없음
- `BL-G`: graph HGB, 로컬 CPU/RAM, 공통 3-seed block
- `BL-R`: raster HGB, frozen raster cache + 로컬 CPU/RAM, 공통 3-seed block

결정론 8셀 합계는 cache 후 반나절 목표, learned cell은 셀당 3 fit을 허용한다. 시간은 제안 budget이다.

### 6.2 16개 셀

각 셀 가설은 “이 bundle이 두 band와 guardrail을 만족한다”는 viability 가설이며, 요인 효과 가설은 16셀 전체 대비로만 검정한다. 한 셀을 다른 셀과 임의 pairwise test하지 않는다.

| Run | 정확한 셀 설정 | 셀별 사전 가설 | 지표·제안 합격선 | 주요 kill | 예산·seed |
|---:|---|---|---|---|---|
| 1 | graph · deterministic · T-SYN · hard · ST off · L-DWG | 합성 튜닝을 쓴 가장 단순한 graph-rule 참조 셀이 두 band를 동시에 넘는지 본다. | 공통 dual PASS + guardrail | K-SYN, K-GRAPH, K-FIRM, K-LEAK | BD-G, deterministic hash 1회 |
| 2 | graph · deterministic · T-SYN · weighted · ST off · L-FIRM | exact synthetic label에서 D가 사실상 null이어도 firm 분리 후 viability가 남는지 본다. | 동일 | K-SYN, K-GRAPH, K-FIRM | BD-G, 반복 없음 |
| 3 | graph · deterministic · T-SILVER · hard · ST on · L-FIRM | silver hard label과 1회 pseudo-refit이 strict firm split에서도 규칙 scorer를 개선 가능한지 본다. | 동일 | K-SIL, K-GRAPH, K-FIRM, K-ST | BD-G, 반복 없음 |
| 4 | graph · deterministic · T-SILVER · weighted · ST on · L-DWG | confidence weighting이 shared-firm 환경의 겉보기 이득만 키우는지 포함해 viability를 본다. | 동일 | K-SIL, K-GRAPH, K-ST, K-LEAK | BD-G, 반복 없음 |
| 5 | graph · HGB · T-SYN · hard · ST on · L-FIRM | 합성 학습 HGB가 self-training 후에도 unseen-firm에 전이하는지 본다. | 동일 | K-SYN, K-GRAPH, K-FIRM, K-ST, K-SEED | BL-G, 공통 3 seed |
| 6 | graph · HGB · T-SYN · weighted · ST on · L-DWG | pseudo confidence weighting이 graph HGB의 합성→실도면 교차응답을 올리는지 본다. | 동일 | K-SYN, K-GRAPH, K-ST, K-SEED | BL-G, 공통 3 seed |
| 7 | graph · HGB · T-SILVER · hard · ST off · L-DWG | 알려진 HGB 축에 가까운 shared-firm silver 학습 bundle이 실제 band를 넘는지 본다. | 동일 | K-SIL, K-GRAPH, K-FIRM, K-SEED, K-LEAK | BL-G, 공통 3 seed |
| 8 | graph · HGB · T-SILVER · weighted · ST off · L-FIRM | confidence-weighted silver HGB가 자기학습 없이 firm holdout에 강건한지 본다. | 동일 | K-SIL, K-GRAPH, K-FIRM, K-SEED | BL-G, 공통 3 seed |
| 9 | raster · deterministic · T-SYN · hard · ST on · L-DWG | paired raster 증거만으로 rule scorer와 한 번의 pseudo-refit이 작동하는지 본다. | 동일 | K-SYN, K-RASTER, K-ST, K-FIRM | BD-R, 반복 없음 |
| 10 | raster · deterministic · T-SYN · weighted · ST on · L-FIRM | raster rule bundle이 strict firm split과 pseudo confidence 아래서 유지되는지 본다. | 동일 | K-SYN, K-RASTER, K-FIRM, K-ST | BD-R, 반복 없음 |
| 11 | raster · deterministic · T-SILVER · hard · ST off · L-FIRM | raster evidence와 silver tuning만으로 unseen-firm viability가 있는지 본다. | 동일 | K-SIL, K-RASTER, K-FIRM | BD-R, 반복 없음 |
| 12 | raster · deterministic · T-SILVER · weighted · ST off · L-DWG | confidence-weighted silver가 raster rule의 shared-firm 점수만 올리는지 함께 본다. | 동일 | K-SIL, K-RASTER, K-FIRM, K-LEAK | BD-R, 반복 없음 |
| 13 | raster · HGB · T-SYN · hard · ST off · L-FIRM | 학습 이득이 graph에 한정되지 않고 raster-conditioned feature에서도 strict split에 남는지 본다. | 동일 | K-SYN, K-RASTER, K-FIRM, K-SEED | BL-R, 공통 3 seed |
| 14 | raster · HGB · T-SYN · weighted · ST off · L-DWG | exact T-SYN에서 D의 null 가능성을 포함해 raster HGB의 baseline viability를 본다. | 동일 | K-SYN, K-RASTER, K-FIRM, K-SEED | BL-R, 공통 3 seed |
| 15 | raster · HGB · T-SILVER · hard · ST on · L-DWG | 가장 leakage·confirmation-bias 위험이 큰 bundle이 겉보기로만 좋아지는지 본다. | 동일 | K-SIL, K-RASTER, K-ST, K-SEED, K-LEAK | BL-R, 공통 3 seed |
| 16 | raster · HGB · T-SILVER · weighted · ST on · L-FIRM | 가장 복합적인 bundle이 strict split에서도 dual PASS를 달성하는지 본다. | 동일 | K-SIL, K-RASTER, K-FIRM, K-ST, K-SEED | BL-R, 공통 3 seed |

### 6.3 cheapest probe

먼저 B=deterministic인 run `1,2,3,4,9,10,11,12`만 실행한다. 이 8개는 6요인 fraction 전체가 아니므로 B main 또는 B가 포함된 interaction을 추정하지 않는다. 목적은 다음 세 가지다.

- paired A가 실제로 설정 가능한지
- C와 F 수준이 metric을 움직일 최소 신호가 있는지
- raster mapping, firm split, silver materialization, resource cap이 learned 투자 전에 견디는지

이 probe에서 graph/raster 후보우주가 달라지거나 T-SYN이 fidelity 자격을 못 얻으면 learned 8셀을 열지 않는다. 현재 fidelity FAIL 상태에서의 probe는 engineering dry run으로만 기록한다.

### 6.4 effects table — UNRUN

사전 main-effect 기대 **크기 순위**는 패킷대로 `C > B > A > F > D > E`다. 방향은 데이터 전에 단정하지 않는다. 모든 effect는 high-minus-low다.

| estimand | 의미 | 사전 순위/관심 | R-SYN effect | R-SILVER effect | rank | active | status |
|---|---|---|---|---|---|---|---|
| A | raster − graph | main 3위 | — | — | — | — | UNRUN |
| B | HGB − deterministic | main 2위 | — | — | — | — | UNRUN |
| C | T-SILVER − T-SYN | main 1위 | — | — | — | — | UNRUN |
| D | weighted − hard | main 5위 | — | — | — | — | UNRUN |
| E | ST on − off | main 6위 | — | — | — | — | UNRUN |
| F | L-FIRM − L-DWG | main 4위 | — | — | — | — | UNRUN |
| G1 | `AB = CE` | representation×family 후보이나 truth×ST와 불리 | — | — | — | — | UNRUN |
| G2 | `AC = BE` | representation×truth 대 family×ST | — | — | — | — | UNRUN |
| G3 | `AD = EF` | representation×noise 대 ST×leakage | — | — | — | — | UNRUN |
| G4 | `AE = BC = DF` | family×truth 사전 핵심이나 두 항과 불리 | — | — | — | — | UNRUN |
| G5 | `AF = DE` | representation×leakage 대 noise×ST | — | — | — | — | UNRUN |
| G6 | `BD = CF` | truth×leakage 사전 핵심이나 family×noise와 불리 | — | — | — | — | UNRUN |
| G7 | `BF = CD` | family×leakage 대 truth×noise | — | — | — | — | UNRUN |
| H1 | `ABD=CDE=ACF=BEF` | 고차 진단, 해석 금지 | — | — | — | — | UNRUN |
| H2 | `ACD=BDE=ABF=CEF` | 고차 진단, 해석 금지 | — | — | — | — | UNRUN |

### 6.5 interactions_found — UNRUN

현재 “found”된 interaction은 없다. 사전 후보만 있다.

| 사전 질문 | 실제 16런 estimand | 단독 식별 가능? | status |
|---|---|---|---|
| 계열 우위가 표현에 의존하는가? (`AB`) | G1=`AB=CE` | 아니오 | UNRUN |
| 학습 우위가 정답원에 의존하는가? (`BC`) | G4=`AE=BC=DF` | 아니오 | UNRUN |
| 정답원 효과가 누수 입도에 의존하는가? (`CF`) | G6=`BD=CF` | 아니오 | UNRUN |

활성 G1/G4/G6가 나오면 그것을 각각 AB/BC/CF로 이름 바꾸지 않는다. 먼저 해당 사슬의 후보 열들이 독립 rank를 갖도록 추가 treatment를 고른다. 8-run targeted augmentation은 가능한 선택이지만, 다음 조건을 만족할 때만 쓴다.

- 64개 전체 후보 중 기존 16개를 제외한 후보에서 선택
- 관심 main+2FI model matrix가 full column rank
- condition number와 prediction variance가 prereg 기준 이내
- 기존 main-effect 추정과의 연결이 유지됨
- 새 결과를 보기 전에 추가 행과 분석식을 봉인

이 증강은 선택한 interaction을 분리하는 **비정규 표적 증강**일 수 있다. 단지 8행을 더했다는 이유로 `Resolution V`라고 쓰지 않는다. 모든 2FI를 전역적으로 분리하려면 별도의 더 큰 설계를 새로 최적화하고 version-bump한다.

### 6.6 confirmation run

- 대상: 2.9의 고정 selection rule이 고른 단일 셀
- 비교: frozen graph-deterministic reference 1개
- population: screen과 어떤 firm도 공유하지 않는 hold-out
- 지표: 같은 R band, S0, recall, per-firm 분포
- Goodhart pair: screen 상대효과와 hold-out 상대효과의 부호 비교
- test 사용: val에서 설정을 바꾼 뒤 test를 다시 보지 않음
- 현재 판정: `PASS_WITH_DEFERRAL`, 실행 증거 없음

---


---

## [doe_P2] — ## 6. 실험 셀 정의 (68 lines)

## 6. 실험 셀 정의

모든 “제안 임계값”은 해당 셀 실행 전에 프리레지스트리에 봉인한다. val은 개발·튜닝에만 쓰고, CubiCasa test는 최종 방법당 단발이다. 결정 셀은 시드가 없고 셀내 반복도 없다.

### C0 — 계약·baseline·절대/상대 gap preflight

- **가설**: 네 factor가 실제 코드 경로에 연결되고, angle/gap 단위가 일관되며, declared-unit absolute와 dimension-anchored 해석 중 하나를 outcome leakage 없이 고정할 수 있다.
- **지표**: factor perturbation smoke, reference scorer↔`fast_score` parity, unit/scale metamorphic consistency, sentinel, v1 baseline cache, firm metadata 완전성, A/B gap 해석의 30개 paired probe.
- **합격선**: 전달 trace에서 factor 값이 exact하게 일치하고, 각 factor를 식별하도록 만든 fixture에서 해당 predicate/cap이 변하며, scorer parity가 exact하고 firm-first split과 hold-out이 가능해야 한다. A/B는 scale/unit R-META band·sentinel eligibility·`2*sigma_drawing` paired-loss 규칙으로 하나를 고정한다. 일반 R-META outcome 개선은 wiring 합격의 근거가 아니다.
- **킬 조건**: rad/mm 계약 불명, fast/reference 불일치, firm 분리 불가, dimension anchor가 필요한데 만들 수 없음, sentinel harness 부재.
- **예산**: 로컬 CPU smoke, manifest 작성, A/C/D frozen baseline에서 `2 parameterizations × 3 gap levels × 5 drawings = 30`개 선행 비교. main 360회에는 포함하지 않는다.
- **시드**: 없음; content hash 순서.

### C1 — cheapest probe: L9 × 5장

- **가설**: 최소 표본에서도 사전 rank `gap > overlap > angle > max_pairs`의 방향 또는 명백한 plateau/폭발 신호가 보인다.
- **지표**: 45개 `L_META`, row별 mean/variance/S/N, candidate count, cap hit, sentinel, 오류.
- **합격선**: 45개 셀이 모두 상태를 갖고, 적어도 한 요인의 level span이 측정 해상도보다 크거나 명시적 plateau로 판정 가능해야 한다. 이 셀만으로 setting을 채택하지 않는다.
- **킬 조건**: 동일 cache key 비결정성, 반복적 compute abort, sentinel collapse, factor가 실제 점수 경로에 무영향인 wiring 오류.
- **예산**: 패킷상 목표 30분, 로컬 CPU·streaming IR. 시간 초과는 실제값으로 보고한다.
- **시드**: 없음. 5장은 미리 고정한 40장의 부분집합.

### C2 — 본선: L9 × development outer 40장

- **가설**: 네 주효과 중 적어도 하나가 `2*sigma_resid`를 넘으며, 평균이 비슷한 행 사이에서 도면 간 분산 차이가 존재한다.
- **지표**: 360개 R-META, equal-firm mean/variance, firm variance, STB S/N, level effects/rank/active, noise stratum별 descriptive breakdown, process counters.
- **합격선**: sentinel·recall hard gate 통과, aggregate R-META `<=0.02`, 그리고 선택 규칙에 따라 관측 robust row를 지명할 수 있어야 한다. active가 없더라도 정직한 plateau 판정은 유효 결과다.
- **킬 조건**: 전 grid plateau, 전 행 R-META `>0.10`, compute cap 때문에 특정 noise stratum이 체계적으로 빠짐, 또는 absolute/relative parameterization의 미해결 혼입.
- **예산**: 9×40=360 결정 평가, 로컬 CPU, 64GB RAM 내 streaming. GPU/DGX 없음.
- **시드**: 없음; 동일한 40장을 모든 run에 paired 적용.

### C3 — T-SYN collapse/secondary gate

- **가설**: R-META가 좋은 행이 wall recall을 버려 얻은 허위 최적은 아니며, F/M family에서 secondary F1이 치명적으로 붕괴하지 않는다.
- **지표**: family별 per-handle precision/recall/F1, LTB S/N, zero/all-wall sentinel, META×SYN disagreement table.
- **합격선**: 제안 recall floor `>=0.95`, sentinel 모두 통과. F/M F1은 행 비교의 2차 tie-break 정보지만 B1 FAIL 동안 독립 채택 근거가 아니다.
- **킬 조건**: R-META 우승 행의 collapse, S팩의 공허한 precision을 pooled F1로 사용, synthetic 결과로 outer FAIL을 덮음.
- **예산**: frozen synthetic pack의 결정 scoring, 로컬 CPU.
- **시드**: 없음.

### C4 — 활성 두 요인 3×3 완전요인 후속

- **가설**: L9에서 active인 두 요인의 효과 방향이 상호작용을 분리해도 유지된다.
- **지표**: 두 요인의 9조합별 R-META mean/variance/S/N, `drawing block + A + B + A×B` 모형의 interaction contrast, sentinel, 동일 outer breakdown.
- **합격선**: 최대 absolute interaction contrast가 C2의 `2*sigma_resid` 이내이고 주효과 방향이 역전되지 않으며, 선택 행이 C2 eligibility를 유지해야 한다. interaction이 `2*sigma_resid`를 넘더라도 새 관측 3×3 최적을 별도 설정으로 지명할 수는 있지만 L9 main-effect 청구는 폐기한다.
- **킬 조건**: interaction이 main effect를 뒤집음, 활성 요인이 둘보다 많아 3×3이 질문을 덮지 못함, L9가 가리킨 optimum이 interaction follow-up에서 사라짐.
- **예산**: 필요한 경우에만 9설정. C2와 같은 개발 drawings를 쓰며 test는 열지 않는다. L27은 명시적 열 배치가 승인된 경우의 대안이다.
- **시드**: 없음.

### C5 — hold-out firm confirmation

- **가설**: 지명된 한 설정의 낮은 R-META와 낮은 분산이 selection에 쓰지 않은 firm에도 유지된다.
- **지표**: hold-out R-META band, STB S/N, drawing/firm variance, sentinel/recall, development firm leave-one-firm-out jackknife 범위.
- **합격선**: hold-out R-META `<=0.02`, sentinel/recall gate 통과, `eta_hold >= eta_dev - 2*SE_JK(eta)` 및 `Var_hold <= Var_dev + 2*SE_JK(Var)`를 모두 만족해야 한다. `SE_JK`는 development firm을 하나씩 제외한 leave-one-firm-out 값으로 계산한다. development firm이 이 계산을 지탱하지 못하면 분산 재확인은 INCONCLUSIVE다. 상태는 패킷대로 `PASS_WITH_DEFERRAL`; 한 hold-out 집합으로 보편성을 확정하지 않는다.
- **킬 조건**: hold-out R-META `>0.10`, 미사용 firm에서 반복 compute abort, 또는 분산이 development 범위를 넘어 firm-specific 과적합을 보임. `0.02–0.10`은 INCONCLUSIVE이며 PASS로 반올림하지 않는다.
- **예산**: named setting 하나만 hold-out drawings에 단독 실행. selection 재튜닝 금지.
- **시드**: 없음; firm은 C0에서 미리 고정.

### C6 — optional CubiCasa transport와 test 단발

- **가설**: archive에서 선택한 robust setting 또는 gap을 제외한 transportable 부분이 CubiCasa SEG-IR에서도 v1의 고재현·저정밀 패턴을 악화시키지 않는다.
- **지표**: val per-handle P/R/F1, R-META, scale-bin descriptive 결과, 기존 v1 `0.2358` 및 GBDT `0.517` comparator.
- **합격선**: px↔gap 계약이 먼저 봉인되고, val에서 sentinel/recall을 통과하며, 개선 주장을 하려면 P/R/F1을 모두 보고해야 한다. 단순 recall 유지나 물리 scale bin 무감만으로 성공 처리하지 않는다.
- **킬 조건**: label을 사용해 px scale을 역추정, val을 보고 factor/threshold를 다시 변경, FloorPlanCAD raster를 handle truth로 둔갑, counsel 미확인.
- **예산**: 기존 SEG-IR의 로컬 scoring. GPU/DGX 없음.
- **시드**: 없음. test는 C0–C5와 val 규칙을 모두 봉인한 뒤 프로그램이 P2를 정식 후보로 승인한 경우에만 한 번 실행한다.

---


---

## [doe_P3] — ## 6. 실험 셀 정의 (67 lines)

## 6. 실험 셀 정의

### 6.1 공통 실행 규칙

- 각 논리 셀은 locked 30 drawing을 평가한다.
- deterministic 모델에는 model seed가 없다. T-SYN generator와 T-SILVER label generation의 seed/repeat만 기록한다.
- learned 모델은 제안 seed `{17,43,89}`를 모두 실행하고 셀 순서를 master seed `20260718`로 무작위화한다. 숫자는 프리레지 제안값이며 실측이 아니다.
- T-SILVER가 A 또는 B에 들어가면 세 생성 반복을 유지한다. train/eval silver raw draw는 분리한다.
- 라벨형 diagonal의 제안 합격선은 source gate PASS와 `R_b>0`. off-diagonal의 실질 합격선은 대응 대각 대비 낙폭 `≤0.20`; 불확실성 상한까지 `≤0.20`이어야 chain closure를 지지한다.
- T-META 셀에는 diagonal이 없다. strict gate PASS 후 `R_META`를 보고하고, transform별 최악 팔을 숨기지 않는다.
- 공통 kill은 source qualification 실패, split overlap, threshold의 B별 재튜닝, shuffle와 real의 미분리, evidence 누락이다.
- 셀별 시간은 계획 상한(실측 아님)으로 deterministic scoring `1 CPU-hour`, learned scoring `1 CPU-hour`; fit 비용은 A·C 공용이므로 셀에 중복 청구하지 않는다.

### 6.2 24셀 매트릭스

| Cell | C | A→B | 사전 가설 | 일차 지표·제안 합격선 | 셀 kill 조건 | 예산·시드 |
|---|---|---|---|---|---|---|
| D-SS | deterministic | SYN→SYN | 대각은 높을 수 있음 | `R_SYN>0`, gate PASS | B1/양음 gate 실패 또는 null 이하 | 30장, population; L-SEED |
| D-SE | deterministic | SYN→EXT | **핵심 벽**, 큰 낙폭 예상 | `Drop_SYN→EXT≤0.20` | 낙폭 `>0.20`, CRS/NC gate 실패 | 30장, population; L-SEED |
| D-SV | deterministic | SYN→SILVER | 합성 tell이면 낙폭 | `Drop_SYN→SILVER≤0.20` | 낙폭 `>0.20` 또는 silver 미자격 | 30장 × silver 3회 |
| D-SM | deterministic | SYN→META | 기하 규칙이면 불변성 유지 | META strict gate PASS, `R_META` 보고 | sentinel/mapping/scale strict FAIL | 30장, transform 반복 |
| D-ES | deterministic | EXT→SYN | 외부 정의의 역전이 확인 | `Drop_EXT→SYN≤0.20` | 낙폭 `>0.20` 또는 SYN 미자격 | 30장, population; L-SEED |
| D-EE | deterministic | EXT→EXT | 대각 학습가능성 확인 | `R_EXT>0`, gate PASS | null 이하, CRS/NC gate 실패 | 30장, population |
| D-EV | deterministic | EXT→SILVER | 두 real-domain proxy의 호환성 | `Drop_EXT→SILVER≤0.20` | 낙폭 `>0.20` 또는 silver 미자격 | 30장 × silver 3회 |
| D-EM | deterministic | EXT→META | 외부 최적화가 invariant인지 | META strict gate PASS, `R_META` 보고 | sentinel/mapping strict FAIL | 30장, transform 반복 |
| D-VS | deterministic | SILVER→SYN | silver 습관의 합성 전이 시험 | `Drop_SILVER→SYN≤0.20` | 낙폭 `>0.20` 또는 source gate 실패 | 30장 × train silver 3회 |
| D-VE | deterministic | SILVER→EXT | 큰 낙폭 예상, 두 번째 핵심 벽 | `Drop_SILVER→EXT≤0.20` | 낙폭 `>0.20`, NC/CRS gate 실패 | 30장 × train silver 3회 |
| D-VV | deterministic | SILVER→SILVER | 대각 높음 예상, family leakage 경계 | `R_SILVER>0`, disjoint-family gate | 같은 raw/family role 재사용 또는 null 이하 | 30장; train 3 × eval 3 |
| D-VM | deterministic | SILVER→META | silver distill이 기하 일관성 보존? | META strict gate PASS, `R_META` 보고 | sentinel/mapping strict FAIL | 30장 × train silver 3회 |
| L-SS | learned | SYN→SYN | 학습계열 대각 높음 예상 | `R_SYN>0`, gate PASS | B1/양음 gate 실패, shuffle 미분리 | 30장 × model seed 3; L-SEED |
| L-SE | learned | SYN→EXT | **핵심 벽**, shortcut이면 최대 낙폭 | `Drop_SYN→EXT≤0.20` | 낙폭 `>0.20`, shuffle/CRS/NC FAIL | 30장 × model seed 3 |
| L-SV | learned | SYN→SILVER | 합성 tell의 silver 전이 시험 | `Drop_SYN→SILVER≤0.20` | 낙폭 `>0.20` 또는 silver 미자격 | 30장 × model seed 3 × eval silver 3 |
| L-SM | learned | SYN→META | learned shortcut의 metamorphic 노출 | META strict gate PASS, `R_META` 보고 | sentinel/mapping/scale strict FAIL | 30장 × model seed 3 |
| L-ES | learned | EXT→SYN | HGB 이득의 역전이 확인 | `Drop_EXT→SYN≤0.20` | 낙폭 `>0.20`, SYN/shuffle FAIL | 30장 × model seed 3 |
| L-EE | learned | EXT→EXT | 기존 HGB 향상의 재현 대각 | `R_EXT>0`, gate PASS | null 이하, shuffle/CRS/NC FAIL | 30장 × model seed 3 |
| L-EV | learned | EXT→SILVER | T-EXT 학습이 silver와 호환? | `Drop_EXT→SILVER≤0.20` | 낙폭 `>0.20`, silver/shuffle FAIL | 30장 × model seed 3 × eval silver 3 |
| L-EM | learned | EXT→META | 높은 T-EXT 점수가 invariant인가 | META strict gate PASS, `R_META` 보고 | sentinel/mapping strict FAIL | 30장 × model seed 3 |
| L-VS | learned | SILVER→SYN | silver shortcut의 합성 전이 | `Drop_SILVER→SYN≤0.20` | 낙폭 `>0.20`, SYN/silver/shuffle FAIL | 30장 × train silver 3 × seed 3 |
| L-VE | learned | SILVER→EXT | 큰 낙폭 예상, 제품 위험 직결 | `Drop_SILVER→EXT≤0.20` | 낙폭 `>0.20`, NC/CRS/shuffle FAIL | 30장 × train silver 3 × seed 3 |
| L-VV | learned | SILVER→SILVER | 대각 높음 예상, 자기복제 위험 최대 | `R_SILVER>0`, disjoint-family gate | raw/family leakage 또는 null 이하 | 30장; train 3 × eval 3 × seed 3 |
| L-VM | learned | SILVER→META | silver 학습의 invariant 여부 | META strict gate PASS, `R_META` 보고 | sentinel/mapping strict FAIL | 30장 × train silver 3 × seed 3 |

`V`는 표 길이를 줄이기 위한 T-SILVER 약자다. 모든 off-diagonal의 `Drop`은 동일 C에서 해당 평가원 대각과 비교한다. 예를 들어 `SYN→EXT`는 `EXT→EXT`와 비교하며 `SYN→SYN`과 비교하지 않는다.

### 6.3 effects table 템플릿 — 현재 전부 UNRUN

**deterministic-tuned**

| train \ eval | T-SYN | T-EXT | T-SILVER | T-META |
|---|---|---|---|---|
| T-SYN | UNRUN (diagonal) | UNRUN (key off-diagonal) | UNRUN | UNRUN (no diagonal) |
| T-EXT | UNRUN | UNRUN (diagonal) | UNRUN | UNRUN (no diagonal) |
| T-SILVER | UNRUN | UNRUN (key off-diagonal) | UNRUN (diagonal) | UNRUN (no diagonal) |

**learned**

| train \ eval | T-SYN | T-EXT | T-SILVER | T-META |
|---|---|---|---|---|
| T-SYN | UNRUN (diagonal) | UNRUN (key off-diagonal) | UNRUN | UNRUN (no diagonal) |
| T-EXT | UNRUN | UNRUN (diagonal) | UNRUN | UNRUN (no diagonal) |
| T-SILVER | UNRUN | UNRUN (key off-diagonal) | UNRUN (diagonal) | UNRUN (no diagonal) |

사전 방향 가설은 세 라벨형 대각이 높고 `T-SYN→T-EXT`, `T-SILVER→T-EXT`가 가장 크게 떨어진다는 것이다. 그러나 null도 완전한 결과다. 특정 off-diagonal이 대각과 동등하면 그 source pair를 호환 후보로 올린다. 현재 `interactions_found=A×B, status=UNRUN`; 효과값, PASS, 호환쌍은 아직 없다.

### 6.4 confirmation run

core validation에서 모든 gate를 통과한 off-diagonal 중 worst-source skill을 최대화하는 `(A,C)`를 먼저 선택하고, 그 안에서 낙폭이 가장 작은 `(train,eval)` pair를 하나 봉인한다. threshold와 model artifact를 바꾸지 않고 hold-out firm에서 한 번 재실행한다. firm metadata가 없거나 counsel이 끝나지 않았으면 상태는 패킷대로 `PASS_WITH_DEFERRAL`; 이를 PASS로 바꾸지 않는다. test를 사용하는 경우 frozen method당 단 한 번만 읽고 재튜닝하지 않는다.


---

## [doe_P4] — ## 6. 실험 셀 정의 (74 lines)

## 6. 실험 셀 정의

### 6.0 공통 규칙

- 지표: hold-out F1 (`R-SYN`/`R-SILVER` 공통 밴드) + (active) 라벨당 비용  
- val 튜닝 / test 단발  
- 셔플 대조군: supervised·특징 파이프에 의무 (앵커 AUC 0.375 PASS 패턴)  
- 증거: 셀당 xlsx 행 (seed, IR hash, paradigm, B, C, F1, gate, cost, hacking_flag)  
- **제안 합격선(프리레그 초안, 평가 전 봉인 대상)**  
  - scarce에서 승자 paradigm의 val F1 ≥ supervised_scarce + 0.03 **또는** 라벨당 비용 ≤ 0.85×supervised  
  - abundant에서 supervised가 RL계 대비 비열등 (ΔF1 ≥ −0.01)  
  - hacking: RH 서명 0건이어야 “진성 우위” 주장 가능  

### 6.1 Cheapest probe (4셀) — 최우선

| Cell | A | C | 가설 | 합격선 | 킬 | 예산 | 시드 |
|------|---|---|------|--------|-----|------|------|
| CP1 | supervised | scarce | C07: 희소에서도 supervised가 안정 | 기준선 확정 | — | 로컬 0.5–1일 | 3 |
| CP2 | supervised | abundant | HGB≈0.517 재현 밴드 | val F1 ∈ [0.49,0.54] 재현(앵커 근처; 봉인 시 확정) | 재현 실패 시 파이프 버그 | 1일 | 3 |
| CP3 | active | scarce | **표적**: 라벨당 F1 > CP1 | ΔF1≥+0.03 또는 비용↓ | 둘 다 실패 → C07 맥락판 유지 쪽 신호 | 1–2일 | ≥5 |
| CP4 | active | abundant | supervised와 비슷하거나 열위 | abundant에서 active 필수 lift 없음이 정상 | active가 비용만 늘리면 A3 abundant 비추천 | 1–2일 | ≥5 |

**Cheapest 킬**: CP3가 CP1을 못 이김 → 풀팩터 RLVR 투자 보류, C07 지지 쪽으로 기울임(아직 최종 판결 아님).

### 6.2 본실험 12셀 (A×B×C)

표기: S=supervised, R=RLVR, Ac=active; H=high T-SYN, L=low T-SILVER; sc=scarce, ab=abundant.

| Cell | A | B | C | 가설 | 지표 | 합격선 | 킬(셀/축) | 예산 | 시드 |
|------|---|---|---|------|------|--------|-----------|------|------|
| 01 | S | H | sc | clean truth·희소: S 안정 | F1 | 기준 | — | 로컬 | ≥3 |
| 02 | S | H | ab | clean·풍부: S 최고 후보 | F1 | ≥ 다른 A | — | 로컬 | ≥3 |
| 03 | S | L | sc | noisy: S 성능↓ but 분산↓ | F1 | 보고 | — | 로컬 | ≥3 |
| 04 | S | L | ab | noisy·풍부 | F1 | 보고 | — | 로컬 | ≥3 |
| 05 | R | H | sc | **가설**: scarce에서 R/Ac ≥ S | F1,gate | scarce 승자 후보 | hacking이면 무효 | DGX | ≥5 |
| 06 | R | H | ab | C07: S ≥ R | F1 | R이 ab에서 S 미상회가 정상 | R만 이기고 Ac/S 전부 패면 이상 징후 | DGX | ≥5 |
| 07 | R | L | sc | **hacking 위험 구간** | F1,gate | hold-out 유지 | gate↑ F1↓ → C08 | DGX | ≥5 |
| 08 | R | L | ab | 동 | F1,gate | 동 | 동 | DGX | ≥5 |
| 09 | Ac | H | sc | **표적 A×C**: scarce Ac 승 | F1,cost | CP3 강화 | Ac 전 예산 패배 | 로컬→DGX | ≥5 |
| 10 | Ac | H | ab | S와 비슷 | F1,cost | lift 불요 | — | 로컬 | ≥5 |
| 11 | Ac | L | sc | noisy+active: 질의 오염 | F1,cost | 보고 | 순서 아티팩트면 seed 재분리 | 로컬 | ≥5 |
| 12 | Ac | L | ab | 동 | F1,cost | 보고 | 동 | 로컬 | ≥5 |

### 6.3 Reward-hacking 프로브 2셀

| Cell | 설정 | 가설 | 합격선 | 킬 |
|------|------|------|--------|-----|
| RH0 | RLVR + gate-only | hacking 유도 가능 | 서명 검출 가능해야 프로브 유효 | 서명 불가능한 보상 설계면 재설계 |
| RH1 | RLVR + gate+holdout 벌점 | 진성만 생존 | RH0 대비 hold-out 회복 | 벌점에도 hacking이면 verifier 수리 선행 |

### 6.4 사전봉인 판정 규칙 (effects_table)

슬롯: A(3수준 대비), B, C main, A×C, A×B. status=UNRUN.

| 결과 | 판결 |
|------|------|
| A×C 유효 (Lenth ME 초과) | C07 **맥락없는 판 반증**; 적용범위 재작성 |
| A×C null ∧ A_main(R,Ac)≤0 | C07 **지지**; RL 계열 하차 |
| R이 L에서 gate↑ & hold-out↓ | reward-hacking 확정; 가짜 승리 폐기 |
| high-truth에서 A 무차별 | “정답원 좋으면 방법 무관” 보고 (null도 승리) |

### 6.5 Confirmation run

- 대상: scarce에서 이긴 paradigm (가설상 Ac 또는 R)  
- 새 hold-out firm / 미접촉 분할  
- hacking 재점검  
- status: **`PASS_WITH_DEFERRAL`** — 미확인 우위를 PASS로 부르지 않음  

### 6.6 프로그램급 kill_condition (패킷 원문 승계)

1. A×C null **그리고** RLVR/active가 어느 예산에서도 supervised를 못 이김 → C07 지지, RL 프로그램 하차  
2. RLVR가 “이겼는데” 전부 hacking 서명 → 가짜 승리, verifier 수리 선행 (훈련 재개 금지)

---


---

## [doe_P5] — ## 6. 실험 셀 정의 (52 lines)

## 6. 실험 셀 정의

### 6.1 사전 자격 셀 — 28셀에 섞지 않음

| 셀 | 가설 | 지표 | 제안 합격선 | 킬 조건 | 예산 | 시드 계획 |
|---|---|---|---|---|---|---|
| `Q0 T-META oracle` | 7 clean relation은 0위반이고 각 exactly-one mutant는 정확히 검출된다 | clean false violation, mutant kill, mapping coverage | clean 전부 0; mutant 전부 kill; mapping collision 0 | 하나라도 clean을 위반 또는 mutant 생존 시 detector 실행 금지 | 로컬 CPU ≤1시간(상한 제안) | catalog seed `20260718`; rename/jitter는 표의 고정 seed |
| `Q1 family sentinels` ×4 | 각 family는 constant-zero/all 해가 아니며 positive fixture를 일부 회수한다 | zero/all flag, labeled recall | sentinel fixture 전부 탐지; recall≥0.20(새 제안) | 자명한 해 미검출 또는 recall 미달 시 family 랭킹 제외 | family당 로컬 ≤1시간; VLM은 DGX preflight | 학습 seed는 upstream artifact에 고정; P5 재학습 없음 |
| `Q2 repeat checksum` ×4 | 동일 입력·artifact는 동일 prediction을 낸다 | normalized prediction SHA-256 | checksum 완전 일치 | 불일치 시 평균하지 않고 family 실행 실패 | family당 5도면 duplicate run | 변환 seed 없음; VLM temperature 0 |

`Q1`의 labeled 자료는 CubiCasa val 또는 PR-1 wall truth pack이다. CubiCasa test는 열지 않는다. sentinel은 R-META 본 반응이 label-free라는 사실을 바꾸지 않고, 자명한 통과자를 랭킹에서 배제하는 자격검사다.

### 6.2 최저비용 프로브 — 먼저 실행할 2셀

5도면은 145 아카이브에서 label 없이 `{작은/큰 segment count, unit known, INSERT 있음}`을 가능한 범위에서 포괄하도록 deterministic하게 선택한다.

| 셀 | 가설 | 지표 | 합격선 | 킬/분기 | 예산 | 시드 |
|---|---|---|---|---|---|---|
| `P-R: deterministic(v0)×rotate` | frozen v0의 wall label은 90° 회전에 불변 | R-META macro, mapping errors, sentinels | PASS≤0.02 | transform oracle 오류면 harness 수정; R-META>0.10이면 rotation normalization 선조사 | 패킷 계약상 두 probe 합계 30분 | 무시드, angle 90° |
| `P-U: deterministic(v0)×unit-change` | mm↔m 물리 동치 뒤 wall label은 불변 | 같은 지표 + unit certificate | PASS≤0.02 | R-META>0.10이면 gap/unit normalization을 P2에서 먼저 수리 | 위와 합산 | 무시드, metadata가 허용하는 반대 단위 1회 |

probe는 원인 가설을 빠르게 고르는 위생검사다. 여기서 PASS해도 나머지 26셀을 통과한 것이 아니다. unit metadata가 없는 도면에 임의 단위를 부여하지 않으며, unit-known 도면을 선택할 수 없으면 `P-U BLOCKED_DATA`다.

### 6.3 본 실험 28셀

모든 셀의 평가 population은 동일한 40도면이고, transform별 parameter 수만 2.2절 표대로 다르다. 다음 표의 시간은 **셀별 실행 중단 상한 제안**이지 처리시간 실측이 아니다.

| 셀군 | 셀 ID | 셀별 가설 | 지표/합격선 | 셀별 킬 조건 | 셀별 예산 | 시드 |
|---|---|---|---|---|---|---|
| deterministic(v0) | `F01` translate, `F02` rotate, `F03` scale, `F04` unit, `F05` explode, `F06` rename, `F07` jitter | v0 label이 해당 relation에 불변이며 scale/unit geometry는 등변 | R-META; PASS≤0.02, INC≤0.10, FAIL>0.10 | 해당 셀 >0.10이면 relation-specific FAIL; 7셀 전부 FAIL이면 P2/CL-B의 unit·표현 정규화 전까지 프로그램 사다리 중단 | 셀당 CPU 2시간 상한 | 공통 catalog seed; 결정 실행을 replicate로 부르지 않음 |
| classical-ML | `F08`–`F14`, 위와 같은 순서 | frozen HGBDT가 val 성능을 얻은 표현 우연성이 아니라 같은 벽 의미를 보존 | 동일 | 7셀 전부 FAIL이면 representation normalization 없이는 부적격; sentinel 미달이면 랭킹 제외 | 셀당 CPU 2시간 상한 | training seed는 artifact manifest의 고정 1개; 변환 seed만 catalog |
| GNN | `F15`–`F21` | graph topology와 canonical geometry를 쓰는 frozen GNN이 transform별 자기일관성을 보존 | 동일 + graph LID coverage | adjacency audit 실패면 셀 실행 전 kill; 7셀 전부 FAIL이면 absolute coordinate/feature normalization 전 부적격 | 셀당 RTX 5070 Ti 4 GPU시간 상한 | upstream training seed 고정; seed 효과를 P5 interaction과 혼동하지 않음 |
| VLM | `F22`–`F28` | frozen render/prompt/model pipeline이 동일 벽을 같은 LID에 투영 | 동일 + inverse-warp residual + checksum | vision 미지원, pixel↔LID exact test 실패, checksum 불일치면 실행 kill; 7셀 전부 FAIL이면 crop/absolute-position 과적합으로 부적격 | 셀당 DGX 4 GPU시간 상한 | temperature 0, greedy; renderer/catalog seed 고정 |

각 transform의 구체 파라미터 표본은 다음과 같이 셀 안에 nested된다: translate 3, rotate 3, scale 3, unit 2, explode 1, rename 3, jitter 3. 이들을 18개의 독립 replicate라고 부르지 않는다. 불변이면 parameter 값에 무관해야 하므로 같은 셀의 사전등록 population이다.

본 실험의 선결 및 판정 순서는 고정한다.

1. Q0 transform oracle PASS.
2. Q1/Q2 family qualification.
3. cheapest probe.
4. 40도면 28셀 full factorial; 실행 순서는 cache locality를 위해 drawing→transform→family여도 되지만 logical run order를 기록한다.
5. A, B, A×B exact matrix와 status 작성.
6. 결과를 본 뒤 detector/config를 바꾸면 기존 결과를 덮어쓰지 않고 새 method ID로 val부터 다시 시작한다.

### 6.4 val/test 및 confirmation

classical/GNN/VLM의 학습과 threshold 선택은 train/val에서 끝낸다. P5 개발 중 CubiCasa test를 metamorphic 용도로도 읽지 않는다. label을 보지 않더라도 test 반응으로 preprocessing을 고칠 수 있기 때문이다. 최종 method별 test는 accuracy metric과 지원되는 metamorphic subset을 한 job manifest로 묶어 **단발** 실행한다.

confirmation은 sentinel-qualified family 중 7셀 worst-case R-META가 가장 낮은 family를 선택해, 학습/개발에 없던 holdout firm에서 한 번 실행한다. selection metric은 mean이 아니라 worst relation으로 봉인한다. known 7관계에는 새 parameter 값을 사용하되 catalog type은 늘리지 않는다. 합격은 7셀 모두 `≤0.02`, mapping/integrity 오류 0이다.

원 제안의 “새 변환 1종 추가”와 “명시된 7개 밖 관계는 발명하지 않음”은 동시에 완수할 수 없다. 본 패킷의 더 엄격한 abstention을 따른다. 여덟 번째 transform은 governance가 카탈로그를 개정하기 전까지 **deferred**이며 confirmation status는 `PASS_WITH_DEFERRAL`이다. 허용되는 확인은 기존 7관계의 held-out parameter뿐이다.


---

## [doe_P6] — ## 6. 실험 셀 정의 (64 lines)

## 6. 실험 셀 정의

공통 규칙: **val=개발·튜닝 허용, test=방법당 단발**, 합격선 평가 전 봉인, 셔플 대조군, 증거 xlsx, 실패도 사유 기록.

### 6.1 Cheapest probe (반나절)

| 항목 | 내용 |
|------|------|
| 셀 | `F-R-SYN` 우선 (예시원 T-SYN); 여유 시 `F-R-SIL` |
| n | 실도면 또는 divergent 후보 **5장** |
| 가설 | 프런티어 VLM이 래스터 평면도에서 벽을 silver로 찍을 **능력 존재** |
| 지표 | 파싱 성공률; handle 또는 선분 단위 합의(가용 진리와); E1.5 B1/B4 예비 |
| 합격선 | “완전 무작위보다 유의하게 벽 구조 언급” — **binary capability**; F1 합격선 아님 |
| 킬 | 능력 0 → frontier 6셀 종료, open만. API 미승인 → `BLOCKED`(킬과 구분) |
| 예산 | API 소액 + 0.5일; GPU 불필요 |
| 시드 | temp=0; few-shot 순서 고정; 프롬프트 해시 기록 |

### 6.2 Frontier 6셀 (juror 자격 실험)

| 항목 | 내용 |
|------|------|
| 가설 | raster ≫ vector; fused는 raster에 근접하거나 혼란; C는 few-shot 품질로만 약효과 |
| 지표 | silver 품질(B1 well-posed, B4 vs 탐지기/외부); R-SILVER 교차; **SoT 승격 지표 사용 금지** |
| 합격선 | B1≥0.70 **AND** B4 Pearson≥0.70 (calibration) → juror 자격 |
| 킬 | 신호 0(E1.5 대비) → juror 자격 미달, silver 학습 타깃 경로 봉쇄 |
| 예산 | API 중심; 가문 2×셀; 도면 샘플 상한 prereg |
| 시드 | few-shot 집합·순서 freeze |

### 6.3 Open-finetune 6셀 (탐지기 후보)

각 셀 공통:

| 항목 | 내용 |
|------|------|
| 가설 | 본문 effects: fused>vector>raster; T-SYN이 T-SILVER보다 전이 안정(또는 그 반대 — 둘 다 허용, 사전 방향은 SYN 선호) |
| 지표 | CubiCasa val F1/P/R/AUC; R-SYN F1; R-META 위반율(게이트 준비 시); 셔플 AUC |
| 제안 합격선 (초안·봉인 대상) | (1) val F1 ≥ GBDT **0.517** 또는 (2) R-SYN/R-META에서 P2 강건 v0를 **동시에** 상회. 둘 다 실패 시 계열 kill |
| 킬 | 최적 open 셀이 위 합격선 실패 → VLM 투자 무이득 하차 |
| 예산 | 셀당 LoRA 1 epoch: 로컬 0.5–2일 규모(서브샘플 먼저); full 12은 DGX |
| 시드 | 본선 seed=17 고정; 최적 셀만 seed=23 민감도 |

**셀별 한 줄 가설**

- `O-R-*`: 래스터가 FP 아이콘 억제에 기여하는지.  
- `O-V-*`: 벡터 직렬화만으로 GBDT 특징을 넘는 표현이 있는지(실패 시 “VLM vector는 중복”).  
- `O-X-*`: 융합 이득(표적). A×B는 frontier 대비로 추정.  
- `*-SIL`: silver 증류 위험 — CL-K와 교차 보고.

### 6.4 Confirmation run

| 항목 | 내용 |
|------|------|
| 대상 | 최적 (mode, modality, supervision) |
| 내용 | hold-out firm 재실행; frontier면 **배심원 자격만** 재확인(SoT 금지) |
| status | 패킷대로 `PASS_WITH_DEFERRAL` 슬롯(UNRUN) |
| 시드 | 본선과 동일 + 1회 반복 |

### 6.5 Effects / interactions 슬롯 (UNRUN)

- effects_table 슬롯: A·B·C main + A×B·B×C  
- interactions_found: 표적 A×B (사전: 큼); B×C (융합의 감독원 민감도)  
- 확정 실험 전 **순위표=판정 아님** (card rule 3)

---


---

## [feyerabend_P1] — ## 6. 실험 셀 정의 (104 lines)

## 6. 실험 셀 정의

### 6.1 실행 순서

```text
E0 생성기·fidelity
        ↓
E1 synthetic 정확도 ──→ E2 metamorphic
        ↓                    ↓
CL-A 감사 완료 ───────→ E3 messy top-20 판별
        ↓
E4 CubiCasa val·proxy 감사 ──→ [모든 gate 봉인] ──→ E6 test 단발

T5 counsel + raster round-trip ──→ E5 FloorPlanCAD NC 탐구
```

E3이 P1의 핵심 판별 셀이다. E4/E5는 외부 전이와 독립성 감사이며 E3 실패를 구제하는 투표가 아니다.

### E0 — PR-1 wall-face 생성기와 T2 fidelity

- **가설:** latent wall/room graph에서 여러 CAD 표현을 내보낸 합성팩이 dimension-only 기존 합성팩보다 divergent-20의 표현 현상을 충실히 포함할 수 있다.
- **데이터:** cheap 단계 10장, 제안 seed `{1101,…,1110}`. 각 latent plan은 최소 두 representation mutation을 갖는다. development와 hidden mutation seed를 분리한다.
- **지표:** entity-family coverage, normalized primitive-length KS, entity-type TV, face-degree/endpoint-gap 분포, truth provenance 완전성, real-vs-synthetic two-sample discriminator(진단).
- **제안 합격선:** LINE/LWPOLYLINE/ARC/HATCH/INSERT와 gap/overshoot/distractor family가 모두 존재하고, truth provenance가 완전하며, 사전 지정 핵심 분포의 `KS_max≤0.30` 및 `TV≤0.20`. 이 값들은 제안 prereg band다. 기존 다이제스트의 B1 `KS 0.5792, TV 0.265`는 현 generator가 이 문턱을 통과했다는 증거가 아니다.
- **킬 조건:** truth가 emitted parallel double-line에서 역으로 만들어져 counter-theory와 독립적이지 않음, hidden mutation에서 provenance 손실, 또는 fidelity band 실패. 실패하면 E1 이후를 중단한다.
- **예산:** 로컬 CPU 2~4시간 생성/검사 + 구현 2~3 인일, GPU 없음.
- **시드 계획:** generator seed와 mutation seed를 별도 기록. hidden seed는 config freeze 전 결과를 보지 않는다.

### E1 — synthetic bridge/ribbon 정확도

- **가설:** parallel feature 가중치 0에서도 face-first가 known bridge를 회수한다.
- **arm:** strict face-only, repaired face-only, repaired+parallel-ablation, LINE-pair v0.
- **지표:** bridge endpoint exact match, ribbon IoU matching 후 bridge recall/precision, per-handle P/R/F1, virtual-repair 의존, bridge-count ratio, 0-wall/all-wall sentinel.
- **제안 합격선:** 패킷 prereg를 따라 synthetic recall@벽리본 `≥0.90`. 추가 안전 gate로 모든 sentinel 의미가 정확하고, 예측 bridge 수 중앙값이 truth의 두 배를 넘지 않으며, primary face-only arm이 합격해야 한다.
- **킬 조건:** face-only가 0.90 미만, all-wall 예측으로 recall을 얻음, repair edge가 wall handle로 유출, 또는 parallel-ablation만 합격.
- **예산:** cheap 10장은 CPU 1시간 이내 목표, full hidden pack은 야간 8시간 상한 제안. peak RAM 32GB soft cap, 48GB hard stop 제안.
- **시드 계획:** E0 development seed로 config 선택 후 hidden seed를 한 번 평가. 실패 후 hidden seed에 재튜닝하지 않고 새 prereg cycle로 간다.

### E2 — rigid/scale/metamorphic 불변

- **가설:** scale-homogeneous threshold와 provenance mapping 때문에 bridge 의미가 전역 변환 뒤 보존된다.
- **변환:** 원본, translation, rotation, reflection, uniform scale. 제안 scale factor는 `{0.1, 1, 10}`이며 단위 변경과 수치 안정성을 동시에 압박한다.
- **지표:** inverse-transform 뒤 bridge provenance-set Jaccard, endpoint pair equality, ribbon IoU, quality-status 전이, handle score 최대차.
- **제안 합격선:** provenance bridge set Jaccard `1.0`, endpoint pair exact equality, inverse-warp ribbon IoU `≥0.99`. 수치는 제안 gate다. 부동소수 tolerance는 config에 봉인한다.
- **킬 조건:** scale에서 systematic bridge 증감, transform에 따라 repair tie-break가 달라짐, 또는 0-wall sentinel이 변환 후 wall을 생성. 기존 다이제스트의 B4 scale arm 0.7624 strict FAIL은 P1이 특히 넘어야 할 선행 실패다.
- **예산:** synthetic 10장×변환 battery CPU 1~2시간. E3 통과 뒤 실측 145장은 로컬 야간 batch.
- **시드 계획:** geometry seed는 E1과 같고 transform parameter list는 prereg에 고정. transform별 새 random noise를 넣지 않는다.

### E3 — messy divergent-20 discrimination (T27, 핵심)

- **선결:** CL-A T3/T4/T8 감사 완료, handle 실재성 확인, sorting artifact 재계산, frozen v0에서 `n_pairs=0` 재확인.
- **가설:** LINE-pair v0가 계속 0인 def에서 face bridge가 LLM-cited handle의 의미 있는 부분을 회수한다.
- **arm:** frozen LINE-pair v0, strict face-only, repaired face-only. parallel/name 가중치 arm은 진단용이며 main 판정에서 제외.
- **지표:** def별 LLM-handle containment, 중앙값과 drawing-level bootstrap interval, bridge/LLM-handle count ratio, repair 비율, dangle/cut/invalid, abstention, matched control의 explosion.
- **VIABLE:** synthetic E1/E2를 동시에 통과하고, top-20 containment 중앙값 `≥0.40`이며, LINE-pair는 재확인 후 계속 0. 또한 중앙값 bridge 수가 LLM handle 수의 10배를 넘지 않는다.
- **약화/킬:** containment 중앙값 `<0.15`이면 관측 언어 교체 가설 약화. face 추출이 open/noisy linework에서 붕괴하고 def당 median bridges가 LLM handle 수의 `>10×`이면 기각 후보. `0.15~0.40`은 성공으로 올리지 않고 `INCONCLUSIVE`다.
- **outcome A:** face bridge가 회수하고 LINE-pair가 0 → `kills: reigning`.
- **outcome B:** face도 거의 0이거나 과다분할로 metric이 무의미 → `kills: counter`.
- **예산:** 로컬 CPU 수 시간, hard wall-clock 8시간 제안. 한 def가 60분을 넘으면 timeout failure로 기록하고 전체를 억지로 완료하지 않는다.
- **시드 계획:** deterministic. tie-break salt를 config에 고정하며 여러 salt 중 좋은 것을 고르지 않는다. bootstrap seed 하나를 봉인하고 raw per-def 값도 전부 공개한다.

### E4 — CubiCasa val 및 proxy 독립성 감사

- **가설 1:** face topology는 기존 6 geometry feature에 없는 조건부 정보를 준다.
- **가설 2:** synthetic/LINE-pair/face가 같은 평행 prior의 복제물이 아니라, human Wall label에 대해 서로 다른 오류 구조를 보인다.
- **arm:** v1 `fast_score`, 기존 6-feature GBDT, deterministic face-only, GBDT+face, shuffled-label control.
- **지표:** val per-handle P/R/F1/AUC, drawing-bootstrap ΔF1, v1/GBDT false-negative에서 face의 conditional precision/recall, 오류 Jaccard/phi, representation family별 성적, name-mask ablation.
- **제안 합격선:** GBDT+face가 기존 GBDT val F1 0.517 대비 absolute `≥0.03` 개선하고 paired bootstrap lower bound가 0보다 크거나, 개선폭이 작아도 v1/GBDT zero-candidate 구간에서 사전등록한 conditional precision `≥0.50`로 고유 정답을 회수한다. 이 두 수치는 제안 band다.
- **독립성 gate:** face와 LINE-pair prediction Jaccard가 `≥0.90`이고 error phi도 `≥0.90`이면 독립 proxy로 합산하지 않는다. 단, 상관이 낮다는 사실만으로 face가 정확하다고 말하지 않고 human label metric을 함께 요구한다.
- **킬 조건:** shuffled control이 비정상 성능, layer/class leakage, drawing split 위반, 또는 face feature가 val 개선 없이 기존 오류를 그대로 복제.
- **예산:** feature 생성 로컬 야간 8~16시간 제안, GBDT 학습은 기존 64GB 경로 재사용, GPU/DGX 없음.
- **시드 계획:** 기존 split 고정. GBDT seed `{17, 29, 43}`을 prereg하고 평균과 최악 seed를 보고한다. val을 본 뒤 seed를 추가하지 않는다.

### E5 — FloorPlanCAD raster transfer (NC, 탐구)

- **선결:** T5 counsel 서면, project/group split 확보, synthetic raster round-trip 통과.
- **가설:** raster contour로 변환된 경우에도 face ribbon이 wall segmask와 공간적으로 겹친다.
- **arm:** 고정 contour-vectorizer+face-only, contour-vectorizer+LINE-pair. bbox는 진단만.
- **지표:** pixel ribbon IoU/P/R, connected component over/under-segmentation, vectorization 실패율, raster round-trip 오차.
- **제안 합격선:** 제품 gate로 쓰지 않는다. 탐구 보고 조건은 round-trip IoU `≥0.95`와 provenance에 해당하는 contour mapping 완전성이다. 이 수치는 제안된 계측 신뢰성 gate다.
- **킬/중단:** counsel 미해결, group split 부재, SVG/handle label이 없는데 line-level 성적을 요구, 또는 vectorizer 오차가 face 오차보다 커 분리가 불가능.
- **예산:** 허가 후 소규모 holdout CPU 4~8시간. 전체 5,308장 batch는 탐구 결과가 해석 가능할 때만 별도 승인.
- **시드 계획:** deterministic contour parameters를 synthetic에서 봉인. FloorPlanCAD 결과로 1.dwg hyperparameter를 변경하지 않는다.

### E6 — CubiCasa test 단발

- **선결:** E0~E4 prereg gate, license clearance, 선택 arm·threshold·seed aggregation·xlsx schema 봉인. E5는 main test의 선결이 아니다.
- **가설:** val에서 선택된 하나의 face arm이 untouched test에서도 baseline 대비 이득을 유지한다.
- **실행:** 기존 GBDT baseline과 선택한 face arm을 test 400장에 각각 한 번 평가한다. 실패한 run을 고쳐 같은 방법 이름으로 재실행하지 않는다. 코드/환경 장애면 `VOID_TECHNICAL` 근거를 남기고 Paul의 새 prereg 승인 후 별도 run id로만 재개한다.
- **지표:** per-handle P/R/F1/AUC, drawing-paired ΔF1, representation family error, abstention, runtime/RAM.
- **제안 합격선:** 선택 face arm의 test ΔF1이 baseline 대비 `≥0.03`이고 paired interval 하한이 0보다 크며, shuffled control은 사전등록된 chance 진단을 벗어나지 않아야 한다. 수치는 test 열람 전 봉인할 제안값이다.
- **킬 조건:** ΔF1 gate 실패, recall을 bridge explosion으로 산 경우, test 후 threshold 변경 필요, 또는 split/leakage 발견.
- **예산:** 로컬 야간 1회, DGX 없음.
- **시드 계획:** 학습 seed는 E4에서 미리 정한 집계 규칙으로 하나의 model artifact를 선택한다. test seed shopping 금지.

### 6.2 공통 통계·판정 규칙

- bootstrap 단위는 handle이 아니라 drawing/def다.
- undefined containment, abstention, timeout을 0이나 1로 몰래 치환하지 않는다. 분모와 실패 수를 별도 보고한다.
- 모든 threshold는 해당 평가 set을 보기 전에 prereg sheet에 봉인한다.
- multiple arm 결과는 primary/secondary를 미리 구분한다. primary가 실패했는데 secondary 하나가 좋아도 `PASS`로 바꾸지 않는다.
- 실패한 synthetic fidelity, counsel, CL-A audit는 downstream cell을 `BLOCKED`로 만들며, 빈 결과를 counter-theory kill로 세지 않는다.

---


---

## [feyerabend_P2] — # 6. 실험 셀 정의 (223 lines)

# 6. 실험 셀 정의

모든 threshold는 실행 전 prereg.json과 evidence.xlsx PREREG sheet에 동시에 봉인한다. primary 설정을 본 뒤 sensitivity 설정으로 판정을 교체하지 않는다.

## 셀 C0 — 실제 벽 합성기 및 fidelity 자격

**가설.** 새 generator가 dimension-only stub이 아니라 source-handle pair truth를 만들며, 기존 합성팩의 표현 결손을 줄인다.

**데이터.** canonical base scene 50개와 divergent-20에서 추출한 phenomenon checklist. scale copy 전 \(\kappa=1\) 장면으로 fidelity를 본다.

**지표.**

- wall truth pair가 실제 존재하는 scene 비율
- LINE/LWPOLYLINE/INSERT 외 ARC/SPLINE/HATCH와 nested block/nonparallel fragment coverage
- real-vs-synthetic entity/geometry distribution KS와 TV
- zero-wall/all-wall sentinel의 truth integrity

**제안 합격선.**

- positive scene에는 하나 이상의 source-handle truth pair
- 지정 mutation family가 각각 최소 한 scene에 존재
- 제안 fidelity gate: KS ≤ 0.20, TV ≤ 0.10
- truth validator 오류 0

KS/TV 문턱은 문헌 인용이 아니라 사전등록 제안값이다. 패킷의 기존 B1 관측 KS 0.5792, TV 0.265보다 엄격한 자격을 요구한다.

**킬/중단 조건.** wall code가 없거나 fidelity gate가 실패하면 synthetic 결과는 plumbing diagnostic만 가능하며 P2 이론 판별 PASS를 금지한다. PR-1/T2 BLOCKED로 종료한다.

**예산.** 로컬 CPU와 운영자 2시간 상한.

**시드.** base scene \(j=0,\ldots,49\)의 seed는 SHA-256("feyerabend_P2:"+j)의 앞 32bit로 결정한다. 동일 \(j\)의 네 scale은 같은 seed와 topology를 쓴다.

## 셀 C1 — Anchor scale 추정과 confidence calibration

**가설.** 벽 pair label 없이 DIM/TEXT/GRID만으로 raw-unit scale을 추정하며, HIGH confidence가 실제 정답 scale과 일치하는 선택적 subset을 만든다.

**데이터.** C0를 통과한 200 IR. anchor corruption diagnostic에는 복제, stale override, suffix 제거, 한 개 outlier를 deterministic mutation으로 추가한다.

**지표.**

- \(e_s=|\log(\hat s/s_{\mathrm{true}})|\)
- HIGH subset의 scale-factor relative error
- HIGH coverage
- confidence bin별 accuracy
- corruption 전후 status transition
- pair-label permutation 전후 anchor artifact digest

**제안 합격선.**

- HIGH subset의 95% 이상이 true scale 대비 상대오차 5% 이하
- 네 scale 각각 HIGH coverage 0.60 이상
- pair-label permutation 전후 anchor digest 완전 동일
- 단일 강한 outlier가 들어가도 scale mode가 바뀌지 않거나 status가 LOW로 내려감

모두 제안값이다.

**킬 조건.** HIGH가 틀린 scale을 자신 있게 내거나, label permutation이 anchor output을 바꾸거나, scale별 confidence coverage가 한 방향으로 붕괴하면 counter theory의 실행체를 kill한다.

**예산.** 로컬 CPU 1시간 상한.

**시드.** C0의 paired 50 seeds 재사용. corruption 종류는 base_scene_id hash로 고정하며 추가 random search는 하지 않는다.

## 셀 C2 — Primary 4-scale absolute 대 relative 판별

**가설.** 좌표 스케일만 바뀌면 A30은 극단 scale에서 붕괴하고 R05-40은 모든 scale에서 유지된다.

**데이터.** 4 scale × 50 IR = 200, 동일 handle truth. C0/C1 통과 후 한 번만 판정한다.

**지표.**

- scale별 unordered pair precision, recall, F1
- base scene별 paired \(F1_R-F1_A\)
- mapped pair-set Jaccard across scales
- per-handle wall_member F1은 보조
- A50 shadow 결과는 별도 열

**제안 합격선.**

- 모든 \(\kappa\in\{0.001,0.01,1,1000\}\)에서 relative-gap pair F1 ≥ 0.85
- \(\kappa\le0.01\) 또는 \(\kappa\ge100\)인 평가점에서 absolute-gap pair F1 ≤ 0.40
- relative mapped pair-set Jaccard ≥ 0.95

앞의 두 문턱은 패킷 prereg band다. Jaccard 문턱은 추가 제안값이다.

**판별.**

- A: absolute만 붕괴하고 relative가 유지되면 kills: reigning, 즉 절대 gap 관측을 기각한다.
- B: relative도 동반 붕괴하면 kills: counter.
- absolute가 극단에서도 유지되면 P2가 상정한 단위-유물 메커니즘이 이 harness에서 작동하지 않은 것이므로 reigning을 죽이지 못한다.

**예산.** 로컬 CPU 2시간 상한.

**시드와 도면-단위 split.** paired 50 seeds를 쓴다. scale은 seed가 아니라 완전요인이다. parser와 threshold 개발은 이 200 IR에 포함되지 않는 손계산 \(\kappa=1\) fixture에서 끝내고, 네 scale의 200 IR은 모두 config 봉인 뒤 한 번 여는 평가 split으로 둔다. scale별 별도 tuning, 한 scale 결과를 본 뒤 다른 scale 설정 변경, 같은 base scene의 다른 scale label을 estimator 입력으로 전달하는 것을 금지한다.

## 셀 C3 — 누수·sentinel·metamorphic 통제

**가설.** C2의 승패는 라벨 누수나 “모두 벽” 예측이 아니라 scale normalization에서 온다.

**데이터.** C2의 200 IR에 포함된 zero-wall/all-wall 및 distractor scenes, pair-label permutation, dimension-table def permutation.

**지표.**

- label permutation 전후 prediction artifact digest
- zero-wall false-positive pair rate
- all-wall recall
- rigid transform/translation/reflection 뒤 mapped pair Jaccard
- dimension-table permutation 뒤 confidence와 scale error

**제안 합격선.**

- pair-label permutation 전후 prediction digest 동일
- zero-wall distractor 후보 중 false-positive rate ≤ 0.10
- all-wall pair recall ≥ 0.85
- 강체변환 mapped Jaccard = 1.0
- 잘못된 def의 dimension table을 주입하면 HIGH를 유지한 채 정답 scale로 우연히 맞는 현상이 반복되지 않음

**킬 조건.** label permutation이 예측을 바꾸거나, sentinel floor를 못 넘거나, 강체변환이 깨지면 C2 결과를 INVALID 처리한다. dimension permutation에서도 성능이 유지되면 anchor가 실제로 사용되지 않았을 가능성이 있으므로 메커니즘 주장을 kill한다.

**예산.** 로컬 CPU 1시간 상한.

**시드.** def permutation은 SHA-256 manifest 순서의 cyclic shift 하나로 봉인한다. 여러 permutation 중 유리한 것만 고르지 않는다.

## 셀 C4 — 실측 DIM-rich 30 def 선택적 A/B

**가설.** HIGH anchor subset에서 R-safe가 frozen absolute arm보다 frozen LLM likelihood와의 pair-count 상관을 단방향으로 높이고, LOW/NONE에서는 정확히 불변이다.

**데이터.** 1.dwg staged DXF의 384 def 중 pair/LLM 결과를 보지 않고 valid DIM 수 상위 30개. 동률은 def_id 순서. LLM likelihood는 기존 frozen artifact만 사용한다.

**지표.**

- anchor status와 DIM-geometry log residual
- def별 \(N_A,N_R,N_R-N_A\)
- HIGH subset의 Pearson \(r_A,r_R,\delta r\)
- paired def bootstrap 95% interval
- LOW/NONE pair-id exact equality
- RESOURCE_ABORT 수

**제안 합격선.**

- HIGH def가 최소 10개
- HIGH subset median \(N_R-N_A>0\)
- \(\delta r\ge+0.05\)
- bootstrap interval 하한 > 0이면 production-adoption eligible
- LOW/NONE에서 pair-id equality = 1.0
- RESOURCE_ABORT = 0

**킬 조건.** 패킷 규칙대로 anchor 가능한 subset에서 \(\delta r<+0.05\)이면 belt는 퇴행적이며 kills: counter다. HIGH가 10개 미만, Pearson 입력이 무분산, 또는 frozen likelihood를 찾지 못하면 INCONCLUSIVE이며 PASS 금지다. 전체 30 평균이 올라도 HIGH 상호작용이 없으면 실패다.

**예산.** 로컬 CPU 4시간과 candidate comparison 상한. 초과 시 자원 실패를 기록한다.

**시드.** detector와 anchor fitter는 결정론적이다. bootstrap만 SHA-256("feyerabend_P2:real30")에서 파생한 단일 seed로 10,000 resample을 고정한다. 이는 제안 계산값이다.

## 셀 C5 — no-anchor 폴백 회귀와 기존 사다리 접속

**가설.** DIM 정박이 불가능한 데이터에서는 P2가 거짓 개선이나 회귀를 만들지 않는다.

**데이터.** CubiCasa val 400 SEG-IR, DIM 없는 synthetic fixtures, FloorPlanCAD adapter fixture. CubiCasa test는 사용하지 않는다.

**지표.**

- frozen v1과 R-safe의 predicted handle/pair digest equality
- val P/R/F1 delta
- fallback reason coverage
- cubicasa_ml row count/order equality

**제안 합격선.**

- prediction digest equality = 1.0
- 모든 metric delta = 0
- 모든 no-anchor item에 explicit NONE reason

패킷의 기존 CubiCasa v1 val F1 0.2358을 재측정 결과처럼 새로 주장하지 않는다. 이 셀의 요구는 수치 개선이 아니라 동일성이다.

**킬 조건.** anchor가 없는데 결과가 달라지면 안전 폴백 구현을 kill한다. 우연한 val 상승도 P2 지지로 세지 않는다.

**예산.** 로컬 CPU 1시간 상한.

**시드.** 없음. byte-level 결정론 비교.

## 6.1 조건부 단발 test 정책(현재 실험 셀 아님)

현재 자산에는 DIM-bearing real vector human pair-label test가 명시되어 있지 않다. 따라서 P2만을 위해 CubiCasa test 400을 소비하지 않는다.

향후 독립적인 DIM-bearing human-labelled vector test가 확보될 때만 다음 조건으로 단발 실행한다.

- C0–C5가 모두 유효
- \(\alpha\), confidence, candidate cap, parser version 동결
- test 접근 1회
- 주 지표 pair F1, 보조 per-handle F1
- scale/firm 단위 split
- 실패도 evidence.xlsx에 유지

그 전까지 “test PASS” 상태는 존재하지 않는다.

## 6.2 통합 판정 함수

~~~text
if C0 fails:
    verdict = BLOCKED_PR1_T2
elif C1 or C3 fails:
    verdict = INVALID_MECHANISM
elif any(relative_F1_by_scale < 0.85):
    verdict = KILLS_COUNTER_SYNTHETIC
elif not extreme_absolute_F1_all_required <= 0.40:
    verdict = DOES_NOT_KILL_REIGNING
else:
    synthetic_verdict = KILLS_REIGNING

if C4 is INCONCLUSIVE:
    overall = SYNTHETIC_SUPPORT_ONLY_NOT_ADOPTABLE
elif real_delta_pearson < 0.05:
    overall = KILLS_COUNTER_REAL
elif selective_high_confidence_pattern is absent:
    overall = NON_PROGRESSIVE_GLOBAL_GAIN
elif C5 identity fails:
    overall = UNSAFE_FALLBACK
else:
    overall = PROGRESSIVE_BELT_CANDIDATE
~~~

합성 지지와 실측 kill이 충돌하면 평균내지 않는다. 실측 kill condition이 belt 채택을 막고, 합성 결과는 “절대 raw gap이 scale-variant”라는 제한된 사실로만 남는다.

---


---

## [feyerabend_P3] — ## 6. 실험 셀 정의 (89 lines)

## 6. 실험 셀 정의

아래 seed 수와 동등성 margin은 모두 평가 전 봉인할 사전등록 제안이다. 기본 seed는 {11, 23, 37, 53, 71} 다섯 개로 하고, cheapest probe와 학습 arm에는 같은 초기 weight·batch 순서를 paired 적용한다. 한 seed가 자원 오류로 빠지면 다른 seed로 조용히 대체하지 않고 실패를 기록한 뒤 전체 cell을 incomplete로 둔다.

### C0 — SILVER-FIREWALL 계약 시험

- 가설: gate-only 산출은 silver 파일의 존재·내용·순서에 인과적으로 의존하지 않는다.
- 조작: silver sidecar 정상/삭제/행 셔플/전부 상수의 네 조건에서 deterministic CPU smoke train을 실행한다.
- 지표: 허용 입력 schema, import dependency, split hash, checkpoint byte hash, 예측 hash.
- 제안 합격선: 네 조건의 gate-only artifact가 byte-identical이고 금지 필드 접근이 0건.
- kill condition: 어떤 silver 변형이라도 gate-only batch, checkpoint, prediction을 바꾸면 P3 구현은 즉시 무효.
- 예산: 로컬 CPU 수십 분 이내 계획; GPU 불필요.
- seed 계획: 고정 seed 1개로 계약을 먼저 증명하고, full run 다섯 seed에서는 dependency manifest를 반복 저장한다.

### C1 — PR-1 FIDELITY·SENTINEL 자격 셀

- 가설: 확장 합성팩은 실제 도면 현상과 충분히 맞고 precision·recall이 모두 정의되는 채점우주를 제공한다.
- 지표: 기존 B1 fidelity gate, 엔티티 구성, positive/negative 수, candidate recall, 0-wall/all-wall/mixed sentinel.
- 제안 합격선: 기존 B1 계약 PASS, 세 sentinel PASS, mixed pack에서 positive와 negative 모두 존재. 패킷에 없는 B1 숫자를 새로 발명하지 않는다.
- kill condition: B1 FAIL, S 음성 0 지속, handle mapping 불완전 중 하나라도 있으면 C2 이후의 방법론 판결 금지.
- 예산: 생성기 구축은 PR-1 별도; 본 셀의 평가는 로컬 CPU.
- seed 계획: 생성 seed 다섯 개를 manifest로 고정하고 family별 결과를 합쳐 숨기지 않는다.

현재 증거 판정: B1은 KS 0.5792, TV 0.265로 FAIL이고 S 음성은 0개이므로 **현재 C1은 FAIL/BLOCKING**이다.

### C2 — CHEAPEST-PAIR 1 epoch 셀

- 가설: 같은 합성·초기화에서 gate-only가 silver-distill보다 metamorphic에 강하고 합성 F1은 비열등하다.
- arm: G=gate-only, S=silver-distill. 두 arm은 정확히 같은 합성 drawing·handle·batch 순서를 보고, S만 동일 합성 handle에 정렬된 family-balanced q를 추가 target으로 받는다. parameter는 공유하지 않고 초기 weight만 복제한다. 동일 합성 q가 없으면 실도면 silver로 대체하지 않고 BLOCKED다.
- 지표: 합성 F1, metamorphic pass rate, candidate recall, closure rank consistency, 학습 후 LLM-Pearson.
- 제안 합격선 A: median(meta_G-meta_S)≥0.10이고 F1_G≥F1_S-0.02. 이때 패킷 판정어는 kills: reigning이다.
- 판정 B: silver-distill이 합성·metamorphic·sentinel gate 모두에서 우월하면 kills: counter다.
- 동등성 운용: |차이|≤0.02를 제안상 동등으로 보고, silver-distill이 합성·metamorphic에서 동등 또는 우월하면 anti-silver 강한 주장을 약화한다.
- kill condition: gate-only가 sentinel을 악화시키거나, meta 우위가 단 한 seed/변환 family에만 존재하거나, silver가 shared encoder로 누수되면 cell 무효.
- 예산: 로컬 RTX 5070 Ti 반나절 또는 DGX 소형 배치라는 패킷 예산. DGX 불통이므로 로컬 우선.
- seed 계획: paired 다섯 seed. 1 epoch 결과로 방향이 없으면 full sweep 중단.

### C3 — SOURCE-ABLATION 최종 val 셀

- 가설: 합성+metamorphic+closure 조합이 어느 한 대리의 단일 prior가 아니라 상보적 신호를 제공한다.
- arm: synthetic-only, synthetic+meta, synthetic+closure, synthetic+meta+closure. 각 arm에 silver가 없는 gate-only를 사용한다.
- 지표: 합성 F1, 변환 family별 pass, closure holdout ranking, zero/all-wall sentinel, 후보 recall.
- 제안 합격선: 최종 arm이 합성 F1≥0.80과 metamorphic pass≥0.90을 동시에 만족. LLM-Pearson은 checkpoint 동결 후 ≤0.35.
- 과적합 판정: 합성 F1≥0.80인데 metamorphic<0.50이면 합성 과적합.
- kill condition: synthetic-only와 최종 arm이 모든 핵심 지표에서 동등하고 closure/meta가 오류만 추가하거나, final pass가 빈/전벽 sentinel에 의존하면 복합 메커니즘을 죽인다.
- 예산: 로컬 GPU 야간 실행과 CPU closure 전처리. exact closure가 불가능한 도면은 근사 결과와 분리한다.
- seed 계획: 다섯 seed, transformation seed는 model seed와 분리해 manifest에 고정.

### C4 — CUBICASA-VAL 외부 전이 셀

- 가설: anti-silver gate가 합성 내부 점수만 맞추지 않고 사람 라벨 벡터축으로 전이한다.
- 학습: CubiCasa label을 주 model loss에 넣지 않는다. 권리 확인 후 train geometry의 meta/closure만 조건부 사용한다.
- 지표: val P/R/F1/AUC, 클래스별 FP, scale 구간별 성능, candidate recall. v1 F1 0.2358과 GBDT F1 0.517을 고정 baseline으로 둔다.
- 제안 승격선: val F1이 최소 GBDT 0.517 이상이고, metamorphic≥0.90 및 sentinel을 유지해야 test 개봉 후보가 된다. 이 수치는 기존 측정 기준선을 승격선으로 재사용하는 제안이지 새 결과가 아니다.
- kill condition: val 향상이 silver 상관 상승에만 동반되고 meta/closure가 악화되거나, Direction/BoundaryPolygon/Door/Window/DimensionMark 중 특정 비벽군을 벽으로 흡수해 총 F1만 맞춘 경우 생산 승격을 죽인다.
- 예산: 이미 변환된 SEG-IR 사용, 로컬 GPU/CPU.
- seed 계획: C3의 다섯 frozen checkpoint를 그대로 평가하며 CubiCasa val을 보고 재학습하지 않는다.

### C5 — REAL-384 독립성·충돌 셀

- 가설: 실도면에서 gate-only는 LLM과 낮은 상관을 억지로 최적화하지 않고도 변환 안정성과 공간폐쇄를 유지한다.
- 데이터: 1.dwg staged DXF의 도면정의 384개. 정의 단위 고정 split과 handle map 사용.
- 지표: 변환 family별 exact-set pass, zero-wall 도면율, closure score 분포, Pearson, M_conflict 크기와 구성, full-vs-name-blind.
- 제안 합격선: 전체 metamorphic pass≥0.90, LLM-Pearson≤0.35, sentinel PASS. 실도면 정답 F1은 보고하지 않는다.
- kill condition: 낮은 Pearson이 빈 탐지기, 후보 recall 붕괴, alignment unknown의 제외로 만들어졌으면 무효. scale pass가 현재 0.7624에서 개선되지 않으면 scale-equivariant 주장을 죽인다.
- 예산: 로컬 CPU candidate/closure + GPU scoring. 최대 412,775 선분 정의는 chunk/tiling.
- seed 계획: C3 checkpoint 다섯 개. LLM sidecar는 모델별 seed가 아니라 고정 jury evidence로 취급하고 두 어휘 가문 단위로 bootstrap한다.

### C6 — FROZEN-TEST 단발 셀

- 가설: C0~C5를 통과한 단일 frozen 구성은 미접촉 CubiCasa test에서도 외부 전이를 유지한다.
- 개봉 조건: C0 PASS, C1 PASS, C3 최종 band PASS, C4 승격선 PASS, config/checkpoint/threshold/evidence schema hash 봉인.
- 지표: preregistered test P/R/F1/AUC와 클래스별 FP. 어떤 지표도 개봉 후 threshold 선택에 쓰지 않는다.
- 제안 합격선: 개봉 전에 evidence_grid에 수치와 판정식을 기록한다. 최소한 val에서 정한 GBDT 기준선과 비열등성 margin을 사전 봉인하되, 현 packet만으로 test 기대값을 발명하지 않는다.
- kill condition: test 개봉 후 재학습·threshold 변경·seed 선택을 하면 단발 원칙 위반으로 방법 전체를 무효화한다.
- 예산: 추론 1회와 보고서 생성.
- seed 계획: 다섯 seed를 보고 가장 좋은 seed를 고르지 않는다. 사전등록한 ensemble 또는 고정 대표 seed 한 방식만 택해 봉인한다.

### 6.1 종합 판정표

| 결과 | 판정 |
|---|---|
| 합성 F1≥0.80, meta≥0.90, Pearson≤0.35, gate-only가 distill 대비 meta≥+0.10이고 합성 비열등 | anti-silver VIABLE, kills: reigning |
| 합성 F1≥0.80, meta<0.50 | 합성 과적합, anti-silver 실패 |
| silver-distill이 모든 핵심 gate에서 우월 | kills: counter |
| silver-distill이 합성·meta에서 동등 또는 우월 | anti-silver 강한 주장 약화 |
| 낮은 Pearson만 달성 | 무판정; 성공으로 세지 않음 |
| PR-1 fidelity 또는 sentinel FAIL | 실험 미성립/BLOCKED |
| 양쪽 arm 모두 합성·meta 실패 | 두 이론 모두 무판정, 표현/후보 생성 문제로 환원 |


---

## [feyerabend_P4] — ## 6. 실험 셀 정의 (95 lines)

## 6. 실험 셀 정의

원칙: val=개발·튜닝, test=방법당 단발, 합격선 사전 봉인, 셔플 대조군 의무(정책 입력 셔플 — 컨텍스트 φ를 순열해도 비용↑F1동일이면 누출/상수정책 의심).

### Cell S0 — Cheapest probe (학습 0, top-20 divergence def)

| 항목 | 내용 |
|------|------|
| **가설** | 고정 풀스캔 대비, 탐구 ε-greedy/정적 탐욕이 F1 저하 ≤0.02로 비용을 유의미히 줄인다. |
| **지표** | (1) 상대 비용 `cost/cost_FULL` (2) per-handle F1 (실도면은 metamorphic+수동/은 proxy 병행 시 명시) (3) 빈 예측률 (4) 행동 선택 히스토그램 |
| **합격선 (prereg)** | 비용 절감 ≥30% ∧ F1 저하 ≤0.02 → Stage 1 **VIABLE 진입**; 절감 <10% → **bandit 가치 없음, Stage 1+ kill** |
| **킬 조건** | 빈 예측으로 F1 붕괴; 또는 GREEDY≈FULL≈상한(비용만 다르고 F1 동일 천장)이 **아니면서**도 절감 <10%; 또는 해킹 모니터 κ 초과 |
| **예산** | ≤1일, 로컬 CPU, GPU 불요 |
| **시드** | 시뮬 난수 seed ∈ {0,1,2}; def 목록 고정 시드와 분리 기록 |

### Cell S0b — Greedy vs Beam 보상지형 (CL-H 공유 선결)

| 항목 | 내용 |
|------|------|
| **가설** | 동결 보상에서 greedy≈beam≈상한이면 순차 선택의 잔여 가치가 없어 **훈련 전 RL kill**. |
| **지표** | 동일 보상 함수 하 greedy/beam/random의 R 및 F1 |
| **합격선** | beam − greedy ≥ δ_pre (δ는 봉인; 제안 기본 0.02 R 단위) 일 때만 Stage 2 검토 |
| **킬 조건** | greedy≈beam → short RLVR 경로 kill (bandit만 잔류 가능) |
| **예산** | ≤1일, 학습 0 |
| **시드** | beam width {2,4,8} 기록 |

### Cell V1 — Verifier soundness (T26 사활)

| 항목 | 내용 |
|------|------|
| **가설** | metamorphic+합성(가용 시) verifier의 false-accept ≤0.01. |
| **지표** | FAR, FRR; 센티널 통과율 |
| **합격선** | FAR ≤ 0.01 (calibration P6와 정합) |
| **킬 조건** | FAR > 0.01 → **RL 계열 전체 중단** (보상 학습 금지) |
| **예산** | CL-D와 공유; 별도 1일 가능 |
| **시드** | mutation pack ID 고정 |

### Cell B1 — Tabular/linear contextual bandit (로컬)

| 항목 | 내용 |
|------|------|
| **가설** | 컨텍스트 조건화가 FULL_SCAN·정적 규칙 대비 Pareto를 지배한다. |
| **지표** | 합성(게이트 통과 후) F1; 비용; CubiCasa **val** F1/cost proxy; 해킹 서명 |
| **합격선** | FULL 대비 비용 ≥30% 절감 ∧ 합성 F1 저하 ≤0.02 → VIABLE; supervised-only(검사 없음/최소)와 Pareto 동일 → kill |
| **킬 조건** | 패킷: 해킹 또는 무이득; 또는 silver가 보상에 유입된 구현 발견 |
| **예산** | 로컬 1–2일; 5070 Ti optional |
| **시드** | train_policy seeds {10,20,30}; eval seed {99} 분리; CubiCasa test **미사용** |

### Cell B1-shuf — 셔플 대조군

| 항목 | 내용 |
|------|------|
| **가설** | φ(s) 셔플 시 정책이 비용을 못 줄이거나 F1이 붕괴 — 컨텍스트가 실제 신호. |
| **지표** | AUC-like: 비용 절감폭; F1 |
| **합격선** | 셔플 절감 ≪ 본실험 절감 ( qualitatively; 수치 밴드는 B1과 동시 봉인) |
| **킬 조건** | 셔플≈본실험 → 허위 적응/상수 정책 |
| **예산** | B1의 +20% |
| **시드** | shuffle seed {7} |

### Cell R2 — Short-horizon RLVR (조건부, DGX 또는 로컬 소형)

| 항목 | 내용 |
|------|------|
| **가설** | T≤4 다스텝이 bandit 대비 utility를 개선한다 (calibration: ≥5% 제안과 정합하되, 본 패킷 1차 밴드는 Pareto 30%/F1≤0.02가 우선). |
| **지표** | utility = αF1+βMeta−γCost; bandit 대비 비 |
| **합격선** | bandit 대비 utility 개선 ∧ 해킹 없음 ∧ FAR 유지 |
| **킬 조건** | bandit 동률/열위; 또는 C07 오용으로 θ_clf 에 gradient 유입 |
| **예산** | DGX 단기 또는 로컬 소형 2–3일; vLLM 큐 분리 |
| **시드** | ≥3; test 단발은 **최종 1회만** |

### Cell H — Reward hacking red team (상시 모니터 셀)

| 항목 | 내용 |
|------|------|
| **가설** | 비용 최소화 압력이 빈 예측·재현율 붕괴를 유도할 수 있다. |
| **지표** | empty_pred_rate; recall floor; R_proxy vs holdout F1 gap |
| **합격선** | empty_pred_rate ≤ κ; recall ≥ floor (T7과 공유 봉인) |
| **킬 조건** | 해킹 서명 확정 → 즉시 정책 학습 중단, 사건 기록 |
| **예산** | 매 셀에 내장 |
| **시드** | n/a |

### Cell X — 실측 Pareto only (합성 부재 시 대체)

| 항목 | 내용 |
|------|------|
| **가설** | PR-1 이전에도 Stage 0는 실도면 비용-품질 Pareto만으로 reigning 읽기를 흔들 수 있다. |
| **지표** | 비용, metamorphic 위반, (가능 시) 외부 val F1 — **합성 F1 주장 금지** |
| **합격선** | 절감 ≥30% ∧ metamorphic·recall floor 유지 → “라우팅 자리 실험 가치 VIABLE”; C07 **전면 배제 읽기**에 대한 soft kill 증거. 확정 `kills: reigning`은 합성 오라클 가용 후 B1에서만. |
| **킬 조건** | 절감 <10% |
| **예산** | S0에 포함 |
| **시드** | S0과 공유 |

**test 분할**: CubiCasa test 400은 **방법당 단발**. B1에서 우승한 설정 1개만, 인간 게이트(V2) 승인 후 집행. 그 전 수치를 test로 보고하지 않음.

---


---

## [feyerabend_P5] — ## 6. 실험 셀 정의 (124 lines)

## 6. 실험 셀 정의

### 6.1 공통 프리레지스트레이션

- 학습 seed 제안값은 `1729, 2718, 3141` 세 개다. 모든 architecture를 같은 seed로 실행한다.
- deterministic fixture는 seed 0과 미리 생성해 hash를 봉인한 transform 목록을 쓴다.
- architecture 선택은 val의 세 seed 중앙값으로 하고, 최악 seed와 seed별 원자료도 함께 보고한다.
- 최종 방식이 세-checkpoint 평균이라면 그 ensemble 정의 자체를 test 전에 봉인한다. test 400은 runner 호출 한 번에서만 읽는다.
- paired 비교의 제안 통계 규칙은 drawing/building 단위 bootstrap 95% interval이다. 선분을 독립 표본처럼 부풀리지 않는다.
- primary endpoint 순서는 `CRS 무결성 → FPCAD IoU → CubiCasa gate-qualified Recall@20 lift → CL-B/GBDT 대비 조건부 lift → metamorphic/sentinel → 라이선스 격리`다.
- 아래 제안 합격선은 결과를 보기 전에 machine-readable prereg로 봉인한다.

### Cell P5-00 — 권리·계보·split 봉인

- **가설**: 모든 학습 데이터와 checkpoint의 사용 범위, parent hash, group split을 결정할 수 있다.
- **지표**: counsel 문서 상태, unknown parent 수, cross-split duplicate-cluster 수, prompt/silver target 유입 수.
- **제안 합격선**: counsel이 해당 arm을 명시적으로 허용하고, unknown parent=0, cross-split cluster=0, silver 유입=0.
- **킬/정지 조건**: FloorPlanCAD 원 도면·라벨·파생 weight의 연구 사용이 허용되지 않으면 NC arm 중단. 제품 사용이 불허되면 연구는 가능해도 `PRODUCT_CANDIDATE` 금지. 판단 불명은 `BLOCKED`다.
- **예산**: 로컬 manifest 작업 반나절 제안; counsel 회신 시간은 별도이며 실험자가 임의 추정하지 않는다.
- **시드 계획**: 없음. manifest와 문서 checksum으로 재현한다.

### Cell P5-01 — exact CRS/handle round-trip

- **가설**: render mask 위치를 새 geometry 없이 원본 handle로 정확히 되돌릴 수 있다.
- **지표**: inverse-mapped handle-set Jaccard, 최대 world 좌표 오차, phantom handle 수, nested INSERT identity mismatch, clipped tile duplicate/miss 수.
- **제안 합격선**: handle Jaccard=1.0, phantom=0, miss=0. 좌표는 `max(1e-6 world unit, 해당 렌더의 0.5 pixel을 world로 환산한 값)` 이내.
- **킬 조건**: affine/viewport/INSERT chain의 모호성을 manifest로 제거할 수 없거나 동일 fixture에서 비결정적 handle 결과가 한 번이라도 재현되면 역투영 설계를 폐기한다.
- **예산**: 로컬 CPU 1일 제안.
- **시드 계획**: seed 0의 고정 fixture + 세 학습 seed 번호를 재사용한 무작위 transform fixture; 모두 개별 보고.

### Cell P5-02 — 파인튜닝 전 값싼 20-definition 프로브

- **가설**: 동결 open segmenter의 mask proposal만으로도 v0 wall_pairs가 놓친 definition에서 새 gate-qualified handle을 찾을 수 있다.
- **지표**: `operational_yield@20`, v0 대비 paired lift, unmatched component 비율, CRS reject, definition당 wall-clock.
- **제안 합격선**: CL-A가 확정한 20 definitions에서 lift가 양수이고, CRS phantom=0. 이 셀은 방향성 screen일 뿐 `RESEARCH_VIABLE` 판정은 하지 않는다.
- **킬 조건**: 모든 prereg stratum에서 lift≤0이거나, 이득이 unmatched raster geometry를 벽으로 허용해야만 생기면 학습 전 `PARK`.
- **예산**: 로컬 RTX/CPU 1일 이내 제안. 새 API 호출 없음.
- **시드 계획**: checkpoint·automatic prompt grid·threshold hash를 하나로 고정한 deterministic inference. 여러 checkpoint를 보고 고르지 않는다.

### Cell P5-03 — FloorPlanCAD mask 학습

- **가설**: 사람/데이터셋 wall mask로 학습한 경량 segmenter가 frozen probe와 shuffle null을 넘어 벽 외형을 학습한다.
- **지표**: val wall IoU, Dice, pixel P/R, boundary F-score, seed 분산, label-shuffle null percentile.
- **제안 합격선**: 세 seed로 선택한 봉인 방식의 val wall IoU≥0.60이며, permutation null의 95th percentile을 초과한다. 같은 기준을 research-holdout에서도 다시 만족해야 최종 통과한다.
- **킬 조건**: bounded model/hyperparameter 공간 전체가 밴드 미달, shuffle control이 비정상적으로 높음, duplicate 제거 뒤 이득 소실, 또는 NC counsel 불허.
- **예산**: 로컬 architecture당 수일 제안; DGX가 복구되면 패킷의 1–3일 배치 계획을 별도 arm으로 사용.
- **시드 계획**: 1729/2718/3141 전부. OOM seed를 조용히 버리지 않고 실패로 기록한다.

### Cell P5-04 — CubiCasa val 역투영·조건부 이득

- **가설**: FPCAD-only raster 후보가 v0뿐 아니라 CL-B와 GBDT가 놓친 사람-labeled wall handle을 같은 벡터 게이트 아래에서 추가 회수한다.
- **지표**: candidate Recall@20, gate-qualified P/R/F1, zero-pair drawing recall, v0/CL-B/GBDT 대비 paired delta, GBDT∪raster union의 unique true positives.
- **제안 합격선**: (a) v0 대비 top-20 gate-qualified recall 절대 delta≥0.25라는 패킷 밴드, (b) CL-B 대비 paired bootstrap 하한>0, (c) GBDT∪raster가 GBDT 단독보다 gate-qualified precision을 낮추지 않으면서 recall 차이 하한>0.
- **킬 조건**: CL-B 뒤 delta가 0 이하, 이득이 Wall-class 렌더 누출에서만 발생, 또는 GBDT union에 고유 true positive가 없음.
- **예산**: 로컬 render/index/inference 1–2일 제안.
- **시드 계획**: 세 checkpoint를 모두 평가하고 사전 정의 ensemble 결과를 primary로, seed별 결과를 secondary로 기록.

### Cell P5-05 — 대리 독립성·ablation

- **가설**: raster의 이득은 합성·gate·parallel prior를 되풀이한 것이 아니라 사람 라벨 축에서 고유한 오류 보완이다.
- **지표**: 동일 definition에서 `{human, v0, CL-B, GBDT, raster, synthetic, metamorphic, silver(자격 시)}`의 pairwise disagreement, error correlation, unique-TP/FP, train-source×eval-source 행렬.
- **제안 합격선**: human-labeled val에서 raster unique-TP의 paired interval 하한>0이고, 그 이득이 gate pass를 학습 target으로 쓴 arm 없이 재현된다. silver 없는 arm이 primary다.
- **킬 조건**: raster 이득이 평행 이중선 prior와 완전히 같은 표본에만 나타남, synthetic 대각 성능만 높고 human 비대각 전이가 없음, 또는 gate 결과를 sample weight로 넣어야만 이득이 남음.
- **예산**: 기존 prediction을 재사용하는 로컬 분석 1일 제안.
- **시드 계획**: P5-03의 세 seed; shuffle-label 세 seed를 대조로 동일 집계.

### Cell P5-06 — metamorphic·sentinel 배터리

- **가설**: raster nomination을 거쳐도 inverse-mapped 최종 accepted handle 집합은 의미 보존 transform에 불변이고 퇴행 sentinel을 통과한다.
- **지표**: transform 전후 accepted-handle Jaccard, candidate-rank 변화, gate-clause 변화, 0벽 FP, 전벽 recall, scale arm 최저 일치율.
- **제안 합격선**: 강체·반사·이동·단위·scale의 의미 보존 fixture에서 inverse-mapped accepted-handle Jaccard=1.0, 0벽 sentinel FP=0, 전벽 sentinel recall=1.0. 후보 순위 변화는 허용하지만 최종 합격 집합 변화는 허용하지 않는다.
- **킬 조건**: scale FAIL을 threshold 조정으로 숨김, 0벽에서 하나라도 합격, 전벽을 빈 출력으로 통과, 또는 transform마다 gate 설정을 바꿔야 함.
- **예산**: 로컬 CPU/GPU 1일 제안.
- **시드 계획**: 고정 transform manifest를 세 checkpoint에 동일 적용.

### Cell P5-07 — 1.dwg real-axis 및 NC 제거 ablation

- **가설**: CL-A가 확정한 실도면 zero-pair 구간에서 raster가 CL-B 이후에도 새 gate-qualified 기존 핸들을 제안하며, 그 이득은 권리상 허용된 checkpoint로 재현 가능하다.
- **지표**: operational_yield@20, v0/CL-B 대비 delta, definition별 latency/peak memory, unmatched/CRS reject, NC checkpoint 제거 전후 delta.
- **제안 합격선**: v0 대비 절대 delta≥0.25, CL-B 대비 paired interval 하한>0, phantom=0. 제품 후보의 경우 허용 checkpoint도 같은 방향의 유의한 lift를 보여야 한다.
- **킬 조건**: CL-B 보강이 같은 handle을 전부 회수함, 이득이 NC checkpoint에서만 보이고 허용 checkpoint의 delta가 제안 equivalence band `[-0.05,+0.05]` 안에 머묾, 또는 모델 출력을 gate 없이 채택해야 이득이 생김.
- **예산**: 최대 412,775 선분 definition을 고려한 tile/R-tree 로컬 실행 1–2일 제안.
- **시드 계획**: 세 checkpoint의 봉인 ensemble 1회 추론; 실도면을 보고 seed를 선택하지 않는다.

실도면에는 사람 라벨이 없으므로 이 셀 합격만으로 semantic precision/recall을 주장하지 않는다. `RESEARCH_VIABLE`의 의미도 labeled 축의 P5-04/P5-08과 결합할 때만 성립한다.

### Cell P5-08 — 봉인 holdout/test 단발

- **가설**: val에서 고른 P5 방식이 FPCAD research-holdout과 CubiCasa test에 한 번의 봉인 실행으로 전이된다.
- **지표**: FPCAD wall IoU, CubiCasa per-handle P/R/F1와 Recall@20, v0/CL-B/frozen GBDT와의 paired delta, 모든 gate/reject count.
- **제안 합격선**: FPCAD wall IoU≥0.60; v0 대비 gate-qualified Recall@20 delta≥0.25; 같은 test에서 replay한 CL-B 대비 interval 하한>0; GBDT∪raster가 GBDT 단독보다 precision 비열화 없이 recall 하한>0; P5-01/P5-06 hard gate 유지.
- **킬 조건**: read-once 전에 hash가 달라짐, test를 두 번 열어 선택함, 어떤 hard gate도 실패, 또는 val lift가 test에서 재현되지 않음. test 실패 뒤 같은 test로 재튜닝하지 않고 방법을 kill/park한 뒤 새 세대로 넘긴다.
- **예산**: 체크포인트가 봉인된 뒤 로컬 단일 batch 평가 1일 제안.
- **시드 계획**: prereg된 세-checkpoint ensemble을 한 test runner invocation에서 평가. seed별 test 탐색 금지.

### Cell P5-09 — 제품 artifact 격리

- **가설**: 연구 결과와 독립적으로 product build가 NC/unknown 데이터 파생물을 완전히 거부하며, 허용 weight만으로 후보 이득을 재현할 수 있다.
- **지표**: product dependency closure의 금지 checksum 수, research import 수, reproducible build hash, 허용 checkpoint의 P5-04/P5-07 delta.
- **제안 합격선**: 금지 checksum=0, research import=0, 동일 입력 두 build hash 일치, 허용 checkpoint가 앞선 성능 조건을 만족.
- **킬/판정 조건**: NC weight·LoRA·distillation·cache 중 하나라도 제품 트리에 들어가면 제품 arm 즉시 FAIL. NC를 뺀 이득이 ≈0이면 P5는 연구 결과로만 보존하고 제품 제안은 죽인다.
- **예산**: 로컬 lineage scanner/clean-room build 1일 제안.
- **시드 계획**: 없음. byte-level artifact 검사와 두 번의 deterministic build.

### 6.2 최종 판정 논리

```text
if P5-00 or P5-01 is not PASS:
    status = BLOCKED
elif P5-02 fails or P5-03 misses IoU band:
    status = PARK
elif any of P5-04, P5-05, P5-06, P5-08 fails:
    status = KILL_COUNTER_THEORY
elif NC research arm passes but P5-09 does not:
    status = RESEARCH_VIABLE_PRODUCT_BLOCKED
elif P5-07 beats v0 but not CL-B:
    status = KILL_RASTER_MAINLINE_CLAIM
else:
    status = PRODUCT_CANDIDATE_REQUIRES_HUMAN_V2_GATE
```

어떤 상태에서도 VLM/raster mask가 곧 제품 SoT가 되지 않는다. 최종 채택은 route에 명시된 `V2_human_gate`의 Paul 승인 대상이다.

---


---

## [feyerabend_P6] — ## 6. 실험 셀 정의 (122 lines)

## 6. 실험 셀 정의

### 6.1 공통 프리레그

모든 셀에 다음 규칙을 적용한다.

- 결과를 보기 전에 config, code content hash, input content hash, selection manifest, threshold를 기록한다.
- deterministic algorithm에는 “seed 평균”을 만들지 않는다. 생성기나 순서 교란에만 seed를 쓴다.
- val은 개발·튜닝에 허용하지만 test는 방법 동결 뒤 단발이다.
- shuffle/rename 대조군과 zero-wall sentinel을 의무화한다.
- 셀 상태는 PASS, FAIL, BLOCKED, INCONCLUSIVE 네 값만 허용한다.
- 아래 반복 수와 gate는 제안값이며 아직 실행 결과가 아니다.

### 6.2 셀 P6-C0 — INSERT transform oracle

- **가설:** parser adapter의 누적 transform이 hand-authored 월드 endpoint와 일치한다.
- **입력:** identity, translation, rotation, uniform/nonuniform scale, reflection, nested depth, array cell, child/modelspace 조합을 포함한 고정 24 case.
- **지표:** endpoint max normalized error, placed_uid uniqueness, expected instance count, cycle/missing-target 검출률.
- **합격선:** 모든 정상 case의 endpoint error ≤ 1e-9 × max(1, extent), expected instance count 100% 일치, malformed case 100% fail-closed.
- **킬 조건:** 정상 transform 하나라도 틀림, cycle이 무한 전개됨, silent drop 발생.
- **예산:** 로컬 CPU 10분 이내, RAM 1 GiB 이내의 제안 budget.
- **시드:** 없음. case manifest 고정.

### 6.3 셀 P6-C1 — handle-only 누수·동치 감사

- **가설:** block/layer 이름과 외부 라벨을 바꿔도 traversal, placed_uid, pair set이 변하지 않는다.
- **입력:** C0 정상 case의 block name, layer name, entity order, truth column을 독립 shuffle한 5개 mutation seed.
- **지표:** path uid equality, placed geometry equality, pair uid equality, serialized graph field allowlist, forbidden token scan.
- **합격선:** 이름/라벨 mutation에서 세 equality 1.0, graph serialization의 forbidden field 0개.
- **킬 조건:** 이름이나 라벨이 hash, candidate selection, dedup에 사용됨; truth shuffle에 출력이 반응함.
- **예산:** 로컬 CPU 15분, RAM 1 GiB.
- **시드:** P6L-01부터 P6L-05까지 사전 기록.

### 6.4 셀 P6-C2 — split-wall 합성 판별

- **가설:** 참 wall ribbon의 양변이 scope를 가로지를 때 folded는 의도적으로 놓치고 unfolded는 회수한다.
- **입력:** 5 generator seeds × 20 case의 제안 설계. 각 seed는 cross-def, child/modelspace, nested, repeated-placement-context, same-def control, no-wall/distractor를 균형 있게 포함한다.
- **primary metric:** split family의 placed-instance pair recall.
- **보조 metric:** placed-handle precision, same-def non-regression, zero-wall false proposal rate.
- **합격선:** 패킷의 핵심 밴드인 folded recall ≤ 0.2이고 unfolded recall ≥ 0.9. 추가 안전 gate로 unfolded placed-handle precision ≥ 0.9, zero-wall sentinel proposed handle 0개, same-def control의 folded/unfolded pair set agreement 1.0.
- **킬 조건:** 검증된 transform에서도 unfolded recall < 0.9, folded recall > 0.2라서 생성기가 판별을 만들지 못함, 또는 sentinel 오탐으로 recall이 무의미해짐.
- **예산:** 로컬 CPU 1시간, RAM 4 GiB.
- **시드:** P6S-01부터 P6S-05. seed별 결과와 pooled 결과를 모두 기록하고 평균만 보고하지 않는다.
- **해석 제한:** PR-1 fidelity gate가 FAIL이면 이 셀은 구현 oracle PASS일 수는 있어도 프로그램 수준 H_world 지지로 승격하지 않는다.

### 6.5 셀 P6-C3 — 표현·변환 metamorphic battery

- **가설:** 동일한 월드 벽을 modelspace, 한 def, 두 defs, nested INSERT, explode로 표현해도 unfolded canonical geometry pair set은 같다.
- **입력:** 20개 base layout에 representation factorization, entity reorder, block/layer rename, rigid rotation/translation/reflection, unit metadata 보상 rescale을 적용한다.
- **지표:** geometry-mapped pair-set agreement, placed truth recall difference, source-projection disagreement, unsupported count.
- **합격선:** geometry-mapped pair-set agreement 1.0, placed truth recall difference 0, representation별 unsupported count 0.
- **킬 조건:** def 분할만 바꿨는데 pair가 달라짐; 이름 변경에 결과가 달라짐; unit metadata를 함께 보상한 rescale에서 결과가 달라짐.
- **예산:** 로컬 CPU 2시간, RAM 8 GiB.
- **시드:** base generator P6M-01부터 P6M-04, 각 seed 5 layout. transform 목록은 고정.
- **주의:** 좌표만 scale하고 물리 단위 metadata를 보상하지 않는 변환은 P2의 절대/상대 대역 논쟁이므로 P6 invariance gate에 넣지 않는다. 기존 scale 팔 0.7624 FAIL과 scope 효과를 혼동하지 않는다.

### 6.6 셀 P6-C4 — 1.dwg cheapest actual probe

- **가설:** CL-A 재계산 top-20 중 실제로 배치 가능한 INSERT-child def에서 unfolded가 folded에 없던 cross-scope pair를 만든다.
- **표본:** 3.1의 규칙으로 고정한 적격 10개 def. 10개 미만이면 BLOCKED.
- **지표:** def별 folded pair count, unfolded pair count, new_cross_scope_pair count, cross-placement-only count, unsupported fraction, resource counter. primary는 new_cross_scope_pair가 하나 이상인 def의 비율이다.
- **합격선:** 적격 10개 중 최소 3개, 즉 ≥30%에서 new_cross_scope_pair 생성. anonymous-name reporting cohort가 별도로 충분하면 같은 ≥30%를 기술하되 primary topology cohort를 대체하지 않는다.
- **킬 조건:** graph/unit audit가 통과했는데 10개 모두 0개; 추가분이 모두 같은 scope의 반복 복제 또는 duplicate artifact; unsupported 때문에 denominator를 사후 축소.
- **중간 판정:** 1–2개면 INCONCLUSIVE/NO-GO이며 PASS가 아니다.
- **예산:** 로컬 CPU 4시간, peak RSS 48 GiB 이내.
- **시드:** 없음. rank와 handle tie-break로 결정.
- **해석 제한:** 사람 truth가 없으므로 이는 scope relation 생성 gate다. “실제 벽 정답 회수율”로 쓰지 않는다.

### 6.7 셀 P6-C5 — 복잡도·메모리 kill test

- **가설:** exact world pairing이 제곱 후보 폭발 없이 64GB 로컬 머신에서 실용적으로 끝난다.
- **입력:** synthetic density ladder 25k, 50k, 100k, 200k, 400k placed segments와 1.dwg 최대 규모 경로. synthetic 수치는 제안 stress 크기다.
- **지표:** traversal/index/query wall time, peak RSS, N/Q/C/P, Q/N, C/N, log-log empirical slope, abort reason.
- **합격선:** 1.dwg 최대 경로가 lossy cap 없이 2시간 이하, peak RSS 48 GiB 이하, max_exact_candidates 50,000,000 미만에서 완료. density ladder의 마지막 두 점 empirical time slope ≤ 1.5를 보조 gate로 둔다.
- **킬 조건:** 실제 경로가 ceiling에 닿음, RSS/시간 gate 초과, 결과를 얻으려면 top-k/sampling이 필요함, 또는 pair materialization이 사실상 제곱으로 증가.
- **예산:** 로컬 CPU 총 8시간, 각 단계 timeout 2시간, RAM 48 GiB gate.
- **시드:** 구조 seed P6X-01부터 P6X-03. worst-case parallel dense와 typical sparse를 분리 보고.

### 6.8 셀 P6-C6 — downstream 비회귀와 평가단위 감사

- **가설:** INSERT graph가 없는 IR에서는 world mode가 identity이고, INSERT graph가 있는 경우 placed/source projection의 차이가 명시적으로 드러난다.
- **입력:** CubiCasa val의 schema audit 결과에 따른 전량 val identity check 또는 조건부 scope run; 합성 repeated-placement-context family; frozen fast_score와 frozen GBDT.
- **지표:** canonical candidate pair equality, fast_score equality, frozen model prediction equality, placed-vs-source confusion table, fit-call count.
- **합격선:** INSERT가 없는 IR에서는 세 equality 1.0과 fit-call 0. INSERT가 있으면 결과를 개발용 val diagnostic으로 보고하고 C2/C4 gate를 사후 변경하지 않는다.
- **킬 조건:** graph가 없는데 예측이 변함; source projection만으로 placement 오차가 숨겨짐; P6 실행 중 모델 재학습이 발생함.
- **예산:** val 400만 사용, 로컬 CPU 4시간, RAM 32 GiB. test 400 접근 0회.
- **시드:** deterministic. GBDT artifact 고정.

### 6.9 셀 P6-C7 — 동결 후 confirmatory one-shot

- **실행 조건:** C0–C6의 필수 gate가 모두 PASS이고 PR-1 fidelity gate가 통과하며 code/config/input family가 content hash로 동결된 뒤에만 연다.
- **입력:** 결과를 보지 않은 hidden synthetic mutation family. 별도의 insert-bearing 라벨 CAD test가 제공되면 그 데이터는 방법당 단발로 추가할 수 있으나, 현재 패킷에는 그런 자산이 명시되지 않았으므로 있다고 가정하지 않는다.
- **가설/합격선:** C2의 folded ≤ 0.2, unfolded ≥ 0.9 밴드와 precision/sentinel gate를 그대로 재사용한다.
- **킬 조건:** hidden family에서 band 실패, 재실행 요구, threshold 수정 요구.
- **예산:** 로컬 CPU 2시간, 1회.
- **시드:** prereg 때 봉인한 P6H-01 하나. 결과 확인 뒤 seed 교체 금지.
- **CubiCasa test 정책:** schema audit상 world mode가 identity면 test를 소비하지 않는다. 비동일 효과가 있고 P6 방법이 완전히 동결된 경우에만 기존 test 400을 한 번 쓴다.

### 6.10 종합 판정 함수

~~~text
if any of C0, C1 is FAIL:
    verdict = INVALID_IMPLEMENTATION
elif C2 misses its primary band:
    verdict = KILL_COUNTER_OR_GENERATOR
elif C3 is FAIL:
    verdict = KILL_IMPLEMENTATION
elif C4 is BLOCKED:
    verdict = BLOCKED_REAL_EVIDENCE
elif C4 rate == 0:
    verdict = KILLS_COUNTER_FOR_CURRENT_E2_CORPUS
elif C4 rate < 0.30:
    verdict = INCONCLUSIVE_NO_GO
elif C5 is FAIL:
    verdict = KILL_PRACTICALITY
elif required evidence xlsx is missing:
    verdict = PROTOCOL_FAIL
else:
    verdict = SUPPORTS_WORLD_SCOPE_AND_KILLS_DEF_QUOTIENT
~~~

C6는 회귀·평가단위 안전 gate다. C7은 confirmatory gate다. 어떤 상태에서도 새 pair count만으로 semantic wall-system PASS를 선언하지 않는다.


---

## [feyerabend_P7] — ## 6. 실험 셀 정의 (85 lines)

## 6. 실험 셀 정의

실행 순서는 패킷의 좌석 큐를 따른다. P1+P6, P2, P3의 더 싼 판별이 먼저이며 P7은 네 번째다. P7 안에서는 E0→E5 순서로 진행하고, 앞 셀의 kill을 통과하지 못하면 뒤 셀 예산을 쓰지 않는다.

### E0 — 게이트·누수·missingness 계약 셀

- **가설:** P7은 후보 집합을 만들거나 geometry gate를 바꾸지 않으며, 관례가 전부 누락되면 geometry-only와 완전히 같다.
- **데이터:** 소형 합성 smoke set, CubiCasa val의 사전등록 subset, 1.dwg fit subset. 라벨은 assertion에 필요하지 않다.
- **비교:** `G`, `G+R0`, `G+R0+U`의 candidate/gate mask; all-missing arm.
- **지표:** `pred & ~G` 수, candidate universe hash 동일성, all-missing score/pred hash 동일성, eval lookup 시 prior artifact hash 변화 수, label-column 접근 수.
- **합격선:** 모든 위반 수 0, 요구되는 해시 완전 동일.
- **킬 조건:** 단 한 건의 gate 우회, 평가 도면으로 vocabulary/map 갱신, Wall label feature 접근, missing arm 차이.
- **예산:** 로컬 CPU 약 1시간 이내의 계획값.
- **시드:** 결정론 셀이므로 1개; 순서 무작위화만 별도 고정 시드 1개.

### E1 — cheapest 정규식 prior: 정렬/오정렬 합성 2×2

- **가설:** 정렬 합성에서는 `G+R0`가 `G`보다 per-handle F1을 0.15 이상 높이지만, 관례 bundle만 셔플한 오정렬 합성에서는 MI 신뢰도 게이트가 `R0`를 기권시켜 F1과 예측이 변하지 않는다.
- **데이터:** 동일 geometry·label의 aligned/misaligned paired synthetic. 현재 fidelity FAIL 팩은 코드 단위시험용이며, 판결용 hidden family는 PR-1/CL-C 통과 후 동결한다.
- **비교:** `G` 대 `G+R0`. gate와 `τout`은 고정한다.
- **주 지표:** paired per-handle F1 차이. 보조로 precision, recall, gate coverage, direct-token coverage, 예측 hash, 프로젝트별 분산을 기록한다.
- **제안 합격선:** aligned hidden에서 `ΔF1≥+0.15`; misaligned hidden에서 prior weight 0, `ΔF1=0`, 예측 hash 동일. aligned의 개선이 gate-pass universe 안에서만 발생해야 한다.
- **킬 조건:** aligned 개선이 0.15 미만, misaligned에서 예측 변화, direct regex가 gate를 우회, 또는 geometry hash가 쌍 사이에서 다름.
- **예산:** 로컬 CPU 수 시간의 계획값.
- **시드:** 생성 시드 10개를 사전등록하고 paired 분석. 개발 시드는 val에만, hidden mutation family는 한 번만 연다.

E1의 `+0.15`는 패킷이 준 신호 존재 밴드다. 이를 달성해도 실제 프로젝트 일반화가 입증된 것은 아니다.

### E2 — 프로젝트 내부 상호정보와 간접 관례의 증분 셀

- **가설:** 직접 토큰을 제거한 layer/block/text/linetype 관례에도 기하 앵커와 순열 귀무를 넘는 프로젝트 내부 MI가 있고, `G+R0+U`가 `G+R0`보다 추가 이득을 낸다.
- **데이터:** E1 합성의 다국어·stolen-layer 변형과, 라벨을 보지 않는 1.dwg fit folds. 합성에는 truth metric, 1.dwg에는 stability metric만 쓴다.
- **비교:** `G`, `G+R0`, `G+R0+EB`, `G+R0+hashed-char`. 마지막 arm은 EB가 살아남은 뒤에만 연다.
- **주 지표:** 합성 per-handle ΔF1, direct 제거 후 ΔF1, `I_obs` 대 drawing-cluster permutation null, fold 간 score rank correlation, OOV율, block-copy effective sample size.
- **제안 합격선:** 합성 hidden에서 indirect-only 증분이 양수이고 모든 사전등록 seed 방향이 일치하며, MI가 순열 게이트를 통과한다. 정확한 최소 증분은 E1 결과를 보기 전에 별도 prereg에 봉인한다.
- **킬 조건:** 이득이 direct token에만 전부 귀속, 순열 귀무를 넘지 못함, 한 대형 block 복제 제거 후 신호 소멸, 또는 오정렬 arm에서 MI 채널이 기권하지 않음.
- **예산:** EB/MI는 로컬 CPU 수 시간, 문자 모델은 통과 시 추가 수 시간의 계획값.
- **시드:** E1과 같은 10개 paired seed; 순열 seed 목록을 별도 봉인. seed 평균만 보고하지 않고 전부 공개한다.

### E3 — 기하 불변 관례 metamorphic·sentinel 셀

- **가설:** geometry를 고정하고 layer assignment를 깨면 aligned 합성의 P7 성능은 예상 방향으로 하락하지만 geometry gate 자체는 완전히 불변이다. misaligned 합성, all-missing, 0-wall sentinel에서는 prior가 기권한다.
- **변형:** (a) layer bundle의 handle 간 셔플, (b) block path 셔플, (c) TEXT/MTEXT 셔플, (d) linetype 셔플, (e) opaque bijective rename, (f) 모든 convention 삭제. 각 변형은 geometry bytes를 건드리지 않는다.
- **지표:** `Δshuffle=F1(original)-F1(shuffled)`, gate mask hash, candidate hash, 채널별 prediction flip, 0-wall false positive, all-wall recall, direct/indirect 의존량.
- **제안 합격선:** 모든 변형에서 gate/candidate hash 동일; aligned에서 assignment-breaking shuffle의 `Δshuffle>0`; misaligned와 all-missing에서 prediction hash가 geometry-only와 동일. 0-wall sentinel에 prior발 false positive 0. all-wall sentinel의 recall은 geometry-only보다 낮아지지 않아야 한다.
- **킬 조건:** geometry 변화, 0-wall 탐지기로 퇴행, 이름 삭제가 gate를 약화, 또는 aligned와 misaligned의 의존량이 구분되지 않음.
- **예산:** 로컬 CPU 약 반나절의 계획값.
- **시드:** 각 변형×합성 seed 10개, paired. sentinel은 결정론.

opaque bijective rename과 assignment shuffle은 의미가 다르다. 전자는 철자 사전 의존성을, 후자는 엔티티-관례 결합 의존성을 측정한다. 둘을 “layer rename invariance” 하나로 합쳐 평균내지 않는다.

### E4 — 1.dwg fit/freeze 분석 셀

- **가설:** 평가 도면을 보지 않고 적합한 프로젝트 prior가 gate-pass 후보 중 geometry-only와 다른 안정된 top-20 순서를 만들며, 특히 이전 zero-pair 또는 silver-high 구간에서 분석 가치가 있다.
- **데이터:** 1.dwg의 384개 도면정의를 project/definition manifest에 따라 fit와 analysis로 그룹 분할. 사람 라벨 없음.
- **비교:** `G` 대 `G+R0` 대 `G+R0+U`; silver는 약 2개 어휘 가문으로만 병렬 분석.
- **지표:** top-20 rank change, 새 top-20 진입 수, direct/indirect 기여, OOV, MI/null, gate 위반, drawing-level zero-hit 변화, 두 silver 가문과의 disagreement matrix.
- **제안 합격선:** 정확도 합격선은 두지 않는다. infrastructure 합격은 gate 위반 0, eval 학습 0, prior artifact 불변, fold 방향 안정성이다. 사람이 없는 후보 회복 수나 silver 일치는 GO 근거가 아니다.
- **킬 조건:** gate 우회 압력이 생김, fit/analysis 경계 누수, 순위 변화가 direct token 한 종류나 단일 block 복제에 집중, 또는 2가문 silver를 5독립표처럼 세야만 좋아 보임.
- **예산:** 최대 도면정의의 412,775 선분을 streaming 처리하는 로컬 CPU 수 시간의 계획값.
- **시드:** split seed 5개로 안정성만 보되, 최종 project split은 한 개를 사전봉인한다. 성능 선택에는 쓰지 않는다.

### E5 — 프로젝트 간 freeze 전이와 단발 test 판결 셀

- **가설:** source 프로젝트의 lexicon·MI map·가중치를 완전히 동결하고 새 target 프로젝트에 적용해도 `G+P7`의 per-handle F1이 같은 `G`보다 높다.
- **선결:** 최소 두 개 이상의 독립 project/firm ID와 합법적으로 사용할 수 있는 사람 per-handle 라벨, PR-3 counsel, PR-1 fidelity, E0–E3 통과. 현재 패킷 자산만으로 실도면 labeled 전이 판결을 완료할 수 있다고 가정하지 않는다.
- **설계:** leave-one-project-out val로 방법과 하이퍼파라미터를 고른다. target에는 source prior lookup만 하며 현지 비지도 적합도 금지한다. 마지막 target test는 동결 후 한 번만 연다.
- **비교:** 동결 geometry-only(`fast_score` 또는 GBDT) 대 동일 geometry+동결 P7. source별, target별, direct 제거 arm을 모두 paired 평가한다.
- **지표:** 주 지표 per-handle ΔF1. precision/recall, 프로젝트별 ΔF1, OOV, calibration, gate coverage를 보조 보고한다. micro 평균과 project-macro를 함께 쓰고 firm별 결과를 숨기지 않는다.
- **제안 합격선:** 패킷 계약대로 프로젝트 전이 주 지표의 이득이 양수여야 한다. `ΔF1≤0`이면 convention 채널을 PARK한다. 합성 aligned의 0.15 밴드와 전이 양수 조건을 모두 만족해야 P7 전체가 산다.
- **킬 조건:** 전이 ΔF1≤0, 어느 target에서든 gate 우회, 이득이 평가 프로젝트 사전 재적합에 의존, direct 정답 토큰을 제거하면 전부 붕괴하면서 broader convention 모델로 포장, 또는 precision 손실을 감춘 micro 평균만 양수.
- **예산:** 희소 prior 자체는 로컬 CPU 수 시간/프로젝트의 계획값. 라벨 조달·권리 확인은 별도 외부 선결이며 DGX는 불필요하다.
- **시드:** 학습/val seed 5개를 사전등록하고 평균·최악을 모두 공개. test는 선택된 단일 artifact로 단발 실행하며 seed 재시도를 금지한다.

### 6.1 셀 판정표

| 결과 | 판정 |
|---|---|
| E1 aligned `+0.15` 이상, misaligned 불변, E5 전이 양수 | `kills: reigning` 후보. 기하-only 충분성 주장을 기각할 증거가 생김 |
| E1 무이득 또는 E5 전이 0 이하 | `kills: counter`; P7 convention 채널 PARK |
| E1 성공, E5 자료/권리 부재 | 메커니즘만 살아 있음. 제품 채택 보류 |
| E1 성공, direct token만 성공 | broader P7은 죽고 고정 regex 보조 규칙만 별도 후보 |
| 어떤 셀에서든 gate 우회 | 성능과 무관하게 P7 즉시 kill |

---


---

## [platt_P0] — ## 6. 실험 셀 정의 (74 lines)

## 6. 실험 셀 정의

이 방법은 학습 셀이 아니라 계측 감사 셀이다. 개발은 synthetic micro-fixture에서만 하고, 실제 E1/IR은 prereg 동결 후 한 번 읽는다. 전체 로컬 실행 예산은 패킷대로 CPU 1시간 미만, GPU/LLM 0이다. 개별 셀 예산은 이 총량 안의 몫이며 독립적으로 합산해 새 예산을 만들지 않는다.

### C0 — 선택 lineage와 재현성 게이트

- **가설:** 저장된 E1 top-20이 exact `_score_divergence`의 안정 정렬 top-20과 일치하며, 이름/엔티티 수/원시 행 순서가 숨은 선택 키가 아니다.
- **지표:** legacy-vs-recomputed set/order, tie block, nonfinite/parse error, input/prereg/code hash, 2회 semantic hash.
- **제안 합격선:** top-20 집합 exact 일치, divergence 값 재현, 두 실행 decision/semantic hash exact 일치. 이는 확률 밴드가 아니라 결정론 계약이다.
- **킬 조건:** exact divergence를 재현할 수 없거나 cohort가 달라지면 legacy top-20 기반 확인적 해석을 kill한다. 새 cohort 감사는 가능하지만 prereg version과 별도 결과로 분리한다.
- **예산:** streaming sort와 hash; 총 CPU 예산의 작은 부분, GPU/LLM 0.
- **시드:** top-20에는 시드 없음. 대조군 seed 문자열은 `platt_P0/control/20260718/v1`로 고정.

### C1 — 핸들 실재·타입·소유권 감사(주 판별 셀)

- **가설:** H0-M 대 H1-C.
- **지표:** unique citation 기준 `r_bad`, occurrence 민감도, direct/nested/other/absent/ambiguous 분포, 타입별 분포, `r_pair`.
- **제안 합격선:** O-A는 `r_bad >= 0.50`; O-B는 `r_bad <= 0.10 AND r_pair > 0.50`; 그 외 O-MIXED. 패킷 밴드를 사후 변경하지 않는다.
- **킬 조건:** O-B면 H0-M kill. O-A면 “불일치는 실재하며 탐지기 개념 결함”이라는 E1 기반 전제를 kill하고 crosscheck v0를 `RETRACT_CANDIDATE`로 보낸다. join/분모가 불완전하면 양쪽 모두 kill하지 않고 O-BLOCKED.
- **예산:** 40개 정의의 handle index lookup 및 indexed pairability; 총 CPU 1시간 미만 안, GPU/LLM 0.
- **시드:** top-20 없음; 대조 20은 C0 고정 seed. 모든 tie는 stable key.

### C2 — 엔티티 표현·INSERT 구조 설명 셀

- **가설:** E1 극단의 불일치는 LINE-only 관측이 놓친 비-LINE 또는 nested geometry 농축으로 설명될 수 있다.
- **지표:** direct/expanded 타입 hist, max acyclic depth, direct/expanded/unique 내부 기하량, cycle, instance-path ambiguity, top-vs-control 차이.
- **제안 합격선:** 선택된 모든 정의가 완전 histogram 또는 명시적 lower-bound/error 상태를 가져야 한다. 메커니즘은 단일 사전 밴드로 억지 이분화하지 않고 C1 실패 유형을 설명할 때만 채택한다.
- **킬 조건:** top-20이 direct LINE 중심이고 nested/non-LINE 농축이 대조보다 설명력을 갖지 못하면 “표현 타입/중첩이 주원인” 설명을 kill한다. cycle/누락 참조가 결과 범위를 가리면 해당 메커니즘 판정은 blocked다.
- **예산:** definition graph 선형 순회와 instance-expanded count; multiplicity 폭발 시 symbolic count 사용, GPU 0.
- **시드:** 없음. traversal order는 `def_id`/INSERT entity stable key.

### C3 — bbox·단위 보조가정 셀

- **가설:** 기존 50–400 mm gap band가 Graph IR 좌표와 같은 단위라는 보조가정이 top-20에서 유지된다.
- **지표:** raw/converted bbox width-height-diagonal, explicit unit factor, INSERT scale singular values, `p_lower/p_upper` 단위 위반 구간.
- **제안 합격선:** `p_upper < 0.30`이면 패킷 밴드상 단위 위반 증거 부족. `p_lower >= 0.30`이면 위반 플래그. 사이 구간은 inconclusive.
- **킬 조건:** 하한이 30% 이상이면 mm 보조가정을 kill하고 P1의 상대/정박 단위 arm에 주입한다. metadata가 없어 bbox 크기만 있는 경우에는 가설을 살리지도 죽이지도 않는다.
- **예산:** bbox union과 metadata lookup, GPU/LLM 0.
- **시드:** 없음.

### C4 — 블록명 토큰 ↔ `wall_likelihood` 셀

- **가설:** H3 — `평면도` 토큰이 있는 정의에서 LLM wall likelihood의 순위/위치가 달라진다.
- **지표:** token prevalence, median difference, rank-biserial effect, Spearman 계열 연관, fixed permutation p, 전체 join 우주와 선택 cohort의 차이.
- **제안 합격선:** 1차 토큰은 방향이 일치하고 제안 α=0.05를 통과해야 이름-prior 방향 증거로 표시한다. 효과 크기와 원시 분포를 반드시 함께 보고한다.
- **킬 조건:** join 가능한 전체 우주에서 효과 방향이 없거나 permutation 기준을 통과하지 못하면 `평면도` 1차 H3를 kill한다. 이는 다른 미등록 토큰을 자동 승인하지 않는다.
- **예산:** scalar/vector 연산; CPU 예산 내, GPU/LLM 0.
- **시드:** 정의 ID hash 기반 permutation seed를 prereg에 고정. 추가 토큰은 Holm 계열 보정 또는 탐색 표시.

### C5 — `n_h_ornith=10` 원시 계보 셀

- **가설:** 정확히 열 개인 클러스터가 도면 내용보다 prompt/schema/parser/transport 제약에 의해 만들어졌다.
- **지표:** prompt cap, raw occurrence/unique count, parser 전후 차이, 목록 종료, truncation, instrumentation family, unknown interval.
- **제안 합격선:** exact-ten cluster에서 직접 입증된 `INSTRUCTION_BOUND ∪ PARSER_CAP ∪ TRANSPORT_TRUNCATION` 하한이 제안 50% 이상이면 나열 아티팩트 지배로 판정.
- **킬 조건:** raw와 prompt가 완전하고 직접 아티팩트 비율 상한도 50% 미만이면 “열 개 클러스터는 주로 나열 지시 산물” 가설을 kill한다. raw/prompt가 없으면 blocked이며 후처리 수만으로 통과시키지 않는다.
- **예산:** 기존 JSONL 원문 parse만, 신규 LLM 호출 0.
- **시드:** 없음.

### C6 — 통합 결정·재계측 라우팅 셀

- **가설:** C0–C5를 평균내지 않고도 선결 질문의 다음 행동을 단일 decision lattice로 정할 수 있다.
- **지표:** gate completeness, C1 O outcome, C3 unit flag, C4/C5 보조 설명, control contrast.
- **제안 합격선:** 정확히 하나의 terminal outcome과 근거 row link가 있고, unknown이 분모에서 빠지지 않으며, evidence xlsx가 존재한다.
- **킬 조건:** C0 또는 C1이 blocked면 통합 PASS/FAIL을 kill한다. O-A면 E1 서사 재계측으로, O-B면 CL-B 계열 커버리지 실험으로, O-MIXED면 계약 기반 재계측 1회로만 라우팅한다.
- **예산:** 규칙 평가와 workbook 생성, GPU/LLM 0.
- **시드:** 없음; C0–C5의 동결된 결과만 소비.

### val 개발 / test 단발 원칙의 적용

- **개발/val 역할:** synthetic micro-fixture와 작은 brute-force equivalence fixture만 사용한다. 실제 wall label이나 E1 outcome은 튜닝에 쓰지 않는다.
- **실제 감사 단발:** prereg hash 후 real top-20+control20을 한 번 실행한다. schema mismatch로 중단된 run은 결과를 보지 않았다는 log가 있을 때만 prereg 수정 후 재시도한다.
- **CubiCasa test:** 전혀 접촉하지 않는다. P0는 모델 비교 방법이 아니므로 test budget을 소비하지 않는다.
- **셔플 대조:** 학습 leakage shuffle 대신 C4의 token permutation과 고정 무작위 control cohort가 해당 역할을 한다. 기존 CubiCasa 셔플 AUC 0.375 PASS는 패킷의 별도 실측이며 P0가 재실행했다고 주장하지 않는다.
- **증거 xlsx:** 실제 P0 실행의 완료 조건이다. 실패도 사유와 함께 기록한다.


---

## [platt_P1] — ## 6. 실험 셀 정의 (79 lines)

## 6. 실험 셀 정의

### 6.1 공통 seed와 봉인 규칙

다음 seed는 실행을 위한 제안값이며 측정치가 아니다.

- synthetic train root: 1103, 2207, 3301
- synthetic validation root: 4409, 5519
- hidden mutation/test root: 6637, 7741
- shuffle/permutation root: 8803, 9901

generator version, seed list, parameter distribution, mutation-family split, detector config space를 하나의 prereg manifest로 hash한다. deterministic detector 자체에는 seed가 없고 stable tie-break를 쓴다. 각 stochastic generator seed를 독립 복제로 보고 seed별 metric과 pooled metric을 모두 낸다.

### 6.2 셀 표

| 셀 | 가설 | 주요 지표 | 제안 합격선 | 킬/중단 조건 | 예산·시드 |
|---|---|---|---|---|---|
| G0 baseline/evaluator 봉인 | D_cur와 evaluator가 재현 가능하다 | prediction hash, val metric 재현, ID join 감사 | 반복 hash 동일, 기존 공개 metric과 반올림 허용범위 내 일치 | 불일치면 모든 비교 BLOCKED | 로컬 CPU 0.5일, detector seed 없음 |
| G1 normalization oracle | 지원 엔티티와 transform이 기하를 보존한다 | family별 Hausdorff/parameter 오차, 누락률, metamorphic equality | 모든 의무 family가 tolerance 내 PASS, silent drop 0 | mirror/비등방/nested 중 하나라도 systematic fail이면 detector 평가 중단 | 로컬 CPU 1일, 모든 synthetic seed |
| G2 wall generator fidelity | generator가 negative와 divergent 표현을 포함하며 truth가 correct-by-construction이다 | entity/transform/mutation coverage, negative prevalence, KS/TV gate, sentinel | 사전 봉인한 fidelity gate와 모든 sentinel PASS | 벽 코드 부재, negative 0, truth round-trip fail이면 PR-1 미완 | 로컬 CPU 1~2일, train/val roots |
| E0 divergent-20 cheapest probe | zero-pair의 일부는 representation coverage 때문이다 | definition별 n_pairs 0→양수 전환 수, 단계별 provenance, unit status | 하나 이상 설명 가능한 전환이면 full experiment GO; 정확도 PASS로는 세지 않음 | 전환 0이면 P1 vertical slice STOP 및 원인 감사 | 로컬 CPU 1일, seed 없음 |
| E1 synthetic confirmatory | 완전 정규화 후 geometry가 wall pair를 찾는다 | held-out pair P/R, wall_member F1, family slices | pair R≥0.9 및 P≥0.8 | 완전 정규화 후 pair R<0.7이면 H1 kill | 로컬 CPU 1일, val/hidden roots; train tuning 금지 |
| E2 junction ablation | graph가 isolated distractor를 줄이고 진짜 network를 보존한다 | D_p1_norm 대비 ΔP, ΔR, ΔF1, single-wall recall, distractor별 FP | ΔP>0, ΔF1>0, ΔR≥−0.05의 제안 band | precision 이득 없음 또는 recall 붕괴면 graph arm kill | 로컬 CPU 1일, val roots |
| E3 CubiCasa val transfer | topology가 SEG-IR 외부축의 긴 평행 distractor를 구별한다 | micro/macro P/R/F1, five FP family, runtime | D_p1_graph−D_cur F1≥+0.2 및 F1≥0.4; 기존 val 기준 목표 0.4358 이상 | 최종 F1<0.4면 H1-G/X kill | 로컬 CPU 1~2일, 고정 split, detector seed 없음 |
| E4 absolute-vs-relative unit | absolute mm artifact보다 dimension/robust-gap anchor가 scale 전이에 강하다 | scale slice F1, metamorphic scale equality, unit unresolved rate | relative arm이 scale equality strict PASS하고 외부 F1 비열등 | 둘 다 scale strict FAIL이면 unit normalizer 재설계; 성능 숫자로 bbox 규칙 retune 금지 | 로컬 CPU 1일 |
| E5 FloorPlanCAD external | 정합된 외부 vector truth에서도 전이한다 | wall-line F1, v1−v0, registration error | vector 정합 전 BLOCKED; 조달 후 ΔF1≥+0.2 및 F1≥0.4 | F1<0.4면 H1 kill; raster-only면 결론 금지 | counsel/asset 의존, 로컬 CPU; drawing split |
| E6 real-CAD scale/resource | 1.dwg/145에서 설명 가능한 coverage 회수와 bounded execution이 가능하다 | zero-pair율, unsupported율, cap fail, wall time/RSS, determinism hash | silent truncation 0, 반복 hash 동일, cap 실패 전부 보고 | O(n²) 폭발·무기록 drop이면 implementation FAIL | 로컬 CPU 1~2일, seed 없음; 145 tuning 금지 |
| E7 proxy/metamorphic independence | 여러 proxy의 합의가 같은 prior의 복제가 아니다 | 동일-def 3원 contingency, disagreement strata, rigid/scale/unit/explode equality, sentinels | lossless relation exact membership 동치, scale strict PASS, sentinel PASS | 0-wall detector가 통과하거나 proxy가 사실상 동일하면 합의 증거 demote | 로컬 CPU 1일, permutation roots |
| E8 one-shot external test | 봉인된 P1이 unopened test에 전이한다 | CubiCasa test P/R/F1와 CI, per-drawing macro, failures | test 전 봉인한 E3 band 동일 적용 | band 미달이면 H1 kill; test 재튜닝 금지 | 로컬 CPU 1회, test 400, seed 없음 |

### 6.3 셀별 실행·판정 세부

#### G0 — baseline과 evaluator

D_cur의 module/config/input/evaluator hash를 기록한다. val 0.2358이 재현되지 않으면 이름 충돌, converter drift, threshold drift, evaluator drift 중 하나이므로 비교를 시작하지 않는다. 이 셀은 새 성능을 주장하기 위한 것이 아니라 기준선을 고정하는 셀이다. git hash는 사용하지 않고 파일 SHA-256 manifest로 봉인한다.

#### G1 — normalization oracle

detector를 전혀 실행하지 않고 canonical geometry만 검사한다. 특히 nested INSERT의 transform 순서, mirror determinant, nonuniform ARC→ellipse, MLINE style, LWPOLYLINE bulge를 독립 fixture로 테스트한다. 여기서 실패한 family는 synthetic recall 저하와 혼동될 수 있으므로 E1로 넘기지 않는다.

#### G2 — generator fidelity

train distribution을 먼저 동결하고 validation/hidden family를 생성한다. 기존 B1 FAIL 수치 KS 0.5792, TV 0.265를 단순히 더 좋은 숫자로 만들기 위해 145를 모사하지 않는다. 제안 gate는 주요 scalar feature별 KS≤0.2, categorical entity-family TV≤0.1, 공개된 필수 family coverage 100%다. 이 숫자는 실측이 아닌 prereg 제안이며, 패널 승인 전에 봉인한다. divergent-20은 분포 fitting source가 아니라 blind gate로만 사용한다.

#### E0 — cheapest probe

20개 정의 각각에 folded/unfolded를 실행한다. 전환마다 “어떤 원본 handle이 어떤 instance_path와 unit decision을 거쳐 어떤 pair가 되었는지”를 사람이 재현할 수 있어야 한다. n_pairs가 늘어도 dimension/grid/furniture 가능성이 있으므로 semantic precision을 부여하지 않는다. 0→양수 전환이 0이면 full 145 run보다 먼저 transform/unit coverage 가정을 재검토한다.

#### E1/E2 — 합성과 graph

E1은 원 제안 band인 pair recall 0.9와 precision 0.8을 그대로 쓴다. recall 0.7 미만은 H1 kill이다. E2는 같은 prediction에서 graph 전후를 비교하므로 paired comparison이다. single-wall, network-wall, grid, dimension, furniture slice를 따로 내야 평균이 단독벽 삭제를 숨기지 않는다.

#### E3 — CubiCasa val

네 arm을 같은 val에서 한 번에 비교한다: D_cur, D_p1_norm, D_p1_graph, D_p1_graph_relative. D_hgb_ref는 별도 참조 열이다. 현재 geometry detector는 거의 전부를 positive로 잡아 P가 기저율 0.118에 가까운 0.134이고 R은 0.981이다. 그러므로 주 성공지표는 recall을 더 올리는 것이 아니라 FP family별 precision 회복이다. graph가 grid/BoundaryPolygon까지 network로 오인하면 H1-G가 직접 반증된다.

val에서 config를 고친 경우 반드시 새 config hash를 만들고, 이전 결과와 선택 과정을 evidence.xlsx에 남긴다. synthetic-frozen arm과 CubiCasa-val-adapted arm을 분리해 외부 라벨 tuning 효과를 드러낸다. test에는 사전에 지정한 하나만 보낸다.

#### E4 — 단위

absolute 50~400mm arm, P0 dimension anchor arm, bbox-inferred arm, relative-gap arm을 분리한다. 현재 scale 팔 0.7624 FAIL을 strict 동치로 고치는 것이 correctness 목표다. CubiCasa는 px 좌표이고 2~15mm/px 범위에서 기존 성적이 무감했으므로 physical band를 억지 적용하지 않는다. bbox arm이 scale을 잘못 고른 정의는 per-def 근거와 함께 UNRESOLVED로 돌리는 것이 거짓 정규화보다 낫다.

#### E5 — FloorPlanCAD

등록된 vector source가 조달되면 도면 단위 split, raster-vector transform oracle, dual label parser 합치 검사를 먼저 통과한다. bbox와 segmask를 line label로 환원할 때의 boundary thickness/skeleton 선택이 결과를 바꿀 수 있으므로, 그 선택은 evaluator 일부로 hash한다. vector source가 없으면 E5는 BLOCKED이고 raster exploratory 숫자로 원 prereg를 판정하지 않는다.

#### E6 — 실제 CAD와 자원

최대 412,775 선분 정의를 포함해 wall time, peak RSS, 후보 수, tile 수, cap 상태를 definition별 기록한다. resource fail 정의를 성능 denominator에서 몰래 빼지 않는다. 145 archive에서는 오직 inference하고, 관측된 failure family를 다음 버전 backlog로 복사할 수는 있지만 현재 결과를 다시 돌려 PASS로 바꾸지 않는다.

#### E7 — proxy 독립성과 metamorphic

동일 def에서 deterministic P1, 외부 truth, synthetic/metamorphic 판정, 가능한 경우 silver의 wall 여부를 contingency table로 만든다. silver 다섯 모델은 두 어휘 가문 정도로 묶어 family vote를 별도 표시한다. 일치율 하나로 독립성을 주장하지 않고, “모두 평행쌍에 동의하고 같은 Door/DimensionMark에서 틀리는가”를 disagreement stratum으로 본다.

0-wall과 all-wall sentinel을 포함해 예측량 보존까지 확인한다. rigid/reflection/explode/unit rewrite는 source correspondence가 유지되는 한 wall_member가 exact 동치여야 한다. scale arm도 unit normalization 뒤 strict PASS가 목표다.

#### E8 — test 단발

G0~G2, E1~E4, E7이 PASS하고 config/evaluator/container/input manifest를 봉인한 뒤만 test 400을 연다. 실행이 끝날 때까지 aggregate metric을 표시하지 않는 blind runner를 사용한다. test 결과가 band 미달이면 실패 이유와 함께 기록하고 재튜닝하지 않는다. H1이 죽으면 같은 test를 H2용 개발셋처럼 재사용하지 않는다.


---

## [platt_P2] — ## 6. 실험 셀 정의 (127 lines)

## 6. 실험 셀 정의

### 6.1 공통 실행 규칙

- split unit: floorplan, drawing, def, generator family
- primary metric: per-handle micro F1
- uncertainty unit: drawing/def cluster
- 개발: val만 사용
- test: 방법당 단발
- seed: 고전 ML은 {20260718, 20260719, 20260720}, GNN도 같은 세 seed
- promotion: 적격이며 proxy-family가 다른 최소 2 source에서 방향 concordance
- 모든 합격선은 해당 cell 실행 전에 prereg_p2.json에 hash로 봉인

### 6.2 셀 목록

#### P2-G0 — 선결 게이트와 P1 동결

- **가설**: P2가 비교할 P1과 truth source가 재현 가능하고 법적·방법론적으로 적격이다.
- **입력**: CL-B P1, CL-C synthetic status, counsel memo, prereg_e15.json.
- **지표**: P1 version/hash, source eligibility, split collision count, silver B1/B4.
- **합격선**: split collision 0; P1 baseline evidence 완전; external counsel clear; 사용하는 source의 gate 모두 PASS. silver는 B1 ≥ 0.70 및 B4 ≥ 0.70.
- **킬/정지**: 하나라도 실패한 source는 비활성. P1이 동결되지 않으면 전체 P2 primary 실험 정지.
- **예산**: 로컬 CPU 0.5일, GPU 0.
- **시드**: 결정적, seed 없음.

#### P2-G1 — Graph IR adjacency 완전성

- **가설**: 느슨한 candidate graph가 exhaustive reference의 의미 있는 relation을 거의 모두 보존하고 이름에 독립적이다.
- **입력**: 작은 def audit set, divergent/messy 사례, sentinel.
- **지표**: candidate-relation recall, cap truncation, graph hash determinism, transform/name-rename parity, edge/node ratio.
- **제안 합격선**: exhaustive positive relation recall ≥ 0.995; audit case cap truncation 0; 반복 build hash 일치 1.0; name-masked graph rename parity 1.0.
- **킬/정지**: recall 또는 transform parity 실패 시 학습 금지. edge 수가 예산 상한을 넘으면 adjacency rule을 고친 뒤 새 version으로 재감사하며 model tuning으로 우회하지 않음.
- **예산**: CPU 1일, RAM 64GB 내, GPU 0.
- **시드**: 결정적.

#### P2-C1 — 최저비용 고전 ML 사다리

- **가설**: 고정 graph-stat 피처만으로 P1 대비 필요한 lift를 얻을 수 있다.
- **모델**: logistic, HistGradientBoosting.
- **지표**: Δ_main 대 frozen P1, F1/P/R/PR-AUC, train/inference 시간, shuffle control.
- **합격선**: 패킷 밴드와 동일하게 Δ_main ≥ +0.10이면 고전 ML이 H2 관련 정보의 저비용 해법을 이미 포착한 것.
- **킬/정지**: HistGradientBoosting이 support band를 충족하면 production ladder에서 GNN을 중단한다. logistic이 충족하면 tree도 생략 가능하다. shuffle ROC-AUC > 0.55면 해당 pipeline은 누수 의심으로 무효.
- **예산**: CPU 1일, GPU 0.
- **시드**: 세 seed; deterministic 설정이면 동일 결과 여부를 증거로 기록.

#### P2-C2 — GraphSAGE 주효과

- **가설**: 고정 aggregate로 충분하지 않은 다중-hop 관계가 P1 대비 F1을 높인다.
- **모델**: name-masked edge-conditioned GraphSAGE.
- **지표**: Δ_main, seed 분산, per-drawing F1, PR-AUC, recall/precision, runtime.
- **합격선**: Δ_main ≥ +0.10은 H2 지지 후보; 0 ≤ Δ_main < +0.10은 demote; Δ_main < 0은 현 계측기 아래 H2 kill.
- **킬 조건**: 패킷 밴드 그대로. GPU 18시간 기본 예산을 넘거나 seed 방향이 불일치하면 승격하지 않고 불안정으로 기록.
- **예산**: RTX 5070 Ti 최대 18 GPU-hours, CPU shard 준비 별도.
- **시드**: 고정 세 seed, test는 세 seed logit 평균.

#### P2-C3 — 문맥 귀속 ablation

- **가설**: C2의 lift는 node encoder가 아니라 실제 relation topology에서 온다.
- **arm**: FullEdge, NoMessage, degree-preserving EdgeShuffle. node feature와 parameter budget은 동일하게 유지.
- **지표**: Δ_context, FullEdge−EdgeShuffle, drawing/def bootstrap interval.
- **합격선**: Δ_context의 95% cluster-bootstrap interval 하한 > 0이며 FullEdge가 EdgeShuffle보다 높아야 함. 동시에 C2의 Δ_main band를 충족해야 함.
- **킬 조건**: Δ_main은 좋아도 Δ_context 하한 ≤ 0이면 “GNN 문맥” 주장을 kill한다. 이 경우 feature encoder 효과로 재분류하며 classical/MLP 사다리로 돌린다.
- **예산**: C2 checkpoint 재사용 포함 최대 12 GPU-hours.
- **시드**: 고정 세 seed, 같은 minibatch order manifest.

#### P2-C4 — 이름/레이어 mask와 H3 경보

- **가설**: H2의 기하 문맥 lift는 layer/name 없이 유지된다.
- **arm**: FullName, NameMask, NameOnly, layer-token permutation.
- **지표**: Δ_name, mask 후 Δ_main band, name-only F1, silver rationale evidence class별 drop.
- **제안 합격선**: NameMask arm 자체가 Δ_main ≥ +0.10을 유지하고, Δ_name < 0.05.
- **경보/킬**: Δ_name ≥ 0.05이거나 mask로 support band에서 demote/kill band로 떨어지면 누수/H3 경보. name-blind arm이 P1을 넘지 못하면 H2 승격 금지. 이것은 H3 증거일 수 있으나 silver 학습의 안전성을 보장하지 않는다.
- **예산**: RTX 최대 6 GPU-hours. embedding을 제외한 arm은 checkpoint 구조를 공유하지 않고 독립 train.
- **시드**: 고정 세 seed.

#### P2-C5 — truth-source 전이와 proxy 독립성

- **가설**: 학습된 관계가 source 고유 prior가 아니라 다른 표현에도 전이된다.
- **설계**: train {eligible synthetic, FloorPlanCAD, CubiCasa, eligible silver} × eval {동일 source와 타 source}; target threshold 재튜닝 금지.
- **지표**: transfer F1/PR-AUC, diagonal/off-diagonal gap, 동일-instance error correlation, prediction-family collapse.
- **합격선**: H2 승격에는 최소 두 적격·비중복 source에서 Δ_main 방향 일치가 필요. proxy family-collapse rule에 걸린 둘은 한 source family로 셈.
- **보조 kill**: synthetic-trained GNN이 FloorPlanCAD에서 frozen deterministic baseline보다 낮으면 “synthetic 분포 충분” 보조가정 kill. H2 본체와 분리 기록.
- **본체 정지**: 한 source만 적격이거나 off-diagonal이 모두 baseline 이하이면 H2 승격 불가; test 미소비.
- **예산**: source당 CPU build 0.5–1일, 적격 train-source당 RTX 최대 18 GPU-hours.
- **시드**: 고정 세 seed.

#### P2-C6 — silver gate-only 대 distillation 통제

- **가설**: silver를 train target으로 넣는 것이 단순 gate-only 사용보다 실제 일반화를 높이며 판정자 버릇을 복제하지 않는다.
- **arm**: NoSilver, SilverGateOnly, SilverDistill-1epoch. 세 arm 모두 같은 non-silver train과 split 사용.
- **지표**: non-silver val Δ_main, name-mask drop, family별 error, rationale evidence distribution.
- **합격선**: SilverDistill이 NoSilver와 GateOnly보다 non-silver val에서 개선되고 name-masked arm에서도 방향이 유지되어야 함.
- **킬 조건**: silver 내부에서만 상승하거나 name mask 후 소실되면 distillation arm kill. silver B1/B4 미통과 시 cell 자체 비활성.
- **예산**: RTX 최대 9 GPU-hours.
- **시드**: 고정 세 seed.

#### P2-C7 — scale·metamorphic·대형 graph 안정성

- **가설**: 선택 model이 graph chunking과 허용 변환에서 의미 없는 예측 변화를 만들지 않는다.
- **입력**: 145장 modelspace와 sentinel, label 없어도 실행 가능.
- **지표**: 강체/단위/scale/name-rename prediction consistency, zero-wall FP, all-wall recall, chunk/full parity, peak RAM/VRAM, latency.
- **합격선**: 기존 배터리의 강체·단위 불변성을 후퇴시키지 않고, proposed chunk parity gate를 충족하며 zero/all-wall sentinel을 통과.
- **킬/정지**: zero-wall detector나 all-wall detector가 metric 허점을 이용하면 무효. max def에서 cap truncation 또는 OOM으로 handle을 누락하면 전체 scale claim 금지. 기존 scale arm FAIL 0.7624를 숨기지 않고 별도 보고.
- **예산**: CPU 1일, RTX inference 최대 6시간. DGX 사용 안 함이 기본.
- **시드**: 선택 ensemble 1개, 변환 생성 seed 고정.

#### P2-T1 — 최종 test 단발

- **가설**: val에서 봉인한 선택 규칙이 untouched test에 유지된다.
- **진입 조건**: G0/G1 PASS, C1 Occam gate가 GNN을 중단시키지 않음, C2–C4 PASS, C5에서 두 source concordance, evidence completeness PASS.
- **지표**: frozen P1, selected classical, selected GNN의 per-handle F1/P/R/PR-AUC와 drawing-level 분포.
- **합격선/킬**: 패킷의 Δ_main band를 그대로 적용. test에서 Δ_main < 0이면 H2 kill, 0 이상 0.10 미만이면 demote, 0.10 이상이면 지지. 단, context/name/source 조건을 모두 만족해야 최종 승격.
- **예산**: inference 1회, 재실행 금지. 인프라 실패는 prediction file이 생성되기 전이면 failure log 후 동일 immutable checkpoint로 재개할 수 있으나, metric을 본 뒤 재실행하지 않음.
- **시드**: 세 seed logit ensemble으로 사전 봉인.

### 6.3 의사결정 순서

1. G0 또는 G1 실패 → P2 학습 금지.
2. C1의 logistic/GBDT가 support band 충족 → GNN production 후보 kill, 고전 ML 승격 검토.
3. C1이 부족 → C2 GraphSAGE.
4. C2가 support band 미달 → H2 demote/kill, GAT 재탐색 금지.
5. C2 통과하나 C3 실패 → “딥 모델 효과”일 수는 있으나 “그래프 문맥 효과” kill.
6. C3 통과하나 C4 실패 → 이름 누수/H3 경보, H2 승격 금지.
7. C5에서 두 독립 source 미확보 → H2 unresolved, test 미소비.
8. 모두 통과 → C7 안정성 후 T1 단발.

---


---

## [platt_P3] — ## 6. 실험 셀 정의 (77 lines)

## 6. 실험 셀 정의

아래 합격선은 모두 **실행 전 봉인할 제안값**이다. 실측값처럼 읽어서는 안 된다. seed는 generator seed, mutation seed, 후보 seed를 서로 다른 namespace로 관리한다.

### C0 — PR-1 생성기·truth 자격 셀

- **가설**: wall/non-wall membership, mixed entities, chain/junction, open/closed scope를 construction으로 아는 합성 IR을 만들 수 있고, fidelity gate를 통과한다.
- **지표**: generator schema completeness, truth self-consistency, S/F/M 현상 coverage, B1 fidelity 지표, hidden family 분리 여부.
- **제안 합격선**: 패널 PR-1/T2가 요구한 fidelity gate 통과와 truth self-consistency 오류 0. 구체 B1 threshold는 PR-1 프리레그에서 정하며 P3 결과로 조정하지 않는다.
- **킬 조건**: 벽 생성 truth가 없거나 fidelity FAIL이 지속되면 정식 P3 admission·후보 랭킹을 중단한다. micro-fixture smoke test만 남긴다.
- **예산**: P3 자체 예산 밖의 프로그램 선결. 로컬 CPU.
- **시드 계획**: dev/hidden generator seed와 phenomenon family를 완전 분리; hidden은 relation author가 보지 않는다.

### C1 — Relation soundness 셀

- **가설**: MR-R/U/B/C/D의 applicability 조건 안에서는 correct-by-construction reference oracle이 위반하지 않는다.
- **지표**: relation별 reference violation numerator/denominator, invalid/NA 사유, geometry round-trip 오차.
- **제안 합격선**: 각 관계 reference 위반 0%. invalid가 특정 family에 집중되면 coverage 결함으로 별도 실패 처리한다.
- **킬 조건**: 의미 보존을 논증할 수 없거나 reference가 한 번이라도 위반한 관계는 배터리에서 제거한다. 제거 후 관계가 2개 미만이면 P3 전체를 판별기 후보로 보류한다.
- **예산**: 로컬 CPU 0.5일 제안.
- **시드 계획**: 고정 dev seed + 미접촉 hidden seed. 경계값은 random과 별도 deterministic fixture로 전수한다.

### C2 — Mutation conviction admission 셀

- **가설**: sound relation은 자신이 겨냥한 실제 결함 mechanism의 비동치 뮤턴트를 높은 비율로 죽인다.
- **지표**: relation×mutant kill matrix, hidden conviction, equivalent/invalid 사유, mechanism-family coverage.
- **제안 합격선**: 관계별 hidden conviction ≥95%, reference 위반 0%, hidden 비동치 mutant 최소 20개 제안.
- **킬 조건**: 95% 미만인 관계는 불합격. 아무 뮤턴트도 죽이지 못하는 관계는 카드 규칙 2에 따라 즉시 폐기한다. 뮤턴트 복제로 비율을 올린 흔적이 있으면 admission 전체 무효다.
- **예산**: 로컬 CPU 0.5~1일 제안.
- **시드 계획**: family별 균형 seed, public/hidden 분리. stochastic 후보 seed는 conviction 분모와 별개다.

### C3 — Cheapest probe: 회전 + distractor + sentinels

- **가설**: 현 v0와 비교 후보에서 회전 plumbing 오류 또는 wall-like distractor 민감도를 하루 안에 관찰할 수 있고, 0/전벽 adapter를 확실히 죽일 수 있다.
- **지표**: 20 def의 rotation macro failures, injected-handle FP, original-stability failures, S-Z/S-A, runtime, provenance 오류.
- **제안 합격선**: runner/handle map 오류 0, sentinels가 constant-zero/one을 모두 kill, reference fixture 위반 0. 후보 승격선은 이 smoke cell에서 선언하지 않는다.
- **킬 조건**: transform provenance가 불안정하거나 distractor safe patch를 만들 수 없어 유효 trial이 거의 없으면 probe 설계를 폐기·수정한다. 후보의 회전 위반은 engineering finding이지만 C0~C2 전에는 프로그램급 후보 kill로 승격하지 않는다.
- **예산**: 패킷대로 1일, 로컬 CPU, GPU 0.
- **시드 계획**: 20-def manifest와 transform/injection seed를 실행 전 고정; 결과를 보고 definition 교체 금지.

### C4 — 145 실코퍼스 공통 후보 gate

- **가설**: admitted battery가 P1/P2/P4/P5의 label-free failure profile을 분리한다.
- **지표**: 관계별 `V_r`, exact numerator/denominator, coverage, hard rotation failures, sentinel status, runtime, 후보×관계 violation matrix.
- **제안 합격선**: sentinels 통과, 회전 0 위반, 나머지 admitted invariant 관계 `V_r≤1%`. 145개가 모두 유효한 관계는 도면 단위 최대 1건 실패만 허용된다. anti/arrangement는 relation별 prereg scope에 따라 hard 또는 diagnostic으로 분리한다.
- **킬 조건**: 후보는 회전 한 건 위반 시 silver와 무관하게 kill. 반대로 전 후보가 같은 관계를 대량 위반하지만 synthetic C1/C2를 통과했다면 후보들을 일괄 kill하지 않고 relation validity 또는 domain-gap 보조가정을 kill한다. 전체 배터리가 아무 후보도 구분하지 못하면 판별력 0으로 큐에서 제거한다.
- **예산**: 로컬 CPU, definition 병렬. wall-clock 상한은 최대 도면 preflight 뒤 봉인. GPU/DGX 0.
- **시드 계획**: 후보별 동일 transform seed. stochastic 후보는 canonical seed + 사전 지정 반복 seed를 모두 보고하며 best-seed 선택 금지.

### C5 — Thickness·arrangement scope 셀

- **가설**: 두께 band 내부 perturbation은 membership을 보존하고, closed-partition scope의 올바른 wall set은 chain/junction/face 구조에 참여한다.
- **지표**: band stratum별 MR-B violation, invalid collision rate, chain/junction/face support, open-vs-closed scope 차이.
- **제안 합격선**: MR-B reference 0 위반과 conviction ≥95%. MR-C는 `closed_partition`에서만 같은 admission 기준을 만족해야 hard relation이 된다.
- **킬 조건**: open-plan에서 과강하거나 scope tag가 후보 출력에 의존하면 MR-C hard gate를 kill하고 soft diagnostic만 유지한다. MR-B eligibility가 실제 도면에서 지나치게 낮으면 전체 후보 pass로 오인하지 않고 relation을 보류한다.
- **예산**: 로컬 CPU 1~2일 구현·실행 제안.
- **시드 계획**: band 하/중/상과 경계 fixture를 층화, open/closed family 분리.

### C6 — CubiCasa val 개발·test 단발 / raster 전이 셀

- **가설**: SEG-IR와 raster 후보에서도 라벨 점수와 MR robustness가 서로 다른 정보를 주며, adapter 자체의 좌표계 오류를 잡을 수 있다.
- **지표**: val/test F1 등 기존 공식 metric, relation profile, label error×MR violation 교차표, raster inverse-warp consistency, shuffle control.
- **제안 합격선**: 배터리 threshold는 synthetic-only로 이미 봉인; test는 최종 후보·threshold당 한 번. test 실행 성공 전 결과 미열람 정책과 xlsx 증거 완비.
- **킬 조건**: raster interpolation artifact가 mutant보다 더 많이 relation을 죽이거나 exact projection이 없으면 raster 결과를 vector gate에서 분리한다. counsel 미확인 시 외부셋 학습/배포성 주장은 보류한다.
- **예산**: vector는 로컬 CPU; raster/VLM 후보 추론에만 RTX 5070 Ti 16GB. DGX 0.
- **시드 계획**: val 개발 seed와 test canonical seed 분리. test 재튜닝·두 번째 선택 실행 금지.

### C7 — 대리 독립성·관계 상관·abstain 셀

- **가설**: metamorphic 위반은 synthetic/external-label/silver와 완전히 같은 prior의 복제가 아니며, 관계별 실패 pattern도 적어도 일부 비중복 정보를 가진다.
- **지표**: 동일 def에서 synthetic/external/silver/MR의 3원·4원 불일치 구조, φ/Jaccard correlation, violation clustering, silver 어휘가문별 결과.
- **제안 합격선**: 단일 “독립성 점수”를 사후 발명하지 않는다. 관계별 contingency table과 cluster를 의무 공개하고, 완전 중복 관계는 한 증거 family로 축약한다.
- **킬 조건**: MR이 외부/silver와 사실상 같은 평행이중선 prior만 복제하고 추가 disagreement를 설명하지 못하면 “독립 공용 심판” 주장을 kill한다. 모든 후보가 동률이면 A1 abstain을 발동한다.
- **예산**: 기존 후보 출력 재사용, 로컬 CPU 반나절 제안.
- **시드 계획**: C4/C6 frozen 결과만 사용하며 새 seed로 유리한 불일치 사례를 탐색하지 않는다.

---


---

## [platt_P4] — ## 6. 실험 셀 정의 (75 lines)

## 6. 실험 셀 정의

### 6.1 공통 프리레그와 집계

평가 단위는 원본 handle이다. 1차 synthetic F1은 held-out 전체의 pooled per-handle F1, 보조로 도면별 macro F1과 pair/link/component 지표를 보고한다. RL의 3 seed 결과는 사전 봉인한 산술평균으로 집계하고 seed별 원값을 숨기지 않는다. Metamorphic 1차 지표는 hidden transform family의 도면별 위반율 평균이며 낮을수록 좋다. 동일 도면·동일 후보 cache를 arm 간 paired 비교한다.

Val은 개발·튜닝·threshold 봉인에 사용한다. Test manifest는 생존 판정 전 접근하지 않고, 해시만 기록한다. 모든 셀에는 shuffled-label/action 대조군을 포함한다. Shuffle이 비정상적으로 높은 성능을 내면 누출 조사 전까지 해당 셀은 무효다. 실패와 timeout도 evidence xlsx의 행으로 남긴다.

아래 시간과 폭은 모두 **제안된 예산/판정값**이며 새 실측 주장이 아니다.

### 셀 P4-E0 — 선결·verifier 자격 감사

- **가설:** 동결 verifier는 명백히 틀린 집합을 통과시키지 않으며 synthetic·metamorphic proxy의 오류가 완전히 같은 prior로 붕괴하지 않는다.
- **arm:** truth set, empty, all-wall, random, GBDT-threshold, 구조 교란, scale/unit/explode 교란, 긴 평행 distractor; proxy disagreement audit.
- **지표:** verifier false-accept rate, false-reject rate, source별 오류 교집합/조건부 오류, sentinel 통과율, reward SHA 재현성.
- **합격선:** 패널 T26 그대로 false-accept ≤0.01. PR-1 fidelity gate, PR-2 독립성 결론, P3 sentinel/recall floor도 모두 PASS여야 한다.
- **킬/중단:** false-accept >0.01, reward hash 비재현, sentinel 미검증, proxy 붕괴를 독립 확증으로 오해해야만 보상이 성립하는 경우 P4 실행을 중단한다. 이는 HR1 성능 패배와 구분한다.
- **예산:** 로컬 CPU 1일 cap, GPU 불필요. seed가 아니라 봉인된 adversarial family 전수와 bootstrap을 사용한다.

### 셀 P4-E1 — 학습 0 reward-landscape probe

- **가설:** 집합 보상에 실제 탐색 난도가 있다면 beam이 greedy를 유의미하게 넘고, tractable subset에서 둘 다 ILP/열거 상한에 붙지 않는다.
- **arm:** random, greedy, beam width 4/16/64, tractable ILP/열거. 모두 동일 후보·동일 동결 verifier·동일 총 호출/월클록 ledger를 쓴다.
- **지표:** synthetic val F1, terminal reward, beam gain, ILP incumbent/bound gap, verifier 호출 수, action branching, wallclock.
- **합격선:** beam이 greedy보다 개선되고, greedy가 certified/empirical upper bound에 붙지 않아야 E2로 진행한다.
- **사전 킬 정의:** 전체 val에서 best-beam−greedy F1 <0.01이고, tractable stratum에서 상한−greedy F1 ≤0.01이면 `greedy≈beam≈upper bound`로 판정하여 학습 전에 HR1 RL 레인을 kill한다. 상한을 인증할 수 없으면 “상한 근접”을 주장하지 않고 다음 셀로 보수적으로 진행한다.
- **예산:** 로컬 1일, 학습 0, seed 대신 deterministic tie-breaking 1회와 random baseline 3 seed.

### 셀 P4-E2 — 엔티티 고정-라벨 음성 대조

- **가설:** 동일한 동결 특징에서 per-handle supervised BCE/GBDT가 one-step RL보다 같거나 낫다.
- **arm:** 기존 GBDT, 동일 policy head의 supervised BCE, 각 handle을 독립 행동으로 취급한 policy-gradient. Encoder, feature, tuning budget은 공유한다.
- **지표:** synthetic held-out 및 CubiCasa val의 per-handle P/R/F1, calibration, 학습 분산, wallclock.
- **합격선:** 이 셀에는 HR1 생존권이 없다. RL이 supervised를 0.05 F1 이상 넘지 못하면 고정-라벨 full RL을 명시적으로 kill하고 C07의 이 범위 적용을 유지한다.
- **이상 결과 처리:** RL이 0.05 이상 높아도 즉시 채택하지 않는다. supervised 목적·class weight·threshold·budget 누락을 red-team하고 재현된 차이만 별도 이슈로 남긴다. 집합 조립의 승리로 합산하지 않는다.
- **예산:** arm별 동일 8시간 cap, 3 seed, 로컬 GPU. Test는 열지 않는다.

### 셀 P4-E3 — 집합 조립 본선

- **가설:** 비분해 구조 보상에서 RLVR 정책은 동일 compute beam보다 높은 synthetic held-out handle F1을 내면서 metamorphic 위반을 늘리지 않는다.
- **arm:** supervised+greedy, beam budget sweep, ILP 보조 통제, RLVR greedy decode. 모두 같은 πref, P2 encoder, 후보 cache, reward SHA를 쓴다.
- **지표:** synthetic held-out per-handle F1(1차), P/R, pair/link/component F1, hidden metamorphic 위반율, reward, verifier 호출 수, wallclock, peak RAM/VRAM, cap-hit rate.
- **유일 생존 밴드:** `mean_seed(F1_RL) − F1_beam ≥ +0.05` **AND** `mean_seed(Violation_RL) − Violation_beam ≤ 0`. Paired bootstrap interval과 seed별 결과는 보고하지만 이 사전 판정식을 사후 교체하지 않는다.
- **킬:** 둘 중 하나라도 미달하면 HR1 RL 레인을 kill한다. supervised+greedy 또는 ILP가 RL보다 좋으면 그 결과도 그대로 kill 근거로 기록한다. 연장·추가 seed·reward 재가중으로 구조하지 않는다.
- **예산:** 공통 imitation prefix 후 각 arm/seed 추가 24시간 cap, RL 3 seed. Beam/ILP도 동일 ledger 상한. 로컬 우선, DGX는 사후 재현 ablation만.

### 셀 P4-E4 — 보상해킹·강건성 감사

- **가설:** 높은 동결 reward가 독립 truth F1 및 hidden metamorphic 성능과 같은 방향으로 움직인다.
- **arm:** E3 checkpoint 시계열, adversarial set perturbation, hidden generator family, hidden transformation family, reward항별 ablation.
- **지표:** checkpoint reward-F1 궤적, rank correlation, empty/all-wall 빈도, recall-floor hit, conflict/cap-hit, hidden-family regret.
- **즉시 킬:** 연속 평가에서 정책 reward가 상승하는데 synthetic held-out F1이 하락하는 괴리가 재현되거나, best-reward checkpoint가 empty/all-wall·sentinel exploit로 선택되면 즉시 중단하고 incident ID, 최초 checkpoint, exploit family, SHA를 기록한다. E3 평균으로 덮지 않는다.
- **추가 킬:** hidden family에서만 성능이 붕괴하여 E3 생존 밴드가 사라지면 HR1을 kill한다.
- **예산:** E3 실행 중 CPU audit + 종료 후 로컬 8시간 cap, 동일 3 seed trace; 새 정책 튜닝 없음.

### 셀 P4-E5 — 외부 전이와 test 단발

- **가설:** E3에서 살아남은 조립 이점이 synthetic generator에만 국한되지 않는다.
- **arm:** 봉인된 E3의 supervised+greedy, beam, RLVR checkpoint 그대로. CubiCasa test를 방법당 한 번 실행하고, 1.dwg hidden metamorphic 및 held-out silver 일치표를 생성한다.
- **지표:** CubiCasa test per-handle P/R/F1, 도면 macro F1, 1.dwg hidden metamorphic 위반, silver 2-family별 일치. FloorPlanCAD는 T24/PR-3 통과 시 비보상 mask 진단만.
- **합격선:** E3의 HR1 판정을 바꾸는 사후 합격선으로 쓰지 않는다. 다만 RL의 CubiCasa test F1이 beam보다 낮거나 hidden metamorphic 위반이 높으면 “synthetic 한정”으로 명시하고 배포를 kill한다.
- **킬:** test를 미리 보거나, checkpoint/threshold를 test 결과로 바꾸거나, silver를 독립 5표로 평균하면 셀 전체 무효다.
- **예산:** checkpoint당 test 1회, 추가 학습 0, deterministic decode + RL seed 3개 사전 집계. 외부 권리 미확인 시 실행하지 않는다.

### 셀 P4-E6 — 획득 순서 contextual bandit 부속 절차

- **가설:** definition context로 비싼 독립 판정/렌더의 한 단계 가치가 예측 가능하지만 장기 credit assignment는 필요 없다.
- **arm:** random, uncertainty, diversity-stratified heuristic, contextual bandit(LinUCB 또는 Thompson 계열 중 val에서 하나 봉인).
- **context/action/reward:** context는 후보 수, unary entropy, component fragmentation, transform disagreement, 예상 렌더 비용이다. action은 다음 definition 하나 선택, reward는 허용된 사람 truth 또는 synthetic oracle을 얻은 직후의 정보가치/오류감소다. E1.5 silver는 관측·reward·update에 사용하지 않는다.
- **지표:** 동일 비용에서 누적 발견 오류, coverage, 선택 편향, wallclock.
- **합격선:** random/heuristic보다 나아야 부속 도구로 유지한다. full RL과 비교하거나 HR1에 합산하지 않는다.
- **킬:** 효과가 다음 라운드 이후의 상태에 의존한다는 증거가 없는데 full RL로 포장하거나, silver feedback으로 bandit을 갱신하면 즉시 kill한다.
- **예산:** 로컬 CPU 1일 cap, offline replay 3 seed. PR-3가 필요한 사람 truth arm은 counsel 전 실행 금지.

Self-training은 별도 실험 셀을 만들지 않는다. 동일 모델의 pseudo-label E-step과 재학습 M-step으로 명시하고 P2 실험표에 귀속한다. P4가 그 개선을 RL reward나 policy improvement로 보고하는 것을 금지한다.


---

## [platt_P5] — ## 6. 실험 셀 정의 (105 lines)

## 6. 실험 셀 정의

### 6.1 공통 프리레지스트레이션 규칙

- val은 개발·threshold 선택에 허용한다. test는 방법당 한 번만 연다.
- split, renderer style, prompt, model revision, seed, bridge threshold, metric code hash를 시험 전에 봉인한다.
- 셔플 대조군과 0-wall/all-wall sentinel은 의무다.
- 세 seed 결과는 평균·분산·각 seed를 모두 보이고 best seed만 선택하지 않는다.
- 5a는 유효 응답 한 번이 한 trial이다. stochastic repeat 평균으로 신뢰도를 꾸미지 않는다.
- primary metric과 kill condition을 바꾼 재실행은 같은 셀의 재시도가 아니라 새 version이다.
- 모든 셀은 mandatory xlsx에 실패 사유까지 쓴다.

### 6.2 Gate G0 — 권한·자산·capability preflight (과학 셀 아님)

- **가설**: 없음. 실험 자격 확인이다.
- **필수 확인**: PR-1/CL-C synthetic wall pack, counsel 서면, API 승인/retention/cost envelope, CL-A sealed divergent-20, endpoint image+polygon capability, Ornith vision 지원 여부.
- **통과선**: 각 후속 셀이 요구하는 항목이 문서와 hash로 존재.
- **킬/정지**: counsel 거부는 해당 외부 데이터 arm kill; API 미승인은 5a BLOCKED; synthetic pack 부재는 bridge 이후 전 셀 BLOCKED; Ornith vision 미지원은 DGX 확장만 kill.
- **예산**: 제안 0.5 개발일, API 유료 호출 없음.
- **시드**: 해당 없음.

### 6.3 Cell V1 — BRIDGE-ORACLE: vision 독립 bridge gate

- **가설**: exact wall mask와 exact provenance가 주어지면 raster wall region을 wall-member handle로 되돌릴 수 있다.
- **데이터**: CL-C synthetic train/dev/hidden-mutation, 0-wall/all-wall sentinel, nested INSERT/poché/crop-cut fixture.
- **조작**: style family, halo `δ`, positive/negative/ambiguity threshold. 선택은 synthetic dev만 사용하고 hidden mutation은 마지막에 한 번 실행.
- **primary 지표**: oracle-mask micro handle F1. 보조는 precision, recall, macro drawing F1, ambiguity/abstain, strict metamorphic pass, affine error.
- **제안 합격선**: hidden-mutation 포함 `F1_bridge_oracle ≥ 0.6`, sentinel 전부 PASS, metadata audit PASS. 높은 점수 하나로 sentinel 실패를 상쇄할 수 없다.
- **킬 조건**: `F1_bridge_oracle < 0.4`면 5a/5b 동시 kill. 0.4–0.6은 발언권 보류와 bounded redesign 1회; PASS로 반올림 금지.
- **셔플 대조군**: provenance handle mapping을 drawing 내부에서 shuffle했을 때 진짜 mapping과 같은 성능이면 bridge truth chain FAIL.
- **예산**: 제안 1 CPU일, 유료 API 없음.
- **시드**: renderer/style seed 1701/1702/1703; hidden family seed는 prereg 파일에 봉인하고 개발자에게 비공개.

### 6.4 Cell V2 — SEG-FPC: 5b pixel segmentation

- **가설**: 소형 raster segmenter가 FPC 벽 mask를 학습해 synthetic render에서도 벽 픽셀 구조를 회수한다.
- **데이터**: counsel 허용 FPC drawing-level train/val/internal holdout; CL-C synthetic dev는 domain-transfer 진단.
- **조작**: 제한된 SegFormer-B0급 hyperparameter grid. U-Net은 loader/loss sanity baseline이며 model zoo 경쟁자가 아니다.
- **primary 지표**: FPC val wall-pixel IoU. 보조는 Dice, boundary F1, crop-edge recall, calibration/abstain, style-family별 IoU.
- **제안 합격선**: synthetic render에서 5b wall-pixel IoU ≥ 0.7. FPC val은 선택 곡선과 오류 유형을 보고하되 synthetic gate를 대신하지 않는다.
- **킬 조건**: counsel 불허, duplicate/split 누출, mask alignment 실패, 또는 synthetic IoU 0.7 미달이면 5b kill/demote. 이는 oracle bridge가 통과했다면 5a를 죽이지 않는다.
- **셔플 대조군**: drawing 단위로 mask를 shuffle한 동일 학습 budget. 정상 model과 구분되지 않으면 누출/학습 파이프라인 FAIL.
- **예산**: 제안 2–3 GPU일, RTX 5070 Ti 16GB, RAM 64GB. DGX 없음.
- **시드**: 1701/1702/1703 전부 실행·보고.

### 6.5 Cell V3 — SEG-BRIDGE-XFER: 5b end-to-end와 proxy 독립성

- **가설**: 5b mask가 bridge를 거쳐 synthetic handle truth를 회수하고, CubiCasa val에서 locked GBDT와 다른 오류를 낸다.
- **데이터**: synthetic hidden mutation, CubiCasa val 400, registered metamorphic variants. CubiCasa test는 닫힌 상태 유지.
- **primary 지표**: synthetic end-to-end handle F1. 보조는 CubiCasa val handle F1, GBDT+raster 고정 결합 F1, per-drawing macro F1, error-overlap Jaccard, class별 FP, strict metamorphic pass, proxy pairwise disagreement.
- **제안 합격선**: synthetic `F1_handle ≥ 0.6`; 5b pixel IoU ≥ 0.7 유지; zero/all sentinel PASS. CubiCasa에서는 GBDT와 오류가 완전히 중복되지 않고 fixed ensemble에 양의 기여가 있어야 H4 외부전이 후보가 된다.
- **킬 조건**: end-to-end F1 < 0.4이면 5b kill. 단 V1 oracle bridge가 ≥0.6이면 공통 bridge kill로 기록하지 않는다. metadata/render label 누출은 셀 무효.
- **proxy 감사**: 같은 synthetic/CubiCasa definition에서 exact/human label, metamorphic relation, raster vote, 허가된 silver vote의 disagreement tensor를 만든다. 세 proxy가 같은 handle에서 같은 오류를 반복하면 독립 증거로 합산하지 않는다.
- **셔플 대조군**: CubiCasa handle truth를 drawing 내부 prevalence-preserving shuffle하여 complementarity가 우연히 생기는지 확인.
- **예산**: 제안 1 CPU/GPU일, 외부 API 없음.
- **시드**: V2의 3개 checkpoint 전부; permutation seed 1701 고정.

### 6.6 Cell V4 — VLM-CHEAP20: 5a 최저가 screen

- **가설**: 이름·메타데이터가 없는 20개 divergent definition crop만으로 프런티어 VLM이 non-degenerate wall region을 제시한다.
- **데이터**: CL-A가 정렬 artifact를 제거하고 봉인한 divergent-20, definition당 primary neutral render 1장.
- **조작**: 없음. prompt, endpoint, model revision, decoding은 synthetic dev에서 이미 봉인.
- **primary 지표**: schema-valid non-abstain rate와 provisional family-disagreement resolution count. 보조는 polygon validity, bridge ambiguity, crop-edge abstain, per-def billed cost, P0 forensic category와의 교차표.
- **제안 합격선**: 이 셀 단독으로 최종 PASS를 주지 않는다. 적어도 하나의 provisional resolution과 유효한 bridge output이 있어야 V5 비용을 정당화한다.
- **킬 조건**: 예상 또는 누적 비용이 `B_API` envelope를 넘음, API/retention 미승인, repeated invalid schema, 모든 사례 non-informative abstain이면 5a 비용/효용 kill.
- **셔플 대조군**: image와 response 연결을 shuffle한 분석에서 동일한 handle resolution이 나오면 join pipeline FAIL. 추가 API 호출은 하지 않는다.
- **예산**: 패킷 기준 1일, image 20장, 유효 응답 20개 이하, 소액 API envelope 내부.
- **시드**: temperature 제안값 0; endpoint seed 지원 시 1701 하나. 유효 응답 재표본화 금지.

### 6.7 Cell V5 — JURY-META: H4/H3 배심 가치 확인

- **가설**: V1–V4를 통과한 raster juror가 vector family disagreement를 strict metamorphic relation을 지키며 해소하거나 family-level Fleiss κ를 유의하게 높인다.
- **데이터**: divergent-20 primary와 봉인된 강체회전/반사/translation-crop/layer-rename/unit/explode 관계 중 renderer가 지원하는 등록 battery. 5a는 cost envelope가 허용하는 최소 변형만, 5b는 전체 battery.
- **primary 지표**: strict metamorphic-consistent `resolution_rate`. 공동 primary 대안은 family-collapsed `Δκ`와 prevalence-preserving one-sided permutation test다.
- **제안 합격선**: 20개 중 최소 6개를 strict 조건으로 해소 **또는** `Δκ > 0`이고 봉인한 α=0.05 permutation gate 통과. E1.5 편입에는 별도로 B1 ≥0.70 및 B4 Pearson ≥0.70이 모두 필요.
- **킬/강등 조건**: 두 가치 band 모두 미달이면 tie-breaker/diagnostic으로 demote. sentinel 실패, layer rename 후 image hash 변화, transform inverse 실패는 셀 무효. κ 상승과 truth/invariance 하락이 함께 나타나면 juror kill.
- **비교**: 5a, 5b를 각각 한 표로 평가한다. 둘을 함께 넣는 분석은 their error correlation이 낮다는 V3 증거가 있을 때만 secondary.
- **셔플 대조군**: raster vote를 definition·prevalence strata 안에서 permutation해 resolution/Δκ null을 만든다.
- **예산**: 5b 로컬 1일. 5a는 V4 이후 잔여 `B_API` 이내; 부족하면 BLOCKED이며 screen을 최종 PASS로 승격하지 않는다.
- **시드**: model seed는 V2 세 개 전부; permutation seed 1701; VLM은 V4의 고정 endpoint/seed.

### 6.8 Cell V6 — CUBICASA-TEST-ONCE: 외부 단발 확인

- **가설**: FPC에서 학습하고 synthetic/CubiCasa val에서 잠근 5b가 CubiCasa test 400에서도 locked GBDT에 상보적인 handle signal을 낸다.
- **개방 조건**: counsel 승인, V1/V2/V3 통과, config·threshold·metric code·xlsx schema hash 봉인, test 접근 로그가 비어 있음.
- **primary 지표**: locked `GBDT+raster`와 `GBDT-only`의 per-handle F1 차이. 보조는 raster-only F1/precision/recall, macro drawing F1, error categories, abstain, strict relation subset.
- **제안 합격선**: fixed ensemble의 F1 차이에 대한 paired drawing-level confidence interval 하한이 0보다 크고, synthetic bridge/IoU gate가 유지된 config일 것. 이 조건은 새 test threshold 선택을 허용하지 않는다.
- **킬 조건**: test에서 config를 변경하거나 두 번 열면 confirmatory claim 무효. 양의 상보성이 없으면 CubiCasa external-generalization claim kill; real divergent jury 결과가 있더라도 별도 제한적 관찰로만 남긴다.
- **셔플 대조군**: test를 본 뒤 새 shuffle 설계를 만들지 않고 V3에서 봉인한 procedure를 그대로 한 번 적용.
- **예산**: 제안 반나절 로컬 inference/채점, 학습 없음, API 없음.
- **시드**: V2 세 seed ensemble 규칙을 val에서 고정. test에서 seed 선택 금지.

### 6.9 셀 간 판정 행렬

| 결과 | 5a | 5b | 공통 lane |
|---|---|---|---|
| V1 oracle bridge <0.4 | KILL | KILL | KILL |
| V1 0.4–0.6 | 발언권 없음 | 발언권 없음 | bridge redesign 1회만 |
| V2 IoU <0.7, V1 통과 | 영향 없음 | KILL/DEMOTE | 5a만 가능 |
| V4 API 미승인 | BLOCKED | 영향 없음 | 5b만 가능 |
| V4 비용 초과 | 비용 KILL | 영향 없음 | 5b만 가능 |
| V5 가치 band 미달 | DEMOTE | DEMOTE | tie-breaker만 |
| V6 외부 상보성 없음 | real screen 관찰만 | external claim KILL | 제품 승격 금지 |

---


---

## [platt_P6] — ## 6. 실험 셀 정의 (99 lines)

## 6. 실험 셀 정의

공통 원칙: val=개발·튜닝 허용, test=방법당 단발, 합격선 프리레그 봉인, 셔플 대조군 의무, 증거 xlsx, 실패도 기록.  
수치 합격선은 패킷 **prereg band 초안**을 그대로 봉인 후보로 사용(Paul 확정 전 candidate).

### Cell-LEX — Lexicon 동결 (선결)

| 항목 | 내용 |
|------|------|
| 가설 | firm-특유 벽레이어·블록 토큰 목록을 시험 전에 봉인하면 사후 피팅을 차단한다 |
| 지표 | lexicon 버전 해시, 토큰 수, tautology 목록 크기, inter-annotator(가능 시) |
| 합격선 | 해시 고정 + tautology_list 비공집합 + 변경 시 새 실험 ID |
| 킬 | 동결 없이 본실험 착수 → 절차 kill (결과 무효) |
| 예산 | 0.5–1일, 로컬 |
| 시드 | N/A (규칙 동결); 목록 작성자·일자 기록 |

### Cell-PID — project_id 유도 감사 (보조가정)

| 항목 | 내용 |
|------|------|
| 가설 | 파일명/xref 기반 project_id가 실제 관례 클러스터와 일치한다 |
| 지표 | 수동 표본 일치율(예: 30도면), 동일 레이어코딩이 다른 project_id로 쪼개진 비율 |
| 합격선 | 사전등록 일치율 하한(예: ≥0.9 — **요검증·Paul 봉인**); 미달 시 규칙 수정 후 재동결 |
| 킬 | 일치율 낮음에도 GroupKFold 강행 → cross 지표 해석 불가 (실험 무효) |
| 예산 | 0.5일 |
| 시드 | 표본 추출 seed=20260718 |

### Cell-CP — Cheapest probe (384-def)

| 항목 | 내용 |
|------|------|
| 가설 | 관례 토큰 빈도만으로도 v0 쌍-밀도와 유의미한 point-biserial이 나온다 |
| 지표 | point-biserial r, 상위 토큰 표, tautology-stripped vs full |
| 합격선 | 탐색적 — \|r\| 효과크기 기록; 본실험 go/no-go는 운영 판단 |
| 킬 | 조기 경고: tautology-stripped에서 chance 수준이면 Cell-XP 축소 |
| 예산 | 수 시간, CPU |
| 시드 | 토큰 해시 seed=42 |

### Cell-XP — Cross-project 주 실험 (H3 판정)

| 항목 | 내용 |
|------|------|
| 가설 | 기하 없는 관례 모델이 cross-project로 일반화되면 H3(재사용 prior) 지지 |
| 지표 | AUC, F1, P, R — **within vs cross** 쌍; Model-A 기준; 셔플 AUC |
| 제안 합격선 (prereg 초안) | cross AUC ≥0.75 → 재사용 prior로 H3 지지; within ≥0.9 & cross ≤0.6 → H3 demote(프로젝트-국소) |
| 킬 조건 | cross AUC ≤0.55 → **H3 kill**; 셔플 AUC가 본 AUC에 근접하면 누수/버그 kill |
| 예산 | 1–2일 CPU; GPU 0 |
| 시드 | GroupKFold shuffle seed ∈ {0,1,2} 보고; 모델 seed=0 고정 1회 + 민감도 2회 |

### Cell-TAU — 동어반복 분리 보고

| 항목 | 내용 |
|------|------|
| 가설 | 성능의 상당 부분이 WALL/벽 토큰 누수다 |
| 지표 | AUC_A, AUC_B, AUC_C; Δ(C−A) |
| 합격선 | 판정은 A만; Δ(C−A) 크면 누수 경고 플래그 |
| 킬 | C만 인용한 H3 지지 주장 → 보고서 무효 |
| 예산 | Cell-XP에 포함 |
| 시드 | 동일 |

### Cell-E1C — LLM likelihood ↔ 관례 점수

| 항목 | 내용 |
|------|------|
| 가설 | E1/E1.5 silver가 이름-prior를 탄다 |
| 지표 | Pearson/Spearman(s_llm, s_conv); name-blind vs full 각각; 가문별(fable+sol vs opus+sonnet+grok) |
| 합격선 | corr ≥0.7 → E1 silver 독립성 demote (해석 테이블 주입) |
| 킬 | 해당 없음(감사 셀); 단 s_llm 미조달 시 deferred |
| 예산 | 0.5일 + E1 아티팩트 존재 전제 |
| 시드 | 상관은 결정론 |

### Cell-STK — 스태킹 한계 기여 (기하 대비)

| 항목 | 내용 |
|------|------|
| 가설 | 기하 GBDT/탐지기에 관례 점수를 더해도 한계 이득이 있다 |
| 지표 | ΔF1/ΔAUC on val; concordance 검증셋은 훈련과 분리 |
| 합격선 | 사전등록 Δ 하한(예: ΔAUC≥0.02 — Paul 봉인); 미달 ≈0 → 타이브레이커 demote |
| 킬 | 한계 기여 ≈0 → 지배 메커니즘 아닌 보조로 demote (H3 kill과 별개 조항) |
| 예산 | 1일; CubiCasa에서는 관례=0 통제만 |
| 시드 | 기하 모델 고정 체크포인트 + convention seed=0 |

### Cell-SHUF — 셔플 대조군

| 항목 | 내용 |
|------|------|
| 가설 | 라벨 셔플 시 AUC≈0.5 (CubiCasa 기하 암 셔플 0.375 PASS 패턴 준용) |
| 지표 | shuffle AUC |
| 합격선 | 본 AUC − shuffle AUC 간격 충분(사전등록); shuffle≫0.5면 버그 |
| 킬 | shuffle 실패 시 Cell-XP 해석 금지 |
| 예산 | Cell-XP의 20% |
| 시드 | permutation seeds={0,1,2,3,4} |

### 셀 수에 대한 정당화

과소 금지: H3 생사(XP)·누수(TAU)·E1(E1C)·스태킹(STK)·선결(LEX/PID)·probe(CP)·shuffle이 각기 다른 가설을 닫는다.  
과잉 금지: 아키텍처 탐색·GPU·VLM·합성 truth 셀은 두지 않는다.

---
