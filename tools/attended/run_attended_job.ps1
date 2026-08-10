param(
  [Parameter(Mandatory=$true)][string]$StagedDwg,
  [Parameter(Mandatory=$true)][string]$Operation,
  [string]$JobArgsJson = '{}',
  [Parameter(Mandatory=$true)][string]$RunDir,
  [int]$TimeoutSec = 240,
  [string]$AcadExe = 'C:\Program Files\Autodesk\AutoCAD 2027\acad.exe',
  [string]$RouterHome = 'D:\dev\99_tools\autocad-sdk-router__wR_attended',
  [string]$NativeBinDir = ''
)
$ErrorActionPreference = 'Stop'
# Wave-R attended lane: ONE-SHOT native job runner hosted in a DEDICATED, disposable
# acad.exe (never attaches to a pre-existing session) instead of accoreconsole.exe.
# Exists because a handful of native write ops (rasterimage/wipeout/hatch/mpolygon)
# need demand-loaded AutoCAD engine modules (ISM/raster, hatch area engine) that
# accoreconsole does not load; full acad.exe has them. Drives the SAME one-shot
# ARIADNE_NATIVE_JOB_ARGS env-file channel the headless coreconsole lane proved
# (docs/LIVE_JOB_ARGUMENT_CONTRACT.md), reusing the M07B attended-launch pattern
# (tools/attended/run_attended_m07b.ps1): dedicated PID and staged-doc-only.
# Mutating operations QSAVE before QUIT; declared read-only operations never save.
#
# Security scoping (SECURELOAD/TRUSTEDPATHS): M07B set these to load its own ARX
# module but never restored them, leaving the launched profile permanently weakened.
# This script reads the CURRENT values from INSIDE the same AutoCAD session via
# AutoLISP getvar, sets them for the duration of the job only, then restores the
# ORIGINAL values before QUIT -- both before/after values are logged to disk so the
# caller can prove nothing was left changed.
#
# TimeoutSec default is generous (240s, not the ~60-90s a lone acad.exe launch
# normally needs) because this wave's own live runs shared the box with a dozen+
# other concurrent CAD-OS agent workloads (see build_log.md) -- real startup time
# under that contention exceeded a tighter first-attempt budget.

