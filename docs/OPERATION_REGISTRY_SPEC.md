# Operation Registry v2 — Specification

**Lane:** CAD OS Layer build packet `CADOS_M01`, Lane D (Operation Registry v2)
**Status:** additive to v1 — the v1 working surface (11 routes, 29 wired ops, `schemas/cad_job.schema.json`,
`config/cad_job_operation_aliases.json`, `config/autocad_router_capabilities.json`) is preserved unchanged.
**Generated:** 2026-06-21

---

## 1. What this is

The Operation Registry is the single, unified catalogue of every CAD operation the router/`cadctl` knows about —
from the 29 already-wired ops, through the 12 first-class target families of the CAD OS Layer, out to the full
480-operation native ARX/DBX catalogue. It folds two pre-existing, partially-overlapping surfaces into one
addressable registry:

1. **The wired surface** — the 29 ops in the v1 `cad_job.schema.json` enum, each with a live router/dispatcher
   path (`config/cad_job_operation_aliases.json`).
2. **The catalogued surface** — the 480 native operations in `config/autocad_native_arx_operation_catalog.json`
   (16 families × 4 engine tiers), most of which have no router path yet.

The registry is **data, not code**. The router and `cadctl` read it to decide *what* an operation is, *where* it
runs, *how* it is dispatched, and *whether it is safe to run right now*. It never asserts a capability the system
cannot actually deliver (no-fake-success).

### Files in this lane (all additive, alongside v1)

| File | Role |
|---|---|
| `config/operations.v2.json` | The unified Operation Registry (one record per operation + per catalog family). |
| `config/host_matrix.v2.json` | Per-family host resolution (which AutoCAD host, headless vs attended) + the two-vocabulary crosswalk. |
| `config/capabilities.v2.json` | Route × capability map (references, does not modify, the v1 capabilities probe file). |
| `config/policy.v2.json` | Write-safety policy (read default; staged-write preconditions; write_original approval; raw-command ban). |
| `docs/OPERATION_REGISTRY_SPEC.md` | This document. |

`config/operations.v2.json` is the validated artifact of the sibling **Schema lane**: it conforms to
`schemas/operation_registry.v2.schema.json` (`$id` `ariadne.operations_registry.v2`), which is the authoritative
record-shape contract. (That schema, the v2 job schema, and the result/IR/patch/diff schemas are owned by the
Schema lane, not Lane D — this lane references them and validates against them.) The registry's `input_schema` /
`output_schema` fields point at those sibling schemas: requests at `schemas/cad_job.v2.schema.json#/allOf`
(`…autocad_sdk_job.v2`, reusing the v1 `$defs.point`), results at `schemas/cad_result.v2.schema.json`
(`…autocad_sdk_result.v2`), graph reads at `schemas/dwg_graph_ir.v1.schema.json`, patch validation at
`schemas/validation_report.v1.schema.json`, diffs at `schemas/cad_diff.v1.schema.json`, renders at
`schemas/visual_artifact.v1.schema.json`. **The v1 schema enum stays frozen at exactly 29 ops** — v2 ops are added
only in v2 files (see §6).

---

## 2. `operations.v2.json` record shape

Every operation entry carries:

