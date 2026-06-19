# AutoCAD SDK Router -- MANDATORY USAGE CONTRACT

**Router home**: `D:\dev\99_tools\autocad-sdk-router`
**Single entrypoint (PowerShell)**: `tools\autocad-router.ps1`
**Python route runner**: `tools\run_route.py` (invoked by the PS entrypoint; can be called directly for the python routes)
**Capabilities (SoT)**: `config\autocad_router_capabilities.json`
**Live machine status**: `reports\autocad_router_status_latest.json`
**Agent contract (companion)**: `reports\AUTO_CAD_ROUTER_AGENT_CONTRACT.md`
**Last rebuild**: 2026-06-16 (local rebuild of the Drive-mirror original; the old 6 AutoCAD-internal sub-routes are folded into `dwg_truth_autocad`; expanded to the frozen geometry-toolchain spec).

---

## 0. THE RULE (non-negotiable, every agent)

> **Every CAD / DWG / DXF / IFC / STEP-BREP / IGES / mesh (STL/OBJ/PLY) / point cloud (LAS/LAZ/RCS) / geo-vector (SHP/GeoJSON/DGN) / PDF-vector / SVG-vector / raster-compare / parametric-generate operation MUST go through this router.**
>
> **Do NOT hand-call `ezdxf`, `ifcopenshell`, `cadquery`, `trimesh`, `open3d`, `fitz`/PyMuPDF, `cv2`, `pyogrio`, `accoreconsole`, COM, ObjectARX, etc. directly from a one-off script.** Those libraries are the router's *engines*; calling them ad-hoc bypasses availability probing, native ARX/DBX-first routing, explicit write-mode accounting, fallback chains, and the honest "tool-not-installed" contract, and silently reintroduces every failure mode this router exists to prevent.

**Allowed exception**: writing a NEW route or fixing the router itself (work *inside* `D:\dev\99_tools\autocad-sdk-router`). Even then, route execution still flows through `run_route.py` so the discipline below holds.

**Why this rule exists**: the router guarantees (a) DWG work goes through the strongest official Autodesk SDK lane first, native ObjectARX/ObjectDBX when it can own the operation, (b) original/open DWG writes are explicit first-class `write_original`/live-edit operations instead of hidden side effects, (c) AutoCAD inputs can still be ASCII-staged for batch/copy/path-hygiene jobs, (d) a route reports `available:true` only when its REQUIRED tools actually import (no fake passes), (e) unavailable routes refuse to run instead of fabricating output, (f) heavy C-extensions load per-route so the interpreter exits clean.

---

## 1. Hard discipline (memorize)

1. **DWG original writes are allowed.** If the user's intent is direct edit, active-document edit, `write_original`, or equivalent, the router-controlled AutoCAD SDK host may modify the original DWG or the currently open AutoCAD document and must report what changed.
2. **Native ARX/DBX first.** `dwg_truth_autocad` is the full official AutoCAD SDK control plane. Prefer native ObjectARX/ObjectDBX for DB, graphics, geometry, custom objects/entities, object enablers, protocol extensions, overrules, reactors, jigs, and write-original work.
3. **Adapters stay under the DWG truth route.** Managed .NET, AutoLISP/Visual LISP, Core Console, full AutoCAD, and COM/ActiveX are allowed and expected, but they are adapters beneath the native ARX/DBX-first route.
4. **ASCII staging remains available.** Use `staging\dwg_<stamp>\input.dwg` for batch/copy/path-hygiene jobs. Staging is no longer a prohibition on live/open-document editing.
5. **No fake success.** A route is `available:true` only if every REQUIRED tool resolves (live probe `tools\probe_routes.py`). A forced-but-unavailable route returns `status:UNAVAILABLE` and refuses to run. Current status: **11/11 available**.
6. **RealDWG is excluded.** Use ObjectARX/ObjectDBX inside the AutoCAD SDK host; do not add a RealDWG dependency.
7. **LibreDWG is GPL -> sidecar only.** `dwg_libredwg_sidecar` runs as a separate process for AutoCAD-free DWG cross-check. Never link/import LibreDWG into the production router.
8. **Status JSON has a BOM.** PowerShell writes `autocad_router_status_latest.json` with a UTF-8 BOM. Reading it from Python on this cp949 machine needs `encoding='utf-8-sig'` (bare `open()` raises `UnicodeDecodeError`). The router's own PowerShell reader is fine.

