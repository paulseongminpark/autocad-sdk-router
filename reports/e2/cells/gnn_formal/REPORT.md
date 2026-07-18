# GNN formal numeric report

- prereg.json SHA-256: `53d10948a0e56f98cab77dfb962d8db5b6ccdbc639a962ff7327bbe4878bcaca`
- PREREG.csv SHA-256: `34dfdd6ec179d8fabfd211d3c78c1c67bbb5e45b1ca483fa69c2190a201ce476`
- gnn_formal.py SHA-256: `0413f1035de76ab8a175c37c291c3fca634a2f1effb8135b5371aa357d5a94c0`
- completed UTC: `2026-07-18T22:36:14+00:00`
- Output boundary: numeric measurements and unresolved items only; no adoption/rejection adjudication is emitted.

## Design

- Universe: 4,200 CubiCasa train drawings -> 198 W2-09 manifest-listed val-A drawings.
- Graph: frozen GraphConfig, one drawing per graph, segment nodes, 17 numeric allowlisted features, two typed message-passing layers.
- Arms: GNN-A no-pretrain; GNN-B masked+contrastive SSL then identical fine-tune; W2-02 full 2-hop HistGBDT freshly refit train-only.
- Seeds: 17, 29, 43. Threshold: 0.5. Bootstrap: 10,000 paired W2-09 family-cluster resamples, seed 43.
- Calibration measurement: ECE with 10 equal-width bins, without calibration or threshold refitting.

## Self-test transcript

```text
SELFTEST_BEGIN
one_step_reproducibility ok=1 loss1=0.701406180859 loss2=0.701406180859 max_delta=0.000e+00
feature_name_label_guard ok=1 features=17 forbidden=0 malicious_rejected=1
forbidden_split_pre_filesystem_guard ok=1 valB_blocked=1 test_blocked=1 filesystem_calls=0
family_fold_integrity ok=1 valA=198 family_overlap=0 bottom20_in_valA=1
oom_honest_downgrade ok=1 simulation_only=1 nodes=5000->4096 positives=50->50
dual_seal ok=1 prereg_json_sha256=53d10948a0e56f98cab77dfb962d8db5b6ccdbc639a962ff7327bbe4878bcaca prereg_csv_sha256=34dfdd6ec179d8fabfd211d3c78c1c67bbb5e45b1ca483fa69c2190a201ce476
honest_status=OK
SELFTEST_END
```

## Three-seed val-A measurements

| Arm | Mean AUPRC | AUPRC population SD | Mean F1 | F1 population SD | Mean ECE-10 | ECE population SD |
|---|---:|---:|---:|---:|---:|---:|
| GNN_A_no_pretrain | 0.97475955 | 0.00074004 | 0.86999471 | 0.00311698 | 0.02928655 | 0.00193159 |
| GNN_B_SSL_pretrain | 0.97463287 | 0.00065792 | 0.86617804 | 0.00629735 | 0.03052088 | 0.00240370 |
| control_twohop_GBDT_full | 0.87408233 | 0.00021342 | 0.76064814 | 0.00083117 | 0.00783429 | 0.00012124 |

| Arm | Seed | AUPRC | F1 | Precision | Recall | ECE-10 | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GNN_A_no_pretrain | 17 | 0.97567095 | 0.86574571 | 0.76991889 | 0.98881740 | 0.03185691 | 19365 | 5787 | 219 | 142185 |
| GNN_A_no_pretrain | 29 | 0.97385832 | 0.87313551 | 0.78416067 | 0.98488562 | 0.02720045 | 19288 | 5309 | 296 | 142663 |
| GNN_A_no_pretrain | 43 | 0.97474938 | 0.87110290 | 0.77938568 | 0.98728554 | 0.02880229 | 19335 | 5473 | 249 | 142499 |
| GNN_B_SSL_pretrain | 17 | 0.97373838 | 0.85894279 | 0.75934424 | 0.98861315 | 0.03249627 | 19361 | 6136 | 223 | 141836 |
| GNN_B_SSL_pretrain | 29 | 0.97530196 | 0.87429270 | 0.78518579 | 0.98621324 | 0.02713734 | 19314 | 5284 | 270 | 142688 |
| GNN_B_SSL_pretrain | 43 | 0.97485827 | 0.86529864 | 0.76952131 | 0.98830678 | 0.03192903 | 19355 | 5797 | 229 | 142175 |
| control_twohop_GBDT_full | 17 | 0.87398874 | 0.76039823 | 0.82939189 | 0.70200163 | 0.00766941 | 13748 | 2828 | 5836 | 145144 |
| control_twohop_GBDT_full | 29 | 0.87388064 | 0.75977839 | 0.83034633 | 0.70026552 | 0.00795747 | 13714 | 2802 | 5870 | 145170 |
| control_twohop_GBDT_full | 43 | 0.87437763 | 0.76176780 | 0.83094003 | 0.70322712 | 0.00787600 | 13772 | 2802 | 5812 | 145170 |

