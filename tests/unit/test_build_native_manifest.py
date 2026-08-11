from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cadctl  # noqa: E402


def _canonical_text_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


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


def _isolated_git_config_env() -> dict[str, str]:
    """Remove inherited command-scoped Git config from security-boundary tests."""
    return {
        key: value
        for key, value in os.environ.items()
        if key != "GIT_CONFIG_COUNT"
        and key != "GIT_CONFIG_PARAMETERS"
        and not key.startswith("GIT_CONFIG_KEY_")
        and not key.startswith("GIT_CONFIG_VALUE_")
    }


def _git_safe_directory_env(router: Path) -> dict[str, str]:
    """Trust one generated fixture repo without changing machine Git config."""
    env = _isolated_git_config_env()
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "safe.directory"
    env["GIT_CONFIG_VALUE_0"] = str(router)
    return env


def _replace_process_git_env(monkeypatch, env: dict[str, str]) -> None:
    """Apply the same isolated Git environment used by a child process."""
    git_keys = {key for key in os.environ if key.startswith("GIT_")}
    git_keys.update(key for key in env if key.startswith("GIT_"))
    for key in git_keys:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        if key.startswith("GIT_"):
            monkeypatch.setenv(key, value)


def _minimal_pe(
    *,
    machine: int = 0x8664,
    optional_magic: int = 0x20B,
    characteristics: int = 0x2000,
) -> bytes:
    """Independent, header-only PE fixture; it is never executed."""
    payload = bytearray(512)
    payload[0:2] = b"MZ"
    payload[0x3C:0x40] = (0x80).to_bytes(4, "little")
    payload[0x80:0x84] = b"PE\0\0"
    payload[0x84:0x86] = machine.to_bytes(2, "little")
    payload[0x86:0x88] = (1).to_bytes(2, "little")
    payload[0x94:0x96] = (0xF0).to_bytes(2, "little")
    payload[0x96:0x98] = characteristics.to_bytes(2, "little")
    payload[0x98:0x9A] = optional_magic.to_bytes(2, "little")
    return bytes(payload)


def _write_fake_msbuild(tmp_path: Path) -> Path:
    """Create a non-compiling MSBuild stand-in for producer race tests."""

    driver = tmp_path / "fake_msbuild.py"
    driver.write_text(
        r'''from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path


def minimal_pe(marker: int) -> bytes:
    payload = bytearray(512)
    payload[0:2] = b"MZ"
    payload[0x3C:0x40] = (0x80).to_bytes(4, "little")
    payload[0x80:0x84] = b"PE\0\0"
    payload[0x84:0x86] = (0x8664).to_bytes(2, "little")
    payload[0x86:0x88] = (1).to_bytes(2, "little")
    payload[0x94:0x96] = (0xF0).to_bytes(2, "little")
    payload[0x96:0x98] = (0x2000).to_bytes(2, "little")
    payload[0x98:0x9A] = (0x20B).to_bytes(2, "little")
    payload[-1] = marker
    return bytes(payload)


project = Path(sys.argv[1]).resolve()
arguments = sys.argv[2:]
out_dir = next(
    Path(item.split("=", 1)[1].rstrip("\\/"))
    for item in arguments
    if item.lower().startswith("/p:outdir=")
)
target_arg = next(
    (item.split("=", 1)[1] for item in arguments if item.lower().startswith("/p:targetname=")),
    None,
)
project_name = project.name.lower()
if ".dbx." in project_name:
    target_name = target_arg or "Ariadne.AcadNativeDbx"
    extension = ".dbx"
    marker = 1
elif ".crx." in project_name:
    target_name = target_arg or "Ariadne.AcadNative"
    extension = ".crx"
    marker = 2
else:
    target_name = target_arg or "Ariadne.AcadNative"
    extension = ".arx"
    marker = 3

mode = os.environ.get("NATIVE_ABA_MODE", "none")
status_path = Path(os.environ["NATIVE_ABA_STATUS"])
router = Path(os.environ["NATIVE_ABA_ROUTER"]).resolve()
source = Path(os.environ["NATIVE_ABA_SOURCE"])
recipe = Path(os.environ["NATIVE_ABA_RECIPE"])
status = {
    "project": str(project),
    "project_is_mirror": router not in project.parents,
}
mirror_root = project.parents[2]
mirror_source = mirror_root / source.relative_to(router)
mirror_recipe = mirror_root / recipe.relative_to(router)
status["mirror_source_hex"] = mirror_source.read_bytes().hex()
status["mirror_recipe_hex"] = mirror_recipe.read_bytes().hex()

if mode == "existing":
    for label, path in (("source", source), ("recipe", recipe)):
        original = path.read_bytes()
        try:
            path.write_bytes(b"temporary compiler generation\n")
            path.write_bytes(original)
            status[label] = "write_allowed"
        except OSError:
            status[label] = "write_blocked"
    status_path.write_text(json.dumps(status), encoding="utf-8")
    if status["source"] == "write_blocked" and status["recipe"] == "write_blocked":
        print("ABA_BLOCKED")
        raise SystemExit(73)

if mode == "mirror-existing":
    for label, path in (("source", mirror_source), ("recipe", mirror_recipe)):
        original = path.read_bytes()
        try:
            os.chmod(path, stat.S_IWRITE)
            path.write_bytes(b"temporary mirror compiler generation\n")
            path.write_bytes(original)
            status[label] = "write_allowed"
        except OSError:
            status[label] = "write_blocked"
    status_path.write_text(json.dumps(status), encoding="utf-8")
    if status["source"] == "write_blocked" and status["recipe"] == "write_blocked":
        print("MIRROR_ABA_BLOCKED")
        raise SystemExit(73)

if mode == "new-file":
    injected = source.parent / "temporary_compiler_input.hpp"
    injected.write_bytes(b"temporary untracked input\n")
    try:
        status["injected_visible_from_project"] = (
            project.parent / injected.name
        ).exists()
    finally:
        injected.unlink()
    status_path.write_text(json.dumps(status), encoding="utf-8")

status_path.write_text(json.dumps(status), encoding="utf-8")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / f"{target_name}{extension}").write_bytes(minimal_pe(marker))
''',
        encoding="utf-8",
    )
    wrapper = tmp_path / "fake_msbuild.cmd"
    wrapper.write_text(
        f'@echo off\r\n"{sys.executable}" "{driver}" %*\r\nexit /b %ERRORLEVEL%\r\n',
        encoding="ascii",
    )
    return wrapper


def _create_native_build_fixture(
    router: Path, *, initialize_git: bool = True
) -> tuple[Path, Path]:
    native = router / "src" / "Ariadne.AcadNative"
    dbx = router / "src" / "Ariadne.AcadNativeDbx"
    recipe = router / "tools" / "build_native_acad.ps1"
    native.mkdir(parents=True)
    dbx.mkdir(parents=True)
    recipe.parent.mkdir(parents=True)
    source = native / "AriadneNativeJob.cpp"
    source.write_bytes(b"// native generation A\n")
    (native / "AriadneNativeJob.h").write_bytes(b"// native header\n")
    (dbx / "AriadneDbxEntry.cpp").write_bytes(b"// dbx\n")
    for project in (
        native / "Ariadne.AcadNative.crx.vcxproj",
        native / "Ariadne.AcadNative.arx.vcxproj",
        dbx / "Ariadne.AcadNativeDbx.dbx.vcxproj",
    ):
        project.write_text("<Project />\n", encoding="utf-8")
    recipe.write_bytes((REPO / "tools" / "build_native_acad.ps1").read_bytes())
    if initialize_git:
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
    return source, recipe


def test_release_manifest_is_bound_to_an_explicit_rebuild_integrity_claim():
    """A Release receipt must describe a clean rebuild, not generic provenance."""
    text = (REPO / "tools" / "build_native_acad.ps1").read_text(encoding="utf-8")

    assert "$Configuration -ieq 'Release'" in text
    assert "'/t:Rebuild'" in text
    assert "build_target = $buildTarget" in text
    assert "claim_scope = $claimScope" in text
    assert "'release_build_integrity_bundle'" in text
    assert "cryptographic_provenance" not in text


