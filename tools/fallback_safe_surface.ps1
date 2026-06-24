function Get-SafeFallbackImplementedOps {
  @(
    'automate.com.get_app',
    'automate.com.get_document',
    'automate.com.get_for_command',
    'automate.com.get_winapp',
    'automate.com.wrapper_for_object',
    'module.load.lisp'
  )
}

function Get-SafeFallbackStillBlockedOps {
  @(
    'automate.com.send_command',
    'command.invoke.coroutine',
    'command.invoke.sync',
    'command.invoke.sync.resbuf',
    'command.menu.invoke',
    'command.queue.post',
    'embed.ole.frame',
    'module.lifecycle.on_ole_unload'
  )
}

function Get-SafeManagedAdapterMap {
  [ordered]@{
    managed_cad_job = [ordered]@{
      loader = 'NETLOAD'
      dll_leaf = 'Ariadne.DwgGeometryExtractor.dll'
      command = 'ARIADNE_CAD_JOB'
      host_modes = @('coreconsole', 'full_autocad')
      raw_command_exposed = $false
    }
    geometry_extract = [ordered]@{
      loader = 'NETLOAD'
      dll_leaf = 'Ariadne.DwgGeometryExtractor.dll'
      command = 'ARIADNE_DWG_GEOM_EXTRACT'
      host_modes = @('coreconsole', 'full_autocad')
      raw_command_exposed = $false
    }
    objectdbx_extract = [ordered]@{
      loader = 'NETLOAD'
      dll_leaf = 'Ariadne.DwgGeometryExtractor.dll'
      command = 'ARIADNE_DWG_DBX_EXTRACT'
      host_modes = @('coreconsole', 'full_autocad')
      raw_command_exposed = $false
    }
  }
}

function Get-SafeLispAdapterNames {
  @('safe_status')
}

function Get-SafeFallbackRequestedOperation {
  if (-not [string]::IsNullOrWhiteSpace($script:JobPath) -and (Test-Path -LiteralPath $script:JobPath)) {
    $jobOp = Get-CadJobOperation -Path $script:JobPath
    if (-not [string]::IsNullOrWhiteSpace($jobOp)) {
      return $jobOp
    }
  }
  if (-not [string]::IsNullOrWhiteSpace($script:Operation)) {
    return $script:Operation
  }
  return ''
}

function Get-SafeFallbackJobRequest {
  $fallbackOp = Get-SafeFallbackRequestedOperation
  $request = [pscustomobject]@{
    schema = 'ariadne.autocad_sdk_job.v1'
    operation = $fallbackOp
    write_mode = 'read'
    args = [pscustomobject]@{}
  }
  if (-not [string]::IsNullOrWhiteSpace($script:JobPath) -and (Test-Path -LiteralPath $script:JobPath)) {
    try {
      $loaded = Get-Content -LiteralPath $script:JobPath -Raw -Encoding UTF8 | ConvertFrom-Json
      if ($null -ne $loaded) {
        $request = $loaded
        if ($null -eq $request.args) {
          $request | Add-Member -NotePropertyName args -NotePropertyValue ([pscustomobject]@{}) -Force
        }
      }
    }
    catch {}
  }
  return $request
}

function Get-SafeJobArgValue {
  param([object]$Job, [string]$Name, $Default = $null)
  if ($null -eq $Job -or $null -eq $Job.args) { return $Default }
  if ($Job.args.PSObject.Properties.Name -contains $Name) {
    $value = $Job.args.$Name
    if ($null -ne $value) { return $value }
  }
  return $Default
}

function Read-KeyValueFile {
  param([string]$Path)
  $out = [ordered]@{}
  if (-not (Test-Path -LiteralPath $Path)) { return $out }
  foreach ($line in (Get-Content -LiteralPath $Path -Encoding ASCII)) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    $parts = $line.Split('=', 2)
    if ($parts.Length -eq 2) {
      $out[$parts[0]] = $parts[1]
    }
  }
  return $out
}

function Try-GetComProperty {
  param([object]$ComObject, [string]$PropertyName, $Default = $null)
  if ($null -eq $ComObject) { return $Default }
  try {
    $value = $ComObject.$PropertyName
    if ($null -eq $value) { return $Default }
    return $value
  }
  catch {
    return $Default
  }
}

function Try-GetDocVariable {
  param([object]$Document, [string]$VariableName, $Default = $null)
  if ($null -eq $Document) { return $Default }
  try {
    $value = $Document.GetVariable($VariableName)
    if ($null -eq $value) { return $Default }
    return $value
  }
  catch {
    return $Default
  }
}

