"""Public-interface tests for checkout-bound native integrity receipts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from verification.native_integrity import (  # noqa: E402
    verify_build_manifest,
    verify_committed_deployment,
)
from verification import native_integrity  # noqa: E402
from verification import file_snapshot  # noqa: E402
from verification.file_snapshot import (  # noqa: E402
    SnapshotCaptureError,
    capture_files,
)


def _copy_committed_fixture(tmp_path: Path) -> tuple[Path, Path]:
    router = tmp_path / "router"
    for relative in (
        Path("src") / "Ariadne.AcadNative",
        Path("src") / "Ariadne.AcadNativeDbx",
    ):
        shutil.copytree(
            ROOT / relative,
            router / relative,
            ignore=shutil.ignore_patterns("bin", "obj"),
        )
    recipe = Path("tools") / "build_native_acad.ps1"
    (router / recipe).parent.mkdir(parents=True)
    shutil.copy2(ROOT / recipe, router / recipe)
    deploy_dir = router / "prebuilt" / "2027"
    shutil.copytree(ROOT / "prebuilt" / "2027", deploy_dir)
    _git(router, "init", "--quiet")
    _git(router, "config", "user.name", "Native Integrity Test")
    _git(router, "config", "user.email", "native-integrity@example.invalid")
    _git(router, "config", "core.autocrlf", "true")
    _git(router, "add", "src", "tools/build_native_acad.ps1")
    _git(router, "commit", "--quiet", "-m", "native source anchor")
    _bind_deployment_manifest_to_fixture(router, deploy_dir)
    return router, deploy_dir


def test_file_snapshot_binds_bytes_to_the_exact_lexical_path(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    source = root / "source.bin"
    source.write_bytes(b"one immutable generation")

    snapshot = capture_files(root, ("source.bin",))

    captured = snapshot.files["source.bin"]
    assert captured.content == b"one immutable generation"
    assert captured.byte_count == len(captured.content)
    assert captured.sha256 == hashlib.sha256(captured.content).hexdigest()
    assert snapshot.aggregate_sha256 == hashlib.sha256(
        (
            "source.bin\0"
            + captured.sha256
            + "\0"
            + str(captured.byte_count)
            + "\n"
        ).encode("utf-8")
    ).hexdigest()


def test_file_snapshot_rejects_an_alias_parent_even_when_bytes_match(
    tmp_path: Path,
) -> None:
    real_root = tmp_path / "real-root"
    real_root.mkdir()
    (real_root / "source.bin").write_bytes(b"same bytes")
    alias_root = tmp_path / "alias-root"
    if os.name == "nt":
        linked = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias_root), str(real_root)],
            check=False,
            capture_output=True,
            text=True,
        )
        if linked.returncode != 0:
            pytest.skip("directory junctions are unavailable: " + linked.stderr)
    else:
        os.symlink(real_root, alias_root, target_is_directory=True)

    with pytest.raises(SnapshotCaptureError, match="lexical|alias|reparse|symlink"):
        capture_files(alias_root, ("source.bin",))


def test_file_snapshot_rejects_distinct_names_for_one_hardlinked_identity(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    first = root / "first.bin"
    second = root / "second.bin"
    first.write_bytes(b"one physical generation")
    try:
        os.link(first, second)
    except OSError as exc:
        pytest.skip(f"hard links are unavailable: {exc}")

    with pytest.raises(SnapshotCaptureError, match="identity|alias|hardlink"):
        capture_files(root, ("first.bin", "second.bin"))


@pytest.mark.skipif(os.name != "nt", reason="Windows share-mode contract")
def test_file_snapshot_denies_write_while_all_capture_handles_are_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    first = root / "first.bin"
    second = root / "second.bin"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    original_read = file_snapshot._windows_read
    blocked_write_errors: list[OSError] = []

    def read_while_probing_share_mode(handle, path: str) -> bytes:
        if os.path.normcase(path) == os.path.normcase(str(first)):
            try:
                second.write_bytes(b"must be blocked")
            except OSError as exc:
                blocked_write_errors.append(exc)
        return original_read(handle, path)

    monkeypatch.setattr(
        file_snapshot,
        "_windows_read",
        read_while_probing_share_mode,
    )

    snapshot = capture_files(root, ("first.bin", "second.bin"))

    assert len(blocked_write_errors) == 1
    assert snapshot.files["second.bin"].content == b"second"


def _deployment_manifest(deploy_dir: Path) -> tuple[Path, dict]:
    path = deploy_dir / "native_deployment_manifest.json"
    return path, json.loads(path.read_text(encoding="utf-8-sig"))


def _bind_deployment_manifest_to_fixture(router: Path, deploy_dir: Path) -> None:
    manifest_path, manifest = _deployment_manifest(deploy_dir)
    source_inputs = native_integrity._native_source_inputs(router)
    source_digest = native_integrity._source_tree_digest(source_inputs)
    manifest["source_tree"] = {
        "algorithm": "sha256",
        "canonicalization": "crlf_to_lf_unless_nul",
        "digest": source_digest,
        "inputs": source_inputs,
    }
    manifest["source_tree_digest"] = source_digest
    compilation_inputs = native_integrity._native_compilation_inputs(router)
    compilation_digest = native_integrity._source_tree_digest(compilation_inputs)
    manifest["compilation_tree"] = {
        "algorithm": "sha256",
        "byte_representation": "canonical_lf_unless_nul_mirror_bytes",
        "digest": compilation_digest,
        "inputs": compilation_inputs,
    }
    manifest["compilation_tree_digest"] = compilation_digest
    manifest["source_provenance"] = {
        "compilation_input": "immutable_starting_snapshot_mirror",
        "mirror_ephemeral": True,
        "limitations": [
            {"code": "EXTERNAL_TOOLCHAIN_INPUTS_UNSEALED"}
        ],
    }
    recipe = native_integrity._build_recipe_state(router)
    manifest["build_recipe"] = {
        "path": recipe["path"],
        "sha256": recipe["sha256"],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _copy_build_fixture(tmp_path: Path) -> tuple[Path, Path, dict]:
    router, deploy_dir = _copy_committed_fixture(tmp_path)

    native_bin = router / "src" / "Ariadne.AcadNative" / "bin" / "x64" / "Release"
    native_bin.mkdir(parents=True)
    deployment = json.loads(
        (deploy_dir / "native_deployment_manifest.json").read_text(
            encoding="utf-8-sig"
        )
    )
    for artifact in deployment["artifacts"]:
        shutil.copy2(deploy_dir / artifact["leaf"], native_bin / artifact["leaf"])

    source_inputs = native_integrity._native_source_inputs(router)
    compilation_inputs = native_integrity._native_compilation_inputs(router)
    checkout_git = native_integrity._native_source_git_state(router)
    assert checkout_git["available"] is True
    manifest = {
        "schema": "ariadne.cad_os.native_build_manifest.v1",
        "schema_version": 1,
        "claim_scope": "release_build_integrity_bundle",
        "build_target": "Rebuild",
        "configuration": "Release",
        "platform": "x64",
        "load_bin_dir": str(native_bin),
        "checkout": {"root": str(router), "git": checkout_git},
        "build_recipe": deployment["build_recipe"],
        "source_tree": {
            "algorithm": "sha256",
            "canonicalization": "crlf_to_lf_unless_nul",
            "inputs": source_inputs,
            "digest": native_integrity._source_tree_digest(source_inputs),
        },
        "compilation_tree": {
            "algorithm": "sha256",
            "byte_representation": "canonical_lf_unless_nul_mirror_bytes",
            "inputs": compilation_inputs,
            "digest": native_integrity._source_tree_digest(compilation_inputs),
        },
        "source_provenance": {
            "compilation_input": "immutable_starting_snapshot_mirror",
            "mirror_ephemeral": True,
            "limitations": [
                {"code": "EXTERNAL_TOOLCHAIN_INPUTS_UNSEALED"}
            ],
        },
        "build_snapshot": {
            "input_mode": "immutable_starting_snapshot_mirror",
            "exact_match": True,
        },
        "artifacts": deployment["artifacts"],
        "display_membership": {
            "ready": True,
            "canonical_arx_current": True,
        },
    }
    (native_bin / "native_build_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return router, native_bin, manifest


def test_native_git_legacy_projection_delegates_to_the_stable_observer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: list[Path] = []

    def stable_observer(repo_root: Path) -> dict:
        observed.append(Path(repo_root))
        return {
            "status": "PASS",
            "available": True,
            "head": "a" * 40,
            "native_source_dirty": False,
            "native_source_status_sha256": "b" * 64,
        }

    monkeypatch.setattr(
        native_integrity._git_state,
        "observe_native_source_checkout",
        stable_observer,
    )

    projection = native_integrity._native_source_git_state(tmp_path)

    assert observed == [tmp_path]
    assert projection == {
        "available": True,
        "head": "a" * 40,
        "native_source_dirty": False,
        "native_source_status_sha256": "b" * 64,
    }


def test_build_manifest_rejects_checkout_drift_during_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    router, native_bin, manifest = _copy_build_fixture(tmp_path)
    start = manifest["checkout"]["git"]
    observations = [
        {
            "status": "PASS",
            "available": True,
            "head": start["head"],
            "native_source_dirty": start["native_source_dirty"],
            "native_source_status_sha256": start["native_source_status_sha256"],
        },
        {
            "status": "PASS",
            "available": True,
            "head": "f" * 40,
            "native_source_dirty": False,
            "native_source_status_sha256": hashlib.sha256(b"").hexdigest(),
        },
    ]

    monkeypatch.setattr(
        native_integrity._git_state,
        "observe_native_source_checkout",
        lambda repo_root: observations.pop(0),
    )

    receipt = verify_build_manifest(router, native_bin)

    assert receipt["valid"] is False
    assert "checkout changed during native build verification" in receipt["errors"]
    assert observations == []


def test_build_manifest_public_seam_accepts_a_bound_build(tmp_path: Path) -> None:
    router, native_bin, _ = _copy_build_fixture(tmp_path)

    receipt = verify_build_manifest(router, native_bin)

    assert receipt["valid"] is True, receipt["errors"]
    assert receipt["checks"]["git_stable"] is True
    assert receipt["checks"]["source_inputs_at_head"] is True
    assert receipt["checks"]["compilation_inputs_bound_to_head_paths"] is True
    assert receipt["errors"] == []
    assert {Path(path).name for path in receipt["artifact_paths"]} == {
        "Ariadne.AcadNativeDbx.dbx",
        "Ariadne.AcadNative.crx",
        "Ariadne.AcadNative.arx",
    }


def test_build_manifest_public_seam_rejects_artifact_tampering(
    tmp_path: Path,
) -> None:
    router, native_bin, _ = _copy_build_fixture(tmp_path)
    artifact = native_bin / "Ariadne.AcadNative.arx"
    artifact.write_bytes(artifact.read_bytes() + b"tampered")

    receipt = verify_build_manifest(router, native_bin)

    assert receipt["valid"] is False
    assert receipt["checks"][f"artifact:{artifact.name}"] is False
    assert f"manifest artifact binding: {artifact.name}" in receipt["errors"]


def test_committed_deployment_verifies_the_checkout_bundle() -> None:
    receipt = verify_committed_deployment(ROOT, ROOT / "prebuilt" / "2027")

    assert receipt["valid"] is True
    assert receipt["errors"] == []
    assert {Path(path).name for path in receipt["artifact_paths"]} == {
        "Ariadne.AcadNativeDbx.dbx",
        "Ariadne.AcadNative.crx",
        "Ariadne.AcadNative.arx",
    }


@pytest.mark.parametrize("entrypoint", ("committed", "build"))
def test_native_verifiers_use_only_the_safe_starting_byte_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entrypoint: str,
) -> None:
    if entrypoint == "committed":
        router, artifact_dir = _copy_committed_fixture(tmp_path)
        _bind_deployment_manifest_to_fixture(router, artifact_dir)
        verify = verify_committed_deployment
    else:
        router, artifact_dir, _ = _copy_build_fixture(tmp_path)
        verify = verify_build_manifest

    def forbidden_path_read(_path: Path) -> bytes:
        raise AssertionError("verification must not path-check then read by pathname")

    monkeypatch.setattr(Path, "read_bytes", forbidden_path_read)

    receipt = verify(router, artifact_dir)

    assert receipt["valid"] is True, receipt["errors"]
    assert receipt["checks"]["input_snapshot_stable"] is True


@pytest.mark.parametrize("entrypoint", ("committed", "build"))
def test_native_verifiers_reject_a_manifest_that_omits_a_git_source_path(
    tmp_path: Path,
    entrypoint: str,
) -> None:
    if entrypoint == "committed":
        router, artifact_dir = _copy_committed_fixture(tmp_path)
        manifest_path, manifest = _deployment_manifest(artifact_dir)
        verify = verify_committed_deployment
    else:
        router, artifact_dir, manifest = _copy_build_fixture(tmp_path)
        manifest_path = artifact_dir / "native_build_manifest.json"
        verify = verify_build_manifest
    omitted = manifest["source_tree"]["inputs"].pop()
    reduced_digest = native_integrity._source_tree_digest(
        manifest["source_tree"]["inputs"]
    )
    manifest["source_tree"]["digest"] = reduced_digest
    if entrypoint == "committed":
        manifest["source_tree_digest"] = reduced_digest
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    receipt = verify(router, artifact_dir)

    assert omitted["path"].startswith("src/Ariadne.AcadNative")
    assert receipt["valid"] is False
    assert receipt["checks"]["source_inventory_authority"] is False
    assert "Git native source inventory" in receipt["errors"][0]


def test_build_manifest_cannot_omit_an_ignored_untracked_native_source(
    tmp_path: Path,
) -> None:
    router, native_bin, _ = _copy_build_fixture(tmp_path)
    hidden_relative = "src/Ariadne.AcadNative/hidden-consumed.hpp"
    exclude = router / ".git" / "info" / "exclude"
    with exclude.open("a", encoding="utf-8") as stream:
        stream.write("\n" + hidden_relative + "\n")
    hidden = router / hidden_relative
    hidden.write_text("// compiler-consumed but ignored\n", encoding="utf-8")
    assert _git(router, "status", "--porcelain", "--", hidden_relative) == ""

    receipt = verify_build_manifest(router, native_bin)

    assert receipt["valid"] is False
    assert receipt["checks"]["source_inventory_authority"] is False
    assert "Git native source inventory" in receipt["errors"][0]


def test_committed_deployment_rejects_an_ignored_native_file_not_in_head(
    tmp_path: Path,
) -> None:
    router, deploy_dir = _copy_committed_fixture(tmp_path)
    hidden_relative = "src/Ariadne.AcadNative/ignored.cpp"
    exclude = router / ".git" / "info" / "exclude"
    with exclude.open("a", encoding="utf-8") as stream:
        stream.write("\n" + hidden_relative + "\n")
    (router / hidden_relative).write_text(
        "// compiler-visible but absent from HEAD\n",
        encoding="utf-8",
    )
    assert _git(router, "status", "--porcelain", "--", hidden_relative) == ""
    _bind_deployment_manifest_to_fixture(router, deploy_dir)

    receipt = verify_committed_deployment(router, deploy_dir)

    assert receipt["valid"] is False
    assert receipt["checks"]["source_inventory_authority"] is False
    assert "Git native source inventory" in receipt["errors"][0]


def test_missing_build_manifest_returns_an_invalid_receipt(tmp_path: Path) -> None:
    receipt = verify_build_manifest(tmp_path, tmp_path / "missing-bin")

    assert receipt["valid"] is False
    assert receipt["artifact_paths"] == []
    assert receipt["errors"]


def test_committed_deployment_rejects_the_wrong_schema(tmp_path: Path) -> None:
    router, deploy_dir = _copy_committed_fixture(tmp_path)
    manifest_path, manifest = _deployment_manifest(deploy_dir)
    manifest["schema_version"] = 2
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    receipt = verify_committed_deployment(router, deploy_dir)

    assert receipt["valid"] is False
    assert receipt["checks"]["schema"] is False


def test_committed_deployment_blocks_legacy_marker_without_exact_source_inputs(
    tmp_path: Path,
) -> None:
    router, deploy_dir = _copy_committed_fixture(tmp_path)
    manifest_path, manifest = _deployment_manifest(deploy_dir)
    del manifest["source_tree"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    receipt = verify_committed_deployment(router, deploy_dir)

    assert receipt["valid"] is False
    assert receipt["checks"]["source_inventory_authority"] is False
    assert receipt["checks"]["input_snapshot_stable"] is False
    assert "no exact source_tree.inputs inventory" in receipt["errors"][0]


def test_committed_deployment_rejects_an_extra_artifact_record(tmp_path: Path) -> None:
    router, deploy_dir = _copy_committed_fixture(tmp_path)
    manifest_path, manifest = _deployment_manifest(deploy_dir)
    extra = dict(manifest["artifacts"][0])
    extra["leaf"] = "Unexpected.Native.dll"
    manifest["artifacts"].append(extra)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    receipt = verify_committed_deployment(router, deploy_dir)

    assert receipt["valid"] is False
    assert "manifest artifact leaf set" in receipt["errors"]


def test_committed_deployment_rejects_changed_source_and_recipe(tmp_path: Path) -> None:
    router, deploy_dir = _copy_committed_fixture(tmp_path)
    source = router / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source.write_bytes(source.read_bytes() + b"\n// changed after deployment\n")
    recipe = router / "tools" / "build_native_acad.ps1"
    recipe.write_bytes(recipe.read_bytes() + b"\n# changed after deployment\n")

    receipt = verify_committed_deployment(router, deploy_dir)

    assert receipt["valid"] is False
    assert receipt["checks"]["source_tree"] is False
    assert receipt["checks"]["build_recipe"] is False


def test_committed_deployment_rejects_a_rebound_recipe_absent_from_head(
    tmp_path: Path,
) -> None:
    router, deploy_dir = _copy_committed_fixture(tmp_path)
    recipe = router / "tools" / "build_native_acad.ps1"
    recipe.write_bytes(recipe.read_bytes() + b"\n# not present in HEAD\n")
    _bind_deployment_manifest_to_fixture(router, deploy_dir)
    assert _git(
        router,
        "status",
        "--porcelain",
        "--",
        "src/Ariadne.AcadNative",
        "src/Ariadne.AcadNativeDbx",
    ) == ""

    receipt = verify_committed_deployment(router, deploy_dir)

    assert receipt["checks"]["source_inventory_authority"] is True
    assert receipt["checks"]["source_inputs_at_head"] is False
    assert receipt["checks"]["build_recipe"] is True
    assert receipt["valid"] is False
    assert any("exact HEAD blobs" in error for error in receipt["errors"])


def test_committed_deployment_rejects_rehashed_noncanonical_compilation_bytes(
    tmp_path: Path,
) -> None:
    router, deploy_dir = _copy_committed_fixture(tmp_path)
    manifest_path, manifest = _deployment_manifest(deploy_dir)
    source_path = (
        router / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    )
    source_raw = source_path.read_bytes()
    canonical = source_raw.replace(b"\r\n", b"\n")
    noncanonical = source_raw
    if noncanonical == canonical:
        noncanonical = canonical.replace(b"\n", b"\r\n")
    assert noncanonical != canonical

    relative_path = "src/Ariadne.AcadNative/AriadneNativeJob.cpp"
    compilation_inputs = manifest["compilation_tree"]["inputs"]
    record = next(
        item for item in compilation_inputs if item["path"] == relative_path
    )
    record["sha256"] = hashlib.sha256(noncanonical).hexdigest()
    record["bytes"] = len(noncanonical)
    compilation_digest = native_integrity._source_tree_digest(compilation_inputs)
    manifest["compilation_tree"]["digest"] = compilation_digest
    manifest["compilation_tree_digest"] = compilation_digest
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    receipt = verify_committed_deployment(router, deploy_dir)

    assert receipt["checks"]["source_inputs_at_head"] is True
    assert receipt["checks"]["source_tree"] is True
    assert receipt["checks"]["compilation_tree"] is False
    assert receipt["valid"] is False
    assert receipt["verification_scope"] == (
        "committed_artifact_identity_and_canonical_compilation_input_binding"
    )
    assert receipt["limitation_codes"] == [
        "external_toolchain_inputs_unsealed",
        "binary_rebuild_equivalence_not_proven",
    ]


def test_committed_deployment_verifies_lf_crlf_and_mixed_worktrees(
    tmp_path: Path,
) -> None:
    variants = {
        "lf": b"// portable first\n// portable second\n",
        "crlf": b"// portable first\r\n// portable second\r\n",
        "mixed": b"// portable first\r\n// portable second\n",
    }
    compilation_digests: list[str] = []

    for name, content in variants.items():
        router, deploy_dir = _copy_committed_fixture(tmp_path / name)
        source = router / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
        source.write_bytes(content)
        _git(router, "add", "src/Ariadne.AcadNative/AriadneNativeJob.cpp")
        _git(router, "commit", "--quiet", "-m", f"{name} worktree fixture")
        _bind_deployment_manifest_to_fixture(router, deploy_dir)

        receipt = verify_committed_deployment(router, deploy_dir)
        _, manifest = _deployment_manifest(deploy_dir)

        assert source.read_bytes() == content
        assert receipt["valid"] is True, receipt["errors"]
        assert receipt["checks"]["source_inputs_at_head"] is True
        assert receipt["checks"]["canonical_compilation_inputs_at_head"] is True
        assert manifest["compilation_tree"]["byte_representation"] == (
            "canonical_lf_unless_nul_mirror_bytes"
        )
        assert manifest["compilation_tree"]["inputs"] == (
            manifest["source_tree"]["inputs"]
        )
        compilation_digests.append(manifest["compilation_tree"]["digest"])

    assert len(set(compilation_digests)) == 1


@pytest.mark.parametrize("entrypoint", ("committed", "build"))
@pytest.mark.parametrize("mutation", ("omit", "extra", "reorder"))
def test_native_verifiers_reject_compilation_inventory_path_mutation(
    tmp_path: Path,
    entrypoint: str,
    mutation: str,
) -> None:
    if entrypoint == "committed":
        router, artifact_dir = _copy_committed_fixture(tmp_path)
        manifest_path, manifest = _deployment_manifest(artifact_dir)
        verify = verify_committed_deployment
    else:
        router, artifact_dir, manifest = _copy_build_fixture(tmp_path)
        manifest_path = artifact_dir / "native_build_manifest.json"
        verify = verify_build_manifest
    compilation_inputs = manifest["compilation_tree"]["inputs"]

    if mutation == "omit":
        compilation_inputs.pop()
    elif mutation == "extra":
        phantom = b"// absent from the canonical source inventory\n"
        compilation_inputs.append(
            {
                "path": "src/Ariadne.AcadNative/zz_phantom.cpp",
                "sha256": hashlib.sha256(phantom).hexdigest(),
                "bytes": len(phantom),
            }
        )
        compilation_inputs.sort(
            key=lambda item: (item["path"].casefold(), item["path"])
        )
    else:
        compilation_inputs[0], compilation_inputs[1] = (
            compilation_inputs[1],
            compilation_inputs[0],
        )
    compilation_digest = native_integrity._source_tree_digest(compilation_inputs)
    manifest["compilation_tree"]["digest"] = compilation_digest
    if entrypoint == "committed":
        manifest["compilation_tree_digest"] = compilation_digest
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    receipt = verify(router, artifact_dir)

    assert receipt["checks"]["canonical_compilation_inputs_at_head"] is False
    assert receipt["checks"]["compilation_tree"] is False
    assert receipt["valid"] is False


def test_build_manifest_accepts_canonical_compiler_byte_identity(
    tmp_path: Path,
) -> None:
    router, native_bin, manifest = _copy_build_fixture(tmp_path)
    canonical_inputs = native_integrity._native_source_inputs(router)
    compilation_inputs = native_integrity._native_compilation_inputs(router)
    assert compilation_inputs == canonical_inputs
    manifest["compilation_tree"] = {
        "algorithm": "sha256",
        "byte_representation": "canonical_lf_unless_nul_mirror_bytes",
        "inputs": canonical_inputs,
        "digest": native_integrity._source_tree_digest(canonical_inputs),
    }
    (native_bin / "native_build_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    receipt = verify_build_manifest(router, native_bin)

    assert receipt["checks"]["source_tree"] is True
    assert receipt["checks"]["canonical_compilation_inputs_at_head"] is True
    assert receipt["checks"]["compilation_tree"] is True
    assert receipt["valid"] is True


def test_build_manifest_rejects_rehashed_noncanonical_compilation_bytes(
    tmp_path: Path,
) -> None:
    router, native_bin, manifest = _copy_build_fixture(tmp_path)
    source = router / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    canonical = source.read_bytes().replace(b"\r\n", b"\n")
    noncanonical = canonical.replace(b"\n", b"\r\n")
    assert noncanonical != canonical
    relative_path = "src/Ariadne.AcadNative/AriadneNativeJob.cpp"
    record = next(
        item
        for item in manifest["compilation_tree"]["inputs"]
        if item["path"] == relative_path
    )
    record["sha256"] = hashlib.sha256(noncanonical).hexdigest()
    record["bytes"] = len(noncanonical)
    manifest["compilation_tree"]["digest"] = native_integrity._source_tree_digest(
        manifest["compilation_tree"]["inputs"]
    )
    (native_bin / "native_build_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    receipt = verify_build_manifest(router, native_bin)

    assert receipt["checks"]["canonical_compilation_inputs_at_head"] is False
    assert receipt["checks"]["compilation_tree"] is False
    assert receipt["valid"] is False


def test_committed_deployment_rejects_changed_artifact_bytes(tmp_path: Path) -> None:
    router, deploy_dir = _copy_committed_fixture(tmp_path)
    artifact = deploy_dir / "Ariadne.AcadNative.crx"
    artifact.write_bytes(artifact.read_bytes() + b"changed")

    receipt = verify_committed_deployment(router, deploy_dir)

    assert receipt["valid"] is False
    assert receipt["checks"]["artifact:Ariadne.AcadNative.crx"] is False


def test_artifact_identity_and_pe_checks_use_one_byte_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    router, deploy_dir = _copy_committed_fixture(tmp_path)
    _bind_deployment_manifest_to_fixture(router, deploy_dir)
    artifact = deploy_dir / "Ariadne.AcadNative.crx"
    original = artifact.read_bytes()
    replacement = b"X" * len(original)
    manifest_path, manifest = _deployment_manifest(deploy_dir)
    record = next(item for item in manifest["artifacts"] if item["leaf"] == artifact.name)
    record["sha256"] = hashlib.sha256(replacement).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    original_capture = native_integrity._capture_native_verification_snapshot
    swapped = False

    def capture_then_swap(*args, **kwargs):
        nonlocal swapped
        snapshot = original_capture(*args, **kwargs)
        if not swapped:
            swapped = True
            artifact.write_bytes(replacement)
        return snapshot

    monkeypatch.setattr(
        native_integrity,
        "_capture_native_verification_snapshot",
        capture_then_swap,
    )

    receipt = verify_committed_deployment(router, deploy_dir)

    assert swapped is True
    assert artifact.read_bytes() == replacement
    assert receipt["valid"] is False
    assert receipt["checks"][f"artifact_pe:{artifact.name}"] is True
    assert receipt["checks"][f"artifact:{artifact.name}"] is False
    assert receipt["checks"]["input_snapshot_stable"] is False


@pytest.mark.parametrize(
    "relative_path",
    (
        Path("src") / "Ariadne.AcadNative" / "AriadneNativeJob.cpp",
        Path("prebuilt") / "2027" / "Ariadne.AcadNative.arx",
    ),
)
def test_committed_deployment_rejects_input_drift_during_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative_path: Path,
) -> None:
    router, deploy_dir = _copy_committed_fixture(tmp_path)
    _bind_deployment_manifest_to_fixture(router, deploy_dir)
    target = (router / relative_path).resolve()
    original = target.read_bytes()
    replacement = original + b"\nchanged-during-verification\n"
    original_capture = native_integrity._capture_native_verification_snapshot
    capture_count = 0

    def capture_then_persist_change(*args, **kwargs):
        nonlocal capture_count
        snapshot = original_capture(*args, **kwargs)
        capture_count += 1
        if capture_count == 1:
            target.write_bytes(replacement)
        return snapshot

    monkeypatch.setattr(
        native_integrity,
        "_capture_native_verification_snapshot",
        capture_then_persist_change,
    )

    receipt = verify_committed_deployment(router, deploy_dir)

    assert capture_count == 2
    assert target.read_bytes() == replacement
    assert receipt["valid"] is False
    assert receipt["checks"]["input_snapshot_stable"] is False
    assert "deployment inputs changed during verification" in receipt["errors"]


def test_committed_deployment_rejects_same_bytes_file_identity_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router, deploy_dir = _copy_committed_fixture(tmp_path)
    artifact = deploy_dir / "Ariadne.AcadNative.arx"
    original = artifact.read_bytes()
    original_capture = native_integrity._capture_native_verification_snapshot
    replaced = False

    def capture_then_replace_identity(*args, **kwargs):
        nonlocal replaced
        snapshot = original_capture(*args, **kwargs)
        if not replaced:
            replaced = True
            replacement = deploy_dir / "replacement.tmp"
            replacement.write_bytes(original)
            os.replace(replacement, artifact)
        return snapshot

    monkeypatch.setattr(
        native_integrity,
        "_capture_native_verification_snapshot",
        capture_then_replace_identity,
    )

    receipt = verify_committed_deployment(router, deploy_dir)

    assert replaced is True
    assert receipt["input_snapshot_sha256"] == receipt["ending_input_snapshot_sha256"]
    assert receipt["checks"][f"artifact:{artifact.name}"] is True
    assert receipt["checks"]["input_snapshot_stable"] is False
    assert receipt["valid"] is False


def test_committed_deployment_rejects_non_pe_bytes_even_when_hash_matches(
    tmp_path: Path,
) -> None:
    router, deploy_dir = _copy_committed_fixture(tmp_path)
    artifact = deploy_dir / "Ariadne.AcadNative.arx"
    artifact.write_bytes(b"not an x64 PE32+ DLL")
    manifest_path, manifest = _deployment_manifest(deploy_dir)
    record = next(item for item in manifest["artifacts"] if item["leaf"] == artifact.name)
    record["bytes"] = artifact.stat().st_size
    record["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    receipt = verify_committed_deployment(router, deploy_dir)

    assert receipt["valid"] is False
    assert receipt["checks"][f"artifact_pe:{artifact.name}"] is False


def test_committed_deployment_rejects_a_non_directory_path_component(
    tmp_path: Path,
) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("file", encoding="utf-8")

    receipt = verify_committed_deployment(tmp_path, blocker / "2027")

    assert receipt["valid"] is False
    assert "unsafe" in receipt["errors"][0]


def test_committed_deployment_rejects_a_reparse_directory(tmp_path: Path) -> None:
    router, deploy_dir = _copy_committed_fixture(tmp_path)
    link = tmp_path / "linked-deployment"
    try:
        os.symlink(deploy_dir, link, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    receipt = verify_committed_deployment(router, link)

    assert receipt["valid"] is False
    assert "reparse" in receipt["errors"][0] or "symlink" in receipt["errors"][0]


def test_committed_deployment_rejects_a_reparse_parent_of_the_build_recipe(
    tmp_path: Path,
) -> None:
    router, deploy_dir = _copy_committed_fixture(tmp_path)
    linked_tools = router / "tools"
    real_tools = tmp_path / "real-tools"
    linked_tools.rename(real_tools)
    if os.name == "nt":
        linked = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(linked_tools), str(real_tools)],
            check=False,
            capture_output=True,
            text=True,
        )
        if linked.returncode != 0:
            pytest.skip("directory junctions are unavailable: " + linked.stderr)
    else:
        os.symlink(real_tools, linked_tools, target_is_directory=True)

    receipt = verify_committed_deployment(router, deploy_dir)

    assert receipt["valid"] is False
    assert receipt["checks"]["build_recipe"] is False
    assert "missing or unsafe" in receipt["errors"][0]
    assert "final path" in receipt["errors"][0]
