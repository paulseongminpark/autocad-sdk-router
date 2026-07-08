# Roundtrip Fidelity Report

## Source + SHA
- Original path: ``
- Original sha256: ``
- Staged sha256: ``

## Honest ceiling
- Modelspace entities: 375
- Certified total: 375
- Out-of-class total: 0
- Deferred count: 23

## Per-kind verdict table
PASS: 5 | FAIL: 1 | VACUOUS: 8

| DXF Name | Certified | Census | Attempted | Diff0 | Status |
| --- | --- | ---: | ---: | ---: | --- |
| ARC | yes | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |
| CIRCLE | yes | 1 | 1 (live 1) | 1 | PASS [deferred 0] |
| DIMENSION | yes | 113 | 113 (live 113) | 113 | PASS [deferred 0] |
| ELLIPSE | yes | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |
| INSERT | yes | 50 | 50 (live 50) | 49 | FAIL [deferred 0] |
| LEADER | yes | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |
| LINE | yes | 21 | 21 (live 21) | 21 | PASS [deferred 0] |
| LWPOLYLINE | yes | 73 | 73 (live 73) | 73 | PASS [deferred 0] |
| MLINE | yes | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |
| MTEXT | yes | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |
| MULTILEADER | yes | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |
| POLYLINE | yes | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |
| SPLINE | yes | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |
| TEXT | yes | 117 | 117 (live 117) | 117 | PASS [deferred 0] |

## Per-layer example rollup
- Aggregated from verdict examples only; if row totals exceed recorded examples, this table is a sample rather than a full census.
| Layer | Removed | Added | Modified | Total |
| --- | ---: | ---: | ---: | ---: |
| 설비OPEN | 1 | 0 | 0 | 1 |

## Diff patterns table
| Signature | Count | Judgment | Note |
| --- | ---: | --- | --- |
| INSERT / removed / layer:설비OPEN | 1 | unreviewed |  |
| block_reference / deferred / reason:def_entity kind unsupported by write.block.append_entity | 1 | unreviewed |  |
| block_reference / deferred / reason:no block_definitions entry for block_name 'X-평면도(기본형)' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| hatch / deferred / reason:def_entity kind unsupported by write.block.append_entity | 1 | unreviewed |  |
| lwpolyline / deferred / reason:def_entity kind unsupported by write.block.append_entity | 20 | unreviewed |  |

## Naive-foil vs smart contrast
- naive_pass: `False`
- smart_all_diff0: `False`
- note: Naive foil already fails; smart diff0 gate remains the authoritative ceiling-aware verdict.

## Evidence paths
- `D:\dev\99_tools\autocad-sdk-router\runs\e2e_1dwg_R2_20260708\summary.json`
- `D:\dev\99_tools\autocad-sdk-router\runs\e2e_1dwg_R2_20260708\census_report.json`
- `D:\dev\99_tools\autocad-sdk-router\runs\e2e_1dwg_R2_20260708\verdict.json`
- `D:\dev\99_tools\autocad-sdk-router\runs\e2e_1dwg_R2_20260708\regen_summary.json`
- `D:\dev\99_tools\autocad-sdk-router\runs\e2e_1dwg_R2_20260708\deferred.json`
