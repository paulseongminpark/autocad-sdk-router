# handoff/zip — convention + manifest

This folder holds **portable handoff bundles** — one self-contained `.zip` per
executed packet, so another agent or machine can pick up the work without the
full repo checkout.

## Convention

- **One zip per packet**, named after the packet:
  `handoff\zip\<PACKET_NAME>.zip`
  (e.g. `CADOS_M01_FULL_STACK_ULTRACODE_BUILD.zip`).
- The orchestrator emits the `.zip`; agents do not hand-assemble it.
- **`.zip` files are git-ignored; this `index.md` is tracked.** (Repo
  `.gitignore` already excludes `runs/` and CAD binaries; binary bundles are
  treated the same — the index is the durable, diffable record. Each zip is
  regenerable from the repo + the packet record.)
- Read **this index first**, then (if present) unzip the relevant bundle. The
  zip is a *snapshot for portability*; the live source of truth is always the
  repo files the zip was built from.

## Read order inside a bundle

1. `README.md` — what the router is.
2. The build-status doc — overall PASS + how it was accepted.
3. The full-stack handoff doc — resume / what-not-to-touch / deferrals
   (mirrors `handoff\TAKEOVER.md`).
4. `reports\*` — the evidence (status, walking skeleton, coverage, validation).
5. `config\operations.v2.json` + the core schemas — the contracts.

---

## Manifest

### CADOS_M01_FULL_STACK_ULTRACODE_BUILD.zip  *(emitted by orchestrator)*

Intended bundle members (per the CADOS_M01 closeout):

- `README.md`
- `CAD_OS_BUILD_STATUS` — overall build status / PASS summary.
- `CAD_OS_FULL_STACK_HANDOFF` — full-stack resume + deferrals.
- `reports\latest_status` — router live status.
- `reports\walking_skeleton` — walking-skeleton result (PASS, 21,747 entities,
  6/6 gates).
- `reports\operation_coverage` — Operation Registry v2 coverage (30 implemented).
- `reports\validation` — validation report.
- `config\operations.v2.json` — Operation Registry v2.
- The 3 core schemas — `dwg_graph_ir.v1`, `cad_job.v2`, `cad_result.v2`.

> **On-disk name reconciliation (honest — read before building the zip).**
> The bundle member names above are the *logical* contents. The actual files
> currently on disk use these names — map accordingly when assembling:
>
> | Logical member | Actual on-disk file | Present? |
> |---|---|---|
> | `README.md` | `README.md` | yes |
> | `CAD_OS_BUILD_STATUS` | `docs\AUTOCAD_CONTROL_PLANE_STATUS.md` (closest status doc) | yes (different name) |
> | `CAD_OS_FULL_STACK_HANDOFF` | `handoff\TAKEOVER.md` (this packet's resume doc) | yes (different name) |
> | `reports\latest_status` | `reports\autocad_router_status_latest.json` | yes (different name) |
> | `reports\walking_skeleton` | `reports\walking_skeleton_latest.json` | yes |
> | `reports\operation_coverage` | — no standalone file; coverage lives in `config\operations.v2.json` (`totals.by_status`) and is reproducible via `cadctl registry coverage` | **not a standalone file** |
> | `reports\validation` | — no standalone report file; validation is the walking-skeleton 6/6 gates in `reports\walking_skeleton_latest.json`; schema is `schemas\validation_report.v1.schema.json` | **not a standalone file** |
> | `config\operations.v2.json` | `config\operations.v2.json` | yes |
> | core schemas | `schemas\dwg_graph_ir.v1.schema.json`, `schemas\cad_job.v2.schema.json`, `schemas\cad_result.v2.schema.json` | yes |
>
> Two logical members (`operation_coverage`, `validation`) have **no standalone
> on-disk file** at CADOS_M01 close — the data exists inside
> `config\operations.v2.json` and `reports\walking_skeleton_latest.json`
> respectively. The orchestrator should either bundle those source files under
> the logical names or generate the standalone reports before zipping. Listed
> here rather than silently dropped.

Status: `CADOS_M01_FULL_STACK_ULTRACODE_BUILD.zip` is **not yet present** in this
folder at the time this index was written; the orchestrator emits it as the final
closeout step. Once present, it sits beside this file and is git-ignored.

---

### CADOS_M02_V1_COMPLETION_ULTRACODE.zip  *(present — 109 KB, 34 members)*

Unlike M01, every logical member now exists as a **standalone on-disk file** (the M01
reconciliation gap is closed). Members (all present, verified at build):

- `README.md`
- `docs\CAD_OS_BUILD_STATUS.md`, `docs\CAD_OS_FULL_STACK_HANDOFF.md`, `docs\CAD_OS_V1_ACCEPTANCE.md`
- Specs: `docs\{DWG_GRAPH_IR_SPEC,PATCH_ENGINE_SPEC,CAD_DIFF_SPEC,VALIDATION_SPEC,VISUAL_VERIFICATION_SPEC,MCP_TOOL_CONTRACT,OPERATION_REGISTRY_SPEC}.md`
- Reports: `reports\{latest_status,CADOS_M02_V1_COMPLETION_ULTRACODE,v1_acceptance_latest(.json/.md),walking_skeleton_latest,rich_ir_latest,operation_coverage_latest,patch_diff_latest,validation_latest,visual_verification_latest,live_pump_latest,native_graph_smoke_latest}`
- `config\operations.v2.json`
- Schemas: `dwg_graph_ir.v1`, `cad_job.v2`, `cad_result.v2`, `cad_patch.v1`, `cad_diff.v1`, `validation_report.v1`, `operation_registry.v2`
- `handoff\TAKEOVER.md`, `handoff\NEXT_STEP.md`, `packets\CADOS_M02_V1_COMPLETION_ULTRACODE.md`

Packet result: **PARTIAL_PASS** (12/15 full PASS). The zip is git-ignored; this index is the tracked record.
