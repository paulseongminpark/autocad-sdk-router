from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest


REPO = Path(__file__).resolve().parents[2]
CONSUMERS = (
    REPO / "tools" / "autocad-router.ps1",
    REPO / "tools" / "attended" / "run_attended_job.ps1",
)
LEAVES = (
    "Ariadne.AcadNativeDbx.dbx",
    "Ariadne.AcadNative.crx",
    "Ariadne.AcadNative.arx",
)


def _canonical_text_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def _minimal_pe(seed: int) -> bytes:
    payload = bytearray(512)
    payload[0:2] = b"MZ"
    payload[0x3C:0x40] = (0x80).to_bytes(4, "little")
    payload[0x80:0x84] = b"PE\0\0"
    payload[0x84:0x86] = (0x8664).to_bytes(2, "little")
    payload[0x86:0x88] = (1).to_bytes(2, "little")
    payload[0x94:0x96] = (0xF0).to_bytes(2, "little")
    payload[0x98:0x9A] = (0x20B).to_bytes(2, "little")
    payload[-1] = seed
    return bytes(payload)


def _source_inputs(router: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    excluded = {"bin", "obj", ".vs", "build"}
    for root_name in ("Ariadne.AcadNative", "Ariadne.AcadNativeDbx"):
        root = router / "src" / root_name
        for path in root.rglob("*"):
            relative_parts = path.relative_to(root).parts
            if any(
                part.lower() in excluded
                or part.lower().startswith("obj-")
                or part.lower().startswith("obj_")
                for part in relative_parts[:-1]
            ):
                continue
            if path.is_file():
                data = _canonical_text_bytes(path.read_bytes())
                records.append(
                    {
                        "path": path.relative_to(router).as_posix(),
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "bytes": len(data),
                    }
                )
    return sorted(records, key=lambda item: (str(item["path"]).lower(), item["path"]))


def _source_digest(records: list[dict[str, object]]) -> str:
    payload = "".join(
        f'{item["path"]}\0{item["sha256"]}\0{item["bytes"]}\n'
        for item in records
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _native_fixture(tmp_path: Path, *, manifest_leaf: str) -> tuple[Path, Path]:
    router = tmp_path / "router"
    deploy = router / "native-bin"
    (router / "src" / "Ariadne.AcadNative").mkdir(parents=True)
    (router / "src" / "Ariadne.AcadNativeDbx").mkdir(parents=True)
    (router / "tools").mkdir(parents=True)
    deploy.mkdir(parents=True)
    (router / "src" / "Ariadne.AcadNative" / "native.cpp").write_bytes(
        b"// native\n"
    )
    (router / "src" / "Ariadne.AcadNativeDbx" / "dbx.cpp").write_bytes(
        b"// dbx\n"
    )
    recipe = router / "tools" / "build_native_acad.ps1"
    recipe.write_bytes(b"# recipe\n")

    artifacts = []
    for seed, leaf in enumerate(LEAVES, start=1):
        path = deploy / leaf
        path.write_bytes(_minimal_pe(seed))
        artifacts.append(
            {
                "leaf": leaf,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
                "current": True,
                "exists": True,
                "pe_verification": {
                    "verified": True,
                    "machine": "0x8664",
                    "format": "PE32+",
                },
            }
        )

    digest = _source_digest(_source_inputs(router))
    common = {
        "schema_version": 1,
        "claim_scope": "release_build_integrity_bundle",
        "configuration": "Release",
        "platform": "x64",
        "build_target": "Rebuild",
        "build_recipe": {
            "path": "tools/build_native_acad.ps1",
            "sha256": hashlib.sha256(
                _canonical_text_bytes(recipe.read_bytes())
            ).hexdigest(),
        },
        "artifacts": artifacts,
    }
    if manifest_leaf == "native_deployment_manifest.json":
        manifest = {
            **common,
            "schema": "ariadne.cad_os.native_deployment_manifest.v1",
            "deployment_state": "committed",
            "committed": True,
            "source_tree_digest": digest,
        }
    else:
        manifest = {
            **common,
            "schema": "ariadne.cad_os.native_build_manifest.v1",
            "load_bin_dir": str(deploy.resolve()),
            "source_tree": {"algorithm": "sha256", "digest": digest},
            "build_snapshot": {"exact_match": True},
        }
    (deploy / manifest_leaf).write_text(json.dumps(manifest), encoding="utf-8")
    return router, deploy


def _run_consumer(
    consumer: Path,
    router: Path,
    deploy: Path,
    manifest_leaf: str,
    body: str,
) -> subprocess.CompletedProcess[str]:
    values = {
        "consumer": str(consumer).replace("'", "''"),
        "router": str(router).replace("'", "''"),
        "deploy": str(deploy).replace("'", "''"),
        "manifest": manifest_leaf.replace("'", "''"),
    }
    command = f"""
$ErrorActionPreference = 'Stop'
$RouterHome = '{values["router"]}'
$text = Get-Content -Raw -LiteralPath '{values["consumer"]}'
$start = $text.IndexOf('# NATIVE_DEPLOYMENT_CONSUMER_BEGIN')
$end = $text.IndexOf('# NATIVE_DEPLOYMENT_CONSUMER_END')
if ($start -lt 0 -or $end -le $start) {{ throw 'consumer helper boundaries not found' }}
. ([scriptblock]::Create($text.Substring($start, $end - $start)))
$bin = '{values["deploy"]}'
$manifestLeaf = '{values["manifest"]}'
{body}
"""
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )


@pytest.mark.parametrize("consumer", CONSUMERS, ids=lambda path: path.name)
def test_consumer_rejects_stale_source_digest(tmp_path: Path, consumer: Path):
    router, deploy = _native_fixture(
        tmp_path, manifest_leaf="native_deployment_manifest.json"
    )
    (router / "src" / "Ariadne.AcadNative" / "native.cpp").write_text(
        "// changed after publication\n", encoding="utf-8"
    )

    completed = _run_consumer(
        consumer,
        router,
        deploy,
        "native_deployment_manifest.json",
        "Open-NativeDeploymentLease -BinDir $bin -ManifestLeaf $manifestLeaf | Out-Null",
    )

    assert completed.returncode != 0
    assert "source-tree digest" in completed.stderr.lower()


@pytest.mark.parametrize("consumer", CONSUMERS, ids=lambda path: path.name)
def test_consumer_accepts_equivalent_crlf_checkout(
    tmp_path: Path, consumer: Path
):
    router, deploy = _native_fixture(
        tmp_path, manifest_leaf="native_deployment_manifest.json"
    )
    for path in (
        router / "src" / "Ariadne.AcadNative" / "native.cpp",
        router / "src" / "Ariadne.AcadNativeDbx" / "dbx.cpp",
        router / "tools" / "build_native_acad.ps1",
    ):
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))

    completed = _run_consumer(
        consumer,
        router,
        deploy,
        "native_deployment_manifest.json",
        "$lease = Open-NativeDeploymentLease -BinDir $bin -ManifestLeaf $manifestLeaf; "
        "try { $lease.manifest_kind } finally { Close-NativeDeploymentLease $lease }",
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "deployment"


@pytest.mark.parametrize("consumer", CONSUMERS, ids=lambda path: path.name)
def test_consumer_rejects_a_bin_without_a_manifest(tmp_path: Path, consumer: Path):
    router, deploy = _native_fixture(
        tmp_path, manifest_leaf="native_deployment_manifest.json"
    )
    (deploy / "native_deployment_manifest.json").unlink()

    completed = _run_consumer(
        consumer,
        router,
        deploy,
        "native_deployment_manifest.json",
        "Open-NativeDeploymentLease -BinDir $bin -ManifestLeaf $manifestLeaf | Out-Null",
    )

    assert completed.returncode != 0
    assert "manifest" in completed.stderr.lower()


@pytest.mark.parametrize("consumer", CONSUMERS, ids=lambda path: path.name)
def test_explicit_build_bin_is_verified_instead_of_bypassing_validation(
    tmp_path: Path, consumer: Path
):
    router, deploy = _native_fixture(tmp_path, manifest_leaf="native_build_manifest.json")
    accepted = _run_consumer(
        consumer,
        router,
        deploy,
        "native_build_manifest.json",
        "$lease = Open-NativeDeploymentLease -BinDir $bin -ManifestLeaf $manifestLeaf; "
        "try { $lease.manifest_kind } finally { Close-NativeDeploymentLease $lease }",
    )
    assert accepted.returncode == 0, accepted.stderr
    assert accepted.stdout.strip() == "build"

    manifest_path = deploy / "native_build_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_tree"]["digest"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    rejected = _run_consumer(
        consumer,
        router,
        deploy,
        "native_build_manifest.json",
        "Open-NativeDeploymentLease -BinDir $bin -ManifestLeaf $manifestLeaf | Out-Null",
    )
    assert rejected.returncode != 0
    assert "source-tree digest" in rejected.stderr.lower()


@pytest.mark.parametrize("consumer", CONSUMERS, ids=lambda path: path.name)
def test_consumer_lease_pins_one_generation_until_close(tmp_path: Path, consumer: Path):
    router, deploy = _native_fixture(
        tmp_path, manifest_leaf="native_deployment_manifest.json"
    )
    body = r"""
$lease = Open-NativeDeploymentLease -BinDir $bin -ManifestLeaf $manifestLeaf
$marker = Join-Path $bin $manifestLeaf
$artifact = Join-Path $bin 'Ariadne.AcadNative.arx'
$markerBlocked = $false
$artifactBlocked = $false
try { [System.IO.File]::Move($marker, "$marker.swap") } catch [System.IO.IOException] { $markerBlocked = $true }
try { [System.IO.File]::Move($artifact, "$artifact.swap") } catch [System.IO.IOException] { $artifactBlocked = $true }
Close-NativeDeploymentLease $lease
[System.IO.File]::Move($marker, "$marker.swap")
[System.IO.File]::Move("$marker.swap", $marker)
[System.IO.File]::Move($artifact, "$artifact.swap")
[System.IO.File]::Move("$artifact.swap", $artifact)
[ordered]@{ marker_blocked = $markerBlocked; artifact_blocked = $artifactBlocked } | ConvertTo-Json -Compress
"""
    completed = _run_consumer(
        consumer, router, deploy, "native_deployment_manifest.json", body
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "marker_blocked": True,
        "artifact_blocked": True,
    }


@pytest.mark.parametrize("consumer", CONSUMERS, ids=lambda path: path.name)
def test_consumer_releases_every_handle_across_100_leases(tmp_path: Path, consumer: Path):
    router, deploy = _native_fixture(
        tmp_path, manifest_leaf="native_deployment_manifest.json"
    )
    body = r"""
1..100 | ForEach-Object {
  $lease = Open-NativeDeploymentLease -BinDir $bin -ManifestLeaf $manifestLeaf
  Close-NativeDeploymentLease $lease
}
$paths = @((Join-Path $bin $manifestLeaf)) + @(
  'Ariadne.AcadNativeDbx.dbx', 'Ariadne.AcadNative.crx', 'Ariadne.AcadNative.arx' |
    ForEach-Object { Join-Path $bin $_ }
)
foreach ($path in $paths) {
  [System.IO.File]::Move($path, "$path.swap")
  [System.IO.File]::Move("$path.swap", $path)
}
'PASS'
"""
    completed = _run_consumer(
        consumer, router, deploy, "native_deployment_manifest.json", body
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "PASS"


def test_router_has_no_unverified_native_fallback_or_environment_bypass():
    text = (REPO / "tools" / "autocad-router.ps1").read_text(encoding="utf-8")

    assert "else { Join-Path $RouterHome 'src\\Ariadne.AcadNative\\bin\\x64\\Release' }" not in text
    assert "Open-NativeDeploymentLease -BinDir $env:ARIADNE_NATIVE_ACAD_BIN_DIR" in text
    assert "-ManifestLeaf 'native_build_manifest.json'" in text
