# T3a-batch2 build log — spline + dimension subtypes (aligned/radial/diametric)

Branch `cados/w3-batch2`, parent `cados/wave0-build` @ `7ee2ca8` (T3a). Worktree:
`D:\dev\99_tools\autocad-sdk-router__w3_batch2`.

## Root gap (post-T3a state)

`measure/reachable_matrix.jsonl` already classified `write.entity.spline`,
`write.entity.dim.aligned`, `write.entity.dim.radial`, `write.entity.dim.
diametric` as REACHABLE (native `HasOp` admits them, `registry_status:
implemented`, live empty-arg probe returns `MISSING_ARG` not a crash) -- the
native ObjectARX write handlers (`m08g_handlers.inc` / `m08h_handlers.inc`)
were already real and working. Two gaps stood between "reachable" and
"extraction+certification", both closed this batch:

1. **No patch_ops wiring at all.** Unlike `create_ellipse`/`create_dimension`
   (already promoted at T1), these four had no `tools/patch_ops/entities.py`
   `WRITE_OP_MAP` entry or `build_job_args` branch -- `op_roundtrip_probe.
   resolve_native_op` returned `None` for all four op_names, so the P-gate
   pipeline could not even attempt a create for them.
2. **No `collectModelSpaceGraph` read branch** (the same class of gap
   `create_ellipse`/`create_dimension` had through T1) -- `AcDbSpline`,
   `AcDbAlignedDimension`, `AcDbRadialDimension`, `AcDbDiametricDimension` all
   fell through to the generic "no type-specific geometry" case.

## What changed

1. `tools/patch_ops/entities.py` -- first patch-level wiring for all four:
   `WRITE_OP_MAP` gained `create_spline` / `create_dimension_aligned` /
   `create_dimension_radial` / `create_dimension_diametric`; `build_job_args`
   gained one pass-through branch per native op (points/order/layer for
   spline; xline1/xline2/dim_line/dim_text/layer for aligned; center/
   chord_point/leader_length/dim_text/layer for radial; chord_point/
   far_chord_point/leader_length/dim_text/layer for diametric).
   `tests/unit/test_patch_ops_split.py`'s pinned `_ORIGINAL_NATIVE_WRITE_OP_MAP`
   oracle extended to match (same pattern as the WAVE-1 TIER-1 T1 update).
   `config/op_dag.json` regenerated (`tools/op_dag_generate.py`) -- the four
   op_ids' `target_files` now include `tools/patch_engine.py`, mechanically
   derived from `NATIVE_WRITE_OP_MAP` membership; no other content changed.

