"""Fail-closed Git checkout verification receipts."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence


_GIT_TIMEOUT_SECONDS = 15.0
_EXACT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_NATIVE_SOURCE_GIT_PATHS = (
    "src/Ariadne.AcadNative",
    "src/Ariadne.AcadNativeDbx",
)
_NATIVE_BUILD_OUTPUT_DIRS = frozenset({"bin", "obj", ".vs", "build"})


class _GitCommandFailed(RuntimeError):
    pass


def _resolve_git_executable() -> str:
    """Return one concrete Git executable, bypassing the Git-for-Windows shim."""

    located = shutil.which("git")
    if not located:
        raise _GitCommandFailed("git executable is unavailable")
    candidate = Path(located).resolve(strict=False)
    if os.name == "nt" and candidate.parent.name.casefold() in {"cmd", "bin"}:
        native = candidate.parent.parent / "mingw64" / "bin" / "git.exe"
        if native.is_file():
            candidate = native.resolve(strict=False)
    return str(candidate)


def _canonical_repo_text_bytes(raw: bytes) -> bytes:
    """Match the repository's text=auto LF identity without running filters."""

    if b"\0" in raw:
        return raw
    return raw.replace(b"\r\n", b"\n")


def _run_git_bytes(repo_root: Path, args: Sequence[str]) -> bytes:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    environment["GIT_TERMINAL_PROMPT"] = "0"
    completed = subprocess.run(
        [
            _resolve_git_executable(),
            "--no-optional-locks",
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"safe.directory={repo_root}",
            "-C",
            str(repo_root),
            *args,
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        timeout=_GIT_TIMEOUT_SECONDS,
        env=environment,
    )
    stderr = completed.stderr.decode("utf-8", errors="strict")
    if completed.returncode != 0:
        raise _GitCommandFailed(stderr.strip() or f"git exited {completed.returncode}")
    return completed.stdout


def _run_git(repo_root: Path, args: Sequence[str]) -> str:
    return _run_git_bytes(repo_root, args).decode("utf-8", errors="strict")


def _blocked_checkout_receipt(
    root: Path,
    expected_head: str,
    *,
    code: str,
    message: str,
) -> dict[str, Any]:
    return {
        "schema": "ariadne.cad_os.checkout_verification.v1",
        "status": "BLOCKED",
        "available": False,
        "repo_root": str(root),
        "expected_head": expected_head,
        "head": "UNKNOWN",
        "clean": "UNKNOWN",
        "status_sha256": "UNKNOWN",
        "checks": {
            "expected_head_format": True,
            "git_available": False,
            "head_matches": False,
            "clean": False,
            "index_visibility_unmodified": "UNKNOWN",
            "start_end_consistent": False,
        },
        "errors": [{"code": code, "message": message}],
    }


def _blocked_native_receipt(root: Path, *, code: str, message: str) -> dict[str, Any]:
    return {
        "schema": "ariadne.cad_os.native_source_checkout_observation.v1",
        "status": "BLOCKED",
        "available": False,
        "repo_root": str(root),
        "head": "UNKNOWN",
        "native_source_dirty": "UNKNOWN",
        "native_source_status_sha256": "UNKNOWN",
        "checks": {
            "git_available": False,
            "index_visibility_unmodified": "UNKNOWN",
            "start_end_consistent": False,
        },
        "errors": [{"code": code, "message": message}],
    }


def _is_native_build_output_component(component: str) -> bool:
    normalized = component.casefold()
    return (
        normalized in _NATIVE_BUILD_OUTPUT_DIRS
        or normalized.startswith("obj-")
        or normalized.startswith("obj_")
    )


def _native_status_line_tracks_source(line: str) -> bool:
    payload = line[3:] if len(line) >= 3 else line
    for candidate in payload.split(" -> "):
        normalized = candidate.strip().strip('"').replace("\\", "/")
        if not any(
            _is_native_build_output_component(part)
            for part in Path(normalized).parts
        ):
            return True
    return False


def _native_status_text(raw_status: str) -> str:
    return "\n".join(
        line
        for line in raw_status.splitlines()
        if _native_status_line_tracks_source(line)
    )


def _same_resolved_path(left: str, right: Path) -> bool:
    try:
        left_path = Path(left).resolve(strict=False)
        right_path = right.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return False
    return os.path.normcase(str(left_path)) == os.path.normcase(str(right_path))


def _hidden_index_flag_count(raw: bytes) -> int:
    """Count tracked entries whose index flags weaken worktree visibility."""

    count = 0
    for record in raw.split(b"\0"):
        if not record:
            continue
        tag = record[:1]
        if tag == b"S" or (b"a" <= tag <= b"z"):
            count += 1
    return count


def verify_checkout(
    repo_root: str | Path,
    expected_head: str,
    require_clean: bool = True,
) -> dict[str, Any]:
    """Verify an exact revision and stable checkout state."""

    root = Path(repo_root).resolve()
    if not _EXACT_SHA_RE.fullmatch(expected_head):
        return {
            "schema": "ariadne.cad_os.checkout_verification.v1",
            "status": "BLOCKED",
            "observation": "NOT_ATTEMPTED",
            "available": "UNKNOWN",
            "repo_root": str(root),
            "expected_head": expected_head,
            "head": "UNKNOWN",
            "clean": "UNKNOWN",
            "status_sha256": "UNKNOWN",
            "checks": {
                "expected_head_format": False,
                "git_available": "UNKNOWN",
                "head_matches": False,
                "clean": False,
                "index_visibility_unmodified": "UNKNOWN",
                "start_end_consistent": False,
            },
            "errors": [
                {
                    "code": "EXPECTED_HEAD_INVALID",
                    "message": (
                        "expected_head must be exactly 40 lowercase hexadecimal "
                        "characters"
                    ),
                }
            ],
        }
    try:
        git_top_level = _run_git(root, ("rev-parse", "--show-toplevel")).strip()
        if not _same_resolved_path(git_top_level, root):
            return _blocked_checkout_receipt(
                root,
                expected_head,
                code="GIT_ROOT_MISMATCH",
                message="git top-level does not match repo_root",
            )
        head_start = _run_git(root, ("rev-parse", "HEAD")).strip()
        status_start = _run_git(
            root, ("status", "--porcelain=v1", "--untracked-files=all")
        )
        index_flags_start = _run_git_bytes(root, ("ls-files", "-v", "-z"))
        head_end = _run_git(root, ("rev-parse", "HEAD")).strip()
        status_end = _run_git(
            root, ("status", "--porcelain=v1", "--untracked-files=all")
        )
        index_flags_end = _run_git_bytes(root, ("ls-files", "-v", "-z"))
    except subprocess.TimeoutExpired:
        return _blocked_checkout_receipt(
            root,
            expected_head,
            code="GIT_TIMEOUT",
            message="git command exceeded the 15 second timeout",
        )
    except UnicodeError:
        return _blocked_checkout_receipt(
            root,
            expected_head,
            code="GIT_OUTPUT_NOT_UTF8",
            message="git output is not valid UTF-8",
        )
    except _GitCommandFailed:
        return _blocked_checkout_receipt(
            root,
            expected_head,
            code="GIT_COMMAND_FAILED",
            message="git command failed",
        )
    except OSError:
        return _blocked_checkout_receipt(
            root,
            expected_head,
            code="GIT_UNAVAILABLE",
            message="git executable is unavailable",
        )
    if not _EXACT_SHA_RE.fullmatch(head_start) or not _EXACT_SHA_RE.fullmatch(head_end):
        return _blocked_checkout_receipt(
            root,
            expected_head,
            code="GIT_HEAD_INVALID",
            message="git HEAD is not an exact lowercase 40-character SHA",
        )
    hidden_index_flags_start = _hidden_index_flag_count(index_flags_start)
    hidden_index_flags_end = _hidden_index_flag_count(index_flags_end)
    index_visibility_unmodified = hidden_index_flags_start == 0
    clean = not status_start and index_visibility_unmodified
    consistent = (
        head_start == head_end
        and status_start == status_end
        and index_flags_start == index_flags_end
    )
    if not consistent:
        return {
            "schema": "ariadne.cad_os.checkout_verification.v1",
            "status": "BLOCKED",
            "observation": "AMBIGUOUS",
            "available": False,
            "repo_root": str(root),
            "expected_head": expected_head,
            "head": "UNKNOWN",
            "clean": "UNKNOWN",
            "status_sha256": "UNKNOWN",
            "snapshots": {
                "start": {
                    "head": head_start,
                    "clean": not status_start and hidden_index_flags_start == 0,
                    "status_sha256": hashlib.sha256(
                        status_start.encode("utf-8")
                    ).hexdigest(),
                    "index_visibility_sha256": hashlib.sha256(
                        index_flags_start
                    ).hexdigest(),
                },
                "end": {
                    "head": head_end,
                    "clean": not status_end and hidden_index_flags_end == 0,
                    "status_sha256": hashlib.sha256(
                        status_end.encode("utf-8")
                    ).hexdigest(),
                    "index_visibility_sha256": hashlib.sha256(
                        index_flags_end
                    ).hexdigest(),
                },
            },
            "checks": {
                "expected_head_format": True,
                "git_available": True,
                "head_matches": "UNKNOWN",
                "clean": "UNKNOWN",
                "index_visibility_unmodified": "UNKNOWN",
                "start_end_consistent": False,
            },
            "errors": [
                {
                    "code": "CHECKOUT_CHANGED_DURING_VERIFICATION",
                    "message": "checkout HEAD or status changed during verification",
                }
            ],
        }
    passed = head_start == expected_head and (clean or not require_clean) and consistent
    errors: list[dict[str, str]] = []
    if head_start != expected_head:
        errors.append(
            {
                "code": "HEAD_MISMATCH",
                "message": "checkout HEAD does not match expected_head",
            }
        )
    if require_clean and not clean:
        if not index_visibility_unmodified:
            errors.append(
                {
                    "code": "INDEX_VISIBILITY_WEAKENED",
                    "message": (
                        "Git index flags hide tracked worktree changes from status"
                    ),
                }
            )
        elif status_start:
            errors.append(
                {
                    "code": "WORKTREE_DIRTY",
                    "message": "tracked or untracked checkout changes are present",
                }
            )
    return {
        "schema": "ariadne.cad_os.checkout_verification.v1",
        "status": "PASS" if passed else "BLOCKED",
        "available": True,
        "repo_root": str(root),
        "expected_head": expected_head,
        "head": head_start,
        "clean": clean,
        "status_sha256": hashlib.sha256(status_start.encode("utf-8")).hexdigest(),
        "checks": {
            "expected_head_format": True,
            "git_available": True,
            "head_matches": head_start == expected_head,
            "clean": clean,
            "index_visibility_unmodified": index_visibility_unmodified,
            "start_end_consistent": consistent,
        },
        "errors": errors,
    }


def verify_paths_at_revision(
    repo_root: str | Path,
    expected_revision: str,
    observed_digests: Mapping[str, str],
) -> dict[str, Any]:
    """Bind caller-observed file digests to exact blobs at one Git revision."""

    root = Path(repo_root).resolve()
    errors: list[dict[str, str]] = []
    bindings: list[dict[str, object]] = []
    if not _EXACT_SHA_RE.fullmatch(expected_revision):
        errors.append(
            {
                "code": "EXPECTED_REVISION_INVALID",
                "message": "expected_revision must be an exact lowercase commit SHA",
            }
        )
    normalized: list[tuple[str, str]] = []
    if not isinstance(observed_digests, Mapping) or not observed_digests:
        errors.append(
            {
                "code": "OBSERVED_DIGESTS_INVALID",
                "message": "observed_digests must be a non-empty path-to-SHA mapping",
            }
        )
    else:
        for path, digest in observed_digests.items():
            candidate = Path(path) if isinstance(path, str) else None
            normalized_path = path.replace("\\", "/") if isinstance(path, str) else ""
            path_valid = (
                candidate is not None
                and normalized_path == path
                and not candidate.is_absolute()
                and ".." not in candidate.parts
                and path not in {"", "."}
            )
            digest_valid = (
                isinstance(digest, str)
                and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
            )
            if not path_valid or not digest_valid:
                errors.append(
                    {
                        "code": "OBSERVED_DIGEST_RECORD_INVALID",
                        "message": f"invalid observed digest record for path {path!r}",
                    }
                )
                continue
            normalized.append((path, digest))
    if errors:
        return {
            "schema": "ariadne.cad_os.revision_path_binding.v1",
            "status": "BLOCKED",
            "repo_root": str(root),
            "expected_revision": expected_revision,
            "path_count": len(normalized),
            "matched_count": 0,
            "bindings": bindings,
            "errors": errors,
        }
    try:
        git_top_level = _run_git(root, ("rev-parse", "--show-toplevel")).strip()
        if not _same_resolved_path(git_top_level, root):
            raise _GitCommandFailed("git top-level does not match repo_root")
        revision = _run_git(root, ("rev-parse", f"{expected_revision}^{{commit}}")).strip()
        if revision != expected_revision:
            raise _GitCommandFailed("expected revision does not resolve exactly")
        for path, observed_sha256 in sorted(normalized):
            revision_bytes = _run_git_bytes(
                root,
                ("cat-file", "blob", f"{expected_revision}:{path}"),
            )
            canonical_revision_bytes = _canonical_repo_text_bytes(revision_bytes)
            revision_sha256 = hashlib.sha256(revision_bytes).hexdigest()
            revision_is_canonical = revision_bytes == canonical_revision_bytes
            matches = revision_is_canonical and revision_sha256 == observed_sha256
            bindings.append(
                {
                    "path": path,
                    "observed_sha256": observed_sha256,
                    "revision_sha256": revision_sha256,
                    "revision_blob_canonical": revision_is_canonical,
                    "matches": matches,
                }
            )
            if not revision_is_canonical:
                errors.append(
                    {
                        "code": "REVISION_BLOB_NOT_CANONICAL",
                        "message": f"revision text blob is not LF-canonical: {path}",
                    }
                )
            elif not matches:
                errors.append(
                    {
                        "code": "REVISION_BLOB_DIGEST_MISMATCH",
                        "message": f"observed bytes do not match revision blob: {path}",
                    }
                )
    except subprocess.TimeoutExpired:
        errors.append({"code": "GIT_TIMEOUT", "message": "git command timed out"})
    except UnicodeError:
        errors.append(
            {"code": "GIT_OUTPUT_NOT_UTF8", "message": "git metadata is not UTF-8"}
        )
    except _GitCommandFailed:
        errors.append({"code": "GIT_COMMAND_FAILED", "message": "git command failed"})
    except OSError:
        errors.append({"code": "GIT_UNAVAILABLE", "message": "git is unavailable"})
    matched_count = sum(1 for item in bindings if item["matches"] is True)
    return {
        "schema": "ariadne.cad_os.revision_path_binding.v1",
        "status": "PASS" if not errors else "BLOCKED",
        "repo_root": str(root),
        "expected_revision": expected_revision,
        "path_count": len(normalized),
        "matched_count": matched_count,
        "bindings": bindings,
        "errors": errors,
    }


def observe_native_source_checkout(repo_root: str | Path) -> dict[str, Any]:
    """Observe stable Git state for the two fixed native source roots."""

    root = Path(repo_root).resolve()
    status_args = (
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        *_NATIVE_SOURCE_GIT_PATHS,
    )
    visibility_args = (
        "ls-files",
        "-v",
        "-z",
        "--",
        *_NATIVE_SOURCE_GIT_PATHS,
    )
    try:
        git_top_level = _run_git(root, ("rev-parse", "--show-toplevel")).strip()
        if not _same_resolved_path(git_top_level, root):
            return _blocked_native_receipt(
                root,
                code="GIT_ROOT_MISMATCH",
                message="git top-level does not match repo_root",
            )
        head_start = _run_git(root, ("rev-parse", "HEAD")).strip()
        status_start = _native_status_text(_run_git(root, status_args))
        index_flags_start = _run_git_bytes(root, visibility_args)
        head_end = _run_git(root, ("rev-parse", "HEAD")).strip()
        status_end = _native_status_text(_run_git(root, status_args))
        index_flags_end = _run_git_bytes(root, visibility_args)
    except subprocess.TimeoutExpired:
        return _blocked_native_receipt(
            root,
            code="GIT_TIMEOUT",
            message="git command exceeded the 15 second timeout",
        )
    except UnicodeError:
        return _blocked_native_receipt(
            root,
            code="GIT_OUTPUT_NOT_UTF8",
            message="git output is not valid UTF-8",
        )
    except _GitCommandFailed:
        return _blocked_native_receipt(
            root,
            code="GIT_COMMAND_FAILED",
            message="git command failed",
        )
    except OSError:
        return _blocked_native_receipt(
            root,
            code="GIT_UNAVAILABLE",
            message="git executable is unavailable",
        )

    if not _EXACT_SHA_RE.fullmatch(head_start) or not _EXACT_SHA_RE.fullmatch(head_end):
        return _blocked_native_receipt(
            root,
            code="GIT_HEAD_INVALID",
            message="git HEAD is not an exact lowercase 40-character SHA",
        )

    hidden_index_flags_start = _hidden_index_flag_count(index_flags_start)
    hidden_index_flags_end = _hidden_index_flag_count(index_flags_end)
    index_visibility_unmodified = hidden_index_flags_start == 0
    consistent = (
        head_start == head_end
        and status_start == status_end
        and index_flags_start == index_flags_end
    )
    if not consistent:
        return {
            "schema": "ariadne.cad_os.native_source_checkout_observation.v1",
            "status": "BLOCKED",
            "observation": "AMBIGUOUS",
            "available": False,
            "repo_root": str(root),
            "head": "UNKNOWN",
            "native_source_dirty": "UNKNOWN",
            "native_source_status_sha256": "UNKNOWN",
            "snapshots": {
                "start": {
                    "head": head_start,
                    "native_source_dirty": bool(status_start),
                    "native_source_status_sha256": hashlib.sha256(
                        status_start.encode("utf-8")
                    ).hexdigest(),
                    "index_visibility_sha256": hashlib.sha256(
                        index_flags_start
                    ).hexdigest(),
                },
                "end": {
                    "head": head_end,
                    "native_source_dirty": bool(status_end),
                    "native_source_status_sha256": hashlib.sha256(
                        status_end.encode("utf-8")
                    ).hexdigest(),
                    "index_visibility_sha256": hashlib.sha256(
                        index_flags_end
                    ).hexdigest(),
                },
            },
            "checks": {
                "git_available": True,
                "index_visibility_unmodified": "UNKNOWN",
                "start_end_consistent": False,
            },
            "errors": [
                {
                    "code": "CHECKOUT_CHANGED_DURING_VERIFICATION",
                    "message": (
                        "checkout HEAD or native source status changed during "
                        "observation"
                    ),
                }
            ],
        }
    if not index_visibility_unmodified:
        return {
            "schema": "ariadne.cad_os.native_source_checkout_observation.v1",
            "status": "BLOCKED",
            "observation": "UNTRUSTWORTHY",
            "available": True,
            "repo_root": str(root),
            "head": head_start,
            "native_source_dirty": "UNKNOWN",
            "native_source_status_sha256": hashlib.sha256(
                status_start.encode("utf-8")
            ).hexdigest(),
            "index_visibility_sha256": hashlib.sha256(
                index_flags_start
            ).hexdigest(),
            "checks": {
                "git_available": True,
                "index_visibility_unmodified": False,
                "start_end_consistent": True,
            },
            "errors": [
                {
                    "code": "INDEX_VISIBILITY_WEAKENED",
                    "message": (
                        "Git index flags hide native source changes from scoped status"
                    ),
                }
            ],
        }
    errors = []
    return {
        "schema": "ariadne.cad_os.native_source_checkout_observation.v1",
        "status": "PASS" if consistent else "BLOCKED",
        "available": True,
        "repo_root": str(root),
        "head": head_start,
        "native_source_dirty": bool(status_start),
        "native_source_status_sha256": hashlib.sha256(
            status_start.encode("utf-8")
        ).hexdigest(),
        "index_visibility_sha256": hashlib.sha256(index_flags_start).hexdigest(),
        "checks": {
            "git_available": True,
            "index_visibility_unmodified": True,
            "start_end_consistent": consistent,
        },
        "errors": errors,
    }
