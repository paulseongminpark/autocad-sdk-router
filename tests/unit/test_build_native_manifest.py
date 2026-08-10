from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cadctl  # noqa: E402


def _git(router: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(router), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout


def test_build_manifest_source_digest_matches_display_membership_verifier():
    """The producer and consumer independently derive the same native tree ID."""
    script_path = REPO / "tools" / "build_native_acad.ps1"
    ps_literal = str(script_path).replace("'", "''")
    root_literal = str(REPO).replace("'", "''")
    command = f"""
$scriptPath = '{ps_literal}'
$ErrorActionPreference = 'Stop'
$scriptText = Get-Content -Raw -LiteralPath $scriptPath
$functionStart = $scriptText.IndexOf('function Resolve-MSBuild')
$functionEnd = $scriptText.IndexOf('# Capture every provenance input before MSBuild')
if ($functionStart -lt 0 -or $functionEnd -lt 0) {{ throw 'build helper boundaries not found' }}
$RouterHome = '{root_literal}'
. ([scriptblock]::Create($scriptText.Substring($functionStart, $functionEnd - $functionStart)))
$inputs = @(Get-NativeSourceInputs)
[ordered]@{{ inputs = $inputs; digest = (Get-NativeSourceDigest $inputs) }} | ConvertTo-Json -Depth 8 -Compress
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    producer = json.loads(completed.stdout)
    consumer_inputs = cadctl._native_source_inputs(REPO)

    assert producer["inputs"] == consumer_inputs
    assert producer["digest"] == cadctl._source_tree_digest(consumer_inputs)


def test_build_snapshot_scopes_git_status_to_native_sources_and_detects_source_drift(
    tmp_path: Path,
):
    """A report change is not native build dirt, while source drift is."""
    router = tmp_path / "router"
    native = router / "src" / "Ariadne.AcadNative"
    dbx = router / "src" / "Ariadne.AcadNativeDbx"
    recipe = router / "tools" / "build_native_acad.ps1"
    report = router / "reports" / "autocad_router_status_latest.json"
    native.mkdir(parents=True)
    dbx.mkdir(parents=True)
    recipe.parent.mkdir(parents=True)
    report.parent.mkdir(parents=True)
    (native / "AriadneNativeJob.cpp").write_text("// native\n", encoding="utf-8")
    (dbx / "AriadneDbxEntry.cpp").write_text("// dbx\n", encoding="utf-8")
    recipe.write_text("# fixture recipe\n", encoding="utf-8")
    report.write_text('{"status":"baseline"}\n', encoding="utf-8")
    _git(router, "init", "-q")
    _git(router, "add", ".")
    _git(
        router,
        "-c",
        "user.name=Build Manifest Test",
        "-c",
        "user.email=build-manifest@example.invalid",
        "commit",
        "-qm",
        "fixture checkout",
    )
    report.write_text('{"status":"unrelated churn"}\n', encoding="utf-8")
    generated = native / "bin" / "x64" / "Release" / "generated.obj"
    generated.parent.mkdir(parents=True)
    generated.write_bytes(b"build output must not become source dirt")

    script_path = REPO / "tools" / "build_native_acad.ps1"
    ps_literal = str(script_path).replace("'", "''")
    root_literal = str(router).replace("'", "''")
    command = f"""
$ErrorActionPreference = 'Stop'
$scriptPath = '{ps_literal}'
$scriptText = Get-Content -Raw -LiteralPath $scriptPath
$functionStart = $scriptText.IndexOf('function Resolve-MSBuild')
$functionEnd = $scriptText.IndexOf('# Capture every provenance input before MSBuild')
if ($functionStart -lt 0 -or $functionEnd -lt 0) {{ throw 'build helper boundaries not found' }}
$RouterHome = '{root_literal}'
. ([scriptblock]::Create($scriptText.Substring($functionStart, $functionEnd - $functionStart)))
$before = Get-NativeBuildSnapshot
[System.IO.File]::AppendAllText((Join-Path $RouterHome 'src\\Ariadne.AcadNative\\AriadneNativeJob.cpp'), "// changed after snapshot`n")
$after = Get-NativeBuildSnapshot
[ordered]@{{
  before = $before
  after = $after
  exact_equal = (Test-NativeBuildSnapshotEqual -Before $before -After $after)
}} | ConvertTo-Json -Depth 12 -Compress
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    snapshot = json.loads(completed.stdout)

    assert snapshot["before"]["git"]["available"] is True
    assert snapshot["before"]["git"]["native_source_dirty"] is False
    assert snapshot["after"]["git"]["native_source_dirty"] is True
    assert snapshot["before"]["build_recipe"] == {
        "path": "tools/build_native_acad.ps1",
        "sha256": hashlib.sha256(recipe.read_bytes()).hexdigest(),
    }
    assert snapshot["exact_equal"] is False
    assert snapshot["before"]["source_tree"]["digest"] != snapshot["after"]["source_tree"]["digest"]
    assert all("/bin/" not in item["path"] for item in snapshot["before"]["source_tree"]["inputs"])


def test_build_manifest_writer_atomically_replaces_a_complete_json_file(tmp_path: Path):
    script_path = REPO / "tools" / "build_native_acad.ps1"
    destination = tmp_path / "native_build_manifest.json"
    ps_literal = str(script_path).replace("'", "''")
    destination_literal = str(destination).replace("'", "''")
    command = f"""
$ErrorActionPreference = 'Stop'
$scriptPath = '{ps_literal}'
$scriptText = Get-Content -Raw -LiteralPath $scriptPath
$functionStart = $scriptText.IndexOf('function Resolve-MSBuild')
$functionEnd = $scriptText.IndexOf('# Capture every provenance input before MSBuild')
if ($functionStart -lt 0 -or $functionEnd -lt 0) {{ throw 'build helper boundaries not found' }}
. ([scriptblock]::Create($scriptText.Substring($functionStart, $functionEnd - $functionStart)))
$target = '{destination_literal}'
Write-AtomicJson -Object ([ordered]@{{ schema = 'fixture'; revision = 1 }}) -Path $target
Write-AtomicJson -Object ([ordered]@{{ schema = 'fixture'; revision = 2 }}) -Path $target
[System.IO.File]::ReadAllText($target)
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {"schema": "fixture", "revision": 2}
    assert list(tmp_path.glob(".native_build_manifest.json.*.tmp")) == []
