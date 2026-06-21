# CAD OS Layer — Full-Stack Handoff (CADOS_M01)

> **Purpose:** the whole-stack picture for the next agent — how the AutoCAD SDK Router and the
> new CAD OS control plane fit together, the contracts that bind them, the truth gate that
> proves them, and exactly what is next.
>
> **Packet:** `CADOS_M01` (PASS) · **Repo:** `D:\dev\99_tools\autocad-sdk-router` (git).
> **Companion:** `docs\CAD_OS_BUILD_STATUS.md` (authoritative build/deferral/run/accept doc).

---

## 1. Architecture (two stacked planes)

```
                         ┌─────────────────────────────────────────────────────────┐
  AGENT / DAEDALUS  ───▶ │  CAD OS LAYER  (control plane, stdlib Python 3.12)        │
                         │                                                           │
                         │   cadctl_cli.py        agent-facing CLI                   │
                         │   cadctl.py            orchestrator (truthful)            │
                         │   route_select.py      intent -> route                    │
                         │   run_job.py           cad_job.v2 -> router invocation    │
                         │   normalize_result.py  raw -> cad_result.v2               │
                         │   ir_builder.py        extract -> dwg_graph_ir.v1         │
                         │   sqlite_ir_store.py    IR -> SQLite (+ rtree)            │
                         │   validator.py         deterministic gates                │
                         │   patch_engine.py      cad_patch.v1 (safety shell)        │
                         │   visual_report.py     visual_artifact.v1 (safety shell)  │
                         │   cadagent_mcp.py      MCP tool surface (contract)        │
                         └───────────────────────────────┬─────────────────────────┘
                                                          │  (-Action run, staged copy)
                         ┌────────────────────────────────▼────────────────────────┐
  ROUTER (unchanged) ──▶ │  autocad-router.ps1   single entrypoint, 11 routes        │
                         │                                                           │
                         │   dwg_truth_autocad ── native ObjectARX/ObjectDBX FIRST   │
                         │        Ariadne.AcadNative.crx  (Core Console / headless)  │
                         │        Ariadne.AcadNativeDbx.dbx                           │
                         │        Ariadne.AcadNative.arx  (attended; D1 relink)      │
                         │        + managed .NET / accoreconsole+LISP / COM adapters │
                         │   + 10 python routes (dxf / ifc / brep / mesh / pcl /     │
                         │     geo / pdf-svg / raster / parametric / libredwg)       │
                         └───────────────────────────────────────────────────────────┘
```

- **The router is the only thing that touches DWG bytes.** The CAD OS layer never opens a DWG
  itself — it asks the router (`-Action run`), and the router operates on a **staged copy**.
- **Native-first.** `dwg_truth_autocad` prefers the compiled C++ ObjectARX/ObjectDBX module
  (`.crx` headless via Core Console, `.dbx` for ObjectDBX read, `.arx` for attended AutoCAD),
  falling back to managed .NET / accoreconsole+LISP / COM.
- **CAD OS adds the contracts and the brain on top:** typed IR, a queryable store, a
  deterministic validator, a capability registry, and (shelled, not live) patch/visual/MCP.

---

## 2. The DWG Graph IR contract (`dwg_graph_ir.v1`)

Schema: `schemas\dwg_graph_ir.v1.schema.json` · Spec: `docs\DWG_GRAPH_IR_SPEC.md`.

- The **canonical, engine-neutral representation** of a drawing's modelspace as a graph of
  entities (handle, dxf type, layer, owner, space, geometry, vertices, …).
- Produced by `ir_builder.py` from a router extract; **loaded into SQLite** by
  `sqlite_ir_store.py` (with an **rtree** spatial index when available) so agents can ask
  read-only SQL questions instead of re-parsing.
- **It is the contract between CAD OS and its consumers (incl. Daedalus).** Downstream code
  should depend on `dwg_graph_ir.v1`, not on raw router output.
- **Integrity is checked, not assumed:** `validator.py` runs deterministic gates including IR
  schema presence, entity-count consistency (IR == extract.summary == `len(entities)`),
  no-original-write evidence, and registry-status consistency.

---

## 3. The Operation Registry v2 model

Schema: `schemas\operation_registry.v2.schema.json` · Data: `config\operations.v2.json` ·
Spec: `docs\OPERATION_REGISTRY_SPEC.md`.

- A single, machine-readable map of **what CAD operations exist and their state**:
  `totals.by_status = { implemented: 30, stub: 8, blocked: 2 }`.
- **16 `catalog_families`** index the full **480-op** native catalog
  (`config\autocad_native_arx_operation_catalog.json`) so the registry stays honest about the
  large catalogued-but-unbuilt surface.