function Get-ActiveAutoCadComSession {
  $app = $null
  $progId = ''
  foreach ($candidate in @('AutoCAD.Application.26', 'AutoCAD.Application')) {
    try {
      $app = [Runtime.InteropServices.Marshal]::GetActiveObject($candidate)
      if ($app) {
        $progId = $candidate
        break
      }
    }
    catch {}
  }
  if (-not $app) {
    return [ordered]@{
      ok = $false
      engine_exit_code = -11
      code = 'NO_ACTIVE_AUTOCAD'
      detail = 'No running AutoCAD COM application was found for the safe fallback metadata surface.'
    }
  }

  $doc = $null
  try { $doc = $app.ActiveDocument } catch { $doc = $null }
  if (-not $doc) {
    return [ordered]@{
      ok = $false
      engine_exit_code = -12
      code = 'NO_ACTIVE_DOCUMENT'
      detail = 'AutoCAD is running but has no active document for the safe fallback metadata surface.'
      app = $app
      prog_id = $progId
    }
  }

  $activePath = ''
  try { $activePath = [string]$doc.FullName } catch {}
  if (-not [string]::IsNullOrWhiteSpace($script:InputPath) -and -not [string]::IsNullOrWhiteSpace($activePath)) {
    try {
      $want = [System.IO.Path]::GetFullPath($script:InputPath)
      $have = [System.IO.Path]::GetFullPath($activePath)
      if ($want.ToLowerInvariant() -ne $have.ToLowerInvariant()) {
        return [ordered]@{
          ok = $false
          engine_exit_code = -13
          code = 'ACTIVE_DOCUMENT_MISMATCH'
          detail = 'Refusing to inspect a different active drawing through the safe fallback COM surface.'
          requested_input = $want
          active_document = $have
          app = $app
          doc = $doc
          prog_id = $progId
        }
      }
    }
    catch {}
  }

  return [ordered]@{
    ok = $true
    engine_exit_code = 0
    app = $app
    doc = $doc
    active_document = $activePath
    prog_id = $progId
  }
}

