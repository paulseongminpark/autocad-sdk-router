# F04 artifact freeze — resume execution report

- Scientific status: `BLOCKED_INPUT` (Phase 2 canonical cells); Phase 1 classical_ml artifact `RESOLVED`
- Completion status: `CELL_MEASUREMENT_COMPLETE`
- Local prereg SHA-256: `5955f45ecd0383d984115e5578ce815e2e467b4433b3ab083f4525b88ead3c71`
- Prereg path: `D:/runs/e2_program/cells/f04_artifact_freeze/PREREG_local.json`
- Evidence artifact: `D:/dev/99_tools/autocad-sdk-router/reports/e2/cells/f04_artifact_freeze/evidence.csv`
- Evidence format status: `CSV_FALLBACK_XLSX_LOADER_UNAVAILABLE`
- Measurement telemetry: wall `1.145 s`; peak working set `159.7 MiB` (167,477,248 bytes); Python `3.12.10`
- Numeric provenance: `D:/runs/e2_program/cells/f04_artifact_freeze/measurement.json` (every SHA and cell state below is copied from this run)

## Resume summary

The prior worker was interrupted while assembling this report. Its Phase 1 artifacts survived and were **inherited after SHA verification**, not re-run (takeover rule 2). The unfinished Phase 1 step 3 PREREG seal was completed here, and Phase 2 was executed. No pre-existing `PREREG_local.json` was present, so this is a first seal, not a re-seal.

| Axis | Final state | Basis |
|---|---|---|
| Phase 1 - deterministic_v0 manifest | `BLOCKED_INPUT` | v0 method definition absent from sealed sources; inherited seal |
| Phase 1 - classical_ml frozen model | `RESOLVED` | model frozen (recipe sealed before fit), SHA-verified, PREREG sealed |
| Phase 1 - PREREG seal (step 3) | `RESOLVED` | sealed here before any Phase 2 number |
| Phase 2 - 14 canonical cells (F01-F14) | `UNKNOWN` 14/14 | no admissible measurement; reasons below; nothing imputed |

## Phase 1 - frozen artifact SHA-256 (verified against the sealed manifests)

Each "expected" value is the hash recorded inside the sealed manifest that produced the artifact; "actual" is recomputed here. All six core hashes matched (`all_core_hashes_match = True`).

| Artifact | Bytes | SHA-256 (actual) | Expected source | Match |
|---|---:|---|---|---|
| `hist_gbdt_local6_p2a.joblib` | 472,724 | `ccc52d2066cc44502b2a8ccb0412b6c77d8caca4c37cfbf919bb95e46f16c754` | `model_manifest_local6.json:model_sha256` + `training_execution.json:model_sha256` | True |
| `training_manifest_local6.json` | 5,584 | `bf08b962592cc8f2cb8e3e27b470f088c97177eaa995cd676778badc0cd469b0` | `model_manifest_local6.json:training_manifest_sha256` | True |
| `freeze_train_local6.py` | 10,047 | `5cdf738c433fc22cf785201152da9c716970baa0ad94e36f6f4b9303c1012043` | `training_manifest_local6.json:training_implementation.sha256` | True |
| `train.npz` (train-only input) | 13,370,084 | `8f72d8931c6e08927bf027ee87f1bc5362ab1a85217862e09a0cddd6b0b0d5aa` | `training_manifest_local6.json:train_only_input.sha256` | True |
| `PACKET_f04_artifact_freeze.md` | 2,845 | `4d22e6a15ecc53e6734735cc026fe64c37fc17690a4a121ceae31f807eccc8ad` | `training_manifest_local6.json:packet_sha256` | True |
| `f04_common_judge.py` (judge, unmodified) | 39,722 | `dbfb9fea57aed2c56df02801b3ef42a4eaae7007ae4f046845d5d881a1ee1970` | `f04_canonical_fill/PREREG_local.json:judge.implementation_sha256` | True |

Also registered in the new PREREG (no prior expected hash): `method_manifest_deterministic_v0.json` = `3d94122cd1c2b238874e11cf9c31205e41806f60e0475adc828f0b5148b285b6` (4,699 B); `model_manifest_local6.json` = `ade4b15bb3da868cae69aabf54345c96f2b5daeb33b6a7876cde7ec02f2e86f1` (2,729 B); `training_execution.json` = `29b80b44edd404af07f1f95d3ec9fd113ffdca9dad15a8f9bab3481dd21ce83d` (911 B).

### deterministic_v0 - BLOCKED_INPUT (inherited)

`method_manifest_deterministic_v0.json` records `reconstruction_status: BLOCKED_INPUT`. The sealed sources contain a proposed family label and aggregate v0 comparison numbers, plus a complete executable geometry detector **explicitly identified as v1**; promoting v1 to v0 is a prohibited substitution. Cited manifest sources include `reports/e2/dossiers/doe_P5.md` (requires a DetectorManifest; absent v0 artifacts stay blocked), `tools/e2/w1_real_defs.py` (self-identifies its `score>=0.5` detector as v1), and the S4/S5 folds that repeat scalar `v0_baseline=0.682` without a method definition. Missing: an executable code path bound to v0, the complete v0 rule logic/parameters, a frozen threshold, and v0 code/config SHA-256. Terminally BLOCKED_INPUT.

### classical_ml - frozen six-feature model (RESOLVED)

