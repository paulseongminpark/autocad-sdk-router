# AutoCAD SDK Router (local)

## CAD OS Layer v1.0 Release Freeze

Status: PASS. Release branch: cados/cad-os-v1.0-final. Evidence root: reports/release/CADOS_V1_FINAL.json. Handoff zip: handoff/zip/CADOS_M09_V1_RELEASE_FREEZE_AND_DAEDALUS_HANDOFF.zip. Next Daedalus packet: D04_IMPORT_CAD_OS_CAPABILITIES.

Single-entrypoint router over the CAD / geometry toolchain. Agents state an **intent**;
the router live-probes tool availability, selects the strongest available route (with
fallback), and executes a real operation. No fake availability, no fake success.

- **Entrypoint**: `tools\autocad-router.ps1` -- `-Action {status|select|run|explain}`
- **Contract** (read this): `reports\AUTO_CAD_ROUTER_AGENT_CONTRACT.md`
- **Capabilities**: `config\autocad_router_capabilities.json`
- **Live status**: `reports\autocad_router_status_latest.json`
- **Env binding**: Ariadne tracked wrappers export `ARIADNE_AUTOCAD_ROUTER_*` directly.
- **CAD OS Layer status**: M03–M06 PASS · M07 PARTIAL_PASS · **M07B PASS** — native ObjectARX rich IR +
  staged patch/diff/validate + live ARX pump (`CADAGENT_PUMP`, headless + attended) + deep-native
  firing verified (reactor/overrule/selection-monitor, headless + attended). See
  `docs/CAD_OS_BUILD_STATUS.md`; build native with `tools/build_native_acad.ps1`; attended verify with
  `tools/attended/run_attended_m07b.ps1`; firing with `runs/m07b_firing/run_firing.ps1` (dedicated
  acad.exe, zero COM). Next: `CADOS_M08_FULL_OPERATION_COVERAGE_CLOSURE`. No fake PASS · original DWG
  read-only · no remote push.

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

## CAD OS Layer control plane (CADOS_M01)

A stdlib-only Python control plane (`tools\cadctl_cli.py`) layered **on top of** the router:
typed **DWG Graph IR**, a queryable **SQLite IR store**, a deterministic **validator**, and an
**Operation Registry v2**. The router and the 29 v1-wired native ops are unchanged.

- **Walking skeleton: PASS** — `inspect -> dwg_graph_ir.v1 -> SQLite -> query -> validate`
  proven end-to-end on the golden drawing at **21747** modelspace entities (6/6 validation
  gates; original byte-identical). Report: `reports\walking_skeleton_latest.json`.
- **Operation Registry v2** (`config\operations.v2.json`): **30 implemented** / 8 stub /
  2 blocked, 16 catalog families over the 480-op native catalog.
- **Native `inspect.database.graph`** is built into `Ariadne.AcadNative.crx` and smoked
  directly at 3 + 291706 entities (`reports\native_graph_smoke_latest.json`); router-wiring is
  deferred to M02.

```powershell
$C = 'D:\dev\99_tools\autocad-sdk-router\tools\cadctl_cli.py'
python $C status                                              # published router status (read-only)
python $C inspect --dwg <orig.dwg> --out <run_dir>           # stage copy, extract, build IR
python $C query   --ir <run_dir>\dwg_graph_ir.json --sql "select count(*) as n from entities"
python $C validate --ir <run_dir>\dwg_graph_ir.json          # deterministic gates
python $C registry list | python $C registry coverage        # operation registry views
```

- **Build status (authoritative):** `docs\CAD_OS_BUILD_STATUS.md` (built / deferred / how to
  run / acceptance = PASS, deferrals D1–D5).
- **Full-stack handoff:** `docs\CAD_OS_FULL_STACK_HANDOFF.md`.
- **Operation registry spec:** `docs\OPERATION_REGISTRY_SPEC.md` · **IR spec:**
  `docs\DWG_GRAPH_IR_SPEC.md`.
- **Live ARX named-pipe pump:** `docs\LIVE_ARX_NAMED_PIPE_DESIGN.md` (design) — **BUILT in CADOS_M02** as `CADAGENT_PUMP`; runtime-verified headless (see `reports\live_pump_latest.json`).

## CADOS_M02 (v1.0.0 — PASS)

CADOS_M02 took the layer to a **live, validated read + write + visual + live-pump stack** (15/15 acceptance criteria PASS):

- **Rich IR is live:** `python tools\cadctl_cli.py inspect --dwg <p> --out <dir> --include-rich` →
  `coverage_level=native_full` IR (symbol tables, blocks, layouts, xrefs, dictionaries, xrecords, db-meta; 21747 truth).
  Native `inspect.database.graph` is **router-wired** (D2 resolved).
- **Staged patch is real:** `patch_engine.apply_staged(...)` → stage copy → native write (write_copy) → diff → 14/14
  validation → journal; original byte-unchanged (live: +1 LINE 21747→21748). D5 patch-execution resolved.
- **`.arx` relink resolved (D1):** versioned `Ariadne.AcadNative.live_m02.arx`; `tools\build_native_acad.ps1` is lock-resilient.
- **Tests:** `python -m pytest tests -q` → 215 pass / 2 skip.
- **Non-ASCII (PASS):** layer names are correct Hangul, proven by code points (the earlier "mojibake" was a cp949-console display artifact, retracted).
- **Visual (PASS):** real IR→SVG `before/after/overlay` + `visual_diff` (`runs\m02_visual`).
- **Live ARX pump (PASS):** `CADAGENT_PUMP` named-pipe server, runtime-verified headless (`live.echo/status/list_documents/stop`, 21747).
- **M03 depth (within crit4 PASS):** native hatch boundary geometry, per-entity xdata, extension dictionaries. See `reports\v1_acceptance_latest.md`.

Authoritative M02 report: `reports\CADOS_M02_V1_COMPLETION_ULTRACODE.md`. Re-entry: `handoff\TAKEOVER.md`.
