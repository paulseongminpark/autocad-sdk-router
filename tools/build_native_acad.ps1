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
$dbxProj = Join-Path $RouterHome 'src\Ariadne.AcadNativeDbx\Ariadne.AcadNativeDbx.dbx.vcxproj'
$crxProj = Join-Path $RouterHome 'src\Ariadne.AcadNative\Ariadne.AcadNative.crx.vcxproj'
$arxProj = Join-Path $RouterHome 'src\Ariadne.AcadNative\Ariadne.AcadNative.arx.vcxproj'

function Build-Project {
  param([string]$Project, [string[]]$ExtraProps = @())
  if (-not (Test-Path -LiteralPath $Project)) { throw "Native project missing: $Project" }
  $argList = @($Project, "/p:Configuration=$Configuration", "/p:Platform=$Platform") + $ExtraProps + @('/m', '/v:minimal')
  & $msbuild @argList
  return $LASTEXITCODE
}

# .dbx + .crx are the headless truth modules (inspect.database.graph runs on the
# .crx via accoreconsole). They are never held by an attended acad.exe, so they
# must build cleanly.
foreach ($p in @($dbxProj, $crxProj)) {
  if ((Build-Project -Project $p) -ne 0) { throw "MSBuild failed for $p with exit $LASTEXITCODE" }
}

# .arx is the attended/live module. A running acad.exe holds the canonical
# Ariadne.AcadNative.arx (LNK1104). We NEVER kill AutoCAD: instead we relink to a
# versioned target so the build still proves the .arx compiles + links with the
# current source, and the live-pump loader can load the versioned module. The
# canonical .arx relinks automatically on the next lock-free build.
$arxCanonicalCode = Build-Project -Project $arxProj
$arxMode = 'canonical'
$arxVersionedName = ''
if ($arxCanonicalCode -ne 0) {
  $arxVersionedName = "Ariadne.AcadNative.live_$((Get-Date -Format 'yyyyMMdd_HHmmss'))"
  $arxVersionedCode = Build-Project -Project $arxProj -ExtraProps @("/p:TargetName=$arxVersionedName")
  if ($arxVersionedCode -ne 0) {
    throw "MSBuild failed for .arx (canonical exit $arxCanonicalCode, versioned exit $arxVersionedCode); not a lock issue."
  }
  $arxMode = 'versioned_lock_bypass'
}

$bin = Join-Path $RouterHome "src\Ariadne.AcadNative\bin\$Platform\$Configuration"
$artifactLeaves = @('Ariadne.AcadNativeDbx.dbx', 'Ariadne.AcadNative.crx', 'Ariadne.AcadNative.arx')
if ($arxVersionedName) { $artifactLeaves += "$arxVersionedName.arx" }

[ordered]@{
  status = 'ok'
  msbuild = $msbuild
  arx_relink_mode = $arxMode
  arx_versioned_name = $arxVersionedName
  arx_lock_note = if ($arxMode -eq 'versioned_lock_bypass') {
    'Canonical .arx is held by a running AutoCAD; relinked to a versioned target. Canonical relinks on next lock-free build. AutoCAD was NOT killed.'
  } else { 'Canonical .arx relinked normally.' }
  projects = @($dbxProj, $crxProj, $arxProj)
  artifacts = @($artifactLeaves | ForEach-Object {
    $path = Join-Path $bin $_
    [ordered]@{
      path = $path
      exists = Test-Path -LiteralPath $path
      bytes = if (Test-Path -LiteralPath $path) { (Get-Item -LiteralPath $path).Length } else { 0 }
    }
  })
} | ConvertTo-Json -Depth 5
