# AutoCAD SDK Router -- Agent Contract (local rebuild)

**Router home**: `D:\dev\99_tools\autocad-sdk-router`
**Single entrypoint**: `tools\autocad-router.ps1`
**Rebuilt**: 2026-06-17 (native ARX/DBX-first control-plane contract; original DWG writes allowed)
**Schema**: `ariadne.autocad_router_*.v2`

---

## 0. Required rule

Any agent that needs DWG / DXF / IFC / STEP-BREP / mesh / point cloud / geo-vector /
PDF-SVG-vector / raster-compare / parametric-rebuild work for a CAD task MUST call this
router first. State your **intent**; the router selects the strongest currently
**available** route and falls back by capability. Do not hand-pick an engine unless the
task explicitly overrides via `-Route`.

```powershell
& 'D:\dev\99_tools\autocad-sdk-router\tools\autocad-router.ps1' -Action status
```

---

## 1. Hard discipline (non-negotiable)

1. **DWG original write is allowed.** For DWG work, agents may modify the original
   drawing or the currently open AutoCAD document when the user intent is
   `write_original`, `live_autocad`, `active_document`, or an equivalent edit command.
   The operation must still report what changed.
2. **Native ARX/DBX first.** `dwg_truth_autocad` is the top-level AutoCAD SDK control
   plane. Prefer native ObjectARX/ObjectDBX for DB, geometry, graphics, custom class,
   reactor, overrule, protocol-extension, and write-original work. Managed .NET,
   AutoLISP, Core Console, COM/ActiveX, and full AutoCAD host lanes are adapters under
   this route, not replacements for the native ceiling.
3. **ASCII staging remains a mode, not a wall.** Staging under
   `staging\dwg_<stamp>\input.dwg` is still available for batch, copy, and path-hygiene
   jobs. It is not mandatory for live/open-document editing.
4. **Official SDK family coverage.** The agent-facing capability surface must cover the
   official AutoCAD/ObjectARX SDK families: runtime commands and AutoLISP-callable
   functions; ObjectDBX database operations; transactions; symbol tables; dictionaries;
   XData/XRecords; entities; blocks and xrefs; layouts, plotting, and publishing; AcGe
   geometry; AcBr/BRep; AcGi/AcGs graphics; editor/input/jigs/grips; reactors and
   events; custom entities/objects/object enablers; protocol extensions/queryX;
   overrules; associativity and constraints; CUI/UI surfaces; COM/ActiveX bridges;
   AutoLISP/Visual LISP; and Core Console batch execution. RealDWG is excluded.
5. **No fake success.** A route is reported `available: true` only if every REQUIRED tool
   actually imports / resolves (live probe, `tools\probe_routes.py`). An unavailable
   route, if forced, returns `status: UNAVAILABLE` and refuses to run -- it never
   fabricates a pass. Current status is `ALL_AVAILABLE` with 11/11 routes available.
6. **LibreDWG is GPL -> sidecar only.** `dwg_libredwg_sidecar` must run as a separate
   process for AutoCAD-free DWG cross-check. Never link / import LibreDWG into the
   production router.

---

## 2. Actions

| Action | What it does |
|---|---|
| `-Action status` | LIVE-probe every route's tool availability; write `reports\autocad_router_status_latest.json`. |
| `-Action select -Intent <intent>` | Map intent -> route; honor availability + fallback chain; emit the selection (no execution). |
| `-Action run -Intent <intent> [-InputPath <file>] [-Out <file>]` | Select, then actually execute the route against the input. Refuses if the selected route is unavailable. |
| `-Action explain -Intent <intent>` | Selection + full capability metadata dump. |

Optional params: `-Route <id>` (force a specific route), `-InputPath2 <file>` (second image
for `raster_compare_route`), `-Out <file>` (output for `parametric_rebuild`),
`-Script <file.scr>` (custom accoreconsole script for `dwg_truth_autocad`),
`-WriteMode read|write_copy|write_original|live_edit`,
`-HostMode auto|coreconsole|full_autocad`, `-Operation <sdk-op>`,
`-PythonExe <path>` (override interpreter).

---

## 3. The 12-route spec (11 distinct routes implemented)