## Paired family-cluster bootstrap deltas

| Comparison | Observed ΔAUPRC | Bootstrap ΔAUPRC mean | 95% CI | Observed ΔF1 | Bootstrap ΔF1 mean | 95% CI |
|---|---:|---:|---:|---:|---:|---:|
| GNN_A_minus_control | 0.10067721 | 0.10060552 | [0.09539842, 0.10600993] | 0.10934657 | 0.10928158 | [0.10116511, 0.11763937] |
| GNN_B_minus_control | 0.10055054 | 0.10047994 | [0.09522010, 0.10594521] | 0.10552990 | 0.10545635 | [0.09714636, 0.11415827] |
| GNN_B_minus_GNN_A_SSL_lift | -0.00012668 | -0.00012558 | [-0.00058097, 0.00034416] | -0.00381666 | -0.00382523 | [-0.00531185, -0.00235348] |

## Inference ablations

| GNN arm | Ablation | Mean AUPRC | Mean F1 | Mean ECE-10 | Mean full-minus-ablation ΔAUPRC | Mean full-minus-ablation ΔF1 |
|---|---|---:|---:|---:|---:|---:|
| GNN_A_no_pretrain | NoMessage | 0.29827327 | 0.26818368 | 0.25512020 | 0.67648628 | 0.60181103 |
| GNN_A_no_pretrain | edge_type_shuffle | 0.56557178 | 0.50366593 | 0.15372813 | 0.40918776 | 0.36632878 |
| GNN_B_SSL_pretrain | NoMessage | 0.26233150 | 0.28313381 | 0.25636742 | 0.71230137 | 0.58304423 |
| GNN_B_SSL_pretrain | edge_type_shuffle | 0.61042291 | 0.55062237 | 0.12339948 | 0.36420996 | 0.31555567 |

## W2-01 lowest-20 family slice

- Families: 20; pooled rows: 15194.

| Arm | Pooled mean AUPRC | AUPRC population SD | Pooled mean F1 | F1 population SD |
|---|---:|---:|---:|---:|
| GNN_A_no_pretrain | 0.95505410 | 0.00318235 | 0.82982949 | 0.00288647 |
| GNN_B_SSL_pretrain | 0.95458159 | 0.00101405 | 0.82610400 | 0.00521459 |
| control_twohop_GBDT_full | 0.78646908 | 0.00090724 | 0.66839527 | 0.00271464 |

