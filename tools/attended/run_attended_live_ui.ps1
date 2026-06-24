param(
  [int]$PumpTimeoutSec = 300
)
$ErrorActionPreference = 'Stop'

$py    = 'C:\Users\PAUL\AppData\Local\Programs\Python\Python312\python.exe'
$root  = [System.IO.Path]::GetFullPath("$PSScriptRoot\..\..")
if (-not (Test-Path (Join-Path $root 'src\Ariadne.AcadNative'))) {
  $root = 'D:\dev\99_tools\autocad-sdk-router_wave4x_fast_b_on_fast_a_truth'
}
$acad  = 'C:\Program Files\Autodesk\AutoCAD 2027\acad.exe'
$bin   = Join-Path $root 'src\Ariadne.AcadNative\bin\x64\Release'
$ts    = Get-Date -Format 'yyyyMMdd_HHmmss'
$runId = "w4x_live_ui_attended_$ts"
$runDir   = Join-Path $root "runs\$runId"
$shotDir  = Join-Path $runDir 'screenshots'
$stageDir = Join-Path $root "staging\attended_live_ui\$runId"
New-Item -ItemType Directory -Force -Path $runDir,$shotDir,$stageDir | Out-Null

function FS([string]$p) { $p -replace '\\','/' }
function WriteJson($obj, $path) { $obj | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $path -Encoding UTF8 }

$preIds = @(Get-Process acad -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)

$fixtureDwg = Join-Path $root 'staging\dwg_20260624_134436\input.dwg'
if (-not (Test-Path $fixtureDwg)) {
  $fixtureDwg = 'D:\dev\99_tools\autocad-sdk-router_wave4x_fast_b_on_fast_a_truth\staging\dwg_20260624_134436\input.dwg'
}
$shaBefore = (Get-FileHash $fixtureDwg -Algorithm SHA256).Hash
$stagedDwg = Join-Path $stageDir 'attended.dwg'
Copy-Item $fixtureDwg $stagedDwg -Force
Set-ItemProperty $stagedDwg -Name IsReadOnly -Value $false

$pipe = "\\.\pipe\ariadne-cadagent-live-ui-$runId"

$dbxFwd = FS (Join-Path $bin 'Ariadne.AcadNativeDbx.dbx')
$arxFwd = FS (Join-Path $bin 'Ariadne.AcadNative.arx')
$trusted = $bin.Replace('\','\\')
$scr = Join-Path $runDir 'attended.scr'
@(
  '(setvar "SECURELOAD" 0)','(setvar "FILEDIA" 0)','(setvar "CMDECHO" 0)',
  "(setvar `"TRUSTEDPATHS`" `"$trusted`")",
  "(arxload `"$dbxFwd`")","(arxload `"$arxFwd`")",
  'CADAGENT_PUMP',
  ''
) | Set-Content -LiteralPath $scr -Encoding ASCII

$plan = [ordered]@{
  schema = 'ariadne.cad_os.live_ui.attended_plan.v1'
  run_id = $runId
  acad_exe = $acad
  staged_dwg = $stagedDwg
  fixture_dwg = $fixtureDwg
  fixture_sha256_before = $shaBefore
  pipe = $pipe
  pre_existing_acad_pids = $preIds
  host_mode = 'full_autocad'
  fixture = [ordered]@{
    handle = '119F5'
    subent_type = 'edge'
    subent_index = 1
  }
}
WriteJson $plan (Join-Path $runDir 'attended_plan.json')

$env:ARIADNE_PUMP_PIPE = $pipe
$env:ARIADNE_PUMP_TIMEOUT = "$PumpTimeoutSec"
$env:ARIADNE_CAD_JOB_HOST_MODE = 'full_autocad'

Write-Output "=== Live UI attended run: $runId ==="
Write-Output "pre-existing acad PIDs: $($preIds -join ',')"