| Field | Meaning |
|---|---|
| `id` | Canonical operation id (e.g. `inspect.database.graph`). |
| `family` | For wired-exact/catalogued ops: the catalog family (one of the 16). For router ops: the verb namespace (`inspect`/`write`/`live`/`extend`/`query`/`render`/`apply`/`validate`/`diff`). |
| `status` | One of `implemented \| wired \| stub \| catalogued \| deprecated \| blocked \| not_implemented` (see §3). |
| `engine_tier` | The catalog engine_tier (WHAT API surface): `native_arx_only \| objectdbx_capable \| managed_also \| accoreconsole_lisp_also`. |
| `host_eligibility` | Ordered, cheapest-host-first list over the **execution_host_class** enum `dbx \| coreconsole \| arx_adapter \| full_autocad` (WHERE it runs). Physical-host mapping is in `host_matrix.v2.json` `registry_vocabulary_crosswalk`. |
| `write_level` | Object `{default_write_mode, allowed_write_modes[], dwg_persisted}` over the v1 write_mode enum `read \| write_copy \| write_original \| live_edit`. `policy.v2.json` maps these to its descriptive `read/staged_write/write_original/live`. |
| `handler` | Object `{router_lane, dispatcher_symbol, execution_host_class, native_api, composed_of[]}`. `router_lane` ∈ `ARIADNE_CAD_JOB \| ARIADNE_NATIVE_JOB \| geometry_native \| full_autocad \| libredwg_sidecar \| null`. `dispatcher_symbol` is the C++/C# handler name where one exists (cross-checkable against the native dispatcher tests; `null` for catalogued/stub). |
| `mapping_type` / `catalog_op_id` | Catalog relationship from the v1 alias map: `exact` (`catalog_op_id == id`) / `alias` / `synthetic` (`catalog_op_id: null`). |
| `input_schema` / `output_schema` | String refs to the sibling validators (`schemas/cad_job.v2.schema.json#/allOf` for requests; `cad_result.v2` / `dwg_graph_ir.v1` / `validation_report.v1` / `cad_diff.v1` / `visual_artifact.v1` for results). |
| `summary` / `source_slice` / `citation` | Catalog provenance, carried for exact ops. |
| `evidence_refs[]` | Provenance: catalog op/family refs, alias-map ref, dispatcher-test ref (`tests/test_native_arx_dbx_contract.py::<symbol>`), design-doc/triage refs. |

`catalog_families[]` is a parallel list of 16 family-head records, each `{id: "catalog.family.<fam>", status:
"catalogued", catalog_op_count, by_tier, …}`. Per-op records for the ~451 unwired catalog operations are **not**
expanded individually; the family heads + counts cover the catalogue (the registry is addressable by family
without 480 stub rows). Indexing by tier/family is computed — the source catalogue is a flat list of 480.

### Result envelope (native ops)

At the native module level, ops emit the existing hand-rolled envelope from `AriadneNativeJob.cpp`:

```
{"schema":"ariadne.autocad_native_job_result.v1","engine":"native_objectarx",
 "operation":"<op>","result":{…},"status":"ok|error"[,"error":"…"]}
```

Top-level keys: `schema`, `engine`, `operation`, `result`, `status` (+ optional `error`). At the registry level,
each op's `output_schema` points at the appropriate sibling result validator
(`schemas/cad_result.v2.schema.json` for the general job lane; `dwg_graph_ir.v1` / `validation_report.v1` /
`cad_diff.v1` / `visual_artifact.v1` for the graph / patch-validate / diff / render families). The router maps the
native envelope onto the declared result schema.

---

## 3. Status vocabulary

| Status | Meaning | How it is derived |
|---|---|---|
| `implemented` | Wired AND has an asserted dispatcher handler. | The 29 v1-enum ops — all 29 have a live router path and a C++/C# handler name asserted by `tests/test_native_arx_dbx_contract.py`. 28 native + 1 managed (`inspect.database.summary`). |
| `wired` | Reachable through the router with a live path, handler not separately asserted. | Reserved; currently the 29 all qualify as `implemented`. The status exists so a future op can be `wired` before its handler test lands. |
| `stub` | A named target family with a designed-but-unbuilt handler. | The new CAD OS Layer target families whose dispatcher branch is designed but not yet compiled/verified (e.g. `inspect.database.graph`, `apply.patch`). |
| `catalogued` | Known in the 480-catalogue, no router path yet. | The 16 catalog family heads (and, by extension, the ~451 unwired catalog ops they represent). |
| `deprecated` | Retired. | None today; reserved. |
| `blocked` | Cannot run on currently-available hosts; explicit non-PASS. | `render.layout` (plot host), `live.apply_patch` (attended full-AutoCAD live edit + approval). Carries `blocked_reason`. |
| `not_implemented` | Addressable id, no handler exists at all. | Reserved as a job-result status for an id present in the registry but without any dispatch path; none carry it statically today. |

`blocked` and the `not_implemented`/`unavailable` job-result statuses are the **no-fake-success** surface: an op
that cannot actually run reports a non-PASS status as *data*, so the router never claims a host it lacks. This
mirrors the router guard that the literal `SDK_OPERATION_NOT_IMPLEMENTED` must not ship as a silent success stub —
the *registry* is the correct place to record reality.