> NOTE: the frozen spec header says "12-ROUTE" but tabulates **11 distinct route IDs**
> (and names 11 engines in its own dispatch list). This router implements exactly those
> 11. The "12" appears to count `dwg_truth_autocad` as both "AutoCAD truth" and its
> AutoCAD-internal sub-routes (ObjectDBX / ObjectARX / COM / CoreConsole), which the old
> Drive router split into 6. Here they are folded under the single `dwg_truth_autocad`
> engine. If a genuine 12th top-level route is intended, that is a spec clarification for
> Paul, not an invention this router will fake.

| # | route | engine | available | intent keywords |
|---|---|---|---|---|
| 1 | `dwg_truth_autocad` | native ObjectARX/ObjectDBX first; accoreconsole/full AutoCAD/.NET/LISP/COM adapters | yes | dwg, autocad, official_sdk, arx, dbx, write_original, live_autocad, dynamic_block, xdata, layout, objectdbx |
| 2 | `dxf_fast_secondary` | ezdxf + shapely | yes | dxf, polyline, 2d_geometry |
| 3 | `ifc_bim_semantic` | ifcopenshell | yes | ifc, bim, wall, storey, property_set |
| 4 | `solid_brep_occ` | cadquery + OCP (OCCT 7.8) | yes | step, brep, solid, iges, topology, boolean |
| 5 | `parametric_rebuild` | cadquery | yes | rebuild, generate, parametric, export_step |
| 6 | `dwg_libredwg_sidecar` | LibreDWG CLI | yes | libredwg, dwg_no_autocad, dwg_crosscheck |
| 7 | `mesh_analysis` | trimesh + meshio + open3d | yes | mesh, stl, watertight, obj, ply |
| 8 | `pointcloud_route` | open3d + laspy | yes | pointcloud, las, laz, rcs, icp |
| 9 | `geo_vector_route` | pyogrio (bundled GDAL) + pyproj | yes | geo, shp, geojson, crs, dgn |
| 10 | `pdf_svg_vector_route` | svgpathtools + svgelements | yes | pdf, svg, vector_path, overlay |
| 11 | `raster_compare_route` | opencv-headless + skimage | yes | raster, image_compare, ssim, visual_qa |

Full route metadata: `config\autocad_router_capabilities.json`.
Live machine status: `reports\autocad_router_status_latest.json`.

## 3.1 AutoCAD SDK control-plane priority

For DWG work, route selection is:

1. Native ObjectARX/ObjectDBX for maximum SDK coverage and direct database/graphics/
   geometry/runtime access.
2. Managed .NET when Autodesk exposes the needed API there or when the wrapper layer is
   the fastest correct implementation.
3. AutoLISP/Visual LISP and Core Console for command automation and batch execution.
4. Full AutoCAD/COM for currently open drawings, UI/session-bound operations, and
   active-document write_original edits.

The router may still use non-DWG routes for IFC, STEP/BRep, meshes, point clouds, geo,
PDF/SVG, and raster work, but those do not reduce the DWG authority of the native
AutoCAD SDK route.

---

## 4. Examples

