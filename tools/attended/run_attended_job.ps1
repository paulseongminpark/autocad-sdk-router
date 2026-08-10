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
# (tools/attended/run_attended_m07b.ps1): dedicated PID, staged-doc-only, then QSAVE
# + QUIT (no interactive pump -- this is a single job, not a live session).
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

$dbx = if ([string]::IsNullOrWhiteSpace($NativeBinDir)) {
  Join-Path $RouterHome 'prebuilt\2027\Ariadne.AcadNativeDbx.dbx'
} else {
  Join-Path $NativeBinDir 'Ariadne.AcadNativeDbx.dbx'
}
$arx = if ([string]::IsNullOrWhiteSpace($NativeBinDir)) {
  Join-Path $RouterHome 'prebuilt\2027\Ariadne.AcadNative.arx'
} else {
  Join-Path $NativeBinDir 'Ariadne.AcadNative.arx'
}
if (-not (Test-Path -LiteralPath $dbx)) { throw "native dbx missing: $dbx" }
if (-not (Test-Path -LiteralPath $arx)) { throw "native arx missing: $arx" }
$binDir = Split-Path -Parent $arx

# ---- Gate 1: pre-existing acad.exe (record; NEVER attach) -------------------
# PID plus process start time is an identity, unlike a PID alone which Windows
# may reuse after a process exits.  The compact completion receipt carries
# these facts for Python's independent recovery validator if finalization hangs.
$preProcesses = @(
  Get-Process acad -ErrorAction SilentlyContinue | ForEach-Object {
    $started = $null
    try { $started = $_.StartTime.ToUniversalTime().ToString('o') } catch {}
    [ordered]@{
      pid = [int]$_.Id
      process_name = [string]$_.ProcessName
      start_time_utc = $started
    }
  }
)
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
  '_QSAVE',
  '_QUIT',
  ''
) | Set-Content -LiteralPath $scr -Encoding ASCII

Log "=== attended job run: $runId ==="
Log "pre-existing acad PIDs: $($preIds -join ',')"
Log "operation: $Operation"

# state used by the finally block even if something below throws
$launchedPid = $null
$launchedStartTimeUtc = $null
$dedicatedOk = $true
$jobDone = $false
$timedOut = $false
$launchedGone = $null
$launchedExited = $false
$preStillAlive = @()
$proc = $null
$completionReceiptWritten = $false

