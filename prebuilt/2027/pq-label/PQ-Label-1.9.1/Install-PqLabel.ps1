[CmdletBinding()]
param(
    [string]$InstallRoot
)

$ErrorActionPreference = 'Stop'
$releaseVersion = '1.9.1'
$expectedDllSha256 = '9106103A8D46A37631107593B5EC7D610E6B20FDFD5904E12E5D0189B1137018'
$payloadPath = Join-Path $PSScriptRoot 'PqLabel.bundle.zip'
$usesDefaultInstallRoot = [string]::IsNullOrWhiteSpace($InstallRoot)
$applicationPluginsPath = if ($usesDefaultInstallRoot) {
    Join-Path $env:APPDATA 'Autodesk\ApplicationPlugins'
} else {
    [IO.Path]::GetFullPath($InstallRoot)
}
$targetBundlePath = Join-Path $applicationPluginsPath 'PqLabel.bundle'
$temporaryPath = Join-Path ([IO.Path]::GetTempPath()) ('PqLabel-Install-' + [guid]::NewGuid().ToString('N'))
$backupPath = $null

function Stop-WithMessage([string]$message) {
    Write-Host "ERROR: $message" -ForegroundColor Red
    exit 1
}

if ($usesDefaultInstallRoot -and
    (Get-Process -Name 'acad','accoreconsole' -ErrorAction SilentlyContinue)) {
    Stop-WithMessage 'AutoCAD or AutoCAD Core Console is running. Close it completely and run the installer again.'
}

if (-not (Test-Path -LiteralPath $payloadPath -PathType Leaf)) {
    Stop-WithMessage "Installer payload was not found: $payloadPath"
}

try {
    New-Item -ItemType Directory -Path $temporaryPath -Force | Out-Null
    Expand-Archive -LiteralPath $payloadPath -DestinationPath $temporaryPath -Force

    $sourceBundlePath = Join-Path $temporaryPath 'PqLabel.bundle'
    $manifestPath = Join-Path $sourceBundlePath 'PackageContents.xml'
    $sourceDllPath = Join-Path $sourceBundlePath 'Contents\Windows\PqLabel.dll'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $sourceDllPath -PathType Leaf)) {
        Stop-WithMessage 'The payload is incomplete or has an invalid folder structure.'
    }

    [xml]$manifest = Get-Content -LiteralPath $manifestPath -Raw
    $payloadVersion = [string]$manifest.ApplicationPackage.AppVersion
    if ($payloadVersion -ne $releaseVersion) {
        Stop-WithMessage "Payload version '$payloadVersion' does not match installer version '$releaseVersion'."
    }

    $sourceHash = (Get-FileHash -LiteralPath $sourceDllPath -Algorithm SHA256).Hash
    if ($sourceHash -ne $expectedDllSha256) {
        Stop-WithMessage 'PqLabel.dll failed SHA-256 verification. Do not install this package.'
    }

    New-Item -ItemType Directory -Path $applicationPluginsPath -Force | Out-Null
    if (Test-Path -LiteralPath $targetBundlePath) {
        $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $backupPath = Join-Path $applicationPluginsPath "PqLabel.bundle.backup-$timestamp"
        if (Test-Path -LiteralPath $backupPath) {
            $backupPath += '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
        }
        Move-Item -LiteralPath $targetBundlePath -Destination $backupPath
        Write-Host "Previous bundle backed up to: $backupPath" -ForegroundColor Yellow
    }

    try {
        Copy-Item -LiteralPath $sourceBundlePath -Destination $targetBundlePath -Recurse
        Get-ChildItem -LiteralPath $targetBundlePath -File -Recurse | Unblock-File

        $installedToolsPath = Join-Path $targetBundlePath 'Installer'
        New-Item -ItemType Directory -Path $installedToolsPath -Force | Out-Null
        foreach ($toolName in @('Uninstall.cmd','Uninstall-PqLabel.ps1','README-INSTALL-KO.txt')) {
            $toolSource = Join-Path $PSScriptRoot $toolName
            if (Test-Path -LiteralPath $toolSource -PathType Leaf) {
                Copy-Item -LiteralPath $toolSource -Destination (Join-Path $installedToolsPath $toolName)
            }
        }

        $installedDllPath = Join-Path $targetBundlePath 'Contents\Windows\PqLabel.dll'
        $installedHash = (Get-FileHash -LiteralPath $installedDllPath -Algorithm SHA256).Hash
        if ($installedHash -ne $expectedDllSha256) {
            throw 'Installed DLL hash verification failed.'
        }
    }
    catch {
        if (Test-Path -LiteralPath $targetBundlePath) {
            Remove-Item -LiteralPath $targetBundlePath -Recurse -Force
        }
        if ($backupPath -and (Test-Path -LiteralPath $backupPath)) {
            Move-Item -LiteralPath $backupPath -Destination $targetBundlePath
        }
        throw
    }

    Write-Host ''
    Write-Host "PQ Label $releaseVersion installed successfully." -ForegroundColor Green
    Write-Host "Location: $targetBundlePath"
    Write-Host "Uninstaller: $(Join-Path $targetBundlePath 'Installer\Uninstall.cmd')"
    Write-Host 'Start AutoCAD and run PQPALETTE.'
}
finally {
    $resolvedTempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $resolvedTemporaryPath = [IO.Path]::GetFullPath($temporaryPath)
    if ($resolvedTemporaryPath.StartsWith($resolvedTempRoot, [StringComparison]::OrdinalIgnoreCase) -and
        (Test-Path -LiteralPath $resolvedTemporaryPath)) {
        Remove-Item -LiteralPath $resolvedTemporaryPath -Recurse -Force
    }
}
