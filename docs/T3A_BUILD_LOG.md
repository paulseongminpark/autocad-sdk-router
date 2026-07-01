# T3a build log — extraction completeness (ellipse/dimension/text/mtext/polyline)

Branch `cados/w3-t3a`, parent `cados/wave0-build` @ `67c53b5`. Worktree:
`D:\dev\99_tools\autocad-sdk-router__w3_t3a`.

## Root gap (T1 state)

`src/Ariadne.AcadNative/AriadneNativeJob.cpp::collectModelSpaceGraph` — the
only function `inspect.database.graph` calls — had no `AcDbEllipse` branch, no
`AcDbDimension`-subclass branch, and its `AcDbText`/`AcDbMText`/`AcDbPolyline`
branches never surfaced height/bulge/closed even though the write handlers set
them. `op_roundtrip_probe.py` documented `create_ellipse`/`create_dimension`
as genuinely unbuildable for exactly this reason (commit `67c53b5`).

## What changed

1. `src/Ariadne.AcadNative/AriadneNativeJob.cpp`
   - `#include "dbelipse.h"` / `#include "dbdim.h"`.
   - New `AcDbEllipse::cast` branch: `center`, `major_axis`, `radius_ratio`,
     `start_angle`, `end_angle`, `normal`.
   - New `AcDbRotatedDimension::cast` branch (appended after Hatch):
     `xline1_point`, `xline2_point`, `dim_line_point`, `rotation`,
     `measurement` (via `AcDbDimension::measurement()`, guarded by its
     ErrorStatus — omitted, never faked, if it fails), plus
     `dim_block_handle`/`dim_block_name` (dimBlockId resolved the same way
     `AcDbBlockReference`'s `block_name` already is).
   - `AcDbText`/`AcDbMText` branches now also emit `height`.
   - `AcDbPolyline` (LWPOLYLINE) branch now emits per-vertex `bulge`
     (`getBulgeAt`) and entity-level `closed` (`isClosed()`); vertex shape
     changed from bare `[x,y,z]` to `{"point":[x,y,z],"bulge":b}` so
     `ir_builder.py`'s existing vertex-lifting branch (already built to accept
     this shape) picks it up with zero change there.
   - All doubles already flow through the existing `kJsonDoublePrecision`
     (`.precision(17)`) ostringstream from the north-star precision fix —
     no separate work needed.

2. `tools/ir_builder.py` (`_geometry_from_native_entity` / `_entity_from_native`)
   — the raw-JSON-to-IR lift is a fixed allowlist, not a passthrough, so the
   new C++ fields would have been silently dropped without this:
   - Point-lift loop extended: `major_axis`, `xline1_point`, `xline2_point`,
     `dim_line_point`.
   - Number-lift loop extended: `radius_ratio`, `height`, `measurement`.
   - `dim_block_handle`/`dim_block_name` lifted as **top-level** entity
     fields (mirroring the existing `block_record_handle` convention) —
     deliberately kept OUTSIDE `"geometry"` (see rationale below).

3. `tools/op_roundtrip_probe.py`
   - `_expect_create_ellipse`: direct pass-through of every ctor arg (same
     pattern as `_expect_create_arc`).
   - `_expect_create_dimension` + two helpers:
     - `_rotated_dimension_measurement`: independently computes the
       xLine1→xLine2 vector projected onto the rotation direction.
     - `_rotated_dimension_line_point`: **live-discovered** — see below.
   - `_expect_create_text` / `_expect_create_mtext`: now assert `height`
     (was explicitly asserted ABSENT before T3a; that assertion is gone).
   - `_expect_create_polyline`: now asserts per-vertex `bulge` + `closed`
     (was explicitly asserted ABSENT before T3a).
   - `_EXPECTED_ENTITY_BUILDERS`: added `create_ellipse`, `create_dimension`.
   - `dim_block_handle`/`dim_block_name` are **never** asserted in
     `_expect_create_dimension`'s output — see rationale.

4. Tests updated to match (`tests/unit/test_op_roundtrip_probe.py`,
   `tests/unit/test_ir_builder.py` — new `TestNativeGraphGeometryLifting`
   class covering the ir_builder.py lift with synthetic raw dicts, since
   `build_ir_from_database_graph` had zero non-live unit coverage before).

## Live discovery: `dim_line_point` does not survive as a raw echo