def test_native_source_inventory_rejects_reparse_directories_before_descent():
    text = (REPO / "tools" / "build_native_acad.ps1").read_text(encoding="utf-8")
    function = text[
        text.index("function Get-NativeSourcePathRecords") : text.index(
            "function Get-NativeSourceInputs"
        )
    ]

    assert "System.Collections.Queue" in function
    assert "FileAttributes]::ReparsePoint" in function
    assert "Native source root is a reparse point" in function
    assert "Native source tree contains a reparse point" in function
    assert "Get-ChildItem -LiteralPath $root -Recurse" not in function


def test_native_artifact_verifier_accepts_only_nontrivial_x64_pe32_plus(tmp_path: Path):
    valid = tmp_path / "valid.arx"
    x86 = tmp_path / "x86.crx"
    pe32 = tmp_path / "pe32.dbx"
    tiny = tmp_path / "tiny.arx"
    bad_mz = tmp_path / "bad-mz.arx"
    non_dll = tmp_path / "non-dll.arx"
    valid.write_bytes(_minimal_pe())
    x86.write_bytes(_minimal_pe(machine=0x14C))
    pe32.write_bytes(_minimal_pe(optional_magic=0x10B))
    tiny.write_bytes(b"MZ")
    bad_mz.write_bytes(b"ZZ" + _minimal_pe()[2:])
    non_dll.write_bytes(_minimal_pe(characteristics=0))

    script_path = REPO / "tools" / "build_native_acad.ps1"
    literals = {
        name: str(path).replace("'", "''")
        for name, path in {
            "valid": valid,
            "x86": x86,
            "pe32": pe32,
            "tiny": tiny,
            "bad_mz": bad_mz,
            "non_dll": non_dll,
        }.items()
    }
    script_literal = str(script_path).replace("'", "''")
    command = f"""
$ErrorActionPreference = 'Stop'
$scriptText = Get-Content -Raw -LiteralPath '{script_literal}'
$functionStart = $scriptText.IndexOf('function Resolve-MSBuild')
$functionEnd = $scriptText.IndexOf('# Capture every provenance input before MSBuild')
if ($functionStart -lt 0 -or $functionEnd -lt 0) {{ throw 'build helper boundaries not found' }}
. ([scriptblock]::Create($scriptText.Substring($functionStart, $functionEnd - $functionStart)))
[ordered]@{{
  valid = Get-NativePeVerification -Path '{literals["valid"]}'
  x86 = Get-NativePeVerification -Path '{literals["x86"]}'
  pe32 = Get-NativePeVerification -Path '{literals["pe32"]}'
  tiny = Get-NativePeVerification -Path '{literals["tiny"]}'
  bad_mz = Get-NativePeVerification -Path '{literals["bad_mz"]}'
  non_dll_path = Get-NativePeVerification -Path '{literals["non_dll"]}'
  non_dll_bytes = Get-NativePeVerificationFromBytes -Bytes ([System.IO.File]::ReadAllBytes('{literals["non_dll"]}'))
}} | ConvertTo-Json -Depth 6 -Compress
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
    results = json.loads(completed.stdout)

    assert results["valid"]["verified"] is True
    assert results["valid"]["machine"] == "0x8664"
    assert results["valid"]["format"] == "PE32+"
    for key in ("x86", "pe32", "tiny", "bad_mz", "non_dll_path", "non_dll_bytes"):
        assert results[key]["verified"] is False, key
    assert "DLL" in results["non_dll_path"]["reason"]
    assert "DLL" in results["non_dll_bytes"]["reason"]


def test_native_artifact_record_never_mixes_two_byte_generations(tmp_path: Path):
    """PE identity, digest, and length must describe one captured generation."""

    artifact = tmp_path / "artifact.arx"
    generation_a = _minimal_pe()
    generation_b = bytes(len(generation_a))
    artifact.write_bytes(generation_a)

    script_path = REPO / "tools" / "build_native_acad.ps1"
    script_literal = str(script_path).replace("'", "''")
    bin_literal = str(tmp_path).replace("'", "''")
    artifact_literal = str(artifact).replace("'", "''")
    replacement_literal = str(tmp_path / "replacement.bin").replace("'", "''")
    (tmp_path / "replacement.bin").write_bytes(generation_b)
    command = f"""
$ErrorActionPreference = 'Stop'
$scriptText = Get-Content -Raw -LiteralPath '{script_literal}'
$functionStart = $scriptText.IndexOf('function Resolve-MSBuild')
$functionEnd = $scriptText.IndexOf('# Capture every provenance input before MSBuild')
. ([scriptblock]::Create($scriptText.Substring($functionStart, $functionEnd - $functionStart)))
function Get-NativePeVerification {{
  param([string]$Path)
  [System.IO.File]::Copy('{replacement_literal}', $Path, $true)
  return [pscustomobject]@{{
    verified = $true
    format = 'PE32+'
    machine = '0x8664'
    minimum_bytes = 512
    pe_header_offset = 128
    section_count = 1
    optional_header_bytes = 240
    reason = 'generation A was inspected before the fixture installed generation B'
  }}
}}
New-NativeArtifactRecord -BinDir '{bin_literal}' -Leaf 'artifact.arx' -Current $true |
  ConvertTo-Json -Depth 8 -Compress
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
    record = json.loads(completed.stdout)

    coherent_a = (
        record["sha256"] == hashlib.sha256(generation_a).hexdigest()
        and record["bytes"] == len(generation_a)
        and record["pe_verification"]["verified"] is True
    )
    coherent_b = (
        record["sha256"] == hashlib.sha256(generation_b).hexdigest()
        and record["bytes"] == len(generation_b)
        and record["pe_verification"]["verified"] is False
    )
    assert coherent_a or coherent_b, record


