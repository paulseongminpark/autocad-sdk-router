# CADOS Crash Triage — 2026-07-07 Sweep

**Registry**: `config/operations.v2.json` — 550 ops total (488 `implemented` + 62 `blocked`, verified this session).
**Sweep**: `runs/sweep_20260707/reachable_matrix_merged.jsonl` — 488 rows (one per `implemented` op), one JSON object per line, sorted by `op_id`.
**Class distribution** (counted directly from the merged matrix, this session):

| class | count |
|---|---|
| RUNNABLE | 270 |
| REACHABLE | 171 |
| RUNNABLE_BUT_DEGENERATE | 30 |
| ATTENDED_ONLY | 15 |
| CRASH | 2 |
| **total** | **488** |

Classifier source: `tools/probe_reachability.py`, `classify_probe_response()` (lines 343–413) and `classify_op_result()` (lines 428–485).

## 0. Note on inputs (read this before the rest)

This report was commissioned with four live-triage-agent JSON payloads (`crash`, `degenA`, `degenB`, plus the 15-op ATTENDED_ONLY ask). Two of those payloads were unusable as given, so this report does not repeat them verbatim — it replaces them with direct file evidence, cited by path:

- **`crash` input was a stub, not real triage output** (`{"data":{"test":"ok"},"summary":"test","findings":[{"id":"a","severity":"low","detail":"test"}]}`). Section 1 below is built entirely from the merged matrix rows, per-op `probe_result.json` files, and per-op `empty/stdout.txt` router logs on disk — not from this stub.
- **`degenB`'s `findings` array was truncated mid-entry.** It cuts off inside `write.entity.solid3d.primitive`'s detail text at `"...createBox/createSphere/createTorus/createWe"` (mid-word, `createWedge`), after which the raw text of this report's own task instructions appears where JSON should continue. Only 2 of the last 15 `RUNNABLE_BUT_DEGENERATE` ops (`write.entity.solid3d.loft` complete, `write.entity.solid3d.primitive` cut off) had individual root-cause findings in the input. The other 13 are root-caused independently in Section 3 below, directly from the C++ handler source (file:line cited per op) — nothing is invented; every op_id below appears either in the input JSON or in the live merged matrix.
- **No ATTENDED_ONLY payload was supplied at all.** Section 4 is built entirely from the merged matrix plus each op's work-dir artifacts (or absence thereof).
- `degenA` (first 15 `RUNNABLE_BUT_DEGENERATE` ops) was complete and is used as given, cross-checked against the matrix and source where cited.

---

## 1. Live CRASH ops (2 of 488)

| op_id | family | matrix class | `empty_arg_probe.status` | reason |
|---|---|---|---|---|
| `live.jig.point_probe` | live | CRASH | partial | native job produced no parseable result JSON |
| `live.status` | live | CRASH | partial | native job produced no parseable result JSON |

Evidence:
- Matrix rows: `runs/sweep_20260707/reachable_matrix_merged.jsonl:297` (`live.jig.point_probe`), `:302` (`live.status`).
- `runs/sweep_20260707/work/live_jig_point_probe/probe_result.json`: `empty_env.status="partial"`, `exit_code=0`, `result_ref=null`.
- `runs/sweep_20260707/work/live_jig_point_probe/empty/stdout.txt`: router-level JSON, `status:"ROUTE_NONZERO"`, `execution.engine_exit_code:-11`, `execution.engine_output:{"status":"NO_ACTIVE_AUTOCAD","detail":"No running AutoCAD COM application was found for full_autocad native job mode."}`.
- `runs/sweep_20260707/work/live_status/probe_result.json` and `.../empty/stdout.txt`: identical shape — `engine_exit_code:-11`, same `NO_ACTIVE_AUTOCAD` detail.
- Both `empty/stderr.txt` files are 0 bytes.

