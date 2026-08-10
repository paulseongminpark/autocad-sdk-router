param(
  [string]$Configuration = 'Release',
  [string]$Platform = 'x64',
  [string]$RouterHome = '',
  [string]$OutputRoot = '',
  [string]$TargetSuffix = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RouterHome)) {
  $RouterHome = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
}
$RouterHome = (Resolve-Path -LiteralPath $RouterHome).Path

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

function Get-Sha256File {
  param([string]$Path)
  $stream = [System.IO.File]::OpenRead($Path)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    -join ($sha.ComputeHash($stream) | ForEach-Object { $_.ToString('x2') })
  } finally {
    $sha.Dispose()
    $stream.Dispose()
  }
}

function Get-Sha256Text {
  param([string]$Text)
  $encoding = New-Object System.Text.UTF8Encoding($false)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $bytes = $encoding.GetBytes($Text)
    -join ($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') })
  } finally {
    $sha.Dispose()
  }
}

function Test-NativeBuildOutputPart {
  param([string]$Part)
  $normalized = $Part.ToLowerInvariant()
  return (
    $normalized -in @('bin', 'obj', '.vs', 'build') -or
    $normalized.StartsWith('obj-') -or
    $normalized.StartsWith('obj_')
  )
}

function Get-NativeSourceInputs {
  $roots = @(
    (Join-Path $RouterHome 'src\Ariadne.AcadNative'),
    (Join-Path $RouterHome 'src\Ariadne.AcadNativeDbx')
  )
  $inputs = @()
  foreach ($root in $roots) {
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
      throw "Native source root missing: $root"
    }
    foreach ($file in (Get-ChildItem -LiteralPath $root -Recurse -File -Force)) {
      $relative = $file.FullName.Substring($RouterHome.Length).TrimStart('\', '/') -replace '\\', '/'
      $parts = $relative -split '/'
      $skip = $false
      if ($parts.Count -gt 1) {
        foreach ($part in $parts[0..($parts.Count - 2)]) {
          if (Test-NativeBuildOutputPart $part) {
            $skip = $true
            break
          }
        }
      }
      if (-not $skip) {
        $inputs += [ordered]@{
          path = $relative
          sha256 = Get-Sha256File -Path $file.FullName
          bytes = [int64]$file.Length
        }
      }
    }
  }
  $inputs = @($inputs | Sort-Object @{ Expression = { $_.path.ToLowerInvariant() } }, @{ Expression = { $_.path } })
  if ($inputs.Count -eq 0) { throw 'Native source input inventory is empty.' }
  return $inputs
}

function Get-NativeSourceDigest {
  param([object[]]$Inputs)
  $builder = New-Object System.Text.StringBuilder
  foreach ($input in $Inputs) {
    [void]$builder.Append([string]$input.path)
    [void]$builder.Append([char]0)
    [void]$builder.Append([string]$input.sha256)
    [void]$builder.Append([char]0)
    [void]$builder.Append([string]$input.bytes)
    [void]$builder.Append("`n")
  }
  Get-Sha256Text $builder.ToString()
}