---

## 2. Workflow (always this order)

```powershell
$R = 'D:\dev\99_tools\autocad-sdk-router\tools\autocad-router.ps1'

# 1) Availability snapshot (LIVE probe -> rewrites status JSON)
& $R -Action status

# 2) Resolve intent -> route (honors availability + fallback chain; no execution)
& $R -Action select  -Intent <intent>

# 3) Execute against the real input
& $R -Action run     -Intent <intent> -InputPath <file>

# (optional) full capability metadata for a route
& $R -Action explain -Intent <intent>
```

**Actions**: `status` (probe + write status JSON) / `select` (intent->route, no run) / `run` (select + execute, refuses if unavailable) / `explain` (select + metadata dump).

**Key params**: `-Intent <alias>` · `-InputPath <file>` · `-InputPath2 <file>` (2nd image for raster compare) · `-Out <file>` (parametric output) · `-Route <id>` (force a specific route, bypassing intent mapping) · `-Script <file.scr>` (custom accoreconsole script for `dwg_truth_autocad`) · `-PythonExe <path>` (override interpreter).

> Intent aliases are defined in `config\autocad_router_capabilities.json` (`intent_aliases`). You may pass any alias (e.g. `dwg`, `dxf`, `ifc`, `step`, `mesh`, `las`, `geo`, `svg`, `raster`, `parametric`) or the full route id.

---

## 3. The 12-route spec -> 11 distinct routes (honest count)

> The frozen spec header says "12-ROUTE" but tabulates **11 distinct route IDs** and names 11 engines. This router implements exactly those 11. The "12th" is `dwg_truth_autocad`'s AutoCAD-internal sub-routes (CoreConsole / AutoLISP / ObjectDBX / ObjectARX / COM / full-AutoCAD — the old Drive router's 6-way split) folded under one engine. A genuine 12th top-level route would be a **Paul clarification**, not a fabrication.

| # | route | engine (tools) | available | use it when… |
|---|---|---|---|---|
| 1 | **dwg_truth_autocad** | accoreconsole — AutoCAD 2027 + AutoLISP/.scr (+ ObjectDBX/ARX/COM host SDKs) | YES | DWG **ground truth**: dynamic blocks, xdata, layouts, named objects, ObjectDBX reads, CoreConsole batch extraction. The authoritative route. |
| 2 | **dxf_fast_secondary** | ezdxf + shapely | YES | Read DXF **without** AutoCAD; entity inventory, layers, polyline/line analysis, 2D geometry compare/align. |
| 3 | **ifc_bim_semantic** | ifcopenshell | YES | IFC BIM semantics: wall/slab/space/storey/door/window, schema, property sets, GUID/placement. |
| 4 | **solid_brep_occ** | cadquery + OCP (OCCT 7.8) | YES | STEP/IGES/BRep solids: solid/face/edge topology, volume, bbox, shape validation, boolean. |
| 5 | **parametric_rebuild** | cadquery (+ cadquery-ocp) | YES | **Generate a NEW** CAD model from rules/IR in Python; export STEP/STL/SVG. Only generative route. |
| 6 | **dwg_libredwg_sidecar** | LibreDWG CLI (dwgread/dwg2dxf) | YES | AutoCAD-free DWG cross-check (read DWG / DWG->DXF). GPL sidecar-only. |
| 7 | **mesh_analysis** | trimesh + meshio + open3d | YES | STL/OBJ/PLY mesh: watertightness, volume, surface area, bounds, euler, registration. |
| 8 | **pointcloud_route** | open3d + laspy | YES | RCS/RCP/LAS/LAZ point cloud: read, count, bbox, thinning, ICP, distance; LAS/LAZ headers. |
| 9 | **geo_vector_route** | pyogrio (bundled GDAL 3.11.4) + pyproj | YES | SHP/GeoJSON/DXF/DGN/GPKG vector IO + conversion; CRS/coordinate reprojection. |
| 10 | **pdf_svg_vector_route** | svgpathtools + svgelements (+ PyMuPDF/fitz for PDF) | YES | Extract vector paths from **PDF/SVG** references; path length/segment counts; CAD/PDF overlay compare. |
| 11 | **raster_compare_route** | opencv-python-headless + scikit-image | YES | Compare PDF/DWG **render images**: intensity stats, SSIM, alignment, feature matching, visual QA. |