function Invoke-SafeFallbackComMetadata {
  param([string]$OperationName)
  $session = Get-ActiveAutoCadComSession
  if (-not $session.ok) {
    return [ordered]@{
      engine_exit_code = $session.engine_exit_code
      engine_output = [ordered]@{
        status = $session.code
        mode = 'safe_com_metadata'
        operation = $OperationName
        raw_command_exposed = $false
        detail = $session.detail
        requested_input = $session.requested_input
        active_document = $session.active_document
      }
    }
  }

  $app = $session.app
  $doc = $session.doc
  $cmdNames = [string](Try-GetDocVariable -Document $doc -VariableName 'CMDNAMES' -Default '')
  $cmdActive = Try-GetDocVariable -Document $doc -VariableName 'CMDACTIVE' -Default 0
  $dbmod = Try-GetDocVariable -Document $doc -VariableName 'DBMOD' -Default 0
  $tileMode = Try-GetDocVariable -Document $doc -VariableName 'TILEMODE' -Default 1
  $ctab = [string](Try-GetDocVariable -Document $doc -VariableName 'CTAB' -Default '')
  $result = [ordered]@{}

  switch ($OperationName) {
    'automate.com.get_app' {
      $docs = Try-GetComProperty -ComObject $app -PropertyName 'Documents' -Default $null
      $docCount = 0
      try { if ($docs) { $docCount = [int]$docs.Count } } catch {}
      $result = [ordered]@{
        prog_id = $session.prog_id
        caption = [string](Try-GetComProperty -ComObject $app -PropertyName 'Caption' -Default '')
        version = [string](Try-GetComProperty -ComObject $app -PropertyName 'Version' -Default '')
        visible = [bool](Try-GetComProperty -ComObject $app -PropertyName 'Visible' -Default $false)
        hwnd = [string](Try-GetComProperty -ComObject $app -PropertyName 'HWND' -Default '')
        documents_count = $docCount
        active_document = $session.active_document
        com_dispatch_exposed = $false
      }
    }
    'automate.com.get_document' {
      $fullName = [string](Try-GetComProperty -ComObject $doc -PropertyName 'FullName' -Default '')
      $result = [ordered]@{
        name = [string](Try-GetComProperty -ComObject $doc -PropertyName 'Name' -Default '')
        full_name = $fullName
        directory = if ([string]::IsNullOrWhiteSpace($fullName)) { '' } else { Split-Path -Parent $fullName }
        saved = [bool](Try-GetComProperty -ComObject $doc -PropertyName 'Saved' -Default $false)
        active_layout = [string]$ctab
        dbmod = [int]$dbmod
        tilemode = [int]$tileMode
        idle = [string]::IsNullOrWhiteSpace($cmdNames)
        com_dispatch_exposed = $false
      }
    }
    'automate.com.get_for_command' {
      $result = [ordered]@{
        cmdnames = $cmdNames
        cmdactive = [int]$cmdActive
        dbmod = [int]$dbmod
        active_layout = [string]$ctab
        idle = [string]::IsNullOrWhiteSpace($cmdNames)
        sendcommand_exposed = $false
        command_unknown_interface_exposed = $false
      }
    }
    'automate.com.get_winapp' {
      $result = [ordered]@{
        prog_id = $session.prog_id
        caption = [string](Try-GetComProperty -ComObject $app -PropertyName 'Caption' -Default '')
        hwnd = [string](Try-GetComProperty -ComObject $app -PropertyName 'HWND' -Default '')
        visible = [bool](Try-GetComProperty -ComObject $app -PropertyName 'Visible' -Default $false)
        window_state = [string](Try-GetComProperty -ComObject $app -PropertyName 'WindowState' -Default '')
        active_document = $session.active_document
        com_dispatch_exposed = $false
      }
    }
    'automate.com.wrapper_for_object' {
      $job = Get-SafeFallbackJobRequest
      $handle = [string](Get-SafeJobArgValue -Job $job -Name 'handle' -Default '')
      if ([string]::IsNullOrWhiteSpace($handle)) {
        return [ordered]@{
          engine_exit_code = -15
          engine_output = [ordered]@{
            status = 'MISSING_ARG'
            mode = 'safe_com_metadata'
            operation = $OperationName
            raw_command_exposed = $false
            detail = 'automate.com.wrapper_for_object requires args.handle and returns bounded metadata only.'
          }
        }
      }
      $wrapped = $null
      try { $wrapped = $doc.HandleToObject($handle) } catch { $wrapped = $null }
      if (-not $wrapped) {
        return [ordered]@{
          engine_exit_code = -16
          engine_output = [ordered]@{
            status = 'HANDLE_NOT_FOUND'
            mode = 'safe_com_metadata'
            operation = $OperationName
            raw_command_exposed = $false
            handle = $handle
            active_document = $session.active_document
            detail = 'No object could be resolved for the requested handle through the bounded COM metadata surface.'
          }
        }
      }
      $result = [ordered]@{
        handle = [string](Try-GetComProperty -ComObject $wrapped -PropertyName 'Handle' -Default $handle)
        object_name = [string](Try-GetComProperty -ComObject $wrapped -PropertyName 'ObjectName' -Default '')
        entity_name = [string](Try-GetComProperty -ComObject $wrapped -PropertyName 'EntityName' -Default '')
        layer = [string](Try-GetComProperty -ComObject $wrapped -PropertyName 'Layer' -Default '')
        object_id = [string](Try-GetComProperty -ComObject $wrapped -PropertyName 'ObjectID' -Default '')
        has_extension_dictionary = [bool](Try-GetComProperty -ComObject $wrapped -PropertyName 'HasExtensionDictionary' -Default $false)
        com_wrapper_exposed = $false
      }
    }
    default {
      return $null
    }
  }

  return [ordered]@{
    engine_exit_code = 0
    engine_output = [ordered]@{
      status = 'ok'
      mode = 'safe_com_metadata'
      host = 'full_autocad_com_metadata'
      operation = $OperationName
      active_document = $session.active_document
      raw_command_exposed = $false
      result = $result
      detail = 'Bounded fallback metadata surface: returns structured metadata only and never surfaces IDispatch/IUnknown/SendCommand handles.'
    }
  }
}