```powershell
$R = 'D:\dev\99_tools\autocad-sdk-router\tools\autocad-router.ps1'

# Availability snapshot (live probe)
& $R -Action status

# Pick a route for an intent (with fallback if unavailable)
& $R -Action select -Intent ifc

# DWG SDK control-plane route (native ARX/DBX first; write_original allowed when requested)
& $R -Action run -Intent dwg  -InputPath 'C:\path\to\drawing.dwg'

# Explicit original/live-document edit intent for SDK job operations
& $R -Action run -Intent write_original -InputPath 'C:\path\to\drawing.dwg'

# Run a script against the original DWG path; script must SAVE/QSAVE if persistence is needed
& $R -Action run -Intent write_original -InputPath 'C:\path\to\drawing.dwg' -WriteMode write_original -Script 'C:\path\to\job.scr'

# Send a script to the currently open AutoCAD ActiveDocument
& $R -Action run -Intent active_document -InputPath 'C:\path\to\drawing.dwg' -WriteMode live_edit -HostMode full_autocad -Script 'C:\path\to\job.scr'

# DXF fast read without AutoCAD
& $R -Action run -Intent dxf  -InputPath 'C:\path\to\model.dxf'

# IFC BIM semantics
& $R -Action run -Intent ifc  -InputPath 'C:\path\to\model.ifc'

# STEP/BREP solid topology
& $R -Action run -Intent step -InputPath 'C:\path\to\part.step'

# Generate a NEW parametric solid -> STEP
& $R -Action run -Intent parametric -Out 'C:\path\to\out.step' -p-len 30 -p-wid 12 -p-hgt 6

# LibreDWG GPL sidecar DWG cross-check
& $R -Action run -Intent libredwg -InputPath 'C:\path\to\drawing.dwg'

# Mesh watertightness / volume
& $R -Action run -Intent mesh -InputPath 'C:\path\to\mesh.stl'

# Point cloud header / count
& $R -Action run -Intent las  -InputPath 'C:\path\to\cloud.las'

# Vector GIS + CRS
& $R -Action run -Intent geo  -InputPath 'C:\path\to\layer.geojson'

# PDF/SVG vector path extraction
& $R -Action run -Intent svg  -InputPath 'C:\path\to\ref.svg'

# Raster compare two renders (SSIM)
& $R -Action run -Intent raster -InputPath 'a.png' -InputPath2 'b.png'
```

---

## 5. Engine / install notes (honest gaps)

- **`dwg_libredwg_sidecar` AVAILABLE**: LibreDWG 0.13.4 win64 sidecar is installed under
  `D:\dev\99_tools\libredwg\bin`. It is invoked as a separate CLI process with
  `dwgread -O JSON|DXF -o <out> <input.dwg>`. GPL: keep it a separate process; never
  import, link, or bundle.
- **`geo_vector_route`**: native `osgeo.gdal` binding is NOT installed (no Windows wheel).
  The route is satisfied via **pyogrio 0.12.1** (self-contained, bundles GDAL 3.11.4) for
  vector IO + **pyproj** for CRS. Native GDAL is only needed for raster ops and the
  `gdal_translate` / `ogr2ogr` CLIs.
- **`solid_brep_occ` / `parametric_rebuild`**: use **cadquery-ocp 7.8.1.1** (the OCP / OCCT
  7.8 binding). `pythonocc-core` is an optional alternate binding (NOT installed, NOT
  required). `freecadcmd` 1.1.1 is an optional alternate kernel (installed).
- **`pdf_svg_vector_route`**: PyMuPDF (`fitz` 1.27.2.3) is installed **shared** in the
  main Python312 env, not isolated. The spec noted "PyMuPDF isolated"; this is a pending
  Paul decision. SVG path extraction (svgpathtools/svgelements) needs no isolation.
- **Native-extension shutdown segfault**: importing all heavy CAD/geometry extensions in
  one process can raise a 0xC0000005 at interpreter shutdown (after work completes). The
  probe avoids this by checking each module in an isolated subprocess and writing results
  to a flushed file; per-route runs each load only that route's libs, so they exit clean.

---

## 6. Env-var binding and enforcement (ARIADNE_AUTOCAD_ROUTER_*)

The Ariadne tracked entrypoints export `ARIADNE_AUTOCAD_ROUTER_*` pointing at this local
router from `D:\dev\_ariadne\bin\ariadne_entrypoint_common.ps1`.

- `ARIADNE_AUTOCAD_ROUTER_ROOT=D:\dev\99_tools\autocad-sdk-router`
- `ARIADNE_AUTOCAD_ROUTER_PATH=D:\dev\99_tools\autocad-sdk-router\tools\autocad-router.ps1`
- `ARIADNE_LIBREDWG_BIN_DIR=D:\dev\99_tools\libredwg\bin`
- `ARIADNE_CAD_ROUTER_ENFORCEMENT=required`
- `ARIADNE_CAD_ROUTER_PROMPT_PATH=D:\dev\_ariadne\context\live\CAD_ROUTER_ENFORCEMENT.md`

Wrappers inject this policy into boot context and, where supported, the model prompt /
system prompt. Known context/policy bypass flags are blocked by tracked wrappers.