Status as of 2026-06-16 smoke: `route_count=11`, `available=11`, `status=ALL_AVAILABLE`.

Current DWG contract supersedes the older row wording above: `dwg_truth_autocad` is now
the full official AutoCAD SDK control plane, with native ObjectARX/ObjectDBX first and
write_original/live active-document edits allowed when requested.

---

## 4. Per-route call examples + input / output / limits

> `$R` = `'D:\dev\99_tools\autocad-sdk-router\tools\autocad-router.ps1'` throughout.
> Python routes can also be run directly: `python tools\run_route.py --route <id> --input <file> [--out <file>] [--input2 <img>]`. The PS entrypoint is preferred (it does availability + staging first).

### A. dwg_truth_autocad  (FLAGSHIP — DWG ground truth)
```powershell
& $R -Action run -Intent dwg -InputPath 'C:\path\to\drawing.dwg'
# custom AutoLISP/.scr job instead of the default extractor:
& $R -Action run -Intent dwg -InputPath 'C:\path\to\drawing.dwg' -Script 'C:\path\to\job.scr'
# original/live-document edit intent:
& $R -Action run -Intent write_original -InputPath 'C:\path\to\drawing.dwg'
```
- **Input**: any `.dwg` (incl. non-ASCII / Drive paths — staged automatically).
- **Output**: `runs\dwg_truth_autocad_<stamp>\extract.json` (modelspace_count, entities_by_type, layers) + `accoreconsole_stdout/stderr.txt`.
- **Verified**: on `input.dwg` -> modelspace_count=375; INSERT=50 LWPOLYLINE=73 TEXT=117 DIMENSION=113 LINE=21 CIRCLE=1. Original byte-identical pre/post.
- **Current contract**: this route is now the DWG ground-truth and full official AutoCAD SDK control plane. Prefer native ObjectARX/ObjectDBX first; use Managed .NET, AutoLISP/Visual LISP, Core Console, full AutoCAD, and COM/ActiveX as adapters when appropriate. RealDWG is excluded.
- **Write modes**: `write_original`/live-edit may modify the original DWG or active document. Batch/copy jobs may still use ASCII staging and derivative outputs.
- **Implementation state**: current implemented commands are still extractor-oriented; the contract now requires the next implementation layer to add SDK job operations across the full official Autodesk SDK families.
- **Limits**: requires AutoCAD 2027 Core Console for headless batch mode. `accoreconsole` console output is UTF-16 -> mojibake in captured stdout is cosmetic capture-encoding noise, not a failure. The existing extractor path is still batch/export-oriented; write_original/live-edit operations belong to the new SDK job layer.

### B. dxf_fast_secondary  (DXF without AutoCAD)
```powershell
& $R -Action run -Intent dxf -InputPath 'C:\path\to\model.dxf'
```
- **Input**: `.dxf` (ASCII or binary).  **Output**: `runs\…` JSON — entity_count, by_type, layers (Korean layer names OK), `line_total_length`.
- **Verified**: `input_84A.dxf` (15.7MB, AC1032) -> entity_count=375, identical per-type profile to the DWG truth route (cross-engine 375=375 => the DXF is an export of that DWG), 14 layers incl `설비OPEN`.
- **Limits**: 2D-centric; not a substitute for AutoCAD on dynamic blocks/xdata — use route A for those.

### C. ifc_bim_semantic
```powershell
& $R -Action run -Intent ifc -InputPath 'C:\path\to\model.ifc'
```
- **Input**: `.ifc` (IFC2x3/IFC4).  **Output**: JSON — schema, total entities, per-type counts (IfcWall/IfcDoor/IfcBuildingStorey…).
- **Verified**: on a generated minimal IFC4 (no real `.ifc` in `alm\build`) -> schema=IFC4, IfcWall=2 IfcDoor=1 IfcBuildingStorey=1. **Re-run on a real `.ifc` for true-data confirmation.**

