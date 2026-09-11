#requires -Version 7.0
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$global:LASTEXITCODE = 0
& (Join-Path $root 'src\PqLabel\build-roslyn.ps1')
if ($LASTEXITCODE -ne 0) { throw 'PQ Label compilation failed.' }
$destination = Join-Path $root 'prebuilt\2027\pq-label\router'
New-Item -ItemType Directory -Path $destination -Force | Out-Null
$dll = Join-Path $destination 'PqLabel.dll'
Copy-Item -LiteralPath (Join-Path $root 'src\PqLabel\bin\Release\net10.0-windows\PqLabel.dll') -Destination $dll
$sources = [ordered]@{}
Get-ChildItem (Join-Path $root 'src\PqLabel') -Recurse -File |
  Where-Object { $_.FullName -notmatch '[\\/](bin|obj)[\\/]' -and $_.Extension -in @('.cs', '.csproj', '.ps1') } |
  Sort-Object FullName | ForEach-Object {
    $relative = [IO.Path]::GetRelativePath($root, $_.FullName).Replace('\', '/')
    $sources[$relative] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
  }
[ordered]@{
  schema = 'pq_label.router_build.v1'
  sha256 = (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash
  sources = $sources
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $destination 'manifest.json') -Encoding utf8