---

## 4. The 12 first-class target families

The CAD OS Layer pins these 12 families as first-class registry entries:

| Op id | Status | Host | Note |
|---|---|---|---|
| `inspect.database.summary` | implemented | managed (dbx-eligible) | The 1 managed wired op; 4 scalar counts. |
| `inspect.database.graph` | stub | objectdbx (headless) | Per-entity graph IR (handle/type/layer/geometry). Native branch designed (`collectModelSpaceGraph`, adjacent to summary). |
| `inspect.layers` | stub | objectdbx (headless) | Enumerate layer-table records; extends `countSymbolTable`. |
| `inspect.blocks` | stub | objectdbx (headless) | Enumerate block definitions; extends `countBlockDefinitions`. |
| `inspect.entities` | stub | objectdbx (headless) | Per-entity inspection; sibling of the graph op. |
| `query.entities` | stub | objectdbx (headless) | Filtered entity query (type/layer/handle). |
| `render.layout` | **blocked** | full_autocad (attended) | Plot/publish render; no headless path. |
| `apply.patch` | stub | objectdbx (headless) | Structured edit → staged copy under journal+backup+validate. |
| `validate.patch` | stub | objectdbx (headless) | Read-only dry-run of `apply.patch`. |
| `diff.before_after` | stub | objectdbx (headless) | Entity-level diff of two graph snapshots; diff math in python. |
| `live.status` | stub | full_autocad (attended) | Active-document session status. |
| `live.apply_patch` | **blocked** | full_autocad (attended) | Live active-doc edit; requires approval. |

The 10 stub/blocked families are not claimed as working; they are registered so the router/`cadctl` can address
them, report their true status, and route them once their lanes are built. (For `inspect.database.graph`, the
native triage identified the exact insertion point: a new `else if (op == "inspect.database.graph")` branch + a
`collectModelSpaceGraph` helper modelled on `countModelSpace`/`countModelSpaceEntitiesByType`, emitting the
existing nested-array JSON. Building and verifying it requires a native rebuild + accoreconsole smoke against a
staged golden DWG — not done in this lane.)

---

## 5. Host model and the two-vocabulary crosswalk

Two 4-value vocabularies already exist and describe **different axes**:

- `execution_host_class` (alias map): `dbx | coreconsole | arx_adapter | full_autocad` — **where** an op runs.
- `engine_tier` (catalogue): `objectdbx_capable | native_arx_only | managed_also | accoreconsole_lisp_also` —
  **what API surface** an op needs.

`host_matrix.v2.json` defines the crosswalk between them and resolves each family to a concrete host plus a
`headless` flag. Hosts (cheapest → richest): `objectdbx` (hostless DBX in Core Console, headless) → `core_console`
(accoreconsole, headless) → `native_arx` (.arx/.crx dispatcher, headless) → `managed` (.NET CadJobRunner,
headless) → `full_autocad` (attended UI). The router picks the cheapest *available* host and falls back along the
v1 `fallback_to` chain. Headless ops (all `inspect.*`/`write.*`/`query.*`/`validate.*`/`diff.*` on DB-readable
tiers) run unattended; `live.jig.point_probe`, `render.layout`, `live.status`, `live.apply_patch` are
attended-only.

`capabilities.v2.json` maps the 11 routes to the capability vocabulary and gives a reverse `capability → routes`
index. It **references but never modifies** `config/autocad_router_capabilities.json`; route *availability*
remains owned by the live probe (`tools/probe_routes.py` → `reports/autocad_router_status_latest.json`). This file
is not a source of availability truth.

---

## 6. How the router / `cadctl` consume the registry

1. **Resolve op** — look up `operations.v2.json` by `id`. If absent → `not_implemented`.
2. **Check status** — `blocked`/`deprecated`/`stub` (with no handler) → return the explicit non-PASS status; never
   fabricate a result.
3. **Pick host** — read `host_eligibility` (already cheapest-first); intersect with live route availability from
   the v1 probe; choose the first available; else fall back along `fallback_to`. `host_matrix.v2.json` supplies
   the headless/attended gate.
