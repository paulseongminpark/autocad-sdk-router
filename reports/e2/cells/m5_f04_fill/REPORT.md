# M-5 F04 classical sealed fill — F08-F14

> W3-BOUNDARY: "본 보고의 탐지기 사다리·모든 val-A/val-B 수치의 유효 범위는 CubiCasa SEG-IR 우주 한정이다. E1 실무 도면 전이는 미검증이다."

- Scientific status: `BLOCKED_INPUT`
- Completion status: `CELL_MEASUREMENT_COMPLETE`
- PREREG_local SHA-256: `ebe6ff1a991c6c849965a3111a99f60c18f4e67e29ced5b6654658bf9e3f4712`
- PREREG.csv SHA-256: `98f8f53aac9e68686609330da586d7bc070b657adb6e464b5e85ac0df52b0cd5`
- Extractor spec SHA-256: `a1ef92a42a8e0117c7b0da5f90cf5a654c5bc09ad24e22cced8f48ad6627a9c4`
- Extractor code SHA-256: `171b4ce27f4fa6958250122e260c99870d962b9fa703234fa8bfb4faf8a07896`
- Frozen model SHA-256: `ccc52d2066cc44502b2a8ccb0412b6c77d8caca4c37cfbf919bb95e46f16c754` (no refit)
- Measurement SHA-256: `3504331b3a3b4529ac9c392ec6f26496ff7177a3c8c20cb973ace96df53024dc`
- Evidence CSV SHA-256: `50615267892fe3d8dc1a8f7d154f684287314350103438cebbadb75efcb3c76a`
- Device: `CPU`; GPU use: `0`; peak VRAM: `N/A(no_GPU)`
- W3-TELEM: wall_seconds `12.464836`; peak_rss_bytes `346705920`; peak_vram_bytes `N/A(no_GPU)`; device `CPU`; budget_charge `{"resource":"CPU","seconds":12.464836400002241}`
- Prior failed-run W3-TELEM: attempt `1`; wall_seconds `15.159862`; peak_rss_bytes `341331968`; peak_vram_bytes `N/A(no_GPU)`; device `CPU`; budget_charge `{"resource":"CPU","seconds":15.15986159996828}`; scientific stop `BLOCKED_INPUT` (superseded reporting wrapper only).
- Prior failed-run W3-TELEM: attempt `2`; wall_seconds `12.903009`; peak_rss_bytes `346423296`; peak_vram_bytes `N/A(no_GPU)`; device `CPU`; budget_charge `{"resource":"CPU","seconds":12.903009000001475}`; scientific stop `BLOCKED_INPUT` (superseded expected-pair display only).

## Verdicts

| Cell | Relation | R-META | Mean invariance | Verdict | Eligible / expected | Basis |
|---|---|---:|---:|---|---:|---|
| F08 | `translate` | — | — | **BLOCKED_INPUT** | 0 / 150 | zero-eligible-stop after frozen-family qualification: constant_zero_flag=True; near_all_flag=False; positive_entity_recall=0.00000000 < required 0.20000000 |
| F09 | `rotate` | — | — | **BLOCKED_INPUT** | 0 / 150 | zero-eligible-stop after frozen-family qualification: constant_zero_flag=True; near_all_flag=False; positive_entity_recall=0.00000000 < required 0.20000000 |
| F10 | `uniform-scale` | — | — | **BLOCKED_INPUT** | 0 / 150 | zero-eligible-stop after frozen-family qualification: constant_zero_flag=True; near_all_flag=False; positive_entity_recall=0.00000000 < required 0.20000000 |
| F11 | `unit-change` | — | — | **BLOCKED_INPUT** | 0 / 100 | zero-eligible-stop after frozen-family qualification: constant_zero_flag=True; near_all_flag=False; positive_entity_recall=0.00000000 < required 0.20000000 |
| F12 | `block-explode` | — | — | **BLOCKED_INPUT** | 0 / 50 | zero-eligible-stop after frozen-family qualification: constant_zero_flag=True; near_all_flag=False; positive_entity_recall=0.00000000 < required 0.20000000 |
| F13 | `layer-rename` | — | — | **BLOCKED_INPUT** | 0 / 150 | zero-eligible-stop after frozen-family qualification: constant_zero_flag=True; near_all_flag=False; positive_entity_recall=0.00000000 < required 0.20000000 |
| F14 | `coord-jitter` | — | — | **BLOCKED_INPUT** | 0 / 150 | zero-eligible-stop after frozen-family qualification: constant_zero_flag=True; near_all_flag=False; positive_entity_recall=0.00000000 < required 0.20000000 |