$proc = Start-Process -FilePath $acad -ArgumentList @('/nologo', "`"$stagedDwg`"", '/b', "`"$scr`"") -PassThru
$launchedPid = $proc.Id
Write-Output "launched dedicated acad PID: $launchedPid"

$dedicatedOk = ($preIds -notcontains $launchedPid)
if (-not $dedicatedOk) {
  Write-Output 'GATE1 FAIL: launched PID collides with a pre-existing session; aborting without driving.'
  $env:ARIADNE_PUMP_PIPE=''; $env:ARIADNE_PUMP_TIMEOUT=''; $env:ARIADNE_CAD_JOB_HOST_MODE=''
  exit 9
}

$pipeShort = "ariadne-cadagent-live-ui-$runId"
$pipeUp = $false
for ($i=0; $i -lt $PumpTimeoutSec; $i++) {
  Start-Sleep -Seconds 1
  if ([System.IO.Directory]::GetFiles('\\.\pipe\') -match [regex]::Escape($pipeShort)) { $pipeUp = $true; break }
  if ($proc.HasExited) { break }
}
Write-Output "pipe up: $pipeUp (after ~$i s); acad exited early: $($proc.HasExited)"

$shotPath = Join-Path $shotDir 'acad_window.png'
$script:shotTaken = $false
function Invoke-AcadShot {
  if (-not $pipeUp) { return }
  try {
    Add-Type -AssemblyName System.Windows.Forms, System.Drawing
    Add-Type @"
using System;using System.Runtime.InteropServices;
public class Win32lui {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr h,int n);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
    $proc.Refresh()
    $h = $proc.MainWindowHandle
    if ($h -eq [IntPtr]::Zero) { $h = (Get-Process -Id $launchedPid).MainWindowHandle }
    if ($h -ne [IntPtr]::Zero) {
      [Win32lui]::ShowWindowAsync($h,3) | Out-Null
      [Win32lui]::BringWindowToTop($h) | Out-Null
      [Win32lui]::SetForegroundWindow($h) | Out-Null
      Start-Sleep -Seconds 3
      $r = New-Object Win32lui+RECT
      [Win32lui]::GetWindowRect($h,[ref]$r) | Out-Null
      $w = [Math]::Max(64, $r.Right - $r.Left)
      $ht = [Math]::Max(64, $r.Bottom - $r.Top)
      $bmp = New-Object System.Drawing.Bitmap($w,$ht)
      $g = [System.Drawing.Graphics]::FromImage($bmp)
      $hdc = $g.GetHdc()
      [Win32lui]::PrintWindow($h,$hdc,2) | Out-Null
      $g.ReleaseHdc($hdc)
      $g.Dispose()
      $bmp.Save($shotPath,[System.Drawing.Imaging.ImageFormat]::Png)
      $bmp.Dispose()
      $script:shotTaken = Test-Path $shotPath
    }
  } catch { Write-Output "screenshot error: $($_.Exception.Message)" }
}

$cf = Join-Path $root 'tools/attended/attended_live_ui_client.py'
$resultJson = Join-Path $runDir 'attended_pump_result.json'
$clientExit = 99
if ($pipeUp) {
  & $py $cf $pipe $resultJson
  $clientExit = $LASTEXITCODE
} else {
  Write-Output 'pipe never came up; pump not driven.'
}

Invoke-AcadShot
Write-Output "screenshot taken: $($script:shotTaken) -> $shotPath"

Start-Sleep -Seconds 2
$stillRunning = -not $proc.HasExited
if ($stillRunning) {
  try { Stop-Process -Id $launchedPid -Force -ErrorAction Stop; Write-Output "closed launched PID $launchedPid" }
  catch { Write-Output "could not close launched PID: $($_.Exception.Message)" }
}
Start-Sleep -Seconds 2
$postIds = @(Get-Process acad -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$launchedGone = ($postIds -notcontains $launchedPid)
$preStillAlive = @($preIds | Where-Object { $postIds -contains $_ })

$shaAfter = (Get-FileHash $fixtureDwg -Algorithm SHA256).Hash
$goldenUnchanged = ($shaBefore -eq $shaAfter)

$env:ARIADNE_PUMP_PIPE=''; $env:ARIADNE_PUMP_TIMEOUT=''; $env:ARIADNE_CAD_JOB_HOST_MODE=''

$shutdown = [ordered]@{
  schema='ariadne.cad_os.live_ui.attended_shutdown.v1'
  run_id=$runId
  launched_pid=$launchedPid
  dedicated_instance=$dedicatedOk
  pipe=$pipe
  pipe_up=$pipeUp
  client_exit=$clientExit
  screenshot=$shotPath
  screenshot_taken=$shotTaken
  launched_pid_closed=$launchedGone
  pre_existing_pids=$preIds
  pre_existing_still_alive=$preStillAlive
  user_session_touched=([bool]($preStillAlive.Count -lt $preIds.Count))
  fixture_sha256_before=$shaBefore
  fixture_sha256_after=$shaAfter
  original_dwg_modified=(-not $goldenUnchanged)
}
WriteJson $shutdown (Join-Path $runDir 'attended_shutdown.json')

Write-Output '=== RESULT ==='
Write-Output "client exit: $clientExit | launched PID closed: $launchedGone | fixture unchanged: $goldenUnchanged"
Write-Output "run dir: $runDir"
if (Test-Path $resultJson) {
  Write-Output '--- attended_pump_result ---'
  Get-Content $resultJson -Raw
}
exit $clientExit
