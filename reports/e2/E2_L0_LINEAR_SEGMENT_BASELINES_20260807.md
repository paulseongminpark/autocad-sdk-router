상태: **PARTIAL_PASS**

# E2 L0 선형 segment baseline 보고서

## 결론

원본 DWG를 보존한 채 한 도면의 owner-labeled segment를 대상으로 첫 정직한 baseline을 만들었다. native 표시 판정은 첫 실행의 `DEGENERATE_WORLD_TARGET`(INSERT transform 아래 target segment가 퇴화) 실패를 수정한 뒤 `PASS`가 되었고, population은 `PASS_WITH_DEFERRAL`, 세 frozen model arm의 종합 상태는 `PARTIAL_PASS`다.

Rules, GBDT, GNN은 fine-tune 없이 실제 7,430개 ID를 모두 점수화했다. 반면 SymPointV2, VecFormer, Graph Transformer/GraphGPS는 E2 task 계약으로 즉시 실행할 수 없어 `BLOCKED`다. 이번 결과의 낮은 점수는 모델 불가능성의 증거가 아니다. WorldIR/native 모집단 차이, 한 도면의 합의 라벨, CubiCasa supervision 의존성, 낮은 양성률이 함께 있는 진단용 동결 전이 결과다.

## 1. 범위와 원본 무결성

- 원본: `D:\runs\e2_program\l0_gold_1dwg\l0_gold.dwg`
- SHA-256: `14eb65eb292d8a07f38ab5662dcafe9761c6185bc5ff0c8a9a008be15b598961`
- 평가 단위: `xclip_visible_linear_segment_instance`
- 도면 수: 1
- claim boundary: 한 owner-labeled drawing의 segment-level frozen transfer만 주장한다. object PQ, junction/room-cycle, 도면 간·회사 간 일반화는 주장하지 않는다(`baselines_20260807_v2\model_arm_receipt.json`, field `claim_boundary`).

population receipt는 원본 before/after SHA가 모두 위 값이고 `unchanged: true`임을 기록한다(`population_20260807_v2\detector_population_receipt.json`, fields `source.sha256_before`, `source.sha256_after`, `source.unchanged`). 두 v2 guard도 같은 source path, SHA, file identity를 preflight/postflight에서 확인했다(`population_guard_20260807_v2.json`, `baseline_guard_20260807_v2.json`, fields `evidence_binding.source_path`, `evidence_binding.source_sha256`, `evidence_binding.source_snapshot_stable`, `pre_spawn_validation.source_matches_preflight`, `post_execution_validation.source_matches_preflight`). native만 staged DWG를 사용했고, baseline은 native/WorldIR에서 만든 파생 JSON을 읽었다. baseline guard는 원본 DWG를 read-only source binding과 pre/post 무결성 검증 대상으로만 묶었다.

## 2. native 판정과 정확한 재현 명령

첫 native 실행은 다음으로 종료했다.

```text
operation=e2.inspect.xclip_membership
error_code=DEGENERATE_WORLD_TARGET
error=a target segment collapsed under INSERT transforms
```

수정된 정본은 `D:\runs\e2_program\l0_detector_baseline\native_linear_20260807_v2\display_membership_receipt.json`이다. receipt fields `status=PASS`, `execution_context=dedicated_full_autocad`, `geometry_scope=linear_segments_v1`, `native_visible_source_segments=7512`를 기록한다. fields `original_sha256_before`, `original_sha256_after`, `original_unchanged`도 원본 불변을 보인다. 같은 receipt의 `degraded: true`는 숨기지 않는다. 여기의 PASS는 native membership operation의 receipt-level PASS이고, 전체 실험 상태를 PASS로 올리는 근거는 아니다.

가드가 저장한 실제 argv와 terminal 증거는 다음과 같다.