def test_native_artifact_lease_uses_one_generation_and_blocks_replacement(
    tmp_path: Path,
) -> None:
    build_bin = tmp_path / "build-bin"
    build_bin.mkdir()
    leaves = (
        "Ariadne.AcadNativeDbx.dbx",
        "Ariadne.AcadNative.crx",
        "Ariadne.AcadNative.arx",
    )
    expected = {}
    for marker, leaf in enumerate(leaves, start=1):
        payload = bytearray(_minimal_pe())
        payload[-1] = marker
        (build_bin / leaf).write_bytes(payload)
        expected[leaf] = hashlib.sha256(payload).hexdigest()

    script_path = REPO / "tools" / "build_native_acad.ps1"
    ps_literal = str(script_path).replace("'", "''")
    bin_literal = str(build_bin).replace("'", "''")
    command = f"""
$ErrorActionPreference = 'Stop'
$scriptText = Get-Content -Raw -LiteralPath '{ps_literal}'
$functionStart = $scriptText.IndexOf('function Resolve-MSBuild')
$functionEnd = $scriptText.IndexOf('# Capture every provenance input before MSBuild')
. ([scriptblock]::Create($scriptText.Substring($functionStart, $functionEnd - $functionStart)))
$leaves = @('Ariadne.AcadNativeDbx.dbx', 'Ariadne.AcadNative.crx', 'Ariadne.AcadNative.arx')
$specs = @($leaves | ForEach-Object {{ [pscustomobject]@{{ leaf = $_; current = $true; required = $true }} }})
$lease = Open-NativeArtifactLease -BinDir '{bin_literal}' -Specs $specs
try {{
  $blocked = @()
  foreach ($leaf in $leaves) {{
    try {{
      [System.IO.File]::WriteAllBytes((Join-Path '{bin_literal}' $leaf), [byte[]](1, 2, 3))
      $blocked += $false
    }} catch {{
      $blocked += $true
    }}
  }}
  [ordered]@{{ records = $lease.records; blocked = $blocked }} | ConvertTo-Json -Depth 8 -Compress
}} finally {{
  Close-NativeArtifactLease -Lease $lease
}}
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
    result = json.loads(completed.stdout)
    assert result["blocked"] == [True, True, True]
    assert {item["leaf"]: item["sha256"] for item in result["records"]} == expected
    assert all(item["pe_verification"]["verified"] for item in result["records"])

    # The finally released every handle; a new generation can be installed now.
    (build_bin / leaves[0]).write_bytes(b"new generation")


def test_prebuilt_publish_commits_all_three_or_restores_the_previous_set(tmp_path: Path):
    router = tmp_path / "router"
    native = router / "src" / "Ariadne.AcadNative"
    dbx_source = router / "src" / "Ariadne.AcadNativeDbx"
    recipe = router / "tools" / "build_native_acad.ps1"
    build_bin = router / "build-bin"
    success_dir = router / "prebuilt" / "success"
    failure_dir = router / "prebuilt" / "failure"
    native.mkdir(parents=True)
    dbx_source.mkdir(parents=True)
    recipe.parent.mkdir(parents=True)
    build_bin.mkdir(parents=True)
    success_dir.mkdir(parents=True)
    failure_dir.mkdir(parents=True)
    (native / "native.cpp").write_text("// native\n", encoding="utf-8")
    (dbx_source / "dbx.cpp").write_text("// dbx\n", encoding="utf-8")
    recipe.write_text("# fixture recipe\n", encoding="utf-8")
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

    leaves = (
        "Ariadne.AcadNativeDbx.dbx",
        "Ariadne.AcadNative.crx",
        "Ariadne.AcadNative.arx",
    )
    for index, leaf in enumerate(leaves, start=1):
        current = bytearray(_minimal_pe())
        current[-1] = index
        (build_bin / leaf).write_bytes(current)
        previous = bytearray(_minimal_pe())
        previous[-1] = index + 20
        (failure_dir / leaf).write_bytes(previous)
    expected_failure_hashes = {
        key: hashlib.sha256((failure_dir / leaf).read_bytes()).hexdigest()
        for key, leaf in zip(("dbx", "crx", "arx"), leaves)
    }
    previous_marker = b'{"deployment_state":"previous"}\n'
    (failure_dir / "native_deployment_manifest.json").write_bytes(previous_marker)

    script_path = REPO / "tools" / "build_native_acad.ps1"
    script_literal = str(script_path).replace("'", "''")
    router_literal = str(router).replace("'", "''")
    bin_literal = str(build_bin).replace("'", "''")
    success_literal = str(success_dir).replace("'", "''")
    failure_literal = str(failure_dir).replace("'", "''")
    command = f"""
$ErrorActionPreference = 'Stop'
$scriptText = Get-Content -Raw -LiteralPath '{script_literal}'
$functionStart = $scriptText.IndexOf('function Resolve-MSBuild')
$functionEnd = $scriptText.IndexOf('# Capture every provenance input before MSBuild')
if ($functionStart -lt 0 -or $functionEnd -lt 0) {{ throw 'build helper boundaries not found' }}
. ([scriptblock]::Create($scriptText.Substring($functionStart, $functionEnd - $functionStart)))
$RouterHome = '{router_literal}'
$bin = '{bin_literal}'
$leaves = @('Ariadne.AcadNativeDbx.dbx', 'Ariadne.AcadNative.crx', 'Ariadne.AcadNative.arx')
$snapshot = Get-NativeBuildSnapshot
$artifactSpecs = @($leaves | ForEach-Object {{ [pscustomobject]@{{ leaf = $_; current = $true; required = $true }} }})
$artifactLease = Open-NativeArtifactLease -BinDir $bin -Specs $artifactSpecs
$records = @($artifactLease.records)
$manifestPath = Join-Path $bin 'native_build_manifest.json'
$manifest = [ordered]@{{
  schema = 'ariadne.cad_os.native_build_manifest.v1'
  schema_version = 1
  claim_scope = 'release_build_integrity_bundle'
  configuration = 'Release'
  platform = 'x64'
  build_target = 'Rebuild'
  load_bin_dir = $bin
  source_tree = $snapshot.source_tree
  compilation_tree = $snapshot.compilation_tree
  source_provenance = [ordered]@{{ compilation_input = 'immutable_starting_snapshot_mirror' }}
  build_snapshot = [ordered]@{{
    input_mode = 'immutable_starting_snapshot_mirror'
    exact_match = $true
  }}
  artifacts = $records
}}
Write-AtomicJson -Object $manifest -Path $manifestPath
$verified = Confirm-NativeBuildManifest -ManifestPath $manifestPath -RequiredLeaves $leaves -ExpectedClaimScope 'release_build_integrity_bundle' -ExpectedBuildTarget 'Rebuild' -ExpectedConfiguration 'Release' -ExpectedPlatform 'x64' -ExpectedSourceTreeDigest $snapshot.source_tree.digest -ExpectedCompilationTreeDigest $snapshot.compilation_tree.digest
$success = Publish-NativePrebuiltSet -BinDir $bin -DeployDir '{success_literal}' -Leaves $leaves -BuildManifestVerification $verified -SourceSnapshot $snapshot -ArtifactContents $artifactLease.contents
$successMarkerPath = Join-Path '{success_literal}' 'native_deployment_manifest.json'
$successMarker = Get-Content -Raw -LiteralPath $successMarkerPath | ConvertFrom-Json
$successMarkerBytes = [System.IO.File]::ReadAllBytes($successMarkerPath)
$repeatSuccess = Publish-NativePrebuiltSet -BinDir $bin -DeployDir '{success_literal}' -Leaves $leaves -BuildManifestVerification $verified -SourceSnapshot $snapshot -ArtifactContents $artifactLease.contents
$repeatMarkerBytes = [System.IO.File]::ReadAllBytes($successMarkerPath)

$failureError = ''
$lockedPath = Join-Path '{failure_literal}' 'Ariadne.AcadNative.arx'
$lock = [System.IO.File]::Open($lockedPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::None)
try {{
  try {{
    Publish-NativePrebuiltSet -BinDir $bin -DeployDir '{failure_literal}' -Leaves $leaves -BuildManifestVerification $verified -SourceSnapshot $snapshot -ArtifactContents $artifactLease.contents | Out-Null
  }} catch {{
    $failureError = $_.Exception.Message
  }}
}} finally {{
  $lock.Dispose()
}}

$tamperedMarker = Get-Content -Raw -LiteralPath $successMarkerPath | ConvertFrom-Json
$tamperedMarker.claim_scope = 'cryptographic_provenance'
Write-AtomicJson -Object $tamperedMarker -Path $successMarkerPath
$tamperError = ''
try {{
  Confirm-NativeDeploymentManifest -ManifestPath $successMarkerPath -RequiredLeaves $leaves -ExpectedSourceTreeDigest $snapshot.source_tree.digest -ExpectedSourceInputs $snapshot.source_tree.inputs -ExpectedCompilationTreeDigest $snapshot.compilation_tree.digest -ExpectedCompilationInputs $snapshot.compilation_tree.inputs -ExpectedBuildRecipeSha256 $snapshot.build_recipe.sha256 | Out-Null
}} catch {{
  $tamperError = $_.Exception.Message
}}
Close-NativeArtifactLease -Lease $artifactLease