function Get-NativeSourceGitState {
  $unknown = [ordered]@{
    available = $false
    head = 'UNKNOWN'
    native_source_dirty = 'UNKNOWN'
    native_source_status_sha256 = 'UNKNOWN'
  }
  $git = Get-Command git -CommandType Application -ErrorAction SilentlyContinue
  if (-not $git) { return $unknown }
  try {
    $headLines = & $git.Source -C $RouterHome rev-parse HEAD 2>$null
    if ($LASTEXITCODE -ne 0) { return $unknown }
    $head = (@($headLines) -join "`n").Trim()
    if ([string]::IsNullOrWhiteSpace($head)) { return $unknown }
    # Do not bind a native build to unrelated tracked products such as the
    # router status report.  The explicit source pathspec mirrors the source
    # inventory's output exclusions, so build output cannot make source state
    # look dirty either.
    $statusArgs = @(
      '-C', $RouterHome,
      'status', '--porcelain=v1', '--untracked-files=all', '--',
      'src/Ariadne.AcadNative',
      'src/Ariadne.AcadNativeDbx',
      ':(exclude)src/Ariadne.AcadNative/bin/**',
      ':(exclude)src/Ariadne.AcadNative/obj/**',
      ':(exclude)src/Ariadne.AcadNative/.vs/**',
      ':(exclude)src/Ariadne.AcadNative/build/**',
      ':(exclude)src/Ariadne.AcadNative/**/bin/**',
      ':(exclude)src/Ariadne.AcadNative/**/obj/**',
      ':(exclude)src/Ariadne.AcadNative/**/.vs/**',
      ':(exclude)src/Ariadne.AcadNative/**/build/**',
      ':(exclude)src/Ariadne.AcadNative/**/obj-*/**',
      ':(exclude)src/Ariadne.AcadNative/**/obj_*/**',
      ':(exclude)src/Ariadne.AcadNativeDbx/bin/**',
      ':(exclude)src/Ariadne.AcadNativeDbx/obj/**',
      ':(exclude)src/Ariadne.AcadNativeDbx/.vs/**',
      ':(exclude)src/Ariadne.AcadNativeDbx/build/**',
      ':(exclude)src/Ariadne.AcadNativeDbx/**/bin/**',
      ':(exclude)src/Ariadne.AcadNativeDbx/**/obj/**',
      ':(exclude)src/Ariadne.AcadNativeDbx/**/.vs/**',
      ':(exclude)src/Ariadne.AcadNativeDbx/**/build/**',
      ':(exclude)src/Ariadne.AcadNativeDbx/**/obj-*/**',
      ':(exclude)src/Ariadne.AcadNativeDbx/**/obj_*/**'
    )
    $statusLines = & $git.Source @statusArgs 2>$null
    if ($LASTEXITCODE -ne 0) { return $unknown }
    $statusText = @($statusLines) -join "`n"
    return [ordered]@{
      available = $true
      head = $head
      native_source_dirty = (-not [string]::IsNullOrEmpty($statusText))
      native_source_status_sha256 = Get-Sha256Text $statusText
    }
  } catch {
    return $unknown
  }
}

function Get-BuildRecipeState {
  $relative = 'tools/build_native_acad.ps1'
  $path = Join-Path $RouterHome ($relative -replace '/', '\\')
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "Native build recipe missing: $path"
  }
  return [ordered]@{
    path = $relative
    sha256 = Get-Sha256File -Path $path
  }
}

function Get-NativeBuildSnapshot {
  $inputs = @(Get-NativeSourceInputs)
  return [ordered]@{
    source_tree = [ordered]@{
      algorithm = 'sha256'
      digest = Get-NativeSourceDigest $inputs
      inputs = $inputs
    }
    git = Get-NativeSourceGitState
    build_recipe = Get-BuildRecipeState
  }
}

function Get-NativeBuildSnapshotDigest {
  param([object]$Snapshot)
  return Get-Sha256Text (($Snapshot | ConvertTo-Json -Depth 12 -Compress))
}

function Test-NativeBuildSnapshotEqual {
  param([object]$Before, [object]$After)
  return (Get-NativeBuildSnapshotDigest $Before) -ceq (Get-NativeBuildSnapshotDigest $After)
}

function New-NativeArtifactRecord {
  param([string]$BinDir, [string]$Leaf, [bool]$Current)
  $path = Join-Path $BinDir $Leaf
  $exists = Test-Path -LiteralPath $path -PathType Leaf
  return [ordered]@{
    leaf = $Leaf
    sha256 = if ($exists) { Get-Sha256File $path } else { 'UNKNOWN' }
    bytes = if ($exists) { [int64](Get-Item -LiteralPath $path).Length } else { [int64]0 }
    current = $Current
    exists = $exists
  }
}

