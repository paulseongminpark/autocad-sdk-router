# HATCH Append Design

## Field Mapping

| IR kind | Python append entity payload | Native replay |
| --- | --- | --- |
| `hatch` | `kind`, `normal`, `elevation`, `pattern_angle`, `pattern_scale`, `pattern_type`, `hatch_style`, `loop_count`, `pattern_name`, `pattern_double`, `is_solid_fill`, `is_associative`, `is_gradient`, `loops` passed through verbatim from the IR geometry when every loop is a polyline-style `vertices` loop | `AcDbHatch`; `setNormal`, `setElevation`, `setPattern(kPreDefined, ...)`, `setPatternAngle`, `setPatternScale`, `setPatternDouble`, `setHatchStyle`, `appendLoop(loop_type, vertices, bulges)`, `setAssociative(false)`, `evaluateHatch()` |
| `face3d` | `kind`, `p0`, `p1`, `p2`, `p3`, `edge_visibility` passed through verbatim | `AcDbFace(p0, p1, p2, p3)` plus per-edge visibility replay via `makeEdgeVisibleAt` / `makeEdgeInvisibleAt` |
| `wipeout` | Deferred on the Python side | No native append path wired for block definitions |

## Decisions

- Associativity is forced off for block-appended hatches. The IR field `is_associative` is preserved in the job payload for traceability, but the native replay uses `setAssociative(false)` before `evaluateHatch()` to avoid boundary-object dependencies inside synthesized block definitions.
- Gradient hatches defer in Python with `def_entity kind unsupported by write.block.append_entity (no gradient replay)`. No partial/native fallback is attempted.
- Only hatch loops that already carry polyline-style `vertices` replay. Fixture hatches whose loops contain `edges` instead of `vertices` still defer with the existing generic unsupported reason.
- `pattern_type` and `loop_count` are passed through verbatim for parity with the IR sample, but the native replay policy still uses `AcDbHatch::kPreDefined` as requested and derives the effective loop count from the emitted loops.
- Wipeout stays deferred. The local SDK header exposes `AcDbWipeout::append(AcDbObjectId&)` as the class-specific, proven construction path, but that API has no `AcDbBlockTableRecord*` or target-block argument. The generic `appendAcDbEntity` path is not a proven block-definition construction protocol for wipeout, so `write.block.append_entity` cannot honestly target a named block record headlessly yet.

## Backtrack Triggers

- If the orchestrator build shows `AcDbHatch` API/signature drift in this TU, back out the hatch native branch and re-check the SDK-visible signatures in `dbhatch.h` before reattempting.
- If measured corpus demand expands beyond polyline-loop hatches, extend the Python/native contract to replay edge-based hatch loops explicitly instead of widening the current branch heuristically.
- If a proven wipeout-in-block construction sequence appears that can target an arbitrary block table record, replace the Python defer with that exact sequence and keep the design note in sync.