```text
python -X utf8 tools/e2/build_l0_detector_population.py --native-graph D:\runs\e2_program\l0_gold_1dwg\runs\l0_step1_probe_rich\dwg_graph_ir.json --source-dwg D:\runs\e2_program\l0_gold_1dwg\l0_gold.dwg --full-linear-oracle D:\runs\e2_program\l0_detector_baseline\native_linear_20260807_v2\target_population_oracle.json --positive-oracle D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\target_population_oracle.json --label-contract D:\runs\e2_program\l0_gold_1dwg\SPEC.md --out-dir D:\runs\e2_program\l0_detector_baseline\population_20260807_v2
```

`population_guard_20260807_v2.json`의 fields `command`, `command_exit_code=0`, `terminal_state=AUTHORIZED_SUCCESS`, `execution_outcome=COMMAND_SUCCEEDED`가 이를 고정한다.

```text
python -X utf8 tools/e2/run_l0_segment_baselines.py --population-receipt D:\runs\e2_program\l0_detector_baseline\population_20260807_v2\detector_population_receipt.json --model-input D:\runs\e2_program\l0_detector_baseline\population_20260807_v2\detector_input.seg.json --truth D:\runs\e2_program\l0_detector_baseline\population_20260807_v2\detector_truth.json --transfer-harness D:\runs\e2_program\w4\cells\a4_transfer\a4_transfer.py --out-dir D:\runs\e2_program\l0_detector_baseline\baselines_20260807_v2
```

`baseline_guard_20260807_v2.json`의 fields `command`, `command_exit_code=0`, `terminal_state=AUTHORIZED_SUCCESS`, `execution_outcome=COMMAND_SUCCEEDED`가 이를 고정한다.

## 3. 모집단과 입력 계약

| 항목 | 수 |
|---|---:|
| WorldIR visible all kinds | 10,271 |
| WorldIR linear candidates | 9,351 |
| native visible linear candidates | 7,512 |
| exact native/WorldIR consensus | 7,430 |
| WorldIR-only raw | 1,921 |
| native-only | 82 |
| excluded arc chords | 920 |
| positive wall oracle | 241 |
| negative | 7,189 |

근거는 `population_20260807_v2\detector_population_receipt.json`의 fields `disputed_segments.native_only_count`, `disputed_segments.worldir_only_count`, `disputed_segments.policy`, `excluded_arc_chords`, `native_visible_linear_candidates`, `qualified_linear_candidates`, `positive_segments`, `negative_segments`, `worldir_visible_linear_candidates`, `status`다. `9,351-1,921=7,430`이고 `7,512-82=7,430`이다. 모델 population은 raw union이 아니라 exact consensus이며 disputed ID는 inference 전에 quarantine되었다. receipt의 상태가 `PASS_WITH_DEFERRAL`인 이유다.

`D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\model_input\display_model_input.json`은 `schema=ariadne.e2.model_input_population.v1`, `population_exact=true`, `xclip_applied=true`이고 parsed `segments.count=241`이다. 이는 display positive oracle의 241-segment 입력이며 repo baseline adapter가 직접 먹은 파일이 아니다. 실제 baseline은 `population_20260807_v2\detector_input.seg.json`을 읽었고, population receipt의 `exact_seg_ir_v1=true`가 이 입력이 exact `seg.v1` 계약임을 나타낸다. 세 arm의 `input_segment_ids=7430`, missing/extra ID=0은 `baselines_20260807_v2\model_arm_receipt.json`의 `executed_arms.*` fields에 있다. 따라서 “241 display input을 세 baseline이 그대로 받았다”고 말할 수 없다.

입력 누출 방어도 `population_20260807_v2\detector_population_receipt.json`의 `layer_leakage_guard` fields에 고정되어 있다. `source_layer_fields=0`, `wall_layer_name_occurrences=0`, `blank_layer_count=7430`, `unknown_label_count=7430`, `exact_seg_ir_v1=true`다. 즉 source layer명, 벽 레이어명, label cue는 모델 입력에 없다. 실행된 baseline 계약은 `baselines_20260807_v2\model_arm_receipt.json`의 `model_input_diagnostics` fields에 있는 graph 17 features, GBDT 12 features, graph edges 86,792다.

## 4. 세 frozen arm의 수치