### D. solid_brep_occ
```powershell
& $R -Action run -Intent step -InputPath 'C:\path\to\part.step'
```
- **Input**: `.step/.stp/.iges/.igs/.brep`.  **Output**: JSON — solid_count, face_count, edge_count, total_volume, bbox.
- **Verified**: read the STEP from route E -> 1 solid / 10 faces / 24 edges / volume=995.707963 / bbox 20x10x5 (round-trip exact).
- **Limits**: uses `cadquery-ocp` (OCCT 7.8). `pythonocc-core` is an optional alt binding (not installed, not required).

### E. parametric_rebuild  (the only GENERATIVE route)
```powershell
& $R -Action run -Intent parametric -Out 'C:\path\to\out.step' -p-len 30 -p-wid 12 -p-hgt 6
```
- **Input**: none (rule/param driven).  **Output**: writes a NEW artifact at `-Out` (`.step/.stl/.svg`) **only** — never near any source.
- **Verified**: generated `gen_box.step` 20x10x5 filleted -> generated_volume=995.707963, 31753 bytes.
- **Limits**: writes only to the explicit `-Out` path.

### F. dwg_libredwg_sidecar  (GPL sidecar cross-check)
```powershell
& $R -Action run -Intent libredwg -InputPath 'C:\path\to\drawing.dwg'
```
- **State**: LibreDWG 0.13.4 win64 sidecar is installed under `D:\dev\99_tools\libredwg\bin`.
- **Output**: `runs\dwg_libredwg_sidecar_<stamp>\libredwg_extract.json` and `libredwg_export.dxf`.
- **Verified**: `input.dwg` produced JSON and DXF with `dwgread -O JSON|DXF -o ...`; original input was read-only.
- **License boundary**: GPL sidecar process only; never import/link/bundle LibreDWG into production code.

### G. mesh_analysis
```powershell
& $R -Action run -Intent mesh -InputPath 'C:\path\to\mesh.stl'
```
- **Input**: `.stl/.obj/.ply`.  **Output**: JSON — vertices, faces, is_watertight, volume, area, euler_number.
- **Verified**: synthetic 2x3x4 box.stl -> watertight=true, volume=24.0, area=52.0, euler=2, 8 verts / 12 faces.

### H. pointcloud_route
```powershell
& $R -Action run -Intent las -InputPath 'C:\path\to\cloud.las'
```
- **Input**: `.las/.laz/.pcd/.ply` (RCS/RCP via export).  **Output**: JSON — reader, point_count, bbox_min/max.
- **Verified**: synthetic 100-pt cloud.ply -> open3d reader, point_count=100, bbox in unit cube. LAS/LAZ path via laspy (import-verified).
- **Limits**: `pdal` not installed (optional) — full pipeline/streaming/COPC ops need it; basic read/thin/ICP work via open3d+laspy.

### I. geo_vector_route
```powershell
& $R -Action run -Intent geo -InputPath 'C:\path\to\layer.geojson'
```
- **Input**: `.shp/.geojson/.dxf/.dgn/.gpkg`.  **Output**: JSON — reader, feature_count, fields, crs, geometry_type.
- **Verified**: synthetic 2-feature EPSG:4326 GeoJSON -> pyogrio reader, 2 features, EPSG:4326, Point, fields=[id].
- **Limits**: native `osgeo.gdal` NOT installed; route runs on **pyogrio (bundles GDAL 3.11.4) + pyproj**. Vector IO + CRS fully work; native GDAL only needed for raster ops and `gdal_translate`/`ogr2ogr` CLIs (manual: OSGeo4W or conda-forge gdal).

### J. pdf_svg_vector_route  (B-side flagship — PDF + SVG vector)
```powershell
& $R -Action run -Intent svg -InputPath 'C:\path\to\ref.svg'   # SVG branch
& $R -Action run -Intent pdf -InputPath 'C:\path\to\ref.pdf'   # PDF branch (PyMuPDF)
```
- **Input**: `.svg` (svgpathtools/svgelements) or `.pdf` (PyMuPDF/fitz).  **Output**: JSON — reader, page_count, per-page vector drawing/path counts, page size.
- **Verified (PDF)**: `84A_hq.pdf` -> pymupdf, 1 page, 54882 vector drawings, page 1684x2384 pt.  **SVG branch**: import-verified only (no `.svg` sample) — re-run on a real `.svg` for true-data confirmation.
- **Limits**: PyMuPDF (`fitz` 1.27.2.3) is installed **shared** in the main Python312 env, not isolated as the spec noted. Works as-is; isolation is a pending Paul decision. SVG path extraction needs no isolation.