$t0 = Get-Date
function Log([string]$msg) { Write-Output ("[{0,6:N1}s] {1}" -f ((Get-Date) - $t0).TotalSeconds, $msg) }
function FS([string]$p) { $p -replace '\\','/' }
function WriteJsonAtomic($obj, [string]$path) {
  # Keep every receipt small, serialize it once, flush it, then atomically
  # rename it.  Do not use a pipeline into Set-Content/Move-Item here: the
  # caller's finalization path must not retain a large native job_out object or
  # a provider pipeline after the native process has already exited.
  $tmp = "$path.$([guid]::NewGuid().ToString('N')).tmp"
  $stream = $null
  try {
    $json = $obj | ConvertTo-Json -Depth 12 -Compress
    $bytes = (New-Object System.Text.UTF8Encoding($false)).GetBytes($json + [Environment]::NewLine)
    $stream = [System.IO.File]::Open(
      $tmp,
      [System.IO.FileMode]::CreateNew,
      [System.IO.FileAccess]::Write,
      [System.IO.FileShare]::None
    )
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Flush($true)
    $stream.Dispose()
    $stream = $null
    if ([System.IO.File]::Exists($path)) {
      [System.IO.File]::Replace($tmp, $path, $null)
    } else {
      [System.IO.File]::Move($tmp, $path)
    }
  } finally {
    if ($null -ne $stream) { $stream.Dispose() }
    if (Test-Path -LiteralPath $tmp) {
      Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
  }
}
function WriteJson($obj, $path) { WriteJsonAtomic $obj $path }

function New-ProcessIdentity($process) {
  # A PID is only one part of the identity.  StartTime is intentionally read
  # here, before any launch/cleanup decision, so an access failure cannot be
  # mistaken for a process that is absent or safe to terminate.
  if ($null -eq $process) { return $null }
  $processId = 0
  $processName = $null
  $startTimeUtc = $null
  try { $processId = [int]$process.Id } catch { return $null }
  try { $processName = [string]$process.ProcessName } catch { return $null }
  try { $startTimeUtc = $process.StartTime.ToUniversalTime().ToString('o') } catch { return $null }
  if ($processId -le 0 -or [string]::IsNullOrWhiteSpace($processName) -or
      [string]::IsNullOrWhiteSpace($startTimeUtc)) { return $null }
  return [ordered]@{
    pid = $processId
    process_name = $processName
    start_time_utc = $startTimeUtc
    known = $true
    identity_known = $true
  }
}

function Same-ProcessIdentity($expected, $current) {
  if ($null -eq $expected -or $null -eq $current) { return $false }
  if ($expected.identity_known -ne $true -or $current.identity_known -ne $true) { return $false }
  return ([int]$expected.pid -eq [int]$current.pid) -and
    ([string]::Equals([string]$expected.process_name, [string]$current.process_name,
      [System.StringComparison]::OrdinalIgnoreCase)) -and
    ([string]$expected.start_time_utc -ceq [string]$current.start_time_utc)
}

function Get-AcadProcessSnapshot {
  # ObjectNotFound is a known empty result.  Any other enumeration failure or
  # an incomplete process identity is unknown and must fail closed.
  $processes = @()
  try {
    $candidates = @(Get-Process -Name acad -ErrorAction Stop)
  } catch {
    if ($_.CategoryInfo.Category -eq [System.Management.Automation.ErrorCategory]::ObjectNotFound) {
      return [ordered]@{ known = $true; processes = @() }
    }
    return [ordered]@{ known = $false; processes = @(); error = $_.Exception.Message }
  }
  foreach ($candidate in $candidates) {
    $identity = New-ProcessIdentity $candidate
    if ($null -eq $identity) {
      return [ordered]@{ known = $false; processes = @(); error = 'acad process identity was incomplete' }
    }
    $processes += $identity
  }
  return [ordered]@{ known = $true; processes = @($processes) }
}

function Get-ProcessIdentityById([int]$ProcessId) {
  try {
    $candidate = Get-Process -Id $ProcessId -ErrorAction Stop
  } catch {
    if ($_.CategoryInfo.Category -eq [System.Management.Automation.ErrorCategory]::ObjectNotFound) {
      return [ordered]@{
        pid = $ProcessId; known = $true; present = $false
        process_name = $null; start_time_utc = $null; identity_known = $false
      }
    }
    return [ordered]@{
      pid = $ProcessId; known = $false; present = $null
      process_name = $null; start_time_utc = $null; identity_known = $false
      error = $_.Exception.Message
    }
  }
  $identity = New-ProcessIdentity $candidate
  if ($null -eq $identity) {
    return [ordered]@{
      pid = $ProcessId; known = $false; present = $null
      process_name = $null; start_time_utc = $null; identity_known = $false
      error = 'process identity was incomplete'
    }
  }
  $identity['present'] = $true
  return $identity
}

# NATIVE_DEPLOYMENT_CONSUMER_BEGIN
$script:NativeDeploymentLeaves = @(
  'Ariadne.AcadNativeDbx.dbx',
  'Ariadne.AcadNative.crx',
  'Ariadne.AcadNative.arx'
)

function Get-Sha256File {
  param([string]$Path)
  $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
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
        $inputs += [ordered]@{
          path = $relative
          sha256 = Get-Sha256File -Path $entry.FullName
          bytes = [int64]$entry.Length
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

function Get-NativeLockedStreamSha256 {
  param([System.IO.FileStream]$Stream)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $Stream.Position = 0
    $digest = -join ($sha.ComputeHash($Stream) | ForEach-Object { $_.ToString('x2') })
    $Stream.Position = 0
    return $digest
  } finally {
    $sha.Dispose()
  }
}

function Read-NativeLockedUtf8Text {
  param([System.IO.FileStream]$Stream)
  if ($Stream.Length -le 0 -or $Stream.Length -gt 8MB) {
    throw "Native manifest size is outside the accepted range: $($Stream.Length)"
  }
  $Stream.Position = 0
  $buffer = New-Object byte[] ([int]$Stream.Length)
  $offset = 0
  while ($offset -lt $buffer.Length) {
    $read = $Stream.Read($buffer, $offset, $buffer.Length - $offset)
    if ($read -le 0) { throw 'Native manifest ended before its declared length.' }
    $offset += $read
  }
  $Stream.Position = 0
  return (New-Object System.Text.UTF8Encoding($false, $true)).GetString($buffer)
}

function Test-NativeLockedX64Pe32Plus {
  param([System.IO.FileStream]$Stream)
  if ($Stream.Length -lt 512) { return $false }
  $reader = New-Object System.IO.BinaryReader($Stream, (New-Object System.Text.UTF8Encoding($false)), $true)
  try {
    $Stream.Position = 0
    if ($reader.ReadByte() -ne 0x4D -or $reader.ReadByte() -ne 0x5A) { return $false }
    $Stream.Position = 0x3C
    $peOffset = $reader.ReadInt32()
    if ($peOffset -lt 0x40 -or ([int64]$peOffset + 26) -gt $Stream.Length) { return $false }
    $Stream.Position = $peOffset
    if ($reader.ReadUInt32() -ne 0x00004550) { return $false }
    if ($reader.ReadUInt16() -ne 0x8664) { return $false }
    if ($reader.ReadUInt16() -lt 1) { return $false }
    $Stream.Position = $peOffset + 20
    $optionalBytes = $reader.ReadUInt16()
    if ($optionalBytes -lt 0xF0 -or ([int64]$peOffset + 24 + $optionalBytes) -gt $Stream.Length) { return $false }
    $Stream.Position = $peOffset + 24
    return ($reader.ReadUInt16() -eq 0x020B)
  } finally {
    $reader.Dispose()
    $Stream.Position = 0
  }
}

function Close-NativeDeploymentLease {
  param($Lease)
  if ($null -eq $Lease -or $Lease.closed -eq $true) { return }
  foreach ($stream in @($Lease.artifact_streams)) {
    if ($null -ne $stream) { $stream.Dispose() }
  }
  if ($null -ne $Lease.manifest_stream) { $Lease.manifest_stream.Dispose() }
  $Lease.closed = $true
}

function Open-NativeDeploymentLease {
  param([string]$BinDir, [string]$ManifestLeaf)
  if ($ManifestLeaf -cnotin @('native_deployment_manifest.json', 'native_build_manifest.json')) {
    throw "Unsupported native manifest leaf: $ManifestLeaf"
  }
  $lease = [pscustomobject]@{
    bin_dir = $null
    manifest_kind = if ($ManifestLeaf -ceq 'native_deployment_manifest.json') { 'deployment' } else { 'build' }
    manifest_path = $null
    manifest_stream = $null
    artifact_streams = New-Object System.Collections.ArrayList
    artifact_paths = @{}
    closed = $false
  }
  try {
    $directory = Get-Item -LiteralPath $BinDir -Force -ErrorAction Stop
    if (-not $directory.PSIsContainer -or
        ($directory.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
      throw "Native bin directory is missing or a reparse point: $BinDir"
    }
    $lease.bin_dir = $directory.FullName
    $lease.manifest_path = Join-Path $directory.FullName $ManifestLeaf
    $manifestItem = Get-Item -LiteralPath $lease.manifest_path -Force -ErrorAction Stop
    if ($manifestItem.PSIsContainer -or
        ($manifestItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
      throw "Native manifest is not a regular file: $($lease.manifest_path)"
    }
    $lease.manifest_stream = [System.IO.File]::Open(
      $lease.manifest_path,
      [System.IO.FileMode]::Open,
      [System.IO.FileAccess]::Read,
      [System.IO.FileShare]::Read
    )
    try {
      $document = (Read-NativeLockedUtf8Text $lease.manifest_stream) | ConvertFrom-Json
    } catch {
      throw "Native manifest is invalid JSON: $($_.Exception.Message)"
    }

    if ($lease.manifest_kind -ceq 'deployment') {
      if ([string]$document.schema -cne 'ariadne.cad_os.native_deployment_manifest.v1' -or
          [string]$document.deployment_state -cne 'committed' -or $document.committed -ne $true) {
        throw 'Native deployment manifest is not a committed v1 marker.'
      }
      $claimedSourceDigest = [string]$document.source_tree_digest
    } else {
      if ([string]$document.schema -cne 'ariadne.cad_os.native_build_manifest.v1' -or
          $document.build_snapshot.exact_match -ne $true) {
        throw 'Native build manifest is not a finalized exact-snapshot v1 manifest.'
      }
      $manifestBin = [System.IO.Path]::GetFullPath([string]$document.load_bin_dir).TrimEnd('\')
      if (-not [string]::Equals($manifestBin, $directory.FullName.TrimEnd('\'), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Native build manifest load_bin_dir does not match the requested bin directory.'
      }
      $claimedSourceDigest = [string]$document.source_tree.digest
    }
    if ([string]$document.claim_scope -cne 'release_build_integrity_bundle' -or
        [string]$document.build_target -cne 'Rebuild' -or
        [string]$document.configuration -cne 'Release' -or
        [string]$document.platform -cne 'x64') {
      throw 'Native manifest is not a Release|x64 Rebuild integrity bundle.'
    }
    $recipePath = Join-Path $RouterHome 'tools\build_native_acad.ps1'
    if ([string]$document.build_recipe.path -cne 'tools/build_native_acad.ps1' -or
        [string]$document.build_recipe.sha256 -cne (Get-Sha256File $recipePath)) {
      throw 'Native manifest does not bind to the current build recipe.'
    }
    $sourceInputs = @(Get-NativeSourceInputs)
    $actualSourceDigest = Get-NativeSourceDigest $sourceInputs
    if ($claimedSourceDigest -notmatch '^[0-9a-f]{64}$' -or
        $claimedSourceDigest -cne $actualSourceDigest) {
      throw 'Native manifest source-tree digest does not match the current native sources.'
    }

    $allRecords = @($document.artifacts)
    if ($allRecords.Count -ne $script:NativeDeploymentLeaves.Count) {
      throw 'Native manifest must contain the exact DBX, CRX, and ARX artifact set.'
    }
    foreach ($leaf in $script:NativeDeploymentLeaves) {
      $records = @($allRecords | Where-Object { [string]$_.leaf -ceq $leaf })
      if ($records.Count -ne 1) {
        throw "Native manifest must contain exactly one record for $leaf."
      }
      $record = $records[0]
      $artifactPath = Join-Path $directory.FullName $leaf
      $artifactItem = Get-Item -LiteralPath $artifactPath -Force -ErrorAction Stop
      if ($artifactItem.PSIsContainer -or
          ($artifactItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Native artifact is not a regular file: $leaf"
      }
      $artifactStream = [System.IO.File]::Open(
        $artifactPath,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read
      )
      [void]$lease.artifact_streams.Add($artifactStream)
      $lease.artifact_paths[$leaf] = $artifactPath
      if ($record.exists -ne $true -or $record.current -ne $true -or
          $record.pe_verification.verified -ne $true -or
          [string]$record.pe_verification.machine -cne '0x8664' -or
          [string]$record.pe_verification.format -cne 'PE32+' -or
          [int64]$record.bytes -ne [int64]$artifactStream.Length -or
          [string]$record.sha256 -cne (Get-NativeLockedStreamSha256 $artifactStream) -or
          -not (Test-NativeLockedX64Pe32Plus $artifactStream)) {
        throw "Native artifact does not match its verified manifest record: $leaf"
      }
    }
    return $lease
  } catch {
    Close-NativeDeploymentLease $lease
    throw
  }
}
# NATIVE_DEPLOYMENT_CONSUMER_END

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$runId = Split-Path -Leaf $RunDir
$completionReceipt = Join-Path $RunDir 'attended_job_completion.json'
$finalReceipt = Join-Path $RunDir 'attended_job_final_receipt.json'

if (-not (Test-Path -LiteralPath $StagedDwg)) {
  $result = [ordered]@{
    schema = 'ariadne.cad_os.attended_job_result.v1'; run_id = $runId; status = 'error'
    error = "staged dwg not found: $StagedDwg"
  }
  WriteJson $result $finalReceipt
  $result | ConvertTo-Json -Depth 12
  exit 2
}
if (-not (Test-Path -LiteralPath $AcadExe)) {
  $result = [ordered]@{
    schema = 'ariadne.cad_os.attended_job_result.v1'; run_id = $runId; status = 'error'
    error = "acad.exe not found: $AcadExe"
  }
  WriteJson $result $finalReceipt
  $result | ConvertTo-Json -Depth 12
  exit 2
}

$usingDefaultPrebuilt = [string]::IsNullOrWhiteSpace($NativeBinDir)
$requestedDbx = if ($usingDefaultPrebuilt) { $null } else { Join-Path $NativeBinDir 'Ariadne.AcadNativeDbx.dbx' }
$requestedArx = if ($usingDefaultPrebuilt) { $null } else { Join-Path $NativeBinDir 'Ariadne.AcadNative.arx' }
$binDir = if ($usingDefaultPrebuilt) { Join-Path $RouterHome 'prebuilt\2027' } else { $NativeBinDir }
$manifestLeaf = if ($usingDefaultPrebuilt) { 'native_deployment_manifest.json' } else { 'native_build_manifest.json' }
$nativeLease = Open-NativeDeploymentLease -BinDir $binDir -ManifestLeaf $manifestLeaf
$dbx = [string]$nativeLease.artifact_paths['Ariadne.AcadNativeDbx.dbx']
$arx = [string]$nativeLease.artifact_paths['Ariadne.AcadNative.arx']
if (-not $usingDefaultPrebuilt -and
    (-not [string]::Equals([System.IO.Path]::GetFullPath($requestedDbx), $dbx, [System.StringComparison]::OrdinalIgnoreCase) -or
     -not [string]::Equals([System.IO.Path]::GetFullPath($requestedArx), $arx, [System.StringComparison]::OrdinalIgnoreCase))) {
  Close-NativeDeploymentLease $nativeLease
  throw 'Explicit native module paths escaped the verified build-manifest directory.'
}

try {

# ---- Gate 1: pre-existing acad.exe (record; NEVER attach) -------------------
# PID plus process start time is an identity, unlike a PID alone which Windows
# may reuse after a process exits.  The compact completion receipt carries
# these facts for Python's independent recovery validator if finalization hangs.
$preSnapshot = Get-AcadProcessSnapshot
$preEnumerationKnown = ($preSnapshot.known -eq $true)
$preProcesses = @($preSnapshot.processes)
$preIdentityKnown = [bool]$preEnumerationKnown
foreach ($identity in $preProcesses) {
  if ($identity.known -ne $true -or $identity.identity_known -ne $true -or
      [int]$identity.pid -le 0 -or [string]::IsNullOrWhiteSpace([string]$identity.process_name) -or
      [string]::IsNullOrWhiteSpace([string]$identity.start_time_utc)) {
    $preIdentityKnown = $false
    break
  }
}
$preIds = @($preProcesses | ForEach-Object { [int]$_.pid })

# ---- build the job (flat shape: {"operation": ..., <op args>} -- the SAME shape
# docs/LIVE_JOB_ARGUMENT_CONTRACT.md and the M07B probe-create job used; NOT the
# patch_engine._native_job_doc nested {"args":{...}} envelope, which is a
# DIFFERENT (headless ARIADNE_NATIVE_JOB, not _ARGS) contract.) ----------------
$jobArgsObj = $JobArgsJson | ConvertFrom-Json
$jobDoc = [ordered]@{ operation = $Operation }
foreach ($prop in $jobArgsObj.PSObject.Properties) { $jobDoc[$prop.Name] = $prop.Value }

$jobIn  = Join-Path $RunDir 'job_in.json'
$jobOut = Join-Path $RunDir 'job_out.json'
$argsF  = Join-Path $RunDir 'live_job_args.json'
$completionCleanupWaitSec = 60
WriteJson $jobDoc $jobIn
WriteJson ([ordered]@{ job_in = (FS $jobIn); job_out = (FS $jobOut); host_mode = 'full_autocad' }) $argsF

$secBefore = Join-Path $RunDir 'security_before.txt'
$secAfter  = Join-Path $RunDir 'security_after.txt'
$trustedEscaped = $binDir.Replace('\', '\\')

$scr = Join-Path $RunDir 'attended_job.scr'
$readOnlyOperation = ($Operation -eq 'e2.inspect.xclip_membership')
$saveCommand = if ($readOnlyOperation) { '(princ)' } else { '_QSAVE' }
@(
  '(setq _ariadneOsl (getvar "SECURELOAD"))',
  '(setq _ariadneOtp (getvar "TRUSTEDPATHS"))',
  "(setq _f (open `"$(FS $secBefore)`" `"w`"))",
  '(write-line (itoa _ariadneOsl) _f)',
  '(write-line _ariadneOtp _f)',
  '(close _f)',
  '(setvar "FILEDIA" 0)',
  '(setvar "CMDECHO" 0)',
  '(setvar "SECURELOAD" 0)',
  "(setvar `"TRUSTEDPATHS`" (strcat _ariadneOtp `";$trustedEscaped`"))",
  "(arxload `"$(FS $dbx)`")",
  "(arxload `"$(FS $arx)`")",
  'ARIADNE_NATIVE_JOB_ARGS',
  '(setvar "SECURELOAD" _ariadneOsl)',
  '(setvar "TRUSTEDPATHS" _ariadneOtp)',
  "(setq _f2 (open `"$(FS $secAfter)`" `"w`"))",
  '(write-line (itoa (getvar "SECURELOAD")) _f2)',
  '(write-line (getvar "TRUSTEDPATHS") _f2)',
  '(close _f2)',
  $saveCommand,
  '_QUIT',
  ''
) | Set-Content -LiteralPath $scr -Encoding ASCII

Log "=== attended job run: $runId ==="
Log "pre-existing acad PIDs: $($preIds -join ',')"
Log "operation: $Operation"

# state used by the finally block even if something below throws
$launchedPid = $null
$launchedProcessName = $null
$launchedStartTimeUtc = $null
$launchedIdentity = $null
$launchedIdentityKnown = $false
$dedicatedOk = $preIdentityKnown
$jobDone = $false
$timedOut = $false
$launchedGone = $null
$launchedExited = $false
$preStillAlive = @()
$postProcesses = @()
$postEnumerationKnown = $false
$launchedPidQueryKnown = $false
$launchedPidQueryFailed = $false
$preExistingIdentityVerified = $false
$launchedPidIdentityVerified = $false
$launchedPidReused = $false
$userSessionTouched = $null
$proc = $null
$completionReceiptWritten = $false

try {
  if (-not $preIdentityKnown) {
    $dedicatedOk = $false
    Log 'GATE1 FAIL: pre-existing acad process identity enumeration was unknown; aborting before launch.'
  } else {
    # ---- launch DEDICATED acad.exe on the STAGED doc only --------------------
    # ARIADNE_NATIVE_JOB_ARGS (the AutoCAD command run inside the script) reads
    # this env var from the child at launch time; writing the path to disk alone
    # is not enough to select the non-interactive command.
    $env:ARIADNE_NATIVE_JOB_ARGS = $argsF
    # Pass one explicitly quoted command line.  Autodesk requires /b <script>
    # to be the final parameter pair.
    $launchArgs = "`"$StagedDwg`" /nologo /b `"$scr`""
    Log "launch args: $launchArgs"
    $proc = Start-Process -FilePath $AcadExe -ArgumentList $launchArgs -PassThru
    if ($null -eq $proc) {
      $dedicatedOk = $false
      Log 'GATE1 FAIL: Start-Process returned no process handle.'
    } else {
      $launchedPid = [int]$proc.Id
      $launchedIdentity = New-ProcessIdentity $proc
      $launchedIdentityKnown = $null -ne $launchedIdentity
      if ($launchedIdentityKnown) {
        $launchedProcessName = $launchedIdentity.process_name
        $launchedStartTimeUtc = $launchedIdentity.start_time_utc
      }
      Log "launched dedicated acad PID: $launchedPid"
      $preCollision = @($preProcesses | Where-Object { Same-ProcessIdentity $_ $launchedIdentity })
      $dedicatedOk = $preIdentityKnown -and $launchedIdentityKnown -and ($preCollision.Count -eq 0)
      if (-not $dedicatedOk) {
        Log 'GATE1 FAIL: launched process identity is unknown or collides with a pre-existing identity; aborting without driving.'
      } else {
        # ---- poll for completion: job_out.json appears, OR process exits, OR timeout
        $deadline = (Get-Date).AddSeconds($TimeoutSec)
        while ((Get-Date) -lt $deadline) {
          if (Test-Path -LiteralPath $jobOut) { $jobDone = $true; Log "job_out.json appeared"; break }
          $proc.Refresh()
          if ($proc.HasExited) { Log "process exited on its own (no job_out.json yet)"; break }
          Start-Sleep -Milliseconds 500
        }
        if (-not $jobDone -and -not $proc.HasExited) {
          Log "poll deadline ($($TimeoutSec)s) reached without job_out.json"
        }
        # This compact signal is written before save/QUIT cleanup.  It is only
        # usable for Python recovery when both captured identity sets are known.
        if ($jobDone -and $launchedIdentityKnown -and $preIdentityKnown) {
          $completion = [ordered]@{
            schema = 'ariadne.cad_os.attended_job_completion.v1'
            run_id = $runId
            phase = 'cleanup_pending'
            status = 'observed'
            operation = $Operation
            read_only_operation = $readOnlyOperation
            staged_save_attempted = (-not $readOnlyOperation)
            launched_pid = $launchedPid
            launched_process_name = $launchedProcessName
            launched_start_time_utc = $launchedStartTimeUtc
            dedicated_instance = $dedicatedOk
            timed_out = $false
            job_out = $jobOut
            job_out_present = $true
            pre_existing_pids = $preIds
            pre_existing_processes = $preProcesses
            cleanup_wait_sec = $completionCleanupWaitSec
          }
          try {
            WriteJsonAtomic $completion $completionReceipt
            $completionReceiptWritten = $true
            Log 'wrote compact completion receipt before cleanup'
          } catch {
            Log "completion receipt write failed: $($_.Exception.Message)"
          }
        }
        # Grace period for the optional save plus QUIT to flush and exit.
        $proc.Refresh()
        if ($jobDone -and -not $proc.HasExited) {
          Log "job done; waiting up to 30s for the process to quit on its own"
          $graceDeadline = (Get-Date).AddSeconds(30)
          while ((Get-Date) -lt $graceDeadline) {
            $proc.Refresh()
            if ($proc.HasExited) { break }
            Start-Sleep -Milliseconds 500
          }
        }
        $proc.Refresh()
        $launchedExited = $proc.HasExited
        $timedOut = -not $jobDone -and -not $launchedExited
        Log "post-poll: jobDone=$jobDone hasExited=$launchedExited timedOut=$timedOut"
      }
    }
  }
} catch {
  $dedicatedOk = $false
  Log "EXCEPTION during launch/poll: $($_.Exception.Message)"
} finally {
  # ---- teardown: close ONLY the launched process handle after revalidating
  # its captured identity.  A numeric PID is never a sufficient kill target.
  $env:ARIADNE_NATIVE_JOB_ARGS = $null
  $stillRunning = $false
  if ($launchedPid -and $launchedIdentityKnown -and $null -ne $proc) {
    Log "cleanup: launchedExited=$launchedExited"
    try {
      $proc.Refresh()
      if (-not $proc.HasExited) {
        $handleIdentity = New-ProcessIdentity $proc
        if ($null -eq $handleIdentity) {
          $launchedPidQueryKnown = $false
          $launchedPidQueryFailed = $true
          Log 'cleanup: launched process identity became unknown; refusing to terminate it'
        } elseif (Same-ProcessIdentity $launchedIdentity $handleIdentity) {
          $stillRunning = $true
        } else {
          $launchedPidReused = $true
          $launchedPidQueryKnown = $true
          Log 'cleanup: launched PID now names a different process; refusing to terminate it'
        }
      } else {
        $launchedPidQueryKnown = $true
      }
    } catch {
      $launchedPidQueryKnown = $false
      $launchedPidQueryFailed = $true
      Log "cleanup: launched process identity query failed: $($_.Exception.Message)"
    }
    if ($stillRunning) {
      Log "closing launched PID $launchedPid through its exact process handle"
      try { Stop-Process -InputObject $proc -Force -ErrorAction Stop; Log 'Stop-Process handle close ok' }
      catch { Log "Stop-Process handle close failed: $($_.Exception.Message)" }
      Start-Sleep -Seconds 1

      # Re-query the PID and require an exact identity match before the raw
      # taskkill fallback.  If the query is unknown or the PID was reused, do
      # not send a kill command to the unrelated process.
      $afterStop = Get-ProcessIdentityById $launchedPid
      if ($afterStop.known -ne $true) {
        $launchedPidQueryKnown = $false
        $launchedPidQueryFailed = $true
        $stillThere = $true
        Log 'cleanup: post-Stop-Process identity query unknown; refusing taskkill fallback'
      } elseif (-not $afterStop.present) {
        $launchedPidQueryKnown = $true
        $stillThere = $false
      } elseif (Same-ProcessIdentity $launchedIdentity $afterStop) {
        $launchedPidQueryKnown = $true
        $stillThere = $true
      } else {
        $launchedPidQueryKnown = $true
        $launchedPidReused = $true
        $stillThere = $false
        Log 'cleanup: PID was reused after Stop-Process; refusing taskkill fallback'
      }
      if ($stillThere) {
        $taskkillTarget = Get-ProcessIdentityById $launchedPid
        if ($taskkillTarget.known -eq $true -and $taskkillTarget.present -and
            (Same-ProcessIdentity $launchedIdentity $taskkillTarget)) {
          Log "PID $launchedPid still alive after handle close; taskkill fallback (/T /F)"
          try {
            $taskkillProc = Start-Process -FilePath 'taskkill.exe' -ArgumentList "/PID $launchedPid /T /F" -PassThru -NoNewWindow
            if (-not $taskkillProc.WaitForExit(10000)) {
              Log 'taskkill fallback exceeded 10s; stopping taskkill helper'
              try { Stop-Process -InputObject $taskkillProc -Force -ErrorAction Stop } catch {}
            } else {
              Log "taskkill exit code: $($taskkillProc.ExitCode)"
            }
          } catch { Log "taskkill invocation failed: $($_.Exception.Message)" }
          Start-Sleep -Seconds 1
        } elseif ($taskkillTarget.known -ne $true) {
          $launchedPidQueryKnown = $false
          $launchedPidQueryFailed = $true
          Log 'cleanup: taskkill identity revalidation unknown; no fallback issued'
        } else {
          $launchedPidReused = $true
          Log 'cleanup: taskkill identity revalidation found PID reuse; no fallback issued'
        }
      }
    }
  } elseif ($launchedPid) {
    Log 'cleanup: launched process identity was unknown; refusing any process termination'
    $launchedPidQueryKnown = $false
    $launchedPidQueryFailed = $true
  }

  Log 'cleanup: collecting process-safety evidence'
  $postSnapshot = Get-AcadProcessSnapshot
  $postEnumerationKnown = ($postSnapshot.known -eq $true)
  $postProcesses = @($postSnapshot.processes)
  $preExistingIdentityVerified = $preIdentityKnown -and $postEnumerationKnown
  $preStillAlive = @()
  if ($preExistingIdentityVerified) {
    foreach ($expected in $preProcesses) {
      $current = @($postProcesses | Where-Object { [int]$_.pid -eq [int]$expected.pid }) | Select-Object -First 1
      if ($null -eq $current -or -not (Same-ProcessIdentity $expected $current)) {
        $preExistingIdentityVerified = $false
      } else {
        $preStillAlive += [int]$expected.pid
      }
    }
  }
  if ($launchedPid -and $launchedIdentityKnown) {
    $launchedPost = Get-ProcessIdentityById $launchedPid
    if ($launchedPost.known -ne $true) { $launchedPidQueryFailed = $true }
    $launchedPidQueryKnown = (-not $launchedPidQueryFailed) -and ($launchedPost.known -eq $true)
    if ($launchedPidQueryKnown -and -not $launchedPost.present) {
      $launchedGone = $true
      $launchedPidIdentityVerified = $true
    } elseif ($launchedPidQueryKnown -and (Same-ProcessIdentity $launchedIdentity $launchedPost)) {
      $launchedGone = $false
      $launchedPidIdentityVerified = $false
    } elseif ($launchedPidQueryKnown) {
      $launchedGone = $true
      $launchedPidReused = $true
      $launchedPidIdentityVerified = $true
    } else {
      $launchedGone = $false
      $launchedPidIdentityVerified = $false
    }
  } else {
    $launchedGone = $false
    $launchedPidIdentityVerified = $false
  }
  if ($preExistingIdentityVerified) {
    $userSessionTouched = $false
  } elseif ($preEnumerationKnown -and $postEnumerationKnown) {
    $userSessionTouched = $true
  }

  # ---- read back compact launcher safety evidence --------------------------
  Log 'cleanup: collecting security restoration evidence'
  $secBeforeLines = if (Test-Path -LiteralPath $secBefore) { Get-Content -LiteralPath $secBefore } else { @() }
  $secAfterLines  = if (Test-Path -LiteralPath $secAfter)  { Get-Content -LiteralPath $secAfter }  else { @() }
  $secureloadBefore = if ($secBeforeLines.Count -ge 1) { $secBeforeLines[0] } else { $null }
  $trustedpathsBefore = if ($secBeforeLines.Count -ge 2) { $secBeforeLines[1] } else { $null }
  $secureloadAfter = if ($secAfterLines.Count -ge 1) { $secAfterLines[0] } else { $null }
  $trustedpathsAfter = if ($secAfterLines.Count -ge 2) { $secAfterLines[1] } else { $null }
  $securityRestored = ($secureloadBefore -eq $secureloadAfter) -and ($trustedpathsBefore -eq $trustedpathsAfter) -and ($null -ne $secureloadBefore) -and ($null -ne $trustedpathsBefore)
  $jobOutPresent = Test-Path -LiteralPath $jobOut
  $finalizationFailures = @()
  if (-not $preIdentityKnown) { $finalizationFailures += 'pre-existing acad process identity was unknown' }
  if (-not $launchedIdentityKnown -and $launchedPid) { $finalizationFailures += 'launched acad process identity was unknown' }
  if (-not $postEnumerationKnown) { $finalizationFailures += 'post-cleanup acad process enumeration was unknown' }
  if ($launchedPid -and -not $launchedPidQueryKnown) { $finalizationFailures += 'launched PID identity query was unknown' }
  if ($launchedPid -and -not $launchedPidIdentityVerified) { $finalizationFailures += 'launched PID identity was not verified closed or reused' }
  if (-not $preExistingIdentityVerified) { $finalizationFailures += 'pre-existing user AutoCAD identities were not exact matches' }
  if ($null -eq $userSessionTouched -or $userSessionTouched) { $finalizationFailures += 'pre-existing user AutoCAD session safety was not proven' }
  if (-not $launchedGone) { $finalizationFailures += 'launched PID was not confirmed closed' }
  if (-not $securityRestored) { $finalizationFailures += 'SECURELOAD/TRUSTEDPATHS restoration was not confirmed' }

  $status = if (-not $dedicatedOk) { 'blocked' }
            elseif ($timedOut) { 'timeout' }
            elseif (-not $jobDone -or -not $jobOutPresent) { 'error' }
            elseif ($finalizationFailures.Count -gt 0) { 'error' }
            else { 'ok' }
  $errorMessage = if ($status -eq 'blocked') { 'GATE1 FAIL: process identity was unknown or collided with a pre-existing identity; aborted without driving.' }
                  elseif ($status -eq 'timeout') { "no job_out.json within ${TimeoutSec}s and process did not exit on its own" }
                  elseif (-not $jobDone -or -not $jobOutPresent) { 'native job completion was not observed' }
                  elseif ($finalizationFailures.Count -gt 0) { $finalizationFailures -join '; ' }
                  else { $null }
  $result = [ordered]@{
    schema = 'ariadne.cad_os.attended_job_result.v1'
    run_id = $runId
    phase = 'finalized'
    status = $status
    operation = $Operation
    read_only_operation = $readOnlyOperation
    staged_save_attempted = (-not $readOnlyOperation)
    receipt_authority = 'powershell_launcher'
    recovered_from_launcher_finalization_hang = $false
    launched_pid = $launchedPid
    launched_process_name = $launchedProcessName
    launched_start_time_utc = $launchedStartTimeUtc
    dedicated_instance = $dedicatedOk
    timed_out = $timedOut
    launched_pid_closed = $launchedGone
    launched_pid_identity_verified = $launchedPidIdentityVerified
    launched_pid_reused = $launchedPidReused
    launched_pid_identity_query_known = $launchedPidQueryKnown
    pre_existing_pids = $preIds
    pre_existing_processes = $preProcesses
    pre_existing_still_alive = $preStillAlive
    pre_existing_identity_verified = $preExistingIdentityVerified
    pre_existing_identity_query_known = ($preEnumerationKnown -and $postEnumerationKnown)
    post_processes = $postProcesses
    user_session_touched = $userSessionTouched
    job_in = $jobIn
    job_out = $jobOut
    job_out_present = $jobOutPresent
    completion_receipt = $completionReceipt
    completion_receipt_written = $completionReceiptWritten
    final_receipt = $finalReceipt
    degraded = $false
    security = [ordered]@{
      secureload_before = $secureloadBefore; secureload_after = $secureloadAfter
      trustedpaths_before = $trustedpathsBefore; trustedpaths_after = $trustedpathsAfter
      restored = $securityRestored
    }
    error = $errorMessage
  }
  Log 'cleanup: writing final receipt'
  WriteJson $result $finalReceipt
  Log '--- attended_job_final_receipt ---'
  $result | ConvertTo-Json -Depth 12
}
}
finally {
  Close-NativeDeploymentLease $nativeLease
}