양성 prevalence는 `241/7430 = 0.03243606998654105`다. threshold `0.5`는 이 도면에 맞춰 튜닝하지 않은 **고정 진단 운용점**이다.

| arm | AP | PR-AUC | TP / FP / FN / TN @ 0.5 | precision / recall / F1 |
|---|---:|---:|---:|---:|
| Rules | 0.0347858913941951 | 0.033565566392345314 | 1 / 148 / 240 / 7041 | 0.0067114094 / 0.0041493776 / 0.0051282051 |
| GBDT | 0.09120953320362332 | 0.089615549265129 | 27 / 140 / 214 / 7049 | 0.1616766467 / 0.1120331950 / 0.1323529412 |
| GNN | 0.09020507732184094 | 0.08919834100725822 | 82 / 520 / 159 / 6669 | 0.1362126246 / 0.3402489627 / 0.1945432977 |

정본 수치는 `D:\runs\e2_program\l0_detector_baseline\baselines_20260807_v2\segment_metrics.json`의 `arms.gbdt`, `arms.gnn`, `arms.rules`, top-level `positive_count`, `negative_count`, `drawing_count`, `evaluation_unit`, `independence_warning` fields에 있다. AP/prevalence lift는 Rules `1.0724x`, GBDT `2.8120x`, GNN `2.7810x`다. GBDT와 GNN의 AP 차이는 약 `0.001`이고 도면 수가 `n=1`이므로 어느 쪽이 우월하다는 증거가 아니다. GNN은 recall이 가장 높지만 FP도 가장 많다. GBDT와 GNN은 구조가 달라도 CubiCasa supervision을 공유하므로 독립적인 두 learned witness가 아니다(`baselines_20260807_v2\model_arm_receipt.json`, fields `artifact_integrity.dependence_groups`, `artifact_integrity.warning`). Rules는 **실행 계약상** `deterministic_geometry` dependence group으로 분류될 뿐이다. threshold를 CubiCasa train 4,200 drawings에서 컴파일했으므로 corpus-epistemically 독립적인 human prior라고 과장할 수 없다.

Rules는 `evidence_grid`가 아니라 실제 sealed A4 16-rule library다. `D:\runs\e2_program\cells\onto_real1\rules_library.py`는 17-dim graph 입력, fixed no-learning weighted score, CubiCasa train 4,200 drawings provenance, A/B/C/D 네 범주 4개씩 총 16개 rule을 명시한다. 실행 receipt의 `artifact_integrity.checks.rules_library_py`가 같은 파일 SHA를 검증한다.

## 5. 차단된 neural arm과 정확한 결손

| arm | 확인된 자산 | 즉시 E2 실행 판정 |
|---|---|---|
| SymPointV2 | code와 `D:\runs\e2_program\w5\refs\models\SymPointV2\weights.pth` 존재 | **BLOCKED**: 35-class semantic/instance checkpoint이고 wall은 class 33이지만 E2 wall-binary SEG-IR adapter, nested checkpoint extraction, qualified legacy CUDA runtime이 없다. `SEMANTIC35_ADAPTER_AND_RUNTIME_UNQUALIFIED` (`baselines_20260807_v2\model_arm_receipt.json`, `blocked_arms.sympointv2`). |
| VecFormer | local training/inference code 존재, checkpoint-like file 0개 | **BLOCKED**: released/frozen task checkpoint와 prepared FloorPlanCAD input이 없다. `TASK_CHECKPOINT_ABSENT` (`baselines_20260807_v2\model_arm_receipt.json`, `blocked_arms.vecformer`). |
| Graph Transformer/GraphGPS | qualified L0 executable arm 없음 | **BLOCKED**: E2 task checkpoint와 input contract가 없다. `code_present=false`, `task_weights_present=false`, `NO_E2_TASK_CHECKPOINT_OR_INPUT_CONTRACT` (`baselines_20260807_v2\model_arm_receipt.json`, `blocked_arms.graph_transformer`). |

