# Phase 0 to Phase 5 AutoCAD Native Build Continuation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Continue the AutoCAD native ObjectARX/ObjectDBX build from the current P1/P2 implementation state without blurring evidence gaps.

**Architecture:** Keep `tools/autocad-router.ps1` as the single entrypoint. Use Core Console for headless ObjectDBX/database proof, full AutoCAD only for editor-bound ARX work, and record unsupported host behavior explicitly instead of converting it to fake success.

**Tech Stack:** PowerShell router, JSON schema, pytest, C++ ObjectARX/ObjectDBX modules, AutoCAD 2027 Core Console, full AutoCAD COM automation where editor interaction is required.

---

## Current Evidence Baseline

- P1/P2 implementation exists in `schemas/cad_job.schema.json`, `tools/autocad-router.ps1`, `src/Ariadne.AcadNative/AriadneNativeJob.cpp`, and the native/router contract tests.
- `runs/p2_batch_check_20260618_183246.json` is a partial aggregate artifact: 26/27 PASS, with `write.block.insert` failing.
- `runs/p2_stateful_batch_result_20260619_135949.json` is the current clean stateful block artifact: create, insert, and count all PASS on one staged DWG.
- `runs/phase1_entity_batch_result_20260619_140223.json` verifies the new Phase 1 `write.entity.circle` and `inspect.entity.count` operations.
- Current schema/router/native surface is 29 operations.
- `runs/p5_batch_check_20260618_185444.json` is valid P2 Batch 5 evidence: 10/10 PASS for overrule registry, overrule enable/disable, jig host support, and jig point probe across Core Console and full AutoCAD.
- `runs/full_autocad_jig_host_support_probe_20260619_140323.json` and `runs/full_autocad_overrule_registry_probe_20260619_140336.json` verify the current full AutoCAD read/probe lane after native lock hardening.
- Do not edit `reports/AUTO_CAD_ROUTER_AGENT_CONTRACT.md` during Phase 0 docs/evidence-only work.
- Do not run `graphify update`.

## Files And Roles

- `schemas/cad_job.schema.json` defines the allowed native job operation surface.
- `tools/autocad-router.ps1` selects host mode, invokes Core Console/full AutoCAD, and writes run envelopes.
- `src/Ariadne.AcadNative/AriadneNativeJob.cpp` dispatches `ARIADNE_NATIVE_JOB`.
- `src/Ariadne.AcadNativeDbx/` owns DBX custom-object/enabler code.
- `tests/test_cad_job_control_plane.py` and `tests/test_native_arx_dbx_contract.py` guard schema/router/native contract drift.
- `test_native/*.json` fixtures are the durable job requests for smoke runs.
- `runs/*.json` artifacts are evidence only; stale or partial artifacts must be labeled as such.

---

### Phase 0: Evidence And Hardening

**Purpose:** Turn the current P1/P2 implementation into a clean, current evidence baseline before widening the native surface.

- [ ] Run native build verification:

```powershell
tools\build_native_acad.ps1
```

Expected: `.dbx`, `.crx`, and `.arx` build in the native Release output folders.

- [ ] Run contract tests:

```powershell
python -m pytest tests/test_cad_job_control_plane.py tests/test_native_arx_dbx_contract.py -q
```

Expected: all selected tests pass.

- [ ] Run router status:

```powershell
tools\autocad-router.ps1 -Action status
```

Expected: DWG route available and native module probe evidence current.

- [x] Re-run the P2 stateful batch serially.

Artifact: `runs/p2_stateful_batch_result_20260619_135949.json` records PASS for block create, insert, and count using one controlled stateful DWG. No parallel host-bound runs; no `ACTIVE_DOCUMENT_MISMATCH`.

### Phase 1: ObjectDBX/CoreConsole CRUD

**Purpose:** Stabilize the headless database lane before deeper ARX behavior.

- [x] Keep Core Console as the default proof host for database summary, layer creation, line/circle creation, entity count, xrecord set/get, xdata set/get, block create/insert, layout create/list, and xref list.
- [ ] Confirm `write_original` persistence through router script-level `QSAVE`, not `Database.SaveAs(...)` from the native command body.
- [ ] Preserve managed fallback ownership for broad CRUD that does not need the native ceiling.

Expected: clean Core Console artifacts prove every Phase 1 operation, including stateful block insert.

### Phase 2: Custom Object, Enabler, And Protocol

**Purpose:** Harden first-class Ariadne custom entities/objects and their ObjectDBX enabler behavior.

- [ ] Verify `extend.customclass.create`, `inspect.customclass.count`, `extend.customobject.create`, `inspect.customobject.count`, and `inspect.protocol.queryx`.
- [ ] Confirm DBX filing/version behavior and object-enabler load behavior in Core Console.
- [ ] Keep proxy/forward-compat behavior explicit when opening drawings without the enabler.

Expected: custom class/object round-trip and protocol-extension evidence is current and separable from generic CRUD.

### Phase 3: ARX OPM, Overrule, And WorldDraw

**Purpose:** Make typed objects useful in-session without mixing in editor-only jig behavior.

- [ ] Add or verify OPM/`AcRxProperty` metadata for Ariadne custom objects.
- [ ] Keep lifecycle overrule registration and cleanup deterministic.
- [ ] Verify custom graphics through protected `subWorldDraw`, not sealed public draw methods.

Expected: overrule/worldDraw/OPM evidence is explicit about host support and cleanup.

### Phase 4: Full AutoCAD Jig And Reactor Lane

**Purpose:** Isolate editor-bound operations in full AutoCAD and keep Core Console responses honest.

- [ ] Keep `inspect.jig.host_support` returning `supported=false` in Core Console and `supported=true` in full AutoCAD.
- [ ] Verify `live.jig.point_probe` through full AutoCAD with scripted point input.
- [ ] Verify transient and persistent reactor behavior without parallel host-bound collisions.

Expected: full AutoCAD artifacts prove editor-loop operations; Core Console artifacts prove unsupported contracts, not execution.

### Phase 5: UI/COM Glue Last

**Purpose:** Add session chrome and automation glue only after the database/object/graphics/editor lanes have clean evidence.

- [ ] Defer palettes, menus, status bar, CUI, COM/ActiveX bridges, and OPM automation glue until Phases 0-4 are stable.
- [ ] Keep COM use as a host-control bridge, not as a replacement for native ObjectARX/ObjectDBX capability.
- [ ] Update root/router contract docs only under a separate explicit docs packet.

Expected: UI/COM work is last, scoped, and evidence-backed.