[ordered]@{{
  success = $success
  success_marker = $successMarker
  marker_repeat_same = [Convert]::ToBase64String($successMarkerBytes) -ceq [Convert]::ToBase64String($repeatMarkerBytes)
  tamper_error = $tamperError
  failure_error = $failureError
  failure_marker = [System.IO.File]::ReadAllText((Join-Path '{failure_literal}' 'native_deployment_manifest.json'))
  failure_sha256 = [ordered]@{{
    dbx = Get-Sha256File (Join-Path '{failure_literal}' 'Ariadne.AcadNativeDbx.dbx')
    crx = Get-Sha256File (Join-Path '{failure_literal}' 'Ariadne.AcadNative.crx')
    arx = Get-Sha256File (Join-Path '{failure_literal}' 'Ariadne.AcadNative.arx')
  }}
  staging_dirs = @(Get-ChildItem -LiteralPath (Split-Path -Parent '{failure_literal}') -Directory -Force | Where-Object {{ $_.Name.StartsWith('.native-deploy-') }}).Count
}} | ConvertTo-Json -Depth 12 -Compress
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=_git_safe_directory_env(router),
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)

    assert result["success"]["committed"] is True
    assert set(result["success"]["deployed_leaves"]) == set(leaves)
    assert result["success_marker"]["deployment_state"] == "committed"
    assert result["success_marker"]["claim_scope"] == "release_build_integrity_bundle"
    assert result["success_marker"]["source_tree_digest"]
    assert result["success_marker"]["source_tree"] == {
        "algorithm": "sha256",
        "canonicalization": "crlf_to_lf_unless_nul",
        "digest": result["success_marker"]["source_tree_digest"],
        "inputs": [
            {
                "path": "src/Ariadne.AcadNative/native.cpp",
                "sha256": _canonical_text_sha256(native / "native.cpp"),
                "bytes": len(
                    (native / "native.cpp").read_bytes().replace(b"\r\n", b"\n")
                ),
            },
            {
                "path": "src/Ariadne.AcadNativeDbx/dbx.cpp",
                "sha256": _canonical_text_sha256(dbx_source / "dbx.cpp"),
                "bytes": len(
                    (dbx_source / "dbx.cpp")
                    .read_bytes()
                    .replace(b"\r\n", b"\n")
                ),
            },
        ],
    }
    assert result["success_marker"]["compilation_tree"] == {
        "algorithm": "sha256",
        "byte_representation": "canonical_lf_unless_nul_mirror_bytes",
        "digest": result["success_marker"]["compilation_tree_digest"],
        "inputs": [
            {
                "path": "src/Ariadne.AcadNative/native.cpp",
                "sha256": _canonical_text_sha256(native / "native.cpp"),
                "bytes": len(
                    (native / "native.cpp").read_bytes().replace(b"\r\n", b"\n")
                ),
            },
            {
                "path": "src/Ariadne.AcadNativeDbx/dbx.cpp",
                "sha256": _canonical_text_sha256(dbx_source / "dbx.cpp"),
                "bytes": len(
                    (dbx_source / "dbx.cpp")
                    .read_bytes()
                    .replace(b"\r\n", b"\n")
                ),
            },
        ],
    }
    assert result["success_marker"]["build_recipe"] == {
        "path": "tools/build_native_acad.ps1",
        "sha256": _canonical_text_sha256(recipe),
    }
    assert "build_manifest" not in result["success_marker"]
    assert "committed_utc" not in result["success_marker"]
    assert "deploy_dir" not in result["success_marker"]
    assert result["marker_repeat_same"] is True
    assert result["tamper_error"]
    assert result["failure_error"]
    assert result["failure_marker"].encode() == previous_marker
    assert result["staging_dirs"] == 0
    assert result["failure_sha256"] == expected_failure_hashes


def test_main_publishes_prebuilt_only_after_snapshot_and_final_manifest_verification():
    text = (REPO / "tools" / "build_native_acad.ps1").read_text(encoding="utf-8")
    main = text.split("# Capture every provenance input before MSBuild", 1)[1]

    git_guard = main.index("if ($nativeBuildSnapshotBefore.git.available -ne $true)")
    msbuild_resolve = main.index("$msbuild = Resolve-MSBuild")
    post_snapshot = main.index("$nativeBuildSnapshotBeforeManifest = Get-NativeBuildSnapshot")
    manifest_write = main.index("Write-AtomicJson -Object $manifest -Path $manifestPath")
    manifest_verify = main.index("$manifestVerification = Confirm-NativeBuildManifest")
    prebuilt_publish = main.index("$prebuiltDeployment = Publish-NativePrebuiltSet")
    prebuilt_gate_start = main.index("$prebuiltEligible = (")
    prebuilt_gate_end = main.index(
        "if (-not $isolatedBuild -and [string]::IsNullOrWhiteSpace($TargetSuffix))",
        prebuilt_gate_start,
    )
    prebuilt_gate = main[prebuilt_gate_start:prebuilt_gate_end]
    assert git_guard < msbuild_resolve
    assert post_snapshot < manifest_write < manifest_verify < prebuilt_publish
    assert "@('Ariadne.AcadNativeDbx.dbx', 'Ariadne.AcadNative.crx', 'Ariadne.AcadNative.arx')" in main
    assert "$gitState.available -eq $true" in prebuilt_gate
    assert "$gitState.native_source_dirty -eq $false" in prebuilt_gate
    assert "$sourceAuthority.source_inventory_authoritative -eq $true" in prebuilt_gate
    assert "$sourceAuthority.captured_inputs_match_head -eq $true" in prebuilt_gate
    assert "Copy-Item -LiteralPath $src -Destination" not in main


