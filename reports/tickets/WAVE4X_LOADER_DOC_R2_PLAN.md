# WAVE4X Loader Doc R2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reopen `doc.sendstring` and module entrypoint/lifecycle operations, implement safe lifecycle evidence handlers where possible, and keep only unsafe raw command/session mutation hard-blocked.

**Architecture:** Extend the existing `m08n` runtime command family with non-mutating module lifecycle evidence/status handlers. These handlers report compile/load lifecycle registration evidence and explicitly do not synthesize host loader messages. Keep `doc.sendstring` blocked because arbitrary `sendStringToExecute` is a raw command surface.

**Tech Stack:** Python 3.12, pytest source-contract tests, ObjectARX native source, JSON operation registry, PowerShell packaging.

---

### Task 1: Add RED tests for R2 target closure

**Files:**
- Create: `tests/unit/test_module_lifecycle_r2.py`
- Create: `tests/unit/test_doc_sendstring_safety.py`

- [ ] **Step 1: Write lifecycle target test**

```python
def test_lifecycle_ops_are_implemented_status_handlers():
    for op_id in MODULE_LIFECYCLE_TARGETS:
        op = registry()[op_id]
        assert op["status"] == "implemented"
        assert op["handler"]["dispatcher_symbol"] == "m08nDispatch"
        assert op["policy"]["runtime_behavior"] == "lifecycle_evidence_status_only"
```

- [ ] **Step 2: Write sendstring safety test**

```python
def test_doc_sendstring_remains_blocked_and_non_agent_exposed():
    op = registry()["doc.sendstring"]
    assert op["status"] == "blocked"
    assert op["policy"]["agent_exposed"] is False
    assert "SAFETY_FORBIDDEN" in op["blocked_reason"]
```

- [ ] **Step 3: Verify RED**

Run: `python -m pytest tests/unit/test_module_lifecycle_r2.py tests/unit/test_doc_sendstring_safety.py -q`

Expected: FAIL before native source/registry/report updates.

### Task 2: Implement m08n lifecycle evidence handlers

**Files:**
- Modify: `src/Ariadne.AcadNative/families/m08n_handlers.inc`
- Modify: `tests/unit/test_m08n_handlers.py`

- [ ] **Step 1: Admit seven lifecycle/entrypoint ops**

Add these to `_RUNTIME` in tests and `m08nHasOp` in source:

```text
module.entrypoint.define
module.entrypoint.dispatch
module.lifecycle.init
module.lifecycle.on_load_dwg
module.lifecycle.on_unload_dwg
module.lifecycle.other
module.lifecycle.unload
```

- [ ] **Step 2: Add non-mutating dispatch branch**

Return JSON evidence with:

```json
{
  "mode": "lifecycle_evidence_status_only",
  "actual_lifecycle_callback_invoked": false,
  "synthetic_loader_message_dispatched": false,
  "raw_command_agent_surface": false,
  "writes_dwg": false
}
```

### Task 3: Update operation registry and reports

**Files:**
- Modify: `config/operations.v2.json`
- Create: `reports/tickets/WAVE4X_LOADER_DOC_R2.md`
- Create: `reports/tickets/WAVE4X_LOADER_DOC_R2.json`
- Create: `reports/tickets/WAVE4X_LOADER_DOC_R2_OPS.json`
- Create: `packets/tickets/WAVE4X_LOADER_DOC_R2.md`

- [ ] **Step 1: Mark lifecycle ops implemented**

Set handler to `m08nDispatch`, `router_lane=ARIADNE_NATIVE_JOB`, `agent_exposed=true`, `risk_class=read_safe`, and add R2 evidence refs.

- [ ] **Step 2: Strengthen doc.sendstring hard block**

Keep status `blocked`, add `agent_exposed=false`, `risk_class=raw_command`, and R2 evidence refs.

### Task 4: Validate, build if native source changed, and package

**Files:**
- Generated: `reports/operation_coverage_latest.json`
- Create if build runs: `reports/tickets/WAVE4X_LOADER_DOC_R2_native_build.json`
- Create: `handoff/pr/WAVE4X_LOADER_DOC_R2.patch`
- Create: `handoff/tickets/WAVE4X_LOADER_DOC_R2.zip`

- [ ] **Step 1: Run validation**

```powershell
python -m pytest tests -q
python tools\cadctl_cli.py registry coverage
python tools\reconcile_native_registry.py
python -m json.tool reports\operation_coverage_latest.json
```

- [ ] **Step 2: If native source changed, build isolated output only**

```powershell
tools\build_native_acad.ps1
```

- [ ] **Step 3: Package and commit**

```powershell
git diff --binary > handoff\pr\WAVE4X_LOADER_DOC_R2.patch
Compress-Archive -Force -Path reports\tickets\WAVE4X_LOADER_DOC_R2*,packets\tickets\WAVE4X_LOADER_DOC_R2.md,handoff\pr\WAVE4X_LOADER_DOC_R2.patch -DestinationPath handoff\tickets\WAVE4X_LOADER_DOC_R2.zip
git commit -m "cados: implement wave4x loader doc r2 lifecycle evidence"
```
