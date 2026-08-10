#requires -Version 5.1
<#
  Run the official MCP SDK stdio contract under the system v1 SDK and an
  isolated v2 target.  This never upgrades the system Python installation.

  First use (creates a disposable target under %TEMP%):
    .\tools\test_cadagent_mcp_sdk_matrix.ps1 -InstallV2
#>
[CmdletBinding()]
param(
  [string]$PythonExe = '',
  [string]$V2Target = '',
  [switch]$InstallV2
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Invoke-CheckedNative {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][string]$Label,
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(Mandatory = $true)][string[]]$ArgumentList
  )

  # A nonzero native exit is not a PowerShell terminating error by default.
  # Clear stale state, invoke once, and make every failure stop this matrix.
  $global:LASTEXITCODE = 0
  & $FilePath @ArgumentList
  $commandSucceeded = $?
  $exitCode = $LASTEXITCODE
  if (-not $commandSucceeded -or $exitCode -ne 0) {
    throw "$Label failed with exit code $exitCode."
  }
}

if (-not $PythonExe) {
  $candidate = Get-Command py -ErrorAction SilentlyContinue
  if ($candidate) { $PythonExe = 'py' }
  else {
    $candidate = Get-Command python -ErrorAction SilentlyContinue
    if ($candidate) { $PythonExe = $candidate.Source }
  }
}
if (-not $PythonExe) { throw 'Python 3.10+ is required.' }
if (-not $V2Target) { $V2Target = Join-Path $env:TEMP 'cadagent-mcp-sdk-v2' }

$testPath = Join-Path $Root 'tests\integration\test_cadagent_mcp_sdk_stdio.py'
$v1HadPythonPath = Test-Path Env:PYTHONPATH
$v1PreviousPythonPath = $env:PYTHONPATH
$v1HadV2Target = Test-Path Env:CADAGENT_MCP_V2_TARGET
$v1PreviousV2Target = $env:CADAGENT_MCP_V2_TARGET
try {
  # The default interpreter is the verified v1 lane.  Do not let a caller's
  # v2 compatibility target change what pytest imports before this proof runs.
  Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
  Remove-Item Env:CADAGENT_MCP_V2_TARGET -ErrorAction SilentlyContinue
  $verifyV1Code = @'
import importlib.metadata
import sys
from pathlib import Path

import mcp

target = Path(sys.argv[1]).resolve()
version = importlib.metadata.version('mcp')
module_path = Path(mcp.__file__).resolve()
if version != '1.27.1':
    raise SystemExit('expected mcp==1.27.1, got %s from %s' % (version, module_path))
if module_path.is_relative_to(target):
    raise SystemExit('v1 mcp was imported from the isolated v2 target: %s' % module_path)
print('MCP_V1_IMPORT_OK version=%s path=%s' % (version, module_path))
'@
  Write-Host "[v1] $PythonExe" -ForegroundColor Cyan
  Invoke-CheckedNative -Label 'v1 MCP SDK import verification' -FilePath $PythonExe `
    -ArgumentList @('-c', $verifyV1Code, $V2Target)
  Invoke-CheckedNative -Label 'v1 MCP SDK integration tests' -FilePath $PythonExe `
    -ArgumentList @('-m', 'pytest', '-q', '-p', 'no:cacheprovider', $testPath)
} finally {
  if ($v1HadPythonPath) { $env:PYTHONPATH = $v1PreviousPythonPath }
  else { Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue }
  if ($v1HadV2Target) { $env:CADAGENT_MCP_V2_TARGET = $v1PreviousV2Target }
  else { Remove-Item Env:CADAGENT_MCP_V2_TARGET -ErrorAction SilentlyContinue }
}

if ($InstallV2) {
  Write-Host "[v2 install] isolated target: $V2Target" -ForegroundColor Cyan
  Invoke-CheckedNative -Label 'isolated MCP SDK v2 install' -FilePath $PythonExe `
    -ArgumentList @('-m', 'pip', 'install', '--disable-pip-version-check', '--target',
                    $V2Target, '-r', (Join-Path $Root 'requirements-mcp-sdk-v2.txt'))
}

$v2HadPythonPath = Test-Path Env:PYTHONPATH
$v2PreviousPythonPath = $env:PYTHONPATH
$v2HadV2Target = Test-Path Env:CADAGENT_MCP_V2_TARGET
$v2PreviousV2Target = $env:CADAGENT_MCP_V2_TARGET
try {
  $env:PYTHONPATH = $V2Target
  $env:CADAGENT_MCP_V2_TARGET = $V2Target
  $verifyV2Code = @'
import importlib.metadata
import os
from pathlib import Path

import mcp

target = Path(os.environ['CADAGENT_MCP_V2_TARGET']).resolve()
version = importlib.metadata.version('mcp')
module_path = Path(mcp.__file__).resolve()
if version != '2.0.0':
    raise SystemExit('expected mcp==2.0.0, got %s from %s' % (version, module_path))
if not module_path.is_relative_to(target):
    raise SystemExit('mcp was imported outside the isolated target: %s' % module_path)
print('MCP_V2_IMPORT_OK version=%s path=%s' % (version, module_path))
'@
  Invoke-CheckedNative -Label 'isolated MCP SDK v2 import verification' -FilePath $PythonExe `
    -ArgumentList @('-c', $verifyV2Code)
  Write-Host "[v2] $PythonExe with PYTHONPATH=$V2Target" -ForegroundColor Cyan
  Invoke-CheckedNative -Label 'v2 MCP SDK integration tests' -FilePath $PythonExe `
    -ArgumentList @('-m', 'pytest', '-q', '-p', 'no:cacheprovider', $testPath)
} finally {
  if ($v2HadPythonPath) { $env:PYTHONPATH = $v2PreviousPythonPath }
  else { Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue }
  if ($v2HadV2Target) { $env:CADAGENT_MCP_V2_TARGET = $v2PreviousV2Target }
  else { Remove-Item Env:CADAGENT_MCP_V2_TARGET -ErrorAction SilentlyContinue }
}
