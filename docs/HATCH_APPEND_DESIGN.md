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

## 패턴 정의선 추출

- Native extract contract: non-solid, non-gradient `AcDbHatch` entities now emit `geometry.pattern_definitions` only when `numPatternDefinitions() > 0`.
- Row schema: each item is `{"angle": <rad>, "base": [baseX, baseY], "offset": [offsetX, offsetY], "dashes": [d1, d2, ...]}` from `getPatternDefinitionAt(i, angle, baseX, baseY, offsetX, offsetY, dashes)`.
- Angle units stay in radians in the IR verbatim. No extractor-side conversion is allowed; `.pat` synthesis is the only place that converts `angle` to degrees.
- `tools/ir_builder.py` is not a generic geometry passthrough for native graph entities; it lifts hatch fields explicitly, so `pattern_definitions` must be preserved there unchanged as a bare pass-through list.
- REBUILD-side contract for the next packet: stage a temporary `.pat` entry as `*<NAME>\n<angle_deg>, <baseX>, <baseY>, <offsetX>, <offsetY>[, dashes...]`, then replay with `setPattern(kCustomDefined, <NAME>)` and apply `setPatternAngle(...)` / `setPatternScale(...)` separately.
- Never bake the same transform twice: definition-line `angle_deg` comes only from the stored row radians, while hatch instance rotation/scale remain the existing `pattern_angle` and `pattern_scale` setters.

## REBUILD Implementation Notes

- `tools/patch_ops/blocks.py` now emits drawing-custom block-definition hatches only when `pattern_definitions` is present and non-empty; the emitted `entity` carries `pattern_definitions` verbatim for batch-side `.pat` synthesis. Custom names without definitions still defer with `custom hatch pattern replay pending .pat synthesis`.
- `tools/patch_engine.py` synthesizes one `.pat` file per unique hatch pattern name per native batch before the per-op job JSON files are written. The exact file naming rule is `<NAME>.pat` with `<NAME>` uppercased, and every emitted hatch job receives `entity.pattern_pat_path` as an absolute forward-slash path to that synthesized file.
- The only radians-to-degrees conversion site is the batch `.pat` writer (`%.10g` formatting via Python `.10g`), so extractor IR and job payloads stay in radians elsewhere.
- Router/runtime assumption proven from the custom-script lane: the batch `.scr` is copied into the router's staged DWG directory and `accoreconsole` is launched with that staged DWG directory as its working directory. The native hatch builder therefore copies the synthesized `<NAME>.pat` from `pattern_pat_path` into the current working directory before calling `AcDbHatch::setPattern(AcDbHatch::kCustomDefined, name)`.

## REBUILD Backtrack Trigger

- If custom hatch replay starts failing with `HATCH_CUSTOM_PAT_UNRESOLVED` after the batch-side `.pat` file is present, back out the custom replay branch and re-verify the effective `accoreconsole` working directory / custom-pattern resolution behavior before widening the batch surface.

## Edge Loops

- Native extract contract for a non-polyline hatch loop: keep the existing loop wrapper fields `index`, `loop_type`, `closed`, and `status`, and emit `edges` instead of `vertices`.
- Edge row schema:
  - `{"type":"line","start":[x,y],"end":[x,y]}`
  - `{"type":"arc","center":[x,y],"radius":r,"start_angle":a0,"end_angle":a1,"ccw":bool}`
  - `{"type":"ellipse","center":[x,y],"major":[x,y],"ratio":k,"start_angle":a0,"end_angle":a1,"ccw":bool}`
  - `{"type":"spline","degree":n,"control":[[x,y],...],"knots":[...],"rational":bool,"weights":[...]}`
  - `{"type":"unsupported_<AcGe::EntityId int>"}` for any unexpected `AcGeCurve2d` subtype; extraction must count it honestly and never silently skip it.
- Angle units stay in radians verbatim for `arc` and `ellipse` edges.
- `ellipse.major` is the major-axis vector with the major radius baked into its magnitude, and `ellipse.ratio` is `minor_radius / major_radius`.
- REBUILD contract for the next packet: construct one `AcGeCurve2d*` per `edges[]` row and replay the loop via `appendLoop(loopType, edgePtrs, edgeTypes)`.
- REBUILD constructors:
  - `line` -> `AcGeLineSeg2d(start, end)`
  - `arc` -> `AcGeCircArc2d(center, radius, start_angle, end_angle, AcGeVector2d::kXAxis, !ccw)`
  - `ellipse` -> derive `majorRadius = |major|`, `minorRadius = majorRadius * ratio`, derive orthogonal unit major/minor axes from `major`, then construct `AcGeEllipArc2d(center, majorAxisUnit, minorAxisUnit, majorRadius, minorRadius, start_angle, end_angle)`
  - `spline` -> `AcGeNurbCurve2d(degree, knots, control)` when `rational == false`, otherwise `AcGeNurbCurve2d(degree, knots, control, weights)`

## Edge Loop Rebuild Notes

- Python emit gate: a hatch loop is replayable when it is either the existing polyline `vertices` form or a non-empty `edges` array whose rows all match the live `line` / `arc` / `ellipse` / `spline` schema. Any `unsupported_<n>` edge defers the whole hatch with `def_entity kind unsupported by write.block.append_entity (unsupported edge type in loop)`.
- Arc rebuild keeps extractor radians verbatim and maps `ccw` directly to the `AcGeCircArc2d(..., AcGeVector2d::kXAxis, !ccw)` clockwise flag.
- Ellipse rebuild treats `major` as the full major-axis vector: `majorRadius = |major|`, `majorAxisUnit = major / |major|`, `minorRadius = majorRadius * ratio`. `ccw=true` uses the left-hand perpendicular minor axis `(-uy, ux)`; `ccw=false` flips it to `(uy, -ux)` so the same start/end radians replay the opposite sweep.
- Spline rebuild consumes `degree`, `control`, `knots`, `rational`, and `weights` exactly from the edge row. Rational splines require `len(weights) == len(control)`; otherwise the native builder fails loud with `HATCH_EDGE_LOOP_MALFORMED`.
- Ownership rule: edge-loop replay allocates one heap `AcGeCurve2d` subclass per edge, passes those pointers to `AcDbHatch::appendLoop(loopType, edgePtrs, edgeTypes)`, then deletes the temporary curves immediately after `appendLoop` returns because `AcDbHatch` copies the boundary geometry. Parse or append failures must release any already-built edge curves before returning.