function Write-AtomicJson {
  param([object]$Object, [string]$Path)
  $directory = Split-Path -Parent $Path
  if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
    throw "Manifest directory missing: $directory"
  }
  $temporary = Join-Path $directory ("." + [System.IO.Path]::GetFileName($Path) + "." + [guid]::NewGuid().ToString('N') + '.tmp')
  $backup = Join-Path $directory ("." + [System.IO.Path]::GetFileName($Path) + "." + [guid]::NewGuid().ToString('N') + '.bak')
  $encoding = New-Object System.Text.UTF8Encoding($false)
  $stream = $null
  try {
    $stream = New-Object System.IO.FileStream($temporary, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    $bytes = $encoding.GetBytes(($Object | ConvertTo-Json -Depth 12) + "`n")
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Flush($true)
    $stream.Dispose()
    $stream = $null
    if ([System.IO.File]::Exists($Path)) {
      # Windows PowerShell/.NET Framework does not reliably marshal a null
      # backup path for File.Replace.  A UUID backup keeps the replacement
      # atomic; the controlled backup is removed in this invocation's finally.
      [System.IO.File]::Replace($temporary, $Path, $backup)
    } else {
      [System.IO.File]::Move($temporary, $Path)
    }
  } finally {
    if ($stream) { $stream.Dispose() }
    if (Test-Path -LiteralPath $temporary) {
      Remove-Item -LiteralPath $temporary -Force
    }
    if (Test-Path -LiteralPath $backup) {
      Remove-Item -LiteralPath $backup -Force
    }
  }
}

# Capture every provenance input before MSBuild has a chance to compile from a
# moving source tree.  A post-build-only hash could otherwise certify binaries
# compiled before a source edit as though they came from the newer checkout.
$nativeBuildSnapshotBefore = Get-NativeBuildSnapshot
$nativeBuildSnapshotBeforeDigest = Get-NativeBuildSnapshotDigest $nativeBuildSnapshotBefore
$msbuild = Resolve-MSBuild
$dbxProj = Join-Path $RouterHome 'src\Ariadne.AcadNativeDbx\Ariadne.AcadNativeDbx.dbx.vcxproj'
$crxProj = Join-Path $RouterHome 'src\Ariadne.AcadNative\Ariadne.AcadNative.crx.vcxproj'
$arxProj = Join-Path $RouterHome 'src\Ariadne.AcadNative\Ariadne.AcadNative.arx.vcxproj'

$isolatedBuild = -not [string]::IsNullOrWhiteSpace($OutputRoot)
if ($isolatedBuild) {
  $OutputRoot = (New-Item -ItemType Directory -Force -Path $OutputRoot).FullName
}

function Build-Project {
  param([string]$Project, [string]$ObjectSubdir, [string]$TargetBase, [string[]]$ExtraProps = @())
  if (-not (Test-Path -LiteralPath $Project)) { throw "Native project missing: $Project" }
  $props = @("/p:Configuration=$Configuration", "/p:Platform=$Platform")
  if ($script:isolatedBuild) {
    $outDir = (Join-Path $script:OutputRoot "bin\$Platform\$Configuration") + '\'
    $intDir = (Join-Path $script:OutputRoot "obj\$ObjectSubdir\$Platform\$Configuration") + '\'
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    New-Item -ItemType Directory -Force -Path $intDir | Out-Null
    $props += "/p:OutDir=$outDir"
    $props += "/p:IntDir=$intDir"
    if (-not [string]::IsNullOrWhiteSpace($TargetSuffix)) {
      $props += "/p:TargetName=$TargetBase$TargetSuffix"
      if ($ObjectSubdir -eq 'dbx') {
        # The .crx/.arx projects link against Ariadne.AcadNativeDbx.lib by name.
        # Keep that import-library leaf canonical inside the isolated OutDir while
        # the loadable .dbx itself may be version/suffix named.
        $props += "/p:ImportLibrary=$outDir\Ariadne.AcadNativeDbx.lib"
      }
    }
  }
  $argList = @($Project) + $props + $ExtraProps + @('/m', '/v:minimal')
  & $msbuild @argList
  $script:LastNativeBuildExitCode = $LASTEXITCODE
}

