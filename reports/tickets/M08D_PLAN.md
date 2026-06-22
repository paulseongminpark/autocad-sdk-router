# M08D_PLAN — native READ family D: entities / geometry-kernel / BRep-solid topology

Owner file: `src/Ariadne.AcadNative/families/m08d_handlers.inc` (ONLY source I edit).
Seam: `m08dHasOp(op)` + `m08dDispatch(op, ctx, r)` `#include`d into `AriadneNativeJob.cpp`
(TU sees every in-TU helper). Result envelope: append `"result":{...},"status":"ok"}` on
success; `emitNativeError(r,"CODE","msg")` on error. `AriadneJobCtx{ job, pDb, hostMode }`.

All 73 ops are READS → read-only. No original DWG write, no `acedCommand*`, UTF-8 via `njsonStr`.

## Build-reachability analysis (the decisive constraint)

The `.crx`/`.arx` vcxproj `AdditionalIncludeDirectories` = `C:\ObjectARX 2027\inc;inc-x64` ONLY;
link deps (via `arx.props`) = `accore.lib;acad.lib;acui26.lib;adui26.lib` (+ acge/acdb pulled by
those). **I may NOT edit the vcxproj.** Consequences:

- **AcGe + AcDbEntity + AcDbCurve + subentity (`dbmain.h`, `dbsubeid.h`, `ge*.h`)**: headers on
  the main `inc` path; `acge26.lib`/`acdb26.lib` already linked. → Groups A + B fully buildable.
- **AcBr (BRep)**: headers live in `C:\ObjectARX 2027\utils\brep\inc\` (NOT on include path). The
  research slice claimed the import lib is `AcDrawBridge.lib` — **VERIFIED WRONG at build time**:
  `dumpbin /LINKERMEMBER AcDrawBridge.lib` shows only `Config@DrawBridge` localization symbols, ZERO
  AcBr. The REAL AcBr import lib is **`C:\ObjectARX 2027\utils\brep\lib-x64\acbr26.lib`** (274 AcBr
  symbols) + `acgex26.lib`; `AcDb3dSolid`/`AcGeNurbSurface` come from `acgeoment.lib` (the brep
  SAMPLE's own `AdditionalDependencies`). I reach all of this WITHOUT editing the vcxproj, inside my
  `.inc` only: (1) absolute `#include "C:\\ObjectARX 2027\\utils\\brep\\inc\\<hdr>.h"`,
  (2) `#pragma comment(lib, "C:\\ObjectARX 2027\\utils\\brep\\lib-x64\\acbr26.lib")` (+ acgex26.lib by
  absolute path; + `acgeoment.lib` by name since lib-x64 is on the path). Legal in-TU, keeps the
  disjoint-file contract. **RESULT: builds exit 0 — the AcBr group is NOT hard-blocked.**

## Priority order (implement + build-verify as I go; PARTIAL_PASS acceptable)

### Group A — entities (4) — CERTAIN (main-path headers)
Each: `resolveHandle(pDb, handle_hex, id)` → `acdbOpenObject(pEnt, id, kForRead)` →
`serializeEntityCommon(pEnt)` + op-specific.
| op | API (cited) | result |
|---|---|---|
| inspect.entity.common | `AcDbEntity::layer/colorIndex/linetype/lineWeight/visibility` (dbmain.h getters; entities-slice row "inspect.entity.common") | entity-common block (already serializeEntityCommon) + lineweight |
| inspect.entity.geomextents | `AcDbEntity::getGeomExtents(AcDbExtents&)` (dbmain.h:1997; AcDbExtents::minPoint/maxPoint dbmain.h:2567-2568) | min[x,y,z], max[x,y,z] |
| inspect.entity.osnap | `AcDbEntity::getOsnapPoints(mode,gsMark,pickPt,lastPt,xform,AcGePoint3dArray&,...)` (dbmain.h:2056; OsnapMode acdb.h:378) | snap point array (kOsModeEnd default) |
| inspect.curve.protocol | `AcDbCurve::getStartPoint/getEndPoint/isClosed/isPlanar/getArea` (dbcurve.h:36-107) | is_curve, start, end, closed, planar, area(if closed) |

