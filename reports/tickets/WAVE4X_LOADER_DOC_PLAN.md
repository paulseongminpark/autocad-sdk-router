# WAVE4X Loader/Doc/Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reopen Pane 2 loader, document, module, and command-stack blockers and implement every feasible safe operation as a typed native status/introspection handler while keeping raw command/load execution out of the agent surface.

**Architecture:** Extend the existing M08N native ObjectARX family seam because it already owns command stack, module app accessor, and document current/lock/new/syncopen handlers. Implement only bounded read/status or bounded ARIADNE-owned cleanup operations; do not expose arbitrary raw command strings, arbitrary module load/unload, registry writes, or host-owned lifecycle message dispatch.

**Tech Stack:** Python registry/tests, ObjectARX C++ family include file, deterministic operation coverage tools, zip/patch handoff artifacts.

---

## Files

- Create: `reports/tickets/WAVE4X_LOADER_DOC_PLAN.md`
- Create: `tests/unit/test_m08_loader_doc.py`
- Create: `tests/unit/test_m08_doc_lifecycle.py`
- Modify: `src/Ariadne.AcadNative/families/m08n_handlers.inc`
- Modify: `tests/unit/test_m08n_handlers.py`
- Modify: `tests/unit/test_m08o_fallback.py`
- Modify: `tests/unit/test_wave3_remaining_registry_closure.py`
- Modify: `config/operations.v2.json`
- Create: `docs/LOADER_DOC_COMMAND_STATUS.md`
- Create: `reports/tickets/WAVE4X_LOADER_DOC.md`
- Create: `reports/tickets/WAVE4X_LOADER_DOC.json`
- Create: `reports/tickets/WAVE4X_LOADER_DOC_OPS.json`
- Create: `packets/tickets/WAVE4X_LOADER_DOC.md`
- Create: `handoff/pr/WAVE4X_LOADER_DOC.patch`
- Create: `handoff/tickets/WAVE4X_LOADER_DOC.zip`

## Classification after feasibility review

- Implemented as safe typed handlers: `module.command.lookup`, `module.command.remove_group`, `module.load`, `module.load.acad_rx`, `module.load.by_app`, `module.load.demand_register`, `module.unload`.
- Still hard-blocked: `doc.sendstring`, `module.entrypoint.define`, `module.entrypoint.dispatch`, `module.lifecycle.init`, `module.lifecycle.on_load_dwg`, `module.lifecycle.on_unload_dwg`, `module.lifecycle.other`, `module.lifecycle.unload`.

## Tasks

### Task 1: Add failing tests for safe loader/command reversals

**Files:**
- Create: `tests/unit/test_m08_loader_doc.py`

- [ ] **Step 1: Write source/registry tests**

```python
SAFE_IMPLEMENTED = {
    "module.command.lookup",
    "module.command.remove_group",
    "module.load",
    "module.load.acad_rx",
    "module.load.by_app",
    "module.load.demand_register",
    "module.unload",
}
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/unit/test_m08_loader_doc.py -q`
Expected: FAIL because the seven operations are not in `m08nHasOp` and remain `blocked` in `operations.v2.json`.

### Task 2: Add failing tests for lifecycle blockers and doc safety

**Files:**
- Create: `tests/unit/test_m08_doc_lifecycle.py`

- [ ] **Step 1: Write tests proving unsafe surfaces remain blocked with allowed blocker codes**

```python
STILL_BLOCKED = {
    "doc.sendstring": "SAFETY_FORBIDDEN",
    "module.entrypoint.define": "SDK_NOT_EXPOSED",
    "module.entrypoint.dispatch": "HOST_UNAVAILABLE",
    "module.lifecycle.init": "HOST_UNAVAILABLE",
    "module.lifecycle.on_load_dwg": "HOST_UNAVAILABLE",
    "module.lifecycle.on_unload_dwg": "HOST_UNAVAILABLE",
    "module.lifecycle.other": "HOST_UNAVAILABLE",
    "module.lifecycle.unload": "HOST_UNAVAILABLE",
}
```