**Mechanism.** Both ops are registered `host_eligibility: ["full_autocad"]` only in `config/operations.v2.json` — i.e., by the registry's own contract they require an attended, already-open AutoCAD session, and are **not** dbx/coreconsole-eligible. `live.jig.point_probe`'s own registry `notes` field says so explicitly: *"Router job drives a point probe through the live jig path; Core Console can only report support status."* The sweep nonetheless drove both through `dwg_truth_autocad` → `full_autocad` COM native-job mode headlessly via `accoreconsole`. The engine itself correctly *detects* the missing session (`engine_output.status = NO_ACTIVE_AUTOCAD`) but the native job process still hard-exits with `-11` (an abnormal/access-violation-class exit) instead of returning that detection as a clean structured JSON error — so `cadctl` never gets parseable JSON back, and `classify_probe_response`'s `status=="partial"` branch (line 384–387: *"the engine most likely died mid-run without an OS-level crash exit code reaching us"*) classifies it CRASH.

**Honest classification verdict.** CRASH is the technically correct label for *this probe*, under the classifier's current rules — but the underlying defect is not evidence of broken op logic in the op's actual supported (attended) code path. It is a **host-eligibility/robustness gap**: a `full_autocad`-only op invoked outside its supported host class should soft-fail with the `NO_ACTIVE_AUTOCAD` structured error it already computes, not abnormally exit at `-11` before that string reaches stdout as parseable JSON. Do not read this as "these two ops are broken when used correctly" — that has not been tested here.

**Repro plan.**
1. Confirmed above: `host_eligibility=["full_autocad"]` only for both ops (`config/operations.v2.json`).
2. Re-run `tools/probe_reachability.py --live --ops live.jig.point_probe,live.status` against the staged fixture, this time with an **actual interactively-open AutoCAD session** (attended, not `accoreconsole`), to separate "genuinely broken op" from "unsupported host class, should soft-fail."
3. If it still exits `-11` attended → real native defect, escalate under owner ticket `M08J-T01` (both ops carry this ticket).
4. If it succeeds attended → the fix belongs in the router/dispatcher layer: detect "no attended full_autocad session" *before* invoking the native job for `full_autocad`-only ops, and short-circuit to `status:"error", error_code:"NO_ACTIVE_AUTOCAD"` instead of dispatching into the crash path. `engine_output.status` already contains the string needed; it just isn't surfaced pre-crash.
5. Track under `M08J-T01`.

---

## 2. Regression pair: `extend.customclass.create` / `extend.customobject.create`

**Historical resolution (2026-07-06, Lane G → Lane I).** `reports/lane_i_router_fix_resolution.json`: Lane G traced a router dispatch bug where `live_edit`-default-write-mode ops always routed `cadctl.run_operation`'s headless surface to the attended `full_autocad` COM branch. Lane I fixed `tools/autocad-router.ps1` (commit `b3f456d`) to honor `handler.execution_host_class` from the registry instead of `write_mode`, then re-probed 34 previously-CRASH ops. Result rows for this pair (`lane_i_router_fix_resolution.json` lines 41–57): both went `old_class:"CRASH" → new_class:"RUNNABLE", resolved:true`. `config/operations.v2.json`'s `notes` field for both ops still asserts today: *"this op is now live-re-probed RUNNABLE through the headless Invoke-CadJobRoute path."*

**This sweep (2026-07-07) reclassifies both as ATTENDED_ONLY.** Matrix rows:
```
extend.customclass.create:  class=ATTENDED_ONLY, fixture_available=true,
  fixture_evidence="test_native/job_create_args.json (existing working fixture)",
  empty_arg_probe.reason="probe exceeded 60.0s (no headless UI to answer it)"
extend.customobject.create: class=ATTENDED_ONLY, fixture_available=true,
  fixture_evidence="test_native/job_record_create.json (existing working fixture)",
  empty_arg_probe.reason="probe exceeded 60.0s (no headless UI to answer it)"
```

**File evidence — the empty-arg call actually succeeded, headlessly, this same sweep.**
- `runs/sweep_20260707/work/extend_customclass_create/empty/stdout.txt`: router-level JSON, `status:"PASS"`, `engine_exit_code:0`, `result.created:true, errorstatus:0`, `process_hygiene.status:"PASS", new_acad_processes:[]`. Timestamp `2026-07-07T16:11:18+09:00`.
- `runs/sweep_20260707/work/extend_customobject_create/empty/stdout.txt`: same shape, `created:true, errorstatus:0`, `process_hygiene PASS`. Timestamp `2026-07-07T16:13:01+09:00`.
- `runs/sweep_20260707/work/extend_customclass_create/valid/job_args.json`: `{"operation":"extend.customclass.create","center":{"x":10.0,"y":20.0,"z":0.0},"size":5.0}` — matches `FIXTURES["extend.customclass.create"]` in `tools/probe_reachability.py:309-312` exactly.
- **Neither work dir has a `probe_result.json` or any `valid/stdout.txt`/`valid/stderr.txt`.** The valid-arg call's `job_args.json` was written but no output followed it.

