#!/usr/bin/env python3
"""Official fail-closed launcher for new E2 experiment commands."""
from __future__ import annotations

import argparse
import hashlib
import json
import numbers
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import experiment_guard
from qualification.engine import validate_downstream_qualification_receipt


_DWG_HEADER_CONTRACT = "ASCII_AC10_PLUS_TWO_DIGITS"
_EXECUTION_PURPOSES = frozenset(
    {"observation_only", "downstream_learning_or_scoring"}
)
_OBSERVATION_SCRIPT = Path(__file__).with_name("experiment_guard.py").resolve()


class _RunnerContractError(Exception):
    """A runner returned an object that cannot be trusted as a terminal result."""

    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type


class _QualificationBundleLock:
    def __init__(self, streams: dict[Path, Any]) -> None:
        self._streams = streams

    @staticmethod
    def _read_stream(stream: Any) -> bytes:
        stream.seek(0)
        raw = stream.read()
        stream.seek(0)
        return raw

    def bound_file_snapshot(self, path: Path) -> dict[str, Any]:
        key = path.resolve(strict=True)
        stream = self._streams[key]
        raw = self._read_stream(stream)
        return {
            "canonical_target": str(key),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "file_identity": _native_file_identity(os.fstat(stream.fileno())),
            "observed_signature": raw[:6],
        }

    def close(self) -> None:
        while self._streams:
            _, stream = self._streams.popitem()
            try:
                stream.seek(0)
                try:
                    if os.name != "nt":
                        import fcntl

                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
            finally:
                stream.close()


def _path_is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    attributes = int(getattr(info, "st_file_attributes", 0) or 0)
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0) or 0)
    is_junction = getattr(path, "is_junction", lambda: False)
    return path.is_symlink() or bool(reparse_flag and attributes & reparse_flag) or is_junction()


def _open_read_snapshot(path: Path) -> Any:
    """Open a readable snapshot that denies concurrent write/delete on Windows."""

    resolved = path.resolve(strict=True)
    if os.name != "nt":
        stream = resolved.open("rb")
        try:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            return stream
        except BaseException:
            stream.close()
            raise

    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(resolved),
        0x80000000,  # GENERIC_READ
        0x00000001,  # FILE_SHARE_READ only: no concurrent write or delete
        None,
        3,  # OPEN_EXISTING
        0x00000080,  # FILE_ATTRIBUTE_NORMAL
        None,
    )
    invalid_handle = wintypes.HANDLE(-1).value
    if handle == invalid_handle:
        raise ctypes.WinError(ctypes.get_last_error(), filename=str(resolved))
    try:
        descriptor = msvcrt.open_osfhandle(
            int(handle), os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
    except BaseException:
        kernel32.CloseHandle(handle)
        raise
    try:
        return os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise


def _lock_bound_evidence(binding: Mapping[str, Any]) -> _QualificationBundleLock:
    """Hold the exact source/probe files through an allowed observation command."""

    paths: list[Path] = []
    for name in ("source", "probe"):
        canonical = binding.get(f"{name}_canonical_target")
        if not isinstance(canonical, str) or not canonical:
            raise ValueError(f"{name} canonical target is not bound")
        path = Path(canonical)
        if _path_is_reparse(path) or _path_is_reparse(path.parent):
            raise ValueError(f"{name} path is a symlink, junction, or reparse point")
        paths.append(path)

    streams: dict[Path, Any] = {}
    lock = _QualificationBundleLock(streams)
    try:
        for path in paths:
            stream = _open_read_snapshot(path)
            try:
                stream.seek(0)
                streams[path.resolve(strict=True)] = stream
            except BaseException:
                stream.close()
                raise

        for name, path in zip(("source", "probe"), paths):
            snapshot = lock.bound_file_snapshot(path)
            requested = Path(str(binding[f"{name}_requested_path"]))
            if not (
                requested.resolve(strict=True) == path.resolve(strict=True)
                and snapshot["sha256"] == binding.get(f"{name}_sha256")
                and snapshot["file_identity"] == binding.get(f"{name}_file_identity")
            ):
                raise ValueError(f"{name} changed before its locked snapshot was acquired")
        return lock
    except BaseException:
        lock.close()
        raise


def _observation_command_allowed(command: Sequence[str]) -> bool:
    """Allow only the repository's read-only guard introspection command."""

    if len(command) < 2 or not all(isinstance(item, str) and item for item in command):
        return False
    try:
        interpreter = Path(command[0]).resolve(strict=True)
        script = Path(command[1]).resolve(strict=True)
    except (OSError, ValueError):
        return False
    if (
        os.path.normcase(str(interpreter)) != os.path.normcase(str(Path(sys.executable).resolve()))
        or os.path.normcase(str(script)) != os.path.normcase(str(_OBSERVATION_SCRIPT))
    ):
        return False
    arguments = list(command[2:])
    if arguments in ([], ["--help"]):
        return True
    return (
        len(arguments) % 2 == 0
        and all(arguments[index] == "--require" for index in range(0, len(arguments), 2))
        and all(
            arguments[index + 1]
            and not arguments[index + 1].startswith("-")
            for index in range(0, len(arguments), 2)
        )
    )


def _run_allowed_command(
    runner: Callable[..., Any], command: Sequence[str]
) -> Any:
    """Invoke the real subprocess with a closed Python import environment."""

    if runner is not subprocess.run:
        return runner(list(command), check=False)
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("PYTHON")
    }
    environment["PYTHONNOUSERSITE"] = "1"
    return runner(
        list(command),
        check=False,
        cwd=_OBSERVATION_SCRIPT.parent,
        env=environment,
    )


def _load_probe(path: Path | None) -> Mapping[str, Any] | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _absolute_requested_path(path: Path) -> Path:
    """Make a path absolute without resolving a symlink, junction, or alias."""

    return Path(os.path.abspath(os.fspath(path)))


def _json_integer(value: object) -> int | None:
    if isinstance(value, numbers.Integral) and not isinstance(value, bool):
        return int(value)
    return None


