# CAD OS — AutoCAD SDK control plane for AI agents

Let an AI agent (Claude / Codex / Pi / Hermes / Gemini) **drive the AutoCAD SDK
directly** — hundreds of native ObjectARX/ObjectDBX operations plus inspect / patch /
diff / validate / query — through one safe MCP server, with original drawings kept
read-only. CAD OS is a control plane layered *on top of* AutoCAD; you run your own
AutoCAD, this repo is everything around it.

> **New here? → [`INSTALL.md`](INSTALL.md)** (clone → `install.ps1` → register MCP → use).

## What you get

- **`cadagent` MCP server** (`tools/cadagent_mcp.py`) — 13 `cad.*` tools an agent calls
  in natural language. The keystone is `cad.run_operation(op_id, args, write_mode)`,
  a governed gateway to the native operations.
- **Operation registry** (`config/operations.v2.json`) — the catalog + governance
  (allow-list, write-mode policy, host eligibility) for every operation.
- **Router** (`tools/autocad-router.ps1`) — intent/operation → strongest available
  engine, with live availability probing. No fake availability, no fake success.
- **Native modules** (`prebuilt/<version>/`) — compiled ObjectARX/ObjectDBX:
  `.crx` (headless / accoreconsole), `.arx` (attended / full AutoCAD + live pump),
  `.dbx` (ObjectDBX, host-neutral).
- **`cadctl`** (`tools/cadctl_cli.py`) — the same safe surface as a CLI.
- **10 non-AutoCAD geometry routes** — DXF, IFC, STEP/BREP, mesh, point-cloud, geo,
  PDF/SVG, raster (optional Python deps; not needed for AutoCAD control).

## Status (current)

- Registry (2026-07-06, post wave-0/S/A): **525 catalogued** = **465 implemented** +
  **60 blocked** (headless-impossible: need the ASM solid modeler).
- Router lanes: **455** `ARIADNE_NATIVE_JOB` + 2 `ARIADNE_CAD_JOB` + 2 `full_autocad`
  + 66 unrouted (60 = the blocked set). The earlier 447/447 generic-reachability sweep
  predates the +8 wave-0 ops (dimstyle/linetype/textstyle/ucs/view/vport/xdata/
  polyline2d.deep); a re-sweep on the current binary is the standing capstone item.
- Python-layer ops via dedicated tools (`cad.patch_*` / `cad.diff_before_after` /
  `cad.validate_ir` / `cad.query_entities`), **2** managed, **1** live pump
  (`cad.live_status`).
- Plus ~**16 native C++ handlers** (live-pump verbs + firing/probe diagnostics) that
  exist in the module but are **not yet entered in the registry** — so the real native
  surface is ≈ **473**. See the 2026-06-29 audit in
  [`docs/CADOS_M10_FULL_AGENT_CONTROL_PLAN.md`](docs/CADOS_M10_FULL_AGENT_CONTROL_PLAN.md).
- Tests: `pytest -q` → **510 passed / 3 skipped**.
- Safety invariants: original DWG **read-only** (staged copy only, sha-verified);
  `write_original` is **always refused** from the agent surface; blocked/unknown ops are
  refused, never faked.

## Quick start

```powershell
git clone https://github.com/paulseongminpark/autocad-sdk-router.git
cd autocad-sdk-router
powershell -ExecutionPolicy Bypass -File .\install.ps1
# -> paste the printed MCP registration block into your agent; start a new session.
```

Prerequisites: **AutoCAD** (team standard 2027; `prebuilt/2027/` ships), **Python 3.10+**
(the AutoCAD core is pure stdlib + one optional `jsonschema`), **git**. Not required:
Visual Studio, the ObjectARX SDK, the .NET SDK (only for building binaries yourself or
the optional geometry routes). Full details + per-agent registration: **[`INSTALL.md`](INSTALL.md)**.

Smoke it directly:

```powershell
powershell tools\autocad-router.ps1 -Action status               # live tool availability
python   tools\cadctl_cli.py run --op inspect.layers --dwg <your.dwg>
```

## The `cad.*` MCP tools

