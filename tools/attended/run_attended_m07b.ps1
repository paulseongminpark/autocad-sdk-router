param(
  [int]$PumpTimeoutSec = 300,
  [int]$RenderWaitSec  = 6
)
$ErrorActionPreference = 'Stop'
# CADOS_M07B attended-GUI harness. Launches a DEDICATED acad.exe (never attaches
# to a pre-existing session), loads the .dbx + .arx, creates an AriadneProbe via
# the ARIADNE_NATIVE_JOB_ARGS env-file channel, zooms to it, opens the Properties
# (OPM) palette with the probe pickfirst-selected, then serves CADAGENT_PUMP on a
# UNIQUE pipe. A screenshot captures the worldDraw circle + OPM "Size" panel; the
# pipe client then proves the live pump + the gated real highlight in a full
# editor. The ORIGINAL golden DWG is only ever copied FROM (never opened/written).
# Three safety gates must pass; only the launched PID is ever closed.

$py    = 'C:\Users\PAUL\AppData\Local\Programs\Python\Python312\python.exe'
$root  = 'D:\dev\99_tools\autocad-sdk-router'
$acad  = 'C:\Program Files\Autodesk\AutoCAD 2027\acad.exe'
$bin   = Join-Path $root 'src\Ariadne.AcadNative\bin\x64\Release'
$ts    = Get-Date -Format 'yyyyMMdd_HHmmss'
$runId = "cados_m07b_attended_$ts"
$runDir   = Join-Path $root "runs\$runId"
$shotDir  = Join-Path $runDir 'screenshots'
$stageDir = Join-Path $root "staging\attended\$runId"
New-Item -ItemType Directory -Force -Path $runDir,$shotDir,$stageDir | Out-Null

function FS([string]$p) { $p -replace '\\','/' }
function WriteJson($obj, $path) { $obj | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $path -Encoding UTF8 }

# ---- Gate 1: pre-existing acad.exe (record; NEVER attach) -------------------
$preIds = @(Get-Process acad -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)

# ---- Gate 2: staged document; original golden READ-ONLY ---------------------
$golden = Join-Path $root 'staging\dwg_20260617_191504\input.dwg'
$shaBefore = (Get-FileHash $golden -Algorithm SHA256).Hash
$stagedDwg = Join-Path $stageDir 'attended.dwg'
Copy-Item $golden $stagedDwg -Force
Set-ItemProperty $stagedDwg -Name IsReadOnly -Value $false
$stagedShaBefore = (Get-FileHash $stagedDwg -Algorithm SHA256).Hash

# ---- Gate 3: unique live channel -------------------------------------------
$pipe = "\\.\pipe\ariadne-cadagent-m07b-$runId"

# probe-create job (env-file channel), result captured for the report
$argsF  = Join-Path $runDir 'live_job_args.json'
$jobIn  = Join-Path $runDir 'job_create_probe.json'
$jobOut = Join-Path $runDir 'job_create_probe_out.json'
('{0}"operation":"extend.customclass.create","cx":150000.0,"cy":350000.0,"cz":0.0,"size":3000.0{1}' -f '{','}') |
    Set-Content -LiteralPath $jobIn -Encoding ASCII
('{0}"job_in":"{1}","job_out":"{2}","host_mode":"full_autocad"{3}' -f '{', (FS $jobIn), (FS $jobOut), '}') |
    Set-Content -LiteralPath $argsF -Encoding ASCII