# .dbx + .crx are the headless truth modules (inspect.database.graph runs on the
# .crx via accoreconsole). They are never held by an attended acad.exe, so they
# must build cleanly.
Build-Project -Project $dbxProj -ObjectSubdir 'dbx' -TargetBase 'Ariadne.AcadNativeDbx'
if ($script:LastNativeBuildExitCode -ne 0) { throw "MSBuild failed for $dbxProj with exit $script:LastNativeBuildExitCode" }
Build-Project -Project $crxProj -ObjectSubdir 'crx' -TargetBase 'Ariadne.AcadNative'
if ($script:LastNativeBuildExitCode -ne 0) { throw "MSBuild failed for $crxProj with exit $script:LastNativeBuildExitCode" }

# .arx is the attended/live module. A running acad.exe holds the canonical
# Ariadne.AcadNative.arx (LNK1104). We NEVER kill AutoCAD: instead we relink to a
# versioned target so the build still proves the .arx compiles + links with the
# current source, and the live-pump loader can load the versioned module. The
# canonical .arx relinks automatically on the next lock-free build.
Build-Project -Project $arxProj -ObjectSubdir 'arx' -TargetBase 'Ariadne.AcadNative'
$arxCanonicalCode = $script:LastNativeBuildExitCode
$arxMode = 'canonical'
$arxVersionedName = ''
if ($arxCanonicalCode -ne 0) {
  $arxVersionedName = "Ariadne.AcadNative.live_$((Get-Date -Format 'yyyyMMdd_HHmmss'))"
  Build-Project -Project $arxProj -ObjectSubdir 'arx' -TargetBase 'Ariadne.AcadNative' -ExtraProps @("/p:TargetName=$arxVersionedName")
  $arxVersionedCode = $script:LastNativeBuildExitCode
  if ($arxVersionedCode -ne 0) {
    throw "MSBuild failed for .arx (canonical exit $arxCanonicalCode, versioned exit $arxVersionedCode); not a lock issue."
  }
  $arxMode = 'versioned_lock_bypass'
}

$nativeBuildSnapshotAfterMsbuild = Get-NativeBuildSnapshot
$nativeBuildSnapshotAfterMsbuildDigest = Get-NativeBuildSnapshotDigest $nativeBuildSnapshotAfterMsbuild
if (-not (Test-NativeBuildSnapshotEqual -Before $nativeBuildSnapshotBefore -After $nativeBuildSnapshotAfterMsbuild)) {
  throw 'Native source, native-source Git state, or build recipe changed while MSBuild ran; refusing to emit a provenance manifest.'
}

$bin = if ($isolatedBuild) { Join-Path $OutputRoot "bin\$Platform\$Configuration" } else { Join-Path $RouterHome "src\Ariadne.AcadNative\bin\$Platform\$Configuration" }
if (-not (Test-Path -LiteralPath $bin -PathType Container)) {
  throw "Native build output directory missing: $bin"
}
$bin = (Resolve-Path -LiteralPath $bin).Path
$nativeBase = if ([string]::IsNullOrWhiteSpace($TargetSuffix)) { 'Ariadne.AcadNative' } else { "Ariadne.AcadNative$TargetSuffix" }
$dbxBase = if ([string]::IsNullOrWhiteSpace($TargetSuffix)) { 'Ariadne.AcadNativeDbx' } else { "Ariadne.AcadNativeDbx$TargetSuffix" }
$artifactRecords = @(
  (New-NativeArtifactRecord -BinDir $bin -Leaf "$dbxBase.dbx" -Current $true),
  (New-NativeArtifactRecord -BinDir $bin -Leaf "$nativeBase.crx" -Current $true),
  (New-NativeArtifactRecord -BinDir $bin -Leaf "$nativeBase.arx" -Current ($arxMode -eq 'canonical'))
)
if ($arxVersionedName) {
  $artifactRecords += (New-NativeArtifactRecord -BinDir $bin -Leaf "$arxVersionedName.arx" -Current $true)
}
$artifactLeaves = @($artifactRecords | ForEach-Object { $_.leaf })
$requiredBuiltLeaves = @("$dbxBase.dbx", "$nativeBase.crx")
if ($arxVersionedName) {
  $requiredBuiltLeaves += "$arxVersionedName.arx"
} else {
  $requiredBuiltLeaves += "$nativeBase.arx"
}
$missingBuiltArtifacts = @($artifactRecords | Where-Object {
  ($requiredBuiltLeaves -contains $_.leaf) -and ((-not $_.exists) -or $_.bytes -le 0)
})
if ($missingBuiltArtifacts.Count -gt 0) {
  throw ('Native build did not produce required artifacts: ' + (($missingBuiltArtifacts | ForEach-Object { $_.leaf }) -join ', '))
}

