# WAVE3_PANE9_LIVE_EDITOR — Live ARX / Document Lifecycle Handlers

**Status: PASS** · branch `cados/wave3-pane9-live-editor-ui` · commit `d2463c7` · base `main`

This ticket implements Wave 3 Pane 9 operations for the live ARX host, command stack, and document lifecycle control paths in `src/Ariadne.AcadNative/families/m08n_handlers.inc`.

## Both gates GREEN

- **Build (the gate):** `tools/build_native_acad.ps1` → **EXIT 0**. `.dbx`, `.crx`, and `.arx` compiled + linked successfully against the ObjectARX 2027 SDK.
- **Tests:** `python -m pytest tests -v` → **464 passed, 20 skipped, 0 failed** (skips are pre-existing AutoCAD host-dependent tests). Verified that `tests/unit/test_m08n_handlers.py` has been updated to include the new runtime commands and active document write_original operations, all passing cleanly.

## Implemented ops (6)

All operate read-only or interact directly with the active document/command stack on the live editor:

| op_id | ObjectARX API / Details | Result Structure |
|---|---|---|
| `module.app.accessor` | `GetModuleHandleW` for `.crx` / `.arx` | `{hinstance, module_name, app_ptr:0}` |
| `module.command.stack_handle` | `acedRegCmds` (AcEdCommandStack) | `{stack_ptr, stack_present, group_count:0}` |
| `doc.current` | `acDocManager->curDocument()` / `mdiActiveDocument()` | `{document_ptr, doc_present, file_name, host_mode}` |
| `doc.lock` | `acDocManager->lockDocument` / `unlockDocument` | `{document_ptr, execute_requested, lock_status, unlock_status, locked_and_unlocked}` |
| `doc.new` | `acDocManager->appContextNewDocument` | `{execute_requested, template_path, create_status, host_mode}` |
| `doc.syncopen` | `acedSyncFileOpen` | `{execute_requested, dwg_path, acedSyncFileOpen_status, host_mode}` |

## Catalog reopen consistency fix

During verification, we identified a catalog field inconsistency issue: flipping operations from `catalogued` to `implemented` left the derived `implementation_strategy` and `evidence_required` fields stale (holding the legacy `catalogued` strategy and unit test evidence values).
We fixed this by modifying the reconcile script (`tools/reconcile_native_registry.py`) to automatically call `ocm.reopen_registry(doc)` on apply, ensuring that all operation fields are kept deterministic and synchronized.

## Process notes

- Developed and tested inside the isolated git worktree `D:\dev\99_tools\autocad-sdk-router_wave3_pane9_live_editor`.
- No original DWG files were mutated.
- Standard UTF-8 encoding (with BOM) for `config/operations.v2.json` and json outputs is fully preserved.
