# CAD OS Layer — Build Status (CADOS_M01)

> **Authoritative answer to:** *What is built, what is deferred, how do I run it, and is
> it accepted?* for the CAD OS Layer control plane added on top of the AutoCAD SDK Router.
>
> **Packet:** `CADOS_M01` · **Repo:** `D:\dev\99_tools\autocad-sdk-router` (git) ·
> **Overall status: PASS.** Every packet PASS criterion was met. The remaining items
> (below, D1–D5) are documented enhancements plus one environmental file-lock — **none is a
> criterion failure**. No fake availability, no fake success.

---

## 0. TL;DR

- The router stays the single entrypoint and is **`ALL_AVAILABLE`, 11/11 routes**; the 29
  v1-wired native ops are **intact and untouched** (frozen v1 files unmodified).
- A new **CAD OS control plane** (stdlib-only Python, `tools\`) sits on top: `cadctl`
  (CLI), a **DWG Graph IR**, a **SQLite IR store** (with rtree), a **read-only SQL query**
  path, a **deterministic validator**, an **Operation Registry v2**, and safety shells for
  patch/visual/MCP.
- **Walking skeleton = PASS** end-to-end on the golden drawing: `cadctl inspect` →
  `dwg_graph_ir.v1` (**21747** entities) → SQLite (21747 rows) → `query` → `validate`
  (6/6 gates). Original DWG stayed byte-identical (worked on a staged copy only).
- A new **native graph op** (`inspect.database.graph`) is **built** into
  `Ariadne.AcadNative.crx` and **smoked directly** (accoreconsole + `.scr`) at **3** and
  **291706** entities — graph count == summary count, consistent, zero regression.
- **120 tests pass** (37 existing contract + 83 new), **0 fail, 0 skip**; the native-inspect
  integration test ran **live**.
- **Deferred (honest):** native graph op not yet router-wired (D2); `.arx` relink blocked by
  a live AutoCAD file-lock (D1, environmental); non-ASCII funnel to `?` on the native graph
  path (D3); 30 of 480 catalog ops implemented by design (D4); patch-execute and visual-render
  are non-destructive safety shells (D5).

---

## 1. What was built (3 phases)

### Phase P1 — Contracts (`schemas\`, `config\`, `docs\`)

Eight v2 JSON Schemas plus the Operation Registry v2 and the IR / registry specs:

| Artifact | Path |
|---|---|
| DWG Graph IR schema | `schemas\dwg_graph_ir.v1.schema.json` |
| CAD job schema (v2) | `schemas\cad_job.v2.schema.json` |
| CAD result schema (v2) | `schemas\cad_result.v2.schema.json` |
| CAD patch schema | `schemas\cad_patch.v1.schema.json` |
| CAD diff schema | `schemas\cad_diff.v1.schema.json` |
| Validation report schema | `schemas\validation_report.v1.schema.json` |
| Operation registry schema (v2) | `schemas\operation_registry.v2.schema.json` |
| Visual artifact schema | `schemas\visual_artifact.v1.schema.json` |
| Operation Registry v2 (data) | `config\operations.v2.json` |
| IR spec | `docs\DWG_GRAPH_IR_SPEC.md` |
| Registry spec | `docs\OPERATION_REGISTRY_SPEC.md` |
| Patch-engine spec | `docs\PATCH_ENGINE_SPEC.md` |
| Validation spec | `docs\VALIDATION_SPEC.md` |
| MCP tool contract | `docs\MCP_TOOL_CONTRACT.md` |
| Visual-verification spec | `docs\VISUAL_VERIFICATION_SPEC.md` |

### Phase P2 — Python control surface + walking skeleton (`tools\`)

New, standard-library-only Python 3.12 modules (no third-party deps):

`cadctl.py`, `cadctl_cli.py`, `route_select.py`, `run_job.py`, `normalize_result.py`,
`sqlite_ir_store.py`, `ir_builder.py`, `validator.py`, `patch_engine.py`, `visual_report.py`,
`cadagent_mcp.py`.

These add the control surface and the walking skeleton, plus **83 new tests** (74 unit /
8 smoke / 1 integration).

### Phase P3 — Native `inspect.database.graph`

The native operation `inspect.database.graph` was added to the C++ ObjectARX module
(helper `collectModelSpaceGraph`) and compiled into `Ariadne.AcadNative.crx`
(**156160 B**). Smoked **directly** via `accoreconsole` + a generated `.scr` script.

---

## 2. Walking skeleton — the truth gate (PASS)

Report: `reports\walking_skeleton_latest.json` (`status: PASS`).

- **Golden drawing:** `D:\dev\99_tools\autocad-sdk-router\staging\dwg_20260617_191504\input.dwg`
  - size **2524981 B**, `sha256[:16] = 27DBF6B95FF72A89`
  - **TRUTH = 21747 modelspace entities**, established by 3-way cross-engine agreement
    (ObjectARX == ObjectDBX == AutoLISP) in earlier router work.
- **Pipeline proven end-to-end:**
  `cadctl inspect` → `dwg_graph_ir.v1` (entity_count **21747**) → SQLite (**21747** rows,
  rtree available) → `query` → `validate` (**6/6** gates pass).
- **`entities_by_type` (exact, sums to 21747):**

  | type | count |
  |---|---|
  | LINE | 16276 |
  | INSERT | 2027 |
  | POLYLINE | 1874 |
  | ARC | 753 |
  | HATCH | 669 |
  | MTEXT | 106 |
  | CIRCLE | 33 |
  | TEXT | 9 |
  | **sum** | **21747** |

- **Original byte-identical** — the router staged a copy and operated on it; the origin DWG's
  bytes/mtime were unchanged.
- Also proven on a **3-entity** small drawing (deterministic + live-small gates), so the
  pipeline is verified at both scales.

---

## 3. Native graph op — built and smoked (PASS)

Report: `reports\native_graph_smoke_latest.json` (`status: PASS`).

- **Op:** `inspect.database.graph` · **lane:** `ARIADNE_NATIVE_JOB` (Core Console / `.crx`).
- **Built into** `Ariadne.AcadNative.crx` (156160 B) via helper `collectModelSpaceGraph`;
  loaded alongside `Ariadne.AcadNativeDbx.dbx`.
- **Smoked DIRECTLY** (accoreconsole + `.scr`, not via cadctl) at two scales:
  - **3 entities** — graph count == `entities_len` == summary count == 3, `consistent: true`.
  - **291706 entities** — graph count == `entities_len` == summary count == 291706,
    `consistent: true`.
- **Zero regression:** existing-op smoke still OK; **120 tests** pass.

---

## 4. Operation Registry v2 (30 implemented)

Data: `config\operations.v2.json`. Spec: `docs\OPERATION_REGISTRY_SPEC.md`.

- `totals.by_status` = **{ implemented: 30, stub: 8, blocked: 2 }** (40 enumerated ops).
- **16 `catalog_families`** cover the full **480-op** native catalog
  (`config\autocad_native_arx_operation_catalog.json`).
- `cadctl registry coverage`: **wired/implemented = 30**, `consistent = true`.
- The **30 implemented** = the 29 v1-wired native ops **+** the new `inspect.database.graph`.

---

## 5. Tests (120 pass / 0 fail / 0 skip)

- **37** existing contract tests (unchanged) + **83** new (**74** unit / **8** smoke / **1**
  integration).
- The **integration native-inspect** test ran **LIVE** (not skipped).

---

## 6. How to run (cadctl — the agent-facing surface)

All commands are stdlib Python 3.12, run from the repo root
`D:\dev\99_tools\autocad-sdk-router`. JSON is printed to stdout. Exit 0 = truthful answer
(an unavailable route/host is still exit 0); exit 1 = cadctl-side failure only.

```powershell
# 0) read the published router status (read-only)
python tools\cadctl_cli.py status

# 1) stage a copy of an original DWG, extract via the router, build the IR
python tools\cadctl_cli.py inspect --dwg <path\to\original.dwg> --out <run_dir>
#    -> writes <run_dir>\dwg_graph_ir.json (dwg_graph_ir.v1)

# 2) read-only SQL over the IR's sqlite store
python tools\cadctl_cli.py query --ir <run_dir>\dwg_graph_ir.json --sql "select count(*) as n from entities"

# 3) deterministic validation gates over an IR
python tools\cadctl_cli.py validate --ir <run_dir>\dwg_graph_ir.json

# 4) operation registry views
python tools\cadctl_cli.py registry list
python tools\cadctl_cli.py registry coverage
```

Reproduce the golden walking skeleton (truth = 21747):

```powershell
python tools\cadctl_cli.py inspect --dwg staging\dwg_20260617_191504\input.dwg --out runs\skeleton_demo
python tools\cadctl_cli.py query   --ir runs\skeleton_demo\dwg_graph_ir.json --sql "select count(*) as n from entities"
python tools\cadctl_cli.py validate --ir runs\skeleton_demo\dwg_graph_ir.json
```

---

## 7. Safe vs forbidden

**Safe (read / derive only):**

- Any `cadctl` subcommand above — `inspect` stages a **copy** and never writes the original.
- `-Action status` / `-Action select` on the router; `query` and `validate` are read-only.
- Reading reports under `reports\` and run artifacts under `runs\`.

**Forbidden / out of scope this milestone:**

- Modifying any **original** `*.dwg` / `*.dxf` / `*.3dm` (originals are READ-ONLY; operate on
  staged copies only).
- Editing the **frozen v1** router/native source or the 29 wired-op files.
- Wiring the native graph op into the router allow-list (that is **M02**, see D2).
- Any destructive patch execution or live ARX named-pipe pump (safety shells only; see D5 and
  `docs\LIVE_ARX_NAMED_PIPE_DESIGN.md`).
- Reading or printing secrets; any remote push.

---

## 8. Deferred / partial (honest — not criterion failures)

- **D1 — `.arx` relink blocked by a live AutoCAD file-lock.**
  `Ariadne.AcadNative.arx` could not relink because a live `acad.exe` (PID 49460) held the
  file (`LNK1104`). This is **environmental, not a code defect** — the identical translation
  unit linked successfully into the `.crx`. The on-disk `.arx` is the prior working binary and
  will relink on the next build when AutoCAD is not holding it.
  Evidence: `reports\build_native_latest.log`.

- **D2 — Native `inspect.database.graph` is not yet routable via cadctl/router.**
  It is verified **directly** (accoreconsole + `.scr`) but reaching it through cadctl needs an
  `autocad-router.ps1` native allow-list edit — **deliberately out of scope** this packet. The
  walking skeleton uses the existing `geometry_native` ObjectARX extract, which works.

- **D3 — Non-ASCII fidelity on the native graph path.**
  The native graph op funnels `dxf_name` / `layer` / `block_name` through `acharToAscii`, so
  code points > 127 become `?` (e.g. Korean `설비OPEN` → `????????`). The `geometry_native`
  path **preserves bytes**. ASCII-funnel widening / JSON-lib vendoring is **M02**.

- **D4 — Coverage is phased by design.**
  **30 of 480** catalogued ops are implemented (29 v1-wired + the native graph op). The rest
  are catalogued / stub / blocked on purpose (phased rollout).

- **D5 — Patch execution and visual render are non-destructive safety shells.**
  `patch_engine` execution and `visual_report` rendering are `not_implemented` shells — no
  destructive writes, no fake visual PASS. The live ARX named-pipe pump is **design-only**
  (see `docs\LIVE_ARX_NAMED_PIPE_DESIGN.md`).

---

## 9. How Daedalus should consume CAD OS

Daedalus (the CAD Agent Control Plane) consumes the CAD OS Layer through `cadctl` — it does
**not** call the router or accoreconsole directly:

1. **Discover** capability: `python tools\cadctl_cli.py status` and
   `... registry coverage` (what is implemented vs catalogued).
2. **Inspect** a drawing into the IR: `... inspect --dwg <orig> --out <run>` (originals stay
   READ-ONLY; cadctl stages the copy).
3. **Query** the IR's SQLite store read-only for facts/geometry: `... query --ir <ir> --sql ...`.
4. **Validate** any derived IR against the deterministic gates: `... validate --ir <ir>`.
5. Treat **`dwg_graph_ir.v1`** as the contract between CAD OS and Daedalus; treat
   **Operation Registry v2** as the capability map. Patch/visual/live-pump are not yet
   executable — do not assume them.

The follow-on packet `D04_IMPORT_CAD_OS_CAPABILITIES` is where Daedalus formally imports these
capabilities. See `CAD_OS_FULL_STACK_HANDOFF.md` for the architecture and the next steps.

---

## 10. How to resume

- **Single source of truth for state:** this file + `CAD_OS_FULL_STACK_HANDOFF.md`.
- **Re-verify in seconds:**
  - `python tools\cadctl_cli.py status` → expect router `ALL_AVAILABLE`, 11/11.
  - `python tools\cadctl_cli.py registry coverage` → expect implemented 30, `consistent: true`.
  - Re-run the §6 golden reproduction → expect 21747 + 6/6 validate gates.
- **Reports to read (not regenerate):** `reports\walking_skeleton_latest.json`,
  `reports\native_graph_smoke_latest.json`, `reports\autocad_router_status_latest.json`,
  `reports\build_native_latest.log` (D1 evidence).
- **Pick the next packet:**
  - `D04_IMPORT_CAD_OS_CAPABILITIES` — Daedalus consumes CAD OS via cadctl, **or**
  - `CADOS_M02_NATIVE_IR_COMPLETION` — router-wire the native graph op (D2) + relink the
    `.arx` (D1) + non-ASCII fidelity (D3) + more native ops (D4).
