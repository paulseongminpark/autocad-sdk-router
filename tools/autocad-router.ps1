param(
  [ValidateSet('status', 'select', 'run', 'explain')]
  [string]$Action = 'status',
  [string]$Intent = 'auto',
  [string]$Route = '',
  [string]$InputPath = '',
  [string]$InputPath2 = '',
  [string]$Out = '',
  [string]$Script = '',
  [string]$JobPath = '',
  [ValidateSet('summary', 'geometry_native', 'objectdbx', 'truth_chain')]
  [string]$ExtractMode = 'truth_chain',
  [ValidateSet('', 'read', 'write_copy', 'write_original', 'live_edit')]
  [string]$WriteMode = '',
  [ValidateSet('auto', 'coreconsole', 'full_autocad')]
  [string]$HostMode = 'auto',
  [string]$Operation = '',
  [string]$RouterHome = '',
  [string]$ConfigPath = '',
  [string]$PythonExe = ''
)

# =============================================================================
# AutoCAD SDK Router (local rebuild) -- single entrypoint, 12-route spec.
# Home: D:\dev\99_tools\autocad-sdk-router
#
# -Action status  : LIVE-probe every route's tool availability -> status JSON.
# -Action select  : map -Intent (or -Route) to a route, honor availability + fallback.
# -Action run      : select then actually execute the route against -InputPath / -Out.
# -Action explain  : select + dump full capability metadata.
#
# DWG work is the AutoCAD SDK control plane: native ARX/DBX first, with
# .NET/LISP/CoreConsole/full-AutoCAD adapters. write_original/live_edit are
# explicit modes; no fake availability: a route is available only if its
# required tools really resolve (probe_routes.py).
# =============================================================================

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RouterHome)) {
  $RouterHome = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
}
if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
  $ConfigPath = Join-Path $RouterHome 'config\autocad_router_capabilities.json'
}
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
  $PythonExe = 'C:\Users\PAUL\AppData\Local\Programs\Python\Python312\python.exe'
  if (-not (Test-Path -LiteralPath $PythonExe)) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $PythonExe = $cmd.Source }
  }
}

$ProbeScript = Join-Path $RouterHome 'tools\probe_routes.py'
$RunRouteScript = Join-Path $RouterHome 'tools\run_route.py'
$LatestStatusPath = Join-Path $RouterHome 'reports\autocad_router_status_latest.json'
$RunsDir = Join-Path $RouterHome 'runs'
$StagingDir = Join-Path $RouterHome 'staging'
$NativeExtractorProject = Join-Path $RouterHome 'src\Ariadne.DwgGeometryExtractor\Ariadne.DwgGeometryExtractor.csproj'
$NativeAcadBinDir = if (-not [string]::IsNullOrWhiteSpace($env:ARIADNE_NATIVE_ACAD_BIN_DIR)) { $env:ARIADNE_NATIVE_ACAD_BIN_DIR } else { Join-Path $RouterHome 'src\Ariadne.AcadNative\bin\x64\Release' }
. (Join-Path $RouterHome 'tools\fallback_safe_surface.ps1')

function Read-JsonFile {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) { throw "Missing JSON file: $Path" }
  Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Write-Json {
  param([object]$Payload, [string]$Path = '')
  $json = $Payload | ConvertTo-Json -Depth 16
  if (-not [string]::IsNullOrWhiteSpace($Path)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null
    $json | Set-Content -LiteralPath $Path -Encoding UTF8
  }
  $json
}

function Resolve-NativeExtractorDll {
  $projectDir = Split-Path -Parent $NativeExtractorProject
  $dll = Join-Path $projectDir 'bin\Release\net10.0-windows\Ariadne.DwgGeometryExtractor.dll'
  if (Test-Path -LiteralPath $dll) {
    return (Resolve-Path -LiteralPath $dll).Path
  }
  if (-not (Test-Path -LiteralPath $NativeExtractorProject)) {
    throw "Native DWG geometry extractor project missing: $NativeExtractorProject"
  }
  $dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
  if (-not $dotnet) {
    throw 'dotnet SDK not found; cannot build native DWG geometry extractor.'
  }
  $raw = & $dotnet.Source build $NativeExtractorProject -c Release --nologo 2>&1
  $code = $LASTEXITCODE
  if ($code -ne 0 -or -not (Test-Path -LiteralPath $dll)) {
    $tail = (($raw | Select-Object -Last 40) -join "`n")
    throw "Native DWG geometry extractor build failed (exit $code): $tail"
  }
  return (Resolve-Path -LiteralPath $dll).Path
}

function Resolve-NativeAcadModule {
  param([string]$LeafName)
  $path = Join-Path $NativeAcadBinDir $LeafName
  if (-not (Test-Path -LiteralPath $path)) {
    throw "Native AutoCAD module missing: $path"
  }
  return (Resolve-Path -LiteralPath $path).Path
}

function Get-CadJobOperation {
  param([string]$Path)
  try {
    $job = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    return "$($job.operation)"
  }
  catch {
    return ''
  }
}

function Get-CadJobJigPointLine {
  param([string]$Path)
  try {
    $job = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    $point = $null
    if ($job.PSObject.Properties.Name -contains 'args' -and $null -ne $job.args) {
      if ($job.args.PSObject.Properties.Name -contains 'point') {
        $point = $job.args.point
      }
    }
    if ($null -eq $point -and $job.PSObject.Properties.Name -contains 'point') {
      $point = $job.point
    }
    if ($null -eq $point) {
      return $null
    }

    $z = 0.0
    if ($point.PSObject.Properties.Name -contains 'z') {
      $z = [double]$point.z
    }
    return ('{0} {1} {2}' -f [double]$point.x, [double]$point.y, $z)
  }
  catch {
    return $null
  }
}

function Test-NativeP1CadJobOperation {
  param([string]$OperationName)
  if ([string]::IsNullOrWhiteSpace($OperationName)) { return $false }

  # WAVE4X: any implemented registry op explicitly bound to ARIADNE_NATIVE_JOB is
  # a native cad-job surface, even if it landed after the original fixed P1 list.
  try {
    $registryPath = Join-Path $RouterHome 'config\operations.v2.json'
    $registry = Read-JsonFile -Path $registryPath
    $record = @($registry.operations | Where-Object {
      "$($_.id)" -eq $OperationName -or "$($_.operation)" -eq $OperationName
    } | Select-Object -First 1)
    if ($record) {
      $status = "$($record.status)"
      $lane = if ($record.handler) { "$($record.handler.router_lane)" } else { '' }
      if ((@('implemented', 'wired') -contains $status) -and $lane -eq 'ARIADNE_NATIVE_JOB') {
        return $true
      }
    }
  }
  catch {
    # Fall through to the frozen explicit allow-list below.
  }

  return @(
    'inspect.database.summary',
    'inspect.database.graph',
    'write.layer.create',
    'write.entity.line',
    'write.entity.circle',
    'inspect.entity.count',
    'write.xrecord.set',
    'inspect.xrecord.get',
    'write.xdata.set',
    'inspect.xdata.get',
    'write.block.simple_create',
    'write.block.insert',
    'inspect.block.count',
    'write.layout.create',
    'inspect.layout.list',
    'inspect.xref.list',
    'inspect.runtime.capabilities',
    'live.reactor.enable',
    'inspect.reactor.registry',
    'live.reactor.disable',
    'inspect.overrule.registry',
    'live.overrule.enable',
    'live.overrule.disable',
    'inspect.jig.host_support',
    'live.jig.point_probe',
    'extend.customclass.create',
    'inspect.customclass.count',
    'extend.customobject.create',
    'inspect.customobject.count',
    'inspect.protocol.queryx'
  ) -contains $OperationName
}

