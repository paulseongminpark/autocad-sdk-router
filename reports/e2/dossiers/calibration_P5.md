# DOSSIER — calibration_P5

**제안**: Frontier VLM jury silver와 local open VLM 학습의 분리  
**좌석**: calibration_forecaster · P5  
**클러스터**: CL-G (래스터/VLM 이중 트랙)  
**상태**: candidate — VIABLE(조건부). 채택은 Paul.  
**forecast**: null (abstain) · `score_type=brier` · `reference_class=RC-WALL-ZL, n=0, n_min=5` · `abstain_flag=empty_reference_class`  
**resolution_verdict**: open

---

## 0. 한 줄 계약

E1.5 admission gate(`B1≥0.70` AND `B4 Pearson≥0.70`)를 통과한 고합의 VLM silver만 local open VLM(LoRA/adapter) 또는 P2/P3 weak feature의 **제한된 training evidence**로 쓰고, 최종 평가는 synthetic exact handles와 FloorPlanCAD held-out labels의 **S/F resolver만** truth로 쓴다. VLM 출력은 어떤 경우에도 resolver·geometric SoT가 되지 않는다.

---

## 1. 이론적 근거·선행연구

### 1.1 계보 (왜 "jury silver → student"인가)

이 제안은 세 갈래의 방법론 계보를 합친다.

1. **Weakly supervised / silver labeling.** 고비용 oracle 대신 약한 라벨로 학습하되, 라벨을 truth와 동일시하지 않는 전통(예: distant supervision, Snorkel식 generative labeling — 요검증: Ratner et al. Snorkel; Zhou weak supervision survey). E2에서는 E1.5·frontier 합의·rationale가 전부 silver이며, S/F resolver만이 semantic 성공을 판정한다.
2. **Committee / jury consensus.** 독립(또는 준독립) 판정자 다수가 합의할 때만 학습 표본으로 승격하는 설계. 고전 committee machine·query-by-committee와, LLM-as-judge 앙상블(예: LLM-as-a-Judge / MT-Bench 계열 — 요검증)의 CAD 시각판 변형이다. 핵심은 **합의 = truth가 아니라 admission**이라는 점이다.
3. **Teacher–student / knowledge distillation with frozen teacher.** Frontier VLM을 동결 teacher로, local open VLM(3–7B quantized + LoRA)을 student로 둔다. Prompting 경로 = silver acquisition, fine-tuning 경로 = student learning으로 **역할 분리**. 이는 vision-as-SoT를 기각한 R23 판례("VLM은 배심원")와 정합한다.

### 1.2 왜 "분리"가 메커니즘의 본체인가

패널 반대의견 원장 #1·#2가 이미 지적하듯, silver는 **신호와 오염원이 동시에** 될 수 있다. P5의 분리 규칙은 그 이중성을 구조적으로 봉인한다.

| 경로 | 허용 행위 | 금지 행위 |
|------|-----------|-----------|
| Frontier prompting | 동결 prompt·projection·schema로 독립 투표 → silver 저장 | resolver 대체, geometric SoT, test truth/mutation명 노출 |
| Local student FT | E1.5+handle consensus 통과 silver만 LoRA/P2/P3 weak feature | NC 라벨 혼입, silver를 eval truth로 사용, API teacher를 runtime SoT로 고정 |
| Eval | S/F exact handles + FloorPlanCAD held-out | E1.5·합의·rationale를 success 판정에 사용 |

### 1.3 관련 기법명 (구현에 직접 쓰이는 것)

- **LoRA / QLoRA** (Hu et al.; Dettmers et al. — 요검증): 16GB에서 3–7B open VLM adapter probe의 기본 수단.
- **Pairwise Jaccard / Fleiss·majority consensus**: handle 집합 합의 계측. P5 prereg는 top-tier pairwise Jaccard `≥0.50`, 4/5 합의 coverage `≥0.30`.
- **Calibration metrics REL/RES**: student 확률의 reliability·resolution 하한 (`REL≤0.04`, `RES≥0.02`) — silver confirmation loop를 확률 보정 축에서 죽이기 위함.
- **AUPRC lift vs best non-VLM**: 희소 양성(벽 선분율 ~11.8% CubiCasa; 평행구조 FP 다수)에서 accuracy/F1 단독 보고를 피한다.
- **Name-blind / layer-blind render**: B5에서 탐지기는 레이어명 신호 0(full-vs-nb Pearson 동일 1.0). VLM jury도 vector projection+raster만 보고 이름을 받지 않아야 H3 교차검증 가치가 산다.

