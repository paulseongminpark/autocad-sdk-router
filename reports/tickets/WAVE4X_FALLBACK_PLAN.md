# WAVE4X_FALLBACK_PLAN

## Scope
- worktree: `D:/dev/99_tools/autocad-sdk-router_w4x_fallback`
- branch: `cados/w4x-fallback-com-ole`
- claim file: `reports/tickets/WAVE4X_PANE4_FALLBACK_COM_OLE_CLAIMS.json`

## Closure plan

### Implement
- `automate.com.get_app` → safe COM app metadata only
- `automate.com.get_document` → safe active-document metadata only
- `automate.com.get_for_command` → command-state metadata only
- `automate.com.get_winapp` → bounded window/process metadata only
- `automate.com.wrapper_for_object` → handle→object metadata only, no COM wrapper escape
- `module.load.lisp` → router-authored AutoLISP `safe_status` adapter only, plus managed `.NET` adapter map

### Keep hard-blocked
- `automate.com.send_command`
- `command.invoke.coroutine`
- `command.invoke.sync`
- `command.invoke.sync.resbuf`
- `command.menu.invoke`
- `command.queue.post`
- `embed.ole.frame`
- `module.lifecycle.on_ole_unload`

## Files
- `tools/fallback_safe_surface.ps1`
- `tools/autocad-router.ps1`
- `docs/FALLBACK_POLICY.md`
- `config/operations.v2.json`
- `tests/unit/test_m08o_fallback.py`
- `tests/unit/test_wave3_remaining_registry_closure.py`
- `tests/unit/test_wave4x_fallback_surface.py`
- `reports/tickets/WAVE4X_FALLBACK.*`

## Validation
- `python -m pytest tests -q`
- `python tools/operation_coverage_matrix.py`
- `python tools/cadctl_cli.py registry coverage`
- `python -m json.tool reports/operation_coverage_latest.json`