SymPointV2가 벽 이진 분류를 직접 지원한다고 할 수 없다. config는 `in_channels: 10`, `semantic_classes: 35`를 요구하고(`SymPointV2\configs\svg\svg_pointT.yaml`, fields `model.in_channels`, `model.semantic_classes`), category table의 id 33이 wall이라는 것뿐이다(`gen_coco_det.py`, category `id=33`). inference entrypoint는 config/checkpoint/datadir를 받고 `SVGDataset.load(..._s2.json)`의 coords, feats, labels, lengths, layerIds를 CUDA로 처리한다(`SymPointV2\tools\inference.py`, entrypoint arguments and `SVGDataset.load` call). 241 또는 7,430 SEG-IR segment를 이 계약으로 바꾸는 qualified adapter와 35-to-binary task mapping이 없으므로, class 33의 존재를 즉시 E2 벽 분류 지원으로 확대하면 안 된다.

Fine-tune 없이 지금 smoke 가능한 것은 Rules/GBDT/GNN이다. SymPointV2는 기존 weight가 있으므로 adapter/runtime을 새로 자격화한 뒤 fine-tune 없이 별도 transfer smoke가 가능한지는 아직 미측정이다. VecFormer와 GraphGPS는 task checkpoint가 없어 checkpoint 확보 또는 새 학습 없이는 smoke가 불가능하다. 없는 결과나 GPU 실행 성공을 추측하지 않는다. VecFormer의 local README는 Python 3.9, torch 2.5.1/cu118, torch-scatter, flash-attention, FloorPlanCAD 전처리를 요구하고(`VecFormer\README.md`, environment/data-preparation sections), local LICENSE는 Apache 2.0이다.

## 6. 모집단 불일치: 1,847 known scope + 156 unresolved

WorldIR-only 1,921개를 모두 진짜 오류로 세지 않는다. 아래 1,754/93 분해는 detector population receipt의 직접 field가 아니다. native graph, WorldIR output, native/full-linear oracle, display oracle을 stable ID로 read-only join하고 entity type, bulge, native linear support를 세어 만든 derived audit이며, 이 보고서 자체가 그 derived audit 기록이다. receipt는 raw total과 oracle counts를 제공하고, 재현 논리는 `WorldIR-only` stable-ID set을 만든 뒤 known curve/unsupported categories를 분리하고 남은 ID를 native-only set과 합치는 것이다.

```text
raw WorldIR-only                                      1,921
  visible nonzero-bulge LWPOLYLINE scope difference  1,754
  visible POLYLINE unsupported scope difference         93
known scope difference                                1,847
remaining straight candidates (1,921-1,847)             74
native-only                                              82
unresolved disputed IDs (74+82)                         156
```

현재 WorldIR straight-chord 경로는 visible nonzero-bulge LWPOLYLINE 1,754개를 linear 후보처럼 다루지만 native linear scope는 제외한다. visible POLYLINE 93개도 native linear scope에서 지원되지 않는다. 그러므로 2,003 union 전체를 genuine labeling error라고 부르면 안 된다. 1,847개는 알려진 scope 차이이고, 74 WorldIR-only straight candidate와 82 native-only만 XCLIP/degenerate ordinal/display membership 불일치로 남은 156개다. raw count의 근거는 `population_20260807_v2\detector_population_receipt.json` fields `disputed_segments.*`, `native_visible_linear_candidates`, `qualified_linear_candidates`, `worldir_visible_linear_candidates`이고, 1,754/93/74/156은 위 stable-ID derived audit의 결과다.

합의 subset 선택은 metric을 편향시킬 수 있다. disputed ID를 모델 전에 제거했기 때문에 현재 수치는 전체 visible geometry가 아니라 7,430 exact consensus에서의 수치다. 편향 방향은 한 도면에서 결정할 수 없다.

## 7. 해석, 한계, 다음 실험

