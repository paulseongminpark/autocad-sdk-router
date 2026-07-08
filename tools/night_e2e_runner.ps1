# night_e2e_runner.ps1 -- detached overnight E2E roundtrip chain (2026-07-08).
# Registered loop: see D:\dev\_ariadne\docs\v3\v3-build\loop-fragments\claude_code_e2e-roundtrip-night.yaml
#
# Discipline (octorun skill):
#  - disk-first reporting: every stage transition lands in night_state.json (atomic
#    temp+move) and night_log.jsonl BEFORE the next action runs.
#  - payload-truth liveness: night_state.json carries a strictly monotonic `seq`
#    plus per-stage artifact paths+bytes -- consumers assert content, not mtime.
#  - terminal-state vocabulary (never lie): success | clean_no_op | blocked |
#    approval_required | exhausted | no_progress.
#  - NO git writes. NO original-CAD writes (capstone stages copies; original 1.dwg
#    sha is re-verified at the end and a mismatch forces overall=blocked).
param(
  [string]$RepoRoot = 'D:\dev\99_tools\autocad-sdk-router',
  [string]$NightId = 'night_20260708'
)
$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$Py = 'C:\Users\PAUL\AppData\Local\Programs\Python\Python312\python.exe'
$Dwg = 'D:\dev\.build\1.dwg'
$DwgSha = '14EB65EB292D8A07F38AB5662DCAFE9761C6185BC5FF0C8A9A008BE15B598961'
$Seed = Join-Path $RepoRoot 'tests\fixtures\blank_seed.dwg'
$NightDir = Join-Path $RepoRoot ("runs\" + $NightId)
$StateFile = Join-Path $NightDir 'night_state.json'
$LogFile = Join-Path $NightDir 'night_log.jsonl'
$ReportDir = Join-Path $RepoRoot 'reports\e2e_roundtrip_20260708'
New-Item -ItemType Directory -Force -Path $NightDir, $ReportDir | Out-Null
Set-Location $RepoRoot

$script:Seq = 0
$script:Stages = [System.Collections.Generic.List[object]]::new()

function Write-State([string]$Overall = 'running') {
  $script:Seq += 1
  $doc = [ordered]@{
    schema = 'ariadne.night_run_state.v1'; night_id = $NightId; seq = $script:Seq
    pid = $PID; updated_at = (Get-Date -Format o); overall = $Overall
    stages = $script:Stages
  }
  $tmp = $StateFile + '.tmp'
  $doc | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $tmp -Encoding utf8
  Move-Item -LiteralPath $tmp -Destination $StateFile -Force
}
function Add-Log([string]$Event, [object]$Detail) {
  $line = [ordered]@{ ts = (Get-Date -Format o); seq = $script:Seq; event = $Event; detail = $Detail }
  ($line | ConvertTo-Json -Depth 6 -Compress) | Add-Content -LiteralPath $LogFile -Encoding utf8
}
function Get-ArtifactInfo([string[]]$Paths) {
  @($Paths | ForEach-Object {
    if (Test-Path -LiteralPath $_) { @{ path = $_; bytes = (Get-Item -LiteralPath $_).Length } }
    else { @{ path = $_; bytes = $null } }
  })
}
function Start-Stage([string]$Id) {
  $st = [ordered]@{ id = $Id; status = 'running'; started_at = (Get-Date -Format o); ended_at = $null; artifacts = @(); detail = $null }
  $script:Stages.Add($st); Write-State; Add-Log 'stage_start' @{ stage = $Id }
  return $st
}
function End-Stage($St, [string]$Status, [string]$Detail, [string[]]$Artifacts = @()) {
  $St.status = $Status; $St.ended_at = (Get-Date -Format o); $St.detail = $Detail
  $St.artifacts = Get-ArtifactInfo $Artifacts
  Write-State; Add-Log 'stage_end' @{ stage = $St.id; status = $Status; detail = $Detail }
}
function Invoke-Py([string[]]$PyArgs, [string]$StdoutLog) {
  Add-Log 'py_start' @{ args = ($PyArgs -join ' ') }
  & $Py @PyArgs *> $StdoutLog
  $code = $LASTEXITCODE
  Add-Log 'py_end' @{ args = ($PyArgs -join ' '); exit = $code }
  return $code
}

Write-State; Add-Log 'night_start' @{ repo = $RepoRoot }

# ---------- S0: watch R2 to completion; relaunch fresh if it dies ----------
$s0 = Start-Stage 'S0_r2_watch'
$r2Dir = Join-Path $RepoRoot 'runs\e2e_1dwg_R2_20260708'
$r2Verdict = Join-Path $r2Dir 'verdict.json'
$deadline = (Get-Date).AddHours(5)
$lastCount = -1; $lastGrowth = Get-Date; $relaunched = $false
while ($true) {
  if (Test-Path -LiteralPath $r2Verdict) { break }
  if ((Get-Date) -gt $deadline) { break }
  $applyDir = Join-Path $r2Dir 'regen\apply'
  $count = 0
  if (Test-Path -LiteralPath $applyDir) { $count = (Get-ChildItem -LiteralPath $applyDir -Directory | Measure-Object).Count }
  if ($count -ne $lastCount) { $lastCount = $count; $lastGrowth = Get-Date }
  elseif (-not $relaunched -and ((Get-Date) - $lastGrowth).TotalMinutes -gt 20) {
    # R2 (session-bound) died mid-run: relaunch the SAME experiment into a fresh dir.
    Add-Log 'r2_declared_dead' @{ ops_applied = $count }
    $relaunched = $true
    $r2Dir = Join-Path $RepoRoot 'runs\e2e_1dwg_R2b_20260708'
    $r2Verdict = Join-Path $r2Dir 'verdict.json'
    $code = Invoke-Py @('tools\full_roundtrip_capstone.py', '--dwg', $Dwg, '--seed', $Seed,
      '--out-dir', 'runs\e2e_1dwg_R2b_20260708', '--max-def-entities-per-block', '300',
      '--with-records', '--skip-identity') (Join-Path $NightDir 'r2b_stdout.log')
    Add-Log 'r2b_finished' @{ exit = $code }
    break
  }
  Write-State; Start-Sleep -Seconds 60
}
if (Test-Path -LiteralPath $r2Verdict) {
  End-Stage $s0 'success' ("R2 verdict present (relaunched=" + $relaunched + ", dir=" + $r2Dir + ")") @($r2Verdict, (Join-Path $r2Dir 'summary.json'))
} else {
  End-Stage $s0 'blocked' 'no verdict.json within 5h watch window' @()
}

# ---------- S1: fidelity report on the completed R2 run ----------
$s1 = Start-Stage 'S1_r2_report'
if ($s0.status -eq 'success') {
  $r2Json = Join-Path $ReportDir 'R2_fidelity_report.json'
  $r2Md = Join-Path $ReportDir 'R2_FIDELITY_REPORT.md'
  $code = Invoke-Py @('tools\roundtrip_report.py', '--run-dir', $r2Dir, '--out-json', $r2Json,
    '--out-md', $r2Md, '--harmless-rules', 'config\roundtrip_harmless_rules.json') (Join-Path $NightDir 's1_stdout.log')
  if ((Test-Path $r2Json) -and (Test-Path $r2Md)) { End-Stage $s1 'success' ("report written (exit=" + $code + ")") @($r2Json, $r2Md) }
  else { End-Stage $s1 'blocked' ("report tool exit=" + $code + ", outputs missing") @() }
} else { End-Stage $s1 'no_progress' 'upstream S0 not successful' @() }

# ---------- S2: batching support probe ----------
$s2 = Start-Stage 'S2_batch_probe'
$helpOut = Join-Path $NightDir 's2_help.log'
[void](Invoke-Py @('tools\full_roundtrip_capstone.py', '--help') $helpOut)
$batchSupported = (Test-Path $helpOut) -and ((Get-Content -LiteralPath $helpOut -Raw) -match '--batch-size')
End-Stage $s2 ($(if ($batchSupported) { 'success' } else { 'blocked' })) ("batch-size supported=" + $batchSupported) @($helpOut)

# ---------- S3: live batched-vs-perop equivalence gate ----------
$s3 = Start-Stage 'S3_batch_equivalence'
$equivOk = $false
if ($batchSupported) {
  $common = @('--dwg', $Dwg, '--seed', $Seed, '--kinds', 'line,circle,text,dimension,lwpolyline,block_reference',
    '--per-kind-limit', '3', '--max-def-entities-per-block', '100', '--with-records', '--skip-identity')
  $codeA = Invoke-Py (@('tools\full_roundtrip_capstone.py') + $common + @('--out-dir', 'runs\e2e_1dwg_R1c_perop_20260708')) (Join-Path $NightDir 's3_perop.log')
  $codeB = Invoke-Py (@('tools\full_roundtrip_capstone.py') + $common + @('--out-dir', 'runs\e2e_1dwg_R1c_batched_20260708', '--batch-size', '6')) (Join-Path $NightDir 's3_batched.log')
  $equivJson = Join-Path $NightDir 'batch_equivalence.json'
  $codeE = Invoke-Py @('tools\batch_equivalence_check.py', 'runs\e2e_1dwg_R1c_perop_20260708',
    'runs\e2e_1dwg_R1c_batched_20260708', '--out-json', $equivJson) (Join-Path $NightDir 's3_equiv.log')
  $equivOk = ($codeE -eq 0)
  End-Stage $s3 ($(if ($equivOk) { 'success' } else { 'blocked' })) ("perop_exit=" + $codeA + " batched_exit=" + $codeB + " equiv_exit=" + $codeE) @($equivJson)
} else { End-Stage $s3 'no_progress' 'batching unsupported (S2)' @() }

# ---------- S4: batched FULL regen incl. the giant block (the 74h -> hours bet) ----------
$s4 = Start-Stage 'S4_full_regen'
$r3Dir = Join-Path $RepoRoot 'runs\e2e_1dwg_R3_full_20260708'
if ($equivOk) {
  $args4 = @('tools\full_roundtrip_capstone.py', '--dwg', $Dwg, '--seed', $Seed,
    '--out-dir', 'runs\e2e_1dwg_R3_full_20260708', '--max-def-entities-per-block', '25000',
    '--batch-size', '100', '--with-records', '--skip-identity')
  $proc = Start-Process -FilePath $Py -ArgumentList $args4 -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $NightDir 's4_stdout.log') `
    -RedirectStandardError (Join-Path $NightDir 's4_stderr.log')
  $s4Deadline = (Get-Date).AddHours(9)
  while (-not $proc.HasExited -and (Get-Date) -lt $s4Deadline) { Write-State; Start-Sleep -Seconds 120 }
  if (-not $proc.HasExited) {
    try { $proc.Kill() } catch {}
    End-Stage $s4 'exhausted' 'killed at 9h wall-clock budget' @((Join-Path $r3Dir 'summary.json'))
  } else {
    $v3 = Join-Path $r3Dir 'verdict.json'
    if (Test-Path $v3) { End-Stage $s4 'success' ("exit=" + $proc.ExitCode + " (2 = honest gate block is acceptable)") @($v3, (Join-Path $r3Dir 'summary.json')) }
    else { End-Stage $s4 'blocked' ("exit=" + $proc.ExitCode + ", no verdict.json") @((Join-Path $r3Dir 'summary.json')) }
  }
} else { End-Stage $s4 'no_progress' 'equivalence gate did not pass (S3)' @() }

# ---------- S5: fidelity report on R3 ----------
$s5 = Start-Stage 'S5_r3_report'
if ($s4.status -eq 'success') {
  $r3Json = Join-Path $ReportDir 'R3_fidelity_report.json'
  $r3Md = Join-Path $ReportDir 'R3_FIDELITY_REPORT.md'
  $code = Invoke-Py @('tools\roundtrip_report.py', '--run-dir', $r3Dir, '--out-json', $r3Json,
    '--out-md', $r3Md, '--harmless-rules', 'config\roundtrip_harmless_rules.json') (Join-Path $NightDir 's5_stdout.log')
  if ((Test-Path $r3Json) -and (Test-Path $r3Md)) { End-Stage $s5 'success' ("report written (exit=" + $code + ")") @($r3Json, $r3Md) }
  else { End-Stage $s5 'blocked' ("report tool exit=" + $code) @() }
} else { End-Stage $s5 'no_progress' 'no successful R3 run' @() }

# ---------- S6: corpus census sweep (R4 anti-overfitting stage, read-only lane) ----------
$s6 = Start-Stage 'S6_corpus_census'
$dwgList = Join-Path $NightDir 'corpus_dwgs.txt'
$corpus = @(Get-ChildItem 'D:\dev\.build\*.dwg', 'D:\dev\_ariadne\alm\build\*.dwg' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName -Unique)
if ($corpus.Count -gt 0) {
  $corpus | Set-Content -LiteralPath $dwgList -Encoding utf8
  $code = Invoke-Py @('tools\roundtrip_corpus_sweep.py', '--dwg-list', $dwgList,
    '--out-root', 'runs\corpus_census_20260708', '--python', $Py) (Join-Path $NightDir 's6_stdout.log')
  $sumJson = Join-Path $RepoRoot 'runs\corpus_census_20260708\corpus_census_summary.json'
  if (Test-Path $sumJson) { End-Stage $s6 'success' ("swept " + $corpus.Count + " dwgs (exit=" + $code + ")") @($sumJson) }
  else { End-Stage $s6 'blocked' ("sweep exit=" + $code + ", no summary") @($dwgList) }
} else { End-Stage $s6 'clean_no_op' 'no corpus dwgs found' @() }

# ---------- S7: runs evidence index ----------
$s7 = Start-Stage 'S7_runs_index'
$idxMd = Join-Path $ReportDir 'RUNS_INDEX.md'
$idxJson = Join-Path $ReportDir 'RUNS_INDEX.json'
$code = Invoke-Py @('tools\roundtrip_runs_index.py', '--runs-root', 'runs', '--out-md', $idxMd, '--out-json', $idxJson) (Join-Path $NightDir 's7_stdout.log')
if ((Test-Path $idxMd) -and (Test-Path $idxJson)) { End-Stage $s7 'success' ("index written (exit=" + $code + ")") @($idxMd, $idxJson) }
else { End-Stage $s7 'blocked' ("index tool exit=" + $code) @() }

# ---------- Final: original-immutability audit + overall fold (worst-of) ----------
$shaNow = (Get-FileHash -LiteralPath $Dwg -Algorithm SHA256).Hash
$originalIntact = ($shaNow -eq $DwgSha)
Add-Log 'original_audit' @{ intact = $originalIntact; sha = $shaNow }
$rank = @{ 'success' = 0; 'clean_no_op' = 1; 'no_progress' = 2; 'exhausted' = 3; 'approval_required' = 4; 'blocked' = 5 }
$worst = ($script:Stages | ForEach-Object { $_.status } | Sort-Object { $rank[$_] } | Select-Object -Last 1)
if (-not $originalIntact) { $worst = 'blocked' }
Write-State $worst
Add-Log 'night_end' @{ overall = $worst; original_intact = $originalIntact }
