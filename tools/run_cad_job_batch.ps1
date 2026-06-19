param(
  [Parameter(Mandatory = $true)]
  [string]$BatchPath,
  [string]$RouterPath = '',
  [string]$RootPath = '',
  [int]$LockTimeoutSeconds = 1800
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RouterPath)) {
  $RouterPath = Join-Path $PSScriptRoot 'autocad-router.ps1'
}
if ([string]::IsNullOrWhiteSpace($RootPath)) {
  $RootPath = Join-Path $PSScriptRoot '..'
}

$BatchPath = (Resolve-Path -LiteralPath $BatchPath).Path
$RouterPath = (Resolve-Path -LiteralPath $RouterPath).Path
$RootPath = (Resolve-Path -LiteralPath $RootPath).Path

function Get-PropertyValue {
  param([object]$Object, [string]$Name, [object]$Default = $null)
  if ($null -eq $Object) {
    return $Default
  }
  $property = $Object.PSObject.Properties[$Name]
  if ($null -eq $property) {
    return $Default
  }
  return $property.Value
}

function Resolve-TemplateString {
  param([string]$Text, [hashtable]$Variables)

  $resolved = $Text
  foreach ($key in $Variables.Keys) {
    $token = '${' + $key + '}'
    $resolved = $resolved.Replace($token, [string]$Variables[$key])
  }
  return $resolved
}

function Resolve-BatchPath {
  param([string]$Path, [string]$BasePath)

  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $BasePath $Path))
}

function Write-Json {
  param([object]$Payload)
  $Payload | ConvertTo-Json -Depth 32
}

$batch = Get-Content -LiteralPath $BatchPath -Raw -Encoding UTF8 | ConvertFrom-Json
$execution = Get-PropertyValue $batch 'execution'
$mode = [string](Get-PropertyValue $execution 'mode' 'sequential')
$parallel = [bool](Get-PropertyValue $execution 'parallel' $false)
$batchWriteMode = [string](Get-PropertyValue $execution 'write_mode' '')
if ($mode -ne 'sequential' -or $parallel) {
  throw 'CAD batch harness only supports sequential execution; parallel AutoCAD invocations are forbidden.'
}

$variables = @{}
$variables['repo_root'] = $RootPath
$variableObject = Get-PropertyValue $batch 'variables'
if ($null -ne $variableObject) {
  foreach ($property in $variableObject.PSObject.Properties) {
    $variables[$property.Name] = [string]$property.Value
  }
}
foreach ($key in @($variables.Keys)) {
  $variables[$key] = Resolve-TemplateString -Text ([string]$variables[$key]) -Variables $variables
}

$steps = @(Get-PropertyValue $batch 'steps')
if ($steps.Count -eq 0) {
  throw "CAD batch contains no steps: $BatchPath"
}

$mutexName = 'Global\AriadneCadJobBatchHarness'
$mutex = [System.Threading.Mutex]::new($false, $mutexName)
$hasMutex = $false
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ('ariadne_cad_job_batch_' + [System.Guid]::NewGuid().ToString('N'))