$dbxFwd = FS (Join-Path $bin 'Ariadne.AcadNativeDbx.dbx')
$arxFwd = FS (Join-Path $bin 'Ariadne.AcadNative.arx')
$trusted = $bin.Replace('\','\\')
$scr = Join-Path $runDir 'attended.scr'
@(
  '(setvar "SECURELOAD" 0)','(setvar "FILEDIA" 0)','(setvar "CMDECHO" 0)',
  "(setvar `"TRUSTEDPATHS`" `"$trusted`")",
  "(arxload `"$dbxFwd`")","(arxload `"$arxFwd`")",
  'ARIADNE_NATIVE_JOB_ARGS',
  '(setq ariadneE (entlast))',
  '(if ariadneE (command "._zoom" "_o" ariadneE ""))',
  '(if ariadneE (sssetfirst nil (ssadd ariadneE)))',
  '(command "._propertiesclose")','(command "._properties")',
  'CADAGENT_PUMP',
  ''
) | Set-Content -LiteralPath $scr -Encoding ASCII

# ---- attended_plan.json (gates recorded BEFORE launch) ----------------------
$plan = [ordered]@{
  schema = 'ariadne.cad_os.m07b.attended_plan.v1'
  run_id = $runId
  acad_exe = $acad
  staged_dwg = $stagedDwg
  original_golden = $golden
  original_golden_sha256_before = $shaBefore
  pipe = $pipe
  pre_existing_acad_pids = $preIds
  host_mode = 'full_autocad'
  gates = [ordered]@{
    dedicated_instance = 'pending (launched PID must differ from pre-existing)'
    staged_document    = (Test-Path $stagedDwg)
    unique_live_channel = ($pipe -like "*$runId*")
  }
}
WriteJson $plan (Join-Path $runDir 'attended_plan.json')

# ---- env for the launched instance ------------------------------------------
$env:ARIADNE_PUMP_PIPE = $pipe
$env:ARIADNE_PUMP_TIMEOUT = "$PumpTimeoutSec"
$env:ARIADNE_CAD_JOB_HOST_MODE = 'full_autocad'
$env:ARIADNE_NATIVE_JOB_ARGS = $argsF

Write-Output "=== M07B attended run: $runId ==="
Write-Output "pre-existing acad PIDs: $($preIds -join ',')"

