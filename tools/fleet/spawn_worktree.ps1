<#
  spawn_worktree.ps1 -- CADOS fleet worktree spawner [F7].

  Gives ONE parallel builder its OWN, disjoint execution surface:
    1. an isolated git worktree (own directory, own branch, forked from a
       PINNED base commit -- never a moving ref -- so every node spawned in
       the same batch forks from the exact same validated baseline);
    2. an absolute staging directory inside that worktree, under the same
       staging/ convention cadctl.py already uses (STAGING_GOLDEN_DIR =
       ROUTER_HOME / "staging" / "golden"); staging/ is repo-gitignored, so
       nothing here is ever accidentally committed;
    3. its own environment: a small, dot-sourceable env file written under
       that staging dir (CADOS_FLEET_WAVE / _NODE / _WORKTREE /
       _STAGING_DIR) so any tool the builder runs can discover its private
       paths instead of assuming a shared/relative one.

  This script only ADDS a worktree; it never deletes or force-resets one.
  Re-running it for a node that already exists is a safe no-op (idempotent):
  the existing worktree/branch is reused and only the staging dir + env file
  are (re)materialized.

  Usage:
    tools\fleet\spawn_worktree.ps1 -Node f20
    tools\fleet\spawn_worktree.ps1 -Node f20 -Wave w0 -BaseRef main
    tools\fleet\spawn_worktree.ps1 -Node f20 -RepoRoot D:\dev\99_tools\autocad-sdk-router -SiblingRoot D:\scratch

  Prints one JSON object (ariadne.cados.fleet_worktree.v1) to stdout.
#>
param(
  [Parameter(Mandatory = $true)]
  [string]$Node,
  [string]$Wave = 'w0',
  [string]$RepoRoot = '',
  [string]$BaseRef = 'HEAD',
  [string]$SiblingRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Node)) {
  throw 'Node id must be non-empty (e.g. -Node f20).'
}
if ($Node -notmatch '^[A-Za-z0-9_.-]+$') {
  throw "Node id contains characters unsafe for a path/branch segment: '$Node'"
}
if ([string]::IsNullOrWhiteSpace($Wave) -or ($Wave -notmatch '^[A-Za-z0-9_.-]+$')) {
  throw "Wave id contains characters unsafe for a path/branch segment: '$Wave'"
}

function Resolve-FleetRepoRoot {
  param([string]$Explicit)
  if (-not [string]::IsNullOrWhiteSpace($Explicit)) {
    return (Resolve-Path -LiteralPath $Explicit).Path
  }
  # Works whether this script is invoked from the main checkout or from any
  # linked worktree of the same repo: --git-common-dir always resolves to
  # <main-repo>\.git, regardless of which worktree is CWD or $PSScriptRoot.
  $commonDir = & git -C $PSScriptRoot rev-parse --path-format=absolute --git-common-dir 2>$null
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($commonDir)) {
    throw "Could not resolve the git repo containing $PSScriptRoot -- is this checked out under git?"
  }
  $commonDir = $commonDir.Trim().Replace('/', '\')
  return (Split-Path -Parent $commonDir)
}

