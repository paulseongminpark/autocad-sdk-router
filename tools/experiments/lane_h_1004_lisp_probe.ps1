<#
Lane H (CADOS closeout, wave0 follow-up): AutoLISP entmod path for writing
binary xdata (DXF group code 1004) -- the alternate-path experiment ordered
after Lane E's ObjectARX setXData attempt (see build_log.md "Lane E (closeout
follow-up wave)"). Lane E proved: writing a NON-EMPTY 1004 chunk via ARX
setXData (both acutBuildList and a manual acutNewRb construction) makes
AutoCAD 2027's OWN reader crash (0xC0000005) on the VERY NEXT reopen, even
though an independent reader (LibreDWG) shows the saved bytes are byte-perfect
-- i.e. the crash is inside AutoCAD's own EED reconstruction, not in anything
the write side controls. A 0-byte 1004 chunk round-trips cleanly. Verdict:
BLOCKED at the ARX level.

This script asks the SAME question through a completely different write path:
raw AutoLISP entmod/entget, never touching ObjectARX's setXData at all. Key
unknown resolved empirically (AutoLISP has no dedicated "binary" datatype):
whether entmod even ACCEPTS a value for group 1004, and in what Lisp shape.

Three independent stages, each on its OWN staged copy of the fixture (so one
stage's entmod attempt can never contaminate another stage's saved file):
  stageA_string1004   -- 1004 value given as a plain AutoLISP STRING ("Hello").
  stageB_listint1004  -- 1004 value given as a LIST OF INTEGERS (72 101 108
                         108 111 == "Hello" byte-for-byte) -- the AutoLISP
                         Reference's documented binary-chunk representation.
  stageC_control_1000 -- group 1000 (string) ONLY, no 1004 at all -- proves
                         this script's own write/reopen/readback plumbing is
                         sound independent of the 1004 question (mirrors Lane
                         E's "control test" rigor).

For each stage: WRITE (entmod + immediate in-session readback + QSAVE) in one
accoreconsole process, then REOPEN (a SEPARATE, fresh accoreconsole process,
handent-by-handle + entget readback, no save) in a second process -- mirrors
Lane E's two-process write/reopen/crash-detection methodology exactly.

Deliberately duplicates (in miniature) tools/autocad-router.ps1's
Resolve-AcadEnginePath / Invoke-AccoreScr staging discipline (ASCII staging
dir, forward-slash paths, SECURELOAD 0, `/i /s` accoreconsole invocation)
rather than dot-sourcing the production router file -- keeps this one-off
Lane H experiment fully isolated from the canonical router and from Lane G's
concurrent C++ wave. NOT wired into the router, cadctl, or any production op.
Original fixture is never opened directly -- only ASCII-staged copies -- and
its sha256 is verified unchanged before AND after every stage.
#>

param(
  [string]$RouterHome = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
)

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'

$Fixture = Join-Path $RouterHome 'tests\fixtures\native_sample.dwg'
$ExpectedSha = 'eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76'
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$RunOut = Join-Path $RouterHome ("runs\lane_h_1004_lisp_probe_{0}" -f $Stamp)
New-Item -ItemType Directory -Force -Path $RunOut | Out-Null

function Get-Sha256Hex {
  param([string]$Path)
  (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLower()
}

if (-not (Test-Path -LiteralPath $Fixture)) {
  throw "Fixture missing: $Fixture"
}
$shaBefore = Get-Sha256Hex -Path $Fixture
if ($shaBefore -ne $ExpectedSha) {
  throw "Fixture sha256 mismatch BEFORE any work: got $shaBefore expected $ExpectedSha -- refusing to proceed."
}

function Resolve-AcadEngine {
  # Miniature duplicate of autocad-router.ps1's Resolve-AcadEnginePath.
  # Deliberately NOT dot-sourcing the production router (isolation).
  if (-not [string]::IsNullOrWhiteSpace($env:ARIADNE_ACAD_ENGINE_PATH) -and (Test-Path -LiteralPath $env:ARIADNE_ACAD_ENGINE_PATH)) {
    return $env:ARIADNE_ACAD_ENGINE_PATH
  }
  $bases = @($env:ProgramW6432, ${env:ProgramFiles}, 'C:\Program Files') |
    Where-Object { $_ -and (Test-Path -LiteralPath (Join-Path $_ 'Autodesk')) } |
    ForEach-Object { Join-Path $_ 'Autodesk' } | Select-Object -Unique
  foreach ($b in $bases) {
    $hit = Get-ChildItem -LiteralPath $b -Directory -Filter 'AutoCAD 20*' -ErrorAction SilentlyContinue |
      Sort-Object Name -Descending |
      ForEach-Object { Join-Path $_.FullName 'accoreconsole.exe' } |
      Where-Object { Test-Path -LiteralPath $_ } |
      Select-Object -First 1
    if ($hit) { return $hit }
  }
  $cmd = Get-Command accoreconsole.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  throw 'accoreconsole.exe not found on this machine.'
}

$Engine = Resolve-AcadEngine
Write-Host "engine: $Engine"

function Invoke-Accore {
  param([string]$StagedDwg, [string]$ScrPath, [string]$Tag, [string]$RunDir, [int]$TimeoutMs = 90000)
  $stdoutFile = Join-Path $RunDir ("{0}_stdout.txt" -f $Tag)
  $stderrFile = Join-Path $RunDir ("{0}_stderr.txt" -f $Tag)
  $dwgDir = Split-Path -Parent $StagedDwg
  $p = Start-Process -FilePath $Engine -ArgumentList @('/i', $StagedDwg, '/s', $ScrPath) `
    -WorkingDirectory $dwgDir -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile
  $exited = $p.WaitForExit($TimeoutMs)
  if (-not $exited) {
    try { $p.Kill() } catch {}
    return [ordered]@{ ExitCode = -2; Stdout = 'TIMEOUT'; Stderr = '' }
  }
  $stdout = if (Test-Path -LiteralPath $stdoutFile) { Get-Content -LiteralPath $stdoutFile -Raw -ErrorAction SilentlyContinue } else { '' }
  $stderr = if (Test-Path -LiteralPath $stderrFile) { Get-Content -LiteralPath $stderrFile -Raw -ErrorAction SilentlyContinue } else { '' }
  [ordered]@{ ExitCode = $p.ExitCode; Stdout = $stdout; Stderr = $stderr }
}

function Get-Tail {
  param([string]$Text, [int]$N = 10)
  if (-not $Text) { return '' }
  ($Text -split "`r?`n" | Where-Object { $_.Trim() -ne '' } | Select-Object -Last $N) -join ' | '
}

function Invoke-Stage {
  param([string]$StageName, [string]$Xdata1004LispForm, [string]$RunDir)

  $stageDir = Join-Path $RunDir $StageName
  New-Item -ItemType Directory -Force -Path $stageDir | Out-Null
  $stagedDwg = Join-Path $stageDir 'input.dwg'
  Copy-Item -LiteralPath $Fixture -Destination $stagedDwg -Force
  Set-ItemProperty -LiteralPath $stagedDwg -Name IsReadOnly -Value $false

  $markerValue = "${StageName}_marker"
  $xdataTailForm = if ($Xdata1004LispForm) { " $Xdata1004LispForm" } else { '' }

  # ---- WRITE pass ----
  $writeResultTxt = (Join-Path $stageDir 'write_result.txt').Replace('\', '/')
  $writeLsp = Join-Path $stageDir 'write_probe.lsp'
  $lispLines = @(
    '(defun c:LANEHWRITE (/ outfile e ed xdata res rb)',
    "  (setq outfile (open `"$writeResultTxt`" `"w`"))",
    '  (regapp "ARIADNELANEH")',
    '  (entmake (list (cons 0 "LINE") (cons 10 (list 0.0 0.0 0.0)) (cons 11 (list 10.0 0.0 0.0))))',
    '  (setq e (entlast))',
    '  (write-line (strcat "TARGET_HANDLE=" (cdr (assoc 5 (entget e)))) outfile)',
    '  (setq ed (entget e))',
    "  (setq xdata (list -3 (list `"ARIADNELANEH`" (cons 1000 `"$markerValue`")$xdataTailForm)))",
    '  (setq res (vl-catch-all-apply (function entmod) (list (append ed (list xdata)))))',
    '  (if (vl-catch-all-error-p res)',
    '    (write-line (strcat "ENTMOD_ERROR=" (vl-catch-all-error-message res)) outfile)',
    '    (write-line (strcat "ENTMOD_RESULT=" (if res "SUCCESS" "NIL_REJECTED")) outfile)',
    '  )',
    '  (setq rb (vl-catch-all-apply (function entget) (list e (list "ARIADNELANEH"))))',
    '  (if (vl-catch-all-error-p rb)',
    '    (write-line (strcat "INSESSION_READBACK_ERROR=" (vl-catch-all-error-message rb)) outfile)',
    '    (write-line (strcat "INSESSION_READBACK=" (vl-prin1-to-string rb)) outfile)',
    '  )',
    '  (close outfile)',
    '  (princ)',
    ')',
    '(princ)'
  )
  $lispLines | Set-Content -LiteralPath $writeLsp -Encoding ASCII
  $writeLspFwd = $writeLsp.Replace('\', '/')
  $writeScr = Join-Path $stageDir 'write.scr'
  @(
    '(vl-load-com)', '(setvar "SECURELOAD" 0)', '(setvar "FILEDIA" 0)', '(setvar "CMDECHO" 0)',
    "(load `"$writeLspFwd`")", 'LANEHWRITE', '_QSAVE', 'QUIT', ''
  ) | Set-Content -LiteralPath $writeScr -Encoding ASCII

  $writeRun = Invoke-Accore -StagedDwg $stagedDwg -ScrPath $writeScr -Tag 'write' -RunDir $stageDir
  $writeResultPath = Join-Path $stageDir 'write_result.txt'
  $writeResultParsed = if (Test-Path -LiteralPath $writeResultPath) { Get-Content -LiteralPath $writeResultPath -Raw -ErrorAction SilentlyContinue } else { $null }

  $handleMatch = if ($writeResultParsed) { [regex]::Match($writeResultParsed, 'TARGET_HANDLE=(\S+)') } else { $null }
  $targetHandle = if ($handleMatch -and $handleMatch.Success) { $handleMatch.Groups[1].Value } else { $null }

  # ---- REOPEN pass: separate fresh accoreconsole process, no save ----
  $reopenRun = $null
  $reopenResultParsed = $null
  if ($targetHandle) {
    $reopenResultTxt = (Join-Path $stageDir 'reopen_result.txt').Replace('\', '/')
    $reopenLsp = Join-Path $stageDir 'reopen_probe.lsp'
    $reopenLines = @(
      '(defun c:LANEHREOPEN (/ outfile e rb)',
      "  (setq outfile (open `"$reopenResultTxt`" `"w`"))",
      "  (setq e (handent `"$targetHandle`"))",
      '  (if (null e)',
      '    (write-line "HANDENT_FAILED=entity not found by handle" outfile)',
      '    (progn',
      '      (setq rb (vl-catch-all-apply (function entget) (list e (list "ARIADNELANEH"))))',
      '      (if (vl-catch-all-error-p rb)',
      '        (write-line (strcat "REOPEN_READBACK_ERROR=" (vl-catch-all-error-message rb)) outfile)',
      '        (write-line (strcat "REOPEN_READBACK=" (vl-prin1-to-string rb)) outfile)',
      '      )',
      '    )',
      '  )',
      '  (close outfile)',
      '  (princ)',
      ')',
      '(princ)'
    )
    $reopenLines | Set-Content -LiteralPath $reopenLsp -Encoding ASCII
    $reopenLspFwd = $reopenLsp.Replace('\', '/')
    $reopenScr = Join-Path $stageDir 'reopen.scr'
    @(
      '(vl-load-com)', '(setvar "SECURELOAD" 0)', '(setvar "FILEDIA" 0)', '(setvar "CMDECHO" 0)',
      "(load `"$reopenLspFwd`")", 'LANEHREOPEN', 'QUIT', ''
    ) | Set-Content -LiteralPath $reopenScr -Encoding ASCII

    $reopenRun = Invoke-Accore -StagedDwg $stagedDwg -ScrPath $reopenScr -Tag 'reopen' -RunDir $stageDir
    $reopenResultPath = Join-Path $stageDir 'reopen_result.txt'
    $reopenResultParsed = if (Test-Path -LiteralPath $reopenResultPath) { Get-Content -LiteralPath $reopenResultPath -Raw -ErrorAction SilentlyContinue } else { $null }
  }

  [ordered]@{
    stage              = $StageName
    target_handle      = $targetHandle
    write_exit_code    = $writeRun.ExitCode
    write_stdout_tail  = Get-Tail -Text $writeRun.Stdout
    write_stderr_tail  = Get-Tail -Text $writeRun.Stderr
    write_result       = $writeResultParsed
    reopen_exit_code   = if ($reopenRun) { $reopenRun.ExitCode } else { $null }
    reopen_stdout_tail = if ($reopenRun) { Get-Tail -Text $reopenRun.Stdout } else { $null }
    reopen_stderr_tail = if ($reopenRun) { Get-Tail -Text $reopenRun.Stderr } else { $null }
    reopen_result      = $reopenResultParsed
  }
}

$results = @()
$results += Invoke-Stage -StageName 'stageA_string1004' -Xdata1004LispForm '(cons 1004 "Hello")' -RunDir $RunOut
$results += Invoke-Stage -StageName 'stageB_listint1004' -Xdata1004LispForm '(cons 1004 (list 72 101 108 108 111))' -RunDir $RunOut
$results += Invoke-Stage -StageName 'stageC_control_1000' -Xdata1004LispForm '' -RunDir $RunOut

$shaAfter = Get-Sha256Hex -Path $Fixture
$summary = [ordered]@{
  schema                = 'ariadne.lane_h_1004_lisp_probe.v1'
  fixture               = $Fixture
  fixture_sha256_before = $shaBefore
  fixture_sha256_after  = $shaAfter
  fixture_unchanged     = ($shaBefore -eq $shaAfter)
  engine                = $Engine
  run_dir               = $RunOut
  stages                = $results
}
$summaryPath = Join-Path $RunOut 'summary.json'
$summary | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
Write-Host "=== SUMMARY ($summaryPath) ==="
$summary | ConvertTo-Json -Depth 10 | Write-Host