def test_prebuilt_publisher_rejects_unknown_git_provenance_before_staging(
    tmp_path: Path,
):
    build_bin = tmp_path / "build-bin"
    deploy_dir = tmp_path / "prebuilt" / "2027"
    build_bin.mkdir()
    deploy_dir.mkdir(parents=True)
    script_path = REPO / "tools" / "build_native_acad.ps1"
    script_literal = str(script_path).replace("'", "''")
    bin_literal = str(build_bin).replace("'", "''")
    deploy_literal = str(deploy_dir).replace("'", "''")
    command = f"""
$ErrorActionPreference = 'Stop'
$scriptText = Get-Content -Raw -LiteralPath '{script_literal}'
$functionStart = $scriptText.IndexOf('function Resolve-MSBuild')
$functionEnd = $scriptText.IndexOf('# Capture every provenance input before MSBuild')
if ($functionStart -lt 0 -or $functionEnd -lt 0) {{ throw 'build helper boundaries not found' }}
. ([scriptblock]::Create($scriptText.Substring($functionStart, $functionEnd - $functionStart)))
$snapshot = [pscustomobject]@{{
  git = [pscustomobject]@{{ available = $false }}
}}
$verification = [pscustomobject]@{{
  verified = $true
  claim_scope = 'release_build_integrity_bundle'
  build_target = 'Rebuild'
  configuration = 'Release'
  platform = 'x64'
}}
$errorText = ''
try {{
  Publish-NativePrebuiltSet `
    -BinDir '{bin_literal}' `
    -DeployDir '{deploy_literal}' `
    -Leaves @('Ariadne.AcadNativeDbx.dbx', 'Ariadne.AcadNative.crx', 'Ariadne.AcadNative.arx') `
    -BuildManifestVerification $verification `
    -SourceSnapshot $snapshot | Out-Null
}} catch {{
  $errorText = $_.Exception.Message
}}
$errorText
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
    assert "Git checkout identity is unavailable; refusing prebuilt publication." in completed.stdout
    assert list(tmp_path.rglob(".native-deploy-*")) == []


def test_native_build_rejects_unknown_git_provenance_before_msbuild(
    tmp_path: Path,
) -> None:
    router = tmp_path / "router"
    _create_native_build_fixture(router, initialize_git=False)
    output_root = tmp_path / "build-output"

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(REPO / "tools" / "build_native_acad.ps1"),
            "-RouterHome",
            str(router),
            "-OutputRoot",
            str(output_root),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=_isolated_git_config_env(),
    )
    assert completed.returncode != 0
    assert (
        "Git checkout identity is unavailable; refusing native build before MSBuild."
        in completed.stdout + completed.stderr
    )
    assert not output_root.exists()


def test_native_build_blocks_existing_source_and_recipe_aba_before_publish(
    tmp_path: Path,
) -> None:
    """A compiler-side A->B->A swap must not reach a manifest or deployment."""

    router = tmp_path / "router"
    source, recipe = _create_native_build_fixture(router)
    fake_msbuild = _write_fake_msbuild(tmp_path)
    output_root = tmp_path / "build-output"
    status_path = tmp_path / "aba-status.json"
    env = _git_safe_directory_env(router)
    env.update(
        {
            "NATIVE_ABA_MODE": "existing",
            "NATIVE_ABA_STATUS": str(status_path),
            "NATIVE_ABA_ROUTER": str(router),
            "NATIVE_ABA_SOURCE": str(source),
            "NATIVE_ABA_RECIPE": str(recipe),
        }
    )

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(REPO / "tools" / "build_native_acad.ps1"),
            "-RouterHome",
            str(router),
            "-OutputRoot",
            str(output_root),
            "-MSBuildExe",
            str(fake_msbuild),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert completed.returncode != 0
    assert "ABA_BLOCKED" in completed.stdout + completed.stderr
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["source"] == "write_blocked"
    assert status["recipe"] == "write_blocked"
    assert not list(output_root.rglob("native_build_manifest.json"))
    assert not list(router.rglob("native_deployment_manifest.json"))
    assert source.read_bytes() == b"// native generation A\n"


def test_native_build_blocks_mirror_source_and_recipe_aba_before_publish(
    tmp_path: Path,
) -> None:
    """Clearing ReadOnly must not permit an A->B->A swap in the build mirror."""

    router = tmp_path / "router"
    source, recipe = _create_native_build_fixture(router)
    fake_msbuild = _write_fake_msbuild(tmp_path)
    output_root = tmp_path / "build-output"
    status_path = tmp_path / "mirror-aba-status.json"
    env = _git_safe_directory_env(router)
    env.update(
        {
            "NATIVE_ABA_MODE": "mirror-existing",
            "NATIVE_ABA_STATUS": str(status_path),
            "NATIVE_ABA_ROUTER": str(router),
            "NATIVE_ABA_SOURCE": str(source),
            "NATIVE_ABA_RECIPE": str(recipe),
        }
    )

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(REPO / "tools" / "build_native_acad.ps1"),
            "-RouterHome",
            str(router),
            "-OutputRoot",
            str(output_root),
            "-MSBuildExe",
            str(fake_msbuild),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert completed.returncode != 0
    assert "MIRROR_ABA_BLOCKED" in completed.stdout + completed.stderr
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["source"] == "write_blocked"
    assert status["recipe"] == "write_blocked"
    assert not list(output_root.rglob("native_build_manifest.json"))
    assert not list(router.rglob("native_deployment_manifest.json"))


@pytest.mark.parametrize("ignored", (False, True))
def test_native_build_never_publishes_untracked_or_ignored_compiler_inputs(
    tmp_path: Path,
    ignored: bool,
) -> None:
    """A canonical prebuilt set may contain only exact HEAD-tracked inputs."""

    router = tmp_path / ("router-ignored" if ignored else "router-untracked")
    source, recipe = _create_native_build_fixture(router)
    injected_relative = "src/Ariadne.AcadNative/injected-compiler-input.hpp"
    injected = router / injected_relative
    injected.write_text("// not present in HEAD\n", encoding="utf-8")
    if ignored:
        exclude = router / ".git" / "info" / "exclude"
        with exclude.open("a", encoding="utf-8") as stream:
            stream.write("\n" + injected_relative + "\n")
        assert _git(router, "status", "--porcelain", "--", injected_relative) == ""

    deploy_dir = router / "prebuilt" / "2027"
    deploy_dir.mkdir(parents=True)
    old_payloads: dict[str, bytes] = {}
    for marker, leaf in enumerate(
        (
            "Ariadne.AcadNativeDbx.dbx",
            "Ariadne.AcadNative.crx",
            "Ariadne.AcadNative.arx",
        ),
        start=40,
    ):
        payload = bytearray(_minimal_pe())
        payload[-1] = marker
        old_payloads[leaf] = bytes(payload)
        (deploy_dir / leaf).write_bytes(payload)

    status_path = tmp_path / f"unused-{'ignored' if ignored else 'untracked'}.json"
    fake_msbuild = _write_fake_msbuild(tmp_path)
    env = _git_safe_directory_env(router)
    env.update(
        {
            "NATIVE_ABA_MODE": "none",
            "NATIVE_ABA_STATUS": str(status_path),
            "NATIVE_ABA_ROUTER": str(router),
            "NATIVE_ABA_SOURCE": str(source),
            "NATIVE_ABA_RECIPE": str(recipe),
        }
    )
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(REPO / "tools" / "build_native_acad.ps1"),
            "-RouterHome",
            str(router),
            "-MSBuildExe",
            str(fake_msbuild),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout)
    assert result["prebuilt_deployment"]["committed"] is False
    assert "HEAD-tracked" in result["prebuilt_deployment"]["reason"]
    assert not (deploy_dir / "native_deployment_manifest.json").exists()
    assert {
        leaf: (deploy_dir / leaf).read_bytes() for leaf in old_payloads
    } == old_payloads


def test_native_source_authority_binds_the_build_recipe_to_exact_head(
    tmp_path: Path,
) -> None:
    router = tmp_path / "router-dirty-recipe"
    _source, recipe = _create_native_build_fixture(router)
    recipe.write_bytes(recipe.read_bytes() + b"\n# not present in HEAD\n")
    assert _git(
        router,
        "status",
        "--porcelain",
        "--",
        "src/Ariadne.AcadNative",
        "src/Ariadne.AcadNativeDbx",
    ) == ""

    script_literal = str(REPO / "tools" / "build_native_acad.ps1").replace("'", "''")
    router_literal = str(router).replace("'", "''")
    command = f"""
$ErrorActionPreference = 'Stop'
$scriptText = Get-Content -Raw -LiteralPath '{script_literal}'
$functionStart = $scriptText.IndexOf('function Resolve-MSBuild')
$functionEnd = $scriptText.IndexOf('# Capture every provenance input before MSBuild')
$RouterHome = '{router_literal}'
. ([scriptblock]::Create($scriptText.Substring($functionStart, $functionEnd - $functionStart)))
$snapshot = Get-NativeBuildSnapshot
[ordered]@{{ git = $snapshot.git; authority = $snapshot.source_authority }} | ConvertTo-Json -Depth 8 -Compress
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=_git_safe_directory_env(router),
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["git"]["native_source_dirty"] is False
    assert result["authority"]["source_inventory_authoritative"] is True
    assert result["authority"]["captured_inputs_match_head"] is False
    assert "HEAD blob" in result["authority"]["reason"]


def test_native_build_compiles_only_the_starting_immutable_source_mirror(
    tmp_path: Path,
) -> None:
    """A temporary new source file in the checkout cannot enter compilation."""

    router = tmp_path / "router"
    source, recipe = _create_native_build_fixture(router)
    fake_msbuild = _write_fake_msbuild(tmp_path)
    output_root = tmp_path / "build-output"
    status_path = tmp_path / "new-file-status.json"
    env = _git_safe_directory_env(router)
    env.update(
        {
            "NATIVE_ABA_MODE": "new-file",
            "NATIVE_ABA_STATUS": str(status_path),
            "NATIVE_ABA_ROUTER": str(router),
            "NATIVE_ABA_SOURCE": str(source),
            "NATIVE_ABA_RECIPE": str(recipe),
        }
    )

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(REPO / "tools" / "build_native_acad.ps1"),
            "-RouterHome",
            str(router),
            "-OutputRoot",
            str(output_root),
            "-MSBuildExe",
            str(fake_msbuild),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout)
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["project_is_mirror"] is True
    assert status["injected_visible_from_project"] is False
    assert Path(status["project"]).is_relative_to(Path(os.environ["TEMP"]))
    assert result["build_manifest_verification"]["verified"] is True
    assert not (source.parent / "temporary_compiler_input.hpp").exists()


