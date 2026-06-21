# CAD OS Layer — v1 Acceptance Matrix (through CADOS_M02)

> **Purpose:** one honest table mapping each M02 PASS criterion to its realized state
> (**implemented / partial / blocked**) with the **exact evidence artifact path**, plus the
> deferrals carried forward. No criterion is marked done on aspiration. Where a thing is partial or
> deferred, this doc says so and points at the proof.
>
> **Scope:** CADOS_M01 (walking skeleton + frozen v1 surface) **plus** CADOS_M02 (native router-wire,
> native_full IR, staged-write path). **Repo:** `D:\dev\99_tools\autocad-sdk-router`.
> **Companions (authoritative state):** `docs\CAD_OS_BUILD_STATUS.md`, `docs\CAD_OS_FULL_STACK_HANDOFF.md`,
> `docs\DWG_GRAPH_IR_SPEC.md` §10, `docs\PATCH_ENGINE_SPEC.md` §A–C.

---

## 1. Truth pins (the numbers everything else is checked against)

| pin | value | evidence |
|---|---|---|
| golden original (READ-ONLY) | `staging\dwg_20260617_191504\input.dwg` | byte_size **2524981**, `sha256` `27dbf6b95ff72a89…` |
| truth entity count (modelspace) | **21747** (3-way: ObjectARX == ObjectDBX == AutoLISP) | `runs\m02_cadctl_rich\dwg_graph_ir.json` `diagnostics.entity_count` |
| `entities_by_type` (sum 21747) | LINE 16276 · INSERT 2027 · POLYLINE 1874 · ARC 753 · HATCH 669 · MTEXT 106 · CIRCLE 33 · TEXT 9 | same IR `diagnostics.entities_by_type` |
| native graph result consumed | `.result` object | `runs\dwg_truth_autocad_cad_job_20260622_012807\native_cad_job_result.json` |

> **"375" is NOT this drawing.** A separate, smaller drawing also historically named `input.dwg`
> profiles to 375 entities; that is a *different file*. The v1 truth pin is **21747** for the
> 2524981-byte drawing identified by its sha256/byte_size above. Always pin drawing identity with the
> count.

---

## 2. Acceptance matrix

Status legend: **IMPLEMENTED** = built, runs, evidence on disk · **PARTIAL** = works for the
common case, named gap remains · **BLOCKED** = cannot complete now, reason is environmental/upstream.

### 2.A Core stack (M01 frozen surface — preserved by M02)