- [ ] **Step 2: Verify RED/PASS split**

Run: `python -m pytest tests/unit/test_m08_doc_lifecycle.py -q`
Expected: PASS for already-hard-blocked records, or FAIL only where Wave4X evidence references are absent.

### Task 3: Implement M08N native handlers

**Files:**
- Modify: `src/Ariadne.AcadNative/families/m08n_handlers.inc`
- Modify: `tests/unit/test_m08n_handlers.py`

- [ ] **Step 1: Add seven safe op IDs to `m08nHasOp`**

Add the safe loader/doc command IDs to the runtime command lifecycle group.

- [ ] **Step 2: Add typed handlers**

Implement:
- `module.command.lookup`: lookup only ARIADNE-owned command names; return stack availability and lookup result, never execute.
- `module.command.remove_group`: remove only `ARIADNE_W4X_LOADER_DOC` scratch group after registering a bounded no-op command.
- `module.load`: report current module handle/linker presence; never load external modules.
- `module.load.acad_rx`: read-only acad.rx path/status detection.
- `module.load.by_app`: app-name validation/status contract; no registry access mutation.
- `module.load.demand_register`: demand-load registration plan validation only; no registry writes.
- `module.unload`: report unload safety status for current module; no unload call.

- [ ] **Step 3: Preserve safety guards**

Run: `python -m pytest tests/unit/test_m08n_handlers.py tests/unit/test_m08_loader_doc.py -q`
Expected: PASS after implementation.

### Task 4: Update registry and legacy guard tests

**Files:**
- Modify: `config/operations.v2.json`
- Modify: `tests/unit/test_m08o_fallback.py`
- Modify: `tests/unit/test_wave3_remaining_registry_closure.py`

- [ ] **Step 1: Promote seven safe ops to `implemented`**

Set `handler.dispatcher_symbol` to `m08nDispatch`, `implementation_strategy` to `native_typed_safe_status_handler`, and add Wave4X test/evidence references.

- [ ] **Step 2: Keep eight unsafe ops blocked**

Add Wave4X evidence references without changing their final status.

- [ ] **Step 3: Update tests that previously pinned these seven as blocked**

Remove implemented ops from the Wave3 blocked set and from M08O raw-command blocked set.

### Task 5: Create reports and handoff artifacts

**Files:**
- Create: `docs/LOADER_DOC_COMMAND_STATUS.md`
- Create: `reports/tickets/WAVE4X_LOADER_DOC.md`
- Create: `reports/tickets/WAVE4X_LOADER_DOC.json`
- Create: `reports/tickets/WAVE4X_LOADER_DOC_OPS.json`
- Create: `packets/tickets/WAVE4X_LOADER_DOC.md`
- Create: `handoff/pr/WAVE4X_LOADER_DOC.patch`
- Create: `handoff/tickets/WAVE4X_LOADER_DOC.zip`

- [ ] **Step 1: Generate deterministic reports**

Include implemented, hard-blocked, deprecated, attended-required, tests, blockers, and next steps.

- [ ] **Step 2: Validate**

Run:

```powershell
python -m pytest tests -q
python tools\cadctl_cli.py registry coverage
python tools\reconcile_native_registry.py
python -m json.tool reports\operation_coverage_latest.json
```

- [ ] **Step 3: Commit and package**

Run:

```powershell
git add src tests config docs reports packets handoff
git commit -m "feat: implement Wave4X loader doc command claims"
git diff main..HEAD --binary > handoff\pr\WAVE4X_LOADER_DOC.patch
Compress-Archive -Path reports\tickets\WAVE4X_LOADER_DOC.md,reports\tickets\WAVE4X_LOADER_DOC.json,reports\tickets\WAVE4X_LOADER_DOC_OPS.json,packets\tickets\WAVE4X_LOADER_DOC.md,handoff\pr\WAVE4X_LOADER_DOC.patch -DestinationPath handoff\tickets\WAVE4X_LOADER_DOC.zip -Force
```
