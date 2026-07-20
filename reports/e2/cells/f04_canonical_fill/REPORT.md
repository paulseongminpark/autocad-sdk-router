# F04 canonical fill — execution report

- Scientific status: `BLOCKED_INPUT`
- Completion status: `CELL_MEASUREMENT_COMPLETE`
- Local prereg SHA-256: `f8e681331c6eb4000801d44e353d5888b74d432c7dd06b1a6a70704e2f5a4ea4`
- Evidence artifact: `D:/dev/99_tools/autocad-sdk-router/reports/e2/cells/f04_canonical_fill/evidence.csv`
- Evidence artifact SHA-256: `00b1d04a6f03ed371812f7e669e5179679f91a26d146ce47b51e5585be4ee5e9`
- Evidence format status: `CSV_FALLBACK_DEPENDENCY_LOADER_UNAVAILABLE`
- Execution UTC: `2026-07-20T02:44:15.440752Z`

The packet was executed through its frozen-method admission gate. Neither in-scope family has the exact required frozen artifact, so no transform variant, detector prediction, checksum, LID certificate, sentinel score, or R-META number was manufactured. All 14 owned cells remain `UNKNOWN` with `BLOCKED_INPUT` evidence.

## Canonical confirmation table

| Transform | deterministic_v0 | classical_ml |
|---|---|---|
| `translate` | UNKNOWN (F01; BLOCKED_INPUT) | UNKNOWN (F08; BLOCKED_INPUT) |
| `rotate` | UNKNOWN (F02; BLOCKED_INPUT) | UNKNOWN (F09; BLOCKED_INPUT) |
| `uniform-scale` | UNKNOWN (F03; BLOCKED_INPUT) | UNKNOWN (F10; BLOCKED_INPUT) |
| `unit-change` | UNKNOWN (F04; BLOCKED_INPUT) | UNKNOWN (F11; BLOCKED_INPUT) |
| `block-explode` | UNKNOWN (F05; BLOCKED_INPUT) | UNKNOWN (F12; BLOCKED_INPUT) |
| `layer-rename` | UNKNOWN (F06; BLOCKED_INPUT) | UNKNOWN (F13; BLOCKED_INPUT) |
| `coord-jitter` | UNKNOWN (F07; BLOCKED_INPUT) | UNKNOWN (F14; BLOCKED_INPUT) |

Admissible numeric cells: **0/14**. UNKNOWN cells: **14/14**. No missing value was coerced to zero, PASS, or an imputed rate.

## Frozen artifact qualification

### deterministic_v0

- Status: `BLOCKED_INPUT`.
- Candidate directories searched: 3.
- Exact manifest hits: 0.
- The baseline-freeze directory contains the classical B* manifest/model, and the Feyerabend C0 report directory contains generator coverage/report evidence, not a detector method manifest.
- The current V1 detector was not substituted for V0.

### classical_ml

- Status: `BLOCKED_INPUT`.
- Frozen joblib candidates inspected outside deferred GNN/VLM scope: 8.
- Exact persisted six-feature model hits: 0.
- `D:/runs/e2_program/cells/baseline_freeze/bstar_model.joblib` is `hist_gbdt_context12_p2b`: 12 features, and its bundle has no threshold field.
- `D:/runs/e2_program/cells/w2_09_valb/clean_incumbent.joblib` is a 12-feature context model. It has threshold 0.5, but the feature schema is not the required six-feature schema.
- `hist_gbdt_local6_p2a` has historical result rows at threshold 0.5, but the baseline-freeze code persisted only the selected 12-feature champion. Result rows are not a frozen estimator and were not promoted.

## Sealed transform rules and execution status