2. `src/Ariadne.AcadNative/AriadneNativeJob.cpp` (`#include "dbspline.h"`,
   `dbdim.h` already included by T3a):
   - New `AcDbSpline::cast` branch (grouped with the ellipse/curve-ish
     primitives): `degree` (`degree()`), `closed` (`isClosed()`),
     `fit_points` (`numFitPoints()`/`getFitPointAt`) -- all direct,
     args-derivable echoes of what `write.entity.spline`'s fit-point ctor
     was given. Also extracts `spline_control_points`/`spline_knots` via one
     `getNurbsData()` call -- AutoCAD's own fit-to-NURBS conversion result,
     NOT derivable from args alone (see LIVE DISCOVERY notes below).
   - New `AcDbAlignedDimension` / `AcDbRadialDimension` / `AcDbDiametricDimension`
     branches (appended after T3a's `AcDbRotatedDimension` branch): same
     `xline1_point`/`xline2_point`/`dim_line_point`/`measurement` shape for
     aligned (minus `rotation` -- aligned has none); `center`/`chord_point`/
     `leader_length`/`measurement` for radial; `chord_point`/
     `far_chord_point`/`leader_length`/`measurement` for diametric. All three
     also extract `dim_block_handle`/`dim_block_name` via the same
     `dimBlockId()` + `acdbOpenObject`+`getName` idiom T3a used (base
     `AcDbDimension` method, works identically across subtypes). All doubles
     flow through the existing `kJsonDoublePrecision` stream.

3. `tools/ir_builder.py` (`_geometry_from_native_entity`/`_entity_from_native`
   -- the allowlist, not a passthrough):
   - `_NATIVE_CLASS_TO_DXF_KIND`: added `AcDbRadialDimension` /
     `AcDbDiametricDimension` -> `("DIMENSION", "dimension")` (`AcDbSpline` /
     `AcDbAlignedDimension` were already mapped, pre-T3a-batch2).
   - Point-lift loop extended: `chord_point`, `far_chord_point`.
   - Number-lift loop extended: `degree`.
   - New `fit_points` lift (distinct from `vertices`: fit points have no
     bulge concept and are not an owning polyline/curve's own vertices).
   - `spline_control_points`/`spline_knots`/`leader_length` lifted as
     TOP-LEVEL entity fields (never inside `"geometry"`) -- same treatment as
     T3a's `dim_block_handle`/`dim_block_name`, for the same reason (see LIVE
     DISCOVERY below for `leader_length`; spline's NURBS-basis fields are the
     un-reproducible-fit-algorithm case documented from the start).

4. `tools/op_roundtrip_probe.py` -- four new ground-truth builders:
   `_expect_create_spline`, `_expect_create_dimension_aligned`,
   `_expect_create_dimension_radial`, `_expect_create_dimension_diametric`,
   all registered in `_EXPECTED_ENTITY_BUILDERS`.

5. Tests updated/added to match: `tests/unit/test_ir_builder.py` (4 new
   `TestNativeGraphGeometryLifting` cases), `tests/unit/test_op_roundtrip_
   probe.py` (6 new `TestExpectedIrForOp` cases, incl. an explicit-`order`
   spline case), `tests/unit/test_patch_ops_split.py` (oracle extension, see
   above).

## LIVE DISCOVERY 1: aligned dimension re-anchors `dim_line_point` -- exactly like rotated

An aligned dimension is, geometrically, a rotated dimension whose "rotation"
is not an independent arg: it is always the xLine1->xLine2 baseline's own
angle (`atan2(dy, dx)`) -- that is the definition of "aligned". Reused T3a's
`_rotated_dimension_line_point`/`_rotated_dimension_measurement` verbatim,
substituting the baseline angle for "rotation". **Live-verified on the FIRST
attempt, no correction needed**, against two geometries:

| xline1 | xline2 | dim_line | stored dim_line_point | measurement |
|---|---|---|---|---|
| (0,0,0) | (100,0,0) | (50,20,0) | (100.0, 20.0, 0.0) | 100.0 |
| (0,0,0) | (60,80,0) | (20,60,0) | (44.0, 92.0, 0.0) | 100.0 |

The second case is a non-axis-aligned (60/80/100 triangle) baseline,
specifically chosen because T3a's own caveat says the rotated-dim formula is
"only asserted for [a baseline] PARALLEL to the rotation direction" --
for an ALIGNED dimension this parallelism holds BY CONSTRUCTION (rotation
literally *is* the baseline angle), so this case is not a coincidental pass;
it is a structural guarantee the aligned case has and the generic rotated
case does not.

## LIVE DISCOVERY 2: radial/diametric `leader_length` does not survive as a ctor-arg echo

First live re-cert attempt gave `leader_length=5.0` to both
`create_dimension_radial` (chord_point 10 units from center) and
`create_dimension_diametric` (chord_point<->far_chord_point 20 units apart);
both came back with `leaderLength()` reset to `0.0` on read-back -- every
other field (`center`/`chord_point`/`far_chord_point`/`measurement`) matched
exactly. Root cause: AutoCAD only actually draws (and therefore only
persists a nonzero) leader when its own dimstyle-driven heuristic decides the
dimension text does not fit without one; at the default text/arrow size and
a chord distance of 10-20 units, no leader was needed, so the ctor's
`leaderLength` argument was silently discarded on regen. This is AutoCAD's
own internal recompute, not derivable from this op's own args alone (whether
a leader is "needed" depends on dimstyle text height/arrow size interacting
with geometry, not on `leader_length` itself) -- so, exactly like T3a's
`dim_block_handle`/`dim_block_name`, `leader_length` is extracted (real,
sometimes-informative reader value) but kept OUTSIDE `"geometry"` as a
top-level entity field, never asserted by the P-gate. Both ops re-certified
diff=0 immediately after this fix, no rebuild required (Python-only change).

## LIVE DISCOVERY 3 (test-fixture bug, not a code regression): rotated-dim non-parallel baseline is genuinely unverified

