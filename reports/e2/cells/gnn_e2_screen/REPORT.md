# GNN E2 Screen — Blocked Family-Split Record

- Recorded: 2026-07-19T03:16:35+09:00
- Status: blocked before any further experimental rerun.
- No formal claim and no screen verdict is emitted.

## Blocking condition

The supplied 150-drawing gen2 pack collapses to one canonical synthetic wall template family. Calibration P3 section 6.1 requires the template and all parameter variants to remain in one fold, so a family-disjoint train/development split cannot be formed from this pack.

- Drawings audited: 150.
- Seed variants per tier: 50.
- Tier variants: 3.
- Shared w01–w08 core signatures: 1.
- Canonical synthetic template families: 1.
- Family-disjoint train/development split available: 0.

| Tier | Drawings | Exact truth templates | Core signatures | Wall IDs |
|---|---:|---:|---:|---|
| S | 50 | 1 | 1 | w01, w02, w03, w04, w05, w06, w07, w08 |
| F | 50 | 1 | 1 | w01, w02, w03, w04, w05, w06, w07, w08, w09 |
| M | 50 | 1 | 1 | w01, w02, w03, w04, w05, w06, w07, w08, w09, w10 |

## Valid builder evidence retained

- Frozen-config graphs built: 150.
- Minimum supported typed relation recall: 1.00000000.
- Wall-handle recall: 1.00000000 (2700/2700).
- Wall-pair candidate recall: 1.00000000 (1350/1350).
- Unresolved required references: 0.

| Relation | Support | Recovered | Recall |
|---|---:|---:|---:|
| collinearity | 450 | 450 | 1.00000000 |
| containment | 1350 | 1350 | 1.00000000 |
| instancing | 17700 | 17700 | 1.00000000 |
| intersection_junction | 950 | 950 | 1.00000000 |
| parallel_band | 1350 | 1350 | 1.00000000 |
| proximity | 150 | 150 | 1.00000000 |

## Invalidated diagnostic run

The following numbers came from a drawing-ID 40/10 split that crossed the single template family. They are preserved for debugging only and are not development evidence.

| Arm | Node AUPRC | Node F1 | Pair AUPRC | Pair F1 |
|---|---:|---:|---:|---:|
| A no-pretrain | 1.00000000 | 1.00000000 | 1.00000000 | 1.00000000 |
| B SSL-pretrain | 1.00000000 | 1.00000000 | 1.00000000 | 1.00000000 |

- Diagnostic authority: invalidated; family leakage across folds.
- Checkpoints: retained under `ckpt/invalidated_drawing_id_split/` and must not be promoted.

## Self-test transcript

```text
SELFTEST one_step_reproducibility ok=1 loss1=1.515443086624 loss2=1.515443086624 max_parameter_abs_delta=0.000e+00
SELFTEST feature_label_name_guard ok=1 features=17 forbidden_feature_count=0 malicious_rejected=1
SELFTEST oom_batch_downgrade ok=1 simulation_only=1 attempts=8,4,2 selected=2
SELFTEST cubicasa_split_guard ok=1 train_accepted=1 val_rejected=1
```

## Input-contact and compute record

- CubiCasa train SEG-IR selected: 20.
- CubiCasa truth/val/test contacts: 0/0/0.
- Original CAD contacts: 0.
- Conservative cumulative executor wall time across failed/invalidated attempts: 0.267967 h.
- Maximum observed CUDA allocation: 0.405455 GiB.
- Maximum observed sampled RAM: 2.461281 GiB.
- Actual CUDA OOM events: 0.

## Evidence workbook

- `evidence.xlsx` was not created because the required `load_workspace_dependencies` capability is unavailable in this executor.
- The mandated `@oai/artifact-tool` runtime could not be loaded; no alternate spreadsheet library was used.

## Required unblock

Provide at least two genuinely distinct synthetic template families with family metadata (the calibration cell called for a much broader synthetic block set), then rerun seed 17 once on a family-disjoint split. The current sealed screen truth table remains unapplied.

CELL_BLOCKED: gnn_e2_screen
