param(
  [Parameter(Mandatory=$true)][string]$StagedDwg,
  [Parameter(Mandatory=$true)][string]$Operation,
  [string]$JobArgsJson = '{}',
  [Parameter(Mandatory=$true)][string]$RunDir,
  [int]$TimeoutSec = 240,
  [string]$AcadExe = 'C:\Program Files\Autodesk\AutoCAD 2027\acad.exe',
  [string]$RouterHome = 'D:\dev\99_tools\autocad-sdk-router__wR_attended'
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
function WriteJson($obj, $path) { $obj | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $path -Encoding UTF8 }

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$runId = Split-Path -Leaf $RunDir

if (-not (Test-Path -LiteralPath $StagedDwg)) {
  $result = [ordered]@{
    schema = 'ariadne.cad_os.attended_job_result.v1'; run_id = $runId; status = 'error'
    error = "staged dwg not found: $StagedDwg"
  }
  WriteJson $result (Join-Path $RunDir 'attended_job_result.json')
  $result | ConvertTo-Json -Depth 12
  exit 2
}
if (-not (Test-Path -LiteralPath $AcadExe)) {
  $result = [ordered]@{
    schema = 'ariadne.cad_os.attended_job_result.v1'; run_id = $runId; status = 'error'
    error = "acad.exe not found: $AcadExe"
  }
  WriteJson $result (Join-Path $RunDir 'attended_job_result.json')
  $result | ConvertTo-Json -Depth 12
  exit 2
}

$dbx = Join-Path $RouterHome 'prebuilt\2027\Ariadne.AcadNativeDbx.dbx'
$arx = Join-Path $RouterHome 'prebuilt\2027\Ariadne.AcadNative.arx'
if (-not (Test-Path -LiteralPath $dbx)) { throw "native dbx missing: $dbx" }
if (-not (Test-Path -LiteralPath $arx)) { throw "native arx missing: $arx" }
$binDir = Split-Path -Parent $arx

# ---- Gate 1: pre-existing acad.exe (record; NEVER attach) -------------------
$preIds = @(Get-Process acad -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)

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
$dedicatedOk = $true
$jobDone = $false
$timedOut = $false
$launchedGone = $null
$preStillAlive = @()
$proc = $null

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
  $proc = Start-Process -FilePath $AcadExe -ArgumentList @('/nologo', "`"$StagedDwg`"", '/b', "`"$scr`"") -PassThru
  $launchedPid = $proc.Id
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
    $timedOut = -not $jobDone -and -not $proc.HasExited
    Log "post-poll: jobDone=$jobDone hasExited=$($proc.HasExited) timedOut=$timedOut"
  }
} catch {
  Log "EXCEPTION during launch/poll: $($_.Exception.Message)"
} finally {
  # ---- teardown: close ONLY the launched PID (Stop-Process, then a raw
  # taskkill.exe /T /F last resort) -- wrapped so a teardown failure can never
  # prevent the result file below from being written (no silent hang/no result).
  $env:ARIADNE_NATIVE_JOB_ARGS = $null
  if ($launchedPid) {
    $stillRunning = $false
    try { $stillRunning = [bool](Get-Process -Id $launchedPid -ErrorAction SilentlyContinue) } catch {}
    if ($stillRunning) {
      Log "closing launched PID $launchedPid (Stop-Process)"
      try { Stop-Process -Id $launchedPid -Force -ErrorAction Stop; Log "Stop-Process ok" }
      catch { Log "Stop-Process failed: $($_.Exception.Message)" }
      Start-Sleep -Seconds 1
      $stillThere = $false
      try { $stillThere = [bool](Get-Process -Id $launchedPid -ErrorAction SilentlyContinue) } catch {}
      if ($stillThere) {
        Log "PID $launchedPid still alive after Stop-Process; taskkill fallback (/T /F)"
        try { & taskkill.exe /PID $launchedPid /T /F 2>&1 | ForEach-Object { Log "taskkill: $_" } } catch { Log "taskkill invocation failed: $($_.Exception.Message)" }
        Start-Sleep -Seconds 1
      }
    }
  }

  $postIds = @()
  try { $postIds = @(Get-Process acad -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id) } catch {}
  $launchedGone = ($null -eq $launchedPid) -or ($postIds -notcontains $launchedPid)
  $preStillAlive = @($preIds | Where-Object { $postIds -contains $_ })

  # ---- read back job_out + security before/after ---------------------------
  $jobOutObj = $null
  if (Test-Path -LiteralPath $jobOut) {
    try { $jobOutObj = Get-Content -LiteralPath $jobOut -Raw -Encoding UTF8 | ConvertFrom-Json } catch { Log "job_out.json parse failed: $($_.Exception.Message)" }
  }
  $secBeforeLines = if (Test-Path -LiteralPath $secBefore) { Get-Content -LiteralPath $secBefore } else { @() }
  $secAfterLines  = if (Test-Path -LiteralPath $secAfter)  { Get-Content -LiteralPath $secAfter }  else { @() }
  $secureloadBefore = if ($secBeforeLines.Count -ge 1) { $secBeforeLines[0] } else { $null }
  $trustedpathsBefore = if ($secBeforeLines.Count -ge 2) { $secBeforeLines[1] } else { $null }
  $secureloadAfter = if ($secAfterLines.Count -ge 1) { $secAfterLines[0] } else { $null }
  $trustedpathsAfter = if ($secAfterLines.Count -ge 2) { $secAfterLines[1] } else { $null }
  $securityRestored = ($secureloadBefore -eq $secureloadAfter) -and ($trustedpathsBefore -eq $trustedpathsAfter) -and ($null -ne $secureloadBefore)

  $status = if ($jobDone -and $jobOutObj) { 'ok' } elseif (-not $dedicatedOk) { 'blocked' } elseif ($timedOut) { 'timeout' } else { 'error' }
  $result = [ordered]@{
    schema = 'ariadne.cad_os.attended_job_result.v1'
    run_id = $runId
    status = $status
    operation = $Operation
    launched_pid = $launchedPid
    dedicated_instance = $dedicatedOk
    timed_out = $timedOut
    launched_pid_closed = $launchedGone
    pre_existing_pids = $preIds
    pre_existing_still_alive = $preStillAlive
    user_session_touched = [bool]($preStillAlive.Count -lt $preIds.Count)
    job_in = $jobIn
    job_out = $jobOut
    job_out_present = (Test-Path -LiteralPath $jobOut)
    result = $jobOutObj
    security = [ordered]@{
      secureload_before = $secureloadBefore; secureload_after = $secureloadAfter
      trustedpaths_before = $trustedpathsBefore; trustedpaths_after = $trustedpathsAfter
      restored = $securityRestored
    }
    error = if ($status -eq 'blocked') { 'GATE1 FAIL: launched PID collides with a pre-existing session; aborted without driving.' }
            elseif ($status -eq 'timeout') { "no job_out.json within ${TimeoutSec}s and process did not exit on its own" }
            else { $null }
  }
  WriteJson $result (Join-Path $RunDir 'attended_job_result.json')
  Log '--- attended_job_result ---'
  $result | ConvertTo-Json -Depth 12
}