- **Additive to v1, extend-only** — the 29 v1-wired ops are preserved; the registry now also
  carries the new native `inspect.database.graph` op (→ 30 implemented).
- Read it via `python tools\cadctl_cli.py registry list` / `... registry coverage`
  (`consistent: true`, wired/implemented = 30).

---

## 4. The walking-skeleton truth gate

Report: `reports\walking_skeleton_latest.json` (`status: PASS`). Full numbers in
`docs\CAD_OS_BUILD_STATUS.md` §2. In short:

`cadctl inspect` → `dwg_graph_ir.v1` (**21747** entities) → SQLite (**21747** rows, rtree) →
`query` → `validate` (**6/6** gates), original **byte-identical**, and the exact
`entities_by_type` breakdown (LINE 16276 / INSERT 2027 / POLYLINE 1874 / ARC 753 / HATCH 669 /
MTEXT 106 / CIRCLE 33 / TEXT 9 = 21747). Also proven at 3 entities.

This is the gate that any future change to the CAD OS stack must keep green.

---

## 5. The golden identity pin

Pin the truth fixture exactly so regressions are detectable:

| field | value |
|---|---|
| golden path | `D:\dev\99_tools\autocad-sdk-router\staging\dwg_20260617_191504\input.dwg` |
| size | **2524981 B** |
| `sha256[:16]` | **27DBF6B95FF72A89** |
| truth entity count | **21747** (3-way: ObjectARX == ObjectDBX == AutoLISP) |

The native graph op was additionally smoked directly at **3** and **291706** entities
(`reports\native_graph_smoke_latest.json`, graph count == summary count, consistent).

---

## 6. What is NOT yet wired (carry forward)

See `docs\CAD_OS_BUILD_STATUS.md` §8 for the verbatim list. Headline carry-forwards:

- **D1** `.arx` relink blocked by a live `acad.exe` lock (environmental; relinks next clean
  build). Evidence: `reports\build_native_latest.log`.
- **D2** native `inspect.database.graph` verified directly but **not router-wired** yet
  (needs an `autocad-router.ps1` native allow-list edit).
- **D3** non-ASCII funnel to `?` on the native graph path (`geometry_native` preserves bytes).
- **D4** 30 / 480 ops implemented by design (phased).
- **D5** patch-execute + visual-render are non-destructive safety shells; live ARX named-pipe
  pump is design-only (`docs\LIVE_ARX_NAMED_PIPE_DESIGN.md`).

---

## 7. Next steps (M02 / D04)

- **`CADOS_M02_NATIVE_IR_COMPLETION`** — router-wire the native graph op (D2), relink the
  `.arx` when AutoCAD is free (D1), fix non-ASCII fidelity (D3), and implement more native ops
  toward the 480-op catalog (D4).
- **`D04_IMPORT_CAD_OS_CAPABILITIES`** — Daedalus consumes the CAD OS Layer via `cadctl`,
  depending on `dwg_graph_ir.v1` and Operation Registry v2 as the contracts (§9 of the build
  status doc describes the consumption pattern).

---

## 8. Where things live (quick index)

| concern | path |
|---|---|
| Agent CLI | `tools\cadctl_cli.py` |
| Orchestrator + lane modules | `tools\cadctl.py`, `route_select.py`, `run_job.py`, `normalize_result.py`, `ir_builder.py`, `sqlite_ir_store.py`, `validator.py`, `patch_engine.py`, `visual_report.py`, `cadagent_mcp.py` |
| Schemas (v2) | `schemas\*.v2.schema.json`, `schemas\dwg_graph_ir.v1.schema.json`, `schemas\cad_patch.v1.schema.json`, `schemas\cad_diff.v1.schema.json`, `schemas\validation_report.v1.schema.json`, `schemas\visual_artifact.v1.schema.json` |
| Specs | `docs\DWG_GRAPH_IR_SPEC.md`, `OPERATION_REGISTRY_SPEC.md`, `PATCH_ENGINE_SPEC.md`, `VALIDATION_SPEC.md`, `MCP_TOOL_CONTRACT.md`, `VISUAL_VERIFICATION_SPEC.md` |
| Registry data | `config\operations.v2.json` (+ `autocad_native_arx_operation_catalog.json`) |
| Router | `tools\autocad-router.ps1`, `config\autocad_router_capabilities.json` |
| Reports (truth) | `reports\walking_skeleton_latest.json`, `native_graph_smoke_latest.json`, `autocad_router_status_latest.json`, `build_native_latest.log` |
| Build status (authoritative) | `docs\CAD_OS_BUILD_STATUS.md` |
| Live-pump design (unbuilt) | `docs\LIVE_ARX_NAMED_PIPE_DESIGN.md` |
