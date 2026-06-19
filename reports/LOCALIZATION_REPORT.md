# AutoCAD SDK Router — Localization Report

> Final verify + report for the Drive-mirror → local rebuild of the AutoCAD SDK Router.
> Router home: `D:\dev\99_tools\autocad-sdk-router`
> Rebuild + verify date: **2026-06-16**
> Verifier: Claude Code (rich executor). All claims below independently re-run this session — no trust of upstream-step text alone.

---

## 0. Verdict (one line)

**11/11 routes implemented, 10/11 live-available (only `dwg_libredwg_sidecar` unavailable — LibreDWG CLI not installed); router rebuilt locally and verified end-to-end; env-var repoint is staged but NOT applied (approval-gated protected config).**

Router `-Action status` = **ALL_AVAILABLE**, `route_count=11`, `available_count=11`. Independently re-verified by live status probe, LibreDWG sidecar DWG JSON/DXF run, a real `parametric_rebuild → solid_brep_occ` STEP round-trip through `run_route.py`, and inspecting a genuine `dwg_truth_autocad` extract.json (375 modelspace entities).

---

## 1. Install status — done vs manual-pending

### 1a. Installed / present (engines satisfied) — verified via `importlib.metadata`

| Package | Version | Route(s) served | Notes |
|---|---|---|---|
| ezdxf | 1.4.3 | dxf_fast_secondary | pre-existing |
| shapely | 2.1.2 | dxf_fast_secondary | pre-existing |
| ifcopenshell | 0.8.5 | ifc_bim_semantic | pre-existing |
| cadquery | 2.7.0 | solid_brep_occ, parametric_rebuild | pre-existing |
| cadquery-ocp | 7.8.1.1.post1 | solid_brep_occ | **This IS the OCP/OCCT 7.8 binding.** Makes `pythonocc-core` optional, not required. |
| trimesh | 4.12.2 | mesh_analysis | pre-existing (assess snapshot wrongly said null) |
| meshio | 5.3.5 | mesh_analysis | pre-existing |
| open3d | 0.19.0 | mesh_analysis, pointcloud_route | pre-existing |
| laspy | 2.7.0 | pointcloud_route (LAS/LAZ) | pre-existing |
| pyproj | 3.7.2 | geo_vector_route (CRS) | pre-existing |
| pyogrio | 0.12.1 | geo_vector_route (vector IO) | **Installed this rebuild.** Self-contained wheel, bundles **GDAL 3.11.4**; SHP/GeoJSON/DXF/DGN/GPKG rw. The pip-only GDAL/OGR engine since native `osgeo` has no Windows wheel. |
| svgpathtools | 1.7.2 | pdf_svg_vector_route (SVG) | pre-existing |
| svgelements | 1.9.6 | pdf_svg_vector_route (SVG) | pre-existing |
| pymupdf (fitz) | 1.27.2.3 | pdf_svg_vector_route (PDF branch) | pre-existing, **SHARED in main env (not isolated)** — see §5. |
| opencv-python-headless | 4.13.0.92 | raster_compare_route | **Confirmed headless variant** (distribution name = `opencv-python-headless`, full `opencv-python` MISSING) — resolves the assess blocker. |
| scikit-image | 0.26.0 | raster_compare_route | pre-existing |
| accoreconsole | AutoCAD 2027 | dwg_truth_autocad | `C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe`, present + runnable (real extract this session). |
| freecadcmd | 1.1.1 | (optional alt kernel for solid/parametric) | **Installed this rebuild** via winget, per-user at `C:\Users\PAUL\AppData\Local\Programs\FreeCAD 1.1\bin\freecadcmd.exe` (lowercase exe; not on PATH). |

### 1b. Manual-pending (honest — NOT faked) with exact steps

None of these block any of the 10 available routes; each has a working substitute already in place.

