param(
  [string]$Configuration = 'Release',
  [string]$Platform = 'x64',
  [string]$RouterHome = '',
  [string]$OutputRoot = '',
  [string]$TargetSuffix = '',
  [string]$MSBuildExe = ''
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
  if (-not [string]::IsNullOrWhiteSpace($MSBuildExe)) {
    if (-not (Test-Path -LiteralPath $MSBuildExe -PathType Leaf)) {
      throw "Explicit MSBuild executable is missing: $MSBuildExe"
    }
    return (Resolve-Path -LiteralPath $MSBuildExe).Path
  }
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

function ConvertTo-CanonicalNativeSourceBytes {
  param([byte[]]$Raw)
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

function Get-CanonicalNativeSourceBytes {
  param([string]$Path)
  [byte[]]$raw = [System.IO.File]::ReadAllBytes($Path)
  Write-Output -NoEnumerate (ConvertTo-CanonicalNativeSourceBytes -Raw $raw)
}

function Read-NativeBuildInputStreamBytes {
  param([System.IO.FileStream]$Stream)
  $Stream.Position = 0
  $buffer = New-Object System.IO.MemoryStream
  try {
    $Stream.CopyTo($buffer)
    [byte[]]$raw = $buffer.ToArray()
  } finally {
    $buffer.Dispose()
  }
  if ([int64]$raw.Length -ne [int64]$Stream.Length) {
    throw "Native build input changed while its held handle was read: $($Stream.Name)"
  }
  Write-Output -NoEnumerate $raw
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

function Get-NativeSourcePathRecords {
  $roots = @(
    (Join-Path $RouterHome 'src\Ariadne.AcadNative'),
    (Join-Path $RouterHome 'src\Ariadne.AcadNativeDbx')
  )
  $paths = @()
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
        $paths += [pscustomobject][ordered]@{
          path = $relative
          full_path = $entry.FullName
        }
      }
    }
  }
  $paths = @($paths | Sort-Object @{ Expression = { $_.path.ToLowerInvariant() } }, @{ Expression = { $_.path } })
  if ($paths.Count -eq 0) { throw 'Native source input inventory is empty.' }
  return $paths
}

function Get-NativeSourceState {
  $canonicalInputs = @()
  $compilationInputs = @()
  $authorityInputs = @()
  foreach ($record in @(Get-NativeSourcePathRecords)) {
    [byte[]]$raw = [System.IO.File]::ReadAllBytes($record.full_path)
    [byte[]]$canonical = ConvertTo-CanonicalNativeSourceBytes -Raw $raw
    $canonicalInputs += [ordered]@{
      path = $record.path
      sha256 = Get-Sha256Bytes -Bytes $canonical
      bytes = [int64]$canonical.Length
    }
    $compilationInputs += [ordered]@{
      path = $record.path
      sha256 = Get-Sha256Bytes -Bytes $canonical
      bytes = [int64]$canonical.Length
    }
    $authorityInputs += [pscustomobject][ordered]@{
      kind = 'source'
      path = $record.path
      raw = $raw
    }
  }
  return [pscustomobject][ordered]@{
    canonical_inputs = $canonicalInputs
    compilation_inputs = $compilationInputs
    authority_inputs = $authorityInputs
  }
}