Rules의 TP 1, GBDT의 낮은 recall, GNN의 높은 recall과 520 FP는 이 도면과 이 population에서의 진단 결과다. 3.24% prevalence에서는 FP 수백 개가 precision을 크게 낮춘다. 따라서 낮은 AP/F1을 모델 불가능성으로 해석하지 않는다. 또한 GBDT/GNN shared CubiCasa supervision 때문에 learned 결과를 독립 증언으로 합산하지 않는다.

다음 실험은 다음 순서로 한다.

1. 여러 실시도면을 모아 **도면 단위 owner-style adaptation train/validation split**을 만든다. segment random split으로 같은 owner style이 양쪽에 새지 않게 한다.
2. 현재 model input은 이미 layer/label cue가 0이므로 layer strip intervention은 no-op이다. 먼저 geometry/native display membership을 유지한 rotation, translation, consistent unit-scale, segment split intervention invariance를 측정한다. 별도로 display-membership XCLIP, nested transform, bulge, unsupported POLYLINE 변화도 분리한다.
3. 현재 도면은 결과를 이미 봤으므로 sealed/final holdout이 될 수 없다. 이 도면과 threshold 0.5는 **고정 공개 회귀 benchmark**로 보존하고 adaptation model selection 근거로 쓰지 않는다. 진짜 holdout은 아직 열지 않은 새 실시도면이어야 한다.
4. 새 held-out drawings마다 native display oracle과 WorldIR scope ledger를 먼저 만들고, known scope와 unresolved disagreement를 분리한 뒤 AP/PR-AUC와 고정 운용점 confusion을 보고한다.
5. 그 후 SymPointV2 adapter/runtime, VecFormer checkpoint/input, GraphGPS executable/checkpoint/input contract를 각각 qualification한다. 조건이 충족되기 전에는 차단 arm에 숫자를 넣지 않는다.

## 8. v2 정본 아티팩트와 hash

- population receipt: `D:\runs\e2_program\l0_detector_baseline\population_20260807_v2\detector_population_receipt.json`, status `PASS_WITH_DEFERRAL`; model input SHA `4dabdf7b9fb7197930004556ac7c0a4dfcfd2f1682e762fdefef9ed2f4ceb902`, truth SHA `47f66145e2e1bc0c1d790570fa7468e8c51d71d202a385529e6b12b62acd9ab6` (fields `artifacts.model_input`, `artifacts.truth`, `status`).
- population guard: `D:\runs\e2_program\l0_detector_baseline\population_guard_20260807_v2.json`, status `READY`, source/probe stable, command authorized (fields `qualification.status`, `evidence_binding`, `command`, `terminal_state`).
- baseline receipt: `D:\runs\e2_program\l0_detector_baseline\baselines_20260807_v2\model_arm_receipt.json`, status `PARTIAL_PASS`; implementation hashes include baseline runner `e398e14248f9bc35bcbbddbf50b74358d2cc755f52ce58e57bee240b1799a9e1` and frozen jury adapter `dbf5f01b76788e66e6485ee59eb84b579ddb63c033cd57d3339290a7eea29a06` (fields `implementation.baseline_runner`, `implementation.frozen_jury_adapter`).
- baseline guard: `D:\runs\e2_program\l0_detector_baseline\baseline_guard_20260807_v2.json`, status `READY`, command authorized (fields `qualification.status`, `evidence_binding`, `command`, `terminal_state`).
- metrics: `D:\runs\e2_program\l0_detector_baseline\baselines_20260807_v2\segment_metrics.json`, SHA `a584936b4c479fd41afb1625d351ab5896fd752daea87f6eb959aa50beadab15` (`model_arm_receipt.json`, field `metrics`).
- predictions: `D:\runs\e2_program\l0_detector_baseline\baselines_20260807_v2\baseline_predictions.json`, SHA `5a270237cd62a6861c9a8286cd88888dc0353c256384caa9bd96234919f4f693` (`model_arm_receipt.json`, field `predictions`).

v2 model input/truth/prediction SHA는 이전 실행과 동일했고, v2 영수증은 구현 코드 SHA까지 포함한다. 이 보고서의 성능은 그 v2 정본 아티팩트와 고정 threshold에서만 재현·해석해야 한다.
