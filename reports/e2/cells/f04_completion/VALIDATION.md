# F04 validation

- Axis status: `AXIS_MEASUREMENT_COMPLETE`
- Scientific gate: `INCOMPLETE_CANONICAL_EVIDENCE`
- Prereg SHA-256: `444fa333d0ba816d723e9fc2b0125714a1ad31940710da7a79932b425d7587c0`
- Self-test: `PASS`

## Input seals

| Role | Exists | Hash match | Actual SHA-256 |
|---|---|---|---|
| packet | True | True | `03ace40a101894eb0bd5d2ff3fd124c342485ef3221e0d382f5e4946645ec35b` |
| legacy_independence_projection | True | True | `9000f4e36246e7d450e358251cad9aa44f788536cdc6bec8669f5aac2f4996ad` |
| corrected_strict_metamorphic_fold | True | True | `866fadf11fa93fa5f8bd6c185c63124f3b7ef40cac0d7b7e12cbace4be6472dc` |
| F04_system_of_truth | True | True | `53efc08a96d8b0a770b5f0b5eaf9ae2d9ca8b5ce7db6422dce64e86afb75fda0` |
| upstream_program_prereg | True | True | `fc93dad9232cfd877802c1d53996357eccc710daff8cfb2cf7c865bf7f78bcd2` |
| relation_and_family_design | True | True | `4a55c843c7224a2e5800f116e360dfe327e13d1fc04e78e882099cfe96f32fc3` |

## Structural checks

- Registry relations: 7, from the sealed preregistration.
- Families: 4, from the sealed preregistration.
- Canonical matrix: 28 rows (= 7 × 4), all explicit.
- Unknown preservation: 28 rows remain UNKNOWN; none was converted to zero or PASS.
- Legacy mirror: retained as OUT_OF_CATALOG.
- Scale: both source observations retained with FAIL diagnostic bands.
- Effects/interactions: not computed because the 28-cell numeric matrix is incomplete.
