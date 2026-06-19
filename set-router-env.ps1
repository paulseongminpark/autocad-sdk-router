# set-router-env.ps1 -- session-local repoint of ARIADNE_AUTOCAD_ROUTER_* to the
# LOCAL router at D:\dev\99_tools\autocad-sdk-router.
#
# This is SAFE: it only sets Process-scope env vars for the current shell. Tracked
# Ariadne wrappers already export these values; dot-source this only for direct
# interactive/ad-hoc shells:
#
#     . D:\dev\99_tools\autocad-sdk-router\set-router-env.ps1
#
# After dot-sourcing, $env:ARIADNE_AUTOCAD_ROUTER_PATH points at the local router.

$LocalRouterRoot = 'D:\dev\99_tools\autocad-sdk-router'
$LocalLibreDwgBin = 'D:\dev\99_tools\libredwg\bin'

$env:ARIADNE_AUTOCAD_ROUTER_ROOT             = $LocalRouterRoot
$env:ARIADNE_AUTOCAD_ROUTER_PATH             = Join-Path $LocalRouterRoot 'tools\autocad-router.ps1'
$env:ARIADNE_AUTOCAD_ROUTER_CAPABILITIES_PATH = Join-Path $LocalRouterRoot 'config\autocad_router_capabilities.json'
$env:ARIADNE_AUTOCAD_ROUTER_STATUS_PATH      = Join-Path $LocalRouterRoot 'reports\autocad_router_status_latest.json'
$env:ARIADNE_AUTOCAD_ROUTER_CONTRACT_PATH    = Join-Path $LocalRouterRoot 'reports\AUTO_CAD_ROUTER_AGENT_CONTRACT.md'
$env:ARIADNE_AUTOCAD_ROUTER_POLICY           = 'call_router_first_originals_read_only_ascii_staging_export_only'
$env:ARIADNE_LIBREDWG_BIN_DIR                = $LocalLibreDwgBin
$env:ARIADNE_CAD_ROUTER_ENFORCEMENT          = 'required'
$env:ARIADNE_CAD_ROUTER_PROMPT_PATH          = 'D:\dev\_ariadne\context\live\CAD_ROUTER_ENFORCEMENT.md'

Write-Host "[set-router-env] ARIADNE_AUTOCAD_ROUTER_* -> $LocalRouterRoot (Process scope)"
Write-Host "  PATH   = $env:ARIADNE_AUTOCAD_ROUTER_PATH"
Write-Host "  STATUS = $env:ARIADNE_AUTOCAD_ROUTER_STATUS_PATH"
Write-Host "  LIBREDWG_BIN = $env:ARIADNE_LIBREDWG_BIN_DIR"