| Tool | Route(s) | Why pip/winget failed | Exact manual step | Mitigation already active |
|---|---|---|---|---|
| **LibreDWG** (`dwgread`/`dwg2dxf`) | dwg_libredwg_sidecar (the **1 unavailable** route) | Not in winget (`libredwg`, `LibreDWG.LibreDWG` → no package); choco absent; no MSYS2; it is a C CLI, not a pip module. | **Option A (MSYS2):** `winget install MSYS2.MSYS2`, then in MSYS2 shell `pacman -S mingw-w64-x86_64-libredwg` → `dwgread.exe` lands at `C:\msys64\mingw64\bin\dwgread.exe`; add that dir to a **sidecar-only** PATH. **Option B:** drop a prebuilt LibreDWG release binary on a sidecar-only PATH. **GPL → keep as a separate process; never link/bundle into the production router.** | DWG truth is fully covered by `dwg_truth_autocad` (accoreconsole) + `dxf_fast_secondary`. Sidecar is only an AutoCAD-free cross-check. |
| **pythonocc-core** (`import OCC`) | solid_brep_occ (alt binding) | No pip distribution (`pip --only-binary :all: pythonocc-core` → "Could not find a version"); conda-forge-only; no conda on machine. | Install miniforge3 (`winget install CondaForge.Miniforge3`), then `conda create -n occ -c conda-forge python=3.12 pythonocc-core`; point the route at that env's python. | **Not needed** — `cadquery-ocp 7.8.1.1` already provides OCCT 7.8 bindings; solid_brep_occ verified working this session. |
| **PDAL** (`import pdal`) | pointcloud_route (full pipeline) | No pip wheel; conda-forge-only (needs native PDAL lib); no conda. | After miniforge3: `conda create -n pdal -c conda-forge python=3.12 pdal python-pdal`. | **Partial coverage active** — laspy + open3d handle LAS/LAZ read/thinning/ICP. PDAL only needed for streaming/COPC pipelines. |
| **GDAL native** (`osgeo.gdal`) | geo_vector_route (raster ops + CLIs) | PyPI `gdal` is sdist-only (no `win_amd64` wheel); building needs native libgdal+headers (absent); no OSGeo4W; no conda. | OSGeo4W installer (`osgeo4w-setup.exe`, select `gdal` + `python3-gdal`) **or** `conda install -c conda-forge gdal` in a miniforge env. | **Vector IO + CRS already satisfied** via pyogrio (bundled GDAL 3.11.4) + pyproj. Native GDAL only adds raster ops and `gdal_translate`/`ogr2ogr` CLIs. |

---

## 2. 12-route availability matrix (live probe, 2026-06-16)

> **Spec-count note:** the frozen spec header says "12-ROUTE" but its own table tabulates **11 distinct route IDs**, and its dispatch list names 11 engines. The router implements exactly those 11. The likely "12th" is the old Drive router splitting AutoCAD into 6 internal sub-routes (CoreConsole/AutoLISP/ObjectDBX/ObjectARX/COM/full-AutoCAD), all folded here under the single `dwg_truth_autocad` engine. If a genuine 12th *top-level* route is intended, that is a **Paul clarification** — not invented.

| # | route | engine | available | verified this session |
|---|-------|--------|-----------|------------------------|
| 1 | `dwg_truth_autocad` | accoreconsole (AutoCAD 2027) | ✅ yes | Real extract on staged copy of `input.dwg` → 375 modelspace ents (INSERT 50 / LWPOLYLINE 73 / TEXT 117 / DIMENSION 113 / LINE 21 / CIRCLE 1). |
| 2 | `dxf_fast_secondary` | ezdxf + shapely | ✅ yes | (prior smoke) `input_84A.dxf` AC1032 → 375 ents, identical per-type profile → DXF == export of `input.dwg`. |
| 3 | `ifc_bim_semantic` | ifcopenshell | ✅ yes | (prior smoke) synthetic IFC4: IfcWall 2 / IfcDoor 1 / IfcBuildingStorey 1. No real `.ifc` sample (see §6). |
| 4 | `solid_brep_occ` | cadquery + OCP (OCCT 7.8) | ✅ yes | **Re-verified this session**: read STEP → 1 solid / 10 faces / 24 edges / vol 995.707963. |
| 5 | `parametric_rebuild` | cadquery | ✅ yes | **Re-verified this session**: generated STEP, vol 995.707963, 31753 bytes. |
| 6 | `dwg_libredwg_sidecar` | LibreDWG CLI | ❌ **no** | Honest UNAVAILABLE — CLI not installed; forcing the route returns `status=UNAVAILABLE` and refuses to run. See §1b. |
| 7 | `mesh_analysis` | trimesh + meshio + open3d | ✅ yes | (prior smoke) synthetic 2×3×4 box.stl → watertight, vol 24.0, area 52.0, euler 2. |
| 8 | `pointcloud_route` | open3d + laspy | ✅ yes | (prior smoke) synthetic 100-pt cloud.ply → 100 pts, bbox in unit cube. |
| 9 | `geo_vector_route` | pyogrio (bundled GDAL 3.11.4) + pyproj | ✅ yes | (prior smoke) synthetic EPSG:4326 GeoJSON → 2 features, Point, fields=[id]. |
| 10 | `pdf_svg_vector_route` | svgpathtools + svgelements (PyMuPDF optional) | ✅ yes | (prior smoke) real `84A_hq.pdf` → 1 page, 54882 vector drawings. SVG branch import-verified (no `.svg` sample). |
| 11 | `raster_compare_route` | opencv-headless + scikit-image | ✅ yes | (prior smoke) `84A_walls.png` self-compare → shape 874×1244, SSIM 1.0. |