def _native_file_identity(stat_result: os.stat_result) -> dict[str, int | None]:
    """Return a JSON-safe identity plus freshness fingerprint from one open file."""

    inode = _json_integer(getattr(stat_result, "st_ino", None))
    return {
        "device": _json_integer(getattr(stat_result, "st_dev", None)),
        "inode": inode,
        # Python exposes the Windows file index through st_ino.  Keeping the
        # explicit alias lets cross-platform receipt consumers avoid guessing.
        "file_index": inode,
        "size": _json_integer(getattr(stat_result, "st_size", None)),
        "mtime_ns": _json_integer(getattr(stat_result, "st_mtime_ns", None)),
        "ctime_ns": _json_integer(getattr(stat_result, "st_ctime_ns", None)),
    }


def _dwg_format_validation(signature: bytes, *, status: str = "OBSERVED") -> dict[str, Any]:
    valid = (
        len(signature) == 6
        and signature[:4] == b"AC10"
        and all(ord("0") <= byte <= ord("9") for byte in signature[4:6])
    )
    return {
        "status": status,
        "contract": _DWG_HEADER_CONTRACT,
        "observed_signature": signature.decode("ascii", errors="replace"),
        "observed_signature_hex": signature.hex(),
        "valid": valid,
    }


def _unavailable_dwg_format_validation() -> dict[str, Any]:
    return {
        "status": "NOT_PROVIDED",
        "contract": _DWG_HEADER_CONTRACT,
        "observed_signature": None,
        "observed_signature_hex": None,
        "valid": None,
    }


def _snapshot_file(path: Path, *, capture_bytes: bool = False) -> tuple[dict[str, Any], bytes | None]:
    """Observe the object reached through ``path`` without resolving its alias away.

    The caller records both the lexical requested path and the resolved target.  The
    hash and native identity come from the same open handle reached through the
    requested path.  This is detect-and-invalidate evidence, not an atomic lock.
    """

    requested = _absolute_requested_path(path)
    canonical_before = requested.resolve(strict=True)
    if not canonical_before.is_file():
        raise ValueError(f"{canonical_before}: expected a file")

    digest = hashlib.sha256()
    captured: list[bytes] | None = [] if capture_bytes else None
    signature = b""
    with requested.open("rb") as stream:
        identity = _native_file_identity(os.fstat(stream.fileno()))
        while True:
            chunk = stream.read(1 << 20)
            if not chunk:
                break
            if len(signature) < 6:
                signature += chunk[: 6 - len(signature)]
            digest.update(chunk)
            if captured is not None:
                captured.append(chunk)

    canonical_after = requested.resolve(strict=True)
    snapshot_stable = canonical_before == canonical_after
    snapshot = {
        "requested_path": str(requested),
        "canonical_target": str(canonical_before),
        "canonical_target_after_read": str(canonical_after),
        "sha256": digest.hexdigest(),
        "file_identity": identity,
        "observed_signature": signature,
        "snapshot_stable": snapshot_stable,
        "snapshot_reasons": (
            [] if snapshot_stable else ["REQUESTED_PATH_RETARGETED_DURING_SNAPSHOT"]
        ),
    }
    return snapshot, b"".join(captured) if captured is not None else None


def _record_snapshot(binding: dict[str, Any], name: str, snapshot: Mapping[str, Any]) -> None:
    binding[f"{name}_path"] = snapshot["canonical_target"]  # Compatibility alias.
    binding[f"{name}_requested_path"] = snapshot["requested_path"]
    binding[f"{name}_canonical_target"] = snapshot["canonical_target"]
    binding[f"{name}_sha256"] = snapshot["sha256"]
    binding[f"{name}_file_identity"] = snapshot["file_identity"]
    binding[f"{name}_snapshot_stable"] = snapshot["snapshot_stable"]
    binding[f"{name}_snapshot_reasons"] = snapshot["snapshot_reasons"]


def _evidence_binding(
    *,
    source_drawing: Path | None,
    probe_path: Path | None,
    source_binding_required: bool,
) -> tuple[dict[str, Any], Mapping[str, Any] | None]:
    """Capture source/probe identity, exact bytes, and format evidence at preflight."""

    binding: dict[str, Any] = {
        "source_binding_required": source_binding_required,
        "source_path": None,
        "source_requested_path": None,
        "source_canonical_target": None,
        "source_sha256": None,
        "source_file_identity": None,
        "source_snapshot_stable": None,
        "source_snapshot_reasons": [],
        "source_format_validation": _unavailable_dwg_format_validation(),
        "probe_path": None,
        "probe_requested_path": None,
        "probe_canonical_target": None,
        "probe_sha256": None,
        "probe_file_identity": None,
        "probe_snapshot_stable": None,
        "probe_snapshot_reasons": [],
        "observed_probe_drawing_id": None,
        "verified_probe_drawing_id": None,
        "binding_errors": [],
        "pre_spawn_validation": {"status": "PENDING" if source_binding_required else "NOT_REQUIRED"},
        "post_execution_validation": {"status": "PENDING" if source_binding_required else "NOT_REQUIRED"},
        "terminal_evidence_valid": None,
        "terminal_evidence_validity": "PENDING" if source_binding_required else "NOT_REQUIRED",
        "validation_contract": "DETECT_AND_INVALIDATE_NOT_ATOMIC",
    }
    probe_output: Mapping[str, Any] | None = None

    if source_drawing is not None:
        try:
            source_snapshot, _ = _snapshot_file(source_drawing)
            _record_snapshot(binding, "source", source_snapshot)
            binding["source_format_validation"] = _dwg_format_validation(
                source_snapshot["observed_signature"]
            )
            if source_snapshot["snapshot_stable"] is not True:
                binding["binding_errors"].append(
                    "SOURCE_DRAWING_REQUESTED_PATH_RETARGETED_DURING_PREFLIGHT"
                )
            if binding["source_format_validation"]["valid"] is not True:
                binding["binding_errors"].append("SOURCE_DRAWING_FORMAT_INVALID")
        except (OSError, ValueError) as error:
            binding["source_format_validation"] = {
                **_unavailable_dwg_format_validation(),
                "status": "UNAVAILABLE",
                "valid": False,
            }
            binding["binding_errors"].append(f"SOURCE_DRAWING_UNAVAILABLE: {error}")

    if probe_path is not None:
        try:
            probe_snapshot, raw = _snapshot_file(probe_path, capture_bytes=True)
            _record_snapshot(binding, "probe", probe_snapshot)
            if probe_snapshot["snapshot_stable"] is not True:
                binding["binding_errors"].append(
                    "PROBE_FILE_REQUESTED_PATH_RETARGETED_DURING_PREFLIGHT"
                )
            value = json.loads((raw or b"").decode("utf-8-sig"))
            if not isinstance(value, Mapping):
                raise ValueError(f"{probe_snapshot['canonical_target']}: expected a JSON object")
            probe_output = value
            observed = value.get("drawing_id")
            binding["observed_probe_drawing_id"] = observed if isinstance(observed, str) else None
        except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
            binding["binding_errors"].append(f"PROBE_FILE_UNAVAILABLE_OR_INVALID: {error}")

    return binding, probe_output