**Why the good empty-arg result got thrown away.** `probe_one()` (`tools/probe_reachability.py:498-519`) runs the empty-arg call, then the valid-arg call, **sequentially inside one child process**, and `_worker_main` (line 530-543) only writes `probe_result.json` once, *after both calls return*. `_spawn_worker` (line 546+) wraps the whole child process in `subprocess.run(..., timeout=timeout_sec)`; this sweep's row reports `"probe exceeded 60.0s"`, i.e. a 60s budget (the script's own `DEFAULT_TIMEOUT_SEC` is 120.0 at line 112, so this sweep ran with a tightened per-op timeout). When the *second* (valid-arg) call hangs past that budget, `subprocess.TimeoutExpired` fires, `_spawn_worker` returns `{"_probe_timeout": True}` (line 557-558), and `classify_op_result`'s payload-level short-circuit (line 453-458) discards the entire payload — including the already-completed, already-good empty-arg result — and stamps the row ATTENDED_ONLY. This matches exactly what's on disk: `empty/` has real output, `valid/` has only the input it was about to run, `probe_result.json` was never written because the worker process never returned.

**Hypotheses (unresolved — pick one with the settling experiment below):**
- **H1 — timeout-budget false positive.** The valid-arg call would also complete headlessly given more wall-clock; this sweep's 60s per-op budget is simply too tight for this op, and Lane I's 2026-07-06 RUNNABLE result (presumably run with a longer or op-scoped timeout, per its own `reprobe_method` field) is the accurate one.
- **H2 — genuine attended requirement specific to non-default args.** Populating `center`/`size` away from the entity's degenerate `(0,0,0)`/`size=1` defaults routes through a different, attended-only ObjectARX code path (e.g. a modal dialog on custom-class registration triggered only by non-trivial geometry) that the `{}` call never exercises.

