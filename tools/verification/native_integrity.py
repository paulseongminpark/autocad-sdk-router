"""Fail-closed verification for checkout-bound native CAD binaries.

The public interface deliberately has only two entry points: one for an
ephemeral native build and one for a committed prebuilt deployment.  Both
return receipts; neither builds, publishes, loads, or mutates native files.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath

from . import git_state as _git_state
from . import file_snapshot as _file_snapshot


NATIVE_BUILD_MANIFEST_NAME = "native_build_manifest.json"
NATIVE_BUILD_MANIFEST_SCHEMA = "ariadne.cad_os.native_build_manifest.v1"
NATIVE_BUILD_MANIFEST_VERSION = 1
NATIVE_DEPLOYMENT_MANIFEST_NAME = "native_deployment_manifest.json"
NATIVE_DEPLOYMENT_MANIFEST_SCHEMA = "ariadne.cad_os.native_deployment_manifest.v1"
NATIVE_DEPLOYMENT_MANIFEST_VERSION = 1
REQUIRED_NATIVE_ARTIFACTS = (
    "Ariadne.AcadNativeDbx.dbx",
    "Ariadne.AcadNative.crx",
    "Ariadne.AcadNative.arx",
)
_NATIVE_SOURCE_ROOTS = (
    Path("src") / "Ariadne.AcadNative",
    Path("src") / "Ariadne.AcadNativeDbx",
)
_NATIVE_SOURCE_PREFIXES = tuple(
    PurePosixPath(root.as_posix()) for root in _NATIVE_SOURCE_ROOTS
)
_NATIVE_BUILD_OUTPUT_DIRS = frozenset({"bin", "obj", ".vs", "build"})
_NATIVE_BUILD_RECIPE_PATH = Path("tools") / "build_native_acad.ps1"
_SOURCE_CANONICALIZATION = "crlf_to_lf_unless_nul"
_COMPILATION_BYTE_REPRESENTATION = "canonical_lf_unless_nul_mirror_bytes"
_COMPILATION_INPUT_MODE = "immutable_starting_snapshot_mirror"
_COMMITTED_VERIFICATION_SCOPE = (
    "committed_artifact_identity_and_canonical_compilation_input_binding"
)
_COMMITTED_LIMITATION_CODES = (
    "external_toolchain_inputs_unsealed",
    "binary_rebuild_equivalence_not_proven",
)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not permitted: {value}")


def _reject_duplicate_json_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _strict_json_loads(value: str) -> object:
    return json.loads(
        value,
        object_pairs_hook=_reject_duplicate_json_object,
        parse_constant=_reject_json_constant,
    )


def _source_tree_digest(inputs: list[dict]) -> str:
    digest = hashlib.sha256()
    for entry in inputs:
        digest.update(
            f"{entry['path']}\0{entry['sha256']}\0{entry['bytes']}\n".encode("utf-8")
        )
    return digest.hexdigest()


def _is_native_build_output_component(component: str) -> bool:
    normalized = component.casefold()
    return (
        normalized in _NATIVE_BUILD_OUTPUT_DIRS
        or normalized.startswith("obj-")
        or normalized.startswith("obj_")
    )


def _is_reparse_point(path: Path) -> bool:
    metadata = os.lstat(path)
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _canonical_native_source_bytes(raw: bytes) -> bytes:
    if b"\0" in raw:
        return raw
    return raw.replace(b"\r\n", b"\n")


def _path_reparse_error(path: Path) -> str | None:
    """Return an error for an existing reparse or non-directory path component."""
    absolute = Path(os.path.abspath(str(path)))
    if not absolute.anchor:
        return f"path is not absolute: {path}"
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        if not os.path.lexists(current):
            break
        try:
            if _is_reparse_point(current):
                return f"path crosses a symlink or reparse point: {current}"
        except OSError as exc:
            return f"cannot inspect path component {current}: {type(exc).__name__}: {exc}"
        if current != absolute and not current.is_dir():
            return f"path component is not a directory: {current}"
    return None


def _native_source_inputs(
    router_home: Path,
    *,
    is_reparse_point=None,
    path_reparse_error=None,
) -> list[dict]:
    relative_paths = _discover_native_source_paths(
        router_home,
        is_reparse_point=is_reparse_point,
        path_reparse_error=path_reparse_error,
    )
    captured = _file_snapshot.capture_files(router_home, tuple(relative_paths))
    return _native_source_inputs_from_capture(captured, relative_paths)


def _native_compilation_inputs(router_home: Path) -> list[dict]:
    relative_paths = _discover_native_source_paths(router_home)
    captured = _file_snapshot.capture_files(router_home, tuple(relative_paths))
    return _native_compilation_inputs_from_capture(captured, relative_paths)


def _discover_native_source_paths(
    router_home: Path,
    *,
    is_reparse_point=None,
    path_reparse_error=None,
) -> list[str]:
    is_reparse_point = is_reparse_point or _is_reparse_point
    path_reparse_error = path_reparse_error or _path_reparse_error
    relative_paths: list[str] = []
    for relative_root in _NATIVE_SOURCE_ROOTS:
        root = Path(router_home) / relative_root
        if not root.is_dir() or path_reparse_error(root) is not None:
            raise FileNotFoundError(f"native source root is missing: {root}")
        for current_text, directory_names, file_names in os.walk(
            root, topdown=True, followlinks=False
        ):
            current = Path(current_text)
            if is_reparse_point(current):
                raise OSError(f"native source directory is a reparse point: {current}")
            retained_directories = []
            for name in directory_names:
                child = current / name
                if is_reparse_point(child):
                    raise OSError(f"native source directory is a reparse point: {child}")
                if not _is_native_build_output_component(name):
                    retained_directories.append(name)
            directory_names[:] = retained_directories
            for name in file_names:
                path = current / name
                relative_paths.append(path.relative_to(router_home).as_posix())
    relative_paths.sort(key=str.casefold)
    if not relative_paths:
        raise FileNotFoundError("native source input inventory is empty")
    return relative_paths


def _native_source_inputs_from_capture(
    captured: _file_snapshot.ImmutableFileSnapshot,
    relative_paths: list[str] | tuple[str, ...],
) -> list[dict]:
    inputs: list[dict] = []
    for relative_path in sorted(relative_paths, key=str.casefold):
        raw = _canonical_native_source_bytes(
            captured.files[relative_path].content
        )
        inputs.append({
            "path": relative_path,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        })
    return inputs


def _native_compilation_inputs_from_capture(
    captured: _file_snapshot.ImmutableFileSnapshot,
    relative_paths: list[str] | tuple[str, ...],
) -> list[dict]:
    inputs: list[dict] = []
    for relative_path in sorted(relative_paths, key=str.casefold):
        canonical = _canonical_native_source_bytes(
            captured.files[relative_path].content
        )
        inputs.append({
            "path": relative_path,
            "sha256": hashlib.sha256(canonical).hexdigest(),
            "bytes": len(canonical),
        })
    return inputs


def _native_source_git_state(router_home: Path) -> dict:
    """Project the stable public observer onto the historical manifest shape."""

    unknown = {
        "available": False,
        "head": "UNKNOWN",
        "native_source_dirty": "UNKNOWN",
        "native_source_status_sha256": "UNKNOWN",
    }
    observed = _git_state.observe_native_source_checkout(Path(router_home))
    if (
        observed.get("status") != "PASS"
        or observed.get("available") is not True
        or not isinstance(observed.get("head"), str)
        or not isinstance(observed.get("native_source_dirty"), bool)
        or not isinstance(observed.get("native_source_status_sha256"), str)
    ):
        return unknown
    return {
        "available": True,
        "head": observed["head"],
        "native_source_dirty": observed["native_source_dirty"],
        "native_source_status_sha256": observed[
            "native_source_status_sha256"
        ],
    }


def _build_recipe_state(router_home: Path) -> dict:
    try:
        captured = _file_snapshot.capture_files(
            Path(router_home),
            (_NATIVE_BUILD_RECIPE_PATH.as_posix(),),
        )
        sha256 = hashlib.sha256(
            _canonical_native_source_bytes(
                captured.files[_NATIVE_BUILD_RECIPE_PATH.as_posix()].content
            )
        ).hexdigest()
    except OSError:
        return {
            "path": _NATIVE_BUILD_RECIPE_PATH.as_posix(),
            "sha256": "UNKNOWN",
            "available": False,
        }
    return {
        "path": _NATIVE_BUILD_RECIPE_PATH.as_posix(),
        "sha256": sha256,
        "available": True,
    }


def _same_resolved_path(left: object, right: Path) -> bool:
    if not isinstance(left, str) or not left:
        return False
    try:
        left_path = Path(left).resolve(strict=False)
        right_path = Path(right).resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return False
    return os.path.normcase(str(left_path)) == os.path.normcase(str(right_path))


def _pe64_bytes_state(raw: bytes) -> dict:
    state = {
        "verified": False,
        "machine": None,
        "format": None,
        "minimum_bytes": 512,
        "pe_header_offset": None,
        "section_count": None,
        "optional_header_bytes": None,
        "reason": None,
    }
    try:
        if len(raw) < state["minimum_bytes"]:
            raise ValueError("artifact is smaller than the minimum PE inspection size")
        if raw[:2] != b"MZ":
            raise ValueError("DOS MZ signature is missing")
        pe_offset = int.from_bytes(raw[0x3C:0x40], "little")
        state["pe_header_offset"] = pe_offset
        if pe_offset < 0x40 or pe_offset + 24 > len(raw):
            raise ValueError("PE header offset is outside the artifact")
        if raw[pe_offset : pe_offset + 4] != b"PE\x00\x00":
            raise ValueError("PE signature is missing")
        machine = int.from_bytes(raw[pe_offset + 4 : pe_offset + 6], "little")
        section_count = int.from_bytes(raw[pe_offset + 6 : pe_offset + 8], "little")
        optional_bytes = int.from_bytes(raw[pe_offset + 20 : pe_offset + 22], "little")
        characteristics = int.from_bytes(raw[pe_offset + 22 : pe_offset + 24], "little")
        optional_offset = pe_offset + 24
        if optional_offset + optional_bytes > len(raw):
            raise ValueError("optional header extends beyond the artifact")
        optional_magic = int.from_bytes(raw[optional_offset : optional_offset + 2], "little")
        state.update(
            {
                "machine": f"0x{machine:04x}",
                "format": "PE32+" if optional_magic == 0x20B else f"0x{optional_magic:04x}",
                "section_count": section_count,
                "optional_header_bytes": optional_bytes,
            }
        )
        if machine != 0x8664:
            raise ValueError("PE machine is not AMD64")
        if section_count < 1:
            raise ValueError("PE has no sections")
        if optional_bytes < 0xF0 or optional_magic != 0x20B:
            raise ValueError("PE optional header is not a complete PE32+ header")
        if not characteristics & 0x2000:
            raise ValueError("PE image is not marked as a DLL")
        state["verified"] = True
        state["reason"] = "verified x64 PE32+ DLL image"
    except ValueError as exc:
        state["reason"] = f"{type(exc).__name__}: {exc}"
    return state


def _pe64_image_state(path: Path) -> dict:
    try:
        path = Path(path)
        captured = _file_snapshot.capture_files(path.parent, (path.name,))
        raw = captured.files[path.name].content
    except OSError as exc:
        state = _pe64_bytes_state(b"")
        state["reason"] = f"{type(exc).__name__}: {exc}"
        return state
    return _pe64_bytes_state(raw)


def _new_receipt(path: Path) -> dict:
    return {
        "path": str(path),
        "sha256": None,
        "valid": False,
        "checks": {},
        "errors": [],
        "artifact_paths": [],
    }


def _verified_artifact_bytes(
    raw: bytes,
    item: object,
    *,
    require_exists_claim: bool,
) -> tuple[bool, bool]:
    if not isinstance(item, dict):
        return False, False
    observed_pe = _pe64_bytes_state(raw)
    manifest_pe = item.get("pe_verification")
    pe_ok = (
        isinstance(manifest_pe, dict)
        and manifest_pe.get("verified") is True
        and manifest_pe.get("machine") == observed_pe.get("machine") == "0x8664"
        and manifest_pe.get("format") == observed_pe.get("format") == "PE32+"
        and manifest_pe.get("minimum_bytes") == observed_pe.get("minimum_bytes") == 512
        and manifest_pe.get("pe_header_offset") == observed_pe.get("pe_header_offset")
        and manifest_pe.get("section_count") == observed_pe.get("section_count")
        and manifest_pe.get("optional_header_bytes")
        == observed_pe.get("optional_header_bytes")
        and observed_pe.get("verified") is True
    )
    artifact_ok = (
        item.get("current") is True
        and (not require_exists_claim or item.get("exists") is True)
        and isinstance(item.get("bytes"), int)
        and not isinstance(item.get("bytes"), bool)
        and item.get("bytes") == len(raw)
        and isinstance(item.get("sha256"), str)
        and item.get("sha256").lower() == hashlib.sha256(raw).hexdigest()
        and pe_ok
    )
    return artifact_ok, pe_ok


def _artifact_records(manifest: dict, receipt: dict) -> dict[str, dict]:
    artifacts = manifest.get("artifacts")
    by_leaf: dict[str, dict] = {}
    if not isinstance(artifacts, list):
        receipt["errors"].append("manifest artifacts")
        return by_leaf
    for item in artifacts:
        if not isinstance(item, dict) or not isinstance(item.get("leaf"), str):
            receipt["errors"].append("manifest artifact record")
            continue
        leaf = item["leaf"]
        if leaf in by_leaf:
            receipt["errors"].append(f"duplicate manifest artifact: {leaf}")
        by_leaf[leaf] = item
    expected = set(REQUIRED_NATIVE_ARTIFACTS)
    if set(by_leaf) != expected or len(artifacts) != len(expected):
        receipt["errors"].append("manifest artifact leaf set")
    return by_leaf


@dataclass(frozen=True)
class _NativeVerificationSnapshot:
    captured: _file_snapshot.ImmutableFileSnapshot
    source_paths: tuple[str, ...]

    @property
    def manifest_bytes(self) -> bytes:
        return self.captured.files["manifest"].content

    @property
    def recipe_bytes(self) -> bytes:
        return self.captured.files["build_recipe"].content

    def artifact_bytes(self, leaf: str) -> bytes:
        return self.captured.files[f"artifact:{leaf}"].content

    def source_inputs(self) -> list[dict]:
        inputs: list[dict] = []
        for relative_path in self.source_paths:
            raw = _canonical_native_source_bytes(
                self.captured.files[f"source:{relative_path}"].content
            )
            inputs.append({
                "path": relative_path,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            })
        return inputs

    def compilation_inputs(self) -> list[dict]:
        inputs: list[dict] = []
        for relative_path in self.source_paths:
            canonical = _canonical_native_source_bytes(
                self.captured.files[f"source:{relative_path}"].content
            )
            inputs.append({
                "path": relative_path,
                "sha256": hashlib.sha256(canonical).hexdigest(),
                "bytes": len(canonical),
            })
        return inputs

    def same_generation_as(self, other: object) -> bool:
        return (
            isinstance(other, _NativeVerificationSnapshot)
            and self.source_paths == other.source_paths
            and self.captured.same_generation_as(other.captured)
        )


def _capture_native_verification_snapshot(
    router_home: Path,
    artifact_dir: Path,
    manifest_name: str,
    source_paths: tuple[str, ...],
) -> _NativeVerificationSnapshot:
    """Capture every native verifier input in one handle-held generation."""

    requests: dict[str, _file_snapshot.FileRequest] = {
        "manifest": _file_snapshot.FileRequest(artifact_dir, manifest_name),
        "build_recipe": _file_snapshot.FileRequest(
            router_home,
            _NATIVE_BUILD_RECIPE_PATH.as_posix(),
        ),
        **{
            f"source:{relative_path}": _file_snapshot.FileRequest(
                router_home,
                relative_path,
            )
            for relative_path in source_paths
        },
        **{
            f"artifact:{leaf}": _file_snapshot.FileRequest(artifact_dir, leaf)
            for leaf in REQUIRED_NATIVE_ARTIFACTS
        },
    }
    captured = _file_snapshot.capture_file_set(requests)
    return _NativeVerificationSnapshot(captured, source_paths)


def _normalized_manifest_source_inputs(manifest: object) -> list[dict]:
    if not isinstance(manifest, dict):
        raise ValueError("native manifest root must be an object")
    source_tree = manifest.get("source_tree")
    inputs = source_tree.get("inputs") if isinstance(source_tree, dict) else None
    if not isinstance(inputs, list) or not inputs:
        raise ValueError(
            "native manifest has no exact source_tree.inputs inventory"
        )
    normalized: list[dict] = []
    for item in inputs:
        if not isinstance(item, dict):
            raise ValueError("native source input must be an object")
        path = item.get("path")
        sha256 = item.get("sha256")
        byte_count = item.get("bytes")
        if (
            not isinstance(path, str)
            or not isinstance(sha256, str)
            or len(sha256) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in sha256)
            or not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
        ):
            raise ValueError("native source input fields are invalid")
        candidate = PurePosixPath(path.replace("\\", "/"))
        if (
            candidate.is_absolute()
            or any(part in {"", ".", ".."} for part in candidate.parts)
            or not any(
                candidate == root or root in candidate.parents
                for root in _NATIVE_SOURCE_PREFIXES
            )
            or any(_is_native_build_output_component(part) for part in candidate.parts)
        ):
            raise ValueError(f"native source input path is unsafe: {path!r}")
        normalized.append({
            "path": candidate.as_posix(),
            "sha256": sha256.lower(),
            "bytes": byte_count,
        })
    expected_order = sorted(
        normalized,
        key=lambda item: (item["path"].casefold(), item["path"]),
    )
    if normalized != expected_order:
        raise ValueError("native source input inventory is not deterministically sorted")
    paths = [item["path"] for item in normalized]
    if len(paths) != len(set(paths)):
        raise ValueError("native source input inventory contains duplicate paths")
    return normalized


def _normalized_manifest_compilation_inputs(manifest: object) -> list[dict]:
    if not isinstance(manifest, dict):
        raise ValueError("native manifest root must be an object")
    compilation_tree = manifest.get("compilation_tree")
    inputs = (
        compilation_tree.get("inputs")
        if isinstance(compilation_tree, dict)
        else None
    )
    if not isinstance(inputs, list) or not inputs:
        raise ValueError(
            "native manifest has no exact compilation_tree.inputs inventory"
        )
    return _normalized_manifest_source_inputs({"source_tree": {"inputs": inputs}})


def _capture_manifest_declaration(
    artifact_dir: Path,
    manifest_name: str,
) -> tuple[bytes, dict, list[dict]]:
    captured = _file_snapshot.capture_files(artifact_dir, (manifest_name,))
    raw = captured.files[manifest_name].content
    manifest = _strict_json_loads(raw.decode("utf-8-sig"))
    inputs = _normalized_manifest_source_inputs(manifest)
    assert isinstance(manifest, dict)
    return raw, manifest, inputs


def _git_native_source_paths(router_home: Path) -> tuple[str, ...]:
    raw = _git_state._run_git_bytes(  # one hardened Git command owner
        Path(router_home),
        (
            "ls-files",
            "-z",
            "--cached",
            "--",
            *(_root.as_posix() for _root in _NATIVE_SOURCE_ROOTS),
        ),
    )
    paths: list[str] = []
    for encoded in raw.split(b"\0"):
        if not encoded:
            continue
        path = encoded.decode("utf-8", errors="strict").replace("\\", "/")
        candidate = PurePosixPath(path)
        if any(_is_native_build_output_component(part) for part in candidate.parts):
            continue
        if not any(
            candidate == root or root in candidate.parents
            for root in _NATIVE_SOURCE_PREFIXES
        ):
            raise ValueError(f"Git returned an out-of-scope native path: {path!r}")
        paths.append(candidate.as_posix())
    paths.sort(key=lambda path: (path.casefold(), path))
    if not paths or len(paths) != len(set(paths)):
        raise ValueError("Git native source inventory is empty or duplicated")
    return tuple(paths)


def _snapshot_head_binding(
    router_home: Path,
    git_state: dict,
    snapshot: _NativeVerificationSnapshot,
) -> dict:
    """Bind canonical captured inputs, including the recipe, to exact HEAD blobs."""

    head = git_state.get("head")
    if git_state.get("available") is not True or not isinstance(head, str):
        return {
            "status": "BLOCKED",
            "errors": [{"message": "native checkout HEAD is unavailable"}],
        }
    observed = {
        item["path"]: item["sha256"] for item in snapshot.source_inputs()
    }
    recipe = _recipe_state_from_snapshot(snapshot)
    observed[recipe["path"]] = recipe["sha256"]
    return _git_state.verify_paths_at_revision(router_home, head, observed)


def _recipe_state_from_snapshot(snapshot: _NativeVerificationSnapshot) -> dict:
    raw = _canonical_native_source_bytes(snapshot.recipe_bytes)
    return {
        "path": _NATIVE_BUILD_RECIPE_PATH.as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "available": True,
    }


def verify_committed_deployment(router_home: Path, deploy_dir: Path) -> dict:
    """Verify artifact identity and canonical compiler inputs against HEAD.

    The producer compiles the canonical leased mirror generation.  This
    consumer reconstructs that deterministic byte generation from the current
    handle-held checkout and binds it to exact HEAD blobs before comparing the
    manifest, independent of checkout line-ending materialization.
    """
    router_home = Path(router_home)
    deploy_dir = Path(deploy_dir)
    manifest_path = deploy_dir / NATIVE_DEPLOYMENT_MANIFEST_NAME
    receipt = _new_receipt(manifest_path)
    receipt["verification_scope"] = _COMMITTED_VERIFICATION_SCOPE
    receipt["limitation_codes"] = list(_COMMITTED_LIMITATION_CODES)
    checks = receipt["checks"]
    try:
        _, _, declared_source_inputs = (
            _capture_manifest_declaration(
                deploy_dir,
                NATIVE_DEPLOYMENT_MANIFEST_NAME,
            )
        )
        source_paths = tuple(item["path"] for item in declared_source_inputs)
        current_git = _native_source_git_state(router_home)
        git_source_paths = _git_native_source_paths(router_home)
        workspace_source_paths = tuple(_discover_native_source_paths(router_home))
        checks["source_inventory_authority"] = (
            current_git.get("available") is True
            and source_paths == git_source_paths == workspace_source_paths
        )
        if not checks["source_inventory_authority"]:
            raise ValueError(
                "committed source_tree.inputs must equal the clean Git native "
                "source inventory"
            )
        checks["source_checkout_clean"] = (
            current_git.get("native_source_dirty") is False
        )
        if not checks["source_checkout_clean"]:
            receipt["errors"].append(
                "committed native source checkout is not clean"
            )
        starting_snapshot = _capture_native_verification_snapshot(
            router_home,
            deploy_dir,
            NATIVE_DEPLOYMENT_MANIFEST_NAME,
            source_paths,
        )
        receipt["input_snapshot_sha256"] = (
            starting_snapshot.captured.aggregate_sha256
        )
        head_binding = _snapshot_head_binding(
            router_home,
            current_git,
            starting_snapshot,
        )
        checks["source_inputs_at_head"] = head_binding.get("status") == "PASS"
        checks["compilation_inputs_bound_to_head_paths"] = (
            checks["source_inputs_at_head"]
            and [item["path"] for item in starting_snapshot.compilation_inputs()]
            == [item["path"] for item in starting_snapshot.source_inputs()]
        )
        checks["canonical_compilation_inputs_at_head"] = (
            checks["source_inputs_at_head"]
            and starting_snapshot.compilation_inputs()
            == starting_snapshot.source_inputs()
        )
        receipt["head_binding"] = head_binding
        if not checks["source_inputs_at_head"]:
            receipt["errors"].append(
                "captured native source or build recipe does not match exact HEAD blobs"
            )
    except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
        receipt["errors"].append(
            "native deployment input snapshot is missing or unsafe: "
            f"{type(exc).__name__}: {exc}"
        )
        checks["build_recipe"] = False
        checks.setdefault("source_inventory_authority", False)
        checks["input_snapshot_stable"] = False
        return receipt

    manifest: object | None = None
    try:
        manifest_bytes = starting_snapshot.manifest_bytes
        manifest = _strict_json_loads(manifest_bytes.decode("utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        receipt["errors"].append(
            f"native deployment manifest is not parseable: {type(exc).__name__}: {exc}"
        )
    else:
        receipt["sha256"] = hashlib.sha256(manifest_bytes).hexdigest()

    artifact_paths: list[Path] = []
    if not isinstance(manifest, dict):
        if manifest is not None:
            receipt["errors"].append("native deployment manifest is not an object")
    else:
        checks["schema"] = (
            manifest.get("schema") == NATIVE_DEPLOYMENT_MANIFEST_SCHEMA
            and manifest.get("schema_version") == NATIVE_DEPLOYMENT_MANIFEST_VERSION
        )
        checks["claim_scope"] = (
            manifest.get("claim_scope") == "release_build_integrity_bundle"
        )
        checks["committed"] = (
            manifest.get("deployment_state") == "committed"
            and manifest.get("committed") is True
        )
        checks["build_target"] = manifest.get("build_target") == "Rebuild"
        checks["configuration"] = manifest.get("configuration") == "Release"
        checks["platform"] = manifest.get("platform") == "x64"
        source_provenance = manifest.get("source_provenance")
        checks["immutable_compilation_input"] = (
            isinstance(source_provenance, dict)
            and source_provenance.get("compilation_input")
            == _COMPILATION_INPUT_MODE
            and source_provenance.get("mirror_ephemeral") is True
        )
        for key in (
            "schema",
            "claim_scope",
            "committed",
            "build_target",
            "configuration",
            "platform",
            "immutable_compilation_input",
        ):
            if not checks[key]:
                receipt["errors"].append("manifest " + key.replace("_", " "))

        recipe = _recipe_state_from_snapshot(starting_snapshot)
        checks["build_recipe"] = (
            manifest.get("build_recipe")
            == {"path": recipe["path"], "sha256": recipe["sha256"]}
        )
        if not checks["build_recipe"]:
            receipt["errors"].append("manifest build recipe SHA-256")

        source_inputs = starting_snapshot.source_inputs()
        source_digest = _source_tree_digest(source_inputs)
        try:
            manifest_source_inputs = _normalized_manifest_source_inputs(manifest)
        except ValueError:
            manifest_source_inputs = None
        checks["source_tree"] = (
            manifest_source_inputs == source_inputs
            and isinstance(manifest.get("source_tree"), dict)
            and manifest["source_tree"].get("algorithm") == "sha256"
            and manifest["source_tree"].get("canonicalization")
            == _SOURCE_CANONICALIZATION
            and manifest["source_tree"].get("digest") == source_digest
            and manifest.get("source_tree_digest") == source_digest
        )
        if not checks["source_tree"]:
            receipt["errors"].append("native source-tree digest")

        try:
            manifest_compilation_inputs = (
                _normalized_manifest_compilation_inputs(manifest)
            )
        except ValueError:
            manifest_compilation_inputs = None
        compilation_tree = manifest.get("compilation_tree")
        expected_compilation_inputs = starting_snapshot.compilation_inputs()
        expected_compilation_digest = _source_tree_digest(
            expected_compilation_inputs
        )
        manifest_compilation_paths = (
            [item["path"] for item in manifest_compilation_inputs]
            if manifest_compilation_inputs is not None
            else None
        )
        source_input_paths = [item["path"] for item in source_inputs]
        checks["compilation_inputs_bound_to_head_paths"] = (
            checks["compilation_inputs_bound_to_head_paths"]
            and manifest_compilation_paths == source_input_paths
        )
        checks["canonical_compilation_inputs_at_head"] = (
            checks["canonical_compilation_inputs_at_head"]
            and manifest_compilation_inputs
            == expected_compilation_inputs
            == source_inputs
        )
        checks["compilation_tree"] = (
            isinstance(compilation_tree, dict)
            and compilation_tree.get("algorithm") == "sha256"
            and compilation_tree.get("byte_representation")
            == _COMPILATION_BYTE_REPRESENTATION
            and checks["canonical_compilation_inputs_at_head"]
            and compilation_tree.get("digest") == expected_compilation_digest
            and manifest.get("compilation_tree_digest")
            == expected_compilation_digest
        )
        if not checks["compilation_tree"]:
            receipt["errors"].append("canonical compilation input-tree binding")

        by_leaf = _artifact_records(manifest, receipt)
        artifacts_ok = set(by_leaf) == set(REQUIRED_NATIVE_ARTIFACTS)
        for leaf in REQUIRED_NATIVE_ARTIFACTS:
            artifact_ok, pe_ok = _verified_artifact_bytes(
                starting_snapshot.artifact_bytes(leaf),
                by_leaf.get(leaf),
                require_exists_claim=True,
            )
            checks[f"artifact_pe:{leaf}"] = pe_ok
            checks[f"artifact:{leaf}"] = artifact_ok
            if artifact_ok:
                artifact_paths.append(deploy_dir / leaf)
            else:
                artifacts_ok = False
                receipt["errors"].append(f"manifest artifact binding: {leaf}")
        checks["artifacts"] = artifacts_ok

    try:
        ending_snapshot = _capture_native_verification_snapshot(
            router_home,
            deploy_dir,
            NATIVE_DEPLOYMENT_MANIFEST_NAME,
            source_paths,
        )
        ending_snapshot_sha256 = ending_snapshot.captured.aggregate_sha256
        receipt["ending_input_snapshot_sha256"] = ending_snapshot_sha256
        checks["input_snapshot_stable"] = starting_snapshot.same_generation_as(
            ending_snapshot
        )
    except (OSError, ValueError) as exc:
        receipt["ending_input_snapshot_sha256"] = None
        checks["input_snapshot_stable"] = False
        receipt["errors"].append(
            "deployment inputs became unavailable during verification: "
            f"{type(exc).__name__}: {exc}"
        )
    if not checks["input_snapshot_stable"]:
        receipt["errors"].append("deployment inputs changed during verification")
    final_git = _native_source_git_state(router_home)
    try:
        final_git_source_paths = _git_native_source_paths(router_home)
        final_workspace_source_paths = tuple(
            _discover_native_source_paths(router_home)
        )
    except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
        final_git_source_paths = ()
        final_workspace_source_paths = ()
        receipt["errors"].append(
            "committed source inventory became unavailable during verification: "
            f"{type(exc).__name__}: {exc}"
        )
    checks["git_stable"] = (
        current_git.get("available") is True
        and final_git.get("available") is True
        and current_git == final_git
        and final_git_source_paths == git_source_paths
        and final_workspace_source_paths == workspace_source_paths
    )
    if not checks["git_stable"]:
        receipt["errors"].append(
            "committed source checkout changed during verification"
        )
    receipt["artifact_paths"] = [str(path) for path in artifact_paths]
    receipt["valid"] = not receipt["errors"]
    return receipt


def verify_build_manifest(router_home: Path, native_bin: Path) -> dict:
    """Verify an ephemeral build manifest against the current checkout."""
    router_home = Path(router_home)
    native_bin = Path(native_bin)
    manifest_path = native_bin / NATIVE_BUILD_MANIFEST_NAME
    receipt = _new_receipt(manifest_path)
    checks = receipt["checks"]
    try:
        _, _, declared_source_inputs = _capture_manifest_declaration(
            native_bin,
            NATIVE_BUILD_MANIFEST_NAME,
        )
        source_paths = tuple(item["path"] for item in declared_source_inputs)
        git_source_paths = _git_native_source_paths(router_home)
        workspace_source_paths = tuple(_discover_native_source_paths(router_home))
        checks["source_inventory_authority"] = (
            source_paths == git_source_paths == workspace_source_paths
        )
        if not checks["source_inventory_authority"]:
            raise ValueError(
                "build source_tree.inputs must equal the Git native source inventory"
            )
        starting_snapshot = _capture_native_verification_snapshot(
            router_home,
            native_bin,
            NATIVE_BUILD_MANIFEST_NAME,
            source_paths,
        )
        receipt["input_snapshot_sha256"] = (
            starting_snapshot.captured.aggregate_sha256
        )
    except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
        receipt["errors"].append(
            "native build input snapshot is missing or unsafe: "
            f"{type(exc).__name__}: {exc}"
        )
        checks["input_snapshot_stable"] = False
        checks.setdefault("source_inventory_authority", False)
        return receipt

    current_git = _native_source_git_state(router_home)
    head_binding = _snapshot_head_binding(
        router_home,
        current_git,
        starting_snapshot,
    )
    checks["source_inputs_at_head"] = head_binding.get("status") == "PASS"
    checks["compilation_inputs_bound_to_head_paths"] = (
        checks["source_inputs_at_head"]
        and [item["path"] for item in starting_snapshot.compilation_inputs()]
        == [item["path"] for item in starting_snapshot.source_inputs()]
    )
    checks["canonical_compilation_inputs_at_head"] = (
        checks["source_inputs_at_head"]
        and starting_snapshot.compilation_inputs()
        == starting_snapshot.source_inputs()
    )
    receipt["head_binding"] = head_binding
    if not checks["source_inputs_at_head"]:
        receipt["errors"].append(
            "captured native source or build recipe does not match exact HEAD blobs"
        )
    manifest: object | None = None
    try:
        manifest_bytes = starting_snapshot.manifest_bytes
        manifest = _strict_json_loads(manifest_bytes.decode("utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        receipt["errors"].append(
            f"native build manifest is not parseable: {type(exc).__name__}: {exc}"
        )
    else:
        receipt["sha256"] = hashlib.sha256(manifest_bytes).hexdigest()

    artifact_paths: list[Path] = []
    if not isinstance(manifest, dict):
        if manifest is not None:
            receipt["errors"].append("native build manifest is not an object")
    else:
        checks["schema"] = (
            manifest.get("schema") == NATIVE_BUILD_MANIFEST_SCHEMA
            and manifest.get("schema_version") == NATIVE_BUILD_MANIFEST_VERSION
        )
        if not checks["schema"]:
            receipt["errors"].append("manifest schema/version")
        checks["claim_scope"] = (
            manifest.get("claim_scope") == "release_build_integrity_bundle"
        )
        checks["build_target"] = manifest.get("build_target") == "Rebuild"
        if not checks["claim_scope"] or not checks["build_target"]:
            receipt["errors"].append("manifest claim scope or build target")
        checks["configuration"] = manifest.get("configuration") == "Release"
        checks["platform"] = manifest.get("platform") == "x64"
        if not checks["configuration"] or not checks["platform"]:
            receipt["errors"].append("manifest configuration/platform")
        source_provenance = manifest.get("source_provenance")
        build_snapshot = manifest.get("build_snapshot")
        checks["immutable_compilation_input"] = (
            isinstance(source_provenance, dict)
            and source_provenance.get("compilation_input")
            == _COMPILATION_INPUT_MODE
            and source_provenance.get("mirror_ephemeral") is True
            and isinstance(build_snapshot, dict)
            and build_snapshot.get("input_mode") == _COMPILATION_INPUT_MODE
            and build_snapshot.get("exact_match") is True
        )
        if not checks["immutable_compilation_input"]:
            receipt["errors"].append("manifest immutable compilation input mode")
        checks["load_bin_dir"] = _same_resolved_path(
            manifest.get("load_bin_dir"), native_bin
        )
        if not checks["load_bin_dir"]:
            receipt["errors"].append("manifest load bin directory")

        checkout = manifest.get("checkout")
        git = checkout.get("git") if isinstance(checkout, dict) else None
        checks["checkout_root"] = (
            isinstance(checkout, dict)
            and _same_resolved_path(checkout.get("root"), router_home)
        )
        if not checks["checkout_root"]:
            receipt["errors"].append("manifest checkout root")
        checks["git_available"] = (
            isinstance(git, dict)
            and git.get("available") is True
            and current_git.get("available") is True
        )
        if not checks["git_available"]:
            receipt["errors"].append("checkout Git state is UNKNOWN")
        else:
            checks["git_head"] = (
                isinstance(git.get("head"), str)
                and git.get("head") == current_git.get("head")
            )
            checks["git_native_source_dirty"] = (
                isinstance(git.get("native_source_dirty"), bool)
                and git.get("native_source_dirty")
                == current_git.get("native_source_dirty")
            )
            checks["git_native_source_status_sha256"] = (
                isinstance(git.get("native_source_status_sha256"), str)
                and git.get("native_source_status_sha256")
                == current_git.get("native_source_status_sha256")
            )
            for key in (
                "git_head",
                "git_native_source_dirty",
                "git_native_source_status_sha256",
            ):
                if not checks[key]:
                    receipt["errors"].append(
                        "manifest " + key.replace("git_", "Git ")
                    )

        manifest_recipe = manifest.get("build_recipe")
        current_recipe = _recipe_state_from_snapshot(starting_snapshot)
        checks["build_recipe"] = (
            isinstance(manifest_recipe, dict)
            and manifest_recipe.get("path") == _NATIVE_BUILD_RECIPE_PATH.as_posix()
            and isinstance(manifest_recipe.get("sha256"), str)
            and manifest_recipe.get("sha256").lower()
            == current_recipe.get("sha256")
        )
        if not checks["build_recipe"]:
            receipt["errors"].append("manifest build recipe SHA-256")

        source_tree = manifest.get("source_tree")
        manifest_inputs = (
            source_tree.get("inputs") if isinstance(source_tree, dict) else None
        )
        normalized_inputs = []
        if isinstance(manifest_inputs, list):
            for item in manifest_inputs:
                if not isinstance(item, dict):
                    normalized_inputs = None
                    break
                path = item.get("path")
                sha256 = item.get("sha256")
                size = item.get("bytes")
                if (
                    not isinstance(path, str)
                    or not isinstance(sha256, str)
                    or not isinstance(size, int)
                    or isinstance(size, bool)
                ):
                    normalized_inputs = None
                    break
                normalized_inputs.append({
                    "path": path,
                    "sha256": sha256,
                    "bytes": size,
                })
        else:
            normalized_inputs = None
        actual_inputs = starting_snapshot.source_inputs()
        checks["source_tree"] = (
            isinstance(source_tree, dict)
            and source_tree.get("algorithm") == "sha256"
            and source_tree.get("canonicalization") == _SOURCE_CANONICALIZATION
            and normalized_inputs is not None
            and normalized_inputs == actual_inputs
            and source_tree.get("digest") == _source_tree_digest(actual_inputs)
        )
        if not checks["source_tree"]:
            receipt["errors"].append(
                "native source-tree digest or input inventory"
            )

        compilation_tree = manifest.get("compilation_tree")
        try:
            normalized_compilation_inputs = (
                _normalized_manifest_compilation_inputs(manifest)
            )
        except ValueError:
            normalized_compilation_inputs = None
        actual_compilation_inputs = starting_snapshot.compilation_inputs()
        checks["canonical_compilation_inputs_at_head"] = (
            checks["canonical_compilation_inputs_at_head"]
            and normalized_compilation_inputs
            == actual_compilation_inputs
            == actual_inputs
        )
        checks["compilation_tree"] = (
            isinstance(compilation_tree, dict)
            and compilation_tree.get("algorithm") == "sha256"
            and compilation_tree.get("byte_representation")
            == _COMPILATION_BYTE_REPRESENTATION
            and checks["canonical_compilation_inputs_at_head"]
            and compilation_tree.get("digest")
            == _source_tree_digest(actual_compilation_inputs)
        )
        if not checks["compilation_tree"]:
            receipt["errors"].append(
                "canonical compilation input-tree digest or inventory"
            )

        by_leaf = _artifact_records(manifest, receipt)
        artifacts_ok = set(by_leaf) == set(REQUIRED_NATIVE_ARTIFACTS)
        for leaf in REQUIRED_NATIVE_ARTIFACTS:
            artifact_ok, pe_ok = _verified_artifact_bytes(
                starting_snapshot.artifact_bytes(leaf),
                by_leaf.get(leaf),
                require_exists_claim=False,
            )
            checks[f"artifact_pe:{leaf}"] = pe_ok
            checks[f"artifact:{leaf}"] = artifact_ok
            if artifact_ok:
                artifact_paths.append(native_bin / leaf)
            else:
                artifacts_ok = False
                receipt["errors"].append(f"manifest artifact binding: {leaf}")
        checks["artifacts"] = artifacts_ok
        display_membership = manifest.get("display_membership")
        checks["display_membership_ready"] = (
            isinstance(display_membership, dict)
            and display_membership.get("ready") is True
            and display_membership.get("canonical_arx_current") is True
            and by_leaf.get("Ariadne.AcadNative.arx", {}).get("current") is True
        )
        if not checks["display_membership_ready"]:
            receipt["errors"].append(
                "canonical ARX is not current for display membership"
            )

    try:
        ending_snapshot = _capture_native_verification_snapshot(
            router_home,
            native_bin,
            NATIVE_BUILD_MANIFEST_NAME,
            source_paths,
        )
        receipt["ending_input_snapshot_sha256"] = (
            ending_snapshot.captured.aggregate_sha256
        )
        checks["input_snapshot_stable"] = starting_snapshot.same_generation_as(
            ending_snapshot
        )
    except (OSError, ValueError) as exc:
        receipt["ending_input_snapshot_sha256"] = None
        checks["input_snapshot_stable"] = False
        receipt["errors"].append(
            "native build inputs became unavailable during verification: "
            f"{type(exc).__name__}: {exc}"
        )
    if not checks["input_snapshot_stable"]:
        receipt["errors"].append(
            "native build inputs changed during verification"
        )

    final_git = _native_source_git_state(router_home)
    try:
        final_git_source_paths = _git_native_source_paths(router_home)
        final_workspace_source_paths = tuple(
            _discover_native_source_paths(router_home)
        )
    except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
        final_git_source_paths = ()
        final_workspace_source_paths = ()
        receipt["errors"].append(
            "build source inventory became unavailable during verification: "
            f"{type(exc).__name__}: {exc}"
        )
    checks["git_stable"] = (
        current_git.get("available") is True
        and final_git.get("available") is True
        and current_git == final_git
        and final_git_source_paths == git_source_paths
        and final_workspace_source_paths == workspace_source_paths
    )
    if current_git.get("available") is True and not checks["git_stable"]:
        receipt["errors"].append("checkout changed during native build verification")
    receipt["artifact_paths"] = [str(path) for path in artifact_paths]
    receipt["valid"] = not receipt["errors"]
    return receipt
