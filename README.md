# AutoCAD SDK Router (local)

Single-entrypoint router over the CAD / geometry toolchain. Agents state an **intent**;
the router live-probes tool availability, selects the strongest available route (with
fallback), and executes a real operation. No fake availability, no fake success.

- **Entrypoint**: `tools\autocad-router.ps1` -- `-Action {status|select|run|explain}`
- **Contract** (read this): `reports\AUTO_CAD_ROUTER_AGENT_CONTRACT.md`
- **Capabilities**: `config\autocad_router_capabilities.json`
- **Live status**: `reports\autocad_router_status_latest.json`
- **Env binding**: Ariadne tracked wrappers export `ARIADNE_AUTOCAD_ROUTER_*` directly.

## Quick start

```powershell
$R = 'D:\dev\99_tools\autocad-sdk-router\tools\autocad-router.ps1'
& $R -Action status                                   # what's available now
& $R -Action select -Intent ifc                       # which route for an intent
& $R -Action run -Intent dwg  -InputPath drawing.dwg  # DWG truth via AutoCAD SDK control plane
& $R -Action run -Intent write_original -InputPath drawing.dwg  # original/live-document edit intent
& $R -Action run -Intent active_document -InputPath drawing.dwg -WriteMode live_edit -HostMode full_autocad -Script job.scr
& $R -Action run -Intent step -InputPath part.step    # STEP/BREP solid topology
& $R -Action run -Intent parametric -Out out.step      # generate a new CAD model
```

## Layout

```
autocad-sdk-router/
  tools/
    autocad-router.ps1     # single entrypoint, route dispatch
    probe_routes.py        # LIVE availability probe (isolated-subprocess per module)
    run_route.py           # real per-route work engine (non-AutoCAD routes)
  config/
    autocad_router_capabilities.json   # routes + official AutoCAD SDK control-plane policy
  reports/
    autocad_router_status_latest.json  # live machine status (regenerated each call)
    AUTO_CAD_ROUTER_AGENT_CONTRACT.md  # the binding contract
  staging/                 # ASCII-safe writable copies for batch/copy/path-hygiene modes
  runs/                    # logs, reports, extracts, exports, and change records per run
  set-router-env.ps1       # session-local ARIADNE_AUTOCAD_ROUTER_* repoint (safe)
  ENVVAR_REPOINT.md        # exact protected-file diff (apply only with approve P-NN)
```

## Routes (11 implemented; spec header says "12" -- see contract section 3)

| route | engine | available |
|---|---|---|
| dwg_truth_autocad | native ObjectARX/ObjectDBX first; accoreconsole/full AutoCAD/.NET/LISP/COM adapters | yes |
| dxf_fast_secondary | ezdxf + shapely | yes |
| ifc_bim_semantic | ifcopenshell | yes |
| solid_brep_occ | cadquery + OCP | yes |
| parametric_rebuild | cadquery | yes |
| dwg_libredwg_sidecar | LibreDWG CLI | yes |
| mesh_analysis | trimesh + meshio + open3d | yes |
| pointcloud_route | open3d + laspy | yes |
| geo_vector_route | pyogrio (bundled GDAL) + pyproj | yes |
| pdf_svg_vector_route | svgpathtools + svgelements | yes |
| raster_compare_route | opencv-headless + skimage | yes |
