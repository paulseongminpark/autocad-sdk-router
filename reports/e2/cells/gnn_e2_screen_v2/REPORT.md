# GNN E2 Screen v2 — Numeric Execution Report

PREREG_SHA256: dfaf641c95cb075f8884d54dc6768935e6421774e0ea5aeb18ece789b453476e
PREREG_CSV_SHA256: 0fb5e462a3c1c5c1d2b48df13764f9f438aebeeb62021646ebe215475eb3be2e
ASSIGNMENT_SHA256: d51463fcfeb7dadf68f34ba69d0e4a56ef5d991a581b04017ceae933ec95acbb

- Completed: 2026-07-19T04:47:04+09:00
- Device route: local RTX 5070 Ti
- Seed: 17 (one run per arm)
- Interpretation boundary: single-seed development probe; no formal claim and no screen verdict is emitted.
- CubiCasa contacts: train SEG-IR 20; val 0; test 0; labels 0.

## Dual preregistration seal

- Both cell-local seals were created and hashed before model execution.
- `load_workspace_dependencies` was not exposed, so the packet-authorized `PREREG.csv` fallback was used; `@oai/artifact-tool` was not loaded and no alternate spreadsheet library was used.

## Design

- Encoder: geometry-only 17-feature input projection plus two typed message-passing layers.
- Arm A: no pretraining, then joint node/pair fine-tuning.
- Arm B: masked-feature reconstruction plus graph contrastive pretraining on 20 unlabeled train graphs, then the same joint fine-tuning.
- Fixed evaluation thresholds: node 0.5, pair 0.5.
- Gen2 family split: train F01–F06 (150 drawings); development F07–F08 (50 drawings); family overlap 0.
- Drawing-ID splitting was not used; development families alone were scored.

## Contact and write-scope record

- Output root: `D:\runs\e2_program\cells\gnn_e2_screen_v2` only; repository files modified 0; existing artifacts modified 0.
- Subagents used: 0; original CAD reads: 0.
- CubiCasa truth/val/test reads: 0/0/0.
- Git invocation attempts: 1; successful operations: 0; mutations: 0.
- Disclosure: Before the packet contents were read, reconnaissance attempted git status --short --branch from the tool-reported workdir. It returned fatal: not a git repository and made no mutation. No git command was issued after the packet prohibition became known.

## Self-test transcript

```text
SELFTEST dual_seal ok=1 prereg_json_sha256=dfaf641c95cb075f8884d54dc6768935e6421774e0ea5aeb18ece789b453476e prereg_csv_sha256=0fb5e462a3c1c5c1d2b48df13764f9f438aebeeb62021646ebe215475eb3be2e
SELFTEST one_step_reproducibility ok=1 loss1=1.515443086624 loss2=1.515443086624 max_parameter_abs_delta=0.000e+00
SELFTEST feature_label_name_guard ok=1 features=17 forbidden_feature_count=0 malicious_rejected=1
SELFTEST oom_batch_downgrade ok=1 simulation_only=1 attempts=8,4,2 selected=2
SELFTEST cubicasa_split_guard ok=1 train_accepted=1 val_rejected=1
SELFTEST family_split_integrity ok=1 assignments_checked=200 train_families=6 development_families=2 family_overlap=0 path_errors=0 assignment_sha256=d51463fcfeb7dadf68f34ba69d0e4a56ef5d991a581b04017ceae933ec95acbb
```

## Graph relationship recovery recheck

- Drawings: 200; families: 8.
- Minimum supported typed relation recall: 1.00000000.
- Wall-handle recall: 1.00000000 (4998/4998).
- Wall-pair parallel-candidate recall: 1.00000000 (2499/2499).
- Unresolved required references: 0.

| Relation | Support | Recovered | Recall |
|---|---:|---:|---:|
| collinearity | 0 | 0 | n/a |
| containment | 1800 | 1800 | 1.00000000 |
| instancing | 23641 | 23641 | 1.00000000 |
| intersection_junction | 3841 | 3841 | 1.00000000 |
| parallel_band | 2499 | 2499 | 1.00000000 |
| proximity | 232 | 232 | 1.00000000 |

## Development metrics

| Arm | Node AUPRC | Node F1 | Pair AUPRC | Pair F1 |
|---|---:|---:|---:|---:|
| A no-pretrain | 1.00000000 | 1.00000000 | 1.00000000 | 0.97974684 |
| B SSL-pretrain | 1.00000000 | 1.00000000 | 1.00000000 | 0.97974684 |
| Frozen B* inference on gen2 dev | 0.76555201 | 0.52921615 | n/a | n/a |

### Read-only comparison references

- Frozen B* source report: mean val AUPRC 0.8311985694, mean F1@0.5 0.7063773452. This is a separate source universe.
- W2-02 2-hop classical reference: val-A mean AUPRC 0.87408233 (0.8741 rounded). Reference only; it does not adjudicate this screen.

### Numeric deltas

| Comparison | Node ΔAUPRC | Node ΔF1 | Pair ΔAUPRC | Pair ΔF1 |
|---|---:|---:|---:|---:|
| B minus A | -0.00000000 | 0.00000000 | 0.00000000 | 0.00000000 |
| B minus frozen B* | 0.23444799 | 0.47078385 | n/a | n/a |

## Arm B inference ablations

ΔAUPRC is full Arm B minus ablation. The 95% interval uses 10,000 paired family-cluster replicates.

