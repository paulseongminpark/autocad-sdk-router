# W2-02 2-hop classical features

PREREG_SHA256: 6c7db98abe8eb08edd05f09ef1b52d68aa849b9cc2aa803c033e66d01dff747d
EVIDENCE_PREREG_SEAL_SHA256: be2511e7bd5825ea9488997e9a7b075ec0da41519f4b8f0432fa1faf62f6af9f
PREREG_CONTENT_HASH: afb7b7f476289e9d3b0ef7d6ef8a74229139a27706dd0b864d4d2085dec8d95c

This report contains measurements only. It does not emit an adoption or rejection judgment.

## Scope and fixed protocol

- Train drawings: 4200
- Train rows: 3862317
- val-A drawings: 198
- val-A rows: 167556
- val-A families: 198
- Seeds: 17, 29, 43
- Radius: 20px
- Threshold: 0.5
- Bootstrap: 10000 paired family-cluster replicates, seed 43
- val-B drawing reads: 0
- test reads: 0
- Original CAD reads: 0
- Identifier/name/layer feature count: 0

The supplied clean incumbent artifact was fitted on train + val-A. Directly scoring it on val-A would score fit rows, so the comparison arm reproduces its frozen context12 configuration and seeds but fits on train only, exactly matching the packet's train-to-val-A protocol.

## Three-seed val-A measurements

| Arm | Mean AUPRC | AUPRC population SD | Mean F1 | F1 population SD |
|---|---:|---:|---:|---:|
| full | 0.87408233 | 0.00021342 | 0.76064814 | 0.00083117 |
| twohop_removed | 0.83291827 | 0.00078167 | 0.70767682 | 0.00111663 |

| Arm | Seed | AUPRC | F1 | Precision | Recall | Fit seconds |
|---|---:|---:|---:|---:|---:|---:|
| full | 17 | 0.87398874 | 0.76039823 | 0.82939189 | 0.70200163 | 12.066 |
| full | 29 | 0.87388064 | 0.75977839 | 0.83034633 | 0.70026552 | 13.279 |
| full | 43 | 0.87437763 | 0.76176780 | 0.83094003 | 0.70322712 | 12.949 |
| twohop_removed | 17 | 0.83337243 | 0.70863080 | 0.82082829 | 0.62341708 | 8.164 |
| twohop_removed | 29 | 0.83356400 | 0.70828967 | 0.82365286 | 0.62127247 | 7.583 |
| twohop_removed | 43 | 0.83181836 | 0.70611000 | 0.82911044 | 0.61488971 | 8.140 |

## Full minus protocol-matched clean incumbent

| Metric | Point delta | Bootstrap mean | SE | 95% percentile CI |
|---|---:|---:|---:|---:|
| AUPRC | 0.04116407 | 0.04118461 | 0.00226797 | [0.03689308, 0.04568742] |
| F1 | 0.05297132 | 0.05300767 | 0.00312985 | [0.04712176, 0.05936636] |

## Top 20 feature importance by gain

| Rank | Feature | Raw gain sum across seeds | Gain fraction |
|---:|---|---:|---:|
| 1 | nearest_parallel_gap_px | 6327743.094493 | 0.24383088 |
| 2 | junction_degree | 2735739.946696 | 0.10541798 |
| 3 | log10_len | 2675240.812195 | 0.10308673 |
| 4 | collinear_extension_chain_length_px_le2 | 2626362.883551 | 0.10120328 |
| 5 | radius_density_r20_per_px2 | 2566174.935233 | 0.09888402 |
| 6 | sin2t | 2245489.964969 | 0.08652687 |
| 7 | drawing_length_percentile | 1509776.001626 | 0.05817714 |
| 8 | junction_neighbor_degree_sum | 1044227.017041 | 0.04023785 |
| 9 | neighbor_angle_entropy_r20 | 959132.633727 | 0.03695886 |
| 10 | junction_neighbor_degree_variance | 708857.153495 | 0.02731484 |
| 11 | parallel_band_neighbor_count | 646970.245773 | 0.02493011 |
| 12 | parallel | 469728.365924 | 0.01810034 |
| 13 | junction_neighbor_degree_max | 463625.761382 | 0.01786518 |
| 14 | thickness | 195268.961838 | 0.00752442 |
| 15 | twohop_length_max_px | 151060.016305 | 0.00582089 |
| 16 | cos2t | 108180.063250 | 0.00416857 |
| 17 | junction_component_size | 100115.251081 | 0.00385780 |
| 18 | twohop_parallel_gap_max_px | 97231.937562 | 0.00374670 |
| 19 | twohop_parallel_gap_min_px | 95804.994827 | 0.00369171 |
| 20 | twohop_length_mean_px | 86788.480684 | 0.00334427 |