### 1.4 이 제안이 *기대지 않는* 것

- Frontier API를 제품 runtime에 넣는 것 (유일 결재 게이트·미승인; 의존은 expected failure mode).
- E1.5 5기를 "5독립"으로 취급하는 것 — 실측상 2어휘 가문(fable+sol vs opus+sonnet+grok). 합의 통계는 **~2-family**로 해석한다.
- 합성팩 B1을 이미 통과한 것으로 가정하는 것 — B1 FAIL(KS 0.5792, TV 0.265). Admission의 B1 게이트는 **E1.5 조문의 B1(well-posed)**이며, 합성 fidelity B1과 식별자가 겹치므로 구현 시 네임스페이스를 `E15_B1` / `SYN_B1`으로 분리한다(반대의견 #1·T10 부수).

---

## 2. 알고리즘 정확 스펙

### 2.1 기호

- 도면(또는 def) \(d\), 핸들 집합 \(H(d)\), 후보 핸들 \(h \in H(d)\).
- Frozen projection: vector IR → (raster crop \(R_d\), handle-aligned overlay \(O_d\), entity manifest without names \(M_d\)).
- Jury \(J = \{j_1,\ldots,j_5\}\) (E1.5 5기; 가문 가중은 §2.4).
- Judge 출력: handle set \(\hat H_{j}(d)\) + rationale schema \(r_j\) (rationale는 학습 타깃 아님·감사 로그 전용).
- Silver label: \(y^\mathrm{sil}(h) \in \{0,1,\emptyset\}\) (∅ = 미합의·제외).
- Student \(f_\theta\): local open VLM(+LoRA) 또는 그 임베딩을 받는 P2/P3 head.
- Truth: \(y^\star(h)\) from S/F resolver or FloorPlanCAD held-out only.

### 2.2 Phase A — Admission gate (frontier 호출 전·E1.5 산출만)

```
INPUT:  e15_metrics = {B1_wellposed, B4_pearson_detector_vs_silver, ...}
PREREG: E15_B1 ≥ 0.70 AND E15_B4 ≥ 0.70
IF fail:
  HALT likelihood_silver_path  # kill: B1/B4 실패 시 likelihood silver 중단
  RECORD reason → dossier/update_log
ELSE:
  OPEN frontier_jury_budget on high-consensus candidates only
```

실측 참고(게이트 *입력*이지 통과 증거가 아님): B5 Pearson 0.2911 — 현재 축은 B4 밴드(0.70)에 미달 가능성이 크다. 즉 **P5의 cheapest 다음 단계는 "API 쓰기"가 아니라 E1.5 B1/B4 재산출·판정**이다.

### 2.3 Phase B — Frozen prompt jury (silver acquisition)

**동결 대상(test 전):** prompt template, judge set, consensus rule, render style family, projection code hash, rationale JSON schema.

```
FOR each drawing d in silver_pool:  # disjoint from train_student and test
  (R, O, M) ← FROZEN_PROJECT(d)   # no layer/block names; no test truth; no mutation family ids
  FOR each judge j in J:
    (Ĥ_j, r_j) ← VLM_j(prompt*, R, O, M)  # independent call; no cross-judge leakage
  # Handle consensus
  FOR each pair (j,k) in top_tier_pairs:  # within-family pairs downweighted; see §2.4
    jac_jk ← |Ĥ_j ∩ Ĥ_k| / |Ĥ_j ∪ Ĥ_k|
  jac_bar ← mean(jac_jk over top-tier pairs)
  cov_4of5 ← fraction of h that appear in ≥4 of 5 Ĥ_j
  IF jac_bar < 0.50:
    REJECT d from handle_silver     # kill local to handle learning
  IF drawing-level cov_4of5 pool < 0.30 after aggregation:
    HALT handle_learning_path
  ELSE:
    FOR h in H(d):
      y_sil(h) ← 1 if count_j(h∈Ĥ_j)≥4 else (0 if count≤1 else ∅)
    STORE silver_record(d, y_sil, jac_bar, rationales_hash)  # silver only
```

**Hallucination 계측 (truth-conditioned, synthetic exact handles에서만):**

\[
\mathrm{HallRate} = \frac{|\{h\in \bigcup_j \hat H_j : h \notin H^\star(d)\}|}{|\bigcup_j \hat H_j|}
\]

Kill: `HallRate > 0.01` on the 100-synthetic probe → 전체 handle 경로 폐기.

### 2.4 Family-aware consensus (2가문 보정)

E1.5 5기 = 2 family. 단순 5/5 다수는 family-correlated error를 과소평가한다.

- Top-tier pairwise Jaccard: **cross-family** 쌍을 우선 top-tier로 정의 (fable/sol 중 1 · opus/sonnet/grok 중 1 이상의 교차쌍). Within-family 쌍은 보조 리포트만.
- Coverage 4/5는 유지하되, 추가 리포트: `cross_family_and` (양 가문 각각 ≥1 찬성) 비율. 학습 승격은 `4/5 AND cross_family_and`를 **기본 옵션 A**, 4/5 only를 **ablation 옵션 B**로 셀에 넣는다.

### 2.5 Phase C — Student learning (local open VLM)

**입력:** silver-admitted \((R_d, O_d, y^\mathrm{sil})\) only; NC FloorPlanCAD/CubiCasa raw labels는 이 경로 가중치에 혼입 금지(별도 counsel·registry — PR-3).  
**모델:** 로컬 실존 `qwen2.5-VL-3B` floorplan SFT/GRPO 체크포인트를 **시작점 후보**로 쓰되, P5 student는 (a) 해당 가중치에서 LoRA를 silver-only로 추가 학습하거나 (b) base 3B에서 silver-only LoRA — 둘을 셀로 분리. NC 계보 체크포인트는 제품 경로와 registry 격리.

**손실 (handle-level):**

\[
\mathcal{L} = \mathbb{E}_{h: y^\mathrm{sil}(h)\neq\emptyset}\big[\mathrm{BCE}(f_\theta(h), y^\mathrm{sil}(h))\big] + \lambda \|\Delta W_\mathrm{LoRA}\|_F^2
\]

∅(미합의) 핸들은 손실에서 제외 (PU/부분라벨). Rationale text는 loss에 넣지 않는다 (사후 합리화 학습 방지).

**하이퍼파라미터 공간 (로컬 probe):**

| 축 | 후보 |
|----|------|
| backbone | Qwen2.5-VL-3B (quantized), 가능 시 7B QLoRA |
| LoRA rank | {8, 16} |
| lr | {1e-4, 5e-5} |
| epochs | {1, 3} (1-epoch가 confirmation-loop 조기 탐지에 유리) |
| λ | {0, 0.01} |
| batch / accum | 5070 Ti 16GB에 맞게 고정 후 seed sweep만 |

DGX: 대형 local open VLM FT만 예약 시간대 — **현재 DGX unreachable**이므로 Phase C full은 PARK until reachable; 로컬 3B LoRA probe는 진행 가능.

### 2.6 Phase D — Independent evaluation (truth only)

```
REQUIRE: disjoint drawing IDs across silver_pool / student_train / test
METRICS on S/F synthetic exact + FloorPlanCAD held-out:
  AUPRC_F(f_θ) ≥ AUPRC_F(best_nonVLM) + 0.03
  REL ≤ 0.04
  RES ≥ 0.02
  lift_CI_low(AUPRC_F student − best_nonVLM) > 0
  HallRate ≤ 0.01   # jury and/or student decoded handles vs exact
OUTPUT: wsd_eval_p5.json
```

`best_nonVLM` 고정 후보(개발 val에서만 선정, test 단발): 기하 탐지기 v1, HistGradientBoosting(6특징; 다이제스트 val F1 0.517 / AUC 0.9215), 및 P2/P3가 봉인한 비-VLM head. Test에서는 선정된 1개 baseline만 비교.

### 2.7 출력 스키마 (구현 계약)

- `silver_records/*.jsonl`: `{drawing_id, judge_id, handles[], rationale_hash, prompt_hash, proj_hash}`
- `consensus_table.parquet`: drawing×handle → votes, y_sil, jac metrics
- `student_ckpt/`: LoRA adapter + `data_lineage.json` (NC방화벽)
- `wsd_eval_p5.json`: prereg bands, CIs, kill flags, seed list

---

## 3. 벽 과업 적응 설계

### 3.1 세 평가 축 접속

| 축 | 자산 | P5에서의 역할 |
|----|------|----------------|
| CubiCasa SEG-IR 벡터 | train 4200 / val 400 / test 400; 벽율 ~11.8%; 라벨=Wall 모서리 | **비-VLM baseline·weak feature 무결성 참조**. P5 student의 주 truth가 아님(사람 라벨 경로와 silver 경로 혼선 방지). val에서 best_nonVLM 선정 가능. |
| FloorPlanCAD 래스터 | 5,308장 + 벽 bbox/segmask (벡터 SVG 없음) | Held-out **raster/handle-proxy truth** for student eval. Jury 입력용 projection 원천. NC counsel(PR-3) 전 제품 가중치 반입 금지. |
| 1.dwg 실도면 | 384 defs; max 412,775 segs | Name-blind jury sanity·연산 병목 프로브. Truth 부족 → metamorphic/B5 독립성 감사 보조만. |
| Synthetic S/F | exact handles | **유일한 닫힌 truth 사슬** for HallRate·calibration·lift CI. 단 SYN_B1 FAIL → curved/hatch/spline 미포함 한계를 eval stratum에 명시. |

### 3.2 전이 실패(0.236)와 GBDT(0.517)를 아는 상태에서 VLM이 가져올 수 있는 것

기하 v1 전이 F1 0.2358은 FP가 Direction/BoundaryPolygon/Door/Window/DimensionMark 등 **대역 내 평행 구조**에 집중됨을 보여준다. GBDT는 같은 6특징으로 P 0.860 / R 0.370 / F1 0.517까지 올린다 — 즉 **로컬 기하 통계만으로도 정밀도는 크게 회복**된다.

P5 student가 *추가로* 가져올 수 있는 기여는 다음에 한정된다.

1. **아이콘·문자·치수 등 비-벽 평행구조의 시각적 배제** — GBDT 특징(parallel/thickness/junction/log길이/sin2θ/cos2θ)이 포착 못 하는 raster context.
2. **단선·해치·곡선 스트라텀** — 합성팩이 LINE/LWPOLYLINE/INSERT뿐이라 기하 prior가 비는 영역(단, SYN_B1 미통과면 이 스트라텀의 synthetic truth 자체가 약함 → FloorPlanCAD·실도면 정성 감사와 병행).
3. **P2/P3 weak feature**: VLM embedding/vote를 GBDT/GNN 입력 채널로만 제공 — SoT 아님.

가져올 수 *없는*/기대하지 말 것: B1 fidelity 공백을 VLM이 메운다는 주장, silver 합의 자체가 벽 의미의 정의가 된다는 주장, API teacher 없는 배포 성능.

### 3.3 역투영·projection 선결 (CL-G / T24)

platt P5·calibration P4와 공유: pixel↔handle exact harness가 synthetic에서 선검증되지 않으면 jury의 handle set는 평가 불능이다. P5는 **CRS/back-projection probe를 Phase B 예산에 포함**하되, 실패 시 CL-G 공통 kill(브리지 병목)을 수용한다.

### 3.4 Prompt/style shift 방어

Render style family를 다양화 후 동결; student eval에 unseen style holdout 1종. Prompt는 단일 frozen string + schema version. Style/prompt drift 발견 시 silver_pool 재취득은 **새 experiment_id**로만 (구 silver와 혼합 학습 금지).

---

## 4. 데이터·컴퓨트 요구

### 4.1 로컬 (RTX 5070 Ti 16GB · RAM 64GB) — 기본 실행면

| 단계 | 작업 | 자원 | 비고 |
|------|------|------|------|
| A0 | E1.5 B1/B4 admission 재산출 | CPU | cheapest; API 0 |
| A1 | Frozen project 100 synth + 50 FPC | CPU | HallRate·calibration |
| A2 | (조건부) Frontier jury 150장 | API 과금 | **미승인 게이트** — 승인 전 dry-run 스텁만 |
| C0 | Qwen2.5-VL-3B QLoRA 1–3 epoch | 16GB | silver subset ≤수k crops |
| D0 | wsd_eval_p5 on S/F + FPC holdout | GPU/CPU | test 단발 |

### 4.2 DGX Spark (Ornith-35B) — 분리 계획

- 현재 **unreachable**(승인은 됨). Vision 지원 여부 미확인(T13) → 확인 전 Ornith를 jury로 가정 금지.
- 도달 시: 7B+ local open VLM FT, 대규모 LoRA sweep만 배치. Frontier API를 DGX가 대체하지는 않음(가문 다양성 목적상 외부 jury는 별도).

### 4.3 데이터 예산 (cheapest → full)

1. **Probe:** 100 synthetic + 50 FloorPlanCAD projection, frozen prompt, hallucination + truth-conditioned calibration.
2. **Silver scale-up (admission 후):** 고합의 후보만 — 전량 5,308 FPC 호출 금지. Coverage 목표 `≥0.30` at 4/5에 필요한 최소 drawing 수만.
3. **Student train:** silver-admitted handles only; drawing 단위로 test/FPC holdout과 중복 0.
4. **Zenodo10K/Text2CAD/ArchCAD/pseudo-floor-plan-12k:** P5 학습 혼입 **NON-GOAL** (도메인·라이선스·라벨 정의 불명). 보유 사실만 기록.

### 4.4 실행 가능성 판정

- 로컬 3B LoRA probe: **가능**.
- Frontier jury: **결재 게이트 대기**.
- DGX full FT: **unreachable로 PARK**.
- 학습 데이터 NC: FloorPlanCAD/CubiCasa 원 도면 권리 **PR-3 미해결** — silver-from-frontier는 NC 라벨을 직접 쓰지 않더라도 원 도면 렌더 권리에 종속 → counsel 클리어 전 Phase B 실도면/FPC 대량 호출은 보류, synthetic-only probe는 진행 가능.

---

## 5. 구현 계획

### 5.1 모듈 골격 (신규는 `wsd_vlm_jury/` 아래만 가정)

```
wsd_vlm_jury/
  project_frozen.py      # IR → raster+overlay+nameless manifest; hash freeze
  jury_client.py         # frontier adapters (stub until approval)
  consensus.py           # Jaccard, 4/5, family-aware gates
  silver_store.py        # jsonl/parquet + lineage
  student_lora.py        # Qwen2.5-VL-3B LoRA train loop
  eval_p5.py             # S/F + FPC → wsd_eval_p5.json
  prereg_p5.json         # bands, kill, seeds (write-once)
```

### 5.2 기존 도구 접속점

| 기존 | 접속 |
|------|------|
| `evidence_grid` / 증거 xlsx 의무 | 셀 결과·kill reason 행 추가 |
| `fast_score` | best_nonVLM 기하 채널·name-blind 대조 |
| `cubicasa_ir` / `cubicasa_ml` | GBDT baseline·특징 6종 재사용; VLM 확률을 7번째 특징으로 넣는 ablation만 P2/P3 경계에서 |
| E1.5 산출물 | Phase A admission 입력 |
| FloorPlanCAD 로컬 래스터 | projection·held-out eval |
| qwen2.5-VL-3B 로컬 가중치 | student init (lineage 태그 필수) |

### 5.3 개발 규모 추정

| 작업 | 규모 | 의존 |
|------|------|------|
| Frozen projection + hash harness | S (1–2일) | P4/T24와 공유 가능 |
| Consensus + silver store | S | E1.5 스키마 |
| Jury client stubs + 1-pass probe | S–M | API 승인 |
| Student LoRA + eval JSON | M (2–4일) | silver_pool |
| Family-aware metrics + REL/RES | S | — |
| **총 (승인·DGX 제외)** | **~1–1.5주 로컬** | PR-1/PR-3/E1.5 게이트에 블로킹 |

### 5.4 시드·봉인

`prereg_p5.json`에 seeds `{0,1,2}`, prompt_hash, judge_set, consensus_rule, split_manifest를 test 전 기록. 이후 변경은 새 실험 ID.

---

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

## 7. red team 티켓 응답

P5/CL-G에 직접 걸리는 OPEN 티켓과 입장.

| 티켓 | 요지 | P5 응답 |
|------|------|---------|
| **T1** 대리 독립성 (sev 0.75) | 합성·외부·metamorphic·silver가 동일 parallel-dual prior 공유 시 편향 증폭 | **수용+완화**: silver는 truth 합산 금지. CL-E 3원 불일치 구조를 P5 eval에 병기. Student 성공은 S/F·FPC 독립 truth에서만 선언. |
| **T2** 생성기 부재 / SYN fidelity | 벽 synthetic truth 미구축·B1 FAIL | **하드 선결 수용**: HallRate·exact handle eval은 PR-1/CL-C 전엔 부분만 가능. SYN_B1 미통과면 P5-D의 synthetic 축을 "제한적"으로 표기하고 FPC holdout 비중 상향 — 단 exact HallRate kill은 synthetic 없이 대체 불가 → **PR-1 완료 전 P5-D 공식 seal 금지**. |
| **T5** NC 라이선스 (0.65) | FloorPlanCAD/CubiCasa 권리 미해결 | **수용**: PR-3 서면 전 FPC/CubiCasa 대량 렌더·학습 가중치 제품 경로 금지. Synthetic-only A0–B 일부만 진행. |
| **T13** Ornith vision | DGX vision 미확인 | **확인 전 비가정**. Jury는 승인된 frontier 또는 로컬 open VLM 명시적 대리(비공식). |
| **T24** CRS / 역투영 | pixel→handle exact 미검증 | **선결 수용**: projection harness 실패=CL-G kill 공유. P5-B에 mapping audit 포함. |
| **T10** (부수) Graph/은닉·게이트 식별자 | silver 게이트 인용 불일치 | **교정 채택**: 원문 prereg 기준 **B1∧B4** (calibration 정확). 구현 식별자 `E15_B1`/`E15_B4`로 SYN_B1과 분리. |
| **T3/T4/T8** E1 법의학 | 계측 아티팩트 시 고가 실험 무용 | **순서 수용**: 프로브 큐상 CL-A가 CL-G 5a보다 앞. P5 API 예산은 CL-A 통과·교차 대조 후에만. |
| **T34** 인용 R-레인 | load-bearing 인용 미실행 | P5 본문 인용은 다이제스트·패널에 한정; 외부 논문은 '요검증'. |
| **반대 #2 / CL-K** | silver=오염 목표 | Cell P5-E로 **실험적 보존**. 오염 증거 시 student 경로 정직히 사망. |

명시적으로 P5가 **해소했다고 주장하지 않는** 티켓: T1, T2, T5 — 위험 인정·게이트로만 관리.

---

## 8. 인접 제안과의 관계

### 8.1 병합 가능 지점

| 인접 | 관계 |
|------|------|
| **platt P5** (CL-G 5a/5b) | 동일 클러스터. platt=배심원 편입+래스터 분할 FT; calibration P5=**jury silver ↔ student 분리 계약·prereg·kill**에 초점. 공유: frozen render, 역투영, NC 방화벽, E1.5 B1∧B4. 병합 시 문서상 "5a prompting / 5b local FT / P5 silver-student contract" 3층으로 표기. |
| **calibration P4** | Dual-view DL·back-projection. P5 projection harness를 P4 CRS 계약에 위임 가능. P4는 raster encoder SoT 금지·handle metric 최종 — P5와 철학 동형. |
| **calibration P2/P3 · CL-F** | Student 산출을 weak feature로 주입(Cell P5-F). P2 lift 밴드는 P1 선결(T22) — P5가 P2를 대체하지 않음. |
| **feyerabend P3 / CL-K** | Anti-silver 통제 arm = Cell P5-E. |
| **feyerabend P5** | "래스터 본선" 프레임은 PARKED; 메커니즘만 CL-G 흡수. P5는 본선 주장 안 함. |
| **doe P6** | Vision 레인 실험 설계와 예산 태그 공유 가능. |

### 8.2 차별점

- P5의 본체는 **모델 아키텍처가 아니라 거버넌스 분리**: prompting=silver acquisition, local FT=student, S/F=truth.
- Prereg에 handle Jaccard·4/5 coverage·HallRate·REL/RES·AUPRC lift를 **동시에** 걸어, 합의 미학만으로 통과 불가.
- 2-family 현실을 family-aware consensus로 명시적 모델링(5독립 환상 거부).

### 8.3 이 제안이 죽어야 하는 조건 (정직)

다음 중 **하나**면 calibration_P5 handle/student 경로를 폐기하거나 PARK한다.

1. `E15_B1 < 0.70` 또는 `E15_B4 < 0.70` (likelihood silver 중단).
2. Top-tier pairwise Jaccard `< 0.50` 또는 4/5 coverage `< 0.30` (handle 학습 중단).
3. Independent truth에서 student lift CI 하한 `≤ 0`.
4. Hallucinated handle rate `> 0.01`.
5. Pixel↔handle bridge / CRS 오류가 선검증 실패 (CL-G 공유 kill).
6. PR-3 NC counsel 거절 — FPC/실도면 기반 경로 불가; synthetic-only로 축소 불가능한 범위면 전체 PARK.
7. Cell P5-E에서 silver-distill ≤ gate-only (오염 증거) — student 경로 사망, audit-only 잔존은 별도 결재.
8. Frontier API 미승인 **그리고** 로컬/Ornith로 가문 다양 jury 구성 실패 — silver acquisition 불가.
9. PR-1 벽 합성 truth 부재가 지속되어 HallRate·exact handle seal이 영구 불가 — 공식 `wsd_eval_p5.json` seal 포기.

---

## 부록 A — 예측 원장 (패킷 필드 이관)

- `claim`: E1.5 admission gate를 통과한 VLM silver로 학습한 local student가 독립 S/F truth에서 비-VLM baseline을 개선한다.
- `forecast`: null
- `score_type`: brier
- `reference_class`: RC-WALL-ZL, n=0, n_min=5
- `base_rate`: none
- `resolution_criterion`: admission·handle consensus·student lift·hallucination·calibration band가 모두 참
- `resolution_trigger`: E1.5 binding 결과와 독립 student evaluation `wsd_eval_p5.json`이 모두 생성될 때
- `update_log`: 2026-07-17 KST 최초 abstain. E1.5 B1/B4/handle band 통과는 상향, 독립 truth 대비 합의 오류와 hallucination은 하향 증거로 사전 약정. 2026-07-18 dossier: B5 Pearson 0.2911·SYN_B1 FAIL·DGX unreachable·API 미승인·NC PR-3를 **하향/블로킹 사전 증거**로 기록(수치 forecast는 계속 abstain).
- `uncertainty_type`: epistemic — E1.5와 truth-conditioned VLM probe로 감소
- `resolution_verdict`: open
- `abstain_flag`: empty_reference_class

## 부록 B — 수치 인용 경계

본 도시에에서 인용한 측정치는 전부 패킷 실측 다이제스트(2026-07-18)에 한정한다: SYN B1 KS 0.5792/TV 0.265, B2/B3/B4/B5 수치, CubiCasa 분할·F1 0.2358·GBDT F1 0.517/AUC 0.9215, E1.5 2가문, 자산 목록. 문헌 기법명 옆의 연도·수치는 일반 지식이며 요검증이다. 신규 벤치마크 수치는 주장하지 않았다.

DOSSIER_COMPLETE: calibration_P5
