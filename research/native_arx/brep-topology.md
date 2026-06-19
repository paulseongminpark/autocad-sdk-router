## Slice: brep-topology

ObjectARX 2027 **AcBr** (Autodesk Boundary Representation) library — the topology + subentity layer
that sits on top of an `AcDb3dSolid` / `AcDbSurface` / `AcDbRegion` / `AcDbBody`. This slice covers the
**read-only B-Rep query + topology traversal + subentity addressing** surface. It deliberately does NOT
re-catalog solid creation / booleans / loft / `getArea` / `getMassProp` on `AcDb3dSolid` (covered by the
entities slice). AcBr is the layer that lets an agent walk a solid's faces/loops/edges/vertices, pull the
underlying `AcGe` surface/curve geometry per face/edge, classify point/line containment, and address +
transform + highlight individual subentities by `AcDbFullSubentPath`.

**Provenance of every API below:** read this session from the local ObjectARX 2027 headers under
`C:\ObjectARX 2027\utils\brep\inc\` (exact signatures), the brep sample sources under
`C:\ObjectARX 2027\utils\brep\samples\brepsamp\` (usage idiom), `C:\ObjectARX 2027\inc\acdb.h` +
`dbmain.h` (subentity addressing), and the Autodesk Help MCP OARX-2027 Reference/Developer guides (GUIDs
cited). Anything I could not positively verify this session is tagged **[unverified]** and never invented.

---

### Operation catalog

ENGINE_TIER legend: `native_arx_only` = needs full ObjectARX C++ link (acdb26/accore/AcDrawBridge);
`objectdbx_capable` = pure database/geometry query, no AutoCAD editor/UI dependency → callable from a host
that opens the .dwg via the ObjectDBX/`AcDbDatabase` surface **and** links AcDrawBridge.lib (in-process,
e.g. accoreconsole-hosted; standalone RealDWG host is EXCLUDED from license per packet);
`managed_also` = a .NET `BrepBuilder`/`Brep` (Autodesk.AutoCAD.BoundaryRepresentation) wrapper exists;
`accoreconsole_lisp_also` = reachable from AutoLISP/COM at coarse granularity.

`dwg_persisted` column: `read-only` = pure query, original DWG byte-unchanged; `mutates-subent` = writes
back to the entity (subentity transform). `execution_context`: `hostless_dbx` = works against a
DB-resident entity with no editor; `editor` = needs interactive pick / GS-marker / highlight (graphics).

| proposed_op_id | native API (class::method) | engine_tier | what it does | key inputs | key outputs | dwg_persisted? | execution_context | citation |
|---|---|---|---|---|---|---|---|---|
| `inspect.brep.from_entity` | `AcBrBrep::set(const AcDbEntity&)` | objectdbx_capable | Bind an AcBrBrep to a database-resident solid/surface/region/body (the entry point when you already hold the entity, no subent pick) | `const AcDbEntity&` (must be AcDb3dSolid/AcDbRegion/AcDbBody) | initialized `AcBrBrep`; `eWrongObjectType` otherwise | read-only | hostless_dbx | brbrep.h `set(const AcDbEntity&)`; sample brselect.cpp `((AcBrBrep*)pEnt)->set((const AcDbEntity&)*pEntity)` |
| `inspect.brep.from_subentpath` | `AcBrEntity::set(const AcDbFullSubentPath&)` / `setSubentPath(AcDbFullSubentPath&)` | objectdbx_capable | Bind ANY AcBr topology object (brep/face/edge/vertex) to a specific subentity path (with full nested-blockref transform chain) | `AcDbFullSubentPath` (objId array + AcDbSubentId; `kNullSubentId` for whole brep) | initialized AcBr object; rich `AcBr::ErrorStatus` (`eWrongSubentityType`, `eNullObjectId`, …) | read-only | hostless_dbx (path may come from editor pick) | brent.h `set(const AcDbFullSubentPath&)`, `setSubentPath(...)`; sample bredump.cpp `newVertex.set(subPath)` |
| `inspect.brep.solid_roundtrip` | `AcBrBrep::get(AcDb3dSolid*&)` / `get(AcDbSurface*&)` | objectdbx_capable | Return a NEW copy of the internal solid/surface from the AcBrBrep (clone-out, caller owns) | bound `AcBrBrep` | `AcDb3dSolid*` / `AcDbSurface*` (new) | read-only | hostless_dbx | brbrep.h `get(AcDb3dSolid*&)`, `get(AcDbSurface*&)`; MCP GUID OARX-RefGuide-AcBrBrep__get_AcDb3dSolid |
| `inspect.brep.bounds` | `AcBrEntity::getBoundBlock(AcGeBoundBlock3d&)` | objectdbx_capable | Model-space bounding block of any topology object, full transform chain applied | bound AcBr object | `AcGeBoundBlock3d` | read-only | hostless_dbx | brent.h `getBoundBlock`; MCP AcBrEntity Methods |
| `inspect.brep.validate` | `AcBrEntity::checkEntity()` | objectdbx_capable | Validate topology+geometry+data-structure of the entity | bound AcBr object | `Adesk::Boolean` (true = no errors) | read-only | hostless_dbx | brent.h `checkEntity`; MCP AcBrEntity Methods (`checkEntity`) |
| `inspect.brep.changed` | `AcBrEntity::brepChanged()` | objectdbx_capable | Has owning AutoCAD object changed since this AcBr obj was last set (cache-coherency guard) | bound AcBr object | `Adesk::Boolean` | read-only | hostless_dbx | brent.h `brepChanged`; MCP AcBrEntity Methods |
| `inspect.brep.validation_level` | `AcBrEntity::setValidationLevel / getValidationLevel(AcBr::ValidationLevel&)` | objectdbx_capable | Set kFullValidation/kNoValidation (perf knob; kNoValidation suppresses eBrepChanged) | `AcBr::ValidationLevel` | level / status | read-only | hostless_dbx | brent.h; brgbl.h enum ValidationLevel {kFullValidation=0,kNoValidation=1} |
| `traverse.brep.complexes` | `AcBrBrepComplexTraverser::setBrep / getComplex / next / done / restart` | objectdbx_capable | Iterate the complexes (lumps) of a brep | `AcBrBrep` | per-step `AcBrComplex` | read-only | hostless_dbx | brbctrav.h; MCP Traverser Classes |
| `traverse.brep.shells` | `AcBrBrepShellTraverser::setBrep / getShell / next / done` | objectdbx_capable | Iterate all shells of a brep (flattened) | `AcBrBrep` | per-step `AcBrShell` | read-only | hostless_dbx | brbstrav.h |
| `traverse.brep.faces` | `AcBrBrepFaceTraverser::setBrep / getFace / next / done / restart` | objectdbx_capable | Iterate all faces of a brep (the common "list faces" walk) | `AcBrBrep` | per-step `AcBrFace` | read-only | hostless_dbx | brbftrav.h; MCP AcBrBrep "used to set the BREP owner of an AcBrBrepFaceTraverser" |
| `traverse.brep.edges` | `AcBrBrepEdgeTraverser::setBrep / getEdge / next / done` | objectdbx_capable | Iterate all edges of a brep (flattened, de-duplicated) | `AcBrBrep` | per-step `AcBrEdge` | read-only | hostless_dbx | brbetrav.h |
| `traverse.brep.vertices` | `AcBrBrepVertexTraverser::setBrep / getVertex / next / done` | objectdbx_capable | Iterate all vertices of a brep | `AcBrBrep` | per-step `AcBrVertex` | read-only | hostless_dbx | brbvtrav.h |
| `traverse.complex.shells` | `AcBrComplexShellTraverser::setComplex / getShell / next / done` | objectdbx_capable | Iterate shells within one complex | `AcBrComplex` | `AcBrShell` | read-only | hostless_dbx | brcstrav.h |
| `traverse.shell.faces` | `AcBrShellFaceTraverser::setShell / getFace / next / done` | objectdbx_capable | Iterate faces of one shell | `AcBrShell` | `AcBrFace` | read-only | hostless_dbx | brsftrav.h |
| `traverse.face.loops` | `AcBrFaceLoopTraverser::setFace / getLoop / next / done` | objectdbx_capable | Iterate the loops bounding a face (exterior + interior holes) | `AcBrFace` | `AcBrLoop` | read-only | hostless_dbx | brfltrav.h |
| `traverse.loop.edges` | `AcBrLoopEdgeTraverser::setLoop / getEdge / getEdgeOrientToLoop / getParamCurve / getOrientedCurve / next / done` | objectdbx_capable | Walk edges around a loop, with per-edge loop-orientation flag, 2D param-curve (pcurve) and oriented 3D curve | `AcBrLoop` (or `AcBrFaceLoopTraverser`) | `AcBrEdge`, `Adesk::Boolean` orient, `AcGeCurve2d*` pcurve, `AcGeCurve3d*` oriented curve | read-only | hostless_dbx | brletrav.h `setLoop/getEdge/getEdgeOrientToLoop/getParamCurve/getOrientedCurve` |
| `traverse.loop.vertices` | `AcBrLoopVertexTraverser::setLoop / getVertex / getParamPoint / next / done` | objectdbx_capable | Walk vertices of a loop (used for singularity loops, e.g. cone apex); next()/restart() return eNotApplicable on this traverser by design | `AcBrLoop` | `AcBrVertex`, `AcGePoint2d` param point | read-only | hostless_dbx | brlvtrav.h; brgbl.h note (`eNotApplicable … on AcBrLoopVertexTraverser`) |
| `traverse.edge.loops` | `AcBrEdgeLoopTraverser::setEdge / getLoop / next / done` | objectdbx_capable | UPWARD walk: which loops use this edge (an edge is shared by ≤2 loops) | `AcBrEdge` | `AcBrLoop` | read-only | hostless_dbx | breltrav.h |
| `traverse.vertex.edges` | `AcBrVertexEdgeTraverser::setVertex / getEdge / next / done` | objectdbx_capable | UPWARD walk: edges incident to this vertex | `AcBrVertex` | `AcBrEdge` | read-only | hostless_dbx | brvetrav.h |
| `traverse.vertex.loops` | `AcBrVertexLoopTraverser::setVertex / getLoop / next / done` | objectdbx_capable | UPWARD walk: loops incident to this vertex | `AcBrVertex` | `AcBrLoop` | read-only | hostless_dbx | brvltrav.h |
| `inspect.face.surface` | `AcBrFace::getSurface(AcGeSurface*&)` | objectdbx_capable | Underlying surface of a face as an AcGe external bounded surface (full transform chain applied; caller owns) | `AcBrFace` | `AcGeSurface*` (AcGeExternalBoundedSurface) | read-only | hostless_dbx | brface.h `getSurface`; MCP GUID OARXMAC-RefGuide-AcBrFace__getSurface |
| `inspect.face.surface_type` | `AcBrFace::getSurfaceType(AcGe::EntityId&)` | objectdbx_capable | Best-match native surface kind (plane/cylinder/cone/sphere/torus/nurb… or kExternalBoundedSurface) for fast filtering | `AcBrFace` | `AcGe::EntityId` | read-only | hostless_dbx | brface.h `getSurfaceType` |
| `inspect.face.surface_as_nurb` | `AcBrFace::getSurfaceAsNurb(AcGeNurbSurface&, fitTol*)` | objectdbx_capable | Face surface forced to a NURBS (subset to face uv-box) | `AcBrFace`, fitTol | `AcGeNurbSurface` | read-only | hostless_dbx | brface.h `getSurfaceAsNurb` |
| `inspect.face.surface_as_trimmed_nurbs` | `AcBrFace::getSurfaceAsTrimmedNurbs(UInt32&, AcGeExternalBoundedSurface**&)` | objectdbx_capable | Face as an array of trimmed-NURBS patches (seam-split); caller delete[]s | `AcBrFace` | count + `AcGeExternalBoundedSurface**` | read-only | hostless_dbx | brface.h `getSurfaceAsTrimmedNurbs` |
| `inspect.face.orientation` | `AcBrFace::getOrientToSurface(Adesk::Boolean&)` | objectdbx_capable | Is face outside-normal aligned with surface normal (kTrue) or flipped | `AcBrFace` | `Adesk::Boolean` | read-only | hostless_dbx | brface.h; MCP GUID OARX-RefGuide-AcBrFace__getOrientToSurface |
| `inspect.face.shell` | `AcBrFace::getShell(AcBrShell&)` | objectdbx_capable | Owning shell of a face (upward) | `AcBrFace` | `AcBrShell` | read-only | hostless_dbx | brface.h `getShell` |
| `inspect.face.area` | `AcBrFace::getArea(double&, tol*)` | objectdbx_capable | Area of a single face (note: base `getSurfaceArea` on a face returns eNotApplicable — use this) | `AcBrFace`, tol | `double` area | read-only | hostless_dbx | brface.h `getArea` (distinct from AcBrEntity::getSurfaceArea) |
| `inspect.edge.curve` | `AcBrEdge::getCurve(AcGeCurve3d*&)` | objectdbx_capable | Underlying 3D curve of an edge (oriented in edge direction; full transform chain; caller owns) | `AcBrEdge` | `AcGeCurve3d*` (AcGeExternalCurve3d) | read-only | hostless_dbx | bredge.h `getCurve`; MCP GUID OARX-RefGuide-AcBrEdge__getCurve |
| `inspect.edge.curve_type` | `AcBrEdge::getCurveType(AcGe::EntityId&)` | objectdbx_capable | Best-match native curve kind (line/arc/circle/ellipse/nurb… or kExternalCurve3d) | `AcBrEdge` | `AcGe::EntityId` | read-only | hostless_dbx | bredge.h `getCurveType` |
| `inspect.edge.curve_as_nurb` | `AcBrEdge::getCurveAsNurb(AcGeNurbCurve3d&, fitTol*)` | objectdbx_capable | Edge curve forced to a NURBS | `AcBrEdge`, fitTol | `AcGeNurbCurve3d` | read-only | hostless_dbx | bredge.h `getCurveAsNurb` |
| `inspect.edge.orientation` | `AcBrEdge::getOrientToCurve(Adesk::Boolean&)` | objectdbx_capable | Is edge natural v1→v2 direction aligned with curve param (apply via AcGeCurve3d::reverseParam) | `AcBrEdge` | `Adesk::Boolean` | read-only | hostless_dbx | bredge.h `getOrientToCurve` |
| `inspect.edge.vertices` | `AcBrEdge::getVertex1(AcBrVertex&)` / `getVertex2(AcBrVertex&)` | objectdbx_capable | Start/end vertices of an edge (eDegenerateTopology if a null/closed-loop edge) | `AcBrEdge` | two `AcBrVertex` | read-only | hostless_dbx | bredge.h `getVertex1/getVertex2` |
| `inspect.vertex.point` | `AcBrVertex::getPoint(AcGePoint3d&)` | objectdbx_capable | 3D position of a vertex (transform chain applied) | `AcBrVertex` | `AcGePoint3d` | read-only | hostless_dbx | brvtx.h `getPoint` |
| `inspect.loop.type` | `AcBrLoop::getType(AcBr::LoopType&)` | objectdbx_capable | Classify loop: exterior / interior(hole) / winding / unclassified | `AcBrLoop` | `AcBr::LoopType` | read-only | hostless_dbx | brloop.h `getType`; MCP GUID OARX-RefGuide-AcBrLoop__getType |
| `inspect.loop.face` | `AcBrLoop::getFace(AcBrFace&)` | objectdbx_capable | Owning face of a loop (upward) | `AcBrLoop` | `AcBrFace` | read-only | hostless_dbx | brloop.h `getFace` |
| `inspect.shell.type` | `AcBrShell::getType(AcBr::ShellType&)` | objectdbx_capable | Classify shell: exterior(peripheral) / interior(void) / unclassified | `AcBrShell` | `AcBr::ShellType` | read-only | hostless_dbx | brshell.h `getType` |
| `inspect.shell.complex` | `AcBrShell::getComplex(AcBrComplex&)` | objectdbx_capable | Owning complex of a shell (upward) | `AcBrShell` | `AcBrComplex` | read-only | hostless_dbx | brshell.h `getComplex` |
| `inspect.brep.owner` | `AcBrEntity::getBrep(AcBrBrep&)` | objectdbx_capable | From any topology object, get the top-of-hierarchy AcBrBrep (used in upward walks) | any AcBr object | `AcBrBrep` | read-only | hostless_dbx | brent.h `getBrep`; sample bredump.cpp `edgeEntity.getBrep(brepOwner)` |
| `compute.brep.massprops` | `AcBrEntity::getMassProps(AcBrMassProps&, density*, tolReq*, tolAch*)` | objectdbx_capable | Full mass properties (volume, mass, centroid, radii-of-gyration, moments+products of inertia, principal moments+axes) at brep/complex/shell level (faces/loops/edges/vertices return eNotApplicable) | bound AcBr object (brep/complex/shell), optional density | `AcBrMassProps` struct | read-only | hostless_dbx | brent.h `getMassProps`; brprops.h struct AcBrMassProps {mVolume,mMass,mCentroid,mRadiiGyration[3],mMomInertia[3],mProdInertia[3],mPrinMoments[3],mPrinAxes[3]} |
| `compute.brep.volume` | `AcBrEntity::getVolume(double&, tolReq*, tolAch*)` | objectdbx_capable | Volume at brep/complex/shell level (eNotApplicable on face/loop/edge/vertex) | bound AcBr object | `double` volume | read-only | hostless_dbx | brent.h `getVolume` |
| `compute.brep.surface_area` | `AcBrEntity::getSurfaceArea(double&, tolReq*, tolAch*)` | objectdbx_capable | Total surface area at brep/complex/shell level (face uses getArea instead) | bound AcBr object | `double` area | read-only | hostless_dbx | brent.h `getSurfaceArea` |
| `compute.brep.perimeter` | `AcBrEntity::getPerimeterLength(double&, tolReq*, tolAch*)` | objectdbx_capable | Perimeter length of a topology object (eNotApplicable on AcBrVertex) | bound AcBr object | `double` length | read-only | hostless_dbx | brent.h `getPerimeterLength` |
| `compute.brep.point_containment` | `AcBrEntity::getPointContainment(const AcGePoint3d&, AcGe::PointContainment&, AcBrEntity*&)` | objectdbx_capable | Classify a point as kInside/kOutside/kOnBoundary vs the topology; on-boundary returns the lowest-level containing subobject (e.g. the edge) | `AcGePoint3d`, bound AcBr object | `AcGe::PointContainment` + `AcBrEntity*` container (caller owns) | read-only | hostless_dbx | brent.h `getPointContainment`; MCP AcBrEntity Methods (`getPointContainment`) |
| `compute.brep.line_containment` | `AcBrEntity::getLineContainment(const AcGeLinearEnt3d&, const UInt32& numWanted, UInt32& numFound, AcBrHit*&)` | objectdbx_capable | Segment/ray/infinite-line vs topology: returns the in/out hit segmentation as an AcBrHit array (caller delete[]s) | `AcGeLinearEnt3d`, numWanted | `numFound` + `AcBrHit*` array | read-only | hostless_dbx | brent.h `getLineContainment`; brhit.h (AcBrHit) |
| `inspect.subentity.path_at_marker` | `AcDbEntity::getSubentPathsAtGsMarker(SubentType, GsMarker, AcGePoint3d&, AcDbMatrix… , int&, AcDbFullSubentPath*&)` | native_arx_only | From a picked GS marker (screen selection) produce the full subentity path(s) — the bridge from an interactive pick to an AcDbFullSubentPath you can feed AcBr | entity + SubentType + GS marker (from pick) | array of `AcDbFullSubentPath` | read-only | editor (needs GS marker / interactive pick) | dbmain.h:2033 `getSubentPathsAtGsMarker`; MCP AcDbEntity::getGsMarkersAtSubentPath (describes pairing) |
| `inspect.subentity.markers_at_path` | `AcDbEntity::getGsMarkersAtSubentPath(const AcDbFullSubentPath&, AcArray<Adesk::GsMarker>&)` | native_arx_only | Inverse: given a subent path, the GS markers that draw it (drives highlight/unhighlight) | entity + `AcDbFullSubentPath` | `AcArray<GsMarker>` | read-only | editor | dbmain.h:2044; MCP GUID OARX-RefGuide-AcDbEntity__getGsMarkersAtSubentPath |
| `inspect.subentity.class_id` | `AcDbEntity::getSubentClassId(const AcDbFullSubentPath&, CLSID*)` | native_arx_only | CLSID of the wrapper coclass for a subentity (custom-object subent typing) | entity + path | `CLSID` | read-only | hostless_dbx | dbmain.h:2007; MCP GUID OARX-RefGuide-AcDbEntity__getSubentClassId |
| `inspect.subentity.geom_extents` | `AcDbEntity::getSubentPathGeomExtents(const AcDbFullSubentPath&, AcDbExtents&)` | native_arx_only | Bounding extents of a single addressed subentity | entity + path | `AcDbExtents` | read-only | hostless_dbx | dbmain.h:2029 `getSubentPathGeomExtents` |
| `inspect.subentity.ptr` | `AcDbEntity::subentPtr(const AcDbFullSubentPath&)` | native_arx_only | Materialize a transient AcDbEntity* for the addressed subentity (e.g. the face/edge as a standalone entity) | entity + path | `AcDbEntity*` (caller owns) | read-only | hostless_dbx | dbmain.h:2054 `subentPtr` |
| `edit.subentity.transform` | `AcDbEntity::transformSubentPathsBy(const AcDbFullSubentPath[], const AcGeMatrix3d&)` | native_arx_only | **Direct modeling**: move/rotate/scale specific faces/edges/vertices in place (this WRITES to the entity) | entity (write) + path array + `AcGeMatrix3d` | mutated solid | mutates-subent | hostless_dbx (entity open-for-write) | dbmain.h:2011 `transformSubentPathsBy`; MCP AcDbSubentityOverrule (overrule pairing) |
| `edit.subentity.add_paths` | `AcDbEntity::addSubentPaths(const AcDbFullSubentPath[])` | native_arx_only | Add subentities (custom-object / associative authoring) | entity (write) + path array | status | mutates-subent | hostless_dbx | dbmain.h:2001 `addSubentPaths` |
| `edit.subentity.delete_paths` | `AcDbEntity::deleteSubentPaths(const AcDbFullSubentPath[])` | native_arx_only | Delete addressed subentities | entity (write) + path array | status | mutates-subent | hostless_dbx | dbmain.h:2004 `deleteSubentPaths` |
| `ui.subentity.highlight` | `AcDbEntity::highlight(const AcDbFullSubentPath&, Adesk::Boolean all)` / `unhighlight(...)` | native_arx_only | Highlight / unhighlight a subentity on screen (requires graphics flush; calls getGsMarkersAtSubentPath internally) | entity + path | screen highlight | read-only | editor (graphics) | dbmain.h:2048/2051; MCP GUID OARX-RefGuide-AcDbEntity__highlight / __unhighlight |
| `inspect.subentity.color` | `AcDbSubentColor` (per-subentity color override carrier) | native_arx_only **[unverified header line]** | Carry a per-subentity color (face coloring) | — | — | mutates-subent (when applied) | hostless_dbx | referenced by packet; class not located in inc/*.h this session — **[unverified]**, confirm header before use |

> Mesh side-note (present but out of this slice's core ask): the same AcBr lib also ships
> `AcBrMesh2d` + `AcBrMesh2dElement2dTraverser` + `AcBrElement2dNodeTraverser` (brmesh2d.h, brentrav.h,
> brelem2d.h, brnode.h) for tessellating a brep into a 2D element/node mesh with per-node surface normals
> and param points. Cataloged here only as existing capability; full mesh op-set is a separate slice.

---

### Classes & subsystems covered

**Topology object classes** (all derive `AcBrEntity : public AcRxObject`; default-construct then
`set()`/traverser-`get()`; all support copy ctor, assignment, `isEqualTo`, `isNull`):
- `AcBrEntity` (brent.h) — base: setSubentPath/getSubentPath, set/get(AcDbFullSubentPath), getBoundBlock,
  getPointContainment, getLineContainment, getBrep, getMassProps, getVolume, getSurfaceArea,
  getPerimeterLength, checkEntity, brepChanged, set/getValidationLevel.
- `AcBrBrep` (brbrep.h) — set(const AcDbEntity&), get(AcDb3dSolid*&), get(AcDbSurface*&); is the owner for
  the five `AcBrBrep*Traverser`s.
- `AcBrComplex` (brcplx.h) — **adds no methods of its own** (pure inherited); a lump/region of the brep.
- `AcBrShell` (brshell.h) — getComplex, getType (ShellType).
- `AcBrFace` (brface.h) — getSurface, getSurfaceType, getSurfaceAsNurb, getSurfaceAsTrimmedNurbs,
  getOrientToSurface, getShell, getArea.
- `AcBrLoop` (brloop.h) — getFace, getType (LoopType).
- `AcBrEdge` (bredge.h) — getCurve, getCurveType, getCurveAsNurb, getOrientToCurve, getVertex1, getVertex2.
- `AcBrVertex` (brvtx.h) — getPoint.

**Traverser classes** (all derive `AcBrTraverser : public AcRxObject`; `done()`, `next()`, `restart()`,
set/getValidationLevel, brepChanged) — 14 in this slice + 2 mesh:
- Downward from brep (flattened): `AcBrBrepComplexTraverser`, `AcBrBrepShellTraverser`,
  `AcBrBrepFaceTraverser`, `AcBrBrepEdgeTraverser`, `AcBrBrepVertexTraverser` (brb?trav.h).
- Hierarchical downward: `AcBrComplexShellTraverser` (brcstrav.h), `AcBrShellFaceTraverser` (brsftrav.h),
  `AcBrFaceLoopTraverser` (brfltrav.h), `AcBrLoopEdgeTraverser` (brletrav.h — richest: getEdgeOrientToLoop,
  getParamCurve 2D pcurve, getOrientedCurve 3D), `AcBrLoopVertexTraverser` (brlvtrav.h — for singularities).
- Upward adjacency: `AcBrEdgeLoopTraverser` (breltrav.h), `AcBrVertexEdgeTraverser` (brvetrav.h),
  `AcBrVertexLoopTraverser` (brvltrav.h).
- Mesh (adjacent capability): `AcBrMesh2dElement2dTraverser`, `AcBrElement2dNodeTraverser` (brentrav.h).
- Traverser set semantics (from MCP Developer Guide "Traverser Classes"): `setListOwner` (from AcBr obj or
  upstream traverser) defaults position to first; `setCurrentPosition` requires owner already set;
  `setListOwnerAndCurrentPosition` swaps owner/position between paired up/down traversers
  (e.g. AcBrLoopEdge ↔ AcBrEdgeLoop). Hence the `setBrepAndFace`/`setLoopAndEdge`/etc. convenience setters.

**Subentity addressing (AcDb layer, inc/, NOT the brep subdir):**
- `AcDb::SubentType` enum (`acdb.h:459-475`): `kNullSubentType=0, kFaceSubentType=1, kEdgeSubentType=2,
  kVertexSubentType=3, kMlineSubentCache=4, kClassSubentType=5, kAxisSubentType=6,
  kSilhouetteSubentType=7` (typedef Adesk::UInt32).
- `AcDbSubentId` (objId-less {type,index}) + `AcDbFullSubentPath` (objId chain + AcDbSubentId) — declared
  through `acdb.h`/`dbsubeid.h` include graph (referenced by all AcBr `set` calls; brep sample uses
  `AcDbFullSubentPath subPath(kNullSubent)`).
- `AcDbEntity` subentity virtuals (`dbmain.h:2001-2054`, all `ACDBCORE2D_PORT ADESK_SEALED_VIRTUAL`):
  addSubentPaths, deleteSubentPaths, getSubentClassId, transformSubentPathsBy, getSubentPathGeomExtents,
  getSubentPathsAtGsMarker, getGsMarkersAtSubentPath, highlight, unhighlight, subentPtr.
- `AcDbSubentityOverrule` (MCP GUID, reference guide) — the override surface for all of the above when
  authoring custom objects' subentities.

**AcBr global enums** (brgbl.h / `struct AcBr`): ErrorStatus (base 3000: eBrepChanged=3008,
eUnsuitableTopology=3013, eDegenerateTopology=3020, eUninitialisedObject=3021, plus Acad-aliased codes),
Relation, LoopType (kLoopExterior/Interior/Winding), ShellType (kShellExterior/Interior), ValidationLevel,
Element2dShape.

---

### Build / integration notes

- **AcBr headers do NOT live in the main `inc/` dir.** They are under
  `C:\ObjectARX 2027\utils\brep\inc\` (43 `br*.h` files). Add that to the compiler include path in addition
  to `C:\ObjectARX 2027\inc` and `inc-x64`. Key headers: `brent.h, brbrep.h, brcplx.h, brshell.h, brface.h,
  brloop.h, bredge.h, brvtx.h, brgbl.h, brprops.h, brhit.h` + the `br*trav.h` traversers.
- **Link library = `AcDrawBridge.lib`** — confirmed present in `C:\ObjectARX 2027\lib-x64\` (one of 33
  libs there). This is the AcBr import lib. Link it alongside the standard ObjectARX set:
  `acdb26.lib accore.lib acge26.lib rxapi.lib acgeoment.lib` (+ `acismobj26.lib` is also present if ASM
  surface internals are needed). All x64.
- **Canonical build reference**: `C:\ObjectARX 2027\utils\brep\samples\brepsamp\brsample.vcxproj` — a
  ready-made VS project that already wires the brep include dir + AcDrawBridge.lib. Mirror its settings for
  the router's native module. Sample sources to copy idioms from: `brselect.cpp` (entity→brep:
  `((AcBrBrep*)pEnt)->set((const AcDbEntity&)*pEntity)`, `pEnt->setValidationLevel(vlevel)`), `bredump.cpp`
  (`newVertex.set(subPath)`, `edgeEntity.getBrep(brepOwner)`, vertex/curve dump), plus `brdump/brfdump/
  brbdump/brmmesh/brptcnt/brlncnt/brtrmsrf` for face/mesh/containment/trimmed-nurbs dumps.
- **The canonical traversal idiom** (grounded in the sample dump files): default-construct the AcBr object
  and the traverser → `traverser.setBrep(brep)` (or setFace/setShell/setLoop) → loop
  `while (!traverser.done()) { traverser.getFace(face); /* query */ traverser.next(); }` → check the
  `AcBr::ErrorStatus` after each set/get. For upward walks build the leaf object via `set(subPath)` then
  `AcBrEdgeLoopTraverser::setEdge(edge)` etc. Always honor `brepChanged()`/eBrepChanged for cache coherency.
- **Hostless feasibility**: every `inspect.*` / `traverse.*` / `compute.*` op is a pure database+geometry
  query on a DB-resident solid/region/body and needs no editor — so they run in an **accoreconsole-hosted**
  in-process module (in scope per packet) the same way they run inside full AutoCAD. The only `editor`-bound
  ops are the GS-marker / highlight family (they need an interactive pick and live graphics). Standalone
  no-AutoCAD RealDWG hosting is EXCLUDED from license and therefore out of scope.
- **Memory ownership**: getSurface/getCurve/getPoint(ptr form)/get(AcDb3dSolid*&)/getPointContainment
  container all hand back caller-owned heap objects; getSurfaceAsTrimmedNurbs and getLineContainment hand
  back caller-`delete[]`'d arrays. Wrap in the router's per-op cleanup.

---

### C++-only delta (what this slice gives the controller that managed/LISP/CoreConsole cannot)

- **True topology walk** with stable subentity identity. AutoLISP / COM expose a solid as an opaque entity;
  they cannot enumerate faces→loops→edges→vertices, nor give per-face surface type, per-edge curve, loop
  classification, or vertex coordinates. AcBr is the only API surface that does.
- **Per-face / per-edge AcGe geometry extraction** (getSurface → AcGeExternalBoundedSurface, getCurve →
  AcGeCurve3d, getSurfaceAsTrimmedNurbs) — the foundation for exporting a solid's exact analytic B-rep
  (planes/cylinders/cones/tori/nurbs) rather than a tessellated mesh. This is the native ceiling that the
  python `solid_brep_occ` router engine approximates only via STEP round-trip.
- **Point/line containment with sub-object identification** (getPointContainment returns the *containing
  edge/face*; getLineContainment returns the in/out hit segmentation) — geometric reasoning not available
  anywhere in the managed quantity-takeoff surface.
- **BRep-level mass properties as a full inertia tensor** (AcBrMassProps: centroid + radii of gyration +
  moments + products of inertia + principal moments + principal axes) — richer than AcDb3dSolid::getMassProp
  for downstream structural reasoning, and computable per-shell.
- **Direct subentity modeling + addressing** (transformSubentPathsBy to push/move individual faces;
  subentPtr to lift a face/edge to a standalone entity; getSubentPathsAtGsMarker to convert a pick to a
  durable path). The only managed analog is the .NET BoundaryRepresentation/SubentityId wrapper, which is a
  thin shim over exactly these ARX methods (confirmed: SubentityOverrule .NET methods each "wrap the
  ObjectARX method AcDbSubentityOverrule::…").
- `.NET managed_also` reality check: Autodesk ships `Autodesk.AutoCAD.BoundaryRepresentation` (Brep, Face,
  Edge, Vertex, Complex, Shell, BoundaryLoop + matching traversers) — so most `inspect/traverse` ops have a
  managed twin for the existing CadJobRunner plane. But the C++ AcBr is the authoritative/complete surface
  (trimmed-nurbs arrays, AcBrHit line containment, full validation-level control) and is the recommended
  implementation tier for fidelity-critical extraction.

---

### Sources actually read (this session)

Local ObjectARX 2027 headers (exact C++ signatures, read via sandbox):
- `C:\ObjectARX 2027\utils\brep\inc\` — brent.h, brbrep.h, brcplx.h, brshell.h, brface.h, brloop.h,
  bredge.h, brvtx.h, brprops.h (AcBrMassProps struct), and traversers brtrav.h, brbctrav.h, brbstrav.h,
  brbftrav.h, brbetrav.h, brbvtrav.h, brcstrav.h, brsftrav.h, brfltrav.h, brletrav.h, brlvtrav.h,
  brvltrav.h, brvetrav.h, breltrav.h, brentrav.h.
- `C:\ObjectARX 2027\inc\acdb.h` (SubentType enum, lines 459-475), `dbmain.h` (AcDbEntity subentity
  virtuals, lines 2001-2054).
- `C:\ObjectARX 2027\lib-x64\` — directory enumeration confirming **AcDrawBridge.lib** (+ acdb26/accore/
  acge26/rxapi/acismobj26/acgeoment present), 33 libs total.
- `C:\ObjectARX 2027\utils\brep\samples\brepsamp\` — file inventory + read of brselect.cpp & bredump.cpp
  for the entity→brep and traversal idioms; brsample.vcxproj confirmed as build template.

Autodesk Help MCP (OARX 2027 Reference/Developer guides — authoritative, GUIDs/URLs):
- AcBrEntity — `OARXMAC-RefGuide-AcBrEntity.html`
- AcBr Structure (all enums + every ErrorStatus semantics) — `OARX-RefGuide-AcBr.html` (File brgbl.h)
- AcBrBrep + AcBrBrep Methods + AcBrBrep::get — `OARX-RefGuide-AcBrBrep*.html` (File brbrep.h)
- AcBrEntity Methods (getMassProps/getPointContainment/getBoundBlock/checkEntity/… semantics) —
  `OARXMAC-RefGuide-__MEMBERTYPE_Methods_AcBrEntity.html`
- Entity Classes (Dev Guide) — `GUID-D30618E4-8C61-4D98-B2CB-D2110D21454F.htm`
- Traverser Classes (Dev Guide — set semantics, full traverser list) —
  `GUID-8D806C0D-0DB9-477B-882F-AB76A74F702B.htm`
- AcBrFace::getSurface — `OARXMAC-RefGuide-AcBrFace__getSurface_AcGeSurface___const.html`
- AcBrFace::getOrientToSurface — `OARX-RefGuide-AcBrFace__getOrientToSurface_Adesk__Boolean__const.html`
- AcBrEdge::getCurve — `OARX-RefGuide-AcBrEdge__getCurve_AcGeCurve3d___const.html`
- AcBrLoop::getType — `OARX-RefGuide-AcBrLoop__getType_AcBr__LoopType__const.html`
- AcDbEntity::getGsMarkersAtSubentPath — `OARX-RefGuide-AcDbEntity__getGsMarkersAtSubentPath_*.html`
- AcDbEntity::getSubentClassId — `OARX-RefGuide-AcDbEntity__getSubentClassId_*.html`
- AcDbEntity::highlight / unhighlight — `OARX-RefGuide-AcDbEntity__highlight_*.html` / `__unhighlight_*.html`
- AcDbSubentityOverrule Methods + managed SubentityOverrule Methods (managed-wraps-ARX confirmation) —
  `OARX-RefGuide-__MEMBERTYPE_Methods_AcDbSubentityOverrule.html` /
  `OARX-ManagedRefGuide-__MEMBERTYPE_Methods_Autodesk_AutoCAD_DatabaseServices_SubentityOverrule.html`
