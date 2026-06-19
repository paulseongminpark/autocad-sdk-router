# P2 Native CAD Job Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the native ObjectARX/ObjectDBX CAD job control plane beyond P1 custom class/object probes into a broader P2 operation surface.

**Architecture:** Keep the router as the single entrypoint and dispatch all P2 jobs through `ARIADNE_NATIVE_JOB` when the DWG route is selected. Prefer Core Console-verifiable database operations first; expose host-bound features as explicit capability/job contracts rather than fake success.

**Tech Stack:** PowerShell router, JSON schema, pytest contract tests, C++ ObjectARX/ObjectDBX modules, AutoCAD 2027 Core Console.

---

## 2026-06-19 Evidence Sync

This file is now a historical P2 implementation plan plus current evidence notes. Do not read
the unchecked boxes below as proof that the implementation is absent.

Current verified state:
- P1/P2 implementation exists across `schemas/cad_job.schema.json`, `tools/autocad-router.ps1`,
  `src/Ariadne.AcadNative/AriadneNativeJob.cpp`, `tests/test_cad_job_control_plane.py`, and
  `tests/test_native_arx_dbx_contract.py`.
- The broad P2 aggregate artifact `runs/p2_batch_check_20260618_183246.json` is **26/27**.
  It is useful evidence that most operations were wired, but it is not closeout evidence
  because `write.block.insert` failed with `native_cad_job_failed`.
- A fresh serialized stateful closeout now exists:
  `runs/p2_stateful_batch_result_20260619_135949.json` proves block create/insert/count
  cleanly on one staged DWG.
- The operation surface has expanded to 29 operations with Phase 1 `write.entity.circle`
  and `inspect.entity.count`, verified by
  `runs/phase1_entity_batch_result_20260619_140223.json`.
- P2 Batch 5 overrule/jig evidence exists in `runs/p5_batch_check_20260618_185444.json`:
  10/10 PASS across Core Console and full AutoCAD for overrule registry, overrule
  enable/disable, jig host support, and jig point probe.
- The remaining closeout requirement from this historical plan is satisfied by the
  2026-06-19 stateful batch artifact above.

Batch status:
- Batch 1 Core Database CRUD: implemented/evidenced in the 26/27 aggregate run.
- Batch 2 Blocks, Layouts, Xrefs: implementation exists, and stateful block evidence is now
  clean in `runs/p2_stateful_batch_result_20260619_135949.json`.
- Batch 3 Host-Bound Capability Contracts: implemented/evidenced, including honest
  Core Console unsupported contracts for interactive jig behavior.
- Batch 4 Full AutoCAD Native Job Lane: implementation exists and is evidenced by the full
  AutoCAD side of the P2 Batch 5 artifact.
- Batch 5 Overrule Registry and Jig Probe: evidenced by `runs/p5_batch_check_20260618_185444.json`
  with 10/10 PASS.

---

### Task 1: Batch 1 Core Database CRUD

**Files:**
- Modify: `schemas/cad_job.schema.json`
- Modify: `tools/autocad-router.ps1`
- Modify: `src/Ariadne.AcadNative/AriadneNativeJob.cpp`
- Modify: `tests/test_cad_job_control_plane.py`
- Modify: `tests/test_native_arx_dbx_contract.py`
- Create: `test_native/job_layer_create.json`
- Create: `test_native/job_line_create.json`
- Create: `test_native/job_xrecord_set.json`
- Create: `test_native/job_xrecord_get.json`
- Create: `test_native/job_xdata_set.json`
- Create: `test_native/job_xdata_get.json`

- [ ] **Step 1: Write failing tests**

Add contract tests asserting the schema, router allowlist, and native C++ dispatcher expose these operations:

```text
write.layer.create
write.entity.line
write.xrecord.set
inspect.xrecord.get
write.xdata.set
inspect.xdata.get
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_cad_job_control_plane.py tests/test_native_arx_dbx_contract.py -q`
Expected: FAIL because inspect/xdata operations are missing from schema/router/native code.