### Group B — geometry_kernel (18) — CERTAIN (AcGe pure compute, main-path headers)
Pure-geometry ops read args from JSON (`parsePointPayload`/`jsonFindObject`/`jsonFindNumber`),
build the AcGe object, compute, emit. No DB needed (host-less).
| op | API (cited, entities-geometry-graphics slice) |
|---|---|
| compute.geometry.point.distance | `AcGePoint3d::distanceTo` (gepnt3d.h:75) — two points a,b |
| compute.geometry.point.transform | `AcGePoint3d::transformBy(AcGeMatrix3d)` (gepnt3d.h) — point + matrix(translate) |
| compute.geometry.matrix.build | `AcGeMatrix3d::setToTranslation/setToScaling/setToRotation` (gemat3d.h:101-104) → emit 4x4 |
| compute.geometry.matrix.compose | `AcGeMatrix3d::preMultBy` + `inverse(AcGeMatrix3d&,tol)` (gemat3d.h:182) |
| compute.geometry.scale.build | `AcGeScale3d(factor)`/`(sx,sy,sz)`, `isProportional` (gescl3d.h:33-57) |
| compute.geometry.lineseg | `AcGeLineSeg3d(p1,p2)` length/midpoint (gelnsg3d.h) |
| compute.geometry.circarc | `AcGeCircArc3d(center,normal,radius)` (gearc3d.h) |
| compute.geometry.elliparc | `AcGeEllipArc3d` (geell3d.h) |
| compute.geometry.tolerance | `AcGeTol` equalPoint/equalVector (getol.h) |
| compute.geometry.curve.eval | `AcGeCircArc3d::evalPoint(param)` via AcGeCurve3d (gecurv3d.h:218) |
| compute.geometry.curve.sample | `AcGeCurve3d::getSamplePoints(numSample, arr)` (gecurv3d.h:228) |
| compute.geometry.curve.closest | `AcGeCurve3d::getClosestPointTo(pnt, AcGePointOnCurve3d&)` (gecurv3d.h:77) |
| compute.geometry.curve.intersect | `AcGeCurveCurveInt3d` (gecint3d.h) numIntPoints/getIntPoint |
| compute.geometry.nurbcurve | `AcGeNurbCurve3d(degree,knots,ctrlPts,...)` eval (genurb3d.h) |
| compute.geometry.compositecurve | `AcGeCompositeCurve3d(curveList)` (gecomp3d.h) |
| compute.geometry.surface.nurb | `AcGeNurbSurface` evalPoint (genurbsf.h) |
| compute.entity.intersect | `AcDbEntity::intersectWith(pEnt,kOnBothOperands,AcGePoint3dArray&)` (dbmain.h:2098; Intersect acdb.h:82) — DB: two handles |
| compute.solid3d.interference | `AcDb3dSolid::checkInterference(other,false,bool&)` (dbsol3d.h) — DB: two solid handles |

### Group C — brep_solids (51) — BUILD-GATED (AcBr via absolute-include + pragma-lib)
8 `inspect.subentity.*` are `dbmain.h`/`dbsubeid.h` (main path, no AcBr) — implement first within C.
Then AcBr binding/compute/traversal. Canonical idiom (brep-topology slice): default-construct AcBr
obj, `set(*pEnt)` (brep) or traverser `setBrep/setFace/...` → `while(!t.done()){ t.getX(x); ...; t.next(); }`,
check `AcBr::ErrorStatus` (eOk=0). All bound via `resolveHandle` → entity must be 3dSolid/Surface/Region/Body.

Subentity (main-path, no AcBr lib):
- inspect.subentity.geom_extents `getSubentPathGeomExtents` (dbmain.h:2029)
- inspect.subentity.class_id `getSubentClassId` (dbmain.h:2007)
- inspect.subentity.ptr `subentPtr` (dbmain.h:2054) — materialize transient, report class/extents, delete
- (markers_at_path / path_at_marker / color / highlight = editor/GS-marker or unverified header → DEFER, see below)

AcBr brep-level (brent.h/brbrep.h):
- inspect.brep.from_entity `AcBrBrep::set(const AcDbEntity&)` (brbrep.h:75)
- inspect.brep.validate `checkEntity()` (brent.h:242)
- inspect.brep.changed `brepChanged()` (brent.h:266)
- inspect.brep.validation_level `getValidationLevel(AcBr::ValidationLevel&)` (brent.h:265)
- inspect.brep.bounds `getBoundBlock(AcGeBoundBlock3d&)` + `getMinMaxPoints` (brent.h:248, geblok3d.h:39)
- inspect.brep.owner `getBrep(AcBrBrep&)` (brent.h:261)
- inspect.brep.solid_roundtrip `AcBrBrep::get(AcDb3dSolid*&)` (brbrep.h:78) — clone-out, report type, delete
- inspect.brep.from_subentpath `set(AcDbFullSubentPath)` (whole-brep null subent)
- compute.brep.volume `getVolume(double&)` (brent.h:279)
- compute.brep.surface_area `getSurfaceArea(double&)` (brent.h:282)
- compute.brep.perimeter `getPerimeterLength(double&)` (brent.h:285)
- compute.brep.massprops `getMassProps(AcBrMassProps&)` (brent.h:275; struct brprops.h: mVolume/mMass/mCentroid/mRadiiGyration[3]/mMomInertia[3]/mProdInertia[3]/mPrinMoments[3]/mPrinAxes[3])
- compute.brep.point_containment `getPointContainment(pt,AcGe::PointContainment&,AcBrEntity*&)` (brent.h:251; kInside/kOutside/kOnBoundary gegblabb.h:150)
- compute.brep.line_containment `getLineContainment` (brent.h; AcBrHit brhit.h)