# Deploy headless modules into prebuilt/<newest>/ -- patch_engine resolves
# prebuilt BEFORE src/bin (_resolve_native_acad_bin_dir), so a rebuild that
# does not refresh prebuilt ships STALE code to every subsequent flight.
# Measured on R4t (runs/e2e_1dwg_R4t_vintage_20260710): the lwpolyline
# setElevation repair was built to src/bin but the flight arxloaded
# prebuilt/2027's 07-09 crx -- 25 predicted pairs did not fold. Canonical,
# non-isolated, non-suffixed builds now refresh prebuilt automatically.
$prebuiltDeployed = @()
if (-not $isolatedBuild -and [string]::IsNullOrWhiteSpace($TargetSuffix)) {
  $prebuiltRoot = Join-Path $RouterHome 'prebuilt'
  if (Test-Path -LiteralPath $prebuiltRoot) {
    $deployDir = Get-ChildItem -LiteralPath $prebuiltRoot -Directory |
      Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'Ariadne.AcadNative.crx') } |
      Sort-Object Name -Descending | Select-Object -First 1
    if ($deployDir) {
      foreach ($leaf in @('Ariadne.AcadNativeDbx.dbx', 'Ariadne.AcadNative.crx')) {
        $src = Join-Path $bin $leaf
        if (Test-Path -LiteralPath $src) {
          Copy-Item -LiteralPath $src -Destination (Join-Path $deployDir.FullName $leaf) -Force
          $prebuiltDeployed += (Join-Path $deployDir.FullName $leaf)
        }
      }
    }
  }
}