def _not_required_validation() -> dict[str, Any]:
    return {
        "status": "NOT_REQUIRED",
        "valid": None,
        "source_requested_path": None,
        "source_canonical_target": None,
        "source_file_identity": None,
        "source_sha256": None,
        "source_requested_path_matches_preflight": None,
        "source_canonical_target_matches_preflight": None,
        "source_file_identity_matches_preflight": None,
        "source_sha256_matches_preflight": None,
        "source_matches_preflight": None,
        "probe_requested_path": None,
        "probe_canonical_target": None,
        "probe_file_identity": None,
        "probe_sha256": None,
        "probe_requested_path_matches_preflight": None,
        "probe_canonical_target_matches_preflight": None,
        "probe_file_identity_matches_preflight": None,
        "probe_sha256_matches_preflight": None,
        "probe_matches_preflight": None,
        "reasons": [],
    }


def _fingerprint_mismatch_reasons(
    expected: Mapping[str, Any], actual: Mapping[str, Any], prefix: str
) -> list[str]:
    reasons: list[str] = []
    identity_keys = ("device", "inode", "file_index")
    stat_keys = ("size", "mtime_ns", "ctime_ns")
    if any(expected.get(key) != actual.get(key) for key in identity_keys):
        reasons.append(f"{prefix}_FILE_IDENTITY_CHANGED")
    if any(expected.get(key) != actual.get(key) for key in stat_keys):
        reasons.append(f"{prefix}_FILE_STAT_CHANGED")
    return reasons


def _revalidate_one(
    *,
    binding: Mapping[str, Any],
    result: dict[str, Any],
    name: str,
    reason_prefix: str,
) -> None:
    expected_requested = binding.get(f"{name}_requested_path")
    expected_canonical = binding.get(f"{name}_canonical_target")
    expected_identity = binding.get(f"{name}_file_identity")
    expected_sha256 = binding.get(f"{name}_sha256")
    if not (
        isinstance(expected_requested, str)
        and isinstance(expected_canonical, str)
        and isinstance(expected_identity, Mapping)
        and isinstance(expected_sha256, str)
    ):
        result["reasons"].append(f"{reason_prefix}_PREFLIGHT_BINDING_MISSING")
        return

    try:
        snapshot, _ = _snapshot_file(Path(expected_requested))
    except (OSError, ValueError) as error:
        result["reasons"].append(f"{reason_prefix}_UNAVAILABLE: {error}")
        return

    result[f"{name}_requested_path"] = snapshot["requested_path"]
    result[f"{name}_canonical_target"] = snapshot["canonical_target"]
    result[f"{name}_file_identity"] = snapshot["file_identity"]
    result[f"{name}_sha256"] = snapshot["sha256"]
    requested_matches = snapshot["requested_path"] == expected_requested
    canonical_matches = snapshot["canonical_target"] == expected_canonical
    identity_matches = snapshot["file_identity"] == expected_identity
    sha256_matches = snapshot["sha256"] == expected_sha256
    result[f"{name}_requested_path_matches_preflight"] = requested_matches
    result[f"{name}_canonical_target_matches_preflight"] = canonical_matches
    result[f"{name}_file_identity_matches_preflight"] = identity_matches
    result[f"{name}_sha256_matches_preflight"] = sha256_matches
    result[f"{name}_matches_preflight"] = all(
        (requested_matches, canonical_matches, identity_matches, sha256_matches)
    )

    if snapshot["snapshot_stable"] is not True:
        result["reasons"].append(f"{reason_prefix}_REQUESTED_PATH_RETARGETED_DURING_REVALIDATION")
    if not requested_matches:
        result["reasons"].append(f"{reason_prefix}_REQUESTED_PATH_CHANGED")
    if not canonical_matches:
        result["reasons"].append(f"{reason_prefix}_CANONICAL_TARGET_CHANGED")
    if not identity_matches:
        result["reasons"].extend(
            _fingerprint_mismatch_reasons(expected_identity, snapshot["file_identity"], reason_prefix)
        )
    if not sha256_matches:
        result["reasons"].append(f"{reason_prefix}_HASH_CHANGED")
    if name == "source":
        source_format = _dwg_format_validation(snapshot["observed_signature"])
        result["source_format_validation"] = source_format
        if source_format["valid"] is not True:
            result["reasons"].append("SOURCE_DRAWING_FORMAT_INVALID")


def _revalidate_evidence(binding: Mapping[str, Any]) -> dict[str, Any]:
    """Re-observe the original requested paths and require every binding facet."""

    if not binding.get("source_binding_required"):
        return _not_required_validation()

    result: dict[str, Any] = {
        "status": "INVALID",
        "valid": False,
        "source_requested_path": None,
        "source_canonical_target": None,
        "source_file_identity": None,
        "source_sha256": None,
        "source_requested_path_matches_preflight": False,
        "source_canonical_target_matches_preflight": False,
        "source_file_identity_matches_preflight": False,
        "source_sha256_matches_preflight": False,
        "source_matches_preflight": False,
        "probe_requested_path": None,
        "probe_canonical_target": None,
        "probe_file_identity": None,
        "probe_sha256": None,
        "probe_requested_path_matches_preflight": False,
        "probe_canonical_target_matches_preflight": False,
        "probe_file_identity_matches_preflight": False,
        "probe_sha256_matches_preflight": False,
        "probe_matches_preflight": False,
        "reasons": [],
    }
    _revalidate_one(binding=binding, result=result, name="source", reason_prefix="SOURCE_DRAWING")
    _revalidate_one(binding=binding, result=result, name="probe", reason_prefix="PROBE_FILE")
    if not result["reasons"]:
        result["status"] = "VALID"
        result["valid"] = True
    return result


