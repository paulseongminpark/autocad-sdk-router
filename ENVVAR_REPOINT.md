# ARIADNE_AUTOCAD_ROUTER_* repoint -- superseded

Status: APPLIED on 2026-06-16.

The Ariadne tracked entrypoints now export the local router directly from:

`D:\dev\_ariadne\bin\ariadne_entrypoint_common.ps1`

Current values:

```powershell
$Script:AutoCadRouterRoot     = "D:\dev\99_tools\autocad-sdk-router"
$Script:AutoCadRouterPath     = Join-Path $Script:AutoCadRouterRoot "tools\autocad-router.ps1"
$Script:AutoCadRouterCaps     = Join-Path $Script:AutoCadRouterRoot "config\autocad_router_capabilities.json"
$Script:AutoCadRouterStatus   = Join-Path $Script:AutoCadRouterRoot "reports\autocad_router_status_latest.json"
$Script:AutoCadRouterContract = Join-Path $Script:AutoCadRouterRoot "reports\AUTO_CAD_ROUTER_AGENT_CONTRACT.md"
$Script:LibreDwgBin           = "D:\dev\99_tools\libredwg\bin"
```

The wrapper also exports:

- `ARIADNE_LIBREDWG_BIN_DIR`
- `ARIADNE_CAD_ROUTER_ENFORCEMENT=required`
- `ARIADNE_CAD_ROUTER_PROMPT_PATH`
- `ARIADNE_CAD_ROUTER_GEMINI_POLICY`

Verification:

```powershell
& 'D:\dev\99_tools\autocad-sdk-router\tools\autocad-router.ps1' -Action status
# -> ALL_AVAILABLE, route_count=11, available_count=11
```