def test_native_build_materializes_canonical_bytes_in_compiler_mirror(
    tmp_path: Path,
) -> None:
    """The compiler-facing mirror contains the canonical leased generation."""

    router = tmp_path / "router"
    source, recipe = _create_native_build_fixture(router)
    source_raw = b"// first\r\n// second\rthird\n"
    recipe_raw = b"# binary-like\r\n\0# preserve\r\n"
    source.write_bytes(source_raw)
    recipe.write_bytes(recipe_raw)
    _git(router, "add", ".")
    _git(
        router,
        "-c",
        "user.name=Build Manifest Test",
        "-c",
        "user.email=build-manifest@example.invalid",
        "commit",
        "-qm",
        "mixed line ending fixture",
    )
    fake_msbuild = _write_fake_msbuild(tmp_path)
    status_path = tmp_path / "canonical-mirror-status.json"
    env = _git_safe_directory_env(router)
    env.update(
        {
            "NATIVE_ABA_MODE": "none",
            "NATIVE_ABA_STATUS": str(status_path),
            "NATIVE_ABA_ROUTER": str(router),
            "NATIVE_ABA_SOURCE": str(source),
            "NATIVE_ABA_RECIPE": str(recipe),
        }
    )

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(REPO / "tools" / "build_native_acad.ps1"),
            "-RouterHome",
            str(router),
            "-OutputRoot",
            str(tmp_path / "build-output"),
            "-MSBuildExe",
            str(fake_msbuild),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    status = json.loads(status_path.read_text(encoding="utf-8"))
    result = json.loads(completed.stdout)
    assert bytes.fromhex(status["mirror_source_hex"]) == source_raw.replace(
        b"\r\n", b"\n"
    )
    assert bytes.fromhex(status["mirror_recipe_hex"]) == recipe_raw
    build_manifest = json.loads(
        Path(result["build_manifest_path"]).read_text(encoding="utf-8-sig")
    )
    assert build_manifest["compilation_tree"]["byte_representation"] == (
        "canonical_lf_unless_nul_mirror_bytes"
    )
    assert build_manifest["compilation_tree"]["inputs"] == (
        build_manifest["source_tree"]["inputs"]
    )


def test_native_build_scrubs_inherited_git_repo_redirection_before_msbuild(
    tmp_path: Path,
) -> None:
    """GIT_DIR/GIT_WORK_TREE cannot substitute a clean decoy checkout."""

    router = tmp_path / "not-a-repo"
    source, recipe = _create_native_build_fixture(router, initialize_git=False)
    # Remove only the real repository metadata; inherited variables will point
    # at the otherwise valid clean decoy repository.
    decoy = tmp_path / "decoy"
    _create_native_build_fixture(decoy)
    called = tmp_path / "msbuild-called.txt"
    marker_wrapper = tmp_path / "must-not-run.cmd"
    marker_wrapper.write_text(
        f'@echo called>"{called}"\r\nexit /b 99\r\n', encoding="ascii"
    )
    env = _isolated_git_config_env()
    env.update(
        {
            "GIT_DIR": str(decoy / ".git"),
            "GIT_WORK_TREE": str(decoy),
            "NATIVE_ABA_MODE": "none",
            "NATIVE_ABA_STATUS": str(tmp_path / "unused.json"),
            "NATIVE_ABA_ROUTER": str(router),
            "NATIVE_ABA_SOURCE": str(source),
            "NATIVE_ABA_RECIPE": str(recipe),
        }
    )

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(REPO / "tools" / "build_native_acad.ps1"),
            "-RouterHome",
            str(router),
            "-OutputRoot",
            str(tmp_path / "build-output"),
            "-MSBuildExe",
            str(marker_wrapper),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert completed.returncode != 0
    assert "Git checkout identity is unavailable" in completed.stdout + completed.stderr
    assert not called.exists()


def test_native_build_rejects_hidden_native_index_flags_before_msbuild(
    tmp_path: Path,
) -> None:
    router = tmp_path / "router"
    source, _recipe = _create_native_build_fixture(router)
    relative_source = source.relative_to(router).as_posix()
    _git(router, "update-index", "--assume-unchanged", relative_source)
    called = tmp_path / "msbuild-called.txt"
    marker_wrapper = tmp_path / "must-not-run.cmd"
    marker_wrapper.write_text(
        f'@echo called>"{called}"\r\nexit /b 99\r\n', encoding="ascii"
    )

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(REPO / "tools" / "build_native_acad.ps1"),
            "-RouterHome",
            str(router),
            "-OutputRoot",
            str(tmp_path / "build-output"),
            "-MSBuildExe",
            str(marker_wrapper),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=_git_safe_directory_env(router),
    )

    assert completed.returncode != 0
    assert "Git index visibility is weakened" in completed.stdout + completed.stderr
    assert not called.exists()


def test_native_input_and_artifact_leases_release_on_100_failure_paths(
    tmp_path: Path,
) -> None:
    router = tmp_path / "router"
    source, _recipe = _create_native_build_fixture(router)
    build_bin = tmp_path / "build-bin"
    build_bin.mkdir()
    artifact_leaves = (
        "Ariadne.AcadNativeDbx.dbx",
        "Ariadne.AcadNative.crx",
        "Ariadne.AcadNative.arx",
    )
    for marker, leaf in enumerate(artifact_leaves, start=1):
        payload = bytearray(_minimal_pe())
        payload[-1] = marker
        (build_bin / leaf).write_bytes(payload)
    script_path = REPO / "tools" / "build_native_acad.ps1"
    ps_literal = str(script_path).replace("'", "''")
    root_literal = str(router).replace("'", "''")
    source_literal = str(source).replace("'", "''")
    bin_literal = str(build_bin).replace("'", "''")
    command = f"""
$ErrorActionPreference = 'Stop'
$scriptText = Get-Content -Raw -LiteralPath '{ps_literal}'
$functionStart = $scriptText.IndexOf('function Resolve-MSBuild')
$functionEnd = $scriptText.IndexOf('# Capture every provenance input before MSBuild')
$RouterHome = '{root_literal}'
. ([scriptblock]::Create($scriptText.Substring($functionStart, $functionEnd - $functionStart)))
$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$before = @(Get-ChildItem -LiteralPath $tempRoot -Directory -Force | Where-Object {{ $_.Name -match '^\\.ariadne-native-source-[0-9a-f]{{32}}$' }}).Count
$mirrorWriteBlocks = 0
for ($iteration = 1; $iteration -le 100; $iteration++) {{
  $lease = $null
  $mirrorRoot = $null
  try {{
    $lease = Open-NativeBuildInputLease
    $mirrorRoot = $lease.mirror_root
    $mirrorPath = [string]$lease.mirror_captures[0].stream.Name
    [System.IO.File]::SetAttributes($mirrorPath, [System.IO.FileAttributes]::Normal)
    try {{
      $mirrorProbe = [System.IO.File]::Open(
        $mirrorPath,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
      )
      $mirrorProbe.Dispose()
      throw 'fixture mirror write unexpectedly succeeded'
    }} catch [System.IO.IOException] {{
      $mirrorWriteBlocks++
    }}
    throw 'fixture failure after acquisition'
  }} catch {{
    if ($_.Exception.Message -cne 'fixture failure after acquisition') {{ throw }}
  }} finally {{
    Close-NativeBuildInputLease -Lease $lease
  }}
  if ($null -ne $mirrorRoot -and (Test-Path -LiteralPath $mirrorRoot)) {{
    throw "fixture mirror survived cleanup: $mirrorRoot"
  }}
  $probe = [System.IO.File]::Open(
    '{source_literal}',
    [System.IO.FileMode]::Open,
    [System.IO.FileAccess]::ReadWrite,
    [System.IO.FileShare]::None
  )
  $probe.Dispose()
}}
$artifactLeaves = @('Ariadne.AcadNativeDbx.dbx', 'Ariadne.AcadNative.crx', 'Ariadne.AcadNative.arx')
$artifactSpecs = @($artifactLeaves | ForEach-Object {{ [pscustomobject]@{{ leaf = $_; current = $true; required = $true }} }})
for ($iteration = 1; $iteration -le 100; $iteration++) {{
  $artifactLease = $null
  try {{
    $artifactLease = Open-NativeArtifactLease -BinDir '{bin_literal}' -Specs $artifactSpecs
    throw 'fixture artifact failure after acquisition'
  }} catch {{
    if ($_.Exception.Message -cne 'fixture artifact failure after acquisition') {{ throw }}
  }} finally {{
    Close-NativeArtifactLease -Lease $artifactLease
  }}
  $artifactProbe = [System.IO.File]::Open(
    (Join-Path '{bin_literal}' $artifactLeaves[0]),
    [System.IO.FileMode]::Open,
    [System.IO.FileAccess]::ReadWrite,
    [System.IO.FileShare]::None
  )
  $artifactProbe.Dispose()
}}
$after = @(Get-ChildItem -LiteralPath $tempRoot -Directory -Force | Where-Object {{ $_.Name -match '^\\.ariadne-native-source-[0-9a-f]{{32}}$' }}).Count
[ordered]@{{ input_iterations = 100; mirror_write_blocks = $mirrorWriteBlocks; artifact_iterations = 100; before = $before; after = $after }} | ConvertTo-Json -Compress
"""
    process_temp = tmp_path / "process-temp"
    process_temp.mkdir()
    process_env = _git_safe_directory_env(router)
    process_env["TEMP"] = str(process_temp)
    process_env["TMP"] = str(process_temp)
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=process_env,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result == {
        "input_iterations": 100,
        "mirror_write_blocks": 100,
        "artifact_iterations": 100,
        "before": 0,
        "after": 0,
    }

    moved = tmp_path / "router-after-100-failures"
    router.rename(moved)
    assert moved.is_dir()
    moved_bin = tmp_path / "build-bin-after-100-failures"
    build_bin.rename(moved_bin)
    assert moved_bin.is_dir()


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
        env=_git_safe_directory_env(router),
    )
    assert completed.returncode == 0, completed.stderr
    snapshot = json.loads(completed.stdout)

    assert snapshot["before"]["git"]["available"] is True
    assert snapshot["before"]["git"]["native_source_dirty"] is False
    assert snapshot["after"]["git"]["native_source_dirty"] is True
    assert snapshot["before"]["build_recipe"] == {
        "path": "tools/build_native_acad.ps1",
        "sha256": _canonical_text_sha256(recipe),
    }
    assert snapshot["exact_equal"] is False
    assert snapshot["before"]["source_tree"]["digest"] != snapshot["after"]["source_tree"]["digest"]
    assert all("/bin/" not in item["path"] for item in snapshot["before"]["source_tree"]["inputs"])