def _revalidate_locked_evidence(
    binding: Mapping[str, Any], lock: _QualificationBundleLock
) -> dict[str, Any]:
    """Validate source/probe from the same locked handles held through the runner."""

    result: dict[str, Any] = {
        "status": "INVALID",
        "valid": False,
        "reasons": [],
        "validation_contract": "LOCKED_OPEN_HANDLES_HELD_THROUGH_RUNNER",
    }
    stable_identity_keys = ("device", "inode", "file_index", "size")
    for name, reason_prefix in (("source", "SOURCE_DRAWING"), ("probe", "PROBE_FILE")):
        requested = Path(str(binding.get(f"{name}_requested_path") or ""))
        canonical = Path(str(binding.get(f"{name}_canonical_target") or ""))
        expected_identity = binding.get(f"{name}_file_identity")
        expected_identity = expected_identity if isinstance(expected_identity, Mapping) else {}
        try:
            snapshot = lock.bound_file_snapshot(canonical)
            requested_target = requested.resolve(strict=True)
        except (OSError, ValueError, KeyError) as error:
            result["reasons"].append(f"{reason_prefix}_LOCKED_SNAPSHOT_UNAVAILABLE: {error}")
            continue
        actual_identity = snapshot["file_identity"]
        requested_matches = requested_target == canonical.resolve(strict=True)
        identity_matches = all(
            actual_identity.get(key) == expected_identity.get(key)
            for key in stable_identity_keys
        )
        sha256_matches = snapshot["sha256"] == binding.get(f"{name}_sha256")
        result[f"{name}_requested_path"] = str(requested)
        result[f"{name}_canonical_target"] = snapshot["canonical_target"]
        result[f"{name}_file_identity"] = actual_identity
        result[f"{name}_sha256"] = snapshot["sha256"]
        result[f"{name}_requested_path_matches_preflight"] = requested_matches
        result[f"{name}_canonical_target_matches_preflight"] = (
            snapshot["canonical_target"] == str(canonical)
        )
        result[f"{name}_file_identity_matches_preflight"] = identity_matches
        result[f"{name}_sha256_matches_preflight"] = sha256_matches
        result[f"{name}_matches_preflight"] = all(
            (requested_matches, identity_matches, sha256_matches)
        )
        if not requested_matches:
            result["reasons"].append(f"{reason_prefix}_REQUESTED_PATH_CHANGED")
        if not identity_matches:
            result["reasons"].append(f"{reason_prefix}_FILE_IDENTITY_CHANGED")
        if not sha256_matches:
            result["reasons"].append(f"{reason_prefix}_HASH_CHANGED")
        if name == "source":
            source_format = _dwg_format_validation(snapshot["observed_signature"])
            result["source_format_validation"] = source_format
            if source_format["valid"] is not True:
                result["reasons"].append("SOURCE_DRAWING_FORMAT_INVALID")
    if not result["reasons"]:
        result["status"] = "VALID"
        result["valid"] = True
    return result


def _terminal_block(
    decision: Mapping[str, Any],
    *,
    reason_code: str,
    reason: str,
) -> dict[str, Any]:
    """Turn a qualification decision into an explicit terminal non-success."""

    unverified = list(decision.get("unverified_observables") or [])
    if "source_document_identity" not in unverified:
        unverified.append("source_document_identity")
    return {
        **decision,
        "status": experiment_guard.BLOCKED,
        "exit_code": experiment_guard.EXIT_CODES[experiment_guard.BLOCKED],
        "reason_code": reason_code,
        "reason": reason,
        "unverified_observables": unverified,
    }


def _preflight_guard(qualification: Mapping[str, Any]) -> dict[str, Any]:
    """A disk preflight marker must never look like a terminal READY result."""

    return _terminal_block(
        qualification,
        reason_code="PREFLIGHT_NON_TERMINAL",
        reason="Qualification is recorded separately; this receipt is a non-terminal preflight marker.",
    )


def _fsync_directory_if_available(path: Path) -> None:
    try:
        descriptor = os.open(os.fspath(path), os.O_RDONLY)
    except (AttributeError, NotImplementedError, OSError):
        return
    try:
        try:
            os.fsync(descriptor)
        except (AttributeError, NotImplementedError, OSError):
            # Windows commonly cannot fsync a directory handle.  The file itself
            # was already flushed and fsynced before replace.
            pass
    finally:
        os.close(descriptor)


def _write_receipt(path: Path | None, result: Mapping[str, Any]) -> None:
    """Atomically persist one receipt, or leave the prior receipt untouched."""

    if path is None:
        return
    output = _absolute_requested_path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    descriptor: int | None = None
    temporary: str | None = None
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{output.name}.", suffix=".tmp", dir=os.fspath(output.parent)
        )
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
        temporary = None
        _fsync_directory_if_available(output.parent)
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass
        raise


def _same_lexical_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(os.path.normpath(right))