function Get-NativeSourceInputs {
  return @((Get-NativeSourceState).canonical_inputs)
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

function Invoke-NativeGitText {
  param([string[]]$Arguments)
  $git = Get-Command git -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if (-not $git) { throw 'git executable is unavailable.' }

  # Git's repository-selection environment variables take precedence over -C.
  # Run every producer observation with a closed, restored command environment
  # so inherited GIT_DIR/GIT_WORK_TREE/config cannot redirect provenance to a
  # clean decoy repository.
  $savedGitEnvironment = [ordered]@{}
  foreach ($entry in @(Get-ChildItem Env:)) {
    if ($entry.Name.StartsWith('GIT_', [System.StringComparison]::OrdinalIgnoreCase)) {
      $savedGitEnvironment[$entry.Name] = $entry.Value
    }
  }
  try {
    foreach ($name in @($savedGitEnvironment.Keys)) {
      Remove-Item -LiteralPath ("Env:$name") -ErrorAction SilentlyContinue
    }
    $env:GIT_OPTIONAL_LOCKS = '0'
    $env:GIT_NO_REPLACE_OBJECTS = '1'
    $env:GIT_CONFIG_NOSYSTEM = '1'
    $env:GIT_CONFIG_GLOBAL = 'NUL'
    $env:GIT_TERMINAL_PROMPT = '0'
    $output = & $git.Source --no-optional-locks `
      -c 'core.fsmonitor=false' `
      -c 'core.autocrlf=true' `
      -c "safe.directory=$RouterHome" `
      -C $RouterHome @Arguments 2>$null
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { throw "git command failed with exit $exitCode." }
    return (@($output) -join "`n")
  } finally {
    foreach ($entry in @(Get-ChildItem Env:)) {
      if ($entry.Name.StartsWith('GIT_', [System.StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath ("Env:$($entry.Name)") -ErrorAction SilentlyContinue
      }
    }
    foreach ($name in @($savedGitEnvironment.Keys)) {
      Set-Item -LiteralPath ("Env:$name") -Value $savedGitEnvironment[$name]
    }
  }
}

function Get-GitBlobObjectId {
  param([byte[]]$Bytes, [string]$ObjectFormat)
  $algorithm = if ($ObjectFormat -ceq 'sha1') {
    [System.Security.Cryptography.SHA1]::Create()
  } elseif ($ObjectFormat -ceq 'sha256') {
    [System.Security.Cryptography.SHA256]::Create()
  } else {
    throw "Unsupported Git object format: $ObjectFormat"
  }
  $stream = New-Object System.IO.MemoryStream
  try {
    [byte[]]$header = [System.Text.Encoding]::ASCII.GetBytes("blob $($Bytes.Length)`0")
    $stream.Write($header, 0, $header.Length)
    $stream.Write($Bytes, 0, $Bytes.Length)
    $stream.Position = 0
    return -join ($algorithm.ComputeHash($stream) | ForEach-Object { $_.ToString('x2') })
  } finally {
    $algorithm.Dispose()
    $stream.Dispose()
  }
}

function Get-NativeTrackedSourcePaths {
  $records = Invoke-NativeGitText @(
    'ls-files', '-z', '--cached', '--',
    'src/Ariadne.AcadNative',
    'src/Ariadne.AcadNativeDbx'
  )
  $paths = @()
  foreach ($record in @($records -split "`0")) {
    if ([string]::IsNullOrEmpty($record)) { continue }
    $path = $record.Replace('\', '/')
    $inScope = (
      $path.StartsWith('src/Ariadne.AcadNative/', [System.StringComparison]::Ordinal) -or
      $path.StartsWith('src/Ariadne.AcadNativeDbx/', [System.StringComparison]::Ordinal)
    )
    if (-not $inScope) { throw "Git returned an out-of-scope native path: $path" }
    $isBuildOutput = $false
    foreach ($part in @($path -split '/')) {
      if (Test-NativeBuildOutputPart $part) { $isBuildOutput = $true; break }
    }
    if (-not $isBuildOutput) { $paths += $path }
  }
  $paths = @($paths | Sort-Object @{ Expression = { $_.ToLowerInvariant() } }, @{ Expression = { $_ } })
  if ($paths.Count -eq 0 -or @($paths | Select-Object -Unique).Count -ne $paths.Count) {
    throw 'Tracked native source inventory is empty or duplicated.'
  }
  return $paths
}

function Get-NativeCapturedHeadAuthority {
  param([object[]]$Inputs, [string]$GitHead)
  $result = [ordered]@{
    source_inventory_authoritative = $false
    captured_inputs_match_head = $false
    tracked_source_path_count = 0
    tracked_source_inventory_sha256 = 'UNKNOWN'
    reason = 'Native source authority was not verified.'
  }
  try {
    if ($GitHead -notmatch '^(?:[0-9a-f]{40}|[0-9a-f]{64})$') {
      throw 'Exact Git HEAD is unavailable.'
    }
    $trackedPaths = @(Get-NativeTrackedSourcePaths)
    $capturedSourcePaths = @($Inputs | Where-Object { [string]$_.kind -ceq 'source' } |
      ForEach-Object { [string]$_.path } |
      Sort-Object @{ Expression = { $_.ToLowerInvariant() } }, @{ Expression = { $_ } })
    $inventoryExact = $capturedSourcePaths.Count -eq $trackedPaths.Count
    if ($inventoryExact) {
      for ($index = 0; $index -lt $trackedPaths.Count; $index++) {
        if ([string]$capturedSourcePaths[$index] -cne [string]$trackedPaths[$index]) {
          $inventoryExact = $false
          break
        }
      }
    }
    $inventoryBuilder = New-Object System.Text.StringBuilder
    foreach ($path in $trackedPaths) {
      [void]$inventoryBuilder.Append($path)
      [void]$inventoryBuilder.Append([char]0)
      [void]$inventoryBuilder.Append("`n")
    }
    $result.tracked_source_path_count = $trackedPaths.Count
    $result.tracked_source_inventory_sha256 = Get-Sha256Text $inventoryBuilder.ToString()
    $result.source_inventory_authoritative = $inventoryExact
    if (-not $inventoryExact) {
      $result.reason = 'Captured native inputs are not exactly the cached tracked-only Git inventory.'
      return [pscustomobject]$result
    }

    $objectFormat = (Invoke-NativeGitText @('rev-parse', '--show-object-format')).Trim()
    $allMatch = $true
    foreach ($input in @($Inputs)) {
      $path = [string]$input.path
      [byte[]]$raw = [byte[]]$input.raw
      [byte[]]$canonical = ConvertTo-CanonicalNativeSourceBytes -Raw $raw
      $capturedOid = Get-GitBlobObjectId -Bytes $canonical -ObjectFormat $objectFormat
      $headOid = (Invoke-NativeGitText @('rev-parse', '--verify', "${GitHead}:$path")).Trim()
      if ($headOid -notmatch '^(?:[0-9a-f]{40}|[0-9a-f]{64})$' -or $capturedOid -cne $headOid) {
        $allMatch = $false
        break
      }
    }
    $result.captured_inputs_match_head = $allMatch
    $result.reason = if ($allMatch) {
      'Captured canonical source and build-recipe bytes match exact HEAD blobs.'
    } else {
      'At least one captured canonical input does not match its exact HEAD blob.'
    }
    return [pscustomobject]$result
  } catch {
    $result.reason = "Native source authority verification failed: $($_.Exception.Message)"
    return [pscustomobject]$result
  }
}

function Get-HiddenNativeIndexFlagCount {
  param([string]$Records)
  $count = 0
  foreach ($record in @($Records -split "`0")) {
    if ([string]::IsNullOrEmpty($record)) { continue }
    $tag = [int][char]$record[0]
    if ($record[0] -ceq 'S' -or ($tag -ge [int][char]'a' -and $tag -le [int][char]'z')) {
      $count++
    }
  }
  return $count
}

function Get-NativeSourceGitState {
  $unknown = [ordered]@{
    available = $false
    head = 'UNKNOWN'
    native_source_dirty = 'UNKNOWN'
    native_source_status_sha256 = 'UNKNOWN'
    index_visibility_sha256 = 'UNKNOWN'
    checks = [ordered]@{
      git_available = $false
      repo_root_exact = $false
      index_visibility_unmodified = 'UNKNOWN'
      start_end_consistent = $false
    }
  }
  try {
    $topLevel = (Invoke-NativeGitText @('rev-parse', '--show-toplevel')).Trim()
    $resolvedTopLevel = (Resolve-Path -LiteralPath $topLevel).Path
    if (-not [string]::Equals(
        $resolvedTopLevel,
        $RouterHome,
        [System.StringComparison]::OrdinalIgnoreCase
      )) {
      return $unknown
    }
    $statusArgs = @(
      'status', '--porcelain=v1', '--untracked-files=all', '--',
      'src/Ariadne.AcadNative',
      'src/Ariadne.AcadNativeDbx'
    )
    $visibilityArgs = @(
      'ls-files', '-v', '-z', '--',
      'src/Ariadne.AcadNative',
      'src/Ariadne.AcadNativeDbx'
    )
    $headStart = (Invoke-NativeGitText @('rev-parse', 'HEAD')).Trim()
    $statusStart = @((Invoke-NativeGitText $statusArgs) -split "`r?`n") |
      Where-Object { Test-NativeSourceStatusLine ([string]$_) }
    $statusStartText = @($statusStart) -join "`n"
    $visibilityStart = Invoke-NativeGitText $visibilityArgs
    $headEnd = (Invoke-NativeGitText @('rev-parse', 'HEAD')).Trim()
    $statusEnd = @((Invoke-NativeGitText $statusArgs) -split "`r?`n") |
      Where-Object { Test-NativeSourceStatusLine ([string]$_) }
    $statusEndText = @($statusEnd) -join "`n"
    $visibilityEnd = Invoke-NativeGitText $visibilityArgs
    if ($headStart -notmatch '^[0-9a-f]{40}$' -or $headEnd -notmatch '^[0-9a-f]{40}$') {
      return $unknown
    }
    $consistent = (
      $headStart -ceq $headEnd -and
      $statusStartText -ceq $statusEndText -and
      $visibilityStart -ceq $visibilityEnd
    )
    if (-not $consistent) { return $unknown }
    $visibilityUnmodified = (Get-HiddenNativeIndexFlagCount $visibilityStart) -eq 0
    return [ordered]@{
      available = $true
      head = $headStart
      native_source_dirty = (-not [string]::IsNullOrEmpty($statusStartText))
      native_source_status_sha256 = Get-Sha256Text $statusStartText
      index_visibility_sha256 = Get-Sha256Text $visibilityStart
      checks = [ordered]@{
        git_available = $true
        repo_root_exact = $true
        index_visibility_unmodified = $visibilityUnmodified
        start_end_consistent = $true
      }
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

function Open-NativeBuildInputLease {
  $sourcePaths = @(Get-NativeSourcePathRecords)
  $recipeRelative = 'tools/build_native_acad.ps1'
  $recipePath = Join-Path $RouterHome ($recipeRelative -replace '/', '\\')
  if (-not (Test-Path -LiteralPath $recipePath -PathType Leaf)) {
    throw "Native build recipe missing: $recipePath"
  }
  $recipeItem = Get-Item -LiteralPath $recipePath -Force
  if (($recipeItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw "Native build recipe is a reparse point: $recipePath"
  }

  $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\', '/')
  $mirrorLeaf = '.ariadne-native-source-' + [guid]::NewGuid().ToString('N')
  $mirrorRoot = Join-Path $tempRoot $mirrorLeaf
  [System.IO.Directory]::CreateDirectory($mirrorRoot) | Out-Null
  $handles = New-Object 'System.Collections.Generic.List[System.IO.FileStream]'
  $captures = @()
  $mirrorCaptures = @()
  $leaseReady = $false
  try {
    # Open the complete requested set before reading any bytes.  FileShare.Read
    # lets the compiler read but denies writers and delete/rename replacement
    # until publication completes.
    foreach ($record in $sourcePaths) {
      $stream = [System.IO.File]::Open(
        $record.full_path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read
      )
      [void]$handles.Add($stream)
      $captures += [pscustomobject][ordered]@{
        kind = 'source'
        path = $record.path
        full_path = $record.full_path
        stream = $stream
      }
    }
    $recipeStream = [System.IO.File]::Open(
      $recipePath,
      [System.IO.FileMode]::Open,
      [System.IO.FileAccess]::Read,
      [System.IO.FileShare]::Read
    )
    [void]$handles.Add($recipeStream)
    $captures += [pscustomobject][ordered]@{
      kind = 'recipe'
      path = $recipeRelative
      full_path = $recipePath
      stream = $recipeStream
    }

    $sourceInputs = @()
    $compilationInputs = @()
    $authorityInputs = @()
    $recipeState = $null
    foreach ($capture in $captures) {
      [byte[]]$raw = Read-NativeBuildInputStreamBytes -Stream $capture.stream
      [byte[]]$canonical = ConvertTo-CanonicalNativeSourceBytes -Raw $raw
      $authorityInputs += [pscustomobject][ordered]@{
        kind = $capture.kind
        path = $capture.path
        raw = $raw
      }
      $mirrorPath = Join-Path $mirrorRoot ($capture.path -replace '/', '\\')
      $mirrorParent = [System.IO.Path]::GetDirectoryName($mirrorPath)
      [System.IO.Directory]::CreateDirectory($mirrorParent) | Out-Null
      [System.IO.File]::WriteAllBytes($mirrorPath, $canonical)
      $mirrorStream = [System.IO.File]::Open(
        $mirrorPath,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read
      )
      [void]$handles.Add($mirrorStream)
      $mirrorCaptures += [pscustomobject][ordered]@{
        kind = $capture.kind
        path = $capture.path
        stream = $mirrorStream
        expected_sha256 = Get-Sha256Bytes -Bytes $canonical
        expected_bytes = [int64]$canonical.Length
      }
      [System.IO.File]::SetAttributes($mirrorPath, [System.IO.FileAttributes]::ReadOnly)
      if ($capture.kind -ceq 'source') {
        $sourceInputs += [ordered]@{
          path = $capture.path
          sha256 = Get-Sha256Bytes -Bytes $canonical
          bytes = [int64]$canonical.Length
        }
        $compilationInputs += [ordered]@{
          path = $capture.path
          sha256 = Get-Sha256Bytes -Bytes $canonical
          bytes = [int64]$canonical.Length
        }
      } else {
        $recipeState = [ordered]@{
          path = $capture.path
          sha256 = Get-Sha256Bytes -Bytes $canonical
        }
      }
    }
    $gitState = Get-NativeSourceGitState
    $sourceAuthority = Get-NativeCapturedHeadAuthority `
      -Inputs $authorityInputs `
      -GitHead ([string]$gitState.head)
    $snapshot = [ordered]@{
      source_tree = [ordered]@{
        algorithm = 'sha256'
        canonicalization = 'crlf_to_lf_unless_nul'
        digest = Get-NativeSourceDigest $sourceInputs
        inputs = $sourceInputs
      }
      compilation_tree = [ordered]@{
        algorithm = 'sha256'
        byte_representation = 'canonical_lf_unless_nul_mirror_bytes'
        digest = Get-NativeSourceDigest $compilationInputs
        inputs = $compilationInputs
      }
      git = $gitState
      source_authority = $sourceAuthority
      build_recipe = $recipeState
    }
    $lease = [pscustomobject][ordered]@{
      snapshot = $snapshot
      mirror_root = $mirrorRoot
      temp_root = $tempRoot
      handles = $handles.ToArray()
      mirror_captures = $mirrorCaptures
    }
    $leaseReady = $true
    return $lease
  } finally {
    if (-not $leaseReady) {
      Close-NativeBuildInputLease -Lease ([pscustomobject][ordered]@{
        mirror_root = $mirrorRoot
        temp_root = $tempRoot
        handles = $handles.ToArray()
      })
    }
  }
}

function Assert-NativeBuildMirrorStable {
  param([object]$Lease)
  if ($null -eq $Lease -or @($Lease.mirror_captures).Count -eq 0) {
    throw 'Native build mirror has no held input captures.'
  }
  $actualCompilationInputs = @()
  $recipeCount = 0
  foreach ($capture in @($Lease.mirror_captures)) {
    [byte[]]$raw = Read-NativeBuildInputStreamBytes -Stream $capture.stream
    $actualSha256 = Get-Sha256Bytes -Bytes $raw
    if ([int64]$raw.Length -ne [int64]$capture.expected_bytes -or
        $actualSha256 -cne [string]$capture.expected_sha256) {
      throw "Native build mirror input changed after capture: $($capture.path)"
    }
    if ([string]$capture.kind -ceq 'source') {
      $actualCompilationInputs += [ordered]@{
        path = [string]$capture.path
        sha256 = $actualSha256
        bytes = [int64]$raw.Length
      }
    } elseif ([string]$capture.kind -ceq 'recipe') {
      $recipeCount++
    } else {
      throw "Native build mirror contains an unknown input kind: $($capture.kind)"
    }
  }
  if ($recipeCount -ne 1) {
    throw "Native build mirror must contain exactly one build recipe; found $recipeCount."
  }
  $expectedInputsJson = @($Lease.snapshot.compilation_tree.inputs) | ConvertTo-Json -Depth 12 -Compress
  $actualInputsJson = @($actualCompilationInputs) | ConvertTo-Json -Depth 12 -Compress
  $actualDigest = Get-NativeSourceDigest $actualCompilationInputs
  if ($actualInputsJson -cne $expectedInputsJson -or
      $actualDigest -cne [string]$Lease.snapshot.compilation_tree.digest) {
    throw 'Native build mirror canonical compilation inputs do not match the starting snapshot.'
  }
  return $true
}

function Close-NativeBuildInputLease {
  param([object]$Lease)
  if ($null -eq $Lease) { return }
  foreach ($handle in @($Lease.handles)) {
    if ($null -ne $handle) { $handle.Dispose() }
  }
  if (-not [System.IO.Directory]::Exists([string]$Lease.mirror_root)) { return }
  $resolvedMirror = (Resolve-Path -LiteralPath $Lease.mirror_root).Path
  $resolvedTemp = (Resolve-Path -LiteralPath $Lease.temp_root).Path.TrimEnd('\', '/')
  $mirrorParent = [System.IO.Path]::GetDirectoryName($resolvedMirror).TrimEnd('\', '/')
  $mirrorLeaf = [System.IO.Path]::GetFileName($resolvedMirror)
  $mirrorItem = Get-Item -LiteralPath $resolvedMirror -Force
  $isReparse = (($mirrorItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)
  if (-not [string]::Equals($mirrorParent, $resolvedTemp, [System.StringComparison]::OrdinalIgnoreCase) -or
      $mirrorLeaf -notmatch '^\.ariadne-native-source-[0-9a-f]{32}$' -or
      $isReparse) {
    throw "Refusing recursive native mirror cleanup outside verified TEMP: $resolvedMirror"
  }
  foreach ($file in @(Get-ChildItem -LiteralPath $resolvedMirror -File -Recurse -Force)) {
    $file.Attributes = [System.IO.FileAttributes]::Normal
  }
  [System.IO.Directory]::Delete($resolvedMirror, $true)
}

function Get-NativeBuildSnapshot {
  $sourceState = Get-NativeSourceState
  $inputs = @($sourceState.canonical_inputs)
  $compilationInputs = @($sourceState.compilation_inputs)
  $gitState = Get-NativeSourceGitState
  $recipeRelative = 'tools/build_native_acad.ps1'
  [byte[]]$recipeRaw = [System.IO.File]::ReadAllBytes((Join-Path $RouterHome 'tools\build_native_acad.ps1'))
  $authorityInputs = @($sourceState.authority_inputs) + @(
    [pscustomobject][ordered]@{
      kind = 'recipe'
      path = $recipeRelative
      raw = $recipeRaw
    }
  )
  $sourceAuthority = Get-NativeCapturedHeadAuthority `
    -Inputs $authorityInputs `
    -GitHead ([string]$gitState.head)
  return [ordered]@{
    source_tree = [ordered]@{
      algorithm = 'sha256'
      canonicalization = 'crlf_to_lf_unless_nul'
      digest = Get-NativeSourceDigest $inputs
      inputs = $inputs
    }
    compilation_tree = [ordered]@{
      algorithm = 'sha256'
      byte_representation = 'canonical_lf_unless_nul_mirror_bytes'
      digest = Get-NativeSourceDigest $compilationInputs
      inputs = $compilationInputs
    }
    git = $gitState
    source_authority = $sourceAuthority
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
    $characteristics = $reader.ReadUInt16()
    $verification.optional_header_bytes = [int]$optionalHeaderBytes
    if (($characteristics -band 0x2000) -eq 0) {
      $verification.reason = 'PE image is not marked as a DLL (IMAGE_FILE_DLL 0x2000).'
      return [pscustomobject]$verification
    }
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
    $verification.reason = 'MZ, PE, x64 machine, DLL characteristic, section table, and PE32+ optional header checks passed.'
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
  if (-not $exists) {
    return [ordered]@{
      leaf = $Leaf
      sha256 = 'UNKNOWN'
      bytes = [int64]0
      current = $Current
      exists = $false
      pe_verification = Get-NativePeVerificationFromBytes -Bytes ([byte[]]@())
    }
  }
  [byte[]]$bytes = [System.IO.File]::ReadAllBytes($path)
  return New-NativeArtifactRecordFromBytes -Leaf $Leaf -Bytes $bytes -Current $Current
}

function Get-NativePeVerificationFromBytes {
  param([byte[]]$Bytes)
  $verification = [ordered]@{
    verified = $false
    format = 'UNKNOWN'
    machine = 'UNKNOWN'
    minimum_bytes = [int64]512
    pe_header_offset = [int64]-1
    section_count = 0
    optional_header_bytes = 0
    reason = 'Artifact bytes were not inspected.'
  }
  if ([int64]$Bytes.Length -lt $verification.minimum_bytes) {
    $verification.reason = "Artifact is too small to be a native load module ($($Bytes.Length) bytes)."
    return [pscustomobject]$verification
  }
  $stream = $null
  $reader = $null
  try {
    $stream = New-Object System.IO.MemoryStream(,$Bytes)
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
    $characteristics = $reader.ReadUInt16()
    $verification.optional_header_bytes = [int]$optionalHeaderBytes
    if ($optionalHeaderBytes -lt 0xF0 -or ([int64]$peOffset + 24 + $optionalHeaderBytes) -gt [int64]$stream.Length) {
      $verification.reason = 'PE32+ optional header is truncated.'
      return [pscustomobject]$verification
    }
    if (($characteristics -band 0x2000) -eq 0) {
      $verification.reason = 'PE image is not marked as a DLL (IMAGE_FILE_DLL 0x2000).'
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
    $verification.reason = 'MZ, PE, x64 machine, DLL characteristic, section table, and PE32+ optional header checks passed.'
    return [pscustomobject]$verification
  } catch {
    $verification.reason = "PE inspection failed: $($_.Exception.Message)"
    return [pscustomobject]$verification
  } finally {
    if ($reader) { $reader.Dispose() }
    if ($stream) { $stream.Dispose() }
  }
}

function New-NativeArtifactRecordFromBytes {
  param([string]$Leaf, [byte[]]$Bytes, [bool]$Current)
  return [ordered]@{
    leaf = $Leaf
    sha256 = Get-Sha256Bytes -Bytes $Bytes
    bytes = [int64]$Bytes.Length
    current = $Current
    exists = $true
    pe_verification = Get-NativePeVerificationFromBytes -Bytes $Bytes
  }
}

function Open-NativeArtifactLease {
  param([string]$BinDir, [object[]]$Specs)
  if (-not (Test-Path -LiteralPath $BinDir -PathType Container)) {
    throw "Native build output directory missing: $BinDir"
  }
  $handles = New-Object 'System.Collections.Generic.List[System.IO.FileStream]'
  $captures = @()
  $complete = $false
  try {
    $seen = @{}
    foreach ($spec in @($Specs)) {
      $leaf = [string]$spec.leaf
      if ([System.IO.Path]::GetFileName($leaf) -cne $leaf -or $seen.ContainsKey($leaf)) {
        throw "Native artifact lease requires unique plain leaves: $leaf"
      }
      $seen[$leaf] = $true
      $path = Join-Path $BinDir $leaf
      if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        if ($spec.required -eq $true) { throw "Required native artifact is missing: $leaf" }
        $captures += [pscustomobject][ordered]@{ spec = $spec; stream = $null }
        continue
      }
      $item = Get-Item -LiteralPath $path -Force
      if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Native artifact is a reparse point: $path"
      }
      $stream = [System.IO.File]::Open(
        $path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read
      )
      [void]$handles.Add($stream)
      $captures += [pscustomobject][ordered]@{ spec = $spec; stream = $stream }
    }

    $records = @()
    $contents = [ordered]@{}
    foreach ($capture in $captures) {
      if ($null -eq $capture.stream) {
        $records += [ordered]@{
          leaf = [string]$capture.spec.leaf
          sha256 = 'UNKNOWN'
          bytes = [int64]0
          current = [bool]$capture.spec.current
          exists = $false
          pe_verification = Get-NativePeVerificationFromBytes -Bytes ([byte[]]@())
        }
        continue
      }
      [byte[]]$bytes = Read-NativeBuildInputStreamBytes -Stream $capture.stream
      $contents[[string]$capture.spec.leaf] = $bytes
      $records += New-NativeArtifactRecordFromBytes `
        -Leaf ([string]$capture.spec.leaf) `
        -Bytes $bytes `
        -Current ([bool]$capture.spec.current)
    }
    $lease = [pscustomobject][ordered]@{
      records = $records
      contents = $contents
      handles = $handles.ToArray()
    }
    $complete = $true
    return $lease
  } finally {
    if (-not $complete) {
      foreach ($handle in @($handles.ToArray())) { $handle.Dispose() }
    }
  }
}

function Close-NativeArtifactLease {
  param([object]$Lease)
  if ($null -eq $Lease) { return }
  foreach ($handle in @($Lease.handles)) {
    if ($null -ne $handle) { $handle.Dispose() }
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
    [string]$ExpectedSourceTreeDigest,
    [string]$ExpectedCompilationTreeDigest
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
  if ([string]$document.source_tree.algorithm -cne 'sha256' -or
      [string]$document.source_tree.canonicalization -cne 'crlf_to_lf_unless_nul' -or
      [string]$document.source_tree.digest -cne $ExpectedSourceTreeDigest) {
    throw 'Native build manifest source-tree digest does not match the post-build snapshot.'
  }
  if ([string]$document.compilation_tree.algorithm -cne 'sha256' -or
      [string]$document.compilation_tree.byte_representation -cne 'canonical_lf_unless_nul_mirror_bytes' -or
      [string]$document.compilation_tree.digest -cne $ExpectedCompilationTreeDigest) {
    throw 'Native build manifest does not identify the canonical bytes compiled from the immutable mirror.'
  }
  if ($document.build_snapshot.exact_match -ne $true) {
    throw 'Native build manifest does not record an exact pre/post source snapshot match.'
  }
  if ([string]$document.build_snapshot.input_mode -cne 'immutable_starting_snapshot_mirror' -or
      [string]$document.source_provenance.compilation_input -cne 'immutable_starting_snapshot_mirror') {
    throw 'Native build manifest does not bind compilation to the immutable starting source mirror.'
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
    compilation_tree_digest = $ExpectedCompilationTreeDigest
    artifacts = $verifiedArtifacts
  }
}

function Confirm-NativeDeploymentManifest {
  param(
    [string]$ManifestPath,
    [string[]]$RequiredLeaves,
    [string]$ExpectedSourceTreeDigest,
    [object[]]$ExpectedSourceInputs,
    [string]$ExpectedCompilationTreeDigest,
    [object[]]$ExpectedCompilationInputs,
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
  $expectedSourceInputsJson = @($ExpectedSourceInputs) | ConvertTo-Json -Depth 12 -Compress
  $observedSourceInputsJson = @($document.source_tree.inputs) | ConvertTo-Json -Depth 12 -Compress
  $expectedCompilationInputsJson = @($ExpectedCompilationInputs) | ConvertTo-Json -Depth 12 -Compress
  $observedCompilationInputsJson = @($document.compilation_tree.inputs) | ConvertTo-Json -Depth 12 -Compress
  if ([string]$document.source_tree.algorithm -cne 'sha256' -or
      [string]$document.source_tree.canonicalization -cne 'crlf_to_lf_unless_nul' -or
      [string]$document.source_tree.digest -cne $ExpectedSourceTreeDigest -or
      $observedSourceInputsJson -cne $expectedSourceInputsJson -or
      [string]$document.source_tree_digest -cne $ExpectedSourceTreeDigest -or
      [string]$document.compilation_tree.algorithm -cne 'sha256' -or
      [string]$document.compilation_tree.byte_representation -cne 'canonical_lf_unless_nul_mirror_bytes' -or
      [string]$document.compilation_tree.digest -cne $ExpectedCompilationTreeDigest -or
      $observedCompilationInputsJson -cne $expectedCompilationInputsJson -or
      [string]$document.compilation_tree_digest -cne $ExpectedCompilationTreeDigest -or
      [string]$document.build_recipe.path -cne 'tools/build_native_acad.ps1' -or
      [string]$document.build_recipe.sha256 -cne $ExpectedBuildRecipeSha256) {
    throw 'Native deployment marker does not bind to the exact verified source inventory and build recipe.'
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
    [object]$SourceSnapshot,
    [object]$ArtifactContents
  )
  $canonicalLeaves = @('Ariadne.AcadNativeDbx.dbx', 'Ariadne.AcadNative.crx', 'Ariadne.AcadNative.arx')
  if (@(Compare-Object -ReferenceObject $canonicalLeaves -DifferenceObject @($Leaves)).Count -ne 0) {
    throw 'Prebuilt publication requires exactly the canonical DBX, CRX, and ARX leaves.'
  }
  if ($SourceSnapshot.git.available -ne $true) {
    throw 'Git checkout identity is unavailable; refusing prebuilt publication.'
  }
  if ($SourceSnapshot.git.native_source_dirty -ne $false -or
      $SourceSnapshot.source_authority.source_inventory_authoritative -ne $true -or
      $SourceSnapshot.source_authority.captured_inputs_match_head -ne $true) {
    throw 'Prebuilt publication requires clean inputs from the exact cached HEAD-tracked native inventory.'
  }
  if ($BuildManifestVerification.verified -ne $true -or
      [string]$BuildManifestVerification.claim_scope -cne 'release_build_integrity_bundle' -or
      [string]$BuildManifestVerification.build_target -cne 'Rebuild' -or
      [string]$BuildManifestVerification.configuration -cne 'Release' -or
      [string]$BuildManifestVerification.platform -cne 'x64') {
    throw 'Prebuilt publication requires a finalized Release|x64 Rebuild integrity manifest.'
  }
  foreach ($leaf in $Leaves) {
    if ($null -eq $ArtifactContents -or -not $ArtifactContents.Contains($leaf)) {
      throw "Prebuilt publication requires captured artifact bytes for $leaf."
    }
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
      $stagedPath = Join-Path $stagingRoot $leaf
      [byte[]]$capturedArtifactBytes = $ArtifactContents[$leaf]
      $stagedStream = [System.IO.File]::Open(
        $stagedPath,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
      )
      try {
        $stagedStream.Write($capturedArtifactBytes, 0, $capturedArtifactBytes.Length)
        $stagedStream.Flush($true)
      } finally {
        $stagedStream.Dispose()
      }
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
      source_tree = [ordered]@{
        algorithm = 'sha256'
        canonicalization = 'crlf_to_lf_unless_nul'
        digest = [string]$SourceSnapshot.source_tree.digest
        inputs = @($SourceSnapshot.source_tree.inputs)
      }
      source_tree_digest = [string]$BuildManifestVerification.source_tree_digest
      source_authority = $SourceSnapshot.source_authority
      compilation_tree = [ordered]@{
        algorithm = 'sha256'
        byte_representation = 'canonical_lf_unless_nul_mirror_bytes'
        digest = [string]$SourceSnapshot.compilation_tree.digest
        inputs = @($SourceSnapshot.compilation_tree.inputs)
      }
      compilation_tree_digest = [string]$BuildManifestVerification.compilation_tree_digest
      source_provenance = [ordered]@{
        compilation_input = 'immutable_starting_snapshot_mirror'
        mirror_ephemeral = $true
        limitations = @(
          [ordered]@{
            code = 'EXTERNAL_TOOLCHAIN_INPUTS_UNSEALED'
            scope = 'ObjectARX SDK headers/properties, Visual Studio targets, compiler, linker, and system libraries are external toolchain inputs and are not part of source_tree.'
          }
        )
      }
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
      -ExpectedSourceInputs @($SourceSnapshot.source_tree.inputs) `
      -ExpectedCompilationTreeDigest ([string]$SourceSnapshot.compilation_tree.digest) `
      -ExpectedCompilationInputs @($SourceSnapshot.compilation_tree.inputs) `
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
$nativeBuildInputLease = $null
$nativeArtifactLease = $null
try {
$nativeBuildInputLease = Open-NativeBuildInputLease
$nativeBuildSnapshotBefore = $nativeBuildInputLease.snapshot
$nativeBuildSnapshotBeforeDigest = Get-NativeBuildSnapshotDigest $nativeBuildSnapshotBefore
if ($nativeBuildSnapshotBefore.git.available -ne $true) {
  throw 'Git checkout identity is unavailable; refusing native build before MSBuild.'
}
if ($nativeBuildSnapshotBefore.git.checks.start_end_consistent -ne $true) {
  throw 'Git checkout changed during the starting observation; refusing native build before MSBuild.'
}
if ($nativeBuildSnapshotBefore.git.checks.index_visibility_unmodified -ne $true) {
  throw 'Git index visibility is weakened for native sources; refusing native build before MSBuild.'
}
Assert-NativeBuildMirrorStable -Lease $nativeBuildInputLease | Out-Null
$msbuild = Resolve-MSBuild
$dbxProj = Join-Path $nativeBuildInputLease.mirror_root 'src\Ariadne.AcadNativeDbx\Ariadne.AcadNativeDbx.dbx.vcxproj'
$crxProj = Join-Path $nativeBuildInputLease.mirror_root 'src\Ariadne.AcadNative\Ariadne.AcadNative.crx.vcxproj'
$arxProj = Join-Path $nativeBuildInputLease.mirror_root 'src\Ariadne.AcadNative\Ariadne.AcadNative.arx.vcxproj'

$isolatedBuild = -not [string]::IsNullOrWhiteSpace($OutputRoot)
if ($isolatedBuild) {
  $OutputRoot = (New-Item -ItemType Directory -Force -Path $OutputRoot).FullName
}
$nativeBuildOutputDir = if ($isolatedBuild) {
  Join-Path $OutputRoot "bin\$Platform\$Configuration"
} else {
  Join-Path $RouterHome "src\Ariadne.AcadNative\bin\$Platform\$Configuration"
}
$nativeBuildObjectRoot = Join-Path $nativeBuildInputLease.mirror_root '.build-obj'

function Build-Project {
  param([string]$Project, [string]$ObjectSubdir, [string]$TargetBase, [string[]]$ExtraProps = @())
  if (-not (Test-Path -LiteralPath $Project)) { throw "Native project missing: $Project" }
  $props = @(
    "/p:Configuration=$Configuration",
    "/p:Platform=$Platform",
    '/p:ImportDirectoryBuildProps=false',
    '/p:ImportDirectoryBuildTargets=false'
  )
  $outDir = $script:nativeBuildOutputDir + '\'
  $intDir = (Join-Path $script:nativeBuildObjectRoot "$ObjectSubdir\$Platform\$Configuration") + '\'
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

Assert-NativeBuildMirrorStable -Lease $nativeBuildInputLease | Out-Null
$nativeBuildSnapshotAfterMsbuild = Get-NativeBuildSnapshot
$nativeBuildSnapshotAfterMsbuildDigest = Get-NativeBuildSnapshotDigest $nativeBuildSnapshotAfterMsbuild
if (-not (Test-NativeBuildSnapshotEqual -Before $nativeBuildSnapshotBefore -After $nativeBuildSnapshotAfterMsbuild)) {
  throw 'Native source, native-source Git state, or build recipe changed while MSBuild ran; refusing to emit a provenance manifest.'
}

$bin = $nativeBuildOutputDir
if (-not (Test-Path -LiteralPath $bin -PathType Container)) {
  throw "Native build output directory missing: $bin"
}
$bin = (Resolve-Path -LiteralPath $bin).Path
$nativeBase = if ([string]::IsNullOrWhiteSpace($TargetSuffix)) { 'Ariadne.AcadNative' } else { "Ariadne.AcadNative$TargetSuffix" }
$dbxBase = if ([string]::IsNullOrWhiteSpace($TargetSuffix)) { 'Ariadne.AcadNativeDbx' } else { "Ariadne.AcadNativeDbx$TargetSuffix" }
$requiredBuiltLeaves = @("$dbxBase.dbx", "$nativeBase.crx")
if ($arxVersionedName) {
  $requiredBuiltLeaves += "$arxVersionedName.arx"
} else {
  $requiredBuiltLeaves += "$nativeBase.arx"
}
$artifactSpecs = @(
  [pscustomobject][ordered]@{ leaf = "$dbxBase.dbx"; current = $true; required = $true },
  [pscustomobject][ordered]@{ leaf = "$nativeBase.crx"; current = $true; required = $true },
  [pscustomobject][ordered]@{
    leaf = "$nativeBase.arx"
    current = ($arxMode -eq 'canonical')
    required = ($arxMode -eq 'canonical')
  }
)
if ($arxVersionedName) {
  $artifactSpecs += [pscustomobject][ordered]@{
    leaf = "$arxVersionedName.arx"
    current = $true
    required = $true
  }
}
$nativeArtifactLease = Open-NativeArtifactLease -BinDir $bin -Specs $artifactSpecs
$artifactRecords = @($nativeArtifactLease.records)
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
$compilationInputs = @($nativeBuildSnapshotBefore.compilation_tree.inputs)
$compilationDigest = $nativeBuildSnapshotBefore.compilation_tree.digest
$gitState = $nativeBuildSnapshotBefore.git
$sourceAuthority = $nativeBuildSnapshotBefore.source_authority
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
  $gitState.native_source_dirty -eq $false -and
  $sourceAuthority.source_inventory_authoritative -eq $true -and
  $sourceAuthority.captured_inputs_match_head -eq $true -and
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
    source_authority = $sourceAuthority
  }
  build_recipe = $buildRecipeState
  source_tree = [ordered]@{
    algorithm = 'sha256'
    canonicalization = 'crlf_to_lf_unless_nul'
    digest = $sourceDigest
    inputs = $sourceInputs
  }
  compilation_tree = [ordered]@{
    algorithm = 'sha256'
    byte_representation = 'canonical_lf_unless_nul_mirror_bytes'
    digest = $compilationDigest
    inputs = $compilationInputs
  }
  source_provenance = [ordered]@{
    compilation_input = 'immutable_starting_snapshot_mirror'
    mirror_ephemeral = $true
    limitations = @(
      [ordered]@{
        code = 'EXTERNAL_TOOLCHAIN_INPUTS_UNSEALED'
        scope = 'ObjectARX SDK headers/properties, Visual Studio targets, compiler, linker, and system libraries are external toolchain inputs and are not part of source_tree.'
      }
    )
  }
  build_snapshot = [ordered]@{
    input_mode = 'immutable_starting_snapshot_mirror'
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
  -ExpectedSourceTreeDigest $sourceDigest `
  -ExpectedCompilationTreeDigest $compilationDigest
$manifestVerification['schema'] = $manifest.schema
$manifestVerification['source_input_count'] = $sourceInputs.Count
$manifestVerification['git'] = $gitState
$manifestVerification['source_authority'] = $sourceAuthority
$manifestVerification['build_recipe'] = $buildRecipeState
$manifestVerification['snapshot_stable'] = $snapshotStable
$manifestVerification['source_snapshot'] = $manifest.build_snapshot
$manifestVerification['source_provenance'] = $manifest.source_provenance
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
  $gitState.native_source_dirty -eq $false -and
  $sourceAuthority.source_inventory_authoritative -eq $true -and
  $sourceAuthority.captured_inputs_match_head -eq $true -and
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
        -SourceSnapshot $nativeBuildSnapshotBefore `
        -ArtifactContents $nativeArtifactLease.contents
      $prebuiltDeployed = @($canonicalDeployLeaves | ForEach-Object { Join-Path $deployDir.FullName $_ })
    } else {
      $prebuiltDeployment.reason = if (
        $gitState.native_source_dirty -ne $false -or
        $sourceAuthority.source_inventory_authoritative -ne $true -or
        $sourceAuthority.captured_inputs_match_head -ne $true
      ) {
        'Canonical prebuilt publication requires clean inputs from the exact cached HEAD-tracked native inventory; prebuilt was left unchanged.'
      } else {
        'Canonical DBX/CRX/ARX Release|x64 Rebuild set is not current and verified; prebuilt was left unchanged.'
      }
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
} finally {
  Close-NativeArtifactLease -Lease $nativeArtifactLease
  Close-NativeBuildInputLease -Lease $nativeBuildInputLease
}