function Invoke-SafeFallbackModuleLoadLisp {
  param([object]$Capabilities)

  $cap = @($Capabilities.routes | Where-Object { $_.id -eq 'dwg_truth_autocad' }) | Select-Object -First 1
  $engine = if ($cap) { $cap.engine_path } else { '' }
  if ([string]::IsNullOrWhiteSpace($engine) -or -not (Test-Path -LiteralPath $engine)) {
    return [ordered]@{
      engine_exit_code = -1
      engine_output = [ordered]@{
        status = 'ENGINE_NOT_AVAILABLE'
        operation = 'module.load.lisp'
        detail = "accoreconsole not found at $engine"
      }
    }
  }

  $job = Get-SafeFallbackJobRequest
  $adapter = [string](Get-SafeJobArgValue -Job $job -Name 'adapter' -Default 'safe_status')
  $supportedAdapters = @(Get-SafeLispAdapterNames)
  if ($supportedAdapters -notcontains $adapter) {
    return [ordered]@{
      engine_exit_code = -14
      engine_output = [ordered]@{
        status = 'ADAPTER_NOT_ALLOWED'
        operation = 'module.load.lisp'
        adapter = $adapter
        supported_adapters = $supportedAdapters
        raw_command_exposed = $false
        detail = 'module.load.lisp only accepts router-authored adapter names; no user-supplied LISP paths or command text are executed.'
      }
    }
  }

  $sourceDwg = $script:InputPath
  if ([string]::IsNullOrWhiteSpace($sourceDwg)) {
    $sourceDwg = Join-Path $script:RouterHome 'test_native\blank.dwg'
  }
  if ([string]::IsNullOrWhiteSpace($sourceDwg) -or -not (Test-Path -LiteralPath $sourceDwg)) {
    return [ordered]@{
      engine_exit_code = -15
      engine_output = [ordered]@{
        status = 'INPUT_REQUIRED'
        operation = 'module.load.lisp'
        adapter = $adapter
        raw_command_exposed = $false
        detail = 'module.load.lisp requires -InputPath <dwg> or the built-in test_native/blank.dwg fixture.'
      }
    }
  }

  $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
  $runOut = Join-Path $script:RunsDir "dwg_truth_autocad_fallback_lisp_$stamp"
  $stageRoot = Join-Path $script:StagingDir "dwg_fallback_lisp_$stamp"
  New-Item -ItemType Directory -Force -Path $runOut | Out-Null
  New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null

  $stagedDwg = Join-Path $stageRoot 'input.dwg'
  Copy-Item -LiteralPath $sourceDwg -Destination $stagedDwg -Force
  Set-ItemProperty -LiteralPath $stagedDwg -Name IsReadOnly -Value $false
  $dwgDir = Split-Path -Parent $stagedDwg

  $statusFile = Join-Path $runOut 'safe_lisp_status.txt'
  $statusFwd = $statusFile.Replace('\', '/')
  $lspPath = Join-Path $runOut 'safe_lisp_status.lsp'
  $lspLines = @(
    ('(setq ariadne-safe-status-file "{0}")' -f $statusFwd),
    '(defun ARIADNE_SAFE_LISP_STATUS (/ f)',
    '  (setq f (open ariadne-safe-status-file "w"))',
    '  (if f (progn',
    '    (write-line "status=ok" f)',
    '    (write-line "adapter=safe_status" f)',
    '    (write-line "raw_command_exposed=false" f)',
    '    (close f)))',
    '  (princ))',
    '(princ)'
  )
  $lspLines | Set-Content -LiteralPath $lspPath -Encoding ASCII

  $lspFwd = $lspPath.Replace('\', '/')
  $scrPath = Join-Path $runOut 'safe_lisp_status.scr'
  $scrLines = @(
    'SECURELOAD', '0',
    'FILEDIA', '0',
    'CMDECHO', '0',
    "(load `"$lspFwd`")",
    'ARIADNE_SAFE_LISP_STATUS',
    'QUIT',
    ''
  )
  $scrLines | Set-Content -LiteralPath $scrPath -Encoding ASCII

  $r = Invoke-AccoreScr -Engine $engine -StagedDwg $stagedDwg -ScrPath $scrPath -DwgDir $dwgDir -RunOut $runOut -EnvVars @{} -Tag 'safe_lisp_adapter'
  $statusMap = Read-KeyValueFile -Path $statusFile
  $ok = ($r.ExitCode -eq 0 -and "$($statusMap['status'])" -eq 'ok')

  return [ordered]@{
    engine_exit_code = if ($ok) { 0 } else { if ($r.ExitCode -ne 0) { $r.ExitCode } else { -3 } }
    engine_output = [ordered]@{
      status = if ($ok) { 'ok' } else { 'module_load_lisp_failed' }
      mode = 'safe_lisp_adapter'
      host = 'coreconsole_safe_lisp'
      operation = 'module.load.lisp'
      adapter = $adapter
      supported_adapters = $supportedAdapters
      input = $stagedDwg
      original_input = $sourceDwg
      lisp_module = $lspPath
      script = $scrPath
      status_file = $statusFile
      status_kv = $statusMap
      managed_adapter_map = Get-SafeManagedAdapterMap
      raw_command_exposed = $false
      stdout_tail = $r.StdoutTail
      process_hygiene = $r.Hygiene
      detail = 'Router-authored AutoLISP fallback only: loads a fixed status adapter and returns the allowlisted .NET adapter map; no user script text or arbitrary command dispatch is accepted.'
    }
  }
}

function Invoke-SafeFallbackOperation {
  param([object]$Capabilities)
  $op = Get-SafeFallbackRequestedOperation
  if ([string]::IsNullOrWhiteSpace($op)) { return $null }
  if ($op -eq 'module.load.lisp') {
    return Invoke-SafeFallbackModuleLoadLisp -Capabilities $Capabilities
  }
  if ((Get-SafeFallbackImplementedOps) -contains $op) {
    return Invoke-SafeFallbackComMetadata -OperationName $op
  }
  return $null
}