The primary response is the sealed drawing-macro violation rate: equal-weight parameter mean within each drawing, then equal-weight mean across all 50 drawings. Bands are PASS `<=0.02`, INCONCLUSIVE `>0.02 and <=0.10`, and FAIL `>0.10`. A required-gate failure is `BLOCKED_INPUT`, never an invented number.

## Mandatory cubicasa_ml parity

- Status: `PASS`.
- Same-fixture exact float32 array equality: `True`.
- Maximum absolute deviation: `0.0`.
- Candidate/reference feature bytes SHA-256: `c2d700615d0dcd7cd3fcb7cd7adfa86575a2753101f76919123d0899f73bb07e` / `c2d700615d0dcd7cd3fcb7cd7adfa86575a2753101f76919123d0899f73bb07e`.

## Frozen-family qualification

- Status: `FAIL`.
- Base predicted-positive share: `0.0`; constant-zero flag `True`; near-all flag `False`.
- Truth-bearing positive entity recall: `0.0` (required `>=0.20`).
- Repeat normalized-prediction checksum: `PASS` on `5` drawings.

## Definition and boundary audit

- F08-F14 operational definitions were discovered before sealing: translate, rotate, uniform-scale, unit-change, block-explode, layer-rename, and coord-jitter, respectively. Missing definition count: `0`.
- Synthetic population: `50` `scene_*_k1.json` drawings; aggregate SHA-256 `7ba8943db3f8224dd28288cbdc08f55a077a531b88dda7d8bc0e5d15703abd89`.
- Frozen estimator prediction calls: `165`; refit calls: `0`.
- Prohibition counters: GPU `0`; val-B reads `0`; test reads `0`; git commands `0`; subagents `0`; relative I/O paths `0`.
- The measurement is restricted to the synthetic CubiCasa-compatible SEG-IR adapter universe. It is not evidence of transfer to E1 production drawings.

## Artifacts

- `D:/runs/e2_program/cells/m5_f04_fill/PREREG_local.json` — `ebe6ff1a991c6c849965a3111a99f60c18f4e67e29ced5b6654658bf9e3f4712`
- `D:/runs/e2_program/cells/m5_f04_fill/PREREG.csv` — `98f8f53aac9e68686609330da586d7bc070b657adb6e464b5e85ac0df52b0cd5`
- `D:/runs/e2_program/cells/m5_f04_fill/extractor_spec.json` — `a1ef92a42a8e0117c7b0da5f90cf5a654c5bc09ad24e22cced8f48ad6627a9c4`
- `D:/runs/e2_program/cells/m5_f04_fill/m5_f04_fill.py` — `171b4ce27f4fa6958250122e260c99870d962b9fa703234fa8bfb4faf8a07896`
- `D:/runs/e2_program/cells/m5_f04_fill/measurement.json` — `3504331b3a3b4529ac9c392ec6f26496ff7177a3c8c20cb973ace96df53024dc`
- `D:/runs/e2_program/cells/m5_f04_fill/evidence.csv` — `50615267892fe3d8dc1a8f7d154f684287314350103438cebbadb75efcb3c76a`

CELL_MEASUREMENT_COMPLETE