AcBr traversal counts + per-element inspect (brb?trav.h / br*.h):
- traverse.brep.{complexes,shells,faces,edges,vertices} — `AcBrBrep{Complex,Shell,Face,Edge,Vertex}Traverser` setBrep/get/next/done → count
- traverse.complex.shells / shell.faces / face.loops / loop.edges / loop.vertices / edge.loops / vertex.edges / vertex.loops — hierarchical/upward traversers → count (needs a bound parent; brep-level walk to first parent of the right kind, then count its children)
- inspect.face.{area,orientation,shell,surface,surface_type} — AcBrFace getArea/getOrientToSurface/getShell/getSurface(type)/getSurfaceType (brface.h:161-181)
- inspect.face.surface_as_nurb / surface_as_trimmed_nurbs — getSurfaceAsNurb / getSurfaceAsTrimmedNurbs (brface.h) — report success + counts, delete[]
- inspect.edge.{curve,curve_type,orientation,vertices} — AcBrEdge getCurve/getCurveType/getOrientToCurve/getVertex1+2 (bredge.h:157-164)
- inspect.edge.curve_as_nurb — getCurveAsNurb (bredge.h)
- inspect.vertex.point — AcBrVertex getPoint(AcGePoint3d&) (brvtx.h:85)
- inspect.loop.{type,face} — AcBrLoop getType/getFace (brloop.h:72-75)
- inspect.shell.{type,complex} — AcBrShell getType/getComplex (brshell.h)

For the per-element inspect ops I bind the FIRST element of that kind (first face/edge/loop/vertex/shell
via the brep→…→first traverser step) and report its property + an `index:0` note + `element_count`.
This is a real, verifiable read (no fabrication); deeper per-index addressing is a documented follow-up.

## Deferred / hard-blocked (out of m08dHasOp; honest catalogued-remaining)
- `ui.subentity.highlight` — attended/graphics (needs live editor + GS flush). Brief says defer. DEFER (attended-only).
- `inspect.subentity.markers_at_path`, `inspect.subentity.path_at_marker` — `native_arx_only` + `editor` (GS marker from interactive pick; no marker source headless). DEFER (editor-bound).
- `inspect.subentity.color` — `AcDbSubentColor` header "[unverified]" in slice (not located in inc this session). DEFER until header confirmed (no fake).
- Any AcBr op that fails to compile/link via absolute-include + pragma-lib → the entire AcBr subset is HARD_BLOCKED (vcxproj edit needed), left out of HasOp, reported with the exact compiler/linker error. Subentity (main-path) + Groups A/B remain.

## Tests — tests/unit/test_m08d_handlers.py (source-contract, no AutoCAD needed)
- m08dHasOp ⟷ m08dDispatch: every op the `.inc` lists in HasOp has a `op == "..."` branch in Dispatch (regex parse of the .inc), and vice-versa (no drift → no OPERATION_DISPATCH_MISMATCH).
- read-only: the `.inc` contains no `->save(`/`saveAs`/`acedCommand`/`abortTransaction` write-escape; uses AriadneReadTransaction/kForRead only.
- UTF-8: string emission goes through `njsonStr(` (no raw `acharToAscii` into the JSON, no lossy funnel).
- count assertion: implemented-op count matches the PLAN's HasOp list (guards silent shrink).

## Workflow
1. branch cados/M08D ✓. 2. this PLAN ✓. 3. implement .inc (A→B→C, build-verify each). 
4. `powershell -File tools/build_native_acad.ps1` exit 0. 5. pytest tests/unit -q green.
6. commit + push -u origin cados/M08D; PR base main. 7. reports/tickets/M08D.{md,json} + packets/tickets/M08D.md + handoff/tickets/M08D.zip.
