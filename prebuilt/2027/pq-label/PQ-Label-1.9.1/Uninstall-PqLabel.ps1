[CmdletBinding()]
param(
    [string]$InstallRoot,
    [string]$RecoveryRoot
)

$ErrorActionPreference = 'Stop'
$usesDefaultInstallRoot = [string]::IsNullOrWhiteSpace($InstallRoot)
$applicationPluginsPath = if ($usesDefaultInstallRoot) {
    Join-Path $env:APPDATA 'Autodesk\ApplicationPlugins'
} else {
    [IO.Path]::GetFullPath($InstallRoot)
}
$targetBundlePath = Join-Path $applicationPluginsPath 'PqLabel.bundle'
$recoveryRoot = if ([string]::IsNullOrWhiteSpace($RecoveryRoot)) {
    Join-Path $env:LOCALAPPDATA 'PQLabel\Uninstalled'
} else {
    [IO.Path]::GetFullPath($RecoveryRoot)
}

if ($usesDefaultInstallRoot -and
    (Get-Process -Name 'acad','accoreconsole' -ErrorAction SilentlyContinue)) {
    Write-Host 'ERROR: Close AutoCAD completely before uninstalling PQ Label.' -ForegroundColor Red
    exit 1
}

if (-not (Test-Path -LiteralPath $targetBundlePath)) {
    Write-Host 'PQ Label is not installed for the current Windows user.' -ForegroundColor Yellow
    exit 0
}

New-Item -ItemType Directory -Path $recoveryRoot -Force | Out-Null
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$recoveryPath = Join-Path $recoveryRoot "PqLabel.bundle-$timestamp"
Move-Item -LiteralPath $targetBundlePath -Destination $recoveryPath

Write-Host 'PQ Label was removed from AutoCAD.' -ForegroundColor Green
Write-Host "Recoverable copy: $recoveryPath"
