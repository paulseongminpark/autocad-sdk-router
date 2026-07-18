# Non-GNN Baseline Freeze — Numeric Execution Report

- Completed: 2026-07-19T01:17:52+09:00
- Development universe: CubiCasa train to val
- Rows: train 3,862,317; val 353,953
- Drawings: train 4,200; val 400
- Split hash: `f667686bec339f0253bbc39936131041c59af4a7e67363dc2287393b5ccc18c9`
- Test-split reads: 0
- Peak sampled RSS: 1.771 GiB

## Primary arms (val, three-seed mean ± population std)

| Arm | AUPRC | F1@0.5 |
|---|---:|---:|
| fast_score_p1 | 0.10863559 ± 0.00000000 | 0.17914727 ± 0.00000000 |
| logistic_local6 | 0.34083734 ± 0.00000000 | 0.05319321 ± 0.00000000 |
| hist_gbdt_local6_p2a | 0.67850546 ± 0.00035010 | 0.51587417 ± 0.00126267 |
| hist_gbdt_context12_p2b | 0.83119857 ± 0.00073391 | 0.70637735 ± 0.00093223 |

## Frozen B*

- Arm: `hist_gbdt_context12_p2b`
- Selection metric: mean val AUPRC = 0.8311985694
- Mean val F1@0.5: 0.7063773452
- Model artifact SHA-256: `04c0515f0253b1d1979b5a5ca4a1f6ad6801c8e6b17a74734978f14717749f21`

## Leakage, shuffle, and family controls

- Primary identifier/name feature count: 0
- Diagnostic name-derived feature count: 2
- Leaky-minus-masked AUPRC: +0.0000000000
- Leaky-minus-masked F1: +0.0000000000
- Shuffle-null AUPRC central 95%: [0.0977762655, 0.2025050821]
- P2-b observed AUPRC percentile position in shuffle null: 1.0000000000
- Held-out shuffle AUPRC percentile position among remaining shuffles: 0.3333333333
- Family collision count: 4
- Cross-fold geometry-family count: 4
- Cross-fold drawing-ID count: 0
- Source-classifier accuracy mean: 0.5130000000

## Evidence artifact status

- `BLOCKED_XLSX`: the required artifact-tool dependency loader was unavailable in this executor.
- Row-complete substitute: `evidence_rows.json`.

## Artifact hashes

- baseline_freeze.py: `631abe6ab2ebf9f805882e269eb139dd15788fb5e6ea6cdca949377479db9f3c`
- results.json: `7a696ff08c0a78c8b9db5f85ef5b5ece4dcc5ded40a664efe6564af36d65eab7`
- bstar_manifest.json: `9a4a2cbf60c818ec5224c30c0b10f894f4c5612199a0cac359f23754f48b77d2`
- bstar_model.joblib: `04c0515f0253b1d1979b5a5ca4a1f6ad6801c8e6b17a74734978f14717749f21`
- evidence_rows.json: `ad65d6a2fe8aeb79ee7ce3db076a8740c567cb91fe482691d02ffd2384d07ba8`

CELL_COMPLETE: baseline_freeze