$nativeBuildSnapshotBeforeManifest = Get-NativeBuildSnapshot
$nativeBuildSnapshotBeforeManifestDigest = Get-NativeBuildSnapshotDigest $nativeBuildSnapshotBeforeManifest
if (-not (Test-NativeBuildSnapshotEqual -Before $nativeBuildSnapshotBefore -After $nativeBuildSnapshotBeforeManifest)) {
  throw 'Native source, native-source Git state, or build recipe changed after MSBuild and before manifest publication.'
}
$sourceInputs = @($nativeBuildSnapshotBefore.source_tree.inputs)
$sourceDigest = $nativeBuildSnapshotBefore.source_tree.digest
$gitState = $nativeBuildSnapshotBefore.git
$buildRecipeState = $nativeBuildSnapshotBefore.build_recipe
$snapshotStable = $true
$canonicalDbx = Join-Path $bin 'Ariadne.AcadNativeDbx.dbx'
$canonicalCrx = Join-Path $bin 'Ariadne.AcadNative.crx'
$canonicalArx = Join-Path $bin 'Ariadne.AcadNative.arx'
$canonicalDbxCurrent = [string]::IsNullOrWhiteSpace($TargetSuffix) -and (Test-Path -LiteralPath $canonicalDbx -PathType Leaf) -and ((Get-Item -LiteralPath $canonicalDbx).Length -gt 0)
$canonicalCrxCurrent = [string]::IsNullOrWhiteSpace($TargetSuffix) -and (Test-Path -LiteralPath $canonicalCrx -PathType Leaf) -and ((Get-Item -LiteralPath $canonicalCrx).Length -gt 0)
$canonicalArxCurrent = [string]::IsNullOrWhiteSpace($TargetSuffix) -and $arxMode -eq 'canonical' -and (Test-Path -LiteralPath $canonicalArx -PathType Leaf) -and ((Get-Item -LiteralPath $canonicalArx).Length -gt 0)
$displayMembershipReady = (
  $Configuration -eq 'Release' -and
  $Platform -eq 'x64' -and
  $canonicalDbxCurrent -and
  $canonicalCrxCurrent -and
  $canonicalArxCurrent -and
  $gitState.available -and
  $snapshotStable
)
$manifestPath = Join-Path $bin 'native_build_manifest.json'
$manifest = [ordered]@{
  schema = 'ariadne.cad_os.native_build_manifest.v1'
  schema_version = 1
  configuration = $Configuration
  platform = $Platform
  load_bin_dir = $bin
  checkout = [ordered]@{
    root = $RouterHome
    git = $gitState
  }
  build_recipe = $buildRecipeState
  source_tree = [ordered]@{
    algorithm = 'sha256'
    digest = $sourceDigest
    inputs = $sourceInputs
  }
  build_snapshot = [ordered]@{
    before_msbuild_sha256 = $nativeBuildSnapshotBeforeDigest
    after_msbuild_sha256 = $nativeBuildSnapshotAfterMsbuildDigest
    before_manifest_sha256 = $nativeBuildSnapshotBeforeManifestDigest
    exact_match = $snapshotStable
  }
  artifacts = $artifactRecords
  display_membership = [ordered]@{
    ready = [bool]$displayMembershipReady
    canonical_arx_current = [bool]$canonicalArxCurrent
    reason = if (-not $gitState.available) {
      'Git checkout identity is UNKNOWN; display-membership provenance is not ready.'
    } elseif ($Configuration -ne 'Release' -or $Platform -ne 'x64') {
      'Display membership requires the canonical Release|x64 build.'
    } elseif (-not $canonicalArxCurrent) {
      'Canonical Ariadne.AcadNative.arx is not a current build artifact.'
    } elseif (-not ($canonicalDbxCurrent -and $canonicalCrxCurrent)) {
      'Canonical DBX/CRX load artifacts are missing from this build output.'
    } else { 'All canonical display-membership load artifacts bind to this checkout.' }
  }
}
Write-AtomicJson -Object $manifest -Path $manifestPath
$manifestSha256 = Get-Sha256File $manifestPath
$manifestVerification = [ordered]@{
  status = if ($displayMembershipReady) { 'PASS' } else { 'NEEDS_BUILD' }
  verified = [bool]$displayMembershipReady
  manifest_path = $manifestPath
  manifest_sha256 = $manifestSha256
  schema = $manifest.schema
  configuration = $Configuration
  platform = $Platform
  load_bin_dir = $bin
  source_input_count = $sourceInputs.Count
  source_tree_digest = $sourceDigest
  git = $gitState
  build_recipe = $buildRecipeState
  snapshot_stable = $snapshotStable
  source_snapshot = $manifest.build_snapshot
  canonical_arx_current = [bool]$canonicalArxCurrent
  artifacts = $artifactRecords
}

[ordered]@{
  status = 'ok'
  msbuild = $msbuild
  arx_relink_mode = $arxMode
  arx_versioned_name = $arxVersionedName
  arx_lock_note = if ($arxMode -eq 'versioned_lock_bypass') {
    'Canonical .arx is held by a running AutoCAD; relinked to a versioned target. The canonical ARX is NOT current for display-membership provenance. AutoCAD was NOT killed.'
  } else { 'Canonical .arx relinked normally.' }
  projects = @($dbxProj, $crxProj, $arxProj)
  prebuilt_deployed = $prebuiltDeployed
  artifacts = @($artifactRecords | ForEach-Object {
    $path = Join-Path $bin $_.leaf
    [ordered]@{
      path = $path
      leaf = $_.leaf
      exists = $_.exists
      sha256 = $_.sha256
      bytes = $_.bytes
      current = $_.current
    }
  })
  build_manifest_path = $manifestPath
  build_manifest_sha256 = $manifestSha256
  build_manifest_verification = $manifestVerification
} | ConvertTo-Json -Depth 12
