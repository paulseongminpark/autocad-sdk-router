# F04 transform-by-family table

Prereg SHA-256: `444fa333d0ba816d723e9fc2b0125714a1ad31940710da7a79932b425d7587c0`

Canonical cells stay `UNKNOWN` unless every sealed admissibility gate is evidenced.
Legacy numeric observations are listed separately and are not silently assigned to a family.

| Transform | deterministic_v0 | classical_ml | gnn | vlm |
|---|---|---|---|---|
| translate | UNKNOWN (F01) | UNKNOWN (F08) | UNKNOWN (F15) | UNKNOWN (F22) |
| rotate | UNKNOWN (F02) | UNKNOWN (F09) | UNKNOWN (F16) | UNKNOWN (F23) |
| uniform-scale | UNKNOWN (F03) | UNKNOWN (F10) | UNKNOWN (F17) | UNKNOWN (F24) |
| unit-change | UNKNOWN (F04) | UNKNOWN (F11) | UNKNOWN (F18) | UNKNOWN (F25) |
| block-explode | UNKNOWN (F05) | UNKNOWN (F12) | UNKNOWN (F19) | UNKNOWN (F26) |
| layer-rename | UNKNOWN (F06) | UNKNOWN (F13) | UNKNOWN (F20) | UNKNOWN (F27) |
| coord-jitter | UNKNOWN (F07) | UNKNOWN (F14) | UNKNOWN (F21) | UNKNOWN (F28) |

## Legacy observations (unassigned to canonical families)

| Source transform | Registry relation | Preferred source | Mean invariance | Derived R-META | Diagnostic band | Source verdict | Admission |
|---|---|---|---:|---:|---|---|---|
| translate | translate | b4_fold_v2 | 1 | 0 | PASS | FAIL | INADMISSIBLE |
| rotate | rotate | b4_fold_v2 | 1 | 0 | PASS | FAIL | INADMISSIBLE |
| mirror | — | b4_fold_v2 | 1 | 0 | PASS | FAIL | OUT_OF_CATALOG |
| scale | uniform-scale | b4_fold_v2 | 0.7624 | 0.2376 | FAIL | FAIL | INADMISSIBLE |
| units | unit-change | b4_fold_v2 | 1 | 0 | PASS | REPORT_ONLY | INADMISSIBLE |

`mirror` is retained above as legacy evidence but is outside T-META v1.
The corrected `scale` observation remains FAIL and is never hidden or averaged with the older fold.