function Test-NativeAcadModules {
  param([object]$Capabilities, [bool]$ProbeCoreConsoleLoad = $false)
  $cap = @($Capabilities.routes | Where-Object { $_.id -eq 'dwg_truth_autocad' }) | Select-Object -First 1
  $engine = if ($cap) { $cap.engine_path } else { '' }
  $dbx = Join-Path $NativeAcadBinDir 'Ariadne.AcadNativeDbx.dbx'
  $crx = Join-Path $NativeAcadBinDir 'Ariadne.AcadNative.crx'
  $arx = Join-Path $NativeAcadBinDir 'Ariadne.AcadNative.arx'
  $blank = Join-Path $RouterHome 'test_native\blank.dwg'
  $moduleRecords = @($dbx, $crx, $arx | ForEach-Object {
    [ordered]@{
      path = $_
      exists = Test-Path -LiteralPath $_
      bytes = if (Test-Path -LiteralPath $_) { (Get-Item -LiteralPath $_).Length } else { 0 }
    }
  })

  if (-not $ProbeCoreConsoleLoad) {
    return [ordered]@{
      status = if (@($moduleRecords | Where-Object { -not $_.exists }).Count -eq 0) { 'PRESENT' } else { 'MISSING' }
      modules = $moduleRecords
      coreconsole_load = [ordered]@{
        status = 'NOT_RUN'
        detail = 'Core Console native module load probe runs only for -Action status.'
      }
    }
  }

  $canProbe = (Test-Path -LiteralPath $engine) -and
              (Test-Path -LiteralPath $dbx) -and
              (Test-Path -LiteralPath $crx) -and
              (Test-Path -LiteralPath $blank)
  if (-not $canProbe) {
    return [ordered]@{
      status = 'SKIPPED'
      modules = $moduleRecords
      coreconsole_load = [ordered]@{
        status = 'SKIPPED'
        detail = 'accoreconsole, blank.dwg, DBX, or CRX missing.'
      }
    }
  }

  $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
  $stageRoot = Join-Path $StagingDir "native_status_$stamp"
  $runOut = Join-Path $RunsDir "native_status_$stamp"
  New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null
  New-Item -ItemType Directory -Force -Path $runOut | Out-Null
  $stagedDwg = Join-Path $stageRoot 'input.dwg'
  Copy-Item -LiteralPath $blank -Destination $stagedDwg -Force
  Set-ItemProperty -LiteralPath $stagedDwg -Name IsReadOnly -Value $false

  $dbxFwd = $dbx.Replace('\', '/')
  $crxFwd = $crx.Replace('\', '/')
  $diag = Join-Path $runOut 'native_module_load.txt'
  $diagFwd = $diag.Replace('\', '/')
  $scrPath = Join-Path $stageRoot 'native_status.scr'
  $scrLines = @(
    '(vl-load-com)',
    '(setvar "SECURELOAD" 0)',
    '(setvar "FILEDIA" 0)',
    ('(setq dbx-r (vl-catch-all-apply ''arxload (list "{0}")))' -f $dbxFwd),
    ('(setq crx-r (vl-catch-all-apply ''arxload (list "{0}")))' -f $crxFwd),
    ('(setq f (open "{0}" "w"))' -f $diagFwd),
    '(if (vl-catch-all-error-p dbx-r) (write-line (strcat "DBXLOAD_ERROR: " (vl-catch-all-error-message dbx-r)) f) (write-line "DBXLOAD_OK" f))',
    '(if (vl-catch-all-error-p crx-r) (write-line (strcat "CRXLOAD_ERROR: " (vl-catch-all-error-message crx-r)) f) (write-line "CRXLOAD_OK" f))',
    '(write-line "---LOADED---" f)',
    '(foreach m (arx) (write-line m f))',
    '(close f)',
    '(princ)',
    'QUIT',
    ''
  )
  $scrLines | Set-Content -LiteralPath $scrPath -Encoding ASCII
  $r = Invoke-AccoreScr -Engine $engine -StagedDwg $stagedDwg -ScrPath $scrPath -DwgDir (Split-Path -Parent $stagedDwg) -RunOut $runOut -EnvVars @{} -Tag 'native_status'
  $diagText = if (Test-Path -LiteralPath $diag) { Get-Content -LiteralPath $diag -Raw -ErrorAction SilentlyContinue } else { '' }
  $ok = $r.ExitCode -eq 0 -and $diagText -match 'DBXLOAD_OK' -and $diagText -match 'CRXLOAD_OK'

  [ordered]@{
    status = if ($ok) { 'PASS' } else { 'FAIL' }
    modules = $moduleRecords
    coreconsole_load = [ordered]@{
      status = if ($ok) { 'PASS' } else { 'FAIL' }
      staged_input = $stagedDwg
      script = $scrPath
      result_file = $diag
      stdout_tail = $r.StdoutTail
      process_hygiene = $r.Hygiene
    }
  }
}

function Get-CadProcessSnapshot {
  $items = @()
  foreach ($name in @('accoreconsole', 'acad')) {
    foreach ($proc in @(Get-Process -Name $name -ErrorAction SilentlyContinue)) {
      $commandLine = $null
      $parentPid = $null
      try {
        $cim = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)"
        if ($cim) {
          $commandLine = $cim.CommandLine
          $parentPid = $cim.ParentProcessId
        }
      }
      catch {}
      $items += [ordered]@{
        process_name = $proc.ProcessName
        pid          = $proc.Id
        parent_pid   = $parentPid
        title        = $proc.MainWindowTitle
        command_line = $commandLine
      }
    }
  }
  @($items)
}

function Invoke-Probe {
  # Live availability probe. The probe writes JSON to a file (flush+fsync) AND
  # prints to stdout; we read the FILE so the result is immune to any
  # interpreter-shutdown segfault in heavy native extensions. The parent probe
  # process imports only stdlib, so it itself exits cleanly -- but we tolerate a
  # nonzero exit as long as the out-file parsed.
  if (-not (Test-Path -LiteralPath $ProbeScript)) {
    throw "Probe script missing: $ProbeScript"
  }
  $probeOut = Join-Path $env:TEMP ("acad_router_probe_{0}.json" -f ([guid]::NewGuid().ToString('N')))
  try {
    & $PythonExe $ProbeScript '--out' $probeOut 2>&1 | Out-Null
    $code = $LASTEXITCODE
    if (Test-Path -LiteralPath $probeOut) {
      $parsed = Get-Content -LiteralPath $probeOut -Raw -Encoding UTF8 | ConvertFrom-Json
      return $parsed
    }
    throw "probe_routes.py produced no out-file (exit $code): $probeOut"
  }
  finally {
    if (Test-Path -LiteralPath $probeOut) { Remove-Item -LiteralPath $probeOut -Force -ErrorAction SilentlyContinue }
  }
}

function Get-Status {
  param([object]$Capabilities, [bool]$ProbeNativeModules = $false)
  $probe = Invoke-Probe
  $routes = @()
  foreach ($cap in $Capabilities.routes) {
    $p = $probe.routes.PSObject.Properties[$cap.id]
    $avail = if ($p) { [bool]$p.Value.available } else { $false }
    $required = if ($p) { @($p.Value.required) } else { @() }
    $routes += [ordered]@{
      route       = $cap.id
      priority    = $cap.priority
      engine      = $cap.engine
      available   = $avail
      can_do      = $cap.can_do
      entrypoint  = $cap.entrypoint
      tools       = @($cap.tools)
      required    = $required
      intents     = @($cap.intents)
      fallback_to = @($cap.fallback_to)
    }
  }
  $unavail = @($routes | Where-Object { -not $_.available })
  [ordered]@{
    timestamp        = (Get-Date).ToString('o')
    schema           = 'ariadne.autocad_router_status.v2'
    status           = if ($unavail.Count -eq 0) { 'ALL_AVAILABLE' } else { 'PARTIAL' }
    router_home      = $RouterHome
    python_exe       = $PythonExe
    route_count      = $routes.Count
    available_count  = @($routes | Where-Object { $_.available }).Count
    unavailable      = @($unavail | ForEach-Object { $_.route })
    native_modules   = Test-NativeAcadModules -Capabilities $Capabilities -ProbeCoreConsoleLoad $ProbeNativeModules
    routes           = $routes
  }
}

function Resolve-IntentToRoute {
  param([object]$Capabilities, [string]$Intent)
  $key = $Intent.ToLowerInvariant()
  $alias = $Capabilities.intent_aliases.PSObject.Properties[$key]
  if ($alias) { return [string]$alias.Value }
  # If the intent is already a literal route id, accept it.
  $direct = @($Capabilities.routes | Where-Object { $_.id -eq $key }) | Select-Object -First 1
  if ($direct) { return $direct.id }
  $intentMatch = @($Capabilities.routes | Where-Object {
    @($_.intents | ForEach-Object { "$_".ToLowerInvariant() }) -contains $key
  }) | Select-Object -First 1
  if ($intentMatch) { return $intentMatch.id }
  return $null
}

function Select-Route {
  param([object]$Capabilities, [object]$Status, [string]$Intent, [string]$Route)
  if (-not [string]::IsNullOrWhiteSpace($Route)) {
    $cap = @($Capabilities.routes | Where-Object { $_.id -eq $Route }) | Select-Object -First 1
    if (-not $cap) { throw "Unknown route: $Route" }
    $state = @($Status.routes | Where-Object { $_.route -eq $Route }) | Select-Object -First 1
    return [ordered]@{
      intent          = $Intent
      requested_route = $Route
      selected_route  = $cap.id
      forced          = $true
      available       = if ($state) { [bool]$state.available } else { $false }
      reason          = 'Route explicitly requested via -Route.'
      fallback_chain  = @($cap.fallback_to)
    }
  }

  $mapped = Resolve-IntentToRoute -Capabilities $Capabilities -Intent $Intent
  if (-not $mapped) {
    throw "Intent '$Intent' does not map to any route. Known intents: $((@($Capabilities.intent_aliases.PSObject.Properties.Name) -join ', '))"
  }
  $cap = @($Capabilities.routes | Where-Object { $_.id -eq $mapped }) | Select-Object -First 1
  $state = @($Status.routes | Where-Object { $_.route -eq $mapped }) | Select-Object -First 1
  $available = if ($state) { [bool]$state.available } else { $false }

  $selected = $mapped
  $fellBack = $false
  $chainTried = @($mapped)
  if (-not $available) {
    foreach ($fb in @($cap.fallback_to)) {
      $fbState = @($Status.routes | Where-Object { $_.route -eq $fb }) | Select-Object -First 1
      $chainTried += $fb
      if ($fbState -and [bool]$fbState.available) {
        $selected = $fb
        $fellBack = $true
        break
      }
    }
  }
  $selState = @($Status.routes | Where-Object { $_.route -eq $selected }) | Select-Object -First 1

  [ordered]@{
    intent             = $Intent
    mapped_route       = $mapped
    mapped_available   = $available
    selected_route     = $selected
    fell_back          = $fellBack
    available          = if ($selState) { [bool]$selState.available } else { $false }
    reason             = if ($fellBack) { "Mapped route '$mapped' unavailable; fell back to '$selected'." }
                         elseif ($available) { "Mapped route '$mapped' available." }
                         else { "Mapped route '$mapped' unavailable and no available fallback." }
    fallback_chain     = @($cap.fallback_to)
    chain_tried        = $chainTried
  }
}

function Invoke-PythonRoute {
  param([string]$RouteId)
  $cliArgs = @('--route', $RouteId, '--run-dir', $RunsDir)
  if (-not [string]::IsNullOrWhiteSpace($InputPath))  { $cliArgs += @('--input', $InputPath) }
  if (-not [string]::IsNullOrWhiteSpace($InputPath2)) { $cliArgs += @('--input2', $InputPath2) }
  if (-not [string]::IsNullOrWhiteSpace($Out))    { $cliArgs += @('--out', $Out) }
  if (-not [string]::IsNullOrWhiteSpace($env:ARIADNE_LIBREDWG_BIN_DIR)) {
    $cliArgs += @('--libredwg-bin', $env:ARIADNE_LIBREDWG_BIN_DIR)
  }
  $raw = & $PythonExe $RunRouteScript @cliArgs 2>&1
  $code = $LASTEXITCODE
  $text = ($raw -join "`n")
  $obj = $null
  try { $obj = $text | ConvertFrom-Json } catch { $obj = $null }
  [ordered]@{
    engine_exit_code = $code
    engine_output    = if ($obj) { $obj } else { $text }
  }
}

function Invoke-AccoreScr {
  # Run ONE accoreconsole pass with a given .scr and env vars. Captures stdout/stderr,
  # tracks acad.exe process hygiene, restores env afterward. The caller decides whether
  # the input is a staged copy or the original DWG path.
  param(
    [string]$Engine, [string]$StagedDwg, [string]$ScrPath, [string]$DwgDir,
    [string]$RunOut, [hashtable]$EnvVars = @{}, [string]$Tag = 'job'
  )
  $stdoutFile = Join-Path $RunOut ("accoreconsole_{0}_stdout.txt" -f $Tag)
  $stderrFile = Join-Path $RunOut ("accoreconsole_{0}_stderr.txt" -f $Tag)
  $prev = @{}
  foreach ($k in $EnvVars.Keys) {
    $prev[$k] = [Environment]::GetEnvironmentVariable($k)
    [Environment]::SetEnvironmentVariable($k, [string]$EnvVars[$k])
  }
  $preCad = Get-CadProcessSnapshot
  $code = $null
  try {
    $p = Start-Process -FilePath $Engine -ArgumentList @('/i', $StagedDwg, '/s', $ScrPath) `
      -WorkingDirectory $DwgDir -PassThru -WindowStyle Hidden `
      -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile
    $exited = $p.WaitForExit(120000)
    if (-not $exited) {
      try { $p.Kill() } catch {}
      return [ordered]@{ ExitCode = -2; StdoutTail = 'accoreconsole timed out (120s)'; Hygiene = $null }
    }
    $code = $p.ExitCode
  }
  finally {
    foreach ($k in $EnvVars.Keys) {
      if ($null -ne $prev[$k]) { [Environment]::SetEnvironmentVariable($k, $prev[$k]) }
      else { [Environment]::SetEnvironmentVariable($k, $null) }
    }
  }
  $postCad = Get-CadProcessSnapshot
  $preCadPids = @($preCad | ForEach-Object { $_.pid })
  $newAcad = @($postCad | Where-Object { $_.process_name -eq 'acad' -and $preCadPids -notcontains $_.pid })
  $hygiene = [ordered]@{
    status             = if ($newAcad.Count -eq 0) { 'PASS' } else { 'WARN' }
    new_acad_processes = $newAcad
  }
  $stdoutTail = ''
  if (Test-Path -LiteralPath $stdoutFile) {
    $st = Get-Content -LiteralPath $stdoutFile -Raw -ErrorAction SilentlyContinue
    if ($st) { $stdoutTail = ($st -split "`r?`n" | Where-Object { $_.Trim() -ne '' } | Select-Object -Last 6) -join ' | ' }
  }
  if ($null -eq $code) { $code = 0 }
  [ordered]@{ ExitCode = $code; StdoutTail = $stdoutTail; Hygiene = $hygiene }
}

function Get-AutoLispExtractScr {
  # AutoLISP ssget fallback (3rd priority): count modelspace entities by type -> JSON.
  # The proven robust pattern (no fragile -DXFOUT prompt chaining). Output env var:
  # SDK_DWG_EXTRACT_OUT.
  param([string]$StageRoot)
  $lispPath = Join-Path $StageRoot 'extract.lsp'
  $lispLines = @(
    '(defun c:SDKDWGXTRACT (/ out f ss total i en ed typ counts cell dwgname)',
    '  (setq out (getenv "SDK_DWG_EXTRACT_OUT"))',
    '  (if (or (null out) (= out "")) (setq out "extract.json"))',
    '  (setq ss (ssget "_X" (list (cons 410 "Model"))))',
    '  (setq total (if ss (sslength ss) 0))',
    '  (setq counts (list))',
    '  (setq i 0)',
    '  (while (< i total)',
    '    (setq en (ssname ss i))',
    '    (setq ed (entget en))',
    '    (setq typ (cdr (assoc 0 ed)))',
    '    (setq cell (assoc typ counts))',
    '    (if cell',
    '      (setq counts (subst (cons typ (1+ (cdr cell))) cell counts))',
    '      (setq counts (cons (cons typ 1) counts)))',
    '    (setq i (1+ i)))',
    '  (setq dwgname (getvar "DWGNAME"))',
    '  (setq f (open out "w"))',
    '  (write-line "{" f)',
    '  (write-line "  \"route\": \"dwg_truth_autocad\"," f)',
    '  (write-line "  \"status\": \"ok\"," f)',
    '  (write-line "  \"engine\": \"autolisp_ssget\"," f)',
    '  (write-line (strcat "  \"dwg_name\": \"" dwgname "\",") f)',
    '  (write-line (strcat "  \"modelspace_count\": " (itoa total) ",") f)',
    '  (write-line "  \"entities_by_type\": {" f)',
    '  (setq i 0)',
    '  (foreach c counts',
    '    (write-line (strcat "    \"" (car c) "\": " (itoa (cdr c)) (if (< (1+ i) (length counts)) "," "")) f)',
    '    (setq i (1+ i)))',
    '  (write-line "  }" f)',
    '  (write-line "}" f)',
    '  (close f)',
    '  (princ))',
    '(princ)'
  )
  $lispLines | Set-Content -LiteralPath $lispPath -Encoding ASCII
  $lispFwd = $lispPath.Replace('\', '/')
  return @('FILEDIA', '0', 'CMDECHO', '0', "(load `"$lispFwd`")", 'SDKDWGXTRACT', 'QUIT', '')
}

function Get-EffectiveDwgWriteMode {
  if (-not [string]::IsNullOrWhiteSpace($WriteMode)) { return $WriteMode }
  $key = $Intent.ToLowerInvariant()
  if (@('live_autocad', 'active_document') -contains $key) { return 'live_edit' }
  if ($key -eq 'write_original') { return 'write_original' }
  return 'read'
}

function Invoke-FullAutoCadScript {
  param([string]$RunOut)
  if ([string]::IsNullOrWhiteSpace($Script) -or -not (Test-Path -LiteralPath $Script)) {
    return [ordered]@{
      engine_exit_code = -10
      engine_output    = [ordered]@{
        status = 'SCRIPT_REQUIRED'
        detail = 'live_edit/full_autocad mode requires -Script <file.scr>.'
      }
    }
  }

  $app = $null
  foreach ($progId in @('AutoCAD.Application', 'AutoCAD.Application.26')) {
    try {
      $app = [Runtime.InteropServices.Marshal]::GetActiveObject($progId)
      if ($app) { break }
    }
    catch {}
  }
  if (-not $app) {
    return [ordered]@{
      engine_exit_code = -11
      engine_output    = [ordered]@{
        status = 'NO_ACTIVE_AUTOCAD'
        detail = 'No running AutoCAD COM application was found for live_edit/full_autocad mode.'
      }
    }
  }

  $doc = $null
  try { $doc = $app.ActiveDocument } catch { $doc = $null }
  if (-not $doc) {
    return [ordered]@{
      engine_exit_code = -12
      engine_output    = [ordered]@{ status = 'NO_ACTIVE_DOCUMENT'; detail = 'AutoCAD is running but has no active document.' }
    }
  }

  $activePath = ''
  try { $activePath = [string]$doc.FullName } catch {}
  if (-not [string]::IsNullOrWhiteSpace($InputPath) -and -not [string]::IsNullOrWhiteSpace($activePath)) {
    $want = [System.IO.Path]::GetFullPath($InputPath)
    $have = [System.IO.Path]::GetFullPath($activePath)
    if ($want.ToLowerInvariant() -ne $have.ToLowerInvariant()) {
      return [ordered]@{
        engine_exit_code = -13
        engine_output    = [ordered]@{
          status = 'ACTIVE_DOCUMENT_MISMATCH'
          requested_input = $want
          active_document = $have
          detail = 'Refusing to send live edit commands to a different active drawing.'
        }
      }
    }
  }

  $scriptText = Get-Content -LiteralPath $Script -Raw
  $sentPath = Join-Path $RunOut 'live_autocad_script_sent.scr'
  Copy-Item -LiteralPath $Script -Destination $sentPath -Force
  try {
    $doc.SendCommand($scriptText + "`n")
  }
  catch {
    return [ordered]@{
      engine_exit_code = -14
      engine_output    = [ordered]@{ status = 'SENDCOMMAND_FAILED'; detail = "$($_.Exception.Message)"; active_document = $activePath }
    }
  }

  return [ordered]@{
    engine_exit_code = 0
    engine_output    = [ordered]@{
      status = 'command_sent_async'
      host = 'full_autocad_com_active_document'
      write_mode = 'live_edit'
      active_document = $activePath
      script = $sentPath
      detail = 'Commands were sent to AutoCAD ActiveDocument through COM SendCommand. AutoCAD executes this asynchronously; the script should include any required SAVE/QSAVE command.'
    }
  }
}

function Wait-NativeCadJobResult {
  param([string]$ResultPath, [int]$TimeoutSeconds = 90, [string]$ExpectedOperation = '')
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $last = $null
  while ((Get-Date) -lt $deadline) {
    if (Test-Path -LiteralPath $ResultPath) {
      try {
        $candidate = Get-Content -LiteralPath $ResultPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $last = $candidate
        if ([string]::IsNullOrWhiteSpace($ExpectedOperation) -or "$($candidate.operation)" -eq $ExpectedOperation) {
          return $candidate
        }
      }
      catch {
        Start-Sleep -Milliseconds 500
        continue
      }
    }
    Start-Sleep -Milliseconds 500
  }
  return $last
}

function Wait-FullAutoCadIdle {
  param([object]$Document, [int]$TimeoutSeconds = 30)
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $cmd = [string]$Document.GetVariable('CMDNAMES')
      if ([string]::IsNullOrWhiteSpace($cmd)) {
        return $true
      }
    }
    catch {
      # AutoCAD rejects COM calls while it is executing a command. Keep polling.
    }
    Start-Sleep -Milliseconds 250
  }
  return $false
}

function Wait-PathExists {
  param([string]$Path, [int]$TimeoutSeconds = 30)
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-Path -LiteralPath $Path) {
      return $true
    }
    Start-Sleep -Milliseconds 250
  }
  return $false
}