# ---- launch DEDICATED acad.exe ---------------------------------------------
$proc = Start-Process -FilePath $acad -ArgumentList @('/nologo', "`"$stagedDwg`"", '/b', "`"$scr`"") -PassThru
$launchedPid = $proc.Id
Write-Output "launched dedicated acad PID: $launchedPid"

# Gate 1 enforcement
$dedicatedOk = ($preIds -notcontains $launchedPid)
if (-not $dedicatedOk) {
  Write-Output 'GATE1 FAIL: launched PID collides with a pre-existing session; aborting without driving.'
  $env:ARIADNE_PUMP_PIPE=''; $env:ARIADNE_PUMP_TIMEOUT=''; $env:ARIADNE_CAD_JOB_HOST_MODE=''; $env:ARIADNE_NATIVE_JOB_ARGS=''
  exit 9
}

# ---- wait for the unique pipe to appear (= acad reached CADAGENT_PUMP) -------
$pipeShort = "ariadne-cadagent-m07b-$runId"
$pipeUp = $false
for ($i=0; $i -lt ($PumpTimeoutSec); $i++) {
  Start-Sleep -Seconds 1
  if ([System.IO.Directory]::GetFiles('\\.\pipe\') -match [regex]::Escape($pipeShort)) { $pipeUp = $true; break }
  if ($proc.HasExited) { break }
}
Write-Output "pipe up: $pipeUp (after ~$i s); acad exited early: $($proc.HasExited)"

# ---- screenshot helper (called AFTER the client connects) -------------------
# The client must connect to the single-instance pump pipe PROMPTLY after it
# appears (a long pre-connect delay let the pump's connect window lapse in run 2).
# So we drive the pump first, THEN screenshot: acad stays alive after the pump
# returns, and the probe + OPM (rendered during startup, before the pump) are
# still on screen. PrintWindow targets acad's own HWND (no foreground race);
# PW_RENDERFULLCONTENT=2 captures owner-drawn content. The GPU viewport may render
# dark, but the ribbon + docked OPM "Size" panel prove a real attended GUI.
$shotPath = Join-Path $shotDir 'acad_window.png'
$shotFull = Join-Path $shotDir 'primary_screen.png'
$script:shotTaken = $false
function Invoke-AcadShot {
  if (-not $pipeUp) { return }
  try {
    Add-Type -AssemblyName System.Windows.Forms, System.Drawing
    Add-Type @"
using System;using System.Runtime.InteropServices;
public class Win32pw {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr h,int n);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
    # Resolve acad main window (refresh MainWindowHandle).
    $proc.Refresh()
    $h = $proc.MainWindowHandle
    if ($h -eq [IntPtr]::Zero) { $h = (Get-Process -Id $launchedPid).MainWindowHandle }
    if ($h -ne [IntPtr]::Zero) {
      [Win32pw]::ShowWindowAsync($h,3) | Out-Null   # SW_MAXIMIZE
      [Win32pw]::BringWindowToTop($h) | Out-Null
      [Win32pw]::SetForegroundWindow($h) | Out-Null
      Start-Sleep -Seconds 3
      $r = New-Object Win32pw+RECT
      [Win32pw]::GetWindowRect($h,[ref]$r) | Out-Null
      $w = [Math]::Max(64, $r.Right - $r.Left); $ht = [Math]::Max(64, $r.Bottom - $r.Top)
      # (a) PrintWindow capture of acad's own window
      $bmp = New-Object System.Drawing.Bitmap($w,$ht)
      $g = [System.Drawing.Graphics]::FromImage($bmp)
      $hdc = $g.GetHdc()
      [Win32pw]::PrintWindow($h,$hdc,2) | Out-Null
      $g.ReleaseHdc($hdc); $g.Dispose()
      $bmp.Save($shotPath,[System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
      $script:shotTaken = Test-Path $shotPath
      # (b) screen-region capture of acad's rect (viewport pixels if visible)
      try {
        $bmp2 = New-Object System.Drawing.Bitmap($w,$ht)
        $g2 = [System.Drawing.Graphics]::FromImage($bmp2)
        $g2.CopyFromScreen($r.Left,$r.Top,0,0,$bmp2.Size)
        $bmp2.Save($shotFull,[System.Drawing.Imaging.ImageFormat]::Png)
        $g2.Dispose(); $bmp2.Dispose()
      } catch {}
    } else { Write-Output 'acad MainWindowHandle is 0 (window not yet realized)' }
  } catch { Write-Output "screenshot error: $($_.Exception.Message)" }
}

# ---- drive the pump (pipe client) -------------------------------------------
$client = @'
import sys, json, time, struct
pipe=sys.argv[1]
def frame(op, **kw):
    b=json.dumps({"op":op, **kw}).encode("utf-8"); return struct.pack("<I", len(b))+b
def _readn(f,n):
    buf=b""
    while len(buf)<n:
        c=f.read(n-len(buf))
        if not c: return None
        buf+=c
    return buf
def rd(f):
    h=_readn(f,4)
    if h is None: return None
    n=struct.unpack("<I", h)[0]
    body=_readn(f,n)
    return json.loads(body.decode("utf-8")) if body is not None else None
fh=None
for _ in range(60):
    try: fh=open(pipe,"r+b",buffering=0); break
    except OSError: time.sleep(0.5)
if fh is None: print("CLIENT: could not connect"); sys.exit(1)
def call(op, **kw):
    fh.write(frame(op,**kw)); fh.flush(); r=rd(fh)
    print(op,"->",json.dumps(r,ensure_ascii=False)); return r
res={}
res["echo"]=call("live.echo", message="CADOS_M07B_ATTENDED")
res["status"]=call("live.status")
res["list"]=call("live.list_documents")
res["active"]=call("live.active_document")
res["sel"]=call("live.inspect_selection")
res["hl"]=call("live.highlight_handles", handles=["11935","12B4C"])
res["clr"]=call("live.clear_highlight", handles=["11935","12B4C"])
res["zoom"]=call("live.zoom_to_handles", handles=["11935"])
res["render"]=call("live.render_view")
res["stop"]=call("live.stop")
fh.close()
def g(k): return res.get(k) or {}
checks={
 "echo": g("echo").get("echo")=="CADOS_M07B_ATTENDED",
 "pump_running": g("status").get("pump")=="running",
 "host_full_autocad": g("status").get("host_mode")=="full_autocad",
 "active_ok": g("active").get("status")=="ok",
 "selection_real_path": g("sel").get("status")=="ok",
 "highlight_real": g("hl").get("status")=="ok" and g("hl").get("highlighted",0)>=1,
 "clear_real": g("clr").get("status")=="ok",
 "zoom_deferred": g("zoom").get("status")=="deferred",
 "render_deferred": g("render").get("status")=="deferred",
 "stop_ok": g("stop").get("stopped")==True,
}
allok=all(checks.values())
print("ATTENDED_CHECKS:", json.dumps(checks, ensure_ascii=False))
print("ATTENDED_PUMP_OK:", allok)
json.dump({"checks":checks,"all_ok":allok,"responses":res}, open(sys.argv[2],"w",encoding="utf-8"), ensure_ascii=False, indent=2)
sys.exit(0 if allok else 2)
'@
$cf = Join-Path $runDir 'attended_client.py'
$client | Out-File -LiteralPath $cf -Encoding UTF8
$resultJson = Join-Path $runDir 'attended_pump_result.json'
$clientExit = 99
if ($pipeUp) {
  & $py $cf $pipe $resultJson
  $clientExit = $LASTEXITCODE
} else {
  Write-Output 'pipe never came up; pump not driven.'
}

# ---- screenshot NOW (pump returned; acad still alive with probe + OPM) -------
Invoke-AcadShot
Write-Output "screenshot taken: $($script:shotTaken) -> $shotPath"

# ---- teardown: close ONLY the launched PID ----------------------------------
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

# ---- verify golden + read probe-create result ------------------------------
$shaAfter = (Get-FileHash $golden -Algorithm SHA256).Hash
$goldenUnchanged = ($shaBefore -eq $shaAfter)
$createResult = if (Test-Path $jobOut) { Get-Content $jobOut -Raw } else { '(no create result)' }

$env:ARIADNE_PUMP_PIPE=''; $env:ARIADNE_PUMP_TIMEOUT=''; $env:ARIADNE_CAD_JOB_HOST_MODE=''; $env:ARIADNE_NATIVE_JOB_ARGS=''

# ---- attended_shutdown.json -------------------------------------------------
$shutdown = [ordered]@{
  schema='ariadne.cad_os.m07b.attended_shutdown.v1'; run_id=$runId
  launched_pid=$launchedPid; dedicated_instance=$dedicatedOk
  pipe=$pipe; pipe_up=$pipeUp; client_exit=$clientExit
  screenshot=$shotPath; screenshot_taken=$shotTaken
  launched_pid_closed=$launchedGone
  pre_existing_pids=$preIds; pre_existing_still_alive=$preStillAlive
  user_session_touched=([bool]($preStillAlive.Count -lt $preIds.Count))
  original_golden_sha256_before=$shaBefore; original_golden_sha256_after=$shaAfter
  original_dwg_modified=(-not $goldenUnchanged)
  probe_create_result=$createResult
}
WriteJson $shutdown (Join-Path $runDir 'attended_shutdown.json')

Write-Output '=== RESULT ==='
Write-Output "client exit: $clientExit | launched PID closed: $launchedGone | golden unchanged: $goldenUnchanged"
Write-Output "pre-existing still alive (must equal pre list): $($preStillAlive -join ',') vs pre $($preIds -join ',')"
Write-Output "probe create: $createResult"
Write-Output "run dir: $runDir"
if (Test-Path $resultJson) { Write-Output '--- attended_pump_result ---'; Get-Content $resultJson -Raw }