def _receipt_path_conflicts(
    receipt_path: Path | None,
    binding: Mapping[str, Any],
    qualification_receipt_path: Path | None = None,
) -> list[str]:
    """Reject an output path that resolves to or aliases a bound evidence file."""

    if receipt_path is None:
        return []
    requested = _absolute_requested_path(receipt_path)
    conflicts: list[str] = []
    receipt_canonical: str | None = None
    receipt_identity: Mapping[str, Any] | None = None
    try:
        receipt_snapshot, _ = _snapshot_file(requested)
        receipt_canonical = receipt_snapshot["canonical_target"]
        receipt_identity = receipt_snapshot["file_identity"]
    except (OSError, ValueError):
        # A missing future receipt path cannot yet alias an existing file.
        pass

    if qualification_receipt_path is not None:
        qualification_requested = _absolute_requested_path(qualification_receipt_path)
        try:
            qualification_snapshot, _ = _snapshot_file(qualification_requested)
        except (OSError, ValueError):
            qualification_snapshot = None
        if _same_lexical_path(str(requested), str(qualification_requested)):
            conflicts.append("RECEIPT_PATH_ALIASES_QUALIFICATION_RECEIPT")
        elif qualification_snapshot is not None:
            if (
                receipt_canonical is not None
                and _same_lexical_path(
                    receipt_canonical,
                    str(qualification_snapshot["canonical_target"]),
                )
            ):
                conflicts.append("RECEIPT_PATH_ALIASES_QUALIFICATION_RECEIPT")
            elif isinstance(receipt_identity, Mapping):
                qualification_identity = qualification_snapshot["file_identity"]
                identity_keys = ("device", "inode", "file_index")
                if all(
                    receipt_identity.get(key) is not None
                    and receipt_identity.get(key) == qualification_identity.get(key)
                    for key in identity_keys
                ):
                    conflicts.append("RECEIPT_PATH_ALIASES_QUALIFICATION_RECEIPT")

    for name, label in (("source", "SOURCE_DRAWING"), ("probe", "PROBE_FILE")):
        evidence_requested = binding.get(f"{name}_requested_path")
        evidence_canonical = binding.get(f"{name}_canonical_target")
        evidence_identity = binding.get(f"{name}_file_identity")
        if isinstance(evidence_requested, str) and _same_lexical_path(
            str(requested), evidence_requested
        ):
            conflicts.append(f"RECEIPT_PATH_ALIASES_{label}")
            continue
        if isinstance(receipt_canonical, str) and isinstance(evidence_canonical, str):
            if _same_lexical_path(receipt_canonical, evidence_canonical):
                conflicts.append(f"RECEIPT_PATH_ALIASES_{label}")
                continue
        if isinstance(receipt_identity, Mapping) and isinstance(evidence_identity, Mapping):
            identity_keys = ("device", "inode", "file_index")
            if all(
                receipt_identity.get(key) is not None
                and receipt_identity.get(key) == evidence_identity.get(key)
                for key in identity_keys
            ):
                conflicts.append(f"RECEIPT_PATH_ALIASES_{label}")
    return conflicts


def _base_result(
    *, decision: Mapping[str, Any], binding: Mapping[str, Any], command: Sequence[str]
) -> dict[str, Any]:
    return {
        "schema": "ariadne.e2.guarded_experiment_run.v1",
        "qualification": dict(decision),
        "guard": dict(decision),
        "evidence_binding": binding,
        "executed": False,
        "command": list(command),
        "command_exit_code": None,
        "receipt_phase": "TERMINAL",
        "terminal_state": "NOT_EXECUTED_GUARD_NOT_READY",
        "execution_outcome": "NOT_EXECUTED_GUARD_NOT_READY",
        "evidence_authorized": None,
        "command_succeeded": False,
        "terminal_success": False,
        "terminal_authorized": False,
        "receipt_persisted": None,
    }


def _preflight_receipt(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **result,
        "guard": _preflight_guard(result["qualification"]),
        "receipt_phase": "PREFLIGHT",
        "terminal_state": "NON_TERMINAL",
        "execution_outcome": "PREFLIGHT_NON_TERMINAL",
        "evidence_authorized": None,
        "command_succeeded": False,
        "terminal_success": False,
        "terminal_authorized": False,
        "receipt_persisted": True,
    }


def _receipt_write_failed(result: Mapping[str, Any], error: Exception) -> dict[str, Any]:
    failed = {
        **result,
        "guard": _terminal_block(
            result["qualification"],
            reason_code="RECEIPT_WRITE_FAILED",
            reason="The guarded lifecycle could not durably persist its authoritative receipt.",
        ),
        "receipt_phase": "TERMINAL",
        "terminal_state": "RECEIPT_WRITE_FAILED",
        "execution_outcome": "RECEIPT_WRITE_FAILED",
        "terminal_success": False,
        "terminal_authorized": False,
        "receipt_persisted": False,
        "receipt_write_error_type": type(error).__name__,
        "receipt_write_error": str(error),
    }
    return failed


def _persist_terminal(result: dict[str, Any], receipt_path: Path | None) -> dict[str, Any]:
    if receipt_path is None:
        result["receipt_persisted"] = None
        return result
    result["receipt_persisted"] = True
    try:
        _write_receipt(receipt_path, result)
    except Exception as error:
        return _receipt_write_failed(result, error)
    return result


def _persist_preflight(result: Mapping[str, Any], receipt_path: Path | None) -> dict[str, Any] | None:
    if receipt_path is None:
        return None
    try:
        _write_receipt(receipt_path, _preflight_receipt(result))
    except Exception as error:
        return _receipt_write_failed(result, error)
    return None


def _validated_returncode(completed: Any) -> int:
    try:
        returncode = completed.returncode
    except Exception as error:
        raise _RunnerContractError(
            "MISSING_RETURNCODE", "The runner result did not expose a readable integral returncode."
        ) from error
    if not isinstance(returncode, numbers.Integral) or isinstance(returncode, bool):
        raise _RunnerContractError(
            "INVALID_RETURNCODE", "The runner result returncode was missing or not an integral command exit code."
        )
    return int(returncode)


def _record_terminal_evidence(
    result: dict[str, Any], binding: dict[str, Any], validation: Mapping[str, Any]
) -> None:
    if not binding["source_binding_required"]:
        result["evidence_authorized"] = None
        return
    evidence_authorized = validation.get("valid") is True
    result["evidence_authorized"] = evidence_authorized
    binding["terminal_evidence_valid"] = evidence_authorized
    binding["terminal_evidence_validity"] = "VALID" if evidence_authorized else "INVALID"