- [ ] **Step 3: Implement minimal native support**

Add C++ helpers for layer creation, line append, NOD xrecord set/get, and xdata set/get using simple string values.

- [ ] **Step 4: Verify GREEN**

Run: `tools/build_native_acad.ps1`, then targeted pytest, then Core Console smoke for each write/read pair.

### Task 2: Batch 2 Blocks, Layouts, Xrefs

**Files:**
- Modify the same schema/router/native files and tests.
- Create fixtures for:

```text
write.block.simple_create
write.block.insert
inspect.block.count
write.layout.create
inspect.layout.list
inspect.xref.list
```

- [ ] **Step 1:** Add failing schema/router/native contract tests.
- [ ] **Step 2:** Implement simple block definition + insert, layout create/list, and xref list inspection.
- [ ] **Step 3:** Build and smoke with staged DWGs.

### Task 3: Batch 3 Host-Bound Capability Contracts

**Files:**
- Modify schema/router/native tests and native dispatcher.
- Create fixtures for:

```text
inspect.runtime.capabilities
inspect.reactor.registry
inspect.overrule.registry
inspect.jig.host_support
```

- [ ] **Step 1:** Add tests that require honest capability results for Core Console vs full AutoCAD host.
- [ ] **Step 2:** Implement result contracts that mark unsupported interactive surfaces as `supported:false` in Core Console, while preserving operation-level PASS when the contract is truthfully reported.
- [ ] **Step 3:** Build, run pytest, run router status, and smoke the capability operations.

### Task 4: Batch 4 Full AutoCAD Native Job Lane

**Files:**
- Modify: `tools/autocad-router.ps1`
- Modify: `src/Ariadne.AcadNative/AriadneNativeJob.cpp`
- Modify: `tests/test_native_arx_dbx_contract.py`
- Create: `test_native/job_fullacad_runtime_capabilities.json`

- [ ] **Step 1:** Add failing tests requiring `Invoke-FullAutoCadCadJob`, AutoCAD `setenv`, native `acedGetEnv` fallback, and `ARIADNE_CAD_JOB_HOST_MODE`.
- [ ] **Step 2:** Implement native command fallback from process environment to AutoCAD profile environment via `acedGetEnv`.
- [ ] **Step 3:** Implement router full AutoCAD job runner that copies the job file, writes a `.scr`, sets AutoCAD env values, loads DBX/ARX, invokes `ARIADNE_NATIVE_JOB`, optionally `QSAVE`s, polls for the result JSON, and reports async/poll outcome.
- [ ] **Step 4:** Build, run pytest, and smoke `inspect.runtime.capabilities` through an active AutoCAD document.

### Task 5: Batch 5 Overrule Registry and Jig Probe

**Files:**
- Modify: `schemas/cad_job.schema.json`
- Modify: `tools/autocad-router.ps1`
- Modify: `src/Ariadne.AcadNative/AriadneNativeJob.cpp`
- Modify: `tests/test_cad_job_control_plane.py`
- Modify: `tests/test_native_arx_dbx_contract.py`
- Create: `test_native/job_overrule_enable.json`
- Create: `test_native/job_overrule_disable.json`
- Create: `test_native/job_jig_point_probe.json`

- [ ] **Step 1:** Add failing schema/router/native contract tests for:

```text
live.overrule.enable
live.overrule.disable
live.jig.point_probe
```

- [ ] **Step 2:** Implement a minimal `AcDbObjectOverrule` registration against the Ariadne custom probe class, with honest registry inspection and unload cleanup.
- [ ] **Step 3:** Implement a full AutoCAD `AcEdJig::drag()` point probe that can be smoke-tested unattended by feeding a scripted point from the router job.
- [ ] **Step 4:** Build, run pytest, run router status, and smoke enable/inspect/disable plus jig point probe through an active AutoCAD document.