try {
  # ---- launch DEDICATED acad.exe on the STAGED doc only ----------------------
  # ARIADNE_NATIVE_JOB_ARGS (the AutoCAD command run inside the script) reads this
  # env var via acedGetEnv/_wgetenv (docs/LIVE_JOB_ARGUMENT_CONTRACT.md). Start-
  # Process only passes environment variables that are set in THIS calling
  # process at launch time -- it does not read them from the script file, so this
  # MUST be set here, not merely written into live_job_args.json. Without it the
  # command falls back to its documented interactive prompt and hangs forever
  # (confirmed empirically: this wave's first live run hung past its own timeout
  # with this line missing -- see build_log.md).
  $env:ARIADNE_NATIVE_JOB_ARGS = $argsF
  # Pass one explicitly quoted command line.  PowerShell's string[] form can
  # lose the grouping of quoted path arguments when it flattens ArgumentList;
  # the observed failure mode is a healthy acad.exe stuck on the Start page
  # with neither the DWG nor /b script consumed.  Autodesk's startup contract
  # also requires /b <script> to be the final parameter pair.
  $launchArgs = "`"$StagedDwg`" /nologo /b `"$scr`""
  Log "launch args: $launchArgs"
  $proc = Start-Process -FilePath $AcadExe -ArgumentList $launchArgs -PassThru
  $launchedPid = $proc.Id
  try { $launchedStartTimeUtc = $proc.StartTime.ToUniversalTime().ToString('o') }
  catch { Log "could not read launched process start time: $($_.Exception.Message)" }
  Log "launched dedicated acad PID: $launchedPid"

  $dedicatedOk = ($preIds -notcontains $launchedPid)
  if (-not $dedicatedOk) {
    Log 'GATE1 FAIL: launched PID collides with a pre-existing session; aborting without driving.'
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
    # The native side has produced its output.  Write this deliberately tiny,
    # atomic receipt BEFORE the normal QSAVE/QUIT wait and finally cleanup so a
    # Python caller does not mistake late cleanup for an unfinished CAD job.
    # It is explicitly not the final success receipt: it carries no job_out
    # payload and cannot prove security restoration or process isolation.
    if ($jobDone) {
      $completion = [ordered]@{
        schema = 'ariadne.cad_os.attended_job_completion.v1'
        run_id = $runId
        phase = 'cleanup_pending'
        status = 'observed'
        operation = $Operation
        launched_pid = $launchedPid
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
    # grace period for QSAVE+QUIT to flush and the process to exit on its own
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
} catch {
  Log "EXCEPTION during launch/poll: $($_.Exception.Message)"
} finally {
  # ---- teardown: close ONLY the launched PID (Stop-Process, then a raw
  # taskkill.exe /T /F last resort) -- wrapped so a teardown failure can never
  # prevent the result file below from being written (no silent hang/no result).
  $env:ARIADNE_NATIVE_JOB_ARGS = $null
  if ($launchedPid) {
    Log "cleanup: launchedExited=$launchedExited"
    $stillRunning = -not $launchedExited
    if (-not $launchedExited) {
      try {
        if ($null -ne $proc) {
          $proc.Refresh()
          $stillRunning = -not $proc.HasExited
        } else {
          $stillRunning = [bool](Get-Process -Id $launchedPid -ErrorAction SilentlyContinue)
        }
      } catch {
        try { $stillRunning = [bool](Get-Process -Id $launchedPid -ErrorAction SilentlyContinue) } catch {}
      }
    }
    if ($stillRunning) {
      Log "closing launched PID $launchedPid (Stop-Process)"
      try { Stop-Process -Id $launchedPid -Force -ErrorAction Stop; Log "Stop-Process ok" }
      catch { Log "Stop-Process failed: $($_.Exception.Message)" }
      Start-Sleep -Seconds 1
      $stillThere = $false
      try {
        if ($null -ne $proc) {
          $proc.Refresh()
          $stillThere = -not $proc.HasExited
        } else {
          $stillThere = [bool](Get-Process -Id $launchedPid -ErrorAction SilentlyContinue)
        }
      } catch {
        try { $stillThere = [bool](Get-Process -Id $launchedPid -ErrorAction SilentlyContinue) } catch {}
      }
      if ($stillThere) {
        Log "PID $launchedPid still alive after Stop-Process; taskkill fallback (/T /F)"
        try {
          $taskkillProc = Start-Process -FilePath 'taskkill.exe' -ArgumentList "/PID $launchedPid /T /F" -PassThru -NoNewWindow
          if (-not $taskkillProc.WaitForExit(10000)) {
            Log 'taskkill fallback exceeded 10s; stopping taskkill helper'
            try { Stop-Process -Id $taskkillProc.Id -Force -ErrorAction Stop } catch {}
          } else {
            Log "taskkill exit code: $($taskkillProc.ExitCode)"
          }
        } catch { Log "taskkill invocation failed: $($_.Exception.Message)" }
        Start-Sleep -Seconds 1
      }
    }
  }

  Log 'cleanup: collecting process-safety evidence'
  $postIds = @()
  try { $postIds = @(Get-Process acad -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id) } catch {}
  $launchedGone = $launchedExited
  if (-not $launchedGone) {
    try {
      if ($null -ne $proc) {
        $proc.Refresh()
        $launchedGone = $proc.HasExited
      } elseif ($launchedPid) {
        $launchedGone = $postIds -notcontains $launchedPid
      }
    } catch {
      if ($launchedPid) { $launchedGone = $postIds -notcontains $launchedPid }
    }
  }
  $preStillAlive = @($preIds | Where-Object { $postIds -contains $_ })

  # ---- read back compact launcher safety evidence --------------------------
  Log 'cleanup: collecting security restoration evidence'
  $secBeforeLines = if (Test-Path -LiteralPath $secBefore) { Get-Content -LiteralPath $secBefore } else { @() }
  $secAfterLines  = if (Test-Path -LiteralPath $secAfter)  { Get-Content -LiteralPath $secAfter }  else { @() }
  $secureloadBefore = if ($secBeforeLines.Count -ge 1) { $secBeforeLines[0] } else { $null }
  $trustedpathsBefore = if ($secBeforeLines.Count -ge 2) { $secBeforeLines[1] } else { $null }
  $secureloadAfter = if ($secAfterLines.Count -ge 1) { $secAfterLines[0] } else { $null }
  $trustedpathsAfter = if ($secAfterLines.Count -ge 2) { $secAfterLines[1] } else { $null }
  $securityRestored = ($secureloadBefore -eq $secureloadAfter) -and ($trustedpathsBefore -eq $trustedpathsAfter) -and ($null -ne $secureloadBefore) -and ($null -ne $trustedpathsBefore)
  $userSessionTouched = [bool]($preStillAlive.Count -lt $preIds.Count)
  $jobOutPresent = Test-Path -LiteralPath $jobOut
  $finalizationFailures = @()
  if (-not $launchedGone) { $finalizationFailures += 'launched PID was not confirmed closed' }
  if ($userSessionTouched) { $finalizationFailures += 'a pre-existing user AutoCAD session disappeared' }
  if (-not $securityRestored) { $finalizationFailures += 'SECURELOAD/TRUSTEDPATHS restoration was not confirmed' }

  $status = if (-not $dedicatedOk) { 'blocked' }
            elseif ($timedOut) { 'timeout' }
            elseif (-not $jobDone -or -not $jobOutPresent) { 'error' }
            elseif ($finalizationFailures.Count -gt 0) { 'error' }
            else { 'ok' }
  $errorMessage = if ($status -eq 'blocked') { 'GATE1 FAIL: launched PID collides with a pre-existing session; aborted without driving.' }
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
    receipt_authority = 'powershell_launcher'
    recovered_from_launcher_finalization_hang = $false
    launched_pid = $launchedPid
    launched_start_time_utc = $launchedStartTimeUtc
    dedicated_instance = $dedicatedOk
    timed_out = $timedOut
    launched_pid_closed = $launchedGone
    pre_existing_pids = $preIds
    pre_existing_processes = $preProcesses
    pre_existing_still_alive = $preStillAlive
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
