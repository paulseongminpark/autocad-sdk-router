#requires -Version 5.1
<#
  CAD OS - teammate installer (team-private, AutoCAD on Windows).

  Idempotent. Prepares a freshly-cloned repo so an AI agent (Claude / Codex / Pi /
  Hermes / Gemini) can drive the AutoCAD SDK through the cadagent MCP server.

  What it does (no surprises):
    1. Detect AutoCAD (accoreconsole.exe) and its version.
    2. Verify the committed prebuilt native modules for that version exist.
    3. Detect Python; pip-install the core dep (jsonschema). -Full adds the heavy
       non-AutoCAD geometry routes.
    4. Run a router status smoke.
    5. PRINT the MCP registration block to paste into your agent config.

  Usage:
    powershell -ExecutionPolicy Bypass -File .\install.ps1
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -Full        # + geometry routes
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -PythonExe C:\path\to\python.exe
#>
[CmdletBinding()]
param(
  [switch]$Full,
  [string]$PythonExe = ''
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Say  ($m) { Write-Host $m -ForegroundColor Cyan }
function Ok   ($m) { Write-Host "  + $m" -ForegroundColor Green }
function Warn ($m) { Write-Host "  ! $m" -ForegroundColor Yellow }

Say "CAD OS installer"
Write-Host "  repo: $Root"

# 1) AutoCAD --------------------------------------------------------------------
$acad = $null
foreach ($base in @($env:ProgramW6432, $env:ProgramFiles, 'C:\Program Files')) {
  if (-not $base) { continue }
  $adsk = Join-Path $base 'Autodesk'
  if (-not (Test-Path -LiteralPath $adsk)) { continue }
  $hit = Get-ChildItem -LiteralPath $adsk -Directory -Filter 'AutoCAD 20*' -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending |
    ForEach-Object { Join-Path $_.FullName 'accoreconsole.exe' } |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1
  if ($hit) { $acad = $hit; break }
}
if (-not $acad) { throw "AutoCAD (accoreconsole.exe) not found under <ProgramFiles>\Autodesk. Install AutoCAD first." }
$acadVer = 'unknown'
if ($acad -match 'AutoCAD\s+(\d{4})') { $acadVer = $Matches[1] }
Ok "AutoCAD $acadVer  ($acad)"

# 2) prebuilt native modules for this version -----------------------------------
$prebuilt = Join-Path $Root "prebuilt\$acadVer"
$need = @('Ariadne.AcadNative.crx', 'Ariadne.AcadNative.arx', 'Ariadne.AcadNativeDbx.dbx')
if (Test-Path -LiteralPath $prebuilt) {
  $missing = @($need | Where-Object { -not (Test-Path -LiteralPath (Join-Path $prebuilt $_)) })
  if ($missing.Count -gt 0) {
    Warn "prebuilt\$acadVer is missing: $($missing -join ', ')"
  } else {
    Ok "native modules present: prebuilt\$acadVer  (crx + arx + dbx)"
  }
} else {
  Warn "No prebuilt\$acadVer for your AutoCAD version."
  Warn "Ask the maintainer for a $acadVer build, OR build locally with"
  Warn "  tools\build_native_acad.ps1   (needs Visual Studio + ObjectARX $acadVer SDK + .NET SDK)"
}

# 3) Python + deps --------------------------------------------------------------
if (-not $PythonExe) {
  $c = Get-Command py -ErrorAction SilentlyContinue
  if ($c) { $PythonExe = 'py' }
  else {
    $c = Get-Command python -ErrorAction SilentlyContinue
    if ($c) { $PythonExe = $c.Source }
  }
}
if (-not $PythonExe) { throw "Python not found. Install Python 3.10+ (3.12 recommended) and re-run." }
$pyv = (& $PythonExe -c "import sys;print('%d.%d'%sys.version_info[:2])").Trim()
Ok "Python $pyv  ($PythonExe)"

Say "Installing core dependency (jsonschema)..."
& $PythonExe -m pip install --quiet --disable-pip-version-check -r (Join-Path $Root 'requirements.txt')
Ok "core deps installed"
if ($Full) {
  Say "Installing OPTIONAL geometry-route deps (heavy; non-AutoCAD routes)..."
  & $PythonExe -m pip install --disable-pip-version-check -r (Join-Path $Root 'requirements-full.txt')
  Ok "full deps installed"
}

# 4) router status smoke --------------------------------------------------------
Say "Router status smoke (live tool probe)..."
& (Join-Path $Root 'tools\autocad-router.ps1') -Action status | Out-Null
Ok "router status ran (see reports\autocad_router_status_latest.json)"

# 5) MCP registration block to paste -------------------------------------------
# Resolve the CONCRETE interpreter (sys.executable) so the MCP command is
# deterministic even when Python was found via the 'py' launcher.
$pyAbs = ''
try { $pyAbs = (& $PythonExe -c "import sys;print(sys.executable)").Trim() } catch { $pyAbs = '' }
if (-not $pyAbs) {
  $cmd = Get-Command $PythonExe -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source) { $pyAbs = $cmd.Source } else { $pyAbs = $PythonExe }
}
$mcpPy = Join-Path $Root 'tools\cadagent_mcp.py'

$snippet = [ordered]@{
  mcpServers = [ordered]@{
    cadagent = [ordered]@{
      command = $pyAbs
      args    = @($mcpPy, '--serve')
      env     = [ordered]@{ PYTHONUTF8 = '1'; PYTHONIOENCODING = 'utf-8' }
    }
  }
}
Write-Host ""
Write-Host "=== MCP registration - paste into your agent config ===" -ForegroundColor Magenta
Write-Host ($snippet | ConvertTo-Json -Depth 6)
Write-Host ""
Write-Host "Claude Code : .mcp.json (project) or your user config - exactly the JSON above." -ForegroundColor Gray
Write-Host "Codex       : ~/.codex/config.toml  [mcp_servers.cadagent]  (command/args/env)" -ForegroundColor Gray
Write-Host "Pi          : ~/.pi/agent/mcp.json   mcpServers.cadagent" -ForegroundColor Gray
Write-Host "Hermes      : ~/.hermes/config.yaml  mcp_servers.cadagent  (+ platform_toolsets)" -ForegroundColor Gray
Write-Host "Gemini      : ~/.gemini/settings.json mcpServers.cadagent  (read-only: includeTools whitelist)" -ForegroundColor Gray
Write-Host "Full per-agent snippets + read-only whitelist: see INSTALL.md" -ForegroundColor Gray
Write-Host ""
Write-Host "Done. Start a NEW agent session, then verify the tools load (e.g. 'claude mcp list')." -ForegroundColor Green
