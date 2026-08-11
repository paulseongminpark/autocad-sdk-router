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
$buildTarget = if ($Configuration -ieq 'Release') { 'Rebuild' } else { 'Build' }
$msbuildTargetArgument = if ($Configuration -ieq 'Release') { '/t:Rebuild' } else { '/t:Build' }
$claimScope = if ($Configuration -ieq 'Release') {
  'release_build_integrity_bundle'
} else {
  'non_release_build_diagnostic'
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

function Get-Sha256Bytes {
  param([byte[]]$Bytes)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    -join ($sha.ComputeHash($Bytes) | ForEach-Object { $_.ToString('x2') })
  } finally {
    $sha.Dispose()
  }
}

function Get-CanonicalNativeSourceBytes {
  param([string]$Path)
  [byte[]]$raw = [System.IO.File]::ReadAllBytes($Path)
  if ([Array]::IndexOf($raw, [byte]0) -ge 0) {
    Write-Output -NoEnumerate $raw
    return
  }
  $buffer = New-Object System.IO.MemoryStream
  try {
    for ($index = 0; $index -lt $raw.Length; $index++) {
      if ($raw[$index] -eq 13 -and ($index + 1) -lt $raw.Length -and $raw[$index + 1] -eq 10) {
        $buffer.WriteByte(10)
        $index++
      } else {
        $buffer.WriteByte($raw[$index])
      }
    }
    [byte[]]$canonical = $buffer.ToArray()
  } finally {
    $buffer.Dispose()
  }
  Write-Output -NoEnumerate $canonical
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
    $rootItem = Get-Item -LiteralPath $root -Force
    if (($rootItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
      throw "Native source root is a reparse point: $root"
    }
    $pending = New-Object System.Collections.Queue
    $pending.Enqueue($rootItem.FullName)
    while ($pending.Count -gt 0) {
      $current = $pending.Dequeue()
      foreach ($entry in (Get-ChildItem -LiteralPath $current -Force)) {
        if (($entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
          throw "Native source tree contains a reparse point: $($entry.FullName)"
        }
        if ($entry.PSIsContainer) {
          if (-not (Test-NativeBuildOutputPart $entry.Name)) {
            $pending.Enqueue($entry.FullName)
          }
          continue
        }
        $relative = $entry.FullName.Substring($RouterHome.Length).TrimStart('\', '/') -replace '\\', '/'
        [byte[]]$sourceBytes = Get-CanonicalNativeSourceBytes -Path $entry.FullName
        $inputs += [ordered]@{
          path = $relative
          sha256 = Get-Sha256Bytes -Bytes $sourceBytes
          bytes = [int64]$sourceBytes.Length
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

function Test-NativeSourceStatusLine {
  param([string]$Line)
  if ([string]::IsNullOrWhiteSpace($Line)) { return $false }
  $payload = if ($Line.Length -ge 3) { $Line.Substring(3) } else { $Line }
  foreach ($candidate in @($payload -split ' -> ')) {
    $normalized = $candidate.Trim().Trim('"').Replace('\', '/')
    $hasBuildPart = $false
    foreach ($part in @($normalized -split '/')) {
      if (Test-NativeBuildOutputPart $part) {
        $hasBuildPart = $true
        break
      }
    }
    if (-not $hasBuildPart) { return $true }
  }
  return $false
}

function Get-NativeSourceGitState {
  $unknown = [ordered]@{
    available = $false
    head = 'UNKNOWN'
    native_source_dirty = 'UNKNOWN'
    native_source_status_sha256 = 'UNKNOWN'
  }
  $git = Get-Command git -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1
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
      'src/Ariadne.AcadNativeDbx'
    )
    $statusLines = @(& $git.Source @statusArgs 2>$null) |
      Where-Object { Test-NativeSourceStatusLine ([string]$_) }
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
  [byte[]]$recipeBytes = Get-CanonicalNativeSourceBytes -Path $path
  return [ordered]@{
    path = $relative
    sha256 = Get-Sha256Bytes -Bytes $recipeBytes
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

function Get-NativePeVerification {
  param([string]$Path)
  $verification = [ordered]@{
    verified = $false
    format = 'UNKNOWN'
    machine = 'UNKNOWN'
    minimum_bytes = [int64]512
    pe_header_offset = [int64]-1
    section_count = 0
    optional_header_bytes = 0
    reason = 'Artifact was not inspected.'
  }
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    $verification.reason = 'Artifact is missing.'
    return [pscustomobject]$verification
  }

  $file = Get-Item -LiteralPath $Path
  if ([int64]$file.Length -lt $verification.minimum_bytes) {
    $verification.reason = "Artifact is too small to be a native load module ($($file.Length) bytes)."
    return [pscustomobject]$verification
  }

  $stream = $null
  $reader = $null
  try {
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    $reader = New-Object System.IO.BinaryReader($stream)
    if ($reader.ReadByte() -ne 0x4D -or $reader.ReadByte() -ne 0x5A) {
      $verification.reason = 'DOS MZ signature is missing.'
      return [pscustomobject]$verification
    }
    $stream.Position = 0x3C
    $peOffset = $reader.ReadInt32()
    $verification.pe_header_offset = [int64]$peOffset
    if ($peOffset -lt 0x40 -or ([int64]$peOffset + 26) -gt [int64]$stream.Length) {
      $verification.reason = 'PE header offset is outside the artifact.'
      return [pscustomobject]$verification
    }
    $stream.Position = $peOffset
    if ($reader.ReadUInt32() -ne 0x00004550) {
      $verification.reason = 'PE signature is missing.'
      return [pscustomobject]$verification
    }
    $machine = $reader.ReadUInt16()
    $sections = $reader.ReadUInt16()
    $verification.machine = ('0x{0:X4}' -f $machine)
    $verification.section_count = [int]$sections
    if ($machine -ne 0x8664) {
      $verification.reason = "PE machine is $($verification.machine), not x64 (0x8664)."
      return [pscustomobject]$verification
    }
    if ($sections -lt 1) {
      $verification.reason = 'PE file has no sections.'
      return [pscustomobject]$verification
    }
    $stream.Position = $peOffset + 20
    $optionalHeaderBytes = $reader.ReadUInt16()
    $verification.optional_header_bytes = [int]$optionalHeaderBytes
    if ($optionalHeaderBytes -lt 0xF0 -or ([int64]$peOffset + 24 + $optionalHeaderBytes) -gt [int64]$stream.Length) {
      $verification.reason = 'PE32+ optional header is truncated.'
      return [pscustomobject]$verification
    }
    $stream.Position = $peOffset + 24
    $optionalMagic = $reader.ReadUInt16()
    if ($optionalMagic -ne 0x020B) {
      $verification.reason = ('Optional-header magic is 0x{0:X4}, not PE32+ (0x020B).' -f $optionalMagic)
      return [pscustomobject]$verification
    }
    $verification.format = 'PE32+'
    $verification.verified = $true
    $verification.reason = 'MZ, PE, x64 machine, section table, and PE32+ optional header checks passed.'
    return [pscustomobject]$verification
  } catch {
    $verification.reason = "PE inspection failed: $($_.Exception.Message)"
    return [pscustomobject]$verification
  } finally {
    if ($reader) { $reader.Dispose() }
    if ($stream) { $stream.Dispose() }
  }
}

function New-NativeArtifactRecord {
  param([string]$BinDir, [string]$Leaf, [bool]$Current)
  $path = Join-Path $BinDir $Leaf
  $exists = Test-Path -LiteralPath $path -PathType Leaf
  $peVerification = Get-NativePeVerification -Path $path
  return [ordered]@{
    leaf = $Leaf
    sha256 = if ($exists) { Get-Sha256File $path } else { 'UNKNOWN' }
    bytes = if ($exists) { [int64](Get-Item -LiteralPath $path).Length } else { [int64]0 }
    current = $Current
    exists = $exists
    pe_verification = $peVerification
  }
}

function Write-AtomicJson {
  param([object]$Object, [string]$Path)
  $directory = Split-Path -Parent $Path
  if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
    throw "Manifest directory missing: $directory"
  }
  # Keep transaction leaves short: Windows PowerShell still encounters legacy
  # MAX_PATH behavior in deep clone/test roots even when the final path is valid.
  $nonce = [guid]::NewGuid().ToString('N')
  $temporary = Join-Path $directory ('.' + $nonce + '.tmp')
  $backup = Join-Path $directory ('.' + $nonce + '.bak')
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

function Confirm-NativeBuildManifest {
  param(
    [string]$ManifestPath,
    [string[]]$RequiredLeaves,
    [string]$ExpectedClaimScope,
    [string]$ExpectedBuildTarget,
    [string]$ExpectedConfiguration,
    [string]$ExpectedPlatform,
    [string]$ExpectedSourceTreeDigest
  )
  if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw "Native build manifest is missing: $ManifestPath"
  }
  try {
    $document = [System.IO.File]::ReadAllText($ManifestPath) | ConvertFrom-Json
  } catch {
    throw "Native build manifest is not valid JSON: $($_.Exception.Message)"
  }
  $expectedFields = [ordered]@{
    schema = 'ariadne.cad_os.native_build_manifest.v1'
    claim_scope = $ExpectedClaimScope
    build_target = $ExpectedBuildTarget
    configuration = $ExpectedConfiguration
    platform = $ExpectedPlatform
  }
  foreach ($entry in $expectedFields.GetEnumerator()) {
    if ([string]$document.($entry.Key) -cne [string]$entry.Value) {
      throw "Native build manifest $($entry.Key) mismatch: expected '$($entry.Value)', got '$($document.($entry.Key))'."
    }
  }
  if ([string]$document.source_tree.digest -cne $ExpectedSourceTreeDigest) {
    throw 'Native build manifest source-tree digest does not match the post-build snapshot.'
  }
  if ($document.build_snapshot.exact_match -ne $true) {
    throw 'Native build manifest does not record an exact pre/post source snapshot match.'
  }
  if (-not (Test-Path -LiteralPath ([string]$document.load_bin_dir) -PathType Container)) {
    throw "Native build manifest load_bin_dir is missing: $($document.load_bin_dir)"
  }

  $verifiedArtifacts = @()
  foreach ($leaf in $RequiredLeaves) {
    if ([System.IO.Path]::GetFileName($leaf) -cne $leaf) {
      throw "Native artifact leaf is not a plain file name: $leaf"
    }
    $matches = @($document.artifacts | Where-Object { [string]$_.leaf -ceq $leaf })
    if ($matches.Count -ne 1) {
      throw "Native build manifest must contain exactly one record for $leaf."
    }
    $claimed = $matches[0]
    if ($claimed.exists -ne $true -or $claimed.current -ne $true -or $claimed.pe_verification.verified -ne $true) {
      throw "Native build manifest does not mark $leaf as a current verified PE artifact."
    }
    $actual = New-NativeArtifactRecord -BinDir ([string]$document.load_bin_dir) -Leaf $leaf -Current $true
    if (-not $actual.exists -or $actual.pe_verification.verified -ne $true) {
      throw "Native artifact failed final PE verification: $leaf ($($actual.pe_verification.reason))"
    }
    if ([string]$claimed.sha256 -cne [string]$actual.sha256 -or [int64]$claimed.bytes -ne [int64]$actual.bytes) {
      throw "Native artifact changed after manifest creation: $leaf"
    }
    $verifiedArtifacts += $actual
  }

  return [ordered]@{
    status = 'PASS'
    verified = $true
    manifest_path = (Resolve-Path -LiteralPath $ManifestPath).Path
    manifest_sha256 = Get-Sha256File $ManifestPath
    claim_scope = $ExpectedClaimScope
    build_target = $ExpectedBuildTarget
    configuration = $ExpectedConfiguration
    platform = $ExpectedPlatform
    load_bin_dir = (Resolve-Path -LiteralPath ([string]$document.load_bin_dir)).Path
    source_tree_digest = $ExpectedSourceTreeDigest
    artifacts = $verifiedArtifacts
  }
}

function Confirm-NativeDeploymentManifest {
  param(
    [string]$ManifestPath,
    [string[]]$RequiredLeaves,
    [string]$ExpectedSourceTreeDigest,
    [string]$ExpectedBuildRecipeSha256
  )
  if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw "Native deployment commit marker is missing: $ManifestPath"
  }
  try {
    $document = [System.IO.File]::ReadAllText($ManifestPath) | ConvertFrom-Json
  } catch {
    throw "Native deployment commit marker is not valid JSON: $($_.Exception.Message)"
  }
  if ([string]$document.schema -cne 'ariadne.cad_os.native_deployment_manifest.v1' -or
      [string]$document.deployment_state -cne 'committed' -or
      $document.committed -ne $true) {
    throw 'Native deployment manifest is not a committed v1 deployment marker.'
  }
  if ([string]$document.claim_scope -cne 'release_build_integrity_bundle' -or
      [string]$document.build_target -cne 'Rebuild' -or
      [string]$document.configuration -cne 'Release' -or
      [string]$document.platform -cne 'x64') {
    throw 'Native deployment marker exceeds or contradicts the Release|x64 Rebuild integrity claim.'
  }
  if ([string]$document.source_tree_digest -cne $ExpectedSourceTreeDigest -or
      [string]$document.build_recipe.path -cne 'tools/build_native_acad.ps1' -or
      [string]$document.build_recipe.sha256 -cne $ExpectedBuildRecipeSha256) {
    throw 'Native deployment marker does not bind to the verified source tree and build recipe.'
  }
  $deployDir = Split-Path -Parent $ManifestPath
  foreach ($leaf in $RequiredLeaves) {
    $matches = @($document.artifacts | Where-Object { [string]$_.leaf -ceq $leaf })
    if ($matches.Count -ne 1) {
      throw "Native deployment marker must contain exactly one record for $leaf."
    }
    $claimed = $matches[0]
    $actual = New-NativeArtifactRecord -BinDir $deployDir -Leaf $leaf -Current $true
    if (-not $actual.exists -or $actual.pe_verification.verified -ne $true) {
      throw "Deployed native artifact failed PE verification: $leaf"
    }
    if ([string]$claimed.sha256 -cne [string]$actual.sha256 -or [int64]$claimed.bytes -ne [int64]$actual.bytes) {
      throw "Deployed native artifact does not match its commit marker: $leaf"
    }
  }
  return [ordered]@{
    status = 'PASS'
    verified = $true
    manifest_path = (Resolve-Path -LiteralPath $ManifestPath).Path
    manifest_sha256 = Get-Sha256File $ManifestPath
  }
}

function Publish-NativePrebuiltSet {
  param(
    [string]$BinDir,
    [string]$DeployDir,
    [string[]]$Leaves,
    [object]$BuildManifestVerification,
    [object]$SourceSnapshot
  )
  $canonicalLeaves = @('Ariadne.AcadNativeDbx.dbx', 'Ariadne.AcadNative.crx', 'Ariadne.AcadNative.arx')
  if (@(Compare-Object -ReferenceObject $canonicalLeaves -DifferenceObject @($Leaves)).Count -ne 0) {
    throw 'Prebuilt publication requires exactly the canonical DBX, CRX, and ARX leaves.'
  }
  if ($SourceSnapshot.git.available -ne $true) {
    throw 'Git checkout identity is unavailable; refusing prebuilt publication.'
  }
  if ($BuildManifestVerification.verified -ne $true -or
      [string]$BuildManifestVerification.claim_scope -cne 'release_build_integrity_bundle' -or
      [string]$BuildManifestVerification.build_target -cne 'Rebuild' -or
      [string]$BuildManifestVerification.configuration -cne 'Release' -or
      [string]$BuildManifestVerification.platform -cne 'x64') {
    throw 'Prebuilt publication requires a finalized Release|x64 Rebuild integrity manifest.'
  }
  if (-not (Test-NativeBuildSnapshotEqual -Before $SourceSnapshot -After (Get-NativeBuildSnapshot))) {
    throw 'Native source or build recipe changed after build-manifest verification.'
  }
  if (-not (Test-Path -LiteralPath $DeployDir -PathType Container)) {
    throw "Prebuilt deployment directory is missing: $DeployDir"
  }
  $DeployDir = (Resolve-Path -LiteralPath $DeployDir).Path
  $deployParent = (Resolve-Path -LiteralPath (Split-Path -Parent $DeployDir)).Path
  $stagingRoot = Join-Path $deployParent ('.native-deploy-' + [guid]::NewGuid().ToString('N'))
  [void][System.IO.Directory]::CreateDirectory($stagingRoot)
  $markerLeaf = 'native_deployment_manifest.json'
  $markerPath = Join-Path $DeployDir $markerLeaf
  $stagedMarkerPath = Join-Path $stagingRoot $markerLeaf
  $previousMarkerPath = Join-Path $stagingRoot 'previous_native_deployment_manifest.json'
  $replacements = New-Object System.Collections.ArrayList
  $previousMarkerMoved = $false
  $commitWritten = $false
  $failure = $null
  try {
    $stagedRecords = @()
    foreach ($leaf in $Leaves) {
      $sourcePath = Join-Path $BinDir $leaf
      $stagedPath = Join-Path $stagingRoot $leaf
      [System.IO.File]::Copy($sourcePath, $stagedPath, $false)
      $staged = New-NativeArtifactRecord -BinDir $stagingRoot -Leaf $leaf -Current $true
      $matches = @($BuildManifestVerification.artifacts | Where-Object { [string]$_.leaf -ceq $leaf })
      if ($matches.Count -ne 1 -or $staged.pe_verification.verified -ne $true -or
          [string]$matches[0].sha256 -cne [string]$staged.sha256 -or
          [int64]$matches[0].bytes -ne [int64]$staged.bytes) {
        throw "Staged native artifact does not match the finalized build manifest: $leaf"
      }
      $stagedRecords += $staged
    }
    $deploymentManifest = [ordered]@{
      schema = 'ariadne.cad_os.native_deployment_manifest.v1'
      schema_version = 1
      claim_scope = 'release_build_integrity_bundle'
      deployment_state = 'committed'
      committed = $true
      build_target = 'Rebuild'
      configuration = 'Release'
      platform = 'x64'
      build_recipe = [ordered]@{
        path = [string]$SourceSnapshot.build_recipe.path
        sha256 = [string]$SourceSnapshot.build_recipe.sha256
      }
      source_tree_digest = [string]$BuildManifestVerification.source_tree_digest
      artifacts = $stagedRecords
    }
    Write-AtomicJson -Object $deploymentManifest -Path $stagedMarkerPath
    $prepared = [System.IO.File]::ReadAllText($stagedMarkerPath) | ConvertFrom-Json
    if ([string]$prepared.deployment_state -cne 'committed' -or $prepared.committed -ne $true) {
      throw 'Staged deployment commit marker failed JSON verification.'
    }

    if ([System.IO.File]::Exists($markerPath)) {
      [System.IO.File]::Move($markerPath, $previousMarkerPath)
      $previousMarkerMoved = $true
    }
    foreach ($leaf in $Leaves) {
      $stagedPath = Join-Path $stagingRoot $leaf
      $destinationPath = Join-Path $DeployDir $leaf
      $backupPath = Join-Path $stagingRoot ('.previous-' + $leaf)
      $existed = [System.IO.File]::Exists($destinationPath)
      if ($existed) {
        [System.IO.File]::Replace($stagedPath, $destinationPath, $backupPath)
      } else {
        [System.IO.File]::Move($stagedPath, $destinationPath)
      }
      [void]$replacements.Add([pscustomobject]@{
        destination = $destinationPath
        backup = $backupPath
        existed = $existed
      })
      $deployed = New-NativeArtifactRecord -BinDir $DeployDir -Leaf $leaf -Current $true
      $expected = @($stagedRecords | Where-Object { [string]$_.leaf -ceq $leaf })[0]
      if ($deployed.pe_verification.verified -ne $true -or [string]$deployed.sha256 -cne [string]$expected.sha256) {
        throw "Atomic native artifact replacement failed verification: $leaf"
      }
    }
    if (-not (Test-NativeBuildSnapshotEqual -Before $SourceSnapshot -After (Get-NativeBuildSnapshot))) {
      throw 'Native source or build recipe changed before deployment commit.'
    }

    # This same-volume rename is the transaction commit. Consumers that require
    # this marker never accept the replacement set while any member is partial.
    [System.IO.File]::Move($stagedMarkerPath, $markerPath)
    $commitWritten = $true
    $deploymentVerification = Confirm-NativeDeploymentManifest -ManifestPath $markerPath `
      -RequiredLeaves $Leaves `
      -ExpectedSourceTreeDigest ([string]$SourceSnapshot.source_tree.digest) `
      -ExpectedBuildRecipeSha256 ([string]$SourceSnapshot.build_recipe.sha256)
    return [ordered]@{
      committed = $true
      deploy_dir = $DeployDir
      deployed_leaves = @($Leaves)
      deployment_manifest_path = $markerPath
      deployment_manifest_sha256 = $deploymentVerification.manifest_sha256
    }
  } catch {
    $failure = $_
    if ($commitWritten -and [System.IO.File]::Exists($markerPath)) {
      [System.IO.File]::Move($markerPath, (Join-Path $stagingRoot 'failed_native_deployment_manifest.json'))
    }
    for ($index = $replacements.Count - 1; $index -ge 0; $index--) {
      $replacement = $replacements[$index]
      if ($replacement.existed) {
        if ([System.IO.File]::Exists($replacement.backup)) {
          if ([System.IO.File]::Exists($replacement.destination)) {
            $discard = Join-Path $stagingRoot ('.failed-' + [guid]::NewGuid().ToString('N'))
            [System.IO.File]::Replace($replacement.backup, $replacement.destination, $discard)
          } else {
            [System.IO.File]::Move($replacement.backup, $replacement.destination)
          }
        }
      } elseif ([System.IO.File]::Exists($replacement.destination)) {
        [System.IO.File]::Move($replacement.destination, (Join-Path $stagingRoot ('.failed-new-' + [guid]::NewGuid().ToString('N'))))
      }
    }
    if ($previousMarkerMoved -and [System.IO.File]::Exists($previousMarkerPath) -and -not [System.IO.File]::Exists($markerPath)) {
      [System.IO.File]::Move($previousMarkerPath, $markerPath)
    }
    throw $failure
  } finally {
    if (Test-Path -LiteralPath $stagingRoot -PathType Container) {
      $resolvedStagingRoot = (Resolve-Path -LiteralPath $stagingRoot).Path
      $stagingInfo = Get-Item -LiteralPath $resolvedStagingRoot -Force
      $resolvedStagingParent = [System.IO.Path]::GetDirectoryName($resolvedStagingRoot)
      $stagingLeaf = [System.IO.Path]::GetFileName($resolvedStagingRoot)
      $stagingIsReparsePoint = (($stagingInfo.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)
      if (-not [string]::Equals($resolvedStagingParent, $deployParent, [System.StringComparison]::OrdinalIgnoreCase) -or
          $stagingLeaf -notmatch '^\.native-deploy-[0-9a-f]{32}$' -or
          $stagingIsReparsePoint) {
        throw "Refusing recursive staging cleanup outside the verified deployment parent: $resolvedStagingRoot"
      }
      [System.IO.Directory]::Delete($resolvedStagingRoot, $true)
    }
  }
}

# Capture every provenance input before MSBuild has a chance to compile from a
# moving source tree.  A post-build-only hash could otherwise certify binaries
# compiled before a source edit as though they came from the newer checkout.
$nativeBuildSnapshotBefore = Get-NativeBuildSnapshot
$nativeBuildSnapshotBeforeDigest = Get-NativeBuildSnapshotDigest $nativeBuildSnapshotBefore
if ($nativeBuildSnapshotBefore.git.available -ne $true) {
  throw 'Git checkout identity is unavailable; refusing native build before MSBuild.'
}
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
  $argList = @($Project) + $props + $ExtraProps + @($script:msbuildTargetArgument, '/m', '/v:minimal')
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
$invalidBuiltArtifacts = @($artifactRecords | Where-Object {
  ($requiredBuiltLeaves -contains $_.leaf) -and ($_.pe_verification.verified -ne $true)
})
if ($invalidBuiltArtifacts.Count -gt 0) {
  throw ('Native build artifact PE verification failed: ' + (($invalidBuiltArtifacts | ForEach-Object {
    "$($_.leaf) [$($_.pe_verification.reason)]"
  }) -join '; '))
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
$canonicalDbxRecord = @($artifactRecords | Where-Object { $_.leaf -ceq 'Ariadne.AcadNativeDbx.dbx' })[0]
$canonicalCrxRecord = @($artifactRecords | Where-Object { $_.leaf -ceq 'Ariadne.AcadNative.crx' })[0]
$canonicalArxRecord = @($artifactRecords | Where-Object { $_.leaf -ceq 'Ariadne.AcadNative.arx' })[0]
$canonicalDbxCurrent = (
  [string]::IsNullOrWhiteSpace($TargetSuffix) -and
  $canonicalDbxRecord.current -eq $true -and
  $canonicalDbxRecord.pe_verification.verified -eq $true
)
$canonicalCrxCurrent = (
  [string]::IsNullOrWhiteSpace($TargetSuffix) -and
  $canonicalCrxRecord.current -eq $true -and
  $canonicalCrxRecord.pe_verification.verified -eq $true
)
$canonicalArxCurrent = (
  [string]::IsNullOrWhiteSpace($TargetSuffix) -and
  $arxMode -eq 'canonical' -and
  $canonicalArxRecord.current -eq $true -and
  $canonicalArxRecord.pe_verification.verified -eq $true
)
$displayMembershipReady = (
  $Configuration -eq 'Release' -and
  $Platform -eq 'x64' -and
  $buildTarget -eq 'Rebuild' -and
  $gitState.available -eq $true -and
  $canonicalDbxCurrent -and
  $canonicalCrxCurrent -and
  $canonicalArxCurrent -and
  $snapshotStable
)
$manifestPath = Join-Path $bin 'native_build_manifest.json'
$manifest = [ordered]@{
  schema = 'ariadne.cad_os.native_build_manifest.v1'
  schema_version = 1
  claim_scope = $claimScope
  configuration = $Configuration
  platform = $Platform
  build_target = $buildTarget
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
      'Git checkout identity is UNKNOWN; the display-membership integrity bundle is not ready.'
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
$manifestVerification = Confirm-NativeBuildManifest -ManifestPath $manifestPath `
  -RequiredLeaves $requiredBuiltLeaves `
  -ExpectedClaimScope $claimScope `
  -ExpectedBuildTarget $buildTarget `
  -ExpectedConfiguration $Configuration `
  -ExpectedPlatform $Platform `
  -ExpectedSourceTreeDigest $sourceDigest
$manifestVerification['schema'] = $manifest.schema
$manifestVerification['source_input_count'] = $sourceInputs.Count
$manifestVerification['git'] = $gitState
$manifestVerification['build_recipe'] = $buildRecipeState
$manifestVerification['snapshot_stable'] = $snapshotStable
$manifestVerification['source_snapshot'] = $manifest.build_snapshot
$manifestVerification['display_membership_ready'] = [bool]$displayMembershipReady
$manifestVerification['canonical_arx_current'] = [bool]$canonicalArxCurrent
$manifestSha256 = $manifestVerification.manifest_sha256

# prebuilt/<version> is consumed before src/bin. Publish the exact canonical
# DBX/CRX/ARX set only after the source post-snapshot and finalized build
# manifest both verify. The deployment manifest is committed last.
$prebuiltDeployed = @()
$prebuiltDeployment = [ordered]@{
  committed = $false
  reason = 'This invocation is not eligible for canonical prebuilt publication.'
}
$canonicalDeployLeaves = @('Ariadne.AcadNativeDbx.dbx', 'Ariadne.AcadNative.crx', 'Ariadne.AcadNative.arx')
$prebuiltEligible = (
  -not $isolatedBuild -and
  [string]::IsNullOrWhiteSpace($TargetSuffix) -and
  $Configuration -eq 'Release' -and
  $Platform -eq 'x64' -and
  $buildTarget -eq 'Rebuild' -and
  $gitState.available -eq $true -and
  $canonicalDbxCurrent -and
  $canonicalCrxCurrent -and
  $canonicalArxCurrent -and
  $manifestVerification.verified -eq $true
)
if (-not $isolatedBuild -and [string]::IsNullOrWhiteSpace($TargetSuffix)) {
  $prebuiltRoot = Join-Path $RouterHome 'prebuilt'
  if (Test-Path -LiteralPath $prebuiltRoot -PathType Container) {
    if ($prebuiltEligible) {
      $deployDir = Get-ChildItem -LiteralPath $prebuiltRoot -Directory |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'Ariadne.AcadNative.crx') } |
        Sort-Object Name -Descending | Select-Object -First 1
      if (-not $deployDir) {
        throw 'Canonical Release|x64 Rebuild is ready, but no prebuilt deployment directory exists.'
      }
      $prebuiltDeployment = Publish-NativePrebuiltSet -BinDir $bin -DeployDir $deployDir.FullName `
        -Leaves $canonicalDeployLeaves `
        -BuildManifestVerification $manifestVerification `
        -SourceSnapshot $nativeBuildSnapshotBefore
      $prebuiltDeployed = @($canonicalDeployLeaves | ForEach-Object { Join-Path $deployDir.FullName $_ })
    } else {
      $prebuiltDeployment.reason = 'Canonical DBX/CRX/ARX Release|x64 Rebuild set is not current and verified; prebuilt was left unchanged.'
    }
  } else {
    $prebuiltDeployment.reason = 'No prebuilt root exists; no deployment was attempted.'
  }
}

[ordered]@{
  status = 'ok'
  msbuild = $msbuild
  arx_relink_mode = $arxMode
  arx_versioned_name = $arxVersionedName
  arx_lock_note = if ($arxMode -eq 'versioned_lock_bypass') {
    'Canonical .arx is held by a running AutoCAD; relinked to a versioned target. The canonical ARX is NOT current for the display-membership integrity bundle. AutoCAD was NOT killed.'
  } else { 'Canonical .arx relinked normally.' }
  projects = @($dbxProj, $crxProj, $arxProj)
  prebuilt_deployed = $prebuiltDeployed
  prebuilt_deployment = $prebuiltDeployment
  artifacts = @($artifactRecords | ForEach-Object {
    $path = Join-Path $bin $_.leaf
    [ordered]@{
      path = $path
      leaf = $_.leaf
      exists = $_.exists
      sha256 = $_.sha256
      bytes = $_.bytes
      current = $_.current
      pe_verification = $_.pe_verification
    }
  })
  build_manifest_path = $manifestPath
  build_manifest_sha256 = $manifestSha256
  build_manifest_verification = $manifestVerification
} | ConvertTo-Json -Depth 12