def test_build_snapshot_makes_lf_crlf_and_mixed_compiler_inputs_equivalent(
    tmp_path: Path,
) -> None:
    router = tmp_path / "router"
    native = router / "src" / "Ariadne.AcadNative"
    dbx = router / "src" / "Ariadne.AcadNativeDbx"
    recipe = router / "tools" / "build_native_acad.ps1"
    native.mkdir(parents=True)
    dbx.mkdir(parents=True)
    recipe.parent.mkdir(parents=True)
    native_file = native / "AriadneNativeJob.cpp"
    dbx_file = dbx / "AriadneDbxEntry.cpp"
    native_file.write_bytes(b"// native\n// second\n")
    dbx_file.write_bytes(b"// dbx\n// second\n")
    recipe.write_text("# fixture recipe\n", encoding="utf-8")

    script_path = REPO / "tools" / "build_native_acad.ps1"
    ps_literal = str(script_path).replace("'", "''")
    root_literal = str(router).replace("'", "''")
    native_literal = str(native_file).replace("'", "''")
    dbx_literal = str(dbx_file).replace("'", "''")
    command = f"""
$ErrorActionPreference = 'Stop'
$scriptText = Get-Content -Raw -LiteralPath '{ps_literal}'
$functionStart = $scriptText.IndexOf('function Resolve-MSBuild')
$functionEnd = $scriptText.IndexOf('# Capture every provenance input before MSBuild')
$RouterHome = '{root_literal}'
. ([scriptblock]::Create($scriptText.Substring($functionStart, $functionEnd - $functionStart)))
$lf = Get-NativeBuildSnapshot
[System.IO.File]::WriteAllBytes('{native_literal}', [System.Text.Encoding]::UTF8.GetBytes("// native`r`n// second`r`n"))
[System.IO.File]::WriteAllBytes('{dbx_literal}', [System.Text.Encoding]::UTF8.GetBytes("// dbx`r`n// second`r`n"))
$crlf = Get-NativeBuildSnapshot
[System.IO.File]::WriteAllBytes('{native_literal}', [System.Text.Encoding]::UTF8.GetBytes("// native`r`n// second`n"))
[System.IO.File]::WriteAllBytes('{dbx_literal}', [System.Text.Encoding]::UTF8.GetBytes("// dbx`n// second`r`n"))
$mixed = Get-NativeBuildSnapshot
[ordered]@{{
  source = @($lf.source_tree.digest, $crlf.source_tree.digest, $mixed.source_tree.digest)
  compilation = @($lf.compilation_tree.digest, $crlf.compilation_tree.digest, $mixed.compilation_tree.digest)
  representations = @($lf.compilation_tree.byte_representation, $crlf.compilation_tree.byte_representation, $mixed.compilation_tree.byte_representation)
  trees_equal = @(
    (($lf.source_tree.inputs | ConvertTo-Json -Compress) -ceq ($lf.compilation_tree.inputs | ConvertTo-Json -Compress)),
    (($crlf.source_tree.inputs | ConvertTo-Json -Compress) -ceq ($crlf.compilation_tree.inputs | ConvertTo-Json -Compress)),
    (($mixed.source_tree.inputs | ConvertTo-Json -Compress) -ceq ($mixed.compilation_tree.inputs | ConvertTo-Json -Compress))
  )
}} | ConvertTo-Json -Compress
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
    result = json.loads(completed.stdout)
    assert len(set(result["source"])) == 1
    assert len(set(result["compilation"])) == 1
    assert result["compilation"] == result["source"]
    assert result["representations"] == [
        "canonical_lf_unless_nul_mirror_bytes",
    ] * 3
    assert result["trees_equal"] == [True, True, True]


def test_build_recipe_identity_ignores_checkout_line_endings(tmp_path: Path):
    router = tmp_path / "router"
    native = router / "src" / "Ariadne.AcadNative"
    dbx = router / "src" / "Ariadne.AcadNativeDbx"
    recipe = router / "tools" / "build_native_acad.ps1"
    native.mkdir(parents=True)
    dbx.mkdir(parents=True)
    recipe.parent.mkdir(parents=True)
    (native / "AriadneNativeJob.cpp").write_bytes(b"// native\n")
    (dbx / "AriadneDbxEntry.cpp").write_bytes(b"// dbx\n")
    recipe.write_bytes(b"# fixture recipe\n")

    script_path = REPO / "tools" / "build_native_acad.ps1"
    ps_literal = str(script_path).replace("'", "''")
    root_literal = str(router).replace("'", "''")
    recipe_literal = str(recipe).replace("'", "''")
    command = f"""
$ErrorActionPreference = 'Stop'
$scriptText = Get-Content -Raw -LiteralPath '{ps_literal}'
$functionStart = $scriptText.IndexOf('function Resolve-MSBuild')
$functionEnd = $scriptText.IndexOf('# Capture every provenance input before MSBuild')
$RouterHome = '{root_literal}'
. ([scriptblock]::Create($scriptText.Substring($functionStart, $functionEnd - $functionStart)))
$before = Get-NativeBuildSnapshot
[System.IO.File]::WriteAllBytes('{recipe_literal}', [System.Text.Encoding]::UTF8.GetBytes("# fixture recipe`r`n"))
$after = Get-NativeBuildSnapshot
[ordered]@{{
  before = $before.build_recipe.sha256
  after = $after.build_recipe.sha256
}} | ConvertTo-Json -Compress
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
    result = json.loads(completed.stdout)
    assert result["before"] == result["after"]