def run_guarded(
    *,
    required_observables: Iterable[str],
    command: Sequence[str],
    execution_purpose: str,
    experiment_id: str | None = None,
    command_config: Mapping[str, Any] | None = None,
    candidate: str = "auto",
    conclusion: str = "exploratory",
    probe_output: Mapping[str, Any] | None = None,
    probe_path: Path | None = None,
    source_drawing: Path | None = None,
    allow_empty: bool = False,
    independent_oracle_receipt: Mapping[str, Any] | None = None,
    target_population_oracle: Mapping[str, Any] | None = None,
    model_input_output: Mapping[str, Any] | None = None,
    qualification_receipt_path: Path | None = None,
    receipt_path: Path | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    required = list(required_observables)
    if command_config is not None and not isinstance(command_config, Mapping):
        raise TypeError("command_config must be a JSON object")
    effective_command_config = json.loads(
        json.dumps(dict(command_config or {}), allow_nan=False)
    )
    decision = experiment_guard.qualify(
        required_observables=required,
        candidate=candidate,
        conclusion=conclusion,
    )
    source_binding_required = (
        execution_purpose == "downstream_learning_or_scoring"
        or "source_document_identity" in required
    )
    binding, bound_probe_output = _evidence_binding(
        source_drawing=source_drawing,
        probe_path=probe_path,
        source_binding_required=source_binding_required,
    )
    # A supplied probe path is authoritative.  Its exact hashed bytes replace
    # an in-memory payload so a stale caller value cannot authorize execution.
    effective_probe = bound_probe_output if probe_path is not None else probe_output
    expected_source_sha256 = binding["source_sha256"]
    if source_binding_required and probe_path is None:
        binding["binding_errors"].append("PROBE_FILE_BINDING_REQUIRED")
        expected_source_sha256 = None

    if effective_probe is not None and decision["status"] == experiment_guard.NEEDS_PROBE:
        decision = experiment_guard.verify_probe(
            decision,
            effective_probe,
            allow_empty=allow_empty,
            independent_oracle_receipt=independent_oracle_receipt,
            target_population_oracle=target_population_oracle,
            model_input_output=model_input_output,
            expected_source_sha256=expected_source_sha256,
        )

    source_identity = decision.get("source_document_identity")
    if isinstance(source_identity, Mapping):
        binding["verified_probe_drawing_id"] = source_identity.get("verified_probe_drawing_id")

    result = _base_result(decision=decision, binding=binding, command=command)
    result["execution_purpose"] = execution_purpose
    result["experiment_id"] = experiment_id
    result["command_config"] = effective_command_config
    authorization_context = {
        "execution_purpose": execution_purpose,
        "experiment_id": experiment_id,
        "required_observables": sorted(set(required)),
        "source_path": binding.get("source_canonical_target"),
        "source_requested_path": binding.get("source_requested_path"),
        "source_sha256": binding.get("source_sha256"),
        "command": list(command),
        "command_config": effective_command_config,
    }
    result["qualification_receipt_validation"] = (
        validate_downstream_qualification_receipt(
            qualification_receipt_path,
            authorization_context=authorization_context,
        )
        if execution_purpose == "downstream_learning_or_scoring"
        and qualification_receipt_path is not None
        else {"status": "NOT_REQUIRED", "path": None}
    )
    validation_digest = result["qualification_receipt_validation"].get(
        "authorization_snapshot_digest"
    )
    result["qualification_authorization_snapshot"] = (
        {
            "digest": validation_digest,
            "qualification_receipt_sha256": result[
                "qualification_receipt_validation"
            ].get("sha256"),
            "experiment_id": experiment_id,
            "required_observables": authorization_context["required_observables"],
            "source_path": authorization_context["source_path"],
            "source_requested_path": authorization_context["source_requested_path"],
            "source_sha256": authorization_context["source_sha256"],
            "command": list(command),
            "command_config": effective_command_config,
        }
        if validation_digest is not None
        else None
    )
    receipt_conflicts = _receipt_path_conflicts(
        receipt_path,
        binding,
        qualification_receipt_path,
    )
    if receipt_conflicts:
        result["guard"] = _terminal_block(
            decision,
            reason_code="RECEIPT_PATH_ALIASES_EVIDENCE",
            reason="The requested receipt path aliases a source or probe evidence file.",
        )
        result["terminal_state"] = "RECEIPT_PATH_ALIASES_EVIDENCE"
        result["execution_outcome"] = "NOT_EXECUTED_RECEIPT_PATH_ALIASES_EVIDENCE"
        result["receipt_persisted"] = False
        result["receipt_path_conflicts"] = receipt_conflicts
        if source_binding_required:
            result["evidence_authorized"] = False
            binding["terminal_evidence_valid"] = False
            binding["terminal_evidence_validity"] = "RECEIPT_PATH_ALIASES_EVIDENCE"
        return result

    source_format = binding["source_format_validation"]
    if source_drawing is not None and source_format.get("valid") is not True:
        result["guard"] = _terminal_block(
            decision,
            reason_code="SOURCE_DRAWING_FORMAT_INVALID",
            reason="--source-drawing must begin with a conservative DWG AC10xx header.",
        )
        result["terminal_state"] = "SOURCE_DRAWING_FORMAT_INVALID"
        result["execution_outcome"] = "NOT_EXECUTED_SOURCE_DRAWING_FORMAT_INVALID"
        result["evidence_authorized"] = False if source_binding_required else None
        if source_binding_required:
            binding["terminal_evidence_valid"] = False
            binding["terminal_evidence_validity"] = "SOURCE_DRAWING_FORMAT_INVALID"
        return _persist_terminal(result, receipt_path)

    if decision["status"] != experiment_guard.READY:
        if source_binding_required:
            result["evidence_authorized"] = False
            binding["terminal_evidence_valid"] = False
            binding["terminal_evidence_validity"] = "NOT_READY"
        return _persist_terminal(result, receipt_path)

    if execution_purpose not in _EXECUTION_PURPOSES:
        result["guard"] = _terminal_block(
            decision,
            reason_code="EXECUTION_PURPOSE_INVALID",
            reason="Execution purpose must be one of the closed public runner modes.",
        )
        result["terminal_state"] = "EXECUTION_PURPOSE_INVALID"
        result["execution_outcome"] = "NOT_EXECUTED_EXECUTION_PURPOSE_INVALID"
        return _persist_terminal(result, receipt_path)

    if execution_purpose == "observation_only" and not _observation_command_allowed(command):
        result["guard"] = _terminal_block(
            decision,
            reason_code="OBSERVATION_COMMAND_NOT_ALLOWED",
            reason=(
                "Observation-only execution is limited to the repository-owned "
                "read-only experiment guard introspection command."
            ),
        )
        result["terminal_state"] = "OBSERVATION_COMMAND_NOT_ALLOWED"
        result["execution_outcome"] = "NOT_EXECUTED_OBSERVATION_COMMAND_NOT_ALLOWED"
        return _persist_terminal(result, receipt_path)

    if (
        execution_purpose == "downstream_learning_or_scoring"
        and qualification_receipt_path is None
    ):
        result["guard"] = _terminal_block(
            decision,
            reason_code="QUALIFICATION_RECEIPT_REQUIRED",
            reason=(
                "Downstream learning or scoring requires an explicit current "
                "qualification receipt before the command may start."
            ),
        )
        result["terminal_state"] = "QUALIFICATION_RECEIPT_REQUIRED"
        result["execution_outcome"] = "NOT_EXECUTED_QUALIFICATION_RECEIPT_REQUIRED"
        return _persist_terminal(result, receipt_path)

    if execution_purpose == "downstream_learning_or_scoring" and not experiment_id:
        result["guard"] = _terminal_block(
            decision,
            reason_code="QUALIFICATION_EXPERIMENT_ID_REQUIRED",
            reason="Downstream execution must name the qualification experiment being consumed.",
        )
        result["terminal_state"] = "QUALIFICATION_EXPERIMENT_ID_REQUIRED"
        result["execution_outcome"] = "NOT_EXECUTED_QUALIFICATION_EXPERIMENT_ID_REQUIRED"
        return _persist_terminal(result, receipt_path)

    if not command:
        result["guard"] = {
            **decision,
            "status": experiment_guard.REDESIGN,
            "exit_code": experiment_guard.EXIT_CODES[experiment_guard.REDESIGN],
            "reason_code": "NO_EXPERIMENT_COMMAND",
            "reason": "The instrument is qualified, but no experiment command was supplied.",
        }
        result["terminal_state"] = "NOT_EXECUTED_NO_COMMAND"
        result["execution_outcome"] = "NOT_EXECUTED_NO_COMMAND"
        if source_binding_required:
            result["evidence_authorized"] = False
            binding["terminal_evidence_valid"] = False
            binding["terminal_evidence_validity"] = "NOT_EXECUTED"
        return _persist_terminal(result, receipt_path)

    if (
        execution_purpose == "downstream_learning_or_scoring"
        and qualification_receipt_path is not None
        and result["qualification_receipt_validation"].get(
            "integrity_status",
            result["qualification_receipt_validation"].get("status"),
        )
        != "PASS"
    ):
        result["guard"] = _terminal_block(
            decision,
            reason_code="QUALIFICATION_RECEIPT_REJECTED",
            reason=(
                "The explicit qualification receipt does not authorize downstream model "
                "learning or scoring, so the command was not started."
            ),
        )
        result["terminal_state"] = "QUALIFICATION_RECEIPT_REJECTED"
        result["execution_outcome"] = "NOT_EXECUTED_QUALIFICATION_RECEIPT_REJECTED"
        return _persist_terminal(result, receipt_path)

    if execution_purpose == "downstream_learning_or_scoring":
        result["guard"] = _terminal_block(
            decision,
            reason_code="SEALED_DOWNSTREAM_EXECUTOR_REQUIRED",
            reason=(
                "The qualification bundle is internally consistent, but an arbitrary "
                "host command cannot prove that it consumed only the qualified source, "
                "model, checkpoint, and independent gold. Downstream execution stays "
                "blocked until a registered OS-confined sealed executor is available."
            ),
        )
        result["terminal_state"] = "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"
        result["execution_outcome"] = (
            "NOT_EXECUTED_SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"
        )
        result["evidence_authorized"] = False
        binding["terminal_evidence_valid"] = False
        binding["terminal_evidence_validity"] = "EXECUTION_NOT_CONFINED"
        return _persist_terminal(result, receipt_path)

    preflight_failure = _persist_preflight(result, receipt_path)
    if preflight_failure is not None:
        return preflight_failure

    pre_spawn_validation = _revalidate_evidence(binding)
    binding["pre_spawn_validation"] = pre_spawn_validation
    if source_binding_required and pre_spawn_validation["valid"] is not True:
        result["guard"] = _terminal_block(
            decision,
            reason_code="EVIDENCE_BINDING_INVALIDATED_BEFORE_SPAWN",
            reason="The requested source drawing or exact probe changed after preflight and before spawn.",
        )
        result["terminal_state"] = "EVIDENCE_BINDING_INVALIDATED_BEFORE_SPAWN"
        result["execution_outcome"] = "NOT_EXECUTED_EVIDENCE_INVALIDATED_BEFORE_SPAWN"
        result["evidence_authorized"] = False
        binding["post_execution_validation"] = {"status": "NOT_RUN", "valid": False}
        binding["terminal_evidence_valid"] = False
        binding["terminal_evidence_validity"] = "INVALIDATED_BEFORE_SPAWN"
        return _persist_terminal(result, receipt_path)

    bound_evidence_lock: _QualificationBundleLock | None = None
    if source_binding_required:
        try:
            bound_evidence_lock = _lock_bound_evidence(binding)
        except (OSError, ValueError) as error:
            result["guard"] = _terminal_block(
                decision,
                reason_code="EVIDENCE_SNAPSHOT_LOCK_FAILED",
                reason=(
                    "The exact source drawing and probe could not be held as one "
                    "locked pre-spawn snapshot."
                ),
            )
            result["terminal_state"] = "EVIDENCE_SNAPSHOT_LOCK_FAILED"
            result["execution_outcome"] = "NOT_EXECUTED_EVIDENCE_SNAPSHOT_LOCK_FAILED"
            result["evidence_snapshot_lock_error_type"] = type(error).__name__
            result["evidence_authorized"] = False
            return _persist_terminal(result, receipt_path)
        binding["validation_contract"] = "LOCKED_OPEN_HANDLES_HELD_THROUGH_RUNNER"

    locked_post_execution_validation: dict[str, Any] | None = None
    try:
        try:
            completed = _run_allowed_command(runner, command)
        except Exception as error:
            post_execution_validation = (
                _revalidate_locked_evidence(binding, bound_evidence_lock)
                if bound_evidence_lock is not None
                else _revalidate_evidence(binding)
            )
            binding["post_execution_validation"] = post_execution_validation
            _record_terminal_evidence(result, binding, post_execution_validation)
            binding["terminal_evidence_valid"] = False
            binding["terminal_evidence_validity"] = "RUNNER_EXCEPTION"
            result["guard"] = _terminal_block(
                decision,
                reason_code="RUNNER_INVOCATION_FAILED",
                reason="The guarded command runner raised before a terminal command result was available.",
            )
            result["terminal_state"] = "RUNNER_INVOCATION_FAILED"
            result["execution_outcome"] = "RUNNER_EXCEPTION"
            result["runner_error_type"] = type(error).__name__
            return _persist_terminal(result, receipt_path)
        locked_post_execution_validation = (
            _revalidate_locked_evidence(binding, bound_evidence_lock)
            if bound_evidence_lock is not None
            else _revalidate_evidence(binding)
        )
    finally:
        if bound_evidence_lock is not None:
            bound_evidence_lock.close()

    result["executed"] = True
    try:
        result["command_exit_code"] = _validated_returncode(completed)
    except _RunnerContractError as error:
        post_execution_validation = _revalidate_evidence(binding)
        binding["post_execution_validation"] = post_execution_validation
        _record_terminal_evidence(result, binding, post_execution_validation)
        binding["terminal_evidence_valid"] = False
        binding["terminal_evidence_validity"] = "RUNNER_CONTRACT_INVALID"
        result["guard"] = _terminal_block(
            decision,
            reason_code="RUNNER_CONTRACT_INVALID",
            reason="The guarded command runner did not return a valid integral command exit code.",
        )
        result["terminal_state"] = "RUNNER_CONTRACT_INVALID"
        result["execution_outcome"] = "RUNNER_CONTRACT_INVALID"
        result["runner_error_type"] = error.error_type
        result["runner_result_type"] = type(completed).__name__
        return _persist_terminal(result, receipt_path)

    post_execution_validation = (
        locked_post_execution_validation
        if locked_post_execution_validation is not None
        else _revalidate_evidence(binding)
    )
    binding["post_execution_validation"] = post_execution_validation
    _record_terminal_evidence(result, binding, post_execution_validation)
    returncode = result["command_exit_code"]
    result["command_succeeded"] = returncode == 0
    if source_binding_required and post_execution_validation["valid"] is not True:
        result["guard"] = _terminal_block(
            decision,
            reason_code="EVIDENCE_BINDING_INVALIDATED_AFTER_EXECUTION",
            reason=(
                "The requested source drawing or exact probe changed during command execution; "
                "the completed command is not an authorized terminal experiment."
            ),
        )
        result["terminal_state"] = "EVIDENCE_BINDING_INVALIDATED_AFTER_EXECUTION"
        result["execution_outcome"] = "COMMAND_COMPLETED_EVIDENCE_INVALIDATED"
        result["evidence_authorized"] = False
        binding["terminal_evidence_valid"] = False
        binding["terminal_evidence_validity"] = "INVALIDATED_AFTER_EXECUTION"
    elif not result["command_succeeded"]:
        result["terminal_state"] = "COMMAND_FAILED"
        result["execution_outcome"] = "COMMAND_FAILED"
    else:
        result["terminal_state"] = "AUTHORIZED_SUCCESS"
        result["execution_outcome"] = "COMMAND_SUCCEEDED"
        result["terminal_success"] = True
        result["terminal_authorized"] = True
    return _persist_terminal(result, receipt_path)


def _requirements(values: Iterable[str]) -> list[str]:
    flattened: list[str] = []
    for value in values:
        flattened.extend(piece.strip() for piece in value.split(",") if piece.strip())
    return flattened


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an E2 experiment command only after instrument qualification."
    )
    parser.add_argument("--require", action="append", default=[], help="Observable token; repeat or comma-separate.")
    parser.add_argument(
        "--execution-purpose",
        required=True,
        choices=sorted(_EXECUTION_PURPOSES),
    )
    parser.add_argument("--experiment-id")
    parser.add_argument(
        "--command-config-json",
        type=Path,
        help="JSON object whose exact canonical identity is bound to downstream authorization.",
    )
    parser.add_argument(
        "--candidate",
        default="auto",
        choices=["auto", "database_summary", "native_graph", "native_graph_worldir_segments"],
    )
    parser.add_argument(
        "--conclusion",
        default="exploratory",
        choices=["exploratory", "direction_changing", "absence", "impossibility"],
    )
    parser.add_argument("--probe-ir", type=Path)
    parser.add_argument(
        "--source-drawing",
        type=Path,
        help="Source or staged DWG to bind and validate when supplied.",
    )
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--independent-oracle-receipt", type=Path)
    parser.add_argument("--target-population-oracle", type=Path)
    parser.add_argument("--model-input-ir", type=Path)
    parser.add_argument(
        "--qualification-receipt",
        type=Path,
        help="Explicit qualification receipt that must authorize downstream learning or scoring.",
    )
    parser.add_argument(
        "--receipt-output",
        type=Path,
        help="Persist a non-terminal preflight marker, then the final terminal receipt.",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    result = run_guarded(
        execution_purpose=args.execution_purpose,
        experiment_id=args.experiment_id,
        command_config=_load_probe(args.command_config_json),
        required_observables=_requirements(args.require),
        command=command,
        candidate=args.candidate,
        conclusion=args.conclusion,
        probe_path=args.probe_ir,
        source_drawing=args.source_drawing,
        allow_empty=args.allow_empty,
        independent_oracle_receipt=_load_probe(args.independent_oracle_receipt),
        target_population_oracle=_load_probe(args.target_population_oracle),
        model_input_output=_load_probe(args.model_input_ir),
        qualification_receipt_path=args.qualification_receipt,
        receipt_path=args.receipt_output,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["guard"]["status"] != experiment_guard.READY:
        return int(result["guard"]["exit_code"])
    if result["executed"]:
        return int(result["command_exit_code"])
    return int(result["guard"]["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