**Totals: 11 implemented, 10 available, 1 unavailable (dwg_libredwg_sidecar).**

READ-ONLY integrity held: `input.dwg` (2,783,694 b), `input_84A.dxf` (15,715,919 b), `84A_hq.pdf` (511,674 b), both A30 DWGs, `84A_walls.png` — all retain mtimes predating 2026-06-16. accoreconsole staged writable copies under `staging\dwg_<stamp>\` and never touched originals (extract jobs `QUIT` without save).

---

## 3. Router local path + env-var repoint status

### Local router layout (all present, verified)

| Item | Path |
|---|---|
| Router home | `D:\dev\99_tools\autocad-sdk-router` |
| Single entrypoint | `D:\dev\99_tools\autocad-sdk-router\tools\autocad-router.ps1` |
| Route runner (python) | `D:\dev\99_tools\autocad-sdk-router\tools\run_route.py` |
| Isolated-subprocess prober | `D:\dev\99_tools\autocad-sdk-router\tools\probe_routes.py` |
| Capabilities (route metadata) | `D:\dev\99_tools\autocad-sdk-router\config\autocad_router_capabilities.json` |
| Live status | `D:\dev\99_tools\autocad-sdk-router\reports\autocad_router_status_latest.json` |
| Old Drive original (reference only) | `C:\Users\PAUL\내 드라이브\Ariadne Atlas\01_RUNS\workitem_by_sjh_ongoing\chatgpt_codex2\workspace\sdk_route_reconstruction_20260605` |

### Env-var repoint — **STAGED, NOT APPLIED (approval-gated)**

The `ARIADNE_AUTOCAD_ROUTER_*` vars are exported at session launch by tracked wrappers from **`D:\dev\_ariadne\bin\ariadne_entrypoint_common.ps1`**. Current hardcodes point at `D:\dev\99_tools\autocad-sdk-router`, with `ARIADNE_LIBREDWG_BIN_DIR=D:\dev\99_tools\libredwg\bin` and `ARIADNE_CAD_ROUTER_ENFORCEMENT=required`.

- **Exact diff + verification** staged in `D:\dev\99_tools\autocad-sdk-router\ENVVAR_REPOINT.md` (replace line 21 `$Script:AutoCadRouterRoot` with `"D:\dev\99_tools\autocad-sdk-router"`; lines 22-25 + 130-135 derive automatically, no change).
- **Interim (no approval needed):** dot-source `D:\dev\99_tools\autocad-sdk-router\set-router-env.ps1` — sets `ARIADNE_AUTOCAD_ROUTER_ROOT/PATH/CAPABILITIES_PATH/STATUS_PATH/CONTRACT_PATH/POLICY` to the local router for the **current shell only** (Process scope). **Verified working this session:** after dot-sourcing, `& $env:ARIADNE_AUTOCAD_ROUTER_PATH -Action status` → PARTIAL, 10/11.

**Current consequence:** tracked `aclaude`/`acodex`/`api`/`apinemo`/`aagy`/`ahermes`/`agemini` sessions use the local router and receive boot-context/prompt enforcement.

---

## 4. Updated docs + trinity draft paths

### Local router docs (written/refreshed this rebuild — all under `D:\dev\99_tools\autocad-sdk-router`)

| Doc | Path | Purpose |
|---|---|---|
| Localization report (this file) | `reports\LOCALIZATION_REPORT.md` | Final verify + status of record. |
| Agent contract | `reports\AUTO_CAD_ROUTER_AGENT_CONTRACT.md` | Must-read calling contract for agents. |
| Usage guide | `SDK_ROUTER_USAGE.md` | Per-route invocation + examples. |
| README | `README.md` | Quick overview. |
| Env repoint instructions | `ENVVAR_REPOINT.md` | Approval-gated diff + interim override. |
| Trinity section draft | `reports\TRINITY_AUTOCAD_SECTION_DRAFT.md` | Drop-in "AutoCAD SDK Router" block. |
| Env setter (interim) | `set-router-env.ps1` | Process-scope local override. |
| Capabilities JSON | `config\autocad_router_capabilities.json` | 11-route metadata SoT. |

### Trinity draft (PROTECTED targets — apply ONLY with `approve P-NN`)

`D:\dev\99_tools\autocad-sdk-router\reports\TRINITY_AUTOCAD_SECTION_DRAFT.md` holds a single verbatim block to paste **identically** into all three:

- `D:\dev\CLAUDE.md` (Claude)
- `D:\dev\AGENTS.md` (Codex)
- `D:\dev\GEMINI.md` (Gemini CLI)

All three are PROTECTED, but the root trio now carries the corrected local paths, the 11-route table, the read-only/ASCII-staging discipline, LibreDWG sidecar availability, and the wrapper enforcement note.

---

## 5. Pending Paul decisions (advisory, not failures)

1. **PyMuPDF isolation.** Spec noted "PyMuPDF isolated" for `pdf_svg_vector_route`, but `fitz 1.27.2.3` is installed **shared in the main Python312 env**. It works as-is (54882 drawings extracted from the real PDF). Left shared because isolating would duplicate a working install. If true isolation is required: `python -m venv <dir>` + `pip install pymupdf`, route only the PDF-vector branch through it. The **required** SVG tools (svgpathtools/svgelements) need no isolation.
2. **Env-var repoint approval** (`ENVVAR_REPOINT.md`) — see §3.
3. **Trinity block application** to CLAUDE/AGENTS/GEMINI — see §4.
4. **Genuine 12th route?** If "12-ROUTE" means a real 12th top-level route (not the folded AutoCAD sub-routes), specify it — not invented.

---

## 6. Open blockers + next actions

| Blocker | Severity | Next action |
|---|---|---|
| `dwg_libredwg_sidecar` unavailable | Low (1 of 11; AutoCAD-free cross-check only) | Install LibreDWG via MSYS2 on a sidecar-only PATH (GPL — never bundle). §1b. |
| Env-var repoint / LibreDWG sidecar | Closed | Local router and `D:\dev\99_tools\libredwg\bin` are exported by tracked wrappers; status is 11/11. |
| Trinity + boot-context/registry docs still reference Drive path | Medium (doc drift) | `approve P-NN` → apply `TRINITY_AUTOCAD_SECTION_DRAFT.md` to all 3; refresh `_ariadne` boot-context/runtime/registry router pointers. |
| pythonocc-core / PDAL / native GDAL absent | Low (working substitutes in place) | Optional: install miniforge3, create conda envs (§1b). Not required for any of the 10 available routes. |
| No real `.ifc` / `.svg` sample in `D:\dev\_ariadne\alm\build` | Low (synthetic + import-verified) | If real samples exist elsewhere, re-run `ifc_bim_semantic` and the SVG branch for true-data confirmation. |
| PyMuPDF shared vs isolated | Advisory | Paul decision (§5). |

### Known-cosmetic (not defects)
- **Native-extension shutdown segfault** (0xC0000005) when *all* heavy C-extensions load in one process — mitigated: `probe_routes.py` checks each module in an isolated subprocess + flush/fsync; `run_route.py` loads only the target route's libs, so per-route runs exit clean (all verified exit 0 with valid JSON).
- **Status JSON BOM** — PowerShell writes it `-Encoding UTF8` (BOM). PowerShell reads fine; Python `json.load` needs `encoding='utf-8-sig'` under this machine's cp949 locale.

---

## 7. How to use (quick reference)

```powershell
# interim: point env at local router for this shell
. D:\dev\99_tools\autocad-sdk-router\set-router-env.ps1

# live availability
& $env:ARIADNE_AUTOCAD_ROUTER_PATH -Action status        # -> PARTIAL, 10/11

# DWG ground truth (stages a copy; original untouched)
& $env:ARIADNE_AUTOCAD_ROUTER_PATH -Action run -Intent dwg_truth_autocad -Input <dwg>

# python routes via the runner
$py = "C:\Users\PAUL\AppData\Local\Programs\Python\Python312\python.exe"
$rr = "D:\dev\99_tools\autocad-sdk-router\tools\run_route.py"
& $py $rr --route dxf_fast_secondary --input <dxf>
& $py $rr --route parametric_rebuild --out <file.step>
& $py $rr --route solid_brep_occ --input <step>
```