| Family | GNN-A ensemble AUPRC | GNN-B ensemble AUPRC | Control ensemble AUPRC |
|---|---:|---:|---:|
| `1110ae6be92e3ce70289188f5c60b2f8b2cd44e81df484e5d2ddc7e3f921874f` | 0.94587531 | 0.93671812 | 0.69661274 |
| `39e272c0644bca05ef9a1072d6fddfceb26fef2f89d2d7a5fbf9e77ab301ca71` | 0.94917740 | 0.93881849 | 0.69634152 |
| `319e1caca40cecbdc61e90df65a6bfb7d98590e2c5ab5059c93c0e2171460e67` | 0.96530301 | 0.97051147 | 0.76537614 |
| `33cb37871aba4a8a752b8447a6477d5c673b9d12323b2248f387e3081d6df02e` | 0.97276032 | 0.98042228 | 0.73904565 |
| `2168b658d557e58728ddc8152e6f4cf1d0fa2f1608721585b024ebf9c70db570` | 0.98708547 | 0.98500083 | 0.75878232 |
| `28875d1e3f37c4ce0c65bfd218ebc972b7a6d7a59fe88a601235d5b29650497f` | 0.99382814 | 0.99340008 | 0.74734079 |
| `04d9c84d0635432e9faae408abf15d4804fdd25bf8bb68dc2b64722fa4ea47c4` | 0.98223176 | 0.98641170 | 0.84949302 |
| `0bd75bcf23bf3958934b6eeef32c7d9486ee949bf187d06fb89b633f0f6f19d8` | 0.93258378 | 0.92279957 | 0.81480096 |
| `03db38cae9f60b9f81898b95eb01251f5a89ad43e581a50278d3a5129d9588f5` | 0.95488607 | 0.95337441 | 0.83582528 |
| `202d94e93e71064515cdf59ce2acab89bfee773a60fb6a0445bdbc1aa6c58313` | 0.94621433 | 0.93991350 | 0.79906680 |
| `2e3cd029faef920f0cf5a9c1723cecb93793d302b826fbc5b314a42a83049022` | 0.96331776 | 0.94997324 | 0.78681947 |
| `353f43342ffab9a080b1a52f1892efbce1a9d043c7238d277742aa376186fa31` | 0.95569425 | 0.95492237 | 0.77692399 |
| `07a0fee0ad875f51a2a6beb617518df2469fbe72ebdd23d8ace7e8df3ebfdbb1` | 0.98444365 | 0.98506799 | 0.83823604 |
| `1394ce8e13e6aa38502a53bd763ad9016c145076bfce18ff33b928e9bc53b547` | 0.98683635 | 0.98498537 | 0.79826321 |
| `0b9d8a0d081d1f3d6cf43d4fd13e209f6f314f3f2b5190f411d893431a2e72fe` | 0.99231959 | 0.99415947 | 0.85529417 |
| `3d00de647586dd74fb4eb5bf7d285f81cd223a1dc1e4199d25c25b41b3b97394` | 0.95910152 | 0.95553754 | 0.85076008 |
| `132b4ab859803cd775275dd79942b9b81c0048137c1c2f24482e830f2c2acbc3` | 0.95573386 | 0.95701176 | 0.80532291 |
| `1beaab4ca845e75c7806be945198df540e6be915889864ff066ba5279c6ec042` | 0.92509594 | 0.92835532 | 0.79040838 |
| `1ab858ea0af88be21fab72d5397ef20503c2d0cc9312f7f3e42be39a6815544d` | 0.98096657 | 0.98019470 | 0.83826065 |
| `1fd7018c321ef5d1b66495cd7b0b1b2e433a4bbfaee7f490164ca82efaeb42cc` | 0.97185307 | 0.96977486 | 0.84045653 |

## Graph and resource measurements

- Graph config SHA-256: `56911f4633979a3fe00fd56be2d0a39ac06757ed255ed49ed18ca20ba9d4ac49`
- Train graph nodes / directed edges: 3,862,317 / 95,964,019
- val-A graph nodes / directed edges: 167,556 / 4,082,196
- Largest drawing nodes / directed edges: 8,087 / 221,007
- Train-val-A geometry-family collisions: 0
- val-B drawing reads / test reads / original CAD reads: 0 / 0 / 0
- Formal elapsed: 1.540701 h; cumulative G5 charge: 1.988842 / 132.0 h
- Peak process-tree RSS: 4.544163 GiB / 48 GiB
- Peak CUDA allocated / reserved: 0.818103 / 2.041016 GiB
- CUDA OOM events: 0; sampled training graphs: 0

## Full ECE-10 measurements

All per-seed 10-bin counts, mean probabilities, positive rates, and absolute gaps are recorded in `results.json` under `metrics.arms.*.per_seed.*.ece_10bin`.

## Unresolved

- The hash-sealed amendment1 source is syntactically malformed JSON at its final object boundary; it was kept read-only and validated by exact SHA-256 plus the sealed G5 RTX total 132h text.
- The packet names a W2-02 README, but no README file exists in the cell; the existing REPORT.md, results.json, prereg.json, source, work arrays, and fresh exact refit reproduction were used without inventing a README.
- The sealed sampled OOM downgrade was not invoked; all train and val-A graphs used full topology.
- Adoption/rejection AND-gate adjudication remains intentionally outside this cell.

CELL_COMPLETE: gnn_formal