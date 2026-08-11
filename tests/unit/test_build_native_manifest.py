from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


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


def _minimal_pe(*, machine: int = 0x8664, optional_magic: int = 0x20B) -> bytes:
    """Independent, header-only PE fixture; it is never executed."""
    payload = bytearray(512)
    payload[0:2] = b"MZ"
    payload[0x3C:0x40] = (0x80).to_bytes(4, "little")
    payload[0x80:0x84] = b"PE\0\0"
    payload[0x84:0x86] = machine.to_bytes(2, "little")
    payload[0x86:0x88] = (1).to_bytes(2, "little")
    payload[0x94:0x96] = (0xF0).to_bytes(2, "little")
    payload[0x98:0x9A] = optional_magic.to_bytes(2, "little")
    return bytes(payload)


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
        text.index("function Get-NativeSourceInputs") : text.index(
            "function Get-NativeSourceDigest"
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
    valid.write_bytes(_minimal_pe())
    x86.write_bytes(_minimal_pe(machine=0x14C))
    pe32.write_bytes(_minimal_pe(optional_magic=0x10B))
    tiny.write_bytes(b"MZ")
    bad_mz.write_bytes(b"ZZ" + _minimal_pe()[2:])

    script_path = REPO / "tools" / "build_native_acad.ps1"
    literals = {
        name: str(path).replace("'", "''")
        for name, path in {
            "valid": valid,
            "x86": x86,
            "pe32": pe32,
            "tiny": tiny,
            "bad_mz": bad_mz,
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
    for key in ("x86", "pe32", "tiny", "bad_mz"):
        assert results[key]["verified"] is False, key


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
$records = @($leaves | ForEach-Object {{ New-NativeArtifactRecord -BinDir $bin -Leaf $_ -Current $true }})
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
  build_snapshot = [ordered]@{{ exact_match = $true }}
  artifacts = $records
}}
Write-AtomicJson -Object $manifest -Path $manifestPath
$verified = Confirm-NativeBuildManifest -ManifestPath $manifestPath -RequiredLeaves $leaves -ExpectedClaimScope 'release_build_integrity_bundle' -ExpectedBuildTarget 'Rebuild' -ExpectedConfiguration 'Release' -ExpectedPlatform 'x64' -ExpectedSourceTreeDigest $snapshot.source_tree.digest
$success = Publish-NativePrebuiltSet -BinDir $bin -DeployDir '{success_literal}' -Leaves $leaves -BuildManifestVerification $verified -SourceSnapshot $snapshot
$successMarkerPath = Join-Path '{success_literal}' 'native_deployment_manifest.json'
$successMarker = Get-Content -Raw -LiteralPath $successMarkerPath | ConvertFrom-Json
$successMarkerBytes = [System.IO.File]::ReadAllBytes($successMarkerPath)
$repeatSuccess = Publish-NativePrebuiltSet -BinDir $bin -DeployDir '{success_literal}' -Leaves $leaves -BuildManifestVerification $verified -SourceSnapshot $snapshot
$repeatMarkerBytes = [System.IO.File]::ReadAllBytes($successMarkerPath)

$failureError = ''
$lockedPath = Join-Path '{failure_literal}' 'Ariadne.AcadNative.arx'
$lock = [System.IO.File]::Open($lockedPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::None)
try {{
  try {{
    Publish-NativePrebuiltSet -BinDir $bin -DeployDir '{failure_literal}' -Leaves $leaves -BuildManifestVerification $verified -SourceSnapshot $snapshot | Out-Null
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
  Confirm-NativeDeploymentManifest -ManifestPath $successMarkerPath -RequiredLeaves $leaves -ExpectedSourceTreeDigest $snapshot.source_tree.digest -ExpectedBuildRecipeSha256 $snapshot.build_recipe.sha256 | Out-Null
}} catch {{
  $tamperError = $_.Exception.Message
}}

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
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)

    assert result["success"]["committed"] is True
    assert set(result["success"]["deployed_leaves"]) == set(leaves)
    assert result["success_marker"]["deployment_state"] == "committed"
    assert result["success_marker"]["claim_scope"] == "release_build_integrity_bundle"
    assert result["success_marker"]["source_tree_digest"]
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

    post_snapshot = main.index("$nativeBuildSnapshotBeforeManifest = Get-NativeBuildSnapshot")
    manifest_write = main.index("Write-AtomicJson -Object $manifest -Path $manifestPath")
    manifest_verify = main.index("$manifestVerification = Confirm-NativeBuildManifest")
    prebuilt_publish = main.index("$prebuiltDeployment = Publish-NativePrebuiltSet")
    assert post_snapshot < manifest_write < manifest_verify < prebuilt_publish
    assert "@('Ariadne.AcadNativeDbx.dbx', 'Ariadne.AcadNative.crx', 'Ariadne.AcadNative.arx')" in main
    assert "Copy-Item -LiteralPath $src -Destination" not in main


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
        env={**os.environ, "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"},
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


def test_build_snapshot_source_identity_ignores_checkout_line_endings(tmp_path: Path):
    router = tmp_path / "router"
    native = router / "src" / "Ariadne.AcadNative"
    dbx = router / "src" / "Ariadne.AcadNativeDbx"
    recipe = router / "tools" / "build_native_acad.ps1"
    native.mkdir(parents=True)
    dbx.mkdir(parents=True)
    recipe.parent.mkdir(parents=True)
    native_file = native / "AriadneNativeJob.cpp"
    dbx_file = dbx / "AriadneDbxEntry.cpp"
    native_file.write_bytes(b"// native\n")
    dbx_file.write_bytes(b"// dbx\n")
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
$before = Get-NativeBuildSnapshot
[System.IO.File]::WriteAllBytes('{native_literal}', [System.Text.Encoding]::UTF8.GetBytes("// native`r`n"))
[System.IO.File]::WriteAllBytes('{dbx_literal}', [System.Text.Encoding]::UTF8.GetBytes("// dbx`r`n"))
$after = Get-NativeBuildSnapshot
[ordered]@{{
  before = $before.source_tree.digest
  after = $after.source_tree.digest
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
    assert "safe.directory=" in helper


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
