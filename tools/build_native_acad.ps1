param(
  [string]$Configuration = 'Release',
  [string]$Platform = 'x64',
  [string]$RouterHome = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RouterHome)) {
  $RouterHome = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
}

function Resolve-MSBuild {
  $preferred = @(
    'C:\Program Files\Microsoft Visual Studio\2026\Community\MSBuild\Current\Bin\amd64\MSBuild.exe',
    'C:\Program Files\Microsoft Visual Studio\2026\Community\MSBuild\Current\Bin\MSBuild.exe'
  )
  foreach ($path in $preferred) {
    if (Test-Path -LiteralPath $path) { return $path }
  }
  $found = Get-ChildItem -Path 'C:\Program Files\Microsoft Visual Studio' -Recurse -Filter MSBuild.exe -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Select-Object -First 1
  if ($found) { return $found.FullName }
  throw 'MSBuild.exe not found under Visual Studio.'
}

$msbuild = Resolve-MSBuild
$projects = @(
  (Join-Path $RouterHome 'src\Ariadne.AcadNativeDbx\Ariadne.AcadNativeDbx.dbx.vcxproj'),
  (Join-Path $RouterHome 'src\Ariadne.AcadNative\Ariadne.AcadNative.crx.vcxproj'),
  (Join-Path $RouterHome 'src\Ariadne.AcadNative\Ariadne.AcadNative.arx.vcxproj')
)

foreach ($project in $projects) {
  if (-not (Test-Path -LiteralPath $project)) {
    throw "Native project missing: $project"
  }
  & $msbuild $project "/p:Configuration=$Configuration" "/p:Platform=$Platform" /m /v:minimal
  if ($LASTEXITCODE -ne 0) {
    throw "MSBuild failed for $project with exit $LASTEXITCODE"
  }
}

$bin = Join-Path $RouterHome "src\Ariadne.AcadNative\bin\$Platform\$Configuration"
$artifacts = @(
  (Join-Path $bin 'Ariadne.AcadNativeDbx.dbx'),
  (Join-Path $bin 'Ariadne.AcadNative.crx'),
  (Join-Path $bin 'Ariadne.AcadNative.arx')
)

[ordered]@{
  status = 'ok'
  msbuild = $msbuild
  projects = $projects
  artifacts = @($artifacts | ForEach-Object {
    [ordered]@{
      path = $_
      exists = Test-Path -LiteralPath $_
      bytes = if (Test-Path -LiteralPath $_) { (Get-Item -LiteralPath $_).Length } else { 0 }
    }
  })
} | ConvertTo-Json -Depth 5