function Invoke-FullAutoCadCadJob {
  param([string]$RunOut)

  $app = $null
  foreach ($progId in @('AutoCAD.Application', 'AutoCAD.Application.26')) {
    try {
      $app = [Runtime.InteropServices.Marshal]::GetActiveObject($progId)
      if ($app) { break }
    }
    catch {}
  }
  if (-not $app) {
    return [ordered]@{
      engine_exit_code = -11
      engine_output    = [ordered]@{
        status = 'NO_ACTIVE_AUTOCAD'
        detail = 'No running AutoCAD COM application was found for full_autocad native job mode.'
      }
    }
  }

  $doc = $null
  try { $doc = $app.ActiveDocument } catch { $doc = $null }
  if (-not $doc) {
    return [ordered]@{
      engine_exit_code = -12
      engine_output    = [ordered]@{ status = 'NO_ACTIVE_DOCUMENT'; detail = 'AutoCAD is running but has no active document.' }
    }
  }

  $activePath = ''
  try { $activePath = [string]$doc.FullName } catch {}
  if (-not [string]::IsNullOrWhiteSpace($InputPath) -and -not [string]::IsNullOrWhiteSpace($activePath)) {
    $want = [System.IO.Path]::GetFullPath($InputPath)
    $have = [System.IO.Path]::GetFullPath($activePath)
    if ($want.ToLowerInvariant() -ne $have.ToLowerInvariant()) {
      return [ordered]@{
        engine_exit_code = -13
        engine_output    = [ordered]@{
          status = 'ACTIVE_DOCUMENT_MISMATCH'
          requested_input = $want
          active_document = $have
          detail = 'Refusing to run a full AutoCAD native job against a different active drawing.'
        }
      }
    }
  }

  $preIdle = Wait-FullAutoCadIdle -Document $doc -TimeoutSeconds 30
  if (-not $preIdle) {
    # KEEP: FULL_AUTOCAD_BUSY_BEFORE_SEND remains a supported signal in diagnostics and contract coverage.
    Write-Verbose '[full-autocad] AutoCAD not idle before SendCommand; attempting command submit anyway and relying on result marker for completion.'
  }

  $effectiveWriteMode = Get-EffectiveDwgWriteMode
  $jobIn = Join-Path $RunOut 'cad_job_request.json'
  if (-not [string]::IsNullOrWhiteSpace($JobPath)) {
    if (-not (Test-Path -LiteralPath $JobPath)) {
      return [ordered]@{ engine_exit_code = -1; engine_output = "CAD job file not found: $JobPath" }
    }
    Copy-Item -LiteralPath $JobPath -Destination $jobIn -Force
  }
  elseif (-not [string]::IsNullOrWhiteSpace($Operation)) {
    Write-Json -Payload ([ordered]@{
      schema = 'ariadne.autocad_sdk_job.v1'
      operation = $Operation
      write_mode = $effectiveWriteMode
    }) -Path $jobIn | Out-Null
  }
  else {
    return [ordered]@{
      engine_exit_code = -10
      engine_output = [ordered]@{ status = 'JOB_REQUIRED'; detail = 'Full AutoCAD native job requires -JobPath <job.json> or -Operation <operation>.' }
    }
  }
  $jobOperation = Get-CadJobOperation -Path $jobIn
  $jigPointLine = $null
  if ($jobOperation -eq 'live.jig.point_probe') {
    $jigPointLine = Get-CadJobJigPointLine -Path $jobIn
    if ([string]::IsNullOrWhiteSpace($jigPointLine)) {
      return [ordered]@{
        engine_exit_code = -16
        engine_output    = [ordered]@{
          status = 'JIG_POINT_REQUIRED'
          detail = 'live.jig.point_probe requires args.point {x,y,z} so SendCommand can satisfy the AcEdJig prompt.'
          job = $jobIn
        }
      }
    }
  }

  $dbx = Resolve-NativeAcadModule -LeafName 'Ariadne.AcadNativeDbx.dbx'
  $arx = Resolve-NativeAcadModule -LeafName 'Ariadne.AcadNative.arx'
  $dbxFwd = $dbx.Replace('\', '/')
  $arxFwd = $arx.Replace('\', '/')
  $jobFwd = $jobIn.Replace('\', '/')
  $resultOut = Join-Path $RunOut 'native_cad_job_result.json'
  $resultFwd = $resultOut.Replace('\', '/')
  $doneOut = Join-Path $RunOut 'full_autocad_native_job_done.txt'
  $doneFwd = $doneOut.Replace('\', '/')
  $mailboxOut = Join-Path $RunsDir 'full_autocad_native_job_mailbox.txt'
  $mailboxFwd = $mailboxOut.Replace('\', '/')
  $trusted = (Split-Path -Parent $arx).Replace('\', '\\')
  $scrPath = Join-Path $RunOut 'full_autocad_native_job.scr'
  $scrLines = @(
    '(vl-load-com)',
    ('(setq ariadne-done-file "{0}")' -f $doneFwd),
    ('(setq ariadne-mailbox-file "{0}")' -f $mailboxFwd),
    '(defun ariadne-write-done (/ f) (setq f (open ariadne-done-file "w")) (if f (progn (write-line "done" f) (close f))) (princ))',
    ('(defun ariadne-write-mailbox (/ f) (setq f (open ariadne-mailbox-file "w")) (if f (progn (write-line "ARIADNE_CAD_JOB_IN={0}" f) (write-line "ARIADNE_CAD_JOB_OUT={1}" f) (write-line "ARIADNE_CAD_JOB_HOST_MODE=full_autocad" f) (close f))) (princ))' -f $jobFwd, $resultFwd),
    '(setvar "SECURELOAD" 0)',
    '(setvar "FILEDIA" 0)',
    '(setvar "CMDECHO" 0)',
    "(setvar `"TRUSTEDPATHS`" `"$trusted`")",
    '(ariadne-write-mailbox)',
    '(setq ariadne-arx-list (mapcar ''strcase (arx)))',
    ('(if (not (member "ARIADNE.ACADNATIVEDBX.DBX" ariadne-arx-list)) (setq dbx-r (vl-catch-all-apply ''arxload (list "{0}"))))' -f $dbxFwd),
    '(setq ariadne-arx-list (mapcar ''strcase (arx)))',
    ('(if (not (member "ARIADNE.ACADNATIVE.ARX" ariadne-arx-list)) (setq arx-r (vl-catch-all-apply ''arxload (list "{0}"))))' -f $arxFwd),
    'ARIADNE_NATIVE_JOB_MAILBOX'
  )
  if (-not [string]::IsNullOrWhiteSpace($jigPointLine)) {
    $scrLines += $jigPointLine
  }
  if (@('write_copy', 'write_original', 'live_edit') -contains $effectiveWriteMode) {
    $scrLines += '_QSAVE'
  }
  $scrLines += '(ariadne-write-done)'
  $scrLines += '(princ)'
  $scrLines += ''
  $scrLines | Set-Content -LiteralPath $scrPath -Encoding ASCII

  $commandText = (Get-Content -LiteralPath $scrPath -Raw) + "`n"
  $sendAttempts = 0
  $sendOk = $false
  while (-not $sendOk -and $sendAttempts -lt 4) {
    $sendAttempts += 1
    try {
      $doc.SendCommand($commandText)
      $sendOk = $true
    }
    catch {
      if ($sendAttempts -lt 4 -and $_.Exception.Message -match 'Call was rejected by callee|RPC_E_CALL_REJECTED') {
        Start-Sleep -Seconds 1
        continue
      }
      return [ordered]@{
        engine_exit_code = -14
        engine_output    = [ordered]@{
          status = 'SENDCOMMAND_FAILED'
          detail = "$($_.Exception.Message)"
          active_document = $activePath
          send_attempts = $sendAttempts
        }
      }
    }
  }

  $result = Wait-NativeCadJobResult -ResultPath $resultOut -TimeoutSeconds 90 -ExpectedOperation $jobOperation
  $doneAfter = Wait-PathExists -Path $doneOut -TimeoutSeconds 30
  $idleAfter = Wait-FullAutoCadIdle -Document $doc -TimeoutSeconds 30
  $ok = $false
  if ($result -and "$($result.status)" -ne 'error' -and "$($result.operation)" -eq $jobOperation -and $doneAfter) {
    if ($jobOperation -eq 'live.jig.point_probe') {
      # Jig workflows can legitimately keep the editor command stack busy for a short
      # interaction window; treat a captured done/result marker as a successful run.
      $ok = $true
    }
    elseif ($idleAfter) {
      $ok = $true
    }
    elseif (-not $preIdle) {
      # If AutoCAD was not idle before send, rely on captured result + marker
      # to avoid false negatives on startup/race timing.
      $ok = $true
    }
  }
  return [ordered]@{
    engine_exit_code = if ($ok) { 0 } else { 1 }
    engine_output = [ordered]@{
      status = if ($ok) { 'ok' } else { 'native_cad_job_pending_or_failed' }
      mode = 'full_autocad_native_job'
      host = 'full_autocad_com_active_document'
      operation = $jobOperation
      write_mode = $effectiveWriteMode
      active_document = $activePath
      job = $jobIn
      result_json = $resultOut
      result = $result
      done_marker = $doneOut
      done_after = $doneAfter
      mailbox = $mailboxOut
      idle_after = $idleAfter
      dbx_module = $dbx
      arx_module = $arx
      script = $scrPath
      detail = 'Commands were sent to AutoCAD ActiveDocument and the router polled for ARIADNE_NATIVE_JOB result JSON.'
    }
  }
}

function Invoke-DwgWriteOriginalScript {
  param([object]$Capabilities)
  $cap = @($Capabilities.routes | Where-Object { $_.id -eq 'dwg_truth_autocad' }) | Select-Object -First 1
  $engine = $cap.engine_path
  if (-not (Test-Path -LiteralPath $engine)) {
    return [ordered]@{ engine_exit_code = -1; engine_output = "accoreconsole not found at $engine" }
  }
  if ([string]::IsNullOrWhiteSpace($InputPath) -or -not (Test-Path -LiteralPath $InputPath)) {
    return [ordered]@{ engine_exit_code = -1; engine_output = 'write_original requires -InputPath <existing.dwg>' }
  }
  if ([string]::IsNullOrWhiteSpace($Script) -or -not (Test-Path -LiteralPath $Script)) {
    return [ordered]@{
      engine_exit_code = -10
      engine_output    = [ordered]@{
        status = 'SCRIPT_REQUIRED'
        detail = 'write_original/coreconsole mode requires -Script <file.scr>. The script is responsible for SAVE/QSAVE when mutation should persist.'
      }
    }
  }

  $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
  $runOut = Join-Path $RunsDir "dwg_truth_autocad_write_original_$stamp"
  New-Item -ItemType Directory -Force -Path $runOut | Out-Null
  $dwgDir = Split-Path -Parent $InputPath
  $scrPath = Join-Path $runOut 'write_original_job.scr'
  Copy-Item -LiteralPath $Script -Destination $scrPath -Force
  $r = Invoke-AccoreScr -Engine $engine -StagedDwg $InputPath -ScrPath $scrPath -DwgDir $dwgDir -RunOut $runOut -EnvVars @{} -Tag 'write_original'
  return [ordered]@{
    engine_exit_code = $r.ExitCode
    engine_output    = [ordered]@{
      status = 'write_original_script_ran'
      host = 'accoreconsole_original_input'
      write_mode = 'write_original'
      input = $InputPath
      script = $scrPath
      stdout_tail = $r.StdoutTail
      process_hygiene = $r.Hygiene
      detail = 'The script ran against the original DWG path, not an ASCII staging copy. The script is responsible for SAVE/QSAVE when mutation should persist.'
    }
  }
}

function Invoke-CadJobRoute {
  param([object]$Capabilities)
  $cap = @($Capabilities.routes | Where-Object { $_.id -eq 'dwg_truth_autocad' }) | Select-Object -First 1
  $engine = $cap.engine_path
  if (-not (Test-Path -LiteralPath $engine)) {
    return [ordered]@{ engine_exit_code = -1; engine_output = "accoreconsole not found at $engine" }
  }
  if ([string]::IsNullOrWhiteSpace($InputPath) -or -not (Test-Path -LiteralPath $InputPath)) {
    return [ordered]@{ engine_exit_code = -1; engine_output = 'CAD job requires -InputPath <existing.dwg> for Core Console execution.' }
  }

  $effectiveWriteMode = Get-EffectiveDwgWriteMode
  $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
  $runOut = Join-Path $RunsDir "dwg_truth_autocad_cad_job_$stamp"
  New-Item -ItemType Directory -Force -Path $runOut | Out-Null

  $jobIn = Join-Path $runOut 'cad_job_request.json'
  if (-not [string]::IsNullOrWhiteSpace($JobPath)) {
    if (-not (Test-Path -LiteralPath $JobPath)) {
      return [ordered]@{ engine_exit_code = -1; engine_output = "CAD job file not found: $JobPath" }
    }
    Copy-Item -LiteralPath $JobPath -Destination $jobIn -Force
  }
  elseif (-not [string]::IsNullOrWhiteSpace($Operation)) {
    Write-Json -Payload ([ordered]@{
      schema = 'ariadne.autocad_sdk_job.v1'
      operation = $Operation
      write_mode = $effectiveWriteMode
    }) -Path $jobIn | Out-Null
  }
  else {
    return [ordered]@{
      engine_exit_code = -10
      engine_output = [ordered]@{ status = 'JOB_REQUIRED'; detail = 'CAD job execution requires -JobPath <job.json> or -Operation <operation>.' }
    }
  }
  $jobOperation = Get-CadJobOperation -Path $jobIn

  $inputDwg = $InputPath
  $dwgDir = Split-Path -Parent $inputDwg
  if ($effectiveWriteMode -ne 'write_original') {
    $stageRoot = Join-Path $StagingDir "dwg_job_$stamp"
    New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null
    $inputDwg = Join-Path $stageRoot 'input.dwg'
    Copy-Item -LiteralPath $InputPath -Destination $inputDwg -Force
    Set-ItemProperty -LiteralPath $inputDwg -Name IsReadOnly -Value $false
    $dwgDir = Split-Path -Parent $inputDwg
  }

  if (Test-NativeP1CadJobOperation -OperationName $jobOperation) {
    $resultOut = Join-Path $runOut 'native_cad_job_result.json'
    $dbx = Resolve-NativeAcadModule -LeafName 'Ariadne.AcadNativeDbx.dbx'
    $crx = Resolve-NativeAcadModule -LeafName 'Ariadne.AcadNative.crx'
    $dbxFwd = $dbx.Replace('\', '/')
    $crxFwd = $crx.Replace('\', '/')
    $jobFwd = $jobIn.Replace('\', '/')
    $resultFwd = $resultOut.Replace('\', '/')
    $trusted = (Split-Path -Parent $crx).Replace('\', '\\')
    $scrPath = Join-Path $runOut 'native_cad_job.scr'
    $scrLines = @(
      '(setvar "SECURELOAD" 0)',
      '(setvar "FILEDIA" 0)',
      '(setvar "CMDECHO" 0)',
      "(setvar `"TRUSTEDPATHS`" `"$trusted`")",
      "(arxload `"$dbxFwd`")",
      "(arxload `"$crxFwd`")",
      ('(setenv "ARIADNE_CAD_JOB_IN" "{0}")' -f $jobFwd),
      ('(setenv "ARIADNE_CAD_JOB_OUT" "{0}")' -f $resultFwd),
      '(setenv "ARIADNE_CAD_JOB_HOST_MODE" "coreconsole")',
      'ARIADNE_NATIVE_JOB'
    )
    if (@('write_copy', 'write_original', 'live_edit') -contains $effectiveWriteMode) {
      $scrLines += '_QSAVE'
    }
    $scrLines += @('QUIT', '')
    $scrLines | Set-Content -LiteralPath $scrPath -Encoding ASCII

    $envVars = @{
      ARIADNE_CAD_JOB_IN = $jobIn
      ARIADNE_CAD_JOB_OUT = $resultOut
      ARIADNE_CAD_JOB_WRITE_MODE = $effectiveWriteMode
    }
    $r = Invoke-AccoreScr -Engine $engine -StagedDwg $inputDwg -ScrPath $scrPath -DwgDir $dwgDir -RunOut $runOut -EnvVars $envVars -Tag 'native_cad_job'

    $result = $null
    $ok = $false
    if (Test-Path -LiteralPath $resultOut) {
      try {
        $result = Get-Content -LiteralPath $resultOut -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($result -and "$($result.status)" -ne 'error') { $ok = $true }
      }
      catch { $ok = $false }
    }

    return [ordered]@{
      engine_exit_code = if ($r.ExitCode -eq 0 -and $ok) { 0 } else { if ($r.ExitCode -ne 0) { $r.ExitCode } else { -3 } }
      engine_output = [ordered]@{
        status = if ($ok) { 'ok' } else { 'native_cad_job_failed' }
        mode = 'native_cad_job'
        operation = $jobOperation
        write_mode = $effectiveWriteMode
        input = $inputDwg
        original_input = $InputPath
        job = $jobIn
        result_json = $resultOut
        result = $result
        dbx_module = $dbx
        crx_module = $crx
        stdout_tail = $r.StdoutTail
        process_hygiene = $r.Hygiene
      }
    }
  }

  $dll = Resolve-NativeExtractorDll
  $dllFwd = $dll.Replace('\', '/')
  $scrPath = Join-Path $runOut 'cad_job.scr'
  $scrLines = @('SECURELOAD', '0', 'FILEDIA', '0', 'CMDECHO', '0', 'NETLOAD', "`"$dllFwd`"", 'ARIADNE_CAD_JOB')
  if ($effectiveWriteMode -eq 'write_original') {
    $scrLines += 'QSAVE'
  }
  $scrLines += @('QUIT', '')
  $scrLines | Set-Content -LiteralPath $scrPath -Encoding ASCII

  $resultOut = Join-Path $runOut 'cad_job_result.json'
  $envVars = @{
    ARIADNE_CAD_JOB_IN = $jobIn
    ARIADNE_CAD_JOB_OUT = $resultOut
    ARIADNE_CAD_JOB_WRITE_MODE = $effectiveWriteMode
  }
  $r = Invoke-AccoreScr -Engine $engine -StagedDwg $inputDwg -ScrPath $scrPath -DwgDir $dwgDir -RunOut $runOut -EnvVars $envVars -Tag 'cad_job'

  $result = $null
  $ok = $false
  if (Test-Path -LiteralPath $resultOut) {
    try {
      $result = Get-Content -LiteralPath $resultOut -Raw -Encoding UTF8 | ConvertFrom-Json
      if ($result -and "$($result.status)" -ne 'error') { $ok = $true }
    }
    catch { $ok = $false }
  }

  [ordered]@{
    engine_exit_code = if ($r.ExitCode -eq 0 -and $ok) { 0 } else { if ($r.ExitCode -ne 0) { $r.ExitCode } else { -3 } }
    engine_output = [ordered]@{
      status = if ($ok) { 'ok' } else { 'cad_job_failed' }
      mode = 'cad_job'
      write_mode = $effectiveWriteMode
      input = $inputDwg
      original_input = $InputPath
      job = $jobIn
      result_json = $resultOut
      result = $result
      stdout_tail = $r.StdoutTail
      process_hygiene = $r.Hygiene
    }
  }
}

function Invoke-AutoCadRoute {
  # DWG ground-truth via accoreconsole. Priority chain (most authoritative first):
  #   ObjectARX (active document) -> ObjectDBX (side database) -> AutoLISP (ssget count).
  # The first engine that yields a valid extract wins; the rest are skipped. In this
  # extractor path, the original DWG is not modified: ASCII-staged copy, and every
  # generated script QUITs without SAVE. write_original/live_edit use separate lanes.
  # -ExtractMode selects the chain:
  #   truth_chain (default) = arx->dbx->autolisp ; geometry_native = arx only ;
  #   objectdbx = dbx only ; summary = autolisp only.
  param([object]$Capabilities)
  $cap = @($Capabilities.routes | Where-Object { $_.id -eq 'dwg_truth_autocad' }) | Select-Object -First 1
  $engine = $cap.engine_path
  if (-not (Test-Path -LiteralPath $engine)) {
    return [ordered]@{ engine_exit_code = -1; engine_output = "accoreconsole not found at $engine" }
  }
  if ([string]::IsNullOrWhiteSpace($InputPath)) {
    return [ordered]@{ engine_exit_code = -1; engine_output = 'dwg_truth_autocad requires -InputPath <dwg>' }
  }
  if (-not (Test-Path -LiteralPath $InputPath)) {
    return [ordered]@{ engine_exit_code = -1; engine_output = "Input DWG not found: $InputPath" }
  }

  $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
  $stageRoot = Join-Path $StagingDir "dwg_$stamp"
  New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null
  # ASCII-safe staged copy of the input for the batch extractor path.
  $stagedDwg = Join-Path $stageRoot 'input.dwg'
  Copy-Item -LiteralPath $InputPath -Destination $stagedDwg -Force
  Set-ItemProperty -LiteralPath $stagedDwg -Name IsReadOnly -Value $false
  $dwgDir = Split-Path -Parent $stagedDwg

  $runOut = Join-Path $RunsDir "dwg_truth_autocad_$stamp"
  New-Item -ItemType Directory -Force -Path $runOut | Out-Null

  # Custom script short-circuits the whole chain (caller-supplied .scr).
  if (-not [string]::IsNullOrWhiteSpace($Script) -and (Test-Path -LiteralPath $Script)) {
    $scrPath = Join-Path $stageRoot 'job.scr'
    Copy-Item -LiteralPath $Script -Destination $scrPath -Force
    $r = Invoke-AccoreScr -Engine $engine -StagedDwg $stagedDwg -ScrPath $scrPath -DwgDir $dwgDir -RunOut $runOut -EnvVars @{} -Tag 'custom'
    return [ordered]@{
      engine_exit_code = $r.ExitCode
      engine_output    = [ordered]@{
        status = 'custom_script_ran'; mode = 'custom_script'; staged_input = $stagedDwg
        script = $scrPath; stdout_tail = $r.StdoutTail; process_hygiene = $r.Hygiene
      }
    }
  }

  # Build the engine chain from ExtractMode (truth_chain = full priority fallback).
  $chain = switch ($ExtractMode) {
    'summary'         { @('autolisp') }
    'geometry_native' { @('arx') }
    'objectdbx'       { @('dbx') }
    default           { @('arx', 'dbx', 'autolisp') }
  }

  # Managed ObjectARX extractor DLL (acdbmgd-based) needed for arx/dbx engines.
  $dll = $null
  if (($chain -contains 'arx') -or ($chain -contains 'dbx')) {
    try { $dll = Resolve-NativeExtractorDll } catch { $dll = $null }
  }

  $attempts = @()
  $final = $null
  foreach ($mode in $chain) {
    $modeOut = (Join-Path $runOut ("extract_{0}.json" -f $mode)).Replace('\', '/')
    $scrPath = Join-Path $stageRoot ("job_{0}.scr" -f $mode)
    $envVars = @{}
    $scrLines = $null

    if ($mode -eq 'arx') {
      if (-not $dll) { $attempts += [ordered]@{ mode = 'arx'; status = 'skipped_no_dll' }; continue }
      $dllFwd = $dll.Replace('\', '/')
      $scrLines = @('SECURELOAD', '0', 'FILEDIA', '0', 'CMDECHO', '0', 'NETLOAD', "`"$dllFwd`"", 'ARIADNE_DWG_GEOM_EXTRACT', 'QUIT', '')
      $envVars = @{ ARIADNE_DWG_GEOM_OUT = $modeOut }
    }
    elseif ($mode -eq 'dbx') {
      if (-not $dll) { $attempts += [ordered]@{ mode = 'dbx'; status = 'skipped_no_dll' }; continue }
      # DBX reads a SEPARATE staged copy via ReadDwgFile: the active /i document already
      # holds a lock on input.dwg, so side-DB reading the SAME path throws
      # eFileSharingViolation. A distinct copy avoids the lock entirely.
      $dbxIn = Join-Path $stageRoot 'input_dbx.dwg'
      Copy-Item -LiteralPath $stagedDwg -Destination $dbxIn -Force
      Set-ItemProperty -LiteralPath $dbxIn -Name IsReadOnly -Value $false
      $dllFwd = $dll.Replace('\', '/')
      $scrLines = @('SECURELOAD', '0', 'FILEDIA', '0', 'CMDECHO', '0', 'NETLOAD', "`"$dllFwd`"", 'ARIADNE_DWG_DBX_EXTRACT', 'QUIT', '')
      $envVars = @{ ARIADNE_DWG_DBX_IN = $dbxIn; ARIADNE_DWG_GEOM_OUT = $modeOut }
    }
    elseif ($mode -eq 'autolisp') {
      $scrLines = Get-AutoLispExtractScr -StageRoot $stageRoot
      $envVars = @{ SDK_DWG_EXTRACT_OUT = $modeOut }
    }

    $scrLines | Set-Content -LiteralPath $scrPath -Encoding ASCII
    $r = Invoke-AccoreScr -Engine $engine -StagedDwg $stagedDwg -ScrPath $scrPath -DwgDir $dwgDir -RunOut $runOut -EnvVars $envVars -Tag $mode

    $modeOutWin = $modeOut.Replace('/', '\')
    $extract = $null
    $ok = $false
    if (Test-Path -LiteralPath $modeOutWin) {
      try {
        $extract = Get-Content -LiteralPath $modeOutWin -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($extract -and ("$($extract.status)" -ne 'error')) { $ok = $true }
      } catch { $ok = $false }
    }
    $attempts += [ordered]@{ mode = $mode; exit = $r.ExitCode; extract_json = $modeOutWin; ok = $ok; stdout_tail = $r.StdoutTail }
    if ($ok) {
      $final = [ordered]@{ engine = $mode; extract = $extract; extract_json = $modeOutWin; hygiene = $r.Hygiene }
      break
    }
  }

  if ($null -eq $final) {
    return [ordered]@{
      engine_exit_code = -3
      engine_output    = [ordered]@{ status = 'all_engines_failed'; mode = $ExtractMode; staged_input = $stagedDwg; attempts = $attempts }
    }
  }
  # Inline only a compact summary; the FULL extract (potentially tens of thousands of
  # entities) stays in extract_json so the router's return payload never blows up an
  # agent's context. Read extract_json when the entity-level detail is actually needed.
  $summary = $null
  if ($final.extract) {
    if ($null -ne $final.extract.summary) { $summary = $final.extract.summary }
    else { $summary = [ordered]@{ modelspace_count = $final.extract.modelspace_count; entities_by_type = $final.extract.entities_by_type } }
  }
  [ordered]@{
    engine_exit_code = 0
    engine_output    = [ordered]@{
      status          = 'ok'
      mode            = $ExtractMode
      winning_engine  = $final.engine
      staged_input    = $stagedDwg
      extract_json    = $final.extract_json
      extract_summary = $summary
      attempts        = $attempts
      process_hygiene = $final.hygiene
    }
  }
}

# ---- main ----
$capabilities = Read-JsonFile -Path $ConfigPath

switch ($Action) {
  'status' {
    $status = Get-Status -Capabilities $capabilities -ProbeNativeModules $true
    Write-Json -Payload $status -Path $LatestStatusPath
  }
  'select' {
    $status = Get-Status -Capabilities $capabilities
    $selection = Select-Route -Capabilities $capabilities -Status $status -Intent $Intent -Route $Route
    Write-Json -Payload ([ordered]@{
      timestamp   = (Get-Date).ToString('o')
      schema      = 'ariadne.autocad_router_selection.v2'
      status      = 'PASS'
      selection   = $selection
      status_path = $LatestStatusPath
    })
  }
  'run' {
    $status = Get-Status -Capabilities $capabilities
    Write-Json -Payload $status -Path $LatestStatusPath | Out-Null
    $selection = Select-Route -Capabilities $capabilities -Status $status -Intent $Intent -Route $Route
    if (-not $selection.available) {
      Write-Json -Payload ([ordered]@{
        timestamp = (Get-Date).ToString('o')
        schema    = 'ariadne.autocad_router_run.v2'
        status    = 'UNAVAILABLE'
        selection = $selection
        detail    = "Selected route '$($selection.selected_route)' is not available on this machine; refusing to fake a run."
      })
      break
    }
    $sel = $selection.selected_route
  if ($sel -eq 'dwg_truth_autocad') {
    $effectiveWriteMode = Get-EffectiveDwgWriteMode
    $safeFallbackExec = Invoke-SafeFallbackOperation -Capabilities $capabilities
    if ($null -ne $safeFallbackExec) {
      $exec = $safeFallbackExec
    }
    elseif (
      ($HostMode -eq 'full_autocad' -or $effectiveWriteMode -eq 'live_edit') -and
      (-not [string]::IsNullOrWhiteSpace($JobPath) -or -not [string]::IsNullOrWhiteSpace($Operation))
    ) {
      $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
      $runOut = Join-Path $RunsDir "dwg_truth_autocad_full_job_$stamp"
      New-Item -ItemType Directory -Force -Path $runOut | Out-Null
      $exec = Invoke-FullAutoCadCadJob -RunOut $runOut
    }
    elseif (-not [string]::IsNullOrWhiteSpace($JobPath) -or -not [string]::IsNullOrWhiteSpace($Operation)) {
      $exec = Invoke-CadJobRoute -Capabilities $capabilities
    }
      elseif ($HostMode -eq 'full_autocad' -or $effectiveWriteMode -eq 'live_edit') {
        $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $runOut = Join-Path $RunsDir "dwg_truth_autocad_live_edit_$stamp"
        New-Item -ItemType Directory -Force -Path $runOut | Out-Null
        $exec = Invoke-FullAutoCadScript -RunOut $runOut
      }
      elseif ($effectiveWriteMode -eq 'write_original') {
        $exec = Invoke-DwgWriteOriginalScript -Capabilities $capabilities
      }
      else {
        $exec = Invoke-AutoCadRoute -Capabilities $capabilities
      }
    }
    else {
      $exec = Invoke-PythonRoute -RouteId $sel
    }
    Write-Json -Payload ([ordered]@{
      timestamp     = (Get-Date).ToString('o')
      schema        = 'ariadne.autocad_router_run.v2'
      status        = if ($exec.engine_exit_code -eq 0) { 'PASS' } else { 'ROUTE_NONZERO' }
      selection     = $selection
      executed_route = $sel
      execution     = $exec
    })
  }
  'explain' {
    if (-not [string]::IsNullOrWhiteSpace($Operation)) {
      $registryPath = Join-Path $RouterHome 'config\operations.v2.json'
      $registry = Read-JsonFile -Path $registryPath
      $record = @($registry.operations | Where-Object {
        "$($_.id)" -eq $Operation -or "$($_.operation)" -eq $Operation
      }) | Select-Object -First 1
      if ($null -eq $record) {
        Write-Json -Payload ([ordered]@{
          timestamp = (Get-Date).ToString('o')
          schema = 'ariadne.autocad_router_operation_explain.v1'
          status = 'NOT_FOUND'
          operation = $Operation
          registry_path = $registryPath
          reason = "Operation '$Operation' is not present in config\operations.v2.json."
        })
        break
      }
      Write-Json -Payload ([ordered]@{
        timestamp = (Get-Date).ToString('o')
        schema = 'ariadne.autocad_router_operation_explain.v1'
        status = 'PASS'
        operation = $Operation
        registry_operation_status = "$($record.status)"
        registry_path = $registryPath
        record = $record
      })
      break
    }
    $status = Get-Status -Capabilities $capabilities
    $selection = Select-Route -Capabilities $capabilities -Status $status -Intent $Intent -Route $Route
    Write-Json -Payload ([ordered]@{
      timestamp    = (Get-Date).ToString('o')
      schema       = 'ariadne.autocad_router_explain.v2'
      status       = 'PASS'
      selection    = $selection
      capabilities = $capabilities.routes
    })
  }
}