| Relation | Parameters | Structured relation | Validity gate | Execution |
|---|---:|---|---|---|
| `translate` | 3 | axis translated by the same vector; thickness unchanged | inverse transform restores endpoints and topology | NOT_RUN — both family inputs blocked |
| `rotate` | 3 | axis rotated about bbox centroid; thickness unchanged | inverse rotation restores endpoints and topology | NOT_RUN — both family inputs blocked |
| `uniform-scale` | 3 | axis scaled about bbox centroid; thickness multiplied by absolute factor | factor is positive and inverse scaling restores geometry | NOT_RUN — both family inputs blocked |
| `unit-change` | 2 | raw coordinates and thickness scale while canonical millimetre quantities remain unchanged | coordinates, $INSUNITS, and scale_mm_per_unit encode the same physical quantities | NOT_RUN — both family inputs blocked |
| `block-explode` | 1 | world geometry unchanged with occurrence-level LID mapping | no remaining INSERT; occurrence mapping bijective; world topology unchanged | NOT_RUN — both family inputs blocked |
| `layer-rename` | 3 | geometry and LID unchanged; layer map bijective | layer map bijective and geometry hash unchanged | NOT_RUN — both family inputs blocked |
| `coord-jitter` | 3 | shared logical vertices receive the same deterministic bounded dither | nonzero segments, unchanged incidence/topology, certified parallel-band margin, and input-only decision-margin certificate | NOT_RUN — both family inputs blocked |

The 50 sealed `kappa=1` synthetic drawings and their aggregate SHA were verified, but transformed measurement variants were not generated after the zero-eligible-family stop rule fired. Consequently every transform/LID/checksum/sentinel certificate is explicitly `NOT_RUN_BLOCKED_INPUT`, not PASS.

## Judge bands

- PASS: `R-META <= 0.02`
- INCONCLUSIVE: `0.02 < R-META <= 0.10`
- FAIL: `R-META > 0.10`
- UNKNOWN: no admissible numeric measurement; never coerce to zero or PASS
- Boundary self-test: `PASS` on 6 fixed fixtures using the sealed judge implementation.

## Numeric lineage and boundary audit

- Synthetic drawings: 50 from `D:/runs/e2_program/cells/feyerabend_c0/scenes`; aggregate SHA-256 `7ba8943db3f8224dd28288cbdc08f55a077a531b88dda7d8bc0e5d15703abd89`.
- Positive drawings: 49; zero-wall sentinels: 1; all-wall sentinels: 1. Source: sealed `coverage_numbers.json` and the 50-file manifest.
- Preregistered nested parameter values: 18 per family; generated transformed variants: 0 because Q1/Q2 method input admission failed first.
- Model/API calls: 0; local estimator prediction calls: 0; test-set reads: 0; original CAD reads/writes: 0/0; git commands: 0; subagents: 0; GNN/VLM executions: 0/0.
- Every source number and artifact hash is preserved in `D:/runs/e2_program/cells/f04_canonical_fill/results.json`, `D:/runs/e2_program/cells/f04_canonical_fill/candidate_inventory.json`, `D:/runs/e2_program/cells/f04_canonical_fill/synthetic_pack_manifest.json`, and the evidence artifact named in the report header.
- XLSX fallback reason: the required `load_workspace_dependencies` capability is not exposed in this session; the spreadsheet skill forbids guessed dependency paths or alternate workbook libraries, so the packet-authorized UTF-8 CSV fallback was emitted as `D:/dev/99_tools/autocad-sdk-router/reports/e2/cells/f04_canonical_fill/evidence.csv`.

## Cell reasons

| Cells | Family | State | Reason |
|---|---|---|---|
| F01–F07 | `deterministic_v0` | UNKNOWN / BLOCKED_INPUT | exact frozen v0 method manifest absent; v1 substitution forbidden |
| F08–F14 | `classical_ml` | UNKNOWN / BLOCKED_INPUT | no persisted frozen six-feature HGBDT with frozen threshold/training manifest |

The completion marker records that the requested packet was fully adjudicated and packaged. It does not claim that the scientific F04 cells were filled; both family input gates remain blocked.

CELL_MEASUREMENT_COMPLETE