| Ablation | Node AUPRC | Node ΔAUPRC | Node CI low | Node CI high | Pair AUPRC | Pair ΔAUPRC | Pair CI low | Pair CI high |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NoMessage | 0.96069035 | 0.03930965 | 0.02612066 | 0.05445049 | 0.97630744 | 0.02369256 | 0.01635217 | 0.02985370 |
| Edge-type shuffle | 0.99417487 | 0.00582513 | 0.00465706 | 0.00602106 | 0.97966760 | 0.02033240 | 0.00268482 | 0.02793071 |

## Training transcript (epoch numeric summaries)

### SSL pretraining

| Epoch | Mean total loss | Steps | Seconds |
|---:|---:|---:|---:|
| 1 | 4.57453310 | 4 | 0.164 |
| 2 | 3.46304089 | 4 | 0.119 |
| 3 | 2.81757480 | 4 | 0.149 |
| 4 | 3.03583199 | 4 | 0.133 |
| 5 | 3.06112134 | 4 | 0.116 |
| 6 | 3.22179341 | 4 | 0.118 |
| 7 | 2.78095865 | 4 | 0.118 |
| 8 | 2.20422432 | 4 | 0.115 |
| 9 | 2.82216036 | 4 | 0.118 |
| 10 | 2.38685536 | 4 | 0.120 |
| 11 | 2.43698859 | 4 | 0.119 |
| 12 | 2.37450314 | 4 | 0.112 |
| 13 | 2.39793447 | 4 | 0.113 |
| 14 | 2.34633663 | 4 | 0.125 |
| 15 | 2.34289694 | 4 | 0.126 |
| 16 | 2.37942839 | 4 | 0.118 |
| 17 | 1.94348487 | 4 | 0.122 |
| 18 | 2.11791527 | 4 | 0.121 |
| 19 | 2.10271800 | 4 | 0.129 |
| 20 | 1.87292430 | 4 | 0.122 |

### Arm A fine-tune

| Epoch | Mean joint loss | Steps | Seconds |
|---:|---:|---:|---:|
| 1 | 0.26855358 | 38 | 0.949 |
| 2 | 0.02911634 | 38 | 0.703 |
| 3 | 0.00741737 | 38 | 0.704 |
| 4 | 0.00080318 | 38 | 0.698 |
| 5 | 0.00041043 | 38 | 0.708 |
| 6 | 0.00026178 | 38 | 0.718 |
| 7 | 0.00018129 | 38 | 0.727 |
| 8 | 0.00012571 | 38 | 0.693 |
| 9 | 0.00009041 | 38 | 0.686 |
| 10 | 0.00006710 | 38 | 0.707 |
| 11 | 0.00005731 | 38 | 0.776 |
| 12 | 0.00005001 | 38 | 0.749 |
| 13 | 0.00004730 | 38 | 0.707 |
| 14 | 0.00003247 | 38 | 0.705 |
| 15 | 0.00002870 | 38 | 0.777 |
| 16 | 0.00002892 | 38 | 0.746 |

### Arm B fine-tune

| Epoch | Mean joint loss | Steps | Seconds |
|---:|---:|---:|---:|
| 1 | 0.26449463 | 38 | 0.695 |
| 2 | 0.01789584 | 38 | 0.675 |
| 3 | 0.00306668 | 38 | 0.688 |
| 4 | 0.00136446 | 38 | 0.704 |
| 5 | 0.00049586 | 38 | 0.682 |
| 6 | 0.00021182 | 38 | 0.702 |
| 7 | 0.00016141 | 38 | 0.703 |
| 8 | 0.00010912 | 38 | 0.737 |
| 9 | 0.00008472 | 38 | 0.699 |
| 10 | 0.00007953 | 38 | 0.769 |
| 11 | 0.00006020 | 38 | 0.790 |
| 12 | 0.00005125 | 38 | 0.716 |
| 13 | 0.00005114 | 38 | 0.710 |
| 14 | 0.00003497 | 38 | 0.729 |
| 15 | 0.00003411 | 38 | 0.697 |
| 16 | 0.00002530 | 38 | 0.704 |

## Compute and OOM record

- Peak sampled process-tree RAM: 2.753132 GiB.
- Peak CUDA allocated: 0.405352 GiB.
- Peak CUDA reserved: 0.496094 GiB.
- End-to-end elapsed: 0.180174 h.
- Prior screen charge: 0.267967 h; cumulative charge: 0.448141 h / 24.0 h.
- Actual CUDA OOM events: 0.
- OOM downgrade record: [].

## Unresolved

- Frozen B* was originally selected on a CubiCasa train-to-val universe; this report keeps that source score separate from read-only bundle inference on the gen2 development common-handle universe.
- The CubiCasa family key available to this cell is a normalized geometry fingerprint; no label, layer name, filename, handle, or family identifier enters the model tensor.
- One seed cannot support a formal variance or adoption claim.
- Both trained arms saturated at node and pair AUPRC 1.0 on the two development families, and B-minus-A is numerically zero at report precision. The family-disjoint split removes the prior drawing-ID leakage, but this small shared-generator development surface does not distinguish SSL initialization or establish real-domain generalization.
- The required ablation bootstrap uses only two development family clusters; its 10,000 resamples quantify this sealed two-cluster surface and are not formal population evidence.

CELL_COMPLETE: gnn_e2_screen_v2