**Settling experiment.** Re-run `tools/probe_reachability.py --live --ops extend.customclass.create,extend.customobject.create --timeout-sec 180` (or higher) in isolation and observe:
- `probe_result.json` now written with `valid_env.status=="ok"` → supports H1 (raise the sweep's default per-op timeout for this pair, or all ops).
- Still hangs at 180s → supports H2; cross-check `process_hygiene.new_acad_processes` / enumerate windows for a live modal at hang time to confirm an attended dialog is actually open, then escalate as a genuine attended-only classification (owner ticket `M08K-T01`, both ops).

---

## 3. The 30 RUNNABLE_BUT_DEGENERATE causes + fixture-gap list

**Shared mechanism** (`tools/probe_reachability.py`, `classify_probe_response` line 343-413 + `classify_op_result` line 428-485): the `{}` empty-arg control call is always attempted first. If its result shows `created:true`, `classify_probe_response(is_empty_arg=True)` returns `RUNNABLE_BUT_DEGENERATE` **unconditionally** (line 411-412) — regardless of how plausible the resulting default geometry looks. The ONLY way to override this is a `FIXTURES[op_id]` entry (`tools/probe_reachability.py:230-321`) whose valid-arg call *also* returns `created:true`; `classify_op_result` line 471 then makes `RUNNABLE` win outright over the degenerate empty-arg result. **The `FIXTURES` dict has exactly 15 entries total, and none of the 30 degenerate ops below are among them** (verified: `fixture_available=false` for all 30 rows in the merged matrix).

### First 15 (from `degenA`, complete, cross-checked)

| op_id | root cause | evidence |
|---|---|---|
| `define.assocaction.create` | Handler takes zero job args; unconditionally creates a bare `AcDbAssocAction` shell, no dependency/value-param attached (`evaluated:false`). | `families/m08kc_handlers.inc:426-451` |
| `define.constraint.group` | Handler takes zero job args; builds a bare `AcDbAssoc2dConstraintGroup` with default XY plane, zero members. | `families/m08kc_handlers.inc:302-309` |
| `editor.react.events` | Handler takes zero args; registers `AcEditorReactor` then immediately unregisters it in the same statement block before returning — `command_starts/ends=0` **by construction**, not by missing input. | `families/m08n_handlers.inc:427-441` |
| `live.overrule.enable` | Handler takes zero args; registers a persistent process-global overrule and reports registration state only — nothing in the call exercises it against a real entity edit. | `AriadneNativeJob.cpp:6879-6886` |
| `live.reactor.enable` | Handler takes zero args; registers `AcDbEditorReactor` and reports registration state only; the batch script is register→QUIT, so no doc event ever fires. | `AriadneNativeJob.cpp:6826-6832` |
| `write.dimstyle.create` | `name` silently defaults to `"ARIADNE_DIMSTYLE"`; ~70 DIMVAR fields are all optional has-flag reads with zero validation — `{}` still successfully upserts a DIMSTYLE record. | `AriadneNativeJob.cpp:6202-6379` |
| `write.entity.attribdef` | `position` defaults `(0,0,0)`; text/tag/prompt/height all optional and silently blank/default — result is a tag-less, prompt-less, text-less attribute definition. | `families/m08g_handlers.inc:809-827` |
| `write.entity.body` | **Architecturally blocked, not a fixture gap** — see below. | `families/m08g_handlers.inc:1306-1312` |
| `write.entity.face` | p0-p3 default to a real 1×1 unit quad `(0,0,0)/(1,0,0)/(1,1,0)/(0,1,0)` via `m08gPoint()`; classifier judges arg-validation, not the plausibility of the resulting shape. | `families/m08g_handlers.inc:585-596` |
| `write.entity.nurbsurface` | width/height default `1.0/1.0` → a real degree-1 bilinear 2×2-control-grid patch (`surface_area == width*height` exactly, per its own in-code comment) — genuinely non-degenerate, just never given a fixture. | `families/m08g_handlers.inc:1411-1419+` |
| `write.entity.point` | `position` defaults `(0,0,0)`; no `MISSING_ARG` check exists (contrast `write.entity.spline`, which does validate). | `families/m08g_handlers.inc:531-537` |
| `write.entity.ray` | `base` defaults `(0,0,0)`, `direction` defaults `(1,0,0)`; both optional, unvalidated. | `families/m08g_handlers.inc:539-548` |
| `write.entity.shape` | `name` hardcodes to `"ARIADNE"` when omitted — a shape name that will almost certainly not resolve in the active textstyle's SHX; genuinely visually-degenerate (unrenderable), not just unvalidated. | `families/m08g_handlers.inc:976-1001` |
| `write.entity.solid2d` | p0-p3 default to the same real 1×1 quad pattern as `write.entity.face`. | `families/m08g_handlers.inc:573-583` |
| `write.entity.solid3d.extrude` | width/depth/height default `1.0/1.0/1.0` → `createExtrudedSolid()` on a real 1×1 profile genuinely produces a non-degenerate 1×1×1 box. | `families/m08g_handlers.inc:1338-1350` |

### Last 15 (from `degenB`'s fixture-gap list; 2 findings given, 13 independently root-caused for this report)

| op_id | root cause | evidence | source of this finding |
|---|---|---|---|
| `write.entity.solid3d.loft` | width/depth/top_width/top_depth/height default `1.0/1.0/0.5/0.5/1.0`; `createLoftedSolid()` on two synthetic rect profiles. **Deliberately** left fixture-less -- **reaffirmed by 2026-07-08 adversarial review**: the only candidate fixture just rescales the same synthetic same-profile rectangle these defaults already produce, gaming the `created:true` classifier rather than proving non-degeneracy (see below). | `families/m08g_handlers.inc:1381-1398` | given (degenB, complete) |
| `write.entity.solid3d.primitive` | `primitive` defaults `"box"`, x=y=z=1.0; dispatches to `createBox/createSphere/createTorus/createWedge/createPyramid/createFrustum` depending on the (unvalidated, defaulted) `primitive` string. Self-contained parametric args — pure fixture-authoring oversight. | `families/m08g_handlers.inc:1314-1336` | given in degenB but truncated mid-word at `createWe`; completed here from source |
| `write.entity.solid3d.revolve` | width/height/angle default `0.5/1.0/2π`; `createRevolvedSolid()` on a synthetic rect profile — full 360° revolve of a real rectangle, genuinely non-degenerate. **PROMOTED by 2026-07-08 adversarial review**: its fixture (angle=4.71238898 rad = 270°, an OPEN solid) is materially different topology from the handler's own 360°-CLOSED default, not a rescale of it -- not gaming the classifier. | `families/m08g_handlers.inc:1352-1365` | root-caused for this report |
| `write.entity.solid3d.sweep` | width/height/length default `0.2/0.2/2.0`; `createSweptSolid()` sweeps a real rect profile along a straight `AcDbLine` path. **PROMOTED by 2026-07-08 adversarial review**: its fixture drives a distinct swept path/profile combination through `createSweptSolid()`, not a rescale of the default -- not gaming the classifier. | `families/m08g_handlers.inc:1366-1380` | root-caused for this report |
| `write.entity.subdmesh` | x_len/y_len/z_len default `1.0/1.0/1.0`; `AcDbSubDMesh::setBox(...)` on real dimensions — pure fixture-authoring oversight. | `families/m08g_handlers.inc:1436-1445` | root-caused for this report |
| `write.entity.surface` | width/height default `1.0/1.0`; `AcDbSurface::createFrom()` on a real 1×1 rect profile — pure fixture-authoring oversight. | `families/m08g_handlers.inc:1400-1409` | root-caused for this report |
| `write.entity.table` | `text` defaults `"Ariadne"`, rows/columns default `2/2`, row_height/column_width/text_height all default; builds a real 2×2 table with placeholder cell text — pure fixture-authoring oversight. | `families/m08h_handlers.inc:370-399+` | root-caused for this report |
| `write.entity.tolerance` | `text` defaults to the FCF placeholder `"%%v"` at origin, normal `(0,0,1)`, direction `(1,0,0)` — a syntactically-valid but semantically-empty feature control frame. | `families/m08g_handlers.inc:1293-1304` | root-caused for this report |
| `write.entity.trace` | p0-p3 default to the same real 1×1 quad pattern as `write.entity.face`/`solid2d`. | `families/m08g_handlers.inc:561-572` | root-caused for this report |
| `write.entity.xline` | `base` defaults `(0,0,0)`, `direction` defaults `(1,0,0)` — pure fixture-authoring oversight, same pattern as `write.entity.ray`. | `families/m08g_handlers.inc:550-560` | root-caused for this report |
| `write.linetype.create` | `name` defaults `"ARIADNE_LINETYPE"`; description/dash_lengths both optional (upsert-if-absent semantics by design) — `{}` still creates a valid (if pattern-less) linetype record. | `AriadneNativeJob.cpp:6389-6416` | root-caused for this report |
| `write.textstyle.create` | `name` defaults `"ARIADNE_TEXTSTYLE"`; every font/height/width/oblique/flag field optional — `{}` still upserts a usable textstyle record with engine defaults. | `AriadneNativeJob.cpp:6417-6454` | root-caused for this report |
| `write.ucs.create` | `name` defaults `"ARIADNE_UCS"`; origin/x_axis/y_axis all optional — `{}` still upserts a UCS record at the world-default orientation. | `AriadneNativeJob.cpp:6455-6479` | root-caused for this report |
| `write.view.create` | `name` defaults `"ARIADNE_VIEW"`; every geometric/clip/perspective field optional — `{}` still upserts a VIEW record with engine defaults. | `AriadneNativeJob.cpp:6480-6527` | root-caused for this report |
| `write.vport.create` | `name` defaults `"ARIADNE_VPORT"`; every geometric/UCS/grid/snap field optional — `{}` still upserts a VPORT record with engine defaults. | `AriadneNativeJob.cpp:6528-6568+` | root-caused for this report |

### Category rollup (all 30)

- **Deliberately deferred by design (1):** `write.entity.solid3d.loft` — the ASM family; a genuinely non-degenerate cross-section/profile is a modeler-dependent input barriered behind the B6 ASM non-degeneracy gate, explicitly out of F1 scope per the `FIXTURES` dict's own header comment (`tools/probe_reachability.py`, confirmed by direct read). Adding numeric-only fixture args would technically flip the class label (the classifier only checks `created:true`) but would just re-exercise the same synthetic rectangle the `{}` call already produces — the team's own comment says not to game the classifier this way. **Reaffirmed 2026-07-08 (adversarial review):** loft was promoted in a first pass, then reverted for exactly this reason.
- **Promoted despite the ASM family, distinct topology/path (2):** `write.entity.solid3d.{revolve,sweep}` — unlike `loft`, their handlers' own non-degeneracy comes from the CALLER'S args, not just the defaults: `revolve`'s fixture drives a 270° OPEN solid against the handler's 360°-CLOSED default (materially different topology), and `sweep`'s fixture drives a distinct swept path/profile combination through `createSweptSolid()`. Confirmed by 2026-07-08 adversarial review to be genuine promotions, not classifier-gaming, and left in `FIXTURES`. See `reports/crash_triage_20260707.md` (this file) and `tools/probe_reachability.py`.
- **Pure fixture-authoring oversight (21):** the other 12 in the "last 15" table above (`solid3d.primitive`, `subdmesh`, `surface`, `table`, `tolerance`, `trace`, `xline`, `linetype.create`, `textstyle.create`, `ucs.create`, `view.create`, `vport.create`) + 9 of the "first 15" (`write.dimstyle.create`, `write.entity.{attribdef,face,nurbsurface,point,ray,shape,solid2d,solid3d.extrude}`). All take self-contained numeric/string args with no external DWG-entity dependency — a `FIXTURES[op_id]` entry with real values, authored the same way the existing 15 entries are (handler arg-key reads or an existing `test_native/job_*.json` fixture), legitimately promotes each to RUNNABLE on the next `--live` sweep.
- **Architecturally blocked, needs native code (1):** `write.entity.body` — `families/m08g_handlers.inc:1306-1312` does `new AcDbBody(); setDatabaseDefaults(pDb);` and calls **no** ACIS/ASM content-setting API at all, for any possible arg set (the job JSON is never even read in this branch). The registry's own `notes` field independently confirms: *"CREATED_DEGENERATE by construction; not certifiable non-degenerate until a content-setting C++ path exists."* No fixture can fix this.
- **Needs probe-harness capability beyond one call (5):** `define.assocaction.create`, `define.constraint.group`, `editor.react.events`, `live.overrule.enable`, `live.reactor.enable` — all take zero job args; each needs either a chained follow-up call (e.g. `define.assocaction.addDependency` onto the returned handle) or an in-probe triggering action (a real command/doc-edit between register and inspect). The current single-call-per-op harness (`probe_one()`) cannot express either.

**Net result (2026-07-08, after the adversarial review above): 23 of these 30 rows are promoted (21 pure-oversight + revolve + sweep); 7 stay fixture-less** (`write.entity.body`, `define.assocaction.create`, `define.constraint.group`, `editor.react.events`, `live.overrule.enable`, `live.reactor.enable`, `write.entity.solid3d.loft`) — matching `tools/probe_reachability.py`'s `FIXTURES` / `tests/unit/test_probe_degen_fixtures.py`'s `NON_PROMOTABLE_OPS`.

### Registry-drift footnote (verified, not from input)

5 of the "last 15" ops (`write.entity.subdmesh`, `write.entity.table`, `write.entity.tolerance`, `write.entity.trace`, `write.entity.xline`) show `policy_status_policy: "catalogued_not_runnable"` in this sweep's matrix row, but `config/operations.v2.json` currently reads `status: "implemented"` / `policy.status_policy: "implemented"` for the same 5 ops (both checked live, this session). This is a registry-vs-sweep-snapshot drift, orthogonal to the degenerate-cause diagnosis above, but worth its own queue item so downstream consumers don't see disagreeing status labels for the same op.

---

## 4. 15 ATTENDED_ONLY — verification pass (genuine vs. possible false positives)

All 15 rows share one `empty_arg_probe.reason`: `"probe exceeded 60.0s (no headless UI to answer it)"` — a payload-level `_probe_timeout` short-circuit (`classify_op_result` line 453-458), not a per-call error message. Full list, with `fixture_available` and whether any work-dir artifact exists on disk:

| op_id | fixture_available | work-dir artifact before kill |
|---|---|---|
| `automate.com.bridge_objectid` | false | none |
| `automate.com.entity_helpers` | false | none |
| `extend.customclass.create` | true | **empty/stdout.txt = completed PASS** (see §2) |
| `extend.customobject.create` | true | **empty/stdout.txt = completed PASS** (see §2) |
| `inspect.face.surface_as_trimmed_nurbs` | false | none |
| `inspect.face.surface_type` | false | none |
| `inspect.layout.list` | false | none |
| `inspect.loop.face` | false | none |
| `inspect.loop.type` | false | none |
| `inspect.shell.complex` | false | none |
| `inspect.shell.type` | false | none |
| `inspect.subentity.class_id` | false | none |
| `inspect.vertex.point` | false | none |
| `inspect.xref.list` | false | none |
| `write.layout.create` | false | none |

**Verdict:**
- **13 "clean" ATTENDED_ONLY** — `automate.com.{bridge_objectid,entity_helpers}`, `inspect.face.{surface_as_trimmed_nurbs,surface_type}`, `inspect.layout.list`, `inspect.loop.{face,type}`, `inspect.shell.{complex,type}`, `inspect.subentity.class_id`, `inspect.vertex.point`, `inspect.xref.list`, `write.layout.create`. Confirmed (`Glob`, this session): **zero** output files exist in any of these 13 work dirs — no `stdout.txt`, no `stderr.txt`, nothing. That means the very first native call for each of these hung with no output at all, consistent with a genuine attended-UI block from the start, not a partial/near-success. No evidence of false positive for these 13.
- **2 possible false positives** — `extend.customclass.create`, `extend.customobject.create`. As detailed in §2: the empty-arg call for both **demonstrably completed successfully** (headless PASS, `created:true`, `errorstatus:0`, ~13-17s wall clock) before the *same worker process's second (valid-arg) call* hung past the 60s budget and the whole payload was discarded. These two should not be trusted as "genuinely attended-only" until the §2 settling experiment (rerun with a longer timeout) is run.

---

## 5. REACHABLE → RUNNABLE promotion criteria + counts

**Promotion rule** (same classifier code as §3): `REACHABLE` = a genuine, structured native dispatcher error (`status=="error"` with an `error_code` other than `OPERATION_NOT_IMPLEMENTED` / `OPERATION_DISPATCH_MISMATCH` / `ORIGINAL_WRITE_FORBIDDEN`) on whichever probe actually ran (`classify_probe_response` line 392-402: *"every other structured native error ... is an honest, reachable dispatcher response"*). Promotion is mechanically identical to the §3 fixture-gap fix: author a `FIXTURES[op_id]` entry with real values (evidence-grounded the same way the existing 15 are — handler arg-key reads or an existing `test_native/job_*.json` fixture); if the resulting `valid_arg_probe.class == RUNNABLE`, `classify_op_result` line 471 makes it win outright, regardless of the empty-arg result.

**Counts (live, this sweep, verified this session):**

| metric | value |
|---|---|
| REACHABLE rows | 171 |
| … with `fixture_available == true` | **0** |
| `error_code` = `MISSING_ARG` | 132 |
| `error_code` = `MISSING_HANDLE` | 15 |
| `error_code` = `MISSING_PATH` | 3 |
| `error_code` = `MISSING_OUTPUT_PATH` | 3 |
| `error_code` = `MISSING_KEY` | 1 |
| `error_code` = `WIPEOUT_CLIP_FAILED` | 1 |
| no `error_code` at all | 16 |

Every single REACHABLE op is sitting one `FIXTURES` entry away from a promotion *attempt* — none have been tried and failed; the class is entirely "honestly validated its args, never given a fixture."

**The 16 "no `error_code`" rows are a distinct sub-population**, not a fixture gap. All 16 share the literal reason string `"Unsupported CAD job operation: <op_id>"`: `anchor.clear`, `anchor.get`, `anchor.list`, `anchor.set`, `apply.patch`, `diff.before_after`, `inspect.entity.identity_contract`, `inspect.xdata.semantic_anchor`, `patch.apply_staged`, `patch.dry_run`, `query.entities`, `render.layout`, `run.corpus.batch`, `validate.ir`, `validate.patch`, `verify.cross_engine.dwg`. Cross-checked against `config/operations.v2.json` (this session): **15 of these 16 have `handler.router_lane: null`** — they are MCP/orchestration-layer surface names (the `cad.*` MCP tool layer — `cad_anchor_*`, `cad_patch_*`, `cad_query_entities`, `cad_diff_before_after`, `cad_validate_ir`, etc.), never wired to the native `ARIADNE_CAD_JOB` dispatcher that `probe_reachability.py` drives. `"Unsupported CAD job operation"` is therefore the *correct* response for those 15 — a probe-harness/scope mismatch (these op_ids shouldn't be in the native-job sweep population at all), not a real capability gap.

**One genuine anomaly: `render.layout`.** Unlike the other 15, its registry entry claims `handler.router_lane: "ARIADNE_CAD_JOB"` — i.e. it is *supposed* to be native-dispatchable — yet the probe got the identical `"Unsupported CAD job operation: render.layout"` response. This is a real registry-vs-dispatcher mismatch, distinct from the other 15's scope mismatch, and worth its own queue item.

**Net effect:** of the 171 REACHABLE rows, ~155 (171 − 16 scope-mismatch rows) are real fixture-gap promotion candidates, using the same methodology as §3's 21 pure-oversight `RUNNABLE_BUT_DEGENERATE` ops.

---

## Prioritized action list

1. **P0 — Router/dispatcher soft-fail for `full_autocad`-only ops without an attended session.** `live.jig.point_probe` / `live.status` should return a structured `NO_ACTIVE_AUTOCAD` error, not exit `-11`. Owner: `M08J-T01`. (§1)
2. **P0 — Settle the `extend.customclass.create`/`extend.customobject.create` regression before trusting either classification.** Rerun with `--timeout-sec 180`+; today's ATTENDED_ONLY and Lane I's 2026-07-06 RUNNABLE cannot both be blindly trusted without this. Owner: `M08K-T01`. (§2)
3. **P1 — Author `FIXTURES` entries for the 21 pure-oversight `RUNNABLE_BUT_DEGENERATE` ops** listed in §3 (`solid3d.primitive`, `subdmesh`, `surface`, `table`, `tolerance`, `trace`, `xline`, `linetype.create`, `textstyle.create`, `ucs.create`, `view.create`, `vport.create`, `dimstyle.create`, `attribdef`, `face`, `nurbsurface`, `point`, `ray`, `shape`, `solid2d`, `solid3d.extrude`) — mechanical, evidence is already in this report.
4. **P1 — Escalate `write.entity.body` as a native-code gap**, not a fixture gap — no ObjectARX content-setting API is ever called. (§3)
5. **P2 — Author `FIXTURES` entries for the ~155 fixture-gap-eligible REACHABLE ops** (§5), starting with the 132 `MISSING_ARG` rows (largest, most mechanical bucket).
6. **P2 — Design a probe-harness extension** (chained follow-up call, or an in-probe triggering action) for the 5 zero-arg ops that can't be certified with a single call: `define.assocaction.create`, `define.constraint.group`, `editor.react.events`, `live.overrule.enable`, `live.reactor.enable`. (§3)
7. **P2 — Resolve the `render.layout` registry-vs-dispatcher mismatch** (`router_lane:"ARIADNE_CAD_JOB"` claimed, but native dispatcher reports `"Unsupported CAD job operation"`). (§5)
8. **P3 — Exclude the 15 MCP-layer op_ids from the native-job sweep population** (or give them a distinct classification bucket) so they stop presenting as REACHABLE-pending-fixture: `anchor.{clear,get,list,set}`, `apply.patch`, `diff.before_after`, `inspect.entity.identity_contract`, `inspect.xdata.semantic_anchor`, `patch.{apply_staged,dry_run}`, `query.entities`, `run.corpus.batch`, `validate.{ir,patch}`, `verify.cross_engine.dwg`. (§5)
9. **P3 — Fix the registry-drift footnote**: reconcile `policy_status_policy` between the 2026-07-07 sweep snapshot and the live `config/operations.v2.json` for `subdmesh`/`table`/`tolerance`/`trace`/`xline`. (§3)