## Optional W2-01 lowest-family deltas

Unavailable: D:\runs\e2_program\cells\w2_01_autopsy\autopsy_results.json was absent; no lowest-family delta was computed.

## Selftest transcript

    SELFTEST_BEGIN
    fixture=colorful_10052.segir.json
    rows=617
    features=30
    double_calculation_equal=1
    numeric_meta_equal_excluding_volatile=1
    determinism_claim=휘발 필드(runtime·타임스탬프) 제외 수치 전 필드 동일
    label_shuffle_changed_labels=1
    label_shuffle_feature_invariant=1
    val_B_probe_blocked=1
    test_probe_blocked=1
    val_B_drawing_reads=0
    test_reads=0
    identifier_name_layer_feature_count=0
    junction_degree_mismatches=0
    subagents_used=0
    honest_verdict=PASS
    SELFTEST_END

## Run accounting

- CPU hours: 0.735113 / 48
- Wall seconds: 1534.104
- Peak RSS GiB: 1.007378 / 48
- Threads: 8
- Subagents used: 0

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| w2_02_twohop.py | ae81bf8c5311fc19c8ad38f7feca5d1c15bf39a71d41a1fb925775d6e63aafe6 |
| prereg.json | 6c7db98abe8eb08edd05f09ef1b52d68aa849b9cc2aa803c033e66d01dff747d |
| results.json | 391aedddf26c0b44116de89bcb27b1b3a6fed07aa1ae8b9dcae9d8b71995bbfb |
| evidence.xlsx final | c05fcdd4bbf1a506dddc031bf599d348cace70cfb27e163bbdb90102985b3194 |
| models/twohop_removed_seed_17.joblib | 12d8792f138dd0e4acc9a8a5fa3354aec54c5c4c6607c27282b42e0a1b49c99b |
| models/full_seed_17.joblib | 10c17dfd86aac602cf7857ac774e04095acb844c1bd6e59eff382b155ccde546 |
| models/twohop_removed_seed_29.joblib | da4129f916679e89025d52a09615b567f4e66e5ca25a7635179f6fb34de9de34 |
| models/full_seed_29.joblib | 0ba894befffae5e22bfc0926b9d9fdd3e0a050c2df403e5c1a1dd7a48256387b |
| models/twohop_removed_seed_43.joblib | d673c8bf0ce34872f48674398480539a66cf855308ae2e5b8a7d747876de35ca |
| models/full_seed_43.joblib | 1df4c400401dfc41a230cacfaa54b694b39cc2bca648b9aef73825182cf1f586 |

## Unresolved and disclosures

- The packet literal IR root D:\runs\e2_ext_cubicasa\ir does not exist. The read-only data root was resolved to the hashed W2-09 source-of-truth path D:\dev\99_tools\autocad-sdk-router\runs\e2_ext_cubicasa\ir.
- The optional W2-01 autopsy artifact was absent at execution time.
- Gain importance uses scikit-learn HistGradientBoosting internal tree-node gain fields and is reported as a numeric diagnostic.
- No val-B drawing, test split, original CAD, identifier, name, or layer string entered feature extraction.

CELL_COMPLETE: w2_02