def test_native_git_snapshot_uses_portable_positive_pathspecs() -> None:
    text = (REPO / "tools" / "build_native_acad.ps1").read_text(encoding="utf-8")
    start = text.index("function Get-NativeSourceGitState")
    end = text.index("function Get-BuildRecipeState", start)
    helper = text[start:end]

    assert ":(exclude)" not in helper
    assert "Test-NativeSourceStatusLine" in helper
    assert "safe.directory" not in helper
    assert "git config --global" not in helper


def test_native_git_snapshot_uses_one_git_when_path_has_multiple_applications(
    tmp_path: Path,
) -> None:
    router = tmp_path / "router"
    native = router / "src" / "Ariadne.AcadNative"
    dbx = router / "src" / "Ariadne.AcadNativeDbx"
    recipe = router / "tools" / "build_native_acad.ps1"
    native.mkdir(parents=True)
    dbx.mkdir(parents=True)
    recipe.parent.mkdir(parents=True)
    (native / "AriadneNativeJob.cpp").write_bytes(b"// native\n")
    (dbx / "AriadneDbxEntry.cpp").write_bytes(b"// dbx\n")
    recipe.write_bytes(b"# fixture recipe\n")
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

    extra_bin = tmp_path / "extra-bin"
    extra_bin.mkdir()
    (extra_bin / "git.cmd").write_text("@exit /b 99\n", encoding="ascii")
    env = _git_safe_directory_env(router)
    env["PATH"] = f'{env["PATH"]}{os.pathsep}{extra_bin}'

    script_path = REPO / "tools" / "build_native_acad.ps1"
    ps_literal = str(script_path).replace("'", "''")
    root_literal = str(router).replace("'", "''")
    command = f"""
$ErrorActionPreference = 'Stop'
$scriptText = Get-Content -Raw -LiteralPath '{ps_literal}'
$functionStart = $scriptText.IndexOf('function Resolve-MSBuild')
$functionEnd = $scriptText.IndexOf('# Capture every provenance input before MSBuild')
$RouterHome = '{root_literal}'
. ([scriptblock]::Create($scriptText.Substring($functionStart, $functionEnd - $functionStart)))
[ordered]@{{
  application_count = @(Get-Command git -CommandType Application).Count
  git = (Get-NativeBuildSnapshot).git
}} | ConvertTo-Json -Depth 4 -Compress
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["application_count"] >= 2
    assert result["git"]["available"] is True


def test_native_git_snapshot_supplies_only_the_requested_safe_directory(
    tmp_path: Path, monkeypatch
) -> None:
    router = tmp_path / "router"
    native = router / "src" / "Ariadne.AcadNative"
    dbx = router / "src" / "Ariadne.AcadNativeDbx"
    recipe = router / "tools" / "build_native_acad.ps1"
    native.mkdir(parents=True)
    dbx.mkdir(parents=True)
    recipe.parent.mkdir(parents=True)
    (native / "AriadneNativeJob.cpp").write_bytes(b"// native\n")
    (dbx / "AriadneDbxEntry.cpp").write_bytes(b"// dbx\n")
    recipe.write_bytes(b"# fixture recipe\n")
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
    head = _git(router, "rev-parse", "HEAD").strip()
    empty_global_config = tmp_path / "empty.gitconfig"
    empty_global_config.write_bytes(b"")
    ownership_env = {
        **_isolated_git_config_env(),
        "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1",
        "GIT_CONFIG_GLOBAL": str(empty_global_config),
        "GIT_CONFIG_NOSYSTEM": "1",
    }

    script_path = REPO / "tools" / "build_native_acad.ps1"
    ps_literal = str(script_path).replace("'", "''")
    root_literal = str(router).replace("'", "''")
    command = f"""
$ErrorActionPreference = 'Stop'
$scriptText = Get-Content -Raw -LiteralPath '{ps_literal}'
$functionStart = $scriptText.IndexOf('function Resolve-MSBuild')
$functionEnd = $scriptText.IndexOf('# Capture every provenance input before MSBuild')
$RouterHome = '{root_literal}'
. ([scriptblock]::Create($scriptText.Substring($functionStart, $functionEnd - $functionStart)))
(Get-NativeBuildSnapshot).git | ConvertTo-Json -Compress
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=ownership_env,
    )
    assert completed.returncode == 0, completed.stderr
    powershell_state = json.loads(completed.stdout)
    expected = {
        "available": True,
        "head": head,
        "native_source_dirty": False,
        "native_source_status_sha256": hashlib.sha256(b"").hexdigest(),
    }
    assert {key: powershell_state[key] for key in expected} == expected
    assert powershell_state["checks"] == {
        "git_available": True,
        "repo_root_exact": True,
        "index_visibility_unmodified": True,
        "start_end_consistent": True,
    }

    _replace_process_git_env(monkeypatch, ownership_env)
    python_state = cadctl._native_source_git_state(router)
    assert python_state == expected


def test_native_git_snapshot_accepts_exact_safe_directory_for_dubious_ownership(
    tmp_path: Path, monkeypatch
) -> None:
    router = tmp_path / "router"
    native = router / "src" / "Ariadne.AcadNative"
    dbx = router / "src" / "Ariadne.AcadNativeDbx"
    recipe = router / "tools" / "build_native_acad.ps1"
    native.mkdir(parents=True)
    dbx.mkdir(parents=True)
    recipe.parent.mkdir(parents=True)
    (native / "AriadneNativeJob.cpp").write_bytes(b"// native\n")
    (dbx / "AriadneDbxEntry.cpp").write_bytes(b"// dbx\n")
    recipe.write_bytes(b"# fixture recipe\n")
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
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    (sibling / "tracked.txt").write_text("sibling\n", encoding="utf-8")
    _git(sibling, "init", "-q")
    _git(sibling, "add", ".")
    _git(
        sibling,
        "-c",
        "user.name=Build Manifest Test",
        "-c",
        "user.email=build-manifest@example.invalid",
        "commit",
        "-qm",
        "sibling checkout",
    )
    head = _git(router, "rev-parse", "HEAD").strip()
    empty_global_config = tmp_path / "empty.gitconfig"
    empty_global_config.write_bytes(b"")
    ownership_env = _git_safe_directory_env(router)
    ownership_env.update(
        {
            "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1",
            "GIT_CONFIG_GLOBAL": str(empty_global_config),
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )

    script_path = REPO / "tools" / "build_native_acad.ps1"
    ps_literal = str(script_path).replace("'", "''")
    root_literal = str(router).replace("'", "''")
    command = f"""
$ErrorActionPreference = 'Stop'
$scriptText = Get-Content -Raw -LiteralPath '{ps_literal}'
$functionStart = $scriptText.IndexOf('function Resolve-MSBuild')
$functionEnd = $scriptText.IndexOf('# Capture every provenance input before MSBuild')
$RouterHome = '{root_literal}'
. ([scriptblock]::Create($scriptText.Substring($functionStart, $functionEnd - $functionStart)))
(Get-NativeBuildSnapshot).git | ConvertTo-Json -Compress
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=ownership_env,
    )
    assert completed.returncode == 0, completed.stderr
    expected = {
        "available": True,
        "head": head,
        "native_source_dirty": False,
        "native_source_status_sha256": hashlib.sha256(b"").hexdigest(),
    }
    powershell_state = json.loads(completed.stdout)
    assert {key: powershell_state[key] for key in expected} == expected
    assert powershell_state["checks"] == {
        "git_available": True,
        "repo_root_exact": True,
        "index_visibility_unmodified": True,
        "start_end_consistent": True,
    }

    sibling_probe = subprocess.run(
        ["git", "-C", str(sibling), "rev-parse", "HEAD"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=ownership_env,
    )
    assert sibling_probe.returncode != 0
    assert "dubious ownership" in sibling_probe.stderr

    _replace_process_git_env(monkeypatch, ownership_env)
    assert cadctl._native_source_git_state(router) == expected


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