function Test-FleetWorktreeRegistered {
  param([string]$RepoRoot, [string]$CandidatePath)
  $normalizedTarget = ([System.IO.Path]::GetFullPath($CandidatePath)).TrimEnd('\').ToLowerInvariant()
  $list = & git -C $RepoRoot worktree list --porcelain 2>$null
  foreach ($line in $list) {
    if ($line.StartsWith('worktree ')) {
      $wt = $line.Substring('worktree '.Length).Trim().Replace('/', '\').TrimEnd('\').ToLowerInvariant()
      if ($wt -eq $normalizedTarget) { return $true }
    }
  }
  return $false
}

function Test-FleetBranchExists {
  param([string]$RepoRoot, [string]$BranchName)
  & git -C $RepoRoot show-ref --verify --quiet "refs/heads/$BranchName"
  return ($LASTEXITCODE -eq 0)
}

$RepoRoot = Resolve-FleetRepoRoot -Explicit $RepoRoot
if ([string]::IsNullOrWhiteSpace($SiblingRoot)) {
  $SiblingRoot = Split-Path -Parent $RepoRoot
}
else {
  $SiblingRoot = (Resolve-Path -LiteralPath $SiblingRoot).Path
}

$repoName = Split-Path -Leaf $RepoRoot
$branch = "cados/${Wave}-${Node}"
$worktreePath = Join-Path $SiblingRoot "${repoName}__${Wave}_${Node}"

$baseCommit = (& git -C $RepoRoot rev-parse $BaseRef 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($baseCommit)) {
  throw "BaseRef '$BaseRef' did not resolve to a commit in $RepoRoot"
}
$baseCommit = $baseCommit.Trim()

$alreadyRegistered = Test-FleetWorktreeRegistered -RepoRoot $RepoRoot -CandidatePath $worktreePath
$createdWorktree = $false

if (-not $alreadyRegistered) {
  if (Test-Path -LiteralPath $worktreePath) {
    throw "Path exists but is not a registered git worktree of $RepoRoot -- refusing to touch it: $worktreePath"
  }
  # Capture git's own progress chatter (e.g. "Preparing worktree...", "HEAD is
  # now at ...") instead of letting it leak onto stdout ahead of the JSON
  # envelope below -- a caller doing `$json = & spawn_worktree.ps1 ... |
  # ConvertFrom-Json` must see ONLY that JSON on the success stream.
  if (Test-FleetBranchExists -RepoRoot $RepoRoot -BranchName $branch) {
    $gitAddOutput = & git -C $RepoRoot worktree add $worktreePath $branch 2>&1
  }
  else {
    $gitAddOutput = & git -C $RepoRoot worktree add -b $branch $worktreePath $baseCommit 2>&1
  }
  if ($LASTEXITCODE -ne 0) {
    $gitAddText = ($gitAddOutput | ForEach-Object { [string]$_ }) -join "`n"
    throw "git worktree add failed for $worktreePath (exit $LASTEXITCODE): $gitAddText"
  }
  $createdWorktree = $true
}

$worktreePath = (Resolve-Path -LiteralPath $worktreePath).Path
$stagingDir = Join-Path $worktreePath 'staging\fleet'
New-Item -ItemType Directory -Force -Path $stagingDir | Out-Null

$env:CADOS_FLEET_WAVE = $Wave
$env:CADOS_FLEET_NODE = $Node
$env:CADOS_FLEET_WORKTREE = $worktreePath
$env:CADOS_FLEET_STAGING_DIR = $stagingDir

$envFile = Join-Path $stagingDir 'fleet-env.ps1'
$envFileTemplate = @'
# Auto-generated by tools\fleet\spawn_worktree.ps1 -- do not hand-edit.
# Dot-source this to bind the CURRENT shell to the ${node} (${wave}) fleet builder:
#     . '${env_file}'
$env:CADOS_FLEET_WAVE        = '${wave}'
$env:CADOS_FLEET_NODE        = '${node}'
$env:CADOS_FLEET_WORKTREE    = '${worktree}'
$env:CADOS_FLEET_STAGING_DIR = '${staging}'
'@
$envFileText = $envFileTemplate.Replace('${node}', $Node).Replace('${wave}', $Wave).Replace('${worktree}', $worktreePath).Replace('${staging}', $stagingDir).Replace('${env_file}', $envFile)
$envFileText | Set-Content -LiteralPath $envFile -Encoding UTF8

[ordered]@{
  schema           = 'ariadne.cados.fleet_worktree.v1'
  status           = 'ok'
  wave             = $Wave
  node             = $Node
  repo_root        = $RepoRoot
  branch           = $branch
  base_ref         = $BaseRef
  base_commit      = $baseCommit
  worktree_path    = $worktreePath
  staging_dir      = $stagingDir
  env_file         = $envFile
  created_worktree = $createdWorktree
  reused_existing  = (-not $createdWorktree)
  env              = [ordered]@{
    CADOS_FLEET_WAVE        = $Wave
    CADOS_FLEET_NODE        = $Node
    CADOS_FLEET_WORKTREE    = $worktreePath
    CADOS_FLEET_STAGING_DIR = $stagingDir
  }
} | ConvertTo-Json -Depth 5
