# W3 M-2 GNN AND-gate sealed measurement report

> W3-BOUNDARY: "본 보고의 탐지기 사다리·모든 val-A/val-B 수치의 유효 범위는 CubiCasa SEG-IR 우주 한정이다. E1 실무 도면 전이는 미검증이다."

## Seal and artifact hashes

- `PREREG_local.json` SHA-256: `7b73cb451cc582d4c605d5fe09f43734e4d70cd68c8024f5f455e638355d0aa3`
- `PREREG.csv` SHA-256: `b5253e736506277fbc163fe1c9416d93fa5ca3993c0713d9a1f4350839f129ef`
- `measurement.json` SHA-256: `dbe809729b3f57e25938120429ff4d9e45a63e81eaf581b2eab653523de4a756`
- `evidence.csv` SHA-256: `016d857b78ca5f9fbc2c848f19b442277eb895c9ccb4936f216b07df1b2fa22f` (canonical evidence)
- `run_measurement.py` SHA-256: `337e201943370d98f3bd22fec8b049a6b77b44a1e93146737c63c8ba03601eda`
- Seal order: both prereg artifacts were written and SHA-256 sealed before this numeric run.

## Telemetry

- wall_seconds: `98.83335430000443`
- peak_rss_bytes: `1390432256`
- peak_vram_bytes: `52428800`
- device: `NVIDIA GeForce RTX 5070 Ti`
- budget_charge: `{"cap": 8.0, "status": "PASS", "unit": "RTX-hour", "value": 0.027453709527779008}`

## Fixed-order definition discovery

- **S-node F1 — DISCOVERED.** Sealed sources define one graph per drawing with segment nodes, positive truth as membership in `truth.wall_handles_flat`, pooled val-A per-handle F1 at fixed probability threshold 0.5, and arithmetic mean across seeds 17/29/43.
- **S-pair F1 — BLOCKED_INPUT.** Only the `>=0.80` band text was discoverable. No candidate-pair universe, pair truth rule, scorer, decision threshold, pooling unit, or seed aggregation was sealed. No value was invented.
- **true style-OOD drop — BLOCKED_INPUT.** The calibration source explicitly says its available source-category slices are IID and that true OOD belongs to a future preregistration. No value was invented.

## Band verdicts

| Band | Statistic | Sealed threshold | Verdict |
|---|---:|---:|---|
| S-node F1 | 0.86999471 (population SD 0.00311698) | >= 0.92 | **FAIL** |
| S-pair F1 | N/A | >= 0.80 | **BLOCKED_INPUT** |
| true style-OOD drop | N/A | <= 0.10 | **BLOCKED_INPUT** |
| Three-band AND | — | all three | **FAIL** |

### S-node per-seed evidence

| Seed | F1 | Precision | Recall | TP | FP | FN | TN |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 17 | 0.86574571 | 0.76991889 | 0.98881740 | 19365 | 5787 | 219 | 142185 |
| 29 | 0.87313551 | 0.78416067 | 0.98488562 | 19288 | 5309 | 296 | 142663 |
| 43 | 0.87110290 | 0.77938568 | 0.98728554 | 19335 | 5473 | 249 | 142499 |

## Lineage and boundary precheck

- `gnn_formal.py`: `0413f1035de76ab8a175c37c291c3fca634a2f1effb8135b5371aa357d5a94c0` — PASS
- `graph_builder.py`: `c95d4a30d30e0db157fe56102053a7884902b7749464f7f4cb8852c0819321f6` — PASS
- GraphConfig digest: `56911f4633979a3fe00fd56be2d0a39ac06757ed255ed49ed18ca20ba9d4ac49` — PASS
- split manifest content SHA-256 binding: `5e16541d7191ad01c57a9cee72172f63112ed68590dd371aff5bf0aaaab8e07b`
- split manifest file SHA-256: `8aad64eeda77df55296fc711c21d7befdeada7fe379aeafec81fd1691aea044f` — PASS
- val-A drawing-list SHA-256: `4905890378c4dc3958bcd04876dd4e78f9c8cba0d1511b7c23117b8f12f6a6f7` — PASS
- Split semantics parsed: `frozen.splits.A prefix only`; parser stopped at byte offset `10246` before the B object.
- val-B drawing-list reads: `0`; val-B drawing reads: `0`; test reads: `0`.
- Relative-path count: `0`.

## Checkpoints

- seed 17: `D:\runs\e2_program\cells\gnn_formal\ckpt\GNN_A_no_pretrain_seed_17.pt` SHA-256 `612e4bf954ff5967853f7a08e66195b79dfa15250d6e9d42f88a877c92a3952c`
- seed 29: `D:\runs\e2_program\cells\gnn_formal\ckpt\GNN_A_no_pretrain_seed_29.pt` SHA-256 `1b4bbd004491609cfe8cfc217d18b0ec5ff344f8fee43c67b392a4c37dbc6877`
- seed 43: `D:\runs\e2_program\cells\gnn_formal\ckpt\GNN_A_no_pretrain_seed_43.pt` SHA-256 `ab37cf25894e8ed7f2e96ca287a21da961c68d37bcf2bd9633ae1cb9b663e2a3`

## Adjudication

The preregistered AND rule is: FAIL if any band is FAIL; otherwise BLOCKED_INPUT if any band is BLOCKED_INPUT; otherwise PASS. S-node is below its immutable threshold, so the final AND verdict is FAIL even though the other two bands remain honestly BLOCKED_INPUT. No threshold relaxation, alternate pair proxy, or IID-style substitute was attempted.

CELL_COMPLETE: w3_m2_gnn_andgate
