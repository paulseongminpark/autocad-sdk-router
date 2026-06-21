# CADOS_M01 — Full-Stack Ultracode Build (CAD OS Layer, Milestone 01)

**Status: PASS** (executed). On-disk record of what this packet built and how it
was accepted. Resume entry point: `handoff\TAKEOVER.md`. Decision for what's next:
`handoff\NEXT_STEP.md`.

---

## Goal

Promote the AutoCAD SDK Router from "intent → route dispatch" toward an actual CAD
**control plane** (the "CAD OS Layer"): a versioned contract layer, a stdlib-only
Python control surface with a working extract → IR → store → query → validate
walking skeleton, and a native ObjectARX graph-collection operation — all without
breaking the frozen v1 routes or modifying any original DWG.

## Scope

- **TARGET repo:** `D:\dev\99_tools\autocad-sdk-router` (git). New top-level dirs
  `handoff\` and `packets\` created this packet.
- **Allowed:** new v2 schemas/specs; new stdlib-Python control surface under
  `tools\`; the native `inspect.database.graph` op in the ObjectARX module;
  Operation Registry v2; tests; reports.
- **Out of scope (by design):** router-wiring the native op; relinking the `.arx`
  under a live `acad.exe`; non-ASCII fidelity; patch execution / visual render;
  any remote push.

## Constraints / Safety (honored)

- stdlib / JSON / Markdown for the Python control surface (Python 3.12).
- Original CAD sources READ-ONLY — work on staged copies (`staging\dwg_<stamp>\`),
  QUIT only, never SAVE.
- No edits to frozen v1 route files; no breaking edits to `autocad-router.ps1` or
  the native source.
- No secrets; no remote push.
- No fake availability, no fake success — PASS claims backed by on-disk evidence.

---

## Execution — 3 phases

**P1 — Contracts.**
- 8 schemas: `dwg_graph_ir.v1`, `cad_job.v2`, `cad_result.v2`, `cad_patch.v1`,
  `cad_diff.v1`, `validation_report.v1`, `operation_registry.v2`,
  `visual_artifact.v1` (under `schemas\`).
- 6 specs: `DWG_GRAPH_IR_SPEC`, `OPERATION_REGISTRY_SPEC`, `PATCH_ENGINE_SPEC`,
  `VALIDATION_SPEC`, `MCP_TOOL_CONTRACT`, `VISUAL_VERIFICATION_SPEC` (under
  `docs\`).
- Operation Registry v2 (`config\operations.v2.json`): `totals.by_status`
  {implemented: 30, stub: 8, blocked: 2} + 16 `catalog_families` over the 480-op
  catalog.

**P2 — Python control surface + walking skeleton + 83 new tests.**
- New code under `tools\`: `cadctl.py`, `cadctl_cli.py`, `route_select.py`,
  `run_job.py`, `normalize_result.py`, `sqlite_ir_store.py`, `ir_builder.py`,
  `validator.py`, `patch_engine.py`, `visual_report.py`, `cadagent_mcp.py`.
- Agent-facing CLI: `python tools\cadctl_cli.py {status | inspect --dwg <p>
  --out <dir> | query --ir <ir.json> --sql "<sql>" | validate --ir <ir.json> |
  registry list | registry coverage}`.

**P3 — Native `inspect.database.graph`.**
- Built into `Ariadne.AcadNative.crx` (156,160 B) via helper
  `collectModelSpaceGraph`.

---

## Acceptance — PASS (evidence)

- **Router intact:** `-Action status` = `ALL_AVAILABLE`, route_count 11 /
  available_count 11, `native_modules.status` PASS, `coreconsole_load` PASS. The
  29 v1-wired ops unchanged (frozen v1 files unmodified).
  → `reports\autocad_router_status_latest.json`.
- **Walking skeleton = PASS** → `reports\walking_skeleton_latest.json`.
  - Golden `staging\dwg_20260617_191504\input.dwg` (2,524,981 B,
    sha256[:16] `27DBF6B95FF72A89`), **TRUTH 21,747** modelspace entities, 3-way
    cross-engine (ObjectARX = ObjectDBX = AutoLISP).
  - `inspect` → `dwg_graph_ir.v1` (21,747) → SQLite (21,747 rows, rtree
    available) → query → validate (**6/6 gates**).
  - `entities_by_type`: LINE 16,276 · INSERT 2,027 · POLYLINE 1,874 · ARC 753 ·
    HATCH 669 · MTEXT 106 · CIRCLE 33 · TEXT 9 (sum 21,747).
  - Original byte-identical (staged copy only). Also proven at 3 entities.
- **Native graph op = PASS** → `reports\native_graph_smoke_latest.json`.
  - Smoked directly (accoreconsole + `.scr`) at 3 entities **and** 291,706
    entities; graph count == summary count. Zero regression; existing-op smoke
    OK; 120 tests pass.
- **Registry coverage:** `cadctl registry_coverage` → wired/implemented 30,
  `consistent = true`.
- **Tests:** 120 pass (37 existing contract + 83 new: 74 unit / 8 smoke / 1
  integration). Native-inspect integration ran LIVE (not skipped). 0 fail,
  0 skip.

---

## Deferrals (honest — D1–D5)

- **D1.** `.arx` relink blocked by a live `acad.exe` (PID 49460) file lock
  (LNK1104) — environmental, not a code defect. Identical TU linked into the
  `.crx`; on-disk `.arx` is the prior working binary, relinks on the next build
  when AutoCAD is not holding it. → `reports\build_native_latest.log`.
- **D2.** Native `inspect.database.graph` verified directly but not yet routable
  via cadctl/router — needs an `autocad-router.ps1` native allow-list edit
  (out of scope). Walking skeleton uses the existing `geometry_native` ObjectARX
  extract, which works.
- **D3.** Non-ASCII fidelity: native graph op funnels `dxf_name` / `layer` /
  `block_name` through `acharToAscii` → `?` for code points > 127 (e.g. Korean
  "설비OPEN" → "????????"). `geometry_native` path preserves bytes. Widening /
  JSON-lib vendoring = M02.
- **D4.** Coverage: 30 of 480 catalogued ops implemented (29 v1-wired + native
  graph); the rest catalogued / stub / blocked by design (phased).
- **D5.** Patch EXECUTION and visual RENDER are not_implemented safety shells
  (no destructive writes, no fake visual PASS). Live ARX named-pipe pump =
  design-only (deferred).

**Overall:** PASS. Remaining items are documented enhancements + one environmental
file-lock, not criterion failures.

## Next

Choose **`D04_IMPORT_CAD_OS_CAPABILITIES`** (Daedalus consumes CAD OS via cadctl —
recommended since the walking skeleton is PASS) **or**
**`CADOS_M02_NATIVE_IR_COMPLETION`** (router-wire the native graph op + relink
`.arx` + non-ASCII fidelity + more native ops). See `handoff\NEXT_STEP.md`.