| tool | purpose |
|---|---|
| `cad.run_operation(op_id, args, write_mode)` | run any of the 447 native ops (allow-listed; `write_original` refused) |
| `cad.inspect_drawing` / `cad.query_entities` / `cad.get_entity` | read / query the rich DWG graph IR |
| `cad.patch_dry_run` → `cad.patch_apply_staged` → `cad.diff_before_after` | change a **staged copy** (original untouched) and diff it |
| `cad.validate_ir` / `cad.visual_report` | deterministic validation / IR→SVG visual report |
| `cad.status` / `cad.registry_status` / `cad.registry_explain` / `cad.live_status` | router/registry/liveness introspection |

Discover any op: `powershell tools\autocad-router.ps1 -Action explain -Operation <id>`.

## Routes (11)

| route | engine | needs AutoCAD? |
|---|---|---|
| `dwg_truth_autocad` | native ObjectARX/ObjectDBX (+ accoreconsole / full AutoCAD / .NET / LISP adapters) | **yes** |
| `dxf_fast_secondary` | ezdxf + shapely | no |
| `ifc_bim_semantic` | ifcopenshell | no |
| `solid_brep_occ` | cadquery + OCP | no |
| `parametric_rebuild` | cadquery | no |
| `dwg_libredwg_sidecar` | LibreDWG CLI (GPL sidecar, separate process) | no |
| `mesh_analysis` | trimesh + meshio + open3d | no |
| `pointcloud_route` | open3d + laspy | no |
| `geo_vector_route` | pyogrio (bundled GDAL) + pyproj | no |
| `pdf_svg_vector_route` | svgpathtools + svgelements | no |
| `raster_compare_route` | opencv-headless + scikit-image | no |

Non-AutoCAD routes need Python deps: `install.ps1 -Full` (or `pip install -r requirements-full.txt`).

## AutoCAD version / upgrades

The code is **version-agnostic** — the router auto-detects your installed AutoCAD and
auto-loads `prebuilt/<version>/`. Only the native binaries are version-coupled: an
upgrade needs at most a native rebuild (`tools/build_native_acad.ps1`, requires Visual
Studio + the matching ObjectARX SDK), not a rewrite. Drop the rebuilt `.crx`/`.arx`/`.dbx`
into `prebuilt/<version>/` and commit. The registry, router, MCP surface, and Python
layer are unchanged across versions.

## Architecture & specs

```
autocad-sdk-router/
  tools/        autocad-router.ps1 · cadagent_mcp.py · cadctl(_cli).py · patch_engine.py · ...
  config/       operations.v2.json (registry) · autocad_router_capabilities.json
  src/          Ariadne.AcadNative (.crx/.arx C++) · Ariadne.AcadNativeDbx (.dbx) · managed extractor
  prebuilt/     <version>/ compiled native modules (shipped; clone-and-run)
  schemas/      cad_job / cad_result / dwg_graph_ir / operation_registry (v2)
  tests/        pytest suite (510 passed / 3 skipped)
```

- Install & per-agent MCP registration: **[`INSTALL.md`](INSTALL.md)**
- Full agent-control plan + handler audit: [`docs/CADOS_M10_FULL_AGENT_CONTROL_PLAN.md`](docs/CADOS_M10_FULL_AGENT_CONTROL_PLAN.md)
- MCP tool contract: [`docs/MCP_TOOL_CONTRACT.md`](docs/MCP_TOOL_CONTRACT.md)
- Operation registry spec: [`docs/OPERATION_REGISTRY_SPEC.md`](docs/OPERATION_REGISTRY_SPEC.md) · DWG IR: [`docs/DWG_GRAPH_IR_SPEC.md`](docs/DWG_GRAPH_IR_SPEC.md)
- Native design: [`docs/NATIVE_ARX_DBX_DESIGN.md`](docs/NATIVE_ARX_DBX_DESIGN.md) · patch/diff/validate: [`docs/PATCH_ENGINE_SPEC.md`](docs/PATCH_ENGINE_SPEC.md)
- Router contract: `reports/AUTO_CAD_ROUTER_AGENT_CONTRACT.md`

## License

Proprietary / internal use — see [`LICENSE`](LICENSE). Third-party components (AutoCAD/
ObjectARX = Autodesk; LibreDWG = GPL sidecar-only; Python packages) keep their own terms.
