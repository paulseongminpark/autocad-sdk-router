# TAKEOVER — CADOS_M01 (CAD OS Layer, Milestone 01)

Agent-agnostic resume doc. Read this first if you are picking up the AutoCAD SDK
Router / CAD OS Layer after CADOS_M01.

- **Repo (TARGET):** `D:\dev\99_tools\autocad-sdk-router` (git).
- **Status:** **PASS.** Every packet PASS criterion was met. Remaining items are
  documented *enhancements* + one *environmental file-lock*, not criterion
  failures. No fake PASS — see deferrals D1–D5 below.
- **Packet of record:** `packets\CADOS_M01_FULL_STACK_ULTRACODE_BUILD.md`.
- **Index of packets:** `packets\PACKET_INDEX.md`.
- **Decision for what's next:** `handoff\NEXT_STEP.md`.

---

## 1. What CADOS_M01 built

The router was promoted from "intent → route dispatch" toward an actual CAD
**control plane** (the "CAD OS Layer"): a contract layer, a stdlib-Python control
surface with a working extract→IR→store→query→validate walking skeleton, and a
native ObjectARX graph-collection operation. Three phases:

- **P1 — Contracts.** 8 v2 schemas + the Operation Registry v2 + IR/registry
  specs.
- **P2 — Python control surface + walking skeleton + 83 new tests.**
- **P3 — Native `inspect.database.graph`** built into the ObjectARX module.

### Walking skeleton (the proof it works end to end) — PASS
- Evidence: `reports\walking_skeleton_latest.json`.
- Golden input: `staging\dwg_20260617_191504\input.dwg`
  (size 2,524,981 B, sha256[:16] `27DBF6B95FF72A89`).
- **TRUTH = 21,747 modelspace entities**, agreed 3-way cross-engine
  (ObjectARX = ObjectDBX = AutoLISP).
- Pipeline: `cadctl inspect` → `dwg_graph_ir.v1` (entity_count 21,747) → SQLite
  (21,747 rows, rtree available) → query → validate (**6/6 gates**).
- `entities_by_type` (exact): LINE 16,276 · INSERT 2,027 · POLYLINE 1,874 ·
  ARC 753 · HATCH 669 · MTEXT 106 · CIRCLE 33 · TEXT 9 (sum 21,747).
- Original DWG byte-identical — the pipeline operated on a **staged copy only**.
- Also proven on a 3-entity small drawing.

### Native graph operation — PASS
- `inspect.database.graph` built into `Ariadne.AcadNative.crx` (156,160 B; helper
  `collectModelSpaceGraph`).
- Smoked **directly** via `accoreconsole` + `.scr` at 3 entities **and** at
  291,706 entities — graph count == summary count (consistent). Zero regression;
  existing-op smoke OK; 120 tests pass.
- Evidence: `reports\native_graph_smoke_latest.json` = PASS.

### Operation Registry v2 — PASS
- `config\operations.v2.json`: `totals.by_status` = {implemented: 30, stub: 8,
  blocked: 2} + 16 `catalog_families` covering the 480-op catalog.
- `cadctl registry_coverage`: wired/implemented 30, `consistent = true`.

### Router invariants — INTACT
- `-Action status` → `ALL_AVAILABLE`, `route_count` 11 / `available_count` 11,
  `native_modules.status` PASS, `coreconsole_load` PASS.
- The 29 v1-wired operations are unchanged (frozen v1 files untouched).

---

## 2. How to run it (agent-facing CLI)

The control surface is `python tools\cadctl_cli.py`:

```powershell
python tools\cadctl_cli.py status
python tools\cadctl_cli.py inspect --dwg <path.dwg> --out <dir>
python tools\cadctl_cli.py query --ir <ir.json> --sql "<sql>"
python tools\cadctl_cli.py validate --ir <ir.json>
python tools\cadctl_cli.py registry list
python tools\cadctl_cli.py registry coverage
```

The legacy router entrypoint (`tools\autocad-router.ps1 -Action {status|select|run}`)
is unchanged and still the path for the 11 wired routes. See `README.md` and
`reports\AUTO_CAD_ROUTER_AGENT_CONTRACT.md`.

---

## 3. Where the artifacts are