try {
  $hasMutex = $mutex.WaitOne([System.TimeSpan]::FromSeconds($LockTimeoutSeconds))
  if (-not $hasMutex) {
    throw "Timed out waiting for CAD batch mutex: $mutexName"
  }

  New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
  $results = @()
  $index = 0

  foreach ($step in $steps) {
    $index += 1
    $operation = Resolve-TemplateString -Text ([string](Get-PropertyValue $step 'operation')) -Variables $variables
    if ([string]::IsNullOrWhiteSpace($operation)) {
      throw "CAD batch step $index is missing operation."
    }
    $writeMode = Resolve-TemplateString -Text ([string](Get-PropertyValue $step 'write_mode' $batchWriteMode)) -Variables $variables

    $inputTemplate = [string](Get-PropertyValue $step 'input_path' (Get-PropertyValue $batch 'input_path'))
    if ([string]::IsNullOrWhiteSpace($inputTemplate)) {
      throw "CAD batch step $index is missing input_path."
    }
    $inputPath = Resolve-BatchPath -Path (Resolve-TemplateString -Text $inputTemplate -Variables $variables) -BasePath $RootPath

    $jobPathValue = [string](Get-PropertyValue $step 'job_path' '')
    $jobObject = Get-PropertyValue $step 'job'
    if (-not [string]::IsNullOrWhiteSpace($jobPathValue)) {
      $jobPath = Resolve-BatchPath -Path (Resolve-TemplateString -Text $jobPathValue -Variables $variables) -BasePath $RootPath
    }
    elseif ($null -ne $jobObject) {
      $safeOperation = $operation -replace '[^A-Za-z0-9_.-]', '_'
      $jobPath = Join-Path $tempDir ('{0:D2}_{1}.json' -f $index, $safeOperation)
      $jobJson = Resolve-TemplateString -Text ($jobObject | ConvertTo-Json -Depth 32) -Variables $variables
      $jobJson | Set-Content -LiteralPath $jobPath -Encoding UTF8

      $materializedJob = Get-Content -LiteralPath $jobPath -Raw -Encoding UTF8 | ConvertFrom-Json
      if ([string]$materializedJob.operation -ne $operation) {
        throw "CAD batch step $index operation does not match materialized job operation."
      }
    }
    else {
      throw "CAD batch step $index must define job_path or inline job."
    }

    $LASTEXITCODE = 0
    $routerOutput = @()
    $routerStatus = ''
    $routerEngineExitCode = $null
    try {
      $routerOutput = & $RouterPath `
        -Action 'run' `
        -Intent 'dwg' `
        -InputPath $inputPath `
        -Operation $operation `
        -JobPath $jobPath `
        -WriteMode $writeMode 2>&1
      $exitCode = [int]$LASTEXITCODE
      if (-not $?) {
        $exitCode = 1
      }
      $routerText = ($routerOutput | ForEach-Object { [string]$_ }) -join "`n"
      if (-not [string]::IsNullOrWhiteSpace($routerText)) {
        try {
          $routerJson = $routerText | ConvertFrom-Json
          $routerStatus = [string](Get-PropertyValue $routerJson 'status' '')
          $execution = Get-PropertyValue $routerJson 'execution'
          if ($null -ne $execution) {
            $routerEngineExitCode = Get-PropertyValue $execution 'engine_exit_code'
          }
          if ($routerStatus -and $routerStatus -ne 'PASS') {
            $exitCode = if ($null -ne $routerEngineExitCode -and [int]$routerEngineExitCode -ne 0) {
              [int]$routerEngineExitCode
            }
            else {
              1
            }
          }
        }
        catch {
          if ($exitCode -eq 0) {
            $exitCode = 1
            $routerStatus = 'UNPARSEABLE_ROUTER_OUTPUT'
          }
        }
      }
    }
    catch {
      $routerOutput = @($_.Exception.Message)
      $exitCode = 1
    }

    $results += [ordered]@{
      index = $index
      id = [string](Get-PropertyValue $step 'id' '')
      operation = $operation
      write_mode = $writeMode
      input_path = $inputPath
      job_path = $jobPath
      router_status = $routerStatus
      router_engine_exit_code = $routerEngineExitCode
      exit_code = $exitCode
      output = ($routerOutput | ForEach-Object { [string]$_ }) -join "`n"
    }

    if ($exitCode -ne 0) {
      Write-Json ([ordered]@{
        status = 'FAILED'
        batch_path = $BatchPath
        failed_step = $index
        results = $results
      })
      exit $exitCode
    }
  }

  Write-Json ([ordered]@{
    status = 'PASS'
    batch_path = $BatchPath
    results = $results
  })
}
finally {
  if (Test-Path -LiteralPath $tempDir) {
    Remove-Item -LiteralPath $tempDir -Recurse -Force
  }
  if ($hasMutex) {
    $mutex.ReleaseMutex()
  }
  if ($null -ne $mutex) {
    $mutex.Dispose()
  }
}