The recipe was sealed **before** the fit (`freeze_status = FROZEN_BEFORE_TRAINING`, `sealed_before_model_fit = true`), then three seed estimators (17/29/43) were fit on the literal train split only. Introspection of the frozen bundle confirms `feature_order = ['parallel', 'thickness', 'junction', 'log10_len', 'sin2t', 'cos2t']` (exact six-feature schema = True), `decision_threshold = 0.5`, and three `HistGradientBoostingClassifier` estimators each with `n_features_in = 6`. No `predict`/`predict_proba` was called. This is a genuine advance: the classical_ml **artifact precheck is now ELIGIBLE**, where the prior f04_canonical_fill cell had it BLOCKED for lack of any persisted six-feature model.

## Phase 2 - canonical confirmation table (7 relations x 2 CPU families)

| Transform | deterministic_v0 | classical_ml |
|---|---|---|
| `translate` | UNKNOWN (F01; BLOCKED_INPUT) | UNKNOWN (F08; BLOCKED_INPUT) |
| `rotate` | UNKNOWN (F02; BLOCKED_INPUT) | UNKNOWN (F09; BLOCKED_INPUT) |
| `uniform-scale` | UNKNOWN (F03; BLOCKED_INPUT) | UNKNOWN (F10; BLOCKED_INPUT) |
| `unit-change` | UNKNOWN (F04; BLOCKED_INPUT) | UNKNOWN (F11; BLOCKED_INPUT) |
| `block-explode` | UNKNOWN (F05; BLOCKED_INPUT) | UNKNOWN (F12; BLOCKED_INPUT) |
| `layer-rename` | UNKNOWN (F06; BLOCKED_INPUT) | UNKNOWN (F13; BLOCKED_INPUT) |
| `coord-jitter` | UNKNOWN (F07; BLOCKED_INPUT) | UNKNOWN (F14; BLOCKED_INPUT) |

Admissible numeric cells: **0/14**. UNKNOWN cells: **14/14**. Imputed: **0**. No value was coerced to zero, PASS, or a rate. (`gnn` and `vlm` are out of F04 CPU scope and were not touched.)

### Why the cells stay UNKNOWN (differentiated reasons)

- **deterministic_v0 (F01-F07):** artifact precheck `BLOCKED_INPUT` - the exact frozen v0 method manifest is absent and v1 substitution is forbidden. With no method, no downstream gate is reachable.

- **classical_ml (F08-F14):** artifact precheck is now `ELIGIBLE`, but the canonical cells remain `UNKNOWN` because the **common** admissibility gates (`f04_canonical_fill/PREREG_local.json:admissibility_gates.common_required`) cannot be satisfied: transform validity certificate, occurrence-level bijective LID map, prediction schema on a nonempty LID population, repeat normalized-prediction checksum, and sentinel + positive recall >= 0.20. Satisfying these requires **running a detector on transformed synthetic scenes** (`feyerabend_c0/scenes/scene_*_k1.json`). No sealed source contains a synthetic-scene -> six-feature extractor - the training features came from CubiCasa vector data via `tools/e2/ext/cubicasa_ml.py`, a different domain - so scoring these scenes would require inventing an unsealed feature-extraction + LID + certificate pipeline. That is prohibited invention. Two independent sealed guards enforce the same stop:
  - `f04_common_judge.py` (judge of record, unmodified) is fold-only: `build_canonical_matrix` emits UNKNOWN for every cell and its only numeric inputs are two hardcoded legacy folds; no code path consumes a frozen model.
  - `f04_canonical_fill.py` is hard-sealed to the zero-eligible path: its classical-model discovery list is hardcoded and **does not include** this frozen model (verified: `model_in_sealed_harness_candidate_list = False`), and it raises if a family becomes eligible, mandating a **fresh preregistration** (`zero_eligible_stop_rule`) rather than an edit.

  Filling F08-F14 therefore requires a new, properly sealed measurement preregistration + pipeline, outside this packet's frozen-source-confirmable scope. Marking them `UNKNOWN` with this reason is the honest disposition.

## Judge bands (sealed `f04_common_judge.py`, unmodified)

- PASS `R-META <= 0.02` / INCONCLUSIVE `0.02 < R-META <= 0.10` / FAIL `R-META > 0.10` / UNKNOWN = no admissible numeric measurement (never coerced).
- Boundary self-test: `PASS` on 6 fixed fixtures via `importlib` of the sealed judge; judge SHA-256 matches the sealed value and was not modified.

## Boundaries and prohibition audit

All counters are zero for this run: estimator_predict_calls `0`, git_mutation_commands `0`, gnn_family_executions `0`, judge_modifications `0`, model_api_calls `0`, original_cad_reads `0`, original_cad_writes `0`, subagents `0`, test_set_reads `0`, valb_reads `0`, vlm_family_executions `0`. Surviving Phase 1 artifacts were read-only inherited; the only new writes are this cell's PREREG, measurement, cell tables, and this report.

## Files

- Raw: `D:/runs/e2_program/cells/f04_artifact_freeze/{PREREG_local.json, measurement.json, canonical_cells.csv, spreadsheet_status.json, measure_f04_artifact_freeze.py, emit_report.py}` plus inherited `{hist_gbdt_local6_p2a.joblib, training_manifest_local6.json, model_manifest_local6.json, training_execution.json, freeze_train_local6.py, method_manifest_deterministic_v0.json}`
- Report: `D:/dev/99_tools/autocad-sdk-router/reports/e2/cells/f04_artifact_freeze/{REPORT.md, evidence.csv}`

CELL_MEASUREMENT_COMPLETE