4. **Resolve write safety** — read `write_level.default` (defaults to `read`). Apply `policy.v2.json`:
   `staged_write` requires copy+backup+journal+validation; `write_original` requires explicit approval;
   `Database.SaveAs` is forbidden (persist via QSAVE); raw command dispatch is forbidden (only enumerated ids).
5. **Validate input** — against `input_schema.ref` (`cad_job.v2.schema.json#/operations/<id>`), which carries the
   v1 arg rules verbatim for the 29 + extensions for the new families.
6. **Dispatch** — via `router_lane`/`handler` (`ARIADNE_NATIVE_JOB` for 28 native ops, `ARIADNE_CAD_JOB` for the
   managed `inspect.database.summary`, `python:<route>` / `full_autocad` for the rest).
7. **Return** — the result envelope (`output_schema.envelope`).

### Freeze points (must not break)

The 29-op enum in `cad_job.schema.json` is pinned by an exact literal-list assertion and mirrored by all-29-strings
assertions against `tools/autocad-router.ps1` and the native ARX entry source; `cad_job_operation_aliases.json` is
pinned to `== set(enum)`. **Therefore v2 is additive-files-only.** Adding a 30th op to the v1 enum is a multi-test
break. v2 ops live exclusively in `operations.v2.json` (+ `cad_job.v2.schema.json`); a v2 registry test should
assert v2 is *extend-only* (every v1-enum op present with status ∈ {implemented, wired}; no v1 enum entry removed
or renamed).

---

## 7. Coverage math

**29 wired / 480 catalogued.**

- **Wired ops:** 29 — all status `implemented` (28 `native:ARIADNE_NATIVE_JOB` + 1 `managed:ARIADNE_CAD_JOB`,
  the managed op being `inspect.database.summary`). Of these, **6** are *exact* catalog identities
  (`inspect.database.summary`, `write.layer.create`, `write.entity.line`, `write.entity.circle`,
  `write.xrecord.set`, `inspect.xrecord.get`); the other 23 are alias/synthetic router aggregates over catalog
  primitives (carried in `composed_of`).
- **Target families:** 12 first-class entries — `inspect.database.summary` (already wired, status `implemented`)
  + 9 `stub` + 2 `blocked` (`render.layout`, `live.apply_patch`).
- **`operations.v2.json` `operations[]` records:** 40 — `implemented` 29, `stub` 9, `blocked` 2. Rolled up in the
  file's `totals.by_status` / `by_family` / `by_engine_tier`.
- **Catalogued:** 480 native operations across **16 families** and **4 engine tiers**, represented by 16 family
  head records (status `catalogued`) in the parallel `catalog_families[]` array.
  - By tier: `native_arx_only` 221, `objectdbx_capable` 198, `managed_also` 45, `accoreconsole_lisp_also` 16
    (= 480).
  - By family: `custom_objects_protocols` 63, `constraints_associativity` 58, `entities` 56, `brep_solids` 54,
    `com_activex` 49, `ui_customization` 39, `editor_input` 27, `runtime_commands` 26, `geometry_kernel` 25,
    `reactors_events` 22, `objectdbx_database` 21, `symbol_tables_dictionaries` 16, `graphics_system` 9,
    `active_document_write_original` 8, `blocks_xrefs_clone` 5, `layouts_plot_publish` 2 (= 480).

So the registry covers the **29 wired** ops as `implemented`, **12 target families** as first-class (1 implemented,
9 stub, 2 blocked), and the full **480-op catalogue** as `catalogued` family heads — with the wired surface and the
catalogued surface joined on canonical `op_id` so no record is double-counted. `config/operations.v2.json` validates
clean (`jsonschema.validate`) against the sibling `schemas/operation_registry.v2.schema.json`.

---

## 8. Invariants honoured

- Original DWG files are READ-ONLY; writes are staged-copy-only by default; `write_original` is an explicit,
  approved escalation. Persistence via QSAVE, never `Database.SaveAs`.
- No-fake-success: unavailable/unbuilt ops carry `blocked`/`stub`/`not_implemented` status as data; nothing claims
  PASS for unrun work.
- v1 working surface preserved: 11 routes, 29 wired ops, v1 schema/aliases/capabilities untouched; all v2 files are
  additive and live alongside v1.
- Raw-command dispatch forbidden; only enumerated registry ids run.
- Secrets never read or printed.