First live re-cert attempt (both a `rotation=0` and a `rotation=pi/4` case)
FAILED with `modified=1` on `create_dimension` — `xline1_point`,
`xline2_point`, `rotation`, and `measurement` all matched exactly, but
`dim_line_point` did not.

Reconstructed the transform from the two live results and confirmed it
algebraically (exact match to float precision on both cases):
AutoCAD keeps only the **perpendicular offset** of the input `dim_line` point
relative to `xLine1Point`, along `v = (-sin(rotation), cos(rotation))`, and
re-anchors it at `xLine2Point`:

```
stored_dim_line_point = xLine2Point + offset * v
where offset = (dim_line_input - xLine1Point) . v
```

Example (rotation=0): `xline1=(0,0) xline2=(100,0) dim_line_in=(50,20)` →
stored `(100.0, 20.0, 0.0)`, not `(50, 20, 0)`.

This is a genuine, deterministic, args-derivable AutoCAD behavior (not
live-DB-state-dependent like the anonymous block counter below), so
`_expect_create_dimension`'s ground truth now computes it via
`_rotated_dimension_line_point` instead of echoing the raw arg. Both
verification cases used an xLine1→xLine2 baseline PARALLEL to the rotation
direction (the common "measure along this axis" use of a rotated dimension);
behavior for a non-parallel baseline is unverified and out of this ticket's
scope.

## Why `dim_block_handle`/`dim_block_name` are extracted but never asserted

The dimension's defining anonymous block name (`*D246`, `*D1`, ...) is
AutoCAD's own incrementing counter — a function of how many anonymous blocks
already exist in the live drawing, not of this op's own args. Asserting it in
`_expect_create_dimension` would violate `expected_ir_for_op`'s "ground truth
from args alone, never a live read" contract, and since `cad_diff.py`'s
`comparison_basis="geometry"` fingerprints ONLY `entity["geometry"]`, keeping
these two fields at the top level of the IR entity (not nested in
`"geometry"`) means they are extracted (satisfying "dimBlockId text if
cheap") without ever being able to break the P-gate.

## Re-certification (real, unmocked)

Driver: ad-hoc script invoking `op_roundtrip_probe.probe_roundtrip()` directly
(real `patch_engine.apply_staged`, no injection), staging
`tests/fixtures/native_sample.dwg` fresh per op. Two full runs (first caught
the `dim_line_point` bug; second, after the fix, is the certified result):

| op | args | result |
|---|---|---|
| create_line (regression) | start/end | **PASS** diff=0 |
| create_circle (regression) | center/radius | **PASS** diff=0 |
| create_arc (regression) | center/radius/angles | **PASS** diff=0 |
| create_ellipse | center/normal/major_axis/radius_ratio/angles | **PASS** diff=0 |
| create_dimension (rotation=0) | xline1/xline2/dim_line/rotation | **PASS** diff=0 |
| create_dimension (rotation=pi/4) | xline1/xline2/dim_line/rotation | **PASS** diff=0 |
| create_text | position/text/height | **PASS** diff=0 |
| create_mtext | position/text/height | **PASS** diff=0 |
| create_polyline | points w/ bulge + closed | **PASS** diff=0 |

9/9 ok. `tests/fixtures/native_sample.dwg` confirmed byte-identical
(git-clean, sha256 unchanged) after both runs — original READ-ONLY invariant
held. No residual gaps.

## Build / deploy

`tools/build_native_acad.ps1 -OutputRoot <worktree>/build_iso`: `status=ok`,
all 3 artifacts present, `arx_relink_mode=canonical` (AutoCAD was not running;
clean canonical relink, no versioned-lock-bypass needed).

`prebuilt/2027/_bak/` created holding the pre-T3a `.arx`/`.crx`/`.dbx` (in
addition to git history) before the new binaries were copied into
`prebuilt/2027/`.

## Tests

`PYTHONUTF8=1 python -m pytest tests/unit -q`: **918 passed, 13 skipped, 0
failed.** The 13 skips are pre-existing `SKIPPED_FIXTURE` gates tied to
`runs/` artifacts from prior live sessions that exist in the main repo
checkout but not in this fresh worktree (verified: 923 baseline passed in the
original checkout − 13 that become skips here + 4 new
`test_op_roundtrip_probe.py` tests + 4 new `test_ir_builder.py` tests = 918);
zero relation to this change.
