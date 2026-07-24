# F04 common metamorphic judge — completion report

- Axis measurement status: `AXIS_MEASUREMENT_COMPLETE`
- Scientific F04 gate: `INCOMPLETE_CANONICAL_EVIDENCE`
- Local prereg SHA-256: `444fa333d0ba816d723e9fc2b0125714a1ad31940710da7a79932b425d7587c0`
- Execution UTC: `2026-07-20T02:24:46Z`

The registry/judge and exhaustive table were completed from the sealed inputs. No canonical family received a PASS: the input folds do not identify a frozen method/family or provide the required transform, LID, checksum, and sentinel qualification certificates. Their numbers are preserved as legacy observations, while every unproven canonical cell remains `UNKNOWN`.

## Sealed F04 wording

승계 — 공용 relation registry/judge + 방법별 게이트 분리(C11). doe_P5의 **effects/confirmation(발견 기능)을 명시 산출물로 복원**: transform×family 상호작용 표는 F04의 필수 보고서다 (판정 기능에 흡수 금지). CPU part = doe_P5 F01–F14(결정론+고전ML)

## Relation registry

| Relation | Binary relation | Structured relation | Validity gate |
|---|---|---|---|
| `translate` | invariant | axis translated by the same vector; thickness unchanged | inverse transform restores endpoints and topology |
| `rotate` | invariant | axis rotated about bbox centroid; thickness unchanged | inverse rotation restores endpoints and topology |
| `uniform-scale` | invariant | axis scaled about bbox centroid; thickness multiplied by absolute factor | factor is positive and inverse scaling restores geometry |
| `unit-change` | invariant | raw coordinates and thickness scale while canonical millimetre quantities remain unchanged | coordinates, $INSUNITS, and scale_mm_per_unit encode the same physical quantities |
| `block-explode` | invariant | world geometry unchanged with occurrence-level LID mapping | no remaining INSERT; occurrence mapping bijective; world topology unchanged |
| `layer-rename` | invariant | geometry and LID unchanged; layer map bijective | layer map bijective and geometry hash unchanged |
| `coord-jitter` | invariant | shared logical vertices receive the same deterministic bounded dither | nonzero segments, unchanged incidence/topology, certified parallel-band margin, and input-only decision-margin certificate |

## Method admissibility

A numeric cell verdict is allowed only after all common and family-specific gates in `PREREG_local.json` pass. A number without those certificates is evidence, but not a canonical cell result. In particular, strict source verdicts and sentinel trips are never waived.

| Family | Owner | Current tranche | Required artifact/status |
|---|---|---|---|
| `deterministic_v0` | `F04` | in scope | exact frozen v0 method manifest; current v1 must not substitute |
| `classical_ml` | `F04` | in scope | frozen HGBDT model, six-feature schema, threshold, and training manifest |
| `gnn` | `F04G` | deferred | DEFERRED_SCOPE |
| `vlm` | `F04V` | deferred | DEFERRED_SCOPE |

## Transform-by-family confirmation table

| Transform | deterministic_v0 | classical_ml | gnn | vlm |
|---|---|---|---|---|
| `translate` | UNKNOWN (F01) | UNKNOWN (F08) | UNKNOWN (F15) | UNKNOWN (F22) |
| `rotate` | UNKNOWN (F02) | UNKNOWN (F09) | UNKNOWN (F16) | UNKNOWN (F23) |
| `uniform-scale` | UNKNOWN (F03) | UNKNOWN (F10) | UNKNOWN (F17) | UNKNOWN (F24) |
| `unit-change` | UNKNOWN (F04) | UNKNOWN (F11) | UNKNOWN (F18) | UNKNOWN (F25) |
| `block-explode` | UNKNOWN (F05) | UNKNOWN (F12) | UNKNOWN (F19) | UNKNOWN (F26) |
| `layer-rename` | UNKNOWN (F06) | UNKNOWN (F13) | UNKNOWN (F20) | UNKNOWN (F27) |
| `coord-jitter` | UNKNOWN (F07) | UNKNOWN (F14) | UNKNOWN (F21) | UNKNOWN (F28) |

The table has 28 canonical cells because the sealed registry has 7 relations and 4 families. Admissible numeric cells: 0; missing cells: 28. No missing cell was imputed. Consequently transform effects, family effects, and A×B interactions are `NOT_COMPUTABLE_MISSING_CANONICAL_CELLS`, and confirmation is not run.

## Legacy evidence, with numeric lineage

| Transform | Registry relation | Source | Mean invariance | R-META derivation | Diagnostic band | Source verdict | Sentinel all | Admission |
|---|---|---|---:|---|---|---|---:|---|
| `translate` | `translate` | `b4_fold_v2` `/transforms/translate` | 1 | `1 - 1 = 0` | PASS | FAIL | 20 | INADMISSIBLE |
| `rotate` | `rotate` | `b4_fold_v2` `/transforms/rotate` | 1 | `1 - 1 = 0` | PASS | FAIL | 20 | INADMISSIBLE |
| `mirror` | `—` | `b4_fold_v2` `/transforms/mirror` | 1 | `1 - 1 = 0` | PASS | FAIL | 20 | OUT_OF_CATALOG |
| `scale` | `uniform-scale` | `b4_fold_v2` `/transforms/scale` | 0.7624 | `1 - 0.7624 = 0.2376` | FAIL | FAIL | 20 | INADMISSIBLE |
| `units` | `unit-change` | `b4_fold_v2` `/transforms/units` | 1 | `1 - 1 = 0` | PASS | REPORT_ONLY | 20 | INADMISSIBLE |

`b4_fold_v2` has precedence for the overlapping legacy observations because it is the repaired strict fold. `w2_independence_audit_v1` is retained in `evidence.json`; the two are not averaged.

## Scale failure retained

- `b4_fold_v2` `/transforms/scale`: invariance 0.7624; R-META 0.2376 from `1 - 0.7624 = 0.2376`; diagnostic band `FAIL`; source verdict `FAIL`; sentinel_all `20`. sentinel_all trips on 20/20 rows; sealed rule: any sentinel trip = automatic FAIL; invariance 0.7624 also below 0.90
- `w2_independence_audit_v1` `/surrogates/D_detector_vs_metamorphic/per_transform/scale`: invariance 0.8795; R-META 0.1205 from `1 - 0.8795 = 0.1205`; diagnostic band `FAIL`; source verdict `FAIL`; sentinel_all `—`.

Both recorded scale measurements exceed the sealed FAIL boundary. The corrected fold is worse than the older projection; the exact delta is retained in `evidence.json`. This failure is not converted to UNKNOWN—the observation remains FAIL—while its assignment to a canonical method family remains inadmissible.

## Boundaries and validation

- Model/API calls: 0 (instrument consumes local JSON only).
- Test-set reads: 0 (only preregistered report/design inputs were opened).
- Original CAD reads/writes: 0/0.
- Existing source files modified: 0; both instrument files are new.
- Input hash checks passing: 6/6, directly from the sealed expected hashes and current SHA-256 values.
- Self-test: `PASS` using hand-fixed expected fixtures, independent of production input values.

The completion marker means the requested registry/judge measurement surface was built and exhaustively emitted. It does not mean the F04 scientific gate passed; that gate remains incomplete until admissible family-tagged cells exist.

AXIS_MEASUREMENT_COMPLETE