### K. raster_compare_route
```powershell
& $R -Action run -Intent raster -InputPath 'a.png' -InputPath2 'b.png'
```
- **Input**: two raster images (PNG/JPG/…).  **Output**: JSON — shape, mean_intensity, ssim (+ alignment/feature-match).
- **Verified**: `84A_walls.png` self-compare -> shape 874x1244, mean_intensity 244.82, SSIM=1.0 (correct for identical images).

---

## 5. Cross-route patterns (the real workflows)

- **DWG truth vs DXF agreement**: route A on the `.dwg` and route B on the exported `.dxf`; equal entity counts (375=375) confirm the DXF is a faithful export. Use this to validate an export pipeline.
- **Generate -> inspect round-trip**: route E (`parametric_rebuild`) writes a STEP, route D (`solid_brep_occ`) reads it back; equal volume proves the generator and the kernel agree.
- **PDF reference overlay**: route J extracts PDF vector paths; route K compares a DWG render against the PDF render (SSIM) for visual QA.

---

## 6. Honest gaps / manual-install routes (do NOT fake)

| item | state | manual path |
|---|---|---|
| **dwg_libredwg_sidecar** | installed and available | `D:\dev\99_tools\libredwg\bin\dwgread.exe` / `dwg2dxf.exe`; official win64 release SHA256 verified; GPL sidecar only, never bundle/import/link. |
| **native osgeo.gdal** | not installed (geo_vector_route uses pyogrio instead) | OSGeo4W installer (gdal + python3-gdal) OR `conda install -c conda-forge gdal`. Only needed for raster GDAL + ogr2ogr/gdal_translate CLIs. |
| **pythonocc-core** | not installed (OPTIONAL — cadquery-ocp already covers solid_brep_occ) | miniforge3 then `conda create -n occ -c conda-forge python=3.12 pythonocc-core`. |
| **pdal** | not installed (OPTIONAL — laspy+open3d cover basic pointcloud) | miniforge3 then `conda create -n pdal -c conda-forge python=3.12 pdal python-pdal`. |
| **PyMuPDF isolation** | installed SHARED (works), not isolated | optional dedicated venv if true isolation required — pending Paul decision. |
| **freecadcmd** | installed 1.1.1 (OPTIONAL alt solid kernel) | `C:\Users\PAUL\AppData\Local\Programs\FreeCAD 1.1\bin\freecadcmd.exe` (not on PATH; lowercase exe). |

Installed engines satisfying the available routes: ifcopenshell 0.8.5, ezdxf 1.4.3, shapely 2.1.2, cadquery 2.7.0, cadquery-ocp 7.8.1.1, trimesh 4.12.2, meshio 5.3.5, open3d 0.19.0, laspy 2.7.0, pyogrio 0.12.1, pyproj 3.7.2, svgpathtools 1.7.2, svgelements 1.9.6, pymupdf 1.27.2.3, opencv-python-headless 4.13.0.92, scikit-image 0.26.0; AutoCAD 2027 Core Console at `C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe`.

---

## 7. Env-var binding and enforcement (ARIADNE_AUTOCAD_ROUTER_*)

The Ariadne tracked entrypoints export `ARIADNE_AUTOCAD_ROUTER_*` pointing at this local router from `D:\dev\_ariadne\bin\ariadne_entrypoint_common.ps1`.

- `ARIADNE_AUTOCAD_ROUTER_ROOT=D:\dev\99_tools\autocad-sdk-router`
- `ARIADNE_AUTOCAD_ROUTER_PATH=D:\dev\99_tools\autocad-sdk-router\tools\autocad-router.ps1`
- `ARIADNE_LIBREDWG_BIN_DIR=D:\dev\99_tools\libredwg\bin`
- `ARIADNE_CAD_ROUTER_ENFORCEMENT=required`
- `ARIADNE_CAD_ROUTER_PROMPT_PATH=D:\dev\_ariadne\context\live\CAD_ROUTER_ENFORCEMENT.md`

Tracked wrappers inject this policy into boot context and, where the CLI supports it, prompt/system-prompt arguments. Known context/policy bypass flags are blocked in the wrappers.