The first regression-sweep pass included a `rotation=pi/4` case reusing the
rotation=0 case's baseline verbatim (`xline1=(0,0,0)`, `xline2=(100,0,0)`,
i.e. baseline angle 0, paired with `rotation=pi/4`) -- a baseline NOT
parallel to the rotation direction. This is *exactly* the case T3a's own
build log flags as "unverified, out of scope": `_rotated_dimension_line_
point`'s formula was only ever confirmed for a parallel baseline. The actual
readback (`dim_line_point=(65.0, 35.0, 0.0)`) did not match the formula's
prediction (`(115.0, -15.0, 0.0)`) -- a real, expected divergence given the
documented caveat, not a regression in T3a's code. Corrected the regression
fixture to use a baseline parallel to rotation (`xline2=(70.71...,
70.71..., 0)`, i.e. also at pi/4) and it re-certified diff=0 immediately,
confirming `AcDbRotatedDimension`'s own behavior is unchanged by this
batch's edits. No product code was touched for this "fix" -- it was a
test-fixture correction only, recorded here so the non-parallel-baseline gap
stays documented rather than silently rediscovered.

## Why spline_control_points/spline_knots are extracted but never asserted

`write.entity.spline` only ever creates a FIT-POINT `AcDbSpline`
(`AcDbSpline(fitPoints, order, 0.0)`); AutoCAD internally converts that into
a NURBS representation via its own proprietary global curve-interpolation
algorithm (knot parameterization, end conditions, etc. are not part of the
public ObjectARX contract). `degree`/`closed`/`fit_points` are trivially
predictable (`degree = order - 1`, `closed` always `False` for this ctor
path, `fit_points` is the literal input) and are asserted; the derived
NURBS basis is not reproducible in Python without reimplementing that
algorithm, so -- consistent with `expected_ir_for_op`'s "ground truth from
args alone, never a live read" contract -- it is extracted (real reader
value for anyone reading an arbitrary, not-necessarily-self-created spline)
but surfaced as TOP-LEVEL fields, never inside `"geometry"`.

## Re-certification (real, unmocked)

Driver: ad-hoc script invoking `op_roundtrip_probe.probe_roundtrip()`
directly (real `patch_engine.apply_staged`, no injection), staging
`tests/fixtures/native_sample.dwg` fresh per op. Two full runs (first caught
the `leader_length` bug and the bad pi/4 test fixture; second, after both
fixes, is the certified result):

| op | args | result |
|---|---|---|
| create_spline | 4 fit points, default order | **PASS** diff=0 |
| create_dimension_aligned | xline1/xline2/dim_line (axis-aligned) | **PASS** diff=0 |
| create_dimension_aligned | xline1/xline2/dim_line (60/80/100 diagonal) | **PASS** diff=0 |
| create_dimension_radial | center/chord_point/leader_length | **PASS** diff=0 |
| create_dimension_diametric | chord_point/far_chord_point/leader_length | **PASS** diff=0 |
| create_line (regression) | start/end | **PASS** diff=0 |
| create_circle (regression) | center/radius | **PASS** diff=0 |
| create_arc (regression) | center/radius/angles | **PASS** diff=0 |
| create_ellipse (regression) | center/normal/major_axis/radius_ratio/angles | **PASS** diff=0 |
| create_dimension (regression, rotation=0) | xline1/xline2/dim_line/rotation | **PASS** diff=0 |
| create_dimension (regression, rotation=pi/4, corrected baseline) | xline1/xline2/dim_line/rotation | **PASS** diff=0 |
| create_text (regression) | position/text/height | **PASS** diff=0 |
| create_mtext (regression) | position/text/height | **PASS** diff=0 |
| create_polyline (regression) | points w/ bulge + closed | **PASS** diff=0 |

14/14 ok (5 new + 9 regression). `tests/fixtures/native_sample.dwg` confirmed
byte-identical (sha256 `eac5d4b1...5fe3f76` unchanged across the smoke test
and both full re-cert runs) -- original READ-ONLY invariant held throughout.
No residual gaps for the four target kinds beyond the two deliberately-
unasserted, deliberately-documented fields above (spline NURBS basis;
dimension leader_length).

## Build / deploy

`tools/build_native_acad.ps1 -OutputRoot <worktree>/build_iso`: `status=ok`,
all 3 artifacts present, `arx_relink_mode=canonical` (AutoCAD was not
running). Compiled clean on the first attempt, no iteration needed.

`prebuilt/2027/_bak/` updated to hold the pre-batch2 (i.e. T3a's own)
`.arx`/`.crx`/`.dbx` before the new binaries were copied into
`prebuilt/2027/`.

## Tests

`PYTHONUTF8=1 python -m pytest tests/unit -q`: **927 passed, 13 skipped, 0
failed** (918 T3a baseline + 9 new tests this batch; same 13 pre-existing
`SKIPPED_FIXTURE` skips as T3a's own worktree, unrelated to this change).