| Artifact | Path |
|---|---|
| Router live status | `reports\autocad_router_status_latest.json` |
| Walking skeleton result | `reports\walking_skeleton_latest.json` |
| Native graph smoke result | `reports\native_graph_smoke_latest.json` |
| Native build log (D1 lock evidence) | `reports\build_native_latest.log` |
| Operation Registry v2 | `config\operations.v2.json` |
| Schemas (8 v2/v1) | `schemas\dwg_graph_ir.v1.schema.json`, `cad_job.v2.schema.json`, `cad_result.v2.schema.json`, `cad_patch.v1.schema.json`, `cad_diff.v1.schema.json`, `validation_report.v1.schema.json`, `operation_registry.v2.schema.json`, `visual_artifact.v1.schema.json` |
| Specs | `docs\DWG_GRAPH_IR_SPEC.md`, `docs\OPERATION_REGISTRY_SPEC.md`, `docs\PATCH_ENGINE_SPEC.md`, `docs\VALIDATION_SPEC.md`, `docs\MCP_TOOL_CONTRACT.md`, `docs\VISUAL_VERIFICATION_SPEC.md` |
| New control-surface code | `tools\cadctl.py`, `tools\cadctl_cli.py`, `tools\route_select.py`, `tools\run_job.py`, `tools\normalize_result.py`, `tools\sqlite_ir_store.py`, `tools\ir_builder.py`, `tools\validator.py`, `tools\patch_engine.py`, `tools\visual_report.py`, `tools\cadagent_mcp.py` |

**Tests:** 120 pass (37 existing contract tests + 83 new: 74 unit / 8 smoke /
1 integration). The native-inspect integration test ran **LIVE** (not skipped).
0 fail, 0 skip.

---

## 4. What NOT to touch

- **Original DWG/DXF files** — read-only. Always operate on staged copies
  (`staging\dwg_<stamp>\`). Never SAVE; QUIT only.
- **Frozen v1 route files** — the 29 v1-wired operations and their files are
  unchanged and must stay that way unless a packet explicitly says otherwise.
- **`tools\autocad-router.ps1`** — do not edit the router entrypoint as a
  side effect. Router-wiring the native op (D2) is its own scoped change.
- **The live `acad.exe` process** — at packet close a live AutoCAD (PID **49460**)
  held a file lock on the on-disk `.arx` (see D1). Do not assume you can relink
  the `.arx` while AutoCAD is running.
- **Protected paths / secrets** — no `.env`, credentials, tokens, keys. No remote
  push without explicit approval.

---

## 5. Deferrals (honest — D1–D5)

- **D1 — `.arx` relink blocked by live `acad.exe` (PID 49460), LNK1104.**
  Environmental, not a code defect. The identical translation unit linked into
  the `.crx`; the on-disk `.arx` is the prior working binary and will relink on
  the next build when AutoCAD is not holding it. Evidence:
  `reports\build_native_latest.log`.
- **D2 — Native `inspect.database.graph` not yet routable via cadctl/router.**
  It is verified **directly** (accoreconsole + `.scr`) but routing it needs an
  `autocad-router.ps1` native allow-list edit, deliberately out of scope this
  packet. The walking skeleton uses the existing `geometry_native` ObjectARX
  extract, which works.
- **D3 — Non-ASCII fidelity (native graph op).** The native graph op funnels
  `dxf_name` / `layer` / `block_name` through `acharToAscii` → `?` for code
  points > 127 (e.g. Korean "설비OPEN" → "????????"). The `geometry_native`
  path preserves bytes. ASCII-funnel widening / JSON-lib vendoring = **M02**.
- **D4 — Coverage.** 30 of 480 catalogued ops implemented (29 v1-wired + native
  graph). The rest are catalogued / stub / blocked **by design** (phased).
- **D5 — Patch EXECUTION and visual RENDER are not_implemented safety shells.**
  No destructive writes, no fake visual PASS. Live ARX named-pipe pump is
  design-only (deferred).

---

## 6. Agent-specific notes

**aclaude (Claude Code — rich executor):**
- You may inspect/implement/refactor/validate within the next packet's scope.
- For CAD/DWG/DXF/IFC/STEP/etc. work, go through the router / cadctl — do not
  hand-roll native calls or ad-hoc scripts (origin-corruption / fake-extraction
  / route-drift risk).
- `tools\autocad-router.ps1`, original DWGs, and frozen v1 files are protected;
  router-wiring the native op (D2) is a scoped change, not a casual edit.
- If you need fresh-context counter-execution, hand off to Codex via the team
  routing patterns; merged state goes through `merge_executor`.

**acodex (Codex — peer rich executor):**
- Co-equal executor, not validator-only. Same router/cadctl discipline and the
  same protected paths apply.
- Good fit for independent verification of the walking-skeleton numbers and the
  registry coverage claim against a fresh checkout.