| # | M02 PASS criterion | status | evidence artifact |
|---|---|---|---|
| A1 | `cadctl inspect` stages a COPY; original byte-identical after | **IMPLEMENTED** | `tools\cadctl.py` `inspect()` (`shutil.copy2` → `staging\golden\<ts>\`); IR `source.dwg_path` under `staging\golden\…` ≠ `original_path` |
| A2 | extract → `dwg_graph_ir.v1` produced | **IMPLEMENTED** | `tools\ir_builder.py`; `runs\m02_cadctl_rich\dwg_graph_ir.json` |
| A3 | IR → SQLite store (+ rtree) | **IMPLEMENTED** | `runs\m02_cadctl_rich\dwg_graph_ir.sqlite` (6.9 MB); `tools\sqlite_ir_store.py` |
| A4 | read-only SQL query over the store | **IMPLEMENTED** | `tools\cadctl.py` `query()` → `ariadne.cadctl.query.v1` |
| A5 | deterministic validation — required gates pass | **IMPLEMENTED** | `tools\validator.py`; **14 gates, overall `pass`** (7 pass / 0 fail / 7 patch-diff gates skip cleanly) against `runs\m02_cadctl_rich\` (VALIDATION_SPEC "M02" section) |
| A6 | **entity-count truth gate** `entity_count == len(entities) == 21747` | **IMPLEMENTED** | `entity_count_consistency` gate, `expected==actual==21747` |
| A7 | frozen v1 **29-op** surface preserved; additive only | **IMPLEMENTED** | registry `operation_count == 42`, `by_status.implemented == 33` (29 v1 + native graph + 3 native write ops), `consistent: true` (`tools\cadctl_cli.py registry coverage`) |
| A8 | stdlib-only; BOM-tolerant reads (`utf-8-sig`) | **IMPLEMENTED** | every `tools\*.py` (no third-party imports); `_JSON_ENCODING="utf-8-sig"` |
| A9 | every external command captures stdout+stderr+exit | **IMPLEMENTED** | `run_job.run_router_*` writes `stdout.txt`/`stderr.txt`; `runs\m02_cadctl_rich\stdout.txt` (38 MB) |

### 2.B Native IR completion (the M02 deliverable)

| # | M02 PASS criterion | status | evidence artifact |
|---|---|---|---|
| B1 | native `inspect.database.graph` **router-wired** (closes M01 D2) | **IMPLEMENTED** | `tools\autocad-router.ps1` `Test-NativeP1CadJobOperation` line 152; reached via `cadctl.inspect(include_rich=True)` |
| B2 | native_full IR: **layers/linetypes/styles** | **IMPLEMENTED** | IR `symbol_tables` — 70 layers, 15 linetypes, 4 text_styles, 4 dim_styles |
| B3 | native_full IR: **blocks** (defs + BTRs + INSERT projection) | **IMPLEMENTED** | IR `block_definitions` 245, `symbol_tables.block_table_records` 248, `block_references` 2027 |
| B4 | native_full IR: **layouts** | **IMPLEMENTED** | IR `layouts` (3: Model + 2 paper) |
| B5 | native_full IR: **xrefs** | **IMPLEMENTED** | IR `xrefs` (0 — a true zero for this drawing, not skipped) |
| B6 | native_full IR: **dictionaries** | **IMPLEMENTED** | IR `dictionaries`; `coverage.counts.dictionary_entries == 16` |
| B7 | native_full IR: **xrecords** | **PARTIAL** | IR `xrecords` (2 decoded); `coverage.section_status.xrecords == "partial"` |
| B8 | per-entity **XDATA** folded into IR | **PARTIAL → M03** | **0** entities carry `xdata`; `section_status.xdata == "partial"`. (Write/read XDATA *ops* are wired; graph-folding is not.) |
| B9 | per-entity **extension dictionaries** in IR | **PARTIAL → M03** | **0** entities carry `extension_dictionary_handle`; `section_status.extension_dictionaries == "skipped"` |
| B10 | **2D/3D polyline vertex geometry** | **PARTIAL → M03** | **0** of 1874 `POLYLINE` entities carry `geometry.vertices`; LWPOLYLINE path emits vertices, legacy `AcDb2dPolyline`/`AcDb3dPolyline` vertex walk not yet collected |
| B11 | non-ASCII layer/block names: **UTF-8 conversion fixed** (no `?`-funnel) | **IMPLEMENTED** | **0** of 70 layer names contain `?`; `write_ir(ensure_ascii=False)` — the M01 D3 `?`-funnel symptom is gone |
| B12 | non-ASCII names: **byte-faithful CJK strings** | **BLOCKED (upstream, D3′)** | 68/70 layer names are cp949 **mojibake** (`X-주택동(기본형)$0$TEXT` → mangled). Decode loss happens at **accoreconsole load time**, before CAD OS sees the bytes; confirmed **cross-engine** (native == managed). Join on `handle`, not name. |

### 2.C Patch / diff / visual / MCP (control surface)

| # | M02 PASS criterion | status | evidence artifact |
|---|---|---|---|
| C1 | patch **dry-run** (validate + risk + guards + plan) | **IMPLEMENTED** | `tools\patch_engine.py` `dry_run_plan` → `ariadne.cad_patch.dry_run.v1`; self-test `SELFTEST_OK` |
| C2 | original-DWG safety guards (3) enforced | **IMPLEMENTED** | `require_staged_copy`, `reject_write_original_by_default`, `require_validation` |
| C3 | **real staged write** path (mutation on a COPY, `_QSAVE`) | **IMPLEMENTED** | `autocad-router.ps1` `write_copy` → `_QSAVE` (lines 817/1007); native write ops `write.layer.create`, `write.entity.line`, `write.entity.circle` (lines 153–155) |
| C4 | `patch_engine.apply_staged(patch, dwg, out_dir)` lifecycle | **IMPLEMENTED** | `tools\patch_engine.py` `apply_staged` landed: validate→risk→guards→stage→pre-IR→apply(write_copy)→post-IR→`compute_diff`→`validate_target`→journal; truthful `ok/blocked/not_implemented/partial`; original-unchanged proof (sha256 before==after). Contract: PATCH_ENGINE_SPEC §A. |
| C5 | `cad_diff.compute_diff(pre_ir, post_ir)` → `cad_diff.v1` | **IMPLEMENTED** | `tools\cad_diff.py` landed: handle-keyed, deterministic `diff_id`, `comparison_basis: "handle"`, `summary` + `layer/geometry/bbox_changes` projections; self-test PASS |
| C6 | native write ops for create_polyline/create_text/move/delete | **PARTIAL → M03** | live `NATIVE_WRITE_OP_MAP` = `create_line→write.entity.line`, `create_circle→write.entity.circle`, `set_layer`/`create_layer→write.layer.create`; the rest return `not_implemented` (PATCH_ENGINE_SPEC §A op-map, §C) |
| C7 | MCP tool surface delegates to shells (never raw SDK) | **IMPLEMENTED** | `tools\cadagent_mcp.py`; **12** tools in `_DISPATCH` (`set(_DISPATCH)==manifest tools`), each delegating to cadctl/validator/patch_engine/cad_diff/visual_report; `transport == "mock"` |
| C8 | MCP tools for apply_staged/diff/registry_explain/visual/live wired | **IMPLEMENTED** | all bound in `_DISPATCH`: `cad.patch_apply_staged`, `cad.diff_before_after`, `cad.registry_explain`, `cad.visual_report`, `cad.live_status` (MCP_TOOL_CONTRACT wired-tools table) |
| C9 | visual render | **PARTIAL (safety shell)** | `tools\visual_report.py`; a render it cannot produce returns `NOT_IMPLEMENTED`, never a fake PASS |

---

## 3. Honest deferrals (carried forward to M03)

These are explicit non-goals/limits for v1 — **not** criterion failures. Each names its proof.

| id | deferral | why | evidence |
|---|---|---|---|
| **D1** | `Ariadne.AcadNative.arx` could not relink | **environmental** — a live `acad.exe` held the file (`LNK1104`); the identical translation unit linked fine into the `.crx`. Relinks on next clean build. | `reports\build_native_latest.log` |
| **D3′** | CJK layer/block/style names arrive as cp949 **mojibake** | **upstream** — `accoreconsole.exe` decodes the DWG code page to its own active page before CAD OS reads it; lossy at that boundary. Cross-engine confirmed (native == managed). The UTF-8 conversion *in our pipeline* is fixed (no `?`-funnel). | DWG_GRAPH_IR_SPEC §10.3; 0/70 names contain `?`, 68/70 mojibake |
| **D-XDATA** | per-entity XDATA not folded into the graph IR | phased — XDATA write/read ops are wired; graph-folding is M03 | IR: 0 entities with `xdata`; `section_status.xdata == "partial"` |
| **D-POLY** | 2D/3D polyline vertex geometry not collected | phased — LWPOLYLINE vertices emit; legacy POLYLINE `VERTEX` sub-entity walk is M03 | IR: 0/1874 POLYLINE with `geometry.vertices` |
| **D-WRITEOPS** | native write ops limited to 4 (line/circle/layer×2) | phased — `create_polyline/create_text/move_entity/delete_entity` have no native handler yet → `not_implemented` | `patch_engine.NATIVE_WRITE_OP_MAP` |
| **D-MULTIOP** | `apply_staged` applies one mutation per call | `operations[0]` only; later ops journalled `deferred`; transactional multi-op is future | `apply_staged` journal `deferred` steps |
| **D-POSTCOND** | pre/postcondition *value* evaluation vs live state | the lifecycle builds post-IR + diff (deltas available); a full evaluator is the next increment | PATCH_ENGINE_SPEC §C |
| **D-ARXPUMP** | live ARX named-pipe pump runtime | design-only | `docs\LIVE_ARX_NAMED_PIPE_DESIGN.md` |
| **D4** | 33 / 480 catalogued ops implemented | phased rollout by design | registry `operation_count == 42`, `by_status.implemented == 33` |

---

## 4. Reproduce the acceptance (read-only)

```powershell
# capability (does not run -Action status; reads published JSON / registry)
python tools\cadctl_cli.py status            # router ALL_AVAILABLE, 11/11
python tools\cadctl_cli.py registry coverage # implemented 33 of 42, consistent: true

# truth gate + native_full coverage against the live artifact (no re-extraction needed)
python -c "import json,sys; d=json.load(open(r'runs\m02_cadctl_rich\dwg_graph_ir.json',encoding='utf-8-sig')); \
print('coverage_level', d['coverage_level']); \
print('entity_count==len', d['diagnostics']['entity_count']==len(d['entities']), d['diagnostics']['entity_count']); \
print('by_type_sum', sum(d['diagnostics']['entities_by_type'].values()))"
# -> native_full / True 21747 / 21747

# validation report (14 gates, overall pass; patch/diff gates skip cleanly with no diff supplied)
python -c "import sys; sys.path.insert(0,'tools'); import validator,json; \
r=validator.validate_target(ir_path=r'runs\m02_cadctl_rich\dwg_graph_ir.json', run_dir=r'runs\m02_cadctl_rich'); \
print(r['status'], json.dumps(r['summary']))"
# -> pass {"gates_total": 14, "gates_passed": 7, "gates_failed": 0, "gates_skipped": 7}

# the M02 control surface is landed (not just designed):
python tools\patch_engine.py   # SELFTEST_OK (staged-write shell + guards)
python tools\cad_diff.py       # RESULT: PASS (handle-keyed deterministic diff)
python tools\cadagent_mcp.py   # SELFTEST_OK | tools=12 transport=mock
```

**Verdict (v1, through M02):** the core stack (2.A), the native IR backbone (2.B B1–B6, B11), and the
control surface (2.C C1–C5, C7–C8: dry-run, guards, real staged write, **`apply_staged` lifecycle**,
**`compute_diff`**, **12-tool MCP**) are **IMPLEMENTED** and proven — validation is **14 gates,
overall `pass`** on the live 21747-entity artifact. The named gaps (B7–B10 partial, B12
upstream-blocked, C6/C9 partial, plus the D-series) are **honestly deferred to M03** with evidence —
**no faked PASS anywhere**.
